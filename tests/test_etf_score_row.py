"""tests/test_etf_score_row.py — v19.166 守衛:build_etf_score_row(單檔/多檔共用 row SSOT)。

§8.1:純計算、自身零 I/O,I/O 依賴(品質/追蹤誤差)由 caller 注入 → 單檔頁可直接餵
render 已抓的 df/divs/info,不重抓。回傳欄位須與原多檔 _fetch_one_etf 對齊。
"""
from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")

from src.compute.etf.etf_scoring_helpers import (
    build_etf_score_row,
    compute_etf_composite_score,
)

_KEYS = ('ticker', 'name', 'error', 'price', 'total_ret_1y', 'cagr_3y', 'sharpe',
         'mdd', 'expense_ratio', 'aum', 'div_yield', 'beta', 'quality',
         'premium_pct', 'stale_nav', 'avg_yield_5y', 'valuation_zone',
         'dividend_health', 'liquidity_level', 'liquidity_avg_vol_20d',
         'liquidity_reasons', 'tracking_error', 'sigma_buy', 'sigma_sell', 'sigma_z')

_NO_DIV = pd.Series(dtype='float64')   # 無配息 → 空 Series(§1 不腦補)


def _mk_df(n=300, start=100.0):
    idx = pd.date_range('2021-01-01', periods=n, freq='D')
    close = pd.Series([start * (1 + 0.0003 * i) for i in range(n)], index=idx)
    return pd.DataFrame({'Open': close, 'High': close * 1.01, 'Low': close * 0.99,
                         'Close': close, 'Volume': [1_000_000] * n}, index=idx)


def test_error_path_full_schema_and_injection():
    """無 df → error 列,但完整 schema + 注入的 quality/tracking_error 仍帶回(不腦補)。"""
    r = build_etf_score_row('X', None, None, None,
                            quality={'q': 1}, tracking_error=0.5)
    assert r['error'] == '無 K 線資料'
    assert r['quality'] == {'q': 1} and r['tracking_error'] == 0.5
    assert r['price'] is None
    for k in _KEYS:
        assert k in r, f'缺欄 {k}(與 _fetch_one_etf schema 不齊)'


def test_happy_path_computes_price_and_schema():
    df = _mk_df()
    r = build_etf_score_row('0050.TW', df, _NO_DIV,
                            {'totalAssets': 5e10, 'annualReportExpenseRatio': 0.0032,
                             'beta': 0.9, 'shortName': 'ETF-X'},
                            quality={'q': 1}, tracking_error=0.5, zh_name='元大台灣50')
    assert r['error'] is None
    assert isinstance(r['price'], float) and r['price'] > 0
    assert r['name'] == '元大台灣50'          # zh_name 優先
    assert r['aum'] == 5e10 and r['beta'] == 0.9
    assert r['tracking_error'] == 0.5
    for k in _KEYS:
        assert k in r
    comp, stars = compute_etf_composite_score(r)   # 吃這個 row 不炸
    assert comp is None or (0.0 <= comp <= 1.0)


def test_name_fallback_chain():
    df = _mk_df(60)
    assert build_etf_score_row('0056', df, _NO_DIV, {'longName': 'Long'})['name'] == 'Long'
    assert build_etf_score_row('0056', df, _NO_DIV, {})['name'] == '0056'  # 退回 ticker
