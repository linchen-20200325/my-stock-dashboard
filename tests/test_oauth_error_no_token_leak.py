"""SEC-2 審計 round 1(SA1-S3):`OAuthError` 訊息不得含 token / 回應本文。

修前:`infra/oauth.py` 以 `f"token response 缺 access_token：{tokens}"` 把整份回應(可能含
refresh_token / id_token)塞進例外,callback 再以 `st.error(f"❌ OAuth 失敗：{_oe}")` 畫上畫面;
非 200 時也把 `r.text[:200]` 原樣帶出。現在只留「哪一步 / HTTP 狀態 / Google error 代碼 / 鍵名」。
"""
from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest

import infra.oauth as io
import src.data.portfolio.oauth_nonce_store as ns
import src.data.portfolio.oauth_state as ost

_SECRET = 'SECRET_TOKEN_VALUE_123'


class _Resp:
    def __init__(self, status, payload=None, text=None):
        self.status_code = status
        self._payload = payload
        self.text = text if text is not None else str(payload)

    def json(self):
        if self._payload is None:
            raise ValueError('not json')
        return self._payload


def _exchange():
    return io.exchange_code_for_tokens('CODE', 'cid', 'csecret', 'https://r/')


def _refresh():
    return io.refresh_access_token('RT_' + _SECRET, 'cid', 'csecret')


@pytest.mark.parametrize('call', [_exchange, _refresh])
@pytest.mark.parametrize('resp', [
    _Resp(200, {'refresh_token': _SECRET, 'id_token': _SECRET, 'scope': 's'}),   # 缺 access_token
    _Resp(400, {'error': 'invalid_grant', 'error_description': _SECRET, 'access_token': _SECRET}),
    _Resp(500, None, text=f'<html>{_SECRET}</html>'),
    _Resp(400, {'error': f'bad {_SECRET} <x>'}),                                  # error 代碼不合字母集
    _Resp(200, [_SECRET]),                                                         # 非物件
])
def test_oauth_error_messages_never_contain_response_values(call, resp):
    with patch('requests.post', return_value=resp):
        with pytest.raises(io.OAuthError) as ei:
            call()
    msg = str(ei.value)
    assert _SECRET not in msg
    assert 'csecret' not in msg


def test_missing_access_token_lists_keys_only():
    with patch('requests.post', return_value=_Resp(200, {'refresh_token': _SECRET, 'scope': 's'})):
        with pytest.raises(io.OAuthError, match=r'回應欄位：refresh_token, scope'):
            _exchange()


def test_error_code_whitelisted_is_shown():
    with patch('requests.post', return_value=_Resp(400, {'error': 'invalid_grant'})):
        with pytest.raises(io.OAuthError, match=r'\(400\)：invalid_grant$'):
            _exchange()


@pytest.mark.parametrize('call', [_exchange, _refresh])
def test_network_error_shows_type_only(call):
    with patch('requests.post', side_effect=ConnectionError(f'https://x/?t={_SECRET}')):
        with pytest.raises(io.OAuthError) as ei:
            call()
    assert _SECRET not in str(ei.value) and 'ConnectionError' in str(ei.value)


def test_callback_error_on_screen_has_no_token_values(monkeypatch):
    """端到端:真 `exchange_code_for_tokens` 回缺欄位的回應 → st.error 不含任何值。"""
    ns._STORE.clear()
    binding = hashlib.sha256(b'b').hexdigest()
    ns.issue('N1', binding)

    class _QP(dict):
        pass

    class _St:
        session_state: dict = {}
        query_params = _QP({'code': 'CODE', 'state': 'N1'})
        errors: list = []

        def error(self, m, *a, **k):
            self.errors.append(m)

        def success(self, *a, **k):
            raise AssertionError('不應成功')

        def rerun(self):
            raise AssertionError('不應 rerun')

    fst = _St()
    fst.session_state, fst.errors = {}, []
    monkeypatch.setattr(ost, 'st', fst)
    monkeypatch.setattr(ost, '_browser_binding', lambda: binding)
    monkeypatch.setattr(ost, '_resolve_oauth_cfg',
                        lambda: {'client_id': 'c', 'client_secret': 's', 'redirect_uri': 'r'})
    with patch('requests.post', return_value=_Resp(200, {'refresh_token': _SECRET})):
        ost.handle_oauth_callback()
    ns._STORE.clear()
    assert len(fst.errors) == 1 and _SECRET not in fst.errors[0]
    assert 'gsheet_tokens' not in fst.session_state
