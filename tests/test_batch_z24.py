"""批 Z24（防禦補強）—— 進階警示訊號 1／3 非有限不印 ＋ 先行指標表 int 欄數字字串不崩
（基底 `wip/batch-z23` `faa271e2`）。

- §三「⚡ 進階警示」訊號 1：外資大小有限且 < -20000、外(選) = -inf 時原印「選擇權外資淨空-inf千元」
  ⇒ 外(選)走 `_finite_yoy`，非有限落入既有「不帶該句」分支（與外(選) None／NaN 同一段輸出）。
- 同區訊號 3：外資或投信 ±inf 原印「外資+inf億」「投信-inf億」⇒ 非有限落入既有「不列警示」分支
  （與該欄 None 同一段輸出）。有限值逐字不變。
- L1 `leading_indicators.render_leading_table`：BRACKET 四欄與「未平倉口數」遇可轉有限浮點數的數字字串
  （"12.5"／"-0.25"／"1e3"）時 `int()` 拋 ValueError、整張表不渲染 ⇒ int() 轉不了時先轉 float 再取整，
  與同欄有限 float 輸入逐字一致（基底實跑：12.5 →「▲ 12」、-0.25 →「0」）。

golden：有限值的修前輸出於基底 `faa271e2` 以本檔同一支 harness 實跑後寫死 sha256（⛔ 不由現行碼反推）。
本檔所有斷言皆為實跑行為斷言，不讀原始碼字面。
"""
from __future__ import annotations

import hashlib
import math
import re
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from src.data.macro.leading_indicators import render_leading_table
from tests.test_batch_z10 import _chips, _digest
from tests.test_batch_z21 import _COLS, _cells, _txt

#: 獨立字詞的 inf／nan（排除「YFinance」等既有字句）
_INFNAN = re.compile(r'(?<![A-Za-z])(inf|nan)(?![A-Za-z])', re.I)

_BAD = {'pinf': math.inf, 'ninf': -math.inf, 'np_ninf': np.float64(-np.inf), 'np_pinf': np.float64(np.inf),
        'f32_ninf': np.float32(-np.inf), 'f32_pinf': np.float32(np.inf),
        'dec_ninf': Decimal('-Infinity'), 'dec_pinf': Decimal('Infinity'), 'nan': math.nan}


def _li_s(fnet=None, opt=None, fo=None, tr=None):
    return pd.DataFrame({'日期': ['2026-10-01'], '外資大小': pd.Series([fnet], dtype=object),
                         '選PCR': pd.Series([110.0], dtype=object), '外(選)': pd.Series([opt], dtype=object),
                         '外資': pd.Series([fo], dtype=object), '投信': pd.Series([tr], dtype=object)})


def _no_csv(out):
    """「⬇️ 下載先行指標 CSV」匯出原始值（inf 照實寫出、None 為空欄），屬原始資料、不在本批範圍。"""
    return [(k, t) for k, t in out if 'download="先行指標.csv"' not in t]


# ══════════════════════════════════════════════════════════════════════════
# 1. 訊號 1：外(選) 非有限不帶「選擇權外資淨空…千元」
# ══════════════════════════════════════════════════════════════════════════
class TestSignal1OptNonFinite:
    @pytest.mark.parametrize('bad', sorted(_BAD))
    @pytest.mark.parametrize('fnet', [-25000.0, -40000.0, -20001])
    def test_not_printed(self, bad, fnet, monkeypatch):
        txt = _txt(_chips(_li_s(fnet=fnet, opt=_BAD[bad]), monkeypatch))
        assert not _INFNAN.search(txt), txt          # 修前：「選擇權外資淨空-inf千元」
        assert '選擇權外資淨空' not in txt and '期權同向崩盤警戒' not in txt, txt

    @pytest.mark.parametrize('bad', sorted(_BAD))
    @pytest.mark.parametrize('fnet', [-25000.0, -40000.0])
    def test_same_as_missing(self, bad, fnet, monkeypatch):
        got = _chips(_li_s(fnet=fnet, opt=_BAD[bad]), monkeypatch)
        monkeypatch.undo()
        ref = _chips(_li_s(fnet=fnet, opt=None), monkeypatch)
        assert _digest(_no_csv(got)) == _digest(_no_csv(ref))
        assert len(got) - len(_no_csv(got)) == 1     # 只濾掉那一個下載鈕

    #: 修前（基底 faa271e2）同一支 `_chips` 實跑的整段 §三 sha256（涵蓋訊號 1 崩盤／大空／未達門檻各分支）
    _BASE = {
        'crash': (dict(fnet=-25000.0, opt=-5000.0), 'eebff6691c81ce339417ccb08fdc5630dc9996602726bb1bf5bd0925978c881a'),
        'crash_m1': (dict(fnet=-20001, opt=-1), '11403d924f409add1ada41716d4f08470550b496fa2d3252b01d04e3818a5fbc'),
        'crash_np': (dict(fnet=np.float64(-31000.0), opt=np.float64(-2.5)), 'e3b395d75c2c14e9fa047f0040f94412e70651408a0d8d70fd4f714b6cff0115'),
        'crash_dec': (dict(fnet=Decimal('-50000'), opt=Decimal('-3')), 'd1409c5ba83c2488366666bcab8f479e5ab51a2dd3f2753e792f7a24f8897844'),
        'crash_f32': (dict(fnet=np.float32(-32000), opt=np.float32(-7.0)), '91612259e640b8dda15aa2a4cda218d413f7a783a639c33cb884123ab511e311'),
        'opt_zero': (dict(fnet=-40000.0, opt=0.0), '7ade64f7255cdab05beaeac091aea6dba7e8f200a7af59fbe8c6a67b38fa539b'),
        'opt_pos': (dict(fnet=-40000.0, opt=5000.0), '5f86db873196832acbdab14b97cd101e9605c6945933c1a2a731f6192de36f73'),
        'opt_none_small': (dict(fnet=-25000.0, opt=None), '8f1e6db26c9e5ed10960998e71038da9d3d4c66c2cc8865b8042ffbec90fe4c0'),
    }

    @pytest.mark.parametrize('case', sorted(_BASE))
    def test_finite_unchanged(self, case, monkeypatch):
        kw, gold = self._BASE[case]
        assert _digest(_chips(_li_s(**kw), monkeypatch)) == gold

    def test_finite_still_alerts(self, monkeypatch):
        txt = _txt(_chips(_li_s(fnet=-25000.0, opt=-5000.0), monkeypatch))
        assert '期貨空25,000口 + 選擇權外資淨空-5,000千元' in txt


# ══════════════════════════════════════════════════════════════════════════
# 2. 訊號 3：外資／投信 非有限不列「外資投信同買／同賣」
# ══════════════════════════════════════════════════════════════════════════
_S3_FIN = {'buy': (60.0, 6.0), 'sell': (-150.0, -6.25)}


class TestSignal3NonFinite:
    @pytest.mark.parametrize('bad', sorted(_BAD))
    @pytest.mark.parametrize('side', sorted(_S3_FIN))
    @pytest.mark.parametrize('field', ['fo', 'tr'])
    def test_not_printed(self, field, side, bad, monkeypatch):
        fo, tr = _S3_FIN[side]
        kw = {'fo': fo, 'tr': tr, field: _BAD[bad]}
        txt = _txt(_chips(_li_s(fnet=-1000.0, **kw), monkeypatch))
        assert not _INFNAN.search(txt), txt          # 修前：「外資+inf億 + 投信+6.0億 同步買超」
        assert '同步買超' not in txt and '同步賣超' not in txt, txt

    @pytest.mark.parametrize('bad', sorted(_BAD))
    @pytest.mark.parametrize('side', sorted(_S3_FIN))
    @pytest.mark.parametrize('field', ['fo', 'tr'])
    def test_same_as_missing(self, field, side, bad, monkeypatch):
        fo, tr = _S3_FIN[side]
        base = {'fnet': -1000.0, 'fo': fo, 'tr': tr}
        got = _chips(_li_s(**{**base, field: _BAD[bad]}), monkeypatch)
        monkeypatch.undo()
        ref = _chips(_li_s(**{**base, field: None}), monkeypatch)
        assert _digest(_no_csv(got)) == _digest(_no_csv(ref))
        assert len(got) - len(_no_csv(got)) == 1

    #: 修前（基底 faa271e2）同一支 `_chips` 實跑的整段 §三 sha256（同買／同賣／門檻邊界／混向）
    _BASE = {
        'buy': (dict(fo=60.0, tr=6.0), 'd601928dd1d160a47e54c76000c5723b47b898e501e06e4a75cd8dec9bb1f855'),
        'buy_edge': (dict(fo=50.0, tr=5.0), '785b36fce80d5686e452eef7622ee7ecb8f514cd36a70c2add796940c15645bc'),
        'buy_e2': (dict(fo=50.5, tr=5.05), '9b6f9d4c61e03e83a16f3dd39a4bba8af939f88bdd38a1024817f3acfb758351'),
        'sell': (dict(fo=-150.0, tr=-6.25), 'efabbaf70f22c00594d3a4dfe17cd64dba2781f0afb16768b316e99a0a143d48'),
        'sell_edge': (dict(fo=-100.0, tr=-5.0), 'd7e78124af8c00794477b7743422b69c2596b885f24ebbf143e43114f188a558'),
        'sell_e2': (dict(fo=-100.4, tr=-5.01), '0b0a669bba742a720c6a87475b7041c31ee4999af2e74911fcd1980d9f11522a'),
        'np': (dict(fo=np.float64(77.7), tr=np.float32(8.0)), '1991e93df1be8d5857eb40449ecc1e39c64b5745053f9bfb9a6143cbb2b016ff'),
        'dec': (dict(fo=Decimal('-120'), tr=Decimal('-9.5')), '3ebf3d412acf41e425a30300e0fdc7adeb89b5215a8d953271c73c86807f560c'),
        'mixed': (dict(fo=60.0, tr=-6.0), '55d1ba380aeff974ccd762fe9f5d50a89ffaffd6d027d33da8bb65e4e5c8d2e6'),
        'int': (dict(fo=51, tr=6), 'cdb3ee34054123ed7c6338980356d52f600f70c088194488441f0659f295c51e'),
    }

    @pytest.mark.parametrize('case', sorted(_BASE))
    def test_finite_unchanged(self, case, monkeypatch):
        kw, gold = self._BASE[case]
        assert _digest(_chips(_li_s(fnet=-1000.0, **kw), monkeypatch)) == gold

    def test_finite_still_alerts(self, monkeypatch):
        txt = _txt(_chips(_li_s(fnet=-1000.0, fo=-150.0, tr=-6.25), monkeypatch))
        assert '外資-150億 + 投信-6.2億 同步賣超' in txt


# ══════════════════════════════════════════════════════════════════════════
# 3. L1 render_leading_table：int 欄數字字串不崩、與同欄有限 float 逐字一致
# ══════════════════════════════════════════════════════════════════════════
_INT_COLS = ['外資大小', '前五大留倉', '前十大留倉', '外(選)', '未平倉口數']
_FIN = {'外資': 12.3, '投信': -1.5, '自營': 0.0, '外資大小': -40000.0, '融資餘額': 3400.4,
        '融券餘額': 99.5, '前五大留倉': 6789, '前十大留倉': -20000, '選PCR': 79.95,
        '外(選)': 15000.0, '未平倉口數': 123456, '韭菜指數': -12.5}
#: (數字字串, 同值有限 float)
_NUMSTR = [('12.5', 12.5), ('-0.25', -0.25), ('1e3', 1000.0), ('-12.5', -12.5), ('0.5', 0.5),
           ('-1e3', -1000.0), ('1E3', 1000.0), (' 7.9 ', 7.9), ('1234567.9', 1234567.9)]
_FLOAT_SERIES = [12.5, -0.25, 1000.0, -12.5, 0.5, -1000.0, 1234567.9]


def _row_df(**cells):
    return pd.DataFrame({'日期': ['2026-10-01'], '成交量': ['3000億'],
                         **{c: pd.Series([cells.get(c)], dtype=object) for c in _COLS}})


def _multi_df(vals):
    n = len(vals)
    return pd.DataFrame({'日期': [f'2026-10-0{i + 1}' for i in range(n)], '成交量': ['3000億'] * n,
                         **{c: pd.Series(vals if c in _INT_COLS else [_FIN[c]] * n, dtype=object)
                            for c in _COLS}})


class TestLeadingTableNumericString:
    @pytest.mark.parametrize('s,f', _NUMSTR, ids=[s.strip() for s, _ in _NUMSTR])
    @pytest.mark.parametrize('col', _INT_COLS)
    def test_same_as_float(self, col, s, f):
        """數字字串 ⇒ 與同欄同值有限 float 同一張表（含顏色）；修前 int('12.5') → ValueError 整表不渲染。"""
        got = render_leading_table(_row_df(**{**_FIN, col: s}))
        ref = render_leading_table(_row_df(**{**_FIN, col: f}))
        assert got == ref

    def test_expected_cells(self):
        """基底對有限 float 的既有輸出（實跑抄錄）：截尾取整、BRACKET 加箭頭括號，未平倉口數純數字。"""
        exp = {'外資大小': ['▲ 12', '0', '▲ 1,000', '▼ (12)', '0', '▼ (1,000)', '▲ 1,234,567'],
               '未平倉口數': ['12', '0', '1,000', '-12', '0', '-1,000', '1,234,567']}
        strs = ['12.5', '-0.25', '1e3', '-12.5', '0.5', '-1e3', '1234567.9']
        for col, cells in exp.items():
            for s, want in zip(strs, cells):
                got = _cells(render_leading_table(_row_df(**{**_FIN, col: s})))[2 + _COLS.index(col)]
                assert got == want, (col, s, got)

    def test_float_table_unchanged(self):
        """修前（基底 faa271e2）int 五欄餵有限 float 的整張 HTML sha256；改成對應數字字串後同一雜湊。"""
        gold = '731edfa3bc24f5fd8c5b42b1b12994085a076e00edef52d79e5e194ef0a1f9b8'
        assert hashlib.sha256(render_leading_table(_multi_df(_FLOAT_SERIES)).encode()).hexdigest() == gold
        strs = ['12.5', '-0.25', '1e3', '-12.5', '0.5', '-1e3', '1234567.9']
        assert hashlib.sha256(render_leading_table(_multi_df(strs)).encode()).hexdigest() == gold

    @pytest.mark.parametrize('s', ['1e400', '-1e400', 'inf', 'nan', '1' * 400])
    def test_non_finite_string_still_dash(self, s):
        cells = _cells(render_leading_table(_row_df(**{c: s for c in _COLS})))
        assert cells[2:] == ['-'] * len(_COLS), cells
