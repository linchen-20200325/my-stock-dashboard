"""New UI2 Preview 殼：Preview 控制（資料來源／fake 場景）＋四頁導覽＋派發。

session key 僅限 `ui2_` 前綴的純 UI 狀態（目前頁、場景、資料來源）；⛔ 寫任何投資狀態 key。
資料來源（`ui2_feed`）：預設 FAKE（`src.services.ui2.preview_feed`，既有行為不變）；
Real-data Preview（NUI2-REAL-FEED）＝`src.services.ui2.real_feed`（唯讀；每 rerun 讀一次、四頁共用）
→ `real_canonical`（純）→ 既有 VM builder。⛔ 不觸發更新、不呼叫 producer、⛔ 把整包 session_state 傳出去。
"""
from __future__ import annotations

import streamlit as st

from shared.ui2_contract.pages import (
    ACCOUNT_IDS, ACCOUNT_SIGNED_IN, ACCOUNT_SIGNED_OUT, ACCOUNT_UNAVAILABLE, FEED_FAKE, FEED_IDS, FEED_REAL,
    PAGE4_LABELS, PAGE_IDS, SCENARIO_IDS,
)
from src.services.ui2.preview_feed import DEFAULT_SCENARIO, get_preview_page_vm
from src.services.ui2.real_canonical import get_real_page_vm
from src.services.ui2.real_feed import read_real_snapshot
from shared.ui2_contract.text import PREVIEW_BANNER_NOTE, REAL_PREVIEW_BANNER_NOTE
from src.ui2.components.html import banner_html
from src.ui2.shell.css import CSS
from src.ui2.views import VIEWS

KEY_PAGE = "ui2_page"
KEY_SCENARIO = "ui2_scenario"
KEY_NAV = "ui2_nav"          # container key（CSS 錨點 `.st-key-ui2_nav`；非 session_state）
KEY_ACCOUNT = "ui2_account"            # 👤 我的頁 FAKE 帳戶狀態（Preview 控制；純 UI 狀態）
KEY_TARGET_MODE = "ui2_target_mode"    # 🎯 標的頁模式（widget 在 views/target.py；須與該檔常數相同）
KEY_FEED = "ui2_feed"                  # 資料來源（FAKE／Real-data Preview；Preview 控制；純 UI 狀態）

_FEED_LABELS = {
    FEED_FAKE: "FAKE 場景（預設）", FEED_REAL: "Real-data Preview（唯讀；只接 2 項真資料）",
}

_ACCOUNT_LABELS = {
    ACCOUNT_SIGNED_IN: "signed-in（已登入）", ACCOUNT_SIGNED_OUT: "signed-out（尚未登入）",
    ACCOUNT_UNAVAILABLE: "unavailable（Sheet 讀取失敗）",
}

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
    if KEY_ACCOUNT not in st.session_state:
        st.session_state[KEY_ACCOUNT] = ACCOUNT_SIGNED_IN
    if KEY_FEED not in st.session_state:
        st.session_state[KEY_FEED] = FEED_FAKE
    real = st.session_state[KEY_FEED] == FEED_REAL
    if real:
        # 每 rerun 只讀一次；只建目前頁的 VM（四頁共用同一個 snapshot 函式與轉換，位階三處同一次呼叫結果）。
        vm = get_real_page_vm(st.session_state[KEY_PAGE], read_real_snapshot(),
                              mode=st.session_state.get(KEY_TARGET_MODE))
    else:
        vm = get_preview_page_vm(st.session_state[KEY_PAGE], st.session_state[KEY_SCENARIO],
                                 mode=st.session_state.get(KEY_TARGET_MODE),
                                 account=st.session_state[KEY_ACCOUNT])
    if vm.banner_text:
        note = PREVIEW_BANNER_NOTE if vm.is_fake else REAL_PREVIEW_BANNER_NOTE
        st.markdown(banner_html(vm.banner_text, note), unsafe_allow_html=True)
    VIEWS[st.session_state[KEY_PAGE]](vm)
    # Real 模式標題不出現 fake 字樣（QA P3）；兩種模式都以「Preview 控制」開頭（量測腳本錨點）。
    with st.expander("Preview 控制（資料來源）" if real else "Preview 控制（資料來源／fake 場景）", expanded=False):
        st.selectbox("資料來源（feed）", FEED_IDS, key=KEY_FEED, format_func=lambda f: _FEED_LABELS[f])
        # Real-data Preview 時 FAKE 維度不適用：保留 widget（狀態不丟），但 disabled。
        st.selectbox("場景", SCENARIO_IDS, key=KEY_SCENARIO, disabled=real,
                     format_func=lambda s: _SCENARIO_LABELS[s])
        # label 固定（避免切換模式時 widget 身分改變而丟狀態），且兩種模式都不帶 fake 字樣（QA P3）。
        st.selectbox("帳戶狀態（👤 我的頁，示意場景）", ACCOUNT_IDS, key=KEY_ACCOUNT, disabled=real,
                     format_func=lambda a: _ACCOUNT_LABELS[a])
    # W-1：固定四頁導覽（手機＝底部固定四格、桌機＝左側四項；位置由 CSS 決定，見 shell/css.py）。
    # 放在內容之後：視覺位置由 `position:fixed` 決定，DOM 順序＝手機底部列的 Tab 順序（內容→導覽）。
    # 用 `st.container(key=...)`（Streamlit ≥1.39 加 `st-key-ui2_nav` class）當唯一 CSS 錨點；
    # 元件仍是 `st.radio`（key=`ui2_page`；原生 radiogroup／aria-checked＝當前頁語意；AppTest 可切頁）。
    with st.container(key=KEY_NAV):
        st.radio("導覽", PAGE_IDS, key=KEY_PAGE, horizontal=True,
                 format_func=lambda p: PAGE4_LABELS[p], label_visibility="collapsed")
