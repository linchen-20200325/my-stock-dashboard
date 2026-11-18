"""New UI2 a11y 三項最小修（DEC-197；GPT §B）離線守衛：解析 `css.py::CSS` 與標題 renderer 原始碼，不需瀏覽器。

- D1：disabled CTA 游標——`.ui2-ctawrap .ui2-cta.ui2-cta--disabled{cursor:not-allowed}` 存在，且 specificity 嚴格大於
  單一 class 規則（才壓得過 Streamlit 的 `button:not(:disabled)` pointer 規則）。
- D2：標題語意——頁標題 `role="heading" aria-level="1"`、區塊標題 `role="heading" aria-level="2"`；屬性放在 class **之前**
  （`tests/test_ui2_p3_evidence_preservation.py` 以子字串 `ui2-section-title">{t}<` 比對）；兩個頁標題 renderer 逐位元組相同。
- D3：`[data-testid="stMain"]:focus-visible` 有 2px solid outline，顏色用既有 token（不用字面色碼）。
真瀏覽器行為見 `tests/test_ui2_drawer_browser.py`（marker `ui2_browser`）。
"""
from __future__ import annotations

import re
from pathlib import Path

from src.ui2.components import html as H
from src.ui2.shell.css import CSS

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "ui2"


_CSS_NC = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)   # 去註解後再解析（註解內可能提到選擇器）


def _rules(selector_re: str) -> list[tuple[str, str]]:
    return re.findall(r"(?:^|})\s*(" + selector_re + r")\s*\{([^}]*)\}", _CSS_NC, re.M)


def _specificity(sel: str) -> tuple[int, int, int]:
    """(id, class/attr/pseudo-class, type)——只處理本守衛用到的簡單選擇器。"""
    a = len(re.findall(r"#[\w-]+", sel))
    b = len(re.findall(r"\.[\w-]+|\[[^\]]+\]|:(?!not\b)[\w-]+(?:\([^)]*\))?", sel))
    c = len(re.findall(r"(?:^|[\s>+~])[a-zA-Z][\w-]*", sel))
    return a, b, c


# ── D1 ─────────────────────────────────────────────────────────────
def test_d1_disabled_cta_not_allowed_rule_exists():
    hits = [(s, b) for s, b in _rules(r"[^{}]*ui2-cta--disabled[^{}]*") if "cursor:not-allowed" in b.replace(" ", "")]
    assert hits, "css.py 缺 disabled CTA 的 cursor:not-allowed 規則（A11Y-D1）"
    sel = hits[0][0].strip()
    assert sel == ".ui2-ctawrap .ui2-cta.ui2-cta--disabled", sel


def test_d1_specificity_beats_single_class_pointer_rule():
    # Streamlit 的 `button:not(:disabled){cursor:pointer}`＝(0,1,1)（:not 取其引數的 specificity）；本規則須嚴格大於。
    assert _specificity(".ui2-ctawrap .ui2-cta.ui2-cta--disabled") > (0, 1, 1)
    assert _specificity(".ui2-ctawrap .ui2-cta.ui2-cta--disabled") == (0, 3, 0)


def test_d1_disabled_cta_stays_non_interactive_markup():
    from shared.ui2_contract.models import CtaVM
    out = H.cta_html(CtaVM(label="x", enabled=False, disabled_reason="r"))
    assert 'aria-disabled="true"' in out and "ui2-cta--disabled" in out
    assert "<button" not in out and "onclick" not in out and "href=" not in out


# ── D2 ─────────────────────────────────────────────────────────────
def test_d2_page_title_has_level1_heading_before_class():
    out = H.page_title_html("p4_market", "loaded", "T")
    assert out.startswith('<div role="heading" aria-level="1" class="ui2-pagetitle" '), out


def test_d2_page_title_renderers_are_byte_identical():
    """`_page.render_title` 與 `html.page_title_html` 註解宣告逐字相同；以 st.markdown spy 取 render_title 的實際輸出。"""
    from shared.ui2_contract.models import PageVM  # noqa: F401
    from src.ui2.views import _page as P

    captured: list[str] = []
    orig = P._md
    P._md = lambda s: captured.append(s)
    try:
        class _VM:
            page_id, scenario_id, title = "p4_hold", "loaded", "持股 <T>"
        P.render_title(_VM())
    finally:
        P._md = orig
    assert captured == [H.page_title_html("p4_hold", "loaded", "持股 <T>")]


def test_d2_every_section_title_site_is_level2_heading():
    total = 0
    for f in sorted(SRC.rglob("*.py")):
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r'<div[^>]*class="ui2-section-title"[^>]*>', t):
            total += 1
            assert m.group(0) == '<div role="heading" aria-level="2" class="ui2-section-title">', (f.name, m.group(0))
    assert total == 7, total   # html.py 5 + _page.py 1 + data.py 1；增減站點時須同步確認其帶 level 2


def test_d2_every_pagetitle_site_is_level1_heading():
    total = 0
    for f in sorted(SRC.rglob("*.py")):
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r'<div[^>]*class="ui2-pagetitle"', t):
            total += 1
            assert m.group(0).startswith('<div role="heading" aria-level="1" class="ui2-pagetitle"'), (f.name, m.group(0))
    assert total == 2, total   # render_title＋page_title_html


def test_d2_exactly_one_level1_in_each_page_html_source():
    # 區塊標題不得誤用 level 1
    for f in sorted(SRC.rglob("*.py")):
        t = f.read_text(encoding="utf-8")
        assert not re.search(r'aria-level="1"[^>]*ui2-section-title', t), f.name


# ── D3 ─────────────────────────────────────────────────────────────
def test_d3_stmain_focus_visible_rule_exists_with_token_color():
    hits = _rules(r'\[data-testid="stMain"\]:focus-visible')
    assert hits, "css.py 缺 [data-testid=\"stMain\"]:focus-visible（A11Y-D3：第一個 Tab 停駐點需可見焦點框）"
    body = hits[0][1].replace(" ", "")
    assert "outline:2pxsolidvar(--ui2-nav-fg)" in body, body
    assert "outline-offset:-2px" in body, body
    assert "--ui2-nav-fg:" in CSS   # token 本身仍定義（不退回字面色碼）


def test_d3_rule_documents_streamlit_testid_exception():
    i = CSS.index('[data-testid="stMain"]:focus-visible')
    assert "data-testid" in CSS[max(0, i - 600):i] and "A11Y-D3" in CSS[max(0, i - 600):i]
