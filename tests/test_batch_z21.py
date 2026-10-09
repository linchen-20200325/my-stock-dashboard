"""批 Z21（防禦補強）—— Z7-n4-f1 ＋ PCR 非有限不計分 ＋ 先行指標表 pd.NA 不崩（基底 `wip/batch-z20` `f7a969d0`）。

- Z7-n4-f1（L5 `section_chips.read_v4_macro_veto`）：`vix_value_or_none` 帶 `upper=VIX_FETCH_MAX`（與 L1
  `fetch_vix_block` 同一上限）⇒ session 繞過 L1 直接寫入 > 100（150、1e300、100.0001）時視同取數失敗，
  走既有「VIX 未取得 → 無法判定」：§三 v4 卡不判 🔴、§八 跨區揭露框不再印「看的是 VIX=1000…」。
  恰 100 與 (0, 100) 有效值輸出與修前逐字相同。
  ⚠️ §八 `section_mid` 自己的結論段「❌ VIX 數值異常（{:.0f}）」**本批未動**：它是既有設計（批 Z7 C7-n7，
  `test_v1_vix_nonfinite.test_vix_over_100_still_api_error` 釘「VIX 數值異常（150）」），套上限會讓該分支變死碼。
- PCR（`section_chips` §三「進階警示」訊號 4、「籌碼綜合判斷」）：±inf 原印「PCR=inf／-inf」並列警示／計分
  ⇒ 非有限走既有「無 PCR 不列／不計」分支；有限值逐字不變。
- L1 `leading_indicators.render_leading_table` 的 `fmt`：pd.NA 原拋 TypeError、±inf 拋 OverflowError 或印「inf」
  ⇒ 非有限值走既有缺值顯示「-」；有限值表格逐字不變。

golden：有限值的修前輸出於基底 `f7a969d0` 以本檔同一支 harness 實跑後寫死 sha256（⛔ 不由現行碼反推）。
本檔所有斷言皆為實跑行為斷言，不讀原始碼字面。
"""
from __future__ import annotations

import hashlib
import math
import re
import types

import numpy as np
import pandas as pd
import pytest

import src.services.allocation_service as AS
import src.ui.tabs.macro.section_chips as SC
from src.data.macro.leading_indicators import render_leading_table
from tests.test_batch_z10 import _chips, _digest, _li
from tests.test_batch_z28 import use_pre_qz7_scope, use_pre_z28_v4
from tests.test_m2n2_no_zero_fill import _FakeST, _mod

_GIANT = re.compile(r'\d{20,}')


def _txt(out) -> str:
    return re.sub(r'<[^>]+>', '', '\x1e'.join(t for _k, t in out))


# ══════════════════════════════════════════════════════════════════════════
# Z7-n4-f1：§三 read_v4_macro_veto 第二道防線（VIX > 100 視同取數失敗）
# ══════════════════════════════════════════════════════════════════════════
def _veto(vix, fut, mp):
    mp.setattr(SC, 'st', _FakeST({'macro_info': {'vix': {'current': vix}}, 'li_latest': _li([fut], [110.0])}))
    return SC.read_v4_macro_veto()


def _veto_digest(r):
    return hashlib.sha256(repr(sorted(r.items())).encode()).hexdigest()


_OVER = [150.0, 1e300, 100.0001, np.float64(150.0), 10 ** 6]


class TestZ7n4f1VetoUpper:
    @pytest.mark.parametrize('vix', _OVER, ids=['150', '1e300', '100.0001', 'np150', 'int1e6'])
    @pytest.mark.parametrize('fut', [-40000.0, 5000.0])
    def test_over_100_is_missing(self, vix, fut, monkeypatch):
        assert _veto(vix, fut, monkeypatch) is None      # 修前：dict（-40000 時 🔴）

    #: 修前（基底 f7a969d0）同一支 `_veto` 實跑的回傳 sha256（含 status／msg／_vix…）
    _BASE = {
        (100.0, -40000.0): '491af029ed2527fa548b73d61836e4c6b78753cdb623d8bcdfb0247ec16bb1f2',
        (100.0, 5000.0): '393f2d9b7a36826ed1143453af5dd9e0f287d60b54836b78db1cb55a0401f6a1',
        (99.99, -40000.0): '2aad8b26c024193e0835177749ac1c640ea6e649e984bb92f0994806e74bca10',
        (99.99, 5000.0): 'dacede1a4be615065731719184980e2544be06a8297de34f9558e35074e9211a',
        (15.0, -40000.0): '67ab5a744ee8d7562930a395aca76eea080344f36d0bf05a40d60611d8d13e52',
        (15.0, 5000.0): '6a80fcd8fc33edcdd3d7ebd990f6467121607b6fc70ced44440b572d19393dc7',
        (0.5, -40000.0): 'f687459f6fc4b5791cb9e2341fc1cd8ec9980b0ae7e78914c3458adb96cfc738',
        (0.5, 5000.0): '15ac0b2321b9d8df2eceef4c4e3506ee91dbac6be5105ff0d8a1a9315c619c66',
        (30.0, -40000.0): '0450c3b1d7e04523cc6dbc41b6da2e071bcb31584944c024c6b2d3aeb54f2963',
        (30.0, 5000.0): 'bff2e6aa82277658b4e880555cf83177bdbd33e58501ac289d682474581cc54d',
        (np.float64(45.2), -40000.0): '83888387d982256203a7b8275b14ebf1d3b53405af9ab51ba6fa86291572affc',
        (np.float64(45.2), 5000.0): 'da6737e552c4b577b7bfdfe3b2510041149f4521c38d7fabc803737a4f922ac2',
        (100, -40000.0): '491af029ed2527fa548b73d61836e4c6b78753cdb623d8bcdfb0247ec16bb1f2',
        (100, 5000.0): '393f2d9b7a36826ed1143453af5dd9e0f287d60b54836b78db1cb55a0401f6a1',
    }

    @pytest.mark.parametrize('vix,fut', sorted(_BASE, key=repr), ids=repr)
    def test_valid_unchanged(self, vix, fut, monkeypatch):
        r = _veto(vix, fut, monkeypatch)
        assert _veto_digest(r) == self._BASE[(vix, fut)]
        assert r['_vix'] == float(vix)

    def test_100_still_red_with_heavy_short(self, monkeypatch):
        """恰 100 仍有效（上限是 > 100）：重空單照判 🔴。"""
        assert _veto(100.0, -40000.0, monkeypatch)['status'].startswith('🔴')

    @pytest.mark.parametrize('vix', [150.0, 1e300], ids=['150', '1e300'])
    def test_chips_v4_card_unknown_not_red(self, vix, monkeypatch):
        """§三 v4 卡：走既有「⬜ 無法判定…VIX 未取得」卡，不判 🔴、不印巨大數字。"""
        fake = _FakeST({'macro_info': {'vix': {'current': vix}}, 'li_latest': _li([-40000.0], [110.0])})
        monkeypatch.setattr(SC, 'st', fake)
        monkeypatch.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(
            is_loaded=False, range_text='', capped=False, cap_text='', final_hi=None))
        monkeypatch.setattr(AS, 'get_allocation_sleeves', lambda *a, **k: None)
        SC.render_section_chips({}, None, {})
        txt = _txt(fake.out)
        assert 'VIX 未取得，' in txt and '⬜ 無法判定' in txt
        assert not _GIANT.search(txt)


_MID_BASE = {"ism_pmi": {"value": 52.0}, "us_core_cpi": {"yoy": 3.0},
             "tw_export": {"yoy": 5.0, "date": "2026-08"}, "ndc_signal": {"score": 27}}


def _mid(vix, mp, fut=-40000.0):
    """實跑 §八（**不** stub `read_v4_macro_veto`，§三 入口真的讀同一份 session）。"""
    info = dict(_MID_BASE)
    info['vix'] = {'current': vix}
    mod = _mod('mid')
    fake = _FakeST({'macro_info': info, 'bias_info': {'bias_240': 5.0}, 'li_latest': _li([fut], [110.0])})
    mp.setattr(mod, 'st', fake)
    mp.setattr(SC, 'st', fake)
    mp.setattr(AS, 'apply_vix_veto', lambda *a, **k: None)
    mp.setattr(AS, 'apply_ring_gate', lambda *a, **k: None)
    mp.setattr(AS, 'register_conflict', lambda *a, **k: None)
    mp.setattr(AS, 'get_allocation', lambda *a, **k: types.SimpleNamespace(
        is_loaded=False, final_hi=None, range_text='', capped=False, cap_text=''))
    mod.render_section_mid(False, {}, {}, {})
    return fake.out


class TestZ7n4f1SectionMidCrossBox:
    @pytest.mark.parametrize('vix', [150.0, 1e300, 100.0001], ids=['150', '1e300', '100.0001'])
    def test_cross_box_takes_missing_caption(self, vix, monkeypatch):
        out = _mid(vix, monkeypatch)
        txt = _txt(out)
        assert '看的是 VIX=' not in txt                  # 修前：「🔴 紅燈　看的是 VIX=150.0／1000…0.0」
        assert '因 VIX 未取得而無法判定' in txt           # 既有缺值句
        # 跨區揭露框不得印巨大數字（§八 結論段「VIX 數值異常（…）」為既有設計、本批未動，排除）
        assert not any(_GIANT.search(t) for _k, t in out if 'VIX 數值異常' not in t)

    #: 修前（基底 f7a969d0）同一支 `_mid` 實跑的整段 §八 sha256
    _BASE = {
        100.0: '351586fe2e8ff56107fe8673b09a1ba09aea6f184f9e93182912270368a02ba5',
        35.0: '6e6247773c86672f5fa4f387d225e72cab1187a35fa827738e27ba7bcd199ff9',
        15.0: '26bd08f7f41e488d7e63b42674f81fc771259b11924479bd7efab69b20428f98',
    }

    @pytest.mark.parametrize('vix', sorted(_BASE))
    def test_valid_unchanged(self, vix, monkeypatch):
        assert _digest(_mid(vix, monkeypatch)) == self._BASE[vix]

    def test_valid_cross_box_still_shows_vix(self, monkeypatch):
        """有效 VIX＋重空單：§三 判 🔴、本區無觸發 ⇒ 揭露框照舊列 §三 看的 VIX（既有字句）。"""
        assert '🔴 紅燈　看的是 VIX=15.0、外資期貨=-40,000 口' in _txt(_mid(15.0, monkeypatch))


# ══════════════════════════════════════════════════════════════════════════
# PCR 非有限：不印 inf／nan、不計分
# ══════════════════════════════════════════════════════════════════════════
_PCR_BAD = {
    'pinf': lambda: [math.inf],
    'ninf': lambda: [-math.inf],
    'nan': lambda: [math.nan],
    'none': lambda: pd.Series([None], dtype=object),
    'pdna_obj': lambda: pd.array([pd.NA], dtype=object),
    'pdna_f64': lambda: pd.array([pd.NA], dtype='Float64'),
    'np_inf': lambda: [np.float64(np.inf)],
}


def _summary(out) -> str:
    hits = [re.sub(r'<[^>]+>', '', t) for _k, t in out if '籌碼綜合判斷</div>' in t]
    assert len(hits) == 1, hits
    return hits[0]


class TestPcrNonFinite:
    @pytest.mark.parametrize('case', sorted(_PCR_BAD))
    @pytest.mark.parametrize('fut', [-20000.0, 12000.0])
    def test_no_pcr_text_no_score(self, case, fut, monkeypatch):
        out = _chips(_li([fut], _PCR_BAD[case]()), monkeypatch)
        txt = _txt(out)
        assert not re.search(r'PCR=\s*[-+]?(inf|nan)', txt, re.I), txt
        assert 'PCR=' not in txt
        assert '選擇權Put/Call' not in txt                 # 進階警示訊號 4 不列
        monkeypatch.undo()
        ref = _chips(_li([fut], pd.Series([None], dtype=object)), monkeypatch)
        assert _summary(out) == _summary(ref)              # 綜合判斷＝「無 PCR」時同一張卡（不計分）

    #: 修前（基底 f7a969d0）同一支 `_chips` 實跑的整段 §三 sha256（補 Z20 golden 未覆蓋的 >150／>130／=80 邊界）
    _BASE = {
        150.5: 'eaa03a33a7716efa0fdefa190fdaafbf91cb8b7366e0e6538e06cd4401440b4a',
        131.0: '2d81505847c281d0580fb5072fa14463abeef6e0d1ab3213262afa13e951da26',
        80.0: 'e27b2af515928e4bb7e58d173f2b80063be3569fc2f02906e5b2b0ddbb0aa928',
        79.99: '62050774cdf28a7f35a3437a6cb0d4c56332e2229bdf35b6575894935a15774f',
        100.0: '08faa1bd135207ce598b599c33f8e2c7bbba1c764c1cd01fc337fe2e43e09354',
    }

    @pytest.mark.parametrize('pcr', sorted(_BASE))
    def test_finite_unchanged(self, pcr, monkeypatch):
        # 📌 批 Z28（Z19-n8，客戶 Q-z5＝A「剛好等於門檻判較差側」，有意識的更正，⛔ 不是漏改）：本例外資期貨剛好 −20,000 口，
        #   v4 引擎風險燈由 🟡 改 🔴（預期改變，已由 test_batch_z28 斷言）。為保留本檔原 golden（本檔主題與 v4 等號無關），
        #   本例改用 `use_pre_z28_v4`（恰一次還原 v4 兩個判式為 `<`）實跑；golden 一字未改。
        use_pre_z28_v4(monkeypatch)
        # 📌 批 Z28（客戶 Q-z7＝A，有意識的更正，⛔ 不是漏改）：§三 v4 卡範圍說明「空單超過 2 萬口…超過 1 萬口」改「達」，
        #   本段 golden 為修字前實跑；改用 `use_pre_qz7_scope`（只把該說明恰一次還原為修前字）保留原 digest，新字由 test_batch_z28 斷言。
        use_pre_qz7_scope(monkeypatch)
        assert _digest(_chips(_li([-20000.0], [pcr]), monkeypatch)) == self._BASE[pcr]

    def test_finite_still_scored(self, monkeypatch):
        txt = _txt(_chips(_li([-20000.0], [150.5]), monkeypatch))
        assert 'PCR=150.5（>150偏多，市場過度悲觀）' in txt and '🟢 PCR=150（>130強支撐）' in txt


# ══════════════════════════════════════════════════════════════════════════
# L1 render_leading_table：pd.NA／±inf 不崩，走既有「-」
# ══════════════════════════════════════════════════════════════════════════
_COLS = ['外資', '投信', '自營', '外資大小', '融資餘額', '融券餘額', '前五大留倉', '前十大留倉',
         '選PCR', '外(選)', '未平倉口數', '韭菜指數']


def _cells(html: str) -> list[str]:
    body = html.split('<tbody>', 1)[1]
    return [re.sub(r'<[^>]+>', '', c) for c in re.findall(r'<td[^>]*>(.*?)</td>', body)]


class TestLeadingTableNonFinite:
    @pytest.mark.parametrize('bad', [pd.NA, math.inf, -math.inf, np.float64(-np.inf), math.nan, None],
                             ids=['pdna', 'pinf', 'ninf', 'np_ninf', 'nan', 'none'])
    def test_every_column_shows_dash(self, bad):
        df = pd.DataFrame({'日期': ['2026-10-01'], '成交量': ['3000億'],
                           **{c: pd.Series([bad], dtype=object) for c in _COLS}})
        cells = _cells(render_leading_table(df))      # 修前 pd.NA → TypeError、inf → OverflowError
        # 融資／融券整欄 NA ⇒ 既有邏輯不渲染該二欄（_has_margin=False）；±inf 算 notna ⇒ 渲染
        assert len(cells) - 2 in (len(_COLS) - 2, len(_COLS)), cells
        assert set(cells[2:]) == {'-'}, cells
        assert not any(re.search(r'inf|nan', c, re.I) for c in cells)

    def test_float64_pd_na_column(self):
        df = pd.DataFrame({'日期': ['2026-10-01', '2026-10-02'], '成交量': ['1億', '2億'],
                           '選PCR': pd.array([110.0, pd.NA], dtype='Float64'),
                           '外資大小': pd.array([-40000, pd.NA], dtype='Int64')})
        cells = _cells(render_leading_table(df))
        assert '110.0' in cells and '▼ (40,000)' in cells and cells.count('-') >= 2

    def test_chips_renders_with_pd_na_without_stub(self, monkeypatch):
        """Z20 時需 stub 掉 L1 表格才跑得完；本批起 §三 整段直接跑完。"""
        out = _chips(_li([12000.0], pd.array([pd.NA], dtype=object)), monkeypatch)
        assert '籌碼綜合判斷' in _txt(out)

    def test_finite_table_unchanged(self):
        """修前（基底 f7a969d0）同一份 df 的整張 HTML sha256。"""
        df = pd.DataFrame({
            '日期': ['2026-10-01', '2026-10-02', '2026-10-03'], '成交量': ['3000億', '2800億', '3100億'],
            '外資': [12.3, -4.56, 0.0], '投信': [np.float64(1.25), -0.05, 3], '自營': [0, -7.7, 2.2],
            '外資大小': [-40000.0, 12000, 0], '融資餘額': [3400.4, 2799.6, np.float64(3000)],
            '融券餘額': [100.0, 99.5, 12], '前五大留倉': [-12345.0, 6789, 0], '前十大留倉': [-20000, 15000.0, 1],
            '選PCR': [110.0, 79.95, np.float64(150.55)], '外(選)': [-15000.0, 20000, 0],
            '未平倉口數': [123456, 0, -500], '韭菜指數': [12.34, -6.0, 0.0]})
        got = hashlib.sha256(render_leading_table(df).encode()).hexdigest()
        assert got == '32c3e92e434ab4bfd41146234362d5ddccc535bf425a0d626fd1564a6f1bdff6'
