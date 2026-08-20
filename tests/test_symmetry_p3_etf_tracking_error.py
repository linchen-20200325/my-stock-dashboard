"""#3 v19.200(對稱性稽核)—— ETF 多檔「留/觀察/換」判定納入追蹤誤差(**僅市值型**)。

病症
====
`calc_tracking_error` 早已算好、多檔比較表也顯示「追蹤誤差%」欄,但
`recommend_etf_action`(留/觀察/換 判定)完全不看它 → 追蹤誤差對判定零影響。
單檔頁對高 TE 有 ⚠️ 提示,多檔判定卻沒有 = 不對稱。

為什麼閘門用「同指數」而非「市值型」(§-1 關鍵)
================================================
追蹤誤差一律以 `auto_detect_benchmark` → 0050.TW 為基準。TE 只有在「該 ETF 理應追蹤
0050 追的那支指數(FTSE 台灣50)」時才有「追不準 = 隱藏成本」意義。與 0050 同指數者
只有 0050 / 006208。其餘 ETF 追**不同**指數,TE vs 0050 天生偏高、屬設計差異而非缺陷:
  - 高股息(0056/00878/00919)/ 主題 / 債券 / 海外 —— 明顯不追 0050;
  - **中型100(0051)、領袖50(00922)、ESG低碳50(00923)** —— 雖列「市值型」,但追的是
    互斥/篩選後的**不同**指數 → 若用寬鬆「市值型」閘門會誤殺 0051 等,正是本修法要
    避免的 §-1 誤判換位重演。故閘門用精確 `tracks_tw50_index`(同指數集合)。

3 個最容易出錯的輸入(本檔涵蓋):
  1. 高股息 ETF(0056)+ 中型100(0051)高 TE vs 0050 —— **不可**降級(設計差異,非缺陷)。
  2. 006208(與 0050 同指數)高 TE —— 應降級(真隱藏成本)。
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
from src.compute.etf.etf_categories import tracks_tw50_index
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


# ── tracks_tw50_index 分類(閘門)──────────────────────────────
def test_tracks_tw50_index_classification():
    assert tracks_tw50_index('0050.TW') is True         # FTSE 台灣50
    assert tracks_tw50_index('006208.TW') is True        # 富邦台50 同指數
    assert tracks_tw50_index('0056.TW') is False         # 高股息
    assert tracks_tw50_index('00878.TW') is False        # 高股息
    assert tracks_tw50_index('0051.TW') is False         # 中型100(互斥宇宙,非同指數)
    assert tracks_tw50_index('00922.TW') is False        # 領袖50(不同指數)
    assert tracks_tw50_index('00923.TW') is False        # ESG低碳50(不同指數)
    assert tracks_tw50_index('00891.TW') is False        # 半導體
    assert tracks_tw50_index('00679B.TW') is False       # 債券
    assert tracks_tw50_index('9999.TW') is False         # 查無
    # 格式容錯:.TWO / 裸碼 / None / ''
    assert tracks_tw50_index('0050.TWO') is True
    assert tracks_tw50_index('006208') is True
    assert tracks_tw50_index(None) is False
    assert tracks_tw50_index('') is False


# ── 核心:同指數降級、非同指數(含中型/高股息)豁免 ───────────────
def test_same_index_high_te_flagged_and_downgraded():
    """006208(與 0050 同指數)綜合分高(本應留)+ 高 TE → 紅旗 + 留→觀察。"""
    v = recommend_etf_action(_row('006208.TW', composite=0.9, te=_HIGH_TE))
    assert any('追蹤誤差' in f for f in v['red_flags']), '同指數高 TE 應觸發紅旗'
    assert v['verdict'] == VERDICT_WATCH, '高 TE 應把「留下」降級為「觀察」'


def test_high_dividend_high_te_NOT_flagged():
    """高股息 0056 同樣高 TE(vs 0050)→ **不**觸發紅旗、維持「留下」(§-1 不誤殺)。"""
    v = recommend_etf_action(_row('0056.TW', composite=0.9, te=_HIGH_TE))
    assert not any('追蹤誤差' in f for f in v['red_flags']), \
        '高股息 ETF 的 TE vs 0050 天生高,不得當缺陷降級'
    assert v['verdict'] == VERDICT_KEEP


def test_midcap_0051_high_te_NOT_flagged():
    """中型100(0051)雖列『市值型』但追**不同**指數 → 高 TE vs 0050 豁免(audit 抓到的誤判)。"""
    v = recommend_etf_action(_row('0051.TW', composite=0.9, te=_HIGH_TE))
    assert not any('追蹤誤差' in f for f in v['red_flags']), \
        '0051 中型100 追不同指數,TE vs 0050 天生高,不得降級'
    assert v['verdict'] == VERDICT_KEEP


def test_same_index_low_te_not_flagged():
    """同指數但 TE 未達門檻 → 不觸發。"""
    v = recommend_etf_action(_row('006208.TW', composite=0.9, te=_LOW_TE))
    assert not any('追蹤誤差' in f for f in v['red_flags'])
    assert v['verdict'] == VERDICT_KEEP


def test_te_none_no_flag_no_crash():
    """TE=None(算不出)→ 不觸發、不炸。"""
    v = recommend_etf_action(_row('006208.TW', composite=0.9, te=None))
    assert not any('追蹤誤差' in f for f in v['red_flags'])
    assert v['verdict'] == VERDICT_KEEP


def test_same_index_watch_downgraded_to_switch():
    """同指數中庸分(觀察)+ 高 TE → 觀察→考慮換。"""
    v = recommend_etf_action(_row('006208.TW', composite=0.5, te=_HIGH_TE))
    assert any('追蹤誤差' in f for f in v['red_flags'])
    assert v['verdict'] == VERDICT_SWITCH


def test_semiconductor_etf_exempt():
    """半導體 ETF(00891)高 TE vs 0050 → 豁免(非同指數)。"""
    v = recommend_etf_action(_row('00891.TW', composite=0.9, te=_HIGH_TE))
    assert not any('追蹤誤差' in f for f in v['red_flags'])
    assert v['verdict'] == VERDICT_KEEP
