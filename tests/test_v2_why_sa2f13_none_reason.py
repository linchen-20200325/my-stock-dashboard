"""SA2-f13（2026-10-01）：`None` 不得被印成字面「None」。

修前：`tab_today.scrub_state_glyphs()` 對輸入做 `str(text)` ⇒ `None` 變成 "None"，
`page_why._clean_reason(None)` 回 "None"、各頁 `_error_why(src, None)` 回「…拋出例外：None」。
修後：`None` 回空字串，交給呼叫端**既有**的兜底字（`UNKNOWN_ERROR_TEXT` 等）—— 無新文案（K1）。
"""
from __future__ import annotations

import pytest

from src.ui.tabs import tab_today as T
from src.ui.views import page_find, page_hold, page_inspect, page_today
from src.ui.views import page_why as P


def test_scrub_state_glyphs_none_is_empty():
    assert T.scrub_state_glyphs(None) == ("", 0)
    assert T.scrub_state_glyphs("abc") == ("abc", 0)          # 其餘照舊
    assert T.scrub_state_glyphs(0) == ("0", 0)                 # 非 None 的假值照舊 str()


def test_clean_reason_none_falls_back_to_existing_text():
    assert P._clean_reason(None) == P.UNKNOWN_ERROR_TEXT
    T.Note(now="x", why=P._clean_reason(None), where="y")


def test_upstream_error_why_none():
    why = T.upstream_error_why(None)
    assert "None" not in why and why.endswith("（上游沒有給訊息）")


@pytest.mark.parametrize("mod", [P, page_find, page_hold, page_inspect, page_today])
def test_page_error_why_none_never_prints_none(mod):
    why = mod._error_why("來源X", None)
    assert "None" not in why, why
