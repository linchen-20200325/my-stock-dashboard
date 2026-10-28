"""tests/test_nav1_default_mode_sidebar.py — NAV-1：**預設（新）模式**下，側欄既有的「新版模式」語意照舊生效（slow）。

背景：側欄「🔐 Google 帳號」區塊有一組只在「新版模式」才啟動的行為（`_IA_PAGE is not None`）——
Sheet ID 只露末 6 碼、貼 ID 框不得留完整 ID、指路句改指「👤 我的」。NAV-1 把預設翻轉成四頁導覽後，
`app.py` 在新模式令 `_IA_PAGE`＝目前 view 頁 id（非 None）以維持這組語意；
`tests/test_me_p1_logout_e2e.py` 守的是 D2（legacy）路徑，本檔補**預設路徑**的對應守衛（斷言語意同那邊）。
替身：tests/sheet_safety_rw_fakes.py（⛔ 不打真 Google）。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import tests.sheet_safety_rw_fakes as F
from shared import sheet_id as S

_APP = Path(__file__).resolve().parents[1] / "app.py"
A = "AAAABOOK1234567890abcdef"
B = "BBBBBOOK1234567890abcdef"
_BOX = S.SIDEBAR_SHEET_INPUT_KEY

pytestmark = [pytest.mark.slow, pytest.mark.usefixtures("stub_trading_day_status")]


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
    at = AppTest.from_file(str(_APP), default_timeout=300)   # ⛔ 不設 legacy 旗標 ⇒ 預設（新）模式
    at.session_state["custom_oauth_cfg"] = dict(F.OAUTH_CFG)
    at.session_state["gsheet_tokens"] = dict(F.TOKENS)
    at.session_state["gsheet_email"] = "qa@example.com"
    at.session_state["portfolio_sheet_id"] = A
    at.session_state["stock_portfolio_sheet_id"] = A
    at.session_state[S.ACTIVE_PORTFOLIO_SESSION_KEY] = {"sheet_id": A, "name": "核心", "skip": False}
    at.query_params["sheet"] = A
    at.run()
    assert not at.exception, at.exception
    return at


def _box(at) -> str:
    return str(at.sidebar.text_input(key=_BOX).value or "")


def test_default_mode_sidebar_caption_shows_tail_only(client):
    a = _start()
    _c = [c.value for c in a.sidebar.caption if "Sheet ID" in c.value]
    assert _c == [f"✅ Sheet ID：`{S.sheet_id_tail(A)}`"], _c
    assert all(A not in c.value for c in a.sidebar.caption)


def test_default_mode_sidebar_box_never_holds_full_id(client):
    a = _start()
    assert A not in _box(a)
    a.sidebar.text_input(key=_BOX).input(f"https://docs.google.com/spreadsheets/d/{A}/edit#gid=0").run()
    assert not a.exception, a.exception
    assert A not in _box(a) and B not in _box(a)
    a.sidebar.text_input(key=_BOX).input(B).run()
    assert not a.exception, a.exception
    assert a.session_state["portfolio_sheet_id"] == B
    assert A not in _box(a) and B not in _box(a)
    a.run()
    assert A not in _box(a) and B not in _box(a)


def test_default_mode_sidebar_bad_paste_stays_with_error(client):
    a = _start()
    _bad = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pubhtml"
    a.sidebar.text_input(key=_BOX).input(_bad).run()
    assert not a.exception, a.exception
    assert _box(a) == _bad and a.sidebar.error
    assert a.session_state["portfolio_sheet_id"] == A


def test_default_mode_sidebar_has_no_old_tab_pointer_when_logged_in(client):
    a = _start()
    _hints = [c.value for c in a.sidebar.caption]
    assert not any("組合管理" in h for h in _hints), "預設模式側欄不得指向舊『📁 組合管理』頁籤"


def test_default_mode_logged_out_hint_points_to_the_me_page(client):
    from shared import ia_nav
    at = AppTest.from_file(str(_APP), default_timeout=300)
    at.session_state["custom_oauth_cfg"] = dict(F.OAUTH_CFG)
    at.run()
    assert not at.exception, at.exception
    _caps = " ".join(c.value for c in at.sidebar.caption)
    assert ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET) in _caps
    assert "組合管理" not in _caps
