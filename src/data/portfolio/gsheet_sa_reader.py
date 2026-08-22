"""L1 Data — headless Service-Account 讀持股 / 觀察清單（每日推播 cron 專用）。

為什麼要有這一檔（與 `gsheet_portfolio` 的分工）
================================================
`gsheet_portfolio` 走 **OAuth + streamlit session**（`st.session_state['gsheet_tokens']`,
EX-OAUTH-1）—— 那是「使用者在瀏覽器登入」的路徑,**GitHub Actions cron 沒有瀏覽器 session**,
無法用。本檔改走 **Service Account**:憑證 + sheet_id 全走 `os.environ`（GitHub Secrets）,
**無 streamlit 依賴**,純 gspread I/O,專供 headless cron 讀你的私有 Sheet。

§2.1 SSOT
=========
worksheet 名稱 + 「lots>0 & avg>0 / 純代碼」解析規則**一律 import** `gsheet_portfolio` 的
常數與純解析器（`parse_portfolio_records` / `parse_watchlist_records`),**不另立第二套**,
避免主 app（OAuth 路徑）與 cron（SA 路徑）兩邊 schema / 濾值邏輯漂移。

§8.2 L1
=======
純 I/O,無 streamlit、無業務邏輯 / 門檻。scopes 只要 `spreadsheets.readonly`（唯讀:
cron 只讀不寫你的 Sheet;§1 最小權限 + 不誤改）。

§1 Fail-Loud
============
- `GCP_SERVICE_ACCOUNT_JSON` 未設 / 非合法 JSON / 缺必要欄位 → raise（cron 紅燈,
  **不**靜默回空 = 不假裝「你沒持股」）。
- worksheet 不存在 → 該類清單視為空（非錯誤:你可能只有持股沒觀察清單,反之亦然）。
- 開表 / 讀取的網路錯誤 → 往上拋（由腳本決定紅燈,不吞）。
"""
from __future__ import annotations

import json
import os

# §2.1 SSOT:分頁名 + 純解析器一律取自 gsheet_portfolio（同層 L1→L1,非跨層違憲）。
from src.data.portfolio.gsheet_portfolio import (
    _STOCK_WATCHLIST_WORKSHEET,
    _WORKSHEET_NAME,
    parse_portfolio_records,
    parse_watchlist_records,
)

_CREDS_ENV = "GCP_SERVICE_ACCOUNT_JSON"
# 唯讀 scope:cron 只讀你的持股/觀察清單,不需要寫入或 Drive（§1 最小權限）。
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def load_sa_credentials() -> dict:
    """讀環境變數 `GCP_SERVICE_ACCOUNT_JSON`（整段 service account JSON）→ dict。

    §1:未設 / 非合法 JSON / 缺必要欄位 → raise ValueError（cron 紅燈,不靜默）。
    """
    _raw = os.environ.get(_CREDS_ENV, "").strip()
    if not _raw:
        raise ValueError(
            f"{_CREDS_ENV} 未設定 —— 請於 GitHub repo Settings → Secrets 貼整段 "
            "service account JSON,並把你的 Google Sheet 分享給該 SA 的 client_email。")
    try:
        _info = json.loads(_raw)
    except (ValueError, TypeError) as _e:
        raise ValueError(f"{_CREDS_ENV} 不是合法 JSON: {type(_e).__name__}: {_e}") from _e
    if (not isinstance(_info, dict) or not _info.get("client_email")
            or not _info.get("private_key")):
        raise ValueError(
            f"{_CREDS_ENV} 缺 service account 必要欄位（client_email / private_key）")
    return _info


def _build_client(creds_dict: dict):
    """SA 憑證 dict → gspread client（唯讀 scope）。§1 憑證缺 → raise。"""
    if not creds_dict:
        raise ValueError("缺 service account 憑證")
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(creds_dict, scopes=_SCOPES)
    return gspread.authorize(creds)


def _worksheet_records(client, sheet_id: str, worksheet_name: str) -> list[dict]:
    """開 sheet_id → 取 worksheet_name 全表 records。分頁不存在 → [](非錯誤)。"""
    import gspread

    sh = client.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        return []
    return ws.get_all_records()


def read_holdings(sheet_id: str, creds_dict: dict) -> list[dict]:
    """讀某 Sheet 的 `portfolios` 分頁全部持股 → `[{ticker, lots, avg_price}, ...]`。

    跨所有命名組合聯集,並**以 ticker 去重（保留首見）**—— 同一代號出現在多個命名組合時
    避免推播出現重複列（不同組合不同均價的加權合併屬 v2,現版取首見並記 log,§1 不臆造合併值）。
    sheet_id 為空 → 回 []（該通道未設定,由 caller 依 §1 決定是否整體 fail-loud）。
    """
    if not sheet_id:
        return []
    client = _build_client(creds_dict)
    _parsed = parse_portfolio_records(_worksheet_records(client, sheet_id, _WORKSHEET_NAME))
    _out: list[dict] = []
    _seen: set[str] = set()
    _dups = 0
    for _h in _parsed:
        _tk = str(_h.get("ticker", "")).strip().upper()
        if _tk in _seen:
            _dups += 1
            continue
        _seen.add(_tk)
        _out.append(_h)
    if _dups:
        print(f"[gsheet_sa_reader] {sheet_id[:12]}… 持股去重:略過 {_dups} 筆重複代號（保留首見）")
    return _out


def read_watchlist(sheet_id: str, creds_dict: dict) -> list[str]:
    """讀某 Sheet 的 `stock_watchlist` 分頁 → 純代碼 `list[str]`（保序去重,無價格）。

    sheet_id 為空 → 回 []。§1 反捏造:只取代碼,不觸碰任何價格欄。
    """
    if not sheet_id:
        return []
    client = _build_client(creds_dict)
    return parse_watchlist_records(
        _worksheet_records(client, sheet_id, _STOCK_WATCHLIST_WORKSHEET))
