"""OneBrain 持股 FAKE 示範的真瀏覽器證據 runner＋純函式判定器（C-OB-HOLD-DEMO-STAGE2-A1；**tests-only**）。

⛔ 這**不是** DEC-137 正式證據（四份固定檔名那一套）：meta 標 `label="tests-only／非 DEC-137 正式"`；
⛔ 不稱 Cloud 已驗；⛔ 本 runner **不進 CI**（既有 browser lane 只列兩個檔；總管 Q9）⇒ 原生 CI 覆蓋 NOT VERIFIED，只有本地封網驗證。

用法（repo 根；需 Playwright＋Chromium；Playwright 只在函式內 import，沒有它時 Fast lane 與 import 本檔都不受影響）::

    python -m tests.ui2_viewport.onebrain_hold_demo_evidence --out /tmp/a1_evidence [--cases R1,L1,L2,L3,FAILCLOSED]
        [--preview-css] [--python /path/to/venv/bin/python]      # --python：用該 python 起 streamlit server（例：1.56.0 的 venv）

流程：每個案例各起一個以 `onebrain_hold_demo_launcher.py` 為入口的 server（cwd＝repo 根、`sys.executable`、env 帶 `UI2_OBDEMO_*`），
`?ui2_dev=1` → 資料來源切 FAKE → 點 💼 持股 → 量測。另起一個**不注入**的 server 當首屏對照（`first_screen_equals_nodemo`）。
視窗在本檔自訂 {390×844, 1280×900, 1440×900}，**不重用** `measure_viewport.VIEWPORTS`（DEC-137 V1 另案會改它）。
封網：server 側（launcher `seal_network`）＋ Playwright context 側（`route` abort 非本機請求）各自計數並寫進 meta。
⚠️ 截圖的開發面（dev surface）：`*_viewport.png` 走 `MV._screenshot`，**預設暫時隱藏開發面**（`.st-key-ui2_dev_surface`）⇒ 這些 PNG 裡，
槽外「測試輸入說明」直接出現在「持股清單」正下方；**開發面顯示時**（真實操作 `?ui2_dev=1` 的畫面），它會接在虛線框
「🧪 開發／測試工具（非產品內容）」**之後**。兩者只差開發面是否入鏡；本 runner 沒有另產「開發面入鏡」的 PNG（`*_testinfo.png` 只截說明容器本身）。
輸出只寫到 `--out`（預設 `tempfile.gettempdir()/onebrain_a1_evidence`；⛔ 預設不在 repo 內）。

判定器 `evaluate_demo()` 是**純函式**（吃量測 dict，不碰瀏覽器），並有突變測試（tests/test_onebrain_holdings_ui2_demo_view.py）。
⚠️ `data-state="ok"` 只是文字載體（見 `onebrain_holdings_ui2_demo_vm.OK_STATE_IS_TEXT_CARRIER_ONLY`）；本檔任何判定不得以它推導持股正常。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from tests.ui2_viewport import measure_viewport as MV

LABEL = "tests-only／非 DEC-137 正式"
#: meta `note` 內的截圖說明（F3 證據誠實）：預設 PNG 隱藏開發面 ⇒ 槽外測試資訊的位置與真實操作畫面不同。
DEVSURFACE_NOTE = ("截圖預設隱藏開發面（.st-key-ui2_dev_surface）：PNG 中槽外「測試輸入說明」緊接在「持股清單」下方；"
                   "開發面顯示時，它在虛線框「🧪 開發／測試工具（非產品內容）」之後。")
TOOL = "tests/ui2_viewport/onebrain_hold_demo_evidence.py"
LAUNCHER = Path(__file__).with_name("onebrain_hold_demo_launcher.py")
#: A 證據自訂尺寸（不重用 MV.VIEWPORTS）。
VIEWPORTS: dict[str, tuple[int, int]] = {"mobile_390": (390, 844), "desktop_1280": (1280, 900), "desktop_1440": (1440, 900)}
MOBILE_MAX_W = 768
VARIANT_BASELINE = "baseline"
VARIANT_PREVIEW = "preview"
VARIANT_DIRS = {VARIANT_BASELINE: "baseline_unmodified_css", VARIANT_PREVIEW: "supplementary_preview_css"}
FAILCLOSED = "FAILCLOSED"
CASE_KEYS = ("R1", "L1", "L2", "L3", FAILCLOSED)

#: A1 四個檔（meta 記 hash；路徑相對 repo 根）
A1_FILES = ("tests/onebrain_holdings_ui2_demo_vm.py", "tests/ui2_viewport/onebrain_hold_demo_launcher.py",
            "tests/ui2_viewport/onebrain_hold_demo_evidence.py", "tests/test_onebrain_holdings_ui2_demo_view.py")

# ── 判定器用的本地 oracle（刻意不 import mapper／demo；改 mapper 時由測試抓到）──────────────
EXPECTED_ROWS = {"R1": 7, "R2": 7, "R3": 7, "L1": 9, "L2": 8, "L3": 5, FAILCLOSED: 5}
DISCLOSURE_ROW = "示意：合成持股快照（FAKE）；非真實持股；非即時 OneBrain；非投資建議"
SOURCE_ROW = "FAKE 合成持股快照（非真實持股）"
ASOF_ROW = "無（FAKE 示意，沒有持股讀取時點）"
FAILCLOSED_NOTE = "示意內容未能產生，未顯示任何摘要句"
TESTINFO_PREFIX = "測試輸入說明（非系統輸出；為本示範的合成測試輸入，非持股清單內容）："
#: 前綴必須同時帶三個語意標記（總管裁示：說明的是「本示範的合成測試輸入」，不是系統摘要、也不是持股清單內容）
TESTINFO_MARKERS = ("非系統輸出", "合成測試輸入", "非持股清單內容")
#: 各案例說明本文的本地 oracle（刻意不 import mapper／demo；與 mapper 的 `TEST_INFO_BODY` 逐字相同，由測試對照）
TESTINFO_BODY = {
    "R1": "合成讀取結局：網路例外（不含持股內容）",
    "R2": "合成讀取結局：未選定投資組合（不含持股內容）",
    "R3": "合成測試持股 FAKE-T1、FAKE-T2 可讀；另有 1 筆資料為非數字",
    "L1": "合成測試持股 FAKE-T1、FAKE-T2，均無組合鍵（不在本頁顯示）",
    "L2": "合成測試持股 FAKE-T1、FAKE-T2，僅 FAKE-T1 有組合鍵（不在本頁顯示）",
    "L3": "合成測試持股 FAKE-T1、FAKE-T2，均有組合鍵（不在本頁顯示）",
}
#: 說明全文不得出現「裸 N 列」（會被誤讀成持股清單的列數，且與槽內顯示列撞詞）
_BARE_ROWS_RX = re.compile(r"\d+\s*列")
DIGEST_LABELS = ("存股", "資本利得")
CARRIER_LABELS = ("示意", "存股", "資本利得", "說明", "來源", "時點")      # D 型列（DOM 上 data-state=ok；只是文字載體）
JUDGEMENT_LABEL = "持股判讀"
#: L3（AVAILABLE）不得出現的完整性／安全字樣
COMPLETENESS_WORDS = ("完整", "正常", "安全", "無異常", "已通過", "OK", "✅", "🟢")
FORBIDDEN_TEXT = ("顯示＝規則式摘要", "FakeProvider", "草稿不採用", "§C", "示範鏈", "與本頁其他 FAKE 數字無關", "is_complete")
FIRST_SCREEN_TOL_PX = 0.5
FIRST_DIGEST_MAX_DISTANCE = 2           # 首個 Digest 句與「示意」首列最多相距 2 列（索引差）
CONTRAST_MIN = 4.5                      # WCAG AA 一般文字（.ui2-row__detail 為 .8rem ≈ 12.8px，非大字）
META_REQUIRED = ("label", "tool", "git_sha", "source_hash", "a1_file_hashes", "generated_at", "streamlit_version",
                 "playwright_version", "chromium_version", "viewports", "network_sealed", "css_variant", "case")

# ══════════════════════════════════════════════════════════════════════
# 純函式判定器
# ══════════════════════════════════════════════════════════════════════
CHECKS = ("slot_rows", "no_horizontal_overflow", "no_truncated_text", "disclosure_first", "l3_no_completeness",
          "testinfo_outside_slot", "no_forbidden_text", "layout_mode", "row_state_attrs", "failclosed_shape",
          "source_asof_rows", "first_screen_equals_nodemo")


def case_key(case: str, failclosed: bool) -> str:
    return FAILCLOSED if failclosed else case


def _is_desktop(m: dict) -> bool:
    return m["viewport"]["w"] > MOBILE_MAX_W


def _first_screen_diff(elements, baseline) -> list[str]:
    out: list[str] = []
    if baseline is None:
        return ["缺少無注入對照（baseline elements）"]
    if [e["q"] for e in elements] != [e["q"] for e in baseline]:
        return [f"首屏 data-ui2-q 區塊集合不同：{[e['q'] for e in elements]} vs {[e['q'] for e in baseline]}"]
    for a, b in zip(elements, baseline):
        if a["text"] != b["text"]:
            out.append(f"{a['q']} 文字不同")
        for k in ("top", "bottom", "left", "right", "width", "height"):
            if abs(a[k] - b[k]) > FIRST_SCREEN_TOL_PX:
                out.append(f"{a['q']}.{k} 差 {a[k] - b[k]:+.2f}px")
    return out


def evaluate_demo(m: dict, baseline_elements=None) -> dict[str, list[str]]:
    """量測 → {檢查名: [失敗描述…]}（空＝通過）。`m` 欄位見 `_JS_DEMO`；另含 case／failclosed／css_variant／viewport。"""
    key = case_key(m["case"], m["failclosed"])
    out: dict[str, list[str]] = {k: [] for k in CHECKS}
    rows = m.get("rows") or []
    labels = [r["label"] for r in rows]
    slot = m.get("slot")
    # 1. 槽存在且列數
    if slot is None:
        out["slot_rows"].append("找不到 [data-ui2-l1=onebrain] 槽")
    elif len(rows) != EXPECTED_ROWS[key]:
        out["slot_rows"].append(f"列數 {len(rows)} ≠ 預期 {EXPECTED_ROWS[key]}（{key}）")
    # 2. 無橫向溢出
    hs = m.get("hscroll") or {}
    for a, b, name in (("doc_sw", "doc_cw", "document"), ("main_sw", "main_cw", "stMain")):
        if hs.get(a, 0) > hs.get(b, 0) + 1:
            out["no_horizontal_overflow"].append(f"{name} 橫向可捲（{hs.get(a)} > {hs.get(b)}）")
    if slot is not None and slot.get("scroll_w", 0) > slot.get("client_w", 0) + 1:
        out["no_horizontal_overflow"].append("槽 scrollWidth > clientWidth")
    # 3. 無截斷
    for t in m.get("truncated") or []:
        out["no_truncated_text"].append(f"{t.get('why')}：{t.get('text')}")
    # 4. 示意首列在最前，且與首個 Digest 句 ≤ 2 列
    if not rows or labels[0] != "示意" or rows[0]["value"] != DISCLOSURE_ROW:
        out["disclosure_first"].append("槽內第一列不是逐字的「示意」揭露")
    digest_idx = [i for i, lb in enumerate(labels) if lb in DIGEST_LABELS]
    if digest_idx and digest_idx[0] > FIRST_DIGEST_MAX_DISTANCE:
        out["disclosure_first"].append(f"首個 Digest 句在第 {digest_idx[0]} 列（>{FIRST_DIGEST_MAX_DISTANCE}）")
    if key == FAILCLOSED and digest_idx:
        out["disclosure_first"].append("fail-closed 不得有 Digest 句")
    # 5. L3 不得有完整性字樣
    if key == "L3":
        text = m.get("slot_text") or ""
        hit = [w for w in COMPLETENESS_WORDS if w in text]
        if hit:
            out["l3_no_completeness"].append(f"L3 出現完整性／安全字樣 {hit}")
    # 6. 測試輸入說明在槽外（fail-closed 不顯示）
    ti = m.get("testinfo")
    if key == FAILCLOSED:
        if ti is not None:
            out["testinfo_outside_slot"].append("fail-closed 不得顯示測試輸入說明")
    elif ti is None:
        out["testinfo_outside_slot"].append("正常案例缺測試輸入說明")
    else:
        if ti.get("inside_slot"):
            out["testinfo_outside_slot"].append("測試輸入說明在 onebrain 槽內（closest 非 null）")
        if not str(ti.get("text", "")).startswith(TESTINFO_PREFIX):
            out["testinfo_outside_slot"].append("測試輸入說明前綴不是約定的整句前綴（須含「非系統輸出」「合成測試輸入」「非持股清單內容」）")
        txt = str(ti.get("text", ""))
        miss = [w for w in TESTINFO_MARKERS if w not in txt]
        if miss:
            out["testinfo_outside_slot"].append(f"測試輸入說明缺語意標記 {miss}")
        if _BARE_ROWS_RX.search(txt):
            out["testinfo_outside_slot"].append("測試輸入說明含裸「N 列」（會被誤讀成持股清單列數）")
        if key in TESTINFO_BODY and txt != TESTINFO_PREFIX + TESTINFO_BODY[key]:
            out["testinfo_outside_slot"].append("測試輸入說明整句與該案例的約定字樣不同")
        if txt.replace("非持股清單內容", "").count("持股清單"):
            out["testinfo_outside_slot"].append("測試輸入說明出現「持股清單」（僅許可於『非持股清單內容』的否定語）")
    # 7. 禁字（槽與整頁產品文字）
    for scope, text in (("槽", m.get("slot_text") or ""), ("整頁", m.get("page_text") or "")):
        hit = [w for w in FORBIDDEN_TEXT if w in text]
        if hit:
            out["no_forbidden_text"].append(f"{scope}出現 {hit}")
    # 8. 桌機版面（baseline 必須是 flex；preview 必須是 block；手機不得是 flex）
    if slot is not None:
        disp = slot.get("display")
        variant = m["css_variant"]
        if _is_desktop(m):
            want = "flex" if variant == VARIANT_BASELINE else "block"
            if disp != want:
                out["layout_mode"].append(f"桌機 .ui2-m-onebrain display={disp}，{variant} 須為 {want}")
        elif disp == "flex":
            out["layout_mode"].append("手機 .ui2-m-onebrain 不應為 flex")
    # 9. 列的 DOM 屬性（只檢查「載體」現象；⛔ 不以 ok 推導安全）
    for r in rows:
        if r["label"] == JUDGEMENT_LABEL:
            if (r["axis"], r["state"]) != ("judgement", "undeterminable"):
                out["row_state_attrs"].append(f"持股判讀 列屬性 {r['axis']}/{r['state']}")
        elif r["label"] in CARRIER_LABELS:
            if (r["axis"], r["state"]) != ("data", "ok"):
                out["row_state_attrs"].append(f"{r['label']} 列屬性 {r['axis']}/{r['state']}（預期文字載體 data/ok）")
        else:
            out["row_state_attrs"].append(f"label 不在白名單：{r['label']}")
    # 10. fail-closed 形狀
    if key == FAILCLOSED:
        if labels != ["示意", "持股判讀", "說明", "來源", "時點"]:
            out["failclosed_shape"].append(f"fail-closed 列 {labels}")
        note = [r for r in rows if r["label"] == "說明"]
        if not note or note[0]["value"] != FAILCLOSED_NOTE:
            out["failclosed_shape"].append("fail-closed 說明不是固定句")
    # 11. 來源／時點
    if len(rows) >= 2 and (labels[-2:] != ["來源", "時點"] or rows[-2]["value"] != SOURCE_ROW
                           or rows[-1]["value"] != ASOF_ROW):
        out["source_asof_rows"].append("末兩列不是逐字的 來源／時點")
    elif len(rows) < 2:
        out["source_asof_rows"].append("缺來源／時點")
    # 12. 首屏與無注入對照一致
    out["first_screen_equals_nodemo"] = _first_screen_diff(m.get("elements") or [], baseline_elements)
    return out


def failures(checks: dict[str, list[str]]) -> dict[str, list[str]]:
    return {k: v for k, v in checks.items() if v}


def fold_report(m: dict) -> dict | None:
    """手機：槽相對底部保留線（vh−53，390×844 為 791）的位置（**量測值，不是 pass/fail**；不得縮字或刪列來「修」）。"""
    if m["viewport"]["w"] > MOBILE_MAX_W or not m.get("slot"):
        return None
    fold = m["viewport"]["h"] - MV.NAV_MOBILE_H
    rows = m.get("rows") or []
    s = m["slot"]
    return {"fold": fold, "slot_top": round(s["top"], 1), "slot_bottom": round(s["bottom"], 1),
            "slot_crosses_fold": s["top"] < fold < s["bottom"],
            "first_row_bottom": round(rows[0]["bottom"], 1) if rows else None,
            "first_row_above_fold": bool(rows) and rows[0]["bottom"] <= fold,
            "rows_fully_below_fold": sum(1 for r in rows if r["top"] >= fold)}


def row_layout(m: dict) -> dict:
    """列怎麼排（桌機並排判讀用）：同一 top（±2px）的列視為同一行。"""
    rows = m.get("rows") or []
    lines: list[list[str]] = []
    tops: list[float] = []
    for r in rows:
        for i, t in enumerate(tops):
            if abs(r["top"] - t) <= 2:
                lines[i].append(r["label"])
                break
        else:
            tops.append(r["top"])
            lines.append([r["label"]])
    title = m.get("title")
    title_shares_row = bool(rows and title and abs(title["top"] - rows[0]["top"]) <= 6)
    return {"visual_lines": lines, "rows_sharing_a_line": sum(1 for ln in lines if len(ln) > 1),
            "title_on_same_line_as_first_row": title_shares_row}


# ── 對比（深色主題；單量，量不到＝NOT VERIFIED）──────────────────────────────
def _lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(fg_rgb, bg_rgb) -> float:
    a, b = sorted((luminance(fg_rgb), luminance(bg_rgb)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def effective_contrast(sample: dict | None) -> float | None:
    """sample＝`_JS_CONTRAST` 的回傳。前景以其 alpha×祖先 opacity 與不透明背景混色；量不到（無不透明背景）→ None（NOT VERIFIED）。"""
    if not sample or not sample.get("fg") or not sample.get("bg") or sample["bg"].get("a", 0) < 0.999 or sample.get("bg_partial"):
        return None
    fg, bg = sample["fg"], sample["bg"]
    alpha = fg.get("a", 1.0) * sample.get("opacity", 1.0)
    mixed = tuple(fg[k] * alpha + bg[k] * (1 - alpha) for k in ("r", "g", "b"))
    return contrast_ratio(mixed, (bg["r"], bg["g"], bg["b"]))


def check_meta(meta: dict) -> list[str]:
    """證據 meta 必填欄位（缺任一即判紅）。"""
    bad = [f"缺 meta.{k}" for k in META_REQUIRED if meta.get(k) in (None, "", {}, [])]
    if meta.get("label") != LABEL:
        bad.append("meta.label 不是「tests-only／非 DEC-137 正式」")
    sha = meta.get("git_sha")
    if sha and not re.fullmatch(r"[0-9a-f]{40}", str(sha)):
        bad.append("git_sha 不是完整 40 位")
    if meta.get("css_variant") not in VARIANT_DIRS:
        bad.append("css_variant 不是 baseline／preview")
    ns = meta.get("network_sealed") or {}
    for k in ("server_sealed", "server_rejected", "context_aborted", "context_sealed"):
        if k not in ns:
            bad.append(f"meta.network_sealed 缺 {k}")
    hashes = meta.get("a1_file_hashes") or {}
    if sorted(hashes) != sorted(A1_FILES):
        bad.append("a1_file_hashes 必須恰為 A1 四個檔")
    return bad


def variant_dir_ok(meta: dict, dirname: str) -> bool:
    """baseline 目錄不得出現 preview 圖／JSON；反之亦然。"""
    return VARIANT_DIRS.get(meta.get("css_variant")) == dirname


# ══════════════════════════════════════════════════════════════════════
# 瀏覽器端（Playwright 只在函式內 import）
# ══════════════════════════════════════════════════════════════════════
_JS_DEMO = r"""
() => {
  const R = e => { const r = e.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height}; };
  const txt = e => e.innerText.replace(/\s+/g,' ').trim();
  const slot = document.querySelector('[data-ui2-l1="onebrain"]');
  const main = document.querySelector('[data-testid="stMain"]') || document.documentElement;
  const out = {slot: null, rows: [], title: null, truncated: [], testinfo: null};
  out.hscroll = {doc_sw: document.documentElement.scrollWidth, doc_cw: document.documentElement.clientWidth,
                 main_sw: main.scrollWidth, main_cw: main.clientWidth};
  const bcEl = document.querySelector('.block-container') || document.body;
  const clone = bcEl.cloneNode(true);
  clone.querySelectorAll('.st-key-ui2_dev_surface, .st-key-ui2_nav, style, script').forEach(e => e.remove());
  out.page_text = (clone.textContent || '').replace(/\s+/g, ' ').trim();
  if (slot) {
    const cs = getComputedStyle(slot);
    out.slot = {...R(slot), display: cs.display, flex_wrap: cs.flexWrap, scroll_w: slot.scrollWidth, client_w: slot.clientWidth};
    out.slot_text = txt(slot);
    const t = slot.querySelector('.ui2-section-title'); out.title = t ? {...R(t), text: txt(t)} : null;
    const body = slot.closest('.ui2-h-body'); out.body_width = body ? R(body).width : null;
    out.rows = [...slot.querySelectorAll('.ui2-row')].map(r => {
      const l = r.querySelector('.ui2-row__label'), v = r.querySelector('.ui2-row__value'),
            d = r.querySelector('.ui2-row__detail'), c = r.querySelector('.ui2-chip');
      return {label: l ? txt(l) : '', value: v ? txt(v) : '', chip: c ? txt(c) : '', detail: d ? txt(d) : '',
              axis: r.dataset.axis, state: r.dataset.state, ...R(r)};
    });
    const w = document.createTreeWalker(slot, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) {
      const text = n.nodeValue.trim(); if (!text) continue;
      const rg = document.createRange(); rg.selectNodeContents(n); const rr = rg.getBoundingClientRect();
      const short = text.slice(0, 40);
      if (rr.width === 0 && rr.height === 0) { out.truncated.push({why: '文字節點未渲染（零尺寸）', text: short}); continue; }
      if (rr.left < -1 || rr.right > innerWidth + 1) out.truncated.push({why: '超出視窗', text: short, left: rr.left, right: rr.right});
      for (let e = n.parentElement; e && e !== document.documentElement; e = e.parentElement) {
        const c = getComputedStyle(e);
        if (['hidden', 'clip', 'auto', 'scroll'].includes(c.overflowX)) {
          const er = e.getBoundingClientRect();
          if (rr.left < er.left - 1 || rr.right > er.right + 1) out.truncated.push({why: '被祖先橫向裁切', text: short, el: (e.className || e.tagName).toString().slice(0, 40)});
        }
        if (['hidden', 'clip'].includes(c.overflowY) && e.scrollHeight > e.clientHeight + 1)
          out.truncated.push({why: '被祖先縱向裁切', text: short, el: (e.className || e.tagName).toString().slice(0, 40)});
        if (c.textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1) out.truncated.push({why: 'ellipsis 截斷', text: short});
        if (c.webkitLineClamp && c.webkitLineClamp !== 'none') out.truncated.push({why: 'line-clamp', text: short});
      }
    }
  }
  const ti = document.querySelector('.st-key-ui2_obdemo_testinfo');
  if (ti) out.testinfo = {text: txt(ti), inside_slot: !!ti.closest('[data-ui2-l1="onebrain"]'),
                          slot_contains: slot ? slot.contains(ti) : false, ...R(ti)};
  out.elements = [...document.querySelectorAll('[data-ui2-q]')].map(e => ({q: e.dataset.ui2Q, text: txt(e), ...R(e)}));
  return out;
}
"""

_JS_CONTRAST = r"""
(sel) => {
  const slot = document.querySelector('[data-ui2-l1="onebrain"]'); if (!slot) return null;
  const el = slot.querySelector(sel); if (!el) return null;
  const parse = s => { const m = (s || '').match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(parseFloat); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const cs = getComputedStyle(el);
  let op = 1; for (let e = el; e; e = e.parentElement) op *= parseFloat(getComputedStyle(e).opacity);
  let bg = null, partial = false;
  for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor);
    if (c && c.a > 0) { if (c.a >= 0.999) { bg = c; break; } partial = true; } }
  return {fg: parse(cs.color), opacity: op, bg: bg, bg_partial: partial, font_size: cs.fontSize, text: el.innerText.trim().slice(0, 40),
          prefers_dark: matchMedia('(prefers-color-scheme: dark)').matches};
}
"""


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def a1_file_hashes(repo: Path) -> dict[str, str]:
    return {rel: _sha256(repo / rel) for rel in A1_FILES}


def _mktemp(prefix: str, suffix: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)
    return Path(name)


def start_server(repo: Path, env_extra: dict[str, str], python: str = sys.executable) -> tuple[subprocess.Popen, str, Path]:
    """以 launcher 為入口起 streamlit server（cwd＝repo 根；不重用 MV.start_server，它寫死 app_ui2.py）。回 (proc, url, log 路徑)。"""
    port = MV._free_port()
    env = {**os.environ, **env_extra, "PYTHONDONTWRITEBYTECODE": "1"}
    log = _mktemp("obdemo_server_", ".log")
    fh = open(log, "wb")
    proc = subprocess.Popen(
        [python, "-m", "streamlit", "run", str(LAUNCHER), "--server.headless", "true", "--server.port", str(port),
         "--browser.gatherUsageStats", "false"],
        cwd=str(repo), env=env, stdout=fh, stderr=subprocess.STDOUT)
    fh.close()                       # 子進程持有自己的 fd
    url = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            urllib.request.urlopen(url + "/_stcore/health", timeout=1)
            return proc, url, log
        except Exception:
            if proc.poll() is not None:
                break
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("streamlit server 未就緒：" + log.read_text(encoding="utf-8", errors="replace")[-800:])


def _read_seal_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _new_context(browser, vw: int, vh: int, aborted: list, *, dark: bool = False):
    """Playwright context：封網（abort 非本機請求並計數）。"""
    ctx = browser.new_context(viewport={"width": vw, "height": vh}, color_scheme="dark" if dark else "light")

    def handler(route):
        host = re.match(r"^[a-z][a-z0-9+.-]*://([^/:]+)", route.request.url)
        if host and host.group(1) in ("127.0.0.1", "localhost", "[::1]"):
            route.continue_()
        else:
            aborted.append(route.request.url.split("?")[0][:120])
            route.abort()
    ctx.route("**/*", handler)
    return ctx


def _open_hold_fake(page, url: str) -> None:
    from shared.ui2_contract.pages import FEED_FAKE, P4_HOLD, PAGE_LABELS, SCENARIO_COLD
    from src.ui2.shell.app import _FEED_LABELS
    page.goto(MV._dev_url(url))
    page.wait_for_selector(".ui2-qa", timeout=40000)
    MV._select_box(page, "資料來源", _FEED_LABELS[FEED_FAKE], f'[data-ui2-scenario="{SCENARIO_COLD}"]')
    MV.click_nav(page, PAGE_LABELS[P4_HOLD])
    page.wait_for_selector(f'[data-ui2-page="{P4_HOLD}"][data-ui2-scenario="{SCENARIO_COLD}"]', timeout=30000)
    page.wait_for_timeout(500)


def _scroll_top(page) -> None:
    page.evaluate("(() => { const m = document.querySelector('[data-testid=\"stMain\"]'); if (m) m.scrollTo({top: 0, behavior: 'instant'}); })()")
    page.wait_for_timeout(150)


def _shots(page, out: Path, stem: str, shot_slot: bool) -> list[str]:
    files = []
    _scroll_top(page)
    MV._screenshot(page, out / f"{stem}_viewport.png")
    files.append(f"{stem}_viewport.png")
    if shot_slot and page.locator('[data-ui2-l1="onebrain"]').count():
        page.locator('[data-ui2-l1="onebrain"]').scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        page.locator('[data-ui2-l1="onebrain"]').screenshot(path=str(out / f"{stem}_slot.png"))
        files.append(f"{stem}_slot.png")
    if page.locator(".st-key-ui2_obdemo_testinfo").count():
        page.locator(".st-key-ui2_obdemo_testinfo").scroll_into_view_if_needed()
        page.wait_for_timeout(150)
        page.locator(".st-key-ui2_obdemo_testinfo").screenshot(path=str(out / f"{stem}_testinfo.png"))
        files.append(f"{stem}_testinfo.png")
    return files


def measure_one(page, case: str, failclosed: bool, variant: str, vp_name: str, vw: int, vh: int) -> dict:
    _scroll_top(page)
    m = page.evaluate(_JS_DEMO)
    legacy = MV.measure_state(page, vw, vh)           # 重用既有量測（首屏 elements／hscroll 以此為準）
    m["legacy_first_screen"] = legacy["elements"]
    m["elements"] = [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in e.items()} for e in legacy["elements"]]
    m.update(case=case, failclosed=failclosed, css_variant=variant, viewport={"name": vp_name, "w": vw, "h": vh})
    return m


def run_server_case(p, browser, repo: Path, out: Path, *, tag: str, env_extra: dict, case: str, failclosed: bool,
                    variant: str, python: str, real_control: bool = False, dark: bool = False) -> dict:
    """一個 server（一個案例）× 三視窗。回 {"measures": {vp: m}, "files": [...], "network": {...}, "streamlit_version"}。"""
    seal_log = _mktemp("obdemo_seal_", ".jsonl")
    seal_log.write_text("", encoding="utf-8")
    env = {**env_extra, "UI2_OBDEMO_SEAL": "1", "UI2_OBDEMO_SEAL_LOG": str(seal_log)}
    proc, url, log = start_server(repo, env, python)
    aborted: list[str] = []
    res: dict = {"measures": {}, "files": [], "real_control": {}, "dark": {}}
    try:
        for vp_name, (vw, vh) in VIEWPORTS.items():
            ctx = _new_context(browser, vw, vh, aborted)
            page = ctx.new_page()
            _open_hold_fake(page, url)
            m = measure_one(page, case, failclosed, variant, vp_name, vw, vh)
            res["measures"][vp_name] = m
            res["files"] += _shots(page, out, f"{tag}_{vp_name}", shot_slot=True)
            if real_control:
                res["real_control"][vp_name] = _real_control(page, out, f"{tag}_{vp_name}_REALFEED", res["files"])
            ctx.close()
        if dark:
            for scheme_dark in (False, True):
                ctx = _new_context(browser, 390, 844, aborted, dark=scheme_dark)
                page = ctx.new_page()
                _open_hold_fake(page, url)
                key = "dark" if scheme_dark else "light"
                res["dark"][key] = {sel: page.evaluate(_JS_CONTRAST, sel) for sel in (".ui2-row__detail", ".ui2-row__value")}
                if scheme_dark:
                    res["files"] += _shots(page, out, f"{tag}_mobile_390_DARK", shot_slot=True)
                ctx.close()
    finally:
        proc.kill()
        proc.wait(timeout=10)
    rejected = _read_seal_log(seal_log)
    res["network"] = {"server_rejected": len(rejected), "server_rejected_hosts": sorted({r["host"] for r in rejected}),
                      "context_aborted": len(aborted), "context_aborted_urls": sorted(set(aborted))}
    for f in (log, seal_log):
        try:
            f.unlink()
        except OSError:
            pass
    return res


def _real_control(page, out: Path, stem: str, files: list) -> dict:
    """同一 server 切回 Real：槽必須是預設槽，無示範文字、無槽外測試資訊（Real 不經 wrapper）。"""
    from shared.ui2_contract.pages import FEED_REAL, P4_HOLD, PAGE_LABELS, SCENARIO_REAL
    from src.ui2.shell.app import _FEED_LABELS
    MV._select_box(page, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
    MV.click_nav(page, PAGE_LABELS[P4_HOLD])
    page.wait_for_selector(f'[data-ui2-page="{P4_HOLD}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
    page.wait_for_timeout(500)
    info = page.evaluate("""() => { const s = document.querySelector('[data-ui2-l1="onebrain"]');
      return {slot_text: s ? s.innerText.replace(/\\s+/g,' ').trim() : null,
              testinfo_present: !!document.querySelector('.st-key-ui2_obdemo_testinfo')}; }""")
    info["no_demo_text"] = info["slot_text"] is not None and "示意：合成持股快照" not in info["slot_text"] and not info["testinfo_present"]
    files += _shots(page, out, stem, shot_slot=True)
    return info


def build_meta(repo: Path, *, variant: str, case: str, streamlit_version: str, chromium_version: str, network: dict,
               server_sealed: bool = True) -> dict:
    base = MV.evidence_meta(repo, chromium_version)
    return {"label": LABEL, "tool": TOOL, **base, "a1_file_hashes": a1_file_hashes(repo),
            "streamlit_version": streamlit_version, "viewports": {k: list(v) for k, v in VIEWPORTS.items()},
            "network_sealed": {"server_sealed": server_sealed, "context_sealed": True,
                               "server_rejected": network["server_rejected"], "context_aborted": network["context_aborted"],
                               "server_rejected_hosts": network["server_rejected_hosts"],
                               "context_aborted_urls": network["context_aborted_urls"]},
            "css_variant": variant, "case": case,
            "note": ("tests-only 證據；非 DEC-137 正式；不稱 Cloud 已驗；本 runner 不進 CI（NOT VERIFIED 原生 CI）；"
                     "封網僅本進程 Python socket＋瀏覽器 route，非作業系統層。" + DEVSURFACE_NOTE)}


def run_all(repo: Path, out_root: Path, cases=CASE_KEYS, *, preview_cases=(), python: str = sys.executable) -> dict:
    from playwright.sync_api import sync_playwright
    streamlit_version = MV._streamlit_version(python)
    summary: dict = {"label": LABEL, "runs": []}
    with sync_playwright() as p:
        browser = MV.launch_chromium(p)
        chromium_version = browser.version
        baseline_elements: dict[str, list] = {}
        plan = [(VARIANT_BASELINE, "NODEMO", {}, "NODEMO")]
        plan += [(VARIANT_BASELINE, c, _env_for(c, False), c) for c in cases]
        plan += [(VARIANT_PREVIEW, c, {**_env_for(c, True)}, c) for c in preview_cases]
        for variant, case, env, label in plan:
            out = out_root / VARIANT_DIRS[variant]
            out.mkdir(parents=True, exist_ok=True)
            fc = case == FAILCLOSED
            real_case = "R1" if fc else case
            res = run_server_case(p, browser, repo, out, tag=f"{label}_{variant}", env_extra=env, case=real_case, failclosed=fc,
                                  variant=variant, python=python, real_control=(variant == VARIANT_BASELINE and case == "R1"),
                                  dark=(variant == VARIANT_BASELINE and case == "R1"))
            if case == "NODEMO":
                baseline_elements = {vp: m["elements"] for vp, m in res["measures"].items()}
                continue
            meta = build_meta(repo, variant=variant, case=case, streamlit_version=streamlit_version,
                              chromium_version=chromium_version, network=res["network"])
            per_vp = {}
            for vp, m in res["measures"].items():
                checks = evaluate_demo(m, baseline_elements.get(vp))
                per_vp[vp] = {"measure": m, "failures": failures(checks), "pass": not failures(checks),
                              "fold": fold_report(m), "layout": row_layout(m)}
            contrast = {scheme: {sel: effective_contrast(s) for sel, s in d.items()} for scheme, d in res["dark"].items()}
            doc = {"meta": meta, "meta_failures": check_meta(meta), "results": per_vp, "real_control": res["real_control"],
                   "contrast": contrast, "files": res["files"]}
            name = f"onebrain_hold_demo_{label}_{variant}.json"
            (out / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            summary["runs"].append({"case": label, "variant": variant, "file": f"{VARIANT_DIRS[variant]}/{name}",
                                    "pass": {vp: r["pass"] for vp, r in per_vp.items()},
                                    "failures": {vp: r["failures"] for vp, r in per_vp.items() if r["failures"]},
                                    "meta_failures": doc["meta_failures"], "network": res["network"]})
        browser.close()
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def _env_for(case: str, preview: bool) -> dict:
    env = {"UI2_OBDEMO_CASE": "R1" if case == FAILCLOSED else case}
    if case == FAILCLOSED:
        env["UI2_OBDEMO_FAILCLOSED"] = "1"
    if preview:
        env["UI2_OBDEMO_PREVIEW_CSS"] = "1"
    return env


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "onebrain_a1_evidence"))
    ap.add_argument("--cases", default=",".join(CASE_KEYS))
    ap.add_argument("--preview-css", action="store_true", help="另跑補充比較的預覽 CSS（⛔ 非 baseline）")
    ap.add_argument("--python", default=sys.executable, help="用此 python 起 streamlit server（例：1.56.0 venv）")
    ap.add_argument("--allow-in-repo", action="store_true")
    a = ap.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    out = Path(a.out).resolve()
    if repo in (out, *out.parents) and not a.allow_in_repo:
        print("拒絕：--out 在 repo 內（A1 證據預設不入庫；A2 另案）。需要請加 --allow-in-repo", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    cases = tuple(c for c in a.cases.split(",") if c)
    unknown = [c for c in cases if c not in CASE_KEYS and c not in EXPECTED_ROWS]
    if unknown:
        print(f"未知案例 {unknown}", file=sys.stderr)
        return 2
    summary = run_all(repo, out, cases, preview_cases=(cases if a.preview_css else ()), python=a.python)
    bad = [r for r in summary["runs"] if r["failures"] or r["meta_failures"]]
    print(f"runs={len(summary['runs'])} failing={len(bad)} out={out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
