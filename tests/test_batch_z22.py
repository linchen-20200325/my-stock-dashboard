"""批 Z22（防禦補強）—— v4 否決 PCR 缺值不填 100 ＋ 籌碼綜合判斷非有限不計分 ＋ 先行指標表 Decimal／float32 inf 不崩
（基底 `wip/batch-z21` `6d787aef`）。

- §三 `section_chips.read_v4_macro_veto`：原 `float(_row.get('選PCR') or 100)` ＋ 預設 `_pcr = 100.0` 把缺欄／None／0
  捏成 100、NaN／±inf 照傳入引擎、pd.NA 讓 `or` 拋「boolean value of NA is ambiguous」（被 except 印 log）
  ⇒ 改走既有 `_finite_yoy`，缺／非有限 → `None`。引擎 `check_macro_veto` 不讀 pcr ⇒ 燈號／msg 不變；
  回傳的 `_pcr` 無任何畫面讀者（僅供揭露依據）。有限值 → 與修前同一個 float。
- §三「籌碼綜合判斷」外資大小／韭菜指數／前五大留倉／外(選)：`safe_get` 只擋 None／NaN，±inf 照印並計分
  ⇒ 比照同區 PCR（批 Z21）走 `_finite_yoy`，非有限落入各欄既有「無此項不列、不計分」分支；有限值逐字不變。
- L1 `leading_indicators.render_leading_table`：`fmt` 原只認 `float` 子類，Decimal('Infinity'／'NaN')、物件欄
  np.float32(±inf) 仍拋 OverflowError／ValueError ⇒ 走既有「-」；`sty` 對 ±inf 原照套紅綠色 ⇒ 與 NaN 一致無色。

golden：有限值的修前輸出於基底 `6d787aef` 以本檔同一支 harness 實跑後寫死 sha256（⛔ 不由現行碼反推）。
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

import src.ui.tabs.macro.section_chips as SC
from src.data.macro.leading_indicators import render_leading_table
from tests.test_batch_z10 import _chips, _digest, _li
from tests.test_batch_z21 import _COLS, _cells, _summary, _txt, _veto_digest
from tests.test_batch_z28 import use_pre_qz7_scope, use_pre_z28_v4
from tests.test_m2n2_no_zero_fill import _FakeST


# ══════════════════════════════════════════════════════════════════════════
# 1. read_v4_macro_veto：PCR 缺值不填 100
# ══════════════════════════════════════════════════════════════════════════
def _veto_pcr(pcr, fut, mp, *, li=None):
    li = _li([fut], pcr) if li is None else li
    mp.setattr(SC, 'st', _FakeST({'macro_info': {'vix': {'current': 15.0}}, 'li_latest': li}))
    return SC.read_v4_macro_veto()


_PCR_BAD = {
    'pinf': lambda: [math.inf],
    'ninf': lambda: [-math.inf],
    'nan': lambda: [math.nan],
    'np_inf': lambda: [np.float64(np.inf)],
    'none': lambda: pd.Series([None], dtype=object),
    'pdna_obj': lambda: pd.array([pd.NA], dtype=object),
    'pdna_f64': lambda: pd.array([pd.NA], dtype='Float64'),
    'dec_inf': lambda: pd.Series([Decimal('Infinity')], dtype=object),
    'f32_ninf': lambda: pd.Series([np.float32(-np.inf)], dtype=object),
}


def _drop_pcr(r):
    return {k: v for k, v in r.items() if k != '_pcr'}


class TestVetoPcrMissing:
    @pytest.mark.parametrize('case', sorted(_PCR_BAD))
    @pytest.mark.parametrize('fut', [-40000.0, 5000.0])
    def test_bad_pcr_is_none_not_100(self, case, fut, monkeypatch, capsys):
        r = _veto_pcr(_PCR_BAD[case](), fut, monkeypatch)
        assert r['_pcr'] is None                         # 修前：100.0（或 nan／inf）
        assert 'ambiguous' not in capsys.readouterr().out
        monkeypatch.undo()
        ref = _veto_pcr([110.0], fut, monkeypatch)
        assert _drop_pcr(r) == _drop_pcr(ref)            # 燈號／msg／_vix／_futures 與有限 PCR 時相同

    @pytest.mark.parametrize('fut', [-40000.0, 5000.0])
    def test_missing_column_is_none(self, fut, monkeypatch):
        r = _veto_pcr(None, fut, monkeypatch)            # 無「選PCR」欄（修前 100.0）
        assert r['_pcr'] is None
        assert r['status'] == ('🔴 紅燈' if fut < 0 else '🟢 綠燈')

    def test_no_li_is_none(self, monkeypatch):
        monkeypatch.setattr(SC, 'st', _FakeST({'macro_info': {'vix': {'current': 15.0}}}))
        r = SC.read_v4_macro_veto()
        assert r['_pcr'] is None and r['status'] == '⬜ 無法判定'

    def test_zero_pcr_kept_not_100(self, monkeypatch):
        """有限 0 是值，不是缺值（修前 `0 or 100` → 100）。"""
        assert _veto_pcr([0.0], 5000.0, monkeypatch)['_pcr'] == 0.0

    #: 修前（基底 6d787aef）同一支 harness 實跑的回傳 sha256
    _BASE = {
        (110.0, -40000.0): '67ab5a744ee8d7562930a395aca76eea080344f36d0bf05a40d60611d8d13e52',
        (110.0, 5000.0): '6a80fcd8fc33edcdd3d7ebd990f6467121607b6fc70ced44440b572d19393dc7',
        (79.95, -40000.0): '3b6b2f8e9e3fca3f01907af61812c4506620839eac458e30930b22093212be8a',
        (79.95, 5000.0): '54d392e313a8b4fcb54bbd1c1e19e96feb767d6211b46688ba5fd0c15dd5107d',
        (150.55, -40000.0): 'e78b4fbb2d0daed40c38a60b43908fb3cc48de99a93ab350ce0e6c9189aa2c4c',
        (150.55, 5000.0): 'b1a21746de2e80c7f86ec12fb336cdcf13e1074d8335e6558d38fbd8f4d35703',
        (np.float64(130.0), -40000.0): '249353b88d8a426c2548409bbd281da6c596e2c53129a89401db0e7c7419179d',
        (np.float64(130.0), 5000.0): 'c6ffb542bfee24159e1f3674cc5fb0f9171761c5df58f1d0ba2a1e9c892f70be',
        (100.0, -40000.0): '532db344110e46779292cf5a280f4b060a6d4bb10c16b53bbad679fd177f0fd7',
        (100.0, 5000.0): 'dbfcba254958b88793c647bb6677c5917f5db7bbb1d07a72f2a84f4bcc4b5565',
        (1e-3, -40000.0): '006d739b2dfd4b353db03ccf05ca5e924e8b45bf4c2076470bbba931c52d3604',
        (1e-3, 5000.0): '6217894430604058458cbcd51a69b2f66b585ae894a2924135abf6271e11c21b',
        (-5.0, -40000.0): '06c5c226a0428180c3225e09c316616dcd23d13d1001102513f7beeaca2762b6',
        (-5.0, 5000.0): '6d9e972fa5cfda700fe5ad78462ac018896fb6087c72398f7a54977da5b7ef5d',
    }

    @pytest.mark.parametrize('pcr,fut', sorted(_BASE, key=repr), ids=repr)
    def test_finite_unchanged(self, pcr, fut, monkeypatch):
        r = _veto_pcr([pcr], fut, monkeypatch)
        assert _veto_digest(r) == self._BASE[(pcr, fut)]
        assert r['_pcr'] == float(pcr)


# ══════════════════════════════════════════════════════════════════════════
# 2. 籌碼綜合判斷：外資大小／韭菜指數／前五大／外選 非有限不印、不計分
# ══════════════════════════════════════════════════════════════════════════
_FIELD = {'fnet': '外資大小', 'leek': '韭菜指數', 'top5': '前五大留倉', 'opt': '外(選)'}


def _li4(fnet=-20000.0, leek=12.34, top5=-12000.0, opt=15000.0, pcr=110.0):
    return pd.DataFrame({'日期': ['2026-10-01'], '外資大小': pd.Series([fnet], dtype=object),
                         '選PCR': pd.Series([pcr], dtype=object), '韭菜指數': pd.Series([leek], dtype=object),
                         '前五大留倉': pd.Series([top5], dtype=object), '外(選)': pd.Series([opt], dtype=object)})


_BAD = {'pinf': math.inf, 'ninf': -math.inf, 'np_inf': np.float64(np.inf),
        'f32_ninf': np.float32(-np.inf), 'nan': math.nan}

#: 各欄既有計分字句（修前即存在）的開頭片段：該欄缺值時一個都不得出現
_FIELD_MARK = {'fnet': ('期貨空單', '期貨淨空', '期貨淨多'), 'leek': ('韭菜指數',),
               'top5': ('前五大',), 'opt': ('外選',)}


class TestSummaryNonFinite:
    @pytest.mark.parametrize('bad', sorted(_BAD))
    @pytest.mark.parametrize('field', sorted(_FIELD))
    def test_not_printed_not_scored(self, field, bad, monkeypatch):
        s = _summary(_chips(_li4(**{field: _BAD[bad]}), monkeypatch))
        assert not re.search(r'inf|nan', s, re.I), s     # 修前：「期貨淨多 +inf口」「韭菜指數inf%」…
        # 📌 批 Z31（Q-z11，客戶 2026-10-10 核准，有意識的更正，⛔ 不是漏改）：缺項改列同頁既有格式「📌 ○○ 未取得」
        #   （由 test_batch_z31 斷言）⇒ 該欄的計分字句仍一個都不得出現，但先扣掉這個缺值標記再檢查（標記本身含欄名）。
        _tag = {'fnet': '📌 外資期貨 未取得', 'leek': '📌 韭菜指數 未取得', 'top5': '📌 前五大 未取得',
                'opt': '📌 外選 未取得'}[field]
        assert _tag in s, s
        assert not any(m in s.replace(_tag, '') for m in _FIELD_MARK[field]), s
        monkeypatch.undo()
        ref = _summary(_chips(_li4(**{field: None}), monkeypatch))
        assert s == ref                                  # 與「無此項」同一張卡（含總分→結論）

    #: 修前（基底 6d787aef）同一支 `_chips` 實跑的整段 §三 sha256
    _BASE = {
        'base': ({}, 'f05a7894872d0a17c341e9a7ab8d72b2e12ff22998a4e2805e52b9fc34d97ff7'),
        'neg': (dict(fnet=-35000.0, leek=-8.0, top5=-15000.0, opt=-20000.0),
                '56bda6635776e2db311f9dd2e0f487e9842a3838fd995e24534489b62260ce86'),
        'pos': (dict(fnet=12000.0, leek=3.0, top5=500.0, opt=0.0),
                '5d4f27fbaf1d990167547f256fbbbdf312fd999e0e2e409507b95195d8de3f52'),
        'np': (dict(fnet=np.float64(-30000.0), leek=np.float64(10.0), top5=np.float64(0.0),
                    opt=np.float64(10000.0)),
               '730bcc78c9185a73da472ea2d2458175660b0778b2e9ee9ba7db5ff7efee013f'),
        'int': (dict(fnet=-1, leek=40, top5=-10001, opt=-10001),
                'c1d931bb1cda6f00d5e54fbf4e5ca26228534327bcf6643e520aadf0306f5358'),
    }

    #: 📌 批 Z28（Z19-n8，客戶 Q-z5＝A「剛好等於門檻判較差側」，有意識的更正，⛔ 不是漏改）：本例外資期貨剛好 −20,000 口，
    #:   v4 引擎風險燈由 🟡 改 🔴（預期改變，已由 test_batch_z28 斷言）。為保留本檔原 golden（本檔主題與 v4 等號無關），
    #:   本例改用 `use_pre_z28_v4`（恰一次還原 v4 兩個判式為 `<`）實跑；golden 一字未改。
    _Z28_V4_EDGE = {'base'}

    @pytest.mark.parametrize('case', sorted(_BASE))
    def test_finite_unchanged(self, case, monkeypatch):
        kw, gold = self._BASE[case]
        # 📌 批 Z28（客戶 Q-z7＝A，有意識的更正，⛔ 不是漏改）：§三 v4 卡範圍說明「空單超過 2 萬口…超過 1 萬口」改「達」，
        #   本段 golden 為修字前實跑；改用 `use_pre_qz7_scope`（只把該說明恰一次還原為修前字）保留原 digest，新字由 test_batch_z28 斷言。
        use_pre_qz7_scope(monkeypatch)
        if case in self._Z28_V4_EDGE:
            use_pre_z28_v4(monkeypatch)
        assert _digest(_chips(_li4(**kw), monkeypatch)) == gold


# ══════════════════════════════════════════════════════════════════════════
# 3. L1 render_leading_table：Decimal／float32 非有限不崩、顯示「-」、無色
# ══════════════════════════════════════════════════════════════════════════
_TBL_BAD = {'dec_inf': Decimal('Infinity'), 'dec_ninf': Decimal('-Infinity'), 'dec_nan': Decimal('NaN'),
            'f32_inf': np.float32(np.inf), 'f32_ninf': np.float32(-np.inf), 'f32_nan': np.float32(np.nan),
            'pinf': math.inf, 'ninf': -math.inf}


class TestLeadingTableDecimalF32:
    @pytest.mark.parametrize('bad', sorted(_TBL_BAD))
    def test_every_column_dash_no_colour(self, bad):
        df = pd.DataFrame({'日期': ['2026-10-01'], '成交量': ['3000億'],
                           **{c: pd.Series([_TBL_BAD[bad]], dtype=object) for c in _COLS}})
        html = render_leading_table(df)                 # 修前 Decimal／float32 inf → OverflowError／ValueError
        cells = _cells(html)
        assert len(cells) - 2 in (len(_COLS) - 2, len(_COLS)), cells
        assert set(cells[2:]) == {'-'}, cells
        body = html.split('<tbody>', 1)[1]
        assert 'color:' not in body.replace('color:#9CDCFE;', ''), body   # 成交量欄固定色除外

    def test_finite_decimal_f32_table_unchanged(self):
        """修前（基底 6d787aef）同一份 df 的整張 HTML sha256（Decimal／float32 有限值）。"""
        df = pd.DataFrame({'日期': ['2026-10-01', '2026-10-02'], '成交量': ['1億', '2億'],
            '外資': pd.Series([Decimal('12.3'), np.float32(-4.5)], dtype=object),
            '投信': pd.Series([np.float32(1.25), Decimal('-0.05')], dtype=object),
            '自營': pd.Series([Decimal('0'), np.float32(2.0)], dtype=object),
            '外資大小': pd.Series([Decimal('-40000'), np.float32(12000)], dtype=object),
            '融資餘額': pd.Series([Decimal('3400.4'), np.float32(2799.5)], dtype=object),
            '融券餘額': pd.Series([np.float32(100.0), Decimal('12')], dtype=object),
            '前五大留倉': pd.Series([np.float32(-12345), Decimal('6789')], dtype=object),
            '前十大留倉': pd.Series([Decimal('-20000'), np.float32(1)], dtype=object),
            '選PCR': pd.Series([Decimal('110.0'), np.float32(79.5)], dtype=object),
            '外(選)': pd.Series([np.float32(-15000), Decimal('20000')], dtype=object),
            '未平倉口數': pd.Series([Decimal('123456'), np.float32(-500)], dtype=object),
            '韭菜指數': pd.Series([np.float32(12.5), Decimal('-6.0')], dtype=object)})
        got = hashlib.sha256(render_leading_table(df).encode()).hexdigest()
        assert got == '5fe6185ef05b1c101ef2dfed4fd8cf066abe6b35d5b49ed28465bc8ea11782ad'
