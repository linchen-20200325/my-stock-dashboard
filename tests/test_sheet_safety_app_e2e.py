"""Sheet Safety 批 QA 回修 —— 整支 app.py 跑 AppTest（slow lane）：側欄貼 ID、Drive ✅、登出。

QA（PR #926，2026-10-25）兩組獨立重現：
- BLK-2：已綁 A（側欄文字框顯示 A）→ 在 📁 組合管理用 Drive 選 B 按 ✅ → 下一輪側欄文字框的舊值 A
  經寫入契約把綁定改回 A（之後存檔寫進 A）。
- B-1：Drive ✅ 選的那本 ＝ secrets 預設 → 契約什麼都沒寫（個股通道空、無 ?sheet=）卻顯示成功。
替身：tests/sheet_safety_rw_fakes.py（可讀寫、記錄每次呼叫，⛔ 不打真 Google）。
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from streamlit.testing.v1 import AppTest

import tests.sheet_safety_rw_fakes as F

_APP = Path(__file__).resolve().parents[1] / "app.py"
A = "AAAABOOK1234567890abcdef"
B = "BBBBBOOK0987654321zyxwvu"
SB_KEY = "sb_portfolio_sheet_id_input"

pytestmark = [pytest.mark.slow, pytest.mark.usefixtures("stub_trading_day_status")]


@pytest.fixture()
def client(monkeypatch):
    from src.data.portfolio import gsheet_portfolio as gsp
    c = F.FakeClient()
    c.books[A] = {"portfolios": [["name", "ticker", "lots", "avg_price", "updated_at"],
                                 ["核心", "0050", "1", "100", "t"]]}
    c.books[B] = {}
    monkeypatch.setattr(gsp, "_build_client", lambda: c)
    monkeypatch.setattr(gsp, "list_user_folders", lambda: [])
    monkeypatch.setattr(gsp, "list_user_sheets",
                        lambda folder_id="": [{"id": A, "name": "甲本"}, {"id": B, "name": "乙本"}])
    gsp.clear_read_cache()
    yield c
    gsp.clear_read_cache()


def _app(*, logged=False, sid=None, qp=None, secrets=None):
    at = AppTest.from_file(str(_APP), default_timeout=300)
    at.session_state["custom_oauth_cfg"] = dict(F.OAUTH_CFG)
    for k, v in (secrets or {}).items():
        at.secrets[k] = v
    if logged:
        at.session_state["gsheet_tokens"] = dict(F.TOKENS)
        at.session_state["gsheet_email"] = "qa@example.com"
    if sid:
        at.session_state["portfolio_sheet_id"] = sid
        at.session_state["stock_portfolio_sheet_id"] = sid
    for k, v in (qp or {}).items():
        at.query_params[k] = v
    return at


def _qp(at, k):
    v = at.query_params.get(k)
    return (v[0] if v else None) if isinstance(v, list) else v


def _sidebar_errors(at):
    """側欄紅字,排除「🔌 連線狀態」那幾顆燈(`FinMind ❌` 之類,測試環境本來就沒有金鑰)。"""
    return [e.value for e in at.sidebar.error if not e.value.endswith("❌")]


def _bound(at):
    return (at.session_state["portfolio_sheet_id"] if "portfolio_sheet_id" in at.session_state else None,
            at.session_state["stock_portfolio_sheet_id"]
            if "stock_portfolio_sheet_id" in at.session_state else None)


def _drive_use(at, label):
    at.button(key="_mgmt_drive_list").click()
    at.run()
    assert not at.exception, at.exception
    at.selectbox(key="_mgmt_drive_pick").select(label)
    at.button(key="_mgmt_drive_use").click()
    at.run()
    assert not at.exception, at.exception


def test_drive_pick_b_is_not_reverted_by_sidebar_widget(client):
    """BLK-2：Drive 選 B 之後連跑兩輪，仍是 B（側欄文字框改顯示 B）。"""
    at = _app(logged=True, sid=A)
    at.run()
    assert not at.exception, at.exception
    assert at.sidebar.text_input(key=SB_KEY).value == A
    _drive_use(at, f"乙本（{B[:12]}…）")
    at.run()
    at.run()
    assert not at.exception, at.exception
    assert _bound(at) == (B, B)
    assert _qp(at, "sheet") == B
    assert at.sidebar.text_input(key=SB_KEY).value == B


def test_drive_use_on_secrets_default_really_binds_both_channels(client):
    """B-1：選的那本 ＝ secrets 預設 → 兩格 session ＋ ?sheet= 都寫上（修前什麼都沒寫卻顯示成功）。"""
    at = _app(logged=True, secrets={"portfolio_sheet_id": A})
    at.run()
    assert not at.exception, at.exception
    _drive_use(at, f"甲本（{A[:12]}…）")
    assert _bound(at) == (A, A)
    assert _qp(at, "sheet") == A


def test_sidebar_paste_binds_only_after_user_changes_text(client):
    at = _app(logged=True, sid=A)
    at.run()
    at.run()
    assert _bound(at) == (A, A) and _qp(at, "sheet") is None, "沒動文字框 ⇒ 不得寫任何東西"
    at.sidebar.text_input(key=SB_KEY).input(f"https://docs.google.com/spreadsheets/d/{B}/edit#gid=0")
    at.run()
    assert not at.exception, at.exception
    assert _bound(at) == (B, B) and _qp(at, "sheet") == B
    assert _sidebar_errors(at) == []
    at.run()
    assert at.sidebar.text_input(key=SB_KEY).value == B, "框改顯示解析後的 ID"


@pytest.mark.parametrize("raw", [
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQabcDEF_ghi/pubhtml",
    "garbage with spaces !!",
])
def test_sidebar_paste_bad_input_binds_nothing(client, raw):
    at = _app(logged=True, sid=A)
    at.run()
    at.sidebar.text_input(key=SB_KEY).input(raw)
    at.run()
    assert not at.exception, at.exception
    assert _bound(at) == (A, A)
    errs = _sidebar_errors(at)
    assert len(errs) == 1 and raw not in errs[0], errs


def _login_state(at):
    for el in at.sidebar.get("link_button"):
        url = el.proto.url
        if "state=" in url:
            return parse_qs(urlparse(url).query).get("state", [""])[0]
    return None


def test_logout_clears_binding_and_does_not_rebind(client):
    at = _app(logged=True, sid=A, qp={"sheet": A})
    at.run()
    assert not at.exception, at.exception
    at.sidebar.button(key="btn_oauth_logout_sb").click()
    at.run()
    assert not at.exception, at.exception
    assert _bound(at) == (None, None)
    assert _qp(at, "sheet") is None and _qp(at, "gs") is None
    st_ = _login_state(at)
    assert st_ is not None and A not in st_, st_
    at.session_state["gsheet_tokens"] = dict(F.TOKENS)   # 同一 session 重新登入
    at.run()
    assert not at.exception, at.exception
    assert at.sidebar.text_input(key=SB_KEY).value in ("", None)
    assert _bound(at) == (None, None)
