"""tests/test_pattern_targets_ui_mounted.py — v19.162 守衛:型態目標價 UI。

v19.174 去識別化改名:原檔名 `test_caisen_ui_mounted.py`;受測模組
`caisen_targets_ui.py` → `pattern_targets_ui.py`、
`caisen_targets.py` → `pattern_targets.py`、
`render_caisen_for_ticker` → `render_pattern_targets_for_ticker`、
`summarize_caisen` → `summarize_pattern`、結果欄 `_caisen` → `_pattern`。

釘住:(1) 可 forward import、(2) UI 走 L2 SSOT compute_pattern_targets 不自算、
(3) L2 引擎純度(只 import math/__future__,零 I/O)、(4) 人名不得回流。
避免孤兒 + 分層違憲回歸。
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]

# v19.174 去識別化**守衛黑名單**(人名 + 羅馬拼音)——
# 這是刻意保留的檢查清單,不是殘留;全 repo 掃人名時請跳過本區塊。
_BANNED = ('孫慶龍', '郭俊宏', '林明樟', '蔡森', '春哥',
           '弘爺', '妮可', '朱家泓', '宏爺', 'caisen')


def test_render_pattern_targets_for_ticker_importable():
    """v19.163:核心可重用元件可直接 import(不再有獨立分頁,見 test_reusable_*)。"""
    from src.ui.tabs.pattern_targets_ui import render_pattern_targets_for_ticker
    assert callable(render_pattern_targets_for_ticker)


def test_no_standalone_pattern_tab():
    """v19.163 user 要求:型態目標價不設獨立分頁(只內嵌個股/組合)。"""
    src = (_REPO / "app.py").read_text(encoding="utf-8")
    assert "render_caisen_targets_tab" not in src, "殘留獨立型態分頁掛載(舊名)"
    assert "render_pattern_targets_tab" not in src, "殘留獨立型態分頁掛載(新名)"


def test_ui_uses_l2_ssot_not_selfcompute():
    src = (_REPO / "src/ui/tabs/pattern_targets_ui.py").read_text(encoding="utf-8")
    assert "from src.compute.strategy import" in src, "UI 未走 L2 strategy 套件"
    assert "compute_pattern_targets" in src, "UI 未用 L2 SSOT 計算(疑似自算)"


def test_reusable_component_wired_into_stock_and_group():
    """核心 render_pattern_targets_for_ticker 接進 個股(單檔)+ 組合(v19.164 批次表 + 下鑽)。"""
    from src.ui.tabs.pattern_targets_ui import render_pattern_targets_for_ticker
    assert callable(render_pattern_targets_for_ticker)
    stock = (_REPO / "src/ui/tabs/tab_stock.py").read_text(encoding="utf-8")
    # v19.164:組合的型態目標價從 tab_stock_grp 下沉到 section_portfolio_summary(批次表 + 下鑽)
    grp_sec = (_REPO / "src/ui/tabs/stock_grp_sections/section_portfolio_summary.py"
               ).read_text(encoding="utf-8")
    assert "render_pattern_targets_for_ticker" in stock and "cs_stk" in stock, \
        "個股 Tab 未接型態目標價"
    assert "render_pattern_targets_for_ticker" in grp_sec and "cs_grp" in grp_sec, \
        "個股組合 未接型態目標價(批次表/下鑽)"


def test_pattern_batch_summary_wired():
    """v19.164:型態批次化 — 批次抓取器就地算 summarize_pattern 塞 results_t3(_pattern)。"""
    batch = (_REPO / "src/ui/tabs/stock_grp_sections/section_batch_fetcher.py"
             ).read_text(encoding="utf-8")
    assert "summarize_pattern" in batch, "批次抓取器未接型態批次摘要"
    assert "'_pattern'" in batch, "批次結果未帶 _pattern 欄(總表/下鑽取用)"


def test_l2_engine_pure_no_io():
    """L2 引擎只准 import math / __future__(§8.2 L2 無 I/O)。"""
    src = (_REPO / "src/compute/strategy/pattern_targets.py").read_text(encoding="utf-8")
    for mod in re.findall(r'^\s*(?:import|from)\s+([\w.]+)', src, re.M):
        top = mod.split('.')[0]
        assert top in ("math", "__future__"), f"L2 引擎誤 import {mod}(破壞純函式)"


def test_no_person_name_in_renamed_modules():
    """v19.174 守衛:改名後的兩個模組原始碼不得再出現人名(含羅馬拼音)。

    舊檔 `caisen_targets*.py` 是待刪的 deprecation 轉發,不在掃描範圍;
    新檔一旦被加回人名,這條會紅。
    """
    for rel in ("src/compute/strategy/pattern_targets.py",
                "src/ui/tabs/pattern_targets_ui.py"):
        src = (_REPO / rel).read_text(encoding="utf-8")
        # 過渡期 alias 行本身帶舊名 caisen_*,屬預期內 → 只掃非 alias 行
        body = "\n".join(ln for ln in src.splitlines()
                         if "caisen" not in ln.lower())
        hit = [n for n in _BANNED if n in body]
        assert not hit, f"{rel} 殘留人名：{hit}"
