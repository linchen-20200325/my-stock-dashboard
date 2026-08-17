"""L1 Repository — ETF 成分股（穿透用），兩源 fallback。

來源鏈（抓到就停）：
  1. yfinance `funds_data.top_holdings` — 海外 ETF 主源；台股常 None。
  2. 台灣 Yahoo 股市 `/quote/{代碼}/holding` — 台股 ETF 在地源（繞海外源封鎖）。

⚠️ 為何不是 TWSE：TWSE（mis.twse）只揭露 ETF **淨值/價格**,**不提供成分股權重**;
台股 ETF 成分的實務在地來源是台灣 Yahoo 股市 holding 頁（與主專案 etf_fetch 同源）。
官方 PCF（實物申購買回清單）為各投信逐檔揭露、格式雜,未納入本 fallback。

兩源都優先抓「成分**代號**」（去交易所後綴）→ 與直接持股代碼對齊,穿透才能去重複計數;
Yahoo 頁抓不到代號時退成分名（穿透引擎會把對不上的標「無法判定」,不假裝合併）。

純解析（`_normalize_holdings` / `_parse_yahoo_tw_holdings` / `_scale_to_percent`）與 I/O
分離,離線可單測。全鏈失敗 → Fail Loud（§1）,交 L2 穿透引擎標「不完整」,不捏造權重。
"""
from __future__ import annotations

import re

import pandas as pd

from ..core.circuit_breaker import FailLoudError, require
from ..core.provenance import prov_log

_WEIGHT_COLS = ("Holding Percent", "holdingPercent", "% Assets", "weight")
_YAHOO_TW_HOLDING_URL = "https://tw.stock.yahoo.com/quote/{sym}/holding"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_MAX_HOLDINGS = 60

# Yahoo TW 頁內嵌 JSON：同一物件內（不跨 {}）symbol/name 鍵 + 權重鍵就近配對
_YH_SYMBOL_RE = re.compile(
    r'"symbol"\s*:\s*"([^"]{1,12})"[^{}]{0,240}?'
    r'"(?:weighting|holdingPercent|percent|weight|ratio)"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?')
_YH_NAME_RE = re.compile(
    r'"(?:symbolName|holdingName|stockName|name)"\s*:\s*"([^"]{1,40})"[^{}]{0,240}?'
    r'"(?:weighting|holdingPercent|percent|weight|ratio)"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?')


def _strip_suffix(sym: str) -> str:
    """'2330.TW' → '2330'；'AAPL' → 'AAPL'（去交易所後綴,對齊直接持股代碼）。"""
    s = str(sym).strip().upper()
    return s.split(".")[0] if s else s


def _yahoo_symbol(ticker: str) -> str:
    """純台股數字代碼補 '.TW'；已有後綴或海外代碼原樣。"""
    s = str(ticker).strip().upper()
    if "." in s or not s:
        return s
    return f"{s}.TW" if s.isdigit() else s


def _scale_to_percent(raw: dict[str, float]) -> dict[str, float]:
    """統一權重單位：整組最大值 <=1 視為小數 → ×100；否則已是百分比。

    只保留 0<w<=100 的合理值（濾掉解析雜訊）。同 key 累加。
    """
    require(bool(raw), "無成分權重可正規化")
    factor = 100.0 if max(raw.values()) <= 1.0 else 1.0
    out: dict[str, float] = {}
    for k, v in raw.items():
        w = v * factor
        if 0 < w <= 100:
            out[k] = round(out.get(k, 0.0) + w, 4)
    require(bool(out), "成分權重全部超出合理範圍 (0,100]")
    return out


def _normalize_holdings(raw: pd.DataFrame) -> dict[str, float]:
    """yfinance top_holdings DataFrame → {成分代號: 權重%}（純函式）。"""
    require(raw is not None and not raw.empty, "ETF 成分表為空")
    df = raw
    wcol = next((c for c in _WEIGHT_COLS if c in df.columns), None)
    require(wcol is not None, f"成分表缺權重欄,實際欄位={list(df.columns)}")

    if "Symbol" in df.columns:
        symbols = [str(x) for x in df["Symbol"].tolist()]
    else:
        symbols = [str(x) for x in df.index.tolist()]
    names = [str(x) for x in df["Name"].tolist()] if "Name" in df.columns else [""] * len(df)

    raw_map: dict[str, float] = {}
    for sym, nm, w in zip(symbols, names, df[wcol].tolist()):
        if pd.isna(w):
            continue
        key = _strip_suffix(sym) or str(nm).strip().upper()
        if not key or key.lower() in ("nan", "none"):
            continue
        wv = float(w)
        require(wv >= 0, f"成分權重不可為負: {key}={wv}")
        raw_map[key] = raw_map.get(key, 0.0) + wv
    return _scale_to_percent(raw_map)


def _parse_yahoo_tw_holdings(html: str) -> dict[str, float]:
    """台灣 Yahoo holding 頁 HTML → {成分代號或名稱: 權重%}（純函式）。

    優先抓 symbol（代號,去後綴對齊直接持股）;抓不到 symbol 才退 name。
    """
    require(bool(html and html.strip()), "Yahoo TW 頁面為空")
    raw: dict[str, float] = {}
    for m in _YH_SYMBOL_RE.finditer(html):
        code = _strip_suffix(m.group(1))
        if not code or code.lower() in ("nan", "none"):
            continue
        raw.setdefault(code, float(m.group(2)))
        if len(raw) >= _MAX_HOLDINGS:
            break
    if not raw:                              # 無代號 → 退成分名
        for m in _YH_NAME_RE.finditer(html):
            nm = m.group(1).strip()
            if not nm or nm.isdigit():
                continue
            raw.setdefault(nm.upper(), float(m.group(2)))
            if len(raw) >= _MAX_HOLDINGS:
                break
    require(bool(raw), "Yahoo TW 頁面無可解析持股")
    return _scale_to_percent(raw)


# ── I/O 來源（可被測試 monkeypatch）─────────────────────────────────────
def _from_yfinance(ticker: str) -> dict[str, float]:
    import yfinance as yf

    raw = yf.Ticker(_yahoo_symbol(ticker)).funds_data.top_holdings
    return _normalize_holdings(raw)


def _from_yahoo_tw(ticker: str) -> dict[str, float]:
    import requests

    url = _YAHOO_TW_HOLDING_URL.format(sym=_yahoo_symbol(ticker))
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=15)
    require(r.status_code == 200, f"Yahoo TW 非 200：{r.status_code}")
    r.encoding = "utf-8"
    return _parse_yahoo_tw_holdings(r.text)


def fetch_etf_holdings(ticker: str) -> dict[str, float]:
    """抓 ETF 成分 → {成分代號: 權重%}。兩源依序 fallback,全敗 → Fail Loud。"""
    require(bool(ticker), "ticker 不可為空")
    # 於呼叫時解析 globals（便於測試 monkeypatch 兩段 fetcher）
    chain = (("yfinance", _from_yfinance), ("yahoo_tw", _from_yahoo_tw))
    errs: list[str] = []
    for name, fn in chain:
        try:
            holdings = fn(ticker)
        except Exception as e:  # noqa: BLE001 - 單源失敗續走下一源
            errs.append(f"{name}:{type(e).__name__}:{e}")
            continue
        if holdings:
            prov_log("fetch_etf_holdings",
                     source=f"{name}:{ticker}",
                     summary=f"{len(holdings)} 檔,權重和 {sum(holdings.values()):.1f}%",
                     ticker=ticker)
            return holdings
        errs.append(f"{name}:empty")
    raise FailLoudError(
        f"{ticker} 無法取得 ETF 成分（兩源皆敗：{' | '.join(errs)}）")
