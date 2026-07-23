"""tests/test_macd_kernel_b6.py — B6 MACD SSOT kernel。

驗 compute_macd 三線數學 + adjust 語意 + weekly_macd_hist 樣本 gate。
釘死重構前後等價:個股初篩 daily(adjust=True)/ 週線 12/26/9(adjust=False)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from shared.signal_thresholds import WK_MACD_DAYS_PER_WEEK, WK_MACD_MIN_WEEKS
from src.compute.scoring.exit_signals import compute_macd, weekly_macd_hist


def test_compute_macd_matches_old_daily_formula_adjust_true():
    # 釘死 tab_stock_picker 舊 daily 公式(pandas ewm 預設 adjust=True)逐點等價
    s = pd.Series(np.linspace(100, 120, 60) + np.sin(np.arange(60)))
    dif, dea, hist = compute_macd(s, adjust=True)
    _dif = s.ewm(span=12).mean() - s.ewm(span=26).mean()
    _dea = _dif.ewm(span=9).mean()
    assert np.allclose(dif.values, _dif.values)
    assert np.allclose(dea.values, _dea.values)
    assert np.allclose(hist.values, (_dif - _dea).values)


def test_compute_macd_default_spans_equal_explicit_12_26_9():
    s = pd.Series(np.random.default_rng(0).normal(100, 2, 80).cumsum())
    for a, b in zip(compute_macd(s), compute_macd(s, fast=12, slow=26, signal=9)):
        assert np.allclose(a.values, b.values)


def test_compute_macd_adjust_flag_changes_result():
    s = pd.Series(np.linspace(100, 130, 50))
    _, _, h_false = compute_macd(s, adjust=False)
    _, _, h_true = compute_macd(s, adjust=True)
    assert not np.allclose(h_false.values, h_true.values)   # adjust 語意確實不同


def test_weekly_macd_hist_insufficient_returns_none():
    # < 35 週 = 175 交易日 → None(§1 不臆造),None/空亦 None
    short = list(range(WK_MACD_MIN_WEEKS * WK_MACD_DAYS_PER_WEEK - 1))
    assert weekly_macd_hist(short) is None
    assert weekly_macd_hist(None) is None
    assert weekly_macd_hist([]) is None


def test_weekly_macd_hist_sufficient_returns_hist_list():
    n_days = WK_MACD_MIN_WEEKS * WK_MACD_DAYS_PER_WEEK + 20
    hist = weekly_macd_hist(list(np.linspace(50, 80, n_days)))
    assert isinstance(hist, list) and len(hist) >= WK_MACD_MIN_WEEKS
    assert all(isinstance(x, float) for x in hist)
