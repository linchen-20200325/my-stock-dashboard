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
    """app.py 選股網入口不得再用 nlargest 殖利率當排序閘門。

    v19.98 merge-fix:原斷言釘 v18.466/v19.74 的實作細節
    (`nsmallest(PICKER_DEEP_SCAN_N` / `gate_pool_by_fundamentals` / 估值優選),
    但選股網 v19.88-90 重設計改走 `composite_rank_candidates`(綜合評分)+
    `get_fundamental_survivors`(基本面存活池) — 舊斷言在 main 上恆紅(CI 失敗根因)。
    改釘「當前設計」的入口契約;負面斷言(不得回退殖利率排序)原樣保留。

    v19.147:選股網組裝抽成 L3 `get_ranked_picks`(畫面/cron 同源),app.py 改呼叫它;
    `composite_rank_candidates` 下沉為 get_ranked_picks 內部呼叫,不再出現在 app.py。
    斷言改釘 `get_ranked_picks`(仍是「走綜合評分排序」的同一契約,只是換入口名)。
    """
    with open('app.py', encoding='utf-8') as f:
        app_src = f.read()
    assert "nlargest(50, '殖利率(%)')" not in app_src, (
        '選股網入口仍用「殖利率前50」nlargest 當排序閘門')
    # source_label 不再自稱「高殖利率前50」
    assert "source_label='高殖利率前50'" not in app_src
    # v19.88+ 現行設計:基本面存活池 → 綜合評分 → picker(v19.147 綜合評分入口 = get_ranked_picks)
    assert "get_fundamental_survivors" in app_src, '選股網入口應接基本面存活池'
    assert "get_ranked_picks" in app_src, '選股網入口應走綜合評分排序（get_ranked_picks 同源）'
    assert "基本面優選" in app_src
