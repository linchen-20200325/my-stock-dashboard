"""SA2-f12（2026-10-01）：「📖 憑什麼」葉2 來源卡的 unknown-status 分支，`Note.now` 裡的狀態字面值須先洗 glyph。

修前：`now=f"{SOURCE_UNKNOWN_NOW_HEAD}（L0 回 {probe.unknown_status!r}）"` 原樣插入 ⇒ L0 `last_status`
帶狀態 glyph 時 `Note.__post_init__` 直接 `ValueError`，且本卡建在 `_render_one()` 隔離之外。
修後：先過 `tab_today.scrub_state_glyphs()` SSOT；揭露句由 `why`（`_clean_reason(probe.error)`）承擔。
⚠️ 潛伏：以當下 L0 `shared/fetch_monitor.py` 只寫三種狀態、走不到 —— 下面全是**合成輸入**。
"""
from __future__ import annotations

import pytest

from shared.ui_state import UI_FAILED, UI_STATE_META
from src.ui.views import page_why as P

_GLYPHS: tuple[str, ...] = tuple(_g for _n, _g, _h in UI_STATE_META.values())
_DISCLOSURE = "原文裡的燈號符號已移除"


def _entry(status: str) -> dict:
    return {"category": "c", "frequency": "monthly", "last_status": status,
            "last_error": None, "last_rows": None, "last_ms": None, "last_called_at": None}


@pytest.mark.parametrize("glyph", _GLYPHS)
def test_unknown_status_with_a_state_glyph_builds_a_red_card(glyph):
    probe = P.probe_from_entry("fetch_x", _entry(f"怪{glyph}狀態"))
    assert probe.unknown_status == f"怪{glyph}狀態"          # 原文照存（工程師表仍看得到）
    card = P.build_source_card(probe)[0]                      # 修前：ValueError
    assert card.state == UI_FAILED
    assert glyph not in card.note.now
    assert card.note.now == f"{P.SOURCE_UNKNOWN_NOW_HEAD}（L0 回 '怪狀態'）"
    assert _DISCLOSURE in card.note.why                       # 洗過就要說（§1）
    assert P.v2_short_rows_key(card) == ("why.source.wall", P.SOURCE_UNKNOWN_NOW_HEAD)
    out = P.v2_card_html(*P.build_source_card(probe))         # v2 卡面也畫得出來
    assert "怪狀態" in out


def test_glyph_only_status_does_not_raise():
    probe = P.probe_from_entry("fetch_x", _entry("".join(_GLYPHS)))
    card = P.build_source_card(probe)[0]
    assert card.state == UI_FAILED
    assert not any(_g in card.note.now for _g in _GLYPHS)
    assert _DISCLOSURE in card.note.why


def test_plain_unknown_status_output_is_unchanged():
    """無 glyph 的字面值：輸出逐字同修前（只洗不改）。"""
    card = P.build_source_card(P.probe_from_entry("fetch_x", _entry("zz")))[0]
    assert card.note.now == "**這一盞的狀態本頁看不懂**（L0 回 'zz'）"
