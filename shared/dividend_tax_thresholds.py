"""shared/dividend_tax_thresholds.py — 台股股利稅務常數 SSOT(L0)。

配息「稅後」試算用:二代健保補充保費 + 綜所稅股利二擇一(合併/分開)。
§3.3 反捏造:所有稅率/門檻/上限一律從本檔引入,禁止 inline。純常數模組,零 import 依賴。

法規依據(現行,量測日 2026-08-11;稅法會修 → 改這裡即全站同步):
- 二代健保補充保費率 2.11%;單筆給付 ≥ 20,000 元(含)才扣,單筆計費上限 1,000 萬元。
- 綜所稅股利二擇一:
    合併計稅 → 股利全額併入綜合所得按邊際稅率課,享 8.5% 可抵減稅額、每戶每年上限 8 萬元
             (股利 941,176 元時抵減達上限)。
    分開計稅 → 單一稅率 28%。
"""
from __future__ import annotations

# ── 二代健保補充保費(§4.1 金額單位:TWD 元)──────────────────────────────
NHI_SUPPLEMENTARY_RATE: float = 0.0211          # 補充保費率 2.11%
NHI_SINGLE_PAYMENT_MIN_TWD: int = 20_000        # 單筆給付 ≥ 此(含)才扣;< 此免扣
NHI_SINGLE_PAYMENT_CAP_TWD: int = 10_000_000    # 單筆計費上限(超過部分不計)

# ── 綜所稅股利二擇一(§4.1 金額 TWD、比率為小數)────────────────────────────
DIVIDEND_TAX_CREDIT_RATE: float = 0.085         # 合併計稅可抵減率 8.5%
DIVIDEND_TAX_CREDIT_CAP_TWD: int = 80_000       # 合併抵減每戶每年上限 8 萬元
DIVIDEND_SEPARATE_TAX_RATE: float = 0.28        # 分開計稅單一稅率 28%

# ── 綜所稅邊際稅率級距(UI 下拉;現行 5 級)─────────────────────────────────
MARGINAL_TAX_RATE_OPTIONS: tuple = (0.05, 0.12, 0.20, 0.30, 0.40)
