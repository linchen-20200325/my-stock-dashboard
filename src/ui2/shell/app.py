"""New UI2 Preview 殼：Preview 控制（fake 場景）＋四頁導覽＋派發。

session key 僅限 `ui2_` 前綴的純 UI 狀態（目前頁、場景）；⛔ 寫任何投資狀態 key。
Preview 期資料來源＝`src.services.ui2.preview_feed`（FAKE）；⛔ 不取真資料、不呼叫 producer。
"""
from __future__ import annotations

import streamlit as st

from shared.ui2_contract.pages import PAGE4_LABELS, PAGE_IDS, SCENARIO_IDS
from src.services.ui2.preview_feed import DEFAULT_SCENARIO, get_preview_page_vm
from shared.ui2_contract.text import PREVIEW_BANNER_NOTE
from src.ui2.components.html import banner_html
from src.ui2.shell.css import CSS
from src.ui2.views import VIEWS

KEY_PAGE = "ui2_page"
KEY_SCENARIO = "ui2_scenario"
KEY_NAV = "ui2_nav"          # container key（CSS 錨點 `.st-key-ui2_nav`；非 session_state）

_SCENARIO_LABELS = {
    "cold": "冷啟動（未載入）", "loaded": "已載入", "missing": "Missing（資料未取得／未備）",
    "stale": "Stale（過期）", "unavailable": "Unavailable（來源不可用）",
    "not_evaluated": "Not evaluated／無法判定（兩者不同態）",
}


def run() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if KEY_PAGE not in st.session_state:
        st.session_state[KEY_PAGE] = PAGE_IDS[0]
    if KEY_SCENARIO not in st.session_state:
        st.session_state[KEY_SCENARIO] = DEFAULT_SCENARIO
    # Preview 標示放頁面最頂（導覽之前）；VM 依目前 session 的頁／場景取得（皆 ui2_ 純 UI 狀態）。
    vm = get_preview_page_vm(st.session_state[KEY_PAGE], st.session_state[KEY_SCENARIO])
    if vm.banner_text:
        st.markdown(banner_html(vm.banner_text, PREVIEW_BANNER_NOTE), unsafe_allow_html=True)
    VIEWS[st.session_state[KEY_PAGE]](vm)
    with st.expander("Preview 控制（fake 場景）", expanded=False):
        st.selectbox("場景", SCENARIO_IDS, key=KEY_SCENARIO,
                     format_func=lambda s: _SCENARIO_LABELS[s])
    # W-1：固定四頁導覽（手機＝底部固定四格、桌機＝左側四項；位置由 CSS 決定，見 shell/css.py）。
    # 放在內容之後：視覺位置由 `position:fixed` 決定，DOM 順序＝手機底部列的 Tab 順序（內容→導覽）。
    # 用 `st.container(key=...)`（Streamlit ≥1.39 加 `st-key-ui2_nav` class）當唯一 CSS 錨點；
    # 元件仍是 `st.radio`（key=`ui2_page`；原生 radiogroup／aria-checked＝當前頁語意；AppTest 可切頁）。
    with st.container(key=KEY_NAV):
        st.radio("導覽", PAGE_IDS, key=KEY_PAGE, horizontal=True,
                 format_func=lambda p: PAGE4_LABELS[p], label_visibility="collapsed")
