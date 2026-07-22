"""shared/cross_quarter_thresholds.py — 跨季趨勢因子門檻 SSOT(L0).

全台股「跨季基本面趨勢」計算用的語意常數。斜率符號方向(毛利/營益率漲為佳、
負債比降為佳)寫死於 L2 語意,不在此列數值門檻。
"""
from __future__ import annotations

CROSS_QUARTER_MIN_POINTS: int = 3
"""單一比率序列要算「趨勢斜率」的最少季數;不足 → 該因子回 NaN(§1 誠實,不硬配)。
   現有快照僅 5 季(114Q1–115Q1)且 QoQ 有季節性,3 季是「能看出方向」的最低門檻。"""
