"""hold 頁 view：只渲染 PageVM。

版面（Wireframes §4.1／§4.2、W-11〔客戶 Q3 核准〕）：標題＋第一屏放同一容器（`ui2-h-l1`），手機堆疊（與原版面逐像素相同），
桌機由 CSS 排成「header 列＝標題＋主 CTA → 三 tile → 今日需處理／下一步」。元件、欄位、字樣不增不減。
"""
from __future__ import annotations

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import hold_l1_html, page_title_html
from src.ui2.views._page import _md, render_cards, render_sections


def render(vm: PageVM) -> None:
    _md(hold_l1_html(page_title_html(vm.page_id, vm.scenario_id, vm.title), vm.context.first_screen))
    render_cards(vm)
    render_sections(vm)
