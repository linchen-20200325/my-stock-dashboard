"""vNext 1.0-B2 迴歸:重新整理後靜默恢復 Google 登入(prompt=none,不保存任何 Google 憑證;DEC-062 Q2)。

客戶硬性條件(原文):「不得保存 Google 密碼或 Google 憑證」⇒ token 只住在 session。
做法:登入強驗成功 → 網址掛非憑證記號 `?gs=<MAC(sub, sheet)>`;重新整理(新 session、無 token)
看到記號 → 標記 session、發 nonce(state＝`nonce.sheet.記號`)→ script 先 replaceState 拿掉記號再整頁轉
Google `prompt=none` → 回呼走 SEC-2 consume,並以新的 sub 重算記號比對。

稽核修正輪(2026-10-19)新增:記號綁帳號＋Sheet(攻擊者連結 / 換帳號 / 竄改 → 不登入)、
上一頁陷阱(伺服器端不拿記號,改 script replaceState)、`?error=` 只在「靜默＋靜默失敗代碼」才燒 nonce、
錯誤代碼只顯示標準表內的、登入逾時走灰卡(L1→L3→L5)。

本檔釘住(每條對應一個宣稱):
  1. 有記號的新 session → 恰好 1 個轉跳 script(先 replaceState 拿掉記號);同 session 再跑 → 0。
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
    OAUTH_LOGIN_EXPIRED_SESSION_KEY,
    OAUTH_SILENT_MARKER_PARAM as MK,
    OAUTH_SILENT_REAUTH_SECRET_KEY,
)

_ME = hashlib.sha256(b'my-browser').hexdigest()
_OTHER = hashlib.sha256(b'other-browser').hexdigest()
_CFG = {'client_id': 'CID', 'client_secret': 'CSECRET', 'redirect_uri': 'https://app.example/'}


def _tag(sub: str = 'SUB_ME', sheet: str = '') -> str:
    """登入成功時會掛上的記號值(＝ MAC(client_secret, sub, sheet))。"""
    return ost._silent_tag(_CFG['client_secret'], sub, sheet)


MV = _tag()                       # 我、沒有綁 Sheet 時的記號


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
    state = {'binding': _ME, 'cfg': dict(_CFG), 'exchanged': [], 'sub': 'SUB_ME'}
    monkeypatch.setattr(ost, '_browser_binding', lambda: state['binding'])
    monkeypatch.setattr(ost, '_resolve_oauth_cfg',
                        lambda: dict(state['cfg']) if state['cfg'] else None)

    def _exchange(code, ci, cs, ru):
        state['exchanged'].append(code)
        # 靜默恢復:Google 不發 refresh_token(本檔預設情境)
        return {'access_token': 'AT_SECRET_' + code, 'expires_at': 9_999_999_999,
                'id_token': _id_token(sub=state['sub'], email='me@example.com')}
    monkeypatch.setattr(ost, 'exchange_code_for_tokens', _exchange)

    def _wire(*, qp, session=None, secrets=None, binding=_ME, cfg=True, sub='SUB_ME'):
        state['binding'] = binding
        state['sub'] = sub          # 這個瀏覽器目前登入的 Google 帳號(Google 換 token 時回這個 sub)
        state['cfg'] = (dict(_CFG) if cfg is True else (dict(cfg) if cfg else None))
        fst = _FakeSt({} if session is None else session, qp, secrets)
        monkeypatch.setattr(ost, 'st', fst)
        monkeypatch.setattr(gsp, 'st', fst)
        fst.exchanged = state['exchanged']
        return fst
    return _wire


def _run_app(fst) -> None:
    """模擬 app.py 一輪:callback → (rerun 就再跑一輪,同 session)→ 靜默恢復 → 重算記號。"""
    for _ in range(3):
        try:
            ost.handle_oauth_callback()
        except _Rerun:
            continue
        break
    ost.maybe_silent_reauth()
    ost.sync_silent_marker()


def _redirect_url(fst) -> str:
    """從最後一個轉跳 script 取出 URL(JSON 字串常值)。"""
    body, _ = fst.htmls[-1]
    m = re.search(r'var u=(".*?");var k=', body)
    assert m, body
    return json.loads(m.group(1))


def _browser_url_after_script(fst) -> dict:
    """模擬 script 在最上層視窗執行 replaceState(拿掉記號)之後、導去 Google 之前的網址。"""
    return {k: v for k, v in fst.query_params.items() if k != MK}


def _qs(url: str) -> dict:
    return {k: v[0] for k, v in up.parse_qs(up.urlsplit(url).query).items()}


# ══════════════════════════════════════════════════════════════════════════
# 1. 有記號 → 恰好一次轉跳,記號被拿掉;同 session 再跑 → 0
# ══════════════════════════════════════════════════════════════════════════
def test_fresh_session_with_marker_redirects_exactly_once(wire):
    tag = _tag(sheet='SHEET_A')
    fst = wire(qp={MK: tag, 'sheet': 'SHEET_A'})
    _run_app(fst)
    assert len(fst.htmls) == 1
    body, unsafe = fst.htmls[0]
    assert unsafe is True, 'script 要能執行必須 unsafe_allow_javascript=True'
    # 稽核 SA2 SHOULD-1:伺服器端**不**拿記號(那會在前端 pushState 多一筆帶記號的歷史 → 上一頁陷阱),
    # 改由 script 在導頁前 replaceState 同一筆紀錄。
    assert fst.query_params.get(MK) == tag
    assert 'history.replaceState(' in body and 'searchParams.delete(k)' in body
    assert fst.query_params.get('sheet') == 'SHEET_A', 'sheet 不得被沖掉'
    assert fst.captions == [ost.OAUTH_SILENT_REAUTH_PENDING_MSG]
    assert fst.errors == [] and fst.infos == []
    url = _redirect_url(fst)
    assert url.startswith(GOOGLE_AUTH_URL + '?')
    q = _qs(url)
    assert q['prompt'] == 'none'
    nonce, sheet, got_tag = q['state'].split('.')
    assert sheet == 'SHEET_A', 'state 便車要帶著 sheet(新 session 從網址讀)'
    assert got_tag == tag, '記號跟著 state 繞 Google 一圈,回呼才能比對'
    assert ns._STORE[nonce][1] == _ME, 'nonce 走既有 get_login_state 發放並綁本瀏覽器'
    # 同一個 session 再跑(例如使用者在轉跳前點了什麼;記號仍在伺服器端網址)→ 不再轉
    _run_app(fst)
    assert len(fst.htmls) == 1
    assert fst.session_state[OAUTH_SILENT_ATTEMPTED_SESSION_KEY] is True


def test_session_guard_is_the_only_thing_stopping_a_second_redirect(wire):
    """記號留在伺服器端網址 ⇒ 同 session 不再轉,完全靠 session 旗標(拿掉它這條必紅)。"""
    fst = wire(qp={MK: MV})
    for _ in range(4):
        _run_app(fst)
    assert len(fst.htmls) == 1


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


@pytest.mark.parametrize('val', ['1', '0', '', 'true', 'a' * 31, 'a' * 33, 'A' * 32, 'g' * 32,
                                 'a' * 31 + '.'])
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
    i_sync = src.index('    _oauth_sync()')
    assert i_si < i_sync and '\n' not in src[src.index('\n', i_si) + 1:i_sync].strip()
    i_sb_write = src.index("st.query_params['sheet'] = _sb_sid_new")
    assert src.index('_sb_sync_silent()', i_sb_write) < src.index('if _sb_sid_new:', i_sb_write)
    i_logout = src.index("key='btn_oauth_logout_sb'")
    i_forget = src.index('_sb_forget_silent()', i_logout)
    assert i_forget < src.index('st.rerun()', i_logout)


# ══════════════════════════════════════════════════════════════════════════
# 3. Google 一直回 login_required → 不迴圈,每次失敗都有訊息
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize('err', sorted(OAUTH_SILENT_FAILURE_ERROR_CODES))
def test_google_always_errors_no_loop(wire, err):
    url_now = {'sheet': 'S', MK: _tag(sheet='S')}   # 使用者上次登入成功後的網址
    redirects, failures = 0, 0
    for _refresh in range(6):
        fst = wire(qp=dict(url_now))         # 每次重新整理 = 新 session
        _run_app(fst)
        url_now = dict(fst.query_params)
        if fst.htmls:
            redirects += 1
            url_now = _browser_url_after_script(fst)    # script:replaceState 拿掉記號 → 導 Google
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


def test_script_could_not_navigate_next_refresh_tries_once_more(wire):
    """跨來源 iframe:script 什麼都不做 ⇒ 網址原封不動 ⇒ 下一次重新整理再試一次(每次動作最多一次)。"""
    url_now = {MK: MV}
    for n in range(1, 4):
        fst = wire(qp=dict(url_now))
        _run_app(fst)
        _run_app(fst)                       # 同 session 多跑幾輪也只有一次
        assert len(fst.htmls) == 1
        url_now = dict(fst.query_params)    # 沒導走:網址仍帶記號
        assert url_now.get(MK) == MV


def test_error_branch_burns_nonce_and_restores_sheet_from_strong_state(wire):
    fst = wire(qp={MK: _tag(sheet='S1'), 'sheet': 'S1'})
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
    landing = wire(qp={'error': 'login_required', 'state': 'N_OTHER.EVIL.' + MV})
    _run_app(landing)
    assert 'portfolio_sheet_id' not in landing.session_state, 'consume 沒過 → 不回綁 session'
    # 稽核第二輪:靜默 state 的 Sheet 只寫回網址(網址層級,既有信任模型)
    assert dict(landing.query_params) == {'sheet': 'EVIL'}
    assert landing.infos == [ost.OAUTH_SILENT_REAUTH_FAILED_MSG]


@pytest.mark.parametrize('code,msg', [
    ('access_denied', ost.OAUTH_LOGIN_INCOMPLETE_MSG.format(code='access_denied')),
    ('server_error', ost.OAUTH_LOGIN_INCOMPLETE_MSG.format(code='server_error')),
    ('visit-evil.com-to-fix', ost.OAUTH_LOGIN_INCOMPLETE_GENERIC_MSG),   # 稽核 SA1 NIT-1
    ('<script>x</script>', ost.OAUTH_LOGIN_INCOMPLETE_GENERIC_MSG),
    ('', ost.OAUTH_LOGIN_INCOMPLETE_GENERIC_MSG)])
def test_error_branch_other_codes_message(wire, code, msg):
    landing = wire(qp={'error': code, 'sheet': 'KEEP'})       # 沒有 state 也要處理
    _run_app(landing)
    assert landing.infos == [msg]
    assert 'evil' not in ''.join(landing.infos)
    assert dict(landing.query_params) == {'sheet': 'KEEP'}
    assert landing.errors == [] and landing.successes == [] and landing.htmls == []


def test_cancel_in_tab2_then_retry_from_tab1_still_works(wire):
    """稽核 SA2 SHOULD-2:登入鈕在新分頁開 Google、按取消(access_denied + 一般 state)⇒ **不燒** nonce;
    回原分頁再按同一顆鈕(同一個 nonce)要能登入(修前會被當成重放 → 紅字)。"""
    ns.issue('N1', _ME)                                       # 分頁 1 的登入鈕
    tab2 = wire(qp={'error': 'access_denied', 'state': 'N1.SHEET_A'})
    _run_app(tab2)
    assert tab2.infos == [ost.OAUTH_LOGIN_INCOMPLETE_MSG.format(code='access_denied')]
    assert 'portfolio_sheet_id' not in tab2.session_state, '沒 consume 就不信 state 載荷'
    assert 'N1' in ns._STORE, '非靜默的錯誤不得燒 nonce'
    tab1_retry = wire(qp={'code': 'C', 'state': 'N1.SHEET_A'})
    _run_app(tab1_retry)
    assert tab1_retry.errors == []
    assert tab1_retry.session_state['gsheet_tokens']['access_token'] == 'AT_SECRET_C'


@pytest.mark.parametrize('state_fn', [lambda: 'N1', lambda: 'N1.S'])
def test_silent_error_code_without_silent_state_does_not_burn(wire, state_fn):
    ns.issue('N1', _ME)
    landing = wire(qp={'error': 'login_required', 'state': state_fn()})
    _run_app(landing)
    assert 'N1' in ns._STORE
    assert landing.infos == [ost.OAUTH_SILENT_REAUTH_FAILED_MSG]


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
    assert dict(fst.query_params) == {'sheet': 'SHEET_A', MK: _tag(sheet='SHEET_A')}
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
    assert dict(s1.query_params) == {'sheet': 'SH', MK: _tag(sheet='SH')}
    s2 = wire(qp=dict(s1.query_params))                    # 重新整理
    _run_app(s2)
    assert len(s2.htmls) == 1 and 'gsheet_tokens' not in s2.session_state
    st_param = _qs(_redirect_url(s2))['state']
    s3 = wire(qp={'code': 'C1', 'state': st_param})       # Google prompt=none 成功帶 code 回來
    _run_app(s3)
    assert s3.session_state['gsheet_tokens']['access_token'] == 'AT_SECRET_C1'
    assert s3.session_state['portfolio_sheet_id'] == 'SH'
    assert dict(s3.query_params) == {'sheet': 'SH', MK: _tag(sheet='SH')}, '恢復後記號重新掛上'
    assert s3.htmls == []


# ══════════════════════════════════════════════════════════════════════════
# 5b. 記號綁帳號＋Sheet(稽核 SA1 SHOULD-1 ＋ 換帳號)
# ══════════════════════════════════════════════════════════════════════════
def _silent_roundtrip(wire, *, url, sub, tamper=None):
    """重新整理(帶 url)→ 轉跳 → Google 以 `sub` 這個帳號回 code → 回呼。回落地那一個 session。"""
    s = wire(qp=dict(url), sub=sub)
    _run_app(s)
    assert len(s.htmls) == 1
    st_param = _qs(_redirect_url(s))['state']
    if tamper:
        st_param = tamper(st_param)
    landing = wire(qp={'code': 'CS', 'state': st_param}, sub=sub)
    _run_app(landing)
    landing.state_sheet = ost._split_silent_state(st_param)[1]
    return landing


def _assert_silent_rejected(landing):
    assert 'gsheet_tokens' not in landing.session_state, '不得登入'
    assert 'gsheet_email' not in landing.session_state
    assert 'portfolio_sheet_id' not in landing.session_state, '不得回綁'
    assert 'stock_portfolio_sheet_id' not in landing.session_state
    # 稽核第二輪 MUST-1(b):不登入、不回綁 session、不掛記號;但 state 帶回的 Sheet 寫回**網址**
    # (網址層級 ＝ app.py v19.204 `?sheet=` 還原的既有信任等級 —— 攻擊者本來就能直接寄 `?sheet=EVIL`)。
    assert MK not in landing.query_params
    _ss = landing.state_sheet
    assert dict(landing.query_params) == ({'sheet': _ss} if _ss else {})
    assert landing.infos == [ost.OAUTH_SILENT_MISMATCH_MSG]
    assert landing.errors == [] and landing.successes == []


@pytest.mark.parametrize('forged', ['0' * 32, 'deadbeef' * 4, _tag(sub='SUB_ME', sheet='')])
def test_attacker_link_with_own_sheet_does_not_log_in_or_bind(wire, forged):
    """`?gs=<偽造 / 亂數 / 別本 Sheet 的合法記號>&sheet=EVIL` 寄給受害者 → 零點擊也不會登入、不會綁 EVIL。"""
    landing = _silent_roundtrip(wire, url={MK: forged, 'sheet': 'EVIL'}, sub='SUB_ME')
    _assert_silent_rejected(landing)


def test_different_google_account_does_not_log_in(wire):
    """同一台電腦換了 Google 帳號:記號是我(SUB_ME)的,Google 回的是別人(SUB_OTHER)→ 不靜默登入。"""
    landing = _silent_roundtrip(wire, url={MK: _tag(sheet='S'), 'sheet': 'S'}, sub='SUB_OTHER')
    _assert_silent_rejected(landing)


def test_same_account_same_sheet_succeeds(wire):
    landing = _silent_roundtrip(wire, url={MK: _tag(sheet='S'), 'sheet': 'S'}, sub='SUB_ME')
    assert landing.session_state['gsheet_tokens']['access_token'] == 'AT_SECRET_CS'
    assert landing.session_state['portfolio_sheet_id'] == 'S'


@pytest.mark.parametrize('tamper', [
    lambda st_: st_[:-1] + ('0' if st_[-1] != '0' else '1'),    # 改記號最後一碼
    lambda st_: st_.rsplit('.', 1)[0] + '.zz',                   # 記號格式不合
    lambda st_: st_.rsplit('.', 1)[0] + '.',                     # 記號空白(仍是三段)
    lambda st_: st_.replace('.S.', '.EVIL.'),                    # 換 Sheet、記號不變
])
def test_tampered_state_tag_does_not_log_in(wire, tamper):
    landing = _silent_roundtrip(wire, url={MK: _tag(sheet='S'), 'sheet': 'S'}, sub='SUB_ME',
                                tamper=tamper)
    _assert_silent_rejected(landing)


def test_no_client_secret_disables_silent_reauth(wire, capsys):
    fst = wire(qp={MK: MV}, cfg={'client_id': 'CID', 'client_secret': '',
                                 'redirect_uri': 'https://app.example/'})
    _run_app(fst)
    assert fst.htmls == []
    assert 'silent_reauth=skip reason=no_client_secret' in capsys.readouterr().out
    assert ost._silent_tag('', 'SUB', 'S') == ''


def test_marker_not_set_without_sub(wire, monkeypatch, capsys):
    ns.issue('N1', _ME)
    fst = wire(qp={'code': 'C', 'state': 'N1.S'})
    monkeypatch.setattr(ost, 'exchange_code_for_tokens',
                        lambda *a: {'access_token': 'AT', 'expires_at': 9_999_999_999})
    _run_app(fst)
    assert 'gsheet_tokens' in fst.session_state
    assert MK not in fst.query_params
    assert 'marker_not_set_no_sub' in capsys.readouterr().out


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
    m = re.fullmatch(r'<script>\(function\(\)\{var u=(".*?");var k="gs";var t;(.*)\}\)\(\);</script>',
                     body)
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


def test_script_removes_marker_with_replace_state_before_navigating():
    """稽核 SA2 SHOULD-1(上一頁陷阱):在**要導的那個視窗**上先 replaceState 拿掉記號,成功後才導走。"""
    body = ost._silent_redirect_script(GOOGLE_AUTH_URL + '?a=1')
    i_probe = body.index('void t.location.href;')
    i_url = body.index('new URL(t.location.href)')
    i_del = body.index('l.searchParams.delete(k)')
    i_rs = body.index("t.history.replaceState(null,'',l.toString())")
    i_nav = body.index('t.location.replace(u)')
    assert i_probe < i_url < i_del < i_rs < i_nav
    # replaceState 失敗 → return(不導):replaceState 與 replace 不在同一個 try 裡,中間隔著 return
    assert body[i_rs:i_nav].count('catch(e){return;}') == 1
    assert 'pushState' not in body and 'window.history' not in body, '只動最上層視窗(t)的歷史'


def test_malicious_sheet_id_never_reaches_script(wire):
    fst = wire(qp={MK: MV, 'sheet': 'S";alert(1);//</script>'})
    _run_app(fst)
    url = _redirect_url(fst)
    _nonce, _sheet, _tg = _qs(url)['state'].split('.')
    assert _sheet == '' and _tg == MV, '消毒不過的 sheet 不上 state 便車(只剩記號)'
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
    # 之後「沒有 token」的讀取仍說「已逾時」(不是「請先登入」)
    assert fst.session_state[OAUTH_LOGIN_EXPIRED_SESSION_KEY] is True
    with patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True):
        with pytest.raises(gsp.LoginRequiredError) as ei2:
            gsp._build_client()
    assert str(ei2.value) == gsp.LOGIN_EXPIRED_MSG
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
    s1 = wire(qp={MK: _tag(sheet='SHEETSECRET'), 'sheet': 'SHEETSECRET'})
    _run_app(s1)
    url = _redirect_url(s1)
    st_param = _qs(url)['state']
    nonce = st_param.partition('.')[0]
    s2 = wire(qp={'error': 'login_required', 'state': st_param})
    _run_app(s2)
    s3 = wire(qp={MK: _tag(sheet='SHEETSECRET'), 'sheet': 'SHEETSECRET'})
    _run_app(s3)
    st3 = _qs(_redirect_url(s3))['state']
    s4 = wire(qp={'code': 'CODESECRET', 'state': st3})
    _run_app(s4)
    out = capsys.readouterr().out
    assert 'silent_reauth=redirect' in out
    assert 'callback error=login_required state=ok' in out
    for leaked in (nonce, st3.partition('.')[0], st3.rsplit('.', 1)[1], MV, 'SHEETSECRET',
                   'CODESECRET', 'AT_SECRET',
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
    at.query_params[MK] = _tag(sheet='SHEET_A')
    at.query_params['sheet'] = 'SHEET_A'
    at.run()
    assert not at.exception
    assert at.session_state['_silent_rv'] is True
    htmls = at.get('html')
    assert len(htmls) == 1
    assert htmls[0].proto.unsafe_allow_javascript is True
    assert 'prompt=none' in htmls[0].proto.body
    assert 'history.replaceState(' in htmls[0].proto.body
    # 伺服器端不拿記號(上一頁陷阱);script 在瀏覽器端拿
    assert at.query_params.get(MK) == [_tag(sheet='SHEET_A')]
    assert at.query_params.get('sheet') == ['SHEET_A']
    assert [c.value for c in at.caption] == [ost.OAUTH_SILENT_REAUTH_PENDING_MSG]
    at.run()                                  # 同 session 再跑一次 → 不再轉
    assert at.session_state['_silent_rv'] is False
    assert len(at.get('html')) == 0


# ══════════════════════════════════════════════════════════════════════════
# 11. 稽核 SA2 MUST-1:登入逾時一路 L1 → L3 → L5 都是灰卡、文案是「已逾時」
# ══════════════════════════════════════════════════════════════════════════
def _expired_session():
    return {'gsheet_tokens': {'access_token': 'AT_OLD', 'expires_at': 1,
                              'id_token': _id_token(sub='SUB_ME')},
            'gsheet_email': 'me@example.com',
            gsp.PORTFOLIO_SHEET_KEY: 'SID_A', gsp.STOCK_PORTFOLIO_SHEET_KEY: 'SID_A'}


def test_expiry_chain_l1_l3_l5_renders_gray_with_expiry_text(wire):
    """修前:binding 讀組合清單 → L1 清 session 拋 LOGIN_EXPIRED → 被 L3 吞成舊的 logged_in=True/bound →
    持股再讀一次 → 「請先登入」→ 頁面紅卡 ＋ repr。修後:兩張卡都是灰、都寫「Google 登入已逾時」。"""
    from shared.ui_state import UI_EMPTY, UI_FAILED
    from src.services.holdings_service import get_holdings
    from src.services.portfolio_binding_service import STATUS_UNBOUND, get_binding_state
    from src.ui.views import page_hold as P

    fst = wire(qp={MK: MV}, session=_expired_session())
    gsp.clear_read_cache()
    with patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True), \
         patch('src.data.portfolio.oauth_state._get_oauth_client',
               side_effect=AssertionError('不得走到 ensure_fresh_tokens')):
        bs = get_binding_state()
        assert (bs.logged_in, bs.status, bs.login_expired, bs.read_error) == (
            False, STATUS_UNBOUND, True, ''), '⛔ 不得回舊的 logged_in=True / bound'
        assert 'gsheet_tokens' not in fst.session_state
        hr = get_holdings(keep_blank=True)
        assert (hr.bound, hr.logged_in, hr.login_expired, hr.holdings) == (False, False, True, ())

        req = P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING)
        b = P.load_binding(req)
        h = P.load_holdings(req)
    assert b.error == '' and h.error == ''
    assert b.login_expired and h.login_expired
    for card in (P.build_binding_card(b)[0], P.build_holdings_preview_card(h)[0],
                 P.build_lightwall_card(P.load_station(h))[0]):
        assert card.state == UI_EMPTY != UI_FAILED, card.key
        assert card.note.now == P.LOGIN_EXPIRED_NOW, card.key
        assert gsp.LOGIN_EXPIRED_MSG in card.note.where
        assert 'LoginRequiredError' not in (card.note.why + card.note.where)
    # 不轉跳(session 中途)
    _run_app(fst)
    assert fst.htmls == []


def test_holdings_service_race_login_cleared_between_calls_reaches_page_as_gray(wire, monkeypatch):
    """binding 那一刻還登入,持股讀組合清單時才逾時:L3 照舊往上拋(投資組合那半 fail loud 不變),
    頁面經 `is_login_required_error()` 轉成灰色「登入已逾時」卡。"""
    from shared.ui_state import UI_EMPTY
    from src.services import portfolio_binding_service as PBS
    from src.ui.views import page_hold as P

    wire(qp={})
    monkeypatch.setattr(PBS, 'get_binding_state', lambda: PBS.BindingState(
        logged_in=True, sheet_id='SID_A', portfolio_count=1, status=PBS.STATUS_BOUND))

    def _raise(**_k):
        gsp.st.session_state[OAUTH_LOGIN_EXPIRED_SESSION_KEY] = True
        raise gsp.LoginRequiredError(gsp.LOGIN_EXPIRED_MSG)
    monkeypatch.setattr(gsp, 'list_portfolios', _raise)
    h = P.load_holdings(P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING))
    assert h.error == '' and h.login_expired and not h.bound
    card = P.build_holdings_preview_card(h)[0]
    assert card.state == UI_EMPTY and card.note.now == P.LOGIN_EXPIRED_NOW


def test_page_hold_load_holdings_maps_login_required_to_gray(wire, monkeypatch):
    from shared.ui_state import UI_EMPTY
    from src.services import holdings_service as HS
    from src.ui.views import page_hold as P

    def _raise(**_k):
        raise gsp.LoginRequiredError(gsp.LOGIN_EXPIRED_MSG)
    monkeypatch.setattr(HS, 'get_holdings', _raise)
    h = P.load_holdings(P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING))
    assert h.error == '' and h.login_expired and not h.bound
    assert P.build_holdings_preview_card(h)[0].state == UI_EMPTY

    def _raise2(**_k):
        raise gsp.LoginRequiredError(gsp.LOGIN_REQUIRED_MSG)
    monkeypatch.setattr(HS, 'get_holdings', _raise2)
    h2 = P.load_holdings(P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING))
    assert h2.error == '' and not h2.login_expired
    assert P.build_holdings_preview_card(h2)[0].note.now == P.NOT_BOUND_NOW

    def _boom(**_k):
        raise RuntimeError('boom')
    monkeypatch.setattr(HS, 'get_holdings', _boom)
    h3 = P.load_holdings(P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING))
    assert h3.error, '真正的讀取失敗照舊紅'


def test_expired_flag_cleared_on_login_and_logout(wire):
    ns.issue('N1', _ME)
    fst = wire(qp={'code': 'C', 'state': 'N1'}, session={OAUTH_LOGIN_EXPIRED_SESSION_KEY: True})
    _run_app(fst)
    assert 'gsheet_tokens' in fst.session_state
    assert OAUTH_LOGIN_EXPIRED_SESSION_KEY not in fst.session_state, '重新登入後不再是「已逾時」'
    fst2 = wire(qp={MK: MV}, session={OAUTH_LOGIN_EXPIRED_SESSION_KEY: True})
    ost.forget_silent_reauth()
    assert OAUTH_LOGIN_EXPIRED_SESSION_KEY not in fst2.session_state
    with patch('src.data.portfolio.oauth_state.is_oauth_configured', return_value=True):
        with pytest.raises(gsp.LoginRequiredError) as ei:
            gsp._build_client()
    assert str(ei.value) == gsp.LOGIN_REQUIRED_MSG


# ══════════════════════════════════════════════════════════════════════════
# 還原鏈(稽核修正輪動到 `src/ui/views/page_hold.py`)
# ══════════════════════════════════════════════════════════════════════════
#: 本輪(1.0-B2 稽核修正)對 page_hold 的改動 → 換回 23596359 的寫法。舊批次的「還原到基底」守衛
#: (`test_batch_c21` / `test_batch_z66b` 經 `tests/test_uia_01_02_07_data_state.uia_revert_for`)
#: 會先套本表再套它們自己的,⛔ 不必改它們寫死的基底 sha。本表由 difflib 自動產生後逐字貼上,
#: 下方 `test_vn1b2_revert_is_exact_base_source` 釘住「換回去 == 23596359 的原文(sha 寫死)」。
VN1B2_BASE_SHA = {"src/ui/views/page_hold.py": "471cb1155e7b737dc9a1592e14d8587aadddaead103a66b99e3bfcd562f98d7a"}
VN1B2_REVERT_PAIRS = {
    "src/ui/views/page_hold.py": (
        ('    綁定狀態      L3 `services.portfolio_binding_service.get_binding_state`\n    沒登入判斷    L3 `services.portfolio_binding_service.is_login_required_error`  ← 1.0-B2（純判斷式，唯讀）\n    VIX（單獨）   L3 `services.dividend_station_service.fetch_vix`\n',
         '    綁定狀態      L3 `services.portfolio_binding_service.get_binding_state`\n    VIX（單獨）   L3 `services.dividend_station_service.fetch_vix`\n'),
        ('# L0：要畫上畫面的上游例外字串，先洗掉金鑰／Sheet ID／檔案路徑（Q1-r5，2026-09-26）。\nfrom shared.oauth_session_policy import OAUTH_LOGIN_EXPIRED_MSG\nfrom shared.secret_scrub import scrub_secrets\n',
         '# L0：要畫上畫面的上游例外字串，先洗掉金鑰／Sheet ID／檔案路徑（Q1-r5，2026-09-26）。\nfrom shared.secret_scrub import scrub_secrets\n'),
        ('    error: str = ""\n    #: 1.0-B2:登入已逾時(L3 `BindingState.login_expired`)→ 「未綁」灰卡改寫成「登入已逾時」(仍是灰)。\n    login_expired: bool = False\n\n',
         '    error: str = ""\n\n'),
        ('        submitted=req.submitted,\n        login_expired=bool(getattr(_s, "login_expired", False)),\n        logged_in=bool(getattr(_s, "logged_in", False)),\n',
         '        submitted=req.submitted,\n        logged_in=bool(getattr(_s, "logged_in", False)),\n'),
        ('    error: str = ""\n    #: 1.0-B2:登入已逾時 → `bound=False` ＋ 空清單,卡片畫灰色「登入已逾時」(⛔ 不是紅色讀取失敗)。\n    login_expired: bool = False\n\n',
         '    error: str = ""\n\n'),
        ('    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞\n        # 1.0-B2(稽核 SA2 MUST-1):「沒有登入 / 登入已逾時」(L1 `LoginRequiredError`)不是讀取失敗 →\n        # 走既有的灰色「未綁」那一條(逾時時文案換成「登入已逾時」),⛔ 不進紅卡。\n        # L5 不 import L1:經 L3 `is_login_required_error()` 判斷(§8.2)。\n        from src.services.portfolio_binding_service import is_login_required_error\n        if is_login_required_error(_e):\n            print("[views/page_hold] 持股清單：未登入 / 登入已逾時 → 灰卡（不是讀取失敗）")\n            return HoldingsReadout(\n                requested=True, submitted=req.submitted, bound=False,\n                login_expired=str(_e) == OAUTH_LOGIN_EXPIRED_MSG)\n        print(f"[views/page_hold] 持股清單讀取失敗 → 轉紅態：{scrub_secrets(repr(_e))}")\n',
         '    except Exception as _e:  # noqa: BLE001 — 轉成紅態顯示，不吞\n        print(f"[views/page_hold] 持股清單讀取失敗 → 轉紅態：{scrub_secrets(repr(_e))}")\n'),
        ('        more_watchlists=bool(getattr(_h, "more_watchlists", False)),\n        watchlist_error=str(getattr(_h, "watchlist_error", "") or ""),\n        login_expired=bool(getattr(_h, "login_expired", False)))\n\n',
         '        more_watchlists=bool(getattr(_h, "more_watchlists", False)),\n        watchlist_error=str(getattr(_h, "watchlist_error", "") or ""))\n\n'),
        ('    holdings_n: int = 0\n    #: 1.0-B2:由 `HoldingsReadout.login_expired` 帶下來 —— 「還沒綁」那幾張灰卡改說「登入已逾時」。\n    login_expired: bool = False\n    rows: tuple[dict, ...] = ()\n',
         '    holdings_n: int = 0\n    rows: tuple[dict, ...] = ()\n'),
        ('        return StationReadout(requested=True, submitted=holdings.submitted,\n                              bound=holdings.bound, login_expired=holdings.login_expired)\n    try:\n',
         '        return StationReadout(requested=True, submitted=holdings.submitted,\n                              bound=holdings.bound)\n    try:\n'),
        ('\n#: 1.0-B2(稽核 SA2 MUST-1):**登入已逾時**時取代上面那組「還沒綁」(同一批卡、同一個灰色)。\n#: 修前這一態一路變成紅卡 ＋ 例外 repr(「請先登入 Google 才能讀取持股」,還說錯了原因)。\n#: where 直接用 L0 那一句(`OAUTH_LOGIN_EXPIRED_MSG`,L1 拋例外也是同一句,⛔ 不寫第二份)。\nLOGIN_EXPIRED_NOW: str = "**Google 登入已逾時**"\nLOGIN_EXPIRED_WHY: str = (\n    "本站**不保存任何 Google 憑證**，登入只活在這個分頁的這一段連線裡；"\n    "自動恢復的登入大約 1 小時後就會逾時。**這不是故障**，你的 Sheet 也沒有出問題")\nLOGIN_EXPIRED_WHERE: str = OAUTH_LOGIN_EXPIRED_MSG\n\n\ndef _not_bound_note(login_expired: bool) -> Note:\n    """「還沒綁 / 沒登入」那一句 —— 登入已逾時時換成逾時那一組(兩者都是灰色有效態)。"""\n    if login_expired:\n        return Note(now=LOGIN_EXPIRED_NOW, why=LOGIN_EXPIRED_WHY, where=LOGIN_EXPIRED_WHERE)\n    return Note(now=NOT_BOUND_NOW, why=NOT_BOUND_WHY, where=NOT_BOUND_WHERE)\n\n\nEMPTY_SHEET_NOW: str = "**Sheet 綁好了，但裡面還沒有任何一列持股**"\n',
         '\nEMPTY_SHEET_NOW: str = "**Sheet 綁好了，但裡面還沒有任何一列持股**"\n'),
        ('        return Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY, where=EMPTY_SHEET_WHERE)\n    return _not_bound_note(station.login_expired)\n\n',
         '        return Note(now=EMPTY_SHEET_NOW, why=EMPTY_SHEET_WHY, where=EMPTY_SHEET_WHERE)\n    return Note(now=NOT_BOUND_NOW, why=NOT_BOUND_WHY, where=NOT_BOUND_WHERE)\n\n'),
        ('    holdings_n: int = 0\n    #: 1.0-B2:由戰情表帶下來(同 `StationReadout.login_expired`)。\n    login_expired: bool = False\n    has_station_rows: bool = False\n',
         '    holdings_n: int = 0\n    has_station_rows: bool = False\n'),
        ('    _shared = {"submitted": station.submitted, "bound": station.bound,\n               "holdings_n": station.holdings_n, "login_expired": station.login_expired}\n    if not station.requested:\n',
         '    _shared = {"submitted": station.submitted, "bound": station.bound,\n               "holdings_n": station.holdings_n}\n    if not station.requested:\n'),
        ('                    where=EMPTY_SHEET_WHERE)\n    return _not_bound_note(deep.login_expired)\n\n',
         '                    where=EMPTY_SHEET_WHERE)\n    return Note(now=NOT_BOUND_NOW, why=NOT_BOUND_WHY, where=NOT_BOUND_WHERE)\n\n'),
        ('        #    改的時候一定會漏改一份，於是兩張卡對同一個狀況給出兩種說法。\n        _note = _not_bound_note(binding.login_expired)\n    return Card(key="hold.binding", label="Google Sheet 綁定",\n',
         '        #    改的時候一定會漏改一份，於是兩張卡對同一個狀況給出兩種說法。\n        _note = Note(now=NOT_BOUND_NOW, why=NOT_BOUND_WHY, where=NOT_BOUND_WHERE)\n    return Card(key="hold.binding", label="Google Sheet 綁定",\n'),
        ('    else:\n        _note = _not_bound_note(holdings.login_expired)\n    return Card(key="hold.setup.preview", label="持股列預覽",\n',
         '    else:\n        _note = Note(now=NOT_BOUND_NOW, why=NOT_BOUND_WHY, where=NOT_BOUND_WHERE)\n    return Card(key="hold.setup.preview", label="持股列預覽",\n'),
        ('                    "用 Google 登入後選一本持股 Sheet" + V2_EXCERPT_GAP + "現行入口在側欄「🔐 Google 帳號」"),\n    LOGIN_EXPIRED_NOW: ("Google 登入已逾時",\n                        "自動恢復的登入大約 1 小時後就會逾時",\n                        "請重新整理頁面以自動恢復登入"),\n    EMPTY_SHEET_NOW: ("Sheet 綁好了，但裡面還沒有任何一列持股",\n',
         '                    "用 Google 登入後選一本持股 Sheet" + V2_EXCERPT_GAP + "現行入口在側欄「🔐 Google 帳號」"),\n    EMPTY_SHEET_NOW: ("Sheet 綁好了，但裡面還沒有任何一列持股",\n'),
        ('    + [_v2_rows_for(_k, NOT_BOUND_NOW, _V2_SHARED_SHORT[NOT_BOUND_NOW])\n       for _k in _V2_NOT_BOUND_KEYS]\n    # 1.0-B2:「登入已逾時」與「還沒綁」出現在**同一批卡**(同一個 `_not_bound_note()`)。\n    + [_v2_rows_for(_k, LOGIN_EXPIRED_NOW, _V2_SHARED_SHORT[LOGIN_EXPIRED_NOW])\n       for _k in _V2_NOT_BOUND_KEYS]\n',
         '    + [_v2_rows_for(_k, NOT_BOUND_NOW, _V2_SHARED_SHORT[NOT_BOUND_NOW])\n       for _k in _V2_NOT_BOUND_KEYS]\n'),
    ),
}


def vn1b2_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`(或 repo 相對路徑)與原始碼,換回本輪之前的寫法(無 pair 則原樣)。"""
    from pathlib import Path
    _repo = Path(__file__).resolve().parents[1]
    p = Path(file_path)
    rel = (p.resolve().relative_to(_repo) if p.is_absolute() else p).as_posix()
    # VN1-STORE 最小 PoC（2026-10-19，有意識的接鏈，⛔ 不是漏改）：更新的那一批先換回（還原鏈頭往前接一節）。
    from tests.test_vn1_store_poc import vn1store_revert_for
    code = vn1store_revert_for(file_path, code)
    for new, old in VN1B2_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def test_vn1b2_revert_is_exact_base_source():
    from pathlib import Path
    _repo = Path(__file__).resolve().parents[1]
    for rel in sorted(VN1B2_REVERT_PAIRS):
        code = vn1b2_revert_for(rel, (_repo / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == VN1B2_BASE_SHA[rel], rel



# ══════════════════════════════════════════════════════════════════════════
# 12. 稽核修正第二輪 MUST-1:登入後才綁 / 換 Sheet → 重算記號;靜默沒成功時 Sheet 不弄丟
# ══════════════════════════════════════════════════════════════════════════
def _login_strict(wire, *, sheet='', sub='SUB_ME', secrets=None):
    """手動按登入鈕、強驗通過(回落地 session;網址＝登入後的網址)。"""
    ns.issue('NL', _ME)
    fst = wire(qp={'code': 'C0', 'state': 'NL.' + sheet if sheet else 'NL'}, sub=sub,
               secrets=secrets)
    _run_app(fst)
    assert 'gsheet_tokens' in fst.session_state
    return fst


def _bind_sheet_like_sidebar(fst, sid):
    """app.py 側欄:寫兩通道 + `?sheet=` → 就地 `sync_silent_marker()`(這一輪不會再 rerun)。"""
    fst.session_state['portfolio_sheet_id'] = sid
    fst.session_state['stock_portfolio_sheet_id'] = sid
    fst.query_params['sheet'] = sid
    return ost.sync_silent_marker()


def test_login_then_bind_sheet_remints_marker_and_refresh_restores_with_sheet(wire):
    s1 = _login_strict(wire)
    assert dict(s1.query_params) == {MK: _tag(sheet='')}
    assert _bind_sheet_like_sidebar(s1, 'SID') is True
    assert s1.query_params[MK] == _tag(sheet='SID'), '記號跟著新 Sheet 重算'
    # 重新整理 → 靜默恢復 → 帶 SID 成功
    s2 = wire(qp=dict(s1.query_params))
    _run_app(s2)
    st_param = _qs(_redirect_url(s2))['state']
    s3 = wire(qp={'code': 'C1', 'state': st_param})
    _run_app(s3)
    assert s3.session_state['gsheet_tokens']['access_token'] == 'AT_SECRET_C1'
    assert s3.session_state['portfolio_sheet_id'] == 'SID'
    assert dict(s3.query_params) == {'sheet': 'SID', MK: _tag(sheet='SID')}


def test_binder_path_resyncs_on_the_hook_after_its_rerun(wire, monkeypatch):
    """📁 組合管理 / 就地綁定(真的 `portfolio_binder.apply_active_sheet`:寫 session 兩通道 ＋ `?sheet=`,
    不碰 gs)之後都會 st.rerun → app.py 頂端的 hook 在那一輪重算(⛔ 不改凍結的舊 UI 檔)。

    📌 第三輪(2026-10-19,有意識的修改):修前本條只改網址 `s1.query_params['sheet'] = 'SID2'`、**沒寫 session**,
    與真的 `apply_active_sheet` 不符(它先寫 session 兩通道再寫網址)。現在直接呼叫真函式;
    sync 只信 session 的 Sheet,只改網址的那種寫法已不會(也不該)重算 —— 見下一條。"""
    from src.ui.tabs import portfolio_binder as PB
    s1 = _login_strict(wire)
    monkeypatch.setattr(PB, 'st', s1)
    PB.apply_active_sheet(gsp, 'SID2')
    assert s1.session_state['portfolio_sheet_id'] == 'SID2' and s1.query_params['sheet'] == 'SID2'
    assert MK in s1.query_params and s1.query_params[MK] == _tag(sheet=''), 'apply_active_sheet 不碰 gs'
    _run_app(s1)                               # st.rerun 之後的那一輪
    assert s1.query_params[MK] == _tag(sheet='SID2')
    # 重新整理 → 靜默恢復帶 SID2 成功
    s2 = wire(qp=dict(s1.query_params))
    _run_app(s2)
    s3 = wire(qp={'code': 'C1', 'state': _qs(_redirect_url(s2))['state']})
    _run_app(s3)
    assert s3.session_state['gsheet_tokens'] and s3.session_state['portfolio_sheet_id'] == 'SID2'


# ── 第三輪(客戶核准):已登入分頁的 Sheet 只信 session 設定值 ─────────────────────────
def test_tampered_url_sheet_in_logged_in_session_is_not_minted(wire, capsys):
    """已登入、綁 VICTIM;網址被外部改成 `?sheet=EVIL`(session 仍是 VICTIM)並觸發 rerun →
    ⛔ 不得替自己的 sub 算出 MAC(sub, EVIL);之後重新整理也不會靜默綁上 EVIL。"""
    s1 = _login_strict(wire, sheet='VICTIM')
    assert s1.session_state['portfolio_sheet_id'] == 'VICTIM'
    good = s1.query_params[MK]
    assert good == _tag(sheet='VICTIM')
    s1.query_params.clear()
    s1.query_params.update({'sheet': 'EVIL', MK: good})     # 外部改 query(例:host 訊息)
    _run_app(s1)                                           # 被觸發的那一輪
    _run_app(s1)
    assert s1.query_params[MK] == good != _tag(sheet='EVIL'), '不得替 EVIL 重算記號'
    out = capsys.readouterr().out
    assert out.count('resync_skip reason=url_sheet_not_session_sheet') == 1
    assert 'EVIL' not in out and 'VICTIM' not in out
    # 使用者接著重新整理(網址帶 EVIL ＋ VICTIM 的記號)→ 不會靜默綁 EVIL
    s2 = wire(qp=dict(s1.query_params))
    _run_app(s2)
    s3 = wire(qp={'code': 'C1', 'state': _qs(_redirect_url(s2))['state']})
    _run_app(s3)
    assert 'gsheet_tokens' not in s3.session_state
    assert s3.session_state.get('portfolio_sheet_id') != 'EVIL'
    assert s3.infos == [ost.OAUTH_SILENT_MISMATCH_MSG]


def test_url_only_sheet_change_without_session_does_not_remint(wire):
    """只改網址、session 沒跟著改(不是使用者自己的 UI 操作)→ 不重算。"""
    s1 = _login_strict(wire)
    s1.query_params['sheet'] = 'SID2'
    _run_app(s1)
    assert s1.query_params[MK] == _tag(sheet='')


def test_error_callback_in_logged_in_session_does_not_write_state_sheet(wire):
    """已登入分頁收到 `?error=login_required&state=n.EVIL.tag` → 網址不會變成 EVIL,也不會替 EVIL 算記號。"""
    s1 = _login_strict(wire, sheet='VICTIM')
    s1.query_params.clear()
    s1.query_params.update({'error': 'login_required', 'state': 'NX.EVIL.' + _tag(sheet='EVIL')})
    _run_app(s1)
    assert s1.query_params.get('sheet') != 'EVIL'
    assert s1.query_params.get(MK) != _tag(sheet='EVIL')
    assert s1.session_state['portfolio_sheet_id'] == 'VICTIM'
    assert s1.session_state['gsheet_tokens'], '仍是登入狀態'


def test_error_callback_in_logged_in_session_keeps_urls_own_sheet(wire):
    s1 = _login_strict(wire, sheet='VICTIM')
    s1.query_params.update({'error': 'server_error', 'state': 'NX.EVIL.' + MV})
    _run_app(s1)
    assert s1.query_params['sheet'] == 'VICTIM'
    assert s1.query_params[MK] == _tag(sheet='VICTIM'), '同一輪 sync 依 session 的 VICTIM 重掛記號'


def test_refresh_right_after_sidebar_change_is_covered_by_the_inline_sync(wire):
    """「換完 Sheet 還沒任何 rerun 就重新整理」:側欄那一行就地 sync 已經把記號改好 → 恢復成功。"""
    s1 = _login_strict(wire)
    _bind_sheet_like_sidebar(s1, 'SID')        # 同一輪內(沒有下一次 rerun)
    s2 = wire(qp=dict(s1.query_params))        # 立刻重新整理
    _run_app(s2)
    s3 = wire(qp={'code': 'C1', 'state': _qs(_redirect_url(s2))['state']})
    _run_app(s3)
    assert s3.session_state['portfolio_sheet_id'] == 'SID'


def test_stale_marker_mismatch_keeps_sheet_in_url_and_manual_login_rebinds_it(wire):
    """萬一記號還是舊的(例:別的寫入 `?sheet=` 的地方沒有 rerun):對不上 → 不登入,但 Sheet 留在網址,
    手動按一次登入就回綁那一本(修前:Sheet 一起被清掉,且每次重新整理都一樣)。"""
    landing = _silent_roundtrip(wire, url={MK: _tag(sheet=''), 'sheet': 'SID'}, sub='SUB_ME')
    _assert_silent_rejected(landing)
    assert dict(landing.query_params) == {'sheet': 'SID'}
    # 同一個落地 session:app.py 開機還原把 ?sheet= setdefault 進 session → 按登入鈕(state 帶那本)
    landing.session_state.setdefault('portfolio_sheet_id', landing.query_params['sheet'])
    st_btn = ost.login_state_with_sheet(landing.session_state['portfolio_sheet_id'])
    back = wire(qp={'code': 'CM', 'state': st_btn})
    _run_app(back)
    assert back.session_state['portfolio_sheet_id'] == 'SID'
    assert dict(back.query_params) == {'sheet': 'SID', MK: _tag(sheet='SID')}


@pytest.mark.parametrize('code', ['server_error', 'temporarily_unavailable', 'access_denied',
                                  'visit-evil.com-to-fix', 'login_required'])
def test_silent_state_any_error_keeps_sheet(wire, code):
    s = wire(qp={MK: _tag(sheet='S'), 'sheet': 'S'})
    _run_app(s)
    st_param = _qs(_redirect_url(s))['state']
    landing = wire(qp={'error': code, 'state': st_param})
    _run_app(landing)
    assert dict(landing.query_params) == {'sheet': 'S'}, 'Sheet 不得被弄丟(稽核第二輪 SHOULD-A)'
    assert MK not in landing.query_params and 'gsheet_tokens' not in landing.session_state
    assert landing.session_state.get('portfolio_sheet_id') == 'S', 'consume ok → 照舊回綁 session'
    assert st_param.partition('.')[0] not in ns._STORE, '靜默 nonce 任何錯誤都燒掉'
    assert landing.htmls == [] and landing.errors == []


def test_silent_callback_rejected_by_sec2_keeps_sheet(wire):
    """process 重啟 → 回呼查無 nonce(unknown)→ SEC-2 紅字照舊,但靜默 state 的 Sheet 寫回網址。"""
    s = wire(qp={MK: _tag(sheet='S'), 'sheet': 'S'})
    _run_app(s)
    st_param = _qs(_redirect_url(s))['state']
    ns._STORE.clear()                                  # 模擬重啟
    landing = wire(qp={'code': 'C', 'state': st_param})
    _run_app(landing)
    assert landing.errors == [ost.OAUTH_STATE_REJECTED_MSG]
    assert dict(landing.query_params) == {'sheet': 'S'}
    assert 'portfolio_sheet_id' not in landing.session_state, 'consume 沒過 → 不回綁 session'


def test_silent_token_exchange_failure_keeps_sheet(wire, monkeypatch):
    s = wire(qp={MK: _tag(sheet='S'), 'sheet': 'S'})
    _run_app(s)
    st_param = _qs(_redirect_url(s))['state']
    landing = wire(qp={'code': 'C', 'state': st_param})

    def _boom(*a):
        raise ost.OAuthError('invalid_grant')
    monkeypatch.setattr(ost, 'exchange_code_for_tokens', _boom)
    _run_app(landing)
    assert dict(landing.query_params) == {'sheet': 'S'}
    assert 'gsheet_tokens' not in landing.session_state


def test_normal_login_failures_still_clear_everything(wire, monkeypatch):
    """一般登入(兩段 state)的失敗照舊全清 —— 不信未驗證的 state 載荷(與修前相同)。"""
    landing = wire(qp={'code': 'C', 'state': 'UNKNOWN.EVIL'})
    _run_app(landing)
    assert dict(landing.query_params) == {}


# ── sync 的閘:永遠只替「本 session 自己、強驗登入」的帳號算 ─────────────────────
def test_sync_never_mints_for_valve_login(wire):
    ns.issue('NV', _OTHER)
    fst = wire(qp={'code': 'C', 'state': 'NV'},
               secrets={OAUTH_CSRF_ENFORCE_SECRET_KEY: False})
    _run_app(fst)
    assert 'gsheet_tokens' in fst.session_state and MK not in fst.query_params
    assert _bind_sheet_like_sidebar(fst, 'SID') is False
    assert MK not in fst.query_params


def test_sync_never_mints_when_disabled_no_secret_no_sub_logged_out(wire, monkeypatch):
    s1 = _login_strict(wire)
    # 開關後來關掉
    s1.secrets = {OAUTH_SILENT_REAUTH_SECRET_KEY: 'off'}
    assert _bind_sheet_like_sidebar(s1, 'A') is False
    s1.secrets = {}
    # 沒有 client_secret
    monkeypatch.setattr(ost, '_resolve_oauth_cfg', lambda: {'client_id': 'CID', 'client_secret': '',
                                                             'redirect_uri': 'r'})
    assert _bind_sheet_like_sidebar(s1, 'B') is False
    monkeypatch.setattr(ost, '_resolve_oauth_cfg', lambda: dict(_CFG))
    # session 的 token 沒有 sub
    _saved = s1.session_state['gsheet_tokens']
    s1.session_state['gsheet_tokens'] = {'access_token': 'AT'}
    assert _bind_sheet_like_sidebar(s1, 'C') is False
    s1.session_state['gsheet_tokens'] = _saved
    # 回呼參數還在網址上
    s1.query_params['code'] = 'x'
    assert _bind_sheet_like_sidebar(s1, 'D') is False
    del s1.query_params['code']
    # 值沒變 → 不改寫
    assert _bind_sheet_like_sidebar(s1, 'E') is True
    assert ost.sync_silent_marker() is False
    # 登出 → 不再算
    s1.session_state.pop('gsheet_tokens')
    ost.forget_silent_reauth()
    assert _bind_sheet_like_sidebar(s1, 'F') is False
    assert MK not in s1.query_params
    # 登出也清掉 eligibility 旗標(縱深防禦:即使日後有別的路徑把 token 放回 session,也不會替它重算)
    from shared.oauth_session_policy import OAUTH_SILENT_ELIGIBLE_SESSION_KEY
    assert OAUTH_SILENT_ELIGIBLE_SESSION_KEY not in s1.session_state


def test_sync_never_mints_without_sub_at_login(wire, monkeypatch):
    ns.issue('N1', _ME)
    fst = wire(qp={'code': 'C', 'state': 'N1'})
    monkeypatch.setattr(ost, 'exchange_code_for_tokens',
                        lambda *a: {'access_token': 'AT', 'expires_at': 9_999_999_999})
    _run_app(fst)
    assert _bind_sheet_like_sidebar(fst, 'SID') is False and MK not in fst.query_params


def test_sync_uses_only_the_sessions_own_sub(wire):
    s1 = _login_strict(wire, sub='SUB_ME')
    _bind_sheet_like_sidebar(s1, 'SID')
    assert s1.query_params[MK] == _tag(sub='SUB_ME', sheet='SID')
    assert s1.query_params[MK] != _tag(sub='SUB_OTHER', sheet='SID')
    # 換人重新登入(強驗)→ 之後的重算用新的 sub
    ns.issue('N2', _ME)
    s2 = wire(qp={'code': 'C2', 'state': 'N2.SID'}, sub='SUB_OTHER')
    _run_app(s2)
    _bind_sheet_like_sidebar(s2, 'SID3')
    assert s2.query_params[MK] == _tag(sub='SUB_OTHER', sheet='SID3')


def test_relogin_via_valve_in_same_session_drops_eligibility(wire):
    s1 = _login_strict(wire)
    s1.session_state.pop('gsheet_tokens')                  # (例:逾時清掉)
    ns.issue('NV', _OTHER)
    s1.query_params.clear()
    s1.query_params.update({'code': 'CV', 'state': 'NV'})
    s1.secrets = {OAUTH_CSRF_ENFORCE_SECRET_KEY: False}
    _run_app(s1)
    assert 'gsheet_tokens' in s1.session_state
    assert _bind_sheet_like_sidebar(s1, 'SID') is False, '安全閥放行的登入 ⇒ 不可重算記號'
