"""OneBrain 持股槽「四主題」FAKE 預覽的真瀏覽器操作證據 runner（C-OB-TOPICS-DEMO；延續 #1268；**tests-only**）。

⛔ 這**不是** DEC-137 正式證據：meta 標 `label="tests-only／非 DEC-137 正式"`；本 runner **不進 CI**（原生 CI 覆蓋 NOT VERIFIED，只有本地封網驗證）。

用法（repo 根；需 Playwright＋Chromium）::

    python -m tests.ui2_viewport.onebrain_topics_evidence --out /tmp/obtopics_evidence [--cases R1,L2,FAILCLOSED] [--python /path/to/venv/bin/python]

流程：每個案例起一個以 `onebrain_hold_demo_launcher.py` 為入口的 server（四主題為預設），三個視窗各自開一個 context：
`?ui2_dev=1` → 資料來源切 FAKE → 點 💼 持股 → **依序點選四主題**，每個主題截圖（整個視窗／槽／控制群組）並量測。
另在同一個 server 切到 Real 做負控（沒有選擇器、沒有示範字樣）。視窗＝{390×844, 1280×900, 1440×900}（本檔自訂，不重用 `measure_viewport.VIEWPORTS`）。

⚠️ 截圖的開發面：`MV._screenshot` 預設暫時隱藏開發面（`.st-key-ui2_dev_surface`）；「🧪 FAKE 預覽控制」群組不在開發面內，所以會入鏡。
輸出只寫到 `--out`（預設在系統暫存；⛔ 預設不在 repo 內）。判定器 `evaluate_topic()` 是**純函式**（吃量測 dict），不碰瀏覽器。
SF1 量測（首列底部 px、列數、視覺列數）沿用 `onebrain_hold_demo_evidence.fold_report()`／`row_layout()`，與原單一槽用**同一量測法**，才可前後對照。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path

from tests import onebrain_holdings_ui2_demo_topics as T
from tests.ui2_viewport import measure_viewport as MV
from tests.ui2_viewport import onebrain_hold_demo_evidence as EV

LABEL = EV.LABEL
TOOL = "tests/ui2_viewport/onebrain_topics_evidence.py"
VIEWPORTS = EV.VIEWPORTS
FAILCLOSED = EV.FAILCLOSED
CASE_KEYS = ("R1", "L2", FAILCLOSED)
TOPIC_SLUG = {T.TOPIC_MARKET: "1market", T.TOPIC_INDUSTRY: "2industry", T.TOPIC_HOLDINGS: "3holdings", T.TOPIC_RISK: "4risk"}
FILES = ("tests/onebrain_holdings_ui2_demo_topics.py", "tests/ui2_viewport/onebrain_hold_demo_launcher.py",
         "tests/ui2_viewport/onebrain_topics_evidence.py", "tests/test_onebrain_topics_ui2_demo.py")
NEVER = ("顯示＝規則式摘要", "FakeProvider", "§C", "示範鏈", "與本頁其他 FAKE 數字無關", "is_complete")
MARKET_WORDS = ("bull", "🟢", "72.5", "市場位階", "市場燈號", "市場健康度")
CHECKS = ("topic_title", "disclosure_first", "rows_match_vm", "no_expander", "ctrl_present_with_fake_marker", "ctrl_outside_slot",
          "no_horizontal_overflow", "no_forbidden_text", "d7_marker_in_slot")

_JS_EXTRA = r"""
() => {
  const ctrl = document.querySelector('.st-key-ui2_obdemo_ctrl');
  const slot = document.querySelector('[data-ui2-l1="onebrain"]');
  const R = e => { const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height}; };
  return {details: document.querySelectorAll('details, [data-testid="stExpander"]').length,
          ctrl: ctrl ? {...R(ctrl), text: ctrl.innerText.replace(/\s+/g, ' ').trim(), radios: ctrl.querySelectorAll('input[type=radio]').length,
                        inside_slot: !!ctrl.closest('[data-ui2-l1="onebrain"]'), position: getComputedStyle(ctrl).position,
                        checked: (ctrl.querySelector('input[type=radio]:checked') ? ctrl.querySelector('input[type=radio]:checked').closest('label').innerText.trim() : null)} : null,
          title: slot && slot.querySelector('.ui2-section-title') ? slot.querySelector('.ui2-section-title').innerText.trim() : null,
          vh: innerHeight, vw: innerWidth};
}
"""


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def expected_labels(topic: str, case: str, failclosed: bool) -> list[str]:
    return [f.label for f in T.build_topic_section(topic, case, fail_closed=failclosed).fields]


def evaluate_topic(m: dict, topic: str, case: str, failclosed: bool) -> dict[str, list[str]]:
    """量測（`_JS_DEMO`＋`_JS_EXTRA` 合併後的 dict）→ {檢查名: [失敗描述…]}（空＝通過）。"""
    out: dict[str, list[str]] = {k: [] for k in CHECKS}
    rows = m.get("rows") or []
    title = (m.get("title") or {}).get("text") if isinstance(m.get("title"), dict) else m.get("extra_title")
    if not title or not title.endswith(topic):
        out["topic_title"].append(f"槽標題 {title!r} 不是主題 {topic}")
    if not rows or rows[0]["label"] != "示意" or rows[0]["value"] != EV.DISCLOSURE_ROW:
        out["disclosure_first"].append("槽內第一列不是逐字的「示意」揭露")
    want = expected_labels(topic, case, failclosed)
    if [r["label"] for r in rows] != want:
        out["rows_match_vm"].append(f"列序 {[r['label'] for r in rows]} ≠ VM {want}")
    if m["extra"]["details"] != 0:
        out["no_expander"].append(f"details／expander 數 {m['extra']['details']}")
    ctrl = m["extra"]["ctrl"]
    if not ctrl or ctrl["radios"] != 4 or "FAKE" not in ctrl["text"] or ctrl.get("checked") != topic:
        out["ctrl_present_with_fake_marker"].append(f"控制群組不符：{ctrl and {k: ctrl[k] for k in ('radios', 'checked')}}")
    if ctrl and ctrl["inside_slot"]:
        out["ctrl_outside_slot"].append("控制群組在 onebrain 槽內")
    hs = m.get("hscroll") or {}
    for a, b, name in (("doc_sw", "doc_cw", "document"), ("main_sw", "main_cw", "stMain")):
        if hs.get(a, 0) > hs.get(b, 0) + 1:
            out["no_horizontal_overflow"].append(f"{name} 橫向可捲")
    for scope, text in (("槽", m.get("slot_text") or ""), ("整頁", m.get("page_text") or "")):
        hit = [w for w in NEVER if w in text]
        if scope == "槽" and topic == T.TOPIC_MARKET:
            hit += [w for w in MARKET_WORDS if w in text]
        if hit:
            out["no_forbidden_text"].append(f"{scope}出現 {hit}")
    if T.D7_MARK not in (m.get("slot_text") or ""):
        out["d7_marker_in_slot"].append("槽內缺『預覽暫行口徑（D7 未裁，非正式）』標示")
    return out


def failures(checks: dict[str, list[str]]) -> dict[str, list[str]]:
    return {k: v for k, v in checks.items() if v}


def measure_topic(page, case: str, failclosed: bool, vp: str, vw: int, vh: int, topic: str) -> dict:
    EV._scroll_top(page)
    m = page.evaluate(EV._JS_DEMO)
    m["extra"] = page.evaluate(_JS_EXTRA)
    m.update(case=case, failclosed=failclosed, topic=topic, viewport={"name": vp, "w": vw, "h": vh}, css_variant="baseline")
    return m


def _click_topic(page, topic: str) -> None:
    page.locator(".st-key-ui2_obdemo_ctrl label", has_text=topic).first.click()
    page.wait_for_function("(t) => { const s = document.querySelector('[data-ui2-l1=\"onebrain\"] .ui2-section-title'); return s && s.innerText.includes(t); }",
                           arg=topic, timeout=20000)
    page.wait_for_timeout(400)


def _shots(page, out: Path, stem: str) -> list[str]:
    files = []
    EV._scroll_top(page)
    MV._screenshot(page, out / f"{stem}_viewport.png")
    files.append(f"{stem}_viewport.png")
    slot = page.locator('[data-ui2-l1="onebrain"]')
    if slot.count():
        slot.scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        slot.screenshot(path=str(out / f"{stem}_slot.png"))
        files.append(f"{stem}_slot.png")
    ctrl = page.locator(".st-key-ui2_obdemo_ctrl")
    if ctrl.count():
        ctrl.scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        ctrl.screenshot(path=str(out / f"{stem}_ctrl.png"))
        files.append(f"{stem}_ctrl.png")
    return files


def _real_control(page, out: Path, stem: str, files: list) -> dict:
    """同一 server 切到 Real：槽必須是預設槽；沒有主題選擇器、沒有示範字樣、沒有槽外測試輸入說明。"""
    from shared.ui2_contract.pages import FEED_REAL, P4_HOLD, PAGE_LABELS, SCENARIO_REAL
    from src.ui2.shell.app import _FEED_LABELS
    MV._select_box(page, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
    MV.click_nav(page, PAGE_LABELS[P4_HOLD])
    page.wait_for_selector(f'[data-ui2-page="{P4_HOLD}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
    page.wait_for_timeout(600)
    info = page.evaluate("""() => { const s = document.querySelector('[data-ui2-l1="onebrain"]');
      return {slot_text: s ? s.innerText.replace(/\\s+/g,' ').trim() : null,
              ctrl_present: !!document.querySelector('.st-key-ui2_obdemo_ctrl'), radios: document.querySelectorAll('.st-key-ui2_obdemo_ctrl input[type=radio]').length,
              testinfo_present: !!document.querySelector('.st-key-ui2_obdemo_testinfo')}; }""")
    info["no_demo"] = (info["slot_text"] is not None and "示意：合成持股快照" not in info["slot_text"] and "fake-syn" not in info["slot_text"]
                       and "OneBrain 持股摘要｜" not in info["slot_text"] and not info["ctrl_present"] and not info["testinfo_present"])
    files += _shots(page, out, stem)
    return info


def run_case(p, browser, repo: Path, out: Path, *, case: str, failclosed: bool, python: str) -> dict:
    seal_log = EV._mktemp("obtopics_seal_", ".jsonl")
    seal_log.write_text("", encoding="utf-8")
    env = {"UI2_OBDEMO_CASE": case, "UI2_OBDEMO_SEAL": "1", "UI2_OBDEMO_SEAL_LOG": str(seal_log)}
    env.pop("UI2_OBDEMO_TOPICS", None)
    if failclosed:
        env["UI2_OBDEMO_FAILCLOSED"] = "1"
    proc, url, log = EV.start_server(repo, env, python)
    aborted: list[str] = []
    res: dict = {"measures": {}, "files": [], "real_control": {}}
    key = FAILCLOSED if failclosed else case
    try:
        for vp, (vw, vh) in VIEWPORTS.items():
            ctx = EV._new_context(browser, vw, vh, aborted)
            page = ctx.new_page()
            EV._open_hold_fake(page, url)
            res["measures"][vp] = {}
            for topic in T.TOPICS:
                _click_topic(page, topic)
                m = measure_topic(page, case, failclosed, vp, vw, vh, topic)
                res["measures"][vp][topic] = m
                res["files"] += _shots(page, out, f"{key}_{vp}_{TOPIC_SLUG[topic]}")
            if not failclosed and case == "R1":
                res["real_control"][vp] = _real_control(page, out, f"{key}_{vp}_REALFEED", res["files"])
            ctx.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)
    rejected = EV._read_seal_log(seal_log)
    res["network"] = {"server_rejected": len(rejected), "server_rejected_hosts": sorted({r["host"] for r in rejected}),
                      "context_aborted": len(aborted), "context_aborted_urls": sorted(set(aborted))}
    for f in (log, seal_log):
        try:
            f.unlink()
        except OSError:
            pass
    return res


def _body(m: dict) -> tuple:
    return tuple((r["label"], r["value"], r["detail"]) for r in m.get("rows") or [])


def run_all(repo: Path, out_root: Path, cases=CASE_KEYS, *, python: str = sys.executable) -> dict:
    from playwright.sync_api import sync_playwright
    streamlit_version = MV._streamlit_version(python)
    summary: dict = {"label": LABEL, "runs": []}
    with sync_playwright() as p:
        browser = MV.launch_chromium(p)
        chromium_version = browser.version
        out_root.mkdir(parents=True, exist_ok=True)
        for key in cases:
            fc = key == FAILCLOSED
            case = "R1" if fc else key
            res = run_case(p, browser, repo, out_root, case=case, failclosed=fc, python=python)
            per_vp: dict = {}
            for vp, by_topic in res["measures"].items():
                topics_out = {}
                for topic, m in by_topic.items():
                    checks = failures(evaluate_topic(m, topic, case, fc))
                    topics_out[topic] = {"failures": checks, "pass": not checks, "fold": EV.fold_report(m), "layout": EV.row_layout(m),
                                         "row_count": len(m["rows"]), "slot": m["slot"], "ctrl": m["extra"]["ctrl"], "rows": m["rows"]}
                distinct = len({_body(m) for m in by_topic.values()})
                per_vp[vp] = {"topics": topics_out, "distinct_topic_bodies": distinct,
                              "content_changes_with_topic": distinct == len(T.TOPICS)}
            texts = {vp: tuple(_body(m) for m in by_topic.values()) for vp, by_topic in res["measures"].items()}
            meta = {"label": LABEL, "tool": TOOL, "git_sha": MV._git_head(repo), "streamlit_version": streamlit_version,
                    "chromium_version": chromium_version, "viewports": {k: list(v) for k, v in VIEWPORTS.items()},
                    "file_hashes": {rel: _sha(repo / rel) for rel in FILES}, "case": key,
                    "network_sealed": {"server_sealed": True, "context_sealed": True, **{k: res["network"][k] for k in res["network"]}},
                    "note": ("tests-only 證據；非 DEC-137 正式；不稱 Cloud 已驗；本 runner 不進 CI（NOT VERIFIED 原生 CI）；封網僅本進程 Python socket＋瀏覽器 route，"
                             "非作業系統層。D7 未裁：字數口徑為預覽暫行，非正式。")}
            doc = {"meta": meta, "results": per_vp, "real_control": res["real_control"], "files": res["files"],
                   "same_text_across_viewports": len(set(texts.values())) == 1}
            name = f"onebrain_topics_{key}.json"
            (out_root / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            summary["runs"].append({
                "case": key, "file": name,
                "pass": {vp: {t: v["pass"] for t, v in d["topics"].items()} for vp, d in per_vp.items()},
                "failures": {vp: {t: v["failures"] for t, v in d["topics"].items() if v["failures"]} for vp, d in per_vp.items()},
                "content_changes_with_topic": {vp: d["content_changes_with_topic"] for vp, d in per_vp.items()},
                "same_text_across_viewports": doc["same_text_across_viewports"],
                "real_control_no_demo": {vp: v["no_demo"] for vp, v in res["real_control"].items()},
                "network": res["network"]})
        browser.close()
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "onebrain_topics_evidence"))
    ap.add_argument("--cases", default=",".join(CASE_KEYS))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--allow-in-repo", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    out = Path(a.out).resolve()
    if repo in (out, *out.parents) and not a.allow_in_repo:
        print("拒絕：--out 在 repo 內（證據預設不入庫）。需要請加 --allow-in-repo", file=sys.stderr)
        return 2
    cases = tuple(c for c in a.cases.split(",") if c)
    unknown = [c for c in cases if c not in CASE_KEYS and c not in EV.EXPECTED_ROWS]
    if unknown:
        print(f"未知案例 {unknown}", file=sys.stderr)
        return 2
    summary = run_all(repo, out, cases, python=a.python)
    bad = [r for r in summary["runs"]
           if any(v for d in r["failures"].values() for v in d.values())
           or not all(r["content_changes_with_topic"].values()) or not r["same_text_across_viewports"]
           or not all(r["real_control_no_demo"].values()) or r["network"]["server_rejected"] or r["network"]["context_aborted"]]
    print(f"runs={len(summary['runs'])} failing={len(bad)} out={out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
