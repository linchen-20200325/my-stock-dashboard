"""update_macro_history.py — GitHub Actions 排程：抓總經歷史資料增量到 data_cache/。

資料流（與 update_etf_managers.py 同模式，但抓多個 dataset）
=========================================================
data_cache/twii_ohlcv.parquet              ← ^TWII 日 K（yfinance via NAS proxy）
data_cache/finmind_inst.parquet            ← 三大法人總買賣超（FinMind）
data_cache/finmind_margin.parquet          ← 融資餘額（FinMind）
data_cache/finmind_m1m2.parquet            ← M1B / M2 月差（FinMind）
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
    python update_macro_history.py --bootstrap # 砍掉重抓全部 20 年（初次部署用）
    python update_macro_history.py --years 10  # 自訂歷史長度（預設 20）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import re
import sys
from pathlib import Path

import pandas as pd
import requests

# v19.101:`python scripts/update_macro_history.py` 直跑時 sys.path[0]=scripts/,
# 不含 repo root → 函式內的 `src.*` lazy import 必 ImportError(m1m2 段死因之一)。
# 同 calibrate_health_weights.py 既有模式。
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

CACHE_DIR = Path("data_cache")
META_PATH = CACHE_DIR / "metadata.json"

# Parquet 表名 → 抓取函式名（runtime dispatch）
DATASETS = ["twii_ohlcv", "finmind_inst", "finmind_margin", "finmind_m1m2",
            "tw_pmi"]  # v18.176 Phase D：加台灣 PMI 月頻 history（dgtw 6100）

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
        # v19.101:v18.359 檔案搬家後根目錄 shim 已刪,舊頂層路徑恆 ImportError
        # → 之前一律走直連 fallback(twii 因此僥倖活著)。改正式路徑。
        from src.data.proxy.proxy_helper import fetch_url
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
    # v19.170:憑證只走 header,不進 query string(避免落入 proxy / access log)
    # 本檔為 GitHub Actions cron,query string 會被 runner log 明文記錄,風險最高。
    _hdrs = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if token:
        _hdrs["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(
            FINMIND_URL, params=params, timeout=30,
            headers=_hdrs,
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

        # ── §1/§3.2 sanity:「價格有波動但 volume == 0」= 物理上不可能的觀測 ──
        # 上游(Yahoo Chart API)對 ^TWII 會間歇回 volume=0。實測
        # `data_cache/twii_ohlcv.parquet`(量測日 2026-08-27):41 筆 volume==0,
        # **41/41 都 high > low** —— 價格有波動就一定有成交,那個 0 不是觀測、
        # 是缺值。若原樣落地,下游 `market_strategy.volume_window_stats()` 之外
        # 的任何 rolling 均量都會被稀釋(實測可把量比灌到 20.0x → 假瘋牛)。
        #
        # 判準刻意用「價格有動但量為 0」而不是絕對門檻:那才是「物理上不可能」
        # 的準確表達,且不會誤殺 §4.6 記載的「跌停 0 vol」(整日無成交時
        # high == low,不命中本條)。
        #
        # 處置刻意**不 raise**(對照同檔 `fetch_finmind_margin` 的全批不寫):
        # 那裡漂的是**採用欄位/口徑**,整批都不可信;這裡 close 本身是好的,
        # 只有 volume 一欄有問題 —— 全批擋掉會連帶弄丟日 K,損失更大。
        # 故改為「顯式寫 NaN + log 受影響筆數」(§1:任何填補/剔除必須顯式 + log)。
        if not df.empty and "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
            _impossible = (df["volume"] == 0) & (df["high"] > df["low"])
            _n_bad = int(_impossible.sum())
            if _n_bad:
                _dates = list(df.loc[_impossible, "date"].astype(str).head(5))
                df.loc[_impossible, "volume"] = float("nan")
                print(f"[twii_ohlcv] ⚠️ {_n_bad}/{len(df)} 列 volume=0 但 high>low"
                      f"（價格有波動 ⇒ 必有成交）→ 顯式標為 NaN，不寫 0"
                      f"（樣本日期={_dates}）")

        # S-PROV-1 phase 13 v18.259 — provenance(schema-additive)
        if not df.empty:
            df["source"] = "Yahoo:^TWII:chart"
            df["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
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
    # S-PROV-1 phase 13 v18.259 — provenance(schema-additive)
    if not out.empty:
        out["source"] = "FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign"
        out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    return out


def fetch_finmind_margin(start: _dt.date, end: _dt.date, token: str) -> pd.DataFrame:
    """融資餘額（FinMind TaiwanStockTotalMarginPurchaseShortSale）。

    輸出欄位：date / margin_balance（**單位:元**）/ source（列級）/ fetched_at。

    B3 v19.179 治本（原實作是本次雙峰混口徑事故的根因）
    ====================================================
    原欄位偵測是照**個股版寬格式**寫的（`MarginPurchaseTodayBalance`），但本
    dataset 是**彙總版長格式** —— 同一天回多列、靠 `name` 分口徑
    （`MarginPurchaseMoney`=元 / `MarginPurchaseVolume`=**張**）。原碼
    `raw[["date", bal_col]]` 把所有 name 列一起拿，再被 `_merge_dedupe` 的
    `drop_duplicates(keep="last")` 壓成一列 → 留哪一列由 API 回傳順序決定
    → 序列變「元 / 張」雙峰混口徑（2006~2026 共 4,929 列約 40% 元、36% 張）。

    修正三件：
    1. 列/欄判定改走 `shared.margin_schema`（L0 SSOT），與即時路徑
       `src/data/daily/daily_data_fetchers.fetch_margin_balance` **同一份規則**。
       只認 Money 列 + 只取當日餘額欄（排除 `Yes*` —— 用昨日欄會讓整條序列
       **日期錯位一天**，違 §2.3 PIT）。
    2. 寫入前逐列 sanity（元 → 億，§3.2 [500, 10000] 億）；**任一列不合格 → raise**
       （由 `update_one` 接住 → 記 `last_error` → **不寫 parquet**，既有資料原封不動）。
       單位/schema 漂移屬系統性問題，不可只丟壞列繼續（§1 Fail-Loud, Never Fake）。
    3. `source` 記到**列級**（`...:MarginPurchaseMoney:TodayBalance`），
       原本只記到 dataset 就停 → 事後分不出 Money vs Volume，此為根因之二。
    """
    from shared.margin_schema import (
        MARGIN_BALANCE_SANITY_MAX_YI,
        MARGIN_BALANCE_SANITY_MIN_YI,
        MARGIN_DATASET,
        TWD_PER_YI,
        extract_margin_money_series,
        margin_twd_sanity_mask,
    )

    raw = _finmind_get(MARGIN_DATASET, "",
                       start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), token)
    if raw.empty:
        return raw

    out, meta = extract_margin_money_series(raw)
    print(f"[finmind_margin] shape={meta['format']} raw={meta['n_raw']} "
          f"money列={meta['n_money_rows']} 採用欄={meta['balance_col']} "
          f"name值={meta['name_values']}")
    if meta["n_dropped_nonpositive"]:
        # §3.3:任何顯式剔除都要 log 筆數
        print(f"[finmind_margin] ⚠️ 顯式剔除 {meta['n_dropped_nonpositive']} 列"
              f"（餘額 NaN / <=0）")
    if meta["n_dup_dates"]:
        print(f"[finmind_margin] ⚠️ 過濾後仍有 {meta['n_dup_dates']} 列同日重複"
              f"（上游 shape 可能又變了）→ 保留第一列")
    if out.empty:
        print(f"[finmind_margin] ❌ 取不到融資金額序列：{meta['reason']}")
        return pd.DataFrame()

    # ── §3.2 sanity：元 → 億 ∈ (500, 10000)；任一列不合格 = 上游口徑漂移 → 全批不寫
    ok = margin_twd_sanity_mask(out["margin_balance"])
    if not bool(ok.all()):
        bad = out[~ok.to_numpy()]
        _yi = bad["margin_balance"] / TWD_PER_YI
        raise RuntimeError(
            f"融資餘額 sanity 失敗：{len(bad)}/{len(out)} 列換算後超出 "
            f"[{MARGIN_BALANCE_SANITY_MIN_YI:.0f}, {MARGIN_BALANCE_SANITY_MAX_YI:.0f}] 億"
            f"（採用欄={meta['balance_col']}, "
            f"樣本日期={list(bad['date'].astype(str).head(5))}, "
            f"樣本值(億)={[round(float(v), 4) for v in _yi.head(5)]}）"
            "→ 疑似上游改口徑/換欄；不寫入 parquet（§1 寧缺勿錯）"
        )

    out = out.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.date
    # S-PROV-1 phase 13 v18.259 — provenance；B3 v19.179 起 source 已是列級字串
    out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    print(f"[finmind_margin] ✅ {len(out)} rows 通過 sanity "
          f"({out['margin_balance'].min() / TWD_PER_YI:.0f}~"
          f"{out['margin_balance'].max() / TWD_PER_YI:.0f} 億)")
    return out[["date", "margin_balance", "source", "fetched_at"]]


# ════════════════════════════════════════════════════════════════
# B7b（2026-09-27）：CBC PXWeb「存量 vs 流量」欄位辨識
# ════════════════════════════════════════════════════════════════
# 根因：舊解析寫死「row[1] = 主數值」，但 EF19M01／EF21M01 的 row[1] 實測是
# **月變動額（流量）**—— 2026-09-24 cron 整檔重抓後 238 列仍有 87 列 M1B 或 M2
# 為負（貨幣供給額是存量，不可能為負）。再對會變號的序列算 YoY → gap ∈ ±13,976。
#
# 修法（**不猜欄位位置**）：
#   ① 先用回應內的欄位標籤找「餘額」欄（排除 變動／增減／年增／率 等流量／比率欄）；
#   ② 標籤不在 → 以**定義**驗證每一欄（全 > 0 ＋ 月變動 ≤ 20%），**恰好一欄**過才用；
#   ③ 0 欄或 ≥ 2 欄都過 → **fail loud**（回 None ＋ 印結構 dump），**不挑一個**。
# 最後合併後再過一次 `_m1m2_level_sanity`（與 `export_stock_db._money_supply_sanity_gate`
# 同一組定義常數），不過就整表拒寫 —— 寧可缺席，不寫錯的量（§1）。
#
# ⚠️ DL-f1-r1（2026-09-28）起 `fetch_finmind_m1m2` **不再呼叫本段**：EF19M01／EF21M01 是
# 「變動因素分析」表，每一欄都是變動額，本段的判定（無餘額欄 → 拒用）是對的，但它讓重建
# 永遠失敗。餘額改由下方 `_parse_cbc_ef15m01_levels` 從 EF15M01 依標籤取得。
# 因此 `_parse_cbc_pxweb_level`、`_cbc_find_column_labels`、`_cbc_label_text`、`_is_level_series`、
# `_to_float` 與本段三個 `_CBC_*` 常數成為 0 production caller（只剩單測引用；`_cbc_norm_label`
# 仍被新解析器使用）。是否清除交總管裁示 —— 刪除需連同其直接單測一起刪，不在本批授權範圍內。
_CBC_LEVEL_LABEL_KEYS = ("餘額", "outstanding", "level", "amount")
_CBC_FLOW_LABEL_KEYS = ("變動", "增減", "增加", "減少", "年增", "月增", "成長",
                        "率", "change", "growth", "rate", "%", "flow")
# 存量序列的月變動上限（相對值）。M1B／M2 月增率歷史極值約 ±5%；20% 是寬鬆上界，
# 目的是把「月變動額」這種會跨 0 的流量序列排除，不是攔真實波動。
_CBC_LEVEL_MAX_MOM_ABS = 0.20


def _to_float(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _cbc_label_text(x) -> str | None:
    if isinstance(x, str):
        return x
    if isinstance(x, dict):
        for k in ("label", "name", "text", "title", "valueTexts", "id"):
            v = x.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return None


def _cbc_find_column_labels(obj, n_value_cols: int, _depth: int = 0) -> list | None:
    """在回應 JSON 內找一串長度 = 欄數（含或不含期間欄）的欄位標籤。找不到回 None。"""
    if _depth > 6 or obj is None:
        return None
    if isinstance(obj, list):
        texts = [_cbc_label_text(x) for x in obj]
        if texts and all(t is not None for t in texts):
            if len(texts) == n_value_cols + 1:
                return texts[1:]
            if len(texts) == n_value_cols:
                return texts
        for x in obj:
            if isinstance(x, (dict, list)):
                hit = _cbc_find_column_labels(x, n_value_cols, _depth + 1)
                if hit is not None:
                    return hit
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("dataSets", "value"):  # 資料列本身不是標籤
                continue
            hit = _cbc_find_column_labels(v, n_value_cols, _depth + 1)
            if hit is not None:
                return hit
    return None


def _is_level_series(vals: list) -> bool:
    """定義檢查：存量序列 → 全數可解析、全 > 0、相鄰月相對變動 ≤ 上限。"""
    if len(vals) < 13 or any(v is None for v in vals):
        return False
    if any(v <= 0 for v in vals):
        return False
    for a, b in zip(vals, vals[1:]):
        if abs(b / a - 1) > _CBC_LEVEL_MAX_MOM_ABS:
            return False
    return True


def _cbc_norm_label(t: str) -> str:
    """標籤正規化：全形→半形（NFKC）、大寫、去空白（比對序列名用）。"""
    import unicodedata
    return "".join(unicodedata.normalize("NFKC", str(t)).upper().split())


def _parse_cbc_pxweb_level(sdmx, label: str, series: str | None = None):
    """CBC PXWeb 回應 → [{"period_raw", "value"}]（**餘額欄**）或 None（fail loud）。

    `series`（"M1B"／"M2"）：回應帶欄位標籤時，選中的餘額欄標籤**必須含該序列名**
    （全半形／大小寫不拘）—— 防止表內另有 M1A 等餘額欄時選錯序列卻照樣通過存量檢查。
    有標籤但沒有一欄含序列名 → fail loud（不寫）。

    回 (rows, col_desc)；失敗回 (None, 原因)。純函式,無 I/O（只 print 診斷）。
    """
    raw_rows = []
    if isinstance(sdmx, dict):
        _data = sdmx.get("data")
        if isinstance(_data, dict):
            raw_rows = _data.get("dataSets") or _data.get("value") or []
        elif isinstance(_data, list):
            raw_rows = _data
    rows = [r for r in raw_rows if isinstance(r, list) and len(r) >= 2]
    if not rows:
        return None, "dataSets 空"
    n_val = min(len(r) for r in rows) - 1
    labels = _cbc_find_column_labels(sdmx, n_val)
    chosen = None
    col_desc = ""
    if labels is not None:
        lv = [i for i, t in enumerate(labels)
              if any(k in t.lower() for k in _CBC_LEVEL_LABEL_KEYS)
              and not any(k in t.lower() for k in _CBC_FLOW_LABEL_KEYS)]
        if series:
            _sn = _cbc_norm_label(series)
            lv_s = [i for i in lv if _sn in _cbc_norm_label(labels[i])]
            if not lv_s:
                print(f"[finmind_m1m2/{label}] 餘額欄標籤皆不含序列名 {series!r} → 不猜"
                      f" labels={labels}")
                return None, f"標籤無 {series} 餘額欄"
            lv = lv_s
        if len(lv) > 1:
            # CBC 官方貨幣供給年增率以「日平均」餘額計 → 同時有日平均／月底時取日平均
            lv_avg = [i for i in lv if "日平均" in labels[i] or "average" in labels[i].lower()]
            if len(lv_avg) == 1:
                lv = lv_avg
        if len(lv) == 1:
            chosen = lv[0]
            col_desc = f"label={labels[chosen]}"
        else:
            print(f"[finmind_m1m2/{label}] 欄位標籤無法唯一辨識餘額欄"
                  f"（候選 {len(lv)}）labels={labels}")
            return None, f"標籤候選 {len(lv)} 欄"
    else:
        cand = []
        for i in range(n_val):
            vals = [_to_float(r[i + 1]) for r in rows]
            if _is_level_series(vals):
                cand.append(i)
        if len(cand) != 1:
            print(f"[finmind_m1m2/{label}] 無欄位標籤,且符合存量定義的欄數={len(cand)}"
                  f"（須恰為 1）→ 不猜。首列={rows[0][:12]} 末列={rows[-1][:12]}"
                  f" top-keys={list(sdmx.keys())[:10] if isinstance(sdmx, dict) else type(sdmx).__name__}")
            return None, f"定義候選 {len(cand)} 欄"
        chosen = cand[0]
        col_desc = f"col={chosen + 1}(定義辨識)"
    out = [{"period_raw": str(r[0]), "value": r[chosen + 1]} for r in rows]
    if not _is_level_series([_to_float(x["value"]) for x in out]):
        print(f"[finmind_m1m2/{label}] 選定欄 {col_desc} 不符存量定義（有 ≤0 或跳動過大）→ 拒用")
        return None, f"{col_desc} 非存量"
    return out, col_desc


def _m1m2_level_sanity(df: pd.DataFrame) -> tuple[bool, str]:
    """寫檔前守門（整表判定,不逐列剔除）。三條定義檢查同 `export_stock_db._money_supply_sanity_gate`。

    （DL-f1-r1：匯出端另有「億元量級帶」—— 那是換算後的單位檢查,本檔 parquet 為百萬元,
    單位改由 `_parse_cbc_ef15m01_levels` 比對回應 `meta.units` 把關,不在此重複。）"""
    from shared.signal_thresholds import (
        M1B_M2_GAP_SANITY_ABS_MAX_PP,
        MONEY_SUPPLY_LEVEL_MIN,
    )
    if df is None or df.empty:
        return False, "空表"
    for c in ("m1b", "m2", "m1b_m2_gap"):
        if c not in df.columns:
            return False, f"缺欄 {c}"
    _lv = (df["m1b"] <= MONEY_SUPPLY_LEVEL_MIN) | (df["m2"] <= MONEY_SUPPLY_LEVEL_MIN)
    _ord = df["m2"] < df["m1b"]
    _g = df["m1b_m2_gap"]
    _gap = _g.notna() & (_g.abs() > M1B_M2_GAP_SANITY_ABS_MAX_PP)
    bad = _lv | _ord | _gap
    if not bad.any():
        return True, f"{len(df)} 列通過"
    return False, (f"{int(bad.sum())}/{len(df)} 列不合格（餘額≤0:{int(_lv.sum())}、"
                   f"m2<m1b:{int(_ord.sum())}、|gap|>{M1B_M2_GAP_SANITY_ABS_MAX_PP:.0f}pp:"
                   f"{int(_gap.sum())}）→ 疑似月變動額而非餘額")


# ════════════════════════════════════════════════════════════════
# DL-f1-r1（2026-09-28）：M1B／M2 餘額改取 CBC EF15M01（貨幣總計數-日平均數）
# ════════════════════════════════════════════════════════════════
# 根因（GitHub Actions run 36408641177 實測）：EF19M01／EF21M01 是「貨幣供給額 M1B／M2
# **變動因素分析**」表 —— 每一欄都是變動額（流量），根本沒有餘額欄；B7b 的解析器正確地
# 拒絕它們，於是每天排程的整段重建都失敗。同一個 API 的 EF15M01 才有餘額：
#   meta.title = "5.貨幣總計數-A.日平均數依期間"、meta.units = "新台幣百萬元,%"
#   data.structure.Table1 = 15 個序列標籤（M1A、M1B、M2 各一；標籤是全形字）
#   data.structure.Table2 = ["原始值", "年增率"]
#   data.dataSets 每列 = [期間, 序列0 原始值, 序列0 年增率, 序列1 原始值, …]；缺值是字串 "-"
# 解析原則（**依標籤成對，不猜欄位位置**）：
#   ① 值欄數必須 = len(Table1) × len(Table2)，任一列不符 → 整表拒用並印出標籤；
#   ② 序列以 NFKC 正規化後的**完整名稱**唯一命中（M1A 不得冒充 M1B；0 或 ≥2 命中都拒用）；
#   ③ 量度以 Table2 標籤找「原始值」（= 餘額）與「年增率」（官方值，只拿來對帳）；
#   ④ "-" = 缺值，**不填 0**；餘額缺值的月份顯式剔除並逐月印出；
#   ⑤ 對帳：由餘額自算的年增率須與表內官方年增率一致（容差推導見 `_ef15_yoy_tolerance_pp`），
#      任一列超出 → 整表拒用（選錯欄、配錯對、表內自相矛盾，三者都不得寫入）。
# 單位：meta.units 的「原始值」單位必須等於 `MONEY_SUPPLY_CACHE_UNIT_LABEL`（新台幣百萬元），
# 不一致就拒用 —— parquet 對讀取端承諾的是百萬元（`export_stock_db` 再 ÷100 成億元外送）。
_EF15_FILE = "EF15M01"
_EF15_TITLE_KEY = "日平均"                  # source 字串宣稱「日平均餘額」的依據，必須在 meta.title 內
_EF15_SERIES = (("m1b", "M1B", "貨幣總計數-M1B"),   # (輸出欄, 簡稱, NFKC＋去空白後的完整序列名)
                ("m2", "M2", "貨幣總計數-M2"))
_EF15_MEASURE_LEVEL = "原始值"
_EF15_MEASURE_YOY = "年增率"
_EF15_UNIT_YOY = "%"
_EF15_MISSING = "-"
_EF15_PERIOD_RE = re.compile(r"^(\d{4})M(\d{2})$")
# 對帳容差的三個來源（推導見 `_ef15_yoy_tolerance_pp`）：
_EF15_YOY_DECIMALS = 2          # 表內官方年增率只到小數兩位（實測 "7.34"、"10.00"）
_EF15_LEVEL_STEP = 1.0          # 餘額以「百萬元」整數發布 → 相鄰可表示值的間距 = 1 百萬元
_EF15_FLOAT_EPS_PP = 1e-9       # 十進位字串 → 二進位浮點的表示誤差（遠小於前兩項）


def _ef15_yoy_tolerance_pp(level_t: float, level_t12: float) -> float:
    """|自算年增率 − 表內官方年增率| 的容許上界（百分點）。三項相加：

    (1) 官方年增率只到小數兩位：表內值 = 四捨五入(真值, 2) → 誤差 ≤ 半個最小位數
        = 0.5 × 10⁻² = **0.005 pp**。（前提：四捨五入而非截斷。DL-f1-r1 實作組以探針三列真實資料
        的恆等式 M1B＝M1A＋活期儲蓄、M2＝M1B＋準貨幣 推回 t−12 做區間檢查：截斷假設下
        2026-07 的 M2 無解、四捨五入假設下全部有解 —— 單組分析，未經第二組複驗。）
    (2) 餘額以百萬元整數發布：每個餘額的捨入誤差 ≤ δ = 0.5 × `_EF15_LEVEL_STEP`。
        自算 r = (a/b − 1)×100；a、b 各偏離 ≤ δ 時
        |Δr| = 100·|b·εa − a·εb| / (b·(b+εb)) ≤ **100·δ·(a + b) / (b·(b − δ))**（精確上界，非近似）。
        本表最小的 M1B 餘額約 1.26e6 百萬元 → 此項 < 1e-4 pp；仍逐列計入，不假設可忽略。
    (3) 浮點表示誤差 → `_EF15_FLOAT_EPS_PP`。
    超出三者之和 = 不是捨入能解釋的差 → 選錯欄／配錯對／表內自相矛盾 → fail loud。
    呼叫端須保證 level_t12 > δ（否則無法對帳，由呼叫端直接判不符）。
    """
    _delta = 0.5 * _EF15_LEVEL_STEP
    _half_ulp = 0.5 * 10.0 ** (-_EF15_YOY_DECIMALS)
    _rounding = 100.0 * _delta * (abs(level_t) + abs(level_t12)) / (level_t12 * (level_t12 - _delta))
    return _half_ulp + _rounding + _EF15_FLOAT_EPS_PP


def _ef15_labels(seq) -> list | None:
    """PXWeb `structure.TableN`（[{"data": "…"}, …]）→ 標籤字串 list；任一項取不到字串 → None。"""
    if not isinstance(seq, list) or not seq:
        return None
    out = []
    for x in seq:
        t = x.get("data") if isinstance(x, dict) else x
        if not isinstance(t, str) or not t.strip():
            return None
        out.append(t)
    return out


def _ef15_cell(v):
    """值欄字串 → float；"-" → None（缺值，**不是 0**）；其他無法解析的內容 → ValueError（不猜）。"""
    s = str(v).replace(",", "").strip()
    if s == _EF15_MISSING:
        return None
    x = float(s)
    if not math.isfinite(x):
        raise ValueError(f"非有限數值 {v!r}")
    return x


def _parse_cbc_ef15m01_levels(sdmx) -> tuple[pd.DataFrame | None, str]:
    """CBC EF15M01 回應 → (DataFrame[date, m1b, m2], 說明) 或 (None, 拒用原因)。

    純函式（無 I/O，只 print 診斷）。date = 資料月月初（datetime.date）；m1b／m2 = 日平均餘額，
    單位新台幣百萬元，int（與既有 parquet schema 的 int64 一致）。規則見本段上方註解。
    """
    from shared.signal_thresholds import MONEY_SUPPLY_CACHE_UNIT_LABEL

    tag = f"[finmind_m1m2/{_EF15_FILE}]"

    def _fail(reason: str, **dump):
        _extra = "".join(f" {k}={v!r}" for k, v in dump.items())
        print(f"{tag} ❌ 拒用：{reason}{_extra}")
        return None, reason

    if not isinstance(sdmx, dict):
        return _fail(f"回應不是 JSON 物件（{type(sdmx).__name__}）")
    _data = sdmx.get("data")
    _struct = _data.get("structure") if isinstance(_data, dict) else None
    rows = _data.get("dataSets") if isinstance(_data, dict) else None
    t1 = _ef15_labels(_struct.get("Table1")) if isinstance(_struct, dict) else None
    t2 = _ef15_labels(_struct.get("Table2")) if isinstance(_struct, dict) else None
    if t1 is None or t2 is None or not isinstance(rows, list) or not rows:
        return _fail("缺 data.structure.Table1／Table2（字串標籤）或 data.dataSets",
                     top_keys=list(sdmx.keys())[:10],
                     data_keys=(list(_data.keys())[:10] if isinstance(_data, dict)
                                else type(_data).__name__),
                     Table1=t1, Table2=t2)

    # ① 值欄數 = len(Table1) × len(Table2)（每一列都要成立）
    n_val = len(t1) * len(t2)
    bad_len = [(i, len(r) if isinstance(r, list) else type(r).__name__)
               for i, r in enumerate(rows) if not (isinstance(r, list) and len(r) == n_val + 1)]
    if bad_len:
        return _fail(f"值欄數 ≠ len(Table1)×len(Table2) = {len(t1)}×{len(t2)} = {n_val}"
                     f"（含期間欄每列應為 {n_val + 1} 格；不符 {len(bad_len)} 列，"
                     f"前 5 =(列號, 格數) {bad_len[:5]}）", Table1=t1, Table2=t2)

    # ③ 量度：Table2 須恰有一個「原始值」、一個「年增率」
    t2n = [_cbc_norm_label(t) for t in t2]
    j_lv = [j for j, t in enumerate(t2n) if t == _cbc_norm_label(_EF15_MEASURE_LEVEL)]
    j_yy = [j for j, t in enumerate(t2n) if t == _cbc_norm_label(_EF15_MEASURE_YOY)]
    if len(j_lv) != 1 or len(j_yy) != 1:
        return _fail(f"Table2 須各恰有一個「{_EF15_MEASURE_LEVEL}」與「{_EF15_MEASURE_YOY}」"
                     f"（實得 {len(j_lv)}／{len(j_yy)}）", Table2=t2)
    j_lv, j_yy = j_lv[0], j_yy[0]

    # 表頭：日平均（source 宣稱的依據）＋ 單位（與 parquet 單位契約一致）
    _meta = sdmx.get("meta") if isinstance(sdmx.get("meta"), dict) else {}
    if _EF15_TITLE_KEY not in _cbc_norm_label(_meta.get("title") or ""):
        return _fail(f"meta.title 不含「{_EF15_TITLE_KEY}」→ 不能宣稱是日平均餘額",
                     title=_meta.get("title"))
    _units = _cbc_norm_label(_meta.get("units") or "").split(",")
    if (len(_units) != len(t2)
            or _units[j_lv] != _cbc_norm_label(MONEY_SUPPLY_CACHE_UNIT_LABEL)
            or _units[j_yy] != _EF15_UNIT_YOY):
        return _fail(f"meta.units 與量度不對應（須 {_EF15_MEASURE_LEVEL}＝"
                     f"{MONEY_SUPPLY_CACHE_UNIT_LABEL}、{_EF15_MEASURE_YOY}＝{_EF15_UNIT_YOY}）",
                     units=_meta.get("units"), Table2=t2)

    # ② 序列：NFKC 正規化後的完整名稱唯一命中；欄位 = 1 + i × len(Table2) + j
    t1n = [_cbc_norm_label(t) for t in t1]
    cols = {}
    for key, short, name in _EF15_SERIES:
        hits = [i for i, t in enumerate(t1n) if t == _cbc_norm_label(name)]
        if len(hits) != 1:
            return _fail(f"序列「{name}」須以完整名稱唯一命中，實得 {len(hits)} 個", Table1=t1)
        i = hits[0]
        cols[key] = (short, t1n[i], 1 + i * len(t2) + j_lv, 1 + i * len(t2) + j_yy)

    # ④ 逐列解析："-" = 缺值；其他解析不了的內容 → 拒用（不猜）
    recs: dict = {}
    for r in rows:
        _p = str(r[0]).strip()
        _m = _EF15_PERIOD_RE.match(_p)
        if not _m or not 1 <= int(_m.group(2)) <= 12:
            return _fail(f"期間格式不是 YYYYMmm：{_p!r}")
        d = _dt.date(int(_m.group(1)), int(_m.group(2)), 1)
        if d in recs:
            return _fail(f"期間重複：{_p}")
        vals = {}
        for key, (short, _lab, c_lv, c_yy) in cols.items():
            try:
                lv, yy = _ef15_cell(r[c_lv]), _ef15_cell(r[c_yy])
            except (TypeError, ValueError) as e:
                return _fail(f"{_p} {short} 值無法解析（{e}）",
                             level_raw=r[c_lv], yoy_raw=r[c_yy])
            if lv is not None and not float(lv).is_integer():
                return _fail(f"{_p} {short} 餘額不是整數百萬元（格式或單位變了？）",
                             level_raw=r[c_lv])
            vals[key] = (lv, yy)
        recs[d] = vals

    _miss = {key: sorted(d for d, v in recs.items() if v[key][0] is None) for key in cols}
    dropped = sorted(set(_miss["m1b"]) | set(_miss["m2"]))
    if dropped:
        print(f"{tag} ⚠️ 餘額欄為「{_EF15_MISSING}」→ 剔除 {len(dropped)} 個月（不填 0、不補值）："
              + "；".join(f"{cols[k][0]} 缺 {[d.strftime('%Y-%m') for d in v]}"
                         for k, v in _miss.items() if v))
    keep = {d: v for d, v in recs.items() if d not in set(dropped)}
    if not keep:
        return _fail("剔除缺值月份後無任何月份")

    # ⑤ 對帳：自算年增率（t ÷ t−12 − 1，t−12 = 同月去年）vs 表內官方年增率
    _delta = 0.5 * _EF15_LEVEL_STEP
    n_ok = {k: 0 for k in cols}
    n_skip = {k: 0 for k in cols}
    worst = {k: 0.0 for k in cols}
    bad = []
    for d in sorted(keep):
        _prev = keep.get(_dt.date(d.year - 1, d.month, 1))
        for key, (short, _lab, _c1, _c2) in cols.items():
            a, off = keep[d][key]
            if off is None or _prev is None:
                n_skip[key] += 1                    # 無官方年增率 或 t−12 無餘額 → 無從對帳
                continue
            b = _prev[key][0]
            if b <= _delta:
                bad.append((d.strftime("%Y-%m"), short, "t−12 餘額 ≤ 捨入半階,無法對帳", off))
                continue
            calc = (a / b - 1) * 100
            diff = abs(calc - off)
            if diff > _ef15_yoy_tolerance_pp(a, b):
                bad.append((d.strftime("%Y-%m"), short, round(calc, 6), off))
            else:
                n_ok[key] += 1
                worst[key] = max(worst[key], diff)
    if bad:
        return _fail(f"對帳不符 {len(bad)} 列（自算年增率 vs 表內官方年增率，超出捨入容差）",
                     first10=bad[:10])
    for key, (short, _lab, _c1, _c2) in cols.items():
        if n_ok[key] == 0:
            return _fail(f"{short} 無任何可對帳的列 → 無法驗證欄位配對")

    ds = sorted(keep)
    out = pd.DataFrame({
        "date": ds,
        "m1b": pd.array([int(keep[d]["m1b"][0]) for d in ds], dtype="int64"),
        "m2": pd.array([int(keep[d]["m2"][0]) for d in ds], dtype="int64"),
    })
    desc = "; ".join(f"{short} label={lab}" for short, lab, _c1, _c2 in cols.values())
    print(f"{tag} ✅ 日平均餘額 {len(out)} 個月（{ds[0]:%Y-%m}～{ds[-1]:%Y-%m}，{desc}）；"
          f"對帳 " + "、".join(f"{cols[k][0]} {n_ok[k]} 列 max|Δ|={worst[k]:.4f}pp"
                              for k in cols)
          + "；無從對帳（無官方年增率或無 t−12 餘額）"
          + "、".join(f"{cols[k][0]} {n_skip[k]} 列" for k in cols))
    return out, desc


def fetch_finmind_m1m2(start: _dt.date, end: _dt.date, token: str) -> pd.DataFrame:
    """M1B / M2 月頻（CBC 中央銀行；FinMind 無對應 dataset，表名為歷史沿用）。

    走 proxy_helper.fetch_url（PROXY_URL）→ CBC 擋海外 IP 必須過台灣中繼。
    輸出：date / m1b / m2 / m1b_m2_gap（M1B YoY − M2 YoY，pp）/ source / fetched_at。
    Tier 2（EF15M01，DL-f1-r1 起）的 m1b／m2 = 日平均餘額，單位新台幣百萬元
    （`shared.signal_thresholds.MONEY_SUPPLY_CACHE_UNIT_LABEL`）。
    """
    # token 參數忽略不用（CBC 不需要），但維持 signature 統一
    _ = token
    try:
        # v19.101 真因修正:原 `from proxy_helper import ...` / `from tw_macro import ...`
        # 是 v18.359 檔案搬家前的舊頂層路徑,根目錄 shim 已刪 → 本段自搬家起
        # 恆 ImportError → CBC 整段靜默跳過(2026-07-11 Actions run 實錘)。
        from src.data.proxy.proxy_helper import fetch_url as _fu_cbc  # noqa: F401
        from src.data.macro.tw_macro import CBC_MS1_URLS, fetch_cbc_ms1_rows
        from src.data.macro.tw_macro import CBC_EF15M01_URL   # DL-f1-r1：Tier 2 端點 SSOT
    except ImportError as e:
        # §1:印出真正缺什麼,不再吞成固定字串誤導診斷
        print(f"[finmind_m1m2] import 失敗,無法抓 CBC:{type(e).__name__}: {e}")
        return pd.DataFrame()
    # ── Tier 1: ms1.json（共用 tw_macro.CBC_MS1_URLS SSOT + fetch_cbc_ms1_rows kernel）──
    # v18.240：URL 清單從 tw_macro import，dead Attachment URL（v18.231 確認 404）已移除
    data = None
    for url in CBC_MS1_URLS:
        try:
            rows = fetch_cbc_ms1_rows(url, log_label='finmind_m1m2/ms1',
                                      timeout=15, attempts=2)
            if rows is not None:
                data = rows
                break
        except Exception as e:
            print(f"[finmind_m1m2/ms1] {url[-40:]} ❌ {type(e).__name__}: {e}")

    # ── Tier 2: CBC PXWeb EF15M01（貨幣總計數-日平均數；DL-f1-r1）──
    # **只請求一次**，M1B／M2 依標籤成對取「原始值」（= 餘額），並以表內官方年增率對帳。
    # EF19M01／EF21M01 是變動因素分析表、沒有餘額欄（run 36408641177 實測），不再請求。
    ef15, ef15_desc = None, ""
    if not isinstance(data, list) or len(data) < 13:
        r = _fu_cbc(CBC_EF15M01_URL, params={"FileName": _EF15_FILE}, timeout=20, attempts=2)
        if r is None or r.status_code != 200:
            print(f"[finmind_m1m2/{_EF15_FILE}] ❌ 無回應或非 200"
                  f"（status={getattr(r, 'status_code', None)}）")
        else:
            try:
                sdmx = r.json()
            except ValueError as e:
                print(f"[finmind_m1m2/{_EF15_FILE}] ❌ JSON 解析失敗 {type(e).__name__}: {e}"
                      f" body={r.text[:300]}")
            else:
                ef15, ef15_desc = _parse_cbc_ef15m01_levels(sdmx)

    if ef15 is not None:
        out = ef15[["date", "m1b", "m2"]].copy()
        _source = f"CBC:PXWeb:{_EF15_FILE}:daily_avg_level[{ef15_desc}]"
    else:
        if not isinstance(data, list) or len(data) < 13:
            print("[finmind_m1m2] CBC 全來源失敗")
            return pd.DataFrame()
        print(f"[finmind_m1m2] 抓到欄位：{list(pd.DataFrame(data).columns)[:15]}")

        df = pd.DataFrame(data)
        # 舊 ms1.json 路徑（已不再可用，留邏輯防禦）
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
        # 日期 normalize：支援 'YYYYMmm'（CBC PXWeb）/ 'YYYY-MM' / 'YYYY/MM' / 'YYYYMM'
        import re as _re
        def _norm(s):
            s = str(s).strip()
            m = _re.search(r"(20\d{2})\s*M\s*(\d{1,2})", s, _re.IGNORECASE)
            if m:
                return _dt.date(int(m.group(1)), int(m.group(2)), 1)
            m = _re.search(r"(20\d{2})[-/年]?(\d{1,2})", s)
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
        _source = "CBC:ms1.json"
    # M1B YoY − M2 YoY（黃金交叉指標）。算式不變；DL-f1-r1 起先補齊日曆月再 shift(12)，
    # t−12 一定是「同月去年」—— 月份被剔除（例：EF15M01 餘額為 "-"）時不會錯配成 t−13；
    # 月份連續時與原本的逐列 shift(12) 逐位相同。期間重複則無從對齊 → 拒寫（§1）。
    if out.empty:
        print("[finmind_m1m2] ❌ 無有效列（日期或數值全數無法解析）")
        return pd.DataFrame()
    if not out["date"].is_unique:
        _dup = out.loc[out["date"].duplicated(keep=False), "date"].astype(str).head(6).tolist()
        print(f"[finmind_m1m2] ❌ 期間重複,無法對齊 t−12 → 拒寫：{_dup}")
        return pd.DataFrame()
    _ts = pd.to_datetime(out["date"])
    _cal = (out[["m1b", "m2"]].set_index(_ts)
            .reindex(pd.date_range(_ts.min(), _ts.max(), freq="MS")))
    _gap = (_cal["m1b"] / _cal["m1b"].shift(12) - 1) * 100 - \
           (_cal["m2"] / _cal["m2"].shift(12) - 1) * 100
    out["m1b_m2_gap"] = _gap.reindex(_ts).to_numpy()
    out = out[(out["date"] >= start) & (out["date"] <= end)]
    print(f"[finmind_m1m2] ✅ CBC PXWeb {len(out)} rows")
    out = out[["date", "m1b", "m2", "m1b_m2_gap"]].copy()
    # B7b：寫檔前守門 —— 存量定義不過就整表拒寫（寧缺勿錯,§1）
    if not out.empty:
        _ok, _msg = _m1m2_level_sanity(out)
        if not _ok:
            print(f"[finmind_m1m2] ❌ sanity 不過,拒寫：{_msg}")
            return pd.DataFrame()
        print(f"[finmind_m1m2] sanity：{_msg}")
    # S-PROV-1 phase 14 v18.260 — provenance(schema-additive)
    if not out.empty:
        out["source"] = _source
        out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    return out


# ════════════════════════════════════════════════════════════════
# v18.176 Phase D：台灣 PMI 月頻 history（data.gov.tw dataset/6100）
# ════════════════════════════════════════════════════════════════
_DGTW_PMI_METADATA_URLS = (
    "https://data.gov.tw/api/v2/rest/dataset/6100",
    "https://data.gov.tw/api/v1/rest/dataset/6100",
    "https://data.gov.tw/dataset/6100/resource",
)
_PMI_DATE_KEYS = ("年月", "資料時間", "時間", "日期", "month", "date", "yearmonth")
_PMI_VALUE_KEYS = ("PMI", "採購經理", "製造業", "指數")


def _parse_pmi_csv_full(csv_text: str) -> pd.DataFrame:
    """全 CSV 解析 → [date YYYY-MM-01, pmi float] DataFrame；月頻保留全歷史。

    Sanity：PMI ∈ [20, 80]（中華經濟研究院實務範圍 30-65，留 ±15 緩衝）。
    """
    import csv as _csv
    import io as _io
    import re as _re_p
    _rdr = list(_csv.DictReader(_io.StringIO(csv_text)))
    if not _rdr:
        return pd.DataFrame(columns=["date", "pmi"])
    _rows: list[tuple[_dt.date, float]] = []
    for _row in _rdr:
        _date_v = None
        _pmi_v = None
        for _k, _v in _row.items():
            _kl = str(_k)
            # PMI 數值欄
            if any(_x in _kl for _x in _PMI_VALUE_KEYS):
                try:
                    _val = float(str(_v).strip().replace(",", ""))
                    if 20 <= _val <= 80:
                        _pmi_v = _val
                except (ValueError, TypeError):
                    pass
            # 日期欄
            if _date_v is None:
                _m = _re_p.search(r"(20\d{2}|19\d{2})[-/年]?(\d{1,2})", str(_v))
                if _m:
                    try:
                        _date_v = _dt.date(int(_m.group(1)), int(_m.group(2)), 1)
                    except ValueError:
                        pass
        if _date_v is not None and _pmi_v is not None:
            _rows.append((_date_v, _pmi_v))
    if not _rows:
        return pd.DataFrame(columns=["date", "pmi"])
    _df = pd.DataFrame(_rows, columns=["date", "pmi"]).drop_duplicates(
        subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    return _df


def fetch_tw_pmi_history(start: _dt.date, end: _dt.date) -> pd.DataFrame:
    """台灣製造業 PMI 月頻歷史（data.gov.tw dataset/6100 — 國發會 NDC 提供）。

    輸出欄位：[date, pmi]；月度資料量小（~300 月 / 25 年），每次 bootstrap 全 CSV
    無增量必要；caller 透過 `_merge_dedupe` 去重。
    """
    for _meta_url in _DGTW_PMI_METADATA_URLS:
        try:
            _r_meta = _fetch_url_via_proxy(_meta_url, timeout=10)
            if _r_meta is None or _r_meta.status_code != 200:
                print(f"[tw_pmi] metadata HTTP={getattr(_r_meta, 'status_code', 'None')}")
                continue
            try:
                _j_meta = _r_meta.json()
            except Exception as _e_json:
                print(f"[tw_pmi] metadata JSON parse fail: {_e_json}")
                continue
            # ── v19.122:cron 端補齊 `result.distribution`（v19.120 runtime 修正的另一半）──
            # v19.120 已在 runtime 端(`macro_core._pmi_src_dgtw`)把 6100 的**真實** shape
            # `result.distribution[]` 接回來(探針 run 33101596383:result.resources /
            # resources / data.resources 三者皆 None,**只有 result.distribution 有東西**),
            # 但**寫 metadata.json / parquet 的這條 cron 路徑當時沒跟上** → 候選鏈仍只有
            # 三種舊 shape → `_res` 恆空 → 走下面那條 continue。實證:本次修正前
            # `data_cache/metadata.json` 的 `datasets.tw_pmi` 一直是
            # {"last_updated": null, "row_count": 0, "last_error": "抓取結果為空"}。
            # ⚠️ **順序必須與 macro_core 逐字一致**:兩邊都是
            #    result.resources → resources → **result.distribution** → data.resources。
            #    `or` 鏈是**短路取第一個非空**,順序不同 ⇒ 同一份 metadata 若同時有兩種
            #    shape,runtime 與 cron 會挑到**不同的 resource 清單** —— 那會變成
            #    「畫面對、存檔錯」這種最難查的分岔。順序同步鎖見
            #    `tests/test_dgtw_pmi_cron_shape_v19_122.py::TestShapeChainParity`。
            _res = (_j_meta.get("result", {}).get("resources")
                    or _j_meta.get("resources")
                    or _j_meta.get("result", {}).get("distribution")
                    or _j_meta.get("data", {}).get("resources")
                    or [])
            if not _res:
                # 原為靜默 continue —— 200 但 metadata 無 resources 陣列時無痕
                print(f"[tw_pmi] metadata 200 但無 resources"
                      f"（keys={list(_j_meta)[:8]}）url=…{_meta_url[-24:]}")
                continue
            # ── 雙重 gate 移除（同步 macro_core._pmi_src_dgtw 的 v19.114 修正）──
            # 舊碼:「format in (CSV, JSON)」+ 只取第一個命中 → 6100 的**唯一** resource
            # 是 `https://ws.ndc.gov.tw/Download.ashx?u=…`,**format 欄根本不存在**
            # (探針 run 29227373503 section C 印出 `[?]` = `it.get('format','?')` 取到
            #  預設值)、URL 也無 'csv' 字樣,但內容是合法 CSV:
            #      `Date,PMI,NMI / 201207,47.1,- / … / 202606,60.7,-`（HTTP 200, 2881 bytes）
            # → 這條**活 CSV 從未被解析**,`_csv_url` 恆 None、靜默 continue,
            #   metadata.json 因此長期 `row_count: 0 / last_error: "抓取結果為空"`。
            #   v19.114 已在 runtime 端(`macro_core._pmi_src_dgtw`)修掉,但 cron 這一份
            #   （= 寫 metadata.json / parquet 的那條路徑）當時未同步 → 本次補上。
            # 改法同 runtime:收**所有** resource url(宣告 CSV 者排前),逐一下載後交
            # `_parse_pmi_csv_full` 靠**內容**判斷,不靠 URL 副檔名 / format 欄。
            _urls: list[str] = []
            for _it in _res:
                _url2 = (_it.get("url") or _it.get("resourceDownloadUrl")
                         or _it.get("downloadUrl"))
                if not _url2:
                    continue
                # v19.122:同上,補 `resourceFormat`。實測 6100 的 distribution item
                # 用的是 `resourceFormat`(完整 key 集見探針 run 33101596383),舊碼只看
                # `format` → 恆為空字串 → CSV 永遠排不到前面。**只影響順序不影響正確性**
                # (下載後一律交 `_parse_pmi_csv_full` 靠內容判斷),但多資源時會白跑,
                # 且與 runtime 端行為不一致,一併補齊。
                if str(_it.get("format")
                       or _it.get("resourceFormat") or "").upper() == "CSV":
                    _urls.insert(0, _url2)
                else:
                    _urls.append(_url2)
            if not _urls:
                print(f"[tw_pmi] resources×{len(_res)} 但無任何可下載 url")
                continue
            for _res_url in _urls:
                _r_csv = _fetch_url_via_proxy(_res_url, timeout=15)
                if _r_csv is None or _r_csv.status_code != 200:
                    print(f"[tw_pmi] resource HTTP="
                          f"{getattr(_r_csv, 'status_code', 'None')} url=…{_res_url[-40:]}")
                    continue
                _txt = _r_csv.content.decode("utf-8-sig", errors="ignore")
                _df = _parse_pmi_csv_full(_txt)
                if _df.empty:
                    print(f"[tw_pmi] 解析後無有效列（{len(_r_csv.content)} bytes）"
                          f"url=…{_res_url[-40:]}")
                    continue
                _df = _df[(_df["date"] >= start) & (_df["date"] <= end)].reset_index(drop=True)
                print(f"[tw_pmi] ✅ data.gov.tw {len(_df)} rows ({start}~{end})")
                # S-PROV-1 phase 14 v18.260 — provenance(schema-additive)
                if not _df.empty:
                    _df["source"] = "data.gov.tw:dataset:6100"
                    _df["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return _df
        except Exception as _e_outer:
            print(f"[tw_pmi] outer {type(_e_outer).__name__}: {_e_outer}")
    print("[tw_pmi] ❌ 所有 dgtw metadata URL 皆失敗")
    return pd.DataFrame(columns=["date", "pmi"])


# B7b：既有 Parquet 的定義守門（name → fn(df) -> (ok, msg)）。不過 → update_one 整段重建。
_EXISTING_SANITY_GATES = {
    "finmind_m1m2": _m1m2_level_sanity,
}

FETCHERS = {
    "twii_ohlcv": (fetch_twii_ohlcv, False),       # (fn, needs_token)
    "finmind_inst": (fetch_finmind_inst, True),
    "finmind_margin": (fetch_finmind_margin, True),
    "finmind_m1m2": (fetch_finmind_m1m2, True),
    "tw_pmi": (fetch_tw_pmi_history, False),       # v18.176 Phase D PMI Parquet
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
    # B7b：既有歷史若違反該表的定義守門（例：m1m2 存了流量）→ 不得在壞歷史上增量
    # 疊加（會產出「新舊兩種量混在一張表」）；改整段重抓，成功才整檔取代。
    _corrupt_existing = None
    _gate = _EXISTING_SANITY_GATES.get(name)
    if _gate is not None and existing is not None and not existing.empty:
        _ok_ex, _msg_ex = _gate(existing)
        if not _ok_ex:
            print(f"[{name}] ⚠️ 既有檔 sanity 不過（{_msg_ex}）→ 改整段重建")
            _corrupt_existing, existing = existing, None
            bootstrap = True
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
        if _corrupt_existing is not None:
            # 重建途中拋例外：壞檔原樣保留，metadata 誠實標壞
            meta["last_error"] += "；既有檔 sanity 不過,待重建"
            meta["row_count"] = len(_corrupt_existing)
        print(f"[{name}] ❌ {meta['last_error']}")
        return meta

    if new.empty:
        meta["last_error"] = "抓取結果為空"
        if _corrupt_existing is not None:
            # 重建失敗：壞檔原樣保留（不刪、不回填），但 metadata 誠實標壞,不假裝最新
            meta["last_error"] = "抓取結果為空；既有檔 sanity 不過,待重建"
            meta["row_count"] = len(_corrupt_existing)
            print(f"[{name}] ⚠️ 重建失敗，既有（已知不合格）檔原樣保留")
            return meta
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
    p.add_argument("--years", type=int, default=20,
                   help="歷史長度（bootstrap / 缺檔時用，預設 20）")
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

    # v19.118：durable「上次已知值」快照 — 抓成功即存 data_cache/macro_last_good/，
    # 供 Streamlit Cloud 即時全敗時讀（撐過雲端 container recycle;cache/ ephemeral 撐不過）。
    # 只存 **live hit**，**不回存 stale fallback**（否則 cached_at 被每日重刷 → 過期值假裝
    # 永遠新鮮，違 §1）。跑 runtime 同一個 fetch_tw_pmi()（8 源賽跑）確保 shape 一致。
    try:
        from src.data.macro.macro_core import (
            fetch_tw_pmi as _rt_fetch_pmi, _macro_durable_save)
        _pmi_now = _rt_fetch_pmi()
        if _pmi_now.get("value") is not None and not _pmi_now.get("is_stale"):
            _macro_durable_save("tw_pmi", _pmi_now)
            print(f"✅ durable PMI 快照更新 → value={_pmi_now['value']} "
                  f"date={_pmi_now.get('date')} source={_pmi_now.get('source')}")
        else:
            print(f"⚠️ PMI live 未取得（value={_pmi_now.get('value')}, "
                  f"stale={_pmi_now.get('is_stale')}）→ 保留既有 durable 快照，不覆寫")
    except Exception as _e_pmi_dur:
        print(f"⚠️ durable PMI 快照步驟失敗（不影響其他 dataset）："
              f"{type(_e_pmi_dur).__name__}: {_e_pmi_dur}")

    # 任何 fatal error 計入退碼，但仍維持 0 讓 workflow 不爆掉（部分失敗仍 commit 成功部分）
    err_count = sum(1 for m in metadata.values() if m.get("last_error"))
    if err_count:
        print(f"⚠️ {err_count}/{len(metadata)} dataset 有錯誤，請查上方 log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
