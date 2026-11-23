"""OneBrain 持股 FAKE 示範的真瀏覽器證據 runner＋純函式判定器（C-OB-HOLD-DEMO-STAGE2-A1；**tests-only**）。

【A2 scratch 增補（非 #1268 內容；僅存在於 scratch 證據分支，基底＝#1268 head 711142ce38c5cdae07144ae164a72a3bb0f9df6a）】
  `--a2`：(1) 新判定 `no_fake_t_above_slot`（排除測試輸入說明後，整頁文字無 FAKE-T）與 `caption_after_slot`
  （說明在槽外且位於槽下方；fail-closed 無說明）；(2) 新增 clip 圖（槽上緣−120px～說明下緣＋120px；無說明則槽區±120px）；
  (3) L3／FAILCLOSED 另產「開發面顯示」成對 clip；(4) 不產 `_DARK` 截圖（對比量測仍保留）；(5) summary 加 `invocation`（已遮罩）。
  `--a2-assemble DIR --a2-base-sha SHA`：由 DIR 下 `streamlit_*/` 產生 `MANIFEST.json` 與 `SHA256SUMS`（相對路徑）。
  原有判定與輸出格式不變（未加 `--a2` 時行為與 #1268 head 相同）。

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
#: A2 scratch 增補
A2_CLIP_PAD = 120                                    # clip 圖：槽上緣／說明下緣外各 120px
A2_DEV_PAIR_CASES = ("L3", FAILCLOSED)               # 另產「開發面顯示」成對 clip 的案例
A2_FAKE_T = "FAKE-T"
A2_LABEL_NOTE = ("A2 scratch 證據：tests-only 離線示範，非 DEC-137 正式存證；基底＝#1268 head；"
                 "clip 圖以暫時加高的視窗（同寬）截取，量測判定仍以原視窗為準；"
                 "`*_clip_devshown.png` 的下緣另延伸到開發面下緣（若較低）＋120px。")

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
    "L1": "合成測試持股 FAKE-T1、FAKE-T2，均無組合鍵（不出現在上方畫面）",
    "L2": "合成測試持股 FAKE-T1、FAKE-T2，僅 FAKE-T1 有組合鍵（不出現在上方畫面）",
    "L3": "合成測試持股 FAKE-T1、FAKE-T2，均有組合鍵（不出現在上方畫面）",
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
          "source_asof_rows", "first_screen_equals_nodemo", "no_fake_t_above_slot", "caption_after_slot")
A2_NEW_CHECKS = ("no_fake_t_above_slot", "caption_after_slot")


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
    # 13.（A2 增補）排除「測試輸入說明」後，整頁文字不得出現 FAKE-T（合成代號只許出現在槽外說明）
    ex = m.get("page_text_ex_testinfo")
    if ex is None:       # 相容舊量測：由 page_text 扣掉說明全文
        ex = str(m.get("page_text") or "")
        if ti:
            ex = ex.replace(str(ti.get("text", "")), "")
    if A2_FAKE_T in ex:
        out["no_fake_t_above_slot"].append("排除測試輸入說明後，整頁文字仍出現 FAKE-T")
    if "FAKE" not in (m.get("slot_text") or ""):
        out["no_fake_t_above_slot"].append("槽文字不含 FAKE 標示")
    # 14.（A2 增補）說明在槽外、且位於槽下方；fail-closed 必須無說明＋固定句
    if key == FAILCLOSED:
        if ti is not None:
            out["caption_after_slot"].append("fail-closed 不得有說明")
        note_rows = [r for r in rows if r["label"] == "說明"]
        if not note_rows or note_rows[0]["value"] != FAILCLOSED_NOTE:
            out["caption_after_slot"].append("fail-closed 缺固定句")
    elif ti is None or slot is None:
        out["caption_after_slot"].append("缺說明或缺槽，無法判定相對位置")
    else:
        if ti.get("inside_slot"):
            out["caption_after_slot"].append("說明在槽內")
        if ti.get("top") is None or ti["top"] < slot["bottom"] - 0.01:
            out["caption_after_slot"].append(f"說明 top {ti.get('top')} < 槽 bottom {slot['bottom']}（說明未在槽下方）")
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
  clone.querySelectorAll('.st-key-ui2_obdemo_testinfo').forEach(e => e.remove());
  out.page_text_ex_testinfo = (clone.textContent || '').replace(/\s+/g, ' ').trim();
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


_JS_CLIP_GEO = r"""
() => {
  const R = e => { const r = e.getBoundingClientRect(); return {top: r.top, bottom: r.bottom}; };
  const slot = document.querySelector('[data-ui2-l1="onebrain"]');
  const cap = document.querySelector('.st-key-ui2_obdemo_testinfo');
  const bc = document.querySelector('.block-container');
  const dev = document.querySelector('.st-key-ui2_dev_surface');
  const vis = e => !!e && getComputedStyle(e).display !== 'none';
  return {slot: slot ? R(slot) : null, caption: cap ? R(cap) : null, content_bottom: bc ? R(bc).bottom : null,
          dev_surface: (dev && vis(dev)) ? R(dev) : null};
}
"""


def _set_dev_surface(page, shown: bool) -> None:
    """A2：顯示（還原預設）／隱藏開發面（只改 inline display；不動 measure_viewport）。"""
    v = "''" if shown else "'none'"
    page.evaluate("() => { const e = document.querySelector('.st-key-ui2_dev_surface'); if (e) e.style.display = " + v + "; }")


def _clip_bottom(g: dict, dev_shown: bool) -> float:
    """clip 下緣基準：說明下緣（無說明＝槽下緣）；開發面顯示版另取開發面下緣（兩者較大者），好讓 fail-closed 版也看得到開發面。"""
    b = (g["caption"] or g["slot"])["bottom"]
    if dev_shown and g.get("dev_surface"):
        b = max(b, g["dev_surface"]["bottom"])
    return b


def _a2_clip(page, out: Path, name: str, vw: int, vh: int, *, dev_shown: bool) -> dict:
    """A2：clip 圖＝槽上緣−120px 至（說明下緣；無說明則槽下緣）＋120px。暫時加高視窗（同寬）讓上下文放得下，截完還原。"""
    _set_dev_surface(page, dev_shown)
    try:
        page.set_viewport_size({"width": vw, "height": 3200})
        _scroll_top(page)
        g = page.evaluate(_JS_CLIP_GEO)
        if not g["slot"]:
            return {"file": None, "reason": "no slot"}
        y1 = _clip_bottom(g, dev_shown) + A2_CLIP_PAD
        if g["content_bottom"] is not None:
            y1 = min(y1, g["content_bottom"])
        page.set_viewport_size({"width": vw, "height": max(vh, int(y1) + 90)})   # 手機底部固定導覽落在 clip 之外
        _scroll_top(page)
        g = page.evaluate(_JS_CLIP_GEO)
        y0 = max(0.0, g["slot"]["top"] - A2_CLIP_PAD)
        y1 = _clip_bottom(g, dev_shown) + A2_CLIP_PAD
        if g["content_bottom"] is not None:
            y1 = min(y1, g["content_bottom"])
        page.screenshot(path=str(out / name), clip={"x": 0, "y": y0, "width": vw, "height": max(1.0, y1 - y0)})
        rd = lambda d: None if d is None else {k: round(v, 1) for k, v in d.items()}
        return {"file": name, "dev_surface_shown": dev_shown, "clip_y0": round(y0, 1), "clip_y1": round(y1, 1),
                "slot": rd(g["slot"]), "caption": rd(g["caption"]), "dev_surface": rd(g["dev_surface"]),
                "caption_below_slot": (g["caption"]["top"] >= g["slot"]["bottom"]) if g["caption"] else None}
    finally:
        page.set_viewport_size({"width": vw, "height": vh})
        _set_dev_surface(page, True)
        _scroll_top(page)


def _a2_shots(page, out: Path, stem: str, vw: int, vh: int, failclosed: bool, case: str) -> tuple[list[str], dict]:
    files: list[str] = []
    geo: dict = {}
    geo["clip"] = _a2_clip(page, out, f"{stem}_clip.png", vw, vh, dev_shown=False)
    if geo["clip"].get("file"):
        files.append(geo["clip"]["file"])
    if case_key(case, failclosed) in A2_DEV_PAIR_CASES:
        geo["clip_devshown"] = _a2_clip(page, out, f"{stem}_clip_devshown.png", vw, vh, dev_shown=True)
        if geo["clip_devshown"].get("file"):
            files.append(geo["clip_devshown"]["file"])
    return files, geo


def measure_one(page, case: str, failclosed: bool, variant: str, vp_name: str, vw: int, vh: int) -> dict:
    _scroll_top(page)
    m = page.evaluate(_JS_DEMO)
    legacy = MV.measure_state(page, vw, vh)           # 重用既有量測（首屏 elements／hscroll 以此為準）
    m["legacy_first_screen"] = legacy["elements"]
    m["elements"] = [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in e.items()} for e in legacy["elements"]]
    m.update(case=case, failclosed=failclosed, css_variant=variant, viewport={"name": vp_name, "w": vw, "h": vh})
    return m


def run_server_case(p, browser, repo: Path, out: Path, *, tag: str, env_extra: dict, case: str, failclosed: bool,
                    variant: str, python: str, real_control: bool = False, dark: bool = False, a2: bool = False) -> dict:
    """一個 server（一個案例）× 三視窗。回 {"measures": {vp: m}, "files": [...], "network": {...}, "streamlit_version"}。"""
    seal_log = _mktemp("obdemo_seal_", ".jsonl")
    seal_log.write_text("", encoding="utf-8")
    env = {**env_extra, "UI2_OBDEMO_SEAL": "1", "UI2_OBDEMO_SEAL_LOG": str(seal_log)}
    proc, url, log = start_server(repo, env, python)
    aborted: list[str] = []
    res: dict = {"measures": {}, "files": [], "real_control": {}, "dark": {}, "a2_clips": {}}
    try:
        for vp_name, (vw, vh) in VIEWPORTS.items():
            ctx = _new_context(browser, vw, vh, aborted)
            page = ctx.new_page()
            _open_hold_fake(page, url)
            m = measure_one(page, case, failclosed, variant, vp_name, vw, vh)
            res["measures"][vp_name] = m
            res["files"] += _shots(page, out, f"{tag}_{vp_name}", shot_slot=True)
            if a2 and tag != "NODEMO_baseline":
                f2, geo = _a2_shots(page, out, f"{tag}_{vp_name}", vw, vh, failclosed, case)
                res["files"] += f2
                res["a2_clips"][vp_name] = geo
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
                if scheme_dark and not a2:           # A2：不產 _DARK 截圖（對比量測仍保留）
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


def run_all(repo: Path, out_root: Path, cases=CASE_KEYS, *, preview_cases=(), python: str = sys.executable, a2: bool = False,
            invocation: list | None = None) -> dict:
    from playwright.sync_api import sync_playwright
    streamlit_version = MV._streamlit_version(python)
    summary: dict = {"label": LABEL, "runs": []}
    if a2:
        summary.update(a2=True, a2_note=A2_LABEL_NOTE, invocation=invocation or [])
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
                                  dark=(variant == VARIANT_BASELINE and case == "R1"), a2=a2)
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
            if a2:
                doc["a2"] = {"note": A2_LABEL_NOTE, "clips": res["a2_clips"],
                             "new_checks": {vp: {c: (not r["failures"].get(c)) for c in A2_NEW_CHECKS} for vp, r in per_vp.items()}}
            name = f"onebrain_hold_demo_{label}_{variant}.json"
            (out / name).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            summary["runs"].append({"case": label, "variant": variant, "file": f"{VARIANT_DIRS[variant]}/{name}",
                                    "pass": {vp: r["pass"] for vp, r in per_vp.items()},
                                    "failures": {vp: r["failures"] for vp, r in per_vp.items() if r["failures"]},
                                    "meta_failures": doc["meta_failures"], "network": res["network"],
                                    **({"a2_new_checks": doc["a2"]["new_checks"]} if a2 else {})})
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


def _mask_invocation(argv: list[str], repo: Path) -> list[str]:
    """A2：只記相對／已遮罩形式的命令列（不含絕對路徑、帳號、venv 路徑）。"""
    masked = ["python", "-m", "tests.ui2_viewport.onebrain_hold_demo_evidence"]
    it = iter(argv)
    for tok in it:
        if tok == "--out":
            next(it, None)
            masked += ["--out", "<OUT_DIR>"]
        elif tok == "--python":
            next(it, None)
            masked += ["--python", "<VENV_PYTHON>"]
        elif tok.startswith("--out=") or tok.startswith("--python="):
            masked.append(tok.split("=", 1)[0] + "=<MASKED>")
        else:
            masked.append(tok)
    return masked


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=str(repo), text=True).strip()


def assemble_a2_manifest(repo: Path, ev_dir: Path, base_sha: str) -> dict:
    """A2：由 `ev_dir/streamlit_*/` 產生 `MANIFEST.json` 與 `SHA256SUMS`（相對路徑；SHA256SUMS 為 `sha256sum` 格式）。"""
    import datetime
    if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        raise SystemExit("--a2-base-sha 必須是完整 40 位")
    ev_dir = ev_dir.resolve()
    top_skip = {"MANIFEST.json", "SHA256SUMS"}
    files = sorted((p for p in ev_dir.rglob("*") if p.is_file() and not (p.parent == ev_dir and p.name in top_skip)),
                   key=lambda p: p.relative_to(ev_dir).as_posix())
    entries = [{"path": p.relative_to(ev_dir).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size} for p in files]
    runs: dict = {}
    for d in sorted(ev_dir.glob("streamlit_*")):
        summ = json.loads((d / "summary.json").read_text(encoding="utf-8"))
        cases = {}
        for r in summ["runs"]:
            doc = json.loads((d / r["file"]).read_text(encoding="utf-8"))
            meta = doc["meta"]
            cases[r["case"]] = {"json": f"{d.name}/{r['file']}", "viewports_pass": r["pass"], "failures": r["failures"],
                                "meta_failures": r["meta_failures"]}
            info = {k: meta[k] for k in ("streamlit_version", "playwright_version", "chromium_version", "git_sha", "source_hash")}
        gen = sorted(json.loads((d / r["file"]).read_text(encoding="utf-8"))["meta"]["generated_at"] for r in summ["runs"])
        runs[d.name] = {**info, "runs": len(summ["runs"]), "failing": sum(1 for r in summ["runs"] if r["failures"] or r["meta_failures"]),
                        "viewports_total": sum(len(r["pass"]) for r in summ["runs"]),
                        "viewports_passing": sum(sum(1 for v in r["pass"].values() if v) for r in summ["runs"]),
                        "generated_at_utc_first": gen[0], "generated_at_utc_last": gen[-1],
                        "invocation_masked": summ.get("invocation"), "cases": cases}
    inv = {}
    four = {}
    for rel in A1_FILES:
        base_blob = _git_out(repo, "rev-parse", f"{base_sha}:{rel}")
        cur_blob = _git_out(repo, "hash-object", "--no-filters", rel)
        raw = (repo / rel).read_bytes()
        four[rel] = {"sha256": hashlib.sha256(raw).hexdigest(), "git_blob_sha": cur_blob, "head_1268_blob_sha": base_blob,
                     "identical_to_1268_head": cur_blob == base_blob}
    inv["a1_four_files"] = four
    runner = TOOL
    inv["runner_blob_sha"] = {"head_1268": four[runner]["head_1268_blob_sha"], "a2_modified": four[runner]["git_blob_sha"]}
    inv["other_three_identical_to_1268_head"] = {k: v["identical_to_1268_head"] for k, v in four.items() if k != runner}
    added = "tests/ui2_viewport/a2_evidence_privacy_scan.py"
    manifest = {
        "manifest_version": 1,
        "label": "tests-only 離線示範，非 DEC-137 正式存證",
        "base_head_sha": base_sha,
        "scratch_commit_note": ("本目錄隨 scratch 分支 scratch/onebrain-a2-evidence-20261123 的單一 commit 提交；"
                                "該 commit SHA 無法自我包含於本檔，請以 git 取得（見 README）。不開 PR、不進 main。"),
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "source_hash": next(iter(runs.values()))["source_hash"] if runs else None,
        "four_files": four, "runner_blob_sha": inv["runner_blob_sha"],
        "other_three_identical_to_1268_head": inv["other_three_identical_to_1268_head"],
        "a2_added_tool": ({"path": added, "sha256": hashlib.sha256((repo / added).read_bytes()).hexdigest()}
                          if (repo / added).exists() else None),
        "versions": {"streamlit": sorted({r["streamlit_version"] for r in runs.values()}),
                     "playwright": sorted({r["playwright_version"] for r in runs.values()}),
                     "chromium": sorted({r["chromium_version"] for r in runs.values()})},
        "runs": runs, "files": entries, "files_note": "files 不含 MANIFEST.json／SHA256SUMS 本身；SHA256SUMS 另涵蓋 MANIFEST.json。"}
    (ev_dir / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    allf = sorted((p for p in ev_dir.rglob("*") if p.is_file() and p.name != "SHA256SUMS"), key=lambda p: p.relative_to(ev_dir).as_posix())
    (ev_dir / "SHA256SUMS").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ev_dir).as_posix()}\n" for p in allf),
                                       encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "onebrain_a1_evidence"))
    ap.add_argument("--cases", default=",".join(CASE_KEYS))
    ap.add_argument("--preview-css", action="store_true", help="另跑補充比較的預覽 CSS（⛔ 非 baseline）")
    ap.add_argument("--python", default=sys.executable, help="用此 python 起 streamlit server（例：1.56.0 的 venv）")
    ap.add_argument("--allow-in-repo", action="store_true")
    ap.add_argument("--a2", action="store_true", help="A2 scratch 增補：clip 圖／開發面成對／新判定／不產 _DARK")
    ap.add_argument("--a2-assemble", default=None, metavar="DIR", help="A2：由 DIR/streamlit_*/ 產生 MANIFEST.json 與 SHA256SUMS")
    ap.add_argument("--a2-base-sha", default=None, help="A2：#1268 head 完整 40 位 SHA（--a2-assemble 用）")
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    a = ap.parse_args(raw_argv)
    repo = Path(__file__).resolve().parents[2]
    if a.a2_assemble:
        if not a.a2_base_sha:
            print("--a2-assemble 需要 --a2-base-sha", file=sys.stderr)
            return 2
        m = assemble_a2_manifest(repo, Path(a.a2_assemble), a.a2_base_sha)
        print(f"MANIFEST files={len(m['files'])}")
        return 0
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
    summary = run_all(repo, out, cases, preview_cases=(cases if a.preview_css else ()), python=a.python, a2=a.a2,
                      invocation=_mask_invocation(raw_argv, repo) if a.a2 else None)
    bad = [r for r in summary["runs"] if r["failures"] or r["meta_failures"]]
    print(f"runs={len(summary['runs'])} failing={len(bad)} out={out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
