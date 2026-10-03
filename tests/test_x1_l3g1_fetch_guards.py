# -*- coding: utf-8 -*-
"""批 X1（2026-10-03，客戶放行 L3-G1 七列；CLAUDE.md §1.A-3「只快取成功結果；失敗時退避，不連續轟炸來源」）。

  · **D2-f32** `requirements.txt` yfinance 下限 0.2.36 → 0.2.52（0.2.39／0.2.45 在 Python 3.11 import 失敗；
    0.2.40～0.2.51 拒收 `60d`／`9mo`）。
  · **D2-f37／D2-f46** `yf_proxy._is_yf_no_data`：裸 `Exception` 只在沒有型別例外的 yfinance（0.2.36～0.2.38）
    才算「沒資料」；docstring 補齊 `safe_merge_dfs` 5 處。
  · **D2-f36** `yf_proxy._history_or_raise`：「沒資料」型別的例外另看該次 K 線請求的 HTTP 回應 ——
    5xx／401／403、或 200 但 body 為 `null` → 失敗（不入快取、冷卻）。
  · **D2-f49** `macro_core.fetch_fred`：HTTP 200 之後整理回應拋例外 → 記退避（該次照舊拋出）；
    `macro_core.fetch_yf_ohlcv`：HTTP 200 但收盤全缺 → 記退避、不算成功（該次回傳不變）。
  · **D2-f41** `proxy_helper._url_cache_put` 持鎖；`fetch_url` 讀快取改單次 `.get()`。
  · **D2-f29** 單股月營收 fallback：OpenAPI 全市場快照的失敗冷卻在檔與檔之間共用。

不觸網：一律換掉最底層 HTTP（`YfData.get`／`fetch_url`）。冷卻期用假時鐘（只換 `shared.fail_cooldown.time`）。
每一項至少一條測試在 origin/main（`501b45c`）上會紅（各測試 docstring 註明）。
"""
from __future__ import annotations

import json
import pathlib
import threading
import time
import types

import pandas as pd
import pytest
import requests
import yfinance
from yfinance import exceptions as YFE

import shared.fail_cooldown as FC
import src.data.macro.macro_core as MC
import src.data.proxy.proxy_helper as PH
import src.data.proxy.yf_proxy as YP
import src.data.stock.monthly_revenue_fetcher as MR
from shared.fail_cooldown import FAIL_COOLDOWN_SEC

_REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def fc_clock(monkeypatch):
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


def _assert_bare_empty(df) -> None:
    ref = pd.DataFrame()
    assert isinstance(df, pd.DataFrame) and repr(df) == repr(ref) and df.attrs == {}


# ══════════════════════════════════════════════════════════════════
# D2-f32 yfinance 下限
# ══════════════════════════════════════════════════════════════════
class TestD2f32YfinanceFloor:
    @staticmethod
    def _spec():
        from packaging.specifiers import SpecifierSet
        lines = [ln.split("#", 1)[0].strip() for ln in
                 (_REPO / "requirements.txt").read_text(encoding="utf-8").splitlines()]
        (spec,) = [ln[len("yfinance"):] for ln in lines if ln.startswith("yfinance")]
        return SpecifierSet(spec)

    def test_broken_versions_excluded(self):
        """main：`>=0.2.36` 允許 0.2.39～0.2.51 → 紅。"""
        spec = self._spec()
        for i in range(36, 52):
            assert f"0.2.{i}" not in spec, f"0.2.{i} 不得在宣告範圍內"

    def test_working_versions_still_allowed(self):
        spec = self._spec()
        for v in ("0.2.52", "0.2.66", "1.0", "1.7.0"):
            assert v in spec
        assert "2.0" not in spec, "上限不變"

    def test_installed_version_inside_range(self):
        assert yfinance.__version__ in self._spec()


# ══════════════════════════════════════════════════════════════════
# D2-f37 裸 Exception 規則只套沒有型別的舊版
# ══════════════════════════════════════════════════════════════════
_SAFE_MERGE_MSGS = ("No data to merge", "Expected 1 data col",
                    "New index contains duplicates but unsure how to aggregate for 'Dividends'",
                    "Data was lost in merge, investigate")


class TestD2f37BareException:
    @pytest.mark.parametrize("msg", _SAFE_MERGE_MSGS)
    def test_typed_world_bare_exception_is_failure(self, msg):
        """已安裝的 yfinance 有型別例外 → 裸 `Exception`（資料整理失敗）不是「沒資料」。main：True → 紅。"""
        assert YP._yf_no_data_exc_types(), "前提：已安裝的 yfinance 有型別例外"
        assert YP._is_yf_no_data(Exception(msg)) is False

    def test_legacy_world_bare_exception_is_no_data(self, monkeypatch):
        """0.2.36～0.2.38（沒有型別例外）：裸 `Exception` 照舊是「沒資料」。"""
        monkeypatch.setattr(YP, "_yf_no_data_exc_types", lambda: ())
        assert YP._is_yf_no_data(Exception("X.TW: No data found, symbol may be delisted")) is True

    def test_typed_no_data_unchanged(self):
        e = YFE.YFPricesMissingError.__new__(YFE.YFPricesMissingError)
        Exception.__init__(e, "X: no price data found")
        assert YP._is_yf_no_data(e) is True
        assert YP._is_yf_no_data(Exception.__new__(RuntimeError)) is False

    def test_bare_exception_through_cache_backs_off(self, monkeypatch, fc_clock):
        """經 `cached_history`：裸 Exception → 失敗（不入快取、冷卻），期滿即恢復。main：被快取 1 小時 → 紅。"""
        state = {"mode": "bare", "n": 0}
        ok = pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.DatetimeIndex(["2026-09-01", "2026-09-02"]))

        class _T:
            def __init__(self, t):
                pass

            def history(self, period="1mo", raise_errors=False):
                state["n"] += 1
                if state["mode"] == "bare":
                    raise Exception("Data was lost in merge, investigate")
                return ok.copy()

        monkeypatch.setattr(yfinance, "Ticker", _T)
        YP.cached_history.clear()
        try:
            df, failed = YP.cached_history.with_status("X37A.TW", "1y")
            _assert_bare_empty(df)
            assert failed is True and ("X37A.TW", "1y") in YP._history_fail_cooldown
            state["mode"] = "ok"
            df, failed = YP.cached_history.with_status("X37A.TW", "1y")
            assert failed is True and state["n"] == 1, "冷卻期內不重打"
            fc_clock["now"] += FAIL_COOLDOWN_SEC
            df, failed = YP.cached_history.with_status("X37A.TW", "1y")
            assert failed is False and state["n"] == 2
            pd.testing.assert_frame_equal(df, ok)
        finally:
            YP.cached_history.clear()

    def test_docstring_counts_safe_merge(self):
        """D2-f46：docstring 交代 `safe_merge_dfs` 5 處（main 只寫 auto_adjust 一處 → 紅）。"""
        doc = YP._is_yf_no_data.__doc__
        assert "safe_merge_dfs" in doc and "5 處" in doc


# ══════════════════════════════════════════════════════════════════
# D2-f36 帶 JSON body 的 HTTP 錯誤 —— 已安裝的真 yfinance，只換 `YfData.get` 與時區查詢
# ══════════════════════════════════════════════════════════════════
class _Resp:
    def __init__(self, status: int, body=None, text=None):
        self.status_code = status
        self.text = text if text is not None else json.dumps(body)
        self.content = self.text.encode("utf-8")
        self.url = "https://query2.finance.yahoo.com/v8/finance/chart/X"
        self.headers: dict = {}

    def json(self):
        return json.loads(self.text)


def _chart_ok(sym: str, period: str, n: int = 40) -> dict:
    base = 1_780_000_000 - (1_780_000_000 % 86400) + 3600
    ts = [base + i * 86400 for i in range(n)]
    closes = [100.0 + i for i in range(n)]
    per = {"timezone": "CST", "start": ts[-1], "end": ts[-1] + 16200, "gmtoffset": 28800}
    meta = {"currency": "TWD", "symbol": sym, "exchangeName": "TAI", "fullExchangeName": "Taiwan",
            "instrumentType": "EQUITY", "firstTradeDate": 946861200, "regularMarketTime": ts[-1] + 16200,
            "hasPrePostMarketData": False, "gmtoffset": 28800, "timezone": "CST",
            "exchangeTimezoneName": "Asia/Taipei", "regularMarketPrice": closes[-1],
            "fiftyTwoWeekHigh": max(closes), "fiftyTwoWeekLow": min(closes),
            "regularMarketDayHigh": closes[-1] + 1, "regularMarketDayLow": closes[-1] - 1,
            "regularMarketVolume": 1000, "chartPreviousClose": closes[0], "priceHint": 2,
            "currentTradingPeriod": {"pre": per, "regular": per, "post": per},
            "dataGranularity": "1d", "range": period,
            "validRanges": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]}
    quote = {"open": closes, "high": [c + 1 for c in closes], "low": [c - 1 for c in closes],
             "close": closes, "volume": [1000 + i for i in range(n)]}
    return {"chart": {"result": [{"meta": meta, "timestamp": ts,
                                  "indicators": {"quote": [quote], "adjclose": [{"adjclose": closes}]}}],
                      "error": None}}


_CHART_404 = {"chart": {"result": None, "error": {"code": "Not Found",
                                                  "description": "No data found, symbol may be delisted"}}}
_CHART_5XX = {"chart": {"result": None, "error": {"code": "Internal Server Error",
                                                  "description": "Internal Server Error"}}}
_FINANCE_401 = {"finance": {"result": None, "error": {"code": "Unauthorized",
                                                      "description": "Invalid Crumb"}}}

_REPLIES = {
    "ok": None,
    "404": lambda: _Resp(404, _CHART_404),
    "503_chart": lambda: _Resp(503, _CHART_5XX),
    "500_chart": lambda: _Resp(500, _CHART_5XX),
    "401_finance": lambda: _Resp(401, _FINANCE_401),
    "403_finance": lambda: _Resp(403, _FINANCE_401),
    "200_null": lambda: _Resp(200, text="null"),
    "200_null_ws": lambda: _Resp(200, text=" null\n"),
}
_FAIL_MODES = ("503_chart", "500_chart", "401_finance", "403_finance", "200_null", "200_null_ws")


@pytest.fixture
def real_yf(monkeypatch, fc_clock):
    from yfinance import base as yfb
    from yfinance import data as yfd
    assert hasattr(yfd, "YfData") and hasattr(yfd.YfData, "get")
    state = {"mode": "ok", "urls": []}

    def _get(self, url, *a, **k):
        state["urls"].append(url)
        p = k.get("params") or {}
        mk = _REPLIES[state["mode"]]
        if mk is None:
            return _Resp(200, _chart_ok(url.rsplit("/", 1)[-1], p.get("range", "1y")))
        return mk()

    monkeypatch.setattr(yfd.YfData, "get", _get)
    monkeypatch.setattr(yfb.TickerBase, "_get_ticker_tz", lambda self, *a, **k: "Asia/Taipei")
    YP.cached_history.clear()
    yield state
    YP.cached_history.clear()


@pytest.mark.filterwarnings("ignore:'raise_errors' deprecated:DeprecationWarning")
class TestD2f36HttpErrorNotNoData:
    @pytest.mark.parametrize("mode", _FAIL_MODES)
    def test_premise_yfinance_reports_no_data(self, real_yf, mode):
        """前提：yfinance 把這些 HTTP 錯誤拋成「沒資料」型別（`YFPricesMissingError`）。"""
        real_yf["mode"] = mode
        with pytest.raises(YFE.YFPricesMissingError):
            yfinance.Ticker("PRE36.TW").history(period="1y", raise_errors=True)

    @pytest.mark.parametrize("mode", _FAIL_MODES)
    def test_http_error_backs_off_then_recovers(self, real_yf, fc_clock, mode):
        """main：判「沒資料」、快取 1 小時（failed=False）→ 紅。"""
        sym = f"F36{mode.upper()}.TW"
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

    def test_404_still_no_data_cached(self, real_yf, fc_clock):
        real_yf["mode"] = "404"
        df, failed = YP.cached_history.with_status("F36NF.TW", "1y")
        _assert_bare_empty(df)
        assert failed is False and ("F36NF.TW", "1y") not in YP._history_fail_cooldown
        n = len(real_yf["urls"])
        real_yf["mode"] = "ok"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        _assert_bare_empty(YP.cached_history("F36NF.TW", "1y"))
        assert len(real_yf["urls"]) == n, "照舊快取"

    @pytest.mark.parametrize("period", ["1y", "60d", "9mo"])
    def test_success_identical(self, real_yf, period):
        a = yfinance.Ticker("F36OK.TW").history(period=period)
        b = YP._history_or_raise(yfinance.Ticker("F36OK.TW"), "F36OK.TW", period)
        pd.testing.assert_frame_equal(a, b)
        assert repr(a) == repr(b) and a.attrs == b.attrs

    def test_recorder_installed_once(self, real_yf):
        from yfinance import data as yfd
        for _ in range(3):
            YP._history_or_raise(yfinance.Ticker("F36W.TW"), "F36W.TW", "1y")
        g = yfd.YfData.get
        assert getattr(g, YP._CHART_REPLY_RECORDER_FLAG, False)
        assert not getattr(g.__wrapped__, YP._CHART_REPLY_RECORDER_FLAG, False), "只包一層"

    def test_reply_reset_each_call(self, real_yf):
        """上一次（或別處）留下的失敗回應不得影響本次判斷。"""
        YP._CHART_REPLY.reply = (503, False)
        real_yf["mode"] = "404"
        assert YP._history_or_raise(yfinance.Ticker("F36R.TW"), "F36R.TW", "1y") is None

    def test_no_recorder_falls_back_to_main(self, monkeypatch):
        """找不到 `YfData.get`（內部結構不同）→ 不記錄，判斷同修前（沒資料）。"""
        from yfinance import data as yfd
        monkeypatch.setattr(yfd, "YfData", object)

        class _T:
            def history(self, period="1mo", raise_errors=False):
                e = YFE.YFPricesMissingError.__new__(YFE.YFPricesMissingError)
                Exception.__init__(e, "X: no price data found")
                raise e
        YP._CHART_REPLY.reply = (503, False)
        assert YP._history_or_raise(_T(), "X", "1y") is None

    def test_reply_is_per_thread(self, real_yf):
        real_yf["mode"] = "503_chart"
        t = threading.Thread(target=lambda: yfinance.Ticker("F36T.TW").history(period="1y"))
        t.start()
        t.join()
        assert getattr(YP._CHART_REPLY, "reply", None) is None, "別的執行緒的回應不寫到這裡"

    def test_reply_survives_other_thread_reset(self, monkeypatch):
        """強制交錯（Event，不靠時序運氣）：A 收到 503 後、判斷前，B 開始自己的呼叫（清空「本次回應」）。
        A 的 503 必須仍被看見 → 拋出（失敗）。`_CHART_REPLY` 若是全執行緒共用的物件，A 會被 B 清掉 →
        誤判「沒資料」回 None。"""
        from yfinance import data as yfd
        monkeypatch.setattr(yfd.YfData, "get", lambda self, url, *a, **k: _Resp(503, _CHART_5XX))
        YP._ensure_chart_reply_recorder()
        a_recorded, b_reset = threading.Event(), threading.Event()
        res: dict = {}

        def _no_data():
            e = YFE.YFPricesMissingError.__new__(YFE.YFPricesMissingError)
            Exception.__init__(e, "X: no price data found")
            return e

        class _TA:
            def history(self, period="1mo", raise_errors=False):
                yfd.YfData.get(object.__new__(yfd.YfData), "https://q/v8/finance/chart/A")
                a_recorded.set()
                assert b_reset.wait(5)
                raise _no_data()

        class _TB:
            def history(self, period="1mo", raise_errors=False):
                b_reset.set()                                 # B 的呼叫已越過「清空本次回應」那一步
                return pd.DataFrame({"Close": [1.0]})

        def _a():
            try:
                res["a"] = YP._history_or_raise(_TA(), "A", "1y")
            except Exception as e:  # noqa: BLE001
                res["a_exc"] = e

        def _b():
            assert a_recorded.wait(5)
            res["b"] = YP._history_or_raise(_TB(), "B", "1y")

        ta, tb = threading.Thread(target=_a), threading.Thread(target=_b)
        ta.start()
        tb.start()
        ta.join(10)
        tb.join(10)
        assert isinstance(res.get("a_exc"), YFE.YFPricesMissingError), res
        assert len(res["b"]) == 1

    @pytest.mark.parametrize("reply,want", [
        (None, ""), ((None, False), ""), ((200, False), ""), ((404, False), ""), ((400, False), ""),
        ((429, False), ""), ((499, False), ""), ((500, False), "HTTP 500"), ((503, False), "HTTP 503"),
        ((401, False), "HTTP 401"), ((403, False), "HTTP 403"), ((200, True), "HTTP 200（body 為 null）"),
        ((404, True), ""), (("503", False), ""),
    ])
    def test_reply_failure_table(self, reply, want):
        assert YP._chart_reply_failure(reply) == want

    @pytest.mark.parametrize("text,want", [("null", True), (" null \n", True), ("{}", False),
                                           ("nullx", False), ('"null"', False), ("", False)])
    def test_reply_of_null_body(self, text, want):
        assert YP._chart_reply_of(_Resp(200, text=text)) == (200, want)
        assert YP._chart_reply_of(_Resp(503, text=text)) == (503, False)

    def test_reply_of_long_whitespace_null(self):
        assert YP._chart_reply_of(_Resp(200, text=" " * 500 + "null")) == (200, True)

    def test_non_chart_url_not_recorded(self, real_yf):
        """只記 K 線（`/v8/finance/chart/`）的回應；其他端點（例：quoteSummary）不覆寫。"""
        from yfinance import data as yfd
        YP._ensure_chart_reply_recorder()
        real_yf["mode"] = "503_chart"
        YP._CHART_REPLY.reply = ("sentinel", False)
        yfd.YfData.get(object.__new__(yfd.YfData), "https://query2.finance.yahoo.com/v10/finance/quoteSummary/X")
        assert YP._CHART_REPLY.reply == ("sentinel", False)
        yfd.YfData.get(object.__new__(yfd.YfData), "https://query2.finance.yahoo.com/v8/finance/chart/X")
        assert YP._CHART_REPLY.reply == (503, False)

    def test_reply_of_text_only_response(self):
        r = types.SimpleNamespace(status_code=200, text="null")
        assert YP._chart_reply_of(r) == (200, True)


# ══════════════════════════════════════════════════════════════════
# D2-f49 fetch_fred／fetch_yf_ohlcv 在 HTTP 200 之後的失敗也記退避
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


_FRED_GOOD = {"observations": [{"date": "2026-09-01", "value": "4.1"}, {"date": "2026-09-02", "value": "."},
                               {"date": "2026-09-03", "value": "4.3"}]}


class TestD2f49Fred:
    @pytest.mark.parametrize("body,exc", [
        ({"observations": [{"date": "2026-09-01"}]}, KeyError),                       # 缺 value 欄
        ({"observations": [{"date": "not-a-date", "value": "1.0"}]}, Exception),       # 日期解析失敗
    ])
    def test_post_200_error_backs_off(self, fred, body, exc):
        """main：第二次呼叫照樣打上游、照樣拋 → 紅。"""
        fred["body"] = body
        with pytest.raises(exc):
            MC.fetch_fred("X49A", "k", n=10)
        assert fred["n"] == 1
        assert ("X49A", "k", 10) in MC._FRED_FAIL_CACHE
        fred["body"] = _FRED_GOOD
        out = MC.fetch_fred("X49A", "k", n=10)
        assert fred["n"] == 1, "冷卻期內不重打上游"
        assert isinstance(out, pd.DataFrame) and out.empty and list(out.columns) == []
        MC._FRED_FAIL_CACHE[("X49A", "k", 10)] -= MC._FAIL_COOLDOWN_SEC
        out = MC.fetch_fred("X49A", "k", n=10)
        assert fred["n"] == 2 and out["value"].tolist() == [4.1, 4.3]
        assert ("X49A", "k", 10) not in MC._FRED_FAIL_CACHE

    def test_late_failure_keeps_newer_record(self, fred, monkeypatch):
        """D2-f14 同一規則：並行時別人在本次呼叫期間記下較新的失敗 → 本次較舊的 now 不得蓋掉它。"""
        key = ("X49L", "k", 10)
        orig = MC.fetch_url

        def _fu(url, **kw):
            with MC._FRED_CACHE_LOCK:
                MC._FRED_FAIL_CACHE[key] = time.time() + 50
            return orig(url, **kw)
        monkeypatch.setattr(MC, "fetch_url", _fu)
        fred["body"] = {"observations": [{"date": "2026-09-01"}]}
        t0 = time.time()
        with pytest.raises(KeyError):
            MC.fetch_fred("X49L", "k", n=10)
        assert MC._FRED_FAIL_CACHE[key] >= t0 + 49

    def test_schema_error_backs_off(self, fred):
        pytest.importorskip("pandera")
        from shared.schemas import PANDERA_AVAILABLE
        if not PANDERA_AVAILABLE:
            pytest.skip("pandera 不可用")
        fred["body"] = {"observations": [{"date": "2026-09-01", "value": "1"},
                                         {"date": "2026-09-01", "value": "2"}]}   # date 重複
        with pytest.raises(Exception) as ei:
            MC.fetch_fred("X49S", "k", n=10)
        assert "Schema" in type(ei.value).__name__
        assert ("X49S", "k", 10) in MC._FRED_FAIL_CACHE

    def test_success_unchanged(self, fred):
        fred["body"] = _FRED_GOOD
        out = MC.fetch_fred("X49G", "k", n=10)
        assert list(out.columns) == ["date", "value", "source", "fetched_at"]
        assert out["value"].tolist() == [4.1, 4.3] and out["value"].dtype == "float64"
        assert out["date"].tolist() == [pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-03")]
        assert set(out["source"]) == {"FRED:X49G"}
        assert ("X49G", "k", 10) not in MC._FRED_FAIL_CACHE
        MC.fetch_fred("X49G", "k", n=10)
        assert fred["n"] == 1, "成功照舊入 30 分鐘快取"

    def test_existing_failure_exits_unchanged(self, fred):
        fred["body"] = {"observations": []}
        out = MC.fetch_fred("X49E", "k", n=10)
        assert out.empty and ("X49E", "k", 10) in MC._FRED_FAIL_CACHE


def _chart_ohlcv(closes):
    ts = [1_780_000_000 + i * 86400 for i in range(len(closes))]
    q = {"open": closes, "high": closes, "low": closes, "close": closes, "volume": [1000] * len(closes)}
    return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [q]}}], "error": None}}


class TestD2f49Ohlcv:
    def test_all_close_missing_backs_off(self, fred):
        """main：收盤全缺走成功路徑（清退避）、第二次照打上游 → 紅。"""
        fred["body"] = _chart_ohlcv([None, None, None])
        first = MC.fetch_yf_ohlcv("X49O", range_="9mo")
        assert isinstance(first, pd.DataFrame) and first.empty
        assert list(first.columns) == ["Open", "High", "Low", "Close", "Volume"], "該次回傳同修前"
        assert ("X49O", "9mo", "1d") in MC._YF_OHLCV_FAIL_CACHE
        fred["body"] = _chart_ohlcv([1.0, 2.0])
        again = MC.fetch_yf_ohlcv("X49O", range_="9mo")
        assert fred["n"] == 1 and again.empty and list(again.columns) == [], "冷卻期內不重打上游"
        MC._YF_OHLCV_FAIL_CACHE[("X49O", "9mo", "1d")] -= MC._FAIL_COOLDOWN_SEC
        ok = MC.fetch_yf_ohlcv("X49O", range_="9mo")
        assert fred["n"] == 2 and ok["Close"].tolist() == [1.0, 2.0]
        assert ("X49O", "9mo", "1d") not in MC._YF_OHLCV_FAIL_CACHE

    def test_empty_close_respects_generation(self, fred):
        """期間有人成功過（世代已變）→ 晚到的「收盤全缺」不記退避（同其他失敗出口）。"""
        key = ("X49P", "9mo", "1d")
        fred["body"] = _chart_ohlcv([None])
        orig = MC.fetch_url

        def _fu(url, **kw):
            with MC._YF_OHLCV_FAIL_LOCK:
                MC._YF_OHLCV_OK_GEN_CACHE[key] = MC._YF_OHLCV_OK_GEN_CACHE.get(key, 0) + 1
            return orig(url, **kw)
        MC.fetch_url = _fu
        try:
            MC.fetch_yf_ohlcv("X49P", range_="9mo")
        finally:
            MC.fetch_url = orig
        assert key not in MC._YF_OHLCV_FAIL_CACHE

    def test_late_failure_keeps_newer_record(self, fred, monkeypatch):
        key = ("X49M", "9mo", "1d")
        orig = MC.fetch_url

        def _fu(url, **kw):
            with MC._YF_OHLCV_FAIL_LOCK:
                MC._YF_OHLCV_FAIL_CACHE[key] = time.time() + 50
            return orig(url, **kw)
        monkeypatch.setattr(MC, "fetch_url", _fu)
        fred["body"] = _chart_ohlcv([None])
        t0 = time.time()
        MC.fetch_yf_ohlcv("X49M", range_="9mo")
        assert MC._YF_OHLCV_FAIL_CACHE[key] >= t0 + 49

    def test_partial_close_is_success(self, fred):
        fred["body"] = _chart_ohlcv([None, 5.0])
        out = MC.fetch_yf_ohlcv("X49Q", range_="9mo")
        assert out["Close"].tolist() == [5.0] and "source" in out.columns
        assert ("X49Q", "9mo", "1d") not in MC._YF_OHLCV_FAIL_CACHE
        assert MC._YF_OHLCV_OK_GEN_CACHE[("X49Q", "9mo", "1d")] == 1


# ══════════════════════════════════════════════════════════════════
# D2-f41 proxy_helper URL 快取
# ══════════════════════════════════════════════════════════════════
class TestD2f41UrlCacheLock:
    def test_put_takes_the_lock(self, monkeypatch):
        """main：沒有 `_URL_CACHE_LOCK` → 紅。"""
        monkeypatch.setattr(PH, "_URL_CACHE", {})
        done = threading.Event()
        with PH._URL_CACHE_LOCK:
            t = threading.Thread(target=lambda: (PH._url_cache_put(("u", ()), b"x"), done.set()))
            t.start()
            assert not done.wait(0.2), "持鎖期間寫入必須等待"
            assert ("u", ()) not in PH._URL_CACHE
        t.join(5)
        assert done.is_set() and PH._URL_CACHE[("u", ())][1:] == (b"x", 200)

    def test_read_is_single_get(self, monkeypatch):
        """先查 in、再取值之間被逐出 → main 拋 KeyError（在 try 外）→ 紅；現在當成未命中、照常抓取。"""
        class _Evicting(dict):
            def __contains__(self, k):
                return True

            def __getitem__(self, k):
                raise KeyError(k)

        class _S:
            def get(self, url, **kw):
                r = requests.models.Response()
                r.status_code = 200
                r._content = b"fresh"
                return r

        monkeypatch.setattr(PH, "_URL_CACHE", _Evicting())
        monkeypatch.setattr(PH, "get_proxy_config", lambda: None)
        monkeypatch.setattr(PH, "_get_thread_session", lambda lean=False: _S())
        r = PH.fetch_url("https://example.invalid/x", attempts=1)
        assert r is not None and r.content == b"fresh"

    def test_cache_hit_unchanged(self, monkeypatch):
        monkeypatch.setattr(PH, "_URL_CACHE", {("https://e.invalid/y", ()): (time.time(), b"cached", 200)})
        r = PH.fetch_url("https://e.invalid/y")
        assert r.status_code == 200 and r.content == b"cached"

    def test_concurrent_puts_no_error(self, monkeypatch):
        monkeypatch.setattr(PH, "_URL_CACHE", {})
        monkeypatch.setattr(PH, "_URL_CACHE_MAX", 8)
        errs: list = []

        def _w(i):
            try:
                for j in range(1500):
                    PH._url_cache_put((i, j), b"v")
            except Exception as e:  # noqa: BLE001
                errs.append(e)
        ts = [threading.Thread(target=_w, args=(i,)) for i in range(8)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        assert errs == [] and len(PH._URL_CACHE) <= 8

    @pytest.mark.slow
    def test_puts_with_unlocked_external_clear(self, monkeypatch):
        """鎖外有人直接 `_URL_CACHE.clear()`（強制重抓的兩個呼叫端）同時寫入 → 寫入端不拋。
        （壓力測試，約 20 秒 → slow lane；迭代改成對快照做的那一處，拿掉快照時本測試會紅。）"""
        monkeypatch.setattr(PH, "_URL_CACHE", {})
        monkeypatch.setattr(PH, "_URL_CACHE_MAX", 10_000)
        monkeypatch.setattr(PH, "_URL_CACHE_TTL", -1)      # 每次寫入都要掃一輪「過期」
        stop = threading.Event()
        errs: list = []

        def _clearer():
            while not stop.is_set():
                PH._URL_CACHE.clear()

        def _writer(i):
            try:
                for j in range(3000):
                    if errs:
                        return
                    for k in range(20):
                        dict.__setitem__(PH._URL_CACHE, (i, j, k), (0.0, b"", 200))
                    PH._url_cache_put((i, j), b"v")
            except Exception as e:  # noqa: BLE001
                errs.append(e)
        c = threading.Thread(target=_clearer)
        ws = [threading.Thread(target=_writer, args=(i,)) for i in range(4)]
        c.start()
        for t in ws:
            t.start()
        for t in ws:
            t.join()
        stop.set()
        c.join()
        assert errs == []

    def test_clear_during_expiry_scan_not_a_false_failure(self, monkeypatch):
        """鎖外 `_URL_CACHE.clear()` 恰好落在過期掃描途中（以 ts 的 `__rsub__` 鉤子在掃描第一筆時觸發，
        確定性重現）→ 寫入端不拋、`fetch_url` 照常回 200。掃描若直接迭代活的 dict（不先取快照）→
        RuntimeError → 被 `fetch_url` 當一般錯誤接住 → 回 None（假失敗）。"""
        cache: dict = {}

        class _HookTs(float):
            fired = False

            def __rsub__(self, other):
                if not _HookTs.fired:
                    _HookTs.fired = True
                    dict.clear(cache)                         # 模擬另一執行緒的鎖外 clear()
                return float(other) - float(self)

        now = time.time()
        cache[("a", ())] = (_HookTs(now), b"a", 200)
        cache[("b", ())] = (_HookTs(now), b"b", 200)

        class _S:
            def get(self, url, **kw):
                r = requests.models.Response()
                r.status_code = 200
                r._content = b"fresh"
                return r

        monkeypatch.setattr(PH, "_URL_CACHE", cache)
        monkeypatch.setattr(PH, "get_proxy_config", lambda: None)
        monkeypatch.setattr(PH, "get_nas_relay", lambda: None)
        monkeypatch.setattr(PH, "_get_thread_session", lambda lean=False: _S())
        r = PH.fetch_url("https://example.invalid/z", attempts=1)
        assert _HookTs.fired, "前提：鉤子確實在掃描中觸發"
        assert r is not None and r.content == b"fresh"
        assert list(cache) == [("https://example.invalid/z", ())]

    def test_put_survives_external_clear(self, monkeypatch):
        """鎖外的 `_URL_CACHE.clear()`（強制重抓）在逐出迴圈中清空 → 不拋。"""
        class _ClearOnLen(dict):
            armed = False

            def __len__(self):
                n = dict.__len__(self)
                if self.armed and n:
                    self.armed = False
                    real = n
                    dict.clear(self)
                    return real
                return n

        d = _ClearOnLen({("a", i): (time.time(), b"v", 200) for i in range(4)})
        monkeypatch.setattr(PH, "_URL_CACHE", d)
        monkeypatch.setattr(PH, "_URL_CACHE_MAX", 4)
        d.armed = True
        PH._url_cache_put(("b", 0), b"w")
        assert ("b", 0) in d

    def test_eviction_order_unchanged(self, monkeypatch):
        now = time.time()
        d = {("k", i): (now - 10 + i, b"v", 200) for i in range(3)}
        d[("k", "tie")] = (now - 10, b"v", 200)            # 與 ("k", 0) 同時點 → 先插入者先被逐出
        monkeypatch.setattr(PH, "_URL_CACHE", d)
        monkeypatch.setattr(PH, "_URL_CACHE_MAX", 4)
        PH._url_cache_put(("new", 0), b"n")
        assert ("k", 0) not in d and ("k", "tie") in d and ("new", 0) in d


# ══════════════════════════════════════════════════════════════════
# D2-f29 單股月營收 fallback：OpenAPI 快照失敗冷卻檔與檔共用
# ══════════════════════════════════════════════════════════════════
_TWSE_ROWS = [{"公司代號": "2330", "資料年月": "11508", "營業收入-當月營收": "1000"},
              {"公司代號": "2317", "資料年月": "11508", "營業收入-當月營收": "2000"}]
_TPEX_ROWS = [{"公司代號": "6488", "資料年月": "11508", "營業收入-當月營收": "3000"}]


class _MResp:
    def __init__(self, rows):
        self.status_code = 200
        self._rows = rows

    def json(self):
        return [dict(r) for r in self._rows]


@pytest.fixture
def mrev(monkeypatch, fc_clock):
    w = types.SimpleNamespace(twse="none", tpex="none", calls={"twse": 0, "tpex": 0})

    def _fu(url, headers=None, params=None, timeout=20, attempts=3):
        side = "twse" if "openapi.twse.com.tw" in url else "tpex"
        w.calls[side] += 1
        if getattr(w, side) == "ok":
            return _MResp(_TWSE_ROWS if side == "twse" else _TPEX_ROWS)
        return None

    monkeypatch.setattr(PH, "fetch_url", _fu)
    monkeypatch.setattr(MR, "finmind_get", lambda *a, **k: pd.DataFrame())
    monkeypatch.setenv("FINMIND_TOKEN", "dummy")
    MR.fetch_monthly_revenue.clear()
    MR.fetch_batch_monthly_revenue.clear()
    yield w
    MR.fetch_monthly_revenue.clear()
    MR.fetch_batch_monthly_revenue.clear()


class TestD2f29SharedOpenApiCooldown:
    def test_many_stocks_hit_openapi_once(self, mrev):
        """FinMind 掛、OpenAPI 兩邊都失敗：5 檔只打上游一輪。main：每檔各一輪（10 次）→ 紅。"""
        outs = [MR.fetch_monthly_revenue(str(9000 + i)) for i in range(5)]
        assert mrev.calls == {"twse": 1, "tpex": 1}
        for df in outs:
            _assert_bare_empty(df)
        for i in range(5):
            assert (str(9000 + i), 18) in MR._single_fail_cooldown, "每一檔照舊不入快取、記自己的冷卻"

    def test_shared_snapshot_serves_other_side(self, mrev):
        """上市失敗、上櫃正常：上市股失敗後，上櫃股在冷卻期內直接用同一份快照拿到資料（0 次上游）。"""
        mrev.tpex = "ok"
        _assert_bare_empty(MR.fetch_monthly_revenue("2330"))
        n = dict(mrev.calls)
        df = MR.fetch_monthly_revenue("6488")
        assert mrev.calls == n, "冷卻期內不重打"
        assert len(df) == 1 and df["revenue"].iloc[0] == 3000 * 1000.0
        assert list(df.columns) == ["date", "revenue", "revenue_year", "revenue_month"]
        assert ("6488", 18) not in MR._single_fail_cooldown, "拿到資料 → 照舊算成功"

    def test_result_same_as_refetch(self, mrev, monkeypatch):
        """冷卻期內沿用快照的結果 ＝ 關掉共用冷卻、重打一次（上游仍同樣失敗）的結果。"""
        mrev.tpex = "ok"
        MR.fetch_monthly_revenue("2330")
        shared = MR.fetch_monthly_revenue.with_status("6488", 12)
        MR.fetch_monthly_revenue.clear()
        monkeypatch.setattr(MR._openapi_snapshot_fail_cooldown, "seconds", 0.0)
        MR.fetch_monthly_revenue("2330")
        fresh = MR.fetch_monthly_revenue.with_status("6488", 12)
        assert shared[1] == fresh[1]
        pd.testing.assert_frame_equal(shared[0], fresh[0])
        a = MR.fetch_monthly_revenue.with_status("2317", 12)
        assert a[1] is True and a[0].empty

    def _escalate_to_long_cooldown(self, mrev, fc_clock):
        """上市持續失敗、上櫃正常：失敗兩次 → 冷卻加倍到 2×FAIL_COOLDOWN_SEC（> URL 快取 300 秒）。"""
        mrev.tpex = "ok"
        MR.fetch_monthly_revenue("2330")                     # 失敗 #1（冷卻 180 秒）
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        MR.fetch_monthly_revenue("2317")                     # 期滿重抓、再失敗 #2（冷卻 360 秒）
        assert mrev.calls == {"twse": 2, "tpex": 2}

    def test_reused_snapshot_never_older_than_url_cache(self, mrev, fc_clock):
        """冷卻期內沿用的快照含正常市場（上櫃）的資料時，最多沿用 URL 快取期限（300 秒）；超過就重抓一次
        —— 不把比修前更舊的上櫃資料以「現在」的 fetched_at 入 6 小時快取。修前（本批 v1）沿用到冷卻結束 → 紅。"""
        self._escalate_to_long_cooldown(mrev, fc_clock)
        fc_clock["now"] += PH._URL_CACHE_TTL                 # 剛好 300 秒：仍沿用
        df = MR.fetch_monthly_revenue("6488")
        assert mrev.calls == {"twse": 2, "tpex": 2} and len(df) == 1
        fc_clock["now"] += 1                                 # 超過 300 秒，仍在 360 秒冷卻內
        df = MR.fetch_monthly_revenue("6488", months=12)
        assert mrev.calls == {"twse": 3, "tpex": 3}, "快照過舊 → 重抓一次"
        assert len(df) == 1 and df["revenue"].iloc[0] == 3000 * 1000.0
        MR.fetch_monthly_revenue("6488", months=6)           # 重抓後以新快照重記 → 再沿用
        assert mrev.calls == {"twse": 3, "tpex": 3}

    def test_empty_snapshot_reused_whole_cooldown(self, mrev, fc_clock):
        """兩邊都失敗（快照為空）→ 沒有舊資料問題，整段冷卻都沿用、不重打。"""
        MR.fetch_monthly_revenue("9600")
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        MR.fetch_monthly_revenue("9601")                     # 失敗 #2 → 冷卻 360 秒
        n = dict(mrev.calls)
        fc_clock["now"] += 2 * FAIL_COOLDOWN_SEC - 1
        MR.fetch_monthly_revenue("9602")
        assert mrev.calls == n

    def test_cooldown_expires_and_recovers(self, mrev, fc_clock):
        MR.fetch_monthly_revenue("9100")
        mrev.twse = mrev.tpex = "ok"
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        df = MR.fetch_monthly_revenue("2330")
        assert mrev.calls == {"twse": 2, "tpex": 2} and df["revenue"].iloc[0] == 1000 * 1000.0
        assert MR._OPENAPI_SNAPSHOT_KEY not in MR._openapi_snapshot_fail_cooldown, "成功即解除"

    def test_escalates_like_single(self, mrev, fc_clock):
        assert MR._openapi_snapshot_fail_cooldown.seconds == MR._single_fail_cooldown.seconds
        assert MR._openapi_snapshot_fail_cooldown.max_seconds == MR._single_fail_cooldown.max_seconds
        MR.fetch_monthly_revenue("9200")
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        MR.fetch_monthly_revenue("9201")
        assert mrev.calls["twse"] == 2
        fc_clock["now"] += FAIL_COOLDOWN_SEC                 # 第二次失敗 → 冷卻加倍
        MR.fetch_monthly_revenue("9202")
        assert mrev.calls["twse"] == 2, "仍在加倍後的冷卻內"

    def test_success_resets_escalation(self, mrev, fc_clock):
        """成功一次即歸零：之後再失敗，冷卻從起點算（不是接著加倍）。"""
        MR.fetch_monthly_revenue("9500")                     # 失敗 #1
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        mrev.twse = mrev.tpex = "ok"
        MR.fetch_monthly_revenue("2330")                     # 成功
        mrev.twse = mrev.tpex = "none"
        MR.fetch_monthly_revenue("9501")                     # 新一串的失敗 #1
        n = mrev.calls["twse"]
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        MR.fetch_monthly_revenue("9502")
        assert mrev.calls["twse"] == n + 1, "冷卻回到起點 FAIL_COOLDOWN_SEC"

    def test_clear_resets_shared_cooldown(self, mrev):
        MR.fetch_monthly_revenue("9300")
        MR.fetch_monthly_revenue.clear()
        MR.fetch_monthly_revenue("9301")
        assert mrev.calls == {"twse": 2, "tpex": 2}

    def test_batch_path_not_affected(self, mrev):
        """全市場那支不吃這張冷卻（有自己的 `_batch_fail_cooldown`）。"""
        MR.fetch_monthly_revenue("9400")
        MR.fetch_batch_monthly_revenue()
        assert mrev.calls == {"twse": 2, "tpex": 2}

    def test_success_path_unchanged(self, mrev):
        mrev.twse = mrev.tpex = "ok"
        df = MR.fetch_monthly_revenue("2317")
        assert df["revenue"].tolist() == [2000 * 1000.0]
        assert df.attrs["source"] == "TWSE-OpenAPI:t187ap05_L(keyless fallback,單股)"
        assert MR._OPENAPI_SNAPSHOT_KEY not in MR._openapi_snapshot_fail_cooldown
