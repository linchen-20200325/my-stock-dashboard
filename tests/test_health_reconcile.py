"""tests/test_health_reconcile.py — §4.3 健康評分對帳守(v18.300)

健康評分 method A(生產 calc_traffic_light)vs method B(對照演算法)
abs diff <= 5 視為對齊。
"""
from __future__ import annotations

import math

import pytest

from health_reconcile import (
    compute_method_b_health,
    reconcile_health_score,
    HEALTH_RECONCILE_TOLERANCE,
    HealthReconcileResult,
)


# ════════════════════════════════════════════════════════════════
# 1. Method B 純函式行為
# ════════════════════════════════════════════════════════════════
class TestMethodBHealth:
    def test_all_positive_inputs(self):
        # (60 + 60 + 100) / 3 ≈ 73.3
        result = compute_method_b_health(jqavg=60, score=3, fnet=50)
        assert math.isclose(result, 73.3, abs_tol=0.1)

    def test_all_zero_inputs(self):
        # (0 + 0 + 50) / 3 ≈ 16.7(fnet=0 → 中性 50)
        result = compute_method_b_health(jqavg=0, score=0, fnet=0)
        assert math.isclose(result, 16.7, abs_tol=0.1)

    def test_all_negative_or_low(self):
        # (0 + 0 + 0) / 3 = 0
        result = compute_method_b_health(jqavg=0, score=0, fnet=-100)
        assert result == 0.0

    def test_score_clamp_at_100(self):
        """score 過高 (>5) → clamp 至 100。"""
        # (50 + 100 + 100) / 3 ≈ 83.3
        result = compute_method_b_health(jqavg=50, score=10, fnet=100)
        assert math.isclose(result, 83.3, abs_tol=0.1)

    def test_jqavg_clamp(self):
        """jqavg 過高(>100)/ 過低(<0)→ clamp。"""
        # jqavg=200 → clamp 100, score=3 → 60, fnet>0 → 100
        # (100 + 60 + 100) / 3 ≈ 86.7
        result = compute_method_b_health(jqavg=200, score=3, fnet=100)
        assert math.isclose(result, 86.7, abs_tol=0.1)

    def test_none_inputs_use_defaults(self):
        """全 None → defaults(jqavg=50, score=0, fnet=0)→ (50+0+50)/3 ≈ 33.3。"""
        result = compute_method_b_health(jqavg=None, score=None, fnet=None)
        assert math.isclose(result, 33.3, abs_tol=0.1)


# ════════════════════════════════════════════════════════════════
# 2. Reconcile 對帳結果
# ════════════════════════════════════════════════════════════════
class TestReconcileAlignment:
    def test_aligned_when_within_tolerance(self):
        """method A 在 method B ± 5 內 → aligned。"""
        # Method A 估 75, Method B = 73.3 → diff 1.7,within 5 → aligned
        r = reconcile_health_score(75.0, jqavg=60, score=3, fnet=50)
        assert r.within_tolerance
        assert r.reason == 'aligned'
        assert math.isclose(r.method_b, 73.3, abs_tol=0.1)

    def test_drift_warning_when_outside_tolerance(self):
        """abs diff > 5 但 <= 30 → drift_warning。"""
        # Method B = 73.3, A = 90 → diff 16.7 > 5
        r = reconcile_health_score(90.0, jqavg=60, score=3, fnet=50)
        assert not r.within_tolerance
        assert r.reason == 'drift_warning'

    def test_extreme_divergence_above_30(self):
        """abs diff > 30 → extreme_divergence(可能輸入錯)。"""
        # Method B = 73.3, A = 10 → diff 63.3 > 30
        r = reconcile_health_score(10.0, jqavg=60, score=3, fnet=50)
        assert r.reason == 'extreme_divergence'
        assert not r.within_tolerance

    def test_exactly_at_boundary_5_is_aligned(self):
        """abs diff == 5(邊界)→ aligned(包含)。"""
        # Method B = 73.3, A = 78.3 → diff 5.0
        r = reconcile_health_score(78.3, jqavg=60, score=3, fnet=50)
        assert r.within_tolerance
        assert r.reason == 'aligned'

    def test_diff_sign(self):
        """diff 可正可負(method_a - method_b)。"""
        # A < B → diff 負
        r1 = reconcile_health_score(50.0, jqavg=60, score=3, fnet=50)
        assert r1.diff < 0
        # A > B → diff 正
        r2 = reconcile_health_score(85.0, jqavg=60, score=3, fnet=50)
        assert r2.diff > 0


# ════════════════════════════════════════════════════════════════
# 3. 整合:模擬生產輸入 → 對帳
# ════════════════════════════════════════════════════════════════
class TestProductionScenarios:
    def test_typical_bull_market(self):
        """多頭情境:jqavg=70, score=4, fnet>0
        Method A: 70*0.4 + min(4/5*100,100)*0.4 + 20 = 28 + 32 + 20 = 80
        Method B: (70 + 80 + 100)/3 = 83.3
        diff ≈ -3.3 → aligned"""
        method_a = 70 * 0.4 + min(4/5*100, 100) * 0.4 + 20
        assert method_a == 80.0
        r = reconcile_health_score(method_a, jqavg=70, score=4, fnet=100)
        assert r.within_tolerance
        assert r.reason == 'aligned'

    def test_typical_bear_market(self):
        """空頭情境:jqavg=20, score=1, fnet<0
        Method A: 20*0.4 + min(1/5*100,100)*0.4 + 0 = 8 + 8 + 0 = 16
        Method B: (20 + 20 + 0)/3 ≈ 13.3
        diff ≈ +2.7 → aligned"""
        method_a = 20 * 0.4 + min(1/5*100, 100) * 0.4 + 0
        assert method_a == 16.0
        r = reconcile_health_score(method_a, jqavg=20, score=1, fnet=-100)
        assert r.within_tolerance

    def test_typical_neutral(self):
        """中性情境:jqavg=50, score=2.5, fnet=0
        Method A: 50*0.4 + min(2.5/5*100,100)*0.4 + 0 = 20 + 20 + 0 = 40
        Method B: (50 + 50 + 50)/3 ≈ 50.0
        diff ≈ -10 → drift_warning(中性 fnet 兩 method 處理差異最大)"""
        method_a = 50 * 0.4 + min(2.5/5*100, 100) * 0.4 + 0
        assert method_a == 40.0
        r = reconcile_health_score(method_a, jqavg=50, score=2.5, fnet=0)
        # diff = 40 - 50 = -10,abs 10 > 5 → drift_warning
        assert not r.within_tolerance
        assert r.reason == 'drift_warning'


# ════════════════════════════════════════════════════════════════
# 4. SSOT 容差常數
# ════════════════════════════════════════════════════════════════
class TestTolerance:
    def test_default_tolerance_is_5(self):
        """SSOT:容差 5 分,改動須更新 docstring。"""
        assert HEALTH_RECONCILE_TOLERANCE == 5.0

    def test_custom_tolerance(self):
        """caller 可自訂容差(如 backtest 用更寬鬆)。"""
        # diff = 10,with tol 5 = warning,with tol 15 = aligned
        r_strict = reconcile_health_score(50.0, jqavg=60, score=3, fnet=50, tolerance=5.0)
        assert not r_strict.within_tolerance
        r_loose = reconcile_health_score(50.0, jqavg=60, score=3, fnet=50, tolerance=30.0)
        assert r_loose.within_tolerance
