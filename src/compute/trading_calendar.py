"""src/compute/trading_calendar.py — 「這一天是不是台股交易日」純函式（L2，零 I/O）。

批 D5（2026-10-02，HANDOFF B4 (a)）。資料由 L1 `src/data/stock/twse_holiday_fetcher.py`
供給，本檔只吃**純集合**（不 import L1 的型別），可單獨測。

判定規則（逐條，順序即優先序）::

    1. 該日所在年份不在休市表涵蓋範圍  → 無法判定（⛔ 不猜「平日就是交易日」）
    2. 該日在表內但無法分類            → 無法判定
    3. 該日在表內標為「休市」          → 非交易日
    4. 該日在表內標為「交易」          → 交易日（含週末補行交易的情形）
    5. 週六、週日                      → 非交易日
    6. 其餘平日                        → 交易日

⚠️ 已知限制：**臨時休市（颱風等）不在官方年度表內** —— 規則 6 在那一天會判「交易日」。
這是來源本身給不出來的資訊，不是本檔可以補的；呼叫端若要顯示，須自行揭露。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
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
