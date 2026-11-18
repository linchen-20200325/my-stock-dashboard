"""OneBrain OB-1（完全離線）— Provider 中立契約（L0）。

═══ 範圍（DEC-195；Issue #1199 GPT §C 核准，僅限離線鷹架）═══════════════════
只定義「一個 Provider 該長什麼樣」：`SummaryProvider` Protocol、請求／錯誤分類。
⛔ 本檔**不含**任何 SDK／網路／金鑰／時鐘／sleep／快取／重試；不選 Provider、不選 model、不談費用。
⛔ **零 production import**：除 `src/services/onebrain_shadow.py` 與測試外，任何模組都不得 import 本檔
   （由 `tests/test_onebrain_offline_guard.py` 的 AST 守衛強制）。

═══ 契約 ═══════════════════════════════════════════════════════════════
- Provider 只能回傳結構化 `SummaryDraft`（`shared.decision_digest_grounding`）；自由文字不是合法回傳，
  會在 grounding（`check_summary`）被擋下。
- 失敗一律 `raise ProviderError(kind, detail)`；`kind` 屬 `ProviderErrorKind` 四類。
- Provider 的輸出**永遠不是**決策來源：action／Risk Cap 由既有規則決定，本契約沒有任何欄位能承載它們。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from shared.decision_digest import DecisionDigest
from shared.decision_digest_grounding import SummaryDraft

#: 目前唯一的任務種類（影子摘要草稿）。新增種類屬 Decision Gate，不在 OB-1 範圍。
TASK_SUMMARY_DRAFT = "summary_draft"


class ProviderErrorKind(str, Enum):
    """Provider 失敗的封閉分類（值為穩定字串，可進 log／trace）。"""
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"


class ProviderError(Exception):
    """Provider 的受控失敗。`kind` 為封閉分類，`detail` 為給人讀的簡述（不得含金鑰／原始回應全文）。"""

    def __init__(self, kind: ProviderErrorKind, detail: str = "") -> None:
        if type(kind) is not ProviderErrorKind:
            raise TypeError(f"ProviderError.kind 必須是 ProviderErrorKind：{kind!r}")
        super().__init__(f"{kind.value}: {detail}")
        self.kind = kind
        self.detail = detail


@dataclass(frozen=True)
class ProviderRequest:
    """送給 Provider 的唯讀請求：只含已通過驗證的 Decision Digest v1（不新增任何 Digest 欄位）。"""
    digest: DecisionDigest
    task: str = TASK_SUMMARY_DRAFT


@runtime_checkable
class SummaryProvider(Protocol):
    """摘要草稿提供者。實作可能是離線 Fake（測試）；真實 Provider 屬 Decision Gate，本批不存在。"""

    def propose_summary(self, request: ProviderRequest) -> SummaryDraft:
        """回傳結構化 `SummaryDraft`；失敗 → `raise ProviderError`。"""
        ...


__all__ = ["TASK_SUMMARY_DRAFT", "ProviderErrorKind", "ProviderError", "ProviderRequest", "SummaryProvider"]
