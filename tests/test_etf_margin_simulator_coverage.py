"""tests/test_etf_margin_simulator_coverage.py — D.測試覆蓋 #11-19。

對應 src/compute/etf/etf_margin_simulator.py(L2 純 compute 質借倒金字塔模擬器)。

涵蓋:
- 常數 SSOT(MARGIN_CALL_RATIO=140 / LIQUIDATION_RATIO=130)
- get_preset:deep copy 隔離 + 未知 key raise KeyError(§1 fail loud)
- _compute_maintenance_ratio:borrowed=0 → 999 哨兵 + 正常公式 + 零除防護
- simulate_margin_strategy:空/None/零初始價 邊界 + Day0 全押 + 倒金字塔觸發
  + 追繳(margin_call)/強平(liquidated)門檻 + 單日只觸發一 level
- SimulationResult properties:final_equity / total_return_pct / max_drawdown_pct
  / avg_leverage_ratio(空集 + 無借款日不計入)
- result_to_dataframe 欄位契約
"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from src.compute.etf.etf_margin_simulator import (
    LEVERAGE_PRESETS,
    LIQUIDATION_RATIO,
    MARGIN_CALL_RATIO,
    PHASE_RECOMMENDATION,
    SimulationParams,
    SimulationResult,
    _compute_maintenance_ratio,
    get_preset,
    result_to_dataframe,
    simulate_margin_strategy,
)


def _series(prices, start="2026-01-01"):
    idx = pd.date_range(start=start, periods=len(prices), freq="D")
    return pd.Series([float(p) for p in prices], index=idx)


# ─────────────────────────── 常數 SSOT ───────────────────────────
class TestThresholdConstants:
    def test_margin_call_and_liquidation_values(self):
        # 台股保守實務值,本功能 SSOT
        assert MARGIN_CALL_RATIO == 140.0
        assert LIQUIDATION_RATIO == 130.0

    def test_call_above_liquidation(self):
        # 追繳門檻必須高於強平門檻(否則邏輯顛倒)
        assert MARGIN_CALL_RATIO > LIQUIDATION_RATIO

    def test_default_params_inherit_constants(self):
        p = SimulationParams(preset_key="balanced")
        assert p.margin_call_ratio == MARGIN_CALL_RATIO
        assert p.liquidation_ratio == LIQUIDATION_RATIO
        assert p.initial_capital == 1_000_000.0

    def test_phase_recommendation_keys_map_to_real_presets(self):
        # 每個景氣階段推薦的 preset 必須真實存在
        for phase, preset_key in PHASE_RECOMMENDATION.items():
            assert preset_key in LEVERAGE_PRESETS, phase


# ─────────────────────────── get_preset ───────────────────────────
class TestGetPreset:
    def test_known_keys_return_triggers(self):
        for key in ("conservative", "balanced", "aggressive", "extreme"):
            preset = get_preset(key)
            assert len(preset["triggers"]) == 3
            assert "label" in preset

    def test_unknown_key_raises_keyerror(self):
        # §1 fail loud:未知 preset 必須炸,不可靜默回 default
        with pytest.raises(KeyError):
            get_preset("nonexistent")

    def test_returns_deep_copy_not_shared_ref(self):
        # 呼叫端污染回傳值不可影響原表
        preset = get_preset("balanced")
        preset["triggers"][0]["drawdown_pct"] = 999
        assert LEVERAGE_PRESETS["balanced"]["triggers"][0]["drawdown_pct"] == 5


# ─────────────────── _compute_maintenance_ratio ───────────────────
class TestMaintenanceRatio:
    def test_zero_borrowed_returns_sentinel_999(self):
        # borrowed<=0 → 999 哨兵(無借款 = 維持率無限大)
        assert _compute_maintenance_ratio(shares=10, price=100, cash=0, borrowed=0) == 999.0

    def test_negative_borrowed_also_sentinel(self):
        assert _compute_maintenance_ratio(shares=10, price=100, cash=0, borrowed=-5) == 999.0

    def test_basic_formula(self):
        # (shares*price + cash) / borrowed * 100 = (10*20 + 0)/100*100 = 200
        assert _compute_maintenance_ratio(shares=10, price=20, cash=0, borrowed=100) == pytest.approx(200.0)

    def test_cash_included_in_collateral(self):
        # 現金計入擔保品:(10*20 + 50)/100*100 = 250
        assert _compute_maintenance_ratio(shares=10, price=20, cash=50, borrowed=100) == pytest.approx(250.0)


# ───────────────────── simulate edge cases ─────────────────────
class TestSimulateEdgeCases:
    def test_empty_series_returns_empty_result(self):
        r = simulate_margin_strategy(_series([]), SimulationParams(preset_key="balanced"))
        assert r.daily == []
        assert r.margin_call_count == 0
        assert r.liquidation_count == 0

    def test_none_series_returns_empty_result(self):
        r = simulate_margin_strategy(None, SimulationParams(preset_key="balanced"))
        assert r.daily == []

    def test_zero_initial_price_returns_empty(self):
        # 初始價 <= 0 無法計算持股 → 安全回空(不 ÷0)
        r = simulate_margin_strategy(_series([0.0, 100.0]), SimulationParams(preset_key="balanced"))
        assert r.daily == []

    def test_single_row_day0_full_buy_no_borrow(self):
        # Day 0 全押:1,000,000 / 100 = 10000 股,無借款,equity = 本金
        r = simulate_margin_strategy(_series([100.0]), SimulationParams(preset_key="balanced"))
        assert len(r.daily) == 1
        d = r.daily[0]
        assert d.shares == pytest.approx(10000.0)
        assert d.borrowed == 0.0
        assert d.equity == pytest.approx(1_000_000.0)
        assert d.maintenance_ratio == 999.0  # 無借款
        assert d.status == "normal"


# ───────────────────── simulate core logic ─────────────────────
class TestSimulateLogic:
    def test_flat_price_no_trigger_no_borrow(self):
        # 價格不跌 → 不觸發任何加碼,報酬 0
        r = simulate_margin_strategy(_series([100.0, 100.0, 100.0]), SimulationParams(preset_key="balanced"))
        assert r.triggered_levels == []
        assert r.daily[-1].borrowed == 0.0
        assert r.total_return_pct == pytest.approx(0.0)
        assert r.avg_leverage_ratio == 0.0  # 無借款日 → 不計入

    def test_balanced_first_level_trigger(self):
        # balanced L1: drawdown>=5% → 借 initial*10% = 100,000
        # 100 → 94 = 6% 回撤,觸發 L0;加碼 100000/94 股
        r = simulate_margin_strategy(_series([100.0, 94.0]), SimulationParams(preset_key="balanced"))
        assert r.triggered_levels == [0]
        d = r.daily[-1]
        assert d.borrowed == pytest.approx(100_000.0)
        assert d.shares == pytest.approx(10000.0 + 100_000.0 / 94.0)
        assert d.status == "normal"  # 維持率仍遠高於 140

    def test_only_one_level_per_day(self):
        # 即使一天跌破多個門檻,單日只觸發一個 level(然後下一根 K 補)
        # balanced 門檻 5/10/20;直接跌到 75(25% dd)
        r = simulate_margin_strategy(_series([100.0, 75.0]), SimulationParams(preset_key="balanced"))
        # day2 只觸發 index 0(break 後跳出)
        assert r.daily[-1].event.count("觸發") == 1
        assert r.triggered_levels == [0]

    def test_levels_trigger_progressively_across_days(self):
        # 逐步加深的回撤 → 依序觸發 L1/L2/L3
        prices = [100.0, 94.0, 89.0, 79.0]  # dd 0/6/11/21 → 觸發 5/10/20 三檔
        r = simulate_margin_strategy(_series(prices), SimulationParams(preset_key="balanced"))
        assert r.triggered_levels == [0, 1, 2]

    def test_liquidation_on_catastrophic_crash(self):
        # extreme preset 重壓後暴跌 → 維持率 < 130% 強平
        prices = [100.0, 96.0, 92.0, 86.0, 50.0]
        r = simulate_margin_strategy(_series(prices), SimulationParams(preset_key="extreme"))
        last = r.daily[-1]
        assert last.status == "liquidated"
        assert r.liquidation_count == 1
        # 強平後賣光持股、清借款
        assert last.shares == 0.0
        assert last.borrowed == 0.0
        assert last.maintenance_ratio == 999.0  # reset 哨兵
        assert "強制平倉" in last.event

    def test_margin_call_status_recorded(self):
        # 構造一個落在 [130, 140) 區間的維持率 → margin_call 但不強平。
        # balanced: day2 100→94 觸發 L0(借 100,000);day3 跌到 19.75
        # (~80% dd)再觸發 L1(借 200,000)→ borrowed=300,000,
        # 維持率 ≈ 139.5% ∈ [130, 140) → margin_call(非 liquidated)。
        prices = [100.0, 94.0, 19.75]
        r = simulate_margin_strategy(_series(prices), SimulationParams(preset_key="balanced"))
        last = r.daily[-1]
        assert last.status == "margin_call"
        assert r.margin_call_count == 1
        assert r.liquidation_count == 0
        assert LIQUIDATION_RATIO <= last.maintenance_ratio < MARGIN_CALL_RATIO


# ───────────────────── result properties ─────────────────────
class TestResultProperties:
    def test_empty_result_properties_safe(self):
        r = SimulationResult(params=SimulationParams(preset_key="balanced"))
        assert r.final_equity == 0.0
        assert r.total_return_pct == 0.0
        assert r.max_drawdown_pct == 0.0
        assert r.avg_leverage_ratio == 0.0

    def test_total_return_pct_positive_on_recovery(self):
        # 跌後反彈超過起點:用 conservative 避免被強平,終值 > 本金
        # 100 → 90(觸發 L1 借 50000) → 130 反彈
        prices = [100.0, 90.0, 130.0]
        r = simulate_margin_strategy(_series(prices), SimulationParams(preset_key="conservative"))
        assert r.total_return_pct > 0.0
        assert r.final_equity > r.params.initial_capital

    def test_max_drawdown_pct_nonneg(self):
        prices = [100.0, 90.0, 130.0]
        r = simulate_margin_strategy(_series(prices), SimulationParams(preset_key="conservative"))
        assert r.max_drawdown_pct >= 0.0

    def test_avg_leverage_excludes_no_borrow_days(self):
        # day0 無借款不計入;有借款日才納入平均,結果為正
        prices = [100.0, 94.0, 95.0]
        r = simulate_margin_strategy(_series(prices), SimulationParams(preset_key="balanced"))
        assert r.avg_leverage_ratio > 0.0


# ───────────────────── result_to_dataframe ─────────────────────
class TestResultToDataframe:
    def test_columns_and_rows(self):
        r = simulate_margin_strategy(_series([100.0, 94.0]), SimulationParams(preset_key="balanced"))
        df = result_to_dataframe(r)
        expected = {
            "date", "price", "hwm", "drawdown_pct", "shares",
            "cash", "borrowed", "equity", "maintenance_ratio", "status", "event",
        }
        assert set(df.columns) == expected
        assert len(df) == len(r.daily) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
