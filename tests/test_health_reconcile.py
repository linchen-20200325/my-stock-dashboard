"""tests/test_health_reconcile.py — §4.3 健康評分對帳守(v18.300;v19.102 校準改版)

健康評分 method A(生產 calc_traffic_light)vs method B(對照演算法)
abs diff <= 5 視為對齊。

v19.102 校準採納(方案 B,MACRO_HEALTH_WEIGHT_PROPOSAL.md):
- Method A 權重 0.6/0.4/0(fnet bonus 歸零)+ score/max_score 正規化
- Method B 同步改「兩組件等權平均」:(jqavg + score/max*100)/2,fnet 不計分
  (參數保留向後相容),max_score 預設 4(market_regime 基本滿分)。
"""
from __future__ import annotations

import math

from src.compute.health import (
    HEALTH_RECONCILE_TOLERANCE,
    compute_method_b_health,
    reconcile_health_score,
)


# ════════════════════════════════════════════════════════════════
# 1. Method B 純函式行為(v19.102:兩組件等權,score/max*100)
# ════════════════════════════════════════════════════════════════
class TestMethodBHealth:
    def test_all_positive_inputs(self):
        # (60 + 3/4*100) / 2 = (60 + 75) / 2 = 67.5
        result = compute_method_b_health(jqavg=60, score=3, fnet=50)
        assert math.isclose(result, 67.5, abs_tol=0.1)

    def test_all_zero_inputs(self):
        # (0 + 0) / 2 = 0(v19.102:fnet 不再貢獻中性 50)
        result = compute_method_b_health(jqavg=0, score=0, fnet=0)
        assert result == 0.0

    def test_all_negative_or_low(self):
        # (0 + 0) / 2 = 0
        result = compute_method_b_health(jqavg=0, score=0, fnet=-100)
        assert result == 0.0

    def test_fnet_ignored_since_v19_102(self):
        # 校準:fnet 零預測力 → Method B 不計分;不同 fnet 同分
        a = compute_method_b_health(jqavg=60, score=3, fnet=999)
        b = compute_method_b_health(jqavg=60, score=3, fnet=-999)
        c = compute_method_b_health(jqavg=60, score=3, fnet=None)
        assert a == b == c

    def test_score_clamp_at_100(self):
        """score 過高(>max)→ clamp 至 100。(50 + 100) / 2 = 75。"""
        result = compute_method_b_health(jqavg=50, score=10, fnet=100)
        assert math.isclose(result, 75.0, abs_tol=0.1)

    def test_max_score_param(self):
        """max_score=6(全特徵 market_regime)→ score=3 → 50。(60+50)/2=55。"""
        result = compute_method_b_health(jqavg=60, score=3, max_score=6)
        assert math.isclose(result, 55.0, abs_tol=0.1)

    def test_jqavg_clamp(self):
        """jqavg 過高(>100)→ clamp。(100 + 75) / 2 = 87.5。"""
        result = compute_method_b_health(jqavg=200, score=3, fnet=100)
        assert math.isclose(result, 87.5, abs_tol=0.1)

    def test_none_inputs_use_defaults(self):
        """全 None → defaults(jqavg=50, score=0)→ (50+0)/2 = 25。"""
        result = compute_method_b_health(jqavg=None, score=None, fnet=None)
        assert math.isclose(result, 25.0, abs_tol=0.1)


# ════════════════════════════════════════════════════════════════
# 2. Reconcile 對帳結果
# ════════════════════════════════════════════════════════════════
class TestReconcileAlignment:
    def test_aligned_when_within_tolerance(self):
        """method A 在 method B ± 5 內 → aligned。"""
        # Method B = 67.5;A = 70 → diff 2.5,within 5 → aligned
        r = reconcile_health_score(70.0, jqavg=60, score=3, fnet=50)
        assert r.within_tolerance
        assert r.reason == 'aligned'
        assert math.isclose(r.method_b, 67.5, abs_tol=0.1)

    def test_drift_warning_when_outside_tolerance(self):
        """abs diff > 5 但 <= 30 → drift_warning。"""
        # Method B = 67.5, A = 90 → diff 22.5 > 5
        r = reconcile_health_score(90.0, jqavg=60, score=3, fnet=50)
        assert not r.within_tolerance
        assert r.reason == 'drift_warning'

    def test_extreme_divergence_above_30(self):
        """abs diff > 30 → extreme_divergence(可能輸入錯)。"""
        # Method B = 67.5, A = 10 → diff 57.5 > 30
        r = reconcile_health_score(10.0, jqavg=60, score=3, fnet=50)
        assert r.reason == 'extreme_divergence'
        assert not r.within_tolerance

    def test_exactly_at_boundary_5_is_aligned(self):
        """abs diff == 5(邊界)→ aligned(包含)。"""
        # Method B = 67.5, A = 72.5 → diff 5.0
        r = reconcile_health_score(72.5, jqavg=60, score=3, fnet=50)
        assert r.within_tolerance
        assert r.reason == 'aligned'

    def test_diff_sign(self):
        """diff 可正可負(method_a - method_b)。"""
        r1 = reconcile_health_score(50.0, jqavg=60, score=3, fnet=50)
        assert r1.diff < 0     # A(50) < B(67.5)
        r2 = reconcile_health_score(85.0, jqavg=60, score=3, fnet=50)
        assert r2.diff > 0     # A(85) > B(67.5)


# ════════════════════════════════════════════════════════════════
# 3. 整合:模擬生產輸入 → 對帳(v19.102 權重)
# ════════════════════════════════════════════════════════════════
class TestProductionScenarios:
    def test_typical_bull_market(self):
        """多頭情境:jqavg=70, score=4(max 4), fnet>0
        Method A: 70*0.6 + min(4/4*100,100)*0.4 + 0 = 42 + 40 = 82
        Method B: (70 + 100)/2 = 85
        diff = -3 → aligned"""
        method_a = 70 * 0.6 + min(4 / 4 * 100, 100) * 0.4 + 0
        assert method_a == 82.0
        r = reconcile_health_score(method_a, jqavg=70, score=4, fnet=100, max_score=4)
        assert r.within_tolerance
        assert r.reason == 'aligned'

    def test_typical_bear_market(self):
        """空頭情境:jqavg=20, score=1(max 4), fnet<0
        Method A: 20*0.6 + (1/4*100)*0.4 + 0 = 12 + 10 = 22
        Method B: (20 + 25)/2 = 22.5
        diff = -0.5 → aligned"""
        method_a = 20 * 0.6 + min(1 / 4 * 100, 100) * 0.4 + 0
        assert method_a == 22.0
        r = reconcile_health_score(method_a, jqavg=20, score=1, fnet=-100, max_score=4)
        assert r.within_tolerance

    def test_components_disagree_flags_drift(self):
        """兩組件打架(廣度高、分數 0)→ A/B 權重差放大 → drift 提示(有效訊號)。
        A: 90*0.6 + 0 = 54;B: (90+0)/2 = 45 → diff 9 > 5 → drift_warning"""
        method_a = 90 * 0.6 + 0.0
        r = reconcile_health_score(method_a, jqavg=90, score=0, fnet=0, max_score=4)
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
        # B=67.5;A=50 → diff 17.5:tol 5 → warning;tol 30 → aligned
        r_strict = reconcile_health_score(50.0, jqavg=60, score=3, fnet=50, tolerance=5.0)
        assert not r_strict.within_tolerance
        r_loose = reconcile_health_score(50.0, jqavg=60, score=3, fnet=50, tolerance=30.0)
        assert r_loose.within_tolerance
