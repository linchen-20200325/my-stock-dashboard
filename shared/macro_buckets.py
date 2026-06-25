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
    note: str = ""         # 業務語意
    source: str = ""       # 門檻來源（SSOT:... 或 DESIGN）


# ════════════════════════════════════════════════════════════════
# 危險門檻註冊表 — 五桶 × 指標
# ════════════════════════════════════════════════════════════════
BUCKET_DANGER_SPECS: list[DangerSpec] = [
    # ── 🌳 長期：結構 / 景氣位階 ──
    DangerSpec("health", "總經健康評分", "long", "", "low_bad",
               yellow=_HEALTH_YELLOW, red=_HEALTH_RED, decimals=0,
               note="<35 防禦 / <50 轉弱", source="SSOT:HEALTH_DEFENSE_THRESHOLD(35)+DESIGN(50)"),
    DangerSpec("ndc_signal", "NDC 景氣對策燈號", "long", "分", "band",
               yellow=32.0, red=38.0, yellow_lo=23.0, red_lo=16.0, decimals=0,
               note="9-16 藍衰退 / 23-31 綠穩定 / 38+ 紅過熱", source="DESIGN:NDC 燈號 9藍-45紅"),
    DangerSpec("m1b_m2_gap", "M1B-M2 資金動能", "long", "%", "low_bad",
               yellow=1.0, red=0.0, decimals=2,
               note="≥1 黃金交叉 / <0 死亡交叉", source="DESIGN:資金動能交叉慣例"),

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
