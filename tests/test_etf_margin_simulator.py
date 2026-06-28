"""test_etf_margin_simulator.py — v18.162 ETF 質借模擬器驗收."""
from __future__ import annotations

import pandas as pd
import pytest

from src.compute.etf import (
    LEVERAGE_PRESETS,
    LIQUIDATION_RATIO,
    MARGIN_CALL_RATIO,
    PHASE_RECOMMENDATION,
    SimulationParams,
    _compute_maintenance_ratio,
    get_preset,
    result_to_dataframe,
    simulate_margin_strategy,
)

EXPECTED_PRESETS = ["conservative", "balanced", "aggressive", "extreme"]
EXPECTED_PHASES = ["復甦 Recovery", "過熱 Overheat",
                   "停滯 Stagflation", "衰退 Recession"]


class TestPresetStructure:
    def test_four_presets_exist(self):
        assert set(LEVERAGE_PRESETS.keys()) == set(EXPECTED_PRESETS)

    @pytest.mark.parametrize("key", EXPECTED_PRESETS)
    def test_preset_has_label_desc_triggers(self, key):
        p = LEVERAGE_PRESETS[key]
        assert "label" in p and p["label"]
        assert "desc" in p and p["desc"]
        assert "triggers" in p
        assert len(p["triggers"]) == 3

    @pytest.mark.parametrize("key", EXPECTED_PRESETS)
    def test_triggers_have_drawdown_and_leverage(self, key):
        for trig in LEVERAGE_PRESETS[key]["triggers"]:
            assert "drawdown_pct" in trig and trig["drawdown_pct"] > 0
            assert "leverage_add_pct" in trig and trig["leverage_add_pct"] > 0

    @pytest.mark.parametrize("key", EXPECTED_PRESETS)
    def test_drawdown_monotonic_increasing(self, key):
        """倒金字塔：drawdown_pct 必須 L1 < L2 < L3。"""
        dds = [t["drawdown_pct"] for t in LEVERAGE_PRESETS[key]["triggers"]]
        assert dds == sorted(dds), f"{key} drawdown 非單調遞增：{dds}"
        assert len(set(dds)) == len(dds), f"{key} drawdown 有重複"

    @pytest.mark.parametrize("key", EXPECTED_PRESETS)
    def test_leverage_monotonic_increasing(self, key):
        """倒金字塔：加碼幅度 L1 < L2 < L3（跌越深加越多）。"""
        leveraged = [t["leverage_add_pct"]
                     for t in LEVERAGE_PRESETS[key]["triggers"]]
        assert leveraged == sorted(leveraged), \
            f"{key} leverage 非單調遞增：{leveraged}"

    def test_extreme_more_aggressive_than_conservative(self):
        cons_total = sum(t["leverage_add_pct"]
                         for t in LEVERAGE_PRESETS["conservative"]["triggers"])
        extr_total = sum(t["leverage_add_pct"]
                         for t in LEVERAGE_PRESETS["extreme"]["triggers"])
        assert extr_total > cons_total * 2, \
            f"極限總槓桿應 > 保守 ×2（cons={cons_total} / extr={extr_total}）"

    def test_phase_recommendation_covers_four(self):
        assert set(PHASE_RECOMMENDATION.keys()) == set(EXPECTED_PHASES)
        for rec in PHASE_RECOMMENDATION.values():
            assert rec in EXPECTED_PRESETS

    def test_recovery_recommends_aggressive(self):
        """谷底反轉應推薦積極（最大化反彈報酬）。"""
        assert PHASE_RECOMMENDATION["復甦 Recovery"] == "aggressive"


class TestGetPreset:
    @pytest.mark.parametrize("key", EXPECTED_PRESETS)
    def test_returns_dict(self, key):
        p = get_preset(key)
        assert isinstance(p, dict)
        assert "triggers" in p

    def test_unknown_raises(self):
        with pytest.raises(KeyError, match="未知 preset_key"):
            get_preset("nonexistent")

    def test_deep_copy_does_not_mutate_source(self):
        """確認回傳是 deep copy；污染不應回流到 LEVERAGE_PRESETS。"""
        original_first_dd = LEVERAGE_PRESETS["balanced"]["triggers"][0]["drawdown_pct"]
        p = get_preset("balanced")
        p["triggers"][0]["drawdown_pct"] = 999
        assert LEVERAGE_PRESETS["balanced"]["triggers"][0]["drawdown_pct"] == original_first_dd


class TestMaintenanceRatioFormula:
    def test_no_borrowing_returns_999(self):
        assert _compute_maintenance_ratio(100, 50, 1000, 0) == 999.0

    def test_full_collateral_above_margin_call(self):
        # shares*price + cash = 200_000；borrowed = 100_000 → 200%
        assert _compute_maintenance_ratio(1000, 200, 0, 100_000) == 200.0

    def test_below_margin_call_threshold(self):
        # shares*price = 135_000；borrowed = 100_000 → 135% < 140%
        r = _compute_maintenance_ratio(1000, 135, 0, 100_000)
        assert r == 135.0
        assert r < MARGIN_CALL_RATIO

    def test_below_liquidation_threshold(self):
        # 125_000 / 100_000 = 125% < 130%
        r = _compute_maintenance_ratio(1000, 125, 0, 100_000)
        assert r == 125.0
        assert r < LIQUIDATION_RATIO


class TestSimulationFlatPrice:
    """價格不動：應一檔都不觸發，借款 = 0、總報酬 ≈ 0。"""

    def test_flat_no_trigger(self):
        series = pd.Series([100.0] * 30,
                           index=pd.date_range("2024-01-01", periods=30))
        result = simulate_margin_strategy(
            series, SimulationParams(preset_key="balanced",
                                     initial_capital=1_000_000))
        assert result.triggered_levels == []
        assert result.margin_call_count == 0
        assert result.liquidation_count == 0
        assert abs(result.total_return_pct) < 1e-6
        assert result.daily[-1].borrowed == 0.0


class TestSimulationVShape:
    """V 型回測：價 100 → 70（-30%）→ 100，平衡 preset 應觸發 3 階。"""

    def _v_series(self):
        prices = [100, 95, 90, 85, 80, 75, 70, 75, 80, 85, 90, 95, 100]
        return pd.Series(prices,
                         index=pd.date_range("2024-01-01", periods=len(prices)))

    def test_v_shape_triggers_three_levels(self):
        result = simulate_margin_strategy(
            self._v_series(),
            SimulationParams(preset_key="balanced", initial_capital=1_000_000))
        assert result.triggered_levels == [0, 1, 2], \
            f"V 型應觸發全部 3 階，實際 {result.triggered_levels}"

    def test_v_shape_final_borrowed_is_sum_of_loans(self):
        """3 階 balanced：10% + 20% + 30% = 60 萬借款。"""
        result = simulate_margin_strategy(
            self._v_series(),
            SimulationParams(preset_key="balanced", initial_capital=1_000_000))
        final = result.daily[-1]
        assert final.borrowed == pytest.approx(600_000.0)

    def test_v_shape_recovery_gains_leverage_profit(self):
        """V 型完全回升：總報酬應 > 0（槓桿放大反彈獲利）。"""
        result = simulate_margin_strategy(
            self._v_series(),
            SimulationParams(preset_key="balanced", initial_capital=1_000_000))
        assert result.total_return_pct > 0


class TestLiquidationOn2008Crash:
    """2008 風暴模擬：價跌 70% 仍持續，極限 preset 該強平。"""

    def _crash_series(self):
        prices = [100 * (1 - 0.7 * i / 30) for i in range(31)]  # 100 → 30
        return pd.Series(prices,
                         index=pd.date_range("2008-01-01", periods=len(prices)))

    def test_extreme_preset_gets_liquidated(self):
        result = simulate_margin_strategy(
            self._crash_series(),
            SimulationParams(preset_key="extreme", initial_capital=1_000_000))
        assert result.liquidation_count >= 1, \
            "70% 暴跌極限 preset 應至少強平 1 次"

    def test_conservative_preset_survives_better(self):
        """保守 preset 比極限的爆倉機率小（總槓桿小）。"""
        cons_r = simulate_margin_strategy(
            self._crash_series(),
            SimulationParams(preset_key="conservative",
                             initial_capital=1_000_000))
        extr_r = simulate_margin_strategy(
            self._crash_series(),
            SimulationParams(preset_key="extreme",
                             initial_capital=1_000_000))
        # 兩者都可能爆倉，但保守的次數應 ≤ 極限的次數
        assert cons_r.liquidation_count <= extr_r.liquidation_count


class TestSimulationEdgeCases:
    def test_empty_series_returns_empty_result(self):
        series = pd.Series([], dtype=float)
        result = simulate_margin_strategy(
            series, SimulationParams(preset_key="balanced"))
        assert result.daily == []
        assert result.total_return_pct == 0.0

    def test_single_day_no_trigger(self):
        series = pd.Series([100.0],
                           index=pd.date_range("2024-01-01", periods=1))
        result = simulate_margin_strategy(
            series, SimulationParams(preset_key="balanced"))
        assert len(result.daily) == 1
        assert result.daily[0].borrowed == 0.0

    def test_negative_initial_price_returns_empty(self):
        series = pd.Series([-100.0, 50.0],
                           index=pd.date_range("2024-01-01", periods=2))
        result = simulate_margin_strategy(
            series, SimulationParams(preset_key="balanced"))
        assert result.daily == []

    def test_only_first_level_triggers_at_shallow_drop(self):
        """跌 7%（在 balanced L1 5% 之上但 < L2 10%）只應觸發 L1。"""
        prices = [100, 97, 95, 93, 93, 93, 93]
        series = pd.Series(prices,
                           index=pd.date_range("2024-01-01", periods=len(prices)))
        result = simulate_margin_strategy(
            series, SimulationParams(preset_key="balanced"))
        assert result.triggered_levels == [0]


class TestResultDataFrame:
    def test_dataframe_columns(self):
        series = pd.Series([100, 95, 90],
                           index=pd.date_range("2024-01-01", periods=3))
        result = simulate_margin_strategy(
            series, SimulationParams(preset_key="balanced"))
        df = result_to_dataframe(result)
        expected = {"date", "price", "hwm", "drawdown_pct", "shares",
                    "cash", "borrowed", "equity", "maintenance_ratio",
                    "status", "event"}
        assert expected.issubset(set(df.columns))
        assert len(df) == 3

    def test_empty_result_dataframe(self):
        result = simulate_margin_strategy(
            pd.Series([], dtype=float),
            SimulationParams(preset_key="balanced"))
        df = result_to_dataframe(result)
        assert len(df) == 0


class TestSimulationParamsImmutability:
    def test_frozen(self):
        p = SimulationParams(preset_key="balanced")
        with pytest.raises(Exception):
            p.preset_key = "extreme"  # type: ignore
