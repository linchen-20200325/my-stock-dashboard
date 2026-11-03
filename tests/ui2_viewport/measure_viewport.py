"""New UI2 Preview 的 viewport／y 座標量測（NUI2-PREVIEW-MOBILE-MEASURE；可重現腳本）。

用法（repo 根；需 Playwright＋Chromium）::

    python -m tests.ui2_viewport.measure_viewport --out docs/vnext/newui2_batch2 [--shots all|first|none]
    python -m tests.ui2_viewport.measure_viewport --url http://localhost:8501 --out /tmp/x   # 量既有 server

對 `streamlit run app_ui2.py` 於 390×844（手機）與 1440×900（桌機），四頁 ×（cold／loaded／missing／
stale／unavailable／not_evaluated）逐一量測並輸出 `viewport_measurements.json`＋截圖。

判定門檻**全部引用既有條文，不自創新門檻**（見 `THRESHOLDS`）。第一屏高度、導覽列高度出自
Freeze §16／Architecture Gate §3：手機第一屏可用高 = 844 − 底部導覽 53 = 791px。
本腳本是 Preview 層量測，⛔ 不連任何真資料（場景全為 FAKE）。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

VIEWPORTS: dict[str, tuple[int, int]] = {"mobile": (390, 844), "desktop": (1440, 900)}
#: Freeze §16 視窗說明／Gate §3：手機底部導覽 53px。
NAV_MOBILE_H = 53
#: 手機斷點（`src/ui2/shell/css.py` 的 `@media (max-width:768px)`）。
MOBILE_MAX_W = 768
#: 第一屏四問錨點（`src/ui2/components/html.py::first_screen_html` 的 `data-ui2-q`）。
FIRST_SCREEN_QS = ("q1", "q2", "q3", "q4")
NAV_LABELS = ("📊 市場", "🎯 標的", "💼 持股", "👤 我的")

#: 判定門檻與出處（⛔ 新門檻）。`id` 對應 `evaluate()` 的 check key。
THRESHOLDS: list[dict[str, str]] = [
    {"id": "first_screen_within_usable_height",
     "rule": "第一屏四問（① 現在狀態／② 是否需要行動／③ 下一步／④ 主 CTA）與頁面 context 列（Risk Cap 等）"
             "的元素底緣 ≤ 可用高：手機 = 844 − 底部導覽 53 = 791px；桌機 = 900px。",
     "source": "Freeze §16 視窗說明＋§0.1.6-2、Gate §3、Wireframes §0.4／§1／§8（px 數值出自 Freeze §16『可用高約 791px』）"},
    {"id": "first_screen_above_nav",
     "rule": "手機：第一屏元素底緣 ≤ 導覽列上緣（不被底部固定列遮住）；桌機：元素左緣 ≥ 左側導覽右緣。",
     "source": "Wireframes §0.4（W-1）／Freeze §16"},
    {"id": "no_horizontal_scroll",
     "rule": "document／stMain 的 scrollWidth ≤ clientWidth（無水平捲動）；第一屏區塊內容不被橫向裁切。",
     "source": "Gate §3（Mobile-first）、Audit Checklist 手機項（客戶 (5)-9）"},
    {"id": "nav_fixed_four",
     "rule": "導覽恰 4 項（📊 市場／🎯 標的／💼 持股／👤 我的）；手機＝底部固定（top = 844 − 53、貼底、全寬、4 格同列）；"
             "桌機＝左側固定（left = 0、垂直排列）；恰一項為當前頁。",
     "source": "Wireframes §0.4／§7 W-1；客戶 (5)-7（固定四頁、⛔ 第五頁）"},
    {"id": "nav_current_marked_not_by_color_only",
     "rule": "當前頁除顏色外另有符號（`● ` 前綴 pseudo-element）與原生 radio `checked` 狀態。",
     "source": "Freeze §4.1（顏色不是唯一載體）"},
    {"id": "content_not_covered_by_nav",
     "rule": "捲到頁底後，最後一個內容元素底緣 ≤ 導覽列上緣（手機）／左緣 ≥ 導覽右緣（桌機）。",
     "source": "Wireframes §0.4（導覽不得遮住主要內容）"},
    {"id": "no_title_overlap",
     "rule": "頁面標題不與 Preview banner、第一屏區塊重疊（上下緣依序不交疊）。",
     "source": "客戶 (9) 手機截圖目視項（標題無重疊）轉為可量測條件"},
]


# ── 純函式：由量測 dict 判定（可單獨測試，見 tests/test_ui2_viewport.py） ──────────────
def evaluate(m: dict) -> dict[str, list[str]]:
    """回傳 {check_id: [失敗訊息...]}；空 list＝通過。`m` 為 `measure_state()` 的輸出。"""
    out: dict[str, list[str]] = {t["id"]: [] for t in THRESHOLDS}
    vw, vh = m["viewport"]["w"], m["viewport"]["h"]
    mobile = vw <= MOBILE_MAX_W
    nav = m["nav"]
    limit = (vh - NAV_MOBILE_H) if mobile else vh
    present = {e["q"] for e in m["elements"]}
    for q in FIRST_SCREEN_QS:
        if q not in present:
            out["first_screen_within_usable_height"].append(f"缺第一屏錨點 {q}")
    for e in m["elements"]:
        if e["bottom"] > limit + 0.5:
            out["first_screen_within_usable_height"].append(
                f"{e['q']}（{e['text'][:12]}）底緣 y={e['bottom']:.0f} > 可用高 {limit}")
        if mobile and nav["top"] is not None and e["bottom"] > nav["top"] + 0.5:
            out["first_screen_above_nav"].append(f"{e['q']} 底緣 {e['bottom']:.0f} > 導覽上緣 {nav['top']:.0f}")
        if not mobile and nav["right"] is not None and e["left"] < nav["right"] - 0.5:
            out["first_screen_above_nav"].append(f"{e['q']} 左緣 {e['left']:.0f} < 導覽右緣 {nav['right']:.0f}")
    h = m["hscroll"]
    for k in ("doc", "main"):
        if h[k]["scrollWidth"] > h[k]["clientWidth"] + 0.5:
            out["no_horizontal_scroll"].append(f"{k}: scrollWidth {h[k]['scrollWidth']} > clientWidth {h[k]['clientWidth']}")
    if h["qa_clipped"]:
        out["no_horizontal_scroll"].append("第一屏區塊內容被橫向裁切")
    # 導覽
    labels = nav["labels"]
    if tuple(labels) != NAV_LABELS:
        out["nav_fixed_four"].append(f"導覽項 {labels!r} ≠ 固定四頁 {NAV_LABELS!r}")
    if nav["position"] != "fixed":
        out["nav_fixed_four"].append(f"導覽 position={nav['position']!r}（應為 fixed）")
    if mobile:
        if abs((nav["top"] or -99) - (vh - NAV_MOBILE_H)) > 1 or abs((nav["bottom"] or -99) - vh) > 1:
            out["nav_fixed_four"].append(f"手機導覽應貼底 53px：top={nav['top']} bottom={nav['bottom']}")
        if abs((nav["left"] or 0)) > 1 or abs((nav["right"] or 0) - vw) > 1:
            out["nav_fixed_four"].append("手機導覽未全寬")
        if len({round(t) for t in nav["label_tops"]}) != 1:
            out["nav_fixed_four"].append("手機導覽 4 格未同列")
    else:
        if abs(nav["left"] or 0) > 1:
            out["nav_fixed_four"].append("桌機導覽應在左側（left=0）")
        if len({round(x) for x in nav["label_lefts"]}) != 1 or len({round(t) for t in nav["label_tops"]}) != 4:
            out["nav_fixed_four"].append("桌機導覽 4 項應垂直排列")
    if nav["checked_count"] != 1:
        out["nav_fixed_four"].append(f"當前頁（checked）數量 {nav['checked_count']} ≠ 1")
    marks = nav["marker_contents"]
    if [i for i, c in enumerate(marks) if "●" in c] != [nav["checked_index"]]:
        out["nav_current_marked_not_by_color_only"].append(f"當前頁符號標記與 checked 不一致：{marks!r}")
    # 導覽不遮內容
    last = m["last_content"]
    if mobile and nav["top"] is not None and last["bottom"] > nav["top"] + 0.5:
        out["content_not_covered_by_nav"].append(f"頁底內容 {last['bottom']:.0f} > 導覽上緣 {nav['top']:.0f}")
    if not mobile and nav["right"] is not None and last["left"] < nav["right"] - 0.5:
        out["content_not_covered_by_nav"].append(f"頁底內容左緣 {last['left']:.0f} < 導覽右緣 {nav['right']:.0f}")
    # 標題不重疊
    t = m["title"]
    if t["banner_bottom"] is not None and t["top"] < t["banner_bottom"] - 0.5:
        out["no_title_overlap"].append("標題與 banner 重疊")
    if t["qa_top"] is not None and t["qa_top"] < t["bottom"] - 0.5:
        out["no_title_overlap"].append("標題與第一屏區塊重疊")
    return out


# ── 瀏覽器端量測 ──────────────────────────────────────────────────────────
_JS = r"""
() => {
  const R = e => { const r = e.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,height:r.height,width:r.width}; };
  const main = document.querySelector('[data-testid="stMain"]') || document.documentElement;
  const nav = document.querySelector('.st-key-ui2_nav');
  const nr = nav ? R(nav) : null;
  const labels = nav ? [...nav.querySelectorAll('[role="radiogroup"] > label')] : [];
  const checkedIdx = labels.findIndex(l => l.querySelector('input').checked);
  const elements = [...document.querySelectorAll('[data-ui2-q]')].map(e => ({q: e.dataset.ui2Q, text: e.innerText.replace(/\s+/g,' ').trim(), ...R(e)}));
  const qa = document.querySelector('.ui2-qa');
  const title = document.querySelector('.ui2-pagetitle');
  const banner = document.querySelector('.ui2-banner');
  const sc = el => ({scrollWidth: el.scrollWidth, clientWidth: el.clientWidth});
  // 頁底內容：捲到底後最後一個 ui2 內容元素（Preview 控制 expander）
  const prev = main.scrollTop; main.scrollTo({top: main.scrollHeight, behavior: 'instant'});
  const blocks = [...document.querySelectorAll('.stMainBlockContainer [data-testid="stElementContainer"], .block-container [data-testid="stElementContainer"]')]
    .filter(e => R(e).height > 1 && (!e.checkVisibility || e.checkVisibility()) && (!nav || (!nav.contains(e) && !e.contains(nav))));   // 排除導覽本身與其 0 高的外層包裝
  const lastEl = blocks.length ? blocks[blocks.length-1] : null;
  const last = lastEl ? R(lastEl) : {bottom:0,left:0};
  main.scrollTo({top: prev, behavior: 'instant'});
  return {
    nav: nr && {...nr, position: getComputedStyle(nav).position, labels: labels.map(l => l.innerText.trim()),
      label_tops: labels.map(l => l.getBoundingClientRect().top), label_lefts: labels.map(l => l.getBoundingClientRect().left),
      label_heights: labels.map(l => l.getBoundingClientRect().height),
      checked_count: labels.filter(l => l.querySelector('input').checked).length, checked_index: checkedIdx,
      marker_contents: labels.map(l => { const p = l.querySelector('p'); return p ? getComputedStyle(p, '::before').content : ''; })},
    elements,
    hscroll: {doc: sc(document.documentElement), main: sc(main), qa_clipped: qa ? qa.scrollWidth > qa.clientWidth + 0.5 : false},
    title: {top: title ? R(title).top : null, bottom: title ? R(title).bottom : null,
            banner_bottom: banner ? R(banner).bottom : null, qa_top: qa ? R(qa).top : null},
    last_content: {bottom: last.bottom, left: last.left},
    card_heights: [...document.querySelectorAll('.ui2-card')].slice(0,8).map(e => Math.round(R(e).height)),
  };
}
"""


def measure_state(page, vw: int, vh: int) -> dict:
    page.evaluate("(() => { const m = document.querySelector('[data-testid=\"stMain\"]'); if (m) m.scrollTo({top: 0, behavior: 'instant'}); })()")
    page.wait_for_timeout(150)
    data = page.evaluate(_JS)
    data["viewport"] = {"w": vw, "h": vh}
    return data


# ── 驅動 ──────────────────────────────────────────────────────────────────
def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(repo: Path, python: str = sys.executable) -> tuple[subprocess.Popen, str]:
    port = _free_port()
    proc = subprocess.Popen(
        [python, "-m", "streamlit", "run", "app_ui2.py", "--server.headless", "true",
         "--server.port", str(port), "--browser.gatherUsageStats", "false"],
        cwd=str(repo), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=1)
            return proc, url
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("streamlit server 未在 40 秒內就緒")


def launch_chromium(p):
    """預設 launch；若該 Playwright 版本對應的 build 不在（只裝了別的 revision）→ 退回找現有 headless shell。"""
    try:
        return p.chromium.launch()
    except Exception:
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        cands = sorted(glob.glob(f"{root}/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
        if not cands:
            raise
        return p.chromium.launch(executable_path=cands[-1])


def run_measurements(url: str, out: Path | None, shots: str = "all", server_python: str | None = None,
                     streamlit_version: str | None = None) -> dict:
    from playwright.sync_api import sync_playwright

    from shared.ui2_contract.pages import PAGE4_LABELS, PAGE_IDS, SCENARIO_IDS
    from src.ui2.shell.app import _SCENARIO_LABELS

    results: list[dict] = []
    with sync_playwright() as p:
        browser = launch_chromium(p)
        for vp_name, (vw, vh) in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": vw, "height": vh})
            page.goto(url)
            page.wait_for_selector(".ui2-qa", timeout=40000)
            for scenario in SCENARIO_IDS:
                _select_scenario(page, _SCENARIO_LABELS[scenario], scenario)
                for pid in PAGE_IDS:
                    page.locator(".st-key-ui2_nav [role='radiogroup'] > label", has_text=PAGE4_LABELS[pid]).click()
                    page.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{scenario}"]', timeout=30000)
                    page.wait_for_timeout(250)
                    m = measure_state(page, vw, vh)
                    checks = evaluate(m)
                    rec = {"viewport_name": vp_name, "viewport": m["viewport"], "page": pid, "scenario": scenario,
                           "elements": [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in e.items()}
                                        for e in m["elements"]],
                           "nav": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in m["nav"].items()
                                   if k in ("top", "bottom", "left", "right", "width", "height", "position", "labels", "checked_index")},
                           "hscroll": m["hscroll"], "title": {k: (round(v, 1) if v is not None else None) for k, v in m["title"].items()},
                           "last_content_bottom": round(m["last_content"]["bottom"], 1),
                           "card_heights": m["card_heights"],
                           "failures": {k: v for k, v in checks.items() if v}, "pass": not any(checks.values())}
                    results.append(rec)
                    if out is not None and _want_shot(shots, vp_name, scenario):
                        page.screenshot(path=str(out / f"{vp_name}_{pid}_{scenario}.png"))
            page.close()
        streamlit_version = streamlit_version or _streamlit_version(server_python)
        browser.close()
    summary = {"states": len(results), "passed": sum(r["pass"] for r in results),
               "failed": [f"{r['viewport_name']}/{r['page']}/{r['scenario']}" for r in results if not r["pass"]]}
    return {"meta": {"tool": "tests/ui2_viewport/measure_viewport.py", "streamlit_version": streamlit_version,
                     "viewports": {k: list(v) for k, v in VIEWPORTS.items()}, "nav_mobile_h": NAV_MOBILE_H,
                     "thresholds": THRESHOLDS,
                     "note": "全部場景為 FAKE；量測值未四捨五入的原始 px 於 elements／nav；門檻不自創（見 thresholds.source）。"},
            "summary": summary, "results": results}


def _want_shot(mode: str, vp_name: str, scenario: str) -> bool:
    if mode == "all":
        return True
    if mode == "core":          # 手機全部場景＋桌機 cold／loaded（控制 repo 檔案大小）
        return vp_name == "mobile" or scenario in ("cold", "loaded")
    return False


def _streamlit_version(python: str | None = None) -> str:
    if python is None:
        import streamlit
        return streamlit.__version__
    return subprocess.check_output(
        [python, "-c", "import streamlit;print(streamlit.__version__)"], text=True).strip()


def _select_scenario(page, label: str, scenario: str) -> None:
    """展開『Preview 控制』並選場景（⛔ 動 app 程式；純用 UI 操作）。"""
    exp = page.locator('[data-testid="stExpander"]', has_text="Preview 控制").first
    if exp.locator("details[open]").count() == 0:
        exp.locator("summary").click()
    page.wait_for_function(
        "() => { const e = document.querySelector('[data-testid=\"stSelectbox\"]'); "
        "return e && e.getBoundingClientRect().height > 10; }", timeout=10000)
    page.wait_for_timeout(500)          # 展開動畫
    box = page.get_by_role("combobox", name="場景")
    box.click()
    page.wait_for_timeout(250)
    if box.get_attribute("aria-expanded") != "true":      # Streamlit 1.59（react-aria）click 不一定展開 → 鍵盤展開
        box.press("ArrowDown")
    page.get_by_role("option", name=label, exact=True).click()
    page.wait_for_selector(f'[data-ui2-scenario="{scenario}"]', timeout=30000)
    page.wait_for_timeout(200)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--url", default=None)
    ap.add_argument("--shots", default="core", choices=("all", "core", "none"))
    ap.add_argument("--python", default=None, help="用此 python 起 streamlit server（例：/tmp/v156/bin/python 驗 floor 1.56）")
    ap.add_argument("--streamlit-version", default=None, help="搭配 --url：被量測 server 的 streamlit 版本標示")
    ap.add_argument("--json-name", default="viewport_measurements.json")
    a = ap.parse_args()
    repo = Path(__file__).resolve().parents[2]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    proc = None
    url = a.url
    if url is None:
        proc, url = start_server(repo, a.python or sys.executable)
    try:
        report = run_measurements(url, out, a.shots, a.python if proc is not None else None,
                                  a.streamlit_version if proc is None else None)
    finally:
        if proc is not None:
            proc.kill()
    (out / a.json_name).write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    s = report["summary"]
    print(f"states={s['states']} passed={s['passed']} failed={s['failed']}")
    return 0 if not s["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
