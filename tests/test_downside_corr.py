"""空頭相關(危機失效)純函式測試(#3a)。"""
import numpy as np
import pandas as pd

from src.compute.etf.etf_smart_analysis import (
    DOWNSIDE_CORR_HIGH_WARN,
    _downside_corr_series,
    downside_corr_warn_label,
    find_best_diversifiers,
)


def test_downside_corr_high_when_crash_together():
    # 造兩檔:平時獨立,但 A 大跌時 B 也大跌 → 空頭相關高
    rng = np.random.default_rng(0)
    n = 120
    a = rng.normal(0, 0.01, n)
    b = rng.normal(0, 0.01, n)
    crash = a < np.quantile(a, 0.2)
    b = np.where(crash, a * 1.1, b)   # A 崩時 B 跟著崩
    ret = pd.DataFrame({'A': a, 'B': b})
    dc = _downside_corr_series(ret, 'A')
    assert dc is not None and dc['B'] > 0.5


def test_downside_corr_insufficient_data_none():
    ret = pd.DataFrame({'A': [0.01, -0.02], 'B': [0.0, 0.01]})
    assert _downside_corr_series(ret, 'A') is None


def test_warn_label():
    assert downside_corr_warn_label(0.9) == '🔴 崩盤一起跌'
    assert downside_corr_warn_label(DOWNSIDE_CORR_HIGH_WARN) == '🔴 崩盤一起跌'
    assert downside_corr_warn_label(0.3) == ''
    assert downside_corr_warn_label(None) == ''
    assert downside_corr_warn_label(np.nan) == ''


def test_find_best_diversifiers_has_downside_col():
    idx = pd.date_range('2023-01-01', periods=200, freq='B')
    rng = np.random.default_rng(3)
    px = pd.DataFrame({
        '0050.TW': 100 + np.cumsum(rng.normal(0, 1, 200)),
        '0056.TW': 50 + np.cumsum(rng.normal(0, 1, 200)),
    }, index=idx)
    out = find_best_diversifiers('0050.TW', px, {}, top_n=5)
    assert '空頭相關' in out.columns
