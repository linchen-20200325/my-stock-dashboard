# -*- coding: utf-8 -*-
"""v19.93 Phase 2 — scripts/calibrate_health_weights 純函式單測（合成 df）。

真實擬合在部署 cron;此處只驗 wiring 正確性 + SSOT parity（reconstruct_score 呼**真**
market_regime）+ PIT backward 對齊 + §1 fail-loud。main() 的 parquet I/O 不在此測。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.calibrate_health_weights import (
    _ma_flags,
    _prep_close,
    build_feature_frame,
    reconstruct_score,
    render_proposal,
    run_calibration,
)


def _twii(n=200, rate=0.002, start="2023-01-02"):
    idx = pd.date_range(start=start, periods=n, freq="B")
    close = [100.0 * (1 + rate) ** i for i in range(n)]
    return pd.DataFrame({"date": idx, "open": close, "high": close,
                         "low": close, "close": close, "volume": [1e6] * n})


def _inst(n=200, start="2023-01-02", foreign=10.0):
    idx = pd.date_range(start=start, periods=n, freq="B")
    return pd.DataFrame({"date": idx, "foreign_buy": [foreign] * n})


def _m1m2(months=14, start="2023-01-01"):
    idx = pd.date_range(start=start, periods=months, freq="MS")
    return pd.DataFrame({"date": idx, "m1b": [5.0 + 0.1 * i for i in range(months)],
                         "m2": [4.0] * months,
                         "m1b_m2_gap": [1.0 + 0.1 * i for i in range(months)]})


class TestPrepClose:
    def test_sorted_dedup_keep_last(self):
        df = pd.DataFrame({"date": ["2023-01-03", "2023-01-02", "2023-01-02"],
                           "close": [11.0, 10.0, 10.5]})
        s = _prep_close(df)
        assert list(s.index) == [pd.Timestamp("2023-01-02"), pd.Timestamp("2023-01-03")]
        assert s.iloc[0] == 10.5   # 同日重複取最後


class TestMaFlags:
    def test_uptrend_above_and_rising(self):
        close = pd.Series([10.0 + 0.1 * i for i in range(70)],
                          index=pd.date_range("2023-01-02", periods=70, freq="B"))
        f = _ma_flags(close, 60)
        assert bool(f["above_3d"].iloc[-1])
        assert bool(f["rising"].iloc[-1])
        assert not bool(f["below_3d"].iloc[-1])


class TestReconstructScoreParity:
    def test_strict_uptrend_full_6_of_6(self):
        """強勢上升 + 外資買超 + m1m2 正向上升 → 真 market_regime 滿分 6/6 → score_norm=100。

        非循環:斷言基於「全因子正向 → market_regime 定義上必得滿分」的獨立推理。
        """
        close = _prep_close(_twii())
        sc = reconstruct_score(close, _inst(), _m1m2())
        row = sc.iloc[130]   # ≥120 日歷史 + 非首月（gap_prev 存在）
        assert row["max_score"] == 6.0    # ad_ratio + m1m2 皆傳入
        assert row["score"] == 6.0        # 4 MA 因子 + 外資 + 廣度 + 活水全正向
        assert row["score_norm"] == 100.0

    def test_early_days_before_ma120_are_nan(self):
        close = _prep_close(_twii())
        sc = reconstruct_score(close, _inst(), _m1m2())
        assert pd.isna(sc.iloc[10]["score_norm"])   # <120 日 → 不評分（不偽造）

    def test_no_lookahead_foreign_backward(self):
        """外資只在其公布日（含）之後對齊 → 未來的外資值不得回填到過去日（PIT）。"""
        close = _prep_close(_twii(n=130))
        # 外資只有「後半段」有資料 → 前半段 fnet 應為 None（backward 找不到過去值）
        inst = _inst(n=130).iloc[60:].reset_index(drop=True)
        sc = reconstruct_score(close, inst, _m1m2())
        assert pd.isna(sc.iloc[5]["fnet"])         # 早於外資起始 → 無值（不回填未來 = 無 lookahead）
        assert sc.iloc[120]["fnet"] == 10.0        # 外資公布日之後 → 取得


class TestBuildFeatureFrame:
    def test_columns_and_length(self):
        feat = build_feature_frame(_twii(), _inst(), _m1m2())
        assert set(feat.columns) == {"jqavg", "score_norm", "fnet", "y"}
        assert len(feat) == 200
        assert len(feat.dropna()) > 0


class TestRunCalibrationAndProposal:
    def test_single_class_uptrend_raises(self):
        # 強勢上升 → 幾乎無回撤 → y 單一類別（或樣本不足）→ §1 raise
        with pytest.raises(ValueError):
            run_calibration(build_feature_frame(_twii(), _inst(), _m1m2()))

    def _sawtooth_twii(self, n=440, start="2022-01-03"):
        seg = list(np.linspace(100, 120, 40)) + list(np.linspace(120, 105, 15))  # 漲後 -12.5%
        close = (seg * ((n // len(seg)) + 1))[:n]
        idx = pd.date_range(start=start, periods=n, freq="B")
        return pd.DataFrame({"date": idx, "close": close, "open": close,
                             "high": close, "low": close, "volume": [1e6] * n})

    def test_fit_and_proposal_on_mixed(self):
        twii = self._sawtooth_twii()
        feat = build_feature_frame(twii, _inst(n=440, start="2022-01-03"),
                                   _m1m2(months=26, start="2022-01-01"))
        result = run_calibration(feat)      # 鋸齒 → y 兩類 + 足量樣本
        assert set(result["weights_raw"]) == {"jqavg", "score_norm", "fnet"}
        assert result["n_samples"] >= 60
        md = render_proposal(result, feat)
        for token in ("校準提案", "jqavg", "score_norm", "fnet", "overfit_flag", "λ"):
            assert token in md
        assert "未改任何 code" in md   # 提案不動 SSOT（§8.1 / Phase 3 才改）


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
