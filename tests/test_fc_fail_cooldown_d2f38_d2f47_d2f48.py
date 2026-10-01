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


# ══════════════════════════════════════════════════════════════════
# D2-f47 `_gen`／`_streak` 上限跟著 max_entries 走
# ══════════════════════════════════════════════════════════════════
class TestD2f47GenCapFollowsMaxEntries:
    N = FC._GEN_MAX_ENTRIES + 500

    def test_unbounded_table_keeps_escalating_past_4096_keys(self, fc_clock):
        """單股月營收的設定（`max_entries=sys.maxsize`）：超過 4096 個不同鍵後，最早的鍵仍照常加倍。"""
        import sys
        c = FC.FailCooldown(max_seconds=TTL_1HOUR, max_entries=sys.maxsize)
        _fail_once(c, 0)
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        for i in range(1, self.N):
            _fail_once(c, i)
        _fail_once(c, 0)                                     # 鍵 0 的第 2 次失敗
        assert _window_now(c, 0, fc_clock) == 2 * FAIL_COOLDOWN_SEC, "修前退回基準 180 秒"
        assert len(c._streak) == self.N and len(c._gen) == 0

    def test_success_generation_survives_past_4096_keys(self):
        import sys
        c = FC.FailCooldown(max_entries=sys.maxsize)
        for i in range(self.N):
            c.success(i)
        assert len(c._gen) == self.N and c.begin(0)[1] == 1

    @pytest.mark.parametrize("max_entries", [64, 200, FC._GEN_MAX_ENTRIES])
    def test_small_max_entries_keep_4096_floor(self, max_entries):
        """既有使用者（預設 64、K 線 200）：上限仍是 4096，逐出順序不變（最早插入者先出）。"""
        c = FC.FailCooldown(max_entries=max_entries)
        for i in range(self.N):
            c.success(i)
        assert list(c._gen) == list(range(self.N - FC._GEN_MAX_ENTRIES, self.N))

    def test_cap_between_follows_max_entries(self, fc_clock):
        c = FC.FailCooldown(max_seconds=TTL_1HOUR, max_entries=5000)
        for i in range(6000):
            c.success(i)
            _fail_once(c, ("s", i))
        assert len(c._gen) == 5000 and len(c._streak) == 5000 and len(c._last_fail) == 5000

    def test_live_instances(self):
        import sys

        import src.data.stock.monthly_revenue_fetcher as MR
        assert MR._single_fail_cooldown._gen_cap == sys.maxsize
        assert MR._batch_fail_cooldown._gen_cap == FC._GEN_MAX_ENTRIES
