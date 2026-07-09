"""shared/shortage_screen_thresholds.py — 缺貨 / 供不應求選股 L0 SSOT（v19.65）。

「缺貨選股」= 用四個間接財務/營運訊號交叉驗證「市場供不應求」的股票：
  ① 合約負債大增（客戶預付訂金搶產能）
  ② 毛利率走揚（成功轉嫁漲價）
  ③ 存貨週轉天數下降（做出來就賣掉，庫存極低）
  ④ 月營收 YoY 連續成長

本檔**只放本篩選器獨有的新語意常數**：四訊號計分權重 + 分級 cutoff + 月營收 YoY 門檻。
訊號**邊界值**（合約負債 YoY 15%/30%、QoQ 20% 等）一律**重用** `shared/signal_thresholds.py`
既有 SSOT（`CL_GROWTH_YOY_PCT` / `CL_SURGE_YOY_PCT` / `LEAD_CL_QOQ_SURGE_PCT`），
不在此重複定義，避免同一數字兩處漂移。

§8.2 layer:L0 Infra — 純常數,不依賴任何 L1+。
§3.3 反捏造:consumer(`src/compute/screener/shortage_screener.py`)一律 import 本檔,禁止 inline。
"""
from __future__ import annotations

# ════════════════════════════════════════════════════════════════
# 四訊號計分權重（滿分 100）
# ════════════════════════════════════════════════════════════════
SHORTAGE_W_CONTRACT_LIAB: float = 35.0
"""① 合約負債訊號滿分。四訊號中權重最高 — 合約負債是「在手訂單/預收貨款」最直接的缺貨證據。"""

SHORTAGE_W_GROSS_MARGIN: float = 25.0
"""② 毛利率走揚訊號滿分。供不應求 → 有議價權轉嫁漲價 → 毛利率同步季增+年增。"""

SHORTAGE_W_INVENTORY_DAYS: float = 20.0
"""③ 存貨週轉天數下降訊號滿分。缺貨 → 產品做出來立刻出貨 → 存貨在手天數 DIO 下降。"""

SHORTAGE_W_REVENUE_YOY: float = 20.0
"""④ 月營收 YoY 連續成長訊號滿分。需求強勁的最終體現，且為全市場最便宜可得的圈池訊號。"""

# 權重和 = 35 + 25 + 20 + 20 = 100（不變量，consumer 以此正規化 / 斷言）

# ════════════════════════════════════════════════════════════════
# ① 合約負債 — 子項配分（重用 signal_thresholds 的 YoY/QoQ 邊界值）
# ════════════════════════════════════════════════════════════════
SHORTAGE_CL_SURGE_SCORE: float = 35.0
"""合約負債 YoY ≥ CL_SURGE_YOY_PCT(30%) → 給滿分（爆量在手訂單）。"""

SHORTAGE_CL_GROWTH_SCORE: float = 20.0
"""合約負債 YoY 落在 [CL_GROWTH_YOY_PCT(15%), CL_SURGE_YOY_PCT(30%)) → 給成長分。"""

SHORTAGE_CL_QOQ_BONUS: float = 10.0
"""合約負債 QoQ ≥ LEAD_CL_QOQ_SURGE_PCT(20%) 額外加分（封頂於 SHORTAGE_W_CONTRACT_LIAB）。"""

# ② 毛利率 — 子項配分
SHORTAGE_GM_DUAL_UP_SCORE: float = 25.0
"""毛利率季增(QoQ)且年增(YoY)雙升 → 滿分。"""

SHORTAGE_GM_SINGLE_UP_SCORE: float = 12.0
"""毛利率只有一項（QoQ 或 YoY）上升 → 半分。"""

# ③ 存貨天數 — 子項配分
SHORTAGE_INV_DUAL_DOWN_SCORE: float = 20.0
"""存貨天數較上季 + 較去年同季雙降 → 滿分。"""

SHORTAGE_INV_SINGLE_DOWN_SCORE: float = 10.0
"""存貨天數只有一項下降（或僅有上季可比且下降）→ 半分。"""

# ④ 月營收 — 子項配分
SHORTAGE_REV_STRONG_SCORE: float = 20.0
"""近月 YoY 皆 > 門檻 且逐月遞增 → 滿分（加速成長）。"""

SHORTAGE_REV_STEADY_SCORE: float = 12.0
"""近月 YoY 皆 > 門檻 但未逐月遞增 → 中分（穩健成長）。"""

SHORTAGE_REV_PARTIAL_SCORE: float = 5.0
"""近月 YoY 部分 > 門檻 → 低分（動能不完整）。"""

SHORTAGE_REVENUE_YOY_MIN_PCT: float = 15.0
"""④ 月營收 YoY「強勁成長」判定門檻（單位：%）。對齊 monthly_revenue_calc.classify_trend
的 yoy_threshold 預設 15.0（強進步分界），語意一致。"""

# ════════════════════════════════════════════════════════════════
# 綜合分級 cutoff（總分 → 缺貨訊號強度）
# ════════════════════════════════════════════════════════════════
SHORTAGE_TIER_STRONG_MIN: float = 65.0
"""總分 ≥ 65 → 🟥 強缺貨訊號。"""

SHORTAGE_TIER_MID_MIN: float = 40.0
"""總分 ∈ [40, 65) → 🟧 中度缺貨訊號；< 40 → ⬜ 不明顯。"""

# 分級中文 label + icon SSOT（下游 UI 一律引用，禁止 inline）
TIER_STRONG: str = "強缺貨"
TIER_MID: str = "中度"
TIER_WEAK: str = "不明顯"
TIER_INSUFFICIENT: str = "資料不足"
TIER_NA: str = "不適用"

TIER_ICONS: dict[str, str] = {
    TIER_STRONG: "🟥",
    TIER_MID: "🟧",
    TIER_WEAK: "⬜",
    TIER_INSUFFICIENT: "⚪",
    TIER_NA: "🚫",
}

# ════════════════════════════════════════════════════════════════
# 掃描規模 / 邊界
# ════════════════════════════════════════════════════════════════
SHORTAGE_DEEP_SCAN_MAX: int = 50
"""候選池深掃上限。深抓合約負債/季損益成本高（逐股打 FinMind），比照選股網
`PICKER_DEEP_SCAN_N=50` 界定 FinMind 用量上界，避免撞速限。"""

SHORTAGE_MIN_QUARTERS: int = 5
"""可算 YoY（t vs t-4）所需最少季數。不足 → 標「資料不足」剔除，不 KeyError。"""

SHORTAGE_QUARTER_DAYS: float = 365.0
"""存貨天數（DIO）年化用天數：DIO = 存貨 /（近 4 季營業成本 / 365）。
用「近 4 季成本 / 365」= 每日成本，避免單季成本 ×90 的粗估失真（§4.1 交易日 vs 日曆日）。"""

SHORTAGE_VERSION: str = "shortage_screen_v1"
"""血緣/版本標記（provenance），寫入輸出供追溯。"""
