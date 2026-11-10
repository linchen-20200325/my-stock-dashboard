"""New UI2 Preview 的 viewport／y 座標量測（NUI2-PREVIEW-MOBILE-MEASURE；可重現腳本）。

用法（repo 根；需 Playwright＋Chromium）::

    python -m tests.ui2_viewport.measure_viewport --out docs/vnext/newui2_batch2 [--shots all|first|none]
    python -m tests.ui2_viewport.measure_viewport --url http://localhost:8501 --out /tmp/x   # 量既有 server
    python -m tests.ui2_viewport.measure_viewport --feed real --shots all --out docs/vnext/newui2_realfeed  # Real-data Preview

DEC-146（2026-11-07）：導覽改為**頂部兩列五頁**（第一列＝Active Sheet｜FAKE／Real 模式標示｜帳號；第二列＝五頁 radiogroup；
⛔ Drawer／左 rail）。判定器相應改寫（`nav_fixed_four`→`nav_fixed_five_top`；`first_screen_above_nav`／`no_title_overlap`／
`p1_banner_single_line`／`real_feed_banner_on_top` 改為「頂部導覽／第一列內」的等價判定，均有突變 teeth，見 tests/test_ui2_batch2.py）。
`p2_nav_margin_160` 的量測錨點（今日主要風險之後第一區塊頂緣 → 底部保留線 791）與舊值**同公式同單位**，只是頂部導覽的高度現在
自然包含在內（內容被導覽往下推），所以舊 162.5 與現值可直接比較；門檻 160 不變。

對 `streamlit run app_ui2.py` 於 390×844（手機）與 1440×900（桌機），五頁 ×（cold／loaded／missing／
stale／unavailable／not_evaluated）逐一量測並輸出 `viewport_measurements.json`＋截圖。

判定門檻**全部引用既有條文，不自創新門檻**（見 `THRESHOLDS`）。第一屏高度、導覽列高度出自
Freeze §16／Architecture Gate §3：手機第一屏可用高 = 844 − 底部導覽 53 = 791px。
本腳本是 Preview 層量測；預設 `--feed fake`（場景全為 FAKE）。`--feed real`（NUI2-REAL-FEED A3，2026-11-03）
切到 Real-data Preview（唯讀 feed：本地 git 追蹤快取＋本地狀態檔；不觸發更新）量四頁第一屏與 banner。

P1（New UI2 UI Correction，2026-11-03）：Preview 控制（資料來源／場景／帳戶）改在 `?ui2_dev=1` 開發面（虛線框「🧪 開發／測試工具（非產品內容）」，
`.st-key-ui2_dev_surface`），預設道 0 個控制。本腳本一律以 `?ui2_dev=1` 開頁來切場景（仍是純 UI 操作）；量測「頁底內容」時排除開發面區塊
（它不是產品內容）；截圖預設把開發面暫時隱藏（`--keep-dev` 才保留），所以截圖＝產品畫面，與預設道逐像素等價於版面（開發面在頁尾、不影響上方）。

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
#: DEC-134／DEC-137（手機抽屜）起：底部已無固定主導覽，53px 改為**底部保留帶**（Manage app／家的指示條可能遮擋區），
#: 量測線＝視窗高 − 53（844 → 791）**不變**；第一屏、導覽餘裕、頁底可達性一律以這條線判定（等價於舊「導覽上緣」）。
NAV_MOBILE_H = 53
#: 手機斷點（`src/ui2/shell/css.py` 的 `@media (max-width:768px)`）。
MOBILE_MAX_W = 768
#: 第一屏四問錨點（`src/ui2/components/html.py::first_screen_html` 的 `data-ui2-q`）。
FIRST_SCREEN_QS = ("q1", "q2", "q3", "q4")
#: 💼 持股（DEC-141 Q6）：「是否需要行動／下一步」合為「今日需處理」單行 → 沒有獨立 q3 錨點（其餘頁不變）。
HOLD_FIRST_SCREEN_QS = ("q1", "q2", "q4")
#: 頂部導覽第二列觸控目標下限（統一施工規格 §5；通用準則，非客戶裁示；DEC-146 沿用 ☰ 的 44px）。
NAV_TOUCH_MIN_PX = 44
NAV_LABELS = ("📊 市場", "🎯 標的", "💼 持股", "👤 我的", "🗂 資料")

#: 判定門檻與出處（⛔ 新門檻）。`id` 對應 `evaluate()` 的 check key。
THRESHOLDS: list[dict[str, str]] = [
    {"id": "first_screen_within_usable_height",
     "rule": "第一屏四問（① 現在狀態／② 是否需要行動／③ 下一步／④ 主 CTA）與頁面 context 列（Risk Cap 等）"
             "的元素底緣 ≤ 可用高：手機 = 844 − 底部導覽 53 = 791px；桌機 = 900px。",
     "source": "Freeze §16 視窗說明＋§0.1.6-2、Gate §3、Wireframes §0.4／§1／§8（px 數值出自 Freeze §16『可用高約 791px』）"},
    {"id": "first_screen_above_nav",
     "rule": "（DEC-146 頂部兩列導覽；取代舊『不與 ☰ 相交／桌機不入左 rail』）第一屏元素：手機底緣 ≤ 底部保留線（844 − 53 = 791）；"
             "手機與桌機頂緣 ≥ 頂部導覽底緣（不被固定在頂端的兩列導覽遮住）；主 CTA（q4）因此必在導覽之下、首屏之內＝可操作。",
     "source": "Wireframes §0.4（W-1）／Freeze §16；DEC-134（底部保留帶）；DEC-146（頂部兩列）"},
    {"id": "no_horizontal_scroll",
     "rule": "document／stMain 的 scrollWidth ≤ clientWidth（無水平捲動）；第一屏區塊內容不被橫向裁切；"
             "頂部第一列（Active Sheet｜模式標示｜帳號）不被裁切（scrollWidth ≤ clientWidth 且 scrollHeight ≤ clientHeight）。",
     "source": "Gate §3（Mobile-first）、Audit Checklist 手機項（客戶 (5)-9）；DEC-146（第一列併入標示，不得截斷）"},
    {"id": "nav_fixed_five_top",
     "rule": "（DEC-146；取代舊 nav_fixed_four）導覽恰 5 項（📊 市場／🎯 標的／💼 持股／👤 我的／🗂 資料）；全 DOM 恰 1 個頁面 radiogroup；恰一項為當前頁。"
             "手機與桌機同一份 DOM：fixed 於視窗頂端（top≈0、left≈0、寬＝視窗寬）、五項同一列、觸控目標高 ≥44px、"
             "⛔ ☰／遮罩／Drawer／左 rail／視窗底部固定主導覽。桌機＝五項全可見、無需捲動；"
             "手機＝第二列在自身容器內橫向捲動（overflow-x:auto/scroll），捲到最右後第 5 項（🗂 資料）完整進入視窗。",
     "source": "DEC-146（客戶核准頂部兩列五頁）；Wireframes §0.4／§7 W-1；NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE §2／§4"},
    {"id": "nav_current_marked_not_by_color_only",
     "rule": "當前頁除顏色外另有符號（`● ` 前綴 pseudo-element）與原生 radio `checked` 狀態。",
     "source": "Freeze §4.1（顏色不是唯一載體）"},
    {"id": "content_not_covered_by_nav",
     "rule": "捲到頁底後，最後一個內容元素底緣 ≤ 底部保留線 791（手機）／≤ 視窗高（桌機）；且捲到底後內容底緣不被頂部導覽遮蓋（導覽在頂端，故以底緣判定）。",
     "source": "Wireframes §0.4（導覽不得遮住主要內容）；DEC-146（導覽改頂部）"},
    {"id": "market_conclusion_in_first_screen",
     "rule": "📊 市場：今日結論列存在、位於第一屏（底緣 ≤ 可用高；與 ①～④ 同一條門檻）、且在 ① 市場目前狀態之上。",
     "source": "Freeze §0.1.6-5（四必要項＋今日結論同在第一屏）、Wireframes §2.1／§9、DEC-081 Q2-1／DEC-109"},
    {"id": "market_main_risk_follows_first_screen",
     "rule": "📊 市場：今日主要風險（L1）存在，手機位於第一屏四問之後且其後第一個內容區塊（卡片／摺疊）不早於它的底緣"
             "（⛔ 被 L2／L3 插隊）；桌機與 ①、Risk Cap 同列排成三 tile（頂緣差 ≤ 2px）。",
     "source": "Freeze §0.1.6-3（Q3-3）、Wireframes §2.1 手機／§2.2 桌機三 tile、DEC-117 Q1 桌機"},
    {"id": "market_cta_before_conclusion",
     "rule": "📊 市場：主更新 CTA（q4）在 DOM 與座標上都位於今日結論**之前**（CTA 底緣 ≤ 今日結論頂緣；手機與桌機皆然）。"
             "四問是資訊需求，不要求視覺順序 ①→④。",
     "source": "Wireframes §2.1／§2.2（頁首→更新 CTA→今日結論）、DEC-117 Q5、Freeze §16.1／§0.1.6；客戶 2026-11-03 裁示（DEC-127）"},
    {"id": "market_main_risk_nav_margin",
     "rule": "📊 市場（手機，FAKE 六場景）：今日主要風險之後第一個內容區塊的頂緣，距底部保留線 791（DEC-134 前＝底部導覽上緣）≥ 1 行內文行高"
             "（行高由頁內 `getComputedStyle(.ui2-risk).lineHeight` 現場量，⛔ 寫死 px）。"
             "**AI 總管內部判準（無條文給 px；客戶可推翻）**：餘裕不得小到下一區塊『剛好貼著導覽』而看不出頁面還有內容。",
     "source": "客戶 2026-11-03 裁示項 3（NUI2-MAIN-RISK-NAV-MARGIN）；判準本身＝AI 總管內部（Wireframes §0.4 導覽不得遮住主要內容為上位原則）"},
    {"id": "market_stress_reachable",
     "rule": "📊 市場（手機，壓力測試：L1 區內所有文字加長 1.5×，非改 production 常數）：捲到頁底後最後內容底緣 ≤ 導覽上緣、"
             "今日主要風險可整塊捲到導覽之上、無水平捲動、CTA 仍在今日結論之前。長字串只允許把內容往下推，不得被導覽遮住而捲不到。",
     "source": "Wireframes §0.4（導覽不得遮住主要內容）、Gate §3（Mobile-first）；客戶 2026-11-03 裁示項 3（長字串）"},
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
    {"id": "real_feed_banner_on_top",
     "rule": "Real-data Preview（`--feed real`）：頁首 banner 文字以 `REAL_PREVIEW_BANNER_TEXT`（Real-data Preview（非正式 "
             "production default））開頭、底緣 ≤ 頁面標題頂緣（在頁首）且 ≤ 可用高，且位於頂部第一列內、不被截斷（DEC-146 方案 A）。FAKE feed 不適用（恆通過）。"
             "另：👤 我的在 real 模式不讀帳戶（account＝None，路徑 C 擋）⇒ `me_account_state_first_screen` 改判"
             "『不得出現帳戶動作列（不假裝已登入／未登入）、主 CTA 仍在第一屏』。",
     "source": "客戶 (11) A3（Preview 明確標示 Real-data Preview／非正式 production default）；Freeze §16（可用高）"},
    {"id": "p1_human_text_clean",
     "rule": "（P1）產品畫面可見文字（排除 `?ui2_dev=1` 開發面、導覽 chrome、CSS）不含具名工程詞彙清單"
             "（`tests/test_ui2_p1_human_text.py::ENGINEERING_VOCAB`）、層級字樣（L1～L6）與可見題號「①②③④」；"
             "唯一放行：客戶要求的 Real-data 單行標示 `REAL_PREVIEW_BANNER_TEXT`。",
     "source": "客戶 2026-11-03 (16) P1 第 2 項；Active Presentation Contract §9／§11（題號與工程字樣）"},
    {"id": "p1_banner_single_line",
     "rule": "（P1／DEC-146）頂部標示（FAKE 示意資料／Real-data Preview）為單行且位於頂部導覽**第一列內**（DEC-146 方案 A）：banner 高度 ≤ 1 行行高 + 12px"
             "（行高由頁內 `getComputedStyle(.ui2-banner).lineHeight` 現場量）、文字不被截斷（scrollWidth ≤ clientWidth）、"
             "上下緣落在第一列（`.ui2-top1`）內、不超出視窗左右緣。",
     "source": "客戶 2026-11-03 (16) P1：Real banner『縮為單行』；手機窄螢幕折行 → 判紅"},
    {"id": "p3_no_evidence_expander",
     "rule": "（P3）四頁產品畫面（排除 `?ui2_dev=1` 開發面與導覽）實際渲染的 expander（DOM `stExpander`）標題，只准是 "
             "`src.ui2.views._page.SHOWN_FOLDS` 白名單內的使用者功能／稽核入口（🎯 選股條件；👤 Decision Digest／Rule Registry），"
             "且全部預設收合；📊／💼 必為 0 個。L2／L3 evidence expander（為什麼／指標明細／原始資料表／完整表／明細…）不得出現。",
     "source": "客戶 2026-11-03 (17) A2 第 1 項；Active Presentation Contract §3／§8"},
    {"id": "p2_onebrain_primary_slot_order",
     "rule": "（P2／Issue #1108 方向 B）📊 市場：DOM 與座標上依序為 今日主要風險 → 🇹🇼 台股日 K 主圖／空槽 → 核心指標卡 → 🤖 OneBrain Outlook（手機與桌機皆然；"
             "桌機另要求 OneBrain 在 是否需要行動／下一步 之後）。指標卡必須在 Primary **之後**、OneBrain 必須在指標卡**之後**（真瀏覽器 lane 的 VM 恆帶 OneBrain 區塊，缺＝判紅；缺席時不畫空框由 tests/test_ui2_p2_primary_slot.py 單元測試守）。"
             "空槽 0 個 svg／polyline／canvas／img（⛔ 假走勢）、含 `⬜ 尚未提供`、SPEC 行含『最新收盤參考』且不含『日頻』。",
     "source": "客戶 2026-11-04 (19) P2（G-1=A／G-2=B／G-3=A；OneBrain 位置段已由 DEC-157 取代）；Wireframes §2.1／§2.2；P2 文字線框 C 節；"
               "Issue #1108 方向 B（客戶截圖回饋＋『繼續』；DEC-157）"},
    {"id": "p2_nav_margin_160",
     "rule": "（P2）📊 市場（手機；stale／unavailable 場景，FAKE 與 Real）：今日主要風險之後第一個內容區塊頂緣距底部保留線 791"
             "（＝視窗高 − 53；DEC-134 前＝底部導覽上緣，同一條線）≥ 160px；"
             "不達須停手回報，不得縮字、刪資訊或改設計。",
     "source": "客戶 2026-11-04 (19)『導覽餘裕維持既有 ≥160px 的驗收門檻；未達就停止，不擅自更改設計』"},
    {"id": "kbar_primary_chart",
     "rule": "（Issue #1099 PR-2）📊 市場：Primary 位置恰一個區塊——誠實空槽（FAKE／無日 K 事實；照 p2 判定）或日 K 主圖"
             "（Real-data Preview），⛔ 兩者並存。日 K 主圖有 K 棒（OK／Stale）時：K 棒 1～20 根、svg 圖高約 220px"
             "（量測 200～240）、文字圖例逐字『紅｜收盤＞開盤　綠｜收盤＜開盤　灰｜收盤＝開盤』、不得含『MA』／『均線』／『成交量』、"
             "不得有紅色 danger chip；無 K 棒（灰／紅態）時 0 個 svg／K 棒，紅色 danger chip 只准出現在 unavailable 態。"
             "排序沿用 p2（Primary → 指標卡 → OneBrain；Issue #1108 方向 B）；水平捲動沿用 no_horizontal_scroll。",
     "source": "客戶 2026-11-09 裁示 DEC-156 A／B（K 色、手機預設最近 20 根、圖高約 220px）；Issue #1099 核准施工範圍（客戶授權轉述）；CLAUDE.md §1.A 第 4 點（灰紅分離）"},
    {"id": "w11_hold_layout",
     "rule": "（DEC-141 W-11 批 1）💼 持股：組合狀態行三段齊全且『資料日』段顯示 `⬜ 資料日未提供`、不被截斷；"
             "DOM／座標順序：桌機＝OneBrain → 〔Primary｜建議持股水位（市場端）〕同列並排 → 持股表；手機＝建議持股水位 → OneBrain → Primary → 持股表；"
             "Primary 空槽桌機高度 ≥ 240px、手機收成一行（高 ≤ 64px 且標題與 `⬜ 尚未提供` 同列）、0 個圖形元素、無紅色；"
             "持股表可見欄名桌機＝八欄（代碼／名稱／持股比例／成本／現價／報酬／策略／System Action）、手機＝四欄（代碼／名稱／報酬／System Action）+ 展開提示；"
             "0 個資料列（⛔ 假列）；欄名不被裁切。",
     "source": "客戶 2026-11-05 Q1~Q8（DEC-141）；Wireframes §4.2／W-6／W-11（客戶 Q3 核准）"},
    {"id": "no_title_overlap",
     "rule": "頁面標題不與 Preview banner、第一屏區塊、頂部導覽重疊（上下緣依序不交疊；DEC-146：標題頂緣 ≥ 導覽底緣）。",
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
    line = _nav_line(m)
    present = {e["q"] for e in m["elements"]}
    for q in (HOLD_FIRST_SCREEN_QS if m.get("page") == "p4_hold" else FIRST_SCREEN_QS):
        if q not in present:
            out["first_screen_within_usable_height"].append(f"缺第一屏錨點 {q}")
    for e in m["elements"]:
        if e["bottom"] > limit + 0.5:
            out["first_screen_within_usable_height"].append(
                f"{e['q']}（{e['text'][:12]}）底緣 y={e['bottom']:.0f} > 可用高 {limit}")
        if mobile and line is not None and e["bottom"] > line + 0.5:
            out["first_screen_above_nav"].append(f"{e['q']} 底緣 {e['bottom']:.0f} > 底部保留線 {line:.0f}")
        if nav.get("bottom") is not None and e["top"] < nav["bottom"] - 0.5:     # DEC-146：頂部導覽不得遮住第一屏（含主 CTA）
            out["first_screen_above_nav"].append(f"{e['q']} 頂緣 {e['top']:.0f} < 頂部導覽底緣 {nav['bottom']:.0f}（被導覽遮住）")
    h = m["hscroll"]
    for k in ("doc", "main"):
        if h[k]["scrollWidth"] > h[k]["clientWidth"] + 0.5:
            out["no_horizontal_scroll"].append(f"{k}: scrollWidth {h[k]['scrollWidth']} > clientWidth {h[k]['clientWidth']}")
    if h["qa_clipped"]:
        out["no_horizontal_scroll"].append("第一屏區塊內容被橫向裁切")
    if h.get("top1_clipped"):
        out["no_horizontal_scroll"].append("頂部第一列（Active Sheet｜模式標示｜帳號）被裁切")
    # 導覽（DEC-146：頂部兩列五頁）
    labels = nav["labels"]
    if tuple(labels) != NAV_LABELS:
        out["nav_fixed_five_top"].append(f"導覽項 {labels!r} ≠ 固定五頁 {NAV_LABELS!r}")
    if nav["position"] != "fixed":
        out["nav_fixed_five_top"].append(f"導覽 position={nav['position']!r}（應為 fixed）")
    tn = m.get("top_nav")
    if tn is None:
        out["nav_fixed_five_top"].append("量測缺 `top_nav` 鍵（radiogroup 數／☰ 殘留／捲動／第 5 項可達）")
        tn = {}
    else:
        if tn.get("page_radiogroups") != 1:
            out["nav_fixed_five_top"].append(f"頁面 radiogroup 數量 {tn.get('page_radiogroups')} ≠ 1（雙主導覽）")
        if tn.get("bottom_fixed_navs", 0):
            out["nav_fixed_five_top"].append(f"視窗底部出現 {tn['bottom_fixed_navs']} 個固定主導覽（導覽只在頂部）")
        if tn.get("drawer_dom", 0):
            out["nav_fixed_five_top"].append(f"殘留 ☰／遮罩／Drawer DOM {tn['drawer_dom']} 個（DEC-146 不留 Drawer）")
        if tn.get("rail_padding"):
            out["nav_fixed_five_top"].append("內容仍為左 rail 讓位（padding-left）")
        if not (abs(nav.get("top") or 0) <= 1 and abs(nav.get("left") or 0) <= 1 and abs((nav.get("width") or 0) - vw) <= 1):
            out["nav_fixed_five_top"].append(f"導覽未貼齊視窗頂端左右：top={nav.get('top')} left={nav.get('left')} width={nav.get('width')}")
        g = tn.get("group") or {}
        if not g:
            out["nav_fixed_five_top"].append("缺第二列容器量測")
        elif mobile:
            if g.get("overflow_x") not in ("auto", "scroll"):
                out["nav_fixed_five_top"].append(f"手機第二列不是自身容器內橫向捲動（overflow-x={g.get('overflow_x')!r}）")
            if g.get("last_right_after_scroll") is None or g["last_right_after_scroll"] > vw + 0.5 or g.get("last_left_after_scroll", 0) < -0.5:
                out["nav_fixed_five_top"].append(f"手機捲到最右後第 5 項未完整進入視窗：{g.get('last_left_after_scroll')}～{g.get('last_right_after_scroll')}")
        else:
            if g.get("scroll_w", 0) > g.get("client_w", 0) + 0.5 or g.get("last_right", 1e9) > vw + 0.5:
                out["nav_fixed_five_top"].append("桌機五項未全部可見（需捲動或超出視窗）")
    if len({round(t) for t in nav["label_tops"]}) != 1:
        out["nav_fixed_five_top"].append("五項應在同一列")
    if any(h_ < NAV_TOUCH_MIN_PX - 0.5 for h_ in nav.get("label_heights", [])):
        out["nav_fixed_five_top"].append(f"導覽觸控目標高 {nav.get('label_heights')} < {NAV_TOUCH_MIN_PX}px")
    if nav["checked_count"] != 1:
        out["nav_fixed_five_top"].append(f"當前頁（checked）數量 {nav['checked_count']} ≠ 1")
    marks = nav["marker_contents"]
    if [i for i, c in enumerate(marks) if "●" in c] != [nav["checked_index"]]:
        out["nav_current_marked_not_by_color_only"].append(f"當前頁符號標記與 checked 不一致：{marks!r}")
    # 導覽不遮內容
    last = m["last_content"]
    if mobile and line is not None and last["bottom"] > line + 0.5:
        out["content_not_covered_by_nav"].append(f"頁底內容 {last['bottom']:.0f} > 底部保留線 {line:.0f}")
    if not mobile and last["bottom"] > vh + 0.5:
        out["content_not_covered_by_nav"].append(f"桌機頁底內容底緣 {last['bottom']:.0f} > 視窗高 {vh}")
    se = m.get("scroll_end_bottom")        # 捲到底後 block-container 內容底緣（扣掉底部 padding）；舊 dict 無此鍵 → 略過
    if mobile and se is not None and line is not None and se > line + 0.5:
        out["content_not_covered_by_nav"].append(f"捲到底後內容底緣 {se:.0f} > 底部保留線 {line:.0f}")
    _evaluate_batch3(m, out, mobile, limit)
    if m.get("feed") == "real":
        rb = "real_feed_banner_on_top"
        bt, tt = m.get("banner_text"), m["title"]
        from shared.ui2_contract.text import REAL_PREVIEW_BANNER_TEXT
        if not bt or not bt.startswith(REAL_PREVIEW_BANNER_TEXT):
            out[rb].append(f"banner 文字 {bt!r} 不是 Real-data Preview 標示")
        elif tt["banner_bottom"] is None or tt["top"] is None or tt["banner_bottom"] > tt["top"] + 0.5:
            out[rb].append("banner 不在頁面標題之上")
        elif tt["banner_bottom"] > limit + 0.5:
            out[rb].append(f"banner 底緣 {tt['banner_bottom']:.0f} > 可用高 {limit}")
        bbx = m.get("banner_box") or {}
        if bbx.get("row_top") is not None and not (bbx["top"] >= bbx["row_top"] - 0.5 and bbx["bottom"] <= bbx["row_bottom"] + 0.5):
            out[rb].append("Real 標示不在頂部第一列內（DEC-146 方案 A：標示併入第一列）")
        if bbx.get("clipped"):
            out[rb].append("Real 標示被截斷（必要揭露不得消失）")
    # 標題不重疊
    t = m["title"]
    if t["banner_bottom"] is not None and t["top"] < t["banner_bottom"] - 0.5:
        out["no_title_overlap"].append("標題與 banner 重疊")
    if t["qa_top"] is not None and t["qa_top"] < t["bottom"] - 0.5:
        out["no_title_overlap"].append("標題與第一屏區塊重疊")
    if nav.get("bottom") is not None and t["top"] is not None and t["top"] < nav["bottom"] - 0.5:
        out["no_title_overlap"].append(f"標題頂緣 {t['top']:.0f} 被頂部導覽（底緣 {nav['bottom']:.0f}）遮住")
    _evaluate_p1(m, out)
    _evaluate_p2(m, out)
    _evaluate_h1(m, out)
    _evaluate_p3(m, out)
    return out


def _nav_line(m: dict) -> float | None:
    """底部保留線（DEC-146 後的『首屏可操作空間』下界）：手機＝視窗高 − 底部保留帶 53（Manage app／家的指示條可能遮擋區；數值與
    DEC-134／DEC-137 的 791 相同，故與歷史值可比）；桌機＝無底部保留帶 → None 以外回傳導覽 top（僅供舊呼叫相容，桌機判定不用它）。
    ⚠️ DEC-146 起導覽在頂部：`first_block_after_l1_top`（今日主要風險之後第一區塊頂緣）已**自然包含**頂部兩列導覽＋標示列的高度，
    因此 `p2_nav_margin_160` ＝『頂部導覽之下、底部保留線之上，第一個後續內容區塊以下還剩多少可操作空間』——
    與舊值同公式同單位，**可直接比較**（舊 162.5／現值見 evidence），⛔ 因導覽移位而放寬門檻或改量測基準。"""
    vp = m.get("viewport")
    if vp is None:                      # 舊版／合成 dict（無 viewport）：沿用導覽 top
        return m["nav"].get("top")
    if vp["w"] <= MOBILE_MAX_W:
        return float(vp["h"] - NAV_MOBILE_H)
    return m["nav"].get("top")


def _intersects(a: dict, b: dict) -> bool:
    return a["left"] < b["right"] - 0.5 and b["left"] < a["right"] - 0.5 and a["top"] < b["bottom"] - 0.5 and b["top"] < a["bottom"] - 0.5


P2_NAV_MARGIN_MIN_PX = 160
P2_NAV_MARGIN_SCENARIOS = ("stale", "unavailable")


#: 日 K 主圖判定常數（判定器自己的字面值，獨立於被測的 `src/ui2/components/html.py`，避免 mutation 時判定器跟著被改）。
KBAR_LEGEND_TEXT = "紅｜收盤＞開盤　綠｜收盤＜開盤　灰｜收盤＝開盤"
KBAR_MAX_BARS = 20
KBAR_PLOT_H_RANGE = (200.0, 240.0)
_KBAR_FORBIDDEN = ("MA", "均線", "成交量")


def _evaluate_kbar(p2: dict, out: dict[str, list[str]]) -> None:
    """Issue #1099 PR-2：日 K 主圖（`p2['chart']` 有值才判；FAKE／無日 K 事實 → 只需不與空槽並存）。"""
    k = "kbar_primary_chart"
    chart = p2.get("chart")
    if chart and p2.get("slot"):
        out[k].append("誠實空槽與日 K 主圖同時出現（Primary 位置只能有一個）")
    if not chart:
        return
    state, bars = p2.get("chart_state"), int(p2.get("chart_bars") or 0)
    text = p2.get("chart_text") or ""
    for w in _KBAR_FORBIDDEN:
        if w in text:
            out[k].append(f"日 K 主圖出現未核准字樣 {w!r}")
    if state in ("ok", "stale"):
        if not (1 <= bars <= KBAR_MAX_BARS):
            out[k].append(f"K 棒 {bars} 根（應 1～{KBAR_MAX_BARS}）")
        h = p2.get("chart_svg_h")
        if h is None or not (KBAR_PLOT_H_RANGE[0] <= h <= KBAR_PLOT_H_RANGE[1]):
            out[k].append(f"日 K 圖高 {h}（應約 220，量測 {KBAR_PLOT_H_RANGE[0]:.0f}～{KBAR_PLOT_H_RANGE[1]:.0f}）")
        if (p2.get("chart_legend") or "") != KBAR_LEGEND_TEXT:
            out[k].append(f"文字圖例不符：{p2.get('chart_legend')!r}")
        if p2.get("chart_danger", 0):
            out[k].append("有 K 棒卻出現紅色 danger chip")
    else:
        if bars or p2.get("chart_graphics", 0):
            out[k].append(f"{state} 態不得有圖形（K 棒 {bars}、圖形 {p2.get('chart_graphics')}）")
        if state != "unavailable" and p2.get("chart_danger", 0):
            out[k].append(f"{state} 態出現紅色 danger chip（紅只給系統真錯誤）")


def _evaluate_p2(m: dict, out: dict[str, list[str]]) -> None:
    """P2：OneBrain／Primary 空槽順序與誠實性、手機導覽餘裕 ≥160px。僅 📊 市場頁；缺 `p2` 鍵的舊 dict／其他頁略過；
    真瀏覽器 market 量測缺 `p2` 鍵＝判紅。"""
    if m.get("page") != "p4_market":
        return
    k, k2 = "p2_onebrain_primary_slot_order", "p2_nav_margin_160"
    p2 = m.get("p2")
    if p2 is None:
        out[k].append("p4_market 量測缺 `p2` 鍵（真瀏覽器 lane 必須量 OneBrain／空槽）")
        return
    mobile = m["viewport"]["w"] <= MOBILE_MAX_W
    ob, slot, grid, risk = p2.get("onebrain"), p2.get("slot"), p2.get("grid"), m.get("risk")
    chart = p2.get("chart")                       # Issue #1099 PR-2：日 K 主圖（只在 Real-data Preview 有日 K 事實時）
    els = {e["q"]: e for e in m["elements"]}
    if not ob:
        out[k].append("缺 🤖 OneBrain Outlook 區塊")
    if not slot and not chart:
        out[k].append("缺 🇹🇼 台股趨勢空槽")
    _evaluate_kbar(p2, out)
    if not slot and chart:                        # 日 K 主圖取代空槽：順序判定改用主圖座標（判定式不變）
        slot = chart
    if not grid:
        out[k].append("缺核心指標卡 grid")
    if ob and risk and ob["top"] < risk["bottom"] - 0.5:
        out[k].append(f"OneBrain top {ob['top']:.0f} 早於今日主要風險底緣 {risk['bottom']:.0f}")
    if ob and not mobile:
        for q in ("q2", "q3"):
            if q in els and ob["top"] < els[q]["bottom"] - 0.5:
                out[k].append(f"桌機：OneBrain top {ob['top']:.0f} 早於 {q} 底緣 {els[q]['bottom']:.0f}")
    if ob and slot and ob["top"] < slot["bottom"] - 0.5:
        out[k].append(f"OneBrain top {ob['top']:.0f} 早於 Primary（空槽／日 K）底緣 {slot['bottom']:.0f}（方向 B：OneBrain 在 Primary 之後）")
    if ob and grid and ob["top"] < grid["bottom"] - 0.5:
        out[k].append(f"OneBrain top {ob['top']:.0f} 早於核心指標卡底緣 {grid['bottom']:.0f}（方向 B：OneBrain 在指標卡之後）")
    if slot and risk and slot["top"] < risk["bottom"] - 0.5:
        out[k].append(f"Primary top {slot['top']:.0f} 早於今日主要風險底緣 {risk['bottom']:.0f}")
    if slot and grid and grid["top"] < slot["bottom"] - 0.5:
        out[k].append(f"指標卡 top {grid['top']:.0f} 早於空槽底緣 {slot['bottom']:.0f}（{'手機' if mobile else '桌機'}指標卡必須在空槽之後）")
    if slot and slot is not chart:
        if p2.get("slot_graphics", 0):
            out[k].append(f"空槽含 {p2['slot_graphics']} 個 svg／polyline／canvas／img（⛔ 假走勢）")
        t = p2.get("slot_text") or ""
        if "⬜ 尚未提供" not in t:
            out[k].append("空槽缺 `⬜ 尚未提供`")
        spec = p2.get("spec_text") or ""
        if not spec.startswith("SPEC｜") or "最新收盤參考" not in spec:
            out[k].append(f"SPEC 行缺或未標『最新收盤參考』：{spec!r}")
        if "日頻" in spec or "日頻" in t:
            out[k].append("SPEC 出現『日頻』（G-2=B：省略頻率欄）")
        if p2.get("slot_danger", 0):
            out[k].append("空槽出現紅色（danger）chip：Capability 空槽不得用紅")
    nb, ntop = m.get("first_block_after_l1_top"), _nav_line(m)
    if mobile and m.get("scenario") in P2_NAV_MARGIN_SCENARIOS and nb is not None and ntop is not None:
        if ntop - nb < P2_NAV_MARGIN_MIN_PX - 0.05:
            out[k2].append(f"手機 {m.get('scenario')}：導覽餘裕 {ntop - nb:.1f}px < {P2_NAV_MARGIN_MIN_PX}px")


#: DEC-141 W-11 批 1 判定常數（判定器自己的字面值，獨立於被測的 `shared/ui2_contract/text.py`，避免 mutation 時判定器跟著被改）。
H1_COLS_DESKTOP = ["代碼", "名稱", "持股比例", "成本", "現價", "報酬", "策略", "System Action"]
H1_COLS_MOBILE = ["代碼", "名稱", "報酬", "System Action"]
H1_PRIMARY_DESKTOP_MIN_PX = 240          # 桌機 Primary 預定高度（Q3；草稿 §2.1 估 220～260px）
H1_PRIMARY_MOBILE_MAX_PX = 64            # 手機一行：padding 12 + chip 行高；容許 1 行，不容許 2 行（≥ 80）


def _evaluate_h1(m: dict, out: dict[str, list[str]]) -> None:
    """DEC-141：💼 W-11 批 1 版面判定（僅 p4_hold；舊／合成 dict 無 `page` 或非 hold → 略過；hold 缺 `h1` 鍵＝判紅）。"""
    if m.get("page") != "p4_hold":
        return
    k = "w11_hold_layout"
    h1 = m.get("h1")
    if not h1:
        out[k].append("p4_hold 量測缺 `h1` 鍵（真瀏覽器 lane 必須量狀態行／Primary／建議持股水位／持股表）")
        return
    mobile = m["viewport"]["w"] <= MOBILE_MAX_W
    st, ob, pr, cap, tb = h1.get("status"), h1.get("onebrain"), h1.get("primary"), h1.get("cap"), h1.get("table")
    if not st:
        out[k].append("缺組合狀態行")
    else:
        segs = {s["seg"]: s for s in st["segs"]}
        if set(segs) != {"portfolio", "asof", "judged"}:
            out[k].append(f"狀態行段落 {sorted(segs)} ≠ portfolio／asof／judged")
        a = segs.get("asof")
        if a:
            if "⬜ 資料日未提供" not in a["text"]:
                out[k].append(f"資料日段不是 `⬜ 資料日未提供`：{a['text']!r}")
            if a["clipped"] or a["right"] > h1["vw"] + 0.5:
                out[k].append("資料日段被截斷或超出視窗右緣")
        if re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", " ".join(s["text"] for s in st["segs"])):
            out[k].append("狀態行出現日期（⛔ 今日／最舊一檔／抓取時間頂替）")
    for name, box in (("Primary 空槽", pr), ("建議持股水位空槽", cap), ("持股表", tb)):
        if not box:
            out[k].append(f"缺 {name}")
    if not (pr and cap and tb):
        return
    if pr["graphics"]:
        out[k].append(f"Primary 空槽含 {pr['graphics']} 個 svg／polyline／canvas／img（⛔ 假圖）")
    if pr["danger"] or cap["danger"]:
        out[k].append("空槽出現紅色 chip：Capability 空槽不得用紅")
    if "⬜ 尚未提供" not in pr["text"] or "⬜ 尚未提供" not in cap["text"]:
        out[k].append("Primary／建議持股水位空槽缺 `⬜ 尚未提供`")
    if tb["data_rows"]:
        out[k].append(f"持股表出現 {tb['data_rows']} 個資料列（⛔ 假列／假成本／假報酬）")
    want = H1_COLS_MOBILE if mobile else H1_COLS_DESKTOP
    got = [c["text"] for c in tb["th"]]
    if got != want:
        out[k].append(f"{'手機' if mobile else '桌機'}可見欄名 {got} ≠ {want}")
    if any(c["clipped"] for c in tb["th"]):
        out[k].append("持股表欄名被裁切")
    if mobile != tb["more_visible"]:
        out[k].append(f"每列展開提示可見性 {tb['more_visible']}（應僅手機可見）")
    if mobile:
        if pr["height"] > H1_PRIMARY_MOBILE_MAX_PX + 0.5:
            out[k].append(f"手機 Primary 空槽高 {pr['height']:.0f}px > {H1_PRIMARY_MOBILE_MAX_PX}px（未收成一行）")
        if pr.get("title_cy") is None or pr.get("chip_cy") is None or abs(pr["title_cy"] - pr["chip_cy"]) > 8:
            out[k].append("手機 Primary 標題與 `⬜ 尚未提供` 不同列")
        seq = [("建議持股水位", cap)] + ([("OneBrain", ob)] if ob else []) + [("Primary", pr), ("持股表", tb)]
        for (an, a_), (bn, b_) in zip(seq, seq[1:]):
            if b_["top"] < a_["bottom"] - 0.5:
                out[k].append(f"手機順序錯：{bn} top {b_['top']:.0f} 早於 {an} 底緣 {a_['bottom']:.0f}")
    else:
        if pr["height"] < H1_PRIMARY_DESKTOP_MIN_PX - 0.5:
            out[k].append(f"桌機 Primary 空槽高 {pr['height']:.0f}px < 預定高度 {H1_PRIMARY_DESKTOP_MIN_PX}px")
        if abs(pr["top"] - cap["top"]) > 2 or pr["right"] > cap["left"] + 0.5:
            out[k].append("桌機 Primary 與建議持股水位未並排同列")
        if ob and pr["top"] < ob["bottom"] - 0.5:
            out[k].append("桌機 Primary 早於 OneBrain 底緣")
        if tb["top"] < max(pr["bottom"], cap["bottom"]) - 0.5:
            out[k].append("桌機持股表未在 Primary／建議持股水位之下")


def _evaluate_p1(m: dict, out: dict[str, list[str]]) -> None:
    """P1 兩條判定（可單獨測試）：產品畫面可見文字乾淨、頂部標示單行。舊版量測 dict 無對應鍵 → 略過（向下相容）。"""
    pt = m.get("product_text")                      # 舊版量測 dict 無此鍵 → 略過（向下相容）
    if pt is not None:
        from tests.test_ui2_p1_human_text import hits_in
        h = hits_in(pt)
        if h:
            out["p1_human_text_clean"].append(f"產品畫面可見文字含工程詞彙／題號／層級字樣：{h}")
    bb = m.get("banner_box")
    if bb:
        if bb["height"] > bb["lineHeight"] + 12.5:
            out["p1_banner_single_line"].append(f"banner 高 {bb['height']:.0f}px > 1 行（行高 {bb['lineHeight']:.0f}+12）：折行")
        if bb.get("clipped"):
            out["p1_banner_single_line"].append("banner 文字被截斷（scrollWidth > clientWidth）")
        if bb.get("row_top") is not None and not (bb["top"] >= bb["row_top"] - 0.5 and bb["bottom"] <= bb["row_bottom"] + 0.5):
            out["p1_banner_single_line"].append(
                f"banner（top {bb['top']:.0f}～{bb['bottom']:.0f}）不在頂部第一列內（{bb['row_top']:.0f}～{bb['row_bottom']:.0f}）")
        if bb.get("right") is not None and (bb["right"] > m["viewport"]["w"] + 0.5 or bb["left"] < -0.5):
            out["p1_banner_single_line"].append("banner 超出視窗左右緣")
    elif m.get("page") is not None and m.get("banner_text"):
        out["p1_banner_single_line"].append("有 banner 文字但缺 `banner_box` 量測")


#: 判定器自己的允許標題常數（獨立於被測的 `src.ui2.views._page.SHOWN_FOLDS`，避免 mutation 時判定器跟著被改；
#: 與 pytest 的 `EXPECTED_SHOWN_FOLDS` 對照一致性由 tests/test_ui2_p3_evidence_preservation.py 的單元測試守）。
P3_ALLOWED_EXPANDER_TITLES: dict[str, frozenset[str]] = {
    "p4_market": frozenset(),
    "p4_hold": frozenset(),
    "p4_data": frozenset(),         # DEC-146：🗂 資料頁不渲染任何 expander
    "p4_target": frozenset({"選股條件（收合）"}),
    "p4_me": frozenset({"Audit：Decision Digest", "Audit：Rule Registry（唯讀）"}),
}


def _evaluate_p3(m: dict, out: dict[str, list[str]]) -> None:
    """P3：產品畫面不得渲染 L2／L3 evidence expander。
    真瀏覽器量測 dict（帶 `page` 鍵）**必須**有 `expanders` 鍵——缺＝判紅（不得因量測漏掉而放行）；
    不帶 `page` 的純合成／舊版 dict（既有單元測試用）略過。"""
    page = m.get("page")
    if page is None:
        return
    ex = m.get("expanders")
    if ex is None:
        out["p3_no_evidence_expander"].append(f"{page} 量測缺 `expanders` 鍵（真瀏覽器 lane 必須量 expander）")
        return
    allowed = P3_ALLOWED_EXPANDER_TITLES.get(page, frozenset())
    for e in ex:
        # Streamlit 的展開箭頭是圖示字型 ligature（innerText 帶 `keyboard_arrow_right ` 前綴）→ 剝掉再比
        title = re.sub(r"^(?:keyboard_arrow_\w+|expand_\w+|arrow_\w+)\s+", "", e["title"])
        if title not in allowed:
            out["p3_no_evidence_expander"].append(f"{page} 渲染了不在白名單內的 expander：{title!r}")
        if e.get("open"):
            out["p3_no_evidence_expander"].append(f"{page} expander {title!r} 預設不是收合")


def evaluate_stress(m: dict) -> dict[str, list[str]]:
    """壓力測試態（手機）：只判『長字串不得讓內容被導覽遮住、捲不到』。⛔ 不套第一屏高度（長字串本來就會往下推）。"""
    k = "market_stress_reachable"
    out: dict[str, list[str]] = {k: []}
    ntop = _nav_line(m)
    se = m.get("scroll_end_bottom")
    if se is None or ntop is None:
        out[k].append("缺 scroll_end_bottom／導覽")
        return out
    if se > ntop + 0.5:
        out[k].append(f"捲到底後內容底緣 {se:.0f} > 導覽上緣 {ntop:.0f}（被遮住）")
    rb = m.get("risk_bottom_at_scroll_end")
    if rb is None or rb > ntop + 0.5:
        out[k].append(f"捲到底後今日主要風險底緣 {rb} 仍在導覽之下（捲不出來）")
    for kk in ("doc", "main"):
        if m["hscroll"][kk]["scrollWidth"] > m["hscroll"][kk]["clientWidth"] + 0.5:
            out[k].append(f"出現水平捲動（{kk}）")
    els = {e["q"]: e for e in m["elements"]}
    if "q4" not in els or "concl" not in els or els["q4"]["bottom"] > els["concl"]["top"] + 0.5:
        out[k].append("壓力下 CTA 不在今日結論之前")
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
        c2 = "market_cta_before_conclusion"
        if "q4" not in els or "concl" not in els:
            out[c2].append("缺主 CTA 或今日結論")
        elif els["q4"]["bottom"] > els["concl"]["top"] + 0.5:
            out[c2].append(f"主 CTA 底緣 {els['q4']['bottom']:.0f} > 今日結論頂緣 {els['concl']['top']:.0f}（CTA 不在結論之前）")
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
            mg = "market_main_risk_nav_margin"
            lh, ntop = m.get("risk_line_height"), _nav_line(m)
            if mobile and nb is not None and lh is not None and ntop is not None and ntop - nb < lh - 0.5:
                out[mg].append(f"手機：今日主要風險後第一區塊 top {nb:.1f} 距導覽上緣 {ntop:.0f} 僅 {ntop - nb:.1f}px < 1 行行高 {lh:.1f}px")
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
    elif page == "p4_me" and m.get("feed") == "real":
        k = "me_account_state_first_screen"
        if m.get("account"):
            out[k].append("Real-data Preview 不讀帳戶，卻出現帳戶動作列（不得假裝已知帳戶狀態）")
        q4 = els.get("q4")
        if q4 is None or q4["bottom"] > limit + 0.5:
            out[k].append(f"主 CTA 不在第一屏：{q4['bottom'] if q4 else None}")
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
  // DEC-146 頂部導覽：頁面 radiogroup 數（全 DOM，以五頁 label 判定）、視窗底部固定主導覽數、☰／Drawer 殘留、第二列捲動與第 5 項可達
  const PAGE_LABELS = ['📊 市場', '🎯 標的', '💼 持股', '👤 我的', '🗂 資料'];
  const pageGroups = [...document.querySelectorAll('[role="radiogroup"]')].filter(g => [...g.querySelectorAll('label')].some(l => PAGE_LABELS.includes(l.textContent.trim())));
  const bottomFixed = pageGroups.filter(g => { const r = R(g); let e = g, fx = false; while (e && e !== document.body) { if (getComputedStyle(e).position === 'fixed') { fx = true; break; } e = e.parentElement; }
    return fx && r.bottom >= innerHeight - 1 && r.right > 0 && r.left < innerWidth && r.top < innerHeight && getComputedStyle(g).visibility === 'visible'; }).length;
  const checkedIdx = labels.findIndex(l => l.querySelector('input').checked);
  const grpEl = nav ? nav.querySelector('[role="radiogroup"]') : null;
  let topGroup = null;
  if (grpEl && labels.length) {
    const lastL = labels[labels.length - 1]; const gs = getComputedStyle(grpEl);
    const before = grpEl.scrollLeft; const lr0 = R(lastL);
    grpEl.scrollLeft = grpEl.scrollWidth; const lr1 = R(lastL); grpEl.scrollLeft = before;      // 量完還原
    topGroup = {overflow_x: gs.overflowX, scroll_w: grpEl.scrollWidth, client_w: grpEl.clientWidth, last_right: lr0.right,
                last_left_after_scroll: lr1.left, last_right_after_scroll: lr1.right};
  }
  const row1El = document.querySelector('.ui2-top1');
  const elements = [...document.querySelectorAll('[data-ui2-q]')].map(e => ({q: e.dataset.ui2Q, text: e.innerText.replace(/\s+/g,' ').trim(), ...R(e)}));
  const qa = document.querySelector('.ui2-m-l1') || document.querySelector('.ui2-qa');
  const title = document.querySelector('.ui2-pagetitle');
  const banner = document.querySelector('.ui2-banner');
  const sc = el => ({scrollWidth: el.scrollWidth, clientWidth: el.clientWidth});
  // 頁底內容：捲到底後最後一個 ui2 產品內容元素（P1 起 Preview 控制在 `?ui2_dev=1` 開發面，不算產品內容 → 排除）
  const prev = main.scrollTop; main.scrollTo({top: main.scrollHeight, behavior: 'instant'});
  const blocks = [...document.querySelectorAll('.stMainBlockContainer [data-testid="stElementContainer"], .block-container [data-testid="stElementContainer"]')]
    .filter(e => R(e).height > 1 && (!e.checkVisibility || e.checkVisibility()) && (!nav || (!nav.contains(e) && !e.contains(nav))) && !e.closest('.st-key-ui2_dev_surface'));   // 排除導覽本身與其 0 高的外層包裝、開發面
  const lastEl = blocks.length ? blocks[blocks.length-1] : null;
  const last = lastEl ? R(lastEl) : {bottom:0,left:0};
  // 捲到底後的真實內容底緣（block-container 底緣扣掉底部 padding＝保留量之上）與今日主要風險位置
  const bc = document.querySelector('.block-container');
  const scrollEndBottom = bc ? R(bc).bottom - parseFloat(getComputedStyle(bc).paddingBottom) : null;
  const riskAtEnd = document.querySelector('.ui2-risk');
  const riskBottomAtEnd = riskAtEnd ? R(riskAtEnd).bottom : null;
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
  // P1：產品畫面可見文字（排除開發面、導覽、<style>）——供 p1_human_text_clean 判定
  const bcEl = document.querySelector('.block-container') || document.body;
  const clone = bcEl.cloneNode(true);
  clone.querySelectorAll('.st-key-ui2_dev_surface, .st-key-ui2_nav, style, script').forEach(e => e.remove());
  const productText = (clone.textContent || '').replace(/\s+/g, ' ').trim();
  // P3：產品畫面實際渲染的 expander（DOM stExpander；排除開發面與導覽）
  const expanders = [...document.querySelectorAll('[data-testid="stExpander"]')]
    .filter(e => !e.closest('.st-key-ui2_dev_surface') && !e.closest('.st-key-ui2_nav'))
    .map(e => { const d = e.querySelector('details'); const sm = e.querySelector('summary');
      return {title: sm ? sm.innerText.replace(/\s+/g,' ').trim() : '', open: d ? d.open : null}; });
  // P2：OneBrain／台股 Primary 空槽／指標卡 grid 座標與空槽內容
  const obEl = document.querySelector('[data-ui2-l1="onebrain"]');
  const slotEl = document.querySelector('[data-ui2-l1="primary_slot"]');
  const chartEl = document.querySelector('[data-ui2-l1="primary_chart"]');
  const chartSvg = chartEl ? chartEl.querySelector('.ui2-kbar__svg') : null;
  const chartLeg = chartEl ? chartEl.querySelector('[data-ui2-kbar-legend]') : null;
  const gridEl = document.querySelector('.ui2-grid');
  const p2 = {onebrain: obEl ? R(obEl) : null, slot: slotEl ? R(slotEl) : null, grid: gridEl ? R(gridEl) : null,
    slot_graphics: slotEl ? slotEl.querySelectorAll('svg,polyline,canvas,img,[data-testid="stVegaLiteChart"]').length : 0,
    slot_text: slotEl ? slotEl.innerText.replace(/\s+/g,' ').trim() : null,
    spec_text: slotEl && slotEl.querySelector('[data-ui2-spec]') ? slotEl.querySelector('[data-ui2-spec]').innerText.replace(/\s+/g,' ').trim() : null,
    slot_danger: slotEl ? slotEl.querySelectorAll('.ui2-chip--danger').length : 0,
    chart: chartEl ? R(chartEl) : null, chart_state: chartEl ? chartEl.dataset.state : null,
    chart_bars: chartEl ? chartEl.querySelectorAll('[data-kbar-dir]').length : 0,
    chart_graphics: chartEl ? chartEl.querySelectorAll('svg,polyline,canvas,img,[data-testid="stVegaLiteChart"]').length : 0,
    chart_svg_h: chartSvg ? R(chartSvg).height : null,
    chart_legend: chartLeg ? chartLeg.textContent.trim() : null,
    chart_text: chartEl ? chartEl.innerText.replace(/\s+/g,' ').trim() : null,
    chart_danger: chartEl ? chartEl.querySelectorAll('.ui2-chip--danger').length : 0};
  // DEC-141：💼 W-11 批 1 座標與內容（僅 p4_hold 有）
  const hq = s => document.querySelector(s);
  const hStat = hq('[data-ui2-l1="hold_status"]'), hPrim = hq('[data-ui2-l1="hold_primary_slot"]'),
        hCap = hq('[data-ui2-l1="hold_cap_slot"]'), hTab = hq('[data-ui2-l1="hold_table"]'),
        hOb = hq('.ui2-h-ob'), hMore = hq('.ui2-ht__more');
  const vis = e => e && R(e).width > 1 && R(e).height > 1;
  const ctr = e => e ? (R(e).top + R(e).bottom) / 2 : null;
  const h1 = hStat || hPrim ? {
    vw: window.innerWidth,
    status: hStat ? {...R(hStat), segs: [...hStat.querySelectorAll('[data-seg]')].map(s => ({seg: s.dataset.seg,
      text: s.innerText.replace(/\s+/g,' ').trim(), left: R(s).left, right: R(s).right, clipped: s.scrollWidth > s.clientWidth + 1}))} : null,
    onebrain: hOb ? R(hOb) : null,
    primary: hPrim ? {...R(hPrim), graphics: hPrim.querySelectorAll('svg,polyline,canvas,img,[data-testid="stVegaLiteChart"]').length,
      danger: hPrim.querySelectorAll('.ui2-chip--danger').length, text: hPrim.innerText.replace(/\s+/g,' ').trim(),
      title_cy: ctr(hPrim.querySelector('.ui2-section-title')), chip_cy: ctr(hPrim.querySelector('.ui2-chip'))} : null,
    cap: hCap ? {...R(hCap), danger: hCap.querySelectorAll('.ui2-chip--danger').length, text: hCap.innerText.replace(/\s+/g,' ').trim()} : null,
    table: hTab ? {...R(hTab), data_rows: hTab.querySelectorAll('tbody tr, td').length, more_visible: vis(hMore),
      th: [...hTab.querySelectorAll('th')].filter(th => vis(th) && getComputedStyle(th).display !== 'none').map(th => ({
        text: th.innerText.trim(), left: R(th).left, right: R(th).right, clipped: th.scrollWidth > th.clientWidth + 1}))} : null,
  } : null;
  const bn = document.querySelector('.ui2-banner');
  const bannerBox = bn ? {height: R(bn).height, lineHeight: parseFloat(getComputedStyle(bn).lineHeight), fontSize: parseFloat(getComputedStyle(bn).fontSize),
    top: R(bn).top, bottom: R(bn).bottom, left: R(bn).left, right: R(bn).right, clipped: bn.scrollWidth > bn.clientWidth + 1,
    row_top: row1El ? R(row1El).top : null, row_bottom: row1El ? R(row1El).bottom : null} : null;
  const riskLH = riskEl ? parseFloat(getComputedStyle(riskEl).lineHeight) : null;
  return {
    page: pageEl ? pageEl.dataset.ui2Page : null,
    product_text: productText, banner_box: bannerBox, expanders: expanders, p2: p2, h1: h1,
    dev_surface_present: !!document.querySelector('.st-key-ui2_dev_surface'),
    banner_text: banner ? banner.innerText.replace(/\s+/g,' ').trim() : null,
    scroll_end_bottom: scrollEndBottom, risk_bottom_at_scroll_end: riskBottomAtEnd, risk_line_height: riskLH,
    risk: riskEl ? {...R(riskEl), inside_l1: !!(l1 && l1.contains(riskEl)), text: riskEl.innerText.replace(/\s+/g,' ').trim()} : null,
    first_block_after_l1_top: afterTops.length ? Math.min(...afterTops) : null,
    mode_box: modeBox ? {...R(modeBox), labels: modeLabels.map(l => l.innerText.trim()), checked_count: modeLabels.filter(l => l.querySelector('input').checked).length, checked_index: modeChecked} : null,
    mode_content: pageEl && pageEl.dataset.ui2Page === 'p4_target' ? {curated: !!document.querySelector('[data-ui2-mode-content="curated"]'), lookup: !!document.querySelector('[data-ui2-mode-content="lookup"]')} : null,
    font_sizes: {q1: fz('[data-ui2-q="q1"]'), ctx: fz('.ui2-ctxline')},
    account: accEl ? {...R(accEl), state: accEl.dataset.ui2Account} : null,
    snapshot_labels: snap,
    top_nav: {page_radiogroups: pageGroups.length, bottom_fixed_navs: bottomFixed, group: topGroup,
      drawer_dom: document.querySelectorAll('.ui2-dr-toggle, .ui2-dr-btn, .ui2-dr-scrim, .ui2-dr-wrap').length,
      rail_padding: parseFloat(getComputedStyle(document.querySelector('.block-container')).paddingLeft) > 150},
    nav: nr && {...nr, position: getComputedStyle(nav).position, visibility: getComputedStyle(nav).visibility,
      labels: labels.map(l => l.textContent.trim()),
      label_tops: labels.map(l => l.getBoundingClientRect().top), label_lefts: labels.map(l => l.getBoundingClientRect().left),
      label_heights: labels.map(l => l.getBoundingClientRect().height),
      checked_count: labels.filter(l => l.querySelector('input').checked).length, checked_index: checkedIdx,
      marker_contents: labels.map(l => { const p = l.querySelector('p'); return p ? getComputedStyle(p, '::before').content : ''; })},
    elements,
    hscroll: {doc: sc(document.documentElement), main: sc(main), qa_clipped: qa ? qa.scrollWidth > qa.clientWidth + 0.5 : false,
            top1_clipped: row1El ? (row1El.scrollWidth > row1El.clientWidth + 1 || row1El.scrollHeight > row1El.clientHeight + 1) : false},
    title: {top: title ? R(title).top : null, bottom: title ? R(title).bottom : null,
            banner_bottom: banner ? R(banner).bottom : null, qa_top: qa ? R(qa).top : null},
    last_content: {bottom: last.bottom, left: last.left},
    card_heights: [...document.querySelectorAll('.ui2-card')].slice(0,8).map(e => Math.round(R(e).height)),
  };
}
"""


#: 壓力測試：把 `.ui2-m-l1`（CTA／今日結論／四問／今日主要風險）內所有文字節點加長 1.5×（頁內 DOM 操作；⛔ 改 production 常數／VM）。
STRESS_FACTOR = 1.5
_STRESS_JS = """
(f) => {
  const root = document.querySelector('.ui2-m-l1'); if (!root) return 0;
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n, c = 0;
  while ((n = w.nextNode())) { const t = n.nodeValue; if (t.trim().length > 6) { n.nodeValue = t + t.slice(0, Math.ceil(t.length * (f - 1))); c++; } }
  return c;
}
"""


def measure_state(page, vw: int, vh: int) -> dict:
    page.evaluate("(() => { const m = document.querySelector('[data-testid=\"stMain\"]'); if (m) m.scrollTo({top: 0, behavior: 'instant'}); })()")
    page.wait_for_timeout(150)
    data = page.evaluate(_JS)
    data["viewport"] = {"w": vw, "h": vh}
    return data


# ── 證據 meta（防沉默通過：測試規格 §2.5）──────────────────────────────────
def source_files(repo: Path) -> list[Path]:
    """`source_hash` 涵蓋的檔：`src/ui2/**/*.py`＋`app_ui2.py`＋本量測腳本（排序、排除 __pycache__）。"""
    files = sorted(p for p in (repo / "src" / "ui2").rglob("*.py") if "__pycache__" not in p.parts)
    return files + [repo / "app_ui2.py", repo / "tests" / "ui2_viewport" / "measure_viewport.py"]


def source_hash(repo: Path) -> str:
    """sha256(相對路徑＋NUL＋位元組內容（CRLF→LF）＋NUL …)；任何 UI2 原始碼或量測腳本變更 → 值改變 → 舊證據判過期。"""
    import hashlib
    h = hashlib.sha256()
    for f in source_files(repo):
        h.update(f.relative_to(repo).as_posix().encode() + b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def _git_dirs(repo: Path) -> tuple[Path, Path]:
    """(gitdir, commondir)。一般 clone：皆為 `repo/.git`；git worktree：`.git` 是寫著 `gitdir: <路徑>` 的檔，
    HEAD 在該 gitdir、分支 refs／packed-refs 在其 `commondir`（Issue #1099 PR-2：在 worktree 量測時 git_sha 不再讀成 None）。"""
    g = repo / ".git"
    if g.is_file():
        line = g.read_text(encoding="utf-8").strip()
        if line.startswith("gitdir:"):
            gd = Path(line.split(":", 1)[1].strip())
            gd = gd if gd.is_absolute() else (repo / gd)
            cf = gd / "commondir"
            if cf.exists():
                cd = Path(cf.read_text(encoding="utf-8").strip())
                return gd, (cd if cd.is_absolute() else (gd / cd))
            return gd, gd
    return g, g


def _git_head(repo: Path) -> str | None:
    """純 Python 讀 HEAD sha（不呼叫外部 git：test_zz_test_portability）；讀不到 → None（測試會判紅）。"""
    try:
        gd, cd = _git_dirs(repo)
        head = (gd / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref:"):
            return head
        ref = head.split(None, 1)[1]
        for base in (gd, cd):
            f = base / ref
            if f.exists():
                return f.read_text(encoding="utf-8").strip()
        for line in (cd / "packed-refs").read_text(encoding="utf-8").splitlines():
            if line.endswith(" " + ref):
                return line.split()[0]
    except Exception:
        pass
    return None


def evidence_meta(repo: Path, chromium_version: str | None) -> dict:
    import datetime
    sha = _git_head(repo)
    try:
        from importlib.metadata import version
        pw = version("playwright")
    except Exception:
        pw = None
    return {"git_sha": sha, "source_hash": source_hash(repo),
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "playwright_version": pw, "chromium_version": chromium_version}


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
            account: str | None = None, feed: str = "fake") -> dict:
    m = measure_state(page, vw, vh)
    m["scenario"] = scenario
    m["feed"] = feed
    checks = evaluate(m)
    rd = lambda d: {k: (round(v, 1) if isinstance(v, float) else v) for k, v in d.items()}
    rec = {"viewport_name": vp_name, "viewport": m["viewport"], "page": pid, "scenario": scenario,
           "mode": mode, "account": account, "feed": feed, "banner_text": m.get("banner_text"),
           "elements": [rd(e) for e in m["elements"]],
           "nav": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in m["nav"].items()
                   if k in ("top", "bottom", "left", "right", "width", "height", "position", "visibility", "labels",
                            "checked_index")},
           "top_nav": m.get("top_nav"), "banner_box": m.get("banner_box"),
           "hscroll": m["hscroll"], "title": {k: (round(v, 1) if v is not None else None) for k, v in m["title"].items()},
           "last_content_bottom": round(m["last_content"]["bottom"], 1),
           "card_heights": m["card_heights"], "expanders": m.get("expanders"),
           "p2": ({k: (rd(v) if isinstance(v, dict) else v) for k, v in m["p2"].items()} if m.get("p2") else None),
           "h1": m.get("h1"),
           "batch3": {"risk": rd(m["risk"]) if m.get("risk") else None,
                      "mode_box": rd(m["mode_box"]) if m.get("mode_box") else None,
                      "mode_content": m.get("mode_content"), "font_sizes": m.get("font_sizes"),
                      "account": rd(m["account"]) if m.get("account") else None,
                      "snapshot_labels": m.get("snapshot_labels"),
                      "first_block_after_l1_top": (round(m["first_block_after_l1_top"], 1)
                                                   if m.get("first_block_after_l1_top") is not None else None),
                      "risk_line_height": m.get("risk_line_height"),
                      "scroll_end_bottom": (round(m["scroll_end_bottom"], 1) if m.get("scroll_end_bottom") is not None else None),
                      "nav_margin_after_risk": (round(_nav_line(m) - m["first_block_after_l1_top"], 1)
                                                if m.get("first_block_after_l1_top") is not None
                                                and m["viewport"]["w"] <= MOBILE_MAX_W else None)},
           "failures": {k: v for k, v in checks.items() if v}, "pass": not any(checks.values())}
    return rec


def _record_stress(page, vp_name: str, vw: int, vh: int, scenario: str, feed: str = "fake") -> dict:
    """手機市場頁壓力測試態：L1 區文字 1.5×（頁內 DOM 操作）後量測可達性（`evaluate_stress`）。"""
    n = page.evaluate(_STRESS_JS, STRESS_FACTOR)
    page.wait_for_timeout(200)
    m = measure_state(page, vw, vh)
    checks = evaluate_stress(m)
    risk = m.get("risk") or {}
    return {"viewport_name": vp_name, "viewport": m["viewport"], "page": "p4_market", "scenario": scenario,
            "mode": "stress", "account": None, "feed": feed, "stress_factor": STRESS_FACTOR, "stressed_text_nodes": n,
            "elements": [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in e.items()} for e in m["elements"]],
            "nav": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in m["nav"].items()
                    if k in ("top", "bottom", "position")},
            "hscroll": m["hscroll"],
            "stress": {"risk_top": round(risk["top"], 1) if risk else None,
                       "risk_bottom": round(risk["bottom"], 1) if risk else None,
                       "scroll_end_bottom": round(m["scroll_end_bottom"], 1) if m.get("scroll_end_bottom") is not None else None,
                       "scroll_end_gap_to_nav": (round(_nav_line(m) - m["scroll_end_bottom"], 1)
                                                 if m.get("scroll_end_bottom") is not None else None),
                       "risk_bottom_at_scroll_end": (round(m["risk_bottom_at_scroll_end"], 1)
                                                     if m.get("risk_bottom_at_scroll_end") is not None else None)},
            "failures": {k: v for k, v in checks.items() if v}, "pass": not any(checks.values())}


def run_measurements(url: str, out: Path | None, shots: str = "all", server_python: str | None = None,
                     streamlit_version: str | None = None, feed: str = "fake") -> dict:
    from playwright.sync_api import sync_playwright

    if feed == "real":
        return _run_real(url, out, shots, server_python, streamlit_version)

    from shared.ui2_contract.pages import (
        ACCOUNT_SIGNED_IN, ACCOUNT_SIGNED_OUT, ACCOUNT_UNAVAILABLE, MODE_LABELS, MODE_LOOKUP,
        P4_ME, P4_MARKET, P4_TARGET, PAGE_LABELS, PAGE_IDS, SCENARIO_IDS, SCENARIO_LOADED,
    )
    from src.ui2.shell.app import _ACCOUNT_LABELS, _SCENARIO_LABELS

    results: list[dict] = []

    def shot(page, vp_name, pid, scenario, suffix=""):
        if out is not None and _want_shot(shots, vp_name, scenario):
            _screenshot(page, out / f"{vp_name}_{pid}_{scenario}{suffix}.png")

    with sync_playwright() as p:
        browser = launch_chromium(p)
        for vp_name, (vw, vh) in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": vw, "height": vh})
            page.goto(_dev_url(url))
            page.wait_for_selector(".ui2-qa", timeout=40000)
            nav_click = lambda pid: click_nav(page, PAGE_LABELS[pid])
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
                    if pid == P4_MARKET and vw <= MOBILE_MAX_W:       # 手機市場頁：長字串壓力測試（每場景；shot 之後才動 DOM）
                        results.append(_record_stress(page, vp_name, vw, vh, scenario))
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
        chromium_version = browser.version
        browser.close()
    summary = {"states": len(results), "passed": sum(r["pass"] for r in results),
               "failed": [f"{r['viewport_name']}/{r['page']}/{r['scenario']}/{r.get('mode')}/{r.get('account')}"
                          for r in results if not r["pass"]]}
    return {"meta": {"tool": "tests/ui2_viewport/measure_viewport.py", "streamlit_version": streamlit_version,
                     **evidence_meta(Path(__file__).resolve().parents[2], chromium_version),
                     "viewports": {k: list(v) for k, v in VIEWPORTS.items()}, "nav_mobile_h": NAV_MOBILE_H,
                     "thresholds": THRESHOLDS,
                     "note": "全部場景為 FAKE；量測值未四捨五入的原始 px 於 elements／nav；門檻不自創（見 thresholds.source）。"},
            "summary": summary, "results": results}


def _run_real(url: str, out: Path | None, shots: str, server_python: str | None,
              streamlit_version: str | None) -> dict:
    """Real-data Preview（NUI2-REAL-FEED A3）：每 viewport 四頁＋🎯 查一檔模式；手機市場頁加壓力態。"""
    from playwright.sync_api import sync_playwright

    from shared.ui2_contract.pages import (
        FEED_REAL, MODE_LABELS, MODE_LOOKUP, P4_MARKET, P4_TARGET, PAGE_LABELS, PAGE_IDS, SCENARIO_REAL,
    )
    from src.ui2.shell.app import _FEED_LABELS

    results: list[dict] = []
    with sync_playwright() as p:
        browser = launch_chromium(p)
        for vp_name, (vw, vh) in VIEWPORTS.items():
            page = browser.new_page(viewport={"width": vw, "height": vh})
            page.goto(_dev_url(url))
            page.wait_for_selector(".ui2-qa", timeout=40000)
            _select_box(page, "資料來源", _FEED_LABELS[FEED_REAL], f'[data-ui2-scenario="{SCENARIO_REAL}"]')
            for pid in PAGE_IDS:
                click_nav(page, PAGE_LABELS[pid])
                page.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-scenario="{SCENARIO_REAL}"]', timeout=30000)
                page.wait_for_timeout(300)
                results.append(_record(page, vp_name, vw, vh, pid, SCENARIO_REAL,
                                       mode="curated" if pid == P4_TARGET else None, feed="real"))
                if out is not None and shots != "none":
                    _screenshot(page, out / f"{vp_name}_{pid}_real.png")
                if pid == P4_MARKET and vw <= MOBILE_MAX_W:
                    results.append(_record_stress(page, vp_name, vw, vh, SCENARIO_REAL, feed="real"))
                if pid == P4_TARGET:
                    page.locator(".st-key-ui2_target_mode_box [role='radiogroup'] > label",
                                 has_text=MODE_LABELS[MODE_LOOKUP]).click()
                    page.wait_for_selector(f'[data-ui2-page="{pid}"][data-ui2-mode="{MODE_LOOKUP}"]', timeout=30000)
                    page.wait_for_timeout(300)
                    results.append(_record(page, vp_name, vw, vh, pid, SCENARIO_REAL, mode=MODE_LOOKUP, feed="real"))
                    if out is not None and shots != "none":
                        _screenshot(page, out / f"{vp_name}_{pid}_real_lookup.png")
            page.close()
        streamlit_version = streamlit_version or _streamlit_version(server_python)
        chromium_version = browser.version
        browser.close()
    summary = {"states": len(results), "passed": sum(r["pass"] for r in results),
               "failed": [f"{r['viewport_name']}/{r['page']}/{r['scenario']}/{r.get('mode')}"
                          for r in results if not r["pass"]]}
    return {"meta": {"tool": "tests/ui2_viewport/measure_viewport.py", "feed": "real",
                     **evidence_meta(Path(__file__).resolve().parents[2], chromium_version),
                     "streamlit_version": streamlit_version,
                     "viewports": {k: list(v) for k, v in VIEWPORTS.items()}, "nav_mobile_h": NAV_MOBILE_H,
                     "thresholds": THRESHOLDS,
                     "note": ("Real-data Preview（唯讀 feed）：只接台股加權指數與市場位階兩項真資料，其餘欄位 ⬜＋原因；"
                              "量測當下的真值會隨每日 cron 與本地狀態檔變動（證據為量測日快照）。")},
            "summary": summary, "results": results}


def click_nav(page, label: str) -> None:
    """點導覽項（DEC-146）：頂部導覽五項常駐（桌機全可見；手機必要時先捲入視野再點），⛔ 先開抽屜。"""
    loc = page.locator(".st-key-ui2_nav [role='radiogroup'] > label", has_text=label)
    loc.scroll_into_view_if_needed()
    loc.click()
    page.wait_for_timeout(250)


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


#: 截圖時是否保留開發面（預設隱藏＝截產品畫面）。`--keep-dev` 設為 True。
KEEP_DEV_IN_SHOTS = False


def _dev_url(url: str) -> str:
    """量測要切場景／帳戶／資料來源，所以一律以 `?ui2_dev=1` 開頁（開發面旗標；不是登入證據）。"""
    return url + ("&" if "?" in url else "?") + "ui2_dev=1"


def _screenshot(page, path) -> None:
    """截圖。預設暫時隱藏開發面（`.st-key-ui2_dev_surface`）→ 截到的是產品畫面；截完還原。"""
    if KEEP_DEV_IN_SHOTS:
        page.screenshot(path=str(path))
        return
    page.evaluate("() => { const e = document.querySelector('.st-key-ui2_dev_surface'); if (e) e.style.display = 'none'; }")
    try:
        page.screenshot(path=str(path))
    finally:
        page.evaluate("() => { const e = document.querySelector('.st-key-ui2_dev_surface'); if (e) e.style.display = ''; }")


def _select_box(page, name: str, option_label: str, anchor: str) -> None:
    """在開發面（`?ui2_dev=1`）名為 `name` 的 selectbox 選 `option_label`（⛔ 動 app 程式；純用 UI 操作）。"""
    page.wait_for_selector(".st-key-ui2_dev_surface [data-testid=\"stSelectbox\"]", timeout=15000)
    # 置中捲動：開發面在頁尾，只「捲到可見」會落在手機底部固定導覽之後（點擊被導覽攔截；1.56 實測）
    page.evaluate("() => document.querySelector('.st-key-ui2_dev_surface').scrollIntoView({block: 'center'})")
    page.wait_for_timeout(200)
    # 以 selectbox 的 label（開頭比對）定位，不靠 combobox 的 accessible name：Streamlit 1.56（BaseWeb）的 combobox 名稱含目前選中的值
    # （例「FAKE 場景（預設）」含「場景」）→ 會誤選到資料來源那一格。
    box = page.locator('.st-key-ui2_dev_surface [data-testid="stSelectbox"]',
                       has=page.locator("label", has_text=re.compile(rf"^\s*{re.escape(name)}"))).get_by_role("combobox")
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
    ap.add_argument("--keep-dev", action="store_true",
                    help="截圖保留 `?ui2_dev=1` 開發面（預設暫時隱藏，截產品畫面）")
    ap.add_argument("--feed", default="fake", choices=("fake", "real"),
                    help="real＝Real-data Preview（NUI2-REAL-FEED；唯讀 feed）")
    a = ap.parse_args()
    global KEEP_DEV_IN_SHOTS
    KEEP_DEV_IN_SHOTS = a.keep_dev
    repo = Path(__file__).resolve().parents[2]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    proc = None
    url = a.url
    if url is None:
        proc, url = start_server(repo, a.python or sys.executable)
    try:
        report = run_measurements(url, out, a.shots, a.python if proc is not None else None,
                                  a.streamlit_version if proc is None else None, feed=a.feed)
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
