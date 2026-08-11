"""src/services/dividend_tax_service.py — 配息稅後試算編排(L3 service)。

編排:L1 取配息(fetch_etf_dividends)+ L2 幣別判定(portfolio_fx.holding_currency)+
L2 稅務純函式(dividend_tax)→ UI-ready 稅後 view。§8.2 L3:合法組合 L1 fetcher + L2 純函式。

職責:給 ETF 組合持股(代號 + 股數),逐檔取近 1 年**逐筆**配息(每股 × 股數)→
二代健保逐筆 + 綜所稅年度(合併/分開取較省)→ 稅前/稅後 + 每檔明細 + 海外標記。

§1 / §4.6:
- **海外/美元 ETF**(海外所得+最低稅負制,不適用國內二代健保與綜所稅二擇一)→ 排除稅務計算、
  僅標記,不混算。
- 抓不到配息 → 該檔 0,不捏造。
- marginal_rate=None → 只算二代健保、不算綜所稅(綜所稅需使用者選邊際率)。
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd

from src.data.etf import fetch_etf_dividends
from src.compute.etf.portfolio_fx import CURRENCY_USD, holding_currency
from src.compute.etf.dividend_tax import after_tax_dividend, nhi_premium

_LOOKBACK_DAYS = 365


def _recent_payments_twd(ticker, shares: int) -> list[float]:
    """近 `_LOOKBACK_DAYS` 天逐筆股利金額(TWD;每筆 = 該次每股配息 × 股數)。

    僅台幣 ETF 呼叫(海外已於上層排除)。抓不到/無配息 → []。tz-aware index 先去時區
    (對齊 etf_tab_portfolio 既有處理),避免與 naive cutoff 比較報錯。
    """
    _div_s = fetch_etf_dividends(ticker)
    if _div_s is None or len(_div_s) == 0:
        return []
    try:
        _idx = _div_s.index
        if getattr(_idx, "tz", None) is not None:
            _div_s = _div_s.copy()
            _div_s.index = _idx.tz_localize(None)
    except Exception as _e:                       # tz 去除失敗 → 不硬比,回空(§1 不猜)
        print(f"[dividend_tax/{ticker}] tz strip 失敗:{type(_e).__name__}: {_e}")
        return []
    _cutoff = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=_LOOKBACK_DAYS))
    _recent = _div_s[_div_s.index >= _cutoff]
    return [float(_v) * shares for _v in _recent.values if float(_v or 0.0) > 0]


def get_dividend_tax_view(holdings, *, marginal_rate=None) -> dict:
    """ETF 組合持股 → 配息稅後試算 view。

    Args:
        holdings: [{'ticker': str, 'shares': int}](通常來自 ETF 組合 rows)。
        marginal_rate: 綜所稅邊際稅率(0.05/.../0.40);None → 只算二代健保。

    Returns dict:
        summary   after_tax_dividend 結果(gross/nhi_premium/income_tax/tax_method/net_after_all…)
        per_etf   [{代號, 幣別, 近1年稅前配息, 二代健保, 配息筆數}](僅台幣 ETF)
        overseas  [代號](美元/海外 ETF,已排除稅務計算,僅標記)
        n_tw      納入計算的台幣 ETF 檔數
    """
    _tw_payments_all: list[float] = []
    _per_etf: list[dict] = []
    _overseas: list[str] = []

    for _h in holdings or []:
        _tk = str((_h or {}).get("ticker") or "").strip()
        try:
            _sh = int(round(float((_h or {}).get("shares") or 0)))
        except (TypeError, ValueError):
            _sh = 0
        if not _tk or _sh <= 0:
            continue
        if holding_currency(_tk) == CURRENCY_USD:      # §4.6 海外不適用國內稅制 → 排除標記
            _overseas.append(_tk)
            continue
        _pays = _recent_payments_twd(_tk, _sh)
        _tw_payments_all.extend(_pays)
        _per_etf.append({
            "代號": _tk,
            "幣別": "TWD",
            "近1年稅前配息": round(sum(_pays)),
            "二代健保": sum(nhi_premium(_p) for _p in _pays),
            "配息筆數": len(_pays),
        })

    _summary = after_tax_dividend(_tw_payments_all, marginal_rate=marginal_rate)
    return {
        "summary": _summary,
        "per_etf": _per_etf,
        "overseas": _overseas,
        "n_tw": len(_per_etf),
    }
