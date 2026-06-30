"""src/data/stock/picker_fetcher.py — 智慧選股 K 線 fetcher(L1 Data)。

P1-1a v18.374 深層拔毒:從 src/ui/tabs/tab_stock_picker.py:283(L5 UI 違憲)
抽出 yfinance.Ticker.history 直呼。

職責:
- fetch_stock_history_1y(ticker):個股 1y K 線(.TW + .TWO 雙後綴 fallback)
"""
from __future__ import annotations


def fetch_stock_history_1y(ticker: str):
    """個股 1 年 K 線 fallback。

    .TW(上市)→ .TWO(上櫃)雙後綴重試;任一回 >= 60 筆即視為有效,回 DataFrame。
    全部失敗回 None。線程安全(獨立 yfinance call,無共享 state)。

    S-PROV-1 phase 19+:成功回 DataFrame 時注入 attrs(source/fetched_at);
    上游 yfinance 不提供 provenance,attrs 是唯一 schema-additive 落地點。
    """
    import yfinance as yf
    import pandas as _pd
    for _sfx in ('.TW', '.TWO'):
        try:
            df = yf.Ticker(f'{ticker}{_sfx}').history(period='1y')
            if df is not None and not df.empty and len(df) >= 60:
                try:
                    df.attrs.setdefault('source', f'yfinance:Ticker({ticker}{_sfx}).history(1y)')
                    df.attrs.setdefault('fetched_at', _pd.Timestamp.now('UTC').isoformat())
                except Exception:
                    pass
                return df
        except Exception:
            continue
    return None
