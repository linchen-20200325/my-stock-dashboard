"""Google Sheet 持股組合雲端儲存 (PR #5 + OAuth 擴充)

⚠️ §8.2.A EX-OAUTH-1(v19.159 團隊稽核擴充):本檔 L1 讀 `st.session_state`
(gsheet_tokens / portfolio_sheet_id,見下方 ready 檢查)屬 OAuth session lifecycle
(token 取用),非業務 UI。例外正式登錄於 CLAUDE.md §8.2.A EX-OAUTH-1。

Schema
======
- worksheet `portfolios`(ETF / legacy 持股組合)：
    name | ticker | lots | avg_price | updated_at
- worksheet `forward_test_picks`(前進式驗證選股凍結,見 _FT_HEADERS)
- worksheet `stock_watchlist`(個股**純代碼**觀察清單,Option B)：
    name | ticker | updated_at
  ⚠️ §1 反捏造:純代碼清單**不**寫張數/均價/任何價格,與 `portfolios` schema
  物理隔離(獨立分頁),避免哨兵假價污染。

多組命名 = 多列共用同一 worksheet；同一個 name 多列 = 該組合的所有持股 / 代碼。

雙模式認證
==========
- OAuth（推薦）：使用者在 sidebar 用 Google 登入，自帶 Sheet
  - secrets：`[google_oauth]` 或 in-app wizard 設定（client_id/secret/redirect_uri）
  - 個人 Sheet ID：UI 輸入 → session_state['portfolio_sheet_id']
- Service Account（向後相容）：管理員部署
  - secrets：`portfolio_sheet_id` + `[gcp_service_account]`

依賴
====
- gspread>=6.0
- google-auth>=2.0

呼叫端
======
- src/ui/tabs/portfolio_manager.py（📁 組合管理頁）— ETF 組合 + 個股清單的唯一管理入口

設計
====
- 純函式 API：is_configured / list_portfolios / load_portfolio / save_portfolio / delete_portfolio
- 例外不吞，往上拋給 caller（UI 層用 try/except 顯示 st.error）
- OAuth client 由 src.data.portfolio.oauth_state._get_oauth_client() 提供
  (v18.400 D4:原 oauth_state 誤放 src/ui/pages/,已歸位 src/data/portfolio/ 同層)
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

try:
    import streamlit as st
except ImportError:
    st = None

_WORKSHEET_NAME = 'portfolios'
_HEADERS = ['name', 'ticker', 'lots', 'avg_price', 'updated_at']

# ── Option B:個股**純代碼**觀察清單(§3.3 worksheet 名稱 + headers 具名常數)──────
# §1 反捏造:此分頁**只**存 name/ticker/updated_at 三欄,無張數/均價/哨兵/任何價格;
# 與 `portfolios`(5 欄含價格)物理隔離(獨立 worksheet),互不污染。
_STOCK_WATCHLIST_WORKSHEET = 'stock_watchlist'
_STOCK_WATCHLIST_HEADERS = ['name', 'ticker', 'updated_at']

# §3.3 SSOT:個股 新建 Sheet 的專屬 Drive 資料夾名稱(與 ETF 建的 Sheet 物理分隔)。
_STOCK_DRIVE_FOLDER_NAME = '台股 Dashboard（個股組合）'

# ── §3.3 session-key SSOT:個股 / ETF 雲端儲存分家(Phase 1)──────────────
# 兩條 session channel,各自獨立指向不同 Google Sheet,互不污染:
#   PORTFOLIO_SHEET_KEY       — ETF 組合 + legacy(含 SA secrets fallback);
#                               forward-test 亦沿用此 legacy 通道(_get_active_sheet_id)。
#   STOCK_PORTFOLIO_SHEET_KEY — 個股組合專用(session-only,無 secrets fallback)。
PORTFOLIO_SHEET_KEY = 'portfolio_sheet_id'
STOCK_PORTFOLIO_SHEET_KEY = 'stock_portfolio_sheet_id'


def _oauth_active() -> bool:
    """OAuth 模式:已設 OAuth Client + 已登入 + 有 sheet id。"""
    if st is None:
        return False
    try:
        from src.data.portfolio.oauth_state import is_oauth_configured
    except Exception:
        return False
    if not is_oauth_configured():
        return False
    if not st.session_state.get('gsheet_tokens'):
        return False
    if not _get_active_sheet_id():
        return False
    return True


def _sa_configured() -> bool:
    """Service Account 模式：兩個 secrets 都有。"""
    if st is None:
        return False
    try:
        _ = st.secrets[PORTFOLIO_SHEET_KEY]
        _ = st.secrets['gcp_service_account']
        return True
    except (KeyError, FileNotFoundError, AttributeError):
        return False


def is_configured() -> bool:
    """OAuth 已登入＋有 Sheet ID，或 SA 已備齊；任一條件即可。"""
    return _oauth_active() or _sa_configured()


def _get_active_sheet_id() -> str:
    """OAuth 模式下取使用者輸入的 sheet id；SA 模式回 secrets 的值。

    ⚠️ 這是 **ETF / legacy** 通道(PORTFOLIO_SHEET_KEY + secrets fallback);
    forward-test(_ft_worksheet)亦沿用。個股組合請改用 `_get_active_stock_sheet_id()`。
    """
    if st is None:
        return ''
    sid = str(st.session_state.get(PORTFOLIO_SHEET_KEY, '') or '').strip()
    if sid:
        return sid
    try:
        return str(st.secrets.get(PORTFOLIO_SHEET_KEY, '') or '').strip()
    except (KeyError, FileNotFoundError, AttributeError):
        return ''


def _get_active_stock_sheet_id() -> str:
    """個股組合專用 sheet id — 只讀 session channel `STOCK_PORTFOLIO_SHEET_KEY`。

    與 ETF/legacy 分家(Phase 1):**不** fallback 到 secrets(SA/secrets 仍屬
    ETF-legacy 專用),也**不**讀 `PORTFOLIO_SHEET_KEY`。未設定 → 回空字串
    (由 caller 依 §1 fail-loud 處理,不靜默借用 ETF sheet)。
    """
    if st is None:
        return ''
    return str(st.session_state.get(STOCK_PORTFOLIO_SHEET_KEY, '') or '').strip()


def _has_oauth_tokens() -> bool:
    """是否已透過 OAuth 登入（不要求 Sheet ID 已設定）。

    `_oauth_active()` 額外要求 sheet_id，會擋掉「列檔挑 Sheet」的場景；
    建構 client 只需要看「有沒有登入 + OAuth Client 有設」。

    用 `is_oauth_configured()` 動態解析（取代 stale module-level `_oauth_configured`）—
    in-app wizard 套用 OAuth config 後不必重啟 streamlit 也能立刻生效。
    """
    if st is None:
        return False
    try:
        from src.data.portfolio.oauth_state import is_oauth_configured
    except Exception:
        return False
    if not is_oauth_configured():
        return False
    if not st.session_state.get('gsheet_tokens'):
        return False
    return True


def _build_client():
    """依當前模式建一個 gspread client。OAuth 優先；fallback SA。

    OAuth 判斷只看「有 token + 有 OAuth Client」，不綁 sheet_id —
    讓「列檔挑 Sheet」流程能在 sheet_id 還沒設定前先建 client。
    """
    if _has_oauth_tokens():
        from src.data.portfolio.oauth_state import _get_oauth_client
        cli = _get_oauth_client()
        if cli is not None:
            return cli
    # Fallback: Service Account（OAuth 沒登入或建 client 失敗才走這條）
    if not _sa_configured():
        raise RuntimeError(
            '尚未登入 Google 也未設定 Service Account — 請先「🔐 用 Google 登入」'
            '或請管理員設定 `[gcp_service_account]` secret')
    import gspread
    from google.oauth2.service_account import Credentials
    sa_info = dict(st.secrets['gcp_service_account'])
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    return gspread.authorize(creds)


def _col_letter(n_cols: int) -> str:
    """1-based 欄數 → A1 欄字母(headers ≤ 26 欄,單字母 A..Z)。

    e.g. 3 欄 → 'C'、5 欄 → 'E'。用於動態算 header 更新範圍,取代死寫 'A1:E1'。
    """
    if not 1 <= n_cols <= 26:
        raise ValueError(f'_col_letter 僅支援 1..26 欄,收到 {n_cols}')
    return chr(ord('A') + n_cols - 1)


def _get_worksheet(*, sheet_id: str | None = None,
                   worksheet_name: str = _WORKSHEET_NAME,
                   headers: list[str] = _HEADERS):
    """取得 (或建立) `worksheet_name` 這個 worksheet，並確保 header 列存在。

    sheet_id=None(或空)→ 走 legacy `_get_active_sheet_id()`(ETF / SA / forward-test
    行為 byte-for-byte 不變);非空 sheet_id → 開 **那本** sheet(個股組合分家用)。

    worksheet_name / headers 預設為 `portfolios` 分頁(既有 caller 無感);個股純代碼
    清單傳 `stock_watchlist` + 3 欄 header。header 更新範圍依 `len(headers)` **動態**
    計算(3 欄 → A1:C1、5 欄 → A1:E1),修原本死寫 'A1:E1' 在 3 欄分頁會誤蓋 D/E 欄的 bug。
    """
    import gspread

    _sid = sheet_id or _get_active_sheet_id()
    if not _sid:
        raise RuntimeError('尚未設定 Sheet ID（OAuth 模式請在雲端儲存區塊輸入）')
    client = _build_client()
    sh = client.open_by_key(_sid)

    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=200, cols=10)
        ws.append_row(headers)
        return ws

    first_row = ws.row_values(1)
    if first_row != headers:
        ws.update(f'A1:{_col_letter(len(headers))}1', [headers])
    return ws


def _ws(*, sheet_id: str | None = None,
        worksheet_name: str = _WORKSHEET_NAME,
        headers: list[str] = _HEADERS):
    """取得 worksheet handle。每次重新建立（OAuth token 可能 refresh）。

    sheet_id / worksheet_name / headers 透傳給 `_get_worksheet`
    (預設 portfolios 分頁 → 既有 caller 無感)。
    """
    return _get_worksheet(sheet_id=sheet_id, worksheet_name=worksheet_name,
                          headers=headers)


def _all_records(*, sheet_id: str | None = None,
                 worksheet_name: str = _WORKSHEET_NAME,
                 headers: list[str] = _HEADERS) -> list[dict[str, Any]]:
    """回傳全表（含 header 後的所有列）為 dict list（預設 portfolios 分頁）。"""
    return _ws(sheet_id=sheet_id, worksheet_name=worksheet_name,
               headers=headers).get_all_records()


def list_portfolios(*, sheet_id: str | None = None) -> list[str]:
    """列出所有不重複的組合名稱（按字母排序）。

    sheet_id=None → legacy active sheet(ETF);非空 → 指定 sheet(個股組合)。
    """
    names: set[str] = set()
    for rec in _all_records(sheet_id=sheet_id):
        n = str(rec.get('name', '')).strip()
        if n:
            names.add(n)
    return sorted(names)


def load_portfolio(name: str, *, sheet_id: str | None = None) -> list[dict[str, Any]]:
    """讀取指定名稱的組合，回傳 `[{ticker, lots, avg_price}, ...]`。

    sheet_id=None → legacy active sheet(ETF);非空 → 指定 sheet(個股組合)。
    """
    name = (name or '').strip()
    if not name:
        return []
    out: list[dict[str, Any]] = []
    for rec in _all_records(sheet_id=sheet_id):
        if str(rec.get('name', '')).strip() != name:
            continue
        tk = str(rec.get('ticker', '')).strip()
        if not tk:
            continue
        try:
            lots = float(rec.get('lots') or 0)
            avg = float(rec.get('avg_price') or 0)
        except (TypeError, ValueError):
            continue
        if lots <= 0 or avg <= 0:
            continue
        out.append({'ticker': tk, 'lots': lots, 'avg_price': avg})
    return out


def save_portfolio(name: str, rows: list[dict[str, Any]], *,
                   sheet_id: str | None = None) -> int:
    """儲存（覆蓋）指定名稱的組合，回傳寫入的列數。

    rows 預期格式：每筆含 `ticker` / `lots` / `avg_price`。其它欄位忽略。
    sheet_id=None → legacy active sheet(ETF);非空 → 指定 sheet(個股組合)。
    """
    name = (name or '').strip()
    if not name:
        raise ValueError('組合名稱不可為空')
    if not rows:
        raise ValueError('組合內容不可為空')

    ws = _ws(sheet_id=sheet_id)
    existing = ws.get_all_values()
    keep_rows = [r for r in existing[1:] if (r and r[0].strip() != name)]

    ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_rows = []
    for r in rows:
        tk = str(r.get('ticker', '')).strip().upper()
        if not tk:
            continue
        try:
            lots = float(r.get('lots') or 0)
            avg = float(r.get('avg_price') or 0)
        except (TypeError, ValueError):
            continue
        if lots <= 0 or avg <= 0:
            continue
        new_rows.append([name, tk, lots, avg, ts])

    if not new_rows:
        raise ValueError('無有效持股可儲存（檢查代號、張數、均價）')

    ws.clear()
    ws.append_row(_HEADERS)
    if keep_rows:
        ws.append_rows(keep_rows)
    ws.append_rows(new_rows)
    return len(new_rows)


# ── Option B:個股**純代碼**觀察清單 API(獨立 `stock_watchlist` 分頁,無價格)──────
# §1 反捏造:save 只寫 [name, ticker.upper(), updated_at],**絕無**張數/均價/哨兵。
# 與 portfolios(5 欄含價格)物理隔離,pure watchlist 讀寫時不接觸任何價格欄位。
def save_stock_watchlist(name: str, tickers: list[str], *,
                         sheet_id: str | None = None) -> int:
    """儲存(覆蓋)指定名稱的**純代碼**觀察清單到 `stock_watchlist` 分頁,回寫入列數。

    §1:每列僅 `[name, ticker.upper(), updated_at]` 三欄 —— **無**張數/均價/哨兵/任何
    捏造價格。tickers 去空 + 去重(保序,大寫正規化)。同名覆蓋(保留其它 name,
    與 `save_portfolio` 的 keep_rows 同 pattern)。name/代碼皆空 → raise ValueError。
    sheet_id=None → legacy active sheet;非空 → 指定 sheet(個股組合分家用)。
    """
    name = (name or '').strip()
    if not name:
        raise ValueError('組合名稱不可為空')
    if not tickers:
        raise ValueError('代碼清單不可為空')

    clean: list[str] = []
    seen: set[str] = set()
    for _t in tickers:
        tk = str(_t or '').strip().upper()
        if tk and tk not in seen:
            seen.add(tk)
            clean.append(tk)
    if not clean:
        raise ValueError('無有效代碼可儲存')

    ws = _ws(sheet_id=sheet_id, worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
             headers=_STOCK_WATCHLIST_HEADERS)
    existing = ws.get_all_values()
    keep_rows = [r for r in existing[1:] if (r and r[0].strip() != name)]

    ts = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_rows = [[name, tk, ts] for tk in clean]  # ← 無價格欄,§1 反捏造

    ws.clear()
    ws.append_row(_STOCK_WATCHLIST_HEADERS)
    if keep_rows:
        ws.append_rows(keep_rows)
    ws.append_rows(new_rows)
    return len(new_rows)


def list_stock_watchlists(*, sheet_id: str | None = None) -> list[str]:
    """列出 `stock_watchlist` 分頁內所有不重複的清單名稱(字母排序)。

    sheet_id=None → legacy active sheet;非空 → 指定 sheet(個股組合)。
    """
    names: set[str] = set()
    for rec in _all_records(sheet_id=sheet_id,
                            worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
                            headers=_STOCK_WATCHLIST_HEADERS):
        n = str(rec.get('name', '')).strip()
        if n:
            names.add(n)
    return sorted(names)


def load_stock_watchlist(name: str, *, sheet_id: str | None = None) -> list[str]:
    """讀取指定名稱的**純代碼**清單(保序、去重),回傳 `list[str]`,**無**價格欄位。

    sheet_id=None → legacy active sheet;非空 → 指定 sheet(個股組合)。
    """
    name = (name or '').strip()
    if not name:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for rec in _all_records(sheet_id=sheet_id,
                            worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
                            headers=_STOCK_WATCHLIST_HEADERS):
        if str(rec.get('name', '')).strip() != name:
            continue
        tk = str(rec.get('ticker', '')).strip()
        if tk and tk not in seen:
            seen.add(tk)
            out.append(tk)
    return out


# ── 前進式驗證:選股凍結紀錄(獨立 worksheet,不污染 portfolios)── FT-2 v19.142
_FT_WORKSHEET_NAME = 'forward_test_picks'
_FT_HEADERS = ['cohort', 'stock_id', 'name', 'entry_price', 'factors', 'frozen_at']


def _ft_worksheet():
    """取得 (或建立) `forward_test_picks` worksheet,並確保 header 列存在。"""
    import gspread

    sheet_id = _get_active_sheet_id()
    if not sheet_id:
        raise RuntimeError('尚未設定 Sheet ID(OAuth 模式請在雲端儲存區塊輸入)')
    sh = _build_client().open_by_key(sheet_id)
    try:
        ws = sh.worksheet(_FT_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=_FT_WORKSHEET_NAME, rows=1000, cols=8)
        ws.append_row(_FT_HEADERS)
        return ws
    if ws.row_values(1) != _FT_HEADERS:
        ws.update('A1:F1', [_FT_HEADERS])
    return ws


def append_forward_test_picks(rows: list[dict[str, Any]]) -> int:
    """把選股凍結列 append 到 forward_test_picks worksheet;回寫入列數。

    rows 每筆須含 _FT_HEADERS 各欄(由 L2 build_pick_snapshot_rows 產出)。空 → 0。
    """
    if not rows:
        return 0
    ws = _ft_worksheet()
    ws.append_rows([[r.get(h, '') for h in _FT_HEADERS] for r in rows])
    return len(rows)


def load_forward_test_picks() -> list[dict[str, Any]]:
    """讀回全部凍結紀錄(dict list;含 cohort/stock_id/entry_price/factors…)。

    worksheet 不存在 / 未設定 Sheet / 讀取失敗 → 回 [](不炸對帳面板;§1 由 caller 判空)。
    """
    try:
        return _ft_worksheet().get_all_records()
    except Exception as _e:  # noqa: BLE001 — gsheet 不可用不炸前進式驗證面板
        print(f'[gsheet] forward_test_picks 讀取失敗: {type(_e).__name__}: {_e}')
        return []


def list_user_sheets(folder_id: str = '') -> list[dict]:
    """OAuth 模式列出使用者 Google Drive 內 Spreadsheets。

    Args:
        folder_id: 若提供，僅列出此資料夾內的 Sheets；留空則列全部。

    需要 OAuth scope `drive.metadata.readonly`（infra/oauth.py 已內建）。
    回傳 [{'id': ..., 'name': ...}, ...] 依名稱排序；非 OAuth 模式回空 list。

    v19.x：直接走 Drive v3 API（同 list_user_folders）加 `trashed=false` 過濾，
    取代原本 gspread `list_spreadsheet_files()`（會抓出已刪除 Sheets，造成
    UI 下拉出現殭屍項目）。
    """
    if not _has_oauth_tokens():
        # 未登入 OAuth → 無法列檔（SA 沒 drive.metadata.readonly scope）
        return []
    client = _build_client()
    url = 'https://www.googleapis.com/drive/v3/files'
    q_parts = [
        'mimeType="application/vnd.google-apps.spreadsheet"',
        'trashed=false',
    ]
    if folder_id and folder_id.strip():
        q_parts.append(f'"{folder_id.strip()}" in parents')
    params = {
        'q': ' and '.join(q_parts),
        'pageSize': 1000,
        'supportsAllDrives': True,
        'includeItemsFromAllDrives': True,
        'fields': 'nextPageToken,files(id,name)',
    }
    files: list[dict] = []
    page_token: str | None = None
    try:
        while True:
            if page_token:
                params['pageToken'] = page_token
            resp = client.http_client.request('get', url, params=params)
            data = resp.json() if hasattr(resp, 'json') else resp
            for f in (data.get('files') or []):
                _id, _nm = f.get('id'), f.get('name')
                if _id and _nm:
                    files.append({'id': _id, 'name': _nm})
            page_token = data.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        raise RuntimeError(f'列出 Drive Sheets 失敗：[{type(e).__name__}] {e}') from e
    files.sort(key=lambda x: x['name'].lower())
    return files


def list_user_folders() -> list[dict]:
    """OAuth 模式列出使用者 Google Drive 內所有資料夾（含共享）。

    透過 gspread client 的 http_client 直接打 Drive v3 API；
    需要 OAuth scope `drive.metadata.readonly`。
    回傳 [{'id': ..., 'name': ...}, ...] 依名稱排序；非 OAuth 模式回空 list。
    """
    if not _has_oauth_tokens():
        return []
    client = _build_client()
    url = 'https://www.googleapis.com/drive/v3/files'
    params = {
        'q': 'mimeType="application/vnd.google-apps.folder" and trashed=false',
        'pageSize': 1000,
        'supportsAllDrives': True,
        'includeItemsFromAllDrives': True,
        'fields': 'nextPageToken,files(id,name)',
    }
    folders: list[dict] = []
    page_token: str | None = None
    try:
        while True:
            if page_token:
                params['pageToken'] = page_token
            resp = client.http_client.request('get', url, params=params)
            data = resp.json()
            for f in (data.get('files') or []):
                _id, _nm = f.get('id'), f.get('name')
                if _id and _nm:
                    folders.append({'id': _id, 'name': _nm})
            page_token = data.get('nextPageToken')
            if not page_token:
                break
    except Exception as e:
        raise RuntimeError(f'列出 Drive 資料夾失敗：[{type(e).__name__}] {e}') from e
    folders.sort(key=lambda x: x['name'].lower())
    return folders


def _get_or_create_app_folder(folder_name: str) -> str:
    """回傳(或建立)名為 `folder_name` 的 app 專屬 Drive 資料夾 id。

    在 `drive.file` scope 下,Drive v3 `files.list` **只**會列出本 app 建立的檔案 /
    資料夾 —— 故先 SEARCH 同名資料夾:命中即 reuse(避免每次新建重複資料夾),
    未命中才 CREATE 一個。整個流程只需 `drive.file`,不需 `drive.metadata.readonly`。

    §1 fail-loud:任一 Drive API 呼叫失敗 → raise RuntimeError(不回假 id、不靜默)。
    """
    if not _has_oauth_tokens():
        raise RuntimeError('建立/查詢資料夾需先「🔐 用 Google 登入」')
    client = _build_client()
    url = 'https://www.googleapis.com/drive/v3/files'
    # q 字串內單引號需以 \' 轉義,避免注入 / 破壞查詢語法
    _escaped = folder_name.replace("'", "\\'")
    # ── SEARCH:同名 app-created 資料夾(mirror list_user_folders 的 params)──
    search_params = {
        'q': ("mimeType='application/vnd.google-apps.folder' and "
              f"name='{_escaped}' and trashed=false"),
        'pageSize': 10,
        'supportsAllDrives': True,
        'includeItemsFromAllDrives': True,
        'fields': 'files(id,name)',
    }
    try:
        resp = client.http_client.request('get', url, params=search_params)
        data = resp.json() if hasattr(resp, 'json') else resp
        for f in (data.get('files') or []):
            _fid = f.get('id')
            if _fid:
                return _fid            # ← reuse 既有資料夾
        # ── CREATE:未命中才建立 ──
        resp2 = client.http_client.request(
            'post', url,
            json={'name': folder_name,
                  'mimeType': 'application/vnd.google-apps.folder'},
            params={'fields': 'id', 'supportsAllDrives': True})
        data2 = resp2.json() if hasattr(resp2, 'json') else resp2
        new_id = (data2 or {}).get('id')
        if not new_id:
            raise RuntimeError('建立資料夾後未取得 id（Drive 回傳異常）')
        return new_id
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f'資料夾建立/查詢失敗：[{type(e).__name__}] {e}') from e


def create_new_sheet(title: str = '台股 Dashboard - 投資組合', *,
                     folder_name: str | None = None) -> tuple[str, str]:
    """建立新 Google Sheet 並回傳 (sheet_id, sheet_url)。

    OAuth 模式下 `drive.file` scope 已允許 app 建立並擁有此檔，
    不需要 `drive.metadata.readonly` — 可避開「token 缺中繼權限」的卡關。

    folder_name
    -----------
    - None(預設)→ 行為與舊版 byte-for-byte 相同:Sheet 建於 Drive 根目錄
      (ETF caller 走此路,不受影響)。
    - 非空字串 → 建立後把 Sheet **搬入** 該名稱的 app 專屬資料夾
      (`_get_or_create_app_folder`),使個股 Sheet 與 ETF Sheet 在 Drive 物理分隔。
      §1 best-effort:搬移屬「錦上添花」,失敗**只記 log 不炸**,仍回傳已建立的
      (sheet_id, sheet_url) —— **Sheet 永不遺失 / 永不 orphan**。
    """
    if not _has_oauth_tokens():
        raise RuntimeError('建立新 Sheet 需先「🔐 用 Google 登入」')
    title = (title or '').strip() or '台股 Dashboard - 投資組合'
    client = _build_client()
    try:
        sh = client.create(title)
    except Exception as e:
        raise RuntimeError(f'建立 Sheet 失敗：[{type(e).__name__}] {e}') from e
    sheet_id = getattr(sh, 'id', '') or ''
    sheet_url = getattr(sh, 'url', '') or (
        f'https://docs.google.com/spreadsheets/d/{sheet_id}/edit' if sheet_id else '')
    if not sheet_id:
        raise RuntimeError('建立 Sheet 後未取得 ID（gspread 回傳異常）')

    # ── best-effort:放入專屬資料夾(失敗不影響已建立的 Sheet)──
    if isinstance(folder_name, str) and folder_name.strip():
        try:
            fid = _get_or_create_app_folder(folder_name)
            files_url = 'https://www.googleapis.com/drive/v3/files'
            # 先取現有 parents,搬移時一併 remove,避免雙 parent(dual-parented)
            resp = client.http_client.request(
                'get', f'{files_url}/{sheet_id}',
                params={'fields': 'parents', 'supportsAllDrives': True})
            gdata = resp.json() if hasattr(resp, 'json') else resp
            cur_parents = (gdata or {}).get('parents') or []
            update_params = {
                'addParents': fid,
                'fields': 'id,parents',
                'supportsAllDrives': True,
            }
            if cur_parents:
                update_params['removeParents'] = ','.join(cur_parents)
            client.http_client.request(
                'patch', f'{files_url}/{sheet_id}', params=update_params)
        except Exception as e:  # noqa: BLE001 — §1 disclosed best-effort log
            print(f'[create_new_sheet] 資料夾放置失敗，Sheet 仍建於根目錄：{e}')

    return sheet_id, sheet_url


def rename_sheet(new_title: str) -> bool:
    """重新命名目前作用中的 Sheet。需要編輯權限。"""
    new_title = (new_title or '').strip()
    if not new_title:
        raise ValueError('rename_sheet: 新名稱不可為空')
    sheet_id = _get_active_sheet_id()
    if not sheet_id:
        raise RuntimeError('rename_sheet: 尚未選定 Sheet ID')
    client = _build_client()
    try:
        sh = client.open_by_key(sheet_id)
        sh.update_title(new_title)
        return True
    except Exception as e:
        raise RuntimeError(f'重新命名失敗：[{type(e).__name__}] {e}') from e


def get_sheet_title(sheet_id: str = '') -> str:
    """取得指定 Sheet 的標題；sheet_id 為空時用目前作用中的。失敗回空字串。"""
    sheet_id = sheet_id or _get_active_sheet_id()
    if not sheet_id:
        return ''
    try:
        sh = _build_client().open_by_key(sheet_id)
        return getattr(sh, 'title', '') or ''
    except Exception:
        return ''


def delete_portfolio(name: str, *, sheet_id: str | None = None) -> int:
    """刪除指定名稱的組合（所有持股列），回傳刪除的列數。

    sheet_id=None → legacy active sheet(ETF);非空 → 指定 sheet(個股組合)。
    """
    name = (name or '').strip()
    if not name:
        return 0
    ws = _ws(sheet_id=sheet_id)
    existing = ws.get_all_values()
    if len(existing) <= 1:
        return 0
    keep_rows = [r for r in existing[1:] if (r and r[0].strip() != name)]
    deleted = (len(existing) - 1) - len(keep_rows)
    if deleted == 0:
        return 0
    ws.clear()
    ws.append_row(_HEADERS)
    if keep_rows:
        ws.append_rows(keep_rows)
    return deleted


def delete_stock_watchlist(name: str, *, sheet_id: str | None = None) -> int:
    """刪除指定名稱的**個股觀察清單**(所有代碼列),回傳刪除的列數。

    語意鏡像 delete_portfolio,但操作 `stock_watchlist` 分頁(純代碼、無價格)。
    補齊個股端原缺的刪除能力(ETF 早有 delete_portfolio,個股一直只能同名覆蓋)。
    sheet_id=None → legacy active sheet;非空 → 指定 sheet(個股組合分家用)。
    """
    name = (name or '').strip()
    if not name:
        return 0
    ws = _ws(sheet_id=sheet_id, worksheet_name=_STOCK_WATCHLIST_WORKSHEET,
             headers=_STOCK_WATCHLIST_HEADERS)
    existing = ws.get_all_values()
    if len(existing) <= 1:
        return 0
    keep_rows = [r for r in existing[1:] if (r and r[0].strip() != name)]
    deleted = (len(existing) - 1) - len(keep_rows)
    if deleted == 0:
        return 0
    ws.clear()
    ws.append_row(_STOCK_WATCHLIST_HEADERS)
    if keep_rows:
        ws.append_rows(keep_rows)
    return deleted
