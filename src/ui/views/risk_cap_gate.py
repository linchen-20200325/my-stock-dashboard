"""src/ui/views/risk_cap_gate.py — 新頁「建議持股」的系統風險上限閘門（L5，批 Z65 QA）。

客戶規則（Q-z34～36 已核准；批 Z65 QA 實測缺口）：
「新頁取不到有效的系統風險上限 → 建議持股『無法判定』」。
修前：沒有 `macro_state.json`、檔案過期、或 fail-safe 且沒有舊檔時，卡①（今天頁）與 ⑤（持股頁）
仍照姿態帶印出持股區間，天花板清單是空的 —— 等於在缺一條硬否決天花板的情況下**放寬風控**。

判斷依據（⛔ 不另寫一套過期／有效判斷）：
`get_allocation()` 內部的 `build_allocation_decision` 只在 `get_macro_state()['exposure_limit_pct']`
**有值且可轉成整數**時，才把名為「系統風險上限」的 `Cap` 放進 `caps`；而 `get_macro_state()` 已把
過期（`MACRO_VERDICT_MAX_AGE_DAYS`）、fail-safe「系統異常」、讀不出來的檔一律當成沒有上限。
⇒ 本檔只看 allocation 的 `caps` 裡**有沒有那一條**，與 `get_allocation` 內部的有效判斷同一份。

⚠️ 只管新頁（`src/ui/views/**`）。共用層 `get_allocation` / `build_allocation_decision` 不改
（舊 UI 共用）。本檔純函式、零 streamlit、零取數。
"""
from __future__ import annotations

from typing import Any

#: `shared/allocation_decision.build_allocation_decision` 為 macro_state 曝險上限建的 `Cap.name`。
#: 共用層以字面寫在函式內（本批禁改共用層），故這裡對齊同一字面；
#: 一致性由 `tests/test_batch_z65.py` 以真的 `build_allocation_decision` 輸出守住。
SYSTEM_RISK_CAP_NAME: str = "系統風險上限"

#: 缺上限時卡片的 now / why（where 由各頁用自己的「按本頁按鈕可重算」出口）。
RISK_CAP_UNAVAILABLE_NOW: str = "**建議持股：無法判定**"
#: 批 Z65 複驗 R2-1：⛔ 不宣稱是哪一種原因（本頁分不出是沒算、算不出、過期還是讀壞）。
RISK_CAP_UNAVAILABLE_WHY: str = (
    "目前沒有可用的系統風險上限（尚未計算、本輪算不出來、檔案已過期或讀不出來都會如此）；"
    "系統不會在缺上限的情況下給持股數字")


def has_system_risk_cap(caps: Any) -> bool:
    """allocation 的 `caps` 裡有沒有一條有效的「系統風險上限」。"""
    return any(getattr(c, "name", None) == SYSTEM_RISK_CAP_NAME for c in (caps or ()))
