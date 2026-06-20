from data_config import CACHE_TTL
"""v18.209 K5嚗finance ?梁 cached + proxy wrapper嚗圾 Cloud IP 403 憸券嚗?

Phase 1 audit ?曉 8+ ??`yf.Ticker()` ?游嚗eep check 敺Ⅱ隤?3 ????cache嚗?
  - app.py:363 (fetch_dividend_data)
  - tab_stock_picker.py:237 (_check_one_stock, in loop)
  - daily_checklist.py:487 (fetch_single, in loop)

Streamlit Cloud 瘚瑕? IP 撣貉◤ Yahoo 403/rate-limit嚗??NAS Squid Proxy 韏啣振?典??IP
?舐??? caller ?撖思?隞賬nv backup ??set proxy ??call ??restore?oilerplate
???乓璅∠???嚗?
  - cached_history(ticker, period): @st.cache_data(ttl=CACHE_TTL["price_data"]) ??yf.Ticker.history
  - cached_dividends(ticker): @st.cache_data(ttl=CACHE_TTL["price_data"]) ??yf.Ticker.dividends
proxy env ?望芋蝯 try/finally 蝯曹???嚗aller ?嗆見?踴?

閮剛?嚗??賢? wrapper + st.cache_data嚗aller ??from yf_proxy import ... ?喳??
"""
from __future__ import annotations

import os as _os
from contextlib import contextmanager

import pandas as pd
import streamlit as st


_PROXY_ENV_KEYS = ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy")


@contextmanager
def _proxy_env():
    """?冽?閮?NAS Squid Proxy ??env vars嚗inally ?芸???嚗撣詨??剁???

    敺?tw_stock_data_fetcher._load_proxy_config ??proxy URL嚗 proxy ????env??
    """
    _purl = None
    try:
        from tw_stock_data_fetcher import _load_proxy_config
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


@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=200, show_spinner=False)
def cached_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """yfinance Ticker.history with NAS proxy + 1h cache??

    Args:
        ticker: yfinance 璅?隞?Ⅳ嚗? "2330.TW"
        period: "5d"/"1mo"/"3mo"/"1y"/"5y"/"max"

    Returns:
        pd.DataFrame嚗?銝?征 DataFrame嚗???憭???
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


@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=200, show_spinner=False)
def cached_dividends(ticker: str) -> pd.Series:
    """yfinance Ticker.dividends with NAS proxy + 1h cache??

    Returns:
        pd.Series嚗?銝?征 Series嚗???憭???
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

