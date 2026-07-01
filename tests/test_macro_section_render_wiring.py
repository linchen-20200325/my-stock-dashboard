"""tests/test_macro_section_render_wiring.py — v18.447 回歸守衛。

production 事故:「總經」分頁全頁炸掉,顯示
`NameError: name 'render_section_mid' is not defined`(被 v18.440 per-tab 隔離器擋住,
其他分頁不受影響,但總經分頁空白)。

根因:`section_long.py`(Section 3 長期桶)結尾殘留一行從未清乾淨的
`render_section_mid(...)` 呼叫 —— 這是 F-7.1 B-4 抽出 section_mid.py 時留下的雜物;
真正的呼叫鏈其實已經在 `tab_macro.py`(orchestrator)裡正確存在(`render_section_long`
接著 `render_section_mid`,R3 已補回並加註解)。`section_long.py` 從未 import
`render_section_mid`,故一執行到那行就 NameError。

若直接補 import 而非刪除該行,會變成 render_section_mid 被呼叫兩次(一次在
section_long.py 內部、一次在 tab_macro.py orchestrator)→ UI 重複渲染。正確修法是
刪除 section_long.py 裡的雜物呼叫,讓 orchestrator(tab_macro.py)保留唯一呼叫點
(§8.2:L5 section 之間不應互相呼叫渲染,應由上層 orchestrator 依序呼叫)。

本守衛:
1. section_long.py 原始碼不得再出現對 render_section_mid 的呼叫(防止雜物復發)。
2. tab_macro.py 仍須依序呼叫 render_section_long → render_section_mid(確保
   orchestrator 唯一呼叫點還在,沒有連 tab_macro.py 那邊的呼叫都被誤刪)。
"""
from __future__ import annotations

import pathlib

_MACRO_DIR = pathlib.Path(__file__).resolve().parents[1] / "src" / "ui" / "tabs" / "macro"
_SECTION_LONG = _MACRO_DIR / "section_long.py"
_TAB_MACRO = pathlib.Path(__file__).resolve().parents[1] / "src" / "ui" / "tabs" / "tab_macro.py"


def _src(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_section_long_does_not_call_render_section_mid():
    """section_long.py 不得殘留呼叫 render_section_mid(那是 orchestrator 的責任;
    section_long.py 從未 import 它,呼叫必炸 NameError)。"""
    src = _src(_SECTION_LONG)
    assert "render_section_mid(" not in src, (
        "section_long.py 出現 render_section_mid( 呼叫 —— 這曾導致總經分頁全頁 "
        "NameError(§8.2:L5 section 不應互相呼叫渲染,交給 orchestrator)。"
    )


def test_tab_macro_still_chains_long_then_mid():
    """orchestrator(tab_macro.py)須依序呼叫 render_section_long 接著 render_section_mid,
    確保刪除 section_long.py 內雜物呼叫後,真正的呼叫鏈仍然存在(沒有連正確的那份也被
    誤刪 —— 那樣總經拼圖區塊會直接消失,而非丟 NameError)。"""
    src = _src(_TAB_MACRO)
    assert "render_section_long(" in src, "tab_macro.py 缺 render_section_long 呼叫"
    assert "render_section_mid(" in src, "tab_macro.py 缺 render_section_mid 呼叫"
    _idx_long = src.index("render_section_long(")
    _idx_mid = src.index("render_section_mid(")
    assert _idx_long < _idx_mid, "render_section_long 應先於 render_section_mid 呼叫"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
