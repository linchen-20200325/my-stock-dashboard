"""AB-1 Decision Digest Builder 測試（fast lane）。

守的是 `src/services/decision_digest_builder.py`：只搬運既有輸出、不發明日期、不發明鍵、
missing ≠ 0、unavailable ≠ neutral、行動依 Q4 序且上限 3、文字逐字等於真實引擎輸出。
行動文字／分支代碼用**真實引擎**（`assess_holding` → `row_from_assessment`）驗證。
"""
from __future__ import annotations

import ast
import dataclasses
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared import dividend_station_thresholds as T
from shared import station_specs as SS
from shared.allocation_decision import build_allocation_decision
from shared.decision_digest import (
    MAX_ACTIONS, Availability, DataStatus, DefinitionState, HoldingKey, MissingReason, StrategyType,
    validate,
)
from shared.decision_digest_rules import ACTION_RULE_IDS, validate_strict
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION, RiskCapDisclosure
from src.compute.etf import dividend_station as ds
from src.services import dividend_station_service as svc
from src.services.decision_digest_builder import SourceStamp, build_decision_digest

REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "src" / "services" / "decision_digest_builder.py"
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)          # 台北 2026-10-27 17:00
MACRO_STAMP = SourceStamp("macro_state.json", date(2026, 10, 26))
STATION_STAMP = SourceStamp("dividend_station_service", date(2026, 10, 26))


def disclosure(ts="2026-10-26 18:30:00"):
    return RiskCapDisclosure(snapshot_ts=ts, not_evaluated=(), disabled=(), sahm_status=None)


def macro(**over):
    base = {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5,
            "exposure_limit_pct": 60, "defense": False, "risk_cap_disclosure": disclosure()}
    base.update(over)
    return base


def fact_map(d):
    return {f.fact_id: f for f in d.market.facts}


# ── 真實引擎列 ───────────────────────────────────────────────────────────
_IDX = pd.date_range("2023-01-01", periods=120, freq="W-SUN")
_I = np.arange(120)
_SERIES = {
    "up": pd.Series(20 + 0.01 * _I + 0.05 * np.sin(_I), index=_IDX),
    "weak": pd.Series(np.r_[20 + 0.02 * _I[:112], (20 + 0.02 * 111) * np.cumprod(np.full(8, 0.98))], index=_IDX),
    "spike": pd.Series(np.r_[20 + 0.05 * np.sin(_I[:119]), 23.0], index=_IDX),
}
_CALM, _CRASH = T.VIX_LIGHT1 - 5.0, T.VIX_LIGHT3 + 2.0


def real_assessment(ticker, series, vix, *, tr1y=10.0, premium=0.1):
    return ds.assess_holding(
        ticker=ticker, name=ticker, asset_class=T.ASSET_CORE, weekly_close=_SERIES[series], vix=vix,
        premium_pct=premium, sharpe=0.8, total_return_1y_pct=tr1y, annual_yield_pct=5.0,
        inception_years=5, ann_return_3y_pct=5.0, cum_return_3y_pct=15.0, peer_ranks=None)


def real_row(ticker, series, vix, *, held=True, **kw):
    r = svc.row_from_assessment(real_assessment(ticker, series, vix, **kw))
    r["held"] = held
    return r


def keys_for(*tickers, pid="pf-A"):
    return {t: HoldingKey(pid, t) for t in tickers}


def holdings_for(*tickers, held=True):
    return [{"ticker": t, "name": f"name-{t}", "held": held, "asset_kind": "etf", "lots": 1, "avg_price": 10.0}
            for t in tickers]


def build(**kw):
    kw.setdefault("generated_at", NOW)
    return build_decision_digest(**kw)


def fake_row(ticker, code, text=None, held=True, detail=None):
    return {"代號": ticker, "held": held, "_action": code, "建議動作": text or f"txt-{code}-{ticker}",
            "_detail": detail if detail is not None else {}}


# ════════════════════════════════════════════════════════════════════════
# 基本形狀
# ════════════════════════════════════════════════════════════════════════
def test_empty_inputs_all_unavailable_and_valid():
    d = build()
    assert validate_strict(d) == ()
    assert d.market.availability is Availability.UNAVAILABLE
    assert all(f.status is DataStatus.MISSING and f.missing_reason is MissingReason.NO_INPUT
               for f in d.market.facts)
    assert d.holdings.availability is Availability.UNAVAILABLE
    assert d.holdings.unkeyed_count == 0 and d.holdings.entries == ()
    assert d.actions.availability is Availability.UNAVAILABLE
    assert d.risk_cap.cap_valid is False and d.risk_cap.availability is Availability.UNAVAILABLE
    assert d.ai_participation.value == "rule_only"
    json.dumps(d.to_dict(), ensure_ascii=False)


def test_definition_sections_are_fixed_and_never_populated():
    d = build(macro_state=macro(), macro_stamp=MACRO_STAMP)
    for name, want in (("tw_trend", DefinitionState.NOT_DEFINED), ("intl_trend", DefinitionState.NOT_DEFINED),
                       ("industry", DefinitionState.NOT_DEFINED), ("valuation", DefinitionState.RESEARCH_ONLY)):
        s = getattr(d, name)
        assert s.definition is want and s.observations == () and s.series_ref is None
        assert s.availability is Availability.UNAVAILABLE


def test_builder_signature_does_not_accept_industry_or_picks():
    import inspect
    params = set(inspect.signature(build_decision_digest).parameters)
    assert not any("industry" in p or "pick" in p or "concentration" in p for p in params)


# ════════════════════════════════════════════════════════════════════════
# market
# ════════════════════════════════════════════════════════════════════════
def test_market_ok_carries_verbatim_values_with_stamp_dates():
    d = build(macro_state=macro(), macro_stamp=MACRO_STAMP)
    fm = fact_map(d)
    assert fm["market.regime"].text == "bull" and fm["market.light"].text == "🟢"
    assert fm["market.health"].value == 72.5
    for f in fm.values():
        assert f.status is DataStatus.OK
        assert f.provenance.as_of == date(2026, 10, 26) and f.provenance.source == "macro_state.json"
        assert f.rule is None
    assert d.market.availability is Availability.AVAILABLE


def test_market_without_stamp_is_missing_never_ok_with_invented_date():
    d = build(macro_state=macro(), macro_stamp=None)
    for f in d.market.facts:
        assert f.status is DataStatus.MISSING and f.missing_reason is MissingReason.NO_INPUT
        assert f.value is None and f.text is None and f.provenance.as_of is None
    assert d.market.availability is Availability.UNAVAILABLE


def test_market_unknown_regime_and_blank_light_never_become_values():
    d = build(macro_state=macro(regime="unknown", light="⬜", health=None), macro_stamp=MACRO_STAMP)
    for f in d.market.facts:
        assert f.status is DataStatus.MISSING and f.text is None and f.value is None
    assert d.market.availability is Availability.UNAVAILABLE


def test_market_regime_unknown_only_hides_that_fact():
    d = build(macro_state=macro(regime="unknown"), macro_stamp=MACRO_STAMP)
    fm = fact_map(d)
    assert fm["market.regime"].status is DataStatus.MISSING
    assert fm["market.light"].status is DataStatus.OK and fm["market.health"].status is DataStatus.OK
    assert d.market.availability is Availability.PARTIAL


def test_market_not_loaded_is_missing_even_with_values_and_stamp():
    d = build(macro_state=macro(is_loaded=False), macro_stamp=MACRO_STAMP)
    assert all(f.status is DataStatus.MISSING for f in d.market.facts)


def test_market_health_zero_is_real_and_nan_is_invalid_not_zero():
    d = build(macro_state=macro(health=0.0), macro_stamp=MACRO_STAMP)
    h = fact_map(d)["market.health"]
    assert h.status is DataStatus.OK and h.value == 0.0
    d = build(macro_state=macro(health=float("nan")), macro_stamp=MACRO_STAMP)
    h = fact_map(d)["market.health"]
    assert h.status is DataStatus.INVALID and h.value is None and h.missing_reason is None
    d = build(macro_state=macro(health=True), macro_stamp=MACRO_STAMP)
    assert fact_map(d)["market.health"].status is DataStatus.INVALID


def test_source_stamp_validation():
    with pytest.raises(ValueError):
        SourceStamp("", date(2026, 10, 26))
    with pytest.raises(ValueError):
        SourceStamp("x", datetime(2026, 10, 26))            # datetime 不是 date
    with pytest.raises(ValueError):
        SourceStamp("x", date(2026, 10, 26), datetime(2026, 10, 26, 1, 0))   # naive fetched_at
    with pytest.raises(ValueError, match="ai_reserved"):
        build(macro_state=macro(), macro_stamp=SourceStamp("Gemini", date(2026, 10, 26)))


def test_future_stamp_date_fails_loud():
    with pytest.raises(ValueError, match="as_of_after_generated"):
        build(macro_state=macro(), macro_stamp=SourceStamp("x", date(2026, 10, 28)))


# ════════════════════════════════════════════════════════════════════════
# risk cap
# ════════════════════════════════════════════════════════════════════════
def test_risk_cap_ok_and_rule_and_unit():
    d = build(macro_state=macro(), macro_stamp=MACRO_STAMP)
    rc = d.risk_cap
    assert rc.cap_valid is True
    assert rc.cap_pct.status is DataStatus.OK and rc.cap_pct.value == 60.0 and rc.cap_pct.unit == "%"
    assert rc.cap_pct.provenance.as_of == date(2026, 10, 26)
    for f in rc.facts:
        assert f.rule == type(f.rule)("risk_cap", RISK_CAP_RULESET_VERSION)
    # 沒有 allocation → lo/hi 缺，整段 PARTIAL
    assert rc.exposure_lo_pct.status is DataStatus.MISSING and rc.availability is Availability.PARTIAL


def test_risk_cap_zero_is_a_real_zero_and_none_stays_missing():
    d0 = build(macro_state=macro(exposure_limit_pct=0), macro_stamp=MACRO_STAMP)
    assert d0.risk_cap.cap_valid is True
    assert d0.risk_cap.cap_pct.status is DataStatus.OK and d0.risk_cap.cap_pct.value == 0.0
    dn = build(macro_state=macro(exposure_limit_pct=None), macro_stamp=MACRO_STAMP)
    assert dn.risk_cap.cap_valid is False
    assert dn.risk_cap.cap_pct.status is DataStatus.MISSING and dn.risk_cap.cap_pct.value is None
    assert dn.risk_cap.cap_pct.missing_reason is MissingReason.NO_INPUT


@pytest.mark.parametrize("bad", [101, -1, float("nan"), float("inf"), True, "60"])
def test_risk_cap_out_of_domain_or_bad_type_is_invalid_not_clamped(bad):
    d = build(macro_state=macro(exposure_limit_pct=bad), macro_stamp=MACRO_STAMP)
    assert d.risk_cap.cap_valid is False
    assert d.risk_cap.cap_pct.status is DataStatus.INVALID and d.risk_cap.cap_pct.value is None


def test_risk_cap_valid_proxy_requires_disclosure_timestamp():
    for disc in (None, disclosure(""), disclosure("not-a-date"), disclosure("2026-10-26")):
        d = build(macro_state=macro(risk_cap_disclosure=disc), macro_stamp=MACRO_STAMP)
        assert d.risk_cap.cap_valid is False
        assert d.risk_cap.cap_pct.status is DataStatus.MISSING and d.risk_cap.cap_pct.value is None
        assert d.risk_cap.cap_pct.provenance.as_of is None


def test_risk_cap_does_not_need_macro_stamp():
    d = build(macro_state=macro(), macro_stamp=None)
    assert d.risk_cap.cap_valid is True and d.risk_cap.cap_pct.status is DataStatus.OK


@pytest.mark.parametrize("ts, want", [
    ("2026-10-26 23:30:00", date(2026, 10, 26)),   # 台北 23:30：不是隔天（不可當 UTC 再轉）
    ("2026-10-27 00:30:00", date(2026, 10, 27)),   # 台北 00:30：UTC 日期是前一天，仍取台北日期
    ("2026-10-26 08:00:00", date(2026, 10, 26)),
])
def test_snapshot_ts_taipei_date(ts, want):
    d = build(macro_state=macro(risk_cap_disclosure=disclosure(ts)), macro_stamp=MACRO_STAMP)
    assert d.risk_cap.cap_pct.provenance.as_of == want


def test_snapshot_ts_in_future_fails_loud():
    with pytest.raises(ValueError, match="as_of_after_generated"):
        build(macro_state=macro(risk_cap_disclosure=disclosure("2026-10-28 00:10:00")))


def test_disclosure_is_read_only_from_macro_state_not_from_allocation():
    """A.3：揭露只讀 macro_state；allocation 帶的揭露不得被當成第二條取數路徑（cap_valid 保守為 False）。"""
    ms = macro()
    alloc = build_allocation_decision(ms)
    alloc = dataclasses.replace(alloc, risk_cap_disclosure=disclosure())
    ms2 = {k: v for k, v in ms.items() if k != "risk_cap_disclosure"}
    d = build(macro_state=ms2, macro_stamp=MACRO_STAMP, allocation=alloc)
    assert d.risk_cap.cap_valid is False
    assert d.risk_cap.cap_pct.status is DataStatus.MISSING and d.risk_cap.cap_pct.value is None


def test_snapshot_ts_format_pinned_to_macro_state_locker():
    import src.services.decision_digest_builder as B
    from src.services import macro_state_locker as L
    assert B._SNAPSHOT_TS_FMT == L._TIMESTAMP_FMT


def test_unevaluated_placeholders_are_the_regime_arbiter_ssot_and_case_insensitive():
    from shared.regime_arbiter import UNLOADED_VERDICT
    assert (UNLOADED_VERDICT.regime, UNLOADED_VERDICT.light) == ("unknown", "⬜")
    d = build(macro_state=macro(regime=" UNKNOWN ", light="⬜"), macro_stamp=MACRO_STAMP)
    fm = fact_map(d)
    assert fm["market.regime"].status is DataStatus.MISSING and fm["market.light"].status is DataStatus.MISSING
    # 一般值仍逐字（含大小寫、前後空白不被「修飾」）
    d = build(macro_state=macro(regime="Bull"), macro_stamp=MACRO_STAMP)
    assert fact_map(d)["market.regime"].text == "Bull"


def test_risk_cap_uses_exposure_limit_pct_not_allocation_min_cap():
    ms = macro(exposure_limit_pct=80)
    from shared.allocation_decision import Cap
    alloc = build_allocation_decision(ms, caps=(Cap("其他", 30, "x"),))
    assert alloc.cap_pct == 30                       # allocation 的 cap_pct 是最小值
    d = build(macro_state=ms, macro_stamp=MACRO_STAMP, allocation=alloc)
    assert d.risk_cap.cap_pct.value == 80.0          # builder 取 exposure_limit_pct，不是 30


def test_allocation_loaded_carries_final_lo_hi_with_macro_stamp_date():
    ms = macro()
    alloc = build_allocation_decision(ms)
    assert alloc.is_loaded and alloc.final_lo is not None
    d = build(macro_state=ms, macro_stamp=MACRO_STAMP, allocation=alloc)
    lo, hi = d.risk_cap.exposure_lo_pct, d.risk_cap.exposure_hi_pct
    assert (lo.status, hi.status) == (DataStatus.OK, DataStatus.OK)
    assert (lo.value, hi.value) == (float(alloc.final_lo), float(alloc.final_hi))
    assert lo.provenance.as_of == date(2026, 10, 26)
    assert d.risk_cap.availability is Availability.AVAILABLE


def test_allocation_not_loaded_makes_lo_hi_missing():
    ms = macro(is_loaded=False)
    alloc = build_allocation_decision(ms)
    assert alloc.is_loaded is False
    d = build(macro_state=macro(), macro_stamp=MACRO_STAMP, allocation=alloc)
    assert d.risk_cap.exposure_lo_pct.status is DataStatus.MISSING
    assert d.risk_cap.exposure_hi_pct.status is DataStatus.MISSING
    assert d.risk_cap.exposure_lo_pct.value is None


def test_allocation_flagged_not_loaded_is_trusted_even_if_final_values_present():
    alloc = dataclasses.replace(build_allocation_decision(macro()), is_loaded=False)
    assert alloc.final_lo is not None            # 不一致的上游：旗標說未載入、卻帶值
    d = build(macro_state=macro(), macro_stamp=MACRO_STAMP, allocation=alloc)
    assert d.risk_cap.exposure_lo_pct.status is DataStatus.MISSING and d.risk_cap.exposure_lo_pct.value is None
    assert d.risk_cap.exposure_hi_pct.status is DataStatus.MISSING


def test_allocation_loaded_without_macro_stamp_has_no_invented_date():
    alloc = build_allocation_decision(macro())
    d = build(macro_state=macro(), macro_stamp=None, allocation=alloc)
    assert d.risk_cap.exposure_lo_pct.status is DataStatus.MISSING
    assert d.risk_cap.exposure_lo_pct.provenance.as_of is None


# ════════════════════════════════════════════════════════════════════════
# holdings & keys
# ════════════════════════════════════════════════════════════════════════
def test_holdings_none_is_unavailable_unknown_not_zero():
    d = build(holdings_rows=None)
    assert d.holdings.availability is Availability.UNAVAILABLE
    assert d.holdings.missing_reason is MissingReason.NO_INPUT and d.holdings.unkeyed_count == 0


def test_no_keys_supplied_means_no_entries_and_all_held_counted_unkeyed():
    d = build(holdings_rows=holdings_for("0050", "0056") + holdings_for("9999", held=False),
              holding_keys=None)
    assert d.holdings.entries == ()
    assert d.holdings.unkeyed_count == 2                 # 觀察清單（held=False）不算
    assert d.holdings.availability is Availability.UNAVAILABLE
    assert d.holdings.missing_reason is MissingReason.NO_INPUT


def test_portfolio_name_never_becomes_a_key():
    rows = [{"ticker": "0050", "name": "元大台灣50", "held": True, "portfolio_name": "我的組合"}]
    d = build(holdings_rows=rows, holding_keys={})
    assert d.holdings.entries == () and d.holdings.unkeyed_count == 1
    assert "我的組合" not in json.dumps(d.to_dict(), ensure_ascii=False)


def test_only_supplied_keys_become_entries_with_unclassified_strategy():
    d = build(holdings_rows=holdings_for("0050", "0056"), holding_keys=keys_for("0050"))
    assert [e.key for e in d.holdings.entries] == [HoldingKey("pf-A", "0050")]
    e = d.holdings.entries[0]
    assert e.strategy is StrategyType.UNCLASSIFIED and e.strategy_source is None
    assert d.holdings.unkeyed_count == 1


def test_key_symbol_mismatch_or_wrong_type_fails_loud():
    with pytest.raises(ValueError, match="不一致"):
        build(holdings_rows=holdings_for("0050"), holding_keys={"0050": HoldingKey("pf", "0056")})
    with pytest.raises(TypeError):
        build(holdings_rows=holdings_for("0050"), holding_keys={"0050": "pf:0050"})


def test_duplicate_held_rows_are_not_silently_deduped():
    with pytest.raises(ValueError, match="duplicate_holding_key"):
        build(holdings_rows=holdings_for("0050", "0050"), holding_keys=keys_for("0050"))


def test_holdings_with_unkeyed_and_actions_is_partial_not_available():
    rows = [fake_row("0050", "add")]
    d = build(holdings_rows=holdings_for("0050", "0056"), holding_keys=keys_for("0050"),
              station_rows=rows, station_stamp=STATION_STAMP)
    assert d.holdings.availability is Availability.PARTIAL and d.holdings.unkeyed_count == 1


# ════════════════════════════════════════════════════════════════════════
# actions
# ════════════════════════════════════════════════════════════════════════
def act_digest(rows, tickers=None, stamp=STATION_STAMP, **kw):
    tickers = tickers or [r["代號"] for r in rows]
    return build(holdings_rows=holdings_for(*tickers), holding_keys=keys_for(*tickers),
                 station_rows=rows, station_stamp=stamp, **kw)


def _partial_assessment(ticker):
    a = real_assessment(ticker, "up", _CALM)
    return dataclasses.replace(a, light=dataclasses.replace(a.light, take_profit="partial"))


def test_actions_text_is_verbatim_from_real_engine_for_every_carried_branch():
    assessments = [
        real_assessment("00901", "up", _CRASH, tr1y=1.0),                       # cut
        real_assessment("00902", "spike", _CRASH),                              # take_profit_force
        _partial_assessment("00903"),                                           # take_profit_partial
        real_assessment("00904", "weak", _CALM),                                # pause_add
        real_assessment("00905", "up", (T.VIX_LIGHT2 + T.VIX_LIGHT3) / 2),      # add
    ]
    assert [ds.action_branch(a) for a in assessments] == list(ACTION_RULE_IDS)
    rows = []
    for a in assessments:
        r = svc.row_from_assessment(a)
        r["held"] = True
        rows.append(r)
    expected = {a.ticker: ds.suggest_action(a) for a in assessments}   # 引擎本身的輸出（獨立呼叫）
    for chunk in (rows[:3], rows[3:]):
        d = act_digest(chunk)
        assert len(d.actions.items) == len(chunk)
        for item in d.actions.items:
            tk = item.target.symbol
            assert item.text == expected[tk]
            assert item.rule.rule_id == ds.action_branch(next(a for a in assessments if a.ticker == tk))
            assert item.rule.rule_version == "action_branch.v1"
    # 動態字串（含 emoji、%、標點）原樣保留
    assert "暫停加碼" in expected["00904"] and "加碼" in expected["00905"]


def test_action_text_equals_fact_text_and_evidence_points_to_it():
    d = act_digest([fake_row("0050", "cut", "🔴 汰弱：吃本金")])
    a = d.actions.items[0]
    fact = d.holdings.entries[0].facts[0]
    assert a.evidence_refs == (fact.fact_id,) and fact.text == a.text == "🔴 汰弱：吃本金"
    assert fact.status is DataStatus.OK and fact.provenance.as_of == date(2026, 10, 26)
    assert fact.rule == a.rule and a.target == d.holdings.entries[0].key
    assert a.origin.value == "rule_layer"


def test_actions_sorted_by_q4_tiers_with_ranks():
    rows = [fake_row("A", "add"), fake_row("B", "take_profit_partial"), fake_row("C", "pause_add")]
    d = act_digest(rows)
    assert [a.rule.rule_id for a in d.actions.items] == ["take_profit_partial", "pause_add", "add"]
    assert [a.priority_rank for a in d.actions.items] == [1, 2, 3]
    rows = [fake_row("A", "take_profit_partial"), fake_row("B", "take_profit_force"), fake_row("C", "cut")]
    d = act_digest(rows)
    assert [a.rule.rule_id for a in d.actions.items] == ["cut", "take_profit_force", "take_profit_partial"]


def test_ties_keep_input_order():
    rows = [fake_row("Z", "add"), fake_row("A", "add"), fake_row("M", "add")]
    d = act_digest(rows)
    assert [a.target.symbol for a in d.actions.items] == ["Z", "A", "M"]


def test_truncated_to_max_actions_keeping_highest_priority():
    rows = [fake_row(f"T{i}", c) for i, c in enumerate(
        ["add", "pause_add", "add", "take_profit_force", "cut", "take_profit_partial"])]
    d = act_digest(rows)
    assert MAX_ACTIONS == 3 and len(d.actions.items) == 3
    assert [a.rule.rule_id for a in d.actions.items] == ["cut", "take_profit_force", "take_profit_partial"]
    assert [a.priority_rank for a in d.actions.items] == [1, 2, 3]
    # 被截斷者不留殘影在 holdings facts
    assert sum(len(e.facts) for e in d.holdings.entries) == 3
    assert len(d.holdings.entries) == 6


@pytest.mark.parametrize("code", ["premium", "cruise", "unknown_code", "", None, 7])
def test_non_action_branches_are_never_carried(code):
    d = act_digest([fake_row("0050", code)])
    assert d.actions.items == () and d.actions.availability is Availability.UNAVAILABLE
    assert all(not e.facts for e in d.holdings.entries)


def test_real_premium_and_cruise_rows_not_carried():
    cruise = real_row("00910", "up", _CALM)
    premium = real_row("00911", "up", _CALM, premium=T.PREMIUM_ALERT_PCT + 3.0)
    assert cruise["_action"] == ds.ACTION_CRUISE and premium["_action"] == ds.ACTION_PREMIUM
    d = act_digest([cruise, premium])
    assert d.actions.items == () and d.actions.availability is Availability.UNAVAILABLE


def test_rows_with_error_not_held_unkeyed_or_no_stamp_are_not_carried():
    err = fake_row("E", "cut", detail={"error": "抓取失敗"})
    watch = fake_row("W", "cut", held=False)
    ok = fake_row("K", "add")
    d = build(holdings_rows=holdings_for("E", "W", "K"), holding_keys=keys_for("E", "W", "K"),
              station_rows=[err, watch, ok], station_stamp=STATION_STAMP)
    assert [a.target.symbol for a in d.actions.items] == ["K"]
    # 無鍵
    d = build(holdings_rows=holdings_for("K", "N"), holding_keys=keys_for("K"),
              station_rows=[fake_row("N", "cut"), ok], station_stamp=STATION_STAMP)
    assert [a.target.symbol for a in d.actions.items] == ["K"]
    # 持股清單沒有這檔（鍵在，但不在 holdings 內）→ 不搬
    d = build(holdings_rows=holdings_for("K"), holding_keys=keys_for("K", "N"),
              station_rows=[fake_row("N", "cut"), ok], station_stamp=STATION_STAMP)
    assert [a.target.symbol for a in d.actions.items] == ["K"]


def test_no_station_stamp_means_no_actions_and_never_invents_a_date():
    d = act_digest([fake_row("0050", "cut")], stamp=None)
    assert d.actions.items == () and d.actions.availability is Availability.UNAVAILABLE
    assert d.actions.missing_reason is MissingReason.NO_INPUT
    assert all(not e.facts for e in d.holdings.entries)
    assert "2026" not in json.dumps([f.provenance.as_of for e in d.holdings.entries for f in e.facts], default=str)


def test_actions_unavailable_when_holdings_unavailable():
    for kw in (dict(holdings_rows=None), dict(holdings_rows=[]),
               dict(holdings_rows=holdings_for("0050"), holding_keys=None)):
        d = build(station_rows=[fake_row("0050", "cut")], station_stamp=STATION_STAMP, **kw)
        assert d.holdings.availability is Availability.UNAVAILABLE
        assert d.actions.availability is Availability.UNAVAILABLE and d.actions.items == ()
        assert validate_strict(d) == ()


def test_inputs_missing_never_becomes_available_with_nothing_to_do():
    # 持股、鍵、stamp 都齊，但規則層沒有可搬運的行動：v1 不得說「可得、沒事做」
    d = act_digest([fake_row("0050", "cruise")])
    assert d.actions.availability is Availability.UNAVAILABLE


def test_station_rows_none_is_no_input():
    d = build(holdings_rows=holdings_for("0050"), holding_keys=keys_for("0050"), station_rows=None,
              station_stamp=STATION_STAMP)
    assert d.actions.availability is Availability.UNAVAILABLE


def test_two_portfolios_same_symbol_are_distinct_keys():
    rows = [fake_row("0050", "cut")]
    d = build(holdings_rows=holdings_for("0050"), holding_keys={"0050": HoldingKey("pf-B", "0050")},
              station_rows=rows, station_stamp=STATION_STAMP)
    assert d.actions.items[0].target == HoldingKey("pf-B", "0050")


# ════════════════════════════════════════════════════════════════════════
# 總體：契約、序列化、純度
# ════════════════════════════════════════════════════════════════════════
def test_full_digest_passes_strict_and_serializes():
    ms = macro()
    d = build(macro_state=ms, macro_stamp=MACRO_STAMP, allocation=build_allocation_decision(ms),
              station_rows=[fake_row("A", "cut"), fake_row("B", "add")], station_stamp=STATION_STAMP,
              holdings_rows=holdings_for("A", "B", "C"), holding_keys=keys_for("A", "B"))
    assert validate(d) == () and validate_strict(d) == ()
    out = d.to_dict()
    json.dumps(out, ensure_ascii=False)
    assert out["actions"]["availability"] == "available"
    assert out["ai_participation"] == "rule_only"
    assert out["holdings"]["unkeyed_count"] == 1


def test_builder_raises_value_error_if_it_would_emit_a_violation(monkeypatch):
    import src.services.decision_digest_builder as B
    monkeypatch.setattr(B, "ACTION_RULE_VERSION", "action_branch.v999")
    with pytest.raises(ValueError, match="rule_version_not_allowed"):
        act_digest([fake_row("0050", "cut")])


# ── 型別異常：Fail Loud，不默默當成「沒給」 ────────────────────────────────
@pytest.mark.parametrize("kw", [
    dict(macro_state=["is_loaded"]), dict(macro_state="x"),
    dict(macro_stamp=date(2026, 10, 26)), dict(macro_stamp=("m", date(2026, 10, 26))),
    dict(station_stamp="s"), dict(allocation=object()), dict(allocation={"is_loaded": True}),
    dict(station_rows="abc"), dict(station_rows={"a": 1}), dict(holdings_rows="abc"),
    dict(holdings_rows={"ticker": "0050"}), dict(holding_keys=[HoldingKey("p", "0050")]),
    dict(holding_keys="x"),
])
def test_wrong_input_types_raise_type_error(kw):
    with pytest.raises(TypeError):
        build(**kw)


def test_generated_at_wrong_type_or_non_utc_fails_loud():
    with pytest.raises(ValueError):
        build_decision_digest(generated_at="2026-10-27")  # type: ignore[arg-type]
    from datetime import timedelta
    with pytest.raises(ValueError, match="generated_at_not_utc"):
        build_decision_digest(generated_at=datetime(2026, 10, 27, 9, 0, tzinfo=timezone(timedelta(hours=8))))


def test_non_mapping_rows_inside_lists_are_ignored_not_crashing():
    d = build(holdings_rows=[None, 3, "x", holdings_for("0050")[0]], holding_keys=keys_for("0050"),
              station_rows=[None, 7, fake_row("0050", "cut")], station_stamp=STATION_STAMP)
    assert [a.rule.rule_id for a in d.actions.items] == ["cut"]


@pytest.mark.parametrize("held", [1, "True", "yes", 1.0, np.True_, np.False_, 0, ""])
def test_held_non_bool_fails_loud_never_silently_not_held(held):
    with pytest.raises(TypeError):
        build(holdings_rows=[{"ticker": "0050", "held": held}], holding_keys=keys_for("0050"))
    with pytest.raises(TypeError):
        build(holdings_rows=holdings_for("0050"), holding_keys=keys_for("0050"),
              station_rows=[dict(fake_row("0050", "cut"), held=held)], station_stamp=STATION_STAMP)


def test_held_none_missing_or_false_means_not_held():
    for row in ({"ticker": "0050"}, {"ticker": "0050", "held": None}, {"ticker": "0050", "held": False}):
        d = build(holdings_rows=[row], holding_keys=keys_for("0050"))
        assert d.holdings.entries == () and d.holdings.unkeyed_count == 0


@pytest.mark.parametrize("code", ["cut", "add"])
@pytest.mark.parametrize("key, val", [
    (SS.KEY_INVALID_LIGHTS, ("健檢A",)), (SS.KEY_INVALID_LIGHTS, ["235"]),
    (SS.KEY_INVALID_INPUTS, (SS.ITEM_LOTS,)), (SS.KEY_INVALID_INPUTS, ("均價", "現價")),
])
def test_rows_with_invalid_data_marks_never_produce_actions(code, key, val):
    bad = dict(fake_row("0050", code), **{key: val})
    ok = fake_row("0056", "add")
    d = act_digest([bad, ok])
    assert [a.target.symbol for a in d.actions.items] == ["0056"]
    assert all(not e.facts for e in d.holdings.entries if e.key.symbol == "0050")


@pytest.mark.parametrize("key", [SS.KEY_INVALID_LIGHTS, SS.KEY_INVALID_INPUTS])
@pytest.mark.parametrize("empty", [(), [], {}, None, set()])
def test_empty_invalid_marks_mean_no_anomaly(key, empty):
    d = act_digest([dict(fake_row("0050", "cut"), **{key: empty})])
    assert [a.rule.rule_id for a in d.actions.items] == ["cut"]


def test_invalid_mark_keys_are_the_station_specs_ssot():
    assert SS.KEY_INVALID_LIGHTS == "_invalid_lights" and SS.KEY_INVALID_INPUTS == "_invalid_inputs"


def test_invalid_row_with_unusable_text_is_skipped_before_text_check():
    row = dict(fake_row("0050", "cut"), **{SS.KEY_INVALID_INPUTS: ("張數",)})
    row["建議動作"] = None
    assert act_digest([row]).actions.items == ()


def test_two_qualifying_rows_same_ticker_fail_loud_duplicate_action_id():
    with pytest.raises(ValueError, match="duplicate_action_id"):
        build(holdings_rows=holdings_for("0050"), holding_keys=keys_for("0050"),
              station_rows=[fake_row("0050", "cut"), fake_row("0050", "add")], station_stamp=STATION_STAMP)


@pytest.mark.parametrize("text", [None, "", "   ", 7, "N/A", "—"])
def test_carryable_row_with_unusable_text_fails_loud_not_silently_dropped(text):
    row = fake_row("0050", "cut")
    row["建議動作"] = text
    with pytest.raises(ValueError):
        act_digest([row])


def test_unusable_text_on_a_non_carryable_row_is_ignored():
    # premium／無鍵／非持有／error 列的文字不在搬運範圍，不應炸
    bad = [dict(fake_row("0050", "premium"), 建議動作=None),
           dict(fake_row("0050", "cut", held=False), 建議動作=None),
           dict(fake_row("0050", "cut", detail={"error": "x"}), 建議動作=None)]
    d = act_digest(bad, tickers=["0050"])
    assert d.actions.items == ()


def test_row_without_action_key_like_stock_rows_is_skipped():
    stock_row = {"代號": "2330", "held": True, "建議動作": "換股字串", "_detail": {}}   # 個股列：無 _action
    d = act_digest([stock_row])
    assert d.actions.items == () and all(not e.facts for e in d.holdings.entries)


def test_ticker_falls_back_to_chinese_key_and_blank_ticker_is_unkeyed():
    d = build(holdings_rows=[{"ticker": "  ", "held": True}, {"held": True}], holding_keys=keys_for("0050"))
    assert d.holdings.unkeyed_count == 2 and d.holdings.entries == ()


def test_action_ids_do_not_collide_across_portfolios():
    keys = {"A": HoldingKey("p1", "A"), "B": HoldingKey("p2", "A")}
    # 同 symbol 不同組合：各自可獨立有鍵（此處以不同 ticker 字串映到同 symbol 會被 symbol 不一致擋下）
    with pytest.raises(ValueError, match="不一致"):
        build(holdings_rows=holdings_for("B"), holding_keys={"B": keys["B"]})


def test_upstream_branch_codes_are_exactly_allowlist_plus_the_two_excluded():
    """上游若新增 `ACTION_*` 分支碼，這裡轉紅 —— 逼人決定它在 Q4 序的位置，而不是被默默忽略。"""
    upstream = {getattr(ds, n) for n in dir(ds) if n.startswith("ACTION_") and isinstance(getattr(ds, n), str)}
    assert upstream == set(ACTION_RULE_IDS) | {ds.ACTION_PREMIUM, ds.ACTION_CRUISE}


def test_every_allowlisted_id_is_accepted_by_ab0_constructors():
    """允許名單與 AB-0 拒收名單相容：名單成員不得被 AI／方向字樣拒收誤殺。"""
    from shared.decision_digest import RuleRef
    from shared.decision_digest_rules import ACTION_RULE_VERSION, RULE_ID_ALLOWLIST
    for rid, vers in RULE_ID_ALLOWLIST.items():
        for v in vers:
            RuleRef(rid, v)
    assert ACTION_RULE_VERSION == "action_branch.v1"


@pytest.mark.parametrize("flag", ["yes", 1, 1.0, "True", np.True_])
def test_is_loaded_non_bool_fails_loud(flag):
    with pytest.raises(TypeError):
        build(macro_state=macro(is_loaded=flag), macro_stamp=MACRO_STAMP)
    alloc = dataclasses.replace(build_allocation_decision(macro()), is_loaded=flag)
    with pytest.raises(TypeError):
        build(macro_state=macro(), macro_stamp=MACRO_STAMP, allocation=alloc)


def test_is_loaded_none_or_false_is_missing():
    for flag in (None, False):
        d = build(macro_state=macro(is_loaded=flag), macro_stamp=MACRO_STAMP)
        assert all(f.status is DataStatus.MISSING for f in d.market.facts)
        alloc = dataclasses.replace(build_allocation_decision(macro()), is_loaded=flag)
        d = build(macro_state=macro(), macro_stamp=MACRO_STAMP, allocation=alloc)
        assert d.risk_cap.exposure_lo_pct.status is DataStatus.MISSING


@pytest.mark.parametrize("txt", ["N/A", " n/a ", "—", "-", "--", "未知", "None", "null", "nan", "無資料", "0", "0.0%",
                                 "Ｎ／Ａ", "N\u200b/A"])
def test_ab0_placeholder_texts_degrade_to_missing_not_crash(txt):
    d = build(macro_state=macro(regime=txt, light=txt), macro_stamp=MACRO_STAMP)
    fm = fact_map(d)
    assert fm["market.regime"].status is DataStatus.MISSING and fm["market.light"].status is DataStatus.MISSING
    assert fm["market.health"].status is DataStatus.OK


def test_placeholder_mirror_agrees_with_ab0_fact_oracle():
    """本檔的佔位字複本與 AB-0 `Fact` 的實際拒收一致：AB-0 拒收者都被降級；AB-0 接受者都被逐字搬運。"""
    import src.services.decision_digest_builder as B
    from shared.decision_digest import PLACEHOLDER_TEXTS, Fact, Provenance
    cands = sorted(PLACEHOLDER_TEXTS) + ["0", "0.0", "0%", "bull", "🟢", "Bull", "neutral", "N/A "]
    for c in cands:
        try:
            Fact("x", DataStatus.OK, Provenance("s", date(2026, 10, 26)), text=c)
            rejected = False
        except ValueError:
            rejected = True
        assert B._is_placeholder_text(c) == rejected, c


@pytest.mark.parametrize("bad", [5, 1.5, ["bull"], b"bull", "", "   "])
def test_non_str_or_blank_regime_light_are_missing(bad):
    d = build(macro_state=macro(regime=bad, light=bad), macro_stamp=MACRO_STAMP)
    fm = fact_map(d)
    assert fm["market.regime"].status is DataStatus.MISSING and fm["market.light"].status is DataStatus.MISSING
    assert fm["market.health"].status is DataStatus.OK


def test_blank_light_symbol_with_surrounding_whitespace_is_still_missing():
    d = build(macro_state=macro(light=" ⬜ "), macro_stamp=MACRO_STAMP)
    assert fact_map(d)["market.light"].status is DataStatus.MISSING


def test_source_stamp_source_type():
    with pytest.raises(ValueError):
        SourceStamp(5, date(2026, 10, 26))   # type: ignore[arg-type]
    with pytest.raises(ValueError):
        SourceStamp("   ", date(2026, 10, 26))


def test_action_text_is_carried_byte_for_byte_including_edge_whitespace():
    raw = "  🔴 汰弱：吃本金  \u3000"
    d = act_digest([fake_row("0050", "cut", raw)])
    assert d.actions.items[0].text == raw and d.holdings.entries[0].facts[0].text == raw
    assert d.to_dict()["actions"]["items"][0]["text"] == raw


def test_station_stamp_dates_propagate_to_fact_provenance():
    st = SourceStamp("dividend_station_service", date(2026, 10, 24),
                     datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc))
    d = act_digest([fake_row("0050", "cut")], stamp=st)
    pv = d.holdings.entries[0].facts[0].provenance
    assert (pv.source, pv.as_of, pv.fetched_at) == ("dividend_station_service", date(2026, 10, 24), st.fetched_at)


def test_market_stamp_fetched_at_after_generated_fails_loud():
    st = SourceStamp("m", date(2026, 10, 26), datetime(2026, 10, 28, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="fetched_after_generated"):
        build(macro_state=macro(), macro_stamp=st)


def test_naive_generated_at_fails_loud():
    with pytest.raises(ValueError):
        build_decision_digest(generated_at=datetime(2026, 10, 27, 9, 0))


def _imports(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0:
            mods.add(n.module or "")
    return mods


def test_builder_imports_no_streamlit_ui_or_network():
    mods = _imports(BUILDER)
    banned = ("streamlit", "requests", "yfinance", "FinMind", "src.ui", "src.ui_v2", "src.data",
              "src.compute", "app")
    for m in mods:
        assert not any(m == b or m.startswith(b + ".") for b in banned), m
    assert {m.split(".")[0] for m in mods} <= {"__future__", "math", "numbers", "dataclasses",
                                                "datetime", "typing", "shared", "re", "unicodedata"}


def test_builder_not_imported_directly_by_app_or_ia_nav():
    """⚠️ 只檢查直接 import（不追蹤間接鏈），與 AB-0 的鎖相同。"""
    for rel in ("app.py", "shared/ia_nav.py"):
        mods = _imports(REPO / rel)
        assert not any("decision_digest" in m for m in mods), (rel, mods)
