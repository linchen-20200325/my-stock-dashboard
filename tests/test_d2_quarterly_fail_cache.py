# -*- coding: utf-8 -*-
"""批 D2 — D2-f24：季報 `fetch_quarterly_shortage_frame` 確定抓取失敗不入快取（`finmind_get(failed=…)`）。

三個最容易出錯的輸入（§6）：
1. 連線錯誤／402 額度／5xx → 確定失敗：不入快取、冷卻期內不重打、期滿重抓
2. 一張表成功、另一張確定失敗 → 半套結果照舊回傳，但不入快取
3. 200 但沒資料、或 400（方案不支援）→ 分不出失敗與沒資料 → 照舊快取（不猜）
"""
from __future__ import annotations

import types
import time

import pandas as pd
import pytest
import requests

import shared.fail_cooldown as FC
import src.data.core.finmind_client as FMC
import src.data.stock.quarterly_financials_fetcher as QF
from shared.fail_cooldown import FAIL_COOLDOWN_SEC


class _Resp:
    def __init__(self, payload=None, *, status=200, exc=None):
        self.status_code = status
        self._p = payload
        self._exc = exc

    def json(self):
        if self._exc is not None:
            raise self._exc
        return self._p


@pytest.fixture()
def clock(monkeypatch):
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    QF.fetch_quarterly_shortage_frame.clear()
    yield t
    QF.fetch_quarterly_shortage_frame.clear()


class TestFinmindGetFailedReport:
    @pytest.mark.parametrize("resp,expect", [
        (lambda: (_ for _ in ()).throw(requests.exceptions.ConnectionError("x")), True),
        (lambda: _Resp({"status": 402, "msg": "Requests reach the upper limit."}, status=402), True),
        (lambda: _Resp(None, status=500, exc=ValueError("Expecting value")), True),
        (lambda: _Resp({"status": 429}, status=429), True),
        (lambda: _Resp([1, 2]), True),                                   # 非 dict JSON
        (lambda: _Resp({"status": 200, "data": []}), False),            # 真的沒資料
        (lambda: _Resp({"status": 400, "msg": "plan"}, status=400), False),  # 分不出來，不猜
    ])
    def test_failed_list(self, monkeypatch, resp, expect):
        monkeypatch.setattr(requests, "get", lambda *a, **k: resp())
        failed: list = []
        out = FMC.finmind_get("TaiwanStockBalanceSheet", data_id="2330", token="t",
                              timeout=1, failed=failed)
        assert isinstance(out, pd.DataFrame) and out.empty
        assert bool(failed) is expect, failed

    def test_default_none_unchanged(self, monkeypatch):
        monkeypatch.setattr(requests, "get",
                            lambda *a, **k: _Resp(None, status=500, exc=ValueError("x")))
        assert FMC.finmind_get("X", token="t", timeout=1).empty


_IS_ROW = {"date": "2025-03-31", "type": "Revenue", "origin_name": "營業收入合計", "value": 1000}
_BS_ROW = {"date": "2025-03-31", "type": "Inventories", "origin_name": "存貨", "value": 50}


def _router(bs_mode: dict, n: dict):
    def _get(url, params=None, **k):
        n["get"] += 1
        ds = (params or {}).get("dataset")
        if ds == "TaiwanStockBalanceSheet":
            if bs_mode["down"]:
                return _Resp(None, status=503, exc=ValueError("maintenance"))
            return _Resp({"status": 200, "data": [_BS_ROW]})
        return _Resp({"status": 200, "data": [_IS_ROW]})
    return _get


def test_partial_failure_not_cached(monkeypatch, clock):
    monkeypatch.setenv("FINMIND_TOKEN", "dummy-token")
    n = {"get": 0}
    mode = {"down": True}
    monkeypatch.setattr(requests, "get", _router(mode, n))
    out1 = QF.fetch_quarterly_shortage_frame("2330")
    assert len(out1) == 1 and out1[0]["inventory"] is None, "回傳同修前（半套）"
    assert QF.fetch_quarterly_shortage_frame.with_status("2330")[1] is True
    mode["down"] = False
    base = n["get"]
    QF.fetch_quarterly_shortage_frame("2330")
    assert n["get"] == base, "冷卻期內不重打"
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    out2 = QF.fetch_quarterly_shortage_frame("2330")
    assert out2[0]["inventory"] == 50, "半套結果不得入快取：冷卻期滿須重抓"
    base = n["get"]
    assert QF.fetch_quarterly_shortage_frame("2330")[0]["inventory"] == 50 and n["get"] == base, \
        "成功照舊快取"
    assert QF.fetch_quarterly_shortage_frame.with_status("2330")[1] is False


def test_true_no_data_still_cached(monkeypatch, clock):
    monkeypatch.setenv("FINMIND_TOKEN", "dummy-token")
    n = {"get": 0}

    def _empty(*a, **k):
        n["get"] += 1
        return _Resp({"status": 200, "data": []})
    monkeypatch.setattr(requests, "get", _empty)
    assert QF.fetch_quarterly_shortage_frame("2330") == []
    base = n["get"]
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    assert QF.fetch_quarterly_shortage_frame("2330") == [] and n["get"] == base, "沒資料照舊快取"
