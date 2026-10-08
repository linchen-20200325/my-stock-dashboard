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
- C7-n11（只改 `SPEC.md` §11，⛔ 不改正式碼）：客戶 2026-10-06 裁示 Q-r9d ④「數字等於門檻算較差那邊」。
  程式 `classify_danger` 本就如此（`high_bad` `>=`、`low_bad` `<=`）；§11 表的健康 35、PMI 46、ADL 35、
  旌旗 40 紅欄寫 `<`、M1B-M2 綠欄寫 `≥1`／紅欄寫 `<0`，與程式不一致 → 改表。
  本檔釘兩件事：(1) 程式在這些界值的判法（防有人反過來改程式去配舊表）；
  (2) §11 表該 5 列的紅／綠欄字面與程式一致（防表再漂回去）。
  ⚠️ 燈卡畫面字（`DangerSpec.note`／`source`）的同類不一致**未改**（需新字句，停手登記），本檔不釘。
"""
from __future__ import annotations

import math
import pathlib
import re

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


# ══════════════════════════════════════════════════════════════════════════
# C7-n11：§11 等號歸屬 —— 數字剛好等於門檻算較差那邊（Q-r9d ④）
# ══════════════════════════════════════════════════════════════════════════
_EQ_CASES = [
    # key,          值,    預期燈
    ('health',      35.0, 'red'),
    ('health',      50.0, 'yellow'),
    ('ism_pmi',     46.0, 'red'),
    ('ism_pmi',     50.0, 'yellow'),
    ('adl',         35.0, 'red'),
    ('adl',         50.0, 'yellow'),
    ('jingqi',      40.0, 'red'),
    ('jingqi',      60.0, 'yellow'),
    ('m1b_m2_gap',   1.0, 'yellow'),
    ('m1b_m2_gap',   0.0, 'red'),
]


class TestC7n11EqualityGoesToWorseSide:
    @pytest.mark.parametrize('key,v,lvl', _EQ_CASES, ids=[f'{k}={v:g}' for k, v, _ in _EQ_CASES])
    def test_threshold_value_itself_is_worse_side(self, key, v, lvl):
        assert classify_danger(v, SPECS_BY_KEY[key]) == lvl

    @pytest.mark.parametrize('key,v', [('health', 50.0), ('ism_pmi', 50.0), ('adl', 50.0),
                                       ('jingqi', 60.0), ('m1b_m2_gap', 1.0)],
                             ids=['health', 'ism_pmi', 'adl', 'jingqi', 'm1b_m2_gap'])
    def test_just_above_yellow_is_green(self, key, v):
        assert classify_danger(math.nextafter(v, math.inf), SPECS_BY_KEY[key]) == 'green'


_SPEC_MD = pathlib.Path(__file__).resolve().parents[1] / 'SPEC.md'


def _spec11_row(label_prefix: str) -> list[str]:
    text = _SPEC_MD.read_text(encoding='utf-8')
    sec = text.split('## §11 ', 1)[1].split('\n## ', 1)[0]
    rows = [ln for ln in sec.splitlines() if ln.startswith(f'| {label_prefix}')]
    assert len(rows) == 1, (label_prefix, rows)
    return [c.strip() for c in rows[0].strip('|').split('|')]


class TestC7n11Spec11TableMatchesCode:
    @pytest.mark.parametrize('label,green,red', [
        ('總經健康評分', '>50', '≤35'),
        ('M1B-M2 資金動能', '>1 黃金交叉', '≤0 死亡交叉'),
        ('台灣 PMI', '>50', '≤46 嚴重收縮'),
        ('ADL 漲跌家數比', '>50', '≤35 廣度崩'),
        ('旌旗指數', '>60 積極', '≤40 弱勢'),
    ])
    def test_row_green_red_columns(self, label, green, red):
        cells = _spec11_row(label)
        assert (cells[2], cells[4]) == (green, red)

    def test_no_strict_less_than_red_for_low_bad_rows(self):
        """low_bad 列紅欄不得再寫 `<`（程式 `<=`）。"""
        for label in ('總經健康評分', 'M1B-M2 資金動能', '台灣 PMI', 'ADL 漲跌家數比', '旌旗指數'):
            assert not re.match(r'^<', _spec11_row(label)[4]), label
