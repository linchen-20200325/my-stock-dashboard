"""src/compute/screener/scorability.py — 「可評分性」判定 SSOT（L2 純函式，zero-IO）。

B5-b（2026-08）：🏆 個股組合同一畫面對「候選」有三個各自獨立的算式，分子／分母來自
不同母體，且其中一處用「拿不到就給滿分」的預設值 —— 三個數字互相否定。

本模組把那三處收斂成**一個**來源（§2.1 SSOT），並把「拿不到資料」與「評出來很差」
在型別上分開（§1 Fail Loud, Never Fake）：

    可評分（scored）   → 有真實分數，進分子/分母、進排序
    無法評分（unscored）→ 標「無法評分」，**不進分子、不進分母、不給假分數排序**

反面教材（本次修掉的原始碼）：
  - `section_portfolio_summary.py` KPI：分子取自 `score_t3`、分母取自 `results_t3`
    （兩個 list 長度不保證相等 —— `section_batch_fetcher.py` 只在 K 線非空時才
    append `score_t3`），於是同一個「≥70」在同頁出現兩個不同分母。
  - `_render_elimination_detail`：`r.get('健康度', 100)` —— 缺健康度時預設**滿分**，
    方向與同檔另外兩處的預設 0 相反，是「假綠燈」的引信。

§8.2：L2 Compute（純函式，無 I/O、無 streamlit、無 requests）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from shared.health_thresholds import HEALTH_GRADE_B_MIN
from shared.signal_thresholds import (
    MULTIFACTOR_ENTRY_MIN,
    TREND_MIN_FIN_SNAPSHOTS,
    TREND_MIN_REVENUE_MONTHS,
)

# 「357 評價」欄的超貴標記。產生端：section_batch_fetcher 的 `val4 = '🔴超貴'`。
# 消費端（汰弱留強）以子字串比對，抽成具名常數避免 inline magic string（§3.3）。
EXPENSIVE_VALUATION_MARKER = "超貴"

# results_t3 內用來取股號的欄（產生端兩個 key 同值寫入，這裡保序 fallback）。
_ID_KEYS = ("stock_id", "代碼")


def _as_float(v) -> float | None:
    """數值化：None / NaN / bool / 非數字 → None（代表「沒有這個讀數」）。

    bool 明確排除：True 會被 float() 轉成 1.0，那不是分數。
    """
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f      # NaN


def row_id(row: dict) -> str:
    """取一列的股號（'stock_id' 優先，退回 '代碼'）；都沒有 → ''。"""
    for k in _ID_KEYS:
        v = (row or {}).get(k)
        if v not in (None, ""):
            return str(v)
    return ""


def build_score_map(scores) -> dict[str, float]:
    """{stock_id: 多因子總分} —— **只收真的算出分數的檔**。

    與 `scoring_engine.rank_stocks` 同一條篩選規則（丟掉含 'error' 的列），
    所以「KPI 分母」與「③ 多因子排行表列數」保證是同一個母體。
    """
    out: dict[str, float] = {}
    for s in (scores or []):
        if not isinstance(s, dict) or "error" in s:
            continue
        sid = row_id(s)
        total = _as_float(s.get("total"))
        if sid and total is not None:
            out[sid] = total
    return out


@dataclass(frozen=True)
class CandidateStats:
    """🏆 個股組合「一頁一份」的候選統計（所有顯示處都吃這個 dataclass）。"""

    n_total: int                 # 本批檔數（results 列數）
    n_scored: int                # 有真實多因子分的檔數 = 明細表列數 = KPI 分母
    n_entry_pass: int            # 多因子分 ≥ entry_min 的檔數 = KPI 分子
    entry_min: float
    unscored_ids: tuple[str, ...] = ()      # 無多因子分（通常是抓不到 K 線）
    n_health_known: int = 0
    health_unknown_ids: tuple[str, ...] = ()
    eliminated_ids: tuple[str, ...] = ()    # 健康度 < health_min 或 357 超貴
    kept_ids: tuple[str, ...] = ()
    health_min: float = 0.0
    scored_ids: tuple[str, ...] = field(default=())

    @property
    def n_unscored(self) -> int:
        return len(self.unscored_ids)

    @property
    def n_health_unknown(self) -> int:
        return len(self.health_unknown_ids)

    @property
    def n_eliminated(self) -> int:
        return len(self.eliminated_ids)

    @property
    def n_kept(self) -> int:
        return len(self.kept_ids)

    def is_scored(self, sid: str) -> bool:
        return str(sid) in self.scored_ids


def summarize_candidates(
    results,
    scores,
    *,
    entry_min: float = MULTIFACTOR_ENTRY_MIN,
    health_min: float = HEALTH_GRADE_B_MIN,
    expensive_marker: str = EXPENSIVE_VALUATION_MARKER,
) -> CandidateStats:
    """把「本批結果 + 多因子評分」收斂成單一份候選統計。

    Args:
        results: 批次分析結果 list[dict]（每檔一列，含 stock_id/代碼，可選 '健康度'、'357評價'）。
        scores:  多因子評分 list[dict]（`score_single_stock` 輸出；含 'error' 的列會被丟掉）。
        entry_min:  多因子「入選候選」門檻（SSOT: MULTIFACTOR_ENTRY_MIN）。
        health_min: 汰弱門檻（SSOT: HEALTH_GRADE_B_MIN）。
        expensive_marker: 357 評價的超貴標記。

    Returns:
        CandidateStats。§1 契約：
          - 沒有真實多因子分的檔 → 進 `unscored_ids`，**不算入** n_scored / n_entry_pass。
          - 健康度不是有效數字 → 進 `health_unknown_ids`，**既不算 kept 也不算 eliminated**
            （不預設 100 也不預設 0）。
    """
    _rows = [r for r in (results or []) if isinstance(r, dict)]
    _score_map = build_score_map(scores)

    scored_ids: list[str] = []
    unscored_ids: list[str] = []
    n_entry_pass = 0
    health_unknown: list[str] = []
    eliminated: list[str] = []
    kept: list[str] = []

    for r in _rows:
        sid = row_id(r)
        total = _score_map.get(sid)
        if total is None:
            unscored_ids.append(sid)
        else:
            scored_ids.append(sid)
            if total >= entry_min:
                n_entry_pass += 1

        health = _as_float(r.get("健康度"))
        if health is None:
            health_unknown.append(sid)
            continue
        _val_txt = str(r.get("357評價", "") or "")
        if health < health_min or (expensive_marker and expensive_marker in _val_txt):
            eliminated.append(sid)
        else:
            kept.append(sid)

    return CandidateStats(
        n_total=len(_rows),
        n_scored=len(scored_ids),
        n_entry_pass=n_entry_pass,
        entry_min=float(entry_min),
        unscored_ids=tuple(unscored_ids),
        n_health_known=len(eliminated) + len(kept),
        health_unknown_ids=tuple(health_unknown),
        eliminated_ids=tuple(eliminated),
        kept_ids=tuple(kept),
        health_min=float(health_min),
        scored_ids=tuple(scored_ids),
    )


# ════════════════════════════════════════════════════════════════
# 📊 財報趨勢 × 轉機 —— 「這一列到底有沒有資料可算」
# ════════════════════════════════════════════════════════════════
# `compute_trend_score` 對「月營收缺 + 季快照不足」一律回 score=0.0 → 落在
# 「➖ 中性」帶（±0.5）正中央，與「真的持平」完全無法區分（§1 假分數參與排序）。
# 下面兩支純函式讓消費端能把這種列標成「⚪ 無法評分」並排除於計數/排序之外。

def trend_row_evidence(row: dict) -> tuple[int, int]:
    """回 (有 YoY 的月份數, 季快照數)；欄位缺 / 型別不對 → 0（保守視為無證據）。"""
    _mon = (row or {}).get("mon_detail")
    _fin = (row or {}).get("fin_detail")
    _mon = _mon if isinstance(_mon, dict) else {}
    _fin = _fin if isinstance(_fin, dict) else {}
    _m = _as_float(_mon.get("n_months")) or 0.0
    _s = _as_float(_fin.get("n_snapshots")) or 0.0
    return int(_m), int(_s)


def is_trend_scorable(
    row: dict,
    *,
    min_months: int = TREND_MIN_REVENUE_MONTHS,
    min_snapshots: int = TREND_MIN_FIN_SNAPSHOTS,
) -> bool:
    """這一列的趨勢分數是否有任何真實輸入撐著。

    月營收 ≥ min_months 個月有 YoY **或** 季快照 ≥ min_snapshots 季（可 diff）
    → 可評分；兩者皆缺 → 無法評分（分數 0.0 純屬預設值，不可當「中性」用）。
    """
    _m, _s = trend_row_evidence(row)
    return _m >= int(min_months) or _s >= int(min_snapshots)


def split_trend_rows(rows, **kwargs) -> tuple[list[dict], list[dict]]:
    """(可評分列, 無法評分列)，各自保持原順序。非 dict 元素一律歸「無法評分」。"""
    ok: list[dict] = []
    bad: list[dict] = []
    for r in (rows or []):
        (ok if isinstance(r, dict) and is_trend_scorable(r, **kwargs) else bad).append(r)
    return ok, bad
