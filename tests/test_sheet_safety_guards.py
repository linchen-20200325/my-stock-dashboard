"""Sheet Safety 批（DEC-083）靜態 + 執行守衛：讀取零寫入、單一 parser、單一綁定寫入者。

1. 靜態：L1 讀取函式（含傳遞呼叫）不碰任何 gspread 寫入方法、也不呼叫寫入 helper。
2. 靜態：`/spreadsheets/…d/` 解析正則全 repo 只准在 `shared/sheet_id.py`（B3）。
3. 靜態：`st.session_state['portfolio_sheet_id' / 'stock_portfolio_sheet_id']` 只准由
   `oauth_state` 的唯一寫入契約寫入 / 清除（B4）。
4. 執行：tripwire 假 gspread（任何寫入方法一呼叫就紅）實跑所有讀取路徑 ——
   L1 四支讀取、forward-test 讀取、`get_binding_state`、`get_holdings`、板塊資金潮汐的觀察清單收集、
   `reconcile_all`（真的走 L3 → L1，價格用替身）。
"""
from __future__ import annotations

import ast
import pathlib

import pandas as pd
import pytest

from src.data.portfolio import gsheet_portfolio as gsp
from tests.sheet_safety_fakes import WRITE_METHODS, TripwireClient

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_GSP_SRC = _ROOT / 'src' / 'data' / 'portfolio' / 'gsheet_portfolio.py'

#: L1 讀取入口（public 讀取 ＋ forward-test 讀取 ＋ 唯讀資訊）。
_READ_ENTRIES = (
    'list_portfolios', 'load_portfolio', 'list_stock_watchlists', 'load_stock_watchlist',
    'read_forward_test_picks', 'load_forward_test_picks', 'get_sheet_title',
    'list_user_sheets', 'list_user_folders', 'is_configured', 'login_expired',
)
#: 只為寫入而存在的 helper（讀取路徑不得傳遞呼叫到它們）。
_WRITE_HELPERS = {
    '_ws_for_write', '_ft_worksheet_for_write', '_write_whole_sheet', '_require_writable_header',
    'save_portfolio', 'save_stock_watchlist', 'add_to_stock_watchlist', 'append_forward_test_picks',
    'delete_portfolio', 'delete_stock_watchlist', 'create_new_sheet', 'rename_sheet',
    '_get_or_create_app_folder',
}


def _module_functions(tree):
    return {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _called_names(fn) -> set[str]:
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                out.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                out.add(n.func.attr)
        elif isinstance(n, ast.Name):          # 當參數傳進去的函式（例 `_read_status(fn, …)`）
            out.add(n.id)
    return out


def _closure(funcs, entry):
    seen, todo = set(), [entry]
    while todo:
        f = todo.pop()
        if f in seen or f not in funcs:
            continue
        seen.add(f)
        todo += [c for c in _called_names(funcs[f]) if c in funcs]
    return seen


@pytest.mark.parametrize('entry', _READ_ENTRIES)
def test_l1_read_paths_have_no_write_calls(entry):
    funcs = _module_functions(ast.parse(_GSP_SRC.read_text(encoding='utf-8')))
    assert entry in funcs, f'讀取入口 {entry} 不見了 —— 守衛清單要更新'
    reach = _closure(funcs, entry)
    _bad_helpers = sorted(reach & _WRITE_HELPERS)
    assert not _bad_helpers, f'{entry} 會傳遞呼叫寫入 helper：{_bad_helpers}'
    _hits = sorted({(f, n.func.attr) for f in reach for n in ast.walk(funcs[f])
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in WRITE_METHODS})
    # list_user_* 走 Drive HTTP 'get'(http_client.request('get', …)),不是 gspread 寫入方法。
    assert not _hits, f'{entry} 的讀取路徑出現 gspread 寫入方法呼叫：{_hits}'


def test_write_helpers_still_exist_so_the_guard_is_not_vacuous():
    funcs = _module_functions(ast.parse(_GSP_SRC.read_text(encoding='utf-8')))
    assert {'_ws_for_write', '_ft_worksheet_for_write', '_write_whole_sheet'} <= set(funcs)
    assert _closure(funcs, 'save_portfolio') & {'_ws_for_write'}, '對照組:寫入路徑確實會走寫入 helper'


# ── 2. 單一 parser ─────────────────────────────────────────────────────────
_PARSER_SSOT = 'shared/sheet_id.py'
#: 不是 Sheet ID 解析器、但字串裡含 spreadsheets 與正則字元的檔（逐檔理由）：
#:   secret_scrub —— 遮蔽 log / 例外訊息裡的 Google 文件識別碼（遮蔽，不是解析綁定）；
#:   risk_cap/history —— Risk Cap 寫入身分的 scope 檢查（DEC-083 G：⛔ 不碰 Risk Cap）。
_PARSER_WHITELIST = {'shared/secret_scrub.py', 'src/data/risk_cap/history.py'}
_SCAN = ('src', 'shared', 'scripts', 'infra', 'mcp_server')


def _py_files():
    for base in _SCAN:
        p = _ROOT / base
        if p.exists():
            yield from (f for f in sorted(p.rglob('*.py')) if '__pycache__' not in f.parts)
    yield _ROOT / 'app.py'


def _docstring_ids(tree) -> set[int]:
    out = set()
    for n in [tree] + [x for x in ast.walk(tree)
                       if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]:
        if n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            out.add(id(n.body[0].value))
    return out


def test_only_one_sheet_url_parser_regex_in_repo():
    hits = []
    for f in _py_files():
        rel = f.relative_to(_ROOT).as_posix()
        if rel == _PARSER_SSOT or rel in _PARSER_WHITELIST:
            continue
        tree = ast.parse(f.read_text(encoding='utf-8'))
        _docs = _docstring_ids(tree)
        for n in ast.walk(tree):
            if (isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in _docs
                    and 'spreadsheets' in n.value and any(c in n.value for c in '([')):
                hits.append(f'{rel}:{n.lineno}')
    assert not hits, f'發現第二份 Sheet URL 解析正則（B3 只准 {_PARSER_SSOT}）：{hits}'


def test_parser_ssot_really_holds_the_regexes():
    src = (_ROOT / _PARSER_SSOT).read_text(encoding='utf-8')
    assert '/spreadsheets/(?:u/\\d+/)?d/e(?=[/?#]|$)' in src and '/spreadsheets/(?:u/\\d+/)?d/(' in src


# ── 3. 單一綁定寫入者 ───────────────────────────────────────────────────────
_BIND_LITERALS = {'portfolio_sheet_id', 'stock_portfolio_sheet_id'}
_BIND_NAMES = {'PORTFOLIO_SHEET_KEY', 'STOCK_PORTFOLIO_SHEET_KEY', 'PORTFOLIO_SHEET_SESSION_KEY',
               'STOCK_PORTFOLIO_SHEET_SESSION_KEY', 'SS_STOCK_SHEET_ID'}
#: 唯一准寫 / 清兩格的地方（檔 → 函式）。
_BIND_WRITERS = {('src/data/portfolio/oauth_state.py', '_write_binding_session'),
                 ('src/data/portfolio/oauth_state.py', 'clear_sheet_binding'),
                 ('src/data/portfolio/oauth_state.py', 'restore_sheet_binding_from_query')}


def _is_bind_key(node) -> bool:
    if isinstance(node, ast.Constant):
        return node.value in _BIND_LITERALS
    if isinstance(node, ast.Attribute):
        return node.attr in _BIND_NAMES
    if isinstance(node, ast.Name):
        return node.id in _BIND_NAMES
    return False


def _is_session_state(node) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == 'session_state') or \
           (isinstance(node, ast.Name) and node.id in ('session_state', 'session'))


def _enclosing_functions(tree):
    parent = {}
    for p in ast.walk(tree):
        for c in ast.iter_child_nodes(p):
            parent[c] = p

    def _fn(n):
        while n in parent:
            n = parent[n]
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return n.name
        return '<module>'
    return _fn


def test_binding_session_keys_written_only_by_the_contract():
    hits = []
    for f in _py_files():
        rel = f.relative_to(_ROOT).as_posix()
        tree = ast.parse(f.read_text(encoding='utf-8'))
        fn_of = _enclosing_functions(tree)
        for n in ast.walk(tree):
            bad = False
            if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
                tgts = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]
                bad = any(isinstance(t, ast.Subscript) and _is_session_state(t.value)
                          and _is_bind_key(t.slice) for t in tgts)
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and _is_session_state(n.func.value)):
                if n.func.attr in ('setdefault', 'pop', '__setitem__', '__delitem__'):
                    bad = bool(n.args) and _is_bind_key(n.args[0])
                elif n.func.attr == 'update':
                    bad = any(isinstance(a, ast.Dict) and any(_is_bind_key(k) for k in a.keys if k)
                              for a in n.args) or any(k.arg in _BIND_LITERALS for k in n.keywords)
            elif isinstance(n, ast.For) and _is_bind_name(n.iter):
                bad = True                       # 例:`for _k in SHEET_BINDING_SESSION_KEYS: …`
            if bad and (rel, fn_of(n)) not in _BIND_WRITERS:
                hits.append(f'{rel}:{n.lineno} ({fn_of(n)})')
    assert not hits, f'綁定 session key 在唯一寫入契約以外被寫入／清除（B4）：{hits}'


def _is_bind_name(node) -> bool:
    return (isinstance(node, ast.Name) and node.id == 'SHEET_BINDING_SESSION_KEYS') or \
           (isinstance(node, ast.Attribute) and node.attr == 'SHEET_BINDING_SESSION_KEYS')


def test_binding_guard_is_not_vacuous():
    """對照組:契約本身確實寫兩格(守衛的偵測式抓得到它)。"""
    src = (_ROOT / 'src' / 'data' / 'portfolio' / 'oauth_state.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    fn_of = _enclosing_functions(tree)
    found = {fn_of(n) for n in ast.walk(tree) if isinstance(n, ast.For) and _is_bind_name(n.iter)}
    assert {'_write_binding_session', 'clear_sheet_binding', 'restore_sheet_binding_from_query'} <= found


def test_app_logout_clears_binding_and_sidebar_widget():
    src = (_ROOT / 'app.py').read_text(encoding='utf-8')
    i = src.index("key='btn_oauth_logout_sb'")
    j = src.index('st.rerun()', i)
    blk = src[i:j]
    assert '_sb_forget_silent()' in blk and '_sb_clear_binding()' in blk
    assert "st.session_state.pop('sb_portfolio_sheet_id_input', None)" in blk


# ── 4. 執行：所有讀取路徑零寫入 ─────────────────────────────────────────────
H, WH, FH = gsp._HEADERS, gsp._STOCK_WATCHLIST_HEADERS, gsp._FT_HEADERS
_SHEETS = {
    'ok': {gsp._WORKSHEET_NAME: [H, ['核心', '0056', '3', '30', 't']],
           gsp._STOCK_WATCHLIST_WORKSHEET: [WH, ['觀察', '2454', 't']],
           gsp._FT_WORKSHEET_NAME: [FH, ['2026-09-30', '0050', 'x', '180', 'f', 't']]},
    'missing': {},
    'mismatch': {gsp._WORKSHEET_NAME: [['x'], ['1']], gsp._STOCK_WATCHLIST_WORKSHEET: [['x'], ['1']],
                 gsp._FT_WORKSHEET_NAME: [['x'], ['1']]},
    'empty': {gsp._WORKSHEET_NAME: [], gsp._STOCK_WATCHLIST_WORKSHEET: [], gsp._FT_WORKSHEET_NAME: []},
}


@pytest.fixture(params=sorted(_SHEETS))
def tripwire(request, monkeypatch):
    gsp.clear_read_cache()
    cli = TripwireClient({'SID': _SHEETS[request.param]})
    monkeypatch.setattr(gsp, '_build_client', lambda: cli)
    monkeypatch.setattr(gsp, '_has_oauth_tokens', lambda: True)
    monkeypatch.setattr(gsp, '_oauth_import_error', lambda: '')
    monkeypatch.setattr(gsp, 'is_configured', lambda: True)
    monkeypatch.setattr(gsp, 'login_expired', lambda: False)
    monkeypatch.setattr(gsp, '_get_active_sheet_id', lambda: 'SID')
    monkeypatch.setattr(gsp, '_get_active_stock_sheet_id', lambda: 'SID')
    monkeypatch.setattr('src.services.dividend_station_service.resolve_holding_names', lambda h: h)
    monkeypatch.setattr('src.data.portfolio.forward_test_store.load_picks_local', lambda: [])
    monkeypatch.setattr('src.data.stock.picker_fetcher.fetch_stock_history_1y',
                        lambda code: (pd.DataFrame({'Close': [100.0]}), None))
    yield cli
    gsp.clear_read_cache()


def _swallow(fn):
    try:
        fn()
    except gsp.SheetSchemaMismatchError:
        pass          # 表頭不符 → 拋錯是正確行為;本條只驗「沒有寫入」


def test_every_read_path_makes_zero_writes(tripwire):
    from src.services import forward_test_service as FT
    from src.services import holdings_service as HS
    from src.services import portfolio_binding_service as B
    from src.services import sector_flow_service as SF
    for fn in (lambda: gsp.list_portfolios(sheet_id='SID'),
               lambda: gsp.list_portfolios(sheet_id='SID', raise_if_missing=True),
               lambda: gsp.load_portfolio('核心', sheet_id='SID'),
               lambda: gsp.load_portfolio('核心', sheet_id='SID', keep_blank=True),
               lambda: gsp.list_stock_watchlists(sheet_id='SID'),
               lambda: gsp.load_stock_watchlist('觀察', sheet_id='SID'),
               gsp.read_forward_test_picks, gsp.load_forward_test_picks,
               lambda: gsp.get_sheet_title('SID'),
               B.get_binding_state, B.get_binding_presence, HS.get_holdings,
               lambda: SF._collect_stock_watchlist_tickers('SID'),
               FT.load_frozen_picks_df, FT.reconcile_all):
        try:
            _swallow(fn)
        except gsp.SheetWorksheetMissingError:
            pass
    assert tripwire.writes == [], tripwire.writes
    assert tripwire.opened, '前提:讀取真的打到(假的)Google'
