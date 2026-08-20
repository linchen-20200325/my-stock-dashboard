"""#3 v19.200(對稱性稽核)—— ETF 多檔「留/觀察/換」判定納入追蹤誤差(**僅市值型**)。

病症
====
`calc_tracking_error` 早已算好、多檔比較表也顯示「追蹤誤差%」欄,但
`recommend_etf_action`(留/觀察/換 判定)完全不看它 → 追蹤誤差對判定零影響。
單檔頁對高 TE 有 ⚠️ 提示,多檔判定卻沒有 = 不對稱。

為什麼**只**對市值型加(§-1 關鍵)
================================
追蹤誤差一律以 `auto_detect_benchmark` → 0050.TW 為基準。只有市值型(追蹤台灣 50 /
大盤市值指數)拿 TE vs 0050 才有「追不準 = 隱藏成本」意義;高股息 / 主題 / 債券 /
海外等**本就不追 0050**,其 TE vs 0050 天生偏高、屬設計差異而非缺陷。若一律降級,
會誤殺 user 核心存股(0056 / 00878 / 00919 …)。故 red-flag 以 `is_market_cap_type` 閘門。

3 個最容易出錯的輸入(本檔涵蓋):
  1. 高股息 ETF(0056)高 TE vs 0050 —— **不可**降級(設計差異,非缺陷)。
  2. 市值型 ETF(0050)高 TE —— 應降級(真隱藏成本)。
  3. TE=None(單檔頁可能算不出)—— 不可炸、不可誤判為缺陷。
"""
from __future__ import annotations

import pytest

from shared.etf_recommendation_thresholds import (
    VERDICT_KEEP,
    VERDICT_SWITCH,
    VERDICT_WATCH,
)
from shared.signal_thresholds import ETF_TRACKING_ERROR_MAX_PCT
from src.compute.etf.etf_categories import is_market_cap_type
from src.compute.etf.etf_recommendation import recommend_etf_action

_HIGH_TE = ETF_TRACKING_ERROR_MAX_PCT + 0.5   # 超門檻
_LOW_TE = ETF_TRACKING_ERROR_MAX_PCT - 0.5    # 未達門檻


def _row(ticker, composite, te):
    """乾淨 row(不觸發流動性/配息紅旗,只驗 TE 這條)。"""
    return {
        'ticker': ticker, 'composite': composite, 'tracking_error': te,
        'liquidity_level': '🟢', 'dividend_health': '🟢 健康',
        'valuation_zone': '—', 'sigma_z': None, 'error': None,
    }


# ── is_market_cap_type 分類 ────────────────────────────────────
def test_is_market_cap_type_classification():
    assert is_market_cap_type('0050.TW') is True
    assert is_market_cap_type('006208.TW') is True
    assert is_market_cap_type('0056.TW') is False       # 高股息
    assert is_market_cap_type('00878.TW') is False      # 高股息
    assert is_market_cap_type('00891.TW') is False      # 半導體
    assert is_market_cap_type('00679B.TW') is False     # 債券
    assert is_market_cap_type('9999.TW') is False       # 查無


# ── 核心:市值型降級、高股息豁免 ───────────────────────────────
def test_market_cap_high_te_flagged_and_downgraded():
    """市值型 0050 綜合分高(本應留)+ 高 TE → 紅旗 + 留→觀察。"""
    v = recommend_etf_action(_row('0050.TW', composite=0.9, te=_HIGH_TE))
    assert any('追蹤誤差' in f for f in v['red_flags']), '市值型高 TE 應觸發紅旗'
    assert v['verdict'] == VERDICT_WATCH, '高 TE 應把「留下」降級為「觀察」'


def test_high_dividend_high_te_NOT_flagged():
    """高股息 0056 同樣高 TE(vs 0050)→ **不**觸發紅旗、維持「留下」(§-1 不誤殺)。"""
    v = recommend_etf_action(_row('0056.TW', composite=0.9, te=_HIGH_TE))
    assert not any('追蹤誤差' in f for f in v['red_flags']), \
        '高股息 ETF 的 TE vs 0050 天生高,不得當缺陷降級'
    assert v['verdict'] == VERDICT_KEEP


def test_market_cap_low_te_not_flagged():
    """市值型但 TE 未達門檻 → 不觸發。"""
    v = recommend_etf_action(_row('0050.TW', composite=0.9, te=_LOW_TE))
    assert not any('追蹤誤差' in f for f in v['red_flags'])
    assert v['verdict'] == VERDICT_KEEP


def test_te_none_no_flag_no_crash():
    """TE=None(算不出)→ 不觸發、不炸。"""
    v = recommend_etf_action(_row('0050.TW', composite=0.9, te=None))
    assert not any('追蹤誤差' in f for f in v['red_flags'])
    assert v['verdict'] == VERDICT_KEEP


def test_market_cap_watch_downgraded_to_switch():
    """市值型中庸分(觀察)+ 高 TE → 觀察→考慮換。"""
    v = recommend_etf_action(_row('0050.TW', composite=0.5, te=_HIGH_TE))
    assert any('追蹤誤差' in f for f in v['red_flags'])
    assert v['verdict'] == VERDICT_SWITCH


def test_semiconductor_etf_exempt():
    """半導體 ETF(00891)高 TE vs 0050 → 豁免(非市值型)。"""
    v = recommend_etf_action(_row('00891.TW', composite=0.9, te=_HIGH_TE))
    assert not any('追蹤誤差' in f for f in v['red_flags'])
    assert v['verdict'] == VERDICT_KEEP
