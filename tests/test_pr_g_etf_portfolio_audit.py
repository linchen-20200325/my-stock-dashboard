"""v18.332 PR-G U-9 — etf_tab_portfolio 深度 audit 8 項投組特有 magic 收斂守衛。

audit 範圍:etf_tab_portfolio.py 投組層特有(single/grp 不消費)。
SSOT 位置:shared.signal_thresholds 新增「ETF 投組 Tab 投組特有 SSOT」區段。

收斂項目:
- G1 P1 — ETF_CORR_HIGH_THRESHOLD (相關係數 0.85)
- G1 P2 — PORTFOLIO_OVERLAP_WEIGHT/JACCARD_THRESHOLD_PCT (Overlap 30 / 50)
- G1 P3 — PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT (再平衡預設 5)
- G2    — PORTFOLIO_STRESS_TEST_DROP_PCT / LOSS_WARN_PCT (壓測 -20 / 20)
- G2    — PORTFOLIO_VAR_95/99_PERCENTILE (VaR 0.05 / 0.01)
- G2    — PORTFOLIO_VAR_MONTHLY_WARN_PCT (月度 VaR 警示 10)
"""
from __future__ import annotations

import shared.signal_thresholds as st_mod


class TestG1P3_RebalTolerance:
    """G1 P3 — 再平衡 Slider 預設值 SSOT。"""

    def test_constant_exists_and_value(self):
        assert st_mod.PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT == 5.0

    def test_in_slider_range(self):
        """Slider 範圍 1~15,預設應落在範圍內。"""
        assert 1 <= st_mod.PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT <= 15

    def test_no_inline_in_portfolio(self):
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        assert "', 1, 15, 5," not in src
        assert 'PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT' in src


class TestG1P1_CorrThreshold:
    """G1 P1 — 相關係數同質性警示 SSOT。"""

    def test_constant_exists_and_value(self):
        assert st_mod.ETF_CORR_HIGH_THRESHOLD == 0.85

    def test_in_correlation_range(self):
        """Pearson corr ∈ [-1, 1],高同質性門檻應 ∈ (0.5, 1)。"""
        assert 0.5 < st_mod.ETF_CORR_HIGH_THRESHOLD < 1.0

    def test_no_inline_in_portfolio(self):
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        assert 'val > 0.85' not in src
        assert '> 0.85，資產同質性過高' not in src
        assert 'ETF_CORR_HIGH_THRESHOLD' in src


class TestG1P2_OverlapThresholds:
    """G1 P2 — 持股 Overlap 矩陣(weight / jaccard)雙門檻 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT == 30.0
        assert st_mod.PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT == 50.0

    def test_jaccard_above_weight(self):
        """Jaccard 不看權重,門檻設較高才合理(50 > 30)。"""
        assert (st_mod.PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT
                > st_mod.PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT)

    def test_no_inline_in_portfolio(self):
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        assert "30.0 if _method_key == 'weight' else 50.0" not in src
        assert 'PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT' in src
        assert 'PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT' in src


class TestG2_StressTest:
    """G2 — 壓力測試 S&P500 下跌幅度 + 警示門檻 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.PORTFOLIO_STRESS_TEST_DROP_PCT == -20.0
        assert st_mod.PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT == 20.0

    def test_drop_negative(self):
        """壓測「下跌」應為負值,警示門檻應為正值。"""
        assert st_mod.PORTFOLIO_STRESS_TEST_DROP_PCT < 0
        assert st_mod.PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT > 0

    def test_no_inline_in_portfolio(self):
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        assert '* (-0.20) * total_value' not in src
        assert "'red' if loss_pct > 20 else 'green'" not in src
        assert '⚠️ 超過20%' not in src
        assert 'PORTFOLIO_STRESS_TEST_DROP_PCT' in src
        assert 'PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT' in src


class TestG2_VaR:
    """G2 — VaR 風險值 95% / 99% 分位數 + 月度警示門檻 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.PORTFOLIO_VAR_95_PERCENTILE == 0.05
        assert st_mod.PORTFOLIO_VAR_99_PERCENTILE == 0.01
        assert st_mod.PORTFOLIO_VAR_MONTHLY_WARN_PCT == 10.0

    def test_var99_more_conservative_than_var95(self):
        """99% 分位數(0.01) < 95% 分位數(0.05),取較小分位 → 更保守的尾部估計。"""
        assert (st_mod.PORTFOLIO_VAR_99_PERCENTILE
                < st_mod.PORTFOLIO_VAR_95_PERCENTILE)

    def test_percentiles_in_valid_range(self):
        """quantile 參數必須 ∈ (0, 1)。"""
        assert 0 < st_mod.PORTFOLIO_VAR_95_PERCENTILE < 1
        assert 0 < st_mod.PORTFOLIO_VAR_99_PERCENTILE < 1

    def test_monthly_warn_positive(self):
        assert st_mod.PORTFOLIO_VAR_MONTHLY_WARN_PCT > 0

    def test_no_inline_in_portfolio(self):
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        assert '_port_ret.quantile(0.05)' not in src
        assert '_port_ret.quantile(0.01)' not in src
        assert 'abs(_m99) / total_value > 0.10' not in src
        assert '⚠️ 超過10%' not in src
        assert 'PORTFOLIO_VAR_95_PERCENTILE' in src
        assert 'PORTFOLIO_VAR_99_PERCENTILE' in src
        assert 'PORTFOLIO_VAR_MONTHLY_WARN_PCT' in src


class TestImportContract:
    """確保所有 PR-G 常數可從 shared.signal_thresholds 直接 import。"""

    def test_all_pr_g_constants_importable(self):
        from shared.signal_thresholds import (  # noqa: F401
            ETF_CORR_HIGH_THRESHOLD,
            PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT,
            PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT,
            PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT,
            PORTFOLIO_STRESS_TEST_DROP_PCT,
            PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT,
            PORTFOLIO_VAR_95_PERCENTILE,
            PORTFOLIO_VAR_99_PERCENTILE,
            PORTFOLIO_VAR_MONTHLY_WARN_PCT,
        )
