"""v18.331 PR-F audit 殘留 SSOT 守衛測試 — 6 項未結案修正驗證:
U-7  etf_calc σ位階 hardcode 抽 SSOT
U-8  shared.thresholds 新增 classify_yield_zone() 函式
U-10 個股 Tab 布林帶邊界 0.97/0.95 抽 SSOT
U-11 個股 Tab 融資警戒消費 SSOT(MARGIN_BALANCE_WARN/OVERHEAT)
U-12 個股 Tab RS 帶狀 75/50 抽 SSOT
U-13 個股 Tab 月線乖離 ±20/15 抽 SSOT
"""
from __future__ import annotations

import shared.signal_thresholds as st_mod


class TestU7_EtfQuickSigma:
    """U-7 — etf_calc σ位階 5 段倍數抽 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.ETF_QUICK_SIGMA_DISASTER == 3.0
        assert st_mod.ETF_QUICK_SIGMA_OVERSOLD == 2.0
        assert st_mod.ETF_QUICK_SIGMA_CHEAP == 1.0
        assert st_mod.ETF_QUICK_SIGMA_HIGH == 1.5
        assert st_mod.ETF_QUICK_SIGMA_OVERBOUGHT == 2.0

    def test_no_inline_in_etf_calc(self):
        """v18.335 PR-H3:etf_calc 已改用 classify_etf_quick_sigma SSOT,
        ETF_QUICK_SIGMA_* 常數由 etf_helpers 內部消費(不再直引)。"""
        src = open('etf_calc.py', encoding='utf-8').read()
        # 函式內 inline 已退役
        assert '- 3 * _std' not in src
        assert '- 2 * _std' not in src
        assert '- 1 * _std' not in src
        assert '+ 1.5 * _std' not in src
        assert '+ 2 * _std' not in src
        # etf_calc 改用 classify_etf_quick_sigma(PR-H3 抽離分級邏輯)
        assert 'classify_etf_quick_sigma' in src
        # 常數仍被 etf_helpers SSOT 消費
        helpers_src = open('etf_helpers.py', encoding='utf-8').read()
        assert 'ETF_QUICK_SIGMA_DISASTER' in helpers_src
        assert 'ETF_QUICK_SIGMA_OVERBOUGHT' in helpers_src


class TestU8_ClassifyYieldZone:
    """U-8 — shared.thresholds 新增 classify_yield_zone() 函式。"""

    def test_function_exists(self):
        from shared.thresholds import classify_yield_zone
        assert callable(classify_yield_zone)

    def test_strong_buy_at_7pct(self):
        from shared.thresholds import classify_yield_zone
        label, code = classify_yield_zone(7.0)
        assert '強烈買進' in label
        assert code == 'strong_buy'

    def test_sell_below_3pct(self):
        from shared.thresholds import classify_yield_zone
        label, code = classify_yield_zone(2.5)
        assert '獲利了結' in label
        assert code == 'sell'

    def test_reduce_3_to_5(self):
        from shared.thresholds import classify_yield_zone
        label, code = classify_yield_zone(4.0)
        assert '適度減碼' in label
        assert code == 'reduce'

    def test_neutral_5_to_7(self):
        from shared.thresholds import classify_yield_zone
        label, code = classify_yield_zone(6.0)
        assert '中性持有' in label
        assert code == 'neutral'

    def test_none_input(self):
        from shared.thresholds import classify_yield_zone
        label, code = classify_yield_zone(None)
        assert label == '—'
        assert code == 'na'

    def test_avg_yield_zero_means_na(self):
        """ETF 場景:avg_yield=0 視為 N/A(無估值脈絡)。"""
        from shared.thresholds import classify_yield_zone
        label, code = classify_yield_zone(5.0, avg_yield=0)
        assert code == 'na'

    def test_etf_helpers_delegates_to_classify(self):
        """etf_helpers.yield_valuation_zone 應 delegate 給 classify_yield_zone。"""
        from etf_helpers import yield_valuation_zone
        from shared.thresholds import classify_yield_zone
        # 同輸入應回同 label
        for cur, avg in [(7.5, 5.0), (2.5, 5.0), (4.0, 5.0), (6.0, 5.0)]:
            assert yield_valuation_zone(cur, avg) == classify_yield_zone(cur, avg)[0]


class TestU10_BollingerBands:
    """U-10 — 個股 Tab 布林帶邊界抽 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.BB_NEAR_UPPER_RATIO == 0.97
        assert st_mod.BB_DROP_OUT_RATIO == 0.95

    def test_drop_below_near(self):
        """drop_out < near_upper(防漂移)。"""
        assert st_mod.BB_DROP_OUT_RATIO < st_mod.BB_NEAR_UPPER_RATIO

    def test_no_inline_in_tab_stock(self):
        src = open('tab_stock.py', encoding='utf-8').read()
        assert '_bb_upper * 0.97' not in src
        assert '_bb_upper * 0.95' not in src
        assert 'BB_NEAR_UPPER_RATIO' in src
        assert 'BB_DROP_OUT_RATIO' in src


class TestU11_MarginBalance:
    """U-11 — 個股 Tab 融資警戒消費 SSOT(SSOT 早已存在,本次新增 caller)。"""

    def test_constants_exist_and_values(self):
        assert st_mod.MARGIN_BALANCE_WARN_THRESHOLD_YI == 2500.0
        assert st_mod.MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI == 3400.0

    def test_warn_below_overheat(self):
        """warn 黃線 < overheat 紅線。"""
        assert (st_mod.MARGIN_BALANCE_WARN_THRESHOLD_YI
                < st_mod.MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI)

    def test_no_inline_in_tab_stock(self):
        """tab_stock.py 不再有 inline 2500 / 3400 比較。"""
        src = open('tab_stock.py', encoding='utf-8').read()
        assert '_wr_margin2 < 2500' not in src
        assert '_wr_margin2 > 3400' not in src
        assert 'MARGIN_BALANCE_WARN_THRESHOLD_YI' in src
        assert 'MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI' in src


class TestU12_RsBands:
    """U-12 — 個股 Tab RS 帶狀抽 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.STOCK_RS_STRONG_MIN == 75.0
        assert st_mod.STOCK_RS_NEUTRAL_MIN == 50.0

    def test_strong_above_neutral(self):
        assert st_mod.STOCK_RS_STRONG_MIN > st_mod.STOCK_RS_NEUTRAL_MIN

    def test_no_inline_in_tab_stock(self):
        src = open('tab_stock.py', encoding='utf-8').read()
        assert '_rs_val >= 75' not in src
        assert '_rs_val >= 50' not in src
        assert 'STOCK_RS_STRONG_MIN' in src
        assert 'STOCK_RS_NEUTRAL_MIN' in src


class TestU13_BiasDeviation:
    """U-13 — 個股 Tab 月線乖離 ±20/±15 抽 SSOT。"""

    def test_constants_exist_and_values(self):
        assert st_mod.STOCK_BIAS_OVERHEAT_PCT == 20.0
        assert st_mod.STOCK_BIAS_DEEP_DEVIATION_PCT == 20.0
        assert st_mod.STOCK_BIAS_MILD_DEVIATION_PCT == 15.0

    def test_mild_below_overheat(self):
        assert (st_mod.STOCK_BIAS_MILD_DEVIATION_PCT
                < st_mod.STOCK_BIAS_OVERHEAT_PCT)

    def test_no_inline_in_tab_stock(self):
        src = open('tab_stock.py', encoding='utf-8').read()
        assert '_bias_i < -20' not in src
        assert '_bias_i > 20' not in src
        assert '_bias_20_i > 15' not in src
        assert 'STOCK_BIAS_OVERHEAT_PCT' in src
        assert 'STOCK_BIAS_MILD_DEVIATION_PCT' in src
