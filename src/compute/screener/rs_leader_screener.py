"""src/compute/screener/rs_leader_screener.py — 抗跌 RS 選股純函式（L2）（v19.70）。

需求:大盤下跌時（例如 2020 疫情崩盤），排出「仍贏過大盤」的相對強弱前 50。

計分口徑（§4.1 單位陷阱：報酬用 %，RS 用 σ 標準差倍數）:
  個股區間報酬 r_i = close_i[t]/close_i[t−N] − 1
  大盤區間報酬 r_m = TWII[t]/TWII[t−N] − 1
  超額報酬      = r_i − r_m           ← 「贏過大盤」= 這個 > 0
  RS(σ標準化)  = (r_i − r_m) / σ_m    ← σ_m = 大盤日報酬標準差
排序鍵 = avg_rs（σ 標準化超額），降冪取前 N。

§8.2 L2 純函式:無 I/O、無 streamlit。σ 公式 **reuse** `v5_modules.calc_relative_strength`
（唯一 SSOT），本檔只負責:對齊個股/大盤交易日 + 分級標籤 + 排序取前 N。
§1 fail-loud:對齊後不足 / 缺 close → 標「資料不足」，不硬算、不補值。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from shared.rs_screen_thresholds import (
    RS_LEADER_TOP_N,
    RS_LEADER_VERSION,
    RS_MIN_ALIGNED_ROWS,
    RS_RANKABLE_TIERS,
    TIER_ICONS,
    TIER_INSUFFICIENT,
    TIER_LAG,
    TIER_LEAD,
    TIER_MILD,
    TIER_SYNC,
)
from shared.signal_thresholds import (
    RS_SIGMA_LAG_MAX,
    RS_SIGMA_LEAD_MIN,
    RS_SIGMA_MILD_MIN,
)
from src.compute.strategy.v5_modules import calc_relative_strength


@dataclass(frozen=True)
class RsLeaderScore:
    """單檔抗跌 RS 結果。avg_rs 為 σ 標準化超額報酬（排序鍵；資料不足時 None）。"""
    stock_id: str
    name: str
    avg_rs: float | None
    tier: str
    tier_icon: str
    stock_ret_pct: float | None     # 個股區間報酬 %
    market_ret_pct: float | None    # 大盤同期報酬 %
    excess_pct: float | None        # 超額 = 個股 − 大盤（>0 = 贏過大盤）
    beat_market: bool               # excess_pct > 0
    lookback: int
    version: str = RS_LEADER_VERSION

    @property
    def reason_text(self) -> str:
        if self.avg_rs is None:
            return f"對齊後有效交易日不足（需 ≥ {RS_MIN_ALIGNED_ROWS} 日）"
        _beat = "贏過大盤" if self.beat_market else "未贏過大盤"
        return (f"RS {self.avg_rs:+.2f}σ｜個股 {self.stock_ret_pct:+.1f}% vs "
                f"大盤 {self.market_ret_pct:+.1f}%（超額 {self.excess_pct:+.1f}%，{_beat}）")

    def to_row(self) -> dict:
        return {
            "代碼": self.stock_id,
            "名稱": self.name,
            "RS(σ)": self.avg_rs,
            "個股報酬%": self.stock_ret_pct,
            "大盤報酬%": self.market_ret_pct,
            "超額%": self.excess_pct,
            "贏過大盤": bool(self.beat_market),
            "訊號": f"{self.tier_icon} {self.tier}",
            "_tier": self.tier,
        }


def _classify(avg_rs: float | None) -> str:
    """avg_rs（σ）→ 分級標籤。門檻全來自 signal_thresholds SSOT（RS_SIGMA_*）。"""
    if avg_rs is None:
        return TIER_INSUFFICIENT
    if avg_rs >= RS_SIGMA_LEAD_MIN:
        return TIER_LEAD
    if avg_rs >= RS_SIGMA_MILD_MIN:
        return TIER_MILD
    if avg_rs >= RS_SIGMA_LAG_MAX:
        return TIER_SYNC
    return TIER_LAG


def _prep_close(df) -> pd.DataFrame | None:
    """任意來源 K 線 → 標準化成單欄 `close` + 日曆日 index（升冪、去重）。

    相容 yfinance（Close）/ 內部（close）大小寫；index normalize 到日期（與大盤對齊，
    同 VIX/3M 修正的教訓：日線用日曆日為鍵，不用含時分秒的原始 timestamp）。
    缺 close / 全空 → None（下游標資料不足）。
    """
    if df is None or len(df) == 0:
        return None
    _col = next((c for c in ("close", "Close", "CLOSE", "收盤價") if c in df.columns), None)
    if _col is None:
        return None
    out = df[[_col]].rename(columns={_col: "close"}).copy()
    try:
        _idx = pd.to_datetime(out.index)
        # tz 統一:yfinance 個股 K 線是 tz-aware(Asia/Taipei),fetch_yf_close 大盤是 tz-naive。
        # 不脫 tz → intersection 對不上(甚至報錯)。一律脫成 naive + normalize 到日曆日。
        if getattr(_idx, "tz", None) is not None:
            _idx = _idx.tz_localize(None)
        out.index = _idx.normalize()
    except Exception:
        return None
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["close"])
    return out if len(out) else None


def score_rs_leader(
    stock: dict,
    df_market: pd.DataFrame,
    *,
    lookback: int,
) -> RsLeaderScore:
    """單檔 → RsLeaderScore。

    Args:
        stock: {stock_id, name, df}（df 為個股 K 線，含 close/Close 欄 + 日期 index）
        df_market: 大盤 K 線（^TWII），同格式
        lookback: 區間交易日數（如 60）

    §1:個股/大盤對齊後共同交易日 < max(lookback, RS_MIN_ALIGNED_ROWS) → 資料不足。
    """
    sid = str(stock.get("stock_id", "")).strip()
    name = str(stock.get("name", "")).strip()

    def _insufficient() -> RsLeaderScore:
        return RsLeaderScore(
            stock_id=sid, name=name, avg_rs=None, tier=TIER_INSUFFICIENT,
            tier_icon=TIER_ICONS[TIER_INSUFFICIENT], stock_ret_pct=None,
            market_ret_pct=None, excess_pct=None, beat_market=False, lookback=lookback)

    ds = _prep_close(stock.get("df"))
    dm = _prep_close(df_market)
    if ds is None or dm is None:
        return _insufficient()

    # 對齊共同交易日（inner join）→ 保證 iloc[-N] 指向同一批日期
    _common = ds.index.intersection(dm.index)
    _need = max(int(lookback), RS_MIN_ALIGNED_ROWS)
    if len(_common) < _need:
        return _insufficient()
    ds_a = ds.loc[_common]
    dm_a = dm.loc[_common]

    # σ 公式 reuse calc_relative_strength（單一 lookback → avg = 該期值）
    rs = calc_relative_strength(ds_a, dm_a, periods=(int(lookback),))
    avg_rs = rs.get("avg_rs")
    if avg_rs is None:
        return _insufficient()

    s_ret = rs.get("avg_stock_ret")
    m_ret = rs.get("avg_market_ret")
    excess = round(s_ret - m_ret, 2) if (s_ret is not None and m_ret is not None) else None
    tier = _classify(avg_rs)
    return RsLeaderScore(
        stock_id=sid, name=name, avg_rs=avg_rs, tier=tier,
        tier_icon=TIER_ICONS[tier], stock_ret_pct=s_ret, market_ret_pct=m_ret,
        excess_pct=excess, beat_market=bool(excess is not None and excess > 0),
        lookback=lookback)


def rank_rs_leaders(
    stocks: list[dict],
    df_market: pd.DataFrame,
    *,
    lookback: int,
    top_n: int = RS_LEADER_TOP_N,
    beat_only: bool = False,
) -> list[RsLeaderScore]:
    """多檔 → 依 avg_rs 降冪排序取前 top_n（資料不足不列入排行）。

    Args:
        beat_only: True → 只留「贏過大盤」（excess>0）的；False → 全排（含落後，供對照）。
    """
    scored = [score_rs_leader(s, df_market, lookback=lookback) for s in stocks]
    rankable = [s for s in scored if s.tier in RS_RANKABLE_TIERS and s.avg_rs is not None]
    if beat_only:
        rankable = [s for s in rankable if s.beat_market]
    rankable.sort(key=lambda s: s.avg_rs, reverse=True)
    return rankable[:top_n]


def market_interval_return(df_market, lookback: int) -> float | None:
    """大盤自身區間報酬 %（給「此期間大盤漲/跌」情境橫幅用）。

    用與 calc_relative_strength 相同口徑 close[-1]/close[-lookback]−1，數字才對得上排行表。
    資料不足回 None（§1 不硬算）。
    """
    dm = _prep_close(df_market)
    if dm is None or len(dm) < int(lookback):
        return None
    return round((dm["close"].iloc[-1] / dm["close"].iloc[-int(lookback)] - 1) * 100, 2)


def to_rows(scores: list[RsLeaderScore]) -> list[dict]:
    return [s.to_row() for s in scores]


def count_insufficient(stocks: list[dict], df_market: pd.DataFrame, *, lookback: int) -> int:
    """診斷用:有幾檔因資料不足被排除（§5 可觀測性）。"""
    return sum(
        1 for s in stocks
        if score_rs_leader(s, df_market, lookback=lookback).tier == TIER_INSUFFICIENT
    )

