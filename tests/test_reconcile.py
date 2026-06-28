"""test_reconcile.py — S-RECON-1 v18.252 雙演算法對帳 unit tests"""
from __future__ import annotations
import pytest

from src.compute.risk import (
    reconcile_pair,
    reconcile_us10y_yield,
    reconcile_monthly_revenue_yoy,
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
