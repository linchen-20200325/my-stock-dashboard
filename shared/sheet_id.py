"""shared/sheet_id.py — Google Sheet ID 解析 / 消毒 SSOT（L0，Sheet Safety 批 B3／B4）。

純函式＋常數，零 I/O、零 streamlit。使用端（**全 repo 只准這一份 parser**，守衛見
`tests/test_sheet_safety_guards.py`）：
- L1 `src/data/portfolio/oauth_state.py`（綁定寫入契約 `apply_sheet_binding`、state 便車消毒）
- L1 `src/data/portfolio/gsheet_portfolio.py`（session key 常數）
- L5 `src/ui/tabs/portfolio_manager.parse_sheet_id`（舊介面薄殼，委派本檔）
- 👤 我的 P1（DEC-083）另放：ID 末 6 碼顯示（Q4）、active portfolio／watchlist 選定的 session key（Q7）、
  共用登出另清的 session key（Q5）—— 見檔尾專段

為什麼要有這一份（客戶 2026-10-25 DEC-083 B3，原文）
====================================================
「目前發布連結可能解析成 "e"。……建立單一 Sheet ID parser。不得再保留多份互相不同的 parser 行為。」
修前有三份互不相同的解析：`app.py` 側欄與 `portfolio_binder` 用 `/spreadsheets/d/([a-zA-Z0-9_-]+)`
（發布連結 `/spreadsheets/d/e/2PACX…` → 抓到 `e`，再拿 `e` 當 Sheet ID 綁上去）；
`portfolio_manager.parse_sheet_id` 另外擋了 `/d/e/`；`oauth_state` 只做字母集消毒。

規則（判斷順序固定，⛔ 不猜）
============================
1. 空 / 只有空白 → `empty`。
2. 網址含 `/spreadsheets/(u/<數字>/)?d/e` 且 `e` 後面是 `/`、`?`、`#` 或字串結尾 → `published_link`。
   發布 token（`2PACX-…`）**不是** spreadsheet ID，⛔ 不嘗試轉換（沒有安全的轉換法）。
   ⚠️ 「`e` 後面要接分隔符」：真 ID 以 `e` 開頭（例 `/d/eAbc…`）時不可誤判成發布連結。
3. 網址含 `/spreadsheets/(u/<數字>/)?d/<片段>` → 取 `<片段>`（到下一個 `/`、`?`、`#` 為止）再消毒；
   消毒不過 → `invalid`。
4. 其他 → 整串（去頭尾空白）消毒；不過 → `invalid`（例：drive.google.com 檔案網址、`key=` 舊格式、
   含空白、HTML、全形字、超過長度上限）。

消毒（`sanitize_sheet_id`）＝ 只放行 `SHEET_ID_RE`（`[A-Za-z0-9_-]{1,120}`）完整比對；其餘回空字串。
自 `oauth_state._SHEET_ID_RE` 原樣搬來（字母集、長度界一字未改）。
**唯一的例外**：單一字元 `e`（`LEGACY_PUBLISH_LINK_ARTEFACT`）一律拒絕 —— 那正是修前 bug 把發布連結
`/spreadsheets/d/e/…` 解析出來的值，已被綁定、寫進 `?sheet=e` 書籤的人，重新整理時不得再被還原成
Sheet ID（QA N-5，2026-10-25）。⚠️ 只擋這一個字面值，⛔ 不是「太短就拒絕」的長度規則（不發明規則；
其他短字串照舊放行，見交付報告 NB-6）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ── session / URL key（§3.3 SSOT；值與修前各處字面值逐字相同）─────────────────────
#: ETF / legacy 通道（亦是 forward-test、`sync_silent_marker` 信任的那一格）。
PORTFOLIO_SHEET_SESSION_KEY: str = "portfolio_sheet_id"
#: 個股通道（session-only，無 secrets fallback）。
STOCK_PORTFOLIO_SHEET_SESSION_KEY: str = "stock_portfolio_sheet_id"
#: 綁定寫入契約一律同時寫的兩格（legacy compatibility adapter，DEC-083 B4）。
SHEET_BINDING_SESSION_KEYS: tuple[str, str] = (
    PORTFOLIO_SHEET_SESSION_KEY, STOCK_PORTFOLIO_SHEET_SESSION_KEY)
#: 網址上「上次用哪本」的參數名（非憑證）。
SHEET_QUERY_PARAM: str = "sheet"
#: 綁定「世代」:唯一寫入契約每寫一次 / 清一次就 +1。被動文字框(側欄貼 ID、就地貼網址框)據此在綁定
#: 變了之後丟掉自己的舊 widget 狀態,重新顯示現值(QA BLK-2:舊值不得在下一輪又被綁回去)。
SHEET_BINDING_VERSION_SESSION_KEY: str = "_sheet_binding_version"

# ── 字母集 / 長度 ──────────────────────────────────────────────────────────
#: Google Drive fileId 實測 44 字元；上限 120 留餘裕又擋濫用（防超長字串灌爆 URL / session）。
SHEET_ID_MAX_LEN: int = 120
SHEET_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,%d}" % SHEET_ID_MAX_LEN)
#: 修前發布連結 bug 的產物(`/spreadsheets/d/e/…` 被解析成 `e`)—— 不是任何人的 Sheet ID,一律拒絕。
LEGACY_PUBLISH_LINK_ARTEFACT: str = "e"

#: 發布連結（「檔案 → 共用 → 發布到網路」）：`/spreadsheets/d/e/<發布 token>/pubhtml`。
_PUBLISHED_LINK_RE = re.compile(r"/spreadsheets/(?:u/\d+/)?d/e(?=[/?#]|$)")
#: 一般編輯網址：`/spreadsheets/d/<ID>/edit…`（含多帳號 `/u/0/` 變體）。
_EDIT_LINK_RE = re.compile(r"/spreadsheets/(?:u/\d+/)?d/([^/?#]*)")

# ── 解析錯誤代碼 + 白話訊息（§3.3；⛔ 訊息不回顯使用者貼的內容）────────────────────
SHEET_INPUT_EMPTY: str = "empty"
SHEET_INPUT_PUBLISHED_LINK: str = "published_link"
SHEET_INPUT_INVALID: str = "invalid"

SHEET_INPUT_ERROR_MESSAGES: dict[str, str] = {
    SHEET_INPUT_EMPTY: "請貼上 Google Sheet 網址或 ID。",
    SHEET_INPUT_PUBLISHED_LINK: (
        "這是「發布到網路」的連結，不能用來讀取或寫入你的 Sheet。"
        "請改貼瀏覽器網址列上的編輯網址（…/spreadsheets/d/<ID>/edit），或直接貼 Sheet ID。"),
    SHEET_INPUT_INVALID: (
        "看不懂這個網址或 ID。請貼 Google Sheet 的編輯網址（…/spreadsheets/d/<ID>/edit），"
        "或只貼網址中間那段 ID（只含英文字母、數字、- 與 _）。"),
}


@dataclass(frozen=True)
class SheetIdParse:
    """`parse_sheet_input` 的結果。`error` 為空字串 ⇔ `sheet_id` 非空（可用）。"""

    sheet_id: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.sheet_id) and not self.error

    @property
    def message(self) -> str:
        """給使用者看的白話錯誤；成功 → 空字串。"""
        return SHEET_INPUT_ERROR_MESSAGES.get(self.error, "")


def sanitize_sheet_id(raw) -> str:
    """Sheet ID 消毒：只放行純 `[A-Za-z0-9_-]`（1..120 字）；其餘一律回空字串。純函式。

    不可信輸入（state 便車帶回的乘客、網址上的 `?sheet=`、使用者貼上的字）專用。
    """
    s = str(raw or "").strip()
    if s == LEGACY_PUBLISH_LINK_ARTEFACT:
        return ""
    return s if s and SHEET_ID_RE.fullmatch(s) else ""


def parse_sheet_input(raw) -> SheetIdParse:
    """使用者貼上的 Google Sheet 網址或 ID → `SheetIdParse`（規則見檔頭；⛔ 不猜）。純函式。"""
    s = str(raw or "").strip()
    if not s:
        return SheetIdParse(error=SHEET_INPUT_EMPTY)
    if _PUBLISHED_LINK_RE.search(s):
        return SheetIdParse(error=SHEET_INPUT_PUBLISHED_LINK)
    m = _EDIT_LINK_RE.search(s)
    sid = sanitize_sheet_id(m.group(1) if m else s)
    if not sid:
        return SheetIdParse(error=SHEET_INPUT_INVALID)
    return SheetIdParse(sheet_id=sid)


# ══ 👤 我的 P1（DEC-083 Q4／Q5／Q7）════════════════════════════════════════════
# 客戶原文 Q4：「一般 UI 顯示：『Sheet 名稱＋ID 末 6 碼』。」
#: 一般畫面上 Sheet ID 只露出末幾碼（Q4）。⛔ 新版畫面永不印完整 ID。
SHEET_ID_TAIL_LEN: int = 6
#: 末幾碼前面的省略記號（線框原文「…f3K9aQ」）。
SHEET_ID_TAIL_PREFIX: str = "…"


def sheet_id_tail(raw) -> str:
    """Sheet ID → 畫面用的「…末 6 碼」（消毒後）；空 / 不合格 → 空字串。純函式。

    ⚠️ 只截字串，⛔ 不猜也不補：ID 本身不足 6 碼（不是真的 Google ID）時照樣只回它的末段。
    """
    _sid = sanitize_sheet_id(raw)
    return f"{SHEET_ID_TAIL_PREFIX}{_sid[-SHEET_ID_TAIL_LEN:]}" if _sid else ""


# 客戶原文 Q7：「👤 我的提供新版全站共用：active portfolio／active watchlist。🛡️ 持股／🎯 標的／⚡ 行動等頁
# 只能讀這個共同選擇。不得再以『名稱排序第一本』作為不可見的業務決策。」
# 值的形狀：`{"sheet_id": <選的時候那本 Sheet>, "name": <組合／清單名>, "skip": <僅觀察清單：明確不使用>}`。
# ⚠️ **綁住 Sheet**：讀取端只在 `sheet_id` 與目前 active Sheet 相同時才認（換了 Sheet 不會把舊名字套到新那本）。
# ⚠️ **只活在 session**（AI 總管裁示：不持久化到 Sheet 或網址）；寫入一律經 L1 `oauth_state` 的
#    `set_active_selection` / `clear_active_selection`（守衛：`tests/test_me_p1_state.py`）。
SELECTION_KIND_PORTFOLIO: str = "portfolio"
SELECTION_KIND_WATCHLIST: str = "watchlist"
ACTIVE_PORTFOLIO_SESSION_KEY: str = "_me_active_portfolio"
ACTIVE_WATCHLIST_SESSION_KEY: str = "_me_active_watchlist"
#: kind → session key（讀寫一律查這張表，⛔ 不手抄 key）。
ACTIVE_SELECTION_SESSION_KEYS: dict[str, str] = {
    SELECTION_KIND_PORTFOLIO: ACTIVE_PORTFOLIO_SESSION_KEY,
    SELECTION_KIND_WATCHLIST: ACTIVE_WATCHLIST_SESSION_KEY,
}

# 客戶原文 Q5：「登出時同步清除：Google 登入 session、active Sheet binding、URL 上 "sheet" 參數、OAuth state／
# 登入流程攜帶的舊 Sheet ID、會造成登出後重新自動綁回舊 Sheet 的 silent marker。不得登出後自動恢復上一個 Sheet。」
#: 「👤 我的」頁存放 Drive 清單（資料夾 / Sheets）的 session key —— 帶著上一個帳號的雲端硬碟檔名，登出時一併清。
ME_DRIVE_FOLDERS_SESSION_KEY: str = "p07me_drive_folders"
ME_DRIVE_SHEETS_SESSION_KEY: str = "p07me_drive_sheets"
#: 「👤 我的」頁貼網址 / ID 的文字框 widget key（登出時一併拿掉舊值，理由同側欄貼 ID 框）。
ME_PASTE_INPUT_KEY: str = "p07me_paste_sheet"
#: 共用登出（L1 `oauth_state.logout_google_session`）在登入 / 綁定 / 選定之外**另外**清掉的 session key。
LOGOUT_EXTRA_SESSION_KEYS: tuple[str, ...] = (
    ME_DRIVE_FOLDERS_SESSION_KEY, ME_DRIVE_SHEETS_SESSION_KEY, ME_PASTE_INPUT_KEY)
