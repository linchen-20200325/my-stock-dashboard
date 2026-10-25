"""👤 我的 P1（DEC-083）—— L1 `gsheet_portfolio.read_sheet_title`（fail loud、快取分人分本）與
`session_binding_snapshot`（純讀）。

走**真** `st.cache_data`（同 `tests/test_sheet_safety_b5_cache.py`：只換掉 `gsp.st` 指向的 session_state，
Google client 用假的、不打網路），以「真的有沒有再去問 Google」（open_by_key 次數）判定快取行為。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.data.portfolio import gsheet_portfolio as gsp
from tests.sheet_safety_fakes import TripwireClient


class _APIError(Exception):
    """假的 gspread APIError（只需 `.code`；classify_read_error 以 isinstance 判 gspread 型別，故另 patch）。"""

    def __init__(self, code):
        super().__init__(f"api {code}")
        self.code = code


@pytest.fixture
def env():
    calls: list[tuple[str, str]] = []
    fake_st = MagicMock()
    fake_st.session_state = {}
    fake_st.secrets = {}
    behaviour: dict[str, object] = {}

    class _SH:
        def __init__(self, title):
            self.title = title

    class _Client:
        def __init__(self, who):
            self.who = who

        def open_by_key(self, sid):
            calls.append((self.who, sid))
            _b = behaviour.get(sid, "title-" + sid)
            if isinstance(_b, BaseException):
                raise _b
            return _SH(_b)

    class _Env:
        def login(self, who):
            fake_st.session_state = {'gsheet_tokens': {'who': who, 'access_token': f'at-{who}',
                                                      'refresh_token': f'rt-{who}'}}

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
        e.behaviour = behaviour
        e.st = fake_st
        yield e
    gsp.clear_read_cache()
    with gsp._READ_GEN_LOCK:
        gsp._READ_GEN.clear()


class TestReadSheetTitle:
    def test_ok_and_cached_per_person(self, env):
        env.login('A')
        assert gsp.read_sheet_title('SID1') == (gsp.READ_OK, 'title-SID1')
        assert gsp.read_sheet_title('SID1') == (gsp.READ_OK, 'title-SID1')
        assert env.n('A', 'SID1') == 1
        env.login('B')
        gsp.read_sheet_title('SID1')
        assert env.n('B', 'SID1') == 1, 'B 不得命中 A 的快取'

    @pytest.mark.parametrize("exc, code", [
        (PermissionError("no ACL"), gsp.READ_ERROR_PERMISSION_DENIED),
        (_APIError(404), gsp.READ_ERROR_SHEET_NOT_FOUND),
        (_APIError(403), gsp.READ_ERROR_PERMISSION_DENIED)])
    def test_403_404_become_cacheable_status(self, env, monkeypatch, exc, code):
        import gspread.exceptions as GE
        monkeypatch.setattr(GE, "APIError", _APIError)
        env.login('A')
        env.behaviour['SID1'] = exc
        assert gsp.read_sheet_title('SID1') == (code, '')
        assert gsp.read_sheet_title('SID1') == (code, '')
        assert env.n('A', 'SID1') == 1

    @pytest.mark.parametrize("exc", [ConnectionError("net"), TimeoutError("slow"), _APIError(429),
                                     ValueError("odd")])
    def test_other_errors_raise_and_are_not_cached(self, env, monkeypatch, exc):
        import gspread.exceptions as GE
        monkeypatch.setattr(GE, "APIError", _APIError)
        env.login('A')
        env.behaviour['SID1'] = exc
        for _ in range(2):
            with pytest.raises(type(exc)):
                gsp.read_sheet_title('SID1')
        assert env.n('A', 'SID1') == 2, '失敗不得進快取'

    def test_not_logged_in_raises_login_required(self, env):
        env.st.session_state = {}
        with pytest.raises(gsp.LoginRequiredError):
            gsp.read_sheet_title('SID1')

    @pytest.mark.parametrize("raw", ["", None, "e", "含 空白"])
    def test_bad_id_raises_and_never_falls_back_to_session(self, env, raw):
        env.login('A')
        env.st.session_state[gsp.PORTFOLIO_SHEET_KEY] = 'SESSION_SID'
        with pytest.raises(gsp.SheetNotConfiguredError):
            gsp.read_sheet_title(raw)
        assert env.n('A', 'SESSION_SID') == 0

    def test_reload_bumps_only_my_entry(self, env):
        env.login('A')
        gsp.read_sheet_title('SID1')
        gsp.read_sheet_title('SID2')
        gsp.invalidate_my_read_cache('SID1')
        gsp.read_sheet_title('SID1')
        gsp.read_sheet_title('SID2')
        assert (env.n('A', 'SID1'), env.n('A', 'SID2')) == (2, 1)

    def test_clear_read_cache_covers_title(self, env):
        env.login('A')
        gsp.read_sheet_title('SID1')
        gsp.clear_read_cache()
        gsp.read_sheet_title('SID1')
        assert env.n('A', 'SID1') == 2

    def test_old_get_sheet_title_still_swallows(self, env):
        """舊函式行為不動（`tests/test_sec3_no_anonymous_sa.py` 另有釘住）。"""
        env.login('A')
        env.behaviour['SID1'] = ConnectionError('x')
        assert gsp.get_sheet_title('SID1') == ''


def test_read_sheet_title_makes_zero_writes(monkeypatch):
    gsp.clear_read_cache()
    cli = TripwireClient({'SID': {gsp._WORKSHEET_NAME: [gsp._HEADERS]}})
    monkeypatch.setattr(gsp, '_build_client', lambda: cli)
    monkeypatch.setattr(gsp, '_cache_identity', lambda: '')
    status, _title = gsp.read_sheet_title('SID')
    assert status == gsp.READ_OK and cli.writes == [] and cli.opened
    gsp.clear_read_cache()


class TestSessionBindingSnapshot:
    def _st(self, monkeypatch, session=None, secrets=None):
        fake = MagicMock()
        fake.session_state = dict(session or {})
        fake.secrets = dict(secrets or {})
        monkeypatch.setattr(gsp, 'st', fake)
        return fake

    def test_reads_both_channels_and_default_sanitized(self, monkeypatch):
        self._st(monkeypatch, session={gsp.PORTFOLIO_SHEET_KEY: ' A1 ', gsp.STOCK_PORTFOLIO_SHEET_KEY: 'B<2>'},
                 secrets={gsp.PORTFOLIO_SHEET_KEY: 'DFLT'})
        snap = gsp.session_binding_snapshot()
        assert (snap.portfolio_channel, snap.stock_channel, snap.deploy_default) == ('A1', '', 'DFLT')

    def test_empty(self, monkeypatch):
        self._st(monkeypatch)
        assert gsp.session_binding_snapshot() == gsp.SessionBindingSnapshot()

    def test_missing_secrets_file_is_empty_default(self, monkeypatch):
        fake = self._st(monkeypatch, session={gsp.PORTFOLIO_SHEET_KEY: 'A1'})
        fake.secrets = MagicMock()
        fake.secrets.get.side_effect = FileNotFoundError('no secrets')
        assert gsp.session_binding_snapshot().deploy_default == ''

    def test_pure_read(self, monkeypatch):
        fake = self._st(monkeypatch, session={gsp.PORTFOLIO_SHEET_KEY: 'A1'})
        before = dict(fake.session_state)
        gsp.session_binding_snapshot()
        assert fake.session_state == before

    def test_no_streamlit(self, monkeypatch):
        monkeypatch.setattr(gsp, 'st', None)
        assert gsp.session_binding_snapshot() == gsp.SessionBindingSnapshot()
