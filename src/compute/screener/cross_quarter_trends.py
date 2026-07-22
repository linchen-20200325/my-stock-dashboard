"""src/compute/screener/cross_quarter_trends.py — 全台股跨季基本面趨勢(L2 純函式).

吃「全部季別」的全市場快照(long-form,每檔每季一列),對**比率型指標**做跨季線性
趨勢,揭露「逐季在變好還變壞」。比率對季節性較穩健(不像 QoQ 金額會被 Q1淡/Q4旺 汙染)。

⚠️ 資料限制(§1 誠實):現有快照僅 5 季(114Q1–115Q1)、無 113 前。故
  - 趨勢用「線性斜率」而非「連續成長季數」(後者 5 季 + QoQ 季節性會造假訊號)。
  - 營收 YoY 只算得出最新季 vs 去年同季一個點(無更早年可連續)。

4 個因子(方向語意寫死):
  - gross_margin_slope  毛利率 5 季斜率, > 0 為佳(獲利品質走揚)
  - op_margin_slope     營益率 5 季斜率, > 0 為佳(本業經營改善)
  - debt_ratio_slope    負債比 5 季斜率, < 0 為佳(逐季去槓桿)
  - revenue_yoy         最新季營收 vs 去年同季, > 0 為佳(規模成長)
favorable_count = 上述有資料的因子中「方向為佳」的個數;favorable_of = 有資料的因子數。

§1 / §3.3:斜率有效點 < CROSS_QUARTER_MIN_POINTS(SSOT)→ 回 NaN(不硬配);
  revenue ≤ 0 / total_assets ≤ 0 → 該比率 NaN(不 silent 0);缺去年同季 → yoy NaN。
§8.2:L2 純函式,零 I/O、零 streamlit。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from shared.cross_quarter_thresholds import CROSS_QUARTER_MIN_POINTS

REQUIRED_COLS = (
    "stock_id", "revenue", "gross_profit", "op_income",
    "total_assets", "total_liab", "roc_year", "season",
)

_OUT_COLS = [
    "stock_id", "n_quarters", "gross_margin_slope", "op_margin_slope",
    "debt_ratio_slope", "revenue_yoy", "favorable_count", "favorable_of",
]

_QUARTERS_PER_YEAR = 4   # YoY 回溯 4 季 = 去年同季;季序 ordinal 用


def _safe_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    """num/den;分母 ≤0 或 NaN → NaN(§4.4 guard,不 silent 0、不 inf)。"""
    return num / den.where(den > 0)


def _slope(t: np.ndarray, y: np.ndarray) -> float:
    """(t, y) 一次項最小平方斜率;非 NaN 點 < MIN → NaN。t 為季序(間距感知)。"""
    y = np.asarray(y, dtype=float)
    t = np.asarray(t, dtype=float)
    mask = ~np.isnan(y)
    if int(mask.sum()) < CROSS_QUARTER_MIN_POINTS:
        return float("nan")
    return float(np.polyfit(t[mask], y[mask], 1)[0])


def _revenue_yoy(qord: np.ndarray, revenue: np.ndarray) -> float:
    """最新季營收 vs 去年同季(qord−4);缺任一 / 去年同季 ≤0 → NaN。"""
    _by_q = {int(q): float(r) for q, r in zip(qord, revenue) if r == r}
    if not _by_q:
        return float("nan")
    _latest = max(_by_q)
    _cur = _by_q.get(_latest)
    _prev = _by_q.get(_latest - _QUARTERS_PER_YEAR)
    if _cur is None or _prev is None or not (_prev > 0):
        return float("nan")
    return _cur / _prev - 1.0


def compute_cross_quarter_trends(all_quarters: pd.DataFrame) -> pd.DataFrame:
    """全台股跨季趨勢因子(純函式,無 I/O)。

    Args:
        all_quarters: 全部季別全市場快照 long-form(每檔每季一列),須含 REQUIRED_COLS。

    Returns:
        DataFrame(每檔一列,依 favorable_count 由大到小、stock_id 次序),欄見 _OUT_COLS。
        空輸入 → 回空(帶完整欄位)。斜率/yoy 缺資料 → NaN(不猜)。
    """
    empty = pd.DataFrame(columns=_OUT_COLS)
    if all_quarters is None or all_quarters.empty:
        return empty
    missing = [c for c in REQUIRED_COLS if c not in all_quarters.columns]
    if missing:
        raise ValueError(f"cross_quarter_trends 缺必備欄:{missing}")

    df = all_quarters.copy()
    df["stock_id"] = df["stock_id"].astype(str).str.strip()
    for c in ("revenue", "gross_profit", "op_income", "total_assets", "total_liab",
              "roc_year", "season"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["roc_year", "season"])
    if df.empty:
        return empty

    # 季序 ordinal(間距感知,處理缺季);同檔同季去重(keep last = 最新補抓)
    df["_qord"] = (df["roc_year"] * _QUARTERS_PER_YEAR + (df["season"] - 1)).astype(int)
    df = df.drop_duplicates(subset=["stock_id", "_qord"], keep="last")

    df["_gm"] = _safe_ratio(df["gross_profit"], df["revenue"])
    df["_om"] = _safe_ratio(df["op_income"], df["revenue"])
    df["_debt"] = _safe_ratio(df["total_liab"], df["total_assets"])

    rows = []
    for sid, g in df.groupby("stock_id", sort=False):
        g = g.sort_values("_qord")
        _q = g["_qord"].to_numpy()
        _t = (_q - _q.min()).astype(float)          # 季序自 0 起(間距感知)
        _gm_s = _slope(_t, g["_gm"].to_numpy())
        _om_s = _slope(_t, g["_om"].to_numpy())
        _debt_s = _slope(_t, g["_debt"].to_numpy())
        _yoy = _revenue_yoy(_q, g["revenue"].to_numpy())
        # 方向為佳:毛利/營益率漲、負債比降、營收 YoY 正
        _checks = [(_gm_s, _gm_s > 0), (_om_s, _om_s > 0),
                   (_debt_s, _debt_s < 0), (_yoy, _yoy > 0)]
        _avail = [ok for v, ok in _checks if v == v]   # v==v 濾掉 NaN
        rows.append({
            "stock_id": sid,
            "n_quarters": int(len(g)),
            "gross_margin_slope": _gm_s,
            "op_margin_slope": _om_s,
            "debt_ratio_slope": _debt_s,
            "revenue_yoy": _yoy,
            "favorable_count": int(sum(bool(x) for x in _avail)),
            "favorable_of": int(len(_avail)),
        })

    out = pd.DataFrame(rows, columns=_OUT_COLS)
    return out.sort_values(
        ["favorable_count", "stock_id"], ascending=[False, True]
    ).reset_index(drop=True)
