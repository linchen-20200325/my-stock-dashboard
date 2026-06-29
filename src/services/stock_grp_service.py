"""src/services/stock_grp_service.py — 個股組合 tab L3 service wrapper(v18.405 R1)。

對齊 user 未完成項目 R1:將 tab_stock_grp.py 5 處散落 L1 import 集中至 L3 wrapper,
讓 lazy import failure → fail-loud 一致(原 5 處各自 try/except / 不一致)。

收斂的 L1 fetcher:
- `fetch_bps`(src.data.core)
- `fetch_industry_category`(src.data.core)
- `_fetch_news_for`(src.data.etf)
- `fetch_financial_statements`(src.data.core,fallback app.py)
- `fetch_5_years_cash_flow`(src.data.stock)

§8.2 L3 service:純 forward(thin pass-through),但統一 fail-loud:
- import 失敗 → 拋 ImportError(原 silent catch 改 visible)
- caller 透過 `from src.services.stock_grp_service import ...` 取得穩定 API

§-1 對齊:EX-PASSTHRU-1 升級觸發條件(Group A:5 處跨多 fetcher)達標,
本 service 真有業務值(unified import + 統一 fail-loud)。
"""
from __future__ import annotations

from typing import Any

# ── 上游 fetcher 集中 import(模組 load 時即 verify)──────────
# 失敗即 ImportError 全頁炸(§1 Fail Loud)— 取代原 tab_stock_grp 5 處散落
# lazy import 各自 try/except 的不一致行為。
from src.data.core import (
    fetch_bps,
    fetch_industry_category,
    fetch_financial_statements,
)
from src.data.etf import _fetch_news_for
from src.data.stock import fetch_5_years_cash_flow


# ── L3 wrapper(thin pass-through)─────────────────────────
# 設計考量:現階段 5 個 fetcher 介面已穩定,L3 不加業務轉換 / 不改變 cache。
# 未來若需:統一 TTL / 多源 fallback / 結果後處理,集中在此 file 就近編輯。

def get_bps(sid: str) -> Any:
    """取得 BPS(book value per share)。"""
    return fetch_bps(sid)


def get_industry_category(sid: str) -> Any:
    """取得個股產業分類。"""
    return fetch_industry_category(sid)


def get_news_for(sid: str, name: str = '', n: int = 3) -> str:
    """取得個股新聞(Google News + Yahoo News 多源 RSS)。

    對齊 etf_sector_service.get_news_for(R1+B1 PR #401 同 pattern)。
    """
    return _fetch_news_for(sid, name, n)


def get_financial_statements(sid: str, fm_token: str = '') -> Any:
    """取得個股財報 dict(income / balance / cashflow / quarterly_extra)。"""
    return fetch_financial_statements(sid, fm_token)


def get_5_years_cash_flow(sid: str, fm_token: str = '') -> Any:
    """取得個股 5 年現金流量。"""
    return fetch_5_years_cash_flow(sid, fm_token)
