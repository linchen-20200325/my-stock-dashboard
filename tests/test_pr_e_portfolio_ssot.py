"""v18.330 PR-E ETF portfolio SSOT 守衛測試 — 三項未結案修正驗證:
1. U-4:VCP 最低天數抽 SSOT(etf_calc + etf_tab_single 兩處同值)
2. U-5:etf_tab_portfolio 裸 except 補 log
3. U-6:流動性評分 4 個閾值抽 SSOT(etf_calc.calc_liquidity_score 內部)
"""
from __future__ import annotations

import shared.signal_thresholds as st_mod


class TestEtfVcpMinDaysSSOT:
    """U-4 — VCP 最低天數抽 SSOT。"""

    def test_constant_exists_and_value(self):
        assert st_mod.ETF_VCP_MIN_DAYS == 210

    def test_no_inline_in_etf_calc(self):
        src = open('etf_calc.py', encoding='utf-8').read()
        assert 'len(df) < 210' not in src
        assert 'ETF_VCP_MIN_DAYS' in src

    def test_no_inline_in_etf_tab_single(self):
        src = open('etf_tab_single.py', encoding='utf-8').read()
        assert 'len(df) < 210' not in src
        assert 'ETF_VCP_MIN_DAYS' in src


class TestEtfLiquiditySSOT:
    """U-6 — 流動性評分 4 個閾值抽 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.ETF_AVG_VOL_20D_LOW_LOTS == 500
        assert st_mod.ETF_AVG_VOL_20D_FAIR_LOTS == 1000
        assert st_mod.ETF_AUM_LOW_YI == 5.0
        assert st_mod.ETF_AUM_FAIR_YI == 10.0

    def test_volume_monotone(self):
        assert st_mod.ETF_AVG_VOL_20D_LOW_LOTS < st_mod.ETF_AVG_VOL_20D_FAIR_LOTS

    def test_aum_monotone(self):
        assert st_mod.ETF_AUM_LOW_YI < st_mod.ETF_AUM_FAIR_YI

    def test_no_inline_in_etf_calc(self):
        src = open('etf_calc.py', encoding='utf-8').read()
        # 函式內 inline 已退役
        assert '_avg < 500' not in src
        assert '_avg < 1000' not in src
        assert '_aum_e < 5\n' not in src and '_aum_e < 5:' not in src
        assert '_aum_e < 10' not in src
        # SSOT 引用
        assert 'ETF_AVG_VOL_20D_LOW_LOTS' in src
        assert 'ETF_AUM_LOW_YI' in src


class TestEtfPortfolioNoSilentExcept:
    """U-5 — 裸 except + pass 補 log。"""

    def test_no_bare_pass_in_portfolio(self):
        """etf_tab_portfolio 不應有「except Exception: pass」(裸 pass 模式)。"""
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        # 常見裸 pass 縮排:8/12/16/20 spaces
        assert 'except Exception:\n            pass' not in src
        assert 'except Exception:\n                pass' not in src
        assert 'except Exception:\n                    pass' not in src

    def test_diagnostic_prints_present(self):
        """補 log 後應該至少有 5 個 [etf_tab_portfolio] print 標籤。"""
        src = open('etf_tab_portfolio.py', encoding='utf-8').read()
        assert src.count('[etf_tab_portfolio]') >= 5


class TestLiquidityScoreBehavior:
    """U-6 行為測試:確保抽 SSOT 後 calc_liquidity_score 邏輯不變。"""

    def test_normal_liquidity(self):
        """高均量 + 高 AUM → 🟢"""
        import pandas as pd
        from etf_calc import calc_liquidity_score
        # 假造 30 日 5000 張均量
        df = pd.DataFrame({'Volume': [5_000_000] * 30})  # 5M 股 = 5000 張
        result = calc_liquidity_score(df, aum=20_000_000_000)  # 200 億
        assert result['level'] == '🟢'

    def test_low_volume_red(self):
        """均量 < 500 張 → 🔴"""
        import pandas as pd
        from etf_calc import calc_liquidity_score
        df = pd.DataFrame({'Volume': [200_000] * 30})  # 200 張
        result = calc_liquidity_score(df, aum=20_000_000_000)
        assert result['level'] == '🔴'

    def test_low_aum_red(self):
        """AUM < 5 億 → 🔴"""
        import pandas as pd
        from etf_calc import calc_liquidity_score
        df = pd.DataFrame({'Volume': [5_000_000] * 30})
        result = calc_liquidity_score(df, aum=300_000_000)  # 3 億
        assert result['level'] == '🔴'

    def test_insufficient_data(self):
        """資料不足(< 5 日)→ ⚪"""
        import pandas as pd
        from etf_calc import calc_liquidity_score
        df = pd.DataFrame({'Volume': [5_000_000] * 3})
        result = calc_liquidity_score(df, aum=20_000_000_000)
        assert result['level'] == '⚪'
