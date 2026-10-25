"""src/ui/views/page_me.py — IA v2「👤 我的」頁（L5 UI；👤 我的 P1，DEC-083）。

單一職責（核准草稿 `docs/vnext/ME_PAGE_DRAFT_2026-10-25.md` §3.1 原文）::

    我用哪個 Google 帳號、這個 App 現在讀哪一本 Sheet、它是不是最新的？

客戶裁示（DEC-083，原文摘錄）：
  · Q1=A：「側欄新增獨立『👤 我的』，作為 Google 帳號、Sheet 綁定與新版 Sheet SSOT 的唯一設定入口。」
  · Q2=A：P1 只做登入／登出／重新登入、Sheet URL／ID、Drive Sheet 清單、明確選擇／切換、重新讀取、
    active Sheet、active portfolio、active watchlist。⛔ 不搬建立／改名／刪 Sheet、組合／觀察清單／持股列 CRUD。
  · Q4=A：「一般 UI 顯示：『Sheet 名稱＋ID 末 6 碼』。」（⛔ 本頁永不印完整 ID）
  · Q5=A：登出清登入、綁定、`?sheet=`、state 夾帶的舊 Sheet ID、silent marker（L1 共用 `logout_google_session`）。
  · Q6=A：組合與觀察清單指向不同本時：白話警示、⛔ 不偷選、⛔ 不覆寫，讓使用者在本頁明確重選。
  · Q7=A：本頁提供全站共用的 active portfolio／active watchlist；⛔ 不以名稱排序第一本代替使用者決定。
  · C 段：「唯一本 Sheet 自動綁 取消。就算 Drive 只有一本：仍要使用者明確按『使用這本』。」
  · D 段：要改內容 → 「目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。」（L0 `ia_nav` 原封不動）

═══ 版面（首屏三張卡，同核准線框 §3.1）══════════════════════════════════
  ① Google 帳號 ／ ② 目前 Sheet（含「🔄 切換 Sheet」展開區）／ ③ 這本 Sheet 內容（組合／觀察清單選擇器
  ＋哪些頁正在用）；其下「▸ 詳細：切回舊版、已知限制」預設收合。
  每一態都有文字＋燈（⛔ 不只靠顏色）：⬜ 灰＝未載入／有效空狀態；🟢 綠＝正常；⚠️ 黃＝資料疑義／不一致；
  🔴 紅＝真的出錯（v3 §02）。

═══ 本頁**不做**的事 ══════════════════════════════════════════════════════
- ⛔ 不寫使用者 Sheet 的任何內容（沒有 CRUD、沒有建立／改名／刪除 Sheet）。
- ⛔ 不自動綁任何一本（Drive 清單只有一本也一樣；部署預設也要按「使用這本」）。
- ⛔ 不清全域快取：「🔄 重新讀取」只失效本人×這本 Sheet（L3 → L1 失效世代，⛔ 不 `.clear()`）。
- ⛔ 不把選定持久化到 Sheet 或網址（只活在 session；AI 總管裁示）。
- ⛔ 零 `src.data.*` import：所有動作經 L3 `me_account_service`（`tests/test_c3_layering_guard.py`）。

掛載：`app.py::_ia_view_me()` 於側欄「🆕 新版戰情室（試用中）」radio 選到本頁時 late import 並呼叫
`render_page_me()`；沒被選到時本檔連 import 都不發生。session / widget key 一律 `p07me_` 前綴。

分層：L5 —— 依賴 L0（`shared.ia_nav`／`shared.sheet_id`／`shared.secret_scrub`）與函式體內 lazy 的
L3（`services.me_account_service`／`services.portfolio_binding_service`／`services.holdings_service` 的常數）。
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import streamlit as st

from shared import ia_nav
from shared.secret_scrub import scrub_secrets
from shared.sheet_id import (
    ME_DRIVE_FOLDERS_SESSION_KEY,
    ME_DRIVE_SHEETS_SESSION_KEY,
    ME_PASTE_INPUT_KEY,
    sheet_id_tail,
)

# ══════════════════════════════════════════════════════════════════
# session / widget key（本頁自有前綴 `p07me_`）
# ══════════════════════════════════════════════════════════════════
#: 本頁上一個動作的結果訊息（`[(kind, text), …]`；畫完就清）。kind ∈ success / info / error。
SS_FLASH: str = "p07me_flash"
SS_FOLDER_PICK: str = "p07me_folder_pick"
SS_SHEET_PICK: str = "p07me_sheet_pick"
SS_PF_PICK: str = "p07me_portfolio_pick"
SS_WL_PICK: str = "p07me_watchlist_pick"
#: Drive 清單讀取失敗的說明（按了「列出」才會有；登出時由本頁 `_on_logout` 清）。
SS_DRIVE_ERROR: str = "p07me_drive_error"

# ══════════════════════════════════════════════════════════════════
# 首屏字樣（卡名 ＝ `ia_nav.SECTION_LABELS`，指路句與卡名同一個 SSOT）
# ══════════════════════════════════════════════════════════════════
PAGE_QUESTION: str = "我用哪個 Google 帳號、這個 App 現在讀哪一本 Sheet、這本 Sheet 裡分析的是哪一本？"
CARD_ACCOUNT_TITLE: str = "① " + ia_nav.SECTION_LABELS[ia_nav.SECTION_ME_ACCOUNT]
CARD_SHEET_TITLE: str = "② " + ia_nav.SECTION_LABELS[ia_nav.SECTION_ME_SHEET]
CARD_CONTENT_TITLE: str = "③ " + ia_nav.SECTION_LABELS[ia_nav.SECTION_ME_CONTENT]

USE_SHEET_LABEL: str = ia_nav.action_label(ia_nav.ACTION_ME_USE_SHEET)
RELOAD_LABEL: str = ia_nav.action_label(ia_nav.ACTION_ME_RELOAD)
LOGIN_LABEL: str = ia_nav.action_label(ia_nav.ACTION_GOOGLE_LOGIN)
RELOGIN_LABEL: str = "🔐 重新登入"
LOGOUT_LABEL: str = "🚪 登出"
SWITCH_SHEET_TITLE: str = "🔄 切換 Sheet"
LIST_FOLDERS_LABEL: str = "📁 列出資料夾（可選）"
LIST_SHEETS_LABEL: str = "📂 列出 Sheets"
CLEAR_PF_LABEL: str = "取消選定組合"
CLEAR_WL_LABEL: str = "取消選定觀察清單"
PICK_PLACEHOLDER: str = "— 尚未選定 —"
ALL_FOLDERS_LABEL: str = "整個帳號（不限資料夾）"
#: 觀察清單選擇器多一個選項：明確不使用。⚠️ 值不是任何清單名（選擇器的值是這個常數本身）。
WATCHLIST_SKIP_OPTION: str = "（不使用觀察清單）"

# ── 卡① Google 帳號 ──────────────────────────────────────────────────
ACC_NOT_CONFIGURED: str = "⬜ 本站尚未設定 Google 登入（部署設定，不是你的操作問題）"
ACC_NOT_CONFIGURED_WHY: str = "網頁讀取持股一律需要 Google 登入；部署端設定好之前，本頁沒有可以登入的按鈕。"
ACC_READ_FAILED: str = "🔴 登入狀態讀取失敗"
ACC_READ_FAILED_WHERE: str = "可重新整理頁面後再試；一直如此請把上面那行訊息回報給維護者。"
ACC_LOGGED_OUT: str = "⬜ 尚未登入 —— 登入後才能讀你的 Sheet"
ACC_EXPIRED: str = "⬜ 登入已逾時（自動恢復的登入約 1 小時後逾時，不是故障）"
ACC_LOGGED_IN: str = "🟢 已登入"
ACC_SCOPE_NOTE: str = ("權限：沿用既有的 Google 授權（可讀寫你帳號內的試算表、列出雲端硬碟的檔名）；"
                       "本頁只讀你選的那一本，⛔ 不改它的任何內容。")
#: 已知限制（據實）：Google 轉跳回來是新的一次使用 ⇒ 側欄導覽回到「不使用」。
ACC_AFTER_LOGIN_NOTE: str = "登入後會回到首頁：請在側欄再選一次「" + ia_nav.page_label(ia_nav.PAGE_ME) + "」。"

# ── 卡② 目前 Sheet ────────────────────────────────────────────────────
SHEET_NEED_LOGIN: str = "⬜ 登入後才能選 Sheet"
SHEET_NONE: str = "⬜ 尚未選 Sheet"
SHEET_NONE_WHERE: str = f"用下方「{SWITCH_SHEET_TITLE}」貼網址／ID，或從雲端硬碟選一本，再按「{USE_SHEET_LABEL}」。"
SHEET_DEFAULT_ONLY: str = "⬜ 尚未選 Sheet（本站有一本部署預設的 Sheet，但不會替你決定）"
SHEET_DEFAULT_WHERE: str = f"要用部署預設那一本（{{tail}}）請按下面的「{USE_SHEET_LABEL}」；也可以改選別本。"
SHEET_DIVERGED: str = "⚠️ 你的「組合」和「觀察清單」目前讀的是兩本不同的 Sheet（{a}／{b}）"
SHEET_DIVERGED_WHY: str = ("本來應該讀同一本；可能是舊版分別設定過。本頁不會替你選其中一本，"
                           "也不會自動覆寫 —— 請按下面其中一顆，或用「" + SWITCH_SHEET_TITLE + "」另選一本。")
SHEET_UNSET_TAIL: str = "（未設定）"
SHEET_USE_PF_SIDE: str = "✅ 使用「組合」那一本（{tail}）"
SHEET_USE_WL_SIDE: str = "✅ 使用「觀察清單」那一本（{tail}）"
SHEET_USE_DEFAULT: str = USE_SHEET_LABEL + "（部署預設 {tail}）"
SHEET_OK_TITLE: str = "📗「{title}」（{tail}）"
SHEET_OK_UNTITLED: str = "📗（這本 Sheet 沒有標題）（{tail}）"
SHEET_TITLE_NOT_READ: str = "📗 ID 末 6 碼 {tail} ｜ ⬜ 標題尚未讀取（登入後才讀得到）"
SHEET_NOT_FOUND: str = "🔴 這本 Sheet 打不開：找不到（可能已刪除，或網址打錯）—— 請重新選一本（{tail}）"
SHEET_FORBIDDEN: str = "🔴 這本 Sheet 打不開：你的 Google 帳號沒有權限 —— 請確認分享設定，或重新選一本（{tail}）"
SHEET_TITLE_QUOTA: str = "🔴 讀取 Sheet 失敗：Google 讀取額度暫時用完，可稍後按「" + RELOAD_LABEL + "」（{tail}）"
SHEET_TITLE_NETWORK: str = "🔴 讀取 Sheet 失敗：網路連線失敗，可稍後按「" + RELOAD_LABEL + "」（{tail}）"
SHEET_TITLE_FAILED: str = "🔴 讀取 Sheet 失敗：{err}，可稍後按「" + RELOAD_LABEL + "」（{tail}）"
SHEET_READ_FAILED: str = "🔴 綁定狀態讀取失敗：{err}"
SHEET_SOURCE_NOTE: str = "這本是你明確選定的（本頁、側欄、網址書籤或登入時帶回的同一本）。"
SHEET_SAFE_NOTE: str = "ⓘ 切換只改「這個 App 讀哪一本」，不會改你 Sheet 裡的任何內容。"
PASTE_LABEL: str = "方法一：貼 Google Sheet 網址或 ID（按 Enter 套用）"
PASTE_PLACEHOLDER: str = "https://docs.google.com/spreadsheets/d/…/edit"
DRIVE_HEADING: str = "方法二：從我的雲端硬碟選"
DRIVE_FOLDER_LABEL: str = "限定資料夾"
DRIVE_PICK_LABEL: str = "清單共 {n} 本 —— 選一本"
DRIVE_EMPTY: str = "⬜ 這個範圍找不到任何 Sheet（有效結果，不是故障）"
DRIVE_FAILED: str = "🔴 讀取雲端硬碟清單失敗：{err}，可稍後再按一次"
DRIVE_PICK_FIRST: str = "先在上面選一本，再按「" + USE_SHEET_LABEL + "」。"
#: 建立新 Sheet 不在 P1（Q2）：只放指路（D 段客戶原句原封不動）。
CREATE_SHEET_WHERE: str = "要建立新 Sheet：" + ia_nav.CONTENT_EDIT_OLD_UI_WHERE

BIND_CHANGED: str = "已改讀這一本 Sheet（{tail}）。組合／觀察清單請在下方重新選定。"
BIND_ALREADY: str = "已是目前使用的 Sheet（{tail}），不用再設定。"
RELOAD_DONE: str = "已重新讀取這本 Sheet（只更新你自己的讀取，不影響其他使用者）。"
RELOAD_NOTHING: str = "目前沒有可重新讀取的 Sheet。"

# ── 卡③ 這本 Sheet 內容 ────────────────────────────────────────────────
CONTENT_NOT_READ: str = "⬜ 尚未讀取（不是 0 本）"
CONTENT_NOT_READ_WHY_LOGIN: str = "登入並選定 Sheet 之後才會讀。"
CONTENT_NOT_READ_WHY_SHEET: str = "先在卡②選定一本 Sheet。"
PF_WORKSHEET_MISSING: str = "⬜ 這本 Sheet 沒有「{ws}」分頁（本頁不會替你建立）"
SCHEMA_MISMATCH: str = "⚠️ 資料疑義：「{ws}」分頁第一列應為 {headers}，本頁未讀取也未修改"
LIST_READ_FAILED: str = "🔴 {what}讀取失敗：{err}，可稍後按「" + RELOAD_LABEL + "」"
PF_EMPTY: str = "⬜ 還沒有任何組合（有效結果，不是故障）"
WL_EMPTY: str = "⬜ 還沒有任何觀察清單（有效結果，不是故障）"
PF_COUNT: str = "組合 {n} 本：{names}"
WL_COUNT: str = "觀察清單 {n} 份：{names}"
PF_NOT_SELECTED: str = "⬜ 還沒選定要分析哪一本組合（本站不替你挑，不以名稱排序第一本代替你決定）"
WL_NOT_SELECTED: str = "⬜ 還沒選定觀察清單（沒選也可以；持股分析照常）"
PF_SELECTED: str = "🟢 分析中的組合：「{name}」"
WL_SELECTED: str = "🟢 使用中的觀察清單：「{name}」"
WL_SKIPPED: str = "⬜ 已選「不使用觀察清單」"
SEL_MISSING: str = "⚠️ 你選定的{what}「{name}」在這本 Sheet 裡找不到（可能被改名或刪掉）—— 請重新選定"
PF_PICK_LABEL: str = "選定要分析的組合"
WL_PICK_LABEL: str = "選定要使用的觀察清單"
SELECT_FAILED_MISSING: str = "沒有選定：「{name}」不在這本 Sheet 的清單裡（可能剛被改名），請重新選。"
SELECT_FAILED_LIST: str = "沒有選定：這本 Sheet 的清單現在讀不到，請稍後按「" + RELOAD_LABEL + "」再選。"
SELECT_FAILED_SHEET: str = "沒有選定：還沒有選定 Sheet。"
EDIT_CONTENT_WHERE: str = "要新增／修改組合、觀察清單或持股列：" + ia_nav.CONTENT_EDIT_OLD_UI_WHERE
USED_BY_HEADING: str = "用到這本 Sheet 的頁"
#: 「哪些頁正在用」—— 頁名一律 `ia_nav.page_label`（⛔ 不手抄）。⚡ 行動頁尚未上線（不在 PAGE_LABELS）。
USED_BY_LINES: tuple[str, ...] = (
    f"{ia_nav.page_label(ia_nav.PAGE_HOLD)}：分析你選定的組合＋觀察清單",
    f"{ia_nav.page_label(ia_nav.PAGE_FIND)}：板塊資金潮汐的持股標示（你選定的組合＋觀察清單）",
    f"{ia_nav.page_label(ia_nav.PAGE_TODAY)}：只看有沒有綁 Sheet，不讀組合內容",
    "⚡ 行動：尚未上線",
)

# ── 詳細（第三層，預設收合）────────────────────────────────────────────
DETAIL_TITLE: str = "▸ 詳細：切回舊版、已知限制"
#: 切回舊版的方法。側欄字面（radio 標題、「不使用」選項、舊頁籤名）逐字取自 `app.py`（測試對帳）。
OLD_UI_NAV_LABEL: str = "🆕 新版戰情室（試用中）"
OLD_UI_NAV_OFF: str = "不使用（用下方原功能）"
OLD_UI_TAB: str = "📁 組合管理"
SWITCH_BACK_TEXT: str = (f"切回舊版：側欄「{OLD_UI_NAV_LABEL}」選「{OLD_UI_NAV_OFF}」→ 主畫面回到原本的頁籤 → "
                         f"「{OLD_UI_TAB}」。舊版的頁籤照舊讀它自己的設定，不受本頁的組合／觀察清單選定影響。")
KNOWN_LIMITS: tuple[str, ...] = (
    "組合／觀察清單的選定只記在這一次使用中：重新整理頁面、或重新登入之後要重選（不會寫進你的 Sheet 或網址）。",
    "Google 登入轉跳回來是新的一次使用：側欄導覽會回到「" + OLD_UI_NAV_OFF + "」，登入後請在側欄再選一次「"
    + ia_nav.page_label(ia_nav.PAGE_ME) + "」。",
    "同時開多個瀏覽器分頁時，每個分頁依自己的網址還原 Sheet；在這裡登出只管得到目前這個分頁。",
    "排程推播讀的是部署環境的設定，與本頁選哪一本無關。",
)


# ══════════════════════════════════════════════════════════════════
# 卡片 view-model（純資料；`build_*` 純函式，易測）
# ══════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class CardView:
    """一張卡要畫的東西。`lines` 依序畫成 markdown；`captions` 畫成灰字；按鈕另由 render 依態決定。"""

    title: str
    status: str
    lines: tuple[str, ...] = ()
    captions: tuple[str, ...] = ()


def _md(text: object) -> str:
    """使用者的資料（Sheet 標題、組合名）放進 markdown 前跳脫，免得名稱裡的符號被當成格式。"""
    _s = str(text)
    for _c in ("\\", "*", "_", "`", "[", "]", "<", ">", "#", "|", "~"):
        _s = _s.replace(_c, "\\" + _c)
    return _s


def _err(text: object) -> str:
    """上游例外 → 可以上畫面的一句（先洗金鑰／Sheet ID／路徑，再跳脫）。"""
    return _md(scrub_secrets(str(text or "（上游沒有給訊息）")))


def build_account_card(acct) -> CardView:
    """卡①。`acct` ＝ L3 `me_account_service.AccountView`。"""
    from src.services import me_account_service as ME

    _st = getattr(acct, "state", "")
    if _st == ME.ACCOUNT_NOT_CONFIGURED:
        return CardView(CARD_ACCOUNT_TITLE, ACC_NOT_CONFIGURED, captions=(ACC_NOT_CONFIGURED_WHY,))
    if _st == ME.ACCOUNT_READ_FAILED:
        return CardView(CARD_ACCOUNT_TITLE, ACC_READ_FAILED,
                        lines=(_err(getattr(acct, "error", "")),), captions=(ACC_READ_FAILED_WHERE,))
    if _st == ME.ACCOUNT_LOGGED_IN:
        _email = getattr(acct, "email_masked", "")
        return CardView(CARD_ACCOUNT_TITLE, ACC_LOGGED_IN + (f" {_md(_email)}" if _email else ""),
                        captions=(ACC_SCOPE_NOTE,))
    _status = ACC_EXPIRED if _st == ME.ACCOUNT_EXPIRED else ACC_LOGGED_OUT
    return CardView(CARD_ACCOUNT_TITLE, _status, captions=(ACC_AFTER_LOGIN_NOTE, ACC_SCOPE_NOTE))


def _tail_or_unset(sid: str) -> str:
    return sheet_id_tail(sid) or SHEET_UNSET_TAIL


def build_sheet_card(view, *, logged_in: bool) -> CardView:
    """卡②。`view` ＝ L3 `me_account_service.SheetView`（`active` ＝ `portfolio_binding_service.ActiveSheet`）。

    ⚠️ 只顯示 ID 末 6 碼（Q4）；⛔ 部署預設 / 兩本不同時不讀標題（那不是你選定的那一本）。
    """
    from src.services import me_account_service as ME
    from src.services import portfolio_binding_service as PB

    _a = getattr(view, "active", None)
    _state = getattr(_a, "state", "")
    _read_err = str(getattr(_a, "read_error", "") or "")
    if _read_err:
        return CardView(CARD_SHEET_TITLE, SHEET_READ_FAILED.format(err=_err(_read_err)),
                        captions=(ACC_READ_FAILED_WHERE,))
    if not logged_in:
        return CardView(CARD_SHEET_TITLE, SHEET_NEED_LOGIN)
    if _state == PB.ACTIVE_DIVERGED:
        return CardView(CARD_SHEET_TITLE,
                        SHEET_DIVERGED.format(a=_tail_or_unset(_a.portfolio_channel),
                                              b=_tail_or_unset(_a.stock_channel)),
                        captions=(SHEET_DIVERGED_WHY,))
    if _state == PB.ACTIVE_DEPLOY_DEFAULT_ONLY:
        return CardView(CARD_SHEET_TITLE, SHEET_DEFAULT_ONLY,
                        captions=(SHEET_DEFAULT_WHERE.format(tail=sheet_id_tail(_a.deploy_default)),))
    if _state != PB.ACTIVE_OK:
        return CardView(CARD_SHEET_TITLE, SHEET_NONE, captions=(SHEET_NONE_WHERE,))
    _tail = sheet_id_tail(_a.sheet_id)
    _ts = getattr(view, "title_status", "")
    _gsp_ok, _nf, _pd, _quota, _net = _read_codes()
    if _ts == _gsp_ok:
        _title = str(getattr(view, "title", "") or "")
        _status = (SHEET_OK_TITLE.format(title=_md(_title), tail=_tail) if _title
                   else SHEET_OK_UNTITLED.format(tail=_tail))
        return CardView(CARD_SHEET_TITLE, _status, captions=(SHEET_SOURCE_NOTE,))
    if _ts in ("", ME.TITLE_LOGIN_REQUIRED):
        return CardView(CARD_SHEET_TITLE, SHEET_TITLE_NOT_READ.format(tail=_tail))
    if _ts == _nf:
        return CardView(CARD_SHEET_TITLE, SHEET_NOT_FOUND.format(tail=_tail))
    if _ts == _pd:
        return CardView(CARD_SHEET_TITLE, SHEET_FORBIDDEN.format(tail=_tail))
    if _ts == _quota:
        return CardView(CARD_SHEET_TITLE, SHEET_TITLE_QUOTA.format(tail=_tail))
    if _ts == _net:
        return CardView(CARD_SHEET_TITLE, SHEET_TITLE_NETWORK.format(tail=_tail))
    return CardView(CARD_SHEET_TITLE, SHEET_TITLE_FAILED.format(
        err=_err(getattr(view, "title_error", "") or _ts), tail=_tail))


def _read_codes() -> tuple[str, str, str, str, str]:
    """讀取狀態代碼（SSOT 在 L1；經 L3 取，L5 不 import L1）。"""
    from src.services import me_account_service as ME
    return ME.read_status_codes()


def _list_status(names, issue: str, err: str, *, what: str, ws: str, headers: Sequence[str],
                 empty_text: str, count_text: str) -> str:
    """一份清單（組合名 / 觀察清單名）的狀態句。**`None` ＝ 沒讀到（⛔ 不寫 0）；`()` ＝ 真的空。**"""
    _ok, _nf, _pd, _quota, _net = _read_codes()
    if names is not None:
        if not names:
            return empty_text
        return count_text.format(n=len(names), names="、".join(f"「{_md(_n)}」" for _n in names))
    from src.services import me_account_service as ME
    if issue == ME.ISSUE_WORKSHEET_MISSING:
        return PF_WORKSHEET_MISSING.format(ws=ws)
    if issue == ME.ISSUE_SCHEMA_MISMATCH:
        return SCHEMA_MISMATCH.format(ws=ws, headers="、".join(headers))
    if issue == ME.TITLE_LOGIN_REQUIRED:
        return CONTENT_NOT_READ + " —— " + CONTENT_NOT_READ_WHY_LOGIN
    _why = {_quota: "Google 讀取額度暫時用完", _net: "網路連線失敗", _pd: "沒有這本 Sheet 的權限",
            _nf: "找不到這本 Sheet"}.get(issue, _err(err or issue))
    return LIST_READ_FAILED.format(what=what, err=_why)


def build_content_card(contents, *, logged_in: bool, active_ok: bool) -> CardView:
    """卡③。`contents` ＝ L3 `me_account_service.SheetContents`（沒登入 / 沒 active Sheet → None）。"""
    if contents is None or not logged_in or not active_ok:
        _why = CONTENT_NOT_READ_WHY_LOGIN if not logged_in else CONTENT_NOT_READ_WHY_SHEET
        return CardView(CARD_CONTENT_TITLE, CONTENT_NOT_READ, captions=(_why,))
    from src.services import me_account_service as ME

    _hdr = ME.worksheet_headers()
    _pf_ws, _wl_ws = ME.PORTFOLIO_WORKSHEET, ME.WATCHLIST_WORKSHEET
    _lines = [
        _list_status(contents.portfolios, contents.portfolio_issue, contents.portfolio_error,
                     what="組合清單", ws=_pf_ws, headers=_hdr[_pf_ws],
                     empty_text=PF_EMPTY, count_text=PF_COUNT),
        _list_status(contents.watchlists, contents.watchlist_issue, contents.watchlist_error,
                     what="觀察清單", ws=_wl_ws, headers=_hdr[_wl_ws],
                     empty_text=WL_EMPTY, count_text=WL_COUNT),
    ]
    _sel = contents.selection
    _pf_sel = str(getattr(_sel, "portfolio", "") or "")
    if contents.portfolios:
        if not _pf_sel:
            _lines.append(PF_NOT_SELECTED)
        elif _pf_sel not in contents.portfolios:
            _lines.append(SEL_MISSING.format(what="組合", name=_md(_pf_sel)))
        else:
            _lines.append(PF_SELECTED.format(name=_md(_pf_sel)))
    _wl_sel = str(getattr(_sel, "watchlist", "") or "")
    if getattr(_sel, "watchlist_skip", False):
        _lines.append(WL_SKIPPED)
    elif contents.watchlists:
        if not _wl_sel:
            _lines.append(WL_NOT_SELECTED)
        elif _wl_sel not in contents.watchlists:
            _lines.append(SEL_MISSING.format(what="觀察清單", name=_md(_wl_sel)))
        else:
            _lines.append(WL_SELECTED.format(name=_md(_wl_sel)))
    return CardView(CARD_CONTENT_TITLE, _lines[0], lines=tuple(_lines[1:]), captions=(EDIT_CONTENT_WHERE,))


# ══════════════════════════════════════════════════════════════════
# 動作（一律 on_click / on_change callback —— 按下那一刻才呼叫 L3，畫面這一輪就看到結果）
# ══════════════════════════════════════════════════════════════════
def _flash(kind: str, text: str) -> None:
    st.session_state.setdefault(SS_FLASH, []).append((kind, text))


def _on_logout() -> None:
    from src.services import me_account_service as ME
    ME.logout()
    for _k in (SS_FOLDER_PICK, SS_SHEET_PICK, SS_PF_PICK, SS_WL_PICK, SS_DRIVE_ERROR):
        st.session_state.pop(_k, None)


def _report_bind(result) -> None:
    """契約 `SheetBindResult` → 一句結果。成功只在**真的寫了**時說（QA B-1 同一原則）。"""
    if result is None:
        return
    _tail = sheet_id_tail(getattr(result, "sheet_id", ""))
    if getattr(result, "error", ""):
        from shared.sheet_id import SHEET_INPUT_EMPTY
        if result.error != SHEET_INPUT_EMPTY:
            _flash("error", result.message)
    elif getattr(result, "changed", False):
        _flash("success", BIND_CHANGED.format(tail=_tail))
    elif getattr(result, "already_current", False):
        _flash("info", BIND_ALREADY.format(tail=_tail))


def _on_use_sheet(sheet_id: str) -> None:
    """「✅ 使用這本」（Drive 清單 / 部署預設 / 不一致時兩側之一）—— 使用者按了才呼叫唯一寫入契約。"""
    from src.services import me_account_service as ME
    _report_bind(ME.bind_sheet(sheet_id))


def _on_use_drive_pick() -> None:
    _sid = str(st.session_state.get(SS_SHEET_PICK) or "")
    if not _sid:
        _flash("info", DRIVE_PICK_FIRST)
        return
    _on_use_sheet(_sid)


def _on_paste() -> None:
    from src.services import me_account_service as ME
    ME.on_paste_change(ME_PASTE_INPUT_KEY)


def _on_reload() -> None:
    """「🔄 重新讀取」—— 只失效本人×這本 Sheet 的讀取快取（L3 → L1 失效世代；⛔ 不 `.clear()`）。"""
    from src.services import me_account_service as ME
    if ME.reload_reads():
        _flash("success", RELOAD_DONE)
    else:
        _flash("info", RELOAD_NOTHING)


def _load_drive(kind: str) -> None:
    from src.services import me_account_service as ME
    st.session_state.pop(SS_DRIVE_ERROR, None)
    try:
        if kind == "folders":
            st.session_state[ME_DRIVE_FOLDERS_SESSION_KEY] = ME.list_drive_folders()
        else:
            _folder = str(st.session_state.get(SS_FOLDER_PICK) or "")
            st.session_state[ME_DRIVE_SHEETS_SESSION_KEY] = ME.list_drive_sheets(_folder)
            st.session_state.pop(SS_SHEET_PICK, None)
    except Exception as _e:  # noqa: BLE001 — 列檔失敗誠實報（⛔ 不捏造清單）
        print(f"[views/page_me] Drive 清單讀取失敗：{scrub_secrets(repr(_e))}")
        st.session_state[SS_DRIVE_ERROR] = ME.drive_issue(_e) + "｜" + repr(_e)
        if kind != "folders":
            st.session_state.pop(ME_DRIVE_SHEETS_SESSION_KEY, None)


def _report_select(code: str, name: str) -> None:
    from src.services import me_account_service as ME
    if code == ME.SELECT_NAME_MISSING:
        _flash("error", SELECT_FAILED_MISSING.format(name=_md(name)))
    elif code == ME.SELECT_LIST_UNAVAILABLE:
        _flash("error", SELECT_FAILED_LIST)
    elif code == ME.SELECT_NO_ACTIVE_SHEET:
        _flash("error", SELECT_FAILED_SHEET)


def _on_pick_portfolio() -> None:
    from src.services import me_account_service as ME
    _name = st.session_state.get(SS_PF_PICK)
    if _name is None:
        ME.clear_portfolio_selection()
        return
    _report_select(ME.select_portfolio(str(_name)), str(_name))


def _on_pick_watchlist() -> None:
    from src.services import me_account_service as ME
    _name = st.session_state.get(SS_WL_PICK)
    if _name is None:
        ME.clear_watchlist_selection()
    elif _name == WATCHLIST_SKIP_OPTION:
        _report_select(ME.select_watchlist(skip=True), "")
    else:
        _report_select(ME.select_watchlist(str(_name)), str(_name))


def _on_clear_portfolio() -> None:
    from src.services import me_account_service as ME
    ME.clear_portfolio_selection()
    st.session_state.pop(SS_PF_PICK, None)


def _on_clear_watchlist() -> None:
    from src.services import me_account_service as ME
    ME.clear_watchlist_selection()
    st.session_state.pop(SS_WL_PICK, None)


def _sync_pick(widget_key: str, value) -> None:
    """選擇器的 widget 值與目前選定不同（例：換了 Sheet、選定被清掉）→ 丟掉舊 widget 值，改顯示目前選定。"""
    if widget_key in st.session_state and st.session_state.get(widget_key) != value:
        st.session_state.pop(widget_key, None)


# ══════════════════════════════════════════════════════════════════
# 渲染
# ══════════════════════════════════════════════════════════════════
def _render_card(card: CardView) -> None:
    st.markdown(f"**{card.title}**")
    st.markdown(card.status)
    for _ln in card.lines:
        st.markdown(_ln)
    for _c in card.captions:
        st.caption(_c)


def _render_flash() -> None:
    for _kind, _text in st.session_state.pop(SS_FLASH, None) or ():
        {"success": st.success, "error": st.error}.get(_kind, st.info)(_text)


def _render_account(acct) -> None:
    from src.services import me_account_service as ME
    _render_card(build_account_card(acct))
    if acct.state == ME.ACCOUNT_LOGGED_IN:
        st.button(LOGOUT_LABEL, key="p07me_logout", on_click=_on_logout, width="stretch")
    elif acct.state in (ME.ACCOUNT_LOGGED_OUT, ME.ACCOUNT_EXPIRED) and acct.login_url:
        st.link_button(RELOGIN_LABEL if acct.state == ME.ACCOUNT_EXPIRED else LOGIN_LABEL,
                       acct.login_url, width="stretch")


def _render_sheet(view, *, logged_in: bool) -> None:
    from src.services import portfolio_binding_service as PB
    _render_card(build_sheet_card(view, logged_in=logged_in))
    if not logged_in:
        return
    _a = view.active
    if _a.state == PB.ACTIVE_DIVERGED:
        # Q6：兩顆明確的按鈕（⛔ 不偷選、⛔ 不自動覆寫）；空的那一側沒有可用的那一本 ⇒ 不畫按鈕。
        for _sid, _label, _key in ((_a.portfolio_channel, SHEET_USE_PF_SIDE, "p07me_use_pf_side"),
                                   (_a.stock_channel, SHEET_USE_WL_SIDE, "p07me_use_wl_side")):
            if _sid:
                st.button(_label.format(tail=sheet_id_tail(_sid)), key=_key,
                          on_click=_on_use_sheet, args=(_sid,), width="stretch")
    elif _a.state == PB.ACTIVE_DEPLOY_DEFAULT_ONLY:
        st.button(SHEET_USE_DEFAULT.format(tail=sheet_id_tail(_a.deploy_default)), key="p07me_use_default",
                  on_click=_on_use_sheet, args=(_a.deploy_default,), width="stretch")
    elif _a.state == PB.ACTIVE_OK:
        st.button(RELOAD_LABEL, key="p07me_reload", on_click=_on_reload, width="stretch")
    _render_switch_sheet()


def _render_switch_sheet() -> None:
    """「🔄 切換 Sheet」展開區：貼網址／ID、Drive 清單 —— 兩種方法都要使用者明確動作才綁（⛔ 一本也不自動綁）。"""
    from src.services import me_account_service as ME
    with st.expander(SWITCH_SHEET_TITLE, expanded=False):
        st.caption(SHEET_SAFE_NOTE)
        # 方法一：被動文字框三步（L1 QA BLK-2 接法）。⚠️ `value=""`：⛔ 不把目前的完整 ID 放回框裡（Q4）。
        ME.prepare_paste_input(ME_PASTE_INPUT_KEY)
        st.text_input(PASTE_LABEL, value="", key=ME_PASTE_INPUT_KEY, on_change=_on_paste,
                      placeholder=PASTE_PLACEHOLDER)
        _report_bind(ME.pop_paste_result(ME_PASTE_INPUT_KEY))
        st.markdown(f"**{DRIVE_HEADING}**")
        st.button(LIST_FOLDERS_LABEL, key="p07me_list_folders", on_click=_load_drive, args=("folders",))
        _folders = st.session_state.get(ME_DRIVE_FOLDERS_SESSION_KEY)
        if _folders:
            _fmap = {"": ALL_FOLDERS_LABEL, **{str(_f.get("id")): str(_f.get("name")) for _f in _folders}}
            st.selectbox(DRIVE_FOLDER_LABEL, list(_fmap), format_func=lambda _k: _fmap.get(_k, ""),
                         key=SS_FOLDER_PICK)
        st.button(LIST_SHEETS_LABEL, key="p07me_list_sheets", on_click=_load_drive, args=("sheets",))
        _derr = str(st.session_state.get(SS_DRIVE_ERROR) or "")
        if _derr:
            st.markdown(DRIVE_FAILED.format(err=_err(_derr.split("｜", 1)[-1])))
        _sheets = st.session_state.get(ME_DRIVE_SHEETS_SESSION_KEY)
        if _sheets is not None and not _sheets:
            st.markdown(DRIVE_EMPTY)
        elif _sheets:
            _smap = {str(_s.get("id")): f"{_s.get('name')}（{sheet_id_tail(_s.get('id'))}）" for _s in _sheets}
            # ⚠️ index=None：清單只有一本也**不預選**（DEC-083 C）；值是 ID，畫面只出 format_func 的「名稱（…末 6 碼）」。
            st.selectbox(DRIVE_PICK_LABEL.format(n=len(_smap)), list(_smap),
                         format_func=lambda _k: _smap.get(_k, ""), index=None,
                         placeholder=PICK_PLACEHOLDER, key=SS_SHEET_PICK)
            st.button(USE_SHEET_LABEL, key="p07me_use_drive", on_click=_on_use_drive_pick,
                      type="primary", width="stretch")
        st.caption(CREATE_SHEET_WHERE)


def _render_contents(contents, *, logged_in: bool, active_ok: bool) -> None:
    _render_card(build_content_card(contents, logged_in=logged_in, active_ok=active_ok))
    if contents is None or not logged_in or not active_ok:
        return
    _sel = contents.selection
    if contents.portfolios:
        _cur = str(getattr(_sel, "portfolio", "") or "")
        _cur = _cur if _cur in contents.portfolios else None
        _sync_pick(SS_PF_PICK, _cur)
        _opts = list(contents.portfolios)
        st.selectbox(PF_PICK_LABEL, _opts, index=(_opts.index(_cur) if _cur else None),
                     placeholder=PICK_PLACEHOLDER, key=SS_PF_PICK, on_change=_on_pick_portfolio)
        if _cur:
            st.button(CLEAR_PF_LABEL, key="p07me_clear_pf", on_click=_on_clear_portfolio)
    if contents.watchlists:
        _wcur = (WATCHLIST_SKIP_OPTION if getattr(_sel, "watchlist_skip", False)
                 else str(getattr(_sel, "watchlist", "") or ""))
        _wopts = [WATCHLIST_SKIP_OPTION, *contents.watchlists]
        _wcur = _wcur if _wcur in _wopts else None
        _sync_pick(SS_WL_PICK, _wcur)
        st.selectbox(WL_PICK_LABEL, _wopts, index=(_wopts.index(_wcur) if _wcur else None),
                     placeholder=PICK_PLACEHOLDER, key=SS_WL_PICK, on_change=_on_pick_watchlist)
        if _wcur:
            st.button(CLEAR_WL_LABEL, key="p07me_clear_wl", on_click=_on_clear_watchlist)
    st.markdown(f"**{USED_BY_HEADING}**")
    st.markdown("\n".join(f"- {_ln}" for _ln in USED_BY_LINES))


def render_page_me() -> None:
    """「👤 我的」頁。三張卡；所有讀取都經 L3（Sheet 讀取在 L1 有本人×本 Sheet 的 15 分鐘快取）。"""
    from src.services import me_account_service as ME
    from src.services import portfolio_binding_service as PB

    st.markdown(f"### {ia_nav.page_label(ia_nav.PAGE_ME)}")
    st.caption(PAGE_QUESTION)
    _render_flash()
    _acct = ME.get_account()
    _logged = _acct.state == ME.ACCOUNT_LOGGED_IN
    _view = ME.get_sheet_view()
    _active_ok = getattr(_view.active, "state", "") == PB.ACTIVE_OK
    _contents = ME.get_sheet_contents(_view.active.sheet_id) if (_logged and _active_ok) else None
    _c1, _c2, _c3 = st.columns(3)
    with _c1, st.container(border=True):
        _render_account(_acct)
    with _c2, st.container(border=True):
        _render_sheet(_view, logged_in=_logged)
    with _c3, st.container(border=True):
        _render_contents(_contents, logged_in=_logged, active_ok=_active_ok)
    with st.expander(DETAIL_TITLE, expanded=False):
        st.markdown(SWITCH_BACK_TEXT)
        st.markdown("**已知限制**\n" + "\n".join(f"- {_ln}" for _ln in KNOWN_LIMITS))
