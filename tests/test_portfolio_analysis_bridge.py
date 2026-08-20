"""組合管理持股 → ETF 組合分析 rows 橋接測試(v19.202)。

驗:契約欄位、§1 跳過無效列(觀察清單候選/缺張數均價)、單位(1張=1000股)、ticker 正規化。
"""
from __future__ import annotations

import math

from src.compute.etf.etf_helpers import auto_role, normalize_etf_ticker
from src.services.portfolio_analysis_bridge import (
    PortfolioRowsResult,
    build_portfolio_rows_from_holdings,
)


def _h(ticker, *, held=True, lots=None, avg_price=None):
    return {'ticker': ticker, 'held': held, 'lots': lots, 'avg_price': avg_price}


def test_valid_holding_produces_contract_row():
    res = build_portfolio_rows_from_holdings([_h('0050', lots=3, avg_price=100.0)])
    assert isinstance(res, PortfolioRowsResult)
    assert len(res.rows) == 1
    r = res.rows[0]
    assert r['ticker'] == normalize_etf_ticker('0050') == '0050.TW'
    assert r['lots'] == 3.0
    assert r['shares'] == 3000.0                 # 1 張 = 1000 股
    assert r['avg_price'] == 100.0
    assert math.isclose(r['cost'], 300000.0)     # shares × avg_price
    assert r['role'] == auto_role('0050.TW')
    assert r['target_pct_user'] is None and r['target_pct'] is None
    # 契約欄位齊全(與 render_etf_portfolio 寫入 etf_portfolio_rows 一致)
    assert set(r) == {'ticker', 'lots', 'shares', 'avg_price', 'cost',
                      'target_pct_user', 'target_pct', 'role'}


def test_watchlist_candidate_excluded():
    """held=False(觀察清單候選,非持有)→ 跳過,不進組合分析。"""
    res = build_portfolio_rows_from_holdings([_h('2330', held=False, lots=1, avg_price=900.0)])
    assert res.rows == ()
    assert res.skipped and res.skipped[0]['ticker'] == '2330.TW'


def test_missing_lots_or_price_skipped_not_fabricated():
    """§1:缺張數/均價 → 跳過,不腦補成本。"""
    for h in (_h('0056', lots=None, avg_price=30.0),
              _h('0056', lots=5, avg_price=None),
              _h('0056', lots=0, avg_price=30.0),
              _h('0056', lots=5, avg_price=0),
              _h('0056', lots=float('nan'), avg_price=30.0)):
        res = build_portfolio_rows_from_holdings([h])
        assert res.rows == ()
        assert res.skipped


def test_empty_and_garbage_inputs():
    assert build_portfolio_rows_from_holdings(None).rows == ()
    assert build_portfolio_rows_from_holdings([]).rows == ()
    assert build_portfolio_rows_from_holdings(['x', 5, None]).rows == ()


def test_blank_ticker_skipped():
    res = build_portfolio_rows_from_holdings([_h('', lots=1, avg_price=10.0)])
    assert res.rows == ()
    assert res.skipped and '代號' in res.skipped[0]['reason']


def test_mixed_batch_partitions_correctly():
    res = build_portfolio_rows_from_holdings([
        _h('0050', lots=2, avg_price=150.0),       # ok
        _h('00878', held=False, lots=1, avg_price=20.0),  # watchlist → skip
        _h('2330', lots=1, avg_price=900.0),       # ok
        _h('9999', lots=None, avg_price=None),     # missing → skip
    ])
    assert {r['ticker'] for r in res.rows} == {'0050.TW', '2330.TW'}
    assert len(res.skipped) == 2
