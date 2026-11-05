"""New UI2 Preview 殼：四頁導覽＋派發；開發專用的 Preview 控制僅在 `?ui2_dev=1` 時顯示。

session key 僅限 `ui2_` 前綴的純 UI 狀態（目前頁、場景、資料來源）；⛔ 寫任何投資狀態 key。
資料來源（`ui2_feed`）：預設 FAKE（`src.services.ui2.preview_feed`，既有行為不變）；
Real-data Preview（NUI2-REAL-FEED）＝`src.services.ui2.real_feed`（唯讀；每 rerun 讀一次、四頁共用）
→ `real_canonical`（純）→ 既有 VM builder。⛔ 不觸發更新、不呼叫 producer、⛔ 把整包 session_state 傳出去。

Preview 控制的去向（Active Contract §6／DEC-130 (c)／UI Correction P1）：
- 預設（無旗標）**0 個** Preview 控制；預設值＝FAKE／loaded／帳戶預設態（`ui2_` session 預設）。
- `?ui2_dev=1`：在頁面內容之後、導覽之前畫一個虛線框、標明「🧪 開發／測試工具（非產品內容）」的獨立區塊
  （不是 expander、不在 sidebar、不新增導覽項、不佔桌機左導覽）。
- ⛔ `ui2_dev` 只決定「開發面是否顯示」；不是任何登入／授權證據（守衛 `check_ui2_dev_not_auth`、`T_new_9`）。
  帳戶場景只是 FAKE 示意，不是正式 auth contract（`NUI2-AUTH-CONTRACT-GATE`）。
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
from src.ui2.components.html import banner_html, drawer_account_html
from src.ui2.shell.css import CSS
from src.ui2.shell.drawer_js import render_drawer_script
from src.ui2.views import VIEWS

KEY_PAGE = "ui2_page"
KEY_SCENARIO = "ui2_scenario"
KEY_NAV = "ui2_nav"          # container key（CSS 錨點 `.st-key-ui2_nav`；非 session_state）
KEY_ACCOUNT = "ui2_account"            # 👤 我的頁 FAKE 帳戶狀態（Preview 控制；純 UI 狀態）
KEY_TARGET_MODE = "ui2_target_mode"    # 🎯 標的頁模式（widget 在 views/target.py；須與該檔常數相同）
KEY_FEED = "ui2_feed"                  # 資料來源（FAKE／Real-data Preview；Preview 控制；純 UI 狀態）
KEY_DEV_SURFACE = "ui2_dev_surface"    # 開發面 container key（CSS／測試錨點 `.st-key-ui2_dev_surface`；非 session_state）
DEV_FLAG_PARAM = "ui2_dev"             # 開發面旗標（query parameter）
DEV_SURFACE_TITLE = "🧪 開發／測試工具（非產品內容）"

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


def dev_surface_enabled() -> bool:
    """`?ui2_dev=1` → True。只決定開發面是否顯示；⛔ 其結果不得流入任何使用者身分或權限判斷。"""
    return st.query_params.get(DEV_FLAG_PARAM) == "1"


def _render_dev_surface(real: bool) -> None:
    """開發／測試專用區塊（僅 `?ui2_dev=1`）：資料來源／場景／帳戶示意態的切換。非產品內容。"""
    with st.container(key=KEY_DEV_SURFACE):
        st.markdown(f'<div class="ui2-dev__head" data-ui2-dev="1">{DEV_SURFACE_TITLE}</div>',
                    unsafe_allow_html=True)
        st.selectbox("資料來源（feed）", FEED_IDS, key=KEY_FEED, format_func=lambda f: _FEED_LABELS[f])
        # Real-data Preview 時 FAKE 維度不適用：保留 widget（狀態不丟），但 disabled。
        st.selectbox("場景", SCENARIO_IDS, key=KEY_SCENARIO, disabled=real,
                     format_func=lambda s: _SCENARIO_LABELS[s])
        # label 固定（避免切換模式時 widget 身分改變而丟狀態）。
        st.selectbox("帳戶狀態（👤 我的頁，示意場景）", ACCOUNT_IDS, key=KEY_ACCOUNT, disabled=real,
                     format_func=lambda a: _ACCOUNT_LABELS[a])


def run() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    dev = dev_surface_enabled()
    if KEY_PAGE not in st.session_state:
        st.session_state[KEY_PAGE] = PAGE_IDS[0]
    if KEY_SCENARIO not in st.session_state:
        st.session_state[KEY_SCENARIO] = DEFAULT_SCENARIO
    # 預設值（無開發面時也維持）：皆 ui2_ 純 UI 狀態。
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
    # 單行標示放頁面最頂（導覽之前）：FAKE＝示意資料、Real＝Real-data Preview（非正式 production default）。
    if vm.banner_text:
        note = PREVIEW_BANNER_NOTE if vm.is_fake else REAL_PREVIEW_BANNER_NOTE
        st.markdown(banner_html(vm.banner_text, note, note_hidden_on_mobile=not vm.is_fake), unsafe_allow_html=True)
    VIEWS[st.session_state[KEY_PAGE]](vm)
    if dev:
        _render_dev_surface(real)
    _render_nav()


#: ☰ 外層標籤輪替（降級用）：切頁後外層換標籤 → React 重建 checkbox → 收合。JS 被擋時唯一的自動收合路徑。
_WRAP_TAGS = ("div", "section", "article", "aside")
#: ☰＋遮罩（固定字串；`role=switch`＋原生 checked；⛔ 靜態 aria-expanded、⛔ aria-controls；☰ 符號 aria-hidden）。
#: 殼內唯一的 raw `<input>`（守衛 `tests/test_ui2_drawer_js_guard.py`）。
_TOGGLE_HTML = ('<input type="checkbox" id="ui2dr" class="ui2-dr-toggle" role="switch" aria-label="主選單">'
                '<label for="ui2dr" class="ui2-dr-btn" aria-hidden="true">☰</label>'
                '<label for="ui2dr" class="ui2-dr-scrim" aria-hidden="true"></label>')


def _render_nav() -> None:
    """W-1 導覽（DEC-134／DEC-137）：手機＝左上 ☰＋左側抽屜（預設收合）、桌機＝左側固定 rail；同一份 DOM、只靠 CSS 換呈現。

    放在內容之後（⛔ 在內容前新增 element container：會吃掉第一屏 ≥160px 餘裕）；視覺位置由 `position:fixed` 決定。
    用 `st.container(key=...)`（`st-key-ui2_nav` class）當唯一 CSS 錨點；元件仍是 `st.radio`（key=`ui2_page`；
    原生 radiogroup／checked＝當前頁語意；AppTest 可切頁）。⛔ 新增 session key；帳戶摘要固定占位（不讀 `ui2_account`）。
    """
    tag = _WRAP_TAGS[PAGE_IDS.index(st.session_state[KEY_PAGE])]
    st.markdown(f'<{tag} class="ui2-dr-wrap">{_TOGGLE_HTML}</{tag}>', unsafe_allow_html=True)
    with st.container(key=KEY_NAV):
        st.radio("導覽", PAGE_IDS, key=KEY_PAGE, horizontal=True,
                 format_func=lambda p: PAGE4_LABELS[p], label_visibility="collapsed")
        st.markdown(drawer_account_html(), unsafe_allow_html=True)
    render_drawer_script()
