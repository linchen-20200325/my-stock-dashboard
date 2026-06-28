"""test_section_inputs.py — C1-A/B/C v18.287→v18.289 守衛

CLAUDE.md §8.1 配套:確保 section_inputs 抽出後 behavioral equivalence,
caller(tab_macro 5 桶 summary + 戰情概覽 + 今日作戰室)解 bundle 後與直接讀 session_state 完全等價。

C1-B v18.288 升級:
- jingqi_info 優先讀 session_state 真實 dict,fallback 合成 `{'avg': warroom['jingqi_avg']}`
- 新增 last_inst 欄位

C1-C v18.289 升級:
- 新增 cl_ts(str)+ futures_net(int)欄位,匹配 evaluate_market_status_v4_final 介面
"""
from __future__ import annotations

import pytest

from src.services import SectionInputs, load_section_inputs


# ════════════════════════════════════════════════════════════════
# 1. load_section_inputs 對齊舊 tab_macro 5 桶 caller 寫法
# ════════════════════════════════════════════════════════════════

class TestLoadSectionInputsEquivalence:
    def test_empty_state(self):
        """空 session_state → SectionInputs 全 None。"""
        out = load_section_inputs({})
        assert isinstance(out, SectionInputs)
        assert out.macro_info is None
        assert out.mkt_info is None
        assert out.warroom_summary == {}  # 走 dict() fallback,空 dict 而非 None
        assert out.m1b_m2_info is None
        assert out.bias_info is None
        assert out.cl_data is None
        assert out.li_latest is None
        assert out.news_items is None
        assert out.last_inst is None
        # C1-C v18.289:cl_ts 空字串,futures_net=0 為 fail-safe 預設(對齊原 int(...) or 0)
        assert out.cl_ts == ''
        assert out.futures_net == 0
        # C1-F v18.292:
        assert out.last_inst_date is None
        assert out.last_margin is None
        # jingqi_info 在 warroom 為空 dict + 無 session_state['jingqi_info'] → None
        # 對齊 §1 Fail Loud:無資料時不偽造空 dict
        assert out.jingqi_info is None

    def test_none_state(self):
        out = load_section_inputs(None)
        assert isinstance(out, SectionInputs)
        assert out.macro_info is None

    def test_full_state_synthetic_jingqi(self):
        """完整 session_state(無 jingqi_info key)→ jingqi_info 從 warroom 合成。"""
        state = {
            'macro_info': {'us_core_cpi': {'yoy': 3.1}},
            'mkt_info': {'regime': 'bull', 'score': 3.5},
            'warroom_summary': {'health_score': 75, 'jingqi_avg': 28},
            'm1b_m2_info': {'gap': 1.2},
            'bias_info': {'ma20_bias': 0.05},
            'cl_data': {'inst': {'外資': {'net': 50}}},
            'li_latest': {'date': '2026-06-26'},
            '_macro_news_items': [{'title': 'A'}, {'title': 'B'}],
            '_last_inst': {'外資': {'net': 99}},
            'cl_ts': '2026-06-26 17:00:00',
            'futures_net': -5,
        }
        out = load_section_inputs(state)
        assert out.macro_info == {'us_core_cpi': {'yoy': 3.1}}
        assert out.mkt_info['regime'] == 'bull'
        assert out.warroom_summary['health_score'] == 75
        assert out.m1b_m2_info['gap'] == 1.2
        assert out.bias_info['ma20_bias'] == 0.05
        assert out.cl_data['inst']['外資']['net'] == 50
        assert out.li_latest['date'] == '2026-06-26'
        assert len(out.news_items) == 2
        assert out.last_inst['外資']['net'] == 99
        # 無 session_state['jingqi_info'] → 合成 {'avg': warroom['jingqi_avg']}
        assert out.jingqi_info == {'avg': 28}
        # C1-C
        assert out.cl_ts == '2026-06-26 17:00:00'
        assert out.futures_net == -5

    def test_jingqi_info_real_dict_preferred(self):
        """C1-B v18.288:session_state['jingqi_info'] 真實 dict 存在 → 優先用,
        不再合成 warroom 衍生值。對應 tab_macro:1221/3781/3927 寫入路徑。"""
        state = {
            'jingqi_info': {
                'avg': 65.5, 'pos': '50~70%', 'regime': 'bull',
                'color': '#3fb950', 'label': '🟢 多頭積極',
                'source': 'jingqi_proxy', 'pct20': 65.5,
            },
            'warroom_summary': {'jingqi_avg': 30},  # 即使 warroom 有衝突數值,
        }
        out = load_section_inputs(state)
        # 走 session_state 真實 dict
        assert out.jingqi_info['avg'] == 65.5
        assert out.jingqi_info['regime'] == 'bull'
        assert out.jingqi_info['source'] == 'jingqi_proxy'
        # warroom 衝突的 30 被忽略(這是 §2.1 SSOT 順序裁決:session_state['jingqi_info'] 為主)

    def test_jingqi_avg_none_in_warroom(self):
        """warroom_summary 有但無 jingqi_avg key + 無 session_state['jingqi_info']
        → jingqi_info={'avg': None}(對應 macro_helpers.calc_traffic_light:71 預設 50 之前的原值)。"""
        out = load_section_inputs({'warroom_summary': {'health_score': 50}})
        assert out.jingqi_info == {'avg': None}

    def test_frozen_dataclass(self):
        """SectionInputs 為 frozen dataclass,caller 不可意外改值。"""
        out = load_section_inputs({})
        with pytest.raises(Exception):  # FrozenInstanceError
            out.macro_info = {'forced': True}


# ════════════════════════════════════════════════════════════════
# 2. 與 compute_five_bucket_summary 介面對齊
# ════════════════════════════════════════════════════════════════

class TestOverviewSectionIntegration:
    """C1-B v18.288:戰情概覽 section 解 bundle 等價性。

    對齊 tab_macro.py:665-673 原寫法,確保 4 個 KPI 值來源一致:
    _ov_mkt / _ov_jq / _ov_cd / _ov_inst(雙源 fallback)/ _ov_bias / _ov_margin。
    """
    def test_overview_kpis_equivalence(self):
        state = {
            'mkt_info': {'regime': 'bull', 'exposure_pct': 75},
            'jingqi_info': {'avg': 62.3, 'pos': '50~70%'},
            'cl_data': {
                'inst': {'外資及陸資(不含外資自營商)': {'net': 45.7}},
                'margin': 1200,
            },
            'bias_info': {'bias_240': 12.5},
        }
        out = load_section_inputs(state)
        # 1. 大盤 regime + 持股建議
        assert out.mkt_info['regime'] == 'bull'
        assert out.mkt_info['exposure_pct'] == 75
        # 2. 外資籌碼:cl_data['inst'] 為主
        _inst = out.cl_data.get('inst') or (out.last_inst or {})
        fk = next((k for k in _inst if '外資' in k), None)
        assert fk is not None
        assert _inst[fk]['net'] == 45.7
        # 3. 旌旗 avg
        assert out.jingqi_info['avg'] == 62.3
        # 4. 年線乖離
        assert out.bias_info['bias_240'] == 12.5
        # 5. 融資餘額
        assert out.cl_data['margin'] == 1200

    def test_overview_inst_fallback_to_last_inst(self):
        """cl_data 無 inst → _last_inst 接力(對齊 tab_macro:669)。"""
        state = {
            'cl_data': {'margin': 800},  # 無 inst key
            '_last_inst': {'外資': {'net': -15.2}},
        }
        out = load_section_inputs(state)
        _inst = out.cl_data.get('inst') or (out.last_inst or {})
        fk = next((k for k in _inst if '外資' in k), None)
        assert fk == '外資'
        assert _inst[fk]['net'] == -15.2

    def test_overview_all_empty_gating(self):
        """空 session_state → any([mkt, jq, cd]) 為 False,UI gate 不渲染。"""
        out = load_section_inputs({})
        # 對齊 tab_macro:675 `if _show_market_data and any([_ov_mkt, _ov_jq, _ov_cd])`
        gate_inputs = [out.mkt_info or {}, out.jingqi_info or {}, out.cl_data or {}]
        assert not any(gate_inputs), "全空時 gate 應為 False"


class TestRegistrySectionIntegration:
    """C1-F v18.292:戰情區塊摘要 v3 Registry 解 bundle 等價性。

    對齊 tab_macro.py:2132-2250 原寫法。Registry 區塊一口氣讀 10 個 session_state keys,
    本是 C1 系列收斂幅度最大的單筆 PR(10 reads → 1 load_section_inputs)。
    """
    def test_registry_full_bundle(self):
        state = {
            'cl_data': {
                'intl': {'SPX': 'df'}, 'tw': {'TWII': 'df'}, 'tech': {'SOX': 'df'},
                'adl': 'df', 'inst': {'外資及陸資': {'net': 32}},
                'inst_date': '2026-06-26', 'margin': 1500,
            },
            '_last_inst': {'外資': {'net': 99}},
            '_last_inst_date': '2026-06-25',
            '_last_margin': 1300,
            'cl_ts': '2026-06-26 17:00:00',
            'jingqi_info': {'avg': 60},
            'bias_info': {'bias_240': 5.2, 'bias_20': 1.1},
            'm1b_m2_info': {'m1b_yoy': 7.5, 'm2_yoy': 5.0},
            'macro_info': {'vix': {'date': '2026-06-26', 'value': 18}},
            'li_latest': 'df_li',
        }
        out = load_section_inputs(state)
        # 10 個 registry section 用到的欄位全部對齊
        assert out.cl_data['intl']['SPX'] == 'df'
        assert out.last_inst['外資']['net'] == 99
        assert out.last_inst_date == '2026-06-25'
        assert out.last_margin == 1300
        assert out.cl_ts == '2026-06-26 17:00:00'
        assert out.jingqi_info == {'avg': 60}
        assert out.bias_info['bias_240'] == 5.2
        assert out.m1b_m2_info['m1b_yoy'] == 7.5
        assert out.macro_info['vix']['value'] == 18
        assert out.li_latest == 'df_li'

    def test_registry_inst_fallback_to_last_inst(self):
        """cl_data 無 inst → _last_inst 接力。對應 tab_macro:2173 原 fallback 鏈。"""
        state = {
            'cl_data': {},  # 無 inst
            '_last_inst': {'外資': {'net': -5}},
            '_last_inst_date': '2026-06-25',
        }
        out = load_section_inputs(state)
        _inst = out.cl_data.get('inst') or (out.last_inst or {})
        assert _inst['外資']['net'] == -5
        _date = (out.cl_data.get('inst_date') or out.last_inst_date)
        assert _date == '2026-06-25'

    def test_registry_margin_fallback_to_last_margin(self):
        """cl_data['margin'] 缺 → _last_margin 接力。對應 tab_macro:2186 原 fallback。"""
        state = {
            'cl_data': {},
            '_last_margin': 850,
        }
        out = load_section_inputs(state)
        _margin = out.cl_data.get('margin') or out.last_margin
        assert _margin == 850


class TestTrafficLightSectionIntegration:
    """C1-D v18.290:紅綠燈 section 解 bundle 等價性。

    對齊 tab_macro.py:495-499 原寫法。calc_traffic_light 介面接 4 dict-like 參數,
    `_tm_jq_init` 為關鍵 — 須是 dict(空 `{}` 也可,None 會 AttributeError)。
    """
    def test_traffic_light_inputs_all_dict_like(self):
        """全空 state → 4 input 全部走 `or {}` fallback,確保 calc_traffic_light 不炸。"""
        out = load_section_inputs({})
        _mkt = out.mkt_info or {}
        _jq  = out.jingqi_info or {}
        _cd  = out.cl_data or {}
        _li  = out.li_latest  # 可為 None,calc_traffic_light 自處
        assert isinstance(_mkt, dict)
        assert isinstance(_jq, dict)
        assert isinstance(_cd, dict)
        # _jq.get('avg', 50) 不可炸
        assert _jq.get('avg', 50) == 50

    def test_traffic_light_jingqi_from_session_state_real(self):
        """session_state['jingqi_info'] 真實 dict → calc 直接用 'avg' key。"""
        state = {
            'mkt_info': {'regime': 'bull'},
            'jingqi_info': {'avg': 65.0, 'regime': 'bull'},
            'cl_data': {'inst': {}},
            'li_latest': {'date': '2026-06-26'},
        }
        out = load_section_inputs(state)
        assert (out.jingqi_info or {}).get('avg', 50) == 65.0
        assert out.li_latest['date'] == '2026-06-26'

    def test_traffic_light_jingqi_fallback_to_warroom(self):
        """jingqi_info 缺 + warroom 存 jingqi_avg → 合成 dict 仍提供 'avg' key。"""
        state = {
            'warroom_summary': {'jingqi_avg': 48},
        }
        out = load_section_inputs(state)
        assert (out.jingqi_info or {}).get('avg', 50) == 48


class TestWarroomSectionIntegration:
    """C1-C v18.289:今日作戰室 section 解 bundle 等價性。

    對齊 tab_macro.py:723-738 原寫法。今日作戰室同時讀 6 keys + 走 v4 引擎。
    """
    def test_warroom_full_bundle(self):
        state = {
            'mkt_info': {'regime': 'bull', 'exposure_pct': 80},
            'cl_data': {
                'inst': {'外資': {'net': 32.1}},
                'margin': 1500,
                'adl': 1.05,
            },
            'bias_info': {'price': 17500, 'ma240': 16800, 'bias_240': 4.2},
            'm1b_m2_info': {'gap': 0.8},
            'cl_ts': '2026-06-26 17:00:00',
            'futures_net': 1200,
        }
        out = load_section_inputs(state)
        assert out.mkt_info['regime'] == 'bull'
        assert out.cl_data['margin'] == 1500
        assert out.cl_data['adl'] == 1.05
        assert out.bias_info['price'] == 17500
        assert out.bias_info['ma240'] == 16800
        assert out.m1b_m2_info['gap'] == 0.8
        assert out.cl_ts == '2026-06-26 17:00:00'
        assert out.futures_net == 1200

    def test_futures_net_coercion(self):
        """futures_net 走 int(... or 0)幾種怪輸入:None / float / 字串數字 / 空字串。"""
        assert load_section_inputs({'futures_net': None}).futures_net == 0
        assert load_section_inputs({'futures_net': 1500}).futures_net == 1500
        assert load_section_inputs({'futures_net': -250.7}).futures_net == -250
        assert load_section_inputs({'futures_net': '300'}).futures_net == 300
        assert load_section_inputs({'futures_net': ''}).futures_net == 0
        assert load_section_inputs({'futures_net': 0}).futures_net == 0

    def test_cl_ts_falsy_coerce_to_empty_str(self):
        """cl_ts 走 str fallback,None / 缺值 / 空字串都回 ''(對齊 _wr_ts 原寫法)。"""
        assert load_section_inputs({'cl_ts': None}).cl_ts == ''
        assert load_section_inputs({}).cl_ts == ''
        assert load_section_inputs({'cl_ts': ''}).cl_ts == ''
        assert load_section_inputs({'cl_ts': '2026-06-26'}).cl_ts == '2026-06-26'


class TestComputeFiveBucketIntegration:
    def test_pipeline_no_data(self):
        """空 session_state → compute_five_bucket_summary 不 raise,全 gray。"""
        from src.compute.macro import compute_five_bucket_summary
        out = load_section_inputs({})
        result = compute_five_bucket_summary(
            macro_info=out.macro_info,
            mkt_info=out.mkt_info,
            warroom_summary=out.warroom_summary,
            m1b_m2_info=out.m1b_m2_info,
            bias_info=out.bias_info,
            cl_data=out.cl_data,
            li_latest=out.li_latest,
            jingqi_info=out.jingqi_info,
            news_items=out.news_items,
        )
        # 5 桶皆存在(long/mid/short/chips/news)
        for k in ('long', 'mid', 'short', 'chips', 'news'):
            assert k in result
            assert 'level' in result[k]
