"""分散度『價格相關』警示純函式測試(v19.63)。"""
import numpy as np

from src.compute.etf.etf_smart_analysis import (
    PRICE_CORR_HIGH_WARN,
    price_corr_warn_label,
)


def test_high_corr_warns():
    assert price_corr_warn_label(0.85) == '⚠️ 高度同向'
    assert price_corr_warn_label(PRICE_CORR_HIGH_WARN) == '⚠️ 高度同向'  # 邊界含


def test_low_corr_no_warn():
    assert price_corr_warn_label(0.3) == ''
    assert price_corr_warn_label(-0.5) == ''
    assert price_corr_warn_label(0.69) == ''


def test_none_and_nan_safe():
    assert price_corr_warn_label(None) == ''
    assert price_corr_warn_label(np.nan) == ''
    assert price_corr_warn_label('x') == ''
