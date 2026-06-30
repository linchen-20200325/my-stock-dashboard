"""tests/test_app_tab_wiring.py — v18.439 回歸守衛。

production 事故:commit 94a257d「chore(dead): 刪 4 個 0-caller dead fn」誤把
app.py 內 `with tab_X: render_tab_X()` 4 個分頁渲染綁定當死碼刪掉,導致
總經 / 個股 / 個股組合 / 教學 四個分頁全空白(0 內容),且無測試攔到。

本守衛:app.py 必須綁定全部 10 個 tab,且 4 個 render entrypoint 確實被呼叫。
"""
from __future__ import annotations

import pathlib

_APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"


def _src() -> str:
    return _APP.read_text(encoding="utf-8")


# (tab 變數, 對應 render entrypoint)— 4 個 render-fn 型分頁
_RENDER_TABS = [
    ("tab_macro", "render_tab_macro"),
    ("tab_stock", "render_tab_stock"),
    ("tab_stock_grp", "render_stock_grp"),
    ("tab_edu", "render_tab_edu"),
]

# 其餘以 with-block 內聯渲染的分頁
_INLINE_TABS = ["tab_heatmap", "tab_screener", "tab_etf",
                "tab_etf_grp", "tab_etf_margin", "tab_diag"]


def test_render_fn_tabs_wired():
    """4 個 render-fn 分頁:既要 `with tab_X:` 又要呼叫 render_X()。"""
    src = _src()
    for tab, fn in _RENDER_TABS:
        assert f"with {tab}:" in src, f"app.py 未綁定 `with {tab}:`(回歸:該分頁會空白)"
        assert f"{fn}()" in src, f"app.py 未呼叫 `{fn}()`(回歸:該分頁會空白)"


def test_all_tabs_have_with_block():
    """全部 10 個 st.tabs 分頁都要有 with-block(沒有 = 空白分頁)。"""
    src = _src()
    for tab in [t for t, _ in _RENDER_TABS] + _INLINE_TABS:
        assert f"with {tab}:" in src, f"app.py 缺 `with {tab}:` → 該分頁空白"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
