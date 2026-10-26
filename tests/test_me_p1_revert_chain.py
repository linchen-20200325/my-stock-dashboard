"""👤 我的 P1（DEC-083，2026-10-25）—— 舊批次「還原鏈」的最新一節。

本 repo 慣例（見 `tests/test_dec074_revert_chain.py` 檔頭）：每個批次登記自己的 `(新寫法, 舊寫法)` 還原組，
舊批次的回歸測試先把「更新的批次」換回去、再換回自己那一批，最後逐位比對各自的基底 sha256。
本批（👤 我的 P1 第 8 個 commit：新版頁面 dead-end 指路＋Q7 選定落點）改了下列 view 檔 —— 它們被
sheet_safety／c2a／c1／c21／z66b／uia／vn1b2／dec074…等舊鏈管 ⇒ 在鏈頭往前接一節：`me_p1_revert_for` 把本批改動
換回基底（`55601f42`，main，👤 我的 P1 開工前），由 `tests/test_sheet_safety_revert_chain.py::sheet_safety_revert_for`
（原鏈頭）在最前面呼叫（比照 `tests/test_c2a_risk_cap_shadow.py::c2a_revert_for` 接 sheet_safety 的作法）。

還原組由 difflib 對 `git show 55601f42:<檔>` 與工作樹逐 hunk 產生（最小唯一上下文），
`test_me_p1_revert_is_exact_base_source` 守：還原後逐位等於基底 sha256（寫死，測試不依賴 git）。
⚠️ 只套一次（idempotent，判定同 dec074／c1／c2a／sheet_safety）：各組 `新寫法` 全 1 次 ⇒ 換回；全 0 次 ⇒ 已換回、
原樣返回；其餘 ⇒ AssertionError（錨點漂移，必須重產還原組）。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: 基底 `55601f42`（main，👤 我的 P1 開工前）原始檔 sha256（`git show 55601f42:<檔> | sha256sum` 實算；寫死以免依賴 git）。
ME_P1_BASE_SHA = {'src/ui/views/page_find.py': 'd1c37726161b53026b5805455e2cd25f09733020e743bc553b7f7dcdb4b0016f',
 'src/ui/views/page_hold.py': '1853a43f6a72a41f8abedcbebb8e89127e740129b2d70e0e98ad94b5218a54cd',
 'src/ui/views/page_today.py': '1576f5cd672615fcfb21228f7bd1377fa9cf0c2913437e106461bdd380dd7a0a'}

# >>> ME_P1_REVERT_PAIRS（difflib 對基底逐 hunk、最小唯一上下文產生；改下列檔後須整組重產）
ME_P1_REVERT_PAIRS = {'src/ui/views/page_find.py': (('import re\n'
                                'from dataclasses import dataclass, field\n'
                                'from typing import Any, Iterable, Mapping, Sequence\n',
                                'import re\n'
                                'from dataclasses import dataclass\n'
                                'from typing import Any, Iterable, Mapping, Sequence\n'),
                               ('# ── 上游（既有分頁）寫進 session 的 UI 狀態 key ─────────────────────\n'
                                '# 📌 👤 我的 P1（DEC-083 Q7，有意識的移除，⛔ 不是漏刪）：~~`SS_ETF_PORTFOLIO_ROWS = '
                                '"etf_portfolio_rows"`／\n'
                                '#   `SS_STOCK_SHEET_ID = "stock_portfolio_sheet_id"` ＋ '
                                '`_etf_tickers(session)`~~ —— 持股標示改讀 L3\n'
                                '#   '
                                '`sector_flow_service.get_sector_flow_view(use_active_selection=True)`（「👤 '
                                '我的」選定的組合＋觀察清單），\n'
                                '#   本檔因此不再讀這兩個上游 key；三者因本次改動變成 0 production caller ⇒ 本次清掉（v3 §01-2 收尾義務）。\n'
                                '#   舊分頁 `src/ui/tabs/tab_sector_flow.py` 照舊讀它們（未動）。\n'
                                '\n',
                                '# ── 上游（既有分頁）寫進 session 的 UI 狀態 key ─────────────────────\n'
                                '#: ETF 組合按「計算組合」後寫入的持股列。\n'
                                '#: L3 `sector_flow_service` 的 docstring 明文：「**L5 只負責從 session_state 取\n'
                                '#: ETF 組合的 ticker + 個股 sheet_id 傳入**（session_state 是 UI 專屬，\n'
                                '#: 只能在 L5 讀）」—— 也就是讀這兩個 key 是 L3 契約**指派給 L5** 的工作，\n'
                                '#: 不是本檔自己多開的取數路徑。字面與 `src/ui/tabs/tab_sector_flow.py` 一致。\n'
                                'SS_ETF_PORTFOLIO_ROWS: str = "etf_portfolio_rows"\n'
                                '#: 個股組合 Google Sheet 的 sheet_id（同上）。\n'
                                'SS_STOCK_SHEET_ID: str = "stock_portfolio_sheet_id"\n'
                                '\n'),
                               ('    tpex_complete: bool | None = None\n'
                                '    #: 👤 我的 P1（DEC-083 Q7，只加不改）：持股標示的來源（L3 `holding_source`：選定的組合／觀察清單名、\n'
                                '    #: 選定狀態、讀取錯誤）。空 ⇒ L3 沒給（舊路徑）。\n'
                                '    holding_source: Mapping[str, Any] = field(default_factory=dict)\n'
                                '\n',
                                '    tpex_complete: bool | None = None\n\n'),
                               ('        """可畫板塊數 ＝ 全部 − 未取得（批 Z39：卡面板塊數 / has_value 以此計，\n'
                                '        避免全部未取得時仍寫「43 個板塊」）。"""\n'
                                '        return max(len(self.sectors) - len(self.unavailable), 0)\n'
                                '\n'
                                '\n'
                                'def _quadrant_counts(sectors: Iterable[Mapping[str, Any]]\n',
                                '        """可畫板塊數 ＝ 全部 − 未取得（批 Z39：卡面板塊數 / has_value 以此計，\n'
                                '        避免全部未取得時仍寫「43 個板塊」）。"""\n'
                                '        return max(len(self.sectors) - len(self.unavailable), 0)\n'
                                '\n'
                                '\n'
                                'def _etf_tickers(session: Mapping[str, Any]) -> list[str]:\n'
                                '    """ETF 組合持股的 ticker（讀 **UI 狀態**，不是抓資料）。\n'
                                '\n'
                                '    L3 `sector_flow_service` 的 docstring 指派給 L5 的工作就是這一件；\n'
                                '    ticker 常帶 `.TW` / `.TWO` 後綴，正規化由 L3 負責（本檔不去尾碼，\n'
                                '    那會變成第二處正規化規則）。\n'
                                '    """\n'
                                '    _rows = session.get(SS_ETF_PORTFOLIO_ROWS) or []\n'
                                '    if not isinstance(_rows, list):\n'
                                '        return []\n'
                                '    return [str(_r.get("ticker")).strip() for _r in _rows\n'
                                '            if isinstance(_r, Mapping) and _r.get("ticker")]\n'
                                '\n'
                                '\n'
                                'def _quadrant_counts(sectors: Iterable[Mapping[str, Any]]\n'),
                               ('        from src.services.sector_flow_service import get_sector_flow_view\n'
                                '        # 👤 我的 P1（DEC-083 Q7，有意識的修改，⛔ 不是漏刪）：~~持股標示讀本 session 的 ETF 組合列\n'
                                '        #   '
                                '（`_etf_tickers(session)`）＋個股通道整本**全部**觀察清單（`stock_sheet_id=session[SS_STOCK_SHEET_ID]`）~~\n'
                                '        #   → 改讀「👤 我的」選定的組合＋觀察清單（與 💼 我的持股 同一份選定；客戶：「只能讀這個共同選擇」）。\n'
                                '        _view = get_sector_flow_view(strict=True, '
                                'use_active_selection=True)\n'
                                '    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞\n',
                                '        from src.services.sector_flow_service import get_sector_flow_view\n'
                                '        _view = get_sector_flow_view(\n'
                                '            etf_tickers=_etf_tickers(session),\n'
                                '            stock_sheet_id=(str(session.get(SS_STOCK_SHEET_ID) or '
                                '"").strip()\n'
                                '                            or None),\n'
                                '            strict=True,\n'
                                '        )\n'
                                '    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞\n'),
                               ('        tpex_complete=_tpc if isinstance(_tpc, bool) else None,\n'
                                '        holding_source=dict(_view.get("holding_source") or {}),\n'
                                '    )\n',
                                '        tpex_complete=_tpc if isinstance(_tpc, bool) else None,\n    )\n'),
                               ('\n'
                                '#: 持股標示來源的說法（👤 我的 P1）。分區名一律走 `ia_nav`（⛔ 不手抄）。\n'
                                'HOLDING_SOURCE_NO_SHEET: str = "尚未選 Sheet → 到" + '
                                'ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET)\n'
                                'HOLDING_SOURCE_NOT_SELECTED: str = ("尚未選定組合／觀察清單 → 到"\n'
                                '                                    + '
                                'ia_nav.where_to_find(ia_nav.SECTION_ME_CONTENT))\n'
                                'HOLDING_SOURCE_FAILED: str = "讀不到你選定的組合／觀察清單（板塊圖照常）："\n'
                                '# PR #927 QA-2 第 3／4 點：照實分辨「沒登入 / 登入失效 / 兩本不同 / 選定的不見了 / 沒有分頁」，\n'
                                '#   失敗只講分類白話（~~`HOLDING_SOURCE_FAILED + scrub_secrets(error)`~~：例外原文可能含完整 '
                                'Sheet ID；\n'
                                '#   有意識的修改，⛔ 不是漏改）。\n'
                                'HOLDING_SOURCE_NOT_LOGGED_IN: str = ("尚未登入 Google → 到" + '
                                'ia_nav.where_to_find(ia_nav.SECTION_ME_ACCOUNT)\n'
                                '                                     + "登入後再選 Sheet")\n'
                                'HOLDING_SOURCE_LOGIN_EXPIRED: str = "Google 登入已失效 → 到" + '
                                'ia_nav.where_to_find(ia_nav.SECTION_ME_ACCOUNT) + "重新登入"\n'
                                'HOLDING_SOURCE_DIVERGED: str = ("你的組合和觀察清單目前讀的是兩本不同的 Sheet → 到"\n'
                                '                                + '
                                'ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET) + "選定一本")\n'
                                'HOLDING_SOURCE_PF_MISSING: str = "組合：你選定的那本已不在這本 Sheet 裡"\n'
                                'HOLDING_SOURCE_WL_MISSING: str = "觀察清單：你選定的那份已不在這本 Sheet 裡"\n'
                                'HOLDING_SOURCE_PF_NO_TAB: str = "組合：這本 Sheet 還沒有組合分頁"\n'
                                'HOLDING_SOURCE_WL_NO_TAB: str = "觀察清單：這本 Sheet 還沒有觀察清單分頁"\n'
                                'HOLDING_SOURCE_RECHECK: str = " → 到" + '
                                'ia_nav.where_to_find(ia_nav.SECTION_ME_CONTENT) + "重新選定"\n'
                                '# PR #927 QA-2 複驗：組合 / 觀察清單**兩半各自**照實說（~~某一半有狀態、另一半「尚未選定」時只講有狀態那一半~~，\n'
                                '#   例：組合沒選 ＋ 觀察清單沒有分頁 ⇒ 只印「觀察清單：…沒有分頁」，組合那半整個不見；有意識的修改，⛔ 不是漏改）。\n'
                                'HOLDING_SOURCE_PF_NOT_SELECTED: str = "組合：尚未選定"\n'
                                'HOLDING_SOURCE_WL_NOT_SELECTED: str = "觀察清單：尚未選定"\n'
                                'HOLDING_SOURCE_PF_EMPTY: str = "組合：這本 Sheet 裡還沒有任何一本組合"\n'
                                'HOLDING_SOURCE_WL_SKIPPED: str = "觀察清單：你選了不使用"\n'
                                'HOLDING_SOURCE_PICK: str = " → 到" + '
                                'ia_nav.where_to_find(ia_nav.SECTION_ME_CONTENT) + "選定"\n'
                                '#: 讀取失敗分類 → 白話（代碼 SSOT 在 L1，經 L3 `me_account_service.read_status_codes()` '
                                '取）。\n'
                                'HOLDING_ISSUE_QUOTA: str = "Google 讀取額度暫時用完，稍後再試"\n'
                                'HOLDING_ISSUE_NETWORK: str = "網路連線失敗，稍後再試"\n'
                                'HOLDING_ISSUE_DENIED: str = "你的 Google 帳號沒有這本 Sheet 的權限 → 確認分享設定，或到" + '
                                'ia_nav.where_to_find(\n'
                                '    ia_nav.SECTION_ME_SHEET) + "重新選一本"\n'
                                'HOLDING_ISSUE_NOT_FOUND: str = "找不到這本 Sheet（可能已刪除）→ 到" + '
                                'ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET) + "重新選一本"\n'
                                'HOLDING_ISSUE_OTHER: str = "未預期的錯誤（{kind}）"\n'
                                '\n'
                                '\n'
                                'def _holding_issue_text(issue: str) -> str:\n'
                                '    from src.services import me_account_service as _ME\n'
                                '    _ok, _nf, _pd, _quota, _net = _ME.read_status_codes()\n'
                                '    _known = {_quota: HOLDING_ISSUE_QUOTA, _net: HOLDING_ISSUE_NETWORK, '
                                '_pd: HOLDING_ISSUE_DENIED,\n'
                                '              _nf: HOLDING_ISSUE_NOT_FOUND}\n'
                                '    if issue in _known:\n'
                                '        return _known[issue]\n'
                                '    return HOLDING_ISSUE_OTHER.format(kind=(str(issue or "").split(":", '
                                '1)[-1] or "不明"))\n'
                                '\n'
                                '\n'
                                'def _holding_source_text(src: Mapping[str, Any]) -> str:\n'
                                '    """L3 `holding_source` → 一句事實（⛔ 不猜：沒給 ⇒「未提供」；⛔ 不露例外原文）。"""\n'
                                '    if not src:\n'
                                '        return "未提供"\n'
                                '    from shared.sheet_id import ACTIVE_DIVERGED\n'
                                '    from src.services.holdings_service import SELECTION_MISSING\n'
                                '    _issue = str(src.get("error_issue") or "")\n'
                                '    if src.get("error"):\n'
                                '        if _issue == "login_required" or src.get("login_expired"):\n'
                                '            return HOLDING_SOURCE_LOGIN_EXPIRED\n'
                                '        return HOLDING_SOURCE_FAILED + _holding_issue_text(_issue)\n'
                                '    if not src.get("bound"):\n'
                                '        if src.get("active_state") == ACTIVE_DIVERGED:\n'
                                '            return HOLDING_SOURCE_DIVERGED\n'
                                '        if "logged_in" in src and not src.get("logged_in"):\n'
                                '            return HOLDING_SOURCE_LOGIN_EXPIRED if src.get("login_expired") '
                                'else HOLDING_SOURCE_NOT_LOGGED_IN\n'
                                '        return HOLDING_SOURCE_NO_SHEET\n'
                                '    from src.services.holdings_service import SELECTION_NOT_SELECTED, '
                                'SELECTION_SKIPPED\n'
                                '    _ws_missing = "worksheet_missing"\n'
                                '    _pf_n = src.get("portfolio_names_n")\n'
                                '    # 每一半回 (句子, 種類)；種類：name / gone（選定的不見了）/ pick（還沒選）/ fact（其餘事實）/ ""（不知道 ⇒ '
                                '⛔ 不猜）。\n'
                                '    if src.get("portfolio_name"):\n'
                                '        _pf = (f"組合「{src.get(\'portfolio_name\')}」", "name")\n'
                                '    elif src.get("portfolio_selection") == SELECTION_MISSING:\n'
                                '        _pf = (HOLDING_SOURCE_PF_MISSING, "gone")\n'
                                '    elif src.get("portfolio_issue") == _ws_missing:\n'
                                '        _pf = (HOLDING_SOURCE_PF_NO_TAB, "fact")\n'
                                '    elif isinstance(_pf_n, int) and not isinstance(_pf_n, bool) and _pf_n '
                                '== 0:\n'
                                '        _pf = (HOLDING_SOURCE_PF_EMPTY, "fact")\n'
                                '    elif src.get("portfolio_selection") == SELECTION_NOT_SELECTED:\n'
                                '        _pf = (HOLDING_SOURCE_PF_NOT_SELECTED, "pick")\n'
                                '    else:\n'
                                '        _pf = ("", "")\n'
                                '    if src.get("watchlist_name"):\n'
                                '        _wl = (f"觀察清單「{src.get(\'watchlist_name\')}」", "name")\n'
                                '    elif src.get("watchlist_selection") == SELECTION_MISSING:\n'
                                '        _wl = (HOLDING_SOURCE_WL_MISSING, "gone")\n'
                                '    elif src.get("watchlist_issue") == _ws_missing:\n'
                                '        _wl = (HOLDING_SOURCE_WL_NO_TAB, "fact")\n'
                                '    elif src.get("watchlist_selection") == SELECTION_SKIPPED:\n'
                                '        _wl = (HOLDING_SOURCE_WL_SKIPPED, "fact")\n'
                                '    elif src.get("watchlist_selection") == SELECTION_NOT_SELECTED:\n'
                                '        _wl = (HOLDING_SOURCE_WL_NOT_SELECTED, "pick")\n'
                                '    else:\n'
                                '        _wl = ("", "")\n'
                                '    _kinds = {_pf[1], _wl[1]} - {""}\n'
                                '    if not _kinds or _kinds == {"pick"}:\n'
                                '        return HOLDING_SOURCE_NOT_SELECTED   # 兩半都還沒選（或都不知道）⇒ 同一句（原文照舊）\n'
                                '    _parts = [_t for _t, _k in (_pf, _wl) if _t]\n'
                                '    _tail = (HOLDING_SOURCE_RECHECK if "gone" in _kinds\n'
                                '             else HOLDING_SOURCE_PICK if "pick" in _kinds else "")\n'
                                '    return "＋".join(_parts) + _tail\n'
                                '\n'
                                '\n'
                                'def build_sector_flow_card(flow: SectorFlowReadout\n',
                                '\ndef build_sector_flow_card(flow: SectorFlowReadout\n'),
                               ('                       "、".join(flow.insufficient)))\n'
                                '    # 👤 我的 P1（DEC-083 D／Q7，有意識的改指，⛔ 不是漏刪）：~~「未偵測到 —— 到 ETF 組合按「計算組合」，或設定\n'
                                '    #   個股組合雲端清單後才會標出」~~（新版模式看不到那兩個舊頁籤）→ 照實列出持股標示讀的是哪一份選定。\n'
                                '    _facts.append(("持股標示來源", _holding_source_text(flow.holding_source)))\n'
                                '    _facts.append((\n'
                                '        "你的持股板塊",\n'
                                '        "、".join(flow.highlight) if flow.highlight else '
                                '"未偵測到（見上一列的持股標示來源）"))\n'
                                '\n',
                                '                       "、".join(flow.insufficient)))\n'
                                '    _facts.append((\n'
                                '        "你的持股板塊",\n'
                                '        "、".join(flow.highlight) if flow.highlight else\n'
                                '        "未偵測到 —— 到 ETF 組合按「計算組合」，或設定個股組合雲端清單後才會標出"))\n'
                                '\n')),
 'src/ui/views/page_hold.py': (('#    ⛔ 不多 import 任何 `src.services.*` / `src.compute.*` / '
                                '`src.data.*`（唯讀白名單不變）。\n'
                                'from shared.sheet_id import ACTIVE_DIVERGED\n'
                                'from src.ui.views.page_today import (\n'
                                '    SHEET_DIVERGED_WHERE,\n'
                                '    SHEET_UNBOUND_WHERE,\n'
                                '    V2_CSS_MODE,\n',
                                '#    ⛔ 不多 import 任何 `src.services.*` / `src.compute.*` / '
                                '`src.data.*`（唯讀白名單不變）。\n'
                                'from src.ui.views.page_today import (\n'
                                '    V2_CSS_MODE,\n'),
                               ('SETUP_WHERE: str = '
                                'ia_nav.where_to_find(ia_nav.SECTION_HOLD_PORTFOLIO_SETUP)\n'
                                '\n'
                                '# ── 👤 我的 P1（DEC-083 D 段）：兩類指路 ─────────────────────────────────\n'
                                '# 客戶原文：「Sheet／登入／切換相關提示 → 統一導向『👤 我的』。需要修改持股／組合／觀察清單內容：P1 尚未提供 CRUD，\n'
                                '# 因此必須誠實指路：『目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。』不得再出現：新版模式看不到的頁面\n'
                                '# 卻叫使用者直接去點、指回自己的唯讀頁、寫著有控制項但實際沒有。」\n'
                                '#: 甲類（Sheet／登入／切換）的去處（ia_nav 組字，⛔ 不手抄）。\n'
                                'ME_SHEET_WHERE: str = ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET)\n'
                                'ME_CONTENT_WHERE: str = ia_nav.where_to_find(ia_nav.SECTION_ME_CONTENT)\n'
                                'ME_ACCOUNT_WHERE: str = ia_nav.where_to_find(ia_nav.SECTION_ME_ACCOUNT)\n'
                                '\n'
                                '\n'
                                'def _edit_where(task: str, tail: str = "") -> str:\n'
                                '    """乙類（要改 Sheet 裡的內容）的「去哪補」：`{要做什麼}：{客戶原句}{之後}`。客戶句原封不動（`ia_nav`）。"""\n'
                                '    return f"{task}：{ia_nav.CONTENT_EDIT_OLD_UI_WHERE}{tail}"\n'
                                '\n',
                                'SETUP_WHERE: str = '
                                'ia_nav.where_to_find(ia_nav.SECTION_HOLD_PORTFOLIO_SETUP)\n'
                                '\n'),
                               ('    "也不在畫面上放一顆按了會改資料的鈕")\n'
                                '#: 📌 👤 我的 P1（DEC-083 D 段，有意識的改指，⛔ 不是漏刪）：~~「{NO_EXIT_MARKER}（本頁刻意沒有這個出口）——\n'
                                '#:    現行入口仍在既有的 📁 組合管理分頁；要在本頁做，必須先由客戶拍板「這一頁可以寫入」，再補一支寫入型 L3\n'
                                '#:    並補上二次確認與失敗回報」~~（新版模式看不到那個分頁；客戶已指定這一句）→ 客戶原句原封不動。\n'
                                'READONLY_WHERE: str = ia_nav.CONTENT_EDIT_OLD_UI_WHERE\n'
                                '#: 「Sheet 選擇」那張卡（甲類）：選 Sheet / 選組合是全站共用的選擇，集中在「👤 我的」。\n'
                                'PICK_SHEET_WHY: str = (\n'
                                '    "選哪一本 Sheet、分析哪一本組合是**全站共用**的選擇，集中在"\n'
                                '    + ia_nav.where_to_find(ia_nav.PAGE_ME) + "（本頁不另放一份，兩份會各說各話）；"\n'
                                '    "本頁對你的持股帳本仍**一律唯讀**")\n'
                                'PICK_SHEET_WHERE: str = f"到{ME_SHEET_WHERE}選一本 '
                                'Sheet，再到{ME_CONTENT_WHERE}選定要分析的組合"\n'
                                '\n',
                                '    "也不在畫面上放一顆按了會改資料的鈕")\n'
                                'READONLY_WHERE: str = (\n'
                                '    f"{NO_EXIT_MARKER}（本頁刻意沒有這個出口）—— "\n'
                                '    "現行入口仍在既有的 📁 組合管理分頁；"\n'
                                '    "要在本頁做，必須先由客戶拍板「這一頁可以寫入」，"\n'
                                '    "再補一支寫入型 L3 並補上二次確認與失敗回報")\n'
                                '\n'),
                               ('    sheet_issue: str = ""\n'
                                '    #: PR #927 QA-2 第 4 點(只加不改):組合 / 觀察清單兩條通道是兩本不同的 Sheet(L3 `active_state '
                                '== ACTIVE_DIVERGED`)\n'
                                '    #: → 「未綁」灰卡改說「兩本不同，請選定一本」(⛔ 不說「你還沒有綁定」「新使用者灰色正常」—— 對綁過兩本的人是假的)。\n'
                                '    diverged: bool = False\n'
                                '\n',
                                '    sheet_issue: str = ""\n\n'),
                               ('        )\n'
                                '        # 👤 我的 P1（DEC-083）：~~`get_binding_state()`（legacy 通道 ＋ secrets '
                                '預設）~~ → 新版 SSOT（與持股清單同一本）。\n'
                                '        _s = get_binding_state(ssot=True)\n'
                                '    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞\n',
                                '        )\n'
                                '        _s = get_binding_state()\n'
                                '    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞\n'),
                               ('        count_missing_reason=_reason,\n'
                                '        sheet_issue=str(getattr(_s, "sheet_issue", "") or ""),\n'
                                '        diverged=str(getattr(_s, "active_state", "") or "") == '
                                'ACTIVE_DIVERGED)\n'
                                '\n',
                                '        count_missing_reason=_reason,\n'
                                '        sheet_issue=str(getattr(_s, "sheet_issue", "") or ""))\n'
                                '\n'),
                               ('    login_expired: bool = False\n'
                                '    #: 👤 我的 P1(只加不改,DEC-083 Q7):L3 `HoldingsResult.portfolio_selection` '
                                '原樣搬運(`SELECTION_*`)。\n'
                                '    portfolio_selection: str = ""\n'
                                '    #: 👤 我的 P1:觀察清單那半的選定狀態(只用於事實列,不參與狀態判定)。\n'
                                '    watchlist_selection: str = ""\n'
                                '    #: PR #927 QA-2 第 4 點(只加不改):兩條通道是兩本不同的 Sheet(同 '
                                '`BindingReadout.diverged`)。\n'
                                '    diverged: bool = False\n'
                                '\n',
                                '    login_expired: bool = False\n\n'),
                               ('                               error=repr(_e), '
                                'sheet_issue=sheet_read_issue(_e))\n'
                                '    # 👤 我的 P1（DEC-083 Q7）：組合沒選定 / 選定名稱不在了 → 本頁**不分析**（AI 總管裁示：沒選定 → 不分析）。\n'
                                '    # L3 那一側仍會照觀察清單自己的選定讀觀察清單（給別頁用）；本頁把它一併收起來，否則戰情室會只拿觀察清單\n'
                                '    # 跑出一整排「沒有持股」的說法（例：配息卡叫你「新增至少一列持股」—— 你明明有，只是還沒選）。\n'
                                '    from src.services.holdings_service import SELECTION_MISSING, '
                                'SELECTION_NOT_SELECTED\n'
                                '    _pf_sel = str(getattr(_h, "portfolio_selection", "") or "")\n'
                                '    _rows = (() if _pf_sel in (SELECTION_NOT_SELECTED, SELECTION_MISSING)\n'
                                '             else tuple(dict(_r) for _r in (getattr(_h, "holdings", ()) or '
                                '())))\n'
                                '    return HoldingsReadout(\n'
                                '        requested=True, submitted=req.submitted,\n'
                                '        holdings=_rows,\n'
                                '        bound=bool(getattr(_h, "bound", False)),\n',
                                '                               error=repr(_e), '
                                'sheet_issue=sheet_read_issue(_e))\n'
                                '    return HoldingsReadout(\n'
                                '        requested=True, submitted=req.submitted,\n'
                                '        holdings=tuple(dict(_r) for _r in (getattr(_h, "holdings", ()) or '
                                '())),\n'
                                '        bound=bool(getattr(_h, "bound", False)),\n'),
                               ('        watchlist_error=str(getattr(_h, "watchlist_error", "") or ""),\n'
                                '        login_expired=bool(getattr(_h, "login_expired", False)),\n'
                                '        portfolio_selection=_pf_sel,\n'
                                '        watchlist_selection=str(getattr(_h, "watchlist_selection", "") or '
                                '""),\n'
                                '        diverged=str(getattr(_h, "active_state", "") or "") == '
                                'ACTIVE_DIVERGED)\n'
                                '\n',
                                '        watchlist_error=str(getattr(_h, "watchlist_error", "") or ""),\n'
                                '        login_expired=bool(getattr(_h, "login_expired", False)))\n'
                                '\n'),
                               ('    login_expired: bool = False\n'
                                '    #: 👤 我的 P1:由 `HoldingsReadout.portfolio_selection` 帶下來 —— 「綁了但沒選定」的灰卡（⛔ '
                                '不是「Sheet 是空的」）。\n'
                                '    portfolio_selection: str = ""\n'
                                '    #: PR #927 QA-2 第 4 點:由 `HoldingsReadout.diverged` 帶下來 —— '
                                '「還沒綁」那幾張灰卡改說「兩本不同」。\n'
                                '    diverged: bool = False\n'
                                '    rows: tuple[dict, ...] = ()\n',
                                '    login_expired: bool = False\n    rows: tuple[dict, ...] = ()\n'),
                               ('        return StationReadout(requested=True, '
                                'submitted=holdings.submitted,\n'
                                '                              bound=holdings.bound, '
                                'login_expired=holdings.login_expired,\n'
                                '                              '
                                'portfolio_selection=holdings.portfolio_selection,\n'
                                '                              diverged=holdings.diverged)\n'
                                '    try:\n',
                                '        return StationReadout(requested=True, '
                                'submitted=holdings.submitted,\n'
                                '                              bound=holdings.bound, '
                                'login_expired=holdings.login_expired)\n'
                                '    try:\n'),
                               ('#:    舊句在「不使用」模式下仍是真的，只是本頁不在那個模式裡。\n'
                                '#: 📌 👤 我的 P1（DEC-083 D 段，有意識的改指，⛔ 不是漏刪）：~~「…**現行入口在側欄「🔐 Google 帳號」的「Google '
                                'Sheet ID\n'
                                '#:    或完整 URL（系統會自動解析 ID）」**…」~~ → 開頭改用「🚦 '
                                '今天」頁同一句（`page_today.SHEET_UNBOUND_WHERE`，\n'
                                '#:    指「👤 我的」）；後半一字未改。\n'
                                'NOT_BOUND_WHERE: str = (\n'
                                '    SHEET_UNBOUND_WHERE\n'
                                '    + "（本頁只讀不寫，所以不在這裡放選 Sheet 的控制項）；"\n'
                                '    "綁定狀態在下面的**葉2 組合設定**看得到")\n',
                                '#:    舊句在「不使用」模式下仍是真的，只是本頁不在那個模式裡。\n'
                                'NOT_BOUND_WHERE: str = (\n'
                                '    "用 Google 登入後選一本持股 Sheet —— **現行入口在側欄「🔐 Google 帳號」的「Google Sheet ID 或完整 '
                                'URL（系統會自動解析 ID）」**"\n'
                                '    "（本頁只讀不寫，所以不在這裡放選 Sheet 的控制項）；"\n'
                                '    "綁定狀態在下面的**葉2 組合設定**看得到")\n'),
                               ('    "自動恢復的登入大約 1 小時後就會逾時。**這不是故障**，你的 Sheet 也沒有出問題")\n'
                                '#: 📌 👤 我的 P1（DEC-083 D 段，有意識的改指，⛔ 不是漏刪）：~~`LOGIN_EXPIRED_WHERE = '
                                'OAUTH_LOGIN_EXPIRED_MSG`~~\n'
                                '#:    （L0 那一句叫人「按側欄「🔐 用 Google 登入」」；L0 句**不改** —— L1 拋例外、側欄仍用它）→ 本頁自有一句，\n'
                                '#:    重新登入改指「👤 我的 › Google 帳號」。開頭「請重新整理頁面以自動恢復登入」與 L0 原句逐字相同。\n'
                                'LOGIN_EXPIRED_WHERE: str = f"請重新整理頁面以自動恢復登入，或到{ME_ACCOUNT_WHERE}重新登入。"\n'
                                '\n'
                                '\n'
                                '#: PR #927 QA-2 第 4 點：組合 / 觀察清單兩條通道是兩本不同的 '
                                'Sheet（`ACTIVE_DIVERGED`）時取代「還沒綁」那一組\n'
                                '#: （同一批卡、同一個灰色）。~~這一態原本落進 `NOT_BOUND_*`「你還沒有綁定持股 Sheet／新使用者灰色正常」~~ ——\n'
                                '#: 對已經綁過兩本的人是假的（有意識的修改，⛔ 不是漏改）。where 與「🚦 今天」狀態列同一句（⛔ 不寫第二份）。\n'
                                'DIVERGED_NOW: str = "**你的組合和觀察清單目前讀的是兩本不同的 Sheet**"\n'
                                'DIVERGED_WHY: str = (\n'
                                '    "**這不是故障**：兩邊各記著一本 Sheet，本站不替你挑一本，所以這一輪不讀持股 —— "\n'
                                '    "本站不拿其中一本頂替（那會讓你以為畫面上是你選的那一本）")\n'
                                'DIVERGED_WHERE: str = SHEET_DIVERGED_WHERE\n'
                                '\n'
                                '\n'
                                'def _not_bound_note(login_expired: bool, diverged: bool = False) -> Note:\n'
                                '    """「還沒綁 / 沒登入」那一句 —— 登入已逾時時換成逾時那一組；兩本不同時換成「請選定一本」(都是灰色有效態)。"""\n'
                                '    if diverged and not login_expired:\n'
                                '        return Note(now=DIVERGED_NOW, why=DIVERGED_WHY, '
                                'where=DIVERGED_WHERE)\n'
                                '    if login_expired:\n',
                                '    "自動恢復的登入大約 1 小時後就會逾時。**這不是故障**，你的 Sheet 也沒有出問題")\n'
                                'LOGIN_EXPIRED_WHERE: str = OAUTH_LOGIN_EXPIRED_MSG\n'
                                '\n'
                                '\n'
                                'def _not_bound_note(login_expired: bool) -> Note:\n'
                                '    """「還沒綁 / 沒登入」那一句 —— 登入已逾時時換成逾時那一組(兩者都是灰色有效態)。"""\n'
                                '    if login_expired:\n'),
                               ('    "⚠️ 這與上一種**不是同一件事**：你已經綁好了，缺的是內容")\n'
                                '#: 📌 👤 我的 P1（D 段，有意識的改指）：~~「到既有的 📁 組合管理分頁新增一本組合並填入持股列（代號／張數／均價），\n'
                                '#:    填完回本頁…」~~ → 乙類客戶原句（`_edit_where`）。\n'
                                'EMPTY_SHEET_WHERE: str = _edit_where(\n'
                                '    "新增一本組合並填入持股列（代號／張數／均價）",\n'
                                '    f"填完回本頁{press(ACTION_RUN_WARROOM_LABEL)}")\n'
                                '\n'
                                '#: 👤 我的 P1（DEC-083 Q7）：讀到了組合清單、但使用者還沒選定（或選定的名稱不在了）—— **灰**，有效結果。\n'
                                '#: 客戶原文：「不得再以『名稱排序第一本』作為不可見的業務決策。」AI 總管裁示：沒選定 → 不分析（只有一本也一樣）。\n'
                                'NOT_SELECTED_NOW: str = "**你還沒有選定要分析哪一本組合**"\n'
                                'NOT_SELECTED_WHY: str = (\n'
                                '    "**這是一個有效的結果**（已經讀到這本 Sheet 的組合清單）—— "\n'
                                '    "本站**不替你挑**，不以名稱排序第一本代替你決定")\n'
                                'SELECTION_MISSING_NOW: str = "**你選定的組合在這本 Sheet 裡找不到**"\n'
                                'SELECTION_MISSING_WHY: str = (\n'
                                '    "可能在 Sheet 上被改名或刪掉了 —— 本站不改讀別本頂替")\n'
                                'SELECT_PORTFOLIO_WHERE: str = '
                                'f"到{ME_CONTENT_WHERE}選定要分析的組合，回本頁{press(ACTION_RUN_WARROOM_LABEL)}"\n'
                                '#: 葉2 開頭的指路（甲類）。\n'
                                'SETUP_ME_POINTER: str = (f"要換 '
                                'Sheet、選定要分析的組合／觀察清單：到{ia_nav.where_to_find(ia_nav.PAGE_ME)}"\n'
                                '                         "（本葉只顯示狀態，不能改）。")\n'
                                '\n'
                                '\n'
                                'def _selection_note(selection: str) -> "Note | None":\n'
                                '    """`HoldingsResult.portfolio_selection` → 灰卡三要素；不是「沒選 / 名稱不在」→ '
                                'None（走原本的分支）。"""\n'
                                '    from src.services.holdings_service import SELECTION_MISSING, '
                                'SELECTION_NOT_SELECTED\n'
                                '    if selection == SELECTION_NOT_SELECTED:\n'
                                '        return Note(now=NOT_SELECTED_NOW, why=NOT_SELECTED_WHY, '
                                'where=SELECT_PORTFOLIO_WHERE)\n'
                                '    if selection == SELECTION_MISSING:\n'
                                '        return Note(now=SELECTION_MISSING_NOW, why=SELECTION_MISSING_WHY, '
                                'where=SELECT_PORTFOLIO_WHERE)\n'
                                '    return None\n'
                                '\n',
                                '    "⚠️ 這與上一種**不是同一件事**：你已經綁好了，缺的是內容")\n'
                                'EMPTY_SHEET_WHERE: str = (\n'
                                '    "到既有的 📁 組合管理分頁新增一本組合並填入持股列（代號／張數／均價），"\n'
                                '    f"填完回本頁{press(ACTION_RUN_WARROOM_LABEL)}")\n'
                                '\n'),
                               ('#:    「戰情表一列都沒有回來」—— 而這一種戰情表是有列的（觀察列），那句是假的。\n'
                                '#: 📌 👤 我的 P1（DEC-083 D 段，客戶裁示取代 E3-r1 那一句；有意識的改指，⛔ 不是漏刪）：\n'
                                '#:    ~~"到「💼 我的持股 › 組合設定」，在你的持股表新增至少一列持股（要有代號、張數、均價）。"~~\n'
                                '#:    （那是**指回自己的唯讀頁** —— 客戶 D 段點名禁止）→ 客戶原句 ＋ E3-r1 原句後半（「在你的持股表…」一字未改）。\n'
                                '#: 📌 PR #927 QA-2 第 6 點（有意識的修改，⛔ 不是漏改）：~~客戶原句 ＋「在你的持股表新增…」~~（先講去哪、後講要做什麼，\n'
                                '#:    讀起來像是「切回舊版」本身就能新增）→ 動作在前、客戶原句在後（同 `_edit_where` 的順序）；客戶原句一字未改。\n'
                                'CASH_WATCHLIST_ONLY_WHERE: str = _edit_where("在你的持股表新增至少一列持股（要有代號、張數、均價）")\n'
                                'CASH_NO_PAYOUT_NOW: str = "**近一年查不到任何一筆配息**"\n',
                                '#:    「戰情表一列都沒有回來」—— 而這一種戰情表是有列的（觀察列），那句是假的。\n'
                                'CASH_WATCHLIST_ONLY_WHERE: str = "到「💼 我的持股 › '
                                '組合設定」，在你的持股表新增至少一列持股（要有代號、張數、均價）。"\n'
                                'CASH_NO_PAYOUT_NOW: str = "**近一年查不到任何一筆配息**"\n'),
                               ('COUNT_NOT_BOUND_NOW: str = "**還沒有可以數的 Sheet**"\n'
                                '#: PR #927 QA-2 第 4 點：兩本不同（`BindingReadout.diverged`）時這一格的 why / where。\n'
                                'COUNT_DIVERGED_WHY: str = ("上一張卡顯示你的組合和觀察清單讀的是**兩本不同的 Sheet** —— "\n'
                                '                           '
                                '"還沒選定一本，就沒有人問過「那一本裡有幾本組合」。**這不是失敗，是這個問題還沒有成立**")\n'
                                'COUNT_DIVERGED_WHERE: str = "先照上一張卡說的選定一本，這一格會自己有東西"\n'
                                'COUNT_DRIFT_NOW: str = "**綁定看起來正常，但讀不到組合清單**"\n',
                                'COUNT_NOT_BOUND_NOW: str = "**還沒有可以數的 Sheet**"\n'
                                'COUNT_DRIFT_NOW: str = "**綁定看起來正常，但讀不到組合清單**"\n'),
                               ('#:    修前那句「到 📁 組合管理補齊即可」對它是錯的指引（§1）。\n'
                                '#: 📌 👤 我的 P1（D 段，有意識的改指）：~~"若是缺張數／均價，到既有的 📁 組合管理分頁補齊"~~ → 乙類客戶原句。\n'
                                '#: 條件子句的前半（短句表摘錄同一個常數，⛔ 不另抄一份）。\n'
                                'IF_LOTS_AVG_MISSING_TASK: str = "若是缺張數／均價"\n'
                                'IF_LOTS_AVG_MISSING_WHERE: str = _edit_where(IF_LOTS_AVG_MISSING_TASK)\n'
                                '\n',
                                '#:    修前那句「到 📁 組合管理補齊即可」對它是錯的指引（§1）。\n'
                                'IF_LOTS_AVG_MISSING_WHERE: str = "若是缺張數／均價，到既有的 📁 組合管理分頁補齊"\n'
                                '\n'),
                               ('    if station.bound:\n'
                                '        return (_selection_note(station.portfolio_selection)\n'
                                '                or Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY, '
                                'where=EMPTY_SHEET_WHERE))\n'
                                '    return _not_bound_note(station.login_expired, station.diverged)\n'
                                '\n',
                                '    if station.bound:\n'
                                '        return Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY, '
                                'where=EMPTY_SHEET_WHERE)\n'
                                '    return _not_bound_note(station.login_expired)\n'
                                '\n'),
                               ('            # P1a-f2：檔數核對用**去重前**的原清單（L3 按列數）；顯示時同代號只列一次。\n'
                                '            # 👤 我的 P1：條件子句改為客戶原句（句號結尾）⇒ 後綴 ~~「；沒有納入：」~~ → 「沒有納入：」。\n'
                                '            + ("沒有納入：" + "、".join(dict.fromkeys(_codes))\n'
                                '               if _codes and len(_codes) == _held_n - _valued_n else '
                                '"")))\n',
                                '            # P1a-f2：檔數核對用**去重前**的原清單（L3 按列數）；顯示時同代號只列一次。\n'
                                '            + ("；沒有納入：" + "、".join(dict.fromkeys(_codes))\n'
                                '               if _codes and len(_codes) == _held_n - _valued_n else '
                                '"")))\n'),
                               ('                 "三檔各一張與三檔各一百張，配置完全不同"),\n'
                                '            # 👤 我的 P1（D 段）：~~「到既有的 📁 組合管理分頁把持股的**張數**與**均價**補齊，回本頁…」~~\n'
                                '            where=_edit_where("把持股的**張數**與**均價**補齊",\n'
                                '                              f"補齊後回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.alloc_split", label="80/20 配置偏離（該減）",\n',
                                '                 "三檔各一張與三檔各一百張，配置完全不同"),\n'
                                '            where=("到既有的 📁 組合管理分頁把持股的**張數**與**均價**補齊，"\n'
                                '                   f"回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.alloc_split", label="80/20 配置偏離（該減）",\n'),
                               ('                 "但下面那一列會告訴你缺的是什麼"),\n'
                                '            # 👤 我的 P1（D 段）：~~「若你預期應該要有：到 📁 組合管理確認那幾檔**個股**的均價有填；補齊後…」~~\n'
                                '            where=_edit_where("若你預期應該要有：確認那幾檔**個股**的均價有填",\n'
                                '                              f"補齊後回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.take_profit", label="衛星停利",\n',
                                '                 "但下面那一列會告訴你缺的是什麼"),\n'
                                '            where=("若你預期應該要有：到 📁 組合管理確認那幾檔**個股**的均價有填；"\n'
                                '                   f"補齊後回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.take_profit", label="衛星停利",\n'),
                               ('    login_expired: bool = False\n'
                                '    #: 👤 我的 P1(只加不改):由戰情表帶下來(同 `StationReadout.portfolio_selection`)。\n'
                                '    portfolio_selection: str = ""\n'
                                '    #: PR #927 QA-2 第 4 點(只加不改):由戰情表帶下來(同 `StationReadout.diverged`)。\n'
                                '    diverged: bool = False\n'
                                '    has_station_rows: bool = False\n',
                                '    login_expired: bool = False\n    has_station_rows: bool = False\n'),
                               ('    _shared = {"submitted": station.submitted, "bound": station.bound,\n'
                                '               "holdings_n": station.holdings_n, "login_expired": '
                                'station.login_expired,\n'
                                '               "portfolio_selection": station.portfolio_selection, '
                                '"diverged": station.diverged}\n'
                                '    if not station.requested:\n',
                                '    _shared = {"submitted": station.submitted, "bound": station.bound,\n'
                                '               "holdings_n": station.holdings_n, "login_expired": '
                                'station.login_expired}\n'
                                '    if not station.requested:\n'),
                               ('    if deep.bound:\n'
                                '        return (_selection_note(deep.portfolio_selection)\n'
                                '                or Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY,\n'
                                '                        where=EMPTY_SHEET_WHERE))\n'
                                '    return _not_bound_note(deep.login_expired, deep.diverged)\n'
                                '\n',
                                '    if deep.bound:\n'
                                '        return Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY,\n'
                                '                    where=EMPTY_SHEET_WHERE)\n'
                                '    return _not_bound_note(deep.login_expired)\n'
                                '\n'),
                               ('              "**本頁不替任何一邊背書**",\n'
                                '            # 👤 我的 P1（D 段）：~~「到既有的 📁 組合管理分頁把持股的**張數／均價**補齊（…），再回本頁…」~~\n'
                                '            _edit_where("把持股的**張數／均價**補齊（兩套算法差的多半就是那幾列）",\n'
                                '                        f"再回本頁{press(ACTION_RUN_WARROOM_LABEL)}")))\n'
                                '    _no_price = tuple(getattr(result, "no_price", ()) or ())\n',
                                '              "**本頁不替任何一邊背書**",\n'
                                '            "到既有的 📁 組合管理分頁把持股的**張數／均價**補齊"\n'
                                '            "（兩套算法差的多半就是那幾列），"\n'
                                '            f"再回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    _no_price = tuple(getattr(result, "no_price", ()) or ())\n'),
                               ('             "而偏小的總額看起來跟正確的總額一模一樣")\n'
                                '    # 👤 我的 P1（D 段）：~~「到既有的 📁 組合管理分頁確認上面那幾檔的**代號與張數**（…），再回本頁…」~~\n'
                                '    _where = _edit_where("確認上面那幾檔的**代號與張數**"\n'
                                '                         "（張數太小、四捨五入後股數為 0 的會被上游整筆略過）",\n'
                                '                         f"再回本頁{press(ACTION_RUN_WARROOM_LABEL)}")\n'
                                '    if _os_hit:\n',
                                '             "而偏小的總額看起來跟正確的總額一模一樣")\n'
                                '    _where = ("到既有的 📁 組合管理分頁確認上面那幾檔的**代號與張數**"\n'
                                '              "（張數太小、四捨五入後股數為 0 的會被上游整筆略過），"\n'
                                '              f"再回本頁{press(ACTION_RUN_WARROOM_LABEL)}")\n'
                                '    if _os_hit:\n'),
                               ('                   "承受同一個跌幅的損失完全不同"),\n'
                                '            # 👤 我的 P1（D 段）：~~「到既有的 📁 組合管理分頁把持股的**張數**與**均價**補齊，回本頁…」~~\n'
                                '            where=_edit_where("把持股的**張數**與**均價**補齊",\n'
                                '                              f"補齊後回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.deep.stress", label="壓力測試",\n',
                                '                   "承受同一個跌幅的損失完全不同"),\n'
                                '            where=("到既有的 📁 組合管理分頁把持股的**張數**與**均價**補齊，"\n'
                                '                   f"回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.deep.stress", label="壓力測試",\n'),
                               ('                 + _deep_reason(_res)),\n'
                                '            # 👤 我的 P1（D 段）：~~「到既有的 📁 組合管理分頁把持股的**張數**補齊，回本頁…」~~\n'
                                '            where=_edit_where("把持股的**張數**補齊",\n'
                                '                              f"補齊後回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.deep.dividend_cash", label="配息現金流",\n',
                                '                 + _deep_reason(_res)),\n'
                                '            where=("到既有的 📁 組合管理分頁把持股的**張數**補齊，"\n'
                                '                   f"回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.deep.dividend_cash", label="配息現金流",\n'),
                               ('        #    改的時候一定會漏改一份，於是兩張卡對同一個狀況給出兩種說法。\n'
                                '        _note = _not_bound_note(binding.login_expired, binding.diverged)\n'
                                '    return Card(key="hold.binding", label="Google Sheet 綁定",\n',
                                '        #    改的時候一定會漏改一份，於是兩張卡對同一個狀況給出兩種說法。\n'
                                '        _note = _not_bound_note(binding.login_expired)\n'
                                '    return Card(key="hold.binding", label="Google Sheet 綁定",\n'),
                               ('        _note = Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)\n'
                                '    elif _state == UI_IDLE and binding.diverged:\n'
                                '        # PR #927 QA-2 第 4 點：兩本不同時上一張卡**沒有**說「還沒有綁定」⇒ ⛔ 不沿用下一支那句假敘述。\n'
                                '        _note = Note(now=COUNT_NOT_BOUND_NOW, why=COUNT_DIVERGED_WHY, '
                                'where=COUNT_DIVERGED_WHERE)\n'
                                '    elif _state == UI_IDLE:\n',
                                '        _note = Note(now=IDLE_NOW, why=IDLE_WHY, where=IDLE_WHERE)\n'
                                '    elif _state == UI_IDLE:\n'),
                               ('                 "剛建好 Sheet 還沒填內容時，這裡本來就該是灰的"),\n'
                                '            # 👤 我的 P1（D 段）：~~「到既有的 📁 組合管理分頁新增一本組合並填入持股列；填完回本頁…」~~\n'
                                '            where=_edit_where("新增一本組合並填入持股列",\n'
                                '                              f"填完回本頁{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.portfolio_count", label="這本 Sheet 裡的組合",\n',
                                '                 "剛建好 Sheet 還沒填內容時，這裡本來就該是灰的"),\n'
                                '            where=("到既有的 📁 組合管理分頁新增一本組合並填入持股列；"\n'
                                '                   "填完回本頁"\n'
                                '                   f"{press(ACTION_RUN_WARROOM_LABEL)}"))\n'
                                '    return Card(key="hold.portfolio_count", label="這本 Sheet 裡的組合",\n'),
                               ('        now=PICK_SHEET_UNWIRED_NOW,\n'
                                '        # 👤 我的 P1（D 段，有意識的改指，⛔ 不是漏刪）：~~why=READONLY_WHY, '
                                'where=READONLY_WHERE~~（選 Sheet 不是改\n'
                                '        #   Sheet 內容；那句「本質上是寫入」對它不成立）＋ ~~「現行入口」＝側欄「🔐 Google 帳號」~~ → 「👤 '
                                '我的」。\n'
                                '        why=PICK_SHEET_WHY, where=PICK_SHEET_WHERE,\n'
                                '        facts=(("為什麼", "選 Sheet 會改寫你的綁定設定 —— 那是寫入"),\n'
                                '               ("現行入口", ME_SHEET_WHERE))),\n'
                                '    UnwiredSpec(\n',
                                '        now=PICK_SHEET_UNWIRED_NOW,\n'
                                '        why=READONLY_WHY, where=READONLY_WHERE,\n'
                                '        # 批 Z54：「現行入口」同 `NOT_BOUND_WHERE` 的更正（新版模式看不到 📁 組合管理分頁）。\n'
                                '        facts=(("為什麼", "選 Sheet 會改寫你的綁定設定 —— 那是寫入"),\n'
                                '               ("現行入口", "側欄「🔐 Google 帳號」的「Google Sheet ID 或完整 URL（系統會自動解析 '
                                'ID）」"))),\n'
                                '    UnwiredSpec(\n'),
                               ('        facts=(("為什麼", "新增或移除觀察清單會寫回你的 Sheet —— 那是寫入"),\n'
                                '               # 👤 我的 P1（D 段）：~~「既有的 📁 組合管理分頁 ／ 選股網的「加入觀察清單」」~~ → 客戶原句。\n'
                                '               # PR #927 QA-2 第 6 點：~~客戶原句 ＋「選股網的「加入觀察清單」同在舊版」~~ → '
                                '動作在前（`_edit_where`）。\n'
                                '               ("現行入口", _edit_where("要管理觀察清單（含選股網的「加入觀察清單」）")))),\n'
                                ')\n',
                                '        facts=(("為什麼", "新增或移除觀察清單會寫回你的 Sheet —— 那是寫入"),\n'
                                '               ("現行入口", "既有的 📁 組合管理分頁 ／ 選股網的「加入觀察清單」"))),\n'
                                ')\n'),
                               ('    if holdings.more_portfolios or holdings.more_watchlists:\n'
                                '        # 👤 我的 P1（DEC-083 Q7，有意識的修改，⛔ 不是漏刪）：~~「本頁只取**第一本**組合／**第一份**觀察清單\n'
                                '        #   （沿用既有行為）」~~（那正是客戶點名禁止的「名稱排序第一本」）→ 只分析使用者選定的那一本。\n'
                                '        _facts.append((\n'
                                '            "⚠️ 這本 Sheet 裡還有別的沒讀",\n'
                                '            f"本頁只分析你在{ME_CONTENT_WHERE}選定的那一本組合／那一份觀察清單 —— "\n'
                                '            "畫面上這幾檔**不是你的全部**"))\n'
                                '    if holdings.watchlist_selection:\n'
                                '        from src.services.holdings_service import SELECTION_NOT_SELECTED, '
                                'SELECTION_SKIPPED\n'
                                '        if holdings.watchlist_selection == SELECTION_NOT_SELECTED:\n'
                                '            _facts.append(("觀察清單", '
                                'f"還沒選定（不影響持股分析）；要選：到{ME_CONTENT_WHERE}"))\n'
                                '        elif holdings.watchlist_selection == SELECTION_SKIPPED:\n'
                                '            _facts.append(("觀察清單", "你選了不使用觀察清單"))\n'
                                '    if holdings.watchlist_error:\n',
                                '    if holdings.more_portfolios or holdings.more_watchlists:\n'
                                '        _facts.append((\n'
                                '            "⚠️ 這本 Sheet 裡還有別的沒讀",\n'
                                '            "本頁只取**第一本**組合／**第一份**觀察清單（沿用既有行為）—— "\n'
                                '            "畫面上這幾檔**不是你的全部**"))\n'
                                '    if holdings.watchlist_error:\n'),
                               ('    elif holdings.bound:\n'
                                '        _note = (_selection_note(holdings.portfolio_selection)\n'
                                '                 or Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY,\n'
                                '                         where=EMPTY_SHEET_WHERE))\n'
                                '    else:\n'
                                '        _note = _not_bound_note(holdings.login_expired, holdings.diverged)\n'
                                '    return Card(key="hold.setup.preview", label="持股列預覽",\n',
                                '    elif holdings.bound:\n'
                                '        _note = Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY,\n'
                                '                     where=EMPTY_SHEET_WHERE)\n'
                                '    else:\n'
                                '        _note = _not_bound_note(holdings.login_expired)\n'
                                '    return Card(key="hold.setup.preview", label="持股列預覽",\n'),
                               ('_V2_NO_EXIT_UNWIRED: str = NO_EXIT_MARKER + " —— 這是待接線項，不是你操作的問題"\n'
                                '#: 👤 我的 P1：~~"到既有的 📁 組合管理分頁把持股的張數與均價補齊，回本頁" + _V2_PRESS_RUN~~ → 新原文的摘錄。\n'
                                '_V2_OLD_UI: str = "目前請切回舊版 → 📁 組合管理"   # 客戶原句的開頭一段（K1：原文摘錄）\n'
                                '_V2_FILL_LOTS: str = ("把持股的張數與均價補齊" + V2_EXCERPT_GAP + _V2_OLD_UI + '
                                'V2_EXCERPT_GAP\n'
                                '                      + "回本頁" + _V2_PRESS_RUN)\n'
                                '#: 批 Z49：持有列資料異常那一句（客戶核准句；整句就是摘錄，代號清單在摺疊區原文）。\n',
                                '_V2_NO_EXIT_UNWIRED: str = NO_EXIT_MARKER + " —— 這是待接線項，不是你操作的問題"\n'
                                '_V2_FILL_LOTS: str = "到既有的 📁 組合管理分頁把持股的張數與均價補齊，回本頁" + _V2_PRESS_RUN\n'
                                '#: 批 Z49：持有列資料異常那一句（客戶核准句；整句就是摘錄，代號清單在摺疊區原文）。\n'),
                               ('                    "這是一個有效的結果" + V2_EXCERPT_GAP + "沒有綁定就沒有清單可讀",\n'
                                '                    # 👤 我的 P1：~~… + "現行入口在側欄「🔐 Google 帳號」"~~\n'
                                '                    "用 Google 登入後選一本持股 Sheet" + V2_EXCERPT_GAP + "到" + '
                                'ME_SHEET_WHERE + "選一本"),\n'
                                '    DIVERGED_NOW: (None,\n'
                                '                   "這不是故障" + V2_EXCERPT_GAP + "本站不替你挑一本",\n'
                                '                   "到" + ME_SHEET_WHERE + "選定一本"),\n'
                                '    LOGIN_EXPIRED_NOW: ("Google 登入已逾時",\n',
                                '                    "這是一個有效的結果" + V2_EXCERPT_GAP + "沒有綁定就沒有清單可讀",\n'
                                '                    "用 Google 登入後選一本持股 Sheet" + V2_EXCERPT_GAP + "現行入口在側欄「🔐 '
                                'Google 帳號」"),\n'
                                '    LOGIN_EXPIRED_NOW: ("Google 登入已逾時",\n'),
                               ('                      "這是一個有效的結果" + V2_EXCERPT_GAP + "你已經綁好了，缺的是內容",\n'
                                '                      # 👤 我的 P1：~~"到既有的 📁 組合管理分頁新增一本組合並填入持股列" + … + '
                                '填完回本頁…~~\n'
                                '                      "新增一本組合並填入持股列" + V2_EXCERPT_GAP + _V2_OLD_UI),\n'
                                '    NOT_SELECTED_NOW: ("你還沒有選定要分析哪一本組合",\n'
                                '                       "本站不替你挑，不以名稱排序第一本代替你決定",\n'
                                '                       v2_plain(SELECT_PORTFOLIO_WHERE)),\n'
                                '    SELECTION_MISSING_NOW: ("你選定的組合在這本 Sheet 裡找不到",\n'
                                '                            v2_plain(SELECTION_MISSING_WHY),\n'
                                '                            v2_plain(SELECT_PORTFOLIO_WHERE)),\n'
                                '    NO_ROWS_NOW: ("讀到了持股，但戰情表一列都沒有回來",\n',
                                '                      "這是一個有效的結果" + V2_EXCERPT_GAP + "你已經綁好了，缺的是內容",\n'
                                '                      "到既有的 📁 組合管理分頁新增一本組合並填入持股列"\n'
                                '                      + V2_EXCERPT_GAP + "填完回本頁" + _V2_PRESS_RUN),\n'
                                '    NO_ROWS_NOW: ("讀到了持股，但戰情表一列都沒有回來",\n'),
                               ('    "兩套算法對不起來", "抓不到價格序列", "這個總額只涵蓋一部分持股")\n'
                                '#: 👤 我的 P1：「到既有的 📁 組合管理分頁…」那幾個候選換成新原文的摘錄（舊候選見 git 歷史 / 還原鏈）。\n'
                                '_V2_DEGRADED_WHERE: tuple[str, ...] = (\n'
                                '    "把持股的張數／均價補齊" + V2_EXCERPT_GAP + _V2_OLD_UI + V2_EXCERPT_GAP + '
                                '"先確認這幾檔的代號是否正確",\n'
                                '    "把持股的張數／均價補齊" + V2_EXCERPT_GAP + _V2_OLD_UI,\n'
                                '    "先確認這幾檔的代號是否正確",\n'
                                '    "確認上面那幾檔的代號與張數" + V2_EXCERPT_GAP + _V2_OLD_UI + V2_EXCERPT_GAP + '
                                '"海外那幾檔請另按最低稅負制",\n'
                                '    "確認上面那幾檔的代號與張數" + V2_EXCERPT_GAP + _V2_OLD_UI)\n'
                                '\n',
                                '    "兩套算法對不起來", "抓不到價格序列", "這個總額只涵蓋一部分持股")\n'
                                '_V2_DEGRADED_WHERE: tuple[str, ...] = (\n'
                                '    "到既有的 📁 組合管理分頁把持股的張數／均價補齊" + V2_EXCERPT_GAP + "先確認這幾檔的代號是否正確",\n'
                                '    "到既有的 📁 組合管理分頁把持股的張數／均價補齊",\n'
                                '    "先確認這幾檔的代號是否正確",\n'
                                '    "到既有的 📁 組合管理分頁確認上面那幾檔的代號與張數" + V2_EXCERPT_GAP + "海外那幾檔請另按最低稅負制自行計算",\n'
                                '    "到既有的 📁 組合管理分頁確認上面那幾檔的代號與張數")\n'
                                '\n'),
                               ('       for _k in _V2_NOT_BOUND_KEYS]\n'
                                '    # PR #927 QA-2 第 4 點：「兩本不同」同樣出現在這一批卡(同一個 `_not_bound_note()`)。\n'
                                '    + [_v2_rows_for(_k, DIVERGED_NOW, _V2_SHARED_SHORT[DIVERGED_NOW])\n'
                                '       for _k in _V2_NOT_BOUND_KEYS]\n'
                                '    + [_v2_rows_for(_k, EMPTY_SHEET_NOW, '
                                '_V2_SHARED_SHORT[EMPTY_SHEET_NOW])\n'
                                '       for _k in _V2_EMPTY_SHEET_KEYS]\n'
                                '    # 👤 我的 P1（Q7）：「綁了但沒選定／選定的名稱不在了」出現在與「綁了但空」**同一批卡**（同一個分支點）。\n'
                                '    + [_v2_rows_for(_k, _now, _V2_SHARED_SHORT[_now])\n'
                                '       for _now in (NOT_SELECTED_NOW, SELECTION_MISSING_NOW) for _k in '
                                '_V2_EMPTY_SHEET_KEYS]\n'
                                '    + [_v2_rows_for(_k, NO_ROWS_NOW, _V2_SHARED_SHORT[NO_ROWS_NOW])\n',
                                '       for _k in _V2_NOT_BOUND_KEYS]\n'
                                '    + [_v2_rows_for(_k, EMPTY_SHEET_NOW, '
                                '_V2_SHARED_SHORT[EMPTY_SHEET_NOW])\n'
                                '       for _k in _V2_EMPTY_SHEET_KEYS]\n'
                                '    + [_v2_rows_for(_k, NO_ROWS_NOW, _V2_SHARED_SHORT[NO_ROWS_NOW])\n'),
                               ('           None, "可能是還沒漲到門檻，也可能是那幾檔沒有均價因此判不了",\n'
                                '           "若你預期應該要有：確認那幾檔個股的均價有填" + V2_EXCERPT_GAP + _V2_OLD_UI)),\n'
                                '       _v2_rows_for("hold.position_cap", CAP_FAILED_NOW, (\n',
                                '           None, "可能是還沒漲到門檻，也可能是那幾檔沒有均價因此判不了",\n'
                                '           "若你預期應該要有：到 📁 組合管理確認那幾檔個股的均價有填")),\n'
                                '       _v2_rows_for("hold.position_cap", CAP_FAILED_NOW, (\n'),
                               ('           "若是新上市／剛買進的標的，等歷史累積" + V2_EXCERPT_GAP\n'
                                '           + IF_LOTS_AVG_MISSING_TASK + "：" + _V2_OLD_UI)),\n'
                                '       # 批 Z48：歷史收盤價異常（why 摘開頭與結尾；代號清單在 fact 列與「▸ 詳細」摺疊區）。\n',
                                '           "若是新上市／剛買進的標的，等歷史累積" + V2_EXCERPT_GAP\n'
                                '           + IF_LOTS_AVG_MISSING_WHERE)),\n'
                                '       # 批 Z48：歷史收盤價異常（why 摘開頭與結尾；代號清單在 fact 列與「▸ 詳細」摺疊區）。\n'),
                               ('       _v2_rows_for("hold.deep.dividend_cash", CASH_NO_HOLDINGS_NOW, (\n'
                                '           # 👤 我的 P1：where 改為客戶原句 ＋ 後半（64 字）⇒ 卡面改摘錄（⛔ 不縮寫原文；全文在「▸ 詳細」）。\n'
                                '           # PR #927 QA-2 第 6 點：原文改「動作在前」⇒ 摘錄順序跟著換（~~舊版 → 新增~~）。\n'
                                '           None, "這是一個有效的結果（已經算過，不是還沒算）",\n'
                                '           "在你的持股表新增至少一列持股" + V2_EXCERPT_GAP + _V2_OLD_UI)),\n'
                                '       _v2_rows_for("hold.deep.dividend_cash", CASH_EMPTY_NOW, (\n'
                                '           None, "這是一個有效的結果（已經算過，不是還沒算）",\n'
                                '           "把持股的張數補齊" + V2_EXCERPT_GAP + _V2_OLD_UI + V2_EXCERPT_GAP + '
                                '"回本頁" + _V2_PRESS_RUN))]\n'
                                '    + [_v2_rows_for(_k, DEGRADED_NOW_TEMPLATE.format(label=_label), (\n',
                                '       _v2_rows_for("hold.deep.dividend_cash", CASH_NO_HOLDINGS_NOW, (\n'
                                '           None, "這是一個有效的結果（已經算過，不是還沒算）", CASH_WATCHLIST_ONLY_WHERE)),\n'
                                '       _v2_rows_for("hold.deep.dividend_cash", CASH_EMPTY_NOW, (\n'
                                '           None, "這是一個有效的結果（已經算過，不是還沒算）",\n'
                                '           "到既有的 📁 組合管理分頁把持股的張數補齊，回本頁" + _V2_PRESS_RUN))]\n'
                                '    + [_v2_rows_for(_k, DEGRADED_NOW_TEMPLATE.format(label=_label), (\n'),
                               ('           None, _v2_raised(SRC_BINDING), _V2_CHECK_NET)),\n'
                                '       # PR #927 QA-2 第 4 點：兩本不同 ⇒ 同一個 now、不同的 where ⇒ '
                                '第二個候選（~~單一候選~~，有意識的修改）。\n'
                                '       _v2_rows_for("hold.portfolio_count", COUNT_NOT_BOUND_NOW, (\n'
                                '           None, "這不是失敗，是這個問題還沒有成立",\n'
                                '           ("先完成上一張卡說的綁定，這一格會自己有東西", COUNT_DIVERGED_WHERE))),\n'
                                '       _v2_rows_for("hold.portfolio_count", COUNT_DRIFT_NOW, (\n',
                                '           None, _v2_raised(SRC_BINDING), _V2_CHECK_NET)),\n'
                                '       _v2_rows_for("hold.portfolio_count", COUNT_NOT_BOUND_NOW, (\n'
                                '           None, "這不是失敗，是這個問題還沒有成立", "先完成上一張卡說的綁定，這一格會自己有東西")),\n'
                                '       _v2_rows_for("hold.portfolio_count", COUNT_DRIFT_NOW, (\n'),
                               ('           None, "空的組合就是空的，本站不把它畫成紅色錯誤",\n'
                                '           "新增一本組合並填入持股列" + V2_EXCERPT_GAP + _V2_OLD_UI + V2_EXCERPT_GAP\n'
                                '           + "填完回本頁" + _V2_PRESS_RUN)),\n',
                                '           None, "空的組合就是空的，本站不把它畫成紅色錯誤",\n'
                                '           "到既有的 📁 組合管理分頁新增一本組合並填入持股列" + V2_EXCERPT_GAP\n'
                                '           + "填完回本頁" + _V2_PRESS_RUN)),\n'),
                               ('           "「portfolios」分頁，把第一列從 A 欄起依序改成" + V2_EXCERPT_GAP + "改好後回本頁"))]\n'
                                '    # 👤 我的 P1（D 段）：~~兩張共用 why「這一項本質上是寫入…」＋ '
                                'where「{NO_EXIT_MARKER}…現行入口仍在既有的\n'
                                '    #   📁 組合管理分頁」~~ → 選 Sheet 那張改指「👤 我的」；觀察清單管理那張的 where 改為客戶原句。\n'
                                '    + [_v2_rows_for("hold.setup.pick_sheet", PICK_SHEET_UNWIRED_NOW, (\n'
                                '           None, "選哪一本 Sheet、分析哪一本組合是全站共用的選擇",\n'
                                '           "到" + ME_SHEET_WHERE + "選一本 Sheet")),\n'
                                '       _v2_rows_for("hold.setup.watchlist", WATCHLIST_UNWIRED_NOW, (\n'
                                '           None, "這一項本質上是寫入" + V2_EXCERPT_GAP + "本頁對你的持股帳本一律唯讀",\n'
                                '           _V2_OLD_UI))]\n'
                                ')\n',
                                '           "「portfolios」分頁，把第一列從 A 欄起依序改成" + V2_EXCERPT_GAP + "改好後回本頁"))]\n'
                                '    + [_v2_rows_for(_k, _now, (\n'
                                '           None, "這一項本質上是寫入" + V2_EXCERPT_GAP + "本頁對你的持股帳本一律唯讀",\n'
                                '           NO_EXIT_MARKER + V2_EXCERPT_GAP + "現行入口仍在既有的 📁 組合管理分頁"))\n'
                                '       for _k, _now in (("hold.setup.pick_sheet", PICK_SHEET_UNWIRED_NOW),\n'
                                '                        ("hold.setup.watchlist", WATCHLIST_UNWIRED_NOW))]\n'
                                ')\n'),
                               ('                   "需要寫入才做得到的部分會標「未接線」並說明原因。")\n'
                                '    st.caption(SETUP_ME_POINTER)   # 👤 我的 P1（D 段）：選 Sheet / 選組合的入口在「👤 我的」\n'
                                '    _submitted = _render_holdings_form()\n',
                                '                   "需要寫入才做得到的部分會標「未接線」並說明原因。")\n'
                                '    _submitted = _render_holdings_form()\n'),
                               ('        return\n'
                                '    # 👤 我的 P1（D 段）：~~「**唯讀** —— 要新增／修改／刪除請到既有的 📁 組合管理分頁。」~~\n'
                                '    st.caption("**唯讀** —— " + _edit_where("要新增／修改／刪除持股")\n'
                                '               + f"要換 Sheet、選組合：到{ia_nav.where_to_find(ia_nav.PAGE_ME)}。")\n'
                                '    st.dataframe(\n',
                                '        return\n'
                                '    st.caption("**唯讀** —— 要新增／修改／刪除請到既有的 📁 組合管理分頁。")\n'
                                '    st.dataframe(\n')),
 'src/ui/views/page_today.py': (('from shared.secret_scrub import scrub_secrets\n'
                                 'from shared.sheet_id import ACTIVE_DIVERGED\n'
                                 'from shared.ui_state import (\n',
                                 'from shared.secret_scrub import scrub_secrets\n'
                                 'from shared.ui_state import (\n'),
                                ('SHEET_UNBOUND_WHY: str = "**這是一個有效的結果**（已經去讀過，不是還沒讀、也不是故障）"\n'
                                 '#: 📌 👤 我的 P1（DEC-083 D 段「Sheet／登入／切換相關提示 → 統一導向『👤 我的』」；有意識的改指，⛔ 不是漏刪）：\n'
                                 '#:    ~~「用 Google 登入後選一本持股 Sheet —— **現行入口在側欄「🔐 Google 帳號」的「Google Sheet '
                                 'ID 或完整 URL\n'
                                 '#:    （系統會自動解析 ID）」**」~~（側欄那一格照留、仍可用；新版的唯一設定入口改為「👤 我的」）。\n'
                                 '#:    分區名 / 按鈕名一律走 `ia_nav`（⛔ 不手抄）。\n'
                                 'SHEET_UNBOUND_WHERE: str = (\n'
                                 '    "用 Google 登入後選一本持股 Sheet —— **到"\n'
                                 '    + ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET) + "選一本，"\n'
                                 '    + ia_nav.where_to_press(ia_nav.ACTION_ME_USE_SHEET) + "**")\n'
                                 '#: PR #927 QA-2 第 4 點：組合 / 觀察清單兩條通道各記一本、不是同一本（`ACTIVE_DIVERGED`）⇒ 新版不替你挑。\n'
                                 '#:    ~~這種情形原本落進「尚未綁定 Sheet／這是一個有效的結果」~~ —— 對已經綁過兩本的人是錯的說法\n'
                                 '#:    （有意識的修改，⛔ 不是漏改）。分區名走 `ia_nav`（⛔ 不手抄）。\n'
                                 'SHEET_DIVERGED_NOW: str = "組合和觀察清單讀的是兩本不同的 Sheet"\n'
                                 'SHEET_DIVERGED_WHY: str = "**這不是故障**：兩邊各記著一本 Sheet，新版不替你挑一本，所以先不讀"\n'
                                 'SHEET_DIVERGED_WHERE: str = (\n'
                                 '    "你的組合和觀察清單目前讀的是兩本不同的 Sheet，請到"\n'
                                 '    + ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET) + "選定一本")\n'
                                 'SHEET_FAILED_NOW: str = "**綁定狀態讀不出來**"\n',
                                 'SHEET_UNBOUND_WHY: str = "**這是一個有效的結果**（已經去讀過，不是還沒讀、也不是故障）"\n'
                                 'SHEET_UNBOUND_WHERE: str = "用 Google 登入後選一本持股 Sheet —— **現行入口在側欄「🔐 Google '
                                 '帳號」的「Google Sheet ID 或完整 URL（系統會自動解析 ID）」**"\n'
                                 'SHEET_FAILED_NOW: str = "**綁定狀態讀不出來**"\n'),
                                ('                     where=SHEET_FAILED_WHERE)\n'
                                 '    elif str(getattr(binding, "active_state", "") or "") == '
                                 'ACTIVE_DIVERGED:   # PR #927 QA-2 第 4 點\n'
                                 '        _note = Note(now=SHEET_DIVERGED_NOW, why=SHEET_DIVERGED_WHY, '
                                 'where=SHEET_DIVERGED_WHERE)\n'
                                 '    else:   # UI_EMPTY —— 還沒綁。有效結果。\n',
                                 '                     where=SHEET_FAILED_WHERE)\n'
                                 '    else:   # UI_EMPTY —— 還沒綁。有效結果。\n'),
                                ('    # 批 Z54：狀態列「Sheet 綁定」接線後的兩句指路（皆為頁4 既有原文，短語＝原文的一段）。\n'
                                 '    # 👤 我的 P1：~~"現行入口在側欄「🔐 Google 帳號」"~~ → 改指「👤 我的」（原文的一段，ia_nav 組字）。\n'
                                 '    (SHEET_UNBOUND_WHERE,         "到" + '
                                 'ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET) + "選一本"),\n'
                                 '    (SHEET_FAILED_WHERE,          SHEET_FAILED_WHERE),\n'
                                 '    # PR #927 QA-2 第 4 點：兩本不同（原文的一段，ia_nav 組字）。\n'
                                 '    (SHEET_DIVERGED_WHERE,        "到" + '
                                 'ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET) + "選定一本"),\n'
                                 '    # 批 Z59：狀態列「交易日」接線後的紅態指路（實作組內部擬稿）。\n',
                                 '    # 批 Z54：狀態列「Sheet 綁定」接線後的兩句指路（皆為頁4 既有原文，短語＝原文的一段）。\n'
                                 '    (SHEET_UNBOUND_WHERE,         "現行入口在側欄「🔐 Google 帳號」"),\n'
                                 '    (SHEET_FAILED_WHERE,          SHEET_FAILED_WHERE),\n'
                                 '    # 批 Z59：狀態列「交易日」接線後的紅態指路（實作組內部擬稿）。\n'))}
# <<< ME_P1_REVERT_PAIRS


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def me_p1_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 👤 我的 P1 之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = ME_P1_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} 👤 我的 P1 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_me_p1_revert_is_exact_base_source():
    # 📌 D2 導覽殼（DEC-090，2026-10-26；有意識的接鏈，⛔ 不是漏改）：鏈頭已往前接一節 `d2_revert_for`，本節先收 D2 的改動。
    from tests.test_d2_shell_revert_chain import d2_revert_for
    for rel in sorted(ME_P1_REVERT_PAIRS):
        code = me_p1_revert_for(rel, d2_revert_for(rel, (REPO / rel).read_text(encoding="utf-8")))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == ME_P1_BASE_SHA[rel], rel


def test_me_p1_revert_is_idempotent():
    from tests.test_d2_shell_revert_chain import d2_revert_for   # D2 接鏈，同上
    for rel in sorted(ME_P1_REVERT_PAIRS):
        once = me_p1_revert_for(rel, d2_revert_for(rel, (REPO / rel).read_text(encoding="utf-8")))
        assert me_p1_revert_for(rel, once) == once, rel


def test_chain_head_calls_me_p1_first():
    """原鏈頭 `sheet_safety_revert_for` 必須先呼叫本節（否則舊批次的基底 sha 守衛看到的是本批的新寫法）。"""
    import inspect

    from tests.test_sheet_safety_revert_chain import sheet_safety_revert_for
    src = inspect.getsource(sheet_safety_revert_for)
    assert src.index("me_p1_revert_for(rel, code)") < src.index("SHEET_SAFETY_REVERT_PAIRS.get(rel")
