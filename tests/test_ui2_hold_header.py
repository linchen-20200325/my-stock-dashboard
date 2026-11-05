"""💼 持股頁桌機首屏重排（Wireframes §4.2／W-11；客戶 Q3 核准）守衛。

只重排既有元素：DOM 內容／錨點不增不減、CTA 仍 disabled、手機版面規則只有「補回舊間距」一條、桌機規則全在 ≥769px media 內。
"""
from __future__ import annotations

import re

import pytest

from shared.ui2_contract.pages import P4_HOLD
from src.services.ui2.preview_feed import get_preview_page_vm
from src.ui2.components import html as H
from src.ui2.shell.css import CSS
from src.ui2.views import _page, hold

SCENARIOS = ("cold", "loaded", "missing", "stale", "unavailable", "not_evaluated")


def _render(monkeypatch, vm, fn) -> list[str]:
    out: list[str] = []
    monkeypatch.setattr(_page.st, "markdown", lambda html, **kw: out.append(html))
    monkeypatch.setattr(_page.st, "expander", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no expander on hold")), raising=False)
    fn(vm)
    return out


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_hold_html_is_old_html_wrapped_not_changed(monkeypatch, scenario):
    """舊版＝title 與 first_screen 兩個 markdown；新版＝同內容包進 `ui2-h-l1` 一個 markdown（內容逐字相同）。"""
    vm = get_preview_page_vm(P4_HOLD, scenario)
    old_title = _render(monkeypatch, vm, _page.render_title)
    new = _render(monkeypatch, vm, hold.render)
    old_fs = H.first_screen_html(vm.context.first_screen)
    assert len(old_title) == 1
    assert new[0] == '<div class="ui2-h-l1">' + old_title[0] + old_fs + "</div>"


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_anchors_and_cta_preserved(monkeypatch, scenario):
    vm = get_preview_page_vm(P4_HOLD, scenario)
    h = _render(monkeypatch, vm, hold.render)[0]
    assert re.findall(r'data-ui2-q="(\w+)"', h) == ["q1", "ctx", "ctx", "q2", "q3", "q4"]
    assert 'data-ui2-page="p4_hold"' in h
    cta = vm.context.first_screen.primary_cta
    assert cta.enabled is False and f'aria-disabled="true"' in h and cta.label in h
    assert not re.search(r"<a\s|href=|onclick|<button|<form|<input", h, re.I)


_DESK = re.compile(r"@media \(min-width:769px\)\{\n  \.ui2-h-l1\{position:relative\}.*?\n\}\n", re.S)


def _outside_desktop_h_rules(css: str) -> list[str]:
    """桌機 media 區塊以外、含 `.ui2-h-l1` 的規則（去註解後）。"""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = _DESK.sub("", css)
    return [r.strip() for r in re.findall(r"[^{}\n]*\.ui2-h-l1[^{}]*\{[^}]*\}", css)]


def test_desktop_rules_only_inside_min_width_media():
    assert _DESK.search(CSS), "桌機 media 區塊不存在"
    assert _outside_desktop_h_rules(CSS) == [".ui2-h-l1>.ui2-qa{margin-top:16px}"]   # 手機唯一規則＝補回舊間距


def test_qa_stays_a_real_box_and_cta_is_in_header_row():
    desk = _DESK.search(CSS).group(0)
    assert "display:contents" not in desk                      # 量測 qa_top 需要真實盒（measure_viewport 標題不重疊檢查）
    assert re.search(r'\[data-ui2-q="q4"\]\{position:absolute;top:0;right:0', desk)
    for sel in ('ctx"]:nth-child(2)', 'ctx"]:nth-child(3)', 'q1"]'):
        assert sel in desk
    assert desk.count("grid-row:1") == 3                       # 三 tile 同一列


def test_mutation_desktop_rule_leaking_to_mobile_is_detected():
    leaked = CSS.replace("@media (min-width:769px){\n  .ui2-h-l1{position:relative}",
                         ".ui2-h-l1{position:relative}\n@media (min-width:769px){", 1)
    assert leaked != CSS
    assert _outside_desktop_h_rules(leaked) != [".ui2-h-l1>.ui2-qa{margin-top:16px}"]
