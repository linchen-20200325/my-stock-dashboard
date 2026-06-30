"""test_portfolio_manager_coverage.py — CoreSatelliteManager 單元測試。

對應 src/compute/strategy/portfolio_manager.py（L2 純 compute,核心衛星動態配資引擎）。
涵蓋 deterministic 純函式面:
- __init__ regime → core/satellite ratio + override + invalid capital
- core_budget / satellite_budget rounding
- check_rebalance 三態（HOLD / MONITOR / SELL_EXCESS）+ 不變量
- calc_position（正常/額度不足/股價無效/rounding/zero weight）
- summary 結構

全部 crafted in-memory inputs,無 I/O,無網路。
"""
from __future__ import annotations

import math

import pytest

from src.compute.strategy.portfolio_manager import CoreSatelliteManager


class TestInit:
    def test_bull_regime_ratios(self):
        m = CoreSatelliteManager(1_000_000, 'bull')
        assert m.core_ratio == 0.60
        assert m.satellite_ratio == 0.40

    def test_neutral_regime_ratios(self):
        m = CoreSatelliteManager(1_000_000, 'neutral')
        assert m.core_ratio == 0.70
        assert m.satellite_ratio == pytest.approx(0.30)

    def test_bear_regime_ratios(self):
        m = CoreSatelliteManager(1_000_000, 'bear')
        assert m.core_ratio == 0.85
        assert m.satellite_ratio == pytest.approx(0.15)

    def test_unknown_regime_defaults_to_70(self):
        # _CORE_RATIO.get(regime, 0.70) → 未知 regime 退回 0.70
        m = CoreSatelliteManager(1_000_000, 'whatever')
        assert m.core_ratio == 0.70
        assert m.satellite_ratio == pytest.approx(0.30)

    def test_core_ratio_override_wins_over_regime(self):
        # override 0.5 應壓過 bull(0.6)
        m = CoreSatelliteManager(1_000_000, 'bull', core_ratio_override=0.5)
        assert m.core_ratio == 0.5
        assert m.satellite_ratio == 0.5

    def test_ratios_sum_to_one(self):
        # 核心 + 衛星 = 1.0 不變量（rounding 後仍應 ≈ 1）
        for regime in ('bull', 'neutral', 'caution', 'bear'):
            m = CoreSatelliteManager(1_000_000, regime)
            assert math.isclose(m.core_ratio + m.satellite_ratio, 1.0, abs_tol=1e-9)

    def test_zero_capital_raises(self):
        with pytest.raises(ValueError):
            CoreSatelliteManager(0, 'bull')

    def test_negative_capital_raises(self):
        with pytest.raises(ValueError):
            CoreSatelliteManager(-100, 'bull')


class TestBudgets:
    def test_core_and_satellite_budget_split(self):
        m = CoreSatelliteManager(1_000_000, 'bull')  # 0.6 / 0.4
        assert m.core_budget == 600_000.0
        assert m.satellite_budget == 400_000.0

    def test_budget_rounding_to_whole_units(self):
        # 333,333 * 0.7 = 233,333.1 → round(,0) = 233333.0
        m = CoreSatelliteManager(333_333, 'neutral')
        assert m.core_budget == round(333_333 * 0.70, 0)
        assert m.satellite_budget == round(333_333 * 0.30, 0)


class TestCheckRebalance:
    def test_sell_excess_well_past_threshold(self):
        # satellite 0.55 vs target 0.4 → excess 0.15 >> 0.10 → SELL_EXCESS
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.check_rebalance(550_000)
        assert r['rebalance_needed'] is True
        assert r['action'] == 'SELL_EXCESS'
        assert r['actual_ratio'] == 0.55
        assert r['target_ratio'] == 0.4
        assert r['excess_pct'] == pytest.approx(15.0)
        assert r['excess_value'] == 150_000.0

    def test_monitor_above_target_below_threshold(self):
        # satellite 0.45 vs target 0.4 → excess 0.05 < 0.10 → MONITOR
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.check_rebalance(450_000)
        assert r['rebalance_needed'] is False
        assert r['action'] == 'MONITOR'
        assert r['excess_pct'] == pytest.approx(5.0)

    def test_hold_at_or_below_target(self):
        # satellite 0.40 == target → HOLD
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.check_rebalance(400_000)
        assert r['rebalance_needed'] is False
        assert r['action'] == 'HOLD'

    def test_hold_below_target(self):
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.check_rebalance(300_000)  # 0.30 < 0.40
        assert r['action'] == 'HOLD'
        assert r['excess_pct'] == pytest.approx(-10.0)

    def test_zero_satellite_value_holds(self):
        # 空持股 → actual_ratio 0 → HOLD,不爆
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.check_rebalance(0.0)
        assert r['action'] == 'HOLD'
        assert r['actual_ratio'] == 0.0


class TestCalcPosition:
    def test_normal_buy(self):
        # satellite_budget 400k, weight 0.25 → budget 100k, price 100 → 1000 股 / 1 張
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.calc_position(price=100.0, weight=0.25)
        assert r['shares'] == 1000
        assert r['lots'] == 1
        assert r['cost'] == 100_000.0
        assert r['budget'] == 100_000.0
        assert r['remaining'] == 300_000.0

    def test_invalid_price_returns_zero_position(self):
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.calc_position(price=0.0, weight=0.25)
        assert r['shares'] == 0
        assert r['lots'] == 0
        assert r['cost'] == 0.0
        assert '股價無效' in r['message']

    def test_negative_price_returns_zero_position(self):
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.calc_position(price=-50.0, weight=0.25)
        assert r['shares'] == 0

    def test_zero_weight_yields_no_shares(self):
        # weight 0 → budget 0 → shares 0 → 額度不足訊息
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.calc_position(price=100.0, weight=0.0)
        assert r['shares'] == 0
        assert r['lots'] == 0
        assert '無法建倉' in r['message']

    def test_satellite_used_exhausts_budget(self):
        # 已用滿衛星額度 → available 被 max(...,0) clamp 至 0 → 0 股
        m = CoreSatelliteManager(1_000_000, 'bull')  # satellite_budget 400k
        r = m.calc_position(price=100.0, weight=0.25, satellite_used=400_000)
        assert r['shares'] == 0
        assert '無法建倉' in r['message']

    def test_share_rounding_floors_partial_shares(self):
        # budget 100k / price 333 → 300.30... → floor 300 股
        m = CoreSatelliteManager(1_000_000, 'bull')
        r = m.calc_position(price=333.0, weight=0.25)
        assert r['shares'] == 300  # 100000 // 333 = 300
        assert r['lots'] == 0       # 300 // 1000 = 0
        assert r['cost'] == round(300 * 333.0, 0)

    def test_weight_capped_at_full_available(self):
        # weight > 1 → budget = min(available*weight, available) = available
        m = CoreSatelliteManager(1_000_000, 'bull')  # satellite_budget 400k
        r = m.calc_position(price=100.0, weight=2.0)
        # budget clamps to 400k → 4000 股 / 4 張
        assert r['budget'] == 400_000.0
        assert r['shares'] == 4000
        assert r['lots'] == 4


class TestSummary:
    def test_summary_structure_and_values(self):
        m = CoreSatelliteManager(1_000_000, 'bull')
        s = m.summary(satellite_current_value=550_000)
        assert s['total'] == 1_000_000.0
        assert s['core_budget'] == 600_000.0
        assert s['satellite_budget'] == 400_000.0
        assert s['core_ratio'] == 0.60
        assert s['satellite_ratio'] == 0.40
        assert s['regime'] == 'bull'
        # 內嵌 rebalance 與 check_rebalance 一致(0.55 >> threshold → SELL_EXCESS)
        assert s['rebalance']['action'] == 'SELL_EXCESS'

    def test_summary_default_zero_satellite(self):
        m = CoreSatelliteManager(1_000_000, 'neutral')
        s = m.summary()
        assert s['rebalance']['action'] == 'HOLD'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
