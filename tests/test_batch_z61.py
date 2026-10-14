"""批 Z61 — freshness SSOT 第一批 F1：L0 純規則（不接線）。

客戶 2026-10-14 Q-z37=A（日頻：落後超過 3 個交易日 → 已過期、不計分）、
Q-z38=A（月頻：依資料月份＋正常發布週期判斷，不得一律 30 天）。

全部用合成的 `CalendarSets`，⛔ 不連網。
"""
from __future__ import annotations

import ast
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

from shared import freshness_policy as FP
from shared import trading_days as TD
from shared.dated_value import AssessedValue, DatedValue
from shared.freshness_policy import (
    DAILY_MAX_LAG_TRADING_DAYS,
    FRESHNESS_POLICY,
    DailyPolicy,
    FreshnessStatus,
    FreshnessVerdict,
    MonthlyPolicy,
    assess,
    assess_daily,
    assess_monthly,
    is_previous_data_month,
)
from shared.trading_days import CalendarSets, count_trading_days_after, count_weekdays_after

REPO = Path(__file__).resolve().parents[1]

FRESH = FreshnessStatus.FRESH
STALE = FreshnessStatus.STALE
MISSING = FreshnessStatus.MISSING
UND = FreshnessStatus.UNDETERMINED

# ── 合成休市表（只涵蓋 2026 年）─────────────────────────────────────────
#   連假：2026-09-24（四）、09-25（五）平日休市
#   補班：2026-09-19（六）交易
#   元旦：2026-01-01（四）休市
#   無法分類：2026-11-20（五）
CAL = CalendarSets(
    closed=frozenset({date(2026, 9, 24), date(2026, 9, 25), date(2026, 1, 1)}),
    trading=frozenset({date(2026, 9, 19)}),
    unclassified=frozenset({date(2026, 11, 20)}),
    covered_years=frozenset({2026}),
)


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _daily(a, t, cal=CAL, kind="twse"):
    return assess_daily(_d(a) if isinstance(a, str) else a, today=_d(t), calendar=cal,
                        calendar_kind=kind)


# ═════════════════════════════════════════════════════════════════════
# 日頻 — 台股交易日
# ═════════════════════════════════════════════════════════════════════
class TestDailyTwse:
    def test_third_trading_day_fresh_fourth_stale_today_counted(self):
        # a＝週一 10/05 → 週二、三、四 N=1,2,3（今天計入）FRESH；週五 N=4 STALE
        for t, n, st in [("2026-10-06", 1, FRESH), ("2026-10-07", 2, FRESH),
                         ("2026-10-08", 3, FRESH), ("2026-10-09", 4, STALE)]:
            v = _daily("2026-10-05", t)
            assert (v.status, v.lag) == (st, n), t
            assert v.lag_unit == "trading_day"
            assert v.evaluated_on == _d(t)

    def test_same_day_is_zero(self):
        v = _daily("2026-10-05", "2026-10-05")
        assert (v.status, v.lag) == (FRESH, 0)

    def test_reason_text(self):
        v = _daily("2026-10-05", "2026-10-09")
        assert v.reason == "資料日 10/05，落後 4 個交易日（上限 3）"

    def test_weekend_crossing(self):
        # 週四 → 下週一：週五、週一 → N=2
        v = _daily("2026-10-08", "2026-10-12")
        assert (v.status, v.lag) == (FRESH, 2)
        # 週五 → 下週三：N=3 仍 FRESH；下週四 N=4 STALE
        v = _daily("2026-10-09", "2026-10-14")
        assert (v.status, v.lag) == (FRESH, 3)
        v = _daily("2026-10-09", "2026-10-15")
        assert (v.status, v.lag) == (STALE, 4)

    def test_weekend_today_not_counted(self):
        # 週五 → 週日：週六、週日都不計
        v = _daily("2026-10-09", "2026-10-11")
        assert (v.status, v.lag) == (FRESH, 0)

    def test_holiday_block_not_counted(self):
        # 週三 9/23 → 週二 9/29：9/24、9/25 休市，9/26、27 週末 → 只有 28、29
        v = _daily("2026-09-23", "2026-09-29")
        assert (v.status, v.lag) == (FRESH, 2)
        # 若連假被當交易日，會是 4 → STALE；這裡必須 FRESH
        v = _daily("2026-09-23", "2026-09-30")
        assert (v.status, v.lag) == (FRESH, 3)
        v = _daily("2026-09-23", "2026-10-01")
        assert (v.status, v.lag) == (STALE, 4)

    def test_makeup_saturday_counted(self):
        # 週五 9/18 → 週一 9/21：補班週六 9/19 計入 → N=2
        v = _daily("2026-09-18", "2026-09-21")
        assert (v.status, v.lag) == (FRESH, 2)
        # 週三 9/16 → 週一 9/21：17、18、19(補班)、21 → N=4 STALE（不計補班會是 3 FRESH）
        v = _daily("2026-09-16", "2026-09-21")
        assert (v.status, v.lag) == (STALE, 4)

    def test_cal_none_small_gap_fresh(self):
        # 曆日差 3（週一 → 週四）：upper=3 ≤ 3 → FRESH（以上界判定）
        v = _daily("2026-10-12", "2026-10-15", cal=None)
        assert v.status == FRESH
        assert v.lag == 3
        assert "休市表取不到" in v.reason

    def test_cal_none_gap_five_is_undetermined(self):
        # 曆日差 5：lower=0、upper=5 → 不得 FRESH、也不得 STALE
        v = _daily("2026-10-09", "2026-10-14", cal=None)
        assert v.status == UND
        assert v.status not in (FRESH, STALE)
        assert v.lag is None
        assert "休市表取不到" in v.reason

    def test_cal_none_is_not_weekend_only(self):
        # ⛔ 不得退回「只扣週末」：週五 → 下週一（只扣週末會是 N=1）仍是全部未知
        c = count_trading_days_after(_d("2026-10-09"), _d("2026-10-12"), None)
        assert (c.lower, c.upper) == (0, 3)
        assert len(c.unknown_days) == 3

    def test_cross_year_interval_fresh(self):
        # 12/30 → 01/05：12/31 未涵蓋(upper+1)；01/01 休市；01/02、01/05 交易 → [2,3] FRESH
        c = count_trading_days_after(_d("2025-12-30"), _d("2026-01-05"), CAL)
        assert (c.lower, c.upper) == (2, 3)
        assert c.unknown_days == (_d("2025-12-31"),)
        v = _daily("2025-12-30", "2026-01-05")
        assert v.status == FRESH and v.lag == 3
        assert "休市表未涵蓋 2025 年" in v.reason

    def test_cross_year_interval_undetermined(self):
        # 12/29 → 01/06：未知 12/30、12/31；交易 01/02、05、06 → [3,5] → UNDETERMINED
        c = count_trading_days_after(_d("2025-12-29"), _d("2026-01-06"), CAL)
        assert (c.lower, c.upper) == (3, 5)
        v = _daily("2025-12-29", "2026-01-06")
        assert v.status == UND
        assert "休市表未涵蓋 2025 年，無法判定新鮮度" in v.reason

    def test_cross_year_interval_stale(self):
        # 12/26 → 01/08：未知 12/27~31；交易 01/02、05、06、07、08 → lower 5 ≥ 4 → STALE
        c = count_trading_days_after(_d("2025-12-26"), _d("2026-01-08"), CAL)
        assert (c.lower, c.upper) == (5, 10)
        v = _daily("2025-12-26", "2026-01-08")
        assert (v.status, v.lag) == (STALE, 5)

    def test_unclassified_day_is_unknown(self):
        # 11/19（四）→ 11/25（三）：11/20 無法分類；交易 23、24、25 → [3,4] → UNDETERMINED
        c = count_trading_days_after(_d("2026-11-19"), _d("2026-11-25"), CAL)
        assert (c.lower, c.upper) == (3, 4)
        assert c.unknown_days == (_d("2026-11-20"),)
        v = _daily("2026-11-19", "2026-11-25")
        assert v.status == UND
        assert "2026-11-20 無法分類" in v.reason

    def test_future_is_undetermined(self):
        v = _daily("2026-10-15", "2026-10-14")
        assert v.status == UND and v.lag is None

    def test_none_is_missing(self):
        v = assess_daily(None, today=_d("2026-10-14"), calendar=CAL)
        assert v.status == MISSING and v.lag is None

    def test_count_raises_on_future(self):
        with pytest.raises(ValueError):
            count_trading_days_after(_d("2026-10-15"), _d("2026-10-14"), CAL)
        with pytest.raises(ValueError):
            count_weekdays_after(_d("2026-10-15"), _d("2026-10-14"))

    def test_datetime_rejected(self):
        from datetime import datetime
        with pytest.raises(TypeError):
            count_trading_days_after(datetime(2026, 10, 1), _d("2026-10-14"), CAL)


# ═════════════════════════════════════════════════════════════════════
# 日頻 — VIX 平日上界
# ═════════════════════════════════════════════════════════════════════
class TestDailyWeekday:
    def test_friday_to_thursday_is_stale(self):
        v = _daily("2026-10-09", "2026-10-15", cal=None, kind="weekday")
        assert (v.status, v.lag, v.lag_unit) == (STALE, 4, "weekday")
        v = _daily("2026-10-09", "2026-10-14", cal=None, kind="weekday")
        assert (v.status, v.lag) == (FRESH, 3)

    def test_monday_to_friday(self):
        for t, n, st in [("2026-10-06", 1, FRESH), ("2026-10-07", 2, FRESH),
                         ("2026-10-08", 3, FRESH), ("2026-10-09", 4, STALE)]:
            v = _daily("2026-10-05", t, cal=None, kind="weekday")
            assert (v.status, v.lag) == (st, n), t

    def test_weekend_not_counted(self):
        assert count_weekdays_after(_d("2026-10-09"), _d("2026-10-11")) == 0
        assert count_weekdays_after(_d("2026-10-09"), _d("2026-10-12")) == 1

    def test_ignores_twse_holidays(self):
        # 台股連假對 VIX 無效：9/23 → 9/29 平日 24、25、28、29 = 4 → STALE（台股日曆會是 2 FRESH）
        v = _daily("2026-09-23", "2026-09-29", cal=CAL, kind="weekday")
        assert (v.status, v.lag) == (STALE, 4)

    def test_vix_policy_uses_weekday_via_assess(self):
        dv = DatedValue(18.2, "VIX_Index", "yahoo:^VIX", as_of=_d("2026-09-23"))
        av = assess(dv, today=_d("2026-09-29"), calendar=CAL)
        assert av.verdict.status == STALE
        assert av.verdict.lag_unit == "weekday"
        # cal 為 None 也照樣判得出（平日日曆不需休市表）
        dv = DatedValue(18.2, "VIX_Index", "yahoo:^VIX", as_of=_d("2026-10-09"))
        av = assess(dv, today=_d("2026-10-15"), calendar=None)
        assert av.verdict.status == STALE
        assert av.scoring_value is None

    def test_policy_table_marks_vix_weekday(self):
        assert FRESHNESS_POLICY["VIX_Index"] == DailyPolicy(calendar="weekday")
        for k in ("BIAS240_pct", "PCR", "Futures_Net_Short", "Index_Below_MA5"):
            assert FRESHNESS_POLICY[k] == DailyPolicy(calendar="twse"), k


# ═════════════════════════════════════════════════════════════════════
# 月頻
# ═════════════════════════════════════════════════════════════════════
# 判準：資料月 M 在 (M+2)/01 + lag + 7 當天起 STALE（下一期 M+1 已過發布日＋緩衝）。
_MONTHLY_CASES = [
    # (lag_key, data_month, 前一天 FRESH, 當天 STALE)
    # 台灣 PMI（lag 1）
    ("ism_pmi", "2026-08-01", "2026-10-08", "2026-10-09"),
    ("ism_pmi", "2026-01-01", "2026-03-08", "2026-03-09"),  # 下一期跨 2 月
    ("ism_pmi", "2026-07-01", "2026-09-08", "2026-09-09"),  # 下一期 8 月（31 日大月）
    ("ism_pmi", "2025-12-01", "2026-02-08", "2026-02-09"),  # 跨年
    # M1B／M2（lag 27）
    ("m1b_m2", "2026-07-01", "2026-10-04", "2026-10-05"),
    ("m1b_m2", "2025-12-01", "2026-03-06", "2026-03-07"),   # 下一期 1 月，due 落在 2 月後
    ("m1b_m2", "2026-06-01", "2026-09-03", "2026-09-04"),   # 下一期 7 月（31 日大月）
    ("m1b_m2", "2026-01-01", "2026-04-03", "2026-04-04"),   # 下一期 2 月（28 天）
]


class TestMonthly:
    @pytest.mark.parametrize("key,dm,fresh_day,stale_day", _MONTHLY_CASES)
    def test_boundary(self, key, dm, fresh_day, stale_day):
        v0 = assess_monthly(_d(dm), today=_d(fresh_day), lag_key=key)
        v1 = assess_monthly(_d(dm), today=_d(stale_day), lag_key=key)
        assert v0.status == FRESH, (key, dm, fresh_day, v0)
        assert v1.status == STALE, (key, dm, stale_day, v1)
        assert v1.lag == 1 and v1.lag_unit == "period"

    def test_overdue_days_carried(self):
        # PMI 8 月資料，10/08：9 月資料原定 10/02 發布，逾期 6 天仍在緩衝內
        v = assess_monthly(_d("2026-08-01"), today=_d("2026-10-08"), lag_key="ism_pmi")
        assert v.status == FRESH and v.overdue_days == 6
        assert "逾原定發布日 6 天" in v.reason

    def test_two_periods_behind(self):
        v = assess_monthly(_d("2026-07-01"), today=_d("2026-10-14"), lag_key="ism_pmi")
        assert (v.status, v.lag) == (STALE, 2)

    def test_not_fixed_30_days(self):
        # 突變守衛：「固定 30 天」規則下以下兩例都會判過期；發布期規則下是當期
        v = assess_monthly(_d("2026-09-01"), today=_d("2026-10-14"), lag_key="ism_pmi")
        assert (_d("2026-10-14") - _d("2026-09-01")).days > 30
        assert v.status == FRESH
        v = assess_monthly(_d("2026-08-01"), today=_d("2026-10-14"), lag_key="m1b_m2")
        assert (_d("2026-10-14") - _d("2026-08-01")).days > 30
        assert v.status == FRESH

    def test_none_is_missing(self):
        v = assess_monthly(None, today=_d("2026-10-14"), lag_key="m1b_m2")
        assert v.status == MISSING

    def test_future_month_undetermined(self):
        v = assess_monthly(_d("2026-11-01"), today=_d("2026-10-14"), lag_key="m1b_m2")
        assert v.status == UND

    @pytest.mark.parametrize("key", ["ism_pmi", "m1b_m2"])
    def test_current_month_undetermined(self, key):
        # 當月資料不可能在該月結束前發布 → 日期可疑，UNDETERMINED（不得 FRESH）
        v = assess_monthly(_d("2026-10-01"), today=_d("2026-10-14"), lag_key=key)
        assert v.status == UND and v.lag is None
        assert "尚未結束" in v.reason
        # 月初當天也一樣
        v = assess_monthly(_d("2026-10-01"), today=_d("2026-10-01"), lag_key=key)
        assert v.status == UND

    def test_previous_month_still_fresh(self):
        # 上個月資料：不得被「當月」守衛誤擋（不以 due 日擋，提早發布仍有效）
        v = assess_monthly(_d("2026-09-01"), today=_d("2026-10-14"), lag_key="ism_pmi")
        assert v.status == FRESH
        # M1B lag 27：9 月資料 10/14 尚未到估計 due，但若上游提早給了，仍視為有效當期
        v = assess_monthly(_d("2026-09-01"), today=_d("2026-10-14"), lag_key="m1b_m2")
        assert v.status == FRESH

    def test_unregistered_lag_key_raises(self):
        with pytest.raises(KeyError):
            assess_monthly(_d("2026-09-01"), today=_d("2026-10-14"), lag_key="nope")
        with pytest.raises(KeyError):
            MonthlyPolicy("nope")

    def test_non_month_start_raises(self):
        with pytest.raises(ValueError):
            assess_monthly(_d("2026-09-15"), today=_d("2026-10-14"), lag_key="m1b_m2")

    def test_policy_lag_keys(self):
        assert FRESHNESS_POLICY["ISM_PMI_or_OECD_CLI"] == MonthlyPolicy("ism_pmi")
        assert FRESHNESS_POLICY["PMI_Prev_Month"] == MonthlyPolicy("ism_pmi")
        assert FRESHNESS_POLICY["M1B_YoY_pct"] == MonthlyPolicy("m1b_m2")
        assert FRESHNESS_POLICY["M2_YoY_pct"] == MonthlyPolicy("m1b_m2")


# ═════════════════════════════════════════════════════════════════════
# PMI 上月
# ═════════════════════════════════════════════════════════════════════
class TestPreviousMonth:
    def test_cases(self):
        assert is_previous_data_month(_d("2026-10-01"), _d("2026-09-01"))
        assert is_previous_data_month(_d("2026-01-01"), _d("2025-12-01"))   # 跨年
        assert not is_previous_data_month(_d("2026-10-01"), _d("2026-10-01"))  # 同月
        assert not is_previous_data_month(_d("2026-10-01"), _d("2026-08-01"))  # 差 2 月
        assert not is_previous_data_month(_d("2026-01-01"), _d("2025-11-01"))  # 跨年差 2 月
        assert not is_previous_data_month(_d("2026-09-01"), _d("2026-10-01"))  # 反向
        assert not is_previous_data_month(_d("2026-10-01"), _d("2025-09-01"))  # 差 13 月


# ═════════════════════════════════════════════════════════════════════
# DatedValue / AssessedValue / assess 分派
# ═════════════════════════════════════════════════════════════════════
def _verdict(status):
    return FreshnessVerdict(status, 0, "trading_day", None, "", _d("2026-10-14"))


class TestDatedValue:
    def test_both_dates_rejected(self):
        with pytest.raises(ValueError):
            DatedValue(1.0, "PCR", "x", as_of=_d("2026-10-01"), data_month=_d("2026-10-01"))

    def test_data_month_must_be_month_start(self):
        with pytest.raises(ValueError):
            DatedValue(1.0, "M2_YoY_pct", "x", data_month=_d("2026-09-02"))

    def test_scoring_value_only_fresh(self):
        dv = DatedValue(1.2, "PCR", "taifex", as_of=_d("2026-10-13"))
        assert AssessedValue(dv, _verdict(FRESH)).scoring_value == 1.2
        for st in (STALE, MISSING, UND):
            assert AssessedValue(dv, _verdict(st)).scoring_value is None

    @pytest.mark.parametrize("val", [math.nan, math.inf, -math.inf, None, "1.2"])
    def test_scoring_value_rejects_non_finite(self, val):
        dv = DatedValue(val, "PCR", "taifex", as_of=_d("2026-10-13"))
        assert AssessedValue(dv, _verdict(FRESH)).scoring_value is None

    def test_scoring_value_bool_and_zero(self):
        dv = DatedValue(False, "Index_Below_MA5", "twse", as_of=_d("2026-10-13"))
        assert AssessedValue(dv, _verdict(FRESH)).scoring_value is False
        dv = DatedValue(0.0, "Futures_Net_Short", "taifex", as_of=_d("2026-10-13"))
        assert AssessedValue(dv, _verdict(FRESH)).scoring_value == 0.0

    def test_display_date(self):
        dv = DatedValue(1.0, "PCR", "x", as_of=_d("2026-10-07"))
        assert AssessedValue(dv, _verdict(FRESH)).display_date == "10/07"
        dv = DatedValue(1.0, "M2_YoY_pct", "x", data_month=_d("2026-08-01"))
        assert AssessedValue(dv, _verdict(FRESH)).display_date == "2026-08"
        dv = DatedValue(1.0, "PCR", "x")
        assert AssessedValue(dv, _verdict(FRESH)).display_date is None


class TestAssessDispatch:
    T = _d("2026-10-14")

    def test_daily_fresh_and_scored(self):
        av = assess(DatedValue(5.1, "BIAS240_pct", "twse", as_of=_d("2026-10-12")),
                    today=self.T, calendar=CAL)
        assert av.verdict.status == FRESH and av.scoring_value == 5.1

    def test_daily_without_date_is_missing(self):
        # ⛔ 不得用無日期的值頂替
        av = assess(DatedValue(5.1, "BIAS240_pct", "twse"), today=self.T, calendar=CAL)
        assert av.verdict.status == MISSING and av.scoring_value is None

    def test_value_none_is_missing_with_reason(self):
        av = assess(DatedValue(None, "PCR", "taifex", as_of=_d("2026-10-13"),
                               missing_reason="TAIFEX 抓取失敗"),
                    today=self.T, calendar=CAL)
        assert av.verdict.status == MISSING
        assert av.verdict.reason == "TAIFEX 抓取失敗"

    def test_monthly_via_assess(self):
        av = assess(DatedValue(3.2, "M1B_YoY_pct", "cbc", data_month=_d("2026-07-01")),
                    today=_d("2026-10-05"), calendar=None)
        assert av.verdict.status == STALE and av.scoring_value is None

    def test_misconfigured_dates_raise(self):
        with pytest.raises(ValueError):
            assess(DatedValue(1.0, "PCR", "x", data_month=_d("2026-10-01")),
                   today=self.T, calendar=CAL)
        with pytest.raises(ValueError):
            assess(DatedValue(1.0, "M2_YoY_pct", "x", as_of=_d("2026-10-01")),
                   today=self.T, calendar=CAL)

    def test_unregistered_key_raises(self):
        with pytest.raises(KeyError):
            assess(DatedValue(1.0, "Sahm_Rule_Triggered", "x", as_of=_d("2026-10-01")),
                   today=self.T, calendar=CAL)

    def test_policy_is_read_only(self):
        with pytest.raises(TypeError):
            FRESHNESS_POLICY["PCR"] = DailyPolicy()  # type: ignore[index]


# ═════════════════════════════════════════════════════════════════════
# SSOT 守衛
# ═════════════════════════════════════════════════════════════════════
class TestSsotGuards:
    def test_policy_keys_match_engine_inputs(self):
        from src.services.macro_state_locker import _ENGINE_NUMERIC_INPUTS
        assert set(FRESHNESS_POLICY) == set(_ENGINE_NUMERIC_INPUTS) | {"Index_Below_MA5"}

    def test_max_lag_defined_once(self):
        assert DAILY_MAX_LAG_TRADING_DAYS == 3
        hits = []
        for root in ("shared", "src"):
            for p in (REPO / root).rglob("*.py"):
                tree = ast.parse(p.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    targets = []
                    if isinstance(node, ast.Assign):
                        targets = node.targets
                    elif isinstance(node, ast.AnnAssign):
                        targets = [node.target]
                    for tg in targets:
                        if isinstance(tg, ast.Name) and tg.id == "DAILY_MAX_LAG_TRADING_DAYS":
                            hits.append(p.relative_to(REPO).as_posix())
        assert hits == ["shared/freshness_policy.py"]

    def test_defaults_reference_constant(self):
        import inspect
        assert DailyPolicy().max_lag_trading_days == DAILY_MAX_LAG_TRADING_DAYS
        sig = inspect.signature(assess_daily)
        assert sig.parameters["max_lag"].default == DAILY_MAX_LAG_TRADING_DAYS
        # freshness_policy.py 內 max_lag 的預設值必須是常數名，不是字面數字
        src = (REPO / "shared/freshness_policy.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "assess_daily":
                kw = dict(zip([a.arg for a in node.args.kwonlyargs], node.args.kw_defaults))
                assert isinstance(kw["max_lag"], ast.Name)
                assert kw["max_lag"].id == "DAILY_MAX_LAG_TRADING_DAYS"

    def test_reexport_identity(self):
        from src.compute import trading_calendar as tc
        assert tc.classify_day is TD.classify_day
        assert tc.next_trading_day is TD.next_trading_day
        assert tc.DayVerdict is TD.DayVerdict
        assert (tc.TRADING, tc.CLOSED, tc.UNDETERMINED) == (TD.TRADING, TD.CLOSED,
                                                             TD.UNDETERMINED)
        assert tc.NEXT_TRADING_DAY_SEARCH_DAYS == TD.NEXT_TRADING_DAY_SEARCH_DAYS

    @pytest.mark.parametrize("mod", ["shared/trading_days.py", "shared/dated_value.py",
                                     "shared/freshness_policy.py"])
    def test_l0_does_not_import_src(self, mod):
        tree = ast.parse((REPO / mod).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(("src", "app")), (mod, node.module)
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert not a.name.startswith(("src", "app")), (mod, a.name)
                    assert a.name.split(".")[0] not in ("streamlit", "requests"), (mod, a.name)


def test_module_exposes_status_values():
    assert {s.value for s in FP.FreshnessStatus} == {"fresh", "stale", "missing", "undetermined"}


def test_count_sanity_long_span():
    # 長區間仍逐日計數正確：2026-10-01（四）→ 2026-10-31（六）
    c = count_trading_days_after(_d("2026-10-01"), _d("2026-10-31"), CAL)
    expect = sum(1 for i in range(1, 31)
                 if (_d("2026-10-01") + timedelta(days=i)).weekday() < 5)
    assert c.lower == c.upper == expect
