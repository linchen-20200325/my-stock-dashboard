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

    ETF 場景必須有 5y 平均殖利率作為估值脈絡,否則回 '—'。

    Args:
        cur_yield: 當前殖利率 %
        avg_yield: 5y 平均殖利率 %(None 或 ≤0 → 不判定)

    Returns:
        '🟢 強烈買進' / '🔴 獲利了結' / '🟡 適度減碼' / '⚪ 中性持有' / '—'

    SSOT:三 Tab 共用(單檔 / 多檔 / 組合)。內部 delegate to
    shared.thresholds.classify_yield_zone(v18.331 PR-F U-8 統一判別函式)。
    本 wrapper 額外要求 avg_yield 必須有值(ETF 場景),保留原 etf_tab_grp_compare contract。
    """
    from shared.thresholds import classify_yield_zone
    # ETF 場景:None 視為無 avg → N/A(個股場景可省 avg,classify_yield_zone 允許)
    if avg_yield is None:
        return '—'
    label, _code = classify_yield_zone(cur_yield, avg_yield)
    return label


def calc_sigma_metrics(df, window: int = 252) -> dict:
    """v18.334 PR-H2:ETF σ 統計指標 SSOT(統一計算層,不統一分級邏輯)。

    R-3 audit 部分統一方案:計算層統一,分級邏輯保留兩套(短/長線分離)。
    既消除 etf_calc.py:84 vs etf_tab_single.py:482-483 重複實作,
    又保留各 Tab 的 UX 意圖(快速戰情燈號 vs 教學量化買點)。

    Args:
        df: ETF 價格 DataFrame(需含 'Close' 欄)
        window: 取樣視窗(預設 252 交易日 ≈ 1 年)

    Returns:
        dict {
          'std_price': float | None,        # 近 window 日「價格」標準差(MA20±nσ 用)
          'std_pct_annual': float | None,   # 年化「百分比」波動率 %(z-score 用)
          'ma20': float | None,             # 20 日均線(短線基準 — Quick Sigma)
          'ma60': float | None,             # 60 日均線(中線基準)
          'ma240': float | None,            # 240 日均線(長線基準 — Deep Sigma)
          'n': int,                          # 實際採樣筆數
        }
        資料不足時對應欄位為 None,函式不 raise(讓 caller 決定 fallback UI)。

    SSOT 政策:
      · etf_calc._compute_etf_warroom_row(短線):用 std_price + ma20 → MA20±nσ 5 段
      · etf_tab_single MK#11 σ 卡(長線):用 std_pct_annual + ma240 → z-score 4 段
      · 任何新 σ 用途均應從此函式取 metrics,不再 inline 計算
    """
    import math as _math
    _out = {
        'std_price': None, 'std_pct_annual': None,
        'ma20': None, 'ma60': None, 'ma240': None,
        'n': 0,
    }
    if df is None or len(df) == 0 or 'Close' not in df.columns:
        return _out
    _close = df['Close']
    _n = len(_close)
    _out['n'] = _n

    if _n >= 20:
        _out['ma20'] = float(_close.rolling(20).mean().iloc[-1])
    if _n >= 60:
        _out['ma60'] = float(_close.rolling(60).mean().iloc[-1])
    if _n >= 240:
        _out['ma240'] = float(_close.rolling(240).mean().iloc[-1])

    if _n >= window:
        _tail = _close.tail(window)
        _std_p = float(_tail.std())
        if _std_p > 0 and not _math.isnan(_std_p):
            _out['std_price'] = _std_p
        _ret = _tail.pct_change().dropna()
        if not _ret.empty:
            _std_pct = float(_ret.std()) * (window ** 0.5) * 100
            if _std_pct > 0 and not _math.isnan(_std_pct):
                _out['std_pct_annual'] = _std_pct

    return _out


def classify_etf_quick_sigma(cur: float, ma20: float,
                              std_price: float) -> tuple[str, str, str] | None:
    """v18.335 PR-H3:⚡短線 σ 位階分級 SSOT(MA20±nσ 5 段戰情燈號)。

    原 etf_calc.py:_compute_etf_warroom_row inline hardcode 已抽出。

    Args:
        cur: 當前收盤價
        ma20: 20 日均線
        std_price: 近 1 年日 close 標準差(來自 calc_sigma_metrics['std_price'])

    Returns:
        (emoji, label, action) tuple,任一參數無效時回 None。
        emoji/label 已含「⚡短線」前綴(PR-H2 UX 標註)。

    SSOT 政策:任何用 MA20±nσ 戰情燈號的場景均應呼叫本函式,不再 inline 5 段判斷。
    分級邏輯與閾值來自 shared.signal_thresholds.ETF_QUICK_SIGMA_*(v18.331 PR-F U-7)。
    """
    from shared.signal_thresholds import (
        ETF_QUICK_SIGMA_CHEAP, ETF_QUICK_SIGMA_DISASTER,
        ETF_QUICK_SIGMA_HIGH, ETF_QUICK_SIGMA_OVERBOUGHT,
        ETF_QUICK_SIGMA_OVERSOLD,
    )
    if cur is None or ma20 is None or not std_price or std_price <= 0:
        return None
    _lo3 = ma20 - ETF_QUICK_SIGMA_DISASTER * std_price
    _lo2 = ma20 - ETF_QUICK_SIGMA_OVERSOLD * std_price
    _lo1 = ma20 - ETF_QUICK_SIGMA_CHEAP * std_price
    _hi15 = ma20 + ETF_QUICK_SIGMA_HIGH * std_price
    _hi2 = ma20 + ETF_QUICK_SIGMA_OVERBOUGHT * std_price
    if cur < _lo3:
        return ('🟢🟢🟢', f'⚡短線 股災價(<-{ETF_QUICK_SIGMA_DISASTER:.0f}σ)', '大買 50%')
    if cur < _lo2:
        return ('🟢🟢', f'⚡短線 超跌價(<-{ETF_QUICK_SIGMA_OVERSOLD:.0f}σ)', '買 30%')
    if cur < _lo1:
        return ('🟢', f'⚡短線 便宜價(<-{ETF_QUICK_SIGMA_CHEAP:.0f}σ)', '小買 20%')
    if cur >= _hi2:
        return ('🔴', f'⚡短線 準備停利(≥+{ETF_QUICK_SIGMA_OVERBOUGHT:.0f}σ)', '分批停利')
    if cur >= _hi15:
        return ('🟠', f'⚡短線 偏高(≥+{ETF_QUICK_SIGMA_HIGH:.1f}σ)', '不追高/減碼')
    return ('⚪', f'⚡短線 中性區(±{ETF_QUICK_SIGMA_CHEAP:.0f}σ)', '靜待訊號')


def classify_etf_deep_sigma(cur: float, ma240: float,
                             std_pct_annual: float) -> tuple[str, str, str] | None:
    """v18.335 PR-H3:📅長線 σ 位階分級 SSOT(MA240 z-score 4 段教學)。

    原 etf_tab_single.py:MK#11 σ 卡 inline 已抽出。

    Args:
        cur: 當前收盤價
        ma240: 240 日均線(年線)
        std_pct_annual: 年化百分比波動率(來自 calc_sigma_metrics['std_pct_annual'])

    Returns:
        (label, color, action) tuple — label 含「📅長線」前綴 + emoji。
        color ∈ {'green', 'yellow', 'red'} 供 _colored_box 用。
        任一參數無效時回 None。

    SSOT 政策:MA240 z-score 教學量化買點均呼叫本函式;
    閾值來自 shared.signal_thresholds.ETF_SIGMA_*(PR-D 已抽)。
    """
    from shared.calc_helpers import calc_bias_pct  # C1 v18.401:乖離率 SSOT
    from shared.signal_thresholds import (
        ETF_SIGMA_BUY, ETF_SIGMA_DEEP_BUY,
        ETF_SIGMA_REDUCE, ETF_SIGMA_STOP_PROFIT,
    )
    if cur is None or ma240 is None or not std_pct_annual or std_pct_annual <= 0:
        return None
    _bias_pct = calc_bias_pct(cur, ma240)
    if _bias_pct is None:
        return None
    _z = _bias_pct / std_pct_annual
    if _z <= ETF_SIGMA_DEEP_BUY:
        return (f'🟢 📅長線 極佳買點(≤ {ETF_SIGMA_DEEP_BUY:.0f}σ)', 'green',
                '大跌大買 — 大幅加碼，剩餘資金主力投入')
    if _z <= ETF_SIGMA_BUY:
        return (f'🟢 📅長線 進場買點({ETF_SIGMA_DEEP_BUY:.0f}σ ~ {ETF_SIGMA_BUY:.0f}σ)',
                'green', '小跌小買 — 投入 20–30% 資金')
    if _z <= ETF_SIGMA_REDUCE:
        return (f'🟡 📅長線 持平區(±{ETF_SIGMA_REDUCE:.0f}σ 內)', 'yellow',
                f'保留現金，等待 ≤ {ETF_SIGMA_BUY:.0f}σ 進場')
    if _z <= ETF_SIGMA_STOP_PROFIT:
        return (f'🟠 📅長線 偏高(+{ETF_SIGMA_REDUCE:.0f}σ ~ +{ETF_SIGMA_STOP_PROFIT:.0f}σ)',
                'yellow', '不追高；衛星部位可考慮停利')
    return (f'🔴 📅長線 極端偏高(≥ +{ETF_SIGMA_STOP_PROFIT:.0f}σ)', 'red',
            f'建議減碼；勿在 +{ETF_SIGMA_STOP_PROFIT:.0f}σ 以上加碼')


def compute_etf_annual_cashflow(div_series, shares: int,
                                 lookback_days: int = 365) -> dict | None:
    """v18.335 PR-H3:ETF 單檔近 N 日年化配息預估 + 月度分配 SSOT。

    原 etf_tab_portfolio.py:721-753 inline 年現金流彙整邏輯抽出為純函式。
    純計算層(L2),零 Streamlit / fetch I/O 依賴;caller 負責先 fetch_etf_dividends。

    Args:
        div_series: ETF 歷史配息 pandas Series(index 為 ex-dividend date)
        shares: 持有股數(整數;0 視為未持有)
        lookback_days: 回看窗口(預設 365,即近 1 年)

    Returns:
        dict {
          'annual_per_share': float,   # 近 N 日每股配息總額
          'estimated_income': float,    # annual_per_share × shares
          'n_payments': int,            # 近 N 日配息次數
          'monthly_distribution': dict, # {1: amount, 2: amount, ..., 12: amount} 月度
        }
        無持股 / 無近期配息 → None(caller 跳過此 ETF)。

    SSOT 政策:投組層年配息估算的核心彙整邏輯;
    portfolio Tab 對每檔 ETF 呼叫一次,再加總得組合總現金流。
    """
    import numpy as _np
    import pandas as _pd
    if div_series is None or len(div_series) == 0 or shares <= 0:
        return None
    _cutoff = _pd.Timestamp.now() - _pd.DateOffset(days=lookback_days)
    _recent = div_series[div_series.index >= _cutoff]
    if _recent.empty:
        return None
    _sum = _recent.sum()
    _annual_per_share = (float(_np.ravel(_sum)[0])
                          if hasattr(_sum, '__len__') else float(_sum))
    _n_pay = len(_recent)
    _est_income = _annual_per_share * shares
    _monthly = {m: 0.0 for m in range(1, 13)}
    for _m in sorted(set(_recent.index.month.tolist())):
        _ms = _recent[_recent.index.month == _m].sum()
        _month_div = ((float(_np.ravel(_ms)[0]) if hasattr(_ms, '__len__')
                       else float(_ms)) * shares)
        _monthly[_m] += _month_div
    return {
        'annual_per_share': _annual_per_share,
        'estimated_income': _est_income,
        'n_payments': _n_pay,
        'monthly_distribution': _monthly,
    }


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
