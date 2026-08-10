"""src/compute/sector_flow.py — 板塊資金泡泡圖彙總 L2 純函式(Stage 1)。

把「per-stock 每日三大法人淨買超(張)+ 收盤(元)+ 產業別」→ per-sector 每日 net
金額(億)→ 每板塊 {X, Y, size, quadrant} 泡泡座標。

§8.2 layer:L2 Compute — **純函式,零 I/O,不 import requests/proxy/streamlit/FinMind/
yfinance**。只吃 3 個 DataFrame/dict(inst 張長表、price 元長表、industry map),回
DataFrame。抓取由 L1 fetcher + `scripts/update_sector_flow.py`(entrypoint 編排)負責,
故本層可用合成資料完整單元測試。

§1 Fail Loud, Never Fake
------------------------
- 有法人淨額但**缺當日收盤**的股 → 該股該日剔除 + coverage 計數(不假設價、不 ffill)。
- 有淨額+收盤但**無產業別** → 歸 `SECTOR_UNCLASSIFIED` 桶 + 計數(不猜產業)。
- 「某板塊在某交易日無任何有效成分股」→ 該 (date,sector) 自然不存在;
  `compute_bubble` 在**已成交的交易日軸**上把缺格顯式補 0(代表該日該板塊 ~0 淨流入,
  非缺資料),並在回傳 meta 記錄補格數(§1「填補必須顯式 + log + 帶旗標」)。
  ⚠️ 整日全市場抓取失敗的情境由 cron 負責:全敗日**不寫入** parquet → 不會出現在交易日軸,
  故本層看到的每個交易日都是「市場有成交且有資料」的日子。
- 交易日數 < `WINDOW_Y_MIN_DAYS`(動能兩段窗)→ Y=NaN、quadrant=`資料不足`,不硬編 0。

§4.1 單位陷阱:張→股 ×SHARES_PER_LOT、元→億 ÷YUAN_PER_YI,全走 SSOT 常數。
§4.5 交易日 ≠ 日曆日:所有視窗建在「輸入資料實際出現的交易日」軸上,非日曆日差分。
§5 效能:全向量化(merge / groupby / pivot),無逐列 Python 迴圈。

輸入 schema
-----------
inst_df   : DataFrame[date, stock_id, foreign_lots, trust_lots, dealer_lots]  # 單位 張
price_df  : DataFrame[date, stock_id, close]                                   # 單位 元/股
industry_map : dict[str stock_id -> str sector]
"""
from __future__ import annotations

import logging as _log
from typing import Optional

import pandas as pd

from shared.sector_flow_thresholds import (
    QUADRANT_EBBING,
    QUADRANT_INSUFFICIENT,
    QUADRANT_RISING,
    QUADRANT_ROTATING,
    QUADRANT_WATCHING,
    SECTOR_UNCLASSIFIED,
    SHARES_PER_LOT,
    WINDOW_SIZE,
    WINDOW_X,
    WINDOW_Y_MIN_DAYS,
    WINDOW_Y_PRIOR,
    WINDOW_Y_RECENT,
    YUAN_PER_YI,
)

_logger = _log.getLogger(__name__)

# per-stock 三大法人分項欄(張)。與 cron 對應:外資→foreign_lots 等。
_LOT_COLS = ("foreign_lots", "trust_lots", "dealer_lots")
# per-sector 分項金額欄(億)↔ 三大法人分項。
_CAMP_YI = {
    "foreign_lots": "foreign_yi",
    "trust_lots": "trust_yi",
    "dealer_lots": "dealer_yi",
}


def _norm_dates(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    """把 date 欄正規化為 datetime64[ns](去時分秒),避免 str/date/Timestamp 混型 join 漏配。"""
    out = df.copy()
    out[col] = pd.to_datetime(out[col], errors="coerce").dt.normalize()
    return out


def classify_quadrant(x: Optional[float], y: Optional[float]) -> str:
    """由 (X, Y) 判象限。y 為 None/NaN(動能不可算)→ `資料不足`。

    邊界慣例(見 sector_flow_thresholds):x>=0 為右半、y>=0 為上半。
    """
    if y is None or (isinstance(y, float) and pd.isna(y)):
        return QUADRANT_INSUFFICIENT
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return QUADRANT_INSUFFICIENT
    right = x >= 0
    up = y >= 0
    if right and up:
        return QUADRANT_RISING
    if right and not up:
        return QUADRANT_ROTATING
    if (not right) and (not up):
        return QUADRANT_EBBING
    return QUADRANT_WATCHING


def compute_sector_daily_net(
    inst_df: pd.DataFrame,
    price_df: pd.DataFrame,
    industry_map: dict,
    *,
    unclassified_label: str = SECTOR_UNCLASSIFIED,
) -> tuple[pd.DataFrame, dict]:
    """per-stock 每日淨買超(張)× 收盤(元)× 產業 → per-sector 每日 net 金額(億)。

    Returns
    -------
    (sector_daily, coverage)
        sector_daily : DataFrame[date, sector, net_amt_yi, foreign_yi, trust_yi,
                                 dealer_yi, n_stocks],按 date, sector 排序。
        coverage     : dict — n_stock_days_with_net / n_dropped_missing_price /
                       n_unclassified_stock_days / n_sectors / n_days。
    """
    cov = {
        "n_stock_days_with_net": 0,
        "n_dropped_missing_price": 0,
        "n_unclassified_stock_days": 0,
        "n_sectors": 0,
        "n_days": 0,
    }
    empty_cols = ["date", "sector", "net_amt_yi", "foreign_yi", "trust_yi",
                  "dealer_yi", "n_stocks"]
    if inst_df is None or inst_df.empty:
        _logger.warning("[sector_flow] inst_df 為空 → 回空 sector_daily")
        return pd.DataFrame(columns=empty_cols), cov

    inst = _norm_dates(inst_df)
    inst["stock_id"] = inst["stock_id"].astype(str).str.strip()
    for c in _LOT_COLS:
        if c not in inst.columns:
            inst[c] = 0.0
        inst[c] = pd.to_numeric(inst[c], errors="coerce").fillna(0.0)
    # 保留所有 (date,stock) 列(含全 0 淨額:不影響加總、計入 coverage 分母);
    # 僅剔除 date 無法解析(NaT)的髒列。§1:不靜默丟真實資料。
    inst = inst[["date", "stock_id", *_LOT_COLS]].dropna(subset=["date"])
    cov["n_stock_days_with_net"] = int(len(inst))

    if price_df is None or price_df.empty:
        _logger.warning("[sector_flow] price_df 為空 → 全部缺價,無法換算金額(§1 不造假)")
        cov["n_dropped_missing_price"] = int(len(inst))
        return pd.DataFrame(columns=empty_cols), cov

    price = _norm_dates(price_df)
    price["stock_id"] = price["stock_id"].astype(str).str.strip()
    price["close"] = pd.to_numeric(price["close"], errors="coerce")
    price = price.dropna(subset=["date", "close"])
    # §3.2 收盤價須為正(元/股);非正值視為髒資料剔除
    price = price[price["close"] > 0][["date", "stock_id", "close"]]

    # inner join:同時有淨額 + 有效收盤才算(§1:缺價的股該日剔除,不補值)
    merged = inst.merge(price, on=["date", "stock_id"], how="inner")
    cov["n_dropped_missing_price"] = int(len(inst) - len(merged))
    if cov["n_dropped_missing_price"] > 0:
        _logger.info("[sector_flow] 顯式剔除 %d 個 (股,日):有法人淨額但缺當日收盤",
                     cov["n_dropped_missing_price"])
    if merged.empty:
        _logger.warning("[sector_flow] 法人淨額與收盤 join 後為空")
        return pd.DataFrame(columns=empty_cols), cov

    # ── §4.1 張 → 金額(億)。各分項獨立換算,合計 = 三分項之和(避免重複加主力合計)──
    # net_amt_yuan = lots × SHARES_PER_LOT × close ; net_amt_yi = /YUAN_PER_YI
    _scale = SHARES_PER_LOT / YUAN_PER_YI   # 張×元 → 億 的合併係數
    for c in _LOT_COLS:
        merged[_CAMP_YI[c]] = merged[c] * merged["close"] * _scale
    merged["net_amt_yi"] = merged[[_CAMP_YI[c] for c in _LOT_COLS]].sum(axis=1)

    # ── 產業別對映(§4.6 無產業 → 未分類桶,不猜)────────────────────────
    _imap = {str(k).strip(): (str(v).strip() if v is not None and str(v).strip()
                              else unclassified_label)
             for k, v in (industry_map or {}).items()}
    merged["sector"] = merged["stock_id"].map(_imap).fillna(unclassified_label)
    cov["n_unclassified_stock_days"] = int(
        (merged["sector"] == unclassified_label).sum())
    if cov["n_unclassified_stock_days"] > 0:
        _logger.info("[sector_flow] %d 個 (股,日) 無產業別 → 歸「%s」桶",
                     cov["n_unclassified_stock_days"], unclassified_label)

    # ── groupby (date, sector) 加總(向量化)──────────────────────────────
    agg = merged.groupby(["date", "sector"], as_index=False).agg(
        net_amt_yi=("net_amt_yi", "sum"),
        foreign_yi=("foreign_yi", "sum"),
        trust_yi=("trust_yi", "sum"),
        dealer_yi=("dealer_yi", "sum"),
        n_stocks=("stock_id", "nunique"),
    )
    agg = agg.sort_values(["date", "sector"]).reset_index(drop=True)
    cov["n_sectors"] = int(agg["sector"].nunique())
    cov["n_days"] = int(agg["date"].nunique())
    return agg, cov


def compute_bubble(
    sector_daily: pd.DataFrame,
    *,
    window_x: int = WINDOW_X,
    window_y_recent: int = WINDOW_Y_RECENT,
    window_y_prior: int = WINDOW_Y_PRIOR,
    window_size: int = WINDOW_SIZE,
) -> tuple[pd.DataFrame, dict]:
    """從 per-sector 每日 net 金額序列算每板塊 {X, Y, size, quadrant}。

    定義(令某板塊近 N 交易日日序列 d[1]=最近日 … d[N]):
        X    = Σ_{i=1..window_x} net_amt_yi[i]                              (億)
        Y    = mean_{i=1..R} net_amt_yi[i] − mean_{i=R+1..R+P} net_amt_yi[i](億/天)
               R=window_y_recent, P=window_y_prior
        size = | Σ_{i=1..window_size} net_amt_yi[i] |                        (億)

    Returns
    -------
    (bubble, meta)
        bubble : DataFrame[sector, x_yi, y_yi, size_yi, quadrant, n_days,
                           insufficient]。
        meta   : dict — n_trading_days_used / n_filled_absent_cells / n_sectors。
    """
    meta = {"n_trading_days_used": 0, "n_filled_absent_cells": 0, "n_sectors": 0}
    out_cols = ["sector", "x_yi", "y_yi", "size_yi", "quadrant", "n_days",
                "insufficient"]
    if sector_daily is None or sector_daily.empty:
        _logger.warning("[sector_flow] sector_daily 為空 → 回空 bubble")
        return pd.DataFrame(columns=out_cols), meta

    sd = _norm_dates(sector_daily)
    # 交易日軸 = 輸入實際出現的交易日(cron 已保證全敗日不入檔),取最近 window_size 天。
    all_dates = sorted(sd["date"].dropna().unique())
    recent_dates = all_dates[-int(window_size):]
    meta["n_trading_days_used"] = len(recent_dates)

    sd = sd[sd["date"].isin(recent_dates)]
    # pivot 成 sector × date(元格 = 該板塊該日 net_amt_yi)
    pv = sd.pivot_table(index="sector", columns="date", values="net_amt_yi",
                        aggfunc="sum")
    # 補齊缺格:某板塊在「有成交的交易日」缺席 = 該日 ~0 淨流入(顯式補 0 + 計數,§1)
    pv = pv.reindex(columns=recent_dates)
    meta["n_filled_absent_cells"] = int(pv.isna().sum().sum())
    if meta["n_filled_absent_cells"] > 0:
        _logger.info("[sector_flow] 交易日軸上顯式補 0 共 %d 格"
                     "(板塊當日無有效成分股 = 0 億淨流入,非缺資料)",
                     meta["n_filled_absent_cells"])
    pv = pv.fillna(0.0)
    # 欄(date)由舊到新排序,方便用「尾端 = 最近」切窗
    pv = pv.reindex(columns=sorted(pv.columns))

    n_days = pv.shape[1]
    rows = []
    for sector, ser in pv.iterrows():
        vals = ser.to_numpy(dtype="float64")   # 由舊到新
        # X:近 window_x 交易日總和(不足則用現有,仍為總和語意)
        x_yi = float(vals[-int(window_x):].sum()) if n_days else 0.0
        # size:近 window_size 交易日淨額絕對值(pv 已只留 window_size 天)
        size_yi = float(abs(vals.sum())) if n_days else 0.0
        # Y:需近段 R + 前段 P 完整交易日(§1:不足不硬編 0,標資料不足)
        if n_days >= int(window_y_recent) + int(window_y_prior):
            recent = vals[-int(window_y_recent):]
            prior = vals[-(int(window_y_recent) + int(window_y_prior)):
                         -int(window_y_recent)]
            y_yi = float(recent.mean() - prior.mean())
            insufficient = False
        else:
            y_yi = float("nan")
            insufficient = True
        rows.append({
            "sector": sector,
            "x_yi": x_yi,
            "y_yi": y_yi,
            "size_yi": size_yi,
            "quadrant": classify_quadrant(x_yi, y_yi),
            "n_days": int(n_days),
            "insufficient": bool(insufficient),
        })

    bubble = pd.DataFrame(rows, columns=out_cols)
    bubble = bubble.sort_values("size_yi", ascending=False).reset_index(drop=True)
    meta["n_sectors"] = int(len(bubble))
    return bubble, meta


def map_tickers_to_sectors(
    tickers,
    industry_map: dict,
    *,
    unclassified_label: str = SECTOR_UNCLASSIFIED,
) -> dict:
    """把持股 tickers 對映到板塊(供 Stage 2 在泡泡圖上標點)。

    無產業別 → `未分類`(§4.6 不猜)。回 {ticker: sector},保留輸入順序、去重。
    """
    _imap = {str(k).strip(): (str(v).strip() if v is not None and str(v).strip()
                              else unclassified_label)
             for k, v in (industry_map or {}).items()}
    out: dict = {}
    for t in tickers or []:
        key = str(t).strip()
        if not key or key in out:
            continue
        out[key] = _imap.get(key, unclassified_label)
    return out
