"""
financial_health_engine.py — 財報體檢 AI 引擎（v19.174 去識別化：移除人名／稱謂）
--------------------------------------------------------
analyze_financial_health(api_key, stock_id, fin_data) -> dict
  fin_data: fetch_financial_statements() 的輸出
  回傳標準化 8 欄 JSON 供 Streamlit 前端渲染
"""
from __future__ import annotations

import json
import re


from src.config import TAIWAN_ADVISOR_PERSONA as _PERSONA
from shared.colors import (
    TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW,
)

# v18.323: 財報體檢門檻從 shared SSOT 引入（§3.3 反捏造）。v19.174 常數前綴 MJ_→FH_。
# prompt 文字仍保留人類可讀數字，由 tests/test_financial_health_ssot.py golden test 釘住一致。
from shared.financial_health_thresholds import (
    FH_CASH_RATIO_SAFE_PCT, FH_CASH_RATIO_WATCH_PCT,
    FH_DSO_FAST_DAYS, FH_DSO_SLOW_DAYS,
    FH_CASHFLOW_RATIO_MIN_PCT, FH_CASHFLOW_ADEQUACY_MIN_PCT, FH_CASH_REINVEST_MIN_PCT,
    FH_DEBT_RATIO_EXCELLENT_PCT, FH_DEBT_RATIO_PASS_PCT, FH_DEBT_RATIO_WARN_PCT,
    FH_LONG_TERM_FUNDING_MIN_PCT,
    FH_CURRENT_RATIO_MIN_PCT, FH_QUICK_RATIO_MIN_PCT,
    FH_GROSS_MARGIN_GOOD_PCT, FH_MOS_STRONG_PCT, FH_NET_MARGIN_PASS_PCT,
    FH_ROE_LEVERAGE_CHECK_PCT, FH_DUPONT_LEVERAGE_DEBT_PCT,
    FH_EARNINGS_QUALITY_MIN_PCT,
)


# ── Survival Module Prompt（存活能力：3大生死指標）──────────
_SURVIVAL_PROMPT = """\
# Role & Task
你是一個執行嚴格現金流財務邏輯的量化 AI。你的任務是審查企業的【存活能力 (Survival)】。這攸關公司是否會面臨黑字破產或資金斷鏈，判定標準極度嚴格。

# Constraint: Exception Handling
- 若遇財報欄位缺失，輸出 "N/A"，絕對禁止自行推算或腦補。
- 若遇分母為 0（如流動負債=0 或固定資產=0），**視為該欄位缺漏，一律輸出 "N/A"，
  嚴禁判定為 "Pass"** —— 上市櫃公司流動負債／固定資產不可能是 0，
  取數層查無時回 0，把 0 讀成「無負債／輕資產」等於拿缺值換一張及格證。

# Evaluation Logic (存活能力 3 大生死指標)

## 1. 氣長不長 (Cash Ratio)
- 計算：現金與約當現金 / 總資產 * 100%
- 判斷標準：
  - Pass (綠燈)：>= 25%
  - Acceptable (黃燈)：10% ~ 24%
  - Fail (紅燈)：< 10%

## 2. 收現速度 (Days Sales Outstanding, DSO)
- 判斷公司是不是天天收現金的好生意。
- 判斷標準：
  - Pass (綠燈)：< 15天
  - Acceptable (黃燈)：15 ~ 90天
  - Fail (紅燈)：> 90天

## 3. 現金流自給自足 (100 / 100 / 10 法則)
必須同時檢驗以下三個條件：
- [條件 A] 現金流量比率：(營業活動淨現金流 / 流動負債) * 100% -> 必須 > 100%
- [條件 B] 現金流量允當比率：(近5年營業現金流 / 近5年[資本支出+存貨增加+現金股利]) * 100% -> 必須 > 100%（資料不足5年時輸出 "N/A"）
- [條件 C] 現金再投資比率：([營業現金流 - 現金股利] / 固定與長期資產等) * 100% -> 必須 > 10%
- 判斷標準：
  - Pass (綠燈)：三項全數達標（N/A 項不計入失敗）
  - Fail (紅燈)：任一項未達標

# Input Data
<Financial_Data>
{financial_data_json}
</Financial_Data>

# Output Protocol (Strict JSON)
直接輸出以下 JSON（禁止 Markdown 包裝）：
{{
  "Survival_Module": {{
    "Cash_Ratio": {{
      "Value": "XX.X%",
      "Status": "Pass | Acceptable | Fail",
      "Insight": "一句話短評"
    }},
    "DSO_Speed": {{
      "Value": "XX 天",
      "Status": "Pass | Acceptable | Fail",
      "Insight": "一句話短評"
    }},
    "Rule_100_100_10": {{
      "Cash_Flow_Ratio": "XX.X% 或 N/A",
      "Cash_Flow_Adequacy": "XX.X% 或 N/A",
      "Cash_Reinvestment": "XX.X% 或 N/A",
      "Status": "Pass | Fail",
      "Insight": "一句話短評"
    }},
    "Final_Survival_Verdict": "總結存活能力防禦力等級（高/中/低），並標示是否通過生死關。"
  }}
}}"""

# ── Operating Module Prompt（經營能力：周轉效率 + 資金壓力）──
_OPERATING_PROMPT = """\
# Role: 經營能力分析官

# Core Rules
1. 一年以 360 天計算。
2. 直接使用期末值，不使用平均值。

# Analysis Process

## 模組 A：周轉效率檢驗
- [DSO] 應收帳款天數 = 360 / (營收 / 應收帳款)
- [DIO] 存貨在手天數 = 360 / (成本 / 存貨)
- [DPO] 應付帳款天數 = 360 / (成本 / 應付帳款)

## 模組 B：資金壓力檢驗 (做生意的週期)
1. 做生意的完整週期 = DIO + DSO
   - 判定：> 150 天為笨重生意；< 50 天為極速周轉。
2. 缺錢的天數 (CCC) = 完整週期 - DPO
   - 判定：若 < 0 天，標註具備「OPM 護城河」(拿別人的錢做生意)。

## 模組 C：總資產翻桌率
- 計算：營收 / 總資產
- 判定：
  - > 1.0 : 通過。
  - < 1.0 : 檢查是否滿足 (現金佔比 > 25% OR ROE 連續三年 > 20%)。若不滿足，判定為高風險燒錢行業。

# Constraint
- 若財報欄位缺失或分母為 0，該指標輸出 "N/A"，禁止腦補。

# Input Data
<Financial_Data>
{financial_data_json}
</Financial_Data>

# Output Protocol (Strict JSON)
直接輸出以下 JSON（禁止 Markdown 包裝）：
{{
  "Operating_Module": {{
    "DSO": "XX.X 天",
    "DIO": "XX.X 天 或 N/A",
    "DPO": "XX.X 天",
    "Complete_Cycle": "XX.X 天",
    "Cash_Gap_Days": "XX.X 天",
    "OPM_Strategy": "Yes | No",
    "Asset_Turnover": "X.XX 趟",
    "Verdict": "綜合評價做生意的本事（50字以內）"
  }}
}}"""

# ── Profitability Module Prompt（獲利能力：5大指標 + 槓桿防呆）──
_PROFITABILITY_PROMPT = """\
# Role: 獲利能力分析官

# Core Rules
1. 嚴格區分「本業獲利」與「業外獲利」，本業虧損即視為劣質企業。
2. 看到高 ROE 必須聯動檢查「財務結構（負債比）」，排除槓桿作弊。

# Evaluation Logic (獲利能力 5 大指標)

## 1. 營業毛利率 (Gross Margin)
- 計算：毛利(千) / 營業收入(千)
- 判定：> 40% (Good)；≤ 40% (Hard Work)。

## 2. 營業利益率 (Operating Margin)
- 計算：營業利益(千) / 營業收入(千)
- 判定：> 10% (Excellent)；0%~10% (Moderate)；< 0% (FAIL — 本業虧損)。
- Core_Business_Profitable = "Yes" if 營業利益 > 0 else "No"

## 3. 經營安全邊際 (Margin of Safety)
- 計算：營業利益(千) / 毛利(千)
- 判定：> 60% (Strong)；≤ 60% (Weak)。

## 4. 稅後淨利率 (Net Margin)
- 計算：稅後淨利(千) / 營業收入(千)
- 判定：> 10% (Pass)；2%~10% (Thin Profit)；< 2% (Fail)。

## 5. 股東權益報酬率 (ROE)
- 計算：稅後淨利(千) / 股東權益(千)
- 判定：> 20% (Top Tier)；10%~20% (Good)；< 10% (Weak)。
- 防呆：若 ROE > 15%，強制檢查負債比率(%)。
  - 負債比 > 65% → Leverage_Warning = "High Debt Ratio (>65%)"
  - 其他 → Leverage_Warning = "None"

# Input Data
<Financial_Data>
{financial_data_json}
</Financial_Data>

# Output Protocol
直接輸出以下 JSON（禁止 Markdown 包裝）：
{{
  "Profitability_Module": {{
    "Gross_Margin": {{"Value": "XX.X%", "Status": "Good | Hard Work"}},
    "Operating_Margin": {{"Value": "XX.X%", "Core_Business_Profitable": "Yes | No"}},
    "Margin_Of_Safety": {{"Value": "XX.X%", "Status": "Strong | Weak"}},
    "Net_Margin": {{"Value": "XX.X%", "Status": "Pass | Thin Profit | Fail"}},
    "ROE": {{"Value": "XX.X%", "Leverage_Warning": "None | High Debt Ratio (>65%)"}},
    "Final_Insight": "綜合短評（50字以內，點出最關鍵的獲利品質特徵）"
  }}
}}"""

# ── 財報體檢 Prompt ──────────────────────────────────────────
_PROMPT_TEMPLATE = """\
# Role
你是「財報分析師 AI」。依據「4力1棒子＋現金流矩陣」邏輯，\
對下方台灣上市公司財務數據進行標準化健診，輸出精準的 JSON 報告。

# Absolute Constraint
1. 所有判斷【必須 100% 基於】<Financial_Data> 的數值，禁止使用預訓練記憶或猜測。
2. 禁止在輸出中推薦任何買賣操作或 ETF 標的。
3. 輸出僅限 JSON，禁止任何 Markdown 包裝、前言或結語。

# Financial Health Framework (財報體檢體系)

## 第一關：生死關
- 現金佔總資產比率：>{cash_safe_pct}% 安全（🟢）| {cash_watch_pct}~{cash_safe_pct}% 注意（🟡）| <{cash_watch_pct}% 危險（🔴）
- 營業活動現金流（OCF）：>0 真實獲利（🟢）| ≤0 黑字破產警戒（🔴）
- 負債比率（總負債/總資產）：<{debt_excellent_pct}% 優秀（🟢）| {debt_excellent_pct}~{debt_pass_pct}% 正常（🟡）| >{debt_pass_pct}% 危險（🔴）
  注意：金融/租賃業負債高屬正常，請考量行業特性

## 第二關：五力分析（各 0~100 分）
- 存活能力：現金水位 + OCF 穩定性
- 經營能力：應付帳款天數 vs 應收帳款天數（話語權）+ 資產周轉
- 獲利能力：毛利率趨勢 + OCF 佔淨利比（盈餘品質）
- 財務結構：負債結構健康度 + 流動比率
- 償債能力：自由現金流（FCF = OCF - CAPEX）

## 第三關：企業 DNA（現金流矩陣）
依 OCF / ICF / 籌資CF 正負號判斷企業類型：
- (+, -, -) = A+ 穩健印鈔機（本業強，積極擴張）
- (+, -, +) = A 成熟收割機（本業強，不擴張，向外融資/分紅）
- (+, +, ?) = B 資產出清型（賣廠換現金，需警戒）
- (-, -, +) = C+ 成長燒錢型（新創/擴張初期，可接受）
- (-, -, -) = D 資金黑洞（危險）

## OPM 護城河
應付帳款天數 > 應收帳款天數 → 具備議價優勢（向上下游收錢慢、付錢慢）

# Input Data
<Financial_Data>
{financial_data_json}
</Financial_Data>

# Recent News Context (RSS 即時，僅供輔助研判)
<近期新聞>
{news_context}
</近期新聞>

# Output Protocol
直接輸出以下 JSON（禁止 Markdown 包裝）：
{{
  "cash_ratio_status": "🟢 或 🟡 或 🔴",
  "cash_ratio_value": "XX.X%",
  "ocf_status": "🟢 或 🔴",
  "ocf_value": "XXX億",
  "debt_ratio_status": "🟢 或 🟡 或 🔴",
  "debt_ratio_value": "XX.X%",
  "radar_scores": {{
    "存活能力": 0到100的整數,
    "經營能力": 0到100的整數,
    "獲利能力": 0到100的整數,
    "財務結構": 0到100的整數,
    "償債能力": 0到100的整數
  }},
  "business_model_dna": "A+ 穩健印鈔機 (+, -, -)",
  "opm_data": {{
    "payable_days": 數字,
    "receivable_days": 數字,
    "advantage": true或false
  }},
  "ai_insight": "結合DuPont+盈餘品質的150字白話診斷，說明現況與潛在風險（語氣冷靜客觀）。請結合上述提供的<近期新聞>，分析市場情緒與未來潛在的催化劑。",
  "red_flags": "若有①應收帳款增速>營收增速②存貨大增③OCF持續負④負債急升，請說明。若無異常填 None"
}}"""


# ── Gemini 呼叫（多模型 fallback）──────────────────────────
def _gemini_call(prompt: str, api_key: str) -> str:
    """A1 v18.386:HTTP 細節抽至 src.services.ai_fetcher.post_gemini SSOT。"""
    from src.services.ai_fetcher import post_gemini
    text, _ = post_gemini(
        api_key, prompt,
        models=["gemini-2.5-flash-lite", "gemini-2.5-flash",
                "gemini-2.0-flash", "gemini-2.0-flash-lite"],
        persona=_PERSONA,
        temperature=0.2,
        max_tokens=1200,
        timeout=120,
        retries_per_model=1,
        retry_after_parse=False,  # 原 sleep(5) 模式
        inter_model_sleep=0,  # 原 caller 切 model 不 sleep
    )
    return text or "⚠️ AI 服務暫時無法使用"


def _extract_json(raw: str) -> dict:
    text = re.sub(r"```json|```", "", raw).strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group(0))
    raise ValueError(f"無法解析 JSON：{raw[:120]}")


def _derive_basic_from_fin_data(fin_data: dict) -> dict:
    """當 AI 失效但 fin_data 有效時，從原始財報數據直接計算基本指標。"""
    cash_pct = fin_data.get("現金佔總資產(%)", 0) or 0
    if cash_pct >= FH_CASH_RATIO_SAFE_PCT:
        cash_icon = "🟢"
    elif cash_pct >= FH_CASH_RATIO_WATCH_PCT:
        cash_icon = "🟡"
    else:
        cash_icon = "🔴"

    ocf_k = fin_data.get("OCF(千)", 0) or 0
    # 單位防呆：FinMind/MOPS 均回傳千元（OCF(千) key 已標示）
    # 若 |ocf_k| > 1e9，判定為元（NTD）：÷1e8；否則視為千元：÷1e5
    # 台積電單季 OCF ≈ 3~5千億 → 千元欄位約 3e8，不超過 1e9，走千元路徑
    try:
        _abs = abs(ocf_k)
        if _abs > 1e9:
            ocf_yi = round(ocf_k / 1e8, 2)   # 元 → 億
        else:
            ocf_yi = round(ocf_k / 1e5, 2)    # 千元 → 億（標準路徑）
    except Exception:
        ocf_yi = 0
    ocf_icon = "🟢" if ocf_k > 0 else "🔴"

    # debt_pct=0 可能是資料缺漏，不可直接判綠燈
    debt_pct = fin_data.get("負債比率(%)")
    if not debt_pct:
        debt_icon = "⚪"
        debt_pct = 0
    elif debt_pct <= FH_DEBT_RATIO_EXCELLENT_PCT:
        debt_icon = "🟢"
    elif debt_pct <= FH_DEBT_RATIO_PASS_PCT:
        debt_icon = "🟡"
    else:
        debt_icon = "🔴"

    # 企業DNA（三象限現金流）
    _dna_map = {
        ("正", "負", "負"): "A+ 穩健印鈔機",
        ("正", "負", "正"): "B 擴張型成長",
        ("正", "正", "負"): "C 財務重整",
        ("正", "正", "正"): "D 燒錢模式",
        ("負", "負", "負"): "E 衰退縮減",
        ("負", "正", "負"): "F 借貸維生",
        ("負", "負", "正"): "G 融資求活",
        ("負", "正", "正"): "H 危機警戒",
    }
    _dna_key = (
        fin_data.get("OCF符號", "負"),
        fin_data.get("ICF符號", "負"),
        fin_data.get("籌資CF符號", "負"),
    )
    dna = _dna_map.get(_dna_key, "無法判斷（資料不足）")

    ap_days = fin_data.get("應付帳款天數", 0) or 0
    ar_days = fin_data.get("應收帳款天數", 0) or 0

    # 雷達基本估分（無AI，只做粗略分級）
    gm = fin_data.get("毛利率(%)", 0) or 0

    def _score(val, thresholds):  # thresholds: [(>=val, score), ...]
        for thr, sc in thresholds:
            if val >= thr:
                return sc
        return 20

    radar = {
        # 生死關門檻走 SSOT；其餘為 radar 估分曲線斷點（單用途，保 inline）
        "存活能力": _score(cash_pct, [(FH_CASH_RATIO_SAFE_PCT, 80), (FH_CASH_RATIO_WATCH_PCT, 60)]),
        "經營能力": _score(ap_days - ar_days if ar_days > 0 else -999, [(10, 80), (0, 60), (-30, 40)]),
        "獲利能力": _score(gm, [(FH_GROSS_MARGIN_GOOD_PCT, 80), (20, 60), (10, 40)]),
        "財務結構": _score(100 - debt_pct if debt_pct > 0 else -999, [(60, 80), (40, 60), (20, 40)]),
        "償債能力": 60 if ocf_k > 0 else 30,
    }

    return {
        "cash_ratio_status": cash_icon,
        "cash_ratio_value": f"{cash_pct}%",
        "ocf_status": ocf_icon,
        "ocf_value": f"{ocf_yi}億",
        "debt_ratio_status": debt_icon,
        "debt_ratio_value": f"{debt_pct}%",
        "radar_scores": radar,
        "business_model_dna": dna,
        "opm_data": {"payable_days": ap_days, "receivable_days": ar_days,
                     "advantage": ar_days > 0 and ap_days > ar_days},
        "ai_insight": "⚠️ AI 服務暫時不可用，以下為原始財報數據直接計算結果（無 AI 分析）。",
        "red_flags": "None",
    }


# ══════════════════════════════════════════════════════════════════
# §1 缺值三態：「這一輪沒拿到」≠「真的是 0」
# ══════════════════════════════════════════════════════════════════
# `fd.get(key, 0) or 0` 會把三件不同的事壓成同一個 0：
#   (a) key 根本不存在、(b) 值是 None、(c) 值**真的**是 0。
# 壓平之後那個 0 會被下游當成**觀測值**去判燈號 —— 「營收 0」算出
# 「本業虧損」、「毛利率 0%」被讀成「這門生意很差」。那是 CLAUDE.md §1
# 明令禁止的 `fillna(0)` 等價物，而且產出的是使用者可能拿去交易的假結論。
#
# ⚠️ **這裡不是把 0 換成另一個數字**：缺值一律回「未評估」，由 UI 畫成
# 灰態（§1.A 第 4 點：未載入／缺資料＝灰，系統真出錯＝紅）。
FIELD_ABSENT = "absent"   # key 不存在 / 值是 None / 值轉不成數字
FIELD_ZERO = "zero"       # 欄位在，值**真的**是 0
FIELD_VALUE = "value"     # 欄位在，值非 0

# ⚠️⚠️ **`FIELD_ABSENT` 在現行 fetcher 契約下對 production 資料永遠不會發生。**
# （2026-09-09 P0-B 稽核結論，據實標註；CLAUDE.md §-2 規則 6）
#   `src/data/core/financial_statements_fetcher.py` 的 `_v()` 查無時回 `0.0`、
#   **永遠不回 None**，且它的 return dict **每個 key 都必定存在且是數字**
#   （`prev_period_data` 同樣）。production 進到本引擎的 `fin_data` 只有這兩種
#   來源（其餘 caller 傳的都是它們的原封轉手；`{"error": ...}` 在
#   `analyze_financial_health` 開頭就被 `_FAIL_SAFE` 攔掉，走不到 `_read`）。
#
# **後果**：拿 `state == FIELD_ABSENT` 當「這一格缺漏」的偵測條件，
# 就是寫一個 production 恆為 False 的判斷式 —— 看起來有守衛、實際不觸發，
# 正是 §-2 規則 6 點名的 `db4c139` 型態。
#
# **本引擎因此的分工（P0-B 起）**：
#   * **production 的缺漏偵測一律走領域規則**（`_stmt_gap` / `!= FIELD_VALUE`
#     / `gp <= 0` / `assets <= 0` / 分母 `> 0` 這幾類），它們**會**觸發；
#   * `FIELD_ABSENT` 保留為**自組 dict 呼叫端**（值為 None / NaN / 不可轉數字）
#     的輸入驗證，並由 `tests/test_financial_health_missing_data.py` 涵蓋。
#     它**不是** production 守衛，任何地方**都不得**單靠它擋住一個假結論。
#   * 目前只剩兩處是「只有 `FIELD_ABSENT`」：毛利率①的前半、DIO 的存貨 ——
#     兩處都已就地標註，且兩處的 production 守衛另有活的領域規則（見該處）。


def _read(fd: dict, key: str) -> tuple[float, str]:
    """讀一個財報欄位 → `(值, 三態)`。**缺值不壓成 0。**

    Returns:
        `(0.0, FIELD_ABSENT)`：key 不存在／值是 None／值轉不成 float／NaN。
        `(0.0, FIELD_ZERO)`：欄位在、值真的是 0 —— **這是一個觀測值**；
            要不要把它當缺值，由呼叫端依該欄位的領域意義決定
            （例：營收 0 不可能是真的，見 `_income_gap`；
            存貨 0 對服務業是真的，就不該當缺值）。
        `(v, FIELD_VALUE)`：欄位在且非 0。
    """
    if not isinstance(fd, dict) or key not in fd:
        return 0.0, FIELD_ABSENT
    _raw = fd.get(key)
    if _raw is None or isinstance(_raw, bool):
        return 0.0, FIELD_ABSENT
    try:
        _v = float(_raw)
    except (TypeError, ValueError):
        return 0.0, FIELD_ABSENT
    if _v != _v:                       # NaN（§4.3 浮點：不用 == 比）
        return 0.0, FIELD_ABSENT
    return _v, (FIELD_VALUE if _v != 0 else FIELD_ZERO)


# 缺值時要顯示的字面。**一定帶原因** —— 光一個 "N/A" 使用者無從分辨
# 「這一輪沒抓到」與「算出來就是這樣」。
NA_NO_INCOME_STATEMENT = "N/A (損益表缺漏)"
NA_FIELD_ABSENT = "N/A (欄位缺漏)"
NA_INVENTORY_UNREADABLE = "N/A (存貨欄位無法讀取)"
NA_NO_TOTAL_ASSETS = "N/A (總資產缺漏)"
NA_UNIT_ANOMALY = "N/A (rev 單位異常)"          # v18 既有字面，未改
NA_NO_EQUITY = "N/A (股東權益缺漏)"
NA_GP_NON_POSITIVE = "N/A (毛利非正，安全邊際無意義)"
NA_NO_CASH = "N/A (現金／總資產缺漏)"
NA_INSUFFICIENT = "N/A (資料不足)"                # v18 既有字面，未改
NA_NO_CASHFLOW = "N/A (現金流量表缺漏)"
NA_NO_CURRENT_LIAB = "N/A (流動負債缺漏)"
NA_NO_CURRENT_ASSET = "N/A (流動資產缺漏)"
NA_NO_PPE = "N/A (固定資產缺漏)"
NA_NO_OPERATING_INCOME = "N/A (營業利益缺漏)"
NA_NO_NET_INCOME = "N/A (稅後淨利缺漏)"

#: `Data_Gap.missing` 的機器可讀值 —— UI 據此決定灰態要講哪一句，
#: 而不是自己去猜「為什麼是 N/A」。
GAP_INCOME_STATEMENT = "income_statement"
GAP_BALANCE_SHEET = "balance_sheet"
GAP_CASH_FLOW = "cash_flow_statement"


# ══════════════════════════════════════════════════════════════════
# §1 領域規則：**「0」對這些欄位不是一個可能的觀測值**
# ══════════════════════════════════════════════════════════════════
# ⚠️ **為什麼不能只靠 `FIELD_ABSENT`（2026-09-09 P0-B 稽核結論）**：
# `financial_statements_fetcher._v()` 查無時回 `0.0`、**永遠不回 None**，
# 而它的 return dict **每個 key 都必定存在**。也就是說在現行 fetcher 契約下
# `_read()` 對 production 資料**永遠不會**回 `FIELD_ABSENT` ——
# 拿 `state == FIELD_ABSENT` 當缺漏偵測，等於寫一個恆為 False 的判斷式
# （CLAUDE.md §-2 規則 6 點名的 `db4c139` 前例：宣稱修好、production 恆不觸發）。
#
# **真正能分辨「查無」與「真的是 0」的只有領域規則**：
# 上市櫃公司的營收／總資產／流動資產／流動負債／固定資產／營業利益／稅後淨利
# 都不會是 0，所以讀到 0 一律判缺漏。下面 `_stmt_gap()` 就是這條規則的唯一實作。
#
# ⛔ **反面同樣重要**：存貨（純服務業可以是 0）、現金股利（可以不配）、
# 資本支出（可以沒有）**不在**這條規則內 —— 那些 0 是真實觀測，
# 把它們也當缺漏就是**第二種說謊**（數字在手上卻對使用者說沒有）。

_GAP_WHY_ABSENT = "損益表這一輪沒有回來（欄位「營業收入(千)」不存在）"
_GAP_WHY_ZERO = ("損益表這一輪沒有回來（營業收入讀到 0；"
                 "上市櫃公司單季營收不會是 0，判為缺漏而非觀測值）")


def _stmt_gap(fd: dict, key: str, who: str,
              why_absent: str, why_zero: str) -> tuple[float, str]:
    """讀一個**不可能是 0** 的欄位 → `(值, 缺漏原因)`；原因空字串＝可以算。

    ⚠️ **「key 不存在」與「值讀到 0」在這裡分開判、分開寫 log**，但
    **兩者都回缺漏** —— 因為 0 當分母在數學上同樣算不出任何一個「率」。
    **分開的是原因，不是結論。**（現行 fetcher 契約下只會走到後者，
    前者是給自組 dict 的呼叫端用的，見上方註解。）
    """
    _val, _state = _read(fd, key)
    if _state == FIELD_ABSENT:
        _why = why_absent
    elif _val <= 0:
        _why = why_zero
    else:
        return _val, ""
    # §1 三律之(2)：顯式寫 log，說清楚哪個來源、為什麼。
    print(f"[FinHealth] ⚠️ {who}：{_why} → 相關指標一律回「未評估」，"
          f"不以 0 頂替（CLAUDE.md §1）")
    return _val, _why


def _income_gap(fd: dict, who: str) -> tuple[float, str]:
    """損益表這一輪回來了沒有 → `(營業收入, 缺漏原因)`；原因空字串＝可以算。

    **為什麼拿營收當 sentinel**：三張報表是分開抓的
    （`src/data/core/financial_statements_fetcher.py` 的 `_is` / `_bs` / `_cf`），
    損益表沒回來時**該表所有欄位會一起變 0**（該檔 `_v()` 查無回 `0.0`），
    不是只缺某一格。營收是損益表的第一列，也是所有「率」的分母 ——
    它不在，毛利率／營益率／淨利率／安全邊際**一個都算不出來**。
    """
    return _stmt_gap(fd, "營業收入(千)", who, _GAP_WHY_ABSENT, _GAP_WHY_ZERO)


_BS_WHY_ABSENT = "資產負債表這一輪沒有回來（欄位「總資產(千)」不存在）"
_BS_WHY_ZERO = ("資產負債表這一輪沒有回來（總資產讀到 0；"
                "上市櫃公司總資產不會是 0，判為缺漏而非觀測值）")


def _balance_gap(fd: dict, who: str) -> tuple[float, str]:
    """資產負債表這一輪回來了沒有 → `(總資產, 缺漏原因)`。

    **為什麼拿總資產當 sentinel**（與營收之於損益表同構）：
    它是資產負債表的合計行，而且 fetcher 在 `assets == 0` 時**已先試過**
    「流動＋非流動」兜底（`financial_statements_fetcher` 內 `資產合計查無` 那段）。
    連兜底都是 0 ⇒ 這張表**一格都沒解析出來**，不是只缺某一列。
    """
    return _stmt_gap(fd, "總資產(千)", who, _BS_WHY_ABSENT, _BS_WHY_ZERO)


def _no_ai_survival(fd: dict) -> dict:
    cash, _cash_state = _read(fd, "現金佔總資產(%)")
    # cash=0 代表「資產負債表這一輪沒回來」而非「這家公司現金為零」——
    # 掛牌公司現金不可能是總資產的 0%。原本壓成 0 會判 Fail，
    # 那是**拿缺資料當看空結論**，而且直接扣掉 `no_ai_overall_verdict`
    # 的「氣長」2 分（§1）。寫法同下面 DSO 的既有 N/A 慣例。
    if _cash_state != FIELD_VALUE or cash <= 0:
        cr_st, cr_val = "N/A", NA_NO_CASH
    else:
        cr_st = "Pass" if cash >= FH_CASH_RATIO_SAFE_PCT else ("Acceptable" if cash >= FH_CASH_RATIO_WATCH_PCT else "Fail")
        cr_val = f"{fd.get('現金佔總資產(%)')}%"
    ar = fd.get("應收帳款天數", 0) or 0
    # ar=0 代表資料查無，而非真的 0 天；用 N/A 避免誤判為 Pass
    if ar == 0:
        dso_st, dso_val = "N/A", "N/A (資料不足)"
    else:
        dso_st = "Pass" if ar < FH_DSO_FAST_DAYS else ("Acceptable" if ar <= FH_DSO_SLOW_DAYS else "Fail")
        dso_val = f"{ar:.1f} 天"
    ocf, ocf_state = _read(fd, "OCF(千)")
    # ⚠️ **2026-09-09 P0-B**：`OCF == 0` ＝ 現金流量表這一輪沒回來
    #    （`_v()` 查無回 `0.0`；真實企業單季營業活動現金流不會剛好是 0）。
    #    壓成 0 會讓 A 項 `ocf/cl` 與 C 項 `(ocf-div)/(ppe+lt)` 都算成
    #    **0.0% → Fail → 100-100-10 Fail → grade C →「建議換出」**，
    #    那是拿缺資料寫的看空結論（§1）。
    #    ⚠️ 判準**照抄同檔 `_no_ai_advanced_diagnostic` 的 `ocf_state != FIELD_VALUE`**
    #    —— 原本同一份輸出自相矛盾：盈餘含金量說「N/A (現金流量表缺漏)」，
    #    正上方 100-100-10 說「0.0% Fail」。同一個 0 不能有兩種讀法（§2.1 SSOT）。
    _cf_gap = ocf_state != FIELD_VALUE
    if _cf_gap:
        print("[FinHealth] ⚠️ 存活能力：現金流量表這一輪沒有回來"
              "（OCF 讀到 0／欄位不存在）→ 100-100-10 三項一律回「未評估」，"
              "不以 0 頂替（CLAUDE.md §1）")
    cl = fd.get("流動負債(千)", 0) or 0
    div = fd.get("現金股利(千)", 0) or 0
    ppe = fd.get("固定資產(千)", 0) or 0
    lt = fd.get("長期投資(千)", 0) or 0
    capex = fd.get("資本支出(千)", 0) or 0
    inv = fd.get("存貨(千)", 0) or 0
    inv_p = fd.get("存貨前期(千)", 0) or 0
    a_val = round(ocf / cl * 100, 1) if (cl > 0 and not _cf_gap) else None
    a_st = ("Pass" if a_val and a_val > FH_CASHFLOW_RATIO_MIN_PCT else "Fail") if a_val is not None else "N/A"
    # B項：現金流量允當比率
    # 1. 呼叫端預填 5 年精確值（fetch_5_years_cash_flow）→ 優先採用
    # 2. 預填 status=error（API 失敗）→ N/A，避免單季誤導
    # 3. 上市未滿 5 年 / 年份不足 → N/A 並標示原因
    # 4. 未預填 _b5 → 退回單季估算（legacy 路徑、unit test 使用）
    _b5 = fd.get("b_item_5y") or {}
    _b5_status = _b5.get("status")
    if _b5_status == "ok" and _b5.get("ratio") is not None:
        b_val     = _b5["ratio"]
        b_display = _b5["label"]                          # e.g. "127.3%（5年實際）"
        b_st      = "Pass" if b_val >= FH_CASHFLOW_ADEQUACY_MIN_PCT else "Fail"
    elif _b5_status == "insufficient_data":
        b_val, b_display, b_st = None, f"N/A（{_b5.get('label','上市未滿5年')}）", "Fail"
    elif _b5_status == "error":
        b_val, b_display, b_st = None, "N/A（5年歷史資料未取得）", "N/A"
    elif _cf_gap:
        # 單季估算路徑的分子也是 OCF —— 現金流量表沒回來就算不出來。
        b_val, b_display, b_st = None, NA_NO_CASHFLOW, "N/A"
    else:
        _inv_inc = max(inv - inv_p, 0)
        _b_denom = capex + _inv_inc + div
        if _b_denom <= 0:
            b_val, b_display, b_st = None, "N/A", "N/A"
        else:
            b_val = round(ocf / _b_denom * 100, 1)
            b_display = f"{b_val:.1f}%(1Q估)"
            b_st = "Pass" if b_val >= FH_CASHFLOW_ADEQUACY_MIN_PCT else "Fail"
    c_val = (round((ocf - div) / (ppe + lt) * 100, 1)
             if ((ppe + lt) > 0 and not _cf_gap) else None)
    c_st = ("Pass" if c_val and c_val > FH_CASH_REINVEST_MIN_PCT else "Fail") if c_val is not None else "N/A"
    # ⚠️ **三項全 N/A 不得判 Pass**（2026-09-09 P0-B 的鏡像失效模式）：
    #    原式「N/A 不計入失敗」在「一項都沒算出來」時會退化成
    #    **零筆資料開一張 100-100-10 及格證**，而它會進 `pass_items` 計 2 分。
    #    N/A 不計入失敗的前提是「至少有一項真的算出來了」。
    if a_st == b_st == c_st == "N/A":
        rule_st = "N/A"
    else:
        rule_st = "Pass" if (a_st in ("Pass", "N/A") and b_st in ("Pass", "N/A") and c_st in ("Pass", "N/A")) else "Fail"
    verdict = f"Cash={cr_st} DSO={dso_st} 100-100-10={rule_st}（無AI，原始計算）"
    return {"Survival_Module": {
        "Cash_Ratio": {"Value": cr_val, "Status": cr_st, "Insight": "原始數據直接計算"},
        "DSO_Speed": {"Value": dso_val, "Status": dso_st, "Insight": "原始數據直接計算"},
        "Rule_100_100_10": {
            # 缺值一定帶原因 —— 光一個 "N/A" 使用者無從分辨
            # 「現金流量表沒回來」與「分母（流動負債／固定資產）沒回來」。
            "Cash_Flow_Ratio": (f"{a_val}%" if a_val is not None
                                else (NA_NO_CASHFLOW if _cf_gap
                                      else NA_NO_CURRENT_LIAB)),
            "Cash_Flow_Adequacy": b_display,
            "Cash_Reinvestment": (f"{c_val}%" if c_val is not None
                                  else (NA_NO_CASHFLOW if _cf_gap
                                        else NA_NO_PPE)),
            "Status": rule_st,
            "Insight": (
                "原始數據直接計算（B項5年實際）" if _b5_status == "ok"
                else "原始數據直接計算（B項5年資料未取得）" if _b5_status == "error"
                # 現金流量表沒回來時說「單季估算」是**對使用者謊報有算過**。
                else "未評估（現金流量表這一輪沒有回來）" if _cf_gap
                else "原始數據直接計算（B項單季估算）"
            ),
        },
        "Final_Survival_Verdict": verdict,
        # §1 三律之(3)：輸出帶旗標。與獲利能力／財務結構的 `Data_Gap` 同構，
        # UI 據此畫灰態並講出對的那一句，不必自己猜「為什麼是 N/A」。
        **({"Data_Gap": {"missing": GAP_CASH_FLOW, "field": "OCF(千)",
                         "why": "現金流量表這一輪沒有回來"
                                "（OCF 讀到 0／欄位不存在）"}}
           if _cf_gap else {}),
    }}


def _no_ai_operating(fd: dict) -> dict:
    """經營能力（DSO/DIO/DPO + 翻桌率）。**分母缺 → N/A，不回 0 天 / 0.00x。**

    ⚠️ 「DIO 0.0 天」「DPO 0.0 天」「翻桌率 0.00x」看起來都像**有效觀測**
    （零庫存的完美公司／當天付清的好人／完全不做生意），實際上是
    「營業成本與營收這一輪沒回來」。畫出來就是造假（§1.A 第 1 點）。
    """
    ar, _ = _read(fd, "應收帳款天數")
    ap, _ = _read(fd, "應付帳款天數")
    inv, _inv_state = _read(fd, "存貨(千)")
    cogs, _ = _read(fd, "營業成本(千)")
    rev, _gap = _income_gap(fd, "經營能力")
    assets, _ = _read(fd, "總資產(千)")
    # 年化：單季 cogs/rev × 4，DIO 才能與 DSO/DPO 規模一致。
    # 分母（營業成本 → 退而求其次用營收）兩個都沒有 → **算不出來**。
    # ⚠️ 存貨真的是 0（純服務業）是**真實觀測**，照算 0.0 天，不當缺值。
    if cogs > 0 or rev > 0:
        _dio_denom = (cogs * 4) if cogs > 0 else (rev * 4)
        # ⚠️ **這一條的 `FIELD_ABSENT` 在現行 fetcher 契約下不會發生**
        #    （`_v()` 查無回 0.0、key 必定存在），留著是給**自組 dict 的
        #    呼叫端**（值為 None/NaN）的輸入驗證，不是 production 守衛。
        #    **這裡不能改成 `!= FIELD_VALUE`** —— 存貨真的是 0（純服務業）
        #    是**真實觀測**，把它當缺漏就是第二種說謊（數字在手上卻說沒有）。
        #    DIO 在 production 的守衛是上面那個分母條件（cogs/rev），那條是活的。
        dio_num = (round(inv / _dio_denom * 360, 1)
                   if _inv_state != FIELD_ABSENT else None)
        dio_str = f"{dio_num:.1f} 天" if dio_num is not None else NA_INVENTORY_UNREADABLE
    else:
        dio_num, dio_str = None, (NA_NO_INCOME_STATEMENT if _gap
                                  else NA_INSUFFICIENT)
    # ar=0 代表資料查無；完整週期/資金缺口用 N/A 表示
    dso_str = f"{ar:.1f} 天" if ar > 0 else NA_INSUFFICIENT
    # ap=0 同 ar：應付天數 0 不是「當天付清」，是營業成本或應付帳款沒回來。
    dpo_str = f"{ap:.1f} 天" if ap > 0 else NA_INSUFFICIENT
    if ar > 0 and dio_num is not None:
        cycle_str = f"{round(ar + dio_num, 1):.1f} 天"
        gap_str = (f"{round(ar + dio_num - ap, 1):.1f} 天" if ap > 0
                   else "N/A (DPO缺失)")
    elif dio_num is not None:
        cycle_str = f"N/A (DSO缺失，DIO={dio_num:.1f}天)"
        gap_str = "N/A (DSO缺失)"
    else:
        cycle_str = "N/A (DSO/DIO 皆缺)"
        gap_str = "N/A (DSO/DIO 皆缺)"
    # 年化：單季 rev × 4。營收或總資產缺 → 翻桌率**未評估**（不是 0.00x）。
    if _gap or assets <= 0:
        at_str = NA_NO_INCOME_STATEMENT if _gap else NA_NO_TOTAL_ASSETS
    else:
        at_str = f"{round((rev * 4) / assets, 2):.2f}x"
    if ar <= 0:
        opm = "N/A (DSO缺失，無法判定)"
    elif ap <= 0:
        opm = "N/A (DPO缺失，無法判定)"
    else:
        opm = "Yes" if ap > ar else "No"
    return {"Operating_Module": {
        "DSO": dso_str, "DIO": dio_str, "DPO": dpo_str,
        "Complete_Cycle": cycle_str, "Cash_Gap_Days": gap_str,
        "OPM_Strategy": opm, "Asset_Turnover": at_str,
        "Verdict": "原始數據直接計算（無 AI 分析）",
    }}


def _no_ai_profitability(fd: dict) -> dict:
    """獲利 5 大指標（純計算）。**缺營收 → 五項全部「未評估」，不回 0。**

    ⚠️ **這裡就是 2026-09-09 P0 修的那條鏈**：
    `rev` 缺 → `om = 0` → `Core_Business_Profitable = "No"` →
    畫面寫「本業虧損」，而 `no_ai_overall_verdict` 把它算成一項 Fail →
    體質掉到 C。**一份沒回來的損益表，被講成一家虧錢的公司。**
    使用者可能拿這個結論去交易 —— 這是 CLAUDE.md §1
    「錯誤的數字比沒有數字更危險」的教科書案例。
    """
    rev, _gap = _income_gap(fd, "獲利能力")
    gm, gm_state = _read(fd, "毛利率(%)")
    gp, gp_state = _read(fd, "毛利(千)")
    oi, oi_state = _read(fd, "營業利益(千)")
    ni, ni_state = _read(fd, "稅後淨利(千)")
    eq, eq_state = _read(fd, "股東權益(千)")
    debt, _ = _read(fd, "負債比率(%)")
    # ── 數據健全性檢查：oi/ni 不應大於 rev（單位錯亂或子科目誤抓）──────
    _bad_om = rev > 0 and abs(oi) > rev * 1.2
    _bad_nm = rev > 0 and abs(ni) > rev * 1.2

    # ── ① 毛利率：欄位自帶百分比，不經 rev 換算 ──────────────────
    # **rev 在手上而 gm 真的是 0（毛利＝成本）是一個真實觀測 → 照實顯示**；
    # 只有「欄位不在」或「讀到 0 而損益表本身就沒回來」才算缺值。
    # 線框原話：「『0% 毛利』是一個結論，不是『沒有資料』。」
    # ⚠️ 前半的 `FIELD_ABSENT` 同 DIO：現行 fetcher 契約下不會發生，
    #    留作自組 dict 的輸入驗證。**在 production 生效的是後半那條領域規則**
    #    （毛利率讀到 0 **且** 損益表本身沒回來 → 缺漏）。
    if gm_state == FIELD_ABSENT or (gm_state == FIELD_ZERO and _gap):
        gm_val = NA_NO_INCOME_STATEMENT if _gap else NA_FIELD_ABSENT
        gm_st = "N/A"
    else:
        gm_val = f"{gm:.1f}%"
        gm_st = "Good" if gm >= FH_GROSS_MARGIN_GOOD_PCT else "Average"

    # ── ② 營業利益率 / 本業是否賺錢 ─────────────────────────────
    if _gap:
        om_val, om_cbp = NA_NO_INCOME_STATEMENT, "N/A"
    elif oi_state != FIELD_VALUE:
        # ⚠️ **2026-09-09 P0-B**：原式寫 `oi_state == FIELD_ABSENT`，
        #    而 fetcher 的 `_v()` 查無回 `0.0`（不回 None）→ 那個判斷式
        #    在 production **恆為 False**，`oi == 0` 會掉進下面的 else 算成
        #    `om = 0.0%` → `Core_Business_Profitable = "No"` → 畫面寫「本業虧損」。
        #    **這就是 P0 修好的那條鏈，只是換一個欄位重演一次。**
        #    改用領域規則（`!= FIELD_VALUE` ＝ 缺 ∪ 讀到 0）：上市櫃公司單季
        #    營業利益不會剛好是 0，讀到 0 一律判缺漏。
        om_val, om_cbp = NA_NO_OPERATING_INCOME, "N/A"
    elif _bad_om:
        om_val, om_cbp = NA_UNIT_ANOMALY, "N/A"
    else:
        om = round(oi / rev * 100, 1)
        om_val, om_cbp = f"{om:.1f}%", ("Yes" if om > 0 else "No")

    # ── ③ 安全邊際 = 營業利益 / 毛利（line 153 docs）─────────────
    if _gap:
        mos_val, mos_st = NA_NO_INCOME_STATEMENT, "N/A"
    elif oi_state != FIELD_VALUE:
        # 同 ②：`== FIELD_ABSENT` 恆為 False，改領域規則。
        # （`gp` 側不必另判 —— 下面 `gp <= 0` 已經把「毛利缺漏／毛損」
        #   一起接住，那條本來就是領域規則、本來就會觸發。）
        mos_val, mos_st = NA_NO_OPERATING_INCOME, "N/A"
    elif _bad_om:
        mos_val, mos_st = NA_UNIT_ANOMALY, "N/A"
    elif gp <= 0:
        # 毛損（或毛利讀到 0）→ oi/gp **不是**「抗震尚可」，是算不出來。
        # 原本回 0 會落在 `mos >= 0` 那一階 → 拿缺值換到一張及格證。
        mos_val, mos_st = NA_GP_NON_POSITIVE, "N/A"
    else:
        mos = round(oi / gp * 100, 1)
        mos_val = f"{mos:.1f}%"
        # v18.323 漂移修正：安全邊際 Strong 線 20→60（對齊經典標準，保三階）
        mos_st = ("Strong" if mos >= FH_MOS_STRONG_PCT
                  else ("Acceptable" if mos >= 0 else "Weak"))

    # ── ④ 稅後淨利率 ───────────────────────────────────────────
    if _gap:
        nm_val, nm_st = NA_NO_INCOME_STATEMENT, "N/A"
    elif ni_state != FIELD_VALUE:
        # 同 ②。⚠️ **真的虧損（ni < 0）是 FIELD_VALUE，照常判 "Loss"** ——
        # 這條只擋「讀到 0」，不擋負數。
        nm_val, nm_st = NA_NO_NET_INCOME, "N/A"
    elif _bad_nm:
        nm_val, nm_st = NA_UNIT_ANOMALY, "N/A"
    else:
        nm = round(ni / rev * 100, 1)
        nm_val = f"{nm:.1f}%"
        nm_st = ("Pass" if nm >= FH_NET_MARGIN_PASS_PCT
                 else ("Thin Profit" if nm >= 0 else "Loss"))

    # ── ⑤ ROE：不需要 rev，但需要淨利（損益表）＋ 股東權益（資產負債表）
    # ⚠️ **缺值走 `Value` 表達，`Leverage_Warning` 一律留在 "None"** ——
    #    後者同時被 `src/ui/tabs/tab_stock.py` 與 `compute/health/fin_health_diff.py`
    #    讀成「有沒有槓桿警報」（`!= 'None'` → 亮警示）。在那裡塞第三個值
    #    會把「沒有資料」變成「有警報」，等於用 §1 的鏡像失效模式修 §1。
    #    下游 `no_ai_overall_verdict` 改讀 `ROE.Value` 判缺值。
    if _gap or ni_state != FIELD_VALUE:
        roe_val = NA_NO_INCOME_STATEMENT if _gap else NA_NO_NET_INCOME
        roe_warn = "None"
    elif eq_state != FIELD_VALUE or eq <= 0:
        roe_val, roe_warn = NA_NO_EQUITY, "None"
    else:
        roe = round((ni * 4) / eq * 100, 1)  # 年化：單季 NI × 4
        roe_val = f"{roe:.1f}%"
        roe_warn = ("槓桿膨脹警報"
                    if roe > FH_ROE_LEVERAGE_CHECK_PCT
                    and debt > FH_DUPONT_LEVERAGE_DEBT_PCT else "None")

    _mod = {
        "Gross_Margin": {"Value": gm_val, "Status": gm_st},
        "Operating_Margin": {"Value": om_val,
                             "Core_Business_Profitable": om_cbp},
        "Margin_Of_Safety": {"Value": mos_val, "Status": mos_st},
        "Net_Margin": {"Value": nm_val, "Status": nm_st},
        "ROE": {"Value": roe_val, "Leverage_Warning": roe_warn},
        "Final_Insight": "原始數據直接計算（無 AI 分析）",
    }
    if _gap:
        # §1 三律之(3)：**輸出帶旗標**。UI 據此講出「損益表這一輪沒有回來」
        # 那一句灰態文案，而不是自己猜「為什麼是 N/A」。
        _mod["Data_Gap"] = {"missing": GAP_INCOME_STATEMENT,
                            "field": "營業收入(千)", "why": _gap}
        _mod["Final_Insight"] = f"未評估：{_gap}"
    return {"Profitability_Module": _mod}


def _no_ai_financial_structure(fd: dict) -> dict:
    # §1 三律之(3)：整張資產負債表沒回來時**輸出帶旗標**，
    # 讓 `no_ai_overall_verdict` 不必自己猜（用法與獲利能力的 `Data_Gap` 同構）。
    # ⚠️ 只加旗標，**不動**下面既有的負債比率兜底邏輯（另案，見交付報告登記）。
    _bs_gap = _balance_gap(fd, "財務結構")[1]
    is_finance = fd.get("is_finance", False)
    debt   = fd.get("負債比率(%)", 0) or 0
    eq     = fd.get("股東權益(千)", 0) or 0
    lt_liab = fd.get("非流動負債(千)", 0) or 0
    ppe    = fd.get("固定資產(千)", 0) or 0

    # ── 負債比率兜底：當上游 debt_ratio=0 時，從原始欄位自行重算 ──────
    if debt == 0 and not is_finance:
        _tl = fd.get("總負債(千)", 0) or 0
        _ta = fd.get("總資產(千)", 0) or 0
        _cl = fd.get("流動負債(千)", 0) or 0
        _ca = fd.get("流動資產(千)", 0) or 0
        _eff_liab = _tl if _tl > 0 else _cl          # 優先總負債，否則流動負債
        if _ta > 0:
            _eff_assets = _ta
        elif eq > 0 and _eff_liab > 0:
            _eff_assets = eq + _eff_liab              # IFRS: 資產 = 負債 + 權益
        else:
            _eff_assets = _ca + (fd.get("固定資產(千)", 0) or 0)
        if _eff_liab > 0 and _eff_assets > 0:
            debt = round(_eff_liab / _eff_assets * 100, 1)
            if lt_liab == 0 and _tl > _cl > 0:
                lt_liab = _tl - _cl
    if ppe > 0:
        if eq == 0 and lt_liab == 0:
            lt_st, lt_val = "N/A", "N/A (股東權益資料不足)"
        elif eq > 0 and eq < ppe * 0.001:
            # equity 極小（< 0.1% of ppe），疑似欄位誤配，避免計算出荒謬的 0%
            lt_st, lt_val = "N/A", "N/A (股東權益資料異常)"
        else:
            lt_ratio = round((eq + lt_liab) / ppe * 100, 1)
            lt_st = "Pass" if lt_ratio >= FH_LONG_TERM_FUNDING_MIN_PCT else "Fail"
            lt_val = f"{lt_ratio:.1f}%"
    else:
        # ⚠️ **2026-09-09 P0-B**：原本 `ppe == 0` 走「Pass ＋ N/A (輕資產)」。
        #    但 `_v()` 查無回 `0.0`，**`ppe == 0` 的意思是「這一格沒解析出來」**，
        #    不是「這家公司沒有固定資產」—— 上市櫃公司（含純軟體業）
        #    都會列報不動產、廠房及設備。拿缺值換一張 Pass ＝ §1 的假正結論，
        #    而且它會直接進 `no_ai_overall_verdict` 的 `pass_items` 計 2 分。
        lt_st, lt_val = "N/A", NA_NO_PPE
    # 金融特許行業：負債高槓桿屬正常，不適用一般比率標準
    if is_finance:
        debt_st, debt_val = "N/A", f"N/A (金融特許行業)" if debt == 0 else f"{debt:.1f}% (金融業)"
    elif debt == 0:
        debt_st, debt_val = "N/A", "N/A (負債資料不足)"
    else:
        debt_st = "Pass" if debt < FH_DEBT_RATIO_PASS_PCT else ("Warning" if debt <= FH_DEBT_RATIO_WARN_PCT else "Fail")
        debt_val = f"{debt:.1f}%"
    _mod = {
        "Debt_Ratio": {"Value": debt_val, "Status": debt_st},
        "Long_Term_Funding_Ratio": {"Value": lt_val, "Status": lt_st},
        "Final_Insight": "原始數據直接計算（無 AI 分析）",
    }
    if _bs_gap:
        _mod["Data_Gap"] = {"missing": GAP_BALANCE_SHEET,
                            "field": "總資產(千)", "why": _bs_gap}
        _mod["Final_Insight"] = f"未評估：{_bs_gap}"
    return {"Financial_Structure_Module": _mod}


_CL_WHY_ABSENT = "流動負債這一格沒有回來（欄位「流動負債(千)」不存在）"
_CL_WHY_ZERO = ("流動負債這一格沒有回來（讀到 0；"
                "上市櫃公司流動負債不會是 0，判為缺漏而非觀測值）")
_CA_WHY_ABSENT = "流動資產這一格沒有回來（欄位「流動資產(千)」不存在）"
_CA_WHY_ZERO = ("流動資產這一格沒有回來（讀到 0；"
                "上市櫃公司流動資產不會是 0，判為缺漏而非觀測值）")


def _no_ai_solvency(fd: dict) -> dict:
    """短期償債（流動／速動比率）。**分母缺 → 整組未評估，不發及格證。**

    ⚠️ **2026-09-09 P0-B 修的就是這裡**：原本 `cl == 0` 走
    「Pass (無短期債務)」＋「無短期負債，資金壓力極低」，還在
    `no_ai_overall_verdict` 拿滿分 2 分、進 `pass_items`。
    但 `financial_statements_fetcher._v()` 查無時回 `0.0` ——
    **`cl == 0` 在 production 的意思是「資產負債表沒回來」，
    不是「這家公司沒有短期負債」**。上市櫃公司流動負債不可能是 0。
    **一張沒回來的表換到兩張及格證**，比假的負結論更容易讓人買進（§1）。
    """
    ca, _ca_gap = _stmt_gap(fd, "流動資產(千)", "償債能力",
                            _CA_WHY_ABSENT, _CA_WHY_ZERO)
    cl, _cl_gap = _stmt_gap(fd, "流動負債(千)", "償債能力",
                            _CL_WHY_ABSENT, _CL_WHY_ZERO)
    inv = fd.get("存貨(千)", 0) or 0
    cash_pct = fd.get("現金佔總資產(%)", 0) or 0
    ar_days = fd.get("應收帳款天數", 0) or 0
    if _cl_gap or _ca_gap:
        # ⚠️ 兩個方向都要擋：分母（cl）缺會換到假的「無短期債務 Pass」；
        #    分子（ca）缺會算出 0.0% → `Fail_Initial` 假的負結論。
        _why = _cl_gap or _ca_gap
        _val = NA_NO_CURRENT_LIAB if _cl_gap else NA_NO_CURRENT_ASSET
        return {"Solvency_Module": {
            "Current_Ratio": {"Value": _val, "Status": "N/A"},
            "Quick_Ratio": {"Value": _val, "Status": "N/A"},
            "Cross_Validation_Applied": "No",
            "Final_Solvency_Verdict": "N/A",
            "Final_Insight": f"未評估：{_why}",
            # §1 三律之(3)：輸出帶旗標，下游不必自己猜「為什麼是 N/A」。
            "Data_Gap": {"missing": GAP_BALANCE_SHEET,
                         "field": "流動負債(千)" if _cl_gap else "流動資產(千)",
                         "why": _why},
        }}
    cr = round(ca / cl * 100, 1)
    qr = round((ca - inv) / cl * 100, 1)
    cr_st = "Pass" if cr > FH_CURRENT_RATIO_MIN_PCT else "Fail_Initial"
    qr_st = "Pass" if qr > FH_QUICK_RATIO_MIN_PCT else "Fail_Initial"
    cross = cr_st == "Fail_Initial" or qr_st == "Fail_Initial"
    if not cross:
        verdict, cv = "Pass", "No"
    elif cash_pct > FH_CASH_RATIO_SAFE_PCT:
        verdict, cv = "Exception_Pass (條件A：現金充足)", "Yes"
    elif 0 < ar_days <= FH_DSO_FAST_DAYS:
        verdict, cv = "Exception_Pass (條件B：天天收現)", "Yes"
    else:
        verdict, cv = "Fail", "Yes"
    return {"Solvency_Module": {
        "Current_Ratio": {"Value": f"{cr:.1f}%", "Status": cr_st},
        "Quick_Ratio": {"Value": f"{qr:.1f}%", "Status": qr_st},
        "Cross_Validation_Applied": cv,
        "Final_Solvency_Verdict": verdict,
        "Final_Insight": "原始數據直接計算（無 AI 分析）",
    }}


def _no_ai_advanced_diagnostic(fd: dict) -> dict:
    ocf, ocf_state = _read(fd, "OCF(千)")
    ni, ni_state = _read(fd, "稅後淨利(千)")
    eq, eq_state = _read(fd, "股東權益(千)")
    debt, _ = _read(fd, "負債比率(%)")
    ar_chg = fd.get("應收帳款季增率(%)")
    rev_chg = fd.get("營收季增率(%)")
    inv, _ = _read(fd, "存貨(千)")
    inv_p, _ = _read(fd, "存貨前期(千)")
    _, _gap = _income_gap(fd, "綜合診斷")
    # 盈餘含金量 = OCF / 稅後淨利。
    # ⚠️ 原本 ni 缺（壓成 0）與 ni 真的 ≤ 0 共用同一句
    #    「N/A (本業虧損，不適用此指標)」—— 損益表沒回來時，
    #    那句話是**憑空替公司下的虧損判決**（雖然 Status 同為 N/A，
    #    使用者看到的字面是「本業虧損」）。三態拆開講。
    if _gap or ni_state != FIELD_VALUE:
        eq_val, eq_st = (NA_NO_INCOME_STATEMENT if _gap
                         else NA_NO_NET_INCOME), "N/A"
    elif ni <= 0:
        eq_val, eq_st = "N/A (本業虧損，不適用此指標)", "N/A"
    elif ocf_state != FIELD_VALUE:
        # OCF 讀到 0 ＝ 現金流量表沒回來（真實企業單季 OCF 不會剛好是 0）。
        # 壓成 0 會算出「含金量 0%」→ 紅燈「紙上富貴」，那是假結論。
        eq_val, eq_st = NA_NO_CASHFLOW, "N/A"
    else:
        eq_pct = round(ocf / ni * 100, 1)
        eq_val, eq_st = f"{eq_pct:.1f}%", "Pass" if eq_pct >= FH_EARNINGS_QUALITY_MIN_PCT else "Fail"
    # 杜邦：ROE 算不出來就不要講故事。原本 eq 或 ni 缺 → roe=0 →
    # 直接輸出「⚠️ ROE 為負，本業虧損」，是拿缺資料寫的看空敘事。
    if _gap or ni_state != FIELD_VALUE or eq_state != FIELD_VALUE or eq <= 0:
        dupont = "N/A (資料不足，未評估 ROE)"
    else:
        roe = round((ni * 4) / eq * 100, 1)  # 年化：單季 NI × 4
        dupont = ("槓桿膨脹警報" if roe > FH_ROE_LEVERAGE_CHECK_PCT and debt > FH_DUPONT_LEVERAGE_DEBT_PCT else
                  ("健康成長" if roe > FH_ROE_LEVERAGE_CHECK_PCT else
                   ("ROE 偏低，成長動能不足" if roe > 0 else "⚠️ ROE 為負，本業虧損")))
    if ar_chg is not None and rev_chg is not None and inv_p > 0:
        inv_chg = round((inv - inv_p) / abs(inv_p) * 100, 1)
        dh = "Triggered (危險)" if (ar_chg > (rev_chg or 0) and inv_chg > (rev_chg or 0)) else "Clear (安全)"
    else:
        dh = "N/A (資料不足)"
    _dna_map = {
        ("正", "負", "負"): "A+ 穩健印鈔機",
        ("正", "負", "正"): "成長擴張型",
        ("正", "正", "負"): "變賣祖產型（⚠️ 請確認原因）",
        ("正", "正", "正"): "D 燒錢模式",
        ("負", "負", "負"): "E 衰退縮減",
        ("負", "正", "負"): "瀕死型（🔴 極度危險）",
        ("負", "負", "正"): "燒錢新創型（需觀察現金消耗速度）",
        ("負", "正", "正"): "H 危機警戒",
    }
    dna = _dna_map.get((fd.get("OCF符號","負"), fd.get("ICF符號","負"), fd.get("籌資CF符號","負")), "特殊組合（需個案分析）")
    return {"Advanced_Diagnostic_Module": {
        "Earnings_Quality": {"Value": eq_val, "Status": eq_st},
        "DuPont_Health": dupont,
        "Double_High_Warning": dh,
        "Business_DNA": dna,
        "Final_Verdict": "原始數據直接計算（無 AI 分析）",
    }}


# ── Fail-safe 預設值 ────────────────────────────────────────
_FAIL_SAFE: dict = {
    "cash_ratio_status": "🔴",
    "cash_ratio_value": "N/A",
    "ocf_status": "🔴",
    "ocf_value": "N/A",
    "debt_ratio_status": "🔴",
    "debt_ratio_value": "N/A",
    "radar_scores": {
        "存活能力": 0, "經營能力": 0, "獲利能力": 0,
        "財務結構": 0, "償債能力": 0,
    },
    "business_model_dna": "無法判斷（資料不足）",
    "opm_data": {"payable_days": 0, "receivable_days": 0, "advantage": False},
    "ai_insight": "財報資料載入失敗，無法進行體檢分析。請確認 FINMIND_TOKEN 已設定。",
    "red_flags": "None",
    "error": True,
}


def no_ai_overall_verdict(fin_data: dict, fh_result: dict) -> dict:
    """
    彙整六大模組，生成財報體檢風格的動態總結論（純計算，無 AI）。
    """
    surv = fh_result.get("survival_module", {})
    prof = fh_result.get("profitability_module", {})
    fstr = fh_result.get("financial_structure_module", {})
    solv = fh_result.get("solvency_module", {})
    adv  = fh_result.get("advanced_diagnostic_module", {})

    def _pts(s):
        # ⚠️ 2026-09-09 P0-B 移除 `"Pass (無短期債務)": 2` —— `_no_ai_solvency`
        #    不再產出那個字串（`cl == 0` 現在判缺漏），留著就是一筆恆不命中的
        #    對照（CLAUDE.md §-2 規則 6 點名的死碼型態）。
        return {"Pass": 2, "Acceptable": 1, "Good": 2, "Strong": 2,
                "Exception_Pass": 1,
                "Warning": -1, "Fail": -2, "Fail_Initial": -1, "Thin Profit": -1}.get(str(s), 0)

    # ⚠️ 缺值不得落進任一結論欄。原寫法 `== "Yes" else "Fail"` 把
    #    `Core_Business_Profitable = "N/A"`（損益表沒回來）算成**一項失敗**，
    #    正是 2026-09-09 P0「半份財報 → 體質 C 級」的最後一段。
    _om_slot = prof.get("Operating_Margin", {})
    _cbp = str(_om_slot.get("Core_Business_Profitable", "") or "")
    _roe_slot = prof.get("ROE", {})
    # ROE 缺值看 `Value`，不看 `Leverage_Warning` —— 後者刻意留在 "None"
    #（理由見 `_no_ai_profitability` ⑤ 的註解：那個欄位在 UI 端是「有無警報」）。
    _roe_na = "N/A" in str(_roe_slot.get("Value", ""))

    checks = [
        ("氣長",       surv.get("Cash_Ratio", {}).get("Status", "N/A")),
        ("收現速度",   surv.get("DSO_Speed", {}).get("Status", "N/A")),
        ("100-100-10", surv.get("Rule_100_100_10", {}).get("Status", "N/A")),
        ("毛利率",     prof.get("Gross_Margin", {}).get("Status", "N/A")),
        ("本業獲利",   "Pass" if _cbp == "Yes" else ("Fail" if _cbp == "No" else "N/A")),
        ("ROE品質",    "N/A" if _roe_na else
                       ("Warning" if _roe_slot.get("Leverage_Warning", "None") != "None" else "Pass")),
        ("負債比率",   fstr.get("Debt_Ratio", {}).get("Status", "N/A")),
        ("以長支長",   fstr.get("Long_Term_Funding_Ratio", {}).get("Status", "N/A")),
        ("流動比率",   solv.get("Current_Ratio", {}).get("Status", "N/A")),
        ("盈餘含金量", adv.get("Earnings_Quality", {}).get("Status", "N/A")),
        ("雙高危機",   "Fail" if "Triggered" in str(adv.get("Double_High_Warning", ""))
                      else "Pass" if "Clear" in str(adv.get("Double_High_Warning", "")) else "N/A"),
    ]
    valid      = [(n, s) for n, s in checks if s != "N/A"]
    total_pts  = sum(_pts(s) for _, s in valid)
    max_pts    = len(valid) * 2
    score_pct  = round(total_pts / max_pts * 100) if max_pts > 0 else 50
    pass_items = [n for n, s in valid if _pts(s) >= 2]
    fail_items = [n for n, s in valid if _pts(s) < 0]
    dna        = adv.get("Business_DNA", "")
    is_cashcow = "A+" in str(dna)
    is_dying   = "瀕死" in str(dna)
    ocf        = fin_data.get("OCF(千)", 0) or 0
    eq_ok      = adv.get("Earnings_Quality", {}).get("Status", "") == "Pass"

    # ⚠️ **鏡像失效模式（2026-09-09 修 P0 時實測抓到，必須一起擋）**：
    #    把「本業虧損」改成 N/A 之後，缺營收那一檔的 `fail_items` 會變空，
    #    於是同一份**半份財報**從「體質 C 級」翻成
    #    「🟢 印鈔機！A+ 型企業，策略2 最愛標的」——
    #    **假的正結論跟假的負結論一樣危險**，而且更容易讓人買進。
    #    財報體檢少了整張損益表就不成立（獲利面 5 項全部沒評到），
    #    依 §1 fail loud：**不評等**，把算得出來的那幾項照實列出。
    _skipped = [_n for _n, _s in checks if _s == "N/A"]
    # ⚠️ **2026-09-09 P0-B：同一個 gate 必須涵蓋資產負債表。**
    #    P0 只把「損益表缺漏 → 不評等」修好，但**整張資產負債表沒回來**時，
    #    `cl == 0` 換到「Pass (無短期債務)」、`ppe == 0` 換到「Pass (輕資產)」——
    #    **一張沒回來的表換到兩張及格證**，總評被推到 A+「印鈔機」。
    #    把那兩格改成 N/A 之後**還是 A+**（實測），因為 `fail_items` 一樣是空的：
    #    **少評幾項不會讓等級變差，只會讓它變好。** 所以 gate 必須設在
    #    「整張表在不在」，不能只設在單格。
    #    ⛔ 旗標一律讀 `fh_result`（模組自己掛的），**不從 `fin_data` 現算** ——
    #    `tab_stock.py` 有一處傳 `session_state.get('t2_fin_data', {})`，
    #    現算會把「呼叫端沒帶 fin_data」誤判成「公司沒有資產負債表」。
    _stmt_gaps = [
        (_name, str(_slot.get("Data_Gap", {}).get("why") or _fallback))
        for _name, _slot, _fallback in (
            ("損益表", prof, "損益表缺漏"),
            ("資產負債表", fstr, "資產負債表缺漏"),
        ) if _slot.get("Data_Gap")
    ]
    if _stmt_gaps:
        _why_gap = "；".join(_w for _, _w in _stmt_gaps)
        _detail = ("沒有營收就算不出任何一個「率」，獲利面 5 項全部未評估。"
                   if prof.get("Data_Gap") else "")
        _detail += ("沒有資產負債表就沒有分母，償債能力／財務結構／以長支長"
                    "全部未評估。" if fstr.get("Data_Gap") else "")
        return {
            "grade": "N/A", "grade_color": TRAFFIC_NEUTRAL,
            "headline": "⬜ 只拿到一半的財報，本輪不評等",
            "comment": (f"{_why_gap}。{_detail}"
                        f"—— **本站不拿 0 頂替，也不會用"
                        f"剩下半份財報發一張體質等級**。"
                        + (f"這一輪仍算得出來的是：{'、'.join(pass_items)}。"
                           if pass_items else "")
                        + (f"未評估 {len(_skipped)} 項：{'、'.join(_skipped)}。"
                           if _skipped else "")),
            "score_pct": None,
            "pass_count": len(pass_items), "fail_count": len(fail_items),
            "pass_items": pass_items, "fail_items": fail_items, "dna": dna,
        }

    if not valid:
        # ⚠️ 一項指標都算不出來時，原本會一路掉到最後的 else，
        #    發出「🔵 財務穩定，中規中矩」＋ score_pct=50 ——
        #    **用零筆資料開一張及格證書**，是 §1 的反面（假的正結論）。
        #    `grade="N/A"` 在 `compute/scoring/unified_verdict.py`
        #    的 `fundamental_grade_to_state()` 落在「未知 → None」，
        #    下游會走 coverage 缺值路徑，不會被誤讀成任何一階。
        return {
            "grade": "N/A", "grade_color": TRAFFIC_NEUTRAL,
            "headline": "⬜ 財報資料不足，本輪不評等",
            "comment": ("這一輪沒有任何一項體檢指標算得出來（三張財報都沒回來，"
                        "或欄位全數缺漏）。**這是「沒有資料」，不是「體質差」** —— "
                        "本站不拿缺值去湊一個等級。稍後重試，或到資料診斷頁看備援鏈。"),
            "score_pct": None,
            "pass_count": 0, "fail_count": 0,
            "pass_items": [], "fail_items": [], "dna": dna,
        }

    if is_dying or len(fail_items) >= 4:
        grade, gc = "F", TRAFFIC_RED
        headline  = "🔴 高危企業！多項生死指標亮紅燈"
        comment   = (f"財務健康嚴重失衡，共 **{len(fail_items)}** 項指標觸警："
                     f"{'、'.join(fail_items[:4])}{'…' if len(fail_items) > 4 else ''}。"
                     f"請確認是否為財報資料異常，或確實存在財務困境。")
    elif len(fail_items) >= 2:
        grade, gc = "C", TRAFFIC_YELLOW
        headline  = "🟡 有明顯改善空間，需謹慎評估"
        comment   = (f"關鍵警示：**{'、'.join(fail_items)}**。"
                     f"{'盈餘含金量高，現金流尚佳。' if eq_ok else ''}"
                     f"建議與同業比較，判斷是結構性問題還是短期壓力。")
    elif len(fail_items) == 1:
        grade, gc = "B+", TRAFFIC_YELLOW
        headline  = "🟡 大致穩健，單點需留意"
        comment   = (f"整體財務健康，但「**{fail_items[0]}**」尚需改善。"
                     f"{'其餘 ' + str(len(pass_items)) + ' 項指標達標。' if pass_items else ''}"
                     f"若下季持續改善，可列入重點追蹤。")
    elif is_cashcow:
        grade, gc = "A+", TRAFFIC_GREEN
        headline  = "🟢 印鈔機！A+ 型企業，策略2 最愛標的"
        comment   = (f"企業 DNA = A+ 穩健印鈔機，OCF 為{'正' if ocf > 0 else '負'}。"
                     f"{'共 ' + str(len(pass_items)) + ' 項達標：' + '、'.join(pass_items[:5]) + '。' if pass_items else ''}"
                     f"現金流真實可信，財務體質堅實，符合 策略2「找到好生意」的核心標準。")
    elif score_pct >= 70:
        grade, gc = "A", TRAFFIC_GREEN
        headline  = "🟢 優質企業！財務體質健康"
        comment   = (f"多項指標通過 策略2 嚴格標準：**{'、'.join(pass_items[:5])}**{'等' if len(pass_items) > 5 else ''}。"
                     f"{'盈餘含金量高，現金流真實可信。' if eq_ok else ''}"
                     f"整體財務結構穩健，具備中長期投資價值。")
    else:
        grade, gc = "B", "#58a6ff"
        headline  = "🔵 財務穩定，中規中矩"
        comment   = (f"財務表現尚可，無明顯紅旗。"
                     f"{'已達標：' + '、'.join(pass_items[:4]) + '。' if pass_items else ''}"
                     f"建議持續追蹤下一季財報，確認趨勢是否持續改善。")

    if _skipped:
        # 等級只反映**算得出來的那幾項** —— 不講清楚，B+ 與「11 項只評到 3 項
        # 的 B+」在畫面上長得一模一樣（§-1.5 A-7：無法驗到的限制要標明）。
        comment = (f"{comment}　⚠️ 本輪有 {len(_skipped)} 項未評估"
                   f"（{'、'.join(_skipped)}）—— 缺資料不計分，"
                   f"等級只反映算得出來的那幾項。")

    return {
        "grade": grade, "grade_color": gc,
        "headline": headline, "comment": comment,
        "score_pct": score_pct,
        "pass_count": len(pass_items), "fail_count": len(fail_items),
        "pass_items": pass_items, "fail_items": fail_items, "dna": dna,
    }


# ── Survival Module 入口 ────────────────────────────────────

# ── Financial Structure Module Prompt（財務結構：那根棒子 + 以長支長）──
_FINANCIAL_STRUCTURE_PROMPT = """\
# Role: 財務結構分析官

# Core Rules
1. 此關卡負責檢驗「財務結構」，也就是資產負債表上的「那根棒子」與「資金配置」。
2. 未通過代表公司有極高的突發性倒閉風險。

# Edge Case Handling
- 【金融業例外】：若股票代號屬金融保險業（銀行、金控、壽險），
  「負債佔資產比率」直接標記為 "N/A (特許行業)"，Status = "N/A"。
- 【除以零防呆】：若「固定資產(千)」為 0，**視為該欄位缺漏**，
  「以長支長比率」標記 Status = "N/A"，Value = "N/A (固定資產缺漏)"。
  （2026-09-09 P0-B：原本判 "Pass (輕資產)"。取數層查無回 0，
  「0」與「真的輕資產」在資料上無法分辨，判 Pass 就是拿缺值換及格證。）

# Evaluation Logic

## 1. 負債佔資產比率 (Debt to Asset Ratio)
- 計算：(總負債(千) / 總資產(千)) * 100%
- 判定：< 60% → Pass；60%~70% → Warning；> 70% → Fail。

## 2. 以長支長比率 (Long-Term Funds to Fixed Assets)
- 計算：(股東權益(千) + 非流動負債(千)) / 固定資產(千) * 100%
- 判定：> 100% → Pass；< 100% → Fail（短債長投，資金鏈隨時斷裂）。

# Input Data
<Financial_Data>
{financial_data_json}
</Financial_Data>

# Output Protocol
直接輸出以下 JSON（禁止 Markdown 包裝）：
{{
  "Financial_Structure_Module": {{
    "Debt_Ratio": {{"Value": "XX.X%", "Status": "Pass | Warning | Fail | N/A"}},
    "Long_Term_Funding_Ratio": {{"Value": "XX.X% | N/A (輕資產)", "Status": "Pass | Fail"}},
    "Final_Insight": "綜合短評（50字以內，點出財務結構最關鍵的風險或優勢）"
  }}
}}"""




# ── Solvency Module Prompt（償債能力：流動/速動比率 + 收現豁免）──
_SOLVENCY_PROMPT = """\
# Role: 短期償債分析官

# Core Rules
1. 採用極度嚴格標準 (300/150)。
2. 備有「收現行業」豁免條款，確保不誤殺優質流通業。

# Edge Case Handling
- 【分母缺漏】：若「流動負債(千)」= 0（或「流動資產(千)」= 0），
  **視為資產負債表缺漏**，所有指標標記 Status = "N/A"，
  Cross_Validation_Applied = "No"，Final_Solvency_Verdict = "N/A"。
  （2026-09-09 P0-B：原本判「Pass (無短期債務)」。上市櫃公司流動負債不可能是 0。）

# Evaluation Logic

## 1. 流動比率 (Current Ratio)
- 計算：流動資產(千) / 流動負債(千) * 100%
- 嚴格標準：> 300% → Pass；≤ 300% → Fail_Initial。

## 2. 速動比率 (Quick Ratio)
- 計算：(流動資產(千) - 存貨(千)) / 流動負債(千) * 100%
  （預付費用不在資料中，以存貨作為主要扣減項）
- 嚴格標準：> 150% → Pass；≤ 150% → Fail_Initial。

## 3. 交叉驗證保命符 (Cross-Validation)
若任一項為 Fail_Initial，Cross_Validation_Applied = "Yes"，
依序檢查三個條件（滿足任一即豁免）：
- [條件 A] 現金佔總資產(%) > 25%
- [條件 B] 應收帳款天數 < 15 天（天天收現金行業）
- [條件 C] DSO + DIO - DPO（做生意完整週期）< 50 天
  DIO = 存貨(千) / 營業成本(千) * 360（若營業成本=0則用營業收入(千)代替）
  DPO = 應付帳款天數
  若上述任一條件成立 → Final_Solvency_Verdict = "Exception_Pass (條件X：說明)"
  若均不符合 → Final_Solvency_Verdict = "Fail"

# Input Data
<Financial_Data>
{financial_data_json}
</Financial_Data>

# Output Protocol
直接輸出以下 JSON（禁止 Markdown 包裝）：
{{
  "Solvency_Module": {{
    "Current_Ratio": {{"Value": "XX.X%", "Status": "Pass | Fail_Initial"}},
    "Quick_Ratio": {{"Value": "XX.X%", "Status": "Pass | Fail_Initial"}},
    "Cross_Validation_Applied": "Yes | No",
    "Final_Solvency_Verdict": "Pass | Exception_Pass (說明) | Fail",
    "Final_Insight": "綜合短評（50字以內，說明短期償債能力關鍵結論）"
  }}
}}"""




# ── Advanced Diagnostic Module Prompt（綜合診斷：跨表勾稽 + 地雷偵測）──
_ADVANCED_DIAGNOSTIC_PROMPT = """\
# Role: 綜合診斷與避雷官

# Core Rules
1. 看透高獲利背後的真相，執行跨表勾稽與地雷偵測。
2. 盈餘品質防呆：若「稅後淨利(千)」<= 0，直接輸出 "N/A (淨利為負)"。

# Evaluation Logic

## 1. 盈餘品質 (Earnings Quality)
- 計算：OCF(千) / 稅後淨利(千) * 100%
- 判定：> 100% → Pass（真金白銀）；< 100% → Fail（紙上富貴）。

## 2. 杜邦分析 (DuPont Health)
- ROE = 稅後淨利(千) / 股東權益(千) * 100%
- 若 ROE > 15% 且 負債比率(%) > 65% → "槓桿膨脹警報"
- 若 ROE > 15% 且 負債比率(%) ≤ 65% → "健康成長"
- 若 ROE ≤ 15% → "ROE 偏低，成長動能不足"

## 3. 雙高危機 (Double High Warning)
- 應收帳款增長率 = 應收帳款季增率(%)（已在資料中）
- 存貨增長率 = (存貨(千) - 存貨前期(千)) / |存貨前期(千)| * 100%
- 條件：應收帳款增長率 > 營收季增率(%) 且 存貨增長率 > 營收季增率(%)
  同時滿足 → "Triggered (危險)"；否則 → "Clear (安全)"
  若增長率數值為 null/0 → 標記 "N/A (資料不足)"

## 4. 企業 DNA (Cash Flow Matrix)
- 依 [OCF符號, ICF符號, 籌資CF符號] 判斷：
  (+, -, -) → "A+ 穩健印鈔機"
  (+, -, +) → "成長擴張型"
  (+, +, -) → "變賣祖產型（⚠️ 請確認原因）"
  (-, -, +) → "燒錢新創型（需觀察現金消耗速度）"
  (-, +, -) → "瀕死型（🔴 極度危險）"
  其他 → "特殊組合（需個案分析）"

# Input Data
<Financial_Data>
{financial_data_json}
</Financial_Data>

# Output Protocol
直接輸出以下 JSON（禁止 Markdown 包裝）：
{{
  "Advanced_Diagnostic_Module": {{
    "Earnings_Quality": {{"Value": "XX.X% | N/A", "Status": "Pass | Fail | N/A"}},
    "DuPont_Health": "健康成長 | 槓桿膨脹警報 | ROE 偏低，成長動能不足",
    "Double_High_Warning": "Triggered (危險) | Clear (安全) | N/A (資料不足)",
    "Business_DNA": "標籤名稱 (+/-/- 組合)",
    "Final_Verdict": "綜合短評（60字以內，點出最關鍵的地雷或亮點）"
  }}
}}"""


def analyze_financial_health(api_key: str, stock_id: str, fin_data: dict,
                             news_context: str = "") -> dict:
    """
    從 fin_data 直接計算所有財報體檢指標（純數學）。
    若提供 api_key 與 news_context，則額外呼叫 Gemini 生成結合新聞的 ai_insight。
    """
    if not fin_data or fin_data.get("error"):
        fs = _FAIL_SAFE.copy()
        fs["ai_insight"] = fin_data.get("error", "財報資料為空") if fin_data else "財報資料為空"
        return fs

    # 頂層指標（現金/OCF/負債/雷達/DNA/OPM）
    result = _derive_basic_from_fin_data(fin_data)
    result["ai_insight"] = "📊 財報數據直接計算（點擊上方按鈕可生成 AI 首席顧問完整分析）"

    # 6 大子模組（全部純計算，無 AI）
    result["survival_module"]           = _no_ai_survival(fin_data).get("Survival_Module", {})
    result["operating_module"]          = _no_ai_operating(fin_data).get("Operating_Module", {})
    result["profitability_module"]      = _no_ai_profitability(fin_data).get("Profitability_Module", {})
    result["financial_structure_module"] = _no_ai_financial_structure(fin_data).get("Financial_Structure_Module", {})
    result["solvency_module"]           = _no_ai_solvency(fin_data).get("Solvency_Module", {})
    result["advanced_diagnostic_module"] = _no_ai_advanced_diagnostic(fin_data).get("Advanced_Diagnostic_Module", {})

    # 若有 api_key 與 news_context，呼叫 Gemini 生成含新聞情緒的 ai_insight
    if api_key and news_context:
        try:
            # v19.178 §3.3:第一關三條門檻原為 prompt 內寫死(25/10、40/60),
            # 與 `_no_ai_survival` / `_no_ai_financial_structure` 用的
            # shared/financial_health_thresholds SSOT 是兩份複本 —— 改門檻時
            # code 端會動、送給 Gemini 的判讀規則不會動 → 同一檔股票在
            # 「純計算燈號」與「AI insight 敘事」會給出相反結論。改為插值。
            _news_prompt = _PROMPT_TEMPLATE.format(
                financial_data_json=json.dumps(fin_data, ensure_ascii=False, indent=2),
                news_context=news_context,
                cash_safe_pct=f"{FH_CASH_RATIO_SAFE_PCT:g}",
                cash_watch_pct=f"{FH_CASH_RATIO_WATCH_PCT:g}",
                debt_excellent_pct=f"{FH_DEBT_RATIO_EXCELLENT_PCT:g}",
                debt_pass_pct=f"{FH_DEBT_RATIO_PASS_PCT:g}",
            )
            # v19.174 去識別化：區域變數 _raw_mj/_parsed_mj/_e_mj → _raw_fh/_parsed_fh/_e_fh
            _raw_fh = _gemini_call(_news_prompt, api_key)
            _parsed_fh = _extract_json(_raw_fh)
            if _parsed_fh.get("ai_insight"):
                result["ai_insight"] = _parsed_fh["ai_insight"]
            if _parsed_fh.get("red_flags"):
                result["red_flags"] = _parsed_fh["red_flags"]
            print(f"[FinHealth] ✅ {stock_id} 財報+新聞 AI insight 生成完成")
        except Exception as _e_fh:
            print(f"[FinHealth] {stock_id} 財報體檢 AI insight 生成失敗: {_e_fh}")

    print(f"[FinHealth] ✅ {stock_id} 純計算完成 DNA={result.get('business_model_dna','?')}")
    return result
