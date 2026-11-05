"""hold 頁 view：只渲染 PageVM。

版面（Wireframes §4.1／§4.2、W-11〔客戶 Q3 核准〕；DEC-141 客戶 2026-11-05 Q1~Q8，**僅版面／欄位結構／空槽，⛔ 資料接線**）：
標題 → 組合狀態行 → 第一屏（Risk Cap／目前曝險／組合狀態／**今日需處理單行**／主 CTA）→ 建議持股水位（市場端）空槽 →
OneBrain → Primary（產業曝險／集中度）空槽 → 持股表（桌機八欄／手機四欄＋展開；無資料＝欄名＋原因）。
桌機由 CSS 排成 header 列＋三 tile，OneBrain 之下為〔Primary｜建議持股水位〕並排、持股表在下（Q1=A）。
VM 全量不動：「下一步」欄位與 `holdings_table` 卡仍在 PageVM（只是畫面合併／改以持股表呈現，Presentation Compression ≠ Information Loss）。
"""
from __future__ import annotations

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import hold_body_html, hold_l1_v2_html, page_title_html
from src.ui2.views._page import _md, render_sections, section_l1_html

ONEBRAIN_SECTION_ID = "onebrain"


def render(vm: PageVM) -> None:
    _md(hold_l1_v2_html(page_title_html(vm.page_id, vm.scenario_id, vm.title), vm.context.first_screen))
    onebrain = next((s for s in vm.context.sections if s.section_id == ONEBRAIN_SECTION_ID and s.level == "L1"), None)
    _md(hold_body_html(section_l1_html(onebrain) if onebrain is not None else ""))
    render_sections(vm, skip={ONEBRAIN_SECTION_ID} if onebrain is not None else frozenset())
