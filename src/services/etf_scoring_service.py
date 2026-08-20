"""src/services/etf_scoring_service.py — ETF 評分編排 L3(v19.197 A1)。

§8.2 L3:ETF 評分前置編排的中性家。`build_etf_score_row`(L2)的夏普吃模組級
無風險利率 `etf_calc._RF_PCT`,評分**前**必須先注入即時 FEDFUNDS —— 這件事
語意上屬「ETF 評分編排」,不專屬多檔比較。

A1 修法(對稱性稽核):原 `ensure_etf_rf_injected` 只住在 `etf_grp_compare_service`
且只有多檔比較頁呼叫 → 單檔頁 build_etf_score_row 前從不注入 → 同一支 ETF 的
Sharpe/composite 依「本 process 稍早是否開過多檔頁」給兩種值(違 §5 冪等)。
把注入責任歸位到本中性 L3,單檔頁 + 多檔頁 + 任何 build_etf_score_row 入口
都從此處注入,兩頁行為即刻一致。`etf_grp_compare_service` 保留 re-export alias。
"""
from __future__ import annotations


def ensure_etf_rf_injected() -> float | None:
    """抓即時 FEDFUNDS 注入 etf_calc 夏普無風險利率(v19.106 ⑨,v19.197 A1 遷入)。

    L3 service 職責:L3→L1 抓數(fetch_fed_funds_block,@st.cache_data 1h)+
    L3→L2 設值(set_risk_free_rate_pct)— 兩方向皆合 §8.2。**任何 ETF 評分
    (build_etf_score_row)前呼叫一次**即可(setter 為模組級,ThreadPool worker 共見)。

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
        print(f'[etf_scoring_service] FEDFUNDS 無值(維持 fallback): '
              f'{_ff.get("_err_fed_funds", "unknown")}')
    except Exception as _e:  # noqa: BLE001 — §1 注入失敗維持 fallback,不腦補
        print(f'[etf_scoring_service] FEDFUNDS 注入失敗(維持 fallback): '
              f'{type(_e).__name__}: {_e}')
    return None
