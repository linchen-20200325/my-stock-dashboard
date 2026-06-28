"""ETF 共用純函式 — Phase 7B 抽 closure 為 module-level。

零 Streamlit / Plotly 依賴；任何 module 皆可直接 import。
- auto_role：MK 框架 #9 核心/衛星分類（etf_tab_portfolio）
- normalize_etf_ticker：ETF 代號規範化 SSOT（純 4-6 碼補 .TW；v18.224）
- bare_etf_code：ETF 裸碼 SSOT（strip .TW/.TWO；v18.234）— normalize 反向
"""
from __future__ import annotations

import re as _re_etf_helpers

_TW_PURE_RE = _re_etf_helpers.compile(r'^\d{4,6}[A-Z]?$')


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


# ── v18.329 PR-D:ETF 三 Tab 共用判別函式 SSOT ──────────────────────
# 原 etf_tab_grp_compare.py file-local 函式,單檔/多檔/組合 Tab 統一 import。

def yield_valuation_zone(cur_yield, avg_yield):
    """7% 存股估值買賣點分級(孫慶龍策略)。

    Args:
        cur_yield: 當前殖利率 %
        avg_yield: 5y 平均殖利率 %(需有值才判定)

    Returns:
        '🟢 強烈買進' / '🔴 獲利了結' / '🟡 適度減碼' / '⚪ 中性持有' / '—'

    SSOT:三 Tab 共用(單檔 / 多檔 / 組合)。
    原 etf_tab_grp_compare.py:53-66 + etf_tab_single.py:272-295 inline 各自實作。
    """
    from shared.thresholds import YIELD_HIGH, YIELD_MID, YIELD_LOW
    if not avg_yield or avg_yield <= 0 or cur_yield is None:
        return '—'
    if cur_yield >= YIELD_HIGH:
        return '🟢 強烈買進'
    if cur_yield <= YIELD_LOW:
        return '🔴 獲利了結'
    if cur_yield <= YIELD_MID:
        return '🟡 適度減碼'
    return '⚪ 中性持有'


def dividend_health_label(cur_yield, total_ret_1y, cagr_3y):
    """配息健康度分級(MK 框架 #1+#2)。

    含息報酬 ≥ 殖利率 = 雙贏 ✅;含息 < 殖利率 = 本金侵蝕 🔴;
    無配息直接看 3Y CAGR ≥ ETF_CAGR_TARGET_PCT 達標 ✅ 否則 🟡。

    Args:
        cur_yield: 當前殖利率 %
        total_ret_1y: 近 1 年含息總報酬 %
        cagr_3y: 近 3 年年化報酬 %

    Returns:
        '✅ 雙贏 ...pp' / '🔴 吃本金 ...pp' / '✅ 無息但達標' / '🟡 ...' / '⬜ ...'

    SSOT:三 Tab 共用。原 etf_tab_grp_compare.py:69-85 + etf_tab_single.py:183-200 inline。
    """
    from shared.signal_thresholds import ETF_CAGR_TARGET_PCT
    if cur_yield is None or cur_yield <= 0:
        if cagr_3y is None:
            return '⬜ 資料不足'
        return '✅ 無息但達標' if cagr_3y >= ETF_CAGR_TARGET_PCT else '🟡 無息且未達標'
    if total_ret_1y is None:
        return '⬜ 1Y 報酬缺'
    if total_ret_1y < cur_yield:
        return f'🔴 吃本金 {total_ret_1y - cur_yield:+.1f}pp'
    return f'✅ 雙贏 {total_ret_1y - cur_yield:+.1f}pp'
