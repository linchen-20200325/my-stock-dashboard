"""src/compute/screener/fundamental_screener.py — v18.184 基本面轉強進階篩選器

3 維度組合篩選（可獨立開關），純函式設計易與 v18.180 monthly_revenue_screener
與未來技術面 / 籌碼面條件層層疊加。

判斷規則：
  • A【營收雙增】      ：月營收 MoM > 0 且 YoY > 0
  • B【三率三升】      ：毛利率 / 營益率 / 淨利率 三項皆 QoQ > 0 且 YoY > 0
  • C【獲利成長與轉機】：EPS > 0 且（EPS YoY > 0 或 淨利率虧轉盈）

「虧轉盈」獨立判斷：上年同期淨利率 < 0 且本季 > 0 → 直接 True，
不走 YoY 增長率公式，避免基期負值或趨近零導致公式失真。

輸入 schema (per stock)：
    {
      "id": "6770",
      "monthly_revenue": {"mom": 5.2, "yoy": 30.1},
      "quarterly_margins": {
        "gross_margin":     {"current": 50.1, "prev_q": 48.0, "prev_year_q": 47.5},
        "operating_margin": {"current": 25.3, "prev_q": 22.0, "prev_year_q": 20.8},
        "net_margin":       {"current": 18.0, "prev_q": 15.5, "prev_year_q": -1.2},
      },
      "eps": {"current": 2.5, "yoy": 45.0},
    }

防呆原則：所有欄位 None / undefined / 非數字 → 該條件預設 False；絕不拋 Exception。
"""
from __future__ import annotations

import logging as _fs_log
from dataclasses import dataclass, field
from typing import Any, Callable

_logger = _fs_log.getLogger(__name__)


# ════════════════════════════════════════════════════════════════
# Data models
# ════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ConditionResult:
    """單一條件判斷結果。

    is_turnaround=True 標示「虧轉盈」獨立路徑命中（非依賴增長率公式），
    供下游 UI 加註「轉機股」icon。
    """

    code: str
    passed: bool
    reason: str
    is_turnaround: bool = False


@dataclass
class ScreenResult:
    """單股篩選結果。passed = 啟用條件全 True（AND 邏輯）。"""

    stock_id: str
    passed: bool
    conditions: dict[str, ConditionResult] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "stock_id": self.stock_id,
            "passed": self.passed,
            "conditions": {
                k: {
                    "code": v.code,
                    "passed": v.passed,
                    "reason": v.reason,
                    "is_turnaround": v.is_turnaround,
                }
                for k, v in self.conditions.items()
            },
        }

    @property
    def is_turnaround(self) -> bool:
        return any(c.is_turnaround for c in self.conditions.values())


# ════════════════════════════════════════════════════════════════
# Safe accessors
# ════════════════════════════════════════════════════════════════
def _safe_num(obj: Any, *keys: str) -> float | None:
    """深層取數值；遇 None / 缺欄 / 非數字 / NaN 一律回 None，絕不拋 Exception。"""
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
        if cur is None:
            return None
    try:
        v = float(cur)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN
        return None
    return v


# ════════════════════════════════════════════════════════════════
# 條件 A：營收雙增
# ════════════════════════════════════════════════════════════════
def check_revenue_dual_growth(monthly_revenue: Any) -> ConditionResult:
    """月營收 MoM > 0 且 YoY > 0 → True，短期 + 長期動能皆向上。"""
    mom = _safe_num(monthly_revenue, "mom")
    yoy = _safe_num(monthly_revenue, "yoy")
    if mom is None or yoy is None:
        return ConditionResult("A", False, f"月營收缺值 (mom={mom}, yoy={yoy})")
    if mom > 0 and yoy > 0:
        return ConditionResult("A", True, f"MoM={mom:.2f}% / YoY={yoy:.2f}%")
    return ConditionResult("A", False, f"MoM={mom:.2f}% / YoY={yoy:.2f}% 未雙正")


# ════════════════════════════════════════════════════════════════
# 條件 B：三率三升
# ════════════════════════════════════════════════════════════════
_MARGIN_KEYS = ("gross_margin", "operating_margin", "net_margin")
_MARGIN_LABELS = {
    "gross_margin": "毛利率",
    "operating_margin": "營益率",
    "net_margin": "淨利率",
}


def check_triple_margin_up(quarterly_margins: Any) -> ConditionResult:
    """毛利率 / 營益率 / 淨利率 三項皆 QoQ > 0 且 YoY > 0 → True。"""
    if not isinstance(quarterly_margins, dict):
        return ConditionResult("B", False, "無季度毛利率資料")

    fails: list[str] = []
    pass_details: list[str] = []
    for k in _MARGIN_KEYS:
        sub = quarterly_margins.get(k)
        cur = _safe_num(sub, "current")
        prev_q = _safe_num(sub, "prev_q")
        prev_y = _safe_num(sub, "prev_year_q")
        label = _MARGIN_LABELS[k]
        if cur is None or prev_q is None or prev_y is None:
            fails.append(f"{label}缺值")
            continue
        if cur > prev_q and cur > prev_y:
            pass_details.append(
                f"{label} {cur:.2f}% (QoQ +{cur - prev_q:.2f} / YoY +{cur - prev_y:.2f})"
            )
        else:
            fails.append(
                f"{label} {cur:.2f}% (上季 {prev_q:.2f} / 去年同期 {prev_y:.2f})"
            )

    if fails:
        return ConditionResult("B", False, "; ".join(fails))
    return ConditionResult("B", True, "三率三升 ✓ " + "; ".join(pass_details))


# ════════════════════════════════════════════════════════════════
# 條件 C：獲利成長與轉機
# ════════════════════════════════════════════════════════════════
def check_eps_growth_or_turnaround(
    eps: Any,
    quarterly_margins: Any = None,
) -> ConditionResult:
    """EPS > 0 且（EPS YoY > 0 或 淨利率虧轉盈）→ True。

    虧轉盈獨立路徑：上年同期淨利率 < 0 且本季 > 0 → 直接 True，
    不走 YoY 公式（避免基期負值導致 % 失真）。
    """
    cur_eps = _safe_num(eps, "current")
    if cur_eps is None:
        return ConditionResult("C", False, "EPS 缺值")
    if cur_eps <= 0:
        return ConditionResult("C", False, f"EPS={cur_eps:.2f}（本業未獲利）")

    # 路徑 1：淨利率虧轉盈 — 獨立 True 不依賴增長率公式
    nm_cur = _safe_num(quarterly_margins, "net_margin", "current")
    nm_prev_y = _safe_num(quarterly_margins, "net_margin", "prev_year_q")
    if nm_cur is not None and nm_prev_y is not None and nm_prev_y < 0 and nm_cur > 0:
        return ConditionResult(
            "C",
            True,
            f"淨利率虧轉盈 {nm_prev_y:.2f}% → {nm_cur:.2f}%（EPS={cur_eps:.2f}）",
            is_turnaround=True,
        )

    # 路徑 2：EPS YoY > 0
    yoy = _safe_num(eps, "yoy")
    if yoy is None:
        return ConditionResult("C", False, f"EPS={cur_eps:.2f} / YoY 缺值")
    if yoy > 0:
        return ConditionResult("C", True, f"EPS={cur_eps:.2f} / YoY={yoy:.2f}%")
    return ConditionResult("C", False, f"EPS={cur_eps:.2f} / YoY={yoy:.2f}% 未成長")


# ════════════════════════════════════════════════════════════════
# Orchestrator
# ════════════════════════════════════════════════════════════════
ExtraCheck = Callable[[dict], ConditionResult]


def screen_stocks(
    stocks: Any,
    enable_a: bool = True,
    enable_b: bool = True,
    enable_c: bool = True,
    extra_checks: list[ExtraCheck] | None = None,
) -> list[ScreenResult]:
    """主篩選 orchestrator。

    Args:
        stocks: list of {id, monthly_revenue, quarterly_margins, eps}
        enable_a/b/c: 三維度獨立開關；全 False 則只跑 extra_checks
        extra_checks: 擴充點 — 可疊加技術面 / 籌碼面 callable，
                      每個 callable 收 stock dict 回 ConditionResult；
                      個別異常會被吃掉不影響整批

    Returns:
        list[ScreenResult] — 所有股票（含未通過），passed = 啟用條件 AND
    """
    if not isinstance(stocks, list):
        return []

    results: list[ScreenResult] = []
    for s in stocks:
        if not isinstance(s, dict):
            continue
        try:
            sid = str(s.get("id") or "").strip()
            if not sid:
                continue

            conds: dict[str, ConditionResult] = {}
            if enable_a:
                conds["A"] = check_revenue_dual_growth(s.get("monthly_revenue"))
            if enable_b:
                conds["B"] = check_triple_margin_up(s.get("quarterly_margins"))
            if enable_c:
                conds["C"] = check_eps_growth_or_turnaround(
                    s.get("eps"), s.get("quarterly_margins"),
                )

            if extra_checks:
                for fn in extra_checks:
                    try:
                        r = fn(s)
                        if isinstance(r, ConditionResult):
                            conds[r.code] = r
                    except Exception as e:
                        _logger.warning('[fund_screener] extra_check 失敗 (%s): %s: %s',
                                        sid, type(e).__name__, e)

            passed = bool(conds) and all(c.passed for c in conds.values())
            results.append(
                ScreenResult(stock_id=sid, passed=passed, conditions=conds)
            )
        except Exception as e:
            _logger.warning('[fund_screener] 單股 screen 異常: %s: %s', type(e).__name__, e)
            continue

    return results


def filter_passed(results: list[ScreenResult]) -> list[ScreenResult]:
    """便捷工具：抽出 passed=True 的子集。"""
    return [r for r in results if r.passed]


def to_json_rows(results: list[ScreenResult]) -> list[dict]:
    """便捷工具：list[ScreenResult] → JSON-serializable rows。"""
    return [r.to_dict() for r in results]
