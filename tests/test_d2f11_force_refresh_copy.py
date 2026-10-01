"""D2-f11（批 W2，收窄為只做 #4）：v1 個股頁「🔄 強制重抓」help 不再宣稱「保證下次載入抓最新資料」。

這顆按鈕只做 `st.cache_data.clear()` + pop 幾個 session 鍵，清不到 L1 失敗冷卻表
（`monthly_revenue_fetcher._single_fail_cooldown`，其 docstring 自陳此已知代價）——
冷卻期內按下不會重抓，原尾句不成立。修法為子句界純刪（K1：不新增字樣），剩下的前半句與實作一致。
"""
from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "ui" / "tabs" / "tab_stock.py"
_REMOVED = "保證下次載入抓最新資料"
_EXPECTED_HELP = "清除所有 @st.cache_data 快取 + 清 session 殘留值"


def _tree() -> ast.Module:
    return ast.parse(_SRC.read_text(encoding="utf-8"))


def _force_refresh_if() -> ast.If:
    for node in ast.walk(_tree()):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Call):
            for kw in node.test.keywords:
                if kw.arg == "key" and isinstance(kw.value, ast.Constant) and kw.value.value == "t2_force_refresh":
                    return node
    raise AssertionError("找不到 key='t2_force_refresh' 的 st.button")


def _help_of(node: ast.If) -> str:
    for kw in node.test.keywords:
        if kw.arg == "help":
            assert isinstance(kw.value, ast.Constant), "help 應為單一字串常數"
            return kw.value.value
    raise AssertionError("按鈕沒有 help")


def test_help_is_clause_boundary_deletion_of_original():
    help_txt = _help_of(_force_refresh_if())
    assert help_txt == _EXPECTED_HELP
    # 純刪：現行 help 必為原句在子句界（「，」）切掉尾句後的前綴，未新增任何字樣
    original = _EXPECTED_HELP + "，" + _REMOVED
    assert original.startswith(help_txt + "，")


def test_removed_clause_absent_from_any_string_constant():
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert _REMOVED not in node.value


def test_remaining_help_matches_button_body():
    """前提：剩下的說法（清 st.cache_data + 清 session 殘留值）與按鈕實作一致。"""
    body = ast.unparse(ast.Module(body=_force_refresh_if().body, type_ignores=[]))
    assert "st.cache_data.clear()" in body
    assert "st.session_state.pop(" in body


def test_premise_cache_clear_does_not_clear_single_revenue_cooldown():
    """前提（被刪尾句為何不成立）：`st.cache_data.clear()` 清不到單股月營收冷卻表。"""
    import src.data.stock.monthly_revenue_fetcher as mrf

    key = ("__d2f11_probe__", 12)
    mrf._single_fail_cooldown.clear()
    try:
        _hit, gen = mrf._single_fail_cooldown.begin(key)
        mrf._single_fail_cooldown.fail(key, gen, None)
        import streamlit as st

        st.cache_data.clear()
        hit, _ = mrf._single_fail_cooldown.begin(key)
        assert hit is not mrf._FC_NO_HIT, "冷卻期內 st.cache_data.clear() 後仍應命中冷卻"
    finally:
        mrf._single_fail_cooldown.clear()
