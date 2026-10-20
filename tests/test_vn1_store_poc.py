"""VN1-STORE 最小 PoC（客戶 2026-10-19 裁示 A）— 歷史紀錄 schema／冪等／比較／無頭隔離守衛。

守：
1. `build_record`：VALID（用真的 `compute_and_lock_risk_cap` 寫快照＋官方讀端判定）與每一種非有效狀態；
   非有效 ⇒ `exposure_limit_pct` 空白（⛔ 不補 0）。
2. `upsert_record` 冪等：同日重跑不重複；VALID 內容不同不覆寫；非有效→有效追加且舊列不動；有效後失敗不寫。
3. `compare_status`：無歷史 → START_RECORDING；預期日沒紀錄／過期 → STALE；今日非有效 → 不比較；
   版本不同排除；同一份資料（input_asof 相同）不算變化。
4. `refresh_macro_now(risk_cap_state_file_path=...)`：只寫暫存目錄、app 工作目錄零檔案；預設呼叫不帶新參數。
5. 腳本：`--write` 一律失敗（不跑取數）；app 狀態檔被動到 → exit 1。
6. 靜態守衛：新模組不碰個人持股 Sheet 路徑／`GCP_SERVICE_ACCOUNT_JSON`；L1 不 import streamlit；
   直接呼叫鏈不 import AI 模組；L0 不 import L1+。
7. 突變自驗（in-test，恰一次字面替換）。
L1（休市表、PMI parquet）一律 mock；不連網。
"""
from __future__ import annotations

import ast
import copy
import importlib.util
import json
import os
import re
from datetime import timedelta
from pathlib import Path

import pytest

from shared import risk_cap_history_policy as P
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION, RISK_CAP_STATE_FILE
from src.data.risk_cap import history as L1H
from src.services import macro_refresh_service as RS
from src.services import risk_cap_apply as RC
from src.services import risk_cap_history_service as H
from tests.test_batch_z64 import NOW, _inputs, _session_from
from tests.test_batch_z65 import _hf_cal, _ts
from tests.test_p01_macro_refresh import _FakeST, _content_bundle, _mutated_module
from src.services import macro_engine_inputs as M

REPO = Path(__file__).resolve().parents[1]
NEW_FILES = (
    "shared/risk_cap_history_policy.py",
    "src/data/risk_cap/history.py",
    "src/services/risk_cap_history_service.py",
    "scripts/risk_cap_history_poc.py",
)


# ══════════════════════════════════════════════════════════════════════════
# 0. 還原鏈（舊批次 golden／sha 串接用；同 Z65／C21／UIA／1.0-B2 慣例）
# ══════════════════════════════════════════════════════════════════════════
#: origin/main `8c4722f4` 的 `macro_refresh_service.py` 原檔 sha256（`git show 8c4722f4:<rel> | sha256sum`）。
VN1STORE_BASE_SHA = {"src/services/macro_refresh_service.py":
                     "64275c87af4cd46b76ec0d6ac3b5c97d294a5729e7459ac90842ec21cb6b9e16",
                     # 稽核修正輪（2026-10-19）：`_bundle_summary` 加 `input_source`（8c4722f4 原檔 sha256）。
                     "src/services/risk_cap_apply.py":
                     "4361f74753852e8ed6688c038134636f6381c94a2db7b1ca2073c69437b21e53"}
VN1STORE_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    "src/services/macro_refresh_service.py": (
        ('from dataclasses import dataclass, field\n',
         'from dataclasses import dataclass\n'),
        ('    untouched: tuple[UntouchedBlock, ...] = UNTOUCHED_BLOCKS\n    #: VN1-STORE 最小 PoC（客戶 2026-10-19 裁示 A）：`STEP_RISK_CAP` 的結構化結論\n    #: （`risk_cap_apply.RiskCapApplyResult`；這一步沒跑到或拋例外 ⇒ None）。\n    #: 給無頭紀錄端（`risk_cap_history_service.build_record`）照實取狀態用，⛔ 不必解析步驟報告的中文 detail。\n    #: 畫面不讀它；`compare=False`／`repr=False` ⇒ 報告的相等判定與顯示逐字同修前。\n    risk_cap_result: Any = field(default=None, compare=False, repr=False)\n',
         '    untouched: tuple[UntouchedBlock, ...] = UNTOUCHED_BLOCKS\n'),
        ('                      on_event: Callable[[str, Any], None] | None = None,\n                      risk_cap_state_file_path: str | None = None,\n',
         '                      on_event: Callable[[str, Any], None] | None = None,\n'),
        ('            **純顯示用**；自己拋例外不影響取數。\n        risk_cap_state_file_path: `STEP_RISK_CAP` 寫 `macro_state.json` 的路徑（新 UI 的\n            `risk_cap_state.json` 依 `risk_cap_state_path` 規則落在**同一目錄**）。\n            None（預設，畫面呼叫端一律不傳）⇒ 呼叫方式與修前逐字相同（`compute_and_lock_risk_cap`\n            用它自己的預設相對路徑）。VN1-STORE 最小 PoC（客戶 2026-10-19 裁示 A，`scripts/risk_cap_history_poc.py`）\n            傳暫存目錄，讓無頭驗證**不覆寫** app 工作目錄裡的兩個狀態檔。⛔ 只改「寫到哪」，\n            不改計算、不改判定、不改其餘任何步驟。\n',
         '            **純顯示用**；自己拋例外不影響取數。\n'),
        ('    _rc_result = None\n    try:\n        from shared.staleness import MACRO_VERDICT_MAX_AGE_DAYS\n',
         '    try:\n        from shared.staleness import MACRO_VERDICT_MAX_AGE_DAYS\n'),
        ('            # VN1-STORE PoC：只有呼叫端明確傳了路徑才多帶這個參數（None ⇒ 與修前同一個呼叫）。\n            _rc_kw = ({} if risk_cap_state_file_path is None\n                      else {"state_file_path": risk_cap_state_file_path})\n            _rc = compute_and_lock_risk_cap(st.session_state, now=_utc_now(), **_rc_kw)\n        _rc_result = _rc\n',
         '            _rc = compute_and_lock_risk_cap(st.session_state, now=_utc_now())\n'),
        ('        written_keys=_written, popped_keys=_popped, cleared=_cleared,\n        risk_cap_result=_rc_result)\n',
         '        written_keys=_written, popped_keys=_popped, cleared=_cleared)\n'),
    ),
    "src/services/risk_cap_apply.py": (
        ('        "red_lines": {k: v.status for k, v in bundle.red_lines.items()},\n        # VN1-STORE PoC 稽核修正（2026-10-19，additive）：各輸入的來源標籤，原樣取自 L2 `dated_inputs`\n        #   產出的 `DatedValue.source`（上游 dict 自帶 `source` 時就是它，例如 L1 stale-cache 退路標的\n        #   「stale-cache(…)」）。⛔ 不另判新鮮度、不寫進快照檔（只在回傳值裡）。\n        "input_source": {k: bundle.assessed[k].dv.source for k in ENGINE_INPUT_KEYS},\n',
         '        "red_lines": {k: v.status for k, v in bundle.red_lines.items()},\n'),
    ),
}


def vn1store_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 VN1-STORE PoC 之前的寫法（無 pair 則原樣）。"""
    p = Path(file_path)
    rel = (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()
    for new, old in VN1STORE_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def test_vn1store_revert_is_exact_base_source():
    import hashlib
    for rel in sorted(VN1STORE_REVERT_PAIRS):
        code = vn1store_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == VN1STORE_BASE_SHA[rel], rel


@pytest.fixture
def l1(monkeypatch):
    cal = _hf_cal()
    monkeypatch.setattr(M._hf, "fetch_twse_holiday_calendar", lambda *, taipei_year: cal)
    holder = {"hist": None}
    monkeypatch.setattr(M._mcr, "load_tw_pmi_history", lambda: holder["hist"])
    # 快照 timestamp 與測試時鐘對齊（production 兩者都是真實時鐘；不對齊時讀端會以「超前現在」判過期）
    from src.services import macro_state_locker as MSL
    monkeypatch.setattr(MSL, "_now_str", lambda: _ts(NOW))
    return lambda hist: holder.__setitem__("hist", hist)


def _report(*, fetch_ok=True, rc_step=None, rc=None, sources_ok=True):
    steps = [RS.StepResult(RS.STEP_FETCH, fetch_ok, "1.0s" if fetch_ok else "ConnectionError: boom")]
    if rc_step is not None:
        steps.append(rc_step)
    return RS.MacroRefreshReport(
        mode=RS.MODE_WARM, started_at="t", elapsed_s=1.0,
        sources=(RS.SourceResult("intl", sources_ok, ""),), steps=tuple(steps),
        risk_cap_result=rc)


def _valid_record(tmp_path, l1, *, now=NOW, **inp):
    kw = _inputs(**inp)
    l1(kw["pmi_history"])
    d = tmp_path / "state"
    d.mkdir()
    res = RC.compute_and_lock_risk_cap(_session_from(kw), now=now,
                                       state_file_path=str(d / "macro_state.json"))
    assert res.written
    rep = _report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, True, "ok"), rc=res)
    return H.build_record(rep, state_dir=str(d), now_utc=now, run_id="r1", git_sha="abc"), res


# ══════════════════════════════════════════════════════════════════════════
# 1. build_record
# ══════════════════════════════════════════════════════════════════════════
class TestBuildRecord:
    def test_schema_exact(self, tmp_path, l1):
        row, _ = _valid_record(tmp_path, l1)
        assert tuple(row) == P.HISTORY_COLUMNS
        assert all(isinstance(v, str) for v in row.values())
        assert set(P.IDEMPOTENCY_KEY_COLUMNS) <= set(P.HISTORY_COLUMNS)
        assert set(P.CONTENT_COLUMNS) <= set(P.HISTORY_COLUMNS)
        assert P.COL_WRITTEN_AT_UTC not in P.CONTENT_COLUMNS and P.COL_RUN_ID not in P.CONTENT_COLUMNS

    def test_valid_uses_official_reader_value(self, tmp_path, l1):
        row, res = _valid_record(tmp_path, l1)
        snap = json.loads((tmp_path / "state" / RISK_CAP_STATE_FILE).read_text(encoding="utf-8"))
        assert row[P.COL_STATUS] == P.STATUS_VALID and row[P.COL_REASON_CODE] == ""
        assert row[P.COL_EXPOSURE_LIMIT_PCT] == str(snap["exposure_limit_pct"])
        assert row[P.COL_RULESET_VERSION] == RISK_CAP_RULESET_VERSION
        assert row[P.COL_REQUIRED_CORE_OK] == "TRUE"
        assert row[P.COL_ENGINE_SOURCE] == RC.ENGINE_SOURCE
        assert row[P.COL_SNAPSHOT_TIMESTAMP] == snap["timestamp"]
        assert json.loads(row[P.COL_INPUT_ASOF]) == snap["input_asof"]
        assert row[P.COL_RECORD_DATE] == res.bundle_summary["today"] == "2026-10-14"
        assert row[P.COL_DISABLED_INPUTS] == "M1B_YoY_pct,M2_YoY_pct"
        assert row[P.COL_RUN_ID] == "r1" and row[P.COL_GIT_SHA] == "abc"

    def test_core_missing_no_value(self, tmp_path, l1):
        kw = _inputs(vix=None)
        l1(kw["pmi_history"])
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW,
                                           state_file_path=str(tmp_path / "macro_state.json"))
        assert not res.written
        row = H.build_record(_report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, True, res.reason, skipped=True),
                                     rc=res), state_dir=str(tmp_path), now_utc=NOW, run_id="", git_sha="")
        assert row[P.COL_STATUS] == P.STATUS_REQUIRED_CORE_INCOMPLETE
        assert row[P.COL_EXPOSURE_LIMIT_PCT] == "" and row[P.COL_REQUIRED_CORE_OK] == ""
        assert "VIX_Index" in row[P.COL_MISSING_CORE].split(",")
        assert "VIX" in row[P.COL_REASON_DETAIL]
        assert row[P.COL_SNAPSHOT_TIMESTAMP] == ""

    def test_stale_core_input_is_core_incomplete_with_truthful_detail(self, tmp_path, l1):
        kw = _inputs(vix_date="2026-09-01")      # VIX 過期
        l1(kw["pmi_history"])
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW,
                                           state_file_path=str(tmp_path / "macro_state.json"))
        row = H.build_record(_report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, True, "", skipped=True),
                                     rc=res), state_dir=str(tmp_path), now_utc=NOW, run_id="", git_sha="")
        assert row[P.COL_STATUS] == P.STATUS_REQUIRED_CORE_INCOMPLETE
        assert row[P.COL_EXPOSURE_LIMIT_PCT] == ""
        assert "過期" in row[P.COL_REASON_DETAIL]

    def test_fail_safe(self, tmp_path, l1):
        l1(None)
        res = RC.compute_and_lock_risk_cap({}, now=NOW, state_file_path=str(tmp_path / "macro_state.json"))
        assert res.reason == RC.REASON_FAIL_SAFE
        row = H.build_record(_report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, True, "", skipped=True),
                                     rc=res), state_dir=str(tmp_path), now_utc=NOW, run_id="", git_sha="")
        assert row[P.COL_STATUS] == P.STATUS_ENGINE_FAILSAFE and row[P.COL_EXPOSURE_LIMIT_PCT] == ""

    def test_not_finite(self, tmp_path):
        res = RC.RiskCapApplyResult(False, RC.REASON_NOT_FINITE.format(value=float("nan")),
                                    {"today": "2026-10-14"}, None)
        row = H.build_record(_report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, True, "", skipped=True),
                                     rc=res), state_dir=str(tmp_path), now_utc=NOW, run_id="", git_sha="")
        assert row[P.COL_STATUS] == P.STATUS_ENGINE_NOT_FINITE and row[P.COL_EXPOSURE_LIMIT_PCT] == ""

    def test_fetch_failed(self, tmp_path):
        row = H.build_record(_report(fetch_ok=False), state_dir=str(tmp_path), now_utc=NOW,
                             run_id="", git_sha="")
        assert row[P.COL_STATUS] == P.STATUS_FETCH_FAILED and row[P.COL_EXPOSURE_LIMIT_PCT] == ""
        assert row[P.COL_RECORD_DATE] == "2026-10-14"           # 無 bundle ⇒ 以執行時刻的台北日期
        assert "boom" not in row[P.COL_REASON_DETAIL]           # ⛔ 不帶例外訊息原文
        assert P.STATUS_FETCH_FAILED and "fetch" in row[P.COL_REFRESH_FAILED].split(",")

    def test_compute_error(self, tmp_path):
        rep = _report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, False, "RuntimeError: token=SECRET123"))
        row = H.build_record(rep, state_dir=str(tmp_path), now_utc=NOW, run_id="", git_sha="")
        assert row[P.COL_STATUS] == P.STATUS_COMPUTE_ERROR and row[P.COL_EXPOSURE_LIMIT_PCT] == ""
        assert "SECRET123" not in json.dumps(row, ensure_ascii=False)

    def test_snapshot_rejected_by_reader(self, tmp_path, l1):
        """寫出了但讀端不收（以過期的時鐘模擬）⇒ 不得記 VALID、不得有值。"""
        kw = _inputs()
        l1(kw["pmi_history"])
        d = tmp_path / "s"
        d.mkdir()
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(d / "macro_state.json"))
        rep = _report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, True, ""), rc=res)
        row = H.build_record(rep, state_dir=str(d), now_utc=NOW + timedelta(days=30), run_id="", git_sha="")
        assert row[P.COL_STATUS] == P.STATUS_SNAPSHOT_REJECTED and row[P.COL_EXPOSURE_LIMIT_PCT] == ""

    def test_unknown_not_written_reason_raises(self, tmp_path):
        res = RC.RiskCapApplyResult(False, "某個沒見過的原因", {}, None)
        with pytest.raises(RuntimeError):
            H.build_record(_report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, True, "", skipped=True), rc=res),
                           state_dir=str(tmp_path), now_utc=NOW, run_id="", git_sha="")

    def test_naive_now_raises(self, tmp_path):
        with pytest.raises(ValueError):
            H.build_record(_report(fetch_ok=False), state_dir=str(tmp_path),
                           now_utc=NOW.replace(tzinfo=None), run_id="", git_sha="")

    def test_provenance_from_existing_outputs_only(self, tmp_path, l1):
        """PMI 走 L1 stale-cache 退路時：來源標籤與 `is_stale` 原樣記下；其餘沒有旗標的一律 "unknown"。"""
        kw = _inputs()
        kw["macro_info"]["ism_pmi"].update({"source": "stale-cache(CIER-EN)", "is_stale": True})
        l1(kw["pmi_history"])
        d = tmp_path / "s"
        d.mkdir()
        sess = _session_from(kw)
        res = RC.compute_and_lock_risk_cap(sess, now=NOW, state_file_path=str(d / "macro_state.json"))
        rep = _report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, True, ""), rc=res)
        row = H.build_record(rep, state_dir=str(d), now_utc=NOW, run_id="", git_sha="", session=sess)
        prov = json.loads(row[P.COL_CORE_INPUT_PROVENANCE])
        from shared.risk_cap_policy import REQUIRED_CORE_INPUTS
        assert list(prov) == sorted(REQUIRED_CORE_INPUTS) or set(prov) == set(REQUIRED_CORE_INPUTS)
        assert prov["ISM_PMI_or_OECD_CLI"] == {"source": "stale-cache(CIER-EN)", "upstream_is_stale": True}
        assert prov["VIX_Index"]["upstream_is_stale"] == "unknown"     # VIX 區塊不帶 is_stale ⇒ 不推定 False
        for k in ("PMI_Prev_Month", "Futures_Net_Short", "Index_Below_MA5"):
            assert prov[k]["upstream_is_stale"] == "unknown"
            assert prov[k]["source"] == res.bundle_summary["input_source"][k]
        assert row[P.COL_STATUS] == P.STATUS_VALID                     # 有效性規則不受 provenance 影響
        assert P.COL_CORE_INPUT_PROVENANCE not in P.CONTENT_COLUMNS

    def test_provenance_without_session_all_unknown_flags(self, tmp_path, l1):
        row, _ = _valid_record(tmp_path, l1)
        prov = json.loads(row[P.COL_CORE_INPUT_PROVENANCE])
        assert {v["upstream_is_stale"] for v in prov.values()} == {"unknown"}

    def test_provenance_fetch_failed_all_unknown(self, tmp_path):
        row = H.build_record(_report(fetch_ok=False), state_dir=str(tmp_path), now_utc=NOW,
                             run_id="", git_sha="", session={"macro_info": {"vix": {"is_stale": False}}})
        prov = json.loads(row[P.COL_CORE_INPUT_PROVENANCE])
        assert all(v == {"source": "unknown", "upstream_is_stale": "unknown"} for v in prov.values())

    def test_every_status_has_reason_code(self):
        assert set(P.STATUS_REASON_CODE) == set(P.RECORD_STATUSES)


# ══════════════════════════════════════════════════════════════════════════
# 2. upsert 冪等
# ══════════════════════════════════════════════════════════════════════════
def _row(**over):
    r = {c: "" for c in P.HISTORY_COLUMNS}
    r.update({P.COL_RECORD_DATE: "2026-10-14", P.COL_RULESET_VERSION: RISK_CAP_RULESET_VERSION,
              P.COL_STATUS: P.STATUS_VALID, P.COL_EXPOSURE_LIMIT_PCT: "60",
              P.COL_INPUT_ASOF: '{"VIX_Index":"2026-10-13"}', P.COL_SNAPSHOT_TIMESTAMP: "2026-10-14 10:00:00",
              P.COL_WRITTEN_AT_UTC: "2026-10-14T02:00:00+00:00", P.COL_RUN_ID: "1",
              P.COL_SCHEMA_VERSION: P.HISTORY_SCHEMA_VERSION})
    r.update(over)
    return r


class _FakeGsWS:
    """gspread `Worksheet` 替身（v6 介面：`spreadsheet_id`／`title`）。"""

    def __init__(self, calls, *, sheet_id="SYS_SHEET", title=P.HISTORY_WORKSHEET_NAME, rows=None):
        self.spreadsheet_id = sheet_id
        self.title = title
        self._rows = [[1, "a"]] if rows is None else rows
        self._calls = calls
        self.reads = 0

    def get_all_values(self):
        self.reads += 1
        return self._rows

    def append_row(self, values, value_input_option=None):
        self._calls.append((values, value_input_option))


def _invalid(**over):
    return _row(**{P.COL_STATUS: P.STATUS_REQUIRED_CORE_INCOMPLETE, P.COL_EXPOSURE_LIMIT_PCT: "",
                   P.COL_REASON_CODE: P.REASON_CODE_CORE_MISSING, **over})


class TestUpsert:
    def test_empty_writes_header_then_row(self):
        ws = L1H.InMemoryWorksheet()
        assert L1H.upsert_record(ws, _row()) == P.UPSERT_APPENDED
        vals = ws.get_all_values()
        assert tuple(vals[0]) == P.HISTORY_COLUMNS and len(vals) == 2

    def test_same_day_rerun_no_duplicate_even_if_provenance_differs(self):
        ws = L1H.InMemoryWorksheet()
        L1H.upsert_record(ws, _row())
        assert L1H.upsert_record(ws, _row(**{P.COL_RUN_ID: "2", P.COL_WRITTEN_AT_UTC: "x"})) \
            == P.UPSERT_NOOP_DUPLICATE
        assert len(L1H.rows_as_records(ws.get_all_values())) == 1

    def test_valid_conflict_first_kept_conflict_row_recorded_once(self):
        ws = L1H.InMemoryWorksheet()
        L1H.upsert_record(ws, _row())
        first = ws.get_all_values()[1]
        assert L1H.upsert_record(ws, _row(**{P.COL_EXPOSURE_LIMIT_PCT: "30"})) \
            == P.UPSERT_CONFLICT_KEPT_EXISTING
        vals = ws.get_all_values()
        assert vals[1] == first and len(vals) == 3            # 首筆一字不動；衝突另記一列
        recs = L1H.rows_as_records(vals)
        c = recs[1]
        assert c[P.COL_STATUS] == P.STATUS_SAME_DAY_CONFLICT
        assert c[P.COL_REASON_CODE] == P.REASON_CODE_SAME_DAY_CONFLICT
        assert c[P.COL_EXPOSURE_LIMIT_PCT] == ""             # ⛔ 衝突列不是有效上限
        assert "exposure_limit_pct：60 → 30" in c[P.COL_REASON_DETAIL]
        # 同一個衝突重跑 → 仍回衝突碼，但不重複記
        assert L1H.upsert_record(ws, _row(**{P.COL_EXPOSURE_LIMIT_PCT: "30", P.COL_RUN_ID: "7"})) \
            == P.UPSERT_CONFLICT_KEPT_EXISTING
        assert len(ws.get_all_values()) == 3
        # 讀端仍以首筆 VALID 為當天紀錄
        assert _cmp(recs).current[P.COL_EXPOSURE_LIMIT_PCT] == "60"

    def test_invalid_after_valid_appended_valid_untouched(self):
        ws = L1H.InMemoryWorksheet()
        L1H.upsert_record(ws, _row())
        first = ws.get_all_values()[1]
        assert L1H.upsert_record(ws, _invalid()) == P.UPSERT_APPENDED
        assert L1H.upsert_record(ws, _invalid(**{P.COL_RUN_ID: "8"})) == P.UPSERT_NOOP_DUPLICATE
        vals = ws.get_all_values()
        assert vals[1] == first and len(vals) == 3
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_EXPOSURE_LIMIT_PCT: "30"})
        r = _cmp([prev] + L1H.rows_as_records(vals))         # 當天較晚的失敗不影響比較
        assert r.status == P.COMPARE_COMPARABLE and r.current[P.COL_STATUS] == P.STATUS_VALID

    def test_invalid_dedupe_distinguishes_reason_detail(self):
        """同屬 REQUIRED_CORE_INCOMPLETE，「已過期」與「未取得」是兩個不同事實 ⇒ 不得當重跑吞掉。"""
        ws = L1H.InMemoryWorksheet()
        L1H.upsert_record(ws, _invalid(**{P.COL_REASON_DETAIL: "VIX（VIX_Index：未取得）"}))
        assert L1H.upsert_record(ws, _invalid(**{P.COL_REASON_DETAIL: "VIX（VIX_Index：已過期）"})) \
            == P.UPSERT_APPENDED
        assert P.COL_REASON_DETAIL in P.CONTENT_COLUMNS

    def test_invalid_then_valid_appends_and_keeps_old_row(self):
        ws = L1H.InMemoryWorksheet()
        L1H.upsert_record(ws, _invalid())
        first = ws.get_all_values()[1]
        assert L1H.upsert_record(ws, _row()) == P.UPSERT_APPENDED
        vals = ws.get_all_values()
        assert vals[1] == first and len(vals) == 3
        assert L1H.upsert_record(ws, _row()) == P.UPSERT_NOOP_DUPLICATE

    def test_invalid_rerun_same_content_noop_different_appends(self):
        ws = L1H.InMemoryWorksheet()
        L1H.upsert_record(ws, _invalid())
        assert L1H.upsert_record(ws, _invalid(**{P.COL_RUN_ID: "9"})) == P.UPSERT_NOOP_DUPLICATE
        assert L1H.upsert_record(ws, _invalid(**{P.COL_STATUS: P.STATUS_FETCH_FAILED,
                                                  P.COL_REASON_CODE: P.REASON_CODE_FETCH_EXCEPTION})) \
            == P.UPSERT_APPENDED

    def test_other_day_or_version_is_new_key(self):
        ws = L1H.InMemoryWorksheet()
        L1H.upsert_record(ws, _row())
        assert L1H.upsert_record(ws, _row(**{P.COL_RECORD_DATE: "2026-10-15"})) == P.UPSERT_APPENDED
        assert L1H.upsert_record(ws, _row(**{P.COL_RULESET_VERSION: "risk_cap.v3"})) == P.UPSERT_APPENDED

    def test_header_mismatch_refuses(self):
        ws = L1H.InMemoryWorksheet([["date", "value"]])
        with pytest.raises(L1H.HistorySchemaMismatch):
            L1H.upsert_record(ws, _row())
        assert ws.append_calls == 0

    def test_bad_row_refused(self):
        r = _row()
        r.pop(P.COL_STATUS)
        with pytest.raises(L1H.HistoryRowInvalid):
            L1H.upsert_record(L1H.InMemoryWorksheet(), r)
        with pytest.raises(L1H.HistoryRowInvalid):
            L1H.upsert_record(L1H.InMemoryWorksheet(), _row(**{P.COL_EXPOSURE_LIMIT_PCT: 60}))

    def test_trailing_blank_cells_padded(self):
        ws = L1H.InMemoryWorksheet([list(P.HISTORY_COLUMNS), ["2026-10-13", RISK_CAP_RULESET_VERSION, "VALID"]])
        recs = L1H.rows_as_records(ws.get_all_values())
        assert recs[0][P.COL_GIT_SHA] == ""

    def test_gspread_adapter_uses_raw(self):
        calls = []
        ws = _FakeGsWS(calls)
        a = L1H.GspreadWorksheetAdapter(ws, environ={P.HISTORY_SHEET_ID_ENV_VAR: "SYS_SHEET"})
        assert a.get_all_values() == [["1", "a"]]
        a.append_row(["x"])
        assert calls == [(["x"], "RAW")]
        with pytest.raises(ValueError):
            L1H.GspreadWorksheetAdapter(None, environ={P.HISTORY_SHEET_ID_ENV_VAR: "SYS_SHEET"})

    @pytest.mark.parametrize("env,sheet_id,title", [
        ({}, "SYS_SHEET", P.HISTORY_WORKSHEET_NAME),                                   # 沒設預期 ID
        ({P.HISTORY_SHEET_ID_ENV_VAR: "SYS_SHEET"}, "PERSONAL_SHEET", P.HISTORY_WORKSHEET_NAME),  # ID 不符
        ({P.HISTORY_SHEET_ID_ENV_VAR: "SYS_SHEET"}, None, P.HISTORY_WORKSHEET_NAME),   # 取不到 ID
        ({P.HISTORY_SHEET_ID_ENV_VAR: "SYS_SHEET"}, "SYS_SHEET", "持股"),              # 工作表名稱不符
    ])
    def test_gspread_adapter_refuses_wrong_target(self, env, sheet_id, title):
        calls = []
        ws = _FakeGsWS(calls, sheet_id=sheet_id, title=title, rows=[])
        with pytest.raises(L1H.HistoryTargetMismatch):
            L1H.GspreadWorksheetAdapter(ws, environ=env)
        assert calls == [] and ws.reads == 0                   # 連讀都不讀、表頭也不會被寫

    def test_gspread_adapter_old_gspread_spreadsheet_attr(self):
        ws = _FakeGsWS([], sheet_id=None)
        ws.spreadsheet = type("S", (), {"id": "SYS_SHEET"})()
        L1H.GspreadWorksheetAdapter(ws, environ={P.HISTORY_SHEET_ID_ENV_VAR: "SYS_SHEET"})

    def test_upsert_through_adapter_wrong_target_never_writes_header(self):
        calls = []
        ws = _FakeGsWS(calls, rows=[])
        a = L1H.GspreadWorksheetAdapter(ws, environ={P.HISTORY_SHEET_ID_ENV_VAR: "SYS_SHEET"})
        ws.spreadsheet_id = "SOMETHING_ELSE"                  # 目標中途被換掉
        with pytest.raises(L1H.HistoryTargetMismatch):
            L1H.upsert_record(a, _row())
        assert calls == []

    def test_real_valid_record_rerun_idempotent(self, tmp_path, l1):
        row, _ = _valid_record(tmp_path, l1)
        ws = L1H.InMemoryWorksheet()
        assert L1H.upsert_record(ws, row) == P.UPSERT_APPENDED
        assert L1H.upsert_record(ws, dict(row)) == P.UPSERT_NOOP_DUPLICATE


# ══════════════════════════════════════════════════════════════════════════
# 3. 讀端比較
# ══════════════════════════════════════════════════════════════════════════
def _cmp(rows, date="2026-10-14", now=NOW):
    return H.compare_status(rows, expected_date=date, now=now)


class TestCompare:
    def test_no_history_start_recording(self):
        assert _cmp([]).status == P.COMPARE_START_RECORDING

    def test_first_valid_today_start_recording(self):
        r = _cmp([_row()])
        assert r.status == P.COMPARE_START_RECORDING and r.previous is None

    def test_today_missing_is_stale_no_comparison(self):
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_SNAPSHOT_TIMESTAMP: "2026-10-13 18:00:00"})
        r = _cmp([prev])
        assert r.status == P.COMPARE_STALE and r.reason == P.STALE_TODAY_RUN_MISSING
        assert r.previous is None and r.current is None

    def test_latest_valid_expired(self):
        old = _row(**{P.COL_RECORD_DATE: "2026-09-01", P.COL_SNAPSHOT_TIMESTAMP: "2026-09-01 18:00:00"})
        r = _cmp([old])
        assert r.status == P.COMPARE_STALE and r.reason == P.STALE_LATEST_VALID_EXPIRED

    def test_today_invalid_not_compared(self):
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13"})
        r = _cmp([prev, _invalid()])
        assert r.status == P.COMPARE_CURRENT_NOT_VALID and r.previous is None
        assert r.reason == P.STATUS_REQUIRED_CORE_INCOMPLETE

    def test_comparable(self):
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_EXPOSURE_LIMIT_PCT: "30",
                       P.COL_INPUT_ASOF: '{"VIX_Index":"2026-10-12"}'})
        r = _cmp([prev, _row()])
        assert r.status == P.COMPARE_COMPARABLE
        assert r.previous[P.COL_EXPOSURE_LIMIT_PCT] == "30" and r.current[P.COL_EXPOSURE_LIMIT_PCT] == "60"

    def test_same_input_asof_is_no_new_data(self):
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13"})
        r = _cmp([prev, _row()])
        assert r.status == P.COMPARE_NO_NEW_DATA and r.previous is None

    def test_same_input_asof_but_value_changed_is_comparable(self):
        """資料日相同、正式上限值不同 ⇒ 真實官方值變化，⛔ 不得說成「沒有新資料」（不設門檻）。"""
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_EXPOSURE_LIMIT_PCT: "59"})
        r = _cmp([prev, _row()])
        assert r.status == P.COMPARE_COMPARABLE
        assert (r.previous[P.COL_EXPOSURE_LIMIT_PCT], r.current[P.COL_EXPOSURE_LIMIT_PCT]) == ("59", "60")

    def test_version_mismatch_excluded(self):
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_RULESET_VERSION: "risk_cap.v1",
                       P.COL_INPUT_ASOF: "{}"})
        r = _cmp([prev, _row()])
        assert r.status == P.COMPARE_START_RECORDING and r.excluded_other_version == 1

    def test_invalid_rows_skipped_as_previous(self):
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-10", P.COL_INPUT_ASOF: "{}"})
        mid = _invalid(**{P.COL_RECORD_DATE: "2026-10-13"})
        r = _cmp([prev, mid, _row()])
        assert r.status == P.COMPARE_COMPARABLE and r.previous[P.COL_RECORD_DATE] == "2026-10-10"

    def test_only_invalid_history_no_today(self):
        """~~修前期望 START_RECORDING~~（稽核修正 2026-10-19，有意識的變更）：已有紀錄（即使全是失敗列）
        ⇒ 排程開跑過，今天沒紀錄＝排程沒跑／失敗 ⇒ STALE；說成「從今天開始記錄」會把失敗講成正常起點。"""
        r = _cmp([_invalid(**{P.COL_RECORD_DATE: "2026-10-13"})])
        assert r.status == P.COMPARE_STALE and r.reason == P.STALE_TODAY_RUN_MISSING

    def test_only_invalid_history_today_invalid(self):
        r = _cmp([_invalid(**{P.COL_RECORD_DATE: "2026-10-13"}), _invalid()])
        assert r.status == P.COMPARE_CURRENT_NOT_VALID and r.previous is None

    def test_conflict_rows_never_used(self):
        prev = _row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_EXPOSURE_LIMIT_PCT: "30"})
        conflict = _row(**{P.COL_STATUS: P.STATUS_SAME_DAY_CONFLICT, P.COL_EXPOSURE_LIMIT_PCT: ""})
        assert _cmp([prev, conflict]).status == P.COMPARE_CURRENT_NOT_VALID


# ══════════════════════════════════════════════════════════════════════════
# 4. 無頭鏈：只寫暫存目錄
# ══════════════════════════════════════════════════════════════════════════
def _patch_chain(monkeypatch, fake):
    import src.services.data_registry_scanner as _REG
    import src.services.jingqi_calc as _JQ
    import src.services.macro_fetch_orchestrator as _ORCH
    import src.services.macro_session_apply as _APPLY
    import src.services.macro_trio_orchestrator as _TRIO
    import src.services.market_assessment_apply as _MKT
    import src.services.warroom_apply as _WR

    monkeypatch.setattr(RS, "_utc_now", lambda: NOW)
    monkeypatch.setattr(RS, "st", fake)

    def _bundle(**kw):
        for n in RS.SOURCE_LABELS:
            kw["on_job_done"](n, True, "1.0s")
        return _content_bundle()
    monkeypatch.setattr(_ORCH, "fetch_macro_bundle", _bundle)
    monkeypatch.setattr(_APPLY, "apply_macro_bundle", lambda *a, **k: ({}, ()))
    monkeypatch.setattr(_JQ, "compute_and_store_jingqi", lambda df: None)
    monkeypatch.setattr(_TRIO, "run_macro_trio_and_persist", lambda **k: None)
    monkeypatch.setattr(_MKT, "compute_and_apply_market_assessment", lambda **k: None)
    monkeypatch.setattr(_WR, "compute_and_store_warroom_summary", lambda: _WR.WarroomApplyResult(written=True))
    monkeypatch.setattr(_REG, "scan_and_write_data_registry",
                        lambda **k: fake.session_state.__setitem__("data_registry", {}))


class TestHeadlessIsolation:
    def test_writes_only_temp_dir(self, monkeypatch, tmp_path, l1):
        kw = _inputs()
        l1(kw["pmi_history"])
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        monkeypatch.chdir(app_dir)
        fake = _FakeST(copy.deepcopy(_session_from(kw)))
        _patch_chain(monkeypatch, fake)
        state_dir = tmp_path / "poc"
        rep = H.run_headless_refresh(str(state_dir))
        assert rep.risk_cap_result is not None and rep.risk_cap_result.written
        assert sorted(os.listdir(state_dir)) == sorted([RISK_CAP_STATE_FILE, "macro_state.json"])
        assert os.listdir(app_dir) == []                      # app 工作目錄零檔案
        row = H.build_record(rep, state_dir=str(state_dir), now_utc=NOW, run_id="", git_sha="")
        assert row[P.COL_STATUS] == P.STATUS_VALID and row[P.COL_EXPOSURE_LIMIT_PCT] != ""

    def test_default_call_unchanged_signature(self, monkeypatch, tmp_path, l1):
        """預設（畫面）呼叫不帶 `state_file_path` ⇒ 與修前同一個呼叫（舊 spy 簽章仍收得下）。"""
        l1(None)
        monkeypatch.chdir(tmp_path)
        fake = _FakeST({})
        _patch_chain(monkeypatch, fake)
        seen = []

        def _spy(session, *, now):
            seen.append(now)
            return RC.RiskCapApplyResult(False, RC.REASON_FAIL_SAFE, {}, None)
        monkeypatch.setattr(RC, "compute_and_lock_risk_cap", _spy)
        rep = RS.refresh_macro_now(mode=RS.MODE_WARM)
        assert seen == [NOW] and rep.risk_cap_result.reason == RC.REASON_FAIL_SAFE

    def test_report_field_not_in_equality(self):
        a = RS.MacroRefreshReport(mode="warm", started_at="t", elapsed_s=0.0, risk_cap_result=1)
        b = RS.MacroRefreshReport(mode="warm", started_at="t", elapsed_s=0.0)
        assert a == b and "risk_cap_result" not in repr(a)


# ══════════════════════════════════════════════════════════════════════════
# 5. 腳本
# ══════════════════════════════════════════════════════════════════════════
def _load_script():
    spec = importlib.util.spec_from_file_location("_poc_script", REPO / "scripts/risk_cap_history_poc.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestScript:
    def test_write_hard_fails_without_fetch(self, monkeypatch, capsys):
        mod = _load_script()
        monkeypatch.setattr(H, "run_headless_refresh", lambda d: pytest.fail("--write 不得跑取數"))
        monkeypatch.setenv(P.WRITE_ENABLE_ENV_VAR, "1")
        # VN1-STORE WIF auth-only（2026-10-19，有意識的放寬）：原本還設了 writer JSON key 環境變數 ——
        # 該常數已依 DEC-064 G1 退役（writer 只走 WIF，沒有 key），閘門不再檢查它；其餘條件照舊、照樣拒絕。
        monkeypatch.setenv(P.HISTORY_SHEET_ID_ENV_VAR, "x")
        assert mod.main(["--write"]) == 2
        assert "尚未核准" in capsys.readouterr().out

    def test_credentials_gate_refuses_even_if_configured(self):
        with pytest.raises(L1H.ProductionWriteNotApproved):
            # VN1-STORE WIF auth-only（2026-10-19，有意識的放寬）：拿掉已退役的 writer JSON key 環境變數
            # （DEC-064 G1）；「所有可設的條件都設了仍拒絕」這個守衛意圖不變。
            L1H.load_writer_credentials_or_refuse({P.WRITE_ENABLE_ENV_VAR: "1",
                                                   P.HISTORY_SHEET_ID_ENV_VAR: "x"})
        assert P.PRODUCTION_WRITE_APPROVED is False

    def _fake_run(self, rep_holder, *, write_cwd=False):
        def _run(state_dir):
            os.makedirs(state_dir, exist_ok=True)
            if write_cwd:
                Path(RISK_CAP_STATE_FILE).write_text("{}", encoding="utf-8")
            return rep_holder
        return _run

    def test_dry_run_simulated_rerun(self, monkeypatch, tmp_path, capsys):
        mod = _load_script()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(H, "run_headless_refresh", self._fake_run(_report(fetch_ok=False)))
        monkeypatch.setattr(mod, "_now_utc", lambda: NOW)
        out = tmp_path / "rec.json"
        assert mod.main(["--simulate-rerun", "--out", str(out),
                         "--state-dir", str(tmp_path / "sd")]) == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["record"][P.COL_STATUS] == P.STATUS_FETCH_FAILED
        assert data["simulate_rerun"]["first_upsert"] == P.UPSERT_APPENDED
        assert data["simulate_rerun"]["second_upsert"] == P.UPSERT_NOOP_DUPLICATE
        assert data["simulate_rerun"]["data_rows_after"] == 1
        assert data["simulate_rerun"]["compare_status"] == P.COMPARE_CURRENT_NOT_VALID
        assert data["app_state_files_untouched"] is True

    def test_conflict_exits_3(self, monkeypatch, tmp_path):
        mod = _load_script()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(H, "run_headless_refresh", self._fake_run(_report(fetch_ok=False)))
        monkeypatch.setattr(L1H, "upsert_record", lambda ws, row: P.UPSERT_CONFLICT_KEPT_EXISTING)
        assert mod.main(["--simulate-rerun", "--state-dir", str(tmp_path / "sd")]) == 3

    def test_app_state_touched_exit_1(self, monkeypatch, tmp_path):
        mod = _load_script()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(H, "run_headless_refresh",
                            self._fake_run(_report(fetch_ok=False), write_cwd=True))
        assert mod.main(["--state-dir", str(tmp_path / "sd")]) == 1

    def test_non_empty_state_dir_refused(self, monkeypatch, tmp_path):
        mod = _load_script()
        monkeypatch.chdir(tmp_path)
        sd = tmp_path / "sd"
        sd.mkdir()
        (sd / "x").write_text("1", encoding="utf-8")
        monkeypatch.setattr(H, "run_headless_refresh", lambda d: pytest.fail("不得跑"))
        assert mod.main(["--state-dir", str(sd)]) == 1


# ══════════════════════════════════════════════════════════════════════════
# 6. 靜態守衛
# ══════════════════════════════════════════════════════════════════════════
def _imports(rel: str) -> set[str]:
    tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module)
            out |= {f"{n.module}.{a.name}" for a in n.names}
    return out


_PERSONAL_SHEET = ("gsheet_portfolio", "gsheet_sa_reader", "oauth_state")


def assert_app_only_smoke_hook(app_src: str) -> None:
    """app.py 與系統歷史 Sheet 的唯一接點：恰好一行 `from …reader_service import run_smoke_if_flagged`
    ＋恰好一個模組層、無參數、回傳值不被使用的 `run_smoke_if_flagged()` 呼叫；其餘一字不得提到。"""
    tree = ast.parse(app_src)
    assert app_src.count("risk_cap_history") == 1
    imps = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
            and "risk_cap_history" in (n.module or "")]
    assert len(imps) == 1 and imps[0].module == "src.services.risk_cap_history_reader_service"
    assert [(a.name, a.asname) for a in imps[0].names] == [("run_smoke_if_flagged", None)]
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Import)
                and any("risk_cap_history" in a.name for a in n.names)]
    uses = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "run_smoke_if_flagged"]
    assert len(uses) == 1
    stmts = [s for s in tree.body if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
             and isinstance(s.value.func, ast.Name) and s.value.func.id == "run_smoke_if_flagged"]
    assert len(stmts) == 1 and not stmts[0].value.args and not stmts[0].value.keywords
    assert stmts[0].value.func is uses[0]


class TestStaticGuards:
    @pytest.mark.parametrize("rel", NEW_FILES)
    def test_no_personal_sheet_paths(self, rel):
        imps = _imports(rel)
        assert not [i for i in imps if any(p in i for p in _PERSONAL_SHEET)], imps
        src = (REPO / rel).read_text(encoding="utf-8")
        assert "GCP_SERVICE_ACCOUNT_JSON" not in src
        assert not [i for i in imps if i.startswith("src.data.portfolio")]

    def test_history_credential_names_confined(self):
        """寫入／讀取兩支帳號的名稱只准出現在 L0 定義處（及測試）；個人持股 Sheet／登入路徑一處都不得出現。"""
        # VN1-STORE WIF auth-only（2026-10-19，有意識的放寬）：writer JSON key 環境變數常數已依 DEC-064 G1
        # 退役（writer 只走 WIF），故從名單移除、改由 `tests/test_vn1_wif_auth_only.py` 守「全 repo 不得再出現」；
        # 「讀取端名稱 ≠ 寫入端」改為「L0 不再有寫入端 key 名稱」。
        # 📌 2026-10-20（VN1-STORE Production Wiring 批；有意識的變更，不是漏刪）：環境變數式的讀取端名稱
        # `READER_SA_ENV_VAR` 已退役（reader key 只放 Streamlit secrets 表格，規格步驟 8），名單改為
        # Streamlit secrets 的表格名＋Sheet ID 鍵名；舊字面改由 `tests/test_vn1_production_wiring.py` 守「全 repo 不得再出現」。
        names = (P.READER_SECRETS_TABLE, P.READER_SHEET_ID_SECRET_KEY, P.HISTORY_SHEET_ID_ENV_VAR,
                 P.WRITE_ENABLE_ENV_VAR)
        assert len(set(names)) == len(names)
        assert not hasattr(P, "WRITER_SA_ENV_VAR")
        assert not hasattr(P, "READER_SA_ENV_VAR")
        assert P.READER_SCOPES == ("https://www.googleapis.com/auth/spreadsheets.readonly",)
        assert all("readonly" not in s for s in P.WRITER_SCOPES)
        hits = {}
        for f in list((REPO / "src").rglob("*.py")) + list((REPO / "scripts").rglob("*.py")) \
                + list((REPO / "shared").rglob("*.py")) + [REPO / "app.py"]:
            # 📌 2026-10-20（Pre-Hardening 批）：模組路徑 `risk_cap_history_reader_service` 字面上含 secrets 表格名
            #   （`risk_cap_history_reader`）——那是 import 路徑不是憑證名稱，先去掉再比（app.py 的 smoke import 才不誤判）。
            t = f.read_text(encoding="utf-8").replace("risk_cap_history_reader_service", "")
            for n in names:
                if n in t:
                    hits.setdefault(f.relative_to(REPO).as_posix(), set()).add(n)
        # L0 定義處＋L1 唯一入口的 docstring（講拒絕順序）；其餘一律經 L0 常數引用，不寫字面。
        # 📌 2026-10-20（Production Wiring 批；有意識的放寬）：另准 L3 讀取端服務（docstring 講它只讀哪張 secrets 表）
        #   與 PoC 腳本（docstring 講 `--write` 用哪個 Sheet ID 環境變數）—— 兩者程式碼一律經 L0 常數引用。
        assert set(hits) <= {"shared/risk_cap_history_policy.py", "src/data/risk_cap/history.py",
                             "src/services/risk_cap_history_reader_service.py",
                             "scripts/risk_cap_history_poc.py"}, hits
        # L1 不讀 secrets（reader 憑證由 L3 讀進來再交給 L1）⇒ L1 不得知道 secrets 表格名／鍵名。
        l1_text = (REPO / "src/data/risk_cap/history.py").read_text(encoding="utf-8")
        assert P.READER_SECRETS_TABLE not in l1_text and P.READER_SHEET_ID_SECRET_KEY not in l1_text
        for f in list((REPO / "src").rglob("*.py")):
            rel = f.relative_to(REPO).as_posix()
            if any(p in rel for p in _PERSONAL_SHEET) or "oauth" in rel:
                t = f.read_text(encoding="utf-8")
                assert "risk_cap_history" not in t, rel

    def test_no_reader_code_path_in_app(self):
        # 📌 2026-10-20（VN1-STORE Pre-Hardening 批；有意識的放寬，不是漏改）：原「app.py 一字不得提到
        #   risk_cap_history」放寬為「**只准**一行 import `run_smoke_if_flagged`＋一行無參數呼叫」（log-only smoke，
        #   ⛔ 畫面零輸出）。原意圖（畫面不得有讀取端程式碼路徑、UI 不得顯示歷史）照守：src/ui/ 仍一字不得提到；
        #   app.py 不得用到 reader 服務的其他任何符號。
        for f in (REPO / "src/ui").rglob("*.py"):
            assert "risk_cap_history" not in f.read_text(encoding="utf-8"), f.relative_to(REPO).as_posix()
        assert_app_only_smoke_hook((REPO / "app.py").read_text(encoding="utf-8"))

    def test_app_smoke_hook_guard_mutations(self):
        src = (REPO / "app.py").read_text(encoding="utf-8")
        line = "from src.services.risk_cap_history_reader_service import run_smoke_if_flagged  # noqa: E402\n"
        assert src.count(line) == 1
        for bad in (src.replace(line, line.replace("run_smoke_if_flagged", "run_smoke_if_flagged, read_history")),
                    src.replace("\nrun_smoke_if_flagged()\n", "\nrun_smoke_if_flagged()\nrun_smoke_if_flagged()\n"),
                    src.replace("\nrun_smoke_if_flagged()\n", "\nst.write(run_smoke_if_flagged())\n"),
                    src + "\nfrom src.services import risk_cap_history_reader_service\n"):
            with pytest.raises(AssertionError):
                assert_app_only_smoke_hook(bad)

    def test_l1_no_streamlit_no_upper_layers(self):
        imps = _imports("src/data/risk_cap/history.py")
        assert not [i for i in imps if i == "streamlit" or i.startswith("streamlit.")]
        assert not [i for i in imps if i.startswith(("src.compute", "src.services", "src.ui"))]

    def test_l0_stdlib_only(self):
        imps = _imports("shared/risk_cap_history_policy.py")
        assert not [i for i in imps if i.startswith(("src", "streamlit"))]

    @pytest.mark.parametrize("rel", NEW_FILES + (
        "src/services/risk_cap_apply.py", "src/services/macro_engine_inputs.py",
        "src/services/macro_refresh_service.py"))
    def test_direct_chain_no_ai_modules(self, rel):
        bad = [i for i in _imports(rel)
               if any(t in i for t in ("ai_fetcher", "app_ai_service", "ai_qa_service", "gemini",
                                       "ai_structured_summary", "ai_judgment"))]
        assert not bad, bad

    def test_workflow_dispatch_only_read_perm_no_sheet_secrets(self):
        y = (REPO / ".github/workflows/risk_cap_history_poc.yml").read_text(encoding="utf-8")
        assert "schedule:" not in y and "cron:" not in y
        assert "contents: read" in y and "contents: write" not in y
        # VN1-STORE WIF auth-only（2026-10-19，有意識的變更）：退役的 writer JSON key 名稱改以字面守住
        # （常數已刪）；本測試仍掃全檔 —— 新增的 wif_auth_only job 也不得含下列任何一項。
        # 📌 VN1-STORE Sheet 權限驗證 Gate（2026-10-20，有意識的放寬，不是漏改）：System Risk Cap Sheet ID 的
        # secret（`P.HISTORY_SHEET_ID_ENV_VAR`）只准出現在兩個權限驗證 job（P1／P2／R3 要知道目標 Sheet）——
        # 故 `P.HISTORY_SHEET_ID_ENV_VAR` 與前綴 "RISK_CAP_HISTORY" 改為只掃「去掉那兩個 job 區塊」後的全檔；
        # 其餘各項照舊掃全檔（含新 job）。新 job 的完整守衛在 `tests/test_vn1_permission_gate.py`。
        # 📌 2026-10-20（Production Wiring 批；有意識的放寬，不是漏改）：`production_write`（寫入 job）也需要 Sheet ID
        #   與 `--write`／寫入總開關；只准出現在該 job，其完整守衛在 `tests/test_vn1_production_wiring.py`。
        outside = y
        for job in ("permission_test_writer", "permission_test_reader", "production_write"):
            m = re.search(rf"^  {job}:\n(.*?)(?=^  \S|\Z)", y, flags=re.MULTILINE | re.DOTALL)
            assert m, job
            outside = outside.replace(m.group(0), "")
        for bad in (P.HISTORY_SHEET_ID_ENV_VAR, "RISK_CAP_HISTORY"):
            assert bad not in outside, bad
        for bad in (P.WRITE_ENABLE_ENV_VAR, "--write"):
            assert bad not in outside, bad
        for bad in ("GCP_SERVICE_ACCOUNT_JSON", "RISK_CAP_HISTORY_WRITER_SA_JSON",
                    "RISK_CAP_HISTORY_READER_SA_JSON",
                    "git push", "git commit", "GEMINI"):
            assert bad not in y, bad


# ══════════════════════════════════════════════════════════════════════════
# 7. 突變自驗
# ══════════════════════════════════════════════════════════════════════════
class TestMutations:
    def test_upsert_without_valid_guard_duplicates(self):
        mut = _mutated_module("src/data/risk_cap/history.py",
                              ("    if row[COL_STATUS] == STATUS_VALID and valid_rows:\n",
                               "    if False:\n"))
        ws = mut.InMemoryWorksheet()
        mut.upsert_record(ws, _row())
        mut.upsert_record(ws, _row(**{P.COL_EXPOSURE_LIMIT_PCT: "30"}))
        recs = mut.rows_as_records(ws.get_all_values())
        assert [r[P.COL_STATUS] for r in recs] == [P.STATUS_VALID, P.STATUS_VALID]   # 突變體：同日兩筆 VALID

    def test_compare_treating_latest_as_today_fakes_comparison(self):
        """突變：「今天」改成「所有列」⇒ 今天沒跑也會拿昨天 vs 前天比 —— 假的「和上次比」。"""
        mut = _mutated_module("src/services/risk_cap_history_service.py",
                              ("    today = [r for r in same if r.get(P.COL_RECORD_DATE) == expected_date]\n",
                               "    today = sorted(same, key=lambda r: r[P.COL_RECORD_DATE], reverse=True)[:1]\n"
                               "    expected_date = today[0][P.COL_RECORD_DATE]\n"))
        rows = [_row(**{P.COL_RECORD_DATE: "2026-10-12", P.COL_EXPOSURE_LIMIT_PCT: "30",
                        P.COL_INPUT_ASOF: "{}"}),
                _row(**{P.COL_RECORD_DATE: "2026-10-13"})]
        real = H.compare_status(rows, expected_date="2026-10-14", now=NOW)
        assert real.status == P.COMPARE_STALE and real.previous is None and real.current is None
        fake = mut.compare_status(rows, expected_date="2026-10-14", now=NOW)
        assert fake.status == P.COMPARE_COMPARABLE and fake.previous is not None   # 突變體產生假比較

    def test_compare_value_change_mutation_hides_change(self):
        mut = _mutated_module("src/services/risk_cap_history_service.py",
                              ("            and previous.get(P.COL_EXPOSURE_LIMIT_PCT) == current.get(P.COL_EXPOSURE_LIMIT_PCT)):",
                               "            and True):"))
        rows = [_row(**{P.COL_RECORD_DATE: "2026-10-13", P.COL_EXPOSURE_LIMIT_PCT: "59"}), _row()]
        assert H.compare_status(rows, expected_date="2026-10-14", now=NOW).status == P.COMPARE_COMPARABLE
        assert mut.compare_status(rows, expected_date="2026-10-14", now=NOW).status == P.COMPARE_NO_NEW_DATA

    def test_compare_start_recording_mutation_hides_stale(self):
        mut = _mutated_module("src/services/risk_cap_history_service.py",
                              ("    if not same:\n", "    if not any(r.get(P.COL_STATUS) == P.STATUS_VALID for r in same):\n"))
        rows = [_invalid(**{P.COL_RECORD_DATE: "2026-10-13"})]
        assert mut.compare_status(rows, expected_date="2026-10-14", now=NOW).status == P.COMPARE_START_RECORDING
        assert H.compare_status(rows, expected_date="2026-10-14", now=NOW).status == P.COMPARE_STALE

    def test_upsert_dropping_invalid_after_valid_mutation(self):
        mut = _mutated_module("src/data/risk_cap/history.py",
                              ("    if row[COL_STATUS] != STATUS_VALID:\n",
                               "    if row[COL_STATUS] != STATUS_VALID and valid_rows:\n        return UPSERT_NOOP_DUPLICATE\n"
                               "    if row[COL_STATUS] != STATUS_VALID:\n"))
        ws = mut.InMemoryWorksheet()
        mut.upsert_record(ws, _row())
        mut.upsert_record(ws, _invalid())
        assert len(mut.rows_as_records(ws.get_all_values())) == 1            # 突變體吞掉當天較晚的失敗
        ws2 = L1H.InMemoryWorksheet()
        L1H.upsert_record(ws2, _row())
        L1H.upsert_record(ws2, _invalid())
        assert len(L1H.rows_as_records(ws2.get_all_values())) == 2

    def test_adapter_without_id_check_mutation_writes_wrong_sheet(self):
        mut = _mutated_module("src/data/risk_cap/history.py",
                              ("        if actual != self._expected_id:\n", "        if False:\n"))
        calls = []
        ws = _FakeGsWS(calls, sheet_id="PERSONAL_SHEET", rows=[])
        a = mut.GspreadWorksheetAdapter(ws, environ={P.HISTORY_SHEET_ID_ENV_VAR: "SYS_SHEET"})
        mut.upsert_record(a, _row())
        assert calls and tuple(calls[0][0]) == P.HISTORY_COLUMNS          # 突變體把表頭寫進錯的試算表

    def test_build_record_without_reader_check_marks_valid(self, tmp_path, l1):
        mut = _mutated_module("src/services/risk_cap_history_service.py",
                              ("        if exposure is None:\n            status = P.STATUS_SNAPSHOT_REJECTED",
                               "        if False:\n            status = P.STATUS_SNAPSHOT_REJECTED"))
        kw = _inputs()
        l1(kw["pmi_history"])
        d = tmp_path / "s"
        d.mkdir()
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(d / "macro_state.json"))
        rep = _report(rc_step=RS.StepResult(RS.STEP_RISK_CAP, True, ""), rc=res)
        row = mut.build_record(rep, state_dir=str(d), now_utc=NOW + timedelta(days=30), run_id="", git_sha="")
        assert row[P.COL_STATUS] == P.STATUS_VALID          # 突變體把讀端不收的快照記成 VALID
