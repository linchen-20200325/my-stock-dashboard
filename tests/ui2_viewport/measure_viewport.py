"""New UI2 Preview 的 viewport／y 座標量測（NUI2-PREVIEW-MOBILE-MEASURE；可重現腳本）。

用法（repo 根；需 Playwright＋Chromium）::

    python -m tests.ui2_viewport.measure_viewport --out docs/vnext/newui2_batch2 [--shots all|first|none]
    python -m tests.ui2_viewport.measure_viewport --url http://localhost:8501 --out /tmp/x   # 量既有 server

對 `streamlit run app_ui2.py` 於 390×844（手機）與 1440×900（桌機），四頁 ×（cold／loaded／missing／
stale／unavailable／not_evaluated）逐一量測並輸出 `viewport_measurements.json`＋截圖。

判定門檻**全部引用既有條文，不自創新門檻**（見 `THRESHOLDS`）。第一屏高度、導覽列高度出自
Freeze §16／Architecture Gate §3：手機第一屏可用高 = 844 − 底部導覽 53 = 791px。
本腳本是 Preview 層量測，⛔ 不連任何真資料（場景全為 FAKE）。

Batch 3 擴充（2026-11-03）：📊 今日結論／今日主要風險（位置與不被插隊）、🎯 模式切換／搜尋框／
W-4 context 行／模式互斥、👤 三種帳戶狀態；🎯 每場景另量「即時查一檔」模式、👤 另量 signed-out／unavailable。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
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
    {"id": "market_conclusion_in_first_screen",
     "rule": "📊 市場：今日結論列存在、位於第一屏（底緣 ≤ 可用高；與 ①～④ 同一條門檻）、且在 ① 市場目前狀態之上。",
     "source": "Freeze §0.1.6-5（四必要項＋今日結論同在第一屏）、Wireframes §2.1／§9、DEC-081 Q2-1／DEC-109"},
    {"id": "market_main_risk_follows_first_screen",
     "rule": "📊 市場：今日主要風險（L1）存在，手機位於第一屏四問之後且其後第一個內容區塊（卡片／摺疊）不早於它的底緣"
             "（⛔ 被 L2／L3 插隊）；桌機與 ①、Risk Cap 同列排成三 tile（頂緣差 ≤ 2px）。",
     "source": "Freeze §0.1.6-3（Q3-3）、Wireframes §2.1 手機／§2.2 桌機三 tile、DEC-117 Q1 桌機"},
    {"id": "target_mode_search_first_screen",
     "rule": "🎯 標的：模式切換恰兩項（市場精選／即時查一檔）且恰一項為當前、搜尋框＋搜尋 CTA 在其下、查詢摘要在搜尋之下，"
             "三者底緣皆 ≤ 可用高。",
     "source": "Freeze §16.2（不用滑：mode、search、查詢摘要）、Wireframes §3.1／W-3"},
    {"id": "target_mode_exclusive",
     "rule": "🎯 標的：同一時間只展開一個模式的內容（精選＝產業／候選卡；查一檔＝查詢結果）；兩者不得同時存在於 DOM。",
     "source": "Freeze §3.1-2／客戶 (10)-B-2（不得同時完整展開）"},
    {"id": "target_w4_context_light",
     "rule": "🎯 標的：市場位階＋Risk Cap 為一行輕量 context，位於查詢摘要之下、字級小於查詢摘要；"
             "查一檔 6 維 Snapshot 的「市場環境」不排第一格。",
     "source": "Wireframes §9 W-4（客戶 Q3）、§3.2"},
    {"id": "me_account_state_first_screen",
     "rule": "👤 我的：帳戶狀態（signed-in／signed-out／unavailable）標示存在；帳戶管理動作列與主 CTA 在第一屏；"
             "主 CTA 字樣依帳戶狀態（未登入＝Google 登入／已登入＝切換 Sheet／讀取失敗＝重新讀取）。",
     "source": "Wireframes §1（👤 我的列）／§5.1、Freeze §16.4（不用滑：connection state、primary management actions）"},
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
    _evaluate_batch3(m, out, mobile, limit)
    # 標題不重疊
    t = m["title"]
    if t["banner_bottom"] is not None and t["top"] < t["banner_bottom"] - 0.5:
        out["no_title_overlap"].append("標題與 banner 重疊")
    if t["qa_top"] is not None and t["qa_top"] < t["bottom"] - 0.5:
        out["no_title_overlap"].append("標題與第一屏區塊重疊")
    return out


_ME_PRIMARY_CTA = {"signed_out": "Google 登入", "signed_in": "切換 Sheet", "unavailable": "重新讀取"}
_TARGET_MODE_LABELS = ("市場精選", "即時查一檔")


def _evaluate_batch3(m: dict, out: dict[str, list[str]], mobile: bool, limit: float) -> None:
    """Batch 3 新增檢查。缺 `page` 鍵（舊版量測 dict）→ 略過，保持向下相容。"""
    page = m.get("page")
    if page is None:
        return
    els = {e["q"]: e for e in m["elements"]}
    if page == "p4_market":
        c = "market_conclusion_in_first_screen"
        if "concl" not in els:
            out[c].append("缺今日結論列")
        else:
            if els["concl"]["bottom"] > limit + 0.5:
                out[c].append(f"今日結論底緣 {els['concl']['bottom']:.0f} > 可用高 {limit}")
            if "q1" in els and els["concl"]["top"] > els["q1"]["top"] + 0.5:
                out[c].append("今日結論不在 ① 市場目前狀態之上")
        k = "market_main_risk_follows_first_screen"
        r = m.get("risk")
        if not r:
            out[k].append("缺今日主要風險")
        else:
            if not r["inside_l1"]:
                out[k].append("今日主要風險不在 L1 容器內（可能被移出）")
            if mobile:
                last_q = max((els[q]["bottom"] for q in ("q1", "q2", "q3", "q4") if q in els), default=0)
                if r["top"] < last_q - 0.5:
                    out[k].append(f"手機：今日主要風險 top {r['top']:.0f} 早於第一屏四問底緣 {last_q:.0f}")
            else:
                for q in ("q1", "ctx"):
                    if q in els and abs(els[q]["top"] - r["top"]) > 2:
                        out[k].append(f"桌機三 tile：{q}.top {els[q]['top']:.0f} 與今日主要風險 {r['top']:.0f} 不同列")
            nb = m.get("first_block_after_l1_top")
            if nb is not None and nb < r["bottom"] - 0.5:
                out[k].append(f"今日主要風險之後的內容區塊 top {nb:.0f} < 其底緣 {r['bottom']:.0f}（被插隊）")
    elif page == "p4_target":
        k = "target_mode_search_first_screen"
        mode = m.get("mode_box")
        srch = els.get("q4")
        if not mode:
            out[k].append("缺模式切換")
        else:
            if tuple(mode["labels"]) != _TARGET_MODE_LABELS:
                out[k].append(f"模式切換項 {mode['labels']!r} ≠ {_TARGET_MODE_LABELS!r}")
            if mode["checked_count"] != 1:
                out[k].append(f"當前模式（checked）數量 {mode['checked_count']} ≠ 1")
            if mode["bottom"] > limit + 0.5:
                out[k].append(f"模式切換底緣 {mode['bottom']:.0f} > 可用高 {limit}")
        if srch is None:
            out[k].append("缺搜尋框／搜尋 CTA")
        else:
            if mode and srch["top"] < mode["bottom"] - 0.5:
                out[k].append("搜尋框不在模式切換之下")
            if "q1" in els and els["q1"]["top"] < srch["bottom"] - 0.5:
                out[k].append("查詢摘要不在搜尋框之下")
        e = "target_mode_exclusive"
        cm = m.get("mode_content")
        if cm is not None and mode:
            curated_on, lookup_on = cm["curated"], cm["lookup"]
            if curated_on and lookup_on:
                out[e].append("兩個模式同時展開")
            if mode["checked_index"] == 0 and (lookup_on or not curated_on):
                out[e].append(f"選『市場精選』但內容 curated={curated_on} lookup={lookup_on}")
            if mode["checked_index"] == 1 and (curated_on or not lookup_on):
                out[e].append(f"選『即時查一檔』但內容 curated={curated_on} lookup={lookup_on}")
        w = "target_w4_context_light"
        ctx = els.get("ctx")
        if ctx is None:
            out[w].append("缺 W-4 市場位階＋Risk Cap context 行")
        else:
            if "q1" in els and ctx["top"] < els["q1"]["bottom"] - 0.5:
                out[w].append("context 行不在查詢摘要之下")
            fs = m.get("font_sizes") or {}
            if fs.get("ctx") is not None and fs.get("q1") is not None and fs["ctx"] >= fs["q1"]:
                out[w].append(f"context 字級 {fs['ctx']} 未小於查詢摘要 {fs['q1']}")
        dims = m.get("snapshot_labels")
        if dims and dims[0] == "市場環境":
            out[w].append("6 維 Snapshot 的『市場環境』排在第一格")
    elif page == "p4_me":
        k = "me_account_state_first_screen"
        acc = m.get("account")
        if not acc:
            out[k].append("缺帳戶管理動作列")
        else:
            if acc["state"] not in _ME_PRIMARY_CTA:
                out[k].append(f"未知帳戶狀態 {acc['state']!r}")
            if acc["bottom"] > limit + 0.5:
                out[k].append(f"帳戶管理動作列底緣 {acc['bottom']:.0f} > 可用高 {limit}")
            q4 = els.get("q4")
            want = _ME_PRIMARY_CTA.get(acc["state"])
            if q4 is None or want is None or want not in q4["text"]:
                out[k].append(f"主 CTA 字樣不符：state={acc['state']} 期望含 {want!r}，實際 {q4['text'] if q4 else None!r}")


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
  const qa = document.querySelector('.ui2-m-l1') || document.querySelector('.ui2-qa');
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
  // ── Batch 3 錨點 ──
  const riskEl = document.querySelector('.ui2-risk');
  const l1 = document.querySelector('.ui2-m-l1');
  const after = [...document.querySelectorAll('.ui2-grid, [data-testid="stExpander"], .ui2-section-title')]
    .filter(e => R(e).height > 1 && (!l1 || !l1.contains(e)) && !e.closest('.st-key-ui2_nav'));
  const afterTops = after.map(e => R(e).top).filter(t => !riskEl || t >= R(riskEl).top - 0.5);
  const modeBox = document.querySelector('.st-key-ui2_target_mode_box');
  const modeLabels = modeBox ? [...modeBox.querySelectorAll('[role="radiogroup"] > label')] : [];
  const modeChecked = modeLabels.findIndex(l => l.querySelector('input').checked);
  const fz = sel => { const e = document.querySelector(sel); return e ? parseFloat(getComputedStyle(e).fontSize) : null; };
  const accEl = document.querySelector('[data-ui2-l1="account_actions"]');
  const snap = [...document.querySelectorAll('.ui2-snapshot [data-dim]')].map(e => e.dataset.dim);
  const pageEl = document.querySelector('.ui2-pagetitle');
  return {
    page: pageEl ? pageEl.dataset.ui2Page : null,
    risk: riskEl ? {...R(riskEl), inside_l1: !!(l1 && l1.contains(riskEl)), text: riskEl.innerText.replace(/\s+/g,' ').trim()} : null,
    first_block_after_l1_top: afterTops.length ? Math.min(...afterTops) : null,
    mode_box: modeBox ? {...R(modeBox), labels: modeLabels.map(l => l.innerText.trim()), checked_count: modeLabels.filter(l => l.querySelector('input').checked).length, checked_index: modeChecked} : null,
    mode_content: pageEl && pageEl.dataset.ui2Page === 'p4_target' ? {curated: !!document.querySelector('[data-ui2-mode-content="curated"]'), lookup: !!document.querySelector('[data-ui2-mode-content="lookup"]')} : null,
    font_sizes: {q1: fz('[data-ui2-q="q1"]'), ctx: fz('.ui2-ctxline')},
    account: accEl ? {...R(accEl), state: accEl.dataset.ui2Account} : null,
    snapshot_labels: snap,
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


def _record(page, vp_name: str, vw: int, vh: int, pid: str, scenario: str, *, mode: str | None = None,
            account: str | None = None) -> dict:
    m = measure_state(page, vw, vh)
    m["scenario"] = scenario
    checks = evaluate(m)
    rd = lambda d: {k: (round(v, 1) if isinstance(v, float) else v) for k, v in d.items()}
    rec = {"viewport_name": vp_name, "viewport": m["viewport"], "page": pid, "scenario": scenario,
           "mode": mode, "account": account,
           "elements": [rd(e) for e in m["elements"]],
           "nav": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in m["nav"].items()
                   if k in ("top", "bottom", "left", "right", "width", "height", "position", "labels", "checked_index")},
           "hscroll": m["hscroll"], "title": {k: (round(v, 1) if v is not None else None) for k, v in m["title"].items()},
           "last_content_bottom": round(m["last_content"]["bottom"], 1),
           "card_heights": m["card_heights"],
           "batch3": {"risk": rd(m["risk"]) if m.get("risk") else None,
                      "mode_box": rd(m["mode_box"]) if m.get("mode_box") else None,
                      "mode_content": m.get("mode_content"), "font_sizes": m.get("font_sizes"),
                      "account": rd(m["account"]) if m.get("account") else None,
                      "snapshot_labels": m.get("snapshot_labels"),
                      "first_block_after_l1_top": (round(m["first_block_after_l1_top"], 1)
                                                   if m.get("first_block_after_l1_top") is not None else None)},
           "failures": {k: v for k, v in checks.items() if v}, "pass": not any(checks.values())}
    return rec


def run_measurements(url: str, out: Path | None, shots: str = "all", server_python: str | None = None,
                     streamlit_version: str | None = None) -> dict:
    from playwright.sync_api import sync_playwright

    from shared.ui2_contract.pages import (
        ACCOUNT_SIGNED_IN, ACCOUNT_SIGNED_OUT, ACCOUNT_UNAVAILABLE, MODE_LABELS, MODE_LOOKUP,
        P4_ME, P4_TARGET, PAGE4_LABELS, PAGE_IDS, SCENARIO_IDS, SCENARIO_LOADED,
    )
    from src.ui2.shell.app import _ACCOUNT_LABELS, _SCENARIO_LABELS

    results: list[dict] = []

    def shot(page, vp_name, pid, scenario, suffix=""):
        if out is not None and _want_shot(shots, vp_name, scenario):
            page.screenshot(path=str(out / f"{vp_name}_{pid}_{scenario}{suffix}.png"))

    with sync_playwright() as p:
        browser = launch_chromium(p)
        for vp_name, (vw, vh) in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": vw, "height": vh})
            page.goto(url)
            page.wait_for_selector(".ui2-qa", timeout=40000)
            nav_click = lambda pid: page.locator(
                ".st-key-ui2_nav [role='radiogroup'] > label", has_text=PAGE4_LABELS[pid]).click()
            for scenario in SCENARIO_IDS:
                _select_box(page, "場景", _SCENARIO_LABELS[scenario], f'[data-ui2-scenario="{scenario}"]')
                for pid in PAGE_IDS:
                    nav_click(pid)
                    page.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{scenario}"]', timeout=30000)
                    page.wait_for_timeout(250)
                    results.append(_record(page, vp_name, vw, vh, pid, scenario,
                                           mode="curated" if pid == P4_TARGET else None,
                                           account=ACCOUNT_SIGNED_IN if pid == P4_ME else None))
                    shot(page, vp_name, pid, scenario)
                    if pid == P4_TARGET:        # 同一場景再量『即時查一檔』模式
                        page.locator(".st-key-ui2_target_mode_box [role='radiogroup'] > label",
                                     has_text=MODE_LABELS[MODE_LOOKUP]).click()
                        page.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-mode="{MODE_LOOKUP}"]', timeout=30000)
                        page.wait_for_timeout(250)
                        results.append(_record(page, vp_name, vw, vh, pid, scenario, mode=MODE_LOOKUP))
                        shot(page, vp_name, pid, scenario, "_lookup")
            # 👤 我的：signed-out／unavailable（以 loaded 場景；signed-in 已含於上方六場景）
            _select_box(page, "場景", _SCENARIO_LABELS[SCENARIO_LOADED], f'[data-ui2-scenario="{SCENARIO_LOADED}"]')
            nav_click(P4_ME)
            for acct in (ACCOUNT_SIGNED_OUT, ACCOUNT_UNAVAILABLE):
                _select_box(page, "帳戶狀態", _ACCOUNT_LABELS[acct], f'[data-ui2-account="{acct}"]')
                page.wait_for_timeout(250)
                results.append(_record(page, vp_name, vw, vh, P4_ME, SCENARIO_LOADED, account=acct))
                shot(page, vp_name, P4_ME, SCENARIO_LOADED, f"_{acct}")
            _select_box(page, "帳戶狀態", _ACCOUNT_LABELS[ACCOUNT_SIGNED_IN], f'[data-ui2-account="{ACCOUNT_SIGNED_IN}"]')
            page.close()
        streamlit_version = streamlit_version or _streamlit_version(server_python)
        browser.close()
    summary = {"states": len(results), "passed": sum(r["pass"] for r in results),
               "failed": [f"{r['viewport_name']}/{r['page']}/{r['scenario']}/{r.get('mode')}/{r.get('account')}"
                          for r in results if not r["pass"]]}
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


def _select_box(page, name: str, option_label: str, anchor: str) -> None:
    """展開『Preview 控制』並在名為 `name` 的 selectbox 選 `option_label`（⛔ 動 app 程式；純用 UI 操作）。"""
    exp = page.locator('[data-testid="stExpander"]', has_text="Preview 控制").first
    if exp.locator("details[open]").count() == 0:
        exp.locator("summary").click()
    page.wait_for_function(
        "() => { const e = document.querySelector('[data-testid=\"stSelectbox\"]'); "
        "return e && e.getBoundingClientRect().height > 10; }", timeout=10000)
    page.wait_for_timeout(500)          # 展開動畫
    box = page.get_by_role("combobox", name=re.compile(re.escape(name)))
    box.first.click()
    page.wait_for_timeout(250)
    if box.first.get_attribute("aria-expanded") != "true":      # Streamlit 1.59（react-aria）click 不一定展開 → 鍵盤展開
        box.first.press("ArrowDown")
    page.get_by_role("option", name=option_label, exact=True).click()
    page.wait_for_selector(anchor, timeout=30000)
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
