# -*- coding: utf-8 -*-
"""批 D2 — D2-f40：`tw_macro` 其餘 `_ttl_cache` 函式失敗不入快取，並由本層失敗冷卻擋住轟炸。

三個最容易出錯的輸入（§6）：
1. 上游無回應（`fetch_url` 回 None）→ 回傳同修前（error／None），不入 TTL 快取；冷卻期內不重打
2. 冷卻期滿、上游恢復 → 必須重抓
3. 「有回應但沒資料」（外資無 Foreign_Investor 列）→ 照舊快取（不猜）
"""
from __future__ import annotations

import time
import types

import pytest

import shared.fail_cooldown as FC
import src.data.macro.tw_macro as TW


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


@pytest.fixture()
def clock(monkeypatch):
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


_FNS = ("fetch_twse_breadth", "fetch_finmind_foreign_investor", "fetch_cbc_ms1_rows",
        "fetch_business_indicator_series", "fetch_ndc_signal_history", "fetch_ndc_leading_index",
        "fetch_foreign_consecutive_days", "fetch_tw_market_snapshot")


@pytest.fixture(autouse=True)
def _clean():
    for n in _FNS + ("fetch_cbc_m1b_m2",):
        getattr(TW, n).cache_clear()
    yield
    for n in _FNS + ("fetch_cbc_m1b_m2",):
        getattr(TW, n).cache_clear()


def _counting(monkeypatch, responder):
    n = {"c": 0}

    def _fu(*a, **k):
        n["c"] += 1
        return responder()
    monkeypatch.setattr(TW, "fetch_url", _fu)
    return n


_BREADTH_OK = {"date": "20261001", "tables": [{"data": [["上漲(漲停)", "500(10)"], ["下跌(跌停)", "300(2)"]]}]}


def test_breadth_fail_cooldown_then_heal(monkeypatch, clock):
    state = {"up": False}
    n = _counting(monkeypatch, lambda: _Resp(_BREADTH_OK) if state["up"] else None)
    assert TW.fetch_twse_breadth()["error"]
    assert TW.fetch_twse_breadth()["error"] and n["c"] == 1, "冷卻期內不重打上游"
    state["up"] = True
    clock["now"] += FC.FAIL_COOLDOWN_SEC
    out = TW.fetch_twse_breadth()
    assert out["error"] is None and out["adv"] == 500, "失敗不得入 10 分鐘快取"
    c = n["c"]
    TW.fetch_twse_breadth()
    assert n["c"] == c, "成功照舊快取"


def test_fii_fetch_failure_vs_no_data(monkeypatch, clock):
    state = {"mode": "down"}

    def _r():
        if state["mode"] == "down":
            return None
        if state["mode"] == "nodata":
            return _Resp({"data": []})
        return _Resp({"data": [{"name": "Foreign_Investor", "date": "2026-10-01",
                                "buy": 3_000_000_000, "sell": 1_000_000_000}]})
    n = _counting(monkeypatch, _r)
    assert TW.fetch_finmind_foreign_investor()["error"] == "FinMind 抓取失敗"
    state["mode"] = "ok"
    clock["now"] += FC.FAIL_COOLDOWN_SEC
    assert TW.fetch_finmind_foreign_investor()["fii_net"] == 2_000_000_000
    TW.fetch_finmind_foreign_investor.cache_clear()
    state["mode"] = "nodata"
    assert TW.fetch_finmind_foreign_investor()["error"] == "FinMind 無 Foreign_Investor 資料"
    c = n["c"]
    state["mode"] = "ok"
    clock["now"] += 10 * FC.FAIL_COOLDOWN_SEC
    TW.fetch_finmind_foreign_investor()
    assert n["c"] == c, "沒資料那一類照舊快取（不猜）"


def test_ms1_rows_none_not_cached(monkeypatch, clock):
    state = {"up": False}
    _counting(monkeypatch, lambda: _Resp([{"M1B": 1}] * 13) if state["up"] else None)
    url = TW.CBC_MS1_URLS[0]
    assert TW.fetch_cbc_ms1_rows(url, min_rows=13) is None
    state["up"] = True
    clock["now"] += FC.FAIL_COOLDOWN_SEC
    assert TW.fetch_cbc_ms1_rows(url, min_rows=13) is not None


def test_business_indicator_none_not_cached(monkeypatch, clock):
    state = {"up": False}
    rows = [{"date": f"2026-0{m}-01", "monitoring": 20 + m, "leading": 100 + m} for m in range(1, 9)]
    _counting(monkeypatch, lambda: _Resp({"data": rows}) if state["up"] else None)
    assert TW.fetch_business_indicator_series() is None
    state["up"] = True
    clock["now"] += FC.FAIL_COOLDOWN_SEC
    out = TW.fetch_business_indicator_series()
    assert out is not None and len(out) == 8


def test_predicates():
    assert TW._no_error({"error": None}) and not TW._no_error({"error": "x"}) and not TW._no_error(None)
    assert TW._fii_ok({"error": None}) and TW._fii_ok({"error": "外資資料筆數不足"})
    assert not TW._fii_ok({"error": "FinMind 抓取失敗"})
    assert TW._not_none([]) and not TW._not_none(None)
    assert not TW._market_snapshot_ok({"breadth": {"error": "x"}, "fii": {"error": None}})
    assert TW._market_snapshot_ok({"breadth": {"error": None}, "fii": {"error": None}})


def test_ttl_cache_fail_cooldown_default_off(clock):
    calls = {"n": 0}

    @TW._ttl_cache(ttl_sec=60, maxsize=4, cache_if=lambda r: r is not None)
    def _f():
        calls["n"] += 1
        return None
    _f(); _f()
    assert calls["n"] == 2, "未設 fail_cooldown → 修前 D2-f13 行為（每次重算）"

    @TW._ttl_cache(ttl_sec=60, maxsize=4, cache_if=lambda r: r is not None, fail_cooldown=True)
    def _g():
        calls["n"] += 1
        return None
    _g(); _g()
    assert calls["n"] == 3, "fail_cooldown=True → 冷卻期內不重算"
    _g.cache_clear()
    _g()
    assert calls["n"] == 4, "cache_clear 同清退避紀錄"
