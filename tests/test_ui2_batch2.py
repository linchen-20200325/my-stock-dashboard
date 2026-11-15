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
from shared.ui2_contract.pages import PAGE4_LABELS, PAGE_IDS, PAGE_LABELS, SCENARIO_IDS
from src.services.ui2.preview_feed import get_preview_page_vm
from src.ui2.components import html as H
from src.ui2.shell.css import CSS
from tests.ui2_viewport import measure_viewport as MV

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_SRC = (ROOT / "src" / "ui2" / "shell" / "app.py").read_text(encoding="utf-8")


# ════════════════════════════════════════════════════════════════════
# 1. W-1 導覽（靜態契約；真位置由瀏覽器量測證明）
# ════════════════════════════════════════════════════════════════════
def test_w1_nav_is_exactly_five_top_pages():
    """DEC-146（取代舊 `test_w1_nav_is_exactly_four_fixed_pages_no_fifth`；需求本來就由四頁改五頁）：UI2 導覽恰五頁、順序固定，
    第五頁 `🗂 資料` 為 **UI2 自有登錄**（`shared/ui2_contract/pages.py`），⛔ 擴充舊 UI 共用的 `shared/ia_nav4`（仍固定四頁）。"""
    from shared import ia_nav4
    assert len(PAGE_IDS) == 5
    assert [PAGE_LABELS[p] for p in PAGE_IDS] == list(MV.NAV_LABELS) == ["📊 市場", "🎯 標的", "💼 持股", "👤 我的", "🗂 資料"]
    assert tuple(PAGE4_LABELS) == PAGE_IDS[:4] and len(ia_nav4.PAGE4_LABELS) == 4      # 舊四頁 SSOT 未被擴充


def test_w1_nav_is_keyed_container_with_ui2_prefixed_radio():
    """導覽＝`st.container(key=ui2_nav)` 內的 `st.radio(key=ui2_page)`；session key 限 ui2_ 前綴。"""
    assert 'KEY_NAV = "ui2_nav"' in APP_SRC and "st.container(key=KEY_NAV)" in APP_SRC
    assert 'KEY_PAGE = "ui2_page"' in APP_SRC and "key=KEY_PAGE" in APP_SRC
    for forbidden in ("st.sidebar", "st.navigation", "st.tabs(", "st.page_link", "st.Page("):
        assert forbidden not in APP_SRC, f"導覽不得改用 {forbidden}（多頁路由風險）"


def _nav_css(css: str = CSS) -> str:
    return css[css.index("/* ── DEC-146"):css.index("/* ── Batch 3")]


def check_top_nav_css(css: str) -> list[str]:
    """DEC-146（取代舊 `check_mobile_drawer_css`／左 rail 守衛）：頂部兩列導覽的 CSS 契約。
    等價或更嚴：仍鎖 `position:fixed`、手機內容底部保留 5rem、safe-area `env()`、reduced-motion 無動畫依賴；
    新增鎖「頂端 top:0／左右貼齊」「第二列只在自身容器橫向捲動」「觸控目標 44px」「⛔ 左 rail／Drawer／☰／底部固定 53px 殘留」
    「讓位 padding-top 由 --ui2-nav-h 計算（⛔ 固定 2.75rem 舊保留帶）」。不再覆蓋的舊斷言（需求改變）：左側 rail／抽屜／☰ 的全部規則。"""
    bad = []
    nav = re.sub(r"/\*.*?\*/", "", _nav_css(css), flags=re.S) if "/* ── DEC-146" in css and "/* ── Batch 3" in css else ""
    if not nav:
        return ["缺 DEC-146 導覽區段"]
    if ".st-key-ui2_nav{position:fixed;top:0;left:0;right:0;" not in nav:
        bad.append("導覽不是 fixed 且貼齊視窗頂端左右")
    if "overflow-x:auto" not in nav or "flex-wrap:nowrap" not in nav:
        bad.append("第二列未設為自身容器內橫向捲動（overflow-x:auto＋nowrap）")
    if "height:44px" not in nav:
        bad.append("第二列觸控目標小於 44px")
    if 'p::before{content:"● "' not in nav or "label:has(input:checked){font-weight:700;border-bottom-color:currentColor}" not in nav:
        bad.append("選中態缺 ● 符號／粗體／底線（顏色不是唯一載體）")
    if "calc(var(--ui2-nav-h)" not in css or "padding-top:2.75rem" in css:
        bad.append("內容讓位不是由 --ui2-nav-h 計算（或殘留舊 2.75rem 保留帶）")
    if "padding-bottom:5rem" not in css:
        bad.append("手機內容底部保留量 5rem 消失")
    if "env(safe-area-inset-bottom" not in css or "env(safe-area-inset-left" not in nav:
        bad.append("safe-area 不再套用")
    if "min-width:769px" in nav and "flex:1 1 0" not in nav:
        bad.append("桌機五項未平分寬度")
    if "@media (prefers-reduced-motion:reduce){.st-key-ui2_nav,.st-key-ui2_nav *{transition:none !important;animation:none !important" not in nav:
        bad.append("缺 prefers-reduced-motion 規則（Streamlit 1.56 BaseWeb 內部元件有 transition）")
    if re.search(r"transition\s*:\s*(?!none)|animation\s*:\s*(?!none)", nav):
        bad.append("導覽出現動畫宣告（只准 reduced-motion 內的 none）")
    for dead in ("translateX", "ui2-dr", "padding-left:12.5rem", "width:11rem", "height:53px", "bottom:0;height"):
        if dead in css:
            bad.append(f"殘留舊 Drawer／rail／底部列規則：{dead}")
    return bad


def test_w1_top_nav_css_contract():
    assert check_top_nav_css(CSS) == []


@pytest.mark.parametrize("name,mut", [
    ("非 fixed", lambda c: c.replace(".st-key-ui2_nav{position:fixed;", ".st-key-ui2_nav{position:static;")),
    ("第二列不可橫向捲動", lambda c: c.replace("overflow-x:auto;overflow-y:hidden", "overflow-x:visible;overflow-y:hidden")),
    ("觸控目標縮小", lambda c: c.replace("height:44px", "height:30px")),
    ("選中態拔掉底線", lambda c: c.replace("font-weight:700;border-bottom-color:currentColor", "font-weight:700")),
    ("拔掉 ● 符號", lambda c: c.replace('p::before{content:"● "', 'p::before{content:""')),
    ("讓位改回固定保留帶", lambda c: c.replace("padding-top:calc(var(--ui2-nav-h)", "padding-top:2.75rem;x:calc(var(--ui2-nav-h)")),
    ("手機底部留白消失", lambda c: c.replace("@media (max-width:768px){.block-container{padding-bottom:5rem !important}}", "")),
    ("safe-area 拔掉", lambda c: c.replace("env(safe-area-inset-left", "xenv(safe-area-inset-lx")),
    ("殘留左 rail", lambda c: c.replace("/* ── Batch 3", ".block-container{padding-left:12.5rem}\n/* ── Batch 3", 1)),
    ("加回 Drawer 動畫", lambda c: c.replace(".st-key-ui2_nav{position:fixed;", ".st-key-ui2_nav{transition:transform .2s;position:fixed;")),
    ("拔掉 reduced-motion 規則", lambda c: c.replace("@media (prefers-reduced-motion:reduce){.st-key-ui2_nav,.st-key-ui2_nav *{transition:none", "@media (prefers-reduced-motion:no-preference){.st-key-ui2_nav,.st-key-ui2_nav *{transition:none")),
    ("桌機不平分", lambda c: c.replace("{flex:1 1 0;min-width:0}", "{flex:0 0 auto}")),
])
def test_w1_top_nav_css_guard_has_teeth(name, mut):
    m = mut(CSS)
    assert m != CSS, name
    assert check_top_nav_css(m), name


def test_w1_current_page_is_marked_beyond_color():
    """當前頁：粗體＋『● 』符號前綴＋底線（border-bottom，非僅文字色）；原生 radio `checked` 為語意狀態。"""
    nav = _nav_css()
    assert 'p::before{content:"● "' in nav
    assert "label:has(input:checked){font-weight:700;border-bottom-color:currentColor}" in nav


def test_w1_nav_css_does_not_depend_on_streamlit_internal_classes():
    nav_css = re.sub(r"/\*.*?\*/", "", _nav_css(), flags=re.S)     # 註解可提及，規則不可依賴
    assert "emotion" not in nav_css and "data-baseweb" not in nav_css and "stRadioOption" not in nav_css, \
        "導覽 CSS 依賴 Streamlit 內部 class 會在 1.56／1.59 間失效"
    for internal in ("stSidebar", "stToolbar", "stMain", "stElementContainer", "stVerticalBlock"):   # D-4 加嚴（DEC-137）
        assert internal not in nav_css, internal


def test_w1_top_row_is_fixed_placeholder_not_login():
    """第一列 Active Sheet／帳號＝固定占位（Capability `⬜ 尚未提供`）：⛔ 讀 session／query／帳戶、⛔ 輸入參數影響其內容、⛔ 互動元素。"""
    base = H.top_status_row_html()
    assert base.count(T.TEXT_NOT_PROVIDED) == 2 and 'data-axis="capability"' in base
    for bad in ("<button", "<input", "<a ", "href=", "onclick", "已登入", "signed"):
        assert bad not in base, bad
    # 模式標示併入第一列時，Sheet／帳號兩個占位不變
    withb = H.top_status_row_html(T.PREVIEW_BANNER_TEXT, T.PREVIEW_BANNER_NOTE)
    assert withb.count(T.TEXT_NOT_PROVIDED) == 2 and T.PREVIEW_BANNER_TEXT in withb and T.PREVIEW_BANNER_NOTE in withb
    import ast
    import inspect
    import textwrap
    fn = ast.parse(textwrap.dedent(inspect.getsource(H.top_status_row_html))).body[0]
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    assert not names & {"st", "session_state", "query_params", "ui2_account", "ui2_dev"}, names      # 只吃參數，⛔ 讀任何狀態


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
    assert not re.search(r"20\d\d-\d\d-\d\d", blob), "出現真實日期字樣（Preview 全部為「FAKE 示意」）"


@pytest.mark.parametrize("scenario", ["cold", "loaded", "stale"])
def test_full_rendered_page_has_no_global_update_time(scenario):
    """整頁（含 view／殼）實際 markdown：⛔ 全域假更新時間（`按更新時間 HH:MM`、時鐘時間、真實日期）。"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.query_params["ui2_dev"] = "1"          # P1：場景／帳戶切換控制只在開發面（?ui2_dev=1）
    at.run(timeout=60)
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
        assert ("資料日 FAKE 示意" in h) or (T.TEXT_ASOF_MISSING in h)


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
    """DEC-146 手機頂部兩列導覽（真實量測形狀：fixed 貼齊頂端左右、第一列兩行 40px＋第二列 44px＋邊線＝導覽底緣 85；底部保留線 791）。"""
    return {
        "viewport": {"w": 390, "h": 844},
        "nav": {"top": 0.0, "bottom": 85.0, "left": 0.0, "right": 390.0, "width": 390.0, "position": "fixed", "visibility": "visible",
                "labels": list(MV.NAV_LABELS), "label_tops": [40.0] * 5, "label_lefts": [0.0, 78.0, 156.0, 234.0, 312.0],
                "label_heights": [44.0] * 5,
                "checked_count": 1, "checked_index": 0, "marker_contents": ['"● "', '""', '""', '""', '""']},
        "top_nav": {"page_radiogroups": 1, "bottom_fixed_navs": 0, "drawer_dom": 0, "rail_padding": False,
                    "group": {"overflow_x": "auto", "scroll_w": 400.0, "client_w": 390.0, "last_right": 400.0,
                              "last_left_after_scroll": 322.0, "last_right_after_scroll": 390.0}},
        "elements": [{"q": q, "text": q, "top": 130.0 + i * 60, "bottom": 180.0 + i * 60, "left": 14.0, "right": 376.0,
                      "height": 50.0, "width": 362.0} for i, q in enumerate(MV.FIRST_SCREEN_QS)],
        "hscroll": {"doc": {"scrollWidth": 390, "clientWidth": 390}, "main": {"scrollWidth": 390, "clientWidth": 390},
                    "qa_clipped": False, "top1_clipped": False},
        "title": {"top": 90.0, "bottom": 120.0, "banner_bottom": 38.0, "qa_top": 125.0},
        "last_content": {"bottom": 740.0, "left": 14.0},
    }


def _good_desktop() -> dict:
    m = _good_mobile()
    m["viewport"] = {"w": 1440, "h": 900}
    m["nav"].update(top=0.0, bottom=73.0, left=0.0, right=1440.0, width=1440.0, label_tops=[29.0] * 5,
                    label_lefts=[0.0, 288.0, 576.0, 864.0, 1152.0])
    m["top_nav"]["group"] = {"overflow_x": "auto", "scroll_w": 1440.0, "client_w": 1440.0, "last_right": 1440.0,
                             "last_left_after_scroll": 1152.0, "last_right_after_scroll": 1440.0}
    m["title"] = {"top": 81.0, "bottom": 111.0, "banner_bottom": 22.0, "qa_top": 115.0}
    for i, e in enumerate(m["elements"]):
        e.update(top=120.0 + i * 60, bottom=170.0 + i * 60, left=200.0)
    m["hscroll"] = {"doc": {"scrollWidth": 1440, "clientWidth": 1440}, "main": {"scrollWidth": 1440, "clientWidth": 1440},
                    "qa_clipped": False, "top1_clipped": False}
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


def test_evaluator_has_teeth_top_five_nav():
    """DEC-146（取代 `test_evaluator_has_teeth_nav_not_bottom_fixed`／`..._fifth_page`；需求由左 Drawer／rail 四頁改頂部五頁）：
    等價或更嚴——仍鎖：導覽非 fixed、底部固定主導覽、雙主導覽、桌機未同列、缺量測鍵、checked≠1、項目數；
    新增鎖：未貼齊頂端左右、☰／Drawer／左 rail 殘留、觸控目標過小、手機第二列不可捲或第 5 項不可達、桌機五項未全可見。
    不再覆蓋的舊斷言（Drawer 不存在）：收合態在視窗外且 hidden、☰ (0,0) 44×44、四項垂直排列。"""
    K = "nav_fixed_five_top"
    assert K in _mut(_good_mobile, lambda m: m["nav"].update(position="static"))
    assert K in _mut(_good_mobile, lambda m: m["top_nav"].update(bottom_fixed_navs=1))               # 導覽放回底部
    assert K in _mut(_good_mobile, lambda m: m["top_nav"].update(page_radiogroups=2))                # 雙主導覽
    assert K in _mut(_good_mobile, lambda m: m["top_nav"].update(drawer_dom=1))                      # ☰／Drawer 殘留
    assert K in _mut(_good_mobile, lambda m: m["top_nav"].update(rail_padding=True))                 # 左 rail 讓位殘留
    assert K in _mut(_good_mobile, lambda m: m["nav"].update(top=12.0))                              # 未貼齊頂端
    assert K in _mut(_good_mobile, lambda m: m["nav"].update(width=300.0))                           # 未貼齊左右
    assert K in _mut(_good_mobile, lambda m: m["nav"].update(label_tops=[40.0, 40.0, 88.0, 88.0, 88.0]))   # 五項不同列
    assert K in _mut(_good_mobile, lambda m: m["nav"].update(label_heights=[44.0, 44.0, 30.0, 44.0, 44.0]))  # 觸控目標過小
    assert K in _mut(_good_mobile, lambda m: m["top_nav"]["group"].update(overflow_x="hidden"))      # 手機第二列不可捲
    assert K in _mut(_good_mobile, lambda m: m["top_nav"]["group"].update(last_right_after_scroll=470.0))  # 第 5 項捲到底仍不可達
    assert K in _mut(_good_mobile, lambda m: m["top_nav"]["group"].update(last_left_after_scroll=-20.0))
    assert K in _mut(_good_desktop, lambda m: m["top_nav"]["group"].update(scroll_w=1700.0))         # 桌機需捲動＝五項未全可見
    assert K in _mut(_good_desktop, lambda m: m["top_nav"]["group"].update(last_right=1500.0))
    assert K in _mut(_good_mobile, lambda m: m.pop("top_nav"))                                       # 缺量測鍵＝紅
    assert K in _mut(_good_mobile, lambda m: m["nav"]["labels"].append("⚙ 設定"))                    # 第六頁
    assert K in _mut(_good_mobile, lambda m: m["nav"]["labels"].pop())                               # 少一頁
    assert K in _mut(_good_mobile, lambda m: m["nav"].update(checked_count=2))
    # 頂部導覽遮住第一屏（含主 CTA）
    assert "first_screen_above_nav" in _mut(_good_mobile, lambda m: m["elements"][3].update(top=60.0))
    assert "first_screen_above_nav" in _mut(_good_desktop, lambda m: m["elements"][0].update(top=40.0))
    assert "first_screen_above_nav" in _mut(_good_mobile, lambda m: m["elements"][3].update(bottom=800.0))


def test_evaluator_has_teeth_top_row_clipped():
    assert "no_horizontal_scroll" in _mut(_good_mobile, lambda m: m["hscroll"].update(top1_clipped=True))


def _banner_box(**kw):
    b = {"height": 14.0, "lineHeight": 14.4, "fontSize": 12.0, "top": 6.0, "bottom": 20.0, "left": 12.0, "right": 300.0,
         "clipped": False, "row_top": 0.0, "row_bottom": 40.0}
    b.update(kw)
    return b


def _p1_banner_fails(**kw) -> list[str]:
    m = _good_mobile()
    m.update(page="p4_market", banner_text="示意資料（FAKE）", banner_box=_banner_box(**kw))
    out = {t["id"]: [] for t in MV.THRESHOLDS}
    MV._evaluate_p1(m, out)
    return out["p1_banner_single_line"]


def test_banner_in_first_row_equivalent_judgement_has_teeth():
    """DEC-146：標示併入第一列後，`p1_banner_single_line` 改為『位於第一列內、單行、未截斷、未超出視窗』的等價判定；
    把標示移走／截斷／折行／超出視窗必紅（不是放寬）。"""
    assert _p1_banner_fails() == []
    assert _p1_banner_fails(top=50.0, bottom=64.0)                    # 移到第一列之外（例如又變回獨立一行）
    assert _p1_banner_fails(top=-8.0, bottom=6.0)                     # 跑到第一列之上
    assert _p1_banner_fails(clipped=True)                             # 截斷
    assert _p1_banner_fails(height=30.0)                              # 折成兩行
    assert _p1_banner_fails(right=420.0)                              # 超出視窗右緣
    m = _good_mobile()
    m.update(page="p4_market", banner_text="示意資料（FAKE）")        # 有標示文字卻缺量測
    out = {t["id"]: [] for t in MV.THRESHOLDS}
    MV._evaluate_p1(m, out)
    assert out["p1_banner_single_line"]


def test_real_banner_in_first_row_judgement_has_teeth():
    from shared.ui2_contract.text import REAL_PREVIEW_BANNER_TEXT
    base = _good_mobile()
    base.update(feed="real", banner_text=REAL_PREVIEW_BANNER_TEXT, banner_box=_banner_box())
    assert "real_feed_banner_on_top" not in _failing(base)
    for kw in ({"top": 50.0, "bottom": 64.0}, {"clipped": True}):
        m = copy.deepcopy(base)
        m["banner_box"].update(kw)
        assert "real_feed_banner_on_top" in _failing(m), kw


def test_evaluator_has_teeth_title_overlap():
    assert "no_title_overlap" in _mut(_good_mobile, lambda m: m["title"].update(top=40.0))
    assert "no_title_overlap" in _mut(_good_mobile, lambda m: m["title"].update(qa_top=80.0))
    assert "no_title_overlap" in _mut(_good_mobile, lambda m: m["title"].update(top=60.0, banner_bottom=30.0))   # 標題被頂部導覽（底緣 85）遮住
    assert "no_title_overlap" in _mut(_good_desktop, lambda m: m["title"].update(top=50.0, banner_bottom=22.0))


# ════════════════════════════════════════════════════════════════════
# 真瀏覽器量測（slow：需 Playwright＋Chromium；結果存證於 docs/vnext/newui2_batch2/）
# ════════════════════════════════════════════════════════════════════
@pytest.mark.slow
@pytest.mark.ui2_browser
def test_real_browser_viewport_acceptance(tmp_path):
    # D-18（DEC-137）：skip 分支改走共用 require_browser()——`UI2_BROWSER_LANE=required`（CI ui2-browser lane）時缺 playwright／
    # Chromium 一律 fail（skip ≠ PASS）；本機未設才 skip 並印警示。等價或更嚴格：舊版在任何環境皆可靜默 skip。
    from tests.ui2_browser import launch_or_fail, require_browser
    with require_browser()() as p:                     # 先確認 Chromium 可啟動（不行 → required fail／本機 skip）
        launch_or_fail(p).close()
    proc, url = MV.start_server(ROOT)
    try:
        report = MV.run_measurements(url, tmp_path, "none")
    finally:
        proc.kill()
    # Batch 3：每 viewport＝四頁×六場景＋🎯 每場景另量『即時查一檔』＋👤 signed-out／unavailable
    # 2 viewport × (4 頁×6 場景 ＋ 6 查一檔 ＋ 2 帳戶態)；另加手機市場頁每場景一個長字串壓力態（DEC-127，只有手機）
    assert report["summary"]["states"] == 2 * (len(PAGE_IDS) * len(SCENARIO_IDS) + len(SCENARIO_IDS) + 2) + len(SCENARIO_IDS)
    assert report["summary"]["failed"] == [], report["summary"]["failed"]


@pytest.mark.slow
@pytest.mark.ui2_browser
def test_real_browser_real_feed_first_screen_and_daily_k(tmp_path):
    """Issue #1138 B 線（tests-only）：Real-data Preview（`feed="real"`）第一屏＋日 K 在 CI browser lane 實跑。

    上一支只量 FAKE 場景；real feed 的量測（`MV._run_real`）原本只有手動腳本＋存證 JSON（`docs/vnext/newui2_realfeed`），
    CI 從未在真瀏覽器跑過。本測試沿用同一量測與同一組既有門檻（`MV.THRESHOLDS`，⛔ 不新增門檻），只換 feed。
    """
    from shared.ui2_contract.pages import P4_MARKET, P4_TARGET
    from tests.ui2_browser import launch_or_fail, require_browser
    with require_browser()() as p:                     # 先確認 Chromium 可啟動（不行 → required fail／本機 skip）
        launch_or_fail(p).close()
    proc, url = MV.start_server(ROOT)
    try:
        report = MV.run_measurements(url, tmp_path, "none", feed="real")
    finally:
        proc.kill()
    # `_run_real` 的量測態數（由常數推導，不寫死）：每 viewport 量 PAGE_IDS 每頁一次＋🎯 頁再量『即時查一檔』一次；
    # 手機寬（≤ MOBILE_MAX_W）的 📊 市場頁另加一個長字串壓力態。
    expected = sum(len(PAGE_IDS) + (P4_TARGET in PAGE_IDS) + (P4_MARKET in PAGE_IDS and w <= MV.MOBILE_MAX_W)
                   for w, _h in MV.VIEWPORTS.values())
    assert report["meta"]["feed"] == "real"
    assert report["summary"]["states"] == expected == len(report["results"])
    assert report["summary"]["failed"] == [], report["summary"]["failed"]
    assert all(r["feed"] == "real" for r in report["results"])
    # 每個 viewport 的 📊 市場頁（非壓力態）都必須畫出日 K（真資料 ≥1 根；上限與圖高等由既有 `kbar_primary_chart` 門檻判）
    for vp_name in MV.VIEWPORTS:
        market = [r for r in report["results"]
                  if r["viewport_name"] == vp_name and r["page"] == P4_MARKET and r["mode"] != "stress"]
        assert len(market) == 1, (vp_name, len(market))
        p2 = market[0]["p2"]
        assert p2 is not None, vp_name
        assert int(p2.get("chart_bars") or 0) >= 1, (vp_name, p2.get("chart_state"), p2.get("chart_bars"))
