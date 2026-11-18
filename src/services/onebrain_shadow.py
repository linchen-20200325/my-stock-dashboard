"""OneBrain OB-1（完全離線）— 影子執行（L3）：Provider 的輸出只被「檢查」，永遠不被「採用」。

═══ 規則 ═══════════════════════════════════════════════════════════════
1. `ShadowOutcome.effective` **永遠**是 `build_rule_summary(digest)`（既有 deterministic 規則式摘要）。
   Provider 成功、失敗、逾時、回傳垃圾，`effective` 都一樣 ⇒ AI 不可能把 action／Risk Cap 變成 SAFE／neutral。
2. Provider 的草稿只通過 `check_summary`（G1～G6 grounding）；乾淨 ⇒ `shadow_accepted=True`，僅供離線比對，
   不餵給任何下游（UI／LINE／決策／快取）。
3. 任何例外（含非 `ProviderError`、含 grounding 自己 raise）都被分類成 `error_kind` 並 `logging.warning`
   留下型別名（Fail Loud：不 `pass`、不靜默；但 Provider 失敗不得讓主流程失敗，故不再往上拋）。
   `KeyboardInterrupt`／`SystemExit` 不是 `Exception`，照常往上傳。
4. `build_rule_summary` 自己的錯誤（例如非 rule_only 的 Digest 的 `ValueError`）**不**被影子層吞掉 —— 那是規則層 bug，Fail Loud。

⛔ 零 production import（AST 守衛強制）；⛔ 無 I/O、無時鐘、無第二套快取；⛔ 不改 Digest v1 schema。
本模組刻意**沒有** action／Risk Cap 欄位（反射守衛強制）。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from shared.decision_digest import DecisionDigest
from shared.decision_digest_grounding import GroundingReport, SummaryResult, check_summary
from shared.onebrain_provider import ProviderError, ProviderErrorKind, ProviderRequest, SummaryProvider
from src.services.decision_digest_summary import build_rule_summary

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShadowOutcome:
    """影子執行結果。`effective` 永遠是規則式摘要；其餘欄位僅供離線觀測。"""
    effective: SummaryResult
    error_kind: Optional[ProviderErrorKind]   # None ⇒ Provider 草稿通過 grounding 且乾淨
    grounding: Optional[GroundingReport]      # Provider 未產出草稿（失敗）⇒ None
    shadow_accepted: bool                     # 僅供離線比對；不可被 UI／LINE／決策讀取


def run_shadow(digest: DecisionDigest, provider: SummaryProvider) -> ShadowOutcome:
    """對 `digest` 跑一次影子摘要。規則式摘要先算（規則層錯誤直接 raise），再讓 provider 出草稿並檢查。"""
    effective = build_rule_summary(digest)
    try:
        draft = provider.propose_summary(ProviderRequest(digest=digest))
        report = check_summary(digest, draft)
    except ProviderError as e:
        _log.warning("onebrain shadow: provider error %s", e.kind.value)
        return ShadowOutcome(effective, e.kind, None, False)
    except Exception as e:  # noqa: BLE001 — 未分類例外一律視為 invalid_response，留 log、回到規則式摘要
        _log.warning("onebrain shadow: unclassified %s -> invalid_response", type(e).__name__)
        return ShadowOutcome(effective, ProviderErrorKind.INVALID_RESPONSE, None, False)
    kind = None if report.clean else ProviderErrorKind.INVALID_RESPONSE
    return ShadowOutcome(effective, kind, report, report.clean)


__all__ = ["ShadowOutcome", "run_shadow"]
