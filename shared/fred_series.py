"""v18.237 FRED Series ID SSOT — Stock 端 PMI/Macro 系列散落 4 production 檔，集中為語意常數.

對稱 Fund 端 `shared/fred_series.py`（v19.70 交付），Stock-local（不走 sync_to_stock.sh，
範圍限 Stock 實際消費的 series subset）。
Replace pattern：`fetch_fred("NAPM", ...)` → `fetch_fred(FRED_NAPM, ...)`。

例外保留：
  - `test_macro_core.py` fixture：依測試契約保留字面值。
  - 註解/docstring/UI label（如 "ISM PMI（NAPM）"）：純文件描述，不需 import。

未來新增 FRED series 流程：本檔加常數 → call site `from shared.fred_series import FRED_<NAME>`。
"""
from __future__ import annotations

# ── ISM / PMI ──────────────────────────────────────────────────────
FRED_NAPM: str = "NAPM"                      # NAPM manufacturing (legacy series)
FRED_ISPMANPMI: str = "ISPMANPMI"            # ISM manufacturing PMI

# ── Regional Fed surveys ───────────────────────────────────────────
FRED_PHILLY_FED: str = "GACDFSA066MSFRBPHI"  # Philadelphia Fed manufacturing diffusion

# ── Activity / Sentiment (Proxies) ─────────────────────────────────
FRED_BSCICP02: str = "BSCICP02USM460S"       # OECD US Business Confidence (PMI proxy)
