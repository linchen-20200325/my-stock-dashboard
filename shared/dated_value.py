"""shared/dated_value.py — 帶日期與出處的單一輸入值，以及評估後的「可否計分」包裝（L0）。

批 Z61（freshness SSOT 第一批 F1，2026-10-14）。本批只交付型別與純規則，**尚未接線**。

- `DatedValue`：一個引擎輸入值 ＋ 它屬於哪一天（日頻 `as_of`）或哪一個月（月頻 `data_month`）
  ＋ 來源。⛔ 沒有日期的值不得被當成新鮮（客戶 2026-10-14 Q-z37=A：不得用無日期的值頂替）。
- `AssessedValue`：`DatedValue` ＋ `FreshnessVerdict`。`scoring_value` 是**唯一的計分入口** ——
  只有判定為 FRESH 且值為有限數值（或 bool）時才回值，其餘一律 None（§1：判不出來 ≠ 新鮮）。
- 批 Z62（F2）新增 L0 helper：`coerce_plain_date`／`coerce_month_start`（資料日期收斂，
  解析不了回 None）、`iso_date_or_none`（同上，回 'YYYY-MM-DD' 字串）、`finite_or_none`
  （與 L5 `_finite_yoy` 逐一等價的有限值判定）。
"""
from __future__ import annotations

import math
import numbers
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 避免與 shared/freshness_policy.py 循環 import（後者 import 本檔）
    from shared.freshness_policy import FreshnessVerdict


def _is_plain_date(v: Any) -> bool:
    return isinstance(v, date) and not isinstance(v, datetime)


@dataclass(frozen=True)
class DatedValue:
    """一個帶日期的輸入值。

    - 日頻資料給 `as_of`（資料歸屬日）；月頻資料給 `data_month`（資料月**月初**）。
      兩者不得同時有值；兩者都沒有 ⇒ 評估時為 MISSING。
    - `value is None` 視為缺值（評估時為 MISSING，原因見 `missing_reason`）。
    """

    value: Any
    series_key: str
    source: str
    as_of: date | None = None
    data_month: date | None = None
    missing_reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.series_key, str) or not self.series_key:
            raise ValueError(f"series_key 必須是非空字串：{self.series_key!r}")
        if self.as_of is not None and self.data_month is not None:
            raise ValueError(
                f"{self.series_key}: as_of 與 data_month 不得同時有值"
                f"（as_of={self.as_of}, data_month={self.data_month}）")
        if self.as_of is not None and not _is_plain_date(self.as_of):
            raise TypeError(f"{self.series_key}: as_of 必須是 datetime.date：{self.as_of!r}")
        if self.data_month is not None:
            if not _is_plain_date(self.data_month):
                raise TypeError(
                    f"{self.series_key}: data_month 必須是 datetime.date：{self.data_month!r}")
            if self.data_month.day != 1:
                raise ValueError(
                    f"{self.series_key}: data_month 必須是月初（收到 {self.data_month}）")

    @property
    def is_missing(self) -> bool:
        return self.value is None


def _is_scorable(v: Any) -> bool:
    """有限數值或 bool 才可計分；NaN / inf / None / 字串一律不可。"""
    if isinstance(v, bool):
        return True
    if isinstance(v, numbers.Real):
        try:
            return math.isfinite(float(v))
        except (TypeError, ValueError, OverflowError):
            return False
    return False


# ── 批 Z62（freshness F2）：L0 共用的日期／數值收斂 helper ─────────────────
# 供 L1（`compute_twii_bias` 的 as_of）、L3（`get_market_assessment` 的 index_as_of）、
# L2（`src/compute/macro/dated_inputs.py` 抽取器）共用同一份判定，避免三層各寫一份。
# ⛔ 一律「解析不了就回 None」—— 不猜格式、不退回今天、不拿抓取時間頂替（§1）。

#: 接受的日期字串格式（逐一嚴格比對，不交給 pandas 寬鬆解析 —— 寬鬆解析會把
#: 整數、「3」這種字串硬解成某個日子）。
_DATE_STR_FORMATS: tuple[str, ...] = ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d")
#: 月份字串格式（`m1b_m2_info['data_month']` 為 'YYYY-MM'）。
_MONTH_STR_FORMATS: tuple[str, ...] = ("%Y-%m",)


def coerce_plain_date(v: Any) -> date | None:
    """把一個「資料日期」收斂成純 `date`；解析不了 → None。

    - `date`（非 datetime）→ 原值。
    - `datetime`／`pandas.Timestamp`（含帶時區）→ `.date()`（取它自己的牆上日期，不換時區）。
      `NaT` → None。
    - `numpy.datetime64` → 經 pandas 轉成 Timestamp 後同上；`NaT` → None。
    - 字串 → 只接受 'YYYY-MM-DD'、'YYYYMMDD'、'YYYY/MM/DD'（前後空白容許）。
    - 其餘（None、bool、整數、浮點、其他型別、格式不符的字串）→ None。
    """
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, datetime):
        try:
            if v != v:  # pandas.NaT 自比為 False
                return None
            return v.date()
        except (TypeError, ValueError):
            return None
    if isinstance(v, date):
        return v
    if type(v).__name__ == "datetime64":
        import pandas as _pd  # 延遲 import：只有 numpy datetime64 才需要
        _ts = _pd.Timestamp(v)
        if _ts is _pd.NaT or _ts != _ts:
            return None
        return _ts.date()
    if type(v).__name__ == "NaTType":
        return None
    if isinstance(v, str):
        s = v.strip()
        for fmt in _DATE_STR_FORMATS:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    return None


def coerce_month_start(v: Any) -> date | None:
    """把一個「資料月份」收斂成該月**月初**的純 `date`；解析不了 → None。

    字串先試 'YYYY-MM'，再試 `coerce_plain_date` 接受的日期格式；日期一律取月初。
    """
    if isinstance(v, str):
        s = v.strip()
        for fmt in _MONTH_STR_FORMATS:
            try:
                return datetime.strptime(s, fmt).date().replace(day=1)
            except ValueError:
                continue
    d = coerce_plain_date(v)
    return d.replace(day=1) if d is not None else None


def iso_date_or_none(v: Any) -> str | None:
    """`coerce_plain_date(v)` 的 ISO 字串版（'YYYY-MM-DD'）；解析不了 → None。

    批 Z62 補件（總管裁定）：寫進共用 session dict（`mkt_info['index_as_of']`、
    `bias_info['as_of']`）的新增日期一律用 ISO 字串，不放 date 物件 —— 字串可直接序列化，
    也不會被舊 UI「把 int／float 值逐一列進 prompt」的掃描撿到。
    """
    d = coerce_plain_date(v)
    return d.isoformat() if d is not None else None


def finite_or_none(v: Any) -> Any:
    """有限實數 → **回原值、不轉型**；None／bool／NaN／±inf／非數值 → None。

    與 L5 `src/ui/tabs/macro/section_long._finite_yoy`（以及以它為本的
    `section_news_ai._finite_or_none`）逐一等價的 L0 版本（批 Z62；L2 不得 import L5）。
    等價性由 tests/test_batch_z62.py 以同一組輸入逐一比對守住。
    """
    if v is None or isinstance(v, bool):
        return None
    try:
        return v if math.isfinite(v) else None
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class AssessedValue:
    """`DatedValue` ＋ 新鮮度判定。"""

    dv: DatedValue
    verdict: "FreshnessVerdict"

    @property
    def scoring_value(self) -> Any:
        """唯一的計分入口：FRESH 且值為有限數值或 bool → 回值；否則 None。

        ⚠️ 只接受 Python `bool` 與 `numbers.Real`（含 numpy 浮點數）。numpy 的 `bool_`
        不是 `numbers.Real`，會回 None —— 接線批由 L3 先轉成 Python `bool` 再包進 `DatedValue`
        （總管 2026-10-14 裁定維持現狀）。
        """
        from shared.freshness_policy import FreshnessStatus

        if self.verdict.status != FreshnessStatus.FRESH:
            return None
        if not _is_scorable(self.dv.value):
            return None
        return self.dv.value

    @property
    def display_date(self) -> str | None:
        """日頻 'MM/DD'，月頻 'YYYY-MM'，沒有日期回 None。"""
        if self.dv.as_of is not None:
            return self.dv.as_of.strftime("%m/%d")
        if self.dv.data_month is not None:
            return self.dv.data_month.strftime("%Y-%m")
        return None
