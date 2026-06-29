"""src/services/etf_grp_compare_service.py — ETF 多檔對比 L3 wrapper(v18.406 R4)。

對齊 user 建議 R4:`etf_tab_grp_compare.py:25` 直 import 3 個 L1 fetcher
(price / dividends / info)→ 集中至 L3。

§8.2 L3 service:thin pass-through(對齊 stock_grp_service 同 pattern)。
EX-PASSTHRU-1 Group A 升級觸發條件(3 fetcher 跨頻 cache,加 ETF 多檔對比新
功能會觸發 — 預先收斂避免日後散落)滿足。

未來擴充:若加跨 ETF 統一 TTL / 多源 fallback,集中本檔就近編輯。
"""
from __future__ import annotations

from typing import Any

from src.data.etf import fetch_etf_dividends, fetch_etf_info, fetch_etf_price


def get_etf_price(ticker: str, period: str = '5y') -> Any:
    """取得 ETF 歷史價格(yfinance auto_adjust 還原權息)。"""
    return fetch_etf_price(ticker, period)


def get_etf_dividends(ticker: str) -> Any:
    """取得 ETF 歷史配息 Series。"""
    return fetch_etf_dividends(ticker)


def get_etf_info(ticker: str) -> Any:
    """取得 ETF 基本資訊(name / category / aum 等)。"""
    return fetch_etf_info(ticker)
