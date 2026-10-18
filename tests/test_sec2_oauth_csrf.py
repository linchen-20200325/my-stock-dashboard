"""SEC-2 迴歸:OAuth callback 的 login CSRF 防護(server 端一次性 nonce ＋ 綁定發起瀏覽器)。

修前(實測 scratch AppTest):`?code=ATTACKER_CODE&state=<任意 / 空 / 不帶>` 三種都被吞下,
受害者 session 被登入成攻擊者帳號(`_oauth_state_ok` 在 session 沒有期望值時放行,
而 Google 轉跳回來是整頁載入 ⇒ 新 session ⇒ 期望值恆為空)。
本檔釘住:唯一成功路徑 = `oauth_nonce_store.consume()` ok;失敗時清 query params、
顯示中文錯誤、**不** rerun、**不**換 token(不會迴圈);安全閥 `oauth_csrf_enforce=false`。
"""
from __future__ import annotations

import hashlib
import os

import pytest

import src.data.portfolio.oauth_nonce_store as ns
import src.data.portfolio.oauth_state as ost
from shared.oauth_csrf_policy import OAUTH_CSRF_ENFORCE_SECRET_KEY, OAUTH_STATE_TTL_SEC

_VICTIM = hashlib.sha256(b'victim-browser').hexdigest()
_ATTACKER = hashlib.sha256(b'attacker-browser').hexdigest()


@pytest.fixture(autouse=True)
def _fresh_store():
    ns._STORE.clear()
    ns._EXPIRED.clear()
    yield
    ns._STORE.clear()
    ns._EXPIRED.clear()


class _Rerun(Exception):
    pass


class _QP(dict):
    def clear(self):
        super().clear()


class _FakeSt:
    def __init__(self, session, qp, secrets=None):
        self.session_state = session
        self.query_params = _QP(qp)
        self.secrets = secrets or {}
        self.errors, self.successes = [], []

    def success(self, msg, *a, **k):
        self.successes.append(msg)

    def error(self, msg, *a, **k):
        self.errors.append(msg)

    def rerun(self):
        raise _Rerun


@pytest.fixture
def wire(monkeypatch):
    def _wire(*, qp, binding, session=None, secrets=None):
        exchanged: list[str] = []   # 每個「session」各自記錄
        fst = _FakeSt({} if session is None else session, qp, secrets)
        monkeypatch.setattr(ost, 'st', fst)
        monkeypatch.setattr(ost, '_browser_binding', lambda: binding)
        monkeypatch.setattr(ost, '_resolve_oauth_cfg',
                            lambda: {'client_id': 'c', 'client_secret': 's', 'redirect_uri': 'r'})

        def _exchange(code, ci, cs, ru):
            exchanged.append(code)
            return {'access_token': 'AT_' + code, 'refresh_token': 'RT'}
        monkeypatch.setattr(ost, 'exchange_code_for_tokens', _exchange)
        monkeypatch.setattr(ost, 'decode_id_token_email', lambda t: 'x@y.com')
        fst.exchanged = exchanged
        return fst
    return _wire


def _assert_rejected(fst):
    assert 'gsheet_tokens' not in fst.session_state, '不得換 token / 登入'
    assert fst.exchanged == [], '驗證未通過時不得呼叫 token exchange'
    assert 'portfolio_sheet_id' not in fst.session_state
    assert 'stock_portfolio_sheet_id' not in fst.session_state
    assert dict(fst.query_params) == {}, '?code= / ?state= 必須清掉(下一輪不再處理 → 不迴圈)'
    assert fst.errors == [ost.OAUTH_STATE_REJECTED_MSG]
    assert fst.successes == []


# ── 偽造 / 空 / 沒帶 state ──────────────────────────────────────────────────
@pytest.mark.parametrize('qp', [
    {'code': 'ATTACKER_CODE', 'state': 'anything.EVILSHEET'},
    {'code': 'ATTACKER_CODE', 'state': ''},
    {'code': 'ATTACKER_CODE', 'state': '.EVILSHEET'},
    {'code': 'ATTACKER_CODE'},
])
def test_forged_empty_missing_state_rejected(wire, qp):
    ns.issue('REAL_NONCE', _VICTIM)               # 受害者自己也有一個合法 nonce
    fst = wire(qp=qp, binding=_VICTIM)
    ost.handle_oauth_callback()                    # 不 rerun(不 raise _Rerun)
    _assert_rejected(fst)


# ── 合法:一次成功;重放被拒 ────────────────────────────────────────────────
def test_valid_state_accepted_once_then_replay_rejected(wire):
    ns.issue('N1', _VICTIM)
    fst = wire(qp={'code': 'CODE', 'state': 'N1.SHEET_A'}, binding=_VICTIM)
    with pytest.raises(_Rerun):
        ost.handle_oauth_callback()
    assert fst.session_state['gsheet_tokens']['access_token'] == 'AT_CODE'
    assert fst.session_state['portfolio_sheet_id'] == 'SHEET_A'

    fst2 = wire(qp={'code': 'CODE2', 'state': 'N1.SHEET_A'}, binding=_VICTIM)   # 新 session 重放
    ost.handle_oauth_callback()
    _assert_rejected(fst2)


def test_expired_state_rejected(wire, monkeypatch):
    clk = {'t': 50.0}
    monkeypatch.setattr(ns, '_now', lambda: clk['t'])
    ns.issue('N1', _VICTIM)
    clk['t'] += OAUTH_STATE_TTL_SEC + 1
    fst = wire(qp={'code': 'CODE', 'state': 'N1'}, binding=_VICTIM)
    ost.handle_oauth_callback()
    _assert_rejected(fst)


# ── CSRF 攻擊本體:攻擊者瀏覽器領 nonce,受害者瀏覽器送回 ─────────────────────
def test_attacker_nonce_from_other_browser_rejected(wire):
    """proto.py 的攻擊:server 端有登記(攻擊者在自己瀏覽器開站領到),但綁的是攻擊者瀏覽器。"""
    ns.issue('N_ATT', _ATTACKER)
    fst = wire(qp={'code': 'ATTACKER_CODE', 'state': 'N_ATT.EVILSHEET'}, binding=_VICTIM)
    ost.handle_oauth_callback()
    _assert_rejected(fst)
    # 已燒掉:攻擊者自己也不能再用
    assert ns.consume('N_ATT', _ATTACKER) == (False, ns.REASON_UNKNOWN)


def test_no_cookie_rejected(wire):
    ns.issue('N1', _VICTIM)
    fst = wire(qp={'code': 'CODE', 'state': 'N1'}, binding=None)
    ost.handle_oauth_callback()
    _assert_rejected(fst)


# ── 不迴圈:拒絕後下一輪畫的是全新的登入連結 ──────────────────────────────────
def test_no_loop_next_run_issues_fresh_nonce(wire):
    ns.issue('OLD', _VICTIM)
    fst = wire(qp={'code': 'CODE', 'state': 'WRONG'}, binding=_VICTIM,
               session={'_oauth_state': 'OLD'})
    ost.handle_oauth_callback()
    _assert_rejected(fst)
    assert '_oauth_state' not in fst.session_state, 'callback 處理後本 session 的 nonce 要換新'
    # 下一輪:沒有 ?code= → callback 什麼都不做;登入鈕拿到新的 nonce,且已綁本瀏覽器登記
    ost.handle_oauth_callback()
    assert fst.errors == [ost.OAUTH_STATE_REJECTED_MSG], '下一輪不得再報錯 / 再處理'
    new = ost.get_login_state()
    assert new != 'OLD' and new != 'WRONG'
    assert ns._STORE[new][1] == _VICTIM
    # 用新連結登入可以成功
    fst2 = wire(qp={'code': 'C2', 'state': new}, binding=_VICTIM)
    with pytest.raises(_Rerun):
        ost.handle_oauth_callback()
    assert fst2.session_state['gsheet_tokens']['access_token'] == 'AT_C2'


def test_oauth_error_clears_query_params(wire, monkeypatch):
    ns.issue('N1', _VICTIM)
    fst = wire(qp={'code': 'CODE', 'state': 'N1'}, binding=_VICTIM)

    def _boom(*a):
        raise ost.OAuthError('invalid_grant')
    monkeypatch.setattr(ost, 'exchange_code_for_tokens', _boom)
    ost.handle_oauth_callback()
    assert 'gsheet_tokens' not in fst.session_state
    assert dict(fst.query_params) == {}
    assert fst.errors and 'invalid_grant' in fst.errors[0]


# ── log 只有 reason code,不含任何值 ───────────────────────────────────────────
def test_log_only_reason_codes(wire, capsys):
    ns.issue('SECRET_NONCE_ABC', _ATTACKER)
    wire(qp={'code': 'SECRET_CODE_XYZ', 'state': 'SECRET_NONCE_ABC.SHEETQQ'}, binding=_VICTIM)
    ost.handle_oauth_callback()
    out = capsys.readouterr().out
    assert 'reason=mismatch' in out and 'enforce=on' in out
    for leaked in ('SECRET_NONCE_ABC', 'SECRET_CODE_XYZ', 'SHEETQQ', _VICTIM, _ATTACKER):
        assert leaked not in out


# ── 安全閥 oauth_csrf_enforce ─────────────────────────────────────────────────
@pytest.mark.parametrize('flag', [False, 'false', 'False', '0', 'off'])
def test_safety_valve_off_accepts_with_log_and_no_rebind(wire, capsys, flag):
    ns.issue('N_ATT', _ATTACKER)
    fst = wire(qp={'code': 'CODE', 'state': 'N_ATT.EVILSHEET'}, binding=_VICTIM,
               secrets={OAUTH_CSRF_ENFORCE_SECRET_KEY: flag})
    with pytest.raises(_Rerun):
        ost.handle_oauth_callback()
    assert fst.session_state['gsheet_tokens']['access_token'] == 'AT_CODE'
    assert 'portfolio_sheet_id' not in fst.session_state, '放行的登入不得回綁 state 帶回的 Sheet'
    assert 'sheet' not in fst.query_params
    out = capsys.readouterr().out
    assert 'reason=mismatch' in out and 'enforce=off' in out


@pytest.mark.parametrize('secrets', [{}, {OAUTH_CSRF_ENFORCE_SECRET_KEY: True},
                                     {OAUTH_CSRF_ENFORCE_SECRET_KEY: 'yes'},
                                     {OAUTH_CSRF_ENFORCE_SECRET_KEY: 'garbage'}])
def test_safety_valve_default_is_strict(wire, secrets):
    fst = wire(qp={'code': 'CODE', 'state': 'FORGED'}, binding=_VICTIM, secrets=secrets)
    ost.handle_oauth_callback()
    _assert_rejected(fst)


def test_safety_valve_off_still_succeeds_normally_with_rebind(wire):
    ns.issue('N1', _VICTIM)
    fst = wire(qp={'code': 'CODE', 'state': 'N1.SHEET_A'}, binding=_VICTIM,
               secrets={OAUTH_CSRF_ENFORCE_SECRET_KEY: False})
    with pytest.raises(_Rerun):
        ost.handle_oauth_callback()
    assert fst.session_state['portfolio_sheet_id'] == 'SHEET_A'


# ── AppTest 端到端:真 Streamlit runtime,兩個 session 模擬整頁轉跳 ───────────────
_APP = '''
import os, sys
sys.path.insert(0, {root!r})
import streamlit as st
import src.data.portfolio.oauth_state as ost
ost.exchange_code_for_tokens = lambda code, ci, cs, ru: {{"access_token": "AT_" + code, "refresh_token": "RT"}}
ost.decode_id_token_email = lambda t: "who@x.com"
ost._browser_binding = lambda: os.environ.get("SEC2_TEST_BINDING") or None
ost.handle_oauth_callback()
st.session_state["_issued_nonce"] = ost.get_login_state()
'''


@pytest.fixture
def app_file(tmp_path):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = tmp_path / 'sec2_app.py'
    p.write_text(_APP.format(root=root), encoding='utf-8')
    return str(p)


def _run(app_file, monkeypatch, *, binding, qp=None):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('SEC2_TEST_BINDING', binding)
    at = AppTest.from_file(app_file, default_timeout=30)
    at.secrets['google_oauth'] = {'client_id': 'c', 'client_secret': 's', 'redirect_uri': 'https://app/'}
    for k, v in (qp or {}).items():
        at.query_params[k] = v
    at.run()
    return at


def _ss(at, key):
    return at.session_state[key] if key in at.session_state else None


def test_apptest_login_csrf_end_to_end(app_file, monkeypatch):
    # AppTest 在同一 process 跑腳本、共用 sys.modules:腳本裡對 ost 的 stub 會外洩到後續測試 →
    # 先以 monkeypatch 登記原值,teardown 時還原。
    for _name in ('_browser_binding', 'exchange_code_for_tokens', 'decode_id_token_email'):
        monkeypatch.setattr(ost, _name, getattr(ost, _name))
    # 攻擊者在自己瀏覽器開站 → 領到登記過的 nonce
    at_att = _run(app_file, monkeypatch, binding=_ATTACKER)
    n_att = _ss(at_att, '_issued_nonce')
    assert n_att and n_att in ns._STORE
    # 受害者瀏覽器被導到攻擊者的 callback URL
    at_vic = _run(app_file, monkeypatch, binding=_VICTIM,
                  qp={'code': 'ATTACKER_CODE', 'state': f'{n_att}.EVILSHEET'})
    assert not at_vic.exception
    assert _ss(at_vic, 'gsheet_tokens') is None
    assert _ss(at_vic, 'portfolio_sheet_id') is None
    assert [e.value for e in at_vic.error] == [ost.OAUTH_STATE_REJECTED_MSG]
    assert 'code' not in at_vic.query_params

    # 正常登入:受害者自己開站(session 1)→ 按登入 → Google 轉跳回來是新 session(session 2)
    at_1 = _run(app_file, monkeypatch, binding=_VICTIM)
    n_vic = _ss(at_1, '_issued_nonce')
    at_2 = _run(app_file, monkeypatch, binding=_VICTIM,
                qp={'code': 'MY_CODE', 'state': f'{n_vic}.MYSHEET'})
    assert not at_2.exception
    assert _ss(at_2, 'gsheet_tokens') == {'access_token': 'AT_MY_CODE', 'refresh_token': 'RT'}
    assert _ss(at_2, 'portfolio_sheet_id') == 'MYSHEET'
    assert at_2.query_params.get('sheet') == ['MYSHEET']

    # 重放同一個 callback URL(另一個新 session)→ 拒絕
    at_3 = _run(app_file, monkeypatch, binding=_VICTIM,
                qp={'code': 'MY_CODE', 'state': f'{n_vic}.MYSHEET'})
    assert _ss(at_3, 'gsheet_tokens') is None
    assert [e.value for e in at_3.error] == [ost.OAUTH_STATE_REJECTED_MSG]
