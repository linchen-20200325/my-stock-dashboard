"""tests/test_stock_local_ohlcv.py — 本機匯入個股日 K（L1，純 bytes 解析）。

對應 src/data/stock/stock_local_ohlcv.py:parse_local_ohlcv_csv。
⛔ 全離線：autouse fixture 封鎖 socket 與 requests；本檔不連網、不讀寫真實檔案（輸入全是記憶體 bytes）。
"""
from __future__ import annotations

import ast
import dataclasses
import logging
import socket
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.data.stock import stock_local_ohlcv as mod
from src.data.stock.stock_latest_ohlcv import (
    STATE_FETCH_FAILED, STATE_INVALID_DATA, STATE_INVALID_SYMBOL, STATE_NO_DATA, STATE_OK,
    OhlcvRow, StockLatestOhlcv, rows_to_bars_frame, to_bars_frame,
)
from src.data.stock.stock_local_ohlcv import LocalOhlcvImport, parse_local_ohlcv_csv

MODULE_PATH = Path(mod.__file__)
TODAY = date(2026, 11, 27)
SENT = "LEAK-SENTINEL-7b2e41"

EN_HEADER = ["stock_id", "date", "open", "high", "low", "close", "volume"]
FM_HEADER = ["stock_id", "date", "open", "max", "min", "close", "Trading_Volume"]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("真連網被封鎖：本測試檔限離線")
    monkeypatch.setattr(socket.socket, "connect", _boom)
    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", _boom)
    monkeypatch.setattr(requests, "get", _boom)


# ───────────────────────── helpers ─────────────────────────

def _r(d="2026-11-25", o="100", h="105", lo="99", c="104", v="12345000", sid="0050"):
    """一列（順序＝EN_HEADER／FM_HEADER：stock_id,date,open,high/max,low/min,close,volume）。"""
    return [sid, d, o, h, lo, c, v]


def _csv(rows, header=EN_HEADER, eol="\n", bom=False, trailing_eol=True) -> bytes:
    lines = [",".join(header)] + [",".join(str(x) for x in r) for r in rows]
    text = eol.join(lines) + (eol if trailing_eol else "")
    return (b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8")


def _good_rows():
    return [_r("2026-11-24", "98", "101", "97", "100", "1000"),
            _r("2026-11-25", "100", "105", "99", "104", "2000"),
            _r("2026-11-26", "104", "106", "103", "105.5", "3000")]


def _p(data, symbol="0050", today=TODAY) -> LocalOhlcvImport:
    return parse_local_ohlcv_csv(data, symbol, today=today)


def _assert_invalid(r, *codes):
    assert r.state == STATE_INVALID_DATA and r.error_code == "invalid_data"
    assert r.rows == () and r.latest is None and r.as_of is None and r.n_rows == 0
    assert r.source == mod.SOURCE_LOCAL_IMPORT
    for c in codes:
        assert c in r.reasons, (c, r.reasons)
    assert len(set(r.reasons)) == len(r.reasons) and r.reasons


def _with_col(rows, idx, value):
    out = [list(x) for x in rows]
    out[0][idx] = value
    return out


# ───────────────────────── 正常 ─────────────────────────

class TestOk:
    def test_english_header_values_and_provenance(self):
        r = _p(_csv(_good_rows()))
        assert r.state == STATE_OK and r.error_code is None and r.reasons == ()
        assert r.symbol == "0050" and isinstance(r.symbol, str)
        assert r.n_rows == 3 and len(r.rows) == 3
        assert [x.date for x in r.rows] == [date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 26)]
        assert r.latest is r.rows[-1] and r.as_of == date(2026, 11, 26)
        assert (r.latest.open, r.latest.high, r.latest.low, r.latest.close) == (104.0, 106.0, 103.0, 105.5)
        assert r.latest.volume_shares == 3000.0                         # 不換算
        assert isinstance(r.rows, tuple) and all(isinstance(x, OhlcvRow) for x in r.rows)
        assert r.source == mod.SOURCE_LOCAL_IMPORT

    def test_finmind_native_header_same_result_as_english(self):
        a = _p(_csv(_good_rows(), EN_HEADER))
        b = _p(_csv(_good_rows(), FM_HEADER))
        assert b.state == STATE_OK and a.rows == b.rows and a.as_of == b.as_of

    def test_column_order_is_irrelevant(self):
        header = ["volume", "close", "low", "high", "open", "date", "stock_id"]
        rows = [list(reversed(x)) for x in _good_rows()]
        r = _p(_csv(rows, header))
        assert r.state == STATE_OK and r.rows == _p(_csv(_good_rows())).rows

    def test_utf8_bom(self):
        r = _p(_csv(_good_rows(), bom=True))
        assert r.state == STATE_OK and r.n_rows == 3

    def test_crlf_and_cr_only_line_endings(self):
        assert _p(_csv(_good_rows(), eol="\r\n")).state == STATE_OK
        assert _p(_csv(_good_rows(), eol="\r")).state == STATE_OK

    def test_no_trailing_newline(self):
        assert _p(_csv(_good_rows(), trailing_eol=False)).n_rows == 3

    def test_blank_lines_are_skipped(self):
        data = b"\n" + _csv(_good_rows()).replace(b"\n", b"\n\n") + b"\n\n"
        r = _p(data)
        assert r.state == STATE_OK and r.n_rows == 3

    def test_quoted_fields(self):
        rows = [[f'"{x}"' for x in row] for row in _good_rows()]
        header = [f'"{h}"' for h in EN_HEADER]
        r = _p(_csv(rows, header))
        assert r.state == STATE_OK and r.latest.close == 105.5

    def test_extra_columns_ignored_including_non_ascii_and_commas(self):
        header = EN_HEADER + ["備註", "note"]
        rows = [x + ["中文，含逗號", '"a,b"'] for x in _good_rows()]
        r = _p(_csv(rows, header))
        assert r.state == STATE_OK and r.n_rows == 3

    def test_leading_zero_symbol_preserved_not_int(self):
        r = _p(_csv(_good_rows()), "0050")
        assert r.symbol == "0050" and r.state == STATE_OK
        r2 = _p(_csv([_r(sid="00631L")]), "00631l")
        assert r2.state == STATE_OK and r2.symbol == "00631L"

    def test_whitespace_around_cells_and_header(self):
        header = [f" {h} " for h in EN_HEADER]
        rows = [[f"  {x}  " for x in row] for row in _good_rows()]
        r = _p(_csv(rows, header))
        assert r.state == STATE_OK and r.rows == _p(_csv(_good_rows())).rows

    def test_symbol_argument_whitespace_and_case(self):
        assert _p(_csv(_good_rows()), " 0050 ").symbol == "0050"

    def test_single_row(self):
        r = _p(_csv([_r()]))
        assert r.state == STATE_OK and r.n_rows == 1 and r.latest is r.rows[0]

    def test_today_row_allowed(self):
        assert _p(_csv([_r("2026-11-27")])).as_of == TODAY

    def test_zero_volume_valid_and_distinct_from_missing(self):
        ok = _p(_csv([_r(v="0")]))
        assert ok.state == STATE_OK and ok.latest.volume_shares == 0.0
        assert _p(_csv([_r(v="")])).state == STATE_INVALID_DATA

    def test_numeric_formats_accepted(self):
        r = _p(_csv([_r(o="+1.0e2", h="1.05E2", lo=".99e2", c="104.", v="1e3")]))
        assert r.state == STATE_OK
        assert (r.latest.open, r.latest.high, r.latest.low, r.latest.close, r.latest.volume_shares) == (
            100.0, 105.0, 99.0, 104.0, 1000.0)

    def test_input_buffer_types(self):
        data = _csv(_good_rows())
        assert _p(bytearray(data)).state == STATE_OK
        assert _p(memoryview(data)).state == STATE_OK

    def test_input_not_mutated(self):
        ba = bytearray(_csv(_good_rows()))
        snap = bytes(ba)
        _p(ba)
        assert bytes(ba) == snap

    def test_deterministic_and_no_cross_call_state(self):
        a = _p(_csv(_good_rows()))
        b = _p(_csv([_r("2026-11-20")]))
        assert a == _p(_csv(_good_rows())) and b.as_of == date(2026, 11, 20)

    def test_result_has_no_fetch_provenance_fields(self):
        names = {f.name for f in dataclasses.fields(LocalOhlcvImport)}
        assert names == {"state", "symbol", "rows", "latest", "as_of", "source", "error_code",
                         "reasons", "n_rows"}
        assert not names & {"fetched_at", "authenticated", "imported_at", "filename", "path"}

    def test_source_is_fixed_constant(self):
        assert mod.SOURCE_LOCAL_IMPORT == "本機匯入（使用者提供檔案，來源未經系統驗證）"
        for data in (_csv(_good_rows()), b"", b"\xff", _csv(_good_rows()).replace(b"0050", b"2330")):
            assert _p(data).source == mod.SOURCE_LOCAL_IMPORT


# ───────────────────────── 空檔／只有表頭 ─────────────────────────

class TestEmptyInputs:
    @pytest.mark.parametrize("data", [b"", b"\xef\xbb\xbf", b"\n\n\n", b"\r\n", b"\xef\xbb\xbf\n"],
                             ids=["zero_bytes", "bom_only", "blank_lines", "crlf_only", "bom_blank"])
    def test_no_header_is_invalid_empty_file(self, data):
        r = _p(data)
        _assert_invalid(r, mod.REASON_EMPTY_FILE)
        assert r.state != STATE_NO_DATA                                 # 設計決定：沒有表頭＝壞檔，不是「沒資料」

    @pytest.mark.parametrize("header", [EN_HEADER, FM_HEADER])
    def test_header_only_is_no_data_not_invalid(self, header):
        r = _p(_csv([], header))
        assert r.state == STATE_NO_DATA and r.error_code == "no_data"
        assert r.rows == () and r.latest is None and r.as_of is None and r.n_rows == 0
        assert r.reasons == () and r.symbol == "0050" and r.source == mod.SOURCE_LOCAL_IMPORT

    def test_header_only_with_bom_no_trailing_newline(self):
        assert _p(_csv([], bom=True, trailing_eol=False)).state == STATE_NO_DATA

    def test_header_only_but_bad_header_is_invalid_not_no_data(self):
        _assert_invalid(_p(_csv([], ["stock_id", "date", "open"])), mod.REASON_MISSING_OHLCV_COLUMNS)

    def test_no_data_message_does_not_claim_stock_missing(self):
        r = _p(_csv([], EN_HEADER))
        assert "查無" not in repr(r) and "不存在" not in repr(r)


# ───────────────────────── 欄位 ─────────────────────────

class TestColumns:
    @pytest.mark.parametrize("col", ["open", "max", "min", "close", "Trading_Volume"])
    def test_finmind_group_missing_one_column(self, col):
        header = [h for h in FM_HEADER if h != col]
        i = FM_HEADER.index(col)
        rows = [[v for j, v in enumerate(x) if j != i] for x in _good_rows()]
        _assert_invalid(_p(_csv(rows, header)), mod.reason_missing_column(col))

    @pytest.mark.parametrize("col", ["open", "high", "low", "close", "volume"])
    def test_english_group_missing_one_column(self, col):
        header = [h for h in EN_HEADER if h != col]
        i = EN_HEADER.index(col)
        rows = [[v for j, v in enumerate(x) if j != i] for x in _good_rows()]
        _assert_invalid(_p(_csv(rows, header)), mod.reason_missing_column(col))

    @pytest.mark.parametrize("col", ["stock_id", "date"])
    def test_missing_required_key_column(self, col):
        header = [h for h in EN_HEADER if h != col]
        i = EN_HEADER.index(col)
        rows = [[v for j, v in enumerate(x) if j != i] for x in _good_rows()]
        _assert_invalid(_p(_csv(rows, header)), mod.reason_missing_column(col))

    def test_neither_group(self):
        r = _p(_csv([["0050", "2026-11-25", "1", "2"]], ["stock_id", "date", "open", "close"]))
        _assert_invalid(r, mod.REASON_MISSING_OHLCV_COLUMNS)
        assert mod.REASON_AMBIGUOUS_OHLCV_COLUMNS not in r.reasons

    def test_neither_group_reports_missing_shared_columns(self):
        r = _p(_csv([["0050", "2026-11-25"]], ["stock_id", "date"]))
        _assert_invalid(r, mod.REASON_MISSING_OHLCV_COLUMNS, "missing_column_open", "missing_column_close")

    def test_both_groups_complete_is_ambiguous(self):
        header = ["stock_id", "date", "open", "close", "max", "min", "Trading_Volume", "high", "low", "volume"]
        row = ["0050", "2026-11-25", "100", "104", "105", "99", "1000", "105", "99", "1000"]
        r = _p(_csv([row], header))
        _assert_invalid(r, mod.REASON_AMBIGUOUS_OHLCV_COLUMNS)

    @pytest.mark.parametrize("header", [
        ["stock_id", "date", "open", "max", "low", "close", "volume"],              # max + low + volume
        ["stock_id", "date", "open", "high", "min", "close", "Trading_Volume"],     # high + min + Trading_Volume
        ["stock_id", "date", "open", "max", "min", "high", "close", "Trading_Volume"],
    ], ids=["mixed1", "mixed2", "fm_plus_high"])
    def test_mixed_groups_rejected_not_guessed(self, header):
        row = ["0050", "2026-11-25"] + ["100"] * (len(header) - 2)
        _assert_invalid(_p(_csv([row], header)), mod.REASON_AMBIGUOUS_OHLCV_COLUMNS)

    def test_ambiguous_does_not_pick_either_group(self):
        header = FM_HEADER + ["high"]
        row = ["0050", "2026-11-25", "100", "105", "99", "104", "1000", "1"]
        r = _p(_csv([row], header))
        assert r.state == STATE_INVALID_DATA and r.rows == ()

    @pytest.mark.parametrize("bad", ["Open", "CLOSE", "Stock_ID", "Date", "trading_volume", "Max"])
    def test_column_names_are_case_sensitive(self, bad):
        header = list(EN_HEADER)
        target = {"Open": "open", "CLOSE": "close", "Stock_ID": "stock_id", "Date": "date"}.get(bad)
        if target is None:
            header = list(FM_HEADER)
            target = {"trading_volume": "Trading_Volume", "Max": "max"}[bad]
        header[header.index(target)] = bad
        r = _p(_csv([_r()], header))
        _assert_invalid(r, mod.reason_missing_column(target))

    def test_duplicate_column_rejected(self):
        header = EN_HEADER + ["close"]
        _assert_invalid(_p(_csv([_r() + ["999"]], header)), mod.REASON_DUPLICATE_COLUMN)

    def test_duplicate_after_strip_rejected(self):
        header = EN_HEADER + [" close "]
        _assert_invalid(_p(_csv([_r() + ["999"]], header)), mod.REASON_DUPLICATE_COLUMN)

    def test_duplicate_extra_column_also_rejected(self):
        header = EN_HEADER + ["note", "note"]
        _assert_invalid(_p(_csv([_r() + ["a", "b"]], header)), mod.REASON_DUPLICATE_COLUMN)

    def test_row_length_mismatch_short_and_long(self):
        _assert_invalid(_p(_csv([_r()[:-1]])), mod.REASON_ROW_LENGTH_MISMATCH)
        _assert_invalid(_p(_csv([_r() + ["extra"]])), mod.REASON_ROW_LENGTH_MISMATCH)
        rows = _good_rows()
        rows[1] = rows[1][:-1]                                        # 中間列短一格：不補空、整批拒絕
        _assert_invalid(_p(_csv(rows)), mod.REASON_ROW_LENGTH_MISMATCH)

    def test_whitespace_only_line_is_not_a_blank_line(self):
        data = _csv(_good_rows()) + b"   \n"
        _assert_invalid(_p(data), mod.REASON_ROW_LENGTH_MISMATCH)

    @pytest.mark.parametrize("commas", [6, 7, 8, 1])
    def test_comma_only_rows_are_never_skipped(self, commas):
        """SF-4：只有逗號（全空欄）的列不是「空白行」，絕不被略過。"""
        rows = _good_rows()
        data = _csv(rows) + ("," * commas).encode() + b"\n"
        r = _p(data)
        assert r.state == STATE_INVALID_DATA and r.rows == ()
        if commas == 6:                                      # 欄數相符（7 欄全空）→ 值層拒絕
            _assert_invalid(r, "stock_id_mismatch", "open_missing", "volume_shares_missing")
        else:                                                # 欄數不符 → 結構層拒絕
            _assert_invalid(r, mod.REASON_ROW_LENGTH_MISMATCH)

    def test_comma_only_row_in_middle_rejects_whole_batch(self):
        rows = _good_rows()
        lines = _csv(rows).split(b"\n")
        lines.insert(2, b",,,,,,")
        _assert_invalid(_p(b"\n".join(lines)), "stock_id_mismatch", "open_missing")

    def test_truly_blank_lines_are_skipped_but_whitespace_or_quoted_empty_are_not(self):
        base = _csv(_good_rows())
        assert _p(base + b"\n\n").n_rows == 3                         # 無任何字元的行：略過（現行行為）
        assert _p(base.replace(b"\n", b"\n\n")).n_rows == 3
        assert _p(base + b"\r\n").n_rows == 3
        assert _p(base + b'""\n').state == STATE_INVALID_DATA         # 引號空欄：欄數不符
        assert _p(base + b" \n").state == STATE_INVALID_DATA
        assert _p(base + b"\t\n").state == STATE_INVALID_DATA

    def test_bom_in_middle_header_breaks_first_column(self):
        data = _csv(_good_rows(), bom=True)
        data = b"\xef\xbb\xbf" + data                                  # 兩個 BOM：只剝一個
        _assert_invalid(_p(data), mod.reason_missing_column("stock_id"))

    def test_malformed_csv_quotes(self):
        data = b'stock_id,date,open,high,low,close,volume\n"0050"x,2026-11-25,1,2,1,2,3\n'
        _assert_invalid(_p(data), mod.REASON_CSV_MALFORMED)
        data2 = b'stock_id,date,open,high,low,close,volume\n"0050,2026-11-25,1,2,1,2,3\n'
        assert _p(data2).state == STATE_INVALID_DATA

    def test_oversized_single_field_is_malformed_not_crash(self):
        huge = b"x" * 200_000                                           # 超過 csv 預設欄寬上限 131072
        data = b"stock_id,date,open,high,low,close,volume,note\n0050,2026-11-25,1,2,1,2,3," + huge + b"\n"
        _assert_invalid(_p(data), mod.REASON_CSV_MALFORMED)


# ───────────────────────── stock_id ─────────────────────────

class TestStockId:
    def test_mismatch_whole_batch(self):
        r = _p(_csv([_r(sid="2330")]))
        _assert_invalid(r, "stock_id_mismatch")

    def test_partial_mismatch_rejects_everything(self):
        rows = _good_rows()
        rows[1][0] = "2330"
        r = _p(_csv(rows))
        _assert_invalid(r, "stock_id_mismatch")

    def test_last_row_mismatch(self):
        rows = _good_rows()
        rows[2][0] = "0051"
        _assert_invalid(_p(_csv(rows)), "stock_id_mismatch")

    @pytest.mark.parametrize("cell", ["", "   ", "0050.TW", "０５００", "00 50", "50", "ı050", "0050\u200b"])
    def test_weird_cells_do_not_match(self, cell):
        _assert_invalid(_p(_csv([_r(sid=cell)])), "stock_id_mismatch")

    def test_dotless_i_cannot_alias_symbol_i(self):
        r = _p(_csv([_r(sid="00929ı")]), "00929I")
        _assert_invalid(r, "stock_id_mismatch")

    def test_numeric_looking_id_without_leading_zero_does_not_match(self):
        _assert_invalid(_p(_csv([_r(sid="50")])), "stock_id_mismatch")

    def test_lowercase_cell_matches_normalised_symbol(self):
        assert _p(_csv([_r(sid="00631l")]), "00631L").state == STATE_OK

    def test_requested_symbol_is_what_is_compared(self):
        assert _p(_csv(_good_rows()), "2330").state == STATE_INVALID_DATA


# ───────────────────────── 編碼 ─────────────────────────

class TestEncoding:
    def _big5_csv(self, enc):
        header = EN_HEADER + ["備註"]
        rows = [x + ["測試"] for x in _good_rows()]
        text = "\n".join([",".join(header)] + [",".join(r) for r in rows]) + "\n"
        return text.encode(enc)

    @pytest.mark.parametrize("enc", ["big5", "cp950"])
    def test_non_utf8_chinese_rejected(self, enc):
        r = _p(self._big5_csv(enc))
        _assert_invalid(r, mod.REASON_ENCODING_NOT_UTF8)
        assert "�" not in repr(r)

    def test_utf8_version_of_same_file_is_ok(self):
        assert _p(self._big5_csv("utf-8")).state == STATE_OK

    def test_truncated_utf8_sequence(self):
        data = _csv(_good_rows())[:-1] + "測".encode("utf-8")[:2]
        _assert_invalid(_p(data), mod.REASON_ENCODING_NOT_UTF8)

    @pytest.mark.parametrize("junk", [b"\xff", b"\xfe\xff", b"\xc3\x28", b"\x80", b"\xed\xa0\x80"],
                             ids=["ff", "fefe", "bad2byte", "continuation", "surrogate"])
    def test_invalid_utf8_bytes(self, junk):
        data = _csv(_good_rows()) + junk
        _assert_invalid(_p(data), mod.REASON_ENCODING_NOT_UTF8)

    def test_nul_byte_rejected(self):
        data = _csv(_good_rows())
        _assert_invalid(_p(data.replace(b"0050", b"00\x0050", 1)), mod.REASON_CONTAINS_NUL)
        _assert_invalid(_p(data + b"\x00"), mod.REASON_CONTAINS_NUL)

    def test_utf16_rejected(self):
        text = _csv(_good_rows()).decode("utf-8")
        _assert_invalid(_p(text.encode("utf-16")))
        _assert_invalid(_p(text.encode("utf-16-le")), mod.REASON_CONTAINS_NUL)

    def test_encoding_error_does_not_leak_bytes_or_positions(self):
        r = _p(self._big5_csv("big5"))
        assert r.reasons == (mod.REASON_ENCODING_NOT_UTF8,)
        assert "position" not in repr(r) and "codec" not in repr(r)


# ───────────────────────── 大小／列數上限 ─────────────────────────

def _rows_n(n):
    base = date(2000, 1, 1)
    return [_r((base + timedelta(days=i)).isoformat()) for i in range(n)]


def _sized_csv(total_bytes: int) -> bytes:
    """產生長度剛好 total_bytes 的合法 CSV（用多出的 note 欄塞到目標大小）。"""
    header = ",".join(EN_HEADER + ["note"]) + "\n"
    base = date(2000, 1, 1)
    n_rows = 25
    lines = [",".join(_r((base + timedelta(days=i)).isoformat())) + "," for i in range(n_rows)]
    fixed = len(header) + sum(len(x) + 1 for x in lines)           # +1＝換行
    pad_total = total_bytes - fixed
    per = pad_total // n_rows
    pads = [per] * n_rows
    pads[-1] += pad_total - per * n_rows
    assert max(pads) < 131_072, "單格不得超過 csv 預設欄寬上限"
    out = header + "".join(x + "n" * p + "\n" for x, p in zip(lines, pads))
    data = out.encode("utf-8")
    assert len(data) == total_bytes
    return data


class TestLimits:
    def test_constants_are_named_and_pinned(self):
        assert mod.MAX_FILE_BYTES == 2 * 1024 * 1024 == 2_097_152
        assert mod.MAX_DATA_ROWS == 5000

    def test_file_size_exactly_at_limit_is_allowed(self):
        data = _sized_csv(mod.MAX_FILE_BYTES)
        assert len(data) == mod.MAX_FILE_BYTES
        r = _p(data)
        assert r.state == STATE_OK and r.n_rows == 25

    def test_file_size_one_over_limit_rejected_without_parsing(self):
        data = _sized_csv(mod.MAX_FILE_BYTES + 1)
        r = _p(data)
        _assert_invalid(r, mod.REASON_FILE_TOO_LARGE)
        assert r.reasons == (mod.REASON_FILE_TOO_LARGE,)

    def test_oversize_wins_even_if_content_is_garbage(self):
        r = _p(b"\xff" * (mod.MAX_FILE_BYTES + 1))                  # 不解碼：原因是 too_large 而非 encoding
        assert r.reasons == (mod.REASON_FILE_TOO_LARGE,)

    def test_oversize_memoryview_and_bytearray(self):
        big = bytearray(mod.MAX_FILE_BYTES + 1)
        assert _p(big).reasons == (mod.REASON_FILE_TOO_LARGE,)
        assert _p(memoryview(big)).reasons == (mod.REASON_FILE_TOO_LARGE,)

    def test_oversize_memoryview_counts_bytes_not_items(self):
        import array
        arr = array.array("i", [0]) * (mod.MAX_FILE_BYTES // 4 + 1)      # 項數 < 上限，但 nbytes > 上限
        mv = memoryview(arr)
        assert len(mv) < mod.MAX_FILE_BYTES < mv.nbytes
        assert _p(mv).reasons == (mod.REASON_FILE_TOO_LARGE,)

    def test_exactly_max_rows_allowed(self):
        r = _p(_csv(_rows_n(mod.MAX_DATA_ROWS)))
        assert r.state == STATE_OK and r.n_rows == mod.MAX_DATA_ROWS

    def test_one_more_row_rejected(self):
        r = _p(_csv(_rows_n(mod.MAX_DATA_ROWS + 1)))
        _assert_invalid(r, mod.REASON_TOO_MANY_ROWS)
        assert r.reasons == (mod.REASON_TOO_MANY_ROWS,)

    def test_blank_lines_do_not_count_as_rows(self):
        data = _csv(_rows_n(mod.MAX_DATA_ROWS)) + b"\n" * 10
        assert _p(data).state == STATE_OK


# ───────────────────────── 日期 ─────────────────────────

class TestDates:
    def test_duplicate_date(self):
        _assert_invalid(_p(_csv([_r("2026-11-25"), _r("2026-11-25")])), "date_duplicate")

    def test_nonadjacent_duplicate_date(self):
        _assert_invalid(_p(_csv([_r("2026-11-24"), _r("2026-11-25"), _r("2026-11-24")])), "date_duplicate")

    def test_descending_not_silently_sorted(self):
        r = _p(_csv([_r("2026-11-26"), _r("2026-11-25")]))
        _assert_invalid(r, "date_not_ascending")

    def test_future_date_uses_passed_today(self):
        _assert_invalid(_p(_csv([_r("2026-11-26"), _r("2026-11-28")])), "date_in_future")
        assert _p(_csv([_r("2026-11-28")]), today=date(2026, 11, 28)).state == STATE_OK   # 取決於傳入的 today
        _assert_invalid(_p(_csv([_r("2026-11-27")]), today=date(2026, 11, 26)), "date_in_future")

    @pytest.mark.parametrize("bad", ["2026/11/25", "20261125", "2026-2-3", "2026-02-30", "", "not-a-date",
                                     "2026-11-25T00:00:00", "2026-11-25 00:00", "２０２６-11-25", "25-11-2026",
                                     "115-11-25", "2026-13-01"])
    def test_non_iso_dates(self, bad):
        _assert_invalid(_p(_csv([_r(bad)])), "date_unparseable")

    def test_one_bad_date_rejects_all(self):
        rows = _good_rows()
        rows[1][1] = "bad"
        r = _p(_csv(rows))
        _assert_invalid(r, "date_unparseable")


# ───────────────────────── 缺值 ─────────────────────────

_FIELDS = [("open", 2), ("high", 3), ("low", 4), ("close", 5), ("volume_shares", 6)]


class TestMissingValues:
    @pytest.mark.parametrize("field,idx", _FIELDS)
    @pytest.mark.parametrize("token", ["", "  ", "nan", "NaN", "NAN", "null", "NULL", "None", "none", "NA", "N/A", "n/a"])
    def test_missing_tokens_reject_whole_batch_never_zero(self, field, idx, token):
        rows = _with_col(_good_rows(), idx, token)
        r = _p(_csv(rows))
        _assert_invalid(r, f"{field}_missing")
        assert r.rows == ()                                          # 不丟列、不補 0

    @pytest.mark.parametrize("field,idx", _FIELDS)
    def test_missing_in_last_row_too(self, field, idx):
        rows = _good_rows()
        rows[-1][idx] = ""
        _assert_invalid(_p(_csv(rows)), f"{field}_missing")

    def test_missing_is_not_confused_with_zero_volume(self):
        zero = _p(_csv(_with_col(_good_rows(), 6, "0")))
        miss = _p(_csv(_with_col(_good_rows(), 6, "")))
        assert zero.state == STATE_OK and zero.rows[0].volume_shares == 0.0
        assert miss.state == STATE_INVALID_DATA and "volume_shares_missing" in miss.reasons

    def test_missing_date_cell(self):
        _assert_invalid(_p(_csv(_with_col(_good_rows(), 1, ""))), "date_unparseable")

    @pytest.mark.parametrize("field,idx", _FIELDS)
    @pytest.mark.parametrize("bad", ["abc", "1_0", "１２", '"1,234"', "0x10", "--1", "1e", ".", "٣", "$100",
                                     "100元", "12 34", "true", "False", "[1]", "1.2.3", "e5"])
    def test_not_numeric(self, field, idx, bad):
        _assert_invalid(_p(_csv(_with_col(_good_rows(), idx, bad))), f"{field}_not_numeric")


# ───────────────────────── inf／極大值 ─────────────────────────

class TestNotFinite:
    HUGE_INT = "1" + "0" * 400
    VERY_HUGE = "9" * 5000

    @pytest.mark.parametrize("field,idx", _FIELDS)
    @pytest.mark.parametrize("bad", ["inf", "-inf", "+inf", "Infinity", "-INFINITY", "1e400", "-1e400", "1E999",
                                     HUGE_INT, VERY_HUGE, "-" + HUGE_INT])
    def test_not_finite_is_rejected_cleanly(self, field, idx, bad):
        r = _p(_csv(_with_col(_good_rows(), idx, bad)))               # 不得拋 OverflowError
        _assert_invalid(r, f"{field}_not_finite")

    def test_huge_but_finite_values_do_not_crash(self):
        # 現況記錄，非核准行為：本層不設價格／volume 絕對上限（上限屬待核准業務門檻）；
        # 極大有限值被接受，下游滾動均量可能溢位成偽值。請勿把此斷言當成「已防禦」。
        r = _p(_csv([_r(o="1e300", h="1e300", lo="1e300", c="1e300", v="1e300")]))
        assert r.state == STATE_OK and r.latest.close == 1e300

    def test_underflow_to_zero_price_is_rejected(self):
        _assert_invalid(_p(_csv([_r(o="1e-400", h="1e-400", lo="1e-400", c="1e-400")])), "close_not_positive")

    def test_many_huge_cells_stable(self):
        rows = [_r(f"2026-11-{d:02d}", o=self.HUGE_INT, h=self.HUGE_INT, lo=self.HUGE_INT,
                   c=self.HUGE_INT, v=self.HUGE_INT) for d in range(1, 20)]
        r = _p(_csv(rows))
        _assert_invalid(r, "open_not_finite", "volume_shares_not_finite")


class TestZeroLiterals:
    """SF-1／SF-2：字面非零卻下溢成 0 不可默默變 0；負零不可輸出 -0.0。"""

    @pytest.mark.parametrize("field,idx", _FIELDS)
    @pytest.mark.parametrize("bad", ["1e-400", "1e-999", "-1e-400", "9.9e-500", "0.0001e-400", "+5E-324000"])
    def test_underflow_of_nonzero_literal_rejected(self, field, idx, bad):
        r = _p(_csv(_with_col(_good_rows(), idx, bad)))
        _assert_invalid(r, f"{field}_not_representable")

    def test_underflow_volume_does_not_become_zero_row(self):
        r = _p(_csv([_r(v="1e-400")]))
        _assert_invalid(r, "volume_shares_not_representable")
        assert r.rows == ()

    @pytest.mark.parametrize("lit", ["0", "0.0", "0e5", "0.000", "+0", ".0", "0E-400"])
    def test_true_zero_volume_still_allowed(self, lit):
        r = _p(_csv([_r(v=lit)]))
        assert r.state == STATE_OK and r.latest.volume_shares == 0.0

    @pytest.mark.parametrize("lit", ["0", "0.0", "0e5"])
    def test_true_zero_price_still_rejected_by_old_rule_only(self, lit):
        r = _p(_csv([_r(o=lit)]))
        _assert_invalid(r, "open_not_positive")
        assert "open_not_representable" not in r.reasons and "open_negative_zero" not in r.reasons

    def test_subnormal_nonzero_is_accepted(self):
        r = _p(_csv([_r(v="1e-320")]))
        assert r.state == STATE_OK and r.latest.volume_shares > 0.0

    @pytest.mark.parametrize("lit", ["-0", "-0.0", "-0e5", "-.0", " -0 "])
    def test_negative_zero_volume_rejected_never_minus_zero(self, lit):
        r = _p(_csv([_r(v=lit)]))
        _assert_invalid(r, "volume_shares_negative_zero")
        assert r.rows == ()

    @pytest.mark.parametrize("field,idx", _FIELDS[:4])
    def test_negative_zero_price_rejected_consistently(self, field, idx):
        r = _p(_csv(_with_col(_good_rows(), idx, "-0")))
        _assert_invalid(r, f"{field}_negative_zero", f"{field}_not_positive")

    def test_kind_codes_locked(self):
        assert (mod.KIND_NOT_REPRESENTABLE, mod.KIND_NEGATIVE_ZERO) == ("not_representable", "negative_zero")

    def test_negative_nonzero_volume_still_volume_negative(self):
        _assert_invalid(_p(_csv([_r(v="-1")])), "volume_negative")


# ───────────────────────── 價格／OHLC／volume ─────────────────────────

class TestPriceRules:
    _NP = {"open": "open_not_positive", "high": "high_not_positive", "low": "low_not_positive",
           "close": "close_not_positive"}

    @pytest.mark.parametrize("field,idx", _FIELDS[:4])
    @pytest.mark.parametrize("bad", ["0", "0.0", "-1.5", "-0"])
    def test_price_le_zero_rejects_whole_batch(self, field, idx, bad):
        rows = _good_rows()
        rows[1][idx] = bad                                            # 歷史列（非最新列）也不得被悄悄丟掉
        r = _p(_csv(rows))
        _assert_invalid(r, self._NP[field])

    def test_negative_price_extra_signal(self):
        r = _p(_csv([_r(o="-1", lo="-2")]))
        _assert_invalid(r, "price_negative", "open_not_positive")

    def test_zero_price_has_no_negative_signal(self):
        r = _p(_csv([_r(o="0")]))
        assert "price_negative" not in r.reasons and "open_not_positive" in r.reasons

    def test_all_zero_no_trade_day(self):
        r = _p(_csv([_r(o="0", h="0", lo="0", c="0", v="0")]))
        _assert_invalid(r, *self._NP.values())

    def test_tiny_positive_ok(self):
        assert _p(_csv([_r(o="0.01", h="0.02", lo="0.005", c="0.01")])).state == STATE_OK

    def test_high_below_low(self):
        _assert_invalid(_p(_csv([_r(o="100", h="98", lo="99", c="99")])), "high_below_low")

    def test_open_outside_range(self):
        _assert_invalid(_p(_csv([_r(o="110", h="105", lo="99", c="100")])), "open_outside_low_high")
        _assert_invalid(_p(_csv([_r(o="90", h="105", lo="99", c="100")])), "open_outside_low_high")

    def test_close_outside_range(self):
        _assert_invalid(_p(_csv([_r(o="100", h="105", lo="99", c="106")])), "close_outside_low_high")
        _assert_invalid(_p(_csv([_r(o="100", h="105", lo="99", c="98")])), "close_outside_low_high")

    def test_boundary_equalities_allowed(self):
        assert _p(_csv([_r(o="99", h="105", lo="99", c="105")])).state == STATE_OK
        assert _p(_csv([_r(o="100", h="100", lo="100", c="100")])).state == STATE_OK

    def test_negative_volume(self):
        _assert_invalid(_p(_csv([_r(v="-1")])), "volume_negative")

    def test_fractional_volume_not_truncated(self):
        assert _p(_csv([_r(v="1234.5")])).rows[0].volume_shares == 1234.5

    def test_volume_not_scaled(self):
        assert _p(_csv([_r(v="12345678")])).rows[0].volume_shares == 12_345_678.0

    def test_one_bad_row_rejects_whole_series(self):
        rows = _good_rows()
        rows[1][5] = ""
        r = _p(_csv(rows))
        _assert_invalid(r, "close_missing")

    def test_multiple_reasons_collected_in_order_without_duplicates(self):
        r = _p(_csv([_r("2026-11-28", v="-5")]))
        _assert_invalid(r, "date_in_future", "volume_negative")
        assert list(r.reasons) == list(dict.fromkeys(r.reasons))


# ───────────────────────── 代號／輸入型別 ─────────────────────────

class TestSymbolAndInputTypes:
    @pytest.mark.parametrize("bad", [50, "50", "", "   ", None, b"0050", 50.0, "12345678", "1234567", "00 50",
                                     "0050.TW", "0050.TWO", "００５０", "AB12", "00-50", "0050\n0051", "00$0",
                                     ["0050"], "ı234"])
    def test_invalid_symbol_not_parsed(self, bad):
        r = _p(_csv(_good_rows()), bad)
        assert r.state == STATE_INVALID_SYMBOL and r.symbol is None and r.error_code == "invalid_symbol"
        assert r.rows == () and r.latest is None and r.as_of is None and r.n_rows == 0 and r.reasons == ()

    def test_invalid_symbol_wins_before_looking_at_the_file(self):
        for data in (123, None, "text", b"\xff\x00", b"x" * (mod.MAX_FILE_BYTES + 1)):
            assert _p(data, "bad").state == STATE_INVALID_SYMBOL

    def test_invalid_symbol_not_echoed(self):
        assert "evil" not in repr(_p(_csv(_good_rows()), "evil<script>"))

    def test_symbol_rule_identical_to_fetch_path(self):
        from src.data.stock.stock_latest_ohlcv import _normalize_symbol
        for s in ["0050", " 0050 ", "00631l", "2330", "9999A", "50", "ab12", "0050.TW", None, 50]:
            ok = _p(_csv([_r(sid="0050")]), s).state != STATE_INVALID_SYMBOL
            assert ok == (_normalize_symbol(s) is not None), s

    @pytest.mark.parametrize("bad", ["a,b,c\n1,2,3\n", None, 123, 1.5, ["a"], {"a": 1}, object(), True])
    def test_non_bytes_input_rejected(self, bad):
        _assert_invalid(_p(bad), mod.REASON_INPUT_NOT_BYTES)

    def test_released_memoryview_is_fixed_reason_not_exception(self):
        """SF-5：已 release() 的 memoryview 不 raise，回固定原因碼。"""
        mv = memoryview(_csv(_good_rows()))
        mv.release()
        r = _p(mv)
        _assert_invalid(r, mod.REASON_INPUT_NOT_BYTES)
        assert r.reasons == (mod.REASON_INPUT_NOT_BYTES,)

    def test_released_memoryview_with_bad_symbol_is_still_invalid_symbol(self):
        mv = memoryview(b"abc")
        mv.release()
        assert _p(mv, "bad").state == STATE_INVALID_SYMBOL

    def test_non_contiguous_memoryview_does_not_raise(self):
        mv = memoryview(bytearray(_csv(_good_rows()) * 2))[::2]
        r = _p(mv)
        assert r.state == STATE_INVALID_DATA                 # 內容被抽樣壞掉，但不 raise
        assert r.reasons

    def test_str_with_valid_csv_text_still_rejected(self):
        text = _csv(_good_rows()).decode("utf-8")
        _assert_invalid(_p(text), mod.REASON_INPUT_NOT_BYTES)

    @pytest.mark.parametrize("bad", [datetime(2026, 11, 27), "2026-11-27", None, 20261127, 1.0])
    def test_today_must_be_date(self, bad):
        with pytest.raises(ValueError) as ei:
            parse_local_ohlcv_csv(_csv(_good_rows()), "0050", today=bad)  # type: ignore[arg-type]
        assert str(ei.value) == mod.TODAY_TYPE_MESSAGE

    def test_today_is_required_keyword(self):
        with pytest.raises(TypeError):
            parse_local_ohlcv_csv(_csv(_good_rows()), "0050")  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            parse_local_ohlcv_csv(_csv(_good_rows()), "0050", TODAY)  # type: ignore[misc]

    def test_bad_today_checked_even_for_bad_symbol(self):
        with pytest.raises(ValueError):
            parse_local_ohlcv_csv(b"", "bad", today="x")  # type: ignore[arg-type]

    def test_reason_code_set_locked(self):
        assert (mod.REASON_INPUT_NOT_BYTES, mod.REASON_FILE_TOO_LARGE, mod.REASON_EMPTY_FILE,
                mod.REASON_CONTAINS_NUL, mod.REASON_ENCODING_NOT_UTF8, mod.REASON_CSV_MALFORMED,
                mod.REASON_DUPLICATE_COLUMN, mod.REASON_AMBIGUOUS_OHLCV_COLUMNS,
                mod.REASON_MISSING_OHLCV_COLUMNS, mod.REASON_ROW_LENGTH_MISMATCH,
                mod.REASON_TOO_MANY_ROWS) == (
            "input_not_bytes", "file_too_large", "empty_file", "contains_nul", "encoding_not_utf8",
            "csv_malformed", "duplicate_column", "ambiguous_ohlcv_columns", "missing_ohlcv_columns",
            "row_length_mismatch", "too_many_rows")

    def test_never_returns_fetch_failed(self):
        for data in (b"", b"\xff", _csv(_good_rows()), _csv([], EN_HEADER)):
            assert _p(data).state != STATE_FETCH_FAILED


# ───────────────────────── 不變性／不洩漏／不落盤 ─────────────────────────

class TestImmutabilityAndLeaks:
    def test_frozen(self):
        r = _p(_csv(_good_rows()))
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.state = STATE_NO_DATA  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.latest.close = 1.0  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.rows = ()  # type: ignore[misc]
        assert isinstance(r.rows, tuple) and isinstance(r.reasons, tuple)

    def test_failure_results_are_frozen_too(self):
        r = _p(b"")
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.reasons = ()  # type: ignore[misc]

    def _poisoned_inputs(self):
        hdr = ",".join(EN_HEADER + [SENT + "_col"])
        base = "0050,2026-11-25,100,105,99,104,1000"
        return {
            "bad_cell": f"{hdr}\n{base},x\n".replace("100,105", f"{SENT},105", 1).encode(),
            "bad_stock_id": f"{hdr}\n{SENT},2026-11-25,100,105,99,104,1000,x\n".encode(),
            "bad_date": f"{hdr}\n0050,{SENT},100,105,99,104,1000,x\n".encode(),
            "dup_header": f"{hdr},{SENT}_col\n{base},x,y\n".encode(),
            "missing_cols": f"stock_id,date,{SENT}\n0050,2026-11-25,1\n".encode(),
            "ambiguous": f"{hdr},max,{SENT}\n{base},x,1,2\n".encode(),
            "bad_quotes": f'{hdr}\n"{SENT}"x,2026-11-25,1,2,1,2,3,x\n'.encode(),
            "path_like": f"C:\\Users\\{SENT}\\secret.csv,/home/{SENT}/x.csv\n".encode(),
            "big5": f"{hdr},備註\n{base},測試\n".encode("big5"),
            "ok_with_extra": f"{hdr}\n{base},{SENT}_cell\n".encode(),
        }

    def test_no_input_text_in_any_surface(self, capsys, caplog):
        caplog.set_level(logging.DEBUG)
        for name, data in self._poisoned_inputs().items():
            r = _p(data)
            surfaces = [repr(r), str(r), r.error_code or "", r.source, repr(r.reasons), repr(r.rows)]
            surfaces += [repr(getattr(r, f.name)) for f in dataclasses.fields(r)]
            for s in surfaces:
                assert SENT not in s and "secret.csv" not in s and "C:\\" not in s, name
            assert all(isinstance(x, str) and SENT not in x for x in r.reasons)
        _p(_csv(_good_rows()), SENT)                                 # 壞代號也不回顯
        out = capsys.readouterr()
        assert SENT not in out.out and SENT not in out.err and SENT not in caplog.text
        assert out.out == "" and out.err == "" and caplog.text == ""

    def test_reasons_are_from_fixed_vocabulary(self):
        fixed = {getattr(mod, n) for n in dir(mod) if n.startswith("REASON_")}
        for name, data in self._poisoned_inputs().items():
            for code in _p(data).reasons:
                assert code in fixed or code.startswith("missing_column_") or code.endswith(
                    ("_missing", "_not_finite", "_not_numeric", "_not_positive",
                     "_not_representable", "_negative_zero")) or code in {
                    "stock_id_mismatch", "date_unparseable", "date_duplicate", "date_not_ascending",
                    "date_in_future", "price_negative", "high_below_low", "open_outside_low_high",
                    "close_outside_low_high", "volume_negative"}, (name, code)

    def test_source_never_contains_filename_or_input(self):
        assert SENT not in _p(self._poisoned_inputs()["ok_with_extra"]).source

    def test_no_disk_access(self, monkeypatch, tmp_path):
        import builtins
        import io
        import os

        def _no(*a, **k):
            raise AssertionError("磁碟／暫存檔存取被封鎖")

        monkeypatch.setattr(builtins, "open", _no)
        monkeypatch.setattr(io, "open", _no)
        monkeypatch.setattr(os, "open", _no)
        for name in ("write_text", "write_bytes", "read_text", "read_bytes", "open", "touch", "mkdir"):
            monkeypatch.setattr(Path, name, _no)
        for name in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryFile", "TemporaryDirectory",
                     "SpooledTemporaryFile"):
            monkeypatch.setattr(tempfile, name, _no)
        for name in ("to_parquet", "to_csv", "to_pickle", "to_json", "to_feather"):
            monkeypatch.setattr(pd.DataFrame, name, _no)
        for name in ("read_csv", "read_parquet", "read_pickle"):
            monkeypatch.setattr(pd, name, _no)
        monkeypatch.chdir(tmp_path)
        before = sorted(p.name for p in tmp_path.iterdir())
        for data in (_csv(_good_rows()), _csv([], EN_HEADER), b"", b"\xff", _csv(_good_rows(), FM_HEADER)):
            _p(data)
        assert sorted(p.name for p in tmp_path.iterdir()) == before


# ───────────────────────── 靜態負控（AST）─────────────────────────

class TestStaticSource:
    SRC = MODULE_PATH.read_text(encoding="utf-8")
    TREE = ast.parse(SRC)
    ALLOWED_IMPORTS = {"__future__", "csv", "io", "re", "dataclasses", "datetime", "pandas",
                       "src.data.stock.stock_latest_ohlcv"}

    def _imports(self):
        out = []
        for n in ast.walk(self.TREE):
            if isinstance(n, ast.Import):
                out += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                out.append(n.module or "")
        return out

    def _names(self):
        out = set()
        for n in ast.walk(self.TREE):
            if isinstance(n, ast.Name):
                out.add(n.id)
            elif isinstance(n, ast.Attribute):
                out.add(n.attr)
            elif isinstance(n, ast.keyword) and n.arg:
                out.add(n.arg)
            elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                out.add(n.name)
        return out

    def test_import_allowlist(self):
        assert set(self._imports()) <= self.ALLOWED_IMPORTS, set(self._imports()) - self.ALLOWED_IMPORTS

    def test_no_streamlit_requests_proxy_logging(self):
        roots = {i.split(".")[0] for i in self._imports()}
        for banned in ("streamlit", "requests", "urllib", "http", "socket", "logging", "os", "sys", "time",
                       "tempfile", "pathlib", "shutil", "subprocess", "yfinance"):
            assert banned not in roots, banned
        assert not [i for i in self._imports() if "proxy" in i or "data_loader" in i or "finmind_client" in i]
        assert "st" not in self._names()

    def test_only_one_src_dependency(self):
        assert [i for i in self._imports() if i.startswith("src.")] == ["src.data.stock.stock_latest_ohlcv"]

    def test_forbidden_identifiers(self):
        names = self._names()
        for banned in ("fillna", "bfill", "ffill", "interpolate", "cache_data", "cache_resource", "session_state",
                       "to_parquet", "to_csv", "to_pickle", "read_csv", "read_parquet", "read_excel",
                       "environ", "getenv", "now", "utcnow", "today_", "gethostname", "_fetch_finmind_price_raw",
                       "_bps_dl", "_fm_raw_headers", "finmind_get", "errors", "astype", "sort_values",
                       "sort_index", "dropna", "to_numeric", "infer_objects"):
            assert banned not in names, banned

    def test_no_clock_attribute_calls(self):
        attrs = {n.attr for n in ast.walk(self.TREE) if isinstance(n, ast.Attribute)}
        assert not attrs & {"today", "now", "utcnow", "time", "monotonic", "perf_counter"}

    def test_no_verify_keyword(self):
        for n in ast.walk(self.TREE):
            if isinstance(n, ast.keyword) and n.arg == "verify":
                pytest.fail("verify= keyword must not appear")

    def test_no_open_print_eval_int_calls(self):
        calls = [n.func.id for n in ast.walk(self.TREE) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id in {"open", "print", "eval", "exec", "int", "input", "__import__", "compile"}]
        assert calls == []

    def test_no_bare_except_or_pass_swallowing(self):
        for n in ast.walk(self.TREE):
            if isinstance(n, ast.ExceptHandler):
                assert n.type is not None and not (isinstance(n.type, ast.Name) and n.type.id in {"Exception", "BaseException"})
                assert not all(isinstance(b, ast.Pass) for b in n.body)

    def test_no_replace_decoding(self):
        for n in ast.walk(self.TREE):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                assert n.value not in {"replace", "ignore", "surrogateescape", "backslashreplace"}

    def test_docstring_states_no_upper_bound_limitation(self):
        doc = ast.get_docstring(self.TREE) or ""
        assert "1e300" in doc and "上限" in doc and "非核准" in doc and "溢位" in doc
        assert "not_representable" in doc and "negative_zero" in doc

    def test_codec_is_strict_utf8_sig(self):
        assert mod._CODEC == "utf-8-sig"

    def test_no_module_level_mutable_state(self):
        for n in self.TREE.body:
            if isinstance(n, ast.Assign):
                assert not isinstance(n.value, (ast.List, ast.Dict, ast.Set)), ast.dump(n)[:80]

    def test_no_pandas_type_inference_on_input(self):
        # 必須以全字串（dtype=object）建 DataFrame，且沒有以 pandas 讀 CSV
        calls = [n for n in ast.walk(self.TREE) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "DataFrame"]
        assert len(calls) == 1
        assert any(k.arg == "dtype" and isinstance(k.value, ast.Name) and k.value.id == "object"
                   for k in calls[0].keywords)

    def test_limits_are_module_level_constants(self):
        assigned = {t.id for n in self.TREE.body if isinstance(n, ast.Assign)
                    for t in n.targets if isinstance(t, ast.Name)}
        assert {"MAX_FILE_BYTES", "MAX_DATA_ROWS", "SOURCE_LOCAL_IMPORT"} <= assigned

    def test_no_second_symbol_regex(self):
        # 代號規則只能來自 stock_latest_ohlcv._normalize_symbol（不得複製第二份正規式）
        assert "A-Z" not in self.SRC and "SYMBOL_RE" not in self.SRC


# ───────────────────────── 與 rows_to_bars_frame／C 線串接 ─────────────────────────

class TestBridgeToFacts:
    def _long_csv(self, n=300, header=EN_HEADER):
        base = date(2025, 1, 1)
        rows = [_r((base + timedelta(days=i)).isoformat(), str(100 + i % 7), str(103 + i % 7),
                   str(99 + i % 7), str(101 + i % 7), str(1000 + i)) for i in range(n)]
        return _csv(rows, header)

    def test_rows_convert_to_bars_shape(self):
        r = _p(_csv(_good_rows()))
        df = rows_to_bars_frame(r.rows)
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert type(df.index) is pd.DatetimeIndex and df.index.name == "date" and df.index.tz is None
        assert df.index.is_monotonic_increasing and df.index.is_unique
        assert all(str(t) == "float64" for t in df.dtypes)
        assert df.index[-1].date() == r.as_of
        assert df["volume"].tolist() == [1000.0, 2000.0, 3000.0]      # 不換算

    def test_same_frame_as_finmind_path_bridge(self):
        r = _p(_csv(_good_rows()))
        fake = StockLatestOhlcv(state=STATE_OK, symbol="0050", rows=r.rows, latest=r.latest, as_of=r.as_of,
                                fetched_at=datetime(2026, 11, 27, tzinfo=timezone.utc), source="x",
                                authenticated=False, error_code=None, reasons=(), n_rows=r.n_rows)
        pd.testing.assert_frame_equal(rows_to_bars_frame(r.rows), to_bars_frame(fake))

    @pytest.mark.parametrize("header", [EN_HEADER, FM_HEADER])
    def test_build_stock_research_facts_end_to_end(self, header):
        from src.compute.strategy.stock_research_facts import build_stock_research_facts
        r = _p(_csv(_good_rows(), header))
        facts = build_stock_research_facts(rows_to_bars_frame(r.rows), as_of=r.as_of)
        assert facts.as_of == r.as_of == date(2026, 11, 26)
        assert facts.bar_count == 3 and facts.close == 105.5
        assert facts.ma[5] is None                                    # 根數不足 → None（不是 0）

    def test_long_series_facts(self):
        from src.compute.strategy.stock_research_facts import build_stock_research_facts
        r = _p(self._long_csv(300), today=date(2026, 11, 27))
        assert r.state == STATE_OK and r.n_rows == 300
        facts = build_stock_research_facts(rows_to_bars_frame(r.rows), as_of=r.as_of)
        assert facts.bar_count == 300 and facts.ma[240] is not None and facts.close == r.latest.close

    def test_invalid_import_never_reaches_facts(self):
        r = _p(_csv(_with_col(_good_rows(), 5, "0")))
        assert r.state == STATE_INVALID_DATA
        with pytest.raises(ValueError):
            rows_to_bars_frame(r.rows)                                # rows=() → fail loud，不回空表

    def test_no_data_cannot_be_bridged(self):
        with pytest.raises(ValueError):
            rows_to_bars_frame(_p(_csv([], EN_HEADER)).rows)

    def test_c_contract_rejects_nothing_we_accept(self):
        # C 的 ≤0 價／high<low／負量檢查：本層 OK 的資料 C 不會 raise（對照 SF-1「本層 OK、下游 raise」）
        from src.compute.strategy.stock_research_facts import build_stock_research_facts
        r = _p(_csv([_r(v="0"), _r("2026-11-26", v="0")]))
        build_stock_research_facts(rows_to_bars_frame(r.rows), as_of=r.as_of)
