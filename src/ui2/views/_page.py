"""四頁共用的 PageVM 渲染骨架（第一屏四問 → 核心卡 → L1/L2/L3 區塊）。

Preview 標示（banner）由殼在導覽**之前**統一渲染（頁面頂部），本檔不重複渲染。
"""
from __future__ import annotations

from html import escape

import streamlit as st

from shared.ui2_contract.models import PageVM
from src.ui2.components.html import field_row_html, first_screen_html, metric_card_html


def _md(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def render_page(vm: PageVM) -> None:
    _md(f'<div class="ui2-pagetitle">{escape(vm.title)}</div>')
    _md(first_screen_html(vm.context.first_screen))      # ①②③④（④ Preview：disabled 示意）
    visible = set(vm.slice.visible_card_ids)
    cards = [c for c in vm.context.cards if c.card_id in visible]
    if cards:
        _md('<div class="ui2-grid">' + "".join(metric_card_html(c) for c in cards) + "</div>")
    for sec in vm.context.sections:
        rows = "".join(field_row_html(f) for f in sec.fields)
        if sec.level == "L1":
            _md(f'<div class="ui2-section-title">{escape(sec.title)}</div>' + rows)
        else:
            with st.expander(f"▸ {sec.title}", expanded=False):
                _md(rows)
