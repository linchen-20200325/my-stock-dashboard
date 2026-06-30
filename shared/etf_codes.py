"""shared/etf_codes.py — ETF 代號規範化 SSOT(L0 Infra)。

v18.423 Phase 2 Batch 2:從 `src/compute/etf/etf_helpers.py` 下沉至 L0。

**動機**:`bare_etf_code` 是純字串 helper(strip `.TW` / `.TWO` 後綴 + 大寫去空白),
語意上是 L0 工具非 L2 compute。原放 L2 導致 L1 `src/data/etf/etf_fetch.py` × 8 處
+ L1 `src/data/daily/daily_data_fetchers.py` 需 `from src.compute.etf import ...`
即 L1→L2 反向 import,違反 §8.2「L1 不得 import L2/L3」硬規則。

**回溯相容**:`src/compute/etf/etf_helpers.py:bare_etf_code` 改 thin re-export,
所有既有 caller(L2 etf_calc / L5 tab_stock_picker / L5 etf_tab_portfolio)無感。

對外 API:
- `bare_etf_code(raw: str | None) -> str`
"""
from __future__ import annotations


def bare_etf_code(raw: str | None) -> str:
    """ETF 裸碼 SSOT — strip `.TW` / `.TWO` 後綴並回大寫去空白;normalize_etf_ticker 的反向操作。

    場景:外部 API URL(yuanta / SITCA)/ 內部 lookup key / 中文名 enrich /
    is_active_etf 白名單比對 共用,避免 6+ 處 inline `.replace().upper()` 飄移。

    範例:
      '0050.TW'    → '0050'
      '00982A.TWO' → '00982A'(主動式 ETF 字母後綴保留)
      '  0050.tw ' → '0050'(大小寫無關 + 去空白)
      'SPY'        → 'SPY'(無 .TW 後綴原樣)
      ''/None      → ''
    """
    if not raw:
        return ''
    return str(raw).strip().upper().replace('.TWO', '').replace('.TW', '')
