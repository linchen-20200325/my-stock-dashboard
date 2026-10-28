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
from shared.ia_nav4 import LEGACY_SESSION_KEY
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
    # NAV-1（DEC-097）：預設入口翻轉為新版固定四頁導覽；本測試守的是 D2 側欄 / 舊 UI 行為（＝ legacy 模式），
    # 故一律以 legacy session 旗標進入（斷言一字未動；新預設模式的對應守衛在 tests/test_nav1_*.py）。
    at.session_state[LEGACY_SESSION_KEY] = True
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


# ══ PR #927 QA-1 複驗（DEC-083 Q4）：新版模式側欄貼 ID 框**任何路徑**都不得出現完整 Sheet ID ══════════════════
B = "BBBBBOOK1234567890abcdef"
_BOX = S.SIDEBAR_SHEET_INPUT_KEY


def _box(at) -> str:
    return str(at.sidebar.text_input(key=_BOX).value or "")


def _to(at, page):
    at.sidebar.radio(key="_sb_ia_page").set_value(page)
    at.run()
    assert not at.exception, at.exception


def _assert_no_full_id(at):
    _v = _box(at)
    for _sid in (A, B):
        assert _sid not in _v, f"新版模式側欄框露出完整 Sheet ID：{_v!r}"


def test_sidebar_box_old_mode_keeps_prefill(client):
    a = _start()   # 預設「不使用」⇒ 舊模式
    assert _box(a) == A, "「不使用」模式照舊預填目前的 Sheet ID"


def test_sidebar_box_never_holds_full_id_in_new_mode(client):
    _me = ia_nav.page_label(ia_nav.PAGE_ME)
    a = _start()
    assert _box(a) == A
    # 舊 → 新：框裡沿用的舊值（完整 ID）必須被丟掉
    _to(a, _me)
    _assert_no_full_id(a)
    a.run()
    _assert_no_full_id(a)
    # 新版模式其他頁也一樣
    # D2 兩層導覽：🚦 今天在 📊 大盤 方向底下的第二層（第一層選方向、第二層選葉）。
    _to(a, ia_nav.direction_options()[list(ia_nav.NAV_TREE).index(ia_nav.DIR_MARKET)])
    a.sidebar.radio(key=f"_sb_ia_leaf_{ia_nav.DIR_MARKET}").set_value(ia_nav.leaf_options(ia_nav.DIR_MARKET)[1])
    a.run()
    assert not a.exception, a.exception
    _assert_no_full_id(a)
    _to(a, _me)
    # 貼「已是目前這本」的完整網址 ⇒ 不換代，框也不得留著它
    a.sidebar.text_input(key=_BOX).input(f"https://docs.google.com/spreadsheets/d/{A}/edit#gid=0").run()
    assert not a.exception, a.exception
    _assert_no_full_id(a)
    # 貼另一本 ⇒ 綁到 B，框不得顯示 B
    a.sidebar.text_input(key=_BOX).input(B).run()
    assert not a.exception, a.exception
    assert a.session_state["portfolio_sheet_id"] == B
    _assert_no_full_id(a)
    a.run()
    _assert_no_full_id(a)
    # 新 → 舊：舊模式照舊預填現值（B）
    _to(a, a.sidebar.radio(key="_sb_ia_page").options[0])   # app.py `_IA_NAV_OPTIONS[0]` ＝「不使用」
    assert a.sidebar.radio(key="_sb_ia_page").value == a.sidebar.radio(key="_sb_ia_page").options[0]
    assert _box(a) == B
    # 再回新版：又不得出現
    _to(a, _me)
    _assert_no_full_id(a)


def test_sidebar_box_bad_paste_stays_with_error_in_new_mode(client):
    """BLK-2 不退步：解析失敗的原文留在框裡、旁邊顯示白話錯誤，綁定不變。"""
    a = _start()
    _to(a, ia_nav.page_label(ia_nav.PAGE_ME))
    _bad = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pubhtml"
    a.sidebar.text_input(key=_BOX).input(_bad).run()
    assert not a.exception, a.exception
    assert _box(a) == _bad and a.sidebar.error
    assert a.session_state["portfolio_sheet_id"] == A


def test_sidebar_box_reset_is_pushed_to_the_browser_not_just_popped():
    """⚠️ 上面三支 AppTest 讀的是 server 端狀態 —— 33605619 的「pop ＋ value=''」在 AppTest 過、在瀏覽器**不成立**
    （PR #927 QA-2 Playwright 實測：有 key 的文字框 pop 後前端照舊顯示舊字）。瀏覽器只會在**以 Session State API
    指定值**時收到新值 ⇒ 用原始碼釘住「新版 / 切回舊版兩條路都是明確指定，⛔ 不是 pop」。
    瀏覽器實測腳本：scratchpad `pwfix/pw_box.py`（不在 CI；見 PR 描述）。"""
    src = _APP.read_text(encoding="utf-8")
    blk = src[src.index("_sb_mode_key = 'sb_portfolio_sheet_id_input'"):src.index("st.text_input(\n                'Google Sheet ID")]
    assert "st.session_state['sb_portfolio_sheet_id_input'] = ''" in blk
    assert "st.session_state['sb_portfolio_sheet_id_input'] = _sb_sid_cur" in blk
    assert "session_state.pop('sb_portfolio_sheet_id_input'" not in blk
