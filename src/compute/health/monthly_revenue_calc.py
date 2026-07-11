"""src/compute/health/monthly_revenue_calc.py — 月營收趨勢計算 L2 純函式(v18.400 U1).

從 `src/ui/tabs/monthly_revenue_screener.py` 抽出 compute 層(原 L2 邏輯誤放 L5),
配合 U1 修反向違憲(原 `src/compute/health/mj_trend_score.py:250` 反向 import L5)。

§8.2 layer:L2 Compute — 純函式,無 I/O,無 Streamlit。

對外 API:
- `compute_yoy_mom(df_stock) -> dict`:單股 YoY (近 3 月) + MoM (末月)
- `classify_trend(stats, yoy_threshold=15.0) -> str`:5 段趨勢分類
- `screen_from_batch(df_batch, yoy_threshold, name_map) -> pd.DataFrame`:批次分組計算
- `filter_by_mode(df_result, mode) -> pd.DataFrame`:依模式過濾
- `TREND_LABELS`:5 段趨勢中文 label SSOT
"""
from __future__ import annotations

from typing import Any

import pandas as pd

# 趨勢分類 → 中文 label SSOT
TREND_LABELS = {
    "strong_up": "🚀 強進步",
    "up": "📈 進步",
    "strong_down": "🔻 強退步",
    "down": "📉 退步",
    "neutral": "➖ 中性",
    "insufficient": "⚪ 資料不足",
}


def compute_yoy_mom(df_stock: pd.DataFrame) -> dict[str, Any]:
    """對單股月營收序列計算近 3 月 YoY + 末月 MoM。

    Args:
        df_stock: DataFrame with [date, revenue],按 date 升冪排序

    Returns:
        dict: {
          'last_date': pd.Timestamp | None,
          'last_revenue': float | None,
          'yoy_last3': list[float | None] — [M-2, M-1, M] 的 YoY%(缺基期為 None),
          'mom_last': float | None — 末月 MoM%,
          'months_available': int,
        }
    """
    if df_stock is None or df_stock.empty or "revenue" not in df_stock.columns:
        return {"last_date": None, "last_revenue": None, "yoy_last3": [],
                "mom_last": None, "months_available": 0}
    _df = df_stock.copy()
    if "date" in _df.columns:
        _df = _df.sort_values("date").reset_index(drop=True)
    _rev = pd.to_numeric(_df["revenue"], errors="coerce").tolist()
    _dates = _df["date"].tolist() if "date" in _df.columns else [None] * len(_rev)
    _n = len(_rev)
    if _n == 0 or _rev[-1] is None:
        return {"last_date": None, "last_revenue": None, "yoy_last3": [],
                "mom_last": None, "months_available": 0}

    # YoY: 末 3 月相對「去年同月」
    # v19.83(第六份 review 3-9):原位置索引 _idx_curr-12 假設序列連續無缺月 —
    # 缺月(新上市/暫停公布/來源缺洞,§4.6 月營收三態)時基期錯位(拿去年 M+1 月
    # 當同月基期),YoY 靜默失真。改 (年-1, 同月) 日曆查表;date 欄缺/含 NaT 時
    # 退回位置索引(舊行為,連續序列兩法結果相同)。
    _has_dates = "date" in _df.columns and _df["date"].notna().all() and _n > 0
    _ym = None
    if _has_dates:
        try:
            _ym = pd.to_datetime(_df["date"])
        except (ValueError, TypeError):
            _has_dates = False
    _rev_by_ym: dict[tuple[int, int], float] = {}
    if _has_dates:
        for _y_, _m_, _r_ in zip(_ym.dt.year, _ym.dt.month, _rev):
            if _r_ is not None and not pd.isna(_r_):
                _rev_by_ym[(int(_y_), int(_m_))] = float(_r_)
    _yoy_last3: list[float | None] = []
    for _off in (2, 1, 0):  # M-2, M-1, M(時序)
        _idx_curr = _n - 1 - _off
        if _idx_curr < 0:
            _yoy_last3.append(None)
            continue
        _curr = _rev[_idx_curr]
        if _has_dates:
            _ts_c = _ym.iloc[_idx_curr]
            _base = _rev_by_ym.get((int(_ts_c.year) - 1, int(_ts_c.month)))
        else:
            _idx_base = _idx_curr - 12
            _base = _rev[_idx_base] if _idx_base >= 0 else None
        if (_curr is None or pd.isna(_curr) or _base is None
                or pd.isna(_base) or _base == 0):
            _yoy_last3.append(None)
            continue
        _yoy_last3.append((_curr / _base - 1.0) * 100.0)

    # MoM: 末月 vs 上月
    _mom: float | None = None
    if _n >= 2 and _rev[-1] is not None and _rev[-2] is not None and _rev[-2] != 0:
        _mom = (_rev[-1] / _rev[-2] - 1.0) * 100.0

    return {
        "last_date": _dates[-1],
        "last_revenue": float(_rev[-1]) if _rev[-1] is not None else None,
        "yoy_last3": _yoy_last3,
        "mom_last": _mom,
        "months_available": _n,
    }


def classify_trend(stats: dict[str, Any], yoy_threshold: float = 15.0) -> str:
    """根據 YoY + MoM 雙條件分類趨勢。

    Args:
        stats: compute_yoy_mom() 回傳 dict
        yoy_threshold: 強進步/強退步門檻 %,預設 15.0

    Returns:
        'strong_up' / 'up' / 'strong_down' / 'down' / 'neutral' / 'insufficient'
    """
    _yoy3 = stats.get("yoy_last3") or []
    _mom = stats.get("mom_last")

    # 資料完整性檢查:需要 3 個 YoY + 1 個 MoM 全部非 None
    if len(_yoy3) < 3 or any(y is None for y in _yoy3) or _mom is None:
        return "insufficient"

    _all_strong_up = all(y >= yoy_threshold for y in _yoy3)
    _all_up = all(y > 0 for y in _yoy3)
    _all_strong_down = all(y <= -yoy_threshold for y in _yoy3)
    _all_down = all(y < 0 for y in _yoy3)

    if _all_strong_up and _mom >= 0:
        return "strong_up"
    if _all_strong_down and _mom <= 0:
        return "strong_down"
    if _all_up and _mom >= 0:
        return "up"
    if _all_down and _mom <= 0:
        return "down"
    return "neutral"


def _yoy_round(yoy_list: list[float | None], idx: int) -> float | None:
    """安全 round 第 idx 個 YoY 值,缺值或越界回 None。"""
    if len(yoy_list) <= idx:
        return None
    _v = yoy_list[idx]
    return round(_v, 2) if _v is not None else None


def screen_from_batch(
    df_batch: pd.DataFrame,
    yoy_threshold: float = 15.0,
    name_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """從 batch fetch 結果分組計算每股趨勢。

    Args:
        df_batch: fetch_batch_monthly_revenue() 結果(含 stock_id / date / revenue)
        yoy_threshold: 強進步/強退步門檻 %
        name_map: 可選 {sid: name} 對照(來自 TWSE BWIBBU_d)

    Returns:
        DataFrame: 代碼 / 名稱 / 末月日期 / 末月營收(億) / YoY-2 / YoY-1 / YoY / MoM / 趨勢
    """
    if df_batch is None or df_batch.empty:
        return pd.DataFrame()
    _rows = []
    _name_map = name_map or {}
    for _sid, _grp in df_batch.groupby("stock_id"):
        _stats = compute_yoy_mom(_grp)
        _trend = classify_trend(_stats, yoy_threshold=yoy_threshold)
        _rows.append({
            "代碼": _sid,
            "名稱": _name_map.get(str(_sid), ""),
            "末月日期": _stats["last_date"].strftime("%Y-%m") if _stats["last_date"] is not None else "",
            "末月營收(億)": (round(_stats["last_revenue"] / 1e8, 2)
                          if _stats["last_revenue"] is not None else None),
            "YoY-2(%)": _yoy_round(_stats["yoy_last3"], 0),
            "YoY-1(%)": _yoy_round(_stats["yoy_last3"], 1),
            "YoY(%)":   _yoy_round(_stats["yoy_last3"], 2),
            "MoM(%)":   round(_stats["mom_last"], 2) if _stats["mom_last"] is not None else None,
            "趨勢":     TREND_LABELS.get(_trend, _trend),
            "_trend_key": _trend,
        })
    return pd.DataFrame(_rows)


def filter_by_mode(df_result: pd.DataFrame, mode: str) -> pd.DataFrame:
    """依模式過濾 screen_from_batch 結果。

    Args:
        df_result: screen_from_batch 輸出(含 _trend_key 欄)
        mode: 'all' / 'up' / 'strong_up' / 'down' / 'strong_down' / 'any_up' / 'any_down'

    Returns:
        過濾後 DataFrame(保留 _trend_key 供下游用)
    """
    if df_result is None or df_result.empty or mode == "all":
        return df_result
    if "_trend_key" not in df_result.columns:
        return df_result
    if mode == "any_up":
        return df_result[df_result["_trend_key"].isin(["up", "strong_up"])].reset_index(drop=True)
    if mode == "any_down":
        return df_result[df_result["_trend_key"].isin(["down", "strong_down"])].reset_index(drop=True)
    return df_result[df_result["_trend_key"] == mode].reset_index(drop=True)
