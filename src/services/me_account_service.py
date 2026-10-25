"""src/services/me_account_service.py — 「👤 我的」頁的 L3 介面（L3 Service；👤 我的 P1，DEC-083）。

單一職責：替新版「👤 我的」頁回答三件事 —— **我用哪個 Google 帳號、這個 App 現在讀哪一本 Sheet、
這本 Sheet 裡分析的是哪一本組合／哪一份觀察清單** —— 並把使用者在那一頁按下的動作交給既有的 L1 契約。

客戶原文（DEC-083 C 段）：「首屏維持核准草稿方向：1. Google 帳號 2. 目前 Sheet 3. 這本 Sheet 內目前分析的
組合／觀察清單與哪些頁正在使用」「唯一本 Sheet 自動綁 取消。就算 Drive 只有一本：仍要使用者明確按『使用這本』。
不要替使用者做綁定決策。」

═══ 為什麼要有這一支（不是 pure pass-through）═══════════════════════════════
L5 `src/ui/views/` 不得直呼 L1（`tests/test_c3_layering_guard.py`；EX-PASSTHRU-1 白名單不含 views）。
本檔的編排：登入狀態四態判定＋email 遮罩、active Sheet 標題讀取的例外分類（登入／權限／找不到／配額／網路分開）、
Sheet 內容的「缺分頁／表頭不符／真的空／讀不到」分開回報（⛔ 讀不到不寫 0）、選定前先對清單核對名稱存在。

═══ 寫入邊界（⛔ 一律不寫使用者的 Sheet）═══════════════════════════════════
- 唯一會改狀態的動作：綁定（委派 L1 唯一寫入契約 `oauth_state.apply_sheet_binding`／被動文字框三步）、
  選定（L1 `set_active_selection`，只寫 session）、登出（L1 共用 `logout_google_session`）、
  重新讀取（L3 `reload_my_sheet_reads`，只換本人×這本 Sheet 的快取世代，⛔ 不 `.clear()`）。
- ⛔ 不呼叫任何 `save_*`／`delete_*`／`add_to_*`／`create_new_sheet`／`rename_sheet`／
  `append_forward_test_picks`／`clear_read_cache`（守衛：`tests/test_me_p1_services.py`）。
- ⛔ 不新增 OAuth scope、不新增資料源（Drive 清單沿用 L1 既有 `list_user_folders`／`list_user_sheets`）。

分層：L3 → L1（`gsheet_portfolio`／`oauth_state`）、L3 → L3（`portfolio_binding_service`）、L3 → L0（`shared.sheet_id`）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── 卡① Google 帳號：狀態代碼 ─────────────────────────────────────────────
ACCOUNT_NOT_CONFIGURED = "not_configured"   # 部署端沒設 OAuth（不是使用者的操作問題）
ACCOUNT_LOGGED_OUT = "logged_out"
ACCOUNT_EXPIRED = "expired"                 # 自動恢復的登入逾時（不是故障）
ACCOUNT_LOGGED_IN = "logged_in"
ACCOUNT_READ_FAILED = "read_failed"         # 讀登入狀態本身拋例外 / OAuth 模組載不進來

#: 標題讀取「因為沒登入」而沒讀（灰，不是故障）。其餘狀態沿用 L1 `READ_*` 代碼。
TITLE_LOGIN_REQUIRED = "login_required"

#: 卡③ 原因代碼（值同 L1 `READ_WORKSHEET_MISSING` / `READ_SCHEMA_MISMATCH`；L5 不 import L1，經本檔取）。
ISSUE_WORKSHEET_MISSING = "worksheet_missing"
ISSUE_SCHEMA_MISMATCH = "schema_mismatch"
#: 兩個分頁名（值同 L1 `_WORKSHEET_NAME` / `_STOCK_WATCHLIST_WORKSHEET`；一致性由 `tests/test_page_me.py` 釘住）。
PORTFOLIO_WORKSHEET = "portfolios"
WATCHLIST_WORKSHEET = "stock_watchlist"

#: 選定結果代碼。
SELECT_OK = "ok"
SELECT_NAME_MISSING = "name_missing"        # 名稱不在這本 Sheet 的清單裡 ⇒ ⛔ 不寫
SELECT_LIST_UNAVAILABLE = "list_unavailable"  # 清單讀不到 ⇒ 無從核對 ⇒ ⛔ 不寫
SELECT_NO_ACTIVE_SHEET = "no_active_sheet"


def mask_email(email) -> str:
    """`abcd@gmail.com` → `ab***@gmail.com`（帳號名留前 2 字、網域照留）。純函式。

    帳號名 ≤ 2 字 → 只留第 1 字；沒有 `@` → `***`（⛔ 不猜網域）；空 → 空字串。
    """
    _e = str(email or "").strip()
    if not _e:
        return ""
    _local, _at, _domain = _e.rpartition("@")
    if not _at or not _local or not _domain:
        return "***"
    _keep = _local[:2] if len(_local) > 2 else _local[:1]
    return f"{_keep}***@{_domain}"


@dataclass(frozen=True)
class AccountView:
    """卡① 的讀數。`login_url` 只在未登入 / 逾時且 OAuth 已設定時有值。"""

    state: str
    email_masked: str = ""
    login_url: str = ""
    error: str = ""


def get_account() -> AccountView:
    """登入狀態（純讀；未登入時會組登入網址 —— 那一步與側欄登入鈕相同，會在 server 端登記本 session 的 nonce）。"""
    try:
        from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1
        from src.data.portfolio import oauth_state as _ost       # L3→L1
    except Exception as _e:  # noqa: BLE001 — 模組載不進來 ≠ 沒登入（§1）
        return AccountView(state=ACCOUNT_READ_FAILED, error=repr(_e))
    try:
        if not _ost.is_oauth_configured():
            return AccountView(state=ACCOUNT_NOT_CONFIGURED)
        if _gsp._has_oauth_tokens():
            return AccountView(state=ACCOUNT_LOGGED_IN,
                               email_masked=mask_email(_ost.get_login_email()))
        _state = ACCOUNT_EXPIRED if _gsp.login_expired() else ACCOUNT_LOGGED_OUT
        return AccountView(state=_state, login_url=_ost.build_login_url())
    except Exception as _e:  # noqa: BLE001 — 讀不出來畫紅（⛔ 不畫成「未登入」）
        return AccountView(state=ACCOUNT_READ_FAILED, error=repr(_e))


def logout() -> None:
    """「🚪 登出」—— 與側欄同一支 L1 `logout_google_session`（Q5：登出後不自動恢復上一本）。"""
    from src.data.portfolio import oauth_state as _ost   # L3→L1
    _ost.logout_google_session()


# ── 卡② 目前 Sheet ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SheetView:
    """卡② 的讀數。

    `title_status`：空字串 = 這一輪沒有讀標題（沒有 active Sheet）；`READ_OK` / L1 `READ_ERROR_*` 代碼 /
    `TITLE_LOGIN_REQUIRED`。`title_error`：讀標題拋出、非 403/404 的例外 repr（呼叫端洗過才上畫面）。
    """

    active: object
    title_status: str = ""
    title: str = ""
    title_error: str = ""


def get_sheet_view() -> SheetView:
    """active Sheet ＋（有 active 且已登入時）它的標題。⛔ 只有 `ACTIVE_OK` 才讀標題（部署預設 / 不一致都不讀）。"""
    from src.services.portfolio_binding_service import ACTIVE_OK, get_active_sheet   # L3→L3

    _a = get_active_sheet()
    if _a.state != ACTIVE_OK:
        return SheetView(active=_a)
    from src.data.portfolio import gsheet_portfolio as _gsp   # L3→L1
    try:
        _status, _title = _gsp.read_sheet_title(_a.sheet_id)
    except Exception as _e:  # noqa: BLE001 — 分類後交給頁面（⛔ 不吞成「沒有標題」）
        _code = str(_gsp.classify_read_error(_e))
        if _code == _gsp.READ_ERROR_LOGIN_REQUIRED:
            return SheetView(active=_a, title_status=TITLE_LOGIN_REQUIRED)
        return SheetView(active=_a, title_status=_code, title_error=repr(_e))
    return SheetView(active=_a, title_status=_status, title=_title)


def bind_sheet(raw: str):
    """使用者明確按「✅ 使用這本」→ L1 唯一寫入契約 `apply_sheet_binding`（回 `SheetBindResult`）。

    ⛔ 只給「使用者按了」的路徑呼叫（on_click）；⛔ 本檔沒有任何「清單只有一本就自動綁」的路徑（DEC-083 C）。
    """
    from src.data.portfolio import oauth_state as _ost   # L3→L1
    return _ost.apply_sheet_binding(raw)


def prepare_paste_input(widget_key: str) -> None:
    """貼網址 / ID 文字框三步之①（L1 `prepare_sheet_input`；QA BLK-2 接法）。"""
    from src.data.portfolio import oauth_state as _ost
    _ost.prepare_sheet_input(widget_key)


def on_paste_change(widget_key: str) -> None:
    """三步之②：文字框 `on_change`（使用者真的改了文字才走到這裡 → 契約）。"""
    from src.data.portfolio import oauth_state as _ost
    _ost.on_sheet_input_change(widget_key)


def pop_paste_result(widget_key: str):
    """三步之③：取出這一輪的結果（`SheetBindResult` 或 None）。"""
    from src.data.portfolio import oauth_state as _ost
    return _ost.pop_sheet_input_result(widget_key)


def list_drive_folders() -> list[dict]:
    """Drive 資料夾（L1 既有 `list_user_folders`；未登入 → []）。失敗原樣上拋（呼叫端以 `drive_issue` 分類）。"""
    from src.data.portfolio import gsheet_portfolio as _gsp
    return list(_gsp.list_user_folders() or [])


def list_drive_sheets(folder_id: str = "") -> list[dict]:
    """Drive 裡的 Sheets（L1 既有 `list_user_sheets`）。失敗原樣上拋。⛔ 不在這裡挑任何一本。"""
    from src.data.portfolio import gsheet_portfolio as _gsp
    return list(_gsp.list_user_sheets(folder_id or "") or [])


def drive_issue(exc: BaseException) -> str:
    """Drive 列表例外 → 分類代碼。L1 `list_user_*` 把原始例外包成 `RuntimeError(...) from e` ⇒ 先看 `__cause__`。"""
    from src.data.portfolio import gsheet_portfolio as _gsp
    _root = exc.__cause__ if exc.__cause__ is not None else exc
    try:
        return str(_gsp.classify_read_error(_root))
    except Exception:  # noqa: BLE001
        return f"error:{type(_root).__name__}"


def reload_reads() -> int:
    """「🔄 重新讀取」：只失效**本人 × active Sheet** 的讀取快取（B5；⛔ 不 `.clear()`）。沒有 active → 0。"""
    from src.services.portfolio_binding_service import (
        ACTIVE_OK,
        get_active_sheet,
        reload_my_sheet_reads,
    )
    _a = get_active_sheet()
    return reload_my_sheet_reads(_a.sheet_id) if _a.state == ACTIVE_OK else 0


# ── 卡③ 這本 Sheet 的內容 ──────────────────────────────────────────────────
@dataclass(frozen=True)
class SheetContents:
    """卡③ 的讀數。**`None` = 未知（沒讀到），⛔ 不是 0 本**；`()` = 讀到了、真的沒有。

    `*_issue`：沒讀到的原因代碼（L1 `classify_read_error`：`worksheet_missing` / `schema_mismatch` /
    `permission_denied` / `sheet_not_found` / `quota_exceeded` / `network` / `login_required` / `error:<型別>`）。
    `*_error`：例外 repr（呼叫端洗過才上畫面）。
    `selection`：`portfolio_binding_service.ActiveSelection`（名稱是否存在由 `portfolio_selected_ok` 等判）。
    """

    sheet_id: str
    portfolios: "tuple[str, ...] | None" = None
    portfolio_issue: str = ""
    portfolio_error: str = ""
    watchlists: "tuple[str, ...] | None" = None
    watchlist_issue: str = ""
    watchlist_error: str = ""
    selection: object = field(default=None)


def _read_names(fn, sheet_id: str) -> "tuple[tuple[str, ...] | None, str, str]":
    from src.data.portfolio import gsheet_portfolio as _gsp
    try:
        return tuple(fn(sheet_id=sheet_id, raise_if_missing=True) or ()), "", ""
    except Exception as _e:  # noqa: BLE001 — 分類交給頁面（⛔ 不寫 0）
        try:
            _code = str(_gsp.classify_read_error(_e))
        except Exception:  # noqa: BLE001
            _code = f"error:{type(_e).__name__}"
        return None, _code, repr(_e)


def get_sheet_contents(sheet_id: str) -> SheetContents:
    """`sheet_id` 那本的組合名 / 觀察清單名（都是**純讀**，B1 起分頁不存在不會被建出來）＋目前選定。"""
    from src.data.portfolio import gsheet_portfolio as _gsp
    from src.services.portfolio_binding_service import get_active_selection

    _pf, _pf_issue, _pf_err = _read_names(_gsp.list_portfolios, sheet_id)
    _wl, _wl_issue, _wl_err = _read_names(_gsp.list_stock_watchlists, sheet_id)
    return SheetContents(sheet_id=sheet_id, portfolios=_pf, portfolio_issue=_pf_issue,
                         portfolio_error=_pf_err, watchlists=_wl, watchlist_issue=_wl_issue,
                         watchlist_error=_wl_err, selection=get_active_selection(sheet_id))


def read_status_codes() -> "tuple[str, str, str, str, str]":
    """`(READ_OK, 找不到, 沒權限, 配額, 網路)` 代碼（SSOT 在 L1；給 L5 挑白話句用）。純讀常數。"""
    from src.data.portfolio import gsheet_portfolio as _gsp
    return (_gsp.READ_OK, _gsp.READ_ERROR_SHEET_NOT_FOUND, _gsp.READ_ERROR_PERMISSION_DENIED,
            _gsp.READ_ERROR_QUOTA_EXCEEDED, _gsp.READ_ERROR_NETWORK)


def worksheet_headers() -> "dict[str, tuple[str, ...]]":
    """兩個分頁應有的第一列（L1 SSOT；給「表頭不符」那一句用）。純讀常數。"""
    from src.data.portfolio import gsheet_portfolio as _gsp
    return {_gsp._WORKSHEET_NAME: tuple(_gsp._HEADERS),
            _gsp._STOCK_WATCHLIST_WORKSHEET: tuple(_gsp._STOCK_WATCHLIST_HEADERS)}


def _active_ok_sheet() -> str:
    from src.services.portfolio_binding_service import ACTIVE_OK, get_active_sheet
    _a = get_active_sheet()
    return _a.sheet_id if _a.state == ACTIVE_OK else ""


def _select(kind: str, name: str, list_fn_name: str, *, skip: bool = False) -> str:
    from src.data.portfolio import gsheet_portfolio as _gsp
    from src.data.portfolio import oauth_state as _ost
    _sid = _active_ok_sheet()
    if not _sid:
        return SELECT_NO_ACTIVE_SHEET
    if not skip:
        _names, _issue, _err = _read_names(getattr(_gsp, list_fn_name), _sid)
        if _names is None:
            return SELECT_LIST_UNAVAILABLE
        if str(name or "").strip() not in _names:
            return SELECT_NAME_MISSING
    _ost.set_active_selection(kind, name, _sid, skip=skip)
    return SELECT_OK


def select_portfolio(name: str) -> str:
    """使用者明確選一本組合（名稱必須真的在 active Sheet 的清單裡，否則 ⛔ 不寫）。回 `SELECT_*`。"""
    from shared.sheet_id import SELECTION_KIND_PORTFOLIO
    return _select(SELECTION_KIND_PORTFOLIO, name, "list_portfolios")


def select_watchlist(name: str = "", *, skip: bool = False) -> str:
    """使用者明確選一份觀察清單，或 `skip=True`（「不使用觀察清單」）。回 `SELECT_*`。"""
    from shared.sheet_id import SELECTION_KIND_WATCHLIST
    return _select(SELECTION_KIND_WATCHLIST, name, "list_stock_watchlists", skip=skip)


def clear_portfolio_selection() -> None:
    """「取消選定」組合。"""
    from shared.sheet_id import SELECTION_KIND_PORTFOLIO
    from src.data.portfolio import oauth_state as _ost
    _ost.clear_active_selection(SELECTION_KIND_PORTFOLIO)


def clear_watchlist_selection() -> None:
    """「取消選定」觀察清單（回到「還沒選」—— 與「不使用觀察清單」不同）。"""
    from shared.sheet_id import SELECTION_KIND_WATCHLIST
    from src.data.portfolio import oauth_state as _ost
    _ost.clear_active_selection(SELECTION_KIND_WATCHLIST)
