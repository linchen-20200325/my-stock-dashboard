"""test_reconcile.py — S-RECON-1 v18.252 + 健康評分 v18.396 P5-B5 雙演算法對帳 unit tests"""
from __future__ import annotations
import pytest

from src.compute.risk import (
    reconcile_pair,
    reconcile_us10y_yield,
    reconcile_monthly_revenue_yoy,
)
from src.compute.risk.reconcile import (
    compute_health_score_arithmetic,
    compute_health_score_min_of_factors,
    reconcile_health_score,
)


class TestReconcilePair:
    def test_agree_exact(self):
        r = reconcile_pair("X", 4.25, 4.25, source_a="A", source_b="B")
        assert r['agree'] is True
        assert r['status'] == 'agree'
        assert r['delta_abs'] == 0.0

    def test_agree_within_tolerance(self):
        # default abs_tol=1e-4, rel_tol=1e-3
        r = reconcile_pair("X", 4.2500, 4.2501, source_a="A", source_b="B")
        # 1e-4 within abs_tol → agree
        assert r['agree'] is True

    def test_disagree_outside_tolerance(self):
        r = reconcile_pair("X", 4.25, 5.00, source_a="A", source_b="B")
        assert r['agree'] is False
        assert r['status'] == 'disagree'
        assert r['delta_abs'] == pytest.approx(0.75)

    def test_a_missing(self):
        r = reconcile_pair("X", None, 4.25, source_a="A", source_b="B")
        assert r['status'] == 'a_missing'
        assert r['agree'] is False
        assert r['delta_abs'] is None

    def test_b_missing(self):
        r = reconcile_pair("X", 4.25, None, source_a="A", source_b="B")
        assert r['status'] == 'b_missing'

    def test_both_missing(self):
        r = reconcile_pair("X", None, None, source_a="A", source_b="B")
        assert r['status'] == 'both_missing'

    def test_relative_tolerance(self):
        # 0.1% relative diff within rel_tol=1e-3 → agree
        r = reconcile_pair("X", 1000.0, 1000.5, source_a="A", source_b="B",
                            abs_tol=1.0, rel_tol=1e-3)
        assert r['agree'] is True


class TestReconcileUs10yYield:
    def test_fred_vs_yahoo_agree(self):
        # FRED 4.25%, Yahoo TNX 42.5 (= 4.25 × 10)
        r = reconcile_us10y_yield(4.25, 42.5)
        assert r['agree'] is True
        assert r['name'] == "US10Y_YIELD"
        assert r['value_a'] == 4.25
        assert r['value_b'] == 4.25  # converted

    def test_within_5bp_tolerance(self):
        # FRED 4.25, Yahoo 4.27 (2bp diff) → agree
        r = reconcile_us10y_yield(4.25, 42.7)
        assert r['agree'] is True

    def test_outside_5bp_disagree(self):
        # FRED 4.25, Yahoo 4.50 (25bp diff) → disagree
        r = reconcile_us10y_yield(4.25, 45.0)
        assert r['agree'] is False
        assert r['status'] == 'disagree'

    def test_yahoo_missing(self):
        r = reconcile_us10y_yield(4.25, None)
        assert r['status'] == 'b_missing'

    def test_fred_missing(self):
        r = reconcile_us10y_yield(None, 42.5)
        assert r['status'] == 'a_missing'


class TestReconcileMonthlyRevenueYoy:
    def test_agree(self):
        r = reconcile_monthly_revenue_yoy(0.15, 0.15)
        assert r['agree'] is True

    def test_within_0_1pp_tolerance(self):
        # 0.05pp diff < abs_tol 0.1pp → agree
        r = reconcile_monthly_revenue_yoy(0.15, 0.155)
        assert r['agree'] is True

    def test_outside_tolerance_disagree(self):
        # 0.3 absolute diff > abs_tol 0.1 → disagree
        r = reconcile_monthly_revenue_yoy(0.15, 0.50)
        assert r['agree'] is False


def test_module_smoke():
    """import + 3 函式可叫"""
    from src.compute.risk import reconcile
    assert callable(reconcile.reconcile_pair)
    assert callable(reconcile.reconcile_us10y_yield)
    assert callable(reconcile.reconcile_monthly_revenue_yoy)
    # v18.396 P5-B5:健康評分雙演算法
    assert callable(reconcile.compute_health_score_arithmetic)
    assert callable(reconcile.compute_health_score_min_of_factors)
    assert callable(reconcile.reconcile_health_score)


# ══════════════════════════════════════════════════════════════════
# v18.396 P5-B5:健康評分雙演算法對帳(§4.3 補完)
# ══════════════════════════════════════════════════════════════════

class TestComputeHealthArithmetic:
    def test_basic(self):
        # v19.102 校準 SSOT(0.6/0.4/+0):80*0.6 + 80*0.4 + 0 = 80
        v = compute_health_score_arithmetic(80, 80, 5000)
        assert v == 80.0

    def test_fnet_zero_or_negative(self):
        # v19.102:fnet bonus 歸零 → 正負零皆同分(80*0.6+80*0.4=80)
        assert compute_health_score_arithmetic(80, 80, 0) == 80.0
        assert compute_health_score_arithmetic(80, 80, -5000) == 80.0
        assert compute_health_score_arithmetic(80, 80, 5000) == 80.0

    def test_score_clipped(self):
        # score_pct=150 → clip 至 100;80*0.6 + 100*0.4 + 0 = 48+40 = 88
        v = compute_health_score_arithmetic(80, 150, 5000)
        assert v == 88.0

    def test_missing_input_returns_none(self):
        assert compute_health_score_arithmetic(None, 80, 5000) is None
        assert compute_health_score_arithmetic(80, None, 5000) is None
        assert compute_health_score_arithmetic(80, 80, None) is None


class TestComputeHealthMinOfFactors:
    def test_basic_positive_fnet(self):
        # min(80, 80) = 80(fnet 正不加額外限制)
        v = compute_health_score_min_of_factors(80, 80, 5000)
        assert v == 80.0

    def test_fnet_penalty(self):
        # fnet 負 → 加入 40 cap
        v = compute_health_score_min_of_factors(80, 80, -5000)
        assert v == 40.0

    def test_jq_weakest(self):
        # jqavg 30 < score_pct 80 → min = 30
        v = compute_health_score_min_of_factors(30, 80, 5000)
        assert v == 30.0

    def test_score_clipped(self):
        v = compute_health_score_min_of_factors(80, 150, 5000)
        assert v == 80.0  # min(80, 100)

    def test_missing_input_returns_none(self):
        assert compute_health_score_min_of_factors(None, 80, 5000) is None


class TestReconcileHealthScore:
    def test_agree_balanced(self):
        # 平衡情境:v1≈v2,容差內 agree(v19.102 權重 0.6/0.4/+0)
        # jqavg=80, score_pct=80, fnet=+:v1=80, v2=min(80,80)=80 → delta=0 → agree
        r = reconcile_health_score(80, 80, 5000)
        assert r['name'] == 'MACRO_HEALTH'
        assert r['agree'] is True
        assert r['value_a'] == 80.0
        assert r['value_b'] == 80.0

    def test_disagree_short_board_hidden(self):
        # 短板隱藏情境:jqavg 90(高),score_pct 20(低)→ disagree
        # 這正是 reconcile 想揭露的「arithmetic mean 掩蓋了某因子過弱」場景
        r = reconcile_health_score(90, 20, 5000)
        assert r['agree'] is False
        assert r['status'] == 'disagree'
        # v1 = 90*0.6 + 20*0.4 + 0 = 62(v19.102)
        # v2 = min(90, 20) = 20
        assert r['value_a'] == 62.0
        assert r['value_b'] == 20.0
        assert r['delta_abs'] == pytest.approx(42.0)

    def test_missing_input(self):
        r = reconcile_health_score(None, 80, 5000)
        assert r['status'] == 'both_missing'  # 兩 v 都 None

    def test_fnet_negative_penalizes_both(self):
        # v19.102:v1 無 fnet bonus(恆 80);v2(min-of-factors)fnet 負仍加 40 cap
        # → min(80, 80, 40) = 40;delta = 40 > abs_tol 15 → disagree
        r = reconcile_health_score(80, 80, -5000)
        assert r['value_a'] == 80.0
        assert r['value_b'] == 40.0
        assert r['agree'] is False
