"""批 Z33（Z12-n2）—— 前進式驗證讀 Sheet 凍結紀錄:`stock_id`／`name` 保留原字串。

依據:客戶 2026-10-10〈資料品質、資料來源與公式正確性治理規則〉四、Level 1「型別轉換錯誤＝明確 bug」;
同類問題已於 Q-r7a（批 Z12 D1-n1,portfolio 讀表 `_TEXT_COLS`）修過。

- 修前:`load_forward_test_picks` 走 gspread `get_all_records()` 預設 numericise ⇒ "0050"→50、
  純數字名稱 "0056"→56;`load_frozen_picks_df` 做「本地 ∪ Sheet」去重時 '0050' 與 '50' 被當兩檔,
  '50' 抓不到現價、對帳時被剔除。
- 修後:`stock_id`／`name` 原字串;**其餘欄轉換與 `get_all_records()` 預設逐一相同**（regression）。

假 worksheet 只假造「Sheet 回傳的原始字串格」（`get` / `row_values`）;轉換本身用 gspread 真實的
`Worksheet.get_all_records` 實作（不 mock 掉 numericise）。
`_PRE_FIX_GOLDEN` 為修前碼（基底 origin/main `a56ccf37`）以本檔同一份資料實跑所得,⛔ 不由現行碼反推。
"""
from __future__ import annotations

import math

import pytest
from gspread.worksheet import Worksheet

import src.data.portfolio.gsheet_portfolio as gp
import src.services.forward_test_service as fts

_H = ['cohort', 'stock_id', 'name', 'entry_price', 'factors', 'frozen_at', 'score']
_ROWS = [
    ['2026-09-30', '0050', '0056', '1,050', 'pe_low', '2026-09-30T19:00:00+08:00', '87.5'],
    ['20260930', '00632R', '1234', '180.5', '3', '2026-09-30', '1e3'],
    ['2026-09-30', '2330', '台積電', '1000', 'NaN', '', '1_000'],
    ['2026-09-30', '6223', '007', '-12.25', '', '2026/09/30', '50%'],
    ['2026-09-30', '', '', '', 'x', '', ''],
]

# 修前碼實跑結果（基底 a56ccf37）。
_PRE_FIX_GOLDEN = [
    {'cohort': '2026-09-30', 'stock_id': 50, 'name': 56, 'entry_price': 1050, 'factors': 'pe_low',
     'frozen_at': '2026-09-30T19:00:00+08:00', 'score': 87.5},
    {'cohort': 20260930, 'stock_id': '00632R', 'name': 1234, 'entry_price': 180.5, 'factors': 3,
     'frozen_at': '2026-09-30', 'score': 1000.0},
    {'cohort': '2026-09-30', 'stock_id': 2330, 'name': '台積電', 'entry_price': 1000, 'factors': math.nan,
     'frozen_at': '', 'score': '1_000'},
    {'cohort': '2026-09-30', 'stock_id': 6223, 'name': 7, 'entry_price': -12.25, 'factors': '',
     'frozen_at': '2026/09/30', 'score': '50%'},
    {'cohort': '2026-09-30', 'stock_id': '', 'name': '', 'entry_price': '', 'factors': 'x',
     'frozen_at': '', 'score': ''},
]
_TEXT = ('stock_id', 'name')


class _FakeWS:
    """只假造 Sheet API 回傳的原始字串格;`get_all_records` 用 gspread 真實作。"""

    def __init__(self, values):
        self.values = [list(r) for r in values]

    def get(self, value_render_option=None, pad_values=True):   # 同 gspread:空表 → [[]]
        if not self.values:
            return [[]]
        w = max(len(r) for r in self.values)
        return [r + [''] * (w - len(r)) for r in self.values]

    def row_values(self, i):
        return list(self.values[i - 1]) if len(self.values) >= i else []

    get_all_records = Worksheet.get_all_records


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return type(a) is type(b) and a == b


def _load(monkeypatch, values):
    monkeypatch.setattr(gp, '_ft_worksheet', lambda: _FakeWS(values))
    return gp.load_forward_test_picks()


# ── 主行為:代號／名稱原字串 ──────────────────────────────────────────────
def test_stock_id_and_name_keep_raw_strings(monkeypatch):
    recs = _load(monkeypatch, [_H] + _ROWS)
    assert [r['stock_id'] for r in recs] == ['0050', '00632R', '2330', '6223', '']
    assert [r['name'] for r in recs] == ['0056', '1234', '台積電', '007', '']
    for r in recs:
        assert isinstance(r['stock_id'], str) and isinstance(r['name'], str)


def test_other_columns_identical_to_pre_fix(monkeypatch):
    """其餘欄逐格與修前碼實跑結果相同（含型別）;且與 gspread 預設 get_all_records() 相同。"""
    recs = _load(monkeypatch, [_H] + _ROWS)
    default = _FakeWS([_H] + _ROWS).get_all_records()
    assert len(recs) == len(_PRE_FIX_GOLDEN) == len(default)
    for got, pre, dft in zip(recs, _PRE_FIX_GOLDEN, default):
        assert list(got) == _H
        for k in _H:
            if k in _TEXT:
                continue
            assert _same(got[k], pre[k]), (k, got[k], pre[k])
            assert _same(got[k], dft[k]), (k, got[k], dft[k])


def test_pre_fix_golden_matches_gspread_default():
    """golden 本身的錨:修前 = gspread 預設 get_all_records()（含代號被轉數字）。"""
    default = _FakeWS([_H] + _ROWS).get_all_records()
    for d, pre in zip(default, _PRE_FIX_GOLDEN):
        for k in _H:
            assert _same(d[k], pre[k]), (k, d[k], pre[k])


def test_column_position_found_from_actual_header(monkeypatch):
    """欄序不同時仍依實際表頭找 stock_id／name。"""
    hdr = ['name', 'cohort', 'entry_price', 'stock_id']
    recs = _load(monkeypatch, [hdr, ['0056', '2026-09-30', '1,050', '0050']])
    assert recs == [{'name': '0056', 'cohort': '2026-09-30', 'entry_price': 1050, 'stock_id': '0050'}]


# ── 去重:本地 '0050' ∪ Sheet "0050" → 1 列 ──────────────────────────────
def test_union_dedupe_leading_zero(monkeypatch):
    monkeypatch.setattr('src.data.portfolio.forward_test_store.load_picks_local',
                        lambda: [{'cohort': '2026-09-30', 'stock_id': '0050', 'name': '元大台灣50',
                                  'entry_price': 180.5, 'factors': 'pe_low', 'frozen_at': 'x'}])
    monkeypatch.setattr(gp, '_ft_worksheet', lambda: _FakeWS([
        list(gp._FT_HEADERS),
        ['2026-09-30', '0050', '元大台灣50', '180.5', 'pe_low', '2026-09-30T19:00:00+08:00'],
        ['2026-09-30', '2330', '台積電', '1000', 'pe_low', '2026-09-30T19:00:00+08:00'],
    ]))
    df = fts.load_frozen_picks_df()
    assert sorted(df['stock_id'].tolist()) == ['0050', '2330']
    assert (df['stock_id'] == '0050').sum() == 1
    assert '50' not in df['stock_id'].tolist()
    # 本地優先(keep='first')
    assert df.loc[df['stock_id'] == '0050', 'frozen_at'].iloc[0] == 'x'


# ── 邊界 ──────────────────────────────────────────────────────────────
def test_empty_sheet(monkeypatch):
    assert _load(monkeypatch, []) == []


def test_header_only(monkeypatch):
    assert _load(monkeypatch, [list(gp._FT_HEADERS)]) == []


def test_missing_stock_id_column_behaves_as_before(monkeypatch):
    """表頭缺 stock_id:其他欄（含佔了第 2 欄的 code）照舊轉換;name 仍保留字串。"""
    hdr = ['cohort', 'code', 'name', 'entry_price']
    rows = [['2026-09-30', '0050', '0056', '1,050']]
    recs = _load(monkeypatch, [hdr] + rows)
    assert recs == [{'cohort': '2026-09-30', 'code': 50, 'name': '0056', 'entry_price': 1050}]


def test_missing_both_text_columns_identical_to_default(monkeypatch):
    hdr = ['cohort', 'code', 'entry_price']
    rows = [['20260930', '0050', '1,050'], ['', '', '']]
    recs = _load(monkeypatch, [hdr] + rows)
    assert recs == _FakeWS([hdr] + rows).get_all_records()
    assert recs[0] == {'cohort': 20260930, 'code': 50, 'entry_price': 1050}


def test_blank_and_none_cells(monkeypatch):
    """空字串與 None 儲存格:代號／名稱原樣（'' / None),其餘欄同 gspread 預設。"""
    hdr = list(gp._FT_HEADERS)
    rows = [['2026-09-30', '', None, None, '', ''], ['2026-09-30', None, '', '', None, None]]
    recs = _load(monkeypatch, [hdr] + rows)
    default = _FakeWS([hdr] + rows).get_all_records()
    assert [r['stock_id'] for r in recs] == ['', None]
    assert [r['name'] for r in recs] == [None, '']
    for got, dft in zip(recs, default):
        for k in hdr:
            if k not in _TEXT:
                assert _same(got[k], dft[k]), (k, got[k], dft[k])


def test_read_failure_returns_empty(monkeypatch):
    def _boom():
        raise RuntimeError('尚未設定 Sheet ID')
    monkeypatch.setattr(gp, '_ft_worksheet', _boom)
    assert gp.load_forward_test_picks() == []


@pytest.mark.parametrize('code', ['0050', '00632R', '2330', '6223'])
def test_each_code_roundtrips(monkeypatch, code):
    recs = _load(monkeypatch, [list(gp._FT_HEADERS),
                               ['2026-09-30', code, code, '1', 'f', '2026-09-30']])
    assert recs[0]['stock_id'] == code and recs[0]['name'] == code
    assert recs[0]['entry_price'] == 1
