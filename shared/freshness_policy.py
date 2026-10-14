"""shared/freshness_policy.py — 引擎輸入的「新鮮度」單一規則來源（L0 純規則，零 I/O）。

批 Z61（freshness SSOT 第一批 F1，2026-10-14）。本批**只交付規則與測試，尚未接線**：
任何呼叫端的行為都沒有改變。

客戶已核准的規則（2026-10-14，Q-z37=A、Q-z38=A）
──────────────────────────────────────────────
- **日頻**（VIX、BIAS240、PCR、外資期貨、加權指數／MA5）：最新有效資料落後超過
  `DAILY_MAX_LAG_TRADING_DAYS` 個**交易日** → 未評估、標「已過期」、不計分；
  不得用無日期的值頂替。以交易日計，不是曆日。
- **月頻**（台灣 PMI、M1B、M2）：依「資料月份 ＋ 該資料正常發布週期」判斷，超過一個
  正常發布期仍無新資料 → 未評估／已過期。⛔ 不得一律寫死 30 天；cache 存活時間（TTL）
  與 freshness 是兩件事。
- 規則集中在本檔，⛔ 不得散落各處硬編碼。

總管裁定的技術定義
──────────────────
日頻：t = 台北當日（呼叫端傳入），a = 資料 as_of。
    N(a, t) = |{ d : a < d ≤ t, d ∈ 交易日 }|（今天若是交易日就計入）
    a is None → MISSING；a > t → UNDETERMINED；N ≤ 上限 → FRESH；N > 上限 → STALE
    休市表不完整 → 區間法（`shared.trading_days.count_trading_days_after`）：
        upper ≤ 上限 → FRESH；lower > 上限 → STALE；其餘 → UNDETERMINED
    VIX（美股）用「平日上界」日曆：(a, t] 內週一～週五都計，不需休市表（偏嚴、不會假新鮮）。
月頻：沿用 `shared.staleness.monthly_release_status`（含 `MONTHLY_PUBLICATION_MARGIN_DAYS`）。
    periods_behind None → UNDETERMINED；≥ 1 → STALE；≤ 0 → FRESH。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Literal, Mapping, Union

from shared.dated_value import AssessedValue, DatedValue
from shared.staleness import MACRO_PUBLICATION_LAG_DAYS, monthly_release_status
from shared.trading_days import (
    CalendarSets,
    count_trading_days_after,
    count_weekdays_after,
)


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"
    UNDETERMINED = "undetermined"


#: 日頻資料可接受的最大落後交易日數。
#: 出處：客戶 2026-10-14 Q-z37=A（「最新有效資料落後超過 3 個交易日 → 未評估、標已過期、不計分」）。
#: ⛔ 本數字只在這裡定義一次；其他地方一律 import 本常數。
DAILY_MAX_LAG_TRADING_DAYS: int = 3

CalendarKind = Literal["twse", "weekday"]
_CALENDAR_KINDS: frozenset[str] = frozenset({"twse", "weekday"})

#: `FreshnessVerdict.lag_unit` 的值。
LAG_UNIT_TRADING_DAY = "trading_day"
LAG_UNIT_WEEKDAY = "weekday"
LAG_UNIT_PERIOD = "period"


@dataclass(frozen=True)
class DailyPolicy:
    """日頻規則。`calendar="twse"` 用台股休市表；`"weekday"` 用平日上界（美股指標）。"""

    max_lag_trading_days: int = DAILY_MAX_LAG_TRADING_DAYS
    calendar: CalendarKind = "twse"

    def __post_init__(self) -> None:
        if self.calendar not in _CALENDAR_KINDS:
            raise ValueError(f"未知的 calendar：{self.calendar!r}（只允許 {sorted(_CALENDAR_KINDS)}）")
        if isinstance(self.max_lag_trading_days, bool) or not isinstance(
                self.max_lag_trading_days, int) or self.max_lag_trading_days < 0:
            raise ValueError(f"max_lag_trading_days 必須是非負整數：{self.max_lag_trading_days!r}")


@dataclass(frozen=True)
class MonthlyPolicy:
    """月頻規則。`lag_key` 必須是 `shared.staleness.MACRO_PUBLICATION_LAG_DAYS` 的 key。"""

    lag_key: str

    def __post_init__(self) -> None:
        if self.lag_key not in MACRO_PUBLICATION_LAG_DAYS:
            raise KeyError(f"月頻 lag_key 未登錄於 MACRO_PUBLICATION_LAG_DAYS：{self.lag_key!r}")


Policy = Union[DailyPolicy, MonthlyPolicy]

#: 引擎輸入名 → 新鮮度規則。key 對齊 `src/services/macro_state_locker._ENGINE_NUMERIC_INPUTS`
#: ＋ bool 輸入 `Index_Below_MA5`（一致性由 tests/test_batch_z61.py 守住）。
#: ⚠️ `"ism_pmi"` 是歷史誤稱：該 key 在 `MACRO_PUBLICATION_LAG_DAYS` 內實為**台灣 PMI**（CIER）。
FRESHNESS_POLICY: Mapping[str, Policy] = MappingProxyType({
    "VIX_Index":           DailyPolicy(calendar="weekday"),
    "BIAS240_pct":         DailyPolicy(calendar="twse"),
    "PCR":                 DailyPolicy(calendar="twse"),
    "Futures_Net_Short":   DailyPolicy(calendar="twse"),
    "Index_Below_MA5":     DailyPolicy(calendar="twse"),
    "ISM_PMI_or_OECD_CLI": MonthlyPolicy("ism_pmi"),
    "PMI_Prev_Month":      MonthlyPolicy("ism_pmi"),
    "M1B_YoY_pct":         MonthlyPolicy("m1b_m2"),
    "M2_YoY_pct":          MonthlyPolicy("m1b_m2"),
})


@dataclass(frozen=True)
class FreshnessVerdict:
    """新鮮度判定。

    - `lag`：日頻為落後交易日（或平日）數，月頻為落後發布期數；判不出 → None。
      日頻走區間法時：FRESH 取上界（至多）、STALE 取下界（至少）。
    - `overdue_days`：僅月頻；下一期已超過原定發布日幾天（仍在緩衝內），供日後呈現「上游遲到」。
    """

    status: FreshnessStatus
    lag: int | None
    lag_unit: str
    overdue_days: int | None
    reason: str
    evaluated_on: date


# ── helpers ─────────────────────────────────────────────────────────────


def _check_today(today: date) -> None:
    if isinstance(today, datetime) or not isinstance(today, date):
        raise TypeError(f"today 必須是 datetime.date（台北當日）：{today!r}")


def _fmt_day(d: date, today: date) -> str:
    """同年寫 'MM/DD'，跨年寫 'YYYY/MM/DD'（避免 12/31 與 01/02 被誤讀成同一年）。"""
    return d.strftime("%m/%d") if d.year == today.year else d.strftime("%Y/%m/%d")


def _unknown_reason(cal: CalendarSets | None, unknown_days: tuple[date, ...]) -> str:
    if cal is None:
        return "休市表取不到"
    parts: list[str] = []
    _years = sorted({d.year for d in unknown_days if d.year not in cal.covered_years})
    if _years:
        parts.append(f"休市表未涵蓋 {'、'.join(str(y) for y in _years)} 年")
    _unc = [d for d in unknown_days if d.year in cal.covered_years]
    if _unc:
        parts.append(f"休市表內 {'、'.join(d.isoformat() for d in _unc)} 無法分類")
    return "；".join(parts)


# ── 日頻 ─────────────────────────────────────────────────────────────────


def assess_daily(as_of: date | None, *, today: date, calendar: CalendarSets | None,
                 max_lag: int = DAILY_MAX_LAG_TRADING_DAYS,
                 calendar_kind: CalendarKind = "twse") -> FreshnessVerdict:
    """日頻新鮮度。`calendar` 只在 `calendar_kind="twse"` 時使用。"""
    _check_today(today)
    if calendar_kind not in _CALENDAR_KINDS:
        raise ValueError(f"未知的 calendar_kind：{calendar_kind!r}")
    unit = LAG_UNIT_WEEKDAY if calendar_kind == "weekday" else LAG_UNIT_TRADING_DAY
    if as_of is None:
        return FreshnessVerdict(FreshnessStatus.MISSING, None, unit, None,
                                "無資料日期，不得以無日期的值計分", today)
    if isinstance(as_of, datetime) or not isinstance(as_of, date):
        raise TypeError(f"as_of 必須是 datetime.date：{as_of!r}")
    if as_of > today:
        return FreshnessVerdict(
            FreshnessStatus.UNDETERMINED, None, unit, None,
            f"資料日 {_fmt_day(as_of, today)} 晚於評估日 {_fmt_day(today, today)}，無法判定新鮮度",
            today)

    day_s = _fmt_day(as_of, today)
    if calendar_kind == "weekday":
        n = count_weekdays_after(as_of, today)
        status = FreshnessStatus.FRESH if n <= max_lag else FreshnessStatus.STALE
        return FreshnessVerdict(
            status, n, unit, None,
            f"資料日 {day_s}，落後 {n} 個平日（上限 {max_lag}；美股以平日計，不扣美國假日）",
            today)

    cnt = count_trading_days_after(as_of, today, calendar)
    if not cnt.unknown_days:
        n = cnt.lower
        status = FreshnessStatus.FRESH if n <= max_lag else FreshnessStatus.STALE
        return FreshnessVerdict(status, n, unit, None,
                                f"資料日 {day_s}，落後 {n} 個交易日（上限 {max_lag}）", today)

    why = _unknown_reason(calendar, cnt.unknown_days)
    if cnt.upper <= max_lag:
        return FreshnessVerdict(
            FreshnessStatus.FRESH, cnt.upper, unit, None,
            f"資料日 {day_s}，落後至多 {cnt.upper} 個交易日（上限 {max_lag}；{why}，以上界判定）",
            today)
    if cnt.lower > max_lag:
        return FreshnessVerdict(
            FreshnessStatus.STALE, cnt.lower, unit, None,
            f"資料日 {day_s}，落後至少 {cnt.lower} 個交易日（上限 {max_lag}；{why}，以下界判定）",
            today)
    return FreshnessVerdict(
        FreshnessStatus.UNDETERMINED, None, unit, None,
        f"{why}，無法判定新鮮度（資料日 {day_s}，落後 {cnt.lower}～{cnt.upper} 個交易日，上限 {max_lag}）",
        today)


# ── 月頻 ─────────────────────────────────────────────────────────────────


def assess_monthly(data_month: date | None, *, today: date, lag_key: str) -> FreshnessVerdict:
    """月頻新鮮度（沿用 `shared.staleness.monthly_release_status`，不另寫數學）。"""
    _check_today(today)
    if lag_key not in MACRO_PUBLICATION_LAG_DAYS:
        raise KeyError(f"月頻 lag_key 未登錄於 MACRO_PUBLICATION_LAG_DAYS：{lag_key!r}")
    unit = LAG_UNIT_PERIOD
    if data_month is None:
        return FreshnessVerdict(FreshnessStatus.MISSING, None, unit, None,
                                "無資料月份，不得以無日期的值計分", today)
    if isinstance(data_month, datetime) or not isinstance(data_month, date):
        raise TypeError(f"data_month 必須是 datetime.date：{data_month!r}")
    if data_month.day != 1:
        raise ValueError(f"data_month 必須是月初（收到 {data_month}）")
    month_s = data_month.strftime("%Y-%m")
    if data_month > today:
        return FreshnessVerdict(
            FreshnessStatus.UNDETERMINED, None, unit, None,
            f"資料月 {month_s} 晚於評估日 {today.isoformat()}，無法判定新鮮度", today)

    behind, overdue = monthly_release_status(data_month, indicator=lag_key, today=today)
    if behind is None:
        return FreshnessVerdict(FreshnessStatus.UNDETERMINED, None, unit, None,
                                f"資料月 {month_s}，無法判定落後期數", today)
    if behind >= 1:
        return FreshnessVerdict(FreshnessStatus.STALE, behind, unit, overdue,
                                f"資料月 {month_s}，已落後 {behind} 個發布期", today)
    reason = f"資料月 {month_s}，為當期"
    if overdue:
        reason += f"；下一期已逾原定發布日 {overdue} 天（仍在緩衝內）"
    return FreshnessVerdict(FreshnessStatus.FRESH, behind, unit, overdue, reason, today)


# ── 分派 ─────────────────────────────────────────────────────────────────


def assess(dv: DatedValue, *, today: date, calendar: CalendarSets | None) -> AssessedValue:
    """依 `FRESHNESS_POLICY[dv.series_key]` 分派；key 未登錄 → `KeyError`。

    設定錯誤（日頻帶 data_month、月頻帶 as_of）→ `ValueError`。
    值為 None → MISSING（原因取 `dv.missing_reason`）。
    """
    try:
        policy = FRESHNESS_POLICY[dv.series_key]
    except KeyError:
        raise KeyError(f"series_key 未登錄於 FRESHNESS_POLICY：{dv.series_key!r}") from None

    if isinstance(policy, DailyPolicy):
        if dv.data_month is not None:
            raise ValueError(f"{dv.series_key} 為日頻，卻帶了 data_month={dv.data_month}（應給 as_of）")
        unit = LAG_UNIT_WEEKDAY if policy.calendar == "weekday" else LAG_UNIT_TRADING_DAY
    else:
        if dv.as_of is not None:
            raise ValueError(f"{dv.series_key} 為月頻，卻帶了 as_of={dv.as_of}（應給 data_month）")
        unit = LAG_UNIT_PERIOD

    if dv.value is None:
        _check_today(today)
        reason = dv.missing_reason or "無值"
        return AssessedValue(dv, FreshnessVerdict(FreshnessStatus.MISSING, None, unit, None,
                                                  reason, today))

    if isinstance(policy, DailyPolicy):
        verdict = assess_daily(dv.as_of, today=today, calendar=calendar,
                               max_lag=policy.max_lag_trading_days,
                               calendar_kind=policy.calendar)
    else:
        verdict = assess_monthly(dv.data_month, today=today, lag_key=policy.lag_key)
    return AssessedValue(dv, verdict)


# ── PMI 上月 ────────────────────────────────────────────────────────────


def is_previous_data_month(cur: date, prev: date) -> bool:
    """`prev` 是否恰好是 `cur` 的上一個資料月（只看年月；跨年：2026-01 的上一月是 2025-12）。"""
    return (cur.year * 12 + cur.month) - (prev.year * 12 + prev.month) == 1
