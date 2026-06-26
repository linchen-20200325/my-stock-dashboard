"""tests/test_stats_helpers.py — calc_stats(v18.301)

§8.3 拆檔測試 — calc_stats 從 daily_checklist 提至 shared/stats_helpers,
本檔守 pure 邏輯 + edge case + back-compat re-export。
"""
from __future__ import annotations

import pandas as pd
import pytest

from shared.stats_helpers import calc_stats


def _df(closes: list[float], col: str = "close") -> pd.DataFrame:
    return pd.DataFrame({col: closes})


# ════════════════════════════════════════════════════════════════
# 1. 三態 status 邏輯
# ════════════════════════════════════════════════════════════════
class TestStatusTriad:
    def test_bullish_arrangement(self):
        """last > MA5 > MA20 → 多頭排列↑。
        closes = [10]*15 + [12]*4 + [20] → MA20=10.9, MA5=13.6, last=20。"""
        closes = [10.0] * 15 + [12.0] * 4 + [20.0]
        out = calc_stats(_df(closes))
        assert out['status'] == '多頭排列↑'

    def test_bearish_arrangement(self):
        """last < MA5 < MA20 → 空頭排列↓。
        closes = [20]*15 + [15]*4 + [5] → MA20=18.25, MA5=13, last=5。"""
        closes = [20.0] * 15 + [15.0] * 4 + [5.0]
        out = calc_stats(_df(closes))
        assert out['status'] == '空頭排列↓'

    def test_consolidation(self):
        """last 與 MA 混排 → '整理中'。全平 → MA5==MA20==last → not strict gt/lt。"""
        closes = [10.0] * 21
        out = calc_stats(_df(closes))
        assert out['status'] == '整理中'


# ════════════════════════════════════════════════════════════════
# 2. 數值正確性
# ════════════════════════════════════════════════════════════════
class TestNumericFields:
    def test_last_pct_chg(self):
        out = calc_stats(_df([100.0, 110.0]))
        assert out['last'] == 110.0
        assert out['chg'] == 10.0
        assert out['pct'] == 10.0

    def test_negative_change(self):
        out = calc_stats(_df([100.0, 95.0]))
        assert out['chg'] == -5.0
        assert out['pct'] == -5.0


# ════════════════════════════════════════════════════════════════
# 3. Edge cases
# ════════════════════════════════════════════════════════════════
class TestEdgeCases:
    def test_none_returns_none(self):
        assert calc_stats(None) is None

    def test_empty_df_returns_none(self):
        assert calc_stats(pd.DataFrame()) is None

    def test_missing_close_column(self):
        df = pd.DataFrame({'wrong_col': [1, 2, 3]})
        assert calc_stats(df) is None

    def test_single_row_returns_none(self):
        assert calc_stats(_df([100.0])) is None

    def test_capital_Close_column_works(self):
        """'close' 或 'Close' 任一存在都應 work。"""
        out = calc_stats(_df([100.0, 110.0], col="Close"))
        assert out is not None
        assert out['last'] == 110.0

    def test_zero_prev_no_division_error(self):
        """prev=0 時 pct fallback 為 0,不 ZeroDivisionError。"""
        out = calc_stats(_df([0.0, 5.0]))
        assert out['pct'] == 0

    def test_short_series_under_20(self):
        """< 20 筆時 MA20 fallback 為 MA5,但仍可算。"""
        out = calc_stats(_df([100.0, 110.0, 115.0, 112.0, 120.0]))
        assert out is not None
        assert out['last'] == 120.0


# ════════════════════════════════════════════════════════════════
# 4. Back-compat re-export 守
# ════════════════════════════════════════════════════════════════
class TestBackCompat:
    def test_daily_checklist_reexport(self):
        """daily_checklist.calc_stats 應仍可 import(re-export shim)。"""
        from daily_checklist import calc_stats as cs_old
        from shared.stats_helpers import calc_stats as cs_new
        assert cs_old is cs_new
