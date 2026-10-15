"""shared/cross_quarter_thresholds.py — 跨季趨勢因子門檻 SSOT(L0).

全台股「跨季基本面趨勢」計算用的語意常數。斜率符號方向(毛利/營益率漲為佳、
負債比降為佳)寫死於 L2 語意,不在此列數值門檻。
"""
from __future__ import annotations

CROSS_QUARTER_MIN_POINTS: int = 3
"""單一比率序列要算「趨勢斜率」的最少季數;不足 → 該因子回 NaN(§1 誠實,不硬配)。
   ~~現有快照僅 5 季(114Q1–115Q1)且 QoQ 有季節性,3 季是「能看出方向」的最低門檻。~~
   —— 有意識的修改,不是漏刪(2026-10-15,AUD-C4):季數隨 cron 增加會漂移,不寫死
   (CLAUDE.md §8.2.A.0 規則 4;量測日 2026-10-15 為 6 季 114Q1–115Q2)。
   **現行**:快照季數少、且 QoQ 有季節性,3 季是「能看出方向」的最低門檻(值不變)。
   比率序列為**單季**比率(損益欄原為年初累計,斜率前先單季化,見
   src/compute/screener/cross_quarter_trends.py);單季化後缺前季 / 口徑斷層的季為 NaN,
   不計入有效點。"""
