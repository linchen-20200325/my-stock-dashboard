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
   - `fetch_industry_map_bulk()` : 批 Z43(客戶 Q-z29＝A)起依**官方產業別代碼**選列 ——
     FinMind `TaiwanStockInfo` 整表原始列(不帶 data_id;每檔可多列)+ 官方 openapi
     TWSE `t187ap03_L`(上市)/ TPEx `mopsfin_t187ap03_O`(上櫃)的產業別代碼(T1 免 token),
     規則見 `select_industry_records`;完整選列紀錄由 `get_last_industry_raw()` 交 cron 落地。

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
    TPEX_CLOSE_COL_LOW, TPEX_CLOSE_COL_VOLUME, TPEX_CLOSE_N_FIELDS, TPEX_CLOSE_REQUIRE_TABLE_DATE,
    TPEX_CLOSE_REQUIRED_COLS,
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
                                              require_table_date=TPEX_CLOSE_REQUIRE_TABLE_DATE)
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
#: 批 Z43(客戶 Q-z29＝A):官方「公司基本資料」openapi(產業別欄＝兩位數**代碼**;代碼 ↔ 名稱 SSOT
#: 見 `shared.industry_codes`)。GitHub runner 探針第 7 輪 run 38191149822 實測:上市 1095 筆、上櫃 893 筆。
#: ⚠️ 上櫃舊 URL `openapi.twse.com.tw/v1/opendata/t187ap03_O` 回 HTML(JSONDecodeError)—— 舊備援從未生效。
TWSE_COMPANY_INFO_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_COMPANY_INFO_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
MARKET_TWSE = "上市"
MARKET_TPEX = "上櫃"
#: (市場, 端點, 代號欄, 產業別代碼欄) —— 欄名**完全相等**定位(探針原文),找不到 → 該市場不可用(⛔ 不猜欄)。
_OFFICIAL_INDUSTRY_SOURCES: tuple[tuple[str, str, str, str], ...] = (
    (MARKET_TWSE, TWSE_COMPANY_INFO_URL, "公司代號", "產業別"),
    (MARKET_TPEX, TPEX_COMPANY_INFO_URL, "SecuritiesCompanyCode", "SecuritiesIndustryCode"),
)
#: FinMind `TaiwanStockInfo` 的 `type` 欄 → 市場(用來判斷「官方查無」的代號是否屬於本次官方失敗的市場)。
_FINMIND_TYPE_MARKET = {"twse": MARKET_TWSE, "tpex": MARKET_TPEX}

#: 選列規則(寫進 industry_raw 每檔 `chosen.rule`;決定論、可追溯)。
RULE_OFFICIAL_MATCH = "official_match_finmind"   # FinMind 某列 ＝ 官方名(完全或去尾「業/類」)→ 用該列 FinMind 名
RULE_OFFICIAL_NAME = "official_name"             # 官方有產業別、FinMind 無任何列相符 → 用官方名
RULE_NO_OFFICIAL = "finmind_no_official"         # 官方查無 / 官方名空白 / 未知代碼 → FinMind 決定論
RULE_OFFICIAL_UNAVAILABLE = "official_unavailable"  # 該代號所屬市場官方端點本次失敗

#: 最近一次 `fetch_industry_map_bulk()` 的完整選列紀錄(原始列 + 官方 + chosen);cron 落地 industry_raw 用。
_LAST_INDUSTRY_RAW: dict = {}


def _finmind_industry_rows(token: str) -> list[dict] | None:
    """FinMind TaiwanStockInfo 整表(不帶 data_id)→ 原始列 list(**不去重、不丟 type/date**)。

    憑證只走 header(不進 query string,對齊 §資安慣例)。失敗/被 gate → None(與「0 列」區分)。
    批 Z43:改回傳原始列;舊版「每檔取第一個非空列」(列順序不固定、多列 date 常相同 → 約 6 成多列股取錯)
    已移除,選列改由 `select_industry_records` 依官方產業代碼決定。
    """
    hdr = dict(_HDR_JSON)
    if token:
        hdr["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(FINMIND_URL, params={"dataset": "TaiwanStockInfo"},
                         headers=hdr, timeout=30)
        if r.status_code != 200:
            print(f"[industry/FinMind] HTTP={r.status_code} body={r.text[:160]}")
            return None
        d = r.json()
        if d.get("status") != 200:
            print(f"[industry/FinMind] status={d.get('status')} "
                  f"msg={d.get('msg', '')}")
            return None
        rows = [x for x in (d.get("data") or []) if isinstance(x, dict)]
        print(f"[industry/FinMind] TaiwanStockInfo: {len(rows)} 列 / "
              f"{len({str(x.get('stock_id', '')).strip() for x in rows})} 檔")
        return rows
    except Exception as e:
        print(f"[industry/FinMind] ❌ {type(e).__name__}: {e}")
        return None


def _official_industry_codes() -> tuple[dict, dict]:
    """官方 openapi(上市 t187ap03_L + 上櫃 mopsfin_t187ap03_O)→ ({代號: {market, code, endpoint}}, 狀態)。

    狀態 = {市場: {"ok": bool, "n": int, "reason": str|None, "endpoint": url}}。
    某市場非 200 / 非 JSON / 非 list / 0 筆 / 欄名找不到 / 0 檔可解析 → ok=False(§1 不猜、不靜默退回)。
    同代號兩市場皆出現(轉市場過渡)→ 先到者(上市)為準並 log。
    走 `_fetch`(fetch_url:NAS→直連降級、失敗間隔退避、只快取 200)。
    """
    out: dict = {}
    status: dict = {}
    for market, url, k_code, k_ind in _OFFICIAL_INDUSTRY_SOURCES:
        st = {"ok": False, "n": 0, "reason": None, "endpoint": url}
        status[market] = st
        try:
            r = _fetch(url, timeout=20)
            if r is None or getattr(r, "status_code", 0) != 200:
                st["reason"] = f"HTTP={getattr(r, 'status_code', 'None')}"
                print(f"[industry/official] {market} {st['reason']} {url}")
                continue
            try:
                data = r.json()
            except ValueError as e:
                st["reason"] = f"非 JSON:{type(e).__name__}"
                print(f"[industry/official] {market} {st['reason']} body[:200]="
                      f"{scrubbed_body_head(r)[:200]!r}")
                continue
            if not isinstance(data, list) or not data:
                st["reason"] = f"非 list 或 0 筆({type(data).__name__})"
                print(f"[industry/official] {market} {st['reason']}")
                continue
            if not isinstance(data[0], dict) or k_code not in data[0] or k_ind not in data[0]:
                _keys = list(data[0].keys()) if isinstance(data[0], dict) else type(data[0]).__name__
                st["reason"] = f"欄名找不到 {k_code!r}/{k_ind!r}:{_keys}"
                print(f"[industry/official] {market} {st['reason']}")
                continue
            n = 0
            for item in data:
                if not isinstance(item, dict):
                    continue
                code = str(item.get(k_code, "")).strip()
                ind = str(item.get(k_ind, "")).strip()
                if not code or not ind:
                    continue
                n += 1
                if code in out:
                    print(f"[industry/official] ⚠️ {code} 同時出現於 {out[code]['market']} 與 {market}"
                          f" → 以 {out[code]['market']} 為準")
                    continue
                out[code] = {"market": market, "code": ind, "endpoint": url}
            st["n"] = n
            if n == 0:
                st["reason"] = "0 檔可解析(代號或產業別代碼皆空)"
                print(f"[industry/official] {market} {st['reason']}")
                continue
            st["ok"] = True
            print(f"[industry/official] {market}:{n} 檔")
        except Exception as e:
            st["reason"] = f"{type(e).__name__}: {e}"
            print(f"[industry/official] {market} ❌ {st['reason']}")
    return out, status


def _finmind_deterministic(labels_dates: list[tuple[str, str]]) -> str | None:
    """[(label, date)] → date 最新者;同 date 取名稱字典序最小(決定論、與 API 列順序無關)。空 → None。"""
    xs = [(lab, str(dt or "")) for lab, dt in labels_dates if lab]
    if not xs:
        return None
    _latest = max(dt for _, dt in xs)
    return min(lab for lab, dt in xs if dt == _latest)


def select_industry_records(finmind_rows, official: dict, *,
                            unavailable_markets=()) -> dict:
    """純函式:FinMind 原始列 + 官方 {代號: {market, code, endpoint}} → {代號: 選列紀錄}。

    每檔規則(批 Z43,決定論):
      1. 官方代碼 → 官方名稱(`shared.industry_codes`)。
      2. FinMind 某列與官方名「完全相同」或「去尾『業/類』後相同」→ 用該列 **FinMind 名**
         (`official_match_finmind`;多列皆符取完全相同者,否則 date 最新、名稱字典序)。
      3. 官方有產業名但 FinMind 無任何列相符 → 用**官方名**(`official_name`)。
      4. 官方查無 / 官方名空白('91' TDR)/ 未知代碼 → FinMind 決定論(`finmind_no_official`)。
      5. 官方查無且該檔 FinMind `type` 屬於本次官方失敗的市場 → FinMind 決定論、rule=`official_unavailable`
         (cron 再以上一份 industry_raw 的 chosen 覆蓋,見 `apply_prev_chosen`)。
    紀錄 = {"finmind": [原始 {industry_category, type, date}, …](API 原順序),
            "official": {market, code, name, endpoint} | None,
            "chosen": {"label": str|None, "rule": str}}。⛔ 不臆造:無任何來源 → label None。
    """
    from shared.industry_codes import loose_industry_name, official_industry_name

    _unavail = set(unavailable_markets or ())
    by_id: dict = {}
    for row in finmind_rows or []:
        if not isinstance(row, dict):
            continue
        sid = str(row.get("stock_id", "")).strip()
        if not sid:
            continue
        by_id.setdefault(sid, []).append({
            "industry_category": str(row.get("industry_category") or "").strip(),
            "type": (str(row.get("type")).strip() if row.get("type") is not None else None),
            "date": (str(row.get("date")).strip() if row.get("date") is not None else None),
        })
    out: dict = {}
    for code in sorted(set(by_id) | set(official or {})):
        fm = by_id.get(code, [])
        _ld = [(r["industry_category"], r["date"]) for r in fm if r["industry_category"]]
        off = (official or {}).get(code)
        off_rec = None
        label, rule = None, RULE_NO_OFFICIAL
        if off is not None:
            name = official_industry_name(off.get("code"))
            off_rec = {"market": off.get("market"), "code": off.get("code"), "name": name,
                       "endpoint": off.get("endpoint")}
            if name:
                exact = [x for x in _ld if x[0] == name]
                loose = [x for x in _ld if loose_industry_name(x[0]) == loose_industry_name(name)]
                if exact or loose:
                    label, rule = _finmind_deterministic(exact or loose), RULE_OFFICIAL_MATCH
                else:
                    label, rule = name, RULE_OFFICIAL_NAME
            else:
                label = _finmind_deterministic(_ld)
        else:
            _mk = {_FINMIND_TYPE_MARKET.get(r["type"]) for r in fm} - {None}
            label = _finmind_deterministic(_ld)
            if _mk & _unavail:
                rule = RULE_OFFICIAL_UNAVAILABLE
        out[code] = {"finmind": fm, "official": off_rec,
                     "chosen": {"label": label, "rule": rule}}
    return out


def apply_prev_chosen(raw: dict, prev_raw) -> dict:
    """`official_unavailable` 的代號 → 沿用上一份 industry_raw 的 chosen.label(有才沿用)。回新 dict。

    沿用時 chosen 追加 `from_prev=True` 與 `prev_rule`;上一份沒有該代號 → 維持 FinMind 決定論、
    `from_prev=False`。⛔ 不改其他代號。
    """
    import copy
    new = copy.deepcopy(raw or {})
    _prev = ((prev_raw or {}).get("codes") or {}) if isinstance(prev_raw, dict) else {}
    for code, rec in (new.get("codes") or {}).items():
        ch = rec.get("chosen") or {}
        if ch.get("rule") != RULE_OFFICIAL_UNAVAILABLE:
            continue
        p = (_prev.get(code) or {}).get("chosen") or {}
        if p.get("label"):
            ch["label"] = p["label"]
            ch["from_prev"] = True
            ch["prev_rule"] = p.get("rule")
        else:
            ch["from_prev"] = False
    return new


def industry_map_from_raw(raw) -> dict:
    """industry_raw → 扁平 {代號: chosen.label}(label 空者不列,⛔ 不臆造)。"""
    out: dict = {}
    for code, rec in ((raw or {}).get("codes") or {}).items():
        lab = ((rec or {}).get("chosen") or {}).get("label")
        if code and lab:
            out[str(code)] = str(lab)
    return out


def get_last_industry_raw() -> dict | None:
    """最近一次 `fetch_industry_map_bulk()` 的選列紀錄(deep copy);從未呼叫 → None。"""
    import copy
    return copy.deepcopy(_LAST_INDUSTRY_RAW) if _LAST_INDUSTRY_RAW else None


def fetch_industry_map_bulk(token: str | None = None) -> dict:
    """全市場 {股票代碼: 產業別} 整表(批 Z43:依官方產業代碼選列)。

    FinMind TaiwanStockInfo 原始列 + 官方 openapi 產業代碼 → `select_industry_records`。
    完整紀錄(原始列 / 官方 / chosen / 來源 / 狀態)存 `_LAST_INDUSTRY_RAW`(`get_last_industry_raw()`),
    由 cron 落地 `data_cache/sector_flow/industry_raw.json`(原始資料不覆寫、可追溯)。
    §1:兩源皆空 → 回 {}(caller 決定是否致命);絕不臆造產業別。
    """
    import datetime as _dtm
    _LAST_INDUSTRY_RAW.clear()
    _tok = token if token is not None else _os.environ.get("FINMIND_TOKEN", "")
    fm_rows = _finmind_industry_rows(_tok)
    official, status = _official_industry_codes()
    unavailable = sorted(m for m, s in status.items() if not s.get("ok"))
    codes = select_industry_records(fm_rows or [], official, unavailable_markets=unavailable)
    warnings: list[str] = []
    for m in unavailable:
        warnings.append(f"官方產業別端點不可用:{m}({status[m].get('reason')})→ 該市場官方查無的代號"
                        f"記 {RULE_OFFICIAL_UNAVAILABLE}(沿用上一份 chosen,否則 FinMind 決定論)")
    if fm_rows is None:
        warnings.append("FinMind TaiwanStockInfo 失敗 → 只有官方代碼可用(官方查無者無產業別)")
    from shared.industry_codes import OFFICIAL_INDUSTRY_CODE_NAMES, INDUSTRY_SCHEME_VERSION
    _unknown = sorted({v["code"] for v in official.values()
                       if v.get("code") not in OFFICIAL_INDUSTRY_CODE_NAMES})
    if _unknown:
        warnings.append(f"官方產業別代碼不在代碼表:{_unknown}(⛔ 不猜名稱 → FinMind 決定論)")
    for w in warnings:
        print(f"[industry] ⚠️ {w}")
    _LAST_INDUSTRY_RAW.update({
        "scheme": INDUSTRY_SCHEME_VERSION,
        "fetched_at": _dtm.datetime.now(_dtm.timezone.utc).isoformat(),
        "sources": {"finmind": f"{FINMIND_URL}?dataset=TaiwanStockInfo",
                    MARKET_TWSE: TWSE_COMPANY_INFO_URL, MARKET_TPEX: TPEX_COMPANY_INFO_URL},
        "finmind_status": {"ok": fm_rows is not None, "n_rows": len(fm_rows or [])},
        "official_status": status,
        "unavailable_markets": unavailable,
        "warnings": warnings,
        "codes": codes,
    })
    out = industry_map_from_raw(_LAST_INDUSTRY_RAW)
    _rules: dict = {}
    for rec in codes.values():
        _r = rec["chosen"]["rule"]
        _rules[_r] = _rules.get(_r, 0) + 1
    print(f"[industry] 選列後 {len(out)} 檔(規則分布 {_rules})")
    return out
