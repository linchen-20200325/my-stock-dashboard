"""
test_market_strategy.py — market_strategy step 3c 遷移驗證

驗證重點:
1. fetch_market_data 完全委派給 tw_macro.fetch_finmind_foreign_investor
   (即不再直連 TWSE BFI82U,所有抓取走 NAS proxy)。
2. get_market_assessment 在 df_index=None 時 fallback 走 macro_core.fetch_yf_ohlcv
   (即不再依賴 yfinance.Ticker)。
3. 結構性檢查: market_strategy 原始碼不應 import requests/yfinance。
"""
from __future__ import annotations

import pandas as pd

from src.services import market_strategy


# ══════════════════════════════════════════════════════════════
# fetch_market_data 委派驗證
# ══════════════════════════════════════════════════════════════

def test_fetch_market_data_delegates_to_tw_macro(monkeypatch):
    captured = {}

    def fake_finmind(days_back=7):
        captured['days_back'] = days_back
        return {
            'fii_net': -3_500_000_000,
            'z_fii':   -0.7,
            'date':    '2026-05-05',
            'error':   None,
        }

    # 注意: market_strategy.fetch_market_data 內 import tw_macro,
    # 因此必須 patch tw_macro module 的函式
    from src.data.macro import tw_macro
    monkeypatch.setattr(tw_macro, 'fetch_finmind_foreign_investor', fake_finmind)

    out = market_strategy.fetch_market_data()
    assert captured['days_back']    == 7
    assert out['foreign_net']       == -3_500_000_000.0
    assert out['date']              == '20260505'   # 'YYYY-MM-DD' → 'YYYYMMDD'


def test_fetch_market_data_handles_finmind_error(monkeypatch):
    from src.data.macro import tw_macro
    monkeypatch.setattr(tw_macro, 'fetch_finmind_foreign_investor',
                        lambda days_back=7: {'fii_net': None, 'error': 'mocked'})

    out = market_strategy.fetch_market_data()
    assert out == {'foreign_net': None, 'date': ''}


def test_fetch_market_data_handles_no_fii(monkeypatch):
    from src.data.macro import tw_macro
    monkeypatch.setattr(tw_macro, 'fetch_finmind_foreign_investor',
                        lambda days_back=7: {'fii_net': None, 'error': None})

    out = market_strategy.fetch_market_data()
    assert out['foreign_net'] is None


# ══════════════════════════════════════════════════════════════
# get_market_assessment fallback 走 macro_core.fetch_yf_ohlcv
# ══════════════════════════════════════════════════════════════

def _build_synthetic_twii_df(rows: int = 200) -> pd.DataFrame:
    """生出 200 個交易日的合成 ^TWII 資料,確保 MA120 計算到位。

    末筆錨定「今天」(end=now),避免硬編起始日隨時間推移觸發
    market_strategy 的 `_days_old > 7` 過舊保護 → 測試隨日曆 rot。
    """
    idx = pd.date_range(end=pd.Timestamp.now().normalize(), periods=rows, freq='B')
    closes = [20000 + i * 5 for i in range(rows)]
    return pd.DataFrame({
        'Open':   [c - 10 for c in closes],
        'High':   [c + 20 for c in closes],
        'Low':    [c - 20 for c in closes],
        'Close':  closes,
        'Volume': [1_500_000_000 + i * 1000 for i in range(rows)],
    }, index=idx)


def test_get_market_assessment_fallback_via_macro_core(monkeypatch):
    captured = {}

    def fake_ohlcv(ticker, range_='9mo', interval='1d'):
        captured['ticker']   = ticker
        captured['range_']   = range_
        captured['interval'] = interval
        return _build_synthetic_twii_df()

    # market_strategy.get_market_assessment 內以 from src.data.macro import fetch_yf_ohlcv
    # 形式取用,需 patch 在 macro_core 上
    from src.data.macro import macro_core
    monkeypatch.setattr(macro_core, 'fetch_yf_ohlcv', fake_ohlcv)

    res = market_strategy.get_market_assessment(
        df_index=None, foreign_net=1_000_000_000,
        m1b_m2_gap=0.5, m1b_m2_prev=0.3,
    )

    assert captured['ticker']   == '^TWII'
    assert captured['range_']   == '9mo'
    assert captured['interval'] == '1d'
    assert res is not None
    assert 'regime' in res and 'index_price' in res
    # 合成資料尾巴遠高過 MA120,應為 bull
    assert res['regime'] == 'bull'


def test_get_market_assessment_fallback_returns_none_on_empty(monkeypatch):
    from src.data.macro import macro_core
    monkeypatch.setattr(macro_core, 'fetch_yf_ohlcv',
                        lambda *a, **kw: pd.DataFrame())

    res = market_strategy.get_market_assessment(df_index=None, foreign_net=0)
    assert res is None


# ══════════════════════════════════════════════════════════════
# 結構性檢查 — 防止有人未來偷加直連
# ══════════════════════════════════════════════════════════════

def test_no_direct_requests_or_yfinance_import():
    """讀原始碼確認沒有直接 import requests 或 yfinance(註解/docstring 不算)。"""
    import re
    src = open(market_strategy.__file__).read()
    pattern = re.compile(r'^\s*(?:import|from)\s+(requests|yfinance)\b', re.MULTILINE)
    matches = pattern.findall(src)
    assert not matches, f'market_strategy 不應 import {matches}'
