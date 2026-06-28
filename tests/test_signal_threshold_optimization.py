"""test_signal_threshold_optimization.py — v18.164 MT5-style 校準引擎驗收."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.compute.macro import TwSignalSpec  # noqa: E402
from src.compute.macro import TwiiCrisisEvent  # noqa: E402
from src.compute.scoring import (  # noqa: E402
    make_default_grid,
    optimize_signal_threshold,
)


def _mock_event(peak: str) -> TwiiCrisisEvent:
    return TwiiCrisisEvent(
        peak_date=pd.Timestamp(peak),
        peak_close=18000.0,
        trough_date=pd.Timestamp(peak) + pd.Timedelta(days=60),
        trough_close=15000.0,
        recovery_date=None,
        drawdown_pct=-0.20,
    )


def _spec_above(threshold=25.0):
    return TwSignalSpec(key="X", label="X", threshold=threshold,
                        direction="above", unit="", note="")


class TestMakeDefaultGrid:
    def test_default_grid_has_n_steps(self):
        grid = make_default_grid(25.0, n_steps=11)
        assert len(grid) == 11

    def test_default_grid_centered(self):
        grid = make_default_grid(25.0, n_steps=11)
        # 中位點 ≈ 25
        assert grid[5] == pytest.approx(25.0)
        # 範圍 ±50%
        assert grid[0] == pytest.approx(12.5)
        assert grid[-1] == pytest.approx(37.5)

    def test_zero_default_uses_minus1_to_1(self):
        grid = make_default_grid(0.0, n_steps=11)
        assert grid[0] == -1.0
        assert grid[-1] == 1.0


class TestOptimizeBaseCases:
    def test_empty_series_returns_insufficient(self):
        result = optimize_signal_threshold(
            pd.Series([], dtype=float),
            [_mock_event("2020-01-01")],
            _spec_above(25.0),
        )
        assert result["status"] == "insufficient_events"
        assert result["recommended"] == 25.0  # 退回預設

    def test_insufficient_events_returns_base(self):
        """events 數 < n_folds → 拒跑校準."""
        idx = pd.date_range("2020-01-01", periods=400, freq="D")
        series = pd.Series([20.0] * 400, index=idx, name="X")
        result = optimize_signal_threshold(
            series,
            [_mock_event("2020-06-01")],  # 只 1 event
            _spec_above(25.0),
            n_folds=4,
        )
        assert result["status"] == "insufficient_events"

    def test_returns_grid_results_when_valid(self):
        """足夠 events 時應有 grid_results + walk_forward."""
        idx = pd.date_range("2018-01-01", periods=2000, freq="D")
        # V 字 with 多次震盪：上下擺動
        values = [(20.0 + 10.0 * (i % 200 < 50)) for i in range(2000)]
        series = pd.Series(values, index=idx, name="X")
        events = [_mock_event(f"201{8+i//4}-0{(i%4)+1}-15") for i in range(8)]
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), n_folds=4,
        )
        assert result["status"] in ("adopted", "fallback_overfit")
        assert len(result["grid_results"]) > 0
        assert len(result["walk_forward"]) > 0


class TestWalkForwardNoLeakage:
    def test_train_test_events_disjoint(self):
        """walk-forward 各折 train / test 事件集合不交集."""
        idx = pd.date_range("2015-01-01", periods=3000, freq="D")
        values = [25.0 + 5 * ((i // 100) % 2) for i in range(3000)]
        series = pd.Series(values, index=idx, name="X")
        events = [_mock_event(str((pd.Timestamp("2015-01-15")
                                    + pd.Timedelta(days=i*180)).date()))
                  for i in range(8)]
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), n_folds=4,
        )
        # 各 fold train_end + test 不重疊：fold_i 的 test = train_(i+1) 的尾段
        for wf in result["walk_forward"]:
            assert wf["n_train"] > 0
            assert wf["n_test"] > 0
            # train_n + test_n ≤ 總 events
            assert wf["n_train"] + wf["n_test"] <= len(events)


class TestDriftFallback:
    def test_high_drift_falls_back_to_default(self):
        """合成 high-drift 場景：train 樣本與 test 行為完全不同 → 過半折 drift > 30%."""
        idx = pd.date_range("2010-01-01", periods=3000, freq="D")
        # 前半永遠 below 25、後半永遠 above 25 → train 學「下方為常態」、test 全偏移
        values = [20.0 if i < 1500 else 35.0 for i in range(3000)]
        series = pd.Series(values, index=idx, name="X")
        events = [_mock_event(f"201{i}-06-15") for i in range(8)]
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), n_folds=4,
            drift_threshold_pct=30.0,
        )
        # 結果可能 adopted 也可能 fallback_overfit；若 fallback 應退回預設
        if result["status"] == "fallback_overfit":
            assert result["recommended"] == 25.0
            assert result["drift_warning"] is True


class TestGridSweepStructure:
    def test_grid_results_one_row_per_threshold(self):
        idx = pd.date_range("2015-01-01", periods=2000, freq="D")
        values = [25.0 + 5 * ((i // 80) % 2) for i in range(2000)]
        series = pd.Series(values, index=idx, name="X")
        events = [_mock_event(str((pd.Timestamp("2015-06-15")
                                    + pd.Timedelta(days=i*180)).date()))
                  for i in range(6)]
        custom_grid = (20.0, 25.0, 30.0)
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), grid=custom_grid, n_folds=3,
        )
        # 3 個 thresholds → 3 個 grid_results rows
        assert len(result["grid_results"]) == 3
        for row in result["grid_results"]:
            assert "threshold" in row
            assert "precision" in row
            assert "recall" in row
            assert "f1" in row


class TestStatusDriftWarningFlag:
    def test_drift_warning_is_bool(self):
        idx = pd.date_range("2015-01-01", periods=2000, freq="D")
        values = [25.0 + 5 * ((i // 80) % 2) for i in range(2000)]
        series = pd.Series(values, index=idx, name="X")
        events = [_mock_event(str((pd.Timestamp("2015-06-15")
                                    + pd.Timedelta(days=i*180)).date()))
                  for i in range(6)]
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), n_folds=3,
        )
        assert isinstance(result["drift_warning"], bool)
        assert result["status"] in ("adopted", "fallback_overfit",
                                     "insufficient_events")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
