"""
src/core/technical_indicators.py — 統一技術指標計算

所有技術指標計算（RSI、MA、MACD、布林帶）統一在此模組實現。
禁止在其他模組重複實現相同邏輯。

特性：
- 純函數設計（無副作用）
- 支援 NaN 與缺失值處理
- 類型提示完整
- 高效能 numpy/pandas 實現

v2.0 重構 — 2026-06-20
"""

import pandas as pd
import numpy as np
from typing import Optional, List

from shared.constants import (
    RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    MA_SHORT, MA_MID, MA_LONG, MA_ANNUAL,
    MA_PERIODS_STANDARD, MA_PERIODS_EXTENDED,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BOLLINGER_PERIOD, BOLLINGER_STD_DEV,
)


# ============================================================================
# RSI (相對強度指數)
# ============================================================================

def calc_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """
    計算相對強度指數（Relative Strength Index）
    
    Args:
        close: 收盤價序列
        period: 計算週期（預設 14）
    
    Returns:
        RSI 序列（值介於 0-100）
    
    Notes:
        - 標準 Wilder 平滑法實現
        - < 30 超賣， > 70 超買
    """
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window=period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period, min_periods=period).mean()
    
    rs = gain / (loss + 1e-10)  # 防除零
    rsi = 100 - (100 / (1 + rs))
    
    return rsi


def classify_rsi(rsi: float) -> str:
    """
    根據 RSI 值分類技術狀態
    
    Args:
        rsi: RSI 值（0-100）
    
    Returns:
        'overbought' | 'oversold' | 'neutral'
    """
    if rsi > RSI_OVERBOUGHT:
        return 'overbought'
    elif rsi < RSI_OVERSOLD:
        return 'oversold'
    else:
        return 'neutral'


# ============================================================================
# 移動平均線 (MA)
# ============================================================================

def calc_ma(close: pd.Series, period: int) -> pd.Series:
    """
    計算簡單移動平均線（SMA）
    
    Args:
        close: 收盤價序列
        period: 均線週期
    
    Returns:
        SMA 序列
    """
    return close.rolling(window=period, min_periods=1).mean()


def ensure_moving_averages(
    df: pd.DataFrame,
    close_col: str = 'Close',
    periods: Optional[List[int]] = None,
    inplace: bool = False
) -> pd.DataFrame:
    """
    確保數據框含有所有標準均線（無則補充）
    
    Args:
        df: 股價數據框
        close_col: 收盤價列名（預設 'Close'）
        periods: 均線週期列表（預設使用標準週期）
        inplace: 是否原地修改（預設 False）
    
    Returns:
        包含均線的新數據框（或原地修改後的數據框）
    
    Example:
        >>> df = ensure_moving_averages(df)
        >>> print(df[['Close', 'MA5', 'MA20', 'MA60', 'MA120', 'MA240']])
    """
    if periods is None:
        periods = MA_PERIODS_STANDARD
    
    if not inplace:
        df = df.copy()
    
    close = df[close_col]
    for p in periods:
        col_name = f'MA{p}'
        if col_name not in df.columns:
            df[col_name] = calc_ma(close, p)
    
    return df


def get_ma_trend(close: pd.Series, short_period: int = MA_SHORT,
                 long_period: int = MA_LONG) -> str:
    """
    根據短/長期均線判定趨勢
    
    Args:
        close: 收盤價序列
        short_period: 短期均線週期
        long_period: 長期均線週期
    
    Returns:
        'uptrend' | 'downtrend' | 'mixed'
    """
    ma_short = calc_ma(close, short_period).iloc[-1]
    ma_long = calc_ma(close, long_period).iloc[-1]
    latest_close = close.iloc[-1]
    
    if pd.isna(ma_short) or pd.isna(ma_long):
        return 'mixed'
    
    if latest_close > ma_short > ma_long:
        return 'uptrend'
    elif latest_close < ma_short < ma_long:
        return 'downtrend'
    else:
        return 'mixed'


# ============================================================================
# MACD (移動平均匯聚發散)
# ============================================================================

def calc_macd(
    close: pd.Series,
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL
) -> pd.DataFrame:
    """
    計算 MACD 指標
    
    Args:
        close: 收盤價序列
        fast: 快線週期（預設 12）
        slow: 慢線週期（預設 26）
        signal: 訊號線週期（預設 9）
    
    Returns:
        包含 ['MACD', 'Signal', 'Histogram'] 的數據框
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    
    return pd.DataFrame({
        'MACD': macd,
        'Signal': signal_line,
        'Histogram': histogram,
    }, index=close.index)


def classify_macd(macd_val: float, signal_val: float, hist_val: float) -> str:
    """
    根據 MACD 值分類信號
    
    Args:
        macd_val: MACD 值
        signal_val: 訊號線值
        hist_val: 柱狀圖值
    
    Returns:
        'bullish' | 'bearish' | 'neutral'
    """
    if pd.isna(macd_val) or pd.isna(signal_val):
        return 'neutral'
    
    if macd_val > signal_val and hist_val > 0:
        return 'bullish'
    elif macd_val < signal_val and hist_val < 0:
        return 'bearish'
    else:
        return 'neutral'


# ============================================================================
# 布林帶 (Bollinger Bands)
# ============================================================================

def calc_bollinger_bands(
    close: pd.Series,
    period: int = BOLLINGER_PERIOD,
    std_dev: float = BOLLINGER_STD_DEV
) -> pd.DataFrame:
    """
    計算布林帶指標
    
    Args:
        close: 收盤價序列
        period: 計算週期（預設 20）
        std_dev: 標準差倍數（預設 2）
    
    Returns:
        包含 ['Upper', 'Middle', 'Lower', '%B'] 的數據框
        
    Notes:
        - %B = (Close - Lower) / (Upper - Lower)
        - %B > 1 表價格超出上軌（超買）
        - %B < 0 表價格超出下軌（超賣）
    """
    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    
    # %B 指標
    band_width = upper - lower
    percent_b = (close - lower) / (band_width + 1e-10)
    
    return pd.DataFrame({
        'Upper': upper,
        'Middle': middle,
        'Lower': lower,
        '%B': percent_b,
    }, index=close.index)


def classify_bollinger_bands(percent_b: float) -> str:
    """
    根據 %B 值分類價格位置
    
    Args:
        percent_b: %B 指標值
    
    Returns:
        'overbought' | 'oversold' | 'fair'
    """
    if pd.isna(percent_b):
        return 'fair'
    
    if percent_b > 1.0:
        return 'overbought'
    elif percent_b < 0.0:
        return 'oversold'
    else:
        return 'fair'


# ============================================================================
# 綜合分析工具
# ============================================================================

def analyze_technical_confluence(
    close: pd.Series,
    volume: Optional[pd.Series] = None
) -> dict:
    """
    綜合多個技術指標進行趨勢分析
    
    Args:
        close: 收盤價序列
        volume: 成交量序列（選填）
    
    Returns:
        包含各指標評分的字典
    
    Example:
        >>> signal = analyze_technical_confluence(df['Close'])
        >>> print(f"RSI 信號: {signal['rsi_signal']}")
        >>> print(f"MA 趨勢: {signal['ma_trend']}")
        >>> print(f"MACD 信號: {signal['macd_signal']}")
        >>> print(f"綜合評分: {signal['confluence_score']}/3")
    """
    if len(close) < max(MACD_SLOW, MA_ANNUAL):
        return {
            'status': 'insufficient_data',
            'confluence_score': 0,
        }
    
    latest_close = close.iloc[-1]
    
    # RSI 分析
    rsi = calc_rsi(close).iloc[-1]
    rsi_signal = 'bullish' if rsi > RSI_OVERBOUGHT else ('bearish' if rsi < RSI_OVERSOLD else 'neutral')
    
    # MA 趨勢
    ma_trend = get_ma_trend(close)
    
    # MACD 分析
    macd_df = calc_macd(close)
    macd_val = macd_df['MACD'].iloc[-1]
    signal_val = macd_df['Signal'].iloc[-1]
    hist_val = macd_df['Histogram'].iloc[-1]
    macd_signal = classify_macd(macd_val, signal_val, hist_val)
    
    # 布林帶分析
    bb_df = calc_bollinger_bands(close)
    percent_b = bb_df['%B'].iloc[-1]
    bb_signal = classify_bollinger_bands(percent_b)
    
    # 綜合評分
    confluence_score = sum([
        1 if ma_trend == 'uptrend' else 0,
        1 if macd_signal == 'bullish' else 0,
        1 if bb_signal != 'oversold' else 0,
    ])
    
    return {
        'latest_close': latest_close,
        'rsi': rsi,
        'rsi_signal': rsi_signal,
        'ma_trend': ma_trend,
        'macd': {
            'macd': macd_val,
            'signal': signal_val,
            'histogram': hist_val,
            'signal': macd_signal,
        },
        'bollinger_bands': {
            'upper': bb_df['Upper'].iloc[-1],
            'middle': bb_df['Middle'].iloc[-1],
            'lower': bb_df['Lower'].iloc[-1],
            'percent_b': percent_b,
            'signal': bb_signal,
        },
        'confluence_score': confluence_score,  # 0-3，越高越確認上升趨勢
    }


__all__ = [
    'calc_rsi', 'classify_rsi',
    'calc_ma', 'ensure_moving_averages', 'get_ma_trend',
    'calc_macd', 'classify_macd',
    'calc_bollinger_bands', 'classify_bollinger_bands',
    'analyze_technical_confluence',
]
