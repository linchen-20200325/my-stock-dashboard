"""Sheet Safety 批 QA 回修（PR #926 兩組獨立 QA，2026-10-25）。

B-1：明確選定（Drive「✅ 使用此 Sheet」）時，契約⛔ 不得因「與 ETF 通道 / secrets 預設相同」就什麼都不寫
     卻顯示成功；只有兩格 session **與** `?sheet=` 都已是那本才算 no-op。
BLK-2：被動文字框（側欄貼 ID、就地綁定的貼網址框）每輪 rerun 都拿**舊的 widget 值**呼叫契約 ⇒
     使用者剛用 Drive 選了 B，下一輪又被默默綁回 A。改為「使用者真的改了文字」才呼叫，
     且綁定一變，文字框重新顯示現值。
N-5：舊書籤 `?sheet=e`（修前發布連結 bug 的產物）不得被還原 / 解析成 Sheet ID。
"""
from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

import src.data.portfolio.oauth_state as ost
from shared import sheet_id as S

_ID = "1AbC_dEf-GhIjKlMnOpQrStUvWxYz0123456789abcd"


class _St:
    def __init__(self, session=None, query=None, secrets=None):
        self.session_state = dict(session or {})
        self.query_params = dict(query or {})
        self.secrets = dict(secrets or {})


def _bind(f):
    """兩格綁定 key(session 另有契約的「綁定世代」計數器,不在比對範圍)。"""
    return {k: v for k, v in f.session_state.items() if k in S.SHEET_BINDING_SESSION_KEYS}


@pytest.fixture
def fst(monkeypatch):
    monkeypatch.setattr(ost, "sync_silent_marker", lambda: False)

    def _make(**kw):
        f = _St(**kw)
        monkeypatch.setattr(ost, "st", f)
        return f
    return _make


# ── B-1 ──────────────────────────────────────────────────────────────────
def test_explicit_pick_equal_to_secrets_default_really_binds(fst):
    f = fst(secrets={"portfolio_sheet_id": _ID})
    r = ost.apply_sheet_binding(_ID)
    assert r.changed and not r.error
    assert _bind(f) == {"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID}
    assert f.query_params == {"sheet": _ID}


def test_explicit_pick_fixes_inconsistent_legacy_channels(fst):
    """Q6：兩通道不一致時，使用者在畫面上明確重選 ETF 那本 → 兩格都改成它（修得好）。"""
    f = fst(session={"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": "OTHERSHEET1"},
            query={"sheet": _ID})
    r = ost.apply_sheet_binding(_ID)
    assert r.changed
    assert _bind(f) == {"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID}


def test_explicit_pick_writes_missing_query_param(fst):
    f = fst(session={"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID})
    assert ost.apply_sheet_binding(_ID).changed
    assert f.query_params == {"sheet": _ID}


def test_noop_only_when_both_keys_and_query_already_equal(fst):
    f = fst(session={"portfolio_sheet_id": _ID, "stock_portfolio_sheet_id": _ID},
            query={"sheet": _ID})
    r = ost.apply_sheet_binding(_ID)
    assert (r.sheet_id, r.changed, r.error) == (_ID, False, "")
    assert r.already_current


# ── N-5 ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw", ["e", " e "])
def test_legacy_publish_link_artefact_e_is_rejected(raw):
    assert S.sanitize_sheet_id(raw) == ""
    assert S.parse_sheet_input(raw).error == S.SHEET_INPUT_INVALID


def test_bookmark_sheet_e_is_not_restored(fst):
    f = fst(query={"sheet": "e"})
    assert ost.restore_sheet_binding_from_query() == ""
    assert f.session_state == {}


def test_real_ids_starting_with_e_still_ok():
    assert S.sanitize_sheet_id("eAbc123_-x") == "eAbc123_-x"
    assert S.parse_sheet_input("https://docs.google.com/spreadsheets/d/eAbc123_-x/edit").sheet_id \
        == "eAbc123_-x"


# ── BLK-2（實跑 AppTest：真的 portfolio_binder，Drive 選 B 之後不得被貼網址框綁回 A）──────────
def _binder_app():
    import streamlit as st

    from src.ui.tabs import portfolio_binder as pb

    # ⚠️ 不 monkeypatch 任何模組(AppTest 與 pytest 同一個 process,改了會漏到別的測試);
    #    本 session 沒有強驗登入旗標 ⇒ 真的 `sync_silent_marker()` 第一行就回 False,不需替身。
    class _Gsp:
        @staticmethod
        def _has_oauth_tokens():
            return True

        @staticmethod
        def _get_active_sheet_id():
            return str(st.session_state.get("portfolio_sheet_id", "") or "")

        @staticmethod
        def list_user_folders():
            return []

        @staticmethod
        def list_user_sheets(_fid=""):
            return [{"id": "AAAAAAAAAA11", "name": "甲本"}, {"id": "BBBBBBBBBB22", "name": "乙本"}]

    st.session_state.setdefault("portfolio_sheet_id", "AAAAAAAAAA11")
    st.session_state.setdefault("stock_portfolio_sheet_id", "AAAAAAAAAA11")
    # 貼網址框先畫(同 app.py:側欄 / 狀態列的框都在主頁內容之前 render),Drive 挑選器後畫 ——
    # 這個順序才重現 QA 的 BLK-2:按 ✅ 的那一輪,貼網址框已經以舊值 A 建好 widget 狀態。
    pb.render_paste_id_binder(_Gsp, key_prefix="_p_")
    pb.render_drive_picker(_Gsp, key_prefix="_t_")
    st.write("bound=" + st.session_state["portfolio_sheet_id"] + "/"
             + st.session_state["stock_portfolio_sheet_id"])


def _bound(at):
    return [m.value for m in at.markdown if str(m.value).startswith("bound=")][-1]


def test_drive_pick_not_reverted_by_paste_box_widget_state():
    at = AppTest.from_function(_binder_app)
    at.run()
    assert not at.exception, at.exception
    assert at.text_input(key="_p_paste_sid").value == "AAAAAAAAAA11"
    at.button(key="_t_list").click().run()
    at.selectbox(key="_t_pick").select("乙本（BBBBBBBBBB22…）")
    at.button(key="_t_use").click().run()
    assert not at.exception, at.exception
    at.run()                                       # 下一輪 rerun:舊 widget 值不得把它綁回 A
    at.run()
    assert _bound(at) == "bound=BBBBBBBBBB22/BBBBBBBBBB22"
    assert at.query_params["sheet"] in ("BBBBBBBBBB22", ["BBBBBBBBBB22"])
    assert at.text_input(key="_p_paste_sid").value == "BBBBBBBBBB22", "綁定變了,文字框要顯示現值"


def test_paste_box_binds_only_when_user_changes_text():
    at = AppTest.from_function(_binder_app)
    at.run()
    at.run()
    assert _bound(at) == "bound=AAAAAAAAAA11/AAAAAAAAAA11"
    assert "sheet" not in at.query_params, "沒動文字框 ⇒ 不得寫任何東西"
    at.text_input(key="_p_paste_sid").input(
        "https://docs.google.com/spreadsheets/d/CCCCCCCCCC33/edit").run()
    assert not at.exception, at.exception
    assert _bound(at) == "bound=CCCCCCCCCC33/CCCCCCCCCC33"
    at.run()
    assert _bound(at) == "bound=CCCCCCCCCC33/CCCCCCCCCC33"


def test_paste_box_publish_link_shows_error_and_binds_nothing():
    at = AppTest.from_function(_binder_app)
    at.run()
    at.text_input(key="_p_paste_sid").input(
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vQabc/pubhtml").run()
    assert not at.exception, at.exception
    assert _bound(at) == "bound=AAAAAAAAAA11/AAAAAAAAAA11"
    assert any("發布到網路" in e.value for e in at.error)


def test_drive_use_on_already_current_sheet_says_so_not_false_success():
    at = AppTest.from_function(_binder_app)
    at.query_params["sheet"] = "AAAAAAAAAA11"
    at.run()
    at.button(key="_t_list").click().run()
    at.selectbox(key="_t_pick").select("甲本（AAAAAAAAAA11…）")
    at.button(key="_t_use").click().run()
    assert not at.exception, at.exception
    assert not any("已設定投組資料庫" in s.value for s in at.success)
    assert any("已是目前使用的 Sheet" in i.value for i in at.info)


# ── N-2：表頭不符的「怎麼辦」是改第一列，⛔ 不是重新登入 / 查網路 ─────────────────────────
@pytest.fixture
def mismatch_sheet(monkeypatch):
    """已登入 + 綁 'SID',`portfolios` 分頁第一列欄名不對(tripwire:任何寫入都紅)。"""
    from src.data.portfolio import gsheet_portfolio as gsp
    from tests.sheet_safety_fakes import TripwireClient
    gsp.clear_read_cache()
    cli = TripwireClient({'SID': {gsp._WORKSHEET_NAME: [['secret_header_xyz', 'b'], ['A', '1']]}})
    monkeypatch.setattr(gsp, '_build_client', lambda: cli)
    monkeypatch.setattr(gsp, '_has_oauth_tokens', lambda: True)
    monkeypatch.setattr(gsp, '_oauth_import_error', lambda: '')
    monkeypatch.setattr(gsp, 'login_expired', lambda: False)
    monkeypatch.setattr(gsp, '_get_active_sheet_id', lambda: 'SID')
    monkeypatch.setattr(gsp, '_get_active_stock_sheet_id', lambda: '')
    monkeypatch.setattr('src.services.dividend_station_service.resolve_holding_names', lambda h: h)
    yield cli
    assert cli.writes == []
    gsp.clear_read_cache()


def _assert_fix_header_guidance(card):
    from shared.ui_state import UI_FAILED
    from src.ui.views import page_hold as P
    assert card.state == UI_FAILED
    _where = card.note.where
    assert '把第一列從 A 欄起依序改成' in _where
    assert 'name、ticker、lots、avg_price、updated_at' in _where
    assert '重新用 Google 登入' not in _where and '網路' not in _where
    assert 'secret_header_xyz' not in _where
    P.v2_short_rows(card)            # 短句表有登記、摘錄對得上原文(否則 KeyError)


def test_count_card_schema_mismatch_says_fix_first_row(mismatch_sheet):
    from src.ui.views import page_hold as P
    b = P.load_binding(P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING))
    assert b.sheet_issue == 'schema_mismatch'
    card, _f, _ = P.build_portfolio_count_card(b)
    assert card.note.now == P.COUNT_SCHEMA_MISMATCH_NOW
    _assert_fix_header_guidance(card)


def test_preview_card_schema_mismatch_says_fix_first_row(mismatch_sheet):
    from src.ui.views import page_hold as P
    h = P.load_holdings(P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING))
    assert h.error and h.sheet_issue == 'schema_mismatch'
    card, _f, _ = P.build_holdings_preview_card(h)
    assert card.note.now == P.PREVIEW_SCHEMA_MISMATCH_NOW
    _assert_fix_header_guidance(card)


def test_other_read_failures_keep_the_existing_guidance():
    """對照:表頭不符以外的讀取失敗,文案與修前相同(本批只加一個分支)。"""
    from src.ui.views import page_hold as P
    from src.services import portfolio_binding_service as B
    b = P.BindingReadout(requested=True, submitted=True, logged_in=True, sheet_bound=True,
                         status=B.STATUS_BOUND, count_requested=True, portfolio_count=None,
                         count_missing_reason='fetch_failed', sheet_issue='permission_denied')
    card, _f, _ = P.build_portfolio_count_card(b)
    assert card.note.now == P.COUNT_DRIFT_NOW
    assert '重新用 Google 登入授權一次' in card.note.where


def test_old_status_bar_shows_red_text_label_on_read_problem():
    from src.services import portfolio_binding_service as B
    from src.ui.tabs.portfolio_status_bar import _label_for
    lbl = _label_for(B.BindingState(True, 'SHEETID', None, B.STATUS_BOUND,
                                    sheet_issue='schema_mismatch'))[0]
    assert lbl == '🔴 我的組合：讀取有問題'
    # 沒有讀取問題的降級(舊行為)照舊
    assert '數量未知' in _label_for(B.BindingState(True, 'SHEETID', None, B.STATUS_BOUND))[0]


# ── N-3：前進式驗證對帳的雲端說明不露內部代碼 ────────────────────────────────────────
@pytest.mark.parametrize('status, problem', [
    ('ok', False), ('empty', False), ('worksheet_missing', False), ('not_configured', False),
    ('', False), ('schema_mismatch', True), ('error:APIError', True), ('error:PermissionError', True)])
def test_forward_test_sheet_status_is_problem(status, problem):
    from src.services import forward_test_service as FT
    assert FT.sheet_status_is_problem(status) is problem
    _note = FT._sheet_note(status)
    assert bool(_note) is problem
    assert 'error:' not in _note and 'APIError' not in _note


def test_app_uses_warning_for_forward_test_sheet_problems():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / 'app.py').read_text(encoding='utf-8')
    assert src.count('sheet_status_is_problem(') == 2 and "st.warning(f'⚠️ {_ft_ov[\"note\"]}')" in src
