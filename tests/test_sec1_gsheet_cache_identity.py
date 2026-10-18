"""SEC-1 迴歸:Google Sheet 讀取快取必須依「實際呼叫 Google 的身分」隔離。

根因(修前實測):`list_portfolios` / `load_portfolio` / `list_stock_watchlists` /
`load_stock_watchlist` 是 `@st.cache_data`(server 級、**跨 session 共用**),快取鍵只有
(name, sheet_id, keep_blank)—— 不含身分。A 讀過之後,B / 未登入者 / 失效 token 以相同參數
呼叫就直接命中 A 的快取,**完全不經 Google ACL 檢查**;`sheet_id=None` 時鍵甚至與 session 的
Sheet 無關。

本檔走**真** `st.cache_data`(只換掉 `gsp.st` 這個名稱指向的 session_state / secrets),
mock 掉 Google client(不打網路),每個 client 只認得自己身分有 ACL 的 Sheet。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.data.portfolio import gsheet_portfolio as gsp

_ROWS_A = [gsp._HEADERS, ['A組合', '0050', '3', '100', 't']]
_ROWS_B = [gsp._HEADERS, ['B組合', '2330', '1', '500', 't']]
_ROWS_SA = [gsp._HEADERS, ['SA組合', '00878', '9', '20', 't']]
_WL_A = [gsp._STOCK_WATCHLIST_HEADERS, ['A清單', '2454', 't']]

#: 身分 → {sheet_id: rows}:模擬 Google ACL(只有列出的 Sheet 讀得到)。
_ACL = {
    'A': {'SID_A': _ROWS_A},
    'B': {'SID_B': _ROWS_B},
    'SA': {'SID_SA': _ROWS_SA},
}
_WL_ACL = {'A': {'SID_A': _WL_A}}


class _WS:
    def __init__(self, rows):
        self.rows = rows

    def row_values(self, n):
        return list(self.rows[n - 1]) if n - 1 < len(self.rows) else []

    def get_all_values(self):
        return [list(r) for r in self.rows]


class _SH:
    def __init__(self, who, sid):
        self.who, self.sid = who, sid

    def worksheet(self, name):
        table = _WL_ACL if name == gsp._STOCK_WATCHLIST_WORKSHEET else _ACL
        return _WS(table[self.who][self.sid])


class _Client:
    def __init__(self, who, calls):
        self.who, self.calls = who, calls

    def open_by_key(self, sid):
        self.calls.append((self.who, sid))
        if sid not in _ACL.get(self.who, {}):
            raise PermissionError(f'{self.who} 對 {sid} 沒有 ACL')
        return _SH(self.who, sid)


@pytest.fixture
def env():
    """切換「目前是哪個 session」的環境:真 cache_data + 假 session_state / secrets / client。"""
    calls: list[tuple[str, str]] = []
    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.secrets = {}

    def _oauth_client():
        toks = fake_st.session_state.get('gsheet_tokens') or {}
        if toks.get('revoked'):
            raise RuntimeError('invalid_grant: token 已失效')
        return _Client(toks['who'], calls)

    class _Env:
        def oauth(self, who, *, refresh='', access='', sheet='', revoked=False):
            toks = {'who': who, 'access_token': access or f'at-{who}'}
            if refresh is not None:
                toks['refresh_token'] = refresh or f'rt-{who}'
            if revoked:
                toks['revoked'] = True
            fake_st.session_state = {'gsheet_tokens': toks}
            if sheet:
                fake_st.session_state[gsp.PORTFOLIO_SHEET_KEY] = sheet
            fake_st.secrets = {}

        def sa(self, *, email='sa@proj.iam.gserviceaccount.com', sheet='SID_SA'):
            fake_st.session_state = {}
            fake_st.secrets = {gsp.PORTFOLIO_SHEET_KEY: sheet,
                               'gcp_service_account': {'client_email': email,
                                                       'project_id': 'proj'}}

        def anon(self, *, sheet=''):
            fake_st.session_state = {gsp.PORTFOLIO_SHEET_KEY: sheet} if sheet else {}
            fake_st.secrets = {}

    gsp.clear_read_cache()
    with patch.object(gsp, 'st', fake_st), \
         patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
         patch('src.data.portfolio.oauth_state._get_oauth_client', side_effect=_oauth_client), \
         patch('gspread.authorize', side_effect=lambda _c: _Client('SA', calls)), \
         patch('google.oauth2.service_account.Credentials.from_service_account_info',
               return_value=object()):
        e = _Env()
        e.calls = calls
        yield e
    gsp.clear_read_cache()


# ── A 的資料不會被 B 取得 ────────────────────────────────────────────────────
def test_user_b_cannot_read_user_a_cached_portfolio(env):
    env.oauth('A')
    assert gsp.load_portfolio('A組合', sheet_id='SID_A')[0]['ticker'] == '0050'
    env.oauth('B')
    with pytest.raises(PermissionError):
        gsp.load_portfolio('A組合', sheet_id='SID_A')
    assert ('B', 'SID_A') in env.calls, 'B 必須真的去問 Google(由 ACL 決定),不可吃 A 的快取'


def test_user_b_cannot_list_user_a_cached_names(env):
    env.oauth('A')
    assert gsp.list_portfolios(sheet_id='SID_A') == ['A組合']
    env.oauth('B')
    with pytest.raises(PermissionError):
        gsp.list_portfolios(sheet_id='SID_A')


def test_user_b_cannot_read_user_a_cached_watchlist(env):
    env.oauth('A')
    assert gsp.list_stock_watchlists(sheet_id='SID_A') == ['A清單']
    assert gsp.load_stock_watchlist('A清單', sheet_id='SID_A') == ['2454']
    env.oauth('B')
    with pytest.raises(PermissionError):
        gsp.list_stock_watchlists(sheet_id='SID_A')
    with pytest.raises(PermissionError):
        gsp.load_stock_watchlist('A清單', sheet_id='SID_A')


def test_sheet_id_none_follows_each_sessions_own_sheet(env):
    """sheet_id=None(走 session 的 active sheet):B 拿到的是 B 自己那本,不是 A 的。"""
    env.oauth('A', sheet='SID_A')
    assert gsp.list_portfolios() == ['A組合']
    env.oauth('B', sheet='SID_B')
    assert gsp.list_portfolios() == ['B組合']


# ── 同一使用者重複呼叫命中快取(Google 只被呼叫一次)───────────────────────────
def test_same_user_repeat_hits_cache(env):
    env.oauth('A')
    r1 = gsp.load_portfolio('A組合', sheet_id='SID_A')
    r2 = gsp.load_portfolio('A組合', sheet_id='SID_A')
    assert r1 == r2
    assert env.calls == [('A', 'SID_A')], '同身分同參數第二次應命中快取(429 根治不可退化)'


def test_same_user_after_access_token_refresh_still_hits_cache(env):
    """refresh 後 access_token 變了、refresh_token 不變 → 仍是同一身分,命中快取。"""
    env.oauth('A', access='at-old')
    gsp.list_portfolios(sheet_id='SID_A')
    env.oauth('A', access='at-new')
    gsp.list_portfolios(sheet_id='SID_A')
    assert env.calls == [('A', 'SID_A')]


# ── 未登入 / 失效授權不會取得他人快取 ───────────────────────────────────────────
def test_anonymous_cannot_read_cached_data(env):
    env.oauth('A')
    gsp.load_portfolio('A組合', sheet_id='SID_A')
    env.anon(sheet='SID_A')
    with pytest.raises(RuntimeError):
        gsp.load_portfolio('A組合', sheet_id='SID_A')
    with pytest.raises(RuntimeError):
        gsp.list_portfolios(sheet_id='SID_A')
    with pytest.raises(RuntimeError):
        gsp.list_portfolios()


def test_revoked_token_of_other_user_cannot_read_cached_data(env):
    env.oauth('A')
    gsp.load_portfolio('A組合', sheet_id='SID_A')
    env.oauth('X', revoked=True)
    with pytest.raises(RuntimeError, match='invalid_grant'):
        gsp.load_portfolio('A組合', sheet_id='SID_A')


def test_tokens_without_any_credential_bypass_cache(env):
    """token dict 既無 refresh_token 也無 access_token → 無法定身分 → 不得命中任何快取。"""
    env.oauth('A')
    gsp.list_portfolios(sheet_id='SID_A')
    env.oauth('A', refresh=None, access='')
    gsp.st.session_state['gsheet_tokens'].pop('access_token')
    gsp.st.session_state['gsheet_tokens']['revoked'] = True
    with pytest.raises(RuntimeError):
        gsp.list_portfolios(sheet_id='SID_A')


# ── SA 與 OAuth 身分不共用快取 ─────────────────────────────────────────────────
# SEC-3(有意識的改寫,不是漏測):修前 SA 是一種可讀的身分(有自己的 `sa:` 快取鍵);
# 現在網頁端沒有 SA 路徑 —— 「SA 環境」＝匿名 ＋ SA secrets,一律 LoginRequiredError、
# 從不以 SA 身分呼叫 Google。下列三條改釘這個新語意(快取仍不會在 OAuth / 匿名之間流動)。
def test_sa_secrets_anonymous_refused_then_oauth_user_goes_to_google(env):
    env.sa()
    with pytest.raises(gsp.LoginRequiredError):
        gsp.list_portfolios(sheet_id='SID_SA')
    env.oauth('A')
    with pytest.raises(PermissionError):
        gsp.list_portfolios(sheet_id='SID_SA')
    assert ('A', 'SID_SA') in env.calls
    assert not any(who == 'SA' for who, _ in env.calls)


def test_oauth_cache_not_served_to_anonymous_sa_env(env):
    env.oauth('A')
    gsp.list_portfolios(sheet_id='SID_A')
    env.sa()
    with pytest.raises(gsp.LoginRequiredError):
        gsp.list_portfolios(sheet_id='SID_A')
    assert not any(who == 'SA' for who, _ in env.calls)


def test_service_accounts_never_read(env):
    env.sa(email='sa1@p.iam.gserviceaccount.com')
    with pytest.raises(gsp.LoginRequiredError):
        gsp.list_portfolios(sheet_id='SID_SA')
    env.sa(email='sa2@p.iam.gserviceaccount.com')
    with pytest.raises(gsp.LoginRequiredError):
        gsp.list_portfolios(sheet_id='SID_SA')
    assert ('SA', 'SID_SA') not in env.calls


# ── 快取鍵不含 token 原文 ──────────────────────────────────────────────────────
def test_identity_key_has_no_raw_token(env):
    env.oauth('A', refresh='SECRET-REFRESH-123', access='SECRET-ACCESS-456')
    ident = gsp._cache_identity()
    assert ident.startswith('oauth:')
    assert 'SECRET' not in ident
    env.sa(email='sa@proj.iam.gserviceaccount.com')
    assert gsp._cache_identity() == '', 'SEC-3:沒有 SA 身分(匿名 + SA secrets → 不用快取)'
    env.anon()
    assert gsp._cache_identity() == ''


def test_clear_read_cache_still_forces_refetch(env):
    env.oauth('A')
    gsp.list_portfolios(sheet_id='SID_A')
    gsp.clear_read_cache()
    gsp.list_portfolios(sheet_id='SID_A')
    assert env.calls == [('A', 'SID_A'), ('A', 'SID_A')]


# ── SA2 SHOULD-2:`_get_oauth_client()` 回 None → `_build_client` 會退回 SA ──────────
# 修前:快取鍵是 B 的 `oauth:` 指紋,實際卻用 SA 讀 → SA 能讀、B 本人(OAuth)讀不到的資料
# 被存進 B 的 oauth 鍵,B 之後 OAuth 恢復時 15 分鐘內會從快取拿到「SA 身分讀到的資料」。
# 修後:快取路徑內身分種類被釘住,OAuth 鍵下**拒絕** SA fallback(fail loud,例外不入快取)。
def test_oauth_identity_never_caches_sa_fallback_read(env):
    env.sa()                                    # SA 備齊(能讀 SID_SA)
    env.oauth('B')                               # B 已登入 OAuth(B 沒有 SID_SA 的 ACL)
    gsp.st.secrets = {gsp.PORTFOLIO_SHEET_KEY: 'SID_SA',
                      'gcp_service_account': {'client_email': 'sa@p.iam.gserviceaccount.com'}}
    with patch('src.data.portfolio.oauth_state._get_oauth_client', return_value=None):
        with pytest.raises(gsp.LoginRequiredError):
            gsp.list_portfolios(sheet_id='SID_SA')
    assert ('SA', 'SID_SA') not in env.calls, 'oauth 鍵之下不可改用 SA 讀資料'
    # OAuth 恢復後 B 必須重新經 Google ACL(被拒),不得命中 SA 讀到的資料
    with pytest.raises(PermissionError):
        gsp.list_portfolios(sheet_id='SID_SA')
    # 另一位使用者 C 也不會拿到任何東西
    env.oauth('C')
    with pytest.raises(PermissionError):
        gsp.list_portfolios(sheet_id='SID_SA')


def test_no_sa_fallback_outside_cache_path_either(env):
    """SEC-3(有意識的改寫):修前非快取路徑(寫入 / 列檔)的 `_build_client` 會 OAuth→SA fallback;
    現在 OAuth client 建不起來一律 LoginRequiredError,不論在不在快取路徑。"""
    env.sa()
    env.oauth('B')
    gsp.st.secrets = {gsp.PORTFOLIO_SHEET_KEY: 'SID_SA',
                      'gcp_service_account': {'client_email': 'sa@p.iam.gserviceaccount.com'}}
    with patch('src.data.portfolio.oauth_state._get_oauth_client', return_value=None):
        with pytest.raises(gsp.LoginRequiredError):
            gsp._build_client()
    assert not any(who == 'SA' for who, _ in env.calls)


# ── SA1 SHOULD-2:走真實 save_* / delete_* 路徑,同一使用者寫完再讀是新值 ──────────
@pytest.fixture
def fake_sheets():
    from tests.test_gsheet_portfolio import _FakeWorksheet
    sheets = {
        gsp._WORKSHEET_NAME: _FakeWorksheet([gsp._HEADERS,
                                             ['舊組', '0050', 1, 100, 't']]),
        gsp._STOCK_WATCHLIST_WORKSHEET: _FakeWorksheet([gsp._STOCK_WATCHLIST_HEADERS,
                                                        ['舊清單', '2330', 't']]),
    }
    calls = {'n': 0}

    def _ws(*, sheet_id=None, worksheet_name=gsp._WORKSHEET_NAME, headers=gsp._HEADERS):
        calls['n'] += 1
        return sheets[worksheet_name]
    gsp.clear_read_cache()
    with patch.object(gsp, '_ws', side_effect=_ws), \
         patch.object(gsp, '_cache_identity', return_value='oauth:same-user'):
        yield calls
    gsp.clear_read_cache()


def test_save_then_read_sees_new_value_same_user(fake_sheets):
    assert gsp.list_portfolios(sheet_id='S') == ['舊組']
    assert gsp.load_portfolio('舊組', sheet_id='S')[0]['lots'] == 1
    _n = fake_sheets['n']
    assert gsp.list_portfolios(sheet_id='S') == ['舊組']
    assert fake_sheets['n'] == _n, '先確認確實有快取(否則下面的「讀到新值」是空轉)'
    gsp.save_portfolio('舊組', [{'ticker': '0050', 'lots': 7, 'avg_price': 100}], sheet_id='S')
    gsp.save_portfolio('新組', [{'ticker': '2330', 'lots': 2, 'avg_price': 500}], sheet_id='S')
    assert gsp.load_portfolio('舊組', sheet_id='S')[0]['lots'] == 7
    assert gsp.list_portfolios(sheet_id='S') == ['新組', '舊組']
    gsp.delete_portfolio('新組', sheet_id='S')
    assert gsp.list_portfolios(sheet_id='S') == ['舊組']


def test_watchlist_save_delete_then_read_sees_new_value_same_user(fake_sheets):
    assert gsp.load_stock_watchlist('舊清單', sheet_id='S') == ['2330']
    assert gsp.list_stock_watchlists(sheet_id='S') == ['舊清單']
    gsp.save_stock_watchlist('舊清單', ['2330', '2454'], sheet_id='S')
    assert gsp.load_stock_watchlist('舊清單', sheet_id='S') == ['2330', '2454']
    gsp.add_to_stock_watchlist('新清單', ['1101'], sheet_id='S')
    assert gsp.list_stock_watchlists(sheet_id='S') == ['新清單', '舊清單']
    gsp.delete_stock_watchlist('新清單', sheet_id='S')
    assert gsp.list_stock_watchlists(sheet_id='S') == ['舊清單']
