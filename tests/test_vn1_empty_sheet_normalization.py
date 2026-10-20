"""VN1-STORE 空白分頁收斂守衛（2026-10-20 真連線 smoke 回修）。

背景：真 Streamlit smoke 對空白 `risk_cap_daily` 回報
`read_status=SCHEMA_MISMATCH header_state=MISMATCH data_rows=0`。根因：gspread 6.2.1
`Worksheet.get_values`（`gspread/worksheet.py:962`）`response.get("values", [[]])` —— Sheets API 對空範圍
省略 `values` 鍵 ⇒ L1 收到 `[[]]`，舊碼只把 `[]` 當空表。修法：L1 單一 helper `normalize_sheet_values`。

守：
A. `[]`／`[[]]` ⇒ ABSENT／EMPTY；契約：**真** gspread `Worksheet.get_all_values`（假 HTTP client 回 `{}` 與
   `{"values": []}`）的輸出經 L1 收斂成空表。
B. schema 守衛不放寬：錯表頭 ⇒ MISMATCH；`[[], [資料]]`、`fill_gaps` 後的 `[["",...],[資料]]`、`[[""]]` ⇒ 不是空表。
C. 寫前檢查／冪等寫入在 `[[]]` 上的行為與 `[]` 相同（先寫表頭再寫資料列）；錯表頭仍擋。
D. reader smoke／read_history 在 `[[]]` 上 ⇒ EMPTY／ABSENT／START_RECORDING。
突變：拔掉 `[[]]` 的收斂 ⇒ A～C 的回歸點轉紅（`_mutated_module`，恰好命中一次）。
⛔ 不碰 `PRODUCTION_WRITE_APPROVED`（不讀、不設、不 monkeypatch）。不連網。
"""
from __future__ import annotations

import pytest

from shared import risk_cap_history_policy as P
from src.data.risk_cap import history as L1H
from src.services import risk_cap_history_reader_service as R
from tests.test_batch_z64 import NOW
from tests.test_p01_macro_refresh import _mutated_module
from tests.test_vn1_production_wiring import SID, _factory_for, _FakeWS, _secrets, _values
from tests.test_vn1_store_poc import _row

L1_REL = "src/data/risk_cap/history.py"
TODAY = "2026-10-14"           # `_row()` 的 record_date
HEADER = list(P.HISTORY_COLUMNS)
DATA = [_row()[c] for c in P.HISTORY_COLUMNS]
#: 第 1 列空白、第 2 列有內容（API 回 `[[], [...]]`；gspread `fill_gaps` 後第 1 列補成空字串）。
HEADERLESS_RAW = [[], DATA]
HEADERLESS_FILLED = [[""] * len(DATA), DATA]

@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    R.clear_read_cache()
    monkeypatch.setattr(R, "_SMOKE_DONE", False)
    yield
    R.clear_read_cache()


def _real_ws(response: dict):
    """真 gspread 6.x `Worksheet`，只把 HTTP 層換成回固定 JSON 的假 client（⛔ 不連網、無憑證）。"""
    pytest.importorskip("gspread", reason="gspread 未安裝 ⇒ 無法驅動真 Worksheet 的契約測試")
    from gspread.http_client import HTTPClient
    from gspread.worksheet import Worksheet

    class _FakeHTTP(HTTPClient):
        def __init__(self) -> None:          # ⛔ 不呼叫 super()：不建 session、不碰憑證
            self.calls = 0

        def values_get(self, spreadsheet_id, range_name, params=None):
            self.calls += 1
            assert spreadsheet_id == SID
            return dict(response)

    return Worksheet(None, {"title": P.HISTORY_WORKSHEET_NAME, "sheetId": 0, "index": 0},
                     spreadsheet_id=SID, client=_FakeHTTP())


# ══════════════════════════════════════════════════════════════════════════
# A. 空表的兩種表示法
# ══════════════════════════════════════════════════════════════════════════
class TestBlankShapes:
    @pytest.mark.parametrize("values", [[], [[]]])
    def test_normalize_to_empty(self, values):
        assert L1H.normalize_sheet_values(values) == []

    @pytest.mark.parametrize("values", [[], [[]]])
    def test_header_absent_records_empty(self, values):
        assert L1H.header_state(values) == P.HEADER_STATE_ABSENT
        assert L1H.rows_as_records(values) == []

    def test_normalize_stringifies_and_copies(self):
        src = [["a", 1]]
        out = L1H.normalize_sheet_values(src)
        assert out == [["a", "1"]] and out is not src and out[0] is not src[0]

    @pytest.mark.parametrize("response", [{}, {"values": []}])
    def test_real_gspread_blank_contract(self, response):
        ws = _real_ws(response)
        raw = ws.get_all_values()
        assert raw == [[]], "gspread 6.2.1 對空表回 [[]]；若改了請重審 normalize_sheet_values 的證據"
        adapter = L1H.GspreadWorksheetAdapter(ws, expected_sheet_id=SID)
        assert adapter.get_all_values() == []
        assert L1H.read_history_values(adapter) == []
        assert L1H.read_history_records(adapter) == []

    def test_real_gspread_headerless_shape_is_fill_gapped(self):
        assert _real_ws({"values": HEADERLESS_RAW}).get_all_values() == HEADERLESS_FILLED


# ══════════════════════════════════════════════════════════════════════════
# B. schema 守衛不放寬
# ══════════════════════════════════════════════════════════════════════════
class TestNotBlank:
    def test_wrong_header_mismatch(self):
        assert L1H.header_state([["x"]]) == P.HEADER_STATE_MISMATCH
        with pytest.raises(L1H.HistorySchemaMismatch):
            L1H.rows_as_records([["x"]])

    def test_correct_header_match(self):
        assert L1H.header_state([HEADER]) == P.HEADER_STATE_MATCH
        assert L1H.rows_as_records([HEADER]) == []

    def test_header_and_data_records(self):
        assert L1H.rows_as_records(_values(_row())) == [_row()]

    @pytest.mark.parametrize("values", [HEADERLESS_RAW, HEADERLESS_FILLED, [[""]], [["", ""]]],
                             ids=["raw", "fill_gaps", "one_blank_cell", "two_blank_cells"])
    def test_not_treated_as_empty(self, values):
        assert L1H.normalize_sheet_values(values) != []
        assert L1H.header_state(values) == P.HEADER_STATE_MISMATCH
        with pytest.raises(L1H.HistorySchemaMismatch):
            L1H.rows_as_records(values)

    def test_real_gspread_headerless_is_schema_mismatch(self):
        adapter = L1H.GspreadWorksheetAdapter(_real_ws({"values": HEADERLESS_RAW}), expected_sheet_id=SID)
        with pytest.raises(L1H.HistorySchemaMismatch):
            L1H.read_history_records(adapter)


# ══════════════════════════════════════════════════════════════════════════
# C. 寫前檢查／冪等寫入
# ══════════════════════════════════════════════════════════════════════════
class TestWritePath:
    def test_precheck_blank_passes(self):
        res = L1H.precheck_target([[]], _row(), today_tw=TODAY)
        assert res.ok and res.header_state == P.HEADER_STATE_ABSENT and res.data_rows == 0

    @pytest.mark.parametrize("values", [HEADERLESS_FILLED, [[""]]])
    def test_precheck_headerless_blocked(self, values):
        res = L1H.precheck_target(values, _row(), today_tw=TODAY)
        assert P.PRECHECK_FAIL_HEADER_MISMATCH in res.failures

    def test_inmemory_emits_gspread_blank_shape(self):
        assert L1H.InMemoryWorksheet([[]]).get_all_values() == [[]]

    def test_upsert_blank_writes_header_then_row(self):
        ws = L1H.InMemoryWorksheet([[]])
        assert L1H.upsert_record(ws, _row()) == P.UPSERT_APPENDED
        assert ws.get_all_values() == _values(_row())
        assert ws.append_calls == 2
        assert L1H.verify_written(ws.get_all_values(), _row(), "1").ok

    def test_upsert_wrong_header_still_blocked(self):
        ws = L1H.InMemoryWorksheet([["x"]])
        with pytest.raises(L1H.HistorySchemaMismatch):
            L1H.upsert_record(ws, _row())
        assert ws.append_calls == 0

    def test_upsert_headerless_blocked(self):
        ws = L1H.InMemoryWorksheet(HEADERLESS_FILLED)
        with pytest.raises(L1H.HistorySchemaMismatch):
            L1H.upsert_record(ws, _row())
        assert ws.append_calls == 0

    def test_verify_written_blank_fails(self):
        assert L1H.verify_written([[]], _row(), "1").failures == (P.VERIFY_FAIL_HEADER_MISMATCH,)


# ══════════════════════════════════════════════════════════════════════════
# D. reader smoke／read_history
# ══════════════════════════════════════════════════════════════════════════
class TestReader:
    def _check(self, res):
        assert (res.read_status, res.identity_ok, res.header_state, res.data_rows, res.compare_status) == (
            P.READ_STATUS_EMPTY, True, P.HEADER_STATE_ABSENT, 0, P.COMPARE_START_RECORDING)

    def test_smoke_blank_fake_ws(self):
        self._check(R.smoke_check(NOW, secrets=_secrets(), client_factory=_factory_for(_FakeWS([[]]))))

    @pytest.mark.parametrize("response", [{}, {"values": []}])
    def test_smoke_blank_real_gspread(self, response):
        self._check(R.smoke_check(NOW, secrets=_secrets(), client_factory=_factory_for(_real_ws(response))))

    def test_smoke_headerless_schema_mismatch(self):
        res = R.smoke_check(NOW, secrets=_secrets(),
                            client_factory=_factory_for(_real_ws({"values": HEADERLESS_RAW})))
        assert (res.read_status, res.header_state, res.data_rows) == (
            P.READ_STATUS_SCHEMA_MISMATCH, P.HEADER_STATE_MISMATCH, 1)

    def test_read_history_blank(self):
        res = R.read_history(expected_date=TODAY, now=NOW, secrets=_secrets(),
                             client_factory=_factory_for(_FakeWS([[]])))
        assert res.status == P.READ_STATUS_EMPTY and res.rows == ()
        assert res.compare is not None and res.compare.status == P.COMPARE_START_RECORDING


# ══════════════════════════════════════════════════════════════════════════
# 突變自驗：拔掉 `[[]]` 收斂 ⇒ 回歸點轉紅
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
def mut():
    return _mutated_module(L1_REL, ("    if not rows or rows == [[]]:\n", "    if not rows:\n"))


class TestMutation:
    def test_mutant_header_state_regresses(self, mut):
        assert mut.header_state([[]]) == P.HEADER_STATE_MISMATCH
        assert mut.header_state([]) == P.HEADER_STATE_ABSENT       # `[]` 不受影響 ⇒ 舊測試抓不到

    def test_mutant_records_regress(self, mut):
        with pytest.raises(mut.HistorySchemaMismatch):
            mut.rows_as_records([[]])

    def test_mutant_precheck_regresses(self, mut):
        assert P.PRECHECK_FAIL_HEADER_MISMATCH in mut.precheck_target([[]], _row(), today_tw=TODAY).failures

    def test_mutant_upsert_regresses(self, mut):
        with pytest.raises(mut.HistorySchemaMismatch):
            mut.upsert_record(mut.InMemoryWorksheet([[]]), _row())

    def test_original_passes_same_inputs(self):
        assert L1H.header_state([[]]) == P.HEADER_STATE_ABSENT
        assert L1H.precheck_target([[]], _row(), today_tw=TODAY).ok
