"""New UI2 Batch 2（presentation）：W-1 導覽保真、共用元件三軸呈現、第一屏版面與 viewport 判定器。

三塊：
1. **W-1 Navigation Fidelity**（`NUI2-NAV-W1-FIDELITY`）：導覽恰四頁、手機底部固定 53px／桌機左側、
   當前頁非只靠顏色、內容底部留白不被導覽遮住（靜態＋AppTest；真瀏覽器量測見 `tests/ui2_viewport`）。
2. **共用 Presentation Components**：資料五態／判定結果／capability 三軸的**文字＋樣式**互不混用、
   每個態都有文字標示（⛔ 只靠顏色）、source／as_of 為 field-level、⛔ 全域假更新時間、CTA 在 Preview 不可行動。
3. **viewport 判定器**（`tests/ui2_viewport/measure_viewport.evaluate`）：純函式；對真實量測必須綠、
   對刻意注入違規的量測 dict 必須紅（= 判定器有牙）。真瀏覽器量測為 slow（`-m slow`）。

⛔ 本檔不改任何既有守衛斷言；語意護欄沿用 DEC-124（三軸）、Freeze §4／§5。
"""
from __future__ import annotations

import copy
import pathlib
import re

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.models import (
    CapabilityState, CtaVM, FieldState, FieldVM, FreshnessInfo, JudgementState, status_prefixes_for,
)
from shared.ui2_contract.pages import PAGE4_LABELS, PAGE_IDS, SCENARIO_IDS
from src.services.ui2.preview_feed import get_preview_page_vm
from src.ui2.components import html as H
from src.ui2.shell.css import CSS
from tests.ui2_viewport import measure_viewport as MV

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SRC = (ROOT / "src" / "ui2" / "shell" / "app.py").read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════
# 1. W-1 導覽（靜態契約；真位置由瀏覽器量測證明）
# ════════════════════════════════════════════════════════════════════
def test_w1_nav_is_exactly_four_fixed_pages_no_fifth():
    assert len(PAGE_IDS) == 4
    assert [PAGE4_LABELS[p] for p in PAGE_IDS] == list(MV.NAV_LABELS) == ["📊 市場", "🎯 標的", "💼 持股", "👤 我的"]


def test_w1_nav_is_keyed_container_with_ui2_prefixed_radio():
    """導覽＝`st.container(key=ui2_nav)` 內的 `st.radio(key=ui2_page)`；session key 限 ui2_ 前綴。"""
    assert 'KEY_NAV = "ui2_nav"' in APP_SRC and "st.container(key=KEY_NAV)" in APP_SRC
    assert 'KEY_PAGE = "ui2_page"' in APP_SRC and "key=KEY_PAGE" in APP_SRC
    for forbidden in ("st.sidebar", "st.navigation", "st.tabs(", "st.page_link", "st.Page("):
        assert forbidden not in APP_SRC, f"導覽不得改用 {forbidden}（第五頁／多頁路由風險）"


def _css_block(media: str) -> str:
    m = re.search(re.escape(media) + r"\s*\{(.*?)\n\}", CSS, re.S)
    assert m, f"CSS 缺 {media} 區塊"
    return m.group(1)


def test_w1_mobile_nav_is_bottom_fixed_53px():
    block = _css_block("@media (max-width:768px)")
    assert ".st-key-ui2_nav{left:0;right:0;bottom:0;height:53px" in block
    assert f"height:{MV.NAV_MOBILE_H}px" in block              # 與量測腳本／Freeze §16 的 53px 同源
    assert ".st-key-ui2_nav{position:fixed;" in CSS                 # 基礎規則：固定定位
    assert "padding-bottom:5rem" in block                        # 內容底部留白（>53px），不被底部列遮住


def test_w1_desktop_nav_is_left_column():
    block = _css_block("@media (min-width:769px)")
    assert ".st-key-ui2_nav{top:0;left:0;bottom:0;" in block
    assert 'flex-direction:column' in block                      # 四項垂直排列
    assert "padding-left:12.5rem" in block                       # 內容讓出左欄，不被擠壓／遮住


def test_w1_current_page_is_marked_beyond_color():
    """當前頁：粗體＋『● 』符號前綴＋色條（border，非僅文字色）；原生 radio `checked` 為語意狀態。"""
    assert 'p::before{content:"● "' in CSS
    assert "label:has(input:checked){font-weight:700}" in CSS
    assert "border-top-color:currentColor" in CSS and "border-left-color:currentColor" in CSS


def test_w1_nav_css_does_not_depend_on_streamlit_internal_classes():
    nav_css = re.sub(r"/\*.*?\*/", "", CSS[CSS.index("/* ── W-1"):], flags=re.S)     # 註解可提及，規則不可依賴
    assert "emotion" not in nav_css and "data-baseweb" not in nav_css and "stRadioOption" not in nav_css, \
        "導覽 CSS 依賴 Streamlit 內部 class 會在 1.56／1.59 間失效"


def test_w1_page_switch_still_works_via_app_test():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60).run(timeout=60)
    assert not at.exception
    for page in PAGE_IDS:
        at.radio(key="ui2_page").set_value(page).run(timeout=60)
        assert not at.exception
        assert at.session_state["ui2_page"] == page
        blob = "\n".join(m.value for m in at.markdown)
        assert f'data-ui2-page="{page}"' in blob


# ════════════════════════════════════════════════════════════════════
# 2. 共用元件：三軸呈現
# ════════════════════════════════════════════════════════════════════
def _field(state, text, *, cap=CapabilityState.PROVIDED, value=None, detail=None):
    return FieldVM("x", state, value, text, detail, FreshnessInfo("FAKE-ASOF", "FAKE"), capability=cap)


def _axis_samples() -> list[tuple[str, FieldVM]]:
    """每個資料態、判定結果、capability marker 各一個樣本（含全部允許字樣）。"""
    out: list[tuple[str, FieldVM]] = []
    for st in FieldState:
        if st is FieldState.OK:
            continue
        for txt in T.ALLOWED_STATUS_PREFIXES[st.value]:
            val = "1" if st is FieldState.STALE else None
            out.append(("data", _field(st, txt, value=val)))
    for txt in T.JUDGEMENT_STATUS_PREFIXES["undeterminable"]:
        out.append(("judgement", _field(JudgementState.UNDETERMINABLE, txt)))
    for txt in T.CAPABILITY_STATUS_PREFIXES["not_provided"]:
        out.append(("capability", _field(None, txt, cap=CapabilityState.NOT_PROVIDED)))
    return out


@pytest.mark.parametrize("axis,field", _axis_samples(), ids=lambda v: v if isinstance(v, str) else v.status_text)
def test_every_non_ok_state_has_visible_text_and_axis_style(axis, field):
    out = H.status_chip_html(field)
    assert field.status_text in re.sub(r"<[^>]+>", "", out), "狀態字樣必須在可見文字中（⛔ 只靠顏色）"
    assert f'data-axis="{axis}"' in out
    assert H.AXIS_CLASS[axis] in out
    for other, cls in H.AXIS_CLASS.items():                      # 軸別樣式互斥
        if other != axis:
            assert cls not in out


def test_three_axes_use_three_distinct_styles_and_disjoint_texts():
    assert len(set(H.AXIS_CLASS.values())) == 3
    # 三張字樣表互斥（同一字樣不得出現在兩軸）
    tables = {"data": {p for v in T.ALLOWED_STATUS_PREFIXES.values() for p in v},
              "judgement": {p for v in T.JUDGEMENT_STATUS_PREFIXES.values() for p in v},
              "capability": {p for v in T.CAPABILITY_STATUS_PREFIXES.values() for p in v}}
    names = list(tables)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not (tables[a] & tables[b]), f"{a} 與 {b} 字樣重疊"
    # 樣式以 CSS 邊框形態區分（不只顏色）
    assert "ui2-chip--axis-judgement{border-style:double" in CSS
    assert "ui2-chip--axis-capability{border-style:dashed" in CSS
    assert "ui2-chip--axis-data{border-style:solid" in CSS


def _chips(html_: str) -> list[tuple[str, str]]:
    return re.findall(r'<span class="ui2-chip [^"]*" data-axis="(\w+)"[^>]*>([^<]*)</span>', html_)


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_rendered_chips_never_cross_axes_in_any_preview_page(page, scenario):
    """整頁渲染：每個帶軸別 chip 的文字，必須屬於它宣告的那一軸的允許字樣（三軸互不混用）。"""
    vm = get_preview_page_vm(page, scenario)
    from src.ui2.views._page import render_page  # noqa: F401  (確保 view 可匯入)
    htmls = [H.first_screen_html(vm.context.first_screen)]
    htmls += [H.metric_card_html(c) for c in vm.context.cards]
    htmls += [H.field_row_html(f) for s in vm.context.sections for f in s.fields]
    seen = 0
    for h in htmls:
        for axis, txt in _chips(h):
            seen += 1
            allowed = {"data": [p for v in T.ALLOWED_STATUS_PREFIXES.values() for p in v],
                       "judgement": [p for v in T.JUDGEMENT_STATUS_PREFIXES.values() for p in v],
                       "capability": [p for v in T.CAPABILITY_STATUS_PREFIXES.values() for p in v]}[axis]
            assert txt.startswith(tuple(allowed)), f"{page}/{scenario}: {axis} 軸 chip 文字 {txt!r} 不屬該軸"
    assert seen > 0


def test_capability_marker_and_judgement_are_not_rendered_as_data_axis():
    cap = H.status_chip_html(_field(None, T.TEXT_NOT_PROVIDED, cap=CapabilityState.NOT_PROVIDED))
    jud = H.status_chip_html(_field(JudgementState.UNDETERMINABLE, T.TEXT_RISK_CAP_UNDETERMINABLE))
    ne = H.status_chip_html(_field(FieldState.NOT_EVALUATED, T.TEXT_NOT_EVALUATED))
    assert 'data-axis="capability"' in cap and 'data-axis="judgement"' in jud and 'data-axis="data"' in ne
    assert 'data-state="not_provided"' in cap and 'data-state="undeterminable"' in jud \
        and 'data-state="not_evaluated"' in ne
    assert len({cap, jud, ne}) == 3


def test_chip_tone_families_and_symbols_are_text_carriers():
    from shared.ui2_contract.tones import TONE_SYMBOL, ChipTone
    assert set(TONE_SYMBOL) == set(ChipTone) and len(set(TONE_SYMBOL.values())) == 4   # 四族各有不同符號
    out = H.chip_html("可讀", ChipTone.POSITIVE, with_symbol=True)
    assert "✅ 可讀" in out and "ui2-chip--positive" in out


def test_guard_chip_style_is_never_the_neutral_style():
    """中性資訊（類型／產業／計數／口徑／來源）→ neutral class；guard 類（warning）不得承載。"""
    out = H.neutral_chip_html("半導體")
    assert "ui2-chip--neutral" in out and "warning" not in out


# ── source／as_of micro-tag：field-level，⛔ 全域假更新時間 ──────────────
@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_no_global_update_time_anywhere_on_a_page(page, scenario):
    vm = get_preview_page_vm(page, scenario)
    blob = H.first_screen_html(vm.context.first_screen) + "".join(
        H.metric_card_html(c) for c in vm.context.cards) + "".join(
        H.field_row_html(f) for s in vm.context.sections for f in s.fields)
    assert "更新時間" not in blob
    assert not re.search(r"\b\d{1,2}:\d{2}\b", blob), "出現時鐘時間字樣（可能是全域假更新時間）"
    assert not re.search(r"20\d\d-\d\d-\d\d", blob), "出現真實日期字樣（Preview 全部為 FAKE-ASOF）"


@pytest.mark.parametrize("scenario", ["cold", "loaded", "stale"])
def test_full_rendered_page_has_no_global_update_time(scenario):
    """整頁（含 view／殼）實際 markdown：⛔ 全域假更新時間（`按更新時間 HH:MM`、時鐘時間、真實日期）。"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60).run(timeout=60)
    at.selectbox(key="ui2_scenario").set_value(scenario).run(timeout=60)
    for page in PAGE_IDS:
        at.radio(key="ui2_page").set_value(page).run(timeout=60)
        assert not at.exception
        blob = "\n".join(m.value for m in at.markdown)
        assert "更新時間" not in blob, f"{page}/{scenario}"
        assert not re.search(r"\b\d{1,2}:\d{2}\b", blob), f"{page}/{scenario}: 時鐘時間"
        assert not re.search(r"20\d\d-\d\d-\d\d", blob), f"{page}/{scenario}: 真實日期"


def test_every_card_carries_its_own_freshness_tag():
    vm = get_preview_page_vm("p4_market", "loaded")
    for c in vm.context.cards:
        h = H.metric_card_html(c)
        assert "ui2-freshrow" in h
        assert ("資料日 FAKE-ASOF" in h) or (T.TEXT_ASOF_MISSING in h)


def test_missing_asof_is_marked_not_guessed():
    out = H.freshness_html(FreshnessInfo(None, None))
    assert T.TEXT_ASOF_MISSING in out and "資料日 " not in out


# ── CTA：Preview 期不可行動 ───────────────────────────────────────────
def test_disabled_cta_is_not_actionable_html():
    out = H.cta_html(CtaVM("🚀 更新", enabled=False, disabled_reason="Preview：不觸發任何動作"))
    assert 'aria-disabled="true"' in out and "ui2-cta--disabled" in out
    for token in ("<a ", "<button", "href=", "onclick", "<form", "<input"):
        assert token not in out, f"disabled CTA 不得含可互動標籤 {token!r}"
    assert "Preview：不觸發任何動作" in out


def test_all_preview_ctas_render_disabled():
    for p in PAGE_IDS:
        for s in SCENARIO_IDS:
            h = H.first_screen_html(get_preview_page_vm(p, s).context.first_screen)
            assert 'aria-disabled="true"' in h and "ui2-cta--disabled" in h


def test_action_row_renders_as_capability_never_as_an_action():
    """動作欄（② 是否需要行動）在 Preview 期＝capability `⬜ 尚未提供（待 System Action Aggregator）`。"""
    for p in ("p4_market", "p4_hold"):
        for s in SCENARIO_IDS:
            h = H.first_screen_html(get_preview_page_vm(p, s).context.first_screen)
            q2 = re.search(r'<div class="ui2-qrow" data-ui2-q="q2".*?</div>(?=<div class="ui2-qrow")', h, re.S)
            assert q2 and 'data-axis="capability"' in q2.group(0), f"{p}/{s}: 動作欄不是 capability 軸"
            assert T.TEXT_NOT_PROVIDED_AGGREGATOR in q2.group(0)
            for bad in ("今日無需調整", "加碼", "減碼", "換股", "ui2-cta ", "無需調整"):
                assert bad not in q2.group(0)


def test_empty_state_component_is_labelled_and_never_red_unless_unavailable():
    for axis, f in _axis_samples():
        h = H.empty_state_html(f)
        assert f.status_text in re.sub(r"<[^>]+>", "", h)
        assert f'data-axis="{axis}"' in h
        if f.state is not FieldState.UNAVAILABLE:
            assert "ui2-chip--danger" not in h


def test_risk_cap_row_is_judgement_axis_everywhere():
    for p in ("p4_market", "p4_target", "p4_hold"):
        for s in SCENARIO_IDS:
            h = H.first_screen_html(get_preview_page_vm(p, s).context.first_screen)
            m = re.search(r'Risk Cap</span> <span class="ui2-chip [^"]*" data-axis="(\w+)"[^>]*>([^<]*)<', h)
            assert m, f"{p}/{s}: 找不到 Risk Cap chip"
            assert m.group(1) == "judgement" and m.group(2) == T.TEXT_RISK_CAP_UNDETERMINABLE


# ════════════════════════════════════════════════════════════════════
# 3. 第一屏結構（錨點）＋ viewport 判定器
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("page", PAGE_IDS)
def test_first_screen_has_the_four_questions_in_order(page):
    h = H.first_screen_html(get_preview_page_vm(page, "loaded").context.first_screen)
    qs = re.findall(r'data-ui2-q="(q\d)"', h)
    assert qs == ["q1", "q2", "q3", "q4"]
    # DEC-128／129：舊版強制可見題號字樣「① 現在狀態…④ 主 CTA」（鷹架標籤，非產品文字）——改為只守錨點順序（資訊需求順序）
    assert h.index('data-ui2-q="q1"') < h.index('data-ui2-q="q2"') < h.index('data-ui2-q="q3"') < h.index('data-ui2-q="q4"')


def _good_mobile() -> dict:
    return {
        "viewport": {"w": 390, "h": 844},
        "nav": {"top": 791.0, "bottom": 844.0, "left": 0.0, "right": 390.0, "position": "fixed",
                "labels": list(MV.NAV_LABELS), "label_tops": [792.0] * 4, "label_lefts": [0, 97.5, 195, 292.5],
                "checked_count": 1, "checked_index": 0, "marker_contents": ['"● "', '""', '""', '""']},
        "elements": [{"q": q, "text": q, "top": 100.0 + i * 60, "bottom": 150.0 + i * 60, "left": 14.0, "right": 376.0,
                      "height": 50.0, "width": 362.0} for i, q in enumerate(MV.FIRST_SCREEN_QS)],
        "hscroll": {"doc": {"scrollWidth": 390, "clientWidth": 390}, "main": {"scrollWidth": 390, "clientWidth": 390},
                    "qa_clipped": False},
        "title": {"top": 60.0, "bottom": 90.0, "banner_bottom": 55.0, "qa_top": 95.0},
        "last_content": {"bottom": 740.0, "left": 14.0},
    }


def _good_desktop() -> dict:
    m = _good_mobile()
    m["viewport"] = {"w": 1440, "h": 900}
    m["nav"].update(top=0.0, bottom=900.0, left=0.0, right=176.0, label_tops=[64.0, 102.0, 141.0, 180.0],
                    label_lefts=[0.0] * 4)
    for e in m["elements"]:
        e["left"] = 200.0
    m["hscroll"] = {"doc": {"scrollWidth": 1440, "clientWidth": 1440}, "main": {"scrollWidth": 1440, "clientWidth": 1440},
                    "qa_clipped": False}
    m["last_content"] = {"bottom": 880.0, "left": 200.0}
    return m


def _failing(m: dict) -> set[str]:
    return {k for k, v in MV.evaluate(m).items() if v}


def test_evaluator_accepts_good_mobile_and_desktop():
    assert _failing(_good_mobile()) == set()
    assert _failing(_good_desktop()) == set()


def test_evaluator_thresholds_cite_existing_sources_only():
    ids = {t["id"] for t in MV.THRESHOLDS}
    assert ids == set(MV.evaluate(_good_mobile()))
    for t in MV.THRESHOLDS:
        assert t["source"] and re.search(r"Freeze|Gate|Wireframes|客戶|Checklist", t["source"])
    assert MV.NAV_MOBILE_H == 53 and 844 - MV.NAV_MOBILE_H == 791       # Freeze §16「可用高約 791px」


def _mut(base, fn):
    m = copy.deepcopy(base())
    fn(m)
    return _failing(m)


def test_evaluator_has_teeth_first_screen_too_low():
    assert "first_screen_within_usable_height" in _mut(_good_mobile, lambda m: m["elements"][3].update(bottom=792.0))
    assert "first_screen_above_nav" in _mut(_good_mobile, lambda m: m["elements"][3].update(bottom=800.0))
    assert "first_screen_within_usable_height" in _mut(_good_mobile, lambda m: m["elements"].pop())      # 缺 ④


def test_evaluator_has_teeth_horizontal_scroll():
    assert "no_horizontal_scroll" in _mut(_good_mobile, lambda m: m["hscroll"]["doc"].update(scrollWidth=420))
    assert "no_horizontal_scroll" in _mut(_good_mobile, lambda m: m["hscroll"].update(qa_clipped=True))


def test_evaluator_has_teeth_nav_not_bottom_fixed():
    assert "nav_fixed_four" in _mut(_good_mobile, lambda m: m["nav"].update(top=0.0, bottom=53.0))     # 頂部
    assert "nav_fixed_four" in _mut(_good_mobile, lambda m: m["nav"].update(position="static"))
    assert "nav_fixed_four" in _mut(_good_mobile, lambda m: m["nav"].update(label_tops=[792, 792, 840, 840]))
    assert "nav_fixed_four" in _mut(_good_desktop, lambda m: m["nav"].update(label_tops=[64.0] * 4))  # 桌機未垂直


def test_evaluator_has_teeth_fifth_page():
    assert "nav_fixed_four" in _mut(_good_mobile, lambda m: m["nav"]["labels"].append("⚙ 設定"))
    assert "nav_fixed_four" in _mut(_good_mobile, lambda m: m["nav"]["labels"].pop())


def test_evaluator_has_teeth_current_marked_by_color_only():
    assert "nav_current_marked_not_by_color_only" in _mut(
        _good_mobile, lambda m: m["nav"].update(marker_contents=['""'] * 4))
    assert "nav_fixed_four" in _mut(_good_mobile, lambda m: m["nav"].update(checked_count=2))


def test_evaluator_has_teeth_content_hidden_under_nav():
    assert "content_not_covered_by_nav" in _mut(_good_mobile, lambda m: m["last_content"].update(bottom=830.0))
    assert "content_not_covered_by_nav" in _mut(_good_desktop, lambda m: m["last_content"].update(left=100.0))


def test_evaluator_has_teeth_title_overlap():
    assert "no_title_overlap" in _mut(_good_mobile, lambda m: m["title"].update(top=40.0))
    assert "no_title_overlap" in _mut(_good_mobile, lambda m: m["title"].update(qa_top=80.0))


# ════════════════════════════════════════════════════════════════════
# 真瀏覽器量測（slow：需 Playwright＋Chromium；結果存證於 docs/vnext/newui2_batch2/）
# ════════════════════════════════════════════════════════════════════
@pytest.mark.slow
def test_real_browser_viewport_acceptance(tmp_path):
    pytest.importorskip("playwright.sync_api")
    proc, url = MV.start_server(ROOT)
    try:
        try:
            report = MV.run_measurements(url, tmp_path, "none")
        except Exception as exc:                       # 無瀏覽器可用 → 跳過（不是通過）
            if "Executable doesn't exist" in str(exc) or "BrowserType.launch" in str(exc):
                pytest.skip(f"無可用 Chromium：{str(exc)[:120]}")
            raise
    finally:
        proc.kill()
    # Batch 3：每 viewport＝四頁×六場景＋🎯 每場景另量『即時查一檔』＋👤 signed-out／unavailable
    # 2 viewport × (4 頁×6 場景 ＋ 6 查一檔 ＋ 2 帳戶態)；另加手機市場頁每場景一個長字串壓力態（DEC-127，只有手機）
    assert report["summary"]["states"] == 2 * (len(PAGE_IDS) * len(SCENARIO_IDS) + len(SCENARIO_IDS) + 2) + len(SCENARIO_IDS)
    assert report["summary"]["failed"] == [], report["summary"]["failed"]
