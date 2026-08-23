"""src/data/macro/macro_cache_reader.py — Parquet 本地快取讀取 L1(C4 v18.402).

從 L2 modules 抽出的 Parquet 檔案 I/O,落實 §8.2「L2 純函式無 I/O」契約:
- 原 `src/compute/macro/macro_signal_lookback_tw.py:109 _load_parquet_safe`
- 原 `src/compute/macro/macro_validation_tw.py:40 load_twii_close_from_parquet`

§8.2 layer:L1 Data — 本地 cache 反序列化(filesystem read,非網路 I/O)。
無 Streamlit 依賴(L2 caller 為純函式契約,L1 helper 也保持無 streamlit)。

對外 API:
- `DEFAULT_PARQUET_CACHE_DIR`:預設 cache 目錄(Path("data_cache"))
- `load_parquet_safe(path, required_cols) -> DataFrame | None`:通用 safe loader
- `load_twii_close(cache_dir) -> Series`:讀 twii_ohlcv.parquet → close series
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_PARQUET_CACHE_DIR = Path("data_cache")


def load_parquet_safe(path: Path, required_cols: set) -> Optional[pd.DataFrame]:
    """安全讀 Parquet — 缺檔 / 壞檔 / 缺欄 → 回 None。

    Args:
        path: parquet 檔絕對 / 相對路徑
        required_cols: 必須存在的欄位 set;任一缺失即視為損壞,回 None

    Returns:
        DataFrame(命中)或 None(任一失敗條件)
    """
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty or not required_cols.issubset(df.columns):
            return None
        return df
    except Exception as e:  # noqa: BLE001
        print(f"[macro_cache_reader/load_parquet_safe] {path.name} 讀檔失敗:{e}")
        return None


def load_twii_close(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """讀 twii_ohlcv.parquet → close pd.Series indexed by date(Timestamp)。

    Args:
        cache_dir: parquet cache 目錄(預設 data_cache/)

    Returns:
        close pd.Series(name='twii_close',date 升序,NaN dropped);
        若檔不存在 / 壞 / 缺欄,回空 Series(name 保留)
    """
    path = cache_dir / "twii_ohlcv.parquet"
    df = load_parquet_safe(path, {"date", "close"})
    if df is None:
        return pd.Series(dtype=float, name="twii_close")
    try:
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        s = (df.set_index("date")["close"]
               .astype(float)
               .sort_index())
        s.name = "twii_close"
        return s.dropna()
    except Exception as e:  # noqa: BLE001
        print(f"[macro_cache_reader/load_twii_close] 處理失敗:{e}")
        return pd.Series(dtype=float, name="twii_close")


# ══════════════════════════════════════════════════════════════════════
# 極端風險閘門的兩腿取數（v19.x,2026-08-23）
# ══════════════════════════════════════════════════════════════════════
#
# 消費端:scripts/push_holdings_daily.py → src/compute/notify/market_alert_banner
# 門檻 SSOT:shared/signal_thresholds.py「極端風險閘門」段
#
# 為什麼取數在這裡而不在 L2:這兩腿要讀 parquet,是 I/O。§8.2 明文「L2 不得 I/O」,
# 而 repo 內已有一個同型待修違憲(V-RADAR-1:risk_radar 在 L2 直接打 HTTP),不再複製。

def _leg_series(df, date_col: str, val_col: str, max_age_days: int, today):
    """共用:parquet → (排序後的 DataFrame, 資料最新日期) ;過舊或空回 (None, latest)。

    回傳 latest 即使判定過舊 —— 呼叫端要能在訊息裡講出「舊到什麼時候」。
    """
    import datetime as _dt

    if df is None:
        return None, None
    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    d = d.dropna(subset=[date_col, val_col]).sort_values(date_col)
    if d.empty:
        return None, None
    latest = d[date_col].max()
    _today = pd.Timestamp(today or _dt.date.today())
    age = (_today.normalize() - latest.normalize()).days
    if age > max_age_days:
        print(f"[macro_cache_reader/_leg_series] {val_col} 落後 {age} 天"
              f"(最新 {latest.date()},上限 {max_age_days}）→ 判為無法評估")
        return None, latest
    return d, latest


def load_extreme_risk_legs(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
    *,
    today=None,
) -> dict:
    """極端風險閘門的兩腿 → dict。任一腿算不出來就是 None,**不補值、不猜**。

    Returns:
        {
          "twii_20d_pct":  float | None,   # 加權指數 20 交易日報酬(%)
          "foreign_5d_yi": float | None,   # 外資 5 日累計淨買賣(億 TWD)
          "twii_date":     date  | None,   # 各腿的資料最新日期(供訊息揭露)
          "foreign_date":  date  | None,
        }

    ⚠️ `twii_ohlcv.parquet` 的 **volume 欄自 2026-07-09 起每日皆為 0**
    (Yahoo Chart API 對 ^TWII 停止回傳量,見 services/market_strategy.py 註解)。
    本函式**只讀 close**,不碰 volume。

    「20 交易日」直接取 parquet 的第 20 列之前 —— parquet 的每一列就是一個交易日,
    不需要 trading calendar(這也是為什麼跌幅腿讀 parquet 而不是現抓)。
    """
    from shared.signal_thresholds import EXTREME_STALE_MAX_CALENDAR_DAYS as _MAX_AGE

    out: dict = {"twii_20d_pct": None, "foreign_5d_yi": None,
                 "twii_date": None, "foreign_date": None}

    _tw, _tw_latest = _leg_series(
        load_parquet_safe(cache_dir / "twii_ohlcv.parquet", {"date", "close"}),
        "date", "close", _MAX_AGE, today)
    out["twii_date"] = None if _tw_latest is None else _tw_latest.date()
    if _tw is not None and len(_tw) > 20:
        _c = _tw["close"].astype(float).to_numpy()
        _base = _c[-21]
        if _base > 0:
            out["twii_20d_pct"] = float((_c[-1] / _base - 1.0) * 100.0)
        else:
            print("[macro_cache_reader/load_extreme_risk_legs] 20 日前收盤 <= 0,無法算報酬")
    elif _tw is not None:
        print(f"[macro_cache_reader/load_extreme_risk_legs] TWII 僅 {len(_tw)} 列,"
              f"不足 21 列算 20 日報酬")

    _fi, _fi_latest = _leg_series(
        load_parquet_safe(cache_dir / "finmind_inst.parquet", {"date", "foreign_buy"}),
        "date", "foreign_buy", _MAX_AGE, today)
    out["foreign_date"] = None if _fi_latest is None else _fi_latest.date()
    if _fi is not None and len(_fi) >= 5:
        out["foreign_5d_yi"] = float(_fi["foreign_buy"].astype(float).to_numpy()[-5:].sum())
    elif _fi is not None:
        print(f"[macro_cache_reader/load_extreme_risk_legs] 外資僅 {len(_fi)} 列,不足 5 列")

    return out


def fetch_lead_market_changes(*, range_: str = "5d") -> dict:
    """國際盤領先市場的**日變動 %** → {symbol: pct | None}。

    提示層用(門檻 shared/global_lead_markets.GLOBAL_LEAD_DROP_PCT)。抓不到的
    標的給 None,由 L2 `format_global_lead_line` 決定怎麼揭露 —— **本函式不吞掉
    失敗、也不用 0 代替**:0% 會被讀成「持平」,而持平和不知道是兩件事。

    取數重用既有的 `macro_core.fetch_yf_close`(走 NAS proxy 直打 Chart API),
    不另開一條 HTTP。lazy import 避免本模組被純 parquet 場景 import 時
    連帶拉起整個 macro_core 依賴鏈。

    §8.2:本函式在 L1,做網路 I/O 是對的位置。
    """
    from shared.global_lead_markets import LEAD_MARKETS

    out: dict = {}
    for m in LEAD_MARKETS:
        try:
            from src.data.macro.macro_core import fetch_yf_close
            s = fetch_yf_close(m.symbol, range_=range_)
            if s is None or len(s) < 2:
                out[m.symbol] = None
                print(f"[macro_cache_reader/fetch_lead_market_changes] {m.symbol} 資料不足")
                continue
            prev, last = float(s.iloc[-2]), float(s.iloc[-1])
            out[m.symbol] = float((last / prev - 1.0) * 100.0) if prev > 0 else None
        except Exception as e:  # noqa: BLE001
            out[m.symbol] = None
            print(f"[macro_cache_reader/fetch_lead_market_changes] {m.symbol} 失敗:{e}")
    return out
