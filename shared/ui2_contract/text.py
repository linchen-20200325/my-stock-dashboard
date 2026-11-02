"""L1 外露字樣常數（資料語意五態／判定結果「無法判定」／capability「尚未提供」＋Preview 標示）。

出處：Freeze §5.1（四態字樣）、§9（資料日缺）、§0.1.4（Risk Cap `⬜ 無法判定`）、
Architecture Gate §4.6.5／§7（Preview 期動作欄）、DEC-124（三軸語意邊界）。
⛔ 字樣全站唯一；Missing 與 Not evaluated 同用 ⬜，**必須以文字區分**（Freeze §5.1）；
⛔ Not Evaluated 與 Unable to Determine 同用 ⬜，**同樣必須以文字區分、且分屬不同表**（DEC-124）。
"""
from __future__ import annotations

# ── Missing（灰）：資料未取得／資料未備 ──────────────────────────────
TEXT_MISSING_NOT_FETCHED = "⬜ 資料未取得"   # 應有輸入但這次沒拿到
TEXT_MISSING_NOT_READY = "⬜ 資料未備"       # 來源尚未發布、歷史不足、不適用
TEXT_ASOF_MISSING = "⬜ 資料日未提供"        # 欄位級：缺 as_of（Freeze §9-3）

# ── Stale（琥珀）：有資料但超過 freshness tolerance ─────────────────
TEXT_STALE_DAYS_FMT = "⚠ 過期 {n} 天"
TEXT_STALE_UNKNOWN = "⚠ 可能已過期"

# ── Unavailable（紅，系統真錯誤）──────────────────────────────────────
TEXT_UNAVAILABLE = "🔴 來源目前不可用"       # 後面可接一句原因

# ── Not evaluated（灰）：規則／計算尚未執行或不在本次評估範圍（含子原因）────
TEXT_NOT_EVALUATED = "⬜ 尚未評估"
TEXT_NOT_DEFINED = "⬜ 尚未定義"
#: Freeze §5.2 metadata `not_approved`（規則／數值未核准 → 未執行）＝Not evaluated。
#: ⚠️ 既有字樣尾綴含「無法判定」，屬混合字樣，逐字保留不改；UI2 ⛔ 用它表示 Risk Cap
#: （Risk Cap 一律 `TEXT_RISK_CAP_UNDETERMINABLE`）；待覆核：BACKLOG `NUI2-NOT-APPROVED-LITERAL-REVIEW`。
TEXT_NOT_APPROVED = "⬜ 尚未核准／無法判定"
TEXT_NOT_LOADED = "⬜ 尚未載入"

# ── Unable to Determine（灰；判定結果，非資料語意；DEC-124）────────────────
#: Risk Cap 在 Q1 數值 Gate 前恆「無法判定」（Freeze §0.1.4 第 3 點；逐字）。⛔ 此處不判定任何數值。
#: 語意歸類＝Unable to Determine（必要輸入「目前曝險」無正式來源）；⛔ 等同 Not evaluated（DEC-124）。
#: 亦為一般「無法判定」的預設字樣。無法判定 ≠ safe／neutral／no action／無需調整／可加碼。
TEXT_RISK_CAP_UNDETERMINABLE = "⬜ 無法判定"
#: 客戶逐字（DEC-074／075；字樣一字不改）。原始語境＝「受 breadth 影響且無法依既有正式規則可靠計算」
#: 「因缺少正式 breadth」→ 已進入計算、必要輸入不足 ⇒ 語意歸類 Unable to Determine（DEC-124；
#: 單組判讀，待覆核：BACKLOG `NUI2-DATA-SHORT-CLASSIFICATION-REVIEW`）。
TEXT_NOT_EVALUATED_DATA_SHORT = "⬜ 未評估／資料不足"

# ── Capability／Implementation Availability（與資料語意正交；Preview-only；DEC-124）──
#: ≠ Unavailable（來源壞了）；≠ 資料品質態；⛔ 稱為「第 6 個資料語意態」。
TEXT_NOT_PROVIDED = "⬜ 尚未提供"
TEXT_NOT_PROVIDED_AGGREGATOR = "⬜ 尚未提供（待 System Action Aggregator）"

#: Preview 頁首標示（客戶指示：頁面頂部清楚標示）。
PREVIEW_BANNER_TEXT = "New UI2 Preview（fake data）"
PREVIEW_BANNER_NOTE = "以下全部是 FAKE／scenario 示意資料，不是真實行情、持股或建議。"

#: 資料來源欄位的 FAKE 前綴（避免 fake 值被誤認為真來源）。
FAKE_SOURCE_PREFIX = "FAKE"

#: **正式資料語意**五態允許的 L1 字樣前綴。key 為 `FieldState.value`（恰五個；DEC-124）。
#: 三張表（資料語意／判定結果／capability）互斥：同一字樣不得出現在兩處（見 tests/test_ui2_guards.py）。
ALLOWED_STATUS_PREFIXES: dict[str, tuple[str, ...]] = {
    "ok": (),   # OK 態不外露狀態字樣
    "missing": (TEXT_MISSING_NOT_FETCHED, TEXT_MISSING_NOT_READY, TEXT_ASOF_MISSING),
    "stale": ("⚠ 過期", TEXT_STALE_UNKNOWN),
    "unavailable": (TEXT_UNAVAILABLE,),
    "not_evaluated": (TEXT_NOT_EVALUATED, TEXT_NOT_DEFINED, TEXT_NOT_APPROVED, TEXT_NOT_LOADED),
}

#: **判定結果**允許字樣（key 為 `JudgementState.value`）。⛔ 併入 `not_evaluated`（DEC-124）。
JUDGEMENT_STATUS_PREFIXES: dict[str, tuple[str, ...]] = {
    "undeterminable": (TEXT_RISK_CAP_UNDETERMINABLE, TEXT_NOT_EVALUATED_DATA_SHORT),
}

#: **Capability marker** 允許字樣（key 為 `CapabilityState.value`；Preview-only）。
CAPABILITY_STATUS_PREFIXES: dict[str, tuple[str, ...]] = {
    "not_provided": (TEXT_NOT_PROVIDED,),
}


def stale_text(days: int | None) -> str:
    """Stale 字樣；天數未知 → `⚠ 可能已過期`（⛔ 不補推估天數）。"""
    if days is None:
        return TEXT_STALE_UNKNOWN
    return TEXT_STALE_DAYS_FMT.format(n=int(days))
