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
import streamlit as st

from shared.ttls import TTL_1HOUR


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


@st.cache_data(ttl=TTL_1HOUR, max_entries=200, show_spinner=False)
def cached_dividends(ticker: str) -> pd.Series:
    """yfinance Ticker.dividends with NAS proxy + 1h cache。

    Returns:
        pd.Series；抓不到回空 Series（不爆例外）。
    """
    import yfinance as yf
    try:
        with _proxy_env():
            _s = yf.Ticker(ticker).dividends
        if _s is None or _s.empty:
            return pd.Series(dtype=float)
        return _s
    except Exception as _e:
        print(f"[yf_proxy.dividends] {ticker}: {type(_e).__name__}: {_e}")
        return pd.Series(dtype=float)
