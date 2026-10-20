"""VN1-STORE Pre-Hardening 批（2026-10-20；production 寫入**仍未核准**）— 首次寫入的寫前檢查／寫後驗證守衛。

守：
1. L1 純函式 `record_sha256`／`precheck_target`／`verify_written`（`InMemoryWorksheet` 的值）：空表、只有表頭、表頭錯、
   同鍵已存在、權限驗證殘留、日期不是今天、規則／schema 版本不是現行、重複表頭、超長列；讀回 0／1／2 列相符、欄位不同。
2. 腳本：`--precheck`／`--verify-written`／`--write` 一律**閘門第一**（旗標 False ⇒ exit 2，連 client 都不建）；
   閘門之後的流程（`_write_record`）以假工作表直接測：寫前檢查 → 寫入 → 讀回驗證，任何失敗 exit 非 0、⛔ 不刪任何列。
3. 靜態：腳本與 L1 沒有任何刪除／清空 API 呼叫；workflow 內 `--write`／`--precheck`／`--verify-written` 步驟都在閘門之後。
4. 突變自驗：拔掉殘留檢查、同鍵檢查、多列相符檢查、逐欄比對 ⇒ 轉紅。
⛔ 本檔**不**修改、也不繞過 `PRODUCTION_WRITE_APPROVED`（連 monkeypatch 都沒有；閘門函式本身也不替換）——
   閘門之後的函式一律直接呼叫測試（同 `tests/test_vn1_production_wiring.py` 慣例）。不連網。
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from shared import risk_cap_history_policy as P
from src.data.risk_cap import history as L1H
from tests.test_p01_macro_refresh import _mutated_module
from tests.test_vn1_store_poc import _invalid, _row
from tests.test_vn1_wif_auth_only import _parse

REPO = Path(__file__).resolve().parents[1]
L1_REL = "src/data/risk_cap/history.py"
POC_SCRIPT_REL = "scripts/risk_cap_history_poc.py"
WORKFLOW_REL = ".github/workflows/risk_cap_history_poc.yml"
GATE_RUN = "python3 scripts/risk_cap_history_poc.py --check-write-gate"
#: `_row()` 的 record_date（2026-10-14）在台北時區的「今天」。
TODAY = "2026-10-14"
#: 台北 2026-10-14 10:00（＝ UTC 02:00）。
NOW_UTC = datetime(2026, 10, 14, 2, 0, tzinfo=timezone.utc)
#: 測試用假 Sheet ID（⛔ 不是任何真實 Sheet）。
SID = "TEST_SYSTEM_SHEET_ID"


def _vals(*rows, header=True):
    out = [list(P.HISTORY_COLUMNS)] if header else []
    return out + [[r[c] for c in P.HISTORY_COLUMNS] for r in rows]


def _load_poc():
    spec = importlib.util.spec_from_file_location("_poc_script_fwv", REPO / POC_SCRIPT_REL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ══════════════════════════════════════════════════════════════════════════
# 1. record_sha256
# ══════════════════════════════════════════════════════════════════════════
class TestRecordSha256:
    def test_deterministic_and_field_sensitive(self):
        r = _row()
        assert L1H.record_sha256(r) == L1H.record_sha256(dict(reversed(list(r.items()))))   # 只依 schema 欄序
        assert len(L1H.record_sha256(r)) == 64
        for c in P.HISTORY_COLUMNS:
            assert L1H.record_sha256(_row(**{c: r[c] + "x"})) != L1H.record_sha256(r), c

    def test_rejects_invalid_row(self):
        bad = _row()
        bad.pop(P.COL_RUN_ID)
        with pytest.raises(L1H.HistoryRowInvalid):
            L1H.record_sha256(bad)


# ══════════════════════════════════════════════════════════════════════════
# 2. precheck_target
# ══════════════════════════════════════════════════════════════════════════
class TestPrecheck:
    def test_empty_sheet_ok(self):
        res = L1H.precheck_target([], _row(), today_tw=TODAY)
        assert res.ok and res.header_state == P.HEADER_STATE_ABSENT and res.data_rows == 0

    def test_header_only_ok(self):
        res = L1H.precheck_target(_vals(), _row(), today_tw=TODAY)
        assert res.ok and res.header_state == P.HEADER_STATE_MATCH and res.data_rows == 0

    def test_other_day_rows_ok(self):
        res = L1H.precheck_target(_vals(_row(**{P.COL_RECORD_DATE: "2026-10-13"})), _row(), today_tw=TODAY)
        assert res.ok and res.data_rows == 1

    @pytest.mark.parametrize("header", [
        ["foo"], list(P.HISTORY_COLUMNS)[::-1], list(P.HISTORY_COLUMNS) + ["extra"], list(P.HISTORY_COLUMNS)[:-1]])
    def test_wrong_header(self, header):
        res = L1H.precheck_target([header], _row(), today_tw=TODAY)
        assert res.failures == (P.PRECHECK_FAIL_HEADER_MISMATCH,) and res.header_state == P.HEADER_STATE_MISMATCH

    @pytest.mark.parametrize("existing", [_row(), _invalid(), _row(**{P.COL_RUN_ID: "99"})])
    def test_existing_key_any_status(self, existing):
        res = L1H.precheck_target(_vals(existing), _row(), today_tw=TODAY)
        assert res.failures == (P.PRECHECK_FAIL_KEY_EXISTS,)

    def test_same_date_other_ruleset_not_same_key(self):
        res = L1H.precheck_target(_vals(_row(**{P.COL_RULESET_VERSION: "risk_cap.v1"})), _row(), today_tw=TODAY)
        assert res.ok

    @pytest.mark.parametrize("values", [
        [["PERMISSION_TEST", "123", "2026-10-20T00:00:00+00:00", "note"]],                 # 空表時 P1 測試列落在第 1 列
        _vals() + [["PERMISSION_TEST", "123", "2026-10-20T00:00:00+00:00", "note"]],
        _vals() + [["PERMISSION_TEST_R3_SHOULD_FAIL", "123", "x", "y"]],
        _vals(_row(**{P.COL_REASON_DETAIL: "PERMISSION_TEST leftover"})),
    ])
    def test_permission_test_residue(self, values):
        res = L1H.precheck_target(values, _row(), today_tw=TODAY)
        assert P.PRECHECK_FAIL_PERMISSION_TEST_RESIDUE in res.failures and not res.ok

    def test_markers_match_permission_script(self):
        """L0 前綴與權限驗證腳本（本批不動）的兩個標記一致。"""
        spec = importlib.util.spec_from_file_location("_perm_fwv", REPO / "scripts/risk_cap_permission_test.py")
        perm = importlib.util.module_from_spec(spec)
        sys.modules["_perm_fwv"] = perm
        try:
            spec.loader.exec_module(perm)
        finally:
            sys.modules.pop("_perm_fwv", None)
        assert perm.P1_MARKER.startswith(P.PERMISSION_TEST_MARKER_PREFIX)
        assert perm.R3_MARKER.startswith(P.PERMISSION_TEST_MARKER_PREFIX)

    def test_date_not_today(self):
        res = L1H.precheck_target(_vals(), _row(), today_tw="2026-10-15")
        assert res.failures == (P.PRECHECK_FAIL_DATE_NOT_TODAY,)

    def test_versions_not_current(self):
        res = L1H.precheck_target(_vals(), _row(**{P.COL_RULESET_VERSION: "risk_cap.v1",
                                                   P.COL_SCHEMA_VERSION: "risk_cap_history.v0"}), today_tw=TODAY)
        assert res.failures == (P.PRECHECK_FAIL_RULESET_VERSION, P.PRECHECK_FAIL_SCHEMA_VERSION)

    def test_duplicate_header_and_long_row(self):
        values = _vals(_row(**{P.COL_RECORD_DATE: "2026-10-13"})) + [list(P.HISTORY_COLUMNS)] \
            + [[""] * (len(P.HISTORY_COLUMNS) + 1)]
        res = L1H.precheck_target(values, _row(), today_tw=TODAY)
        assert res.failures == (P.PRECHECK_FAIL_DUPLICATE_HEADER, P.PRECHECK_FAIL_ROW_TOO_LONG)

    def test_all_failures_listed_not_short_circuit(self):
        values = _vals(_row()) + [["PERMISSION_TEST", "1"]]
        res = L1H.precheck_target(values, _row(**{P.COL_SCHEMA_VERSION: "x"}), today_tw="2026-10-15")
        assert set(res.failures) == {P.PRECHECK_FAIL_PERMISSION_TEST_RESIDUE, P.PRECHECK_FAIL_KEY_EXISTS,
                                     P.PRECHECK_FAIL_DATE_NOT_TODAY, P.PRECHECK_FAIL_SCHEMA_VERSION}

    def test_invalid_record(self):
        bad = _row()
        bad[P.COL_RUN_ID] = 1
        assert L1H.precheck_target([], bad, today_tw=TODAY).failures == (P.PRECHECK_FAIL_ROW_INVALID,)

    def test_does_not_mutate_input(self):
        values = _vals(_row(**{P.COL_RECORD_DATE: "2026-10-13"}))
        snap = json.dumps(values)
        L1H.precheck_target(values, _row(), today_tw=TODAY)
        assert json.dumps(values) == snap


# ══════════════════════════════════════════════════════════════════════════
# 3. verify_written
# ══════════════════════════════════════════════════════════════════════════
class TestVerify:
    def test_exactly_one_match_ok(self):
        r = _row()
        res = L1H.verify_written(_vals(_row(**{P.COL_RECORD_DATE: "2026-10-13"}), r), r, "1")
        assert res.ok and res.matches == 1 and res.readback_sha256 == L1H.record_sha256(r)

    def test_trailing_blank_cells_padded(self):
        r = _row()                                       # 最後一欄 schema_version 非空；把 git_sha 留空測尾端省略
        vals = _vals()
        vals.append([r[c] for c in P.HISTORY_COLUMNS])
        assert L1H.verify_written(vals, r, "1").ok

    @pytest.mark.parametrize("values", [[], [["foo"]], [[""] * 3, list(P.HISTORY_COLUMNS)]])
    def test_header_missing_or_wrong_position(self, values):
        assert L1H.verify_written(values + _vals(_row(), header=False), _row(), "1").failures \
            == (P.VERIFY_FAIL_HEADER_MISMATCH,)

    def test_zero_matches(self):
        res = L1H.verify_written(_vals(_row(**{P.COL_RUN_ID: "2"})), _row(), "1")
        assert res.failures == (P.VERIFY_FAIL_NO_MATCH,) and res.matches == 0 and res.readback_sha256 == ""

    def test_header_only_zero_matches(self):
        assert L1H.verify_written(_vals(), _row(), "1").failures == (P.VERIFY_FAIL_NO_MATCH,)

    def test_two_matches(self):
        res = L1H.verify_written(_vals(_row(), _row()), _row(), "1")
        assert res.failures == (P.VERIFY_FAIL_MULTIPLE_MATCHES,) and res.matches == 2 and res.readback_sha256 == ""

    def test_field_mismatch_lists_columns_only(self):
        written = _row(**{P.COL_EXPOSURE_LIMIT_PCT: "61", P.COL_GIT_SHA: "abc"})
        res = L1H.verify_written(_vals(written), _row(), "1")
        assert res.failures == (P.VERIFY_FAIL_FIELD_MISMATCH,)
        assert res.mismatched_columns == (P.COL_EXPOSURE_LIMIT_PCT, P.COL_GIT_SHA)
        assert "61" not in repr(res.failures) + repr(res.mismatched_columns)

    def test_duplicate_header(self):
        res = L1H.verify_written(_vals(_row()) + [list(P.HISTORY_COLUMNS)], _row(), "1")
        assert res.failures == (P.VERIFY_FAIL_DUPLICATE_HEADER,) and res.matches == 1


# ══════════════════════════════════════════════════════════════════════════
# 4. 腳本：閘門第一；閘門之後的流程直接測
# ══════════════════════════════════════════════════════════════════════════
class TestScriptGate:
    @pytest.mark.parametrize("flags", [["--precheck"], ["--verify-written"], ["--write"],
                                       ["--precheck", "--write"]])
    def test_gate_refuses(self, flags, tmp_path, monkeypatch, capsys):
        mod = _load_poc()
        rec = tmp_path / "rec.json"
        rec.write_text(json.dumps({"record": _row()}), encoding="utf-8")
        monkeypatch.setattr(mod, "_open_target", lambda *a, **k: pytest.fail("閘門未過不得開 Sheet"))
        monkeypatch.setattr(L1H, "build_writer_client", lambda *a, **k: pytest.fail("閘門未過不得建 client"))
        monkeypatch.setenv(P.WRITE_ENABLE_ENV_VAR, "1")
        monkeypatch.setenv(P.HISTORY_SHEET_ID_ENV_VAR, SID)
        assert mod.main([*flags, "--record", str(rec)]) == 2
        out = capsys.readouterr().out
        assert "尚未核准" in out and SID not in out

    def test_flows_only_dispatched_after_gate(self):
        """AST：三個 Sheet 流程函式只在 `main` 的 `sheet_flows` 清單出現；呼叫點在閘門之後；其他函式不呼叫它們。"""
        tree = ast.parse((REPO / POC_SCRIPT_REL).read_text(encoding="utf-8"))
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        flows = {"_write_record", "_precheck_only", "_verify_only"}
        for name, fn in fns.items():
            refs = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id in flows}
            assert not refs or name == "main", (name, refs)
        main = fns["main"]
        gate = min(n.lineno for n in ast.walk(main) if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "load_writer_credentials_or_refuse")
        dispatch = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Subscript)]
        assert len(dispatch) == 1 and gate < dispatch[0].lineno
        assert "args.record" in ast.unparse(dispatch[0])

    def test_write_flow_order_static(self):
        fn = next(n for n in ast.parse((REPO / POC_SCRIPT_REL).read_text(encoding="utf-8")).body
                  if isinstance(n, ast.FunctionDef) and n.name == "_write_record")
        first = {}
        for n in ast.walk(fn):
            if isinstance(n, ast.Name):
                first[n.id] = min(first.get(n.id, 10 ** 9), n.lineno)
        assert first["_run_precheck"] < first["upsert_record"] < first["_run_verify"]

    def test_no_delete_api_anywhere_on_write_path(self):
        for rel in (L1_REL, POC_SCRIPT_REL):
            code = ast.unparse(ast.parse((REPO / rel).read_text(encoding="utf-8")))
            for bad in ("delete_row", "delete_rows", "batch_clear", ".clear(", "values_clear", "deleteDimension",
                        "del_worksheet", "update_cell", ".update("):
                assert bad not in code, (rel, bad)


class _Target:
    """閘門之後 `_open_target` 的替身：同一張記憶體表；讀寫 scope 分開記錄。"""

    def __init__(self, rows=(), *, fail_on=None):
        self.ws = L1H.InMemoryWorksheet(rows)
        self.scopes: list[tuple[str, ...]] = []
        self.fail_on = fail_on

    def __call__(self, scopes):
        self.scopes.append(tuple(scopes))
        if self.fail_on is not None and tuple(scopes) == self.fail_on:
            raise L1H.HistoryApiError("TransportError")
        return self.ws


class TestWriteFlowAfterGate:
    @pytest.fixture
    def poc(self, monkeypatch, tmp_path):
        mod = _load_poc()
        monkeypatch.setattr(mod, "_now_utc", lambda: NOW_UTC)
        monkeypatch.setenv("GITHUB_RUN_ID", "1")
        rec = tmp_path / "rec.json"

        def _run(target, record=None, fn="_write_record"):
            rec.write_text(json.dumps({"record": record or _row()}), encoding="utf-8")
            monkeypatch.setattr(mod, "_open_target", target)
            return getattr(mod, fn)(str(rec))
        return _run

    def test_happy_path_readonly_then_write_then_readonly(self, poc, capsys):
        t = _Target()
        assert poc(t) == 0
        assert t.scopes == [P.READER_SCOPES, P.WRITER_SCOPES, P.READER_SCOPES]
        recs = L1H.rows_as_records(t.ws.get_all_values())
        assert recs == [_row()] and t.ws.append_calls == 2                         # 表頭＋一列
        out = capsys.readouterr().out
        pre = json.loads(out.split("precheck: ")[1].splitlines()[0])
        ver = json.loads(out.split("verify: ")[1].splitlines()[0])
        assert pre["ok"] and ver["ok"] and ver["readback_sha256"] == ver["record_sha256"] == L1H.record_sha256(_row())
        assert SID not in out and _row()[P.COL_INPUT_ASOF] not in out          # ⛔ 不印值

    def test_precheck_fail_writes_nothing(self, poc):
        t = _Target(_vals(_invalid()))
        before = t.ws.get_all_values()
        assert poc(t) == 4
        assert t.ws.get_all_values() == before and t.scopes == [P.READER_SCOPES]

    def test_run_id_mismatch_refused_before_write(self, poc, monkeypatch, capsys):
        monkeypatch.setenv("GITHUB_RUN_ID", "2")
        t = _Target()
        assert poc(t) == 4 and t.ws.append_calls == 0
        assert P.PRECHECK_FAIL_RUN_ID_MISMATCH in capsys.readouterr().out

    def test_date_rollover_refused(self, poc, monkeypatch):
        monkeypatch.setenv("GITHUB_RUN_ID", "1")
        t = _Target()
        assert poc(t, _row(**{P.COL_RECORD_DATE: "2026-10-13"})) == 4 and t.ws.append_calls == 0

    def test_precheck_io_failure_exit_1(self, poc):
        t = _Target(fail_on=P.READER_SCOPES)
        assert poc(t) == 1 and t.ws.append_calls == 0

    def test_write_io_failure_exit_1_and_readback_attempted(self, poc, capsys):
        t = _Target(fail_on=P.WRITER_SCOPES)
        assert poc(t) == 1
        assert t.scopes == [P.READER_SCOPES, P.WRITER_SCOPES, P.READER_SCOPES]
        assert "verify: " in capsys.readouterr().out

    def test_verify_fail_exit_5_no_delete(self, poc, monkeypatch):
        t = _Target()
        orig = L1H.InMemoryWorksheet.append_row

        def _corrupt(self, values):                 # 模擬 Sheets 端把某一欄存成別的字串
            if values and values[0] != P.HISTORY_COLUMNS[0]:
                values = list(values)
                values[P.HISTORY_COLUMNS.index(P.COL_EXPOSURE_LIMIT_PCT)] = "60.0"
            orig(self, values)
        monkeypatch.setattr(L1H.InMemoryWorksheet, "append_row", _corrupt)
        assert poc(t) == 5
        assert len(t.ws.get_all_values()) == 2                                       # ⛔ 寫進去的那列沒被刪

    def test_precheck_only_and_verify_only(self, poc):
        t = _Target()
        assert poc(t, fn="_precheck_only") == 0 and t.ws.append_calls == 0
        assert poc(t, fn="_verify_only") == 5                                         # 還沒寫 ⇒ 0 列相符
        t2 = _Target(_vals(_row()))
        assert poc(t2, fn="_precheck_only") == 4
        assert poc(t2, fn="_verify_only") == 0 and t2.ws.append_calls == 0

    def test_verify_only_needs_run_id(self, poc, monkeypatch):
        monkeypatch.delenv("GITHUB_RUN_ID")
        assert poc(_Target(_vals(_row())), fn="_verify_only") == 2


# ══════════════════════════════════════════════════════════════════════════
# 5. workflow：寫前檢查／寫後驗證都在閘門之後
# ══════════════════════════════════════════════════════════════════════════
def assert_sheet_steps_after_gate(text: str) -> None:
    d = _parse(text)
    steps = d["jobs"]["production_write"]["steps"]
    i_gate = [i for i, s in enumerate(steps) if s.get("run") == GATE_RUN]
    assert len(i_gate) == 1
    sheet = [i for i, s in enumerate(steps)
             if any(f in s.get("run", "") for f in ("--write", "--precheck", "--verify-written"))]
    assert sheet and all(i > i_gate[0] for i in sheet), (i_gate, sheet)
    for job, j in d["jobs"].items():
        if job == "production_write":
            continue
        for s in j["steps"]:
            assert not any(f in s.get("run", "") for f in ("--write", "--precheck", "--verify-written")), job


class TestWorkflowOrder:
    def test_real_workflow(self):
        assert_sheet_steps_after_gate((REPO / WORKFLOW_REL).read_text(encoding="utf-8"))

    def test_verify_step_before_gate_turns_red(self):
        text = (REPO / WORKFLOW_REL).read_text(encoding="utf-8")
        gate = f"        run: {GATE_RUN}\n"
        assert text.count(gate) == 1
        mut = text.replace(gate, "        run: python scripts/risk_cap_history_poc.py --verify-written --record x\n"
                                 "\n      - name: gate\n" + gate)
        with pytest.raises(AssertionError):
            assert_sheet_steps_after_gate(mut)


# ══════════════════════════════════════════════════════════════════════════
# 6. 突變自驗
# ══════════════════════════════════════════════════════════════════════════
class TestMutations:
    def test_without_residue_check(self):
        mut = _mutated_module(L1_REL, ("    if _has_permission_test_residue(values):\n", "    if False:\n"))
        values = _vals() + [["PERMISSION_TEST", "1"]]
        assert mut.precheck_target(values, _row(), today_tw=TODAY).ok
        assert not L1H.precheck_target(values, _row(), today_tw=TODAY).ok

    def test_without_key_check(self):
        mut = _mutated_module(L1_REL, (
            "    if state == HEADER_STATE_MATCH and any(_key(_padded(r)) == _key(record) for r in values[1:]):\n",
            "    if False:\n"))
        assert mut.precheck_target(_vals(_invalid()), _row(), today_tw=TODAY).ok
        assert not L1H.precheck_target(_vals(_invalid()), _row(), today_tw=TODAY).ok

    def test_without_multiple_match_check(self):
        mut = _mutated_module(L1_REL, ("    if len(hits) > 1:\n", "    if False:\n"))
        assert mut.verify_written(_vals(_row(), _row()), _row(), "1").ok
        assert not L1H.verify_written(_vals(_row(), _row()), _row(), "1").ok

    def test_without_field_compare(self):
        mut = _mutated_module(L1_REL, ("    if diff:\n", "    if False:\n"))
        written = _vals(_row(**{P.COL_EXPOSURE_LIMIT_PCT: "61"}))
        assert mut.verify_written(written, _row(), "1").ok
        assert not L1H.verify_written(written, _row(), "1").ok

    def test_without_date_check(self):
        mut = _mutated_module(L1_REL, ("    if record[COL_RECORD_DATE] != today_tw:\n", "    if False:\n"))
        assert mut.precheck_target([], _row(), today_tw="2026-10-15").ok
        assert not L1H.precheck_target([], _row(), today_tw="2026-10-15").ok

    def test_writer_scopes_only_two_values(self):
        assert L1H.writer_scopes(P.WRITER_SCOPES) == P.WRITER_SCOPES
        assert L1H.writer_scopes(list(P.READER_SCOPES)) == P.READER_SCOPES
        for bad in ((), P.WRITER_SCOPES + P.READER_SCOPES, ("https://www.googleapis.com/auth/drive",),
                    P.WRITER_SCOPES + ("https://www.googleapis.com/auth/drive",)):
            with pytest.raises(L1H.WriterCredentialRefused):
                L1H.writer_scopes(bad)
        mut = _mutated_module(L1_REL, (
            "    if chosen not in (tuple(WRITER_SCOPES), tuple(READER_SCOPES)):\n", "    if False:\n"))
        assert mut.writer_scopes(("https://www.googleapis.com/auth/drive",))
