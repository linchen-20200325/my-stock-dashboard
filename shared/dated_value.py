"""shared/dated_value.py — 帶日期與出處的單一輸入值，以及評估後的「可否計分」包裝（L0）。

批 Z61（freshness SSOT 第一批 F1，2026-10-14）。本批只交付型別與純規則，**尚未接線**。

- `DatedValue`：一個引擎輸入值 ＋ 它屬於哪一天（日頻 `as_of`）或哪一個月（月頻 `data_month`）
  ＋ 來源。⛔ 沒有日期的值不得被當成新鮮（客戶 2026-10-14 Q-z37=A：不得用無日期的值頂替）。
- `AssessedValue`：`DatedValue` ＋ `FreshnessVerdict`。`scoring_value` 是**唯一的計分入口** ——
  只有判定為 FRESH 且值為有限數值（或 bool）時才回值，其餘一律 None（§1：判不出來 ≠ 新鮮）。
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
