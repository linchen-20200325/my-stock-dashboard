"""v18.329 PR-D ETF SSOT 守衛測試 — ETF audit 三項違憲修正驗證:
1. P3:4 個 inline magic(DIV_YOY / INCEPTION / CAGR / TE)抽 SSOT
2. P1:yield_valuation_zone / dividend_health_label 抽 etf_helpers SSOT(多檔 / 組合 Tab 共用)
3. P2:折溢價 4 段 + σ位階 4 段閾值抽 SSOT(單檔 Tab inline UX 保留,只換閾值)
4. C4:5 處裸 except 補 log
"""
from __future__ import annotations

import shared.signal_thresholds as st_mod


class TestEtfBasicThresholds:
    """P3 — 4 個 inline magic 抽 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.ETF_DIV_YOY_DECLINE_PCT == -10.0
        assert st_mod.ETF_INCEPTION_YEARS_MIN == 3.0
        assert st_mod.ETF_CAGR_TARGET_PCT == 7.0
        assert st_mod.ETF_TRACKING_ERROR_MAX_PCT == 1.5

    def test_no_inline_in_etf_tab_single(self):
        src = open('etf_tab_single.py', encoding='utf-8').read()
        assert '_div_yoy < -10' not in src
        assert '_cagr3 >= 7' not in src
        assert '_incept_yrs >= 3' not in src
        assert 'te > 1.5' not in src
        assert 'ETF_DIV_YOY_DECLINE_PCT' in src
        assert 'ETF_CAGR_TARGET_PCT' in src
        assert 'ETF_INCEPTION_YEARS_MIN' in src
        assert 'ETF_TRACKING_ERROR_MAX_PCT' in src

    def test_no_cagr_inline_in_grp_compare(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'cagr_3y >= 7' not in src  # 改用 SSOT


class TestEtfPremiumThresholds:
    """P2 — 折溢價 4 段閾值抽 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.ETF_PREMIUM_DEEP_DISCOUNT_PCT == -2.0
        assert st_mod.ETF_PREMIUM_FAIR_DISCOUNT_PCT == -0.5
        assert st_mod.ETF_PREMIUM_FAIR_PREMIUM_PCT == 1.0
        assert st_mod.ETF_PREMIUM_HIGH_PREMIUM_PCT == 3.0

    def test_monotone_order(self):
        assert (st_mod.ETF_PREMIUM_DEEP_DISCOUNT_PCT
                < st_mod.ETF_PREMIUM_FAIR_DISCOUNT_PCT
                < st_mod.ETF_PREMIUM_FAIR_PREMIUM_PCT
                < st_mod.ETF_PREMIUM_HIGH_PREMIUM_PCT)

    def test_no_inline_in_single(self):
        src = open('etf_tab_single.py', encoding='utf-8').read()
        assert '_pct <= -2' not in src
        assert '_pct <= -0.5' not in src
        assert '_pct <= 1.0' not in src
        assert '_pct <= 3.0' not in src
        assert 'ETF_PREMIUM_DEEP_DISCOUNT_PCT' in src
        assert 'ETF_PREMIUM_HIGH_PREMIUM_PCT' in src


class TestEtfSigmaThresholds:
    """P2 — σ位階 4 段閾值抽 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.ETF_SIGMA_DEEP_BUY == -2.0
        assert st_mod.ETF_SIGMA_BUY == -1.0
        assert st_mod.ETF_SIGMA_REDUCE == 1.0
        assert st_mod.ETF_SIGMA_STOP_PROFIT == 2.0

    def test_monotone_order(self):
        assert (st_mod.ETF_SIGMA_DEEP_BUY
                < st_mod.ETF_SIGMA_BUY
                < st_mod.ETF_SIGMA_REDUCE
                < st_mod.ETF_SIGMA_STOP_PROFIT)

    def test_no_inline_in_single(self):
        """v18.335 PR-H3:single 已改用 classify_etf_deep_sigma SSOT,
        ETF_SIGMA_* 常數由 etf_helpers 內部消費(不再直引)。"""
        src = open('etf_tab_single.py', encoding='utf-8').read()
        assert '_z <= -2' not in src
        assert '_z <= -1' not in src
        assert '_z <= 1' not in src
        assert '_z <= 2' not in src
        # single 改用 classify_etf_deep_sigma(PR-H3)
        assert 'classify_etf_deep_sigma' in src
        # 常數仍被 etf_helpers SSOT 消費
        helpers_src = open('etf_helpers.py', encoding='utf-8').read()
        assert 'ETF_SIGMA_DEEP_BUY' in helpers_src
        assert 'ETF_SIGMA_STOP_PROFIT' in helpers_src


class TestEtfHelpersSSOT:
    """P1 — yield_valuation_zone / dividend_health_label 抽 etf_helpers SSOT。"""

    def test_functions_in_etf_helpers(self):
        import etf_helpers
        assert hasattr(etf_helpers, 'yield_valuation_zone'), \
            'etf_helpers 缺 yield_valuation_zone()'
        assert hasattr(etf_helpers, 'dividend_health_label'), \
            'etf_helpers 缺 dividend_health_label()'

    def test_grp_compare_uses_ssot(self):
        """組合比較 Tab 走 SSOT,無 file-local 重複定義。"""
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'def _yield_valuation_zone(' not in src
        assert 'def _dividend_health_label(' not in src
        # import alias 形式
        assert 'yield_valuation_zone' in src
        assert 'dividend_health_label' in src

    def test_yield_valuation_zone_behavior(self):
        from etf_helpers import yield_valuation_zone
        # 7%+ 強烈買進
        assert '強烈買進' in yield_valuation_zone(7.5, 5.0)
        # 3%- 獲利了結
        assert '獲利了結' in yield_valuation_zone(2.5, 5.0)
        # 3-5% 適度減碼
        assert '適度減碼' in yield_valuation_zone(4.0, 5.0)
        # 5-7% 中性持有
        assert '中性持有' in yield_valuation_zone(6.0, 5.0)
        # 無 avg_yield → 不判定
        assert yield_valuation_zone(5.0, None) == '—'
        assert yield_valuation_zone(5.0, 0) == '—'

    def test_dividend_health_label_behavior(self):
        from etf_helpers import dividend_health_label
        # 含息 >= 殖利率 → 雙贏
        assert '雙贏' in dividend_health_label(5.0, 10.0, None)
        # 含息 < 殖利率 → 吃本金
        assert '吃本金' in dividend_health_label(5.0, 3.0, None)
        # 無配息 + CAGR>=7 → 無息但達標
        assert '無息但達標' in dividend_health_label(0, None, 10.0)
        # 無配息 + CAGR<7 → 無息且未達標
        assert '無息且未達標' in dividend_health_label(0, None, 3.0)
        # 全缺 → 資料不足
        assert '資料不足' in dividend_health_label(0, None, None)


class TestNoBareExceptInETF:
    """C4 — 5 處裸 except: pass 補 log。"""

    def test_no_bare_pass_in_etf_tab_single(self):
        """etf_tab_single 不再有「except Exception: pass」(裸 pass)。"""
        src = open('etf_tab_single.py', encoding='utf-8').read()
        # 裸 except + pass(允許 except 加 log/print)
        assert 'except Exception:\n            pass' not in src
        assert 'except Exception:\n                pass' not in src

    def test_no_bare_pass_in_etf_tab_grp_compare(self):
        src = open('etf_tab_grp_compare.py', encoding='utf-8').read()
        assert 'except Exception:\n            pass' not in src
        assert 'except Exception:\n                pass' not in src
