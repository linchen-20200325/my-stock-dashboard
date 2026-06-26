"""test_section_inputs.py — C1-A v18.287 守衛

CLAUDE.md §8.1 配套:確保 section_inputs 抽出後 behavioral equivalence,
caller(tab_macro 5 桶 summary)解 bundle 後與直接讀 session_state 完全等價。
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
        # jingqi_info 在 warroom 為空 dict → None({'avg': None} 也算 truthy)
        # 對齊舊寫法:`{'avg': _wr5.get('jingqi_avg')}` 即使 _wr5={} 也回 {'avg': None}
        # 但我們改為 warroom 為 falsy 時整個 jingqi_info=None,以利 Fail Loud。
        assert out.jingqi_info is None

    def test_none_state(self):
        out = load_section_inputs(None)
        assert isinstance(out, SectionInputs)
        assert out.macro_info is None

    def test_full_state(self):
        """完整 session_state → SectionInputs 對應欄位齊全。"""
        state = {
            'macro_info': {'us_core_cpi': {'yoy': 3.1}},
            'mkt_info': {'regime': 'bull', 'score': 3.5},
            'warroom_summary': {'health_score': 75, 'jingqi_avg': 28},
            'm1b_m2_info': {'gap': 1.2},
            'bias_info': {'ma20_bias': 0.05},
            'cl_data': {'inst': {'外資': {'net': 50}}},
            'li_latest': {'date': '2026-06-26'},
            '_macro_news_items': [{'title': 'A'}, {'title': 'B'}],
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
        # jingqi_info 從 warroom_summary['jingqi_avg'] 衍生
        assert out.jingqi_info == {'avg': 28}

    def test_jingqi_avg_none_in_warroom(self):
        """warroom_summary 有但無 jingqi_avg key → jingqi_info={'avg': None}。"""
        out = load_section_inputs({'warroom_summary': {'health_score': 50}})
        # warroom 有資料 → jingqi_info 走 dict 包裝,即使 avg key 缺也回 {'avg': None}
        assert out.jingqi_info == {'avg': None}

    def test_frozen_dataclass(self):
        """SectionInputs 為 frozen dataclass,caller 不可意外改值。"""
        out = load_section_inputs({})
        with pytest.raises(Exception):  # FrozenInstanceError
            out.macro_info = {'forced': True}


# ════════════════════════════════════════════════════════════════
# 2. 與 compute_five_bucket_summary 介面對齊
# ════════════════════════════════════════════════════════════════

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
