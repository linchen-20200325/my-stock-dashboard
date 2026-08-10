"""src/data/stock/market_close_fetcher.py — 全市場「每日收盤價」+「產業別」raw fetcher(L1)。

板塊資金泡泡圖 Stage 1 的兩個新增資料需求(三大法人已由
`data_loader_inst_fetchers._get_t86_day / _get_tpex_day` 供應,直接重用):

1. 全市場**每日收盤價**(元/股)—— 供「張 → 金額」換算:
   - `fetch_twse_close_day(ds)` : TWSE MI_INDEX(帶 date,官方 T1、免 token),回 {code: close}
   - `fetch_tpex_close_day(ds)` : TPEX 上櫃每日收盤(帶 ROC date,官方 T1、免 token)
   兩者皆「逐日全市場」介面(給定 YYYYMMDD 回當日全市場),bootstrap 逐日回補 +
   incremental 每晚只補最新交易日,皆走同一函式(§5 冪等/可重現)。

2. ticker → **產業別**對照:
   - `fetch_industry_map_bulk()` : FinMind `TaiwanStockInfo` 整表(不帶 data_id;
     非時間序列,理論不受 date-bulk gate)為主 → TWSE `t187ap03_L` + TPEX `t187ap03_O`
     官方 openapi(T1 免 token)補齊仍缺者。

§8.2 layer:L1 Data — 只 `requests` + `src.data.proxy.fetch_url`(NAS proxy → 直連降級,
GitHub runner 免 proxy 自動直連),**不 import streamlit**、不算業務邏輯(彙總在 L2)。
§1 Fail Loud:某源/某日抓不到 → 回空 dict + log,**絕不**回假資料 / 補 0 冒充收盤;
欄位定位一律動態偵測,parse 全失敗 loud log。
"""
from __future__ import annotations

import datetime as _dt
import os as _os

import requests

from shared.roc_calendar import gregorian_to_roc_year

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
_HDR_JSON = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _fetch(url: str, params: dict | None = None, timeout: int = 20,
           headers: dict | None = None):
    """走 src.data.proxy.fetch_url;缺 helper(極簡環境)時 fallback 直連。

    與 `update_macro_history._fetch_url_via_proxy` 同款:runner 上 PROXY_URL 未設 →
    fetch_url 內部自動降級直連,TWSE/TPEX openapi 全球可達、免 proxy。
    """
    try:
        from src.data.proxy import fetch_url as _furl
        return _furl(url, params=params, timeout=timeout,
                     headers=headers or _HDR_JSON, attempts=2)
    except ImportError:
        try:
            return requests.get(url, params=params, timeout=timeout,
                                headers=headers or _HDR_JSON)
        except Exception as e:  # §1:不吞例外,log 後回 None
            print(f"[market_close] 直連 fallback 失敗 {url[:60]}: "
                  f"{type(e).__name__}: {e}")
            return None


def _to_float(v) -> float | None:
    """TWSE/TPEX 數字字串 → float;'--' / '' / 'X' 等無效值回 None(§1 不臆造 0)。"""
    s = str(v).replace(",", "").replace("+", "").strip()
    if s in ("", "--", "---", "X", "N/A", "null", "None"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# ══════════════════════════════════════════════════════════════════════
# 1. 全市場每日收盤價
# ══════════════════════════════════════════════════════════════════════
def fetch_twse_close_day(ds: str) -> dict:
    """TWSE 上市全市場單日收盤價。ds=YYYYMMDD。回 {股票代碼: 收盤價(元/股)}。

    來源:MI_INDEX type=ALLBUT0999,回應 `tables` 內「每日收盤行情(全部)」表
    (含每檔 證券代號 + 收盤價)。欄位索引依 `fields` **動態定位**(勿硬編);
    假日/休市 stat!=OK → 回 {}(§1:自然排除,不補值)。
    """
    try:
        r = _fetch("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
                   params={"response": "json", "date": ds, "type": "ALLBUT0999"},
                   timeout=20)
        if r is None or getattr(r, "status_code", 0) != 200:
            print(f"[TWSE close] {ds} HTTP={getattr(r, 'status_code', 'None')}")
            return {}
        j = r.json()
        if j.get("stat") != "OK":
            # 假日/無資料日:TWSE 明確回非 OK → 空(語意正確,非錯誤)
            return {}
        tables = j.get("tables") or ([{"fields": j.get("fields"),
                                       "data": j.get("data")}]
                                     if j.get("data") else [])
        out: dict = {}
        for tbl in tables:
            fields = [str(f) for f in (tbl.get("fields") or [])]
            if not fields:
                continue
            code_idx = next((i for i, n in enumerate(fields)
                             if "證券代號" in n or "股票代號" in n), None)
            close_idx = next((i for i, n in enumerate(fields)
                              if "收盤價" in n), None)
            if code_idx is None or close_idx is None:
                continue
            for row in tbl.get("data") or []:
                if len(row) <= max(code_idx, close_idx):
                    continue
                code = str(row[code_idx]).strip()
                close = _to_float(row[close_idx])
                if code and close is not None and close > 0:
                    out[code] = close
            if out:
                break   # 命中含 證券代號+收盤價 的表即止
        if not out:
            print(f"[TWSE close] {ds} 解析 0 筆(fields 未含 證券代號/收盤價?)")
        else:
            print(f"[TWSE close] {ds}: {len(out)} 檔")
        return out
    except Exception as e:
        print(f"[TWSE close] {ds} 失敗: {type(e).__name__}: {e}")
        return {}


def fetch_tpex_close_day(ds: str) -> dict:
    """TPEX 上櫃全市場單日收盤價。ds=YYYYMMDD。回 {股票代碼: 收盤價(元/股)}。

    來源:櫃買「上櫃股票每日收盤行情(不含定價)」RWD php(帶 ROC date,可回補歷史)。
    aaData 每列:[代號, 名稱, 收盤, 漲跌, 開盤, 最高, 最低, 成交股數, 成交金額, ...]。
    收盤欄位以「代號右側第一個有效數值」動態定位(勿硬編),避免版本欄序差異。
    假日/無資料 → aaData 空 → 回 {}(§1 自然排除)。
    """
    try:
        dt = _dt.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
        roc_date = f"{gregorian_to_roc_year(dt.year)}/{dt.month:02d}/{dt.day:02d}"
        r = _fetch(
            "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/"
            "stk_wn1430_result.php",
            params={"l": "zh-tw", "d": roc_date, "o": "json"},
            timeout=20,
            headers={**_HDR_JSON, "Referer": "https://www.tpex.org.tw/"})
        if r is None or getattr(r, "status_code", 0) != 200:
            print(f"[TPEX close] {ds} HTTP={getattr(r, 'status_code', 'None')}")
            return {}
        j = r.json()
        rows = j.get("aaData") or j.get("data") or []
        out: dict = {}
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 3:
                continue
            code = str(row[0]).strip()
            if not code or not code[0].isdigit():
                continue
            # 收盤 = 代號、名稱之後的第一個有效數值(通常 index 2)
            close = None
            for idx in range(2, min(len(row), 6)):
                close = _to_float(row[idx])
                if close is not None:
                    break
            if code and close is not None and close > 0:
                out[code] = close
        if not out:
            print(f"[TPEX close] {ds} ({roc_date}) 解析 0 筆")
        else:
            print(f"[TPEX close] {ds} ({roc_date}): {len(out)} 檔")
        return out
    except Exception as e:
        print(f"[TPEX close] {ds} 失敗: {type(e).__name__}: {e}")
        return {}


# ══════════════════════════════════════════════════════════════════════
# 2. ticker → 產業別對照(整表 bulk)
# ══════════════════════════════════════════════════════════════════════
def _finmind_industry_map(token: str) -> dict:
    """FinMind TaiwanStockInfo 整表(不帶 data_id)→ {code: industry_category}。

    憑證只走 header(不進 query string,對齊 §資安慣例)。回空 = 失敗/被 gate。
    """
    hdr = dict(_HDR_JSON)
    if token:
        hdr["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(FINMIND_URL, params={"dataset": "TaiwanStockInfo"},
                         headers=hdr, timeout=30)
        if r.status_code != 200:
            print(f"[industry/FinMind] HTTP={r.status_code} body={r.text[:160]}")
            return {}
        d = r.json()
        if d.get("status") != 200:
            print(f"[industry/FinMind] status={d.get('status')} "
                  f"msg={d.get('msg', '')}")
            return {}
        out: dict = {}
        for row in d.get("data", []) or []:
            code = str(row.get("stock_id", "")).strip()
            ind = str(row.get("industry_category", "")).strip()
            if code and ind and code not in out:
                out[code] = ind
        print(f"[industry/FinMind] TaiwanStockInfo: {len(out)} 檔")
        return out
    except Exception as e:
        print(f"[industry/FinMind] ❌ {type(e).__name__}: {e}")
        return {}


def _openapi_industry_map() -> dict:
    """TWSE t187ap03_L(上市)+ TPEX t187ap03_O(上櫃)官方 openapi → {code: 產業別}。

    T1 免 token 備援(FinMind 被 gate 時用)。欄名容錯:公司代號/Code、產業別/
    Industry。回空 = 全失敗。
    """
    out: dict = {}
    sources = [
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "https://openapi.twse.com.tw/v1/opendata/t187ap03_O",
    ]
    for url in sources:
        try:
            r = _fetch(url, timeout=15)
            if r is None or getattr(r, "status_code", 0) != 200:
                print(f"[industry/openapi] {url.split('/')[-1]} "
                      f"HTTP={getattr(r, 'status_code', 'None')}")
                continue
            data = r.json()
            if not isinstance(data, list):
                continue
            before = len(out)
            for item in data:
                code = str(item.get("公司代號", item.get("Code", ""))).strip()
                ind = str(item.get("產業別",
                                   item.get("Industry",
                                            item.get("industry_category", "")))
                          ).strip()
                if code and ind and code not in out:
                    out[code] = ind
            print(f"[industry/openapi] {url.split('/')[-1]}: +{len(out) - before} 檔")
        except Exception as e:
            print(f"[industry/openapi] {url.split('/')[-1]} ❌ "
                  f"{type(e).__name__}: {e}")
    return out


def fetch_industry_map_bulk(token: str | None = None) -> dict:
    """全市場 {股票代碼: 產業別} 整表。FinMind 主 → openapi 補齊仍缺者。

    §1:兩源皆空 → 回 {}(caller 決定是否致命);絕不臆造產業別。
    """
    _tok = token if token is not None else _os.environ.get("FINMIND_TOKEN", "")
    out = _finmind_industry_map(_tok)
    # 不論 FinMind 成敗都補 openapi:填 FinMind 缺漏(新上市未收錄 / gate)
    fallback = _openapi_industry_map()
    for code, ind in fallback.items():
        out.setdefault(code, ind)
    print(f"[industry] 合併後 {len(out)} 檔(FinMind + openapi)")
    return out
