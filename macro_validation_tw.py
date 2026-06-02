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
def load_ndc_signal_from_parquet(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """讀 finmind_ndc_signal.parquet → pd.Series indexed by date (Timestamp).

    缺檔/壞檔 → 回空 Series（不 raise）。
    """
    path = cache_dir / "finmind_ndc_signal.parquet"
    if not path.exists():
        return pd.Series(dtype=float, name="ndc_signal")
    try:
        df = pd.read_parquet(path)
        if df.empty or not {"date", "ndc_signal"}.issubset(df.columns):
            return pd.Series(dtype=float, name="ndc_signal")
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        s = (df.set_index("date")["ndc_signal"]
               .astype(float)   # PR #149 寫 Int64，轉 float 方便 rolling
               .sort_index())
        s.name = "ndc_signal"
        return s.dropna()
    except Exception as e:  # noqa: BLE001
        print(f"[macro_validation_tw/load_ndc] 讀檔失敗：{e}")
        return pd.Series(dtype=float, name="ndc_signal")


def load_leading_index_from_parquet(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """讀 finmind_leading_index.parquet → pd.Series indexed by date (Timestamp)."""
    path = cache_dir / "finmind_leading_index.parquet"
    if not path.exists():
        return pd.Series(dtype=float, name="leading_index")
    try:
        df = pd.read_parquet(path)
        if df.empty or not {"date", "leading_index"}.issubset(df.columns):
            return pd.Series(dtype=float, name="leading_index")
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        s = (df.set_index("date")["leading_index"]
               .astype(float)
               .sort_index())
        s.name = "leading_index"
        return s.dropna()
    except Exception as e:  # noqa: BLE001
        print(f"[macro_validation_tw/load_li] 讀檔失敗：{e}")
        return pd.Series(dtype=float, name="leading_index")


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


# ════════════════════════════════════════════════════════════════
# 命中驗證
# ════════════════════════════════════════════════════════════════
@dataclass
class NdcVerifyResult:
    """單一 TWII 事件對 NDC 信號的預警判定."""
    peak_date: pd.Timestamp
    drawdown_pct: float
    ndc_at_lead: Optional[int]
    ndc_at_peak: Optional[int]
    ndc_drop_pts: Optional[int]   # ndc_at_peak - ndc_at_lead（負 = 下降）
    hit: bool                       # ndc_drop_pts ≤ -drop_pts_threshold


def verify_ndc_signal_vs_crises(
    ndc_series: pd.Series,
    events: list[TwiiCrisisEvent],
    lead_months: int = 6,
    drop_pts_threshold: int = 4,
) -> list[NdcVerifyResult]:
    """對每個 TWII crisis 事件判定「峰前 N 月 NDC score 是否預警下降 ≥drop_pts」.

    NDC 9-45 跨度，4 分 ≈ 跨 1 燈號（紅黃綠藍）→ 預設門檻 4 分。
    """
    out: list[NdcVerifyResult] = []
    if ndc_series is None or ndc_series.empty or not events:
        return out
    s = ndc_series.dropna().sort_index()

    def _val_at_or_before(dt: pd.Timestamp) -> Optional[int]:
        mask = s.index <= dt
        if not mask.any():
            return None
        return int(round(s[mask].iloc[-1]))

    for ev in events:
        peak_dt = pd.Timestamp(ev.peak_date)
        lead_dt = peak_dt - pd.DateOffset(months=int(lead_months))
        v_lead = _val_at_or_before(lead_dt)
        v_peak = _val_at_or_before(peak_dt)
        drop_pts: Optional[int] = None
        hit = False
        if v_lead is not None and v_peak is not None:
            drop_pts = v_peak - v_lead
            hit = drop_pts <= -int(drop_pts_threshold)
        out.append(NdcVerifyResult(
            peak_date=peak_dt,
            drawdown_pct=ev.drawdown_pct,
            ndc_at_lead=v_lead,
            ndc_at_peak=v_peak,
            ndc_drop_pts=drop_pts,
            hit=hit,
        ))
    return out


@dataclass
class LeadingIndexVerifyResult:
    """單一 TWII 事件對領先指標 6M smoothed change 的預警判定."""
    peak_date: pd.Timestamp
    drawdown_pct: float
    li_smooth_at_lead: Optional[float]   # peak 前 N 月的 6M smoothed change %
    li_smooth_at_peak: Optional[float]   # peak 月的 6M smoothed change %
    hit: bool                              # peak 月 smoothed change < 0（翻負警示）


def compute_smoothed_change_pct(
    s: pd.Series,
    window: int = 6,
) -> pd.Series:
    """6M smoothed change %：取 6 月 MA → pct_change × 100.

    與 tw_macro.fetch_ndc_leading_index 完全一致。
    """
    if s is None or s.empty:
        return pd.Series(dtype=float)
    ma = s.rolling(window).mean().dropna()
    if len(ma) < 2:
        return pd.Series(dtype=float)
    return (ma.pct_change() * 100).dropna()


def verify_leading_index_vs_crises(
    leading_index_series: pd.Series,
    events: list[TwiiCrisisEvent],
    lead_months: int = 6,
    smooth_window: int = 6,
) -> list[LeadingIndexVerifyResult]:
    """對每個 TWII crisis 事件判定「峰月領先指標 6M smoothed change 是否已翻負」.

    判定簡化版：peak 月的 smoothed change <0 即算「預警成功」（領先指標已示警）。
    """
    out: list[LeadingIndexVerifyResult] = []
    if (leading_index_series is None or leading_index_series.empty
            or not events):
        return out

    smoothed = compute_smoothed_change_pct(leading_index_series, window=smooth_window)
    if smoothed.empty:
        return out

    def _val_at_or_before(dt: pd.Timestamp) -> Optional[float]:
        mask = smoothed.index <= dt
        if not mask.any():
            return None
        return float(smoothed[mask].iloc[-1])

    for ev in events:
        peak_dt = pd.Timestamp(ev.peak_date)
        lead_dt = peak_dt - pd.DateOffset(months=int(lead_months))
        v_lead = _val_at_or_before(lead_dt)
        v_peak = _val_at_or_before(peak_dt)
        hit = v_peak is not None and v_peak < 0
        out.append(LeadingIndexVerifyResult(
            peak_date=peak_dt,
            drawdown_pct=ev.drawdown_pct,
            li_smooth_at_lead=v_lead,
            li_smooth_at_peak=v_peak,
            hit=hit,
        ))
    return out


# ════════════════════════════════════════════════════════════════
# 統計卡支援
# ════════════════════════════════════════════════════════════════
def compute_hit_rate(results: list) -> tuple[int, int, float]:
    """從 NdcVerifyResult 或 LeadingIndexVerifyResult 列表算 hit / total / rate."""
    if not results:
        return (0, 0, 0.0)
    n_hit = sum(1 for r in results if getattr(r, "hit", False))
    n_total = sum(
        1 for r in results
        if (getattr(r, "ndc_drop_pts", None) is not None
            or getattr(r, "li_smooth_at_peak", None) is not None)
    )
    rate = (n_hit / n_total) if n_total > 0 else 0.0
    return (n_hit, n_total, rate)
