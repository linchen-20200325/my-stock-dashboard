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
from shared.ui2_contract.quote_view import QuoteView, QuoteViewState, build_quote_view
from shared.ui2_contract.target_selection import parse_ticker_input
from shared.ui2_contract.text import LOOKUP_INPUT_LABEL, LOOKUP_SUBMIT_LABEL
from src.ui2.components.html import (
    LOOKUP_P1_STATES, lookup_result_html, lookup_status_html, search_html, target_first_screen_html,
)
from src.ui2.views._page import _md, render_cards, render_sections, render_title

KEY_TARGET_MODE = "ui2_target_mode"       # 純 UI 狀態（目前展開的模式）
KEY_TARGET_MODE_BOX = "ui2_target_mode_box"   # container key（CSS／量測錨點；非 session_state）
# ── 股票代號輸入（B-UI2-LOOKUP-P1-INPUT-1；功能開關預設關，開關由 app_ui2.py 讀取後以參數注入，本檔不讀 secrets／環境）──
KEY_LOOKUP_FORM = "ui2_lookup_form"           # st.form key（非 session_state）
KEY_LOOKUP_TEXT = "ui2_lookup_text"           # text_input widget（字串）
KEY_LOOKUP_STATE = "ui2_lookup_state"         # 只存安全枚舉字串（QuoteViewState.value）；⛔ 物件
KEY_LOOKUP_SYMBOL = "ui2_lookup_symbol"       # 只存已解析代號字串（無效／空＝""）


def lookup_submission_view(raw: object) -> QuoteView:
    """提交時的唯一處理：驗證代號 → 畫面狀態。P1 無資料（loaded=False）⇒ 只會得到 SELECTION_INVALID 或 NOT_LOADED。"""
    return build_quote_view(parse_ticker_input(raw), loaded=False, fetch_error=None, close=None,
                            trade_date=None, fetched_at=None, source=None, is_stale=False)


def _render_lookup_input(placeholder: str) -> None:
    """頂端輸入元件：st.form（僅在 submit 時處理一次）。⛔ 取數／持股／Sheet；『加入觀察』維持 disabled（在結果區，未動）。"""
    with st.form(KEY_LOOKUP_FORM, border=False):
        raw = st.text_input(LOOKUP_INPUT_LABEL, key=KEY_LOOKUP_TEXT, placeholder=placeholder,
                            label_visibility="collapsed")
        submitted = st.form_submit_button(LOOKUP_SUBMIT_LABEL)
    if submitted:                                   # 未提交＝不驗證、不呼叫 parse
        view = lookup_submission_view(raw)
        st.session_state[KEY_LOOKUP_STATE] = view.state.value
        st.session_state[KEY_LOOKUP_SYMBOL] = view.symbol or ""
    try:
        state = QuoteViewState(st.session_state.get(KEY_LOOKUP_STATE, QuoteViewState.NOT_LOADED.value))
    except ValueError:
        state = QuoteViewState.NOT_LOADED
    if state not in LOOKUP_P1_STATES:
        state = QuoteViewState.NOT_LOADED
    _md(lookup_status_html(state, st.session_state.get(KEY_LOOKUP_SYMBOL) or None))


def render(vm: PageVM) -> None:
    """現行標的頁（簽名維持 `render(vm)`；功能開關關閉時唯一入口，輸出與改動前逐元素相同）。"""
    _render(vm, lookup_input=False)


def render_with_lookup(vm: PageVM) -> None:
    """功能開關開啟時的獨立入口（由 `shell/app.py` 在旗標開時改呼叫；⛔ 不經 `VIEWS`）：頂端以股票代號輸入元件取代 disabled searchbox。"""
    _render(vm, lookup_input=True)


def _render(vm: PageVM, *, lookup_input: bool) -> None:
    t = vm.context.target
    assert t is not None, "target 頁 VM 缺 TargetVM"
    mode = vm.slice.active_mode or t.default_mode
    labels = {m.mode_id: m.label for m in t.modes}
    render_title(vm, mode=mode)
    # ① 模式切換（W-3：兩模式都外露搜尋框；膠囊式 radio，與導覽同一套 DOM 無關 CSS 技巧）
    with st.container(key=KEY_TARGET_MODE_BOX):
        st.radio("模式", [m.mode_id for m in t.modes], key=KEY_TARGET_MODE, horizontal=True,
                 format_func=lambda m: labels[m], label_visibility="collapsed")
    # ② 搜尋框＋搜尋 CTA（兩模式都在）。lookup_input 預設關＝與原路徑逐字相同；開＝頂端輸入元件取代 disabled searchbox。
    if lookup_input:
        _render_lookup_input(t.search.placeholder)
    else:
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
        if t.lookup.queried:
            render_sections(vm, mode=MODE_LOOKUP, extra=t.lookup.sections)
