"""Sheet Safety 批（DEC-083）共用測試替身：任何寫入方法一被呼叫就**記錄並拋錯**的假 gspread 物件。

不是測試檔（檔名不以 `test_` 開頭 ⇒ pytest 不收集）；給 B1／B2／守衛測試 import。
⛔ 不打真 Google：`TripwireClient.open_by_key` 只回本檔的假 Spreadsheet。
"""
from __future__ import annotations

#: gspread Worksheet / Spreadsheet 上會改動 Sheet 的方法（DEC-083 指派清單；全部一律攔）。
WRITE_METHODS: tuple[str, ...] = (
    'add_worksheet', 'del_worksheet', 'append_row', 'append_rows', 'update',
    'update_cell', 'update_cells', 'batch_update', 'clear', 'add_rows', 'add_cols',
    'insert_row', 'insert_rows', 'delete_rows', 'resize', 'update_title',
)


class WriteAttempted(AssertionError):
    """讀取路徑呼叫了寫入方法。"""


class _Tripwire:
    def __init__(self, writes: list):
        self.writes = writes

    def __getattr__(self, name):
        if name in WRITE_METHODS:
            def _blocked(*_a, **_k):
                self.writes.append((type(self).__name__, name))
                raise WriteAttempted(f'讀取路徑不得呼叫 {type(self).__name__}.{name}')
            return _blocked
        raise AttributeError(name)


class TripwireWorksheet(_Tripwire):
    """唯讀假 Worksheet：`get_all_values` / `row_values` / `get_all_records` 照真 gspread 語意。"""

    def __init__(self, values, writes: list, title: str = ''):
        super().__init__(writes)
        self._values = [list(r) for r in (values or [])]
        self.title = title
        self.row_count = max(len(self._values), 1000)
        self.col_count = 26

    def get_all_values(self):
        return [list(r) for r in self._values]

    def row_values(self, n):
        return list(self._values[n - 1]) if 0 < n <= len(self._values) else []

    def get_all_records(self, numericise_ignore=None, **_kw):
        from gspread.utils import numericise_all, to_records
        if not self._values:
            return []
        keys, rows = self._values[0], self._values[1:]
        return to_records(keys, [numericise_all(list(r), ignore=numericise_ignore or [])
                                 for r in rows])


class TripwireSpreadsheet(_Tripwire):
    def __init__(self, worksheets: dict, writes: list, sheet_id: str = 'SID'):
        super().__init__(writes)
        self._worksheets = dict(worksheets)
        self.id = sheet_id
        self.title = f'Sheet {sheet_id}'

    def worksheet(self, name):
        import gspread
        if name not in self._worksheets:
            raise gspread.WorksheetNotFound(name)
        return TripwireWorksheet(self._worksheets[name], self.writes, title=name)

    def worksheets(self):
        return [TripwireWorksheet(v, self.writes, title=k) for k, v in self._worksheets.items()]


class TripwireClient:
    """`open_by_key(sid)` → `TripwireSpreadsheet`；`books` 是 {sid: {worksheet: values}}。"""

    def __init__(self, books: dict, writes: list | None = None):
        self.books = books
        self.writes = writes if writes is not None else []
        self.opened: list[str] = []

    def open_by_key(self, sid):
        self.opened.append(sid)
        if sid not in self.books:
            raise PermissionError(f'no ACL for {sid}')
        return TripwireSpreadsheet(self.books[sid], self.writes, sheet_id=sid)
