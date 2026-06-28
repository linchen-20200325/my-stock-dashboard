"""v18.329 PR-1 守衛：台股總經「正常更新」改 scoped cache clear（對齊基金）。

原 `_on_refresh_click` 每次點都 `st.cache_data.clear()` 全站核爆 → 炸掉個股 /
ETF / 健診快取，導致更新總經後全站冷啟重抓（又慢又奇怪）。PR-1 拆成：
- `_on_refresh_click`（正常）→ 只 `_macro_session_reset()` scoped 清總經 session_state。
- `_on_force_clear_click`（🆕 強制重抓）→ 才做 pkl + st.cache_data + proxy 全清。

測試以 AST node 偵測「真實呼叫」，不用字串比對（避免被註解 / docstring 內提及誤判）。
"""
from __future__ import annotations

import ast

_TARGETS = ("_on_refresh_click", "_on_force_clear_click", "_macro_session_reset")


def _func_nodes(p="src/ui/tabs/tab_macro.py"):
    tree = ast.parse(open(p, encoding="utf-8").read())
    return {
        n.name: n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef) and n.name in _TARGETS
    }


def _calls_cache_data_clear(node) -> bool:
    """偵測 `<...>.cache_data.clear(...)` 真實呼叫（非字串提及）。"""
    for n in ast.walk(node):
        if (isinstance(n, ast.Attribute) and n.attr == "clear"
                and isinstance(n.value, ast.Attribute)
                and n.value.attr == "cache_data"):
            return True
    return False


def _calls_name(node, name) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == name:
                return True
            if isinstance(f, ast.Attribute) and f.attr == name:
                return True
    return False


class TestScopedNormalRefresh:
    def test_three_callbacks_exist(self):
        b = _func_nodes()
        for t in _TARGETS:
            assert t in b, f"缺 {t}"

    def test_normal_refresh_does_not_nuke_global_cache(self):
        b = _func_nodes()
        assert not _calls_cache_data_clear(b["_on_refresh_click"]), \
            "正常更新不得 st.cache_data.clear()（會炸全站快取）"
        assert not _calls_name(b["_on_refresh_click"], "_pkl_clear_all")
        assert not _calls_cache_data_clear(b["_macro_session_reset"])
        # 正常更新走 scoped reset
        assert _calls_name(b["_on_refresh_click"], "_macro_session_reset")

    def test_force_clear_does_full_nuke(self):
        b = _func_nodes()
        f = b["_on_force_clear_click"]
        assert _calls_cache_data_clear(f), "強制重抓才做全清"
        assert _calls_name(f, "_pkl_clear_all")
        assert _calls_name(f, "_macro_session_reset")  # 同時清總經 session_state

    def test_global_cache_clear_only_in_force(self):
        """全檔真實 st.cache_data.clear() 呼叫只能有 1 處（強制重抓）。"""
        tree = ast.parse(open("src/ui/tabs/tab_macro.py", encoding="utf-8").read())
        cnt = sum(
            1 for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and n.attr == "clear"
            and isinstance(n.value, ast.Attribute) and n.value.attr == "cache_data"
        )
        assert cnt == 1, f"預期 1 處 cache_data.clear()，實際 {cnt}"


class TestTwoButtons:
    def test_both_button_keys_present(self):
        src = open("src/ui/tabs/tab_macro.py", encoding="utf-8").read()
        assert "key='cl_refresh'" in src, "缺正常更新按鈕"
        assert "key='cl_force_refresh'" in src, "缺強制重抓按鈕"
        assert "on_click=_on_refresh_click" in src
        assert "on_click=_on_force_clear_click" in src
