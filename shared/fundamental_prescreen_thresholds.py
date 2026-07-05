"""全台股基本面初篩門檻 SSOT(Phase 2 選股網 — 全市場基本面漏斗)。

選股網入池前先跑「全台股基本面初篩」:讀 MOPS 全市場季快照,對每檔算 4 項
基本面,四項『全過』才進入下游深掃/評分池。本模組收這 4 項用到的**數字門檻**
+ 檢查項的語意標籤,禁止散落 inline magic number(§3.3)。

4 項檢查(evidence 對照 CLAUDE.md §3.2 合理性表):
  ① 負債比      total_liab / total_assets < DEBT_RATIO_MAX
  ② 三率三升    毛利率/營益率/淨利率 本季 > 去年同季(YoY,嚴格 >;無門檻數字)
  ③ 淨流動值    current_assets - total_liab > 0(保守版葛拉漢;無門檻數字)
  ④ 獲利為正    eps > EPS_MIN

設計:純常數模組,零 import 依賴。caller 用
`from shared.fundamental_prescreen_thresholds import DEBT_RATIO_MAX, EPS_MIN`。
"""
from __future__ import annotations

# ① 負債比上限:total_liab / total_assets 須 < 此值(50%)。
# 來源:CLAUDE.md §3.2 領域慣例「負債比 < 50% 為穩健」;金融業天生 >90% 故天然被排除。
DEBT_RATIO_MAX: float = 0.50

# ④ EPS 門檻:本季 eps 須 > 此值(獲利為正的基本地板)。
EPS_MIN: float = 0.0

# 存活門檻:4 項須『全過』(strict AND)。以常數表達,禁止 UI/L2 端寫死「== 4」。
PRESCREEN_REQUIRED_PASSES: int = 4

# prescreen 版本(快取 key / provenance 用;改公式或門檻時 bump)。
PRESCREEN_VERSION: str = "fundamental_prescreen_v1"

# 各檢查布林欄 → 中文語意標籤(UI 顯示 + golden test 釘一致)。
CHECK_LABELS: dict[str, str] = {
    "pass_debt": "負債比<50%",
    "pass_three_rise": "三率三升(YoY)",
    "pass_net_current": "淨流動值>0",
    "pass_eps_positive": "EPS>0",
}
