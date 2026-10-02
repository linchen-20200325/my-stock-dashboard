# -*- coding: utf-8 -*-
"""批 D2 QA 補測：讓獨立 QA 列出的存活突變體轉紅（只加測試，產品碼不動）。

對應 QA 突變編號：#4/#12 #9/#10/#11 #28 #29 #32 #38 #44 #47 #48 #53 #54。
"""
from __future__ import annotations

import time
import types

import pandas as pd
import pytest
import requests

import shared.fail_cooldown as FC
import src.data.core.finmind_client as FMC
import src.data.daily.daily_data_fetchers as DDF
import src.data.macro.tw_macro as TW
import src.data.stock.monthly_revenue_fetcher as MR
import src.data.stock.quarterly_financials_fetcher as QF
import src.services.shortage_screener_service as SVC
from shared.fail_cooldown import FAIL_COOLDOWN_SEC


@pytest.fixture()
def clock(monkeypatch):
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


class _Resp:
    def __init__(self, payload=None, *, status=200, exc=None):
        self.status_code = status
        self._p = payload
        self._exc = exc

    def json(self):
        if self._exc is not None:
            raise self._exc
        return self._p


# ══════════════════════════════════════════════════════════════════
# tw_macro（D2-f40）
# ══════════════════════════════════════════════════════════════════
_TW_FNS = ("fetch_tw_market_snapshot", "fetch_ndc_signal_history", "fetch_ndc_leading_index",
           "fetch_foreign_consecutive_days", "fetch_twse_breadth", "fetch_finmind_foreign_investor")


@pytest.fixture()
def tw_clean():
    def _clear_all():
        for n in _TW_FNS:   # 被 monkeypatch 換成純函式的那幾支沒有 cache_clear
            getattr(getattr(TW, n), "cache_clear", lambda: None)()
    _clear_all()
    yield
    _clear_all()


def _assert_fail_cooldown_then_heal(call, state, n, ok_check, clock):
    """失敗 → 冷卻期內不重算 → 期滿恢復即取得成功 → 成功照舊快取。"""
    bad = call()
    assert not ok_check(bad)
    base = n["c"]
    call()
    assert n["c"] == base, "冷卻期內不重算"
    state["up"] = True
    clock["now"] += FAIL_COOLDOWN_SEC
    good = call()
    assert ok_check(good), "失敗不得入快取：冷卻期滿須重算"
    base = n["c"]
    call()
    assert n["c"] == base, "成功照舊快取"


class TestMarketSnapshot:   # #4 / #12
    def test_fii_failure_not_cached(self, monkeypatch, clock, tw_clean):
        state, n = {"up": False}, {"c": 0}

        def _fii(days_back=7):
            n["c"] += 1
            return {"error": None if state["up"] else "FinMind 抓取失敗", "fii_net": 1 if state["up"] else None}
        monkeypatch.setattr(TW, "fetch_twse_breadth", lambda: {"error": None, "adv": 1})
        monkeypatch.setattr(TW, "fetch_finmind_foreign_investor", _fii)
        monkeypatch.setattr(TW, "fetch_cbc_m1b_m2", lambda: {"m1b_yoy": 1.0})
        _assert_fail_cooldown_then_heal(TW.fetch_tw_market_snapshot, state, n,
                                        lambda r: r["fii"]["error"] is None, clock)

    def test_predicate_fii_leg(self):
        assert not TW._market_snapshot_ok({"breadth": {"error": None},
                                           "fii": {"error": "FinMind 抓取失敗"}})


class TestNdcSignal:   # #9
    def test_fail_cooldown_then_heal(self, monkeypatch, clock, tw_clean):
        state, n = {"up": False}, {"c": 0}
        tbi = pd.DataFrame({"date": [f"2026-0{m}-01" for m in range(1, 7)],
                            "monitoring": [20, 22, 24, 23, 25, 27]})

        def _tbi(months_back=12, token=""):
            n["c"] += 1
            return tbi if state["up"] else None
        monkeypatch.setattr(TW, "fetch_business_indicator_series", _tbi)
        monkeypatch.setattr(TW, "_dgtw_ndc_signal_from_zip", lambda label="": None)
        monkeypatch.setattr(TW, "_dgtw_ndc_indicator_series", lambda *a, **k: None)
        _assert_fail_cooldown_then_heal(TW.fetch_ndc_signal_history, state, n,
                                        lambda r: r["error"] is None and r["score_latest"] == 27, clock)


class TestNdcLeading:   # #10
    def test_fail_cooldown_then_heal(self, monkeypatch, clock, tw_clean):
        state, n = {"up": False}, {"c": 0}
        tbi = pd.DataFrame({"date": [f"2025-{m:02d}-01" for m in range(1, 13)],
                            "monitoring": [20.0] * 12, "leading": [100.0 + m for m in range(12)]})

        def _tbi(months_back=18, token=""):
            n["c"] += 1
            return tbi if state["up"] else None
        monkeypatch.setattr(TW, "fetch_business_indicator_series", _tbi)
        monkeypatch.setattr(TW, "_dgtw_ndc_indicator_series", lambda *a, **k: None)
        _assert_fail_cooldown_then_heal(TW.fetch_ndc_leading_index, state, n,
                                        lambda r: r["error"] is None and r["latest"] is not None, clock)


class TestForeignConsecutive:   # #11
    def test_fail_cooldown_then_heal(self, monkeypatch, clock, tw_clean):
        state, n = {"up": False}, {"c": 0}
        rows = [{"name": "Foreign_Investor", "date": f"2026-09-{d:02d}", "buy": 2e9, "sell": 1e9}
                for d in range(20, 26)]

        def _fu(*a, **k):
            n["c"] += 1
            return _Resp({"data": rows}) if state["up"] else None
        monkeypatch.setattr(TW, "fetch_url", _fu)
        _assert_fail_cooldown_then_heal(TW.fetch_foreign_consecutive_days, state, n,
                                        lambda r: r["error"] is None and r["consec_days"] == 6, clock)


# ══════════════════════════════════════════════════════════════════
# finmind_client（D2-f24）
# ══════════════════════════════════════════════════════════════════
class TestTransientStatus:   # #28 / #29
    @pytest.mark.parametrize("code,want", [(500, True), (503, True), (599, True), (499, False),
                                           (402, True), (429, True), (400, False), (200, False),
                                           (None, False), ("x", False)])
    def test_is_transient_status(self, code, want):
        assert FMC._is_transient_status(code) is want

    @pytest.mark.parametrize("js", [402, 429, 500])
    def test_http200_json_status_counts_as_failure(self, monkeypatch, js):
        monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp({"status": js, "msg": "x"}, status=200))
        failed: list = []
        assert FMC.finmind_get("X", token="t", timeout=1, failed=failed).empty
        assert failed and f"status={js}" in failed[0]

    def test_http500_with_json_counts_as_failure(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp({"status": 400}, status=500))
        failed: list = []
        FMC.finmind_get("X", token="t", timeout=1, failed=failed)
        assert failed


# ══════════════════════════════════════════════════════════════════
# flow snapshot（D2-f31）— 並行抓取本身拋例外 #32
# ══════════════════════════════════════════════════════════════════
def test_flow_pool_exception_not_cached(monkeypatch):
    import concurrent.futures as cf
    monkeypatch.setattr(DDF, "_pkl_get", lambda k, ttl: DDF._CACHE_SENTINEL)
    puts: list = []
    monkeypatch.setattr(DDF, "_pkl_put", lambda k, v: puts.append(k))
    monkeypatch.setattr(DDF, "_fetch_single_cached",
                        lambda sym, period="60d": pd.DataFrame({"close": [1.0]}))
    real = cf.ThreadPoolExecutor
    state = {"boom": True}

    class _Boom(real):
        def map(self, *a, **k):
            if state["boom"]:
                raise RuntimeError("pool down")
            return super().map(*a, **k)
    monkeypatch.setattr(cf, "ThreadPoolExecutor", _Boom)
    DDF.fetch_flow_snapshot.clear()
    try:
        out1 = DDF.fetch_flow_snapshot()
        assert all(v is None for v in out1.values())
        assert not puts, "並行抓取拋例外 → 不寫 pkl"
        state["boom"] = False
        out2 = DDF.fetch_flow_snapshot()
        assert all(v is not None for v in out2.values()), "並行抓取拋例外的結果不得入快取"
    finally:
        DDF.fetch_flow_snapshot.clear()


# ══════════════════════════════════════════════════════════════════
# 單股月營收 with_status（#38）
# ══════════════════════════════════════════════════════════════════
def test_mrev_with_status_first_fresh_failure(monkeypatch, clock):
    from tests.test_d3e_mrev_fail_cache import _World, _install_mr
    import src.data.proxy.proxy_helper as PH
    w = _World(clock)
    monkeypatch.setenv("FINMIND_TOKEN", "dummy-token")
    monkeypatch.setattr(PH, "fetch_url", w.fetch_url)
    _install_mr(MR, monkeypatch, w)
    try:
        df, failed = MR.fetch_monthly_revenue.with_status("2330")
        assert df.empty and failed is True, "第一次（非冷卻命中）的確定失敗也要回 True"
        w.recover()
        clock["now"] += FAIL_COOLDOWN_SEC
        df2, failed2 = MR.fetch_monthly_revenue.with_status("2330")
        assert not df2.empty and failed2 is False
    finally:
        MR.fetch_monthly_revenue.clear()


# ══════════════════════════════════════════════════════════════════
# 季報（D2-f24）— #44 #47 #48
# ══════════════════════════════════════════════════════════════════
_IS_ROW = {"date": "2025-03-31", "type": "Revenue", "origin_name": "營業收入合計", "value": 1000}
_BS_ROW = {"date": "2025-03-31", "type": "Inventories", "origin_name": "存貨", "value": 50}


@pytest.fixture()
def qf(monkeypatch, clock):
    monkeypatch.setenv("FINMIND_TOKEN", "dummy-token")
    QF.fetch_quarterly_shortage_frame.clear()
    yield clock
    QF.fetch_quarterly_shortage_frame.clear()


def test_quarterly_first_dataset_failed_but_second_returned_rows_is_cached(monkeypatch, qf):   # #44
    n = {"c": 0}

    def _get(url, params=None, **k):
        n["c"] += 1
        ds = params["dataset"]
        if ds == "TaiwanStockFinancialStatement":          # 免費版名稱：確定失敗
            return _Resp(None, status=503, exc=ValueError("maintenance"))
        if ds == "TaiwanStockFinancialStatements":
            return _Resp({"status": 200, "data": [_IS_ROW]})
        return _Resp({"status": 200, "data": [_BS_ROW]})
    monkeypatch.setattr(requests, "get", _get)
    out, failed = QF.fetch_quarterly_shortage_frame.with_status("2330")
    assert failed is False and out[0]["revenue"] == 1000, "該表最後拿到資料 → 不算失敗"
    base = n["c"]
    qf["now"] += 100 * FAIL_COOLDOWN_SEC
    QF.fetch_quarterly_shortage_frame("2330")
    assert n["c"] == base, "照舊快取"


def _qtr_world(monkeypatch):
    state, n = {"up": False}, {"c": 0}

    def _get(url, params=None, **k):
        n["c"] += 1
        if not state["up"]:
            raise requests.exceptions.ConnectionError("down")
        ds = params["dataset"]
        return _Resp({"status": 200, "data": [_BS_ROW if ds == "TaiwanStockBalanceSheet" else _IS_ROW]})
    monkeypatch.setattr(requests, "get", _get)
    return state, n


def test_quarterly_clear_clears_cooldown(monkeypatch, qf):   # #47
    state, n = _qtr_world(monkeypatch)
    assert QF.fetch_quarterly_shortage_frame("2330") == []
    state["up"] = True
    QF.fetch_quarterly_shortage_frame.clear()
    assert QF.fetch_quarterly_shortage_frame("2330")[0]["revenue"] == 1000, ".clear() 須同清退避紀錄"


def test_quarterly_success_resets_escalation(monkeypatch, qf):   # #48
    state, n = _qtr_world(monkeypatch)
    QF.fetch_quarterly_shortage_frame("2330")                  # 失敗：冷卻 FAIL_COOLDOWN_SEC
    qf["now"] += FAIL_COOLDOWN_SEC
    state["up"] = True
    assert QF.fetch_quarterly_shortage_frame("2330")[0]["revenue"] == 1000   # 成功 → 歸零
    QF._fetch_quarterly_shortage_frame_cached.clear()          # 只清成功快取
    state["up"] = False
    QF.fetch_quarterly_shortage_frame("2330")                  # 再失敗：冷卻回起點（沒歸零會加倍）
    state["up"] = True
    qf["now"] += FAIL_COOLDOWN_SEC
    assert QF.fetch_quarterly_shortage_frame("2330")[0]["revenue"] == 1000, "成功須歸零遞增退避"


# ══════════════════════════════════════════════════════════════════
# 缺貨掃描（D2-f30）— #53 #54
# ══════════════════════════════════════════════════════════════════
from tests.test_d2_shortage_deep_scan_fail_cache import _frame, _mrev  # noqa: E402


def _svc_world(monkeypatch, *, q_down=(), m_down=()):
    state = {"q": set(q_down), "m": set(m_down), "calls": 0}

    def _q(sid, quarters=12):
        return _qw(sid)[0]

    def _qw(sid, quarters=12):
        state["calls"] += 1
        return ([], True) if sid in state["q"] else (_frame(), False)
    _q.with_status = _qw

    def _m(sid, months=18):
        return _mw(sid)[0]

    def _mw(sid, months=18):
        return (pd.DataFrame(), True) if sid in state["m"] else (_mrev(), False)
    _m.with_status = _mw
    monkeypatch.setattr(SVC, "fetch_quarterly_shortage_frame", _q)
    monkeypatch.setattr(SVC, "fetch_monthly_revenue", _m)
    SVC._scan_cached.clear()
    return state


def test_monthly_only_failure_is_recorded(monkeypatch):   # #54
    _svc_world(monkeypatch, m_down={"1102"})
    failed: list = []
    SVC._score_and_diagnose([("1101", None), ("1102", None)], failed=failed)
    assert failed == ["1102"], "只有月營收確定失敗也要記"
    SVC._scan_cached.clear()


def test_path2_deep_scan_failure_not_cached(monkeypatch):   # #53
    state = _svc_world(monkeypatch, q_down={"1102"})
    monkeypatch.setattr(SVC, "_survivor_pool", lambda n: [])
    monkeypatch.setattr(SVC, "_batch_revenue_with_status",
                        lambda months: (pd.DataFrame({"stock_id": ["1101"], "date": [pd.Timestamp("2026-08-01")],
                                                      "revenue": [1.0]}), False))
    monkeypatch.setattr(SVC, "_candidate_pool", lambda df, max_n: [
        {"stock_id": "1101", "revenue_yoy_last3": [10.0, 20.0, 30.0]},
        {"stock_id": "1102", "revenue_yoy_last3": [10.0, 20.0, 30.0]}])
    try:
        SVC.run_shortage_scan(max_scan=5)
        state["q"] = set()
        calls = state["calls"]
        SVC.run_shortage_scan(max_scan=5)
        assert state["calls"] > calls, "② 深掃有確定失敗 → 不得入快取"
        calls = state["calls"]
        SVC.run_shortage_scan(max_scan=5)
        assert state["calls"] == calls, "成功照舊快取"
    finally:
        SVC._scan_cached.clear()
