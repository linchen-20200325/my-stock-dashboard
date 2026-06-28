"""v18.277 tests — Stock macro_classroom 紅綠燈說明 + 原理小教室。

驗證:
1. render_traffic_light_explainer 對缺資料 graceful(不 raise)
2. render_principle_classroom 不 raise + ≥ 10 章
3. SSOT 閾值正確 import(HEALTH_DEFENSE_THRESHOLD / BULL_MIN_SCORE)
4. tab_macro wire 點靜態驗證
"""
from __future__ import annotations

import sys
import types

import pytest


def _stub_streamlit():
    if "streamlit" in sys.modules and getattr(
        sys.modules["streamlit"], "_is_test_stub", False
    ):
        return
    _mod = types.ModuleType("streamlit")
    _mod._is_test_stub = True

    def _noop(*a, **k):
        return None

    def _ctx(*a, **k):
        class _Ctx:
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
        return _Ctx()

    for _name in (
        "markdown", "caption", "divider", "info", "success", "warning",
        "metric", "code",
    ):
        setattr(_mod, _name, _noop)
    _mod.expander = _ctx

    # v18.281 — tab_edu 用 @st.cache_data 裝飾,stub 需支援
    # 兩種呼叫:@st.cache_data 與 @st.cache_data(ttl=...)
    def _cache_data(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f
    _mod.cache_data = _cache_data
    _mod.cache_resource = _cache_data
    _mod.columns = lambda spec, **k: [_ctx() for _ in
                                      range(spec if isinstance(spec, int) else len(spec))]

    class _SS(dict):
        def get(self, k, default=None):
            return super().get(k, default)
    _mod.session_state = _SS()
    sys.modules["streamlit"] = _mod


_stub_streamlit()


# ════════════════════════════════════════════════════════════════
# render_traffic_light_explainer
# ════════════════════════════════════════════════════════════════

class TestTrafficLightExplainer:
    def test_none_tl_no_raise(self):
        from src.ui.tabs import render_traffic_light_explainer
        render_traffic_light_explainer(None)

    def test_empty_dict_no_raise(self):
        from src.ui.tabs import render_traffic_light_explainer
        render_traffic_light_explainer({})

    def test_full_tl_no_raise(self):
        """完整 tl dict → 走進判讀規則路徑"""
        from src.ui.tabs import render_traffic_light_explainer
        _tl = {
            'color': '#f85149',
            'label': '空頭防禦｜降低部位',
            'health': 25,
            'score': 1,
            'regime': 'bear',
            'defense': True,
            'fut_net': -45000,
            'conf': 85,
        }
        render_traffic_light_explainer(_tl)

    def test_bull_tl_no_raise(self):
        from src.ui.tabs import render_traffic_light_explainer
        _tl = {
            'color': '#3fb950',
            'label': '多頭市場｜積極操作',
            'health': 72,
            'score': 5,
            'regime': 'bull',
            'defense': False,
            'fut_net': 35000,
            'conf': 95,
        }
        render_traffic_light_explainer(_tl)


class TestPrincipleClassroom:
    def test_render_no_raise(self):
        from src.ui.tabs import render_principle_classroom
        render_principle_classroom()

    def test_at_least_10_chapters(self):
        from src.ui.tabs import _PRINCIPLE_CHAPTERS
        assert len(_PRINCIPLE_CHAPTERS) >= 10, (
            f"教室應 ≥ 10 章,實際 {len(_PRINCIPLE_CHAPTERS)} 章"
        )

    def test_all_chapters_have_body(self):
        from src.ui.tabs import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert _t.strip(), f"第 {_i+1} 章標題空"
            assert len(_b.strip()) > 100, f"第 {_i+1} 章內文 < 100 字"

    def test_tw_local_chapters_present(self):
        """確認 TW 在地章節(外資/韭菜/M1B-M2)存在,證明 Stock 版有適配而非純拷貝 Fund"""
        from src.ui.tabs import _PRINCIPLE_CHAPTERS
        _titles = " ".join(_t for _t, _ in _PRINCIPLE_CHAPTERS)
        assert "外資" in _titles, "缺『外資籌碼』章(TW 股市核心)"
        assert "韭菜" in _titles, "缺『韭菜指數』章(TW 反指標)"
        assert "M1B" in _titles, "缺『M1B-M2』章(TW 在地動能)"


class TestChapterDepthEnhancement:
    """v18.278 — 每章必須含 白話 + 📐 公式 + 📜 案例 三層深度"""

    def test_every_chapter_has_formula_section(self):
        from src.ui.tabs import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert "📐" in _b, (
                f"第 {_i+1} 章 ({_t[:20]}) 缺 📐 數學定義段"
            )

    def test_every_chapter_has_history_case_section(self):
        from src.ui.tabs import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert "📜" in _b, (
                f"第 {_i+1} 章 ({_t[:20]}) 缺 📜 歷史案例段"
            )

    def test_chapters_substantially_longer(self):
        from src.ui.tabs import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert len(_b.strip()) > 400, (
                f"第 {_i+1} 章 ({_t[:20]}) body {len(_b.strip())} 字 < 400(深化未達標)"
            )

    def test_chapters_have_twii_specific_cases(self):
        """歷史案例段必須含 TWII / TW PMI / 外資 等 TW 在地數據"""
        from src.ui.tabs import _PRINCIPLE_CHAPTERS
        _all = " ".join(_b for _, _b in _PRINCIPLE_CHAPTERS)
        # 至少 3 章應含 TWII / TW PMI / 外資 等 TW 本地 keyword
        _tw_keywords = ["TWII", "TW PMI", "TW 50", "台股"]
        _hits = sum(1 for kw in _tw_keywords if kw in _all)
        assert _hits >= 3, (
            f"TW 在地數據覆蓋不足:只 {_hits} / 4 個 keyword 命中"
        )

    def test_chapters_have_numeric_dates_in_cases(self):
        from src.ui.tabs import _PRINCIPLE_CHAPTERS
        import re
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            _hist_idx = _b.find("📜")
            assert _hist_idx > 0
            _hist_section = _b[_hist_idx:]
            _years = re.findall(r"(?:19[89]\d|20[012]\d)", _hist_section)
            assert len(_years) >= 3, (
                f"第 {_i+1} 章 ({_t[:20]}) 案例段年份 < 3 個(實際 {len(_years)}個)"
            )


class TestSSOTImport:
    """確保從 macro_helpers SSOT 引入閾值,不出現 inline magic"""

    def test_imports_from_ssot(self):
        from src.ui.tabs import macro_classroom
        from src.compute.macro import BULL_MIN_SCORE, HEALTH_DEFENSE_THRESHOLD
        assert macro_classroom.HEALTH_DEFENSE_THRESHOLD == HEALTH_DEFENSE_THRESHOLD
        assert macro_classroom.BULL_MIN_SCORE == BULL_MIN_SCORE


class TestTabMacroWiring:
    """靜態檢查 tab_macro.py 兩處 wire 點"""

    def setup_method(self):
        import pathlib
        _src = pathlib.Path(__file__).resolve().parent.parent / "src/ui/tabs/tab_macro.py"
        self.src = _src.read_text(encoding="utf-8")

    def test_imports_explainer(self):
        assert "render_traffic_light_explainer" in self.src
        assert "from src.ui.tabs import" in self.src or "from src.ui.tabs.macro_classroom import" in self.src

    def test_classroom_moved_to_manual(self):
        """v18.281: 教室已從 tab_macro 移至 tab_edu(系統說明書)。
        tab_macro 不再渲染教室,只留指引 caption。"""
        # tab_macro 不應再呼叫 render_principle_classroom()
        assert "render_principle_classroom()" not in self.src, \
            "教室應已移出 tab_macro(改在 tab_edu 系統說明書)"
        # 應留指引到「系統說明書」
        assert "系統說明書" in self.src, "tab_macro 應留指引到系統說明書 Tab"

    def test_explainer_after_traffic_light_render(self):
        """explainer 必須緊跟 _render_traffic_light call 之後(留在 tab_macro)"""
        _tl_render_idx = self.src.find("_render_traffic_light(_tl_placeholder, _tl_final")
        _exp_idx = self.src.find("render_traffic_light_explainer(_tl_final)")
        assert _tl_render_idx > 0 and _exp_idx > 0
        assert _exp_idx > _tl_render_idx, "explainer 應在 traffic light render 之後"
        assert _exp_idx - _tl_render_idx < 500, "explainer 太遠離 traffic light"

    def test_classroom_rendered_in_tab_edu(self):
        """v18.281: 教室現由 tab_edu(系統說明書)渲染"""
        import pathlib
        _edu = (pathlib.Path(__file__).resolve().parent.parent / "src/ui/tabs/tab_edu.py").read_text(encoding="utf-8")
        assert "render_principle_classroom()" in _edu, \
            "tab_edu(系統說明書)應呼叫 render_principle_classroom"
        assert "系統說明書" in _edu, "tab_edu 標題應為系統說明書"
        assert "資料來源完整地圖" in _edu, "tab_edu 應含資料來源完整地圖(學 Fund Section ⓪)"


# v18.277 §6 自審「3 個最容易出錯的輸入」:
#   1. tl=None / {} → explainer graceful skip,不 raise ✅
#   2. 教室章節數量 / 內文長度漂移 → test 鎖 ≥ 10 章 + body ≥ 100 字 ✅
#   3. SSOT 閾值改動但 classroom 沒同步 → test 對齊 macro_helpers ✅


class TestFactCorrectionsV18279:
    """v18.279 — 查證後事實修正回歸守衛(防數字被改回錯誤版本)。

    來源:2026-06-25 四路平行查證(CIER / 國發會 / TWSE / FRED / ISM / CBOE 交叉)。
    """

    def _all_text(self):
        from src.ui.tabs import _PRINCIPLE_CHAPTERS
        return "\n".join(b for _, b in _PRINCIPLE_CHAPTERS)

    def test_no_fabricated_tw_pmi_pre2012(self):
        """台灣官方 PMI 2012/7 才創編 — 不可出現 2008/2009 的台灣 PMI 數值。

        原造假值:2008/12=33.7、2009/3=49.6。必須移除。
        """
        t = self._all_text()
        assert "33.7" not in t, "造假的 TW PMI 2008/12=33.7 不可復現"
        assert "49.6" not in t, "造假的 TW PMI 2009/3=49.6 不可復現"
        # 須明示 CIER 創編年份
        assert "2012" in t and "創編" in t

    def test_2015_foreign_net_buy_not_sell(self):
        """2015 全年外資是淨買超 +422 億,非賣超(符號修正)"""
        t = self._all_text()
        assert "淨買超" in t and "422" in t

    def test_ndc_blue_light_record_corrected(self):
        """國發會藍燈:dot-com 15 月才是史上最長(非海嘯 16 月)"""
        t = self._all_text()
        assert "**15** 月藍燈" in t and "史上最長" in t
        # 不可再宣稱海嘯「連 16 月藍燈(史上最長)」
        assert "連 16 月藍燈(史上最長)" not in t

    def test_margin_2000_peak_corrected(self):
        """融資史上最高在 2000/4 = 5,956 億(非 2000/2 = 4500 億)"""
        t = self._all_text()
        assert "5,956 億" in t
        assert "4500 億" not in t

    def test_merrill_clock_citation_disclaimer(self):
        """美林矩陣帶免責 + 無捏造的『高峰 現金 +5.7%』"""
        t = self._all_text()
        assert "各方引用略有出入" in t
        assert "+5.7%" not in t

    def test_yield_inversion_not_all_time_deepest(self):
        """倒掛『1981 年來最深』非『史上最深』"""
        t = self._all_text()
        assert "1981 年來最深" in t
        assert "-1.1%**(史上最深)" not in t

    def test_vix_intraday_close_distinguished(self):
        """VIX 89.5 盤中 vs 82.7 收盤須標明"""
        t = self._all_text()
        assert "盤中史上最高" in t and "收盤史上最高" in t
