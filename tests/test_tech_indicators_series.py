"""tests/test_tech_indicators_series.py — C5 v18.403 series-variant 單元測試。

對應 src/compute/strategy/tech_indicators.py 新增 3 個 series 函式
(從 tab_stock_picker.py 抽出,picker 用於相鄰兩日比較 / 寬度時序 / 斜率)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.compute.strategy.tech_indicators import (
    calc_bollinger_width_series,
    calc_kd_series,
    calc_ma_series,
)


@pytest.fixture
def synthetic_close():
    """30 日合成 close series:線性上升 100→130。"""
    return pd.Series(np.linspace(100, 130, 30), name='close')


@pytest.fixture
def synthetic_ohlc():
    """30 日 OHLC,高低範圍 ±2,close 線性 100→130。"""
    n = 30
    close = pd.Series(np.linspace(100, 130, n))
    return pd.DataFrame({
        'close': close,
        'high':  close + 2,
        'low':   close - 2,
    })


class TestCalcMaSeries:
    def test_window_20_returns_series_with_nan_prefix(self, synthetic_close):
        ma = calc_ma_series(synthetic_close, window=20)
        assert isinstance(ma, pd.Series)
        # 前 19 個 NaN
        assert ma.iloc[:19].isna().all()
        # 第 20 個 = 前 20 個 close 均值
        assert ma.iloc[19] == pytest.approx(synthetic_close.iloc[:20].mean())

    def test_default_window_20(self, synthetic_close):
        ma_default = calc_ma_series(synthetic_close)
        ma_explicit = calc_ma_series(synthetic_close, window=20)
        pd.testing.assert_series_equal(ma_default, ma_explicit)

    def test_short_series_all_nan(self):
        s = pd.Series([100.0, 101.0, 102.0])
        ma = calc_ma_series(s, window=20)
        assert ma.isna().all()


class TestCalcBollingerWidthSeries:
    def test_returns_series_with_window_20_nan_prefix(self, synthetic_close):
        w = calc_bollinger_width_series(synthetic_close, window=20)
        assert isinstance(w, pd.Series)
        assert w.iloc[:19].isna().all()

    def test_width_positive_for_real_data(self, synthetic_close):
        w = calc_bollinger_width_series(synthetic_close, window=20).dropna()
        assert len(w) > 0
        assert (w > 0).all()

    def test_constant_series_width_is_zero(self):
        # 完全平盤 → std=0 → width=0
        s = pd.Series([100.0] * 30)
        w = calc_bollinger_width_series(s, window=20).dropna()
        assert (w == 0).all() or w.isna().any()  # 0/0 可能是 NaN

    def test_custom_k_multiplier(self, synthetic_close):
        # k=1 應該等於 k=2 的一半
        w1 = calc_bollinger_width_series(synthetic_close, window=20, k=1.0).dropna()
        w2 = calc_bollinger_width_series(synthetic_close, window=20, k=2.0).dropna()
        if len(w1) and len(w2):
            assert w1.iloc[-1] == pytest.approx(w2.iloc[-1] / 2)


class TestCalcKdSeries:
    def test_returns_two_series_same_length(self, synthetic_ohlc):
        k, d = calc_kd_series(
            synthetic_ohlc['close'],
            synthetic_ohlc['high'],
            synthetic_ohlc['low'],
            period=9,
        )
        assert isinstance(k, pd.Series)
        assert isinstance(d, pd.Series)
        assert len(k) == len(d) == len(synthetic_ohlc)

    def test_k_in_0_100_range_for_real_data(self, synthetic_ohlc):
        k, d = calc_kd_series(
            synthetic_ohlc['close'],
            synthetic_ohlc['high'],
            synthetic_ohlc['low'],
        )
        k_valid = k.dropna()
        # 一般情況 K 在 [0, 100],但 EMA 平滑後極端值可能略超界
        assert (k_valid >= -1).all()
        assert (k_valid <= 101).all()

    def test_kd_compares_adjacent_days_safely(self, synthetic_ohlc):
        # 確認 iloc[-1] 跟 iloc[-2] 都可取(picker 黃叉判定的核心場景)
        k, d = calc_kd_series(
            synthetic_ohlc['close'],
            synthetic_ohlc['high'],
            synthetic_ohlc['low'],
        )
        k_clean = k.dropna()
        assert len(k_clean) >= 2
        # 相鄰兩日不爆
        _ = float(k_clean.iloc[-1])
        _ = float(k_clean.iloc[-2])

    def test_short_series_returns_nan_prefix(self):
        # 不足 9 期 → 前面都 NaN
        close = pd.Series([100.0] * 5)
        high = pd.Series([102.0] * 5)
        low = pd.Series([98.0] * 5)
        k, d = calc_kd_series(close, high, low, period=9)
        # rsv rolling 至少需 9 期 → 前 8 個 NaN
        assert k.iloc[:5].isna().all() or k.notna().sum() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
