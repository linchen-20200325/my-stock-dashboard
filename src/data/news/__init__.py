"""src/data/news/ — 新聞 RSS 抓取 L1 module(v18.398 P5-B3-β R8).

對齊 APP_PY_AUDIT.md B3-β 拆檔藍圖:app.py:1052-1297 ~245 LOC 新聞 fetcher
(`_SYSTEMIC_RISK_KEYWORDS` / `_fetch_macro_news` / `_rss_items_from_bytes` /
`_fetch_stock_news`)→ 抽至 L1 data module。

§8.2 layer:L1 Data — RSS feed I/O + 解析 + 系統性風險標記。

對外 API:
- fetch_macro_news(n=5) → list[dict]:全球總經新聞(8 源,@st.cache_data)
- fetch_stock_news(stock_id, stock_name, n, recency, _diag) → list[dict]:個股新聞
- rss_items_from_bytes(content) → list:RSS bytes 解析 helper
- SYSTEMIC_RISK_KEYWORDS:系統性風險關鍵字 SSOT
"""
from __future__ import annotations

from src.data.news.news_fetcher import (
    SYSTEMIC_RISK_KEYWORDS,
    fetch_macro_news,
    fetch_stock_news,
    rss_items_from_bytes,
)

__all__ = [
    'SYSTEMIC_RISK_KEYWORDS',
    'fetch_macro_news',
    'fetch_stock_news',
    'rss_items_from_bytes',
]
