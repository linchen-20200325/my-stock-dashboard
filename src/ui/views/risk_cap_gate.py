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


# ══════════════════════════════════════════════════════════════════════════
# PQ-C6-3（客戶 2026-10-16 核准線框）：系統風險上限的資料完整性揭露 —— 卡面一列＋詳細
# ══════════════════════════════════════════════════════════════════════════
# 兩張卡（今天頁卡① `verdict.exposure`、持股頁卡⑤ `hold.position_cap`）共用本段，⛔ 各頁不另寫一份字。
# 揭露資料一律來自 L3 `get_allocation()` 回傳的 `AllocationDecision.risk_cap_disclosure`
# （與上限出自同一次讀檔；本檔⛔ 不讀檔、不取數）。只在「有系統風險上限」時呈現；
# 「建議持股：無法判定」那一態一個字都不加（客戶裁示）。
# ⛔ 顏色不是唯一載體：完整性一律用字講（「未評估：…」）。

#: 卡面那一列的標籤。
RISK_CAP_COMPLETENESS_LABEL: str = "資料完整性"
#: 有 Optional 未評估時，接在項目清單後面的中性句（客戶逐字；⛔ 不寫「上限可能偏寬」）。
RISK_CAP_INCOMPLETE_SENTENCE: str = "部分訊號未納入，本次上限資訊不完整"
#: Optional 全部可評估時（客戶逐字）。
RISK_CAP_COMPLETE_TEXT: str = "必要與選用訊號皆已評估"
#: 「已停用（不計分）」那一項（客戶逐字）。
RISK_CAP_DISABLED_LABEL: str = "已停用（不計分）"
#: 薩姆規則的固定說明（與步驟報告「薩姆規則目前無資料來源、未評估（不代表已通過）」同義、⛔ 不換說法）。
RISK_CAP_SAHM_NO_SOURCE_TEXT: str = "目前無資料來源、未評估（不代表已通過）"
#: 詳細裡各列的標籤。
RISK_CAP_SNAPSHOT_TS_LABEL: str = "快照時間"
RISK_CAP_NOT_EVALUATED_LABEL: str = "未評估項目"
RISK_CAP_SAHM_LABEL: str = "薩姆規則"

#: 新鮮度狀態 → 客戶語言（`shared.freshness_policy.FreshnessStatus` 的值；與 L3 步驟報告同一組字）。
#: `fresh` 會出現在未評估清單裡只有一種情形：時間新鮮但值不能計分（例如非有限數）。
_STATUS_TEXT: dict[str, str] = {
    "missing": "未取得",
    "stale": "已過期",
    "undetermined": "無法判定",
    "fresh": "資料異常、無法計分",
}


def _label(key: str) -> str:
    from shared.risk_cap_policy import OPTIONAL_INPUT_LABELS, REQUIRED_CORE_LABELS
    return OPTIONAL_INPUT_LABELS.get(key) or REQUIRED_CORE_LABELS.get(key) or key


def _dedup(items) -> list[str]:
    return list(dict.fromkeys(items))


def risk_cap_face_text(disclosure: Any) -> str:
    """卡面那一列的值。有未評估項 ⇒「未評估：PCR、BIAS240；部分訊號未納入，本次上限資訊不完整」。

    項目清單**排在最前**（卡面若被截斷，「未評估」與項目名仍在）；⛔ 停用的 M1B−M2 不在這裡
    （`RiskCapDisclosure.not_evaluated` 本來就不含停用項，這裡再擋一次）。
    """
    _dis = set(getattr(disclosure, "disabled", ()) or ())
    _ne = [k for k, _s, _d in (getattr(disclosure, "not_evaluated", ()) or ()) if k not in _dis]
    if not _ne:
        return RISK_CAP_COMPLETE_TEXT
    return f"未評估：{'、'.join(_dedup(_label(k) for k in _ne))}；{RISK_CAP_INCOMPLETE_SENTENCE}"


def risk_cap_detail_rows(disclosure: Any) -> tuple[tuple[str, str], ...]:
    """詳細（持股頁「▸ 詳細」／今天頁的完整文字）各列：快照時間、未評估項目、已停用、薩姆規則。

    ⛔ 未取得的項目**不給日期**（檔內那一格存的是「預期資料日」，不是資料日）；已過期才帶最新資料日。
    """
    _rows: list[tuple[str, str]] = [
        (RISK_CAP_SNAPSHOT_TS_LABEL, str(getattr(disclosure, "snapshot_ts", "") or "未記錄"))]
    _dis = set(getattr(disclosure, "disabled", ()) or ())
    _items = []
    for k, status, as_of in (getattr(disclosure, "not_evaluated", ()) or ()):
        if k in _dis:
            continue
        _txt = f"{_label(k)} {_STATUS_TEXT.get(status, '無法評估')}"
        if status == "stale" and as_of:
            _txt += f"（最新資料日 {as_of}）"
        _items.append(_txt)
    if _items:
        _rows.append((RISK_CAP_NOT_EVALUATED_LABEL, "；".join(_items)))
    if _dis:
        _rows.append((RISK_CAP_DISABLED_LABEL, "、".join(_dedup(_label(k) for k in
                                                          getattr(disclosure, "disabled", ())))))
    if getattr(disclosure, "sahm_status", None) == "no_source":
        _rows.append((RISK_CAP_SAHM_LABEL, RISK_CAP_SAHM_NO_SOURCE_TEXT))
    return tuple(_rows)


def risk_cap_full_text(disclosure: Any) -> str:
    """卡面值＋詳細接成一段（今天頁卡①那一格的完整文字：卡面截斷後掛在 hover 的就是這段）。"""
    return "｜".join([risk_cap_face_text(disclosure)]
                    + [f"{_k}：{_v}" for _k, _v in risk_cap_detail_rows(disclosure)])
