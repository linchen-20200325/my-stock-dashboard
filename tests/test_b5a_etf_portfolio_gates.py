"""tests/test_b5a_etf_portfolio_gates.py — B5-a「ETF 組合三個假綠燈」行為測試。

對應 `src/compute/etf/portfolio_gates.py`（L2 純函式）。

━━ 這批測試在守什麼 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
實機（🏦 ETF → 組合分析，0050 40% / 00878 30% / VT 30%）三個綠燈同時說謊：

  E-1 「核心 100% / 衛星 0%」卻判「✅ 符合建議 60~80% / 20~40%」
  E-2 「✅ 無需再平衡，最大偏離 0.0%」（目標權重根本沒輸入）
  E-3 「✅ 任兩檔重疊 < 30%」（0050 中文股名 × VT 英文公司名，永遠對不上）

核心不變量（全檔反覆斷言）：
  **綠燈（STATUS_PASS）必須代表「算過且通過」。**
  沒資料 / 沒設定 / 量得到的上限本來就低於門檻 → 一律 STATUS_UNKNOWN。

寫法約定（避免「守衛照抄實作 → 永遠發現不了實作有問題」）：
  - 一律「建構輸入 → 呼叫函式 → 驗結果」，不比對原始碼字面。
  - 唯一的原始碼檢查是 §3.3 反捏造守衛，走 **AST**（不掃註解 / docstring），
    且它約束的是「實作不准出現未登記的魔術數字」——這種約束**無法**靠抄實作滿足。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared.signal_thresholds import (
    PORTFOLIO_CORE_SAT_TOLERANCE_PP,
    PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT,
    PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT,
    PORTFOLIO_TARGET_SUM_TOLERANCE_PP,
)
from src.compute.etf.portfolio_gates import (
    ROLE_BOND,
    ROLE_CORE,
    ROLE_SATELLITE,
    ROLE_UNKNOWN,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_UNKNOWN,
    assess_role_split,
    classify_portfolio_role,
    evaluate_core_satellite_gate,
    evaluate_overlap_gate,
    evaluate_rebalance_gate,
    holdings_coverage_pct,
    holdings_namespace,
    overlap_ceiling_pct,
)

# 實機那組（值為市值 TWD，比例 40 / 30 / 30）
LIVE_ROWS = [
    {'ticker': '0050.TW',  'value': 400_000.0},
    {'ticker': '00878.TW', 'value': 300_000.0},
    {'ticker': 'VT',       'value': 300_000.0},
]

# 台股來源（台灣 Yahoo / MoneyDJ）→ 中文股名；權重覆蓋率高
TW_HOLDINGS_0050 = {
    '台積電 (2330)': 55.0, '鴻海 (2317)': 5.0, '聯發科 (2454)': 4.0,
    '台達電 (2308)': 3.0, '富邦金 (2881)': 2.5, '中華電 (2412)': 2.0,
    '國泰金 (2882)': 2.0, '日月光投控 (3711)': 2.0, '廣達 (2382)': 2.0,
    '中信金 (2891)': 1.5,
}
TW_HOLDINGS_00878 = {
    '聯發科 (2454)': 4.5, '廣達 (2382)': 4.2, '華碩 (2357)': 4.0,
    '仁寶 (2324)': 3.8, '光寶科 (2301)': 3.5, '英業達 (2356)': 3.4,
    '緯創 (3231)': 3.3, '和碩 (4938)': 3.2, '瑞昱 (2379)': 3.1,
    '聯詠 (3034)': 3.0,
}
# 海外來源（yfinance funds_data.top_holdings）→ 英文公司名；只給前 10 大
US_HOLDINGS_VT = {
    'Apple Inc': 4.1, 'Microsoft Corp': 3.9, 'NVIDIA Corp': 3.6,
    'Amazon.com Inc': 2.2, 'Meta Platforms Inc': 1.5, 'Alphabet Inc Class A': 1.3,
    'Broadcom Inc': 1.2, 'Tesla Inc': 1.0,
    'Taiwan Semiconductor Manufacturing Co Ltd': 0.9, 'Eli Lilly and Co': 0.8,
}


# ══════════════════════════════════════════════════════════════════════════
# E-1｜核心 / 衛星
# ══════════════════════════════════════════════════════════════════════════

class TestClassifyPortfolioRole:
    """分類必須四態，且**債券先判**（否則 BND 會被核心白名單吃掉）。"""

    def test_market_cap_etf_is_core(self):
        assert classify_portfolio_role('0050.TW') == ROLE_CORE
        assert classify_portfolio_role('006208.TW') == ROLE_CORE

    def test_high_dividend_etf_is_satellite_not_core(self):
        # 這正是 E-1 的第二個根因：舊 `auto_role` 白名單把高股息也算「核心」。
        assert classify_portfolio_role('00878.TW') == ROLE_SATELLITE
        assert classify_portfolio_role('0056.TW') == ROLE_SATELLITE
        assert classify_portfolio_role('00713.TW') == ROLE_SATELLITE

    def test_overseas_broad_market_is_core(self):
        for _tk in ('VT', 'VTI', 'VOO', 'SPY'):
            assert classify_portfolio_role(_tk) == ROLE_CORE, _tk

    def test_bond_wins_over_core_whitelist(self):
        assert classify_portfolio_role('BND') == ROLE_BOND
        assert classify_portfolio_role('AGG') == ROLE_BOND
        assert classify_portfolio_role('00679B.TW') == ROLE_BOND

    def test_unknown_ticker_is_not_silently_core(self):
        # §1：查不到就說查不到，不硬塞桶（硬塞正是「核心 100%」的來源）。
        assert classify_portfolio_role('9999.TW') == ROLE_UNKNOWN
        assert classify_portfolio_role('ZZZZ') == ROLE_UNKNOWN

    @pytest.mark.parametrize('bad', [None, '', '   '])
    def test_empty_input(self, bad):
        assert classify_portfolio_role(bad) == ROLE_UNKNOWN


class TestAssessRoleSplit:
    def test_live_portfolio_is_not_100_percent_core(self):
        """E-1 回歸：實機那組**不是** 核心 100% / 衛星 0%。"""
        _s = assess_role_split(LIVE_ROWS)
        assert _s['core_pct'] == pytest.approx(70.0)        # 0050 + VT
        assert _s['satellite_pct'] == pytest.approx(30.0)   # 00878
        assert _s['unknown_pct'] == pytest.approx(0.0)
        assert _s['unclassified'] == []

    def test_bond_excluded_from_core_satellite_denominator(self):
        _s = assess_role_split([
            {'ticker': '0050.TW', 'value': 500.0},
            {'ticker': 'BND',     'value': 500.0},
        ])
        assert _s['core_pct'] == pytest.approx(100.0)        # 股票腿內 100%
        assert _s['bond_pct_of_total'] == pytest.approx(50.0)
        assert _s['equity_value'] == pytest.approx(500.0)

    def test_unclassified_is_surfaced(self):
        _s = assess_role_split([
            {'ticker': '0050.TW', 'value': 700.0},
            {'ticker': '9999.TW', 'value': 300.0},
        ])
        assert _s['unknown_pct'] == pytest.approx(30.0)
        assert _s['unclassified'] == ['9999.TW']

    def test_non_numeric_and_zero_values_skipped_not_zeroed(self):
        _s = assess_role_split([
            {'ticker': '0050.TW', 'value': 100.0},
            {'ticker': '00878.TW', 'value': None},
            {'ticker': '0056.TW', 'value': 'abc'},
            {'ticker': '00713.TW', 'value': 0},
        ])
        assert _s['equity_value'] == pytest.approx(100.0)
        assert _s['core_pct'] == pytest.approx(100.0)

    def test_empty_rows(self):
        _s = assess_role_split([])
        assert _s['equity_value'] == 0.0
        assert _s['core_pct'] == 0.0


class TestCoreSatelliteGate:
    def test_live_portfolio_passes_for_real(self):
        """實機那組 vs 中性目標 70% → 真的落在 60~80 帶內 → PASS。"""
        _g = evaluate_core_satellite_gate(LIVE_ROWS, target_core_pct=70.0,
                                          regime='neutral')
        assert _g['status'] == STATUS_PASS
        assert _g['band_lo'] == pytest.approx(60.0)
        assert _g['band_hi'] == pytest.approx(80.0)

    def test_core_shortfall_fails(self):
        """核心不足（衛星超標）→ FAIL。舊碼這一側本來就會紅。"""
        _g = evaluate_core_satellite_gate([
            {'ticker': '0050.TW',  'value': 100.0},
            {'ticker': '00878.TW', 'value': 900.0},
        ], target_core_pct=70.0)
        assert _g['status'] == STATUS_FAIL
        assert _g['split']['core_pct'] == pytest.approx(10.0)

    def test_core_excess_fails_this_is_the_e1_regression(self):
        """★E-1 回歸★ 核心 100% / 衛星 0%，目標 70% → **必須 FAIL**。

        舊實作 `portfolio_manager.check_rebalance` 的判定式
        `excess_ratio >= 0.10` 只抓「衛星超標」，衛星**不足** 30pp 會落到
        else 分支印「✅ 核衛比例符合（±10pp 容忍）」—— 畫面寫雙邊、判定單邊。
        """
        _g = evaluate_core_satellite_gate([
            {'ticker': '0050.TW',   'value': 600.0},
            {'ticker': '006208.TW', 'value': 400.0},
        ], target_core_pct=70.0, regime='neutral')
        assert _g['status'] == STATUS_FAIL
        assert _g['split']['core_pct'] == pytest.approx(100.0)
        assert _g['split']['satellite_pct'] == pytest.approx(0.0)
        assert '✅' not in _g['headline']

    def test_exactly_on_band_edge_passes(self):
        """邊界值：剛好落在 band 端點 → 仍算通過（判定式是 `> tol` 才失敗）。"""
        _g = evaluate_core_satellite_gate([
            {'ticker': '0050.TW',  'value': 800.0},
            {'ticker': '00878.TW', 'value': 200.0},
        ], target_core_pct=70.0)
        assert _g['split']['core_pct'] == pytest.approx(80.0)
        assert _g['status'] == STATUS_PASS

    def test_missing_target_is_unknown_not_green(self):
        _g = evaluate_core_satellite_gate(LIVE_ROWS, target_core_pct=None)
        assert _g['status'] == STATUS_UNKNOWN
        assert '✅' not in _g['headline']

    def test_all_bond_portfolio_is_unknown_not_green(self):
        """全債券 → 股票腿分母為 0 → 無法判定（舊碼會算成核心 100% 綠燈）。"""
        _g = evaluate_core_satellite_gate([
            {'ticker': 'BND', 'value': 1000.0},
        ], target_core_pct=70.0)
        assert _g['status'] == STATUS_UNKNOWN

    def test_unclassified_straddling_band_is_unknown(self):
        """未分類部位會左右結論 → 不下判斷。"""
        _g = evaluate_core_satellite_gate([
            {'ticker': '0050.TW',  'value': 550.0},   # 核心 55%
            {'ticker': '9999.TW',  'value': 200.0},   # 未知 20%
            {'ticker': '00878.TW', 'value': 250.0},   # 衛星 25%
        ], target_core_pct=70.0)
        # core 區間 = [55, 75]，band = [60, 80] → 跨過 60 這條邊
        assert _g['status'] == STATUS_UNKNOWN
        assert _g['core_pct_min'] == pytest.approx(55.0)
        assert _g['core_pct_max'] == pytest.approx(75.0)
        assert '9999.TW' in _g['detail']

    def test_unclassified_but_verdict_still_robust_gives_fail(self):
        """未分類存在、但不管怎麼歸都出界 → 仍可下 FAIL（不濫用 unknown）。"""
        _g = evaluate_core_satellite_gate([
            {'ticker': '00878.TW', 'value': 950.0},   # 衛星 95%
            {'ticker': '9999.TW',  'value': 50.0},    # 未知 5%
        ], target_core_pct=70.0)
        # core 區間 = [0, 5]，整段都 < 60 → 結論穩健
        assert _g['status'] == STATUS_FAIL

    def test_default_tolerance_comes_from_ssot(self):
        """§3.3：不帶 tolerance 呼叫時，容忍帶必須等於 SSOT 常數（非 inline 10）。"""
        _g = evaluate_core_satellite_gate(LIVE_ROWS, target_core_pct=70.0)
        assert _g['tolerance_pp'] == pytest.approx(PORTFOLIO_CORE_SAT_TOLERANCE_PP)
        assert _g['band_lo'] == pytest.approx(70.0 - PORTFOLIO_CORE_SAT_TOLERANCE_PP)
        assert _g['band_hi'] == pytest.approx(70.0 + PORTFOLIO_CORE_SAT_TOLERANCE_PP)

    def test_tolerance_is_two_sided(self):
        """同一個偏離量，往上偏 / 往下偏必須被同等對待。"""
        _up = evaluate_core_satellite_gate([
            {'ticker': '0050.TW',  'value': 850.0},
            {'ticker': '00878.TW', 'value': 150.0},
        ], target_core_pct=70.0)                       # core 85% = +15pp
        _down = evaluate_core_satellite_gate([
            {'ticker': '0050.TW',  'value': 550.0},
            {'ticker': '00878.TW', 'value': 450.0},
        ], target_core_pct=70.0)                       # core 55% = -15pp
        assert _up['status'] == _down['status'] == STATUS_FAIL


# ══════════════════════════════════════════════════════════════════════════
# E-2｜再平衡
# ══════════════════════════════════════════════════════════════════════════

class TestRebalanceGate:
    def test_no_targets_is_unknown_this_is_the_e2_regression(self):
        """★E-2 回歸★ 使用者沒填目標 → **必須是 unknown，不是「無需再平衡」**。

        舊碼在這種情況把「現況」抄成目標（`target_pct = actual_pct`），
        偏離度恆為 0.0 → 永遠印「✅ 所有標的偏離度均在 ±5% 內，無需再平衡」。
        """
        _g = evaluate_rebalance_gate([
            {'ticker': '0050.TW',  'actual_pct': 40.0, 'target_pct': None},
            {'ticker': '00878.TW', 'actual_pct': 30.0, 'target_pct': None},
            {'ticker': 'VT',       'actual_pct': 30.0, 'target_pct': None},
        ], tolerance_pp=5)
        assert _g['status'] == STATUS_UNKNOWN
        assert _g['status'] != STATUS_PASS
        assert '✅' not in _g['headline']
        assert _g['breaches'] == []
        assert len(_g['missing_targets']) == 3

    def test_user_set_targets_equal_to_actual_do_pass(self):
        """對照組（與上一條**不衝突**）：目標是使用者**明確填**的、且剛好等於現況
        → 這是真的「已平衡」，PASS 合理。

        兩條的差別在 `target_pct` 是 None（沒設定）還是有值（設定了）——
        同一函式、不同輸入、不同預期，彼此相容。
        """
        _g = evaluate_rebalance_gate([
            {'ticker': '0050.TW',  'actual_pct': 40.0, 'target_pct': 40.0},
            {'ticker': '00878.TW', 'actual_pct': 30.0, 'target_pct': 30.0},
            {'ticker': 'VT',       'actual_pct': 30.0, 'target_pct': 30.0},
        ], tolerance_pp=5)
        assert _g['status'] == STATUS_PASS
        assert _g['target_sum'] == pytest.approx(100.0)
        assert all(abs(v) < 1e-9 for v in _g['deviations'].values())

    def test_partial_targets_is_unknown(self):
        _g = evaluate_rebalance_gate([
            {'ticker': '0050.TW',  'actual_pct': 40.0, 'target_pct': 60.0},
            {'ticker': '00878.TW', 'actual_pct': 30.0, 'target_pct': None},
            {'ticker': 'VT',       'actual_pct': 30.0, 'target_pct': None},
        ], tolerance_pp=5)
        assert _g['status'] == STATUS_UNKNOWN
        assert _g['missing_targets'] == ['00878.TW', 'VT']

    def test_targets_not_summing_to_100_is_unknown(self):
        _g = evaluate_rebalance_gate([
            {'ticker': '0050.TW',  'actual_pct': 50.0, 'target_pct': 50.0},
            {'ticker': '00878.TW', 'actual_pct': 50.0, 'target_pct': 30.0},
        ], tolerance_pp=5)
        assert _g['status'] == STATUS_UNKNOWN
        assert _g['target_sum'] == pytest.approx(80.0)

    def test_rounding_slack_within_ssot_tolerance_still_evaluated(self):
        """33.3 × 3 = 99.9 → 在 SSOT 容差內，仍應照常判定（不因四捨五入卡死）。"""
        assert PORTFOLIO_TARGET_SUM_TOLERANCE_PP >= 0.1
        _g = evaluate_rebalance_gate([
            {'ticker': 'A', 'actual_pct': 33.3, 'target_pct': 33.3},
            {'ticker': 'B', 'actual_pct': 33.3, 'target_pct': 33.3},
            {'ticker': 'C', 'actual_pct': 33.4, 'target_pct': 33.3},
        ], tolerance_pp=5)
        assert _g['status'] == STATUS_PASS

    def test_breach_direction_and_amounts(self):
        _g = evaluate_rebalance_gate([
            {'ticker': '0050.TW',  'actual_pct': 40.0, 'target_pct': 60.0},
            {'ticker': '00878.TW', 'actual_pct': 60.0, 'target_pct': 40.0},
        ], tolerance_pp=5)
        assert _g['status'] == STATUS_FAIL
        _by_tk = {b['ticker']: b for b in _g['breaches']}
        assert _by_tk['0050.TW']['deviation_pp'] == pytest.approx(-20.0)
        assert _by_tk['0050.TW']['action'] == '買進'      # 不足 → 買
        assert _by_tk['00878.TW']['deviation_pp'] == pytest.approx(20.0)
        assert _by_tk['00878.TW']['action'] == '賣出'     # 超標 → 賣

    def test_deviation_exactly_at_tolerance_passes(self):
        """邊界：偏離剛好等於容忍值 → 不觸發（判定式是嚴格大於）。"""
        _g = evaluate_rebalance_gate([
            {'ticker': 'A', 'actual_pct': 55.0, 'target_pct': 50.0},
            {'ticker': 'B', 'actual_pct': 45.0, 'target_pct': 50.0},
        ], tolerance_pp=5)
        assert _g['status'] == STATUS_PASS

    def test_deviation_just_over_tolerance_fails(self):
        _g = evaluate_rebalance_gate([
            {'ticker': 'A', 'actual_pct': 55.1, 'target_pct': 50.0},
            {'ticker': 'B', 'actual_pct': 44.9, 'target_pct': 50.0},
        ], tolerance_pp=5)
        assert _g['status'] == STATUS_FAIL
        assert len(_g['breaches']) == 2

    @pytest.mark.parametrize('bad_tol', [0, -1, None, 'abc'])
    def test_invalid_tolerance_is_unknown(self, bad_tol):
        _g = evaluate_rebalance_gate(
            [{'ticker': 'A', 'actual_pct': 100.0, 'target_pct': 100.0}],
            tolerance_pp=bad_tol)
        assert _g['status'] == STATUS_UNKNOWN

    def test_empty_portfolio_is_unknown(self):
        assert evaluate_rebalance_gate([], tolerance_pp=5)['status'] == STATUS_UNKNOWN


# ══════════════════════════════════════════════════════════════════════════
# E-3｜持股重疊
# ══════════════════════════════════════════════════════════════════════════

class TestHoldingsHelpers:
    def test_namespace_detection(self):
        assert holdings_namespace(TW_HOLDINGS_0050) == 'zh'
        assert holdings_namespace(US_HOLDINGS_VT) == 'en'
        assert holdings_namespace({'台積電': 1.0, 'Apple Inc': 1.0}) == 'mixed'
        assert holdings_namespace(None) == 'empty'
        assert holdings_namespace({}) == 'empty'

    def test_coverage_pct(self):
        assert holdings_coverage_pct({'台積電': 55.0, '鴻海': 5.0}) == pytest.approx(60.0)
        assert holdings_coverage_pct(US_HOLDINGS_VT) == pytest.approx(20.5)
        assert holdings_coverage_pct(None) == 0.0
        # 超過 100 上限夾住（來源權重加總異常時不外溢）
        assert holdings_coverage_pct({f'股{i}': 30.0 for i in range(10)}) == 100.0

    def test_weight_ceiling_is_min_coverage(self):
        _low = {'Apple Inc': 4.0, 'Microsoft Corp': 3.0}          # 覆蓋 7%
        _high = {'台積電': 55.0, '鴻海': 20.0}                     # 覆蓋 75%
        assert overlap_ceiling_pct(_low, _high, 'weight') == pytest.approx(7.0)

    def test_jaccard_ceiling_is_size_ratio(self):
        _a = {f'股{i}': 1.0 for i in range(10)}
        _b = {f'股{i}': 1.0 for i in range(40)}
        assert overlap_ceiling_pct(_a, _b, 'jaccard') == pytest.approx(25.0)

    def test_ceiling_of_empty_is_zero(self):
        assert overlap_ceiling_pct(None, TW_HOLDINGS_0050, 'weight') == 0.0
        assert overlap_ceiling_pct({}, TW_HOLDINGS_0050, 'jaccard') == 0.0


class TestOverlapGate:
    def test_cross_market_pair_is_unknown_not_zero_percent(self):
        """★E-3 回歸★ 0050（中文股名）× VT（英文公司名）→ **不得**判成綠燈。

        兩邊都持有台積電，但一邊叫「台積電 (2330)」、一邊叫
        `Taiwan Semiconductor Manufacturing Co Ltd` → 交集恆為空 → 算出 0%。
        舊碼把這個 0% 當成「不重疊」直接印綠燈。
        """
        _g = evaluate_overlap_gate(
            {'0050.TW': TW_HOLDINGS_0050, 'VT': US_HOLDINGS_VT},
            ['0050.TW', 'VT'], method='weight')
        assert _g['status'] == STATUS_UNKNOWN
        _p = _g['pairs'][0]
        assert _p['value_pct'] == pytest.approx(0.0)   # 原始數字確實是 0
        assert _p['status'] != 'ok'                    # 但不算「已比對通過」
        assert _p['common_holdings'] == 0
        assert '✅' not in _g['headline']

    def test_missing_holdings_pair_is_unknown_not_green(self):
        """★E-3 回歸★ 有一檔抓不到成分股 → 整體 unknown（舊碼 NaN 被跳過 = 綠燈）。"""
        _g = evaluate_overlap_gate(
            {'0050.TW': TW_HOLDINGS_0050, '00878.TW': TW_HOLDINGS_00878,
             '9999.TW': None},
            ['0050.TW', '00878.TW', '9999.TW'], method='weight')
        assert _g['status'] == STATUS_UNKNOWN
        _no_data = [p for p in _g['pairs'] if p['status'] == 'no_data']
        assert len(_no_data) == 2
        assert _g['measured_pairs'] == 1        # 只有 0050 × 00878 真的比到
        assert _g['total_pairs'] == 3

    def test_low_coverage_pair_cannot_conclude(self):
        """★E-3 回歸★ 可測上限 ≤ 門檻 → 這對「不可能失敗」→ 不給綠燈。"""
        _a = {'Apple Inc': 4.0, 'Microsoft Corp': 3.0}      # 覆蓋 7%
        _b = {'Apple Inc': 5.0, 'Tesla Inc': 2.0}           # 覆蓋 7%
        _g = evaluate_overlap_gate({'X': _a, 'Y': _b}, ['X', 'Y'], method='weight')
        assert _g['status'] == STATUS_UNKNOWN
        assert _g['pairs'][0]['status'] == 'inconclusive_ceiling'
        assert _g['pairs'][0]['ceiling_pct'] <= _g['threshold_pct']

    def test_genuine_pass_requires_real_measurement(self):
        """真的比對過、覆蓋率夠、且低於門檻 → 才給 PASS。"""
        _a = {'台積電': 50.0, '鴻海': 30.0, '聯發科': 10.0}   # 覆蓋 90%
        _b = {'台積電': 8.0, '中華電': 50.0, '台塑': 32.0}     # 覆蓋 90%
        _g = evaluate_overlap_gate({'A': _a, 'B': _b}, ['A', 'B'], method='weight')
        assert _g['status'] == STATUS_PASS
        assert _g['pairs'][0]['status'] == 'ok'
        assert _g['pairs'][0]['value_pct'] == pytest.approx(8.0)
        assert _g['measured_pairs'] == _g['total_pairs'] == 1

    def test_breach_wins_over_unknown(self):
        """有一對確定超標 → 整體 FAIL（超標是硬事實，不被 unknown 稀釋）。"""
        _g = evaluate_overlap_gate(
            {'A': TW_HOLDINGS_0050, 'B': dict(TW_HOLDINGS_0050), 'C': None},
            ['A', 'B', 'C'], method='weight')
        assert _g['status'] == STATUS_FAIL
        assert len(_g['breaches']) == 1
        assert _g['breaches'][0]['value_pct'] > _g['threshold_pct']

    def test_single_ticker_is_unknown(self):
        _g = evaluate_overlap_gate({'0050.TW': TW_HOLDINGS_0050}, ['0050.TW'])
        assert _g['status'] == STATUS_UNKNOWN
        assert _g['total_pairs'] == 0

    def test_all_missing_is_unknown(self):
        _g = evaluate_overlap_gate({'A': None, 'B': None}, ['A', 'B'])
        assert _g['status'] == STATUS_UNKNOWN
        assert _g['measured_pairs'] == 0

    def test_default_threshold_comes_from_ssot_per_method(self):
        """§3.3：門檻不得 inline —— weight / jaccard 各自對上 SSOT 常數。"""
        _w = evaluate_overlap_gate({'A': TW_HOLDINGS_0050, 'B': TW_HOLDINGS_00878},
                                   ['A', 'B'], method='weight')
        _j = evaluate_overlap_gate({'A': TW_HOLDINGS_0050, 'B': TW_HOLDINGS_00878},
                                   ['A', 'B'], method='jaccard')
        assert _w['threshold_pct'] == pytest.approx(PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT)
        assert _j['threshold_pct'] == pytest.approx(PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT)

    def test_pair_detail_is_auditable(self):
        """每一對都要帶得出「憑什麼這樣判」的數字，讓使用者能自己驗。"""
        _g = evaluate_overlap_gate(
            {'0050.TW': TW_HOLDINGS_0050, 'VT': US_HOLDINGS_VT},
            ['0050.TW', 'VT'])
        _p = _g['pairs'][0]
        for _k in ('a', 'b', 'value_pct', 'ceiling_pct', 'coverage_a_pct',
                   'coverage_b_pct', 'common_holdings', 'namespace_a',
                   'namespace_b', 'status', 'reason'):
            assert _k in _p, _k
        assert _p['reason']


# ══════════════════════════════════════════════════════════════════════════
# 跨閘門不變量
# ══════════════════════════════════════════════════════════════════════════

class TestGreenLightInvariant:
    """全域鐵律：任何「缺料 / 沒設定 / 量不到」的輸入，三個閘門都不得回 PASS。"""

    def test_no_gate_returns_pass_on_missing_inputs(self):
        _cases = [
            evaluate_core_satellite_gate([], target_core_pct=70.0),
            evaluate_core_satellite_gate(LIVE_ROWS, target_core_pct=None),
            evaluate_rebalance_gate(
                [{'ticker': 'A', 'actual_pct': 100.0, 'target_pct': None}],
                tolerance_pp=5),
            evaluate_overlap_gate({'A': None, 'B': None}, ['A', 'B']),
            evaluate_overlap_gate({}, []),
        ]
        for _g in _cases:
            assert _g['status'] == STATUS_UNKNOWN, _g['headline']
            assert '✅' not in _g['headline'], _g['headline']

    def test_every_verdict_has_actionable_detail(self):
        """unknown 一定要說「缺什麼」，否則使用者只會看到一個沒用的灰燈。"""
        for _g in (
            evaluate_core_satellite_gate(LIVE_ROWS, target_core_pct=None),
            evaluate_rebalance_gate(
                [{'ticker': 'A', 'actual_pct': 100.0, 'target_pct': None}],
                tolerance_pp=5),
            evaluate_overlap_gate({'A': None, 'B': None}, ['A', 'B']),
        ):
            assert _g['status'] == STATUS_UNKNOWN
            assert len(_g['detail']) > 10, _g


# ══════════════════════════════════════════════════════════════════════════
# §3.3 反捏造守衛（AST，非字串掃描）
# ══════════════════════════════════════════════════════════════════════════

_GATES_PATH = (pathlib.Path(__file__).resolve().parents[1]
               / 'src' / 'compute' / 'etf' / 'portfolio_gates.py')

# 允許的「結構性」數字：索引 / round 位數 / 百分比換算 / 空值哨兵。
# 任何**門檻語意**的數字（10 / 30 / 50 …）都必須從 shared/signal_thresholds 進來。
_ALLOWED_NUMBERS = frozenset({0, 1, 2, 4, 100})


class TestNoInlineMagicThresholds:
    def test_gates_module_has_no_inline_threshold_literals(self):
        """§3.3：判定門檻不得寫死在 portfolio_gates.py。

        用 AST 走訪（`ast.Constant` 且值為 int/float），因此註解與 docstring
        裡的數字**不會**被誤判。失敗時印出該行原文，方便定位。
        """
        _src = _GATES_PATH.read_text(encoding='utf-8')
        _lines = _src.splitlines()
        _bad = []
        for _node in ast.walk(ast.parse(_src)):
            if not isinstance(_node, ast.Constant):
                continue
            if isinstance(_node.value, bool) or not isinstance(_node.value, (int, float)):
                continue
            if _node.value in _ALLOWED_NUMBERS:
                continue
            _ln = getattr(_node, 'lineno', 0)
            _bad.append(f'  L{_ln}: {_node.value!r}  ← {_lines[_ln - 1].strip()}')
        assert not _bad, (
            'portfolio_gates.py 出現未登記的數字常數（§3.3 反捏造）。\n'
            '門檻類數字請放 shared/signal_thresholds.py 並 import；\n'
            f'若確為結構性常數請加入 _ALLOWED_NUMBERS：\n' + '\n'.join(_bad))
