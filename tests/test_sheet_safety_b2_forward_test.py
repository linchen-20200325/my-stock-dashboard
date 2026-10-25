"""Sheet Safety 批 B2（DEC-083）：`forward_test_picks`（不可重建歷史）讀取 / 對帳零寫入。

客戶原文：「read path 零寫入；reconcile/read 不得 create；不得重建 header；不得 rewrite；
不得因 schema 不符自行修復。」
⛔ 不打真 Google、⛔ 不抓真價：Sheet 用 tripwire（任何寫入方法一呼叫就紅），價格用替身。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.portfolio import gsheet_portfolio as gsp
from tests.sheet_safety_fakes import TripwireClient
from tests.test_gsheet_portfolio import _FakeWorksheet

FT, FH = gsp._FT_WORKSHEET_NAME, gsp._FT_HEADERS
_ROW = ['2026-09-30', '0050', '元大台灣50', '180.5', 'pe_low', '2026-09-30T19:00:00+08:00']


def _mount(worksheets, *, sid='SID'):
    cli = TripwireClient({'SID': worksheets})
    return cli, (patch.object(gsp, '_build_client', return_value=cli),
                 patch.object(gsp, '_get_active_sheet_id', return_value=sid))


def _read(worksheets, **kw):
    cli, (p1, p2) = _mount(worksheets, **kw)
    with p1, p2:
        out = gsp.read_forward_test_picks()
    assert cli.writes == [], cli.writes
    return out, cli


@pytest.mark.parametrize('worksheets, expected_status', [
    ({}, gsp.READ_WORKSHEET_MISSING),
    ({FT: []}, gsp.READ_EMPTY),
    ({FT: [['', '', ''], ['', '', '']]}, gsp.READ_EMPTY),
    ({FT: [['x', 'y'], _ROW]}, gsp.READ_SCHEMA_MISMATCH),
    ({FT: [FH[:3], _ROW[:3]]}, gsp.READ_SCHEMA_MISMATCH),                # 只有前段 ⇒ 不替它補
    ({FT: [FH + ['stock_id'], _ROW + ['']]}, gsp.READ_SCHEMA_MISMATCH),  # 欄重複
    ({FT: [['', '', ''], _ROW]}, gsp.READ_SCHEMA_MISMATCH),              # 第一列空、下面有資料
    ({FT: [FH]}, gsp.READ_OK),
])
def test_read_statuses_zero_writes(worksheets, expected_status):
    (status, recs), _ = _read(worksheets)
    assert status == expected_status
    assert recs == []


def test_read_ok_keeps_text_codes_and_user_trailing_columns():
    (status, recs), _ = _read({FT: [FH + ['note'], _ROW + ['mine']]})
    assert status == gsp.READ_OK
    assert recs[0]['stock_id'] == '0050' and recs[0]['entry_price'] == 180.5
    assert recs[0]['note'] == 'mine'


def test_read_not_configured_without_sheet_id_does_not_touch_google():
    (status, recs), cli = _read({FT: [FH]}, sid='')
    assert (status, recs) == (gsp.READ_NOT_CONFIGURED, [])
    assert cli.opened == []


def test_read_not_logged_in_is_not_configured():
    with patch.object(gsp, '_build_client', side_effect=gsp.LoginRequiredError('x')), \
         patch.object(gsp, '_get_active_sheet_id', return_value='SID'):
        assert gsp.read_forward_test_picks() == (gsp.READ_NOT_CONFIGURED, [])


def test_read_permission_error_is_named_status_not_swallowed_silently():
    cli = MagicMock()
    cli.open_by_key.side_effect = PermissionError('403')
    with patch.object(gsp, '_build_client', return_value=cli), \
         patch.object(gsp, '_get_active_sheet_id', return_value='SID'):
        assert gsp.read_forward_test_picks() == ('error:PermissionError', [])
        assert gsp.load_forward_test_picks() == []          # 舊 list 介面相容


# ── L3 對帳：讀取 / 對帳整條路徑零寫入；表頭不符 → 只用本地、白話揭露；L2 公式不變 ─────────
_LOCAL = [{'cohort': '2026-09-30', 'stock_id': '2330', 'name': '台積電', 'entry_price': 1000.0,
           'factors': 'pe_low', 'frozen_at': 'x'}]


def _price_df(close):
    return pd.DataFrame({'Close': [close]})


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr('src.data.portfolio.forward_test_store.load_picks_local', lambda: list(_LOCAL))
    monkeypatch.setattr('src.data.stock.picker_fetcher.fetch_stock_history_1y',
                        lambda code: (_price_df(1100.0 if code == '2330' else 200.0), None))


@pytest.mark.parametrize('worksheets', [
    {}, {FT: []}, {FT: [['x', 'y'], _ROW]}, {FT: [FH[:2], _ROW[:2]]}])
def test_reconcile_all_read_path_never_writes(offline, worksheets):
    from src.services import forward_test_service as fts
    cli, (p1, p2) = _mount(worksheets)
    with p1, p2:
        fts.reconcile_all()
    assert cli.writes == []


def test_reconcile_schema_mismatch_uses_local_only_and_discloses(offline):
    from src.compute.screener.forward_test import reconcile_forward_test
    from src.services import forward_test_service as fts
    cli, (p1, p2) = _mount({FT: [['x', 'y'], _ROW]})
    with p1, p2:
        df = fts.load_frozen_picks_df()
        per, overall = fts.reconcile_all()
    assert df.attrs['sheet_status'] == gsp.READ_SCHEMA_MISMATCH
    assert '第一列欄名' in df.attrs['sheet_note'] and '不會自動修改' in df.attrs['sheet_note']
    assert df['stock_id'].tolist() == ['2330']
    assert overall['sheet_status'] == gsp.READ_SCHEMA_MISMATCH
    assert df.attrs['sheet_note'] in overall['note']
    # L2 對帳公式不變：與直接以本地紀錄呼叫 L2 的結果逐欄相同（note 以外）。
    exp_per, exp_ov = reconcile_forward_test(
        df, {'2330': 1100.0}, benchmark_returns=fts_bench(df))
    pd.testing.assert_frame_equal(per, exp_per)
    assert {k: v for k, v in overall.items() if k not in ('note', 'sheet_status')} == \
        {k: v for k, v in exp_ov.items() if k != 'note'}
    assert cli.writes == []


def fts_bench(df):
    from src.compute.screener.forward_test import benchmark_returns_from_close
    return benchmark_returns_from_close(_price_df(200.0)['Close'], list(df['cohort'].unique()))


@pytest.mark.parametrize('worksheets, status', [
    ({}, gsp.READ_WORKSHEET_MISSING), ({FT: []}, gsp.READ_EMPTY), ({FT: [FH]}, gsp.READ_OK)])
def test_normal_states_add_no_note(offline, worksheets, status):
    from src.services import forward_test_service as fts
    _, (p1, p2) = _mount(worksheets)
    with p1, p2:
        df = fts.load_frozen_picks_df()
    assert df.attrs == {'sheet_status': status, 'sheet_note': ''}


def test_union_with_cloud_rows_unchanged(offline):
    from src.services import forward_test_service as fts
    _, (p1, p2) = _mount({FT: [FH, _ROW]})
    with p1, p2:
        df = fts.load_frozen_picks_df()
    assert sorted(df['stock_id'].tolist()) == ['0050', '2330']


# ── 寫入（使用者按 🧊 凍結 ＝ 明確寫入動作）────────────────────────────────────
def _blank_ws():
    """整張空白的假 worksheet(同真 Sheet:append 從第 1 列開始)。"""
    ws = _FakeWorksheet([[]], row_count=1000, col_count=8)
    ws.rows = []
    return ws


def _write_env(existing_ws=None):
    import gspread
    sh = MagicMock()
    created = _blank_ws()
    if existing_ws is None:
        sh.worksheet.side_effect = gspread.WorksheetNotFound(FT)
    else:
        sh.worksheet.return_value = existing_ws
    sh.add_worksheet.return_value = created
    cli = MagicMock()
    cli.open_by_key.return_value = sh
    return cli, sh, created


_PICK = [{h: v for h, v in zip(FH, _ROW)}]


def _append(cli):
    with patch.object(gsp, '_build_client', return_value=cli), \
         patch.object(gsp, '_get_active_sheet_id', return_value='SID'):
        return gsp.append_forward_test_picks(_PICK)


def test_append_creates_missing_worksheet_with_header():
    cli, sh, created = _write_env()
    assert _append(cli) == 1
    sh.add_worksheet.assert_called_once()
    assert created.get_all_values() == [FH, _ROW]


def test_append_to_fully_blank_worksheet_writes_header_first():
    ws = _blank_ws()
    cli, sh, _ = _write_env(ws)
    assert _append(cli) == 1
    sh.add_worksheet.assert_not_called()
    assert ws.get_all_values() == [FH, _ROW]


def test_append_to_ok_worksheet_only_appends():
    ws = _FakeWorksheet([FH, _ROW])
    cli, _, _ = _write_env(ws)
    _append(cli)
    assert [c[0] for c in ws.calls] == ['append_rows']


@pytest.mark.parametrize('bad', [[['x', 'y'], _ROW], [FH[:3], _ROW[:3]], [FH + ['name'], _ROW + ['']]])
def test_append_refuses_schema_mismatch_no_header_rebuild_no_append(bad):
    ws = _FakeWorksheet([list(r) for r in bad])
    before = ws.get_all_values()
    cli, sh, _ = _write_env(ws)
    with pytest.raises(gsp.SheetSchemaMismatchError):
        _append(cli)
    assert ws.calls == [] and ws.get_all_values() == before
    sh.add_worksheet.assert_not_called()


def test_append_empty_rows_does_not_open_sheet():
    cli, _, _ = _write_env()
    with patch.object(gsp, '_build_client', return_value=cli):
        assert gsp.append_forward_test_picks([]) == 0
    cli.open_by_key.assert_not_called()
