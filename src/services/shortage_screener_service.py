"""src/services/shortage_screener_service.py — 缺貨 / 供不應求選股 L3 編排（v19.65）。

兩段式全市場掃描（誠實揭露：為避免撞 FinMind 速限，先用便宜的全市場月營收動能圈候選池，
再深掃候選池的合約負債/毛利/存貨——找的是「營收正在成長 + 出現缺貨財務特徵」的股票）：

  ① L1 fetch_batch_monthly_revenue（1 次 FinMind 全市場呼叫）
       → L2 compute_yoy_mom / classify_trend → 圈「營收動能向上」候選池（依末月 YoY 排序）
  ② 候選池（上限 SHORTAGE_DEEP_SCAN_MAX=50）逐檔
       → L1 fetch_quarterly_shortage_frame（合約負債/毛利/存貨季序列）
  ③ 組 L2 input → shortage_screener.rank_shortage 四訊號計分排序 → rows + meta

§8.2 L3 service:合法組合 L1 fetcher + L2 純函式（對齊 fundamental_screener_service /
etf_sector_service pattern）。快取集中在此（TTL_1DAY，季度資料日級足夠）。
§1 fail-loud:月營收無資料 / token 缺 → 回空 + note，不炸整頁、不造假。
"""
from __future__ import annotations

# §8.2.A EX-CACHE-1：條件 import streamlit，僅 @st.cache_data，無真 UI 呼叫。
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

import pandas as pd

from shared.shortage_screen_thresholds import SHORTAGE_DEEP_SCAN_MAX, SHORTAGE_VERSION
from shared.ttls import TTL_1DAY
from src.compute.health.monthly_revenue_calc import classify_trend, compute_yoy_mom
from src.compute.screener.shortage_screener import rank_shortage, to_rows
from src.data.stock.monthly_revenue_fetcher import fetch_batch_monthly_revenue
from src.data.stock.quarterly_financials_fetcher import fetch_quarterly_shortage_frame


def _clear(fn) -> None:
    clear = getattr(fn, "clear", None)
    if callable(clear):
        clear()


def _is_finance(stock_id: str) -> bool:
    """台股金融族群常見代碼前綴（28/58）。缺貨模型對金融股不適用。"""
    return str(stock_id).startswith(("28", "58"))


def _candidate_pool(batch_df: pd.DataFrame, *, max_n: int) -> list[dict]:
    """全市場月營收 batch → 「營收動能向上」候選池（依末月 YoY 由高到低，取前 max_n）。

    每筆:{stock_id, revenue_yoy_last3, last_yoy}。只保留 classify_trend ∈ {up, strong_up}。
    """
    if batch_df is None or batch_df.empty or "stock_id" not in batch_df.columns:
        return []
    out: list[dict] = []
    for _sid, _grp in batch_df.groupby("stock_id"):
        _stats = compute_yoy_mom(_grp)
        if classify_trend(_stats) not in ("up", "strong_up"):
            continue
        _yoy3 = _stats.get("yoy_last3") or []
        _last = next((y for y in reversed(_yoy3) if y is not None), None)
        out.append({
            "stock_id": str(_sid),
            "revenue_yoy_last3": _yoy3,
            "last_yoy": _last if _last is not None else float("-inf"),
        })
    out.sort(key=lambda c: c["last_yoy"], reverse=True)
    return out[:max_n]


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def _scan_cached(max_scan: int) -> tuple[list[dict], dict]:
    """重掃全市場（無名稱，名稱由 run_shortage_scan 於快取外套用）。快取集中點。"""
    _fetched_at = pd.Timestamp.now("UTC").isoformat()
    batch = fetch_batch_monthly_revenue(months=18)
    if batch is None or batch.empty:
        return [], {"candidates": 0, "deep_scanned": 0, "scored": 0,
                    "note": "⚠️ 月營收全市場資料無法取得（FinMind token/quota？）",
                    "source": "FinMind:TaiwanStockMonthRevenue:batch",
                    "fetched_at": _fetched_at, "version": SHORTAGE_VERSION}

    pool = _candidate_pool(batch, max_n=max_scan)
    stocks: list[dict] = []
    for c in pool:
        _frame = fetch_quarterly_shortage_frame(c["stock_id"])
        stocks.append({
            "stock_id": c["stock_id"],
            "name": "",
            "is_finance": _is_finance(c["stock_id"]),
            "quarters": _frame,
            "revenue_yoy_last3": c["revenue_yoy_last3"],
        })

    scores = rank_shortage(stocks)
    rows = to_rows(scores)
    meta = {
        "candidates": len(pool),
        "deep_scanned": len(stocks),
        "scored": len(rows),
        "note": "" if rows else "⚠️ 候選池深掃後無可評分標的（多為財報季數不足或缺科目）",
        "source": "FinMind:MonthRevenue(batch)+FinancialStatements+BalanceSheet",
        "fetched_at": _fetched_at,
        "version": SHORTAGE_VERSION,
    }
    return rows, meta


def run_shortage_scan(
    *,
    refresh: bool = False,
    max_scan: int = SHORTAGE_DEEP_SCAN_MAX,
    name_map: dict[str, str] | None = None,
) -> tuple[list[dict], dict]:
    """全市場缺貨掃描 → (排行 rows, meta)。

    Args:
        refresh: True → 清 L1 月營收/季報 cache + 本層 cache 重掃（UI「重新整理」用）。
        max_scan: 深掃候選池上限（預設 50，比照選股網界定 FinMind 用量）。
        name_map: 可選 {代碼: 名稱}（於快取外套用，避免大 dict 進 cache key）。

    Returns:
        (rows, meta):rows 為 shortage_screener.to_rows 輸出（依缺貨分數降冪）。
    """
    if refresh:
        _clear(fetch_batch_monthly_revenue)
        _clear(fetch_quarterly_shortage_frame)
        _clear(_scan_cached)

    rows, meta = _scan_cached(max_scan)
    if name_map:
        rows = [dict(r) for r in rows]  # 淺拷貝避免污染 cache 內物件
        for r in rows:
            _nm = name_map.get(str(r.get("代碼", "")))
            if _nm:
                r["名稱"] = _nm
    return rows, meta
