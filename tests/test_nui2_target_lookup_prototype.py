"""NUI2-TARGET-LOOKUP-VISUAL-PROTOTYPE：隔離離線原型的守衛（DEC-203）。

原型：docs/vnext/prototypes/nui2_target_lookup/index.html（與 App 完全隔離；僅示範，不是正式施工）。
- 靜態斷言（fast lane 必跑）：解析 HTML 字串；字串登錄表（#strings）每條須是「重用 repo 逐字」「任務指定」或「README PROPOSED 清單」。
- 瀏覽器斷言：Playwright 不在 fast lane 依賴內、Chromium 可能不存在 → 缺任一就 skip。
  ⛔ 不加 `ui2_browser` marker、不被 ui2-browser lane 收進去（該 lane 只跑兩個指名檔，且要求 skipped=0）。
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from shared.ui2_contract import text as T

ROOT = Path(__file__).resolve().parent.parent
PDIR = ROOT / "docs" / "vnext" / "prototypes" / "nui2_target_lookup"
PROTO = PDIR / "index.html"
README = (PDIR / "README.md").read_text(encoding="utf-8")
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
#: 任務指定（授權）字串：橫幅、示範值、未來日文案、虛構標的命名（#1199 comment 7000042502 與協調者指示）。
AUTH_ALLOWED = {
    "示範原型・FAKE 資料，不是市場資料", "示範值", "資料日期不可信，暫時無法顯示",
    "9001 示範甲", "9002 示範乙", "9003 示範丙", "9004 示範丁", "9005 示範戊", "9006 示範己", "9099",
}


def _registry(html: str = HTML) -> dict:
    m = re.search(r'<script type="application/json" id="strings">\s*(\{.*?\})\s*</script>', html, re.S)
    assert m, "找不到 #strings 登錄表"
    return json.loads(m.group(1))


def _norm(s: str) -> str:
    s = s.replace("{base}", "{date}").replace("{tol}", "{n}")
    s = re.sub(r"\d{4}-\d{2}-\d{2}", "{date}", s)
    return re.sub(r"\d+", "{n}", s)


def _readme_proposed() -> list[str]:
    m = re.search(r"<!-- PROPOSED:BEGIN -->\n(.*?)\n<!-- PROPOSED:END -->", README, re.S)
    assert m
    return [ln[2:] for ln in m.group(1).split("\n") if ln.startswith("- ")]


_SRC_CACHE: dict[str, tuple[set[str], str]] = {}


def _source(rel: str) -> tuple[set[str], str]:
    if rel not in _SRC_CACHE:
        txt = (ROOT / rel).read_text(encoding="utf-8")
        lits: set[str] = set()
        if rel.endswith(".py"):
            lits = {n.value for n in ast.walk(ast.parse(txt)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        _SRC_CACHE[rel] = (lits, txt)
    return _SRC_CACHE[rel]


# ───────────────────────── 靜態 ─────────────────────────
def _forbidden_js(html: str) -> list[str]:
    return [p for p in (r"\beval\s*\(", r"\bnew\s+Function\b", r"\bFunction\s*\(") if re.search(p, html)]


def test_banner_and_isolation_static():
    assert "示範原型・FAKE 資料，不是市場資料" in HTML
    for bad in BANNED:
        assert bad not in HTML, bad
    assert not re.search(r"https?://", HTML)
    assert not re.search(r"\b(fetch|XMLHttpRequest|WebSocket|sendBeacon|importScripts)\b", HTML)
    assert not re.search(r"""(src|href)\s*=\s*["'](?!#)""", HTML)
    assert "@import" not in HTML and "url(" not in HTML
    assert _forbidden_js(HTML) == []


def test_forbidden_js_check_has_teeth():
    """突變：塞入 eval( ／ new Function 必須被偵測（否則檢查是空的）。"""
    assert _forbidden_js(HTML + "<script>eval('1')</script>")
    assert _forbidden_js(HTML + "<script>new Function('1')</script>")
    assert _forbidden_js(HTML + "<script>Function('1')</script>")


def test_registry_every_string_is_reused_authorized_or_listed_proposed():
    reg = _registry()
    prop_readme = _readme_proposed()
    prop_reg = [v["t"] for v in reg.values() if v["c"] == "proposed"]
    assert sorted(prop_readme) == sorted(prop_reg), "README PROPOSED 清單與登錄表不一致"
    for k, v in reg.items():
        assert v["c"] in ("reuse", "auth", "proposed", "meta"), k
        if v["c"] == "reuse":
            lits, txt = _source(v["s"])
            if v["s"].endswith(".py"):
                assert v["t"] in lits, (k, v["t"], v["s"])
            else:
                assert v["t"] in txt, (k, v["t"], v["s"])
        elif v["c"] == "auth":
            assert v["t"] in AUTH_ALLOWED, (k, v["t"])
    assert reg["tag"]["t"] == "PROPOSED・未核准"


def test_script_has_no_literal_ui_strings():
    """所有 CJK 字串都只能在 #strings 登錄表（JS 一律經 S()／raw() 取字，proposed 自動附小標）。"""
    body = re.sub(r'<script type="application/json".*?</script>', "", HTML, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"(?m)//.*$", "", body)
    body = re.sub(r"<title>.*?</title>", "", body, flags=re.S)
    assert not re.search(r"[　-鿿＀-￯]", body), re.findall(r".{0,15}[　-鿿＀-￯].{0,15}", body)[:5]
    assert "function S(" in body and "R[id].c === \"proposed\"" in body


def test_reused_official_strings_verbatim():
    for s in (T.TEXT_MISSING_NOT_FETCHED, T.TEXT_MISSING_NOT_READY, T.TEXT_ASOF_MISSING, T.TEXT_UNAVAILABLE,
              T.TEXT_NOT_EVALUATED, T.TEXT_NOT_LOADED, T.TEXT_STALE_DAYS_FMT):
        assert s in {v["t"] for v in _registry().values()}, s


def test_placeholder_and_no_real_ticker_format():
    assert _registry()["ph"]["t"] == "輸入代碼"
    body = re.sub(r"<style.*?</style>", "", HTML, flags=re.S)
    for m in re.finditer(r"(?<![\w\-.:/#])(\d{4,6})(?![\w\-.:/])", body):
        assert len(m.group(1)) == 4 and 9001 <= int(m.group(1)) <= 9099, m.group(0)


def test_no_app_references_prototype():
    for p in list((ROOT / "src").rglob("*.py")) + [ROOT / "app.py", ROOT / "app_ui2.py"]:
        if p.exists():
            assert "nui2_target_lookup" not in p.read_text(encoding="utf-8", errors="ignore"), p


# ───────────────────────── 瀏覽器（缺套件／Chromium 則 skip） ─────────────────────────
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


_EXTRACT = """() => {
  document.querySelectorAll('details').forEach(d => d.open = true);
  const out = [], w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = w.nextNode())) {
    const t = n.nodeValue.trim(); if (!t) continue;
    const el = n.parentElement;
    if (el.closest('script,style,[hidden]')) continue;
    const r = el.getClientRects(); if (!r.length) continue;
    out.push({t, tag: el.classList.contains('prop-tag'), prop: el.classList.contains('s') || el.classList.contains('chip') || el.tagName === 'STRONG' || el.tagName === 'H2' || el.tagName === 'BUTTON' || el.tagName === 'SUMMARY',
              next: el.nextElementSibling ? el.nextElementSibling.classList.contains('prop-tag') : false});
  }
  document.querySelectorAll('[placeholder]').forEach(e => out.push({t: e.getAttribute('placeholder'), tag: false, attr: true}));
  return out;
}"""


@pytest.mark.parametrize("size", [(390, 844), (1440, 900)])
def test_browser_states_reachable_clean_and_strings_classified(size):
    pw = pytest.importorskip("playwright.sync_api")
    reg = _registry()
    known = {_norm(v["t"]): v["c"] for v in reg.values()}
    with pw.sync_playwright() as p:
        b = _launch(p)
        pg = b.new_page(viewport={"width": size[0], "height": size[1]})
        reqs, errs = [], []
        pg.on("request", lambda r: reqs.append(r.url))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(PROTO.as_uri())
        assert "示範原型・FAKE 資料，不是市場資料" in pg.inner_text("#banner")
        unknown: set[str] = set()

        def audit(label):
            for it in pg.evaluate(_EXTRACT):
                nt = _norm(it["t"])
                if nt in ("{n}", "{date}"):
                    continue
                if it["tag"]:
                    assert nt == _norm(reg["tag"]["t"]) or nt == _norm(reg["ph_tag"]["t"]), (label, it)
                    continue
                if nt not in known:
                    unknown.add(f"{label}: {it['t']}")
                elif known[nt] == "proposed" and not it.get("attr"):   # 每個 proposed 字串後面都緊接可見小標（placeholder 由 ph_tag 標示）
                    assert it.get("next"), (label, it)

        audit("idle")
        for code, expect in STATES.items():
            pg.click('[data-mode="lookup"]')
            pg.fill("#q", code)
            pg.press("#q", "Enter")
            txt = pg.inner_text("#result")
            assert expect in txt, (code, txt)
            for bad in BANNED:
                assert bad not in txt
            assert not re.search(r"(?<![\w\-.:/])(?!90\d\d)\d{4}(?![\w\-.:/])", txt), (code, txt)
            audit(code)
        for extra in ("2330", "", "abc"):
            pg.fill("#q", extra); pg.press("#q", "Enter"); audit("x" + extra)
        pg.click('[data-mode="curated"]'); audit("curated")
        assert not unknown, sorted(unknown)
        pg.click('[data-mode="lookup"]')
        # 9003：部分缺值不得用綠色／正向 chip
        pg.fill("#q", "9003"); pg.press("#q", "Enter")
        assert pg.locator("#result .chip--pos").count() == 0
        assert "部分欄位未取得" in pg.inner_text("#result") and "3／6 欄有值" in pg.inner_text("#result")
        # 9005：不重用「來源目前不可用」、未來日不印
        pg.fill("#q", "9005"); pg.press("#q", "Enter")
        t5 = pg.inner_text("#result")
        assert "來源目前不可用" not in t5 and "2026-12-05" not in t5
        # 查無：無加入觀察；真實代碼語句
        pg.fill("#q", "9099"); pg.press("#q", "Enter")
        assert "加入觀察" not in pg.inner_text("#result")
        pg.fill("#q", "2330"); pg.press("#q", "Enter")
        r2 = pg.inner_text("#result")
        assert "示範原型不查真實代碼" in r2 and "2330" not in r2
        # 手機：查詢後結果卡在第一屏
        pg.fill("#q", "9001"); pg.press("#q", "Enter")
        top = pg.evaluate("document.getElementById('res-card').getBoundingClientRect().top")
        assert top < size[1] * 0.6, top
        # 切回市場精選
        pg.click('[data-mode="curated"]')
        assert pg.get_attribute("#go", "aria-disabled") == "true"
        assert "精選尚未開放" in pg.inner_text("#panel-curated")
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert all(u.startswith("file://") for u in reqs), reqs
        assert not errs, errs
        b.close()
