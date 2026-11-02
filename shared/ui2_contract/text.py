"""L1 外露字樣常數（四態＋功能尚未提供＋Preview 標示）。

出處：Freeze §5.1（四態字樣）、§9（資料日缺）、Architecture Gate §4.6.5／§7（Preview 期動作欄）。
⛔ 四態字樣全站唯一；Missing 與 Not evaluated 同用 ⬜，**必須以文字區分**（Freeze §5.1）。
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

# ── Not evaluated（灰）：尚未評估（含子原因）──────────────────────────
TEXT_NOT_EVALUATED = "⬜ 尚未評估"
TEXT_NOT_DEFINED = "⬜ 尚未定義"
TEXT_NOT_APPROVED = "⬜ 尚未核准／無法判定"
TEXT_NOT_LOADED = "⬜ 尚未載入"
TEXT_NOT_EVALUATED_DATA_SHORT = "⬜ 未評估／資料不足"   # 客戶逐字（DEC-074／075）
#: Risk Cap 在 Q1 數值 Gate 前恆「無法判定」（Freeze §0.1.4；逐字）。⛔ 此處不判定任何數值。
#: 語意歸類＝Not evaluated（`⬜ 尚未核准／無法判定` 家族）；not evaluated ≠ safe。
TEXT_RISK_CAP_UNDETERMINABLE = "⬜ 無法判定"

# ── 功能尚未提供（四態之外；Freeze §5.3，≠ Unavailable）──────────────
TEXT_NOT_PROVIDED = "⬜ 尚未提供"
TEXT_NOT_PROVIDED_AGGREGATOR = "⬜ 尚未提供（待 System Action Aggregator）"

#: Preview 頁首標示（客戶指示：頁面頂部清楚標示）。
PREVIEW_BANNER_TEXT = "New UI2 Preview（fake data）"
PREVIEW_BANNER_NOTE = "以下全部是 FAKE／scenario 示意資料，不是真實行情、持股或建議。"

#: 資料來源欄位的 FAKE 前綴（避免 fake 值被誤認為真來源）。
FAKE_SOURCE_PREFIX = "FAKE"

#: 各語意態允許的 L1 字樣前綴。key 為 `FieldState.value`。
#: 四態＋NOT_PROVIDED 互斥：同一字樣不得出現在兩個態（見 tests/test_ui2_guards.py）。
ALLOWED_STATUS_PREFIXES: dict[str, tuple[str, ...]] = {
    "ok": (),   # OK 態不外露狀態字樣
    "missing": (TEXT_MISSING_NOT_FETCHED, TEXT_MISSING_NOT_READY, TEXT_ASOF_MISSING),
    "stale": ("⚠ 過期", TEXT_STALE_UNKNOWN),
    "unavailable": (TEXT_UNAVAILABLE,),
    "not_evaluated": (TEXT_NOT_EVALUATED, TEXT_NOT_DEFINED, TEXT_NOT_APPROVED,
                      TEXT_NOT_LOADED, TEXT_NOT_EVALUATED_DATA_SHORT,
                      TEXT_RISK_CAP_UNDETERMINABLE),
    "not_provided": (TEXT_NOT_PROVIDED,),
}


def stale_text(days: int | None) -> str:
    """Stale 字樣；天數未知 → `⚠ 可能已過期`（⛔ 不補推估天數）。"""
    if days is None:
        return TEXT_STALE_UNKNOWN
    return TEXT_STALE_DAYS_FMT.format(n=int(days))
