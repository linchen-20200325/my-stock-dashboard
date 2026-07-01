"""tests/test_picker_check_one_stock.py — v18.452 智慧選股 Stage 1/2 全 N/A 真回歸修。

production bug(user 截圖「個股組合」Tab「🎯 三階段濾網」):不論輸入哪支股票,
Stage 1 基本面表(9 項)與 Stage 2 籌碼技術表(6 項)全部顯示 ❓N/A、S1/S2 通過數
恆為 0/9、0/6。

根因:`_check_one_stock` 呼叫 `_check_dividend_5y(_df, _t_yf)`,但 `_t_yf` 從未
被賦值(v18.374 P1-1a 把 K 線抓取抽到 L1 fetcher 時,原本建構 yfinance.Ticker
物件的那行被漏改)。每一檔股票跑到這行都 100% `NameError`,ThreadPoolExecutor
的 `except Exception` 接住後整檔回退成 `_blank_pick_result`(全 ❓N/A、pass_cnt=0),
且無 traceback 曝光在 UI(只印到 stderr log,使用者只看到「全部都 N/A」)。

修法:`fetch_stock_history_1y` 改回傳 `(df, resolved_ticker)`,`_check_one_stock`
用 `resolved_ticker` 建構真正的 `yfinance.Ticker(...)` 取代未定義的 `_t_yf`。

本測試不觸網:mock `fetch_stock_history_1y` 回傳固定 K 線 + mock `yfinance.Ticker`
回傳固定配息 Series,驗證 `_check_one_stock` 執行完整流程不再半路 NameError。
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest


def _fake_ohlcv(n: int = 90) -> pd.DataFrame:
    """近似 yfinance history() 回傳形狀:DatetimeIndex + Close/High/Low/Open/Volume。"""
    idx = pd.date_range(end=datetime.date.today(), periods=n, freq='D')
    close = pd.Series([100.0 + i * 0.3 for i in range(n)], index=idx)
    return pd.DataFrame({
        'Open': close - 0.5, 'High': close + 1.0, 'Low': close - 1.0,
        'Close': close, 'Volume': [1_000_000] * n,
    }, index=idx)


class _FakeTicker:
    """假 yfinance.Ticker — 只需 `.dividends` 供 _check_dividend_5y 使用。"""
    def __init__(self, symbol):
        self.symbol = symbol
        now = pd.Timestamp(datetime.date.today())
        # 5 年,每年 1 次配息,足以通過 `len(_divs) < 5` 門檻
        self.dividends = pd.Series(
            [2.0, 2.0, 2.0, 2.0, 2.0],
            index=pd.DatetimeIndex([now - pd.Timedelta(days=365 * y + 30) for y in range(5)]),
        )


@pytest.fixture(autouse=True)
def _patch_network(monkeypatch):
    """全面隔離網路 I/O:K 線走假資料;yfinance.Ticker 走假配息;其餘 FinMind 直呼
    (財報/合約負債/法人/大戶)全部 mock 掉,保持測試快速且不依賴外部網路可達性。
    這些函式本身各自已有 try/except 安全回退(§1),mock 只是避免真打 API 拖慢測試,
    不影響本測試要驗證的核心邏輯(_t_yf 修復 + Stage 1/2 是否整體跑完)。"""
    import src.data.stock.picker_fetcher as _pf
    import src.ui.tabs.tab_stock_picker as _tsp
    import yfinance as _yf

    monkeypatch.setattr(_pf, 'fetch_stock_history_1y',
                        lambda ticker: (_fake_ohlcv(), f'{ticker}.TW'))
    monkeypatch.setattr(_yf, 'Ticker', _FakeTicker)
    monkeypatch.setattr(_tsp, '_fetch_fs_safe', lambda ticker: {})
    monkeypatch.setattr(_tsp, '_fetch_quarterly_is', lambda ticker: {})
    monkeypatch.setattr(_tsp, '_check_contract_liab_yoy', lambda ticker: '❓ mocked')
    monkeypatch.setattr(_tsp, '_check_institutional_buying', lambda ticker: '❓ mocked')
    monkeypatch.setattr(_tsp, '_check_major_holders', lambda ticker: '❓ mocked')


def test_check_one_stock_does_not_crash_on_t_yf():
    """核心回歸:_check_one_stock 對任意股票代碼跑完不炸(舊碼在此必 100% NameError)。"""
    from src.ui.tabs.tab_stock_picker import _check_one_stock
    result = _check_one_stock('2330', datetime.date.today())
    assert result is not None


def test_stage1_dividend_check_actually_runs_not_blank():
    """div_5y_label 應反映真實配息計算結果,而非崩潰後的空白骨架 '❓ N/A'。"""
    from src.ui.tabs.tab_stock_picker import _check_one_stock
    result = _check_one_stock('2330', datetime.date.today())
    assert result['div_5y_label'] != '❓ N/A', (
        f"div_5y_label 仍是崩潰骨架預設值,_t_yf NameError 回歸:{result}"
    )
    # 5 年配息 2.0/年,現價 ~113 → 殖利率 ~1.8%,應判為 ❌(未達 YIELD_HIGH 門檻)而非 ❓
    assert result['div_5y_label'].startswith(('✅', '❌'))


def test_stage2_technical_checks_populate_from_real_df():
    """Stage 2 純技術指標(僅需 K 線,不靠外部網路)應產生真實判定,不是全 N/A 骨架。
    間接證明 _check_one_stock 執行到 Stage 2 區塊(未在 Stage 1 中途因例外提前 return)。
    """
    from src.ui.tabs.tab_stock_picker import _check_one_stock
    result = _check_one_stock('2330', datetime.date.today())
    assert result['ma20_label'] != '❓ N/A'
    assert result['macd_label'] != '❓ N/A'
    assert result['kd_label'] != '❓ N/A'
    assert result['boll_label'] != '❓ N/A'


def test_resolved_ticker_used_for_dividend_ticker_not_bare_code():
    """fetch_stock_history_1y 回傳的 resolved_ticker(含 .TW/.TWO 後綴)須真正被拿去
    建構 yfinance.Ticker,而非用原始無後綴代碼(否則配息查詢會用錯代號)。"""
    import src.ui.tabs.tab_stock_picker as _tsp
    _seen = {}
    class _RecordingTicker(_FakeTicker):
        def __init__(self, symbol):
            super().__init__(symbol)
            _seen['symbol'] = symbol
    import yfinance as _yf
    _orig = _yf.Ticker
    _yf.Ticker = _RecordingTicker
    try:
        _tsp._check_one_stock('2330', datetime.date.today())
    finally:
        _yf.Ticker = _orig
    assert _seen.get('symbol') == '2330.TW', _seen


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
