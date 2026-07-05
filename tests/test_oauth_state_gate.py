"""OAuth state 閘門純函式測試(v19.63 修登入無限迴圈)。"""
from src.data.portfolio.oauth_state import _oauth_state_ok


def test_normal_match_accepts():
    assert _oauth_state_ok("ABC", "ABC") is True


def test_session_lost_accepts():
    # session_state 遺失(expected=None)→ 放行(修迴圈,舊版會拒絕)
    assert _oauth_state_ok(None, "ABC") is True


def test_genuine_cross_session_rejects():
    # 本 session 有發起 + state 不符 → 擋(保留防搶帳號)
    assert _oauth_state_ok("ABC", "XYZ") is False


def test_no_state_in_url_accepts():
    assert _oauth_state_ok("ABC", None) is True
    assert _oauth_state_ok(None, None) is True
