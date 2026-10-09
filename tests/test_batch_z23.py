"""批 Z23（防禦補強）—— 進階警示非有限不印 ＋ 個股 v4 PCR 缺值不填 100 ＋ 先行指標表非數值不崩
（基底 `wip/batch-z22` `1b161d2f`）。

- §三「⚡ 進階警示」訊號 1／2：外資大小 -inf 原印「外資期貨空單 inf 口」（或「期貨空inf口 + …」）、
  韭菜指數 ±inf 原印「法人空多比 ±inf%」⇒ 比照同區訊號 4（PCR，批 Z21）走 `_finite_yoy`，
  非有限落入既有「不列警示」分支；有限值逐字不變。
- L5 `section_health_score`（個股健康度頁 v4 引擎輸入）：`_v4_pcr2 = 100.0` 與 `or 100` 把缺欄／None／0／
  先行指標未載入捏成 100、NaN／±inf 照傳 ⇒ 改走 `_finite_yoy`，缺／非有限 → None（同批 Z22 §三 v4 否決）。
  引擎 `V4StrategyEngine` 只讀 macro 的 vix／foreign_futures，全 repo 無 pcr 讀者 ⇒ 畫面零變化（本檔實跑證明）。
- L1 `leading_indicators.render_leading_table`：儲存格為字串「-」、tuple 時 `fmt` 的 int()／float() 拋例外、
  整張表不渲染；float() 轉不了的超大整數（≥2^1024）在走 float() 的 7 欄拋 OverflowError（BRACKET 四欄與
  「未平倉口數」走 int() 原不拋、印完整數字，修後改顯示「-」屬已知可接受差異）⇒ 無法轉成有限浮點數者走既有
  「-」；`sty` 原已不上色（實跑確認）。

golden：有限值的修前輸出於基底 `1b161d2f` 以本檔同一支 harness 實跑後寫死 sha256（⛔ 不由現行碼反推）。
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
from tests.test_batch_z17 import _health
from tests.test_batch_z21 import _COLS, _cells, _txt
from tests.test_batch_z28 import use_pre_qz7_scope, use_pre_z28_v4

_HUGE = 10 ** 400
#: 獨立字詞的 inf／nan（排除「YFinance」等既有字句）
_INFNAN = re.compile(r'(?<![A-Za-z])(inf|nan)(?![A-Za-z])', re.I)


# ══════════════════════════════════════════════════════════════════════════
# 1. §三 進階警示：外資大小／韭菜指數 非有限不印、不列警示
# ══════════════════════════════════════════════════════════════════════════
def _li_w(fnet=None, leek=None, opt=None):
    return pd.DataFrame({'日期': ['2026-10-01'], '外資大小': pd.Series([fnet], dtype=object),
                         '選PCR': pd.Series([110.0], dtype=object), '韭菜指數': pd.Series([leek], dtype=object),
                         '外(選)': pd.Series([opt], dtype=object)})


_W_BAD = {'pinf': math.inf, 'ninf': -math.inf, 'np_ninf': np.float64(-np.inf),
          'f32_ninf': np.float32(-np.inf), 'f32_pinf': np.float32(np.inf),
          'dec_ninf': Decimal('-Infinity'), 'nan': math.nan, 'none': None}

#: 訊號 1／2 既有警示字句（修前即存在）：該欄非有限時一個都不得出現
_W_MARK = {'fnet': ('期權同向崩盤警戒', '期貨大空警戒', '外資期貨空單', '期貨空'),
           'leek': ('韭菜極端', '法人空多比 ')}


def _no_csv(out):
    return [(k, t) for k, t in out if 'download="先行指標.csv"' not in t]


class TestAlertNonFinite:
    @pytest.mark.parametrize('bad', sorted(_W_BAD))
    @pytest.mark.parametrize('opt', [-5000.0, 5000.0, None])
    def test_fnet_not_printed(self, bad, opt, monkeypatch):
        txt = _txt(_chips(_li_w(fnet=_W_BAD[bad], opt=opt), monkeypatch))
        assert not _INFNAN.search(txt), txt  # 修前：「外資期貨空單 inf 口」「期貨空inf口 + …」
        assert not any(m in txt for m in _W_MARK['fnet']), txt

    @pytest.mark.parametrize('bad', sorted(_W_BAD))
    def test_leek_not_printed(self, bad, monkeypatch):
        txt = _txt(_chips(_li_w(fnet=-1000.0, leek=_W_BAD[bad]), monkeypatch))
        assert not _INFNAN.search(txt), txt  # 修前：「法人空多比 +inf%」
        assert not any(m in txt for m in _W_MARK['leek']), txt

    @pytest.mark.parametrize('bad', sorted(_W_BAD))
    @pytest.mark.parametrize('field', ['fnet', 'leek'])
    def test_same_as_missing(self, field, bad, monkeypatch):
        """非有限 ⇒ 與該欄 None（既有缺值路徑）同一段 §三 輸出。

        唯一例外是「⬇️ 下載先行指標 CSV」：它匯出原始值（inf 照實寫出、None 為空欄），屬原始資料、不在本批範圍。
        """
        base = dict(fnet=-40000.0, leek=40.0, opt=-5000.0)
        got = _chips(_li_w(**{**base, field: _W_BAD[bad]}), monkeypatch)
        monkeypatch.undo()
        ref = _chips(_li_w(**{**base, field: None}), monkeypatch)
        assert _digest(_no_csv(got)) == _digest(_no_csv(ref))
        assert len(got) - len(_no_csv(got)) == 1         # 只濾掉那一個下載鈕

    #: 修前（基底 1b161d2f）同一支 `_chips` 實跑的整段 §三 sha256（涵蓋訊號 1／2 每個分支與邊界）
    _BASE = {
        'crash': (dict(fnet=-25000.0, opt=-5000.0, leek=12.0), '7edde8e15e21c0201293764606bdac17f14aef051fb80817abc55fffb64ef109'),
        'big_short': (dict(fnet=-40000.0, opt=5000.0, leek=-12.0), '59ecd894d3562fffc35bdc626f9c2c94a7f4a7a11fed88920fc60f5fcf3383f1'),
        'big_short_no_opt': (dict(fnet=-40000.0, opt=None, leek=None), '949a5efab57a30b9e5b59e5369c4f61fb3ec04aa3b3ca818c510d946678ff689'),
        'edge_20000': (dict(fnet=-20000.0, opt=-5000.0, leek=30.0), '80bec79c0f9fc3208751d7e1d8873f1ac47c3347121c9b6bae822d87e1d2a8ca'),
        'edge_20001': (dict(fnet=-20001, opt=-1, leek=-30.0), '7b500bf8012fc869f3c1935a0fa12d593a5d34b3b75b39f41eb83e040d74c66b'),
        'leek_hi': (dict(fnet=1000.0, opt=None, leek=30.5), '37c231917635742ff27286f632e0033f7853de3d20340ffc82c3a3248b165405'),
        'leek_lo': (dict(fnet=None, opt=None, leek=-45.25), '427a42072b2f263651d9940dbc3fa5c50371e530807481c7f22655aa93227680'),
        'np': (dict(fnet=np.float64(-31000.0), opt=np.float64(-2.0), leek=np.float64(55.0)), 'b4af8756db2ec2ebcb1389b6f292f0be8b46e871fdc8ccb8525f9685818aee1b'),
        'dec': (dict(fnet=Decimal('-50000'), opt=Decimal('3'), leek=Decimal('-31.5')), '5336c3b4f0e63e683e52d832001393228c75628ce4355fff321d78d88a0af06b'),
        'f32': (dict(fnet=np.float32(-32000), opt=None, leek=np.float32(33.0)), '790bab9adc99af50a5d83fd6afc45b65f6cead2d8ea440ca7b3d07ce901309c7'),
    }

    #: 📌 批 Z28（Z19-n8，客戶 Q-z5＝A「剛好等於門檻判較差側」，有意識的更正，⛔ 不是漏改）：本例外資期貨剛好 −20,000 口，
    #:   v4 引擎風險燈由 🟡 改 🔴（預期改變，已由 test_batch_z28 斷言）。為保留本檔原 golden（本檔主題與 v4 等號無關），
    #:   本例改用 `use_pre_z28_v4`（恰一次還原 v4 兩個判式為 `<`）實跑；golden 一字未改。
    _Z28_V4_EDGE = {'edge_20000'}

    @pytest.mark.parametrize('case', sorted(_BASE))
    def test_finite_unchanged(self, case, monkeypatch):
        kw, gold = self._BASE[case]
        # 📌 批 Z28（客戶 Q-z7＝A，有意識的更正，⛔ 不是漏改）：§三 v4 卡範圍說明「空單超過 2 萬口…超過 1 萬口」改「達」，
        #   本段 golden 為修字前實跑；改用 `use_pre_qz7_scope`（只把該說明恰一次還原為修前字）保留原 digest，新字由 test_batch_z28 斷言。
        use_pre_qz7_scope(monkeypatch)
        if case in self._Z28_V4_EDGE:
            use_pre_z28_v4(monkeypatch)
        assert _digest(_chips(_li_w(**kw), monkeypatch)) == gold

    def test_finite_still_alerts(self, monkeypatch):
        txt = _txt(_chips(_li_w(fnet=-40000.0, opt=5000.0, leek=-45.25), monkeypatch))
        assert '外資期貨空單 40,000 口' in txt and '法人空多比 -45.2%' in txt


# ══════════════════════════════════════════════════════════════════════════
# 2. 個股健康度頁 v4 引擎輸入：PCR 缺值不填 100
# ══════════════════════════════════════════════════════════════════════════
_V4_PCR_BAD = {
    'li_none': None,
    'li_empty': pd.DataFrame(),
    'col_absent': pd.DataFrame({'外資大小': [-1000.0]}),
    'none': pd.DataFrame({'外資大小': [-1000.0], '選PCR': [None]}, dtype=object),
    'nan': pd.DataFrame({'外資大小': [-1000.0], '選PCR': [math.nan]}),
    'pinf': pd.DataFrame({'外資大小': [-1000.0], '選PCR': [math.inf]}),
    'ninf': pd.DataFrame({'外資大小': [-1000.0], '選PCR': [-math.inf]}),
    'pdna_obj': pd.DataFrame({'外資大小': [-1000.0], '選PCR': pd.array([pd.NA], dtype=object)}),
    'pdna_f64': pd.DataFrame({'外資大小': [-1000.0], '選PCR': pd.array([pd.NA], dtype='Float64')}),
    'dec_inf': pd.DataFrame({'外資大小': [-1000.0], '選PCR': pd.Series([Decimal('Infinity')], dtype=object)}),
    'f32_ninf': pd.DataFrame({'外資大小': [-1000.0], '選PCR': pd.Series([np.float32(-np.inf)], dtype=object)}),
    'huge': pd.DataFrame({'外資大小': [-1000.0], '選PCR': pd.Series([_HUGE], dtype=object)}),
}


class TestV4PcrMissing:
    @pytest.mark.parametrize('name', sorted(_V4_PCR_BAD))
    def test_missing_is_none_not_100(self, name, monkeypatch):
        _out, macro = _health(monkeypatch, _V4_PCR_BAD[name])
        assert macro['pcr'] is None                      # 修前：100.0（或 nan／±inf）
        assert macro['vix'] == 18.0

    @pytest.mark.parametrize('name', sorted(_V4_PCR_BAD))
    def test_screen_identical_to_pre_fix(self, name, monkeypatch):
        """引擎收到 None 或修前的 100.0，整頁輸出逐字相同（全 repo 無 pcr 讀者）。"""
        now, _ = _health(monkeypatch, _V4_PCR_BAD[name])
        old, m_old = _health(monkeypatch, _V4_PCR_BAD[name], force={'pcr': 100.0})
        assert m_old['pcr'] == 100.0
        assert now == old

    def test_zero_kept_not_100(self, monkeypatch):
        """有限 0 是值，不是缺值（修前 `0 or 100` → 100）。"""
        _out, macro = _health(monkeypatch, pd.DataFrame({'外資大小': [-1000.0], '選PCR': [0.0]}))
        assert macro['pcr'] == 0.0

    #: 修前（基底 1b161d2f）同一支 `_health` 實跑的整頁輸出 sha256
    _BASE = dict.fromkeys([110.0, 79.95, 150.55, 100.0, -5.0],
                          '82d50217995a346f567d569ee0734e2f83a9111ff7c9cd36e1cc035d10407863')  # 五值同頁：本頁不顯示 pcr

    @pytest.mark.parametrize('pcr', sorted(_BASE))
    def test_finite_unchanged(self, pcr, monkeypatch):
        out, macro = _health(monkeypatch, pd.DataFrame({'外資大小': [-1000.0], '選PCR': [pcr]}))
        assert macro['pcr'] == float(pcr) and isinstance(macro['pcr'], float)
        assert _digest(out) == self._BASE[pcr]


# ══════════════════════════════════════════════════════════════════════════
# 3. L1 render_leading_table：字串「-」／tuple／超大整數 不崩、顯示「-」、無色
# ══════════════════════════════════════════════════════════════════════════
_TBL_ODD = {'dash': '-', 'word': 'abc', 'empty_str': '', 'tuple1': (5,), 'tuple2': (1, 2),
            'huge': _HUGE, 'neg_huge': -_HUGE}


def _row_df(**cells):
    return pd.DataFrame({'日期': ['2026-10-01'], '成交量': ['3000億'],
                         **{c: pd.Series([cells.get(c)], dtype=object) for c in _COLS}})


class TestLeadingTableNonNumeric:
    @pytest.mark.parametrize('odd', sorted(_TBL_ODD))
    def test_every_column_dash_no_colour(self, odd):
        df = _row_df(**{c: _TBL_ODD[odd] for c in _COLS})
        html = render_leading_table(df)                 # 修前 int('-') → ValueError；float(10**400) → OverflowError（int 欄則印完整數字）
        cells = _cells(html)
        assert len(cells) == len(_COLS) + 2, cells
        assert cells[2:] == ['-'] * len(_COLS), cells
        body = html.split('<tbody>', 1)[1]
        assert 'color:' not in body.replace('color:#9CDCFE;', ''), body   # 成交量欄固定色除外

    @pytest.mark.parametrize('odd', sorted(_TBL_ODD))
    @pytest.mark.parametrize('col', ['外資', '外資大小', '選PCR', '未平倉口數', '韭菜指數'])
    def test_same_as_none_cell(self, col, odd):
        """單一儲存格異常 ⇒ 與該格 None（既有「-」、無色）同一張表，其餘有限值逐字不變。"""
        fin = {'外資': 12.3, '投信': -1.5, '自營': 0.0, '外資大小': -40000.0, '融資餘額': 3400.4,
               '融券餘額': 99.5, '前五大留倉': 6789, '前十大留倉': -20000, '選PCR': 79.95,
               '外(選)': 15000.0, '未平倉口數': 123456, '韭菜指數': -12.5}
        got = render_leading_table(_row_df(**{**fin, col: _TBL_ODD[odd]}))
        ref = render_leading_table(_row_df(**{**fin, col: None}))
        assert got == ref

    def test_finite_odd_types_table_unchanged(self):
        """修前（基底 1b161d2f）同一份 df 的整張 HTML sha256：數字字串／大整數／bool 等可轉有限浮點數者不變。"""
        df = pd.DataFrame({'日期': ['2026-10-01', '2026-10-02'], '成交量': ['1億', '2億'],
            '外資': pd.Series(['12.5', 3], dtype=object),
            '投信': pd.Series([True, '-0.25'], dtype=object),
            '自營': pd.Series([np.int64(7), '0'], dtype=object),
            '外資大小': pd.Series(['-40000', 10 ** 20], dtype=object),
            '融資餘額': pd.Series(['3400.4', 2 ** 63], dtype=object),
            '融券餘額': pd.Series([np.uint64(100), '12'], dtype=object),
            '前五大留倉': pd.Series([-(10 ** 18), '6789'], dtype=object),
            '前十大留倉': pd.Series([False, np.int32(-5)], dtype=object),
            '選PCR': pd.Series(['110', 1e308], dtype=object),
            '外(選)': pd.Series(['0', -(2 ** 70)], dtype=object),
            '未平倉口數': pd.Series(['123456', 10 ** 25], dtype=object),
            '韭菜指數': pd.Series(['-6.0', 5e-324], dtype=object)})
        got = hashlib.sha256(render_leading_table(df).encode()).hexdigest()
        assert got == '780eebce29f59431d8fd21fa286e00a41eba85e4adb508daf4dc82d71d0b0e74'
