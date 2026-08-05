"""v18.323：財報體檢門檻 SSOT 常數模組。

（v19.174 去識別化：常數前綴 `MJ_*` → `FH_*`（FH = Financial Health），
文字敘述移除人名／稱謂。**數值一個都沒改**；舊名 `MJ_*` 保留為過渡期 alias。）

`financial_health_engine.py` 的「4 力 1 棒子 + 現金流矩陣」門檻原同時硬寫在
**AI prompt 文字** 與 **6 個 `_no_ai_*` fallback 計算**兩處，且 v18.209(commit 4ebe5bc)
一次寫入時就出現 3 處 prompt/code 不一致（負債槓桿 60 vs 65、毛利率 Good 20% vs 40%、
安全邊際 Strong 60% vs 20%）。本模組把判定門檻收為單一具名常數：
- `_no_ai_*` 計算**直接 import** 這些常數（消滅 code 端 inline magic）。
- prompt 文字仍保留人類可讀的數字（不 f-string 模板化，避免破壞既有 `{{ }}` JSON 轉義），
  改由 `tests/test_financial_health_ssot.py` golden test 釘住「prompt 內數值 == 本檔常數」，
  任何一邊漂移測試即紅。

設計：純常數模組，零 import 依賴（L0，不得 import streamlit / requests）；caller 用
`from shared.financial_health_thresholds import FH_CASH_RATIO_SAFE_PCT, ...`。

【3 處漂移的收斂決策（v18.323，git blame 證實 3 處同 commit 手誤、非後期調參）】
1. 負債槓桿警報：**名稱分離**。一般「負債結構」安全線 60/70（`FH_DEBT_RATIO_*`）與
   杜邦「槓桿膨脹警報」門檻 65（`FH_DUPONT_LEVERAGE_DEBT_PCT`，僅 ROE>15% 時觸發的更嚴判斷）
   本為兩個不同用途；profitability prompt 原寫 60 → 對齊其 code + advanced 模組的 65。
2. 毛利率 Good：對齊 **40%**（保 code 現值，修 prompt 20→40）。合「高毛利才是護城河」立場。
3. 安全邊際 Strong：對齊 **60%**（安全邊際>60% 表毛利衰退 40% 本業仍不虧；
   修 code bug 20→60，保三階 Strong/Acceptable/Weak 避免硬懸崖）。

單位：除 `FH_ASSET_TURNOVER_MIN`（純比值「趟」）外，全部為百分比（%）數值，
變數名以 `_PCT` 編碼避免 §4.1 量綱陷阱。閾值來源：現金流量財務分析方法論 +
test_financial_health_engine.py 邊界測試背書（負債 45→Pass / 65→Warning / 75→Fail 釘 60/70）。
"""
from __future__ import annotations

# ════════════════════════════════════════════════════════════════
# 存活關 / 生死關（氣長 + 收現 + 100-100-10 現金流自給）
# ════════════════════════════════════════════════════════════════

FH_CASH_RATIO_SAFE_PCT: float = 25.0
"""氣長（現金與約當現金 / 總資產）安全線：>=25% → 🟢 Pass。生死關第一指標。"""

FH_CASH_RATIO_WATCH_PCT: float = 10.0
"""氣長注意線：10~25% → 🟡 Acceptable；<10% → 🔴 Fail。"""

FH_DSO_FAST_DAYS: float = 15.0
"""收現速度（應收帳款天數 DSO）天天收現門檻：<15 天 → Pass（天天收現金好生意）。
亦為償債能力交叉驗證條件 B（DSO<15 視為收現行業豁免）。"""

FH_DSO_SLOW_DAYS: float = 90.0
"""收現速度慢線：15~90 天 → Acceptable；>90 天 → Fail。"""

FH_CASHFLOW_RATIO_MIN_PCT: float = 100.0
"""100-100-10 法則條件 A — 現金流量比率（營業現金流 / 流動負債）須 >100%。"""

FH_CASHFLOW_ADEQUACY_MIN_PCT: float = 100.0
"""100-100-10 法則條件 B — 現金流量允當比率（近5年OCF / 近5年[CapEx+存貨增+現金股利]）須 >=100%。"""

FH_CASH_REINVEST_MIN_PCT: float = 10.0
"""100-100-10 法則條件 C — 現金再投資比率（(OCF-現金股利)/(固定+長期資產)）須 >10%。"""


# ════════════════════════════════════════════════════════════════
# 財務結構關（那根棒子：負債比 + 以長支長）
# ════════════════════════════════════════════════════════════════

FH_DEBT_RATIO_EXCELLENT_PCT: float = 40.0
"""負債佔資產比率優秀線：<40% → 🟢 優秀。"""

FH_DEBT_RATIO_PASS_PCT: float = 60.0
"""負債佔資產比率安全線：<60% → Pass；40~60% → 🟡 正常。一般「負債結構」標準。
注意：金融/租賃業負債高屬正常，須以 is_finance 旗標豁免。"""

FH_DEBT_RATIO_WARN_PCT: float = 70.0
"""負債佔資產比率警戒線：60~70% → Warning；>70% → 🔴 Fail（突發性倒閉風險高）。"""

FH_LONG_TERM_FUNDING_MIN_PCT: float = 100.0
"""以長支長比率（(股東權益+非流動負債)/固定資產）：>100% → Pass；<100% → Fail（短債長投）。"""


# ════════════════════════════════════════════════════════════════
# 償債能力關（流動 / 速動比率，極嚴 300/150 標準）
# ════════════════════════════════════════════════════════════════

FH_CURRENT_RATIO_MIN_PCT: float = 300.0
"""流動比率（流動資產/流動負債）極嚴標準：>300% → Pass；≤300% → Fail_Initial（待交叉驗證）。"""

FH_QUICK_RATIO_MIN_PCT: float = 150.0
"""速動比率（(流動資產-存貨)/流動負債）極嚴標準：>150% → Pass；≤150% → Fail_Initial。"""


# ════════════════════════════════════════════════════════════════
# 獲利能力關（5 力：毛利 / 營益 / 安全邊際 / 淨利 / ROE + 槓桿防呆）
# ════════════════════════════════════════════════════════════════

FH_GROSS_MARGIN_GOOD_PCT: float = 40.0
"""營業毛利率 Good 線：>=40% → Good（高毛利好生意/護城河）。
v18.323 漂移收斂：對齊 code 現值 40%（prompt 原 20% 已修正對齊），合「高毛利才是護城河」立場。"""

FH_OPERATING_MARGIN_EXCELLENT_PCT: float = 10.0
"""營業利益率 Excellent 線：>10% → Excellent；0~10% → Moderate；<0% → 本業虧損 FAIL。"""

FH_MOS_STRONG_PCT: float = 60.0
"""經營安全邊際（營業利益/毛利）Strong 線：>=60% → Strong（毛利衰退 40% 本業仍不虧）。
v18.323 漂移收斂：對齊經典 60%（code 原 bug 20% 已修正），保三階 Strong/Acceptable/Weak。"""

FH_NET_MARGIN_PASS_PCT: float = 10.0
"""稅後淨利率 Pass 線：>10% → Pass；2~10% → Thin Profit；<2% → Fail。"""

FH_ROE_TOP_PCT: float = 20.0
"""股東權益報酬率 Top Tier 線：>20% → Top Tier；10~20% → Good；<10% → Weak。"""

FH_ROE_LEVERAGE_CHECK_PCT: float = 15.0
"""ROE 槓桿防呆觸發線：ROE>15% 時強制檢查負債比率（避免高 ROE 來自槓桿作弊）。"""

FH_DUPONT_LEVERAGE_DEBT_PCT: float = 65.0
"""杜邦「槓桿膨脹警報」負債門檻：ROE>15%(FH_ROE_LEVERAGE_CHECK_PCT) 且 負債比>65% → 警報。
v18.323 漂移收斂：與一般負債結構安全線 60%(FH_DEBT_RATIO_PASS_PCT) **刻意分離**為不同用途常數；
profitability prompt 原寫 60 → 對齊其 code + advanced 模組一致採用的 65。"""


# ════════════════════════════════════════════════════════════════
# 經營能力 / 綜合診斷
# ════════════════════════════════════════════════════════════════

FH_ASSET_TURNOVER_MIN: float = 1.0
"""總資產翻桌率（營收/總資產）：>1.0 趟 → 通過；<1.0 趟 → 檢查現金佔比 or ROE 三年 >20%。
單位為純比值「趟」（非 %）。"""

FH_EARNINGS_QUALITY_MIN_PCT: float = 100.0
"""盈餘品質（OCF / 稅後淨利）：>=100% → Pass（真金白銀）；<100% → Fail（紙上富貴）。"""


# ════════════════════════════════════════════════════════════════
# v19.174 去識別化過渡期 alias（舊名 `MJ_*` → 新名 `FH_*`）
# ────────────────────────────────────────────────────────────────
# 舊前綴帶人名縮寫，已全面改為中性 `FH_`（FH = Financial Health）。
# 這裡保留同值 alias，避免尚未遷移的 caller 直接 ImportError；
# **caller 全遷移後移除**。數值與新名完全同一物件，不會產生第二份真相。
# ════════════════════════════════════════════════════════════════

MJ_CASH_RATIO_SAFE_PCT = FH_CASH_RATIO_SAFE_PCT
MJ_CASH_RATIO_WATCH_PCT = FH_CASH_RATIO_WATCH_PCT
MJ_DSO_FAST_DAYS = FH_DSO_FAST_DAYS
MJ_DSO_SLOW_DAYS = FH_DSO_SLOW_DAYS
MJ_CASHFLOW_RATIO_MIN_PCT = FH_CASHFLOW_RATIO_MIN_PCT
MJ_CASHFLOW_ADEQUACY_MIN_PCT = FH_CASHFLOW_ADEQUACY_MIN_PCT
MJ_CASH_REINVEST_MIN_PCT = FH_CASH_REINVEST_MIN_PCT
MJ_DEBT_RATIO_EXCELLENT_PCT = FH_DEBT_RATIO_EXCELLENT_PCT
MJ_DEBT_RATIO_PASS_PCT = FH_DEBT_RATIO_PASS_PCT
MJ_DEBT_RATIO_WARN_PCT = FH_DEBT_RATIO_WARN_PCT
MJ_LONG_TERM_FUNDING_MIN_PCT = FH_LONG_TERM_FUNDING_MIN_PCT
MJ_CURRENT_RATIO_MIN_PCT = FH_CURRENT_RATIO_MIN_PCT
MJ_QUICK_RATIO_MIN_PCT = FH_QUICK_RATIO_MIN_PCT
MJ_GROSS_MARGIN_GOOD_PCT = FH_GROSS_MARGIN_GOOD_PCT
MJ_OPERATING_MARGIN_EXCELLENT_PCT = FH_OPERATING_MARGIN_EXCELLENT_PCT
MJ_MOS_STRONG_PCT = FH_MOS_STRONG_PCT
MJ_NET_MARGIN_PASS_PCT = FH_NET_MARGIN_PASS_PCT
MJ_ROE_TOP_PCT = FH_ROE_TOP_PCT
MJ_ROE_LEVERAGE_CHECK_PCT = FH_ROE_LEVERAGE_CHECK_PCT
MJ_DUPONT_LEVERAGE_DEBT_PCT = FH_DUPONT_LEVERAGE_DEBT_PCT
MJ_ASSET_TURNOVER_MIN = FH_ASSET_TURNOVER_MIN
MJ_EARNINGS_QUALITY_MIN_PCT = FH_EARNINGS_QUALITY_MIN_PCT
