"""🗂 資料頁「🔌 連線診斷」契約（L0；只放枚舉與固定文字，零 I/O、零 streamlit、無時間戳／日期）。

出處：GitHub #1110 comment 6933645454（GPT 定稿 D-T2）；docs/vnext/NEWUI2_TOP_FIVE_APPROVED_VISUAL_AND_SAFETY_GATE_2026-11-07.md §7。
⛔ 例外原文／host／IP／URL／header／body／traceback 不得進入本契約：原因只能是下列固定類別（`DiagReason`）。
⛔ `DiagReport` 不含任何時間戳、資料日、檢查日期（「資料發布狀態」第一批固定「尚未提供」）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DiagStatus(Enum):
    NOT_CONFIGURED = "未設定"
    NOT_CHECKED = "尚未檢查"
    SUCCESS = "連線成功"
    FAILED = "連線失敗"
    AUTH_UNVERIFIED = "認證未驗證"


class DiagReason(Enum):
    """固定安全原因類別（白名單）。前六項字樣與 `src/ui/pages/api_diagnostic.py` 的 `ERR_*` 相同（parity 測試鎖住）。"""
    NONE = ""
    TIMEOUT = "逾時"
    CONNECTION = "連線失敗"
    PROXY = "代理錯誤"
    AUTH = "認證失敗(401/403)"
    SERVER = "伺服器錯誤(5xx)"
    OTHER = "其他"
    TLS = "TLS 憑證驗證未通過"
    PROXY_AUTH = "代理認證失敗(407)"
    PLAIN_HTTP = "僅提供明文連線，未送出金鑰"
    KEY_MISSING = "未提供金鑰，無法驗證認證"
    AUTH_NOT_ENFORCED = "無法證明伺服器強制認證"


class DiagNotice(Enum):
    NONE = ""
    WAIT = "請稍後再試"      # 檢查進行中，或距上次檢查未滿冷卻時間


@dataclass(frozen=True)
class ProbeResult:
    status: DiagStatus
    reason: DiagReason = DiagReason.NONE


@dataclass(frozen=True)
class DiagReport:
    nas_relay: ProbeResult
    nas_proxy: ProbeResult
    finmind: ProbeResult
    yahoo: ProbeResult
    twse: ProbeResult
    notice: DiagNotice = DiagNotice.NONE


_NC = ProbeResult(DiagStatus.NOT_CHECKED)
INITIAL_REPORT = DiagReport(_NC, _NC, _NC, _NC, _NC)

# ── 固定文字（GPT 定稿；一字不改）──────────────────────────────────────
TEXT_DIAG_TITLE = "🔌 連線診斷"
TEXT_DIAG_NOTE = "僅供檢查連線；連線成功不代表行情已更新。"
TEXT_DIAG_LABEL_NAS_RELAY = "NAS 中繼站"
TEXT_DIAG_LABEL_NAS_PROXY = "NAS 代理"
TEXT_DIAG_LABEL_EXTERNAL = "外部資料連線"
TEXT_DIAG_LABEL_FINMIND = "FinMind"
TEXT_DIAG_LABEL_YAHOO = "Yahoo"
TEXT_DIAG_LABEL_TWSE = "臺灣證交所"
TEXT_DIAG_LABEL_PUBLICATION = "資料發布狀態"
TEXT_DIAG_PUBLICATION_VALUE = "尚未提供"
TEXT_DIAG_BUTTON = "檢查連線"
TEXT_DIAG_ARIA = "連線診斷"
#: DEC-146 局部文案更正（客戶授權的最小更正）：本區只檢查連線。
TEXT_DIAG_HEALTH_NOT_OPEN = "完整資料健康度尚未開放；本區僅檢查連線，不代表資料已更新"
