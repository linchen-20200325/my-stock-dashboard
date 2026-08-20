"""P3-A(v19.199)對稱性稽核第三輪:§1 beta 捏造帶旗標 + warroom 年輕 ETF 假🟢修正。"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd


# ── Fix A:壓力測試 beta 缺失以 1.0 估算須帶 is_imputed 旗標(§1/§3.1)──────────
@patch('src.compute.etf.etf_calc.fetch_etf_info')
def test_stress_test_flags_imputed_beta(mock_info):
    from src.compute.etf import calc_portfolio_stress_test
    mock_info.side_effect = lambda t: {'beta': 0.8} if t == '0056' else {}   # 9999 查無 beta
    rows = [{'ticker': '0056', 'actual_pct': 50}, {'ticker': '9999', 'actual_pct': 50}]
    r = calc_portfolio_stress_test(rows, total_value=1_000_000)
    assert r['beta_imputed_count'] == 1
    assert r['beta_imputed_tickers'] == ['9999']
    _flags = {e['ETF']: e['_beta_imputed'] for e in r['per_etf']}
    assert _flags == {'0056': False, '9999': True}   # 真實 vs 估算 分得開


@patch('src.compute.etf.etf_calc.fetch_etf_info')
def test_stress_test_all_real_beta_zero_imputed(mock_info):
    from src.compute.etf import calc_portfolio_stress_test
    mock_info.return_value = {'beta': 1.1}
    r = calc_portfolio_stress_test([{'ticker': '0050', 'actual_pct': 100}], total_value=1_000_000)
    assert r['beta_imputed_count'] == 0 and r['beta_imputed_tickers'] == []


# ── Fix B:warroom 年輕 ETF(未滿 1 年)→ 報酬 None → 資料不足,不假🟢綠燈 ────────
@patch('src.compute.etf.etf_calc._get_etf_launch_price', return_value=None)
@patch('src.compute.etf.etf_calc.calc_premium_discount', return_value={'premium_pct': None})
@patch('src.compute.etf.etf_calc.fetch_etf_info', return_value={})
@patch('src.compute.etf.etf_calc.fetch_etf_dividends')
@patch('src.compute.etf.etf_calc.fetch_etf_price')
def test_warroom_young_etf_data_insufficient(mock_price, mock_divs, *_):
    from src.compute.etf.etf_calc import _compute_etf_warroom_row
    idx = pd.bdate_range('2025-01-02', periods=120)          # ~168 日曆天 < 1 年
    mock_price.return_value = pd.DataFrame(
        {'Close': [100 + i * 0.5 for i in range(len(idx))]}, index=idx)
    mock_divs.return_value = pd.Series([2.0], index=pd.to_datetime(['2025-03-01']))
    row = _compute_etf_warroom_row('00981A', '年輕ETF', '核心')
    assert row['1年含息報酬%'] is None            # require_full_period=True → None
    assert '資料不足' in row['健康燈號']           # 不再假🟢體質健康
    assert '🟢' not in row['健康燈號']


@patch('src.compute.etf.etf_calc._get_etf_launch_price', return_value=None)
@patch('src.compute.etf.etf_calc.calc_premium_discount', return_value={'premium_pct': None})
@patch('src.compute.etf.etf_calc.fetch_etf_info', return_value={})
@patch('src.compute.etf.etf_calc.fetch_etf_dividends')
@patch('src.compute.etf.etf_calc.fetch_etf_price')
def test_warroom_mature_etf_still_verdicts(mock_price, mock_divs, *_):
    """滿 1 年 ETF 仍正常給燈(確認 None 守衛不誤傷正常檔)。"""
    from src.compute.etf.etf_calc import _compute_etf_warroom_row
    idx = pd.bdate_range('2023-01-02', periods=400)          # > 1 年
    mock_price.return_value = pd.DataFrame(
        {'Close': [100 + i * 0.1 for i in range(len(idx))]}, index=idx)
    mock_divs.return_value = pd.Series([3.0], index=pd.to_datetime(['2024-07-01']))
    row = _compute_etf_warroom_row('0056', '高股息', '核心')
    assert row['1年含息報酬%'] is not None
    assert '資料不足' not in row['健康燈號']
