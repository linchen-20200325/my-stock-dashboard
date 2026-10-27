"""AB-1 rule_id 允許名單＋Q4 行動排序守衛測試（fast lane）。

守的是 `shared/decision_digest_rules.py`：允許名單是 rule_id 的主要治理手段、Q4 序可被機器驗證、
且與真實 `dividend_station.action_branch` 的實際解衝突順序一致（漂移即紅燈）。
"""
from __future__ import annotations

import ast
import dataclasses
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from shared import decision_digest_rules as R
from shared.decision_digest import (
    MAX_ACTIONS, ActionsSection, DecisionDigest, HoldingKey, RuleRef, validate,
)
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION
from src.compute.etf import dividend_station as ds
from src.services.decision_digest_builder import SourceStamp, build_decision_digest

REPO = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)
STAMP = SourceStamp("dividend_station_service", date(2026, 10, 26))


def make_digest(codes: list[str]) -> DecisionDigest:
    """用 builder 組一份含 `codes` 行動的 digest（輸入順序＝codes 順序；僅為造資料，不是被測物）。"""
    tickers = [f"T{i}" for i in range(len(codes))]
    keys = {t: HoldingKey("pf", t) for t in tickers}
    holdings = [{"ticker": t, "held": True} for t in tickers]
    rows = [{"代號": t, "held": True, "_action": c, "建議動作": f"txt-{c}", "_detail": {}}
            for t, c in zip(tickers, codes)]
    return build_decision_digest(generated_at=NOW, station_rows=rows, station_stamp=STAMP,
                                 holdings_rows=holdings, holding_keys=keys)


def codes_of(vs) -> set:
    return {v.code for v in vs}


def with_actions(d: DecisionDigest, items: tuple) -> DecisionDigest:
    return dataclasses.replace(d, actions=dataclasses.replace(d.actions, items=items))


# ── 允許名單 ────────────────────────────────────────────────────────────
def test_allowlist_members_are_exactly_the_existing_identifiers():
    assert set(R.RULE_ID_ALLOWLIST) == {"risk_cap", "cut", "take_profit_force", "take_profit_partial",
                                        "pause_add", "add"}
    assert R.RULE_ID_ALLOWLIST["risk_cap"] == frozenset({RISK_CAP_RULESET_VERSION}) == frozenset({"risk_cap.v2"})
    for rid in R.ACTION_RULE_IDS:
        assert R.RULE_ID_ALLOWLIST[rid] == frozenset({"action_branch.v1"})


def test_premium_and_cruise_are_not_allowlisted():
    assert ds.ACTION_PREMIUM == "premium" and ds.ACTION_CRUISE == "cruise"
    for rid in (ds.ACTION_PREMIUM, ds.ACTION_CRUISE):
        assert rid not in R.RULE_ID_ALLOWLIST
        assert rid not in R.ACTION_RULE_IDS


def test_allowlist_is_immutable():
    with pytest.raises(TypeError):
        R.RULE_ID_ALLOWLIST["x"] = frozenset({"v"})  # type: ignore[index]
    assert isinstance(R.RULE_ID_ALLOWLIST["add"], frozenset)


def test_action_codes_pinned_to_dividend_station():
    assert R.RULE_CUT == ds.ACTION_CUT
    assert R.RULE_TAKE_PROFIT_FORCE == ds.ACTION_TAKE_PROFIT_FORCE
    assert R.RULE_TAKE_PROFIT_PARTIAL == ds.ACTION_TAKE_PROFIT_PARTIAL
    assert R.RULE_PAUSE_ADD == ds.ACTION_PAUSE_ADD
    assert R.RULE_ADD == ds.ACTION_ADD


def test_rule_ids_valid_on_builder_output_and_rejects_unknowns():
    d = make_digest(["cut", "add"])
    assert R.validate_rule_ids(d) == ()
    bad_id = dataclasses.replace(d.actions.items[0], rule=RuleRef("rule_x", "action_branch.v1"))
    assert "rule_not_allowlisted" in codes_of(R.validate_rule_ids(with_actions(d, (bad_id,) + d.actions.items[1:])))
    bad_ver = dataclasses.replace(d.actions.items[0], rule=RuleRef("cut", "action_branch.v2"))
    assert "rule_version_not_allowed" in codes_of(
        R.validate_rule_ids(with_actions(d, (bad_ver,) + d.actions.items[1:])))


@pytest.mark.parametrize("rid", ["premium", "cruise"])
def test_premium_cruise_rejected_as_action_rule(rid):
    d = make_digest(["add"])
    a = dataclasses.replace(d.actions.items[0], rule=RuleRef(rid, "action_branch.v1"))
    d2 = with_actions(d, (a,))
    assert "rule_not_allowlisted" in codes_of(R.validate_rule_ids(d2))
    assert "action_rule_not_allowed" in codes_of(R.validate_action_order(d2))


def test_fact_rule_walk_covers_risk_cap_and_holdings_facts():
    d = make_digest(["add"])
    holdings_fact = d.holdings.entries[0].facts[0]
    bad = dataclasses.replace(holdings_fact, rule=RuleRef("rule_x", "v1"))
    entry = dataclasses.replace(d.holdings.entries[0], facts=(bad,))
    d2 = dataclasses.replace(d, holdings=dataclasses.replace(d.holdings, entries=(entry,)))
    vs = R.validate_rule_ids(d2)
    assert any(v.code == "rule_not_allowlisted" and v.path.startswith("holdings.entries[0].facts[0]")
               for v in vs)
    rc = d.risk_cap
    bad_cap = dataclasses.replace(rc.cap_pct, rule=RuleRef("risk_cap", "risk_cap.v1"))
    d3 = dataclasses.replace(d, risk_cap=dataclasses.replace(rc, cap_pct=bad_cap))
    assert any(v.code == "rule_version_not_allowed" and v.path.startswith("risk_cap.cap_pct")
               for v in R.validate_rule_ids(d3))


def test_fact_rule_none_is_legal():
    d = make_digest(["add"])
    assert all(f.rule is None for f in d.market.facts)
    assert R.validate_rule_ids(d) == ()


# ── Q4 順序 ─────────────────────────────────────────────────────────────
def test_q4_priority_structure():
    assert [t for t, _ in R.Q4_ACTION_PRIORITY] == ["汰弱", "停利", "趨勢暫停", "加碼"]
    assert R.Q4_ACTION_PRIORITY[1][1] == ("take_profit_force", "take_profit_partial")
    assert R.ACTION_RULE_IDS == ("cut", "take_profit_force", "take_profit_partial", "pause_add", "add")


def _all_conditions_assessment() -> ds.HoldingAssessment:
    """真實 `assess_holding` 產出，再把各分支條件全部打開（dataclasses.replace，凍結物件）。"""
    import numpy as np
    import pandas as pd
    from shared import dividend_station_thresholds as T
    idx = pd.date_range("2023-01-01", periods=120, freq="W-SUN")
    i = np.arange(120)
    wk = pd.Series(20 + 0.01 * i + 0.05 * np.sin(i), index=idx)
    a = ds.assess_holding(ticker="X", name="X", asset_class=T.ASSET_CORE, weekly_close=wk, vix=10.0,
                          premium_pct=0.1, sharpe=0.8, total_return_1y_pct=10.0, annual_yield_pct=5.0,
                          inception_years=5, ann_return_3y_pct=5.0, cum_return_3y_pct=15.0,
                          peer_ranks=None)
    red = dataclasses.replace(a.health_a, level="🔴")
    yellow = dataclasses.replace(a.health_a, level="🟡")
    light_on = dataclasses.replace(a.light, light=T.LIGHT_1, take_profit="force")
    return dataclasses.replace(a, health_a=red, health_c=yellow, health_d=yellow, light=light_on)


def test_q4_order_pinned_to_action_branch_resolution():
    """逐層關掉最高優先的條件，記錄 `action_branch` 實際解出的順序，必須等於 Q4 攤平序。"""
    from shared import dividend_station_thresholds as T
    a = _all_conditions_assessment()
    green = dataclasses.replace(a.health_a, level="🟢")
    seen = [ds.action_branch(a)]                                              # cut
    a = dataclasses.replace(a, health_a=green)
    seen.append(ds.action_branch(a))                                          # take_profit_force
    a = dataclasses.replace(a, light=dataclasses.replace(a.light, take_profit="partial"))
    seen.append(ds.action_branch(a))                                          # take_profit_partial
    a = dataclasses.replace(a, light=dataclasses.replace(a.light, take_profit=None))
    seen.append(ds.action_branch(a))                                          # pause_add（C 🟡）
    a = dataclasses.replace(a, health_c=green)
    seen.append(ds.action_branch(a))                                          # add
    assert seen == list(R.ACTION_RULE_IDS)
    # 再往下才是 premium → cruise（不在客戶順序內）
    off = dataclasses.replace(a.light, light="none-lit")
    assert T.LIGHT_1 != "none-lit"
    a = dataclasses.replace(a, light=off)
    assert ds.action_branch(a) == ds.ACTION_PREMIUM
    a = dataclasses.replace(a, health_d=green)
    assert ds.action_branch(a) == ds.ACTION_CRUISE


def test_validate_action_order_accepts_builder_output_for_every_tier():
    d = make_digest(["add", "pause_add", "take_profit_partial"])
    assert [a.rule.rule_id for a in d.actions.items] == ["take_profit_partial", "pause_add", "add"]
    assert R.validate_action_order(d) == ()
    d = make_digest(["add", "take_profit_force", "cut"])
    assert [a.rule.rule_id for a in d.actions.items] == ["cut", "take_profit_force", "add"]
    assert R.validate_action_order(d) == ()


def test_validate_action_order_rejects_reversed_and_partial_before_force():
    d = make_digest(["cut", "take_profit_force", "add"])
    rev = tuple(reversed(d.actions.items))
    # ranks 仍是 3,2,1（reverse 後 rank 也非遞增）
    cs = codes_of(R.validate_action_order(with_actions(d, rev)))
    assert "action_order_violation" in cs and "action_rank_not_increasing" in cs

    d = make_digest(["take_profit_force", "take_profit_partial"])
    f, p = d.actions.items
    swapped = (dataclasses.replace(p, priority_rank=1), dataclasses.replace(f, priority_rank=2))
    assert "action_order_violation" in codes_of(R.validate_action_order(with_actions(d, swapped)))


def test_validate_action_order_rank_rules():
    d = make_digest(["cut", "add"])
    a0, a1 = d.actions.items
    none_rank = dataclasses.replace(a1, priority_rank=None)
    assert "action_rank_missing" in codes_of(R.validate_action_order(with_actions(d, (a0, none_rank))))
    high = dataclasses.replace(a0, priority_rank=5)       # 5 之後接 2：非遞增（重複 rank 由 AB-0 建構時擋）
    assert "action_rank_not_increasing" in codes_of(R.validate_action_order(with_actions(d, (high, a1))))


def test_validate_action_order_too_many_actions_defence_in_depth():
    d = make_digest(["cut", "take_profit_force", "pause_add"])
    extra = dataclasses.replace(d.actions.items[0], action_id="extra", priority_rank=9)
    sec = ActionsSection.__new__(ActionsSection)
    for k, v in (("availability", d.actions.availability), ("items", d.actions.items + (extra,)),
                 ("missing_reason", None)):
        object.__setattr__(sec, k, v)
    d2 = dataclasses.replace(d, actions=sec)
    assert len(d2.actions.items) == MAX_ACTIONS + 1
    assert "too_many_actions" in codes_of(R.validate_action_order(d2))


# ── validate_strict / assert_strict ─────────────────────────────────────
def test_validate_strict_is_validate_plus_extras():
    d = make_digest(["cut", "add"])
    assert validate(d) == () and R.validate_strict(d) == ()
    R.assert_strict(d)
    bad = dataclasses.replace(d.actions.items[0], rule=RuleRef("rule_x", "v"))
    d2 = with_actions(d, (bad,) + d.actions.items[1:])
    assert validate(d2) == ()                      # AB-0 本身認得 rule_x（臨時 id）
    assert codes_of(R.validate_strict(d2)) >= {"rule_not_allowlisted", "action_rule_not_allowed"}
    with pytest.raises(ValueError, match="rule_not_allowlisted"):
        R.assert_strict(d2)


def test_validate_strict_on_non_digest_does_not_raise():
    vs = R.validate_strict(None)
    assert [v.code for v in vs] == ["type"]
    assert [v.code for v in R.validate_rule_ids(object())] == ["type"]
    assert [v.code for v in R.validate_action_order(42)] == ["type"]
    with pytest.raises(ValueError):
        R.assert_strict("nope")


def test_ai_wording_in_rule_id_still_caught_by_ab0_defence_in_depth():
    with pytest.raises(ValueError, match="ai_reserved"):
        RuleRef("gemini_cut", "v1")


# ── L0 純度 ─────────────────────────────────────────────────────────────
def test_rules_module_is_l0_pure():
    tree = ast.parse((REPO / "shared" / "decision_digest_rules.py").read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0:
            mods.add((n.module or "").split(".")[0])
    assert "src" not in mods and "streamlit" not in mods
    assert mods <= {"__future__", "types", "typing", "shared"}
