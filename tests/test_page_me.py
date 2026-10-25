"""👤 我的 P1（DEC-083）—— L5 `src/ui/views/page_me.py`。

客戶原文（C 段）：「唯一本 Sheet 自動綁 取消。就算 Drive 只有一本：仍要使用者明確按『使用這本』。不要替使用者做綁定決策。」
（Q4）「一般 UI 顯示：『Sheet 名稱＋ID 末 6 碼』。」（B5）「重新讀取不得默認清除所有使用者的全域 cache。」

三張卡每一態都有文字、缺 ≠ 0、動作 callback（使用這本只呼叫契約一次、一本不自動綁、重新讀取不 `.clear()`、
登出走共用函式）、AST 黑名單、key 前綴、指路字面與 app.py 對帳；AppTest 實跑整頁（44 碼 ID 不出現在畫面）。
"""
from __future__ import annotations

import ast
import pathlib
import types

import pytest

import src.data.portfolio.oauth_state as ost
from shared import ia_nav
from shared import sheet_id as S
from src.data.portfolio import gsheet_portfolio as gsp
from src.services import me_account_service as ME
from src.services import portfolio_binding_service as PB
from src.ui.views import page_me as P

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC = (_ROOT / "src/ui/views/page_me.py").read_text(encoding="utf-8")
_ID = "1AbC_dEf-GhIjKlMnOpQrStUvWxYz0123456789abcd"   # 44 字元
_ID2 = "2ZyX_wVu-TsRqPoNmLkJiHgFeDcBa9876543210zyxw"
_TOK = {"access_token": "at", "refresh_token": "rt"}


def _active(state, sid="", pf="", stk="", dflt="", err=""):
    return PB.ActiveSheet(state=state, sheet_id=sid, portfolio_channel=pf, stock_channel=stk,
                          deploy_default=dflt, read_error=err)


def _texts(card: P.CardView) -> str:
    return "\n".join((card.title, card.status, *card.lines, *card.captions))


# ══ 卡① ═════════════════════════════════════════════════════════════════════
class TestAccountCard:
    @pytest.mark.parametrize("acct, needle", [
        (ME.AccountView(state=ME.ACCOUNT_NOT_CONFIGURED), "本站尚未設定 Google 登入（部署設定，不是你的操作問題）"),
        (ME.AccountView(state=ME.ACCOUNT_LOGGED_OUT, login_url="u"), "⬜ 尚未登入"),
        (ME.AccountView(state=ME.ACCOUNT_EXPIRED, login_url="u"), "登入已逾時"),
        (ME.AccountView(state=ME.ACCOUNT_LOGGED_IN, email_masked="ab***@gmail.com"), "🟢 已登入 ab\\*\\*\\*@gmail.com"),
        (ME.AccountView(state=ME.ACCOUNT_READ_FAILED, error="KeyError('x')"), "🔴 登入狀態讀取失敗"),
    ])
    def test_every_state_has_text(self, acct, needle):
        card = P.build_account_card(acct)
        assert card.title == P.CARD_ACCOUNT_TITLE and needle in _texts(card)

    def test_logged_out_says_reselect_page_after_login(self):
        card = P.build_account_card(ME.AccountView(state=ME.ACCOUNT_LOGGED_OUT))
        assert "請在側欄再選一次「👤 我的」" in _texts(card)

    def test_expired_is_grey_not_red(self):
        assert P.build_account_card(ME.AccountView(state=ME.ACCOUNT_EXPIRED)).status.startswith("⬜")

    def test_error_is_scrubbed(self):
        card = P.build_account_card(ME.AccountView(state=ME.ACCOUNT_READ_FAILED,
                                                   error=f"OSError('/home/u/.streamlit/secrets.toml {_ID}')"))
        assert _ID not in _texts(card)


# ══ 卡② ═════════════════════════════════════════════════════════════════════
class TestSheetCard:
    def _card(self, active, *, logged_in=True, **kw):
        return P.build_sheet_card(ME.SheetView(active=active, **kw), logged_in=logged_in)

    def test_needs_login(self):
        assert self._card(_active(PB.ACTIVE_OK, _ID, _ID, _ID), logged_in=False).status == P.SHEET_NEED_LOGIN

    def test_none(self):
        assert self._card(_active(PB.ACTIVE_NONE)).status == P.SHEET_NONE

    def test_deploy_default_is_not_active_and_shows_tail_only(self):
        card = self._card(_active(PB.ACTIVE_DEPLOY_DEFAULT_ONLY, dflt=_ID))
        assert card.status == P.SHEET_DEFAULT_ONLY
        assert "…" + _ID[-6:] in _texts(card) and _ID not in _texts(card)
        assert P.USE_SHEET_LABEL in _texts(card)

    def test_diverged_plain_warning_no_channel_word(self):
        card = self._card(_active(PB.ACTIVE_DIVERGED, pf=_ID, stk=_ID2))
        t = _texts(card)
        assert card.status.startswith("⚠️ 你的「組合」和「觀察清單」目前讀的是兩本不同的 Sheet")
        assert "…" + _ID[-6:] in t and "…" + _ID2[-6:] in t and _ID not in t and _ID2 not in t
        assert "通道" not in t and "ETF" not in t

    def test_diverged_one_side_unset(self):
        assert P.SHEET_UNSET_TAIL in self._card(_active(PB.ACTIVE_DIVERGED, pf=_ID)).status

    @pytest.mark.parametrize("kw, needle", [
        ({"title_status": gsp.READ_OK, "title": "台股投組 2026"}, "📗「台股投組 2026」"),
        ({"title_status": gsp.READ_OK, "title": ""}, "沒有標題"),
        ({"title_status": ME.TITLE_LOGIN_REQUIRED}, "標題尚未讀取"),
        ({"title_status": gsp.READ_ERROR_SHEET_NOT_FOUND}, "🔴 這本 Sheet 打不開：找不到"),
        ({"title_status": gsp.READ_ERROR_PERMISSION_DENIED}, "🔴 這本 Sheet 打不開：你的 Google 帳號沒有權限"),
        ({"title_status": gsp.READ_ERROR_QUOTA_EXCEEDED}, "可稍後按「🔄 重新讀取」"),
        ({"title_status": gsp.READ_ERROR_NETWORK}, "網路連線失敗"),
        ({"title_status": "error:ValueError", "title_error": f"ValueError('{_ID}')"}, "🔴 讀取 Sheet 失敗"),
    ])
    def test_ok_states(self, kw, needle):
        card = self._card(_active(PB.ACTIVE_OK, _ID, _ID, _ID), **kw)
        t = _texts(card)
        assert needle in t and "…" + _ID[-6:] in t and _ID not in t

    def test_title_with_markdown_is_escaped(self):
        card = self._card(_active(PB.ACTIVE_OK, _ID, _ID, _ID), title_status=gsp.READ_OK, title="**粗**[x](y)")
        assert "**粗**" not in card.status and "\\*\\*粗\\*\\*" in card.status

    def test_snapshot_read_error_is_red(self):
        card = self._card(_active(PB.ACTIVE_NONE, err="OSError('boom')"))
        assert card.status.startswith("🔴")


# ══ 卡③ ═════════════════════════════════════════════════════════════════════
def _contents(pf=(), wl=(), *, pf_issue="", wl_issue="", sel=None, pf_err="", wl_err=""):
    return ME.SheetContents(sheet_id=_ID, portfolios=pf, portfolio_issue=pf_issue, portfolio_error=pf_err,
                            watchlists=wl, watchlist_issue=wl_issue, watchlist_error=wl_err,
                            selection=sel or PB.ActiveSelection(sheet_id=_ID))


class TestContentCard:
    def test_not_read_is_not_zero(self):
        for kw in ({"logged_in": False, "active_ok": True}, {"logged_in": True, "active_ok": False}):
            card = P.build_content_card(None, **kw)
            assert card.status == P.CONTENT_NOT_READ and "0 本" not in card.status.replace("不是 0 本", "")

    def test_unknown_lists_never_say_zero(self):
        card = P.build_content_card(_contents(pf=None, wl=None, pf_issue=gsp.READ_ERROR_NETWORK,
                                              wl_issue=gsp.READ_ERROR_NETWORK),
                                    logged_in=True, active_ok=True)
        t = _texts(card)
        assert "0 本" not in t and "0 份" not in t and "🔴 組合清單讀取失敗" in t

    def test_worksheet_missing_and_schema_mismatch(self):
        card = P.build_content_card(_contents(pf=None, wl=None, pf_issue=gsp.READ_WORKSHEET_MISSING,
                                              wl_issue=gsp.READ_SCHEMA_MISMATCH),
                                    logged_in=True, active_ok=True)
        t = _texts(card)
        assert "這本 Sheet 沒有「portfolios」分頁（本頁不會替你建立）" in t
        assert "⚠️ 資料疑義：「stock_watchlist」分頁第一列應為 name、ticker、updated_at，本頁未讀取也未修改" in t

    def test_truly_empty_is_valid(self):
        t = _texts(P.build_content_card(_contents(), logged_in=True, active_ok=True))
        assert P.PF_EMPTY in t and P.WL_EMPTY in t

    def test_names_and_not_selected(self):
        t = _texts(P.build_content_card(_contents(pf=("長期", "波段"), wl=("AI 鏈",)),
                                        logged_in=True, active_ok=True))
        assert "組合 2 本：「長期」、「波段」" in t and P.PF_NOT_SELECTED in t and P.WL_NOT_SELECTED in t

    def test_selected_and_missing(self):
        sel = PB.ActiveSelection(sheet_id=_ID, portfolio="不見了", watchlist="AI 鏈")
        t = _texts(P.build_content_card(_contents(pf=("長期",), wl=("AI 鏈",), sel=sel),
                                        logged_in=True, active_ok=True))
        assert "⚠️ 你選定的組合「不見了」在這本 Sheet 裡找不到" in t and "「AI 鏈」" in t

    def test_skip(self):
        sel = PB.ActiveSelection(sheet_id=_ID, watchlist_skip=True)
        assert P.WL_SKIPPED in _texts(P.build_content_card(_contents(wl=("x",), sel=sel),
                                                           logged_in=True, active_ok=True))

    def test_edit_where_is_customer_sentence_verbatim(self):
        t = _texts(P.build_content_card(_contents(), logged_in=True, active_ok=True))
        assert "目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。" in t

    def test_used_by_pages_use_ia_nav_labels(self):
        for page in (ia_nav.PAGE_HOLD, ia_nav.PAGE_FIND, ia_nav.PAGE_TODAY):
            assert any(_ln.startswith(ia_nav.page_label(page)) for _ln in P.USED_BY_LINES)


# ══ 卡名 ＝ ia_nav 分區名（指路句與卡名同一個 SSOT）═══════════════════════════════
def test_card_titles_match_ia_nav_sections():
    for title, sec in ((P.CARD_ACCOUNT_TITLE, ia_nav.SECTION_ME_ACCOUNT),
                       (P.CARD_SHEET_TITLE, ia_nav.SECTION_ME_SHEET),
                       (P.CARD_CONTENT_TITLE, ia_nav.SECTION_ME_CONTENT)):
        assert title.endswith(ia_nav.SECTION_LABELS[sec])


def test_switch_back_literals_exist_in_app():
    app = (_ROOT / "app.py").read_text(encoding="utf-8")
    assert f"'{P.OLD_UI_NAV_LABEL}'" in app and f"_IA_NAV_OFF = '{P.OLD_UI_NAV_OFF}'" in app
    assert f"'{P.OLD_UI_TAB}'" in app


# ══ 動作 callback（假 st；L3 換成記錄替身）═══════════════════════════════════════
class _FakeSt(types.SimpleNamespace):
    pass


@pytest.fixture
def fake(monkeypatch):
    f = _FakeSt(session_state={})
    monkeypatch.setattr(P, "st", f)
    return f


def test_use_sheet_calls_contract_exactly_once(fake, monkeypatch):
    calls = []
    monkeypatch.setattr(ost, "apply_sheet_binding",
                        lambda raw: calls.append(raw) or ost.SheetBindResult(sheet_id=raw, changed=True))
    P._on_use_sheet(_ID)
    assert calls == [_ID]
    kind, text = fake.session_state[P.SS_FLASH][0]
    assert kind == "success" and _ID not in text and "…" + _ID[-6:] in text


def test_drive_pick_without_choice_binds_nothing(fake, monkeypatch):
    calls = []
    monkeypatch.setattr(ost, "apply_sheet_binding", lambda raw: calls.append(raw))
    fake.session_state[S.ME_DRIVE_SHEETS_SESSION_KEY] = [{"id": _ID, "name": "唯一一本"}]
    P._on_use_drive_pick()
    assert calls == [] and fake.session_state[P.SS_FLASH][0][1] == P.DRIVE_PICK_FIRST


def test_listing_one_sheet_does_not_bind(fake, monkeypatch):
    """DEC-083 C：Drive 只有一本也不自動綁 —— 列清單只寫清單、不碰綁定。"""
    calls = []
    monkeypatch.setattr(ost, "apply_sheet_binding", lambda raw: calls.append(raw))
    monkeypatch.setattr(ME, "list_drive_sheets", lambda folder="": [{"id": _ID, "name": "唯一一本"}])
    P._load_drive("sheets")
    assert fake.session_state[S.ME_DRIVE_SHEETS_SESSION_KEY] == [{"id": _ID, "name": "唯一一本"}]
    assert calls == [] and P.SS_SHEET_PICK not in fake.session_state


def test_drive_failure_is_reported_not_faked(fake, monkeypatch):
    def _boom(folder=""):
        try:
            raise ConnectionError("net")
        except ConnectionError as e:
            raise RuntimeError("列出 Drive Sheets 失敗") from e
    monkeypatch.setattr(ME, "list_drive_sheets", _boom)
    fake.session_state[S.ME_DRIVE_SHEETS_SESSION_KEY] = [{"id": "OLD", "name": "舊清單"}]
    P._load_drive("sheets")
    assert S.ME_DRIVE_SHEETS_SESSION_KEY not in fake.session_state
    assert fake.session_state[P.SS_DRIVE_ERROR].startswith(gsp.READ_ERROR_NETWORK)


def test_reload_never_clears_global_cache(fake, monkeypatch):
    import streamlit as real_st

    def _bomb(*_a, **_k):
        raise AssertionError("⛔ 重新讀取不得呼叫全域 st.cache_data.clear()")
    monkeypatch.setattr(real_st.cache_data, "clear", _bomb)
    monkeypatch.setattr(gsp, "clear_read_cache", _bomb)
    seen = []
    monkeypatch.setattr(PB, "get_active_sheet", lambda: _active(PB.ACTIVE_OK, _ID, _ID, _ID))
    monkeypatch.setattr(gsp, "invalidate_my_read_cache", lambda *ids: seen.append(ids) or 1)
    P._on_reload()
    assert seen == [(_ID,)] and fake.session_state[P.SS_FLASH][0] == ("success", P.RELOAD_DONE)


def test_logout_goes_through_shared_function(fake, monkeypatch):
    calls = []
    monkeypatch.setattr(ost, "logout_google_session", lambda **k: calls.append(k))
    fake.session_state.update({P.SS_PF_PICK: "A", P.SS_SHEET_PICK: _ID})
    P._on_logout()
    assert calls == [{}] and P.SS_PF_PICK not in fake.session_state


@pytest.mark.parametrize("code, needle", [
    (ME.SELECT_NAME_MISSING, "不在這本 Sheet 的清單裡"), (ME.SELECT_LIST_UNAVAILABLE, "清單現在讀不到"),
    (ME.SELECT_NO_ACTIVE_SHEET, "還沒有選定 Sheet")])
def test_select_failures_are_told(fake, monkeypatch, code, needle):
    monkeypatch.setattr(ME, "select_portfolio", lambda name: code)
    fake.session_state[P.SS_PF_PICK] = "A"
    P._on_pick_portfolio()
    assert needle in fake.session_state[P.SS_FLASH][0][1]


def test_watchlist_skip_option(fake, monkeypatch):
    calls = []
    monkeypatch.setattr(ME, "select_watchlist", lambda name="", *, skip=False: calls.append((name, skip)) or ME.SELECT_OK)
    fake.session_state[P.SS_WL_PICK] = P.WATCHLIST_SKIP_OPTION
    P._on_pick_watchlist()
    assert calls == [("", True)]


def test_picking_none_clears(fake, monkeypatch):
    calls = []
    monkeypatch.setattr(ME, "clear_portfolio_selection", lambda: calls.append("pf"))
    fake.session_state[P.SS_PF_PICK] = None
    P._on_pick_portfolio()
    assert calls == ["pf"]


# ══ 靜態守衛 ═══════════════════════════════════════════════════════════════════
_BLACKLIST_EXACT = {"create_new_sheet", "rename_sheet", "append_forward_test_picks", "clear_read_cache",
                    "invalidate_sheet_read_cache", "_get_or_create_app_folder"}
_BLACKLIST_PREFIX = ("save_", "delete_", "add_to_")


def _identifiers(src: str) -> set[str]:
    tree = ast.parse(src)
    return ({n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            | {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names})


def test_page_me_touches_no_write_surface():
    ids = _identifiers(_SRC)
    bad = {i for i in ids if i in _BLACKLIST_EXACT or i.startswith(_BLACKLIST_PREFIX)}
    assert not bad, bad


def test_page_me_imports_no_l1_and_no_global_clear():
    tree = ast.parse(_SRC)
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
           {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(str(m).startswith("src.data") for m in mods), mods
    clears = [ast.unparse(n) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "clear"]
    assert clears == [], clears


def test_all_widget_keys_have_page_prefix():
    tree = ast.parse(_SRC)
    keys = [kw.value for n in ast.walk(tree) if isinstance(n, ast.Call)
            for kw in n.keywords if kw.arg == "key"]
    lits = [k.value for k in keys if isinstance(k, ast.Constant)]
    names = [k.id for k in keys if isinstance(k, ast.Name)]
    assert lits and all(str(v).startswith("p07me_") for v in lits), lits
    for nm in names:
        if nm == "_key":   # 不一致時兩顆按鈕的迴圈變數；值是下面那組字面（同樣要帶前綴）
            assert {"p07me_use_pf_side", "p07me_use_wl_side"} <= {
                n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)}
            continue
        assert str(getattr(P, nm, getattr(S, nm, ""))).startswith("p07me_"), nm
    assert all(str(getattr(P, n)).startswith("p07me_") for n in dir(P) if n.startswith("SS_"))


def test_page_me_never_auto_binds():
    """唯一呼叫綁定的路徑是使用者按鈕的 callback（`_on_use_sheet` / 文字框 on_change）。"""
    tree = ast.parse(_SRC)
    callers = {fn.name for fn in ast.walk(tree) if isinstance(fn, ast.FunctionDef)
               for n in ast.walk(fn) if isinstance(n, ast.Attribute) and n.attr in ("bind_sheet", "on_paste_change")}
    assert callers == {"_on_use_sheet", "_on_paste"}
    assert "index=None" in _SRC


# ══ AppTest 實跑整頁（44 碼 ID 永不出現在畫面上；實測三條合計約 2 秒 ⇒ 留在 fast lane）══════════════════════════════
_SCRIPT = """
from src.ui.views.page_me import render_page_me
render_page_me()
"""


@pytest.fixture
def stub_l1(monkeypatch):
    """登入＋已綁一本；Google 讀取全換成替身（不打網路）。"""
    monkeypatch.setattr(ost, "is_oauth_configured", lambda: True)
    monkeypatch.setattr(gsp, "read_sheet_title", lambda sid: (gsp.READ_OK, "台股投組 2026"))
    monkeypatch.setattr(gsp, "list_portfolios", lambda **_k: ["長期", "波段"])
    monkeypatch.setattr(gsp, "list_stock_watchlists", lambda **_k: ["AI 鏈"])
    monkeypatch.setattr(gsp, "list_user_sheets", lambda folder="": [{"id": _ID2, "name": "唯一一本"}])
    monkeypatch.setattr(gsp, "list_user_folders", lambda: [])


def _run(tmp_path, session):
    from streamlit.testing.v1 import AppTest
    script = tmp_path / "_me_page.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    at = AppTest.from_file(str(script), default_timeout=120)
    for k, v in session.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def _visible(at) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += [b.label for b in at.button] + [str(o) for s in at.selectbox for o in s.options]
    parts += [e.label for e in at.expander]
    return "\n".join(parts)


def test_apptest_bound_page_never_shows_full_id(tmp_path, stub_l1):
    at = _run(tmp_path, {"gsheet_tokens": dict(_TOK), "gsheet_email": "abcd@gmail.com",
                         "portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID})
    out = _visible(at)
    assert "📗「台股投組 2026」（…" + _ID[-6:] + "）" in out
    assert "ab\\*\\*\\*@gmail.com" in out or "ab***@gmail.com" in out
    assert _ID not in out and "abcd@" not in out
    at.button(key="p07me_list_sheets").click().run()
    out = _visible(at)
    assert "唯一一本（…" + _ID2[-6:] + "）" in out and _ID2 not in out
    pick = at.selectbox(key=P.SS_SHEET_PICK)
    assert pick.value is None, "⛔ 清單只有一本也不得預選"
    assert at.session_state["portfolio_sheet_id"] == _ID, "⛔ 列清單不得自動綁"
    pick.select(_ID2).run()
    at.button(key="p07me_use_drive").click().run()
    assert at.session_state["portfolio_sheet_id"] == _ID2
    assert at.session_state["stock_portfolio_sheet_id"] == _ID2
    assert _ID2 not in _visible(at)


def test_apptest_logged_out_and_not_configured(tmp_path, stub_l1, monkeypatch):
    monkeypatch.setattr(ost, "build_login_url", lambda: "https://accounts.google.com/o/oauth2/auth?x=1")
    out = _visible(_run(tmp_path, {}))
    assert P.ACC_LOGGED_OUT in out and P.SHEET_NEED_LOGIN in out and P.CONTENT_NOT_READ in out
    monkeypatch.setattr(ost, "is_oauth_configured", lambda: False)
    assert P.ACC_NOT_CONFIGURED in _visible(_run(tmp_path, {}))


def test_apptest_select_portfolio_and_logout(tmp_path, stub_l1):
    at = _run(tmp_path, {"gsheet_tokens": dict(_TOK), "portfolio_sheet_id": _ID,
                         "stock_portfolio_sheet_id": _ID})
    sb = at.selectbox(key=P.SS_PF_PICK)
    assert sb.value is None, "⛔ 不預選名稱排序第一本"
    sb.select("波段").run()
    assert PB.ActiveSelection(sheet_id=_ID, portfolio="波段").portfolio in _visible(at)
    assert at.session_state[S.ACTIVE_PORTFOLIO_SESSION_KEY]["name"] == "波段"
    at.button(key="p07me_logout").click().run()
    for k in ("gsheet_tokens", "portfolio_sheet_id", "stock_portfolio_sheet_id", S.ACTIVE_PORTFOLIO_SESSION_KEY):
        assert k not in at.session_state


# ══ PR #927 QA-2 BLOCKING：貼網址 / ID 的結果**同一輪**就地出現，展開區不收起 ════════════════════════════════════
def _switch_expander(at):
    return [e for e in at.expander if e.label == P.SWITCH_SHEET_TITLE][0]


def test_apptest_paste_error_and_success_show_in_the_same_run(tmp_path, stub_l1):
    """⛔ 326fb3b0 會紅：結果經 `_flash()` 存起來，頁首訊息區這一輪早畫完 ⇒ 錯誤 / 成功晚一輪才出現。"""
    at = _run(tmp_path, {"gsheet_tokens": dict(_TOK), "portfolio_sheet_id": _ID,
                         "stock_portfolio_sheet_id": _ID})
    at.text_input(key=S.ME_PASTE_INPUT_KEY).input(
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pubhtml").run()
    assert not at.exception, at.exception
    _errs = [e.value for e in _switch_expander(at).error]
    assert _errs, "貼了發布連結：錯誤必須在同一輪、就地出現在框下面"
    assert at.session_state["portfolio_sheet_id"] == _ID, "⛔ 錯誤輸入不得改綁定"
    at.text_input(key=S.ME_PASTE_INPUT_KEY).input(f"https://docs.google.com/spreadsheets/d/{_ID2}/edit#gid=0").run()
    _box = _switch_expander(at)
    _ok = [m.value for m in _box.success]
    assert _ok == [P.BIND_CHANGED.format(tail=S.sheet_id_tail(_ID2))], _ok
    assert not _box.error, "上一輪的錯誤不得殘留"
    assert at.session_state["portfolio_sheet_id"] == _ID2
    assert _ID2 not in _visible(at) + "".join(_ok)
    at.run()   # 再跑一輪：訊息只講一次（⛔ 不在頁首晚一輪再冒出來）
    assert not [m for m in at.success if m.value == P.BIND_CHANGED.format(tail=S.sheet_id_tail(_ID2))]


def test_switch_expander_stays_open_while_it_has_a_result():
    """有貼上結果 / Drive 清單 / Drive 失敗時展開區要開著（AppTest 讀不到 expanded 旗標 ⇒ 用原始碼對帳）。"""
    _body = _SRC.split("def _render_switch_sheet", 1)[1].split("\ndef ", 1)[0]
    assert "expanded=_open" in _body and "expanded=False" not in _body
    assert _body.index("pop_paste_result") < _body.index("st.expander("), "結果要在畫展開區之前取出"
    _code = "\n".join(ln.split("#", 1)[0] for ln in _body.splitlines())
    assert "_report_bind(" not in _code, "⛔ 貼上結果不經頁首訊息區（晚一輪）"


def test_apptest_drive_failure_is_plain_language(tmp_path, stub_l1, monkeypatch):
    """PR #927 QA-2 第 3 點：Drive 清單失敗只說分類白話，⛔ 不露例外原文 / 完整 Sheet ID。"""
    def _boom(folder=""):
        raise RuntimeError(f"HttpError 500 https://www.googleapis.com/drive/v3/files/{_ID}?x=1")
    monkeypatch.setattr(gsp, "list_user_sheets", _boom)
    at = _run(tmp_path, {"gsheet_tokens": dict(_TOK), "portfolio_sheet_id": _ID,
                         "stock_portfolio_sheet_id": _ID})
    at.button(key="p07me_list_sheets").click().run()
    out = _visible(at)
    assert "讀取雲端硬碟清單失敗" in out
    assert _ID not in out and "googleapis" not in out and "HttpError" not in out
    assert at.session_state[S.ME_DRIVE_ERROR_KEY] and "｜" not in at.session_state[S.ME_DRIVE_ERROR_KEY]


def test_content_card_403_404_point_to_sharing_not_reload():
    """PR #927 QA-2 第 2 點：403 / 404 重新讀取不會好 ⇒ 指去分享設定 / 卡②；429 / 網路才留重新讀取。"""
    assert P.RELOAD_LABEL not in P.LIST_READ_DENIED and "分享設定" in P.LIST_READ_DENIED
    assert P.RELOAD_LABEL not in P.LIST_READ_NOT_FOUND and "重新選一本" in P.LIST_READ_NOT_FOUND
    assert P.RELOAD_LABEL in P.LIST_READ_FAILED


def test_issue_text_never_echoes_raw_message():
    assert P.issue_text("error:HttpError") == P.ISSUE_TEXT_OTHER.format(kind="HttpError")
    _raw = f"HttpError('https://x/{_ID}'); OSError('boom')"
    _t = P.error_kinds(_raw)
    assert _ID not in _t and "boom" not in _t and "HttpError" in _t and "OSError" in _t


# ══ 導航 ＋ 側欄說明（app.py；DEC-083 Q1=A／D 段）═══════════════════════════════════
def _app_string_constants() -> list[str]:
    tree = ast.parse((_ROOT / "app.py").read_text(encoding="utf-8"))
    docs = set()
    for n in [tree] + [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.ClassDef))]:
        if n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            docs.add(id(n.body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def test_me_page_is_last_in_nav_and_routed():
    assert list(ia_nav.PAGE_LABELS)[-1] == ia_nav.PAGE_ME
    assert ia_nav.PAGE_LABELS[ia_nav.PAGE_ME] == "👤 我的"
    app = (_ROOT / "app.py").read_text(encoding="utf-8")
    assert "_IA_ME: _ia_view_me," in app and "from src.ui.views.page_me import render_page_me" in app


def test_app_does_not_hand_copy_me_page_label():
    """頁名 SSOT 在 L0 `ia_nav`；`app.py` 不得手抄「👤 我的」（只准 import）。"""
    assert not any(ia_nav.PAGE_LABELS[ia_nav.PAGE_ME] in c for c in _app_string_constants())


def test_app_sidebar_old_mode_strings_unchanged_new_mode_points_to_me():
    """「不使用」模式側欄三句一字不變；新版模式才換成「👤 我的」那一句。"""
    app = (_ROOT / "app.py").read_text(encoding="utf-8")
    for old in ("'貼 URL/ID 後按 Enter 設定投組資料庫（或在「📁 組合管理」頁設定）'",
                "'💡 未設定 — 貼上 URL/ID（或在「📁 組合管理」頁設定）'",
                "'登入後可在「📁 組合管理」頁雲端存取'"):
        i = app.index(old)
        assert "_SB_ME_HINT if _IA_PAGE is not None" in app[max(0, i - 160):i], old
    assert "_SB_ME_HINT = f'要選 Sheet、組合與觀察清單：到{_ia_where_to_find(_IA_SECTION_ME_SHEET)}'" in app


def test_customer_sentence_is_verbatim_in_l0():
    assert ia_nav.CONTENT_EDIT_OLD_UI_WHERE == "目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。"
    assert "'📁 組合管理'" in (_ROOT / "app.py").read_text(encoding="utf-8"), "客戶句裡的舊頁籤名須與 app.py 一致"


def test_me_service_worksheet_constants_match_l1():
    assert (ME.PORTFOLIO_WORKSHEET, ME.WATCHLIST_WORKSHEET) == (gsp._WORKSHEET_NAME, gsp._STOCK_WATCHLIST_WORKSHEET)
    assert (ME.ISSUE_WORKSHEET_MISSING, ME.ISSUE_SCHEMA_MISMATCH) == (
        gsp.READ_WORKSHEET_MISSING, gsp.READ_SCHEMA_MISMATCH)
    assert ME.read_status_codes() == (gsp.READ_OK, gsp.READ_ERROR_SHEET_NOT_FOUND, gsp.READ_ERROR_PERMISSION_DENIED,
                                      gsp.READ_ERROR_QUOTA_EXCEEDED, gsp.READ_ERROR_NETWORK)
