"""target 頁 view：只渲染 PageVM。

雙模式（Freeze §3／§16.2）：頂部 `市場精選｜即時查一檔` 切換，**不得同時完整展開**——
切換只改呈現切片（`PresentationSlice.active_mode`），兩個模式的內容仍都在 `PageVM.context`。
Ad-hoc 查詢＝session-only：本檔只寫 `ui2_` 前綴的純 UI 狀態（模式）；⛔ 持股／觀察／候選池／strategy／Sheet。
搜尋框與搜尋 CTA 在 Preview 為 disabled 示意（⛔ 真查詢／real-data fetch）。
"""
from __future__ import annotations

import streamlit as st

from html import escape

from shared.ui2_contract.local_lookup_request import (
    OP_LIST, OP_QUERY, REASON_BAD_REQUEST, REASON_FILE_INVALID, REASON_FILE_NOT_REGULAR, REASON_FILE_TOO_LARGE,
    REASON_FILE_UNREADABLE, REASON_NO_REQUEST_CONTEXT, REASON_PARSE_FAILED, LocalLookupRequest, LocalLookupResponse,
    LocalProof, build_local_proof,
)
from shared.ui2_contract.local_lookup_result import (
    TEXT_LOCAL_FAILED_CHIP, TEXT_LOCAL_FAILED_NOTICE, TEXT_LOCAL_FILE_LABEL, TEXT_LOCAL_NO_FILES, TEXT_LOCAL_UNAVAILABLE,
)
from shared.ui2_contract.models import PageVM
from shared.ui2_contract.pages import MODE_CURATED, MODE_LOOKUP
from shared.ui2_contract.quote_view import QuoteView, QuoteViewState, build_quote_view
from shared.ui2_contract.target_selection import parse_ticker_input
from shared.ui2_contract.text import LOOKUP_INPUT_LABEL, LOOKUP_SUBMIT_LABEL
from shared.ui2_contract.tones import ChipTone
from src.services.ui2.real_canonical import exception_code
from src.ui2.components.html import (
    LOOKUP_P1_STATES, chip_html, local_lookup_result_html, lookup_result_html, lookup_status_html, search_html,
    target_first_screen_html,
)
from src.ui2.views._page import _md, render_cards, render_sections, render_title

KEY_TARGET_MODE = "ui2_target_mode"       # 純 UI 狀態（目前展開的模式）
KEY_TARGET_MODE_BOX = "ui2_target_mode_box"   # container key（CSS／量測錨點；非 session_state）
# ── 股票代號輸入（B-UI2-LOOKUP-P1-INPUT-1；功能開關預設關，開關由 app_ui2.py 讀取後以參數注入，本檔不讀 secrets／環境）──
KEY_LOOKUP_FORM = "ui2_lookup_form"           # st.form key（非 session_state）
KEY_LOOKUP_TEXT = "ui2_lookup_text"           # text_input widget（字串）
KEY_LOOKUP_STATE = "ui2_lookup_state"         # 只存安全枚舉字串（QuoteViewState.value）；⛔ 物件
KEY_LOOKUP_SYMBOL = "ui2_lookup_symbol"       # 只存已解析代號字串（無效／空＝""）
# ── 本機日K檔查詢（M2；僅 `render_with_local_lookup`；L6 以參數注入 callable，本檔不 import L1／L2／L3）──
KEY_LOCAL_FILE = "ui2_local_file"             # selectbox（只存 basename 字串；選項來自注入 callable 的 list 回應）
KEY_LOCAL_QUERIED = "ui2_local_queried"       # "1"＝最近一次提交有效（只是旗標字串；⛔ 不存 vm／資料／檔案內容）


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


# ════════════════════════════════════════════════════════════════════
# 本機日K檔查詢：L5 邊界（P-M2j §三）。全是小純函式／極薄 Streamlit 讀取，便於單測。
# ⛔ 零檔案系統動作：任何拒絕都發生在呼叫注入的 callable 之前；⛔ 不輸出例外原文／路徑／檔名以外內容。
# ════════════════════════════════════════════════════════════════════
#: 邊界拒絕或 L3 失敗時，顯示為紅色「讀取失敗」的原因碼（系統真的讀不到／檔案本身有問題）；其餘一律灰色「無法使用」。
LOCAL_FAILED_CODES = frozenset({REASON_FILE_INVALID, REASON_FILE_NOT_REGULAR, REASON_FILE_TOO_LARGE,
                                REASON_FILE_UNREADABLE, REASON_PARSE_FAILED})


def derive_local_proof(raw_headers: object, bind_address: object) -> tuple[LocalProof | None, str | None]:
    """由 `st.context.headers`（原始物件）與 `server.address` 取 `LocalProof`；失敗回 `(None, reason_code)`（⛔ 呼叫 L3）。

    - 無 `get_all`（含 None、一般 dict）→ `no_request_context`；
    - `get_all("host")` 筆數：0 → `no_request_context`；≥2 → `bad_request`（StreamlitHeaders 同名多值只回第一個，故必須先數）；
    - 單一 Host 值＋其餘標頭的第一個值組成 mapping，交 `build_local_proof`；ValueError／TypeError → `bad_request`。
    ⛔ 本函式不判斷是否本機（那是 L3 的事）。"""
    get_all = getattr(raw_headers, "get_all", None)
    if not callable(get_all):
        return None, REASON_NO_REQUEST_CONTEXT
    try:
        hosts = get_all("host")
    except Exception:  # noqa: BLE001 — 取不到＝無法證明；固定碼
        return None, REASON_BAD_REQUEST
    if not isinstance(hosts, (list, tuple)):
        return None, REASON_BAD_REQUEST
    if len(hosts) == 0:
        return None, REASON_NO_REQUEST_CONTEXT
    if len(hosts) != 1 or not isinstance(hosts[0], str):
        return None, REASON_BAD_REQUEST
    try:
        mapping = {"host": hosts[0]}
        for k in raw_headers:                                   # type: ignore[attr-defined]
            if isinstance(k, str) and k.strip().lower() != "host":
                mapping[k] = raw_headers[k]                     # type: ignore[index]
        return build_local_proof(bind_address, mapping), None
    except (ValueError, TypeError):
        return None, REASON_BAD_REQUEST
    except Exception:  # noqa: BLE001 — 其他任何讀取失敗亦不洩漏
        return None, REASON_BAD_REQUEST


def _read_proof() -> tuple[LocalProof | None, str | None]:
    """極薄的 Streamlit 讀取（取不到＝None，不 raise；L5 不讀環境／secrets）。"""
    try:
        raw = st.context.headers
    except Exception:  # noqa: BLE001
        raw = None
    try:
        bind = st.get_option("server.address")
    except Exception:  # noqa: BLE001
        bind = None
    return derive_local_proof(raw, bind)


def _fail_response(op: str, code: str) -> LocalLookupResponse:
    return LocalLookupResponse(op=op, ok=False, reason_code=code)


def call_local(local_lookup, op: str, *, symbol: str | None = None, filename: str | None = None) -> LocalLookupResponse:
    """**唯一**呼叫注入 callable 的位置（list／query 都經這裡；測試以 AST 鎖定本檔只有一個對 `local_lookup` 的呼叫）。

    每次呼叫都：① 重新取證據（`derive_local_proof`；拒絕＝固定碼，⛔ 不呼叫 callable、零檔案系統動作）→ ② 建 `LocalLookupRequest`
    （ValueError／TypeError → `bad_request`）→ ③ 以 `try/except Exception` 呼叫 callable（任何例外 → 固定碼 `file_unreadable`，
    只 log 例外類別名；⛔ 訊息、⛔ 顯示）→ ④ 回傳型別／op 不符 → 同一固定碼。"""
    proof, code = _read_proof()
    if proof is None:
        return _fail_response(op, code or REASON_BAD_REQUEST)
    try:
        request = LocalLookupRequest(op=op, proof=proof, symbol=symbol, filename=filename)
    except (ValueError, TypeError):
        return _fail_response(op, REASON_BAD_REQUEST)
    try:
        resp = local_lookup(request)
    except Exception as e:  # noqa: BLE001 — 本邊界唯一的寬例外；固定分類
        print(f"[ui2.local_lookup] failed: {exception_code(e)}")
        return _fail_response(op, REASON_FILE_UNREADABLE)
    if not isinstance(resp, LocalLookupResponse) or resp.op != op:
        print("[ui2.local_lookup] failed: bad_response")
        return _fail_response(op, REASON_FILE_UNREADABLE)
    return resp


def local_notice_html(code: str) -> str:
    """失敗／拒絕的固定畫面：`FAILED_CODES`＝紅「讀取失敗」（沿用 `quote_view` 文案）；其餘＝灰單一句（不洩漏哪個檢查失敗）。"""
    if code in LOCAL_FAILED_CODES:
        chip = chip_html(TEXT_LOCAL_FAILED_CHIP, ChipTone.DANGER)
        detail = f'<span class="ui2-row__detail">{escape(TEXT_LOCAL_FAILED_NOTICE)}</span>'
    else:
        chip, detail = chip_html(TEXT_LOCAL_UNAVAILABLE, ChipTone.NEUTRAL_INFO), ""
    return (f'<div class="ui2-ll" data-ui2-l1="local_lookup_notice"><div class="ui2-ll__status">{chip} {detail}</div></div>')


def local_response_html(resp: LocalLookupResponse) -> str:
    """查詢回應 → HTML：有 vm（成功或 parse_failed 的缺值態）畫結果；否則依固定碼畫失敗／拒絕。"""
    if resp.vm is not None:
        return local_lookup_result_html(resp.vm)
    return local_notice_html(resp.reason_code or REASON_BAD_REQUEST)


def _render_local_block(placeholder: str, local_lookup, *, show_result: bool) -> str | None:
    """代號輸入＋本機日K檔選擇（同一個 form）。回傳要畫在結果區的 HTML（無則 None）。

    session_state 只寫 `ui2_` 前綴常數 key、值為 str；⛔ 存 vm／資料。每次渲染都重新 list（受控目錄可能變動）；
    已提交的查詢在後續 rerun 以同一組（代號、檔名）重查（不存結果）。清單不可用／空 → 退回原代號輸入＋固定說明。"""
    listing = call_local(local_lookup, OP_LIST)
    names = listing.filenames if listing.ok else ()
    if not listing.ok or not names:
        _render_lookup_input(placeholder)
        return local_notice_html(listing.reason_code or REASON_BAD_REQUEST) if not listing.ok else local_notice_html_no_files()
    if st.session_state.get(KEY_LOCAL_FILE) not in names:        # 檔案被移走／竄改：fail closed 回預設
        st.session_state.pop(KEY_LOCAL_FILE, None)
    with st.form(KEY_LOOKUP_FORM, border=False):
        raw = st.text_input(LOOKUP_INPUT_LABEL, key=KEY_LOOKUP_TEXT, placeholder=placeholder,
                            label_visibility="collapsed")
        st.selectbox(TEXT_LOCAL_FILE_LABEL, list(names), key=KEY_LOCAL_FILE)
        submitted = st.form_submit_button(LOOKUP_SUBMIT_LABEL)
    if submitted:
        view = lookup_submission_view(raw)
        st.session_state[KEY_LOOKUP_STATE] = view.state.value
        st.session_state[KEY_LOOKUP_SYMBOL] = view.symbol or ""
        st.session_state[KEY_LOCAL_QUERIED] = "1" if view.symbol else ""
    symbol = st.session_state.get(KEY_LOOKUP_SYMBOL) or ""
    filename = st.session_state.get(KEY_LOCAL_FILE)
    if st.session_state.get(KEY_LOCAL_QUERIED) == "1" and symbol and filename in names:
        if not show_result:
            return None
        return local_response_html(call_local(local_lookup, OP_QUERY, symbol=symbol, filename=filename))
    try:
        state = QuoteViewState(st.session_state.get(KEY_LOOKUP_STATE, QuoteViewState.NOT_LOADED.value))
    except ValueError:
        state = QuoteViewState.NOT_LOADED
    if state not in LOOKUP_P1_STATES:
        state = QuoteViewState.NOT_LOADED
    _md(lookup_status_html(state, symbol or None))
    return None


def local_notice_html_no_files() -> str:
    chip = chip_html(TEXT_LOCAL_NO_FILES, ChipTone.NEUTRAL_INFO)
    return f'<div class="ui2-ll" data-ui2-l1="local_lookup_notice"><div class="ui2-ll__status">{chip}</div></div>'


def render(vm: PageVM) -> None:
    """現行標的頁（簽名維持 `render(vm)`；功能開關關閉時唯一入口，輸出與改動前逐元素相同）。"""
    _render(vm, lookup_input=False)


def render_with_lookup(vm: PageVM) -> None:
    """功能開關開啟時的獨立入口（由 `shell/app.py` 在旗標開時改呼叫；⛔ 不經 `VIEWS`）：頂端以股票代號輸入元件取代 disabled searchbox。"""
    _render(vm, lookup_input=True)


def render_with_local_lookup(vm: PageVM, local_lookup) -> None:
    """本機日K檔查詢的獨立入口（由 `shell/app.py` 在 `local_lookup is not None` 時改呼叫；⛔ 不經 `VIEWS`）。
    `local_lookup`＝L6 注入的 callable（接 `LocalLookupRequest`、回 `LocalLookupResponse`）；L5 不 import L1／L2／L3。"""
    _render(vm, lookup_input=True, local_lookup=local_lookup)


def _render(vm: PageVM, *, lookup_input: bool, local_lookup=None) -> None:
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
    local_html = None
    if local_lookup is not None:
        local_html = _render_local_block(t.search.placeholder, local_lookup, show_result=(mode == MODE_LOOKUP))
    elif lookup_input:
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
    elif local_html is not None:
        _md(local_html)                                     # 本機查詢結果／固定失敗畫面（取代 FAKE 結果區）
    else:
        _md(lookup_result_html(t.lookup))
        if t.lookup.queried:
            render_sections(vm, mode=MODE_LOOKUP, extra=t.lookup.sections)
