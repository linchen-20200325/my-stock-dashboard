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
import numbers
import re
import sys
from decimal import Decimal
from fractions import Fraction

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


# ── 病態自訂 numbers.Real / Rational（只用來驗證「一律收斂成適配層例外」）──────

class _ZeroDenominatorRational:
    """denominator == 0 的 Rational：Fraction(1, 0) 會丟 ZeroDivisionError。"""
    numerator = 1
    denominator = 0

    def __float__(self):
        return 1.0


class _ZeroDivRatioReal:
    """as_integer_ratio() 回傳 (1, 0)：Fraction(1, 0) 丟 ZeroDivisionError。"""
    def __float__(self):
        return 1.0

    def as_integer_ratio(self):
        return (1, 0)


class _StrRatioReal:
    """as_integer_ratio() 回傳非數：int('a') 丟 ValueError。"""
    def __float__(self):
        return 1.0

    def as_integer_ratio(self):
        return ("a", "b")


class _FloatRuntimeErrorReal:
    """__float__ 丟 RuntimeError。"""
    def __float__(self):
        raise RuntimeError("boom 12345")

    def as_integer_ratio(self):
        return (1, 2)


class _FloatInterruptReal:
    """__float__ 丟 KeyboardInterrupt（BaseException，不得被吞掉）。"""
    def __float__(self):
        raise KeyboardInterrupt

    def as_integer_ratio(self):
        return (1, 2)


class _RatioInterruptReal:
    """as_integer_ratio() 丟 KeyboardInterrupt（走 _exact 路徑；BaseException 不得被吞掉）。"""
    def __float__(self):
        return 1.0

    def as_integer_ratio(self):
        raise KeyboardInterrupt


numbers.Real.register(_RatioInterruptReal)
numbers.Rational.register(_ZeroDenominatorRational)
for _cls in (_ZeroDivRatioReal, _StrRatioReal, _FloatRuntimeErrorReal, _FloatInterruptReal):
    numbers.Real.register(_cls)
_PATHOLOGICAL = (_ZeroDenominatorRational, _ZeroDivRatioReal, _StrRatioReal, _FloatRuntimeErrorReal)


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

    @pytest.mark.parametrize("val", [0.0, -0.0, 3.0, -2.5, 0])
    def test_source_absent_with_finite_value_raises(self, val):
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", val, "source_absent")]))

    def test_source_absent_with_numpy_zero_raises(self):
        np = pytest.importorskip("numpy")
        for v in (np.int64(0), np.float32(0.0), np.float64(-0.0)):
            with pytest.raises(FinancialPeriodAdapterError):
                adapt_financial_period(make_raw([ob("cash", v, "source_absent")]))

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

    @pytest.mark.parametrize("obs_unit,period_unit", [("KTWD ", "KTWD"), (" KTWD", "KTWD"),
                                                     ("KTWD", "KTWD "), ("KTWD", " KTWD")])
    def test_observation_unit_whitespace_sensitive(self, obs_unit, period_unit):
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", 1.0, unit=obs_unit)], unit=period_unit))

    def test_exact_match_still_accepted(self):
        a = adapt_financial_period(make_raw([ob("cash", 1.0, currency="TWD", unit="KTWD")],
                                            currency="TWD", unit="KTWD"))
        assert a.period.items["cash"] == 1.0


# ── 精確值語意（R23.68：下溢不得當真 0、大整數碰撞不得合併）─────────────

TINY = Fraction(1, 10 ** 400)          # float(TINY) == 0.0 下溢，但精確值非零


def _cash(obs_values, extra_ev="source_reported"):
    """對 cash 一個科目餵多筆觀測（其餘科目取完整基準），回傳 AdaptedPeriod。"""
    return adapt_financial_period(make_raw(
        full_obs(drop=("cash",)) + [ob("cash", v, extra_ev) for v in obs_values]))


class TestExactValueSemantics:
    @pytest.mark.parametrize("tiny", [TINY, -TINY])
    def test_tiny_reported_is_unrepresentable_gap_not_true_zero(self, tiny):
        assert float(tiny) == 0.0 or float(tiny) == -0.0       # 前提：float 下溢
        a = _cash([tiny])
        assert a.period.items["cash"] is None
        assert gaps_of(a) == {"cash": "unrepresentable_value"}

    def test_tiny_reported_flows_to_pack_as_missing_not_zero_ratio(self):
        e, gaps = _be(make_raw(full_obs(drop=("cash",)) + [ob("cash", TINY)]))
        assert e.items["cash"] is None
        m = e.metrics["cash_ratio_pct"]
        assert m.status == "unknown" and m.reason_code == "missing_input" and m.value is None
        assert [(g.item, g.reason_code) for g in gaps] == [("cash", "unrepresentable_value")]

    @pytest.mark.parametrize("tiny", [TINY, -TINY])
    @pytest.mark.parametrize("ev", ["legacy_default", "legacy_reset", "source_absent"])
    def test_tiny_nonzero_with_contradicting_marker_raises(self, tiny, ev):
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", tiny, ev)]))

    def test_tiny_with_reported_is_the_only_non_raising_combination(self):
        for ev in EVIDENCE_KINDS:
            try:
                adapt_financial_period(make_raw([ob("cash", TINY, ev)]))
                assert ev == "source_reported"
            except FinancialPeriodAdapterError:
                assert ev != "source_reported"

    def test_identical_tiny_duplicates_merge_to_one_unrepresentable_gap(self):
        a = _cash([TINY, Fraction(1, 10 ** 400)])
        assert gaps_of(a) == {"cash": "unrepresentable_value"}

    def test_different_tiny_values_conflict(self):
        a = _cash([TINY, 2 * TINY])
        assert gaps_of(a) == {"cash": "conflicting_observations"}

    def test_tiny_vs_true_zero_conflict(self):
        for perm in ([TINY, 0.0], [0.0, TINY]):
            assert gaps_of(_cash(perm)) == {"cash": "conflicting_observations"}

    @pytest.mark.parametrize("order", [0, 1, 2])
    def test_float_colliding_big_ints_conflict_any_order(self, order):
        vals = [[2 ** 53, 2 ** 53 + 1], [2 ** 53 + 1, 2 ** 53], [2 ** 53, 5, 2 ** 53 + 1]][order]
        a = _cash(vals)
        assert a.period.items["cash"] is None
        assert gaps_of(a) == {"cash": "conflicting_observations"}

    def test_big_int_alone_still_outputs_float_lossy_but_nonzero(self):
        a = _cash([2 ** 53 + 1])
        assert a.period.items["cash"] == float(2 ** 53) and "cash" not in gaps_of(a)

    def test_int_and_equal_float_merge(self):
        a = _cash([2 ** 53, float(2 ** 53)])
        assert a.period.items["cash"] == 9007199254740992.0 and "cash" not in gaps_of(a)

    def test_numpy_int_equals_python_int(self):
        np = pytest.importorskip("numpy")
        a = _cash([np.int64(7), 7, np.int32(7), 7.0])
        assert a.period.items["cash"] == 7.0 and "cash" not in gaps_of(a)

    def test_numpy_int_vs_colliding_int_conflict(self):
        np = pytest.importorskip("numpy")
        assert gaps_of(_cash([np.int64(2 ** 53 + 1), 2 ** 53])) == {"cash": "conflicting_observations"}

    @pytest.mark.parametrize("perm", [(Fraction(1, 10), 0.1), (0.1, Fraction(1, 10))])
    def test_float_vs_decimal_fraction_with_different_exact_value_conflict(self, perm):
        assert gaps_of(_cash(list(perm))) == {"cash": "conflicting_observations"}

    def test_half_float_equals_half_fraction(self):
        a = _cash([0.5, Fraction(1, 2)])
        assert a.period.items["cash"] == 0.5 and "cash" not in gaps_of(a)

    def test_numpy_float32_exactness(self):
        np = pytest.importorskip("numpy")
        assert "cash" not in gaps_of(_cash([np.float32(0.5), 0.5]))
        assert gaps_of(_cash([np.float32(0.1), 0.1])) == {"cash": "conflicting_observations"}

    def test_true_zero_of_every_type_is_zero_and_all_equal(self):
        np = pytest.importorskip("numpy")
        zeros = [0, 0.0, -0.0, Fraction(0), np.int64(0), np.float32(-0.0), np.float64(0.0)]
        for z in zeros:
            a = _cash([z])
            assert a.period.items["cash"] == 0.0 and a.period.items["cash"] is not None
            assert math.copysign(1.0, a.period.items["cash"]) == 1.0 and "cash" not in gaps_of(a)
        merged = _cash(zeros)
        assert merged.period.items["cash"] == 0.0 and "cash" not in gaps_of(merged)

    @pytest.mark.parametrize("v", [1e-300, -1e-300, 5e-324, -5e-324, 1e-310,
                                   Fraction(1, 10 ** 300)])
    def test_representable_tiny_values_stay_nonzero(self, v):
        a = _cash([v])
        assert a.period.items["cash"] is not None and abs(a.period.items["cash"]) > 0.0
        assert "cash" not in gaps_of(a)

    def test_ordinary_decimals_not_rejected(self):
        for v in (0.1, 1234.5678, 1e-9, 12345678.9):
            a = _cash([v])
            assert a.period.items["cash"] == v and "cash" not in gaps_of(a)

    def test_huge_fraction_overflow_still_raises(self):
        for ev in ("source_reported", "legacy_default"):
            with pytest.raises(FinancialPeriodAdapterError):
                _cash([Fraction(10 ** 400)], ev)

    def test_marker_with_non_finite_still_same_as_none(self):
        np = pytest.importorskip("numpy")
        for bad in (float("nan"), float("inf"), np.float32("nan"), np.float64("-inf")):
            for ev in ("source_absent", "legacy_default", "legacy_reset"):
                a = _cash([bad], ev)
                assert a.period.items["cash"] is None and len(gaps_of(a)) == 1

    def test_real_type_without_exact_representation_fails_closed(self):
        import numbers as _n

        class OpaqueReal:
            def __float__(self):
                return 1.5
        _n.Real.register(OpaqueReal)
        for ev in EVIDENCE_KINDS:
            with pytest.raises(FinancialPeriodAdapterError, match="精確表示"):
                adapt_financial_period(make_raw([ob("cash", OpaqueReal(), ev)]))

    def test_real_type_whose_ratio_fails_is_fail_closed(self):
        import numbers as _n

        class BrokenReal:
            def __float__(self):
                return 1.5

            def as_integer_ratio(self):
                raise TypeError("x")
        _n.Real.register(BrokenReal)
        with pytest.raises(FinancialPeriodAdapterError, match="精確表示"):
            adapt_financial_period(make_raw([ob("cash", BrokenReal())]))

    def test_new_reason_code_registered_with_clean_detail(self):
        assert "unrepresentable_value" in GAP_REASON_CODES
        g = next(x for x in _cash([TINY]).gaps if x.item == "cash")
        assert g.detail.strip() and "cash" in g.detail

    def test_exact_helper_values(self):
        assert fpa._exact("cash", 0.5) == Fraction(1, 2)
        assert fpa._exact("cash", 7) == Fraction(7)
        assert fpa._exact("cash", Fraction(1, 3)) == Fraction(1, 3)
        assert fpa._exact("cash", float("nan")) is None and fpa._exact("cash", float("-inf")) is None
        assert fpa._exact("cash", 0.1) != Fraction(1, 10)


class TestPathologicalNumericTypes:
    @pytest.mark.parametrize("cls", _PATHOLOGICAL, ids=lambda c: c.__name__)
    @pytest.mark.parametrize("ev", list(EVIDENCE_KINDS))
    def test_all_pathological_types_raise_adapter_error_exactly(self, cls, ev):
        with pytest.raises(Exception) as ei:
            adapt_financial_period(make_raw([ob("cash", cls(), ev)]))
        assert type(ei.value) is FinancialPeriodAdapterError
        msg = str(ei.value)
        assert "cash" in msg and cls.__name__ in msg and "12345" not in msg and "boom" not in msg

    @pytest.mark.parametrize("cls", _PATHOLOGICAL, ids=lambda c: c.__name__)
    def test_pathological_through_build_evidence_too(self, cls):
        with pytest.raises(FinancialPeriodAdapterError):
            build_evidence_from_raw(make_raw([ob("cash", cls())]))

    @pytest.mark.parametrize("cls", [_FloatInterruptReal, _RatioInterruptReal],
                             ids=lambda c: c.__name__)
    def test_base_exception_is_not_swallowed(self, cls):
        # _FloatInterruptReal 走 float() 路徑，_RatioInterruptReal 走精確值路徑；兩條都不得吞 BaseException
        with pytest.raises(KeyboardInterrupt):
            adapt_financial_period(make_raw([ob("cash", cls())]))

    def test_known_handled_paths_do_not_become_raise(self):
        np = pytest.importorskip("numpy")
        assert gaps_of(_cash([float("nan")])) == {"cash": "non_finite_value"}
        assert gaps_of(_cash([np.float32("inf")])) == {"cash": "non_finite_value"}
        assert gaps_of(_cash([TINY])) == {"cash": "unrepresentable_value"}
        assert gaps_of(_cash([Fraction(1, 10 ** 310)])) == {"cash": "unrepresentable_value"}


class TestLongdoubleExactness:
    def test_adjacent_longdoubles_with_same_double_conflict(self):
        np = pytest.importorskip("numpy")
        if np.finfo(np.longdouble).nmant <= np.finfo(np.float64).nmant:
            pytest.skip("此平台 np.longdouble 精度與 float64 相同，無法構造「轉 double 後相同」的相鄰值")
        a = np.longdouble(1)
        b = np.nextafter(a, np.longdouble(2))
        assert a != b and float(a) == float(b)               # 前提：不同的 longdouble，同一個 double
        for pair in ([a, b], [b, a]):
            assert gaps_of(_cash(pair)) == {"cash": "conflicting_observations"}
        assert "cash" not in gaps_of(_cash([a, np.longdouble(1)]))   # 相同值仍合併


class TestMixedNoValueReasons:
    """兩筆都「無值」但原因不同，不得被當成一致（以現行正式碼行為為準：皆為衝突）。"""

    @pytest.mark.parametrize("pair", [
        (("source_absent", None), ("source_reported", float("nan"))),
        (("legacy_default", 0.0), ("legacy_reset", 0.0)),
        (("source_absent", None), ("legacy_default", 0.0)),
        (("source_absent", None), ("legacy_reset", None)),
        (("source_reported", None), ("source_absent", None)),
        (("source_reported", None), ("source_reported", float("inf"))),
    ])
    def test_every_permutation_is_conflict(self, pair):
        for order in (pair, pair[::-1]):
            a = adapt_financial_period(make_raw(full_obs(drop=("cash",)) + [
                ob("cash", v, ev) for ev, v in order]))
            assert a.period.items["cash"] is None
            assert gaps_of(a) == {"cash": "conflicting_observations"}

    def test_same_reason_no_value_pairs_still_merge(self):
        for ev, v in (("source_absent", None), ("legacy_default", 0.0), ("legacy_reset", None)):
            a = adapt_financial_period(make_raw(full_obs(drop=("cash",)) + [
                ob("cash", v, ev), ob("cash", None, ev)]))
            assert len(gaps_of(a)) == 1 and gaps_of(a)["cash"] != "conflicting_observations"


class TestSubnormalFailClosed:
    MIN = sys.float_info.min

    def test_constant_equals_sys_float_info_min(self):
        assert fpa._FLOAT_MIN_NORMAL == sys.float_info.min

    @pytest.mark.parametrize("sign", [1, -1])
    def test_non_double_subnormal_is_unrepresentable(self, sign):
        v = sign * Fraction(1, 10 ** 310)
        assert 0.0 < abs(float(v)) < self.MIN                 # 前提：落在次正規區、未下溢成 0
        a = _cash([v])
        assert a.period.items["cash"] is None
        assert gaps_of(a) == {"cash": "unrepresentable_value"}

    @pytest.mark.parametrize("v", [5e-324, -5e-324, 1e-310, -1e-310])
    def test_float_subnormal_originals_are_output(self, v):
        a = _cash([v])
        assert a.period.items["cash"] == v and "cash" not in gaps_of(a)

    def test_exactly_representable_fraction_subnormal_is_output(self):
        a = _cash([Fraction(5e-324), Fraction(1e-310)])       # 兩個不同值 → 衝突，但各自單獨可輸出
        assert gaps_of(a) == {"cash": "conflicting_observations"}
        for v in (5e-324, 1e-310):
            b = _cash([Fraction(v)])
            assert b.period.items["cash"] == v and "cash" not in gaps_of(b)

    def test_numpy_float32_subnormal_double_exact_is_output(self):
        np = pytest.importorskip("numpy")
        v = np.float32(1e-40)                                 # float32 次正規，但轉 double 為正規值
        a = _cash([v])
        assert a.period.items["cash"] == float(v) and "cash" not in gaps_of(a)

    def test_boundary_min_normal_and_neighbours(self):
        m = self.MIN
        below = math.nextafter(m, 0.0)                        # 最大次正規 double（本身可精確表示）
        above = math.nextafter(m, 1.0)
        for v in (m, below, above, -m, -below):
            a = _cash([v])
            assert a.period.items["cash"] == v and "cash" not in gaps_of(a), v
        # 恰在 min 與其下一個 double 之間、會被捨入成次正規 double（值不同）→ fail closed
        mid_below = Fraction(below) + Fraction(5e-324) / 4
        assert float(mid_below) == below and Fraction(below) != mid_below
        assert gaps_of(_cash([mid_below])) == {"cash": "unrepresentable_value"}
        # 在 min 之下極近處、會被捨入成 min（正規值）→ 屬正常範圍捨入，照常輸出
        round_up = Fraction(m) - Fraction(1, 10 ** 330)
        assert float(round_up) == m
        a = _cash([round_up])
        assert a.period.items["cash"] == m and "cash" not in gaps_of(a)
        # 在 min 之上的非 double 值（正常範圍捨入）→ 輸出
        above_mid = Fraction(m) + Fraction(1, 10 ** 330)
        b = _cash([above_mid])
        assert b.period.items["cash"] == m and "cash" not in gaps_of(b)

    def test_normal_range_half_ulp_rounding_still_accepted(self):
        for v in (Fraction(1, 3), 2 ** 53 + 1, Fraction(2, 3), Fraction(10 ** 20 + 1, 7)):
            a = _cash([v])
            assert a.period.items["cash"] is not None and "cash" not in gaps_of(a), v

    def test_identical_inexact_subnormals_merge_and_different_conflict(self):
        v = Fraction(1, 10 ** 310)
        assert gaps_of(_cash([v, Fraction(1, 10 ** 310)])) == {"cash": "unrepresentable_value"}
        assert gaps_of(_cash([v, 2 * v])) == {"cash": "conflicting_observations"}

    def test_marker_with_inexact_subnormal_still_contradiction(self):
        for ev in ("legacy_default", "legacy_reset", "source_absent"):
            with pytest.raises(FinancialPeriodAdapterError):
                _cash([Fraction(1, 10 ** 310)], ev)


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
    def test_all_eight_codes_produced(self):
        obs = [ob("revenue", None, "source_absent"), ob("cogs", 0.0, "legacy_default"),
               ob("gross_profit", 0.0, "legacy_reset"), ob("operating_income", float("nan")),
               ob("net_income", 1.0), ob("net_income", 2.0), ob("total_assets", None),
               ob("equity", Fraction(1, 10 ** 400))]
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

    @pytest.mark.parametrize("ev", list(EVIDENCE_KINDS))
    @pytest.mark.parametrize("val", ["1D", "NaT"])
    def test_numpy_timedelta_raises_adapter_error_not_other_exception(self, ev, val):
        np = pytest.importorskip("numpy")
        v = np.timedelta64(1, "D") if val == "1D" else np.timedelta64("NaT", "D")
        with pytest.raises(Exception) as ei:
            adapt_financial_period(make_raw([ob("cash", v, ev)]))
        assert type(ei.value) is FinancialPeriodAdapterError
        assert "timedelta64" in str(ei.value) and "NaT" not in str(ei.value)

    def test_numpy_bool_rejected(self):
        np = pytest.importorskip("numpy")
        with pytest.raises(FinancialPeriodAdapterError):
            adapt_financial_period(make_raw([ob("cash", np.bool_(True))]))

    def test_numeric_acceptance_matches_pack(self):
        """與 pack 的 _normalize_items 型別行為一致：同一個值，兩邊同進同出。"""
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
           ob("net_income", 1.0), ob("net_income", 2.0), ob("total_assets", None),
           ob("equity", Fraction(1, 10 ** 400))]
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
                       "原樣回顯", "大小寫", "timedelta64", "下溢", "與觀測順序無關",
                       "gap.detail", "含 ``0.0``", "精確值", "unrepresentable_value", "fail closed"):
            assert needle in doc, needle

    def test_reason_code_set_is_exactly_eight(self):
        # 第 8 碼 unrepresentable_value 為 R23.68 新增（非零原值轉 float 下溢 / 溢位）
        assert GAP_REASON_CODES == ("not_observed", "source_absent", "legacy_default_zero",
                                    "legacy_anomaly_reset", "non_finite_value",
                                    "conflicting_observations", "value_missing_for_reported",
                                    "unrepresentable_value")


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
            "__future__", "datetime", "math", "numbers", "dataclasses", "fractions", "types", "typing",
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


def _assert_unconvertible_real_is_adapter_error() -> None:
    np = pytest.importorskip("numpy")
    for v in (np.timedelta64(1, "D"), np.timedelta64("NaT", "D")):
        for ev in EVIDENCE_KINDS:
            try:
                adapt_financial_period(make_raw([ob("cash", v, ev)]))
            except FinancialPeriodAdapterError:
                continue
            except Exception as exc:  # noqa: BLE001 — 洩漏了別種例外也算失敗
                raise AssertionError(f"洩漏 {type(exc).__name__}") from exc
            raise AssertionError("應 raise")


def _assert_unit_whitespace_sensitive() -> None:
    _expect_raises(lambda: adapt_financial_period(
        make_raw([ob("cash", 1.0, unit="KTWD ")], unit="KTWD")))


def _assert_source_absent_zero_raises() -> None:
    for v in (0.0, -0.0, 0):
        _expect_raises(lambda v=v: adapt_financial_period(make_raw([ob("cash", v, "source_absent")])))


def _assert_exact_semantics() -> None:
    assert gaps_of(_cash([TINY])) == {"cash": "unrepresentable_value"}
    assert _cash([TINY]).period.items["cash"] is None
    assert gaps_of(_cash([2 ** 53, 2 ** 53 + 1])) == {"cash": "conflicting_observations"}
    assert gaps_of(_cash([Fraction(1, 10), 0.1])) == {"cash": "conflicting_observations"}
    ok = _cash([0.5, Fraction(1, 2), 0.5])
    assert ok.period.items["cash"] == 0.5 and "cash" not in gaps_of(ok)
    z = _cash([0, -0.0, Fraction(0)])
    assert z.period.items["cash"] == 0.0 and z.period.items["cash"] is not None and "cash" not in gaps_of(z)


def _assert_tiny_marker_raises() -> None:
    for ev in ("legacy_default", "legacy_reset", "source_absent"):
        for t in (TINY, -TINY):
            _expect_raises(lambda ev=ev, t=t: adapt_financial_period(make_raw([ob("cash", t, ev)])))


def _assert_pathological_raise_adapter_error() -> None:
    for cls in _PATHOLOGICAL:
        for ev in EVIDENCE_KINDS:
            try:
                adapt_financial_period(make_raw([ob("cash", cls(), ev)]))
            except FinancialPeriodAdapterError:
                continue
            except Exception as exc:  # noqa: BLE001 — 洩漏別種例外也算失敗
                raise AssertionError(f"{cls.__name__}/{ev} 洩漏 {type(exc).__name__}") from exc
            raise AssertionError("應 raise")


def _assert_longdouble_exact() -> None:
    np = pytest.importorskip("numpy")
    if np.finfo(np.longdouble).nmant <= np.finfo(np.float64).nmant:
        pytest.skip("平台 longdouble 精度等同 float64")
    a = np.longdouble(1)
    b = np.nextafter(a, np.longdouble(2))
    assert gaps_of(_cash([a, b])) == {"cash": "conflicting_observations"}


def _assert_no_value_reasons_conflict() -> None:
    combos = [(("source_absent", None), ("source_reported", float("nan"))),
              (("legacy_default", 0.0), ("legacy_reset", 0.0)),
              (("source_absent", None), ("legacy_default", 0.0))]
    for pair in combos:
        for order in (pair, pair[::-1]):
            a = adapt_financial_period(make_raw(full_obs(drop=("cash",)) + [
                ob("cash", v, ev) for ev, v in order]))
            assert gaps_of(a) == {"cash": "conflicting_observations"}


def _assert_subnormal_fail_closed() -> None:
    assert gaps_of(_cash([Fraction(1, 10 ** 310)])) == {"cash": "unrepresentable_value"}
    assert _cash([1e-310]).period.items["cash"] == 1e-310


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
            lambda o: (None, 0.0, None) if o.evidence == "legacy_default" else orig(o))
        with pytest.raises(self._RED):
            _assert_legacy_default_not_zero()

    def test_legacy_reset_treated_as_zero_goes_red(self, monkeypatch):
        orig = fpa._outcome
        monkeypatch.setattr(
            fpa, "_outcome",
            lambda o: (None, 0.0, None) if o.evidence == "legacy_reset" else orig(o))
        with pytest.raises(self._RED):
            _assert_legacy_reset_not_zero()

    def test_all_zeros_turned_into_none_goes_red(self, monkeypatch):
        orig = fpa._outcome

        def mutant(o):
            reason, val, ex = orig(o)
            if reason is None and val is not None and abs(val) < 1e-12:
                return "not_observed", None, None
            return reason, val, ex
        monkeypatch.setattr(fpa, "_outcome", mutant)
        with pytest.raises(self._RED):
            _assert_true_zero_kept()

    def test_conflict_resolved_by_max_goes_red(self, monkeypatch):
        monkeypatch.setattr(
            fpa, "_merge_outcomes",
            lambda outs: max(((x[0], x[1]) for x in outs),
                             key=lambda x: (x[1] is not None, x[1] if x[1] is not None else 0.0)))
        with pytest.raises(self._RED):
            _assert_conflict_not_resolved()

    def test_conflict_resolved_by_last_wins_goes_red(self, monkeypatch):
        monkeypatch.setattr(fpa, "_merge_outcomes", lambda outs: outs[-1][:2])
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
            reason, val, ex = orig(o)
            return (None, 0.0, None) if reason == "non_finite_value" else (reason, val, ex)
        monkeypatch.setattr(fpa, "_outcome", mutant)
        with pytest.raises(self._RED):
            _assert_non_finite_not_zero()

    def test_reported_without_value_coerced_to_zero_goes_red(self, monkeypatch):
        orig = fpa._outcome

        def mutant(o):
            reason, val, ex = orig(o)
            return (None, 0.0, None) if reason == "value_missing_for_reported" else (reason, val, ex)
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
                return None, 0.0, None
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

    def test_baseline_d_guards_pass(self):
        for f in (_assert_unconvertible_real_is_adapter_error, _assert_unit_whitespace_sensitive,
                  _assert_source_absent_zero_raises):
            f()

    def test_unit_only_stripped_in_comparison_goes_red(self, monkeypatch):
        orig = fpa._check_observation_consistency

        def mutant(raw, obs):
            return orig(raw, dataclasses.replace(obs, unit=obs.unit.strip() if obs.unit else obs.unit))
        monkeypatch.setattr(fpa, "_check_observation_consistency", mutant)
        with pytest.raises(self._RED):
            _assert_unit_whitespace_sensitive()

    def test_source_absent_zero_allowed_goes_red(self, monkeypatch):
        orig = fpa._validate_value

        def mutant(obs):
            if obs.evidence == "source_absent":
                return None
            return orig(obs)
        monkeypatch.setattr(fpa, "_validate_value", mutant)
        with pytest.raises(self._RED):
            _assert_source_absent_zero_raises()

    def test_only_overflow_caught_leaks_type_error_goes_red(self, monkeypatch):
        """縮回只捕捉 OverflowError 的舊行為：以等價 mutant 取代轉換步驟，TypeError 洩漏 → 守衛紅。"""
        import numbers as _n

        def mutant(obs):
            v = obs.value
            if v is None:
                return
            if isinstance(v, bool) or not isinstance(v, _n.Real):
                raise FinancialPeriodAdapterError("type")
            try:
                float(v)
            except OverflowError:
                raise FinancialPeriodAdapterError("overflow")
        monkeypatch.setattr(fpa, "_validate_value", mutant)
        with pytest.raises(AssertionError):
            _assert_unconvertible_real_is_adapter_error()

    def test_baseline_exact_guards_pass(self):
        _assert_exact_semantics()
        _assert_tiny_marker_raises()

    def test_merge_compares_float_value_instead_of_exact_goes_red(self, monkeypatch):
        def mutant(outs):
            first = outs[0]
            if all(o[0] == first[0] and o[1] == first[1] for o in outs[1:]):
                return first[0], first[1]
            return "conflicting_observations", None
        monkeypatch.setattr(fpa, "_merge_outcomes", mutant)
        with pytest.raises(self._RED):
            _assert_exact_semantics()

    def test_merge_uses_approximate_equality_goes_red(self, monkeypatch):
        def mutant(outs):
            first = outs[0]
            same = all(o[0] == first[0] and (o[1] is None) == (first[1] is None)
                       and (o[1] is None or math.isclose(o[1], first[1], rel_tol=1e-9))
                       for o in outs[1:])
            return (first[0], first[1]) if same else ("conflicting_observations", None)
        monkeypatch.setattr(fpa, "_merge_outcomes", mutant)
        with pytest.raises(self._RED):
            _assert_exact_semantics()

    def test_underflow_treated_as_true_zero_goes_red(self, monkeypatch):
        orig = fpa._outcome

        def mutant(o):
            reason, val, ex = orig(o)
            return (None, 0.0, ex) if reason == "unrepresentable_value" else (reason, val, ex)
        monkeypatch.setattr(fpa, "_outcome", mutant)
        with pytest.raises(self._RED):
            _assert_exact_semantics()

    def test_new_gap_removed_goes_red(self, monkeypatch):
        orig = fpa._outcome

        def mutant(o):
            reason, val, ex = orig(o)
            return (None, None, ex) if reason == "unrepresentable_value" else (reason, val, ex)
        monkeypatch.setattr(fpa, "_outcome", mutant)
        with pytest.raises(self._RED):
            _assert_exact_semantics()

    def test_marker_contradiction_judged_on_float_goes_red(self, monkeypatch):
        orig = fpa._validate_value

        def mutant(obs):
            if obs.value is not None and obs.evidence != "source_reported":
                return orig(dataclasses.replace(obs, value=float(obs.value)))
            return orig(obs)
        monkeypatch.setattr(fpa, "_validate_value", mutant)
        with pytest.raises(self._RED):
            _assert_tiny_marker_raises()

    def test_exact_representation_replaced_by_float_goes_red(self, monkeypatch):
        orig = fpa._exact

        def mutant(item, v):
            r = orig(item, v)
            return None if r is None else Fraction(float(v))
        monkeypatch.setattr(fpa, "_exact", mutant)
        with pytest.raises(self._RED):
            _assert_exact_semantics()

    def test_baseline_r2369_guards_pass(self):
        _assert_pathological_raise_adapter_error()
        _assert_no_value_reasons_conflict()
        _assert_subnormal_fail_closed()
        _assert_longdouble_exact()

    def test_exact_narrowed_to_some_exceptions_goes_red(self, monkeypatch):
        def mutant(item, v):
            try:
                return fpa._exact_unsafe(item, v)
            except (TypeError, ValueError, OverflowError):
                raise FinancialPeriodAdapterError("mutant") from None
        monkeypatch.setattr(fpa, "_exact", mutant)
        with pytest.raises(self._RED):
            _assert_pathological_raise_adapter_error()

    def test_to_float_narrowed_goes_red(self, monkeypatch):
        def mutant(item, v):
            try:
                return float(v)
            except (TypeError, ValueError, OverflowError):
                raise FinancialPeriodAdapterError("mutant") from None
        monkeypatch.setattr(fpa, "_to_float", mutant)
        with pytest.raises(self._RED):
            _assert_pathological_raise_adapter_error()

    def test_longdouble_float_branch_goes_red(self, monkeypatch):
        orig = fpa._exact

        def mutant(item, v):
            r = orig(item, v)
            if r is None or isinstance(v, numbers.Rational):
                return r
            return Fraction(float(v))
        monkeypatch.setattr(fpa, "_exact", mutant)
        with pytest.raises(self._RED):
            _assert_longdouble_exact()

    def test_merge_ignores_gap_reason_goes_red(self, monkeypatch):
        def mutant(outs):
            first = outs[0]
            if all(o[2] == first[2] for o in outs[1:]):
                return first[0], first[1]
            return "conflicting_observations", None
        monkeypatch.setattr(fpa, "_merge_outcomes", mutant)
        with pytest.raises(self._RED):
            _assert_no_value_reasons_conflict()

    def test_subnormal_criterion_removed_goes_red(self, monkeypatch):
        monkeypatch.setattr(fpa, "_FLOAT_MIN_NORMAL", 0.0)
        with pytest.raises(self._RED):
            _assert_subnormal_fail_closed()

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
