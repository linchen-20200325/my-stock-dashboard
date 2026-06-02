"""update_macro_history.py — GitHub Actions 排程：抓總經歷史資料增量到 data_cache/。

資料流（與 update_etf_managers.py 同模式，但抓多個 dataset）
=========================================================
data_cache/twii_ohlcv.parquet              ← ^TWII 日 K（yfinance via NAS proxy）
data_cache/finmind_inst.parquet            ← 三大法人總買賣超（FinMind）
data_cache/finmind_margin.parquet          ← 融資餘額（FinMind）
data_cache/finmind_m1m2.parquet            ← M1B / M2 月差（FinMind）
data_cache/finmind_ndc_signal.parquet      ← 景氣對策信號分數 9-45（FinMind TaiwanBusinessIndicator.monitoring）
data_cache/finmind_leading_index.parquet   ← 領先指標綜合指數（FinMind TaiwanBusinessIndicator.leading）
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

# FinMind TaiwanBusinessIndicator (v4)：wide-format 月頻國發會景氣表，
# 欄位 date / leading / leading_notrend / coincident / coincident_notrend /
# lagging / lagging_notrend / monitoring（景氣對策信號分數 9-45）。
# 同 (start, end, has_token) 全表只抓一次，NDC + leading 兩 fetcher 共用。
_MACRO_FULL_TABLE_CACHE: dict[tuple, pd.DataFrame] = {}


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


def _finmind_macro_table(start: _dt.date, end: _dt.date, token: str) -> pd.DataFrame:
    """FinMind TaiwanBusinessIndicator wide-format 全表（含模組級快取）。

    NDC monitoring + leading 都在同一 dataset 同一回應 — 用 (start, end, has_token)
    做 key 緩存避免重複 API call；wide-format 直接 column-pick 無需 long-format filter。
    """
    key = (start.isoformat(), end.isoformat(), bool(token))
    cached = _MACRO_FULL_TABLE_CACHE.get(key)
    if cached is not None:
        return cached
    raw = _finmind_get(
        "TaiwanBusinessIndicator", "",
        start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), token,
    )
    _MACRO_FULL_TABLE_CACHE[key] = raw
    return raw


def _pick_macro_column(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """從 TaiwanBusinessIndicator wide-format 抽出 [date, col] 並清理 NaN/型別。"""
    if df is None or df.empty or "date" not in df.columns or col not in df.columns:
        return pd.DataFrame()
    sub = df[["date", col]].copy()
    sub.columns = ["date", "value"]
    sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
    sub["date"] = pd.to_datetime(sub["date"]).dt.date
    return sub.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)


def fetch_finmind_ndc_signal(start: _dt.date, end: _dt.date,
                              token: str) -> pd.DataFrame:
    """景氣對策信號分數（月頻；範圍 9-45；來源 TaiwanBusinessIndicator.monitoring）。

    輸出欄位：date, ndc_signal
    用於驗證總經 Tab 的拐點判定：連 2 月翻多/翻空、歷史 crisis 對應。
    """
    raw = _finmind_macro_table(start, end, token)
    sub = _pick_macro_column(raw, "monitoring")
    if sub.empty:
        print("[finmind_ndc_signal] ⚠️ 無景氣對策信號資料（monitoring 欄缺失或全空）")
        return sub
    out = sub.rename(columns={"value": "ndc_signal"})
    out["ndc_signal"] = out["ndc_signal"].round().astype("Int64")
    print(f"[finmind_ndc_signal] ✅ {len(out)} rows")
    return out


def fetch_finmind_leading_index(start: _dt.date, end: _dt.date,
                                 token: str) -> pd.DataFrame:
    """領先指標綜合指數（月頻原始指數值；來源 TaiwanBusinessIndicator.leading）。

    輸出欄位：date, leading_index
    刻意只存原始指數值；6M smoothed change 需要 6 月以上 lookback context，
    增量更新時無法在 fetcher 內正確計算，由下游分析端 on-the-fly 算（讀全 series 再 rolling）。
    """
    raw = _finmind_macro_table(start, end, token)
    sub = _pick_macro_column(raw, "leading")
    if sub.empty:
        print("[finmind_leading_index] ⚠️ 無領先指標資料")
        return sub
    out = sub.rename(columns={"value": "leading_index"})
    print(f"[finmind_leading_index] ✅ {len(out)} rows")
    return out


FETCHERS = {
    "twii_ohlcv": (fetch_twii_ohlcv, False),       # (fn, needs_token)
    "finmind_inst": (fetch_finmind_inst, True),
    "finmind_margin": (fetch_finmind_margin, True),
    "finmind_m1m2": (fetch_finmind_m1m2, True),
    "finmind_ndc_signal": (fetch_finmind_ndc_signal, True),
    "finmind_leading_index": (fetch_finmind_leading_index, True),
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
