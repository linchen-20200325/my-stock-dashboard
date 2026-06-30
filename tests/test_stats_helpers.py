"""tests/test_stats_helpers.py — calc_stats(v18.301)

§8.3 拆檔測試 — calc_stats 從 daily_checklist 提至 shared/stats_helpers,
本檔守 pure 邏輯 + edge case + back-compat re-export。
"""
from __future__ import annotations

import pandas as pd
import pytest

import math

from shared.stats_helpers import calc_stats, zscore


def _df(closes: list[float], col: str = "close") -> pd.DataFrame:
    return pd.DataFrame({col: closes})


# ════════════════════════════════════════════════════════════════
# 0. zscore SSOT(D2 v18.437 — 統一 macro_core.zscore + multi_factor._zscore)
# ════════════════════════════════════════════════════════════════
class TestZscore:
    def test_normal(self):
        z = zscore(pd.Series([1.0, 2, 3, 4, 5]))
        assert z.mean() == pytest.approx(0.0, abs=1e-12)
        assert z.iloc[0] == pytest.approx(-1.2649, abs=1e-3)
        assert z.iloc[-1] == pytest.approx(1.2649, abs=1e-3)

    def test_zero_std_returns_zeros_no_div_zero(self):
        z = zscore(pd.Series([3.0, 3.0, 3.0]))
        assert z.tolist() == [0.0, 0.0, 0.0]

    def test_empty_returns_empty(self):
        out = zscore(pd.Series([], dtype=float))
        assert len(out) == 0

    def test_single_element_no_crash(self):
        # 單元素 std(ddof=1)=NaN → guard 回 0(不捏造、不爆)
        z = zscore(pd.Series([42.0]))
        assert z.tolist() == [0.0]

    def test_index_preserved(self):
        s = pd.Series([10.0, 20, 30], index=["a", "b", "c"])
        assert list(zscore(s).index) == ["a", "b", "c"]

    def test_macro_core_reexport_delegates(self):
        # macro_core.zscore 仍可用且委派同一 SSOT 實作(值一致)
        from src.data.macro import macro_core
        s = pd.Series([1.0, 2, 4, 8])
        assert macro_core.zscore(s).round(6).tolist() == zscore(s).round(6).tolist()


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
        """src.services.daily_checklist.calc_stats 應仍可 import(re-export shim)。"""
        from src.services import calc_stats as cs_old
        from shared.stats_helpers import calc_stats as cs_new
        assert cs_old is cs_new
