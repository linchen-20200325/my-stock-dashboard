"""vNext 1.0-B2 迴歸:重新整理後靜默恢復 Google 登入(prompt=none,不保存任何 Google 憑證;DEC-062 Q2)。

客戶硬性條件(原文):「不得保存 Google 密碼或 Google 憑證」⇒ token 只住在 session。
做法:登入強驗成功 → 網址掛非憑證記號 `?gs=1`;重新整理(新 session、無 token)看到記號 →
**先拿掉記號**、發 nonce、整頁轉 Google `prompt=none` → 回呼走 SEC-2 consume。

本檔釘住(每條對應一個宣稱):
  1. 有記號的新 session → 恰好 1 個轉跳 script,記號被拿掉;同 session 再跑 → 0。
  2. 有 code/state/error、已登入、OAuth 未設定、沒 cookie、開關關閉、登出後 → 0 轉跳。
  3. Google 每次都回 `error=login_required`,連續重新整理 N 次 → 轉跳總數 ≤ 1、每次失敗都有看得到的訊息。
  4. consume 失敗(unknown/mismatch/no_cookie/expired)→ 不掛記號,下一輪不轉跳。
  5. consume ok 成功 → token、回綁 Sheet、掛記號;安全閥放行 → 不掛記號;開關關閉 → 不掛。
  6. `build_authorize_url`:預設輸出逐字不變(golden);`prompt="none"` 單獨出現。
  7. JS:URL 以 JSON 編碼、無法跳出字串/關掉 </script>;只導最上層視窗,跨來源時什麼都不做。
  8. token 過期且無 refresh_token → `LoginRequiredError(LOGIN_EXPIRED_MSG)`、清 session token、不轉跳。
  9. SEC-1:沒有 refresh_token 時快取身分仍是每人一格(同人穩定、不同人不同)。
 10. log 不含 nonce / token / email / URL / sheet。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.parse as up
from unittest.mock import patch

import pytest

import src.data.portfolio.gsheet_portfolio as gsp
import src.data.portfolio.oauth_nonce_store as ns
import src.data.portfolio.oauth_state as ost
from infra.oauth import GOOGLE_AUTH_URL, GOOGLE_OAUTH_SCOPES, build_authorize_url
from shared.oauth_csrf_policy import OAUTH_CSRF_ENFORCE_SECRET_KEY, OAUTH_STATE_TTL_SEC
from shared.oauth_session_policy import (
    OAUTH_SILENT_ATTEMPTED_SESSION_KEY,
    OAUTH_SILENT_FAILURE_ERROR_CODES,
    OAUTH_SILENT_MARKER_PARAM as MK,
    OAUTH_SILENT_MARKER_VALUE as MV,
    OAUTH_SILENT_REAUTH_SECRET_KEY,
)

_ME = hashlib.sha256(b'my-browser').hexdigest()
_OTHER = hashlib.sha256(b'other-browser').hexdigest()
_CFG = {'client_id': 'CID', 'client_secret': 'CSECRET', 'redirect_uri': 'https://app.example/'}


def _id_token(**claims) -> str:
    _p = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return f'hdr.{_p}.sig'


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
    pass


class _FakeSt:
    """一個 session:session_state / query_params(＝目前瀏覽器網址)/ secrets + 記錄畫了什麼。"""

    def __init__(self, session, qp, secrets=None):
        self.session_state = session
        self.query_params = _QP(qp)
        self.secrets = secrets or {}
        self.errors, self.successes, self.infos, self.captions, self.htmls = [], [], [], [], []

    def success(self, msg, *a, **k):
        self.successes.append(msg)

    def error(self, msg, *a, **k):
        self.errors.append(msg)

    def info(self, msg, *a, **k):
        self.infos.append(msg)

    def caption(self, msg, *a, **k):
        self.captions.append(msg)

    def html(self, body, *a, unsafe_allow_javascript=False, **k):
        self.htmls.append((body, unsafe_allow_javascript))

    def rerun(self):
        raise _Rerun


@pytest.fixture
def wire(monkeypatch):
    """建一個「session」並接上 ost / gsp 的 st;binding = 這個瀏覽器的 cookie 雜湊(None ＝ 沒 cookie)。"""
    state = {'binding': _ME, 'cfg': dict(_CFG), 'exchanged': []}
    monkeypatch.setattr(ost, '_browser_binding', lambda: state['binding'])
    monkeypatch.setattr(ost, '_resolve_oauth_cfg',
                        lambda: dict(state['cfg']) if state['cfg'] else None)

    def _exchange(code, ci, cs, ru):
        state['exchanged'].append(code)
        # 靜默恢復:Google 不發 refresh_token(本檔預設情境)
        return {'access_token': 'AT_SECRET_' + code, 'expires_at': 9_999_999_999,
                'id_token': _id_token(sub='SUB_ME', email='me@example.com')}
    monkeypatch.setattr(ost, 'exchange_code_for_tokens', _exchange)

    def _wire(*, qp, session=None, secrets=None, binding=_ME, cfg=True):
        state['binding'] = binding
        state['cfg'] = dict(_CFG) if cfg else None
        fst = _FakeSt({} if session is None else session, qp, secrets)
        monkeypatch.setattr(ost, 'st', fst)
        monkeypatch.setattr(gsp, 'st', fst)
        fst.exchanged = state['exchanged']
        return fst
    return _wire


def _run_app(fst) -> None:
    """模擬 app.py 一輪:callback → (rerun 就再跑一輪,同 session)→ 靜默恢復。"""
    for _ in range(3):
        try:
            ost.handle_oauth_callback()
        except _Rerun:
            continue
        break
    ost.maybe_silent_reauth()


def _redirect_url(fst) -> str:
    """從最後一個轉跳 script 取出 URL(JSON 字串常值)。"""
    body, _ = fst.htmls[-1]
    m = re.search(r'var u=(".*?");var t;', body)
    assert m, body
    return json.loads(m.group(1))


def _qs(url: str) -> dict:
    return {k: v[0] for k, v in up.parse_qs(up.urlsplit(url).query).items()}


# ══════════════════════════════════════════════════════════════════════════
# 1. 有記號 → 恰好一次轉跳,記號被拿掉;同 session 再跑 → 0
# ══════════════════════════════════════════════════════════════════════════
def test_fresh_session_with_marker_redirects_exactly_once_and_pops_marker(wire):
    fst = wire(qp={MK: MV, 'sheet': 'SHEET_A'})
    _run_app(fst)
    assert len(fst.htmls) == 1
    body, unsafe = fst.htmls[0]
    assert unsafe is True, 'script 要能執行必須 unsafe_allow_javascript=True'
    assert MK not in fst.query_params, '一次性:轉跳前必須先拿掉記號'
    assert fst.query_params.get('sheet') == 'SHEET_A', 'sheet 不得被沖掉'
    assert fst.captions == [ost.OAUTH_SILENT_REAUTH_PENDING_MSG]
    assert fst.errors == [] and fst.infos == []
    url = _redirect_url(fst)
    assert url.startswith(GOOGLE_AUTH_URL + '?')
    q = _qs(url)
    assert q['prompt'] == 'none'
    nonce, _, sheet = q['state'].partition('.')
    assert sheet == 'SHEET_A', 'state 便車要帶著 sheet(新 session 從網址讀)'
    assert ns._STORE[nonce][1] == _ME, 'nonce 走既有 get_login_state 發放並綁本瀏覽器'
    # 同一個 session 再跑(例如使用者在轉跳前點了什麼)→ 不再轉
    _run_app(fst)
    assert len(fst.htmls) == 1


def test_session_guard_blocks_second_redirect_even_if_marker_reappears(wire):
    """記號被拿掉之外,session 旗標是第二道閘:記號就算又出現(pop 失敗 / 別處寫回),同 session 不再轉。"""
    fst = wire(qp={MK: MV})
    _run_app(fst)
    assert len(fst.htmls) == 1
    fst.query_params[MK] = MV
    _run_app(fst)
    assert len(fst.htmls) == 1
    assert fst.session_state[OAUTH_SILENT_ATTEMPTED_SESSION_KEY] is True


# ══════════════════════════════════════════════════════════════════════════
# 2. 不該轉跳的情形
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize('extra', [{'code': 'X'}, {'state': 'X'}, {'error': 'login_required'}])
def test_no_redirect_when_callback_params_present(wire, monkeypatch, extra):
    # 只測 maybe_silent_reauth 本身的閘(不經 callback 先清網址)
    fst = wire(qp={MK: MV, **extra})
    assert ost.maybe_silent_reauth() is False
    assert fst.htmls == []
    assert fst.query_params.get(MK) == MV, '沒轉跳就不該動記號'


def test_no_redirect_when_tokens_exist(wire):
    fst = wire(qp={MK: MV}, session={'gsheet_tokens': {'access_token': 'AT'}})
    _run_app(fst)
    assert fst.htmls == []
    assert fst.query_params.get(MK) == MV, '已登入時記號是常態,保留'


def test_no_redirect_when_oauth_not_configured(wire, capsys):
    fst = wire(qp={MK: MV}, cfg=False)
    _run_app(fst)
    assert fst.htmls == []
    assert 'silent_reauth=skip reason=not_configured' in capsys.readouterr().out


def test_no_redirect_without_cookie_and_logs_once(wire, capsys):
    fst = wire(qp={MK: MV}, binding=None)
    _run_app(fst)
    _run_app(fst)
    assert fst.htmls == []
    assert ns._STORE == {}, '沒 cookie 不發 nonce'
    out = capsys.readouterr().out
    assert out.count('silent_reauth=skip reason=no_cookie') == 1, '每 session 只記一次'


@pytest.mark.parametrize('flag', [False, 'false', 'False', '0', 0, 'no', 'off', ' OFF '])
def test_no_redirect_when_flag_disabled(wire, flag):
    fst = wire(qp={MK: MV}, secrets={OAUTH_SILENT_REAUTH_SECRET_KEY: flag})
    _run_app(fst)
    assert fst.htmls == []


@pytest.mark.parametrize('secrets', [{}, {OAUTH_SILENT_REAUTH_SECRET_KEY: True},
                                     {OAUTH_SILENT_REAUTH_SECRET_KEY: 'yes'},
                                     {OAUTH_SILENT_REAUTH_SECRET_KEY: 'garbage'},
                                     {OAUTH_SILENT_REAUTH_SECRET_KEY: 1}])
def test_flag_default_and_other_values_enable(wire, secrets):
    fst = wire(qp={MK: MV}, secrets=secrets)
    _run_app(fst)
    assert len(fst.htmls) == 1


@pytest.mark.parametrize('val', ['0', '', 'true', '2'])
def test_marker_must_have_exact_value(wire, val):
    fst = wire(qp={MK: val})
    _run_app(fst)
    assert fst.htmls == []


def test_logout_removes_marker_and_refresh_does_not_log_back_in(wire):
    fst = wire(qp={MK: MV, 'sheet': 'S'},
               session={'gsheet_tokens': {'access_token': 'AT'}, 'gsheet_email': 'e'})
    # app.py 側欄登出:pop token → forget_silent_reauth()
    for _k in ('gsheet_tokens', 'gsheet_email', '_oauth_state'):
        fst.session_state.pop(_k, None)
    ost.forget_silent_reauth()
    _run_app(fst)
    assert fst.htmls == [] and MK not in fst.query_params
    assert fst.query_params.get('sheet') == 'S'
    # 重新整理(新 session,網址就是登出後的網址)→ 不得登回去
    fst2 = wire(qp=dict(fst.query_params))
    _run_app(fst2)
    assert fst2.htmls == []


def test_app_py_wires_hook_and_logout():
    """app.py 只加最少的線:callback 之後立刻呼叫、登出呼叫 forget(DEC-019 舊 UI 凍結,只動這幾行)。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, 'app.py'), encoding='utf-8') as f:
        src = f.read()
    i_cb = src.index('    _oauth_cb()\n')
    i_si = src.index('    _oauth_silent()')
    assert i_cb < i_si and '\n' not in src[i_cb + len('    _oauth_cb()\n'):i_si].strip()
    i_logout = src.index("key='btn_oauth_logout_sb'")
    i_forget = src.index('_sb_forget_silent()', i_logout)
    assert i_forget < src.index('st.rerun()', i_logout)


# ══════════════════════════════════════════════════════════════════════════
# 3. Google 一直回 login_required → 不迴圈,每次失敗都有訊息
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize('err', sorted(OAUTH_SILENT_FAILURE_ERROR_CODES))
def test_google_always_errors_no_loop(wire, err):
    url_now = {'sheet': 'S', MK: MV}        # 使用者上次登入成功後的網址
    redirects, failures = 0, 0
    for _refresh in range(6):
        fst = wire(qp=dict(url_now))         # 每次重新整理 = 新 session
        _run_app(fst)
        url_now = dict(fst.query_params)
        if fst.htmls:
            redirects += 1
            # Google 收到 prompt=none,做不到 → 帶 error + 原 state 回固定 redirect_uri(新 session)
            st_param = _qs(_redirect_url(fst))['state']
            landing = wire(qp={'error': err, 'state': st_param})
            _run_app(landing)
            failures += 1
            assert landing.infos == [ost.OAUTH_SILENT_REAUTH_FAILED_MSG], '每次失敗都要有看得到的訊息'
            assert landing.errors == [], '不是系統錯誤 → 不畫紅'
            assert landing.htmls == [], '失敗落地頁不得再轉'
            assert 'gsheet_tokens' not in landing.session_state
            url_now = dict(landing.query_params)
            assert url_now == {'sheet': 'S'}, '清掉 error/state,保留 sheet,不掛記號'
    assert redirects <= 1 and redirects == failures == 1


def test_error_branch_burns_nonce_and_restores_sheet_from_strong_state(wire):
    fst = wire(qp={MK: MV, 'sheet': 'S1'})
    _run_app(fst)
    st_param = _qs(_redirect_url(fst))['state']
    nonce = st_param.partition('.')[0]
    landing = wire(qp={'error': 'login_required', 'state': st_param})
    _run_app(landing)
    assert landing.session_state['portfolio_sheet_id'] == 'S1'
    assert landing.session_state['stock_portfolio_sheet_id'] == 'S1'
    assert ns.consume(nonce, _ME) == (False, ns.REASON_UNKNOWN), 'error 回呼也要燒掉 nonce'


def test_error_branch_foreign_state_does_not_rebind_sheet(wire):
    ns.issue('N_OTHER', _OTHER)
    landing = wire(qp={'error': 'login_required', 'state': 'N_OTHER.EVIL'})
    _run_app(landing)
    assert 'portfolio_sheet_id' not in landing.session_state
    assert dict(landing.query_params) == {}
    assert landing.infos == [ost.OAUTH_SILENT_REAUTH_FAILED_MSG]


@pytest.mark.parametrize('code,shown', [('access_denied', 'access_denied'),
                                        ('<script>x</script>', '(無法解析)'),
                                        ('', '(無法解析)')])
def test_error_branch_other_codes_generic_message(wire, code, shown):
    landing = wire(qp={'error': code, 'sheet': 'KEEP'})       # 沒有 state 也要處理
    _run_app(landing)
    assert landing.infos == [ost.OAUTH_LOGIN_INCOMPLETE_MSG.format(code=shown)]
    assert dict(landing.query_params) == {'sheet': 'KEEP'}
    assert landing.errors == [] and landing.successes == [] and landing.htmls == []


def test_error_branch_does_not_rerun(wire):
    landing = wire(qp={'error': 'login_required', 'state': 'whatever'})
    ost.handle_oauth_callback()          # 不 raise _Rerun
    assert landing.infos


# ══════════════════════════════════════════════════════════════════════════
# 4. consume 失敗 → 不掛記號,下一輪不轉跳
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize('case', ['unknown', 'mismatch', 'no_cookie', 'expired'])
def test_consume_failure_sets_no_marker(wire, monkeypatch, case):
    clk = {'t': 100.0}
    monkeypatch.setattr(ns, '_now', lambda: clk['t'])
    binding = _ME
    if case == 'mismatch':
        ns.issue('N1', _OTHER)
    elif case == 'no_cookie':
        ns.issue('N1', _ME)
        binding = None
    elif case == 'expired':
        ns.issue('N1', _ME)
        clk['t'] += OAUTH_STATE_TTL_SEC + 1
    fst = wire(qp={'code': 'C', 'state': 'N1.S'}, binding=binding)
    _run_app(fst)
    assert fst.errors == [ost.OAUTH_STATE_REJECTED_MSG]
    assert MK not in fst.query_params and 'gsheet_tokens' not in fst.session_state
    assert fst.htmls == []
    fst2 = wire(qp=dict(fst.query_params), binding=binding)    # 重新整理
    _run_app(fst2)
    assert fst2.htmls == []


# ══════════════════════════════════════════════════════════════════════════
# 5. 成功路徑掛記號的條件
# ══════════════════════════════════════════════════════════════════════════
def test_success_with_consume_ok_sets_marker(wire):
    ns.issue('N1', _ME)
    fst = wire(qp={'code': 'C', 'state': 'N1.SHEET_A'})
    _run_app(fst)
    assert fst.session_state['gsheet_tokens']['access_token'] == 'AT_SECRET_C'
    assert fst.session_state['gsheet_email'] == 'me@example.com'
    assert fst.session_state['portfolio_sheet_id'] == 'SHEET_A'
    assert dict(fst.query_params) == {'sheet': 'SHEET_A', MK: MV}
    assert fst.htmls == [], '剛登入的 session 有 token,不轉'


def test_success_without_sheet_still_sets_marker(wire):
    ns.issue('N1', _ME)
    fst = wire(qp={'code': 'C', 'state': 'N1'})
    _run_app(fst)
    assert dict(fst.query_params) == {MK: MV}


def test_success_via_safety_valve_sets_no_marker(wire):
    ns.issue('N1', _OTHER)
    fst = wire(qp={'code': 'C', 'state': 'N1.S'},
               secrets={OAUTH_CSRF_ENFORCE_SECRET_KEY: False})
    _run_app(fst)
    assert 'gsheet_tokens' in fst.session_state
    assert MK not in fst.query_params, '安全閥放行的登入不掛記號(退回 A 行為)'


def test_success_with_flag_disabled_sets_no_marker(wire):
    ns.issue('N1', _ME)
    fst = wire(qp={'code': 'C', 'state': 'N1.S'},
               secrets={OAUTH_SILENT_REAUTH_SECRET_KEY: 'false'})
    _run_app(fst)
    assert 'gsheet_tokens' in fst.session_state
    assert dict(fst.query_params) == {'sheet': 'S'}


def test_full_roundtrip_refresh_restores_login(wire):
    ns.issue('N0', _ME)
    s1 = wire(qp={'code': 'C0', 'state': 'N0.SH'})         # 第一次手動登入
    _run_app(s1)
    s2 = wire(qp=dict(s1.query_params))                    # 重新整理
    _run_app(s2)
    assert len(s2.htmls) == 1 and 'gsheet_tokens' not in s2.session_state
    st_param = _qs(_redirect_url(s2))['state']
    s3 = wire(qp={'code': 'C1', 'state': st_param})       # Google prompt=none 成功帶 code 回來
    _run_app(s3)
    assert s3.session_state['gsheet_tokens']['access_token'] == 'AT_SECRET_C1'
    assert s3.session_state['portfolio_sheet_id'] == 'SH'
    assert dict(s3.query_params) == {'sheet': 'SH', MK: MV}, '恢復後記號重新掛上,下次重新整理仍可恢復'
    assert s3.htmls == []


# ══════════════════════════════════════════════════════════════════════════
# 6. build_authorize_url
# ══════════════════════════════════════════════════════════════════════════
#: 加 `prompt` 參數前(基底 4a576b19)以同一組輸入實跑得到的 URL —— 預設輸出必須逐字相同。
_GOLDEN_DEFAULT = (
    'https://accounts.google.com/o/oauth2/v2/auth?client_id=CID&redirect_uri=https%3A%2F%2Fapp.example%2F'
    '&response_type=code&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fspreadsheets+https%3A%2F%2F'
    'www.googleapis.com%2Fauth%2Fdrive.file+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fdrive.metadata.'
    'readonly+openid+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email&access_type=offline'
    '&prompt=select_account+consent&include_granted_scopes=true&state=NONCE.SHEET')


def test_authorize_url_default_unchanged_golden():
    assert build_authorize_url('CID', 'https://app.example/', state='NONCE.SHEET') == _GOLDEN_DEFAULT
    assert build_authorize_url('CID', 'https://app.example/', state='NONCE.SHEET',
                               prompt=None) == _GOLDEN_DEFAULT


def test_authorize_url_prompt_none_alone_rest_identical():
    d = up.parse_qs(up.urlsplit(_GOLDEN_DEFAULT).query)
    n_url = build_authorize_url('CID', 'https://app.example/', state='NONCE.SHEET', prompt='none')
    n = up.parse_qs(up.urlsplit(n_url).query)
    assert n['prompt'] == ['none'], 'prompt=none 必須單獨出現'
    assert '&prompt=none&' in n_url
    assert {k: v for k, v in n.items() if k != 'prompt'} == {k: v for k, v in d.items() if k != 'prompt'}
    assert n['scope'] == [' '.join(GOOGLE_OAUTH_SCOPES)]


# ══════════════════════════════════════════════════════════════════════════
# 7. 轉跳 script
# ══════════════════════════════════════════════════════════════════════════
_EVIL_URL = GOOGLE_AUTH_URL + '?state=a";alert(1);//</script><img src=x onerror=alert(2)>&x= '


def test_script_json_encodes_url_and_cannot_break_out():
    body = ost._silent_redirect_script(_EVIL_URL)
    m = re.fullmatch(r'<script>\(function\(\)\{var u=(".*?");var t;(.*)\}\)\(\);</script>', body)
    assert m, body
    assert json.loads(m.group(1)) == _EVIL_URL, 'JS 端拿到的就是原 URL'
    literal = m.group(1)
    assert '<' not in literal and '>' not in literal and '&' not in literal
    assert literal.count('"') - literal.count('\\"') == 2, '只有字串頭尾兩個未跳脫引號'
    assert body.count('</script>') == 1 and body.endswith('</script>')


def test_script_only_navigates_top_window():
    body = ost._silent_redirect_script(GOOGLE_AUTH_URL + '?a=1')
    assert 'window.location' not in body, '⛔ 不得導 iframe 自己(Google 拒絕被框 → 白畫面)'
    assert 'location.href=' not in body and 'location.assign' not in body
    assert body.count('location.replace(') == 1 and 't.location.replace(u)' in body
    # 跨來源探測在 replace 之前,探測失敗直接 return
    probe = body.index('void t.location.href;')
    assert body.index('catch(e){return;}') > probe
    assert body.index('t.location.replace(u)') > body.index('catch(e){return;}')
    assert 't=window.top' in body


def test_malicious_sheet_id_never_reaches_script(wire):
    fst = wire(qp={MK: MV, 'sheet': 'S";alert(1);//</script>'})
    _run_app(fst)
    url = _redirect_url(fst)
    assert _qs(url)['state'].count('.') == 0, '消毒不過的 sheet 不上 state 便車'
    body = fst.htmls[0][0]
    assert 'alert' not in body and body.count('</script>') == 1


# ══════════════════════════════════════════════════════════════════════════
# 8. token 過期且無 refresh_token
# ══════════════════════════════════════════════════════════════════════════
def test_expiry_without_refresh_token_raises_login_required_and_clears(wire, capsys):
    fst = wire(qp={MK: MV, 'sheet': 'S'},
               session={'gsheet_tokens': {'access_token': 'AT_OLD_SECRET', 'expires_at': 1,
                                          'id_token': _id_token(sub='SUB_ME')},
                        'gsheet_email': 'me@example.com', gsp.PORTFOLIO_SHEET_KEY: 'S'})
    called = []
    with patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
         patch('src.data.portfolio.oauth_state._get_oauth_client',
               side_effect=lambda: called.append(1)):
        with pytest.raises(gsp.LoginRequiredError) as ei:
            gsp.list_portfolios(sheet_id='S')
    assert str(ei.value) == gsp.LOGIN_EXPIRED_MSG
    assert called == [], '不得走到深處的 ensure_fresh_tokens(原始 OAuthError)'
    assert 'gsheet_tokens' not in fst.session_state and 'gsheet_email' not in fst.session_state
    assert fst.query_params.get(MK) == MV, '記號保留 ⇒ 重新整理可恢復'
    # session 中途絕不自動轉跳
    _run_app(fst)
    assert fst.htmls == []
    out = capsys.readouterr().out
    assert 'login_expired reason=no_refresh_token' in out
    assert 'AT_OLD_SECRET' not in out and 'me@example.com' not in out
    # 重新整理(新 session)→ 靜默恢復一次
    fst2 = wire(qp=dict(fst.query_params))
    _run_app(fst2)
    assert len(fst2.htmls) == 1


def test_build_client_expiry_message_and_no_oauth_error_leak(wire):
    wire(qp={}, session={'gsheet_tokens': {'access_token': 'AT', 'expires_at': 1}})
    with patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True):
        with pytest.raises(gsp.LoginRequiredError, match='Google 登入已逾時'):
            gsp._build_client()


def test_not_expired_without_refresh_token_builds_client(wire):
    wire(qp={}, session={'gsheet_tokens': {'access_token': 'AT', 'expires_at': 9_999_999_999}})
    sentinel = object()
    with patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
         patch('src.data.portfolio.oauth_state._get_oauth_client', return_value=sentinel):
        assert gsp._build_client() is sentinel


def test_expired_with_refresh_token_still_refreshes(wire):
    """有 refresh_token 的(手動 consent 登入)過期照舊交給 ensure_fresh_tokens 續期,不攔。"""
    wire(qp={}, session={'gsheet_tokens': {'access_token': 'AT', 'refresh_token': 'RT',
                                            'expires_at': 1}})
    sentinel = object()
    with patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
         patch('src.data.portfolio.oauth_state._get_oauth_client', return_value=sentinel):
        assert gsp._build_client() is sentinel


# ══════════════════════════════════════════════════════════════════════════
# 9. SEC-1:沒有 refresh_token 時仍每人一格
# ══════════════════════════════════════════════════════════════════════════
def _identity_for(wire, toks):
    wire(qp={}, session={'gsheet_tokens': toks})
    with patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True):
        return gsp._cache_identity()


def test_cache_identity_without_refresh_token_is_per_user_and_stable(wire):
    a1 = _identity_for(wire, {'access_token': 'AT_A1', 'expires_at': 9_999_999_999,
                              'id_token': _id_token(sub='SUB_A', email='a@x')})
    a2 = _identity_for(wire, {'access_token': 'AT_A2', 'expires_at': 9_999_999_999,
                              'id_token': _id_token(sub='SUB_A', email='a@x')})
    b = _identity_for(wire, {'access_token': 'AT_B', 'expires_at': 9_999_999_999,
                             'id_token': _id_token(sub='SUB_B', email='b@x')})
    assert a1 and b, '不得退成空字串以外的共用格,也不得是空(空 = 不用快取)'
    assert a1 == a2, '同一人兩次靜默恢復(access_token 不同)→ 同一身分(快取照常命中)'
    assert a1 != b, '不同人 → 不同身分'
    assert 'SUB_A' not in a1 and 'a@x' not in a1, '快取鍵只放雜湊'
    # 有 refresh_token 時沿用舊指紋(SEC-1 既有行為不變)
    rt = _identity_for(wire, {'access_token': 'AT', 'refresh_token': 'RT_A', 'expires_at': 1,
                              'id_token': _id_token(sub='SUB_A')})
    assert rt == gsp._identity_fingerprint(gsp._IDENTITY_KIND_OAUTH, 'RT_A')
    # 沒 sub 也沒 refresh_token → 退 access_token(每人不同,安全側 cache miss)
    x = _identity_for(wire, {'access_token': 'AT_X', 'expires_at': 9_999_999_999})
    y = _identity_for(wire, {'access_token': 'AT_Y', 'expires_at': 9_999_999_999})
    assert x and y and x != y and x != a1
    # 過期且無 refresh_token → 不用快取
    assert _identity_for(wire, {'access_token': 'AT_A1', 'expires_at': 1,
                                'id_token': _id_token(sub='SUB_A')}) == ''


def test_sec1_cached_read_isolated_between_silent_users(wire):
    """真 st.cache_data:A(sub A)讀過後,B(sub B,無 refresh_token)以相同參數讀必須真的去問 Google。"""
    from tests.test_sec1_gsheet_cache_identity import _Client
    calls: list = []
    fst = wire(qp={})

    def _oauth_client():
        return _Client(fst.session_state['gsheet_tokens']['who'], calls)

    gsp.clear_read_cache()
    try:
        with patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
             patch('src.data.portfolio.oauth_state._get_oauth_client', side_effect=_oauth_client):
            fst.session_state = {'gsheet_tokens': {'who': 'A', 'access_token': 'AT_A1',
                                                   'expires_at': 9_999_999_999,
                                                   'id_token': _id_token(sub='SUB_A')}}
            assert gsp.list_portfolios(sheet_id='SID_A') == ['A組合']
            fst.session_state = {'gsheet_tokens': {'who': 'A', 'access_token': 'AT_A2',
                                                   'expires_at': 9_999_999_999,
                                                   'id_token': _id_token(sub='SUB_A')}}
            assert gsp.list_portfolios(sheet_id='SID_A') == ['A組合']
            assert calls == [('A', 'SID_A')], '同一人靜默恢復後命中快取'
            fst.session_state = {'gsheet_tokens': {'who': 'B', 'access_token': 'AT_B',
                                                   'expires_at': 9_999_999_999,
                                                   'id_token': _id_token(sub='SUB_B')}}
            with pytest.raises(PermissionError):
                gsp.list_portfolios(sheet_id='SID_A')
            assert ('B', 'SID_A') in calls
    finally:
        gsp.clear_read_cache()


# ══════════════════════════════════════════════════════════════════════════
# 10. log 不洩漏
# ══════════════════════════════════════════════════════════════════════════
def test_logs_contain_no_nonce_token_email_url(wire, capsys):
    s1 = wire(qp={MK: MV, 'sheet': 'SHEETSECRET'})
    _run_app(s1)
    url = _redirect_url(s1)
    st_param = _qs(url)['state']
    nonce = st_param.partition('.')[0]
    s2 = wire(qp={'error': 'login_required', 'state': st_param})
    _run_app(s2)
    s3 = wire(qp={MK: MV, 'sheet': 'SHEETSECRET'})
    _run_app(s3)
    st3 = _qs(_redirect_url(s3))['state']
    s4 = wire(qp={'code': 'CODESECRET', 'state': st3})
    _run_app(s4)
    out = capsys.readouterr().out
    assert 'silent_reauth=redirect' in out
    assert 'callback error=login_required state=ok' in out
    for leaked in (nonce, st3.partition('.')[0], 'SHEETSECRET', 'CODESECRET', 'AT_SECRET',
                   'me@example.com', 'accounts.google.com', 'CSECRET', 'CID', _ME):
        assert leaked not in out, leaked


# ══════════════════════════════════════════════════════════════════════════
# AppTest:真 Streamlit runtime(st.html / st.query_params / session 都是真的)
# ══════════════════════════════════════════════════════════════════════════
_APP = '''
import os, sys
sys.path.insert(0, {root!r})
import streamlit as st
import src.data.portfolio.oauth_state as ost
ost._browser_binding = lambda: os.environ.get("B2_TEST_BINDING") or None
ost.handle_oauth_callback()
st.session_state["_silent_rv"] = ost.maybe_silent_reauth()
'''


def test_apptest_real_runtime_redirect_once(tmp_path, monkeypatch):
    for _name in ('_browser_binding',):
        monkeypatch.setattr(ost, _name, getattr(ost, _name))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = tmp_path / 'b2_app.py'
    p.write_text(_APP.format(root=root), encoding='utf-8')
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('B2_TEST_BINDING', _ME)
    at = AppTest.from_file(str(p), default_timeout=30)
    at.secrets['google_oauth'] = dict(_CFG)
    at.query_params[MK] = MV
    at.query_params['sheet'] = 'SHEET_A'
    at.run()
    assert not at.exception
    assert at.session_state['_silent_rv'] is True
    htmls = at.get('html')
    assert len(htmls) == 1
    assert htmls[0].proto.unsafe_allow_javascript is True
    assert 'prompt=none' in htmls[0].proto.body
    assert MK not in at.query_params and at.query_params.get('sheet') == ['SHEET_A']
    assert [c.value for c in at.caption] == [ost.OAUTH_SILENT_REAUTH_PENDING_MSG]
    at.run()                                  # 同 session 再跑一次 → 不再轉
    assert at.session_state['_silent_rv'] is False
    assert len(at.get('html')) == 0
