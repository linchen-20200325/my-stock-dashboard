"""src/compute/notify/technical_snapshot.py — 每日推播「純價格衍生技術面」快照(L2 純函式)。

吃一檔的 OHLCV 價格 df(`fetch_stock_history_1y` 輸出;yfinance 大寫欄名)→ 回技術面
dict:MA5/20/60、多頭排列、距 MA20 乖離%、RSI、KD、MACD 柱。

**全部複用既有 L2 kernel**(§3.3 反捏造,不新增第二套演算法):
  - MA:`calc_ma_series`(tech_indicators)
  - RSI:`calc_rsi`(tech_indicators → 委派 scoring_engine.compute_rsi)
  - KD:`calc_kd`(tech_indicators)
  - MACD:`compute_macd`(exit_signals,B6 SSOT kernel)

§1 fail-loud:資料不足 → 對應欄回 None(**不腦補**);整段無價格 → {ok: False, note}。
§8.2 L2:無 I/O、無 streamlit、無 session_state。
"""
from __future__ import annotations

import pandas as pd

from src.compute.scoring.exit_signals import compute_macd
from src.compute.strategy.tech_indicators import calc_kd, calc_ma_series, calc_rsi


def build_technical_snapshot(price_df) -> dict:
    """OHLCV 價格 df → 技術面快照 dict。

    Args:
        price_df: 含收盤價的 DataFrame(欄名大小寫不拘;至少要有 close/收盤)。
                  通常為 `fetch_stock_history_1y` 的輸出(yfinance:Open/High/Low/Close/Volume)。

    Returns:
        {ok, price, ma5, ma20, ma60, ma_bull, bias20_pct, rsi, k, d, kd_gold, macd_hist}。
        資料不足的欄 → None(不臆造);整段無價格 → {ok: False, note}。
    """
    if price_df is None or getattr(price_df, "empty", True):
        return {"ok": False, "note": "無價格資料"}
    # 正規化欄名(yfinance Close→close),讓吃小寫的 L2 kernel 直接可用
    df = price_df.rename(columns=str.lower)
    if "close" not in df.columns:
        return {"ok": False, "note": "價格欄缺 close"}
    close = df["close"].astype(float)
    if close.dropna().empty:
        return {"ok": False, "note": "close 全空"}
    price = float(close.iloc[-1])

    def _ma(n: int):
        if len(close) < n:
            return None
        _v = calc_ma_series(close, window=n).iloc[-1]
        return round(float(_v), 2) if pd.notna(_v) else None

    ma5, ma20, ma60 = _ma(5), _ma(20), _ma(60)
    # 多頭排列:price > ma5 > ma20 > ma60(任一缺 → None,不臆造)
    ma_bull = bool(price > ma5 > ma20 > ma60) if None not in (ma5, ma20, ma60) else None
    # 距 MA20 乖離%(§4.1:比率×100 = %)
    bias20 = round((price / ma20 - 1) * 100, 2) if ma20 else None

    rsi = calc_rsi(df)                      # kernel 吃小寫 df['close'] ✓
    k = d = kd_gold = None
    if {"high", "low"}.issubset(df.columns):   # calc_kd 需 high/low,缺則不算(不臆造)
        k, d = calc_kd(df)
        if k is not None and d is not None:
            kd_gold = bool(k > d)           # K 在 D 上 = 偏多

    macd_hist = None
    try:
        _, _, _hist = compute_macd(close)   # (dif, dea, hist)
        _h = _hist.iloc[-1]
        macd_hist = round(float(_h), 3) if pd.notna(_h) else None
    except Exception:                        # noqa: BLE001 — 樣本不足 → None,不炸
        macd_hist = None

    return {
        "ok": True,
        "price": round(price, 2),
        "ma5": ma5, "ma20": ma20, "ma60": ma60,
        "ma_bull": ma_bull,
        "bias20_pct": bias20,
        "rsi": rsi,
        "k": k, "d": d, "kd_gold": kd_gold,
        "macd_hist": macd_hist,
    }
