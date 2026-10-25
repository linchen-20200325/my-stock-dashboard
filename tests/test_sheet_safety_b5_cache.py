"""Sheet Safety 批 B5（DEC-083）：「重新讀取」只失效**本人 × 那本 Sheet**，⛔ 不清全域快取。

走**真** `st.cache_data`（同 tests/test_sec1_gsheet_cache_identity.py 的作法：只換掉 `gsp.st` 這個名稱
指向的 session_state，Google client 用假的、不打網路），以「真的有沒有再去問 Google」（open_by_key 次數）判定。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.data.portfolio import gsheet_portfolio as gsp
from src.services import portfolio_binding_service as B

H, WH = gsp._HEADERS, gsp._STOCK_WATCHLIST_HEADERS

_BOOKS = {
    'A': {'SID_A1': [H, ['A1組合', '0050', '1', '1', 't']],
          'SID_A2': [H, ['A2組合', '0056', '1', '1', 't']]},
    'B': {'SID_B': [H, ['B組合', '2330', '1', '1', 't']]},
    'C': {'SID_A1': [H, ['A1組合', '0050', '1', '1', 't']]},   # C 也被分享到 A1
}


class _WS:
    def __init__(self, rows):
        self.rows = rows

    def get_all_values(self):
        return [list(r) for r in self.rows]


class _SH:
    def __init__(self, rows):
        self.rows = rows

    def worksheet(self, name):
        if name == gsp._STOCK_WATCHLIST_WORKSHEET:
            return _WS([WH, ['清單', '2454', 't']])
        return _WS(self.rows)


@pytest.fixture
def env():
    calls: list[tuple[str, str]] = []
    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.secrets = {}

    class _Client:
        def __init__(self, who):
            self.who = who

        def open_by_key(self, sid):
            calls.append((self.who, sid))
            if sid not in _BOOKS[self.who]:
                raise PermissionError('no ACL')
            return _SH(_BOOKS[self.who][sid])

    class _Env:
        def login(self, who, sheet=''):
            fake_st.session_state = {'gsheet_tokens': {'who': who, 'access_token': f'at-{who}',
                                                      'refresh_token': f'rt-{who}'}}
            if sheet:
                fake_st.session_state[gsp.PORTFOLIO_SHEET_KEY] = sheet
                fake_st.session_state[gsp.STOCK_PORTFOLIO_SHEET_KEY] = sheet

        def logout(self):
            fake_st.session_state = {}

        def n(self, who, sid):
            return calls.count((who, sid))

    gsp.clear_read_cache()
    with gsp._READ_GEN_LOCK:
        gsp._READ_GEN.clear()
    with patch.object(gsp, 'st', fake_st), \
         patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
         patch('src.data.portfolio.oauth_state._get_oauth_client',
               side_effect=lambda: _Client(fake_st.session_state['gsheet_tokens']['who'])):
        e = _Env()
        e.calls = calls
        yield e
    gsp.clear_read_cache()
    with gsp._READ_GEN_LOCK:
        gsp._READ_GEN.clear()


def _warm(env):
    """A 讀 A1 / A2、B 讀 B、C 讀 A1 各一次（全部進快取）。"""
    for who, sid in (('A', 'SID_A1'), ('A', 'SID_A2'), ('B', 'SID_B'), ('C', 'SID_A1')):
        env.login(who)
        gsp.list_portfolios(sheet_id=sid)
        gsp.load_portfolio(f'{sid[-2:]}組合' if who != 'B' else 'B組合', sheet_id=sid)
    # 再讀一次：全部命中快取（次數不變）
    _before = list(env.calls)
    for who, sid in (('A', 'SID_A1'), ('A', 'SID_A2'), ('B', 'SID_B'), ('C', 'SID_A1')):
        env.login(who)
        gsp.list_portfolios(sheet_id=sid)
    assert env.calls == _before, '前提：第二輪應全部命中快取'


def test_reload_refetches_only_my_active_sheet(env):
    _warm(env)
    env.login('A', sheet='SID_A1')
    assert B.reload_my_sheet_reads() == 1          # 兩通道同一本 ⇒ 去重成 1
    base = {k: env.n(*k) for k in (('A', 'SID_A1'), ('A', 'SID_A2'), ('B', 'SID_B'), ('C', 'SID_A1'))}
    gsp.list_portfolios(sheet_id='SID_A1')
    assert env.n('A', 'SID_A1') == base[('A', 'SID_A1')] + 1, 'A 重新讀取後，A 讀 A1 必須真的重抓'
    gsp.list_portfolios(sheet_id='SID_A2')
    assert env.n('A', 'SID_A2') == base[('A', 'SID_A2')], 'A 的另一本 Sheet 不受影響'
    env.login('B')
    gsp.list_portfolios(sheet_id='SID_B')
    assert env.n('B', 'SID_B') == base[('B', 'SID_B')], '別的使用者不受影響'
    env.login('C')
    gsp.list_portfolios(sheet_id='SID_A1')
    assert env.n('C', 'SID_A1') == base[('C', 'SID_A1')], '同一本 Sheet 的其他使用者不受影響'


def test_reload_explicit_sheet_ids(env):
    _warm(env)
    env.login('A')
    assert B.reload_my_sheet_reads('SID_A2') == 1
    n1, n2 = env.n('A', 'SID_A1'), env.n('A', 'SID_A2')
    gsp.list_portfolios(sheet_id='SID_A1')
    gsp.list_portfolios(sheet_id='SID_A2')
    assert (env.n('A', 'SID_A1'), env.n('A', 'SID_A2')) == (n1, n2 + 1)


def test_reload_never_calls_global_clear(env):
    _warm(env)
    env.login('A', sheet='SID_A1')
    _fns = (gsp._list_portfolios_cached, gsp._load_portfolio_cached,
            gsp._list_stock_watchlists_cached, gsp._load_stock_watchlist_cached)
    with patch.object(gsp, 'clear_read_cache') as _g, \
         patch.object(type(_fns[0]), 'clear', autospec=True) as _c:
        B.reload_my_sheet_reads()
    _g.assert_not_called()
    _c.assert_not_called()


def test_reload_covers_watchlist_reads_too(env):
    env.login('A', sheet='SID_A1')
    gsp.list_stock_watchlists(sheet_id='SID_A1')
    n = env.n('A', 'SID_A1')
    gsp.list_stock_watchlists(sheet_id='SID_A1')
    assert env.n('A', 'SID_A1') == n
    B.reload_my_sheet_reads()
    gsp.list_stock_watchlists(sheet_id='SID_A1')
    assert env.n('A', 'SID_A1') == n + 1


def test_reload_when_logged_out_is_noop(env):
    env.logout()
    assert B.reload_my_sheet_reads('SID_A1') == 0
    with gsp._READ_GEN_LOCK:
        assert gsp._READ_GEN == {}


def test_sheet_wide_invalidation_hits_every_user_of_that_sheet_only(env):
    _warm(env)
    base = {k: env.n(*k) for k in (('A', 'SID_A1'), ('A', 'SID_A2'), ('C', 'SID_A1'))}
    assert gsp.invalidate_sheet_read_cache('SID_A1') == 1
    env.login('A')
    gsp.list_portfolios(sheet_id='SID_A1')
    gsp.list_portfolios(sheet_id='SID_A2')
    env.login('C')
    gsp.list_portfolios(sheet_id='SID_A1')
    assert env.n('A', 'SID_A1') == base[('A', 'SID_A1')] + 1
    assert env.n('C', 'SID_A1') == base[('C', 'SID_A1')] + 1
    assert env.n('A', 'SID_A2') == base[('A', 'SID_A2')]


def test_generation_table_prunes_entries_older_than_ttl(monkeypatch):
    with gsp._READ_GEN_LOCK:
        gsp._READ_GEN.clear()
    t = [1000.0]
    monkeypatch.setattr(gsp.time, 'monotonic', lambda: t[0])
    gsp._bump_read_generation('fp-A', ['S1'])
    g1 = gsp._read_generation('fp-A', 'S1')
    assert g1 != '0.0'
    t[0] += gsp.TTL_15MIN + 1
    gsp._bump_read_generation('fp-B', ['S2'])
    with gsp._READ_GEN_LOCK:
        assert ('fp-A', 'S1') not in gsp._READ_GEN and ('fp-B', 'S2') in gsp._READ_GEN
    assert gsp._read_generation('fp-A', 'S1') == '0.0'
    gsp._bump_read_generation('fp-A', ['S1'])
    assert gsp._read_generation('fp-A', 'S1') not in ('0.0', g1), '計數器不重用舊世代'
    with gsp._READ_GEN_LOCK:
        gsp._READ_GEN.clear()


def test_read_gen_is_a_cache_key_param_not_underscored():
    """`read_gen` 必須進快取鍵：參數名不可加底線（st.cache_data 排除底線參數）。"""
    import inspect
    for fn in (gsp._list_portfolios_cached, gsp._load_portfolio_cached,
               gsp._list_stock_watchlists_cached, gsp._load_stock_watchlist_cached):
        _sig = inspect.signature(getattr(fn, '__wrapped__', fn))
        assert 'read_gen' in _sig.parameters, fn


def test_existing_global_clear_still_clears_everyone(env):
    """對照：既有的全域 `clear_read_cache()` 行為本批未改（寫入後 / 側欄 🔄 仍用它）。"""
    _warm(env)
    n = env.n('B', 'SID_B')
    gsp.clear_read_cache()
    env.login('B')
    gsp.list_portfolios(sheet_id='SID_B')
    assert env.n('B', 'SID_B') == n + 1
