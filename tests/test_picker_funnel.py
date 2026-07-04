"""v18.466 守衛測試：選股網改「漏斗式」——殖利率不再當入口排序閘門。

使用者回報：選股網入口是「殖利率前50」（nlargest 殖利率），基本面三階段只在那 50 檔跑。
要求改成：全市場 → 基本面/估值初篩 → 依估值便宜度取前 N 深跑三階段（門檻 6/9），
殖利率降為最後的「殖利率確認」欄位。

本測試釘住：
  1. 三階段門檻常數 SSOT（S1 6/9、S2 3/6）。
  2. render_tab_stock_picker 用常數而非 inline `>= 5`。
  3. app.py 入口不再 nlargest 殖利率，改 nsmallest 本益比（估值便宜度）。
"""
import inspect

from src.ui.tabs.tab_stock_picker import (
    PICKER_DEEP_SCAN_N,
    PICKER_S1_MIN_PASS,
    PICKER_S2_MIN_PASS,
    render_tab_stock_picker,
)


def test_picker_thresholds_ssot_values():
    """基本面門檻應為 6/9（使用者要求由 5 拉高到 6）；籌碼技術 3/6；深掃上限 50。"""
    assert PICKER_S1_MIN_PASS == 6, '基本面門檻應為 6/9'
    assert PICKER_S2_MIN_PASS == 3, '籌碼技術門檻應為 3/6'
    assert PICKER_DEEP_SCAN_N == 50, '深掃候選池上限應為 50'


def test_qualified_gate_uses_ssot_constants():
    """通過清單門檻必須引用 SSOT 常數，不得再 inline `>= 5` / `>= 3`。"""
    src = inspect.getsource(render_tab_stock_picker)
    assert "PICKER_S1_MIN_PASS" in src, '通過門檻應引用 PICKER_S1_MIN_PASS'
    assert "PICKER_S2_MIN_PASS" in src, '通過門檻應引用 PICKER_S2_MIN_PASS'
    assert "s1_pass_cnt'] >= 5" not in src, '仍有 inline `>= 5`（應改用常數）'
    assert "s2_pass_cnt'] >= 3" not in src, '仍有 inline `>= 3`（應改用常數）'


def test_app_entry_no_longer_yield_ranked():
    """app.py 選股網入口不得再用 nlargest 殖利率當排序閘門，改 nsmallest 本益比。"""
    with open('app.py', encoding='utf-8') as f:
        app_src = f.read()
    assert "nlargest(50, '殖利率(%)')" not in app_src, (
        '選股網入口仍用「殖利率前50」nlargest 當排序閘門')
    assert "nsmallest(PICKER_DEEP_SCAN_N" in app_src, (
        '選股網入口應改用 nsmallest(PICKER_DEEP_SCAN_N, 本益比) 估值排序')
    # source_label 不再自稱「高殖利率前50」
    assert "source_label='高殖利率前50'" not in app_src
    assert "source_label='估值優選'" in app_src
