"""shared/etf_universe.py — 全球資金流向 ETF universe(L0 Infra)。

v18.424 Phase 2 Batch 2b:從 `src/compute/macro/flow_engine.py` 下沉至 L0。

**動機**:`REGIONAL_ETFS` / `CROSS_ASSET_ETFS` / `all_symbols()` 是「ETF 顯示名 →
yfinance 代號」配置 dict + merge helper,語意上是 L0 universe 配置非 L2 compute。
原放 L2 導致 L1 `src/data/daily/daily_data_fetchers.py:158` 需 `from src.compute.macro
import all_symbols`,違反 §8.2「L1 不得 import L2」硬規則。

**回溯相容**:`src/compute/macro/flow_engine.py` 改 thin re-export,既有 L2 caller
(flow_engine 內 caller / 任何下游 macro_compute)無感。

對外 API:
- `REGIONAL_ETFS: dict` — 世界區域股市 ETF universe
- `CROSS_ASSET_ETFS: dict` — 跨資產 ETF universe(風險情緒分數用)
- `all_symbols() -> dict` — 區域 + 跨資產合併
"""
from __future__ import annotations

# ── 世界區域股市(資金流向代理:相對報酬排名)────────────────────────────
REGIONAL_ETFS: dict[str, str] = {
    "美國 SPY": "SPY",
    "歐洲 VGK": "VGK",
    "日本 EWJ": "EWJ",
    "中國 FXI": "FXI",
    "新興市場 EEM": "EEM",
    "台灣 EWT": "EWT",
}

# ── 跨資產原始序列(風險情緒分數用;MOVE 可能抓不到 → 自動略過)──────────────
CROSS_ASSET_ETFS: dict[str, str] = {
    "股票 SPY": "SPY",
    "長天期美債 TLT": "TLT",
    "高收益債 HYG": "HYG",
    "投資級債 LQD": "LQD",
    "黃金 GLD": "GLD",
    "美元 UUP": "UUP",
    "美元日圓 USDJPY": "JPY=X",
    "VIX 波動率": "^VIX",
    "美債波動 MOVE": "^MOVE",
}


def all_symbols() -> dict:
    """區域 + 跨資產合併後的 {顯示名: yfinance 代號}(含重複代號如 SPY,抓取端會去重)。"""
    m = {}
    m.update(REGIONAL_ETFS)
    m.update(CROSS_ASSET_ETFS)
    return m
