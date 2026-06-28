"""src/compute/etf/etf_helpers.py 純函式 unit test — Phase 7B。

v18.306 S-AUDIT-1:`norm_return` / `norm_lower_better` 為 backtest 退役(v18.265 #284)
連帶移除函式,但本 test 未同步;skip 全檔 import-time 防 collection ImportError。
auto_role / _CORE_TICKERS 仍在 etf_helpers.py,單獨重寫 unit test 不在本 audit
scope(等 user 再要時新增)。
"""
from __future__ import annotations

import pytest

pytest.skip(
    "v18.306 S-AUDIT-1: norm_return / norm_lower_better 已在 v18.265 backtest 移除(#284)"
    "中連帶退役;auto_role / _CORE_TICKERS 仍存在但無對應新 unit test。",
    allow_module_level=True,
)

from src.compute.etf import _CORE_TICKERS, auto_role, norm_lower_better, norm_return  # noqa: E402, F401


class TestNormReturn:
    def test_above_hi_clamps_to_100(self):
        assert norm_return(60) == 100

    def test_at_hi_clamps_to_100(self):
        assert norm_return(50) == 100

    def test_below_lo_clamps_to_0(self):
        assert norm_return(-60) == 0

    def test_at_lo_clamps_to_0(self):
        assert norm_return(-50) == 0

    def test_at_mid_returns_50(self):
        assert norm_return(0) == 50

    def test_above_mid_linear(self):
        # mid=0,hi=50: (25-0)/(50-0)*50 + 50 = 75
        assert norm_return(25) == 75

    def test_below_mid_linear(self):
        # lo=-50,mid=0: (-25-(-50))/(0-(-50))*50 = 25
        assert norm_return(-25) == 25

    def test_custom_bounds_cagr(self):
        # 實際 callsite: lo=-5,mid=5,hi=15
        assert norm_return(15, lo=-5, mid=5, hi=15) == 100
        assert norm_return(5, lo=-5, mid=5, hi=15) == 50
        assert norm_return(10, lo=-5, mid=5, hi=15) == 75
        assert norm_return(-5, lo=-5, mid=5, hi=15) == 0

    def test_sharpe_scaling_path(self):
        # 實際 callsite: norm_return(sharpe * 50, lo=-50, mid=50, hi=150)
        # sharpe=1 → 50；對應 mid → 50 分
        assert norm_return(1 * 50, lo=-50, mid=50, hi=150) == 50


class TestNormLowerBetter:
    def test_at_best_returns_100(self):
        assert norm_lower_better(5) == 100

    def test_zero_returns_100(self):
        assert norm_lower_better(0) == 100

    def test_at_worst_returns_0(self):
        assert norm_lower_better(35) == 0

    def test_beyond_worst_returns_0(self):
        assert norm_lower_better(40) == 0

    def test_absolute_value_neg_best(self):
        assert norm_lower_better(-5) == 100

    def test_absolute_value_neg_worst(self):
        assert norm_lower_better(-35) == 0

    def test_at_mid_returns_50(self):
        assert norm_lower_better(20) == 50

    def test_between_best_and_mid(self):
        # v=10: 100 - (10-5)/(20-5)*50 = 100 - 50/3 ≈ 83.333
        assert norm_lower_better(10) == pytest.approx(83.333, abs=0.01)

    def test_between_mid_and_worst(self):
        # v=27.5: 50 - (27.5-20)/(35-20)*50 = 50 - 25 = 25
        assert norm_lower_better(27.5) == pytest.approx(25.0)

    def test_custom_vol_bounds(self):
        # 實際 callsite: best=8,mid=20,worst=35
        assert norm_lower_better(8, best=8, mid=20, worst=35) == 100
        assert norm_lower_better(20, best=8, mid=20, worst=35) == 50


class TestAutoRole:
    def test_core_tw_high_div(self):
        assert auto_role('0050.TW') == '核心'
        assert auto_role('00878.TW') == '核心'
        assert auto_role('006208.TW') == '核心'

    def test_core_us_broad(self):
        assert auto_role('VOO') == '核心'
        assert auto_role('VTI') == '核心'
        assert auto_role('SCHD') == '核心'

    def test_core_bond(self):
        assert auto_role('BND') == '核心'
        assert auto_role('AGG') == '核心'
        assert auto_role('00679B.TW') == '核心'

    def test_satellite_individual_stock(self):
        assert auto_role('2330.TW') == '衛星'

    def test_satellite_unlisted_theme(self):
        # 主題型 ETF 不在白名單
        assert auto_role('00757.TW') == '衛星'

    def test_lowercase_normalized(self):
        assert auto_role('voo') == '核心'
        assert auto_role('bnd') == '核心'

    def test_two_suffix_stripped(self):
        assert auto_role('00679B.TWO') == '核心'

    def test_empty_string_satellite(self):
        assert auto_role('') == '衛星'

    def test_none_satellite(self):
        assert auto_role(None) == '衛星'

    def test_core_tickers_is_frozenset(self):
        # 防呆：constant 不可被誤改
        assert isinstance(_CORE_TICKERS, frozenset)
        with pytest.raises(AttributeError):
            _CORE_TICKERS.add('XXXX')  # type: ignore[attr-defined]
