"""src/ui/tabs/stock_sections/ — tab_stock.py 拆檔後的 section render 模組(v18.406 U4 Phase 2+).

Phase 2(低風險 section):
- section_revenue: D 月營收趨勢(D 月營收 + 季財報 charts)
- section_financial_leading: C 財報領先指標(合約負債 + 資本支出)
- section_op_recommendation: 即時操作建議規則引擎(4 訊號共振 + AI 文案)
- section_psy_checklist: 心理檢查 + 勝利方程式 + 禁止操作(3 連 section,共享 state)

後續 Phase 3-4 將陸續加入更多 section。
"""
from __future__ import annotations

from src.ui.tabs.stock_sections.section_financial_leading import (
    render_financial_leading_section,
)
from src.ui.tabs.stock_sections.section_op_recommendation import (
    render_op_recommendation_section,
)
from src.ui.tabs.stock_sections.section_psy_checklist import (
    render_psy_checklist_section,
)
from src.ui.tabs.stock_sections.section_revenue import render_revenue_trend_section

__all__ = [
    'render_financial_leading_section',
    'render_op_recommendation_section',
    'render_psy_checklist_section',
    'render_revenue_trend_section',
]
