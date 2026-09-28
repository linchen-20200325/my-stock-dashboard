"""update_macro_history.py — GitHub Actions 排程：抓總經歷史資料增量到 data_cache/。

資料流（與 update_etf_managers.py 同模式，但抓多個 dataset）
=========================================================
data_cache/twii_ohlcv.parquet              ← ^TWII 日 K（yfinance via NAS proxy）
data_cache/finmind_inst.parquet            ← 三大法人總買賣超（FinMind）
data_cache/finmind_margin.parquet          ← 融資餘額（FinMind）
data_cache/finmind_m1m2.parquet            ← M1B／M2 餘額 ＋ M1B 年增率 − M2 年增率（CBC；FinMind 無此資料，
                                             表名 finmind_ 為歷史沿用；細節見下）
data_cache/tw_pmi.parquet                  ← 台灣製造業 PMI 月頻（data.gov.tw dataset/6100，國發會提供）
data_cache/metadata.json                   ← 各表 last_updated + row_count

finmind_m1m2（`fetch_finmind_m1m2`）欄位：date（資料月月初）／m1b／m2／m1b_m2_gap／source／fetched_at
- 寫出的列只來自 CBC PXWeb EF15M01（貨幣總計數-日平均數），每次都請求；source 欄
  `CBC:PXWeb:EF15M01:daily_avg_level[…]`（DL-f1-s40）。
- CBC ms1.json（`tw_macro.CBC_MS1_URLS`；程式內註記「已不再可用，留邏輯防禦」）仍先請求，但只做形狀與
  量級檢查、結果只進 log，**不寫出**：它沒有標題／單位 meta，口徑（日平均或月底）無從驗證，而不同
  來源／口徑的列不得疊進同一份 parquet（DL-f1-s40）。EF15M01 失敗 → 本輪不寫，不以 ms1 替代。
- m1b／m2 = 日平均餘額，新台幣百萬元（int64）；解析、單位檢查與官方年增率對帳見
  `src/data/macro/cbc_ef15m01.py`；寫檔前守門 `_m1m2_level_sanity` 另有百萬元量級帶（任何來源都要過）。
- m1b_m2_gap = M1B 年增率 − M2 年增率（pp），由 m1b／m2 餘額以同月去年自算。

每日跑一次（TW 17:00 收盤後）
- 對每個 Parquet：讀取 last_date → 抓 [last_date+1, today] → append + dedupe → 寫回
- 走 proxy_helper.fetch_url（NAS Squid → 直連 → NAS 中繼站 fallback）解海外 IP 封鎖
- 任一資料源失敗：log 警告但不中止；metadata 記 last_error 供後續排查

刻意維持「無 streamlit 相依」（與 update_etf_managers.py 同款），
在 Actions runner 上 pip install -r requirements.txt 即可跑。

CLI（在 repo 根目錄執行 —— `CACHE_DIR` 是相對路徑 `data_cache/`；排程 workflow 也是這樣跑）
===
    python scripts/update_macro_history.py                      # 增量更新（DATASETS 全部）
    python scripts/update_macro_history.py --bootstrap          # 不讀既有檔、整段重抓，抓到才整檔覆寫（初次部署用）
    python scripts/update_macro_history.py --years 10           # 歷史長度（預設 20）：bootstrap、無既有資料、
                                                                #   或既有檔守門不過而整段重建時用
    python scripts/update_macro_history.py --only finmind_m1m2  # 只跑指定 dataset（debug 用，逗號分隔多個）
⚠️ --only：metadata.json 只寫本次有跑的表（整檔覆寫，沒跑的表的紀錄不保留）；未註冊的名稱印
   「[main] 未知 dataset」後略過；PMI durable 快照步驟（`main()` 末段）不受 --only 限制，照跑。
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
    """外資淨買賣超（FinMind TaiwanStockTotalInstitutionalInvestors；只取外資，投信、自營商不取）。

    輸出欄位：date、foreign_buy（億元，外資淨買賣超）、source、fetched_at。
    FinMind 實際欄位：['buy', 'date', 'name', 'sell']（buy／sell 單位：元）。`name` 是英文投資人類型；
    篩含 'Foreign' 的列（外資總額 = Foreign_Investor ＋ Foreign_Dealer_Self），每列 buy − sell，
    依日加總後 ÷ `TWD_PER_YI` 換成億元。

    DL-f1-s43（2026-09-28）：原本 buy／sell 先 `fillna(0)` 再相減（違 CLAUDE.md §1）—— sell 缺值時
    當日淨額被捏成大正數、buy 缺值時捏成大負數；缺整欄時 `fi.get()` 回 None → AttributeError。改為：
    - 缺 date／buy／sell 欄 → raise（`update_one` 接住 → metadata 記 last_error、既有檔原封不動）。
      上游 schema 漂移是系統性問題；回空表會被記成「抓取結果為空」，讀取端會當成「沒有新資料」。
    - 某日任一外資組成列的 buy 或 sell 缺值（含轉不成數值）→ **該日整日不產出**（不以 0 代入、
      不做部分加總），log 剔除的日期數與樣本；其餘日子的算式、輸出逐位不變。
    - ⚠️ 某日「根本沒有」某一組成列（例：只有 Foreign_Investor）不在此列，照舊以有的列加總 ——
      這不是缺值；若也剔除，會連帶改掉有值日子的輸出。
    """
    from shared.margin_schema import TWD_PER_YI

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
    _missing = [c for c in ("date", "buy", "sell") if c not in fi.columns]
    if _missing:
        raise RuntimeError(
            f"缺欄 {_missing}（欄位={list(raw.columns)}）→ 算不出外資淨買賣超；"
            "不寫入 parquet（§1：不以 0 代入、不猜欄位）")
    fi = fi.copy()
    _buy = pd.to_numeric(fi["buy"], errors="coerce")
    _sell = pd.to_numeric(fi["sell"], errors="coerce")
    fi["foreign_buy"] = (_buy - _sell) / TWD_PER_YI      # 缺值列 → NaN（不以 0 代入）
    _nan_rows = _buy.isna() | _sell.isna()
    if _nan_rows.any():
        # §1／§3.3：顯式剔除 + log 筆數。整日剔除：只加有值的列 = 產出一個「部分加總」，比缺席更危險。
        _bad_days = pd.unique(fi.loc[_nan_rows, "date"])
        print(f"[finmind_inst] ⚠️ 剔除 {len(_bad_days)} 個日期（該日有外資組成列 buy 或 sell 缺值"
              f" → 整日不產出；不以 0 代入、不做部分加總），{int(_nan_rows.sum())} 列缺值"
              f"（樣本日期={sorted(str(d) for d in _bad_days)[:5]}）")
        fi = fi[~fi["date"].isin(_bad_days)]
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
# B7b（2026-09-27）→ DL-f1-r1（2026-09-28）：M1B／M2「存量 vs 流量」
# ════════════════════════════════════════════════════════════════
# 根因：舊解析寫死「row[1] = 主數值」，但 EF19M01／EF21M01 的 row[1] 實測是
# **月變動額（流量）**—— 2026-09-24 cron 整檔重抓後 238 列仍有 87 列 M1B 或 M2
# 為負（貨幣供給額是存量，不可能為負）。再對會變號的序列算 YoY → gap ∈ ±13,976。
# B7b 改以欄位標籤／存量定義辨識餘額欄、辨識不出就 fail loud —— 判定本身正確，但
# run 36408641177 實測 EF19M01／EF21M01 是「變動因素分析」表、**根本沒有餘額欄**，
# 整段重建因此天天失敗。DL-f1-r1 改取 EF15M01（見下方 `_parse_cbc_ef15m01_levels`），
# B7b 的欄位辨識解析器與其專用 helper 隨之成為 0 caller，已於同批 QA 修正時刪除
# （逐一列在該 commit 訊息）。本段原保留兩個仍在用的函式：
#   - `_cbc_norm_label`：標籤正規化 —— DL-f1-s1（2026-09-28）起隨 EF15M01 解析器搬到
#     `src/data/macro/cbc_ef15m01.py`（公開名 `cbc_norm_label`），本檔舊名仍可 import（見下段）；
#   - `_m1m2_level_sanity`：寫檔前最後守門（與 `export_stock_db._money_supply_sanity_gate`
#     同一組定義常數），也判定既有檔是否需整段重建 —— 不過就整表拒寫（§1 寧缺勿錯）。


def _m1m2_level_band() -> tuple[float, float]:
    """本表 m1b／m2 的單位量級帶（新台幣百萬元，閉區間）→ (下界, 上界)。

    DL-f1-s40：**不另訂數值** —— 沿用匯出端的億元量級帶常數
    `shared.signal_thresholds.MONEY_SUPPLY_LEVEL_SANITY_MIN_YI`／`_MAX_YI`（帶寬推導見該常數），
    換成本表契約單位 `MONEY_SUPPLY_CACHE_UNIT_LABEL`（百萬元）：× `TWD_PER_YI`（1e8）
    ÷ `MONEY_SUPPLY_TWD_PER_CACHE_UNIT`（1e6）＝ ×100 ⇒ [1e6, 5e8] 百萬元。
    """
    from shared.margin_schema import TWD_PER_YI
    from shared.signal_thresholds import (
        MONEY_SUPPLY_LEVEL_SANITY_MAX_YI,
        MONEY_SUPPLY_LEVEL_SANITY_MIN_YI,
        MONEY_SUPPLY_TWD_PER_CACHE_UNIT,
    )
    _to_unit = TWD_PER_YI / MONEY_SUPPLY_TWD_PER_CACHE_UNIT          # 億元 → 百萬元（= 100）
    return (MONEY_SUPPLY_LEVEL_SANITY_MIN_YI * _to_unit,
            MONEY_SUPPLY_LEVEL_SANITY_MAX_YI * _to_unit)


def _m1m2_level_sanity(df: pd.DataFrame) -> tuple[bool, str]:
    """寫檔前守門（整表判定,不逐列剔除）。四條檢查同 `export_stock_db._money_supply_sanity_gate`：
    ① 餘額 > 0 ② m2 ≥ m1b ③ |gap| ≤ 30pp ④ m1b／m2 落在單位量級帶內（本表以百萬元訂界，
    見 `_m1m2_level_band`；匯出端吃的是換成億元的表，同一組常數）。

    ④ 是 DL-f1-s40（2026-09-28）補的。原文「（DL-f1-r1：匯出端另有『億元量級帶』—— 那是換算後的
    單位檢查,本檔 parquet 為百萬元,單位改由 `_parse_cbc_ef15m01_levels` 比對回應 `meta.units` 把關,
    不在此重複。）」只對 EF15M01 那一支成立：ms1.json 分支沒有 meta、不比對單位，億元資料原本會一路
    放行，到匯出端才被量級帶擋下（整張 `money_supply` 被 DROP，parquet 本身不會自癒）。寫檔前的最後
    一道守門不能假設資料來自哪一支 ⇒ 任何來源都過同一條量級帶。
    本函式同時是既有檔守門（`_EXISTING_SANITY_GATES`）⇒ 既有 parquet 混進量級不符的列 → 下一次排程
    整段重建。餘額為 NaN 也判帶外（`between` 對 NaN 為 False；① ② 對 NaN 原本都判通過）。

    ⚠️ 量級帶只攔得住「差 100 倍以上」的單位錯。億元資料被當成百萬元時，值 = 真值（元）÷ 1e8，要真值
    < 100 兆元才會落到下界（1e6）之下：2026-07 M2 約 70.2 兆元（EF15M01），以年增 7% 估約 5 年後破
    100 兆，屆時單靠本帶攔不住 M2 的億元列（M1B 約 30.5 兆元，餘裕較大）。本表另一道防線是「寫入的列
    只來自 EF15M01」（`fetch_finmind_m1m2`，DL-f1-s40）。"""
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
    _lo, _hi = _m1m2_level_band()
    _mag = ~(df["m1b"].between(_lo, _hi) & df["m2"].between(_lo, _hi))
    bad = _lv | _ord | _gap | _mag
    if not bad.any():
        return True, f"{len(df)} 列通過"
    return False, (f"{int(bad.sum())}/{len(df)} 列不合格（餘額≤0:{int(_lv.sum())}、"
                   f"m2<m1b:{int(_ord.sum())}、|gap|>{M1B_M2_GAP_SANITY_ABS_MAX_PP:.0f}pp:"
                   f"{int(_gap.sum())}、百萬元量級帶外 [{_lo:.0e}, {_hi:.0e}]:{int(_mag.sum())}）"
                   f"→ 疑似月變動額而非餘額、或單位不是百萬元")


# ════════════════════════════════════════════════════════════════
# DL-f1-r1（2026-09-28）：M1B／M2 餘額改取 CBC EF15M01（貨幣總計數-日平均數）
# DL-f1-s1（2026-09-28）：解析本體搬到 L1 共用模組 `src/data/macro/cbc_ef15m01.py`
# ════════════════════════════════════════════════════════════════
# 根因（GitHub Actions run 36408641177 實測）：EF19M01／EF21M01 是「貨幣供給額 M1B／M2
# **變動因素分析**」表 —— 每一欄都是變動額（流量），根本沒有餘額欄；B7b 的欄位辨識解析器
# （已刪除，見上段）正確地拒絕它們，於是每天排程的整段重建都失敗。同一個 API 的 EF15M01 才有餘額。
# 回應形狀與解析規則（依標籤成對、NFKC 完整序列名、單位／標題檢查、"-" 為缺值、官方年增率對帳
# 與「致命範圍」）原文隨解析器搬進 `src/data/macro/cbc_ef15m01.py` 的模組 docstring，
# **本檔不再重述** —— 同一條規則寫在兩處遲早分岔（§2.1）。
#
# DL-f1-s1 為何搬：線上 `tw_macro._try_cbc_ef15m01` 仍讀頂層 `DataSet`／`Structure`（舊格式）
# → 恆回 None → 線上 M1B／M2 落到 Tier 3 `^TWII` 動能代理。修法是讓兩條路徑共吃同一個解析器，
# 不是在 tw_macro 再寫第二套。
#
# 本檔保留舊名（re-export），既有測試與呼叫端一字不改：
#   - `_parse_cbc_ef15m01_levels`：薄轉接 —— 診斷前綴維持 `[finmind_m1m2/EF15M01]`、只回
#     date／m1b／m2 三欄（共用解析器另帶官方年增率兩欄，給線上路徑用）→ 回傳與搬移前相同；
#   - `_ef15_cell`：薄轉接，且是 `_parse_cbc_ef15m01_levels` 的單格解析注入點
#     （`test_mq3_reconcile_comparison_is_nan_safe` 在本檔命名空間替換它，必須對解析生效）；
#   - 其餘舊名（`_EF15_*` 常數、`_cbc_norm_label`、`_ef15_yoy_tolerance_pp`、`_ef15_labels`、
#     `_ef15_fatal_from`）經下方 PEP 562 `__getattr__` 延遲轉發。
# ⚠️ 為何一律「用到才 import」、不放檔頭：本腳本對 `src.*` 一律延遲 import，單一 dataset 的
#    import 失敗只讓該 dataset 失敗（見 `fetch_finmind_m1m2` 的 ImportError 分支、v19.101 病史）；
#    `src.data.macro` 套件一被 import 就 eager 載入 5 個子模組，放檔頭會把它的故障半徑擴大到
#    整支腳本（連 twii／法人／融資／PMI 都跑不了）。
_EF15_REEXPORTS = {                       # 本檔舊名 → `src.data.macro.cbc_ef15m01` 公開名
    "_EF15_FILE": "EF15_FILE",
    "_EF15_TITLE_KEY": "EF15_TITLE_KEY",
    "_EF15_SERIES": "EF15_SERIES",
    "_EF15_MEASURE_LEVEL": "EF15_MEASURE_LEVEL",
    "_EF15_MEASURE_YOY": "EF15_MEASURE_YOY",
    "_EF15_UNIT_YOY": "EF15_UNIT_YOY",
    "_EF15_MISSING": "EF15_MISSING",
    "_EF15_PERIOD_RE": "EF15_PERIOD_RE",
    "_EF15_YOY_DECIMALS": "EF15_YOY_DECIMALS",
    "_EF15_LEVEL_STEP": "EF15_LEVEL_STEP",
    "_EF15_FLOAT_EPS_PP": "EF15_FLOAT_EPS_PP",
    "_cbc_norm_label": "cbc_norm_label",
    "_ef15_yoy_tolerance_pp": "ef15_yoy_tolerance_pp",
    "_ef15_labels": "ef15_labels",
    "_ef15_fatal_from": "ef15_fatal_from",
}


def __getattr__(name: str):
    """PEP 562：EF15M01 舊名延遲轉發到 `src.data.macro.cbc_ef15m01`（DL-f1-s1，見上段）。

    只管 `_EF15_REEXPORTS` 列出的名字；其他名字照常拋 AttributeError。
    ⚠️ 模組內的函式以裸名稱取全域變數時**不會**經過這裡（Python 的全域查找不呼叫
    `__getattr__`）—— 所以本檔自己的函式一律直接 import 共用模組，不引用這些舊名。"""
    _target = _EF15_REEXPORTS.get(name)
    if _target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from src.data.macro import cbc_ef15m01 as _ef15
    return getattr(_ef15, _target)


def _ef15_cell(v):
    """（DL-f1-s1 re-export）值欄字串 → float；"-" → None；其餘解析不了 → ValueError。

    實作見 `src.data.macro.cbc_ef15m01.ef15_cell`。寫成本檔的函式、而非經 `__getattr__` 轉發，
    是因為 `_parse_cbc_ef15m01_levels` 以本檔全域名稱取它當單格解析函式（注入點，見上段）。"""
    from src.data.macro.cbc_ef15m01 import ef15_cell
    return ef15_cell(v)


def _parse_cbc_ef15m01_levels(sdmx, fatal_from: _dt.date | None = None
                              ) -> tuple[pd.DataFrame | None, str]:
    """CBC EF15M01 回應 → (DataFrame[date, m1b, m2], 說明) 或 (None, 拒用原因)。

    DL-f1-s1 起為薄轉接：解析、驗證、對帳全部由 `src.data.macro.cbc_ef15m01.parse_cbc_ef15m01`
    執行（SSOT；規則見該模組 docstring）。本函式只做兩件事 ——
    (1) 診斷前綴維持 `[finmind_m1m2/EF15M01]`；(2) 只回 date／m1b／m2 三欄（與搬移前的回傳相同）。
    date = 資料月月初（datetime.date）；m1b／m2 = 日平均餘額，單位新台幣百萬元，int64。

    `fatal_from`：對帳「致命範圍」的第一個資料月（fetch 以 `ef15_fatal_from(start)` 傳入）。
    d ≥ fatal_from 的列對帳不符 → 整表拒用；更早的列不符 → 只印 ⚠️。
    None = 全表都是致命範圍（最嚴；直接呼叫本函式時的預設）。
    ⚠️ 只有「對帳不符」分範圍；格式錯誤（期間、欄數、無法解析的值、非整數餘額）一律整表拒用。
    """
    from src.data.macro.cbc_ef15m01 import EF15_FILE, parse_cbc_ef15m01
    df, desc = parse_cbc_ef15m01(sdmx, fatal_from, log_tag=f"[finmind_m1m2/{EF15_FILE}]",
                                 cell=_ef15_cell)
    if df is None:
        return None, desc
    return df[["date", "m1b", "m2"]], desc


def _m1m2_ms1_candidate(data) -> tuple[pd.DataFrame | None, str]:
    """Tier 1 ms1.json 的回應 → (DataFrame[date, m1b, m2], 說明) 或 (None, 不採用原因)。

    DL-f1-s40：**結果只進 log，不進 parquet**（理由見 `fetch_finmind_m1m2`）。依序檢查：
    ① 是 ≥ 13 列的 list；② 形狀：辨識得出 M1B、M2 與日期三欄；③ 解析後至少一列；
    ④ 單位量級：m1b／m2 全落在 `_m1m2_level_band`（百萬元）內。
    ②③ 的欄位辨識、日期正規化、去千分位逐字沿用原 ms1 分支（原本寫在 `fetch_finmind_m1m2` 內）。
    ms1 沒有標題／單位 meta：④ 通過只代表「量級像百萬元」，**口徑（日平均或月底）無從驗證**。
    """
    if not isinstance(data, list) or len(data) < 13:
        _n = len(data) if isinstance(data, list) else "—"
        return None, f"回應不是 ≥ 13 列的 list（{type(data).__name__}，{_n} 列）"
    df = pd.DataFrame(data)
    c1 = next((c for c in df.columns
               if "M1B" in str(c).upper() or "貨幣供給額M1B" in str(c)), None)
    c2 = next((c for c in df.columns
               if str(c).strip().upper() == "M2" or "貨幣供給額M2" in str(c)), None)
    date_col = next((c for c in df.columns
                     if str(c).strip() in ("年月", "date", "yearMonth", "Date",
                                            "PERIOD", "TIME_PERIOD")), None)
    if not (c1 and c2 and date_col):
        return None, f"形狀不符：欄位對應失敗（欄位={list(df.columns)[:15]}）"
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
    if out.empty:
        return None, "日期或數值全數無法解析"
    _lo, _hi = _m1m2_level_band()
    _off = ~(out["m1b"].between(_lo, _hi) & out["m2"].between(_lo, _hi))
    if _off.any():
        _s = out.loc[_off, ["date", "m1b", "m2"]].head(3)
        return None, (f"量級不符：{int(_off.sum())}/{len(out)} 列 m1b／m2 不在百萬元量級帶 "
                      f"[{_lo:.0e}, {_hi:.0e}]（疑似單位不是百萬元；樣本={_s.to_dict('records')}）")
    return out, (f"形狀與百萬元量級皆通過（{len(out)} 列，"
                 f"{out['date'].iloc[0]:%Y-%m}～{out['date'].iloc[-1]:%Y-%m}）")


def fetch_finmind_m1m2(start: _dt.date, end: _dt.date, token: str = "") -> pd.DataFrame:
    """M1B / M2 月頻（CBC 中央銀行；FinMind 無對應 dataset，表名為歷史沿用）。

    走 proxy_helper.fetch_url（PROXY_URL）→ CBC 擋海外 IP 必須過台灣中繼。
    輸出：date / m1b / m2 / m1b_m2_gap（M1B YoY − M2 YoY，pp）/ source / fetched_at。
    m1b／m2 = EF15M01 日平均餘額，單位新台幣百萬元
    （`shared.signal_thresholds.MONEY_SUPPLY_CACHE_UNIT_LABEL`）。

    DL-f1-s40（2026-09-28）：寫出的列**只來自 EF15M01**，且每次都請求它。
    原本 Tier 1 ms1.json 只要回 ≥ 13 列就直接寫出、不再請求 EF15M01 —— ms1 分支不驗單位量級，也沒有
    標題／單位 meta 可驗口徑；它一旦復活，切換就自動、靜默發生：單位不同 → 匯出端量級帶擋下、整張
    `money_supply` 被 DROP；單位相同但口徑不同（月底 vs 日平均，約差 3%）→ 靜默混口徑；ms1 欄位形狀
    一變則直接回空表、不退到 EF15M01。現行 parquet 的列全出自 EF15M01（2026-09-28 main 237 列），
    不同來源／口徑的列不得疊進同一份 parquet ⇒ ms1 **不寫出**。它仍照舊先請求（`tw_macro.CBC_MS1_URLS`），
    由 `_m1m2_ms1_candidate` 做形狀與量級檢查，結果只進 log（它若復活，log 看得出它長什麼樣）；
    ms1 失敗、形狀不符、量級不符、或通過檢查 → 一律接著請求 EF15M01（不再回空表）。
    EF15M01 失敗 → 回空表（`update_one` 保留既有檔、記 last_error），不以 ms1 替代。
    寫檔前守門 `_m1m2_level_sanity` 另含百萬元量級帶（任何來源都要過）。

    `token`：不使用（CBC 不需要 FinMind token）。DL-f1-s9 起 `FETCHERS` 標 needs_token=False，
    `update_one` 以 `fn(start, end)` 兩參數呼叫 → 本參數改為選填（預設空字串）；
    保留它只為相容既有的三參數呼叫端（`fetch_finmind_m1m2(start, end, "")`）。
    """
    _ = token   # 不使用（見 docstring）
    try:
        # v19.101 真因修正:原 `from proxy_helper import ...` / `from tw_macro import ...`
        # 是 v18.359 檔案搬家前的舊頂層路徑,根目錄 shim 已刪 → 本段自搬家起
        # 恆 ImportError → CBC 整段靜默跳過(2026-07-11 Actions run 實錘)。
        from src.data.proxy.proxy_helper import fetch_url as _fu_cbc  # noqa: F401
        from src.data.macro.tw_macro import CBC_MS1_URLS, fetch_cbc_ms1_rows
        from src.data.macro.tw_macro import CBC_EF15M01_URL   # DL-f1-r1：Tier 2 端點 SSOT
        # DL-f1-s1：EF15M01 解析 SSOT（與線上 tw_macro Tier 2 共用；舊名見本檔 re-export 段）
        from src.data.macro.cbc_ef15m01 import (EF15_FILE as _EF15_FILE,
                                                ef15_fatal_from as _ef15_fatal_from)
    except ImportError as e:
        # §1:印出真正缺什麼,不再吞成固定字串誤導診斷
        print(f"[finmind_m1m2] import 失敗,無法抓 CBC:{type(e).__name__}: {e}")
        return pd.DataFrame()
    # ── Tier 1: ms1.json（共用 tw_macro.CBC_MS1_URLS SSOT + fetch_cbc_ms1_rows kernel）──
    # v18.240：URL 清單從 tw_macro import，dead Attachment URL（v18.231 確認 404）已移除
    # DL-f1-s40：只檢查、只進 log，**不寫出**（理由見 docstring）；不論結果如何都接著請求 EF15M01。
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
    if data is not None:
        try:
            _ms1, _ms1_why = _m1m2_ms1_candidate(data)
        except Exception as e:  # noqa: BLE001 — 外部回應解析不了不得擋住 EF15M01（DL-f1-s40）；原因照印
            _ms1, _ms1_why = None, f"解析例外 {type(e).__name__}: {e}"
        if _ms1 is None:
            print(f"[finmind_m1m2/ms1] ❌ 不採用：{_ms1_why} → 改取 {_EF15_FILE}")
        else:
            print(f"[finmind_m1m2/ms1] ⚠️ {_ms1_why}；仍不寫出 —— 本表的列只收 {_EF15_FILE}"
                  "（日平均餘額、百萬元），ms1 沒有標題／單位 meta、口徑無從驗證，"
                  f"不同來源／口徑不得疊進同一份 parquet（DL-f1-s40）→ 改取 {_EF15_FILE}")

    # ── Tier 2: CBC PXWeb EF15M01（貨幣總計數-日平均數；DL-f1-r1；DL-f1-s40 起每次都請求）──
    # **只請求一次**，M1B／M2 依標籤成對取「原始值」（= 餘額），並以表內官方年增率對帳。
    # EF19M01／EF21M01 是變動因素分析表、沒有餘額欄（run 36408641177 實測），不再請求。
    ef15, ef15_desc = None, ""
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
            # 對帳的致命範圍 = 寫入窗口 ＋ gap 的 t−12 基期（更早的列只警示，
            # 見 `src/data/macro/cbc_ef15m01.py` 模組 docstring）
            ef15, ef15_desc = _parse_cbc_ef15m01_levels(
                sdmx, fatal_from=_ef15_fatal_from(start))

    if ef15 is None:
        print(f"[finmind_m1m2] ❌ {_EF15_FILE} 無可用資料 → 本輪不寫出"
              "（ms1 不作替代來源，DL-f1-s40）")
        return pd.DataFrame()
    out = ef15[["date", "m1b", "m2"]].copy()
    _source = f"CBC:PXWeb:{_EF15_FILE}:daily_avg_level[{ef15_desc}]"
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
    # DL-f1-s25：印實際來源（= 下方寫進 source 欄的同一個值）。原本寫死「CBC PXWeb」，
    # 走 ms1.json 或 EF15M01 都印同一句。
    print(f"[finmind_m1m2] ✅ {_source} {len(out)} rows")
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
    # DL-f1-s9：資料來自 CBC、不需要 FinMind token（表名 finmind_ 為歷史沿用）→ False。
    # 原標 True：沒有 token 的執行會把本表白白跳過。update_one 對 False 以 fn(start, end) 呼叫
    # —— `fetch_finmind_m1m2` 的 token 參數已改為選填，不會 TypeError。
    "finmind_m1m2": (fetch_finmind_m1m2, False),
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
        from shared.staleness import EMPTY_FETCH_MARKER  # DL-f1-s6：與讀取端共用同一常數
        meta["last_error"] = EMPTY_FETCH_MARKER
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
    datasets = args.only.split(",") if args.only else DATASETS
    if not token:
        # DL-f1-s9：由 FETCHERS 的 needs_token 推導實際會跑／會跳過的表（不寫死表名）。
        # 原句「FinMind 表全跳過（僅更新 TWII）」不精確：tw_pmi、finmind_m1m2 不需 token，照跑。
        # 只列已註冊的表；未知表名由下方主迴圈另行印出。
        _known = [n for n in datasets if n in FETCHERS]
        _skip = [n for n in _known if FETCHERS[n][1]]
        _run = [n for n in _known if not FETCHERS[n][1]]
        print(f"⚠️ FINMIND_TOKEN 未設定 → 跳過需要 token 的表：{', '.join(_skip) or '（無）'}；"
              f"照常執行：{', '.join(_run) or '（無）'}")

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
