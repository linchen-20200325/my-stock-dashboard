"""ETF 7 維度評分合成 — 線性標準化 + 加權合成 + 星等映射。

v18.223:服務 etf_tab_grp_compare 多檔批次評分。
維度:1Y累積 / 3Y CAGR / 夏普 / MDD / 費用率 / AUM / 殖利率穩定度
星等映射沿用 etf_quality:≥ETF_RATING_EXCELLENT_MIN 5★ ... <ETF_RATING_FAIR_MIN 1★
(C2 v18.402:4 個門檻已抽 shared/signal_thresholds.py:ETF_RATING_*)
"""
from __future__ import annotations

import math

from shared.signal_thresholds import (  # C2 v18.402:ETF 星等 SSOT
    ETF_RATING_EXCELLENT_MIN,
    ETF_RATING_FAIR_MIN,
    ETF_RATING_GOOD_MIN,
    ETF_RATING_VERY_GOOD_MIN,
)

_WEIGHTS = {
    'total_ret_1y': 0.25,
    'cagr_3y':      0.20,
    'sharpe':       0.15,
    'mdd':          0.15,
    'expense_ratio': 0.12,
    'aum':          0.08,
    'div_yield_cv': 0.05,
}

# (滿分值, 零分值) — 滿分值可能比零分值大或小（線性 rescale 自動處理）
_NORM = {
    'total_ret_1y':  (10.0,  -5.0),
    'cagr_3y':       ( 8.0,   0.0),
    'sharpe':        ( 1.0,   0.2),
    'mdd':           (-10.0, -30.0),
    'expense_ratio': (0.003, 0.015),
    'aum_log':       (10.0,   9.0),
}


def _norm(value, hi, lo):
    """線性 rescale 至 [0, 1]。value=hi → 1，value=lo → 0。"""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    if hi == lo:
        return None
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def compute_etf_composite_score(row: dict) -> tuple[float | None, int | None]:
    """7 維度標準化 + 加權合成。回傳 (綜合分 0~1, 星等 1~5)。缺項 rescale 有效權重。"""
    _scores: dict[str, float | None] = {
        'total_ret_1y':  _norm(row.get('total_ret_1y'),  *_NORM['total_ret_1y']),
        'cagr_3y':       _norm(row.get('cagr_3y'),       *_NORM['cagr_3y']),
        'sharpe':        _norm(row.get('sharpe'),        *_NORM['sharpe']),
        'mdd':           _norm(row.get('mdd'),           *_NORM['mdd']),
        'expense_ratio': _norm(row.get('expense_ratio'), *_NORM['expense_ratio']),
    }
    _aum = row.get('aum')
    if _aum and _aum > 0:
        _scores['aum'] = _norm(math.log10(float(_aum)), *_NORM['aum_log'])
    else:
        _scores['aum'] = None
    # 殖利率穩定度借用 etf_quality.compute_etf_quality 的 yield_cv 子分（已是 0-1）
    _q = row.get('quality') or {}
    _factors = _q.get('factors') or {}
    _yc = _factors.get('yield_cv') or {}
    _scores['div_yield_cv'] = _yc.get('score')

    _valid_w = 0.0
    _weighted = 0.0
    for _k, _s in _scores.items():
        if _s is None:
            continue
        _w = _WEIGHTS[_k]
        _valid_w += _w
        _weighted += _w * _s
    if _valid_w <= 0:
        return None, None
    _score = _weighted / _valid_w
    if _score >= ETF_RATING_EXCELLENT_MIN:
        _stars = 5
    elif _score >= ETF_RATING_VERY_GOOD_MIN:
        _stars = 4
    elif _score >= ETF_RATING_GOOD_MIN:
        _stars = 3
    elif _score >= ETF_RATING_FAIR_MIN:
        _stars = 2
    else:
        _stars = 1
    return round(_score, 3), _stars
