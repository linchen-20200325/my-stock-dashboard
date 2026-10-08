"""批 Z15（2026-10-08）—— 只加測試，⛔ 不改正式碼。

- Z6-n3：NDC 景氣對策燈號紅線（`shared/macro_buckets.classify_danger` band 分支，
  `ndc_signal.red` = 38.0、`ndc_signal.red_lo` = 16.0）只有整數測試 ——
  同型於批 Z4 QA R9-M21（高側黃線，已由 `tests/test_batch_z6.py::TestZ4n1NdcHighSideYellowBoundary` 補），
  紅線兩側的突變在全量下存活：
    高側 `v >= red`    → 突變 `v > red − 0.05`
    低側 `v <= red_lo` → 突變 `v < red_lo + 0.05`
  補「界值判紅、緊鄰界值的下一個浮點數（往黃燈帶方向）判黃」。
  分數若恆為整數則上述突變與正式碼等價（推論，HANDOFF 列內已註）；但 `classify_danger`
  收任意有限浮點數（消費端未取整），故仍以非整數輸入釘住。
"""
from __future__ import annotations

import math

import pytest

from shared.macro_buckets import SPECS_BY_KEY, classify_danger

NDC = SPECS_BY_KEY['ndc_signal']
_BELOW_RED = math.nextafter(NDC.red, -math.inf)        # 高側紅線往下一格（黃燈帶內）
_ABOVE_RED_LO = math.nextafter(NDC.red_lo, math.inf)   # 低側紅線往上一格（黃燈帶內）

_HIGH_YELLOW = [_BELOW_RED, 37.999, 37.99, 37.96, 37.951]
_LOW_YELLOW = [_ABOVE_RED_LO, 16.001, 16.01, 16.04, 16.049]


class TestZ6n3NdcRedLineBoundary:
    def test_premise_spec(self):
        """判式在 band 分支：`(red_lo is not None and v <= red_lo) or v >= red` → red。"""
        assert NDC.direction == 'band'
        assert (NDC.yellow, NDC.red, NDC.yellow_lo, NDC.red_lo) == (32.0, 38.0, 22.0, 16.0)
        assert NDC.yellow <= _BELOW_RED < NDC.red              # 緊鄰高側紅線的下一格落在高側黃燈帶
        assert NDC.red_lo < _ABOVE_RED_LO <= NDC.yellow_lo     # 緊鄰低側紅線的上一格落在低側黃燈帶

    # ── 高側 ──────────────────────────────────────────────────────────────
    def test_high_red_line_itself_is_red(self):
        assert classify_danger(NDC.red, NDC) == 'red'
        assert classify_danger(38, NDC) == 'red'

    @pytest.mark.parametrize('v', _HIGH_YELLOW,
                             ids=['nextafter', '37.999', '37.99', '37.96', '37.951'])
    def test_just_below_high_red_is_yellow(self, v):
        assert classify_danger(v, NDC) == 'yellow'

    def test_premise_inputs_split_the_high_mutant(self):
        """突變 `v > red − 0.05`：上面的輸入在突變下判紅、在正式碼下判黃 —— 殺得掉。"""
        for v in _HIGH_YELLOW:
            assert (v > NDC.red - 0.05) and not (v >= NDC.red), v

    # ── 低側 ──────────────────────────────────────────────────────────────
    def test_low_red_line_itself_is_red(self):
        assert classify_danger(NDC.red_lo, NDC) == 'red'
        assert classify_danger(16, NDC) == 'red'

    @pytest.mark.parametrize('v', _LOW_YELLOW,
                             ids=['nextafter', '16.001', '16.01', '16.04', '16.049'])
    def test_just_above_low_red_is_yellow(self, v):
        assert classify_danger(v, NDC) == 'yellow'

    def test_premise_inputs_split_the_low_mutant(self):
        """突變 `v < red_lo + 0.05`：上面的輸入在突變下判紅、在正式碼下判黃 —— 殺得掉。"""
        for v in _LOW_YELLOW:
            assert (v < NDC.red_lo + 0.05) and not (v <= NDC.red_lo), v
