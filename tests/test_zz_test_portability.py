"""tests/ 可攜性守衛 — 讓測試在 Windows(cp950)與 Linux(UTF-8)行為一致。

病史(本守衛存在的理由,皆為 **Windows-only 假紅**,CI 綠但本機必紅):
1. `test_market_strategy.py::test_no_direct_requests_or_yfinance_import`
   用 `open(path)` 讀繁中原始碼 → Windows locale 預設 cp950 →
   `UnicodeDecodeError: 'cp950' codec can't decode byte 0x82`。
2. `test_review_fixes_v19_84.py::TestNestAsyncioRemoved::test_no_asyncio_consumers_repo_wide`
   用 `subprocess.run(["grep", ...])` → Windows 無 grep →
   `FileNotFoundError: [WinError 2]`。

本檔釘死三條規則,避免同款再長出來:
  A. `open()` / `io.open()` / `codecs.open()` 文字模式必須顯式 `encoding=`
     (binary 模式 `'rb'`/`'wb'` 不適用,豁免)。
  B. `Path.read_text()` / `Path.write_text()` 必須顯式 `encoding=`。
  C. 不得呼叫外部 shell 工具(grep / find / cat / ls / wc / sed …)。
     跑 `sys.executable`(Python 自己)不算外部工具,明確放行。

── 假陽性防護(本檔的設計重點) ─────────────────────────────────────
本 session 已被「字串掃描式守衛」的假紅燈擋過三個回合(註解或 docstring 裡
出現同樣字面就誤判)。因此本守衛:
  • **完全用 `ast`,不做字串比對** — 註解與 docstring 在 AST 裡根本不是 Call
    節點,天生不可能誤判;本檔自己內文寫滿 "grep"/"open(" 也不會自我引爆。
  • **判不準就不判**:mode 非字面值、參數用 `**kwargs` 展開、subprocess 的
    程式名非字面值(動態組出來)→ 一律**放行**,寧可漏也不製造假紅。
  • **失敗訊息印出 `檔:行` 與該行原文**,不是只說「有違規」。
  • 留一個白名單逃生口:違規行尾加 `# portability-ok` 即豁免(只會讓紅變綠,
    不會製造紅)。
"""
from __future__ import annotations

import ast
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO = _TESTS_DIR.parent

# 行尾豁免標記(白名單用途;只能讓紅變綠,無法製造假紅)
_PRAGMA = "# portability-ok"

# 需要 encoding= 的「開檔」呼叫(點記法全名;只收字面可判定的,避免誤傷
# webbrowser.open / gzip.open / zipfile.open 等同名但語意不同的 API)
_OPEN_CALLS = {"open", "io.open", "codecs.open"}

# 需要 encoding= 的 pathlib 文字讀寫
_TEXT_IO_METHODS = {"read_text", "write_text"}

# 一律禁止(必然是外部 shell)
_ALWAYS_BANNED = {"os.system", "os.popen"}

# 需檢查「第一個參數是不是外部程式名」的 subprocess 家族
_SUBPROCESS_CALLS = {
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
    "subprocess.getoutput",
    "subprocess.getstatusoutput",
}


# ══════════════════════════════════════════════════════════════
# AST helpers
# ══════════════════════════════════════════════════════════════

def _dotted_name(node: ast.AST) -> str | None:
    """把 `a.b.c` 形式的 expression 還原成 "a.b.c";還原不了回 None。

    還原不了的例子:`Path(x).open()`(base 是 Call)、`d["k"].run()`。
    這類一律回 None → 呼叫端放行,不猜。
    """
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _alias_map(tree: ast.AST) -> dict[str, str]:
    """收集 import 別名 → 正規模組/函式名。

    `import subprocess as sp`        → {"sp": "subprocess"}
    `from subprocess import run`     → {"run": "subprocess.run"}
    `from os import system as sys_`  → {"sys_": "os.system"}
    """
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    out[a.asname] = a.name
                else:
                    # `import os.path` 綁定的是 `os`,不是 `os.path`
                    top = a.name.split(".")[0]
                    out[top] = top
        elif isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            for a in node.names:
                out[a.asname or a.name] = f"{node.module}.{a.name}"
    return out


def _resolve(dotted: str | None, aliases: dict[str, str]) -> str | None:
    """把點記法首段換成正規名(`sp.run` → `subprocess.run`)。"""
    if dotted is None:
        return None
    head, _, rest = dotted.partition(".")
    base = aliases.get(head, head)
    return f"{base}.{rest}" if rest else base


def _has_kwarg(call: ast.Call, name: str) -> bool:
    return any(kw.arg == name for kw in call.keywords)


def _has_kwargs_unpack(call: ast.Call) -> bool:
    """有 `**kwargs` → encoding 可能藏在裡面,判不準,放行。"""
    return any(kw.arg is None for kw in call.keywords)


def _get_arg(call: ast.Call, idx: int, name: str) -> ast.AST | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    if len(call.args) > idx:
        return call.args[idx]
    return None


def _is_sys_executable(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "executable"
            and isinstance(node.value, ast.Name) and node.value.id == "sys")


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# ══════════════════════════════════════════════════════════════
# 單檔掃描
# ══════════════════════════════════════════════════════════════

def _scan(path: Path) -> list[str]:
    """回傳該檔違規清單,每筆為 "相對路徑:行號: [規則] 該行原文"。"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))
    aliases = _alias_map(tree)
    rel = path.relative_to(_REPO).as_posix()
    found: list[str] = []

    def _report(node: ast.AST, rule: str, detail: str) -> None:
        lineno = getattr(node, "lineno", 0)
        raw = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
        if _PRAGMA in raw:          # 白名單:只會讓紅變綠
            return
        found.append(f"{rel}:{lineno}: [{rule}] {detail}\n      → {raw.strip()}")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _has_kwargs_unpack(node):        # 判不準 → 放行
            continue

        resolved = _resolve(_dotted_name(node.func), aliases)

        # ── 規則 A:open() 文字模式必須帶 encoding ──────────────
        if resolved in _OPEN_CALLS:
            mode_node = _get_arg(node, 1, "mode")
            if mode_node is not None:
                mode = _const_str(mode_node)
                if mode is None:            # mode 非字面值 → 判不準,放行
                    continue
                if "b" in mode:             # binary 模式不吃 encoding → 豁免
                    continue
            if not _has_kwarg(node, "encoding"):
                _report(node, "A/open-no-encoding",
                        "open() 未指定 encoding,Windows 會用 cp950 解碼繁中原始碼")
            continue

        # ── 規則 B:Path.read_text/write_text 必須帶 encoding ──
        if (isinstance(node.func, ast.Attribute)
                and node.func.attr in _TEXT_IO_METHODS):
            if not _has_kwarg(node, "encoding"):
                _report(node, "B/read_text-no-encoding",
                        f"{node.func.attr}() 未指定 encoding")
            continue

        # ── 規則 C:不得呼叫外部 shell 工具 ────────────────────
        if resolved in _ALWAYS_BANNED:
            _report(node, "C/external-shell",
                    f"{resolved}() 一律不可用(Windows 無對應 shell)")
            continue

        if resolved in _SUBPROCESS_CALLS:
            if any(kw.arg == "shell" and getattr(kw.value, "value", None) is True
                   for kw in node.keywords):
                _report(node, "C/external-shell",
                        f"{resolved}(shell=True) 不可攜")
                continue
            argv = _get_arg(node, 0, "args")
            prog: str | None = None
            if isinstance(argv, (ast.List, ast.Tuple)):
                if not argv.elts:
                    continue
                first = argv.elts[0]
                if _is_sys_executable(first):   # 跑 Python 自己 → 放行
                    continue
                prog = _const_str(first)
            else:
                prog = _const_str(argv)         # 字串形式 = shell 指令
            if prog is None:                    # 動態組出來 → 判不準,放行
                continue
            _report(node, "C/external-shell",
                    f"呼叫外部程式 {prog!r};請改純 Python "
                    "(pathlib.Path.rglob + read_text 比對)")

    return found


def _all_test_files() -> list[Path]:
    return sorted(_TESTS_DIR.rglob("*.py"))


_CACHE: list[str] = []


def _all_violations() -> list[str]:
    """全 tests/ 掃描結果(整輪只算一次,三條規則共用)。"""
    if not _CACHE:
        _CACHE.extend(v for p in _all_test_files() for v in _scan(p))
        _CACHE.append("")           # sentinel:即使 0 違規也標記為已掃
    return [v for v in _CACHE if v]


# ══════════════════════════════════════════════════════════════
# 守衛本體
# ══════════════════════════════════════════════════════════════

def test_no_open_without_encoding():
    """tests/ 底下不得再出現「open( 未指定 encoding」。"""
    bad = [v for v in _all_violations() if "[A/open-no-encoding]" in v]
    assert not bad, (
        "以下讀寫檔未指定 encoding,Windows(cp950)會炸 UnicodeDecodeError。\n"
        "修法:open(path, encoding='utf-8')。\n\n" + "\n".join(bad))


def test_no_read_text_without_encoding():
    """tests/ 底下不得再出現「read_text()/write_text() 未指定 encoding」。"""
    bad = [v for v in _all_violations() if "[B/read_text-no-encoding]" in v]
    assert not bad, (
        "以下 Path 文字讀寫未指定 encoding,Windows(cp950)會炸。\n"
        "修法:p.read_text(encoding='utf-8')。\n\n" + "\n".join(bad))


def test_no_external_shell_tools():
    """tests/ 底下不得呼叫外部 shell 工具(grep / find / cat / ls / wc …)。"""
    bad = [v for v in _all_violations() if "[C/external-shell]" in v]
    assert not bad, (
        "以下測試依賴外部 shell 工具,Windows 沒有 → FileNotFoundError(WinError 2)。\n"
        "修法:改純 Python(pathlib.Path.rglob + read_text 掃描),\n"
        "禁止改成「Windows 就 skip」——那是藏問題不是修問題。\n\n" + "\n".join(bad))


# ══════════════════════════════════════════════════════════════
# 守衛的自我驗證 — 證明它抓得到真違規、且不會被註解/docstring 騙
# (§6:守衛自己也要有 3 個最容易出錯的輸入)
# ══════════════════════════════════════════════════════════════

def _scan_snippet(tmp_path: Path, code: str) -> list[str]:
    f = tmp_path / "sample_probe.py"
    f.write_text(code, encoding="utf-8")
    # _scan 用 relative_to(_REPO),tmp_path 不在 repo 下 → 改用暫時的 _REPO
    global _REPO
    _orig, _REPO = _REPO, tmp_path
    try:
        return _scan(f)
    finally:
        _REPO = _orig


class TestGuardItself:
    def test_catches_real_violations(self, tmp_path):
        out = _scan_snippet(tmp_path, (
            "import subprocess\n"
            "src = open('a.py').read()\n"
            "t = __import__('pathlib').Path('a').read_text()\n"
            "subprocess.run(['grep', '-r', 'x', 'src'])\n"
        ))
        assert any("[A/open-no-encoding]" in v for v in out), out
        assert any("[B/read_text-no-encoding]" in v for v in out), out
        assert any("[C/external-shell]" in v for v in out), out
        assert any("'grep'" in v for v in out), "訊息要指出是哪個外部程式"

    def test_not_fooled_by_comments_and_docstrings(self, tmp_path):
        """假陽性防護:註解 / docstring / 純字串裡寫同樣字面,不得誤判。"""
        out = _scan_snippet(tmp_path, (
            '"""本檔說明:不要用 open(path) 也不要 subprocess.run(["grep"])。"""\n'
            "# src = open('a.py').read()   ← 這行是註解\n"
            "MSG = 'open(path) / grep -rl asyncio src'\n"
            "HINT = \"改用 p.read_text() 前記得帶 encoding\"\n"
        ))
        assert out == [], f"註解/docstring/字串不該被判違規:{out}"

    def test_exempts_binary_mode_and_sys_executable(self, tmp_path):
        """binary 開檔與跑 Python 自己都不是違規,不可誤殺。"""
        out = _scan_snippet(tmp_path, (
            "import subprocess, sys\n"
            "with open('a.pkl', 'wb') as f:\n"
            "    f.write(b'x')\n"
            "with open('a.pkl', 'rb') as f:\n"
            "    f.read()\n"
            "subprocess.run([sys.executable, '-c', 'print(1)'])\n"
            "open('a.txt', encoding='utf-8').read()\n"
        ))
        assert out == [], f"合法寫法被誤判:{out}"

    def test_pragma_allows_opt_out(self, tmp_path):
        out = _scan_snippet(tmp_path, f"src = open('a.py').read()  {_PRAGMA}\n")
        assert out == [], f"{_PRAGMA} 白名單失效:{out}"
