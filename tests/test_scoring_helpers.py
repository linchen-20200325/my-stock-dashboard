"""scoring_helpers.py 純函式 unit test — Phase 7H。"""
from __future__ import annotations

import pandas as pd
import pytest

from scoring_helpers import calc_fundamental_score, calc_health_score, health_grade


# ─────────────────────── calc_fundamental_score ───────────────────────

class TestCalcFundamentalScore:
    def test_returns_4_dimension_dict(self):
        result = calc_fundamental_score(None, None, None)
        assert set(result.keys()) == {'profit', 'growth', 'dividend', 'valuation'}
        for d in result.values():
            assert 'score' in d
            assert d['max'] == 3
            assert 'label' in d
            assert 'checks' in d

    def test_all_none_zero_scores(self):
        result = calc_fundamental_score(None, None, None)
        for dim in ('profit', 'growth', 'dividend', 'valuation'):
            assert result[dim]['score'] == 0

    def test_list_treated_as_no_data(self):
        # list 型 → 視為 None
        result = calc_fundamental_score([1, 2, 3], [4, 5, 6], None)
        for dim in ('profit', 'growth'):
            assert result[dim]['score'] == 0

    def test_empty_df_no_profit_points(self):
        result = calc_fundamental_score(pd.DataFrame(), pd.DataFrame(), None)
        assert result['profit']['score'] == 0

    def test_high_avg_div_gets_dividend_score(self):
        # avg_div=5 → score +1（>=4 給 2）
        result = calc_fundamental_score(None, None, 5.0)
        assert result['dividend']['score'] == 2
        assert result['dividend']['checks'][0][2] is True  # ok flag

    def test_low_avg_div_partial_dividend(self):
        # avg_div=3 → 2~4 之間 → score +1
        result = calc_fundamental_score(None, None, 3.0)
        assert result['dividend']['score'] == 1

    def test_zero_avg_div_no_dividend_score(self):
        # avg_div=0 → if 不滿足（>0），不加分
        result = calc_fundamental_score(None, None, 0)
        assert result['dividend']['score'] == 0

    def test_valuation_357_classification(self):
        # >7% → 3 分（便宜）
        assert calc_fundamental_score(None, None, 8.0)['valuation']['score'] == 3
        # 5~7% → 2 分（合理）
        assert calc_fundamental_score(None, None, 6.0)['valuation']['score'] == 2
        # 3~5% → 1 分
        assert calc_fundamental_score(None, None, 4.0)['valuation']['score'] == 1
        # <3% → 0 分（偏貴）
        assert calc_fundamental_score(None, None, 2.0)['valuation']['score'] == 0

    def test_eps_sum_above_threshold(self):
        # 近 4 季 EPS 加總 >= 1 → profit +1
        qtr = pd.DataFrame({'EPS': [0.3, 0.3, 0.3, 0.5]})
        result = calc_fundamental_score(qtr, None, None)
        assert result['profit']['score'] >= 1

    def test_high_net_profit_margin(self):
        # 稅後淨利率 >= 5% → profit +1
        qtr = pd.DataFrame({'稅後淨利率': [3, 4, 6, 8]})
        result = calc_fundamental_score(qtr, None, None)
        assert result['profit']['score'] >= 1

    def test_high_operating_margin(self):
        qtr = pd.DataFrame({'營業利益率': [5, 8, 12, 15]})
        result = calc_fundamental_score(qtr, None, None)
        assert result['profit']['score'] >= 1

    def test_revenue_growth_qoq(self):
        # 營收 v1 > v2 → growth +1
        qtr = pd.DataFrame({'營收': [100, 120]})
        result = calc_fundamental_score(qtr, None, None)
        assert result['growth']['score'] >= 1

    def test_gross_margin_above_20(self):
        qtr = pd.DataFrame({'毛利率': [25.0]})
        result = calc_fundamental_score(qtr, None, None)
        assert result['growth']['score'] >= 1

    def test_yearly_dividend_stability(self):
        # 近 4 年都有現金股利 → dividend +1
        yearly = pd.DataFrame({'現金股利': [1.0, 1.2, 1.5, 2.0]})
        result = calc_fundamental_score(None, yearly, 5.0)
        # 5.0 → score=2，加上 stability +1 = 3
        assert result['dividend']['score'] == 3

    def test_yearly_dividend_unstable(self):
        # 有 0 → 不穩定，不加分
        yearly = pd.DataFrame({'現金股利': [1.0, 0, 1.5, 2.0]})
        result = calc_fundamental_score(None, yearly, 5.0)
        assert result['dividend']['score'] == 2  # 僅 avg_div 部分

    def test_checks_recorded(self):
        # 任何維度命中至少一條 check
        qtr = pd.DataFrame({'EPS': [0.5, 0.5, 0.5, 0.5]})
        result = calc_fundamental_score(qtr, None, 5.0)
        assert len(result['profit']['checks']) >= 1
        assert len(result['dividend']['checks']) >= 1
        assert len(result['valuation']['checks']) >= 1


# ─────────────────────── calc_health_score ───────────────────────

def _df_with_ma(price=100, ma20=95, ma100=90):
    """快速建構包含 MA 欄位的 DataFrame。"""
    return pd.DataFrame({
        'close':  [price],
        'MA20':   [ma20],
        'MA100':  [ma100],
    })


class TestCalcHealthScore:
    def test_returns_score_and_details_tuple(self):
        score, details = calc_health_score(None, None, None, None, None, None, None)
        assert isinstance(score, int)
        assert isinstance(details, dict)

    def test_all_none_zero_score(self):
        score, details = calc_health_score(None, None, None, None, None, None, None)
        assert score == 0
        assert details == {}

    def test_score_capped_at_100(self):
        # 全部給滿分輸入
        df = _df_with_ma(100, 95, 90)
        bb = {'near_upper': True, 'price': 100, 'ma': 95, 'bw': 5, 'bw_mean': 10}
        score, _ = calc_health_score(df, 60, 0.1, 2.0, 50, 40, bb)
        assert score <= 100

    def test_trend_bull_30pts(self):
        # price > ma20 > ma100 → 多頭排列 +30
        df = _df_with_ma(110, 100, 90)
        score, details = calc_health_score(df, None, None, None, None, None, None)
        assert score == 30
        assert details['趨勢'] == ('多頭排列', 30, 30)

    def test_trend_bear_0pts(self):
        # price < ma20 < ma100 → 空頭排列 0
        df = _df_with_ma(80, 90, 100)
        score, details = calc_health_score(df, None, None, None, None, None, None)
        assert score == 0
        assert details['趨勢'][0] == '空頭排列'

    def test_trend_no_ma_15pts_default(self):
        # MA 欄位缺 → 給 15 分（中性）
        df = pd.DataFrame({'close': [100]})
        score, details = calc_health_score(df, None, None, None, None, None, None)
        assert score == 15
        assert details['趨勢'][0] == '無MA數據'

    def test_rsi_strong_zone(self):
        # RSI 50~70 → 20 分
        _, details = calc_health_score(None, 60, None, None, None, None, None)
        assert details['RSI'][1] == 20

    def test_rsi_oversold_rebound(self):
        # RSI < 30 → 14 分（超賣反彈機會 > 中性偏弱）
        _, details = calc_health_score(None, 25, None, None, None, None, None)
        assert details['RSI'][1] == 14

    def test_rsi_overbought(self):
        # RSI > 70 → 8 分
        _, details = calc_health_score(None, 75, None, None, None, None, None)
        assert details['RSI'][1] == 8

    def test_vr_abnormal_volume_max(self):
        # 1.5 <= vr <= 3.0 → 15 分（最高）
        _, details = calc_health_score(None, None, None, 2.0, None, None, None)
        assert details['量比'][1] == 15

    def test_vr_extremely_high_lower_score(self):
        # vr > 3.0 → 12 分（主力介入，分數低於異常放量）
        _, details = calc_health_score(None, None, None, 5.0, None, None, None)
        assert details['量比'][1] == 12

    def test_vr_extremely_low(self):
        # vr < 0.5 → 2 分
        _, details = calc_health_score(None, None, None, 0.3, None, None, None)
        assert details['量比'][1] == 2

    def test_ibs_low_reversal(self):
        # ibs <= 0.2 → 10 分（隔日易反彈）
        _, details = calc_health_score(None, None, 0.15, None, None, None, None)
        assert details['IBS'][1] == 10

    def test_ibs_high_selling_pressure(self):
        # ibs >= 0.8 → 2 分（隔日易賣壓）
        _, details = calc_health_score(None, None, 0.85, None, None, None, None)
        assert details['IBS'][1] == 2

    def test_kd_golden_cross(self):
        # k>d 且 k<80 → 黃金交叉 15 分
        _, details = calc_health_score(None, None, None, None, 60, 50, None)
        assert details['KD'][1] == 15

    def test_kd_death_cross(self):
        # k<d 且 k>20 → 死亡交叉 5 分
        _, details = calc_health_score(None, None, None, None, 40, 50, None)
        assert details['KD'][1] == 5

    def test_kd_high_golden_warning(self):
        # k>d 且 k>=80 → 高檔黃叉注意 8 分
        _, details = calc_health_score(None, None, None, None, 85, 80, None)
        assert details['KD'][1] == 8

    def test_bb_near_upper_strong(self):
        bb = {'near_upper': True, 'price': 100, 'ma': 95, 'bw': 10, 'bw_mean': 10}
        _, details = calc_health_score(None, None, None, None, None, None, bb)
        assert details['布林'][1] == 8

    def test_bb_squeeze_imminent_breakout(self):
        # 帶寬極度收縮 → 9 分（即將爆發）
        bb = {'near_upper': False, 'price': 90, 'ma': 100, 'bw': 5, 'bw_mean': 10}
        _, details = calc_health_score(None, None, None, None, None, None, bb)
        assert details['布林'][1] == 9


# ─────────────────────── health_grade ───────────────────────

class TestHealthGrade:
    def test_returns_4tuple(self):
        out = health_grade(80)
        assert isinstance(out, tuple)
        assert len(out) == 4

    def test_grade_a_80_above(self):
        label, color, css, emoji = health_grade(80)
        assert label == '優質優良'
        assert color == '#22c55e'
        assert css == 'health-A'
        assert emoji == '🟢'

    def test_grade_a_100(self):
        assert health_grade(100)[0] == '優質優良'

    def test_grade_b_50_to_79(self):
        label, color, css, emoji = health_grade(60)
        assert label == '震盪盤整'
        assert color == '#eab308'
        assert css == 'health-B'
        assert emoji == '🟡'

    def test_grade_b_at_50_boundary(self):
        assert health_grade(50)[0] == '震盪盤整'

    def test_grade_b_at_79(self):
        assert health_grade(79)[0] == '震盪盤整'

    def test_grade_c_below_50(self):
        label, color, css, emoji = health_grade(30)
        assert label == '弱勢危險'
        assert color == '#ef4444'
        assert css == 'health-C'
        assert emoji == '🔴'

    def test_grade_c_zero(self):
        assert health_grade(0)[0] == '弱勢危險'

    def test_boundary_80_is_a(self):
        # >=80 → A
        assert health_grade(80)[2] == 'health-A'

    def test_boundary_79_is_b(self):
        assert health_grade(79)[2] == 'health-B'

    @pytest.mark.parametrize('score,expected', [
        (100, 'health-A'),
        (85,  'health-A'),
        (80,  'health-A'),
        (79,  'health-B'),
        (50,  'health-B'),
        (49,  'health-C'),
        (0,   'health-C'),
    ])
    def test_threshold_table(self, score, expected):
        assert health_grade(score)[2] == expected
