"""shared/risk_cap_policy.py — 系統風險上限（`macro_state.json` 的 `exposure_limit_pct`）規則版本 SSOT（L0）。

═══ 為什麼有這個檔 ═══════════════════════════════════════════════════
系統風險上限由 L3 `src/services/macro_state_locker.calculate_system_state` 算出、經
`lock_system_state_only` 寫進 `macro_state.json`，再由 `get_macro_state()` 讀成全站建議持股的
天花板之一。修前**沒有任何規則版本**：同一個檔名，可能是舊規則（M1B-M2 資金項仍計分）寫的，
也可能是新規則寫的，讀端分不出來。

客戶 2026-10-16 Q2：System Risk Cap 正式計分停用 M1B-M2 腿（與
`shared/signal_thresholds.M1B_M2_LEG_ENABLED = False` 同步）；**保留歷史版本與版本化、不改寫歷史決策**。
⇒ 本檔給一個 L0 規則版本常數，新 UI 寫檔路徑（`src/services/risk_cap_apply.py`）把它蓋進檔案。
舊 UI（`src/ui/tabs/macro/section_news_ai.py`，凍結）寫的檔**不帶**本欄位。

⚠️ 本常數**不是** `src/compute/macro/macro_forward_test.compute_ruleset_hash`（那是總經燈號的規則雜湊，
與系統風險上限無關，⛔ 不得把本檔常數加進去）。

客戶 2026-10-16 Q1：Required Core（下方 `REQUIRED_CORE_INPUTS`）任一無法評估 ⇒ **不產生新的系統風險上限**；
可沿用 7 天內（`shared.staleness.MACRO_VERDICT_MAX_AGE_DAYS`）最近一次**有效**快照，超過 7 天 →「無法判定」；
⛔ 不得因缺資料放寬風控。M1B／M2、PCR、BIAS240 為 Optional，缺時須揭露未評估項。
⇒ 寫端（`risk_cap_apply`）核心齊全才寫、並蓋 `required_core_ok: True`；新 UI 讀端只認
`is_valid_risk_cap_snapshot(...)` 為 True 的檔（舊 UI 寫的檔、v2 以前的檔一律不認 ⇒ 無上限 ⇒「無法判定」）。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫與 L0（`shared.*`），被 L3 import。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

RISK_CAP_RULESET_VERSION: str = "risk_cap.v2"
"""系統風險上限的規則版本（寫進 `macro_state.json` 的 `risk_cap_ruleset_version`）。

版本史（⛔ 只增不改；舊版本的檔案不改寫）：

==============  ==========  ==================================================================
版本            期間        規則
==============  ==========  ==================================================================
（無欄位）      ～2026-10-16  批 Z65 以前與舊 UI：8 項數值輸入全計分（含 M1B-M2 資金項
                            spread＞3 → +15、＞0 → +5、＜−3 → −10，與「資金緊縮」標記）。
                            檔案不帶版本欄位 ⇒ 讀端一律視為「非現行版本」。
`risk_cap.v2`   2026-10-16～  客戶 Q2：M1B-M2 腿停用（`M1B_M2_LEG_ENABLED = False`）——
                            不計分、不貼「資金緊縮」、不算「未評估」，回報為 `disabled_inputs`；
                            ＋ 客戶 Q1：Required Core 全部可評估才寫檔，並蓋 `required_core_ok: True`
                            （同一批 Z66 的第二個 commit；兩者都是 v2 的一部分，讀端兩欄都要）。
==============  ==========  ==================================================================

⚠️ 改 `shared/signal_thresholds.M1B_M2_LEG_ENABLED`（例如 DL-f1-s8 支持重新啟用）＝改規則 ⇒
**必須同時升本版本**（客戶：重新啟用是另一次裁示）。`tests/test_batch_z66.py` 把兩者綁在一起守住。
"""

#: 寫進 `macro_state.json` 的版本欄位名（寫端與讀端共用，⛔ 不在呼叫端另寫字面）。
RISK_CAP_RULESET_VERSION_KEY: str = "risk_cap_ruleset_version"


# ── Required Core（客戶 2026-10-16 Q1；現有證據下的正式版本）────────────────────
REQUIRED_CORE_INPUTS: tuple[str, ...] = (
    "VIX_Index",             # VIX
    "ISM_PMI_or_OECD_CLI",   # 台灣 PMI 當月（鍵名沿用引擎歷史命名；值是 CIER 台灣 PMI）
    "PMI_Prev_Month",        # 台灣 PMI 前月（PMI 歷史 parquet 的真正前一資料月）
    "Futures_Net_Short",     # 外資期貨淨空單（TX 當量口）
    "Index_Below_MA5",       # 加權指數是否跌破 MA5（與外資期貨同屬硬否決紅線三）
)
"""系統風險上限的**必要核心輸入**（引擎鍵名；順序即報告順序）。任一無法評估 ⇒ 本輪不產生新上限。

「無法評估」的判定與 L3 `macro_engine_inputs` 的硬紅線同一條（新鮮度非 FRESH 或計分值為 None）。
「外資期貨淨空 ＋ 指數跌破 MA5」就是硬否決紅線三的那一對（`RED_LINE_INPUTS["futures_ma5"]`）——
⚠️ 沒有「外資期貨部位的 MA5」這種東西，MA5 指的是加權指數。
⛔ 鍵名在 L0 以字面寫（L0 不得 import L2 `dated_inputs`）；與 L2／L3 的一致性由
`tests/test_batch_z66b.py` 守住。"""

OPTIONAL_INPUTS: tuple[str, ...] = ("M1B_YoY_pct", "M2_YoY_pct", "BIAS240_pct", "PCR")
"""Optional：缺時照算（缺項不計分），但未評估項必須揭露（檔案的 `not_evaluated`、步驟報告）。
M1B／M2 另受 M1B-M2 腿停用（批 Z66）—— 停用時回報為「已停用、不計分」，不算未評估。"""

REQUIRED_CORE_LABELS: Mapping[str, str] = MappingProxyType({
    "VIX_Index": "VIX",
    "ISM_PMI_or_OECD_CLI": "台灣 PMI 當月",
    "PMI_Prev_Month": "台灣 PMI 前月",
    "Futures_Net_Short": "外資期貨淨空單",
    "Index_Below_MA5": "加權指數跌破 MA5",
})
"""Required Core 的客戶語言名稱（步驟報告用）。"""

#: 寫進 `macro_state.json` 的「Required Core 全部可評估」戳記欄位名。
REQUIRED_CORE_OK_KEY: str = "required_core_ok"


def is_valid_risk_cap_snapshot(state: Any) -> bool:
    """這份 `macro_state.json` 內容能不能當**系統風險上限**用（新 UI／服務讀端的唯一判斷）。

    兩條同時成立才算：`required_core_ok is True`（必須是 bool True，⛔ 不收 1／"true"）
    且 `risk_cap_ruleset_version == RISK_CAP_RULESET_VERSION`（現行規則版本）。
    舊 UI 寫的檔、批 Z66 以前的檔都沒有這兩個欄位 ⇒ False（fail-safe 方向：寧可「無法判定」）。
    有效期限（7 天）**不在這裡判**，由 `macro_state_locker.macro_state_is_expired` 負責（同一條既有規則）。
    """
    if not isinstance(state, Mapping):
        return False
    return (state.get(REQUIRED_CORE_OK_KEY) is True
            and state.get(RISK_CAP_RULESET_VERSION_KEY) == RISK_CAP_RULESET_VERSION)
