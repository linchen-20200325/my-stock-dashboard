"""NUI2-TARGET-LOOKUP-VISUAL-PROTOTYPE：隔離離線原型的守衛（DEC-203）。

原型：docs/vnext/prototypes/nui2_target_lookup/index.html（與 App 完全隔離；僅示範，不是正式施工）。
- 靜態斷言（fast lane 必跑）：解析 HTML 字串。
- 瀏覽器斷言：Playwright 不在 fast lane 依賴內、Chromium 可能不存在 → 缺任一就 skip。
  ⛔ 不加 `ui2_browser` marker、不被 ui2-browser lane 收進去（該 lane 只跑兩個指名檔，且要求 skipped=0）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from shared.ui2_contract import text as T

ROOT = Path(__file__).resolve().parent.parent
PROTO = ROOT / "docs" / "vnext" / "prototypes" / "nui2_target_lookup" / "index.html"
HTML = PROTO.read_text(encoding="utf-8")
BANNED = ("買進", "賣出", "推薦", "目標價")
STATES = {  # 代碼 → 畫面上必須出現的字樣
    "9001": "🟢 資料日在規則內",
    "9002": "⚠ 過期 9 天",
    "9003": T.TEXT_MISSING_NOT_FETCHED,
    "9004": T.TEXT_UNAVAILABLE,
    "9005": "資料日期不可信，暫時無法顯示",
    "9006": T.TEXT_NOT_EVALUATED,
    "9099": "查無此標的",
}


def test_banner_and_isolation_static():
    assert "示範原型・FAKE 資料，不是市場資料" in HTML
    for bad in BANNED:
        assert bad not in HTML, bad
    # 零外部資源／零網路
    assert not re.search(r"https?://", HTML)
    assert not re.search(r"\b(fetch|XMLHttpRequest|WebSocket|sendBeacon|importScripts)\b", HTML)
    assert not re.search(r"""(src|href)\s*=\s*["'](?!#)""", HTML)
    assert "@import" not in HTML and "url(" not in HTML


def test_reused_official_strings_verbatim():
    for s in (T.TEXT_MISSING_NOT_FETCHED, T.TEXT_MISSING_NOT_READY, T.TEXT_ASOF_MISSING, T.TEXT_UNAVAILABLE,
              T.TEXT_NOT_EVALUATED, T.TEXT_NOT_LOADED, T.TEXT_STALE_DAYS_FMT):
        assert s in HTML, s


def test_no_real_ticker_format():
    body = re.sub(r"<style.*?</style>", "", HTML, flags=re.S)
    for m in re.finditer(r"(?<![\w\-.:/#])(\d{4,6})(?![\w\-.:/])", body):
        n = int(m.group(1))
        assert len(m.group(1)) == 4 and 9001 <= n <= 9099, m.group(0)


def test_no_app_references_prototype():
    for p in list((ROOT / "src").rglob("*.py")) + [ROOT / "app.py", ROOT / "app_ui2.py"]:
        if p.exists():
            assert "nui2_target_lookup" not in p.read_text(encoding="utf-8", errors="ignore"), p


def _browser():
    pw = pytest.importorskip("playwright.sync_api")
    return pw


def _launch(p):
    import glob
    try:
        return p.chromium.launch()
    except Exception:
        for exe in sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux64/chrome")):
            try:
                return p.chromium.launch(executable_path=exe)
            except Exception:
                continue
    pytest.skip("無可用 Chromium")


@pytest.mark.parametrize("size", [(390, 844), (1440, 900)])
def test_browser_states_reachable_and_clean(size):
    pw = _browser()
    with pw.sync_playwright() as p:
        b = _launch(p)
        pg = b.new_page(viewport={"width": size[0], "height": size[1]})
        reqs, errs = [], []
        pg.on("request", lambda r: reqs.append(r.url))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(PROTO.as_uri())
        assert "示範原型・FAKE 資料，不是市場資料" in pg.inner_text("#banner")
        for code, expect in STATES.items():
            pg.click('[data-mode="lookup"]')
            pg.fill("#q", code)
            pg.press("#q", "Enter")
            txt = pg.inner_text("#result")
            assert expect in txt, (code, txt)
            for bad in BANNED:
                assert bad not in txt
            assert not re.search(r"(?<![\w\-.:/])(?!90\d\d)\d{4}(?![\w\-.:/])", txt), (code, txt)
        # 未來日不得印出不可信日期
        pg.fill("#q", "9005"); pg.press("#q", "Enter")
        assert "2026-12-05" not in pg.inner_text("#result")
        # 切回市場精選：搜尋 aria-disabled 並說明原因
        pg.click('[data-mode="curated"]')
        assert pg.get_attribute("#go", "aria-disabled") == "true"
        assert "精選尚未開放" in pg.inner_text("#panel-curated")
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert all(u.startswith("file://") for u in reqs), reqs
        assert not errs, errs
        b.close()
