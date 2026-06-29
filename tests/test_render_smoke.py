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
import sys, os
sys.path.insert(0, os.getcwd())   # CI 可攜:repo root(非硬編 /home/user)
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


def test_radar_and_bucket_bar_gated_pre_load():
    """v18.285 靜態守衛(fast lane):全球風險雷達 + 五桶 bar 必須 gate 在
    _show_market_data 後 — 未載入資料(尚無快取/過期)時不顯示,對齊紅綠燈「尚無資料」。
    full render AppTest 在無 proxy/secrets 環境會 hang,故用 source pattern 檢查防回歸。"""
    import re
    # F-7.1 B-2/B-5:§一/§五/§六/§七 等 section_header 搬到 macro/section_short.py + section_long.py;source 改合集。
    src = (open("src/ui/tabs/tab_macro.py", encoding="utf-8").read()
           + open("src/ui/tabs/macro/section_short.py", encoding="utf-8").read()
           + open("src/ui/tabs/macro/section_long.py", encoding="utf-8").read())
    # 雷達 call 緊接在 if _show_market_data: 之後
    # v18.317:函式改名 _render_global_risk_bucket(10 燈雷達改桶,從頂部下移至短線急殺後)
    assert re.search(
        r"if _show_market_data:\s*\n\s+_render_global_risk_bucket", src
    ), "全球風險桶未 gate 在 _show_market_data(未載入會跑獨立 fetch + 顯示多餘面板)"
    # 五桶 bar 的 try 緊接在 if _show_market_data: 之後
    # (允許 try: 與 from 之間夾註解行 — C1-A v18.287 後內有 SSOT 引用註)
    assert re.search(
        r"if _show_market_data:\s*\n\s+try:\s*\n"
        r"(?:\s*#[^\n]*\n)*"  # 0+ 註解行
        r"\s+from src\.compute\.macro import compute_five_bucket_summary", src
    ), "五桶 bar 未 gate 在 _show_market_data(未載入會顯示多餘面板)"
    # F-7.1 B-2~B-5 + B-S8-A v18.388:§一/§三/§五/§六/§七/§八/§十一 全部 section
    # header 抽至各 section_*.py;此 test 改檢 tab_macro 內各 render_section_*()
    # call 順序(reading order 入口)。§三 籌碼 v18.388 後改 render_section_chips(...)。
    _tm_src = open("src/ui/tabs/tab_macro.py", encoding="utf-8").read()
    _pos_long   = _tm_src.find("render_section_long(")      # §七/§一/§六 入口
    _pos_mid    = _tm_src.find("render_section_mid(")       # §八 入口
    _pos_short  = _tm_src.find("render_section_short(")     # §五 入口
    _pos_three  = _tm_src.find("render_section_chips(")     # §三 籌碼(B-S8-A 抽)
    _pos_ai     = _tm_src.find("render_section_news_ai(")   # §十一 News AI(P2 v18.389 rename)
    for name, pos in [('render_section_long', _pos_long), ('render_section_mid', _pos_mid),
                      ('render_section_short', _pos_short), ('render_section_chips', _pos_three),
                      ('render_section_news_ai', _pos_ai)]:
        assert pos > 0, f"找不到 {name}"
    # reading order:long(§七一六) → mid(§八) → short(§五) → chips(§三) → news_ai(§十一)
    assert _pos_long < _pos_mid < _pos_short < _pos_three < _pos_ai, (
        f"C1-Z2 v18.297:section call 順序錯。"
        f" 實際: long={_pos_long}, mid={_pos_mid}, short={_pos_short}, "
        f"chips(三)={_pos_three}, news_ai={_pos_ai}"
    )


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
from src.ui.tabs import render_tab_edu
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
from src.ui.pages import render_data_coverage
render_data_coverage()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_data_coverage")

    def test_render_data_coverage_empty_state(self):
        """data_coverage:空 session_state → 全 ⬜ 未觸發(防 KeyError)"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from src.ui.pages import render_data_coverage
render_data_coverage()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_data_coverage 空 state")

    def test_render_api_diagnostic(self):
        """api_diagnostic:Key 遮罩 + secrets 解析(此環境無 secrets 走降級路徑)"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from src.ui.pages import render_api_diagnostic
render_api_diagnostic()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_api_diagnostic")

    def test_render_traffic_light_explainer_none(self):
        """macro_classroom explainer:None tl graceful(防 v18.281 搬遷後壞)"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from src.ui.tabs import render_traffic_light_explainer
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
from src.ui.tabs import render_principle_classroom
render_principle_classroom()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_principle_classroom shim")

    def test_render_five_bucket_bar_red(self):
        """v18.284: 總經五桶 bar — 全紅情境 render（compute + render 串接無例外）"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from src.compute.macro import compute_five_bucket_summary
from src.ui.tabs import render_five_bucket_bar
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
        from src.ui.tabs import add_danger_hlines
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
from src.compute.macro import compute_five_bucket_summary
from src.ui.tabs import render_five_bucket_bar
render_five_bucket_bar(compute_five_bucket_summary())
''')
        at = AppTest.from_string(drv, default_timeout=90)
        at.run()
        _assert_no_uncaught(at, "render_five_bucket_bar(empty)")
