"""批 Z65 — F5：新 UI「🚀 更新今日戰情」自動計算系統風險上限並寫入 `macro_state.json`。

客戶 2026-10-14 題2＝A／Q2＝A。守：
1. 引擎 `veto_flags`（opt-in）：預設輸出與修前逐鍵逐值相同（golden digest 由修前引擎 049911dc 實跑）；
   opt-in 時既有鍵不變、`veto_flags` 與實際分支／`Macro_Phase` 否決標記逐例一致；fail-safe 全 False＋fail_safe。
2. `compute_and_lock_risk_cap`：可計算 → 寫檔正確（上限＝引擎、附帶欄位可 JSON 化且無 nan／inf 字面）；
   fail-safe／非有限 → 既有檔 bytes 不變、`get_macro_state` 仍讀到舊上限；例外 → 既有檔不變、往上拋；
   部分缺漏 → 照寫、`not_evaluated` 與紅線 undetermined 正確。
3. refresh 整合：步驟順序、`STEP_WRITES`／`STEP_FILE_WRITES` 登記、報告文字屬實、步驟失敗不連坐。
4. 下游：寫檔後 `get_macro_state`／`get_allocation` 讀到新上限、卡①天花板生效、出口文字屬實。
5. 舊 UI 不受影響：舊組裝段（原文 exec）引擎輸出沒有 `veto_flags`；消費端讀多了鍵的檔，輸出不變。
6. 突變自驗（in-test，恰一次字面替換）。
L1（休市表、PMI parquet）一律 mock；不連網（conftest 守衛）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from src.services import macro_engine_inputs as M
from src.services import macro_refresh_service as RS
from src.services import risk_cap_apply as RC
from src.services import macro_state_locker as MSL
from src.services.macro_state_locker import (
    MACRO_VETO_FUTURES_NET_SHORT_LOTS,
    MACRO_VETO_PMI_CONTRACTION_LEVEL,
    _ENGINE_NUMERIC_INPUTS,
    calculate_system_state,
    get_macro_state,
)
from tests.test_batch_z64 import (
    NOW,
    _build,
    _golden_cases,
    _inputs,
    _old_for,
    _session_from,
)
from tests.test_p01_macro_refresh import _FakeST, _content_bundle, _mutated_module

REPO = Path(__file__).resolve().parents[1]
TPE = timezone(timedelta(hours=8))

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原鏈（舊批次 golden 串接用；同 Z62／Z63 慣例）：把本批對 L3 引擎的改動換回 049911dc 寫法
# ══════════════════════════════════════════════════════════════════════════
_MSL_REL = "src/services/macro_state_locker.py"
#: 049911dc 的 `macro_state_locker.py` 原檔 sha256（`git show 049911dc:<rel> | sha256sum`）。
Z65_BASE_SHA = {_MSL_REL: "f8b873d3123ca9c815bc3e6b3fa0661f8f6929a918b57ef157d35fd667520001"}
Z65_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _MSL_REL: (
        ("def calculate_system_state(macro_numbers: dict, *, include_veto_flags: bool = False) -> dict:",
         "def calculate_system_state(macro_numbers: dict) -> dict:"),
        ("    `include_veto_flags`（批 Z65，客戶 2026-10-14 題2＝A；預設 False ⇒ 輸出與修前逐字相同）\n"
         "    ────────────────────────────────────────────────────────────────\n"
         "    True → 回傳多一個 `veto_flags`：``{\"sahm\", \"pmi_contraction\", \"futures_ma5\": bool,\n"
         "    \"fail_safe\": bool}``。三條紅線的值**就是下方該分支是否實際進入**（在分支內設定，⛔ 不另寫一份\n"
         "    條件重算）；`fail_safe=True` 只出現在「8 項數值全缺」的 fail-safe 回傳 —— 此時三條一律 False，\n"
         "    語意是「**沒有評估**」，⛔ 不是「未觸發」。其餘既有鍵的值一個都不受影響。\n"
         "    **為什麼是 opt-in 而不是一律帶**：舊 UI `section_news_ai` 把整份 `_system_state`\n"
         "    `json.dumps` 進 AI prompt、並原樣 `**` 進 `lock_system_state_only` 落檔 —— 一律帶等於改了\n"
         "    舊 UI 送給 LLM 的內容與寫出的檔（客戶 2026-10-13 舊 UI 凍結）。只有新 UI 的\n"
         "    `src/services/risk_cap_apply.py` 會傳 True。\n"
         "\n", ""),
        ("        _fs_out = {\n", "        return {\n"),
        ("            \"missing_inputs\": missing_inputs,\n"
         "        }\n"
         "        if include_veto_flags:\n"
         "            # 批 Z65：fail-safe 沒有跑任何紅線 ⇒ 三條 False ＋ fail_safe=True（＝未評估，⛔ 不是「未觸發」）\n"
         "            _fs_out[\"veto_flags\"] = {\"sahm\": False, \"pmi_contraction\": False,\n"
         "                                     \"futures_ma5\": False, \"fail_safe\": True}\n"
         "        return _fs_out\n",
         "            \"missing_inputs\": missing_inputs,\n"
         "        }\n"),
        ("    veto_labels: list[str] = []\n"
         "    # 批 Z65：各分支**實際進入**時才設 True（`include_veto_flags=True` 時輸出；預設不輸出）\n"
         "    _veto_sahm = _veto_pmi = _veto_futures = False\n",
         "    veto_labels: list[str] = []\n"),
        ("        _veto_sahm = True\n", ""),
        ("        _veto_pmi = True\n", ""),
        ("        _veto_futures = True\n", ""),
        ("    if include_veto_flags:\n"
         "        _out[\"veto_flags\"] = {\"sahm\": _veto_sahm, \"pmi_contraction\": _veto_pmi,\n"
         "                              \"futures_ma5\": _veto_futures, \"fail_safe\": False}\n"
         "    return _out\n",
         "    return _out\n"),
    ),
}


def z65_revert_for(file_path, code: str) -> str:
    """舊批次還原鏈串接用：給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣）。"""
    # 📌 批 Z66（客戶 2026-10-16 Q2，有意識的變更，⛔ 不是漏改）：Z66 改了 `calculate_system_state`（M1B-M2 腿停用）
    #   ⇒ 先換回 Z66 之前的寫法（`tests/test_batch_z66.py::Z66_REVERT_PAIRS`；`Z65_BASE_SHA` 不改、本表不動）。
    from tests.test_batch_z66 import z66_revert_for
    code = z66_revert_for(file_path, code)
    p = Path(file_path)
    rel = (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()
    for new, old in Z65_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def test_z65_revert_is_exact_base_source():
    code = z65_revert_for(_MSL_REL, (REPO / _MSL_REL).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z65_BASE_SHA[_MSL_REL]
_VETO_KEYS = ("sahm", "pmi_contraction", "futures_ma5")
_NONFINITE_TOKEN = re.compile(r"(?<![A-Za-z])[-+]?(?:nan|inf(?:inity)?)(?![A-Za-z])", re.IGNORECASE)


def _hf_cal():
    from src.data.stock import twse_holiday_fetcher as hf
    payload = json.loads((REPO / "tests/fixtures/twse_holiday_schedule_115_synthetic.json")
                         .read_text(encoding="utf-8"))
    return hf.parse_holiday_schedule(payload, fetched_at=datetime(2026, 10, 2, tzinfo=timezone.utc))


@pytest.fixture
def l1(monkeypatch):
    """L1 全 mock：休市表＝fixture、PMI 歷史＝呼叫端指定（預設 None）。回傳設定 parquet 的函式。"""
    cal = _hf_cal()
    monkeypatch.setattr(M._hf, "fetch_twse_holiday_calendar", lambda *, taipei_year: cal)
    holder = {"hist": None}
    monkeypatch.setattr(M._mcr, "load_tw_pmi_history", lambda: holder["hist"])

    def _set(hist):
        holder["hist"] = hist
    return _set


def _ts(dt_utc: datetime) -> str:
    return dt_utc.astimezone(TPE).strftime(MSL._TIMESTAMP_FMT)


def _write_old_valid_file(path: Path, *, days_ago: int = 3, cap: int = 30) -> bytes:
    """一份 `days_ago` 天前（相對 NOW）寫的有效上限檔。回傳 bytes。"""
    data = {"market_regime": "空頭", "systemic_risk_level": "危險", "exposure_limit_pct": cap,
            "Macro_Phase": "環境正常", "analysis_summary": f"曝險上限 {cap}%（Python 規則引擎計算）",
            "timestamp": _ts(NOW - timedelta(days=days_ago))}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    return path.read_bytes()


# ══════════════════════════════════════════════════════════════════════════
# 1. 引擎 veto_flags
# ══════════════════════════════════════════════════════════════════════════
_EDGE_NUM = {
    "VIX_Index": [10.0, 14.0, 22.0, 25.0, 28.0, 35.0, 45.0],
    "ISM_PMI_or_OECD_CLI": [44.0, 46.0, 47.99, 48.0, 50.0, 52.01, 55.01],
    "PMI_Prev_Month": [44.0, 47.99, 48.0, 50.0, 56.0],
    "M1B_YoY_pct": [-5.0, 0.0, 3.0, 8.0],
    "M2_YoY_pct": [-2.0, 0.0, 3.01, 6.0],
    "BIAS240_pct": [-20.0, -10.0, 0.0, 15.0, 15.01, 30.0],
    "PCR": [0.5, 0.69, 0.7, 1.0, 1.5, 1.51],
    "Futures_Net_Short": [MACRO_VETO_FUTURES_NET_SHORT_LOTS - 0.01, MACRO_VETO_FUTURES_NET_SHORT_LOTS,
                          -60000.0, -20000.0, 0.0],
}
_BAD = [None, float("nan"), float("inf"), float("-inf"), "abc", True, np.float64("nan")]
#: 修前引擎（049911dc `calculate_system_state`）跑 `_engine_grid()` 的正規化輸出 sha256。
#: 產生方式：`git show 049911dc:src/services/macro_state_locker.py` exec 成模組 → 逐例 `_canon` → sha256。
_PRE_Z65_ENGINE_DIGEST = "fa0b426aa9744508900cb141517e2b4dfbf524eb12b1293656b9b4bb8295554e"
_GRID_N = 4000


def _engine_grid():
    rng = random.Random(65)
    for i in range(_GRID_N):
        d: dict = {}
        all_missing = rng.random() < 0.05
        for k in _ENGINE_NUMERIC_INPUTS:
            r = rng.random()
            if all_missing or r < 0.12:
                v = rng.choice(_BAD)
                if v is not None or rng.random() < 0.5:
                    d[k] = v
            elif r < 0.55:
                d[k] = rng.choice(_EDGE_NUM[k])
            else:
                d[k] = round(rng.uniform(-80000, 80000) if k == "Futures_Net_Short"
                             else rng.uniform(-30, 70), 3)
        d["Sahm_Rule_Triggered"] = rng.choice([None, False, True, "true", "no"])
        d["Index_Below_MA5"] = rng.choice([True, False, None, "yes", np.bool_(True)])
        if rng.random() < 0.3:
            d["TW_Export_YoY_pct"] = rng.uniform(-10, 10)   # 舊 UI 多送、引擎不讀
        yield i, d


def _canon(out: dict) -> str:
    return json.dumps(out, ensure_ascii=False, sort_keys=False, default=repr)


def _grid_digest(engine) -> str:
    h = hashlib.sha256()
    for i, d in _engine_grid():
        h.update(f"{i}|{_canon(engine(copy.deepcopy(d)))}\n".encode("utf-8"))
    return h.hexdigest()


class TestEngineVetoFlags:
    @pytest.fixture(autouse=True)
    def _z66_m1b_m2_leg_on_reference(self, monkeypatch):
        """📌 批 Z66（客戶 2026-10-16 Q2，有意識的變更，⛔ 不是放寬）：M1B-M2 腿自 Z66 起在引擎停用。本類（golden 由修前引擎 049911dc 實跑）比對的是**腿仍計分**的修前引擎 ⇒ 開關設 True 證原等價（不改 golden）；腿停用（開關 False）的行為由 tests/test_batch_z66.py 守。"""
        monkeypatch.setattr("shared.signal_thresholds.M1B_M2_LEG_ENABLED", True)

    def test_default_output_is_byte_identical_to_pre_z65_engine(self):
        assert _grid_digest(calculate_system_state) == _PRE_Z65_ENGINE_DIGEST

    def test_opt_in_existing_keys_identical(self):
        def _strip(d):
            out = calculate_system_state(d, include_veto_flags=True)
            assert set(out["veto_flags"]) == {*_VETO_KEYS, "fail_safe"}
            return {k: v for k, v in out.items() if k != "veto_flags"}
        assert _grid_digest(_strip) == _PRE_Z65_ENGINE_DIGEST

    def test_default_has_no_veto_flags(self):
        for _, d in _engine_grid():
            assert "veto_flags" not in calculate_system_state(d)

    def test_flags_match_branches_and_phase(self):
        n_hit = {k: 0 for k in _VETO_KEYS}
        for i, d in _engine_grid():
            out = calculate_system_state(copy.deepcopy(d), include_veto_flags=True)
            vf, phase = out["veto_flags"], out["Macro_Phase"]
            if vf["fail_safe"]:
                assert phase == "系統異常" and not any(vf[k] for k in _VETO_KEYS), (i, out)
                assert len(out["missing_inputs"]) == len(_ENGINE_NUMERIC_INPUTS)
                continue
            assert vf["sahm"] == ("🚨薩姆規則觸發" in phase), (i, d, out)
            assert vf["pmi_contraction"] == ("⚠️PMI連兩月收縮" in phase), (i, d, out)
            assert vf["futures_ma5"] == ("🚨期貨淨空" in phase), (i, d, out)
            # 獨立的條件 oracle（輸入端重算一次）
            f = {k: (float(d[k]) if MSL._is_finite_number(d.get(k)) else None)
                 for k in _ENGINE_NUMERIC_INPUTS}
            sahm = d["Sahm_Rule_Triggered"]
            sahm = sahm if isinstance(sahm, bool) else (str(sahm).lower() in ("true", "1", "yes")
                                                        if sahm is not None else False)
            ma5 = d["Index_Below_MA5"]
            ma5 = ma5 if isinstance(ma5, bool) else (str(ma5).lower() in ("true", "1", "yes")
                                                     if ma5 is not None else False)
            pmi, prev, fut = f["ISM_PMI_or_OECD_CLI"], f["PMI_Prev_Month"], f["Futures_Net_Short"]
            assert vf["sahm"] == sahm
            assert vf["pmi_contraction"] == (pmi is not None and prev is not None
                                             and pmi < MACRO_VETO_PMI_CONTRACTION_LEVEL
                                             and prev < MACRO_VETO_PMI_CONTRACTION_LEVEL)
            assert vf["futures_ma5"] == (fut is not None and fut < MACRO_VETO_FUTURES_NET_SHORT_LOTS
                                         and ma5)
            for k in _VETO_KEYS:
                n_hit[k] += vf[k]
        assert all(v > 20 for v in n_hit.values()), n_hit   # 三條都真的被觸發過

    def test_fail_safe_flags(self):
        out = calculate_system_state({}, include_veto_flags=True)
        assert out["veto_flags"] == {"sahm": False, "pmi_contraction": False,
                                     "futures_ma5": False, "fail_safe": True}
        out = calculate_system_state({"Sahm_Rule_Triggered": True}, include_veto_flags=True)
        assert out["veto_flags"]["sahm"] is True and out["veto_flags"]["fail_safe"] is False

    def test_old_ui_exec_path_engine_unchanged(self):
        """舊 UI 組裝段原文 exec：`_system_state` 不帶 `veto_flags`，既有鍵與 opt-in 版逐值相同。"""
        n = 0
        for i, kw in _golden_cases():
            if i >= 600:
                break
            prev = kw["pmi_history"]["pmi"].iloc[-1]
            nums, state = _old_for(kw, prev)
            assert "veto_flags" not in state
            opt = calculate_system_state(dict(nums), include_veto_flags=True)
            assert {k: v for k, v in opt.items() if k != "veto_flags"} == state
            n += 1
        assert n == 600

    def test_run_rule_engine_opt_in(self):
        b = _build(_inputs())
        assert "veto_flags" not in M.run_rule_engine(b)
        r = M.run_rule_engine(b, include_veto_flags=True)
        assert r["veto_flags"]["fail_safe"] is False
        assert {k: v for k, v in r.items() if k != "veto_flags"} == M.run_rule_engine(b)


# ══════════════════════════════════════════════════════════════════════════
# 2. compute_and_lock_risk_cap
# ══════════════════════════════════════════════════════════════════════════
def _attached_json(state: dict) -> str:
    return json.dumps({k: state[k] for k in ("engine_source", "input_asof", "not_evaluated",
                                             "red_lines", "veto_flags", "input_detail",
                                             "m1b_m2_data_month")}, ensure_ascii=False)


def _assert_no_nonfinite(text: str):
    assert not _NONFINITE_TOKEN.search(text), _NONFINITE_TOKEN.search(text)
    assert "NaN" not in text and "Infinity" not in text


class TestComputeAndLock:
    def test_computable_writes_correct_file(self, l1, tmp_path):
        kw = _inputs()
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert res.written and res.reason == ""
        state = json.loads(f.read_text(encoding="utf-8"))
        expect = M.run_rule_engine(_build(kw), include_veto_flags=True)
        for k, v in expect.items():
            assert state[k] == v, k
        assert state["exposure_limit_pct"] == expect["exposure_limit_pct"]
        # ~~assert state["engine_source"] == RC.ENGINE_SOURCE == "new_ui_risk_cap_v1"~~
        # ~~assert state["m1b_m2_data_month"] == "2026-08"~~
        # 📌 批 Z66（客戶 2026-10-16 Q2，有意識的變更，⛔ 不是漏改）：來源標記升 v2；M1B-M2 腿停用 ⇒
        #   M1B／M2 沒有進計分 ⇒ 資料月 None（腿開啟時仍回 "2026-08"，見 tests/test_batch_z66.py）。
        assert state["engine_source"] == RC.ENGINE_SOURCE == "new_ui_risk_cap_v2"
        assert state["m1b_m2_data_month"] is None
        assert state["not_evaluated"] == []
        assert state["red_lines"]["sahm"]["status"] == "no_source"
        assert set(state["input_detail"]) == set(M.ENGINE_INPUT_KEYS)
        for k, d in state["input_detail"].items():
            assert set(d) == {"value", "status", "as_of_or_month", "lag", "lag_unit"}, k
            assert d["status"] == "fresh"
        assert state["input_detail"]["VIX_Index"] == {
            "value": 17.3, "status": "fresh", "as_of_or_month": "2026-10-13",
            "lag": state["input_detail"]["VIX_Index"]["lag"], "lag_unit": "weekday"}
        assert state["analysis_summary"].startswith(f"曝險上限 {expect['exposure_limit_pct']}%")
        assert state["timestamp"]
        _assert_no_nonfinite(_attached_json(state))
        json.loads(f.read_text(encoding="utf-8"),
                   parse_constant=lambda c: pytest.fail(f"檔內出現 {c}"))

    def test_nan_input_scrubbed_and_partial(self, l1, tmp_path):
        """上游 PMI 是 NaN、外資期貨缺：照寫；紅線 reason 不含 nan 字面；not_evaluated／undetermined 正確。"""
        kw = _inputs(pmi=float("nan"), fut=float("nan"))
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert res.written
        state = json.loads(f.read_text(encoding="utf-8"))
        b = _build(kw)
        assert state["not_evaluated"] == list(b.not_evaluated)
        assert {"ISM_PMI_or_OECD_CLI", "PMI_Prev_Month", "Futures_Net_Short"} <= set(state["not_evaluated"])
        assert state["red_lines"]["pmi_contraction"]["status"] == "undetermined"
        assert state["red_lines"]["futures_ma5"]["status"] == "undetermined"
        assert state["red_lines"]["sahm"]["status"] == "no_source"
        assert state["veto_flags"] == {"sahm": False, "pmi_contraction": False,
                                       "futures_ma5": False, "fail_safe": False}
        assert state["input_detail"]["ISM_PMI_or_OECD_CLI"]["value"] is None
        assert "missing_inputs" in state
        # Z64 的 reason 本來帶「（nan）」—— 前提自證，否則這支沒守到東西
        assert any(_NONFINITE_TOKEN.search(rl.reason) for rl in b.red_lines.values())
        _assert_no_nonfinite(_attached_json(state))
        assert RC.NONFINITE_TEXT in state["red_lines"]["pmi_contraction"]["reason"]

    def test_partial_missing_prev_month(self, l1, tmp_path):
        kw = _inputs(prev_month=None)
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        state = json.loads(f.read_text(encoding="utf-8"))
        assert res.written and state["not_evaluated"] == ["PMI_Prev_Month"]
        assert state["red_lines"]["pmi_contraction"]["status"] == "undetermined"
        assert state["red_lines"]["futures_ma5"]["status"] == "evaluable"
        assert state["Macro_Phase"].endswith("1 項未評估（缺資料不計分）")

    def test_m1b_proxy_month_none(self, l1, tmp_path):
        kw = _inputs()
        kw["m1b_m2_info"] = dict(kw["m1b_m2_info"], source="TWII-proxy", data_month=None)
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert json.loads(f.read_text(encoding="utf-8"))["m1b_m2_data_month"] is None

    def test_fail_safe_keeps_old_file_bytes(self, l1, tmp_path):
        f = tmp_path / "macro_state.json"
        before = _write_old_valid_file(f, days_ago=3, cap=30)
        assert get_macro_state(None, state_file_path=str(f), now=NOW)["exposure_limit_pct"] == 30
        res = RC.compute_and_lock_risk_cap({}, now=NOW, state_file_path=str(f))
        assert not res.written and res.reason == RC.REASON_FAIL_SAFE
        assert "本輪無法計算，不寫檔（既有檔若有，保留不動）" in res.reason
        assert res.engine_result["veto_flags"]["fail_safe"] is True
        assert f.read_bytes() == before
        assert get_macro_state(None, state_file_path=str(f), now=NOW)["exposure_limit_pct"] == 30
        assert not (tmp_path / "macro_state.json.tmp").exists()

    def test_fail_safe_all_stale(self, l1, tmp_path):
        """8 項都有值但全部過期 ⇒ 全不計分 ⇒ fail-safe ⇒ 不寫。"""
        kw = _inputs()
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW + timedelta(days=400),
                                           state_file_path=str(f))
        assert not res.written and not f.exists()

    def test_not_finite_cap_not_written(self, l1, tmp_path, monkeypatch):
        f = tmp_path / "macro_state.json"
        before = _write_old_valid_file(f)
        for bad in (float("nan"), float("inf"), None, True, "60"):
            monkeypatch.setattr(RC, "run_rule_engine", lambda b, **k: {
                "exposure_limit_pct": bad, "veto_flags": {"fail_safe": False}, "red_lines": {}})
            res = RC.compute_and_lock_risk_cap({}, now=NOW, state_file_path=str(f))
            assert not res.written and "不是有限數" in res.reason, bad
            assert f.read_bytes() == before

    def test_missing_veto_flags_raises(self, l1, tmp_path, monkeypatch):
        f = tmp_path / "macro_state.json"
        before = _write_old_valid_file(f)
        monkeypatch.setattr(RC, "run_rule_engine", lambda b, **k: {"exposure_limit_pct": 60})
        with pytest.raises(RuntimeError, match="veto_flags"):
            RC.compute_and_lock_risk_cap({}, now=NOW, state_file_path=str(f))
        assert f.read_bytes() == before

    @pytest.mark.parametrize("where", ["engine", "inputs", "replace", "dump"])
    def test_exception_propagates_file_unchanged(self, l1, tmp_path, monkeypatch, where):
        kw = _inputs()
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        before = _write_old_valid_file(f)

        def boom(*a, **k):
            raise OSError(f"炸了:{where}")
        if where == "engine":
            monkeypatch.setattr(RC, "run_rule_engine", boom)
        elif where == "inputs":
            monkeypatch.setattr(RC, "load_engine_inputs_from_session", boom)
        elif where == "replace":
            monkeypatch.setattr(MSL.os, "replace", boom)
        else:
            monkeypatch.setattr(MSL.json, "dump", boom)
        with pytest.raises(OSError, match=f"炸了:{where}"):
            RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert f.read_bytes() == before
        assert get_macro_state(None, state_file_path=str(f), now=NOW)["exposure_limit_pct"] == 30

    def test_nonfinite_payload_raises_before_write(self, l1, tmp_path, monkeypatch):
        kw = _inputs()
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        before = _write_old_valid_file(f)
        real = RC.run_rule_engine
        monkeypatch.setattr(RC, "run_rule_engine",
                            lambda b, **k: {**real(b, **k), "input_asof": {"x": float("nan")}})
        with pytest.raises(ValueError):
            RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert f.read_bytes() == before

    def test_session_read_only(self, l1, tmp_path):
        kw = _inputs()
        l1(kw["pmi_history"])
        sess = _session_from(kw)
        keys = set(sess)
        snap = {k: copy.deepcopy(v) for k, v in sess.items() if k != "li_latest"}
        RC.compute_and_lock_risk_cap(sess, now=NOW, state_file_path=str(tmp_path / "m.json"))
        assert set(sess) == keys and {k: v for k, v in sess.items() if k != "li_latest"} == snap

    def test_overwrites_whole_file_like_old_ui(self, l1, tmp_path):
        """`lock_system_state_only` 整份覆寫（不保留、不合併既有欄位）—— 與舊 UI 相同。"""
        kw = _inputs()
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        f.write_text(json.dumps({"traffic_light": "🟢 多頭市場", "strategy": "AI 解讀",
                                 "exposure_limit_pct": 10, "timestamp": "x"}), encoding="utf-8")
        RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        state = json.loads(f.read_text(encoding="utf-8"))
        assert "traffic_light" not in state and "strategy" not in state

    def test_layering(self):
        import ast
        tree = ast.parse((REPO / "src/services/risk_cap_apply.py").read_text(encoding="utf-8"))
        mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not [m for m in mods if m and (m.startswith("src.ui") or m == "app"
                                              or m.startswith("streamlit"))], mods
        src = (REPO / "src/services/risk_cap_apply.py").read_text(encoding="utf-8")
        assert "session_state" not in re.sub(r'"""[\s\S]*?"""|#.*', "", src)


# ══════════════════════════════════════════════════════════════════════════
# 3. refresh 整合（risk_cap_apply 用真的，其餘外部相依換替身）
# ══════════════════════════════════════════════════════════════════════════
def _run_refresh(monkeypatch, tmp_path, *, session=None, pmi_hist=None, risk_cap=None,
                 registry_ok=True, trio_keys=()):
    import src.services.data_registry_scanner as _REG
    import src.services.jingqi_calc as _JQ
    import src.services.macro_fetch_orchestrator as _ORCH
    import src.services.macro_session_apply as _APPLY
    import src.services.macro_trio_orchestrator as _TRIO
    import src.services.market_assessment_apply as _MKT
    import src.services.warroom_apply as _WR

    monkeypatch.chdir(tmp_path)
    cal = _hf_cal()
    monkeypatch.setattr(M._hf, "fetch_twse_holiday_calendar", lambda *, taipei_year: cal)
    monkeypatch.setattr(M._mcr, "load_tw_pmi_history", lambda: pmi_hist)
    monkeypatch.setattr(RS, "_utc_now", lambda: NOW)
    fake = _FakeST(copy.deepcopy(session or {}))
    monkeypatch.setattr(RS, "st", fake)
    order: list[str] = []

    def _bundle(**kw):
        for n in RS.SOURCE_LABELS:
            kw["on_job_done"](n, True, "1.0s")
        return _content_bundle()

    def _registry(**k):
        order.append("registry")
        if not registry_ok:
            raise RuntimeError("registry 炸了")
        fake.session_state["data_registry"] = {}

    monkeypatch.setattr(_ORCH, "fetch_macro_bundle", _bundle)
    monkeypatch.setattr(_APPLY, "apply_macro_bundle", lambda *a, **k: ({}, ()))
    monkeypatch.setattr(_JQ, "compute_and_store_jingqi", lambda df: order.append("jingqi"))
    def _trio(**k):
        order.append("trio")
        for _k in trio_keys:       # 照真模組寫法：整個 key 重新賦值（量測以 id 判寫入）
            fake.session_state[_k] = copy.copy(fake.session_state.get(_k)) \
                if isinstance(fake.session_state.get(_k), dict) else {"v": 1}
    monkeypatch.setattr(_TRIO, "run_macro_trio_and_persist", _trio)
    monkeypatch.setattr(_MKT, "compute_and_apply_market_assessment",
                        lambda **k: order.append("market"))

    def _wr():
        order.append("warroom")
        return _WR.WarroomApplyResult(written=True)
    monkeypatch.setattr(_WR, "compute_and_store_warroom_summary", _wr)
    monkeypatch.setattr(_REG, "scan_and_write_data_registry", _registry)
    if risk_cap is not None:
        monkeypatch.setattr(RC, "compute_and_lock_risk_cap", risk_cap)
    else:
        real = RC.compute_and_lock_risk_cap

        def _spy(session, *, now):
            order.append("risk_cap")
            assert session is fake.session_state and now == NOW
            return real(session, now=now)
        monkeypatch.setattr(RC, "compute_and_lock_risk_cap", _spy)
    return RS.refresh_macro_now(mode=RS.MODE_WARM), fake, order


def _step(r, name):
    (s,) = [s for s in r.steps if s.name == name]
    return s


class TestRefreshIntegration:
    def test_declarations(self):
        assert RS.STEP_RISK_CAP == "risk_cap" and RS.STEP_RISK_CAP in RS.STEP_LABELS
        assert RS.STEP_WRITES[RS.STEP_RISK_CAP] == ()
        assert RS.STEP_FILE_WRITES == {RS.STEP_RISK_CAP: ("macro_state.json",)}
        assert "macro_state.json" not in RS.WRITES_SESSION_KEYS

    def test_untouched_list_no_longer_claims_the_cap(self):
        assert not any(b.session_key == "macro_state.json" or "系統風險上限" in b.label
                       or "系統風險上限" in b.why for b in RS.UNTOUCHED_BLOCKS)

    def test_written_report_and_order(self, monkeypatch, tmp_path):
        kw = _inputs(prev_month=None)
        r, fake, order = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                                      pmi_hist=kw["pmi_history"])
        names = [s.name for s in r.steps]
        assert (names.index(RS.STEP_TRIO) < names.index(RS.STEP_MARKET)
                < names.index(RS.STEP_WARROOM) < names.index(RS.STEP_RISK_CAP)
                < names.index(RS.STEP_REGISTRY))
        assert order.index("warroom") < order.index("risk_cap") < order.index("registry")
        s = _step(r, RS.STEP_RISK_CAP)
        state = json.loads((tmp_path / "macro_state.json").read_text(encoding="utf-8"))
        assert s.ok and not s.skipped and not s.partial
        assert f"系統風險上限 {state['exposure_limit_pct']}%" in s.detail
        assert "已寫入 macro_state.json" in s.detail
        assert "未評估 1 項（PMI_Prev_Month；缺項不計分）" in s.detail
        assert "硬否決紅線無法判定：pmi_contraction" in s.detail
        assert "薩姆規則目前無資料來源、未評估（不代表已通過）" in s.detail
        assert _step(r, RS.STEP_WRITE_AUDIT).ok and r.ok, r.failures
        assert "macro_state.json" not in r.written_keys + r.not_written_keys

    def test_fail_safe_report_and_file_kept(self, monkeypatch, tmp_path):
        before = _write_old_valid_file(tmp_path / "macro_state.json")
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session={})
        s = _step(r, RS.STEP_RISK_CAP)
        assert s.ok and s.skipped
        assert "本輪無法計算，不寫檔（既有檔若有，保留不動）" in s.detail and "7 天有效期" in s.detail
        assert "新頁的建議持股顯示「無法判定」" in s.detail
        assert (tmp_path / "macro_state.json").read_bytes() == before
        assert r.ok   # skipped 不算失敗（綠燈另由 refresh_is_clean 排除 skipped）

    def test_exception_is_failed_step_others_run(self, monkeypatch, tmp_path):
        before = _write_old_valid_file(tmp_path / "macro_state.json")

        def boom(session, *, now):
            raise RuntimeError("風險上限炸了")
        r, _, order = _run_refresh(monkeypatch, tmp_path, session={}, risk_cap=boom)
        s = _step(r, RS.STEP_RISK_CAP)
        assert not s.ok and "風險上限炸了" in s.detail and not r.ok
        assert "registry" in order and _step(r, RS.STEP_REGISTRY).ok
        assert (tmp_path / "macro_state.json").read_bytes() == before

    def test_other_step_failure_does_not_block_risk_cap(self, monkeypatch, tmp_path):
        kw = _inputs()
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"], registry_ok=False)
        assert _step(r, RS.STEP_RISK_CAP).ok and not _step(r, RS.STEP_REGISTRY).ok
        assert (tmp_path / "macro_state.json").exists()


# ══════════════════════════════════════════════════════════════════════════
# 4. 下游：get_macro_state / get_allocation / 卡①
# ══════════════════════════════════════════════════════════════════════════
class TestDownstream:
    _WR = {"traffic_light": "🟢 多頭市場", "health_score": 90.0, "regime": "bull",
           "effective_regime": "bull", "light": "🟢", "regime_source": "test"}

    def _fresh_cap_file(self, l1, tmp_path, monkeypatch, *, vix=40.0):
        """一份**現在**寫的上限檔（VIX 高 ⇒ 上限低），cwd＝tmp。"""
        monkeypatch.chdir(tmp_path)
        kw = _inputs(vix=vix)
        l1(kw["pmi_history"])
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW)
        assert res.written and (tmp_path / "macro_state.json").exists()
        return res.engine_result["exposure_limit_pct"]

    def test_get_macro_state_and_allocation(self, l1, tmp_path, monkeypatch):
        cap = self._fresh_cap_file(l1, tmp_path, monkeypatch)
        # `lock_system_state_only` 以真實時鐘寫 timestamp ⇒ 以真實時鐘讀
        assert get_macro_state(None)["exposure_limit_pct"] == cap
        from src.services import allocation_service as AS
        from tests.test_m2n2_no_zero_fill import _FakeST as _ASFake
        monkeypatch.setattr(AS, "st", _ASFake({"warroom_summary": dict(self._WR)}))
        alloc = AS.get_allocation()
        assert alloc.is_loaded
        assert any(c.name == "系統風險上限" and c.pct == cap for c in alloc.caps)
        assert alloc.final_hi <= cap and alloc.cap_pct <= cap

    def test_card1_cap_live(self, l1, tmp_path, monkeypatch):
        cap = self._fresh_cap_file(l1, tmp_path, monkeypatch)
        from src.services import allocation_service as AS
        from src.ui.views import page_today as P
        from tests.test_m2n2_no_zero_fill import _FakeST as _ASFake
        monkeypatch.setattr(AS, "st", _ASFake({"warroom_summary": dict(self._WR)}))
        alloc = AS.get_allocation()
        tiles = {t.card.key: t for t in P.build_verdict_tiles(
            alloc=alloc, alloc_error="", danger=None, danger_error="",
            danger_requested=False, regime=AS.get_macro_regime(), regime_error="")}
        t = tiles["verdict.exposure"]
        assert t.card.state == P.UI_LIVE
        assert dict(t.facts).get("硬否決天花板") == alloc.cap_text
        assert alloc.cap_pct is not None and alloc.cap_pct <= cap

    def test_card1_idle_exit_is_retry(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        from src.services import allocation_service as AS
        from src.ui.views import page_today as P
        from tests.test_m2n2_no_zero_fill import _FakeST as _ASFake
        monkeypatch.setattr(AS, "st", _ASFake({}))
        tiles = {t.card.key: t for t in P.build_verdict_tiles(
            alloc=AS.get_allocation(), alloc_error="", danger=None, danger_error="",
            danger_requested=False, regime=AS.get_macro_regime(), regime_error="")}
        assert tiles["verdict.exposure"].card.note.where is P.EXIT_RETRY_HERE

    def test_page_today_wording(self):
        from src.ui.views import page_today as P
        src = (REPO / "src/ui/views/page_today.py").read_text(encoding="utf-8")
        # 「系統風險上限本頁摸不到」的說法只准出現在刪除線內
        for pat in ("那一條天花板讀 `macro_state.json`，本頁摸不到",
                    "卡①只有「系統風險上限」那一條天花板讀 `macro_state.json`（本頁摸不到）"):
            for m in re.finditer(re.escape(pat), src):
                head = src[:m.start()]
                assert head.count("~~") % 2 == 1, pat   # 在一段未閉合的 ~~ 之內
        assert "批 Z65" in (P.__doc__ or "")
        assert "按本頁按鈕可重算" in (P.__doc__ or "")


# ══════════════════════════════════════════════════════════════════════════
# 5. 舊 UI ／ 消費端不受影響
# ══════════════════════════════════════════════════════════════════════════
class TestConsumers:
    _BASE = {"market_regime": "震盪", "systemic_risk_level": "警告", "exposure_limit_pct": 50,
             "Macro_Phase": "VIX高波動(26.0)", "analysis_summary": "曝險上限 50%（Python 規則引擎計算）"}

    def _pair(self, tmp_path):
        from src.services.macro_state_locker import _now_str
        a = dict(self._BASE, timestamp=_now_str())
        b = dict(a, engine_source="new_ui_risk_cap_v1", input_asof={"VIX_Index": "2026-10-13"},
                 not_evaluated=["PMI_Prev_Month"], red_lines={"sahm": {"status": "no_source"}},
                 veto_flags={"sahm": False, "pmi_contraction": False, "futures_ma5": False,
                             "fail_safe": False},
                 input_detail={"VIX_Index": {"value": 26.0}}, m1b_m2_data_month="2026-08")
        fa, fb = tmp_path / "a.json", tmp_path / "b.json"
        fa.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
        fb.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
        return fa, fb

    def test_get_macro_state_ignores_extra_keys(self, tmp_path):
        fa, fb = self._pair(tmp_path)
        for strict in (False, True):
            for wr in (None, {"health_score": 70.0, "effective_regime": "bull"}):
                assert (get_macro_state(wr, state_file_path=str(fa), strict=strict)
                        == get_macro_state(wr, state_file_path=str(fb), strict=strict))

    def test_ai_qa_market_state_ignores_extra_keys(self, tmp_path, monkeypatch):
        from src.services import ai_qa_service as Q
        fa, fb = self._pair(tmp_path)
        monkeypatch.chdir(tmp_path)
        (tmp_path / "macro_state.json").write_bytes(fa.read_bytes())
        out_a = Q._tool_get_market_state()
        (tmp_path / "macro_state.json").write_bytes(fb.read_bytes())
        out_b = Q._tool_get_market_state()
        assert out_a == out_b

    def test_old_ui_lock_call_unchanged(self):
        src = (REPO / "src/ui/tabs/macro/section_news_ai.py").read_text(encoding="utf-8")
        assert src.count("_system_state = calculate_system_state(_macro_numbers)") == 1
        assert "include_veto_flags" not in src
        assert src.count("_locker.lock_system_state_only({") == 1

    def test_only_risk_cap_apply_opts_in(self):
        """AST：真的以 `include_veto_flags=<非 False>` 呼叫的檔（註解／docstring 不算）。"""
        import ast
        hits = set()
        for p in list((REPO / "src").rglob("*.py")) + list((REPO / "scripts").rglob("*.py")) \
                + [REPO / "app.py"]:
            for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(n, ast.Call) and any(
                        kw.arg == "include_veto_flags"
                        and not (isinstance(kw.value, ast.Constant) and kw.value.value is False)
                        for kw in n.keywords):
                    hits.add(p.relative_to(REPO).as_posix())
        assert sorted(hits) == ["src/services/macro_engine_inputs.py",
                                "src/services/risk_cap_apply.py"], hits


# ══════════════════════════════════════════════════════════════════════════
# 6. 突變自驗（恰一次字面替換 → 守衛必須轉紅）
# ══════════════════════════════════════════════════════════════════════════
class TestMutations:
    def test_fail_safe_still_writes(self, l1, tmp_path):
        mod = _mutated_module("src/services/risk_cap_apply.py",
                              ('    if veto["fail_safe"] is True:', '    if False:'))
        f = tmp_path / "macro_state.json"
        before = _write_old_valid_file(f)
        mod.compute_and_lock_risk_cap({}, now=NOW, state_file_path=str(f))
        assert f.read_bytes() != before     # 突變體真的蓋掉了 ⇒ 原版的 bytes 守衛抓得到

    def test_exception_clears_file(self, l1, tmp_path):
        """突變：失敗時先刪檔 → 原版守衛（bytes 不變）在突變體上必紅。"""
        mod = _mutated_module(
            "src/services/risk_cap_apply.py",
            ("    bundle = load_engine_inputs_from_session(session, now=now)",
             "    import os as _o; _o.path.exists(state_file_path) and _o.remove(state_file_path)\n"
             "    bundle = load_engine_inputs_from_session(session, now=now)"))
        f = tmp_path / "macro_state.json"
        _write_old_valid_file(f)
        mod.load_engine_inputs_from_session = lambda *a, **k: (_ for _ in ()).throw(OSError("x"))
        with pytest.raises(OSError):
            mod.compute_and_lock_risk_cap({}, now=NOW, state_file_path=str(f))
        assert not f.exists()

    def test_veto_flag_mismatch(self):
        mod = _mutated_module("src/services/macro_state_locker.py",
                              ("        _veto_pmi = True\n", "        _veto_pmi = False\n"))
        bad = 0
        for _, d in _engine_grid():
            vf = mod.calculate_system_state(copy.deepcopy(d), include_veto_flags=True)
            if not vf["veto_flags"]["fail_safe"]:
                bad += vf["veto_flags"]["pmi_contraction"] != ("⚠️PMI連兩月收縮" in vf["Macro_Phase"])
        assert bad > 0

    def test_risk_cap_after_registry(self, monkeypatch, tmp_path):
        """突變：把 risk cap 那段搬到 registry 之後 → 步驟順序守衛必紅。"""
        text = (REPO / "src/services/macro_refresh_service.py").read_text(encoding="utf-8")
        a = text.index("    # ── 5c. 系統風險上限")
        b = text.index("    # ── 6. 資料登錄中心")
        c = text.index("    # ── 7. 寫入對帳")
        assert a < b < c
        swapped = text[:a] + text[b:c] + text[a:b] + text[c:]
        mod = _mutated_module("src/services/macro_refresh_service.py", (text, swapped))
        kw = _inputs()
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"])
        names = [s.name for s in r.steps]
        assert names.index(RS.STEP_RISK_CAP) < names.index(RS.STEP_REGISTRY)   # 原版
        monkeypatch.setattr(mod, "st", RS.st)
        monkeypatch.setattr(mod, "_utc_now", lambda: NOW)
        r2 = mod.refresh_macro_now(mode=mod.MODE_WARM)
        n2 = [s.name for s in r2.steps]
        assert n2.index(mod.STEP_RISK_CAP) > n2.index(mod.STEP_REGISTRY)    # 突變體 ⇒ 守衛會紅

    def test_input_detail_with_nan_string(self, l1, tmp_path):
        mod = _mutated_module(
            "src/services/risk_cap_apply.py",
            ('            "lag_unit": str(av.verdict.lag_unit),',
             '            "lag_unit": str(av.verdict.lag_unit),\n'
             '            "reason": str(av.verdict.reason),'))
        kw = _inputs(pmi=float("nan"))
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        mod.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        state = json.loads(f.read_text(encoding="utf-8"))
        assert _NONFINITE_TOKEN.search(_attached_json(state))   # 原版的 nan 守衛在突變體上必紅

    def test_step_writes_unregistered(self):
        mod = _mutated_module("src/services/macro_refresh_service.py",
                              ("    STEP_RISK_CAP: (),\n", ""))
        assert mod.STEP_RISK_CAP not in mod.STEP_WRITES   # 原版 test_declarations 必紅


# ══════════════════════════════════════════════════════════════════════════
# 7. 批 Z65 QA 追加
# ══════════════════════════════════════════════════════════════════════════
_TRIO_ALL = ("m1b_m2_info", "bias_info", "macro_info")
_STALE_PHRASES = ("不是這一輪算的", "AI 鎖定")


def _as_session(monkeypatch, session: dict):
    from src.services import allocation_service as AS
    from tests.test_m2n2_no_zero_fill import _FakeST as _ASFake
    monkeypatch.setattr(AS, "st", _ASFake(copy.deepcopy(session)))
    return AS


def _today_tiles(AS, P):
    alloc, regime = AS.get_allocation(), AS.get_macro_regime()
    tiles = {t.card.key: t for t in P.build_verdict_tiles(
        alloc=alloc, alloc_error="", danger=None, danger_error="",
        danger_requested=False, regime=regime, regime_error="")}
    return tiles, alloc, regime


_WR_LIVE = {"traffic_light": "🟢 多頭市場", "health_score": 90.0, "regime": "bull",
            "effective_regime": "bull", "light": "🟢", "regime_source": "test"}
_WR_NO_HEALTH = dict(_WR_LIVE, health_score=None)


class TestB1SnapshotWhy:
    """先寫檔、warroom 健康分缺 ⇒ 位階走規則引擎快照（degraded）：why 屬實、無「不是這一輪算的」「AI 鎖定」。"""

    def _setup(self, l1, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        kw = _inputs()
        l1(kw["pmi_history"])
        assert RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW).written
        return _as_session(monkeypatch, {"warroom_summary": dict(_WR_NO_HEALTH)})

    def _whys(self, AS, P):
        from src.ui.tabs.tab_today import build_status_bar_cards, build_today_blocks
        from shared.regime_arbiter import SOURCE_FILE_RULE_ENGINE
        tiles, alloc, regime = _today_tiles(AS, P)
        assert regime["source"] == SOURCE_FILE_RULE_ENGINE and regime["is_loaded"]   # 前提自證
        bar = {c.key: P.contract_exit_retargeted(c) for c in build_status_bar_cards(regime)}
        blocks = {b.key: b for b in build_today_blocks(macro_state=regime)}
        summ = {t.card.key: t for t in P.build_summary_tiles(
            blocks["today.summary"].cards, danger=None, danger_error="",
            danger_requested=False)}
        return {"card3": tiles["verdict.regime"].card.note,
                "statusbar": bar["statusbar.macro"].note,
                "summary": summ["summary.regime"].card.note,
                "card1": tiles["verdict.exposure"].card.note}, alloc

    def test_snapshot_why_is_truthful(self, l1, tmp_path, monkeypatch):
        from src.ui.views import page_today as P
        AS = self._setup(l1, tmp_path, monkeypatch)
        notes, alloc = self._whys(AS, P)
        for name in ("card3", "statusbar", "summary"):
            n = notes[name]
            assert n.why == P.SNAPSHOT_SOURCE_WHY, name
            assert not any(x in n.why for x in _STALE_PHRASES), name
            assert "規則引擎快照" in n.why and "本輪按鈕剛寫的" in n.why
            assert n.where is P.EXIT_RETRY_HERE, name
            assert "快照" in n.now   # now 不動（沿用對面）

    def test_card1_unloaded_why_is_not_universal(self, l1, tmp_path, monkeypatch):
        from src.ui.views import page_today as P
        AS = self._setup(l1, tmp_path, monkeypatch)
        notes, alloc = self._whys(AS, P)
        assert not alloc.is_loaded
        why = notes["card1"].why
        assert "兩條來源本輪都沒有值" not in why
        assert "總經健康分本輪沒有值" in why and "有系統風險上限" in why
        assert notes["card1"].where is P.EXIT_RETRY_HERE

    def test_card1_unloaded_why_when_nothing(self, monkeypatch, tmp_path):
        from src.ui.views import page_today as P
        monkeypatch.chdir(tmp_path)
        AS = _as_session(monkeypatch, {"warroom_summary": dict(_WR_NO_HEALTH)})
        tiles, _, _ = _today_tiles(AS, P)
        # 兩條來源都沒有 ⇒ 契約 `source=unloaded` ⇒ 走既有 idle 那一句（「還沒叫」），不是本 helper
        assert tiles["verdict.exposure"].card.state == P.UI_IDLE
        why = P._alloc_unloaded_why({"health": None, "exposure_limit_pct": None})
        assert "總經健康分本輪沒有值" in why and "也沒有有效值" in why
        assert P._alloc_unloaded_why(None).startswith("L3 建議持股契約回報未評估")

    def test_mutant_why_not_retargeted(self, l1, tmp_path, monkeypatch):
        """突變：拿掉 why 的換句 → 狀態列／三欄摘要／卡③ 回到「AI 鎖定……不是這一輪算的」。"""
        from src.ui.views import page_today as P
        mod = _mutated_module("src/ui/views/page_today.py", (
            '    return SNAPSHOT_SOURCE_WHY if why and why == _tab_today_snapshot_why() else why',
            '    return why'))
        AS = self._setup(l1, tmp_path, monkeypatch)
        notes, _ = self._whys(AS, mod)
        for name in ("card3", "statusbar", "summary"):
            assert any(x in notes[name].why for x in _STALE_PHRASES), name
        assert P.SNAPSHOT_SOURCE_WHY not in notes["card3"].why


_PCT = re.compile(r"\d+\s*[%％]|\d+\s*[-–~～]\s*\d+")


def _no_pct(*texts):
    for t in texts:
        assert not _PCT.search(str(t or "")), t


class TestNoRiskCapMeansUndetermined:
    """客戶 Q-z34～36：新頁取不到有效系統風險上限 → 建議持股「無法判定」（灰），不印任何百分比。"""

    def _gate_asserts(self, P, tile):
        c = tile.card
        assert c.state == P.UI_EMPTY and c.value in (None, "")
        assert "無法判定" in c.note.now and c.note.why == P.RISK_CAP_UNAVAILABLE_WHY
        assert c.note.where is P.EXIT_RETRY_HERE
        _no_pct(c.note.now, c.note.why, c.value, tile.signal_text,
                *[v for _k, v in (tile.facts or ())])

    def _scenario(self, monkeypatch, tmp_path, kind, l1=None):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "macro_state.json"
        if kind == "expired":
            data = {"market_regime": "多頭", "systemic_risk_level": "安全", "exposure_limit_pct": 80,
                    "Macro_Phase": "環境正常",
                    "timestamp": (datetime.now(TPE) - timedelta(days=30)).strftime(MSL._TIMESTAMP_FMT)}
            f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        elif kind == "fail_safe":
            res = RC.compute_and_lock_risk_cap({}, now=NOW)
            assert not res.written and not f.exists()
        elif kind == "valid":
            kw = _inputs()
            l1(kw["pmi_history"])
            assert RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW).written
        return _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})

    @pytest.mark.parametrize("kind", ["missing", "expired", "fail_safe"])
    def test_today_card1_undetermined(self, l1, monkeypatch, tmp_path, kind):
        from src.ui.views import page_today as P
        AS = self._scenario(monkeypatch, tmp_path, kind)
        tiles, alloc, regime = _today_tiles(AS, P)
        assert alloc.is_loaded and alloc.final_hi is not None   # 前提：共用層照舊算得出區間（未改）
        assert regime["exposure_limit_pct"] is None
        self._gate_asserts(P, tiles["verdict.exposure"])

    @pytest.mark.parametrize("kind", ["missing", "expired", "fail_safe"])
    def test_hold_position_cap_undetermined(self, l1, monkeypatch, tmp_path, kind):
        from src.ui.views import page_hold as PH
        self._scenario(monkeypatch, tmp_path, kind)
        card, facts, sig = PH.build_position_cap_card(
            PH.load_allocation(PH.HoldRequest(submitted=True)))
        assert card.state == PH.UI_EMPTY and card.note.now == PH.RISK_CAP_UNAVAILABLE_NOW
        assert card.note.why == PH.RISK_CAP_UNAVAILABLE_WHY and sig == ""
        _no_pct(card.note.now, card.note.why, card.value, *[v for _k, v in facts])

    def test_valid_cap_regression(self, l1, monkeypatch, tmp_path):
        from src.ui.views import page_hold as PH
        from src.ui.views import page_today as P
        AS = self._scenario(monkeypatch, tmp_path, "valid", l1)
        tiles, alloc, _ = _today_tiles(AS, P)
        assert tiles["verdict.exposure"].card.state == P.UI_LIVE
        assert tiles["verdict.exposure"].card.value == alloc.range_text
        card, _, _ = PH.build_position_cap_card(PH.load_allocation(PH.HoldRequest(submitted=True)))
        assert card.state == PH.UI_LIVE and card.value == alloc.range_text

    def test_cap_name_matches_shared_layer(self):
        from shared.allocation_decision import build_allocation_decision
        from src.ui.views.risk_cap_gate import SYSTEM_RISK_CAP_NAME, has_system_risk_cap
        d = build_allocation_decision({"is_loaded": True, "regime": "bull", "health": 80.0,
                                       "defense": False, "exposure_limit_pct": 40})
        assert has_system_risk_cap(d.caps)
        assert [c.name for c in d.caps] == [SYSTEM_RISK_CAP_NAME]
        d2 = build_allocation_decision({"is_loaded": True, "regime": "bull", "health": 80.0,
                                        "defense": False, "exposure_limit_pct": None})
        assert not has_system_risk_cap(d2.caps) and d2.final_hi is not None

    def test_mutant_today_gate_removed(self, monkeypatch, tmp_path):
        mod = _mutated_module("src/ui/views/page_today.py", (
            "    if _alloc_state == UI_LIVE and not has_system_risk_cap(getattr(alloc, \"caps\", ())):",
            "    if False:"))
        AS = self._scenario(monkeypatch, tmp_path, "missing")
        tiles, alloc, _ = _today_tiles(AS, mod)
        c = tiles["verdict.exposure"].card
        assert c.state == mod.UI_LIVE and c.value == alloc.range_text   # 突變體照印區間 ⇒ 原版守衛必紅

    def test_mutant_hold_gate_removed(self, monkeypatch, tmp_path):
        mod = _mutated_module("src/ui/views/page_hold.py", (
            "    if _state == UI_LIVE and not alloc.has_risk_cap:", "    if False:"))
        self._scenario(monkeypatch, tmp_path, "missing")
        card, _, _ = mod.build_position_cap_card(mod.load_allocation(mod.HoldRequest(submitted=True)))
        assert card.state == mod.UI_LIVE


class TestTrioDisclosure:
    """`_trio_ok` 以實際寫入判定；沒寫齊 ⇒ RISK_CAP 報告揭露用的是 session 既有的哪幾個值。"""

    def test_partial_trio_disclosed_in_written_branch(self, monkeypatch, tmp_path):
        kw = _inputs()
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"], trio_keys=("m1b_m2_info",))
        assert _step(r, RS.STEP_TRIO).ok        # 前提：TRIO 步驟本身「成功」
        s = _step(r, RS.STEP_RISK_CAP)
        assert s.ok and not s.skipped and "已寫入 macro_state.json" in s.detail
        assert "沒寫齊" in s.detail and "`bias_info`" in s.detail and "`macro_info`" in s.detail
        assert "本輪用的是 session 既有的" in s.detail
        assert "`m1b_m2_info`" not in s.detail

    def test_full_trio_no_note(self, monkeypatch, tmp_path):
        kw = _inputs()
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"], trio_keys=_TRIO_ALL)
        assert "沒寫齊" not in _step(r, RS.STEP_RISK_CAP).detail

    def test_skipped_branch_also_discloses(self, monkeypatch, tmp_path):
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session={}, trio_keys=())
        s = _step(r, RS.STEP_RISK_CAP)
        assert s.skipped and "沒寫齊" in s.detail

    def _mutant_run(self, monkeypatch, tmp_path, swap):
        mod = _mutated_module("src/services/macro_refresh_service.py", swap)
        kw = _inputs()
        _run_refresh(monkeypatch, tmp_path, session=_session_from(kw), pmi_hist=kw["pmi_history"],
                     trio_keys=("m1b_m2_info",))         # 只為掛好替身與 L1 mock
        monkeypatch.setattr(mod, "st", RS.st)
        monkeypatch.setattr(mod, "_utc_now", lambda: NOW)
        r = mod.refresh_macro_now(mode=mod.MODE_WARM)
        return [x for x in r.steps if x.name == mod.STEP_RISK_CAP][0]

    def test_m11_trio_ok_always_true(self, monkeypatch, tmp_path):
        s = self._mutant_run(monkeypatch, tmp_path, (
            "    _trio_ok = len(_trio_written) == len(STEP_WRITES[STEP_TRIO])",
            "    _trio_ok = True"))
        assert "沒寫齊" not in s.detail    # 突變體吞掉揭露 ⇒ 原版 test_partial_trio_disclosed 必紅

    def test_m16_written_branch_drops_note(self, monkeypatch, tmp_path):
        s = self._mutant_run(monkeypatch, tmp_path, (
            '                  + "；薩姆規則目前無資料來源、未評估（不代表已通過）"\n'
            '                  + _rc_inputs_note)',
            '                  + "；薩姆規則目前無資料來源、未評估（不代表已通過）")'))
        assert s.ok and "沒寫齊" not in s.detail


class TestLowSeverity:
    @pytest.fixture(autouse=True)
    def _z66_m1b_m2_leg_on_reference(self, monkeypatch):
        """📌 批 Z66（客戶 2026-10-16 Q2，有意識的變更，⛔ 不是放寬）：M1B-M2 腿自 Z66 起在引擎停用。本類 m6（M1B／M2 進了計分才回資料月）比對的是**腿仍計分**的修前引擎 ⇒ 開關設 True 證原等價（不改 golden）；腿停用（開關 False）的行為由 tests/test_batch_z66.py 守。"""
        monkeypatch.setattr("shared.signal_thresholds.M1B_M2_LEG_ENABLED", True)

    def test_m6_single_side_month_none(self):
        import dataclasses
        b = _build(_inputs())
        assert RC._m1b_m2_data_month(b) == "2026-08"
        for drop in ("M1B_YoY_pct", "M2_YoY_pct"):
            nb = dataclasses.replace(b, macro_numbers=dict(b.macro_numbers, **{drop: None}))
            assert RC._m1b_m2_data_month(nb) is None, drop

    def test_m6_mutant(self):
        mod = _mutated_module("src/services/risk_cap_apply.py", (
            '    if nums.get("M1B_YoY_pct") is None or nums.get("M2_YoY_pct") is None:',
            '    if nums.get("M1B_YoY_pct") is None:'))
        import dataclasses
        b = _build(_inputs())
        nb = dataclasses.replace(b, macro_numbers=dict(b.macro_numbers, M2_YoY_pct=None))
        assert mod._m1b_m2_data_month(nb) == "2026-08"   # 突變體 ⇒ 原版 test_m6 必紅

    def test_m17_wording(self):
        for txt in (RC.REASON_FAIL_SAFE, RC.REASON_NOT_FINITE):
            assert "不寫檔（既有檔若有，保留不動）" in txt and "未覆寫" not in txt
        src = (REPO / "src/services/macro_refresh_service.py").read_text(encoding="utf-8")
        assert "新頁的建議持股顯示「無法判定」" in src and "＝ 沒有這條天花板" not in src
        rc = (REPO / "src/services/risk_cap_apply.py").read_text(encoding="utf-8")
        assert "＝ 沒有這條天花板" not in rc and "無法判定" in rc



# ══════════════════════════════════════════════════════════════════════════
# 8. 批 Z65 複驗 R2：兩處文字
# ══════════════════════════════════════════════════════════════════════════
class TestR2Wording:
    def test_r2_1_why_does_not_claim_a_cause(self):
        from src.ui.views.risk_cap_gate import RISK_CAP_UNAVAILABLE_WHY as W
        assert W == ("目前沒有可用的系統風險上限（尚未計算、本輪算不出來、檔案已過期或讀不出來都會如此）；"
                     "系統不會在缺上限的情況下給持股數字")
        assert "本輪無法計算" not in W and "7 天內也沒有" not in W

    def _band_text(self, mod):
        r = mod.MacroReadout(requested=True, loaded=True, regime="bull", health=60.0,
                             posture_label="積極", posture_range="30-50%", defense=False)
        rows = [(k, v) for k, v in mod.build_macro_stage_card(r)[1] if "姿態油門帶" in k]
        assert len(rows) == 1
        return rows[0][0] + rows[0][1]

    def test_r2_2_band_wording(self):
        from src.ui.views import page_hold as PH
        txt = self._band_text(PH)
        assert "exposure_limit_pct" not in txt and "系統風險上限任何一條天花板" in txt
        assert "這不是建議持股；系統風險上限取不到時，建議持股為『無法判定』，不得以本帶代替" in txt
        assert "30-50%" in txt   # 數字照舊（只改文字）

    def test_r2_mutants(self):
        m1 = _mutated_module("src/ui/views/risk_cap_gate.py",
                             ('    "目前沒有可用的系統風險上限（尚未計算、本輪算不出來、檔案已過期或讀不出來都會如此）；"',
                              '    "系統風險上限目前無法取得（本輪無法計算）；"'))
        assert "本輪無法計算" in m1.RISK_CAP_UNAVAILABLE_WHY      # 原版 r2_1 守衛必紅
        m2 = _mutated_module("src/ui/views/page_hold.py",
                             ('             "這不是建議持股；系統風險上限取不到時，建議持股為『無法判定』，不得以本帶代替。"\n', ""))
        assert "不得以本帶代替" not in self._band_text(m2)         # 原版 r2_2 守衛必紅
