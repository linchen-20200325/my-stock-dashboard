"""🗂 資料頁 canonical（DEC-146 第一批：可導航的誠實空殼；純函式，無 I/O）。

FAKE（`scenarios`）與 Real-data（`real_canonical`）兩軸**共用同一份固定內容**——內容全是 Capability 軸 `⬜ 尚未提供`
（功能尚未接線），沒有任何「資料事實」可被示意或讀取：⛔ 來源健康度欄位／分母／retrieved_at／proxy／刷新時間／真登入／Sheet／API／公式；
⛔ 補 0。這份內容不屬於任一軸，所以放在中立模組（避免 real 軸 import FAKE 的 `scenarios`）。呼叫端補 `scenario`／`is_fake`。
"""
from __future__ import annotations

from shared.ui2_contract.pages import P4_DATA, PAGE_LABELS
from shared.ui2_contract.text import TEXT_NOT_PROVIDED

R_DATA_NOT_WIRED = "資料健康度尚未開放；這裡不顯示任何來源狀態與資料日"


def _np(key: str, label: str, reason: str) -> dict:
    return {"key": key, "label": label, "value": None, "state": "not_provided", "sub_reason": TEXT_NOT_PROVIDED,
            "reason": reason, "fixed": True, "as_of": None, "source": None}


def data_page_canonical() -> dict:
    return {
        "page": P4_DATA, "title": PAGE_LABELS[P4_DATA],
        "current_state": _np("data_state", "資料健康度", R_DATA_NOT_WIRED),
        "context_rows": [],
        "action_needed": _np("data_action", "是否需要行動", "本頁不產生持股動作；動作權威＝💼 持股"),
        "next_step": _np("data_next", "下一步", "資料健康度清單開放後才可查看"),
        "cta": {"label": "查看資料健康度", "disabled_reason": "資料健康度尚未開放"},
        "cards": [],
        "sections": [
            {"key": "data_overview", "title": "資料來源與連線", "level": "L1", "fields": [
                _np("src_health", "來源健康度", R_DATA_NOT_WIRED),
                _np("data_asof", "資料日", R_DATA_NOT_WIRED),
                _np("active_sheet", "Active Sheet 連線", "登入與 Sheet 尚未開放")]},
        ],
    }
