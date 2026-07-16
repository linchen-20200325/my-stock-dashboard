# -*- coding: utf-8 -*-
"""shared/staleness.py — 資料時效 SSOT 測試（A~E backlog 批次2）。"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from shared.staleness import (
    STALE_DAYS_DAILY,
    STALE_DAYS_MONTHLY,
    STALE_DAYS_QUARTERLY,
    expected_latest_trading_day,
    gate_for_realtime,
    stale_days_threshold,
    stale_tag,
    staleness_days,
)


class TestExpectedLatestTradingDay:
    def test_weekday_returns_self(self):
        # 2026-07-08 是週三
        assert expected_latest_trading_day(dt.date(2026, 7, 8)) == dt.date(2026, 7, 8)

    def test_saturday_retreats_to_friday(self):
        # 2026-07-11 週六 → 週五 07-10
        assert expected_latest_trading_day(dt.date(2026, 7, 11)) == dt.date(2026, 7, 10)

    def test_sunday_retreats_to_friday(self):
        assert expected_latest_trading_day(dt.date(2026, 7, 12)) == dt.date(2026, 7, 10)

    def test_holiday_skipped(self):
        # 週五休市 → 退到週四
        hol = {dt.date(2026, 7, 10)}
        assert expected_latest_trading_day(dt.date(2026, 7, 10), hol) == dt.date(2026, 7, 9)

    def test_holiday_plus_weekend_chain(self):
        # 週一(07-13)休市 + 前面週末 → 退到週五 07-10
        hol = {dt.date(2026, 7, 13)}
        assert expected_latest_trading_day(dt.date(2026, 7, 13), hol) == dt.date(2026, 7, 10)


class TestStalenessDays:
    def test_dataframe_current(self):
        df = pd.DataFrame({"date": pd.to_datetime(["2026-07-08", "2026-07-10"])})
        assert staleness_days(df, today=dt.date(2026, 7, 10)) == 0

    def test_dataframe_stale(self):
        df = pd.DataFrame({"date": pd.to_datetime(["2026-07-01", "2026-07-06"])})
        # 預期最新 07-10（週五）− 資料最新 07-06 = 4 天
        assert staleness_days(df, today=dt.date(2026, 7, 11)) == 4

    def test_bare_date(self):
        assert staleness_days(dt.date(2026, 7, 6), today=dt.date(2026, 7, 10)) == 4

    def test_string_date(self):
        assert staleness_days("2026-07-06", today=dt.date(2026, 7, 10)) == 4

    def test_empty_df_returns_none(self):
        assert staleness_days(pd.DataFrame({"date": []})) is None

    def test_missing_col_returns_none(self):
        assert staleness_days(pd.DataFrame({"x": [1]})) is None

    def test_none_returns_none(self):
        assert staleness_days(None) is None

    def test_unparseable_returns_none(self):
        assert staleness_days("not-a-date") is None


class TestGateForRealtime:
    def test_fresh_passes(self):
        ok, msg = gate_for_realtime(0)
        assert ok is True and msg == ""

    def test_within_tolerance_passes(self):
        ok, msg = gate_for_realtime(1, max_days=1)
        assert ok is True

    def test_stale_blocked(self):
        ok, msg = gate_for_realtime(5, max_days=1)
        assert ok is False and "5 天前" in msg

    def test_none_blocked_failsafe(self):
        ok, msg = gate_for_realtime(None)
        assert ok is False and "無法確認" in msg


class TestStaleTag:
    def test_over_threshold_tagged(self):
        assert stale_tag(45) == "[STALE:45d] "

    def test_under_threshold_empty(self):
        assert stale_tag(10) == ""

    def test_none_empty(self):
        assert stale_tag(None) == ""


class TestStaleDaysThreshold:
    """v19.127 頻率感知過期門檻:不同發布頻率取不同「合理最舊」天數。"""

    def test_daily_default(self):
        assert stale_days_threshold("daily") == STALE_DAYS_DAILY == 7

    def test_quarterly(self):
        # 台股季報 as_of=季末,季後~45d 公告 + 下一季~91d → ~136d,+鏡像寬限 = 150d
        assert stale_days_threshold("quarterly") == STALE_DAYS_QUARTERLY == 150

    def test_monthly(self):
        assert stale_days_threshold("monthly") == STALE_DAYS_MONTHLY == 45

    def test_unknown_falls_back_to_daily(self):
        # 未知頻率 → 退最嚴日頻(§1 Fail-Loud,不放水)
        assert stale_days_threshold("weekly") == STALE_DAYS_DAILY
        assert stale_days_threshold() == STALE_DAYS_DAILY

    def test_quarterly_gt_daily_invariant(self):
        assert STALE_DAYS_QUARTERLY > STALE_DAYS_MONTHLY > STALE_DAYS_DAILY


class TestShimDelegation:
    def test_app_stock_fetchers_shim_delegates(self, monkeypatch):
        """既有 _expected_latest_trading_date 委派至 SSOT(向後相容,介面 0 改)。"""
        from src.data.stock import app_stock_fetchers as A
        out = A._expected_latest_trading_date()
        assert out == expected_latest_trading_day()
        # 且與 SSOT 同型別(date)
        assert isinstance(out, dt.date)


class TestLlmContextStaleWiring:
    """app.py `_build_llm_context` 接 stale_tag(app.py 難以單元 import,故 source-scan;
    邏輯由上方 stale_tag/staleness_days 單元測試覆蓋)。"""

    def test_build_llm_context_imports_staleness(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
        assert "from shared.staleness import stale_tag, staleness_days" in src
        assert "_tag(_exp)" in src and "_tag(_pmi)" in src, "月度指標應套 stale 標籤"
        # v19.85 正名一併帶入 AI prompt
        assert "台灣出口 YoY" in src and "台灣外銷訂單 YoY" not in src

    def test_global_redlight_gated_by_staleness(self):
        """v19.88 批次2 收尾:全域紅綠燈過期時撤 actionable 建議、標記過期。"""
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
        assert "from shared.staleness import gate_for_realtime, staleness_days" in src
        assert "_rt_ok, _rt_msg = gate_for_realtime(" in src
        assert "資料已過期，燈號僅供參考" in src, "過期須明確標記"
        # 過期分支不得再顯示 actionable「建議持股」
        assert "if _rt_ok:" in src
