"""shared/macro_buckets.py — 總經五桶 × 危險門檻 SSOT 註冊表 (v18.284)

CLAUDE.md §3.3 反捏造 / §8.2 L0 Infra：
本模組是「總經五桶」(長期/中期/短線急殺/籌碼/新聞) 危險門檻系統的**單一真相**，
同時被三個 surface 消費，避免閾值散落、漂移：

    compute_five_bucket_summary (L2 macro_helpers)  ← 桶燈號
    render_*_chart add_hline      (L5 tab_macro)     ← 圖表標準線
    SPEC.md §11 危險門檻表          (docs)            ← 參考文件

【為何是 L0】純常數 + 純 classify 函式，零 I/O、零 L1+ 依賴（§8.2 硬規則）。
macro_core.MACRO_THRESHOLDS 位於 L1，L0 不得 import → 重疊值在此鏡像並由
test_macro_buckets.py 斷言相等（drift-safe，CI 擋漂移），非無據腦補。

【門檻來源透明度】每條 DangerSpec.source 標註：
    "SSOT:<位置>"  → 有官方 / 既有常數背書（鏡像或 import）
    "DESIGN"       → 本桶系統設計之警示線（無單一官方源，為 UI 判讀方便而訂，
                     §1 不適用：此為 UI 門檻 config 非偽造資料輸出，已具名 + 文件化）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ── 既有 L0 SSOT 常數（直接 import，不重複宣告）──
from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,       # 3400 億：融資過熱紅線
    FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS,  # -10000 口：外資期貨黃線
    FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS,    # -20000 口：外資期貨紅線
)
from shared.colors import TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED

# ── 燈號 → 色 / emoji / 嚴重度排序（bar + chart + 詳細表共用）──
LEVEL_COLOR = {"green": TRAFFIC_GREEN, "yellow": TRAFFIC_YELLOW,
               "red": TRAFFIC_RED, "gray": "#6e7681"}
LEVEL_EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⬜"}
LEVEL_RANK = {"green": 1, "yellow": 2, "red": 3}   # gray 不參與 worst 計算

# ════════════════════════════════════════════════════════════════
# 鏡像 macro_core.MACRO_THRESHOLDS（L1，L0 不可 import）— drift test 守護
#   test_macro_buckets.py::test_mirror_matches_macro_core 斷言下列 == 源
# ════════════════════════════════════════════════════════════════
_VIX_YELLOW = 22.0   # 對齊 MACRO_THRESHOLDS['VIX']['yellow_above']
_VIX_RED    = 30.0   # 對齊 MACRO_THRESHOLDS['VIX']['red_above']
_CPI_YELLOW = 3.5    # 對齊 MACRO_THRESHOLDS['CPI']['yellow_above']
_CPI_RED    = 4.0    # 對齊 MACRO_THRESHOLDS['CPI']['red_above']
_PMI_YELLOW = 50.0   # 對齊 MACRO_THRESHOLDS['PMI']['yellow_below']（<50 收縮）
_PMI_RED    = 46.0   # 對齊 MACRO_THRESHOLDS['PMI']['red_below']（<46 嚴重收縮）
# v18.286 — 補入 SSOT 鏡像(原僅五桶用指標,本版加 10Y / DXY 給 sparkline 標準線用)
_US10Y_YELLOW = 4.5  # 對齊 MACRO_THRESHOLDS['US10Y']['yellow_above']
_US10Y_RED    = 5.0  # 對齊 MACRO_THRESHOLDS['US10Y']['red_above']
_DXY_YELLOW   = 105.0  # 對齊 MACRO_THRESHOLDS['DXY']['yellow_above']
_DXY_RED      = 110.0  # 對齊 MACRO_THRESHOLDS['DXY']['red_above']

# ════════════════════════════════════════════════════════════════
# 桶 meta：順序鎖定 + emoji + 副標（對齊下方詳細區由上而下閱讀序）
# ════════════════════════════════════════════════════════════════
BUCKET_ORDER = ["long", "mid", "short", "chips", "news"]
BUCKET_META = {
    "long":  {"emoji": "🌳", "title": "長期",   "sub": "結構 / 景氣位階"},
    "mid":   {"emoji": "📈", "title": "中期",   "sub": "景氣循環 3-12 月"},
    "short": {"emoji": "⚡", "title": "短線急殺", "sub": "即時 risk-off"},
    "chips": {"emoji": "🧩", "title": "籌碼",   "sub": "大戶定位 日線"},
    "news":  {"emoji": "📰", "title": "新聞",   "sub": "系統性風險掃描"},
}

# 各桶 × 燈號 → 狀態短語（bar 上的 1 句 label）
BUCKET_LEVEL_LABEL = {
    "long":  {"green": "結構健康", "yellow": "結構轉折", "red": "結構防禦", "gray": "未載入"},
    "mid":   {"green": "循環健康", "yellow": "局部走弱", "red": "循環惡化", "gray": "未載入"},
    "short": {"green": "短線平靜", "yellow": "短線警戒", "red": "急殺風險", "gray": "未載入"},
    "chips": {"green": "籌碼安定", "yellow": "籌碼分歧", "red": "籌碼危險", "gray": "未載入"},
    "news":  {"green": "無系統風險", "yellow": "風險新聞", "red": "系統性警報", "gray": "未掃描"},
}

# 新聞桶：系統性風險命中「則數」→ 燈號（DESIGN：UI 判讀規則，非金融閾值）
NEWS_SYSTEMIC_YELLOW_COUNT = 1   # ≥1 則系統性新聞 → 🟡
NEWS_SYSTEMIC_RED_COUNT    = 2   # ≥2 則系統性新聞 → 🔴

# macro 健康評分（0-100）危險線：red=DEFENSE 預設樓地板，yellow=過半警示
_HEALTH_RED    = 35.0   # SSOT:macro_helpers.HEALTH_DEFENSE_THRESHOLD 預設值（calibrated 可調 [20,60]）
_HEALTH_YELLOW = 50.0   # DESIGN：低於半分轉弱警示


@dataclass(frozen=True)
class DangerSpec:
    """單一指標的危險門檻規格。chart hline / 桶燈號 / SPEC 表共用。"""
    key: str               # 取值 key（session_state / dict 內）
    label: str             # 顯示名
    bucket: str            # long / mid / short / chips / news
    unit: str              # "", "%", "億", "口", "分", "則"
    direction: str         # high_bad | low_bad | band
    yellow: float          # 黃線（high_bad=上緣 / low_bad=下緣 / band=高側）
    red: float             # 紅線（同上）
    decimals: int = 1
    yellow_lo: Optional[float] = None   # band 低側黃線
    red_lo: Optional[float] = None      # band 低側紅線
    note: str = ""         # 業務語意（= SPEC 卡片註解）
    source: str = ""       # 門檻來源（SSOT:... 或 DESIGN）
    emoji: str = ""        # 指標小圖（v18.338 Fund 式卡片網格用；空 → 卡片 fallback 📊）


# ════════════════════════════════════════════════════════════════
# 危險門檻註冊表 — 五桶 × 指標
# ════════════════════════════════════════════════════════════════
BUCKET_DANGER_SPECS: list[DangerSpec] = [
    # ── 🌳 長期：結構 / 景氣位階 ──
    DangerSpec("health", "總經健康評分", "long", "", "low_bad",
               yellow=_HEALTH_YELLOW, red=_HEALTH_RED, decimals=0,
               note="<35 防禦 / <50 轉弱", source="SSOT:HEALTH_DEFENSE_THRESHOLD(35)+DESIGN(50)",
               emoji="🩺"),
    DangerSpec("ndc_signal", "NDC 景氣對策燈號", "long", "分", "band",
               yellow=32.0, red=38.0, yellow_lo=23.0, red_lo=16.0, decimals=0,
               note="9-16 藍衰退 / 23-31 綠穩定 / 38+ 紅過熱", source="DESIGN:NDC 燈號 9藍-45紅",
               emoji="🚦"),
    DangerSpec("m1b_m2_gap", "M1B-M2 資金動能", "long", "%", "low_bad",
               yellow=1.0, red=0.0, decimals=2,
               note="≥1 黃金交叉 / <0 死亡交叉", source="DESIGN:資金動能交叉慣例",
               emoji="💰"),

    # ── 📈 中期：景氣循環 ──
    DangerSpec("ism_pmi", "台灣 PMI", "mid", "", "low_bad",
               yellow=_PMI_YELLOW, red=_PMI_RED, decimals=1,
               note="<50 收縮 / <46 嚴重收縮", source="SSOT:MACRO_THRESHOLDS.PMI"),
    DangerSpec("us_core_cpi", "美國核心 CPI YoY", "mid", "%", "high_bad",
               yellow=_CPI_YELLOW, red=_CPI_RED, decimals=1,
               note=">3.5% 外資提款風險 / >4% 通膨嚴峻", source="SSOT:MACRO_THRESHOLDS.CPI"),
    DangerSpec("tw_export", "台灣出口訂單 YoY", "mid", "%", "low_bad",
               yellow=0.0, red=-5.0, decimals=1,
               note="<0% 衰退邊界 / <-5% 連續衰退", source="SSOT:tab_macro 出口否決權 -5%"),
    DangerSpec("bias_240", "年線乖離率 BIAS240", "mid", "%", "high_bad",
               yellow=10.0, red=20.0, decimals=1,
               note=">+20% 正乖離過熱（負乖離為超賣機會，非危險）",
               source="SSOT:macro_helpers ±20 + DESIGN(10)"),

    # ── ⚡ 短線急殺：即時 risk-off ──
    DangerSpec("vix", "VIX 恐慌指數", "short", "", "high_bad",
               yellow=_VIX_YELLOW, red=_VIX_RED, decimals=1,
               note="≥22 警戒 / ≥30 流動性危機強制空手", source="SSOT:MACRO_THRESHOLDS.VIX"),
    # v18.286:10Y / DXY 加入註冊表(供 tab_macro 國際指標 sparkline 用)
    DangerSpec("us10y", "10Y 公債殖利率", "mid", "%", "high_bad",
               yellow=_US10Y_YELLOW, red=_US10Y_RED, decimals=2,
               note="≥4.5 警戒 / ≥5.0 緊縮", source="SSOT:MACRO_THRESHOLDS.US10Y"),
    DangerSpec("dxy", "美元指數 DXY", "mid", "", "high_bad",
               yellow=_DXY_YELLOW, red=_DXY_RED, decimals=1,
               note="≥105 警戒 / ≥110 強勢美元壓力", source="SSOT:MACRO_THRESHOLDS.DXY"),
    DangerSpec("adl", "ADL 漲跌家數比", "short", "%", "low_bad",
               yellow=50.0, red=35.0, decimals=1,
               note="<50 廣度轉弱 / <35 廣度崩（大型股獨撐）", source="DESIGN:市場廣度慣例"),
    DangerSpec("fut_net", "外資期貨淨口", "short", "口", "low_bad",
               yellow=float(FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS),
               red=float(FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS), decimals=0,
               note="<-10000 避險 / <-20000 大戶閃人", source="SSOT:FOREIGN_FUTURES_*_LOTS"),

    # ── 🧩 籌碼：大戶定位 ──
    DangerSpec("margin", "融資餘額", "chips", "億", "high_bad",
               yellow=2500.0, red=float(MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI), decimals=0,
               note="2500-3400 警戒 / >3400 散戶槓桿極危",
               source="SSOT:MARGIN_BALANCE_OVERHEAT(3400)+DESIGN(2500)"),
    DangerSpec("jingqi", "旌旗指數（站上 20MA %）", "chips", "%", "low_bad",
               yellow=60.0, red=40.0, decimals=0,
               note=">60 積極 / 40-60 中性 / <40 弱勢", source="DESIGN:站上均線比例慣例"),
    DangerSpec("foreign_net", "外資現貨淨買賣", "chips", "億", "low_bad",
               yellow=0.0, red=-200.0, decimals=0,
               note=">0 買超 / <0 賣超 / <-200 大賣（軟線）", source="DESIGN:外資現貨流向"),

    # ── 📰 新聞：系統性風險掃描 ──
    DangerSpec("news_systemic", "系統性風險新聞數", "news", "則", "high_bad",
               yellow=float(NEWS_SYSTEMIC_YELLOW_COUNT),
               red=float(NEWS_SYSTEMIC_RED_COUNT), decimals=0,
               note="≥1 則警戒 / ≥2 則紅（戰爭/倒閉/崩盤關鍵字命中）",
               source="DESIGN:命中則數規則"),
]

# 快速查表
SPECS_BY_KEY: dict[str, DangerSpec] = {s.key: s for s in BUCKET_DANGER_SPECS}

# ════════════════════════════════════════════════════════════════
# v18.349 — session_state["macro_info"] 核心指標 key 契約（SSOT）
#   「🔎 資料診斷」覆蓋率表(data_coverage._macro_keys) + tab_macro 寫入端
#   has-data 判定(_macro_has_data) 共用此單一清單，杜絕 v18.282 那種
#   「key 名各自寫死 → 漂移 → 覆蓋率永遠紅燈」(data_coverage.py:59 留疤)。
#
#   注意維度差異：此為 macro_info dict 的「key 存在性」契約（含 fed_funds，
#   無門檻判讀需求），與 BUCKET_DANGER_SPECS（危險門檻註冊表，含 health /
#   m1b_m2_gap 等衍生指標、且不含 fed_funds）不同維度，不可混用。
#   其中 5 個（除 fed_funds）同時是 DangerSpec key → test 斷言 ⊆ SPECS_BY_KEY，
#   擋下 key 打錯（v18.282 正是此類 typo 導致永遠紅燈）。
# ════════════════════════════════════════════════════════════════
MACRO_INFO_KEYS: tuple[str, ...] = (
    "vix", "ism_pmi", "us_core_cpi", "fed_funds", "ndc_signal", "tw_export",
)


def specs_for_bucket(bucket: str) -> list[DangerSpec]:
    """取某桶的所有 DangerSpec（依註冊順序）。"""
    return [s for s in BUCKET_DANGER_SPECS if s.bucket == bucket]


def classify_danger(value: Optional[float], spec: DangerSpec) -> str:
    """依 DangerSpec 將值分級。回 'green' | 'yellow' | 'red' | 'gray'(None/不可解析)。

    §1 Fail Loud：None → 'gray'（未載入），**不**偽綠。
    """
    if value is None:
        return "gray"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "gray"

    if spec.direction == "high_bad":
        if v >= spec.red:
            return "red"
        if v >= spec.yellow:
            return "yellow"
        return "green"

    if spec.direction == "low_bad":
        if v <= spec.red:
            return "red"
        if v <= spec.yellow:
            return "yellow"
        return "green"

    # band：高低兩側皆有危險帶
    if (spec.red_lo is not None and v <= spec.red_lo) or v >= spec.red:
        return "red"
    if (spec.yellow_lo is not None and v <= spec.yellow_lo) or v >= spec.yellow:
        return "yellow"
    return "green"


def aggregate_level(levels: list[str]) -> str:
    """桶燈號 = 旗下指標取最危險者（紅>黃>綠）。全部 gray（未載入）→ gray。"""
    loaded = [lv for lv in levels if lv in LEVEL_RANK]
    if not loaded:
        return "gray"
    return max(loaded, key=lambda lv: LEVEL_RANK[lv])


def fmt_value(value: Optional[float], spec: DangerSpec) -> str:
    """依 spec.decimals + unit 格式化顯示值。None → '—'。"""
    if value is None:
        return "—"
    try:
        return f"{float(value):.{spec.decimals}f}{spec.unit}"
    except (TypeError, ValueError):
        return f"{value}{spec.unit}"


# ════════════════════════════════════════════════════════════════
# v18.310 Bug-總經版面：桶群組大分隔 banner(把載入後散落的 deep section
#   視覺歸位成 5+1 桶群組)。純字串 builder,零 streamlit(§8.2 L0)。
#   st.markdown 呼叫留在 L5 tab_macro。
# ════════════════════════════════════════════════════════════════

# 桶群組主色(視覺區隔用;與既有 LEVEL_COLOR 燈號色不同維度)
BUCKET_GROUP_COLOR = {
    "long":     "#3fb950",   # 🌳 長期 — 綠
    "mid":      "#58a6ff",   # 📈 中期 — 藍
    "short":    "#f0883e",   # ⚡ 短線急殺 — 橙
    "global":   "#e3b341",   # 🌍 全球風險 — 金（v18.317：10 燈雷達改桶）
    "pivot":    "#ff7b72",   # 🔮 拐點 — 珊瑚紅（v18.321：景氣反轉偵測）
    "cashflow": "#39c5cf",   # 💵 現金流向 — 青綠（v18.321：熱錢三角交叉）
    "chips":    "#a371f7",   # 🧩 籌碼 — 紫
    "news":     "#d2a8ff",   # 📰 新聞 — 淺紫
    "ai":       "#76e3ea",   # 🧠 AI 綜合 — 青
}

# AI 群組(跨桶 AI + 新聞 AI 裁決)非 5 桶之一,meta 另列
_AI_GROUP_META = {"emoji": "🧠", "title": "AI 綜合決策", "sub": "跨桶 AI 投資決策 × 新聞 AI 總裁決"}

# v18.317 全球風險群組(10 燈短線雷達改桶):亦非 5 桶 DangerSpec 之一,meta 另列。
# 資料源為 risk_radar.detect_risk_radar(自帶 color/label/value/trend),非 BUCKET_DANGER_SPECS,
# 故與 "ai" 同走特例 meta(badge 顯示「雷達」而非「桶 N/5」)。
_GLOBAL_GROUP_META = {"emoji": "🌍", "title": "全球風險",
                      "sub": "美股/國際 1-5 日急殺速度（9 燈雷達）"}

# v18.321 拐點 / 現金流向群組:深度分析區塊(非 5 桶 DangerSpec),meta 另列。
# 與 "ai"/"global" 同走特例(badge 顯示自訂短語而非「桶 N/5」)。
_PIVOT_GROUP_META = {"emoji": "🔮", "title": "拐點",
                     "sub": "六大面向 × MK 黃金拐點（景氣反轉偵測）"}
_CASHFLOW_GROUP_META = {"emoji": "💵", "title": "現金流向",
                        "sub": "熱錢三角交叉（外資 × 匯率 × 背離）"}


def bucket_group_banner_html(bucket_key: str, idx: int, total: int = 5) -> str:
    """產生桶群組大分隔 banner HTML(載入後 deep section 視覺歸位)。

    Args
    ----
    bucket_key: BUCKET_ORDER 之一,或 "ai"(AI 綜合群組)/"global"(全球風險群組)
    idx: 第幾桶(1-based,顯示「桶 idx/total」)
    total: 桶總數(預設 5)

    Returns
    -------
    str: 全寬漸層 banner HTML。缺 key → raise KeyError(§1 Fail Loud)。
    """
    _special_meta = {
        "ai": _AI_GROUP_META, "global": _GLOBAL_GROUP_META,
        "pivot": _PIVOT_GROUP_META, "cashflow": _CASHFLOW_GROUP_META,
    }
    _special_badge = {"ai": "綜合", "global": "雷達",
                      "pivot": "拐點", "cashflow": "金流"}
    meta = _special_meta.get(bucket_key) or BUCKET_META[bucket_key]
    color = BUCKET_GROUP_COLOR[bucket_key]  # KeyError on bad key = Fail Loud
    _badge = _special_badge.get(bucket_key) or f"桶 {idx}/{total}"
    return (
        f'<div style="margin:34px 0 10px;padding:12px 18px;'
        f'background:linear-gradient(90deg,{color}2b,{color}0a,#0d1117);'
        f'border-left:6px solid {color};border-radius:0 10px 10px 0;">'
        f'<span style="font-size:12px;color:{color};font-weight:700;opacity:0.85;">'
        f'{_badge}</span>'
        f'<div style="font-size:18px;font-weight:900;color:{color};margin-top:2px;">'
        f'{meta["emoji"]} {meta["title"]}</div>'
        f'<div style="font-size:12px;color:#8b949e;margin-top:2px;">{meta["sub"]}</div></div>'
    )


# ════════════════════════════════════════════════════════════════
# v18.313 桶輕量總結 bar(user 反饋:每桶頂部加「整體狀態」橫條,raw 收 expander)。
#   復用 compute_five_bucket_summary 該桶 summary(color/emoji/label/details),
#   不新增資料線。純字串 builder,零 streamlit(§8.2 L0)。
# ════════════════════════════════════════════════════════════════
def bucket_summary_bar_html(bucket_key: str, bucket_summary: dict) -> str:
    """桶輕量總結 bar:整體燈號 + 🔴🟡🟢 計數 + 各指標 chip + SPEC §11 參考。

    Args
    ----
    bucket_key: BUCKET_ORDER 之一(或 "ai")
    bucket_summary: compute_five_bucket_summary()[bucket_key]，含
                    color / emoji / label / details(list of {danger,label,value_str})

    Returns
    -------
    str: 全寬輕量橫條 HTML。資料缺 → 顯示「未載入」(不 raise,§1 不偽造數字)。
    """
    meta = _AI_GROUP_META if bucket_key == "ai" else BUCKET_META[bucket_key]
    gcolor = BUCKET_GROUP_COLOR.get(bucket_key, "#6e7681")
    _s = bucket_summary or {}
    light_color = _s.get("color", "#6e7681")
    light_emoji = _s.get("emoji", "⬜")
    light_label = _s.get("label", "未載入")
    details = _s.get("details", []) or []

    n_red = sum(1 for d in details if d.get("danger") == "red")
    n_yellow = sum(1 for d in details if d.get("danger") == "yellow")
    n_green = sum(1 for d in details if d.get("danger") == "green")

    # 各指標 chip(燈號 + 名稱 + 值)
    chips = []
    for d in details:
        _ic = LEVEL_EMOJI.get(d.get("danger"), "⬜")
        chips.append(
            f'<span style="display:inline-block;margin:2px 4px;padding:2px 8px;'
            f'border-radius:10px;background:#161b22;border:1px solid #21262d;'
            f'font-size:11px;color:#c9d1d9;">'
            f'{_ic} {d.get("label", "")}：<b>{d.get("value_str", "—")}</b></span>'
        )
    chips_html = "".join(chips) if chips else (
        '<span style="font-size:11px;color:#8b949e;">尚未載入資料 — 點上方「🚀 一鍵更新全部數據」</span>'
    )

    return (
        f'<div style="margin:8px 0 10px;padding:10px 14px;'
        f'background:linear-gradient(90deg,{gcolor}14,#0d1117);'
        f'border:1px solid {gcolor}44;border-radius:8px;">'
        f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:10px;">'
        f'<span style="font-size:13px;font-weight:900;color:{gcolor};">'
        f'{meta["emoji"]} {meta["title"]} 整體狀態</span>'
        f'<span style="font-size:13px;font-weight:700;color:{light_color};">'
        f'{light_emoji} {light_label}</span>'
        f'<span style="font-size:12px;color:#8b949e;">'
        f'🔴 {n_red} ｜ 🟡 {n_yellow} ｜ 🟢 {n_green}</span>'
        f'<span style="font-size:10px;color:#484f58;margin-left:auto;">'
        f'📋 門檻見 SPEC §11 危險門檻表</span></div>'
        f'<div style="margin-top:6px;">{chips_html}</div></div>'
    )


# ════════════════════════════════════════════════════════════════
# v18.336 §1 Fail Loud：籌碼三源(法人/融資/先行指標)全空時的診斷卡。
#   user 2026-06-28 回報「§三 籌碼 資料不見了」：根因為台股籌碼三源
#   (TWSE BFI82U / FinMind 融資 / FinMind+TAIFEX 先行指標)在缺 FINMIND_TOKEN
#   或來源暫無回應時全敗，但 UI 以 `if inst:` / `if margin:` 靜默跳過 → 整區空白。
#   §1：不可靜默,須明確告知「為何空 + 怎麼救」。純字串 builder,零 streamlit(L0)。
# ════════════════════════════════════════════════════════════════
def chips_empty_state_html(attempted: bool, token_present: bool) -> str:
    """籌碼三源全空時的 fail-loud 診斷卡(§1)。

    Args
    ----
    attempted: 是否已嘗試載入重資料(cl_ts / chips_loaded 任一存在)。
               False = 冷啟動尚未點更新;True = 點過更新但仍空 = 抓取失敗。
    token_present: 是否偵測得到 FINMIND_TOKEN(st.secrets 或 os.environ)。

    Returns
    -------
    str: 診斷卡 HTML。三種情境給不同顏色 + 可執行建議,不偽造數字。
    """
    if not attempted:
        icon, color = "📡", "#6e7681"
        msg = ("尚未載入 — 點上方「🚀 一鍵更新全部數據」抓取 "
               "法人聰明錢 / 融資融券 / 先行指標。")
    elif not token_present:
        icon, color = "⚠️", "#f0883e"
        msg = ("已嘗試抓取，但法人 / 融資 / 先行指標三源皆空，且偵測不到 "
               "<b>FINMIND_TOKEN</b>。台股籌碼三源需 FinMind token 或台灣 IP "
               "(海外 Streamlit Cloud 直連 TWSE 會被擋) — 請在部署 secrets 設定 "
               "FINMIND_TOKEN 後，重按「🚀 一鍵更新全部數據」。")
    else:
        icon, color = "⚠️", "#f0883e"
        msg = ("已嘗試抓取，但法人 / 融資 / 先行指標三源皆空。"
               "常見原因：TWSE / FinMind 暫時無回應或當日尚未出表 — "
               "請稍後重按「🚀 一鍵更新全部數據」；若持續，請檢查 "
               "FINMIND_TOKEN 是否已失效 / 額度用罄。")
    return (
        f'<div style="margin:8px 0 12px;padding:12px 16px;'
        f'background:linear-gradient(90deg,{color}1f,#0d1117);'
        f'border-left:4px solid {color};border-radius:0 8px 8px 0;">'
        f'<span style="font-size:13px;font-weight:800;color:{color};">'
        f'{icon} 籌碼資料未顯示</span>'
        f'<div style="font-size:12px;color:#c9d1d9;margin-top:5px;'
        f'line-height:1.55;">{msg}</div></div>'
    )


# ════════════════════════════════════════════════════════════════
# v18.340 — 先行指標明細表(日期 × 法人/期貨/PCR/融資)專屬 fail-loud。
#   user 2026-06-28:對照 6/14 截圖,table 不見 = li_latest empty。
#   原 tab_macro.py:4657 elif 分支只說「請重按更新」+ 一段含糊文案,沒明指
#   FINMIND_TOKEN(真正最常見根因)。同 PR #362 chips 三狀態分流模式,給 table
#   專屬 helper:未載入 / 已試+無token / 已試+有token 三色。純字串 builder,L0。
# ════════════════════════════════════════════════════════════════
def leading_table_empty_state_html(attempted: bool, token_present: bool) -> str:
    """先行指標明細表為空時的 fail-loud 診斷卡(§1)。

    Args
    ----
    attempted: 是否已嘗試載入(cl_data 任一存在)。False = 冷啟動;True = 點過更新
               但 li_latest 仍空 = 4 個 FinMind API(TX/MTX/TXO/三大法人)全敗。
    token_present: 是否偵測得到 FINMIND_TOKEN(st.secrets 或 os.environ)。

    Returns
    -------
    str: 診斷卡 HTML,三情境分色給不同建議,不偽造數字。
    """
    if not attempted:
        icon, color = "📡", "#6e7681"
        msg = ("尚未載入 — 點上方「🚀 一鍵更新全部數據」抓取先行指標"
               "(外資期貨 / 選擇權PCR / 三大法人 / 融資餘額)。")
    elif not token_present:
        icon, color = "⚠️", "#f0883e"
        msg = ("已嘗試抓取,但先行指標 4 源(期貨 TX/MTX、選擇權 TXO、三大法人、"
               "融資)全空,且偵測不到 <b>FINMIND_TOKEN</b>。"
               "上述 4 個 FinMind API 全部需 token,缺 token → 全 422 → 表格無法渲染。"
               "請在部署 secrets 設定 FINMIND_TOKEN 後,重按「🚀 一鍵更新全部數據」。")
    else:
        # v18.343:原文案逕指「4 個 FinMind API 全回空 / 額度用罄」,但實測最常見根因是
        # 先行指標「補強段」(TAIFEX 前五大/精確韭菜)逐日序列爬逾時,整批被併發池砍掉——
        # 此時 FinMind 主資料(三大法人/期貨/PCR/融資)其實已抓到,只是沒組進表。誤導性
        # 文案違反 §1 Fail Loud(診斷講錯方向),改為以逾時為首因、額度/token 退為次因。
        icon, color = "⚠️", "#f0883e"
        msg = ("已嘗試抓取,但先行指標明細表未組出(三大法人摘要/策略燈若已顯示,"
               "代表 FinMind 主資料其實有抓到)。"
               "常見原因:① 補強來源(TAIFEX 前五大/精確韭菜)逐日爬逾時被截斷 → "
               "多按一次「🚀 一鍵更新全部數據」通常即補上(背景已寫快取);"
               "② 非交易日(週末/假日)→ 屬正常,等下個交易日;"
               "③ FinMind token 失效 / 額度用罄(每日 600 次)→ 至 FinMind 後台確認。"
               "TAIFEX 在海外 IP 常被擋,前五大/精確PCR 等備援來源可能無法補齊。")
    return (
        f'<div style="margin:8px 0 12px;padding:12px 16px;'
        f'background:linear-gradient(90deg,{color}1f,#0d1117);'
        f'border-left:4px solid {color};border-radius:0 8px 8px 0;">'
        f'<span style="font-size:13px;font-weight:800;color:{color};">'
        f'{icon} 先行指標明細表未顯示</span>'
        f'<div style="font-size:12px;color:#c9d1d9;margin-top:5px;'
        f'line-height:1.55;">{msg}</div></div>'
    )


# ════════════════════════════════════════════════════════════════
# v18.338 — 桶指標 Fund 式卡片網格（user 2026-06-28：總經資料像基金那樣
#   分組 + 小圖 + SPEC）。每指標一張卡：小圖 + 名稱 + 值(燈號色) + SPEC 註解。
#   復用 compute_five_bucket_summary()[bucket] details，不新增資料線。
#   純字串 builder，零 streamlit（L0）。先做 🌳 長期桶當模板。
# ════════════════════════════════════════════════════════════════
def bucket_indicator_cards_html(bucket_summary: dict) -> str:
    """桶指標 Fund 式卡片網格 HTML。

    Args
    ----
    bucket_summary: compute_five_bucket_summary()[bucket_key]，含
                    details(list of {key, label, value_str, danger, note})。

    Returns
    -------
    str: flex-wrap 卡片網格 HTML。每卡 = 小圖(SPECS_BY_KEY[key].emoji) + 名稱
         + 燈號 + 值 + SPEC 註解(spec.note)。
    details 缺 → 「未載入」提示（§1 不偽造數字，不空字串）。
    """
    details = (bucket_summary or {}).get("details", []) or []
    if not details:
        return ('<div style="font-size:12px;color:#8b949e;padding:8px 4px;">'
                '尚未載入資料 — 點上方「🚀 一鍵更新全部數據」</div>')
    cards = []
    for d in details:
        _spec = SPECS_BY_KEY.get(d.get("key"))
        _emoji = (_spec.emoji if _spec and _spec.emoji else "📊")
        _dg = d.get("danger", "gray")
        _lc = LEVEL_COLOR.get(_dg, "#6e7681")
        _le = LEVEL_EMOJI.get(_dg, "⬜")
        cards.append(
            f'<div style="flex:1 1 160px;min-width:148px;background:#0d1117;'
            f'border:1px solid #21262d;border-left:3px solid {_lc};'
            f'border-radius:8px;padding:10px 12px;">'
            f'<div style="font-size:12px;color:#8b949e;">'
            f'{_emoji} {d.get("label", "")}</div>'
            f'<div style="font-size:20px;font-weight:800;color:{_lc};margin:3px 0;">'
            f'{_le} {d.get("value_str", "—")}</div>'
            f'<div style="font-size:10px;color:#6e7681;line-height:1.4;">'
            f'📋 {d.get("note", "")}</div></div>'
        )
    return (
        '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 12px;">'
        + "".join(cards) + '</div>'
    )
