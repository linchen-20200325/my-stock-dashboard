"""src/ui/tabs/stock_grp_sections/ — tab_stock_grp.py 拆檔後的 section render 模組
(v18.413 Batch 7-1+).

仿 stock_sections/ pattern,逐 section 抽出。

- Batch 7-1(v18.413):section_market_status — ① 市場狀態 3 KPI 卡
- Batch 7-2(v18.414):section_batch_fetcher — 批次抓取 + 計算 + 評分 + 風控警示
- Batch 7-3(v18.415):section_portfolio_summary — KPI banner + ⑤ + RS + ③④
- Batch 7-4(v18.416):section_financial_health — 批次財報體檢(5 模組 expander)

後續 Batch 7-5 將加入 ai_portfolio。
"""
from __future__ import annotations

from src.ui.tabs.stock_grp_sections.section_batch_fetcher import (
    run_batch_fetch,
)
from src.ui.tabs.stock_grp_sections.section_financial_health import (
    render_financial_health_section,
)
from src.ui.tabs.stock_grp_sections.section_market_status import (
    render_market_status_section,
)
from src.ui.tabs.stock_grp_sections.section_portfolio_summary import (
    render_portfolio_summary_section,
)

__all__ = [
    'render_financial_health_section',
    'render_market_status_section',
    'render_portfolio_summary_section',
    'run_batch_fetch',
]
