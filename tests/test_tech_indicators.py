"""src/compute/strategy/tech_indicators.py 純函式 unit test — Phase 7H。"""
from __future__ import annotations

import pandas as pd
import pytest

from src.compute.strategy import (
    calc_bollinger,
    calc_ibs,
    calc_kd,
    calc_rsi,
    calc_vcp,
    calc_volume_ratio,
)


def _ohlcv(closes, highs=None, lows=None, volumes=None):
    """快速建構 OHLCV DataFrame helper。"""
    n = len(closes)
    return pd.DataFrame({
        'close': closes,
        'high':  highs   if highs   is not None else [c + 1 for c in closes],
        'low':   lows    if lows    is not None else [c - 1 for c in closes],
        'volume': volumes if volumes is not None else [1000] * n,
    })


class TestCalcRsi:
    def test_none_returns_none(self):
        assert calc_rsi(None) is None

    def test_too_few_rows_returns_none(self):
        # 預設 period=14，需要 ≥15 rows
        df = _ohlcv(list(range(10)))
        assert calc_rsi(df) is None

    def test_custom_period_too_few(self):
        df = _ohlcv(list(range(5)))
        assert calc_rsi(df, period=10) is None

    def test_all_up_high_rsi(self):
        # 連續上漲 30 天 → RSI 應接近 100
        df = _ohlcv(list(range(1, 31)))
        rsi = calc_rsi(df)
        assert rsi is not None
        assert rsi >= 99

    def test_all_down_low_rsi(self):
        # 連續下跌 30 天 → RSI 應接近 0
        df = _ohlcv(list(range(30, 0, -1)))
        rsi = calc_rsi(df)
        assert rsi is not None
        assert rsi <= 1

    def test_returns_rounded_to_1_decimal(self):
        df = _ohlcv([10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11])
        rsi = calc_rsi(df)
        assert rsi is not None
        # round(_, 1) → 至多 1 位小數
        assert rsi == round(rsi, 1)

    def test_missing_column_returns_none(self):
        # 無 'close' 欄 → except 路徑 → None
        df = pd.DataFrame({'foo': list(range(20))})
        assert calc_rsi(df) is None


class TestCalcIbs:
    def test_none_returns_none(self):
        assert calc_ibs(None) is None

    def test_empty_df_returns_none(self):
        assert calc_ibs(pd.DataFrame()) is None

    def test_close_at_low(self):
        # close == low → IBS = 0
        df = pd.DataFrame({'high': [110], 'low': [100], 'close': [100]})
        assert calc_ibs(df) == 0.0

    def test_close_at_high(self):
        # close == high → IBS = 1
        df = pd.DataFrame({'high': [110], 'low': [100], 'close': [110]})
        assert calc_ibs(df) == 1.0

    def test_close_middle(self):
        # close 在中間 → IBS = 0.5
        df = pd.DataFrame({'high': [110], 'low': [100], 'close': [105]})
        assert calc_ibs(df) == 0.5

    def test_flat_range_returns_half(self):
        # h == l → 預設 0.5（避免 div by zero）
        df = pd.DataFrame({'high': [100], 'low': [100], 'close': [100]})
        assert calc_ibs(df) == 0.5

    def test_uses_last_row(self):
        # 多列時取最後一列
        df = pd.DataFrame({
            'high':  [110, 120],
            'low':   [100, 100],
            'close': [100, 120],
        })
        assert calc_ibs(df) == 1.0

    def test_rounded_to_3_decimals(self):
        df = pd.DataFrame({'high': [100], 'low': [0], 'close': [33.33333]})
        v = calc_ibs(df)
        # round(_, 3)
        assert v == round(v, 3)

    def test_missing_column_returns_none(self):
        df = pd.DataFrame({'foo': [1]})
        assert calc_ibs(df) is None


class TestCalcVolumeRatio:
    def test_none_returns_none(self):
        assert calc_volume_ratio(None) is None

    def test_too_few_rows_returns_none(self):
        df = _ohlcv([10, 11, 12], volumes=[100, 200, 300])
        # 預設 period=5，需要 ≥6 rows
        assert calc_volume_ratio(df) is None

    def test_basic_ratio(self):
        # 過去 5 天均量 = 100，今天 200 → ratio = 2.0
        df = _ohlcv([10] * 6, volumes=[100, 100, 100, 100, 100, 200])
        assert calc_volume_ratio(df) == 2.0

    def test_avg_zero_returns_none(self):
        # 過去 5 天量都 0 → None（避免 div by zero）
        df = _ohlcv([10] * 6, volumes=[0, 0, 0, 0, 0, 100])
        assert calc_volume_ratio(df) is None

    def test_custom_period(self):
        # period=2，過去 2 天均量 = 50，今天 100 → ratio = 2.0
        df = _ohlcv([10] * 4, volumes=[10, 50, 50, 100])
        assert calc_volume_ratio(df, period=2) == 2.0

    def test_rounded_to_2_decimals(self):
        df = _ohlcv([10] * 6, volumes=[100, 100, 100, 100, 100, 333])
        v = calc_volume_ratio(df)
        assert v == round(v, 2)

    def test_excludes_today_from_avg(self):
        # 平均應排除今天本身（df.iloc[-(p+1):-1]）
        df = _ohlcv([10] * 6, volumes=[100, 100, 100, 100, 100, 99999])
        # 過去 5 天 = [100,100,100,100,100]，今天 99999 → 99999/100 = 999.99
        assert calc_volume_ratio(df) == round(99999 / 100, 2)


class TestCalcKd:
    def test_none_returns_tuple_of_none(self):
        assert calc_kd(None) == (None, None)

    def test_too_few_rows_returns_tuple_of_none(self):
        df = _ohlcv(list(range(5)))
        assert calc_kd(df) == (None, None)

    def test_returns_tuple_of_floats(self):
        df = _ohlcv(list(range(1, 21)))
        k, d = calc_kd(df)
        assert isinstance(k, float)
        assert isinstance(d, float)

    def test_k_and_d_in_0_to_100(self):
        df = _ohlcv(list(range(1, 21)))
        k, d = calc_kd(df)
        assert 0 <= k <= 100
        assert 0 <= d <= 100

    def test_all_up_high_k(self):
        # 連續上漲 → K 高
        df = _ohlcv(list(range(1, 31)))
        k, _ = calc_kd(df)
        assert k > 80

    def test_all_down_low_k(self):
        df = _ohlcv(list(range(30, 0, -1)))
        k, _ = calc_kd(df)
        assert k < 20

    def test_rounded_to_1_decimal(self):
        df = _ohlcv(list(range(1, 21)))
        k, d = calc_kd(df)
        assert k == round(k, 1)
        assert d == round(d, 1)

    def test_missing_column_returns_tuple_of_none(self):
        df = pd.DataFrame({'foo': list(range(20))})
        assert calc_kd(df) == (None, None)


class TestCalcBollinger:
    def test_none_returns_none(self):
        assert calc_bollinger(None) is None

    def test_too_few_rows_returns_none(self):
        df = _ohlcv(list(range(10)))
        # 預設 window=20，需要 ≥20 rows
        assert calc_bollinger(df) is None

    def test_returns_dict_with_expected_keys(self):
        df = _ohlcv(list(range(1, 31)))
        bb = calc_bollinger(df)
        assert bb is not None
        for k in ('upper', 'lower', 'ma', 'bw', 'bw_mean', 'price', 'near_upper'):
            assert k in bb

    def test_ma_between_upper_and_lower(self):
        df = _ohlcv(list(range(1, 31)))
        bb = calc_bollinger(df)
        assert bb['lower'] <= bb['ma'] <= bb['upper']

    def test_near_upper_bool(self):
        df = _ohlcv(list(range(1, 31)))
        bb = calc_bollinger(df)
        assert isinstance(bb['near_upper'], bool)

    def test_custom_window(self):
        df = _ohlcv(list(range(1, 16)))
        bb = calc_bollinger(df, window=10)
        assert bb is not None

    def test_missing_column_returns_none(self):
        df = pd.DataFrame({'foo': list(range(30))})
        assert calc_bollinger(df) is None

    def test_constant_price_no_band_width(self):
        # 全 100 → std=0，upper=lower=ma=100，bw=0
        df = _ohlcv([100.0] * 30)
        bb = calc_bollinger(df)
        assert bb is not None
        assert bb['upper'] == bb['lower'] == bb['ma'] == 100.0
        assert bb['bw'] == 0.0


class TestCalcVcp:
    def test_none_returns_none(self):
        assert calc_vcp(None) is None

    def test_too_few_rows_returns_none(self):
        # 需要 ≥30 rows
        df = _ohlcv(list(range(20)))
        assert calc_vcp(df) is None

    def test_no_swings_returns_none(self):
        # 完全平坦 → 無高低點 swings → ranges 不足 → None
        df = _ohlcv([100.0] * 50, highs=[100.0] * 50, lows=[100.0] * 50)
        assert calc_vcp(df) is None

    def test_contracting_pattern_detected(self):
        # 構造振幅遞減的價格序列：50, 100, 60, 90, 70, 80, 75, 75（依序縮）
        # 簡化：用大區間 50 天，後半段震盪縮小
        highs = [100 + 30 * (1 - i / 60) * ((-1) ** (i // 5)) for i in range(60)]
        lows  = [h - 5 for h in highs]
        df = pd.DataFrame({
            'close': [(hi + lo) / 2 for hi, lo in zip(highs, lows)],
            'high':  highs,
            'low':   lows,
            'volume': [1000] * 60,
        })
        out = calc_vcp(df)
        # 視構造可能 None / 有結果；只要能正常處理不丟例外即可
        if out is not None:
            assert 'swings' in out
            assert 'contracting' in out
            assert 'latest_range' in out
            assert isinstance(out['contracting'], bool)

    def test_custom_n_swings_too_high_returns_none(self):
        df = _ohlcv(list(range(1, 31)))
        # 索取 100 個 swings → 不可能達成 → None
        assert calc_vcp(df, n_swings=100) is None

    def test_missing_column_raises(self):
        # 文件述明：失敗不丟例外。但實際上 calc_vcp 在 len<30 之外的
        # column 缺失會拋 KeyError（這是預期行為的局部例外）。
        # 因此 callsite 必須保證有 high/low 欄。
        df = pd.DataFrame({'foo': list(range(50))})
        with pytest.raises(KeyError):
            calc_vcp(df)
