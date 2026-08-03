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


# ══ Option B: 個股純代碼觀察清單（stock_watchlist 分頁,§1 無價格/哨兵）══════════
class _CapturingWorksheet:
    """只記錄 update(range, values) 呼叫,用來驗證 header 更新範圍是否動態。"""
    def __init__(self, first_row):
        self._first_row = list(first_row)
        self.update_calls: list[tuple] = []

    def row_values(self, n):
        return list(self._first_row) if n == 1 else []

    def update(self, range_name, values):
        self.update_calls.append((range_name, [list(v) for v in values]))


def _mount_capturing_ws(first_row):
    """建一個 _build_client stub,open_by_key → spreadsheet → 回傳 capturing ws。"""
    ws = _CapturingWorksheet(first_row)
    sh = MagicMock()
    sh.worksheet.return_value = ws
    client = MagicMock()
    client.open_by_key.return_value = sh
    return ws, client


@pytest.fixture
def fake_watchlist_ws():
    """乾淨的 stock_watchlist worksheet（只含 3 欄 header）。"""
    ws = _FakeWorksheet([gsp._STOCK_WATCHLIST_HEADERS])
    with patch.object(gsp, '_ws', return_value=ws):
        yield ws


# ── 常數 / schema 物理隔離 ─────────────────────────────────────
def test_watchlist_constants():
    """§3.3 worksheet 名稱 + headers 具名常數;3 欄純代碼,與 portfolios 物理隔離。"""
    assert gsp._STOCK_WATCHLIST_WORKSHEET == 'stock_watchlist'
    assert gsp._STOCK_WATCHLIST_HEADERS == ['name', 'ticker', 'updated_at']
    # 不同分頁 + 無價格欄(lots/avg_price 不在 watchlist headers)
    assert gsp._STOCK_WATCHLIST_WORKSHEET != gsp._WORKSHEET_NAME
    assert 'lots' not in gsp._STOCK_WATCHLIST_HEADERS
    assert 'avg_price' not in gsp._STOCK_WATCHLIST_HEADERS


# ── save→load round-trip：僅代碼、無價格、無哨兵 ──────────────
def test_save_stock_watchlist_roundtrip_no_price(fake_watchlist_ws):
    n = gsp.save_stock_watchlist('觀察', ['2330', '2454', '0050.tw'])
    assert n == 3
    # header 完好(3 欄)
    assert fake_watchlist_ws.rows[0] == gsp._STOCK_WATCHLIST_HEADERS
    # 每列恰 3 欄:name / ticker / updated_at —— **無任何價格欄 / 哨兵值**
    for r in fake_watchlist_ws.rows[1:]:
        assert len(r) == 3, f'watchlist 列應為 3 欄(無價格),實得 {r}'
        assert r[0] == '觀察'
        assert 1.0 not in r and 1 not in r       # 無哨兵 1.0
        # 除 name/ticker/updated_at 外沒有任何 float(價格)
        assert not any(isinstance(v, float) for v in r)
    # ticker 大寫正規化
    assert [r[1] for r in fake_watchlist_ws.rows[1:]] == ['2330', '2454', '0050.TW']
    # load 回原代碼(順序一致、無 price 欄)
    assert gsp.load_stock_watchlist('觀察') == ['2330', '2454', '0050.TW']


def test_save_stock_watchlist_dedupes_preserves_order(fake_watchlist_ws):
    n = gsp.save_stock_watchlist('觀察', ['2330', '2330', '2454', ' 2330 '])
    assert n == 2
    assert gsp.load_stock_watchlist('觀察') == ['2330', '2454']


def test_save_stock_watchlist_overwrites_same_name():
    ws = _FakeWorksheet([
        gsp._STOCK_WATCHLIST_HEADERS,
        ['A', '2330', 'ts'],
        ['B', '2454', 'ts'],
    ])
    with patch.object(gsp, '_ws', return_value=ws):
        gsp.save_stock_watchlist('A', ['1101', '1102'])
        assert gsp.load_stock_watchlist('A') == ['1101', '1102']
        assert gsp.load_stock_watchlist('B') == ['2454']   # 其它 name 不受影響


# ── list distinct names ─────────────────────────────────────
def test_list_stock_watchlists_distinct_sorted():
    ws = _FakeWorksheet([
        gsp._STOCK_WATCHLIST_HEADERS,
        ['波段', '2330', 'ts'],
        ['波段', '2454', 'ts'],
        ['存股', '0056', 'ts'],
        ['', '9999', 'ts'],         # 空 name 略過
    ])
    with patch.object(gsp, '_ws', return_value=ws):
        assert gsp.list_stock_watchlists() == ['存股', '波段']


def test_list_stock_watchlists_empty(fake_watchlist_ws):
    assert gsp.list_stock_watchlists() == []


def test_load_stock_watchlist_missing_and_empty_name(fake_watchlist_ws):
    assert gsp.load_stock_watchlist('不存在') == []
    assert gsp.load_stock_watchlist('') == []
    assert gsp.load_stock_watchlist('   ') == []


def test_load_stock_watchlist_dedupes_skips_blank():
    ws = _FakeWorksheet([
        gsp._STOCK_WATCHLIST_HEADERS,
        ['觀察', '2330', 'ts'],
        ['觀察', '2454', 'ts'],
        ['觀察', '2330', 'ts'],      # 重複去除
        ['觀察', '', 'ts'],          # 空代碼略過
    ])
    with patch.object(gsp, '_ws', return_value=ws):
        assert gsp.load_stock_watchlist('觀察') == ['2330', '2454']


# ── 空 name / 空 tickers raise ──────────────────────────────
def test_save_stock_watchlist_empty_name(fake_watchlist_ws):
    with pytest.raises(ValueError, match='名稱'):
        gsp.save_stock_watchlist('', ['2330'])


def test_save_stock_watchlist_empty_tickers(fake_watchlist_ws):
    with pytest.raises(ValueError, match='代碼'):
        gsp.save_stock_watchlist('x', [])


def test_save_stock_watchlist_all_blank_tickers(fake_watchlist_ws):
    with pytest.raises(ValueError, match='代碼'):
        gsp.save_stock_watchlist('x', ['', '   '])


# ── 明確 sheet_id 路由到該 sheet(短路 legacy accessor)──────
def test_stock_watchlist_explicit_sheet_id_routes():
    client, opened = _fake_client_capturing()
    with patch.object(gsp, '_build_client', return_value=client), \
         patch.object(gsp, '_get_active_sheet_id',
                      return_value='LEGACY_SID') as _mock_legacy:
        gsp.save_stock_watchlist('g', ['2330'], sheet_id='STOCK_SID')
        gsp.list_stock_watchlists(sheet_id='STOCK_SID')
        gsp.load_stock_watchlist('g', sheet_id='STOCK_SID')
    assert set(opened) == {'STOCK_SID'}            # legacy sheet 完全沒被打開
    _mock_legacy.assert_not_called()               # 明確 sheet_id 短路 legacy accessor


# ── 動態 header-range 修正（3 欄 → A1:C1,不是死寫的 A1:E1）──
def test_dynamic_header_range_3col_watchlist():
    """§ bug fix:3 欄 watchlist 分頁的 header 更新範圍應為 A1:C1(非死寫 A1:E1)。"""
    ws, client = _mount_capturing_ws(first_row=[])   # header mismatch → 觸發 update
    with patch.object(gsp, '_build_client', return_value=client):
        gsp._get_worksheet(sheet_id='SID',
                           worksheet_name=gsp._STOCK_WATCHLIST_WORKSHEET,
                           headers=gsp._STOCK_WATCHLIST_HEADERS)
    assert ws.update_calls, 'header 不符應觸發 update'
    _rng, _vals = ws.update_calls[0]
    assert _rng == 'A1:C1'                            # 3 欄 → C,不是 E
    assert _vals == [gsp._STOCK_WATCHLIST_HEADERS]


def test_dynamic_header_range_5col_portfolios():
    """對照組:預設 portfolios(5 欄)仍為 A1:E1(既有行為不變)。"""
    ws, client = _mount_capturing_ws(first_row=[])
    with patch.object(gsp, '_build_client', return_value=client):
        gsp._get_worksheet(sheet_id='SID')           # 預設 portfolios + 5 headers
    _rng, _ = ws.update_calls[0]
    assert _rng == 'A1:E1'


def test_col_letter_helper():
    assert gsp._col_letter(3) == 'C'
    assert gsp._col_letter(5) == 'E'
    assert gsp._col_letter(1) == 'A'
    assert gsp._col_letter(26) == 'Z'
    with pytest.raises(ValueError):
        gsp._col_letter(27)
