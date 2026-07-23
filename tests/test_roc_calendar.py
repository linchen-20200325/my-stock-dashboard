"""tests/test_roc_calendar.py — ROC 曆換算 SSOT(B3 / SSOT-H2)。

驗 shared/roc_calendar 的 ± 1911 位移 + 往返一致性。純算術離線可測。
接住原本散落 8+ 處的 magic number 1911 收攏後不走鐘。
"""
from __future__ import annotations

import pytest

from shared.roc_calendar import (
    ROC_EPOCH_OFFSET,
    gregorian_to_roc_year,
    roc_to_gregorian_year,
)


def test_epoch_offset_is_1911():
    # 民國元年 = 西元 1912 → 位移必為 1911(釘死,防未來被誤改)
    assert ROC_EPOCH_OFFSET == 1911


@pytest.mark.parametrize("roc, greg", [
    (1, 1912),      # 民國元年
    (100, 2011),
    (115, 2026),    # 當前年附近
    (50, 1961),     # macro_snapshot sanity 下界附近
])
def test_roc_to_gregorian(roc, greg):
    assert roc_to_gregorian_year(roc) == greg


@pytest.mark.parametrize("greg, roc", [
    (1912, 1),
    (2011, 100),
    (2026, 115),
    (1961, 50),
])
def test_gregorian_to_roc(greg, roc):
    assert gregorian_to_roc_year(greg) == roc


def test_round_trip_identity():
    for roc in range(1, 200):
        assert gregorian_to_roc_year(roc_to_gregorian_year(roc)) == roc


def test_accepts_numeric_string_via_int_coercion():
    # 各 fetcher 常傳 int(s[:3]) 已轉好,但保險驗 str 也不炸(int() 容錯)
    assert roc_to_gregorian_year("115") == 2026
    assert gregorian_to_roc_year("2026") == 115
