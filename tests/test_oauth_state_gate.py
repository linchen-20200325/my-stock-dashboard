"""OAuth state 閘門測試 —— SEC-2 起由 server 端一次性 nonce 表＋瀏覽器綁定把關。

⚠️ SEC-2(有意識的改寫,不是漏測):本檔原本釘住 v19.63 的純函式 `_oauth_state_ok` truth table,
其中兩列 `expected=None → 放行`、`URL 沒帶 state → 放行` **正是 login CSRF 漏洞本身**
(Google 轉跳是整頁載入 ⇒ 新 session ⇒ expected 幾乎恆為 None ⇒ 任何 `?code=` 都被吞下)。
`_oauth_state_ok` 已刪除;那幾列改釘成「拒絕」,並補上 nonce 表與 XSRF cookie 解碼的守衛。
v19.63 的「登入迴圈」由 server 端 nonce(不依賴 session_state)＋拒絕時不 rerun 解掉。
"""
from __future__ import annotations

import hashlib
import os
import threading

import pytest

import src.data.portfolio.oauth_nonce_store as ns
import src.data.portfolio.oauth_state as ost
from shared.oauth_csrf_policy import (
    OAUTH_CSRF_ENFORCE_SECRET_KEY,
    OAUTH_STATE_MAX_ENTRIES,
    OAUTH_STATE_TTL_SEC,
    STREAMLIT_XSRF_COOKIE_NAME,
)
from shared.ttls import TTL_15MIN

_B_VICTIM = hashlib.sha256(b'victim-xsrf-token').hexdigest()
_B_ATTACKER = hashlib.sha256(b'attacker-xsrf-token').hexdigest()


@pytest.fixture(autouse=True)
def _fresh_store():
    ns._STORE.clear()
    ns._EXPIRED.clear()
    yield
    ns._STORE.clear()
    ns._EXPIRED.clear()


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


# ── 常數(§3.3 SSOT)────────────────────────────────────────────────────
def test_policy_constants():
    assert OAUTH_STATE_TTL_SEC == TTL_15MIN
    assert OAUTH_STATE_MAX_ENTRIES == 10_000
    assert STREAMLIT_XSRF_COOKIE_NAME == '_streamlit_xsrf'
    assert OAUTH_CSRF_ENFORCE_SECRET_KEY == 'oauth_csrf_enforce'


# ── 原 truth table 的四列,SEC-2 後的語意 ───────────────────────────────
def test_normal_match_accepts_once():
    assert ns.issue('ABC', _B_VICTIM) is True
    assert ns.consume('ABC', _B_VICTIM) == (True, ns.REASON_OK)


def test_session_lost_no_longer_matters_but_forged_nonce_rejects():
    """修前 expected=None → 放行;現在不看 session,沒登記過的 nonce 一律拒。"""
    assert ns.consume('ABC', _B_VICTIM) == (False, ns.REASON_UNKNOWN)


def test_genuine_cross_session_rejects():
    ns.issue('ABC', _B_VICTIM)
    assert ns.consume('XYZ', _B_VICTIM) == (False, ns.REASON_UNKNOWN)


def test_no_state_in_url_rejects():
    """修前 got=None → 放行(漏洞);現在空 nonce 一律拒。"""
    ns.issue('ABC', _B_VICTIM)
    assert ns.consume('', _B_VICTIM) == (False, ns.REASON_UNKNOWN)
    assert ns.consume(None, _B_VICTIM) == (False, ns.REASON_UNKNOWN)


def test_old_pass_through_function_is_gone():
    assert not hasattr(ost, '_oauth_state_ok'), 'SEC-2:放行路徑的閘門函式不得回來'


# ── 一次性 / 過期 / 綁定 / 沒 cookie ─────────────────────────────────────
def test_replay_rejected():
    ns.issue('N', _B_VICTIM)
    assert ns.consume('N', _B_VICTIM)[0] is True
    assert ns.consume('N', _B_VICTIM) == (False, ns.REASON_UNKNOWN)


def test_expired_rejected(monkeypatch):
    clk = _Clock()
    monkeypatch.setattr(ns, '_now', clk)
    ns.issue('N', _B_VICTIM)
    clk.t += OAUTH_STATE_TTL_SEC
    assert ns.consume('N', _B_VICTIM) == (False, ns.REASON_EXPIRED)


def test_issue_extends_ttl(monkeypatch):
    clk = _Clock()
    monkeypatch.setattr(ns, '_now', clk)
    ns.issue('N', _B_VICTIM)
    clk.t += OAUTH_STATE_TTL_SEC - 1
    ns.issue('N', _B_VICTIM)           # 每次 rerun 畫登入鈕都延長
    clk.t += OAUTH_STATE_TTL_SEC - 1
    assert ns.consume('N', _B_VICTIM) == (True, ns.REASON_OK)


def test_other_browser_rejected_and_burned():
    """login CSRF:攻擊者在自己瀏覽器領 nonce,受害者瀏覽器送回 → mismatch,且 nonce 燒掉。"""
    ns.issue('N_att', _B_ATTACKER)
    assert ns.consume('N_att', _B_VICTIM) == (False, ns.REASON_MISMATCH)
    assert ns.consume('N_att', _B_ATTACKER) == (False, ns.REASON_UNKNOWN), '比對失敗也要燒掉'


def test_no_cookie_rejected_and_burned():
    ns.issue('N', _B_VICTIM)
    assert ns.consume('N', None) == (False, ns.REASON_NO_COOKIE)
    assert ns.consume('N', _B_VICTIM) == (False, ns.REASON_UNKNOWN)


def test_issue_without_binding_does_not_register():
    assert ns.issue('N', None) is False
    assert ns.issue('', _B_VICTIM) is False
    assert ns._STORE == {}


def test_store_holds_only_hashes_no_raw_values():
    ns.issue('N', _B_VICTIM)
    _exp, _h = ns._STORE['N']
    assert _h == _B_VICTIM and len(_h) == 64


# ── 上限與淘汰 ────────────────────────────────────────────────────────────
def test_eviction_at_max_entries():
    for i in range(3):
        ns.issue(f'N{i}', _B_VICTIM, max_entries=3)
    ns.issue('N0', _B_VICTIM, max_entries=3)      # 延長 → 移到最後
    ns.issue('N3', _B_VICTIM, max_entries=3)      # 滿 → 擠掉最久沒被延長的 N1
    assert list(ns._STORE) == ['N2', 'N0', 'N3']
    assert ns.consume('N1', _B_VICTIM) == (False, ns.REASON_UNKNOWN)
    assert ns.consume('N0', _B_VICTIM)[0] is True


def test_default_max_entries_enforced():
    for i in range(OAUTH_STATE_MAX_ENTRIES + 5):
        ns.issue(f'N{i}', _B_VICTIM)
    assert len(ns._STORE) == OAUTH_STATE_MAX_ENTRIES
    assert 'N0' not in ns._STORE and f'N{OAUTH_STATE_MAX_ENTRIES + 4}' in ns._STORE


def test_expired_purged_on_issue(monkeypatch):
    clk = _Clock()
    monkeypatch.setattr(ns, '_now', clk)
    ns.issue('OLD', _B_VICTIM)
    clk.t += OAUTH_STATE_TTL_SEC + 1
    ns.issue('NEW', _B_VICTIM)
    assert list(ns._STORE) == ['NEW']


# ── 併發 ──────────────────────────────────────────────────────────────────
def test_concurrent_issue_consume_thread_safe():
    """多執行緒同時發 / 消耗:每個 nonce 恰好成功一次,沒有例外。"""
    n_threads, per = 8, 200
    for t in range(n_threads):
        for i in range(per):
            ns.issue(f'T{t}-{i}', _B_VICTIM)
    results, errors = [], []

    def worker():
        try:
            for t in range(n_threads):
                for i in range(per):
                    results.append(ns.consume(f'T{t}-{i}', _B_VICTIM)[0])
                    ns.issue(f'X{threading.get_ident()}-{t}-{i}', _B_VICTIM)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert errors == []
    assert sum(results) == n_threads * per, '每個 nonce 只能被消耗成功一次'


# ── XSRF cookie 解碼(釘住 v2 格式;mask 會換,token bytes 不變)──────────────
def _v2(token: bytes, mask: bytes, ts: int = 1700000000) -> str:
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(token))
    return f'2|{mask.hex()}|{masked.hex()}|{ts}'


def test_decode_xsrf_v2_unmasks_and_is_mask_independent():
    tok = os.urandom(16)
    a, b = _v2(tok, b'\x01\x02\x03\x04'), _v2(tok, b'\xa0\xb0\xc0\xd0')
    assert a != b
    assert ost._decode_xsrf_token(a) == tok == ost._decode_xsrf_token(b)
    assert ost._decode_xsrf_token(f'"{a}"') == tok      # 帶引號也可


def test_decode_xsrf_matches_streamlit_generator():
    """與 streamlit 1.59 自己的產生器互通(只在測試端 import 內部模組,產品碼不 import)。"""
    gen = pytest.importorskip('streamlit.web.server.starlette.starlette_app_utils')
    tok = os.urandom(16)
    assert ost._decode_xsrf_token(gen.generate_xsrf_token_string(tok)) == tok


@pytest.mark.parametrize('raw', [
    None, '', '   ', 'x', 123, 'abcdef',            # 非 v2(含 v1 純 hex)
    '2|zz|00|1', '2|0011|abcd', '2|001122|abcd|1',  # 段數 / hex / mask 長度錯
    '2|00112233||1', '2|00112233|ab|x', '1|00112233|ab|1', '2|00112233|ab|1|9',
    '2|0011223３|ab|1',                               # 非 ASCII
])
def test_decode_xsrf_malformed_returns_none(raw):
    assert ost._decode_xsrf_token(raw) is None


class _Ctx:
    def __init__(self, cookies):
        self.cookies = cookies


class _StWithCtx:
    def __init__(self, cookies=None, raise_ctx=False):
        self._cookies, self._raise = cookies or {}, raise_ctx
        self.session_state = {}

    @property
    def context(self):
        if self._raise:
            raise RuntimeError('no script run context')
        return _Ctx(self._cookies)


def test_browser_binding_hashes_decoded_token(monkeypatch):
    tok = os.urandom(16)
    monkeypatch.setattr(ost, 'st', _StWithCtx({STREAMLIT_XSRF_COOKIE_NAME: _v2(tok, b'\x09\x08\x07\x06')}))
    assert ost._browser_binding() == hashlib.sha256(tok).hexdigest()


@pytest.mark.parametrize('st_obj', [
    _StWithCtx({}), _StWithCtx({STREAMLIT_XSRF_COOKIE_NAME: 'garbage'}), _StWithCtx(raise_ctx=True)])
def test_browser_binding_none_when_absent_or_malformed(monkeypatch, st_obj):
    monkeypatch.setattr(ost, 'st', st_obj)
    assert ost._browser_binding() is None


def test_malformed_cookie_leads_to_rejection(monkeypatch):
    """壞 cookie → binding None → consume 回 no_cookie(fail closed)。"""
    monkeypatch.setattr(ost, 'st', _StWithCtx({STREAMLIT_XSRF_COOKIE_NAME: '2|bad|bad|1'}))
    ns.issue('N', _B_VICTIM)
    assert ns.consume('N', ost._browser_binding()) == (False, ns.REASON_NO_COOKIE)


def test_get_login_state_issues_bound_nonce_and_is_stable(monkeypatch):
    tok = os.urandom(16)
    fst = _StWithCtx({STREAMLIT_XSRF_COOKIE_NAME: _v2(tok, b'\x01\x01\x01\x01')})
    monkeypatch.setattr(ost, 'st', fst)
    n1, n2 = ost.get_login_state(), ost.get_login_state()
    assert n1 == n2 == fst.session_state['_oauth_state']
    assert ns._STORE[n1][1] == hashlib.sha256(tok).hexdigest()
    assert len(ns._STORE) == 1


def test_get_login_state_without_cookie_does_not_register(monkeypatch):
    monkeypatch.setattr(ost, 'st', _StWithCtx({}))
    assert ost.get_login_state()
    assert ns._STORE == {}


# ── 審計 round 1(SA1-S1):過期項被別的 session 清掉後,仍回 expired 而非 unknown ──────────
def test_expired_purged_by_other_session_still_reports_expired(monkeypatch):
    clk = _Clock()
    monkeypatch.setattr(ns, '_now', clk)
    ns.issue('IDLE_TAB', _B_VICTIM)
    clk.t += OAUTH_STATE_TTL_SEC + 1
    ns.issue('OTHER_SESSION', _B_ATTACKER)          # 別人的 issue() 順手清掉 IDLE_TAB
    assert 'IDLE_TAB' not in ns._STORE
    assert ns.consume('IDLE_TAB', _B_VICTIM) == (False, ns.REASON_EXPIRED)
    assert ns.consume('IDLE_TAB', _B_VICTIM) == (False, ns.REASON_UNKNOWN), '墓碑也一次性'


def test_tombstones_bounded_fifo(monkeypatch):
    clk = _Clock()
    monkeypatch.setattr(ns, '_now', clk)
    monkeypatch.setattr(ns, 'OAUTH_STATE_EXPIRED_TOMBSTONE_MAX', 3)
    for i in range(5):
        ns.issue(f'E{i}', _B_VICTIM)
    clk.t += OAUTH_STATE_TTL_SEC + 1
    ns.issue('TRIGGER', _B_VICTIM)
    assert list(ns._EXPIRED) == ['E2', 'E3', 'E4']
    assert ns.consume('E0', _B_VICTIM) == (False, ns.REASON_UNKNOWN)
    assert ns.consume('E4', _B_VICTIM) == (False, ns.REASON_EXPIRED)


def test_tombstone_constant_and_capacity_eviction_stays_unknown():
    from shared.oauth_csrf_policy import OAUTH_STATE_EXPIRED_TOMBSTONE_MAX
    assert OAUTH_STATE_EXPIRED_TOMBSTONE_MAX == OAUTH_STATE_MAX_ENTRIES
    for i in range(3):
        ns.issue(f'C{i}', _B_VICTIM, max_entries=2)
    assert ns._EXPIRED == {}, '容量淘汰不是過期,不進墓碑'
    assert ns.consume('C0', _B_VICTIM) == (False, ns.REASON_UNKNOWN)


def test_reissue_clears_tombstone(monkeypatch):
    clk = _Clock()
    monkeypatch.setattr(ns, '_now', clk)
    ns.issue('N', _B_VICTIM)
    clk.t += OAUTH_STATE_TTL_SEC + 1
    ns.issue('X', _B_VICTIM)
    ns.issue('N', _B_VICTIM)                        # 同一 session 又畫了一次登入鈕
    assert 'N' not in ns._EXPIRED
    assert ns.consume('N', _B_VICTIM) == (True, ns.REASON_OK)


# ── 審計 round 1(SA1-S2):沒 cookie 不登記時要記一行 reason,每 session 一次,不含值 ──────
def test_no_cookie_logged_once_per_session(monkeypatch, capsys):
    fst = _StWithCtx({})
    monkeypatch.setattr(ost, 'st', fst)
    n = ost.get_login_state()
    ost.get_login_state()
    out = capsys.readouterr().out
    assert out.count('reason=no_cookie') == 1
    assert n not in out
    fst2 = _StWithCtx({})                            # 另一個 session 會再記一次
    monkeypatch.setattr(ost, 'st', fst2)
    ost.get_login_state()
    assert capsys.readouterr().out.count('reason=no_cookie') == 1


def test_cookie_present_logs_nothing(monkeypatch, capsys):
    monkeypatch.setattr(ost, 'st', _StWithCtx({STREAMLIT_XSRF_COOKIE_NAME: _v2(os.urandom(16), b'\x01\x02\x03\x04')}))
    ost.get_login_state()
    assert 'no_cookie' not in capsys.readouterr().out


# ── 審計 round 1(SA2-S2):SA secret 不再在 import 時常駐 oauth_state ───────────────────
def test_sa_secret_globals_removed():
    assert not hasattr(ost, '_gsa_secret')
    assert not hasattr(ost, '_sheet_id_secret')
