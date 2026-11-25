"""📊 頁尾「接入狀態」真 app 證據截圖＋量測產生器（只讀；非驗收測試）。

用途
    重現 `docs/vnext/newui2_wired_status/` 內的證據截圖與量測 JSON：對每個 Real 組態各起一個真 `app_ui2.py`（經
    `wired_status_launcher.py` 覆寫 snapshot 欄位；畫面由真 shell／VM／view 產生），用 Chromium 量 📊 頁尾的「接入狀態」區塊
    （位置／高度／各列折行／截斷／重疊／水平溢出／DOM 順序／標題出現次數）並截圖（捲到頁尾的視窗圖；390 另截整頁）。
    輸出為「證據截圖與量測」，**不是**驗收通過聲明。檔名不以 `test_` 開頭，不會被 pytest 收集；
    不在 `measure_viewport.source_files()` 內，不影響 DEC-137 JSON 的 `source_hash`。

重現指令（於 repo 根目錄；venv＝Streamlit＋playwright＋Chromium＋Pillow）
    PYTHONDONTWRITEBYTECODE=1 <venv>/bin/python -m tests.ui2_viewport.wired_status_shots \\
        --python <venv>/bin/python --tag st159 --out <dir> --json <file>
    # 對 base（沒有該區塊的對照，只量不拍）：
    ... --repo <base checkout> --no-shots --tag base_st159 --json <file>
    # 只跑部分組態／視窗：--cases live,loaded --viewports 390,1280

組態（`wired_status_launcher.CASES`）：live（真 Real 現況）／loaded／stale／missing／no_new_data／undetermined（畫）；
unavailable／fetch_failed／legacy_upstream_error／degraded（不畫）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tests.ui2_viewport import measure_viewport as MV  # noqa: E402
from shared.ui2_contract.pages import P4_MARKET, PAGE_LABELS, SCENARIO_REAL  # noqa: E402

LAUNCHER = Path(__file__).with_name("wired_status_launcher.py")
ALL_CASES = ("live", "loaded", "stale", "missing", "no_new_data", "undetermined",
             "unavailable", "fetch_failed", "legacy_upstream_error", "degraded")
VIEWPORTS = {"390": (390, 844), "1280": (1280, 900), "1440": (1440, 900)}
TITLE = "接入狀態"

JS = """(title) => {
  const doc = document.documentElement;
  const main = document.querySelector('[data-testid="stMain"]');
  const mt = main ? main.getBoundingClientRect().top : 0, ms = main ? main.scrollTop : 0;
  const R = e => { const q = e.getBoundingClientRect();
    return {top: q.top + ms - mt, bottom: q.bottom + ms - mt, left: q.left, right: q.right, height: q.height, width: q.width}; };
  const lines = e => { const rg = document.createRange(); rg.selectNodeContents(e);
    return new Set([...rg.getClientRects()].filter(x => x.width > 0).map(x => Math.round(x.top))).size; };
  const clippedIn = root => [...root.querySelectorAll('*'), root].some(e =>
      e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible');
  const titles = [...document.querySelectorAll('.ui2-section-title')];
  const t = titles.find(e => e.innerText.trim() === title) || null;
  const anchors = {primary_or_kbar: '.ui2-primary-slot, .ui2-kbar__plot, .ui2-kbar', delta: '[data-ui2-delta]',
                   grid: '.ui2-grid', onebrain: '.ui2-m-onebrain'};
  const pos = {};
  for (const [k, sel] of Object.entries(anchors)) { const e = document.querySelector(sel); pos[k] = e ? R(e).top : null; }
  if (t) pos.wired_status = R(t).top;
  const order = Object.entries(pos).filter(([, v]) => v !== null).sort((a, b) => a[1] - b[1]).map(([k]) => k);
  const out = {
    page_marker: document.querySelector('[data-ui2-page]') ? document.querySelector('[data-ui2-page]').getAttribute('data-ui2-page') : null,
    hscroll: doc.scrollWidth > doc.clientWidth + 1 || (main && main.scrollWidth > main.clientWidth + 1),
    doc_sw: doc.scrollWidth, doc_cw: doc.clientWidth, vw: innerWidth, vh: innerHeight,
    main_scroll_height: main ? main.scrollHeight : null, main_client_height: main ? main.clientHeight : null,
    title_count_in_body: (document.body.innerText.match(new RegExp(title, 'g')) || []).length,
    order, onebrain_bottom: document.querySelector('.ui2-m-onebrain') ? R(document.querySelector('.ui2-m-onebrain')).bottom : null,
    degraded_notice: !!document.querySelector('[data-ui2-degraded]'),
    expanders: document.querySelectorAll('[data-testid="stExpander"]').length,
    block: null,
  };
  if (t) {
    const box = t.parentElement;
    const rows = [...box.querySelectorAll('.ui2-row')];
    const rs = rows.map(R);
    const overlap = (() => { for (let i = 0; i < rs.length; i++) for (let j = i + 1; j < rs.length; j++) {
      const w = Math.min(rs[i].right, rs[j].right) - Math.max(rs[i].left, rs[j].left);
      const h = Math.min(rs[i].bottom, rs[j].bottom) - Math.max(rs[i].top, rs[j].top); if (w > 1 && h > 1) return true; } return false; })();
    out.block = {
      box: R(box), title_box: R(t), title_lines: lines(t), n_rows: rows.length,
      children: [...box.children].map(c => c.className.split(' ')[0] || c.tagName.toLowerCase()),
      rows: rows.map((r, i) => { const lab = r.querySelector('.ui2-row__label'), val = r.querySelector('.ui2-row__value'),
          det = r.querySelector('.ui2-row__detail'), chip = r.querySelector('.ui2-chip');
        return {box: rs[i], label: lab ? lab.innerText.trim() : null, label_lines: lab ? lines(lab) : 0,
                value: val ? val.innerText.trim() : null, value_lines: val ? lines(val) : 0,
                detail: det ? det.innerText.trim() : null, detail_lines: det ? lines(det) : 0, has_chip: !!chip,
                clipped: clippedIn(r), overflow_right: r.getBoundingClientRect().right > innerWidth + 0.5}; }),
      clipped: clippedIn(box), overlap, overflow_right: R(box).right > innerWidth + 0.5,
      gap_below_block_to_scroll_end: main ? main.scrollHeight - R(box).bottom : null,
    };
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


def _start(repo: Path, python: str, case: str) -> tuple[subprocess.Popen, str]:
    port = MV._free_port()
    env = {**os.environ, "UI2_WIRED_CASE": case, "UI2_REPO_ROOT": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen(
        [python, "-m", "streamlit", "run", str(LAUNCHER), "--server.headless", "true", "--server.port", str(port),
         "--browser.gatherUsageStats", "false"],
        cwd=str(repo), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=1)
            return proc, url
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError(f"streamlit server（case={case}）未在 50 秒內就緒")


def _scroll_end(pg) -> None:
    pg.evaluate("(() => { const m = document.querySelector('[data-testid=\"stMain\"]'); if (m) m.scrollTo({top: m.scrollHeight, behavior: 'instant'}); })()")
    pg.wait_for_timeout(500)


def run(repo: Path, python: str, tag: str, cases, vks, out_dir: Path | None, full_vks=("390",)) -> list[dict]:
    from playwright.sync_api import sync_playwright

    rows: list[dict] = []
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
    for case in cases:
        proc, url = _start(repo, python, case)
        try:
            with sync_playwright() as p:
                b = MV.launch_chromium(p)
                for vk in vks:
                    vw, vh = VIEWPORTS[vk]
                    pg = b.new_page(viewport={"width": vw, "height": vh})
                    pg.goto(url)
                    pg.wait_for_selector(".ui2-qa", timeout=40000)
                    MV.click_nav(pg, PAGE_LABELS[P4_MARKET])
                    pg.wait_for_selector(f'[data-ui2-page="{P4_MARKET}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
                    pg.wait_for_timeout(700)
                    _scroll_end(pg)
                    m = _r1(pg.evaluate(JS, TITLE))
                    rec = {"tag": tag, "case": case, "viewport": f"{vw}x{vh}", **m}
                    if out_dir is not None:
                        png = out_dir / f"{tag}_{case}_{vk}_tail.png"
                        MV._screenshot(pg, png)
                        rec["png_tail_bytes"] = _shrink(png)
                        if vk in full_vks:
                            h = pg.evaluate("() => document.querySelector('[data-testid=\"stMain\"]').scrollHeight")
                            pg.evaluate("(() => { const m = document.querySelector('[data-testid=\"stMain\"]'); m.scrollTo({top: 0, behavior: 'instant'}); })()")
                            pg.set_viewport_size({"width": vw, "height": int(min(max(h, vh), 3000))})
                            pg.wait_for_timeout(600)
                            full = out_dir / f"{tag}_{case}_{vk}_full.png"
                            MV._screenshot(pg, full)
                            rec["png_full_bytes"] = _shrink(full)
                            rec["full_height_px"] = int(min(max(h, vh), 3000))
                    rows.append(rec)
                    pg.close()
                b.close()
        finally:
            proc.kill()
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="📊 接入狀態 證據截圖＋量測（非驗收測試）")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--repo", type=Path, default=REPO, help="要啟動的 checkout 根（base 對照用）")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--json", required=True, type=Path, dest="json_path")
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--cases", default=",".join(ALL_CASES))
    ap.add_argument("--viewports", default="390,1280,1440")
    ap.add_argument("--full", default="390", help="逗號分隔：哪些寬度另截整頁（預設只 390）；空字串＝不截")
    a = ap.parse_args(argv)
    cases = [c for c in a.cases.split(",") if c]
    vks = [v for v in a.viewports.split(",") if v]
    full = tuple(v for v in a.full.split(",") if v)
    out = None if a.no_shots else a.out.resolve()
    a.json_path.parent.mkdir(parents=True, exist_ok=True)
    rows = run(a.repo.resolve(), a.python, a.tag, cases, vks, out, full)
    a.json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        b = r["block"]
        print(r["tag"], r["case"], r["viewport"], "block" if b else "no-block", "title_count", r["title_count_in_body"],
              "h", (b or {}).get("box", {}).get("height"), "order", r["order"], "hscroll", r["hscroll"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
