"""src/compute/health/financial_period_adapter.py 單元測試（離線、決定性、無網路）。

涵蓋：真 0 保留 / 缺值各路徑 / legacy 假值 / 多筆觀測衝突 / 不推定（basis、published_at、
company_type）/ 全流程 raw→證據對手算 / 原始異常 vs 重置異常對照 / 驗證 raise 全集 /
不可變、決定性、不改輸入 / 禁字與 emoji 掃描 / 模組純度（AST）/ 突變防守。

突變防守（class TestMutationGuards）：把某個防線拔掉（monkeypatch），對應的
``_assert_*`` 輔助函式必須因此失敗，證明測試真的守得到該防線。
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import datetime as dt
import math
import pathlib
import random
import re
from decimal import Decimal

import pytest

import src.compute.health.financial_period_adapter as fpa
from src.compute.health.financial_health_evidence import (
    ITEM_NAMES,
    METRIC_NAMES,
    FinancialEvidence,
    FinancialEvidenceInputError,
    FinancialPeriodInput,
    build_financial_evidence,
)
from src.compute.health.financial_period_adapter import (
    EVIDENCE_KINDS,
    GAP_REASON_CODES,
    AdaptedEvidence,
    AdaptedPeriod,
    AdapterGap,
    FinancialPeriodAdapterError,
    RawFinancialPeriod,
    RawObservation,
    adapt_financial_period,
    build_evidence_from_raw,
)

TZ = dt.timezone(dt.timedelta(hours=8))
FETCHED = dt.datetime(2026, 11, 1, 12, 0, tzinfo=TZ)
PERIOD_END = dt.date(2026, 9, 30)

BASE_ITEMS = {
    "revenue": 1_234_567.0, "cogs": 700_000.0, "gross_profit": 534_567.0,
    "operating_income": 187_654.0, "net_income": 143_210.0,
    "total_assets": 5_432_100.0, "current_assets": 2_345_678.0,
    "current_liabilities": 1_098_765.0, "total_liabilities": 2_468_024.0,
    "equity": 2_964_076.0, "cash": 812_345.0, "inventory": 345_678.0,
    "ocf": 198_765.0, "capex": 50_000.0, "dividends": 30_000.0,
}


def ob(item: str, value=0.0, evidence: str = "source_reported", label: str | None = None, **kw):
    return RawObservation(item=item, value=value, evidence=evidence,
                          source_label=label or f"LBL_{item}", **kw)


def full_obs(overrides: dict | None = None, drop: tuple[str, ...] = ()) -> list[RawObservation]:
    vals = dict(BASE_ITEMS)
    vals.update(overrides or {})
    return [ob(k, v) for k, v in vals.items() if k not in drop]


def make_raw(observations=None, **over) -> RawFinancialPeriod:
    kw = dict(period_end=PERIOD_END, source="TEST:SRC", fetched_at=FETCHED, unit="千元",
              currency="TWD", basis="single_quarter", published_at=dt.date(2026, 11, 12),
              company_type="general",
              observations=full_obs() if observations is None else observations)
    kw.update(over)
    return RawFinancialPeriod(**kw)


def _be(raw):
    """呼叫 build_evidence_from_raw，確認回傳型別是 AdaptedEvidence，並拆成 (evidence, gaps)。"""
    res = build_evidence_from_raw(raw)
    assert isinstance(res, AdaptedEvidence)
    assert isinstance(res.evidence, FinancialEvidence) and isinstance(res.gaps, tuple)
    assert res.currency == raw.currency
    return res.evidence, res.gaps


def isc(a, b, tol=1e-9) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=1e-9)


def gaps_of(a: AdaptedPeriod) -> dict[str, str]:
    return {g.item: g.reason_code for g in a.gaps}


def _handcalc(i: dict) -> dict:
    return {
        "gross_margin_pct": i["gross_profit"] / i["revenue"] * 100,
        "operating_margin_pct": i["operating_income"] / i["revenue"] * 100,
        "net_margin_pct": i["net_income"] / i["revenue"] * 100,
        "cash_ratio_pct": i["cash"] / i["total_assets"] * 100,
        "debt_ratio_pct": i["total_liabilities"] / i["total_assets"] * 100,
        "current_ratio": i["current_assets"] / i["current_liabilities"],
        "quick_ratio": (i["current_assets"] - i["inventory"]) / i["current_liabilities"],
        "ocf_to_net_income": i["ocf"] / i["net_income"],
    }


# ── 正常流程 ─────────────────────────────────────────────────────────

class TestFullFlowAgainstHandCalc:
    def test_all_eight_ratios_match_hand_calc(self):
        e, gaps = _be(make_raw())
        assert gaps == ()
        assert tuple(e.metrics) == METRIC_NAMES
        for name, want in _handcalc(BASE_ITEMS).items():
            m = e.metrics[name]
            assert m.status == "ok" and m.reason_code is None, name
            assert isc(m.value, round(want, 4), 1e-12), name

    def test_equals_direct_pack_build(self):
        raw = make_raw()
        direct = build_financial_evidence(
            FinancialPeriodInput(period_end=PERIOD_END, source="TEST:SRC", fetched_at=FETCHED,
                                 unit="千元", basis="single_quarter",
                                 published_at=dt.date(2026, 11, 12), items=dict(BASE_ITEMS)),
            company_type="general")
        via, _ = _be(raw)
        assert via == direct

    def test_adapted_period_fields(self):
        a = adapt_financial_period(make_raw())
        assert isinstance(a, AdaptedPeriod) and isinstance(a.period, FinancialPeriodInput)
        assert a.company_type == "general" and a.currency == "TWD" and a.gaps == ()
        assert (a.period.period_end, a.period.source, a.period.fetched_at, a.period.unit,
                a.period.basis, a.period.published_at) == (
            PERIOD_END, "TEST:SRC", FETCHED, "千元", "single_quarter", dt.date(2026, 11, 12))
        assert tuple(a.period.items) == ITEM_NAMES
        for k, v in BASE_ITEMS.items():
            assert a.period.items[k] == v

    def test_observation_self_markers_equal_to_period_are_accepted(self):
        obs = [ob("revenue", 1000.0, period_end=PERIOD_END, unit="千元", currency="TWD")]
        assert adapt_financial_period(make_raw(obs)).period.items["revenue"] == 1000.0

    def test_int_values_accepted_as_float(self):
        a = adapt_financial_period(make_raw([ob("revenue", 1000)]))
        assert a.period.items["revenue"] == 1000.0 and isinstance(a.period.items["revenue"], float)

    def test_envelope_flows_to_evidence(self):
        e, _ = _be(make_raw())
        assert (e.period_end, e.source, e.fetched_at, e.unit, e.basis) == (
            PERIOD_END, "TEST:SRC", FETCHED, "千元", "single_quarter")
        assert e.pit_status == "published_at_declared"


# ── 規則 1：真 0 保留 ────────────────────────────────────────────────

class TestTrueZeroPreserved:
    @pytest.mark.parametrize("item", ITEM_NAMES)
    def test_reported_zero_kept_for_each_item(self, item):
        a = adapt_financial_period(make_raw(full_obs({item: 0.0})))
        assert a.period.items[item] == 0.0 and a.period.items[item] is not None
        assert item not in gaps_of(a)

    @pytest.mark.parametrize("item", ITEM_NAMES)
    def test_negative_zero_normalised(self, item):
        a = adapt_financial_period(make_raw([ob(item, -0.0)]))
        assert a.period.items[item] == 0.0
        assert math.copysign(1.0, a.period.items[item]) == 1.0

    def test_int_zero_kept(self):
        assert adapt_financial_period(make_raw([ob("cash", 0)])).period.items["cash"] == 0.0

    def test_zero_liabilities_flows_to_pack_as_zero_percent(self):
        e, gaps = _be(make_raw(full_obs({"total_liabilities": 0.0})))
        assert gaps == ()
        m = e.metrics["debt_ratio_pct"]
        assert m.status == "ok" and m.value == 0.0

    def test_not_all_zeros_become_none(self):
        obs = [ob(n, 0.0) for n in ITEM_NAMES]
        a = adapt_financial_period(make_raw(obs))
        assert all(v == 0.0 and v is not None for v in a.period.items.values())
        assert a.gaps == ()

    def test_negative_value_kept(self):
        a = adapt_financial_period(make_raw([ob("operating_income", -45_678.0)]))
        assert a.period.items["operating_income"] == -45_678.0


# ── 規則 2：缺值 → None + 具名缺口 ───────────────────────────────────

class TestMissingValues:
    def test_unobserved_item_is_not_observed_gap(self):
        a = adapt_financial_period(make_raw(full_obs(drop=("inventory",))))
        assert a.period.items["inventory"] is None
        assert gaps_of(a) == {"inventory": "not_observed"}

    def test_empty_observations_all_not_observed(self):
        a = adapt_financial_period(make_raw([]))
        assert all(v is None for v in a.period.items.values())
        assert tuple(g.item for g in a.gaps) == ITEM_NAMES
        assert {g.reason_code for g in a.gaps} == {"not_observed"}

    def test_source_absent(self):
        a = adapt_financial_period(make_raw([ob("capex", None, "source_absent")]))
        assert a.period.items["capex"] is None and gaps_of(a)["capex"] == "source_absent"

    def test_reported_without_value(self):
        a = adapt_financial_period(make_raw([ob("capex", None, "source_reported")]))
        assert a.period.items["capex"] is None
        assert gaps_of(a)["capex"] == "value_missing_for_reported"

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite(self, bad):
        a = adapt_financial_period(make_raw([ob("cash", bad)]))
        assert a.period.items["cash"] is None and gaps_of(a)["cash"] == "non_finite_value"

    def test_missing_is_not_zero_in_pack(self):
        e, gaps = _be(make_raw(full_obs(drop=("cash", "total_liabilities"))))
        assert e.items["cash"] is None and e.items["total_liabilities"] is None
        for n in ("cash_ratio_pct", "debt_ratio_pct"):
            m = e.metrics[n]
            assert m.status == "unknown" and m.value is None and m.reason_code == "missing_input"
        assert {g.item for g in gaps} == {"cash", "total_liabilities"}

    def test_missing_inventory_is_not_treated_as_zero_for_quick_ratio(self):
        e, _ = _be(make_raw(full_obs(drop=("inventory",))))
        q = e.metrics["quick_ratio"]
        assert q.status == "unknown" and q.reason_code == "missing_input"
        assert e.metrics["current_ratio"].status == "ok"

    def test_gap_per_item_at_most_one_and_detail_nonempty(self):
        obs = [ob("cash", float("nan")), ob("cash", float("inf")), ob("capex", None, "source_absent")]
        a = adapt_financial_period(make_raw(obs))
        assert [g.item for g in a.gaps].count("cash") == 1
        assert all(g.detail.strip() for g in a.gaps)


# ── 規則 3：legacy 假值 ──────────────────────────────────────────────

class TestLegacyFakeValues:
    def test_legacy_default_zero_is_not_true_zero(self):
        a = adapt_financial_period(make_raw([ob("total_liabilities", 0.0, "legacy_default")]))
        assert a.period.items["total_liabilities"] is None
        assert gaps_of(a)["total_liabilities"] == "legacy_default_zero"

    def test_legacy_default_with_none_value(self):
        a = adapt_financial_period(make_raw([ob("cash", None, "legacy_default")]))
        assert a.period.items["cash"] is None and gaps_of(a)["cash"] == "legacy_default_zero"

    def test_legacy_reset_is_not_zero_nor_restored(self):
        a = adapt_financial_period(make_raw([ob("operating_income", 0.0, "legacy_reset")]))
        assert a.period.items["operating_income"] is None
        assert gaps_of(a)["operating_income"] == "legacy_anomaly_reset"

    def test_legacy_default_through_pack_is_missing_not_zero_ratio(self):
        e, _ = _be(
            make_raw(full_obs() + [ob("total_liabilities", 0.0, "legacy_default")]))
        # 同科目有 reported 又有 legacy_default → 衝突，連真值也不採
        assert e.items["total_liabilities"] is None
        assert e.metrics["debt_ratio_pct"].reason_code == "missing_input"

    @pytest.mark.parametrize("ev", ["legacy_default", "legacy_reset"])
    @pytest.mark.parametrize("val", [5.0, -1.0, 1e-300, 7])
    def test_legacy_with_finite_nonzero_value_is_contradictory_and_raises(self, ev, val):
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", val, ev)]))

    @pytest.mark.parametrize("val", [0.0, 3.0, -2.5])
    def test_source_absent_with_finite_value_raises(self, val):
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", val, "source_absent")]))

    @pytest.mark.parametrize("ev,code", [("source_absent", "source_absent"),
                                         ("legacy_default", "legacy_default_zero"),
                                         ("legacy_reset", "legacy_anomaly_reset")])
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_with_marker_is_same_as_none_not_raise(self, ev, code, bad):
        with_bad = adapt_financial_period(make_raw(full_obs(drop=("cash",)) + [ob("cash", bad, ev)]))
        with_none = adapt_financial_period(make_raw(full_obs(drop=("cash",)) + [ob("cash", None, ev)]))
        assert with_bad.period.items["cash"] is None
        assert gaps_of(with_bad) == {"cash": code}
        assert with_bad.gaps == with_none.gaps
        assert dict(with_bad.period.items) == dict(with_none.period.items)

    def test_non_finite_with_marker_never_becomes_zero_in_pack(self):
        for ev in ("source_absent", "legacy_default", "legacy_reset"):
            e, gaps = _be(make_raw(full_obs(drop=("cash",)) + [ob("cash", float("nan"), ev)]))
            assert e.items["cash"] is None and e.metrics["cash_ratio_pct"].reason_code == "missing_input"
            assert [g.item for g in gaps] == ["cash"]

    def test_non_finite_marker_conflicting_with_reported_is_conflict(self):
        a = adapt_financial_period(make_raw(full_obs(drop=("cash",)) + [
            ob("cash", 5.0), ob("cash", float("nan"), "legacy_default")]))
        assert gaps_of(a) == {"cash": "conflicting_observations"}


# ── 規則 4：衝突 ─────────────────────────────────────────────────────

class TestConflicts:
    def test_different_reported_values_conflict(self):
        a = adapt_financial_period(make_raw([ob("revenue", 100.0), ob("revenue", 101.0)]))
        assert a.period.items["revenue"] is None
        assert gaps_of(a)["revenue"] == "conflicting_observations"

    def test_conflict_not_resolved_by_max_abs_mean_or_last(self):
        for vals in ([5.0, 9.0], [9.0, 5.0], [-9.0, 5.0], [5.0, -5.0], [0.0, 5.0]):
            a = adapt_financial_period(make_raw([ob("cash", v) for v in vals]))
            assert a.period.items["cash"] is None, vals
            assert gaps_of(a)["cash"] == "conflicting_observations"

    def test_tiny_difference_is_still_conflict(self):
        a = adapt_financial_period(make_raw([ob("cash", 100.0), ob("cash", 100.0 + 1e-9)]))
        assert a.period.items["cash"] is None

    @pytest.mark.parametrize("other", [("legacy_default", 0.0), ("legacy_reset", 0.0),
                                       ("source_absent", None)])
    def test_reported_vs_non_reported_conflict(self, other):
        ev, v = other
        for order in (0, 1):
            obs = [ob("cash", 50.0), ob("cash", v, ev)]
            if order:
                obs.reverse()
            a = adapt_financial_period(make_raw(obs))
            assert a.period.items["cash"] is None
            assert gaps_of(a)["cash"] == "conflicting_observations"

    def test_reported_zero_vs_legacy_default_zero_conflict(self):
        a = adapt_financial_period(make_raw([ob("cash", 0.0), ob("cash", 0.0, "legacy_default")]))
        assert a.period.items["cash"] is None
        assert gaps_of(a)["cash"] == "conflicting_observations"

    def test_identical_duplicates_merge(self):
        a = adapt_financial_period(make_raw([ob("cash", 50.0, label="A"), ob("cash", 50.0, label="B")]))
        assert a.period.items["cash"] == 50.0 and "cash" not in gaps_of(a)

    def test_identical_zero_duplicates_merge_to_zero(self):
        a = adapt_financial_period(make_raw([ob("cash", 0.0), ob("cash", -0.0)]))
        assert a.period.items["cash"] == 0.0 and "cash" not in gaps_of(a)

    def test_identical_absent_duplicates_merge_to_one_gap(self):
        a = adapt_financial_period(make_raw(full_obs(drop=("cash",)) + [
            ob("cash", None, "source_absent"), ob("cash", None, "source_absent")]))
        assert [(g.item, g.reason_code) for g in a.gaps] == [("cash", "source_absent")]

    def test_two_non_finite_merge_to_non_finite_gap(self):
        a = adapt_financial_period(make_raw([ob("cash", float("nan")), ob("cash", float("nan"))]))
        assert gaps_of(a)["cash"] == "non_finite_value"

    def test_conflict_is_order_independent(self):
        base = [ob("cash", 1.0), ob("cash", 2.0), ob("cash", 3.0)]
        for perm in (base, base[::-1], [base[1], base[0], base[2]]):
            a = adapt_financial_period(make_raw(full_obs(drop=("cash",)) + perm))
            assert gaps_of(a) == {"cash": "conflicting_observations"}

    def test_conflict_detail_lists_labels_without_choosing(self):
        a = adapt_financial_period(make_raw([ob("cash", 1.0, label="X1"), ob("cash", 2.0, label="X2")]))
        g = next(x for x in a.gaps if x.item == "cash")
        assert "X1" in g.detail and "X2" in g.detail

    def test_other_items_unaffected_by_conflict(self):
        a = adapt_financial_period(make_raw(full_obs() + [ob("cash", 1.0)]))
        assert a.period.items["revenue"] == BASE_ITEMS["revenue"]
        assert tuple(gaps_of(a)) == ("cash",)


# ── 規則 5：不推定（basis / published_at / company_type）────────────

class TestNoInference:
    def test_basis_none_passes_through_and_blocks_flow_metrics(self):
        a = adapt_financial_period(make_raw(basis=None))
        assert a.period.basis is None
        e, _ = _be(make_raw(basis=None))
        assert e.basis is None
        assert e.metrics["gross_margin_pct"].reason_code == "basis_unknown"
        assert e.metrics["debt_ratio_pct"].status == "ok"

    @pytest.mark.parametrize("b", ["single_quarter", "cumulative"])
    def test_basis_values_pass_through(self, b):
        assert adapt_financial_period(make_raw(basis=b)).period.basis == b

    def test_published_at_none_passes_through_and_pit_unknown(self):
        a = adapt_financial_period(make_raw(published_at=None))
        assert a.period.published_at is None
        e, _ = _be(make_raw(published_at=None))
        assert e.published_at is None and e.pit_status == "unknown_publication_date"

    def test_published_at_value_passes_through(self):
        d = dt.date(2026, 12, 31)
        a = adapt_financial_period(make_raw(published_at=d))
        assert a.period.published_at == d
        e, _ = _be(make_raw(published_at=d))
        assert e.pit_status == "published_at_declared"

    def test_published_at_same_day_as_period_end_allowed(self):
        assert adapt_financial_period(make_raw(published_at=PERIOD_END)).period.published_at == PERIOD_END

    def test_company_type_has_no_default(self):
        with pytest.raises(TypeError):
            RawFinancialPeriod(period_end=PERIOD_END, source="S", fetched_at=FETCHED, unit="u",
                               currency="TWD", basis=None, published_at=None, observations=[])

    def test_unknown_company_type_yields_unknown_not_general(self):
        e, _ = _be(make_raw(company_type="unknown"))
        assert e.company_type == "unknown"
        assert all(m.status == "unknown" and m.reason_code == "unknown_company_type"
                   for m in e.metrics.values())

    @pytest.mark.parametrize("ct", ["financial", "etf"])
    def test_financial_and_etf_flow_to_not_applicable(self, ct):
        e, gaps = _be(make_raw(company_type=ct))
        assert e.company_type == ct and gaps == ()
        assert all(m.status == "not_applicable" and m.value is None for m in e.metrics.values())

    @pytest.mark.parametrize("src,ct,expect", [
        ("TWSE:2881", "general", "ok"), ("TPEX:5880", "general", "ok"),
        ("TWSE:2330", "financial", "not_applicable"), ("TWSE:2881", "unknown", "unknown")])
    def test_company_type_not_inferred_from_code_prefix(self, src, ct, expect):
        e, _ = _be(make_raw(source=src, company_type=ct))
        assert e.company_type == ct
        assert {m.status for m in e.metrics.values()} == {expect}

    def test_period_end_fetched_at_not_used_to_derive_other_fields(self):
        a = adapt_financial_period(make_raw(published_at=None, basis=None,
                                            period_end=dt.date(2025, 12, 31)))
        assert a.period.published_at is None and a.period.basis is None


# ── 規則 6：原始異常 vs 重置異常 ─────────────────────────────────────

class TestEnvelopeVerbatimAndCaseSensitivity:
    @pytest.mark.parametrize("src", [" Test:Src ", "FinMind:TWSE_q", "\tabc\n", "ＡＢＣ"])
    @pytest.mark.parametrize("unit", [" 千元 ", "KTWD", "ktwd ", " 百萬元"])
    def test_source_and_unit_pass_through_exactly(self, src, unit):
        a = adapt_financial_period(make_raw(source=src, unit=unit))
        assert a.period.source == src and a.period.unit == unit
        e, _ = _be(make_raw(source=src, unit=unit))
        assert e.source == src and e.unit == unit

    def test_observation_marker_comparison_is_case_sensitive_on_purpose(self):
        # 刻意偏嚴：不做 casefold / strip 正規化。"twd" 與 "TWD" 可能是呼叫端的筆誤，
        # 也可能代表兩個不同來源慣例；本層無法判斷，寧可整份 raise 也不靜默視為相同。
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", 1.0, currency="twd")], currency="TWD"))
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", 1.0, currency="TWD")], currency="twd"))
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", 1.0, unit="ktwd")], unit="KTWD"))
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", 1.0, currency="TWD ")], currency="TWD"))

    def test_exact_match_still_accepted(self):
        a = adapt_financial_period(make_raw([ob("cash", 1.0, currency="TWD", unit="KTWD")],
                                            currency="TWD", unit="KTWD"))
        assert a.period.items["cash"] == 1.0


class TestAnomalyVersusReset:
    def _obs(self, oi_kind):
        base = full_obs(drop=("operating_income",))
        base = [o for o in base if o.item not in ("revenue", "net_income")]
        base += [ob("revenue", 1000.0), ob("net_income", 100.0)]
        if oi_kind == "reported":
            base.append(ob("operating_income", 2500.0))
        else:
            base.append(ob("operating_income", 0.0, "legacy_reset"))
        return base

    def test_reported_anomaly_passes_through_raw_and_pack_flags_unit_anomaly(self):
        e, gaps = _be(make_raw(self._obs("reported")))
        assert gaps == ()
        assert e.items["operating_income"] == 2500.0
        m = e.metrics["operating_margin_pct"]
        assert m.status == "unknown" and m.value is None and m.reason_code == "unit_anomaly"

    def test_reset_value_is_missing_input_not_unit_anomaly_not_zero(self):
        e, gaps = _be(make_raw(self._obs("reset")))
        assert e.items["operating_income"] is None
        assert [(g.item, g.reason_code) for g in gaps] == [("operating_income", "legacy_anomaly_reset")]
        m = e.metrics["operating_margin_pct"]
        assert m.status == "unknown" and m.value is None
        assert m.reason_code == "missing_input"
        assert m.reason_code != "unit_anomaly"
        assert m.value != 0.0

    def test_two_paths_give_different_reason_codes(self):
        r = build_evidence_from_raw(make_raw(self._obs("reported"))).evidence.metrics["operating_margin_pct"]
        s = build_evidence_from_raw(make_raw(self._obs("reset"))).evidence.metrics["operating_margin_pct"]
        assert r.reason_code != s.reason_code

    def test_reset_does_not_pollute_other_metrics(self):
        e, _ = _be(make_raw(self._obs("reset")))
        assert e.metrics["net_margin_pct"].status == "ok" and e.metrics["net_margin_pct"].value == 10.0


# ── gaps 決定性 ──────────────────────────────────────────────────────

class TestGapOrdering:
    def test_gaps_follow_item_names_order_regardless_of_input_order(self):
        obs = [ob("dividends", None, "source_absent"), ob("cash", float("nan")),
               ob("revenue", None, "source_reported"), ob("equity", 0.0, "legacy_default")]
        expected = [i for i in ITEM_NAMES if i in {"dividends", "cash", "revenue", "equity"}]
        gaps_rest = [i for i in ITEM_NAMES if i not in {"dividends", "cash", "revenue", "equity"}]
        for seed in range(6):
            shuffled = obs[:]
            random.Random(seed).shuffle(shuffled)
            a = adapt_financial_period(make_raw(shuffled))
            got = [g.item for g in a.gaps]
            assert [i for i in got if i in expected] == expected
            assert got == [i for i in ITEM_NAMES if i in got]
            assert set(got) == set(expected) | set(gaps_rest)

    def test_same_input_same_output(self):
        raw = make_raw(full_obs(drop=("cash",)) + [ob("capex", float("inf"))])
        a, b = adapt_financial_period(raw), adapt_financial_period(raw)
        assert a.gaps == b.gaps and dict(a.period.items) == dict(b.period.items)
        assert a.period.items is not b.period.items


# ── 所有 reason code 情境 ────────────────────────────────────────────

class TestEveryReasonCodeReachable:
    def test_all_seven_codes_produced(self):
        obs = [ob("revenue", None, "source_absent"), ob("cogs", 0.0, "legacy_default"),
               ob("gross_profit", 0.0, "legacy_reset"), ob("operating_income", float("nan")),
               ob("net_income", 1.0), ob("net_income", 2.0), ob("total_assets", None)]
        a = adapt_financial_period(make_raw(obs))
        codes = set(gaps_of(a).values())
        assert codes == set(GAP_REASON_CODES)

    def test_gap_validates_its_own_fields(self):
        with pytest.raises(FinancialPeriodAdapterError):
            AdapterGap(item="nope", reason_code="not_observed", detail="x")
        with pytest.raises(FinancialPeriodAdapterError):
            AdapterGap(item="cash", reason_code="whatever", detail="x")


# ── 驗證 raise 全集 ──────────────────────────────────────────────────

def _bad_raws() -> list[tuple[str, object]]:
    r = make_raw()
    o = ob("cash", 1.0)

    def with_obs(*obs):
        return dataclasses.replace(r, observations=list(obs))

    def rep(**kw):
        return dataclasses.replace(r, **kw)
    cases: list[tuple[str, object]] = [
        ("raw_is_dict", {"period_end": PERIOD_END}), ("raw_is_none", None),
        ("period_end_datetime", rep(period_end=dt.datetime(2026, 9, 30))),
        ("period_end_str", rep(period_end="2026-09-30")), ("period_end_none", rep(period_end=None)),
        ("source_empty", rep(source="")), ("source_blank", rep(source="   ")),
        ("source_none", rep(source=None)), ("unit_empty", rep(unit="")),
        ("unit_none", rep(unit=None)), ("currency_empty", rep(currency="")),
        ("currency_none", rep(currency=None)),
        ("fetched_naive", rep(fetched_at=dt.datetime(2026, 11, 1))),
        ("fetched_date", rep(fetched_at=dt.date(2026, 11, 1))),
        ("fetched_str", rep(fetched_at="2026-11-01")), ("fetched_none", rep(fetched_at=None)),
        ("company_type_upper", rep(company_type="GENERAL")),
        ("company_type_none", rep(company_type=None)), ("company_type_bank", rep(company_type="bank")),
        ("basis_bad", rep(basis="q")), ("basis_upper", rep(basis="SINGLE_QUARTER")),
        ("published_datetime", rep(published_at=dt.datetime(2026, 11, 12))),
        ("published_str", rep(published_at="2026-11-12")),
        ("published_before_period_end", rep(published_at=dt.date(2026, 9, 29))),
        ("observations_str", rep(observations="abc")), ("observations_dict", rep(observations={})),
        ("observations_none", rep(observations=None)), ("observations_set", rep(observations={o})),
        ("observations_generator", rep(observations=(x for x in [o]))),
        ("observation_not_raw_obs", with_obs({"item": "cash", "value": 1.0})),
        ("item_unknown", with_obs(ob("foo", 1.0))), ("item_none", with_obs(ob(None, 1.0))),
        ("evidence_bad", with_obs(ob("cash", 1.0, "reported"))),
        ("evidence_none", with_obs(ob("cash", 1.0, None))),
        ("label_empty", with_obs(RawObservation("cash", 1.0, "source_reported", ""))),
        ("label_none", with_obs(RawObservation("cash", 1.0, "source_reported", None))),
        ("value_bool_true", with_obs(ob("cash", True))), ("value_bool_false", with_obs(ob("cash", False))),
        ("value_decimal", with_obs(ob("cash", Decimal("1.5")))), ("value_str", with_obs(ob("cash", "1"))),
        ("value_list", with_obs(ob("cash", [1]))), ("value_huge_int", with_obs(ob("cash", 10 ** 400))),
        ("value_complex", with_obs(ob("cash", 1 + 2j))),
        ("value_huge_int_legacy", with_obs(ob("cash", 10 ** 400, "legacy_default"))),
        ("obs_period_end_mismatch", with_obs(ob("cash", 1.0, period_end=dt.date(2026, 6, 30)))),
        ("obs_period_end_datetime", with_obs(ob("cash", 1.0, period_end=dt.datetime(2026, 9, 30)))),
        ("obs_unit_mismatch", with_obs(ob("cash", 1.0, unit="元"))),
        ("obs_unit_not_str", with_obs(ob("cash", 1.0, unit=5))),
        ("obs_currency_mismatch", with_obs(ob("cash", 1.0, currency="USD"))),
        ("obs_currency_not_str", with_obs(ob("cash", 1.0, currency=5))),
        ("mixed_unit_among_good_obs", with_obs(ob("revenue", 1.0), ob("cash", 1.0, unit="百萬元"))),
    ]
    return cases


class TestValidationRaises:
    @pytest.mark.parametrize("case", _bad_raws(), ids=[c[0] for c in _bad_raws()])
    def test_bad_input_raises_adapter_error(self, case):
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(case[1])
        with pytest.raises(FinancialPeriodAdapterError):
            build_evidence_from_raw(case[1])

    def test_error_is_value_error(self):
        assert issubclass(FinancialPeriodAdapterError, ValueError)

    def test_error_message_names_the_field(self):
        with pytest.raises(FinancialPeriodAdapterError, match="company_type"):
            adapt_financial_period(make_raw(company_type="bank"))
        with pytest.raises(FinancialPeriodAdapterError, match="unit"):
            adapt_financial_period(make_raw([ob("cash", 1.0, unit="元")]))

    def test_all_evidence_kinds_accepted(self):
        for k in EVIDENCE_KINDS:
            adapt_financial_period(make_raw([ob("cash", None, k)]))

    @pytest.mark.parametrize("make", ["float64", "float32", "int64", "int32"])
    def test_numpy_numeric_scalars_accepted_and_converted_to_float(self, make):
        np = pytest.importorskip("numpy")
        a = adapt_financial_period(make_raw([ob("cash", getattr(np, make)(3))]))
        assert a.period.items["cash"] == 3.0 and type(a.period.items["cash"]) is float

    def test_numpy_non_finite_scalars_become_gap(self):
        np = pytest.importorskip("numpy")
        a = adapt_financial_period(make_raw([ob("cash", np.float32("nan")), ob("capex", np.float64("inf"))]))
        assert gaps_of(a)["cash"] == gaps_of(a)["capex"] == "non_finite_value"

    def test_numpy_bool_rejected(self):
        np = pytest.importorskip("numpy")
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", np.bool_(True))]))

    def test_numeric_acceptance_matches_pack(self):
        """與 pack 的 _normalize_items 型別行為一致：同一個值，兩邊同進同出。"""
        from fractions import Fraction
        np = pytest.importorskip("numpy")
        samples = [1, 1.5, True, False, Decimal("1"), "1", 1 + 2j, Fraction(1, 2), [1], b"1",
                   np.int64(1), np.int32(1), np.float32(1.5), np.float64(1), np.bool_(True)]
        for v in samples:
            adapter_ok = pack_ok = True
            try:
                adapt_financial_period(make_raw([ob("cash", v)]))
            except FinancialPeriodAdapterError:
                adapter_ok = False
            try:
                build_financial_evidence(
                    FinancialPeriodInput(period_end=PERIOD_END, source="S", fetched_at=FETCHED,
                                         unit="u", basis=None, published_at=None,
                                         items={"cash": v}), company_type="general")
            except FinancialEvidenceInputError:
                pack_ok = False
            assert adapter_ok == pack_ok, (type(v).__name__, adapter_ok, pack_ok)

    def test_bad_item_raises_even_when_other_obs_fine(self):
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw(full_obs() + [ob("not_an_item", 1.0)]))


# ── 不可變 / 不改輸入 / 純度行為 ─────────────────────────────────────

class TestImmutabilityAndPurityOfBehavior:
    def test_input_not_mutated(self):
        obs = full_obs() + [ob("cash", 1.0), ob("capex", float("nan"))]
        raw = make_raw(obs)
        snapshot = copy.deepcopy(obs)
        before = (len(raw.observations), raw.period_end, raw.basis)
        adapt_financial_period(raw)
        build_evidence_from_raw(raw)
        assert len(raw.observations) == before[0]
        assert (raw.period_end, raw.basis) == before[1:]
        assert len(obs) == len(snapshot)
        for x, y in zip(obs, snapshot):
            assert x.item == y.item and x.evidence == y.evidence
            assert (x.value == y.value) or (x.value != x.value and y.value != y.value)

    def test_outputs_frozen(self):
        a = adapt_financial_period(make_raw(full_obs(drop=("cash",))))
        for obj, field in ((a, "currency"), (a.period, "unit"), (a.gaps[0], "reason_code")):
            with pytest.raises(dataclasses.FrozenInstanceError):
                setattr(obj, field, "x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(make_raw(), "unit", "x")
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(ob("cash"), "value", 1.0)

    def test_items_read_only(self):
        a = adapt_financial_period(make_raw())
        with pytest.raises(TypeError):
            a.period.items["revenue"] = 1.0           # type: ignore[index]
        with pytest.raises(TypeError):
            del a.period.items["revenue"]             # type: ignore[attr-defined]

    def test_gaps_is_tuple(self):
        assert isinstance(adapt_financial_period(make_raw([])).gaps, tuple)

    def test_items_always_full_schema_in_order(self):
        a = adapt_financial_period(make_raw([ob("revenue", 1.0)]))
        assert tuple(a.period.items) == ITEM_NAMES

    def test_items_not_aliased_to_observations(self):
        obs = [ob("revenue", 5.0)]
        a = adapt_financial_period(make_raw(obs))
        assert a.period.items["revenue"] == 5.0
        assert not any(v is obs for v in a.period.items.values())

    def test_returns_evidence_object_untouched(self):
        e, gaps = _be(make_raw())
        assert isinstance(e, FinancialEvidence) and isinstance(gaps, tuple)


class TestAdaptedEvidencePairing:
    def test_result_is_frozen_triple(self):
        res = build_evidence_from_raw(make_raw(full_obs(drop=("cash",)), currency="USD"))
        assert isinstance(res, AdaptedEvidence)
        assert [f.name for f in dataclasses.fields(AdaptedEvidence)] == ["evidence", "gaps", "currency"]
        for fld in ("evidence", "gaps", "currency"):
            with pytest.raises(dataclasses.FrozenInstanceError):
                setattr(res, fld, None)

    @pytest.mark.parametrize("cur", ["TWD", "USD", "twd", " JPY "])
    def test_currency_preserved_verbatim_and_pairs_with_adapt(self, cur):
        raw = make_raw(currency=cur)
        res = build_evidence_from_raw(raw)
        assert res.currency == cur == adapt_financial_period(raw).currency

    def test_evidence_itself_carries_no_currency(self):
        res = build_evidence_from_raw(make_raw(currency="USD"))
        assert not hasattr(res.evidence, "currency")
        assert "USD" not in {str(getattr(res.evidence, f.name)) for f in dataclasses.fields(res.evidence)
                             if f.name not in ("items", "metrics")}

    def test_gaps_explain_none_that_pack_alone_cannot(self):
        raw = make_raw(full_obs(drop=("cash", "capex")) + [ob("capex", 0.0, "legacy_default")])
        res = build_evidence_from_raw(raw)
        assert res.evidence.metrics["cash_ratio_pct"].reason_code == "missing_input"
        assert res.evidence.items["capex"] is None
        assert {g.item: g.reason_code for g in res.gaps} == {
            "cash": "not_observed", "capex": "legacy_default_zero"}

    def test_evidence_equals_pack_built_from_adapted_period(self):
        raw = make_raw(full_obs(drop=("cash",)))
        a = adapt_financial_period(raw)
        res = build_evidence_from_raw(raw)
        assert res.evidence == build_financial_evidence(a.period, company_type=a.company_type)
        assert res.gaps == a.gaps

    def test_tuple_observations_accepted(self):
        a = adapt_financial_period(make_raw(tuple(full_obs())))
        assert a.gaps == ()


# ── 禁字 / emoji 掃描 ────────────────────────────────────────────────

_BANNED_WORDS = ("買進", "賣出", "加碼", "減碼", "目標價", "停損", "信心", "機率", "看多", "看空",
                 "評級", "燈號", "分數", "grade", "radar", "headline", "verified", "建議", "score")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
_PATH = pathlib.Path(fpa.__file__)
_SRC = _PATH.read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


def _all_gap_strings() -> list[str]:
    out: list[str] = []
    for code in GAP_REASON_CODES:
        out.append(code)
    obs = [ob("revenue", None, "source_absent"), ob("cogs", 0.0, "legacy_default"),
           ob("gross_profit", 0.0, "legacy_reset"), ob("operating_income", float("nan")),
           ob("net_income", 1.0), ob("net_income", 2.0), ob("total_assets", None)]
    a = adapt_financial_period(make_raw(obs))
    for g in a.gaps:
        out += [g.item, g.reason_code, g.detail]
    out += [g.detail for g in adapt_financial_period(make_raw([])).gaps]
    return out


class TestWording:
    def test_gap_strings_clean(self):
        strings = _all_gap_strings()
        assert len(strings) > 15
        for s in strings:
            low = s.lower()
            for w in _BANNED_WORDS:
                assert w not in low, (w, s)
            assert not _EMOJI.search(s), s

    def test_source_text_clean(self):
        low = _SRC.lower()
        for w in _BANNED_WORDS:
            assert w not in low, w
        assert not _EMOJI.search(_SRC)

    def test_no_forbidden_field_names(self):
        names = set()
        for cls in (RawObservation, RawFinancialPeriod, AdapterGap, AdaptedPeriod):
            names |= {f.name for f in dataclasses.fields(cls)}
        for n in names | set(GAP_REASON_CODES) | set(EVIDENCE_KINDS):
            tokens = set(n.lower().split("_"))
            for w in ("grade", "score", "radar", "rating", "signal", "light", "headline"):
                assert w not in tokens, n

    def test_docstring_covers_required_topics(self):
        doc = fpa.__doc__ or ""
        for needle in ("_v()", "legacy_default", "legacy_reset", "_first_hit", "source_reported",
                       "不判斷", "不處理幣別", "換算", "PIT", "零 production caller", "28", "58",
                       "AdaptedEvidence", "成對", "numbers.Real", "不得丟失", "source_label",
                       "原樣回顯", "大小寫"):
            assert needle in doc, needle

    def test_reason_code_set_is_exactly_seven(self):
        assert GAP_REASON_CODES == ("not_observed", "source_absent", "legacy_default_zero",
                                    "legacy_anomaly_reset", "non_finite_value",
                                    "conflicting_observations", "value_missing_for_reported")


# ── 模組純度（AST）───────────────────────────────────────────────────

_BANNED_IMPORT_PREFIXES = ("streamlit", "requests", "yfinance", "FinMind", "time", "src.data",
                           "src.ui", "src.ui2", "src.services", "app", "shared", "proxy_helper",
                           "google", "gemini", "openai", "pandas", "numpy", "os", "sys", "socket",
                           "subprocess", "pathlib", "random", "urllib", "http",
                           "src.services.financial_health_engine", "financial_health_engine")
_CLOCK_ATTRS = {"now", "today", "utcnow", "utcfromtimestamp", "fromtimestamp",
                "monotonic", "perf_counter", "time", "sleep"}


def _imported_modules() -> list[str]:
    mods: list[str] = []
    for node in ast.walk(_TREE):
        if isinstance(node, ast.Import):
            mods += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods.append(node.module or "")
    return mods


class TestModulePurity:
    def test_no_banned_imports(self):
        for m in _imported_modules():
            for p in _BANNED_IMPORT_PREFIXES:
                assert not (m == p or m.startswith(p + ".")), f"禁止 import {m}"

    def test_only_stdlib_and_pack_imports(self):
        assert set(_imported_modules()) <= {
            "__future__", "datetime", "math", "numbers", "dataclasses", "types", "typing",
            "collections.abc",
            "src.compute.health.financial_health_evidence"}

    def test_pack_is_the_only_src_import(self):
        srcs = {m for m in _imported_modules() if m.startswith("src")}
        assert srcs == {"src.compute.health.financial_health_evidence"}

    def test_no_clock_calls(self):
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                assert n.func.attr not in _CLOCK_ATTRS, n.func.attr
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                assert n.func.id not in _CLOCK_ATTRS

    def test_no_io_calls(self):
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                assert n.func.id not in {"open", "print", "input", "exec", "eval", "__import__"}

    def test_no_float_literal_equality(self):
        for n in ast.walk(_TREE):
            if isinstance(n, ast.Compare):
                for op, comp in zip(n.ops, n.comparators):
                    if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant):
                        assert not isinstance(comp.value, float), ast.dump(n)

    def test_no_streamlit_decorators_or_global_state(self):
        assert not any(isinstance(n, ast.Global) for n in ast.walk(_TREE))
        assert "st.cache" not in _SRC and "session_state" not in _SRC


# ── 突變防守 ─────────────────────────────────────────────────────────

def _expect_raises(fn) -> None:
    try:
        fn()
    except FinancialPeriodAdapterError:
        return
    raise AssertionError("應 raise FinancialPeriodAdapterError 卻沒有")


def _assert_true_zero_kept() -> None:
    a = adapt_financial_period(make_raw([ob("total_liabilities", 0.0), ob("cash", 0.0)]))
    assert a.period.items["total_liabilities"] == 0.0 and a.period.items["total_liabilities"] is not None
    assert a.period.items["cash"] is not None and a.gaps and "cash" not in gaps_of(a)
    e, _ = _be(make_raw(full_obs({"total_liabilities": 0.0})))
    assert e.metrics["debt_ratio_pct"].status == "ok" and e.metrics["debt_ratio_pct"].value == 0.0


def _assert_legacy_default_not_zero() -> None:
    a = adapt_financial_period(make_raw([ob("total_liabilities", 0.0, "legacy_default")]))
    assert a.period.items["total_liabilities"] is None
    assert gaps_of(a)["total_liabilities"] == "legacy_default_zero"


def _assert_legacy_reset_not_zero() -> None:
    a = adapt_financial_period(make_raw([ob("operating_income", 0.0, "legacy_reset")]))
    assert a.period.items["operating_income"] is None
    assert gaps_of(a)["operating_income"] == "legacy_anomaly_reset"


def _assert_non_finite_not_zero() -> None:
    a = adapt_financial_period(make_raw([ob("cash", float("nan")), ob("capex", float("inf"))]))
    assert a.period.items["cash"] is None and a.period.items["capex"] is None
    assert gaps_of(a) == {**{i: "not_observed" for i in ITEM_NAMES if i not in ("cash", "capex")},
                          "cash": "non_finite_value", "capex": "non_finite_value"}


def _assert_conflict_not_resolved() -> None:
    a = adapt_financial_period(make_raw([ob("cash", 5.0), ob("cash", 9.0)]))
    assert a.period.items["cash"] is None and gaps_of(a)["cash"] == "conflicting_observations"
    b = adapt_financial_period(make_raw([ob("cash", 5.0), ob("cash", 0.0, "legacy_default")]))
    assert b.period.items["cash"] is None and gaps_of(b)["cash"] == "conflicting_observations"
    c = adapt_financial_period(make_raw([ob("cash", 5.0), ob("cash", None, "source_absent")]))
    assert c.period.items["cash"] is None and gaps_of(c)["cash"] == "conflicting_observations"


def _assert_no_inference() -> None:
    a = adapt_financial_period(make_raw(published_at=None, basis=None))
    assert a.period.published_at is None and a.period.basis is None
    e, _ = _be(make_raw(published_at=None, basis=None))
    assert e.pit_status == "unknown_publication_date" and e.basis is None


def _assert_unit_consistency_enforced() -> None:
    _expect_raises(lambda: adapt_financial_period(make_raw([ob("cash", 1.0, unit="元")])))
    _expect_raises(lambda: adapt_financial_period(make_raw([ob("cash", 1.0, currency="USD")])))
    _expect_raises(lambda: adapt_financial_period(
        make_raw([ob("cash", 1.0, period_end=dt.date(2026, 6, 30))])))


def _assert_company_type_explicit() -> None:
    e, _ = _be(make_raw(company_type="unknown"))
    assert all(m.status == "unknown" for m in e.metrics.values())
    f, _ = _be(make_raw(company_type="financial"))
    assert all(m.status == "not_applicable" for m in f.metrics.values())


def _assert_no_prefix_inference() -> None:
    for src in ("TWSE:2881", "TPEX:5880", "2801.TW"):
        e, _ = _be(make_raw(source=src, company_type="general"))
        assert e.company_type == "general"
        assert all(m.status == "ok" for m in e.metrics.values())


def _assert_bool_rejected() -> None:
    _expect_raises(lambda: adapt_financial_period(make_raw([ob("cash", True)])))


def _assert_reported_none_not_zero() -> None:
    a = adapt_financial_period(make_raw([ob("cash", None, "source_reported")]))
    assert a.period.items["cash"] is None and gaps_of(a)["cash"] == "value_missing_for_reported"


def _assert_envelope_verbatim() -> None:
    a = adapt_financial_period(make_raw(source=" FinMind:TWSE_q ", unit=" KTWD "))
    assert a.period.source == " FinMind:TWSE_q " and a.period.unit == " KTWD "


def _assert_case_sensitive_markers() -> None:
    _expect_raises(lambda: adapt_financial_period(
        make_raw([ob("cash", 1.0, currency="twd")], currency="TWD")))
    _expect_raises(lambda: adapt_financial_period(
        make_raw([ob("cash", 1.0, unit="ktwd")], unit="KTWD")))
    _expect_raises(lambda: adapt_financial_period(
        make_raw([ob("cash", 1.0, currency="TWD ")], currency="TWD")))


def _assert_marker_non_finite_same_as_none() -> None:
    for ev, code in (("source_absent", "source_absent"), ("legacy_default", "legacy_default_zero"),
                     ("legacy_reset", "legacy_anomaly_reset")):
        for bad in (float("nan"), float("inf"), float("-inf")):
            a = adapt_financial_period(make_raw(full_obs(drop=("cash",)) + [ob("cash", bad, ev)]))
            assert a.period.items["cash"] is None and gaps_of(a) == {"cash": code}


def _assert_finite_nonzero_marker_raises() -> None:
    _expect_raises(lambda: adapt_financial_period(make_raw([ob("cash", 5.0, "legacy_default")])))
    _expect_raises(lambda: adapt_financial_period(make_raw([ob("cash", -5.0, "legacy_reset")])))
    _expect_raises(lambda: adapt_financial_period(make_raw([ob("cash", 5.0, "source_absent")])))


def _assert_numeric_types_match_pack() -> None:
    np = pytest.importorskip("numpy")
    for v in (np.int64(2), np.int32(2), np.float32(2.0), np.float64(2.0), 2):
        assert adapt_financial_period(make_raw([ob("cash", v)])).period.items["cash"] == 2.0
    for v in (np.bool_(True), Decimal("2"), "2", 2 + 0j, True):
        _expect_raises(lambda v=v: adapt_financial_period(make_raw([ob("cash", v)])))


def _assert_currency_paired() -> None:
    res = build_evidence_from_raw(make_raw(currency="USD"))
    assert isinstance(res, AdaptedEvidence) and res.currency == "USD"


class TestMutationGuards:
    """拔掉防線 → 對應斷言輔助函式必須失敗。"""

    _RED = (AssertionError, FinancialPeriodAdapterError, ZeroDivisionError, KeyError, TypeError)

    def test_baseline_unmutated_passes(self):
        for f in (_assert_true_zero_kept, _assert_legacy_default_not_zero,
                  _assert_legacy_reset_not_zero, _assert_non_finite_not_zero,
                  _assert_conflict_not_resolved, _assert_no_inference,
                  _assert_unit_consistency_enforced, _assert_company_type_explicit,
                  _assert_no_prefix_inference, _assert_bool_rejected,
                  _assert_reported_none_not_zero):
            f()

    def test_legacy_default_treated_as_true_zero_goes_red(self, monkeypatch):
        orig = fpa._outcome
        monkeypatch.setattr(
            fpa, "_outcome",
            lambda o: (None, 0.0) if o.evidence == "legacy_default" else orig(o))
        with pytest.raises(self._RED):
            _assert_legacy_default_not_zero()

    def test_legacy_reset_treated_as_zero_goes_red(self, monkeypatch):
        orig = fpa._outcome
        monkeypatch.setattr(
            fpa, "_outcome",
            lambda o: (None, 0.0) if o.evidence == "legacy_reset" else orig(o))
        with pytest.raises(self._RED):
            _assert_legacy_reset_not_zero()

    def test_all_zeros_turned_into_none_goes_red(self, monkeypatch):
        orig = fpa._outcome

        def mutant(o):
            reason, val = orig(o)
            if reason is None and val is not None and abs(val) < 1e-12:
                return "not_observed", None
            return reason, val
        monkeypatch.setattr(fpa, "_outcome", mutant)
        with pytest.raises(self._RED):
            _assert_true_zero_kept()

    def test_conflict_resolved_by_max_goes_red(self, monkeypatch):
        monkeypatch.setattr(
            fpa, "_merge_outcomes",
            lambda outs: max(outs, key=lambda x: (x[1] is not None, x[1] if x[1] is not None else 0.0)))
        with pytest.raises(self._RED):
            _assert_conflict_not_resolved()

    def test_conflict_resolved_by_last_wins_goes_red(self, monkeypatch):
        monkeypatch.setattr(fpa, "_merge_outcomes", lambda outs: outs[-1])
        with pytest.raises(self._RED):
            _assert_conflict_not_resolved()

    def test_published_at_inferred_goes_red(self, monkeypatch):
        orig = fpa._to_period_input

        def mutant(raw, items):
            p = orig(raw, items)
            if p.published_at is None:
                return dataclasses.replace(p, published_at=raw.period_end + dt.timedelta(days=45))
            return p
        monkeypatch.setattr(fpa, "_to_period_input", mutant)
        with pytest.raises(self._RED):
            _assert_no_inference()

    def test_basis_inferred_goes_red(self, monkeypatch):
        orig = fpa._to_period_input

        def mutant(raw, items):
            p = orig(raw, items)
            return dataclasses.replace(p, basis=p.basis or "single_quarter")
        monkeypatch.setattr(fpa, "_to_period_input", mutant)
        with pytest.raises(self._RED):
            _assert_no_inference()

    def test_unit_consistency_check_skipped_goes_red(self, monkeypatch):
        monkeypatch.setattr(fpa, "_check_observation_consistency", lambda raw, obs: None)
        with pytest.raises(self._RED):
            _assert_unit_consistency_enforced()

    def test_company_type_defaulted_to_general_goes_red(self, monkeypatch):
        orig = fpa.build_financial_evidence
        monkeypatch.setattr(fpa, "build_financial_evidence",
                            lambda period, *, company_type: orig(period, company_type="general"))
        with pytest.raises(self._RED):
            _assert_company_type_explicit()

    def test_company_type_inferred_from_code_prefix_goes_red(self, monkeypatch):
        orig = fpa.adapt_financial_period

        def mutant(raw):
            res = orig(raw)
            if re.search(r"(28|58)\d\d", raw.source):
                return dataclasses.replace(res, company_type="financial")
            return res
        monkeypatch.setattr(fpa, "adapt_financial_period", mutant)
        with pytest.raises(self._RED):
            _assert_no_prefix_inference()

    def test_non_finite_coerced_to_zero_goes_red(self, monkeypatch):
        orig = fpa._outcome

        def mutant(o):
            reason, val = orig(o)
            return (None, 0.0) if reason == "non_finite_value" else (reason, val)
        monkeypatch.setattr(fpa, "_outcome", mutant)
        with pytest.raises(self._RED):
            _assert_non_finite_not_zero()

    def test_reported_without_value_coerced_to_zero_goes_red(self, monkeypatch):
        orig = fpa._outcome

        def mutant(o):
            reason, val = orig(o)
            return (None, 0.0) if reason == "value_missing_for_reported" else (reason, val)
        monkeypatch.setattr(fpa, "_outcome", mutant)
        with pytest.raises(self._RED):
            _assert_reported_none_not_zero()

    def test_baseline_new_guards_pass(self):
        for f in (_assert_envelope_verbatim, _assert_case_sensitive_markers,
                  _assert_marker_non_finite_same_as_none, _assert_finite_nonzero_marker_raises,
                  _assert_numeric_types_match_pack, _assert_currency_paired):
            f()

    def test_source_unit_stripped_goes_red(self, monkeypatch):
        orig = fpa._to_period_input

        def mutant(raw, items):
            return dataclasses.replace(orig(raw, items), source=raw.source.strip(), unit=raw.unit.strip())
        monkeypatch.setattr(fpa, "_to_period_input", mutant)
        with pytest.raises(self._RED):
            _assert_envelope_verbatim()

    def test_source_unit_lowercased_goes_red(self, monkeypatch):
        orig = fpa._to_period_input

        def mutant(raw, items):
            return dataclasses.replace(orig(raw, items), source=raw.source.lower(), unit=raw.unit.lower())
        monkeypatch.setattr(fpa, "_to_period_input", mutant)
        with pytest.raises(self._RED):
            _assert_envelope_verbatim()

    def test_marker_comparison_casefolded_goes_red(self, monkeypatch):
        orig = fpa._check_observation_consistency

        def fold(x):
            return x.strip().casefold() if isinstance(x, str) else x

        def mutant(raw, obs):
            raw2 = dataclasses.replace(raw, unit=fold(raw.unit), currency=fold(raw.currency))
            obs2 = dataclasses.replace(obs, unit=fold(obs.unit), currency=fold(obs.currency))
            return orig(raw2, obs2)
        monkeypatch.setattr(fpa, "_check_observation_consistency", mutant)
        with pytest.raises(self._RED):
            _assert_case_sensitive_markers()

    def test_marker_non_finite_raises_again_goes_red(self, monkeypatch):
        orig = fpa._validate_value

        def mutant(obs):
            if (obs.evidence != "source_reported" and obs.value is not None
                    and not math.isfinite(float(obs.value))):
                raise FinancialPeriodAdapterError("mutant")
            return orig(obs)
        monkeypatch.setattr(fpa, "_validate_value", mutant)
        with pytest.raises(self._RED):
            _assert_marker_non_finite_same_as_none()

    def test_marker_non_finite_treated_as_zero_goes_red(self, monkeypatch):
        orig = fpa._outcome

        def mutant(o):
            if (o.evidence != "source_reported" and o.value is not None
                    and not math.isfinite(float(o.value))):
                return None, 0.0
            return orig(o)
        monkeypatch.setattr(fpa, "_outcome", mutant)
        with pytest.raises(self._RED):
            _assert_marker_non_finite_same_as_none()

    def test_finite_nonzero_marker_check_removed_goes_red(self, monkeypatch):
        orig = fpa._validate_value

        def mutant(obs):
            if obs.evidence != "source_reported":
                return None
            return orig(obs)
        monkeypatch.setattr(fpa, "_validate_value", mutant)
        with pytest.raises(self._RED):
            _assert_finite_nonzero_marker_raises()

    def test_numeric_check_narrowed_to_builtin_goes_red(self, monkeypatch):
        orig = fpa._validate_value

        def mutant(obs):
            if obs.value is not None and type(obs.value) not in (int, float):
                raise FinancialPeriodAdapterError("mutant")
            return orig(obs)
        monkeypatch.setattr(fpa, "_validate_value", mutant)
        with pytest.raises(self._RED):
            _assert_numeric_types_match_pack()

    def test_currency_dropped_goes_red(self, monkeypatch):
        orig = fpa.adapt_financial_period
        monkeypatch.setattr(fpa, "adapt_financial_period",
                            lambda raw: dataclasses.replace(orig(raw), currency="TWD"))
        with pytest.raises(self._RED):
            _assert_currency_paired()

    def test_bool_validation_removed_goes_red(self, monkeypatch):
        monkeypatch.setattr(fpa, "_validate_value", lambda obs: None)
        with pytest.raises(self._RED):
            _assert_bool_rejected()
