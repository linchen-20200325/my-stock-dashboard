"""market 頁 view：只渲染 PageVM。

版面（Wireframes §2／Freeze §0.1.6／§16.1-M；P2 起依客戶 2026-11-04 (19)／DEC-133）：
標題 → [今日結論 → 市場目前狀態 → Risk Cap → 是否需要行動 → 下一步 → 主 CTA] → **緊接**「今日主要風險」（L1，⛔ 被插隊）
→ 🤖 OneBrain Outlook（內容不變，只改位置）→ 🇹🇼 台股趨勢**誠實空槽**＋一行 SPEC → 核心指標卡 → 其餘區塊。
（Active Contract §3.1：📊 整頁不承載完整 evidence 摺疊——P3 起 L2／L3 evidence 區塊不渲染，VM 完整保留。）
桌機（≥769px）由 CSS 把 狀態／Risk Cap／今日主要風險 排成三 tile（見 shell/css.py）；手機堆疊。

P2 實作形態（線框 F-5 (ii)）：OneBrain 取 VM 既有 L1 section 原樣渲染（`section_l1_html`），只是畫的位置前移；
`render_sections(skip={"onebrain"})` 仍被呼叫（其餘區塊與 L2／L3 呈現政策不變，`test_render_policy_guard_has_teeth` 保有牙）。
空槽與 SPEC 全在 view 內以既有字樣／TWII 卡 freshness 組成；VM／canonical／scenarios 0 變更。
"""
from __future__ import annotations

from html import escape

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import market_l1_html, primary_slot_html
from src.ui2.views._page import _md, render_cards, render_sections, render_title, section_l1_html

ONEBRAIN_SECTION_ID = "onebrain"
TWII_CARD_ID = "twii"


def render(vm: PageVM) -> None:
    render_title(vm)
    _md(market_l1_html(vm.context.first_screen, vm.context.main_risk))
    # P2-1：OneBrain Outlook 移到核准位置（今日主要風險之後、Primary 空槽之前、核心指標卡之前）；內容原樣。
    onebrain = next((s for s in vm.context.sections if s.section_id == ONEBRAIN_SECTION_ID and s.level == "L1"), None)
    if onebrain is not None:
        _md(f'<div class="ui2-m-onebrain" data-ui2-l1="onebrain">{section_l1_html(onebrain)}</div>')
    # P2-2：台股 Primary 誠實空槽＋一行 SPEC（來源／資料日＝TWII 卡 freshness；不接歷史序列）。
    twii = next((c for c in vm.context.cards if c.card_id == TWII_CARD_ID), None)
    _md(primary_slot_html(twii))
    render_cards(vm)
    render_sections(vm, skip={ONEBRAIN_SECTION_ID} if onebrain is not None else frozenset())
