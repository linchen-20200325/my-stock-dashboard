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


def test_render_section_news_ai_args_defined_in_scope():
    """v18.393 P0-FIX 靜態守衛:render_section_news_ai(_macro_info, _tl_eff_reg)
    的兩個引數必須在 render_tab_macro() 作用域內已定義。

    歷史教訓:D-12 (a13bb25) 抽 trio executor 後,_macro_info 隨外層代碼搬走,
    但 §十一 call 仍 reference → 走入 §十一 render path 100% NameError;
    pytest 2220 case 全是 source-string 檢查,5 個 commit 沒抓到。

    本 test 用 AST 解析 render_tab_macro,確認 call args 在同函式 scope
    有對應 ast.Assign / ast.AnnAssign / ast.arguments(參數)。
    """
    import ast
    src = open("src/ui/tabs/tab_macro.py", encoding="utf-8").read()
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "render_tab_macro")

    # 收集 render_section_news_ai(...) 的 Name 引數
    news_ai_args: list[tuple[str, int]] = []
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "render_section_news_ai"):
            for a in node.args:
                if isinstance(a, ast.Name):
                    news_ai_args.append((a.id, node.lineno))
    assert news_ai_args, "render_section_news_ai 未在 render_tab_macro 內被呼叫"

    # 收集所有 ast.Assign 的 target Name(同 scope,含 nested for/if)
    defined_names: set[str] = set(a.arg for a in fn.args.args)
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defined_names.add(t.id)
                elif isinstance(t, ast.Tuple):
                    for elt in t.elts:
                        if isinstance(elt, ast.Name):
                            defined_names.add(elt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined_names.add(node.target.id)
        elif isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.target, ast.Name):
            defined_names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                defined_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                defined_names.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.withitem) and node.optional_vars:
            if isinstance(node.optional_vars, ast.Name):
                defined_names.add(node.optional_vars.id)

    for arg_name, lineno in news_ai_args:
        assert arg_name in defined_names, (
            f"render_section_news_ai 引數 `{arg_name}` 在 tab_macro.py:{lineno} 引用,"
            f"但未在 render_tab_macro 作用域內定義 — 走入 §十一 render 會 NameError 全頁炸。"
            f"見 v18.393 P0-FIX(L749 _macro_info 從 session_state 重讀)。"
        )


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
    # 五桶 bar gate 在 _show_market_data 之後(P3-D5 v18.390 抽出後改 render_five_bucket_summary())
    # 同時掃 tab_macro(call site)+ section_summary_bar(實作)合集。
    _smry_src = open("src/ui/tabs/macro/section_summary_bar.py", encoding="utf-8").read()
    assert re.search(
        r"if _show_market_data:\s*\n"
        r"(?:\s*#[^\n]*\n)*"  # 0+ 註解行
        r"\s+render_five_bucket_summary\(\)", src
    ), "五桶 bar 未 gate 在 _show_market_data(未載入會顯示多餘面板)"
    assert "from src.compute.macro import compute_five_bucket_summary" in _smry_src, \
        "section_summary_bar 內部應 import compute_five_bucket_summary"
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

    def _has_secrets_toml(self):
        """需要 .streamlit/secrets.toml 才能跑(§十一 News AI 走 app.py lazy import 讀 st.secrets)。"""
        import os.path as _p
        return any(_p.exists(_p.expanduser(f'{d}/.streamlit/secrets.toml'))
                   for d in ['.', '~', '/root', '/home/user/my-stock-dashboard'])

    def test_render_section_news_ai_no_nameerror(self):
        """v18.395 P5-AppTest C1:PR #398 P0-FIX 实機驗 — 走 §十一 News AI render path 不炸 NameError。

        歷史教訓:D-12 抽 trio 後 `_macro_info` 變數懸空,任何走入 §十一 render
        path 都 100% NameError 全頁炸,但 source-string 測試 5 個 commit 沒抓到。

        本 test 用 AppTest 真實 invoke render_section_news_ai 並灌真實 macro_info shape,
        驗證函式可以 import + invoke 不炸。

        Note:§十一 內部 lazy import `from app import gemini_call`(v18.398 P5-B3-β R8
        起 `_fetch_macro_news` 已抽至 `src.data.news`),而 app.py module 載入時直接
        `st.secrets.get('FINMIND_TOKEN', ...)`(會 raise 若無 secrets.toml)。CI 無
        secrets → 自動 skip(production deploy 必有 secrets,實機驗仍涵蓋)。靜態 AST
        守衛 test_render_section_news_ai_args_defined_in_scope 無此依賴,專責 NameError
        類回歸防護。
        """
        if not self._has_secrets_toml():
            pytest.skip("無 .streamlit/secrets.toml(§十一 News AI lazy import app.py 必須讀 st.secrets)")
        from streamlit.testing.v1 import AppTest
        drv = _build_driver(f'''
st.session_state["macro_info"] = {_REAL_MACRO_INFO!r}
st.session_state["m1b_m2_info"] = {{"m1b_yoy": 5.5, "m2_yoy": 4.0, "gap": 1.5}}
st.session_state["bias_info"] = {{"bias_240": 2.5, "bias_20": -1.0}}
from src.ui.tabs.macro.section_news_ai import render_section_news_ai
# 模擬 PR #398 P0-FIX 後的 caller pattern
_macro_info = st.session_state.get("macro_info") or {{}}
render_section_news_ai(_macro_info, "bull")
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_section_news_ai(real macro_info)")
        # 至少要有標題與 expander render
        assert len(at.markdown) > 0, "render_section_news_ai 無 markdown 元素"

    def test_render_section_news_ai_empty_state(self):
        """v18.395 P5-AppTest C1 邊界:空 macro_info / 空 session_state → 不炸"""
        if not self._has_secrets_toml():
            pytest.skip("無 .streamlit/secrets.toml(§十一 lazy import app.py 必須讀 st.secrets)")
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from src.ui.tabs.macro.section_news_ai import render_section_news_ai
_macro_info = st.session_state.get("macro_info") or {}
render_section_news_ai(_macro_info, "neutral")
''')
        at = AppTest.from_string(drv, default_timeout=30)
        at.run()
        _assert_no_uncaught(at, "render_section_news_ai(empty)")

    def test_render_data_registry_panel(self):
        """v18.395 P5-AppTest C2:PR #399 panel 实機驗 — 50+ entries 渲染不炸 + 按 SSOT 11 emoji 分組"""
        from streamlit.testing.v1 import AppTest
        # 灌入 realistic registry shape:11 category 全覆蓋(對齊 shared.data_categories)
        _mock_reg = {
            '道瓊工業 DJI':       {'last_updated': '2026-06-29', 'rows': 90,
                                   'category': '🌐 國際金融', 'frequency': 'daily'},
            '台股加權指數':        {'last_updated': '2026-06-29', 'rows': 90,
                                   'category': '🇹🇼 台股大盤', 'frequency': 'daily'},
            'M1B 資金活水年增率':  {'last_updated': '2026-06-15', 'rows': 1,
                                   'category': '🇹🇼 台灣總經', 'frequency': 'monthly'},
            '美國核心CPI年增率':   {'last_updated': '2026-06-15', 'rows': 1,
                                   'category': '🌍 美國總經', 'frequency': 'monthly'},
            '三大法人 外資買賣超': {'last_updated': '2026-06-28', 'rows': 1,
                                   'category': '💰 籌碼', 'frequency': 'daily'},
            '[個股] 2330 台積電 | 價格走勢': {'last_updated': 'N/A', 'rows': 0,
                                              'category': '🏢 個股財報',
                                              'frequency': 'daily', 'missing': True},
            '[ETF] 0050 | 價格走勢': {'last_updated': 'N/A', 'rows': 0,
                                      'category': '🏦 ETF / 基金',
                                      'frequency': 'daily', 'missing': True},
        }
        drv = _build_driver(f'''
st.session_state["data_registry"] = {_mock_reg!r}
from src.ui.pages import render_data_registry_panel
render_data_registry_panel()
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_data_registry_panel")
        # 應該 render 出 panel 標題 + 7 個 expander group(對應 7 個 category)
        assert len(at.markdown) > 5, "data_registry_panel render 元素太少"

    def test_render_data_registry_panel_empty(self):
        """v18.395 P5-AppTest C2 邊界:空 data_registry → 顯示「尚未觸發」info,不炸"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from src.ui.pages import render_data_registry_panel
render_data_registry_panel()  # 無 session_state['data_registry']
''')
        at = AppTest.from_string(drv, default_timeout=30)
        at.run()
        _assert_no_uncaught(at, "render_data_registry_panel(empty)")

    def test_render_section_short_no_unbound_local_error(self):
        """v18.450:production 事故 — 總經分頁全頁炸
        `UnboundLocalError: cannot access local variable 'df_adl' where it is not
        associated with a value`(section_short.py:72)。根因:`df_adl` 只在函式
        132 行(_load_heavy 補救分支)被賦值,Python 因此把它視為整個函式的區域變數,
        但 72 行早於任何賦值就讀取 → 無論 _load_heavy 為何都會炸(空 session_state
        時最先觸發,幾乎每個冷啟動 session 都會中招)。

        本測試複現原始崩潰條件:空 session_state(無 cl_data.adl)+ 呼叫
        render_section_short,確認真實 render 不再拋例外。"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
from src.ui.tabs.macro.section_short import render_section_short
render_section_short(False, {}, {})
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_section_short(空 session_state)")

    def test_render_section_short_populated_adl_no_undefined_names(self):
        """v18.452:production 事故 — 總經分頁全頁炸
        `NameError: name 'TRAFFIC_GREEN' is not defined`(section_short.py:174)。

        根因:F-7.1 B-2 把「短線急殺桶」從 tab_macro.py 抽成獨立模組時,遺漏原本
        外層 scope 才有的 8 個 import(TRAFFIC_GREEN/RED/YELLOW、os、go、
        BREADTH_BULL_PCT/NEUTRAL_PCT、add_danger_hlines)。空 session_state 測試
        (上一個 test)完全繞過這些 undefined name(df_adl 為 None 時整段跳過),
        production 只有在 ADL 資料真的載入後才會炸 —— 這正是使用者實測命中的分支。

        本測試灌入真實形狀的 ADL DataFrame(對齊 fetch_adl 回傳欄位:
        date/up/down/ad/ad_ratio/adl/adl_ma20)+ 大盤 K 線,強制走入 KPI 卡片
        （TRAFFIC_GREEN/RED）、廣度評分（BREADTH_BULL_PCT/NEUTRAL_PCT）、
        騰落線圖（plotly go.Figure + add_danger_hlines）等原本會炸的路徑。"""
        from streamlit.testing.v1 import AppTest
        drv = _build_driver('''
import pandas as pd
_dates = pd.date_range('2026-06-15', periods=10, freq='D')
_adl_df = pd.DataFrame({
    'date': _dates,
    'up': [500, 520, 480, 600, 610, 590, 620, 630, 640, 650],
    'down': [300, 290, 320, 250, 240, 260, 230, 220, 210, 200],
    'ad': [200, 230, 160, 350, 370, 330, 390, 410, 430, 450],
    'ad_ratio': [62.5, 64.2, 60.0, 70.6, 71.8, 69.4, 72.9, 74.1, 75.3, 76.5],
    'adl': [1000, 1230, 1390, 1740, 2110, 2440, 2830, 3240, 3670, 4120],
    'adl_ma20': [900, 950, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700],
})
_twii_df = pd.DataFrame({
    'close': [22000.0, 22050.0, 22100.0, 22200.0, 22300.0,
              22250.0, 22400.0, 22500.0, 22600.0, 22700.0],
}, index=_dates)
st.session_state["cl_data"] = {"adl": _adl_df}
from src.ui.tabs.macro.section_short import render_section_short
render_section_short(True, {"台股加權指數": _twii_df}, {"台股加權指數": {"pct": 0.8}})
''')
        at = AppTest.from_string(drv, default_timeout=60)
        at.run()
        _assert_no_uncaught(at, "render_section_short(populated ADL)")
        assert len(at.markdown) > 0, "render_section_short(populated) 無 markdown 元素"

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
