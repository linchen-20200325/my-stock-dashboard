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

from shared.shortage_screen_thresholds import (
    SHORTAGE_DEEP_SCAN_MAX,
    SHORTAGE_VERSION,
    TIER_MID,
    TIER_STRONG,
    TIER_WEAK,
)
from shared.ttls import TTL_1DAY
from src.compute.health.monthly_revenue_calc import classify_trend, compute_yoy_mom
from src.compute.screener.shortage_screener import rank_shortage, to_rows
from src.data.stock.monthly_revenue_fetcher import (
    fetch_batch_monthly_revenue,
    fetch_monthly_revenue,
)
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


def _survivor_pool(max_n: int) -> list[str]:
    """免費離線基本面存活池（選股網「四項全過」快照，無需 FinMind sponsor 批次）。

    回前 max_n 檔股號（依 loader 的 EPS 排序），失敗回 []（讓 caller 退回 batch）。
    """
    try:
        from src.services.fundamental_screener_service import get_survivor_ids
        return [str(s) for s in get_survivor_ids()[:max_n]]
    except Exception as _e:  # noqa: BLE001 — 快照不可用不炸掃描
        print(f"[shortage-svc] 基本面存活池不可用:{type(_e).__name__}: {_e}")
        return []


def _score_pairs(pairs: list[tuple[str, list | None]]) -> list[dict]:
    """對 (股號, 月營收YoY或None) 逐檔深抓季報 + 評分 → to_rows。

    yoy3 為 None（存活池路徑）→ 逐檔單抓月營收（data_id，低 tier 也支援）補算；
    抓不到 → C4 標資料不足（0 分），C1-C3 仍由季報計分（fail-soft）。
    """
    stocks: list[dict] = []
    for _sid, _yoy3 in pairs:
        _frame = fetch_quarterly_shortage_frame(_sid)
        if _yoy3 is None:
            _mrev = fetch_monthly_revenue(_sid, months=18)
            _yoy3 = (compute_yoy_mom(_mrev).get("yoy_last3", [])
                     if _mrev is not None and not _mrev.empty else [])
        stocks.append({
            "stock_id": _sid,
            "name": "",
            "is_finance": _is_finance(_sid),
            "quarters": _frame,
            "revenue_yoy_last3": _yoy3,
        })
    return to_rows(rank_shortage(stocks))


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def _scan_cached(max_scan: int) -> tuple[list[dict], dict]:
    """全市場掃描（無名稱，名稱由 run_shortage_scan 於快取外套用）。快取集中點。

    候選池來源(依 tier 相容性排序):
      ① 基本面存活池(免費離線快照,你的環境確定能跑) — 逐檔單抓月營收
      ② 全市場月營收批次(需 FinMind sponsor tier) — fallback,動能排序更佳
    """
    _fetched_at = pd.Timestamp.now("UTC").isoformat()

    # ── ① 優先：免費離線基本面存活池 ──────────────────────────
    _survivors = _survivor_pool(max_scan)
    if _survivors:
        _pairs = [(s, None) for s in _survivors]
        _rows = _score_pairs(_pairs)
        return _rows, {
            "candidates": len(_survivors), "deep_scanned": len(_pairs),
            "scored": len(_rows), "pool_source": "基本面存活池（免費離線快照）",
            "note": "" if _rows else "⚠️ 存活池深掃後無可評分標的（多為財報季數不足或缺科目）",
            "source": "FundamentalsSnapshot(survivors)+FinMind:MonthRevenue(single)+FS+BS",
            "fetched_at": _fetched_at, "version": SHORTAGE_VERSION}

    # ── ② fallback：全市場月營收批次（需 sponsor tier）──────────
    _batch = fetch_batch_monthly_revenue(months=18)
    if _batch is None or _batch.empty:
        return [], {
            "candidates": 0, "deep_scanned": 0, "scored": 0, "pool_source": "（無）",
            "note": ("⚠️ 兩個候選池來源都取不到：基本面快照為空（選股網初篩需先跑 cron 快照），"
                     "且全市場月營收批次不可用（此呼叫需 FinMind sponsor tier，你的方案不支援）。"),
            "source": "none", "fetched_at": _fetched_at, "version": SHORTAGE_VERSION}

    _pool = _candidate_pool(_batch, max_n=max_scan)
    _pairs = [(c["stock_id"], c["revenue_yoy_last3"]) for c in _pool]
    _rows = _score_pairs(_pairs)
    return _rows, {
        "candidates": len(_pool), "deep_scanned": len(_pairs), "scored": len(_rows),
        "pool_source": "全市場月營收動能候選池（sponsor tier）",
        "note": "" if _rows else "⚠️ 候選池深掃後無可評分標的（多為財報季數不足或缺科目）",
        "source": "FinMind:MonthRevenue(batch)+FS+BS",
        "fetched_at": _fetched_at, "version": SHORTAGE_VERSION}


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


# ════════════════════════════════════════════════════════════════
# AI 三型建議報告 — prompt 組裝（純函式，AI 呼叫由 L5 傳入 gemini_fn 執行）
# ════════════════════════════════════════════════════════════════
def build_shortage_ai_prompt(
    rows: list[dict],
    *,
    top_n: int = 10,
    news_text: str | None = None,
) -> str:
    """把缺貨排行 rows 組成「白話三型建議」AI prompt（積極 / 穩健 / 保守）。

    §8.2 L3:純組字串,不抓資料、不呼叫 AI（gemini_fn 由 L5 傳入執行,對齊
    tab_stock_picker._generate_ai_report pattern）。可用合成 rows 單元測試。

    Args:
        rows: shortage_screener.to_rows 輸出（每列含 代碼/名稱/缺貨分數/訊號強度/理由/_tier）
        top_n: 進 AI 的排行檔數上限
        news_text: 已抓好的相關新聞（L5 傳入）；None → prompt 標「沒抓到」

    Returns:
        prompt 字串（交給呼叫端 gemini_fn）
    """
    from src.services.ai_structured_summary import build_structured_summary_prompt

    _rows = rows or []
    _top = _rows[:top_n]

    # ── 第 1 節：缺貨排行（含各股訊號理由）──────────────────
    _pick_lines = []
    for r in _top:
        _code = str(r.get("代碼", "")).strip()
        _name = str(r.get("名稱", "")).strip()
        _title = f"{_code} {_name}".strip()
        _pick_lines.append(
            f"- {_title}：缺貨分數 {r.get('缺貨分數', '?')}（{r.get('訊號強度', '?')}）；"
            f"{r.get('理由', '')}"
        )
    _pick_data = "\n".join(_pick_lines) if _pick_lines else "（本次掃描沒有掃出可評分的缺貨候選股）"

    # ── 第 2 節：訊號分布統計 ──────────────────────────────
    def _cnt(tier):
        return sum(1 for r in _rows if r.get("_tier") == tier)
    _stat_data = "\n".join([
        f"- 這次掃出共 {len(_rows)} 檔可評分。",
        f"- 🟥 強缺貨訊號（分數≥65）：{_cnt(TIER_STRONG)} 檔。",
        f"- 🟧 中度缺貨訊號（40–64）：{_cnt(TIER_MID)} 檔。",
        f"- ⬜ 不明顯（<40）：{_cnt(TIER_WEAK)} 檔。",
        "- 分數越高代表「合約負債大增＋毛利率走揚＋存貨天數下降＋月營收連續成長」越同步。",
    ])

    # ── 第 3 節：模型限制與正確用法（誠實揭露，讓 AI 納入框架）──
    _caveat_data = "\n".join([
        "- 這是「事後驗證」：財報有約 45 天發布延遲，訊號反映的是上一季已發生的缺貨，不是即時現貨報價。",
        "- 兩段式掃描先用月營收動能圈池，會漏掉「合約負債剛爆、營收還沒反映」的極早期標的。",
        "- 分數高只代表財報足跡像缺貨，不等於股價便宜、也不保證會漲；估值/追高/籌碼要另外看。",
        "- 金融股（代號 28/58）不適用本模型，已排除。",
    ])

    _sections = [
        {"name": "這次掃出哪些疑似缺貨（供不應求）的股票", "data": _pick_data},
        {"name": "整批缺貨訊號的強弱分布", "data": _stat_data},
        {"name": "這個缺貨模型的限制與正確用法", "data": _caveat_data},
    ]

    return build_structured_summary_prompt(
        subject_title="缺貨 / 供不應求選股候選清單",
        sections=_sections,
        news_text=news_text,
        overall_question=(
            "針對三種人分別給白話建議："
            "①積極型（願意追動能）②穩健型（想等基本面或技術面再確認）③保守型（先觀望），"
            "這批缺貨股各自現在該怎麼看、進場前最該小心什麼。"
        ),
    )
