"""test_multi_factor_optimization.py — v18.165 台股多因子權重最佳化引擎驗收.

鏡像 fund test_multi_factor_optimization.py（28 case）— 差異僅在：
- CrisisEvent → TwiiCrisisEvent（_mock_event 簽名 / 欄位）
- FACTOR_POOL 4 個（台股本地）而非 10 個（fund 國際）
- _mock_factor_series 用前 4 個 key（FACTOR_POOL[:4]）— 仍恰好全用上
- FACTOR_POOL_BY_KEY["FOREIGN_SELL_5D"].source == "local"
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from macro_validation_tw import TwiiCrisisEvent
from multi_factor_optimization import (
    FACTOR_POOL,
    FACTOR_POOL_BY_KEY,
    build_plateau_heatmap_2d,
    build_plateau_surface_3d,
    compute_composite_score,
    evaluate_f1,
    evaluate_plateau,
    evaluate_sharpe,
    find_plateau_optimum,
    generate_simplex_grid,
    grid_search_performance,
    score_to_signal,
    walk_forward_validate,
)


def _mock_event(peak: str) -> TwiiCrisisEvent:
    p = pd.Timestamp(peak)
    return TwiiCrisisEvent(
        peak_date=p,
        peak_close=100.0,
        trough_date=p + pd.Timedelta(days=60),
        trough_close=85.0,
        recovery_date=None,
        drawdown_pct=-0.15,
    )


def _mock_factor_series(n: int = 1500, seed: int = 1) -> dict[str, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq="D")
    out = {}
    for f in FACTOR_POOL[:4]:
        out[f.key] = pd.Series(rng.normal(0, 1, n).cumsum() / 10 + 20.0,
                               index=idx, name=f.key)
    return out


def _mock_returns(n: int = 1500, seed: int = 2) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq="D")
    price = 100 * (1 + rng.normal(0, 0.01, n)).cumprod()
    return pd.Series(price, index=idx, name="TWII")


class TestComputeCompositeScore:
    def test_empty_weights_raises(self):
        with pytest.raises(ValueError):
            compute_composite_score({}, {})

    def test_lag_prevents_future_leak(self):
        idx = pd.date_range("2020-01-01", periods=10, freq="D")
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
                      index=idx, name="MARGIN_BALANCE")
        score = compute_composite_score(
            {"MARGIN_BALANCE": s}, {"MARGIN_BALANCE": 1.0}, lag_days=1,
        )
        assert score.index[0] >= idx[1]

    def test_zero_weight_skipped(self):
        idx = pd.date_range("2020-01-01", periods=50, freq="D")
        s_a = pd.Series(np.arange(50, dtype=float), index=idx, name="MARGIN_BALANCE")
        s_b = pd.Series(np.arange(50, dtype=float) * 2, index=idx,
                        name="FOREIGN_SELL_5D")
        sc_one = compute_composite_score(
            {"MARGIN_BALANCE": s_a, "FOREIGN_SELL_5D": s_b},
            {"MARGIN_BALANCE": 1.0, "FOREIGN_SELL_5D": 0.0},
        )
        sc_two = compute_composite_score({"MARGIN_BALANCE": s_a},
                                          {"MARGIN_BALANCE": 1.0})
        assert np.allclose(sc_one.values, sc_two.values)

    def test_direction_below_flips_sign(self):
        # FOREIGN_SELL_5D is direction="below" → 高分代表「外資加大賣超」
        idx = pd.date_range("2020-01-01", periods=30, freq="D")
        s = pd.Series(np.arange(30, dtype=float), index=idx, name="FOREIGN_SELL_5D")
        sc = compute_composite_score(
            {"FOREIGN_SELL_5D": s}, {"FOREIGN_SELL_5D": 1.0},
        )
        assert sc.iloc[0] > sc.iloc[-1]


class TestScoreToSignal:
    def test_edge_detection_only_crossings(self):
        idx = pd.date_range("2020-01-01", periods=10, freq="D")
        score = pd.Series([0.5, 0.5, 1.5, 1.5, 0.5, 1.5, 1.5, 1.5, 0.5, 1.5],
                          index=idx)
        cross = score_to_signal(score, threshold=1.0)
        assert cross.sum() == 3
        assert cross.iloc[2] == 1 and cross.iloc[3] == 0


class TestEvaluateF1:
    def test_empty_returns_zero(self):
        stat = evaluate_f1(pd.Series(dtype=int), [])
        assert stat["f1"] == 0.0

    def test_no_crossings_returns_zero(self):
        idx = pd.date_range("2020-01-01", periods=10, freq="D")
        cross = pd.Series([0] * 10, index=idx)
        stat = evaluate_f1(cross, [_mock_event("2020-01-05")])
        assert stat["f1"] == 0.0

    def test_perfect_hit_gives_one(self):
        idx = pd.date_range("2020-01-01", periods=30, freq="D")
        cross = pd.Series([0] * 30, index=idx)
        cross.iloc[0] = 1
        stat = evaluate_f1(cross, [_mock_event("2020-01-10")],
                           max_forward_days=30)
        assert stat["precision"] == 1.0
        assert stat["recall"] == 1.0
        assert stat["f1"] == 1.0


class TestEvaluateSharpe:
    def test_empty_returns_zero(self):
        stat = evaluate_sharpe(pd.Series(dtype=int), pd.Series(dtype=float))
        assert stat["sharpe"] == 0.0

    def test_no_trades_returns_zero(self):
        idx = pd.date_range("2020-01-01", periods=100, freq="D")
        cross = pd.Series([0] * 100, index=idx)
        ret = pd.Series(np.random.default_rng(0).normal(100, 1, 100), index=idx)
        stat = evaluate_sharpe(cross, ret)
        assert stat["n_trades"] == 0


class TestGenerateSimplexGrid:
    def test_2d_step_05_gives_3_points(self):
        combos = generate_simplex_grid(["A", "B"], step=0.5)
        assert len(combos) == 3
        assert all(abs(sum(w.values()) - 1.0) < 1e-9 for w in combos)

    def test_3d_step_05_gives_6_points(self):
        combos = generate_simplex_grid(["A", "B", "C"], step=0.5)
        assert len(combos) == 6
        assert all(abs(sum(w.values()) - 1.0) < 1e-9 for w in combos)

    def test_empty_keys_returns_empty(self):
        assert generate_simplex_grid([], 0.2) == []

    def test_invalid_step_returns_empty(self):
        assert generate_simplex_grid(["A"], step=0) == []
        assert generate_simplex_grid(["A"], step=2.0) == []


class TestGridSearchPerformance:
    def test_empty_factors_returns_empty(self):
        result = grid_search_performance({}, pd.Series(dtype=float), [], [],
                                          step=0.5)
        assert len(result["combos"]) == 0

    def test_basic_run_has_combos(self):
        factor_series = _mock_factor_series(500)
        returns = _mock_returns(500)
        events = [_mock_event(str((pd.Timestamp("2018-06-01")
                                    + pd.Timedelta(days=i * 100)).date()))
                  for i in range(3)]
        result = grid_search_performance(
            factor_series, returns, events,
            ["FOREIGN_SELL_5D", "MARGIN_BALANCE"], step=0.5,
        )
        assert len(result["combos"]) == 3
        assert result["f1"].shape == (3,)
        assert result["sharpe"].shape == (3,)


class TestEvaluatePlateau:
    def test_empty_returns_empty(self):
        result = {"combos": [], "f1": np.array([]), "sharpe": np.array([]),
                  "n_crossings": np.array([])}
        plateau = evaluate_plateau(result, [], 0.5)
        assert len(plateau) == 0

    def test_flat_perf_gives_constant_plateau(self):
        combos = [{"A": 1.0, "B": 0.0},
                  {"A": 0.5, "B": 0.5},
                  {"A": 0.0, "B": 1.0}]
        f1 = np.array([0.6, 0.6, 0.6])
        result = {"combos": combos, "f1": f1, "sharpe": f1.copy(),
                  "n_crossings": np.array([10, 10, 10])}
        plateau = evaluate_plateau(result, ["A", "B"], step=0.5, radius=1,
                                   lambda_std=0.5)
        assert np.allclose(plateau, 0.6, atol=1e-9)


class TestFindPlateauOptimum:
    def test_empty_returns_zero(self):
        result = {"combos": [], "f1": np.array([]), "sharpe": np.array([]),
                  "n_crossings": np.array([])}
        opt = find_plateau_optimum(result, np.array([]))
        assert opt["argmax_idx"] == -1

    def test_returns_argmax(self):
        combos = [{"A": 1.0}, {"A": 0.5}, {"A": 0.0}]
        result = {"combos": combos, "f1": np.array([0.1, 0.5, 0.2]),
                  "sharpe": np.array([0, 0, 0]),
                  "n_crossings": np.array([1, 1, 1])}
        opt = find_plateau_optimum(result, np.array([0.1, 0.7, 0.2]))
        assert opt["argmax_idx"] == 1
        assert opt["weights"] == {"A": 0.5}


class TestWalkForwardValidate:
    def test_no_factors_returns_empty(self):
        result = walk_forward_validate({}, pd.Series(dtype=float), [], [])
        assert result["n_folds"] == 0
        assert result["status"] == "no_factors"

    def test_window_larger_than_data_returns_empty(self):
        idx = pd.date_range("2020-01-01", periods=30, freq="D")
        s = pd.Series(np.arange(30, dtype=float), index=idx, name="MARGIN_BALANCE")
        result = walk_forward_validate(
            {"MARGIN_BALANCE": s}, pd.Series(dtype=float), [],
            ["MARGIN_BALANCE"],
            train_months=12, test_months=6, step=0.5,
        )
        assert result["status"] == "window_larger_than_data"

    def test_basic_walk_forward_produces_folds(self):
        factor_series = _mock_factor_series(1500)
        returns = _mock_returns(1500)
        events = [_mock_event(str((pd.Timestamp("2019-06-01")
                                    + pd.Timedelta(days=i * 180)).date()))
                  for i in range(5)]
        result = walk_forward_validate(
            factor_series, returns, events,
            ["FOREIGN_SELL_5D", "MARGIN_BALANCE"],
            train_months=12, test_months=6, step=0.5,
        )
        assert result["n_folds"] >= 1
        for fold in result["folds"]:
            assert sum(fold["weights"].values()) == pytest.approx(1.0, abs=1e-9)


class TestPlotlyFigures:
    def test_2d_heatmap_returns_figure(self):
        combos = [{"A": 1.0, "B": 0.0},
                  {"A": 0.5, "B": 0.5},
                  {"A": 0.0, "B": 1.0}]
        result = {"combos": combos, "f1": np.array([0.3, 0.5, 0.4]),
                  "sharpe": np.array([0, 0, 0]),
                  "n_crossings": np.array([1, 1, 1])}
        fig = build_plateau_heatmap_2d(result, np.array([0.3, 0.5, 0.4]),
                                       ["A", "B"], ("A", "B"))
        assert fig is not None
        assert len(fig.data) == 1

    def test_3d_surface_returns_figure(self):
        combos = [{"A": 1.0, "B": 0.0},
                  {"A": 0.5, "B": 0.5},
                  {"A": 0.0, "B": 1.0}]
        result = {"combos": combos, "f1": np.array([0.3, 0.5, 0.4]),
                  "sharpe": np.array([0, 0, 0]),
                  "n_crossings": np.array([1, 1, 1])}
        fig = build_plateau_surface_3d(result, np.array([0.3, 0.5, 0.4]),
                                       ["A", "B"], ("A", "B"))
        assert fig is not None
        assert len(fig.data) == 1


class TestFactorPool:
    def test_pool_size(self):
        # v18.168：4 原始訊號 + 3 衍生因子（TWSE_VOL_RATIO / MARGIN_GROWTH_5D / TWII_REALIZED_VOL_20D）
        assert len(FACTOR_POOL) == 7

    def test_keys_unique(self):
        keys = [f.key for f in FACTOR_POOL]
        assert len(set(keys)) == len(keys)

    def test_lookup_by_key(self):
        # 台股訊號全來自本地 Parquet（macro_signal_lookback_tw）
        assert FACTOR_POOL_BY_KEY["FOREIGN_SELL_5D"].source == "local"


class TestV18_168NewFactors:
    """v18.168：3 個 parquet 衍生因子 metadata 驗證."""

    def test_twse_vol_ratio_present(self):
        assert "TWSE_VOL_RATIO" in FACTOR_POOL_BY_KEY
        spec = FACTOR_POOL_BY_KEY["TWSE_VOL_RATIO"]
        assert spec.source == "local"
        assert spec.direction == "above"

    def test_margin_growth_5d_present(self):
        assert "MARGIN_GROWTH_5D" in FACTOR_POOL_BY_KEY
        spec = FACTOR_POOL_BY_KEY["MARGIN_GROWTH_5D"]
        assert spec.source == "local"
        assert spec.direction == "above"

    def test_twii_realized_vol_20d_present(self):
        assert "TWII_REALIZED_VOL_20D" in FACTOR_POOL_BY_KEY
        spec = FACTOR_POOL_BY_KEY["TWII_REALIZED_VOL_20D"]
        assert spec.source == "local"
        assert spec.direction == "above"

    def test_all_new_factors_in_registry(self):
        """3 個新 key 都要在 TW_SIGNAL_FETCHERS registry 內可路由."""
        from macro_signal_lookback_tw import TW_SIGNAL_FETCHERS
        for key in ("TWSE_VOL_RATIO", "MARGIN_GROWTH_5D", "TWII_REALIZED_VOL_20D"):
            assert key in TW_SIGNAL_FETCHERS, f"{key} 未註冊 TW_SIGNAL_FETCHERS"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
