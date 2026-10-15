# -*- coding: utf-8 -*-
"""2026-10-15 — 校準腳本 M1B/M2 Point-in-Time（§2.3）守衛。

修的 bug（兩組獨立確認）
------------------------
`data_cache/finmind_m1m2.parquet` 的 `date` 是**資料月月初**（見
`scripts/update_macro_history.py` 檔頭），不是公布日。

- `scripts/calibrate_health_weights.py::reconstruct_score` 原本以 `date` 直接對每日收盤
  backward `merge_asof`（無發布延遲位移）⇒ M 月資料在 M/01 即可見,最早提前「M 月天數 + lag」天。
- `scripts/calibrate_macro_traffic.py::_enrich_with_finmind` 原本左 join 月初值 + 無上限 ffill
  ⇒ 同樣 look-ahead；且月初遇週末/假日那一列 join 不到、整月被丟掉。

現行：兩支腳本共用 L2 `src.compute.macro.health_calibration.align_monthly_to_daily_pit`，
可用日 = L0 `shared.staleness.monthly_publication_due(M, indicator="m1b_m2")`。

本檔預期值一律由 SSOT 函式算出（不寫死 lag 天數），所以 lag 日後依實測調整時本檔不必改；
但「可用日必在資料月結束之後」這條不變量寫死在 `test_available_date_after_month_end`。
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from shared.staleness import monthly_publication_due
from src.compute.macro.health_calibration import align_monthly_to_daily_pit

_IND = "m1b_m2"
_TOL = pd.Timedelta("40D")
_SPECIAL = 999.0          # 被追蹤月份的特殊值
_TRACK = pd.Timestamp("2026-03-01")   # 被追蹤的資料月（月初 = 週日）


def _monthly(start="2025-10-01", months=9, special_month=_TRACK):
    idx = pd.date_range(start=start, periods=months, freq="MS")
    gap = [float(i + 1) for i in range(months)]          # 1, 2, 3, ...（可辨識期別）
    df = pd.DataFrame({"date": idx, "m1b": [5.0] * months, "m2": [4.0] * months,
                       "m1b_m2_gap": gap})
    df.loc[df["date"] == special_month, "m1b_m2_gap"] = _SPECIAL
    return df


def _avail(month) -> pd.Timestamp:
    return pd.Timestamp(monthly_publication_due(pd.Timestamp(month), indicator=_IND))


def _gap_of(mdf, month) -> float:
    return float(mdf.loc[mdf["date"] == pd.Timestamp(month), "m1b_m2_gap"].iloc[0])


_PREV = pd.Timestamp("2026-02-01")


# ══════════════════════════════════════════════════════════════════════
# L2 純函式
# ══════════════════════════════════════════════════════════════════════
class TestAlignMonthlyToDailyPit:
    def test_available_date_after_month_end(self):
        # 不變量:任何資料月的可用日都在該月結束之後(否則必有 look-ahead)
        for m in pd.date_range("2024-01-01", periods=24, freq="MS"):
            assert _avail(m) > m + pd.offsets.MonthEnd(0)

    def test_not_visible_before_available_date(self):
        mdf = _monthly()
        days = pd.date_range("2026-02-01", "2026-06-30", freq="D")
        out = align_monthly_to_daily_pit(days, mdf, ["m1b_m2_gap"],
                                         indicator=_IND, tolerance=_TOL)
        av = _avail(_TRACK)
        before = out.loc[out.index < av]
        assert not (before["m1b_m2_gap"] == _SPECIAL).any(), \
            "資料月 M 的值在其可用日之前被取到 = look-ahead"
        # M 月內每一天都取不到 M
        in_month = out.loc[(out.index >= _TRACK) & (out.index <= _TRACK + pd.offsets.MonthEnd(0))]
        assert len(in_month) == 31
        assert (in_month["data_month"] < _TRACK).all()
        # 可用日前一天 → 取到的是前一期
        eve = out.loc[av - pd.Timedelta(days=1)]
        assert eve["data_month"] == _PREV
        assert eve["m1b_m2_gap"] == _gap_of(mdf, _PREV)

    def test_visible_on_and_after_available_date(self):
        mdf = _monthly()
        days = pd.date_range("2026-02-01", "2026-06-30", freq="D")
        out = align_monthly_to_daily_pit(days, mdf, ["m1b_m2_gap"],
                                         indicator=_IND, tolerance=_TOL)
        av = _avail(_TRACK)
        nxt = _avail(_TRACK + pd.offsets.MonthBegin(1))
        window = out.loc[(out.index >= av) & (out.index < nxt)]
        assert len(window) > 0
        assert (window["m1b_m2_gap"] == _SPECIAL).all()
        assert (window["data_month"] == _TRACK).all()
        assert out.loc[nxt, "data_month"] == _TRACK + pd.offsets.MonthBegin(1)

    def test_weekend_month_start_not_dropped(self):
        # 2026-02-01、2026-03-01 都是週日;交易日 index 只有平日
        assert pd.Timestamp("2026-02-01").weekday() == 6
        assert _TRACK.weekday() == 6
        mdf = _monthly()
        bdays = pd.bdate_range("2025-11-01", "2026-07-31")
        out = align_monthly_to_daily_pit(bdays, mdf, ["m1b_m2_gap"],
                                         indicator=_IND, tolerance=_TOL)
        seen = set(out["data_month"].dropna())
        for m in mdf["date"]:
            if _avail(m) <= bdays[-1]:
                assert m in seen, f"資料月 {m.date()} 在日頻輸出中消失(丟月)"

    def test_tolerance_measured_from_available_date(self):
        # 只有一期:可用日 + tol 之後 → NaN(不無上限沿用)
        mdf = _monthly(start="2026-03-01", months=1)
        av = _avail(_TRACK)
        days = pd.DatetimeIndex([av, av + _TOL, av + _TOL + pd.Timedelta(days=1)])
        out = align_monthly_to_daily_pit(days, mdf, ["m1b_m2_gap"],
                                         indicator=_IND, tolerance=_TOL)
        assert out["m1b_m2_gap"].iloc[0] == _SPECIAL
        assert out["m1b_m2_gap"].iloc[1] == _SPECIAL
        assert pd.isna(out["m1b_m2_gap"].iloc[2])

    def test_preserves_input_order(self):
        mdf = _monthly()
        days = pd.DatetimeIndex(["2026-06-15", "2026-01-05", "2026-04-30"])
        out = align_monthly_to_daily_pit(days, mdf, ["m1b_m2_gap"],
                                         indicator=_IND, tolerance=_TOL)
        assert list(out.index) == list(days)
        ref = align_monthly_to_daily_pit(days.sort_values(), mdf, ["m1b_m2_gap"],
                                         indicator=_IND, tolerance=_TOL)
        for d in days:
            assert out.loc[d, "data_month"] == ref.loc[d, "data_month"]

    def test_unregistered_indicator_raises(self):
        with pytest.raises(ValueError):
            align_monthly_to_daily_pit(pd.DatetimeIndex(["2026-05-01"]), _monthly(),
                                       ["m1b_m2_gap"], indicator="__nope__",
                                       tolerance=_TOL)

    def test_nat_date_raises(self):
        mdf = _monthly()
        mdf.loc[0, "date"] = pd.NaT
        with pytest.raises(ValueError):
            align_monthly_to_daily_pit(pd.DatetimeIndex(["2026-05-01"]), mdf,
                                       ["m1b_m2_gap"], indicator=_IND, tolerance=_TOL)


# ══════════════════════════════════════════════════════════════════════
# scripts/calibrate_health_weights.py::reconstruct_score
# ══════════════════════════════════════════════════════════════════════
class TestCalibrateHealthWeightsPit:
    def _run(self, monkeypatch, mdf):
        import scripts.calibrate_health_weights as chw
        calls = {}

        def _fake_regime(**kw):
            calls[kw["_dt"]] = (kw.get("m1b_m2_gap"), kw.get("m1b_m2_prev"))
            return {"score": 1.0, "max_score": 4.0}

        # 收盤 400 個交易日:MA120 有效區段涵蓋 2026-02 ~ 2026-07
        idx = pd.bdate_range(end="2026-07-31", periods=400)
        close = pd.Series(np.linspace(100.0, 140.0, len(idx)), index=idx)
        inst = pd.DataFrame({"date": idx, "foreign_buy": [1.0] * len(idx)})

        # 注入 dt:包一層把 index_close 對回日期
        _by_close = {float(v): d for d, v in close.items()}

        def _regime(**kw):
            kw["_dt"] = _by_close[kw["index_close"]]
            return _fake_regime(**kw)

        monkeypatch.setattr(chw, "market_regime", _regime)
        chw.reconstruct_score(close, inst, mdf)
        return calls

    def test_no_lookahead_and_visible_after(self, monkeypatch):
        mdf = _monthly(start="2024-06-01", months=26)
        calls = self._run(monkeypatch, mdf)
        av = _avail(_TRACK)
        prev_gap = _gap_of(mdf, _PREV)
        days = sorted(calls)
        assert days[0] < _TRACK and days[-1] > av
        for d in days:
            gap, prev = calls[d]
            if d < av:
                assert gap != _SPECIAL, f"{d.date()} 在可用日 {av.date()} 前就看到 3 月值"
            if _TRACK <= d < av:
                # M 月內:lag 27 時月初到 2 月可用日之間取到的是 1 月,之後是 2 月 —— 都早於 M
                assert gap in (_gap_of(mdf, "2026-01-01"), prev_gap), d
        eve = max(d for d in days if d < av)
        assert calls[eve][0] == prev_gap, f"可用日前一個交易日 {eve.date()} 應取前一期(2 月)"
        after = [d for d in days if d >= av and d < _avail(_TRACK + pd.offsets.MonthBegin(1))]
        assert after, "測試資料應涵蓋可用日之後"
        for d in after:
            gap, prev = calls[d]
            assert gap == _SPECIAL
            assert prev == prev_gap   # 上一期 = 2 月,與當期同列帶出

    def test_weekend_month_start_not_dropped(self, monkeypatch):
        mdf = _monthly(start="2024-06-01", months=26)
        calls = self._run(monkeypatch, mdf)
        seen = {g for g, _ in calls.values() if g is not None}
        # 只檢查「可用日落在評分區間內」的月份(原 merge_asof 寫法本來就不丟月,
        # 本條是回歸守衛,防日後改成 join 類寫法時丟掉週末月初那一列)
        for m in mdf["date"]:
            if min(calls) <= _avail(m) <= max(calls):
                assert _gap_of(mdf, m) in seen, f"資料月 {m.date()} 消失"


# ══════════════════════════════════════════════════════════════════════
# scripts/calibrate_macro_traffic.py::_enrich_with_finmind
# ══════════════════════════════════════════════════════════════════════
class TestCalibrateMacroTrafficPit:
    def _run(self, tmp_path, mdf):
        from scripts import calibrate_macro_traffic as cmt
        mdf.to_parquet(tmp_path / "finmind_m1m2.parquet", index=False)
        idx = pd.bdate_range("2025-11-01", "2026-07-31")
        df_twii = pd.DataFrame({"Close": np.linspace(100.0, 120.0, len(idx))}, index=idx)
        original = cmt._CACHE_DIR
        cmt._CACHE_DIR = str(tmp_path)
        try:
            return cmt._enrich_with_finmind(df_twii)
        finally:
            cmt._CACHE_DIR = original

    def test_no_lookahead_and_visible_after(self, tmp_path):
        mdf = _monthly()
        out = self._run(tmp_path, mdf)
        av = _avail(_TRACK)
        before = out.loc[out.index < av, "m1b_m2_gap"]
        assert not (before == _SPECIAL).any(), "可用日前看到 3 月值 = look-ahead"
        in_march = out.loc[(out.index >= _TRACK) & (out.index < av), "m1b_m2_gap"]
        assert len(in_march) > 0
        # 3 月內與可用日前一個交易日:前一期(2 月)或更早,絕不是 3 月
        eve = out.loc[out.index < av].iloc[-1]
        assert eve["m1b_m2_gap"] == _gap_of(mdf, _PREV)
        nxt = _avail(_TRACK + pd.offsets.MonthBegin(1))
        window = out.loc[(out.index >= av) & (out.index < nxt), "m1b_m2_gap"]
        assert len(window) > 0 and (window == _SPECIAL).all()

    def test_weekend_month_start_not_dropped(self, tmp_path):
        mdf = _monthly()
        out = self._run(tmp_path, mdf)
        seen = set(out["m1b_m2_gap"].dropna())
        for m in mdf["date"]:
            if _avail(m) <= out.index[-1]:
                assert _gap_of(mdf, m) in seen, f"資料月 {m.date()} 消失(丟月)"

    def test_no_unbounded_ffill(self, tmp_path):
        # 只有 2025-10 一期 → 可用日 + 40d 之後不得再沿用
        mdf = _monthly(start="2025-10-01", months=1, special_month=pd.Timestamp("2025-10-01"))
        out = self._run(tmp_path, mdf)
        av = _avail("2025-10-01")
        late = out.loc[out.index > av + _TOL, "m1b_m2_gap"]
        assert len(late) > 0 and late.isna().all()
