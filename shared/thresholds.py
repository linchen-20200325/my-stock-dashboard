"""v18.235 業務閾值 SSOT — 殖利率三段分級（357 策略）。

孫慶龍 / 郭俊宏「7%/5%/3% 殖利率估值法則」散落 8 檔 28 處 inline magic number，
集中為 3 個百分比常數 + 對應小數版本（便於分母除法 `est_div / YIELD_HIGH_DEC`）。

設計：純常數模組，零 import 依賴；caller 用
`from shared.thresholds import YIELD_HIGH, YIELD_MID, YIELD_LOW`。

對外 API：
- YIELD_HIGH = 7.0  便宜價 / 強烈買進區（殖利率 ≥ 7%）
- YIELD_MID  = 5.0  合理價 / 中性區（殖利率 5%~7%）
- YIELD_LOW  = 3.0  昂貴價 / 獲利了結（殖利率 ≤ 3%）
- YIELD_HIGH_DEC / YIELD_MID_DEC / YIELD_LOW_DEC：上述 / 100，供 `price = avg_div / YIELD_*_DEC` 反推目標價

來源：v18.230 P0 audit 列為 SSOT #5 違規；v5_modules.py:293-310 / tab_stock.py:1581/1637-1639/1657-1659/3066-3068
/ tab_stock_grp.py:231 / etf_tab_single.py:271-290 / etf_tab_grp_compare.py:57-63 / tab_stock_picker.py:444
/ scoring_helpers.py:104-109 / etf_tab_portfolio.py:759/764 共 8 檔 28 處全綠引用本模組。
"""
from __future__ import annotations

YIELD_HIGH: float = 7.0  # 便宜價 / 強烈買進（殖利率 ≥ 7%）
YIELD_MID: float = 5.0   # 合理價（殖利率 5%~7%）
YIELD_LOW: float = 3.0   # 昂貴價 / 獲利了結（殖利率 ≤ 3%）

YIELD_HIGH_DEC: float = YIELD_HIGH / 100  # 0.07 — 反推便宜價分母
YIELD_MID_DEC: float = YIELD_MID / 100    # 0.05 — 反推合理價分母
YIELD_LOW_DEC: float = YIELD_LOW / 100    # 0.03 — 反推昂貴價分母
