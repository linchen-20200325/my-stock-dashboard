"""src/compute/trading_calendar.py — 「這一天是不是台股交易日」純函式（L2，零 I/O）。

批 D5（2026-10-02，HANDOFF B4 (a)）。資料由 L1 `src/data/stock/twse_holiday_fetcher.py`
供給，本檔只吃**純集合**（不 import L1 的型別），可單獨測。

⚠️ 批 Z61（2026-10-14，freshness SSOT F1）：實作已下沉至 L0 `shared/trading_days.py`
（L0 `shared/freshness_policy.py` 需要同一套交易日規則，而 L0 不得 import L2）。
本檔改為 **re-export**，保留既有 import 路徑（`from src.compute import trading_calendar`）
與既有行為；判定規則、已知限制請見 `shared/trading_days.py` 檔頭。
⛔ 不要在本檔另寫一份實作 —— 兩份會漂移。
"""
from __future__ import annotations

from shared.trading_days import (  # noqa: F401 — re-export
    CLOSED,
    NEXT_TRADING_DAY_SEARCH_DAYS,
    TRADING,
    UNDETERMINED,
    DayVerdict,
    classify_day,
    next_trading_day,
)

__all__ = [
    "CLOSED",
    "NEXT_TRADING_DAY_SEARCH_DAYS",
    "TRADING",
    "UNDETERMINED",
    "DayVerdict",
    "classify_day",
    "next_trading_day",
]
