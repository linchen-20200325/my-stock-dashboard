"""shared/calc_helpers.py — 通用計算 helper(L0,純函式)。

A4 v18.384 深層拔毒:統一散落 3 處的 `series.pct_change(N) * 100.0` pattern。
"""
from __future__ import annotations


def pct_change_yoy(series, periods: int = 12, multiplier: float = 100.0):
    """通用 pct_change × multiplier(預設 12 月 YoY × 100 = %)。

    參數:
        series: pd.Series(月頻 → periods=12 ≡ YoY;日頻 → periods=20 ≡ 20-day 跌幅)
        periods: pct_change 期數,預設 12(月頻 YoY)
        multiplier: 結果乘數,預設 100.0(% 表示)

    Caller(3 處):
    - src/compute/macro/macro_helpers.py:860 M2 YoY(月頻 12)
    - src/compute/scoring/scoring_engine.py:446 revenue YoY(月頻 12)
    - src/compute/macro/macro_signal_lookback_tw.py:191 TWII 20D 跌幅(日頻 20)
    """
    return series.pct_change(periods) * multiplier
