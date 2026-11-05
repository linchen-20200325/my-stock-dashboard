"""New UI2 手機抽屜：真瀏覽器行為測試（marker `ui2_browser`；DEC-137；測試規格 §3 T-01～T-20＋§4 突變 teeth）。

- 缺 playwright／Chromium：`UI2_BROWSER_LANE=required`（CI）→ fail；本機未設 → skip＋警示（`tests/ui2_browser.py`）。
- a11y／inert 一律以 CDP `Accessibility.getFullAXTree` 驗；⛔ Playwright `aria_snapshot()`（不反映 inert）。
- 背景可聚焦＝焦點落在 {`.st-key-ui2_nav`, `.ui2-dr-wrap`} 以外的任何元素（`BODY` 與 `section.stMain` 為已知允許停靠點，L-1，
  見 PR 描述／JS 設計 §8 限制；`stMain` 內部已無可操作內容）。
- 突變 teeth：另起一個 server，由 tmp wrapper 在載入前 patch `DRAWER_JS_HTML`（⛔ 動 production 檔），拔掉 inert／focus-return／去重旗標必紅。
"""
from __future__ import annotations

import os
import pathlib
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request

import pytest

from tests.ui2_browser import launch_or_fail, require_browser
from tests.ui2_viewport import measure_viewport as MV

pytestmark = pytest.mark.ui2_browser
ROOT = pathlib.Path(__file__).resolve().parents[1]
MOBILE = {"width": 390, "height": 844}
DESKTOP = {"width": 1440, "height": 900}
NAV_LABEL = ".st-key-ui2_nav [role='radiogroup'] > label"
PAGES = ["📊 市場", "🎯 標的", "💼 持股", "👤 我的"]
PAGE_IDS = ["p4_market", "p4_target", "p4_hold", "p4_me"]


# ── server fixtures ───────────────────────────────────────────────────
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(script: pathlib.Path, env_extra: dict | None = None):
    port = _free_port()
    env = dict(os.environ, PYTHONPATH=str(ROOT), **(env_extra or {}))
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(script), "--server.headless", "true",
                             "--server.port", str(port), "--browser.gatherUsageStats", "false"],
                            cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=1)
            return proc, url
        except Exception:
            time.sleep(0.5)
    proc.kill()
    pytest.fail("streamlit server 未在 40 秒內就緒")


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


def _wrapper(tmp: pathlib.Path, old: str | None, new: str) -> pathlib.Path:
    """tmp wrapper：載入 app_ui2 前 patch `DRAWER_JS_HTML`（old=None＝整段換成 new）。"""
    f = tmp / "wrap_app.py"
    f.write_text(textwrap.dedent(f"""
        import src.ui2.shell.drawer_js as d
        if not getattr(d, "_PATCHED", False):
            old, new = {old!r}, {new!r}
            if old is None:
                d.DRAWER_JS_HTML = new
            else:
                assert d.DRAWER_JS_HTML.count(old) == 1, old
                d.DRAWER_JS_HTML = d.DRAWER_JS_HTML.replace(old, new)
            d._PATCHED = True
        exec(compile(open("app_ui2.py", encoding="utf-8").read(), "app_ui2.py", "exec"))
    """), encoding="utf-8")
    return f


@pytest.fixture
def patched(tmp_path_factory):
    procs = []

    def make(old, new):
        d = tmp_path_factory.mktemp("wrap")
        proc, u = _start(_wrapper(d, old, new))
        procs.append(proc)
        return u
    yield make
    for p in procs:
        p.kill()


# ── page helpers ──────────────────────────────────────────────────────
class Ui:
    def __init__(self, browser, url, vp, query="", mobile=True):
        self.ctx = browser.new_context(viewport=vp, is_mobile=mobile and vp["width"] <= 768, has_touch=mobile and vp["width"] <= 768)
        self.pg = self.ctx.new_page()
        self.errs: list[str] = []
        self.pg.on("pageerror", lambda e: self.errs.append(str(e)))
        self.pg.add_init_script("""
          (() => { window.__lc = {kd: 0, ch: 0, mo: 0};
            const ae = EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener = function (t, ...r) {
              if (this === document && t === 'keydown') window.__lc.kd++;
              if (this === document && t === 'change') window.__lc.ch++;
              return ae.call(this, t, ...r); };
            const MO = window.MutationObserver;
            window.MutationObserver = class extends MO { observe(t, o) { if (t === document.body && o && o.subtree) window.__lc.mo++; return super.observe(t, o); } };
          })();""")
        self.pg.goto(url + ("?" + query if query else ""))
        self.pg.wait_for_selector(".ui2-qa", timeout=40000)
        self.pg.wait_for_function("() => window.__ui2drJS3 !== undefined || true")
        self.pg.wait_for_timeout(700)

    def close(self):
        self.ctx.close()

    # state
    def state(self):
        return self.pg.evaluate("""() => ({
          checked: !!document.querySelector('.ui2-dr-toggle').checked,
          active: (() => { const a = document.activeElement; return a.tagName + (a.classList.contains('ui2-dr-toggle') ? '#toggle' :
              a.closest('.st-key-ui2_nav') ? '#nav' : a.closest('.ui2-dr-wrap') ? '#wrap' : a.tagName === 'SECTION' ? '#stMain' : ''); })(),
          inert: [...document.querySelectorAll('[inert]')].filter(e => !e.matches('[data-testid=stExpanderDetails]')).length,
          page: document.querySelector('.ui2-pagetitle') ? document.querySelector('.ui2-pagetitle').dataset.ui2Page : null,
          vis: getComputedStyle(document.querySelector('.st-key-ui2_nav')).visibility})""")

    def is_open(self):
        return self.state()["checked"]

    def open_tap(self):
        self.pg.locator(".ui2-dr-toggle").tap() if self.pg.evaluate("() => 'ontouchstart' in window") else self.pg.locator(".ui2-dr-toggle").click()
        self.pg.wait_for_timeout(350)

    def wait_closed(self):
        self.pg.wait_for_function("() => !document.querySelector('.ui2-dr-toggle').checked", timeout=10000)
        self.pg.wait_for_timeout(350)

    def focus_toggle(self):
        self.pg.focus(".ui2-dr-toggle")

    def tab_trace(self, n, shift=False):
        out = []
        for _ in range(n):
            self.pg.keyboard.press("Shift+Tab" if shift else "Tab")
            out.append(self.state()["active"])
        return out

    def ax_names(self):
        cdp = self.ctx.new_cdp_session(self.pg)
        nodes = cdp.send("Accessibility.getFullAXTree")["nodes"]
        cdp.detach()
        return [(n.get("role", {}).get("value"), n.get("name", {}).get("value", "")) for n in nodes
                if not n.get("ignored") and n.get("name", {}).get("value")]

    def ax_has(self, text):
        return any(text in nm for _, nm in self.ax_names())


def with_ui(browser, url, vp=MOBILE, query="", mobile=True):
    return Ui(browser, url, vp, query, mobile)


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


BG_TEXT = "示意資料"          # 背景（頁首 banner）具名文字；開啟時必須自 a11y tree 消失


# ════════════════════════════════════════════════════════════════════
# T-17 版本／T-18 單一主導覽／T-14 桌機
# ════════════════════════════════════════════════════════════════════
def test_t17_streamlit_version_matches_matrix():
    import streamlit
    want = os.environ.get("UI2_EXPECT_STREAMLIT")
    from tests.ui2_browser import lane_required
    if lane_required():
        assert want, "browser lane required 時必須設定 UI2_EXPECT_STREAMLIT"
    if want:
        assert streamlit.__version__ == want


@pytest.mark.parametrize("which", ["mob", "desk"])
def test_t18_single_page_radiogroup_and_no_bottom_nav(request, which):
    ui = request.getfixturevalue(which)
    r = ui.pg.evaluate("""() => { const L = ['📊 市場','🎯 標的','💼 持股','👤 我的'];
      const gs = [...document.querySelectorAll('[role=radiogroup]')].filter(g => [...g.querySelectorAll('label')].some(l => L.includes(l.textContent.trim())));
      return {n: gs.length, labels: gs[0] ? [...gs[0].querySelectorAll('label')].map(l => l.textContent.trim()) : []}; }""")
    assert r["n"] == 1 and r["labels"] == PAGES
    m = MV.measure_state(ui.pg, ui.pg.viewport_size["width"], ui.pg.viewport_size["height"])
    assert m["drawer"]["bottom_fixed_navs"] == 0 and m["drawer"]["page_radiogroups"] == 1


def test_t14_desktop_has_no_toggle_and_rail_is_176(desk):
    r = desk.pg.evaluate("""() => ({tg: getComputedStyle(document.querySelector('.ui2-dr-toggle')).display,
      btn: getComputedStyle(document.querySelector('.ui2-dr-btn')).display,
      scrim: getComputedStyle(document.querySelector('.ui2-dr-scrim')).display,
      w: document.querySelector('.st-key-ui2_nav').getBoundingClientRect().width,
      vis: getComputedStyle(document.querySelector('.st-key-ui2_nav')).visibility,
      pad: getComputedStyle(document.querySelector('.block-container')).paddingLeft,
      hs: document.documentElement.scrollWidth <= document.documentElement.clientWidth})""")
    assert r["tg"] == r["btn"] == r["scrim"] == "none" and abs(r["w"] - 176) < 1 and r["vis"] == "visible"
    assert r["pad"] == "200px" and r["hs"]
    assert desk.state()["inert"] == 0
    assert not desk.pg.evaluate("() => !!document.querySelector('[inert]:not([data-testid=stExpanderDetails])')")
    desk.pg.keyboard.press("Tab")        # 桌機 Tab 可進內容（無 inert）
    assert desk.state()["inert"] == 0


# ════════════════════════════════════════════════════════════════════
# 開關／切頁／收合（T-04～T-07, T-10, T-11）
# ════════════════════════════════════════════════════════════════════
def test_open_by_tap_focus_enters_current_page_radio(mob):
    assert not mob.is_open() and mob.state()["vis"] == "hidden"
    mob.open_tap()
    s = mob.state()
    assert s["checked"] and s["vis"] == "visible" and s["active"] == "INPUT#nav" and s["inert"] > 0
    assert mob.pg.evaluate("() => document.activeElement.checked") is True      # 當前頁 radio


def test_t10_enter_on_toggle_opens(mob):
    """R-11 已改（JS_V4）：焦點在 ☰ 時 Enter 開啟（V3 不支援）；Space 同樣。"""
    mob.focus_toggle()
    mob.pg.keyboard.press("Enter")
    mob.pg.wait_for_timeout(300)
    s = mob.state()
    assert s["checked"] and s["active"] == "INPUT#nav"
    mob.pg.keyboard.press("Escape"); mob.wait_closed()
    mob.focus_toggle(); mob.pg.keyboard.press("Space"); mob.pg.wait_for_timeout(300)
    assert mob.state()["checked"]


def test_t10_enter_when_open_on_toggle_closes(mob):
    mob.focus_toggle(); mob.pg.keyboard.press("Enter"); mob.pg.wait_for_timeout(300)
    assert mob.state()["checked"]
    mob.focus_toggle(); mob.pg.keyboard.press("Enter"); mob.pg.wait_for_timeout(400)
    assert not mob.is_open() and mob.state()["inert"] == 0


def test_t04_click_current_page_closes_and_focus_to_toggle(mob):
    mob.open_tap()
    mob.pg.locator(NAV_LABEL, has_text="📊 市場").click()
    mob.wait_closed()
    s = mob.state()
    assert not s["checked"] and s["page"] == "p4_market" and s["active"] == "INPUT#toggle" and s["inert"] == 0


@pytest.mark.parametrize("label,pid", list(zip(PAGES, PAGE_IDS)))
def test_t05_click_page_closes_immediately_and_switches(mob, label, pid):
    mob.open_tap()
    mob.pg.locator(NAV_LABEL, has_text=label).click()
    mob.wait_closed()
    mob.pg.wait_for_selector(f'[data-ui2-page="{pid}"]', timeout=30000)
    s = mob.state()
    assert not s["checked"] and s["page"] == pid and s["inert"] == 0


def test_t05_closes_immediately_even_if_server_is_slow(mob):
    """server 人為延遲（攔截 websocket 以外不可行 → 以 CPU 節流 CDP 模擬慢）仍立即收合（不等 server 往返）。"""
    cdp = mob.ctx.new_cdp_session(mob.pg)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    mob.open_tap()
    t0 = time.time()
    mob.pg.locator(NAV_LABEL, has_text="🎯 標的").click()
    mob.pg.wait_for_function("() => !document.querySelector('.ui2-dr-toggle').checked", timeout=10000)
    assert time.time() - t0 < 3
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})


def test_t06_escape_closes_focus_to_toggle(mob):
    mob.open_tap()
    mob.pg.keyboard.press("Escape"); mob.wait_closed()
    s = mob.state()
    assert not s["checked"] and s["active"] == "INPUT#toggle" and s["inert"] == 0


def test_t11_scrim_click_closes(mob):
    mob.open_tap()
    mob.pg.mouse.click(375, 700)           # 抽屜寬 min(82vw,320)=320；x=375 在遮罩上
    mob.wait_closed()
    s = mob.state()
    assert not s["checked"] and s["active"] == "INPUT#toggle" and s["inert"] == 0


def test_t10_arrow_key_on_radio_selects_and_closes(mob):
    mob.open_tap()
    mob.pg.keyboard.press("ArrowDown")
    mob.wait_closed()
    mob.pg.wait_for_selector('[data-ui2-page="p4_target"]', timeout=30000)
    s = mob.state()
    assert s["page"] == "p4_target" and s["active"] == "INPUT#toggle" and s["inert"] == 0


@pytest.mark.parametrize("key", ["Enter", "Space"])
def test_t10_enter_space_on_radio_closes(mob, key):
    mob.open_tap()
    mob.pg.keyboard.press(key); mob.wait_closed()
    assert not mob.is_open() and mob.state()["inert"] == 0


@pytest.mark.parametrize("how", ["escape", "scrim", "page", "current", "arrow"])
def test_t07_focus_returns_to_toggle_for_every_close_path(mob, how):
    mob.open_tap()
    if how == "escape":
        mob.pg.keyboard.press("Escape")
    elif how == "scrim":
        mob.pg.mouse.click(375, 700)
    elif how == "page":
        mob.pg.locator(NAV_LABEL, has_text="💼 持股").click()
    elif how == "current":
        mob.pg.locator(NAV_LABEL, has_text="📊 市場").click()
    else:
        mob.pg.keyboard.press("ArrowDown")
    mob.wait_closed()
    mob.pg.wait_for_timeout(500)
    assert mob.state()["active"] == "INPUT#toggle"


# ════════════════════════════════════════════════════════════════════
# inert／Tab／a11y（T-01～T-03, T-13）
# ════════════════════════════════════════════════════════════════════
ALLOWED_FOCUS = {"BODY", "SECTION#stMain", "INPUT#toggle", "INPUT#nav", "LABEL#nav", "INPUT#wrap"}


def test_t01_tab_x20_never_reaches_background(mob):
    mob.open_tap()
    trace = mob.tab_trace(20)
    assert set(trace) <= ALLOWED_FOCUS, trace
    assert any(t == "INPUT#nav" for t in trace) and any(t == "INPUT#toggle" for t in trace)


def test_t02_shift_tab_x20_never_reaches_background(mob):
    mob.open_tap()
    trace = mob.tab_trace(20, shift=True)
    assert set(trace) <= ALLOWED_FOCUS, trace


def test_t01_control_tab_reaches_background_when_closed(mob):
    """對照：關閉態 Tab 會到背景（開發面 selectbox）——證明上面的測試不是因為頁面本來就沒有可聚焦背景。"""
    trace = mob.tab_trace(25)
    assert any(t not in ALLOWED_FOCUS for t in trace), trace


def test_t03_ax_tree_background_named_nodes_zero_when_open(mob):
    assert mob.ax_has(BG_TEXT) and mob.ax_has("開發")        # 關閉：背景在
    mob.open_tap()
    assert not mob.ax_has(BG_TEXT) and not mob.ax_has("開發／測試")
    assert mob.ax_has("主選單") or mob.ax_has("📊 市場")
    mob.pg.keyboard.press("Escape"); mob.wait_closed()
    assert mob.ax_has(BG_TEXT)                                 # 關閉後恢復


def test_inert_does_not_hit_drawer_or_toggle(mob):
    mob.open_tap()
    r = mob.pg.evaluate("""() => ({
      navInert: !!document.querySelector('.st-key-ui2_nav').closest('[inert]'),
      toggleInert: !!document.querySelector('.ui2-dr-toggle').closest('[inert]'),
      anyNavDesc: !!document.querySelector('.st-key-ui2_nav [inert]'),
      bgInert: !!document.querySelector('.ui2-qa').closest('[inert]')})""")
    assert r == {"navInert": False, "toggleInert": False, "anyNavDesc": False, "bgInert": True}


def test_t13_closed_drawer_is_clean_in_ax_tree(mob):
    assert not mob.ax_has("Google")
    assert not any(role == "radio" and nm in PAGES for role, nm in mob.ax_names())
    f = mob.pg.evaluate("() => [...document.querySelectorAll('.st-key-ui2_nav *')].filter(e => e.tabIndex >= 0 && getComputedStyle(e).visibility !== 'hidden').length")
    assert f == 0
    mob.open_tap()
    assert mob.ax_has("Google")                                # 開啟後在


# ════════════════════════════════════════════════════════════════════
# 殘留／重繪／去重（T-08, T-09）
# ════════════════════════════════════════════════════════════════════
def test_t09_rerun_with_open_drawer_keeps_inert(mob):
    mob.open_tap()
    n = mob.state()["inert"]
    mob.pg.keyboard.press("r")       # Streamlit rerun 快捷鍵
    mob.pg.wait_for_timeout(1500)
    s = mob.state()
    assert s["checked"] and s["inert"] == n and not mob.errs


def test_t09_thirty_page_switches_leave_no_inert(mob):
    for i in range(30):
        mob.open_tap()
        mob.pg.locator(NAV_LABEL, has_text=PAGES[(i + 1) % 4]).click()
        mob.wait_closed()
    mob.pg.wait_for_timeout(800)
    s = mob.state()
    assert s["inert"] == 0 and not s["checked"] and not mob.errs


def test_t09_rapid_toggle_9_and_escape_5(mob):
    for _ in range(9):
        mob.pg.locator(".ui2-dr-toggle").click(force=True)
    mob.pg.wait_for_timeout(400)
    assert mob.is_open() and mob.state()["inert"] > 0
    for _ in range(5):
        mob.pg.keyboard.press("Escape")
    mob.pg.wait_for_timeout(400)
    s = mob.state()
    assert not s["checked"] and s["inert"] == 0 and not mob.errs


def test_t09_reload_while_open_leaves_no_inert(mob):
    mob.open_tap()
    mob.pg.reload(); mob.pg.wait_for_selector(".ui2-qa", timeout=40000); mob.pg.wait_for_timeout(800)
    s = mob.state()
    assert not s["checked"] and s["inert"] == 0


def test_t09_resize_to_desktop_while_open_then_back(mob):
    mob.open_tap()
    mob.pg.set_viewport_size(DESKTOP); mob.pg.wait_for_timeout(600)
    s = mob.state()
    assert not s["checked"] and s["inert"] == 0
    mob.pg.keyboard.press("Tab")
    assert mob.state()["inert"] == 0
    mob.pg.set_viewport_size(MOBILE); mob.pg.wait_for_timeout(600)
    assert not mob.is_open() and mob.state()["inert"] == 0


def test_t08_listeners_do_not_accumulate_across_reruns(mob):
    base = mob.pg.evaluate("() => ({...window.__lc})")
    for i in range(10):
        mob.open_tap()
        mob.pg.locator(NAV_LABEL, has_text=PAGES[(i + 1) % 4]).click()
        mob.wait_closed()
    now = mob.pg.evaluate("() => ({...window.__lc})")
    assert now["kd"] == base["kd"] and now["ch"] == base["ch"] and now["mo"] == base["mo"], (base, now)
    # 行為：Esc 一次只關一次（不因重複監聽而多次 close）
    mob.open_tap(); mob.pg.keyboard.press("Escape"); mob.wait_closed()
    assert mob.state()["active"] == "INPUT#toggle"


# ════════════════════════════════════════════════════════════════════
# 版面：T-12 餘裕／T-15 水平捲動／T-16 reduced motion／T-19 帳戶占位
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("scenario,base", [("stale", 181.6), ("unavailable", 162.5)])
def test_t12_first_screen_margin_160_baseline_identical(mob, scenario, base):
    from src.ui2.shell.app import _SCENARIO_LABELS
    MV._select_box(mob.pg, "場景", _SCENARIO_LABELS[scenario], f'[data-ui2-scenario="{scenario}"]')
    mob.pg.evaluate("() => window.scrollTo(0, 0)")
    m = MV.measure_state(mob.pg, 390, 844)
    m["scenario"] = scenario
    margin = MV._nav_line(m) - m["first_block_after_l1_top"]
    assert round(margin, 1) == base, margin            # 逐位相同（客戶 (19)：未達停手，不放寬）
    assert margin >= 160
    assert MV.evaluate(m)["p2_nav_margin_160"] == []


@pytest.mark.parametrize("w,h", [(390, 844), (360, 640), (320, 568), (740, 360)])
def test_t15_no_horizontal_scroll_closed_and_open(browser, url, w, h):
    ui = Ui(browser, url, {"width": w, "height": h}, "")
    try:
        chk = "() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"
        assert ui.pg.evaluate(chk)
        ui.open_tap()
        assert ui.pg.evaluate(chk)
        assert ui.pg.evaluate("() => { const r = document.querySelector('.st-key-ui2_nav').getBoundingClientRect(); return r.width <= Math.min(0.82 * innerWidth, 320) + 1; }")
    finally:
        ui.close()


def test_t16_reduced_motion_disables_transition(browser, url):
    ctx = browser.new_context(viewport=MOBILE, reduced_motion="reduce")
    pg = ctx.new_page(); pg.goto(url); pg.wait_for_selector(".ui2-qa", timeout=40000)
    d = pg.evaluate("() => getComputedStyle(document.querySelector('.st-key-ui2_nav')).transitionDuration")
    ctx.close()
    assert set(d.replace(" ", "").split(",")) <= {"0s"}, d


def test_t19_account_block_fixed_placeholder_across_fake_account_states(mob):
    from src.ui2.shell.app import _ACCOUNT_LABELS
    def block():
        return mob.pg.evaluate("() => document.querySelector('[data-ui2-drawer-account]').textContent.replace(/\\s+/g,' ').trim()")
    first = block()
    assert "⬜ 尚未提供" in first and "Google 登入" in first and "登入與 Sheet 操作尚未開放" in first
    assert "已登入" not in first and "尚未登入" not in first
    # 開發面切 FAKE 帳戶情境（👤 頁才有 data-ui2-account 錨點）
    mob.open_tap(); mob.pg.locator(NAV_LABEL, has_text="👤 我的").click(); mob.wait_closed()
    for acct in ("signed_out", "unavailable", "signed_in"):
        MV._select_box(mob.pg, "帳戶狀態", _ACCOUNT_LABELS[acct], f'[data-ui2-account="{acct}"]')
        assert block() == first
    assert mob.pg.evaluate("() => document.querySelector('[data-ui2-drawer-account] .ui2-cta').getAttribute('aria-disabled')") == "true"


def test_real_feed_drawer_works_and_account_block_same(mob):
    from shared.ui2_contract.pages import FEED_REAL, SCENARIO_REAL
    from src.ui2.shell.app import _FEED_LABELS
    fake_block = mob.pg.evaluate("() => document.querySelector('[data-ui2-drawer-account]').innerHTML")
    MV._select_box(mob.pg, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
    assert mob.pg.evaluate("() => document.querySelector('[data-ui2-drawer-account]').innerHTML") == fake_block
    mob.open_tap()
    assert mob.state()["inert"] > 0 and mob.state()["active"] == "INPUT#nav"
    mob.pg.locator(NAV_LABEL, has_text="🎯 標的").click(); mob.wait_closed()
    mob.pg.wait_for_selector(f'[data-ui2-page="p4_target"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
    assert mob.state()["inert"] == 0


# ════════════════════════════════════════════════════════════════════
# T-20 JS 被擋降級＋§4 突變 teeth
# ════════════════════════════════════════════════════════════════════
def test_t20_js_blocked_degrades_to_page_switch_collapse_only(browser, patched):
    """JS 不執行（以空 script 取代）：切頁仍收合（標籤輪替 hack）；inert／Esc／焦點管理缺席——記錄為『降級』，不是完整行為。"""
    u = patched(None, "<script></script>")
    ui = Ui(browser, u, MOBILE, "")
    try:
        ui.open_tap()
        assert ui.is_open() and ui.state()["inert"] == 0           # 無 inert（降級）
        ui.pg.keyboard.press("Escape"); ui.pg.wait_for_timeout(300)
        assert ui.is_open()                                        # 無 Esc（降級）
        ui.pg.locator(NAV_LABEL, has_text="🎯 標的").click()
        ui.pg.wait_for_selector('[data-ui2-page="p4_target"]', timeout=30000)
        ui.wait_closed()
        assert not ui.is_open()                                    # 切頁後輪替 hack 收合
    finally:
        ui.close()


def _mut_ui(browser, patched, old, new):
    return Ui(browser, patched(old, new), MOBILE, "ui2_dev=1")


def test_teeth_without_inert_background_is_reachable(browser, patched):
    ui = _mut_ui(browser, patched, "c.inert = true;", "c.inert = false;")
    try:
        ui.open_tap()
        trace = ui.tab_trace(20)
        assert not set(trace) <= ALLOWED_FOCUS                       # 守衛必紅的條件：Tab 穿到背景
        assert ui.ax_has(BG_TEXT)                                    # 背景仍在 a11y tree
    finally:
        ui.close()


def test_teeth_without_focus_return_focus_is_lost(browser, patched):
    ui = _mut_ui(browser, patched, "t.checked = false; S.ret = Date.now(); t.focus(); sync();\n    setTimeout(() => { const u = T(); if (u) { u.focus(); } }, 0);",
                 "t.checked = false; sync();")
    try:
        ui.open_tap(); ui.pg.keyboard.press("Escape"); ui.wait_closed(); ui.pg.wait_for_timeout(500)
        assert ui.state()["active"] != "INPUT#toggle"
    finally:
        ui.close()


def test_teeth_without_dedupe_flag_listeners_accumulate(browser, patched):
    ui = _mut_ui(browser, patched, "  if (window.__ui2drJS3) { return; }", "")
    try:
        base = ui.pg.evaluate("() => ({...window.__lc})")
        for i in range(5):
            ui.open_tap(); ui.pg.locator(NAV_LABEL, has_text=PAGES[(i + 1) % 4]).click(); ui.wait_closed()
        now = ui.pg.evaluate("() => ({...window.__lc})")
        assert now["kd"] > base["kd"] or now["mo"] > base["mo"]
    finally:
        ui.close()


def test_teeth_without_click_delegation_current_page_does_not_close(browser, patched):
    """拿掉『點抽屜內 label → 收合』委派：點當前頁（radio 值不變、不 rerun）不收合。
    （capture→bubble 的變異在 1.56 無差異〔BaseWeb 不攔 click〕，故改用整段委派拿掉，兩版皆可驗。）"""
    ui = _mut_ui(browser, patched, "e.target.closest('.st-key-ui2_nav label')) { close(); }", "e.target.closest('.st-key-ui2_nav labelX')) { close(); }")
    try:
        ui.open_tap(); ui.pg.locator(NAV_LABEL, has_text="📊 市場").click(); ui.pg.wait_for_timeout(800)
        assert ui.is_open()
    finally:
        ui.close()


def test_teeth_without_enter_branch_enter_does_not_open(browser, patched):
    ui = _mut_ui(browser, patched, "    if (e.key === 'Enter' && t && e.target === t) { t.click(); return; }\n", "")
    try:
        ui.focus_toggle(); ui.pg.keyboard.press("Enter"); ui.pg.wait_for_timeout(500)
        assert not ui.is_open()
    finally:
        ui.close()


def test_teeth_without_release_inert_sticks_after_close(browser, patched):
    ui = _mut_ui(browser, patched, "function release() { S.held.forEach((e) => { e.inert = false; }); S.held = []; }",
                 "function release() { S.held = []; }")
    try:
        ui.open_tap(); ui.pg.keyboard.press("Escape"); ui.wait_closed()
        assert ui.state()["inert"] > 0
    finally:
        ui.close()
