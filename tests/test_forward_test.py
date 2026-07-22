"""tests/test_forward_test.py — 前進式驗證對帳(v19.141 FT-1）。

驗前進報酬 / 等權平均 / 勝率 / vs 0050 超額 + §1 誠實邊界（缺價剔除不灌 0 / 樣本不足旗標 /
基準缺 excess=NaN / 進場價無效剔除）。數學以手算值精確斷言。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.compute.screener.forward_test import reconcile_forward_test


def _picks(rows):
    return pd.DataFrame(rows, columns=["cohort", "stock_id", "entry_price"])


# ── 基本數學 ──────────────────────────────────────────────────
def test_returns_and_excess_math():
    # A: 100→120 = +20%；B: 50→45 = −10%；平均 = +5%
    picks = _picks([("2025Q1", "A", 100), ("2025Q1", "B", 50)])
    df, overall = reconcile_forward_test(
        picks, {"A": 120, "B": 45}, benchmark_returns={"2025Q1": 0.02})  # 0050 +2%
    r = df.iloc[0]
    assert r["avg_return_pct"] == pytest.approx(5.0)
    assert r["benchmark_return_pct"] == pytest.approx(2.0)
    assert r["excess_pct"] == pytest.approx(3.0)          # 5% − 2%
    assert r["hit_rate_pct"] == pytest.approx(50.0)       # A 賺 B 賠 → 1/2
    assert r["beat_bench_rate_pct"] == pytest.approx(50.0)  # 只有 A(+20%)>2%
    assert r["n_valid"] == 2 and r["n_dropped"] == 0


def test_overall_avg_excess_only_solid_cohorts():
    picks = _picks([("C1", "A", 100), ("C1", "B", 100), ("C1", "C", 100),  # 3 檔 → solid
                    ("C2", "X", 100)])                                      # 1 檔 → 不足
    df, overall = reconcile_forward_test(
        picks, {"A": 110, "B": 110, "C": 110, "X": 200},
        benchmark_returns={"C1": 0.05, "C2": 0.05}, min_cohort_picks=3)
    _c1 = df[df["cohort"] == "C1"].iloc[0]
    _c2 = df[df["cohort"] == "C2"].iloc[0]
    assert _c1["enough_sample"] and not _c2["enough_sample"]
    # overall 只採 solid(C1:+10% − 5% = +5%),不被 C2(+100%)汙染
    assert overall["avg_excess_pct"] == pytest.approx(5.0)
    assert overall["n_cohorts_solid"] == 1


# ── §1 誠實邊界 ──────────────────────────────────────────────
def test_missing_current_price_dropped_not_zero():
    # B 凍結後下市 → current_prices 無 B → 剔除,不當 0 報酬拉低平均
    picks = _picks([("Q", "A", 100), ("Q", "B", 100)])
    df, _ = reconcile_forward_test(picks, {"A": 130})   # 只有 A 有現價
    r = df.iloc[0]
    assert r["n_valid"] == 1 and r["n_dropped"] == 1
    assert r["avg_return_pct"] == pytest.approx(30.0)   # 只算 A(+30%),非 (30+(-100))/2


def test_invalid_entry_price_dropped():
    picks = _picks([("Q", "A", 0), ("Q", "B", float("nan")), ("Q", "C", 100)])
    df, _ = reconcile_forward_test(picks, {"A": 50, "B": 50, "C": 150})
    r = df.iloc[0]
    assert r["n_valid"] == 1                              # 只有 C 進場價有效
    assert r["avg_return_pct"] == pytest.approx(50.0)


def test_no_benchmark_excess_nan():
    picks = _picks([("Q", "A", 100), ("Q", "B", 100)])
    df, overall = reconcile_forward_test(picks, {"A": 110, "B": 120})  # 無 benchmark
    r = df.iloc[0]
    assert np.isnan(r["excess_pct"]) and np.isnan(r["benchmark_return_pct"])
    assert r["avg_return_pct"] == pytest.approx(15.0)     # 絕對報酬照算
    assert np.isnan(overall["avg_excess_pct"])


def test_sample_too_small_flag():
    picks = _picks([("Q", "A", 100), ("Q", "B", 100)])   # 2 檔 < 預設 3
    df, overall = reconcile_forward_test(picks, {"A": 110, "B": 110})
    assert not df.iloc[0]["enough_sample"]
    assert "僅供參考" in overall["note"]


def test_cohort_all_dropped_no_crash():
    picks = _picks([("Q", "A", 100), ("Q", "B", 100)])
    df, _ = reconcile_forward_test(picks, {})            # 全無現價
    r = df.iloc[0]
    assert r["n_valid"] == 0 and np.isnan(r["avg_return_pct"])
    assert not r["enough_sample"]


def test_empty_and_missing_cols():
    df, overall = reconcile_forward_test(pd.DataFrame(), {})
    assert df.empty and overall["n_picks_total"] == 0
    with pytest.raises(ValueError, match="缺必備欄"):
        reconcile_forward_test(pd.DataFrame({"cohort": ["Q"]}), {})


def test_multi_cohort_sorted():
    picks = _picks([("2025Q2", "A", 100), ("2025Q1", "B", 100)])
    df, _ = reconcile_forward_test(picks, {"A": 110, "B": 110})
    assert list(df["cohort"]) == ["2025Q1", "2025Q2"]    # 依 cohort 排序
