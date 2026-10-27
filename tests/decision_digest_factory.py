"""AB-2a 測試共用夾具：直接用 AB-0 契約類別組 Digest（比經 builder 更能精確控制每個欄位）。

不是測試檔（檔名不以 test_ 開頭，不會被收集）。
"""
from __future__ import annotations

import dataclasses
from datetime import date, datetime, timezone

from shared.decision_digest import (
    ActionOrigin, ActionRef, ActionsSection, AiParticipation, Availability, DataStatus, DecisionDigest,
    DefinitionSection, DefinitionState, Fact, FactSection, HoldingEntry, HoldingKey, HoldingsSection,
    MissingReason, Provenance, RiskCapSection, RuleRef, StrategyType, derive_availability,
)
from shared.decision_digest_rules import ACTION_RULE_VERSION
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION

NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)
D = date(2026, 10, 26)
RISK_RULE = RuleRef("risk_cap", RISK_CAP_RULESET_VERSION)


def prov(as_of=D, source="svc"):
    return Provenance(source=source, as_of=as_of)


def ok_text(fid, text, as_of=D, rule=None):
    return Fact(fid, DataStatus.OK, prov(as_of), text=text, rule=rule)


def ok_val(fid, value, unit=None, as_of=D, rule=None):
    return Fact(fid, DataStatus.OK, prov(as_of), value=value, unit=unit, rule=rule)


def stale_val(fid, value, unit=None, as_of=D):
    return Fact(fid, DataStatus.STALE, prov(as_of), value=value, unit=unit)


def stale_text(fid, text, as_of=D):
    return Fact(fid, DataStatus.STALE, prov(as_of), text=text)


def proxy_val(fid, value, unit=None, as_of=None):
    return Fact(fid, DataStatus.PROXY, prov(as_of), value=value, unit=unit)


def missing(fid, reason=MissingReason.NO_INPUT):
    return Fact(fid, DataStatus.MISSING, prov(None), missing_reason=reason)


def failed(fid, reason=MissingReason.FETCH_FAILED):
    return Fact(fid, DataStatus.FAILED, prov(None), missing_reason=reason)


def invalid(fid):
    return Fact(fid, DataStatus.INVALID, prov(None))


def market_section(facts):
    av = derive_availability(facts)
    return FactSection(av, facts, MissingReason.NO_INPUT if av is Availability.UNAVAILABLE else None)


def default_market_facts():
    return (ok_text("market.regime", "bull"), ok_text("market.light", "🟢"), ok_val("market.health", 72.5))


def risk_cap_section(valid=True):
    if valid:
        cap = ok_val("risk_cap.cap_pct", 60, "%", rule=RISK_RULE)
        lo = ok_val("risk_cap.exposure_lo_pct", 40, "%", rule=RISK_RULE)
        hi = ok_val("risk_cap.exposure_hi_pct", 60, "%", rule=RISK_RULE)
        return RiskCapSection(True, cap, lo, hi, Availability.AVAILABLE)
    m = [Fact(f"risk_cap.{n}", DataStatus.MISSING, prov(None), missing_reason=MissingReason.NO_INPUT,
              rule=RISK_RULE) for n in ("cap_pct", "exposure_lo_pct", "exposure_hi_pct")]
    return RiskCapSection(False, m[0], m[1], m[2], Availability.UNAVAILABLE, MissingReason.NO_INPUT)


def action_fact(symbol, text, code="add", pid="pf-A"):
    return Fact(f"action_fact:{pid}:{symbol}", DataStatus.OK, prov(), text=text,
                rule=RuleRef(code, ACTION_RULE_VERSION))


def entry(symbol, text=None, code="add", pid="pf-A", strategy=StrategyType.UNCLASSIFIED, source=None, facts=None):
    f = facts if facts is not None else ((action_fact(symbol, text, code, pid),) if text is not None else ())
    return HoldingEntry(HoldingKey(pid, symbol), strategy, source, f)


def action(symbol, text, code="add", rank=1, pid="pf-A", evidence=None):
    return ActionRef(action_id=f"action:{pid}:{symbol}", text=text, origin=ActionOrigin.RULE_LAYER,
                     rule=RuleRef(code, ACTION_RULE_VERSION),
                     evidence_refs=evidence or (f"action_fact:{pid}:{symbol}",),
                     target=HoldingKey(pid, symbol), priority_rank=rank)


def holdings_section(entries, unkeyed=0, reason=MissingReason.NO_INPUT):
    facts = tuple(f for e in entries for f in e.facts)
    base = derive_availability(facts) if entries else Availability.UNAVAILABLE
    if base is Availability.AVAILABLE and unkeyed > 0:
        base = Availability.PARTIAL
    return HoldingsSection(base, tuple(entries), reason if base is Availability.UNAVAILABLE else None, unkeyed)


def actions_section(items, reason=MissingReason.NO_INPUT):
    if items:
        return ActionsSection(Availability.AVAILABLE, tuple(items))
    return ActionsSection(Availability.UNAVAILABLE, (), reason)


def make_digest(*, market_facts=None, risk_valid=True, entries=None, unkeyed=0, items=None,
                holdings_reason=MissingReason.NO_INPUT, **over):
    mf = market_facts if market_facts is not None else default_market_facts()
    es = entries if entries is not None else [
        entry("0050", "🔴 汰弱：吃本金", "cut"), entry("0056", "💰 強制停利（>+3σ）：獲利轉回核心資產",
                                                     "take_profit_force")]
    its = items if items is not None else [
        action("0050", "🔴 汰弱：吃本金", "cut", 1), action("0056", "💰 強制停利（>+3σ）：獲利轉回核心資產",
                                                          "take_profit_force", 2)]
    d = DecisionDigest(
        generated_at=NOW, market=market_section(tuple(mf)),
        tw_trend=DefinitionSection(DefinitionState.NOT_DEFINED),
        intl_trend=DefinitionSection(DefinitionState.NOT_DEFINED),
        valuation=DefinitionSection(DefinitionState.RESEARCH_ONLY),
        industry=DefinitionSection(DefinitionState.NOT_DEFINED),
        holdings=holdings_section(es, unkeyed, holdings_reason), risk_cap=risk_cap_section(risk_valid),
        actions=actions_section(its), ai_participation=AiParticipation.RULE_ONLY)
    return dataclasses.replace(d, **over) if over else d


def force_set(obj, **attrs):
    """繞過 frozen（模擬被竄改／契約漂移）。回傳同一物件。"""
    for k, v in attrs.items():
        object.__setattr__(obj, k, v)
    return obj


def empty_digest():
    return make_digest(market_facts=[missing("market.regime"), missing("market.light"), missing("market.health")],
                       risk_valid=False, entries=[], items=[])
