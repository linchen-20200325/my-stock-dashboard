"""gsheet_portfolio.py 單元測試 — mock gspread client 不打真 API。"""
from unittest.mock import MagicMock, patch

import pytest

from src.data.portfolio import gsheet_portfolio as gsp


@pytest.fixture(autouse=True)
def _clear_read_cache():
    """每測試前後清 L1 讀取快取 —— 防 @st.cache_data 跨測試殘留污染（429 根治的副作用）。"""
    gsp.clear_read_cache()
    yield
    gsp.clear_read_cache()


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


# ── delete_stock_watchlist（新補：個股端原缺刪除能力）──────────────────
def _stock_ws(rows):
    return _FakeWorksheet([gsp._STOCK_WATCHLIST_HEADERS] + rows)


def test_delete_stock_watchlist_existing():
    ws = _stock_ws([
        ['清單A', '2330', 'ts'], ['清單A', '2454', 'ts'], ['清單B', '0050', 'ts'],
    ])
    with patch.object(gsp, '_ws', return_value=ws):
        n = gsp.delete_stock_watchlist('清單A')
    assert n == 2
    assert ws.rows[0] == gsp._STOCK_WATCHLIST_HEADERS
    assert ws.rows[1:] == [['清單B', '0050', 'ts']]   # 只剩清單B,不誤刪


def test_delete_stock_watchlist_missing():
    ws = _stock_ws([['清單A', '2330', 'ts']])
    with patch.object(gsp, '_ws', return_value=ws):
        assert gsp.delete_stock_watchlist('不存在') == 0
    assert ws.rows[1:] == [['清單A', '2330', 'ts']]   # 原資料不變


def test_delete_stock_watchlist_empty_name():
    ws = _stock_ws([['清單A', '2330', 'ts']])
    with patch.object(gsp, '_ws', return_value=ws):
        assert gsp.delete_stock_watchlist('') == 0


def test_delete_stock_watchlist_empty_sheet():
    ws = _stock_ws([])
    with patch.object(gsp, '_ws', return_value=ws):
        assert gsp.delete_stock_watchlist('x') == 0


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


# ══ Phase 2: 個股 新建 Sheet 放進專屬 Drive 資料夾（drive.file scope only）══════
class _FakeResp:
    """模擬 requests.Response：只需 .json() 回預設 payload。"""
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeHTTPClient:
    """記錄每次 request(method, endpoint, params=, json=)；依序列回應。

    routes: 依 method 給 payload —— 'get_search'（q 查資料夾）/ 'post'（建資料夾）
    / 'get_parents'（?fields=parents）/ 'patch'（搬移）。
    """
    def __init__(self, *, search_files=None, new_folder_id=None,
                 cur_parents=None, fail_on=None):
        self.calls: list[dict] = []
        self._search_files = search_files if search_files is not None else []
        self._new_folder_id = new_folder_id
        self._cur_parents = cur_parents if cur_parents is not None else []
        self._fail_on = fail_on   # e.g. 'patch' / 'post' / 'get_search'

    def request(self, method, endpoint, params=None, json=None,
                data=None, files=None, headers=None):
        # 分類這次呼叫
        is_files_root = endpoint.endswith('/drive/v3/files')
        q = (params or {}).get('q', '')
        if method == 'get' and is_files_root and 'folder' in q:
            kind = 'get_search'
        elif method == 'post' and is_files_root:
            kind = 'post'
        elif method == 'get' and not is_files_root:
            kind = 'get_parents'
        elif method == 'patch':
            kind = 'patch'
        else:
            kind = 'other'
        self.calls.append({'kind': kind, 'method': method, 'endpoint': endpoint,
                           'params': params, 'json': json})
        if self._fail_on and kind == self._fail_on:
            # 模擬真實 Drive API 失敗（網路 / requests 例外，非 RuntimeError）
            raise ConnectionError(f'boom on {kind}')
        if kind == 'get_search':
            return _FakeResp({'files': list(self._search_files)})
        if kind == 'post':
            return _FakeResp({'id': self._new_folder_id})
        if kind == 'get_parents':
            return _FakeResp({'parents': list(self._cur_parents)})
        if kind == 'patch':
            return _FakeResp({'id': 'SHEET_X', 'parents': ['FID']})
        return _FakeResp({})


def _fake_client_with_http(http):
    client = MagicMock()
    client.http_client = http
    return client


# ── _get_or_create_app_folder ───────────────────────────────
def test_get_or_create_folder_found_returns_existing_no_create():
    """命中同名資料夾 → 回既有 id，且**不**發 POST（不重複建立）。"""
    http = _FakeHTTPClient(search_files=[{'id': 'FID_EXISTING', 'name': 'X'}])
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client',
                      return_value=_fake_client_with_http(http)):
        fid = gsp._get_or_create_app_folder('台股 Dashboard（個股組合）')
    assert fid == 'FID_EXISTING'
    kinds = [c['kind'] for c in http.calls]
    assert kinds == ['get_search']          # 只有查詢，無 POST
    assert 'post' not in kinds


def test_get_or_create_folder_not_found_creates_and_returns_new_id():
    """查無同名 → 發 POST 建立，回新 id。"""
    http = _FakeHTTPClient(search_files=[], new_folder_id='FID_NEW')
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client',
                      return_value=_fake_client_with_http(http)):
        fid = gsp._get_or_create_app_folder('台股 Dashboard（個股組合）')
    assert fid == 'FID_NEW'
    kinds = [c['kind'] for c in http.calls]
    assert kinds == ['get_search', 'post']
    # POST body 帶正確 name + folder mimeType
    post_call = http.calls[1]
    assert post_call['json']['name'] == '台股 Dashboard（個股組合）'
    assert post_call['json']['mimeType'] == 'application/vnd.google-apps.folder'


def test_get_or_create_folder_escapes_single_quote_in_q():
    """名稱含單引號 → q 字串內以 \\' 轉義（防查詢語法破壞）。"""
    http = _FakeHTTPClient(search_files=[{'id': 'FID', 'name': "a'b"}])
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client',
                      return_value=_fake_client_with_http(http)):
        gsp._get_or_create_app_folder("a'b")
    q = http.calls[0]['params']['q']
    assert "name='a\\'b'" in q


def test_get_or_create_folder_requires_oauth():
    with patch.object(gsp, '_has_oauth_tokens', return_value=False):
        with pytest.raises(RuntimeError, match='登入'):
            gsp._get_or_create_app_folder('X')


def test_get_or_create_folder_api_failure_raises():
    """§1 fail-loud：Drive API 失敗 → RuntimeError（不回假 id）。"""
    http = _FakeHTTPClient(search_files=[], fail_on='get_search')
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client',
                      return_value=_fake_client_with_http(http)):
        with pytest.raises(RuntimeError, match='資料夾建立/查詢失敗'):
            gsp._get_or_create_app_folder('X')


def test_get_or_create_folder_post_no_id_raises():
    """POST 回應無 id → §1 fail-loud RuntimeError（不回假 id）。"""
    http = _FakeHTTPClient(search_files=[], new_folder_id=None)
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client',
                      return_value=_fake_client_with_http(http)):
        with pytest.raises(RuntimeError, match='未取得 id'):
            gsp._get_or_create_app_folder('X')


# ── create_new_sheet(folder_name=...) ───────────────────────
def _sheet_stub(sheet_id='SHEET_X'):
    sh = MagicMock()
    sh.id = sheet_id
    sh.url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/edit'
    return sh


def test_create_new_sheet_default_no_folder_calls():
    """folder_name=None（預設）→ 行為與舊版相同：只 create，無任何 Drive 資料夾呼叫。"""
    http = _FakeHTTPClient()
    client = _fake_client_with_http(http)
    client.create.return_value = _sheet_stub()
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client', return_value=client):
        sid, url = gsp.create_new_sheet('台股 Dashboard - 投資組合')
    assert sid == 'SHEET_X'
    assert url.endswith('/SHEET_X/edit')
    assert http.calls == []                 # 完全沒碰 Drive 資料夾 API


def test_create_new_sheet_with_folder_moves_sheet_into_folder():
    """folder_name 非空 → 先 create Sheet，再 addParents 搬入資料夾。"""
    http = _FakeHTTPClient(search_files=[{'id': 'FID', 'name': 'X'}],
                           cur_parents=['ROOT_ID'])
    client = _fake_client_with_http(http)
    client.create.return_value = _sheet_stub('SHEET_X')
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client', return_value=client):
        sid, url = gsp.create_new_sheet('個股組合',
                                        folder_name='台股 Dashboard（個股組合）')
    assert sid == 'SHEET_X'
    kinds = [c['kind'] for c in http.calls]
    # 搜資料夾 → 取現有 parents → PATCH 搬移
    assert kinds == ['get_search', 'get_parents', 'patch']
    patch_call = http.calls[-1]
    assert patch_call['endpoint'].endswith('/SHEET_X')
    assert patch_call['params']['addParents'] == 'FID'
    assert patch_call['params']['removeParents'] == 'ROOT_ID'


def test_create_new_sheet_folder_step_best_effort_still_returns_sheet():
    """§1 best-effort：搬移（PATCH）失敗 → 仍回傳已建立的 Sheet（永不遺失）。"""
    http = _FakeHTTPClient(search_files=[{'id': 'FID', 'name': 'X'}],
                           cur_parents=['ROOT_ID'], fail_on='patch')
    client = _fake_client_with_http(http)
    client.create.return_value = _sheet_stub('SHEET_X')
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client', return_value=client):
        sid, url = gsp.create_new_sheet('個股組合',
                                        folder_name='台股 Dashboard（個股組合）')
    # 搬移失敗被吞（best-effort log），Sheet id/url 完好回傳
    assert sid == 'SHEET_X'
    assert url.endswith('/SHEET_X/edit')


def test_create_new_sheet_folder_lookup_failure_best_effort():
    """§1 best-effort：連資料夾查詢都失敗 → 仍回傳 Sheet（不炸、不 orphan）。"""
    http = _FakeHTTPClient(fail_on='get_search')
    client = _fake_client_with_http(http)
    client.create.return_value = _sheet_stub('SHEET_X')
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client', return_value=client):
        sid, url = gsp.create_new_sheet('個股組合',
                                        folder_name='台股 Dashboard（個股組合）')
    assert sid == 'SHEET_X'


def test_create_new_sheet_empty_folder_name_treated_as_root():
    """folder_name='' / 空白 → 視同 None，走根目錄（不觸發資料夾流程）。"""
    http = _FakeHTTPClient()
    client = _fake_client_with_http(http)
    client.create.return_value = _sheet_stub()
    with patch.object(gsp, '_has_oauth_tokens', return_value=True), \
         patch.object(gsp, '_build_client', return_value=client):
        gsp.create_new_sheet('t', folder_name='   ')
    assert http.calls == []


def test_stock_drive_folder_name_constant():
    """§3.3 專屬資料夾名為具名常數。"""
    assert gsp._STOCK_DRIVE_FOLDER_NAME == '台股 Dashboard（個股組合）'


# ══ 429 根治:讀取快取(TTL_15MIN)+寫入即清 ═══════════════════════════════════
def test_read_cache_hit_avoids_refetch():
    """同參數第二次讀取命中快取,不再打 _ws(降 Sheets API,根治 429/每分鐘配額)。"""
    ws = _FakeWorksheet([gsp._HEADERS, ['A', '0050.TW', 1, 100, 'ts']])
    calls = {'n': 0}

    def _counting_ws(**kwargs):
        calls['n'] += 1
        return ws
    with patch.object(gsp, '_ws', side_effect=_counting_ws):
        r1 = gsp.list_portfolios(sheet_id='SID_X')
        r2 = gsp.list_portfolios(sheet_id='SID_X')
    assert r1 == r2 == ['A']
    assert calls['n'] == 1, '第二次應命中快取,不重打 _ws（否則 429 沒根治）'


def test_clear_read_cache_forces_refetch():
    """clear_read_cache() → 下次讀取重抓（手動刷新 / 寫入後失效的機制）。"""
    ws = _FakeWorksheet([gsp._HEADERS, ['A', '0050.TW', 1, 100, 'ts']])
    calls = {'n': 0}

    def _counting_ws(**kwargs):
        calls['n'] += 1
        return ws
    with patch.object(gsp, '_ws', side_effect=_counting_ws):
        gsp.list_portfolios(sheet_id='SID_Y')
        gsp.clear_read_cache()
        gsp.list_portfolios(sheet_id='SID_Y')
    assert calls['n'] == 2, 'clear 後應重抓'


def test_save_portfolio_clears_read_cache(populated_ws):
    """§1:save 後讀取快取自動失效 → 使用者自己存的新組合立刻看得到,不服務髒快取。"""
    assert '攻擊組合' in gsp.list_portfolios()          # 先讀進快取
    gsp.save_portfolio('新組', [{'ticker': '2330', 'lots': 1, 'avg_price': 100}])
    assert '新組' in gsp.list_portfolios()              # save 已清快取 → 看得到新組


def test_save_stock_watchlist_clears_read_cache(fake_watchlist_ws):
    """§1:save watchlist 後讀取快取自動失效。"""
    gsp.list_stock_watchlists()                         # 先讀進快取(空)
    gsp.save_stock_watchlist('觀察', ['2330', '2454'])
    assert '觀察' in gsp.list_stock_watchlists()        # 清快取後看得到


# ── #33：add_to_stock_watchlist 併入(聯集去重保序,不覆蓋)────────────────────
def test_add_to_stock_watchlist_merges_dedup():
    ws = _FakeWorksheet([gsp._STOCK_WATCHLIST_HEADERS,
                         ["觀察", "2330", "ts"], ["觀察", "2454", "ts"]])
    with patch.object(gsp, "_ws", return_value=ws):
        n = gsp.add_to_stock_watchlist("觀察", ["2454", "1101", "2330"])   # 2454/2330 已在
        assert n == 3                                     # 去重後 2330,2454,1101
        assert gsp.load_stock_watchlist("觀察") == ["2330", "2454", "1101"]  # 保序,新增在後


def test_add_to_stock_watchlist_new_name_from_empty():
    ws = _FakeWorksheet([gsp._STOCK_WATCHLIST_HEADERS])
    with patch.object(gsp, "_ws", return_value=ws):
        n = gsp.add_to_stock_watchlist("新池", ["2330", "2330", "2454"])   # 同名去重
        assert n == 2
        assert gsp.load_stock_watchlist("新池") == ["2330", "2454"]


def test_add_to_stock_watchlist_empty_raises():
    ws = _FakeWorksheet([gsp._STOCK_WATCHLIST_HEADERS])
    with patch.object(gsp, "_ws", return_value=ws):
        with pytest.raises(ValueError):
            gsp.add_to_stock_watchlist("", ["2330"])
        with pytest.raises(ValueError):
            gsp.add_to_stock_watchlist("x", [])
