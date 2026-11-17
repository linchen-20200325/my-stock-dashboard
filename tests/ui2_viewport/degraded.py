"""降級畫面（#1204）真瀏覽器量測：附加場景，**不改**既有場景與門檻定義（`measure_viewport.THRESHOLDS`／`evaluate` 原樣套用）。

額外只做一件事：對降級態套用既有常數 `P2_NAV_MARGIN_MIN_PX`（160）於手機 📊 市場頁——既有 `p2_nav_margin_160`
判定只套用在 stale／unavailable 場景，Real 場景（`real`）不在其內，所以降級警示造成的餘裕損失原本不會被任何門檻抓到。
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from tests.ui2_viewport import measure_viewport as MV

LAUNCHER = Path(__file__).with_name("degraded_launcher.py")

_JS = """() => {
  const d = document.querySelector('[data-ui2-degraded]'); if (!d) return null;
  const chip = d.querySelector('.ui2-chip'); const r = d.getBoundingClientRect();
  const rg = document.createRange(); rg.selectNodeContents(chip);
  const tops = new Set([...rg.getClientRects()].map(x => Math.round(x.top)));
  const nav = document.querySelector('.st-key-ui2_nav').getBoundingClientRect();
  return {role: d.getAttribute('role'), top: r.top, h: r.height, text_lines: tops.size, nav_bottom: nav.bottom,
          visible: r.width > 0 && r.height > 0 && r.top < innerHeight, text: d.innerText,
          body_leak: /secret-token|Traceback/.test(document.body.innerText)}
}"""


def start_degraded_server(repo: Path) -> tuple[subprocess.Popen, str]:
    port = MV._free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(LAUNCHER), "--server.headless", "true",
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
    raise RuntimeError("degraded streamlit server 未在 40 秒內就緒")


def run_degraded(url: str) -> list[dict]:
    """五頁 × 兩 viewport：既有判定（`_record`）＋降級警示量測＋手機 📊 的 nav margin。"""
    from playwright.sync_api import sync_playwright

    from shared.ui2_contract.pages import FEED_REAL, PAGE_IDS, PAGE_LABELS, SCENARIO_REAL
    from src.ui2.shell.app import _FEED_LABELS

    rows: list[dict] = []
    with sync_playwright() as p:
        browser = MV.launch_chromium(p)
        for vp_name, (vw, vh) in MV.VIEWPORTS.items():
            page = browser.new_page(viewport={"width": vw, "height": vh})
            page.goto(MV._dev_url(url))
            page.wait_for_selector(".ui2-qa", timeout=40000)
            MV._select_box(page, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
            for pid in PAGE_IDS:
                MV.click_nav(page, PAGE_LABELS[pid])
                page.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
                page.wait_for_timeout(300)
                page.evaluate("(() => { const m = document.querySelector('[data-testid=\"stMain\"]'); if (m) m.scrollTo({top: 0}); })()")
                page.wait_for_timeout(150)
                alert = page.evaluate(_JS)
                rec = MV._record(page, vp_name, vw, vh, pid, SCENARIO_REAL, feed="real")
                rows.append({"viewport_name": vp_name, "vw": vw, "page": pid, "alert": alert, "record": rec,
                             "nav_margin": rec["batch3"]["nav_margin_after_risk"]})
            page.close()
        browser.close()
    return rows
