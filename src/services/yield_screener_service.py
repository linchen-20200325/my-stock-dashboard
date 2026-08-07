"""src/services/yield_screener_service.py — 高股息篩選 L3 wrapper(v18.406 R5)。

對齊 user 建議 R5:`yield_screener.py` 的 L1 import 集中至 L3:
- `from src.data.stock.dividend_fetcher import fetch_annual_dividends`(單檔配息歷史)
- `from src.data.proxy import get_proxy_config`(_proxy_status_badge 的 NAS 狀態徽章)

§8.2 L3 service:thin pass-through(對齊 stock_grp_service / etf_grp_compare_service)。

E2(2026-08):`proxy_fetch_url` 已移除 —— 它唯一的 caller 是 `fetch_twse_yield_pe` /
`fetch_tpex_yield_pe`,兩者已下沉 L1(`src/data/stock/yield_pe_fetcher.py`),L1 直接
走 `src.data.proxy`(同層),不再經 L3 繞行(L1→L3 會是 §8.2 上行違憲)。留著會是死碼。
"""
from __future__ import annotations

from typing import Any

from src.data.proxy import get_proxy_config
from src.data.stock.dividend_fetcher import fetch_annual_dividends


def get_proxy_status_config() -> Any:
    """取得 proxy 設定(供 _proxy_status_badge 用)。"""
    return get_proxy_config()


def get_annual_dividends(ticker: str) -> Any:
    """取得年度股利歷史(yfinance Ticker.dividends 走 NAS proxy)。"""
    return fetch_annual_dividends(ticker)
