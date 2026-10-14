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
    資料月 ≥ 今天所在月份 → UNDETERMINED（該月尚未結束、不可能已發布，日期可疑）；
    periods_behind None → UNDETERMINED；≥ 1 → STALE；≤ 0 → FRESH。
PMI 前一資料月（批 Z63，客戶 2026-10-14 Q-z34 Q1=B）：⛔ 不獨立套月頻規則 ——
    前一資料月本來就比當期落後一期，獨立判會在正常情況下被判 STALE（例：今天 10/14，
    當期 9 月 FRESH、前月 8 月獨立判是 STALE），「PMI 連兩月低於 48」紅線就永遠無法評估。
    改用 `PreviousMonthOfPolicy` ＋ `assess_previous_month(prev_dv, anchor)`：**跟著當期走** ——
    當期不是 FRESH → UNDETERMINED；值缺／非有限 → MISSING；沒有資料月 → MISSING；
    不是當期的恰好前一個資料月 → MISSING（「前一資料月不符」）；其餘 → FRESH。
    ⛔ 不得用本月值、session_state、上次按按鈕的值頂替前月（門檻 48、上限 40% 不在本檔、未改）。

⭐ 快取存活時間 ≠ 資料新鮮度（批 Z63，客戶 2026-10-14 Q-z38=A）
──────────────────────────────────────────────────────────────
`src/data/macro/macro_core.py` 的 PMI 取數裡有兩個「90 天」：
- 各來源的 `max_age_days=90`：**來源合理性篩選**（資料月月初距今超過 90 天的頁面不收）；
- `_MACRO_CACHE_TTL_DAYS=90`：**快取保留**（`cached_at` 距今未滿 90 天的快照才回）。
兩者都**不代表資料仍有效**。計分一律由本檔 `assess_monthly` 依**資料月**判斷 ——
快取昨天才寫入、但資料月已落後 2 期 → 照樣 STALE（tests/test_batch_z63.py 守住）。
90 天必須 ≥ 月頻新鮮窗的最大天數（`ism_pmi` 實算為 69 天：資料月 M 月初到 STALE 起點前一天，
31＋31＋7），保證篩選不會比本規則先把仍新鮮的資料擋掉（同測試檔守住）。

已知待接線事項（留給接線批，本批未處理）
──────────────────────────────────────
⭐ **計分輸入的 freshness 一律以本檔 `FRESHNESS_POLICY` 為準**（日頻 = `DAILY_MAX_LAG_TRADING_DAYS`
個**交易日**）。下表是 repo 內現存的「日頻 × 曆日」規則（批 Z62 依第 30 次自檢 B 組盤點登記，
**只登記、不改**）。它們各有用途，⛔ 接線時不得拿其中任何一條當成第二套計分新鮮度門檻，
也 ⛔ 不得因為「跟本檔重複」就順手刪掉 —— 用途不同。

==========================================================  =======  =================================================
規則（檔案::名稱）                                           值        用途／接線時的處置
==========================================================  =======  =================================================
`shared/staleness.py::STALE_DAYS_DAILY`                     7 曆日   **顯示用**（資料診斷頁、健康檢查頁的日頻紅燈）
                                                                     ＋ **AI 標記**（`ai_qa_service`、`macro_cache_reader`
                                                                     經 `stale_days_threshold('daily')`）。不是計分規則。
`shared/staleness.py::MACRO_VERDICT_MAX_AGE_DAYS`           7 曆日   **裁決有效期（決策閘，客戶已核准）**：
                                                                     `macro_state_locker.macro_state_is_expired` 用它判斷
                                                                     `macro_state.json` 的「系統風險上限」天花板是否仍生效
                                                                     （`ai_qa_service` 亦引用）—— 無法計算時保留 7 天內最近
                                                                     一次有效的上限。與**輸入資料**的 freshness 是兩回事，
                                                                     **接線時保留**。（批 Z61 檔頭把它寫成「診斷頁曆日尺」
                                                                     是錯的，批 Z62 更正。）
`src/services/market_strategy.py::get_market_assessment`    7 曆日   inline magic number `_days_old > 7`：^TWII 末筆超過 7 個
  （`_days_old > 7`）                                                自然日 → 整份評估回 None，閘住 ^TWII 位階（regime）與
                                                                     MA5（`mkt_info` 整份消失），與本檔「逐項判缺」語意不同。
                                                                     接線批須決定它與 `Index_Below_MA5` 判定的關係（舊 UI 依賴）。
`src/data/macro/leading_indicators.py::_STALE_MAX_AGE_MIN`  3×24×60  **快取 pickle 的存活上限**（上游當次抓空時，最多沿用多舊
                                                            分鐘     的 pickle，fallback 用），按**日曆天**算，不是計分規則。
`shared/signal_thresholds.py::EXTREME_STALE_MAX_CALENDAR_DAYS`  10   極端風險兩腿（^TWII 20 日跌幅、外資 5 日賣超）來源 parquet
                                                            曆日     最多可落後的天數（`macro_cache_reader`）。
`shared/global_lead_markets.py::LEAD_QUOTE_MAX_AGE_DAYS`    5 曆日   領先市場報價可接受的最大落後（`macro_cache_reader`），
                                                                     超過判為未取得。
`shared/sector_flow_thresholds.py::`                        4 曆日   **顯示用**：板塊資金潮汐快取 metadata 距今的過期門檻
  `SECTOR_FLOW_STALE_MAX_CALENDAR_DAYS`                              （`src/data/sector_flow/reader.py` → `is_stale`）。
`shared/data_freshness.py::FROZEN_STALE_PERIODS_LEADING`    3 期     **凍結值判定**（連續 N 期一階差分為 0），量的是「值有沒有
                                                                     動」而不是「資料多舊」—— 與本檔性質不同。
==========================================================  =======  =================================================

其他待接線事項：

1. L1 休市表 → `shared.trading_days.CalendarSets` 的轉換：批 Z62 已補 L1
   `HolidayCalendar.as_sets()`（四個集合與 L3 `trading_calendar_service` 現行傳給 `classify_day`
   的參數逐一相同，測試守住）；「由哪一層呼叫、休市表取不到時傳 None」仍留給接線批。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from typing import Literal, Mapping, Union

from shared.dated_value import AssessedValue, DatedValue, _is_scorable
from shared.staleness import MACRO_PUBLICATION_LAG_DAYS, monthly_release_status
from shared.station_specs import INVALID_DATA_TEXT  # 批 Z62：資料異常核准句（L0 SSOT）
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

#: 值不是有限數值時的缺值原因：沿用 L0 `shared.station_specs.INVALID_DATA_TEXT`（客戶 2026-10-13
#: 裁示 B 核准句「{項目}資料異常，無法計算，不下結論。」，⛔ 不另寫一份）。`item` 暫填 series_key，
#: UI 呈現時再對應中文名。
NON_FINITE_REASON_FMT: str = INVALID_DATA_TEXT

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


@dataclass(frozen=True)
class PreviousMonthOfPolicy:
    """「當期的前一資料月」規則（批 Z63）。⛔ 不獨立判新鮮度，一律改用 `assess_previous_month`。

    `anchor_key`：當期那一項的引擎輸入名（必須在 `FRESHNESS_POLICY` 內且為 `MonthlyPolicy`，
    由 tests/test_batch_z63.py 守住；這裡無法在定義時檢查 —— 規則表在本類別之後才建）。
    """

    anchor_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.anchor_key, str) or not self.anchor_key:
            raise ValueError(f"anchor_key 必須是非空字串：{self.anchor_key!r}")


Policy = Union[DailyPolicy, MonthlyPolicy, PreviousMonthOfPolicy]

#: 引擎輸入名 → 新鮮度規則。key 對齊 `src/services/macro_state_locker._ENGINE_NUMERIC_INPUTS`
#: ＋ bool 輸入 `Index_Below_MA5`（一致性由 tests/test_batch_z61.py 守住）。
#: ⚠️ `"ism_pmi"` 是歷史誤稱：該 key 在 `MACRO_PUBLICATION_LAG_DAYS` 內實為**台灣 PMI**（CIER）。
#: 批 Z63：`PMI_Prev_Month` 由 `MonthlyPolicy("ism_pmi")` 改為 `PreviousMonthOfPolicy` ——
#:   前一資料月獨立套月頻規則會在正常情況下被判 STALE（見檔頭「PMI 前一資料月」）。
FRESHNESS_POLICY: Mapping[str, Policy] = MappingProxyType({
    "VIX_Index":           DailyPolicy(calendar="weekday"),
    "BIAS240_pct":         DailyPolicy(calendar="twse"),
    "PCR":                 DailyPolicy(calendar="twse"),
    "Futures_Net_Short":   DailyPolicy(calendar="twse"),
    "Index_Below_MA5":     DailyPolicy(calendar="twse"),
    "ISM_PMI_or_OECD_CLI": MonthlyPolicy("ism_pmi"),
    "PMI_Prev_Month":      PreviousMonthOfPolicy(anchor_key="ISM_PMI_or_OECD_CLI"),
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
    # 批 Z62（Z61 QA 低嚴重度遺留）：與 `DailyPolicy.__post_init__` 同一條檢查 ——
    #   直接呼叫本函式時也不得傳負數／bool／非整數（例：3.5 會讓「≤ 上限」的比較悄悄變寬）。
    if isinstance(max_lag, bool) or not isinstance(max_lag, int) or max_lag < 0:
        raise ValueError(f"max_lag 必須是非負整數：{max_lag!r}")
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
    # 總管裁定（2026-10-14，Z61 疑義 1）：資料月是今天所在月份或更晚 → UNDETERMINED。
    # 一個月的資料不可能在該月結束前發布；出現這種日期代表上游日期有誤。
    # ⛔ 刻意不用「應發布日（due）」來擋：真實發布可能比 lag 估計得早，用 due 擋會誤丟有效的新資料。
    if data_month >= date(today.year, today.month, 1):
        return FreshnessVerdict(
            FreshnessStatus.UNDETERMINED, None, unit, None,
            f"資料月 {month_s} 尚未結束，不可能已發布，日期可疑，無法判定", today)

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
    值不是有限數值（NaN／±inf／非數值；bool 除外）→ MISSING，原因「{series_key}資料異常，無法計算，
    不下結論。」—— 在日期判斷之前（批 Z62）。
    """
    try:
        policy = FRESHNESS_POLICY[dv.series_key]
    except KeyError:
        raise KeyError(f"series_key 未登錄於 FRESHNESS_POLICY：{dv.series_key!r}") from None

    # 批 Z63：「前一資料月」不得獨立套月頻規則（正常情況下也會被判 STALE），⛔ 不默默退回 MonthlyPolicy。
    if isinstance(policy, PreviousMonthOfPolicy):
        raise ValueError(
            f"{dv.series_key} 是「{policy.anchor_key} 的前一資料月」，不得獨立判新鮮度；"
            f"請改用 assess_previous_month(prev_dv, anchor)，anchor 為 {policy.anchor_key} 的評估結果")

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

    # 批 Z62（自檢 A 組）：值不是有限數值（NaN／±inf／非數值；bool 除外）→ 一律 MISSING，
    #   ⛔ 放在日期判斷之前。修前 status 會照日期判成 FRESH、只靠 `scoring_value` 擋成 None ——
    #   接線／UI 層若直接讀 status，會把資料異常的值顯示成「新鮮」。
    #   reason 用核准句格式「{項目}資料異常，無法計算，不下結論。」（項目暫用 series_key，UI 再對應中文）。
    if not _is_scorable(dv.value):
        _check_today(today)
        return AssessedValue(dv, FreshnessVerdict(
            FreshnessStatus.MISSING, None, unit, None,
            NON_FINITE_REASON_FMT.format(item=dv.series_key), today))

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


def assess_previous_month(prev_dv: DatedValue, anchor: AssessedValue) -> AssessedValue:
    """「當期的前一資料月」新鮮度（批 Z63；客戶 2026-10-14 Q-z34 Q1=B）。

    `prev_dv` 的規則必須是 `PreviousMonthOfPolicy`，`anchor` 必須是該規則 `anchor_key` 那一項的
    `assess(...)` 結果；不符 → `ValueError`（設定錯誤，不猜）。`prev_dv` 帶 `as_of` → `ValueError`。

    判定順序（第一個成立者為準）：
    1. 當期不可用（`anchor` 不是 FRESH，或 FRESH 卻沒有可計分值）→ UNDETERMINED；
    2. 前月值為 None → MISSING（原因取 `prev_dv.missing_reason`）；
       前月值不是有限數值 → MISSING（核准句「{項目}資料異常，無法計算，不下結論。」）；
    3. 前月沒有 data_month → MISSING；
    4. 不是當期的恰好前一個資料月（`is_previous_data_month`）→ MISSING「前一資料月不符」；
    5. 其餘 → FRESH。

    ⛔ 不另判前月自己落後幾期：前一資料月本來就比當期落後一期，有效性完全跟著當期走。
    `lag`／`overdue_days` 一律 None（「落後期數」對前月沒有意義，見 reason）；
    `evaluated_on` 沿用 `anchor.verdict.evaluated_on`（同一次評估）。
    """
    if not isinstance(prev_dv, DatedValue):
        raise TypeError(f"prev_dv 必須是 DatedValue：{prev_dv!r}")
    if not isinstance(anchor, AssessedValue):
        raise TypeError(f"anchor 必須是 AssessedValue：{anchor!r}")
    try:
        policy = FRESHNESS_POLICY[prev_dv.series_key]
    except KeyError:
        raise KeyError(f"series_key 未登錄於 FRESHNESS_POLICY：{prev_dv.series_key!r}") from None
    if not isinstance(policy, PreviousMonthOfPolicy):
        raise ValueError(f"{prev_dv.series_key} 的規則不是 PreviousMonthOfPolicy（{policy!r}），"
                         f"請改用 assess()")
    if anchor.dv.series_key != policy.anchor_key:
        raise ValueError(f"{prev_dv.series_key} 的當期應為 {policy.anchor_key}，"
                         f"收到 {anchor.dv.series_key}")
    if prev_dv.as_of is not None:
        raise ValueError(f"{prev_dv.series_key} 為月頻，卻帶了 as_of={prev_dv.as_of}（應給 data_month）")

    today = anchor.verdict.evaluated_on
    _check_today(today)
    unit = LAG_UNIT_PERIOD

    def _v(status: FreshnessStatus, reason: str) -> AssessedValue:
        return AssessedValue(prev_dv, FreshnessVerdict(status, None, unit, None, reason, today))

    # 1. 當期不可用 → 前月無從定位（⛔ 不拿前月自己的日期去判）
    if anchor.verdict.status != FreshnessStatus.FRESH or anchor.scoring_value is None:
        return _v(FreshnessStatus.UNDETERMINED,
                  f"當期 {policy.anchor_key} 不可用（{anchor.verdict.status.value}："
                  f"{anchor.verdict.reason}），無法判定前一資料月")
    cur_month = anchor.dv.data_month
    if cur_month is None:  # FRESH 的月頻值必有 data_month；防手工組裝的 AssessedValue
        return _v(FreshnessStatus.UNDETERMINED,
                  f"當期 {policy.anchor_key} 無資料月份，無法判定前一資料月")

    # 2. 值
    if prev_dv.value is None:
        return _v(FreshnessStatus.MISSING, prev_dv.missing_reason or "無值")
    if not _is_scorable(prev_dv.value):
        return _v(FreshnessStatus.MISSING, NON_FINITE_REASON_FMT.format(item=prev_dv.series_key))

    # 3. 資料月
    if prev_dv.data_month is None:
        return _v(FreshnessStatus.MISSING, "前一資料月無資料月份，不得以無日期的值計分")

    # 4. 必須恰好是當期的前一個資料月
    cur_s = cur_month.strftime("%Y-%m")
    prev_s = prev_dv.data_month.strftime("%Y-%m")
    if not is_previous_data_month(cur_month, prev_dv.data_month):
        return _v(FreshnessStatus.MISSING,
                  f"前一資料月不符：當期 {cur_s}，收到 {prev_s}（應為當期的前一個月）")

    # 5.
    return _v(FreshnessStatus.FRESH,
              f"資料月 {prev_s}，為當期 {cur_s} 的前一資料月（有效性隨當期判定）")
