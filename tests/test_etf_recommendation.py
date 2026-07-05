"""tests/test_etf_recommendation.py — ETF 留/觀察/換 建議(L2 純函式)。

覆蓋 3 個最容易出錯的輸入:
1. 綜合分邊界(剛好 0.65 / 0.35)—— off-by-one 分級。
2. 紅旗降級(好體質但流動性🔴 / 配息吃本金)—— 不能還顯示「留」。
3. 同類重疊(2 檔同類 → 分數低者標擇一)+ error/None 不腦補。
"""
from __future__ import annotations

from shared.etf_recommendation_thresholds import (
    KEEP_COMPOSITE_MIN,
    SELL_COMPOSITE_MAX,
    VERDICT_KEEP,
    VERDICT_NA,
    VERDICT_SWITCH,
    VERDICT_WATCH,
)
from src.compute.etf.etf_recommendation import (
    recommend_etf_action,
    recommend_etf_actions,
)


def _row(**kw):
    base = {
        'ticker': '0050.TW', 'composite': 0.5, 'error': None,
        'liquidity_level': '🟢', 'dividend_health': '✅ 雙贏 +2.0pp',
        'valuation_zone': '⚪ 中性持有', 'sigma_z': 0.0,
    }
    base.update(kw)
    return base


# ── 1. 綜合分邊界 ──
def test_keep_at_threshold():
    r = recommend_etf_action(_row(composite=KEEP_COMPOSITE_MIN))
    assert r['verdict'] == VERDICT_KEEP


def test_watch_just_below_keep():
    r = recommend_etf_action(_row(composite=KEEP_COMPOSITE_MIN - 0.01))
    assert r['verdict'] == VERDICT_WATCH


def test_switch_below_sell_max():
    r = recommend_etf_action(_row(composite=SELL_COMPOSITE_MAX - 0.01))
    assert r['verdict'] == VERDICT_SWITCH


def test_watch_at_sell_max_boundary():
    # == SELL_COMPOSITE_MAX 不算「換」(嚴格 <),落在觀察
    r = recommend_etf_action(_row(composite=SELL_COMPOSITE_MAX))
    assert r['verdict'] == VERDICT_WATCH


# ── 2. 紅旗降級 ──
def test_keep_downgraded_to_watch_by_liquidity_redflag():
    r = recommend_etf_action(_row(composite=0.9, liquidity_level='🔴 高風險'))
    assert r['verdict'] == VERDICT_WATCH
    assert any('流動性' in x for x in r['red_flags'])


def test_watch_downgraded_to_switch_by_principal_erosion():
    r = recommend_etf_action(
        _row(composite=0.5, dividend_health='🔴 吃本金 -3.0pp'))
    assert r['verdict'] == VERDICT_SWITCH
    assert any('吃本金' in x for x in r['red_flags'])


def test_two_redflags_on_top_etf_still_only_two_steps():
    # 留 → (紅旗) → 觀察;不會一次掉兩級到「換」
    r = recommend_etf_action(
        _row(composite=0.95, liquidity_level='🔴 高風險',
             dividend_health='🔴 吃本金 -1.0pp'))
    assert r['verdict'] == VERDICT_WATCH
    assert len(r['red_flags']) == 2


# ── 3. 資料不足不腦補 ──
def test_error_row_returns_na():
    r = recommend_etf_action(_row(error='無 K 線資料'))
    assert r['verdict'] == VERDICT_NA


def test_none_composite_returns_watch_not_fabricated():
    r = recommend_etf_action(_row(composite=None))
    assert r['verdict'] == VERDICT_WATCH


# ── 估值/位階註解 ──
def test_cheap_valuation_adds_add_timing_note():
    r = recommend_etf_action(_row(composite=0.8, valuation_zone='🟢 強烈買進'))
    assert any('加碼' in x for x in r['reasons'])


def test_rich_sigma_adds_slowdown_note():
    r = recommend_etf_action(_row(composite=0.8, sigma_z=2.0))
    assert any('暫緩加碼' in x for x in r['reasons'])


# ── 同類重疊(需真類別:用同一 peer group 的兩檔高股息)──
def test_redundancy_marks_lower_score_peer():
    # 0056 與 00878 皆屬「高股息」peer group(etf_categories)
    rows = [
        _row(ticker='0056.TW', composite=0.8),
        _row(ticker='00878.TW', composite=0.6),
    ]
    out = recommend_etf_actions(rows)
    by_tk = {r['ticker'] if 'ticker' in r else None: v
             for r, v in zip(rows, out)}
    # reason_text 一定有值
    assert all(v.get('reason_text') for v in out)
    # 分數低者帶「擇一」提示
    low = out[1]
    assert 'redundant_note' in low
    assert '擇一' in low['redundant_note']
    # 分數高者帶「代表」提示
    high = out[0]
    assert '代表' in high.get('redundant_note', '')


def test_single_etf_no_redundancy_note():
    rows = [_row(ticker='0050.TW', composite=0.8)]
    out = recommend_etf_actions(rows)
    assert 'redundant_note' not in out[0]


def test_reason_text_joined_with_semicolon():
    rows = [_row(ticker='0050.TW', composite=0.8, valuation_zone='🟢 強烈買進')]
    out = recommend_etf_actions(rows)
    assert ';' in out[0]['reason_text']
