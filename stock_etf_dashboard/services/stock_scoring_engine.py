"""L2 Service — 個股量化評分（估值河流圖 + 均線 + MACD + 籌碼）。

純函式,無 I/O。輸入已驗證的 DataFrame,輸出評分 dataclass。
所有門檻自 L0 constants 引入（§3.3）；浮點比較用容差（§4.3）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from ..core import constants as C
from ..core.circuit_breaker import (ConfidenceReport, compute_confidence,
                                    freshness_score, isclose, require)


# ── 估值河流圖位階 ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class ValuationPosition:
    metric: str                  # "pe" / "pb"
    value: float
    percentile: float            # 0~1（在歷史分布的位階,0=最便宜）
    zone: str                    # 便宜區 / 合理區 / 昂貴區
    bands: dict                  # {0.2:.., 0.4:.., 0.6:.., 0.8:..} 河流圖分帶
    n_samples: int
    sufficient: bool             # 樣本是否足夠可信


def valuation_position(valuation_df: pd.DataFrame, *, metric: str = "pe") -> ValuationPosition:
    """本益比/本淨比河流圖位階：當前值在歷史分布的百分位 → 便宜/合理/昂貴。"""
    require(metric in ("pe", "pb"), f"metric 需為 pe/pb,得到 {metric}")
    require(metric in valuation_df.columns, f"估值資料缺 {metric} 欄")
    vals = pd.to_numeric(valuation_df[metric], errors="coerce").dropna()
    require(len(vals) >= 1, f"{metric} 無有效樣本（EPS/BVPS<=0 或無資料）")

    current = float(vals.iloc[-1])
    percentile = float((vals <= current).mean())
    if percentile <= C.VALUATION_CHEAP_PCTL:
        zone = "便宜區"
    elif percentile >= C.VALUATION_EXPENSIVE_PCTL:
        zone = "昂貴區"
    else:
        zone = "合理區"
    bands = {q: round(float(vals.quantile(q)), 4) for q in C.RIVER_BAND_PCTLS}
    n = int(len(vals))
    return ValuationPosition(
        metric=metric, value=round(current, 4), percentile=round(percentile, 4),
        zone=zone, bands=bands, n_samples=n,
        sufficient=n >= C.VALUATION_MIN_SAMPLES,
    )


# ── 技術面：均線排列 + MACD ─────────────────────────────────────────────
def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


@dataclass(frozen=True)
class TrendState:
    close: float
    ma_short: float | None
    ma_mid: float | None
    ma_bullish: bool             # MA20 > MA60 多頭排列
    above_ma_short: bool         # 收盤 > MA20
    macd_dif: float | None
    macd_signal: float | None
    macd_hist: float | None
    macd_bullish: bool           # hist > 0
    label: str                   # 多頭排列 / 空頭排列 / 盤整


def trend_state(ohlcv: pd.DataFrame) -> TrendState:
    """均線多空排列 + MACD 柱狀。資料不足時對應欄位為 None（不腦補）。"""
    require("close" in ohlcv.columns, "OHLCV 缺 close")
    close = pd.to_numeric(ohlcv["close"], errors="coerce").dropna().reset_index(drop=True)
    require(len(close) >= 1, "close 無有效樣本")
    last = float(close.iloc[-1])

    ma_s = float(close.rolling(C.MA_SHORT_DAYS).mean().iloc[-1]) if len(close) >= C.MA_SHORT_DAYS else None
    ma_m = float(close.rolling(C.MA_MID_DAYS).mean().iloc[-1]) if len(close) >= C.MA_MID_DAYS else None

    dif = sig = hist = None
    if len(close) >= C.MACD_SLOW_DAYS:
        dif_s = _ema(close, C.MACD_FAST_DAYS) - _ema(close, C.MACD_SLOW_DAYS)
        sig_s = _ema(dif_s, C.MACD_SIGNAL_DAYS)
        dif, sig = float(dif_s.iloc[-1]), float(sig_s.iloc[-1])
        hist = dif - sig

    ma_bull = (ma_s is not None and ma_m is not None and ma_s > ma_m)
    above_s = (ma_s is not None and last > ma_s)
    macd_bull = (hist is not None and hist > 0)

    if ma_bull and above_s:
        label = "多頭排列"
    elif (ma_s is not None and ma_m is not None and ma_s < ma_m and not above_s):
        label = "空頭排列"
    else:
        label = "盤整"

    return TrendState(
        close=round(last, 4),
        ma_short=None if ma_s is None else round(ma_s, 4),
        ma_mid=None if ma_m is None else round(ma_m, 4),
        ma_bullish=ma_bull, above_ma_short=above_s,
        macd_dif=None if dif is None else round(dif, 4),
        macd_signal=None if sig is None else round(sig, 4),
        macd_hist=None if hist is None else round(hist, 4),
        macd_bullish=macd_bull, label=label,
    )


# ── 籌碼面：外資/投信同步買超 ───────────────────────────────────────────
@dataclass(frozen=True)
class ChipState:
    foreign_net: float           # 近 N 日加總（張）
    trust_net: float
    sync_buy: bool               # 兩者同步買超
    sync_sell: bool              # 兩者同步賣超
    label: str


def chip_state(chip_df: pd.DataFrame, *, lookback: int = C.CHIP_SYNC_LOOKBACK_DAYS) -> ChipState:
    """近 N 日外資/投信淨買賣超加總,判斷同步買/賣超。"""
    require({"foreign_net", "trust_net"}.issubset(chip_df.columns), "籌碼資料缺欄位")
    tail = chip_df.tail(lookback)
    f = float(pd.to_numeric(tail["foreign_net"], errors="coerce").sum())
    t = float(pd.to_numeric(tail["trust_net"], errors="coerce").sum())
    sync_buy = f > 0 and t > 0
    sync_sell = f < 0 and t < 0
    if sync_buy:
        label = "外資投信同步買超"
    elif sync_sell:
        label = "外資投信同步賣超"
    elif isclose(f, 0.0) and isclose(t, 0.0):
        label = "籌碼中性"
    else:
        label = "分歧"
    return ChipState(foreign_net=round(f, 2), trust_net=round(t, 2),
                     sync_buy=sync_buy, sync_sell=sync_sell, label=label)


# ── 綜合評分 ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class StockScore:
    ticker: str
    valuation_score: float       # 0~100（越便宜越高）
    trend_score: float
    chip_score: float
    total_score: float           # 加權 0~100
    valuation: ValuationPosition | None
    trend: TrendState
    chip: ChipState
    confidence: ConfidenceReport
    verdict: str
    details: dict = field(default_factory=dict)


def _valuation_subscore(vp: ValuationPosition | None) -> float:
    if vp is None:
        return 50.0                      # 無估值 → 中性,不獎不罰
    return round((1.0 - vp.percentile) * 100.0, 1)   # 越便宜分越高


def _trend_subscore(ts: TrendState) -> float:
    hits = sum([ts.ma_bullish, ts.above_ma_short, ts.macd_bullish])
    return round(hits / 3.0 * 100.0, 1)


def _chip_subscore(cs: ChipState) -> float:
    if cs.sync_buy:
        return 100.0
    if cs.sync_sell:
        return 20.0
    if isclose(cs.foreign_net, 0.0) and isclose(cs.trust_net, 0.0):
        return 50.0
    return 65.0 if (cs.foreign_net > 0 or cs.trust_net > 0) else 35.0


def score_stock(
    ticker: str,
    ohlcv: pd.DataFrame,
    *,
    valuation: pd.DataFrame | None = None,
    chip: pd.DataFrame | None = None,
    metric: str = "pe",
    as_of: date | None = None,
    is_proxy: bool = False,
) -> StockScore:
    """整合估值/技術/籌碼 → 0~100 綜合分 + 置信度。"""
    require(sum([C.SCORE_WEIGHT_VALUATION, C.SCORE_WEIGHT_TREND, C.SCORE_WEIGHT_CHIP]) == 1.0
            or isclose(C.SCORE_WEIGHT_VALUATION + C.SCORE_WEIGHT_TREND + C.SCORE_WEIGHT_CHIP, 1.0),
            "評分權重和必須為 1.0")
    require(ohlcv is not None and not ohlcv.empty, f"{ticker} 缺 OHLCV,無法評分")

    vp = None
    if valuation is not None and not valuation.empty:
        try:
            vp = valuation_position(valuation, metric=metric)
        except Exception:  # 估值缺樣本 → 視為無估值,不中斷
            vp = None
    ts = trend_state(ohlcv)
    cs = (chip_state(chip) if (chip is not None and not chip.empty)
          else ChipState(0.0, 0.0, False, False, "無籌碼資料"))

    v_s, t_s, c_s = _valuation_subscore(vp), _trend_subscore(ts), _chip_subscore(cs)
    total = round(
        C.SCORE_WEIGHT_VALUATION * v_s
        + C.SCORE_WEIGHT_TREND * t_s
        + C.SCORE_WEIGHT_CHIP * c_s, 1)

    # 置信度：三資料塊齊全度 + 新鮮度 + 來源
    blocks_present = 1 + int(vp is not None) + int(chip is not None and not chip.empty)
    completeness = blocks_present / 3.0
    if vp is not None and not vp.sufficient:
        completeness *= 0.85             # 估值樣本不足再打折
    ref = as_of or date.today()
    last_date = pd.to_datetime(ohlcv["date"]).max().date()
    fresh = freshness_score((ref - last_date).days)
    conf = compute_confidence(completeness=completeness, freshness=fresh,
                              source_reliability=0.7 if is_proxy else 1.0)

    if conf.is_locked:
        verdict = f"🔒 置信度 {conf.score:.0f} 不足（{conf.reason}）— 僅顯示數據,不給操作建議"
    elif total >= 70:
        verdict = f"偏多：{ts.label}／{cs.label}／估值{vp.zone if vp else 'N/A'}"
    elif total <= 40:
        verdict = f"偏空：{ts.label}／{cs.label}／估值{vp.zone if vp else 'N/A'}"
    else:
        verdict = f"中性：{ts.label}／{cs.label}／估值{vp.zone if vp else 'N/A'}"

    return StockScore(
        ticker=ticker, valuation_score=v_s, trend_score=t_s, chip_score=c_s,
        total_score=total, valuation=vp, trend=ts, chip=cs, confidence=conf,
        verdict=verdict,
        details={"weights": {"valuation": C.SCORE_WEIGHT_VALUATION,
                             "trend": C.SCORE_WEIGHT_TREND,
                             "chip": C.SCORE_WEIGHT_CHIP}},
    )
