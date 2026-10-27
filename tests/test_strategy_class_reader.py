"""AB-4r：L1 `strategy_class_reader` ＋ `gsheet_portfolio.read_worksheet_values`（唯讀；⛔ 不打真 Google）。

全部經 `tests.sheet_safety_fakes.TripwireClient`（任何寫入方法一呼叫就記錄並拋錯）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from shared import strategy_class_schema as S
from shared.decision_digest import HoldingKey, StrategyType
from src.data.portfolio import gsheet_portfolio as gsp
from src.data.portfolio import strategy_class_reader as R
from tests.sheet_safety_fakes import TripwireClient
from tests.test_sheet_safety_guards import _WRITE_HELPERS, _closure, _module_functions

SID = "SID"
H = list(S.STRATEGY_HEADERS)
WS = S.STRATEGY_WORKSHEET_NAME
_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def books(monkeypatch):
    gsp.clear_read_cache()
    _books: dict = {}
    cli = TripwireClient(_books)
    monkeypatch.setattr(gsp, '_build_client', lambda: cli)
    yield _books, cli
    gsp.clear_read_cache()


def _key(name, ticker):
    return HoldingKey(S.derive_portfolio_id(SID, name), ticker)


def test_ok_reads_entries(books):
    b, cli = books
    b[SID] = {WS: [H, ['核心', '2330', '存股', 't'], ['核心', '0050', '資本利得', 't']],
              gsp._WORKSHEET_NAME: [gsp._HEADERS]}
    r = R.read_strategy_classes(sheet_id=SID)
    assert r.status == 'ok'
    assert dict(r.entries) == {_key('核心', '2330'): StrategyType.BUY_AND_HOLD,
                               _key('核心', '0050'): StrategyType.CAPITAL_GAIN}
    assert cli.writes == []


def test_reader_and_holding_keys_agree_on_pid(books):
    b, _ = books
    b[SID] = {WS: [H, [' 核心 ', '2330', '存股', 't']]}
    r = R.read_strategy_classes(sheet_id=SID)
    hk = S.build_holding_keys(sheet_id=SID, portfolio_name='核心', tickers=['2330', '2454'])
    assert S.lookup(r, hk.keys['2330']) is StrategyType.BUY_AND_HOLD
    assert S.lookup(r, hk.keys['2454']) is StrategyType.UNCLASSIFIED


@pytest.mark.parametrize('sid', [None, '', '   ', 'e', 'bad id', '/spreadsheets/d/x'])
def test_not_bound(books, sid):
    _, cli = books
    r = R.read_strategy_classes(sheet_id=sid)
    assert r.status == 'not_bound' and not r.entries
    assert cli.opened == []


def test_not_bound_non_str_type_error(books):
    with pytest.raises(TypeError):
        R.read_strategy_classes(sheet_id=123)


def test_worksheet_missing_does_not_create(books):
    b, cli = books
    b[SID] = {gsp._WORKSHEET_NAME: [gsp._HEADERS]}
    r = R.read_strategy_classes(sheet_id=SID)
    assert r.status == 'worksheet_missing' and not r.entries
    assert cli.writes == []
    assert WS not in b[SID]
    assert S.lookup(r, _key('核心', '2330')) is StrategyType.UNCLASSIFIED


def test_empty_worksheet_is_ok_empty(books):
    b, _ = books
    b[SID] = {WS: []}
    r = R.read_strategy_classes(sheet_id=SID)
    assert r.status == 'ok' and not r.entries


def test_header_mismatch_raises_gsheet_type(books):
    b, cli = books
    b[SID] = {WS: [['name', 'ticker', 'strat', 'updated_at'], ['核心', '2330', '存股', 't']]}
    with pytest.raises(gsp.SheetSchemaMismatchError) as ei:
        R.read_strategy_classes(sheet_id=SID)
    assert isinstance(ei.value.__cause__, S.StrategySchemaMismatchError)
    assert gsp.classify_read_error(ei.value) == gsp.READ_SCHEMA_MISMATCH
    assert ei.value.worksheet_name == WS and cli.writes == []


def test_duplicate_header_raises(books):
    b, _ = books
    b[SID] = {WS: [H + ['ticker'], ['核心', '2330', '存股', 't']]}
    with pytest.raises(gsp.SheetSchemaMismatchError):
        R.read_strategy_classes(sheet_id=SID)


class _Boom(Exception):
    pass


@pytest.mark.parametrize('exc', [PermissionError('403'), ConnectionError('net'), TimeoutError('slow'),
                                 _Boom('x'), gsp.LoginRequiredError('login')])
def test_errors_propagate(monkeypatch, exc):
    gsp.clear_read_cache()

    def _raise():
        raise exc
    monkeypatch.setattr(gsp, '_build_client', _raise)
    with pytest.raises(type(exc)):
        R.read_strategy_classes(sheet_id=SID)


def test_open_by_key_error_propagates(books):
    # 找不到 Sheet（books 沒有 SID）→ TripwireClient 拋錯 ⇒ 原樣上拋，不轉成 worksheet_missing
    with pytest.raises(PermissionError):
        R.read_strategy_classes(sheet_id='OTHER')


def test_reader_passes_sanitized_sheet_id(monkeypatch):
    seen = []
    monkeypatch.setattr(gsp, 'read_worksheet_values', lambda ws, *, sheet_id: seen.append((ws, sheet_id)) or [H])
    R.read_strategy_classes(sheet_id='  SID ')
    assert seen == [(WS, 'SID')]


# ── gsheet_portfolio.read_worksheet_values ─────────────────────────────
def test_read_worksheet_values_raw_strings(books):
    b, cli = books
    b[SID] = {WS: [H, ['核心', '0050', '存股', '']]}
    assert gsp.read_worksheet_values(WS, sheet_id=SID) == [H, ['核心', '0050', '存股', '']]
    assert cli.writes == []


def test_read_worksheet_values_missing_raises(books):
    b, _ = books
    b[SID] = {}
    with pytest.raises(gsp.SheetWorksheetMissingError):
        gsp.read_worksheet_values(WS, sheet_id=SID)


@pytest.mark.parametrize('sid', ['', None, 'e', 'a b'])
def test_read_worksheet_values_requires_sheet_id_no_fallback(books, monkeypatch, sid):
    monkeypatch.setattr(gsp, '_get_active_sheet_id', lambda: SID)
    with pytest.raises(gsp.SheetNotConfiguredError):
        gsp.read_worksheet_values(WS, sheet_id=sid)


@pytest.mark.parametrize('name', ['', '  ', None, 3])
def test_read_worksheet_values_bad_worksheet_name(books, name):
    with pytest.raises(ValueError):
        gsp.read_worksheet_values(name, sheet_id=SID)


def test_read_worksheet_values_cached_keys_not_underscored():
    import inspect
    params = inspect.signature(gsp._read_worksheet_values_cached).parameters
    assert {'identity', 'worksheet_name', 'sheet_id', 'read_gen'} <= set(params)


# ── 靜態：讀取路徑零寫入、既有讀取入口不受影響 ──────────────────────────
def _gsp_funcs():
    return _module_functions(ast.parse((_ROOT / 'src/data/portfolio/gsheet_portfolio.py')
                                       .read_text(encoding='utf-8')))


def test_read_worksheet_values_closure_has_no_write_helpers_or_methods():
    from tests.sheet_safety_fakes import WRITE_METHODS
    funcs = _gsp_funcs()
    reach = _closure(funcs, 'read_worksheet_values')
    assert '_ws' in reach and '_worksheet_values' in reach, '前提：守衛不是空轉'
    assert not (reach & _WRITE_HELPERS)
    hits = {(f, n.func.attr) for f in reach for n in ast.walk(funcs[f])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in WRITE_METHODS}
    assert not hits, hits


def test_reader_module_imports_no_streamlit_and_calls_no_writes():
    src = (_ROOT / 'src/data/portfolio/strategy_class_reader.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module or '')
    assert not any(m.split('.')[0] == 'streamlit' for m in mods)
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    from tests.sheet_safety_fakes import WRITE_METHODS
    assert not (attrs & (set(WRITE_METHODS) | _WRITE_HELPERS)), attrs & (set(WRITE_METHODS) | _WRITE_HELPERS)


def test_write_api_monkeypatched_to_fail_is_never_hit(books, monkeypatch):
    b, _ = books
    b[SID] = {}
    for name in ('_ws_for_write', '_write_whole_sheet', 'save_portfolio', 'save_stock_watchlist'):
        monkeypatch.setattr(gsp, name, lambda *a, **k: pytest.fail('讀取路徑呼叫了寫入 API'))
    assert R.read_strategy_classes(sheet_id=SID).status == 'worksheet_missing'
    b[SID] = {WS: [H, ['核心', '2330', '存股', 't']]}
    gsp.clear_read_cache()
    assert R.read_strategy_classes(sheet_id=SID).status == 'ok'
