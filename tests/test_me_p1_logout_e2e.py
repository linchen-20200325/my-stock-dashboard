"""👤 我的 P1（DEC-083 Q5）—— 整支 app.py 跑 AppTest（slow lane）：側欄「🚪 登出」與「👤 我的」頁「🚪 登出」結束狀態相同。

客戶原文 Q5：「登出時同步清除：Google 登入 session、active Sheet binding、URL 上 "sheet" 參數、OAuth state／登入流程
攜帶的舊 Sheet ID、會造成登出後重新自動綁回舊 Sheet 的 silent marker。不得登出後自動恢復上一個 Sheet。」
兩顆鈕呼叫同一支 L1 `oauth_state.logout_google_session`；本檔以真的 app.py 驗「畫面上按下去」的結果一致。
替身：tests/sheet_safety_rw_fakes.py（⛔ 不打真 Google）。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import tests.sheet_safety_rw_fakes as F
from shared import ia_nav
from shared import sheet_id as S

_APP = Path(__file__).resolve().parents[1] / "app.py"
A = "AAAABOOK1234567890abcdef"

pytestmark = [pytest.mark.slow, pytest.mark.usefixtures("stub_trading_day_status")]

#: 比對的 session key（登入、綁定、選定、側欄框、「👤 我的」頁的 Drive 清單）。
_KEYS = ("gsheet_tokens", "gsheet_email", "portfolio_sheet_id", "stock_portfolio_sheet_id",
         S.ACTIVE_PORTFOLIO_SESSION_KEY, S.ACTIVE_WATCHLIST_SESSION_KEY, S.SIDEBAR_SHEET_INPUT_KEY,
         # PR #927 QA-2 第 5 點：👤 我的頁的 key **逐一點名**（⛔ 不只靠 `*LOGOUT_EXTRA_SESSION_KEYS` —— 清單漏列時
         #   比對範圍會跟著縮小，測不到漏清）。
         S.ME_DRIVE_FOLDERS_SESSION_KEY, S.ME_DRIVE_SHEETS_SESSION_KEY, S.ME_PASTE_INPUT_KEY,
         S.ME_FOLDER_PICK_KEY, S.ME_SHEET_PICK_KEY, S.ME_PORTFOLIO_PICK_KEY, S.ME_WATCHLIST_PICK_KEY,
         S.ME_DRIVE_ERROR_KEY,
         *S.LOGOUT_EXTRA_SESSION_KEYS)


@pytest.fixture()
def client(monkeypatch):
    from src.data.portfolio import gsheet_portfolio as gsp
    c = F.FakeClient()
    c.books[A] = {"portfolios": [["name", "ticker", "lots", "avg_price", "updated_at"],
                                 ["核心", "0050", "1", "100", "t"]]}
    monkeypatch.setattr(gsp, "_build_client", lambda: c)
    monkeypatch.setattr(gsp, "list_user_folders", lambda: [])
    monkeypatch.setattr(gsp, "list_user_sheets", lambda folder_id="": [{"id": A, "name": "甲本"}])
    gsp.clear_read_cache()
    yield c
    gsp.clear_read_cache()


def _start() -> AppTest:
    at = AppTest.from_file(str(_APP), default_timeout=300)
    at.session_state["custom_oauth_cfg"] = dict(F.OAUTH_CFG)
    at.session_state["gsheet_tokens"] = dict(F.TOKENS)
    at.session_state["gsheet_email"] = "qa@example.com"
    at.session_state["portfolio_sheet_id"] = A
    at.session_state["stock_portfolio_sheet_id"] = A
    at.session_state[S.ACTIVE_PORTFOLIO_SESSION_KEY] = {"sheet_id": A, "name": "核心", "skip": False}
    # PR #927 QA-2 第 5 點：👤 我的頁殘留（Drive 清單 / 選擇器 / Drive 失敗代碼）也預先放進去 ⇒ 兩條登出都必須清掉，
    #   比對才有意義（~~原本只放綁定 key ⇒ 這幾個 key 兩邊都是 None，比對恆等、測不到側欄登出漏清~~）。
    at.session_state[S.ME_DRIVE_FOLDERS_SESSION_KEY] = [{"id": "fold1", "name": "投資"}]
    at.session_state[S.ME_DRIVE_SHEETS_SESSION_KEY] = [{"id": A, "name": "核心表"}]
    at.session_state[S.ME_DRIVE_ERROR_KEY] = "error:RuntimeError"
    at.session_state[S.ME_FOLDER_PICK_KEY] = "fold1"
    at.session_state[S.ME_SHEET_PICK_KEY] = A
    at.query_params["sheet"] = A
    at.run()
    assert not at.exception, at.exception
    return at


def _end(at) -> tuple:
    """`_oauth_state`（本 session 的 CSRF nonce）登出後畫登入鈕時會**重新產生一個隨機值** ⇒ 只比「有沒有」。"""
    _qp = {k: at.query_params.get(k) for k in ("sheet", "gs")}
    _v = tuple((k, at.session_state[k] if k in at.session_state else None) for k in _KEYS if k != "_oauth_state")
    return _v, _qp, "_oauth_state" in at.session_state


def test_sidebar_and_page_logout_end_in_the_same_state(client):
    a = _start()
    a.sidebar.button(key="btn_oauth_logout_sb").click()
    a.run()
    assert not a.exception, a.exception

    b = _start()
    b.sidebar.radio(key="_sb_ia_page").set_value(ia_nav.page_label(ia_nav.PAGE_ME))
    b.run()
    assert not b.exception, b.exception
    b.button(key="p07me_logout").click()
    b.run()
    assert not b.exception, b.exception

    sa, sb = _end(a), _end(b)
    assert sa == sb
    assert all(v is None for _k, v in sa[0]), sa[0]
    assert sa[1] == {"sheet": None, "gs": None}
    assert sa[2] is True, "登出後兩邊都畫出登入鈕（新的 nonce）"


def test_page_logout_does_not_rebind_on_next_run(client):
    b = _start()
    b.sidebar.radio(key="_sb_ia_page").set_value(ia_nav.page_label(ia_nav.PAGE_ME))
    b.run()
    b.button(key="p07me_logout").click()
    b.run()
    b.session_state["gsheet_tokens"] = dict(F.TOKENS)   # 同一 session 重新登入
    b.run()
    assert not b.exception, b.exception
    assert "portfolio_sheet_id" not in b.session_state and "stock_portfolio_sheet_id" not in b.session_state


def test_sidebar_sheet_caption_shows_tail_only_in_new_mode(client):
    """PR #927 QA-2 第 7 點：側欄「✅ Sheet ID」新版模式只露末 6 碼；「不使用」模式照舊（完整 ID）。
    ⚠️ 側欄貼 ID 框的預填值仍是完整 ID（舊行為，本批未動，列為殘留）⇒ 本測試只看 caption。"""
    a = _start()
    _old = [c.value for c in a.sidebar.caption if "Sheet ID" in c.value]
    assert _old == [f"✅ Sheet ID：`{A}`"], _old
    a.sidebar.radio(key="_sb_ia_page").set_value(ia_nav.page_label(ia_nav.PAGE_ME))
    a.run()
    assert not a.exception, a.exception
    _new = [c.value for c in a.sidebar.caption if "Sheet ID" in c.value]
    assert _new == [f"✅ Sheet ID：`{S.sheet_id_tail(A)}`"], _new
    assert all(A not in c.value for c in a.sidebar.caption)
