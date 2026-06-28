"""src/compute/health/mj_health_diff.py — v18.185 MJ 體檢表跨期變化偵測

對 MJ 林明樟財報體檢（`financial_health_engine.analyze_financial_health`）兩期
結果做 status 等級比對，逐項偵測「變好 / 變差 / 不變」，回傳 verdict
與漏斗篩選器，純函式 zero-IO。

使用情境：
  prev_mj_result = analyze_financial_health(api_key, sid, fin_data_q_prev)
  curr_mj_result = analyze_financial_health(api_key, sid, fin_data_q_curr)
  verdict = diff_mj_health(prev_mj_result, curr_mj_result, stock_id=sid)
  → 取得 verdict.improvements / verdict.deteriorations / verdict.verdict

設計重點：
  • Status → 0/1/2 ordinal normalize（Pass=2 / Acceptable=1 / Fail=0
    + 🟢🟡🔴 + Good/Hard Work + Top Tier/Good/Weak + Strong/Weak
    + Excellent/Moderate + Yes/No 全涵蓋）。
  • Status 等級相同 → unchanged（不管數值微動，避免 50.1% vs 49.9% 噪音）。
  • verdict 規則：improve − deteriorate ≥ min_net_delta → "improving"；
    反之 "deteriorating"；分歧 → "mixed"；全 unchanged → "stable"。
  • 盈轉虧 / 虧轉盈鏡像旗標：Operating_Margin.Core_Business_Profitable
    Yes→No 標 `is_breakdown=True`；No→Yes 標 `is_turnaround=True`。
  • 全 graceful：缺欄 / 非 dict / Status 對應不到 → skip 該指標不拋例外。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ════════════════════════════════════════════════════════════════
# Status → ordinal score（0=差 / 1=普通 / 2=好）
# ════════════════════════════════════════════════════════════════
STATUS_SCORES: dict[str, int] = {
    # Survival / 通用 3 段
    "Pass": 2, "Acceptable": 1, "Fail": 0,
    # Profitability gross margin / ROE
    "Good": 2, "Hard Work": 1,
    "Top Tier": 2, "Weak": 0,
    # Profitability margin_of_safety
    "Strong": 2,
    # Operating margin
    "Excellent": 2, "Moderate": 1,
    # Net margin
    "Thin Profit": 1,
    # Emoji 燈號（MJ top-level）
    "🟢": 2, "🟡": 1, "🔴": 0,
    # OPM / Core_Business_Profitable / Leverage
    "Yes": 2, "No": 0,
    "None": 2,  # Leverage_Warning="None" 代表無警示 = 好
}


def _score(status: Any) -> int | None:
    """Status 字串 → 0/1/2 分；無對應或非字串回 None（跳過該指標）。"""
    if not isinstance(status, str):
        return None
    s = status.strip()
    if not s:
        return None
    # 直接命中
    if s in STATUS_SCORES:
        return STATUS_SCORES[s]
    # 容錯：常見 "Exception_Pass (..." / "High Debt Ratio (..." 抓前綴
    for prefix, score in STATUS_SCORES.items():
        if s.startswith(prefix):
            return score
    # High Debt Ratio 視為壞訊號（leverage_warning ≠ None）
    if "High Debt Ratio" in s:
        return 0
    return None


# ════════════════════════════════════════════════════════════════
# Data models
# ════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class MetricDiff:
    """單一指標跨期變化。delta = +1 變好 / 0 不變 / -1 變差。"""

    module: str
    metric: str
    prev_status: str
    curr_status: str
    delta: int
    direction: str  # "improved" / "unchanged" / "deteriorated"


@dataclass
class HealthDiffVerdict:
    """單股 MJ 體檢跨期 verdict。"""

    stock_id: str
    improvements: list[MetricDiff] = field(default_factory=list)
    deteriorations: list[MetricDiff] = field(default_factory=list)
    unchanged: list[MetricDiff] = field(default_factory=list)
    verdict: str = "stable"
    is_turnaround: bool = False  # Core_Business_Profitable No→Yes
    is_breakdown: bool = False   # Core_Business_Profitable Yes→No

    @property
    def improve_count(self) -> int:
        return len(self.improvements)

    @property
    def deteriorate_count(self) -> int:
        return len(self.deteriorations)

    @property
    def net_delta(self) -> int:
        return self.improve_count - self.deteriorate_count

    def to_dict(self) -> dict:
        def _md(m: MetricDiff) -> dict:
            return {
                "module": m.module, "metric": m.metric,
                "prev_status": m.prev_status, "curr_status": m.curr_status,
                "delta": m.delta, "direction": m.direction,
            }
        return {
            "stock_id": self.stock_id,
            "verdict": self.verdict,
            "improve_count": self.improve_count,
            "deteriorate_count": self.deteriorate_count,
            "net_delta": self.net_delta,
            "is_turnaround": self.is_turnaround,
            "is_breakdown": self.is_breakdown,
            "improvements": [_md(m) for m in self.improvements],
            "deteriorations": [_md(m) for m in self.deteriorations],
            "unchanged": [_md(m) for m in self.unchanged],
        }


# ════════════════════════════════════════════════════════════════
# Module 掃描清單（MJ schema）
# ════════════════════════════════════════════════════════════════
_MJ_MODULES = (
    "Survival_Module",
    "Operating_Module",
    "Profitability_Module",
    "Financial_Structure_Module",
    "Solvency_Module",
    "Advanced_Diagnostic_Module",
)
# Top-level 燈號（v18.x MJ overview）
_TOP_LEVEL_LIGHTS = (
    "cash_ratio_status", "ocf_status", "debt_ratio_status",
)


def _walk_statuses(mj_result: Any) -> dict[tuple[str, str], str]:
    """掃 MJ 結果，回 {(module, metric): status_string} 字典。

    - 6 個 *_Module 內遞迴找帶 "Status" 欄位的子物件（如 Cash_Ratio.Status）
    - Operating_Margin.Core_Business_Profitable 視為 status
    - ROE.Leverage_Warning 視為 status
    - top-level cash_ratio_status / ocf_status / debt_ratio_status
    """
    out: dict[tuple[str, str], str] = {}
    if not isinstance(mj_result, dict):
        return out

    # Top-level 燈號
    for k in _TOP_LEVEL_LIGHTS:
        v = mj_result.get(k)
        if isinstance(v, str) and v.strip():
            out[("TopLevel", k)] = v

    # 6 模組
    for mod_name in _MJ_MODULES:
        mod = mj_result.get(mod_name)
        if not isinstance(mod, dict):
            continue
        for metric_name, payload in mod.items():
            if isinstance(payload, dict):
                # 標準 {"Value":"X", "Status":"Y", ...}
                status = payload.get("Status")
                if isinstance(status, str) and status.strip():
                    out[(mod_name, metric_name)] = status
                # 特例：Operating_Margin.Core_Business_Profitable
                cbp = payload.get("Core_Business_Profitable")
                if isinstance(cbp, str) and cbp.strip():
                    out[(mod_name, f"{metric_name}.Core_Business_Profitable")] = cbp
                # 特例：ROE.Leverage_Warning
                lev = payload.get("Leverage_Warning")
                if isinstance(lev, str) and lev.strip():
                    out[(mod_name, f"{metric_name}.Leverage_Warning")] = lev
            elif isinstance(payload, str) and payload.strip():
                # 例如 Operating_Module 中部分欄位是 plain string
                # 跳過：純 verdict / insight 文字非 status，不參與比對
                continue
    return out


# ════════════════════════════════════════════════════════════════
# 核心 diff
# ════════════════════════════════════════════════════════════════
def diff_mj_health(
    prev: Any,
    curr: Any,
    stock_id: str = "",
    min_net_delta: int = 1,
) -> HealthDiffVerdict:
    """逐項比對 MJ 體檢 prev 與 curr 的 status delta。

    Args:
        prev: 上一期 MJ analyze_financial_health 結果 dict
        curr: 本期 MJ 結果 dict
        stock_id: 標識用，不影響邏輯
        min_net_delta: verdict 緩衝門檻（improve - deteriorate ≥ 此值 → improving）

    Returns:
        HealthDiffVerdict — 包 improvements / deteriorations / unchanged
        / verdict 四段（improving / deteriorating / mixed / stable）
        / is_turnaround / is_breakdown 鏡像旗標
    """
    verdict = HealthDiffVerdict(stock_id=str(stock_id or ""))

    prev_map = _walk_statuses(prev)
    curr_map = _walk_statuses(curr)

    if not prev_map or not curr_map:
        return verdict  # 缺資料 → stable 預設

    # 取兩期都有的指標做比對
    common_keys = set(prev_map.keys()) & set(curr_map.keys())
    for k in common_keys:
        p_str = prev_map[k]
        c_str = curr_map[k]
        p_score = _score(p_str)
        c_score = _score(c_str)
        if p_score is None or c_score is None:
            continue
        delta = c_score - p_score
        mod, metric = k
        if delta > 0:
            md = MetricDiff(mod, metric, p_str, c_str, +1, "improved")
            verdict.improvements.append(md)
        elif delta < 0:
            md = MetricDiff(mod, metric, p_str, c_str, -1, "deteriorated")
            verdict.deteriorations.append(md)
        else:
            md = MetricDiff(mod, metric, p_str, c_str, 0, "unchanged")
            verdict.unchanged.append(md)

        # 鏡像旗標：本業由賺轉賠 / 賠轉賺
        if metric.endswith(".Core_Business_Profitable"):
            if p_str.startswith("Yes") and c_str.startswith("No"):
                verdict.is_breakdown = True
            elif p_str.startswith("No") and c_str.startswith("Yes"):
                verdict.is_turnaround = True

    # verdict 4 段
    net = verdict.net_delta
    total_changes = verdict.improve_count + verdict.deteriorate_count
    if total_changes == 0:
        verdict.verdict = "stable"
    elif net >= min_net_delta:
        verdict.verdict = "improving"
    elif net <= -min_net_delta:
        verdict.verdict = "deteriorating"
    else:
        verdict.verdict = "mixed"
    return verdict


# ════════════════════════════════════════════════════════════════
# 漏斗篩選器
# ════════════════════════════════════════════════════════════════
def screen_health_changes(
    snapshots: Any,
    mode: str = "both",
    min_net_delta: int = 1,
) -> list[HealthDiffVerdict]:
    """漏斗篩選：跨多檔 MJ 跨期快照，依 mode 過濾。

    Args:
        snapshots: list of {"id": sid, "prev": prev_mj_dict, "curr": curr_mj_dict}
        mode: "improving"（只回變好）/ "deteriorating"（只回變差）/
              "both"（變好 + 變差皆回，過濾掉 stable）/ "all"（全回）
        min_net_delta: 雜訊緩衝門檻（傳給 diff_mj_health）

    Returns:
        list[HealthDiffVerdict] — 過濾後 verdict 清單
    """
    if not isinstance(snapshots, list):
        return []
    if mode not in ("improving", "deteriorating", "both", "all"):
        mode = "both"

    out: list[HealthDiffVerdict] = []
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        sid = str(snap.get("id") or "").strip()
        if not sid:
            continue
        try:
            v = diff_mj_health(
                snap.get("prev"), snap.get("curr"),
                stock_id=sid, min_net_delta=min_net_delta,
            )
        except Exception as e:  # pragma: no cover - defensive
            print(f"[mj_health_diff] {sid} diff 失敗: {type(e).__name__}: {e}")
            continue

        if mode == "improving" and v.verdict != "improving":
            continue
        if mode == "deteriorating" and v.verdict != "deteriorating":
            continue
        if mode == "both" and v.verdict not in ("improving", "deteriorating"):
            continue
        # mode == "all" → keep all
        out.append(v)

    return out


def to_json_rows(verdicts: list[HealthDiffVerdict]) -> list[dict]:
    """便捷工具：list[HealthDiffVerdict] → JSON-serializable rows。"""
    return [v.to_dict() for v in verdicts]
