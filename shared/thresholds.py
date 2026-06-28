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


def classify_yield_zone(cur_yield: float | None,
                         avg_yield: float | None = None) -> tuple[str, str]:
    """v18.331 PR-F U-8:357 殖利率分級 SSOT 函式。

    依當前殖利率 vs YIELD_HIGH/MID/LOW 三段分級,回 (label, code)。
    avg_yield 用於 ETF 估值脈絡的「需要 5y 平均」前提,個股 / ETF 三 Tab 共用。

    Args:
        cur_yield: 當前殖利率 %
        avg_yield: 5y 平均殖利率 %(可選,ETF 估值需此值才有意義 — 若提供且 ≤0 → '—')

    Returns:
        (label, code):
        - '🟢 強烈買進' / 'strong_buy'  ≥ 7%
        - '🟡 適度減碼' / 'reduce'      3% < cur ≤ 5%
        - '⚪ 中性持有' / 'neutral'      5% < cur < 7%
        - '🔴 獲利了結' / 'sell'        ≤ 3%
        - '—' / 'na'                    cur 為 None 或 avg_yield <= 0

    SSOT 政策:統一全專案殖利率分級判定;若 caller 需要不同 UX 措辭(教師結論等),
    可基於 code 做下游 UX 映射,本函式只負責純判別。
    """
    if cur_yield is None:
        return '—', 'na'
    if avg_yield is not None and (not avg_yield or avg_yield <= 0):
        # ETF 場景:需要 5y 平均才有估值脈絡
        return '—', 'na'
    if cur_yield >= YIELD_HIGH:
        return '🟢 強烈買進', 'strong_buy'
    if cur_yield <= YIELD_LOW:
        return '🔴 獲利了結', 'sell'
    if cur_yield <= YIELD_MID:
        return '🟡 適度減碼', 'reduce'
    return '⚪ 中性持有', 'neutral'
