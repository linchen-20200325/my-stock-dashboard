"""tests/test_calc_bias_pct.py — C1 v18.401 乖離率 SSOT 單元測試。

對應 shared/calc_helpers.py:calc_bias_pct (從 8 處 inline (price-MA)/MA*100 收斂)。
"""
from __future__ import annotations

import math

import pytest

import pandas as pd

from shared.calc_helpers import calc_bias_pct, calc_bias_pct_series


class TestCalcBiasPct:
    def test_positive_bias_no_round(self):
        # 價 110 / MA 100 → +10%
        assert calc_bias_pct(110, 100) == pytest.approx(10.0)

    def test_negative_bias_with_round(self):
        # 價 95.346 / MA 100 → -4.654%,decimals=1 → -4.7
        assert calc_bias_pct(95.346, 100, decimals=1) == -4.7

    def test_zero_bias_when_price_equals_ma(self):
        assert calc_bias_pct(50.0, 50.0) == 0.0

    def test_none_price_returns_none(self):
        assert calc_bias_pct(None, 100) is None

    def test_none_ma_returns_none(self):
        assert calc_bias_pct(100, None) is None

    def test_zero_ma_returns_none_not_div_zero(self):
        # MA = 0 應回 None 而非 ZeroDivisionError(§1 fail loud not fabricate)
        assert calc_bias_pct(100, 0) is None

    def test_negative_ma_returns_none(self):
        # 不合理 MA 負值 → 回 None(非捏造)
        assert calc_bias_pct(100, -50) is None

    def test_non_numeric_input_returns_none(self):
        # 字串 / 異常型別不爆,回 None
        assert calc_bias_pct("abc", 100) is None
        assert calc_bias_pct(100, "xyz") is None

    def test_decimals_zero_rounds_to_int(self):
        # decimals=0 應 round 到整數(浮點型)
        assert calc_bias_pct(110.7, 100, decimals=0) == 11.0

    def test_int_inputs_work(self):
        # 純 int 也要 work(不要求 caller 強制 cast)
        assert calc_bias_pct(120, 100) == pytest.approx(20.0)

    def test_extreme_large_values(self):
        # 大數值不溢位
        assert calc_bias_pct(1e10, 1e9) == pytest.approx(900.0)

    def test_no_nan_propagation_on_valid_inputs(self):
        # 確保 valid inputs 不會產生 NaN
        result = calc_bias_pct(150.5, 148.2, decimals=2)
        assert result is not None and not math.isnan(result)
        assert result == pytest.approx(1.55, abs=0.01)


class TestCalcBiasPctSeries:
    """#23 v18.436 — series 版 SSOT(etf_render BIAS(MA20) 圖)。"""

    def test_basic_series(self):
        price = pd.Series([110.0, 90.0, 100.0])
        ma = pd.Series([100.0, 100.0, 100.0])
        out = calc_bias_pct_series(price, ma)
        assert out.tolist() == pytest.approx([10.0, -10.0, 0.0])

    def test_same_formula_as_scalar(self):
        # series 版每點須與 scalar 版同值
        price = pd.Series([150.5, 120.0])
        ma = pd.Series([148.2, 100.0])
        out = calc_bias_pct_series(price, ma)
        assert out.iloc[0] == pytest.approx(calc_bias_pct(150.5, 148.2))
        assert out.iloc[1] == pytest.approx(calc_bias_pct(120.0, 100.0))

    def test_ma_zero_becomes_nan_not_divzero(self):
        # ma<=0 的點 → NaN(§1 fail-safe,不 ÷0、不捏造)
        price = pd.Series([100.0, 100.0])
        ma = pd.Series([0.0, 50.0])
        out = calc_bias_pct_series(price, ma)
        assert math.isnan(out.iloc[0])
        assert out.iloc[1] == pytest.approx(100.0)

    def test_ma_nan_propagates_nan(self):
        # rolling 開頭 ma=NaN(未成形)→ 該點 NaN,不污染後續
        price = pd.Series([100.0, 110.0])
        ma = pd.Series([float('nan'), 100.0])
        out = calc_bias_pct_series(price, ma)
        assert math.isnan(out.iloc[0])
        assert out.iloc[1] == pytest.approx(10.0)

    def test_negative_ma_becomes_nan(self):
        price = pd.Series([100.0])
        ma = pd.Series([-50.0])
        out = calc_bias_pct_series(price, ma)
        assert math.isnan(out.iloc[0])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
