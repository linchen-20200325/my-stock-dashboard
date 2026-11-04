"""New UI2 手機抽屜 JS 安全守衛（fast lane；純 AST／文字，不需瀏覽器）—— DEC-137。

依據：`docs/vnext/NEWUI2_MOBILE_DRAWER_JS_SAFETY_DESIGN_2026-11-04.md`（§5～§9；§15 JS_V4）、
測試與驗收規格 §2.4-4／§3（非瀏覽器項）／§4（突變 teeth）。

守什麼（每一層都附「注入違規必紅」的 teeth）：
1. **雜湊釘住**：`DRAWER_JS_HTML` 規範化後 sha256＝`PINNED_SHA256`。任何改動（含空白、註解）→ 紅 → **必須重過 JS Gate**。
2. **API 白名單（主守衛）**：JS 只准列舉的全域識別字／成員／事件／字串／selector／正則；另有明確禁止清單。
   ⚠️ 誠實限制：這是 **regex 掃描，不是 JavaScript parser**；最後防線是雜湊。
3. **Python AST 判準**：全 New UI2 恰一處 `st.html(DRAWER_JS_HTML, unsafe_allow_javascript=True)`；旗標字面 True；
   第一參數裸 Name；該 Name 模組層恰一次賦值且為 `Constant(str)`（擋 f-string／BinOp／format／%／join／再賦值／+=／global）。
4. **全域掃描兩個範圍**：New UI2 只准 `drawer_js.py`；`src/**` allowlist＝`drawer_js.py`＋既有 EX-OAUTH-1 `oauth_state.py`（計數不得增加）。
5. **JS／CSS 斷點交叉比對**、**殼內 raw 互動 HTML 白名單**（只准 ☰ toggle）、**抽屜不讀** `ui2_account`／`query_params`／`ui2_dev`、
   **CI browser lane meta 守衛**（workflow 含 required env／pin 版本／兩個 Streamlit 版本／gate job；行為測試不得裸 skip）。
"""
from __future__ import annotations

import ast
import hashlib
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
JS_FILE = ROOT / "src" / "ui2" / "shell" / "drawer_js.py"
JS_REL = "src/ui2/shell/drawer_js.py"
CONST_NAME = "DRAWER_JS_HTML"

#: JS_V4 釘住值（規範化＝CRLF/CR→LF、去頭尾換行，對含 `<script>` 包裝的整個常數）。JS_V3＝24050f1b…606cd3（研究組候選）。
PINNED_SHA256 = "c84d687fcaa246b7411ce1f1b927efcd230e9863fbaeb132b3fb10cb3702680a"

# ── API 白名單（變更＝改 JS＝重過 JS Gate；V3→V4 只新增成員 `click`）────────────────
GLOBALS_OK = {"window", "document", "Set", "Date", "MutationObserver", "requestAnimationFrame", "setTimeout", "RegExp"}
MEMBERS_OK = {
    "matchMedia", "matches", "querySelector", "closest", "parentElement", "children", "checked", "focus", "inert",
    "held", "ret", "q", "forEach", "push", "now", "add", "has", "addEventListener", "observe", "activeElement", "body",
    "key", "target", "test", "__ui2drJS3",
    "click",          # V4：☰ 上按 Enter → `t.click()`（走與 Space 相同的原生切換路徑）
}
SELECTORS_OK = {".ui2-dr-toggle", ".ui2-dr-wrap", ".st-key-ui2_nav", ".stApp",
                ".st-key-ui2_nav input[type=radio]", ".st-key-ui2_nav input[type=radio]:checked", ".st-key-ui2_nav label"}
REGEX_OK = {"^(Arrow|Enter$| $)"}
EVENTS_OK = {"keydown", "change", "click"}
OTHER_STR_OK = {"Escape", "Enter", "childList", "subtree", "(max-width: 768px)"}
FORBIDDEN_TOKENS = ["fetch", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon", "localStorage", "sessionStorage",
                    "indexedDB", "document.cookie", "eval", "Function", "import(", "importScripts", "window.open", "postMessage",
                    "innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "createElement", "setAttribute",
                    "appendChild", "location", "navigator", "Worker", "srcdoc", "javascript:", "style.", "classList",
                    "removeAttribute", "dispatchEvent", "parent.", "top.", "frames", "opener", "clipboard", "history"]


def normalize(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


def sha(s: str) -> str:
    return hashlib.sha256(normalize(s).encode("utf-8")).hexdigest()


def _strip_js_comments(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"\\])//[^\n]*", r"\1", js)


def check_js_text(js: str) -> list[str]:
    """API 白名單掃描（註解先剝掉）。regex，非 parser（誠實限制）。"""
    v: list[str] = []
    code = _strip_js_comments(js)
    for rx in re.findall(r"(?<![\w)\]$])/(\^[^/\n]*)/(?=\.test)", code):
        if rx not in REGEX_OK:
            v.append(f"regex literal not whitelisted: /{rx}/")
    code = re.sub(r"(?<![\w)\]$])/\^[^/\n]*/(?=\.test)", "rx_", code)
    for t in FORBIDDEN_TOKENS:
        if re.search(r"(?<![\w$])" + re.escape(t) + (r"(?![\w$])" if t[-1].isalnum() else ""), code):
            v.append(f"forbidden token: {t}")
    if "`" in code:
        v.append("template literal (backtick) banned")
    if "\\" in code:
        v.append("backslash / unicode escape banned")
    nostr = re.sub(r"'[^'\n]*'", "''", code)
    if re.search(r"[\w$)\]]\s*\[", nostr):
        v.append("computed member access banned")
    if '"' in nostr:
        v.append("double-quoted string banned（字串一律單引號，才能被白名單掃到）")
    for s in re.findall(r"'([^'\n]*)'", code):
        if s in EVENTS_OK or s in OTHER_STR_OK or s in SELECTORS_OK:
            continue
        v.append(f"string literal not whitelisted: {s!r}")
    for m in set(re.findall(r"\.\s*([A-Za-z_$][\w$]*)", nostr)):
        if m not in MEMBERS_OK:
            v.append(f"member not whitelisted: .{m}")
    for g in set(re.findall(r"(?<![\w$.])(window|document|globalThis|self|[A-Z][A-Za-z]+|setTimeout|setInterval|"
                            r"requestAnimationFrame)\b", nostr)):
        if g not in GLOBALS_OK:
            v.append(f"global not whitelisted: {g}")
    for ev in re.findall(r"addEventListener\(\s*'([^']*)'", code):
        if ev not in EVENTS_OK:
            v.append(f"event not whitelisted: {ev}")
    return v


def _assignments(tree: ast.Module) -> dict[str, list[ast.AST]]:
    out: dict[str, list[ast.AST]] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                for nm in ast.walk(t):
                    if isinstance(nm, ast.Name):
                        out.setdefault(nm.id, []).append(n)
        elif isinstance(n, (ast.AugAssign, ast.AnnAssign)) and isinstance(n.target, ast.Name):
            out.setdefault(n.target.id, []).append(n)
        elif isinstance(n, ast.Global):
            for nm in n.names:
                out.setdefault(nm, []).append(n)
    return out


def check_st_html_js_calls(source: str, *, expect_hash: str | None = PINNED_SHA256) -> list[str]:
    """JS 設計 §6：唯一允許的 `st.html(DRAWER_JS_HTML, unsafe_allow_javascript=True)` 模組的 AST 判準＋白名單＋雜湊。"""
    v: list[str] = []
    tree = ast.parse(source)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and any(k.arg == "unsafe_allow_javascript" for k in n.keywords)]
    if len(calls) != 1:
        v.append(f"expected exactly 1 unsafe_allow_javascript call, found {len(calls)}")
    for c in calls:
        f = c.func
        if not (isinstance(f, ast.Attribute) and f.attr == "html" and isinstance(f.value, ast.Name) and f.value.id == "st"):
            v.append("call must be st.html(...)")
        kw = next(k for k in c.keywords if k.arg == "unsafe_allow_javascript")
        if not (isinstance(kw.value, ast.Constant) and kw.value.value is True):
            v.append("unsafe_allow_javascript must be literal True")
        if len(c.args) != 1 or len(c.keywords) != 1 or any(isinstance(a, ast.Starred) for a in c.args):
            v.append("st.html must have exactly 1 positional arg + only unsafe_allow_javascript kw")
        a0 = c.args[0] if c.args else None
        if not isinstance(a0, ast.Name):
            v.append("first arg must be a bare Name (no JoinedStr/BinOp/Call/format/%/join)")
            continue
        if a0.id != CONST_NAME:
            v.append(f"first arg Name must be {CONST_NAME}")
        defs = _assignments(tree).get(a0.id, [])
        if len(defs) != 1:
            v.append(f"{a0.id} must be assigned exactly once (found {len(defs)}; AugAssign/global/reassign banned)")
            continue
        d = defs[0]
        if not (isinstance(d, ast.Assign) and d in tree.body and len(d.targets) == 1
                and isinstance(d.value, ast.Constant) and isinstance(d.value.value, str)):
            v.append(f"{a0.id} must be a module-level `NAME = <str Constant>` (JoinedStr/BinOp/Call banned)")
            continue
        s = d.value.value
        if not (normalize(s).startswith("<script>\n") and normalize(s).endswith("\n</script>")):
            v.append("constant must be exactly one <script>…</script>")
        if s.count("<script") != 1 or s.count("</script>") != 1:
            v.append("exactly one <script> tag")
        if expect_hash and sha(s) != expect_hash:
            v.append(f"sha256 mismatch: {sha(s)[:12]} != {expect_hash[:12]}  (JS changed → must re-pass JS Gate and update pin)")
        v += [f"js: {x}" for x in check_js_text(normalize(s)[len("<script>"):-len("</script>")])]
    return v


SRC = JS_FILE.read_text(encoding="utf-8")


def _const() -> str:
    from src.ui2.shell.drawer_js import DRAWER_JS_HTML
    return DRAWER_JS_HTML


# ════════════════════════════════════════════════════════════════════
# 1～3. 雜湊／白名單／AST
# ════════════════════════════════════════════════════════════════════
def test_drawer_js_hash_is_pinned():
    """JS changed → must re-pass JS Gate and update pin（JS 設計 §8）。"""
    assert sha(_const()) == PINNED_SHA256, "JS changed → must re-pass JS Gate and update pin"


def test_drawer_js_module_passes_ast_whitelist_and_hash():
    assert check_st_html_js_calls(SRC) == []


def test_drawer_js_v4_diff_from_v3_is_only_the_enter_branch():
    """V3→V4 差異只有 keydown 監聽內兩行（Enter on ☰ → click()）；去掉這兩行必須逐字回到 JS_V3 雜湊。"""
    js = _const()
    v4_lines = [ln for ln in js.split("\n") if "V4：" in ln or "t.click(); return;" in ln]
    assert len(v4_lines) == 2
    v3 = "\n".join(ln for ln in js.split("\n") if ln not in v4_lines)
    assert sha(v3) == "24050f1b81c4fed6441d8dad082c90ab0b94ce10d032f42ce36524842e606cd3"


_TAIL = "  sync();\n})();"
_JS_MUTATIONS = {
    "空白 +1": ("S.q = false; sync();", "S.q = false;  sync();"),
    "只改註解": ("去重旗標", "去重旗標x"),
    "拔掉去重旗標": ("  if (window.__ui2drJS3) { return; }", ""),
    "拔掉 Enter 分支": ("    if (e.key === 'Enter' && t && e.target === t) { t.click(); return; }\n", ""),
    "fetch": (_TAIL, "  fetch('/x');\n" + _TAIL),
    "localStorage": (_TAIL, "  localStorage.setItem('a','b');\n" + _TAIL),
    "eval": (_TAIL, "  eval('1');\n" + _TAIL),
    "new Function": (_TAIL, "  new Function('1')();\n" + _TAIL),
    "innerHTML": (_TAIL, "  document.body.innerHTML = '';\n" + _TAIL),
    "window.open": (_TAIL, "  window.open('http://x');\n" + _TAIL),
    "postMessage": (_TAIL, "  window.parent.postMessage(1,'*');\n" + _TAIL),
    "cookie": (_TAIL, "  const c = document.cookie;\n" + _TAIL),
    "setAttribute": (_TAIL, "  document.body.setAttribute('x','y');\n" + _TAIL),
    "tabIndex 寫入": (_TAIL, "  document.body.tabIndex = 1;\n" + _TAIL),
    "未列 selector": ("$('.ui2-dr-toggle')", "$('.stApp input')"),
    "未列事件": ("document.addEventListener('click'", "document.addEventListener('paste'"),
    "未列成員 .value": (_TAIL, "  const v = T().value;\n" + _TAIL),
    "window['fe'+'tch']": (_TAIL, "  window['fe'+'tch']('/x');\n" + _TAIL),
    "樣板字串": (_TAIL, "  const z = `fe${1}`;\n" + _TAIL),
    "unicode 跳脫": (_TAIL, "  const z = '\\u0066etch';\n" + _TAIL),
    "計算式存取": (_TAIL, "  const k = window[mq];\n" + _TAIL),
    "雙引號字串": (_TAIL, '  const z = "x";\n' + _TAIL),
    "globalThis": (_TAIL, "  globalThis.x = 1;\n" + _TAIL),
    "setInterval": (_TAIL, "  setInterval(sync, 9);\n" + _TAIL),
}
_PY_MUTATIONS = {
    "f-string": ("st.html(DRAWER_JS_HTML,", 'st.html(f"<script>{DRAWER_JS_HTML}</script>",'),
    "BinOp 拼接": ('DRAWER_JS_HTML = """<script>', 'DRAWER_JS_HTML = "<script>" + """'),
    ".format": ("st.html(DRAWER_JS_HTML,", "st.html(DRAWER_JS_HTML.format(),"),
    "%": ("st.html(DRAWER_JS_HTML,", "st.html(DRAWER_JS_HTML % (),"),
    "join": ("st.html(DRAWER_JS_HTML,", "st.html(''.join([DRAWER_JS_HTML]),"),
    "變數取代": ("st.html(DRAWER_JS_HTML,", "st.html(some_var,"),
    "旗標非字面 True": ("st.html(DRAWER_JS_HTML, unsafe_allow_javascript=True)", "st.html(DRAWER_JS_HTML, unsafe_allow_javascript=FLAG)"),
    "別名呼叫": ("    st.html(DRAWER_JS_HTML, unsafe_allow_javascript=True)",
               "    h = st.html\n    h(DRAWER_JS_HTML, unsafe_allow_javascript=True)"),
    "兩個 script": ('</script>"""', '</script><script>1</script>"""'),
}
_PY_APPENDS = {
    "再賦值": "\nDRAWER_JS_HTML = DRAWER_JS_HTML + '<script>x</script>'\n",
    "+=": "\nDRAWER_JS_HTML += '<script>x</script>'\n",
    "global 改寫": "\ndef _f():\n    global DRAWER_JS_HTML\n    DRAWER_JS_HTML = '<script>1</script>'\n",
    "第二個呼叫": "\nst.html('<script>1</script>', unsafe_allow_javascript=True)\n",
}


@pytest.mark.parametrize("name", sorted(_JS_MUTATIONS) + sorted(_PY_MUTATIONS) + sorted(_PY_APPENDS))
def test_drawer_js_guard_has_teeth(name):
    if name in _PY_APPENDS:
        mutated = SRC + _PY_APPENDS[name]
    else:
        old, new = _JS_MUTATIONS.get(name) or _PY_MUTATIONS[name]
        assert SRC.count(old) == 1, (name, old)
        mutated = SRC.replace(old, new)
    assert mutated != SRC
    try:
        v = check_st_html_js_calls(mutated)
    except SyntaxError:
        v = ["SyntaxError"]
    assert v, f"沒抓到：{name}"


@pytest.mark.parametrize("name", ["fetch", "eval", "未列成員 .value", "window['fe'+'tch']", "setAttribute", "tabIndex 寫入"])
def test_drawer_js_whitelist_catches_harmful_additions_even_without_hash(name):
    """分層歸因：有害加法在**不靠雜湊**時也要被白名單層抓到（雜湊是最後防線，不是唯一防線）。"""
    old, new = _JS_MUTATIONS[name]
    assert check_st_html_js_calls(SRC.replace(old, new), expect_hash=None)


def test_whitelist_only_contains_used_members():
    """白名單不得預留未用的成員（預留＝日後可不過 Gate 加功能）；`RegExp` 全域為歷史列入、未用（JS 設計 §5.2 註）。"""
    code = re.sub(r"'[^'\n]*'", "''", _strip_js_comments(normalize(_const())))
    used = set(re.findall(r"\.\s*([A-Za-z_$][\w$]*)", code))
    assert MEMBERS_OK == used, (MEMBERS_OK - used, used - MEMBERS_OK)


# ════════════════════════════════════════════════════════════════════
# 4. 全域掃描（兩個範圍）
# ════════════════════════════════════════════════════════════════════
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
NEWUI2_ALLOW = {JS_REL: {"unsafe_allow_javascript", "<script"}}
#: `src/**` 全域：既有 EX-OAUTH-1（動態字串，⛔ 不得當樣板）＋本模組。**新增任何一處＝紅**。
SRC_ALLOW = {JS_REL: {"unsafe_allow_javascript", "<script"},
             "src/data/portfolio/oauth_state.py": {"unsafe_allow_javascript", "<script"}}


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


def test_newui2_scope_only_drawer_js_has_javascript():
    bad, hits = scan_tree(NEWUI2_SCOPES, NEWUI2_ALLOW)
    assert bad == []
    assert set(hits) == {JS_REL}


def test_src_global_javascript_count_does_not_grow():
    bad, hits = scan_tree(("src",), SRC_ALLOW)
    assert bad == []
    assert set(hits) == set(SRC_ALLOW), "allowlist 有過期項或新增 JS 檔"


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
# 5. 斷點交叉比對／raw 互動 HTML／抽屜不讀帳戶與 query
# ════════════════════════════════════════════════════════════════════
def _css_breakpoints(css: str) -> tuple[set[int], set[int]]:
    return ({int(x) for x in re.findall(r"@media \(max-width:(\d+)px\)\{\s*\n?\s*\.st-key-ui2_nav\{", css)},
            {int(x) for x in re.findall(r"@media \(min-width:(\d+)px\)\{\s*\n?\s*\.st-key-ui2_nav\{", css)})


def check_breakpoints(css: str, js: str) -> list[str]:
    mx, mn = _css_breakpoints(css)
    js_bp = {int(x) for x in re.findall(r"\(max-width: (\d+)px\)", js)}
    bad = []
    if len(mx) != 1 or len(mn) != 1 or len(js_bp) != 1:
        bad.append(f"斷點不唯一：css max={mx} min={mn} js={js_bp}")
    elif js_bp != mx or min(mn) != max(mx) + 1:
        bad.append(f"JS 斷點 {js_bp} 與 CSS 抽屜斷點 max={mx}／min={mn} 不一致（桌機殘留 inert 或手機 inert 不生效）")
    return bad


def test_js_and_css_drawer_breakpoints_match():
    from src.ui2.shell.css import CSS
    assert check_breakpoints(CSS, _const()) == []


def test_breakpoint_guard_has_teeth():
    from src.ui2.shell.css import CSS
    assert check_breakpoints(CSS, _const().replace("(max-width: 768px)", "(max-width: 767px)"))
    assert check_breakpoints(CSS.replace("@media (max-width:768px){\n  .st-key-ui2_nav{",
                                         "@media (max-width:800px){\n  .st-key-ui2_nav{"), _const())


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
    """New UI2 原始碼的字串常數中，raw 互動標籤只准 ☰ toggle（`src/ui2/shell/app.py`：1 個 `<input>`＋2 個 `<label>`）。"""
    bad, counts = [], {}
    for rel, src in files.items():
        for ln, s in _non_doc_strings(src):
            for m in _INTERACTIVE.finditer(s):
                tag = (m.group(1) or "href").lower()
                counts[(rel, tag)] = counts.get((rel, tag), 0) + 1
                if rel != "src/ui2/shell/app.py" or tag not in {"input", "label"}:
                    bad.append(f"{rel}:L{ln}: raw <{tag}>")
    if counts.get(("src/ui2/shell/app.py", "input"), 0) != 1 or counts.get(("src/ui2/shell/app.py", "label"), 0) != 2:
        bad.append(f"殼內 raw toggle 應恰 1 input＋2 label，實際 {counts}")
    return bad


def _ui2_sources() -> dict[str, str]:
    out = {}
    for sc in ("src/ui2", "app_ui2.py"):
        base = ROOT / sc
        for p in (sorted(base.rglob("*.py")) if base.is_dir() else [base]):
            if "__pycache__" not in p.parts:
                out[p.relative_to(ROOT).as_posix()] = p.read_text(encoding="utf-8")
    return out


def test_raw_interactive_html_is_only_the_drawer_toggle():
    assert check_raw_interactive_html(_ui2_sources()) == []


@pytest.mark.parametrize("payload", ["X = '<input type=\"text\">'\n", "X = '<button>x</button>'\n",
                                     "X = '<a href=\"/x\">x</a>'\n", "X = '<form>'\n"])
def test_raw_interactive_html_guard_has_teeth(payload):
    files = _ui2_sources()
    files["src/ui2/views/market.py"] += "\n" + payload
    assert check_raw_interactive_html(files)
    files2 = _ui2_sources()
    files2["src/ui2/shell/app.py"] += "\nY = '<input type=\"checkbox\">'\n"
    assert check_raw_interactive_html(files2)


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


def check_drawer_reads_no_account(app_src: str, html_src: str, js_src: str) -> list[str]:
    """抽屜／帳戶摘要固定占位：`_render_nav` 只准讀 `ui2_page`（KEY_PAGE）；`drawer_account_html` 零參數、零 session／query；
    `drawer_js.py` 不碰 session／query。（統一施工規格 §7、測試規格 D-17）"""
    bad = []
    nav = _fn_src(app_src, "_render_nav")
    hits = set(_ACCOUNT_IDS.findall(nav)) - {"session_state"}
    if hits:
        bad.append(f"_render_nav 讀了 {hits}")
    if re.findall(r"session_state\[(\w+)\]", nav) not in ([], ["KEY_PAGE"]):
        bad.append("_render_nav 讀了 ui2_page 以外的 session key")
    acc = _fn_src(html_src, "drawer_account_html")
    if _ACCOUNT_IDS.search(acc) or not re.search(r"def drawer_account_html\(\) -> str:", acc):
        bad.append("drawer_account_html 必須零參數且不讀 session／query／帳戶")
    if _ACCOUNT_IDS.search(ast.unparse(_strip_doc(ast.parse(js_src)))):
        bad.append("drawer_js.py 碰到 session／query／帳戶")
    return bad


def _drawer_srcs() -> tuple[str, str, str]:
    return ((ROOT / "src/ui2/shell/app.py").read_text(encoding="utf-8"),
            (ROOT / "src/ui2/components/html.py").read_text(encoding="utf-8"), SRC)


def test_drawer_reads_no_account_query_or_dev_flag():
    assert check_drawer_reads_no_account(*_drawer_srcs()) == []


@pytest.mark.parametrize("which,old,new", [
    ("app", "    tag = _WRAP_TAGS[", "    _a = st.session_state[KEY_ACCOUNT]\n    tag = _WRAP_TAGS["),
    ("app", "    tag = _WRAP_TAGS[", "    _q = st.query_params.get('ui2_dev')\n    tag = _WRAP_TAGS["),
    ("html", "def drawer_account_html() -> str:", "def drawer_account_html(account=None) -> str:"),
    ("html", "    btn = cta_html(CtaVM(DRAWER_ACCOUNT_BUTTON,", "    _x = 'ui2_account'\n    btn = cta_html(CtaVM(DRAWER_ACCOUNT_BUTTON,"),
])
def test_drawer_account_guard_has_teeth(which, old, new):
    a, h, j = _drawer_srcs()
    if which == "app":
        assert a.count(old) == 1
        a = a.replace(old, new)
    else:
        assert h.count(old) == 1
        h = h.replace(old, new)
    assert check_drawer_reads_no_account(a, h, j)


def test_drawer_account_is_capability_axis_fixed_placeholder():
    from shared.ui2_contract.text import TEXT_NOT_PROVIDED
    from src.ui2.components.html import drawer_account_html
    h = drawer_account_html()
    assert TEXT_NOT_PROVIDED in h and 'data-axis="capability"' in h and "ui2-chip--axis-capability" in h
    assert 'aria-disabled="true"' in h and "ui2-cta--disabled" in h and "登入與 Sheet 操作尚未開放" in h
    assert "已登入" not in h and "尚未登入" not in h and "狀態" not in h      # ⛔ 宣稱登入狀態、⛔ 放「狀態」欄
    assert drawer_account_html() == h                                        # 固定占位（零輸入、確定性）


def test_allowed_ui2_writes_unchanged_by_drawer():
    """C+JS 不新增 session key（D-17）：允許寫入的 key 仍是既有 5 個。"""
    from tests.test_ui2_real_feed import ALLOWED_UI2_WRITES
    assert ALLOWED_UI2_WRITES == frozenset({"ui2_page", "ui2_scenario", "ui2_account", "ui2_feed", "ui2_target_mode"})


def test_toggle_markup_a11y_contract():
    """A-1～A-3：`aria-label="主選單"`、☰ 符號 aria-hidden、role=switch、⛔ 靜態 aria-expanded、⛔ aria-controls。"""
    from src.ui2.shell.app import _TOGGLE_HTML
    assert 'role="switch"' in _TOGGLE_HTML and 'aria-label="主選單"' in _TOGGLE_HTML
    assert '<label for="ui2dr" class="ui2-dr-btn" aria-hidden="true">☰</label>' in _TOGGLE_HTML
    assert "aria-expanded" not in _TOGGLE_HTML and "aria-controls" not in _TOGGLE_HTML
    assert "✕" not in _TOGGLE_HTML and "關閉" not in _TOGGLE_HTML               # S-14：✕ 待線框定案，⛔ 默默加入


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
