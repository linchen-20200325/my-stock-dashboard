"""target 頁 view：只渲染 PageVM。

雙模式（Freeze §3／§16.2）：頂部 `市場精選｜即時查一檔` 切換，**不得同時完整展開**——
切換只改呈現切片（`PresentationSlice.active_mode`），兩個模式的內容仍都在 `PageVM.context`。
Ad-hoc 查詢＝session-only：本檔只寫 `ui2_` 前綴的純 UI 狀態（模式）；⛔ 持股／觀察／候選池／strategy／Sheet。
搜尋框與搜尋 CTA 在 Preview 為 disabled 示意（⛔ 真查詢／real-data fetch）。
"""
from __future__ import annotations

import streamlit as st

from shared.ui2_contract.models import PageVM
from shared.ui2_contract.pages import MODE_CURATED, MODE_LOOKUP
from src.ui2.components.html import (
    lookup_result_html, search_html, target_first_screen_html,
)
from src.ui2.views._page import _md, render_cards, render_sections, render_title

KEY_TARGET_MODE = "ui2_target_mode"       # 純 UI 狀態（目前展開的模式）
KEY_TARGET_MODE_BOX = "ui2_target_mode_box"   # container key（CSS／量測錨點；非 session_state）


def render(vm: PageVM) -> None:
    t = vm.context.target
    assert t is not None, "target 頁 VM 缺 TargetVM"
    mode = vm.slice.active_mode or t.default_mode
    labels = {m.mode_id: m.label for m in t.modes}
    render_title(vm, mode=mode)
    # ① 模式切換（W-3：兩模式都外露搜尋框；膠囊式 radio，與導覽同一套 DOM 無關 CSS 技巧）
    with st.container(key=KEY_TARGET_MODE_BOX):
        st.radio("模式", [m.mode_id for m in t.modes], key=KEY_TARGET_MODE, horizontal=True,
                 format_func=lambda m: labels[m], label_visibility="collapsed")
    # ② 搜尋框＋搜尋 CTA（兩模式都在）
    _md(search_html(t.search))
    # ③ 查詢摘要＋W-4 市場 context 一行＋②③（依模式取摘要；context 不變）
    summary = t.lookup.summary if mode == MODE_LOOKUP else vm.context.first_screen.current_state
    _md(target_first_screen_html(vm.context.first_screen, summary))
    # ④ 只展開目前模式
    if mode == MODE_CURATED:
        render_cards(vm, content_mode=MODE_CURATED)
        render_sections(vm, mode=MODE_CURATED)
    else:
        _md(lookup_result_html(t.lookup))
        render_sections(vm, mode=MODE_LOOKUP, extra=t.lookup.sections)
