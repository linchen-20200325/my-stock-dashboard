"""P-1「🎯／💼 detail 對齊 📊」真 app 證據截圖＋量測產生器（只讀；非驗收測試）。

用途
    重現 `docs/vnext/newui2_p1_detail/` 內的證據截圖與 `p1_detail_measurements.json`：
    啟動真 `app_ui2.py`（Streamlit）＋ Chromium，量 🎯 context 行（`.ui2-ctxline`）與 💼 今日需處理列
    （`.ui2-qa [data-ui2-q="q2"]`）的位置／高度／各子元素 DOM 順序／水平溢出／截斷／重疊，並截圖。
    輸出為「證據截圖與量測」，**不是**驗收通過聲明（不代表 QA／Design Gate／CI PASS）。
    檔名不以 `test_` 開頭，不會被 pytest 收集；不在 `measure_viewport.source_files()` 內，
    因此不影響 DEC-137 JSON 的 `source_hash`。

重現指令（於 repo 根目錄執行）
    <venv>/bin/python -m tests.ui2_viewport.p1_detail_shots --out <dir> --json <file> [--repo <另一個 checkout 根>] [--no-shots]
    --repo：用另一個 checkout（例如 origin/main 的 worktree）的 `app_ui2.py` 起 server 量測，供 base／分支前後對照；
            量測／截圖邏輯一律用本檔，所以兩邊用同一把尺。

場景（× 寬度 390×844／1280×900／1440×900；× 頁 🎯 標的／💼 持股）
    fake_ok（FAKE `loaded`）／fake_stale／fake_unavailable／real（Real-data Preview）／real_degraded（Real 讀取整體失敗的降級 launcher）。
輸出
    PNG：`<場景>_<頁>_<寬>.png`（捲到頂端的視窗截圖；128 色量化後 ≤ 70KB）。
    JSON：每 shot 一筆 `{shot, viewport, page, ctxline|action_row, anchors, hscroll, ...}`，數值四捨五入到小數 1 位。
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
    FEED_FAKE, FEED_REAL, P4_HOLD, P4_TARGET, PAGE_LABELS, SCENARIO_REAL,
)
from src.ui2.shell.app import _FEED_LABELS, _SCENARIO_LABELS  # noqa: E402

PAGES = ((P4_TARGET, "target"), (P4_HOLD, "hold"))
VIEWPORTS = (("390", (390, 844)), ("1280", (1280, 900)), ("1440", (1440, 900)))
FAKE_SCENARIOS = (("fake_ok", "loaded"), ("fake_stale", "stale"), ("fake_unavailable", "unavailable"))

JS = """() => {
  const doc = document.documentElement;
  const main = document.querySelector('[data-testid="stMain"]');
  const R = e => { const q = e.getBoundingClientRect();
    return {top: q.top, bottom: q.bottom, left: q.left, right: q.right, height: q.height, width: q.width}; };
  const clippedIn = root => [...root.querySelectorAll('*'), root].some(e =>
      e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible');
  const overlap = rs => { for (let i = 0; i < rs.length; i++) for (let j = i + 1; j < rs.length; j++) {
      const a = rs[i], b = rs[j];
      const w = Math.min(a.right, b.right) - Math.max(a.left, b.left), h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (w > 1 && h > 1) return true; } return false; };
  const qa = document.querySelector('.ui2-qa');
  const out = {
    hscroll: doc.scrollWidth > doc.clientWidth + 1 || (main && main.scrollWidth > main.clientWidth + 1),
    doc_sw: doc.scrollWidth, doc_cw: doc.clientWidth, vw: innerWidth, vh: innerHeight,
    anchors: qa ? [...qa.querySelectorAll('[data-ui2-q]')].map(e => e.getAttribute('data-ui2-q')) : [],
    qa: qa ? R(qa) : null, ctxline: null, action_row: null,
  };
  const ctx = document.querySelector('.ui2-ctxline');
  if (ctx) {
    const items = [...ctx.children];
    const rs = items.map(R);
    out.ctxline = {box: R(ctx), text: ctx.innerText.replace(/\\s+/g, ' ').trim(), n_items: items.length,
      item_children: items.map(it => [...it.children].map(c => c.className.split(' ')[0] || c.tagName.toLowerCase())),
      items: items.map((it, i) => { const d = it.querySelector('.ui2-row__detail');
        return {box: rs[i], detail_text: d ? d.innerText.trim() : null, detail_box: d ? R(d) : null}; }),
      clipped: clippedIn(ctx), overlap: overlap(rs),
      overflow_right: rs.some(r => r.right > innerWidth + 0.5) };
  }
  const q2 = document.querySelector('.ui2-qa [data-ui2-q="q2"]');
  if (q2 && document.querySelector('.ui2-h-l1')) {
    const d = q2.querySelector('.ui2-row__detail');
    const kids = [...q2.children];
    out.action_row = {box: R(q2), text: q2.innerText.replace(/\\s+/g, ' ').trim(),
      children: kids.map(c => c.className.split(' ')[0] || c.tagName.toLowerCase()),
      detail_text: d ? d.innerText.trim() : null, detail_box: d ? R(d) : null,
      clipped: clippedIn(q2), overlap: overlap(kids.map(R)), overflow_right: R(q2).right > innerWidth + 0.5 };
    const l1 = document.querySelector('.ui2-h-l1'); out.hold_l1 = R(l1);
  }
  return out;
}"""


def _shrink(path: Path) -> int:
    from PIL import Image
    im = Image.open(path).convert("RGB")
    for colors in (128, 96, 64, 32):
        q = im.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        q.save(path, optimize=True)
        if path.stat().st_size <= 70 * 1024:
            break
    return path.stat().st_size


def _r1(o):
    if isinstance(o, float):
        return round(o, 1)
    if isinstance(o, dict):
        return {k: _r1(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_r1(v) for v in o]
    return o


def _snap(pg, out_dir: Path | None, tag: str, page_name: str, vk: str, vw: int, vh: int, rows: list[dict]) -> None:
    pg.evaluate("(() => { const m = document.querySelector('[data-testid=\"stMain\"]'); if (m) m.scrollTo({top: 0, behavior: 'instant'}); })()")
    pg.wait_for_timeout(400)
    m = _r1(pg.evaluate(JS))
    rec = {"shot": f"{tag}_{page_name}", "viewport": f"{vw}x{vh}", "page": page_name, **m}
    if out_dir is not None:
        png = out_dir / f"{tag}_{page_name}_{vk}.png"
        MV._screenshot(pg, png)
        rec["png_bytes"] = _shrink(png)
    rows.append(rec)


def run(out_dir: Path | None, json_path: Path, repo: Path) -> list[dict]:
    from playwright.sync_api import sync_playwright

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    p1, u1 = MV.start_server(repo, sys.executable)
    try:
        with sync_playwright() as p:
            b = MV.launch_chromium(p)
            for vk, (vw, vh) in VIEWPORTS:
                pg = b.new_page(viewport={"width": vw, "height": vh})
                pg.goto(MV._dev_url(u1)); pg.wait_for_selector(".ui2-qa", timeout=40000)
                MV._select_box(pg, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
                for pid, name in PAGES:
                    MV.click_nav(pg, PAGE_LABELS[pid])
                    pg.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
                    pg.wait_for_timeout(500)
                    _snap(pg, out_dir, "real", name, vk, vw, vh, rows)
                MV._select_box(pg, "資料來源", _FEED_LABELS[FEED_FAKE], '[data-ui2-scenario="cold"]')
                for tag, sc in FAKE_SCENARIOS:
                    MV._select_box(pg, "場景", _SCENARIO_LABELS[sc], f'[data-ui2-scenario="{sc}"]')
                    for pid, name in PAGES:
                        MV.click_nav(pg, PAGE_LABELS[pid])
                        pg.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{sc}"]', timeout=30000)
                        pg.wait_for_timeout(400)
                        _snap(pg, out_dir, tag, name, vk, vw, vh, rows)
                pg.close()
            b.close()
    finally:
        p1.kill()

    DG.LAUNCHER = repo / "tests" / "ui2_viewport" / "degraded_launcher.py"   # base 對照：用該 checkout 自己的降級 launcher
    p2, u2 = DG.start_degraded_server(repo)
    try:
        with sync_playwright() as p:
            b = MV.launch_chromium(p)
            for vk, (vw, vh) in VIEWPORTS:
                pg = b.new_page(viewport={"width": vw, "height": vh})
                pg.goto(MV._dev_url(u2)); pg.wait_for_selector(".ui2-qa", timeout=40000)
                MV._select_box(pg, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
                for pid, name in PAGES:
                    MV.click_nav(pg, PAGE_LABELS[pid])
                    pg.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
                    pg.wait_for_timeout(400)
                    _snap(pg, out_dir, "real_degraded", name, vk, vw, vh, rows)
                pg.close()
            b.close()
    finally:
        p2.kill()
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P-1 🎯／💼 detail 對齊 證據截圖＋量測（非驗收測試）")
    ap.add_argument("--out", type=Path, default=None, help="PNG 輸出目錄（省略＝不截圖，只量測）")
    ap.add_argument("--json", required=True, type=Path, dest="json_path", help="量測 JSON 輸出檔")
    ap.add_argument("--repo", type=Path, default=REPO, help="用此 checkout 的 app_ui2.py 起 server（base 對照用；預設＝本 repo）")
    a = ap.parse_args(argv)
    os.chdir(a.repo)
    rows = run(a.out.resolve() if a.out else None, a.json_path.resolve(), a.repo.resolve())
    for r in rows:
        c, ar = r.get("ctxline"), r.get("action_row")
        print(r["shot"], r["viewport"], "anchors", r["anchors"],
              "ctx_h", c and c["box"]["height"], "act_h", ar and ar["box"]["height"], "hscroll", r["hscroll"],
              "ctx(clip/ovl/ovr)", c and (c["clipped"], c["overlap"], c["overflow_right"]),
              "act(clip/ovl/ovr)", ar and (ar["clipped"], ar["overlap"], ar["overflow_right"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
