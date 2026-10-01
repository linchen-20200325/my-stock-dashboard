# -*- coding: utf-8 -*-
"""批 FC（2026-10-01）：`shared/fail_cooldown.FailCooldown` 三條。

  · **D2-f38** 遞增退避的連續失敗次數**隨時間衰減**：冷卻結束後整整一個 `max_seconds` 都沒再失敗
    → 下一次失敗視為新的一串（冷卻回到 `seconds`）。修前升到上限後，隔天再失敗仍直接冷卻上限秒數。
  · **D2-f47** `_gen`／`_streak` 的鍵數上限跟著 `max_entries` 走（取 `max(max_entries, _GEN_MAX_ENTRIES)`，
    既有 `max_entries ≤ 4096` 的使用者逐字不變）。修前固定 4096 → 不設上限的單股月營收冷卻表
    超過 4096 個鍵後遞增退避失效。
  · **D2-f48** `_prune_locked` 不再每次存取都整表掃描（改以兩個延遲刪除的 heap 依到期／失敗時點排序）。

既有行為以「批 FC 前的原始實作」（`_FC_BEFORE_SRC`，origin/main `8a99564` 逐字）當參考模型逐步比對。
不觸網；假時鐘只換 `shared.fail_cooldown` 的 `time`。
"""
from __future__ import annotations

import random
import threading
import time
import types

import pytest

import shared.fail_cooldown as FC
from shared.fail_cooldown import FAIL_COOLDOWN_SEC
from shared.ttls import TTL_1HOUR


@pytest.fixture
def fc_clock(monkeypatch):
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


def _fail_once(c, key, payload="x"):
    _hit, g = c.begin(key)
    assert _hit is FC.NO_HIT, "前提：此刻不在冷卻期"
    c.fail(key, g, payload)


def _window_now(c, key, clock):
    """實測這個鍵目前的冷卻秒數（從剛失敗的時點往後逐秒推，不讀內部）。"""
    start = clock["now"]
    while c.begin(key)[0] is not FC.NO_HIT:
        clock["now"] += 1
    w = clock["now"] - start
    clock["now"] = start
    return w


# ══════════════════════════════════════════════════════════════════
# D2-f38 連續失敗次數隨時間衰減
# ══════════════════════════════════════════════════════════════════
class TestD2f38StreakDecay:
    def _climb_to_cap(self, c, clock):
        w = FAIL_COOLDOWN_SEC
        while True:
            _fail_once(c, "k")
            got = _window_now(c, "k", clock)
            assert got == w
            clock["now"] += got                             # 冷卻一過期就再失敗（正常遞增路徑）
            if w >= TTL_1HOUR:
                return
            w = min(w * 2, TTL_1HOUR)

    def test_next_day_failure_restarts_from_base(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        self._climb_to_cap(c, fc_clock)
        fc_clock["now"] += 86400                             # 隔天，中間沒成功、也沒再失敗
        _fail_once(c, "k")
        assert _window_now(c, "k", fc_clock) == FAIL_COOLDOWN_SEC, "沉寂一整天 → 從基準冷卻重新起算"

    def test_boundary_quiet_period(self, fc_clock):
        """門檻 ＝ 上一次冷卻秒數 ＋ max_seconds（自上一次失敗起算）：差 1 秒仍延續、剛好滿即重算。"""
        for extra, expect in ((-1, 2 * FAIL_COOLDOWN_SEC), (0, FAIL_COOLDOWN_SEC)):
            c = FC.FailCooldown(max_seconds=TTL_1HOUR)
            _fail_once(c, "k")
            fc_clock["now"] += FAIL_COOLDOWN_SEC + TTL_1HOUR + extra
            _fail_once(c, "k")
            assert _window_now(c, "k", fc_clock) == expect

    def test_after_decay_escalates_again(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        self._climb_to_cap(c, fc_clock)
        fc_clock["now"] += 86400
        self._climb_to_cap(c, fc_clock)                      # 衰減後照常再一路加倍到上限

    def test_continuous_failure_never_decays(self, fc_clock):
        """持續失敗、每 60 秒 rerun 一次（`TestQaN1LoadAmplification` 的情境）：一天內冷卻始終封頂。"""
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        starts = []
        end = fc_clock["now"] + 86400
        while fc_clock["now"] < end:
            h, g = c.begin("k")
            if h is FC.NO_HIT:
                starts.append(fc_clock["now"])
                c.fail("k", g, "x")
            fc_clock["now"] += 60
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        assert gaps[:5] == [180, 360, 720, 1440, 2880]
        assert all(gp == TTL_1HOUR for gp in gaps[5:]), "持續失敗不觸發衰減"

    def test_default_mode_never_writes_decay_state(self, fc_clock):
        c = FC.FailCooldown()
        for _ in range(5):
            _fail_once(c, "k")
            fc_clock["now"] += 86400
        assert c._streak == {} and c._last_fail == {}

    def test_success_and_clear_drop_decay_state(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR)
        _fail_once(c, "a")
        _fail_once(c, "b")
        c.success("a")
        assert "a" not in c._last_fail and "b" in c._last_fail
        c.clear()
        assert c._last_fail == {}
