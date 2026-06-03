"""update_macro_history.py — GitHub Actions 排程：抓總經歷史資料增量到 data_cache/。

資料流（與 update_etf_managers.py 同模式，但抓多個 dataset）
=========================================================
data_cache/twii_ohlcv.parquet              ← ^TWII 日 K（yfinance via NAS proxy）
data_cache/finmind_inst.parquet            ← 三大法人總買賣超（FinMind）
data_cache/finmind_margin.parquet          ← 融資餘額（FinMind）
data_cache/finmind_m1m2.parquet            ← M1B / M2 月差（FinMind）
data_cache/finmind_ndc_signal.parquet      ← 景氣對策信號分數 9-45（data.gov.tw NDC dataset；免 token；v18.154 取代 NDC SPA OpenAPI）
data_cache/finmind_leading_index.parquet   ← 領先指標綜合指數（data.gov.tw NDC dataset；檔名保留 finmind_ 前綴以維持向後相容）
data_cache/metadata.json                   ← 各表 last_updated + row_count

每日跑一次（TW 17:00 收盤後）
- 對每個 Parquet：讀取 last_date → 抓 [last_date+1, today] → append + dedupe → 寫回
- 走 proxy_helper.fetch_url（NAS Squid → 直連 → NAS 中繼站 fallback）解海外 IP 封鎖
- 任一資料源失敗：log 警告但不中止；metadata 記 last_error 供後續排查

刻意維持「無 streamlit 相依」（與 update_etf_managers.py 同款），
在 Actions runner 上 pip install -r requirements.txt 即可跑。

CLI
===
    python update_macro_history.py             # 增量更新
    python update_macro_history.py --bootstrap # 砍掉重抓全部 5 年（初次部署用）
    python update_macro_history.py --years 3   # 自訂歷史長度（預設 5）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests

CACHE_DIR = Path("data_cache")
META_PATH = CACHE_DIR / "metadata.json"

# Parquet 表名 → 抓取函式名（runtime dispatch）
DATASETS = ["twii_ohlcv", "finmind_inst", "finmind_margin", "finmind_m1m2",
            "finmind_ndc_signal", "finmind_leading_index"]

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

# ════════════════════════════════════════════════════════════════
# I/O Helpers
# ════════════════════════════════════════════════════════════════
def _load_existing(name: str) -> pd.DataFrame | None:
    path = CACHE_DIR / f"{name}.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as e:
        print(f"[{name}] 讀現有 Parquet 失敗：{type(e).__name__}: {e}")
        return None


def _write_parquet(name: str, df: pd.DataFrame) -> None:
    path = CACHE_DIR / f"{name}.parquet"
    df.to_parquet(path, compression="snappy", index=False)
    print(f"[{name}] ✅ 寫入 {len(df)} rows → {path}")


def _last_date(df: pd.DataFrame | None, col: str = "date") -> _dt.date | None:
    if df is None or df.empty or col not in df.columns:
        return None
    try:
        return pd.to_datetime(df[col]).max().date()
    except Exception:
        return None


def _merge_dedupe(old: pd.DataFrame | None, new: pd.DataFrame,
                  key: str = "date") -> pd.DataFrame:
    """合併 old + new，按 key 去重保留最新；按 key 排序。"""
    if old is None or old.empty:
        out = new
    else:
        out = pd.concat([old, new], ignore_index=True)
    out = out.drop_duplicates(subset=[key], keep="last").sort_values(key).reset_index(drop=True)
    return out


def _fetch_url_via_proxy(url: str, params: dict | None = None,
                        timeout: int = 25) -> requests.Response | None:
    """走 proxy_helper.fetch_url；缺 helper 時 fallback 直連。"""
    try:
        from proxy_helper import fetch_url
        return fetch_url(url, params=params, timeout=timeout, attempts=2)
    except ImportError:
        try:
            return requests.get(url, params=params, timeout=timeout,
                                headers={"User-Agent": "Mozilla/5.0"})
        except Exception as e:
            print(f"[fetch fallback] {url[:60]} ❌ {type(e).__name__}: {e}")
            return None


def _finmind_get(dataset: str, data_id: str, start: str, end: str,
                 token: str) -> pd.DataFrame:
    """無 streamlit 相依的 FinMind 抓取器（直連，不走 proxy chain）。

    為什麼直連？
    - FinMind API 全球可達，無 IP 封鎖
    - proxy_helper.fetch_url 對非 200/403/407 狀態靜默失敗（無 status 紀錄），
      在 Actions runner 上 PROXY_URL 未設時，整條 chain 失敗看不出真因
    - 直連 + 把 HTTP status / response body 印出 → 任何錯誤都看得到
    """
    params = {"dataset": dataset, "start_date": start, "end_date": end}
    if data_id:
        params["data_id"] = data_id
    if token:
        params["token"] = token
    try:
        r = requests.get(
            FINMIND_URL, params=params, timeout=30,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        if r.status_code != 200:
            print(f"[FinMind/{dataset}] HTTP={r.status_code} body={r.text[:200]}")
            return pd.DataFrame()
        d = r.json()
        if d.get("status") != 200:
            print(f"[FinMind/{dataset}] status={d.get('status')} msg={d.get('msg', '')}")
            return pd.DataFrame()
        df = pd.DataFrame(d.get("data", []))
        print(f"[FinMind/{dataset}] ✅ {len(df)} rows ({start}~{end})")
        return df
    except Exception as e:
        print(f"[FinMind/{dataset}] ❌ {type(e).__name__}: {e}")
        return pd.DataFrame()


# ════════════════════════════════════════════════════════════════
# 各 dataset 抓取邏輯
# ════════════════════════════════════════════════════════════════
def fetch_twii_ohlcv(start: _dt.date, end: _dt.date) -> pd.DataFrame:
    """^TWII 日 K（Yahoo Chart API via NAS proxy）。"""
    period1 = int(_dt.datetime.combine(start, _dt.time(0, 0)).timestamp())
    period2 = int(_dt.datetime.combine(end + _dt.timedelta(days=1), _dt.time(0, 0)).timestamp())
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ETWII"
    params = {"period1": period1, "period2": period2, "interval": "1d", "events": "history"}
    r = _fetch_url_via_proxy(url, params=params, timeout=20)
    if r is None or r.status_code != 200:
        print(f"[twii_ohlcv] HTTP={getattr(r, 'status_code', 'None')}")
        return pd.DataFrame()
    try:
        j = r.json()
        result = j["chart"]["result"][0]
        ts = result["timestamp"]
        ind = result["indicators"]["quote"][0]
        df = pd.DataFrame({
            "date": [_dt.datetime.fromtimestamp(t).date() for t in ts],
            "open": ind.get("open", [None] * len(ts)),
            "high": ind.get("high", [None] * len(ts)),
            "low": ind.get("low", [None] * len(ts)),
            "close": ind.get("close", [None] * len(ts)),
            "volume": ind.get("volume", [None] * len(ts)),
        })
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        print(f"[twii_ohlcv] ✅ {len(df)} rows ({start}~{end})")
        return df
    except Exception as e:
        print(f"[twii_ohlcv] parse error: {type(e).__name__}: {e}")
        return pd.DataFrame()


def fetch_finmind_inst(start: _dt.date, end: _dt.date, token: str) -> pd.DataFrame:
    """三大法人總買賣超（FinMind TaiwanStockTotalInstitutionalInvestors）。

    輸出欄位：date, foreign_buy（億，外資淨買賣超）
    FinMind 實際欄位：['buy', 'date', 'name', 'sell']
    `name` 欄含投資人類型（外資、投信、自營商）；篩 '外資' 後算淨買賣超。
    """
    raw = _finmind_get("TaiwanStockTotalInstitutionalInvestors",
                       "", start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), token)
    if raw.empty:
        return raw
    # FinMind 實際 name 值為英文：Foreign_Investor / Foreign_Dealer_Self /
    # Investment_Trust / Dealer_self / Dealer_Hedging / total
    # 外資總額 = Foreign_Investor + Foreign_Dealer_Self（兩者皆 'Foreign' prefix）
    if "name" not in raw.columns:
        print(f"[finmind_inst] 缺欄位 name，欄位={list(raw.columns)}")
        return pd.DataFrame()
    fi = raw[raw["name"].astype(str).str.contains("Foreign", na=False)]
    if fi.empty:
        print(f"[finmind_inst] name 欄位無 'Foreign' 列，unique={list(raw['name'].unique())[:10]}")
        return pd.DataFrame()
    fi = fi.copy()
    fi["foreign_buy"] = (pd.to_numeric(fi.get("buy"), errors="coerce").fillna(0)
                        - pd.to_numeric(fi.get("sell"), errors="coerce").fillna(0)) / 1e8
    out = fi.groupby("date", as_index=False)["foreign_buy"].sum()
    out["date"] = pd.to_datetime(out["date"]).dt.date
    return out


def fetch_finmind_margin(start: _dt.date, end: _dt.date, token: str) -> pd.DataFrame:
    """融資餘額（FinMind TaiwanStockTotalMarginPurchaseShortSale）→ 取 MarginPurchaseTodayBalance。"""
    raw = _finmind_get("TaiwanStockTotalMarginPurchaseShortSale",
                       "", start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), token)
    if raw.empty:
        return raw
    bal_col = next((c for c in raw.columns
                    if "MarginPurchase" in c and ("Balance" in c or "Today" in c)), None)
    if bal_col is None:
        bal_col = next((c for c in raw.columns if "Balance" in c), None)
    if bal_col is None:
        print(f"[finmind_margin] 找不到融資餘額欄位；欄位={list(raw.columns)}")
        return pd.DataFrame()
    out = raw[["date", bal_col]].copy()
    out.columns = ["date", "margin_balance"]
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out["margin_balance"] = pd.to_numeric(out["margin_balance"], errors="coerce")
    return out.dropna(subset=["margin_balance"]).reset_index(drop=True)


def fetch_finmind_m1m2(start: _dt.date, end: _dt.date, token: str) -> pd.DataFrame:
    """M1B / M2 月頻（改抓 CBC 中央銀行 ms1.json，FinMind 無對應 dataset）。

    走 proxy_helper.fetch_url（PROXY_URL）→ CBC 擋海外 IP 必須過台灣中繼。
    輸出：date / m1b / m2 / m1b_m2_gap（M1B YoY − M2 YoY）。
    """
    # token 參數忽略不用（CBC 不需要），但維持 signature 統一
    _ = token
    try:
        from proxy_helper import fetch_url as _fu_cbc
    except ImportError:
        print("[finmind_m1m2] 缺 proxy_helper，無法抓 CBC")
        return pd.DataFrame()
    # ── Tier 1: ms1.json 三路徑 ──
    ms1_urls = [
        "https://www.cbc.gov.tw/public/Attachment/ms1.json",
        "https://www.cbc.gov.tw/public/data/ms1.json",
        "https://www.cbc.gov.tw/tw/public/data/ms1.json",
    ]
    data = None
    for url in ms1_urls:
        try:
            r = _fu_cbc(url, timeout=15, attempts=2)
            if r is None:
                print(f"[finmind_m1m2/ms1] {url[-40:]} → None")
                continue
            if r.status_code != 200:
                print(f"[finmind_m1m2/ms1] {url[-40:]} HTTP={r.status_code}")
                continue
            try:
                _j = r.json()
                if isinstance(_j, list) and len(_j) > 0:
                    data = _j
                    print(f"[finmind_m1m2/ms1] ✅ {url[-40:]} 取到 {len(_j)} 行")
                    break
                print(f"[finmind_m1m2/ms1] {url[-40:]} json 非 list 或為空")
            except Exception:
                print(f"[finmind_m1m2/ms1] {url[-40:]} JSON 解析失敗 body={r.text[:200]}")
        except Exception as e:
            print(f"[finmind_m1m2/ms1] {url[-40:]} ❌ {type(e).__name__}: {e}")

    # ── Tier 2: SDMX EF15M01 ──
    if not isinstance(data, list) or len(data) < 13:
        try:
            r = _fu_cbc("https://cpx.cbc.gov.tw/API/DataAPI/Get",
                        params={"FileName": "EF15M01"}, timeout=20, attempts=2)
            if r is not None and r.status_code == 200:
                try:
                    sdmx = r.json()
                    rows = sdmx.get("DataSet", []) if isinstance(sdmx, dict) else []
                    if rows:
                        print(f"[finmind_m1m2/EF15M01] ✅ 取到 {len(rows)} 行")
                        data = rows
                except Exception:
                    print(f"[finmind_m1m2/EF15M01] JSON 解析失敗 body={r.text[:200]}")
        except Exception as e:
            print(f"[finmind_m1m2/EF15M01] ❌ {type(e).__name__}: {e}")

    if not isinstance(data, list) or len(data) < 13:
        print("[finmind_m1m2] CBC 全來源失敗")
        return pd.DataFrame()
    print(f"[finmind_m1m2] 抓到欄位：{list(pd.DataFrame(data).columns)[:15]}")

    df = pd.DataFrame(data)
    c1 = next((c for c in df.columns
               if "M1B" in str(c).upper() or "貨幣供給額M1B" in str(c)), None)
    c2 = next((c for c in df.columns
               if str(c).strip().upper() == "M2" or "貨幣供給額M2" in str(c)), None)
    date_col = next((c for c in df.columns
                     if str(c).strip() in ("年月", "date", "yearMonth", "Date",
                                            "PERIOD", "TIME_PERIOD")), None)
    if not (c1 and c2 and date_col):
        print(f"[finmind_m1m2] CBC 欄位對應失敗：{list(df.columns)[:10]}")
        return pd.DataFrame()

    out = df[[date_col, c1, c2]].copy()
    out.columns = ["date_raw", "m1b", "m2"]
    # 日期 normalize：'2026/04' / '2026-04' / '202604' → 'YYYY-MM-01'
    import re as _re
    def _norm(s):
        m = _re.search(r"(20\d{2})[-/年]?(\d{1,2})", str(s))
        if not m:
            return None
        return _dt.date(int(m.group(1)), int(m.group(2)), 1)
    out["date"] = out["date_raw"].apply(_norm)
    out = out.dropna(subset=["date"]).drop(columns=["date_raw"])
    # SDMX 數字可能含 thousand separator，先去掉再轉
    out["m1b"] = pd.to_numeric(
        out["m1b"].astype(str).str.replace(",", ""), errors="coerce")
    out["m2"] = pd.to_numeric(
        out["m2"].astype(str).str.replace(",", ""), errors="coerce")
    out = out.dropna().sort_values("date").reset_index(drop=True)
    # M1B YoY − M2 YoY（黃金交叉指標）
    out["m1b_m2_gap"] = (out["m1b"] / out["m1b"].shift(12) - 1) * 100 - \
                        (out["m2"] / out["m2"].shift(12) - 1) * 100
    out = out[(out["date"] >= start) & (out["date"] <= end)]
    print(f"[finmind_m1m2] ✅ CBC ms1.json {len(out)} rows")
    return out[["date", "m1b", "m2", "m1b_m2_gap"]]


# ──────────────────────────────────────────────────────────────────
# v18.155 NDC OpenAPI 重啟（強制走 NAS 中繼站，帶 AJAX header）+ dgtw 兜底
# ──────────────────────────────────────────────────────────────────
# v18.152/153 透過 Squid Proxy 抓 NDC OpenAPI 全回 SPA HTML，但 Squid 沒帶
# X-Requested-With: XMLHttpRequest header。nas_server.py `_HDR` 配 AJAX
# 標記 → AngularJS SPA 偵測到 XHR 應該會回 JSON（典型 SPA 雙模式行為）。
# 本次三路徑彙整：
#   Path 1: NDC OpenAPI via NAS 中繼站（nas_relay_fetch 帶 AJAX header）— 重新試
#   Path 2: data.gov.tw search API（v18.154 已建）— 兜底
#   Path 3: data.gov.tw direct ID probe（v18.154 已建）— 最後 ditch

# NDC OpenAPI candidate（重啟）
_NDC_SIGNAL_URL_CANDIDATES: tuple = (
    "https://index.ndc.gov.tw/app/data/indicator/monitoring",
    "https://index.ndc.gov.tw/app/data/indicator/composite",
    "https://index.ndc.gov.tw/app/data/indicator/signal",
    "https://index.ndc.gov.tw/app/data/indicator/cyclical",
)
_NDC_LEADING_URL_CANDIDATES: tuple = (
    "https://index.ndc.gov.tw/app/data/indicator/leading",
    "https://index.ndc.gov.tw/app/data/indicator/Leading",
    "https://index.ndc.gov.tw/app/data/indicator/LeadingIndex",
)
_NDC_VALUE_KEYS: tuple = ("value", "score", "data", "index", "composite",
                            "monitoring", "leading", "signal")
_NDC_DATE_KEYS: tuple = ("date", "yearMonth", "period", "month",
                           "year_month", "yearmonth", "yearMonthCode")


def _fetch_via_nas_relay(url: str, label: str) -> pd.DataFrame:
    """直接走 NAS 中繼站（不走 Squid Proxy）抓 NDC OpenAPI；中繼站 _HDR 帶
    X-Requested-With: XMLHttpRequest → 應觸發 SPA 回 JSON 而非 HTML。

    回 [date, value] DataFrame 或空（失敗 graceful）。"""
    try:
        from proxy_helper import nas_relay_fetch
    except ImportError:
        print(f"[ndc-relay/{label}] ❌ proxy_helper.nas_relay_fetch 不可用")
        return pd.DataFrame()
    import re as _re_ndc

    slug = url.rsplit("/", 1)[-1]
    r = nas_relay_fetch(url, timeout=20)
    if r is None:
        print(f"[ndc-relay/{label}/{slug}] 無回應（NAS 中繼未設定或失敗）")
        return pd.DataFrame()
    if r.status_code != 200:
        body = r.text[:200].replace("\n", " ")
        print(f"[ndc-relay/{label}/{slug}] HTTP={r.status_code} body={body}")
        return pd.DataFrame()
    try:
        j = r.json()
    except Exception as e:
        ct = r.headers.get("Content-Type", "?")[:50] if hasattr(r, "headers") else "?"
        body_preview = (r.text[:300] if r.text else "<empty>").replace("\n", " ")
        print(f"[ndc-relay/{label}/{slug}] JSON 失敗 CT={ct} body={body_preview}")
        return pd.DataFrame()

    items = j if isinstance(j, list) else (
        j.get("data") or j.get("items")
        or j.get("result", {}).get("records") or [])
    if not items or not isinstance(items, list):
        top = list(j.keys())[:6] if isinstance(j, dict) else type(j).__name__
        print(f"[ndc-relay/{label}/{slug}] items 為空 (top={top})")
        return pd.DataFrame()

    rows = []
    for it in items:
        if not isinstance(it, dict):
            continue
        v_raw = next((it[k] for k in _NDC_VALUE_KEYS
                      if k in it and it[k] is not None), None)
        d_raw = next((it[k] for k in _NDC_DATE_KEYS
                      if k in it and it[k]), None)
        if v_raw is None or not d_raw:
            continue
        try:
            v = float(v_raw)
        except (TypeError, ValueError):
            continue
        m = _re_ndc.search(r"(20\d{2}|19\d{2})[-/]?(\d{1,2})", str(d_raw))
        if not m:
            continue
        try:
            d = _dt.date(int(m.group(1)), int(m.group(2)), 1)
        except (ValueError, TypeError):
            continue
        rows.append({"date": d, "value": v})

    if not rows:
        print(f"[ndc-relay/{label}/{slug}] items={len(items)} 但 0 row 解析")
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    print(f"[ndc-relay/{label}/{slug}] ✅ {len(df)} rows ({df['date'].iloc[0]} ~ {df['date'].iloc[-1]})")
    return df


def _try_ndc_via_relay(candidates: tuple, label: str) -> pd.DataFrame:
    """逐一試 NDC OpenAPI candidate 經 NAS 中繼站；第一個成功就回。"""
    for url in candidates:
        df = _fetch_via_nas_relay(url, label)
        if not df.empty:
            return df
    print(f"[ndc-relay/{label}] ❌ 所有 {len(candidates)} 個 candidate 全失敗")
    return pd.DataFrame()


# ──────────────────────────────────────────────────────────────────
# v18.154 data.gov.tw search API + dataset CSV（路徑 2/3 兜底）
# ──────────────────────────────────────────────────────────────────
_DGTW_SIGNAL_KEYWORDS: tuple = ("景氣對策信號", "景氣燈號", "景氣指標")
_DGTW_LEADING_KEYWORDS: tuple = ("領先指標綜合指數", "領先指標", "景氣領先指標")

# 已知 dataset ID 鄰近 6100 (PMI)：探 0099 ~ 6108 + 6053 (export 已知) 鄰近
_DGTW_CANDIDATE_IDS: tuple = (
    "6099", "6101", "6102", "6103", "6104", "6105",
    "6098", "6106", "6107", "6108", "6097", "6109",
    "6054", "6055", "6052", "6056",
)

_DGTW_SIGNAL_VALUE_KEYWORDS: tuple = (
    "綜合判斷分數", "對策信號", "景氣分數", "景氣對策", "信號分數", "分數",
)
_DGTW_LEADING_VALUE_KEYWORDS: tuple = (
    "領先指標綜合指數", "領先指標", "綜合指數",
)
_DGTW_DATE_COL_KEYWORDS: tuple = (
    "年月", "日期", "date", "Date", "time", "Time", "month", "Month", "yearMonth",
)


def _fetch_dgtw_search_dataset_ids(keyword: str, label: str) -> list:
    """search data.gov.tw → 回 candidate dataset IDs；多 shape parser + verbose log。"""
    try:
        from proxy_helper import fetch_url
        import urllib.parse as _up
    except ImportError:
        print(f"[dgtw/{label}/search] ❌ proxy_helper 不可用")
        return []
    encoded = _up.quote(keyword)
    for search_url in (
        f"https://data.gov.tw/api/v2/rest/dataset/search?q={encoded}&size=10",
        f"https://data.gov.tw/api/v1/rest/dataset/search?q={encoded}",
        f"https://data.gov.tw/api/front/dataset/search?q={encoded}",
    ):
        try:
            r = fetch_url(search_url, timeout=15, attempts=2,
                          headers={"Accept": "application/json"})
            if r is None:
                print(f"[dgtw/{label}/search] 無回應 {search_url[-30:]}")
                continue
            if r.status_code != 200:
                body = r.text[:200].replace("\n", " ") if r.text else "<empty>"
                print(f"[dgtw/{label}/search] HTTP={r.status_code} body={body}")
                continue
            try:
                j = r.json()
            except Exception as e:
                ct = r.headers.get("Content-Type", "?")[:50] if hasattr(r, "headers") else "?"
                body_preview = (r.text[:200] if r.text else "<empty>").replace("\n", " ")
                print(f"[dgtw/{label}/search] JSON 失敗 CT={ct} body={body_preview}")
                continue
        except Exception as e:
            print(f"[dgtw/{label}/search] {type(e).__name__}: {str(e)[:100]}")
            continue

        items = (j.get("result", {}).get("results")
                 or j.get("datasets")
                 or j.get("result", {}).get("records")
                 or j.get("data")
                 or (j if isinstance(j, list) else []))
        if not items or not isinstance(items, list):
            top = list(j.keys())[:5] if isinstance(j, dict) else type(j).__name__
            print(f"[dgtw/{label}/search] 0 items (top={top})")
            continue

        ids = []
        for it in items[:15]:
            if not isinstance(it, dict):
                continue
            ds_id = (it.get("identifier") or it.get("id")
                     or it.get("dataset_id") or it.get("datasetId"))
            title = (it.get("title") or it.get("name") or "")[:30]
            if ds_id:
                ids.append((str(ds_id), title))
        if ids:
            preview = [(i, t) for i, t in ids[:5]]
            print(f"[dgtw/{label}/search] ✅ 找到 {len(ids)} 個 datasets 前 5={preview}")
            return [i for i, _ in ids]
    return []


def _fetch_dgtw_dataset_csv_full(ds_id: str, value_keywords: tuple,
                                  label: str) -> pd.DataFrame:
    """從 dataset id 抓 metadata → 找 CSV resource → 下載 → 解 [date, value] 全部 rows.

    完全鏡像 macro_core._pmi_src_dgtw 模式（已驗證 dataset/6100 在生產 work）。
    """
    try:
        from proxy_helper import fetch_url
        import io as _io
        import csv as _csv
        import re as _re
    except ImportError:
        return pd.DataFrame()

    for meta_url in (f"https://data.gov.tw/api/v2/rest/dataset/{ds_id}",
                      f"https://data.gov.tw/api/v1/rest/dataset/{ds_id}",
                      f"https://data.gov.tw/dataset/{ds_id}/resource"):
        try:
            r = fetch_url(meta_url, timeout=10, attempts=1,
                          headers={"Accept": "application/json"})
            if r is None or r.status_code != 200:
                continue
            try:
                j = r.json()
            except Exception:
                continue
        except Exception:
            continue

        res = (j.get("result", {}).get("resources")
               or j.get("resources")
               or j.get("data", {}).get("resources")
               or j.get("result", {}).get("distribution")
               or [])
        if not res or not isinstance(res, list):
            continue

        csv_url = None
        csv_fmt = None
        for it in res:
            if not isinstance(it, dict):
                continue
            fmt = str(it.get("format", "")).upper()
            url2 = (it.get("url") or it.get("resourceDownloadUrl")
                    or it.get("downloadUrl"))
            if fmt in ("CSV", "JSON") and url2:
                csv_url = url2
                csv_fmt = fmt
                break
        if not csv_url:
            continue

        try:
            r2 = fetch_url(csv_url, timeout=20, attempts=2)
            if r2 is None or r2.status_code != 200:
                print(f"[dgtw/{label}/{ds_id}] CSV HTTP={r2.status_code if r2 else 'none'}")
                continue
        except Exception as e:
            print(f"[dgtw/{label}/{ds_id}] CSV fetch {type(e).__name__}: {e}")
            continue

        # CSV 解析（JSON 路徑暫不處理 — 通常 dataset 都提供 CSV）
        if csv_fmt != "CSV":
            print(f"[dgtw/{label}/{ds_id}] 跳過 non-CSV resource fmt={csv_fmt}")
            continue
        txt = r2.content.decode("utf-8-sig", errors="ignore")
        try:
            rdr = list(_csv.DictReader(_io.StringIO(txt)))
        except Exception as e:
            print(f"[dgtw/{label}/{ds_id}] CSV parse {type(e).__name__}: {e}")
            continue
        if not rdr:
            print(f"[dgtw/{label}/{ds_id}] CSV 0 rows")
            continue

        cols = list(rdr[0].keys())
        # 找 value 欄（keyword 優先匹配）
        value_col = next(
            (c for c in cols
             if any(kw in str(c) for kw in value_keywords)),
            None,
        )
        date_col = next(
            (c for c in cols
             if any(kw in str(c) for kw in _DGTW_DATE_COL_KEYWORDS)),
            None,
        )
        if not value_col:
            print(f"[dgtw/{label}/{ds_id}] CSV 無 value 欄 cols={cols[:8]}")
            continue

        rows = []
        for row in rdr:
            v_raw = row.get(value_col)
            if v_raw is None or str(v_raw).strip() in ("", "-", "—"):
                continue
            try:
                v = float(str(v_raw).replace(",", "").strip())
            except (ValueError, TypeError):
                continue
            # date：先試 date_col；fallback 掃全 row
            d_raw = row.get(date_col) if date_col else None
            m = _re.search(r"(20\d{2}|19\d{2})[-/年]?(\d{1,2})",
                           str(d_raw)) if d_raw else None
            if not m:
                for v2 in row.values():
                    m = _re.search(r"(20\d{2}|19\d{2})[-/年]?(\d{1,2})", str(v2))
                    if m:
                        break
            if not m:
                continue
            try:
                d = _dt.date(int(m.group(1)), int(m.group(2)), 1)
            except (ValueError, TypeError):
                continue
            rows.append({"date": d, "value": v})

        if not rows:
            print(f"[dgtw/{label}/{ds_id}] CSV 0 個有效 row col={str(value_col)[:30]}")
            continue

        df = pd.DataFrame(rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)
        print(f"[dgtw/{label}/{ds_id}] ✅ {len(df)} rows ({df['date'].iloc[0]} ~ {df['date'].iloc[-1]}) col={str(value_col)[:30]}")
        return df

    return pd.DataFrame()


def _fetch_dgtw_indicator(keywords: tuple, value_keywords: tuple,
                           candidate_ids: tuple, label: str) -> pd.DataFrame:
    """二路徑彙整：① search API ② 直接 probe 已知 dataset ID 範圍。"""
    # 路徑 1：search API（精準）
    seen_ids: set = set()
    for kw in keywords:
        ids = _fetch_dgtw_search_dataset_ids(kw, f"{label}/{kw[:6]}")
        for ds_id in ids[:5]:
            if ds_id in seen_ids:
                continue
            seen_ids.add(ds_id)
            df = _fetch_dgtw_dataset_csv_full(ds_id, value_keywords, label)
            if not df.empty:
                return df

    # 路徑 2：直接 probe 候選 ID（兜底）
    print(f"[dgtw/{label}/probe] search 全敗，改 probe {len(candidate_ids)} 個鄰近 ID")
    for ds_id in candidate_ids:
        if ds_id in seen_ids:
            continue
        df = _fetch_dgtw_dataset_csv_full(ds_id, value_keywords, label)
        if not df.empty:
            return df

    print(f"[dgtw/{label}] ❌ search + probe 全失敗")
    return pd.DataFrame()


def fetch_ndc_signal(start: _dt.date, end: _dt.date) -> pd.DataFrame:
    """景氣對策信號分數（月頻；範圍 9-45；來源 data.gov.tw NDC dataset）。

    輸出欄位：date, ndc_signal
    走 NAS Squid Proxy（fetch_url）+ 二路徑 fallback（search → ID probe）。
    """
    # 路徑 1：NDC OpenAPI via NAS 中繼站（v18.155 — AJAX header 可能觸發 JSON）
    raw = _try_ndc_via_relay(_NDC_SIGNAL_URL_CANDIDATES, "signal")
    # 路徑 2/3：data.gov.tw search + ID probe（v18.154 兜底）
    if raw.empty:
        print("[ndc_signal] NDC 中繼路徑失敗，改試 data.gov.tw...")
        raw = _fetch_dgtw_indicator(
            _DGTW_SIGNAL_KEYWORDS, _DGTW_SIGNAL_VALUE_KEYWORDS,
            _DGTW_CANDIDATE_IDS, "signal")
    if raw.empty:
        print("[ndc_signal] ⚠️ 無景氣對策信號資料")
        return raw
    raw = raw[(raw["date"] >= start) & (raw["date"] <= end)]
    out = raw.rename(columns={"value": "ndc_signal"})
    out["ndc_signal"] = out["ndc_signal"].round().astype("Int64")
    print(f"[ndc_signal] ✅ {len(out)} rows in [{start}, {end}]")
    return out.reset_index(drop=True)


def fetch_ndc_leading_index(start: _dt.date, end: _dt.date) -> pd.DataFrame:
    """領先指標綜合指數（月頻原始指數值；來源 data.gov.tw NDC dataset）。

    輸出欄位：date, leading_index
    6M smoothed change 由下游分析端 on-the-fly 算（rolling 6 月需 lookback context）。
    """
    # 路徑 1：NDC OpenAPI via NAS 中繼站（v18.155）
    raw = _try_ndc_via_relay(_NDC_LEADING_URL_CANDIDATES, "leading")
    # 路徑 2/3：data.gov.tw（v18.154 兜底）
    if raw.empty:
        print("[ndc_leading_index] NDC 中繼路徑失敗，改試 data.gov.tw...")
        raw = _fetch_dgtw_indicator(
            _DGTW_LEADING_KEYWORDS, _DGTW_LEADING_VALUE_KEYWORDS,
            _DGTW_CANDIDATE_IDS, "leading")
    if raw.empty:
        print("[ndc_leading_index] ⚠️ 無領先指標資料")
        return raw
    raw = raw[(raw["date"] >= start) & (raw["date"] <= end)]
    out = raw.rename(columns={"value": "leading_index"})
    print(f"[ndc_leading_index] ✅ {len(out)} rows in [{start}, {end}]")
    return out.reset_index(drop=True)


FETCHERS = {
    "twii_ohlcv": (fetch_twii_ohlcv, False),       # (fn, needs_token)
    "finmind_inst": (fetch_finmind_inst, True),
    "finmind_margin": (fetch_finmind_margin, True),
    "finmind_m1m2": (fetch_finmind_m1m2, True),
    "finmind_ndc_signal": (fetch_ndc_signal, False),       # v18.152 NDC OpenAPI 免 token
    "finmind_leading_index": (fetch_ndc_leading_index, False),
}


# ════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════
def update_one(name: str, today: _dt.date, bootstrap: bool, years: int,
               token: str) -> dict:
    """單一 dataset 增量更新；回傳 metadata 片段。"""
    fn, needs_token = FETCHERS[name]
    meta = {"name": name, "last_updated": None, "row_count": 0, "last_error": None}

    if needs_token and not token:
        meta["last_error"] = "FINMIND_TOKEN 未設定"
        print(f"[{name}] ⏭ 跳過：{meta['last_error']}")
        return meta

    existing = None if bootstrap else _load_existing(name)
    last = _last_date(existing)
    if last is None or bootstrap:
        start = today - _dt.timedelta(days=years * 365)
    else:
        start = last + _dt.timedelta(days=1)
        if start > today:
            print(f"[{name}] 已是最新（last={last}），跳過抓取")
            meta["last_updated"] = last.isoformat()
            meta["row_count"] = len(existing) if existing is not None else 0
            return meta

    print(f"[{name}] 抓 {start} ~ {today} ...")
    try:
        new = fn(start, today, token) if needs_token else fn(start, today)
    except Exception as e:
        meta["last_error"] = f"{type(e).__name__}: {e}"
        print(f"[{name}] ❌ {meta['last_error']}")
        return meta

    if new.empty:
        meta["last_error"] = "抓取結果為空"
        print(f"[{name}] ⚠️ 抓取結果為空，保留現有資料")
        if existing is not None and not existing.empty:
            meta["last_updated"] = _last_date(existing).isoformat()
            meta["row_count"] = len(existing)
        return meta

    merged = _merge_dedupe(existing, new, key="date")
    _write_parquet(name, merged)
    meta["last_updated"] = _last_date(merged).isoformat()
    meta["row_count"] = len(merged)
    return meta


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bootstrap", action="store_true",
                   help="砍掉重抓全部歷史（初次部署用）")
    p.add_argument("--years", type=int, default=5,
                   help="歷史長度（bootstrap / 缺檔時用，預設 5）")
    p.add_argument("--only", default=None,
                   help="只更新指定 dataset（debug 用，逗號分隔）")
    args = p.parse_args()

    CACHE_DIR.mkdir(exist_ok=True)
    today = _dt.date.today()
    token = os.environ.get("FINMIND_TOKEN", "")
    if not token:
        print("⚠️ FINMIND_TOKEN 未設定，FinMind 表全跳過（僅更新 TWII）")

    datasets = args.only.split(",") if args.only else DATASETS

    print(f"\n📊 update_macro_history.py 起跑（today={today}, bootstrap={args.bootstrap}）\n")
    metadata = {}
    for name in datasets:
        if name not in FETCHERS:
            print(f"[main] 未知 dataset: {name}")
            continue
        print(f"\n── {name} ──")
        metadata[name] = update_one(name, today, args.bootstrap, args.years, token)

    # 寫 metadata.json
    payload = {
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "datasets": metadata,
    }
    META_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(f"\n✅ metadata 寫入 → {META_PATH}")

    # 任何 fatal error 計入退碼，但仍維持 0 讓 workflow 不爆掉（部分失敗仍 commit 成功部分）
    err_count = sum(1 for m in metadata.values() if m.get("last_error"))
    if err_count:
        print(f"⚠️ {err_count}/{len(metadata)} dataset 有錯誤，請查上方 log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
