"""New UI2 守衛（NUI2-GUARD-REGISTRATION／NUI2-VM-BOUNDARY；Architecture Gate §9 G1～G5、G9）。

═══ 結構 ═══════════════════════════════════════════════════════════════
- 檢查器（`check_*`）是**純函式**，吃「原始碼字串」回傳違規清單 ⇒ 同一支檢查器
  既掃真檔（必須 0 違規），也掃「刻意注入違規的假原始碼」（必須 >0 違規）。
  後者就是「mutation：拔掉守衛必轉紅」的可執行版本 —— 守衛若是永遠綠燈的裝飾品，
  注入測試會立刻紅燈。
- 行為守衛（G3 切片獨立、G5 四態）同理：`check_*(builder)` 吃 builder callable，
  對真 builder 必須綠、對刻意壞掉的 builder 必須紅。

⛔ 本檔不改任何既有守衛的斷言；c3 的登記只做加性擴充（見 test_c3_layering_guard.py）。
"""
from __future__ import annotations

import ast
import pathlib
from dataclasses import replace

import pytest

from shared.ui2_contract import models as M
from shared.ui2_contract import text as T
from shared.ui2_contract.models import (
    CapabilityState, CardVM, FieldState, FieldVM, FreshnessInfo, JudgementState, PageVM,
)
from shared.ui2_contract.pages import PAGE_IDS, SCENARIO_IDS
from shared.ui2_contract.tones import ChipTone
from src.services.ui2 import market_vm, vm_common
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.scenarios import fake_canonical
from src.ui2.components import html as H

ROOT = pathlib.Path(__file__).resolve().parents[1]

L0_DIR = ROOT / "shared" / "ui2_contract"
L3_DIR = ROOT / "src" / "services" / "ui2"
L5_DIR = ROOT / "src" / "ui2"
L6_FILE = ROOT / "app_ui2.py"


def _py(d: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in d.rglob("*.py") if "__pycache__" not in p.parts)


VM_FILES = _py(L0_DIR) + _py(L3_DIR)             # 純度範圍（L0 契約＋L3 VM 層）
UI_FILES = _py(L5_DIR) + [L6_FILE]                # L5＋L6
ALL_FILES = VM_FILES + UI_FILES
#: NUI2-REAL-FEED（2026-11-03）：New UI2 唯一允許呼叫既有 canonical service 的 feed 檔（**具名列舉**，⛔ 目錄／萬用字元）。
#: 這些檔不走 G2（VM 純度），改走更窄的 G2F（見下）；G2 的規則與允許清單 `_G2_ALLOWED_PROJECT` **一字未改**。
FEED_FILES = (L3_DIR / "real_feed.py",)
PURE_VM_FILES = [p for p in VM_FILES if p not in FEED_FILES]


# ── 共用 AST 工具 ────────────────────────────────────────────────────
def _mod_match(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _imports(tree: ast.AST) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out += [(n.lineno, a.name) for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            out.append((n.lineno, n.module))
            out += [(n.lineno, f"{n.module}.{a.name}") for a in n.names]
    return out


def _relative_imports(tree: ast.AST) -> list[str]:
    """`from .x import y`（level>0）會繞過 `_imports()`（只收 level 0）⇒ 一律違規（QA 2026-11-03；加性強化）。"""
    return [f"L{n.lineno}: 禁止相對 import（level={n.level}）{'.' * n.level}{n.module or ''}"
            for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level > 0]


def _is_session_state(node: ast.AST) -> bool:
    return ((isinstance(node, ast.Attribute) and node.attr == "session_state")
            or (isinstance(node, ast.Name) and node.id == "session_state"))


# ════════════════════════════════════════════════════════════════════
# G2 VM 純度（L0 契約＋L3 VM 層）
# ════════════════════════════════════════════════════════════════════
_G2_BANNED_IMPORTS = (
    "streamlit", "requests", "yfinance", "FinMind", "proxy_helper",
    "src.data", "src.compute", "src.ui", "src.ui_v2", "src.ui2", "app", "app_ui2",
    "time", "random", "os", "pathlib", "subprocess", "socket", "urllib", "http",
    "sqlite3", "shutil", "tempfile",
)
#: VM／契約層允許 import 的專案內模組（其餘專案內模組一律違規；日後真 feed 需明確擴充並走審查）。
_G2_ALLOWED_PROJECT = ("shared", "src.services.ui2")
_CLOCK_CALLS = {("datetime", "now"), ("datetime", "utcnow"), ("datetime", "today"),
                ("date", "today"), ("time", "time")}


def check_vm_purity(source: str) -> list[str]:
    tree = ast.parse(source)
    bad: list[str] = list(_relative_imports(tree))      # NUI2-REAL-FEED QA（加性）：相對 import 一律違規
    for ln, mod in _imports(tree):
        if any(_mod_match(mod, b) for b in _G2_BANNED_IMPORTS):
            bad.append(f"L{ln}: 禁止 import {mod}")
        elif (mod.split(".")[0] in {"src", "shared", "scripts"}
              and not any(_mod_match(mod, a) for a in _G2_ALLOWED_PROJECT)):
            bad.append(f"L{ln}: 專案內 import {mod} 不在 VM 層允許清單 {_G2_ALLOWED_PROJECT}")
    for n in ast.walk(tree):
        if _is_session_state(n):
            bad.append(f"L{n.lineno}: VM 層不得存取 session_state")
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == "open":
                bad.append(f"L{n.lineno}: VM 層不得 open()（I/O）")
            if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                    and (f.value.id, f.attr) in _CLOCK_CALLS):
                bad.append(f"L{n.lineno}: VM 層不得讀時鐘（時間由參數傳入）")
    return bad


@pytest.mark.parametrize("path", PURE_VM_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_g2_vm_layer_is_pure(path):
    assert check_vm_purity(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("injected", [
    "import streamlit as st\n",
    "from src.data.core import data_loader\n",
    "import requests\n",
    "from src.compute.etf import dividend_station\n",
    "from src.ui.views import page_market\n",
    "from src.services import market_strategy\n",        # 非 ui2 的 L3 service：VM 層只吃 canonical dict
    "import time\n",
    "x = st.session_state['a']\n",
    "x = session_state\n",
    "from datetime import datetime\nx = datetime.now()\n",
    "x = open('f.txt')\n",
    "from .real_feed import read_real_snapshot\n",           # 相對 import 繞過（QA 2026-11-03）
    "from ..allocation_service import get_allocation\n",
])
def test_g2_guard_has_teeth(injected):
    """mutation：對乾淨檔注入單一違規，檢查器必須回報（否則守衛是裝飾品）。"""
    clean = (L3_DIR / "market_vm.py").read_text(encoding="utf-8")
    assert check_vm_purity(clean) == []
    assert check_vm_purity(injected + clean), f"檢查器沒抓到：{injected!r}"


# ════════════════════════════════════════════════════════════════════
# G2F Real feed 邊界（NUI2-REAL-FEED A2，2026-11-03；加性：G2 一字未改，只作用於具名 FEED_FILES）
#   feed＝New UI2 唯一做 I/O 的檔：只准 import 具名 canonical L3 白名單＋shared＋src.services.ui2；
#   ⛔ streamlit／src.data／src.compute／Legacy UI／網路／檔案／時鐘、⛔ session_state、⛔ producer 與寫入呼叫。
# ════════════════════════════════════════════════════════════════════
#: feed 的**精確** import 白名單（module → 允許的名稱；None＝該模組任何名稱）。只准 `from X import a, b`；
#: ⛔ `import X`（整包取得後可任意取屬性）、⛔ `from X import *`、⛔ 相對 import。擴充須明確、經審查並同步 mapping。
#: （QA 2026-11-03 強化：原「模組前綴白名單」可 `from allocation_service import st／_invalidate／get_allocation_sleeves`。）
G2F_IMPORT_ALLOWLIST: dict[str, frozenset[str] | None] = {
    "__future__": frozenset({"annotations"}),
    "src.services.market_twii_view_service": frozenset({"get_twii_trend_view"}),
    "src.services.allocation_service": frozenset({"get_macro_regime"}),
    "src.services.ui2.real_canonical": None,
    # 明列的 shared 模組：目前無（需要時逐一具名加入）。
}
#: feed 內任何位置（Name／Attribute／import 名稱）都不得出現的識別字：動態取用、反射、檔案／序列化、producer、寫入。
_G2F_BANNED_NAMES = {
    "importlib", "__import__", "exec", "eval", "compile", "getattr", "setattr", "delattr", "vars", "globals",
    "locals", "builtins", "__builtins__", "__dict__", "open", "pandas", "pd", "json", "pickle", "os", "sys",
    "subprocess", "socket", "requests", "pathlib", "Path", "datetime", "time", "st", "streamlit", "session_state",
    "refresh_macro_now", "get_allocation", "get_allocation_sleeves", "compute_and_lock_risk_cap",
    "compute_and_store_warroom_summary", "reset_allocation_registry", "get_account", "build_login_url",
    "get_holdings", "get_sheet_view", "get_sheet_contents", "logout", "gemini_call", "post_gemini",
    "build_ai_summary", "run_agent", "run_headless_refresh", "_invalidate",
}
_G2F_BANNED_PREFIXES = ("register_", "apply_", "clear_", "save_", "write_", "delete_", "bind_", "select_",
                        "set_", "add_to_", "create_", "rename_", "risk_cap_history_", "lock_", "execute_")
#: 屬性名：時鐘、pandas／檔案讀寫。
_G2F_BANNED_ATTRS = {"now", "utcnow", "today", "write_text", "write_bytes", "read_text", "read_bytes", "mkdir",
                     "unlink", "to_csv", "to_parquet", "to_json", "to_pickle", "to_sql", "to_excel",
                     "read_csv", "read_parquet", "read_json", "read_pickle", "read_sql", "read_excel"}


def _g2f_name_banned(name: str) -> bool:
    return (name in _G2F_BANNED_NAMES or name.endswith("_apply")
            or any(name.startswith(p) for p in _G2F_BANNED_PREFIXES))


def check_feed_boundary(source: str) -> list[str]:
    tree = ast.parse(source)
    bad: list[str] = list(_relative_imports(tree))
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            bad += [f"L{n.lineno}: feed 禁止 `import {a.name}`（只准具名 from-import）" for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.level == 0:
            allowed = G2F_IMPORT_ALLOWLIST.get(n.module or "", False)
            if allowed is False:
                bad.append(f"L{n.lineno}: feed import 模組 {n.module} 不在精確白名單")
                continue
            for a in n.names:
                if a.name == "*":
                    bad.append(f"L{n.lineno}: feed 禁止 `from {n.module} import *`")
                elif allowed is not None and a.name not in allowed:
                    bad.append(f"L{n.lineno}: feed 不得自 {n.module} 取 {a.name}（只准 {sorted(allowed)}）")
                if _g2f_name_banned(a.name) or (a.asname and _g2f_name_banned(a.asname)):
                    bad.append(f"L{n.lineno}: feed 禁止匯入名稱 {a.name}")
        elif isinstance(n, ast.Name) and n.id in _G2F_BANNED_NAMES:
            bad.append(f"L{n.lineno}: feed 禁止使用 {n.id}")
        elif isinstance(n, ast.Attribute):
            if n.attr in _G2F_BANNED_ATTRS or n.attr in _G2F_BANNED_NAMES:
                bad.append(f"L{n.lineno}: feed 禁止屬性 .{n.attr}")
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            if _g2f_name_banned(name):
                bad.append(f"L{n.lineno}: feed 禁止呼叫 {name}()")
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in (
                "session_state", "get_allocation", "refresh_macro_now", "__import__"):
            bad.append(f"L{n.lineno}: feed 出現可供反射取用的字面 {n.value!r}")
    return bad


def test_g2f_feed_files_are_exactly_the_named_one():
    """具名列舉（⛔ 目錄層級放寬）：只有 real_feed.py 走 G2F，其餘 L0／L3 UI2 檔全部仍走 G2。"""
    assert [p.relative_to(ROOT).as_posix() for p in FEED_FILES] == ["src/services/ui2/real_feed.py"]
    assert all(p.exists() for p in FEED_FILES)
    assert set(PURE_VM_FILES) | set(FEED_FILES) == set(VM_FILES)
    assert not set(PURE_VM_FILES) & set(FEED_FILES)
    assert check_vm_purity((FEED_FILES[0]).read_text(encoding="utf-8")), "feed 檔若能過 G2 就不該被豁免"


@pytest.mark.parametrize("path", FEED_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_g2f_feed_respects_boundary(path):
    assert check_feed_boundary(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("injected", [
    "import streamlit as st\n",
    "from src.data.macro.macro_cache_reader import load_twii_close\n",
    "from src.compute.macro import macro_helpers\n",
    "from src.services import market_strategy\n",
    "from src.services.macro_refresh_service import refresh_macro_now\n",
    "from src.ui.views import page_today\n",
    "import requests\n", "import socket\n", "import os\n",
    "refresh_macro_now()\n", "get_allocation()\n", "register_cap('x', 1)\n", "apply_vix_veto(30)\n",
    "compute_and_lock_risk_cap({})\n", "risk_cap_history_read()\n", "get_account()\n",
    "build_login_url()\n", "get_holdings()\n", "save_portfolio({})\n", "bind_sheet('x')\n",
    "x = st.session_state['warroom_summary']\n", "x = open('macro_state.json', 'w')\n",
    "from datetime import datetime\nx = datetime.now()\n",
    "from src.services.allocation_service import get_allocation\n",
    # ── QA 2026-11-03 列出的繞過（精確白名單＋反射禁令）──
    "import importlib\nm = importlib.import_module('src.services.allocation_service')\n",
    "m = __import__('src.services.allocation_service')\n",
    "from ..allocation_service import get_allocation\n",
    "from . import real_canonical\n",
    "from src.services.allocation_service import st\n",
    "from src.services.allocation_service import _invalidate\n",
    "from src.services.allocation_service import get_allocation_sleeves\n",
    "from src.services.allocation_service import get_breadth_proxy_presence\n",   # 精確名稱白名單本身的牙
    "from src.services.market_twii_view_service import TwiiTrendView\n",
    "f = getattr(obj, 'x')\n",                                                   # getattr 禁令本身的牙
    "from src.services.allocation_service import get_macro_regime as g\nimport src.services.allocation_service as a\n",
    "from src.services import allocation_service\nf = getattr(allocation_service, 'get_' + 'allocation')\n",
    "x = vars()['get_macro_regime']\n", "x = globals()['open']\n", "exec('x=1')\n", "eval('1')\n",
    "import builtins\nbuiltins.open('x', 'w')\n",
    "import pandas as pd\npd.read_parquet('data_cache/x.parquet')\n",
    "df.to_parquet('data_cache/x.parquet')\n",
    "import json\njson.dump({}, fh)\n",
    "from datetime import datetime as D\nx = D.now()\n",
    "from src.services.market_twii_view_service import *\n",
    "from shared.secret_scrub import scrub_secrets\n",
    "p.write_text('x')\n",
])
def test_g2f_guard_has_teeth(injected):
    clean = FEED_FILES[0].read_text(encoding="utf-8")
    assert check_feed_boundary(clean) == []
    assert check_feed_boundary(injected + clean), f"G2F 沒抓到：{injected!r}"


@pytest.mark.parametrize("path", PURE_VM_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_g2f_pure_vm_files_do_not_import_the_feed(path):
    """依賴方向：feed → 純轉換（⛔ 純 VM／契約檔反向 import feed，否則經由 G2 允許的 `src.services.ui2` 前綴偷渡 I/O）。"""
    feed_mods = {"src.services.ui2." + p.stem for p in FEED_FILES}
    for ln, mod in _imports(ast.parse(path.read_text(encoding="utf-8"))):
        assert not any(_mod_match(mod, fm) for fm in feed_mods), f"{path.name}:L{ln} import {mod}"


def test_g2f_feed_import_guard_has_teeth():
    bad = "from src.services.ui2.real_feed import read_real_snapshot\n"
    feed_mods = {"src.services.ui2." + p.stem for p in FEED_FILES}
    assert any(_mod_match(m, fm) for _, m in _imports(ast.parse(bad)) for fm in feed_mods)


# ════════════════════════════════════════════════════════════════════
# G4 UI2 獨立性（四個範圍都不得 import Legacy UI / app）
# ════════════════════════════════════════════════════════════════════
_G4_BANNED = ("src.ui", "app", "app_ui2")        # `src.ui` 含 .views/.tabs/.etf/.pages/.render；不含 `src.ui2`
#: Legacy New UI `src.ui_v2` 只走明列允許清單（Gate §6.2(c)：`tokens`／`components` WRAP）。
G4_UI_V2_ALLOWLIST = ("src.ui_v2.tokens", "src.ui_v2.components")


def check_independence(source: str, *, self_pkg: str = "") -> list[str]:
    bad: list[str] = []
    for ln, mod in _imports(ast.parse(source)):
        if any(_mod_match(mod, b) for b in _G4_BANNED):
            if self_pkg and _mod_match(mod, self_pkg):
                continue
            bad.append(f"L{ln}: 禁止 import Legacy/production 入口 {mod}")
        elif _mod_match(mod, "src.ui_v2") and not any(
                _mod_match(mod, a) or _mod_match(a, mod) for a in G4_UI_V2_ALLOWLIST):
            bad.append(f"L{ln}: src.ui_v2 只允許 {G4_UI_V2_ALLOWLIST}，收到 {mod}")
    return bad


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_g4_ui2_does_not_import_legacy(path):
    assert check_independence(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("injected", [
    "from src.ui.views import page_market\n", "from src.ui.tabs import tab_macro\n",
    "import src.ui.etf.etf_tab_smart\n", "from src.ui.pages import oauth_state\n",
    "from src.ui.render import station_cards\n", "import app\n", "from app import main\n",
    "from src.ui_v2 import compact\n", "from src.ui_v2.markup import card_html\n",
])
def test_g4_guard_has_teeth(injected):
    clean = (L5_DIR / "views" / "market.py").read_text(encoding="utf-8")
    assert check_independence(clean) == []
    assert check_independence(injected + clean)


def test_g4_ui_v2_allowlist_passes_only_listed():
    assert check_independence("from src.ui_v2 import tokens\n") == []
    assert check_independence("from src.ui_v2.components import x\n") == []


def test_g4_src_ui2_is_not_confused_with_src_ui():
    """`src.ui2` 不得被 `src.ui` 前綴誤傷（也不得被誤放過：兩者是不同套件）。"""
    assert not _mod_match("src.ui2", "src.ui")
    assert _mod_match("src.ui.views", "src.ui")


def test_g4b_l5_only_reads_services_ui2():
    """L5 取數唯一入口：只准 `src.services.ui2`（其餘 `src.services.*`、`src.data.*` 一律不准）。"""
    for p in _py(L5_DIR) + [L6_FILE]:
        for ln, mod in _imports(ast.parse(p.read_text(encoding="utf-8"))):
            if _mod_match(mod, "src.services"):
                assert _mod_match(mod, "src.services.ui2"), f"{p.name}:L{ln} {mod}"
            assert not _mod_match(mod, "src.data"), f"{p.name}:L{ln} {mod}"
            assert not _mod_match(mod, "src.compute"), f"{p.name}:L{ln} {mod}"


# ════════════════════════════════════════════════════════════════════
# G9 Producer 禁令＋session key 紀律（L5＋L6）
# ════════════════════════════════════════════════════════════════════
_PRODUCER_EXACT = {"refresh_macro_now", "gemini_call", "post_gemini",
                   "build_ai_summary", "run_agent"}


def _const_str_map(tree: ast.AST) -> dict[str, str]:
    m: dict[str, str] = {}
    for n in getattr(tree, "body", []):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name)
                and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)):
            m[n.targets[0].id] = n.value.value
    return m


def _key_of(node: ast.AST, consts: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


_SS_ALLOWED_METHODS = {"get", "pop", "setdefault"}


def _session_state_misuse(tree: ast.AST, consts: dict[str, str]) -> list[str]:
    """G9 強化（QA 2026-11-03；加性）：`session_state` 只准出現在下列位置，其餘一律違規——
    `ss[ui2_常數]`（Subscript）／`ui2_常數 in ss`（Compare In／NotIn）／`ss.get|pop|setdefault(ui2_常數…)`／`ss.ui2_*`。
    （例：`.to_dict()`、`.items()`、`.keys()`、`.__setitem__`、當 list／tuple 元素、預設參數、傳參、取別名、
    `getattr(st, 'session_state')`、`from streamlit import session_state` 皆違規。）key 是否為 `ui2_` 由既有規則另驗。"""
    parent: dict[ast.AST, ast.AST] = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parent[c] = n
    bad: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                if a.name.rsplit(".", 1)[-1] == "session_state":
                    bad.append(f"L{n.lineno}: 禁止 import session_state（{a.name}）")
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"getattr", "setattr", "delattr"}
                and any(isinstance(x, ast.Constant) and x.value == "session_state" for x in n.args)):
            bad.append(f"L{n.lineno}: 禁止以 {n.func.id}() 取用 session_state")
        if not _is_session_state(n):
            continue
        p = parent.get(n)
        ok = False
        if isinstance(p, ast.Subscript) and p.value is n:
            ok = True
        elif isinstance(p, ast.Compare) and n in p.comparators and all(
                isinstance(o, (ast.In, ast.NotIn)) for o in p.ops):
            ok = True
        elif isinstance(p, ast.Attribute) and p.value is n:
            if p.attr.startswith("ui2_"):
                ok = True
            elif p.attr in _SS_ALLOWED_METHODS:
                gp = parent.get(p)
                ok = isinstance(gp, ast.Call) and gp.func is p and bool(gp.args)
            elif p.attr in {"update", "clear"}:
                ok = True        # 既有規則另報（保留原訊息）
        if not ok:
            bad.append(f"L{n.lineno}: session_state 不允許的用法（{ast.unparse(p) if p is not None else ''}）")
    return bad


def check_not_a_producer(source: str) -> list[str]:
    tree = ast.parse(source)
    consts = _const_str_map(tree)
    bad: list[str] = list(_relative_imports(tree)) + _session_state_misuse(tree, consts)

    def need_ui2(node: ast.AST, what: str) -> None:
        k = _key_of(node, consts)
        if k is None or not k.startswith("ui2_"):
            bad.append(f"L{node.lineno}: {what} 的 key 不是 `ui2_` 前綴常數（{ast.unparse(node)}）")

    for ln, mod in _imports(tree):
        last = mod.rsplit(".", 1)[-1]
        if last.endswith("_apply") or last in _PRODUCER_EXACT:
            bad.append(f"L{ln}: 禁止 import producer {mod}")
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            if name.endswith("_apply") or name in _PRODUCER_EXACT:
                bad.append(f"L{n.lineno}: 禁止呼叫 producer {name}()")
            for kw in n.keywords:
                if kw.arg == "key":
                    need_ui2(kw.value, "widget key")
            if isinstance(f, ast.Attribute) and _is_session_state(f.value):
                if f.attr in {"update", "clear"}:
                    bad.append(f"L{n.lineno}: session_state.{f.attr}() 無法驗證 key 前綴")
                elif f.attr in {"get", "pop", "setdefault"} and n.args:
                    need_ui2(n.args[0], f"session_state.{f.attr}")
        elif isinstance(n, ast.Subscript) and _is_session_state(n.value):
            need_ui2(n.slice, "session_state[...]")
        # NUI2-REAL-FEED G9 補洞（加性）：整包 session_state 傳出去（`dict(st.session_state)`、`fn(st.session_state)`、
        # `**st.session_state`）或另取別名（`s = st.session_state`）都會繞過上面的逐 key 前綴檢查 → 一律禁止。
        if isinstance(n, ast.Call):
            for a in [*n.args, *(k.value for k in n.keywords)]:
                inner = a.value if isinstance(a, ast.Starred) else a
                if _is_session_state(inner):
                    bad.append(f"L{n.lineno}: 整包 session_state 傳給 {ast.unparse(n.func)}()（無法驗證 key 前綴）")
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and n.value is not None and _is_session_state(n.value):
            bad.append(f"L{n.lineno}: session_state 取別名（無法驗證 key 前綴）")
        elif isinstance(n, ast.Compare) and any(_is_session_state(c) for c in n.comparators):
            need_ui2(n.left, "`in session_state`")
        elif isinstance(n, ast.Attribute) and _is_session_state(n.value) and isinstance(
                n.ctx, (ast.Store, ast.Del)):
            if not n.attr.startswith("ui2_"):
                bad.append(f"L{n.lineno}: session_state.{n.attr} 寫入非 ui2_ 前綴")
    return bad


@pytest.mark.parametrize("path", UI_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_g9_ui2_is_not_a_producer(path):
    assert check_not_a_producer(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("injected", [
    "from src.services.risk_cap_apply import apply_risk_cap\n",
    "from src.services import warroom_apply\nwarroom_apply.run()\n",
    "refresh_macro_now()\n", "gemini_call('x')\n", "post_gemini('x')\n",
    "build_ai_summary(1, 2)\n", "run_agent()\n",
    "import streamlit as st\nst.session_state['macro_state'] = 1\n",
    "import streamlit as st\nst.session_state.regime = 1\n",
    "import streamlit as st\nst.session_state.update({'a': 1})\n",
    "import streamlit as st\nx = st.session_state.get('portfolio')\n",
    "import streamlit as st\nst.radio('x', [1], key='page')\n",
    "import streamlit as st\nk = 'dyn' + 'x'\nst.session_state[k] = 1\n",
    "import streamlit as st\nif 'macro' in st.session_state: pass\n",
    # NUI2-REAL-FEED G9 補洞（整包傳遞／別名）
    "import streamlit as st\nx = dict(st.session_state)\n",
    "import streamlit as st\nread_real_snapshot(st.session_state)\n",
    "import streamlit as st\nf(state=st.session_state)\n",
    "import streamlit as st\nf(**st.session_state)\n",
    "import streamlit as st\ns = st.session_state\n",
    # QA 2026-11-03 G9 強化
    "import streamlit as st\nd = st.session_state.to_dict()\n",
    "import streamlit as st\nfor k, v in st.session_state.items(): pass\n",
    "import streamlit as st\nks = list(st.session_state.keys())\n",
    "import streamlit as st\nst.session_state.__setitem__('ui2_page', 1)\n",
    "import streamlit as st\nxs = [st.session_state]\n",
    "import streamlit as st\nxs = (1, st.session_state)\n",
    "import streamlit as st\ndef f(s=st.session_state): pass\n",
    "import streamlit as st\ns = getattr(st, 'session_state')\n",
    "from streamlit import session_state as ss\nss['x'] = 1\n",
    "import streamlit as st\nx = st.session_state.get\n",
    "from .views import VIEWS\n",
])
def test_g9_guard_has_teeth(injected):
    clean = (L5_DIR / "shell" / "app.py").read_text(encoding="utf-8")
    assert check_not_a_producer(clean) == []
    assert check_not_a_producer(clean + "\n" + injected), f"沒抓到：{injected!r}"


def test_g9_ui2_prefixed_state_is_allowed():
    ok = ("import streamlit as st\nK = 'ui2_page'\nst.session_state[K] = 'a'\n"
          "st.radio('x', [1], key=K)\nif K not in st.session_state: pass\n")
    assert check_not_a_producer(ok) == []


# ════════════════════════════════════════════════════════════════════
# Chip 語意：⛔ 不用警告族（guard_chip）承載中性資訊
# ════════════════════════════════════════════════════════════════════
def check_no_guard_chip(source: str) -> list[str]:
    bad = []
    for n in ast.walk(ast.parse(source)):
        names = []
        if isinstance(n, ast.Name):
            names.append(n.id)
        elif isinstance(n, ast.Attribute):
            names.append(n.attr)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            names += [a.name.rsplit(".", 1)[-1] for a in n.names]
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            names.append(n.name)
        if "guard_chip" in names:
            bad.append(f"L{n.lineno}: 使用 guard_chip")
    return bad


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_guard_chip_in_ui2(path):
    assert check_no_guard_chip(path.read_text(encoding="utf-8")) == []


def test_no_guard_chip_guard_has_teeth():
    assert check_no_guard_chip("from src.ui_v2.compact import guard_chip\nguard_chip('半導體')\n")
    assert check_no_guard_chip("x = compact.guard_chip('3 項')\n")


@pytest.mark.parametrize("what", ["股票", "半導體", "3 項", "PE（TTM）", "來源 TWSE"])
def test_neutral_info_goes_through_neutral_tone(what):
    """類型／產業／計數／估值口徑／資料來源 → Neutral/Info；絕不落在 warning/danger class。"""
    out = H.neutral_chip_html(what)
    assert "ui2-chip--neutral" in out
    assert "ui2-chip--warning" not in out and "ui2-chip--danger" not in out


def test_source_chip_in_freshness_is_neutral():
    out = H.freshness_html(FreshnessInfo(as_of="FAKE-ASOF", source="FAKE·scenario"))
    assert "ui2-chip--neutral" in out and "warning" not in out and "danger" not in out


def test_chip_tone_has_exactly_four_families():
    assert {t.value for t in ChipTone} == {"positive", "warning", "danger", "neutral_info"}


def test_red_is_only_for_unavailable_never_for_unloaded():
    """未載入＝灰、系統真出錯＝紅（CLAUDE.md §1.A-4）。"""
    assert H.STATE_TONE[FieldState.UNAVAILABLE] is ChipTone.DANGER
    # DEC-124 語意修正：NOT_PROVIDED 改屬 capability 軸（CAPABILITY_TONE），新增判定結果 UNDETERMINABLE；皆灰
    for s in (FieldState.NOT_EVALUATED, FieldState.MISSING, FieldState.OK, JudgementState.UNDETERMINABLE):
        assert H.STATE_TONE[s] is ChipTone.NEUTRAL_INFO
    assert H.CAPABILITY_TONE[CapabilityState.NOT_PROVIDED] is ChipTone.NEUTRAL_INFO
    assert H.STATE_TONE[FieldState.STALE] is ChipTone.WARNING
    for p in PAGE_IDS:
        cold = get_preview_page_vm(p, "cold")
        for f in _all_fields(cold):
            assert "ui2-chip--danger" not in H.status_chip_html(f), f"{p}: 冷啟動出現紅色 {f.label}"


# ════════════════════════════════════════════════════════════════════
# G5 四態（常數唯一性＋欄位不變量＋property-style 掃描）
# ════════════════════════════════════════════════════════════════════
def _all_fields(vm: PageVM) -> list[FieldVM]:
    fs = vm.context.first_screen
    out = [fs.current_state, fs.action_needed, fs.next_step, *fs.context_rows]
    out += [c.field for c in vm.context.cards]
    for s in vm.context.sections:
        out += list(s.fields)
    # Batch 3（只增加掃描範圍，⛔ 縮小）：今日結論／今日主要風險／標的查一檔 FAKE 結果／帳戶欄位
    out += [f for f in (fs.conclusion, vm.context.main_risk) if f is not None]
    t = vm.context.target
    if t is not None:
        out += [t.search.name_search, t.lookup.summary, *t.lookup.snapshot]
        for s in t.lookup.sections:
            out += list(s.fields)
    return out


def test_state_text_constants_are_unique():
    consts = {k: v for k, v in vars(T).items() if k.startswith("TEXT_") and isinstance(v, str)}
    assert len(set(consts.values())) == len(consts), "兩個 TEXT_* 常數字樣重複"


def _all_prefix_tables() -> dict[str, tuple[str, ...]]:
    """資料語意＋判定結果＋capability 三張表合併（只供「互斥」掃描；⛔ 用來查表）。"""
    return {**T.ALLOWED_STATUS_PREFIXES, **T.JUDGEMENT_STATUS_PREFIXES, **T.CAPABILITY_STATUS_PREFIXES}


def test_four_states_never_share_a_status_prefix():
    seen: dict[str, str] = {}
    # DEC-124：掃描範圍＝三張表（原為單一表；範圍不縮小，NOT_PROVIDED／無法判定仍在掃描內）
    for state, prefixes in _all_prefix_tables().items():
        for p in prefixes:
            assert p not in seen, f"字樣 {p!r} 同時屬於 {seen[p]} 與 {state}"
            seen[p] = state
    # Missing 與 Not evaluated 同用 ⬜，必須以文字區分（Freeze §5.1）
    assert all("資料未" in t or "資料日" in t for t in T.ALLOWED_STATUS_PREFIXES["missing"])
    assert not any("資料未取得" in t for t in T.ALLOWED_STATUS_PREFIXES["not_evaluated"])


def test_every_state_is_covered_by_the_enum():
    assert {s.value for s in FieldState} == set(T.ALLOWED_STATUS_PREFIXES)


@pytest.mark.parametrize("state,value", [
    (FieldState.MISSING, "0"), (FieldState.UNAVAILABLE, "1.23"),
    (FieldState.NOT_EVALUATED, "HOLD"), (JudgementState.UNDETERMINABLE, "safe"),
])
def test_non_value_states_reject_a_value(state, value):
    """missing ≠ 0；missing ≠ HOLD；unavailable ≠ safe；not evaluated ≠ safe；無法判定 ≠ safe。

    DEC-124 語意修正：原 `(FieldState.NOT_PROVIDED, "safe")` 列改由下一個測試（capability 軸）承接，
    並新增判定結果 UNDETERMINABLE 列；斷言（帶值必 raise）未放寬。
    """
    status = M.status_prefixes_for(state)[0]
    with pytest.raises(ValueError):
        FieldVM("x", state, value, status)


@pytest.mark.parametrize("value,state", [("safe", None), (None, FieldState.OK), ("0", FieldState.MISSING),
                                         (None, FieldState.NOT_EVALUATED)])
def test_capability_marker_rejects_value_and_any_data_state(value, state):
    """`⬜ 尚未提供` 與資料語意正交：帶值或帶任何資料語意態 → raise（⛔ 偽裝成資料態）。"""
    with pytest.raises(ValueError):
        FieldVM("x", state, value, T.TEXT_NOT_PROVIDED, capability=CapabilityState.NOT_PROVIDED)


def test_status_text_must_belong_to_its_own_state():
    with pytest.raises(ValueError):
        FieldVM("x", FieldState.MISSING, None, T.TEXT_NOT_EVALUATED)       # 混用
    with pytest.raises(ValueError):
        FieldVM("x", FieldState.UNAVAILABLE, None, T.TEXT_MISSING_NOT_FETCHED)
    with pytest.raises(ValueError):
        FieldVM("x", FieldState.OK, "1", T.TEXT_STALE_UNKNOWN)             # OK 不帶狀態字樣


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_all_preview_vms_obey_state_invariants(page, scenario):
    vm = get_preview_page_vm(page, scenario)
    for f in _all_fields(vm):
        if f.state not in (FieldState.OK, FieldState.STALE):
            assert f.value_text is None, f"{page}/{scenario}/{f.label}"
            assert f.status_text, f"{page}/{scenario}/{f.label}"
        prefixes = f.allowed_status_prefixes()          # DEC-124：依欄位所屬語意軸查表
        assert f.state is FieldState.OK or f.status_text.startswith(prefixes)


def check_missing_input_is_never_ok(build_field) -> list[str]:
    """property：任一輸入缺（value=None 且無明示態）→ 該欄非 OK、且無 value。"""
    bad = []
    for kind in (None, "not_fetched", "not_ready"):
        f = build_field({"label": "x", "value": None, "missing_kind": kind})
        if f.state is FieldState.OK or f.value_text is not None:
            bad.append(f"missing_kind={kind}: {f.state}")
    return bad


def test_g5_missing_input_is_never_ok():
    assert check_missing_input_is_never_ok(vm_common.field_from_spec) == []


def test_g5_guard_has_teeth():
    def zero_filler(spec):      # 違憲 builder：缺值補 "0"
        return FieldVM(spec["label"], FieldState.OK, "0", None)
    assert check_missing_input_is_never_ok(zero_filler)


def test_unavailable_spec_drops_its_value():
    f = vm_common.field_from_spec({"label": "x", "value": "9.9", "state": "unavailable"})
    assert f.state is FieldState.UNAVAILABLE and f.value_text is None


def test_missing_asof_is_marked_not_estimated():
    html_ = H.freshness_html(FreshnessInfo(as_of=None, source=None))
    assert T.TEXT_ASOF_MISSING in html_


# ════════════════════════════════════════════════════════════════════
# G3 Presentation Slice ≠ Decision Context
# ════════════════════════════════════════════════════════════════════
def check_slice_independence(build, tops=(None, 0, 2, 5, 10, 99)) -> list[str]:
    base = build(None).context
    bad = [f"top_n={t}: context 隨切片改變" for t in tops if build(t).context != base]
    return bad


def test_g3_context_independent_of_top_n():
    canon = fake_canonical("p4_market", "loaded")
    assert check_slice_independence(lambda t: market_vm.build_market_page_vm(canon, top_n=t)) == []
    assert len(market_vm.build_market_page_vm(canon, top_n=2).slice.visible_card_ids) == 2
    assert len(market_vm.build_market_page_vm(canon, top_n=None).context.cards) == 6


def test_g3_guard_has_teeth():
    canon = fake_canonical("p4_market", "loaded")

    def leaky(top_n):            # 違憲 builder：讓 top_n 截掉 context 的卡
        vm = market_vm.build_market_page_vm(canon, top_n=top_n)
        if top_n is None:
            return vm
        return replace(vm, context=replace(vm.context, cards=vm.context.cards[:top_n]))
    assert check_slice_independence(leaky)


# ════════════════════════════════════════════════════════════════════
# Single Action Authority／Risk Cap／FAKE 標示／術語
# ════════════════════════════════════════════════════════════════════
_FORBIDDEN_ACTION_WORDS = ("減碼 1/2", "全出", "加碼", "買進", "賣出", "今日無需調整",
                           "今日需處理", "強烈出場", "建議減碼")
_FORBIDDEN_TERMS = ("訊號可信度", "信心度", "Portfolio Risk Cap", "已啟用上限")


def _texts(vm: PageVM) -> list[str]:
    out = [vm.title, vm.banner_text or ""]
    for f in _all_fields(vm):
        out += [f.label, f.value_text or "", f.status_text or "", f.detail or ""]
    out += [c.title for c in vm.context.cards]
    out += [s.title for s in vm.context.sections]
    fs = vm.context.first_screen
    out += [fs.primary_cta.label, fs.primary_cta.disabled_reason or ""]
    return out


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_vm_creates_no_actions_and_no_forbidden_terms(page, scenario):
    vm = get_preview_page_vm(page, scenario)
    blob = "\n".join(_texts(vm)).replace(T.TEXT_NOT_PROVIDED_AGGREGATOR, "")
    for w in _FORBIDDEN_ACTION_WORDS + _FORBIDDEN_TERMS:
        assert w not in blob, f"{page}/{scenario}: 出現禁用字樣 {w!r}"
    assert "%" not in "".join(
        f.value_text or "" for f in _all_fields(vm) if "Risk Cap" in f.label), "Risk Cap 不得顯示 %"


@pytest.mark.parametrize("page", ("p4_market", "p4_hold"))
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_action_field_is_aggregator_pending_until_aggregator_exists(page, scenario):
    a = get_preview_page_vm(page, scenario).context.first_screen.action_needed
    # DEC-124 語意修正：「尚未提供」是 capability marker（state 為 None），不是資料語意態
    assert a.capability is CapabilityState.NOT_PROVIDED and a.state is None
    assert a.status_text == T.TEXT_NOT_PROVIDED_AGGREGATOR and a.value_text is None


@pytest.mark.parametrize("page", ("p4_market", "p4_hold"))
def test_canonical_cannot_inject_an_action(page):
    """VM ⛔ 創造／接收動作：canonical 若夾帶 action_needed → raise。"""
    c = fake_canonical(page, "loaded")
    c["action_needed"] = {"label": "是否需要行動", "value": "今日無需調整"}
    with pytest.raises(ValueError):
        vm_common.build_page_vm(c)


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_risk_cap_is_always_undeterminable_and_exposure_is_never_invented(page, scenario):
    vm = get_preview_page_vm(page, scenario)
    rc = [f for f in _all_fields(vm) if f.label == "Risk Cap"]
    for f in rc:
        assert f.status_text == T.TEXT_RISK_CAP_UNDETERMINABLE and f.value_text is None
        # DEC-124 語意修正（客戶 (8)-3）：Risk Cap「⬜ 無法判定」＝Unable to Determine，⛔ 等同 NOT_EVALUATED
        assert f.state is JudgementState.UNDETERMINABLE and f.state != FieldState.NOT_EVALUATED
    for f in _all_fields(vm):
        if f.label == "目前曝險":
            assert f.state is FieldState.MISSING and f.value_text is None
    if page in ("p4_market", "p4_target", "p4_hold"):
        assert rc, f"{page} 缺 Risk Cap 行"


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_everything_is_labelled_fake(page, scenario):
    vm = get_preview_page_vm(page, scenario)
    assert vm.is_fake and vm.banner_text == T.PREVIEW_BANNER_TEXT
    for f in _all_fields(vm):
        if f.freshness.as_of is not None:
            assert f.freshness.as_of.startswith(T.FAKE_SOURCE_PREFIX)
        if f.freshness.source is not None:
            assert f.freshness.source.startswith(T.FAKE_SOURCE_PREFIX)


def test_primary_cta_is_disabled_in_preview():
    for p in PAGE_IDS:
        cta = get_preview_page_vm(p, "loaded").context.first_screen.primary_cta
        assert cta.enabled is False and cta.disabled_reason


def test_only_four_pages():
    assert len(PAGE_IDS) == 4
    assert [p for p in PAGE_IDS] == ["p4_market", "p4_target", "p4_hold", "p4_me"]


def test_scenarios_cover_the_required_six():
    assert set(SCENARIO_IDS) == {"cold", "loaded", "missing", "stale", "unavailable", "not_evaluated"}
    # 每個非 loaded／cold 場景在市場頁至少真的產生對應語意態
    want = {"missing": FieldState.MISSING, "stale": FieldState.STALE,
            "unavailable": FieldState.UNAVAILABLE, "not_evaluated": FieldState.NOT_EVALUATED}
    for sc, st in want.items():
        states = {c.field.state for c in get_preview_page_vm("p4_market", sc).context.cards}
        assert st in states, sc


def test_market_vm_rejects_wrong_page_and_wrong_cards():
    with pytest.raises(ValueError):
        market_vm.build_market_page_vm(fake_canonical("p4_hold", "loaded"))
    c = fake_canonical("p4_market", "loaded")
    c["cards"] = c["cards"][:-1]
    with pytest.raises(ValueError):
        market_vm.build_market_page_vm(c)


def test_vm_dataclasses_are_frozen():
    vm = get_preview_page_vm("p4_market", "loaded")
    with pytest.raises(Exception):
        vm.title = "x"          # type: ignore[misc]
    assert isinstance(vm.context.cards[0], CardVM)


def test_builders_are_deterministic():
    a = get_preview_page_vm("p4_market", "stale")
    b = get_preview_page_vm("p4_market", "stale")
    assert a == b


def test_html_escapes_dynamic_text():
    f = FieldVM("<b>x</b>", FieldState.OK, "<script>1</script>", None)
    out = H.metric_card_html(CardVM("a\"b", "<i>t</i>", f))
    assert "<script>" not in out and "<i>t</i>" not in out and "&lt;script&gt;" in out


# ════════════════════════════════════════════════════════════════════
# DEC-124 Semantic Correction Gate（客戶 2026-11-02 (8)）：三軸語意邊界
#   資料語意（五態）／判定結果（無法判定）／capability（尚未提供，Preview-only）互不混層。
#   每個檢查器都是純函式；對真契約必須 0 違規，對刻意壞掉的輸入必須 >0 違規（teeth）。
# ════════════════════════════════════════════════════════════════════
_CUSTOMER_DATA_STATES = {"ok", "missing", "stale", "unavailable", "not_evaluated"}   # 客戶 (8)-2 逐項


def check_data_semantic_layer(state_enum, data_prefix_table) -> list[str]:
    """正式資料語意只有五個（含 OK）；capability marker／判定結果 ⛔ 混入。"""
    bad: list[str] = []
    values = {s.value for s in state_enum}
    if values != _CUSTOMER_DATA_STATES:
        bad.append(f"資料語意態 {sorted(values)} ≠ 客戶五態 {sorted(_CUSTOMER_DATA_STATES)}")
    if set(data_prefix_table) != _CUSTOMER_DATA_STATES:
        bad.append(f"資料語意字樣表 key {sorted(data_prefix_table)} ≠ 客戶五態")
    capability_or_judgement = (T.CAPABILITY_STATUS_PREFIXES["not_provided"]
                               + T.JUDGEMENT_STATUS_PREFIXES["undeterminable"])
    for state, prefixes in data_prefix_table.items():
        for p in prefixes:
            if any(p.startswith(q) or q.startswith(p) for q in capability_or_judgement):
                bad.append(f"資料語意 {state} 收了非資料語意字樣 {p!r}")
    return bad


def test_dec124_data_semantics_are_exactly_the_five():
    assert check_data_semantic_layer(FieldState, T.ALLOWED_STATUS_PREFIXES) == []
    assert M.DATA_SEMANTIC_STATES == frozenset(FieldState)
    assert "not_provided" not in {s.value for s in FieldState}
    assert "undeterminable" not in {s.value for s in FieldState}


def test_dec124_data_semantic_guard_has_teeth():
    from enum import Enum

    class Sixth(str, Enum):           # 違憲：把 capability marker 塞回資料語意（Batch 1 的形狀）
        OK = "ok"; MISSING = "missing"; STALE = "stale"; UNAVAILABLE = "unavailable"
        NOT_EVALUATED = "not_evaluated"; NOT_PROVIDED = "not_provided"

    class Merged(str, Enum):          # 違憲：把無法判定當成第 6 個資料態
        OK = "ok"; MISSING = "missing"; STALE = "stale"; UNAVAILABLE = "unavailable"
        NOT_EVALUATED = "not_evaluated"; UNDETERMINABLE = "undeterminable"

    assert check_data_semantic_layer(Sixth, T.ALLOWED_STATUS_PREFIXES)
    assert check_data_semantic_layer(Merged, T.ALLOWED_STATUS_PREFIXES)
    leaky = dict(T.ALLOWED_STATUS_PREFIXES, not_provided=(T.TEXT_NOT_PROVIDED,))
    assert check_data_semantic_layer(FieldState, leaky)
    ne_merged = dict(T.ALLOWED_STATUS_PREFIXES,
                     not_evaluated=T.ALLOWED_STATUS_PREFIXES["not_evaluated"] + (T.TEXT_RISK_CAP_UNDETERMINABLE,))
    assert check_data_semantic_layer(FieldState, ne_merged)


def test_dec124_three_axes_are_disjoint_types():
    assert not (set(FieldState) & set(JudgementState))
    assert {s.value for s in JudgementState} == set(T.JUDGEMENT_STATUS_PREFIXES) == {"undeterminable"}
    assert {CapabilityState.NOT_PROVIDED.value} == set(T.CAPABILITY_STATUS_PREFIXES)
    with pytest.raises(TypeError):                       # 原始字串不得冒充語意態
        FieldVM("x", "not_provided", None, T.TEXT_NOT_PROVIDED)
    with pytest.raises(TypeError):
        FieldVM("x", None, None, T.TEXT_NOT_EVALUATED)    # PROVIDED 欄位必須有語意態


# ── Unable to Determine ≠ Not Evaluated（不同值、不同字樣、不同表）──────────
def check_utd_ne_separation(ne_prefixes, utd_prefixes, build_field) -> list[str]:
    bad: list[str] = []
    for p in utd_prefixes:
        for q in ne_prefixes:
            if p == q or p.startswith(q) or q.startswith(p):
                bad.append(f"字樣混用：無法判定 {p!r} ／ 未評估 {q!r}")
    utd = build_field({"label": "x", "value": None, "state": "undeterminable"})
    ne = build_field({"label": "x", "value": None, "state": "not_evaluated"})
    if utd.state is not JudgementState.UNDETERMINABLE:
        bad.append(f"undeterminable 被建成 {utd.state!r}")
    if utd.state == ne.state or utd.state == FieldState.NOT_EVALUATED:
        bad.append("無法判定與未評估同值")
    if utd.status_text == ne.status_text:
        bad.append("無法判定與未評估同字樣")
    if utd.value_text is not None or ne.value_text is not None:
        bad.append("無法判定／未評估帶了 value")
    return bad


def test_dec124_unable_to_determine_is_not_not_evaluated():
    assert check_utd_ne_separation(T.ALLOWED_STATUS_PREFIXES["not_evaluated"],
                                   T.JUDGEMENT_STATUS_PREFIXES["undeterminable"],
                                   vm_common.field_from_spec) == []
    assert JudgementState.UNDETERMINABLE.value != FieldState.NOT_EVALUATED.value


def test_dec124_utd_ne_guard_has_teeth():
    def merging_builder(spec):         # 違憲 builder：把無法判定映射成 NOT_EVALUATED
        if spec.get("state") == "undeterminable":
            return FieldVM(spec["label"], FieldState.NOT_EVALUATED, None, T.TEXT_NOT_EVALUATED)
        return vm_common.field_from_spec(spec)
    assert check_utd_ne_separation(T.ALLOWED_STATUS_PREFIXES["not_evaluated"],
                                   T.JUDGEMENT_STATUS_PREFIXES["undeterminable"], merging_builder)
    merged_ne = T.ALLOWED_STATUS_PREFIXES["not_evaluated"] + (T.TEXT_RISK_CAP_UNDETERMINABLE,)
    assert check_utd_ne_separation(merged_ne, T.JUDGEMENT_STATUS_PREFIXES["undeterminable"],
                                   vm_common.field_from_spec)


def test_dec124_status_text_cannot_cross_axes():
    with pytest.raises(ValueError):    # 無法判定欄位不得掛「尚未評估」字樣
        FieldVM("x", JudgementState.UNDETERMINABLE, None, T.TEXT_NOT_EVALUATED)
    with pytest.raises(ValueError):    # 未評估欄位不得掛「無法判定」字樣
        FieldVM("x", FieldState.NOT_EVALUATED, None, T.TEXT_RISK_CAP_UNDETERMINABLE)
    with pytest.raises(ValueError):    # DEC-074／075 字樣屬無法判定，不得掛在未評估
        FieldVM("x", FieldState.NOT_EVALUATED, None, T.TEXT_NOT_EVALUATED_DATA_SHORT)
    with pytest.raises(ValueError):    # 資料語意欄位不得掛 capability 字樣
        FieldVM("x", FieldState.NOT_EVALUATED, None, T.TEXT_NOT_PROVIDED)
    with pytest.raises(ValueError):    # capability 欄位不得掛無法判定字樣
        FieldVM("x", None, None, T.TEXT_RISK_CAP_UNDETERMINABLE, capability=CapabilityState.NOT_PROVIDED)


def test_dec124_customer_literals_are_verbatim_and_classified():
    """字樣逐字不改（Freeze §0.1.4／DEC-074／075）；只修語意歸類。"""
    assert T.TEXT_RISK_CAP_UNDETERMINABLE == "⬜ 無法判定"
    assert T.TEXT_NOT_EVALUATED_DATA_SHORT == "⬜ 未評估／資料不足"
    assert T.TEXT_NOT_PROVIDED == "⬜ 尚未提供"
    assert T.TEXT_NOT_EVALUATED_DATA_SHORT in T.JUDGEMENT_STATUS_PREFIXES["undeterminable"]
    assert T.TEXT_RISK_CAP_UNDETERMINABLE in T.JUDGEMENT_STATUS_PREFIXES["undeterminable"]
    assert T.TEXT_NOT_EVALUATED_DATA_SHORT not in T.ALLOWED_STATUS_PREFIXES["not_evaluated"]


def test_dec124_scenarios_show_both_ne_and_utd_distinctly():
    vm = get_preview_page_vm("p4_market", "not_evaluated")
    states = {f.state for f in _all_fields(vm)}
    assert FieldState.NOT_EVALUATED in states and JudgementState.UNDETERMINABLE in states
    cur = vm.context.first_screen.current_state
    assert cur.state is JudgementState.UNDETERMINABLE and cur.status_text == T.TEXT_NOT_EVALUATED_DATA_SHORT


def test_unknown_state_hint_is_rejected_not_defaulted_to_ok():
    with pytest.raises(ValueError):
        vm_common.field_from_spec({"label": "x", "value": "1", "state": "safe"})
    with pytest.raises(ValueError):
        vm_common.field_from_spec({"label": "x", "value": "1", "state": "unable_to_determine"})


# ── Risk Cap「⬜ 無法判定」⛔ 渲染／推導成 OK／綠／safe／今日無需調整／可加碼 ────────
_SAFE_READINGS = ("今日無需調整", "無需調整", "可加碼", "加碼", "safe", "Safe", "neutral", "Neutral",
                  "中性", "no action", "無需行動", "安全", "✅")


def _visible_text(html_: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", html_)


def check_undeterminable_never_reads_safe(fields, tone_of, render) -> list[str]:
    bad: list[str] = []
    for f in fields:
        if f.state is FieldState.OK or f.value_text is not None:
            bad.append(f"{f.label}: 無法判定被當成 OK／帶值 {f.value_text!r}")
        if tone_of(f) is ChipTone.POSITIVE:
            bad.append(f"{f.label}: 無法判定給了正向（綠）色調")
        html_ = render(f)
        text = _visible_text(html_)
        if T.TEXT_RISK_CAP_UNDETERMINABLE not in text and T.TEXT_NOT_EVALUATED_DATA_SHORT not in text:
            bad.append(f"{f.label}: 畫面沒有「無法判定」字樣")
        if "ui2-chip--positive" in html_:
            bad.append(f"{f.label}: 畫面用了正向（綠）chip")
        for w in _SAFE_READINGS:
            if w in text:
                bad.append(f"{f.label}: 畫面出現 safe 讀法 {w!r}")
    return bad


def _undeterminable_fields() -> list[FieldVM]:
    out = []
    for p in PAGE_IDS:
        for sc in SCENARIO_IDS:
            out += [f for f in _all_fields(get_preview_page_vm(p, sc))
                    if f.state is JudgementState.UNDETERMINABLE]
    return out


def test_dec124_risk_cap_undeterminable_never_rendered_as_safe():
    fields = _undeterminable_fields()
    assert any(f.label == "Risk Cap" for f in fields)
    for render in (lambda f: H.qa_row_html(None, f), H.field_row_html):
        assert check_undeterminable_never_reads_safe(fields, H.tone_for, render) == []
    for p in ("p4_market", "p4_target", "p4_hold"):     # 第一屏整塊也不得出現 safe 讀法
        fs_html = H.first_screen_html(get_preview_page_vm(p, "loaded").context.first_screen)
        assert T.TEXT_RISK_CAP_UNDETERMINABLE in fs_html
        assert "今日無需調整" not in _visible_text(fs_html) and "ui2-chip--positive" not in fs_html


def test_dec124_risk_cap_safe_guard_has_teeth():
    fields = [f for f in _undeterminable_fields() if f.label == "Risk Cap"]

    def green(f):                       # 違憲：無法判定塗綠
        return ChipTone.POSITIVE

    def says_no_adjust(f):              # 違憲：無法判定被渲染成「今日無需調整」
        return H.qa_row_html(None, f) + "今日無需調整"

    def drops_text(f):                  # 違憲：把「無法判定」字樣吞掉
        return "<div>Risk Cap</div>"
    assert check_undeterminable_never_reads_safe(fields, green, lambda f: H.qa_row_html(None, f))
    assert check_undeterminable_never_reads_safe(fields, H.tone_for, says_no_adjust)
    assert check_undeterminable_never_reads_safe(fields, H.tone_for, drops_text)


# ── Capability marker：Preview-only，只准在明列的 Preview producer／契約／渲染檔出現 ─────
#: 允許出現 `CapabilityState.NOT_PROVIDED`／`TEXT_NOT_PROVIDED*` 的檔（其餘＝違規）。
#: 日後真 feed 若要用，須**明確、經審查地**擴充本清單（cutover 前須清零：BACKLOG `NUI2-CAPABILITY-MARKER-CUTOVER-ZERO`）。
CAPABILITY_MARKER_ALLOWLIST = (
    "shared/ui2_contract/models.py",          # 定義
    "shared/ui2_contract/text.py",            # 字樣
    "src/services/ui2/vm_common.py",          # Preview 期 Aggregator 未實作的動作欄
    "src/services/ui2/scenarios.py",          # FAKE scenario
    "src/ui2/components/html.py",             # 渲染（只上色，不產生）
    # NUI2-REAL-FEED（2026-11-03；明確、經審查的擴充）：Real-data Preview 未接線欄位＝capability `⬜ 尚未提供`＋原因
    # （⛔ FAKE 值、⛔ 補 0／中性）。同屬 Preview-only；cutover 前清零規則不變（`NUI2-CAPABILITY-MARKER-CUTOVER-ZERO`）。
    "src/services/ui2/real_canonical.py",
)
_CAP_NAMES = {"NOT_PROVIDED", "TEXT_NOT_PROVIDED", "TEXT_NOT_PROVIDED_AGGREGATOR"}


def check_capability_marker_scope(source: str, relpath: str) -> list[str]:
    if relpath in CAPABILITY_MARKER_ALLOWLIST:
        return []
    bad = []
    for n in ast.walk(ast.parse(source)):
        name = n.id if isinstance(n, ast.Name) else (n.attr if isinstance(n, ast.Attribute) else None)
        if name in _CAP_NAMES:
            bad.append(f"{relpath}:L{n.lineno}: capability marker {name} 不在 Preview 允許清單")
        if isinstance(n, (ast.ImportFrom,)) and any(a.name in _CAP_NAMES for a in n.names):
            bad.append(f"{relpath}:L{n.lineno}: import capability marker")
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and (
                n.value == "not_provided" or n.value.startswith(T.TEXT_NOT_PROVIDED)):
            bad.append(f"{relpath}:L{n.lineno}: 字面 capability marker {n.value!r}")
    return bad


@pytest.mark.parametrize("path", ALL_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_dec124_capability_marker_is_preview_only(path):
    rel = path.relative_to(ROOT).as_posix()
    assert check_capability_marker_scope(path.read_text(encoding="utf-8"), rel) == []


@pytest.mark.parametrize("injected", [
    "from shared.ui2_contract.models import CapabilityState\nx = CapabilityState.NOT_PROVIDED\n",
    "from shared.ui2_contract.text import TEXT_NOT_PROVIDED\n",
    "x = {'state': 'not_provided'}\n",
    "x = '⬜ 尚未提供（待 OneBrain）'\n",
])
def test_dec124_capability_marker_guard_has_teeth(injected):
    clean = (L3_DIR / "market_vm.py").read_text(encoding="utf-8")
    rel = "src/services/ui2/market_vm.py"
    assert check_capability_marker_scope(clean, rel) == []
    assert check_capability_marker_scope(injected + clean, rel), f"沒抓到：{injected!r}"


def test_dec124_capability_marker_never_counted_as_data_quality():
    """capability marker 欄位：layer＝capability、state 為 None、⛔ 帶值、⛔ safe 讀法。"""
    seen = 0
    for p in PAGE_IDS:
        for sc in SCENARIO_IDS:
            for f in _all_fields(get_preview_page_vm(p, sc)):
                if f.capability is CapabilityState.NOT_PROVIDED:
                    seen += 1
                    assert f.layer == "capability" and f.state is None and f.value_text is None
                    assert f.status_text.startswith(T.TEXT_NOT_PROVIDED)
                    assert not any(w in (f.status_text + (f.detail or "")) for w in _SAFE_READINGS)
                else:
                    assert f.layer in ("data", "judgement")
    assert seen > 0


# ── 混合字樣 `⬜ 尚未核准／無法判定`：UI2 ⛔ 使用（DEC-124 獨立稽核修正）───────────────
def check_no_undeterminable_wording_outside_judgement(tables) -> list[str]:
    """「無法判定」字樣只准出現在判定結果表；資料語意／capability 表出現 → 違規（含混合字樣）。"""
    bad = []
    for name, table in tables.items():
        for state, prefixes in table.items():
            for p in prefixes:
                if "無法判定" in p:
                    bad.append(f"{name}.{state} 收了含「無法判定」的字樣 {p!r}")
    return bad


def test_not_approved_mixed_literal_is_not_allowed_in_ui2():
    assert check_no_undeterminable_wording_outside_judgement(
        {"data": T.ALLOWED_STATUS_PREFIXES, "capability": T.CAPABILITY_STATUS_PREFIXES}) == []
    with pytest.raises(ValueError):
        FieldVM("x", FieldState.NOT_EVALUATED, None, T.TEXT_NOT_APPROVED)
    with pytest.raises(ValueError):
        FieldVM("x", JudgementState.UNDETERMINABLE, None, T.TEXT_NOT_APPROVED)
    assert T.TEXT_NOT_APPROVED == "⬜ 尚未核准／無法判定"          # Legacy 字樣逐字不改
    for p in PAGE_IDS:
        for sc in SCENARIO_IDS:
            assert all(T.TEXT_NOT_APPROVED not in (f.status_text or "")
                       for f in _all_fields(get_preview_page_vm(p, sc)))


def test_not_approved_guard_has_teeth():
    leaky = dict(T.ALLOWED_STATUS_PREFIXES,
                 not_evaluated=T.ALLOWED_STATUS_PREFIXES["not_evaluated"] + (T.TEXT_NOT_APPROVED,))
    assert check_no_undeterminable_wording_outside_judgement({"data": leaky})

