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

from shared.fail_cooldown import CachedFailure as _CachedFailure  # D2-f5 2026-09-28
from shared.shortage_screen_thresholds import (
    SHORTAGE_DEEP_SCAN_MAX,
    SHORTAGE_TIER_MID_MIN,
    SHORTAGE_TIER_STRONG_MIN,
    SHORTAGE_VERSION,
    TIER_INSUFFICIENT,
    TIER_MID,
    TIER_NA,
    TIER_STRONG,
    TIER_WEAK,
)

_RANKABLE_TIERS = (TIER_STRONG, TIER_MID, TIER_WEAK)
from shared.ttls import TTL_1DAY
from src.compute.health.monthly_revenue_calc import classify_trend, compute_yoy_mom
from src.compute.screener.shortage_screener import rank_shortage
from src.data.stock.monthly_revenue_fetcher import (
    fetch_batch_monthly_revenue,
    fetch_monthly_revenue,
)
from src.data.stock.quarterly_financials_fetcher import fetch_quarterly_shortage_frame


class _CandidatePoolFetchFailed(_CachedFailure):
    """`_scan_cached` ② 在全市場月營收是 L1 判定的**確定抓取失敗**時的出口專用(§1.A-3(a)):
    「兩個候選池來源都取不到」(D2-f5 2026-09-28),以及上市／上櫃一邊確定失敗、只拿到半邊表時
    算出的候選池結果(D2-f23 2026-09-28 批 D3e)。

    `st.cache_data` 不快取例外 → 這一份不會被凍成 1 天;`run_shortage_scan` 只接住本類別,
    取 `.payload` 回傳與修前逐字相同的 (rows, meta)。刻意用私有子類別、不直接接
    `CachedFailure`(同 rs_leader_service D2-f1 的理由):別的模組的 `CachedFailure` 若從
    下層漏出來,不會在這裡被誤當成 (rows, meta) 拆開(D2-f26:測試守住這個範圍)。
    """


def _batch_revenue_with_status(months: int) -> tuple[pd.DataFrame, bool]:
    """L1 全市場月營收 +「這一份是不是 L1 判定的確定抓取失敗」(D2-f5 2026-09-28)。

    走 L1 `fetch_batch_monthly_revenue.with_status`:同一次呼叫回 (df, 是否確定失敗),df 與
    `fetch_batch_monthly_revenue(months=months)` 逐字相同(不多打一次、也不必事後查 L1 退避表)。
    `fetch_batch_monthly_revenue` 沒有 `.with_status`(例:被換成純函式)→ 照修前呼叫,
    一律當「非確定失敗」(照舊快取,不猜)。
    """
    _with_status = getattr(fetch_batch_monthly_revenue, "with_status", None)
    if callable(_with_status):
        return _with_status(months)
    return fetch_batch_monthly_revenue(months=months), False


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


def _diagnose(scored: list, n: int) -> str:
    """無可評分時,把失敗原因攤開(§5 可觀測性):幾檔資料不足、其中幾檔 FinMind 回 0 季。"""
    _insuff = [s for s in scored if s.tier == TIER_INSUFFICIENT]
    _zero_q = sum(1 for s in _insuff if "僅 0 季" in s.reason_text)
    _na_fin = sum(1 for s in scored if s.tier == TIER_NA)
    _msg = f"⚠️ 深掃 {n} 檔後無可評分：資料不足 {len(_insuff)} 檔"
    if _zero_q:
        _msg += (f"（其中 {_zero_q} 檔 FinMind 回 0 季 → 多半是你的 FinMind 方案對「季財報/資產"
                 f"負債表」的權限或配額限制，非程式問題；可換更高 tier 或改用單股工具查）")
    if _na_fin:
        _msg += f"、金融股(不適用) {_na_fin} 檔"
    return _msg


def _score_and_diagnose(pairs: list[tuple[str, list | None]]) -> tuple[list[dict], str]:
    """對 (股號, 月營收YoY或None) 逐檔深抓季報 + 評分 → (可排名 rows, 診斷 note)。

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
    _scored = rank_shortage(stocks, include_na=True)
    _rows = [s.to_row() for s in _scored if s.tier in _RANKABLE_TIERS]
    _note = "" if _rows else _diagnose(_scored, len(pairs))
    return _rows, _note


@st.cache_data(ttl=TTL_1DAY, show_spinner=False)
def _scan_cached(max_scan: int) -> tuple[list[dict], dict]:
    """全市場掃描（無名稱，名稱由 run_shortage_scan 於快取外套用）。快取集中點。

    候選池來源(依 tier 相容性排序):
      ① 基本面存活池(免費離線快照,你的環境確定能跑) — 逐檔單抓月營收
      ② 全市場月營收批次(需 FinMind sponsor tier) — fallback,動能排序更佳

    D2-f5（2026-09-28）：②「兩個候選池來源都取不到」那一條，**只有**全市場月營收是 L1 判定的
    **確定抓取失敗**時改**拋** `_CandidatePoolFetchFailed`（不入快取），由 `run_shortage_scan` 接住
    回同一份 (rows, meta)；其餘分支（含 L1 沒有確定失敗的空表、存活池路徑的各種結果）照舊回傳、
    照舊快取。本層不另記退避：這條路唯一會打上游的是 L1 全市場月營收，它自己有冷卻
    （冷卻期內不重打；D2-f25 起遞增）；這條路也不會跑到逐檔深掃（深掃在它之後）。
    D2-f23（2026-09-28 批 D3e）：② 拿到的全市場月營收若是 L1 判定的確定失敗但**不空**（上市／上櫃
    一邊確定失敗、只拿到另一邊的半邊表），算完候選池後同樣改拋 `_CandidatePoolFetchFailed`（不入
    快取），回傳內容不變。本層同樣不另記退避：L1 冷卻期內重算不打上游；半邊表是 OpenAPI 單月快照
    （每檔 1 列、算不出年增率）→ 候選池為 0 檔、逐檔深掃 0 次，重算只花在本機的候選池分類。
    """
    _fetched_at = pd.Timestamp.now("UTC").isoformat()

    # ── ① 優先：免費離線基本面存活池 ──────────────────────────
    _survivors = _survivor_pool(max_scan)
    if _survivors:
        _pairs = [(s, None) for s in _survivors]
        _rows, _note = _score_and_diagnose(_pairs)
        return _rows, {
            "candidates": len(_survivors), "deep_scanned": len(_pairs),
            "scored": len(_rows), "pool_source": "基本面存活池（免費離線快照）",
            "note": _note,
            "source": "FundamentalsSnapshot(survivors)+FinMind:MonthRevenue(single)+FS+BS",
            "fetched_at": _fetched_at, "version": SHORTAGE_VERSION}

    # ── ② fallback：全市場月營收批次（需 sponsor tier）──────────
    _batch, _batch_failed = _batch_revenue_with_status(months=18)   # D2-f5：df 同修前的呼叫
    if _batch is None or _batch.empty:
        _empty = ([], {
            "candidates": 0, "deep_scanned": 0, "scored": 0, "pool_source": "（無）",
            "note": ("⚠️ 兩個候選池來源都取不到：基本面快照為空（選股網初篩需先跑 cron 快照），"
                     "且全市場月營收批次不可用（此呼叫需 FinMind sponsor tier，你的方案不支援）。"),
            "source": "none", "fetched_at": _fetched_at, "version": SHORTAGE_VERSION})
        if _batch_failed:
            # D2-f5(2026-09-28,§1.A-3(a)「只快取成功結果」):全市場月營收是 L1 判定的確定抓取失敗
            # (OpenAPI 備援打不到,判準見 L1 `fetch_batch_monthly_revenue`)—— 修前這份結果被
            # @st.cache_data 快取 1 天,來源恢復後使用者仍一直看到「兩個候選池來源都取不到」。
            # 改為拋出(st.cache_data 不快取例外),由 run_shortage_scan 接住、回傳內容不變。
            # 退避(§1.A-3(b))由 L1 負責:冷卻期內再呼叫不重打上游(本層不另記退避)。
            raise _CandidatePoolFetchFailed(_empty)
        return _empty

    _pool = _candidate_pool(_batch, max_n=max_scan)
    _pairs = [(c["stock_id"], c["revenue_yoy_last3"]) for c in _pool]
    _rows, _note = _score_and_diagnose(_pairs)
    _result = (_rows, {
        "candidates": len(_pool), "deep_scanned": len(_pairs), "scored": len(_rows),
        "pool_source": "全市場月營收動能候選池（sponsor tier）",
        "note": _note,
        "source": "FinMind:MonthRevenue(batch)+FS+BS",
        "fetched_at": _fetched_at, "version": SHORTAGE_VERSION})
    if _batch_failed:   # D2-f23(批 D3e):L1 判定一邊市場確定失敗、只拿到半邊表 → 不入快取(同上)
        raise _CandidatePoolFetchFailed(_result)
    return _result


def run_shortage_scan(
    *,
    refresh: bool = False,
    max_scan: int = SHORTAGE_DEEP_SCAN_MAX,
    name_map: dict[str, str] | None = None,
) -> tuple[list[dict], dict]:
    """全市場缺貨掃描 → (排行 rows, meta)。

    Args:
        refresh: True → 清 L1 月營收/季報 cache + 本層 cache 重掃（UI「重新整理」用）。
            （D2-f5：全市場月營收的 `.clear()` 同清它的失敗退避紀錄 → refresh 照舊一定重抓。）
        max_scan: 深掃候選池上限（預設 50，比照選股網界定 FinMind 用量）。
        name_map: 可選 {代碼: 名稱}（於快取外套用，避免大 dict 進 cache key）。

    Returns:
        (rows, meta):rows 為 shortage_screener.to_rows 輸出（依缺貨分數降冪）。

    D2-f5（2026-09-28）：「兩個候選池來源都取不到」且全市場月營收是 L1 確定抓取失敗的結果
    不入快取（下次呼叫重算；L1 冷卻期內重算不打上游）；每一次的回傳內容與修前同一次計算逐字相同
    （唯 `fetched_at` 是當次重算的時點 —— 修前是被快取那一次的時點；同 D2-f1 大盤失敗那條）。
    D2-f23（2026-09-28 批 D3e）：全市場月營收是 L1 判定失敗的**半邊表**（上市／上櫃一邊確定失敗）時，
    算出的結果同樣不入快取、回傳內容同上。
    已知代價（與 #741 列的 D2-f8／D2-f11 同型）：全站 `st.cache_data.clear()`（例：v1 側欄「強制刷新」）
    清不掉 L1 冷卻，失敗後的冷卻期內按它不會重抓全市場月營收（冷卻由 `FAIL_COOLDOWN_SEC` 起；D2-f25
    起連續失敗時加倍、最長 `TTL_1HOUR`）；`refresh=True` 則會。
    """
    if refresh:
        _clear(fetch_batch_monthly_revenue)
        _clear(fetch_quarterly_shortage_frame)
        _clear(_scan_cached)

    try:
        rows, meta = _scan_cached(max_scan)
    except _CandidatePoolFetchFailed as _cf:
        rows, meta = _cf.payload     # D2-f5:這一份沒進快取;以下的快取外注入照舊套用
    # 存活池涵蓋率診斷（§5，快取外注入以反映最新快照）
    try:
        from src.services.fundamental_screener_service import get_snapshot_coverage_note
        meta = {**meta, "coverage_note": get_snapshot_coverage_note()}
    except Exception as _e:  # noqa: BLE001 — 涵蓋率不可用不炸掃描
        print(f"[shortage-svc] 涵蓋率注入失敗:{type(_e).__name__}: {_e}")
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
        # v19.178 §3.3:原文案 65 / 40–64 / 40 為 prompt 內寫死,tier 判定卻走 SSOT
        # (shared/shortage_screen_thresholds)。改門檻時 tier 會動、送給 AI 的說明不會動
        # → LLM 會依舊門檻敘事。改為插值,單一真相。
        f"- 🟥 強缺貨訊號（分數≥{SHORTAGE_TIER_STRONG_MIN:.0f}）：{_cnt(TIER_STRONG)} 檔。",
        f"- 🟧 中度缺貨訊號（{SHORTAGE_TIER_MID_MIN:.0f} ~ 未達強訊號）：{_cnt(TIER_MID)} 檔。",
        f"- ⬜ 不明顯（<{SHORTAGE_TIER_MID_MIN:.0f}）：{_cnt(TIER_WEAK)} 檔。",
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
