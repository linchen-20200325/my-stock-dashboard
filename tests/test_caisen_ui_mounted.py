"""tests/test_caisen_ui_mounted.py — v19.162 守衛:蔡森目標價 Tab。

釘住:(1) app.py 有掛載 + UI 可 forward import、(2) UI 走 L2 SSOT compute_caisen_targets
不自算、(3) L2 引擎純度(只 import math/__future__,零 I/O)。避免孤兒 + 分層違憲回歸。
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def test_render_caisen_for_ticker_importable():
    """v19.163:蔡森核心可重用元件可直接 import(不再有獨立分頁,見 test_reusable_*)。"""
    from src.ui.tabs.caisen_targets_ui import render_caisen_for_ticker
    assert callable(render_caisen_for_ticker)


def test_no_standalone_caisen_tab():
    """v19.163 user 要求:蔡森不設獨立分頁(只內嵌個股/組合)。"""
    src = (_REPO / "app.py").read_text(encoding="utf-8")
    assert "render_caisen_targets_tab" not in src, "殘留獨立蔡森分頁掛載"


def test_ui_uses_l2_ssot_not_selfcompute():
    src = (_REPO / "src/ui/tabs/caisen_targets_ui.py").read_text(encoding="utf-8")
    assert "from src.compute.strategy import" in src, "UI 未走 L2 strategy 套件"
    assert "compute_caisen_targets" in src, "UI 未用 L2 SSOT 計算(疑似自算)"


def test_reusable_component_wired_into_stock_and_group():
    """蔡森核心 render_caisen_for_ticker 接進 個股(單檔)+ 組合(v19.164 批次表 + 下鑽)。"""
    from src.ui.tabs.caisen_targets_ui import render_caisen_for_ticker
    assert callable(render_caisen_for_ticker)
    stock = (_REPO / "src/ui/tabs/tab_stock.py").read_text(encoding="utf-8")
    # v19.164:組合的蔡森從 tab_stock_grp 下沉到 section_portfolio_summary(批次表 + 下鑽)
    grp_sec = (_REPO / "src/ui/tabs/stock_grp_sections/section_portfolio_summary.py"
               ).read_text(encoding="utf-8")
    assert "render_caisen_for_ticker" in stock and "cs_stk" in stock, "個股 Tab 未接蔡森目標價"
    assert "render_caisen_for_ticker" in grp_sec and "cs_grp" in grp_sec, \
        "個股組合 未接蔡森目標價(批次表/下鑽)"


def test_caisen_batch_summary_wired():
    """v19.164:蔡森批次化 — 批次抓取器就地算 summarize_caisen 塞 results_t3(_caisen)。"""
    batch = (_REPO / "src/ui/tabs/stock_grp_sections/section_batch_fetcher.py"
             ).read_text(encoding="utf-8")
    assert "summarize_caisen" in batch, "批次抓取器未接蔡森批次摘要"
    assert "_caisen" in batch, "批次結果未帶 _caisen 欄(總表/下鑽取用)"


def test_l2_engine_pure_no_io():
    """L2 引擎只准 import math / __future__(§8.2 L2 無 I/O)。"""
    src = (_REPO / "src/compute/strategy/caisen_targets.py").read_text(encoding="utf-8")
    for mod in re.findall(r'^\s*(?:import|from)\s+([\w.]+)', src, re.M):
        top = mod.split('.')[0]
        assert top in ("math", "__future__"), f"L2 引擎誤 import {mod}(破壞純函式)"
