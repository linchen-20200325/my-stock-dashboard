"""👤 我的 P1（DEC-083）—— L0 `shared/sheet_id.py` 新增常數 / 純函式，以及 L1 `oauth_state` 的選定與共用登出。

客戶原文：
- Q4：「一般 UI 顯示：『Sheet 名稱＋ID 末 6 碼』。」
- Q5：「登出時同步清除：Google 登入 session、active Sheet binding、URL 上 "sheet" 參數、OAuth state／登入流程
  攜帶的舊 Sheet ID、會造成登出後重新自動綁回舊 Sheet 的 silent marker。不得登出後自動恢復上一個 Sheet。」
- Q7：「👤 我的提供新版全站共用：active portfolio／active watchlist。……不得再以『名稱排序第一本』作為不可見的業務決策。」
"""
from __future__ import annotations

import pytest

from shared import sheet_id as S

_ID = "1AbC_dEf-GhIjKlMnOpQrStUvWxYz0123456789abcd"   # 44 字元，同 Google 實測長度


# ══ L0 ═════════════════════════════════════════════════════════════════════
class TestSheetIdTail:
    def test_tail_is_last_six_with_ellipsis(self):
        assert S.SHEET_ID_TAIL_LEN == 6
        assert S.sheet_id_tail(_ID) == "…" + _ID[-6:]
        assert _ID not in S.sheet_id_tail(_ID)

    @pytest.mark.parametrize("raw", ["", None, "   ", "e", "含 空白", "<b>x</b>", "a" * 121])
    def test_unusable_id_gives_empty(self, raw):
        assert S.sheet_id_tail(raw) == ""

    def test_short_id_is_not_padded(self):
        assert S.sheet_id_tail("abc") == "…abc"


class TestSelectionKeys:
    def test_kinds_map_to_distinct_keys(self):
        _keys = S.ACTIVE_SELECTION_SESSION_KEYS
        assert set(_keys) == {S.SELECTION_KIND_PORTFOLIO, S.SELECTION_KIND_WATCHLIST}
        assert len(set(_keys.values())) == 2
        assert S.ACTIVE_PORTFOLIO_SESSION_KEY in _keys.values()
        assert S.ACTIVE_WATCHLIST_SESSION_KEY in _keys.values()

    def test_selection_keys_do_not_collide_with_binding_keys(self):
        assert not set(S.ACTIVE_SELECTION_SESSION_KEYS.values()) & set(S.SHEET_BINDING_SESSION_KEYS)

    def test_logout_extra_keys_are_the_me_page_keys(self):
        # PR #927 QA-2 第 5 點：選擇器 4 個 + Drive 失敗代碼也列入（~~原本只有 Drive 清單 2 個 + 貼上框 + 側欄框~~
        #   ⇒ 側欄登出後 👤 我的頁的選擇器 / 失敗訊息會殘留；有意識的修改，⛔ 不是漏改）。
        assert set(S.LOGOUT_EXTRA_SESSION_KEYS) == {
            S.ME_DRIVE_FOLDERS_SESSION_KEY, S.ME_DRIVE_SHEETS_SESSION_KEY, S.ME_PASTE_INPUT_KEY,
            S.ME_FOLDER_PICK_KEY, S.ME_SHEET_PICK_KEY, S.ME_PORTFOLIO_PICK_KEY, S.ME_WATCHLIST_PICK_KEY,
            S.ME_DRIVE_ERROR_KEY, S.SIDEBAR_SHEET_INPUT_KEY}
        assert all(_k.startswith("p07me_") for _k in S.LOGOUT_EXTRA_SESSION_KEYS
                   if _k != S.SIDEBAR_SHEET_INPUT_KEY)

    def test_sidebar_input_key_matches_app_literal(self):
        app = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        assert f"key='{S.SIDEBAR_SHEET_INPUT_KEY}'" in app


# ══ L1 oauth_state：選定（Q7）＋ 共用登出（Q5）════════════════════════════════
import ast   # noqa: E402
import pathlib   # noqa: E402

import src.data.portfolio.oauth_state as ost   # noqa: E402
from shared.oauth_session_policy import (   # noqa: E402
    OAUTH_LOGIN_EXPIRED_SESSION_KEY,
    OAUTH_SILENT_ATTEMPTED_SESSION_KEY,
    OAUTH_SILENT_ELIGIBLE_SESSION_KEY,
    OAUTH_SILENT_MARKER_PARAM,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_PF, _WL = S.SELECTION_KIND_PORTFOLIO, S.SELECTION_KIND_WATCHLIST
_OTHER = "2ZyX_wVu-TsRqPoNmLkJiHgFeDcBa9876543210zyxw"


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
        monkeypatch.setattr(ost, "sync_silent_marker", lambda: False)
        return f
    return _make


class TestActiveSelection:
    def test_set_then_get_same_sheet(self, fst):
        fst()
        ost.set_active_selection(_PF, " 長期存股 ", _ID)
        assert ost.get_active_selection(_PF, _ID) == {"name": "長期存股", "skip": False}
        assert ost.get_active_selection(_WL, _ID) is None

    def test_other_sheet_sees_nothing(self, fst):
        fst()
        ost.set_active_selection(_PF, "A", _ID)
        assert ost.get_active_selection(_PF, _OTHER) is None
        assert ost.get_active_selection(_PF, "") is None

    def test_watchlist_skip(self, fst):
        fst()
        ost.set_active_selection(_WL, "ignored", _ID, skip=True)
        assert ost.get_active_selection(_WL, _ID) == {"name": "", "skip": True}

    @pytest.mark.parametrize("kind, name, sid, skip", [
        (_PF, "A", "", False), (_PF, "A", "含 空白", False), (_PF, "", _ID, False),
        (_PF, "A", _ID, True), ("bogus", "A", _ID, False)])
    def test_bad_input_writes_nothing(self, fst, kind, name, sid, skip):
        f = fst()
        with pytest.raises(ValueError):
            ost.set_active_selection(kind, name, sid, skip=skip)
        assert f.session_state == {}

    def test_malformed_session_value_is_none(self, fst):
        fst(session={S.ACTIVE_PORTFOLIO_SESSION_KEY: "A", S.ACTIVE_WATCHLIST_SESSION_KEY:
                     {"sheet_id": _ID, "name": "", "skip": False}})
        assert ost.get_active_selection(_PF, _ID) is None
        assert ost.get_active_selection(_WL, _ID) is None

    def test_clear(self, fst):
        f = fst()
        ost.set_active_selection(_PF, "A", _ID)
        ost.set_active_selection(_WL, "B", _ID)
        ost.clear_active_selection(_WL)
        assert ost.get_active_selection(_WL, _ID) is None and ost.get_active_selection(_PF, _ID)
        ost.clear_active_selection()
        assert not set(S.ACTIVE_SELECTION_SESSION_KEYS.values()) & set(f.session_state)

    def test_binding_to_another_sheet_clears_selection(self, fst):
        fst()
        ost.apply_sheet_binding(_ID)
        ost.set_active_selection(_PF, "A", _ID)
        ost.apply_sheet_binding(_OTHER)
        assert ost.get_active_selection(_PF, _ID) is None
        assert ost.get_active_selection(_PF, _OTHER) is None

    def test_rebinding_same_sheet_keeps_selection(self, fst):
        """兩格已是這一本、只差網址 `?sheet=` → 契約照寫（`changed=True`），但 Sheet 沒換 ⇒ 選定保留。"""
        f = fst(session={"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID}, query={})
        ost.set_active_selection(_PF, "A", _ID)
        r = ost.apply_sheet_binding(_ID)          # 只差 ?sheet= ⇒ 兩格值不變
        assert r.changed and f.query_params == {"sheet": _ID}
        assert ost.get_active_selection(_PF, _ID) == {"name": "A", "skip": False}

    def test_clear_binding_clears_selection(self, fst):
        fst(session={"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID})
        ost.set_active_selection(_PF, "A", _ID)
        ost.set_active_selection(_WL, "", _ID, skip=True)
        ost.clear_sheet_binding()
        assert ost.get_active_selection(_PF, _ID) is None
        assert ost.get_active_selection(_WL, _ID) is None


class TestSharedLogout:
    def _logged_in(self, fst):
        f = fst(session={"gsheet_tokens": {"access_token": "x"}, "gsheet_email": "ab@x.com",
                         "_oauth_state": "nonce", "portfolio_sheet_id": _ID,
                         "stock_portfolio_sheet_id": _ID, OAUTH_SILENT_ELIGIBLE_SESSION_KEY: True,
                         OAUTH_LOGIN_EXPIRED_SESSION_KEY: True,
                         S.ME_DRIVE_SHEETS_SESSION_KEY: [{"id": _ID, "name": "n"}],
                         S.ME_DRIVE_FOLDERS_SESSION_KEY: [], S.ME_PASTE_INPUT_KEY: _ID,
                         "sb_portfolio_sheet_id_input": _ID, "unrelated": 1},
                query={"sheet": _ID, OAUTH_SILENT_MARKER_PARAM: "a" * 16, "sid": "2330"})
        ost.set_active_selection(_PF, "A", _ID)
        ost.set_active_selection(_WL, "B", _ID)
        return f

    def test_logout_clears_everything_q5_lists(self, fst):
        f = self._logged_in(fst)
        ost.logout_google_session(extra_session_keys=("sb_portfolio_sheet_id_input",))
        for _k in ("gsheet_tokens", "gsheet_email", "_oauth_state", "portfolio_sheet_id",
                   "stock_portfolio_sheet_id", OAUTH_SILENT_ELIGIBLE_SESSION_KEY,
                   OAUTH_LOGIN_EXPIRED_SESSION_KEY, "sb_portfolio_sheet_id_input",
                   *S.LOGOUT_EXTRA_SESSION_KEYS, *S.ACTIVE_SELECTION_SESSION_KEYS.values()):
            assert _k not in f.session_state, _k
        assert f.session_state[OAUTH_SILENT_ATTEMPTED_SESSION_KEY] is True
        assert f.session_state["unrelated"] == 1
        assert f.query_params == {"sid": "2330"}

    def test_after_logout_login_state_carries_no_sheet(self, fst, monkeypatch):
        self._logged_in(fst)
        ost.logout_google_session()
        monkeypatch.setattr(ost, "get_login_state", lambda: "NONCE")
        monkeypatch.setattr(ost, "get_oauth_cfg", lambda: {"client_id": "c", "redirect_uri": "r"})
        seen = {}
        monkeypatch.setattr(ost, "build_authorize_url",
                            lambda cid, ru, *, state: seen.setdefault("state", state) or "u")
        ost.build_login_url()
        assert seen["state"] == "NONCE"

    def test_sidebar_equivalent_steps_in_order(self, fst, monkeypatch):
        """修前側欄 inline 的四步（pop 三鍵 → forget → clear → pop 側欄框）順序不變。"""
        self._logged_in(fst)
        calls = []
        monkeypatch.setattr(ost, "forget_silent_reauth", lambda: calls.append("forget"))
        monkeypatch.setattr(ost, "clear_sheet_binding", lambda: calls.append("clear"))
        ost.logout_google_session(extra_session_keys=("sb_portfolio_sheet_id_input",))
        assert calls == ["forget", "clear"]
        assert "gsheet_tokens" not in ost.st.session_state
        assert "sb_portfolio_sheet_id_input" not in ost.st.session_state


class TestBuildLoginUrl:
    def test_not_configured_gives_empty(self, fst, monkeypatch):
        fst()
        monkeypatch.setattr(ost, "get_oauth_cfg", lambda: None)
        assert ost.build_login_url() == ""

    def test_carries_session_sheet_not_deploy_default(self, fst, monkeypatch):
        fst(session={"portfolio_sheet_id": _ID}, secrets={"portfolio_sheet_id": _OTHER})
        monkeypatch.setattr(ost, "get_login_state", lambda: "NONCE")
        monkeypatch.setattr(ost, "get_oauth_cfg", lambda: {"client_id": "c", "redirect_uri": "r"})
        monkeypatch.setattr(ost, "build_authorize_url",
                            lambda cid, ru, *, state: f"https://accounts.google.com/o?state={state}")
        assert ost.build_login_url().endswith(f"state=NONCE.{_ID}")

    def test_deploy_default_only_carries_nothing(self, fst, monkeypatch):
        fst(secrets={"portfolio_sheet_id": _OTHER})
        monkeypatch.setattr(ost, "get_login_state", lambda: "NONCE")
        monkeypatch.setattr(ost, "get_oauth_cfg", lambda: {"client_id": "c", "redirect_uri": "r"})
        monkeypatch.setattr(ost, "build_authorize_url", lambda cid, ru, *, state: state)
        assert ost.build_login_url() == "NONCE"


# ── 守衛：選定的 session key 只准由 L1 三支函式寫 / 清 ─────────────────────────────
_SEL_NAMES = {"ACTIVE_PORTFOLIO_SESSION_KEY", "ACTIVE_WATCHLIST_SESSION_KEY", "ACTIVE_SELECTION_SESSION_KEYS"}
_SEL_LITERALS = set(S.ACTIVE_SELECTION_SESSION_KEYS.values())
_SEL_WRITERS = {("src/data/portfolio/oauth_state.py", "set_active_selection"),
                ("src/data/portfolio/oauth_state.py", "clear_active_selection")}


def _py_files():
    for base in ("src", "shared", "scripts", "infra", "mcp_server"):
        p = _ROOT / base
        if p.exists():
            yield from (f for f in sorted(p.rglob("*.py")) if "__pycache__" not in f.parts)
    yield _ROOT / "app.py"


def _refs_selection_key(node) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and n.value in _SEL_LITERALS:
            return True
        if isinstance(n, ast.Name) and n.id in _SEL_NAMES:
            return True
        if isinstance(n, ast.Attribute) and n.attr in _SEL_NAMES:
            return True
    return False


def _fn_of(tree):
    parent = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}

    def _f(n):
        while n in parent:
            n = parent[n]
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return n.name
        return "<module>"
    return _f


def test_selection_keys_written_only_by_l1_selection_functions():
    """⚠️ 已知盲點（據實）：經區域變數間接取 key（例 L1 自己的 `_key = _selection_key(kind)`）掃不到 ——
    L1 那兩支由下一條對照組釘住；其他檔若這樣寫，本守衛抓不到。"""
    hits = []
    for f in _py_files():
        rel = f.relative_to(_ROOT).as_posix()
        if rel == "shared/sheet_id.py":
            continue
        tree = ast.parse(f.read_text(encoding="utf-8"))
        fn = _fn_of(tree)
        for n in ast.walk(tree):
            bad = False
            if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
                tgts = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]
                # 任何 `session_state[...] = ` 只要下標引用選定 key（常數或字面值）就算
                bad = any(isinstance(t, ast.Subscript) and "session" in ast.unparse(t.value)
                          and _refs_selection_key(t.slice) for t in tgts)
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr in ("pop", "setdefault", "update", "__setitem__", "__delitem__")
                  and "session" in ast.unparse(n.func.value)):
                bad = any(_refs_selection_key(a) for a in n.args)
            if bad and (rel, fn(n)) not in _SEL_WRITERS:
                hits.append(f"{rel}:{n.lineno} ({fn(n)})")
    assert not hits, f"active 選定 session key 在 L1 唯一寫入者以外被寫入：{hits}"


def test_selection_guard_is_not_vacuous():
    """對照組：L1 兩支寫入者確實經 `_selection_key()` 寫 / 清（守衛的白名單不是空殼）。"""
    src = (_ROOT / "src/data/portfolio/oauth_state.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fns = {n.name: ast.unparse(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "st.session_state[_key] =" in fns["set_active_selection"]
    assert "st.session_state.pop(_selection_key(_k), None)" in fns["clear_active_selection"]
    assert "ACTIVE_SELECTION_SESSION_KEYS[kind]" in fns["_selection_key"]


# ── 共用登出：側欄與「👤 我的」頁結束狀態完全相同（DEC-083 Q5）──────────────────────────
def test_sidebar_and_me_page_logout_end_states_are_identical(fst):
    """側欄：`logout_google_session(extra_session_keys=('sb_portfolio_sheet_id_input',))`；
    「👤 我的」頁：L3 `me_account_service.logout()`（不帶 extra）。兩者跑完 session 與網址必須一模一樣。"""
    from src.services import me_account_service as ME

    def _start():
        f = fst(session={"gsheet_tokens": {"access_token": "x"}, "gsheet_email": "ab@x.com",
                         "_oauth_state": "nonce", "portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID,
                         OAUTH_SILENT_ELIGIBLE_SESSION_KEY: True, S.SIDEBAR_SHEET_INPUT_KEY: _ID,
                         S.ME_DRIVE_SHEETS_SESSION_KEY: [{"id": _ID, "name": "n"}], "keep": 1},
                query={"sheet": _ID, OAUTH_SILENT_MARKER_PARAM: "a" * 16})
        ost.set_active_selection(_PF, "A", _ID)
        return f

    a = _start()
    ost.logout_google_session(extra_session_keys=(S.SIDEBAR_SHEET_INPUT_KEY,))
    end_a = (dict(a.session_state), dict(a.query_params))
    b = _start()
    ME.logout()
    end_b = (dict(b.session_state), dict(b.query_params))
    assert end_a == end_b
    assert end_a[0] == {OAUTH_SILENT_ATTEMPTED_SESSION_KEY: True, S.SHEET_BINDING_VERSION_SESSION_KEY: 1,
                        "keep": 1}
    assert end_a[1] == {}
