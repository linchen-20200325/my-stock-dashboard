"""src/data/sector_flow/ — 板塊資金潮汐本地快取讀取(L1 Data).

Stage 2:讀 cron(scripts/update_sector_flow.py)每交易日凍結在
`data_cache/sector_flow/` 的三個檔,回結構化 view 給 L3 service 編排。
純檔案 I/O,無 streamlit(§8.2 L1)。
"""
from __future__ import annotations

from .reader import read_sector_flow_cache  # noqa: F401
