"""Sheet Safety 批 B1（DEC-083）— L3 `portfolio_binding_service` / `holdings_service` 的嚴格讀取。

- 沒有 `portfolios` 分頁 → `STATUS_BOUND_EMPTY` ＋ `portfolio_count=None`（⛔ 不寫 0）＋ `sheet_issue`。
- 表頭不符 / 權限等 → 維持既有降級（`STATUS_BOUND` ＋ None）＋ `sheet_issue` 帶分類代碼。
- `get_holdings`：投資組合那半表頭不符照舊往上拋；缺分頁記 `portfolio_issue`（灰,有效的空）。
- 整條讀取路徑零寫入（tripwire）。新版 UI 本批不改 —— 只驗它對 BOUND_EMPTY＋None 畫的是灰卡。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.data.portfolio import gsheet_portfolio as gsp
from src.services import holdings_service as HS
from src.services import portfolio_binding_service as B
from tests.sheet_safety_fakes import TripwireClient

H, WH = gsp._HEADERS, gsp._STOCK_WATCHLIST_HEADERS
PF, WL = gsp._WORKSHEET_NAME, gsp._STOCK_WATCHLIST_WORKSHEET


@pytest.fixture(autouse=True)
def _clear():
    gsp.clear_read_cache()
    yield
    gsp.clear_read_cache()


@pytest.fixture
def mount(monkeypatch):
    """已登入 + 綁 'SID'(兩通道)+ tripwire client。回傳 setter(books) → client。"""
    monkeypatch.setattr(gsp, '_has_oauth_tokens', lambda: True)
    monkeypatch.setattr(gsp, '_oauth_import_error', lambda: '')
    monkeypatch.setattr(gsp, '_get_active_sheet_id', lambda: 'SID')
    monkeypatch.setattr(gsp, '_get_active_stock_sheet_id', lambda: 'SID')
    monkeypatch.setattr(gsp, 'login_expired', lambda: False)
    monkeypatch.setattr('src.services.dividend_station_service.resolve_holding_names', lambda h: h)

    def _set(worksheets):
        cli = TripwireClient({'SID': worksheets})
        monkeypatch.setattr(gsp, '_build_client', lambda: cli)
        return cli
    return _set


@pytest.mark.parametrize('worksheets, status, count, issue', [
    ({}, B.STATUS_BOUND_EMPTY, None, gsp.READ_WORKSHEET_MISSING),
    ({PF: []}, B.STATUS_BOUND_EMPTY, 0, ''),
    ({PF: [H]}, B.STATUS_BOUND_EMPTY, 0, ''),
    ({PF: [H, ['A', '2330', '1', '1', 't'], ['B', '2330', '1', '1', 't']]}, B.STATUS_BOUND, 2, ''),
    ({PF: [['x', 'y'], ['A', '1']]}, B.STATUS_BOUND, None, gsp.READ_SCHEMA_MISMATCH),
])
def test_binding_state_strict_and_zero_writes(mount, worksheets, status, count, issue):
    cli = mount(worksheets)
    s = B.get_binding_state()
    assert (s.status, s.portfolio_count, s.sheet_issue) == (status, count, issue)
    assert s.read_error == '' and s.logged_in and s.sheet_id == 'SID'
    assert cli.writes == []


def test_binding_state_permission_error_keeps_degrade_with_issue(mount, monkeypatch):
    cli = MagicMock()
    cli.open_by_key.side_effect = PermissionError('403')
    monkeypatch.setattr(gsp, '_build_client', lambda: cli)
    s = B.get_binding_state()
    assert (s.status, s.portfolio_count, s.sheet_issue) == (
        B.STATUS_BOUND, None, gsp.READ_ERROR_PERMISSION_DENIED)


def test_binding_state_missing_worksheet_never_reports_zero(mount):
    """沒有分頁 ≠ 讀到 0 本：`portfolio_count` 必須是 None（L3 契約「不腦補 0」）。"""
    mount({})
    assert B.get_binding_state().portfolio_count is None


def test_new_ui_renders_bound_empty_with_unknown_count_as_grey_card(mount):
    """本批不改新版 UI：只驗 page_hold 對 BOUND_EMPTY＋None 畫的是灰色「綁了但空」(UI_EMPTY),不是紅卡。"""
    from shared.ui_state import UI_EMPTY
    from src.ui.views import page_hold as P
    mount({})
    _req = P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING)
    assert _req.wants_binding
    b = P.load_binding(_req)
    card, _facts, _ = P.build_portfolio_count_card(b)
    assert card.state == UI_EMPTY, card


def test_status_bar_label_for_missing_worksheet_is_bound_empty(mount):
    from src.ui.tabs.portfolio_status_bar import _label_for
    mount({})
    label, _tip = _label_for(B.get_binding_state())
    assert '還沒有組合資料' in label


# ── get_holdings ──────────────────────────────────────────────────────────
def test_holdings_missing_portfolio_worksheet_is_valid_empty(mount):
    cli = mount({WL: [WH, ['觀察', '2454', 't']]})
    r = HS.get_holdings()
    assert r.bound and r.held == ()
    assert r.portfolio_issue == gsp.READ_WORKSHEET_MISSING
    assert [h['ticker'] for h in r.holdings] == ['2454']
    assert r.watchlist_error == '' and r.watchlist_issue == ''
    assert cli.writes == []


def test_holdings_missing_watchlist_worksheet_is_not_an_error(mount):
    cli = mount({PF: [H, ['核心', '0056', '3', '30', 't']]})
    r = HS.get_holdings()
    assert [h['ticker'] for h in r.held] == ['0056']
    assert r.watchlist_issue == gsp.READ_WORKSHEET_MISSING
    assert r.watchlist_error == ''
    assert cli.writes == []


def test_holdings_portfolio_schema_mismatch_still_raises(mount):
    cli = mount({PF: [['x', 'y'], ['A', '1']], WL: [WH]})
    with pytest.raises(gsp.SheetSchemaMismatchError):
        HS.get_holdings()
    assert cli.writes == []


def test_holdings_watchlist_schema_mismatch_is_reported_not_swallowed(mount):
    cli = mount({PF: [H, ['核心', '0056', '3', '30', 't']], WL: [['x'], ['1']]})
    r = HS.get_holdings()
    assert [h['ticker'] for h in r.held] == ['0056']
    assert 'SheetSchemaMismatchError' in r.watchlist_error
    assert r.watchlist_issue == gsp.READ_SCHEMA_MISMATCH
    assert cli.writes == []


def test_holdings_happy_path_unchanged(mount):
    mount({PF: [H, ['核心', '0056', '3', '30', 't']], WL: [WH, ['觀察', '0056', 't'], ['觀察', '2454', 't']]})
    r = HS.get_holdings()
    assert [(h['ticker'], h['held']) for h in r.holdings] == [('0056', True), ('2454', False)]
    assert (r.portfolio_issue, r.watchlist_issue, r.watchlist_error) == ('', '', '')


def test_classify_fallback_when_l1_classifier_breaks():
    fake = MagicMock()
    fake.classify_read_error.side_effect = RuntimeError('boom')
    assert B._classify_read_error(fake, ValueError()) == 'error:ValueError'


def test_no_write_with_patch_free_real_l1_on_binding_presence(mount):
    """`get_binding_presence` 照舊不連 Google（本批未動它）。"""
    cli = mount({})
    B.get_binding_presence()
    assert cli.opened == [] and cli.writes == []
