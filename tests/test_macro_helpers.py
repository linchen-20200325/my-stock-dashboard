"""macro_helpers.py 純函式 unit test — Phase 7A-Ext。"""
from __future__ import annotations

import pandas as pd
import pytest

from macro_helpers import calc_traffic_light


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
