"""v2 卡面「空白行」守衛（2026-09-26，獨立 QA 抓到、實跑重現）。

v2 卡面是一段交給 `st.markdown` 的 raw HTML。CommonMark 的 HTML 區塊**遇到空白行就結束**
⇒ 卡內任何一段含 `\\n\\n` 的文字（fact 值、摺疊區原文、`title=` 屬性）都會讓後半張卡
被當成 Markdown 段落重新解析：字漏到卡外、尾巴多一個 `">`。

實例（找標的頁）：L3 `get_ranked_picks` 的 note 原樣透傳成「L3 說明」fact，
總經為 bear／caution 時 `_apply_bear_market_filter` 會接上 `"\\n\\n⚠️ 總經為…"`。

每頁一條：造一張含 `\\n\\n` 的卡 → 走該頁 `_render_one_v2` → 抓送去 `st.markdown` 的字串：
  · 前提：`v2_card_html()` 的原始輸出**真的**含空白行（否則這條守衛沒守到東西）；
  · 送出去的字串**不含空白行**；
  · 送出去的字串與原始輸出「空白收成一格」後**逐字相同**（畫面上一個字都不差、沒丟字）；
  · 有 markdown-it-py 時：CommonMark 解析結果**只有一個 `html_block`**；
  · 長值的 `title=` 屬性裡，空白行被換成**恰好一個 `\n`**（釘住替換字串，⛔ 不是空格）。
空白行的寫法四種都測（CommonMark 的行尾含 `\r\n` 與單獨的 `\r`）：
`\n\n`、`\r\n\r\n`、`\r\r`、`\n\r\n`。
"""
from __future__ import annotations

import dataclasses
import html
import re

import pandas as pd
import pytest

from shared.ui_state import UI_LIVE
from src.services.fundamental_screener_service import _apply_bear_market_filter
from src.ui.views import page_find, page_hold, page_inspect, page_today, page_why
from src.ui.views._ui_kit import Card

#: 四種空白行寫法（CommonMark 行尾 = `\n`／`\r\n`／`\r`）。
_SEPS = ["\n\n", "\r\n\r\n", "\r\r", "\n\r\n"]
_SEP_IDS = ["LF", "CRLF", "CR", "LF-CRLF"]
_LONG_HEAD = "第一段" * 40
_LONG_TAIL = "第二段（在 title 與摺疊區裡）"
_PAGES = ["find", "hold", "inspect", "today", "why"]


class _FakeSt:
    """只收 `st.markdown` 的字串；`<style>` 那一次不算卡面。"""

    def __init__(self) -> None:
        self.session_state: dict = {}
        self.cards: list[str] = []

    def markdown(self, body: str, **_kw) -> None:
        if not body.startswith("<style>"):
            self.cards.append(body)


#: CommonMark 的空白行：兩個行尾之間只有空白（`\r\n` 算一個行尾，⛔ 不拆成兩個）。
_BLANK_RE = re.compile(r"(?:\r\n|\r(?!\n)|\n)[ \t]*(?:\r\n|\r(?!\n)|\n)")


def _has_blank_line(s: str) -> bool:
    return _BLANK_RE.search(s) is not None


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def _sent(monkeypatch, page, *args) -> str:
    fake = _FakeSt()
    monkeypatch.setattr(page, "st", fake)
    page._render_one_v2(*args)
    assert len(fake.cards) == 1, f"應只送出一張卡：{fake.cards!r}"
    return fake.cards[0]


def _assert_single_block(raw: str, sent: str) -> None:
    assert _has_blank_line(raw), "前提不成立：原始卡面沒有空白行，這條測試守不到東西"
    assert not _has_blank_line(sent), "送去 st.markdown 的卡面仍含空白行 ⇒ HTML 區塊會被截斷"
    # 空白收成一格後逐字相同 ⇒ 沒丟字、畫面相同（卡面／摺疊區皆無 pre／pre-wrap）
    assert _ws(raw) in _ws(sent)
    md = pytest.importorskip("markdown_it")
    tokens = md.MarkdownIt("commonmark").parse(sent)
    assert [t.type for t in tokens] == ["html_block"], [t.type for t in tokens]


class _Frame:
    def __init__(self, n: int) -> None:
        self._n = n

    def __len__(self) -> int:
        return self._n


def _find_args(note: str) -> tuple:
    req = page_find.ScreenRequest(submitted=True, factors=())
    card, facts = page_find.build_screen_result_card(
        page_find.ScreenResult(requested=True, df=_Frame(3), rows=3, survivors_n=10, note=note),
        req)
    assert ("L3 說明", note) in facts
    return card, facts


def _build(name: str, sep: str) -> tuple:
    """(page 模組, `_render_one_v2` 的引數, `v2_card_html` 原始輸出)。卡內含短值與長值兩段空白行。"""
    short = "甲" + sep + "乙"
    long = _LONG_HEAD + sep + _LONG_TAIL
    if name == "find":
        # 找標的頁的卡 facts 由 ScreenResult 組；L3 note 是唯一一段原樣透傳的長文字
        args = _find_args(short + " " + long)
        return page_find, args, page_find.v2_card_html(*args)
    if name == "today":
        band_label, thr_text, _, l4_err = page_today._load_l4_labels()
        tiles = page_today.build_indicator_tiles(
            page_today.MacroReadout(requested=False),
            band_label=band_label, thr_text=thr_text, l4_error=l4_err)
        tile = next(t for ts in tiles.values() for t in ts)   # {桶: (Tile, …)} → 第一張
        tile = dataclasses.replace(tile, facts=tile.facts + (("說明", short), ("長值", long)))
        return page_today, (tile,), page_today.v2_card_html(tile)
    page, registry = {"hold": (page_hold, page_hold.v2_hold),
                      "inspect": (page_inspect, page_inspect.v2_inspect),
                      "why": (page_why, page_why.v2_why)}[name]
    card = Card(key=sorted(registry.BLOCK_COLS)[0], label="測試卡", state=UI_LIVE, value="1")
    args = (card, (("說明", short), ("長值", long)))
    return page, args, page.v2_card_html(*args)


def test_find_bear_regime_l3_note_stays_inside_the_card(monkeypatch):
    """真實情境：總經 bear、沒有 RS 資料 → L3 note 接上 `\n\n⚠️ 總經為…`。"""
    _, note = _apply_bear_market_filter(pd.DataFrame(), "基礎說明", regime="bear", rs_rows=None)
    assert "\n\n" in note, "L3 的空頭 note 不再含空行 —— 本測試的真實情境需要更新"
    args = _find_args(note)
    sent = _sent(monkeypatch, page_find, *args)
    _assert_single_block(page_find.v2_card_html(*args), sent)
    assert "⚠️ 總經為「bear」" in sent


@pytest.mark.parametrize("sep", _SEPS, ids=_SEP_IDS)
@pytest.mark.parametrize("name", _PAGES)
def test_card_with_blank_line_in_fact_is_one_html_block(monkeypatch, name, sep):
    page, args, raw = _build(name, sep)
    _assert_single_block(raw, _sent(monkeypatch, page, *args))


@pytest.mark.parametrize("sep", _SEPS, ids=_SEP_IDS)
@pytest.mark.parametrize("name", _PAGES)
def test_title_attribute_keeps_exactly_one_newline(monkeypatch, name, sep):
    """釘住替換字串：`title=` 裡的空白行 → **恰好一個 `\n`**（⛔ 不是空格、⛔ 不是兩個）。"""
    page, args, raw = _build(name, sep)
    sent = _sent(monkeypatch, page, *args)
    titles = re.findall(r'title="([^"]*)"', sent)
    hit = [t for t in titles if html.escape(_LONG_TAIL, quote=True) in t]
    assert hit, f"長值沒有落進任何 title 屬性：{titles!r}"
    head, tail = html.escape(_LONG_HEAD, quote=True), html.escape(_LONG_TAIL, quote=True)
    assert any(head + "\n" + tail in t for t in hit), hit


@pytest.mark.parametrize("name", _PAGES)
def test_guard_is_a_no_op_without_blank_lines(name):
    page = {"find": page_find, "hold": page_hold, "inspect": page_inspect,
            "today": page_today, "why": page_why}[name]
    for s in ('<div class="blk">\n<span title="一\n二">甲 乙</span>\n</div>',
              "a\r\nb", "a\rb", "a\nb\r\nc\rd"):
        assert page._V2_BLANK_LINE_RE.sub("\n", s) == s
    assert page._V2_BLANK_LINE_RE.sub("\n", "a\n\nb\n \t\n\nc") == "a\nb\nc"
    for sep in _SEPS + ["\r\r\n", "\r \n"]:
        assert page._V2_BLANK_LINE_RE.sub("\n", "a" + sep + "b") == "a\nb", repr(sep)


@pytest.mark.parametrize("name", _PAGES)
def test_a_single_line_ending_is_never_touched(name):
    """單一個 CRLF／CR／LF（含前後空白）⛔ 不是空白行 ⇒ 逐 byte 不變；CRLF ⛔ 不得被拆成兩個行尾。"""
    page = {"find": page_find, "hold": page_hold, "inspect": page_inspect,
            "today": page_today, "why": page_why}[name]
    for s in ("\r\n", "a\r\nb", "a \r\n b", "a\r\nb\r\nc", "\r", "a\rb", "\n", "a\nb"):
        assert page._V2_BLANK_LINE_RE.sub("\n", s) == s, repr(s)


@pytest.mark.parametrize("name", _PAGES)
def test_regex_is_portable_across_python_versions(name):
    """Streamlit Cloud 的 Python 版本 repo 未釘 ⇒ ⛔ 不用 3.11 才有的 possessive 量詞／atomic group。"""
    page = {"find": page_find, "hold": page_hold, "inspect": page_inspect,
            "today": page_today, "why": page_why}[name]
    pat = page._V2_BLANK_LINE_RE.pattern
    assert not re.search(r"[?*+}]\+|\(\?>", pat), pat
