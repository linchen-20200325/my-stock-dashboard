"""shared/trading_days.py — 交易日判定與「落後幾個交易日」計數（L0 純規則，零 I/O）。

批 Z61（freshness SSOT 第一批 F1，2026-10-14）：自 L2 `src/compute/trading_calendar.py`
下沉 `classify_day` / `next_trading_day` 及其型別與常數，讓 L0 `shared/freshness_policy.py`
能在不違反 §8.2「L0 不得依賴任何 L1+」的前提下使用同一套交易日規則。
原 L2 檔改為 re-export，既有 import 路徑與行為一律不變。

單日判定規則（逐條，順序即優先序；批 D5 原文照搬）::

    1. 該日所在年份不在休市表涵蓋範圍  → 無法判定（⛔ 不猜「平日就是交易日」）
    2. 該日在表內但無法分類            → 無法判定
    3. 該日在表內標為「休市」          → 非交易日
    4. 該日在表內標為「交易」          → 交易日（含週末補行交易的情形）
    5. 週六、週日                      → 非交易日
    6. 其餘平日                        → 交易日

⚠️ 已知限制：**臨時休市（颱風等）不在官方年度表內** —— 規則 6 在那一天會判「交易日」。
這是來源本身給不出來的資訊，不是本檔可以補的；呼叫端若要顯示，須自行揭露。

區間計數（批 Z61 新增，總管裁定）::

    N(a, t) = |{ d : a < d ≤ t, d ∈ 交易日 }|        （今天若是交易日就計入，與時刻無關）
    休市表不完整或取不到時改用區間：
        TRADING      → lower、upper 各 +1
        CLOSED       → 都不加
        UNDETERMINED → 只有 upper +1     （未涵蓋年份、無法分類、cal 為 None）
    ⛔ 台股日曆不得退回「只扣週末」—— `cal is None` 時所有日子都是未知。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

#: 往後找下一個交易日最多看幾天。台股最長連假（農曆春節＋前後無交易日）約 9～10 天；
#: 取 31 只為「防無限迴圈」—— 超過就回「無法判定」，⛔ 不是業務門檻。
NEXT_TRADING_DAY_SEARCH_DAYS: int = 31

#: 判定結果三值。
TRADING: str = "trading"
CLOSED: str = "closed"
UNDETERMINED: str = "undetermined"


@dataclass(frozen=True)
class DayVerdict:
    """單日判定。`status == UNDETERMINED` 時 `reason` 必有值。"""

    day: date
    status: str
    reason: str = ""


@dataclass(frozen=True)
class CalendarSets:
    """休市表的純集合形式（L0 不認識 L1 的休市表型別，只吃集合）。"""

    closed: frozenset[date]
    trading: frozenset[date]
    unclassified: frozenset[date]
    covered_years: frozenset[int]


@dataclass(frozen=True)
class TradingDayCount:
    """(a, t] 區間內的交易日數上下界。

    `lower == upper` ⇔ 區間內每一天都判得出來（`unknown_days` 為空）。
    """

    lower: int
    upper: int
    unknown_days: tuple[date, ...]


def classify_day(day: date, *, closed: Iterable[date], trading: Iterable[date],
                 unclassified: Iterable[date], covered_years: Iterable[int]) -> DayVerdict:
    """依檔頭六條規則判定單日。"""
    if day.year not in set(covered_years):
        return DayVerdict(day, UNDETERMINED,
                          f"休市表未涵蓋 {day.year} 年（表內年份：{sorted(set(covered_years))}）")
    if day in set(unclassified):
        return DayVerdict(day, UNDETERMINED, f"休市表內 {day} 這一列無法分類為休市或交易")
    if day in set(closed):
        return DayVerdict(day, CLOSED)
    if day in set(trading):
        return DayVerdict(day, TRADING)
    if day.weekday() >= 5:
        return DayVerdict(day, CLOSED)
    return DayVerdict(day, TRADING)


def next_trading_day(after: date, *, closed: Iterable[date], trading: Iterable[date],
                     unclassified: Iterable[date], covered_years: Iterable[int],
                     ) -> DayVerdict:
    """`after` 之後（不含當天）的第一個交易日。

    途中遇到任何一天「無法判定」→ 整體回 `UNDETERMINED`（⛔ 不跳過它往後找 ——
    跳過等於假設它是休市）。找不到（超過 `NEXT_TRADING_DAY_SEARCH_DAYS`）也回 `UNDETERMINED`。
    成功時回 `DayVerdict(該日, TRADING)`。
    """
    _closed, _trading = frozenset(closed), frozenset(trading)
    _unc, _years = frozenset(unclassified), frozenset(covered_years)
    d = after
    for _ in range(NEXT_TRADING_DAY_SEARCH_DAYS):
        d = d + timedelta(days=1)
        v = classify_day(d, closed=_closed, trading=_trading,
                         unclassified=_unc, covered_years=_years)
        if v.status == TRADING:
            return v
        if v.status == UNDETERMINED:
            return DayVerdict(after, UNDETERMINED, f"往後找下一個交易日時：{v.reason}")
    return DayVerdict(after, UNDETERMINED,
                      f"{after} 之後 {NEXT_TRADING_DAY_SEARCH_DAYS} 天內找不到交易日")


def _check_span(as_of: date, today: date) -> None:
    """兩端必須是純 `date`（⛔ datetime 帶時刻／時區語意，不猜），且 as_of ≤ today。"""
    for _name, _v in (("as_of", as_of), ("today", today)):
        if isinstance(_v, datetime) or not isinstance(_v, date):
            raise TypeError(f"{_name} 必須是 datetime.date（不得為 datetime 或其他型別）：{_v!r}")
    if as_of > today:
        raise ValueError(f"as_of {as_of} 晚於 today {today}，無法計算落後交易日數")


def _days_after(as_of: date, today: date) -> Iterable[date]:
    """(as_of, today] 內的每一天，遞增。"""
    d = as_of + timedelta(days=1)
    while d <= today:
        yield d
        d = d + timedelta(days=1)


def count_trading_days_after(as_of: date, today: date,
                             cal: CalendarSets | None) -> TradingDayCount:
    """(as_of, today] 內的台股交易日數上下界（見檔頭「區間計數」）。

    `cal is None`（休市表取不到）⇒ 區間內每一天都是未知 ⇒ lower 0、upper = 曆日數。
    as_of > today ⇒ `ValueError`。
    """
    _check_span(as_of, today)
    lower = upper = 0
    unknown: list[date] = []
    for d in _days_after(as_of, today):
        if cal is None:
            status = UNDETERMINED
        else:
            status = classify_day(d, closed=cal.closed, trading=cal.trading,
                                  unclassified=cal.unclassified,
                                  covered_years=cal.covered_years).status
        if status == TRADING:
            lower += 1
            upper += 1
        elif status == UNDETERMINED:
            upper += 1
            unknown.append(d)
        # CLOSED：都不加
    return TradingDayCount(lower=lower, upper=upper, unknown_days=tuple(unknown))


def count_weekdays_after(as_of: date, today: date) -> int:
    """(as_of, today] 內週一～週五的天數（週六、週日不計，不看任何休市表）。

    用於美股指標（VIX）的「平日上界」：美股週末必不交易，平日上界只會**高估**落後天數，
    屬偏嚴、不會產生假新鮮。as_of > today ⇒ `ValueError`。
    """
    _check_span(as_of, today)
    return sum(1 for d in _days_after(as_of, today) if d.weekday() < 5)
