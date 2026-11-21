"""System Action Aggregator：L0 契約欄位／frozen／輸入驗證＋A-T1 純度（M-A2；Architecture Gate §4.6）。"""
from __future__ import annotations

import ast
import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from shared import system_action_contract as C

_ROOT = Path(__file__).resolve().parent.parent
FILES = ("shared/system_action_contract.py", "src/services/system_action_aggregator.py")

# ══════════════════════════════════════════════════════════════════════
# A-T1 純度（AST）
# ══════════════════════════════════════════════════════════════════════
#: 只准 import 標準函式庫這幾個與 L0 `shared.*`（⛔ streamlit／src.ui*／src.data*／requests／任何 I/O 模組）。
_ALLOWED_IMPORT_ROOTS = {"__future__", "typing", "types", "dataclasses", "numbers", "shared"}
#: 寫入／時鐘／取數類呼叫（屬性名或函式名）。
_FORBIDDEN_CALLS = {"open", "exec", "eval", "__import__", "write", "write_text", "write_bytes", "to_csv",
                    "to_parquet", "to_json", "to_excel", "dump", "append_row", "append_rows", "update_cell",
                    "update_cells", "batch_update", "now", "today", "utcnow", "time", "sleep", "post",
                    "get_station_rows", "get_allocation", "get_macro_state"}


def purity_violations(text: str) -> list:
    out = []
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in _ALLOWED_IMPORT_ROOTS:
                    out.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level or mod.split(".")[0] not in _ALLOWED_IMPORT_ROOTS:
                out.append(f"from {mod} import")
        elif isinstance(node, ast.Attribute) and node.attr == "session_state":
            out.append("session_state")
        elif isinstance(node, ast.Name) and node.id in ("st", "session_state"):
            out.append(f"name {node.id}")
        elif isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else (fn.id if isinstance(fn, ast.Name) else "")
            if name in _FORBIDDEN_CALLS or name.endswith("_apply"):
                out.append(f"call {name}")
    return out


@pytest.mark.parametrize("rel", FILES)
def test_a_t1_purity_ast(rel):
    assert purity_violations((_ROOT / rel).read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("inject", [
    "import streamlit as st\n",
    "from src.ui.render import station_cards\n",
    "from src.data.core import data_loader\n",
    "import requests\n",
    "from src.compute.etf import dividend_station\n",
    "def _x(s):\n    return s.session_state\n",
    "def _x(p):\n    return open(p, 'w')\n",
    "def _x(ws):\n    ws.append_row([1])\n",
    "def _x(datetime):\n    return datetime.now()\n",
    "def _x(svc):\n    return svc.portfolio_apply()\n",
])
def test_a_t1_mutation_injected_impurity_is_caught(inject):
    """突變：在真檔尾端注入一行不純的程式 → AST 守衛必轉紅。"""
    for rel in FILES:
        assert purity_violations((_ROOT / rel).read_text(encoding="utf-8") + "\n" + inject) != []


def test_a_t1_runtime_import_is_headless():
    """實際載入兩檔後，sys.modules 不得出現 streamlit／requests／src.data／src.ui／src.compute（含傳遞）。

    以檔案路徑載入 aggregator（不經 `src/services/__init__.py`：那是既有 barrel，會連帶載入
    market_strategy 等重模組 —— 屬既有現況、與本模組自身的依賴無關）。"""
    code = ("import sys, importlib.util as u; import shared.system_action_contract; "
            "s=u.spec_from_file_location('sa_agg', 'src/services/system_action_aggregator.py'); "
            "m=u.module_from_spec(s); sys.modules['sa_agg']=m; s.loader.exec_module(m); "
            "bad=[m for m in sys.modules if m.split('.')[0] in ('streamlit','requests','gspread') "
            "or m.startswith(('src.data','src.ui','src.compute'))]; print(sorted(bad))")
    r = subprocess.run([sys.executable, "-c", code], cwd=_ROOT, capture_output=True, text=True, timeout=120,
                       env={"PYTHONPATH": str(_ROOT), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "[]", r.stdout


# ══════════════════════════════════════════════════════════════════════
# 複本 pin（L0 不得 import src.*；漂移即紅燈）
# ══════════════════════════════════════════════════════════════════════
def test_branch_codes_pinned_to_dividend_station():
    from src.compute.etf import dividend_station as ds
    assert (C.BRANCH_CUT, C.BRANCH_TAKE_PROFIT_FORCE, C.BRANCH_TAKE_PROFIT_PARTIAL, C.BRANCH_PAUSE_ADD,
            C.BRANCH_ADD, C.BRANCH_PREMIUM, C.BRANCH_CRUISE) == (
        ds.ACTION_CUT, ds.ACTION_TAKE_PROFIT_FORCE, ds.ACTION_TAKE_PROFIT_PARTIAL, ds.ACTION_PAUSE_ADD,
        ds.ACTION_ADD, ds.ACTION_PREMIUM, ds.ACTION_CRUISE)
    # 七分支恰為 dividend_station 的全部 ACTION_* 常數（多一個分支 → 本表須經 Gate 才能跟）
    src_codes = {v for k, v in vars(ds).items() if k.startswith("ACTION_") and isinstance(v, str)}
    assert set(C.ETF_BRANCHES) == src_codes
    assert C.LEVEL_UNJUDGED == ds.LEVEL_UNJUDGED


def test_swap_levels_pinned_to_station_specs_text():
    from shared import station_specs as SS
    txt = SS.SPECS_BY_KEY[SS.KEY_STOCK_SWAP].threshold_text
    assert txt == "🔴 換出 / 🟡 留意 / 🟢 續抱"
    assert C.SWAP_LEVELS[:3] == tuple(p.split()[0] for p in txt.split(" / "))
    assert C.SWAP_INSUFFICIENT == "⚪"


def test_system_risk_cap_name_pinned():
    from shared.allocation_decision import build_allocation_decision
    from src.ui.views.risk_cap_gate import SYSTEM_RISK_CAP_NAME
    d = build_allocation_decision({"is_loaded": True, "regime": "bull", "health": 80.0,
                                   "defense": False, "exposure_limit_pct": 40})
    assert C.SYSTEM_RISK_CAP_NAME == SYSTEM_RISK_CAP_NAME == [c.name for c in d.caps][0]


def test_rule_id_allowlist_copy_pinned():
    from shared.decision_digest_rules import RULE_ID_ALLOWLIST
    assert C.RULE_ID_ALLOWLIST_KEYS == frozenset(RULE_ID_ALLOWLIST)


def test_data_short_kinds_and_rule_version_pinned():
    from shared import holdings_data_short as HDS
    from shared.decision_digest_rules import ACTION_RULE_VERSION
    assert C.DATA_SHORT_KINDS == (HDS.SHORT_UNJUDGED, HDS.SHORT_PRICE, HDS.SHORT_FX)
    assert C.SOURCE_KIND_ACTION_BRANCH == ACTION_RULE_VERSION


def test_enums_exact():
    assert C.ACTION_CLASSES == ("actionable", "non_actionable", "unavailable", "not_evaluated", "undeterminable")
    assert C.GROUPS == ("加", "留", "換", "減")
    assert C.DAY_STATUSES == ("needs_action", "no_adjustment_today", "undeterminable")
    assert C.RISK_CAP_STATUSES == ("valid", "invalid", "missing")
    assert C.RISK_CAP_TAG_UNDETERMINABLE == "Risk Cap 無法判定"
    # DEC-124：not_evaluated 與 undeterminable 兩類分列（不同值、不同計數欄）
    assert C.ACTION_CLASS_NOT_EVALUATED != C.ACTION_CLASS_UNDETERMINABLE
    f = {x.name for x in dataclasses.fields(C.ActionCounts)}
    assert {"not_evaluated_n", "undeterminable_n", "unavailable_n", "today_n", "by_group",
            "incomplete_rows_n"} == f


# ══════════════════════════════════════════════════════════════════════
# 欄位／frozen
# ══════════════════════════════════════════════════════════════════════
def _item(**over):
    kw = dict(ticker="0050", name="元大台灣50", held=True, source_kind=C.SOURCE_KIND_ACTION_BRANCH,
              source_rule=C.BRANCH_CUT, formal_label="🔴 汰弱：x", action_class=C.ACTION_CLASS_ACTIONABLE,
              group=C.GROUP_REDUCE, counts_toward_today=True, risk_cap_tag="", rule_id="cut",
              data_short_kind="", stamp=C.ActionSourceStamp())
    kw.update(over)
    return C.ActionItem(**kw)


def test_output_field_names_match_gate_o1_o5():
    assert [f.name for f in dataclasses.fields(C.SystemActionState)] == [
        "items", "counts", "day_status", "day_basis", "risk_cap_state", "exposure_gate", "provenance"]
    assert {f.name for f in dataclasses.fields(C.ActionItem)} == {
        "ticker", "name", "held", "source_kind", "source_rule", "formal_label", "action_class", "group",
        "counts_toward_today", "risk_cap_tag", "rule_id", "data_short_kind", "stamp"}


def test_all_contract_types_frozen():
    from tests import _system_action_checks as K
    from src.services import system_action_aggregator as A
    st = K.run(A, C, K.golden_scenarios()["seven_branches"], risk="valid")
    for obj, attr in ((st, "day_status"), (st.items[0], "group"), (st.counts, "today_n"),
                      (st.day_basis, "judged_lights"), (st.risk_cap_state, "status"),
                      (st.exposure_gate, "status"), (st.provenance, "inputs"), (st.items[0].stamp, "as_of")):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, attr, None)
    with pytest.raises(TypeError):
        st.counts.by_group["加"] = 9
    with pytest.raises(TypeError):
        st.day_basis.tally["live"] = 9


@pytest.mark.parametrize("over, exc", [
    ({"action_class": "hold"}, ValueError),
    ({"group": "賣"}, ValueError),
    ({"source_kind": "ai"}, ValueError),
    ({"source_rule": "reduce_half"}, ValueError),
    ({"rule_id": "premium"}, ValueError),
    ({"risk_cap_tag": "🔴 Risk Cap 超限"}, ValueError),
    ({"risk_cap_tag": C.RISK_CAP_TAG_UNDETERMINABLE}, ValueError),     # 只能標在 add
    ({"data_short_kind": "stale"}, ValueError),
    ({"held": 1}, TypeError),
    ({"counts_toward_today": 1}, TypeError),
    ({"ticker": ""}, ValueError),
    ({"formal_label": ""}, ValueError),
    ({"action_class": C.ACTION_CLASS_NON_ACTIONABLE, "group": C.GROUP_HOLD, "rule_id": ""}, ValueError),
    ({"action_class": C.ACTION_CLASS_UNDETERMINABLE, "counts_toward_today": False, "rule_id": ""}, ValueError),
    ({"action_class": C.ACTION_CLASS_UNAVAILABLE, "group": "", "counts_toward_today": False, "rule_id": ""},
     ValueError),
    ({"source_rule": ""}, ValueError),
    ({"stamp": None}, TypeError),
])
def test_action_item_rejects_unknown_or_inconsistent(over, exc):
    with pytest.raises(exc):
        _item(**over)


def test_action_item_valid_variants():
    _item()
    _item(source_rule=C.BRANCH_ADD, group=C.GROUP_ADD, rule_id="add", risk_cap_tag=C.RISK_CAP_TAG_UNDETERMINABLE)
    _item(action_class=C.ACTION_CLASS_NOT_EVALUATED, group="", counts_toward_today=False, rule_id="")
    _item(action_class=C.ACTION_CLASS_UNAVAILABLE, group="", counts_toward_today=False, rule_id="",
          source_rule="")
    _item(source_kind=C.SOURCE_KIND_SWAP_LEVEL, source_rule=C.SWAP_OUT, group=C.GROUP_SWAP, rule_id="")


@pytest.mark.parametrize("kw, exc", [
    ({"status": "ok"}, ValueError),
    ({"status": "valid"}, ValueError),                                    # valid 須帶 pct
    ({"status": "valid", "system_cap_pct": True}, ValueError),
    ({"status": "valid", "system_cap_pct": 40.0}, ValueError),
    ({"status": "valid", "system_cap_pct": 40, "error": "x"}, ValueError),
    ({"status": "missing", "system_cap_pct": 40}, ValueError),
    ({"status": "missing", "error": "x"}, ValueError),
    ({"status": "missing", "system_cap_reason": "x"}, ValueError),
    ({"status": "invalid"}, ValueError),                                  # invalid 須帶 error
    ({"status": "missing", "stamp": ("a", "b")}, TypeError),
])
def test_risk_cap_state_validation(kw, exc):
    with pytest.raises(exc):
        C.RiskCapState(**kw)


def test_exposure_gate_only_undeterminable_and_stamp_no_empty_string():
    assert C.ExposureGate().status == "undeterminable"
    for bad in ("blocked", "ok", "exceeded", ""):
        with pytest.raises(ValueError):
            C.ExposureGate(status=bad)
    with pytest.raises(ValueError):
        C.ActionSourceStamp(as_of="")
    with pytest.raises(TypeError):
        C.ActionSourceStamp(source=123)


def test_counts_and_state_validation():
    g = {x: 0 for x in C.GROUPS}
    with pytest.raises(ValueError):
        C.ActionCounts(today_n=-1, by_group=g, not_evaluated_n=0, undeterminable_n=0, unavailable_n=0,
                       incomplete_rows_n=0)
    with pytest.raises(ValueError):
        C.ActionCounts(today_n=0, by_group={"加": 0}, not_evaluated_n=0, undeterminable_n=0, unavailable_n=0,
                       incomplete_rows_n=0)
    with pytest.raises(ValueError):
        C.ActionCounts(today_n=True, by_group=g, not_evaluated_n=0, undeterminable_n=0, unavailable_n=0,
                       incomplete_rows_n=0)
    cnt = C.ActionCounts(today_n=0, by_group=g, not_evaluated_n=0, undeterminable_n=0, unavailable_n=0,
                         incomplete_rows_n=0)
    basis = C.DayBasis(judged_lights=0, total_lights=0, tally={}, all_rows_judged=False,
                       cruise_gate_open=False, digest_data_short=True)
    common = dict(items=(), counts=cnt, day_basis=basis, risk_cap_state=C.RiskCapState(status="missing"),
                  exposure_gate=C.ExposureGate(), provenance=C.ActionProvenance(inputs=()))
    with pytest.raises(ValueError):
        C.SystemActionState(day_status="needs_action", **common)            # today_n=0 不得 needs_action
    with pytest.raises(ValueError):
        C.SystemActionState(day_status="all_good", **common)
    with pytest.raises(TypeError):
        C.SystemActionState(day_status="undeterminable", **{**common, "items": ("x",)})
    with pytest.raises(ValueError):
        C.ActionProvenance(inputs=(), contract_version="system_action.v0")
    with pytest.raises(TypeError):
        C.ActionProvenance(inputs=(("station", None),))
    C.SystemActionState(day_status="undeterminable", **common)
