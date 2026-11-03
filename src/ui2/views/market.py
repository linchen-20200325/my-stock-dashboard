"""market 頁 view：只渲染 PageVM。

版面（Wireframes §2／Freeze §0.1.6／§16.1-M）：標題 → [今日結論 → 市場目前狀態 → Risk Cap → 是否需要行動
→ 下一步 → 主 CTA] → **緊接**「今日主要風險」（L1，⛔ 被卡片或其他區塊插隊）→ 核心指標卡 → 其餘區塊。
（Active Contract §3.1：📊 整頁不承載完整 evidence 摺疊；現存摺疊區塊的移除屬 UI correction P3。）
桌機（≥769px）由 CSS 把 狀態／Risk Cap／今日主要風險 排成三 tile（見 shell/css.py）；手機堆疊。
"""
from __future__ import annotations

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import market_l1_html
from src.ui2.views._page import _md, render_cards, render_sections, render_title


def render(vm: PageVM) -> None:
    render_title(vm)
    _md(market_l1_html(vm.context.first_screen, vm.context.main_risk))
    render_cards(vm)
    render_sections(vm)
