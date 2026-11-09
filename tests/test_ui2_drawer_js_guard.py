"""New UI2 JS 退役守衛（fast lane；純 AST／文字，不需瀏覽器）—— DEC-146。

**檔名沿用 `test_ui2_drawer_js_guard.py`（可追溯）；內容由「Drawer JS_V4 雜湊／API 白名單」改寫為「src/ui2 零 JS」守衛。**

背景：DEC-137 的 JS_V4（`src/ui2/shell/drawer_js.py::DRAWER_JS_HTML`）只服務手機 ☰ Drawer（inert 背景、ESC、焦點進出、
點當前頁收合、☰ 上按 Enter、listener 去重）。DEC-146 核准「頂部兩列五頁導覽、⛔ Drawer／rail」後，這些行為所保護的對象
（抽屜、☰、遮罩、背景 inert）**不存在**，沒有東西需要 JS：導覽＝原生 `st.radio`（radiogroup）。
退役**不是**刪守衛求綠，而是以「等價或更嚴」取代：

| 舊守衛（JS_V4） | 汰換／改寫 |
|---|---|
| `PINNED_SHA256`／`test_drawer_js_hash_is_pinned`／V4 diff／AST 白名單／`MEMBERS_OK`… | **汰換**為：drawer_js 模組不存在且無任何 caller／殘留符號（`test_drawer_js_is_fully_retired`）＋ src/ui2 **零** JS 載體（`test_newui2_scope_has_zero_javascript`）。比「釘住一份 JS」更嚴：連 JS 本身都不得存在 |
| `_JS_MUTATIONS`／`_PY_MUTATIONS`（對 JS 注入危害）teeth | **汰換**為對「零 JS」守衛的注入 teeth（`test_zero_js_guard_has_teeth`；注入 `<script>`／`unsafe_allow_javascript`／`st.html`／`on*=`／`components`／`srcdoc`／`javascript:` 必紅） |
| `test_newui2_scope_only_drawer_js_has_javascript`（恰 1 檔有 JS） | **改寫**：New UI2 範圍 0 檔有 JS |
| `SRC_ALLOW`／`test_src_global_javascript_count_does_not_grow` | **改寫**：`src/**` 只剩既有 EX-OAUTH-1（`oauth_state.py`）；drawer_js 項移除 |
| `JS_CALL_ALLOWLIST`（drawer_js:1＋oauth:1＝2）＋ `test_js_call_allowlist_total_is_two` | **改寫**：drawer_js 項移除、總數＝**1**（`test_js_call_allowlist_total_is_one`）；其餘逐檔×逐函式精確計數與 teeth 保留 |
| JS／CSS 斷點交叉比對 | **汰換**（JS 不存在）；以 `test_drawer_js_is_fully_retired` 斷言 CSS 無 Drawer 斷點殘留取代 |
| `check_raw_interactive_html`（只准 ☰ toggle） | **更嚴**：raw 互動 HTML 白名單縮為**空**（☰ toggle 已刪） |
| `check_drawer_reads_no_account`／帳戶摘要固定占位 | **改寫為**頂部第一列版本（`_render_nav` 只讀 `ui2_page`；`top_status_row_html` 不讀 session／query／帳戶） |
| `test_toggle_markup_a11y_contract`（☰ aria） | **汰換**：☰ 不存在；頂部導覽的 a11y（role／checked／鍵盤）改由真 Chromium 測 `tests/test_ui2_drawer_browser.py` |
| `test_workflow_has_required_browser_lane` 等 CI meta 守衛 | **原樣保留** |
"""
from __future__ import annotations

import ast
import functools
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
JS_REL = "src/ui2/shell/drawer_js.py"          # 已退役：此路徑必須不存在
OAUTH_REL = "src/data/portfolio/oauth_state.py"


SCAN_PATTERNS = {
    "unsafe_allow_javascript": r"unsafe_allow_javascript",
    "components": r"streamlit\.components|\bst\.components|from\s+streamlit\s+import[^\n]*\bcomponents\b|\bcomponents\.v[12]\b",
    "<script": r"(?i)<script",
    "on*= attr": r"(?i)\bon[a-z]{3,}\s*=\s*[\"'\\]",
    "javascript:": r"(?i)javascript:",
    "<iframe": r"(?i)<iframe",
    "srcdoc": r"(?i)srcdoc",
}
SCAN_SUFFIXES = {".py", ".js", ".html", ".css"}
NEWUI2_SCOPES = ("src/ui2", "shared/ui2_contract", "src/services/ui2", "app_ui2.py")
NEWUI2_ALLOW: dict[str, set[str]] = {}          # DEC-146：New UI2 範圍 0 JS
#: `src/**` 全域：只剩既有 EX-OAUTH-1（動態字串，⛔ 不得當樣板）；drawer_js 已退役。**新增任何一處＝紅**。
SRC_ALLOW = {OAUTH_REL: {"unsafe_allow_javascript", "<script"}}


def scan_text(text: str) -> list[str]:
    return [k for k, p in SCAN_PATTERNS.items() if re.search(p, text)]


def scan_tree(scopes, allow: dict[str, set[str]]) -> tuple[list[str], dict[str, list[str]]]:
    bad, hits = [], {}
    for sc in scopes:
        base = ROOT / sc
        files = sorted(base.rglob("*")) if base.is_dir() else [base]
        for p in files:
            if not p.is_file() or p.suffix not in SCAN_SUFFIXES or "__pycache__" in p.parts:
                continue
            rel = p.relative_to(ROOT).as_posix()
            ks = scan_text(p.read_text(encoding="utf-8", errors="ignore"))
            if ks:
                hits[rel] = ks
            bad += [f"{rel}: {k}" for k in ks if k not in allow.get(rel, set())]
    return bad, hits



def test_newui2_scope_has_zero_javascript():
    bad, hits = scan_tree(NEWUI2_SCOPES, NEWUI2_ALLOW)
    assert bad == [] and hits == {}, hits


def test_src_global_javascript_count_does_not_grow():
    bad, hits = scan_tree(("src",), SRC_ALLOW)
    assert bad == []
    assert set(hits) == set(SRC_ALLOW), "allowlist 有過期項或新增 JS 檔"


def test_drawer_js_is_fully_retired():
    """JS_V4 退役條件（可追溯）：(1) 模組檔不存在；(2) src／shared／tests 之外的程式碼無任何 caller 或殘留符號；
    (3) CSS 無 Drawer／☰／遮罩／左 rail 殘留。有人把 Drawer 加回來（含只加回 JS、不加 CSS）→ 紅。"""
    assert not (ROOT / JS_REL).exists()
    needles = ("drawer_js", "DRAWER_JS_HTML", "render_drawer_script", "__ui2drJS3", "ui2-dr-", "ui2dr", "_WRAP_TAGS", "_TOGGLE_HTML")
    offenders = []
    for sc in ("src", "shared", "app_ui2.py", "app.py"):
        base = ROOT / sc
        for p in (sorted(base.rglob("*.py")) if base.is_dir() else [base]):
            if "__pycache__" in p.parts:
                continue
            t = p.read_text(encoding="utf-8")
            offenders += [f"{p.relative_to(ROOT).as_posix()}: {n}" for n in needles if n in t]
    assert offenders == []


def check_zero_js(files: dict[str, str]) -> list[str]:
    bad = []
    for rel, t in files.items():
        bad += [f"{rel}: {k}" for k in scan_text(t)]
        tree = ast.parse(t)
        for n in ast.walk(tree):     # `st.html(...)` 本身也禁（即使沒帶 unsafe_allow_javascript）：New UI2 一律走 st.markdown
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "html" \
                    and isinstance(n.func.value, ast.Name) and n.func.value.id == "st":
                bad.append(f"{rel}:L{n.lineno}: st.html")
    return bad


def _ui2_files_for_zero_js() -> dict[str, str]:
    out = {}
    for sc in ("src/ui2", "shared/ui2_contract", "src/services/ui2", "app_ui2.py"):
        base = ROOT / sc
        for p in (sorted(base.rglob("*.py")) if base.is_dir() else [base]):
            if "__pycache__" not in p.parts:
                out[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8")
    return out


def test_zero_js_ast_guard_new_ui2_files():
    assert check_zero_js(_ui2_files_for_zero_js()) == []


@pytest.mark.parametrize("payload", [
    "import streamlit as st\nst.html('<b>x</b>')\n",
    "import streamlit as st\nst.html('x', unsafe_allow_javascript=True)\n",
    "X = '<script>1</script>'\n", "X = '<b onclick=\"1\">'\n", "X = 'javascript:void 0'\n",
    "import streamlit.components.v1 as c\n", "X = '<iframe srcdoc=1>'\n",
])
def test_zero_js_guard_has_teeth(payload):
    files = _ui2_files_for_zero_js()
    files["src/ui2/views/market.py"] += "\n" + payload
    assert check_zero_js(files), payload
    files2 = _ui2_files_for_zero_js()
    files2["src/ui2/shell/app.py"] += "\n" + payload
    assert check_zero_js(files2), payload


def test_drawer_js_retirement_guard_has_teeth(tmp_path, monkeypatch):
    """突變：把 drawer 符號加回任一 src 檔 → `test_drawer_js_is_fully_retired` 的 needles 掃描必抓。"""
    needles = ("drawer_js", "DRAWER_JS_HTML", "render_drawer_script", "ui2-dr-")
    probe = "from src.ui2.shell.drawer_js import render_drawer_script\n"
    assert any(n in probe for n in needles)
    assert not any(n in (ROOT / "src/ui2/shell/app.py").read_text(encoding="utf-8") for n in needles)


# ── 精確計數守衛（QA 變異 M8：同檔加第二個呼叫原本仍綠）：每個允許檔案 × 每種受控 JS 位置的「所在函式限定名＋精確次數」──
#: 掃描根（現有範圍）：`src/**`、`shared/**`、`scripts/**`、`tools/**`、`app.py`、`app_ui2.py`、`mcp_server/**`。
JS_SCAN_ROOTS = ("src", "shared", "scripts", "tools", "mcp_server", "app.py", "app_ui2.py")
#: 白名單：{相對路徑: {(kind, 所在函式限定名): 精確次數}}。`<module>`＝模組層。次數或位置不符＝紅（含少於：呼叫被移走／刪除也要重過 Gate）。
#: kind：`unsafe_js`＝帶 `unsafe_allow_javascript` 關鍵字的呼叫；`kw_ref`＝該字串出現在呼叫關鍵字以外（`**{'…':…}`、字典鍵、屬性）；
#:      `components`＝`streamlit.components`／`st.components`／`components.v1|v2` 的 import 或屬性使用。
JS_CALL_ALLOWLIST: dict[str, dict[tuple[str, str], int]] = {
    "src/data/portfolio/oauth_state.py": {("unsafe_js", "maybe_silent_reauth"): 1},         # 既有 EX-OAUTH-1（base 已存在）
    # 既有驗證探針腳本：把 `unsafe_allow_javascript=False` 寫在**字串**裡探測 kwarg 是否存在（不是呼叫、值為 False、非產品路徑）；精確 2 處字串
    "tools/phase3_verify/appttest_floor156.py": {("kw_ref", "<module>"): 2},
}


def _qualnames(tree: ast.AST):
    """yield (node, 所在函式／類別限定名)；模組層＝`<module>`。"""
    out = []

    def walk(node, stack):
        for ch in ast.iter_child_nodes(node):
            st = stack
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                st = stack + [ch.name]
            out.append((ch, ".".join(stack) or "<module>"))
            walk(ch, st)
    walk(tree, [])
    return out


@functools.lru_cache(maxsize=None)
def count_js_calls(source: str) -> dict[tuple[str, str], int]:
    tree = ast.parse(source)
    doc_ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            doc_ids.add(id(n.body[0].value))
    kw_ids = {id(k.value) for n in ast.walk(tree) if isinstance(n, ast.Call) for k in n.keywords
              if k.arg == "unsafe_allow_javascript"}
    counts: dict[tuple[str, str], int] = {}

    def add(kind, q):
        counts[(kind, q)] = counts.get((kind, q), 0) + 1
    for node, q in _qualnames(tree):
        if isinstance(node, ast.Call) and any(k.arg == "unsafe_allow_javascript" for k in node.keywords):
            add("unsafe_js", q)
        elif isinstance(node, ast.keyword) and node.arg is None and isinstance(node.value, ast.Dict):
            if any(isinstance(k, ast.Constant) and k.value == "unsafe_allow_javascript" for k in node.value.keys):
                add("kw_ref", q)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "unsafe_allow_javascript" in node.value \
                and id(node) not in doc_ids and id(node) not in kw_ids:
            add("kw_ref", q)
        elif isinstance(node, ast.Attribute) and node.attr == "unsafe_allow_javascript":
            add("kw_ref", q)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [(node.module or "") + "." + a.name for a in node.names] + [node.module or ""]
            if any(re.match(r"streamlit\.components(\.|$)", m) for m in mods):
                add("components", q)
        elif isinstance(node, ast.Attribute) and node.attr == "components" and isinstance(node.value, ast.Name) \
                and node.value.id in {"st", "streamlit"}:
            add("components", q)
    return counts


def check_js_call_counts(files: dict[str, str], allow=JS_CALL_ALLOWLIST) -> list[str]:
    bad = []
    for rel, src in sorted(files.items()):
        got = count_js_calls(src)
        want = allow.get(rel, {})
        for k in sorted(set(got) | set(want)):
            if got.get(k, 0) != want.get(k, 0):
                bad.append(f"{rel}: {k[0]} 於 {k[1]} 次數 {got.get(k, 0)} ≠ 核准 {want.get(k, 0)}")
    for rel in allow:
        if rel not in files:
            bad.append(f"{rel}: 核准檔不存在於掃描範圍")
    return bad


@functools.lru_cache(maxsize=1)
def _js_scan_cached() -> tuple:
    return tuple(_js_scan_read().items())


def _js_scan_files() -> dict[str, str]:
    return dict(_js_scan_cached())


def _js_scan_read() -> dict[str, str]:
    out = {}
    for sc in JS_SCAN_ROOTS:
        base = ROOT / sc
        for p in (sorted(base.rglob("*.py")) if base.is_dir() else ([base] if base.exists() else [])):
            if "__pycache__" not in p.parts:
                out[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8")
    return out


def check_js_call_counts(files: dict[str, str], allow=JS_CALL_ALLOWLIST) -> list[str]:
    bad = []
    for rel, src in sorted(files.items()):
        got = count_js_calls(src)
        want = allow.get(rel, {})
        for k in sorted(set(got) | set(want)):
            if got.get(k, 0) != want.get(k, 0):
                bad.append(f"{rel}: {k[0]} 於 {k[1]} 次數 {got.get(k, 0)} ≠ 核准 {want.get(k, 0)}")
    for rel in allow:
        if rel not in files:
            bad.append(f"{rel}: 核准檔不存在於掃描範圍")
    return bad


@functools.lru_cache(maxsize=1)
def _js_scan_cached() -> tuple:
    return tuple(_js_scan_read().items())


def _js_scan_files() -> dict[str, str]:
    return dict(_js_scan_cached())


def _js_scan_read() -> dict[str, str]:
    out = {}
    for sc in JS_SCAN_ROOTS:
        base = ROOT / sc
        for p in (sorted(base.rglob("*.py")) if base.is_dir() else ([base] if base.exists() else [])):
            if "__pycache__" not in p.parts:
                out[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8")
    return out



def test_js_call_counts_exact_per_file_and_function():
    """JS 呼叫總數（src/）＝1（只剩 oauth_state；base 為 1；DEC-146 退役 drawer_js 後相對 DEC-137 的 2 減 1）。逐檔×逐函式精確比對。"""
    assert check_js_call_counts(_js_scan_files()) == []


def test_js_call_allowlist_total_is_one():
    assert sum(n for v in JS_CALL_ALLOWLIST.values() for (k, _), n in v.items() if k == "unsafe_js") == 1
    assert "src/ui2/shell/drawer_js.py" not in JS_CALL_ALLOWLIST


_OAUTH = OAUTH_REL
_OA_CALL = "    st.html(_silent_redirect_script(_url), unsafe_allow_javascript=True)"


def _with(rel, fn):
    files = _js_scan_files()
    new = fn(files.get(rel, ""))
    assert new != files.get(rel)
    files[rel] = new
    return check_js_call_counts(files)


@pytest.mark.parametrize("name,rel,fn", [
    ("(a) oauth 同函式內再加第二次呼叫", _OAUTH, lambda s: s.replace(_OA_CALL, _OA_CALL + "\n" + _OA_CALL)),
    ("(b) oauth 另一函式加一次", _OAUTH, lambda s: s + "\n\ndef _other():\n    st.html('<script></script>', unsafe_allow_javascript=True)\n"),
    ("(c) oauth 的呼叫移到別的函式", _OAUTH, lambda s: s.replace(_OA_CALL, "    pass") + "\n\ndef _moved(_url):\n" + _OA_CALL + "\n"),
    ("(d) 新檔加", "src/data/new_file.py", lambda s: "import streamlit as st\nst.html('x', unsafe_allow_javascript=True)\n"),
    ("(e) 刪除 oauth 現有呼叫", _OAUTH, lambda s: s.replace(_OA_CALL, "    pass")),
    ("ui2 殼加一次（drawer 復活）", "src/ui2/shell/app.py",
     lambda s: s + "\n\ndef _again():\n    st.html('x', unsafe_allow_javascript=True)\n"),
    ("drawer_js 檔復活", "src/ui2/shell/drawer_js.py",
     lambda s: "import streamlit as st\n\ndef render_drawer_script():\n    st.html('x', unsafe_allow_javascript=True)\n"),
    ("**kwargs 字典繞法", "src/data/new_file.py", lambda s: "import streamlit as st\nst.html('x', **{'unsafe_allow_javascript': True})\n"),
    ("getattr 字串繞法", "src/data/new_file.py", lambda s: "k = 'unsafe_allow_javascript'\n"),
    ("components.html import", "src/data/new_file.py", lambda s: "import streamlit.components.v1 as c\n"),
    ("st.components 屬性", "src/data/new_file.py", lambda s: "import streamlit as st\nst.components.v1.html('x')\n"),
    ("shared 目錄新檔", "shared/new_js.py", lambda s: "import streamlit as st\nst.html('x', unsafe_allow_javascript=True)\n"),
    ("app.py 加", "app.py", lambda s: s + "\nst.html('x', unsafe_allow_javascript=True)\n"),
])
def test_js_call_count_guard_has_teeth(name, rel, fn):
    assert _with(rel, fn), f"沒抓到：{name}"


def test_js_call_count_guard_restored_is_green():
    """(f) 變異只在記憶體副本，真檔未動：還原＝原樣掃描為綠。"""
    assert check_js_call_counts(_js_scan_files()) == []


@pytest.mark.parametrize("payload", [
    "st.html(x, unsafe_allow_javascript=True)\n", "x = '<script>1</script>'\n",
    "import streamlit.components.v1 as c\n", "from streamlit import components\n", "x = '<b onclick=\"1\">'\n",
    "x = 'javascript:void 0'\n", "x = '<iframe>'\n", "x = 'srcdoc'\n", "x = '<SCRIPT>'\n",
])
def test_global_scan_has_teeth(payload):
    assert scan_text(payload)
    assert scan_text((ROOT / "src" / "ui2" / "views" / "market.py").read_text(encoding="utf-8")) == []


def test_global_scan_does_not_confuse_ui2_components_html_module():
    """`src.ui2.components.html` 是自家模組，不是 streamlit components（研究組已修的誤判）。"""
    assert scan_text("from src.ui2.components.html import banner_html\nfrom src.ui2.components import html as H\n") == []


# ════════════════════════════════════════════════════════════════════
# 5. raw 互動 HTML 白名單（DEC-146：縮為空）／頂部第一列固定占位不讀帳戶與 query
# ════════════════════════════════════════════════════════════════════
_INTERACTIVE = re.compile(r"(?i)<(input|label|button|select|textarea|form|a)\b|\bhref\s*=")


def _non_doc_strings(source: str) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    docs = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            docs.add(id(n.body[0].value))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def check_raw_interactive_html(files: dict[str, str]) -> list[str]:
    """New UI2 原始碼的字串常數中，raw 互動標籤（input／label／button／select／textarea／form／a／href）**一律禁止**。
    DEC-137 只准 ☰ toggle（1 input＋2 label）；DEC-146 移除 ☰ 後白名單縮為空（導覽用原生 st.radio，不手寫互動 HTML）。"""
    bad = []
    for rel, src in files.items():
        for ln, s in _non_doc_strings(src):
            for m in _INTERACTIVE.finditer(s):
                bad.append(f"{rel}:L{ln}: raw <{(m.group(1) or 'href').lower()}>")
    return bad


def _ui2_sources() -> dict[str, str]:
    out = {}
    for sc in ("src/ui2", "app_ui2.py"):
        base = ROOT / sc
        for p in (sorted(base.rglob("*.py")) if base.is_dir() else [base]):
            if "__pycache__" not in p.parts:
                out[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8")
    return out


def test_raw_interactive_html_is_empty():
    assert check_raw_interactive_html(_ui2_sources()) == []


@pytest.mark.parametrize("payload", ["X = '<input type=\"text\">'\n", "X = '<button>x</button>'\n",
                                     "X = '<a href=\"/x\">x</a>'\n", "X = '<form>'\n",
                                     "X = '<input type=\"checkbox\" id=\"ui2dr\">'\n"])
def test_raw_interactive_html_guard_has_teeth(payload):
    for rel in ("src/ui2/views/market.py", "src/ui2/shell/app.py"):
        files = _ui2_sources()
        files[rel] += "\n" + payload
        assert check_raw_interactive_html(files), (rel, payload)


_ACCOUNT_IDS = re.compile(r"ui2_account|KEY_ACCOUNT|query_params|ui2_dev|DEV_FLAG_PARAM|dev_surface_enabled|session_state")


def _strip_doc(node):
    if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) \
            and isinstance(node.body[0].value.value, str):
        node.body = node.body[1:] or [ast.Pass()]
    return node


def _fn_src(source: str, name: str) -> str:
    """函式原始碼（去 docstring／註解；`ast.unparse`）——說明文字可提及被禁識別字，程式碼不行。"""
    tree = ast.parse(source)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.unparse(_strip_doc(fn))


def check_top_row_reads_no_account(app_src: str, html_src: str) -> list[str]:
    """頂部第一列固定占位：`_render_nav` 只准讀 `ui2_page`（KEY_PAGE；由 st.radio 自己持有）；`top_status_row_html` 只吃模式標示參數，
    零 session／query／帳戶（取代舊 `check_drawer_reads_no_account`）。"""
    bad = []
    nav = _fn_src(app_src, "_render_nav")
    hits = set(_ACCOUNT_IDS.findall(nav))
    if hits:
        bad.append(f"_render_nav 讀了 {hits}")
    acc = _fn_src(html_src, "top_status_row_html")
    if _ACCOUNT_IDS.search(acc):
        bad.append("top_status_row_html 不得讀 session／query／帳戶")
    if not re.search(r"def top_status_row_html\(banner_text: str \| None", acc):
        bad.append("top_status_row_html 簽名只准模式標示參數")
    return bad


def _top_srcs() -> tuple[str, str]:
    return ((ROOT / "src/ui2/shell/app.py").read_text(encoding="utf-8"),
            (ROOT / "src/ui2/components/html.py").read_text(encoding="utf-8"))


def test_top_row_reads_no_account_query_or_dev_flag():
    assert check_top_row_reads_no_account(*_top_srcs()) == []


@pytest.mark.parametrize("which,old,new", [
    ("app", "    with st.container(key=KEY_NAV):", "    _a = st.session_state[KEY_ACCOUNT]\n    with st.container(key=KEY_NAV):"),
    ("app", "    with st.container(key=KEY_NAV):", "    _q = st.query_params.get('ui2_dev')\n    with st.container(key=KEY_NAV):"),
    ("html", '    chip = chip_html(TEXT_NOT_PROVIDED, ChipTone.NEUTRAL_INFO, axis="capability", state="not_provided")\n    mode =',
     '    chip = chip_html(TEXT_NOT_PROVIDED, ChipTone.NEUTRAL_INFO, axis="capability", state="not_provided")\n    _x = "ui2_account"\n    mode ='),
    ("html", "def top_status_row_html(banner_text", "def top_status_row_html(account=None, banner_text"),
])
def test_top_row_account_guard_has_teeth(which, old, new):
    a, h = _top_srcs()
    if which == "app":
        assert a.count(old) == 1
        a = a.replace(old, new)
    else:
        assert h.count(old) == 1
        h = h.replace(old, new)
    assert check_top_row_reads_no_account(a, h)


def test_allowed_ui2_writes_unchanged_by_top_nav():
    """頂部導覽不新增 session key：允許寫入的 key 仍是既有 5 個。"""
    from tests.test_ui2_real_feed import ALLOWED_UI2_WRITES
    assert ALLOWED_UI2_WRITES == frozenset({"ui2_page", "ui2_scenario", "ui2_account", "ui2_feed", "ui2_target_mode"})


# ════════════════════════════════════════════════════════════════════
# 6. CI browser lane meta 守衛（測試規格 §2.4-4）
# ════════════════════════════════════════════════════════════════════
WORKFLOW = ROOT / ".github" / "workflows" / "pr-check.yml"


def test_workflow_has_required_browser_lane():
    y = WORKFLOW.read_text(encoding="utf-8")
    assert "ui2-browser:" in y and "ui2-browser-gate:" in y
    assert re.search(r"UI2_BROWSER_LANE:\s*required", y)
    assert re.search(r"playwright==\d+\.\d+\.\d+", y), "playwright 版本必須 pin"
    assert "1.56.0" in y and "1.59.2" in y
    assert "-m ui2_browser" in y and "--junitxml" in y
    gate = y[y.index("ui2-browser-gate:"):]
    assert "needs:" in gate and "if: always()" in gate
    assert not re.search(r"^\s+continue-on-error:", y[y.index("ui2-browser:"):], re.M)   # browser lane 不得 informational


def test_fast_and_slow_lanes_not_relaxed():
    y = WORKFLOW.read_text(encoding="utf-8")
    fast = y[y.index("fast-checks:"):y.index("slow-tests:")]
    assert "run: pytest -v" in fast and not re.search(r"^\s+continue-on-error:", fast, re.M)
    slow = y[y.index("slow-tests:"):y.index("ui2-browser:")]
    assert "pytest -v -m slow" in slow


def test_pytest_ini_registers_marker_and_excludes_it_by_default():
    ini = (ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert re.search(r"^\s+ui2_browser:", ini, re.M)
    assert 'not slow and not ui2_browser' in ini


def test_browser_behaviour_tests_never_bare_skip():
    """New UI2 行為測試不得裸 `importorskip("playwright…")`／`pytest.skip(`；唯一許可在 `require_browser()`。"""
    offenders = []
    for p in sorted((ROOT / "tests").glob("test_ui2_*.py")) + [ROOT / "tests" / "ui2_browser.py"]:
        t = p.read_text(encoding="utf-8")
        tree = ast.parse(t)
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                    and n.func.value.id == "pytest" and n.func.attr in {"skip", "importorskip"}:
                fn = next((f for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)
                           and f.lineno <= n.lineno <= (f.end_lineno or 0)), None)
                if not (p.name == "ui2_browser.py" and fn is not None and fn.name == "require_browser"):
                    offenders.append(f"{p.name}:L{n.lineno}")
    assert offenders == []
