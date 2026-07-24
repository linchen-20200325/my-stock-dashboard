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


def build_etf_score_row(ticker, df, divs, info, *, quality=None,
                        tracking_error=None, zh_name=None) -> dict:
    """從已抓的 df(5y)/divs/info 組出 ETF 評分 row(單檔 + 多檔共用 row SSOT,v19.166)。

    §8.1 免重複抓取:純計算、自身零 I/O — 需 I/O 的依賴(`compute_etf_quality` /
    追蹤誤差 benchmark)由 caller 注入(quality / tracking_error),讓單檔頁能直接餵
    render 時已抓好的 df/divs/info,不必為了 🚦研判卡再抓一次。
    §1 誠實:各指標算不出一律 None / 三態標籤,不腦補;require_full_period / require_full_years
    沿用(年輕 ETF 不把「上市至今」誤標成 1Y/3Y/5Y)。回傳欄位與多檔 `_fetch_one_etf`
    完全對齊 → 多檔比較表 + `compute_etf_composite_score` + `recommend_etf_action` 直接吃。
    """
    info = info or {}
    _r = {
        'ticker': ticker, 'name': '', 'error': None,
        'price': None, 'total_ret_1y': None, 'cagr_3y': None,
        'sharpe': None, 'mdd': None,
        'expense_ratio': None, 'aum': None,
        'div_yield': None, 'beta': None, 'quality': quality,
        'premium_pct': None, 'stale_nav': False,
        'avg_yield_5y': None, 'valuation_zone': '—',
        'dividend_health': '⬜ 資料不足',
        'liquidity_level': '⚪', 'liquidity_avg_vol_20d': None, 'liquidity_reasons': [],
        'tracking_error': tracking_error,
        'sigma_buy': None, 'sigma_sell': None, 'sigma_z': None,
    }
    if df is None or getattr(df, 'empty', True) or 'Close' not in getattr(df, 'columns', []):
        _r['error'] = '無 K 線資料'
        return _r

    from src.compute.etf.etf_calc import (
        calc_avg_yield, calc_cagr, calc_current_yield, calc_liquidity_score,
        calc_mdd, calc_premium_discount, calc_sharpe, calc_total_return_1y,
    )
    from src.compute.etf.etf_helpers import dividend_health_label, yield_valuation_zone

    _r['name'] = (zh_name or info.get('shortName') or info.get('longName') or ticker)[:30]
    _r['price'] = round(float(df['Close'].iloc[-1]), 2)
    try:
        from src.compute.etf.etf_smart_analysis import compute_std_bands
        _sb = compute_std_bands(df['Close'], window=252)
        if _sb.get('has_data'):
            _r['sigma_buy'] = round(float(_sb['lower_2s']), 2)   # -2σ 強買
            _r['sigma_sell'] = round(float(_sb['upper_2s']), 2)  # +2σ 減碼
            _r['sigma_z'] = round(float(_sb['sigma_z']), 2)
    except Exception as _e_sb:
        print(f'[build_etf_score_row] {ticker} σ 帶計算失敗:{type(_e_sb).__name__}: {_e_sb}')
    _r['total_ret_1y'] = calc_total_return_1y(df, divs, require_full_period=True)
    _r['div_yield'] = calc_current_yield(df, divs)
    _r['cagr_3y'] = calc_cagr(df, expected_years=3)
    _r['sharpe'] = calc_sharpe(df)
    _r['mdd'] = calc_mdd(df)
    _r['expense_ratio'] = info.get('annualReportExpenseRatio')
    _r['aum'] = info.get('totalAssets')
    _r['beta'] = info.get('beta') or info.get('beta3Year')
    try:
        _pd_res = calc_premium_discount(info, df, ticker)
        _r['premium_pct'] = _pd_res.get('premium_pct')
        _r['stale_nav'] = bool(_pd_res.get('stale_nav'))
    except Exception as _e_pd:
        print(f'[build_etf_score_row] {ticker} 折溢價失敗:{type(_e_pd).__name__}: {_e_pd}')
    try:
        _r['avg_yield_5y'] = calc_avg_yield(df, divs, years=5, require_full_years=True)
    except Exception as _e_ay:
        print(f'[build_etf_score_row] {ticker} 5y 均殖失敗:{type(_e_ay).__name__}: {_e_ay}')
    _r['valuation_zone'] = yield_valuation_zone(_r['div_yield'], _r['avg_yield_5y'])
    _r['dividend_health'] = dividend_health_label(
        _r['div_yield'], _r['total_ret_1y'], _r['cagr_3y'])
    try:
        _liq = calc_liquidity_score(df, _r['aum'])
        _r['liquidity_level'] = _liq.get('level', '⚪')
        _r['liquidity_avg_vol_20d'] = _liq.get('avg_vol_20d')
        _r['liquidity_reasons'] = _liq.get('reasons', [])
    except Exception as _e_liq:
        print(f'[build_etf_score_row] {ticker} 流動性失敗:{type(_e_liq).__name__}: {_e_liq}')
    return _r


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
