"""test_section_inputs.py — C1-A/C1-B v18.287→v18.288 守衛

CLAUDE.md §8.1 配套:確保 section_inputs 抽出後 behavioral equivalence,
caller(tab_macro 5 桶 summary + 戰情概覽)解 bundle 後與直接讀 session_state 完全等價。

C1-B v18.288 升級:
- jingqi_info 優先讀 session_state 真實 dict,fallback 合成 `{'avg': warroom['jingqi_avg']}`
- 新增 last_inst 欄位
"""
from __future__ import annotations

import pytest

from section_inputs import SectionInputs, load_section_inputs


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


class TestComputeFiveBucketIntegration:
    def test_pipeline_no_data(self):
        """空 session_state → compute_five_bucket_summary 不 raise,全 gray。"""
        from macro_helpers import compute_five_bucket_summary
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
