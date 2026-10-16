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

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫與 L0（`shared.*`），被 L3 import。
"""
from __future__ import annotations

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
                            不計分、不貼「資金緊縮」、不算「未評估」，回報為 `disabled_inputs`。
==============  ==========  ==================================================================

⚠️ 改 `shared/signal_thresholds.M1B_M2_LEG_ENABLED`（例如 DL-f1-s8 支持重新啟用）＝改規則 ⇒
**必須同時升本版本**（客戶：重新啟用是另一次裁示）。`tests/test_batch_z66.py` 把兩者綁在一起守住。
"""

#: 寫進 `macro_state.json` 的版本欄位名（寫端與讀端共用，⛔ 不在呼叫端另寫字面）。
RISK_CAP_RULESET_VERSION_KEY: str = "risk_cap_ruleset_version"
