"""VN1-STORE Pre-Hardening 批（2026-10-20）— 網站 reader 真連線 smoke（只寫 log、⛔ 畫面零變化）守衛。

守：
1. `smoke_check`：每個讀取狀態（OK／EMPTY／NO_CREDENTIAL／NO_SHEET_ID／IDENTITY_MISMATCH／TAB_MISSING／
   SCHEMA_MISMATCH／API_ERROR／CONTENT_SUSPECT）照實回報；只回固定欄位（狀態、身分布林、表頭狀態、列數、
   最新列的日期／run id／sha256、比較狀態）—— ⛔ 不帶儲存格值、Sheet ID、例外原文。
2. 繞過快取：`read_history` 已快取成功結果後，smoke 仍真的再讀一次（量的是「現在連得上嗎」）。
3. `run_smoke_if_flagged`：secrets 頂層旗標**恰好** `True` 才跑；沒設／`"true"` 字串／1／False／secrets 讀不到 ⇒
   零 client、零輸出；每個行程只跑一次；輸出恰好一行固定格式；smoke 自己的程式 bug ⇒ 只印類別名、⛔ 不往上拋。
⛔ 不連網：Google 依賴全以假物件替換（沿用 `tests/test_vn1_production_wiring.py` 的替身）。
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from shared import risk_cap_history_policy as P
from src.data.risk_cap import history as L1H
from src.services import risk_cap_history_reader_service as R
from tests.test_batch_z64 import NOW
from tests.test_vn1_production_wiring import (
    _FAKE_KEY,
    LEAK,
    SID,
    _factory_for,
    _FakeResponse,
    _FakeWS,
    _info,
    _secrets,
    _values,
)
from tests.test_vn1_store_poc import _invalid, _row


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    R.clear_read_cache()
    monkeypatch.setattr(R, "_SMOKE_DONE", False)
    yield
    R.clear_read_cache()


def _counting(ws=None, **kw):
    calls: list[dict] = []
    return _factory_for(ws, calls=calls, **kw), calls


def _smoke(ws=None, *, secrets=None, now=NOW, **kw):
    f, calls = _counting(ws, **kw)
    return R.smoke_check(now, secrets=_secrets() if secrets is None else secrets, client_factory=f), calls


def _no_leak(text: str) -> None:
    for bad in (SID, LEAK, _FAKE_KEY, "private_key", "Traceback"):
        assert bad not in text, bad


class TestSmokeCheck:
    def test_ok_latest_row_fields(self):
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_RUN_ID: "7", P.COL_EXPOSURE_LIMIT_PCT: "55"})
        last = _row(**{P.COL_RUN_ID: "8"})
        res, calls = _smoke(_FakeWS(_values(prev, last)))
        assert len(calls) == 1
        assert (res.read_status, res.identity_ok, res.header_state, res.data_rows) == (
            P.READ_STATUS_OK, True, P.HEADER_STATE_MATCH, 2)
        assert res.latest_record_date == "2026-10-14" and res.latest_run_id == "8"
        assert res.latest_row_sha256 == L1H.record_sha256(last)
        assert res.compare_status in P.COMPARE_STATUSES

    @pytest.mark.parametrize("values,state", [([], P.HEADER_STATE_ABSENT),
                                              ([list(P.HISTORY_COLUMNS)], P.HEADER_STATE_MATCH)])
    def test_empty(self, values, state):
        res, _ = _smoke(_FakeWS(values))
        assert (res.read_status, res.header_state, res.data_rows, res.latest_run_id, res.compare_status) == (
            P.READ_STATUS_EMPTY, state, 0, "", P.COMPARE_START_RECORDING)

    def test_no_credential_no_client(self):
        res, calls = _smoke(_FakeWS([]), secrets={P.READER_SHEET_ID_SECRET_KEY: SID})
        assert res.read_status == P.READ_STATUS_NO_CREDENTIAL and res.identity_ok is None and not calls
        assert res.header_state == P.HEADER_STATE_NOT_READ and res.data_rows is None

    def test_no_sheet_id(self):
        res, calls = _smoke(_FakeWS([]), secrets={P.READER_SECRETS_TABLE: _info()})
        assert res.read_status == P.READ_STATUS_NO_SHEET_ID and not calls

    def test_identity_mismatch(self):
        res, calls = _smoke(_FakeWS([]), secrets=_secrets(**{P.READER_SECRETS_TABLE: _info(
            client_email=P.WRITER_SA_EMAIL)}))
        assert res.read_status == P.READ_STATUS_IDENTITY_MISMATCH and res.identity_ok is False and not calls

    def test_tab_missing(self):
        import gspread.exceptions as gse
        res, _ = _smoke(None, tab_exc=gse.WorksheetNotFound(LEAK))
        assert res.read_status == P.READ_STATUS_TAB_MISSING and res.identity_ok is True
        assert res.header_state == P.HEADER_STATE_NOT_READ

    def test_schema_mismatch_header(self):
        res, _ = _smoke(_FakeWS([["foo", "bar"], ["1", "2"]]))
        assert (res.read_status, res.header_state, res.data_rows) == (
            P.READ_STATUS_SCHEMA_MISMATCH, P.HEADER_STATE_MISMATCH, 1)

    def test_schema_mismatch_long_row_header_still_match(self):
        res, _ = _smoke(_FakeWS([list(P.HISTORY_COLUMNS), [""] * (len(P.HISTORY_COLUMNS) + 1)]))
        assert (res.read_status, res.header_state) == (P.READ_STATUS_SCHEMA_MISMATCH, P.HEADER_STATE_MATCH)

    def test_api_error(self):
        import gspread.exceptions as gse
        res, _ = _smoke(_FakeWS([], exc=gse.APIError(_FakeResponse())))
        assert res.read_status == P.READ_STATUS_API_ERROR
        _no_leak(res.log_line())

    def test_content_suspect(self):
        res, _ = _smoke(_FakeWS(_values(_row(**{P.COL_EXPOSURE_LIMIT_PCT: ""}))))
        assert res.read_status == P.READ_STATUS_CONTENT_SUSPECT and res.data_rows == 1

    def test_expected_date_is_today_taipei(self):
        res, _ = _smoke(_FakeWS(_values(_invalid())), now=NOW)
        assert res.compare_status == P.COMPARE_CURRENT_NOT_VALID
        res2, _ = _smoke(_FakeWS(_values(_invalid())), now=NOW + timedelta(days=1))
        assert res2.compare_status == P.COMPARE_STALE

    def test_programming_error_propagates_from_smoke_check(self):
        with pytest.raises(KeyError):
            _smoke(_FakeWS([], exc=KeyError("bug")))

    def test_bypasses_cache(self):
        ws = _FakeWS(_values(_row()))
        f, calls = _counting(ws)
        assert R.read_history(expected_date="2026-10-14", now=NOW, secrets=_secrets(),
                              client_factory=f).status == P.READ_STATUS_OK
        R.read_history(expected_date="2026-10-14", now=NOW, secrets=_secrets(), client_factory=f)
        cached = ws.reads
        R.smoke_check(NOW, secrets=_secrets(), client_factory=f)
        assert ws.reads == cached + 1 and len(calls) == cached + 1

    def test_result_has_only_documented_fields(self):
        import dataclasses
        assert [f.name for f in dataclasses.fields(R.SmokeResult)] == [
            "read_status", "identity_ok", "header_state", "data_rows", "latest_record_date", "latest_run_id",
            "latest_row_sha256", "compare_status"]


class TestRunSmokeIfFlagged:
    @pytest.mark.parametrize("flag", [None, "true", "True", 1, False, {"x": 1}])
    def test_not_exactly_true_zero_calls(self, flag, capsys):
        sec = _secrets()
        if flag is not None:
            sec[P.READER_SMOKE_SECRET_KEY] = flag
        f, calls = _counting(_FakeWS(_values(_row())))
        assert R.run_smoke_if_flagged(now=NOW, secrets=sec, client_factory=f) is None
        assert not calls and capsys.readouterr().out == ""

    def test_secrets_unreadable_zero_calls(self, capsys):
        class _Boom:
            def get(self, key):
                raise FileNotFoundError("no secrets.toml")
        f, calls = _counting(_FakeWS([]))
        assert R.run_smoke_if_flagged(now=NOW, secrets=_Boom(), client_factory=f) is None
        assert not calls and capsys.readouterr().out == ""

    def test_st_secrets_attribute_raising_zero_calls(self, monkeypatch, capsys):
        """回修第 1 輪（2026-10-20）：連取 `st.secrets` 屬性本身拋例外也包住 ⇒ 旗標沒開。"""
        class _ST:
            @property
            def secrets(self):
                raise RuntimeError("secrets unavailable")
        monkeypatch.setattr(R, "st", _ST())
        monkeypatch.setattr(L1H, "build_reader_client", lambda *a, **k: pytest.fail("旗標沒開不得建 client"))
        assert R.run_smoke_if_flagged(now=NOW) is None
        assert capsys.readouterr().out == ""

    @pytest.mark.parametrize("exc", [KeyboardInterrupt, SystemExit])
    def test_base_exceptions_not_swallowed(self, exc):
        """只接 `Exception`：KeyboardInterrupt／SystemExit 照常往上（行程該停就停）。"""
        sec = {**_secrets(), P.READER_SMOKE_SECRET_KEY: True}
        f, _ = _counting(_FakeWS([], exc=exc()))
        with pytest.raises(exc):
            R.run_smoke_if_flagged(now=NOW, secrets=sec, client_factory=f)

    def test_flag_true_runs_once_per_process(self, capsys):
        sec = {**_secrets(), P.READER_SMOKE_SECRET_KEY: True}
        f, calls = _counting(_FakeWS(_values(_row())))
        res = R.run_smoke_if_flagged(now=NOW, secrets=sec, client_factory=f)
        assert res is not None and res.read_status == P.READ_STATUS_OK and len(calls) == 1
        assert R.run_smoke_if_flagged(now=NOW, secrets=sec, client_factory=f) is None
        assert len(calls) == 1
        lines = [ln for ln in capsys.readouterr().out.splitlines() if ln]
        assert len(lines) == 1 and lines[0].startswith(P.READER_SMOKE_LOG_PREFIX + " read_status=OK ")
        for k in ("identity_ok=True", "header_state=MATCH", "data_rows=1", "latest_record_date=2026-10-14",
                  "latest_run_id=1", f"latest_row_sha256={L1H.record_sha256(_row())}", "compare_status="):
            assert k in lines[0], k
        _no_leak(lines[0])

    def test_failure_status_logged_not_raised(self, capsys):
        import gspread.exceptions as gse
        sec = {**_secrets(), P.READER_SMOKE_SECRET_KEY: True}
        f, _ = _counting(_FakeWS([], exc=gse.APIError(_FakeResponse())))
        res = R.run_smoke_if_flagged(now=NOW, secrets=sec, client_factory=f)
        assert res.read_status == P.READ_STATUS_API_ERROR
        out = capsys.readouterr().out
        smoke = [ln for ln in out.splitlines() if ln.startswith(P.READER_SMOKE_LOG_PREFIX)]
        assert len(smoke) == 1 and "read_status=API_ERROR" in smoke[0] and "header_state=NOT_READ" in smoke[0]
        _no_leak(out)

    def test_programming_bug_logged_class_only_not_raised(self, capsys):
        sec = {**_secrets(), P.READER_SMOKE_SECRET_KEY: True}
        f, _ = _counting(_FakeWS([], exc=KeyError(LEAK)))
        assert R.run_smoke_if_flagged(now=NOW, secrets=sec, client_factory=f) is None
        out = capsys.readouterr().out
        assert out.strip() == f"{P.READER_SMOKE_LOG_PREFIX} read_status={P.READER_SMOKE_STATUS_BUG} error_type=KeyError"
        assert R.run_smoke_if_flagged(now=NOW, secrets=sec, client_factory=f) is None    # 仍只跑一次
        assert capsys.readouterr().out == ""

    def test_default_secrets_source_is_st_secrets(self, monkeypatch):
        """不注入 ⇒ 讀 `st.secrets`（旗標沒開 ⇒ 不呼叫 L1）。"""
        monkeypatch.setattr(R.st, "secrets", {}, raising=False)
        monkeypatch.setattr(L1H, "build_reader_client", lambda *a, **k: pytest.fail("旗標沒開不得建 client"))
        assert R.run_smoke_if_flagged() is None

    def test_flag_key_constant(self):
        assert P.READER_SMOKE_SECRET_KEY == "risk_cap_history_smoke"
        assert P.READER_SMOKE_SECRET_KEY not in (P.READER_SECRETS_TABLE, P.READER_SHEET_ID_SECRET_KEY)
