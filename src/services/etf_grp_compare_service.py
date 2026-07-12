"""src/services/etf_grp_compare_service.py — ETF 多檔對比 L3 wrapper(v18.406 R4)。

對齊 user 建議 R4:`etf_tab_grp_compare.py:25` 直 import 3 個 L1 fetcher
(price / dividends / info)→ 集中至 L3。

§8.2 L3 service:thin pass-through(對齊 stock_grp_service 同 pattern)。
EX-PASSTHRU-1 Group A 升級觸發條件(3 fetcher 跨頻 cache,加 ETF 多檔對比新
功能會觸發 — 預先收斂避免日後散落)滿足。

未來擴充:若加跨 ETF 統一 TTL / 多源 fallback,集中本檔就近編輯。
"""
from __future__ import annotations

from typing import Any

from src.data.etf import fetch_etf_dividends, fetch_etf_info, fetch_etf_price


def get_etf_price(ticker: str, period: str = '5y') -> Any:
    """取得 ETF 歷史價格(yfinance auto_adjust 還原權息)。"""
    return fetch_etf_price(ticker, period)


def get_etf_dividends(ticker: str) -> Any:
    """取得 ETF 歷史配息 Series。"""
    return fetch_etf_dividends(ticker)


def get_etf_info(ticker: str) -> Any:
    """取得 ETF 基本資訊(name / category / aum 等)。"""
    return fetch_etf_info(ticker)


def ensure_etf_rf_injected() -> float | None:
    """抓即時 FEDFUNDS 注入 etf_calc 夏普無風險利率(v19.106 ⑨)。

    L3 service 職責:L3→L1 抓數(fetch_fed_funds_block,@st.cache_data 1h)+
    L3→L2 設值(set_risk_free_rate_pct)— 兩方向皆合 §8.2。批次評分前呼叫一次
    即可(setter 為模組級,ThreadPool worker 共見)。

    Returns:
        注入成功回 FEDFUNDS 當期值(% 年化);失敗回 None(etf_calc 維持
        SSOT fallback 5.33,行為 = 動態化前,§1 不腦補)。
    """
    import os
    try:
        from src.data.macro.macro_snapshot import fetch_fed_funds_block
        _ff = fetch_fed_funds_block(fred_api_key=os.environ.get('FRED_API_KEY', ''))
        _cur = (_ff.get('fed_funds') or {}).get('current')
        if _cur is not None:
            from src.compute.etf.etf_calc import set_risk_free_rate_pct
            set_risk_free_rate_pct(float(_cur))
            return float(_cur)
        print(f'[etf_grp_compare_service] FEDFUNDS 無值(維持 fallback): '
              f'{_ff.get("_err_fed_funds", "unknown")}')
    except Exception as _e:
        print(f'[etf_grp_compare_service] FEDFUNDS 注入失敗(維持 fallback): '
              f'{type(_e).__name__}: {_e}')
    return None
