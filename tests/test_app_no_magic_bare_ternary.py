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


def test_screener_keeps_only_single_button_flow():
    """v19.111 選股網極簡版：只留最上方「開始選股」一顆按鈕。

    user 明確要求：優選(自動)→勾條件→一鍵出名單，**不要下方那些額外掃描按鈕**
    （進階 expander 的 render_shortage_screener / render_rs_leader_screener + 籌碼×6 picker）。
    這些若被改回去，選股網又會變回「上面選、下面還一堆按鈕」的複雜樣。本測試釘住不回退。
    """
    _src = _APP.read_text(encoding="utf-8")
    _banned = [
        "render_shortage_screener",   # 下方缺貨完整排行按鈕
        "render_rs_leader_screener",  # 下方抗跌RS完整排行按鈕
        "screener_run_deep",          # 籌碼×6 深篩 checkbox
        "render_tab_stock_picker",    # 手動候選 picker（已於簡易版移除）
    ]
    _hit = [b for b in _banned if b in _src]
    assert not _hit, (
        f"app.py 選股網又出現下方額外按鈕/picker：{_hit}。"
        "user 要極簡版——只留最上方單一『開始選股』，缺貨/抗跌RS 於按鈕內自動掃。"
    )
