"""macro_validation_tw.py — 台股總經 tab 歷史驗證引擎 (v18.150 Phase C).

User 需求：「兩邊都可以做回測來驗證台股的總經 tab 與基金（全球的）總經 tab」.

姐妹 repo my-Fund-dashboard 已於 v18.276 (Phase B.2) 把 FRED 9 指標 Parquet
接到 Phase 6a 驗證 UI；本模組為**台灣指標版本**，讀 PR #149 v18.149 鋪好的
`data_cache/*.parquet`：

- `finmind_ndc_signal.parquet`     — 景氣對策信號分數 9-45（月頻拐點）
- `finmind_leading_index.parquet`  — 領先指標綜合指數（6M smoothed change）
- `twii_ohlcv.parquet`             — TWII 日 K（crisis 偵測對齊）

範圍邊界
========
✅ 收錄：純 pandas 計算（讀 Parquet、偵測 crisis、命中驗證）
✅ 收錄：與 services/macro_validation.py（fund 那邊）同形邏輯，命名儘量平行
❌ 不收錄：Streamlit 渲染（在 tab_macro_validation.py）
❌ 不收錄：抓 FinMind / Yahoo（在 update_macro_history.py）

判定邏輯
========
TWII crisis：歷史峰前後檢視 ≥drop_threshold（預設 20%）的回撤事件
NDC 命中：peak 月 score 比峰前 N 月低 ≥drop_pts（預設 4 分；NDC 9-45 跨度，4 分 ≈ 1 燈號）
領先指標命中：peak 月 6M smoothed change 為負（擴張→收縮翻轉）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_PARQUET_CACHE_DIR = Path("data_cache")


# ════════════════════════════════════════════════════════════════
# Parquet 讀取
# ════════════════════════════════════════════════════════════════
def load_twii_close_from_parquet(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """讀 twii_ohlcv.parquet → close pd.Series indexed by date (Timestamp).

    twii_ohlcv 為 OHLCV 多欄；本函式只取 close 欄。
    """
    path = cache_dir / "twii_ohlcv.parquet"
    if not path.exists():
        return pd.Series(dtype=float, name="twii_close")
    try:
        df = pd.read_parquet(path)
        if df.empty or "date" not in df.columns or "close" not in df.columns:
            return pd.Series(dtype=float, name="twii_close")
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        s = (df.set_index("date")["close"]
               .astype(float)
               .sort_index())
        s.name = "twii_close"
        return s.dropna()
    except Exception as e:  # noqa: BLE001
        print(f"[macro_validation_tw/load_twii] 讀檔失敗：{e}")
        return pd.Series(dtype=float, name="twii_close")


# ════════════════════════════════════════════════════════════════
# TWII crisis 偵測（high-water-mark walk-forward）
# ════════════════════════════════════════════════════════════════
@dataclass
class TwiiCrisisEvent:
    """單一 TWII 危機事件（峰 → 谷 → 回升）."""
    peak_date: pd.Timestamp
    peak_close: float
    trough_date: pd.Timestamp
    trough_close: float
    recovery_date: Optional[pd.Timestamp]   # 第一次回到 peak_close 的日期（可能 None）
    drawdown_pct: float                       # (trough - peak) / peak，負數


def detect_twii_crisis_events(
    close_series: pd.Series,
    drop_threshold: float = 0.20,
) -> list[TwiiCrisisEvent]:
    """掃 TWII 日 K 收盤序列，偵測 ≥drop_threshold 的回撤事件.

    演算法（high-water-mark walk-forward，與 fund services/crisis_backtest 同範式）：
      1. 維持 running peak
      2. 任一日收盤 < peak × (1 - drop_threshold) → 標為 crisis 進行中
      3. 該 crisis 期間最低點為 trough
      4. close 回到 ≥ peak → 標為 recovery，crisis 結束、reset peak
      5. 若到序列結束仍未 recovery → recovery_date = None

    Returns:
        list[TwiiCrisisEvent]，依 peak_date 升序。空序列 / 序列過短 → 回空 list。
    """
    if close_series is None or close_series.empty or len(close_series) < 30:
        return []
    if not isinstance(close_series.index, pd.DatetimeIndex):
        try:
            close_series = close_series.copy()
            close_series.index = pd.to_datetime(close_series.index)
        except Exception:
            return []

    s = close_series.dropna().sort_index()
    events: list[TwiiCrisisEvent] = []

    peak = float(s.iloc[0])
    peak_dt = s.index[0]
    in_crisis = False
    trough = peak
    trough_dt = peak_dt

    for dt, v in s.items():
        v = float(v)
        if not in_crisis:
            if v >= peak:
                peak = v
                peak_dt = dt
            elif v <= peak * (1 - drop_threshold):
                in_crisis = True
                trough = v
                trough_dt = dt
        else:
            if v < trough:
                trough = v
                trough_dt = dt
            if v >= peak:
                # recovery
                events.append(TwiiCrisisEvent(
                    peak_date=peak_dt,
                    peak_close=peak,
                    trough_date=trough_dt,
                    trough_close=trough,
                    recovery_date=dt,
                    drawdown_pct=(trough - peak) / peak,
                ))
                in_crisis = False
                peak = v
                peak_dt = dt
                trough = v
                trough_dt = dt

    # 結尾未 recovery 也要記
    if in_crisis:
        events.append(TwiiCrisisEvent(
            peak_date=peak_dt,
            peak_close=peak,
            trough_date=trough_dt,
            trough_close=trough,
            recovery_date=None,
            drawdown_pct=(trough - peak) / peak,
        ))

    return events


