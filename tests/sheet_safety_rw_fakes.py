"""Sheet Safety 批 QA 回修:可讀寫、記錄每一次呼叫的假 gspread(源自 QA2 獨立替身,原樣收錄)。非測試檔。"""
from __future__ import annotations

import gspread


class _Resp:
    def __init__(self, code, status):
        self._code, self._status = code, status
        self.text = status

    def json(self):
        return {"error": {"code": self._code, "message": self._status, "status": self._status}}


def api_error(code=403, status="PERMISSION_DENIED"):
    return gspread.exceptions.APIError(_Resp(code, status))


class FakeWS:
    def __init__(self, book, title):
        self.book, self.title = book, title

    @property
    def _v(self):
        return self.book.sheets[self.title]

    @property
    def row_count(self):
        return max(len(self._v), 1000)

    @property
    def col_count(self):
        return 26

    def get_all_values(self):
        self.book.log.append(("read", self.title, "get_all_values"))
        return [list(r) for r in self._v]

    def row_values(self, n):
        self.book.log.append(("read", self.title, "row_values"))
        return list(self._v[n - 1]) if 0 < n <= len(self._v) else []

    def get_all_records(self, numericise_ignore=None, **_k):
        from gspread.utils import numericise_all, to_records
        self.book.log.append(("read", self.title, "get_all_records"))
        if not self._v:
            return []
        keys, rows = self._v[0], self._v[1:]
        return to_records(keys, [numericise_all(list(r), ignore=numericise_ignore or []) for r in rows])

    # writes
    def update(self, values=None, range_name=None, **_k):
        self.book.log.append(("write", self.title, "update"))
        self.book.sheets[self.title] = [list(r) for r in values]
        # trim fully blank trailing rows like Sheets display
        while self.book.sheets[self.title] and not any(str(c).strip() for c in self.book.sheets[self.title][-1]):
            self.book.sheets[self.title].pop()

    def append_row(self, row, **_k):
        self.book.log.append(("write", self.title, "append_row"))
        self.book.sheets[self.title].append(list(row))

    def append_rows(self, rows, **_k):
        self.book.log.append(("write", self.title, "append_rows"))
        self.book.sheets[self.title].extend([list(r) for r in rows])

    def add_rows(self, n):
        self.book.log.append(("write", self.title, "add_rows"))

    def add_cols(self, n):
        self.book.log.append(("write", self.title, "add_cols"))

    def clear(self):
        self.book.log.append(("write", self.title, "clear"))
        self.book.sheets[self.title] = []


class FakeBook:
    def __init__(self, sid, sheets, log, deny=None):
        self.id, self.sheets, self.log, self.deny = sid, sheets, log, deny
        self.title = f"Book {sid}"

    def worksheet(self, name):
        if self.deny:
            raise self.deny
        self.log.append(("read", name, "worksheet"))
        if name not in self.sheets:
            raise gspread.WorksheetNotFound(name)
        return FakeWS(self, name)

    def add_worksheet(self, title, rows=100, cols=10):
        self.log.append(("write", title, "add_worksheet"))
        self.sheets[title] = []
        return FakeWS(self, title)

    def worksheets(self):
        return [FakeWS(self, t) for t in self.sheets]


class FakeClient:
    def __init__(self):
        self.books: dict[str, dict] = {}
        self.denied: dict[str, Exception] = {}
        self.log: list = []
        self.opened: list = []

    def open_by_key(self, sid):
        self.opened.append(sid)
        if sid in self.denied:
            raise self.denied[sid]
        if sid not in self.books:
            raise gspread.exceptions.SpreadsheetNotFound(sid)
        return FakeBook(sid, self.books[sid], self.log)

    def writes(self):
        return [e for e in self.log if e[0] == "write"]


TOKENS = {"refresh_token": "rt-QA", "access_token": "at-QA", "expires_at": 9_999_999_999}
OAUTH_CFG = {"client_id": "cid", "client_secret": "csec", "redirect_uri": "http://localhost:8501"}
