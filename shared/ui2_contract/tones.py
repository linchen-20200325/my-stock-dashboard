"""Chip 語意色調四族（Freeze §4.1；客戶 §4）。

Positive／Allowed：真正正向的 deterministic state
Warning：需注意
Danger：deterministic violation／Risk Cap（文字須與「取得失敗」不同）
Neutral／Info：類型、產業、計數、估值口徑、資料來源

⛔ 不得拿警告族元件（Legacy 的 `guard_chip`）承載中性資訊。
"""
from __future__ import annotations

from enum import Enum


class ChipTone(str, Enum):
    POSITIVE = "positive"
    WARNING = "warning"
    DANGER = "danger"
    NEUTRAL_INFO = "neutral_info"


#: 狀態符號（顏色不是唯一載體；Freeze §4.1）。Neutral 可無符號。
TONE_SYMBOL: dict[ChipTone, str] = {
    ChipTone.POSITIVE: "✅",
    ChipTone.WARNING: "⚠",
    ChipTone.DANGER: "🔴",
    ChipTone.NEUTRAL_INFO: "ℹ",
}
