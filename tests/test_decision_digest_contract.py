"""AB-0 Decision Digest 契約測試（fast lane）。

守的是 `shared/decision_digest.py` 的不變量（DEC-092；C §2／§3／§4／§7.2）：
missing ≠ 0、unavailable ≠ neutral、AI 不得為數值／行動來源、portfolio_id+symbol 鍵、
NaN／inf／bool 拒收、naive datetime 拒收、L0 只用 stdlib、不被 app 啟動路徑 import。
"""
from __future__ import annotations

import ast
import dataclasses
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import shared.decision_digest as dd
from shared.decision_digest import (
    MAX_ACTIONS, SCHEMA_VERSION, ActionOrigin, ActionRef, ActionsSection, AiParticipation,
    Availability, DataStatus, DecisionDigest, DefinitionSection, DefinitionState, Fact,
    FactSection, HoldingEntry, HoldingKey, HoldingsSection, MissingReason, Provenance,
    RiskCapSection, RuleRef, StrategyType, assert_valid, derive_availability, validate,
)

REPO = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO / "shared" / "decision_digest.py"
TZ8 = timezone(timedelta(hours=8))
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)
D = date(2026, 10, 24)
RULE = RuleRef("rule_x", "rule_x.v1")


# ── builders ────────────────────────────────────────────────────────────
def prov(as_of=D, fetched_at=NOW, source="SRC:x"):
    return Provenance(source=source, as_of=as_of, fetched_at=fetched_at)


def ok_fact(fid, value=1.5, rule=RULE, **kw):
    return Fact(fact_id=fid, status=DataStatus.OK, provenance=prov(), value=value, rule=rule, **kw)


def missing_fact(fid, rule=RULE, reason=MissingReason.NO_INPUT):
    return Fact(fact_id=fid, status=DataStatus.MISSING, provenance=prov(as_of=None, fetched_at=None),
                missing_reason=reason, rule=rule)


def undefined():
    return DefinitionSection(definition=DefinitionState.NOT_DEFINED)


def risk_cap(valid=True):
    if valid:
        return RiskCapSection(cap_valid=True, cap_pct=ok_fact("cap", 60.0, unit="%"),
                              exposure_lo_pct=ok_fact("lo", 40.0, unit="%"),
                              exposure_hi_pct=ok_fact("hi", 60.0, unit="%"),
                              availability=Availability.AVAILABLE)
    return RiskCapSection(cap_valid=False, cap_pct=missing_fact("cap"),
                          exposure_lo_pct=missing_fact("lo"), exposure_hi_pct=missing_fact("hi"),
                          availability=Availability.UNAVAILABLE, missing_reason=MissingReason.NO_INPUT)


K1 = HoldingKey("pf-A", "0050")
K2 = HoldingKey("pf-B", "0050")


def action(aid="a1", target=K1, refs=("cap",), rank=None):
    return ActionRef(action_id=aid, text="（規則層原樣文字）", origin=ActionOrigin.RULE_LAYER,
                     rule=RULE, evidence_refs=refs, target=target, priority_rank=rank)


def digest(**over):
    base = dict(
        generated_at=NOW,
        market=FactSection(availability=Availability.AVAILABLE,
                           facts=(ok_fact("regime", value=None, text="（上游標籤原樣）"),)),
        tw_trend=undefined(), intl_trend=undefined(),
        valuation=DefinitionSection(definition=DefinitionState.RESEARCH_ONLY),
        industry=undefined(),
        holdings=HoldingsSection(availability=Availability.AVAILABLE,
                                 entries=(HoldingEntry(K1, facts=(ok_fact("h1"),)),
                                          HoldingEntry(K2, facts=(ok_fact("h2"),)))),
        risk_cap=risk_cap(),
        actions=ActionsSection(availability=Availability.AVAILABLE, items=(action(),)),
    )
    base.update(over)
    return DecisionDigest(**base)


def codes(d):
    return {v.code for v in validate(d)}


def force(obj, **kw):
    """繞過 frozen＋__post_init__（模擬上游 bug），用來測 validate 的重驗能力。"""
    for k, v in kw.items():
        object.__setattr__(obj, k, v)
    return obj


# ── 正例 ────────────────────────────────────────────────────────────────
def test_valid_digest_passes_and_serializes_to_json():
    d = digest()
    assert validate(d) == ()
    assert_valid(d)
    out = d.to_dict()
    json.dumps(out, ensure_ascii=False)  # JSON 可序列化
    assert out["schema_version"] == SCHEMA_VERSION
    assert out["holdings"]["entries"][0]["strategy"] == "未分類"
    assert out["ai_participation"] == "rule_only"


# ── 列舉成員鎖死（unavailable ≠ neutral；無方向值；AI 不得產值） ─────────────
def test_enum_member_sets_are_locked():
    assert {m.value for m in DataStatus} == {"ok", "stale", "missing", "proxy", "failed", "invalid"}
    assert {m.value for m in MissingReason} == {"no_input", "fetch_failed", "not_enough_history",
                                                 "not_applicable", "contract_drift", "no_variation",
                                                 "not_defined", "not_wired"}
    assert {m.value for m in Availability} == {"available", "partial", "unavailable"}
    assert {m.value for m in AiParticipation} == {"rule_only", "ai_explained", "ai_rejected"}
    assert {m.value for m in StrategyType} == {"存股", "資本利得", "未分類"}
    assert {m.value for m in DefinitionState} == {"尚未定義", "研究框架，未啟用"}
    assert {m.value for m in ActionOrigin} == {"rule_layer"}


@pytest.mark.parametrize("word", ["neutral", "normal", "hold", "中性", "正常", "續抱", "維持",
                                  "bull", "bear", "偏多", "偏空", "變強", "轉弱", "減碼", "多頭", "空頭",
                                  "ai_generated", "ai"])
def test_no_judgement_or_neutral_values_anywhere(word):
    for enum_cls in (DataStatus, Availability, AiParticipation, StrategyType, DefinitionState,
                     ActionOrigin, MissingReason):
        for m in enum_cls:
            assert m.value.lower() != word and m.name.lower() != word, (enum_cls, m)
    for m in DefinitionState:
        for w in ("多", "空", "強", "弱", "漲", "跌"):
            assert w not in m.value


# ── Fact：missing ≠ 0、value/status 綁定 ───────────────────────────────────
def test_missing_is_null_not_zero_in_to_dict():
    d = digest(risk_cap=risk_cap(valid=False),
               actions=ActionsSection(Availability.UNAVAILABLE, missing_reason=MissingReason.NO_INPUT))
    rc = d.to_dict()["risk_cap"]
    assert rc["cap_pct"]["value"] is None and rc["cap_pct"]["status"] == "missing"
    assert rc["cap_pct"]["text"] is None
    assert rc["cap_pct"]["provenance"]["as_of"] is None
    assert '"value": 0' not in json.dumps(rc)


@pytest.mark.parametrize("status", [DataStatus.MISSING, DataStatus.FAILED])
def test_missing_or_failed_status_rejects_value(status):
    with pytest.raises(ValueError, match="value_with_missing_status"):
        Fact("f", status, prov(), value=0.0, missing_reason=MissingReason.NO_INPUT)
    with pytest.raises(ValueError, match="value_with_missing_status"):
        Fact("f", status, prov(), text="x", missing_reason=MissingReason.NO_INPUT)


@pytest.mark.parametrize("status", [DataStatus.OK, DataStatus.STALE, DataStatus.PROXY])
def test_none_value_rejects_present_status(status):
    with pytest.raises(ValueError, match="missing_value_with_present_status"):
        Fact("f", status, prov())


def test_missing_requires_reason_and_ok_forbids_reason():
    with pytest.raises(ValueError, match="missing_reason_required"):
        Fact("f", DataStatus.MISSING, prov(as_of=None))
    with pytest.raises(ValueError, match="missing_reason_forbidden"):
        Fact("f", DataStatus.OK, prov(), value=1.0, missing_reason=MissingReason.NO_INPUT)


@pytest.mark.parametrize("status", [DataStatus.OK, DataStatus.STALE])
def test_ok_and_stale_require_as_of(status):
    with pytest.raises(ValueError, match="dated_status_without_as_of"):
        Fact("f", status, prov(as_of=None), value=1.0)
    Fact("f", status, prov(), value=1.0)


def test_proxy_may_lack_as_of():
    Fact("f", DataStatus.PROXY, prov(as_of=None), value=1.0)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, False, "1.0"])
def test_bad_numbers_rejected(bad):
    with pytest.raises(ValueError, match="bad_number"):
        Fact("f", DataStatus.OK, prov(), value=bad)


def test_zero_is_a_real_value():
    f = Fact("f", DataStatus.OK, prov(), value=0)
    assert f.value == 0  # 真 0 合法；與缺值（None）區分


def test_value_and_text_mutually_exclusive_and_empty_text_rejected():
    with pytest.raises(ValueError, match="value_and_text"):
        Fact("f", DataStatus.OK, prov(), value=1.0, text="x")
    with pytest.raises(ValueError, match="blank_str"):
        Fact("f", DataStatus.OK, prov(), text="   ")


# ── Provenance ──────────────────────────────────────────────────────────
def test_provenance_rules():
    Provenance("S", as_of=date(2025, 12, 31), fetched_at=datetime(2026, 1, 1, tzinfo=TZ8))
    with pytest.raises(ValueError, match="naive_datetime"):
        Provenance("S", fetched_at=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="blank_str"):
        Provenance("  ")
    with pytest.raises(ValueError, match="as_of"):
        Provenance("S", as_of=datetime(2026, 1, 1, tzinfo=TZ8))


def test_naive_generated_at_rejected():
    assert "naive_datetime" in codes(digest(generated_at=datetime(2026, 10, 27)))
    with pytest.raises(ValueError):
        digest(generated_at=datetime(2026, 10, 27)).to_dict()


def test_schema_version_mismatch():
    assert "schema_version_mismatch" in codes(digest(schema_version="other"))


# ── HoldingKey／策略 ─────────────────────────────────────────────────────
def test_same_symbol_different_portfolio_can_have_different_strategy():
    h1 = HoldingEntry(K1, StrategyType.BUY_AND_HOLD, strategy_source="sheet:col", facts=(ok_fact("h1"),))
    h2 = HoldingEntry(K2, StrategyType.CAPITAL_GAIN, strategy_source="sheet:col", facts=(ok_fact("h2"),))
    d = digest(holdings=HoldingsSection(Availability.AVAILABLE, entries=(h1, h2)))
    assert validate(d) == ()


def test_duplicate_holding_key_rejected():
    with pytest.raises(ValueError, match="duplicate_holding_key"):
        HoldingsSection(Availability.AVAILABLE, entries=(HoldingEntry(K1), HoldingEntry(HoldingKey("pf-A", "0050"))))


@pytest.mark.parametrize("pid,sym", [("", "0050"), ("   ", "0050"), ("pf", ""), ("pf", " "), (None, "0050")])
def test_blank_portfolio_id_or_symbol_rejected(pid, sym):
    with pytest.raises(ValueError, match="bad_key"):
        HoldingKey(pid, sym)


def test_strategy_default_unclassified_and_source_rules():
    assert HoldingEntry(K1).strategy is StrategyType.UNCLASSIFIED
    with pytest.raises(ValueError, match="source_required"):
        HoldingEntry(K1, StrategyType.BUY_AND_HOLD)
    with pytest.raises(ValueError, match="source_on_unclassified"):
        HoldingEntry(K1, StrategyType.UNCLASSIFIED, strategy_source="x")
    with pytest.raises(ValueError, match="type"):
        HoldingEntry(K1, "存股", strategy_source="x")  # 裸字串不得冒充列舉


def test_holdings_availability_is_derived_from_entry_facts():
    HoldingsSection(Availability.UNAVAILABLE, missing_reason=MissingReason.FETCH_FAILED)
    with pytest.raises(ValueError, match="missing_reason_required"):
        HoldingsSection(Availability.UNAVAILABLE)
    # 0 筆 → unavailable；不得宣稱 available
    with pytest.raises(ValueError, match="availability_mismatch"):
        HoldingsSection(Availability.AVAILABLE)
    # 有鍵但全部缺值 → unavailable（鍵仍可保留）
    HoldingsSection(Availability.UNAVAILABLE, entries=(HoldingEntry(K1, facts=(missing_fact("m"),)),),
                    missing_reason=MissingReason.NO_INPUT)
    with pytest.raises(ValueError, match="availability_mismatch"):
        HoldingsSection(Availability.AVAILABLE, entries=(HoldingEntry(K1, facts=(missing_fact("m"),)),))
    with pytest.raises(ValueError, match="availability_mismatch"):
        HoldingsSection(Availability.AVAILABLE,
                        entries=(HoldingEntry(K1, facts=(ok_fact("a"),)), HoldingEntry(K2, facts=(missing_fact("b"),))))
    HoldingsSection(Availability.PARTIAL,
                    entries=(HoldingEntry(K1, facts=(ok_fact("a"),)), HoldingEntry(K2, facts=(missing_fact("b"),))))


# ── Actions ──────────────────────────────────────────────────────────────
def test_more_than_three_actions_rejected():
    items = tuple(action(aid=f"a{i}") for i in range(MAX_ACTIONS + 1))
    with pytest.raises(ValueError, match="too_many_actions"):
        ActionsSection(Availability.AVAILABLE, items=items)
    ActionsSection(Availability.AVAILABLE, items=items[:MAX_ACTIONS])


def test_action_requires_evidence_rule_and_rule_origin():
    with pytest.raises(ValueError, match="empty"):
        action(refs=())
    with pytest.raises(ValueError, match="bad_key"):
        action(refs=("",))
    with pytest.raises(ValueError, match="rule_version"):
        ActionRef("a", "t", ActionOrigin.RULE_LAYER, RuleRef("r", ""), ("x",))
    with pytest.raises(ValueError, match="non_rule_origin"):
        ActionRef("a", "t", "ai", RULE, ("x",))
    with pytest.raises(ValueError, match="non_rule_origin"):
        ActionRef("a", "t", AiParticipation.AI_EXPLAINED, RULE, ("x",))


def test_action_ai_origin_injected_after_construction_is_caught_by_validate():
    a = force(action(), origin="ai_generated")
    d = digest(actions=force(ActionsSection(Availability.AVAILABLE, items=(action(),)), items=(a,)))
    assert "non_rule_origin" in codes(d)


def test_action_bad_rank_and_duplicate_rank():
    with pytest.raises(ValueError, match="bad_rank"):
        action(rank=0)
    with pytest.raises(ValueError, match="bad_rank"):
        action(rank=True)
    with pytest.raises(ValueError, match="duplicate_rank"):
        ActionsSection(Availability.AVAILABLE, items=(action("a1", rank=1), action("a2", rank=1)))


def test_dangling_evidence_and_target_outside_holdings():
    d = digest(actions=ActionsSection(Availability.AVAILABLE,
                                      items=(action(refs=("nope",), target=HoldingKey("pf-Z", "2330")),)))
    c = codes(d)
    assert {"dangling_evidence_ref", "target_not_in_holdings"} <= c


def test_actions_unavailable_must_be_empty():
    with pytest.raises(ValueError, match="items_when_unavailable"):
        ActionsSection(Availability.UNAVAILABLE, items=(action(),), missing_reason=MissingReason.NO_INPUT)
    ActionsSection(Availability.AVAILABLE)  # 規則跑了、無行動：合法，與「判不出來」區分


# ── 定義狀態段：未定義 ≠ 可判斷 ─────────────────────────────────────────────
def test_definition_section_cannot_be_available():
    with pytest.raises(ValueError, match="undefined_but_available"):
        DefinitionSection(DefinitionState.NOT_DEFINED, availability=Availability.AVAILABLE, missing_reason=None)
    with pytest.raises(ValueError, match="undefined_but_available"):
        DefinitionSection(DefinitionState.NOT_DEFINED, availability=Availability.PARTIAL, missing_reason=None)
    with pytest.raises(ValueError, match="type"):
        DefinitionSection("偏多")


def test_definition_section_has_no_verdict_field():
    names = {f.name for f in dataclasses.fields(DefinitionSection)}
    assert names == {"definition", "missing_reason", "availability", "series_ref", "observations"}


def test_definition_observations_need_rule():
    with pytest.raises(ValueError, match="rule_required"):
        DefinitionSection(DefinitionState.NOT_DEFINED, observations=(ok_fact("q", text=None, rule=None),))


# ── 可得性 ───────────────────────────────────────────────────────────────
def test_derive_availability():
    assert derive_availability(()) is Availability.UNAVAILABLE
    assert derive_availability((missing_fact("a"),)) is Availability.UNAVAILABLE
    assert derive_availability((ok_fact("a"),)) is Availability.AVAILABLE
    assert derive_availability((ok_fact("a"), missing_fact("b"))) is Availability.PARTIAL
    assert derive_availability((Fact("a", DataStatus.PROXY, prov(), value=1.0),)) is Availability.PARTIAL


def test_unavailable_cannot_be_declared_available():
    with pytest.raises(ValueError, match="availability_mismatch"):
        FactSection(Availability.AVAILABLE, facts=(missing_fact("a"),))
    with pytest.raises(ValueError, match="availability_mismatch"):
        FactSection(Availability.AVAILABLE, facts=(ok_fact("a"), missing_fact("b")))
    with pytest.raises(ValueError, match="missing_reason_required"):
        FactSection(Availability.UNAVAILABLE)


# ── Risk Cap ─────────────────────────────────────────────────────────────
def test_invalid_cap_must_have_no_value():
    with pytest.raises(ValueError, match="invalid_cap_has_value"):
        RiskCapSection(cap_valid=False, cap_pct=ok_fact("cap", 60.0),
                       exposure_lo_pct=missing_fact("lo"), exposure_hi_pct=missing_fact("hi"),
                       availability=Availability.PARTIAL)


def test_risk_cap_requires_rule_domain_and_order():
    with pytest.raises(ValueError, match="rule_required"):
        RiskCapSection(True, ok_fact("cap", 60.0, rule=None), ok_fact("lo", 1.0), ok_fact("hi", 2.0),
                       Availability.AVAILABLE)
    with pytest.raises(ValueError, match="pct_out_of_domain"):
        RiskCapSection(True, ok_fact("cap", 160.0), ok_fact("lo", 1.0), ok_fact("hi", 2.0),
                       Availability.AVAILABLE)
    with pytest.raises(ValueError, match="exposure_lo_gt_hi"):
        RiskCapSection(True, ok_fact("cap", 60.0), ok_fact("lo", 70.0), ok_fact("hi", 50.0),
                       Availability.AVAILABLE)


def test_duplicate_fact_id_across_digest():
    d = digest(market=FactSection(Availability.AVAILABLE, facts=(ok_fact("cap", value=50.0),)))
    assert "duplicate_fact_id" in codes(d)


# ── AI 參與 ──────────────────────────────────────────────────────────────
def test_ai_participation_consistency():
    assert "rejected_without_checks" in codes(digest(ai_participation=AiParticipation.AI_REJECTED))
    assert validate(digest(ai_participation=AiParticipation.AI_REJECTED, ai_failed_checks=("G2",))) == ()
    assert "checks_without_ai" in codes(digest(ai_failed_checks=("G2",)))
    assert "checks_without_ai" in codes(digest(ai_passed_checks=("G1",)))
    assert "explained_without_checks" in codes(digest(ai_participation=AiParticipation.AI_EXPLAINED))
    assert validate(digest(ai_participation=AiParticipation.AI_EXPLAINED, ai_passed_checks=("G1", "G2"))) == ()
    assert "explained_with_failures" in codes(digest(ai_participation=AiParticipation.AI_EXPLAINED,
                                                     ai_passed_checks=("G1",), ai_failed_checks=("G2",)))
    for bad in (("g1",), ("G0",), ("",), ("G1 ",), (1,), ["G1"]):
        assert codes(digest(ai_participation=AiParticipation.AI_EXPLAINED, ai_passed_checks=bad)) & {
            "bad_check_id", "not_tuple"}, bad
    assert "type" in codes(digest(ai_participation="ai_generated_values"))


def test_fact_has_no_ai_source_field():
    # Fact／ActionRef 沒有任何欄位能標示「AI 產生」—— 數值與行動只能來自規則／資料層
    for cls in (Fact, ActionRef, RiskCapSection):
        assert not any("ai" in f.name.split("_") for f in dataclasses.fields(cls)), cls


# ── validate 收集全部違規、assert_valid Fail Loud ─────────────────────────
def test_validate_returns_all_violations_and_rechecks_leaves():
    bad_fact = force(ok_fact("x"), value=float("nan"))
    d = digest(generated_at=datetime(2026, 1, 1), schema_version="zz",
               market=force(FactSection(Availability.AVAILABLE, facts=(ok_fact("x"),)), facts=(bad_fact,)))
    c = codes(d)
    assert {"naive_datetime", "schema_version_mismatch", "bad_number"} <= c
    with pytest.raises(ValueError) as ei:
        assert_valid(d)
    for code in ("naive_datetime", "schema_version_mismatch", "bad_number"):
        assert code in str(ei.value)


def test_validate_non_digest():
    assert validate({"x": 1})[0].code == "type"


# ── 架構守衛：L0 stdlib only；不被 app 啟動路徑 import ───────────────────────
_STDLIB_ALLOWED = {"__future__", "math", "numbers", "re", "unicodedata", "dataclasses", "datetime",
                   "enum", "typing"}


def test_module_imports_stdlib_only():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            assert n.level == 0, "不得相對 import"
            mods.add(n.module.split(".")[0])
    assert mods <= _STDLIB_ALLOWED, mods - _STDLIB_ALLOWED
    for m in mods:
        assert m in sys.stdlib_module_names or m == "__future__"


@pytest.mark.parametrize("rel", ["app.py", "shared/ia_nav.py"])
def test_not_imported_by_boot_path(rel):
    tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert not any(a.name == "shared.decision_digest" for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            assert n.module != "shared.decision_digest"
            if n.module == "shared":
                assert not any(a.name == "decision_digest" for a in n.names)


def test_dataclasses_are_frozen():
    for name in dd.__all__:
        obj = getattr(dd, name)
        if isinstance(obj, type) and dataclasses.is_dataclass(obj):
            assert obj.__dataclass_params__.frozen, name


# ══ QA 第二輪（總管裁定 1～12）════════════════════════════════════════════
import copy  # noqa: E402
import random  # noqa: E402

import numpy as np  # noqa: E402

from shared.decision_digest import MISS_CODE_TO_REASON, PLACEHOLDER_TEXTS, TW_TZ  # noqa: E402


def _walk_enums(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_enums(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_enums(v)
    else:
        yield obj


# 1. to_dict：Enum 輸出 .value 純字串；numpy 數值轉 Python 原生
def test_to_dict_enums_are_plain_str():
    d = digest()
    out = d.to_dict()
    assert type(out["ai_participation"]) is str and out["ai_participation"] == "rule_only"
    assert type(out["market"]["availability"]) is str
    assert type(out["holdings"]["entries"][0]["strategy"]) is str
    assert type(out["market"]["facts"][0]["status"]) is str
    for leaf in _walk_enums(out):
        assert leaf is None or type(leaf) in (str, int, float, bool), type(leaf)
    j = json.dumps(out, ensure_ascii=False)
    for cls in ("DataStatus.", "Availability.", "StrategyType.", "AiParticipation.", "DefinitionState."):
        assert cls not in j


def test_numpy_numbers_accepted_and_converted():
    f1 = Fact("n1", DataStatus.OK, prov(), value=np.float64(1.25))
    f2 = Fact("n2", DataStatus.OK, prov(), value=np.int64(3))
    d = digest(market=FactSection(Availability.AVAILABLE, facts=(f1, f2)))
    facts = d.to_dict()["market"]["facts"]
    assert type(facts[0]["value"]) is float and facts[0]["value"] == 1.25
    assert type(facts[1]["value"]) is int and facts[1]["value"] == 3
    json.dumps(facts)


@pytest.mark.parametrize("bad", [np.bool_(True), np.float64("nan"), np.float64("inf"), 10 ** 400, -(10 ** 400)])
def test_numpy_bool_nan_and_overflow_rejected(bad):
    with pytest.raises(ValueError, match="bad_number"):
        Fact("f", DataStatus.OK, prov(), value=bad)


# 2. validate 永不 raise
def test_overflow_injected_is_violation_not_exception():
    f = force(ok_fact("x"), value=10 ** 400)
    d = digest(market=force(FactSection(Availability.AVAILABLE, facts=(ok_fact("x"),)), facts=(f,)))
    assert "bad_number" in codes(d)


_GARBAGE = [None, [], {}, [1], {"a": 1}, set(), float("nan"), 10 ** 400, object(), "", " x ", True,
            np.bool_(False), (1, 2), ("a",), -1, 0, "ok", datetime(2026, 1, 1)]


def fresh_digest():
    """深拷貝：fuzz 會竄改節點，不得汙染模組級共用物件（RULE／K1／K2）。"""
    return copy.deepcopy(digest())


def _dataclass_nodes(obj):
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        yield obj
        for f in dataclasses.fields(obj):
            yield from _dataclass_nodes(getattr(obj, f.name))
    elif isinstance(obj, tuple):
        for x in obj:
            yield from _dataclass_nodes(x)


def test_fuzz_validate_never_raises():
    rng = random.Random(20261027)
    n_violation = 0
    for _ in range(600):
        d = fresh_digest()
        nodes = list(_dataclass_nodes(d))
        for _k in range(rng.randint(1, 3)):
            node = rng.choice(nodes)
            fld = rng.choice(dataclasses.fields(node)).name
            object.__setattr__(node, fld, rng.choice(_GARBAGE))
        res = validate(d)  # 不得 raise
        assert isinstance(res, tuple)
        n_violation += bool(res)
        with pytest.raises(ValueError):
            if res:
                assert_valid(d)
            else:
                raise ValueError("garbage happened to be valid")
    assert n_violation > 500


@pytest.mark.parametrize("cls", [Fact, Provenance, HoldingKey, HoldingEntry, ActionRef, FactSection,
                                 DefinitionSection, HoldingsSection, RiskCapSection, ActionsSection])
def test_uninitialised_objects_reported_not_raised(cls):
    blank = cls.__new__(cls)
    # 塞到每一個可能的位置（每個位置各用一份新的 digest）
    setters = (
        lambda d: force(d, market=blank),
        lambda d: force(d.market, facts=(blank,)),
        lambda d: force(d.holdings, entries=(blank,)),
        lambda d: force(d.actions, items=(blank,)),
        lambda d: force(d.risk_cap, cap_pct=blank),
        lambda d: force(d.tw_trend, observations=(blank,)),
        lambda d: force(d.holdings.entries[0], key=blank),
        lambda d: force(d.market.facts[0], provenance=blank),
    )
    for setter in setters:
        d = fresh_digest()
        setter(d)
        assert validate(d), cls
    blank_digest = DecisionDigest.__new__(DecisionDigest)
    assert validate(blank_digest)


def test_unhashable_keys_injected_do_not_raise():
    d = fresh_digest()
    force(d.holdings.entries[0].key, portfolio_id=["x"])
    force(d.actions.items[0], target=HoldingKey("pf-A", "0050"), evidence_refs=(["cap"],))
    force(d.market.facts[0], fact_id={"a": 1}, status=["ok"])
    res = validate(d)
    c = {v.code for v in res}
    assert "bad_key" in c
    # 守衛應給出精確違規，而不是退到「無法檢查」的兜底
    assert "uninspectable" not in c, res
    assert any(v.path.startswith("holdings.entries[0].key") for v in res)


# 3. 鍵正規化
@pytest.mark.parametrize("bad", [" 0050", "0050 ", "00\u200b50", "\ufeff0050", "００５０", "Ａ"])
def test_key_normalisation_rejected(bad):
    with pytest.raises(ValueError, match="bad_key"):
        HoldingKey("pf", bad)
    with pytest.raises(ValueError, match="bad_key"):
        HoldingKey(bad, "0050")
    with pytest.raises(ValueError, match="bad_key"):
        Fact(bad, DataStatus.OK, prov(), value=1.0)
    with pytest.raises(ValueError, match="bad_key"):
        action(aid=bad)


def test_keys_are_case_sensitive_not_folded():
    h = HoldingsSection(Availability.AVAILABLE,
                        entries=(HoldingEntry(HoldingKey("pf", "abc"), facts=(ok_fact("a"),)),
                                 HoldingEntry(HoldingKey("pf", "ABC"), facts=(ok_fact("b"),))))
    assert len(h.entries) == 2


# 4. 缺值佔位字
@pytest.mark.parametrize("ph", sorted(PLACEHOLDER_TEXTS) + [" N/A ", "NULL", "None", "NaN"])
@pytest.mark.parametrize("status", [DataStatus.OK, DataStatus.STALE, DataStatus.PROXY])
def test_placeholder_text_rejected(ph, status):
    with pytest.raises(ValueError, match="placeholder_text"):
        Fact("f", status, prov(), text=ph)


def test_placeholder_set_locked_and_real_text_ok():
    assert PLACEHOLDER_TEXTS == frozenset({
        "n/a", "na", "n.a.", "nan", "none", "null", "unknown", "?", "-", "--", "—", "–",
        "無資料", "未評估", "尚無資料", "暫無資料", "未知", "無"})
    Fact("f", DataStatus.OK, prov(), text="0050 汰弱")  # 含 0 但不是佔位字
    with pytest.raises(ValueError, match="placeholder_text"):
        ActionRef("a9", "N/A", ActionOrigin.RULE_LAYER, RULE, ("cap",))


# 5. DefinitionSection
def test_definition_observations_numeric_only():
    DefinitionSection(DefinitionState.NOT_DEFINED, observations=(ok_fact("ma20", 101.5),))
    with pytest.raises(ValueError, match="text_in_definition_section"):
        DefinitionSection(DefinitionState.NOT_DEFINED, observations=(ok_fact("lbl", value=None, text="多頭排列"),))


@pytest.mark.parametrize("ref,ok", [("twii_ohlcv", True), ("fred:dgs10", True), ("ma.20-d", True),
                                    ("TWII", False), ("twii ohlcv", False), ("", False), ("台股", False)])
def test_series_ref_format(ref, ok):
    if ok:
        DefinitionSection(DefinitionState.NOT_DEFINED, series_ref=ref)
    else:
        with pytest.raises(ValueError, match="bad_series_ref"):
            DefinitionSection(DefinitionState.NOT_DEFINED, series_ref=ref)


@pytest.mark.parametrize("reason", list(MissingReason))
def test_definition_reason_restricted(reason):
    if reason in (MissingReason.NOT_DEFINED, MissingReason.NOT_WIRED):
        DefinitionSection(DefinitionState.NOT_DEFINED, missing_reason=reason)
    else:
        with pytest.raises(ValueError, match="bad_definition_reason"):
            DefinitionSection(DefinitionState.NOT_DEFINED, missing_reason=reason)


# 6. 時間一致性
def test_generated_at_must_be_utc():
    assert "generated_at_not_utc" in codes(digest(generated_at=NOW.astimezone(TZ8)))
    assert validate(digest(generated_at=NOW)) == ()


def test_fetched_after_generated_rejected():
    late = Fact("late", DataStatus.OK, prov(fetched_at=NOW + timedelta(minutes=1)), value=1.0)
    assert "fetched_after_generated" in codes(digest(market=FactSection(Availability.AVAILABLE, facts=(late,))))
    same = Fact("same", DataStatus.OK, prov(fetched_at=NOW), value=1.0)
    assert validate(digest(market=FactSection(Availability.AVAILABLE, facts=(same,)))) == ()


def test_as_of_after_generated_tw_date_rejected():
    # NOW = 2026-10-27 09:00 UTC = 17:00 台北 → 台北日期 10-27 合法、10-28 違規
    ok_ = Fact("t", DataStatus.OK, prov(as_of=date(2026, 10, 27), fetched_at=None), value=1.0)
    assert validate(digest(market=FactSection(Availability.AVAILABLE, facts=(ok_,)))) == ()
    bad = Fact("t", DataStatus.OK, prov(as_of=date(2026, 10, 28), fetched_at=None), value=1.0)
    assert "as_of_after_generated" in codes(digest(market=FactSection(Availability.AVAILABLE, facts=(bad,))))
    # UTC 日期還是 10-27 23:30，但台北已是 10-28 → 10-28 合法
    gen = datetime(2026, 10, 27, 16, 30, tzinfo=timezone.utc)
    tw28 = Fact("t", DataStatus.OK, prov(as_of=date(2026, 10, 28), fetched_at=None), value=1.0)
    assert "as_of_after_generated" not in codes(
        digest(generated_at=gen, market=FactSection(Availability.AVAILABLE, facts=(tw28,))))


def test_as_of_after_fetched_tw_date_rejected():
    fetched = datetime(2026, 10, 26, 15, 0, tzinfo=timezone.utc)  # 台北 10-26 23:00
    Provenance("S", as_of=date(2026, 10, 26), fetched_at=fetched)
    with pytest.raises(ValueError, match="as_of_after_fetched"):
        Provenance("S", as_of=date(2026, 10, 27), fetched_at=fetched)
    fetched2 = datetime(2026, 10, 26, 16, 30, tzinfo=timezone.utc)  # 台北已 10-27
    Provenance("S", as_of=date(2026, 10, 27), fetched_at=fetched2)
    assert TW_TZ.utcoffset(None) == timedelta(hours=8)


# 7. actions 段 availability
def test_actions_partial_forbidden():
    with pytest.raises(ValueError, match="partial_actions"):
        ActionsSection(Availability.PARTIAL, items=(action(),))
    with pytest.raises(ValueError, match="missing_reason_required"):
        ActionsSection(Availability.UNAVAILABLE)
    ActionsSection(Availability.UNAVAILABLE, missing_reason=MissingReason.NOT_WIRED)
    ActionsSection(Availability.AVAILABLE)  # 規則層未產出行動：明文合法


# 8. 一致性
def test_evidence_on_missing_fact_rejected():
    d = digest(market=FactSection(Availability.PARTIAL, facts=(ok_fact("regime", value=None, text="x"),
                                                               missing_fact("gone"))),
               actions=ActionsSection(Availability.AVAILABLE, items=(action(refs=("gone",)),)))
    assert "evidence_on_unusable_fact" in codes(d)
    d2 = digest(actions=ActionsSection(Availability.AVAILABLE, items=(action(refs=("regime",)),)))
    assert validate(d2) == ()


def test_valid_cap_requires_usable_value():
    with pytest.raises(ValueError, match="valid_cap_without_value"):
        RiskCapSection(True, missing_fact("cap"), ok_fact("lo", 1.0), ok_fact("hi", 2.0), Availability.PARTIAL)
    with pytest.raises(ValueError, match="valid_cap_without_value"):
        RiskCapSection(True, Fact("cap", DataStatus.PROXY, prov(), value=50.0, rule=RULE),
                       ok_fact("lo", 1.0), ok_fact("hi", 2.0), Availability.PARTIAL)
    RiskCapSection(True, Fact("cap", DataStatus.STALE, prov(), value=50.0, rule=RULE),
                   ok_fact("lo", 1.0), ok_fact("hi", 2.0), Availability.PARTIAL)


# 9. AI 保留前綴
@pytest.mark.parametrize("name", ["ai", "AI:summary", "ai.brain", "LLM_out", "gemini", "Gemini-1.5:x",
                                  "gpt4", "GPT:x", "claude", "Claude3.output", "openai:chat", " ai:x"])
def test_ai_reserved_prefix_rejected(name):
    with pytest.raises(ValueError, match="ai_reserved"):
        Provenance(name)
    with pytest.raises(ValueError, match="ai_reserved"):
        RuleRef(name, "v1")


@pytest.mark.parametrize("name", ["air_quality", "FRED:DGS10", "allocation", "risk_cap", "TWSE:MI_INDEX",
                                  "rainfall", "chain_store"])
def test_non_ai_names_accepted(name):
    Provenance(name)
    RuleRef(name, "v1")


# 10. MissingReason ↔ station_specs.MISS_*
def test_every_station_miss_code_maps():
    import shared.station_specs as ss
    miss = {k: v for k, v in vars(ss).items() if k.startswith("MISS_") and isinstance(v, str)}
    assert miss, "掃描器壞了：station_specs 沒有 MISS_* 常數"
    for name, code in miss.items():
        assert code in MISS_CODE_TO_REASON, name
        assert isinstance(MISS_CODE_TO_REASON[code], MissingReason)
    assert set(MISS_CODE_TO_REASON) == set(miss.values())
    assert MISS_CODE_TO_REASON[ss.MISS_NO_VARIATION] is MissingReason.NO_VARIATION
    assert MISS_CODE_TO_REASON[ss.MISS_NOT_ENOUGH] is MissingReason.NOT_ENOUGH_HISTORY


def test_d11_invalid_status():
    f = Fact("bad", DataStatus.INVALID, prov(as_of=None))
    assert f.value is None and f.missing_reason is None
    with pytest.raises(ValueError, match="value_with_missing_status"):
        Fact("bad", DataStatus.INVALID, prov(), value=1.0)
    with pytest.raises(ValueError, match="value_with_missing_status"):
        Fact("bad", DataStatus.INVALID, prov(), text="x")
    with pytest.raises(ValueError, match="missing_reason_forbidden"):
        Fact("bad", DataStatus.INVALID, prov(), missing_reason=MissingReason.CONTRACT_DRIFT)
    assert derive_availability((Fact("bad", DataStatus.INVALID, prov()),)) is Availability.UNAVAILABLE
    assert derive_availability((ok_fact("a"), Fact("bad", DataStatus.INVALID, prov()))) is Availability.PARTIAL


# 12. docstring 不含同步標記字樣
def test_module_has_no_sync_marker():
    assert "AUTO-SYNCED" not in MODULE_PATH.read_text(encoding="utf-8")


# ══ QA 第三輪（round 2 A～O）══════════════════════════════════════════════


# A. 精確型別
@dataclasses.dataclass(frozen=True)
class EvilFact(Fact):
    ai_verdict: str = "偏多"


def test_subclass_with_extra_field_rejected_and_never_serialized():
    with pytest.raises(ValueError, match="子類別拒收"):
        EvilFact("e", DataStatus.OK, prov(), value=1.0)
    d = fresh_digest()
    evil = EvilFact.__new__(EvilFact)
    for f in dataclasses.fields(EvilFact):
        object.__setattr__(evil, f.name, getattr(d.market.facts[0], f.name, "偏多"))
    force(d.market, facts=(evil,))
    assert "type" in codes(d)
    with pytest.raises(ValueError):
        d.to_dict()
    # 即使繞過驗證直接序列化，也只輸出 Fact 宣告的欄位
    from shared.decision_digest import _to_jsonable
    out = _to_jsonable(evil)
    assert "ai_verdict" not in out and set(out) == {f.name for f in dataclasses.fields(Fact)}


class StrSub(str):
    pass


@pytest.mark.parametrize("make", [
    lambda: Provenance(StrSub("SRC")),
    lambda: Fact("f", DataStatus.OK, prov(), text=StrSub("x")),
    lambda: RuleRef("r", StrSub("v1")),
    lambda: HoldingKey(StrSub("pf"), "0050"),
    lambda: Provenance("S", as_of=datetime(2026, 1, 1, tzinfo=TZ8).date().__class__.__new__(
        type("MyDate", (date,), {}), 2026, 1, 1)),
])
def test_exact_str_and_date_types(make):
    with pytest.raises(ValueError):
        make()


def test_exact_datetime_type():
    class MyDT(datetime):
        pass
    with pytest.raises(ValueError, match="naive_datetime"):
        Provenance("S", fetched_at=MyDT(2026, 1, 1, tzinfo=timezone.utc))
    assert "naive_datetime" in codes(digest(generated_at=MyDT(2026, 10, 27, 9, tzinfo=timezone.utc)))


def test_section_subclass_rejected():
    @dataclasses.dataclass(frozen=True)
    class EvilSection(DefinitionSection):
        verdict: str = "bull"
    with pytest.raises(ValueError, match="子類別拒收"):
        EvilSection(DefinitionState.NOT_DEFINED)


# B. DefinitionSection 綁定
@pytest.mark.parametrize("name,bad", [("tw_trend", DefinitionState.RESEARCH_ONLY),
                                      ("intl_trend", DefinitionState.RESEARCH_ONLY),
                                      ("industry", DefinitionState.RESEARCH_ONLY),
                                      ("valuation", DefinitionState.NOT_DEFINED)])
def test_definition_binding(name, bad):
    assert "definition_binding" in codes(digest(**{name: DefinitionSection(bad)}))


@pytest.mark.parametrize("name,state", [("valuation", DefinitionState.RESEARCH_ONLY),
                                        ("industry", DefinitionState.NOT_DEFINED)])
def test_valuation_and_industry_have_no_observations(name, state):
    sec = DefinitionSection(state, observations=(ok_fact("eps", 10.0),))
    assert "observations_forbidden" in codes(digest(**{name: sec}))


def test_trend_observations_allowed():
    sec = DefinitionSection(DefinitionState.NOT_DEFINED, series_ref="twii_ohlcv",
                            observations=(ok_fact("twii_ma60", 21000.0, unit="pts"),))
    assert validate(digest(tw_trend=sec)) == ()


@pytest.mark.parametrize("unit", ["點 數", "pts\n", "a b", "億"])
def test_definition_observation_unit_format(unit):
    with pytest.raises(ValueError, match="bad_unit"):
        DefinitionSection(DefinitionState.NOT_DEFINED, observations=(ok_fact("x", 1.0, unit=unit),))


_DIR_LATIN_WORDS = ["bull", "BEARISH", "downtrend", "sell", "uptrend", "buy", "weak", "strong"]
_DIR_CJK_WORDS = ["偏多", "空頭", "轉強", "強", "弱", "看多"]
# 中文只測 rule_id／source：series_ref／unit 的格式本來就只收英數，fact_id 與 source 同一套判定
_DIR_CASES = ([(w, x) for w in ("series_ref", "fact_id", "unit", "rule_id", "source") for x in _DIR_LATIN_WORDS]
              + [(w, x) for w in ("rule_id", "source") for x in _DIR_CJK_WORDS])


@pytest.mark.parametrize("where,word", _DIR_CASES)
def test_direction_tokens_rejected(where, word):
    latin = word.isascii()
    ident = f"twii_{word.lower()}" if latin else f"twii{word}"
    kw = {}
    if where == "series_ref":
        kw["series_ref"] = ident
    else:
        f_id, unit, rid, src = "ma60", "pts", "rule_x", "SRC:x"
        if where == "fact_id":
            f_id = ident
        elif where == "unit":
            unit = ident
        elif where == "rule_id":
            rid = ident
        else:
            src = ident
        obs = (Fact(f_id, DataStatus.OK, prov(source=src), value=1.0, unit=unit,
                    rule=RuleRef(rid, "v1")),)
        kw["observations"] = obs
    with pytest.raises(ValueError, match="direction_token"):
        DefinitionSection(DefinitionState.NOT_DEFINED, **kw)


@pytest.mark.parametrize("ident", ["twii_ma60", "upload_ts", "longitude", "sp500", "dgs10"])
def test_non_direction_idents_ok(ident):
    DefinitionSection(DefinitionState.NOT_DEFINED, series_ref=ident,
                      observations=(ok_fact(ident, 1.0, unit="pts"),))


# C. 依據
@pytest.mark.parametrize("status", [DataStatus.PROXY, DataStatus.INVALID, DataStatus.MISSING, DataStatus.FAILED])
def test_evidence_must_be_ok_or_stale(status):
    kw = {}
    if status in (DataStatus.MISSING, DataStatus.FAILED):
        kw["missing_reason"] = MissingReason.NO_INPUT
    if status is DataStatus.PROXY:
        kw["value"] = 1.0
    ev = Fact("ev", status, prov(), **kw)
    d = digest(market=FactSection(derive_availability((ok_fact("regime", value=None, text="x"), ev)),
                                  facts=(ok_fact("regime", value=None, text="x"), ev)),
               actions=ActionsSection(Availability.AVAILABLE, items=(action(refs=("ev",)),)))
    assert "evidence_on_unusable_fact" in codes(d)


def test_evidence_stale_ok():
    ev = Fact("ev", DataStatus.STALE, prov(), value=1.0)
    d = digest(market=FactSection(Availability.PARTIAL, facts=(ok_fact("regime", value=None, text="x"), ev)),
               actions=ActionsSection(Availability.AVAILABLE, items=(action(refs=("ev",)),)))
    assert validate(d) == ()


def test_evidence_on_observation_rejected():
    sec = DefinitionSection(DefinitionState.NOT_DEFINED, observations=(ok_fact("ma60", 1.0),))
    d = digest(tw_trend=sec, actions=ActionsSection(Availability.AVAILABLE, items=(action(refs=("ma60",)),)))
    assert "evidence_on_observation" in codes(d)


def test_duplicate_evidence_refs_rejected():
    with pytest.raises(ValueError, match="duplicate_evidence_ref"):
        action(refs=("cap", "cap"))


# D. 行動 vs 持股
def test_actions_available_requires_holdings():
    h = HoldingsSection(Availability.UNAVAILABLE, missing_reason=MissingReason.FETCH_FAILED)
    d = digest(holdings=h, actions=ActionsSection(Availability.AVAILABLE))
    assert "actions_available_without_holdings" in codes(d)
    d2 = digest(holdings=h, actions=ActionsSection(Availability.UNAVAILABLE, missing_reason=MissingReason.NO_INPUT))
    assert validate(d2) == ()


# E. unkeyed_count
def test_unkeyed_count_caps_availability():
    entries = (HoldingEntry(K1, facts=(ok_fact("a"),)),)
    with pytest.raises(ValueError, match="availability_mismatch"):
        HoldingsSection(Availability.AVAILABLE, entries=entries, unkeyed_count=1)
    HoldingsSection(Availability.PARTIAL, entries=entries, unkeyed_count=1)
    HoldingsSection(Availability.AVAILABLE, entries=entries, unkeyed_count=0)
    with pytest.raises(ValueError, match="availability_mismatch"):
        HoldingsSection(Availability.PARTIAL, unkeyed_count=2, missing_reason=None)
    HoldingsSection(Availability.UNAVAILABLE, unkeyed_count=2, missing_reason=MissingReason.NO_INPUT)


@pytest.mark.parametrize("bad", [-1, True, 1.0, "1", None, np.int64(1)])
def test_unkeyed_count_type(bad):
    with pytest.raises(ValueError, match="bad_unkeyed_count"):
        HoldingsSection(Availability.UNAVAILABLE, unkeyed_count=bad, missing_reason=MissingReason.NO_INPUT)


# G. 佔位字正規化
@pytest.mark.parametrize("ph", ["UNKNOWN", "未知", "無", "暫無資料", "N.A.", "?", "－", "–", "—",
                                "0.0", "0%", "0.00%", "00", "n / a", "N​/A", "Ｎ／Ａ", "n\ta", "nUll\x07"])
def test_placeholder_normalized(ph):
    with pytest.raises(ValueError, match="placeholder_text"):
        Fact("f", DataStatus.OK, prov(), text=ph)
    with pytest.raises(ValueError, match="placeholder_text"):
        ActionRef("a", ph, ActionOrigin.RULE_LAYER, RULE, ("cap",))
    with pytest.raises(ValueError, match="placeholder_text"):
        HoldingEntry(K1, StrategyType.BUY_AND_HOLD, strategy_source=ph)


@pytest.mark.parametrize("txt", ["0.5%", "10", "無法判定", "無風險", "na+", "汰弱 0050"])
def test_placeholder_does_not_overreach(txt):
    Fact("f", DataStatus.OK, prov(), text=txt)


# H. AI 字樣
@pytest.mark.parametrize("name", ["genai:x", "gen_ai", "GenAI", "chatgpt-4o", "anthropic:x", "deepseek_v3",
                                  "copilot", "llmc", "mistral7b", "llama3", "x/claude", "src gemini",
                                  "ＡＩ:x", "a​i:x", "AI模型", "大模型", "財經ai", "ai摘要", "TWSE:ai"])
def test_ai_denylist_extended(name):
    with pytest.raises(ValueError, match="ai_reserved"):
        Provenance(name)
    with pytest.raises(ValueError, match="ai_reserved"):
        RuleRef(name, "v1")
    with pytest.raises(ValueError, match="ai_reserved"):
        HoldingEntry(K1, StrategyType.CAPITAL_GAIN, strategy_source=name)


# I. fullmatch
def test_trailing_newline_rejected_by_regexes():
    with pytest.raises(ValueError, match="bad_series_ref"):
        DefinitionSection(DefinitionState.NOT_DEFINED, series_ref="twii\n")
    assert codes(digest(ai_participation=AiParticipation.AI_EXPLAINED, ai_passed_checks=("G1\n",))) & {"bad_check_id"}
    with pytest.raises(ValueError, match="bad_unit"):
        DefinitionSection(DefinitionState.NOT_DEFINED, observations=(ok_fact("x", 1.0, unit="pts\n"),))


# J. AI checks
@pytest.mark.parametrize("ids", [("G7",), ("G10",), ("G0",)])
def test_check_ids_bounded(ids):
    assert "bad_check_id" in codes(digest(ai_participation=AiParticipation.AI_EXPLAINED, ai_passed_checks=ids))


def test_check_ids_no_duplicates_and_disjoint():
    assert "duplicate_check_id" in codes(digest(ai_participation=AiParticipation.AI_EXPLAINED,
                                                ai_passed_checks=("G1", "G1")))
    assert "check_in_both" in codes(digest(ai_participation=AiParticipation.AI_REJECTED,
                                           ai_passed_checks=("G1",), ai_failed_checks=("G1",)))
    assert validate(digest(ai_participation=AiParticipation.AI_REJECTED,
                           ai_passed_checks=("G1",), ai_failed_checks=("G2",))) == ()


# K. 鍵：控制字元與中間空白
@pytest.mark.parametrize("bad", ["00 50", "00\t50", "00\x0750", "pf\nA", "a　b"])
def test_key_internal_whitespace_and_cc(bad):
    with pytest.raises(ValueError, match="bad_key"):
        HoldingKey("pf", bad)
    with pytest.raises(ValueError, match="bad_key"):
        HoldingKey(bad, "0050")
    with pytest.raises(ValueError, match="bad_key"):
        Fact(bad, DataStatus.OK, prov(), value=1.0)
    with pytest.raises(ValueError, match="bad_key"):
        action(aid=bad)


# L. repr 會炸的物件
class Evil:
    def __repr__(self):
        raise RuntimeError("boom")

    def __str__(self):
        raise RuntimeError("boom")


def test_evil_repr_does_not_raise():
    d = fresh_digest()
    force(d.market.facts[0], unit=Evil())
    force(d.holdings.entries[0].key, symbol=Evil())
    force(d.actions.items[0], priority_rank=Evil(), text=Evil())
    res = validate(d)
    assert res and all(type(v.message) is str for v in res)
    assert any("unrepr-able Evil" in v.message for v in res)
    assert "uninspectable" not in {v.code for v in res}


# M. 改名
def test_rule_only_member_name():
    assert AiParticipation.RULE_ONLY.value == "rule_only"
    assert not hasattr(AiParticipation, "NONE")


# O. 不變項
def test_decimal_still_rejected_and_numpy_rank_ok():
    from decimal import Decimal
    with pytest.raises(ValueError, match="bad_number"):
        Fact("f", DataStatus.OK, prov(), value=Decimal("1.5"))
    action(rank=np.int64(2))
    with pytest.raises(ValueError, match="bad_rank"):
        action(rank=np.bool_(True))
    with pytest.raises(ValueError, match="duplicate_rank"):
        ActionsSection(Availability.AVAILABLE, items=(action("a1", rank=np.int64(1)), action("a2", rank=1)))


# ══ QA 第四輪（round 3：誤殺修正）════════════════════════════════════════
@pytest.mark.parametrize("ident", ["ma_long_240", "ma_long", "short_interest", "up_limit", "down_count"])
def test_existing_repo_idents_not_direction(ident):
    DefinitionSection(DefinitionState.NOT_DEFINED, series_ref=ident,
                      observations=(Fact(ident, DataStatus.OK, prov(source=f"SRC:{ident}"), value=1.0,
                                         unit="pts", rule=RuleRef(ident, "v1")),))


@pytest.mark.parametrize("ident", ["bu\u200bll", "be\x00ar", "bu\u200bllish_x", "s\u2060ell"])
def test_direction_check_strips_cc_cf(ident):
    with pytest.raises(ValueError, match="direction_token"):
        DefinitionSection(DefinitionState.NOT_DEFINED,
                          observations=(Fact("ma60", DataStatus.OK, prov(source=ident), value=1.0,
                                             rule=RULE),))
    with pytest.raises(ValueError, match="direction_token"):
        DefinitionSection(DefinitionState.NOT_DEFINED,
                          observations=(Fact("ma60", DataStatus.OK, prov(), value=1.0,
                                             rule=RuleRef(ident, "v1")),))


@pytest.mark.parametrize("name", ["Shanghai上證", "Mumbai孟買", "Thai泰國", "上證Shanghai", "台灣Taipei", "Dubai杜拜",
                                  "台灣Airways", "空巴airbus"])
def test_latin_words_ending_ai_next_to_cjk_ok(name):
    Provenance(name)
    RuleRef(name, "v1")
    HoldingEntry(K1, StrategyType.CAPITAL_GAIN, strategy_source=name)


@pytest.mark.parametrize("name", ["a\x00i:x", "a\x07i", "財經ai", "ai摘要", "上證ai", "x ai上證"])
def test_ai_check_strips_cc_and_flags_standalone_ai_next_to_cjk(name):
    with pytest.raises(ValueError, match="ai_reserved"):
        Provenance(name)
