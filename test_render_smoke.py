"""v18.283 — render smoke test(AppTest 實際 render,擋 production runtime bug)

背景:這輪有兩個 bug 是 runtime 才現形(v18.281 教室搬移 caller / v18.282 key 名臆測),
純 compile + 單元測試擋不住。本檔用 streamlit.testing.v1.AppTest 真實 render。

涵蓋(全改動 render 路徑):
- render_tab_edu(系統說明書 + 教室 + 資料地圖 ⓪)
- render_data_coverage(覆蓋率表 — v18.282 真實 key)
- render_api_diagnostic(API Key 診斷)
- render_traffic_light_explainer(總經 Tab 即時診斷)

策略:
- AppTest 跑完整 driver,catch uncaught exception
- 容忍 st.error / st.warning(降級展示,§1 Fail Loud 該行為)
- pytest -m "slow" 標記(對齊 Fund Stock 共用慣例)

§3.3 SSOT — 測資 shape 對齊 production(macro_info 6 真實 key / cl_data 真實 key)
§1 Fail Loud — 任何 uncaught exception 直接 fail
"""
from __future__ import annotations

import pytest

# 真實 macro_info shape(對齊 tab_macro.py:1862 _job_macro 回傳)
_REAL_MACRO_INFO = {
    "_loaded_at": "2026-06-25 14:00:00",
    "vix": {"current": 22.0, "ma20": 20.0, "date": "2026-06-25"},
    "ism_pmi": {"current": 48.5, "yoy": -2.0, "date": "2026-06-25"},
    "us_core_cpi": {"current": 3.2, "yoy": 3.2, "date": "2026-06-25"},
    "fed_funds": {"current": 4.5, "date": "2026-06-25"},
    "ndc_signal": {"current": 21.0, "date": "2026-06-25"},
    "tw_export": {"current": 12.0, "yoy": 5.0, "date": "2026-06-25"},
}

_REAL_CL_DATA = {
    "inst": [{"date": "2026-06-25", "foreign": 100, "trust": -50, "dealer": 30}],
    "margin": [{"date": "2026-06-25", "value": 2400}],
    "adl": [{"date": "2026-06-25", "advance": 600, "decline": 200}],
}


def _build_driver(body: str) -> str:
    """共用 driver:sys.path + 灌 session_state"""
    return f'''
import sys
sys.path.insert(0, "/home/user/my-stock-dashboard")
import os
os.environ["FRED_API_KEY"] = "x" * 32
import streamlit as st
{body}
'''


def _assert_no_uncaught(at, label: str):
    """確認 AppTest run 後無 uncaught exception。
    容忍 st.error / st.warning(降級展示,§1 Fail Loud 該行為)。
    """
    if at.exception:
        msgs = []
        for e in at.exception:
            msgs.append(f"{e.type}: {str(e.value)[:300]}")
        pytest.fail(f"{label} 有 uncaught exception:\n" + "\n".join(msgs))


@pytest.mark.slow
class TestRenderSmoke:
    """v18.283 — 改動 render 路徑 smoke test"""

    @classmethod
    def setup_class(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:
            pytest.skip("streamlit.testing.v1.AppTest 不可用(streamlit < 1.30)")

    def test_render_tab_edu_system_manual(self):
        """tab_edu:v18.281 系統說明書 + 教室合併 + 資料地圖 ⓪"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from tab_edu import render_tab_edu
render_tab_edu()
''')
        at = AppTest.from_string(drv, default_timeout=90)
        at.run()
        _assert_no_uncaught(at, "render_tab_edu")
        # 應該有相當量 markdown(教室 10 章 + 4 大師策略 + 資料地圖)
        assert len(at.markdown) > 30, "系統說明書 render 元素太少"

    def test_render_data_coverage(self):
        """data_coverage:v18.282 真實 key 修正 — 灌入真實 macro_info"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver(f'''
st.session_state["macro_info"] = {_REAL_MACRO_INFO!r}
st.session_state["cl_data"] = {_REAL_CL_DATA!r}
st.session_state["t2_data"] = {{"d": "stub", "df": [1, 2]}}
from data_coverage import render_data_coverage
render_data_coverage()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_data_coverage")

    def test_render_data_coverage_empty_state(self):
        """data_coverage:空 session_state → 全 ⬜ 未觸發(防 KeyError)"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from data_coverage import render_data_coverage
render_data_coverage()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_data_coverage 空 state")

    def test_render_api_diagnostic(self):
        """api_diagnostic:Key 遮罩 + secrets 解析(此環境無 secrets 走降級路徑)"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from api_diagnostic import render_api_diagnostic
render_api_diagnostic()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_api_diagnostic")

    def test_render_traffic_light_explainer_none(self):
        """macro_classroom explainer:None tl graceful(防 v18.281 搬遷後壞)"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from macro_classroom import render_traffic_light_explainer
render_traffic_light_explainer(None)
render_traffic_light_explainer({})
render_traffic_light_explainer({
    "color": "#3fb950", "label": "多頭", "health": 70, "score": 5,
    "regime": "bull", "defense": False, "fut_net": 30000, "conf": 90,
})
''')
        at = AppTest.from_string(drv, default_timeout=30)
        at.run()
        _assert_no_uncaught(at, "render_traffic_light_explainer")

    def test_render_principle_classroom_via_shim(self):
        """v18.281: macro_classroom 留向後相容 shim,呼叫應正常 re-export 到 tab_edu"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
# 走 shim 路徑(import from macro_classroom 應 re-export 到 tab_edu 的 fn)
from macro_classroom import render_principle_classroom
render_principle_classroom()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_principle_classroom shim")

    def test_render_five_bucket_bar_red(self):
        """v18.284: 總經五桶 bar — 全紅情境 render（compute + render 串接無例外）"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from macro_helpers import compute_five_bucket_summary
from tab_macro import render_five_bucket_bar
_summary = compute_five_bucket_summary(
    macro_info={"vix":{"current":35},"ism_pmi":{"value":44},"us_core_cpi":{"yoy":4.5},
                "tw_export":{"yoy":-8},"ndc_signal":{"score":14}},
    warroom_summary={"health_score":30,"jingqi_avg":35},
    m1b_m2_info={"gap":-0.5}, bias_info={"bias_240":25},
    news_items=[{"is_systemic":True},{"is_systemic":True}],
)
render_five_bucket_bar(_summary)
''')
        at = AppTest.from_string(drv, default_timeout=90)
        at.run()
        _assert_no_uncaught(at, "render_five_bucket_bar(red)")
        assert len(at.markdown) > 5, "五桶 bar render 元素太少"

    def test_add_danger_hlines(self):
        """v18.284: 圖表危險標準線 helper — VIX 用 SSOT 22(非舊 25)、yref=y2、band 不炸"""
        import plotly.graph_objects as go
        from tab_macro import add_danger_hlines
        f = go.Figure()
        add_danger_hlines(f, 'vix')             # high_bad → 22 / 30
        add_danger_hlines(f, 'adl', yref='y2')  # low_bad on y2 → 50 / 35
        add_danger_hlines(f, 'ndc_signal')      # band → 4 線
        add_danger_hlines(f, 'nope')            # 未知 key → no-op
        ys = sorted(s.y0 for s in f.layout.shapes)
        assert 22.0 in ys and 30.0 in ys, "VIX 標準線應為 SSOT 22/30"
        assert 25.0 not in ys, "VIX 不該再用舊的 inline 25"
        assert len(f.layout.shapes) == 8, "VIX2 + ADL2 + NDC4 = 8 條線"

    def test_render_five_bucket_bar_empty_gray(self):
        """v18.284: 空 session_state → 五桶全 ⬜ 未載入（不偽綠 / 不 KeyError）"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from macro_helpers import compute_five_bucket_summary
from tab_macro import render_five_bucket_bar
render_five_bucket_bar(compute_five_bucket_summary())
''')
        at = AppTest.from_string(drv, default_timeout=90)
        at.run()
        _assert_no_uncaught(at, "render_five_bucket_bar(empty)")
