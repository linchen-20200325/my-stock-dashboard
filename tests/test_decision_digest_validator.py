"""AB-2a Digest 層驗證與四態降級測試（fast lane）。

守的是 `shared/decision_digest_validator.py`：沿用 AB-0 `validate`＋AB-1 `validate_rule_ids`／
`validate_action_order`（不弱化），再加三個只收緊的自有檢查；availability 只由資料推導，不升格。
"""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from shared import decision_digest_terms as T
from shared.decision_digest import (
    ActionOrigin, Availability, DataStatus, DecisionDigest, MissingReason, RuleRef, StrategyType, validate,
)
from shared.decision_digest_rules import ACTION_RULE_VERSION, validate_strict
from shared.decision_digest_validator import (
    SECTION_ALL, SummaryState, assess_digest, derive_state, section_availability,
)
from tests.decision_digest_factory import (
    D, action, empty_digest, entry, force_set, make_digest, market_section, missing, ok_text, ok_val, stale_val,
)

REPO = Path(__file__).resolve().parents[1]


def codes(a):
    return {v.code for v in a.violations}


def gates(a):
    return set(a.failed_gates)


# ── 合規與四態 ────────────────────────────────────────────────────────────
def test_valid_contract_digest_is_partial_never_valid():
    a = assess_digest(make_digest())
    assert a.violations == () and a.invalid_sections == () and a.failed_gates == ()
    # 產業趨勢與策略分類的正式定義未核准 → 那幾段恆 UNAVAILABLE → 整體不可能 VALID
    assert a.state is SummaryState.PARTIAL
    av = dict(a.section_availability)
    assert tuple(av) == T.SECTION_KEYS
    assert av[T.SEC_INDUSTRY] is Availability.UNAVAILABLE
    assert av[T.SEC_MARKET] is Availability.PARTIAL      # 定義狀態段恆 UNAVAILABLE → 市場段至多 PARTIAL
    assert av[T.SEC_ACTIONS] is Availability.AVAILABLE


def test_all_unavailable_is_unavailable_not_neutral():
    a = assess_digest(empty_digest())
    assert a.state is SummaryState.UNAVAILABLE
    assert all(v is Availability.UNAVAILABLE for _, v in a.section_availability)


def test_partial_section_never_promotes_overall():
    d = make_digest(market_facts=[ok_text("market.regime", "bull"), missing("market.light"),
                                  ok_val("market.health", 72.5)])
    a = assess_digest(d)
    assert a.state is SummaryState.PARTIAL
    assert dict(a.section_availability)[T.SEC_MARKET] is Availability.PARTIAL


def test_derive_state_table():
    A, P, U = Availability.AVAILABLE, Availability.PARTIAL, Availability.UNAVAILABLE
    mk = lambda *xs: tuple(zip(T.SECTION_KEYS, xs))  # noqa: E731
    assert derive_state(mk(A, A, A, A, A)) is SummaryState.VALID
    assert derive_state(mk(U, U, U, U, U)) is SummaryState.UNAVAILABLE
    assert derive_state(mk(A, A, A, A, P)) is SummaryState.PARTIAL      # 一段 PARTIAL 就不是 VALID
    assert derive_state(mk(A, A, A, A, U)) is SummaryState.PARTIAL      # 一段 UNAVAILABLE 就不是 VALID
    assert derive_state(mk(U, U, U, U, A)) is SummaryState.PARTIAL      # 一段 AVAILABLE 就不是 UNAVAILABLE
    assert derive_state(()) is SummaryState.UNAVAILABLE


def test_strategy_section_with_unreadable_holdings_stays_unavailable():
    """持股事實全無（holdings UNAVAILABLE）時，即使 entry 帶策略分類，策略段也不得升格成 PARTIAL。"""
    d = make_digest(entries=[entry("0050", None, strategy=StrategyType.BUY_AND_HOLD, source="客戶設定")], items=[])
    assert d.holdings.availability is Availability.UNAVAILABLE
    assert section_availability(d, T.SEC_BUY_AND_HOLD) is Availability.UNAVAILABLE


def test_strategy_section_availability_derivation():
    d = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定")],
                    items=[action("0050", "t", "add")])
    assert section_availability(d, T.SEC_BUY_AND_HOLD) is Availability.PARTIAL    # 基本面判定未接線 → 至多 PARTIAL
    assert section_availability(d, T.SEC_CAPITAL_GAIN) is Availability.UNAVAILABLE
    with pytest.raises(ValueError):
        section_availability(d, "nope")


# ── 非 Digest 輸入：INVALID、不 raise ───────────────────────────────────────
@pytest.mark.parametrize("bad", [None, {}, "digest", 42, [], object(), make_digest().to_dict()])
def test_non_digest_is_invalid_not_raise(bad):
    a = assess_digest(bad)
    assert a.state is SummaryState.INVALID and a.invalid_sections == (SECTION_ALL,)
    assert a.section_availability == () and a.failed_gates == (T.GATE_AB0_CONTRACT,)
    assert len(a.violations) == 1 and a.violations[0].code == "type"


def test_digest_subclass_is_rejected():
    class Sub(DecisionDigest):
        pass
    d = make_digest()
    sub = Sub(**{f.name: getattr(d, f.name) for f in dataclasses.fields(d)})
    assert assess_digest(sub).state is SummaryState.INVALID


# ── 沿用 AB-0／AB-1 的檢查（逐項證明沒被弱化）─────────────────────────────────
def test_schema_version_drift_is_invalid():
    a = assess_digest(make_digest(schema_version="decision_digest.v0"))
    assert a.state is SummaryState.INVALID and "schema_version_mismatch" in codes(a)
    assert T.GATE_AB0_CONTRACT in gates(a) and SECTION_ALL in a.invalid_sections


def test_rule_id_not_in_allowlist_fails_with_rule_gate():
    d = make_digest()
    bad = dataclasses.replace(d.actions.items[0], rule=RuleRef("rule_x", ACTION_RULE_VERSION))
    d2 = dataclasses.replace(d, actions=dataclasses.replace(d.actions, items=(bad, d.actions.items[1])))
    a = assess_digest(d2)
    assert a.state is SummaryState.INVALID and "rule_not_allowlisted" in codes(a)
    assert T.GATE_AB1_RULE_ID in gates(a)


def test_rule_wrong_location_fails():
    d = make_digest()
    # 持股事實只能引行動分支碼；引 risk_cap 屬位置錯誤
    bad_fact = dataclasses.replace(d.holdings.entries[0].facts[0], rule=RuleRef("risk_cap", "risk_cap.v2"))
    e0 = dataclasses.replace(d.holdings.entries[0], facts=(bad_fact,))
    d2 = dataclasses.replace(d, holdings=dataclasses.replace(d.holdings, entries=(e0, d.holdings.entries[1])))
    a = assess_digest(d2)
    assert a.state is SummaryState.INVALID and "rule_wrong_location" in codes(a)
    assert T.GATE_AB1_RULE_ID in gates(a)


def test_rule_version_wrong_fails():
    d = make_digest()
    bad = dataclasses.replace(d.actions.items[0], rule=RuleRef("cut", "action_branch.v9"))
    d2 = dataclasses.replace(d, actions=dataclasses.replace(d.actions, items=(bad, d.actions.items[1])))
    a = assess_digest(d2)
    assert "rule_version_not_allowed" in codes(a) and a.state is SummaryState.INVALID


def test_action_origin_not_rule_layer_fails():
    d = make_digest()
    a0 = d.actions.items[0]
    force_set(a0, origin="ai_layer")                     # 模擬被竄改：行動來源不是規則層
    a = assess_digest(d)
    assert a.state is SummaryState.INVALID and "non_rule_origin" in codes(a)
    assert ActionOrigin.RULE_LAYER.value == "rule_layer"


def test_evidence_pointing_at_missing_fact_fails():
    d = make_digest(entries=[entry("0050", None), entry("0056", "t", "take_profit_force")],
                    items=[action("0056", "t", "take_profit_force", 1, evidence=("market.light",))])
    d = dataclasses.replace(d, market=market_section(
        (ok_text("market.regime", "bull"), missing("market.light"), ok_val("market.health", 72.5))))
    a = assess_digest(d)
    assert a.state is SummaryState.INVALID and "evidence_on_unusable_fact" in codes(a)


def test_dangling_evidence_ref_fails():
    d = make_digest(items=[action("0050", "🔴 汰弱：吃本金", "cut", 1, evidence=("nope.fact",))])
    a = assess_digest(d)
    assert "dangling_evidence_ref" in codes(a) and a.state is SummaryState.INVALID


def test_unavailable_holdings_with_available_actions_fails():
    d = make_digest(entries=[], items=[action("0050", "🔴 汰弱：吃本金", "cut", 1)])
    a = assess_digest(d)
    assert a.state is SummaryState.INVALID
    assert codes(a) & {"actions_available_without_holdings", "target_not_in_holdings"}
    assert "actions" in {k for k in a.invalid_sections} or SECTION_ALL in a.invalid_sections


def test_actions_available_with_holdings_unavailable_exact_code():
    d = make_digest(entries=[entry("0050", None)], items=[action("0050", "t", "add", 1, evidence=("market.health",))])
    assert d.holdings.availability is Availability.UNAVAILABLE
    a = assess_digest(d)
    assert "actions_available_without_holdings" in codes(a) and a.state is SummaryState.INVALID


def test_duplicate_fact_ids_fail():
    d = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.regime", "bear"),
                                  ok_val("market.health", 1.5)])
    a = assess_digest(d)
    assert "duplicate_fact_id" in codes(a) and a.state is SummaryState.INVALID


def test_action_order_violation_fails_with_order_gate():
    d = make_digest(items=[action("0056", "t", "take_profit_force", 1), action("0050", "u", "cut", 2)],
                    entries=[entry("0050", "u", "cut"), entry("0056", "t", "take_profit_force")])
    a = assess_digest(d)
    assert "action_order_violation" in codes(a) and T.GATE_AB1_ACTION_ORDER in gates(a)


def test_nan_and_inf_bypass_are_invalid_not_raise():
    for bad in (float("nan"), float("inf")):
        d = make_digest()
        force_set(d.market.facts[2], value=bad)
        a = assess_digest(d)
        assert a.state is SummaryState.INVALID and "bad_number" in codes(a)


def test_uninspectable_object_does_not_raise():
    d = make_digest()
    force_set(d, market=None)
    a = assess_digest(d)
    assert a.state is SummaryState.INVALID


def test_union_of_gates_equals_validate_strict():
    """assess 的三個沿用閘門合起來＝AB-1 `validate_strict`（不多不少，沒有弱化也沒有偷改語意）。"""
    cases = [make_digest(schema_version="x"), make_digest(entries=[], items=[action("0050", "t", "cut", 1)]),
             make_digest(items=[action("0056", "t", "take_profit_force", 1), action("0050", "u", "cut", 2)])]
    for d in cases:
        a = assess_digest(d)
        strict = {(v.code, v.path) for v in validate_strict(d)}
        mine = {(v.code, v.path) for v in a.violations
                if v.gate in (T.GATE_AB0_CONTRACT, T.GATE_AB1_RULE_ID, T.GATE_AB1_ACTION_ORDER)}
        assert mine == strict
    assert validate(make_digest()) == ()


# ── 自有檢查（只收緊）──────────────────────────────────────────────────────
@pytest.mark.parametrize("ch", ["\n", "​", "‮", "\x00", "﻿"])
def test_control_or_zero_width_in_texts_fail(ch):
    d = make_digest(market_facts=[ok_text("market.regime", f"bu{ch}ll"), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 72.5)])
    a = assess_digest(d)
    assert a.state is SummaryState.INVALID and "control_chars_in_text" in codes(a)
    assert T.GATE_AB2A_TEXT in gates(a)
    # 其餘位置也要擋
    d2 = make_digest(items=[action("0050", f"🔴 汰弱{ch}：吃本金", "cut", 1)],
                     entries=[entry("0050", "🔴 汰弱：吃本金", "cut")])
    assert "control_chars_in_text" in codes(assess_digest(d2))
    d3 = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source=f"客戶{ch}設定")],
                     items=[action("0050", "t", "add")])
    assert "control_chars_in_text" in codes(assess_digest(d3))


@pytest.mark.parametrize("fid", ["section:market", "holding:pf-A:0050"])
def test_reserved_ref_prefix_fails(fid):
    d = make_digest(market_facts=[ok_text(fid, "bull"), ok_text("market.light", "🟢"), ok_val("market.health", 1.5)])
    a = assess_digest(d)
    assert a.state is SummaryState.INVALID and "ref_id_reserved" in codes(a) and T.GATE_AB2A_REFS in gates(a)


def test_fact_and_action_id_collision_fails():
    d = make_digest(entries=[entry("0050", "t", "add")], items=[action("0050", "t", "add", 1)])
    force_set(d.actions.items[0], action_id="action_fact:pf-A:0050")
    a = assess_digest(d)
    assert a.state is SummaryState.INVALID and "ref_id_collision" in codes(a)


# ── invalid_sections 對映 ───────────────────────────────────────────────────
def test_invalid_sections_mapping_and_order():
    d = make_digest(entries=[], items=[action("0050", "t", "cut", 1)])
    a = assess_digest(d)
    # holdings 違規同時影響存股與資本利得；排序依固定段序
    assert list(a.invalid_sections) == [k for k in (*T.SECTION_KEYS, SECTION_ALL) if k in a.invalid_sections]
    d2 = make_digest()
    force_set(d2.holdings, unkeyed_count=-1)
    a2 = assess_digest(d2)
    assert T.SEC_BUY_AND_HOLD in a2.invalid_sections and T.SEC_CAPITAL_GAIN in a2.invalid_sections
    assert T.SEC_MARKET not in a2.invalid_sections and a2.section_availability == ()


def test_stale_fact_is_partial_not_available():
    d = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                  stale_val("market.health", 72.5)])
    assert d.market.availability is Availability.PARTIAL
    assert assess_digest(d).state is SummaryState.PARTIAL


def test_missing_reason_enum_pinned():
    assert MissingReason.NOT_DEFINED.value == "not_defined" and DataStatus.OK.value == "ok"
    assert set(T.MISSING_REASON_LABELS) >= {m.value for m in MissingReason}   # 每個缺值原因都有顯示標籤
    assert D.isoformat() == "2026-10-26"


# ── 邊界：AB-0 沒被改、新檔不碰 UI／AI ───────────────────────────────────────
NEW_FILES = ["shared/decision_digest_terms.py", "shared/decision_digest_validator.py",
             "shared/decision_digest_grounding.py", "src/services/decision_digest_summary.py"]
FORBIDDEN_IMPORT_ROOTS = {"streamlit", "requests", "httpx", "urllib", "urllib3", "aiohttp", "socket", "anthropic",
                          "openai", "google", "gspread", "pandas", "numpy", "yfinance", "app"}


def _imports(rel):
    tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            out.append(n.module or "")
    return out


@pytest.mark.parametrize("rel", NEW_FILES)
def test_new_files_have_no_io_ai_or_ui_imports(rel):
    for mod in _imports(rel):
        assert mod.split(".")[0] not in FORBIDDEN_IMPORT_ROOTS, f"{rel} imports {mod}"
        if rel.startswith("shared/"):
            assert not mod.startswith("src"), f"L0 {rel} 不得 import src.*：{mod}"


@pytest.mark.parametrize("rel", ["app.py", "shared/ia_nav.py"])
def test_app_and_nav_do_not_import_ab2a(rel):
    for mod in _imports(rel):
        assert "decision_digest" not in mod, f"{rel} 不得直接 import {mod}"
