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
                                 entries=(HoldingEntry(K1), HoldingEntry(K2))),
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
    assert {m.value for m in DataStatus} == {"ok", "stale", "missing", "proxy", "failed"}
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
    d = digest(risk_cap=risk_cap(valid=False))
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
    with pytest.raises(ValueError, match="missing_reason_on_value"):
        Fact("f", DataStatus.OK, prov(), value=1.0, missing_reason=MissingReason.NO_INPUT)


def test_ok_requires_as_of_but_stale_and_proxy_may_lack_it():
    with pytest.raises(ValueError, match="ok_without_as_of"):
        Fact("f", DataStatus.OK, prov(as_of=None), value=1.0)
    Fact("f", DataStatus.STALE, prov(as_of=None), value=1.0)
    Fact("f", DataStatus.PROXY, prov(as_of=D), value=1.0)


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
    Provenance("S", as_of=D, fetched_at=datetime(2026, 1, 1, tzinfo=TZ8))
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
    h1 = HoldingEntry(K1, StrategyType.BUY_AND_HOLD, strategy_source="sheet:col")
    h2 = HoldingEntry(K2, StrategyType.CAPITAL_GAIN, strategy_source="sheet:col")
    d = digest(holdings=HoldingsSection(Availability.AVAILABLE, entries=(h1, h2)))
    assert validate(d) == ()


def test_duplicate_holding_key_rejected():
    with pytest.raises(ValueError, match="duplicate_holding_key"):
        HoldingsSection(Availability.AVAILABLE, entries=(HoldingEntry(K1), HoldingEntry(HoldingKey("pf-A", "0050"))))


@pytest.mark.parametrize("pid,sym", [("", "0050"), ("   ", "0050"), ("pf", ""), ("pf", " "), (None, "0050")])
def test_blank_portfolio_id_or_symbol_rejected(pid, sym):
    with pytest.raises(ValueError, match="blank_str"):
        HoldingKey(pid, sym)


def test_strategy_default_unclassified_and_source_rules():
    assert HoldingEntry(K1).strategy is StrategyType.UNCLASSIFIED
    with pytest.raises(ValueError, match="source_required"):
        HoldingEntry(K1, StrategyType.BUY_AND_HOLD)
    with pytest.raises(ValueError, match="source_on_unclassified"):
        HoldingEntry(K1, StrategyType.UNCLASSIFIED, strategy_source="x")
    with pytest.raises(ValueError, match="type"):
        HoldingEntry(K1, "存股", strategy_source="x")  # 裸字串不得冒充列舉


def test_holdings_unavailable_distinguishes_reason_and_has_no_entries():
    HoldingsSection(Availability.UNAVAILABLE, missing_reason=MissingReason.FETCH_FAILED)
    with pytest.raises(ValueError, match="missing_reason_required"):
        HoldingsSection(Availability.UNAVAILABLE)
    with pytest.raises(ValueError, match="entries_when_unavailable"):
        HoldingsSection(Availability.UNAVAILABLE, entries=(HoldingEntry(K1),),
                        missing_reason=MissingReason.NO_INPUT)


# ── Actions ──────────────────────────────────────────────────────────────
def test_more_than_three_actions_rejected():
    items = tuple(action(aid=f"a{i}") for i in range(MAX_ACTIONS + 1))
    with pytest.raises(ValueError, match="too_many_actions"):
        ActionsSection(Availability.AVAILABLE, items=items)
    ActionsSection(Availability.AVAILABLE, items=items[:MAX_ACTIONS])


def test_action_requires_evidence_rule_and_rule_origin():
    with pytest.raises(ValueError, match="empty"):
        action(refs=())
    with pytest.raises(ValueError, match="blank_str"):
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
    d = digest(market=FactSection(Availability.AVAILABLE, facts=(ok_fact("cap"),)))
    assert "duplicate_fact_id" in codes(d)


# ── AI 參與 ──────────────────────────────────────────────────────────────
def test_ai_participation_consistency():
    assert "rejected_without_checks" in codes(digest(ai_participation=AiParticipation.AI_REJECTED))
    assert validate(digest(ai_participation=AiParticipation.AI_REJECTED, ai_failed_checks=("G2",))) == ()
    assert "checks_without_rejection" in codes(digest(ai_failed_checks=("G2",)))
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
_STDLIB_ALLOWED = {"__future__", "math", "dataclasses", "datetime", "enum", "typing"}


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
