"""v18.335 PR-H3 — 抽 4 個 SSOT 函式守衛測試。

R-2 audit Task C P2 「抽函式重構」+ R-3 audit Task C1 「分級邏輯抽出」實作:
1. etf_helpers.classify_etf_quick_sigma — ⚡短線 σ 分級(MA20±nσ 5段)
2. etf_helpers.classify_etf_deep_sigma  — 📅長線 σ 分級(MA240 z-score 4段)
3. etf_calc.calc_portfolio_stress_test  — 投組 S&P500 壓力測試
4. etf_helpers.compute_etf_annual_cashflow — 投組年配息彙整(月度分配)

驗證:
- 4 個函式契約 + 邊界
- caller migration(inline 已淨空)
- import 收斂(舊 ETF_QUICK_SIGMA_* / ETF_SIGMA_* 直引移除)
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from src.compute.etf import (
    classify_etf_deep_sigma,
    classify_etf_quick_sigma,
    compute_etf_annual_cashflow,
)


# ─────────── A. classify_etf_quick_sigma ───────────

class TestClassifyEtfQuickSigma:
    """⚡短線 σ 分級(MA20±nσ 5段戰情燈號)。"""

    def test_disaster_below_minus_3_sigma(self):
        # ma20=100, std=10, cur=65 → bias = (65-100)/10 = -3.5σ → 股災價
        r = classify_etf_quick_sigma(65.0, 100.0, 10.0)
        assert r is not None
        emoji, label, action = r
        assert emoji == '🟢🟢🟢'
        assert '股災價' in label
        assert '⚡短線' in label
        assert action == '大買 50%'

    def test_oversold_between_minus_2_and_3(self):
        # cur=75 → -2.5σ → 超跌價
        r = classify_etf_quick_sigma(75.0, 100.0, 10.0)
        emoji, label, action = r
        assert emoji == '🟢🟢'
        assert '超跌價' in label
        assert action == '買 30%'

    def test_cheap_between_minus_1_and_2(self):
        r = classify_etf_quick_sigma(85.0, 100.0, 10.0)
        emoji, label, action = r
        assert emoji == '🟢'
        assert '便宜價' in label
        assert action == '小買 20%'

    def test_neutral_within_one_sigma(self):
        r = classify_etf_quick_sigma(100.0, 100.0, 10.0)
        emoji, label, action = r
        assert emoji == '⚪'
        assert '中性區' in label
        assert action == '靜待訊號'

    def test_high_between_plus_1_5_and_2(self):
        # cur=117 → +1.7σ → 偏高
        r = classify_etf_quick_sigma(117.0, 100.0, 10.0)
        emoji, label, action = r
        assert emoji == '🟠'
        assert '偏高' in label
        assert action == '不追高/減碼'

    def test_overbought_above_plus_2(self):
        r = classify_etf_quick_sigma(125.0, 100.0, 10.0)
        emoji, label, action = r
        assert emoji == '🔴'
        assert '準備停利' in label
        assert action == '分批停利'

    def test_invalid_returns_none(self):
        assert classify_etf_quick_sigma(None, 100.0, 10.0) is None
        assert classify_etf_quick_sigma(100.0, None, 10.0) is None
        assert classify_etf_quick_sigma(100.0, 100.0, None) is None
        assert classify_etf_quick_sigma(100.0, 100.0, 0) is None
        assert classify_etf_quick_sigma(100.0, 100.0, -1) is None


# ─────────── B. classify_etf_deep_sigma ───────────

class TestClassifyEtfDeepSigma:
    """📅長線 σ 分級(MA240 z-score 4段教學)。"""

    def test_deep_buy_at_minus_2_sigma(self):
        # cur=80 vs ma240=100, std_pct_annual=20 → bias=-20%, z=-1.0
        # ETF_SIGMA_DEEP_BUY=-2 → z=-1 不夠深 → 進場買點(-1 ~ -2)
        r = classify_etf_deep_sigma(80.0, 100.0, 20.0)
        assert r is not None
        label, color, action = r
        # z=-1 落在 ETF_SIGMA_BUY 區
        assert '📅長線' in label
        assert color == 'green'

    def test_extreme_deep_buy(self):
        # cur=55, ma240=100, std=15 → bias=-45%, z=-3 → 極佳買點(≤-2)
        r = classify_etf_deep_sigma(55.0, 100.0, 15.0)
        label, color, action = r
        assert '極佳買點' in label
        assert color == 'green'

    def test_neutral_within_plus_minus_1(self):
        # cur=105, ma240=100, std=20 → bias=+5%, z=+0.25 → 持平區
        r = classify_etf_deep_sigma(105.0, 100.0, 20.0)
        label, color, action = r
        assert '持平區' in label
        assert color == 'yellow'

    def test_extreme_high(self):
        # cur=160, ma240=100, std=20 → bias=60%, z=+3 → 極端偏高(≥+2)
        r = classify_etf_deep_sigma(160.0, 100.0, 20.0)
        label, color, action = r
        assert '極端偏高' in label
        assert color == 'red'

    def test_invalid_returns_none(self):
        assert classify_etf_deep_sigma(None, 100.0, 20.0) is None
        assert classify_etf_deep_sigma(100.0, None, 20.0) is None
        assert classify_etf_deep_sigma(100.0, 100.0, None) is None
        assert classify_etf_deep_sigma(100.0, 100.0, 0) is None


# ─────────── C. calc_portfolio_stress_test ───────────

class TestCalcPortfolioStressTest:
    """投組壓力測試 S&P500 下跌 Beta 加權虧損。"""

    @patch('src.compute.etf.etf_calc.fetch_etf_info')
    def test_basic_two_etf_portfolio(self, mock_info):
        from src.compute.etf import calc_portfolio_stress_test
        mock_info.side_effect = [{'beta': 1.0}, {'beta': 0.5}]
        rows = [
            {'ticker': 'A', 'actual_pct': 60},
            {'ticker': 'B', 'actual_pct': 40},
        ]
        r = calc_portfolio_stress_test(rows, total_value=1_000_000)
        # A: 60% × 1.0 × -20% × 1M = -120,000
        # B: 40% × 0.5 × -20% × 1M =  -40,000
        # total = -160,000;loss_pct = 16%
        assert r['drop_pct'] == -20.0
        assert abs(r['total_loss'] - (-160_000)) < 1
        assert abs(r['loss_pct'] - 16.0) < 1e-6
        assert len(r['per_etf']) == 2

    @patch('src.compute.etf.etf_calc.fetch_etf_info')
    def test_beta_cast_failure_fallback_to_one(self, mock_info):
        from src.compute.etf import calc_portfolio_stress_test
        mock_info.return_value = {'beta': 'invalid'}
        rows = [{'ticker': 'X', 'actual_pct': 100}]
        r = calc_portfolio_stress_test(rows, total_value=1_000_000)
        # fallback beta=1.0 → loss = -200,000
        assert abs(r['total_loss'] - (-200_000)) < 1

    @patch('src.compute.etf.etf_calc.fetch_etf_info')
    def test_custom_drop_pct(self, mock_info):
        from src.compute.etf import calc_portfolio_stress_test
        mock_info.return_value = {'beta': 1.0}
        rows = [{'ticker': 'A', 'actual_pct': 100}]
        r = calc_portfolio_stress_test(rows, total_value=1_000_000, drop_pct=-30.0)
        assert r['drop_pct'] == -30.0
        assert abs(r['total_loss'] - (-300_000)) < 1


# ─────────── D. compute_etf_annual_cashflow ───────────

class TestComputeEtfAnnualCashflow:
    """投組年配息彙整 + 月度分配。"""

    def test_basic_quarterly_dividends(self):
        # 4 季配息各 1 元 × 100 股
        idx = pd.to_datetime(['2025-03-15', '2025-06-15', '2025-09-15', '2025-12-15'])
        div_series = pd.Series([1.0, 1.0, 1.0, 1.0], index=idx)
        with patch('pandas.Timestamp.now',
                   return_value=pd.Timestamp('2026-01-01')):
            r = compute_etf_annual_cashflow(div_series, shares=100)
        assert r is not None
        assert r['annual_per_share'] == 4.0
        assert r['estimated_income'] == 400.0
        assert r['n_payments'] == 4
        # 3/6/9/12 月各 100 元
        assert r['monthly_distribution'][3] == 100.0
        assert r['monthly_distribution'][6] == 100.0
        assert r['monthly_distribution'][9] == 100.0
        assert r['monthly_distribution'][12] == 100.0
        # 其他月份為 0
        assert r['monthly_distribution'][1] == 0.0

    def test_zero_shares_returns_none(self):
        idx = pd.to_datetime(['2025-06-15'])
        div_series = pd.Series([1.0], index=idx)
        assert compute_etf_annual_cashflow(div_series, shares=0) is None

    def test_empty_series_returns_none(self):
        assert compute_etf_annual_cashflow(pd.Series([], dtype=float), shares=100) is None

    def test_none_series_returns_none(self):
        assert compute_etf_annual_cashflow(None, shares=100) is None

    def test_old_dividends_outside_lookback(self):
        # 配息全在 2 年前 → 365 天 lookback 取不到 → None
        idx = pd.to_datetime(['2023-03-15'])
        div_series = pd.Series([1.0], index=idx)
        with patch('pandas.Timestamp.now',
                   return_value=pd.Timestamp('2026-01-01')):
            assert compute_etf_annual_cashflow(div_series, shares=100) is None


# ─────────── Caller migration ───────────

class TestCallerMigration:
    """inline 已淨空 — caller 已改 SSOT。"""

    def test_etf_calc_uses_classify_quick_sigma(self):
        src = open('src/compute/etf/etf_calc.py', encoding='utf-8').read()
        assert 'from src.compute.etf.etf_helpers import' in src
        assert 'classify_etf_quick_sigma' in src
        # inline 5 段 if-elif 已淨空
        assert "'🟢🟢🟢', f'⚡短線 股災價" not in src
        assert "ETF_QUICK_SIGMA_DISASTER * _std" not in src

    def test_etf_tab_single_uses_classify_deep_sigma(self):
        src = open('etf_tab_single.py', encoding='utf-8').read()
        assert 'classify_etf_deep_sigma' in src
        # inline z-score 5 段已淨空
        assert "if _z <= ETF_SIGMA_DEEP_BUY:" not in src

    def test_portfolio_uses_calc_portfolio_stress_test(self):
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        assert 'calc_portfolio_stress_test' in src
        # inline beta loop 已抽掉(剩 caller render)
        assert "beta_i  = info_i.get('beta')" not in src

    def test_portfolio_uses_compute_etf_annual_cashflow(self):
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        assert 'compute_etf_annual_cashflow' in src
        # 月度 inline loop 已淨空(_pay_months variable 已刪)
        assert '_pay_months = sorted(set' not in src


class TestImportContract:
    """import 收斂 — 舊常數直引已移除(由 SSOT 函式內部消費)。"""

    def test_etf_calc_no_direct_quick_sigma_imports(self):
        src = open('src/compute/etf/etf_calc.py', encoding='utf-8').read()
        # ETF_QUICK_SIGMA_* 5 個應該不再被 etf_calc 直引
        assert 'ETF_QUICK_SIGMA_CHEAP,' not in src
        assert 'ETF_QUICK_SIGMA_DISASTER,' not in src

    def test_etf_single_no_direct_sigma_imports(self):
        src = open('etf_tab_single.py', encoding='utf-8').read()
        # ETF_SIGMA_* 4 個應該不再被 single 直引
        assert 'ETF_SIGMA_BUY,' not in src
        assert 'ETF_SIGMA_DEEP_BUY,' not in src


class TestModulesImportable:
    def test_etf_helpers_clean(self):
        from src.compute.etf import etf_helpers  # noqa: F401

    def test_etf_calc_clean(self):
        from src.compute.etf import etf_calc  # noqa: F401

    def test_etf_tab_single_clean(self):
        import etf_tab_single  # noqa: F401

    def test_etf_tab_portfolio_clean(self):
        import etf_tab_portfolio  # noqa: F401
