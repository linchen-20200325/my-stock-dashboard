"""macro_helpers.py 純函式 unit test — Phase 7A-Ext / 7E。"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_helpers import calc_traffic_light, rp_entry, rp_scalar, rp_ts


class TestCalcTrafficLight:
    def test_all_empty_returns_none(self):
        assert calc_traffic_light({}, {}, {}, None) is None
        assert calc_traffic_light(None, None, None, None) is None

    def test_bull_regime_green(self):
        mkt = {'score': 4, 'regime': 'bull'}
        jq  = {'avg': 75}
        cl  = {'inst': {'外資自營': {'net': 1000}}, 'adl': 1}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl is not None
        assert tl['icon'] == '🟢'
        assert tl['color'] == '#3fb950'
        assert '多頭' in tl['label']
        assert tl['regime'] == 'bull'

    def test_caution_regime_red(self):
        # avg=80, score=3 → health = 32+24 = 56 ≥ 40，不觸發 defense，regime=caution
        mkt = {'score': 3, 'regime': 'caution'}
        jq  = {'avg': 80}
        cl  = {'inst': {'外資自營': {'net': -500}}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['icon'] == '🔴'
        assert '保守' in tl['label']
        assert tl['defense'] is False

    def test_bear_regime_red(self):
        # avg=80, score=3, fnet=0 → health=56 ≥ 40，regime=bear
        tl = calc_traffic_light(
            {'score': 3, 'regime': 'bear'}, {'avg': 80}, {}, None,
        )
        assert tl['icon'] == '🔴'
        assert '保守' in tl['label']
        assert tl['defense'] is False

    def test_neutral_regime_yellow(self):
        mkt = {'score': 3, 'regime': 'neutral'}
        jq  = {'avg': 60}
        cl  = {'inst': {'外資自營': {'net': 100}}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['icon'] == '🟡'
        assert '震盪' in tl['label']

    def test_defense_override_red(self):
        # score<2 + 期貨大空單 → 強制空頭防禦（即使 regime=bull）
        mkt = {'score': 1, 'regime': 'bull'}
        jq  = {'avg': 50}
        cl  = {'inst': {'外資自營': {'net': -1000}}}
        li  = pd.DataFrame({'外資大小': [-40000], '韭菜指數': [80]})
        tl = calc_traffic_light(mkt, jq, cl, li)
        assert tl['icon'] == '🔴'
        assert tl['defense'] is True
        assert '空頭防禦' in tl['label']

    def test_health_below_40_forces_defense(self):
        # jqavg=10 + score=0 + fnet=0 → health=10*0.4+0+0=4 < 40 → defense override
        mkt = {'score': 0, 'regime': 'bull'}
        jq  = {'avg': 10}
        cl  = {'inst': {}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['icon'] == '🔴'
        assert '空頭防禦' in tl['label']

    def test_foreign_net_extraction(self):
        cl = {'inst': {'外資 (自營+投信)': {'net': 12345}}}
        tl = calc_traffic_light({'score': 3, 'regime': 'neutral'}, {'avg': 60}, cl, None)
        assert tl['fk'] == '外資 (自營+投信)'
        assert tl['fnet'] == 12345

    def test_confidence_score(self):
        # 5 來源齊全 → conf=100
        mkt = {'score': 3, 'regime': 'neutral'}
        jq  = {'avg': 60}
        cl  = {'inst': {'外資': {'net': 100}}, 'adl': 1}
        li  = pd.DataFrame({'外資大小': [100], '韭菜指數': [50]})
        tl = calc_traffic_light(mkt, jq, cl, li)
        assert tl['conf'] == 100

    def test_confidence_partial(self):
        # 只有 mkt + jq → 2/5 = 40
        tl = calc_traffic_light({'score': 3, 'regime': 'neutral'}, {'avg': 60}, {}, None)
        assert tl['conf'] == pytest.approx(40)

    def test_li_latest_safe_parsing(self):
        # 欄位缺失：不報錯，fut_net=0、leek=50
        li = pd.DataFrame({'其他欄': [1]})
        tl = calc_traffic_light({'score': 3, 'regime': 'neutral'}, {'avg': 60}, {}, li)
        assert tl['fut_net'] == 0
        assert tl['leek'] == 50

    def test_health_formula(self):
        # health = avg*0.4 + min(score/5*100,100)*0.4 + (20 if fnet>0 else 0)
        # avg=50, score=5, fnet=100 → 20 + 40 + 20 = 80
        mkt = {'score': 5, 'regime': 'bull'}
        jq  = {'avg': 50}
        cl  = {'inst': {'外資': {'net': 100}}}
        tl = calc_traffic_light(mkt, jq, cl, None)
        assert tl['health'] == pytest.approx(80.0)


class TestRpTs:
    def test_none_returns_na(self):
        assert rp_ts(None) == 'N/A'

    def test_non_df_returns_na(self):
        assert rp_ts({'x': 1}) == 'N/A'
        assert rp_ts([1, 2, 3]) == 'N/A'

    def test_empty_df_returns_na(self):
        assert rp_ts(pd.DataFrame()) == 'N/A'

    def test_datetime_index(self):
        df = pd.DataFrame({'close': [10, 20]}, index=pd.to_datetime(['2024-01-15', '2024-03-22']))
        assert rp_ts(df) == '2024-03-22'

    def test_quarter_label_q4(self):
        # 季度標籤 '2024Q4' → '2024-12-31'
        df = pd.DataFrame({'季度標籤': ['2024Q1', '2024Q4'], 'val': [1, 2]})
        assert rp_ts(df) == '2024-12-31'

    def test_quarter_label_q1_q2_q3(self):
        # Q1=03-31, Q2=06-30, Q3=09-30
        for q, expect in [('1', '03-31'), ('2', '06-30'), ('3', '09-30')]:
            df = pd.DataFrame({'季度標籤': [f'2023Q{q}']})
            assert rp_ts(df) == f'2023-{expect}'

    def test_quarter_label_invalid_qnum_defaults_to_1231(self):
        df = pd.DataFrame({'季度標籤': ['2024Q9']})
        assert rp_ts(df) == '2024-12-31'

    def test_year_int_column(self):
        df = pd.DataFrame({'年度': [2022, 2023, 2024], 'val': [1, 2, 3]})
        assert rp_ts(df) == '2024-12-31'

    def test_underscore_date_format(self):
        # _date 強制 '%Y%m%d'
        df = pd.DataFrame({'_date': ['20240515', '20240601']})
        assert rp_ts(df) == '2024-06-01'

    def test_date_column_auto_parse(self):
        df = pd.DataFrame({'date': ['2024-05-15', '2024-06-01']})
        assert rp_ts(df) == '2024-06-01'

    def test_unparseable_returns_na(self):
        df = pd.DataFrame({'foo': ['bar', 'baz']})
        assert rp_ts(df) == 'N/A'


class TestRpEntry:
    def test_none_df_missing(self):
        e = rp_entry(None, '個股', 'daily')
        assert e['missing'] is True
        assert e['rows'] == 0
        assert e['last_updated'] == 'N/A'
        assert e['category'] == '個股'
        assert e['frequency'] == 'daily'

    def test_empty_df_missing(self):
        e = rp_entry(pd.DataFrame(), 'ETF', 'monthly')
        assert e['missing'] is True
        assert e['rows'] == 0

    def test_valid_df_uses_rp_ts(self):
        df = pd.DataFrame({'date': ['2024-05-15']})
        e = rp_entry(df, 'ETF', 'daily')
        assert 'missing' not in e
        assert e['rows'] == 1
        assert e['last_updated'] == '2024-05-15'
        assert e['category'] == 'ETF'
        assert e['frequency'] == 'daily'


class TestRpScalar:
    def test_none_val_missing(self):
        e = rp_scalar(None, '個股', 'daily', '2026-05-16')
        assert e['missing'] is True
        assert e['rows'] == 0
        assert e['last_updated'] == 'N/A'

    def test_valid_val_uses_proxy_date(self):
        e = rp_scalar(42, 'ETF', 'daily', '2026-05-16')
        assert 'missing' not in e
        assert e['rows'] == 1
        assert e['last_updated'] == '2026-05-16'
        assert e['category'] == 'ETF'

    def test_zero_treated_as_valid(self):
        # 0 不是 None → 視為有值（如 RSI=0、健康度=0 仍是有效讀數）
        e = rp_scalar(0, '個股', 'daily', '2026-05-16')
        assert e.get('missing') is None
        assert e['rows'] == 1
        assert e['last_updated'] == '2026-05-16'

    def test_empty_string_treated_as_valid(self):
        # '' 也不是 None
        e = rp_scalar('', 'ETF', 'daily', '2026-01-01')
        assert e.get('missing') is None
        assert e['rows'] == 1
