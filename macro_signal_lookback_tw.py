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


# v18.168：擴 3 個 parquet 衍生因子（成交量比 / 融資增速 / 已實現波動率）
def fetch_twse_vol_ratio_series(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """大盤成交量比（volume / SMA60 - 1，z-score 後輸出）.

    異常爆量 = 恐慌賣壓或拋售；z-score 之後高分代表偏離正常水位越多。
    direction="above" → 正向 z-score 越大越警戒。
    """
    df = _load_parquet_safe(cache_dir / "twii_ohlcv.parquet", {"date", "volume"})
    if df is None:
        return pd.Series(dtype=float, name="TWSE_VOL_RATIO")
    vol = (df.assign(date=pd.to_datetime(df["date"]))
             .set_index("date")["volume"]
             .astype(float)
             .sort_index())
    sma60 = vol.rolling(window=60, min_periods=60).mean()
    ratio = (vol / sma60 - 1.0).dropna()
    if ratio.empty:
        return pd.Series(dtype=float, name="TWSE_VOL_RATIO")
    mu, sd = ratio.mean(), ratio.std()
    if not sd or sd == 0:
        return pd.Series(dtype=float, name="TWSE_VOL_RATIO")
    z = (ratio - mu) / sd
    z.name = "TWSE_VOL_RATIO"
    return z.dropna()


def fetch_margin_growth_5d_series(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """融資餘額 5 日累積變動（億元，diff(5)）.

    > 0 = 5 日內融資餘額擴張（散戶加碼加速 → 槓桿堆積）；
    direction="above" → 增加越多越警戒。
    """
    df = _load_parquet_safe(cache_dir / "finmind_margin.parquet",
                             {"date", "margin_balance"})
    if df is None:
        return pd.Series(dtype=float, name="MARGIN_GROWTH_5D")
    s = (df.assign(date=pd.to_datetime(df["date"]))
           .set_index("date")["margin_balance"]
           .astype(float)
           .sort_index()
           / 1e8)
    s = s.diff(5)
    s.name = "MARGIN_GROWTH_5D"
    return s.dropna()


def fetch_twii_realized_vol_20d_series(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """TWII 20 日年化已實現波動率 %（returns.rolling(20).std() × √252 × 100）.

    本地版 VIX 替代品；高波動 = 市場恐慌 / 拋售加速。
    direction="above" → 波動率越高越警戒。
    """
    df = _load_parquet_safe(cache_dir / "twii_ohlcv.parquet", {"date", "close"})
    if df is None:
        return pd.Series(dtype=float, name="TWII_REALIZED_VOL_20D")
    close = (df.assign(date=pd.to_datetime(df["date"]))
               .set_index("date")["close"]
               .astype(float)
               .sort_index())
    rets = close.pct_change()
    vol = rets.rolling(window=20, min_periods=20).std() * (252 ** 0.5) * 100.0
    vol.name = "TWII_REALIZED_VOL_20D"
    return vol.dropna()


# Registry：key → fetcher（從 spec.key 拿對應 series fetcher）
TW_SIGNAL_FETCHERS: dict[str, Callable[[Path], pd.Series]] = {
    "FOREIGN_SELL_5D":       fetch_foreign_sell_5d_series,
    "MARGIN_BALANCE":        fetch_margin_balance_series,
    "M1B_M2_DIFF":           fetch_m1b_m2_diff_series,
    "TWII_DROP_20D":         fetch_twii_drop_20d_series,
    "TWSE_VOL_RATIO":        fetch_twse_vol_ratio_series,
    "MARGIN_GROWTH_5D":      fetch_margin_growth_5d_series,
    "TWII_REALIZED_VOL_20D": fetch_twii_realized_vol_20d_series,
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
    max_lookback_days: int = 180,
    mode: str = "edge",
) -> TwSignalLookback:
    """對單一事件單一訊號做回看判讀.

    1. 取峰日往前 lookback_days 那一天 ≤ 目標日的最近觀測值 → triggered_at_lookback
    2. 在峰前 max_lookback_days 區間找「進入警戒區」日期 → lead_time_days

    v18.160 修正：mode 參數
    - "state" (v1 legacy): 找 series 內第一次 value 落在警戒區
                            → 「一直亮紅燈」會被誤判成提前 N 天預警
    - "edge"  (v2 預設):   找 series 在 window 內**從非警戒跨越到警戒**的轉折日
                            → 真實「事件驅動」訊號；窗口開頭已警戒則不算（沒看到 transition）
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
        if mode == "edge":
            # v2 edge detection：全 series 算 warn_mask（含 window 外的歷史），
            # crossing = t-1 非警戒 + t 警戒；只取落在 window 內的 crossings
            full_warn = before_peak.apply(
                lambda v: _is_warning(float(v), spec.threshold, spec.direction))
            # shift 第 1 列補 True：series 起點的「之前狀態」未知，保守視為「已在警戒」
            # 這樣 series 第一筆即使在警戒區也不算 transition（避免誤判）
            crossings = full_warn & ~full_warn.shift(1, fill_value=True)
            cross_in_window = before_peak.index[
                crossings & (before_peak.index >= window_start)]
            if len(cross_in_window) > 0:
                first_warn_date = cross_in_window[0]
                lead_days = (peak - first_warn_date).days
        else:
            # v1 state：任何警戒值即算（legacy 行為，保留供回歸對照）
            warn_mask = window.apply(
                lambda v: _is_warning(float(v), spec.threshold, spec.direction))
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
    max_lookback_days: int = 180,
    mode: str = "edge",
) -> dict[str, list[TwSignalLookback]]:
    """批次：對所有事件 × 所有訊號做回看（v18.160 預設 edge mode）。"""
    if specs is None:
        specs = DEFAULT_TW_SIGNALS
    out: dict[str, list[TwSignalLookback]] = {}
    for spec in specs:
        series = series_by_key.get(spec.key, pd.Series(dtype=float))
        out[spec.key] = [
            evaluate_signal_at_event(ev, series, spec,
                                     lookback_days, max_lookback_days, mode)
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


# ══════════════════════════════════════════════════════════════
# v18.163：訊號精確率（forward-looking）— 解「召回率」單面向
# ══════════════════════════════════════════════════════════════

def compute_signal_precision(
    signal_series: pd.Series,
    events: list[TwiiCrisisEvent],
    spec: TwSignalSpec,
    max_forward_days: int = 365,
) -> dict:
    """訊號歷史精確率：遍歷全 series 抓所有 crossings → 每個 crossing
    後 max_forward_days 天內是否有 event.peak_date 命中（鏡像 fund v18.282）。

    召回率（Phase 3 hit_rate）= 已知危機回頭看訊號（向後）；
    精確率（本函數）       = 已知訊號響起看未來危機（向前）。

    Returns:
        {
            "n_crossings": int,
            "n_true_positives": int,
            "n_false_positives": int,
            "precision_pct": float | None,
            "false_alert_rate_pct": float | None,
            "avg_lead_to_crisis_days": float | None,
        }
    """
    base = {
        "n_crossings": 0,
        "n_true_positives": 0,
        "n_false_positives": 0,
        "precision_pct": None,
        "false_alert_rate_pct": None,
        "avg_lead_to_crisis_days": None,
    }
    if signal_series is None or signal_series.empty:
        return base
    s = signal_series.dropna()
    if s.empty:
        return base
    warn = s.apply(lambda v: _is_warning(float(v), spec.threshold, spec.direction))
    crossings_mask = warn & ~warn.shift(1, fill_value=True)
    crossing_dates = s.index[crossings_mask]
    n_cross = len(crossing_dates)
    if n_cross == 0:
        return base

    peak_dates = sorted([ev.peak_date for ev in events
                         if ev.peak_date is not None])
    n_tp = 0
    lead_days_list: list[int] = []
    for cd in crossing_dates:
        window_end = cd + pd.Timedelta(days=max_forward_days)
        hit_peak = next((pd_ for pd_ in peak_dates
                        if cd <= pd_ <= window_end), None)
        if hit_peak is not None:
            n_tp += 1
            lead_days_list.append((hit_peak - cd).days)
    n_fp = n_cross - n_tp
    precision = n_tp / n_cross
    return {
        "n_crossings": n_cross,
        "n_true_positives": n_tp,
        "n_false_positives": n_fp,
        "precision_pct": precision * 100,
        "false_alert_rate_pct": (1 - precision) * 100,
        "avg_lead_to_crisis_days": (sum(lead_days_list) / len(lead_days_list))
                                     if lead_days_list else None,
    }
