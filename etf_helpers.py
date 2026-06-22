"""ETF 共用純函式 — Phase 7B 抽 closure 為 module-level。

零 Streamlit / Plotly 依賴；任何 module 皆可直接 import。
- norm_return / norm_lower_better：雷達圖五維分數正規化（etf_tab_backtest）
- auto_role：MK 框架 #9 核心/衛星分類（etf_tab_portfolio）
- normalize_etf_ticker：ETF 代號規範化 SSOT（純 4-6 碼補 .TW；v18.224）
- bare_etf_code：ETF 裸碼 SSOT（strip .TW/.TWO；v18.234）— normalize 反向
"""
from __future__ import annotations

import re as _re_etf_helpers

_TW_PURE_RE = _re_etf_helpers.compile(r'^\d{4,6}[A-Z]?$')


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


def bare_etf_code(raw: str | None) -> str:
    """ETF 裸碼 SSOT — strip `.TW` / `.TWO` 後綴並回大寫去空白；normalize_etf_ticker 的反向操作。

    場景：外部 API URL（yuanta / SITCA）/ 內部 lookup key / 中文名 enrich /
    is_active_etf 白名單比對 共用，避免 6+ 處 inline `.replace().upper()` 飄移。

    範例：
      '0050.TW'    → '0050'
      '00982A.TWO' → '00982A'（主動式 ETF 字母後綴保留）
      '  0050.tw ' → '0050'（大小寫無關 + 去空白）
      'SPY'        → 'SPY'（無 .TW 後綴原樣）
      ''/None      → ''
    """
    if not raw:
        return ''
    return str(raw).strip().upper().replace('.TWO', '').replace('.TW', '')


def auto_role(tk: str | None) -> str:
    """ETF 核心 / 衛星判讀：白名單命中回「核心」，其餘「衛星」。

    自動剝離 `.TW` / `.TWO` 後綴並轉大寫；空字串 / None → 衛星。
    """
    code = bare_etf_code(tk)
    return '核心' if code in _CORE_TICKERS else '衛星'


def normalize_etf_ticker(raw: str | None) -> str:
    """ETF 代號規範化 SSOT — 純 4-6 碼台股自動補 .TW；其餘原樣大寫去空白。

    場景：ETF 單檔診斷 / ETF 組合 / ETF 多檔批次評分 共用，user 不必手動加 .TW。
    範例：
      '0050'    → '0050.TW'
      '00919'   → '00919.TW'
      '00980A'  → '00980A.TW'（主動式 ETF）
      '0050.TW' → '0050.TW'（已含後綴原樣）
      'SPY'     → 'SPY'（美股無後綴）
      '  0056 ' → '0056.TW'（去空白）
      ''/None   → ''
    """
    if not raw:
        return ''
    _t = str(raw).strip().upper()
    if not _t:
        return ''
    if _TW_PURE_RE.fullmatch(_t):
        return f'{_t}.TW'
    return _t
