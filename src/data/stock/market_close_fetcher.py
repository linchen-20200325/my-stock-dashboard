"""src/data/stock/market_close_fetcher.py — 全市場「每日收盤價」+「產業別」raw fetcher(L1)。

板塊資金泡泡圖 Stage 1 的兩個新增資料需求(三大法人已由
`data_loader_inst_fetchers._get_t86_day / _get_tpex_day` 供應,直接重用):

1. 全市場**每日收盤價**(元/股)—— 供「張 → 金額」換算:
   - `fetch_twse_close_day(ds)` : TWSE MI_INDEX(帶 date,官方 T1、免 token),回 {code: close}
   - `fetch_tpex_close_day(ds)` : TPEX 上櫃每日收盤(官方 T1、免 token;批 Z41 改接官方新網站
     `afterTrading/otc` JSON,帶西元 date,欄位以清洗後完全相等定位 + 逐列/整表守衛)
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

import os as _os

import requests

from shared.http_diag import scrubbed_body_head
from shared.tpex_schema import (  # 批 Z41 TPEx 官方新網站 JSON 結構契約 SSOT(L0)
    TPEX_CLOSE_COL_AMOUNT, TPEX_CLOSE_COL_CLOSE, TPEX_CLOSE_COL_CODE, TPEX_CLOSE_COL_HIGH,
    TPEX_CLOSE_COL_LOW, TPEX_CLOSE_COL_VOLUME, TPEX_CLOSE_N_FIELDS, TPEX_CLOSE_REQUIRED_COLS,
    TPEX_CLOSE_TITLE_PREFIX, TPEX_CLOSE_UNIT_GUARD_MIN_PASS_RATIO, TPEX_CLOSE_VWAP_REL_TOL,
    check_tpex_envelope, clean_tpex_field_name, parse_tpex_price, tpex_query_date,
    tpex_redirected_to_error, tpex_roc_date)

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


#: 批 Z39(客戶 Q-z28 診斷):`fetch_tpex_close_day(ds)` 最近一次呼叫的結果狀態。
#:   ok / empty(空表)/ parse_zero(有列但解析 0 筆)/ http_none(None)/
#:   http_error(非 200)/ json_error(非 JSON)/ exception。
#: 批 Z41(客戶 Q-z27＝A):改接官方新網站 `afterTrading/otc`,新增
#:   redirect_error(轉往 /errors)/ schema_error(stat／日期回聲／title／fields 非 17 欄或必要欄名找不到／列長)/
#:   unit_error(整表單位守衛:有成交列「成交金額÷成交股數 ∈ [最低,最高]」成立率不足)。只有 ok 回資料。
_TPEX_CLOSE_DIAG: dict[str, str] = {}
#: 批 Z41:櫃買中心官方新網站「上櫃股票每日收盤行情(不含定價)」JSON(探針 run 38105352894 等驗證)。
TPEX_CLOSE_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc"


def get_tpex_close_status(ds: str) -> str | None:
    """`fetch_tpex_close_day(ds)` 最近一次呼叫的狀態;從未呼叫 → None。"""
    return _TPEX_CLOSE_DIAG.get(ds)


def _tpex_close_fail(ds: str, status: str, r, reason: str) -> dict:
    """批 Z41:非 ok 統一出口 —— 記狀態 + log(含洗過的 body 前 500 字)。"""
    _TPEX_CLOSE_DIAG[ds] = status
    _body = f" body[:500]={scrubbed_body_head(r)!r}" if r is not None else ""
    print(f"[TPEX close] {ds} 非 ok({status}):{reason}{_body}")
    return {}


def _parse_tpex_close_rows(ds: str, fields: list, data: list) -> tuple[str, str, dict]:
    """批 Z41:收盤表欄位定位 + 逐列守衛 + 整表單位守衛 → (status, reason, {代號: 收盤})。純解析。

    - fields 以 `clean_tpex_field_name` 清洗後**完全相等**比對必要欄(各恰一次),欄數須 17;
      列長須 17 —— 任一不符 → schema_error。
    - 收盤 `'----'`／不可解析／≤0 → 該股無收盤(缺值,⛔ 不退去相鄰欄);最高或最低不可解析、或
      `最低 ≤ 收盤 ≤ 最高` 不成立 → 該股缺值並計數。
    - 單位守衛:有成交(成交股數>0 且 成交金額>0 且 高低可解析)列中,
      `成交金額/成交股數 ∈ [最低×(1−tol), 最高×(1+tol)]` 成立率 < 門檻(或 0 列可驗)→ unit_error。
    """
    names = [clean_tpex_field_name(f) for f in fields]
    if len(names) != TPEX_CLOSE_N_FIELDS:
        return "schema_error", f"fields {len(names)} 欄 ≠ {TPEX_CLOSE_N_FIELDS}:{names}", {}
    idx = {}
    for col in TPEX_CLOSE_REQUIRED_COLS:
        hits = [i for i, n in enumerate(names) if n == col]
        if len(hits) != 1:
            return "schema_error", f"必要欄 {col!r} 命中 {len(hits)} 次(清洗後 fields={names})", {}
        idx[col] = hits[0]
    bad_len = [i for i, row in enumerate(data)
               if not isinstance(row, (list, tuple)) or len(row) != TPEX_CLOSE_N_FIELDS]
    if bad_len:
        return ("schema_error",
                f"{len(bad_len)} 列長度≠{TPEX_CLOSE_N_FIELDS}(首例第 {bad_len[0]} 列)", {})
    out: dict = {}
    n_no_close = n_hl_bad = n_unit_ok = n_unit_chk = 0
    tol = TPEX_CLOSE_VWAP_REL_TOL
    for row in data:
        code = str(row[idx[TPEX_CLOSE_COL_CODE]]).strip()
        close = parse_tpex_price(row[idx[TPEX_CLOSE_COL_CLOSE]])
        hi = parse_tpex_price(row[idx[TPEX_CLOSE_COL_HIGH]])
        lo = parse_tpex_price(row[idx[TPEX_CLOSE_COL_LOW]])
        vol = parse_tpex_price(row[idx[TPEX_CLOSE_COL_VOLUME]])
        amt = parse_tpex_price(row[idx[TPEX_CLOSE_COL_AMOUNT]])
        if hi is not None and lo is not None and vol and amt and vol > 0 and amt > 0:
            n_unit_chk += 1
            if lo * (1 - tol) <= amt / vol <= hi * (1 + tol):
                n_unit_ok += 1
        if not code or close is None or close <= 0:
            n_no_close += 1
            continue
        if hi is None or lo is None or not (lo <= close <= hi):
            n_hl_bad += 1
            continue
        out[code] = close
    if n_hl_bad:
        print(f"[TPEX close] ⚠️ {ds} 最高/最低不可解析或 最低≤收盤≤最高 不成立 {n_hl_bad} 列 → 該股缺值")
    if n_unit_chk == 0:
        return "unit_error", "無任何有成交列可驗單位(成交金額/成交股數)", {}
    ratio = n_unit_ok / n_unit_chk
    if ratio < TPEX_CLOSE_UNIT_GUARD_MIN_PASS_RATIO:
        return ("unit_error", f"成交金額/成交股數 ∈ [最低,最高] 成立率 {ratio:.1%} "
                f"({n_unit_ok}/{n_unit_chk}) < {TPEX_CLOSE_UNIT_GUARD_MIN_PASS_RATIO:.0%}", {})
    if not out:
        return "parse_zero", f"有 {len(data)} 列但解析 0 筆有效收盤", {}
    print(f"[TPEX close] {ds}: 無收盤 {n_no_close} 列(缺值)、單位守衛 {n_unit_ok}/{n_unit_chk}")
    return "ok", "", out


def fetch_tpex_close_day(ds: str) -> dict:
    """TPEX 上櫃全市場單日收盤價。ds=YYYYMMDD。回 {股票代碼: 收盤價(元/股)}。

    批 Z41(客戶 Q-z27＝A 受控遷移):來源改為櫃買中心官方新網站「上櫃股票每日收盤行情(不含定價)」
    JSON(`afterTrading/otc?type=EW`,西元 `YYYY/MM/DD`)。舊 RWD php 交易日回 `totalCount=0` 空表
    (探針實測)已不可用。守衛(任一不過 → 非 ok、回 {}):轉址 /errors、非 JSON、stat、日期回聲
    (頂層 YYYYMMDD + tables[0] 民國)、title 以「上櫃股票每日收盤行情」開頭、fields 清洗後完全相等定位
    (17 欄)、列長、逐列 最低≤收盤≤最高、整表單位守衛。收盤 `----`/不可解析 → 該股缺值(⛔ 不退相鄰欄)。
    外幣交易 ETF(代號第六碼 K/C)收盤**照原值保留**於 L1;板塊金額換算的幣別排除在 L2
    (`src/compute/sector_flow.compute_sector_daily_net`)。
    批 Z39:各分支記 `_TPEX_CLOSE_DIAG[ds]`;非 ok 分支印洗過的 body 前 500 字。
    """
    r = None
    try:
        r = _fetch(
            TPEX_CLOSE_URL,
            params={"date": tpex_query_date(ds), "type": "EW", "id": "",
                    "response": "json"},
            timeout=20,
            headers={**_HDR_JSON, "Referer": "https://www.tpex.org.tw/"})
        if r is None:
            return _tpex_close_fail(ds, "http_none", None, "fetch 回 None")
        if getattr(r, "status_code", 0) != 200:
            return _tpex_close_fail(ds, "http_error", r, f"HTTP={getattr(r, 'status_code', None)}")
        if tpex_redirected_to_error(r):
            return _tpex_close_fail(ds, "redirect_error", r,
                                    f"被轉往官方錯誤頁 url={getattr(r, 'url', None)!r}")
        try:
            j = r.json()
        except ValueError as e:
            return _tpex_close_fail(ds, "json_error", r, f"{type(e).__name__}: {e}")
        # tables[0].date 探針未記錄是否存在 → 有就必須＝民國請求日、沒有不臆測(頂層回聲仍強制)
        status, why, t0 = check_tpex_envelope(j, ds, title_prefix=TPEX_CLOSE_TITLE_PREFIX,
                                              require_table_date=False)
        if status != "ok":
            return _tpex_close_fail(ds, status, r, why)
        status, why, out = _parse_tpex_close_rows(ds, list(t0.get("fields") or []),
                                                  t0["data"])
        if status != "ok":
            return _tpex_close_fail(ds, status, r, why)
        _TPEX_CLOSE_DIAG[ds] = "ok"
        print(f"[TPEX close] {ds} ({tpex_roc_date(ds)}): {len(out)} 檔")
        return out
    except Exception as e:
        return _tpex_close_fail(ds, "exception", r, f"{type(e).__name__}: {e}")


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
