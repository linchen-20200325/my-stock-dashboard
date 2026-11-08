# -*- coding: utf-8 -*-
"""tests/test_macro_cache_reader_future_asof.py — 資料觀測日 as_of 晚於 today 的守衛(D2)。

缺陷(已確認):`compute_cache_staleness` 對 as_of > today(未來日期)回
`is_stale=False`、`age_days` 為負、`reason=None` —— 未來日期的資料被當成「很新鮮」。
未來日期代表系統時鐘錯 / 上游日期壞 / 資料被污染,**無法判定新鮮度**。
§1「判不出來 → 視為過期(不假設新鮮)」:應 `is_stale=True`,reason 講明「無法判定」,
`as_of` / `age_days` 照實保留(負值,不截成 0)供診斷。

不改任何門檻 / 公式 / CADENCE。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from src.data.macro.macro_cache_reader import compute_cache_staleness

_TODAY = dt.date(2026, 9, 10)


def _write_daily(tmp_path, last_day: dt.date, n: int = 10):
    idx = pd.date_range(end=pd.Timestamp(last_day), periods=n, freq="D")  # 末日必為 last_day
    pd.DataFrame({"date": idx, "close": range(n)}).to_parquet(
        tmp_path / "twii_ohlcv.parquet")


def _write_monthly(tmp_path, last_month: dt.date, n: int = 6):
    months = pd.date_range(end=pd.Timestamp(last_month), periods=n, freq="MS")
    pd.DataFrame({"date": months, "m1b_m2_gap": range(n)}).to_parquet(
        tmp_path / "finmind_m1m2.parquet")


class TestFutureAsOf:
    def test_daily_future_asof_is_stale_undeterminable(self, tmp_path):
        """(1) 非月頻 as_of = today+3 → is_stale True、reason 含「無法判定」,age_days 為負。"""
        future = _TODAY + dt.timedelta(days=3)
        _write_daily(tmp_path, future)
        r = compute_cache_staleness("twii_ohlcv", cache_dir=tmp_path, today=_TODAY)
        assert r["is_stale"] is True
        assert "無法判定" in (r["reason"] or "")
        assert r["as_of"] == future
        assert r["age_days"] == -3          # 照實保留負值,不截成 0

    def test_monthly_future_asof_is_stale_undeterminable(self, tmp_path):
        """(2) 月頻同上:as_of(月初)晚於 today。"""
        future = dt.date(2026, 10, 1)       # today=2026-09-10 → 未來
        _write_monthly(tmp_path, future)
        r = compute_cache_staleness("finmind_m1m2", cache_dir=tmp_path, today=_TODAY)
        assert r["is_stale"] is True
        assert "無法判定" in (r["reason"] or "")
        assert r["as_of"] == future
        assert r["age_days"] == (_TODAY - future).days and r["age_days"] < 0

    def test_asof_equals_today_still_fresh(self, tmp_path):
        """(3) 邊界:as_of == today 仍 fresh(日頻)。"""
        _write_daily(tmp_path, _TODAY)       
        r = compute_cache_staleness("twii_ohlcv", cache_dir=tmp_path, today=_TODAY)
        assert r["as_of"] == _TODAY and r["age_days"] == 0
        assert r["is_stale"] is False and r["reason"] is None

    def test_monthly_asof_current_month_start_still_fresh(self, tmp_path):
        """(3b) 月頻邊界:as_of=本月月初(≤ today)仍 fresh。"""
        _write_monthly(tmp_path, dt.date(2026, 9, 1))
        r = compute_cache_staleness("finmind_m1m2", cache_dir=tmp_path, today=_TODAY)
        assert r["is_stale"] is False, r["reason"]
        assert "無法判定" not in (r["reason"] or "")

    def test_asof_yesterday_behaviour_unchanged(self, tmp_path):
        """(4) as_of = today-1:日頻 fresh、age_days=1、reason None。"""
        _write_daily(tmp_path, dt.date(2026, 9, 9))
        r = compute_cache_staleness("twii_ohlcv", cache_dir=tmp_path, today=_TODAY)
        assert r["is_stale"] is False and r["age_days"] == 1 and r["reason"] is None

    def test_missing_or_empty_df_behaviour_unchanged(self, tmp_path):
        """(5) 缺 date 欄 / 空 df:仍 is_stale=True、as_of None,且 reason 不是「無法判定」(未來日期專用)。"""
        no_date = compute_cache_staleness(
            "twii_ohlcv", cache_dir=tmp_path, today=_TODAY,
            df=pd.DataFrame({"close": [1, 2]}))
        empty = compute_cache_staleness(
            "twii_ohlcv", cache_dir=tmp_path, today=_TODAY,
            df=pd.DataFrame({"date": [], "close": []}))
        for r in (no_date, empty):
            assert r["is_stale"] is True
            assert r["as_of"] is None and r["age_days"] is None
            assert "無法判定" not in (r["reason"] or "")
            assert "判不出資料日期" in (r["reason"] or "")
