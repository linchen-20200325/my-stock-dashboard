"""L1 Repository — 個股/ETF 行情與估值 (yfinance)。

出口一律過 Pandera（§3.1）+ 蓋 provenance（§2.2）+ 空資料 Fail Loud（§1）。
純轉換函式（`_normalize_ohlcv` / `build_valuation`）與 I/O 分離,可離線單測。
"""
from __future__ import annotations

import pandas as pd

from ..core.circuit_breaker import require
from ..core.provenance import prov_log, stamp_df
from ..core.schemas import OHLCVSchema, ValuationSchema, validate_or_reject

_OHLCV_COLS = ["date", "open", "high", "low", "close", "volume"]


def _to_naive_datetime(series: pd.Series) -> pd.Series:
    """統一成 tz-naive datetime（不位移 wall-time；§4.5）。"""
    s = pd.to_datetime(series)
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_localize(None)
    return s


def _normalize_ohlcv(raw: pd.DataFrame) -> pd.DataFrame:
    """把 yfinance 形狀轉成 canonical OHLCV 並過 schema（純函式）。"""
    require(raw is not None and not raw.empty, "OHLCV 原始資料為空")
    df = raw.rename(columns=str.lower).reset_index()
    # index 名可能是 Date / Datetime / 其他 → 一律定名 date
    first = df.columns[0]
    if "date" not in df.columns:
        df = df.rename(columns={first: "date"})
    elif first.lower() != "date" and "date" not in [c.lower() for c in df.columns[1:]]:
        df = df.rename(columns={first: "date"})
    missing = [c for c in _OHLCV_COLS if c not in df.columns]
    require(not missing, f"OHLCV 缺欄位: {missing}")
    out = df[_OHLCV_COLS].copy()
    out["date"] = _to_naive_datetime(out["date"])
    out = out.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return validate_or_reject(out, OHLCVSchema, name="OHLCV")


def fetch_ohlcv(ticker: str, *, period: str = "2y", interval: str = "1d",
                auto_adjust: bool = True) -> pd.DataFrame:
    """抓 OHLCV。auto_adjust=True → 還原價（除權息連續）。"""
    import yfinance as yf

    require(bool(ticker), "ticker 不可為空")
    raw = yf.Ticker(ticker).history(period=period, interval=interval,
                                    auto_adjust=auto_adjust)
    df = _normalize_ohlcv(raw)
    require(not df.empty, f"{ticker} OHLCV 驗證後為空（來源異常或代碼錯誤）")
    stamp_df(df, source=f"yfinance:{ticker}")
    prov_log("fetch_ohlcv", source=f"yfinance:{ticker}",
             summary=f"{len(df)} rows adj={auto_adjust}", ticker=ticker)
    return df


def fetch_dividends(ticker: str) -> pd.Series:
    """配息事件（date→金額）。無配息回空 Series（非錯誤）。"""
    import yfinance as yf

    div = yf.Ticker(ticker).dividends
    if div is None or len(div) == 0:
        return pd.Series(dtype=float, name="dividend")
    div = div.copy()
    div.index = _to_naive_datetime(pd.Series(div.index)).values
    prov_log("fetch_dividends", source=f"yfinance:{ticker}",
             summary=f"{len(div)} events", ticker=ticker)
    return div


def build_valuation(dates: pd.Series, close: pd.Series, *,
                    eps_ttm: float | None, bvps: float | None) -> pd.DataFrame:
    """本益比/本淨比河流圖序列（純函式）。

    簡化模型（本益比河流圖標準作法）：固定 TTM EPS，PE 隨股價變動。
    EPS<=0 或缺 → PE 全 NaN（§1 不捏造）；BVPS 同理。
    """
    require(len(dates) == len(close), "dates 與 close 長度不一致")
    out = pd.DataFrame({"date": _to_naive_datetime(pd.Series(dates).reset_index(drop=True))})
    close = pd.Series(close).reset_index(drop=True).astype(float)
    nan_col = pd.Series([float("nan")] * len(close), dtype="float64")
    out["pe"] = (close / eps_ttm).round(4) if (eps_ttm and eps_ttm > 0) else nan_col
    out["pb"] = (close / bvps).round(4) if (bvps and bvps > 0) else nan_col.copy()
    return validate_or_reject(out, ValuationSchema, name="Valuation")


def fetch_valuation(ticker: str, ohlcv: pd.DataFrame) -> pd.DataFrame:
    """用 yfinance 基本面（trailingEps / bookValue）組估值序列。"""
    import yfinance as yf

    require(ohlcv is not None and not ohlcv.empty, "需要 OHLCV 才能組估值序列")
    info = yf.Ticker(ticker).get_info() or {}
    eps = info.get("trailingEps")
    bvps = info.get("bookValue")
    df = build_valuation(ohlcv["date"], ohlcv["close"], eps_ttm=eps, bvps=bvps)
    stamp_df(df, source=f"yfinance:{ticker}:info")
    prov_log("fetch_valuation", source=f"yfinance:{ticker}",
             summary=f"eps={eps} bvps={bvps}", ticker=ticker)
    return df
