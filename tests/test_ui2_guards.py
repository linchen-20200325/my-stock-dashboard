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

from shared.ui2_contract import text as T
from shared.ui2_contract.models import (
    CardVM, FieldState, FieldVM, FreshnessInfo, PageVM,
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
    bad: list[str] = []
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


@pytest.mark.parametrize("path", VM_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
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
])
def test_g2_guard_has_teeth(injected):
    """mutation：對乾淨檔注入單一違規，檢查器必須回報（否則守衛是裝飾品）。"""
    clean = (L3_DIR / "market_vm.py").read_text(encoding="utf-8")
    assert check_vm_purity(clean) == []
    assert check_vm_purity(injected + clean), f"檢查器沒抓到：{injected!r}"


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


def check_not_a_producer(source: str) -> list[str]:
    tree = ast.parse(source)
    consts = _const_str_map(tree)
    bad: list[str] = []

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
    for s in (FieldState.NOT_EVALUATED, FieldState.MISSING, FieldState.NOT_PROVIDED, FieldState.OK):
        assert H.STATE_TONE[s] is ChipTone.NEUTRAL_INFO
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
    return out


def test_state_text_constants_are_unique():
    consts = {k: v for k, v in vars(T).items() if k.startswith("TEXT_") and isinstance(v, str)}
    assert len(set(consts.values())) == len(consts), "兩個 TEXT_* 常數字樣重複"


def test_four_states_never_share_a_status_prefix():
    seen: dict[str, str] = {}
    for state, prefixes in T.ALLOWED_STATUS_PREFIXES.items():
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
    (FieldState.NOT_EVALUATED, "HOLD"), (FieldState.NOT_PROVIDED, "safe"),
])
def test_non_value_states_reject_a_value(state, value):
    """missing ≠ 0；missing ≠ HOLD；unavailable ≠ safe；not evaluated ≠ safe。"""
    status = T.ALLOWED_STATUS_PREFIXES[state.value][0]
    with pytest.raises(ValueError):
        FieldVM("x", state, value, status)


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
        prefixes = T.ALLOWED_STATUS_PREFIXES[f.state.value]
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
    assert a.state is FieldState.NOT_PROVIDED and a.status_text == T.TEXT_NOT_PROVIDED_AGGREGATOR


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
        assert f.state is FieldState.NOT_EVALUATED        # not evaluated ≠ safe
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
