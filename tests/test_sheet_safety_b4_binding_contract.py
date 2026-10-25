"""Sheet Safety 批 B4（DEC-083）：Sheet 綁定**唯一寫入契約**（L1 `oauth_state`）＋ Q5 登出清除。

契約四支：`apply_sheet_binding` / `clear_sheet_binding` / `restore_sheet_binding_from_query`
（＋ 回呼內部用的 `_write_binding_session`）。全部以假的 `st`（session_state / query_params dict）測。
"""
from __future__ import annotations

import pytest

import src.data.portfolio.oauth_state as ost
from shared import sheet_id as S
from shared.oauth_session_policy import (
    OAUTH_SILENT_ELIGIBLE_SESSION_KEY,
    OAUTH_SILENT_MARKER_PARAM,
)

_ID = "1AbC_dEf-GhIjKlMnOpQrStUvWxYz0123456789abcd"
_URL = f"https://docs.google.com/spreadsheets/d/{_ID}/edit#gid=0"


class _St:
    def __init__(self, session=None, query=None, secrets=None):
        self.session_state = dict(session or {})
        self.query_params = dict(query or {})
        self.secrets = dict(secrets or {})


@pytest.fixture
def fst(monkeypatch):
    def _make(**kw):
        f = _St(**kw)
        monkeypatch.setattr(ost, "st", f)
        return f
    return _make


# ── apply ────────────────────────────────────────────────────────────────
def test_apply_url_writes_both_channels_query_and_resyncs_marker(fst, monkeypatch):
    f = fst()
    synced = []
    monkeypatch.setattr(ost, "sync_silent_marker", lambda: synced.append(1) or False)
    r = ost.apply_sheet_binding(_URL)
    assert (r.sheet_id, r.changed, r.error) == (_ID, True, "")
    assert f.session_state == {"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID}
    assert f.query_params == {"sheet": _ID}
    assert synced == [1]


@pytest.mark.parametrize("raw, err", [
    ("https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pubhtml", S.SHEET_INPUT_PUBLISHED_LINK),
    ("<script>", S.SHEET_INPUT_INVALID),
    ("", S.SHEET_INPUT_EMPTY),
    ("   ", S.SHEET_INPUT_EMPTY),
])
def test_apply_error_writes_nothing(fst, raw, err):
    f = fst(session={"portfolio_sheet_id": "OLD", "stock_portfolio_sheet_id": "OLD"},
            query={"sheet": "OLD"})
    r = ost.apply_sheet_binding(raw)
    assert r.error == err and r.sheet_id == "" and not r.changed
    assert r.message == S.SHEET_INPUT_ERROR_MESSAGES[err]
    assert f.session_state == {"portfolio_sheet_id": "OLD", "stock_portfolio_sheet_id": "OLD"}
    assert f.query_params == {"sheet": "OLD"}


def test_publish_link_never_binds_e(fst):
    f = fst()
    ost.apply_sheet_binding("https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pubhtml")
    assert "e" not in f.session_state.values()
    assert f.session_state == {} and f.query_params == {}


def test_apply_same_as_current_is_noop(fst, monkeypatch):
    f = fst(session={"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": "OTHER"})
    monkeypatch.setattr(ost, "sync_silent_marker", lambda: pytest.fail("不該重算"))
    r = ost.apply_sheet_binding(_URL)
    assert (r.sheet_id, r.changed, r.error) == (_ID, False, "")
    # Q6:兩通道不一致時,⛔ 不因為「文字框回傳現值」就偷偷覆寫另一格
    assert f.session_state["stock_portfolio_sheet_id"] == "OTHER"
    assert f.query_params == {}


def test_apply_same_as_secrets_default_is_noop(fst):
    """現值來自 secrets 預設(同 L1 `_get_active_sheet_id`)→ 文字框回傳它時不寫進 session。"""
    f = fst(secrets={"portfolio_sheet_id": _ID})
    assert ost.apply_sheet_binding(_ID).changed is False
    assert f.session_state == {}


def test_apply_query_param_failure_not_fatal(fst, monkeypatch):
    class _QP(dict):
        def __setitem__(self, *_a):
            raise RuntimeError("read-only")
    f = fst()
    f.query_params = _QP()
    monkeypatch.setattr(ost, "sync_silent_marker", lambda: False)
    assert ost.apply_sheet_binding(_ID).changed is True
    assert f.session_state["portfolio_sheet_id"] == _ID


# ── clear（Q5）────────────────────────────────────────────────────────────
def test_clear_removes_binding_query_and_silent_marker(fst):
    f = fst(session={"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID,
                     OAUTH_SILENT_ELIGIBLE_SESSION_KEY: True, "other": 1},
            query={"sheet": _ID, OAUTH_SILENT_MARKER_PARAM: "a" * 16, "sid": "2330"})
    ost.clear_sheet_binding()
    assert f.session_state == {"other": 1}
    assert f.query_params == {"sid": "2330"}


def test_after_clear_login_state_carries_no_sheet(fst, monkeypatch):
    f = fst(session={"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID})
    monkeypatch.setattr(ost, "get_login_state", lambda: "NONCE")
    ost.clear_sheet_binding()
    # app.py 側欄登入鈕的寫法:state 由 session 的 portfolio_sheet_id 組成
    assert ost.login_state_with_sheet(str(f.session_state.get("portfolio_sheet_id", "") or "")) == "NONCE"


def test_after_clear_restore_has_nothing_to_restore(fst):
    f = fst(session={"portfolio_sheet_id": _ID}, query={"sheet": _ID})
    ost.clear_sheet_binding()
    assert ost.restore_sheet_binding_from_query() == ""
    assert "portfolio_sheet_id" not in f.session_state


# ── restore ──────────────────────────────────────────────────────────────
def test_restore_setdefault_both_channels(fst):
    f = fst(query={"sheet": f"  {_ID} "})
    assert ost.restore_sheet_binding_from_query() == _ID
    assert f.session_state == {"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID}


def test_restore_does_not_override_this_sessions_choice(fst):
    f = fst(session={"portfolio_sheet_id": "MINE", "stock_portfolio_sheet_id": "MINE"},
            query={"sheet": _ID})
    ost.restore_sheet_binding_from_query()
    assert f.session_state == {"portfolio_sheet_id": "MINE", "stock_portfolio_sheet_id": "MINE"}


@pytest.mark.parametrize("bad", ["<script>", "a b", "x" * 121, "e/2PACX"])
def test_restore_sanitises_untrusted_url(fst, bad):
    f = fst(query={"sheet": bad})
    assert ost.restore_sheet_binding_from_query() == ""
    assert f.session_state == {}


# ── 回呼仍經契約寫兩格（行為不變）───────────────────────────────────────────
def test_write_binding_session_writes_both_legacy_keys(fst):
    f = fst()
    ost._write_binding_session(_ID)
    assert f.session_state == {"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID}


def test_legacy_aliases_point_to_l0():
    assert ost._sanitize_sheet_id is S.sanitize_sheet_id
    assert ost._SHEET_ID_RE is S.SHEET_ID_RE
