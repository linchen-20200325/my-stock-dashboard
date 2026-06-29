"""src/services/yield_screener_service.py — 高股息篩選 L3 wrapper(v18.406 R5)。

對齊 user 建議 R5:`yield_screener.py` 4 處 L1 import 集中至 L3:
- L33 `from src.data.proxy import fetch_url`(lazy,於 fetch_twse_yields 內)
- L71 `from src.data.stock.dividend_fetcher import fetch_annual_dividends`(module-level alias)
- L80 `from src.data.proxy import get_proxy_config`(lazy,於 _proxy_status_badge 內)

§8.2 L3 service:thin pass-through(對齊 stock_grp_service / etf_grp_compare_service)。
EX-PASSTHRU-1 Group A 升級觸發條件(4 處 lazy import 散落,加篩選器併排會觸發)滿足。
"""
from __future__ import annotations

from typing import Any

from src.data.proxy import fetch_url, get_proxy_config
from src.data.stock.dividend_fetcher import fetch_annual_dividends


def proxy_fetch_url(url: str, *args, **kwargs) -> Any:
    """走 NAS proxy 抓 URL(thin pass-through)。"""
    return fetch_url(url, *args, **kwargs)


def get_proxy_status_config() -> Any:
    """取得 proxy 設定(供 _proxy_status_badge 用)。"""
    return get_proxy_config()


def get_annual_dividends(ticker: str) -> Any:
    """取得年度股利歷史(yfinance Ticker.dividends 走 NAS proxy)。"""
    return fetch_annual_dividends(ticker)
