"""src/data/stock/picker_fetcher.py — 智慧選股 K 線 fetcher(L1 Data)。

P1-1a v18.374 深層拔毒:從 src/ui/tabs/tab_stock_picker.py:283(L5 UI 違憲)
抽出 yfinance.Ticker.history 直呼。

職責:
- fetch_stock_history_1y(ticker):個股 1y K 線(Yahoo .TW/.TWO 雙後綴 → FinMind 備援)
"""
from __future__ import annotations


def _finmind_raw_to_close_df(raw):
    """FinMind TaiwanStockPrice 原始 df(date/open/max/min/close/Trading_Volume)→
    標準 K 線 df(DatetimeIndex + Close[/Open/High/Low/Volume])。純函式(可離線測)。

    空 / 缺 close 欄 / date 全壞 → 回空 DataFrame(§1 不回假資料)。
    建議#2 v19.144:Yahoo 全敗時的第二來源,單位對齊 yfinance(close→Close)。
    """
    import pandas as _pd

    if raw is None or not hasattr(raw, "empty") or raw.empty or "close" not in raw.columns:
        return _pd.DataFrame()
    _d = raw.copy()
    _d["date"] = _pd.to_datetime(_d.get("date"), errors="coerce")
    _d = _d.dropna(subset=["date"]).sort_values("date").set_index("date")
    if _d.empty:
        return _pd.DataFrame()
    _out = _pd.DataFrame(index=_d.index)
    _out["Close"] = _pd.to_numeric(_d["close"], errors="coerce")
    for _src, _dst in (("open", "Open"), ("max", "High"),
                       ("min", "Low"), ("Trading_Volume", "Volume")):
        if _src in _d.columns:
            _out[_dst] = _pd.to_numeric(_d[_src], errors="coerce")
    return _out.dropna(subset=["Close"])


def fetch_stock_history_1y(ticker: str):
    """個股 1 年 K 線 fallback。

    .TW(上市)→ .TWO(上櫃)雙後綴重試;任一回 >= 60 筆即視為有效,回 (df, resolved_ticker)。
    resolved_ticker 為成功命中的完整代號(如 "6239.TW"),供呼叫端重用同一檔
    (如另建 yfinance.Ticker 查配息)而不必重跑一次雙後綴 fallback。
    全部失敗回 (None, None)。線程安全(獨立 yfinance call,無共享 state)。

    S-PROV-1 phase 19+:成功回 DataFrame 時注入 attrs(source/fetched_at);
    上游 yfinance 不提供 provenance,attrs 是唯一 schema-additive 落地點。
    """
    import pandas as _pd
    # v19.105(第九份 1-A):原裸 yf.Ticker().history() 無代理無快取 — 雲端易被
    # Yahoo 擋 IP、選股批次重複抓。改走 yf_proxy.cached_history(NAS proxy +
    # 1h cache,抓不到回空 df 不爆例外),回傳契約(df, resolved)不變。
    from src.data.proxy.yf_proxy import cached_history as _yf_hist
    for _sfx in ('.TW', '.TWO'):
        try:
            _resolved = f'{ticker}{_sfx}'
            df = _yf_hist(_resolved, period='1y')
            if df is not None and not df.empty and len(df) >= 60:
                try:
                    df.attrs.setdefault('source', f'yf_proxy.cached_history({_resolved},1y)')
                    df.attrs.setdefault('fetched_at', _pd.Timestamp.now('UTC').isoformat())
                except Exception:
                    pass
                return df, _resolved
        except Exception:
            continue

    # 建議#2 v19.144:Yahoo .TW/.TWO 全敗 → FinMind TaiwanStockPrice 第二來源備援。
    # 補「價格全靠 Yahoo」單點風險:Yahoo 限流/擋 IP 時,RS/技術面降級不瞎(§1 誠實)。
    try:
        import datetime as _dt

        from src.data.core.data_loader import _fetch_finmind_price_raw  # L1→L1 同層
        _end = _dt.date.today()
        _start = _end - _dt.timedelta(days=400)          # 多抓緩衝,確保 ≥ 1y 交易日
        _raw = _fetch_finmind_price_raw(str(ticker), _start.isoformat(), _end.isoformat())
        _fm = _finmind_raw_to_close_df(_raw)
        if not _fm.empty and len(_fm) >= 60:
            try:
                _fm.attrs.setdefault("source", f"FinMind:TaiwanStockPrice:{ticker}(yahoo-fallback)")
                _fm.attrs.setdefault("fetched_at", _pd.Timestamp.now("UTC").isoformat())
            except Exception:
                pass
            return _fm, str(ticker)
    except Exception as _e_fm:
        print(f"[picker_fetcher] FinMind 備援失敗 {ticker}: {type(_e_fm).__name__}: {_e_fm}")
    return None, None
