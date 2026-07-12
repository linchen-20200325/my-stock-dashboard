"""v18.280 tests — data_coverage 純函式覆蓋率計算(學 Fund Section ⓪)."""
from __future__ import annotations

import sys
import types

import pytest


def _stub_st():
    # v18.281 — 不覆蓋既有 test stub(避免污染其他 test 檔的完整 stub)
    # v18.359 Phase 2 F-1.3 — 本檔由 root 搬入 tests/ 後字母順序變早於 test_etf_* /
    #   test_hot_money / test_exit_signals,而那些模組頂部用 @st.cache_data 裝飾。
    #   原本 root → tests 分階段 collect,tests 階段先 import 完真 streamlit 不受
    #   本 stub 影響;搬入後字母順序失序,本 stub 必須含 cache_data / cache_resource
    #   的 no-op decorator,否則後續 import etf_calc / hot_money 等模組會炸。
    _existing = sys.modules.get("streamlit")
    if _existing is not None and (getattr(_existing, "_stub", False)
                                  or getattr(_existing, "_is_test_stub", False)):
        return
    m = types.ModuleType("streamlit")
    m._stub = True

    class _SS(dict):
        def get(self, k, d=None):
            return super().get(k, d)
    m.session_state = _SS()

    def _noop(*a, **k):
        return None
    # v18.362 F-8 R2:擴大 noop list — 涵蓋 tab_edu / macro_classroom 用到的全部 st.*
    # (render_principle_classroom + render_traffic_light_explainer 等)
    # 防 F-8 / F-6.5 後 collection 順序變,任何 tab 內 st.* 撞 stub AttributeError。
    for n in ("markdown", "caption", "divider", "expander", "error", "plotly_chart",
              "warning", "info", "title", "header", "subheader", "write", "code",
              "metric", "dataframe", "table", "button", "text_input", "selectbox",
              "multiselect", "slider", "checkbox", "radio", "columns", "container",
              "spinner", "progress", "tabs", "sidebar", "image", "json", "altair_chart",
              "bar_chart", "line_chart", "area_chart", "pyplot", "graphviz_chart",
              "form", "form_submit_button", "empty", "rerun", "experimental_rerun"):
        setattr(m, n, _noop)

    # 支援 @st.cache_data 與 @st.cache_data(ttl=...) 兩種呼叫
    def _cache_data(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f
    m.cache_data = _cache_data
    m.cache_resource = _cache_data

    sys.modules["streamlit"] = m


def _reload_pages_modules() -> None:
    """就地 reload 已載入的 src.ui.pages.* — rebind 它們的 module-level `st`。"""
    import importlib
    for _name in sorted(k for k in list(sys.modules)
                        if k == "src.ui.pages" or k.startswith("src.ui.pages.")):
        _mod = sys.modules.get(_name)
        if _mod is None:
            continue
        try:
            importlib.reload(_mod)
        except Exception:
            pass  # smoke-allow-pass — 個別 reload 失敗不炸 fixture


@pytest.fixture(autouse=True, scope="module")
def _scoped_streamlit_stub():
    """v19.107 stub 生命週期收斂(CI slow lane 全滅根因之一)。

    原:模組級 `_stub_st()` 於 collection 期永久替換 sys.modules['streamlit'],
    無 cleanup → 字母序在後的整個 run phase 吃到假 st(AppTest 全 skip /
    test_screener_candidates 硬炸)。
    改:本檔測試期間才裝 stub(隔離 st 副作用),測完還原進場前的真身,
    並 reload 期間被綁到 stub 的 src.ui.pages.* 模組(importlib.reload 為
    in-place,既有引用同步 rebind)。
    """
    _saved = sys.modules.get("streamlit")
    _stub_st()
    _reload_pages_modules()
    yield
    if _saved is not None:
        sys.modules["streamlit"] = _saved
    else:
        sys.modules.pop("streamlit", None)
    _reload_pages_modules()


class TestComputeTabCoverage:
    def test_empty_state_all_idle(self):
        from src.ui.pages import compute_tab_coverage
        rows = compute_tab_coverage(state={})
        assert len(rows) == 4
        # 全空 → 全部 ⬜ 未觸發
        assert all(r["emoji"] == "⬜" for r in rows)

    def test_returns_4_tabs(self):
        from src.ui.pages import compute_tab_coverage
        rows = compute_tab_coverage(state={})
        tabs = [r["tab"] for r in rows]
        assert any("總經" in t for t in tabs)
        assert any("個股" in t for t in tabs)
        assert any("籌碼" in t for t in tabs)
        assert any("ETF" in t for t in tabs)

    def test_each_row_has_required_fields(self):
        from src.ui.pages import compute_tab_coverage
        for r in compute_tab_coverage(state={}):
            for f in ("tab", "emoji", "color", "ratio_txt", "detail", "action"):
                assert f in r, f"缺欄位 {f}"

    def test_macro_full_coverage_green(self):
        """v18.282: 用真實 macro_info key；v18.349 由 SSOT MACRO_INFO_KEYS 派生"""
        from src.ui.pages import compute_tab_coverage
        from shared.macro_buckets import MACRO_INFO_KEYS
        _full_macro = {k: {"current": 1.0} for k in MACRO_INFO_KEYS}
        rows = compute_tab_coverage(state={
            "macro_info": _full_macro,
            "m1b_m2_info": {"v": 1},
            "li_latest": {"v": 1},
        })
        macro_row = next(r for r in rows if "總經" in r["tab"])
        assert macro_row["emoji"] == "🟢"
        # 分母 = 核心 6 key + M1B-M2 + 領先 = SSOT 長度 + 2(漂移守門:
        #   改 MACRO_INFO_KEYS → 覆蓋率分母自動跟著,不再各自寫死)
        _expect = f"{len(MACRO_INFO_KEYS) + 2}/{len(MACRO_INFO_KEYS) + 2}"
        assert macro_row["ratio_txt"] == _expect

    def test_macro_coverage_uses_ssot_keys(self):
        """v18.349: data_coverage 認列的 macro key 數 = SSOT 清單長度。
        缺 1 個 SSOT key → 非滿分(覆蓋率隨 SSOT 連動,證明非寫死)。"""
        from src.ui.pages import compute_tab_coverage
        from shared.macro_buckets import MACRO_INFO_KEYS
        # 只放滿全部 SSOT key 但缺 M1B/領先 → have=6/total=8 → 75% → 🟡
        _macro = {k: {"current": 1.0} for k in MACRO_INFO_KEYS}
        rows = compute_tab_coverage(state={"macro_info": _macro})
        macro_row = next(r for r in rows if "總經" in r["tab"])
        # have = len(SSOT)，total = len(SSOT)+2
        assert macro_row["ratio_txt"] == f"{len(MACRO_INFO_KEYS)}/{len(MACRO_INFO_KEYS) + 2}"

    def test_macro_meta_only_is_idle(self):
        """只有 _loaded_at meta key(全 fetch 失敗)→ 未觸發,非綠"""
        from src.ui.pages import compute_tab_coverage
        rows = compute_tab_coverage(state={
            "macro_info": {"_loaded_at": "2026-06-25", "_all_failed": True},
        })
        macro_row = next(r for r in rows if "總經" in r["tab"])
        assert macro_row["emoji"] == "⬜"

    def test_macro_partial_red(self):
        from src.ui.pages import compute_tab_coverage
        # 只有 2/6 macro + 無 M1B/領先 → 紅
        rows = compute_tab_coverage(state={
            "macro_info": {"vix": {"current": 1}, "ism_pmi": {"current": 1}},
        })
        macro_row = next(r for r in rows if "總經" in r["tab"])
        assert macro_row["emoji"] == "🔴"

    def test_stock_loaded_green(self):
        """t2_data 為單一個股 metrics dict(present = 已查)"""
        from src.ui.pages import compute_tab_coverage
        rows = compute_tab_coverage(state={"t2_data": {"d": "台積電", "df": [1, 2]}})
        stock_row = next(r for r in rows if "個股" in r["tab"])
        assert stock_row["emoji"] == "🟢"
        assert stock_row["ratio_txt"] == "已查"

    def test_chips_partial(self):
        """cl_data 真實 key:inst / margin / adl"""
        from src.ui.pages import compute_tab_coverage
        rows = compute_tab_coverage(state={
            "cl_data": {"inst": [1], "margin": [1]}  # 2/3(無 adl)
        })
        chip_row = next(r for r in rows if "籌碼" in r["tab"])
        assert chip_row["emoji"] == "🟡"

    def test_chips_full_green(self):
        from src.ui.pages import compute_tab_coverage
        rows = compute_tab_coverage(state={
            "cl_data": {"inst": [1], "margin": [1], "adl": [1]}  # 3/3
        })
        chip_row = next(r for r in rows if "籌碼" in r["tab"])
        assert chip_row["emoji"] == "🟢"

    def test_etf_loaded_green(self):
        from src.ui.pages import compute_tab_coverage
        rows = compute_tab_coverage(state={"etf_single_data": {"aum": 100, "cur_yield": 5}})
        etf_row = next(r for r in rows if "ETF" in r["tab"])
        assert etf_row["emoji"] == "🟢"

    def test_render_no_raise(self):
        from src.ui.pages import render_data_coverage
        render_data_coverage()  # 空 session_state stub,不 raise
