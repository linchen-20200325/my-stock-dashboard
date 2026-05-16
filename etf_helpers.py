"""ETF 共用純函式 — Phase 7B 抽 closure 為 module-level。

零 Streamlit / Plotly 依賴；任何 module 皆可直接 import。
- norm_return / norm_lower_better：雷達圖五維分數正規化（etf_tab_backtest）
- auto_role：MK 框架 #9 核心/衛星分類（etf_tab_portfolio）
"""
from __future__ import annotations


def norm_return(v: float, lo: float = -50, mid: float = 0, hi: float = 50) -> float:
    """報酬類指標 0-100 正規化，越大越好。

    分段線性：v ≥ hi → 100；v ≤ lo → 0；mid 對應 50。
    """
    if v >= hi:
        return 100
    if v <= lo:
        return 0
    if v >= mid:
        return 50 + (v - mid) / (hi - mid) * 50
    return (v - lo) / (mid - lo) * 50


def norm_lower_better(v: float, best: float = 5, mid: float = 20, worst: float = 35) -> float:
    """風險類指標 0-100 正規化（先取絕對值），越小越好。

    分段線性：|v| ≤ best → 100；|v| ≥ worst → 0；mid 對應 50。
    """
    v = abs(v)
    if v <= best:
        return 100
    if v >= worst:
        return 0
    if v <= mid:
        return 100 - (v - best) / (mid - best) * 50
    return 50 - (v - mid) / (worst - mid) * 50


# MK 框架 #9：核心持股白名單（高股息大型 / 全市場 / 債券）
_CORE_TICKERS: frozenset[str] = frozenset({
    '0050', '0051', '0056', '006208', '00713', '00878', '00919', '00929',
    '00940', '00946', '00713B', '00679B', '00937B',
    'BND', 'AGG', 'VTI', 'VOO', 'SPY', 'VT', 'SCHD', 'VEA', 'VWO', 'VNQ',
})


def auto_role(tk: str | None) -> str:
    """ETF 核心 / 衛星判讀：白名單命中回「核心」，其餘「衛星」。

    自動剝離 `.TW` / `.TWO` 後綴並轉大寫；空字串 / None → 衛星。
    """
    code = (tk or '').replace('.TWO', '').replace('.TW', '').upper()
    return '核心' if code in _CORE_TICKERS else '衛星'
