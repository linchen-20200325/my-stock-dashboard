"""tests/test_stock_latest_ohlcv.py — M2 個股最新日 OHLCV（L1 薄包裝）。

對應 src/data/stock/stock_latest_ohlcv.py:fetch_stock_latest_ohlcv。
⛔ 全離線：以假 `finmind_get` 注入；autouse fixture 封鎖 socket 與 requests，任何真連網即失敗。
"""
from __future__ import annotations

import ast
import dataclasses
import logging
import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.data.stock import stock_latest_ohlcv as mod
from src.data.stock.stock_latest_ohlcv import (
    ALL_STATES, DATASET_STOCK_PRICE, SOURCE_FINMIND_STOCK_PRICE,
    STATE_FETCH_FAILED, STATE_INVALID_DATA, STATE_INVALID_SYMBOL, STATE_NO_DATA, STATE_OK,
    OhlcvRow, StockLatestOhlcv, fetch_stock_latest_ohlcv,
)

MODULE_PATH = Path(mod.__file__)
TODAY = date(2026, 11, 27)
NOW = datetime(2026, 11, 27, 8, 30, tzinfo=timezone.utc)
SECRET = "TOKEN-SENTINEL-9f3a7c1d"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("真連網被封鎖：本測試檔限離線假回應")
    monkeypatch.setattr(socket.socket, "connect", _boom)
    import requests
    monkeypatch.setattr(requests.sessions.Session, "request", _boom)
    monkeypatch.setattr(requests, "get", _boom)


def _row(d="2026-11-25", o=100.0, h=105.0, lo=99.0, c=104.0, v=12_345_000, sid="0050"):
    return {"date": d, "stock_id": sid, "Trading_Volume": v, "Trading_money": 1,
            "open": o, "max": h, "min": lo, "close": c, "spread": 1.0, "Trading_turnover": 5}


def _df(*rows):
    return pd.DataFrame(list(rows))


class _Fake:
    """假 finmind_get：記錄呼叫，回傳指定 df，可選擇往 failed 追加或丟例外。"""

    def __init__(self, df=None, fail_msg=None, raises=None):
        self.df = df if df is not None else pd.DataFrame()
        self.fail_msg = fail_msg
        self.raises = raises
        self.calls = []

    def __call__(self, dataset, *, data_id=None, start_date=None, end_date=None,
                 token="", timeout=20, retries=1, failed=None):
        self.calls.append(dict(dataset=dataset, data_id=data_id, start_date=start_date, end_date=end_date,
                               token=token, timeout=timeout, retries=retries))
        if self.raises is not None:
            raise self.raises
        if self.fail_msg is not None and failed is not None:
            failed.append(self.fail_msg)
        return self.df


def _run(monkeypatch, fake, stock_id="0050", **kw):
    monkeypatch.setattr(mod, "finmind_get", fake)
    kw.setdefault("today", TODAY)
    kw.setdefault("now", NOW)
    return fetch_stock_latest_ohlcv(stock_id, **kw)


def _good_rows():
    return [_row("2026-11-24", 98, 101, 97, 100, 1000),
            _row("2026-11-25", 100, 105, 99, 104, 2000),
            _row("2026-11-26", 104, 106, 103, 105.5, 3000)]


# ───────────────────────── 正常回應 ─────────────────────────

class TestOk:
    def test_multi_rows_values_and_provenance(self, monkeypatch):
        f = _Fake(_df(*_good_rows()))
        r = _run(monkeypatch, f, token=SECRET)
        assert r.state == STATE_OK and r.error_code is None and r.reasons == ()
        assert r.symbol == "0050" and isinstance(r.symbol, str)
        assert r.n_rows == 3 and len(r.rows) == 3
        assert [x.date for x in r.rows] == [date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 26)]
        assert r.latest is r.rows[-1] and r.as_of == date(2026, 11, 26)
        assert (r.latest.open, r.latest.high, r.latest.low, r.latest.close) == (104.0, 106.0, 103.0, 105.5)
        assert r.latest.volume_shares == 3000.0          # 不換算（不 /1000）
        assert r.rows[1].close == 104.0                   # 原始價不調整
        assert r.source == SOURCE_FINMIND_STOCK_PRICE == "FinMind:TaiwanStockPrice:raw_http"
        assert r.authenticated is True
        assert r.fetched_at == NOW and r.fetched_at.tzinfo is not None
        assert r.fetched_at.utcoffset() == timedelta(0)
        assert isinstance(r.rows, tuple) and all(isinstance(x, OhlcvRow) for x in r.rows)

    def test_as_of_and_fetched_at_are_independent(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(*_good_rows())))
        assert r.as_of == date(2026, 11, 26) and r.fetched_at.date() == date(2026, 11, 27)
        assert r.authenticated is False

    def test_request_parameters(self, monkeypatch):
        f = _Fake(_df(*_good_rows()))
        _run(monkeypatch, f, lookback_days=30, timeout=7)
        c = f.calls[0]
        assert c["dataset"] == DATASET_STOCK_PRICE == "TaiwanStockPrice"
        assert c["start_date"] == "2026-10-28" and c["end_date"] == "2026-11-27"
        assert c["timeout"] == 7 and c["retries"] == mod.FETCH_ATTEMPTS == 1

    def test_default_now_is_utc_aware_and_today_is_taipei_day(self, monkeypatch):
        f = _Fake(_df(_row("2026-11-26")))
        monkeypatch.setattr(mod, "finmind_get", f)
        late_utc = datetime(2026, 11, 27, 17, 0, tzinfo=timezone.utc)   # 台北已是 11-28 01:00
        r = fetch_stock_latest_ohlcv("0050", now=late_utc)
        assert f.calls[0]["end_date"] == "2026-11-28"
        assert r.fetched_at == late_utc
        r2 = fetch_stock_latest_ohlcv("0050")                            # 預設現在
        assert r2.fetched_at.tzinfo is not None and r2.fetched_at.utcoffset() == timedelta(0)

    def test_non_utc_now_converted_to_utc(self, monkeypatch):
        tw = timezone(timedelta(hours=8))
        r = _run(monkeypatch, _Fake(_df(_row())), now=datetime(2026, 11, 27, 16, 30, tzinfo=tw))
        assert r.fetched_at == NOW and r.fetched_at.utcoffset() == timedelta(0)

    def test_today_row_allowed_not_future(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(_row("2026-11-27"))))
        assert r.state == STATE_OK and r.as_of == TODAY

    def test_numeric_strings_accepted_values_preserved(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(_row(o="100.5", h="101", lo="99", c="100", v="1000"))))
        assert r.state == STATE_OK and r.latest.open == 100.5 and r.latest.volume_shares == 1000.0

    def test_zero_volume_with_valid_quote_is_valid(self, monkeypatch):     # §4.6 跌停 0 vol：有 close 仍有效
        r = _run(monkeypatch, _Fake(_df(_row(v=0))))
        assert r.state == STATE_OK and r.latest.volume_shares == 0.0

    def test_extra_columns_ignored(self, monkeypatch):
        d = _df(_row())
        d["unexpected"] = "x"
        assert _run(monkeypatch, _Fake(d)).state == STATE_OK

    def test_no_stock_id_column_ok(self, monkeypatch):
        d = _df(_row()).drop(columns=["stock_id"])
        assert _run(monkeypatch, _Fake(d)).state == STATE_OK


# ───────────────────────── 代號 ─────────────────────────

class TestSymbol:
    def test_leading_zero_preserved_in_call(self, monkeypatch):
        f = _Fake(_df(_row()))
        r = _run(monkeypatch, f, "0050")
        assert f.calls[0]["data_id"] == "0050" and r.symbol == "0050"
        assert isinstance(f.calls[0]["data_id"], str)

    def test_whitespace_stripped(self, monkeypatch):
        f = _Fake(_df(_row()))
        r = _run(monkeypatch, f, " 0050 ")
        assert f.calls[0]["data_id"] == "0050" and r.symbol == "0050" and r.state == STATE_OK

    def test_lowercase_normalised_to_upper(self, monkeypatch):
        f = _Fake(_df(_row(sid="00631L")))
        r = _run(monkeypatch, f, "00631l")
        assert f.calls[0]["data_id"] == "00631L" and r.symbol == "00631L"

    @pytest.mark.parametrize("bad", [50, "50", "", "   ", None, b"0050", 50.0, "12345678", "1234567",
                                     "00 50", "0050.TW", "0050.TWO", "００５０", "AB12", "00-50",
                                     "0050\n0051", "00$0", ["0050"], "ı234"])
    def test_invalid_symbol_not_fetched(self, monkeypatch, bad):
        f = _Fake(_df(_row()))
        r = _run(monkeypatch, f, bad)
        assert r.state == STATE_INVALID_SYMBOL and r.symbol is None and r.error_code == "invalid_symbol"
        assert f.calls == [] and r.rows == () and r.latest is None and r.as_of is None and r.n_rows == 0

    def test_integer_50_not_zero_padded(self, monkeypatch):
        f = _Fake(_df(_row()))
        assert _run(monkeypatch, f, 50).state == STATE_INVALID_SYMBOL
        assert _run(monkeypatch, f, "50").state == STATE_INVALID_SYMBOL
        assert f.calls == []

    def test_invalid_symbol_not_echoed(self, monkeypatch):
        r = _run(monkeypatch, _Fake(), "evil<script>")
        assert "evil" not in repr(r)

    def test_stock_id_mismatch_in_response(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(_row(sid="2330"))))
        assert r.state == STATE_INVALID_DATA and mod.REASON_STOCK_ID_MISMATCH in r.reasons


# ───────────────────────── 空資料／失敗 ─────────────────────────

class TestNoDataAndFailure:
    def test_empty_df_is_no_data(self, monkeypatch):
        r = _run(monkeypatch, _Fake(pd.DataFrame()))
        assert r.state == STATE_NO_DATA and r.error_code == "no_data"
        assert r.rows == () and r.latest is None and r.as_of is None and r.n_rows == 0
        assert r.symbol == "0050" and r.source == SOURCE_FINMIND_STOCK_PRICE

    def test_transient_failure(self, monkeypatch):
        r = _run(monkeypatch, _Fake(fail_msg="TaiwanStockPrice: HTTP=429 status=429"), token=SECRET)
        assert r.state == STATE_FETCH_FAILED and r.error_code == "fetch_transient"
        assert r.rows == () and r.as_of is None
        assert "429" not in repr(r)

    def test_failed_wins_over_returned_rows(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(_row()), fail_msg="x"))
        assert r.state == STATE_FETCH_FAILED

    def test_exception_message_not_leaked(self, monkeypatch, caplog):
        caplog.set_level(logging.DEBUG)
        leak = f"https://api.finmindtrade.com/?token={SECRET} connection refused"
        r = _run(monkeypatch, _Fake(raises=RuntimeError(leak)), token=SECRET)
        assert r.state == STATE_FETCH_FAILED and r.error_code == "fetch_exception"
        for field in dataclasses.fields(r):
            assert SECRET not in repr(getattr(r, field.name))
        assert "connection refused" not in repr(r) and "api.finmindtrade" not in repr(r)
        assert SECRET not in caplog.text and "connection refused" not in caplog.text

    def test_non_dataframe_response(self, monkeypatch):
        r = _run(monkeypatch, _Fake(df=[{"date": "2026-11-25"}]))
        assert r.state == STATE_INVALID_DATA and r.reasons == (mod.REASON_RESPONSE_NOT_DATAFRAME,)

    def test_states_are_distinct_strings(self):
        assert len(set(ALL_STATES)) == len(ALL_STATES) == 5


# ───────────────────────── INVALID_DATA：欄位／日期／缺值／不變量 ─────────────────────────

def _assert_invalid(r, *codes):
    assert r.state == STATE_INVALID_DATA and r.error_code == "invalid_data"
    assert r.rows == () and r.latest is None and r.as_of is None and r.n_rows == 0
    for c in codes:
        assert c in r.reasons, (c, r.reasons)
    assert len(set(r.reasons)) == len(r.reasons)


class TestInvalidData:
    @pytest.mark.parametrize("col", ["date", "open", "max", "min", "close", "Trading_Volume"])
    def test_missing_column(self, monkeypatch, col):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row()).drop(columns=[col]))),
                        mod.reason_missing_column(col))

    def test_future_date(self, monkeypatch):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row("2026-11-26"), _row("2026-11-28")))),
                        mod.REASON_DATE_IN_FUTURE)

    def test_duplicate_date(self, monkeypatch):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row("2026-11-25"), _row("2026-11-25")))),
                        mod.REASON_DATE_DUPLICATE)

    def test_nonadjacent_duplicate_date(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(_row("2026-11-24"), _row("2026-11-25"), _row("2026-11-24"))))
        _assert_invalid(r, mod.REASON_DATE_DUPLICATE)

    def test_descending_dates_not_silently_sorted(self, monkeypatch):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row("2026-11-26"), _row("2026-11-25")))),
                        mod.REASON_DATE_NOT_ASCENDING)

    @pytest.mark.parametrize("bad", ["not-a-date", "2026-02-30", "20261125", "2026/11/25", "", None,
                                     "2026-11-25T00:00:00", 20261125, "２０２６-11-25"])
    def test_unparseable_date(self, monkeypatch, bad):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row(bad)))), mod.REASON_DATE_UNPARSEABLE)

    @pytest.mark.parametrize("field,col", [("open", "open"), ("high", "max"), ("low", "min"),
                                           ("close", "close"), ("volume_shares", "Trading_Volume")])
    @pytest.mark.parametrize("bad,kind", [(None, "missing"), (float("nan"), "missing"), ("", "missing"),
                                          ("  ", "missing"), (float("inf"), "not_finite"),
                                          (float("-inf"), "not_finite"), (10 ** 400, "not_finite"),
                                          ("abc", "not_numeric"), (True, "not_numeric"),
                                          ([1], "not_numeric")])
    def test_bad_values_never_become_zero(self, monkeypatch, field, col, bad, kind):
        row = _row()
        row[col] = bad
        r = _run(monkeypatch, _Fake(_df(row)))
        _assert_invalid(r, mod.reason_value(field, kind))

    def test_missing_value_in_object_column_mixed(self, monkeypatch):
        d = _df(_row("2026-11-24"), _row("2026-11-25"))
        d["close"] = [100.0, None]
        r = _run(monkeypatch, _Fake(d))
        _assert_invalid(r, "close_missing")
        assert 0.0 not in [getattr(x, "close", None) for x in r.rows]

    def test_high_below_low(self, monkeypatch):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row(o=100, h=98, lo=99, c=99)))), mod.REASON_HIGH_BELOW_LOW)

    def test_open_outside_range(self, monkeypatch):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row(o=110, h=105, lo=99, c=100)))),
                        mod.REASON_OPEN_OUTSIDE_RANGE)
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row(o=90, h=105, lo=99, c=100)))),
                        mod.REASON_OPEN_OUTSIDE_RANGE)

    def test_close_outside_range(self, monkeypatch):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row(o=100, h=105, lo=99, c=106)))),
                        mod.REASON_CLOSE_OUTSIDE_RANGE)
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row(o=100, h=105, lo=99, c=98)))),
                        mod.REASON_CLOSE_OUTSIDE_RANGE)

    @pytest.mark.parametrize("c", [0, -1.5])
    def test_close_not_positive(self, monkeypatch, c):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row(o=0, h=0, lo=-2, c=c)))), mod.REASON_CLOSE_NOT_POSITIVE)

    def test_negative_open_high_low(self, monkeypatch):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row(o=-1, h=105, lo=-2, c=100)))), mod.REASON_PRICE_NEGATIVE)

    def test_negative_volume(self, monkeypatch):
        _assert_invalid(_run(monkeypatch, _Fake(_df(_row(v=-1)))), mod.REASON_VOLUME_NEGATIVE)

    def test_one_bad_row_rejects_whole_series(self, monkeypatch):
        rows = _good_rows()
        rows[1]["close"] = None
        r = _run(monkeypatch, _Fake(_df(*rows)))
        _assert_invalid(r, "close_missing")

    def test_multiple_reasons_collected(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(_row("2026-11-28", v=-5))))
        _assert_invalid(r, mod.REASON_DATE_IN_FUTURE, mod.REASON_VOLUME_NEGATIVE)

    def test_reasons_are_fixed_codes_no_input_echo(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(_row(c="SECRET-LOOKING-VALUE"))), token=SECRET)
        assert r.state == STATE_INVALID_DATA
        assert "SECRET-LOOKING-VALUE" not in repr(r)


# ───────────────────────── 呼叫端錯誤 ─────────────────────────

class TestCallerErrors:
    @pytest.mark.parametrize("bad", [0, -1, mod.MAX_LOOKBACK_DAYS + 1, True, 1.5, "30", None])
    def test_bad_lookback(self, monkeypatch, bad):
        monkeypatch.setattr(mod, "finmind_get", _Fake())
        with pytest.raises(ValueError):
            fetch_stock_latest_ohlcv("0050", lookback_days=bad, today=TODAY, now=NOW)

    def test_naive_now_rejected(self, monkeypatch):
        monkeypatch.setattr(mod, "finmind_get", _Fake())
        with pytest.raises(ValueError):
            fetch_stock_latest_ohlcv("0050", today=TODAY, now=datetime(2026, 11, 27, 8, 0))

    def test_today_must_be_date(self, monkeypatch):
        monkeypatch.setattr(mod, "finmind_get", _Fake())
        with pytest.raises(ValueError):
            fetch_stock_latest_ohlcv("0050", today=datetime(2026, 11, 27), now=NOW)


# ───────────────────────── 安全／不落盤／不變性 ─────────────────────────

class TestSecurity:
    def test_token_not_in_any_output_surface(self, monkeypatch, capsys, caplog):
        caplog.set_level(logging.DEBUG)
        for fake in (_Fake(_df(*_good_rows())), _Fake(), _Fake(fail_msg="boom"),
                     _Fake(raises=RuntimeError(f"bad {SECRET}")),
                     _Fake(_df(_row(c=None))), _Fake(_df(_row("2026-11-28")))):
            r = _run(monkeypatch, fake, token=SECRET)
            assert r.authenticated is True
            assert SECRET not in repr(r) and SECRET not in str(r)
            for fld in dataclasses.fields(r):
                assert SECRET not in repr(getattr(r, fld.name))
            assert SECRET not in (r.error_code or "") and all(SECRET not in x for x in r.reasons)
        out = capsys.readouterr()
        assert SECRET not in out.out and SECRET not in out.err and SECRET not in caplog.text
        assert fake.calls[0]["token"] == SECRET        # 只傳給 finmind_get（其內部只放 header）

    def test_whitespace_token_is_unauthenticated(self, monkeypatch):
        f = _Fake(_df(_row()))
        r = _run(monkeypatch, f, token="   ")
        assert r.authenticated is False and f.calls[0]["token"] == ""

    def test_nonstring_token_ignored(self, monkeypatch):
        f = _Fake(_df(_row()))
        r = _run(monkeypatch, f, token=123)
        assert r.authenticated is False and f.calls[0]["token"] == ""

    def test_no_file_writes(self, monkeypatch, tmp_path):
        import builtins
        real_open = builtins.open

        def _guard(file, mode="r", *a, **k):
            if any(ch in str(mode) for ch in "wax+"):
                raise AssertionError("寫檔被封鎖")
            return real_open(file, mode, *a, **k)

        def _no_write(*a, **k):
            raise AssertionError("寫檔被封鎖")

        monkeypatch.setattr(builtins, "open", _guard)
        monkeypatch.setattr(Path, "write_text", _no_write)
        monkeypatch.setattr(Path, "write_bytes", _no_write)
        monkeypatch.setattr(pd.DataFrame, "to_parquet", _no_write)
        monkeypatch.setattr(pd.DataFrame, "to_csv", _no_write)
        monkeypatch.chdir(tmp_path)
        before = sorted(p.name for p in tmp_path.iterdir())
        assert _run(monkeypatch, _Fake(_df(*_good_rows()))).state == STATE_OK
        assert sorted(p.name for p in tmp_path.iterdir()) == before

    def test_no_cross_call_state(self, monkeypatch):
        a = _run(monkeypatch, _Fake(_df(_row("2026-11-20"))))
        b = _run(monkeypatch, _Fake(_df(_row("2026-11-25"))))
        assert a.as_of == date(2026, 11, 20) and b.as_of == date(2026, 11, 25)

    def test_frozen_dataclasses(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(_row())))
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.state = STATE_NO_DATA  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.latest.close = 1.0  # type: ignore[misc]
        assert isinstance(r, StockLatestOhlcv) and isinstance(r.rows, tuple)

    def test_no_zero_substitution_anywhere(self, monkeypatch):
        r = _run(monkeypatch, _Fake(_df(_row(o=None))))
        assert r.rows == () and r.latest is None


class TestStaticSource:
    SRC = MODULE_PATH.read_text(encoding="utf-8")
    TREE = ast.parse(SRC)

    def _imports(self):
        out = []
        for n in ast.walk(self.TREE):
            if isinstance(n, ast.Import):
                out += [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                out.append(n.module or "")
                out += [f"{n.module}.{a.name}" for a in n.names]
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

    def test_no_streamlit(self):
        assert not [i for i in self._imports() if i.split(".")[0] == "streamlit"]
        assert "st" not in self._names()

    def test_forbidden_identifiers(self):
        names = self._names()
        for banned in ("fillna", "bfill", "ffill", "_fetch_finmind_price_raw", "_bps_dl", "_fm_raw_headers",
                       "cache_data", "cache_resource", "session_state", "to_parquet", "to_csv", "to_pickle"):
            assert banned not in names, banned

    def test_no_verify_false(self):
        for n in ast.walk(self.TREE):
            if isinstance(n, ast.keyword) and n.arg == "verify":
                pytest.fail("verify= keyword must not appear")

    def test_no_private_data_loader_imports(self):
        assert not [i for i in self._imports() if "data_loader" in i or "proxy" in i]

    def test_no_int_cast_of_symbol(self):
        calls = [n for n in ast.walk(self.TREE) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "int"]
        assert calls == []

    def test_no_file_open_or_print(self):
        banned = {"open", "print"}
        calls = [n.func.id for n in ast.walk(self.TREE) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id in banned]
        assert calls == []

    def test_only_finmind_client_data_dependency(self):
        data_imports = [i for i in self._imports() if i.startswith("src.")]
        assert set(data_imports) == {"src.data.core.finmind_client",
                                     "src.data.core.finmind_client.finmind_get"}
