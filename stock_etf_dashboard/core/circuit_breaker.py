"""L0 Infra — 防呆熔斷器 + 資料置信度 + 除權息還原 (資料憲法 §1 / §4.6).

三件事：
1. Fail Loud：缺料/壞假設一律 raise，不靜默補值。
2. Confidence Score (0~100)：資料齊全度 × 新鮮度 × 來源可靠度；< 70 鎖定建議。
3. 除權息防呆：除息開低跳空 → 還原參考價,避免誤觸移動停損。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import constants as C


class FailLoudError(RuntimeError):
    """§1：寧可炸掉,不可造假。缺料/壞假設時拋出。"""


def require(condition: bool, message: str) -> None:
    """條件不成立就 raise FailLoudError（帶清楚原因）。"""
    if not condition:
        raise FailLoudError(message)


def isclose(a: float, b: float) -> bool:
    """§4.3 浮點比較統一容差,禁止 ==。"""
    return math.isclose(a, b, rel_tol=C.FLOAT_REL_TOL, abs_tol=C.FLOAT_ABS_TOL)


# ── 資料置信度 ──────────────────────────────────────────────────────────
def completeness_score(n_present: int, n_expected: int) -> float:
    """齊全度 ∈ [0,1]。n_expected<=0 視為無從判斷 → 0。"""
    if n_expected <= 0:
        return 0.0
    return max(0.0, min(1.0, n_present / n_expected))


def freshness_score(age_days: float) -> float:
    """新鮮度 ∈ [0,1]。<=FULL 滿分,>=ZERO 零分,之間線性衰減。"""
    full, zero = C.FRESHNESS_FULL_DAYS, C.FRESHNESS_ZERO_DAYS
    if age_days <= full:
        return 1.0
    if age_days >= zero:
        return 0.0
    return 1.0 - (age_days - full) / (zero - full)


@dataclass(frozen=True)
class ConfidenceReport:
    completeness: float          # 0~1
    freshness: float             # 0~1
    source_reliability: float    # 0~1（1=主源, 低=代理/備援）
    score: float                 # 0~100
    is_locked: bool              # score < 門檻 → 鎖定建議
    reason: str

    def as_badge(self) -> str:
        state = "🔒鎖定" if self.is_locked else "✅可用"
        return f"{state} 置信度 {self.score:.0f}/100"


def compute_confidence(
    *,
    completeness: float,
    freshness: float,
    source_reliability: float,
) -> ConfidenceReport:
    """三子項加權 → 0~100；低於門檻鎖定。子項皆須 ∈ [0,1]。"""
    for nm, v in (("completeness", completeness), ("freshness", freshness),
                  ("source_reliability", source_reliability)):
        require(0.0 <= v <= 1.0, f"confidence 子項 {nm}={v} 不在 [0,1]")

    score = 100.0 * (
        C.CONF_WEIGHT_COMPLETENESS * completeness
        + C.CONF_WEIGHT_FRESHNESS * freshness
        + C.CONF_WEIGHT_SOURCE * source_reliability
    )
    locked = score < C.CONFIDENCE_LOCK_THRESHOLD
    bits = []
    if completeness < 1.0:
        bits.append(f"資料不齊({completeness:.0%})")
    if freshness < 1.0:
        bits.append(f"資料偏舊({freshness:.0%})")
    if source_reliability < 1.0:
        bits.append("使用備援源")
    reason = "；".join(bits) or "資料完整且新鮮"
    return ConfidenceReport(
        completeness=completeness,
        freshness=freshness,
        source_reliability=source_reliability,
        score=round(score, 1),
        is_locked=locked,
        reason=reason,
    )


# ── 除權息防呆 ──────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ExDividendGuard:
    is_ex_dividend: bool
    gap_pct: float               # 開盤相對前收跌幅（+ 為下跌）
    adjusted_low: float          # 還原後的當日低點（加回配息）
    stop_triggered: bool         # 用還原價判斷是否真的觸損
    note: str


def ex_dividend_guard(
    *,
    prev_close: float,
    today_open: float,
    today_low: float,
    dividend_amount: float,
    stop_price: float | None,
) -> ExDividendGuard:
    """除權息開低還原：避免除息跳空誤觸停損。

    邏輯：若當日有配息且開盤相對前收跌幅 >= 門檻 → 判定除息跳空。
    還原 = 把配息「加回」當日低點,得到等值於除息前的比較基準,
    再拿還原低點 vs 停損價判斷是否真正跌破。
    """
    require(prev_close > 0, f"prev_close 必須 > 0,得到 {prev_close}")
    require(today_low > 0 and today_open > 0, "today_open/low 必須 > 0")
    require(dividend_amount >= 0, f"dividend_amount 不可為負: {dividend_amount}")

    gap_pct = (prev_close - today_open) / prev_close * 100.0
    is_ex = dividend_amount > 0 and gap_pct >= C.EX_DIVIDEND_GAP_PCT
    adjusted_low = today_low + dividend_amount if is_ex else today_low

    if stop_price is None:
        triggered = False
        note = "無停損設定"
    elif is_ex:
        triggered = adjusted_low <= stop_price
        note = (f"除息跳空 {gap_pct:.1f}%,還原低點 {adjusted_low:.2f} "
                f"vs 停損 {stop_price:.2f}")
    else:
        triggered = today_low <= stop_price
        note = f"一般交易,低點 {today_low:.2f} vs 停損 {stop_price:.2f}"

    return ExDividendGuard(
        is_ex_dividend=is_ex,
        gap_pct=round(gap_pct, 2),
        adjusted_low=round(adjusted_low, 4),
        stop_triggered=triggered,
        note=note,
    )
