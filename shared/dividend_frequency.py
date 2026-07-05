"""ETF 配息頻率分類門檻 SSOT(v19.64)。

近 1 年配息「次數」→ 頻率標籤(月配 / 雙月配 / 季配 / 半年配 / 年配 / 不配息)。
用「次數區間」而非精確值:365 天窗口對月配 ETF 可能落 11 或 13 次,對季配可能 3~5 次。

設計:純常數模組,零 import 依賴。caller 用
`from shared.dividend_frequency import PAY_FREQ_MONTHLY_MIN, ...`。
"""
from __future__ import annotations

# 次數下限(含):n_payments ≥ 此值 → 該頻率(由高到低比對)。
PAY_FREQ_MONTHLY_MIN: int = 10     # ≥10 → 月配
PAY_FREQ_BIMONTHLY_MIN: int = 6    # 6~9 → 雙月配
PAY_FREQ_QUARTERLY_MIN: int = 3    # 3~5 → 季配
PAY_FREQ_SEMIANNUAL_MIN: int = 2   # 2    → 半年配
PAY_FREQ_ANNUAL_MIN: int = 1       # 1    → 年配;0 → 不配息

# 頻率標籤(UI 顯示 + golden test 釘一致)。
PAY_FREQ_LABEL_MONTHLY: str = "月配"
PAY_FREQ_LABEL_BIMONTHLY: str = "雙月配"
PAY_FREQ_LABEL_QUARTERLY: str = "季配"
PAY_FREQ_LABEL_SEMIANNUAL: str = "半年配"
PAY_FREQ_LABEL_ANNUAL: str = "年配"
PAY_FREQ_LABEL_NONE: str = "不配息"
