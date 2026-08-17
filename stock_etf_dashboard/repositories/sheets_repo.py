"""L1 Repository — Google Sheets 帳本與池（實體隔離三張 worksheet）。

- `stock_watchlist`（觀察池,純代碼無價）
- `stock_portfolio`（持股庫存,帶張數/均價/停損停利）
- `stock_ledgers`（交易帳本,append-only）

用 `PoolStore` 介面做依賴反轉（Clean Architecture）：正式走 `GoogleSheetsStore`,
測試/離線走 `InMemoryStore`,兩者同介面 → L2 狀態機一份程式碼兩邊跑,實體隔離。
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..core import constants as C
from ..core.circuit_breaker import require
from ..core.provenance import utc_now_iso


def _norm_ticker(t: str) -> str:
    require(bool(t and str(t).strip()), "ticker 不可為空")
    return str(t).strip().upper()


# ── 介面 ────────────────────────────────────────────────────────────────
@runtime_checkable
class PoolStore(Protocol):
    def list_watchlist(self) -> list[dict]: ...
    def get_watchlist(self, ticker: str) -> dict | None: ...
    def add_watchlist(self, rec: dict) -> None: ...
    def remove_watchlist(self, ticker: str) -> None: ...
    def list_holdings(self) -> list[dict]: ...
    def get_holding(self, ticker: str) -> dict | None: ...
    def upsert_holding(self, rec: dict) -> None: ...
    def remove_holding(self, ticker: str) -> None: ...
    def append_ledger(self, rec: dict) -> None: ...
    def list_ledgers(self) -> list[dict]: ...


# ── 記憶體後端（離線 / 測試；與 Sheets 路徑物理隔離）────────────────────
class InMemoryStore:
    """dict 後端。同介面,便於單測狀態機與離線試跑。"""

    def __init__(self) -> None:
        self._watch: dict[str, dict] = {}
        self._hold: dict[str, dict] = {}
        self._ledger: list[dict] = []

    # watchlist
    def list_watchlist(self) -> list[dict]:
        return list(self._watch.values())

    def get_watchlist(self, ticker: str) -> dict | None:
        return self._watch.get(_norm_ticker(ticker))

    def add_watchlist(self, rec: dict) -> None:
        t = _norm_ticker(rec.get("ticker", ""))
        self._watch[t] = {**rec, "ticker": t, "updated_at": utc_now_iso()}

    def remove_watchlist(self, ticker: str) -> None:
        self._watch.pop(_norm_ticker(ticker), None)

    # holdings
    def list_holdings(self) -> list[dict]:
        return list(self._hold.values())

    def get_holding(self, ticker: str) -> dict | None:
        return self._hold.get(_norm_ticker(ticker))

    def upsert_holding(self, rec: dict) -> None:
        t = _norm_ticker(rec.get("ticker", ""))
        self._hold[t] = {**rec, "ticker": t, "updated_at": utc_now_iso()}

    def remove_holding(self, ticker: str) -> None:
        self._hold.pop(_norm_ticker(ticker), None)

    # ledger
    def append_ledger(self, rec: dict) -> None:
        self._ledger.append({**rec, "ts": rec.get("ts") or utc_now_iso()})

    def list_ledgers(self) -> list[dict]:
        return list(self._ledger)


# ── Google Sheets 後端 ──────────────────────────────────────────────────
class GoogleSheetsStore:
    """gspread 後端。worksheet 不存在自動建立並寫表頭。"""

    def __init__(self, spreadsheet) -> None:
        self._ss = spreadsheet
        self._cache: dict[str, object] = {}

    @classmethod
    def from_service_account(cls, sheet_id: str, creds_dict: dict) -> "GoogleSheetsStore":
        import gspread
        from google.oauth2.service_account import Credentials

        require(bool(sheet_id), "缺 sheet_id")
        require(bool(creds_dict), "缺 service account 憑證")
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        return cls(gc.open_by_key(sheet_id))

    def _ws(self, name: str):
        if name in self._cache:
            return self._cache[name]
        import gspread

        headers = list(C.WS_HEADERS[name])
        try:
            ws = self._ss.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = self._ss.add_worksheet(title=name, rows=100, cols=len(headers))
            ws.append_row(headers)
        self._cache[name] = ws
        return ws

    def _rows(self, name: str) -> list[dict]:
        return self._ws(name).get_all_records()

    def _rewrite(self, name: str, records: list[dict]) -> None:
        headers = list(C.WS_HEADERS[name])
        ws = self._ws(name)
        ws.clear()
        matrix = [headers]
        for r in records:
            matrix.append([r.get(h, "") for h in headers])
        ws.update(matrix, value_input_option="RAW")

    # watchlist
    def list_watchlist(self) -> list[dict]:
        return self._rows(C.WS_WATCHLIST)

    def get_watchlist(self, ticker: str) -> dict | None:
        t = _norm_ticker(ticker)
        return next((r for r in self.list_watchlist()
                     if _norm_ticker(str(r.get("ticker", ""))) == t), None)

    def add_watchlist(self, rec: dict) -> None:
        t = _norm_ticker(rec.get("ticker", ""))
        recs = [r for r in self.list_watchlist()
                if _norm_ticker(str(r.get("ticker", ""))) != t]
        recs.append({**rec, "ticker": t, "updated_at": utc_now_iso()})
        self._rewrite(C.WS_WATCHLIST, recs)

    def remove_watchlist(self, ticker: str) -> None:
        t = _norm_ticker(ticker)
        recs = [r for r in self.list_watchlist()
                if _norm_ticker(str(r.get("ticker", ""))) != t]
        self._rewrite(C.WS_WATCHLIST, recs)

    # holdings
    def list_holdings(self) -> list[dict]:
        return self._rows(C.WS_PORTFOLIO)

    def get_holding(self, ticker: str) -> dict | None:
        t = _norm_ticker(ticker)
        return next((r for r in self.list_holdings()
                     if _norm_ticker(str(r.get("ticker", ""))) == t), None)

    def upsert_holding(self, rec: dict) -> None:
        t = _norm_ticker(rec.get("ticker", ""))
        recs = [r for r in self.list_holdings()
                if _norm_ticker(str(r.get("ticker", ""))) != t]
        recs.append({**rec, "ticker": t, "updated_at": utc_now_iso()})
        self._rewrite(C.WS_PORTFOLIO, recs)

    def remove_holding(self, ticker: str) -> None:
        t = _norm_ticker(ticker)
        recs = [r for r in self.list_holdings()
                if _norm_ticker(str(r.get("ticker", ""))) != t]
        self._rewrite(C.WS_PORTFOLIO, recs)

    # ledger（append-only）
    def append_ledger(self, rec: dict) -> None:
        headers = list(C.WS_HEADERS[C.WS_LEDGERS])
        row = {**rec, "ts": rec.get("ts") or utc_now_iso()}
        self._ws(C.WS_LEDGERS).append_row([row.get(h, "") for h in headers],
                                          value_input_option="RAW")

    def list_ledgers(self) -> list[dict]:
        return self._rows(C.WS_LEDGERS)
