"""技術指標計算 — 6 個純函式

從 app.py:590-707 抽出（PR P2-B Phase 1）。**零 Streamlit / 零 session state
依賴**，只用 pandas + numpy，可在 CLI / pytest 環境直接 import。

收錄函式
========
- calc_rsi(df, period=14)            — 相對強弱指標
- calc_ibs(df)                       — 內部強度 = (C-L)/(H-L)
- calc_volume_ratio(df, period=5)    — 量比 = 今日量 / N 日均量
- calc_kd(df, period=9)              — KD 隨機指標（EMA 平滑）
- calc_bollinger(df, window=20, mult=2) — 布林通道
- calc_vcp(df, n_swings=3)           — Volatility Contraction Pattern

輸入：pandas.DataFrame，columns 必須含 'close' / 'high' / 'low' / 'volume'
輸出：失敗一律回 None（不丟例外），呼叫端只需檢查 falsy
"""
from __future__ import annotations

import sys

import pandas as pd

# Phase 2 Batch 5d v18.432:布林貼近上軌 LOOSE tier SSOT(原 0.97 inline,calc_bollinger 'near_upper')
from shared.signal_thresholds import BB_NEAR_UPPER_RATIO

# S-MED v18.304: 5 處 silent `except Exception:` 改 narrow + stderr log
# 介面保留(None / (None, None) / dict),caller 不需改


def calc_rsi(df, period=14):
    """RSI scalar adapter — 回傳最新 RSI(0-100,round 1 位)或 None。

    R-CALC-1 v18.412:雙寫收斂 — 數學 kernel 委派 scoring_engine.compute_rsi
    (series API),本函式為 UI scalar 適配器(取 last + round + guard + log)。
    Epsilon 從原本 `loss.replace(0,1e-9)` 改為 compute_rsi 的 `loss + 1e-10`,
    在 round(1) 精度下等價(極端 loss=0 兩者皆映射到 RSI≈100)。
    """
    try:
        if df is None or len(df) < period + 1:
            return None
        from src.compute.scoring.scoring_engine import compute_rsi
        rsi_series = compute_rsi(df['close'], period=period)
        val = rsi_series.iloc[-1]
        return round(float(val), 1) if pd.notna(val) else None
    except Exception as e:
        print(f'[tech_indicators/calc_rsi] period={period} fail: {type(e).__name__}: {e}', file=sys.stderr)
        return None


def calc_ibs(df):
    """IBS = (Close - Low) / (High - Low)  當日收盤在日震幅中的位置"""
    try:
        if df is None or df.empty:
            return None
        row = df.iloc[-1]
        h, l, c = float(row['high']), float(row['low']), float(row['close'])
        if h == l:
            return 0.5
        return round((c - l) / (h - l), 3)
    except Exception as e:
        print(f'[tech_indicators/calc_ibs] fail: {type(e).__name__}: {e}', file=sys.stderr)
        return None


def calc_volume_ratio(df, period=5):
    """量比 = 今日成交量 / 近N日平均成交量"""
    try:
        if df is None or len(df) < period + 1:
            return None
        today_vol = float(df['volume'].iloc[-1])
        avg_vol = float(df['volume'].iloc[-(period+1):-1].mean())
        if avg_vol == 0:
            return None
        return round(today_vol / avg_vol, 2)
    except Exception as e:
        print(f'[tech_indicators/calc_volume_ratio] period={period} fail: {type(e).__name__}: {e}', file=sys.stderr)
        return None


def calc_kd(df, period=9):
    """計算最新一日的 K、D 值"""
    try:
        if df is None or len(df) < period:
            return None, None
        low_n = df['low'].rolling(period).min()
        high_n = df['high'].rolling(period).max()
        rsv = ((df['close'] - low_n) / (high_n - low_n).replace(0, 1)) * 100
        k = rsv.ewm(com=2, adjust=False).mean()
        d = k.ewm(com=2, adjust=False).mean()
        k_val = k.iloc[-1]
        d_val = d.iloc[-1]
        if pd.isna(k_val) or pd.isna(d_val):
            return None, None
        return round(float(k_val), 1), round(float(d_val), 1)
    except Exception as e:
        print(f'[tech_indicators/calc_kd] period={period} fail: {type(e).__name__}: {e}', file=sys.stderr)
        return None, None


def calc_bollinger(df, window=20, mult=2):
    try:
        if df is None or len(df) < window:
            return None
        close = df['close']
        ma = close.rolling(window).mean()
        std = close.rolling(window).std()
        upper = ma + mult * std
        lower = ma - mult * std
        # v19.85(§4.4 大數除小數):ma==0 時 Series 除法回 inf(不 raise,會穿過
        # except 與末值 isna 檢查外流)→ 顯式換 NaN,走下方 isna → return None。
        bw = (upper - lower) / ma.replace(0, float('nan')) * 100
        _u, _l, _m, _bw = upper.iloc[-1], lower.iloc[-1], ma.iloc[-1], bw.iloc[-1]
        if any(pd.isna(v) for v in [_u, _l, _m, _bw]):
            return None
        return {
            'upper': round(float(_u), 2),
            'lower': round(float(_l), 2),
            'ma':    round(float(_m), 2),
            'bw':    round(float(_bw), 2),
            'bw_mean': round(float(bw.mean()), 2),  # v19.74:移除恆真 `'bw' in dir()` dead code
            'price': round(float(df['close'].iloc[-1]), 2),
            'near_upper': float(df['close'].iloc[-1]) >= float(_u) * BB_NEAR_UPPER_RATIO,
        }
    except Exception as e:
        print(f'[tech_indicators/calc_bollinger] window={window} fail: {type(e).__name__}: {e}', file=sys.stderr)
        return None


# ══════════════════════════════════════════════════════════════
# C5 v18.403:series-variant — 供 picker 篩選器類 caller 比較相鄰兩日 / 斜率 /
# 寬度時序使用(現有 calc_kd / calc_bollinger 只回最後一日 scalar,不夠)。
# ══════════════════════════════════════════════════════════════

def calc_ma_series(close: pd.Series, window: int = 20) -> pd.Series:
    """N 日移動平均 series(`close.rolling(window).mean()`)。

    Args:
        close: pd.Series 收盤價(任意 index)
        window: rolling 視窗,預設 20

    Returns:
        pd.Series(MA),與 close 等長(前 N-1 個 NaN)
    """
    return close.rolling(window).mean()


def calc_bollinger_width_series(close: pd.Series, window: int = 20,
                                k: float = 2.0) -> pd.Series:
    """布林通道寬度 series(已用 MA 標準化,單位:倍率)。

    寬度公式 = (upper - lower) / MA = 4·std / MA。
    Picker 用「近 5 日均值 vs 前 20 日均值」判斷開口 / 收斂。

    Args:
        close: pd.Series 收盤價
        window: rolling 視窗,預設 20
        k: σ 倍數,預設 2.0(即 ±2σ)

    Returns:
        pd.Series(width),與 close 等長(前 N-1 個 NaN);MA=0 時對應位置為 inf
    """
    ma = close.rolling(window).mean()
    std = close.rolling(window).std()
    return (4 * k * std / 2 / ma)  # = 2k·std / ma;k=2 → 4·std/ma


def calc_kd_series(close: pd.Series, high: pd.Series, low: pd.Series,
                   period: int = 9) -> tuple[pd.Series, pd.Series]:
    """KD 隨機指標 series(EMA 平滑 com=2),供比較相鄰兩日(黃金/死亡交叉)。

    Args:
        close / high / low: pd.Series(同 index 等長)
        period: RSV 窗口,預設 9

    Returns:
        (k_series, d_series),前 period-1 個 NaN
    """
    low_n = low.rolling(period).min()
    high_n = high.rolling(period).max()
    rsv = ((close - low_n) / (high_n - low_n).replace(0, 1)) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    return k, d


def analyze_kd_state(df, period: int = 9):
    """KD 鈍化(passivation) + 背離(divergence) 偵測（v19.94，§7 user 核准）。

    純 L2:dict-or-None + stderr log（同儕 calc_kd/calc_bollinger 契約，不 raise）。

    鈍化：K 連 `KD_PASSIVATION_DAYS` 日 ≥ `KD_OVERBOUGHT`（高檔鈍化＝強勢續漲，非賣訊）
          / ≤ `KD_OVERSOLD`（低檔鈍化）。
    背離（兩窗高低點法，避開脆弱單點 pivot）：最近 `KD_DIVERGENCE_LOOKBACK` 日切兩半——
      頂背離(空)：後半價高點 > 前半價高點 但 後半 K@高點 < 前半 K@高點；
      底背離(多)：後半價低點 < 前半價低點 但 後半 K@低點 > 前半 K@低點。

    Returns:
        dict{k,d,high_passivation,low_passivation,bearish_divergence,
             bullish_divergence,label} 或 None（資料不足/欄缺）。
    """
    from shared.signal_thresholds import (
        KD_DIVERGENCE_LOOKBACK,
        KD_OVERBOUGHT_LEVEL,
        KD_OVERSOLD_LEVEL,
        KD_PASSIVATION_DAYS,
    )
    try:
        if df is None or len(df) < period + KD_PASSIVATION_DAYS:
            return None
        k_s, d_s = calc_kd_series(df['close'], df['high'], df['low'], period)
        k_valid, d_valid = k_s.dropna(), d_s.dropna()
        if len(k_valid) < KD_PASSIVATION_DAYS:
            return None
        recent_k = k_valid.tail(KD_PASSIVATION_DAYS)
        high_passivation = bool((recent_k >= KD_OVERBOUGHT_LEVEL).all())
        low_passivation = bool((recent_k <= KD_OVERSOLD_LEVEL).all())

        # 背離:兩窗高低點（對齊 close 與 K，去 K 的前 period-1 NaN）
        bearish_div = bullish_div = False
        aligned = pd.DataFrame({'close': df['close'], 'k': k_s}).dropna()
        if len(aligned) >= KD_DIVERGENCE_LOOKBACK:
            win = aligned.tail(KD_DIVERGENCE_LOOKBACK)
            half = KD_DIVERGENCE_LOOKBACK // 2
            old, new = win.iloc[:half], win.iloc[half:]
            k_old_hi = float(old.loc[old['close'].idxmax(), 'k'])
            k_new_hi = float(new.loc[new['close'].idxmax(), 'k'])
            bearish_div = bool(new['close'].max() > old['close'].max()
                               and k_new_hi < k_old_hi)          # 價創高 K 沒創高
            k_old_lo = float(old.loc[old['close'].idxmin(), 'k'])
            k_new_lo = float(new.loc[new['close'].idxmin(), 'k'])
            bullish_div = bool(new['close'].min() < old['close'].min()
                               and k_new_lo > k_old_lo)          # 價創低 K 沒創低

        parts = []
        if high_passivation:
            parts.append('高檔鈍化')
        if low_passivation:
            parts.append('低檔鈍化')
        if bearish_div:
            parts.append('頂背離')
        if bullish_div:
            parts.append('底背離')
        return {
            'k': round(float(k_valid.iloc[-1]), 1),
            'd': round(float(d_valid.iloc[-1]), 1) if len(d_valid) else None,
            'high_passivation': high_passivation,
            'low_passivation': low_passivation,
            'bearish_divergence': bearish_div,
            'bullish_divergence': bullish_div,
            'label': '／'.join(parts) if parts else '無',
        }
    except Exception as e:
        print(f'[tech_indicators/analyze_kd_state] fail: '
              f'{type(e).__name__}: {e}', file=sys.stderr)
        return None


def calc_vcp(df, n_swings=3):
    # v19.83(第六份 review 3-4 邊界):本函式契約「失敗回 None」,但原本無 try/except —
    # 缺 high/low 欄(KeyError)或 swing 價為 0(ZeroDivisionError)會直接炸到 caller
    # (tab_stock.py:266 裸呼叫,一炸整個個股 Tab 全掛)。補同儕 calc_kd/calc_bollinger
    # 既有的 try/except + stderr log 模式,計算邏輯 0 改動。
    try:
        if df is None or len(df) < 30:
            return None  # relaxed to 30 days
        highs, lows = df['high'].values, df['low'].values
        swings, w = [], 10
        for i in range(w, len(df) - w):
            if highs[i] == max(highs[max(0, i-w):i+w+1]):
                swings.append(('H', i, highs[i]))
            elif lows[i] == min(lows[max(0, i-w):i+w+1]):
                swings.append(('L', i, lows[i]))

        # P8修正: 只計算 H-L 或 L-H 交替的振幅（過濾連續同向swing）
        alt_swings = []
        for sw in swings:
            if not alt_swings or alt_swings[-1][0] != sw[0]:
                alt_swings.append(sw)
            else:
                # 同向取極值（HH取高，LL取低）
                if sw[0] == 'H' and sw[2] > alt_swings[-1][2]:
                    alt_swings[-1] = sw
                elif sw[0] == 'L' and sw[2] < alt_swings[-1][2]:
                    alt_swings[-1] = sw
        swings = alt_swings

        ranges = [abs(swings[k][2]-swings[k+1][2])/min(swings[k][2], swings[k+1][2])*100
                  for k in range(len(swings)-1) if swings[k][0] != swings[k+1][0]]
        if len(ranges) < n_swings:
            return None
        last_n = ranges[-n_swings:]
        return {'swings': last_n,
                'contracting': all(last_n[i] > last_n[i+1] for i in range(len(last_n)-1)),
                'latest_range': last_n[-1]}
    except Exception as e:
        print(f'[tech_indicators/calc_vcp] n_swings={n_swings} fail: '
              f'{type(e).__name__}: {e}', file=sys.stderr)
        return None
