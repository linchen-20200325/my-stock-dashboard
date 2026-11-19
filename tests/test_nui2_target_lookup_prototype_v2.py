"""NUI2-TARGET-LOOKUP-VISUAL-PROTOTYPE V2 候選的守衛（DEC-204；授權 #1199 comment 7003017605）。

V2：docs/vnext/prototypes/nui2_target_lookup/index_v2.html（與 App 完全隔離；僅示範，不是正式施工）。
V1 測試檔（test_nui2_target_lookup_prototype.py）不改；本檔另行覆蓋 V2。
- 靜態斷言（fast lane 必跑）；瀏覽器斷言缺 Playwright／Chromium 則 skip。
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
PROTO = PDIR / "index_v2.html"
README = (PDIR / "README_V2.md").read_text(encoding="utf-8")
HTML = PROTO.read_text(encoding="utf-8")
BANNED = ("買進", "賣出", "推薦", "目標價")
AUTH_ALLOWED = {
    "示範原型・FAKE 資料，不是市場資料", "示範值", "資料日期不可信，暫時無法顯示",
    "9001 示範甲", "9002 示範乙", "9003 示範丙", "9004 示範丁", "9005 示範戊", "9006 示範己", "9099",
}
#: V2 不得出現的字樣（裁示 (a)(b)(c)(d)）
REMOVED_PHRASES = ("資料日在規則內", "部分欄位未取得", "／6 欄", "欄有值", "來源逾時", "來源有回應", "資料日期不可信，不顯示",
                   "晚於基準日", "STALE_DAYS", "規則")
#: 裁示 (e) 規定屬「下一版 UI 設計候選」的操作提示（須為 tier=design）
DESIGN_REQUIRED = {"輸入代碼", "請先輸入代碼", "清除查詢結果", "請先切換到「即時查一檔」"}
#: 裁示 (e) 規定僅原型適用的字句（須為 tier=proto）
PROTO_REQUIRED = {"查無此標的", "示範來源"}
ERR_RGB = "rgb(255, 123, 114)"   # --dng
POS_RGB = "rgb(63, 185, 80)"     # --pos


def _registry(html: str = HTML) -> dict:
    m = re.search(r'<script type="application/json" id="strings">\s*(\{.*?\})\s*</script>', html, re.S)
    assert m, "找不到 #strings 登錄表"
    return json.loads(m.group(1))


def _norm(s: str) -> str:
    s = re.sub(r"\d{4}-\d{2}-\d{2}", "{date}", s)
    return re.sub(r"\d+", "{n}", s)


def _readme_list(name: str, readme: str = README) -> list[str]:
    m = re.search(r"<!-- %s:BEGIN -->\n(.*?)\n<!-- %s:END -->" % (name, name), readme, re.S)
    assert m, name
    return [ln[2:] for ln in m.group(1).split("\n") if ln.startswith("- ")]


def _tier_mismatch(reg: dict, readme: str = README) -> list[str]:
    """registry 與 README_V2 三欄表不一致的項目（空＝一致）。"""
    exp = {
        "REUSE": sorted(v["t"] for v in reg.values() if v["c"] == "reuse"),
        "DESIGN": sorted(v["t"] for v in reg.values() if v["c"] == "proposed" and v.get("tier") == "design"),
        "PROTO": sorted(v["t"] for v in reg.values() if v["c"] == "proposed" and v.get("tier") == "proto"),
    }
    return [k for k, v in exp.items() if sorted(_readme_list(k, readme)) != v]


_SRC_CACHE: dict[str, tuple[set[str], str]] = {}


def _source(rel: str) -> tuple[set[str], str]:
    if rel not in _SRC_CACHE:
        txt = (ROOT / rel).read_text(encoding="utf-8")
        lits: set[str] = set()
        if rel.endswith(".py"):
            lits = {n.value for n in ast.walk(ast.parse(txt)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        _SRC_CACHE[rel] = (lits, txt)
    return _SRC_CACHE[rel]


def _forbidden_js(html: str) -> list[str]:
    return [p for p in (r"\beval\s*\(", r"\bnew\s+Function\b", r"\bFunction\s*\(") if re.search(p, html)]


def _removed_hits(html: str) -> list[str]:
    reg_text = " ".join(v["t"] for v in _registry(html).values())
    return [p for p in REMOVED_PHRASES if p in reg_text]


_DATE_RX = re.compile(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}月\d{1,2}日|(?<!\d)\d{1,2}/\d{1,2}(?!\d)")


def _has_date(text: str) -> bool:
    return bool(_DATE_RX.search(text))


# ───────────────────────── 靜態 ─────────────────────────
def test_v1_files_still_present():
    for rel in ("index.html", "README.md", "screenshots/mobile_390_02_ok_9001.png"):
        assert (PDIR / rel).exists(), rel
    assert "🟢 資料日在規則內" in (PDIR / "index.html").read_text(encoding="utf-8")   # V1 原樣（V2 不改 V1）


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
    assert _forbidden_js(HTML + "<script>eval('1')</script>")
    assert _forbidden_js(HTML + "<script>new Function('1')</script>")
    assert _forbidden_js(HTML + "<script>Function('1')</script>")


def test_registry_classification_and_readme_v2_consistent():
    reg = _registry()
    for k, v in reg.items():
        assert v["c"] in ("reuse", "auth", "proposed", "meta"), k
        if v["c"] == "proposed":
            assert v.get("tier") in ("design", "proto"), (k, "proposed 字串必須標 tier=design|proto")
        else:
            assert "tier" not in v, k
        if v["c"] == "reuse":
            lits, txt = _source(v["s"])
            if v["s"].endswith(".py"):
                assert v["t"] in lits, (k, v["t"], v["s"])
            else:
                assert v["t"] in txt, (k, v["t"], v["s"])
        elif v["c"] == "auth":
            assert v["t"] in AUTH_ALLOWED, (k, v["t"])
    assert reg["tag"]["t"] == "PROPOSED・未核准"
    assert _tier_mismatch(reg) == []
    by_text = {v["t"]: v for v in reg.values()}
    for t in DESIGN_REQUIRED:
        assert by_text[t]["c"] == "proposed" and by_text[t]["tier"] == "design", t
    for t in PROTO_REQUIRED:
        assert by_text[t]["c"] == "proposed" and by_text[t]["tier"] == "proto", t
    assert "PROPOSED・未核准" in README and "不屬於正式 UI" in README


def test_readme_v2_content_gates():
    for s in ("7003017605", "(a)", "(b)", "(c)", "仍待**使用者最終 Visual 確認**", "不得合併進正式 New UI2", "HOLD",
              "個股權利", "L3 lookup service contract", "OneBrain"):
        assert s in README, s
    assert README.count("\n") < 110   # ≤2 頁


def test_tier_consistency_check_has_teeth():
    reg = _registry()
    bad = json.loads(json.dumps(reg))
    bad["clear"]["tier"] = "proto"          # 突變：把設計候選誤標成僅原型
    assert _tier_mismatch(bad) == ["DESIGN", "PROTO"]
    assert _tier_mismatch(reg, README.replace("- 輸入代碼\n", "", 1)) != []   # 突變：README 少一條


def test_removed_phrases_absent_and_check_has_teeth():
    assert _removed_hits(HTML) == []
    for phrase in REMOVED_PHRASES:
        mut = HTML.replace('"banner":', '"zz":{"t":"%s","c":"meta"},\n"banner":' % phrase, 1)
        assert phrase in _removed_hits(mut), phrase
    body = re.sub(r'<script type="application/json".*?</script>', "", HTML, flags=re.S)
    assert 'chip("pos"' not in body and "chip--pos" not in re.sub(r"<style.*?</style>", "", body, flags=re.S)


def test_script_has_no_literal_ui_strings():
    body = re.sub(r'<script type="application/json".*?</script>', "", HTML, flags=re.S)
    body = re.sub(r"<style.*?</style>", "", body, flags=re.S)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"(?m)//.*$", "", body)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"<title>.*?</title>", "", body, flags=re.S)
    assert not re.search(r"[　-鿿＀-￯]", body), re.findall(r".{0,15}[　-鿿＀-￯].{0,15}", body)[:5]
    assert "function S(" in body and "R[id].c === \"proposed\"" in body


def test_reused_official_strings_verbatim():
    texts = {v["t"] for v in _registry().values()}
    for s in (T.TEXT_MISSING_NOT_FETCHED, T.TEXT_MISSING_NOT_READY, T.TEXT_ASOF_MISSING, T.TEXT_UNAVAILABLE,
              T.TEXT_NOT_EVALUATED, T.TEXT_NOT_LOADED, T.TEXT_STALE_DAYS_FMT):
        assert s in texts, s


def test_no_real_ticker_format_and_no_app_reference():
    body = re.sub(r"<style.*?</style>", "", HTML, flags=re.S)
    for m in re.finditer(r"(?<![\w\-.:/#])(\d{4,6})(?![\w\-.:/])", body):
        assert len(m.group(1)) == 4 and 9001 <= int(m.group(1)) <= 9099, m.group(0)
    for p in list((ROOT / "src").rglob("*.py")) + [ROOT / "app.py", ROOT / "app_ui2.py"]:
        if p.exists():
            assert "nui2_target_lookup" not in p.read_text(encoding="utf-8", errors="ignore"), p


def test_has_date_helper_has_teeth():
    for d in ("資料日 2026-12-05", "2026/12/05", "12月5日", "12/05", "2026.12.05", "2026-11-19"):
        assert _has_date(d), d
    assert not _has_date("資料日未提供")


# ───────────────────────── 瀏覽器（缺套件／Chromium 則 skip） ─────────────────────────
def _launch(p):
    import glob
    attempts = [{}] + [{"executable_path": e} for e in sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))] \
        + [{"executable_path": "/usr/bin/google-chrome"}]
    for kw in attempts:
        try:
            return p.chromium.launch(**kw)
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
    out.push({t, tag: el.classList.contains('prop-tag'),
              next: el.nextElementSibling ? el.nextElementSibling.classList.contains('prop-tag') : false});
  }
  document.querySelectorAll('[placeholder]').forEach(e => out.push({t: e.getAttribute('placeholder'), tag: false, attr: true}));
  return out;
}"""

_POS_JS = """() => [...document.querySelectorAll('#result *')].filter(e => e.classList.contains('chip--pos') ||
  getComputedStyle(e).color === '%s' || getComputedStyle(e).borderTopColor === '%s').length""" % (POS_RGB, POS_RGB)


def _query(pg, code, expand=True):
    pg.click('[data-mode="lookup"]')
    pg.fill("#q", code)
    pg.press("#q", "Enter")
    if expand:
        pg.evaluate("document.querySelectorAll('#result details').forEach(d => d.open = true)")
    return pg.inner_text("#result")


@pytest.mark.parametrize("size", [(390, 844), (1440, 900)])
def test_browser_v2_states(size):
    pw = pytest.importorskip("playwright.sync_api")
    reg = _registry()
    known = {_norm(v["t"]): v["c"] for v in reg.values()}
    with pw.sync_playwright() as p:
        b = _launch(p)
        pg = b.new_page(viewport={"width": size[0], "height": size[1]})
        reqs, errs, dialogs = [], [], []
        pg.on("request", lambda r: reqs.append(r.url))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        pg.goto(PROTO.as_uri())
        assert "示範原型・FAKE 資料，不是市場資料" in pg.inner_text("#banner")
        unknown: set[str] = set()

        def audit(label):
            for it in pg.evaluate(_EXTRACT):
                nt = _norm(it["t"])
                if nt in ("{n}", "{date}"):
                    continue
                if it["tag"]:
                    assert nt in (_norm(reg["tag"]["t"]), _norm(reg["ph_tag"]["t"])), (label, it)
                    continue
                if nt not in known:
                    unknown.add(f"{label}: {it['t']}")
                elif known[nt] == "proposed" and not it.get("attr"):
                    assert it.get("next"), (label, it)

        audit("idle")
        texts = {}
        for code in ("9001", "9002", "9003", "9004", "9005", "9006", "9099"):
            texts[code] = _query(pg, code)
            for bad in BANNED + REMOVED_PHRASES:
                assert bad not in texts[code], (code, bad)
            assert not re.search(r"(?<![\w\-.:/])(?!90\d\d)\d{4}(?![\w\-.:/])", texts[code]), code
            audit(code)
        for extra in ("2330", "", "abc"):
            pg.fill("#q", extra); pg.press("#q", "Enter"); audit("x" + extra)
        pg.click('[data-mode="curated"]'); audit("curated")
        assert not unknown, sorted(unknown)

        # 9001：只有事實層——無任何 chip、無綠色、有資料日與示範值與一行 evidence
        _query(pg, "9001")
        assert pg.locator("#result .chip").count() == 0 and pg.locator("#result .chip--pos").count() == 0
        assert pg.evaluate(_POS_JS) == 0
        assert "資料日 2026-11-18" in texts["9001"] and "示範值" in texts["9001"]
        assert pg.locator("#result .evid").count() == 1
        assert "來源" in pg.inner_text("#result .evid") and "｜" in pg.inner_text("#result .evid")
        # 突變：塞入綠色 chip，檢查必須轉紅
        pg.evaluate("() => { const s = document.createElement('span'); s.className = 'chip chip--pos'; s.textContent = 'x'; document.getElementById('result').appendChild(s); }")
        assert pg.evaluate(_POS_JS) > 0
        # 9002：僅沿用既有「過期 N 天」格式、無規則、仍一行 evidence
        assert "⚠ 過期 9 天" in texts["9002"] and "2026-11-10" in texts["9002"]
        # 9003：無總結 chip／欄數；逐欄沿用既有缺值字樣
        _query(pg, "9003")
        assert pg.locator("#result .chip").count() == 0
        assert pg.locator('#result .field[data-state="missing"]').count() == 3
        t3 = pg.inner_text("#result")
        assert T.TEXT_MISSING_NOT_FETCHED in t3 and T.TEXT_MISSING_NOT_READY in t3
        assert "部分欄位未取得" not in t3 and "／6" not in t3 and "6 欄" not in t3
        # 9004／9005：同紅、文字不同；9005 全頁（含展開）無任何日期、無六維值
        t4 = _query(pg, "9004")
        err4 = pg.evaluate("getComputedStyle(document.querySelector('#result .err')).borderTopColor")
        assert pg.get_attribute("#result .err", "role") == "alert"
        t5 = _query(pg, "9005")
        err5 = pg.evaluate("getComputedStyle(document.querySelector('#result .err')).borderTopColor")
        assert pg.get_attribute("#result .err", "role") == "alert"
        assert err4 == err5 == ERR_RGB, (err4, err5)
        assert T.TEXT_UNAVAILABLE in t4 and "資料日期不可信" not in t4 and "日期" not in t4.replace("資料日", "")
        assert "資料日期不可信，暫時無法顯示" in t5 and T.TEXT_UNAVAILABLE not in t5
        assert pg.locator("#result .err").inner_text().strip() != ""
        assert pg.locator("#result .field").count() == 0 and "示範值" not in t5
        whole = pg.evaluate("document.body.innerText")   # 全頁（含展開、無排除）
        assert not _has_date(whole), whole
        assert t4.split("\n")[1:] != t5.split("\n")[1:]
        # 突變：9005 印出日期時，全頁日期檢查必須轉紅
        for bad_date in ("2026-12-05", "2026/12/05", "12月5日", "12/05"):
            pg.evaluate("t => { const e = document.createElement('p'); e.textContent = t; document.getElementById('result').appendChild(e); }", bad_date)
            assert _has_date(pg.evaluate("document.body.innerText")), bad_date
            pg.evaluate("document.getElementById('result').lastElementChild.remove()")
        # 9002 數值中性色
        _query(pg, "9002")
        assert pg.evaluate("[...document.querySelectorAll('.field .v')].every(e => getComputedStyle(e).color === getComputedStyle(document.body).color)")
        # 查無：無加入觀察；真實代碼不回顯
        assert "加入觀察" not in _query(pg, "9099")
        r2 = _query(pg, "2330")
        assert "示範原型不查真實代碼" in r2 and "2330" not in r2
        # XSS：輸入 HTML 不得被注入、無對話框
        pg.fill("#q", "<img src=x onerror=alert(1)>"); pg.press("#q", "Enter")
        assert pg.locator("#result img").count() == 0 and not dialogs
        # a11y／觸控：互動元件 ≥44px；無水平溢出
        _query(pg, "9001")
        small = pg.evaluate("""() => [...document.querySelectorAll('button:not([hidden]), input, summary')]
          .filter(e => e.getClientRects().length).map(e => [e.textContent.trim().slice(0, 12), e.getBoundingClientRect().height, e.getBoundingClientRect().width])
          .filter(([_, h, w]) => h < 43.5 || w < 43.5)""")
        assert small == [], small
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        top = pg.evaluate("document.getElementById('res-card').getBoundingClientRect().top")
        assert top < size[1] * 0.6, top
        pg.click('[data-mode="curated"]')
        assert pg.get_attribute("#go", "aria-disabled") == "true"
        assert "精選尚未開放" in pg.inner_text("#panel-curated")
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert all(u.startswith("file://") for u in reqs), reqs
        assert not errs, errs
        b.close()
