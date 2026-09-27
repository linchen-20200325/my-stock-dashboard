"""v18.209 K5：yfinance 共用 cached + proxy wrapper（解 Cloud IP 403 風險）。

Phase 1 audit 找到 8+ 處 `yf.Ticker()` 直呼，deep check 後確認 3 處真未 cache：
  - app.py:363 (fetch_dividend_data)
  - tab_stock_picker.py:237 (_check_one_stock, in loop)
  - daily_checklist.py:487 (fetch_single, in loop)

Streamlit Cloud 海外 IP 常被 Yahoo 403/rate-limit；既有 NAS Squid Proxy 走家用台灣 IP
可繞過。但 caller 各自寫一份「env backup → set proxy → call → restore」boilerplate
易漏接。本模組提供：
  - cached_history(ticker, period): @st.cache_data(ttl=TTL_1HOUR) 包 yf.Ticker.history
  - cached_dividends(ticker): @st.cache_data(ttl=TTL_1HOUR) 包 yf.Ticker.dividends
proxy env 由模組內 try/finally 統一處理，caller 零樣板。

設計：純函式 wrapper + st.cache_data；caller 用 from src.data.proxy import ... 即可。
"""
from __future__ import annotations

import os as _os
from contextlib import contextmanager

import pandas as pd
# §8.2.A EX-CACHE-1:條件 import streamlit + 無 UI 呼叫 fallback。
# 本檔僅用 @st.cache_data 包 yfinance call,無真 UI 呼叫。
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

from shared.ttls import TTL_1HOUR
from shared.fail_cooldown import FailCooldown as _FailCooldown, NO_HIT as _FC_NO_HIT


_PROXY_ENV_KEYS = ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy")


@contextmanager
def _proxy_env():
    """臨時設 NAS Squid Proxy 到 env vars（finally 自動還原，異常安全）。

    從 tw_stock_data_fetcher._load_proxy_config 取 proxy URL；無 proxy 時不動 env。
    """
    _purl = None
    try:
        from src.data.stock import _load_proxy_config
        _cfg = _load_proxy_config() or {}
        _purl = _cfg.get("https") or _cfg.get("http")
    except Exception:
        _purl = None
    _backup = {k: _os.environ.get(k) for k in _PROXY_ENV_KEYS}
    try:
        if _purl:
            for k in _PROXY_ENV_KEYS:
                _os.environ[k] = _purl
        yield
    finally:
        for k, v in _backup.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v


@st.cache_data(ttl=TTL_1HOUR, max_entries=200, show_spinner=False)
def cached_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """yfinance Ticker.history with NAS proxy + 1h cache。

    Args:
        ticker: yfinance 標的代碼，例 "2330.TW"
        period: "5d"/"1mo"/"3mo"/"1y"/"5y"/"max"

    Returns:
        pd.DataFrame；抓不到回空 DataFrame（不爆例外）。
    """
    import yfinance as yf
    try:
        with _proxy_env():
            _df = yf.Ticker(ticker).history(period=period)
        if _df is None or _df.empty:
            return pd.DataFrame()
        return _df
    except Exception as _e:
        print(f"[yf_proxy.history] {ticker}: {type(_e).__name__}: {_e}")
        return pd.DataFrame()


#: `cached_dividends()` **拋例外**時，回傳的空 Series 在 `attrs` 裡帶的鍵（值 ＝
#: `"{例外型別}: {訊息}"`）。**只有例外才有**（2026-09-27 Q5-r2）—— yfinance **沒拋、只回空**
#: 時照舊回無旗標的空 Series：那與「真的沒配息」在這一層分不出來，不猜（§1）。
DIVIDENDS_FETCH_FAILED_ATTR = "fetch_failed"


@st.cache_data(ttl=TTL_1HOUR, max_entries=200, show_spinner=False)
def _cached_dividends_cached(ticker: str) -> pd.Series:
    """`cached_dividends()` 的快取層。**拋例外一律往上拋**（Q5-r2-r3 2026-09-27,
    §1.A-3(a)「只快取成功結果」;st.cache_data 不快取例外）。成功與「只回空」路徑與 TTL 同修前。"""
    import yfinance as yf
    with _proxy_env():
        _s = yf.Ticker(ticker).dividends
    if _s is None or _s.empty:
        return pd.Series(dtype=float)
    return _s


#: Q5-r2-r3:配息失敗退避（§1.A-3(b)）—— 冷卻期內同一檔不重打 Yahoo,回同一則失敗旗標。
_dividends_fail_cooldown = _FailCooldown()


def cached_dividends(ticker: str) -> pd.Series:
    """yfinance Ticker.dividends with NAS proxy + 1h cache（**只快取成功**）。

    Returns:
        pd.Series；抓不到回空 Series（不爆例外）。拋例外那一種，空 Series 的 `attrs`
        帶 `DIVIDENDS_FETCH_FAILED_ATTR`（值與內容其餘不變；不讀 attrs 的 caller 無感）。
        Q5-r2-r3:失敗**不入快取**;失敗後 `shared.fail_cooldown.FAIL_COOLDOWN_SEC` 秒內
        同一檔不重抓,回同一則失敗旗標;成功一次即解除。`.clear()` 同清快取與退避紀錄。
    """
    _hit, _gen = _dividends_fail_cooldown.begin(ticker)
    if _hit is not _FC_NO_HIT:
        return _hit
    try:
        _s = _cached_dividends_cached(ticker)
    except Exception as _e:
        print(f"[yf_proxy.dividends] {ticker}: {type(_e).__name__}: {_e}")
        _empty = pd.Series(dtype=float)
        _empty.attrs[DIVIDENDS_FETCH_FAILED_ATTR] = f"{type(_e).__name__}: {_e}"
        return _dividends_fail_cooldown.fail(ticker, _gen, _empty)
    _dividends_fail_cooldown.success(ticker)
    return _s


def _clear_cached_dividends() -> None:
    getattr(_cached_dividends_cached, "clear", lambda: None)()
    _dividends_fail_cooldown.clear()


cached_dividends.clear = _clear_cached_dividends
