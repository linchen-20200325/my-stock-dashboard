# -*- coding: utf-8 -*-
"""批 D2 — D2-f17：RS 掃描有個股確定抓取失敗時，部分失敗的排行不入快取。

三個最容易出錯的輸入（§6）：
1. 部分個股 L1 確定失敗、其餘正常 → 回傳同修前（失敗那檔不在排行），但不入 1 小時快取
2. 冷卻期滿、上游恢復 → 必須重掃、拿到完整排行
3. L1 沒有 `.with_status`（純函式）→ 照修前、照舊快取（不猜）
另：L1 `fetch_stock_history_1y.with_status` 的判準（沒拿到任何 K 線且 Yahoo 確定失敗才算）。
"""
from __future__ import annotations

import time
import types

import pandas as pd
import pytest

import shared.fail_cooldown as FC
import src.services.rs_leader_service as RS
from tests.test_rs_leader_service import _market_series, _series


@pytest.fixture()
def clock(monkeypatch):
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


@pytest.fixture()
def world(monkeypatch, clock):
    price_map = {"A": _series(+0.10, seed=11), "B": _series(-0.05, seed=12),
                 "C": _series(-0.55, seed=13)}
    state = {"down": {"B"}, "calls": 0}

    def _ws(sid):
        state["calls"] += 1
        if sid in state["down"]:
            return (None, None), True
        return (price_map[sid], f"{sid}.TW"), False

    def _plain(sid):
        return _ws(sid)[0]
    _plain.with_status = _ws

    monkeypatch.setattr(RS, "_survivor_pool", lambda n: ["A", "B", "C"][:n])
    monkeypatch.setattr(RS, "fetch_yf_close", lambda tk, range_="2y": _market_series(-0.30))
    monkeypatch.setattr(RS, "fetch_stock_history_1y", _plain)
    RS._scan_cached.clear()
    yield state
    RS._scan_cached.clear()


def test_partial_failure_not_cached_then_heals(world, clock):
    rows1, _ = RS.run_rs_leader_scan(lookback=120)
    assert "B" not in [r["代碼"] for r in rows1] and len(rows1) >= 1
    world["down"] = set()
    calls = world["calls"]
    RS.run_rs_leader_scan(lookback=120)
    assert world["calls"] == calls, "冷卻期內不重掃（掃描層退避）"
    clock["now"] += 100 * FC.FAIL_COOLDOWN_SEC
    rows2, _ = RS.run_rs_leader_scan(lookback=120)
    assert "B" in [r["代碼"] for r in rows2], "部分失敗的排行不得被快取擋住"
    calls = world["calls"]
    clock["now"] += 100 * FC.FAIL_COOLDOWN_SEC
    RS.run_rs_leader_scan(lookback=120)
    assert world["calls"] == calls, "成功照舊快取"


def test_without_with_status_cached_as_before(world, monkeypatch, clock):
    price_map = {"A": _series(+0.10, seed=11), "C": _series(-0.55, seed=13)}
    n = {"c": 0}

    def _plain(sid):
        n["c"] += 1
        return price_map.get(sid), f"{sid}.TW"
    monkeypatch.setattr(RS, "fetch_stock_history_1y", _plain)
    RS.run_rs_leader_scan(lookback=120)
    c = n["c"]
    clock["now"] += 100 * FC.FAIL_COOLDOWN_SEC
    RS.run_rs_leader_scan(lookback=120)
    assert n["c"] == c, "分不出失敗 → 照舊快取"


class TestPickerWithStatus:
    def _install(self, monkeypatch, per_suffix):
        import src.data.proxy.yf_proxy as YP
        import src.data.core.data_loader as DL

        def _ch(tk, period="1y"):
            return per_suffix[tk.rsplit(".", 1)[1]][0]

        def _ch_ws(tk, period="1y"):
            return per_suffix[tk.rsplit(".", 1)[1]]
        _ch.with_status = _ch_ws
        monkeypatch.setattr(YP, "cached_history", _ch)
        monkeypatch.setattr(DL, "_fetch_finmind_price_raw", lambda *a, **k: pd.DataFrame())

    def test_both_suffix_failed_is_failure(self, monkeypatch):
        from src.data.stock.picker_fetcher import fetch_stock_history_1y as F
        self._install(monkeypatch, {"TW": (pd.DataFrame(), True), "TWO": (pd.DataFrame(), True)})
        assert F.with_status("2330") == ((None, None), True)
        assert F("2330") == (None, None)

    def test_no_data_without_failure_is_not_failure(self, monkeypatch):
        from src.data.stock.picker_fetcher import fetch_stock_history_1y as F
        self._install(monkeypatch, {"TW": (pd.DataFrame(), False), "TWO": (pd.DataFrame(), False)})
        assert F.with_status("9999") == ((None, None), False)

    def test_short_history_with_other_suffix_failed_is_not_failure(self, monkeypatch):
        from src.data.stock.picker_fetcher import fetch_stock_history_1y as F
        short = _series(0.0, n=30)
        self._install(monkeypatch, {"TW": (short, False), "TWO": (pd.DataFrame(), True)})
        assert F.with_status("1234")[1] is False, "拿到 K 線（只是太短）→ 上游有回應，不算失敗"

    def test_success(self, monkeypatch):
        from src.data.stock.picker_fetcher import fetch_stock_history_1y as F
        ok = _series(0.1, n=160)
        self._install(monkeypatch, {"TW": (ok, False), "TWO": (pd.DataFrame(), True)})
        (df, resolved), failed = F.with_status("2330")
        assert resolved == "2330.TW" and failed is False and len(df) == 160
