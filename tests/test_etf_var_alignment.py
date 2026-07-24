"""tests/test_etf_var_alignment.py — v19.165 守衛:ETF 組合 VaR 誠實對齊(§1)。

根因:舊 VaR 用 `reindex(union).ffill().fillna(0)`,新上市 ETF 上市前被當成 0% 報酬 →
稀釋波動、低估尾部 VaR(風險看起來比實際小)。修法 `align_portfolio_returns` 改「共同
交易日交集(dropna how='any')」+ 權重重新正規化,絕不補值。本測試釘死此誠實行為。
"""
from __future__ import annotations

import numpy as np
import pytest

pd = pytest.importorskip("pandas")

from src.compute.etf.etf_calc import align_portfolio_returns


def _series(vals, start='2024-01-01'):
    idx = pd.date_range(start, periods=len(vals), freq='D')
    return pd.Series([float(v) for v in vals], index=idx)


def test_common_days_only_no_zero_fill():
    """新上市 B(D6 才有資料)→ 只算共同日 D6..D10,不把 D1..D5 補 0。"""
    A = _series([0.01, 0.02, -0.01, 0.00, 0.03, 0.01, -0.02, 0.01, 0.00, 0.02])  # D1..D10
    B = _series([0.05, -0.03, 0.02, 0.01, -0.01], start='2024-01-06')            # D6..D10
    out = align_portfolio_returns({'A': A, 'B': B}, {'A': 60, 'B': 40})
    pr = out['port_ret']
    assert out['n_union'] == 10 and out['n_common'] == 5 and out['dropped'] == 5
    assert out['limiter'] == 'B'
    assert str(out['limiter_start'].date()) == '2024-01-06'
    assert len(pr) == 5 and str(pr.index.min().date()) == '2024-01-06'
    assert not pr.isna().any()
    # 手算共同日加權(0.6A+0.4B),證明沒補 0、沒 ffill
    expected = 0.6 * A.loc[pr.index] + 0.4 * B.loc[pr.index]
    assert np.allclose(pr.values, expected.values)


def test_missing_ticker_weight_renormalized():
    """權重含無資料的 C → 只用 A/B 並重新正規化到 sum=1(分母不含 C)。"""
    A = _series([0.01, 0.02, 0.03])
    B = _series([0.00, 0.01, -0.01])
    out = align_portfolio_returns({'A': A, 'B': B}, {'A': 30, 'B': 10, 'C': 999})
    expected = 0.75 * A + 0.25 * B          # 30/(30+10)=0.75
    assert np.allclose(out['port_ret'].values, expected.values)
    assert 'C' not in out['tickers_used']


def test_no_zero_injection_single_common_day():
    """只有一天共同交易日 → port_ret 只該有那一天,不得出現舊法補 0 的假報酬日。"""
    A = _series([0.02, -0.02, 0.03])                 # D1..D3
    B = _series([0.05], start='2024-01-03')          # 只有 D3
    out = align_portfolio_returns({'A': A, 'B': B}, {'A': 50, 'B': 50})
    pr = out['port_ret']
    assert len(pr) == 1 and str(pr.index[0].date()) == '2024-01-03'


def test_empty_and_degenerate_no_crash():
    """空輸入 / 全零權重 → 空 Series,不炸不腦補。"""
    assert align_portfolio_returns({}, {})['n_common'] == 0
    assert align_portfolio_returns({}, {'A': 1})['port_ret'].empty
    A = _series([0.01, 0.02])
    assert align_portfolio_returns({'A': A}, {'A': 0})['port_ret'].empty


def test_contract_keys():
    A = _series([0.01, 0.02, 0.03])
    out = align_portfolio_returns({'A': A}, {'A': 100})
    for k in ('port_ret', 'n_union', 'n_common', 'dropped',
              'limiter', 'limiter_start', 'tickers_used'):
        assert k in out
