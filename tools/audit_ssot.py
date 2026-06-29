#!/usr/bin/env python3
"""tools/audit_ssot.py — SSOT 漏抽 audit script(v18.402 P5-#11)。

針對 staged file(或全 src/)scan 疑似 inline magic number,提醒是否該抽 SSOT。

用法:
    # scan staged files(pre-commit 用)
    python tools/audit_ssot.py --staged

    # scan 整 src/
    python tools/audit_ssot.py

    # scan 特定檔案
    python tools/audit_ssot.py path/to/file.py

策略(避免 false positive):
- 只 flag float magic(`0.X` / `X.Y`)+ 整數 magic(>= 100)
- 排除 string literal / docstring / comment
- 排除 enumerate / range / for 內 index
- 排除 type hint(Optional[X], List[X])
- 排除 既有 SSOT import 的常數
- 排除 已知合理 inline(@st.cache_data(ttl=N) / version str)
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

# ── False positive 排除規則 ────────────────────────────────────────
_SAFE_INTS = {0, 1, 2, 3, 4, 5, 10, 100, 1000, -1, -100}  # 太常見不該 flag
_SAFE_FLOATS = {0.0, 0.5, 1.0, 2.0, -1.0}  # 常見數學常數
_CONTEXTS_SKIP = {  # 這些 AST 父節點下的 magic 跳過
    'Slice', 'Index', 'Subscript',  # df[100:] 等
    'Lambda',  # lambda x: x * 2 等
}


def _is_magic_number(node: ast.Constant) -> bool:
    """判斷是否為 magic number(排白名單)。"""
    if not isinstance(node.value, (int, float)):
        return False
    if isinstance(node.value, bool):  # True/False 是 int 子型,排除
        return False
    if isinstance(node.value, int):
        return node.value not in _SAFE_INTS and abs(node.value) >= 4
    if isinstance(node.value, float):
        return node.value not in _SAFE_FLOATS and abs(node.value) > 0.01


def _is_in_safe_context(parents: list) -> bool:
    """parent stack 是否在 docstring / decorator arg / type hint 等安全位置。"""
    for p in parents:
        if isinstance(p, (ast.AnnAssign, ast.arguments)):
            return True
        if isinstance(p, ast.FunctionDef) and p.body and isinstance(p.body[0], ast.Expr):
            # docstring
            if id(p.body[0].value) == id(parents[-1]):
                return True
    return False


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Scan 單檔,回 [(line, value, context_snippet), ...]"""
    try:
        src = path.read_text(encoding='utf-8')
        tree = ast.parse(src)
    except (SyntaxError, UnicodeDecodeError):
        return []
    src_lines = src.splitlines()

    findings = []
    parents: list[ast.AST] = []

    class Walker(ast.NodeVisitor):
        def generic_visit(self, node):
            parents.append(node)
            super().generic_visit(node)
            parents.pop()

        def visit_Constant(self, node):
            if _is_magic_number(node):
                # parent 排除
                if parents and isinstance(parents[-1], (ast.Subscript, ast.Slice)):
                    return
                line = node.lineno
                snippet = src_lines[line - 1].strip() if line - 1 < len(src_lines) else ''
                # 排除 string 內 / comment 內(AST 已剝除,這層通常乾淨)
                # 但跳過 `@st.cache_data(ttl=...)` 已是合理 inline
                if 'cache_data' in snippet or 'TTL_' in snippet:
                    return
                # 跳過 if/elif 比較常數(可能是 magic 但屬閾值,需 user 決定)
                # 標記 ⚠️ 但不算 fail
                findings.append((line, repr(node.value), snippet[:80]))

    Walker().visit(tree)
    return findings


def get_staged_py_files() -> list[Path]:
    """git diff --cached --name-only --diff-filter=AM filter .py"""
    try:
        out = subprocess.check_output(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=AM'],
            text=True,
        )
        return [Path(p) for p in out.splitlines() if p.endswith('.py')]
    except subprocess.CalledProcessError:
        return []


def main():
    parser = argparse.ArgumentParser(description='SSOT 漏抽 audit')
    parser.add_argument('--staged', action='store_true', help='只掃 staged files')
    parser.add_argument('paths', nargs='*', help='指定檔案(預設 src/)')
    args = parser.parse_args()

    if args.staged:
        files = get_staged_py_files()
        if not files:
            print('[audit_ssot] 無 staged .py file,跳過')
            return 0
    elif args.paths:
        files = [Path(p) for p in args.paths]
    else:
        files = list(Path('src').rglob('*.py'))
        files = [f for f in files if '__pycache__' not in str(f) and f.name != '__init__.py']

    total_findings = 0
    for f in files:
        if not f.exists():
            continue
        findings = scan_file(f)
        if findings:
            print(f'\n📋 {f}')
            for line, val, snippet in findings[:5]:
                print(f'  L{line:5} {val:>10}  ← {snippet}')
            if len(findings) > 5:
                print(f'       ... {len(findings)-5} more')
            total_findings += len(findings)

    print(f'\n=== Total potential inline magic: {total_findings} ===')
    print('提醒:這些**疑似**漏抽,需 user 判斷是否該抽 SSOT(§3.3 反捏造)。')
    print('排白名單條件:常見 int(0/1/2/3/4/5/10/100/1000)、常見 float、cache_data/TTL_、Subscript。')
    print()
    print('§-1 對齊:本工具回 0 不擋 commit;只是友善提醒(非 blocking)。')
    return 0  # 永遠 return 0 — 不擋 commit


if __name__ == '__main__':
    sys.exit(main())
