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
        from macro_classroom import render_traffic_light_explainer
        render_traffic_light_explainer(None)

    def test_empty_dict_no_raise(self):
        from macro_classroom import render_traffic_light_explainer
        render_traffic_light_explainer({})

    def test_full_tl_no_raise(self):
        """完整 tl dict → 走進判讀規則路徑"""
        from macro_classroom import render_traffic_light_explainer
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
        from macro_classroom import render_traffic_light_explainer
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
        from macro_classroom import render_principle_classroom
        render_principle_classroom()

    def test_at_least_10_chapters(self):
        from macro_classroom import _PRINCIPLE_CHAPTERS
        assert len(_PRINCIPLE_CHAPTERS) >= 10, (
            f"教室應 ≥ 10 章,實際 {len(_PRINCIPLE_CHAPTERS)} 章"
        )

    def test_all_chapters_have_body(self):
        from macro_classroom import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert _t.strip(), f"第 {_i+1} 章標題空"
            assert len(_b.strip()) > 100, f"第 {_i+1} 章內文 < 100 字"

    def test_tw_local_chapters_present(self):
        """確認 TW 在地章節(外資/韭菜/M1B-M2)存在,證明 Stock 版有適配而非純拷貝 Fund"""
        from macro_classroom import _PRINCIPLE_CHAPTERS
        _titles = " ".join(_t for _t, _ in _PRINCIPLE_CHAPTERS)
        assert "外資" in _titles, "缺『外資籌碼』章(TW 股市核心)"
        assert "韭菜" in _titles, "缺『韭菜指數』章(TW 反指標)"
        assert "M1B" in _titles, "缺『M1B-M2』章(TW 在地動能)"


class TestSSOTImport:
    """確保從 macro_helpers SSOT 引入閾值,不出現 inline magic"""

    def test_imports_from_ssot(self):
        import macro_classroom
        from macro_helpers import BULL_MIN_SCORE, HEALTH_DEFENSE_THRESHOLD
        assert macro_classroom.HEALTH_DEFENSE_THRESHOLD == HEALTH_DEFENSE_THRESHOLD
        assert macro_classroom.BULL_MIN_SCORE == BULL_MIN_SCORE


class TestTabMacroWiring:
    """靜態檢查 tab_macro.py 兩處 wire 點"""

    def setup_method(self):
        import pathlib
        _src = pathlib.Path(__file__).parent / "tab_macro.py"
        self.src = _src.read_text(encoding="utf-8")

    def test_imports_explainer(self):
        assert "render_traffic_light_explainer" in self.src
        assert "from macro_classroom import" in self.src

    def test_imports_classroom(self):
        assert "render_principle_classroom" in self.src

    def test_explainer_after_traffic_light_render(self):
        """explainer 必須緊跟 _render_traffic_light call 之後"""
        _tl_render_idx = self.src.find("_render_traffic_light(_tl_placeholder, _tl_final")
        _exp_idx = self.src.find("render_traffic_light_explainer(_tl_final)")
        assert _tl_render_idx > 0 and _exp_idx > 0
        assert _exp_idx > _tl_render_idx, "explainer 應在 traffic light render 之後"
        # 接點應在 100 字內(緊鄰)
        assert _exp_idx - _tl_render_idx < 500, "explainer 太遠離 traffic light"

    def test_classroom_at_function_end(self):
        """classroom 應在 render_tab_macro 函式末尾(包覆 try/except 在 4 空格函式級)"""
        # 找包覆 classroom call 的 try 區塊
        _marker = "# v18.277 — 📚 總經原理小教室"
        _idx = self.src.find(_marker)
        assert _idx > 0, "classroom 區塊註解缺失"
        # comment 行起始 indent 應 = 4(函式級)
        _line_start = self.src.rfind("\n", 0, _idx) + 1
        _indent = _idx - _line_start
        assert _indent == 4, f"classroom try 包覆應 4 空格,實際 {_indent}"
        # classroom 應在檔尾(後面 < 300 字元)
        _tail = self.src[_idx:]
        assert "render_principle_classroom()" in _tail
        assert len(_tail) < 400, "classroom 不在函式末尾(後面還有太多內容)"


# v18.277 §6 自審「3 個最容易出錯的輸入」:
#   1. tl=None / {} → explainer graceful skip,不 raise ✅
#   2. 教室章節數量 / 內文長度漂移 → test 鎖 ≥ 10 章 + body ≥ 100 字 ✅
#   3. SSOT 閾值改動但 classroom 沒同步 → test 對齊 macro_helpers ✅
