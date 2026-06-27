"""shared/stock_buckets.py — 個股面板「分析桶」section SSOT (v18.307)

Bug 2(2026-06-27 user）：個股深度分析面板(`tab_stock.py` render_tab_stock)
內容散落、找不到。對標總經五桶(`shared/macro_buckets.py`)做法，本模組是個股
面板「section 桶」的**單一真相**：

    render_stock_toc_html()       ← 頂部目錄（一眼看全貌 + 錨點跳轉）
    section_header_html(key)      ← 各 section 漸層標題（5 處改走 SSOT，DRY）

【為何是 L0】純常數 + 純字串 builder，零 I/O、零 streamlit、零 L1+ 依賴
(§8.2 硬規則)。st.markdown 呼叫留在 L5 tab_stock(本模組不 import streamlit)。

【桶順序】對齊 render_tab_stock 由上而下實際渲染序，不做物理重排(PR-C 安全)；
籌碼目前實體位於「技術面」section 內(G. 近20日籌碼集中度)，TOC 標註其歸屬。
"""
from __future__ import annotations

# ── section 漸層標題用色（對齊既有 tab_stock inline header，避免視覺漂移）──
# TRAFFIC_GREEN 由 caller 傳入（避免 L0 import shared.colors 造成耦合；
# 此處 fundamental 用 hex 鏡像，drift test 守護）。
_FUNDAMENTAL_GREEN = "#22c55e"  # 對齊 shared.colors.TRAFFIC_GREEN（drift test 斷言相等）

# ════════════════════════════════════════════════════════════════
# section 桶 meta：順序鎖定 + emoji + 主色 + 副標（對齊由上而下閱讀序）
# ════════════════════════════════════════════════════════════════
# 順序鎖定 = render_tab_stock 由上而下實際 anchor 行序
# （chips 實體位於 tech section 內，anchor 行號介於 tech 與 fundamental 之間）
STOCK_SECTION_ORDER = ["entry", "tech", "chips", "fundamental", "financials", "ai"]

STOCK_SECTION_META = {
    "entry": {
        "emoji": "💰", "title": "建議價格 & 進出場區間", "color": "#f0883e",
        "sub": "停利停損 · 風報比 · 進場條件 · 倉位計算",
        "anchor": "sec-entry",
        "toc": "進出場",
    },
    "tech": {
        "emoji": "📈", "title": "技術面分析", "color": "#58a6ff",
        "sub": "健康度評分 · VCP波幅收縮 · K線技術圖 · 即時操作建議",
        "anchor": "sec-tech",
        "toc": "技術面",
    },
    "chips": {
        "emoji": "🧩", "title": "籌碼定位", "color": "#3aa2f5",
        "sub": "近20日外資+投信集中度 · 延續性 · 吸籌 / 倒貨訊號",
        "anchor": "sec-chips",
        "toc": "籌碼",
    },
    "fundamental": {
        "emoji": "📊", "title": "基本面分析", "color": _FUNDAMENTAL_GREEN,
        "sub": "357殖利率評價 · 財報領先指標 · 月營收趨勢 · 六大先行指標",
        "anchor": "sec-fundamental",
        "toc": "基本面",
    },
    "financials": {
        "emoji": "🏥", "title": "體檢表", "color": "#d2a8ff",
        "sub": "策略2 · 4力1棒子 · 現金流矩陣 · OPM護城河",
        "anchor": "sec-financials",
        "toc": "財報體檢",
    },
    "ai": {
        "emoji": "🤖", "title": "AI 首席顧問總結", "color": "#76e3ea",
        "sub": "技術面 · 三大法人 · 集保大戶籌碼 · 基本面 · 財報體檢 · 總經｜五維綜合評估",
        "anchor": "sec-ai",
        "toc": "AI 總結",
    },
}


def section_header_html(key: str, color_override: str | None = None) -> str:
    """產生單一 section 漸層標題 HTML（取代 tab_stock 5 處 inline 字串，DRY）。

    Args
    ----
    key: STOCK_SECTION_ORDER 之一
    color_override: 若 caller 想用 shared.colors 的實際常數（如 TRAFFIC_GREEN）
                    覆蓋 meta 內鏡像 hex，可傳入（避免色票漂移）。

    Returns
    -------
    str: <div> 漸層標題 HTML（含 anchor id，供 TOC 錨點跳轉）。
    缺 key → raise KeyError（§1 Fail Loud，不偽造空標題）。
    """
    meta = STOCK_SECTION_META[key]  # KeyError on bad key = Fail Loud
    color = color_override or meta["color"]
    return (
        f'<div id="{meta["anchor"]}" '
        f'style="margin:24px 0 8px;padding:8px 16px;'
        f'background:linear-gradient(90deg,{color}18,#0d1117);'
        f'border-left:4px solid {color};border-radius:0 6px 6px 0;">'
        f'<span style="font-size:15px;font-weight:900;color:{color};">'
        f'{meta["emoji"]} {meta["title"]}</span>'
        f'<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
        f'{meta["sub"]}</span></div>'
    )


def render_stock_toc_html() -> str:
    """產生頂部目錄 HTML（一排桶 chip，錨點跳轉到各 section）。

    Returns
    -------
    str: <div> 目錄列 HTML，依 STOCK_SECTION_ORDER 排列。
    """
    chips = []
    for key in STOCK_SECTION_ORDER:
        meta = STOCK_SECTION_META[key]
        chips.append(
            f'<a href="#{meta["anchor"]}" '
            f'style="text-decoration:none;display:inline-block;'
            f'margin:2px 4px;padding:4px 10px;border-radius:14px;'
            f'background:{meta["color"]}1f;border:1px solid {meta["color"]}55;'
            f'font-size:12px;font-weight:700;color:{meta["color"]};">'
            f'{meta["emoji"]} {meta["toc"]}</a>'
        )
    return (
        '<div style="margin:4px 0 12px;padding:8px 12px;'
        'background:#0d1117;border:1px solid #21262d;border-radius:8px;">'
        '<span style="font-size:11px;color:#8b949e;margin-right:6px;">📑 本頁目錄</span>'
        + "".join(chips)
        + '</div>'
    )
