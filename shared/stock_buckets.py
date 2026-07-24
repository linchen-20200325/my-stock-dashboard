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

# ── 桶結論燈號 emoji + 色（v18.337 user：每桶 Bar 上加「一句結論 + 燈號」）──
# 對齊 shared.colors.TRAFFIC_*；L0 不 import shared.colors（同 _FUNDAMENTAL_GREEN 鏡像慣例），
# 由 test_stock_buckets drift test 斷言相等，非腦補。
_LIGHT_EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⬜"}
_LIGHT_COLOR = {
    "green":  "#22c55e",   # TRAFFIC_GREEN
    "yellow": "#eab308",   # TRAFFIC_YELLOW
    "red":    "#ef4444",   # TRAFFIC_RED
    "gray":   "#8b949e",
}

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


def section_header_html(
    key: str,
    color_override: str | None = None,
    level: str | None = None,
    headline: str | None = None,
) -> str:
    """產生單一 section 漸層標題 HTML（取代 tab_stock 5 處 inline 字串，DRY）。

    Args
    ----
    key: STOCK_SECTION_ORDER 之一
    color_override: 若 caller 想用 shared.colors 的實際常數（如 TRAFFIC_GREEN）
                    覆蓋 meta 內鏡像 hex，可傳入（避免色票漂移）。
    level: 燈號 'green'|'yellow'|'red'|'gray'（v18.337）。給定時於 Bar 上加
           「🟢/🟡/🔴/⬜ + 一句結論」。None = 不顯示（向下相容，既有呼叫無感）。
    headline: 一句結論摘要（搭配 level 顯示）。level 給定但 headline 空 → 只顯示燈號。

    Returns
    -------
    str: <div> 漸層標題 HTML（含 anchor id，供 TOC 錨點跳轉）。
    缺 key → raise KeyError（§1 Fail Loud，不偽造空標題）。
    非法 level → 視為 'gray'（不偽綠，§1）。
    """
    meta = STOCK_SECTION_META[key]  # KeyError on bad key = Fail Loud
    color = color_override or meta["color"]
    # 桶結論：燈號 + 一句話（同一個 Bar 內第二行，user「結論直接放桶 Bar 上面」）
    _concl_html = ""
    if level is not None:
        _lv = level if level in _LIGHT_EMOJI else "gray"
        _lc = _LIGHT_COLOR[_lv]
        _head = (headline or "").strip()
        _head_html = (
            f'<span style="font-size:12px;font-weight:700;color:{_lc};'
            f'margin-left:6px;">{_head}</span>' if _head else ""
        )
        _concl_html = (
            f'<div style="margin-top:4px;">'
            f'<span style="font-size:13px;">{_LIGHT_EMOJI[_lv]}</span>'
            f'{_head_html}</div>'
        )
    return (
        f'<div id="{meta["anchor"]}" '
        f'style="margin:24px 0 8px;padding:8px 16px;'
        f'background:linear-gradient(90deg,{color}18,#0d1117);'
        f'border-left:4px solid {color};border-radius:0 6px 6px 0;">'
        f'<span style="font-size:15px;font-weight:900;color:{color};">'
        f'{meta["emoji"]} {meta["title"]}</span>'
        f'<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
        f'{meta["sub"]}</span>'
        f'{_concl_html}</div>'
    )


def compute_stock_section_levels(
    *,
    health: float | None = None,
    rs_val: float | None = None,
    chips_sig: str | None = None,
    chips_con: float | None = None,
    li_green: int | None = None,
    li_yellow: int | None = None,
    li_red: int | None = None,
) -> dict[str, dict]:
    """個股 6 section 桶結論燈號 + 一句話（v18.337，純函式，吃**已算好**的訊號）。

    user 2026-06-28：個股每桶 Bar 上加「一句結論 + 燈號」。本函式吃 tab_stock
    在資料載入後 compute-once 的訊號（health2 / _xsec rs_val·sig20·con20·li_*），
    回各 section 的 {level, headline}，供 section_header_html(level=, headline=)。

    門檻全走 SSOT（§3.3 反捏造）：
      - tech：HEALTH_GRADE_A_MIN(80) / HEALTH_GRADE_B_MIN(50)（shared.health_thresholds）
      - entry：STOCK_RS_STRONG_MIN(75) / STOCK_RS_NEUTRAL_MIN(50)（shared.signal_thresholds）
      - fundamental：六大先行指標「最差燈號」聚合（紅>黃>綠，同 macro aggregate_level）
      - chips：sig20 類別（吸籌/倒貨/中性）— 無數值門檻

    §1 Fail Loud：任何缺值 → gray「未算/待展開」，**不偽綠**。
    financials / ai 為 on-demand（資料在 section 內才抓），本函式一律回 gray + 提示
    「展開後評定」，避免用 top 不存在的值偽造（§4.3 不另起對照算法造成不一致）。

    Returns
    -------
    dict：{section_key: {"level": str, "headline": str}}，涵蓋全 6 個 section。
    """
    from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
    from shared.signal_thresholds import STOCK_RS_NEUTRAL_MIN, STOCK_RS_STRONG_MIN

    out: dict[str, dict] = {}

    # ── entry：RS 相對強度（進場就緒度 proxy）──
    if rs_val is None:
        out["entry"] = {"level": "gray", "headline": "進場訊號待算"}
    else:
        _rs = float(rs_val)
        if _rs >= STOCK_RS_STRONG_MIN:
            out["entry"] = {"level": "green", "headline": f"RS 相對強度 {_rs:.0f} 分 強勢"}
        elif _rs >= STOCK_RS_NEUTRAL_MIN:
            out["entry"] = {"level": "yellow", "headline": f"RS 相對強度 {_rs:.0f} 分 中性"}
        else:
            out["entry"] = {"level": "red", "headline": f"RS 相對強度 {_rs:.0f} 分 弱勢"}

    # ── tech：健康度評分（A/B/C）──
    if health is None:
        out["tech"] = {"level": "gray", "headline": "健康度待算"}
    else:
        _h = float(health)
        if _h >= HEALTH_GRADE_A_MIN:
            out["tech"] = {"level": "green", "headline": f"健康度 {_h:.0f} 分 體質強（A）"}
        elif _h >= HEALTH_GRADE_B_MIN:
            out["tech"] = {"level": "yellow", "headline": f"健康度 {_h:.0f} 分 中性（B）"}
        else:
            out["tech"] = {"level": "red", "headline": f"健康度 {_h:.0f} 分 偏弱（C）"}

    # ── chips：20 日籌碼訊號（吸籌/倒貨/中性）──
    if not chips_sig:
        out["chips"] = {"level": "gray", "headline": "籌碼訊號待算"}
    else:
        _con_txt = f"　集中度 {float(chips_con):.0f}%" if chips_con is not None else ""
        if "吸籌" in chips_sig:
            out["chips"] = {"level": "green", "headline": f"20 日吸籌{_con_txt}"}
        elif "倒貨" in chips_sig:
            out["chips"] = {"level": "red", "headline": f"20 日倒貨{_con_txt}"}
        else:
            out["chips"] = {"level": "yellow", "headline": f"20 日籌碼中性{_con_txt}"}

    # ── fundamental：六大先行指標燈號聚合（最差燈號）──
    if li_green is None and li_yellow is None and li_red is None:
        out["fundamental"] = {"level": "gray", "headline": "先行指標待算"}
    else:
        _g, _y, _r = int(li_green or 0), int(li_yellow or 0), int(li_red or 0)
        _lv = "red" if _r > 0 else ("yellow" if _y > 0 else "green")
        out["fundamental"] = {
            "level": _lv,
            "headline": f"六大先行指標 🟢{_g} 🟡{_y} 🔴{_r}",
        }

    # ── financials / ai：on-demand，於 section 內才抓 → gray 不偽造（§1）──
    out["financials"] = {"level": "gray", "headline": "展開下方體檢表後評定 MJ 等級"}
    out["ai"] = {"level": "gray", "headline": "點下方按鈕生成 AI 五維評估"}

    return out


# ── 個股頁頂「一眼判讀」綜合結論（v19.167，對稱 ETF 🚦 卡 / 組合排行 headline）──
_STOCK_VERDICT_KEYS = ("entry", "tech", "chips", "fundamental")


def summarize_stock_verdict(
    sec_lv: dict[str, dict],
    trend_label: str | None = None,
) -> dict:
    """個股頁頂『一眼判讀』單一綜合結論（純函式，吃 compute_stock_section_levels 輸出）。

    只聚合 4 個「頁頂即時可評定」的桶（entry RS / tech 健康 / chips 籌碼 /
    fundamental 先行指標）；financials / ai 為 on-demand gray → **不納入**
    （§1 不偽造：沒展開就沒有的東西不當綠也不當紅）。**零重算**：理由直接取
    各桶既有 headline，不另起演算法（§4.3 不製造第二套數字）。

    綜合規則（平衡讀，非 macro aggregate_level 的 worst-light 安全聚合）：
      - 有紅且紅 ≥ 綠 → red「訊號偏弱 · 保守」
      - 無紅且綠 > 黃  → green「多項轉強 · 偏多」
      - 其餘          → yellow「訊號分歧 · 觀望」
    可評定桶為 0（資料全未載）→ gray「資料待算」。

    Parameters
    ----------
    sec_lv : compute_stock_section_levels 的回傳 dict。
    trend_label : 頁頂 3-MA 趨勢燈（如「🟢 強勢多頭」）；僅作情境行透傳，
        **不併入 level**（趨勢是價格面、桶是結構面，分開較誠實）。

    Returns
    -------
    dict：{level, verdict, reasons(list[str]), counts(tuple g,y,r), n, trend_label}
    """
    evaluable = [
        sec_lv[k] for k in _STOCK_VERDICT_KEYS
        if isinstance(sec_lv.get(k), dict)
        and sec_lv[k].get("level") in ("green", "yellow", "red")
    ]
    g = sum(1 for b in evaluable if b["level"] == "green")
    y = sum(1 for b in evaluable if b["level"] == "yellow")
    r = sum(1 for b in evaluable if b["level"] == "red")
    n = len(evaluable)
    reasons = [b.get("headline", "") for b in evaluable if b.get("headline")]
    if n == 0:
        return {"level": "gray", "verdict": "資料待算", "reasons": [],
                "counts": (0, 0, 0), "n": 0, "trend_label": trend_label}
    if r > 0 and r >= g:
        level, verdict = "red", "訊號偏弱 · 保守"
    elif r == 0 and g > y:
        level, verdict = "green", "多項轉強 · 偏多"
    else:
        level, verdict = "yellow", "訊號分歧 · 觀望"
    return {"level": level, "verdict": verdict, "reasons": reasons,
            "counts": (g, y, r), "n": n, "trend_label": trend_label}


# ════════════════════════════════════════════════════════════════
# P/B 估值帶狀 SSOT(v18.326)— 個股 Tab + 組合 Tab 共用
# ════════════════════════════════════════════════════════════════
# 產業別 P/B 閾值對照表(低 / 中 / 高 — 三條河流圖橫帶界線)
PB_BANDS_FINANCIAL = (0.5, 0.9, 1.2)   # 金融保險業 / 銀行 — 資產驅動,PB<1 屬正常
PB_BANDS_GROWTH = (1.5, 2.5, 4.0)      # 半導體 / 電子 / 光電 / 通信 — 高 ROE 智財權溢價
PB_BANDS_MFG = (0.8, 1.5, 2.5)         # 製造業 default — 慣例值

_FINANCIAL_INDUSTRY_KEYWORDS = ('金融保險業', '銀行業', '證券業', '保險業', '金融業')
_GROWTH_INDUSTRY_KEYWORDS = (
    '半導體業', '電子工業', '光電業', '通信網路業',
    '電腦及週邊設備業', '其他電子業', '電子零組件業',
)


def get_pb_bands(industry: str | None) -> tuple[float, float, float]:
    """產業類別 → P/B 河流圖橫帶閾值(低 / 中 / 高)。"""
    if not industry:
        return PB_BANDS_MFG
    ind = str(industry)
    if any(kw in ind for kw in _FINANCIAL_INDUSTRY_KEYWORDS):
        return PB_BANDS_FINANCIAL
    if any(kw in ind for kw in _GROWTH_INDUSTRY_KEYWORDS):
        return PB_BANDS_GROWTH
    return PB_BANDS_MFG


def pb_bands_label(industry: str | None) -> str:
    """產業類別 → 標籤字串,供 UI caption 顯示。"""
    if not industry:
        return '製造業預設'
    ind = str(industry)
    if any(kw in ind for kw in _FINANCIAL_INDUSTRY_KEYWORDS):
        return f'金融業({ind})'
    if any(kw in ind for kw in _GROWTH_INDUSTRY_KEYWORDS):
        return f'成長科技({ind})'
    return f'製造業({ind})'


def classify_pb_level(pb_value: float, bands: tuple[float, float, float]) -> str:
    """把 P/B 值依產業別 bands 分為 便宜 / 合理 / 偏貴 / 超貴 燈號(供組合 Tab 列表顯示)。

    Args:
        pb_value: 當前 P/B(>0 才有效)
        bands: get_pb_bands(industry) 的回傳 (low, mid, high)

    Returns:
        '🟢 便宜' / '🟢 合理' / '🟡 偏貴' / '🔴 超貴' / '—'(無效值)
    """
    if pb_value is None or pb_value <= 0:
        return '—'
    low, mid, high = bands
    if pb_value < low:
        return '🟢 便宜'
    if pb_value < mid:
        return '🟢 合理'
    if pb_value < high:
        return '🟡 偏貴'
    return '🔴 超貴'


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
