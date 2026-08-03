"""gsheet_portfolio.py 單元測試 — mock gspread client 不打真 API。"""
from unittest.mock import MagicMock, patch

import pytest

from src.data.portfolio import gsheet_portfolio as gsp


class _FakeWorksheet:
    """模擬 gspread.Worksheet：用 list[list] 存 2D 資料 + header。"""
    def __init__(self, initial_rows=None):
        self.rows = list(initial_rows or [gsp._HEADERS])

    def get_all_values(self):
        return [list(r) for r in self.rows]

    def get_all_records(self):
        if len(self.rows) < 2:
            return []
        headers = self.rows[0]
        return [dict(zip(headers, [str(v) for v in r])) for r in self.rows[1:]]

    def row_values(self, n):
        return list(self.rows[n - 1]) if n - 1 < len(self.rows) else []

    def update(self, _range, values):
        if _range.startswith('A1') and values:
            self.rows[0] = list(values[0])

    def append_row(self, row):
        self.rows.append(list(row))

    def append_rows(self, rows):
        for r in rows:
            self.rows.append(list(r))

    def clear(self):
        self.rows = []


@pytest.fixture
def fake_ws():
    """乾淨的 worksheet，只含 header。"""
    ws = _FakeWorksheet()
    with patch.object(gsp, '_ws', return_value=ws):
        yield ws


@pytest.fixture
def populated_ws():
    """預先塞兩組組合的 worksheet。"""
    ws = _FakeWorksheet([
        gsp._HEADERS,
        ['攻擊組合', '0050.TW', 1.0, 135.5, '2026-05-19 10:00:00'],
        ['攻擊組合', '00713.TW', 0.5, 82.3, '2026-05-19 10:00:00'],
        ['存股組合', 'BND', 0.2, 72.5, '2026-05-19 10:01:00'],
    ])
    with patch.object(gsp, '_ws', return_value=ws):
        yield ws


# ── is_configured ───────────────────────────────────────────
def test_is_configured_no_streamlit():
    with patch.object(gsp, 'st', None):
        assert gsp.is_configured() is False


def test_is_configured_missing_keys():
    fake_st = MagicMock()
    fake_st.secrets = MagicMock()
    fake_st.secrets.__getitem__ = MagicMock(side_effect=KeyError('portfolio_sheet_id'))
    with patch.object(gsp, 'st', fake_st):
        assert gsp.is_configured() is False


def test_is_configured_ok():
    fake_st = MagicMock()
    fake_st.secrets = {'portfolio_sheet_id': 'abc', 'gcp_service_account': {'x': 1}}
    with patch.object(gsp, 'st', fake_st):
        assert gsp.is_configured() is True


# ── list_portfolios ─────────────────────────────────────────
def test_list_portfolios_empty(fake_ws):
    assert gsp.list_portfolios() == []


def test_list_portfolios_dedup_sorted(populated_ws):
    names = gsp.list_portfolios()
    assert names == ['存股組合', '攻擊組合']


def test_list_portfolios_skips_blank_name():
    ws = _FakeWorksheet([gsp._HEADERS, ['', '0050.TW', 1, 100, 'ts']])
    with patch.object(gsp, '_ws', return_value=ws):
        assert gsp.list_portfolios() == []


# ── load_portfolio ──────────────────────────────────────────
def test_load_portfolio_existing(populated_ws):
    rows = gsp.load_portfolio('攻擊組合')
    assert len(rows) == 2
    assert rows[0]['ticker'] == '0050.TW'
    assert rows[0]['lots'] == 1.0
    assert rows[0]['avg_price'] == 135.5
    assert rows[1]['ticker'] == '00713.TW'


def test_load_portfolio_missing_name(populated_ws):
    assert gsp.load_portfolio('不存在') == []


def test_load_portfolio_empty_name(populated_ws):
    assert gsp.load_portfolio('') == []
    assert gsp.load_portfolio('   ') == []


def test_load_portfolio_skips_invalid_rows():
    ws = _FakeWorksheet([
        gsp._HEADERS,
        ['測試', '0050.TW', 1, 100, 'ts'],
        ['測試', '0050.TW', 0, 100, 'ts'],     # 張數為 0 略過
        ['測試', '', 1, 100, 'ts'],            # 代號空略過
        ['測試', 'BND', 'abc', 100, 'ts'],     # 張數非數字略過
    ])
    with patch.object(gsp, '_ws', return_value=ws):
        rows = gsp.load_portfolio('測試')
        assert len(rows) == 1
        assert rows[0]['ticker'] == '0050.TW'


# ── save_portfolio ──────────────────────────────────────────
def test_save_portfolio_new(fake_ws):
    n = gsp.save_portfolio('新組合', [
        {'ticker': '0050.TW', 'lots': 1.0, 'avg_price': 135.5},
        {'ticker': 'BND', 'lots': 0.2, 'avg_price': 72.5},
    ])
    assert n == 2
    assert fake_ws.rows[0] == gsp._HEADERS
    assert fake_ws.rows[1][0] == '新組合'
    assert fake_ws.rows[1][1] == '0050.TW'
    assert fake_ws.rows[2][1] == 'BND'


def test_save_portfolio_overwrites_same_name(populated_ws):
    """同名儲存應覆蓋既有，不重複堆疊。"""
    n = gsp.save_portfolio('攻擊組合', [
        {'ticker': 'VOO', 'lots': 0.1, 'avg_price': 400.0},
    ])
    assert n == 1
    rows = gsp.load_portfolio('攻擊組合')
    assert len(rows) == 1
    assert rows[0]['ticker'] == 'VOO'
    # 存股組合不受影響
    assert len(gsp.load_portfolio('存股組合')) == 1


def test_save_portfolio_empty_name(fake_ws):
    with pytest.raises(ValueError, match='名稱'):
        gsp.save_portfolio('', [{'ticker': 'X', 'lots': 1, 'avg_price': 1}])


def test_save_portfolio_empty_rows(fake_ws):
    with pytest.raises(ValueError, match='內容'):
        gsp.save_portfolio('x', [])


def test_save_portfolio_all_invalid_rows(fake_ws):
    with pytest.raises(ValueError, match='有效'):
        gsp.save_portfolio('x', [
            {'ticker': '', 'lots': 1, 'avg_price': 1},
            {'ticker': 'A', 'lots': 0, 'avg_price': 1},
            {'ticker': 'B', 'lots': 1, 'avg_price': 0},
        ])


def test_save_portfolio_uppercases_ticker(fake_ws):
    gsp.save_portfolio('x', [{'ticker': '0050.tw', 'lots': 1, 'avg_price': 100}])
    rows = gsp.load_portfolio('x')
    assert rows[0]['ticker'] == '0050.TW'


# ── delete_portfolio ────────────────────────────────────────
def test_delete_portfolio_existing(populated_ws):
    n = gsp.delete_portfolio('攻擊組合')
    assert n == 2
    assert gsp.load_portfolio('攻擊組合') == []
    # 存股組合不受影響
    assert len(gsp.load_portfolio('存股組合')) == 1


def test_delete_portfolio_missing(populated_ws):
    n = gsp.delete_portfolio('不存在')
    assert n == 0
    # 原始資料不變
    assert len(gsp.list_portfolios()) == 2


def test_delete_portfolio_empty_name(populated_ws):
    assert gsp.delete_portfolio('') == 0


def test_delete_portfolio_empty_sheet(fake_ws):
    assert gsp.delete_portfolio('x') == 0


# ══ Phase 1: 個股 / ETF 雲端 sheet 分家（sheet_id 參數化 + 個股專屬通道）══════
def _fake_client_capturing():
    """回 (client, opened)：client.open_by_key 記錄每次的 sheet_id 到 opened，
    並回一個 `.worksheet()` 給乾淨 _FakeWorksheet 的 spreadsheet stub。"""
    opened: list[str] = []

    def _open_by_key(sid):
        opened.append(sid)
        _sh = MagicMock()
        _sh.worksheet.return_value = _FakeWorksheet()
        return _sh

    client = MagicMock()
    client.open_by_key.side_effect = _open_by_key
    return client, opened


def test_no_sheet_id_routes_to_legacy_active():
    """(a) 不帶 sheet_id → 走 legacy _get_active_sheet_id（ETF 向後相容 byte-for-byte）。"""
    client, opened = _fake_client_capturing()
    with patch.object(gsp, '_build_client', return_value=client), \
         patch.object(gsp, '_get_active_sheet_id',
                      return_value='LEGACY_SID') as _mock_legacy:
        gsp.list_portfolios()
        gsp.load_portfolio('x')
        gsp.save_portfolio('g', [{'ticker': '2330', 'lots': 1, 'avg_price': 100}])
        gsp.delete_portfolio('g')
    assert opened == ['LEGACY_SID'] * 4
    assert _mock_legacy.call_count >= 4


def test_explicit_sheet_id_routes_to_that_sheet():
    """(b) 明確 sheet_id → open_by_key 用那把 key,且**不**呼叫 legacy accessor（短路）。"""
    client, opened = _fake_client_capturing()
    with patch.object(gsp, '_build_client', return_value=client), \
         patch.object(gsp, '_get_active_sheet_id',
                      return_value='LEGACY_SID') as _mock_legacy:
        gsp.list_portfolios(sheet_id='STOCK_SID')
        gsp.load_portfolio('x', sheet_id='STOCK_SID')
        gsp.save_portfolio('g', [{'ticker': '2330', 'lots': 1, 'avg_price': 100}],
                           sheet_id='STOCK_SID')
        gsp.delete_portfolio('g', sheet_id='STOCK_SID')
    assert set(opened) == {'STOCK_SID'}           # legacy sheet 完全沒被打開
    assert opened == ['STOCK_SID'] * 4
    _mock_legacy.assert_not_called()              # 明確 sheet_id 短路 legacy accessor


def test_explicit_sheet_id_differs_from_legacy():
    """(b) 同一批操作:legacy 與明確 sheet_id 打開的是**不同** key（真正分家）。"""
    client, opened = _fake_client_capturing()
    with patch.object(gsp, '_build_client', return_value=client), \
         patch.object(gsp, '_get_active_sheet_id', return_value='ETF_LEGACY_SID'):
        gsp.list_portfolios()                     # ETF（legacy）
        gsp.list_portfolios(sheet_id='STOCK_SID')  # 個股
    assert opened == ['ETF_LEGACY_SID', 'STOCK_SID']


def test_empty_string_sheet_id_falls_back_to_legacy():
    """sheet_id='' (falsy) → 視同 None 走 legacy（防禦性:callback 已先擋空）。"""
    client, opened = _fake_client_capturing()
    with patch.object(gsp, '_build_client', return_value=client), \
         patch.object(gsp, '_get_active_sheet_id', return_value='LEGACY_SID'):
        gsp.list_portfolios(sheet_id='')
    assert opened == ['LEGACY_SID']


# ── (c) _get_active_stock_sheet_id：只讀個股通道，不借 ETF 通道 / 無 secrets fallback ──
def test_get_active_stock_sheet_id_reads_stock_key():
    """(c) 只讀 STOCK_PORTFOLIO_SHEET_KEY,不讀 portfolio_sheet_id。"""
    fake_st = MagicMock()
    fake_st.session_state = {
        gsp.STOCK_PORTFOLIO_SHEET_KEY: 'STOCK_123',
        gsp.PORTFOLIO_SHEET_KEY: 'ETF_999',
    }
    with patch.object(gsp, 'st', fake_st):
        assert gsp._get_active_stock_sheet_id() == 'STOCK_123'


def test_get_active_stock_sheet_id_ignores_etf_session_key():
    """(c) 只設 ETF 的 portfolio_sheet_id → 個股通道仍回空（不靜默借用）。"""
    fake_st = MagicMock()
    fake_st.session_state = {gsp.PORTFOLIO_SHEET_KEY: 'ETF_999'}
    with patch.object(gsp, 'st', fake_st):
        assert gsp._get_active_stock_sheet_id() == ''


def test_get_active_stock_sheet_id_no_secrets_fallback():
    """(c) 個股通道**無** secrets fallback（SA/secrets 仍屬 ETF-legacy 專用）。"""
    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.secrets = {gsp.PORTFOLIO_SHEET_KEY: 'ETF_FROM_SECRETS'}
    with patch.object(gsp, 'st', fake_st):
        assert gsp._get_active_stock_sheet_id() == ''


def test_get_active_stock_sheet_id_no_streamlit():
    with patch.object(gsp, 'st', None):
        assert gsp._get_active_stock_sheet_id() == ''


def test_legacy_active_sheet_id_still_reads_etf_key():
    """對照組:legacy _get_active_sheet_id 仍讀 portfolio_sheet_id（ETF 行為不變）。"""
    fake_st = MagicMock()
    fake_st.session_state = {gsp.PORTFOLIO_SHEET_KEY: 'ETF_999'}
    fake_st.secrets = {}
    with patch.object(gsp, 'st', fake_st):
        assert gsp._get_active_sheet_id() == 'ETF_999'


def test_sheet_key_constants_distinct():
    """§3.3 兩條 session-key 常數必須不同（分家的根本）。"""
    assert gsp.PORTFOLIO_SHEET_KEY == 'portfolio_sheet_id'
    assert gsp.STOCK_PORTFOLIO_SHEET_KEY == 'stock_portfolio_sheet_id'
    assert gsp.PORTFOLIO_SHEET_KEY != gsp.STOCK_PORTFOLIO_SHEET_KEY
