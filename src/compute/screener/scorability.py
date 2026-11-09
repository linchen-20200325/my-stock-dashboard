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
# 📌 2026-11-08（客戶 DEC-150）：資格由「任一腿有效」改為「**兩腿皆有效**」才可評分（見 is_trend_scorable）。

def trend_row_evidence(row: dict) -> tuple[int, int]:
    """回 (有 YoY 的月份數, 季快照數)；欄位缺 / 型別不對 → 0（保守視為無證據）。"""
    _mon = (row or {}).get("mon_detail")
    _fin = (row or {}).get("fin_detail")
    _mon = _mon if isinstance(_mon, dict) else {}
    _fin = _fin if isinstance(_fin, dict) else {}
    _m = _as_float(_mon.get("n_months")) or 0.0
    _s = _as_float(_fin.get("n_snapshots")) or 0.0
    # 有效快照須「真的比得出東西」（2026-11-08 客戶核准：必要資料不足不得產生正式綜合評級）：
    # 近兩季 diff 若 0 個指標可比（2~3 期皆空 dict／格式不完整）→ delta=0 只是預設值，不是證據。
    # 判定直接沿用既有 `diff_fin_health` 的結果（改善＋惡化＋不變 = 實際比較了幾個指標），
    # 不新增任何門檻常數；列沒有 `diff_verdict`（舊 cache／手工列）→ 退回 n_snapshots（相容）。
    _dv = (row or {}).get("diff_verdict")
    if _s >= 2 and _dv is not None:
        _n_cmp = _diff_compared_count(_dv)
        if _n_cmp is not None and _n_cmp == 0:
            _s = 0.0
    # 2026-11-08（客戶 DEC-150 核准的 QA 補洞）：`compute_one_stock_trend` 算 diff_verdict 時若拋例外，
    # 會留下 `diff_failed=True`（verdict 為 None）。此時「近兩季能不能比」無從查證 → 保守判無證據，
    # **不得**退回只看 n_snapshots（那會把「比較失敗」當成「有 2 季快照」）。
    elif _s >= 2 and _dv is None and (row or {}).get("diff_failed") is True:
        _s = 0.0
    return int(_m), int(_s)


def _diff_compared_count(verdict) -> int | None:
    """`HealthDiffVerdict` 實際比較了幾個指標；形狀不對 → None（呼叫端退回舊判定）。"""
    try:
        return (len(verdict.improvements) + len(verdict.deteriorations)
                + len(verdict.unchanged))
    except (AttributeError, TypeError):
        return None


def is_trend_scorable(
    row: dict,
    *,
    min_months: int = TREND_MIN_REVENUE_MONTHS,
    min_snapshots: int = TREND_MIN_FIN_SNAPSHOTS,
) -> bool:
    """這一列是否可形成**正式雙頻率綜合評級**（月營收腿 **且** 季財報腿皆有真實輸入）。

    2026-11-08（客戶 DEC-150 核准：「財報缺任一必要腿不產正式綜合評級」）：
    原為 OR（任一腿有效即可評分）→ 改為 AND。逐腿「有效」的定義**一字未動**：
      月營收腿：≥ min_months 個月有 YoY（SSOT `TREND_MIN_REVENUE_MONTHS`）
      季財報腿：≥ min_snapshots 季且近兩季確實比得出指標（SSOT `TREND_MIN_FIN_SNAPSHOTS`）
    任一腿無效 → 該腿的 0.0 是預設值（缺值不是持平），65/35 權重又不重配 → 合分不可當結論。
    """
    _m, _s = trend_row_evidence(row)
    return _m >= int(min_months) and _s >= int(min_snapshots)


def split_trend_rows(rows, **kwargs) -> tuple[list[dict], list[dict]]:
    """(可評分列, 無法評分列)，各自保持原順序。非 dict 元素一律歸「無法評分」。"""
    ok: list[dict] = []
    bad: list[dict] = []
    for r in (rows or []):
        (ok if isinstance(r, dict) and is_trend_scorable(r, **kwargs) else bad).append(r)
    return ok, bad


# ════════════════════════════════════════════════════════════════
# 📊 財報趨勢 —— 消費端共用的「資料資格＋文案」SSOT（2026-11-08 客戶核准）
# ════════════════════════════════════════════════════════════════
# 客戶：「財報維持 65%／35% 原始權重，必要資料不足不得產生正式綜合評級」。
# 公式／權重／門檻（TREND_MIN_*）一字未動；單股 Tab、AI prompt、組合 Tab 一律走本節同一組函式，
# 缺值時不得把 `compute_trend_score` 的預設 (0.0, ➖ 中性) 當投資結論。

_MON_REASON_TEXT = {"no_data": "月營收無資料", "no_yoy": "月營收無 YoY 可算"}
_LEG_MONTHLY = "月營收"
_LEG_FIN = "季財報"
_MISSING_SUB_TEXT = "—（缺）"


@dataclass(frozen=True)
class TrendRatingStatus:
    """一列財報趨勢的資料資格與可追溯缺值原因（不含任何分數，分數仍在 row 內）。"""

    scorable: bool          # 兩腿皆有效（`is_trend_scorable`）→ 才可產正式綜合評級
    monthly_ok: bool
    fin_ok: bool
    reason_text: str        # 缺的那幾腿各自的原因；兩腿皆足 → ""

    @property
    def partial(self) -> bool:
        """不可形成正式評級，但有一腿有效：該腿分項可「僅供診斷」顯示（另一腿的 0 是缺值不是持平）。"""
        return (not self.scorable) and (self.monthly_ok or self.fin_ok)

    @property
    def missing_legs(self) -> tuple[str, ...]:
        out = []
        if not self.monthly_ok:
            out.append(_LEG_MONTHLY)
        if not self.fin_ok:
            out.append(_LEG_FIN)
        return tuple(out)

    @property
    def missing_legs_text(self) -> str:
        """『缺月營收腿』／『缺季財報腿』／『缺月營收腿、季財報腿』；兩腿皆足 → ""。"""
        legs = self.missing_legs
        return ("缺" + "、".join(f"{l}腿" for l in legs)) if legs else ""

    @property
    def unscorable_label(self) -> str:
        """不可形成正式評級時給畫面的一行：『⚪ 無法形成正式綜合評級（缺 X 腿：原因）』。"""
        return f"⚪ 無法形成正式綜合評級（{self.missing_legs_text}：{self.reason_text}）"


def trend_rating_status(row: dict) -> TrendRatingStatus:
    """單列的資格判定：沿用 `is_trend_scorable`（兩腿皆須有效）＋逐腿原因。"""
    _m, _s = trend_row_evidence(row)
    monthly_ok = _m >= int(TREND_MIN_REVENUE_MONTHS)
    fin_ok = _s >= int(TREND_MIN_FIN_SNAPSHOTS)
    reasons: list[str] = []
    if not monthly_ok:
        _md = (row or {}).get("mon_detail")
        _code = _md.get("reason") if isinstance(_md, dict) else None
        reasons.append(_MON_REASON_TEXT.get(_code, "月營收缺"))
    if not fin_ok:
        _fd = (row or {}).get("fin_detail")
        _fd = _fd if isinstance(_fd, dict) else {}
        _n_raw = _as_float(_fd.get("n_snapshots")) or 0.0
        if _fd.get("reason") == "bad_input":
            reasons.append("季財報快照格式不正")
        elif _n_raw >= int(TREND_MIN_FIN_SNAPSHOTS) and _s == 0:
            if (row or {}).get("diff_failed") is True:
                reasons.append(f"季快照 {int(_n_raw)} 期但近兩季比較失敗（保守視為無證據）")
            else:
                reasons.append(f"季快照 {int(_n_raw)} 期但無可比較指標（空或格式不完整）")
        else:
            reasons.append(f"季快照僅 {int(_n_raw)} 期，至少需 {int(TREND_MIN_FIN_SNAPSHOTS)} 期")
    return TrendRatingStatus(
        scorable=is_trend_scorable(row or {}),
        monthly_ok=monthly_ok,
        fin_ok=fin_ok,
        reason_text="；".join(reasons),
    )


def trend_sub_texts(row: dict) -> tuple[str, str]:
    """(月分文字, 季分文字)：有效腿顯示 `+x.xx`，缺的那腿顯示 `—（缺）`（保留有效分項，不丟）。"""
    st = trend_rating_status(row)

    def _fmt(key: str, ok: bool) -> str:
        v = _as_float((row or {}).get(key))
        return f"{v:+.2f}" if (ok and v is not None) else _MISSING_SUB_TEXT

    return _fmt("mon_sub", st.monthly_ok), _fmt("fin_sub", st.fin_ok)


def trend_prompt_line(row: dict) -> str:
    """給 AI prompt 的一行。

    兩腿皆有效 → 正式綜合評級（標籤＋合分，格式與舊版逐字相同）。
    任一腿無效 → **不送標籤與合分**，明說無法形成正式綜合評級；僅附有效分項供診斷，
    且註明不得當成已確認結論（客戶 DEC-150）。
    """
    st = trend_rating_status(row)
    mon_txt, fin_txt = trend_sub_texts(row)
    if not st.scorable:
        line = f"財報趨勢資料不足（{st.missing_legs_text}；{st.reason_text}），無法形成正式綜合評級；"
        if st.partial:
            diag = "、".join(
                f"{name} {txt}" for name, txt, ok in
                (("月分", mon_txt, st.monthly_ok), ("季分", fin_txt, st.fin_ok)) if ok)
            line += (f"僅供診斷：有效分項 {diag}（缺的分項是缺值不是持平，權重未重配）——"
                     f"非完整雙頻率評級，不得作為已確認結論")
        else:
            line += "無有效分項可供診斷，請勿推論財報趨勢"
        return line
    _score = _as_float((row or {}).get("score")) or 0.0
    return (f"財報趨勢分數(月+季 65/35)={(row or {}).get('label', '—')} "
            f"(合分 {_score:+.2f},月分 {mon_txt}/季分 {fin_txt})")
