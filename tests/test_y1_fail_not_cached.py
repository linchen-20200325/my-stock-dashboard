# -*- coding: utf-8 -*-
"""批 Y1（2026-10-03；CLAUDE.md §1.A-3(a)「只快取成功結果」＋(b)「失敗時退避」）。

  · **X1-n10** `yf_proxy._history_or_raise`：yfinance **沒拋例外、回空表（或 None）** 時同樣看本次 K 線請求的
    HTTP 回應 —— 5xx／401／403、或 200 但 body 為 `null` → 失敗（不入快取、冷卻）。已安裝的 yfinance 1.7.0
    遇到「HTTP 5xx／401／403 ＋ 帶時間戳、價格全空的 K 線」**不拋例外、回空表**（本檔 `test_premise_*` 實跑）。
  · **X1-n1** `etf_fetch._fetch_etf_price_max_cached`：改經 `yf_proxy._history_or_raise`（同 K 線那支的判準）——
    修前直呼 `yf.Ticker.history`，HTTP 錯誤被當「沒資料」快取 TTL_1HOUR。
  · **X1-n2** `macro_core.fetch_fred`：observations 非空但每一筆都是 '.' → 比照「observations 為空」出口
    （記退避、不入 30 分鐘成功快取、回 `pd.DataFrame()`）。

不觸網：一律換掉最底層 HTTP（`YfData.get`／`fetch_url`）。冷卻期用假時鐘（只換 `shared.fail_cooldown.time`）。
標「main 紅」者在 origin/main（`88d562a`）上會紅。
"""
from __future__ import annotations

import time
import types

import pandas as pd
import pytest
import yfinance
from yfinance import exceptions as YFE

import shared.fail_cooldown as FC
import src.data.etf.etf_fetch as EF
import src.data.macro.macro_core as MC
import src.data.proxy.yf_proxy as YP
from shared.fail_cooldown import FAIL_COOLDOWN_SEC
from tests.test_x1_l3g1_fetch_guards import (
    _CHART_404, _CHART_5XX, _FINANCE_401, _Resp, _chart_ok,
)

pytestmark = pytest.mark.filterwarnings("ignore:'raise_errors' deprecated:DeprecationWarning")


@pytest.fixture
def fc_clock(monkeypatch):
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


def _assert_bare_empty(df) -> None:
    ref = pd.DataFrame()
    assert isinstance(df, pd.DataFrame) and repr(df) == repr(ref) and df.attrs == {}


def _chart_all_nan(sym: str) -> dict:
    """有時間戳、價格全空的 K 線（yfinance 1.7.0 對這種 body 不拋例外、回空表）。"""
    body = _chart_ok(sym, "1y")
    res = body["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    for k in q:
        q[k] = [None] * len(q[k])
    res["indicators"]["adjclose"][0]["adjclose"] = [None] * len(q["close"])
    return body


def _sym_of(url: str) -> str:
    return url.rsplit("/", 1)[-1]


_REPLIES = {
    "ok": lambda u: _Resp(200, _chart_ok(_sym_of(u), "1y")),
    "404": lambda u: _Resp(404, _CHART_404),
    "503_chart": lambda u: _Resp(503, _CHART_5XX),
    "401_finance": lambda u: _Resp(401, _FINANCE_401),
    "200_null": lambda u: _Resp(200, text="null"),
    "200_nan": lambda u: _Resp(200, _chart_all_nan(_sym_of(u))),
    "503_nan": lambda u: _Resp(503, _chart_all_nan(_sym_of(u))),
    "500_nan": lambda u: _Resp(500, _chart_all_nan(_sym_of(u))),
    "401_nan": lambda u: _Resp(401, _chart_all_nan(_sym_of(u))),
    "403_nan": lambda u: _Resp(403, _chart_all_nan(_sym_of(u))),
}
#: 「沒拋例外、回空表」的失敗回應（X1-n10 的破口）
_NAN_FAIL_MODES = ("503_nan", "500_nan", "401_nan", "403_nan")


@pytest.fixture
def real_yf(monkeypatch, fc_clock):
    """已安裝的真 yfinance，只換 `YfData.get` 與時區查詢。"""
    from yfinance import base as yfb
    from yfinance import data as yfd
    state = {"mode": "ok", "urls": []}

    def _get(self, url, *a, **k):
        state["urls"].append(url)
        return _REPLIES[state["mode"]](url)

    monkeypatch.setattr(yfd.YfData, "get", _get)
    monkeypatch.setattr(yfb.TickerBase, "_get_ticker_tz", lambda self, *a, **k: "Asia/Taipei")
    monkeypatch.setattr(EF, "_proxy_env", _null_ctx)
    YP.cached_history.clear()
    EF._fetch_etf_price_max.clear()
    yield state
    YP.cached_history.clear()
    EF._fetch_etf_price_max.clear()


class _null_ctx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ══════════════════════════════════════════════════════════════════
# X1-n10 yf_proxy：沒拋例外、回空表
# ══════════════════════════════════════════════════════════════════
class TestX1n10EmptyReturnChecksReply:
    @pytest.mark.parametrize("mode", _NAN_FAIL_MODES + ("200_nan",))
    def test_premise_yfinance_returns_empty_without_raising(self, real_yf, mode):
        """前提（本批實跑）：這幾種回應下 yfinance `history(raise_errors=True)` 不拋例外、回空表。"""
        real_yf["mode"] = mode
        df = yfinance.Ticker("PRE.TW").history(period="1y", raise_errors=True)
        assert isinstance(df, pd.DataFrame) and df.empty

    @pytest.mark.parametrize("mode", _NAN_FAIL_MODES)
    def test_http_error_empty_backs_off_then_recovers(self, real_yf, fc_clock, mode):
        """main：判「沒資料」、快取 1 小時（failed=False）→ 紅。"""
        sym = f"N10{mode.upper()}.TW"
        real_yf["mode"] = mode
        df, failed = YP.cached_history.with_status(sym, "60d")
        _assert_bare_empty(df)
        assert failed is True and (sym, "60d") in YP._history_fail_cooldown
        n = len(real_yf["urls"])
        real_yf["mode"] = "ok"
        df, failed = YP.cached_history.with_status(sym, "60d")
        assert failed is True and len(real_yf["urls"]) == n, "冷卻期內不打上游"
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        df, failed = YP.cached_history.with_status(sym, "60d")
        assert failed is False and len(df) == 40

    def test_200_all_nan_still_no_data_cached(self, real_yf, fc_clock):
        """200（body 非 null）回空表 → 照舊「沒資料」、照舊快取（同修前）。"""
        real_yf["mode"] = "200_nan"
        df, failed = YP.cached_history.with_status("N10OK.TW", "1y")
        _assert_bare_empty(df)
        assert failed is False and ("N10OK.TW", "1y") not in YP._history_fail_cooldown
        n = len(real_yf["urls"])
        real_yf["mode"] = "ok"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        _assert_bare_empty(YP.cached_history("N10OK.TW", "1y"))
        assert len(real_yf["urls"]) == n, "照舊快取"

    def test_direct_raises_runtime_error_with_log(self, real_yf, capsys):
        real_yf["mode"] = "503_nan"
        with pytest.raises(RuntimeError, match="HTTP 503"):
            YP._history_or_raise(yfinance.Ticker("N10D.TW"), "N10D.TW", "1y")
        assert "[yf_proxy.history] N10D.TW: Yahoo 回應 HTTP 503、回空表 → 抓取失敗" in capsys.readouterr().out

    @pytest.mark.parametrize("period", ["1y", "60d"])
    def test_success_identical(self, real_yf, period):
        a = yfinance.Ticker("N10S.TW").history(period=period)
        b = YP._history_or_raise(yfinance.Ticker("N10S.TW"), "N10S.TW", period)
        pd.testing.assert_frame_equal(a, b)
        assert repr(a) == repr(b) and a.attrs == b.attrs


def _recorded(status: int, null: bool = False):
    """假 `tk.history` 內模擬 recorder：記下本次 K 線回應。"""
    YP._CHART_REPLY.reply = (status, null)


class TestX1n10Branches:
    """沒有真 yfinance 的分支：None 回傳、兩條修前呼叫退路、非空表、看不到回應。"""

    def test_none_return_with_failure_reply_raises(self):
        class _T:
            def history(self, period="1mo", raise_errors=False):
                _recorded(503)
                return None
        with pytest.raises(RuntimeError):
            YP._history_or_raise(_T(), "X", "1y")

    def test_none_return_without_failure_reply_passthrough(self):
        class _T:
            def history(self, period="1mo", raise_errors=False):
                _recorded(200)
                return None
        assert YP._history_or_raise(_T(), "X", "1y") is None

    def test_empty_with_200_null_raises(self):
        class _T:
            def history(self, period="1mo", raise_errors=False):
                _recorded(200, True)
                return pd.DataFrame()
        with pytest.raises(RuntimeError, match="null"):
            YP._history_or_raise(_T(), "X", "1y")

    def test_empty_without_reply_passthrough_same_object(self):
        """看不到回應（例：yfinance 走自己的快取）→ 同修前：原樣回傳。"""
        ret = pd.DataFrame(columns=["Close"])

        class _T:
            def history(self, period="1mo", raise_errors=False):
                return ret
        assert YP._history_or_raise(_T(), "X", "1y") is ret

    def test_nonempty_with_failure_reply_passthrough_same_object(self):
        """非空表一律原樣回傳（成功路徑不看回應）。"""
        ret = pd.DataFrame({"Close": [1.0]})

        class _T:
            def history(self, period="1mo", raise_errors=False):
                _recorded(503)
                return ret
        assert YP._history_or_raise(_T(), "X", "1y") is ret

    def test_object_without_empty_attr_passthrough(self):
        """回的不是表（沒有 `.empty`）→ 不判空、原樣回傳（同修前；不因回應而改拋例外）。"""
        ret = object()

        class _T:
            def history(self, period="1mo", raise_errors=False):
                _recorded(503)
                return ret
        assert YP._history_or_raise(_T(), "X", "1y") is ret

    def test_typeerror_fallback_empty_failure_raises(self):
        seen = []

        class _T:
            def history(self, period="1mo"):
                seen.append(period)
                _recorded(401)
                return pd.DataFrame()
        with pytest.raises(RuntimeError, match="HTTP 401"):
            YP._history_or_raise(_T(), "X", "1y")
        assert seen == ["1y"]

    def test_deprecation_fallback_empty_failure_raises(self):
        calls = []

        class _T:
            def history(self, period="1mo", **kw):
                calls.append(kw)
                if kw.get("raise_errors"):
                    raise DeprecationWarning("'raise_errors' deprecated")
                _recorded(500)
                return pd.DataFrame()
        with pytest.raises(RuntimeError, match="HTTP 500"):
            YP._history_or_raise(_T(), "X", "1y")
        assert calls == [{"raise_errors": True}, {}]

    def test_typeerror_fallback_success_passthrough(self):
        ret = pd.DataFrame({"Close": [2.0]})

        class _T:
            def history(self, period="1mo"):
                return ret
        assert YP._history_or_raise(_T(), "X", "1y") is ret

    def test_no_kwargs_call_unchanged(self):
        """不給 `history_kwargs` → 呼叫與修前逐字相同（只有 period、raise_errors）。"""
        seen = []

        class _T:
            def history(self, *a, **kw):
                seen.append((a, kw))
                return pd.DataFrame({"Close": [1.0]})
        YP._history_or_raise(_T(), "X", "1y")
        assert seen == [((), {"period": "1y", "raise_errors": True})]

    @pytest.mark.parametrize("path", ["strict", "typeerror", "deprecation"])
    def test_kwargs_forwarded_on_every_path(self, path):
        seen = []

        class _T:
            def history(self, *a, **kw):
                seen.append(kw)
                if kw.get("raise_errors") and path == "typeerror":
                    raise TypeError("history() got an unexpected keyword argument 'raise_errors'")
                if kw.get("raise_errors") and path == "deprecation":
                    raise DeprecationWarning("'raise_errors' deprecated")
                return pd.DataFrame({"Close": [1.0]})
        YP._history_or_raise(_T(), "X", "max", auto_adjust=True)
        assert seen[-1]["auto_adjust"] is True and seen[-1]["period"] == "max"


# ══════════════════════════════════════════════════════════════════
# X1-n1 etf_fetch 取價改經 _history_or_raise
# ══════════════════════════════════════════════════════════════════
class TestX1n1EtfPrice:
    @pytest.mark.parametrize("mode", ("503_chart", "401_finance", "200_null") + _NAN_FAIL_MODES)
    def test_http_error_is_failure_backs_off_then_recovers(self, real_yf, fc_clock, mode):
        """main：判「沒資料」、空 df 無失敗旗標、快取 1 小時 → 紅。"""
        sym = f"E1{mode.upper()}.TW"
        real_yf["mode"] = mode
        out = EF._fetch_etf_price_max(sym)
        assert out.empty and EF.PRICE_FETCH_FAILED_ATTR in out.attrs, out.attrs
        assert sym in EF._price_fail_cooldown
        n = len(real_yf["urls"])
        real_yf["mode"] = "ok"
        again = EF._fetch_etf_price_max(sym)
        assert EF.PRICE_FETCH_FAILED_ATTR in again.attrs and len(real_yf["urls"]) == n, "冷卻期內不打上游"
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        healed = EF._fetch_etf_price_max(sym)
        assert len(healed) == 40 and EF.PRICE_FETCH_FAILED_ATTR not in healed.attrs

    @pytest.mark.parametrize("mode", ["404", "200_nan"])
    def test_real_no_data_still_cached_without_flag(self, real_yf, fc_clock, mode):
        """Yahoo 的「查無此代碼」與 200 回空表 → 照舊「沒資料」、照舊快取（同修前）。"""
        sym = f"E1ND{mode}.TW"
        real_yf["mode"] = mode
        out = EF._fetch_etf_price_max(sym)
        _assert_bare_empty(out)
        assert sym not in EF._price_fail_cooldown
        n = len(real_yf["urls"])
        real_yf["mode"] = "ok"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        _assert_bare_empty(EF._fetch_etf_price_max(sym))
        assert len(real_yf["urls"]) == n, "照舊快取"

    def test_success_identical_to_direct_history(self, real_yf):
        """成功路徑：內容＝修前那種直接呼叫（`history(period='max', auto_adjust=True)`）再整理。"""
        raw = yfinance.Ticker("E1OK.TW").history(period="max", auto_adjust=True)
        out = EF._fetch_etf_price_max_cached("E1OK.TW")
        exp = raw.copy()
        exp.index = pd.to_datetime(exp.index).tz_localize(None)
        exp = exp.ffill()
        pd.testing.assert_frame_equal(out, exp)
        assert out.attrs["source"] == "Yahoo:E1OK.TW:history_max_adj"
        assert out.attrs["price_basis"] == EF.PRICE_BASIS_ADJUSTED

    def test_requests_max_adjusted(self, real_yf):
        """K 線請求的確是 period=max（走 _history_or_raise 不改請求內容）。"""
        EF._fetch_etf_price_max_cached("E1RQ.TW")
        assert real_yf["urls"] and all("/v8/finance/chart/E1RQ.TW" in u for u in real_yf["urls"])


# ══════════════════════════════════════════════════════════════════
# X1-n2 fetch_fred：observations 全為 '.'
# ══════════════════════════════════════════════════════════════════
class _JResp:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


@pytest.fixture
def fred(monkeypatch):
    st = {"body": None, "n": 0}

    def _fu(url, **kw):
        st["n"] += 1
        return _JResp(st["body"])
    monkeypatch.setattr(MC, "fetch_url", _fu)
    return st


_ALL_DOT = {"observations": [{"date": "2026-09-01", "value": "."}, {"date": "2026-09-02", "value": "."}]}
_GOOD = {"observations": [{"date": "2026-09-01", "value": "4.1"}, {"date": "2026-09-02", "value": "."},
                          {"date": "2026-09-03", "value": "4.3"}]}


class TestX1n2FredAllDot:
    @pytest.mark.parametrize("body", [
        _ALL_DOT,
        {"observations": [{"date": "2026-09-01", "value": "."}]},
        {"observations": [{"date": "2026-09-01", "value": "n/a"}, {"date": "2026-09-02", "value": "."}]},
    ], ids=["two_dots", "one_dot", "unparsable_and_dot"])
    def test_all_missing_backs_off_not_cached(self, fred, body, capsys):
        """main：空表入 30 分鐘成功快取、不記退避 → 紅。"""
        key = ("Y1N2", "k", 10)
        fred["body"] = body
        out = MC.fetch_fred("Y1N2", "k", n=10)
        _assert_bare_empty(out)
        assert key not in MC._FRED_CACHE and key in MC._FRED_FAIL_CACHE
        assert f"[macro_core/fred] Y1N2 observations {len(body['observations'])} 筆皆無有效值(記退避)" \
            in capsys.readouterr().out
        fred["body"] = _GOOD
        _assert_bare_empty(MC.fetch_fred("Y1N2", "k", n=10))
        assert fred["n"] == 1, "冷卻期內不重打上游"
        MC._FRED_FAIL_CACHE[key] -= MC._FAIL_COOLDOWN_SEC
        healed = MC.fetch_fred("Y1N2", "k", n=10)
        assert fred["n"] == 2 and healed["value"].tolist() == [4.1, 4.3]
        assert key not in MC._FRED_FAIL_CACHE and key in MC._FRED_CACHE

    def test_failure_record_keeps_newer(self, fred, monkeypatch):
        """同 D2-f14：並行時別人記下較新的失敗 → 本次較舊的 now 不得蓋掉它。"""
        key = ("Y1NL", "k", 10)
        orig = MC.fetch_url

        def _fu(url, **kw):
            with MC._FRED_CACHE_LOCK:
                MC._FRED_FAIL_CACHE[key] = time.time() + 50
            return orig(url, **kw)
        monkeypatch.setattr(MC, "fetch_url", _fu)
        fred["body"] = _ALL_DOT
        t0 = time.time()
        MC.fetch_fred("Y1NL", "k", n=10)
        assert MC._FRED_FAIL_CACHE[key] >= t0 + 49

    def test_failure_record_uses_call_start(self, fred, monkeypatch):
        """記的時點 ＝ 本次呼叫開始的 now（同其他出口）。"""
        key = ("Y1NT", "k", 10)
        monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
        fred["body"] = _ALL_DOT
        MC.fetch_fred("Y1NT", "k", n=10)
        assert MC._FRED_FAIL_CACHE[key] == 1_000_000.0

    def test_success_with_some_dots_unchanged(self, fred):
        fred["body"] = _GOOD
        out = MC.fetch_fred("Y1NG", "k", n=10)
        assert list(out.columns) == ["date", "value", "source", "fetched_at"]
        assert out["value"].tolist() == [4.1, 4.3] and out["value"].dtype == "float64"
        assert ("Y1NG", "k", 10) not in MC._FRED_FAIL_CACHE
        MC.fetch_fred("Y1NG", "k", n=10)
        assert fred["n"] == 1, "成功照舊入 30 分鐘快取"


def test_no_data_exception_still_returns_none():
    """`_history_or_raise` 既有的「沒資料」例外路徑不受本批影響。"""
    class _T:
        def history(self, period="1mo", raise_errors=False):
            _recorded(404)
            e = YFE.YFPricesMissingError.__new__(YFE.YFPricesMissingError)
            Exception.__init__(e, "X: no price data found")
            raise e
    assert YP._history_or_raise(_T(), "X", "1y") is None
