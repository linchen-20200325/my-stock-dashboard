"""tests/test_caisen_ui_mounted.py — v19.162 守衛:蔡森目標價 Tab。

釘住:(1) app.py 有掛載 + UI 可 forward import、(2) UI 走 L2 SSOT compute_caisen_targets
不自算、(3) L2 引擎純度(只 import math/__future__,零 I/O)。避免孤兒 + 分層違憲回歸。
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def test_render_caisen_importable_via_package():
    from src.ui.tabs import render_caisen_targets_tab
    assert callable(render_caisen_targets_tab)


def test_app_py_mounts_caisen_tab():
    src = (_REPO / "app.py").read_text(encoding="utf-8")
    assert "render_caisen_targets_tab" in src, "app.py 未掛載 蔡森目標價 render(孤兒風險)"
    assert "🎯 蔡森目標價" in src, "app.py 選股群組未見 蔡森目標價 子 Tab 標籤"


def test_ui_uses_l2_ssot_not_selfcompute():
    src = (_REPO / "src/ui/tabs/caisen_targets_ui.py").read_text(encoding="utf-8")
    assert "from src.compute.strategy import" in src, "UI 未走 L2 strategy 套件"
    assert "compute_caisen_targets" in src, "UI 未用 L2 SSOT 計算(疑似自算)"


def test_reusable_component_wired_into_stock_and_group():
    """v19.163:蔡森核心可重用元件 render_caisen_for_ticker 接進 個股 + 組合 Tab。"""
    from src.ui.tabs.caisen_targets_ui import render_caisen_for_ticker
    assert callable(render_caisen_for_ticker)
    stock = (_REPO / "src/ui/tabs/tab_stock.py").read_text(encoding="utf-8")
    grp = (_REPO / "src/ui/tabs/tab_stock_grp.py").read_text(encoding="utf-8")
    assert "render_caisen_for_ticker" in stock and "cs_stk" in stock, "個股 Tab 未接蔡森目標價"
    assert "render_caisen_for_ticker" in grp and "cs_grp" in grp, "個股組合 Tab 未接蔡森目標價"


def test_l2_engine_pure_no_io():
    """L2 引擎只准 import math / __future__(§8.2 L2 無 I/O)。"""
    src = (_REPO / "src/compute/strategy/caisen_targets.py").read_text(encoding="utf-8")
    for mod in re.findall(r'^\s*(?:import|from)\s+([\w.]+)', src, re.M):
        top = mod.split('.')[0]
        assert top in ("math", "__future__"), f"L2 引擎誤 import {mod}(破壞純函式)"
