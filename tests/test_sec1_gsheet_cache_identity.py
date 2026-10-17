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
def test_sa_cache_not_served_to_oauth_user(env):
    env.sa()
    assert gsp.list_portfolios(sheet_id='SID_SA') == ['SA組合']
    env.oauth('A')
    with pytest.raises(PermissionError):
        gsp.list_portfolios(sheet_id='SID_SA')
    assert ('A', 'SID_SA') in env.calls


def test_oauth_cache_not_served_to_sa_path(env):
    env.oauth('A')
    gsp.list_portfolios(sheet_id='SID_A')
    env.sa()
    with pytest.raises(PermissionError):
        gsp.list_portfolios(sheet_id='SID_A')
    assert ('SA', 'SID_A') in env.calls


def test_different_service_accounts_do_not_share(env):
    env.sa(email='sa1@p.iam.gserviceaccount.com')
    gsp.list_portfolios(sheet_id='SID_SA')
    env.sa(email='sa2@p.iam.gserviceaccount.com')
    gsp.list_portfolios(sheet_id='SID_SA')
    assert env.calls.count(('SA', 'SID_SA')) == 2


# ── 快取鍵不含 token 原文 ──────────────────────────────────────────────────────
def test_identity_key_has_no_raw_token(env):
    env.oauth('A', refresh='SECRET-REFRESH-123', access='SECRET-ACCESS-456')
    ident = gsp._cache_identity()
    assert ident.startswith('oauth:')
    assert 'SECRET' not in ident
    env.sa(email='sa@proj.iam.gserviceaccount.com')
    ident_sa = gsp._cache_identity()
    assert ident_sa.startswith('sa:') and 'sa@proj' not in ident_sa
    env.anon()
    assert gsp._cache_identity() == ''


def test_clear_read_cache_still_forces_refetch(env):
    env.oauth('A')
    gsp.list_portfolios(sheet_id='SID_A')
    gsp.clear_read_cache()
    gsp.list_portfolios(sheet_id='SID_A')
    assert env.calls == [('A', 'SID_A'), ('A', 'SID_A')]
