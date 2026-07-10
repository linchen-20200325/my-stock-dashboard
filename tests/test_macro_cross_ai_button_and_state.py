"""tests/test_macro_cross_ai_button_and_state.py — §九 跨桶 AI 按鈕名 + ①景氣位階 fail-loud（v19.72）。

修兩個 bug：
① 提示指向的按鈕名（「更新總經拼圖」/「🔄 更新全部總經數據」）與實際按鈕
   「🚀 一鍵更新全部數據」不符 → 使用者「找不到按鈕」。
② 其餘總經已載入卻缺「外銷訂單+PMI」時，卡①仍顯示「請點擊更新」（誤導成尚未更新）。
"""
from __future__ import annotations

import pathlib

import pytest

# v19.74:模組層 `from streamlit.testing.v1 import AppTest` 改 slow 測試內
# lazy import(對齊 test_pe_river_merge_dtype / test_render_smoke 既有慣例)。
# 原因:test_data_coverage / test_macro_classroom 在「收集(import)階段」把
# sys.modules['streamlit'] 換成 stub(非 package),本檔字母序在 macro_classroom
# 之後 → 模組層 import 直接 ModuleNotFoundError → 整個 fast lane
# Interrupted exit 2(CI run #425/#426 全紅根因)。按鈕名 source-scan 測試
# 不需 AppTest,留 fast lane;兩個 render 測試歸 slow(AppTest e2e 依 pytest.ini
# 定義本就屬 slow lane),stub 生態下 setup 偵測不可用 → skip(同 pe_river)。

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# 已淘汰的錯誤按鈕名（不得再出現在 production .py；實際按鈕為「🚀 一鍵更新全部數據」）
_STALE_BUTTON_NAMES = ("更新總經拼圖", "更新全部總經數據", "🔄 更新全部總經")


def _prod_py_files():
    files = [_ROOT / "app.py"]
    files += [p for p in (_ROOT / "src").rglob("*.py") if "__pycache__" not in str(p)]
    return files


def test_no_stale_macro_refresh_button_names():
    """全 production 碼不得再引用不存在的按鈕名（防「找不到按鈕」regression）。"""
    offenders = []
    for f in _prod_py_files():
        txt = f.read_text(encoding="utf-8")
        for bad in _STALE_BUTTON_NAMES:
            if bad in txt:
                offenders.append(f"{f.relative_to(_ROOT)} → 「{bad}」")
    assert not offenders, "殘留錯誤按鈕名：\n" + "\n".join(offenders)


# ── ① 景氣位階 fail-loud render 測試 ──────────────────────────
def _script_loaded_but_missing():
    import streamlit as st
    # 復現截圖：VIX/CPI/M1B 都有（其餘卡已填），但缺 ism_pmi + tw_export
    st.session_state["macro_info"] = {
        "vix": {"current": 15.8, "ma20": 17.5},
        "us_core_cpi": {"yoy": 3.0},
    }
    st.session_state["m1b_m2_info"] = {"m1b_yoy": 5.1, "m2_yoy": 7.8}
    st.session_state["bias_info"] = {"bias_240": 41.6}
    from src.ui.tabs.macro.section_cross_ai import render_section_cross_ai
    render_section_cross_ai(tech_s={}, tw_s={})


def _script_nothing_loaded():
    from src.ui.tabs.macro.section_cross_ai import render_section_cross_ai
    render_section_cross_ai(tech_s={}, tw_s={})


@pytest.mark.slow
class TestCard1RenderAppTest:
    """實機 render 驗證(需 streamlit.testing.v1.AppTest,對齊 pe_river 慣例)。"""

    @classmethod
    def setup_class(cls):
        try:
            from streamlit.testing.v1 import AppTest  # noqa: F401
        except ImportError:
            pytest.skip("streamlit.testing.v1.AppTest 不可用(collection stub 生態)")

    def test_card1_honest_diagnostic_when_loaded_but_missing(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_script_loaded_but_missing).run(timeout=30)
        assert not at.exception
        allmd = " ".join(m.value for m in at.markdown)
        # 卡①不再誤說「請點擊更新」，改講實情：這兩個來源抓取失敗
        assert "景氣位階資料未就緒" in allmd
        assert "外銷訂單" in allmd and "PMI" in allmd
        assert "請先按上方" not in allmd     # 已更新 → 不該再叫他去按更新
        # 其餘卡仍正常填（不受影響）
        assert "資金明顯外逃" in allmd or "M2" in allmd

    def test_card1_points_to_real_button_when_nothing_loaded(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_function(_script_nothing_loaded).run(timeout=30)
        assert not at.exception
        allmd = " ".join(m.value for m in at.markdown)
        # 完全沒載入 → 指向【正確】按鈕名
        assert "🚀 一鍵更新全部數據" in allmd
        assert "更新總經拼圖" not in allmd
