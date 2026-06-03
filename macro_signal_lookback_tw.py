"""macro_signal_lookback_tw.py — 台股總經訊號歷史回看引擎 (v18.159, Phase 3).

User 需求：「基金有這測試總經的預測力，台股沒有看到」.

姐妹 repo my-Fund-dashboard 已於 v18.260 Phase 3 用 `services/macro_signal_lookback.py`
驗證全球訊號（VIX / HY / T10Y2Y / UNRATE）對 SPX crisis 的命中率。本模組為**台股
本地版本**，鏡像 fund 引擎但訊號來自 `data_cache/` 4 表（無需額外抓 FRED / Yahoo）：

| 訊號                  | 資料源                       | 閾值          | 解讀                            |
|-----------------------|------------------------------|---------------|---------------------------------|
| 外資 5 日累積賣超     | finmind_inst.foreign_buy     | sum5 ≤ -500   | 連 5 日合計大賣 500 億 → 警戒   |
| 融資餘額過熱          | finmind_margin.margin_balance| ≥ 3400 億     | 散戶槓桿水位過高 → 警示         |
| M1B/M2 缺口惡化       | finmind_m1m2.m1b_m2_gap.diff | ≤ -2 pts/月   | 單月資金結構惡化 → 頭部訊號     |
| TWII 20 日跌幅        | twii_ohlcv.close.pct_change  | ≤ -5%         | 月跌 5% → 加速下跌確認          |

公式鏡像 services/macro_signal_lookback.py (fund repo)：
- evaluate_signal_at_event: 點觀測 + 峰前最早警戒搜尋
- lookback_all_signals: 批次
- compute_signal_hit_rate: 命中率 / 平均提前天數

範圍邊界
========
✅ 收錄：純函式，不依賴 Streamlit
✅ 收錄：讀 data_cache/*.parquet → 計算 daily series
❌ 不收錄：Streamlit 渲染（在 tab_macro_validation.py）
❌ 不收錄：抓 FinMind / Yahoo（在 update_macro_history.py）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Optional

import pandas as pd

from macro_validation_tw import DEFAULT_PARQUET_CACHE_DIR, TwiiCrisisEvent

# 訊號方向：above = 超過閾值算警戒；below = 低於閾值算警戒
Direction = Literal["above", "below"]


@dataclass(frozen=True)
class TwSignalSpec:
    """單一訊號的判讀規格（series 由 TW_SIGNAL_FETCHERS registry 取得）。"""
    key: str
    label: str
    threshold: float
    direction: Direction
    unit: str = ""
    note: str = ""


@dataclass
class TwSignalLookback:
    """單一事件 × 單一訊號的回看結果。"""
    event_peak_date: pd.Timestamp
    signal_key: str
    signal_label: str
    threshold: float
    direction: Direction
    lookback_days: int
    value_at_lookback: Optional[float]
    triggered_at_lookback: bool
    first_warning_date: Optional[pd.Timestamp]
    lead_time_days: Optional[int]

    def to_dict(self) -> dict:
        return {
            "event_peak_date": str(self.event_peak_date.date()) if self.event_peak_date is not None else None,
            "signal_key": self.signal_key,
            "signal_label": self.signal_label,
            "threshold": float(self.threshold),
            "direction": self.direction,
            "lookback_days": int(self.lookback_days),
            "value_at_lookback": float(self.value_at_lookback) if self.value_at_lookback is not None else None,
            "triggered_at_lookback": bool(self.triggered_at_lookback),
            "first_warning_date": str(self.first_warning_date.date()) if self.first_warning_date is not None else None,
            "lead_time_days": int(self.lead_time_days) if self.lead_time_days is not None else None,
        }


# ════════════════════════════════════════════════════════════════
# 4 個本地訊號的 series fetcher（讀 Parquet → 計算 daily series）
# ════════════════════════════════════════════════════════════════
def _load_parquet_safe(path: Path, required_cols: set) -> Optional[pd.DataFrame]:
    """安全讀 Parquet — 缺檔 / 壞檔 / 缺欄 → 回 None。"""
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty or not required_cols.issubset(df.columns):
            return None
        return df
    except Exception as e:  # noqa: BLE001
        print(f"[macro_signal_lookback_tw/load] {path.name} 讀檔失敗：{e}")
        return None


def fetch_foreign_sell_5d_series(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """外資 5 日累積買賣超（億元）— foreign_buy.rolling(5).sum()。

    < 0 表示淨賣超；訊號定義「sum5 ≤ -500 億」= 連 5 日累積賣超 ≥ 500 億。
    """
    df = _load_parquet_safe(cache_dir / "finmind_inst.parquet", {"date", "foreign_buy"})
    if df is None:
        return pd.Series(dtype=float, name="FOREIGN_SELL_5D")
    s = (df.assign(date=pd.to_datetime(df["date"]))
           .set_index("date")["foreign_buy"]
           .astype(float)
           .sort_index()
           .rolling(window=5, min_periods=5)
           .sum())
    s.name = "FOREIGN_SELL_5D"
    return s.dropna()


def fetch_margin_balance_series(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """融資餘額（億元）— margin_balance / 1e8（原始 Parquet 單位是元）。"""
    df = _load_parquet_safe(cache_dir / "finmind_margin.parquet",
                             {"date", "margin_balance"})
    if df is None:
        return pd.Series(dtype=float, name="MARGIN_BALANCE")
    s = (df.assign(date=pd.to_datetime(df["date"]))
           .set_index("date")["margin_balance"]
           .astype(float)
           .sort_index()
           / 1e8)
    s.name = "MARGIN_BALANCE"
    return s.dropna()


def fetch_m1b_m2_diff_series(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """M1B-M2 缺口月變動 — m1b_m2_gap.diff()。

    月頻 series。對 evaluate 而言，會在事件日期向前找 ≤ event_date 最近一筆月度值。
    """
    df = _load_parquet_safe(cache_dir / "finmind_m1m2.parquet",
                             {"date", "m1b_m2_gap"})
    if df is None:
        return pd.Series(dtype=float, name="M1B_M2_DIFF")
    s = (df.assign(date=pd.to_datetime(df["date"]))
           .set_index("date")["m1b_m2_gap"]
           .astype(float)
           .sort_index()
           .diff())
    s.name = "M1B_M2_DIFF"
    return s.dropna()


def fetch_twii_drop_20d_series(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """TWII 20 日跌幅 %（pct_change(20) * 100）."""
    df = _load_parquet_safe(cache_dir / "twii_ohlcv.parquet", {"date", "close"})
    if df is None:
        return pd.Series(dtype=float, name="TWII_DROP_20D")
    s = (df.assign(date=pd.to_datetime(df["date"]))
           .set_index("date")["close"]
           .astype(float)
           .sort_index()
           .pct_change(20) * 100.0)
    s.name = "TWII_DROP_20D"
    return s.dropna()


# Registry：key → fetcher（從 spec.key 拿對應 series fetcher）
TW_SIGNAL_FETCHERS: dict[str, Callable[[Path], pd.Series]] = {
    "FOREIGN_SELL_5D": fetch_foreign_sell_5d_series,
    "MARGIN_BALANCE":  fetch_margin_balance_series,
    "M1B_M2_DIFF":     fetch_m1b_m2_diff_series,
    "TWII_DROP_20D":   fetch_twii_drop_20d_series,
}


# 預設訊號表 — 對齊 fund Phase 3 的 4 國際訊號結構
DEFAULT_TW_SIGNALS: list[TwSignalSpec] = [
    TwSignalSpec(
        key="FOREIGN_SELL_5D",
        label="外資 5 日累積買賣超",
        threshold=-500.0,
        direction="below",
        unit="億",
        note="5 日累積賣超 ≥ 500 億 → 警戒",
    ),
    TwSignalSpec(
        key="MARGIN_BALANCE",
        label="融資餘額",
        threshold=3400.0,
        direction="above",
        unit="億",
        note="融資餘額 ≥ 3400 億（散戶槓桿過熱）",
    ),
    TwSignalSpec(
        key="M1B_M2_DIFF",
        label="M1B/M2 缺口惡化",
        threshold=-2.0,
        direction="below",
        unit="pts/月",
        note="單月 M1B-M2 缺口惡化 ≥ 2 pts（資金流出股市）",
    ),
    TwSignalSpec(
        key="TWII_DROP_20D",
        label="TWII 20 日跌幅",
        threshold=-5.0,
        direction="below",
        unit="%",
        note="20 日跌幅 ≤ -5%（加速下跌）",
    ),
]


# ════════════════════════════════════════════════════════════════
# 引擎：evaluate / lookback / hit_rate（公式鏡像 fund repo）
# ════════════════════════════════════════════════════════════════
def _is_warning(value: float, threshold: float, direction: Direction) -> bool:
    if direction == "above":
        return value >= threshold
    return value <= threshold


def fetch_all_tw_signal_series(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
    specs: Optional[list[TwSignalSpec]] = None,
) -> dict[str, pd.Series]:
    """批次抓所有 spec 對應 series。"""
    if specs is None:
        specs = DEFAULT_TW_SIGNALS
    out: dict[str, pd.Series] = {}
    for spec in specs:
        fn = TW_SIGNAL_FETCHERS.get(spec.key)
        if fn is None:
            out[spec.key] = pd.Series(dtype=float, name=spec.key)
            continue
        try:
            out[spec.key] = fn(cache_dir)
        except Exception as e:  # noqa: BLE001
            print(f"[macro_signal_lookback_tw] {spec.key} fetch 失敗：{e}")
            out[spec.key] = pd.Series(dtype=float, name=spec.key)
    return out


def evaluate_signal_at_event(
    event: TwiiCrisisEvent,
    signal_series: pd.Series,
    spec: TwSignalSpec,
    lookback_days: int = 90,
    max_lookback_days: int = 365,
) -> TwSignalLookback:
    """對單一事件單一訊號做回看判讀（鏡像 fund repo）.

    1. 取峰日往前 lookback_days 那一天 ≤ 目標日的最近觀測值 → triggered_at_lookback
    2. 在峰前 max_lookback_days 區間找「最早一次」進入警戒區 → lead_time_days
    """
    if signal_series is None or signal_series.empty or event.peak_date is None:
        return TwSignalLookback(
            event_peak_date=event.peak_date,
            signal_key=spec.key,
            signal_label=spec.label,
            threshold=spec.threshold,
            direction=spec.direction,
            lookback_days=lookback_days,
            value_at_lookback=None,
            triggered_at_lookback=False,
            first_warning_date=None,
            lead_time_days=None,
        )

    peak = event.peak_date
    target = peak - pd.Timedelta(days=lookback_days)
    before_peak = signal_series[signal_series.index <= peak]
    if before_peak.empty:
        return TwSignalLookback(
            event_peak_date=peak,
            signal_key=spec.key,
            signal_label=spec.label,
            threshold=spec.threshold,
            direction=spec.direction,
            lookback_days=lookback_days,
            value_at_lookback=None,
            triggered_at_lookback=False,
            first_warning_date=None,
            lead_time_days=None,
        )

    on_or_before = before_peak[before_peak.index <= target]
    value_at_lb: Optional[float] = float(on_or_before.iloc[-1]) if not on_or_before.empty else None
    triggered_lb = (value_at_lb is not None) and _is_warning(value_at_lb, spec.threshold, spec.direction)

    window_start = peak - pd.Timedelta(days=max_lookback_days)
    window = before_peak[(before_peak.index >= window_start) & (before_peak.index <= peak)]
    first_warn_date: Optional[pd.Timestamp] = None
    lead_days: Optional[int] = None
    if not window.empty:
        warn_mask = window.apply(lambda v: _is_warning(float(v), spec.threshold, spec.direction))
        warn_idx = window.index[warn_mask]
        if len(warn_idx) > 0:
            first_warn_date = warn_idx[0]
            lead_days = (peak - first_warn_date).days

    return TwSignalLookback(
        event_peak_date=peak,
        signal_key=spec.key,
        signal_label=spec.label,
        threshold=spec.threshold,
        direction=spec.direction,
        lookback_days=lookback_days,
        value_at_lookback=value_at_lb,
        triggered_at_lookback=triggered_lb,
        first_warning_date=first_warn_date,
        lead_time_days=lead_days,
    )


def lookback_all_signals_tw(
    events: list[TwiiCrisisEvent],
    series_by_key: dict[str, pd.Series],
    specs: Optional[list[TwSignalSpec]] = None,
    lookback_days: int = 90,
    max_lookback_days: int = 365,
) -> dict[str, list[TwSignalLookback]]:
    """批次：對所有事件 × 所有訊號做回看。"""
    if specs is None:
        specs = DEFAULT_TW_SIGNALS
    out: dict[str, list[TwSignalLookback]] = {}
    for spec in specs:
        series = series_by_key.get(spec.key, pd.Series(dtype=float))
        out[spec.key] = [
            evaluate_signal_at_event(ev, series, spec, lookback_days, max_lookback_days)
            for ev in events
        ]
    return out


def compute_signal_hit_rate(lookbacks: list[TwSignalLookback]) -> dict:
    """統計單一訊號的命中率 + 平均提前天數（鏡像 fund repo）.

    命中 = lead_time_days is not None（峰前 max_lookback_days 內曾警戒）
    覆蓋 = value_at_lookback is not None 或 first_warning_date is not None（序列有涵蓋）
    """
    if not lookbacks:
        return {"n_total": 0, "n_covered": 0, "n_hit": 0,
                "hit_rate": None, "avg_lead_days": None}
    n_total = len(lookbacks)
    covered = [lb for lb in lookbacks
               if lb.value_at_lookback is not None or lb.first_warning_date is not None]
    n_covered = len(covered)
    hits = [lb for lb in lookbacks if lb.lead_time_days is not None]
    n_hit = len(hits)
    hit_rate = (n_hit / n_covered) if n_covered > 0 else None
    avg_lead = (sum(lb.lead_time_days for lb in hits) / n_hit) if n_hit > 0 else None
    return {
        "n_total": n_total,
        "n_covered": n_covered,
        "n_hit": n_hit,
        "hit_rate": hit_rate,
        "avg_lead_days": avg_lead,
    }
