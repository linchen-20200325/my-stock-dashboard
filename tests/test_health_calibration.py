# -*- coding: utf-8 -*-
"""v19.92 — 紅綠燈校準管線 Phase 1：health_calibration.py L2 純函式。

方法論定案 MACRO_HEALTH_REWEIGHT_PROPOSAL.md（user Path 1 核准）。
測 3 演算法 + §1 fail-loud + §8.2 L2 純度（無 streamlit/requests）。
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.compute.macro.health_calibration import (
    JQAVG_ROLLING_DAYS,
    breadth_from_twii,
    fit_health_weights,
    risk_posture_label,
)

REPO = Path(__file__).resolve().parent.parent


# ───────────────── breadth_from_twii（jqavg 重建，SSOT parity）─────────────────
class TestBreadthFromTwii:
    def test_flat_up_1pct_gives_58_33(self):
        # 每日 +1%：up=1050/down=750 → ad_ratio=58.33；5 日均後仍 58.33
        close = pd.Series([100.0 * (1.01 ** i) for i in range(10)])
        jq = breadth_from_twii(close)
        assert math.isclose(float(jq.iloc[-1]), 1050 / 1800 * 100, rel_tol=1e-6)

    def test_flat_price_gives_50(self):
        # 零漲跌 → up=down=900 → ad_ratio=50
        close = pd.Series([100.0] * 10)
        jq = breadth_from_twii(close)
        assert math.isclose(float(jq.iloc[-1]), 50.0, abs_tol=1e-9)

    def test_down_1pct_below_50(self):
        close = pd.Series([100.0 * (0.99 ** i) for i in range(10)])
        jq = breadth_from_twii(close)
        assert float(jq.iloc[-1]) < 50.0
        assert math.isclose(float(jq.iloc[-1]), 750 / 1800 * 100, rel_tol=1e-4)

    def test_head_is_nan_not_fabricated(self):
        # 前 JQAVG_ROLLING_DAYS 個因 5 日均不足 → NaN（§1 不偽造，不 ffill）
        close = pd.Series([100.0 * (1.01 ** i) for i in range(10)])
        jq = breadth_from_twii(close)
        assert jq.iloc[:JQAVG_ROLLING_DAYS].isna().all()
        assert jq.iloc[JQAVG_ROLLING_DAYS:].notna().all()

    def test_empty_returns_empty(self):
        assert breadth_from_twii(pd.Series(dtype=float)).empty
        assert breadth_from_twii(None).empty

    def test_index_preserved(self):
        idx = pd.date_range("2024-01-01", periods=8, freq="D")
        close = pd.Series([100.0] * 8, index=idx)
        jq = breadth_from_twii(close)
        assert (jq.index == idx).all()


# ───────────────── risk_posture_label（20 日回撤真值）─────────────────
class TestRiskPostureLabel:
    def test_flat_series_all_zero(self):
        # 完全不跌 → 無回撤 → y=0（有完整未來窗的列）
        close = pd.Series([100.0] * 30)
        y = risk_posture_label(close, theta_dd_pct=8.0, horizon=20)
        head = y.iloc[:9]  # t=0..8 有完整 20 日窗
        assert (head == 0.0).all()

    def test_drawdown_triggers_defend(self):
        # day5 跌到 90（10% 回撤）落在 t=0 的未來 20 日窗 → y[0]=1
        close = pd.Series([100.0] * 5 + [90.0] + [100.0] * 30)
        y = risk_posture_label(close, theta_dd_pct=8.0, horizon=20)
        assert y.iloc[0] == 1.0

    def test_shallow_dip_below_threshold_no_defend(self):
        # 只跌 3%（< 8% θ_dd）→ y=0
        close = pd.Series([100.0] * 5 + [97.0] + [100.0] * 30)
        y = risk_posture_label(close, theta_dd_pct=8.0, horizon=20)
        assert y.iloc[0] == 0.0

    def test_tail_insufficient_window_is_nan(self):
        close = pd.Series([100.0] * 30)
        y = risk_posture_label(close, horizon=20)
        assert y.iloc[10:].isna().all()   # t>=10 → end>=30 不足

    def test_theta_adjustable(self):
        # 同資料，θ_dd 放寬到 3% → 原本不觸發的 3% dip 現觸發
        close = pd.Series([100.0] * 5 + [97.0] + [100.0] * 30)
        assert risk_posture_label(close, theta_dd_pct=3.0, horizon=20).iloc[0] == 1.0

    def test_empty_and_bad_horizon(self):
        assert risk_posture_label(pd.Series(dtype=float)).empty
        with pytest.raises(ValueError):
            risk_posture_label(pd.Series([100.0] * 5), horizon=0)


# ───────────────── fit_health_weights（walk-forward L2-logistic）─────────────────
class TestFitHealthWeights:
    def _synth(self, n=300, seed=0):
        rng = np.random.default_rng(seed)
        x1 = rng.uniform(30, 70, n)          # jqavg（低廣度 → 該防禦）
        x2 = rng.uniform(0, 100, n)          # score（噪音）
        x3 = rng.normal(0, 1, n)             # fnet（噪音）
        p = 1.0 / (1.0 + np.exp(-0.25 * (x1 - 50)))  # 低 x1 → 高 P(defend)
        y = (rng.uniform(0, 1, n) < (1 - p)).astype(float)  # defend 與 x1 反向
        return np.column_stack([x1, x2, x3]), y

    def test_recovers_negative_breadth_weight(self):
        X, y = self._synth()
        out = fit_health_weights(X, y, feature_names=["jqavg", "score", "fnet"])
        # 低廣度 → 該防禦：jqavg 對 P(defend) 應負相關
        assert out["weights_raw"]["jqavg"] < 0
        # 訊號特徵 |w| 應大於純噪音 fnet
        assert abs(out["weights_std"]["jqavg"]) > abs(out["weights_std"]["fnet"])

    def test_auc_above_chance(self):
        X, y = self._synth()
        out = fit_health_weights(X, y, feature_names=["jqavg", "score", "fnet"])
        assert out["cv"]["mean_val_auc"] > 0.6

    def test_too_few_samples_raises(self):
        X, y = self._synth(n=30)
        with pytest.raises(ValueError, match="樣本"):
            fit_health_weights(X, y)

    def test_single_class_raises(self):
        X, _ = self._synth(n=200)
        with pytest.raises(ValueError, match="單一類別"):
            fit_health_weights(X, np.zeros(200))

    def test_nan_rows_dropped_not_filled(self):
        X, y = self._synth(n=200)
        X[::20, 0] = np.nan   # 灑 NaN
        out = fit_health_weights(X, y, feature_names=["jqavg", "score", "fnet"])
        assert out["n_samples"] < 200          # NaN 列被 drop（非填補）
        assert out["n_samples"] >= 60

    def test_output_contract(self):
        X, y = self._synth()
        out = fit_health_weights(X, y, feature_names=["jqavg", "score", "fnet"])
        for k in ("weights_raw", "intercept_raw", "lambda_selected",
                  "n_samples", "class_balance", "cv", "robustness", "overfit_flag"):
            assert k in out
        assert set(out["weights_raw"]) == {"jqavg", "score", "fnet"}


# ───────────────── §8.2 L2 純度 ─────────────────
class TestL2Purity:
    def test_no_streamlit_no_requests_import(self):
        src = (REPO / "src/compute/macro/health_calibration.py").read_text(encoding="utf-8")
        assert "import streamlit" not in src
        assert "import requests" not in src
        assert "proxy_helper" not in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
