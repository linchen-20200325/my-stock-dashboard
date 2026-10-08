"""批 Z12 —— 持股 Google Sheet 讀寫三項（客戶 2026-10-06 裁示 Q-r7a ①）。

- D1-n1：數字樣的名稱／代號讀入時不得被改寫（`0050` 不可變 `50`）。
- D1-n5：`save_stock_watchlist`／`delete_portfolio`／`delete_stock_watchlist`
  中途失敗不得把整張表清空（比照 `save_portfolio` 的單次整表寫入）。
- D1-n6：表頭有重複欄名（使用者自加欄、多欄空白表頭）時編輯器仍載得進來；
  核心欄（name／ticker…）本身重複則照舊 fail loud（§1：不讀錯欄）。

全部用假 worksheet，⛔ 不呼叫真實 Google Sheet。
"""
from unittest.mock import patch

import pytest

from src.data.portfolio import gsheet_portfolio as gsp
from tests.test_gsheet_portfolio import _FakeWorksheet

_WL_H = gsp._STOCK_WATCHLIST_HEADERS


@pytest.fixture(autouse=True)
def _clear_read_cache():
    gsp.clear_read_cache()
    yield
    gsp.clear_read_cache()


class _BrokenWriteWorksheet(_FakeWorksheet):
    """`clear()` 成功、之後任何寫入都斷線 —— 模擬「清空後寫回前失敗」。"""

    def append_row(self, row):
        raise ConnectionError('斷線')

    def append_rows(self, rows):
        raise ConnectionError('斷線')

    def update(self, values=None, range_name=None):
        raise ConnectionError('斷線')


# ── D1-n5：中途失敗不得清空整張表 ──────────────────────────────────────
_PF_SHEET = [gsp._HEADERS, ['A', '2330', '1', '100', 't0'], ['B', 'VOO', '2', '400', 't0']]
_WL_SHEET = [_WL_H, ['A', '2330', 't0'], ['B', 'VOO', 't0']]


@pytest.mark.parametrize('sheet,call', [
    (_WL_SHEET, lambda: gsp.save_stock_watchlist('A', ['2317'])),
    (_PF_SHEET, lambda: gsp.delete_portfolio('A')),
    (_WL_SHEET, lambda: gsp.delete_stock_watchlist('A')),
], ids=['save_stock_watchlist', 'delete_portfolio', 'delete_stock_watchlist'])
def test_d1n5_write_failure_leaves_sheet_intact(sheet, call):
    ws = _BrokenWriteWorksheet([list(r) for r in sheet])
    before = ws.get_all_values()
    with patch.object(gsp, '_ws', return_value=ws):
        with pytest.raises(ConnectionError):
            call()
    assert ws.get_all_values() == before
    assert ('clear',) not in ws.calls


def test_d1n5_save_stock_watchlist_result():
    ws = _FakeWorksheet([list(r) for r in _WL_SHEET] + [['C', 'X', 't0']])
    with patch.object(gsp, '_ws', return_value=ws):
        assert gsp.save_stock_watchlist('B', ['2317', '2330']) == 2
        vals = ws.get_all_values()
    assert vals[0] == _WL_H
    assert [r[:2] for r in vals[1:]] == [['A', '2330'], ['C', 'X'],
                                        ['B', '2317'], ['B', '2330']]


def test_d1n5_save_stock_watchlist_grows_small_sheet():
    """新列超出表格格數時先擴列（原 append_rows 會自動長；單次 update 不會）。"""
    ws = _FakeWorksheet([list(r) for r in _WL_SHEET], row_count=3, col_count=3)
    with patch.object(gsp, '_ws', return_value=ws):
        assert gsp.save_stock_watchlist('C', ['1', '2', '3']) == 3
        vals = ws.get_all_values()
    assert len(vals) == 6 and vals[-1][:2] == ['C', '3']


@pytest.mark.parametrize('sheet,call,deleted,left', [
    (_PF_SHEET + [['A', '2317', '1', '1', 't0']], lambda: gsp.delete_portfolio('A'), 2,
     [['B', 'VOO', '2', '400', 't0']]),
    (_WL_SHEET + [['A', '2317', 't0']], lambda: gsp.delete_stock_watchlist('A'), 2,
     [['B', 'VOO', 't0']]),
], ids=['delete_portfolio', 'delete_stock_watchlist'])
def test_d1n5_delete_shrinks_sheet_without_leftover_rows(sheet, call, deleted, left):
    ws = _FakeWorksheet([list(r) for r in sheet])
    with patch.object(gsp, '_ws', return_value=ws):
        assert call() == deleted
        vals = ws.get_all_values()
    assert vals[0] == sheet[0]
    assert vals[1:] == left
