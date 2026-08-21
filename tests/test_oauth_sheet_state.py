"""P2(v19.206 順暢化)—— Sheet ID 搭 OAuth `state` 便車守衛。

全新登入時 Google 轉跳沖掉 ?sheet=(+ callback query_params.clear())→ 上次 Sheet 失憶,
被迫再繞 📁 組合管理。P2:讓 Sheet ID 搭 state(`nonce.sheetid`)撐過轉跳,回來自動回綁。

本檔釘住:編碼/拆解/消毒 + callback 端到端(CSRF 語意不變、回綁兩通道 + ?sheet=、
安全:錯 nonce 擋登入、髒 sheetid 消毒、向後相容純 nonce 不回綁)。
"""
from __future__ import annotations

import pytest

import src.data.portfolio.oauth_state as ost


# ── 消毒:只放行純 [A-Za-z0-9_-] ─────────────────────────────────────────
def test_sanitize_sheet_id_valid_and_invalid():
    assert ost._sanitize_sheet_id('ABC123_-xyz') == 'ABC123_-xyz'
    assert ost._sanitize_sheet_id('  ABC123  ') == 'ABC123'      # strip
    assert ost._sanitize_sheet_id('') == ''
    assert ost._sanitize_sheet_id(None) == ''
    # 怪字元一律拒(不可信輸入):空白 / 標點 / 注入
    assert ost._sanitize_sheet_id('bad id') == ''
    assert ost._sanitize_sheet_id('a<script>') == ''
    assert ost._sanitize_sheet_id('a.b') == ''                   # '.' 不在字母集
    assert ost._sanitize_sheet_id('a/b') == ''


def test_sanitize_sheet_id_length_bound():
    """F2:長度上限(Google fileId 實測 44;{1,120} 留餘裕又擋灌爆)。"""
    assert ost._sanitize_sheet_id('A' * 120) == 'A' * 120        # 邊界內收
    assert ost._sanitize_sheet_id('A' * 121) == ''               # 超長(合法字元)也拒


# ── 拆解:partition 第一個 '.',nonce 完整 + sheetid 消毒 ────────────────
def test_split_login_state():
    assert ost._split_login_state('NONCE.ABC123') == ('NONCE', 'ABC123')
    assert ost._split_login_state('NONCE') == ('NONCE', '')       # 無 '.'(向後相容)
    assert ost._split_login_state('') == ('', '')
    assert ost._split_login_state(None) == ('', '')
    # sheetid 端有髒字 → 消毒成空,但 nonce 仍完整(CSRF 不受影響)
    assert ost._split_login_state('NONCE.bad id!') == ('NONCE', '')
    # 即使多一個 '.',partition 只切第一個 → nonce 完整,尾段消毒(含 '.' → 拒)
    assert ost._split_login_state('NONCE.a.b') == ('NONCE', '')
    # F3:nonce 段**不消毒**(只做相等比對,非拿去別處用)→ 原樣返回(釘住此假設)
    assert ost._split_login_state('a b.ABC') == ('a b', 'ABC')


# ── 編碼:login_state_with_sheet ─────────────────────────────────────────
def test_login_state_with_sheet(monkeypatch):
    monkeypatch.setattr(ost, 'get_login_state', lambda: 'NONCE')
    assert ost.login_state_with_sheet('ABC123') == 'NONCE.ABC123'
    assert ost.login_state_with_sheet('') == 'NONCE'             # 無 sheet → 純 nonce
    assert ost.login_state_with_sheet('bad id') == 'NONCE'       # 髒 → 消毒後空 → 純 nonce
    # 往返一致性:編碼再拆解,sheetid 應還原
    _st = ost.login_state_with_sheet('MySheet_9')
    assert ost._split_login_state(_st) == ('NONCE', 'MySheet_9')


# ── callback 端到端 ─────────────────────────────────────────────────────
class _Rerun(Exception):
    pass


class _QP(dict):
    def clear(self):
        super().clear()


class _FakeSt:
    def __init__(self, session, qp):
        self.session_state = session
        self.query_params = _QP(qp)

    def success(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass

    def rerun(self):
        raise _Rerun


def _wire_callback(monkeypatch, *, session, qp):
    fst = _FakeSt(session, qp)
    monkeypatch.setattr(ost, 'st', fst)
    monkeypatch.setattr(ost, '_resolve_oauth_cfg',
                        lambda: {'client_id': 'c', 'client_secret': 's', 'redirect_uri': 'r'})
    monkeypatch.setattr(ost, 'exchange_code_for_tokens',
                        lambda code, ci, cs, ru: {'access_token': 'AT', 'refresh_token': 'RT'})
    monkeypatch.setattr(ost, 'decode_id_token_email', lambda t: 'a@b.com')
    return fst


def test_callback_rebinds_sheet_from_state(monkeypatch):
    """正常登入:state=nonce.ABC → 換 token + 回綁兩通道 + 重掛 ?sheet=ABC。"""
    fst = _wire_callback(
        monkeypatch,
        session={'_oauth_state': 'NONCE'},
        qp={'code': 'CODE', 'state': 'NONCE.ABC123'})

    with pytest.raises(_Rerun):          # 成功尾聲 st.rerun
        ost.handle_oauth_callback()

    assert fst.session_state['gsheet_tokens'] == {'access_token': 'AT', 'refresh_token': 'RT'}
    # 回綁兩通道
    assert fst.session_state['portfolio_sheet_id'] == 'ABC123'
    assert fst.session_state['stock_portfolio_sheet_id'] == 'ABC123'
    # 重掛 ?sheet=(取代 blanket clear → 戰情室/選股 auto-load 生效)
    assert fst.query_params.get('sheet') == 'ABC123'
    # code/state 已清(不殘留在 URL)
    assert 'code' not in fst.query_params and 'state' not in fst.query_params


def test_callback_csrf_rejects_wrong_nonce(monkeypatch):
    """錯 nonce(別的 session 發起)→ 擋登入,不換 token、不回綁(sheetid 合法也一樣)。"""
    fst = _wire_callback(
        monkeypatch,
        session={'_oauth_state': 'NONCE'},
        qp={'code': 'CODE', 'state': 'WRONGNONCE.ABC123'})

    ost.handle_oauth_callback()          # 不應 raise _Rerun(提早 return)

    assert 'gsheet_tokens' not in fst.session_state, 'CSRF 不符不該換 token'
    assert 'portfolio_sheet_id' not in fst.session_state, 'CSRF 不符不該回綁 Sheet'


def test_callback_backward_compat_pure_nonce(monkeypatch):
    """state 無 sheet(純 nonce / 舊書籤)→ 登入成功但不回綁(不亂寫)。"""
    fst = _wire_callback(
        monkeypatch,
        session={'_oauth_state': 'NONCE'},
        qp={'code': 'CODE', 'state': 'NONCE'})

    with pytest.raises(_Rerun):
        ost.handle_oauth_callback()

    assert fst.session_state['gsheet_tokens']['access_token'] == 'AT'   # 登入仍成功
    assert 'portfolio_sheet_id' not in fst.session_state               # 無 sheet → 不回綁
    assert 'sheet' not in fst.query_params


def test_callback_malicious_sheet_is_dropped(monkeypatch):
    """髒 sheetid(注入)→ 消毒成空 → 登入成功但不回綁(§1:不寫不可信值)。"""
    fst = _wire_callback(
        monkeypatch,
        session={'_oauth_state': 'NONCE'},
        qp={'code': 'CODE', 'state': 'NONCE.bad<script>'})

    with pytest.raises(_Rerun):
        ost.handle_oauth_callback()

    assert fst.session_state['gsheet_tokens']['access_token'] == 'AT'   # 登入仍成功
    assert 'portfolio_sheet_id' not in fst.session_state               # 髒值不回綁
    assert 'sheet' not in fst.query_params


# ── F1 + R1(安全):CSRF 弱驗路徑 —— 攻擊者的 Sheet 不得回綁,空 nonce 更直接拒登入 ──
def test_callback_empty_nonce_with_active_session_is_rejected(monkeypatch):
    """R1 硬化:本 session 有自己的 nonce,卻收到**空 nonce** callback(state='.<攻擊者Sheet>')
    → 絕非本 session 合法回呼 → **整個 callback 拒絕**(login-CSRF + 跨帳號 Sheet 注入雙擋):
    不換 token、不回綁。"""
    fst = _wire_callback(
        monkeypatch,
        session={'_oauth_state': 'VICTIM_NONCE'},
        qp={'code': 'CODE', 'state': '.ATTACKER_SHEET'})

    ost.handle_oauth_callback()          # 提早 return,不應 raise _Rerun

    assert 'gsheet_tokens' not in fst.session_state, 'R1:空 nonce + active session 應拒登入'
    assert 'portfolio_sheet_id' not in fst.session_state
    assert 'stock_portfolio_sheet_id' not in fst.session_state
    assert 'sheet' not in fst.query_params


def test_callback_session_lost_does_not_rebind(monkeypatch):
    """session 遺失(expected=None,轉跳/重啟)→ 放行登入,但無自己的 nonce 可強驗
    → 不信 state 載荷、不回綁(此時使用者可走 A 的 ?sheet= 或 P1 就地重挑)。"""
    fst = _wire_callback(
        monkeypatch,
        session={},                       # 無 _oauth_state
        qp={'code': 'CODE', 'state': 'SOMENONCE.ABC123'})

    with pytest.raises(_Rerun):
        ost.handle_oauth_callback()

    assert fst.session_state['gsheet_tokens']['access_token'] == 'AT'   # 登入成功(迴圈修正不變)
    assert 'portfolio_sheet_id' not in fst.session_state               # 弱驗 → 不回綁
    assert 'sheet' not in fst.query_params
