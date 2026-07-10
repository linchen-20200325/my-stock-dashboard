"""tests/test_macro_cross_ai_button_and_state.py — §九 跨桶 AI 按鈕名 + ①景氣位階 fail-loud（v19.72）。

修兩個 bug：
① 提示指向的按鈕名（「更新總經拼圖」/「🔄 更新全部總經數據」）與實際按鈕
   「🚀 一鍵更新全部數據」不符 → 使用者「找不到按鈕」。
② 其餘總經已載入卻缺「外銷訂單+PMI」時，卡①仍顯示「請點擊更新」（誤導成尚未更新）。
"""
from __future__ import annotations

import pathlib

from streamlit.testing.v1 import AppTest

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


def test_card1_honest_diagnostic_when_loaded_but_missing():
    at = AppTest.from_function(_script_loaded_but_missing).run(timeout=30)
    assert not at.exception
    allmd = " ".join(m.value for m in at.markdown)
    # 卡①不再誤說「請點擊更新」，改講實情：這兩個來源抓取失敗
    assert "景氣位階資料未就緒" in allmd
    assert "外銷訂單" in allmd and "PMI" in allmd
    assert "請先按上方" not in allmd     # 已更新 → 不該再叫他去按更新
    # 其餘卡仍正常填（不受影響）
    assert "資金明顯外逃" in allmd or "M2" in allmd


def test_card1_points_to_real_button_when_nothing_loaded():
    at = AppTest.from_function(_script_nothing_loaded).run(timeout=30)
    assert not at.exception
    allmd = " ".join(m.value for m in at.markdown)
    # 完全沒載入 → 指向【正確】按鈕名
    assert "🚀 一鍵更新全部數據" in allmd
    assert "更新總經拼圖" not in allmd
