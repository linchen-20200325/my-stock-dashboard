"""src/data/stock/dividend_fetcher.py — 個股年配息 fetcher(L1 Data)。

P1-1b v18.375 深層拔毒:從 src/ui/tabs/yield_screener.py:70(L5 UI 違憲)
抽出 yfinance.Ticker.dividends 直呼 + NAS proxy 注入。

EX-CACHE-1 例外:用 @st.cache_data decorator(L1 允許,只 cache 不用 UI)。
"""
from __future__ import annotations

import pandas as pd

try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
    st = _NoOpST()  # noqa

from shared.ttls import TTL_1DAY


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def fetch_annual_dividends(ticker: str) -> pd.Series:
    """取得單檔股票的歷史配息(按年合計)。

    Args:
        ticker: 純台股代碼如 '2330' / '6770',自動補 .TW

    Returns:
        Series:index=西元年, values=該年現金配息合計(元);無資料回傳空 Series
    """
    import os as _os
    try:
        import yfinance as yf
    except ImportError:
        print('[dividend_fetcher] yfinance 未安裝')
        return pd.Series(dtype=float)

    # 注入 NAS proxy 至 env(yfinance/requests 會自動讀取)
    _ek = ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy')
    _bak = {k: _os.environ.get(k) for k in _ek}
    try:
        from src.data.proxy import get_proxy_config
        _proxy_dict = get_proxy_config() or {}
        _px_url = _proxy_dict.get('https') or _proxy_dict.get('http')
        if _px_url:
            for k in _ek:
                _os.environ[k] = _px_url
    except Exception:
        pass

    _t = ticker.strip().upper()
    if not _t.endswith('.TW') and not _t.endswith('.TWO'):
        _t = f'{_t}.TW'

    try:
        _y = yf.Ticker(_t)
        _div = _y.dividends
        if _div is None or len(_div) == 0:
            return pd.Series(dtype=float)
        _annual = _div.groupby(_div.index.year).sum().astype(float)
        # provenance(S-PROV-1 phase 19,Series 走 attrs)
        try:
            _annual.attrs.setdefault('source', f'yfinance.Ticker({_t}).dividends')
            _annual.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        return _annual
    except Exception as _e:
        print(f'[dividend_fetcher] dividend fetch 失敗 {ticker}: {_e}')
        return pd.Series(dtype=float)
    finally:
        # 還原環境變數,避免污染其他模組
        for k, v in _bak.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v
