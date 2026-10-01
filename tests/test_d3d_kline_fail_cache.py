# -*- coding: utf-8 -*-
"""資料層修錯（批 D3d，2026-09-28，CLAUDE.md §1.A-3「只快取成功結果；失敗時退避，不連續轟炸來源」）三列：

  · **D2-f16（根因）** L1 `yf_proxy.cached_history`：yfinance `history()` 預設把抓取階段的例外**吞掉**、
    回一張帶欄位的空表（1.x `hide_exceptions=True`、0.2.x `raise_errors=False`；只有 429 往上拋；
    時區未快取時例外才可能從時區查詢那段拋出）——「時區已快取 ＋ 網路／代理斷線」與「這檔真的沒資料」
    長得一樣，被快取層照舊快取 1 小時（#741 只處理了「拋例外」那條路）。現在快取層經
    `_history_or_raise` 以 `raise_errors=True` 呼叫：網路／代理錯誤、逾時、Yahoo 維護頁、非 JSON 回應
    **原樣往上拋**（不入快取、外層 `FailCooldown` 冷卻）；yfinance 自己回報的「沒有資料」
    （`YFTickerMissingError` 系、`YFChartError`、`YFInvalidPeriodError`；0.2.36～0.2.38 為裸 `Exception`）
    回空表、照舊快取。另掛 `cached_history.with_status`（同一次呼叫取得「是否確定失敗」）。
  · **D2-f15** L1 `daily_data_fetchers.fetch_single`：自己的 `st.cache_data`（1 小時）修前連失敗的 None 也
    快取 —— 上游恢復、冷卻解除之後仍回 None；冷卻期內按 v2「強制重抓」（清 `st.cache_data`、清不到冷卻）
    更把 None 再凍 1 小時。現在快取在 `_fetch_single_cached`：確定失敗（備援清單全空且至少一檔抓取
    失敗；或本體拋例外）拋 `_SingleFetchFailed` 不入快取；成功與「真的沒資料」照舊。
  · **D2-f20（只補測試）**：`FailCooldown._streak` 上限、`cached_history` 快取層套用 proxy、
    帶欄位的空表、冷卻鍵 (ticker, period) 補**行為**測試（`TestD2f20*`；對應突變見 `TestMutations`）。

「修前」一律以**修前模型**比對：把本次改動的區塊換回 origin/main `b2dafba` 原文（逐字嵌在本檔）的同一份模組。
不觸網：換掉 `yfinance.Ticker`（`_FakeYF`，仿 yfinance 真實語意）、proxy 設定固定為「無」、pkl 目錄換到 tmp。
另有 `TestRealYfinancePremise` 以**已安裝的真 yfinance**、只換掉最底層 `YfData.get`（HTTP）與時區查詢
（＝時區已快取）驗前提：修前那種呼叫真的把網路錯誤吞成空表、`raise_errors=True` 真的讓它浮出。
日後 yfinance 改變這兩點，前提測試轉紅，屆時重新評估。
冷卻期用假時鐘：只換 `shared.fail_cooldown` 的 `time`（`st.cache_data` 的 TTL 不受影響，故「把假時鐘推過
冷卻期仍不重打」＝ 真的在快取裡，不是在退避裡）。
突變（`TestMutations`）：每一個修正點拿掉後，本檔對應的共用檢查（`_check_*`）轉紅。
"""
from __future__ import annotations

import ast
import contextlib
import importlib.util
import json
import os
import pathlib
import sys
import threading
import time
import types
import warnings

import numpy as np
import pandas as pd
import pytest
import requests
import yfinance
from yfinance import exceptions as YFE

import shared.cache_layer as CL
import shared.fail_cooldown as FC
import src.data.daily.daily_data_fetchers as DDF
import src.data.proxy as PX
import src.data.proxy.yf_proxy as YP
import src.data.stock.tw_stock_data_fetcher as TSF
from shared.fail_cooldown import FAIL_COOLDOWN_SEC
from shared.ttls import TTL_1HOUR


# ══════════════════════════════════════════════════════════════════
# 模組工具：修前模型、突變體
# ══════════════════════════════════════════════════════════════════
def _load(src: str, name: str, file: str) -> types.ModuleType:
    spec = importlib.util.spec_from_loader(name, loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = file
    sys.modules[name] = m
    try:
        exec(compile(src, file, "exec"), m.__dict__)
    finally:
        sys.modules.pop(name, None)
    return m


def _mutant(mod: types.ModuleType, *pairs: tuple[str, str], tag: str) -> types.ModuleType:
    """同 tests/test_d3c_backoff_d2f5.py：原始碼字面替換後另建一份模組（真模組不動）。

    `tag` 讓每個突變體有自己的模組名 —— `st.cache_data` 以「模組名＋函式名＋原始碼」當快取鍵。
    """
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert src.count(old) == 1, f"突變點不唯一或已不存在：{old!r}"
        src = src.replace(old, new)
    return _load(src, f"_mutant_d3d_{tag}_{mod.__name__.rsplit('.', 1)[-1]}", mod.__file__)


#: b2dafba `yf_proxy.py` 的 `_cached_history_cached` … `cached_history.clear = …`（逐字，第 74～126 行）。
_PREFIX_YP_BLOCK = '''@st.cache_data(ttl=TTL_1HOUR, max_entries=200, show_spinner=False)
def _cached_history_cached(ticker: str, period: str = "1y") -> pd.DataFrame:
    """`cached_history()` 的快取層。**拋例外一律往上拋**（D2-f4 2026-09-28，同
    `_cached_dividends_cached`；§1.A-3(a)「只快取成功結果」；st.cache_data 不快取例外）。
    成功與「沒拋、只回 None／空表」兩條路徑、TTL、max_entries 同修前（照舊快取）。"""
    import yfinance as yf
    with _proxy_env():
        _df = yf.Ticker(ticker).history(period=period)
    if _df is None or _df.empty:
        return pd.DataFrame()
    return _df


#: D2-f4：K 線失敗退避（§1.A-3(b)）—— 冷卻期內同一 (ticker, period) 不重打 Yahoo，回同一份空表。
_history_fail_cooldown = _FailCooldown()


def cached_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """yfinance Ticker.history with NAS proxy + 1h cache（**只快取成功**）。

    Args:
        ticker: yfinance 標的代碼，例 "2330.TW"
        period: "5d"/"1mo"/"3mo"/"1y"/"5y"/"max"

    Returns:
        pd.DataFrame；抓不到回空 DataFrame（不爆例外）。回傳內容同修前（失敗也是無旗標的空表）。

    D2-f4（2026-09-28）：修前 yfinance **拋例外**（例：429 `YFRateLimitError`）時回的空表被
    快取 1 小時 —— Yahoo 恢復後同參數仍回空表。現在拋例外那一種**不入快取**；失敗後
    `shared.fail_cooldown.FAIL_COOLDOWN_SEC` 秒內同一 (ticker, period) 不重抓，回同一份空表；
    成功一次即解除。**失敗 vs 真的沒資料的判準**：yfinance **拋例外**＝失敗；**沒拋、只回
    None／空表**＝照舊快取 —— 那與「這檔真的沒有資料」在這一層分不出來，不猜（§1；同
    `cached_dividends` 的 Q5-r2 判準）。`.clear()` 同清快取與退避紀錄。
    """
    _key = (ticker, period)
    _hit, _gen = _history_fail_cooldown.begin(_key)
    if _hit is not _FC_NO_HIT:
        return _hit
    try:
        _df = _cached_history_cached(ticker, period=period)
    except Exception as _e:
        print(f"[yf_proxy.history] {ticker}: {type(_e).__name__}: {_e}")
        return _history_fail_cooldown.fail(_key, _gen, pd.DataFrame())
    _history_fail_cooldown.success(_key)
    return _df


def _clear_cached_history() -> None:
    getattr(_cached_history_cached, "clear", lambda: None)()
    _history_fail_cooldown.clear()


cached_history.clear = _clear_cached_history
'''

#: b2dafba `daily_data_fetchers.py` 的 `fetch_single`（逐字，第 104～149 行）。
_PREFIX_DDF_BLOCK = '''@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_single(symbol, period: str = "60d"):
    """yfinance 單檔抓取(走 yf_proxy 內含 proxy env + cache_data 1h)+ /tmp pickle 30 分快取。

    跨 process 重啟存活(pkl)+ 同 process 內秒讀(yf_proxy cache_data)兩層保護。
    """
    import hashlib as _hs2
    # D3 v18.437:pkl 快取改用 cache_layer SSOT(_pkl_get/_pkl_put,同檔 fetch_institutional 模式);
    # key 沿用 md5(yf_{symbol}_{period}),TTL 30 分。壞檔 fallback 重抓由 _pkl_get 內建(§1 stderr log)。
    _ck2 = _hs2.md5(f'yf_{symbol}_{period}'.encode()).hexdigest()
    _c2 = _pkl_get(_ck2, TTL_30MIN)
    if _c2 is not _CACHE_SENTINEL:
        return _c2
    # 美元指數備援 symbol 清單
    _sym_list = [symbol]
    if symbol in ('DX-Y.NYB', 'DX=F'):
        _sym_list = ['DX-Y.NYB', 'DX=F', 'UUP']  # NYB→期貨→ETF
    # v18.209 K5:改走 yf_proxy.cached_history(內含 proxy env + st.cache_data 1h),
    # 加 pkl 30min cache 兩層保護 → 跨 process 重啟存活 + 同 process 內秒讀。
    try:
        from src.data.proxy import cached_history as _yp_hist
        h = None
        for _sym in _sym_list:
            _h = _yp_hist(_sym, period=period)
            if _h is not None and not _h.empty:
                h = _h
                break
        if h is None or h.empty:
            return None
        h.index = pd.DatetimeIndex(h.index).tz_localize(None)
        h.columns = [c.lower().replace(' ', '_') for c in h.columns]
        if 'close' in h.columns:
            h = h.dropna(subset=['close'])
        elif 'Close' in h.columns:
            h = h.dropna(subset=['Close'])
        if h.empty:
            _prov_log('fetch_single', 'yf_proxy.cached_history', symbol, 'None:empty')
            return None
        _pkl_put(_ck2, h)
        _prov_log('fetch_single', 'yf_proxy.cached_history', symbol, f'df:{len(h)}rows')
        return h
    except Exception as e:
        print(f'[yf:{symbol}] {e}')
        _prov_log('fetch_single', 'yf_proxy.cached_history', symbol,
                  f'None:exc:{type(e).__name__}')
        return None
'''


def _prefix_yp() -> types.ModuleType:
    src = pathlib.Path(YP.__file__).read_text(encoding="utf-8")
    a = src.index("#: D2-f16：yfinance 在")
    end = "cached_history.with_status = _cached_history_with_status\n"
    b = src.index(end) + len(end)
    return _load(src[:a] + _PREFIX_YP_BLOCK + src[b:], "_prefix_d3d_yf_proxy", YP.__file__)


def _prefix_ddf() -> types.ModuleType:
    src = pathlib.Path(DDF.__file__).read_text(encoding="utf-8")
    a = src.index("class _SingleFetchFailed(")
    end = "fetch_single.clear = _clear_fetch_single\n"
    b = src.index(end) + len(end)
    return _load(src[:a] + _PREFIX_DDF_BLOCK + src[b:], "_prefix_d3d_daily_data_fetchers", DDF.__file__)


def _clear(fn) -> None:
    getattr(fn, "clear", lambda: None)()


@contextlib.contextmanager
def _route(yp: types.ModuleType):
    """讓 `fetch_single` 經 `from src.data.proxy import cached_history` 拿到 `yp` 那一份（真的持有者上換，
    不碰套件層 —— 見 tests/test_zz_proxy_pollution_lock.py）。"""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(YP, "cached_history", yp.cached_history)
        yield


def _fresh(*fns) -> None:
    """清快取：傳進來的各層 ＋ pkl 目錄（已由 autouse 換到 tmp）。"""
    for f in fns:
        _clear(f)
    CL._pkl_clear_all()


# ══════════════════════════════════════════════════════════════════
# 夾具與替身
# ══════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    """每一條都：proxy 設定固定為「無」（不做 TCP 探測）、pkl 目錄換到 tmp、清兩層快取與退避。"""
    monkeypatch.setattr(TSF, "_load_proxy_config", lambda: None)
    monkeypatch.setattr(CL, "_PKL_DIR", str(tmp_path / "pkl"))
    YP.cached_history.clear()
    DDF.fetch_single.clear()
    yield
    YP.cached_history.clear()
    DDF.fetch_single.clear()


@pytest.fixture
def fc_clock(monkeypatch):
    """可手動推進的假 monotonic 時鐘 —— **只**換 `shared.fail_cooldown` 模組裡的 `time`（同 #741 測試）。"""
    t = {"now": float(int(time.monotonic()))}
    monkeypatch.setattr(FC, "time", types.SimpleNamespace(monotonic=lambda: t["now"]))
    return t


def _exc(cls, msg: str):
    """造 yfinance 例外但不呼叫其 `__init__`（各版建構子簽名不同；型別與訊息才是這裡要的）。"""
    e = cls.__new__(cls)
    Exception.__init__(e, msg)
    return e


_YF_COLS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def _yf_empty() -> pd.DataFrame:
    """yfinance `utils.empty_df()` 的同型：帶欄位、0 列、索引名 Date（把例外吞掉時回的就是這種）。"""
    return pd.DataFrame(index=pd.DatetimeIndex([], name="Date"), columns=_YF_COLS, dtype=float)


def _ok_frame(ticker: str, n: int = 70) -> pd.DataFrame:
    """某檔「上游正常」時的 K 線（依代號決定、可重算出同一份當期望值；索引帶交易所時區，同 yfinance）。"""
    seed = sum(map(ord, ticker)) % 97
    idx = pd.date_range("2026-06-01", periods=n, freq="D", tz="Asia/Taipei", name="Date")
    close = 100.0 + seed + np.arange(n, dtype=float)
    return pd.DataFrame({"Open": close - 0.5, "High": close + 1.0, "Low": close - 1.0, "Close": close,
                         "Volume": (1000 + np.arange(n)).astype("int64"),
                         "Dividends": 0.0, "Stock Splits": 0.0}, index=idx)


def _fs_expected(ticker: str) -> pd.DataFrame:
    """`fetch_single` 成功時的輸出（修前那幾行整理：去時區、欄名小寫、丟 close 為 NaN 的列）。"""
    h = _ok_frame(ticker)
    h.index = pd.DatetimeIndex(h.index).tz_localize(None)
    h.columns = [c.lower().replace(" ", "_") for c in h.columns]
    return h.dropna(subset=["close"])


def _assert_bare_empty(df) -> None:
    """修前 `cached_history` 的空回傳是 `pd.DataFrame()` —— 逐字比（無欄位、無旗標、無 attrs）。"""
    ref = pd.DataFrame()
    assert isinstance(df, pd.DataFrame), type(df)
    assert repr(df) == repr(ref), repr(df)
    pd.testing.assert_frame_equal(df, ref)
    assert type(df.index) is type(ref.index) and df.attrs == {}


def _respond(mode: str, ticker: str, period: str, raise_errors: bool):
    if mode == "ok":
        return _ok_frame(ticker)
    if mode == "none":
        return None
    if mode == "empty":
        return _yf_empty()                       # 上游有回應、解析後 0 列：兩種呼叫都不拋
    if mode == "rate_limited":
        raise YFE.YFRateLimitError()             # 1.x 對 429 一律往上拋（不看 raise_errors）
    exc = {
        "net_down": lambda: requests.exceptions.ConnectionError("simulated: network down"),
        "timeout": lambda: requests.exceptions.ReadTimeout("simulated: read timeout"),
        "no_data": lambda: _exc(YFE.YFPricesMissingError,
                                f"${ticker}: possibly delisted; no price data found  (period={period})"),
        "tz_missing": lambda: _exc(YFE.YFTzMissingError, f"${ticker}: possibly delisted; no timezone found"),
        "bad_period": lambda: _exc(YFE.YFInvalidPeriodError, f"{ticker}: Period '{period}' is invalid"),
        "legacy_no_data": lambda: Exception(f"{ticker}: No data found, symbol may be delisted"),
        # 維護頁（"Will be right back"）：1.x 拋 YFDataException、0.2.x 拋 RuntimeError —— 皆為抓取失敗
        "yahoo_down": lambda: _exc(getattr(YFE, "YFDataException", RuntimeError),
                                   "*** YAHOO! FINANCE IS CURRENTLY DOWN! ***"),
        "yahoo_down_legacy": lambda: RuntimeError("*** YAHOO! FINANCE IS CURRENTLY DOWN! ***"),
    }[mode]()
    if raise_errors:
        raise exc
    return _yf_empty()                           # yfinance 預設：吞掉、回帶欄位空表（修前破口）


class _FakeYF:
    """`yfinance.Ticker` 替身，**仿 yfinance 真實語意**（見 `TestRealYfinancePremise`）。

    mode（`per` 可逐檔覆寫）：ok／none／empty（兩種呼叫都回帶欄位空表）／rate_limited（兩種呼叫都拋 429）／
    net_down・timeout（`raise_errors=True` 拋 requests 例外；預設吞成帶欄位空表）／
    yahoo_down・yahoo_down_legacy（維護頁：`raise_errors=True` 拋 YFDataException／RuntimeError；預設吞成空表）／
    no_data・tz_missing・bad_period（`raise_errors=True` 拋 yfinance 型別例外；預設帶欄位空表）／
    legacy_no_data（同上，裸 `Exception`：0.2.36～0.2.38）。記下每一次 `history()` 的
    (ticker, period, raise_errors)。
    """

    def __init__(self):
        self.mode = "net_down"
        self.per: dict = {}
        self.calls: list = []
        self._lock = threading.Lock()

    def Ticker(self, ticker):  # noqa: N802 — 對齊 yfinance API
        outer = self

        class _T:
            def history(self, period="1mo", raise_errors=False, **_kw):
                with outer._lock:
                    outer.calls.append((ticker, period, raise_errors))
                    mode = outer.per.get(ticker, outer.mode)
                return _respond(mode, ticker, period, raise_errors)
        return _T()

    def n(self, ticker: str) -> int:
        with self._lock:
            return sum(1 for c in self.calls if c[0] == ticker)


@pytest.fixture
def yfh(monkeypatch, fc_clock):
    fake = _FakeYF()
    monkeypatch.setattr(yfinance, "Ticker", fake.Ticker)
    return fake


@pytest.fixture
def prefix():
    """修前模型（b2dafba 原文）：`yp`＝修前 `cached_history`、`ddf`＝修前 `fetch_single`。"""
    yp0, ddf0 = _prefix_yp(), _prefix_ddf()
    assert not hasattr(yp0.cached_history, "with_status") and not hasattr(ddf0, "_fetch_single_cached")
    yield types.SimpleNamespace(yp=yp0, ddf=ddf0)
    _clear(yp0.cached_history)
    _clear(ddf0.fetch_single)
    _clear(ddf0.fetch_flow_snapshot)


# ══════════════════════════════════════════════════════════════════
# 共用檢查（真模組必過；突變體／修前模型用來證明檢查擋得住）
# ══════════════════════════════════════════════════════════════════
def _check_swallowed_error_not_cached(yp, fake, clock, mode: str = "net_down") -> None:
    """D2-f16：yfinance 吞成空表的網路錯誤 → 回同一份空表、不入快取、冷卻期內不重打、期滿即取得資料。"""
    _fresh(yp.cached_history)
    fake.mode, fake.per = mode, {}
    base = fake.n("2330.TW")
    _assert_bare_empty(yp.cached_history("2330.TW", period="1y"))
    assert fake.n("2330.TW") - base == 1
    fake.mode = "ok"                                          # 上游恢復，但仍在冷卻期內
    clock["now"] += FAIL_COOLDOWN_SEC - 1
    for _ in range(3):
        _assert_bare_empty(yp.cached_history("2330.TW", period="1y"))
    assert fake.n("2330.TW") - base == 1, "冷卻期內 0 次上游呼叫"
    clock["now"] += 1                                         # 剛好滿冷卻期
    pd.testing.assert_frame_equal(yp.cached_history("2330.TW", period="1y"), _ok_frame("2330.TW"))
    assert fake.n("2330.TW") - base == 2, "冷卻期過的下一次即取得資料（修前：被當成沒資料快取 1 小時）"
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    pd.testing.assert_frame_equal(yp.cached_history("2330.TW", period="1y"), _ok_frame("2330.TW"))
    assert fake.n("2330.TW") - base == 2, "恢復後的成功照舊入快取"


def _check_no_data_cached(yp, fake, clock, mode: str) -> None:
    """真的沒資料（yfinance 自己回報、或沒拋只回空）→ 回 `pd.DataFrame()`、照舊快取、不記退避（同修前）。"""
    _fresh(yp.cached_history)
    fake.mode, fake.per = mode, {}
    base = fake.n("9999.TW")
    _assert_bare_empty(yp.cached_history("9999.TW", period="1y"))
    fake.mode = "ok"
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    _assert_bare_empty(yp.cached_history("9999.TW", period="1y"))
    assert fake.n("9999.TW") - base == 1, "照舊快取（TTL 內不重打）"
    assert ("9999.TW", "1y") not in yp._history_fail_cooldown, "不是失敗，不記退避"


def _check_with_status(yp, fake, clock) -> None:
    """`.with_status`：(與 `cached_history` 逐字相同的回傳, 是否確定抓取失敗)。"""
    _fresh(yp.cached_history)
    fake.per = {"2454.TW": "net_down", "3008.TW": "no_data", "2303.TW": "ok"}
    base = fake.n("2454.TW")
    df, failed = yp.cached_history.with_status("2454.TW", "1y")
    _assert_bare_empty(df)
    assert failed is True, "新的失敗"
    df, failed = yp.cached_history.with_status("2454.TW", "1y")
    _assert_bare_empty(df)
    assert failed is True, "冷卻期內回的那一份仍標失敗"
    assert fake.n("2454.TW") - base == 1
    df, failed = yp.cached_history.with_status("3008.TW", "1y")
    _assert_bare_empty(df)
    assert failed is False, "真的沒資料不是失敗"
    df, failed = yp.cached_history.with_status("2303.TW", "1y")
    pd.testing.assert_frame_equal(df, _ok_frame("2303.TW"))
    assert failed is False
    pd.testing.assert_frame_equal(yp.cached_history("2303.TW", period="1y"), df)


def _check_rate_limit_never_no_data(yp) -> None:
    """429 一律是抓取失敗 —— 就算日後 yfinance 讓它也繼承「沒資料」那一系（防型別階層變動）。"""
    class _FutureRateLimit(YFE.YFRateLimitError, YFE.YFTickerMissingError):
        pass
    assert yp._is_yf_no_data(_exc(YFE.YFRateLimitError, "429")) is False
    assert yp._is_yf_no_data(_exc(_FutureRateLimit, "429")) is False


def _check_legacy_signature_fallback(yp) -> None:
    """日後版本移除 `raise_errors`（TypeError 且提到它）→ 退回修前呼叫：成功照拿、沒資料照舊快取。"""
    _fresh(yp.cached_history)
    calls: list = []

    class _T:
        def __init__(self, t):
            self.t = t

        def history(self, period="1mo"):                     # 沒有 raise_errors 參數
            calls.append((self.t, period))
            return _ok_frame(self.t) if self.t == "0050.TW" else _yf_empty()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(yfinance, "Ticker", _T)
        pd.testing.assert_frame_equal(yp.cached_history("0050.TW", period="1y"), _ok_frame("0050.TW"))
        _assert_bare_empty(yp.cached_history("0000.TW", period="1y"))
        _assert_bare_empty(yp.cached_history("0000.TW", period="1y"))
    assert calls == [("0050.TW", "1y"), ("0000.TW", "1y")], "每一檔只打一次（退回呼叫不重打、空表照舊快取）"
    assert ("0000.TW", "1y") not in yp._history_fail_cooldown


def _check_unrelated_typeerror_not_retried(yp) -> None:
    """yfinance 內部的 TypeError（與 raise_errors 無關）＝ 抓取失敗，**不**退回重打第二次。"""
    _fresh(yp.cached_history)
    calls: list = []

    class _T:
        def __init__(self, t):
            pass

        def history(self, period="1mo", raise_errors=False):
            calls.append(raise_errors)
            raise TypeError("unsupported operand type(s) for /: 'NoneType' and 'float'")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(yfinance, "Ticker", _T)
        df, failed = yp.cached_history.with_status("1101.TW", "1y")
    _assert_bare_empty(df)
    assert failed is True
    assert calls == [True], "只打一次上游"


def _check_deprecation_as_error_falls_back(yp) -> None:
    """`DeprecationWarning` 被設成例外（-W error；1.x 在發出 K 線請求前就警告）→ 退回修前呼叫、只打一次。"""
    calls: list = []

    class _T:
        def history(self, period="1mo", raise_errors=False):
            if raise_errors:
                warnings.warn("'raise_errors' deprecated, do: yf.config.debug.hide_exceptions = False",
                              DeprecationWarning, stacklevel=2)
            calls.append(raise_errors)
            return _ok_frame("0056.TW")

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        try:
            df = yp._history_or_raise(_T(), "0056.TW", "1y")
        except Exception as e:  # noqa: BLE001
            raise AssertionError(f"不該拋：{e!r}") from e
    pd.testing.assert_frame_equal(df, _ok_frame("0056.TW"))
    assert calls == [False]


def _check_fetch_single_failure_not_cached(yp, ddf, fake, clock, symbol: str = "^DJI") -> None:
    """D2-f15：`cached_history` 判定失敗 → `fetch_single` 回 None 不入快取；上游恢復＋冷卻期過的下一次即取得資料。"""
    _fresh(yp.cached_history, ddf.fetch_single)
    with _route(yp):
        fake.mode, fake.per = "net_down", {}
        base = fake.n(symbol)
        assert ddf.fetch_single(symbol) is None
        n0 = fake.n(symbol)
        assert n0 - base == 1
        fake.mode = "ok"
        clock["now"] += FAIL_COOLDOWN_SEC - 1
        assert ddf.fetch_single(symbol) is None, "冷卻期內照舊回 None"
        assert fake.n(symbol) == n0, "冷卻期內 0 次上游呼叫"
        clock["now"] += 1
        got = ddf.fetch_single(symbol)
        assert got is not None, "冷卻期過的下一次即取得資料（修前：None 凍 1 小時）"
        pd.testing.assert_frame_equal(got, _fs_expected(symbol))
        assert fake.n(symbol) == n0 + 1


def _check_fetch_single_force_refresh_in_cooldown(yp, ddf, fake, clock) -> None:
    """冷卻期內按 v2「強制重抓」（真的 L3 `clear_macro_caches`：清 pkl／`st.cache_data`／proxy 快取，
    清不到冷卻）→ 當下仍回 None，但**不再凍 1 小時**：冷卻期過的下一次一般呼叫即取得資料。

    同 tests/test_d3c_backoff_d2f5.py 的顧慮，不在測試行程裡真的清全站快取：`st.cache_data.clear`
    換成只清這兩層（＝全站 clear 對它們的效果）、proxy_helper 的兩個快取換成替身；pkl 目錄已在 tmp。"""
    import streamlit

    import src.data.proxy.proxy_helper as PH
    from src.services.macro_refresh_service import clear_macro_caches
    _fresh(yp.cached_history, ddf.fetch_single)
    scoped: list = []

    def _scoped_clear(_self=None):
        scoped.append(1)
        _clear(getattr(ddf, "_fetch_single_cached", ddf.fetch_single))
        _clear(yp._cached_history_cached)

    with _route(yp), pytest.MonkeyPatch.context() as mp:
        mp.setattr(type(streamlit.cache_data), "clear", _scoped_clear)
        mp.setattr(PH, "_URL_CACHE", {})
        mp.setattr(PH, "reset_proxy_cache", lambda: None)
        fake.mode, fake.per = "net_down", {}
        base = fake.n("^SOX")
        assert ddf.fetch_single("^SOX") is None               # t=0 失敗，冷卻開始
        clock["now"] += 60
        clear_macro_caches()                                    # t=60 使用者按「強制重抓」
        assert scoped == [1], "真的走到 st.cache_data.clear()"
        assert ("^SOX", "60d") in yp._history_fail_cooldown, "前提：強制重抓清不到冷卻"
        assert ddf.fetch_single("^SOX") is None               # 冷卻期內：照舊回 None、不打上游
        assert fake.n("^SOX") - base == 1
        fake.mode = "ok"                                        # 上游恢復
        clock["now"] += FAIL_COOLDOWN_SEC                       # 冷卻期過
        got = ddf.fetch_single("^SOX")
        assert got is not None, "修前：強制重抓時回的 None 又被凍 1 小時"
        pd.testing.assert_frame_equal(got, _fs_expected("^SOX"))


def _check_fetch_single_exception_not_cached(ddf) -> None:
    """`fetch_single` 本體拋例外 → 回 None（log 同修前）但不入快取；下一次重算。"""
    _fresh(ddf.fetch_single)
    src = {"df": pd.DataFrame({0: [1.0]}, index=pd.DatetimeIndex(["2026-06-01"]))}   # 非字串欄名 → .lower() 拋

    def _hist(sym, period="60d"):
        return src["df"].copy()
    _hist.with_status = lambda sym, period="60d": (src["df"].copy(), False)
    _hist.clear = lambda: None
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(YP, "cached_history", _hist)
        assert ddf.fetch_single("^TNX") is None
        src["df"] = _ok_frame("^TNX")
        got = ddf.fetch_single("^TNX")
    assert got is not None, "修前：例外那一次的 None 被凍 1 小時"
    pd.testing.assert_frame_equal(got, _fs_expected("^TNX"))


def _check_fetch_single_no_data_cached(yp, ddf, fake, clock) -> None:
    """真的沒資料 → 回 None、照舊快取（同修前）。"""
    _fresh(yp.cached_history, ddf.fetch_single)
    with _route(yp):
        fake.mode, fake.per = "no_data", {}
        base = fake.n("AAPL")
        assert ddf.fetch_single("AAPL") is None
        fake.mode = "ok"
        clock["now"] += 100 * FAIL_COOLDOWN_SEC
        for _ in range(3):
            assert ddf.fetch_single("AAPL") is None
        assert fake.n("AAPL") - base == 1, "照舊快取"


def _check_dxy_chain(yp, ddf, fake, clock) -> None:
    """DXY 備援鏈（DX-Y.NYB → DX=F → UUP）：全空且有一檔失敗 → 不入快取；恢復後取得第一順位。"""
    _fresh(yp.cached_history, ddf.fetch_single)
    with _route(yp):
        fake.per = {"DX-Y.NYB": "net_down", "DX=F": "no_data", "UUP": "timeout"}
        start = len(fake.calls)
        assert ddf.fetch_single("DX-Y.NYB") is None
        assert [c[0] for c in fake.calls[start:]] == ["DX-Y.NYB", "DX=F", "UUP"]
        fake.per = {"DX-Y.NYB": "ok", "DX=F": "no_data", "UUP": "ok"}
        clock["now"] += FAIL_COOLDOWN_SEC
        got = ddf.fetch_single("DX-Y.NYB")
        assert got is not None, "修前：備援鏈全失敗的 None 凍 1 小時"
        pd.testing.assert_frame_equal(got, _fs_expected("DX-Y.NYB"))


def _check_fetch_single_never_raises(yp, ddf, fake) -> None:
    """回傳契約：任何失敗都回 None，不往外拋。"""
    _fresh(yp.cached_history, ddf.fetch_single)
    with _route(yp):
        for i, mode in enumerate(["net_down", "rate_limited", "no_data", "empty", "none"]):
            fake.mode, fake.per = mode, {}
            try:
                out = ddf.fetch_single(f"SYM{i}")
            except Exception as e:  # noqa: BLE001
                raise AssertionError(f"{mode}: fetch_single 不該拋：{e!r}") from e
            assert out is None, mode


def _check_fetch_single_logs_unchanged(yp, ddf, fake, capsys) -> None:
    """失敗那條路 `fetch_single` 自己的 log 同修前（修前這條路不印任何字；`cached_history` 印自己的）。"""
    _fresh(yp.cached_history, ddf.fetch_single)
    with _route(yp):
        fake.mode, fake.per = "net_down", {}
        capsys.readouterr()
        assert ddf.fetch_single("^IXIC") is None
        out = capsys.readouterr().out
    assert "[yf_proxy.history] ^IXIC: ConnectionError: simulated: network down" in out
    assert "[yf:^IXIC]" not in out, out


def _check_streak_capped(fcm) -> None:
    """D2-f20：遞增退避的「連續失敗次數」表有上限（`_GEN_MAX_ENTRIES`），逐出最早者；
    被逐出的鍵下一波失敗從基準冷卻重算（長時間斷線、大量不同鍵時記憶體不無限成長）。"""
    now = {"t": 1000.0}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fcm, "time", types.SimpleNamespace(monotonic=lambda: now["t"]))
        c = fcm.FailCooldown(seconds=10.0, max_seconds=80.0)
        # 批 FC（2026-10-01）：每波冷卻一過期就再失敗（原為每次 +100 秒 —— D2-f38 之後
        # 「冷卻結束後沉寂 ≥ max_seconds」會讓連續次數歸零，那樣就測不到「被逐出才歸零」）。
        for w in (10, 20, 40):                                 # "old" 連續 3 波失敗 → 冷卻 40 秒
            hit, g = c.begin("old")
            assert hit is fcm.NO_HIT
            c.fail("old", g, "x")
            now["t"] += w
        cap = fcm._GEN_MAX_ENTRIES
        for i in range(cap):                                   # 之後 cap 個別的鍵各失敗一次
            _hit, g = c.begin(i)
            c.fail(i, g, "y")
        assert len(c._streak) == cap, f"上限 {cap}：實得 {len(c._streak)}"
        assert "old" not in c._streak and 0 in c._streak and cap - 1 in c._streak, "逐出最早插入者"
        hit, g = c.begin("old")
        assert hit is fcm.NO_HIT
        c.fail("old", g, "z")
        now["t"] += 10
        assert c.begin("old")[0] is fcm.NO_HIT, "被逐出的鍵從基準 10 秒重算（未逐出會是 80 秒）"


def _check_cache_layer_applies_proxy(yp) -> None:
    """D2-f20：快取層呼叫 yfinance 的當下已設好 NAS proxy env（成功／失敗／沒資料三條路），呼叫後還原。"""
    _fresh(yp.cached_history)
    purl = "http://nas.example.invalid:3128"
    keys = YP._PROXY_ENV_KEYS
    seen: list = []

    class _T:
        def __init__(self, t):
            self.t = t

        def history(self, period="1mo", raise_errors=False, **_kw):
            seen.append({k: os.environ.get(k) for k in keys})
            if self.t == "FAIL.TW":
                raise requests.exceptions.ConnectionError("down")
            if self.t == "NODATA.TW":
                raise _exc(YFE.YFPricesMissingError, "no data")
            return _ok_frame(self.t)

    before = {k: os.environ.get(k) for k in keys}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(TSF, "_load_proxy_config", lambda: {"http": purl, "https": purl})
        mp.setattr(yfinance, "Ticker", _T)
        for t in ("OK.TW", "FAIL.TW", "NODATA.TW"):
            yp.cached_history(t, period="1y")
            assert seen and seen[-1] == {k: purl for k in keys}, f"{t}：呼叫當下沒走 proxy：{seen[-1:]}"
            assert {k: os.environ.get(k) for k in keys} == before, f"{t}：呼叫後 env 沒還原"
    assert len(seen) == 3


def _check_column_bearing_empty(yp, fake, clock) -> None:
    """D2-f20：yfinance 沒拋、回**帶欄位**的空表 → 回無欄位的 `pd.DataFrame()`（修前契約）、照舊快取、不記退避。"""
    _fresh(yp.cached_history)
    fake.mode, fake.per = "empty", {}
    base = fake.n("8888.TW")
    out = yp.cached_history("8888.TW", period="1y")
    _assert_bare_empty(out)
    assert list(out.columns) == []
    fake.mode = "ok"
    clock["now"] += 100 * FAIL_COOLDOWN_SEC
    _assert_bare_empty(yp.cached_history("8888.TW", period="1y"))
    assert fake.n("8888.TW") - base == 1 and ("8888.TW", "1y") not in yp._history_fail_cooldown


def _check_cooldown_key(yp, fake, clock) -> None:
    """D2-f20：冷卻鍵 ＝ (ticker, period) —— 同檔別的區間、別檔同區間照常抓；只有失敗的那一組在冷卻。"""
    _fresh(yp.cached_history)
    fake.mode, fake.per = "net_down", {}
    start = len(fake.calls)
    df, failed = yp.cached_history.with_status("2330.TW", "1y")
    assert failed is True
    fake.mode = "ok"
    pd.testing.assert_frame_equal(yp.cached_history("2330.TW", period="5d"), _ok_frame("2330.TW"))
    pd.testing.assert_frame_equal(yp.cached_history("2317.TW", period="1y"), _ok_frame("2317.TW"))
    df, failed = yp.cached_history.with_status("2330.TW", "1y")
    _assert_bare_empty(df)
    assert failed is True
    assert [(t, p) for t, p, _ in fake.calls[start:]] == [("2330.TW", "1y"), ("2330.TW", "5d"), ("2317.TW", "1y")]
    clock["now"] += FAIL_COOLDOWN_SEC
    pd.testing.assert_frame_equal(yp.cached_history("2330.TW", period="1y"), _ok_frame("2330.TW"))


def _check_cooldown_capacity(yp, fake, clock, n: int = 65) -> None:
    """批 D3d N1：同一冷卻期內 n 個 (ticker, period) 都抓取失敗，連掃 3 輪 —— 第二、三輪上游 0 次
    （n ≤ 成功快取上限 200；修前這些失敗被當成「沒資料」存進上限 200 的成功快取，同樣 0 次）。"""
    _fresh(yp.cached_history)
    fake.mode, fake.per = "net_down", {}
    tickers = [f"{1000 + i}.TW" for i in range(n)]
    rounds: list = []
    for _ in range(3):
        start = len(fake.calls)
        for t in tickers:
            _assert_bare_empty(yp.cached_history(t, period="1y"))
        rounds.append(len(fake.calls) - start)
        clock["now"] += 1                                     # 仍在同一冷卻期
    assert rounds == [n, 0, 0], f"n={n}：三輪各打上游 {rounds} 次（冷卻表容量不足會一邊記一邊逐出）"


_COPY_SEQ = iter(range(10**9))


def _fresh_copy(mod: types.ModuleType) -> types.ModuleType:
    """同一份原始碼另建一個模組（新模組名 → `st.cache_data` 在第一次呼叫時才建新的儲存）。"""
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    return _load(src, f"_copy_d3d_{next(_COPY_SEQ)}_{mod.__name__.rsplit('.', 1)[-1]}", mod.__file__)


def _check_fetch_single_ttl_exact(ddf) -> None:
    """D2-f45（2026-10-01）：快取層實際生效的參數＝`ttl` 3600 秒、`max_entries` 無上限、不顯示 spinner。

    讀 streamlit 掛在 `CachedFunc` 上的設定（`_info`），突變體（原始碼字面替換後另建的模組）一樣適用 ——
    故 TTL 改成 59 分鐘這種落在行為測試 31～61 分鐘窗內的突變也擋得住。"""
    info = ddf._fetch_single_cached._info
    assert (info.ttl, info.max_entries, info.show_spinner) == (3600, None, False), \
        f"_fetch_single_cached 快取參數漂移：ttl={info.ttl!r} max_entries={info.max_entries!r} show_spinner={info.show_spinner!r}"


def _check_fetch_single_ttl(ddf) -> None:
    """D2-f15 快取層 `_fetch_single_cached` 的 TTL ＝ 1 小時（行為）：第 31 分鐘（pkl 的 30 分鐘已過）仍由
    `fetch_single` 自己的快取回應、不再往下問 K 線層；第 61 分鐘才重算。

    時鐘：換 streamlit 建 TTLCache 時讀的 `cache_utils.TTLCACHE_TIMER` —— 只對**第一次呼叫才建儲存**的
    模組有效，故真模組一律用 `_fresh_copy` 的同源副本（突變體本來就是新模組）。下層換成不快取的
    `cached_history` 替身，才看得到每一次重算。"""
    from streamlit.runtime.caching import cache_utils
    if ddf is DDF:
        ddf = _fresh_copy(DDF)
    now = {"t": 10_000.0}
    calls: list = []

    def _hist(sym, period="60d"):
        calls.append(sym)
        return _ok_frame(sym)
    _hist.with_status = lambda sym, period="60d": (_hist(sym, period), False)
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(cache_utils, "TTLCACHE_TIMER", lambda: now["t"])
            mp.setattr(YP, "cached_history", _hist)
            CL._pkl_clear_all()
            pd.testing.assert_frame_equal(ddf.fetch_single("^DJI"), _fs_expected("^DJI"))
            assert calls == ["^DJI"]
            now["t"] += 31 * 60
            CL._pkl_clear_all()                                  # pkl 的 30 分鐘 TTL 已過
            pd.testing.assert_frame_equal(ddf.fetch_single("^DJI"), _fs_expected("^DJI"))
            assert calls == ["^DJI"], "第 31 分鐘：仍在 fetch_single 自己的 1 小時快取裡（不重算）"
            now["t"] += 30 * 60
            CL._pkl_clear_all()
            pd.testing.assert_frame_equal(ddf.fetch_single("^DJI"), _fs_expected("^DJI"))
            assert calls == ["^DJI", "^DJI"], "第 61 分鐘：1 小時到期、重算"
    finally:
        _clear(ddf.fetch_single)


# ══════════════════════════════════════════════════════════════════
# D2-f16 ① 吞成空表的抓取失敗：不入快取、冷卻、恢復；真的沒資料照舊
# ══════════════════════════════════════════════════════════════════
class TestD2f16SwallowedFailureNotCached:
    @pytest.mark.parametrize("mode", ["net_down", "timeout", "yahoo_down", "yahoo_down_legacy"])
    def test_swallowed_error_backs_off_then_recovers(self, yfh, fc_clock, capsys, mode):
        _check_swallowed_error_not_cached(YP, yfh, fc_clock, mode)
        assert all(c[2] is True for c in yfh.calls), "一律以 raise_errors=True 呼叫"
        out = capsys.readouterr().out
        assert "[yf_proxy.history] 2330.TW: " in out, "失敗 log 同 #741 格式"

    def test_persistent_failure_hits_upstream_once_per_cooldown(self, yfh, fc_clock):
        yfh.mode = "net_down"
        for i in range(1, 4):
            for _ in range(4):
                _assert_bare_empty(YP.cached_history("2330.TW", period="1y"))
            assert yfh.n("2330.TW") == i, "持續失敗：每個冷卻期只打 1 次（不入快取、也不轟炸）"
            fc_clock["now"] += FAIL_COOLDOWN_SEC

    def test_rate_limited_still_failure(self, yfh, fc_clock):
        _check_swallowed_error_not_cached(YP, yfh, fc_clock, "rate_limited")

    def test_rate_limit_never_classified_as_no_data(self):
        _check_rate_limit_never_no_data(YP)

    @pytest.mark.parametrize("mode", ["no_data", "tz_missing", "bad_period", "legacy_no_data", "empty", "none"])
    def test_genuinely_no_data_still_cached(self, yfh, fc_clock, mode):
        _check_no_data_cached(YP, yfh, fc_clock, mode)

    def test_with_status(self, yfh, fc_clock):
        _check_with_status(YP, yfh, fc_clock)

    def test_public_interface_kept(self):
        assert PX.cached_history is YP.cached_history, "套件層轉發（caller 的 import 路徑）拿到同一支"
        assert callable(YP.cached_history.clear) and callable(YP.cached_history.with_status)
        import inspect
        sig = inspect.signature(YP.cached_history)
        assert list(sig.parameters) == ["ticker", "period"] and sig.parameters["period"].default == "1y"

    def test_clear_resets_cache_and_backoff(self, yfh, fc_clock):
        YP.cached_history("2330.TW", period="1y")                # 失敗 → 退避中
        yfh.mode = "ok"
        YP.cached_history.clear()
        pd.testing.assert_frame_equal(YP.cached_history("2330.TW", period="1y"), _ok_frame("2330.TW"))
        assert yfh.n("2330.TW") == 2, "clear() 清掉退避紀錄 → 立刻重打"

    def test_legacy_signature_falls_back(self, fc_clock):
        _check_legacy_signature_fallback(YP)

    def test_unrelated_typeerror_not_retried(self, fc_clock):
        _check_unrelated_typeerror_not_retried(YP)

    def test_deprecation_warning_as_error_falls_back(self):
        _check_deprecation_as_error_falls_back(YP)

    def test_deprecation_warning_not_escalated_uses_strict_call(self):
        calls: list = []

        class _T:
            def history(self, period="1mo", raise_errors=False):
                calls.append(raise_errors)
                raise requests.exceptions.ConnectionError("down")

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(requests.exceptions.ConnectionError):
                YP._history_or_raise(_T(), "X", "1y")
        assert calls == [True]


# ══════════════════════════════════════════════════════════════════
# D2-f16 ② 真的 yfinance（已安裝版本）前提：只換最底層 HTTP 與時區查詢
# ══════════════════════════════════════════════════════════════════
class _Resp:
    def __init__(self, status: int, body=None, text=None):
        self.status_code = status
        self.text = text if text is not None else json.dumps(body)
        self.url = "https://query2.finance.yahoo.com/v8/finance/chart/X"
        self.headers: dict = {}

    def json(self):
        return json.loads(self.text)


def _chart_ok(sym: str, period: str, n: int = 40) -> dict:
    base = 1_780_000_000 - (1_780_000_000 % 86400) + 3600          # 01:00 UTC ＝ 台北 09:00
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


@pytest.fixture
def real_yf(monkeypatch, fc_clock):
    """已安裝的**真** yfinance：只換 `YfData.get`（HTTP）與 `TickerBase._get_ticker_tz`（＝時區已快取）。"""
    from yfinance import base as yfb
    from yfinance import data as yfd
    assert hasattr(yfd, "YfData") and hasattr(yfd.YfData, "get"), \
        "yfinance 內部結構變了（找不到 YfData.get）—— D2-f16 前提需重新驗證"
    assert hasattr(yfb.TickerBase, "_get_ticker_tz"), "yfinance 內部結構變了（找不到 _get_ticker_tz）"
    state = {"mode": "ok", "urls": []}

    def _get(self, url, *a, **k):
        state["urls"].append(url)
        p = k.get("params") or {}
        mode = state["mode"]
        if mode == "down":
            raise requests.exceptions.ConnectionError("simulated: network down")
        if mode == "404":
            return _Resp(404, _CHART_404)
        if mode == "html":
            return _Resp(503, text="<html><body>503 Service Unavailable</body></html>")
        if mode == "maint":                                   # Yahoo 維護頁（yfinance 認 "Will be right back"）
            return _Resp(200, text="<html><body>Will be right back ... Thank you for your patience.</body></html>")
        return _Resp(200, _chart_ok(url.rsplit("/", 1)[-1], p.get("range", "1y")))

    monkeypatch.setattr(yfd.YfData, "get", _get)
    monkeypatch.setattr(yfb.TickerBase, "_get_ticker_tz", lambda self, *a, **k: "Asia/Taipei")
    return state


@pytest.mark.filterwarnings("ignore:'raise_errors' deprecated:DeprecationWarning")
class TestRealYfinancePremise:
    @pytest.mark.parametrize("mode", ["down", "html", "maint"])
    def test_premise_default_call_swallows_network_error(self, real_yf, mode):
        """修前那種呼叫（沒帶 raise_errors）：網路錯誤／非 JSON／維護頁被吞成空表，不拋 —— D2-f16 的根因。"""
        real_yf["mode"] = mode
        df = yfinance.Ticker("PRE1.TW").history(period="1y")
        assert isinstance(df, pd.DataFrame) and df.empty
        assert real_yf["urls"], "確實打過（替身）上游"

    @pytest.mark.parametrize("mode,exc", [("down", requests.exceptions.ConnectionError),
                                          ("html", ValueError),
                                          ("maint", (RuntimeError, getattr(YFE, "YFDataException", RuntimeError)))])
    def test_premise_raise_errors_surfaces_it(self, real_yf, mode, exc):
        real_yf["mode"] = mode
        with pytest.raises(exc):
            YP._history_or_raise(yfinance.Ticker("PRE2.TW"), "PRE2.TW", "1y")

    def test_premise_yahoo_no_data_is_typed(self, real_yf):
        real_yf["mode"] = "404"
        assert yfinance.Ticker("PRE3.TW").history(period="1y").empty
        assert YP._history_or_raise(yfinance.Ticker("PRE3.TW"), "PRE3.TW", "1y") is None

    @pytest.mark.parametrize("period", ["1y", "60d", "9mo"])
    def test_premise_success_identical(self, real_yf, period):
        a = yfinance.Ticker("PRE4.TW").history(period=period)
        b = YP._history_or_raise(yfinance.Ticker("PRE4.TW"), "PRE4.TW", period)
        assert not a.empty
        pd.testing.assert_frame_equal(a, b)
        assert repr(a) == repr(b) and a.attrs == b.attrs

    def test_end_to_end_backoff_and_recovery(self, real_yf, fc_clock):
        real_yf["mode"] = "down"
        df, failed = YP.cached_history.with_status("PRE5.TW", "60d")
        _assert_bare_empty(df)
        assert failed is True
        assert DDF.fetch_single("PRE5.TW") is None
        n = len(real_yf["urls"])
        real_yf["mode"] = "ok"
        assert DDF.fetch_single("PRE5.TW") is None and len(real_yf["urls"]) == n, "冷卻期內不打上游"
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        got = DDF.fetch_single("PRE5.TW")
        assert got is not None and len(got) == 40 and list(got.columns)[:5] == \
            ["open", "high", "low", "close", "volume"]
        assert got.index.tz is None
        real_yf["mode"] = "404"
        df, failed = YP.cached_history.with_status("PRE6.TW", "60d")
        _assert_bare_empty(df)
        assert failed is False and ("PRE6.TW", "60d") not in YP._history_fail_cooldown

    def test_end_to_end_maintenance_page_is_failure(self, real_yf, fc_clock):
        """N4(b)：Yahoo 維護頁 ＝ 抓取失敗（不是「沒資料」）—— 不入快取、冷卻期內不重打、期滿即取得資料。"""
        real_yf["mode"] = "maint"
        df, failed = YP.cached_history.with_status("PRE7.TW", "1y")
        _assert_bare_empty(df)
        assert failed is True and ("PRE7.TW", "1y") in YP._history_fail_cooldown
        n = len(real_yf["urls"])
        real_yf["mode"] = "ok"
        df, failed = YP.cached_history.with_status("PRE7.TW", "1y")
        assert failed is True and len(real_yf["urls"]) == n, "冷卻期內不打上游"
        fc_clock["now"] += FAIL_COOLDOWN_SEC
        df, failed = YP.cached_history.with_status("PRE7.TW", "1y")
        assert failed is False and len(df) == 40, "修前（若歸成沒資料）：空表凍 1 小時"


# ══════════════════════════════════════════════════════════════════
# D2-f15 fetch_single：失敗不入快取；真的沒資料照舊
# ══════════════════════════════════════════════════════════════════
class TestD2f15FetchSingle:
    def test_failure_not_cached_recovers_after_cooldown(self, yfh, fc_clock):
        _check_fetch_single_failure_not_cached(YP, DDF, yfh, fc_clock)

    def test_force_refresh_in_cooldown_no_longer_freezes_none(self, yfh, fc_clock):
        _check_fetch_single_force_refresh_in_cooldown(YP, DDF, yfh, fc_clock)

    def test_exception_not_cached(self):
        _check_fetch_single_exception_not_cached(DDF)

    def test_exception_log_unchanged(self, capsys):
        src = pd.DataFrame({0: [1.0]}, index=pd.DatetimeIndex(["2026-06-01"]))

        def _hist(sym, period="60d"):
            return src.copy()
        _hist.with_status = lambda sym, period="60d": (src.copy(), False)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(YP, "cached_history", _hist)
            logged: list = []
            mp.setattr(DDF, "_prov_log", lambda *a: logged.append(a))
            capsys.readouterr()
            assert DDF.fetch_single("^VIX") is None
        assert "[yf:^VIX] 'int' object has no attribute 'lower'" in capsys.readouterr().out
        assert logged == [("fetch_single", "yf_proxy.cached_history", "^VIX", "None:exc:AttributeError")]

    def test_no_data_still_cached(self, yfh, fc_clock):
        _check_fetch_single_no_data_cached(YP, DDF, yfh, fc_clock)

    def test_all_empty_after_dropping_nan_close_still_cached(self, fc_clock):
        """有回 K 線、但 close 全是 NaN（清掉後變空）→ 回 None、照舊快取（不是抓取失敗）。"""
        calls: list = []
        nan = _ok_frame("NAN.TW")
        nan["Close"] = np.nan

        def _hist(sym, period="60d"):
            calls.append(sym)
            return nan.copy()
        _hist.with_status = lambda sym, period="60d": (_hist(sym, period), False)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(YP, "cached_history", _hist)
            for _ in range(3):
                assert DDF.fetch_single("NAN.TW") is None
        assert calls == ["NAN.TW"]

    def test_dxy_chain_failure_not_cached(self, yfh, fc_clock):
        _check_dxy_chain(YP, DDF, yfh, fc_clock)

    def test_dxy_chain_all_no_data_cached(self, yfh, fc_clock):
        yfh.mode = "no_data"
        assert DDF.fetch_single("DX-Y.NYB") is None
        yfh.mode = "ok"
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        assert DDF.fetch_single("DX-Y.NYB") is None
        assert [c[0] for c in yfh.calls] == ["DX-Y.NYB", "DX=F", "UUP"], "三檔都真的沒資料 → 照舊快取"

    def test_dxy_chain_fallback_success_cached(self, yfh, fc_clock):
        yfh.per = {"DX-Y.NYB": "net_down", "DX=F": "ok"}
        pd.testing.assert_frame_equal(DDF.fetch_single("DX-Y.NYB"), _fs_expected("DX=F"))
        yfh.per = {"DX-Y.NYB": "ok", "DX=F": "ok"}
        fc_clock["now"] += 100 * FAIL_COOLDOWN_SEC
        pd.testing.assert_frame_equal(DDF.fetch_single("DX-Y.NYB"), _fs_expected("DX=F"))
        assert [c[0] for c in yfh.calls] == ["DX-Y.NYB", "DX=F"], "成功（含備援命中）照舊快取 1 小時，同修前"

    def test_never_raises(self, yfh):
        _check_fetch_single_never_raises(YP, DDF, yfh)

    def test_failure_log_unchanged(self, yfh, capsys):
        _check_fetch_single_logs_unchanged(YP, DDF, yfh, capsys)

    def test_without_with_status_treated_as_not_failed(self, fc_clock):
        """`cached_history` 被換成沒有 `.with_status` 的純函式 → 一律當非失敗、照舊快取（相容）。"""
        calls: list = []

        def _hist(sym, period="60d"):
            calls.append(sym)
            return pd.DataFrame()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(YP, "cached_history", _hist)
            for _ in range(2):
                assert DDF.fetch_single("PLAIN.TW") is None
        assert calls == ["PLAIN.TW"]

    def test_interface_kept(self):
        import inspect

        import src.data.daily as DD
        import src.services as SV
        sig = inspect.signature(DDF.fetch_single)
        assert list(sig.parameters) == ["symbol", "period"] and sig.parameters["period"].default == "60d"
        assert DD.fetch_single is DDF.fetch_single and SV.fetch_single is DDF.fetch_single
        assert callable(DDF.fetch_single.clear)

    def test_clear(self, yfh):
        yfh.mode = "ok"
        DDF.fetch_single("^DJI")
        CL._pkl_clear_all()
        YP.cached_history.clear()
        DDF.fetch_single("^DJI")
        assert yfh.n("^DJI") == 1, "成功照舊快取"
        CL._pkl_clear_all()
        YP.cached_history.clear()
        DDF.fetch_single.clear()
        DDF.fetch_single("^DJI")
        assert yfh.n("^DJI") == 2, ".clear() 清掉 fetch_single 那層"


# ══════════════════════════════════════════════════════════════════
# 修前 vs 修後：修前真的有這三個破口；成功與「真的沒資料」與修前逐字相同（所有呼叫端）
# ══════════════════════════════════════════════════════════════════
class TestAgainstPrefixModel:
    def test_prefix_caches_swallowed_failure(self, yfh, fc_clock, prefix):
        with pytest.raises(AssertionError):
            _check_swallowed_error_not_cached(prefix.yp, yfh, fc_clock)

    def test_prefix_fetch_single_freezes_none(self, yfh, fc_clock, prefix):
        with pytest.raises(AssertionError):             # 修前 fetch_single ＋ 修後 cached_history：仍凍 None
            _check_fetch_single_failure_not_cached(YP, prefix.ddf, yfh, fc_clock)
        yfh.calls.clear()
        with pytest.raises(AssertionError):             # 冷卻期內強制重抓 → None 再凍 1 小時
            _check_fetch_single_force_refresh_in_cooldown(YP, prefix.ddf, yfh, fc_clock)
        yfh.calls.clear()
        with pytest.raises(AssertionError):
            _check_fetch_single_exception_not_cached(prefix.ddf)

    @pytest.mark.parametrize("mode", ["no_data", "tz_missing", "bad_period", "legacy_no_data", "empty", "none"])
    def test_no_data_same_as_prefix(self, yfh, fc_clock, prefix, mode):
        _check_no_data_cached(prefix.yp, yfh, fc_clock, mode)      # 修前模型同樣通過 ＝ 行為相同
        prefix_calls = list(yfh.calls)
        yfh.calls.clear()
        _check_no_data_cached(YP, yfh, fc_clock, mode)
        assert [c[:2] for c in yfh.calls] == [c[:2] for c in prefix_calls]
        if mode == "no_data":
            yfh.calls.clear()
            _check_fetch_single_no_data_cached(prefix.yp, prefix.ddf, yfh, fc_clock)

    @pytest.mark.parametrize("mode", ["ok", "net_down", "no_data", "empty", "none", "rate_limited"])
    def test_cached_history_first_call_same_as_prefix(self, yfh, prefix, mode):
        """第一次呼叫（任何世界）的回傳與修前逐字相同；差別只在之後要不要重抓。"""
        yfh.mode = mode
        old = prefix.yp.cached_history("1234.TW", period="1y")
        new = YP.cached_history("1234.TW", period="1y")
        pd.testing.assert_frame_equal(new, old)
        assert repr(new) == repr(old) and new.attrs == old.attrs
        if mode == "ok":
            pd.testing.assert_frame_equal(new, _ok_frame("1234.TW"))
        else:
            _assert_bare_empty(new)

    def test_fetch_single_success_same_as_prefix(self, yfh, prefix):
        from src.services.daily_checklist import INTL_MAP, TECH_MAP, TW_MAP
        yfh.mode = "ok"
        syms = [(s, "60d") for s in list(INTL_MAP.values()) + list(TECH_MAP.values())]
        syms += [(s, "9mo") for s in TW_MAP.values()]
        new = {s: DDF.fetch_single(s, period=p) for s, p in syms}
        _fresh(YP.cached_history)
        with _route(prefix.yp):
            old = {s: prefix.ddf.fetch_single(s, period=p) for s, p in syms}
        for s, _p in syms:
            pd.testing.assert_frame_equal(new[s], old[s])
            assert repr(new[s]) == repr(old[s]) and new[s].attrs == old[s].attrs, s

    def test_fetch_macro_bundle_same_as_prefix(self, yfh, prefix):
        """L3 呼叫端（v1 總經頁、v2 更新、排程腳本都走它）：注入修後／修前 `fetch_single` 的結果逐項相同。"""
        from src.services.daily_checklist import INTL_MAP, TECH_MAP, TW_MAP
        from src.services.macro_fetch_orchestrator import fetch_macro_bundle
        yfh.per = {"^SOX": "net_down", "TSM": "no_data"}          # 混合世界：部分失敗、部分真的沒資料
        yfh.mode = "ok"

        def _bundle(fs):
            b = fetch_macro_bundle(load_heavy=False, prev_cl_data={}, fm_token="", li_token="",
                                   bps_session=object(), intl_map=INTL_MAP, tw_map=TW_MAP, tech_map=TECH_MAP,
                                   fetch_single=fs, fetch_institutional=lambda: None,
                                   fetch_margin_balance=lambda: None, fetch_adl=lambda **k: None)
            return {k: b[k] for k in ("intl_raw", "tw_raw", "tech_raw")}

        new = _bundle(DDF.fetch_single)
        _fresh(YP.cached_history)
        with _route(prefix.yp):
            old = _bundle(prefix.ddf.fetch_single)
        assert new.keys() == old.keys()
        for k in new:
            assert new[k].keys() == old[k].keys(), k
            for name in new[k]:
                a, b = new[k][name], old[k][name]
                if a is None or b is None:
                    assert a is None and b is None, (k, name)
                else:
                    pd.testing.assert_frame_equal(a, b)
        assert new["intl_raw"]["費城半導體 SOX"] is None and new["tech_raw"]["台積電 ADR"] is None

    def test_fetch_flow_snapshot_same_as_prefix(self, yfh, prefix):
        yfh.mode = "ok"
        _fresh(DDF.fetch_flow_snapshot)
        new = DDF.fetch_flow_snapshot()
        _fresh(YP.cached_history, DDF.fetch_single)
        with _route(prefix.yp):
            old = prefix.ddf.fetch_flow_snapshot()
        assert new.keys() == old.keys() and len(new) > 0
        for name in new:
            pd.testing.assert_frame_equal(new[name], old[name])
        _clear(DDF.fetch_flow_snapshot)

    def test_picker_fetch_stock_history_1y_same_as_prefix(self, yfh, prefix, monkeypatch):
        """L1 `fetch_stock_history_1y`（v1 選股網、v2 RS 卡共用）：成功回傳 (df, 代號) 與修前逐字相同。"""
        from src.data.stock.picker_fetcher import fetch_stock_history_1y
        import src.data.core.data_loader as DL
        fixed = pd.Timestamp("2026-09-28T01:02:03", tz="UTC")
        monkeypatch.setattr(pd.Timestamp, "now", classmethod(lambda cls, tz=None: fixed))
        monkeypatch.setattr(DL, "_fetch_finmind_price_raw", lambda *a, **k: pd.DataFrame())
        yfh.per = {"2330.TW": "ok", "6488.TW": "no_data", "6488.TWO": "ok"}
        new = [fetch_stock_history_1y(s) for s in ("2330", "6488")]
        _fresh(YP.cached_history)
        with _route(prefix.yp):
            old = [fetch_stock_history_1y(s) for s in ("2330", "6488")]
        for (df_n, r_n), (df_o, r_o) in zip(new, old):
            assert r_n == r_o
            pd.testing.assert_frame_equal(df_n, df_o)
            assert df_n.attrs == df_o.attrs


# ══════════════════════════════════════════════════════════════════
# D2-f20 只補測試（對應突變見 TestMutations）
# ══════════════════════════════════════════════════════════════════
class TestD2f20StreakCap:
    def test_streak_table_capped_and_evicts_oldest(self):
        _check_streak_capped(FC)


class TestD2f20CachedHistoryBehaviour:
    def test_cache_layer_applies_proxy(self):
        _check_cache_layer_applies_proxy(YP)

    def test_column_bearing_empty(self, yfh, fc_clock):
        _check_column_bearing_empty(YP, yfh, fc_clock)

    def test_cooldown_key_is_ticker_and_period(self, yfh, fc_clock):
        _check_cooldown_key(YP, yfh, fc_clock)


# ══════════════════════════════════════════════════════════════════
# 批 D3d 複驗補修（2026-09-29）：N1 冷卻表容量、N4(a) fetch_single 的 TTL（N4(b) 維護頁見上方
# TestD2f16*／TestRealYfinancePremise 的 yahoo_down／maint 情境）
# ══════════════════════════════════════════════════════════════════
class TestN1CooldownCapacity:
    """QA 重現：同一冷卻期內連掃 3 輪，65 個失敗鍵時上游呼叫 修後（冷卻表上限 64）65／65／65、修前 65／0／0。"""

    @pytest.mark.parametrize("n", [64, 65, 200])
    def test_failed_keys_no_upstream_in_rounds_2_and_3(self, yfh, fc_clock, n):
        _check_cooldown_capacity(YP, yfh, fc_clock, n)

    @pytest.mark.parametrize("n", [64, 65, 200])
    def test_same_upstream_calls_as_prefix(self, yfh, fc_clock, prefix, n):
        _check_cooldown_capacity(prefix.yp, yfh, fc_clock, n)       # 修前：吞掉的錯誤進成功快取（上限 200）
        prefix_calls = [c[:2] for c in yfh.calls]
        yfh.calls.clear()
        _check_cooldown_capacity(YP, yfh, fc_clock, n)
        assert [c[:2] for c in yfh.calls] == prefix_calls

    def test_bound_shared_with_success_cache(self):
        assert YP._history_fail_cooldown.max_entries == YP._HISTORY_CACHE_MAX_ENTRIES == 200

    def test_reconcile_like_scan_over_64_keys(self, yfh, fc_clock, monkeypatch):
        """前進式驗證對帳（`forward_test_service.reconcile_all`）的取數路徑：逐檔 `.TW`＋`.TWO` 備援 ——
        40 檔 ＝ 80 個失敗鍵（> 64）。同一冷卻期內第二輪 Yahoo 0 次（修前也是 0）。"""
        import src.data.core.data_loader as DL
        from src.data.stock.picker_fetcher import fetch_stock_history_1y
        monkeypatch.setattr(DL, "_fetch_finmind_price_raw", lambda *a, **k: pd.DataFrame())
        yfh.mode = "net_down"
        codes = [str(2000 + i) for i in range(40)]
        for rnd in range(2):
            start = len(yfh.calls)
            assert [fetch_stock_history_1y(c) for c in codes] == [(None, None)] * len(codes)
            assert len(yfh.calls) - start == (80 if rnd == 0 else 0), f"第 {rnd + 1} 輪"
            fc_clock["now"] += 1


class TestN4aFetchSingleTtl:
    def test_ttl_is_one_hour(self):
        _check_fetch_single_ttl(DDF)

    def test_decorator_pinned_verbatim(self):
        """D2-f45（2026-10-01）：比照 #741 對 `yf_proxy._cached_history_cached` 的逐字斷言。

        上一條行為測試只把 TTL 夾在 31～61 分鐘之間 —— TTL 改成 59 分鐘的突變照樣存活。
        這裡逐字釘住裝飾器（修前掛在 `fetch_single` 上的那一行原樣搬下來），並確認 `TTL_1HOUR` 仍是 3600 秒。"""
        tree = ast.parse(pathlib.Path(DDF.__file__).read_text(encoding="utf-8"))
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        assert [ast.unparse(d) for d in fns["_fetch_single_cached"].decorator_list] == \
            ["st.cache_data(ttl=TTL_1HOUR, show_spinner=False)"], "快取層參數同修前（逐字）"
        assert fns["fetch_single"].decorator_list == [], "外層不快取 —— 失敗才不會被凍住"
        assert TTL_1HOUR == 3600, "TTL_1HOUR 的值同修前"
        _check_fetch_single_ttl_exact(DDF)


# ══════════════════════════════════════════════════════════════════
# 隨機操作序列 × 獨立參考模型（property-based 的精神；固定 seed、不引入新依賴，同 #741 測試手法）
# ══════════════════════════════════════════════════════════════════
_FAILS = ("net_down", "timeout", "rate_limited", "yahoo_down", "yahoo_down_legacy")   # 抓取失敗：不入快取、記冷卻
_NO_DATA = ("no_data", "tz_missing", "bad_period", "legacy_no_data", "empty", "none")   # 照舊快取


class _HistoryModel:
    """`cached_history` 應有的語意（獨立寫出，不讀被測碼）：成功／真的沒資料 → 1 小時快取（測試內不過期）；
    失敗 → 不入快取、`FAIL_COOLDOWN_SEC` 內同鍵回空表且不打上游；任何一次正常回傳清掉該鍵冷卻。"""

    def __init__(self, fake, clock):
        self.fake, self.clock = fake, clock
        self.cache: dict = {}
        self.cool: dict = {}
        self.upstream = 0

    def expire(self) -> None:
        """快取到期／v2「強制重抓」清掉 `st.cache_data`：成功快取清空，冷卻不受影響。"""
        self.cache.clear()

    def call(self, ticker: str, period: str):
        """回 (kind, failed)；kind ∈ {"ok", "empty"}。"""
        key = (ticker, period)
        if key in self.cache:
            return self.cache[key], False
        t0 = self.cool.get(key)
        if t0 is not None and self.clock["now"] - t0 < FAIL_COOLDOWN_SEC:
            return "empty", True
        self.upstream += 1
        mode = self.fake.per.get(ticker, self.fake.mode)
        if mode in _FAILS:
            self.cool[key] = self.clock["now"]
            return "empty", True
        self.cool.pop(key, None)
        self.cache[key] = "ok" if mode == "ok" else "empty"
        return self.cache[key], False


class TestModelBased:
    @pytest.mark.parametrize("seed", range(8))
    def test_cached_history_matches_model(self, yfh, fc_clock, seed):
        import random
        rng = random.Random(seed)
        model = _HistoryModel(yfh, fc_clock)
        keys = [(f"{t}.TW", p) for t in ("A", "B", "C", "D", "E") for p in ("1y", "60d")]
        for step in range(500):
            op = rng.choices(["tick", "mode", "expire", "call"], weights=[3, 2, 1, 8])[0]
            if op == "tick":
                fc_clock["now"] += rng.choice([0, 1, 30, 179, 180, 181, 600])
            elif op == "mode":
                yfh.mode = rng.choice(("ok",) + _FAILS + _NO_DATA)
            elif op == "expire":
                YP._cached_history_cached.clear()
                model.expire()
            else:
                t, p = rng.choice(keys)
                kind, failed = model.call(t, p)
                got, got_failed = YP.cached_history.with_status(t, p)
                where = f"seed={seed} step={step} {t}/{p} mode={yfh.mode}"
                if kind == "ok":
                    pd.testing.assert_frame_equal(got, _ok_frame(t), obj=where)
                else:
                    _assert_bare_empty(got)
                assert got_failed is failed, where
                assert len(yfh.calls) == model.upstream, where

    @pytest.mark.parametrize("seed", range(8))
    def test_fetch_single_matches_model(self, yfh, fc_clock, seed):
        """`fetch_single` 應有的語意：成功與「每一檔都真的沒資料」快取；「全空且至少一檔抓取失敗」不快取。"""
        import random
        rng = random.Random(1000 + seed)
        hist = _HistoryModel(yfh, fc_clock)
        chain = {"DX-Y.NYB": ["DX-Y.NYB", "DX=F", "UUP"]}
        cached: dict = {}                                    # symbol → None | 命中的代號
        upstream_syms = ["^DJI", "DX-Y.NYB", "DX=F", "UUP", "TSM"]
        for step in range(400):
            op = rng.choices(["tick", "mode", "force", "call"], weights=[3, 2, 1, 8])[0]
            if op == "tick":
                fc_clock["now"] += rng.choice([0, 1, 60, 179, 180, 181, 600])
            elif op == "mode":
                yfh.per = {s: rng.choice(("ok", "net_down", "rate_limited", "no_data", "empty"))
                           for s in upstream_syms}
            elif op == "force":                              # v2「強制重抓」：清 pkl 與兩層 st.cache_data，清不到冷卻
                CL._pkl_clear_all()
                DDF._fetch_single_cached.clear()
                YP._cached_history_cached.clear()
                cached.clear()
                hist.expire()
            else:
                sym = rng.choice(["^DJI", "DX-Y.NYB", "TSM"])
                if sym in cached:
                    exp = cached[sym]
                else:
                    exp, failed_any = None, False
                    for s in chain.get(sym, [sym]):
                        kind, failed = hist.call(s, "60d")
                        if kind == "ok":
                            exp = s
                            break
                        failed_any = failed_any or failed
                    if exp is not None or not failed_any:
                        cached[sym] = exp
                got = DDF.fetch_single(sym)
                where = f"seed={seed} step={step} {sym} per={yfh.per}"
                if exp is None:
                    assert got is None, where
                else:
                    pd.testing.assert_frame_equal(got, _fs_expected(exp), obj=where)
                assert len(yfh.calls) == hist.upstream, where


# ══════════════════════════════════════════════════════════════════
# 突變：逐一拿掉每一處修正 → 本檔對應的共用檢查轉紅
# ══════════════════════════════════════════════════════════════════
_YP_STRICT_CALL = "        return tk.history(period=period, raise_errors=True)\n"
_YP_TYPEERROR = ("    except TypeError as _e:\n"
                 "        if \"raise_errors\" not in str(_e):\n"
                 "            raise\n"
                 "        return tk.history(period=period)\n")
_YP_TYPEERROR_MSG = ("        if \"raise_errors\" not in str(_e):\n"
                     "            raise\n")
_YP_DEPRECATION = ("    except DeprecationWarning:\n"
                   "        return tk.history(period=period)\n")
_YP_NO_DATA_BRANCH = ("        if not _is_yf_no_data(_e):\n"
                      "            raise\n")
_YP_BARE_RULE = ("    if type(exc) is Exception:\n"
                 "        return True\n")
_YP_RATE_RULE = ("    if _rate_limited is not None and isinstance(exc, _rate_limited):\n"
                 "        return False\n")
_YP_LAYER_CALL = "        _df = _history_or_raise(yf.Ticker(ticker), ticker, period)\n"
_YP_EMPTY_RULE = ("    if _df is None or _df.empty:\n"
                  "        return pd.DataFrame()\n"
                  "    return _df\n")

_DDF_RAISE_EMPTY = "                raise _SingleFetchFailed(None, f\"抓取失敗:{'、'.join(_failed)}\")\n"
_DDF_RAISE_EXC = "        raise _SingleFetchFailed(None, f'{type(e).__name__}: {e}') from e\n"
_DDF_PASSTHRU = ("    except _SingleFetchFailed:\n"
                 "        raise\n")
_DDF_OUTER = ("    except _SingleFetchFailed as _sf:\n"
              "        return _sf.payload\n")
_DDF_FAILED_APPEND = ("            if _f:\n"
                      "                _failed.append(_sym)\n")

#: 批 FC（2026-10-01）：上限改為 `self._gen_cap`（D2-f47）、逐出時另標記到期 heap 重建（D2-f48）→ 突變點跟著改。
_FC_STREAK_CAP = "        while len(self._streak) > cap:\n"

#: (標籤, 被突變的模組, 替換, 哪一個檢查必須轉紅)
_MUTATIONS = [
    # ── D2-f16 yf_proxy ──
    ("f16_no_raise_errors", "yp", [(_YP_STRICT_CALL, "        return tk.history(period=period)\n")], "swallowed"),
    ("f16_layer_prefix_call", "yp", [(_YP_LAYER_CALL, "        _df = yf.Ticker(ticker).history(period=period)\n")],
     "swallowed"),
    ("f16_no_data_is_failure", "yp", [(_YP_NO_DATA_BRANCH, "        if True:\n            raise\n")], "no_data"),
    ("f16_no_bare_exception_rule", "yp", [(_YP_BARE_RULE, "    if False:\n        return True\n")], "legacy_no_data"),
    ("f16_no_rate_limit_rule", "yp", [(_YP_RATE_RULE, "    if False:\n        return False\n")], "rate_rule"),
    ("f16_no_typeerror_fallback", "yp", [(_YP_TYPEERROR, "")], "legacy_signature"),
    ("f16_typeerror_any_message", "yp", [(_YP_TYPEERROR_MSG, "")], "unrelated_typeerror"),
    ("f16_no_deprecation_fallback", "yp", [(_YP_DEPRECATION, "")], "deprecation"),
    ("f16_status_cooldown_hit_false", "yp", [("        return _hit, True\n", "        return _hit, False\n")],
     "with_status"),
    ("f16_status_fresh_failure_false", "yp",
     [("return _history_fail_cooldown.fail(_key, _gen, pd.DataFrame()), True",
       "return _history_fail_cooldown.fail(_key, _gen, pd.DataFrame()), False")], "with_status"),
    ("f16_status_cooldown_hit_false_via_fetch_single", "yp",
     [("        return _hit, True\n", "        return _hit, False\n")], "force_refresh"),
    ("f16_status_fresh_failure_false_via_fetch_single", "yp",
     [("return _history_fail_cooldown.fail(_key, _gen, pd.DataFrame()), True",
       "return _history_fail_cooldown.fail(_key, _gen, pd.DataFrame()), False")], "fs_failure"),
    # ── D2-f15 daily_data_fetchers ──
    ("f15_failed_empty_cached", "ddf", [(_DDF_RAISE_EMPTY, "                return None\n")], "fs_failure"),
    ("f15_failed_empty_cached_force", "ddf", [(_DDF_RAISE_EMPTY, "                return None\n")], "force_refresh"),
    ("f15_failed_empty_cached_dxy", "ddf", [(_DDF_RAISE_EMPTY, "                return None\n")], "dxy"),
    ("f15_exception_cached", "ddf", [(_DDF_RAISE_EXC, "        return None\n")], "fs_exception"),
    ("f15_ignore_status", "ddf", [("    return _ws(sym, period=period)\n", "    return _ws(sym, period=period)[0], False\n")],
     "fs_failure"),
    ("f15_no_failed_append", "ddf", [(_DDF_FAILED_APPEND, "")], "fs_failure"),
    ("f15_no_passthrough", "ddf", [(_DDF_PASSTHRU, "")], "fs_logs"),
    ("f15_outer_not_catching", "ddf", [(_DDF_OUTER, "    except ZeroDivisionError as _sf:\n        return _sf.payload\n")],
     "fs_never_raises"),
    # ── D2-f20：既有程式碼被改壞時，新補的行為測試擋得住 ──
    ("f20_no_streak_cap", "fc", [(_FC_STREAK_CAP, "        while False:\n")], "streak"),
    ("f20_no_proxy_env", "yp", [("    with _proxy_env():\n" + _YP_LAYER_CALL, "    if True:\n" + _YP_LAYER_CALL)],
     "proxy"),
    ("f20_column_empty_passthrough", "yp",
     [(_YP_EMPTY_RULE, "    if _df is None:\n        return pd.DataFrame()\n    return _df\n")], "column_empty"),
    ("f20_key_ticker_only", "yp", [("    _key = (ticker, period)\n", "    _key = ticker\n")], "cooldown_key"),
    ("f20_key_period_only", "yp", [("    _key = (ticker, period)\n", "    _key = period\n")], "cooldown_key"),
    # ── 批 D3d 複驗補修（2026-09-29）──
    ("n1_cooldown_cap_default_64", "yp",
     [("_history_fail_cooldown = _FailCooldown(max_entries=_HISTORY_CACHE_MAX_ENTRIES)",
       "_history_fail_cooldown = _FailCooldown()")], "capacity"),
    ("n4a_fetch_single_ttl_30min", "ddf",
     [("@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)\ndef _fetch_single_cached(",
       "@st.cache_data(ttl=TTL_30MIN, show_spinner=False)\ndef _fetch_single_cached(")], "fs_ttl"),
    ("n4a_fetch_single_ttl_2h", "ddf",
     [("@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)\ndef _fetch_single_cached(",
       "@st.cache_data(ttl=2 * TTL_1HOUR, show_spinner=False)\ndef _fetch_single_cached(")], "fs_ttl"),
    # ── D2-f45（2026-10-01）：落在行為測試 31～61 分鐘窗內的 TTL 突變（修前存活）──
    ("d2f45_fetch_single_ttl_59min", "ddf",
     [("@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)\ndef _fetch_single_cached(",
       "@st.cache_data(ttl=TTL_1HOUR - 60, show_spinner=False)\ndef _fetch_single_cached(")], "fs_ttl_exact"),
    ("d2f45_fetch_single_ttl_45min", "ddf",
     [("@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)\ndef _fetch_single_cached(",
       "@st.cache_data(ttl=45 * 60, show_spinner=False)\ndef _fetch_single_cached(")], "fs_ttl_exact"),
    ("d2f45_fetch_single_max_entries", "ddf",
     [("@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)\ndef _fetch_single_cached(",
       "@st.cache_data(ttl=TTL_1HOUR, max_entries=200, show_spinner=False)\ndef _fetch_single_cached(")],
     "fs_ttl_exact"),
    ("n4b_maintenance_page_is_no_data", "yp",
     [('"YFChartError", "YFInvalidPeriodError")', '"YFChartError", "YFInvalidPeriodError", "YFDataException")')],
     "yahoo_down"),
    ("n4b_runtime_error_is_no_data", "yp",
     [("    if type(exc) is Exception:\n", "    if type(exc) in (Exception, RuntimeError):\n")],
     "yahoo_down_legacy"),
]


def _run_check(name: str, yp, ddf, fcm, fake, clock, capsys) -> None:
    {
        "swallowed": lambda: _check_swallowed_error_not_cached(yp, fake, clock),
        "no_data": lambda: _check_no_data_cached(yp, fake, clock, "no_data"),
        "legacy_no_data": lambda: _check_no_data_cached(yp, fake, clock, "legacy_no_data"),
        "rate_rule": lambda: _check_rate_limit_never_no_data(yp),
        "legacy_signature": lambda: _check_legacy_signature_fallback(yp),
        "unrelated_typeerror": lambda: _check_unrelated_typeerror_not_retried(yp),
        "deprecation": lambda: _check_deprecation_as_error_falls_back(yp),
        "with_status": lambda: _check_with_status(yp, fake, clock),
        "fs_failure": lambda: _check_fetch_single_failure_not_cached(yp, ddf, fake, clock),
        "force_refresh": lambda: _check_fetch_single_force_refresh_in_cooldown(yp, ddf, fake, clock),
        "dxy": lambda: _check_dxy_chain(yp, ddf, fake, clock),
        "fs_exception": lambda: _check_fetch_single_exception_not_cached(ddf),
        "fs_logs": lambda: _check_fetch_single_logs_unchanged(yp, ddf, fake, capsys),
        "fs_never_raises": lambda: _check_fetch_single_never_raises(yp, ddf, fake),
        "streak": lambda: _check_streak_capped(fcm),
        "proxy": lambda: _check_cache_layer_applies_proxy(yp),
        "column_empty": lambda: _check_column_bearing_empty(yp, fake, clock),
        "cooldown_key": lambda: _check_cooldown_key(yp, fake, clock),
        "capacity": lambda: _check_cooldown_capacity(yp, fake, clock, 65),
        "fs_ttl": lambda: _check_fetch_single_ttl(ddf),
        "fs_ttl_exact": lambda: _check_fetch_single_ttl_exact(ddf),
        "yahoo_down": lambda: _check_swallowed_error_not_cached(yp, fake, clock, "yahoo_down"),
        "yahoo_down_legacy": lambda: _check_swallowed_error_not_cached(yp, fake, clock, "yahoo_down_legacy"),
    }[name]()


class TestMutations:
    @pytest.mark.parametrize("tag,target,pairs,check", _MUTATIONS, ids=[m[0] for m in _MUTATIONS])
    def test_mutant_turns_check_red(self, yfh, fc_clock, capsys, tag, target, pairs, check):
        yp, ddf, fcm = YP, DDF, FC
        if target == "yp":
            yp = _mutant(YP, *pairs, tag=tag)
        elif target == "ddf":
            ddf = _mutant(DDF, *pairs, tag=tag)
        else:
            fcm = _mutant(FC, *pairs, tag=tag)
        try:
            _run_check(check, YP, DDF, FC, yfh, fc_clock, capsys)        # 真模組：必過
            yfh.calls.clear()
            yfh.per = {}
            with pytest.raises(AssertionError):
                _run_check(check, yp, ddf, fcm, yfh, fc_clock, capsys)   # 突變體：必紅
        finally:
            _clear(yp.cached_history)
            _clear(getattr(ddf, "fetch_single", None))
