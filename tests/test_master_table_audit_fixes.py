"""組合排行總表 資料稽核修正(2026-08)守衛。

3 個確認 bug:
  #1 殖利%:原印年均股利(元)當殖利率% → 改算 股利/現價×100(§4.1 單位)。
  #3 絕對停損:已跌破(距現價%<0)時前綴 🚨已跌破(對齊單檔頁三態)。
  #4 風報比:目標≤進場價 → rr=None(顯示「—」),不印負 RR(§1)。
"""
from __future__ import annotations

from pathlib import Path

from src.compute.strategy.pattern_targets import compute_pattern_targets
from src.ui.tabs.stock_grp_sections.section_portfolio_summary import _fmt_abs_stop

_SEC = (Path(__file__).resolve().parents[1]
        / 'src' / 'ui' / 'tabs' / 'stock_grp_sections' / 'section_portfolio_summary.py')


# ── #4 風報比:目標低於進場 → rr None ──────────────────────────
def test_pattern_rr_none_when_target_below_entry():
    """破底翻 target_n=90+(120-110)=100 ≤ sweet(neckline=120) → rr 應 gate 成 None。"""
    r = compute_pattern_targets(
        pattern='破底翻', support=95, breakdown_low=90,
        wave1_start=110, wave1_high=120, consolidation_low=90,
        neckline=120, current_price=118)
    assert r['sweet'] == 120
    assert r['target1'] is not None and r['target1'] <= r['sweet']
    assert r['rr'] is None, f"目標低於進場價 rr 應為 None,得 {r['rr']}"
    assert any('目標低於進場' in n for n in r['notes'])


def test_pattern_rr_positive_when_target_above_entry():
    """target_n=110+(130-100)=140 > sweet(neckline=120) → rr 正常為正。"""
    r = compute_pattern_targets(
        pattern='破底翻', support=95, breakdown_low=90,
        wave1_start=100, wave1_high=130, consolidation_low=110,
        neckline=120, current_price=118)
    assert r['target1'] > r['sweet']
    assert r['rr'] is not None and r['rr'] > 0


# ── #3 絕對停損:已跌破標示 ────────────────────────────────────
def test_fmt_abs_stop_breach_labeled():
    """距現價%<0(停損價在現價之上=已跌破)→ 前綴 🚨已跌破。"""
    s = _fmt_abs_stop({'_abs_stop': 314.69, '_stop_dist_pct': -17.2})
    assert '🚨已跌破' in s and '314.69' in s and '-17.2%' in s


def test_fmt_abs_stop_normal_no_breach():
    """距現價%>0(停損在現價下方=正常緩衝)→ 不加已跌破。"""
    s = _fmt_abs_stop({'_abs_stop': 2333.28, '_stop_dist_pct': 1.8})
    assert '🚨' not in s and '2333.28' in s and '+1.8%' in s


def test_fmt_abs_stop_none():
    assert _fmt_abs_stop({'_abs_stop': None}) == '—'


# ── #1 殖利%:改算真殖利率(源碼守衛;_precompute_fund_map 有 I/O 不易單測)──
def test_yield_column_computes_real_yield_not_dividend_amount():
    src = _SEC.read_text(encoding='utf-8')
    # 由「年均股利 ÷ 現價 × 100」算,不再直接把 _avg3(元)印成 %
    assert '_avg3 / _price_yld3 * 100' in src, '殖利率應由 股利/現價 計算'
    assert '_yield3' in src
    # 舊 bug pattern:直接印 _avg3 當殖利率% 應已移除
    assert "'殖利率%':  f'{_avg3" not in src
