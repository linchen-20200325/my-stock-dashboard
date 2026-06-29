"""src/services/etf_sector_service.py — ETF 類股 / 新聞 L3 wrapper(v18.396 P5-B1)。

封裝 etf_render(L4)原直 import L1 `_fetch_sector_returns` / `_fetch_news_for`
所衍生的兩個 anti-pattern:
1. **L4→L1 跨層 import**(已登錄 §8.2.A EX-RENDER-1 例外)
2. **L4 直接 .clear() L1 cache**(`etf_render.py:594`)— 越權程度比 import 更深;
   有別的 caller 也用 `_fetch_sector_returns` 時會 unexpectedly invalidated。

L3 wrapper 集中:
- `get_sector_returns(tickers, period, *, refresh=False)`:封裝 fetch + 可選 cache invalidation
- `get_news_for(query, name, count)`:thin wrapper(無 cache 邏輯,純 forward)

§8.2 L3 service:caller 注入 L1 fetcher 為 module-level import(`from src.data.etf import ...`)
— 此處的 L3 → L1 import 屬於合法 L3 内部 fetcher composition(對齊
macro_fetch_orchestrator pattern)。
"""
from __future__ import annotations

from typing import Iterable

from src.data.etf import _fetch_news_for, _fetch_sector_returns


def get_sector_returns(
    tickers: tuple | Iterable[str],
    period: str,
    *,
    refresh: bool = False,
) -> dict:
    """抓 sector returns + 可選 cache invalidation。

    Args:
        tickers: ticker 代號 tuple / iterable(L1 fetcher 需 tuple hashable for cache key)
        period: 時間範圍字串(對齊 _fetch_sector_returns 的 period 參數)
        refresh: True → 強制清 L1 cache 重抓(原 etf_render `refresh` button 用)

    Returns:
        L1 fetcher 原 returns(dict ticker → return %)
    """
    _t = tuple(tickers) if not isinstance(tickers, tuple) else tickers
    if refresh:
        # 將 L4 anti-pattern(L4 直接 .clear() L1 cache)收斂到 L3 service。
        _fetch_sector_returns.clear()
    return _fetch_sector_returns(_t, period)


def get_news_for(query: str, name: str = '', count: int = 4) -> str:
    """新聞 thin wrapper(L4 render 直 import _fetch_news_for 的合法路徑)。

    本 wrapper 純 forward,無 cache 邏輯;主要目的是讓 L4 render 不直 import L1。
    """
    return _fetch_news_for(query, name, count)
