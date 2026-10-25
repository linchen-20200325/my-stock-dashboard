"""👤 我的 P1（DEC-083 D 段）—— 新版頁面的 dead-end 指路、Q7 選定在 💼／🔍 的落點、導航掛載。

客戶原文（D 段）：「Sheet／登入／切換相關提示：→ 統一導向『👤 我的』。需要修改持股／組合／觀察清單內容：P1 尚未提供 CRUD，
因此必須誠實指路：『目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。』不得再出現：新版模式看不到的頁面
卻叫使用者直接去點、指回自己的唯讀頁、寫著有控制項但實際沒有。」
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared import ia_nav
from src.services import holdings_service as HS
from src.ui.views import page_find as F
from src.ui.views import page_hold as H
from src.ui.views import page_today as T

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_CUSTOMER = "目前請切回舊版 → 📁 組合管理；新版 CRUD 會在下一階段處理。"
_FILES = {"page_hold": _ROOT / "src/ui/views/page_hold.py", "page_today": _ROOT / "src/ui/views/page_today.py",
          "page_find": _ROOT / "src/ui/views/page_find.py"}


def _docstring_ids(tree) -> set[int]:
    out = set()
    for n in [tree] + [x for x in ast.walk(tree)
                       if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]:
        if n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            out.add(id(n.body[0].value))
    return out


def _string_constants(path: pathlib.Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = _docstring_ids(tree)
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def test_old_tab_name_in_customer_sentence_exists_in_app():
    """客戶句裡的舊頁籤名必須與 `app.py` 的舊頁籤字面一致（舊頁籤改名 ⇒ 本條轉紅）。"""
    app = (_ROOT / "app.py").read_text(encoding="utf-8")
    assert "'📁 組合管理'" in app and "📁 組合管理" in _CUSTOMER


@pytest.mark.parametrize("name", sorted(_FILES))
def test_no_hidden_tab_or_sidebar_pointer_left(name):
    """新版頁面不得再叫人「到既有的 📁 組合管理分頁」或「側欄『🔐 Google 帳號』」（新版模式看不到 / 不是唯一入口）。"""
    bad = [(ln, v) for ln, v in _string_constants(_FILES[name])
           if "到既有的 📁 組合管理分頁" in v or "側欄「🔐 Google 帳號」" in v
           or "現行入口仍在既有的 📁 組合管理" in v or "到 📁 組合管理" in v]
    assert not bad, bad


def _module_where_constants(mod):
    return {k: v for k, v in vars(mod).items() if k.isupper() and k.endswith("_WHERE") and isinstance(v, str)}


@pytest.mark.parametrize("mod", [H, T, F])
def test_every_where_mentioning_old_tab_carries_full_customer_sentence(mod):
    for k, v in _module_where_constants(mod).items():
        if "📁 組合管理" in v:
            assert _CUSTOMER in v, (mod.__name__, k, v)


def test_inline_hold_wheres_use_edit_helper():
    """page_hold 每一個會出現「📁 組合管理」的非 docstring 字串，只准是客戶句的摘錄（短句表）或註解外的 L0 常數。"""
    for ln, v in _string_constants(_FILES["page_hold"]):
        if "📁 組合管理" in v:
            assert v in ("目前請切回舊版 → 📁 組合管理",), (ln, v)


def test_cash_watchlist_only_no_longer_points_to_own_readonly_leaf():
    assert "💼 我的持股 › 組合設定" not in H.CASH_WATCHLIST_ONLY_WHERE
    # PR #927 QA-2 第 6 點：~~`_CUSTOMER + "在你的持股表…。"`~~ → 動作在前、客戶句在後（客戶句一字不改）。
    assert H.CASH_WATCHLIST_ONLY_WHERE == "在你的持股表新增至少一列持股（要有代號、張數、均價）：" + _CUSTOMER


def test_watchlist_manage_entry_is_action_first():
    """PR #927 QA-2 第 6 點：觀察清單管理的「現行入口」也是動作在前、客戶句在後。"""
    _spec = [u for u in H.SETUP_UNWIRED_SPECS if u.key == "hold.setup.watchlist"][0]
    assert dict(_spec.facts)["現行入口"] == "要管理觀察清單（含選股網的「加入觀察清單」）：" + _CUSTOMER


def test_sheet_pointers_go_to_me_page():
    me_sheet = ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET)
    for where in (T.SHEET_UNBOUND_WHERE, H.NOT_BOUND_WHERE, H.PICK_SHEET_WHERE):
        assert me_sheet in where, where
    assert ia_nav.where_to_find(ia_nav.SECTION_ME_ACCOUNT) in H.LOGIN_EXPIRED_WHERE
    assert H.NOT_BOUND_WHERE.startswith(T.SHEET_UNBOUND_WHERE)


def test_page_today_does_not_hand_copy_ia_names():
    """「🚦 今天」不得手抄頁名／分區名／按鈕名（一律 `ia_nav`）。"""
    hand = [ia_nav.PAGE_LABELS[ia_nav.PAGE_ME], ia_nav.ACTION_LABELS[ia_nav.ACTION_ME_USE_SHEET],
            ia_nav.SECTION_LABELS[ia_nav.SECTION_ME_SHEET]]
    bad = [(ln, v) for ln, v in _string_constants(_FILES["page_today"]) if any(h in v for h in hand)]
    assert not bad, bad


# ══ 💼 我的持股：沒選定 ⇒ 灰卡、⛔ 不分析 ══════════════════════════════════════
_REQ = H.HoldRequest(submitted=True, mode=H.SCOPE_WITH_BINDING)


def _holdings(monkeypatch, **kw):
    base = dict(holdings=(HS._row("2454", held=False),), bound=True, logged_in=True)
    base.update(kw)
    monkeypatch.setattr(HS, "get_holdings", lambda **_k: HS.HoldingsResult(**base))
    return H.load_holdings(_REQ)


@pytest.mark.parametrize("sel, now", [(HS.SELECTION_NOT_SELECTED, H.NOT_SELECTED_NOW),
                                      (HS.SELECTION_MISSING, H.SELECTION_MISSING_NOW)])
def test_not_selected_is_grey_and_not_analysed(monkeypatch, sel, now):
    h = _holdings(monkeypatch, portfolio_selection=sel)
    assert h.holdings == (), "沒選定組合 ⇒ 觀察清單列也不進戰情室"
    card = H.build_holdings_preview_card(h)[0]
    assert card.note.now == now and ia_nav.where_to_find(ia_nav.SECTION_ME_CONTENT) in card.note.where
    st = H.load_station(h)
    assert H._station_note(st, now=H.ACTION_FAILED_NOW, source=H.SRC_STATION).now == now
    for c in (card,):
        H.v2_short_rows(c)    # 短句表有登記（查不到 ⇒ KeyError）


def test_selected_portfolio_is_analysed_normally(monkeypatch):
    h = _holdings(monkeypatch, portfolio_selection=HS.SELECTION_OK, portfolio_name="長期",
                  holdings=(HS._row("0056", held=True, lots=1.0, avg_price=30.0),))
    assert h.held_tickers == ("0056",)
    facts = dict(H.build_holdings_preview_card(h)[1])
    assert facts["讀到的投資組合"] == "長期"


def test_more_portfolios_fact_no_longer_says_first(monkeypatch):
    h = _holdings(monkeypatch, portfolio_selection=HS.SELECTION_OK, portfolio_name="長期", more_portfolios=True,
                  holdings=(HS._row("0056", held=True, lots=1.0, avg_price=30.0),))
    v = dict(H.build_holdings_preview_card(h)[1])["⚠️ 這本 Sheet 裡還有別的沒讀"]
    assert "第一本" not in v and "選定的那一本" in v


def test_hold_binding_card_reads_ssot():
    src = _FILES["page_hold"].read_text(encoding="utf-8")
    assert "_s = get_binding_state(ssot=True)" in src


# ══ 🔍 找標的：持股標示來源 ═══════════════════════════════════════════════════
@pytest.mark.parametrize("src, needle", [
    ({}, "未提供"),
    ({"bound": False}, F.HOLDING_SOURCE_NO_SHEET),
    ({"bound": True}, F.HOLDING_SOURCE_NOT_SELECTED),
    ({"bound": True, "portfolio_name": "長期", "watchlist_name": "AI 鏈"}, "組合「長期」＋觀察清單「AI 鏈」"),
    ({"bound": True, "error": "ConnectionError('x')"}, F.HOLDING_SOURCE_FAILED),
    # PR #927 QA-2 第 3／4 點：照實分辨原因
    ({"bound": False, "active_state": "diverged", "logged_in": True}, F.HOLDING_SOURCE_DIVERGED),
    ({"bound": False, "logged_in": False}, F.HOLDING_SOURCE_NOT_LOGGED_IN),
    ({"bound": False, "logged_in": False, "login_expired": True}, F.HOLDING_SOURCE_LOGIN_EXPIRED),
    ({"bound": True, "error": "LoginRequiredError()", "error_issue": "login_required"},
     F.HOLDING_SOURCE_LOGIN_EXPIRED),
    ({"bound": True, "error": "x", "error_issue": "permission_denied"}, F.HOLDING_ISSUE_DENIED),
    ({"bound": True, "error": "x", "error_issue": "network"}, F.HOLDING_ISSUE_NETWORK),
    ({"bound": True, "portfolio_selection": "selection_missing"}, F.HOLDING_SOURCE_PF_MISSING),
    ({"bound": True, "portfolio_issue": "worksheet_missing"}, F.HOLDING_SOURCE_PF_NO_TAB),
    ({"bound": True, "portfolio_name": "長期", "watchlist_selection": "selection_missing"},
     "組合「長期」＋" + F.HOLDING_SOURCE_WL_MISSING)])
def test_find_holding_source_fact(src, needle):
    flow = F.SectorFlowReadout(requested=True, ok=True, sectors=({"sector": "半導體"},), holding_source=src)
    facts = dict(F.build_sector_flow_card(flow)[1])
    assert needle in facts["持股標示來源"]
    assert "計算組合" not in facts["你的持股板塊"]


def test_find_calls_l3_with_active_selection(monkeypatch):
    seen = {}

    def _fake(**kw):
        seen.update(kw)
        return {"ok": True, "sectors": [], "holding_source": {"bound": True}}
    monkeypatch.setattr("src.services.sector_flow_service.get_sector_flow_view", _fake)
    r = F.load_sector_flow({"etf_portfolio_rows": [{"ticker": "0050"}], "stock_portfolio_sheet_id": "X"},
                           requested=True)
    assert seen == {"strict": True, "use_active_selection": True}
    assert r.holding_source == {"bound": True}


def test_find_holding_source_failure_never_echoes_raw_error():
    """PR #927 QA-2 第 3 點：⛔ 例外原文（可能含完整 Sheet ID）不上畫面，只講分類白話。"""
    _sid = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdEF"
    src = {"bound": True, "error": f"APIError('https://sheets.googleapis.com/v4/spreadsheets/{_sid}')",
           "error_issue": "error:APIError"}
    flow = F.SectorFlowReadout(requested=True, ok=True, sectors=({"sector": "半導體"},), holding_source=src)
    _t = dict(F.build_sector_flow_card(flow)[1])["持股標示來源"]
    assert _sid not in _t and "googleapis" not in _t and "APIError" in _t


# ══ PR #927 QA-2 第 4 點：🚦 狀態列 —— 兩本不同 ≠ 尚未綁定 ═══════════════════════════════════
def test_today_sheet_card_diverged_is_not_called_unbound():
    from shared.sheet_id import ACTIVE_DIVERGED
    from src.services.portfolio_binding_service import BindingPresence
    from src.ui.views import page_today as T
    _b = BindingPresence(logged_in=True, sheet_bound=False, read_error="", active_state=ACTIVE_DIVERGED)
    card = T.build_sheet_binding_card(_b)
    assert card.note.now == T.SHEET_DIVERGED_NOW and card.note.where == T.SHEET_DIVERGED_WHERE
    assert "有效的結果" not in card.note.why and T.SHEET_UNBOUND_NOW not in card.note.now
    assert ia_nav.where_to_find(ia_nav.SECTION_ME_SHEET) in card.note.where
    assert any(w is T.SHEET_DIVERGED_WHERE and p in w for w, p in T.V2_EXIT_PHRASES)
    _plain = BindingPresence(logged_in=True, sheet_bound=False, read_error="", active_state="none")
    assert T.build_sheet_binding_card(_plain).note.where == T.SHEET_UNBOUND_WHERE


# ══ PR #927 QA-2 第 4 點：💼 兩本不同 ≠「你還沒有綁定 / 新使用者灰色正常」══════════════════════════════
def test_hold_diverged_cards_say_two_sheets(monkeypatch):
    from shared.sheet_id import ACTIVE_DIVERGED
    from src.services import portfolio_binding_service as PB
    h = _holdings(monkeypatch, holdings=(), bound=False, active_state=ACTIVE_DIVERGED)
    assert h.diverged
    _bs = PB.BindingState(logged_in=True, sheet_id="", status=PB.STATUS_UNBOUND, portfolio_count=None,
                          active_state=ACTIVE_DIVERGED)
    monkeypatch.setattr(PB, "get_binding_state", lambda **_k: _bs)
    b = H.load_binding(_REQ)
    assert b.diverged
    st = H.load_station(h)
    dq = H.load_deep(st)
    for card in (H.build_binding_card(b)[0], H.build_holdings_preview_card(h)[0], H.build_action_card(st)[0],
                 H.build_stress_card(dq)[0]):
        assert card.note.now == H.DIVERGED_NOW, (card.key, card.note.now)
        assert "有效的結果" not in card.note.why and "新使用者" not in card.note.why
        assert card.note.where == T.SHEET_DIVERGED_WHERE
        H.v2_short_rows(card)
    _cnt = H.build_portfolio_count_card(b)[0]
    assert "還沒有綁定" not in _cnt.note.why and _cnt.note.where == H.COUNT_DIVERGED_WHERE
    H.v2_short_rows(_cnt)
    # 不是兩本不同 ⇒ 照舊
    h2 = _holdings(monkeypatch, holdings=(), bound=False, active_state="none")
    assert H.build_holdings_preview_card(h2)[0].note.now == H.NOT_BOUND_NOW


# ══ PR #927 QA-2 複驗：🔍 持股來源 —— 組合 × 觀察清單**每一種組合**兩半都要講到（⛔ 不丟掉其中一半）══════════
import itertools as _it

_PF_STATES = {
    "name": ({"portfolio_name": "長期", "portfolio_selection": HS.SELECTION_OK}, "組合「長期」", ""),
    "missing": ({"portfolio_selection": HS.SELECTION_MISSING}, F.HOLDING_SOURCE_PF_MISSING, "gone"),
    "no_tab": ({"portfolio_issue": "worksheet_missing"}, F.HOLDING_SOURCE_PF_NO_TAB, ""),
    "empty": ({"portfolio_names_n": 0}, F.HOLDING_SOURCE_PF_EMPTY, ""),
    "not_selected": ({"portfolio_selection": HS.SELECTION_NOT_SELECTED, "portfolio_names_n": 2},
                     F.HOLDING_SOURCE_PF_NOT_SELECTED, "pick"),
}
_WL_STATES = {
    "name": ({"watchlist_name": "AI 鏈", "watchlist_selection": HS.SELECTION_OK}, "觀察清單「AI 鏈」", ""),
    "missing": ({"watchlist_selection": HS.SELECTION_MISSING}, F.HOLDING_SOURCE_WL_MISSING, "gone"),
    "no_tab": ({"watchlist_issue": "worksheet_missing"}, F.HOLDING_SOURCE_WL_NO_TAB, ""),
    "skipped": ({"watchlist_selection": HS.SELECTION_SKIPPED}, F.HOLDING_SOURCE_WL_SKIPPED, ""),
    "not_selected": ({"watchlist_selection": HS.SELECTION_NOT_SELECTED}, F.HOLDING_SOURCE_WL_NOT_SELECTED, "pick"),
}


@pytest.mark.parametrize("pf, wl", list(_it.product(_PF_STATES, _WL_STATES)))
def test_find_holding_source_every_combination_mentions_both_halves(pf, wl):
    _pv, _pt, _pk = _PF_STATES[pf]
    _wv, _wt, _wk = _WL_STATES[wl]
    src = {"bound": True, "logged_in": True, **_pv, **_wv}
    out = F._holding_source_text(src)
    if {_pk, _wk} == {"pick"}:
        assert out == F.HOLDING_SOURCE_NOT_SELECTED   # 兩半都還沒選 ⇒ 原本那一句
        return
    assert _pt in out and _wt in out, out
    assert out.index(_pt) < out.index(_wt), "組合在前、觀察清單在後"
    _content = ia_nav.where_to_find(ia_nav.SECTION_ME_CONTENT)
    if "gone" in (_pk, _wk):
        assert out.endswith(F.HOLDING_SOURCE_RECHECK)
    elif "pick" in (_pk, _wk):
        assert out.endswith(F.HOLDING_SOURCE_PICK) and _content in out
    else:
        assert _content not in out, "沒有要選的東西就不叫人去選"


def test_find_holding_source_reported_case_pf_not_selected_wl_no_tab():
    """QA-2 複驗回報的那一種：組合沒選 ＋ 觀察清單沒有分頁 ⇒ ~~只講觀察清單~~，組合那半也要講並指路。"""
    out = F._holding_source_text({"bound": True, "portfolio_selection": HS.SELECTION_NOT_SELECTED,
                                  "watchlist_issue": "worksheet_missing"})
    assert out == (F.HOLDING_SOURCE_PF_NOT_SELECTED + "＋" + F.HOLDING_SOURCE_WL_NO_TAB + F.HOLDING_SOURCE_PICK)
    assert ia_nav.where_to_find(ia_nav.SECTION_ME_CONTENT) in out
