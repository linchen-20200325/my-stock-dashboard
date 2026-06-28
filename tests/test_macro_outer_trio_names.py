"""Regression: 外層 trio executor NameError 全頁炸（台股無法使用）。

User 2026-06-28 回報：總經 tab 一鍵更新時整頁炸 NameError，traceback 停在
`tab_macro.py` 的 `except (TimeoutError, _ConcFutTimeout):`。

根因：外層 trio executor（_job_m1b / _job_bias / _job_macro 並發）用了 `_asc_mc`
（L「for _fut2 in _asc_mc(...)」）與 `_ConcFutTimeout`（except tuple），但這兩個名字
原本只在巢狀函式 `_job_macro` 內部賦值（local），外層 `render_tab_macro` scope 沒有。
平常 3 job 在 timeout 內跑完就不評估 except → 不炸；一旦外層 200s timeout 真的觸發，
`_asc_mc` 先 NameError、評估 except tuple 時 `_ConcFutTimeout` 再 NameError → traceback
停在 except 行，全頁掛掉。

修法：在 `render_tab_macro` 函式入口（無條件執行的 late-imports 區）定義
`_asc_mc = as_completed` 與 `from concurrent.futures import TimeoutError as _ConcFutTimeout`。
本測試靜態守衛：這兩個名字必須綁在 `render_tab_macro` 自身 scope（排除巢狀 def），
否則 timeout 路徑會再次 NameError 炸頁。
"""
from __future__ import annotations

import ast


def _render_tab_macro_def() -> ast.FunctionDef:
    tree = ast.parse(open("tab_macro.py", encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "render_tab_macro":
            return node
    raise AssertionError("找不到 render_tab_macro def")


def _names_bound_in_own_scope(fn: ast.FunctionDef) -> set[str]:
    """蒐集直接綁在 fn 自身 scope 的名字（import as / 一般指派），
    **不下探**巢狀 FunctionDef（那些是 _job_macro 等的 local，不算外層可見）。"""
    bound: set[str] = set()

    class _Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):  # noqa: N802
            if node is fn:
                for child in node.body:
                    self.visit(child)
            # 巢狀 def：不下探（其 local 名字不屬外層 scope）

        visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

        def visit_Import(self, node):  # noqa: N802
            for a in node.names:
                bound.add(a.asname or a.name.split(".")[0])

        def visit_ImportFrom(self, node):  # noqa: N802
            for a in node.names:
                bound.add(a.asname or a.name)

        def visit_Assign(self, node):  # noqa: N802
            for tgt in node.targets:
                for n in ast.walk(tgt):
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                        bound.add(n.id)

    _Visitor().visit(fn)
    return bound


def test_outer_trio_names_bound_in_render_scope():
    fn = _render_tab_macro_def()
    bound = _names_bound_in_own_scope(fn)
    for name in ("_asc_mc", "_ConcFutTimeout"):
        assert name in bound, (
            f"{name} 必須綁在 render_tab_macro 自身 scope（外層 trio executor L~2185/2191 用得到）；"
            f"否則 200s timeout 觸發 except 時會 NameError 全頁炸。"
        )


def test_concfut_alias_points_to_concurrent_futures_timeouterror():
    """確認 _ConcFutTimeout 來自 concurrent.futures.TimeoutError（非別的東西誤綁）。"""
    src = open("tab_macro.py", encoding="utf-8").read()
    assert "from concurrent.futures import TimeoutError as _ConcFutTimeout" in src
