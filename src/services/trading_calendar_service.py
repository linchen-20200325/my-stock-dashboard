"""src/services/trading_calendar_service.py — 「今天台股開不開市」編排（L3）。

批 D5（2026-10-02，客戶裁示頁1⑤「接休市日曆」；HANDOFF B4 (a)）。

流程：台北當日（Asia/Taipei）→ L1 取證交所休市表 → L2 判定今天＋下一個交易日。
**本檔不吞失敗**：拿不到休市表時回 `TradingDayStatus(error=...)`，`is_trading_day`
為 `None`（⛔ 不預設成「交易日」，也不退回「只看週末」—— 那就是在猜，§1）。

⚠️ 畫面尚未接線：今天頁「交易日」格的休市態／失敗態文案沒有既有字樣（K1），
本批只交付資料層＋判定，L5 待文案規格（見批 D5 交付報告的「需規格」）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from src.compute import trading_calendar as _tc
from src.data.stock import twse_holiday_fetcher as _hf

#: 台北時區（§4.5 repo 慣例：`timezone(timedelta(hours=8))`，台灣無日光節約）。
TAIPEI_TZ = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class TradingDayStatus:
    """今天的開市狀態 ＋ provenance。

    `error` 非 None ⇔ 無法判定（此時 `is_trading_day` 與 `next_trading_day` 皆為 None）。
    `is_trading_day` 有值但 `next_trading_day` 為 None ⇔ 今天判得出、下一個交易日判不出
    （原因在 `next_reason`）。
    """

    today: date
    is_trading_day: bool | None
    next_trading_day: date | None
    error: str | None = None
    next_reason: str = ""
    source: str = _hf.SOURCE_ID
    fetched_at: datetime | None = None


def taipei_today(now: datetime | None = None) -> date:
    """台北日曆日。`now` 必須帶時區（naive 一律 raise —— 不猜它是哪個時區）。"""
    _now = now if now is not None else datetime.now(timezone.utc)
    if _now.tzinfo is None:
        raise ValueError("now 必須是 timezone-aware datetime")
    return _now.astimezone(TAIPEI_TZ).date()


def get_today_trading_status(now: datetime | None = None) -> TradingDayStatus:
    """今天（台北）是不是台股交易日，與下一個交易日。"""
    today = taipei_today(now)
    try:
        cal = _hf.fetch_twse_holiday_calendar(taipei_year=today.year)
    except _hf.HolidayCalendarUnavailable as e:
        return TradingDayStatus(today=today, is_trading_day=None,
                                next_trading_day=None, error=str(e))
    sets = dict(closed=cal.dates_of("closed"), trading=cal.dates_of("trading"),
                unclassified=cal.dates_of("unclassified"),
                covered_years=cal.covered_years)
    v = _tc.classify_day(today, **sets)
    if v.status == _tc.UNDETERMINED:
        print(f"[trading_calendar_service] 今天無法判定：{v.reason}")
        return TradingDayStatus(today=today, is_trading_day=None, next_trading_day=None,
                                error=v.reason, source=cal.source, fetched_at=cal.fetched_at)
    nxt = _tc.next_trading_day(today, **sets)
    ok_next = nxt.status == _tc.TRADING
    return TradingDayStatus(
        today=today,
        is_trading_day=(v.status == _tc.TRADING),
        next_trading_day=(nxt.day if ok_next else None),
        next_reason=("" if ok_next else nxt.reason),
        source=cal.source, fetched_at=cal.fetched_at,
    )
