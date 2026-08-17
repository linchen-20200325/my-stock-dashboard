"""L1 Repository — ETF 成分股（穿透用）。

主源 yfinance `funds_data.top_holdings`（Symbol 索引 + 'Holding Percent' 小數）。
純解析 `_normalize_holdings` 與 I/O 分離,可離線單測。
抓不到成分 → Fail Loud（§1）,交由 L2 穿透引擎標記「不完整」,不捏造權重。

⚠️ 已知限制：yfinance 對台股 ETF 成分覆蓋不穩;抓不到時本函式 raise,
上層（exposure_service）會把該 ETF 記為 incomplete → 覆蓋率下降、曝險標「下限」。
未來要補 TWSE/MoneyDJ 第二、三源時,於此函式加 fallback 鏈即可,介面不變。
"""
from __future__ import annotations

import pandas as pd

from ..core.circuit_breaker import require
from ..core.provenance import prov_log

_WEIGHT_COLS = ("Holding Percent", "holdingPercent", "% Assets", "weight")


def _strip_suffix(sym: str) -> str:
    """'2330.TW' → '2330'；'AAPL' → 'AAPL'（去交易所後綴,方便對齊直接持股代碼）。"""
    s = str(sym).strip().upper()
    return s.split(".")[0] if s else s


def _yahoo_symbol(ticker: str) -> str:
    """純台股數字代碼補 '.TW'；已有後綴或海外代碼原樣。"""
    s = str(ticker).strip().upper()
    if "." in s or not s:
        return s
    return f"{s}.TW" if s.isdigit() else s


def _normalize_holdings(raw: pd.DataFrame) -> dict[str, float]:
    """yfinance top_holdings DataFrame → {成分代號: 權重%}（純函式）。

    - 權重來源欄自動偵測；小數(0~1) → 自動 ×100 轉百分比。
    - key 優先用 Symbol（去後綴）,無則退成分名。
    """
    require(raw is not None and not raw.empty, "ETF 成分表為空")
    df = raw
    wcol = next((c for c in _WEIGHT_COLS if c in df.columns), None)
    require(wcol is not None, f"成分表缺權重欄,實際欄位={list(df.columns)}")

    if "Symbol" in df.columns:
        symbols = [str(x) for x in df["Symbol"].tolist()]
    else:
        symbols = [str(x) for x in df.index.tolist()]
    names = [str(x) for x in df["Name"].tolist()] if "Name" in df.columns else [""] * len(df)

    pairs: list[tuple[str, float]] = []
    for sym, nm, w in zip(symbols, names, df[wcol].tolist()):
        if pd.isna(w):
            continue
        key = _strip_suffix(sym) or str(nm).strip().upper()
        if not key or key.lower() in ("nan", "none"):
            continue
        wv = float(w)
        require(wv >= 0, f"成分權重不可為負: {key}={wv}")
        pairs.append((key, wv))
    require(len(pairs) > 0, "成分表無有效列")

    factor = 100.0 if max(w for _, w in pairs) <= 1.0 else 1.0   # 小數→百分比
    out: dict[str, float] = {}
    for key, w in pairs:
        out[key] = round(out.get(key, 0.0) + w * factor, 4)
    return out


def fetch_etf_holdings(ticker: str) -> dict[str, float]:
    """抓 ETF 成分 → {成分代號: 權重%}。抓不到 → Fail Loud。"""
    import yfinance as yf

    require(bool(ticker), "ticker 不可為空")
    err = None
    holdings = None
    try:
        raw = yf.Ticker(_yahoo_symbol(ticker)).funds_data.top_holdings
        holdings = _normalize_holdings(raw)
    except Exception as e:  # noqa: BLE001 - 統一轉 Fail Loud（帶原因）
        err = e
    require(bool(holdings),
            f"{ticker} 無法取得 ETF 成分（yfinance funds_data 無資料"
            f"{f'：{err}' if err else ''}）")
    prov_log("fetch_etf_holdings", source=f"yfinance:{ticker}:top_holdings",
             summary=f"{len(holdings)} 檔成分,權重和 {sum(holdings.values()):.1f}%",
             ticker=ticker)
    return holdings
