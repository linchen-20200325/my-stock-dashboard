"""tests/test_app_no_magic_bare_ternary.py — 守 app.py 不得有「裸三元表達式語句」（v19.87）。

真事故：選股網 AI 卡寫成 `st.markdown(x) if c else st.info(y)`（裸三元表達式），
Streamlit 腳本的 magic 會把裸表達式自動 st.write() → 執行期炸 SyntaxError（整頁掛）。
必須用 if/else 語句。本測試 AST 掃描 app.py，禁止 `Expr(value=IfExp)`。
"""
from __future__ import annotations

import ast
import pathlib

_APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"


def test_app_has_no_bare_ternary_expression_statement():
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.IfExp)
    ]
    assert not offenders, (
        f"app.py:{offenders} 有『裸三元表達式語句』——Streamlit magic 會 st.write() 它 → "
        "執行期炸整頁。改用 if/else 語句。"
    )


def test_app_compiles():
    ast.parse(_APP.read_text(encoding="utf-8"))
