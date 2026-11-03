"""四頁共用的 PageVM 渲染骨架（第一屏四問 → 核心卡 → 各區塊）。

標示（FAKE 示意資料／Real-data Preview 單行 banner）由殼在導覽**之前**統一渲染（頁面頂部），本檔不重複渲染。
開發專用的 Preview 控制只在 `?ui2_dev=1` 由殼畫出，本檔不涉及。

**呈現政策（Active Contract §8）**：`PageVM.context.sections` 是 Human UI 全量（**不是** Decision Context）；
本檔只決定「哪些區塊在畫面上怎麼畫」，不改 VM 內容。目前（P1）仍依 `SectionVM.level` 畫 L1 並摺疊 L2／L3；
**L2／L3 摺疊區塊的移除屬 UI correction P3**（ACTIVE 規格：四個主要投資頁不承載完整 L2／L3 diagnostics），
不得依本檔現況當作規格。
Batch 3：標題／本文拆成可重用片段，供 📊 市場（今日結論＋今日主要風險）、🎯 標的（雙模式）、
👤 我的（帳戶 skeleton）三頁各自組版；所有頁仍只吃 PageVM（⛔ 取數／判態／聚合動作）。
"""
from __future__ import annotations

from html import escape

import streamlit as st

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import field_row_html, first_screen_html, metric_card_html


def _md(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def render_title(vm: PageVM, **attrs: str) -> None:
    # data-ui2-page／-scenario＝量測與測試錨點（tests/ui2_viewport），不影響呈現。
    extra = "".join(f' data-ui2-{k}="{escape(v)}"' for k, v in attrs.items())
    _md(f'<div class="ui2-pagetitle" data-ui2-page="{escape(vm.page_id)}" '
        f'data-ui2-scenario="{escape(vm.scenario_id)}"{extra}>{escape(vm.title)}</div>')


def render_cards(vm: PageVM, *, content_mode: str | None = None) -> None:
    visible = set(vm.slice.visible_card_ids)
    cards = [c for c in vm.context.cards if c.card_id in visible]
    if cards:
        attr = f' data-ui2-mode-content="{escape(content_mode)}"' if content_mode else ""
        _md(f'<div class="ui2-grid"{attr}>' + "".join(metric_card_html(c) for c in cards) + "</div>")


def _label_repeats_title(sec, f) -> bool:
    """區塊只有一個欄位、且欄位 label 已是區塊標題的一部分（如標題「🤖 OneBrain Outlook」＋列「OneBrain Outlook」）
    → 列的 label 不再重複畫（P1 重複標籤合併；欄位資料與 `data-*` 不變）。"""
    return len(sec.fields) == 1 and bool(f.label.strip()) and f.label.strip() in sec.title


def render_sections(vm: PageVM, *, mode: str | None = None, extra=()) -> None:
    """（P1 現況）L1 區塊直接畫、L2／L3 摺疊——摺疊區塊的移除屬 P3，見檔頭。`mode` 給定時只畫該模式
    （或與模式無關）的區塊（⛔ 同時完整展開）。"""
    for sec in (*vm.context.sections, *extra):
        if mode is not None and sec.mode not in (None, mode):
            continue
        rows = "".join(field_row_html(f, hide_label=_label_repeats_title(sec, f)) for f in sec.fields)
        if sec.level == "L1":
            _md(f'<div class="ui2-section-title">{escape(sec.title)}</div>' + rows)
        else:
            with st.expander(sec.title, expanded=False):   # Streamlit 自帶展開箭頭；不再加文字「▸」（雙箭頭）
                _md(rows)


def render_page(vm: PageVM) -> None:
    render_title(vm)
    _md(first_screen_html(vm.context.first_screen))      # 第一屏四問（主 CTA：disabled 示意）
    render_cards(vm)
    render_sections(vm)
