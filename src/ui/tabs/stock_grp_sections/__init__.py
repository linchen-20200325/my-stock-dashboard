"""src/ui/tabs/stock_grp_sections/ — tab_stock_grp.py 拆檔後的 section render 模組(v18.413 Batch 7-1+).

仿 stock_sections/ pattern,逐 section 抽出。

Batch 7-1(v18.413):
- section_market_status: ① 市場狀態 3 KPI 卡(燈號 / 大盤 / 建議持股)

Batch 7-2(v18.414):
- section_batch_fetcher: 批次抓取 + 計算 + 評分 + 風控警示
  (ThreadPoolExecutor + cache lock + score_single_stock + status lamp)

後續 Batch 7-3 ~ 7-5 將陸續加入 portfolio_summary /
financial_health / ai_portfolio。
"""
from __future__ import annotations

from src.ui.tabs.stock_grp_sections.section_batch_fetcher import (
    run_batch_fetch,
)
from src.ui.tabs.stock_grp_sections.section_market_status import (
    render_market_status_section,
)

__all__ = [
    'render_market_status_section',
    'run_batch_fetch',
]
