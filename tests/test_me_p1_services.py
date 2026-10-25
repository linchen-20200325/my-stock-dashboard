"""👤 我的 P1（DEC-083）—— L3 `portfolio_binding_service` 的 Sheet SSOT 與新 `me_account_service`。

客戶原文 Q6：「組合與觀察清單使用同一本 active Sheet。若 legacy 狀態兩者不一致：顯示白話警示、不偷偷選 ETF 通道、
不偷偷選個股通道、不自動覆寫其中一個、讓使用者在 👤 我的明確重新選定。」
AI 總管裁示：secrets 部署預設在新版 UI 不當 active（要使用者明確按「使用這本」）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

import src.data.portfolio.oauth_state as ost
from shared import sheet_id as S
from src.data.portfolio import gsheet_portfolio as gsp
from src.services import me_account_service as ME
from src.services import portfolio_binding_service as B

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_A = "1AbC_dEf-GhIjKlMnOpQrStUvWxYz0123456789abcd"
_B = "2ZyX_wVu-TsRqPoNmLkJiHgFeDcBa9876543210zyxw"
_TOK = {"access_token": "at", "refresh_token": "rt"}


class _St:
    def __init__(self, session=None, query=None, secrets=None):
        self.session_state = dict(session or {})
        self.query_params = dict(query or {})
        self.secrets = dict(secrets or {})


@pytest.fixture
def fst(monkeypatch):
    """L1 兩支模組共用同一個假 `st`；OAuth 視為已設定；Google 一律不打（list_* 由各測試換）。"""
    def _make(**kw):
        f = _St(**kw)
        monkeypatch.setattr(ost, "st", f)
        monkeypatch.setattr(gsp, "st", f)
        monkeypatch.setattr(ost, "sync_silent_marker", lambda: False)
        monkeypatch.setattr(ost, "is_oauth_configured", lambda: True)
        return f
    return _make


def _bound(sid=_A, **extra):
    return {"gsheet_tokens": dict(_TOK), "portfolio_sheet_id": sid, "stock_portfolio_sheet_id": sid, **extra}


# ══ get_active_sheet ═══════════════════════════════════════════════════════
class TestActiveSheet:
    @pytest.mark.parametrize("session, secrets, state, sid", [
        ({"portfolio_sheet_id": _A, "stock_portfolio_sheet_id": _A}, {}, B.ACTIVE_OK, _A),
        ({"portfolio_sheet_id": _A, "stock_portfolio_sheet_id": _B}, {}, B.ACTIVE_DIVERGED, ""),
        ({"portfolio_sheet_id": _A}, {}, B.ACTIVE_DIVERGED, ""),
        ({"stock_portfolio_sheet_id": _B}, {}, B.ACTIVE_DIVERGED, ""),
        ({}, {"portfolio_sheet_id": _B}, B.ACTIVE_DEPLOY_DEFAULT_ONLY, ""),
        ({}, {}, B.ACTIVE_NONE, ""),
    ])
    def test_states(self, fst, session, secrets, state, sid):
        fst(session=session, secrets=secrets)
        a = B.get_active_sheet()
        assert (a.state, a.sheet_id) == (state, sid)

    def test_diverged_never_picks_a_channel_and_writes_nothing(self, fst):
        f = fst(session={"portfolio_sheet_id": _A, "stock_portfolio_sheet_id": _B})
        before = dict(f.session_state)
        a = B.get_active_sheet()
        assert (a.portfolio_channel, a.stock_channel) == (_A, _B) and a.sheet_id == ""
        assert f.session_state == before and f.query_params == {}

    def test_snapshot_failure_is_read_error_not_none(self, fst, monkeypatch):
        fst()
        monkeypatch.setattr(gsp, "session_binding_snapshot", lambda: (_ for _ in ()).throw(OSError("x")))
        a = B.get_active_sheet()
        assert a.state == B.ACTIVE_NONE and "OSError" in a.read_error


# ══ get_binding_state(ssot=True) / get_binding_presence ═══════════════════════
class TestSsotBindingState:
    def test_default_call_unchanged_deploy_default_counts(self, fst, monkeypatch):
        fst(session={"gsheet_tokens": dict(_TOK)}, secrets={"portfolio_sheet_id": _B})
        monkeypatch.setattr(gsp, "list_portfolios", lambda **_k: ["X"])
        s = B.get_binding_state()
        assert (s.status, s.sheet_id, s.active_state) == (B.STATUS_BOUND, _B, "")

    def test_ssot_deploy_default_is_not_active(self, fst, monkeypatch):
        fst(session={"gsheet_tokens": dict(_TOK)}, secrets={"portfolio_sheet_id": _B})
        calls = []
        monkeypatch.setattr(gsp, "list_portfolios", lambda **k: calls.append(k) or ["X"])
        s = B.get_binding_state(ssot=True)
        assert (s.status, s.sheet_id, s.active_state) == (B.STATUS_UNBOUND, "", B.ACTIVE_DEPLOY_DEFAULT_ONLY)
        assert calls == []

    def test_ssot_diverged_is_unbound(self, fst, monkeypatch):
        fst(session=_bound(stock_portfolio_sheet_id=_B))
        monkeypatch.setattr(gsp, "list_portfolios", lambda **_k: ["X"])
        s = B.get_binding_state(ssot=True)
        assert (s.status, s.active_state) == (B.STATUS_UNBOUND, B.ACTIVE_DIVERGED)

    def test_ssot_ok_reads_that_sheet(self, fst, monkeypatch):
        fst(session=_bound(), secrets={"portfolio_sheet_id": _B})
        seen = []
        monkeypatch.setattr(gsp, "list_portfolios", lambda **k: seen.append(k["sheet_id"]) or ["X", "Y"])
        s = B.get_binding_state(ssot=True)
        assert (s.status, s.sheet_id, s.portfolio_count, s.active_state) == (B.STATUS_BOUND, _A, 2, B.ACTIVE_OK)
        assert seen == [_A]

    def test_presence_follows_ssot(self, fst):
        fst(session={"gsheet_tokens": dict(_TOK)}, secrets={"portfolio_sheet_id": _B})
        p = B.get_binding_presence()
        assert (p.logged_in, p.sheet_bound, p.active_state) == (True, False, B.ACTIVE_DEPLOY_DEFAULT_ONLY)
        fst(session=_bound())
        assert B.get_binding_presence().sheet_bound is True

    def test_presence_agrees_with_ssot_state(self, fst, monkeypatch):
        monkeypatch.setattr(gsp, "list_portfolios", lambda **_k: [])
        for session in (_bound(), _bound(stock_portfolio_sheet_id=_B), {"gsheet_tokens": dict(_TOK)},
                        {"portfolio_sheet_id": _A, "stock_portfolio_sheet_id": _A}):
            fst(session=session, secrets={"portfolio_sheet_id": _B})
            a, b = B.get_binding_presence(), B.get_binding_state(ssot=True)
            assert a.sheet_bound == (b.status != B.STATUS_UNBOUND), session
            assert a.active_state == b.active_state


# ══ selection ═══════════════════════════════════════════════════════════════
class TestSelection:
    def test_get_active_selection_needs_active_ok(self, fst):
        fst(session=_bound(stock_portfolio_sheet_id=_B))
        assert B.get_active_selection() == B.ActiveSelection()

    def test_select_portfolio_checks_name_exists(self, fst, monkeypatch):
        fst(session=_bound())
        monkeypatch.setattr(gsp, "list_portfolios", lambda **_k: ["長期", "波段"])
        assert ME.select_portfolio("不存在") == ME.SELECT_NAME_MISSING
        assert B.get_active_selection().portfolio == ""
        assert ME.select_portfolio("波段") == ME.SELECT_OK
        assert B.get_active_selection() == B.ActiveSelection(sheet_id=_A, portfolio="波段")

    def test_select_when_list_unreadable_writes_nothing(self, fst, monkeypatch):
        fst(session=_bound())

        def _boom(**_k):
            raise ConnectionError("net")
        monkeypatch.setattr(gsp, "list_portfolios", _boom)
        assert ME.select_portfolio("長期") == ME.SELECT_LIST_UNAVAILABLE
        assert B.get_active_selection().portfolio == ""

    def test_select_without_active_sheet(self, fst):
        fst(session={"gsheet_tokens": dict(_TOK)}, secrets={"portfolio_sheet_id": _B})
        assert ME.select_portfolio("x") == ME.SELECT_NO_ACTIVE_SHEET

    def test_watchlist_skip_and_clear(self, fst, monkeypatch):
        fst(session=_bound())
        monkeypatch.setattr(gsp, "list_stock_watchlists", lambda **_k: ["AI 鏈"])
        assert ME.select_watchlist(skip=True) == ME.SELECT_OK
        assert B.get_active_selection().watchlist_skip is True
        assert ME.select_watchlist("AI 鏈") == ME.SELECT_OK
        sel = B.get_active_selection()
        assert (sel.watchlist, sel.watchlist_skip) == ("AI 鏈", False)
        ME.clear_watchlist_selection()
        assert B.get_active_selection().watchlist == ""

    def test_changing_sheet_drops_selection(self, fst, monkeypatch):
        fst(session=_bound())
        monkeypatch.setattr(gsp, "list_portfolios", lambda **_k: ["長期"])
        ME.select_portfolio("長期")
        ME.bind_sheet(_B)
        assert B.get_active_selection() == B.ActiveSelection(sheet_id=_B)


# ══ me_account_service：帳號 / Sheet / 內容 ═══════════════════════════════════
class TestAccount:
    @pytest.mark.parametrize("email, masked", [
        ("abcd@gmail.com", "ab***@gmail.com"), ("ab@x.com", "a***@x.com"), ("a@x.com", "a***@x.com"),
        ("nodomain", "***"), ("", ""), (None, ""), ("@x.com", "***")])
    def test_mask_email(self, email, masked):
        assert ME.mask_email(email) == masked

    def test_states(self, fst, monkeypatch):
        fst(session={"gsheet_tokens": dict(_TOK), "gsheet_email": "abcd@gmail.com"})
        a = ME.get_account()
        assert (a.state, a.email_masked, a.login_url) == (ME.ACCOUNT_LOGGED_IN, "ab***@gmail.com", "")
        assert "abcd@" not in repr(a)
        monkeypatch.setattr(ost, "build_login_url", lambda: "https://accounts.google.com/x")
        fst()
        assert (ME.get_account().state, ME.get_account().login_url) == (
            ME.ACCOUNT_LOGGED_OUT, "https://accounts.google.com/x")
        from shared.oauth_session_policy import OAUTH_LOGIN_EXPIRED_SESSION_KEY
        fst(session={OAUTH_LOGIN_EXPIRED_SESSION_KEY: True})
        assert ME.get_account().state == ME.ACCOUNT_EXPIRED

    def test_not_configured(self, fst, monkeypatch):
        fst()
        monkeypatch.setattr(ost, "is_oauth_configured", lambda: False)
        assert ME.get_account().state == ME.ACCOUNT_NOT_CONFIGURED

    def test_read_failure_is_red_not_logged_out(self, fst, monkeypatch):
        fst()
        monkeypatch.setattr(ost, "is_oauth_configured", lambda: (_ for _ in ()).throw(KeyError("boom")))
        a = ME.get_account()
        assert a.state == ME.ACCOUNT_READ_FAILED and "boom" in a.error

    def test_logout_uses_shared_function(self, fst, monkeypatch):
        fst()
        calls = []
        monkeypatch.setattr(ost, "logout_google_session", lambda **k: calls.append(k))
        ME.logout()
        assert calls == [{}]


class TestSheetView:
    def test_only_active_ok_reads_title(self, fst, monkeypatch):
        calls = []
        monkeypatch.setattr(gsp, "read_sheet_title", lambda sid: calls.append(sid) or (gsp.READ_OK, "t"))
        for session, secrets in (({"gsheet_tokens": dict(_TOK)}, {"portfolio_sheet_id": _B}),
                                 (_bound(stock_portfolio_sheet_id=_B), {})):
            fst(session=session, secrets=secrets)
            v = ME.get_sheet_view()
            assert v.title_status == "" and calls == []
        fst(session=_bound())
        v = ME.get_sheet_view()
        assert (v.title_status, v.title, calls) == (gsp.READ_OK, "t", [_A])

    @pytest.mark.parametrize("exc, code", [
        (gsp.LoginRequiredError("x"), ME.TITLE_LOGIN_REQUIRED),
        (ConnectionError("n"), gsp.READ_ERROR_NETWORK),
        (ValueError("v"), "error:ValueError")])
    def test_title_errors_are_classified(self, fst, monkeypatch, exc, code):
        fst(session=_bound())

        def _raise(_sid):
            raise exc
        monkeypatch.setattr(gsp, "read_sheet_title", _raise)
        v = ME.get_sheet_view()
        assert v.title_status == code
        assert (v.title_error == "") == (code == ME.TITLE_LOGIN_REQUIRED)


class TestContents:
    def test_names_and_unknown_are_distinct(self, fst, monkeypatch):
        fst(session=_bound())
        monkeypatch.setattr(gsp, "list_portfolios", lambda **_k: [])

        def _missing(**_k):
            raise gsp.SheetWorksheetMissingError(gsp._STOCK_WATCHLIST_WORKSHEET)
        monkeypatch.setattr(gsp, "list_stock_watchlists", _missing)
        c = ME.get_sheet_contents(_A)
        assert c.portfolios == () and c.portfolio_issue == ""
        assert c.watchlists is None and c.watchlist_issue == gsp.READ_WORKSHEET_MISSING

    def test_schema_mismatch_and_network(self, fst, monkeypatch):
        fst(session=_bound())

        def _mm(**_k):
            raise gsp.SheetSchemaMismatchError(gsp._WORKSHEET_NAME, gsp._HEADERS)

        def _net(**_k):
            raise ConnectionError("x")
        monkeypatch.setattr(gsp, "list_portfolios", _mm)
        monkeypatch.setattr(gsp, "list_stock_watchlists", _net)
        c = ME.get_sheet_contents(_A)
        assert (c.portfolios, c.portfolio_issue) == (None, gsp.READ_SCHEMA_MISMATCH)
        assert (c.watchlists, c.watchlist_issue) == (None, gsp.READ_ERROR_NETWORK)

    def test_reads_are_raise_if_missing_and_explicit_sheet(self, fst, monkeypatch):
        fst(session=_bound())
        seen = []
        monkeypatch.setattr(gsp, "list_portfolios", lambda **k: seen.append(k) or ["P"])
        monkeypatch.setattr(gsp, "list_stock_watchlists", lambda **k: seen.append(k) or ["W"])
        ME.get_sheet_contents(_A)
        assert seen == [{"sheet_id": _A, "raise_if_missing": True}] * 2

    def test_drive_issue_reads_cause(self):
        try:
            try:
                raise ConnectionError("net")
            except ConnectionError as e:
                raise RuntimeError("列出 Drive Sheets 失敗") from e
        except RuntimeError as wrapped:
            assert ME.drive_issue(wrapped) == gsp.READ_ERROR_NETWORK

    def test_reload_targets_only_active_sheet(self, fst, monkeypatch):
        seen = []
        monkeypatch.setattr(B, "reload_my_sheet_reads", lambda *ids: seen.append(ids) or 1)
        fst(session=_bound(stock_portfolio_sheet_id=_B))
        assert ME.reload_reads() == 0 and seen == []
        fst(session=_bound())
        assert ME.reload_reads() == 1 and seen == [(_A,)]


# ══ 守衛：me_account_service 不碰任何寫入面 ═════════════════════════════════════
_WRITE_SURFACE = {"save_portfolio", "delete_portfolio", "save_stock_watchlist", "add_to_stock_watchlist",
                  "delete_stock_watchlist", "create_new_sheet", "rename_sheet", "append_forward_test_picks",
                  "clear_read_cache", "_get_or_create_app_folder", "invalidate_sheet_read_cache"}


def test_me_account_service_touches_no_write_surface():
    tree = ast.parse((_ROOT / "src/services/me_account_service.py").read_text(encoding="utf-8"))
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
            {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
            {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not names & _WRITE_SURFACE, names & _WRITE_SURFACE


def test_me_account_service_has_no_auto_bind_path():
    """DEC-083 C：⛔ 清單只有一本也不自動綁 —— 唯一呼叫契約的地方是 `bind_sheet`（on_click 才呼叫）。"""
    tree = ast.parse((_ROOT / "src/services/me_account_service.py").read_text(encoding="utf-8"))
    callers = {fn.name for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)
               for n in ast.walk(fn) if isinstance(n, ast.Attribute) and n.attr == "apply_sheet_binding"}
    assert callers == {"bind_sheet"}
    assert "len(" not in ast.unparse(next(f for f in tree.body
                                          if isinstance(f, ast.FunctionDef) and f.name == "list_drive_sheets"))


def test_selection_session_keys_shape_matches_l0():
    assert set(S.ACTIVE_SELECTION_SESSION_KEYS) == {S.SELECTION_KIND_PORTFOLIO, S.SELECTION_KIND_WATCHLIST}
