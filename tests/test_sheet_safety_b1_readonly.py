"""Sheet Safety 批 B1（DEC-083）：`gsheet_portfolio` 讀取真正唯讀；初始化只在明確寫入動作。

客戶原文：「禁止：read → worksheet 不存在 → create worksheet；禁止：read → header/schema 不符 →
rewrite 第一列。正確行為：worksheet missing → 明確 UNAVAILABLE / NOT_CONFIGURED；schema mismatch →
明確 SCHEMA_MISMATCH；permission error → 明確 error；empty sheet → EMPTY；真正空值維持空值。」

⛔ 不打真 Google：讀取路徑一律用 `tests.sheet_safety_fakes` 的 tripwire（任何寫入方法一呼叫就紅）。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.data.portfolio import gsheet_portfolio as gsp
from tests.sheet_safety_fakes import TripwireClient, WriteAttempted
from tests.test_gsheet_portfolio import _FakeWorksheet

H, WH = gsp._HEADERS, gsp._STOCK_WATCHLIST_HEADERS
PF, WL = gsp._WORKSHEET_NAME, gsp._STOCK_WATCHLIST_WORKSHEET


@pytest.fixture(autouse=True)
def _clear():
    gsp.clear_read_cache()
    yield
    gsp.clear_read_cache()


def _reads(sid='SID'):
    """四支 public 讀取（含 raise_if_missing=False 預設）。"""
    return [
        lambda **k: gsp.list_portfolios(sheet_id=sid, **k),
        lambda **k: gsp.load_portfolio('A', sheet_id=sid, **k),
        lambda **k: gsp.load_portfolio('A', sheet_id=sid, keep_blank=True, **k),
        lambda **k: gsp.list_stock_watchlists(sheet_id=sid, **k),
        lambda **k: gsp.load_stock_watchlist('A', sheet_id=sid, **k),
    ]


def _mount(books):
    cli = TripwireClient(books)
    return cli, patch.object(gsp, '_build_client', return_value=cli)


# ── 表頭狀態（純函式）───────────────────────────────────────────────────────
@pytest.mark.parametrize('values, expected', [
    ([], gsp._HEADER_EMPTY),
    ([['', ''], ['', '']], gsp._HEADER_EMPTY),
    ([H], gsp._HEADER_OK),
    ([H + ['note'], ['A', '1', '1', '1', 't', 'x']], gsp._HEADER_OK),        # 右邊自加欄
    ([H + ['', ''], ['A', '1', '1', '1', 't', '', '']], gsp._HEADER_OK),
    ([['name', 'ticker', 'lots'], ['B', 'X', '1']], gsp._HEADER_OK),          # M12 窄表（前段）
    ([['name', 'ticker', 'lots', ''], ['B', 'X', '1', '9']], gsp._HEADER_MISMATCH),  # 資料超出表頭寬
    ([['', '', ''], ['A', '2330', '1']], gsp._HEADER_MISMATCH),               # 第一列空、下面有資料
    ([H + ['name']], gsp._HEADER_MISMATCH),                                   # 本分頁欄重複
    ([['ticker', 'name', 'lots', 'avg_price', 'updated_at']], gsp._HEADER_MISMATCH),
    ([['Name', 'ticker', 'lots', 'avg_price', 'updated_at']], gsp._HEADER_MISMATCH),
    ([['name ', 'ticker', 'lots', 'avg_price', 'updated_at']], gsp._HEADER_MISMATCH),
    ([['foo']], gsp._HEADER_MISMATCH),
])
def test_header_state(values, expected):
    assert gsp._header_state(values, H) == expected


# ── 讀取：分頁不存在 → 不建、預設 []、raise_if_missing → 拋 ───────────────────────
@pytest.mark.parametrize('i', range(5))
def test_missing_worksheet_read_zero_writes(i):
    cli, p = _mount({'SID': {}})
    with p:
        assert _reads()[i]() == []
        with pytest.raises(gsp.SheetWorksheetMissingError):
            _reads()[i](raise_if_missing=True)
    assert cli.writes == []


def test_missing_message_is_plain_and_says_no_auto_create():
    msg = str(gsp.SheetWorksheetMissingError(PF))
    assert PF in msg and '不會自動建立' in msg


# ── 讀取：表頭不符 → 一律拋（不論 raise_if_missing）、⛔ 不改第一列 ─────────────────
@pytest.mark.parametrize('i', range(5))
@pytest.mark.parametrize('raise_if_missing', [False, True])
def test_schema_mismatch_read_raises_zero_writes(i, raise_if_missing):
    bad = [['secret_header_xyz', 'b', 'c'], ['A', '2330', '1']]
    cli, p = _mount({'SID': {PF: bad, WL: bad}})
    with p:
        with pytest.raises(gsp.SheetSchemaMismatchError) as ei:
            _reads()[i](raise_if_missing=raise_if_missing)
    assert cli.writes == []
    msg = str(ei.value)
    assert 'secret_header_xyz' not in msg           # ⛔ 不回顯使用者表頭內容
    assert '不會自動修改' in msg
    assert all(h in msg for h in (H if i < 3 else WH))


# ── 讀取：空表 → []；空白格維持缺值 ─────────────────────────────────────────
@pytest.mark.parametrize('i', range(5))
def test_empty_sheet_reads_empty_zero_writes(i):
    cli, p = _mount({'SID': {PF: [], WL: []}})
    with p:
        assert _reads()[i]() == []
    assert cli.writes == []


def test_blank_cells_stay_none_with_keep_blank():
    cli, p = _mount({'SID': {PF: [H, ['A', '2330', '', '100', 't'], ['A', '0050', '2', '', 't']]}})
    with p:
        rows = gsp.load_portfolio('A', sheet_id='SID', keep_blank=True)
    assert rows == [{'ticker': '2330', 'lots': None, 'avg_price': 100.0},
                    {'ticker': '0050', 'lots': 2.0, 'avg_price': None}]
    assert cli.writes == []


def test_truncated_header_reads_missing_columns_as_missing():
    cli, p = _mount({'SID': {PF: [['name', 'ticker', 'lots'], ['A', '2330', '1']]}})
    with p:
        assert gsp.list_portfolios(sheet_id='SID') == ['A']
        assert gsp.load_portfolio('A', sheet_id='SID') == []          # 缺均價 → 照舊丟
        assert gsp.load_portfolio('A', sheet_id='SID', keep_blank=True) == [
            {'ticker': '2330', 'lots': 1.0, 'avg_price': None}]
    assert cli.writes == []


# ── 讀取：權限 / 找不到 / 網路 → 原樣上拋 ─────────────────────────────────────
@pytest.mark.parametrize('exc', [PermissionError('403'), ConnectionError('down')])
def test_permission_and_network_errors_propagate(exc):
    cli = MagicMock()
    cli.open_by_key.side_effect = exc
    with patch.object(gsp, '_build_client', return_value=cli):
        for fn in _reads():
            with pytest.raises(type(exc)):
                fn()


# ── 讀取：「分頁不存在」也進快取（不每輪 rerun 重打 Google）────────────────────────
def test_missing_status_is_cached_not_refetched_each_rerun():
    cli = TripwireClient({'SID': {}})
    fake_st = MagicMock()
    fake_st.session_state = {'gsheet_tokens': {'access_token': 'a', 'refresh_token': 'r-A'}}
    fake_st.secrets = {}
    with patch.object(gsp, 'st', fake_st), \
         patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
         patch.object(gsp, '_build_client', return_value=cli):
        for _ in range(3):
            assert gsp.list_portfolios(sheet_id='SID') == []
        with pytest.raises(gsp.SheetWorksheetMissingError):
            gsp.list_portfolios(sheet_id='SID', raise_if_missing=True)
    assert cli.opened == ['SID']
    assert cli.writes == []


# ── 寫入：建分頁只在明確寫入動作；表頭不符在任何寫入之前拋 ─────────────────────────
def _write_sheet(existing_ws=None):
    """Spreadsheet stub:有 `existing_ws` → worksheet() 回它;否則 WorksheetNotFound,add_worksheet 回空表。"""
    import gspread
    sh = MagicMock()
    created = _FakeWorksheet([[]], row_count=200, col_count=10)
    if existing_ws is None:
        sh.worksheet.side_effect = gspread.WorksheetNotFound('x')
    else:
        sh.worksheet.return_value = existing_ws
    sh.add_worksheet.return_value = created
    cli = MagicMock()
    cli.open_by_key.return_value = sh
    return cli, sh, created


@pytest.mark.parametrize('save, ws_name, headers', [
    (lambda: gsp.save_portfolio('A', [{'ticker': '2330', 'lots': 1, 'avg_price': 10}],
                                sheet_id='SID'), PF, H),
    (lambda: gsp.save_stock_watchlist('A', ['2330'], sheet_id='SID'), WL, WH),
    (lambda: gsp.add_to_stock_watchlist('A', ['2330'], sheet_id='SID'), WL, WH),
])
def test_save_creates_missing_worksheet_and_writes_header(save, ws_name, headers):
    cli, sh, created = _write_sheet()
    with patch.object(gsp, '_build_client', return_value=cli):
        save()
    sh.add_worksheet.assert_called_once()
    assert sh.add_worksheet.call_args.kwargs['title'] == ws_name
    vals = created.get_all_values()
    assert vals[0] == headers and vals[1][:2] == ['A', '2330']


def test_save_invalid_input_does_not_create_worksheet():
    cli, sh, _ = _write_sheet()
    with patch.object(gsp, '_build_client', return_value=cli):
        with pytest.raises(ValueError):
            gsp.save_portfolio('A', [{'ticker': '2330', 'lots': 0, 'avg_price': 1}], sheet_id='SID')
    cli.open_by_key.assert_not_called()
    sh.add_worksheet.assert_not_called()


@pytest.mark.parametrize('delete', [
    lambda: gsp.delete_portfolio('A', sheet_id='SID'),
    lambda: gsp.delete_stock_watchlist('A', sheet_id='SID'),
])
def test_delete_on_missing_worksheet_returns_zero_without_creating(delete):
    cli, sh, _ = _write_sheet()
    with patch.object(gsp, '_build_client', return_value=cli):
        assert delete() == 0
    sh.add_worksheet.assert_not_called()


_BAD = [['oops', 'ticker', 'x'], ['A', '2330', '1']]


@pytest.mark.parametrize('write', [
    lambda: gsp.save_portfolio('A', [{'ticker': '1', 'lots': 1, 'avg_price': 1}], sheet_id='SID'),
    lambda: gsp.save_stock_watchlist('A', ['1'], sheet_id='SID'),
    lambda: gsp.add_to_stock_watchlist('A', ['1'], sheet_id='SID'),
    lambda: gsp.delete_portfolio('A', sheet_id='SID'),
    lambda: gsp.delete_stock_watchlist('A', sheet_id='SID'),
])
def test_writes_refuse_schema_mismatch_before_any_write(write):
    ws = _FakeWorksheet([list(r) for r in _BAD])
    cli, sh, _ = _write_sheet(ws)
    with patch.object(gsp, '_build_client', return_value=cli):
        with pytest.raises(gsp.SheetSchemaMismatchError) as ei:
            write()
    assert ws.calls == [] and ws.get_all_values() == _BAD
    sh.add_worksheet.assert_not_called()
    assert '維持原狀' in str(ei.value) and 'oops' not in str(ei.value)


def test_watchlist_save_keeps_user_trailing_header_cells():
    ws = _FakeWorksheet([WH + ['note'], ['B', '2454', 't', 'mine']])
    with patch.object(gsp, '_ws', return_value=ws):
        gsp.save_stock_watchlist('A', ['2330'])
        vals = ws.get_all_values()
    assert vals[0] == WH + ['note']
    assert vals[1] == ['B', '2454', 't', 'mine']


# ── add_to_stock_watchlist：⛔ 不再先清全域讀取快取 ──────────────────────────────
def test_add_to_watchlist_does_not_clear_global_cache_before_reading():
    ws = _FakeWorksheet([WH, ['A', '2454', 't']])
    with patch.object(gsp, '_ws', return_value=ws), \
         patch.object(gsp, 'clear_read_cache') as _clr:
        assert gsp.add_to_stock_watchlist('A', ['2330']) == 2
    # 只剩 save_stock_watchlist 寫入後那一次（寫入即清，B5 本批不動）；合併前那一次已拿掉。
    assert _clr.call_count == 1
    assert [r[1] for r in ws.get_all_values()[1:]] == ['2454', '2330']


def test_add_to_watchlist_reads_fresh_sheet_not_cache():
    """合併前讀的是 Sheet 最新內容（不經快取）—— 別處剛加的代碼不會被覆蓋掉。"""
    ws = _FakeWorksheet([WH, ['A', '2454', 't']])
    fake_st = MagicMock()
    fake_st.session_state = {'gsheet_tokens': {'access_token': 'a', 'refresh_token': 'r-A'}}
    fake_st.secrets = {}
    with patch.object(gsp, 'st', fake_st), \
         patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
         patch.object(gsp, '_ws', return_value=ws):
        assert gsp.load_stock_watchlist('A', sheet_id='SID') == ['2454']   # 有身分 ⇒ 進快取
        ws.rows.append(['A', '1101', 't'])                                  # 外部直接改 Sheet
        assert gsp.load_stock_watchlist('A', sheet_id='SID') == ['2454']   # 快取仍是舊的（對照）
        with patch.object(gsp, 'clear_read_cache'):   # 隔離:不讓 save 寫入後的清快取干擾判讀
            gsp.add_to_stock_watchlist('A', ['2330'], sheet_id='SID')
    assert [r[1] for r in ws.get_all_values()[1:]] == ['2454', '1101', '2330']


# ── classify_read_error ──────────────────────────────────────────────────
def _api_error(code):
    from gspread.exceptions import APIError
    resp = MagicMock()
    resp.json.return_value = {'error': {'code': code, 'message': 'm', 'status': 's'}}
    return APIError(resp)


@pytest.mark.parametrize('exc, code', [
    (gsp.SheetWorksheetMissingError(PF), gsp.READ_WORKSHEET_MISSING),
    (gsp.SheetSchemaMismatchError(PF, H), gsp.READ_SCHEMA_MISMATCH),
    (gsp.LoginRequiredError('x'), gsp.READ_ERROR_LOGIN_REQUIRED),
    (PermissionError(), gsp.READ_ERROR_PERMISSION_DENIED),
    (ConnectionError(), gsp.READ_ERROR_NETWORK),
    (TimeoutError(), gsp.READ_ERROR_NETWORK),
    (ValueError('x'), 'error:ValueError'),
])
def test_classify_read_error(exc, code):
    assert gsp.classify_read_error(exc) == code


@pytest.mark.parametrize('http, code', [
    (403, gsp.READ_ERROR_PERMISSION_DENIED), (404, gsp.READ_ERROR_SHEET_NOT_FOUND),
    (429, gsp.READ_ERROR_QUOTA_EXCEEDED), (500, 'error:APIError')])
def test_classify_read_error_gspread_api_codes(http, code):
    assert gsp.classify_read_error(_api_error(http)) == code


def test_classify_read_error_spreadsheet_not_found_and_requests():
    import requests
    from gspread.exceptions import SpreadsheetNotFound
    assert gsp.classify_read_error(SpreadsheetNotFound()) == gsp.READ_ERROR_SHEET_NOT_FOUND
    assert gsp.classify_read_error(requests.exceptions.ConnectionError()) == gsp.READ_ERROR_NETWORK
    assert gsp.classify_read_error(requests.exceptions.ReadTimeout()) == gsp.READ_ERROR_NETWORK


def test_tripwire_itself_catches_writes():
    """守衛自身有效：tripwire 的寫入方法真的會紅（避免假綠）。"""
    cli = TripwireClient({'SID': {PF: [H]}})
    ws = cli.open_by_key('SID').worksheet(PF)
    with pytest.raises(WriteAttempted):
        ws.update([['x']], 'A1')
    assert cli.writes == [('TripwireWorksheet', 'update')]
