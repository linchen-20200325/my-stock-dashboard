"""SEC-3 迴歸:未登入訪客**不得**經 Service Account 讀 / 寫任何 Google Sheet。

修前(實測 scratch repro):secrets 有 `[gcp_service_account]` 時,`_build_client()` 在 OAuth 不可用
就退回 SA ⇒ 匿名訪客帶 `?sheet=<任意 ID>`(app.py 會 setdefault 進兩個 session 通道),或什麼都不帶
(secrets 預設 Sheet),都能以 SA 身分讀到 SA 有權限的私人持股 / 觀察清單;新 UI 的
holdings_service 觀察清單那半、sector_flow_service 也走得到。
本檔釘住:沒有 OAuth 登入 ⇒ `LoginRequiredError`,且 `Credentials.from_service_account_info` /
`gspread.authorize` **從未被呼叫**;OAuth 使用者照常可讀且命中快取。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.data.portfolio import gsheet_portfolio as gsp

_PF = [gsp._HEADERS, ['私人組合', '2330', '5', '600', 't']]
_WL = [gsp._STOCK_WATCHLIST_HEADERS, ['私人清單', '2454', 't']]
_DATA = {sid: {gsp._WORKSHEET_NAME: _PF, gsp._STOCK_WATCHLIST_WORKSHEET: _WL}
         for sid in ('SID_VICTIM', 'SID_OWNER', 'SID_ME')}


class _WS:
    def __init__(self, rows):
        self.rows = rows

    def row_values(self, n):
        return list(self.rows[n - 1])

    def get_all_values(self):
        return [list(r) for r in self.rows]


class _SH:
    def __init__(self, sid):
        self.sid = sid

    def worksheet(self, name):
        return _WS(_DATA[self.sid][name])


class _Client:
    def __init__(self, who, calls):
        self.who, self.calls = who, calls

    def open_by_key(self, sid):
        self.calls.append((self.who, sid))
        return _SH(sid)


@pytest.fixture
def env():
    """匿名 + secrets 備齊 SA 與預設 Sheet;SA 建構路徑全部換成會記錄呼叫的 mock。"""
    calls: list[tuple[str, str]] = []
    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.secrets = {gsp.PORTFOLIO_SHEET_KEY: 'SID_OWNER',
                       'gcp_service_account': {'client_email': 'sa@p.iam.gserviceaccount.com',
                                               'private_key': 'x'}}
    sa_creds = MagicMock(side_effect=lambda *a, **k: object())
    authorize = MagicMock(side_effect=lambda _c: _Client('SA', calls))

    def _oauth_client():
        toks = fake_st.session_state.get('gsheet_tokens')
        return _Client('ME', calls) if toks else None

    gsp.clear_read_cache()
    with patch.object(gsp, 'st', fake_st), \
         patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
         patch('src.data.portfolio.oauth_state._get_oauth_client', side_effect=_oauth_client), \
         patch('gspread.authorize', authorize), \
         patch('google.oauth2.service_account.Credentials.from_service_account_info', sa_creds):
        fake_st.calls, fake_st.sa_creds, fake_st.authorize = calls, sa_creds, authorize
        yield fake_st
    gsp.clear_read_cache()


def _assert_no_sa(env):
    env.sa_creds.assert_not_called()
    env.authorize.assert_not_called()
    assert not any(who == 'SA' for who, _ in env.calls), env.calls


_READS = [
    lambda: gsp.list_portfolios(),
    lambda: gsp.list_portfolios(sheet_id='SID_VICTIM'),
    lambda: gsp.load_portfolio('私人組合'),
    lambda: gsp.load_portfolio('私人組合', sheet_id='SID_VICTIM', keep_blank=True),
    lambda: gsp.list_stock_watchlists(sheet_id='SID_VICTIM'),
    lambda: gsp.load_stock_watchlist('私人清單', sheet_id='SID_VICTIM'),
]
_WRITES = [
    lambda: gsp.save_portfolio('x', [{'ticker': '2330', 'lots': 1, 'avg_price': 1}]),
    lambda: gsp.save_stock_watchlist('x', ['2330'], sheet_id='SID_VICTIM'),
    lambda: gsp.add_to_stock_watchlist('x', ['2330'], sheet_id='SID_VICTIM'),
    lambda: gsp.delete_portfolio('私人組合'),
    lambda: gsp.delete_stock_watchlist('私人清單', sheet_id='SID_VICTIM'),
    lambda: gsp.append_forward_test_picks([{h: 'v' for h in gsp._FT_HEADERS}]),
    lambda: gsp.rename_sheet('新名字'),
]


@pytest.mark.parametrize('fn', _READS + _WRITES)
def test_anonymous_with_sa_secrets_every_read_write_refused(env, fn):
    with pytest.raises(gsp.LoginRequiredError, match='請先登入 Google'):
        fn()
    _assert_no_sa(env)


def test_login_required_is_runtime_error_with_ssot_message():
    assert issubclass(gsp.LoginRequiredError, RuntimeError)
    assert gsp.LOGIN_REQUIRED_MSG == '請先登入 Google 才能讀取持股'


def test_anonymous_drive_and_best_effort_helpers_never_use_sa(env):
    assert gsp.list_user_sheets() == []
    assert gsp.list_user_folders() == []
    assert gsp.get_sheet_title('SID_VICTIM') == ''
    assert gsp.load_forward_test_picks() == []
    with pytest.raises(RuntimeError):
        gsp.create_new_sheet('x')
    with pytest.raises(RuntimeError):
        gsp._get_or_create_app_folder('x')
    with pytest.raises(gsp.LoginRequiredError):
        gsp._build_client()
    _assert_no_sa(env)


def test_anonymous_query_sheet_session_keys_refused(env):
    """app.py `?sheet=` 還原把任意 ID setdefault 進兩個通道 —— 未登入照樣拒。"""
    env.session_state[gsp.PORTFOLIO_SHEET_KEY] = 'SID_VICTIM'
    env.session_state[gsp.STOCK_PORTFOLIO_SHEET_KEY] = 'SID_VICTIM'
    assert gsp.is_configured() is False
    with pytest.raises(gsp.LoginRequiredError):
        gsp.list_portfolios()
    with pytest.raises(gsp.LoginRequiredError):
        gsp.load_stock_watchlist('私人清單', sheet_id=gsp._get_active_stock_sheet_id())
    _assert_no_sa(env)


def test_anonymous_secrets_default_sheet_refused(env):
    assert gsp._get_active_sheet_id() == 'SID_OWNER'   # Sheet ID 預設仍在(它不是憑證)
    assert gsp.is_configured() is False
    with pytest.raises(gsp.LoginRequiredError):
        gsp.list_portfolios()
    _assert_no_sa(env)


def test_anonymous_cache_identity_empty_so_no_cache(env):
    assert gsp._cache_identity() == ''


def test_oauth_user_reads_and_hits_cache(env):
    env.session_state['gsheet_tokens'] = {'access_token': 'at', 'refresh_token': 'rt'}
    env.session_state[gsp.PORTFOLIO_SHEET_KEY] = 'SID_ME'
    assert gsp.is_configured() is True
    assert gsp.list_portfolios() == ['私人組合']
    assert gsp.list_portfolios() == ['私人組合']
    assert env.calls == [('ME', 'SID_ME')], '同身分第二次應命中快取'
    _assert_no_sa(env)


def test_oauth_client_none_with_sa_present_refused(env):
    env.session_state['gsheet_tokens'] = {'access_token': 'at', 'refresh_token': 'rt'}
    with patch('src.data.portfolio.oauth_state._get_oauth_client', return_value=None):
        with pytest.raises(gsp.LoginRequiredError):
            gsp.list_portfolios(sheet_id='SID_OWNER')
        with pytest.raises(gsp.LoginRequiredError):
            gsp.save_portfolio('x', [{'ticker': '2330', 'lots': 1, 'avg_price': 1}],
                               sheet_id='SID_OWNER')
    _assert_no_sa(env)


def test_orphaned_sa_symbols_removed():
    """v3 §01-2 收尾:隨 SA fallback 變成死碼的符號已刪(防有人加回半套)。"""
    for name in ('_sa_configured', '_IDENTITY_KIND_SA', '_CACHED_READ_KIND'):
        assert not hasattr(gsp, name), name


# ── L3:新 UI 的兩條路 ─────────────────────────────────────────────────────────
def test_holdings_service_anonymous_skips_watchlist_without_error(env):
    env.session_state[gsp.STOCK_PORTFOLIO_SHEET_KEY] = 'SID_VICTIM'
    from src.services import holdings_service as hs
    with patch('src.services.dividend_station_service.resolve_holding_names', lambda _x: None), \
         patch.object(gsp, 'list_stock_watchlists',
                      side_effect=AssertionError('未登入不得讀觀察清單')) as _lw, \
         patch.object(gsp, 'list_portfolios',
                      side_effect=AssertionError('未登入不得讀組合')) as _lp:
        r = hs.get_holdings(keep_blank=True)
    _lw.assert_not_called()
    _lp.assert_not_called()
    assert r.logged_in is False and r.bound is False
    assert r.holdings == ()
    assert r.watchlist_error == '', '未登入是「還沒做」,不是紅色錯誤(§1.A 第 4 點)'
    assert env.calls == []
    _assert_no_sa(env)


def test_holdings_service_logged_in_still_reads_watchlist(env):
    env.session_state['gsheet_tokens'] = {'access_token': 'at', 'refresh_token': 'rt'}
    env.session_state[gsp.PORTFOLIO_SHEET_KEY] = 'SID_ME'
    env.session_state[gsp.STOCK_PORTFOLIO_SHEET_KEY] = 'SID_ME'
    from src.services import holdings_service as hs
    with patch('src.services.dividend_station_service.resolve_holding_names', lambda _x: None):
        r = hs.get_holdings()
    assert r.logged_in is True and r.bound is True
    assert [h['ticker'] for h in r.holdings] == ['2330', '2454']
    assert r.watchlist_error == ''


def test_sector_flow_anonymous_returns_empty(env):
    from src.services import sector_flow_service as sf
    env.session_state[gsp.STOCK_PORTFOLIO_SHEET_KEY] = 'SID_VICTIM'
    assert sf._collect_stock_watchlist_tickers('SID_VICTIM') == []
    assert env.calls == []
    _assert_no_sa(env)
