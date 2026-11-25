"""Delta Strip BELOW 真 app 證據截圖＋量測產生器（只讀；非驗收測試）。

用途
    重現 `docs/vnext/newui2_delta_below/` 內的證據截圖與 `delta_measurements.json`：
    啟動真 `app_ui2.py`（Streamlit）＋ Chromium，量 Delta 列（`[data-ui2-delta]`）的位置／高度／是否單行／
    是否截斷、主 CTA 可達（390）、頁面水平溢出，並截圖。
    輸出為「證據截圖與量測」，**不是**驗收通過聲明（不代表 QA／Design Gate／CI PASS）。
    檔名不以 `test_` 開頭，不會被 pytest 收集；不在 `measure_viewport.source_files()` 內，
    因此不影響 DEC-137 JSON 的 `source_hash`。

重現指令（於 repo 根目錄執行；輸出目錄由參數指定，不寫入 repo 任何既有路徑）
    <venv>/bin/python -m tests.ui2_viewport.delta_shots --out <dir> --json <file>
    例：PYTHONDONTWRITEBYTECODE=1 $S/v159/bin/python -m tests.ui2_viewport.delta_shots \\
            --out $S/qa_repro/shots --json $S/qa_repro/meas.json

環境
    Streamlit 1.59.2、playwright 1.64.1、Chromium（`MV.launch_chromium` 找不到預設 build 時退回現有 headless shell）、
    Pillow（PNG 量化）。viewport deviceScaleFactor=1。

輸出
    PNG：`<場景>_<頁>_<視窗寬>_<view|full>.png`
        場景：`real`（Real-data Preview；390×844／1280×900／1440×900）、`fake_stale`／`fake_unavailable`
              （FAKE 場景，390×844）、`real_degraded`（Real 讀取整體失敗，既有降級 launcher，390×844）；
        頁：`market`＝📊 市場、`hold`＝💼 持股；
        `view`＝捲到頂端的視窗截圖，`full`＝暫時把視窗高度放大到內容高度（≤3000px）的整頁截圖。
        PNG 量化為 128 色以壓小檔案。共 12 shot × view／full ＝ 24 張。
    JSON：12 筆 `{shot, viewport, delta, page_horizontal_scroll, cta, png_bytes}`，
        數值四捨五入至小數 1 位；與 `docs/vnext/newui2_delta_below/delta_measurements.json` 同結構。

本檔只重用 `measure_viewport.py` 與 `degraded.py`／`degraded_launcher.py` 的既有 helper，不修改它們；
不 import `src.ui`／`app`。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tests.ui2_viewport import degraded as DG  # noqa: E402
from tests.ui2_viewport import measure_viewport as MV  # noqa: E402
from shared.ui2_contract.pages import (  # noqa: E402
    FEED_FAKE, FEED_REAL, P4_HOLD, P4_MARKET, PAGE_LABELS, SCENARIO_COLD, SCENARIO_REAL,
)
from src.ui2.shell.app import _FEED_LABELS, _SCENARIO_LABELS  # noqa: E402

PAGES = ((P4_MARKET, "market"), (P4_HOLD, "hold"))
REAL_VIEWPORTS = (("390", (390, 844)), ("1280", (1280, 900)), ("1440", (1440, 900)))
MOBILE = (390, 844)

JS = """() => {
  const d = document.querySelector('[data-ui2-delta]');
  const doc = document.documentElement;
  const main = document.querySelector('[data-testid="stMain"]');
  const nav = document.querySelector('.st-key-ui2_nav').getBoundingClientRect();
  const out = {delta: null, hscroll: doc.scrollWidth > doc.clientWidth + 1 || (main && main.scrollWidth > main.clientWidth + 1),
               doc_sw: doc.scrollWidth, doc_cw: doc.clientWidth, vh: innerHeight, vw: innerWidth, nav_bottom: nav.bottom};
  if (d) {
    const r = d.getBoundingClientRect();
    const rg = document.createRange(); rg.selectNodeContents(d);
    const tops = new Set([...rg.getClientRects()].filter(x => x.width > 0).map(x => Math.round(x.top)));
    const kids = [...d.children].map(c => { const q = c.getBoundingClientRect(); return {cls: c.className, text: c.innerText, left: q.left, right: q.right, top: q.top, bottom: q.bottom}; });
    const clipped = [...d.querySelectorAll('*'), d].some(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible');
    out.delta = {top: r.top, bottom: r.bottom, height: r.height, left: r.left, right: r.right, width: r.width, lines: tops.size,
                 text: d.innerText.replace(/\\s+/g, ' ').trim(), clipped, kids,
                 in_first_viewport: r.top >= 0 && r.bottom <= innerHeight,
                 overflow_right: r.right > innerWidth + 0.5};
  }
  const cta = document.querySelector('.ui2-cta');
  if (cta) {
    const q = cta.getBoundingClientRect(); const cx = q.left + q.width / 2, cy = q.top + q.height / 2;
    const hit = document.elementFromPoint(cx, cy);
    out.cta = {top: q.top, bottom: q.bottom, left: q.left, right: q.right, text: cta.innerText,
               in_view: q.top >= nav.bottom - 0.5 && q.bottom <= innerHeight, hit_is_cta: !!hit && (hit === cta || cta.contains(hit))};
  }
  return out;
}"""


def _shrink(path: Path) -> int:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    q = im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q.save(path, optimize=True)
    return path.stat().st_size


def _r1(v):
    return round(v, 1) if isinstance(v, float) else v


def _single_line(kids: list[dict]) -> bool:
    """Delta 列所有子元素垂直區間有共同交集 ＝ 同一水平列（未換行）。"""
    if not kids:
        return False
    return max(k["top"] for k in kids) < min(k["bottom"] for k in kids)


def _normalize(m: dict, tag: str, vw: int, vh: int, sizes: dict) -> dict:
    d = m["delta"]
    delta = None
    if d is not None:
        delta = {k: _r1(d[k]) for k in ("top", "bottom", "height", "left", "right", "width")}
        delta.update({
            "text": d["text"], "clipped": d["clipped"], "in_first_viewport": d["in_first_viewport"],
            "overflow_right": d["overflow_right"], "single_line": _single_line(d["kids"]),
        })
    cta = m.get("cta")
    if cta is not None:
        cta = {k: (_r1(v) if isinstance(v, float) else v) for k, v in cta.items()}
    return {"shot": tag, "viewport": f"{vw}x{vh}", "delta": delta,
            "page_horizontal_scroll": bool(m["hscroll"]), "cta": cta, "png_bytes": sizes}


def _snap(pg, out_dir: Path, tag: str, vk: str, vw: int, vh: int, rows: list[dict]) -> None:
    pg.evaluate("(() => { const m = document.querySelector('[data-testid=\"stMain\"]'); if (m) m.scrollTo({top: 0, behavior: 'instant'}); })()")
    pg.wait_for_timeout(400)
    m = pg.evaluate(JS)
    base = out_dir / f"{tag}_{vk}"
    view = Path(str(base) + "_view.png")
    MV._screenshot(pg, view)
    sizes = {"view": _shrink(view)}
    # Streamlit 捲動容器是 stMain，page.screenshot(full_page) 只截視窗；暫時放大視窗高度到內容高度
    h = pg.evaluate("() => { const m = document.querySelector('[data-testid=\"stMain\"]'); return m ? m.scrollHeight : document.documentElement.scrollHeight; }")
    pg.set_viewport_size({"width": vw, "height": int(min(max(h, vh), 3000))})
    pg.wait_for_timeout(500)
    full = Path(str(base) + "_full.png")
    MV._screenshot(pg, full)
    sizes["full"] = _shrink(full)
    pg.set_viewport_size({"width": vw, "height": vh})
    pg.wait_for_timeout(300)
    rows.append(_normalize(m, tag, vw, vh, sizes))


def run(out_dir: Path, json_path: Path) -> list[dict]:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    p1, u1 = MV.start_server(REPO, sys.executable)
    try:
        with sync_playwright() as p:
            b = MV.launch_chromium(p)
            for vk, (vw, vh) in REAL_VIEWPORTS:
                pg = b.new_page(viewport={"width": vw, "height": vh})
                pg.goto(MV._dev_url(u1)); pg.wait_for_selector(".ui2-qa", timeout=40000)
                MV._select_box(pg, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
                for pid, name in PAGES:
                    MV.click_nav(pg, PAGE_LABELS[pid])
                    pg.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
                    pg.wait_for_timeout(500)
                    _snap(pg, out_dir, f"real_{name}", vk, vw, vh, rows)
                pg.close()
            vw, vh = MOBILE
            pg = b.new_page(viewport={"width": vw, "height": vh})
            pg.goto(MV._dev_url(u1)); pg.wait_for_selector(".ui2-qa", timeout=40000)
            MV._select_box(pg, "資料來源", _FEED_LABELS[FEED_FAKE], f'[data-ui2-scenario="{SCENARIO_COLD}"]')
            for sc in ("stale", "unavailable"):
                MV._select_box(pg, "場景", _SCENARIO_LABELS[sc], f'[data-ui2-scenario="{sc}"]')
                for pid, name in PAGES:
                    MV.click_nav(pg, PAGE_LABELS[pid])
                    pg.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{sc}"]', timeout=30000)
                    pg.wait_for_timeout(400)
                    _snap(pg, out_dir, f"fake_{sc}_{name}", "390", vw, vh, rows)
            pg.close(); b.close()
    finally:
        p1.kill()

    p2, u2 = DG.start_degraded_server(REPO)
    try:
        with sync_playwright() as p:
            b = MV.launch_chromium(p)
            vw, vh = MOBILE
            pg = b.new_page(viewport={"width": vw, "height": vh})
            pg.goto(MV._dev_url(u2)); pg.wait_for_selector(".ui2-qa", timeout=40000)
            MV._select_box(pg, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
            for pid, name in PAGES:
                MV.click_nav(pg, PAGE_LABELS[pid])
                pg.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
                pg.wait_for_timeout(400)
                _snap(pg, out_dir, f"real_degraded_{name}", "390", vw, vh, rows)
            pg.close(); b.close()
    finally:
        p2.kill()

    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Delta Strip BELOW 證據截圖＋量測（非驗收測試）")
    ap.add_argument("--out", required=True, type=Path, help="PNG 輸出目錄（不預設、不得指向 docs/ 既有證據目錄以外的 repo 路徑）")
    ap.add_argument("--json", required=True, type=Path, dest="json_path", help="量測 JSON 輸出檔")
    a = ap.parse_args(argv)
    os.chdir(REPO)
    rows = run(a.out.resolve(), a.json_path.resolve())
    for r in rows:
        d = r["delta"]
        print(r["shot"], r["viewport"],
              None if d is None else {k: d[k] for k in ("top", "height", "single_line", "clipped", "in_first_viewport", "overflow_right")},
              "hscroll", r["page_horizontal_scroll"], "cta_in_view", (r["cta"] or {}).get("in_view"), r["png_bytes"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
