"""New UI2 頂部兩列五頁導覽：真瀏覽器行為測試（marker `ui2_browser`；DEC-146；沿用 DEC-137 的 browser lane）。

**檔名沿用 `test_ui2_drawer_browser.py`**（`.github/workflows/pr-check.yml` 的 ui2-browser 步驟以此檔名指定；不動 workflow，內容改寫）。

DEC-146 把「手機 ☰ Drawer＋桌機左 rail」換成「頂部兩列五頁導覽」，Drawer 的 T-01～T-20 測項依下表汰換／改寫（不是單純刪除）：

| 舊測項（Drawer） | 處置 |
|---|---|
| T-17 Streamlit 版本＝matrix | **保留** |
| T-18 單一頁面 radiogroup、無底部固定導覽 | **改寫**：恰 1 個 radiogroup、五項、無底部固定導覽、無 ☰／rail |
| T-14 桌機無 ☰、rail 176px | **改寫**：桌機五項全可見同一列、無左 rail（內容不讓出左欄）、無 ☰ |
| T-04～T-07／T-10／T-11 開關／收合／ESC／焦點回 ☰／遮罩 | **汰換**（沒有 Drawer）；等價保護改為：點擊切頁、方向鍵切頁、Tab 進出、焦點可見、無 inert／遮罩殘留 |
| T-01～T-03／T-13 背景 inert／AX tree 乾淨 | **改寫**：頁面任何時候都**不得**有 inert 殘留、AX tree 恰 1 radiogroup＋5 radio＋恰 1 checked |
| T-08 listener 不累積 | **保留（更嚴）**：30 次切頁 document keydown／change／click listener 與 MutationObserver 數不增加，且 0 個 UI2 script |
| T-09 rerun／reload／resize 後無殘留 inert | **改寫**：切頁 30 次、reload、resize 後 `[inert]`＝0 |
| T-12 首屏餘裕 ≥160 | **保留（更嚴）**：舊為與基準逐位相同；新為全部 FAKE 六場景＋Real 各 ≥160，且 CTA 在首屏 |
| T-15 無水平捲動（含開啟態） | **改寫**：頁面無水平捲動；第二列只在**自身容器**內橫向捲動 |
| T-16 reduced-motion 無 transition | **保留** |
| T-19 帳戶摘要固定占位 | **改寫**為頂部第一列 Active Sheet／帳號固定占位（FAKE 帳戶狀態／Real feed／query 不改變、不冒充登入） |
| T-20 JS 被擋仍降級收合、teeth（拔 inert／focus-return／去重旗標…） | **汰換**（無 JS）；teeth 改為對「每條判準」注入破壞 CSS，判準必紅（`test_teeth_*`） |

- 缺 playwright／Chromium：`UI2_BROWSER_LANE=required`（CI）→ fail；本機未設 → skip＋警示（`tests/ui2_browser.py`）。
- a11y 一律以 CDP `Accessibility.getFullAXTree` 驗；⛔ Playwright `aria_snapshot()`。
"""
from __future__ import annotations

import os
import pathlib

import pytest

from tests.ui2_browser import launch_or_fail, require_browser
from tests.ui2_viewport import measure_viewport as MV

pytestmark = pytest.mark.ui2_browser
ROOT = pathlib.Path(__file__).resolve().parents[1]
MOBILE = {"width": 390, "height": 844}
DESKTOP = {"width": 1440, "height": 900}
NAV_LABEL = ".st-key-ui2_nav [role='radiogroup'] > label"
PAGES = ["📊 市場", "🎯 標的", "💼 持股", "👤 我的", "🗂 資料"]
PAGE_IDS = ["p4_market", "p4_target", "p4_hold", "p4_me", "p4_data"]


@pytest.fixture(scope="module")
def pw():
    sp = require_browser()
    with sp() as p:
        yield p


@pytest.fixture(scope="module")
def browser(pw):
    b = launch_or_fail(pw)
    yield b
    b.close()


@pytest.fixture(scope="module")
def url():
    proc, u = MV.start_server(ROOT)
    yield u
    proc.kill()


class Ui:
    def __init__(self, browser, url, vp, query="", mobile=True, reduced=False):
        touch = mobile and vp["width"] <= 768
        self.ctx = browser.new_context(viewport=vp, is_mobile=touch, has_touch=touch,
                                       reduced_motion="reduce" if reduced else "no-preference")
        self.pg = self.ctx.new_page()
        self.errs: list[str] = []
        self.pg.on("pageerror", lambda e: self.errs.append(str(e)))
        self.pg.add_init_script("""
          (() => { window.__lc = {kd: 0, ch: 0, cl: 0, mo: 0, sc: 0};
            const ae = EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener = function (t, ...r) {
              if (this === document && t === 'keydown') window.__lc.kd++;
              if (this === document && t === 'change') window.__lc.ch++;
              if (this === document && t === 'click') window.__lc.cl++;
              return ae.call(this, t, ...r); };
            const MO = window.MutationObserver;
            window.MutationObserver = class extends MO { observe(t, o) { if (t === document.body && o && o.subtree) window.__lc.mo++; return super.observe(t, o); } };
          })();""")
        self.pg.goto(url + ("?" + query if query else ""))
        self.pg.wait_for_selector(".ui2-qa", timeout=40000)
        self.pg.wait_for_timeout(500)

    def close(self):
        self.ctx.close()

    @property
    def vp(self):
        return self.pg.viewport_size

    def page_id(self):
        return self.pg.evaluate("() => { const t = document.querySelector('.ui2-pagetitle'); return t ? t.dataset.ui2Page : null; }")

    def wait_page(self, pid):
        self.pg.wait_for_function("(p) => { const t = document.querySelector('.ui2-pagetitle'); return !!t && t.dataset.ui2Page === p; }",
                                  arg=pid, timeout=20000)
        self.pg.wait_for_timeout(250)

    def click_page(self, label, pid):
        self.pg.locator(NAV_LABEL, has_text=label).click()
        self.wait_page(pid)

    def ax_nodes(self):
        cdp = self.ctx.new_cdp_session(self.pg)
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
        cdp.detach()
        return nodes

    def listeners(self):
        return self.pg.evaluate("() => ({...window.__lc})")


@pytest.fixture
def mob(browser, url):
    u = Ui(browser, url, MOBILE, "ui2_dev=1")
    yield u
    u.close()


@pytest.fixture
def desk(browser, url):
    u = Ui(browser, url, DESKTOP, "ui2_dev=1", mobile=False)
    yield u
    u.close()


# ════════════════════════════════════════════════════════════════════
# 判準（回傳問題清單；空＝通過）——production 必須空，teeth 注入破壞 CSS 後必須非空
# ════════════════════════════════════════════════════════════════════
_GEOM_JS = """() => {
  const R = e => { const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height}; };
  const nav = document.querySelector('.st-key-ui2_nav'); const g = nav.querySelector('[role=radiogroup]');
  const ls = [...g.querySelectorAll('label')];
  const last = ls[ls.length - 1];
  return {nav: R(nav), navPos: getComputedStyle(nav).position, g: R(g), gScroll: {sw: g.scrollWidth, cw: g.clientWidth, ox: getComputedStyle(g).overflowX},
    docSW: document.documentElement.scrollWidth, docCW: document.documentElement.clientWidth,
    labels: ls.map(l => ({t: l.textContent.trim(), ...R(l)})), last: R(last),
    toggle: !!document.querySelector('.ui2-dr-toggle, .ui2-dr-btn, .ui2-dr-scrim'),
    inert: document.querySelectorAll('[inert]:not([data-testid=stExpanderDetails])').length,
    groups: [...document.querySelectorAll('[role=radiogroup]')].filter(x => [...x.querySelectorAll('label')].some(l => l.textContent.trim() === '📊 市場')).length,
    padL: getComputedStyle(document.querySelector('.block-container')).paddingLeft,
    checked: ls.map(l => { const p = l.querySelector('p'); const cs = getComputedStyle(l);
      return {on: l.querySelector('input').checked, mark: p ? getComputedStyle(p, '::before').content : '', fw: cs.fontWeight, bb: cs.borderBottomWidth, bc: cs.borderBottomColor}; })};
}"""


def check_layout(ui: Ui) -> list[str]:
    """頂部兩列導覽版面判準（手機／桌機通用）。"""
    g = ui.pg.evaluate(_GEOM_JS)
    vw = ui.vp["width"]
    bad = []
    if g["navPos"] != "fixed" or abs(g["nav"]["top"]) > 0.5 or abs(g["nav"]["left"]) > 0.5 or abs(g["nav"]["width"] - vw) > 1:
        bad.append(f"導覽不是貼齊視窗頂端左右的 fixed 列：{g['navPos']} {g['nav']}")
    if g["toggle"] or g["groups"] != 1:
        bad.append(f"殘留 ☰／遮罩，或頁面 radiogroup 數 {g['groups']} ≠ 1")
    if [x["t"] for x in g["labels"]] != PAGES:
        bad.append(f"導覽項 {[x['t'] for x in g['labels']]}")
    if len({round(x["top"]) for x in g["labels"]}) != 1:
        bad.append("五項不在同一列")
    if any(x["height"] < 43.5 for x in g["labels"]):
        bad.append("觸控目標高度 < 44px")
    if g["docSW"] > g["docCW"] + 0.5:
        bad.append(f"頁面水平溢出 {g['docSW']} > {g['docCW']}")
    if g["inert"]:
        bad.append(f"殘留 inert 元素 {g['inert']}")
    if g["padL"] not in ("0px", "14.4px", "14px") and vw > 768 and g["padL"] == "200px":
        bad.append("內容仍為左 rail 讓位")
    if vw > 768:     # 桌機：五項全可見，不需捲動
        if g["gScroll"]["sw"] > g["gScroll"]["cw"] + 0.5 or g["last"]["right"] > vw + 0.5:
            bad.append("桌機五項未全部可見")
    else:            # 手機：只在自身容器內橫向捲動
        if g["gScroll"]["ox"] not in ("auto", "scroll"):
            bad.append("手機第二列不是自身容器內橫向捲動")
    return bad


def check_selected_not_color_only(ui: Ui) -> list[str]:
    g = ui.pg.evaluate(_GEOM_JS)
    on = [c for c in g["checked"] if c["on"]]
    off = [c for c in g["checked"] if not c["on"]]
    bad = []
    if len(on) != 1:
        bad.append(f"checked 數 {len(on)} ≠ 1")
        return bad
    if "●" not in on[0]["mark"]:
        bad.append("選中項缺 ● 符號")
    if any("●" in c["mark"] for c in off):
        bad.append("未選項也有 ● 符號")
    if int(on[0]["fw"]) < 600 or int(on[0]["fw"]) <= max(int(c["fw"]) for c in off):
        bad.append("選中項非粗體")
    def underline(c):      # 底線可見＝寬度 ≥2px 且顏色不透明
        return float(c["bb"].replace("px", "")) >= 2 and not c["bc"].replace(" ", "").endswith(",0)")
    if not underline(on[0]) or any(underline(c) for c in off):
        bad.append("選中項缺底線（或未選項也有底線）")
    return bad


def touch_swipe_nav(ui: Ui, dx: int) -> None:
    """真實觸控拖曳（CDP `Input.dispatchTouchEvent`：touchStart→多次 touchMove→touchEnd）；遵守 overflow／touch-action，
    ⛔ 不用程式設 scrollLeft（overflow:hidden 時它仍可捲，會讓 teeth 失效）。dx<0＝向左滑（內容往左、露出右側）。"""
    box = ui.pg.evaluate("() => { const r = document.querySelector('.st-key-ui2_nav [role=radiogroup]').getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }")
    cdp = ui.ctx.new_cdp_session(ui.pg)
    try:
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": box["x"], "y": box["y"]}]})
        step = -12 if dx < 0 else 12
        for i in range(1, abs(dx) // 12 + 1):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": box["x"] + step * i, "y": box["y"]}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    finally:
        cdp.detach()
    ui.pg.wait_for_timeout(400)


def check_last_item_reachable_by_touch_and_keyboard(ui: Ui) -> list[str]:
    """手機：最後一項（🗂 資料）可由**真實觸控滑動**到達（完全進入視窗）。鍵盤到達另見
    `test_keyboard_arrow_keys_switch_pages_and_scroll_last_item_into_view`。"""
    vw = ui.vp["width"]
    ui.pg.evaluate("() => { document.querySelector('.st-key-ui2_nav [role=radiogroup]').scrollLeft = 0; }")
    touch_swipe_nav(ui, -240)
    r = ui.pg.evaluate("() => { const ls = document.querySelectorAll('.st-key-ui2_nav [role=radiogroup] > label'); const r = ls[ls.length - 1].getBoundingClientRect(); return {l: r.left, r: r.right}; }")
    bad = [] if (r["l"] >= -0.5 and r["r"] <= vw + 0.5) else [f"觸控滑動後第 5 項仍未完整進入視窗 {r}"]
    ui.pg.evaluate("() => { document.querySelector('.st-key-ui2_nav [role=radiogroup]').scrollLeft = 0; }")
    return bad


def _nav_focus(ui: Ui):
    ui.pg.focus(".st-key-ui2_nav input[type=radio]:checked")


# ════════════════════════════════════════════════════════════════════
# T-17 版本
# ════════════════════════════════════════════════════════════════════
def test_t17_streamlit_version_matches_matrix():
    import streamlit
    want = os.environ.get("UI2_EXPECT_STREAMLIT")
    from tests.ui2_browser import lane_required
    if lane_required():
        assert want, "browser lane required 時必須設定 UI2_EXPECT_STREAMLIT"
    if want:
        assert streamlit.__version__ == want


# ════════════════════════════════════════════════════════════════════
# 版面：兩個視窗 × 全部五頁
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("which", ["mob", "desk"])
def test_top_nav_layout_on_every_page(request, which):
    ui = request.getfixturevalue(which)
    for label, pid in zip(PAGES, PAGE_IDS):
        ui.click_page(label, pid)
        assert check_layout(ui) == [], (which, pid)
        assert check_selected_not_color_only(ui) == [], (which, pid)
    assert ui.errs == []


@pytest.fixture
def narrow(browser, url):
    u = Ui(browser, url, {"width": 320, "height": 568}, "ui2_dev=1")
    yield u
    u.close()


def test_mobile_last_item_reachable_by_touch_scroll(narrow):
    """320px 寬（390 時五項剛好放得下，不需捲動；更窄才需要）：第二列在**自身容器**內橫向捲動，觸控滑動後第 5 項完整進入視窗、可點。"""
    g = narrow.pg.evaluate(_GEOM_JS)
    assert g["gScroll"]["sw"] > g["gScroll"]["cw"] + 1, "320px 寬度下第二列應需橫向捲動（否則此測無意義）"
    assert g["docSW"] <= g["docCW"], "頁面本身不得水平捲動（只有第二列容器可捲）"
    assert check_last_item_reachable_by_touch_and_keyboard(narrow) == []
    touch_swipe_nav(narrow, -240)
    narrow.pg.locator(NAV_LABEL, has_text="🗂 資料").tap()
    narrow.wait_page("p4_data")


def test_keyboard_arrow_keys_switch_pages_and_scroll_last_item_into_view(narrow):
    mob = narrow
    _nav_focus(mob)
    for pid in PAGE_IDS[1:]:
        mob.pg.keyboard.press("ArrowRight")
        mob.wait_page(pid)
        _nav_focus(mob)       # rerun 後焦點可能回 body；重新聚焦到目前頁 radio 再按（鍵盤使用者 Tab 回導覽）
    r = mob.pg.evaluate("() => { const ls = document.querySelectorAll('.st-key-ui2_nav [role=radiogroup] > label'); const r = ls[ls.length - 1].getBoundingClientRect(); return {l: r.left, r: r.right, w: innerWidth}; }")
    assert r["l"] >= -0.5 and r["r"] <= r["w"] + 0.5, r
    for pid in reversed(PAGE_IDS[:-1]):
        mob.pg.keyboard.press("ArrowLeft")
        mob.wait_page(pid)
        _nav_focus(mob)
    assert mob.page_id() == "p4_market"


def test_tab_enters_nav_first_and_leaves_it(mob):
    """導覽在 DOM 最前：Tab 序列裡導覽 radio 在任何內容控制項之前（Streamlit 自己的 `section.stMain` 捲動容器是已知的第一個停點，
    不是 UI2 內容）；再 Tab 可離開導覽（⛔ 鍵盤陷阱）。"""
    mob.pg.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
    probe = """() => { const a = document.activeElement; return {nav: !!(a && a.closest('.st-key-ui2_nav')), main: !!(a && a.matches('section.stMain, body'))}; }"""
    seq = []
    for _ in range(6):
        mob.pg.keyboard.press("Tab")
        seq.append(mob.pg.evaluate(probe))
    first_nav = next(i for i, x in enumerate(seq) if x["nav"])
    assert all(x["main"] for x in seq[:first_nav]), f"導覽之前出現內容控制項：{seq}"
    assert any(not x["nav"] for x in seq[first_nav + 1:]), f"Tab 被困在導覽內（鍵盤陷阱）：{seq}"


def test_focus_indicator_is_visible_on_nav_radio(mob):
    _nav_focus(mob)
    mob.pg.keyboard.press("Shift+Tab")
    mob.pg.keyboard.press("Tab")
    r = mob.pg.evaluate("""() => { const l = document.activeElement.closest('label'); if (!l) return null;
      const cs = getComputedStyle(l); return {w: cs.outlineWidth, st: cs.outlineStyle}; }""")
    assert r and r["st"] != "none" and float(r["w"].replace("px", "")) >= 1.5, r


def test_every_page_reachable_by_click_on_both_viewports(mob, desk):
    for ui in (mob, desk):
        for label, pid in zip(PAGES, PAGE_IDS):
            ui.click_page(label, pid)
            assert ui.page_id() == pid


# ════════════════════════════════════════════════════════════════════
# a11y：AX tree（role／checked）
# ════════════════════════════════════════════════════════════════════
def test_ax_tree_has_one_radiogroup_five_radios_one_checked(mob):
    nodes = [n for n in mob.ax_nodes() if not n.get("ignored")]
    role = lambda n: n.get("role", {}).get("value")
    name = lambda n: n.get("name", {}).get("value", "")
    groups = [n for n in nodes if role(n) == "radiogroup" and any("市場" in name(k) for k in nodes if role(k) == "radio")]
    radios = [n for n in nodes if role(n) == "radio" and any(lb.split(" ", 1)[1] in name(n) for lb in PAGES)]
    assert len(groups) >= 1 and len(radios) == 5, ([name(g) for g in groups], [name(r) for r in radios])
    checked = [r for r in radios if any(p["name"] == "checked" and p["value"]["value"] in (True, "true") for p in r.get("properties", []))]
    assert len(checked) == 1 and "市場" in name(checked[0])


def test_no_inert_residue_no_drawer_dom_no_ui2_script(mob):
    for _ in range(3):
        for label, pid in zip(PAGES, PAGE_IDS):
            mob.click_page(label, pid)
    s = mob.pg.evaluate("""() => ({inert: document.querySelectorAll('[inert]:not([data-testid=stExpanderDetails])').length,
      dr: document.querySelectorAll('.ui2-dr-toggle, .ui2-dr-btn, .ui2-dr-scrim, .ui2-dr-wrap').length,
      flag: window.__ui2drJS3 !== undefined,
      scripts: [...document.querySelectorAll('script')].filter(s => /ui2dr|st-key-ui2_nav|ui2-dr/.test(s.textContent)).length})""")
    assert s == {"inert": 0, "dr": 0, "flag": False, "scripts": 0}, s


def test_listeners_do_not_accumulate_across_reruns(mob):
    for label, pid in zip(PAGES, PAGE_IDS):        # 先暖機一輪（Streamlit 自身的 lazy 註冊）
        mob.click_page(label, pid)
    before = mob.listeners()
    for _ in range(6):
        for label, pid in zip(PAGES, PAGE_IDS):
            mob.click_page(label, pid)
    after = mob.listeners()
    # kd／ch／mo：UI2 不註冊任何一個（src/ui2 零 JS，見 test_ui2_drawer_js_guard），故任何增加都是回歸；
    # cl（document click）：Streamlit／BaseWeb 本身每次 radio 互動會多註冊 1 個（與 UI2 無關），故只要求「每次點擊 ≤ 1」不超線性。
    for k in ("kd", "ch", "mo", "sc"):
        assert after[k] == before[k], (k, before, after)
    clicks = 6 * len(PAGES)
    assert after["cl"] - before["cl"] <= clicks, (before, after)


def test_reload_and_resize_leave_no_residue(browser, url):
    ui = Ui(browser, url, MOBILE, "")
    try:
        ui.pg.reload()
        ui.pg.wait_for_selector(".ui2-qa", timeout=40000)
        ui.pg.set_viewport_size(DESKTOP)
        ui.pg.wait_for_timeout(300)
        assert check_layout(ui) == []
        ui.pg.set_viewport_size(MOBILE)
        ui.pg.wait_for_timeout(300)
        assert check_layout(ui) == []
    finally:
        ui.close()


def test_nav_stays_fixed_when_page_scrolls(mob):
    mob.pg.evaluate("() => { const m = document.querySelector('[data-testid=stMain]'); m.scrollTo({top: m.scrollHeight, behavior: 'instant'}); }")
    mob.pg.wait_for_timeout(200)
    assert mob.pg.evaluate("() => document.querySelector('.st-key-ui2_nav').getBoundingClientRect().top") == 0


# ════════════════════════════════════════════════════════════════════
# 首屏：餘裕 ≥160、CTA 可操作、無水平溢出
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("scenario", ["cold", "loaded", "missing", "stale", "unavailable", "not_evaluated"])
def test_first_screen_margin_160_every_fake_scenario(mob, scenario):
    from src.ui2.shell.app import _SCENARIO_LABELS
    MV._select_box(mob.pg, "場景", _SCENARIO_LABELS[scenario], f'[data-ui2-scenario="{scenario}"]')
    mob.pg.evaluate("() => window.scrollTo(0, 0)")
    m = MV.measure_state(mob.pg, 390, 844)
    m["scenario"] = scenario
    margin = MV._nav_line(m) - m["first_block_after_l1_top"]
    assert margin >= 160, (scenario, margin)
    assert MV.evaluate(m)["p2_nav_margin_160"] == []
    q4 = [e for e in m["elements"] if e["q"] == "q4"]
    assert q4 and q4[0]["bottom"] <= 791 and q4[0]["top"] >= m["nav"]["bottom"] - 0.5, q4      # 主 CTA 在導覽之下、首屏內


@pytest.mark.parametrize("w,h", [(390, 844), (360, 640), (320, 568), (740, 360), (1440, 900)])
def test_no_page_horizontal_scroll_and_row1_not_clipped(browser, url, w, h):
    ui = Ui(browser, url, {"width": w, "height": h}, "", mobile=w <= 768)
    try:
        for label, pid in zip(PAGES, PAGE_IDS):
            ui.click_page(label, pid)
            assert ui.pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"), (w, pid)
            r = ui.pg.evaluate("""() => { const row = document.querySelector('.ui2-top1'); const b = document.querySelector('.ui2-top1 .ui2-banner');
              const items = [...row.querySelectorAll('[data-ui2-top-item]')];
              const rr = row.getBoundingClientRect(); const nav = document.querySelector('.st-key-ui2_nav').getBoundingClientRect();
              const t = document.querySelector('.ui2-pagetitle').getBoundingClientRect();
              return {rowClip: row.scrollWidth > row.clientWidth + 1 || row.scrollHeight > row.clientHeight + 1,
                      itemClip: items.some(i => i.scrollWidth > i.clientWidth + 1), bClip: b ? b.scrollWidth > b.clientWidth + 1 : null,
                      inRow: items.every(i => { const r = i.getBoundingClientRect(); return r.top >= rr.top - 1 && r.bottom <= rr.bottom + 1 && r.left >= -0.5 && r.right <= innerWidth + 0.5; }),
                      titleBelowNav: t.top >= nav.bottom - 0.5}; }""")
            assert r == {"rowClip": False, "itemClip": False, "bClip": False, "inRow": True, "titleBelowNav": True}, (w, h, pid, r)
    finally:
        ui.close()


# ════════════════════════════════════════════════════════════════════
# 第一列：Active Sheet／模式標示／帳號（固定占位、不冒充登入）
# ════════════════════════════════════════════════════════════════════
def _row1(ui: Ui) -> dict:
    return ui.pg.evaluate("""() => { const row = document.querySelector('.ui2-top1');
      const t = s => { const e = row.querySelector(s); return e ? e.innerText.replace(/\\s+/g, ' ').trim() : null; };
      return {sheet: t('[data-ui2-top-item=sheet]'), account: t('[data-ui2-top-item=account]'), mode: t('[data-ui2-top-item=mode]'),
              role: (row.querySelector('.ui2-banner') || {}).getAttribute ? row.querySelector('.ui2-banner').getAttribute('role') : null,
              interactive: row.querySelectorAll('button, a, input, [tabindex], [role=button]').length}; }""")


def test_row1_sheet_and_account_are_fixed_placeholders_not_login(mob):
    from shared.ui2_contract import text as T
    from src.ui2.shell.app import _ACCOUNT_LABELS
    base = _row1(mob)
    assert base["sheet"] == f"Active Sheet {T.TEXT_NOT_PROVIDED}" and base["account"] == f"帳號 {T.TEXT_NOT_PROVIDED}"
    assert base["interactive"] == 0
    # FAKE 帳戶狀態切換（開發面）不得改變第一列
    mob.click_page("👤 我的", "p4_me")
    for acct in ("signed_out", "unavailable", "signed_in"):
        MV._select_box(mob.pg, "帳戶狀態", _ACCOUNT_LABELS[acct], f'[data-ui2-account="{acct}"]')
        row = _row1(mob)
        assert row["sheet"] == base["sheet"] and row["account"] == base["account"], (acct, row)
        assert "已登入" not in (row["sheet"] + row["account"])


def test_row1_fake_mode_label_is_complete_single_line(mob):
    from shared.ui2_contract import text as T
    row = _row1(mob)
    assert row["role"] == "note"
    assert T.PREVIEW_BANNER_TEXT in row["mode"] and T.PREVIEW_BANNER_NOTE in row["mode"], row     # FAKE：手機也顯示完整 note（必要揭露）
    h = mob.pg.evaluate("() => { const b = document.querySelector('.ui2-top1 .ui2-banner'); return b.getBoundingClientRect().height <= parseFloat(getComputedStyle(b).lineHeight) + 1; }")
    assert h, "FAKE 標示在手機折成多行"


def test_row1_real_mode_label_is_complete_and_not_production(mob):
    from shared.ui2_contract import text as T
    MV._select_box(mob.pg, "資料來源（feed）", "Real-data Preview（唯讀；只接 2 項真資料）", '[data-ui2-scenario="real"]')
    mob.pg.wait_for_timeout(400)
    row = _row1(mob)
    assert T.REAL_PREVIEW_BANNER_TEXT in row["mode"] and "FAKE" not in row["mode"], row
    assert "非正式 production default" in row["mode"]
    for label, pid in zip(PAGES, PAGE_IDS):        # Real 各頁（含 🗂 資料）第一列一致、標示完整
        mob.click_page(label, pid)
        r = _row1(mob)
        assert T.REAL_PREVIEW_BANNER_TEXT in r["mode"] and r["sheet"] == row["sheet"] and r["account"] == row["account"], (pid, r)
        assert check_layout(mob) == [], pid


def test_data_page_is_honest_not_wired_shell(mob):
    mob.click_page("🗂 資料", "p4_data")
    txt = mob.pg.evaluate("() => document.querySelector('.block-container').innerText.replace(/\\s+/g, ' ')")
    assert "⬜ 尚未提供" in txt and "尚未開放" in txt
    for forbidden in ("retrieved_at", "proxy", "更新時間", "刷新", "OneBrain runtime", "Risk Cap 0", "0%"):
        assert forbidden not in txt, forbidden


# ════════════════════════════════════════════════════════════════════
# reduced-motion／safe-area
# ════════════════════════════════════════════════════════════════════
def test_reduced_motion_nav_has_no_transition_or_animation(browser, url):
    ui = Ui(browser, url, MOBILE, "", reduced=True)
    try:
        d = ui.pg.evaluate("""() => { const out = new Set(); for (const e of document.querySelectorAll('.st-key-ui2_nav, .st-key-ui2_nav *')) {
          const cs = getComputedStyle(e); out.add(cs.transitionDuration + '|' + cs.animationName); } return [...out]; }""")
        assert all(x.split("|")[0].replace(" ", "").split(",")[0] == "0s" and x.split("|")[1] in ("none", "") for x in d), d
        assert ui.pg.evaluate("() => matchMedia('(prefers-reduced-motion: reduce)').matches")
    finally:
        ui.close()


def test_safe_area_rules_present_and_inactive_in_chromium(mob):
    """Chromium 的 safe-area inset＝0：padding 不變（不退化）；規則存在（iOS 真機 NOT VERIFIED）。"""
    from src.ui2.shell.css import CSS
    assert "env(safe-area-inset-left" in CSS and "env(safe-area-inset-bottom" in CSS
    r = mob.pg.evaluate("""() => { const n = getComputedStyle(document.querySelector('.st-key-ui2_nav')); const b = getComputedStyle(document.querySelector('.block-container'));
      return {l: n.paddingLeft, r: n.paddingRight, pb: b.paddingBottom}; }""")
    assert r["l"] == "0px" and r["r"] == "0px" and r["pb"] == "80px", r


# ════════════════════════════════════════════════════════════════════
# 突變 teeth：對每條判準注入破壞 CSS，判準必紅（production 版本為綠）
# ════════════════════════════════════════════════════════════════════
def _mutate(ui: Ui, css: str):
    ui.pg.add_style_tag(content=css)
    ui.pg.wait_for_timeout(200)


@pytest.mark.parametrize("name,css,checker", [
    ("導覽改成非 fixed", ".st-key-ui2_nav{position:static !important}", check_layout),
    ("第二列不可橫向捲動（overflow hidden）", ".st-key-ui2_nav [role=radiogroup]{overflow-x:hidden !important}", check_layout),
    ("觸控目標縮小", ".st-key-ui2_nav [role=radiogroup]>label{height:30px !important}", check_layout),
    ("拔掉選中底線", ".st-key-ui2_nav [role=radiogroup]>label{border-bottom-width:0 !important}", check_selected_not_color_only),
    ("拔掉選中粗體", ".st-key-ui2_nav [role=radiogroup]>label{font-weight:400 !important}", check_selected_not_color_only),
    ("拔掉 ● 符號", '.st-key-ui2_nav [role=radiogroup]>label p::before{content:"" !important}', check_selected_not_color_only),
])
def test_teeth_layout_and_selected_state(mob, name, css, checker):
    assert checker(mob) == [], "production 應為綠"
    _mutate(mob, css)
    assert checker(mob), f"沒抓到：{name}"


def test_teeth_last_item_unreachable_when_container_cannot_scroll(narrow):
    assert check_last_item_reachable_by_touch_and_keyboard(narrow) == []
    _mutate(narrow, ".st-key-ui2_nav [role=radiogroup]{overflow-x:hidden !important}")
    assert check_last_item_reachable_by_touch_and_keyboard(narrow), "容器不可捲動時第 5 項應判為不可達"


def test_teeth_inert_residue_is_detected(mob):
    assert check_layout(mob) == []
    mob.pg.evaluate("() => { document.querySelector('.block-container').setAttribute('inert', ''); }")
    assert any("inert" in b for b in check_layout(mob))


def test_teeth_drawer_dom_residue_is_detected(mob):
    assert check_layout(mob) == []
    mob.pg.evaluate("() => { const b = document.createElement('label'); b.className = 'ui2-dr-btn'; document.body.appendChild(b); }")
    assert any("☰" in b for b in check_layout(mob))


def test_teeth_row1_clipping_is_detected(browser, url):
    ui = Ui(browser, url, MOBILE, "")
    try:
        r0 = ui.pg.evaluate("() => { const row = document.querySelector('.ui2-top1'); return row.scrollWidth > row.clientWidth + 1; }")
        assert r0 is False
        _mutate(ui, ".ui2-top1 .ui2-banner{white-space:nowrap !important;font-size:2rem !important}")
        assert ui.pg.evaluate("() => { const row = document.querySelector('.ui2-top1'); return row.scrollWidth > row.clientWidth + 1 || row.scrollHeight > row.clientHeight + 1; }")
    finally:
        ui.close()
