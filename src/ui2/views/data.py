"""data 頁（🗂 資料）view：只渲染 PageVM。

DEC-146 第一批：可導航、誠實的「尚未提供／尚未接線」空殼。保留 Data State／Capability 分軸（本頁全為 Capability 軸
`⬜ 尚未提供`）。⛔ 來源健康度欄位／分母／retrieved_at／proxy／刷新時間／真登入／Sheet／API／公式；⛔ 取數與判態。
"""
from __future__ import annotations

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import first_screen_html
from src.ui2.views._page import _md, render_cards, render_sections, render_title


def render(vm: PageVM) -> None:
    render_title(vm)
    _md(first_screen_html(vm.context.first_screen))      # 現在狀態／是否需要行動／下一步／主 CTA（disabled 示意）
    render_cards(vm)
    render_sections(vm)
