"""Q3-r5／Q5-r2-r1／Q5-r2-r3（2026-09-27）：L1 失敗不入快取 ＋ 失敗退避 ＋ 股利鏈 REST 腿復活。

CLAUDE.md §1.A-3：(a) 只快取成功結果；(b) 失敗時退避，不連續轟炸來源。
每一條都驗三件事：失敗後冷卻期內**不重打上游**；冷卻期過、上游恢復 → **拿到成功**
（修前會拿到快取住的失敗，直到 TTL 到期）；成功照舊快取（第二次不打上游）。
"""
from __future__ import annotations

import sys

import pandas as pd
import pytest

import src.data.core.data_loader as DL
import src.data.etf.etf_fetch as F
import src.data.proxy.yf_proxy as YP
import src.data.stock.app_stock_fetchers as A
import tests.test_v2_silent_fail_b13_q5r2 as Q
from shared.fail_cooldown import CachedFailure, FailCooldown, NO_HIT

chips_env = Q.chips_env
finmind = Q.finmind


def _ohlcv(n=30):
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    c = [100.0 + i for i in range(n)]
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": [1] * n}, index=idx)


class _YF:
    """可切換的 yfinance 替身；記錄打了幾次上游。"""

    def __init__(self):
        self.mode = "down"
        self.calls = 0

    def Ticker(self, t):  # noqa: N802
        outer = self

        class _T:
            def history(self, *a, **k):
                outer.calls += 1
                if outer.mode == "down":
                    raise ConnectionError("yahoo 429")
                return _ohlcv()

            @property
            def dividends(self):
                outer.calls += 1
                if outer.mode == "down":
                    raise ConnectionError("yahoo 429")
                return pd.Series([1.0], index=[pd.Timestamp.today().normalize()])
        return _T()


# ── 共用元件 ──────────────────────────────────────────────────────
class TestFailCooldown:
    def test_hit_within_window_then_expires(self, monkeypatch):
        c = FailCooldown(seconds=100)
        hit, g = c.begin("k")
        assert hit is NO_HIT
        c.fail("k", g, {"x": 1})
        hit, _ = c.begin("k")
        assert hit == {"x": 1}
        c.seconds = 0
        assert c.begin("k")[0] is NO_HIT

    def test_success_clears_and_race_guard(self):
        c = FailCooldown(seconds=100)
        _, g = c.begin("k")
        c.success("k")                 # 別人在我抓的期間成功了
        c.fail("k", g, "late failure")  # 我的失敗比較晚寫 → 不得覆蓋
        assert c.begin("k")[0] is NO_HIT

    def test_returned_payload_is_a_copy(self):
        c = FailCooldown(seconds=100)
        _, g = c.begin("k")
        c.fail("k", g, [1])
        c.begin("k")[0].append(2)
        assert c.begin("k")[0] == [1]


# ── Q3-r5：ETF 取價 ────────────────────────────────────────────────
@pytest.fixture
def etf_yf(monkeypatch):
    yf = _YF()
    monkeypatch.setattr(F, "yf", yf)
    F._fetch_etf_price_max.clear()
    yield yf
    F._fetch_etf_price_max.clear()


class TestEtfPrice:
    def test_failure_not_cached_and_backs_off(self, etf_yf, monkeypatch):
        out = F._fetch_etf_price_max("0056.TW")
        assert out.empty and "ConnectionError" in out.attrs[F.PRICE_FETCH_FAILED_ATTR]
        assert etf_yf.calls == 1
        etf_yf.mode = "up"
        again = F._fetch_etf_price_max("0056.TW")          # 冷卻期內
        assert etf_yf.calls == 1, "冷卻期內不得重打 Yahoo（§1.A-3(b)）"
        assert F.PRICE_FETCH_FAILED_ATTR in again.attrs, "冷卻期內旗標照帶"
        monkeypatch.setattr(F._price_fail_cooldown, "seconds", 0)
        ok = F._fetch_etf_price_max("0056.TW")
        assert not ok.empty and F.PRICE_FETCH_FAILED_ATTR not in ok.attrs, \
            "上游恢復後必須拿到成功（修前：失敗被快取 1 小時）"
        assert etf_yf.calls == 2

    def test_success_still_cached(self, etf_yf):
        etf_yf.mode = "up"
        a = F._fetch_etf_price_max("0050.TW")
        b = F._fetch_etf_price_max("0050.TW")
        assert etf_yf.calls == 1 and a.equals(b)
        assert a.attrs["price_basis"] == F.PRICE_BASIS_ADJUSTED

    def test_public_failed_param_still_reports(self, etf_yf):
        got: list = []
        assert F.fetch_etf_price("0056.TW", period="1y", failed=got).empty
        assert got and "ConnectionError" in got[0]


# ── Q5-r2-r3：yf_proxy.cached_dividends ─────────────────────────────
@pytest.fixture
def yp_yf(monkeypatch):
    import yfinance
    yf = _YF()
    monkeypatch.setattr(yfinance, "Ticker", yf.Ticker)
    YP.cached_dividends.clear()
    yield yf
    YP.cached_dividends.clear()


class TestYfProxyDividends:
    def test_failure_not_cached_and_backs_off(self, yp_yf, monkeypatch):
        s = YP.cached_dividends("9999.TW")
        assert s.empty and YP.DIVIDENDS_FETCH_FAILED_ATTR in s.attrs
        yp_yf.mode = "up"
        YP.cached_dividends("9999.TW")
        assert yp_yf.calls == 1
        monkeypatch.setattr(YP._dividends_fail_cooldown, "seconds", 0)
        s2 = YP.cached_dividends("9999.TW")
        assert len(s2) == 1 and YP.DIVIDENDS_FETCH_FAILED_ATTR not in s2.attrs
        YP.cached_dividends("9999.TW")
        assert yp_yf.calls == 2, "成功照舊快取"


# ── Q5-r2-r3 ＋ Q5-r2-r1：股利鏈 ─────────────────────────────────────
class _Sess:
    def __init__(self, plan, log):
        self.plan, self.log = plan, log

    def get(self, url, params=None, headers=None, timeout=None):
        key = "twse" if "twse.com.tw" in url else "finmind"
        self.log.append((key, dict(params or {}), dict(headers or {})))
        v = self.plan[key]
        if isinstance(v, Exception):
            raise v
        return Q.B6._Resp(v)


@pytest.fixture
def div(monkeypatch):
    plan = {"finmind": ConnectionError("proxy down"), "twse": ConnectionError("twse down")}
    yf = {"s": Q._yf_divs("raise")}
    log: list = []
    # production：FinMind SDK 未安裝
    monkeypatch.setitem(sys.modules, "FinMind", None)
    monkeypatch.setitem(sys.modules, "finmind", None)
    monkeypatch.setattr(A, "_make_proxy_session", lambda: _Sess(plan, log))
    monkeypatch.setattr(A, "_get_finmind_token", lambda: "tok")
    monkeypatch.setattr(YP, "cached_dividends", lambda t: yf["s"])
    A._fetch_dividend_data_cached.clear()
    yield plan, yf, log
    A._fetch_dividend_data_cached.clear()


_FM_ROWS = {"status": 200, "data": [
    {"date": "2024-07-01", "CashEarningsDistribution": 4.0, "CashDividend": 4.0},
    {"date": "2025-07-01", "CashEarningsDistribution": 5.0, "CashDividend": 5.0}]}


class TestDividendChain:
    def test_r1_rest_leg_runs_without_sdk(self, div):
        plan, _yf, log = div
        plan["finmind"] = _FM_ROWS
        f: dict = {}
        avg, yearly, src = A.fetch_dividend_data("2330", failed=f)
        assert src == "FinMind", "修前：SDK 未安裝 → REST 從未執行，只剩 yfinance/TWSE"
        assert avg == pytest.approx(4.5) and len(yearly) == 2 and f == {}
        fm = [x for x in log if x[0] == "finmind"]
        assert len(fm) == 1
        assert fm[0][1]["dataset"] == "TaiwanStockDividend" and fm[0][1]["data_id"] == "2330"
        assert fm[0][2].get("Authorization") == "Bearer tok"
        assert not [x for x in log if x[0] == "twse"], "鏈順序不變：FinMind 有資料就不打 TWSE"

    def test_r1_rest_200_empty_is_not_a_failure(self, div):
        plan, _yf, _log = div
        plan["finmind"] = {"status": 200, "data": []}
        f: dict = {}
        A.fetch_dividend_data("2330", failed=f)
        assert A.DIVIDEND_LEG_FINMIND not in f

    def test_r1_rest_quota_without_sdk_is_failure(self, div):
        plan, _yf, _log = div
        plan["finmind"] = {"status": 402, "msg": "upper limit"}
        f: dict = {}
        A.fetch_dividend_data("2330", failed=f)
        assert "402" in f[A.DIVIDEND_LEG_FINMIND]

    def test_r3_all_failed_not_cached_and_backs_off(self, div, monkeypatch):
        plan, yf, log = div
        f: dict = {}
        assert A.fetch_dividend_data("2330", failed=f)[2] == ""
        assert set(f) == set(A.DIVIDEND_LEGS)
        n = len(log)
        f2: dict = {}
        A.fetch_dividend_data("2330", failed=f2)
        assert len(log) == n, "冷卻期內不重跑整條鏈"
        assert set(f2) == set(A.DIVIDEND_LEGS), "冷卻期內旗標照帶"
        plan["finmind"] = _FM_ROWS
        monkeypatch.setattr(A._dividend_fail_cooldown, "seconds", 0)
        f3: dict = {}
        assert A.fetch_dividend_data("2330", failed=f3)[2] == "FinMind", \
            "上游恢復後必須拿到成功（修前：失敗被快取 30 分）"
        n2 = len(log)
        A.fetch_dividend_data("2330")
        assert len(log) == n2, "成功照舊快取"

    def test_r3_genuine_none_still_cached(self, div):
        plan, yf, log = div
        plan["finmind"] = {"status": 200, "data": []}
        plan["twse"] = {"stat": "很抱歉，沒有符合條件的資料!"}
        yf["s"] = Q._yf_divs("empty")
        f: dict = {}
        assert A.fetch_dividend_data("2330", failed=f) == (0.0, [], "") and f == {}
        n = len(log)
        A.fetch_dividend_data("2330")
        assert len(log) == n, "分不出是否失敗的「真的沒有」照舊快取（不猜）"


# ── Q5-r2-r3：籌碼（get_combined_data ＋ fetch_price_data pkl）────────────
class TestChips:
    def test_inst_all_failed_not_cached_then_recovers(self, chips_env, monkeypatch):
        loader = chips_env(**Q._ALL_INST_DOWN)
        df, err, _ = loader.get_combined_data("2330", 180, True)
        assert DL.INST_FETCH_FAILED_ATTR in df.attrs
        calls = {"n": 0}
        _orig = DL.StockDataLoader._get_combined_data_body

        def _count(self, *a, **k):
            calls["n"] += 1
            return _orig(self, *a, **k)
        monkeypatch.setattr(DL.StockDataLoader, "_get_combined_data_body", _count)
        df2, _, _ = loader.get_combined_data("2330", 180, True)
        assert calls["n"] == 0 and DL.INST_FETCH_FAILED_ATTR in df2.attrs, "冷卻期內不重抓、旗標照帶"
        monkeypatch.setattr(DL.StockDataLoader, "_get_combined_data_body", _orig)
        # 上游恢復（TPEx 有回答）＋ 冷卻期過 → 不再是失敗
        monkeypatch.setattr(DL._combined_inst_fail_cooldown, "seconds", 0)
        loader = chips_env(**Q._PARTIAL_INST)
        df3, _, _ = loader.get_combined_data("2330", 180, True)
        assert DL.INST_FETCH_FAILED_ATTR not in df3.attrs

    def test_fetch_price_data_does_not_persist_flagged(self, chips_env, monkeypatch):
        chips_env(**Q._ALL_INST_DOWN)
        saved: list = []
        monkeypatch.setattr(A, "_save_cache", lambda *a, **k: saved.append(a))
        df, name, err = A.fetch_price_data("2330", 120)
        assert err is None and DL.INST_FETCH_FAILED_ATTR in df.attrs
        assert saved == [], "法人全段失敗的結果不得寫 pkl（修前寫 0.5 小時）"

    def test_fetch_price_data_ignores_flagged_pkl(self, chips_env, monkeypatch):
        chips_env(**Q._PARTIAL_INST)
        bad = pd.DataFrame({"date": [pd.Timestamp.today().date()], "close": [100.0]})
        bad.attrs[DL.INST_FETCH_FAILED_ATTR] = "old failure"
        monkeypatch.setattr(A, "_load_cache", lambda *a, **k: (bad, "舊"))
        df, name, err = A.fetch_price_data("2330", 120)
        assert DL.INST_FETCH_FAILED_ATTR not in df.attrs and len(df) > 1

    def test_success_still_saved(self, chips_env, monkeypatch):
        chips_env(**Q._PARTIAL_INST)
        saved: list = []
        monkeypatch.setattr(A, "_save_cache", lambda *a, **k: saved.append(a))
        A.fetch_price_data("2330", 120)
        assert len(saved) == 1


def test_cached_failure_carries_payload():
    e = CachedFailure((1, 2))
    assert e.payload == (1, 2)


class TestCooldownBounds:
    def test_expired_entries_pruned(self):
        c = FailCooldown(seconds=100)
        for i in range(5):
            _, g = c.begin(i)
            c.fail(i, g, pd.DataFrame({"x": [i]}))
        assert len(c) == 5
        c.seconds = 0
        c.begin("other")
        assert len(c) == 0, "過期紀錄（含整張 df）必須被清掉，不得只靠成功/clear"

    def test_capped_evicts_oldest(self):
        c = FailCooldown(seconds=1e6, max_entries=3)
        for i in range(10):
            _, g = c.begin(i)
            c.fail(i, g, i)
        assert len(c) == 3
        assert all(k in c for k in (7, 8, 9)) and 0 not in c

    def test_default_cap_matches_old_cache(self):
        from shared.fail_cooldown import FAIL_COOLDOWN_MAX_ENTRIES
        assert FAIL_COOLDOWN_MAX_ENTRIES == 64
        assert DL._combined_inst_fail_cooldown.max_entries == 64


class TestYfProxyRaceAndSuccess:
    def test_success_during_failure_is_not_overwritten(self, yp_yf, monkeypatch):
        """我在抓（會失敗）的期間，別人成功了 → 我的失敗不得寫入冷卻表。"""
        def _raise_after_peer_success(t):
            YP._dividends_fail_cooldown.success(t)   # 另一個 session 此刻成功
            raise ConnectionError("yahoo 429")
        monkeypatch.setattr(YP, "_cached_dividends_cached", _raise_after_peer_success)
        s = YP.cached_dividends("7777.TW")
        assert YP.DIVIDENDS_FETCH_FAILED_ATTR in s.attrs
        assert "7777.TW" not in YP._dividends_fail_cooldown

    def test_wrapper_success_invalidates_inflight_failure(self, yp_yf):
        """別的 session 已開抓（記下世代）→ 本次 `cached_dividends` 成功 → 那次較晚寫入的
        失敗不得進冷卻表（`cached_dividends` 成功時必須呼叫 `success()` 推進世代）。"""
        _, g = YP._dividends_fail_cooldown.begin("8888.TW")   # 同儕開抓
        yp_yf.mode = "up"
        assert len(YP.cached_dividends("8888.TW")) == 1        # 本次成功
        YP._dividends_fail_cooldown.fail("8888.TW", g, pd.Series(dtype=float))  # 同儕晚到的失敗
        assert "8888.TW" not in YP._dividends_fail_cooldown
        assert len(YP.cached_dividends("8888.TW")) == 1
