# -*- coding: utf-8 -*-
"""批 D2 — D2-f30：缺貨掃描逐檔深掃有個股確定抓取失敗時，降級排行不入 L3 1 天快取。

三個最容易出錯的輸入（§6）：
1. 存活池路徑 ①：某檔季報（或月營收）是 L1 確定失敗 → 回傳同修前，但不入快取
2. 上游恢復後同參數再呼叫 → 必須重算、拿到完整排行
3. L1 沒有 `.with_status`（被換成純函式）→ 照修前、照舊快取（不猜）
"""
from __future__ import annotations

import pandas as pd
import pytest

import src.services.shortage_screener_service as SVC


def _frame():
    return [{"label": f"2025Q{q}", "date": f"2025-{q * 3:02d}-30", "revenue": 100.0 + q,
             "gross_profit": 40.0 + q, "cogs": 60.0, "contract_liab": 10.0 + q, "inventory": 5.0}
            for q in (4, 3, 2, 1)] + [
            {"label": f"2024Q{q}", "date": f"2024-{q * 3:02d}-30", "revenue": 90.0 + q,
             "gross_profit": 30.0 + q, "cogs": 60.0, "contract_liab": 5.0 + q, "inventory": 5.0}
            for q in (4, 3, 2, 1)]


def _mrev():
    idx = pd.date_range("2024-01-01", periods=19, freq="MS")
    return pd.DataFrame({"date": idx, "revenue": [100.0 + 5 * i for i in range(19)]})


@pytest.fixture()
def world(monkeypatch):
    state = {"down": {"1102"}, "calls": 0}

    def _qtr(sid, quarters=12):
        return _qtr_ws(sid, quarters)[0]

    def _qtr_ws(sid, quarters=12):
        state["calls"] += 1
        if sid in state["down"]:
            return [], True
        return _frame(), False
    _qtr.with_status = _qtr_ws

    def _mr(sid, months=18):
        return _mr_ws(sid, months)[0]

    def _mr_ws(sid, months=18):
        return _mrev(), False
    _mr.with_status = _mr_ws

    monkeypatch.setattr(SVC, "_survivor_pool", lambda n: ["1101", "1102"])
    monkeypatch.setattr(SVC, "fetch_quarterly_shortage_frame", _qtr)
    monkeypatch.setattr(SVC, "fetch_monthly_revenue", _mr)
    SVC._scan_cached.clear()
    yield state
    SVC._scan_cached.clear()


def test_deep_scan_failure_not_cached_then_heals(world):
    rows1, meta1 = SVC.run_shortage_scan(max_scan=5)
    assert meta1["deep_scanned"] == 2
    codes1 = {r.get("代碼") for r in rows1}
    assert "1102" not in codes1
    world["down"] = set()
    rows2, _ = SVC.run_shortage_scan(max_scan=5)
    assert len(rows2) > len(rows1) or {r.get("代碼") for r in rows2} != codes1, \
        "上游恢復後必須重算，不得回凍住的降級排行"
    calls = world["calls"]
    SVC.run_shortage_scan(max_scan=5)
    assert world["calls"] == calls, "成功照舊快取"


def test_without_with_status_cached_as_before(world, monkeypatch):
    def _plain_qtr(sid, quarters=12):
        world["calls"] += 1
        return [] if sid in world["down"] else _frame()
    monkeypatch.setattr(SVC, "fetch_quarterly_shortage_frame", _plain_qtr)
    SVC.run_shortage_scan(max_scan=5)
    calls = world["calls"]
    SVC.run_shortage_scan(max_scan=5)
    assert world["calls"] == calls, "分不出失敗 → 照舊快取"


def test_score_and_diagnose_failed_list(world):
    failed: list = []
    SVC._score_and_diagnose([("1101", None), ("1102", None)], failed=failed)
    assert failed == ["1102"]
