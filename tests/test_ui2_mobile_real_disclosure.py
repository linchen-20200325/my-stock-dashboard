"""New UI2：手機 Real-data Preview 揭露小字（`ui2-real-mobile-note`）。

背景：Real 橫幅旁註（`.ui2-banner__note--wide`）在 ≤640px 被隱藏以維持單行（P1），手機因此看不到
「目前僅部分台股資料已接入…」這句必要揭露。本批在導覽之後、第一屏之前（與降級警示同位置區）補一個**只在
Real 輸出、只在手機（≤640px）顯示**的小字；文字**逐字沿用** `shared.ui2_contract.text.REAL_PREVIEW_BANNER_NOTE`
（⛔ 不得新增第二份字串常數）。FAKE 一律不輸出；桌機（≥641px）`display:none`（橫幅旁註已可見，不重複）。

本檔分四層：(1) AppTest 輸出契約（Real 五頁恰 1 個、FAKE 6 場景×5 頁 0 個、降級態 0 個且降級警示仍在、escape）；
(2) 負控 teeth（讓元件也在 FAKE 輸出／改文字 → 判定器必紅）；(3) CSS 靜態；(4) 真瀏覽器（marker `ui2_browser`）。
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import re
from html import escape

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.pages import PAGE_IDS, SCENARIO_IDS

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_UI2 = ROOT / "app_ui2.py"
_NOTE_RE = re.compile(r'<div class="ui2-real-mobile-note"[^>]*>(.*?)</div>', re.S)   # 只比對元素本體；CSS 內的 `.ui2-real-mobile-note` 選擇器不算


# ── 判定器（teeth 與主測試共用，確保「判定器自己會紅」）──
def note_texts(blob: str) -> list[str]:
    return _NOTE_RE.findall(blob)


def real_violations(blob: str, expected: str | None = None) -> list[str]:
    exp = escape(T.REAL_PREVIEW_BANNER_NOTE if expected is None else expected)
    got = note_texts(blob)
    out: list[str] = []
    if len(got) != 1:
        out.append(f"Real 應恰 1 個 ui2-real-mobile-note，實得 {len(got)}")
    elif got[0] != exp:
        out.append(f"文字不符：{got[0]!r} != {exp!r}")
    return out


def fake_violations(blob: str) -> list[str]:
    n = len(note_texts(blob))
    return [f"FAKE 不得輸出 ui2-real-mobile-note，實得 {n}"] if n else []


# ── AppTest ──
def _blob(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _at(feed: str, scenario: str | None = None):
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    a.session_state["ui2_feed"] = feed
    if scenario:
        a.session_state["ui2_scenario"] = scenario
    return a.run(timeout=60)


@pytest.fixture
def offline_real(monkeypatch):
    """Real 讀取固定為『三個事實皆取不到』的快照：離線、確定性；Real 標示與 VM 路徑照舊（不是降級）。"""
    from src.services.ui2.real_canonical import RealFeedSnapshot
    from src.ui2.shell import app as shell
    monkeypatch.setattr(shell, "read_real_snapshot",
                        lambda: RealFeedSnapshot.of(None, "OSError", None, "OSError", kbar_error="OSError"))
    return shell


def test_real_every_page_has_exactly_one_note_with_the_banner_note_text(offline_real):
    at = _at("real")
    for p in PAGE_IDS:
        at.radio(key="ui2_page").set_value(p).run(timeout=60)
        blob = _blob(at)
        assert not at.exception, (p, at.exception)
        assert real_violations(blob) == [], p
        assert 'data-ui2-degraded' not in blob, p            # 非降級路徑
        assert blob.count('class="ui2-banner"') == 1, p       # 橫幅單行佈局不變


def test_fake_six_scenarios_by_five_pages_never_output_the_note():
    for sc in SCENARIO_IDS:
        at = _at("fake", sc)
        for p in PAGE_IDS:
            at.radio(key="ui2_page").set_value(p).run(timeout=60)
            assert not at.exception, (sc, p)
            assert fake_violations(_blob(at)) == [], (sc, p)


def test_real_with_empty_banner_text_outputs_no_note(offline_real, monkeypatch):
    orig = offline_real.get_real_page_vm
    monkeypatch.setattr(offline_real, "get_real_page_vm",
                        lambda *a, **k: dataclasses.replace(orig(*a, **k), banner_text=None))
    at = _at("real")
    for p in PAGE_IDS:
        at.radio(key="ui2_page").set_value(p).run(timeout=60)
        assert not at.exception, p
        assert note_texts(_blob(at)) == [], p


def degraded_violations(blob: str) -> list[str]:
    out = [] if blob.count('data-ui2-degraded="1"') == 1 else ["降級警示應恰 1 個"]
    n = len(note_texts(blob))
    return out + ([f"降級態不得輸出 ui2-real-mobile-note（該句指向卡片，降級時卡片數值已隱藏），實得 {n}"] if n else [])


def _degraded_at(monkeypatch):
    from src.ui2.shell import app as shell

    def boom():
        raise RuntimeError("secret-token")
    monkeypatch.setattr(shell, "read_real_snapshot", boom)
    return shell


def test_real_degraded_outputs_no_note_but_keeps_the_degraded_notice(monkeypatch):
    _degraded_at(monkeypatch)
    at = _at("real")
    for p in PAGE_IDS:
        at.radio(key="ui2_page").set_value(p).run(timeout=60)
        blob = _blob(at)
        assert not at.exception, p
        assert degraded_violations(blob) == [], p
        assert "secret-token" not in blob, p
        assert blob.index('data-ui2-degraded="1"') < blob.index('class="ui2-pagetitle"'), p


def test_teeth_degraded_also_outputting_the_note_turns_the_degraded_check_red(monkeypatch):
    shell = _degraded_at(monkeypatch)
    orig = shell.degraded_notice_html
    monkeypatch.setattr(shell, "degraded_notice_html",
                        lambda t: orig(t) + shell.real_mobile_note_html(T.REAL_PREVIEW_BANNER_NOTE))   # 突變：降級也輸出小字
    assert degraded_violations(_blob(_at("real"))) != []


def test_note_text_is_escaped(offline_real, monkeypatch):
    evil = 'x<script>alert(1)</script>&"q"'
    monkeypatch.setattr(offline_real, "REAL_PREVIEW_BANNER_NOTE", evil)
    blob = _blob(_at("real"))
    got = note_texts(blob)
    assert got == [escape(evil)], got
    assert "<script>alert(1)</script>" not in blob.split('class="ui2-real-mobile-note"', 1)[1].split("</div>", 1)[0]


def test_no_second_copy_of_the_note_string_in_the_shell_or_component_sources():
    for rel in ("src/ui2/shell/app.py", "src/ui2/shell/css.py", "src/ui2/components/html.py"):
        assert "目前僅部分台股資料已接入" not in (ROOT / rel).read_text(encoding="utf-8"), rel


# ── 負控（突變 teeth）──
def test_teeth_note_output_in_fake_turns_the_fake_check_red(monkeypatch):
    from src.ui2.shell import app as shell
    orig = shell.get_preview_page_vm
    monkeypatch.setattr(shell, "get_preview_page_vm",
                        lambda *a, **k: dataclasses.replace(orig(*a, **k), is_fake=False))   # 突變：讓 FAKE 也走 Real 揭露分支
    at = _at("fake", "loaded")
    assert fake_violations(_blob(at)) != []


def test_teeth_changed_text_turns_the_real_check_red(offline_real, monkeypatch):
    orig = offline_real.real_mobile_note_html
    monkeypatch.setattr(offline_real, "real_mobile_note_html", lambda text: orig(text + "（改）"))
    assert real_violations(_blob(_at("real"))) != []


def test_teeth_missing_note_turns_the_real_check_red(offline_real, monkeypatch):
    monkeypatch.setattr(offline_real, "real_mobile_note_html", lambda text: "")
    assert real_violations(_blob(_at("real"))) != []


# ── CSS 靜態 ──
def test_css_default_hidden_and_shown_only_inside_the_mobile_media_query():
    from src.ui2.shell.css import CSS
    assert ".ui2-real-mobile-note{display:none" in CSS
    m = re.search(r"@media \(max-width:640px\)\{\.ui2-real-mobile-note\{([^}]*)\}\}", CSS)
    assert m, "缺 ≤640px 顯示規則"
    body = m.group(1)
    assert "display:block" in body and "white-space:normal" in body
    assert "nowrap" not in body and "ellipsis" not in body and "overflow:hidden" not in body     # 自然換行，不截斷
    assert "font-size:.8rem" in body and "opacity:.75" in body
    # 桌機（≥641px）連同 Streamlit 元素容器一起移除，避免空容器仍佔 1rem 元素間距而擠動頁面
    assert re.search(r"@media \(min-width:641px\)\{[^}]*:has\(\.ui2-real-mobile-note\)\{display:none\}", CSS)


def test_css_keeps_the_wide_banner_note_mobile_hide_rule():
    from src.ui2.shell.css import CSS
    assert "@media (max-width:640px){.ui2-banner__note--wide{display:none}}" in CSS


# ═════════════════════ 真瀏覽器（marker ui2_browser）═════════════════════
_JS_NOTE = """() => {
  const n = document.querySelector('.ui2-real-mobile-note');
  const nav = document.querySelector('.st-key-ui2_nav').getBoundingClientRect();
  const t = document.querySelector('.ui2-pagetitle');
  const de = document.documentElement;
  const base = {present: !!n, nav_bottom: nav.bottom, title_top: t ? t.getBoundingClientRect().top : null,
                doc_sw: de.scrollWidth, inner_w: innerWidth, body_sw: document.body.scrollWidth};
  if (!n) return base;
  const cs = getComputedStyle(n), r = n.getBoundingClientRect();
  const host = n.closest('[data-testid="stElementContainer"]');
  const rg = document.createRange(); rg.selectNodeContents(n);
  const rects = [...rg.getClientRects()];
  return {...base, display: cs.display, host_display: host ? getComputedStyle(host).display : null,
          top: r.top, bottom: r.bottom, h: r.height, left: r.left, right: r.right,
          sw: n.scrollWidth, cw: n.clientWidth, text: n.innerText.trim(), fs: parseFloat(cs.fontSize), ws: cs.whiteSpace,
          to: cs.textOverflow, ov: cs.overflow, lines: new Set(rects.map(x => Math.round(x.top))).size,
          text_right: Math.max(0, ...rects.map(x => x.right)), text_left: Math.min(1e9, ...rects.map(x => x.left))};
}"""

PAGES = ["📊 市場", "🎯 標的", "💼 持股", "👤 我的", "🗂 資料"]
MOBILE_VPS = [(390, 844), (360, 640), (320, 568)]
HIDDEN_VPS = [(1280, 900), (1440, 900), (641, 800), (740, 800)]
_REPORT: dict[str, object] = {}


@pytest.fixture(scope="module")
def pw():
    from tests.ui2_browser import require_browser
    with require_browser()() as p:
        yield p


@pytest.fixture(scope="module")
def browser(pw):
    from tests.ui2_browser import launch_or_fail
    b = launch_or_fail(pw)
    yield b
    b.close()


@pytest.fixture(scope="module")
def url():
    from tests.ui2_viewport import measure_viewport as MV
    proc, u = MV.start_server(ROOT)
    yield u
    proc.kill()


def _ui(browser, url, vw, vh, query=""):
    from tests.test_ui2_drawer_browser import Ui
    return Ui(browser, url, {"width": vw, "height": vh}, query, mobile=vw <= 768)


def _page_ids():
    return list(zip(PAGES, ["p4_market", "p4_target", "p4_hold", "p4_me", "p4_data"]))


@pytest.mark.ui2_browser
@pytest.mark.parametrize("vw,vh", MOBILE_VPS, ids=[f"{w}x{h}" for w, h in MOBILE_VPS])
def test_browser_real_mobile_note_visible_complete_not_overlapping(browser, url, vw, vh):
    ui = _ui(browser, url, vw, vh)          # 一般入口＝Real（D2-A）
    try:
        for label, pid in _page_ids():
            ui.click_page(label, pid)
            m = ui.pg.evaluate(_JS_NOTE)
            ctx = (vw, pid)
            assert m["present"], ctx
            assert m["display"] == "block", (ctx, m)
            assert m["text"] == T.REAL_PREVIEW_BANNER_NOTE, (ctx, m)
            assert m["h"] > 0 and m["lines"] >= 1, (ctx, m)
            assert m["sw"] <= m["cw"], (ctx, m)                                   # 無橫向溢出
            assert m["text_left"] >= -0.5 and m["text_right"] <= m["inner_w"] + 0.5, (ctx, m)   # 文字完整在視窗內
            assert m["doc_sw"] <= m["inner_w"] and m["body_sw"] <= m["inner_w"], (ctx, m)       # 頁面無橫向捲動
            assert m["to"] != "ellipsis" and m["ov"] == "visible" and m["ws"] == "normal", (ctx, m)
            assert m["top"] >= m["nav_bottom"] - 0.5, (ctx, m)                    # 不被 fixed 導覽遮蓋
            assert m["title_top"] is not None and m["bottom"] <= m["title_top"] + 0.5, (ctx, m)   # 與頁標題不重疊
            assert abs(m["fs"] - 12.8) < 0.6, (ctx, m)                              # .8rem 小字
            _REPORT[f"{vw}|{pid}"] = {k: round(m[k], 1) for k in ("h", "top", "nav_bottom", "title_top", "lines")}
        assert ui.errs == []
    finally:
        ui.close()


@pytest.mark.ui2_browser
@pytest.mark.parametrize("vw,vh", HIDDEN_VPS, ids=[f"{w}x{h}" for w, h in HIDDEN_VPS])
def test_browser_real_note_is_hidden_from_641px_up(browser, url, vw, vh):
    ui = _ui(browser, url, vw, vh)
    try:
        for label, pid in _page_ids():
            ui.click_page(label, pid)
            m = ui.pg.evaluate(_JS_NOTE)
            assert m["present"], (vw, pid)                         # Real 仍輸出（只是桌機不顯示）
            assert m["display"] == "none" and m["host_display"] == "none", (vw, pid, m)
            assert m["h"] == 0, (vw, pid, m)
            assert m["doc_sw"] <= m["inner_w"], (vw, pid, m)
    finally:
        ui.close()


@pytest.mark.ui2_browser
def test_browser_fake_mobile_has_no_note(browser, url):
    ui = _ui(browser, url, 390, 844, "ui2_dev=1")      # Ui 於 ui2_dev=1 開頁後明示選 FAKE
    try:
        for label, pid in _page_ids():
            ui.click_page(label, pid)
            m = ui.pg.evaluate(_JS_NOTE)
            assert m["present"] is False, (pid, m)
    finally:
        ui.close()


@pytest.mark.ui2_browser
@pytest.mark.parametrize("vw,vh", MOBILE_VPS, ids=[f"{w}x{h}" for w, h in MOBILE_VPS])
def test_browser_report_market_real_first_screen_margin(browser, url, vw, vh):
    """只回報數值（Real 場景不套 p2_nav_margin_160 門檻）：📊 市場、手機、Real 的『第一個後續內容區塊頂緣』與底部保留線。"""
    from tests.ui2_viewport import measure_viewport as MV
    ui = _ui(browser, url, vw, vh)
    try:
        m = MV.measure_state(ui.pg, vw, vh)
        line, fb = MV._nav_line(m), m.get("first_block_after_l1_top")
        assert line is not None and fb is not None
        _REPORT[f"margin|{vw}"] = {"first_block_after_l1_top": round(fb, 1), "nav_line": line, "margin": round(line - fb, 1)}
        print("UI2_MOBILE_NOTE_REPORT", json.dumps(_REPORT, ensure_ascii=False, sort_keys=True))
    finally:
        ui.close()


@pytest.mark.ui2_browser
def test_browser_degraded_mobile_has_no_note_and_keeps_nav_margin(browser):
    """降級（Real 讀取整體失敗）態不輸出小字：該句指向卡片，而降級時卡片數值已隱藏。📊 手機 nav_margin 維持 ≥160（既有 batch2 守衛的同一門檻）。"""
    from tests.ui2_viewport import degraded as DG
    from tests.ui2_viewport import measure_viewport as MV
    proc, u = DG.start_degraded_server(ROOT)
    ui = None
    try:
        ui = _ui(browser, u, 390, 844)
        m = MV.measure_state(ui.pg, 390, 844)
        margin = MV._nav_line(m) - m["first_block_after_l1_top"]
        print("UI2_DEGRADED_NAV_MARGIN", round(margin, 1))
        assert ui.pg.evaluate("() => document.querySelectorAll('.ui2-real-mobile-note').length") == 0
        assert ui.pg.evaluate("() => document.querySelectorAll('[data-ui2-degraded]').length") == 1
        assert margin >= MV.P2_NAV_MARGIN_MIN_PX - 0.05, margin
    finally:
        if ui:
            ui.close()
        proc.kill()
