"""
macro_core.py — 兩個 dashboard 共用的總經核心 v1.0

設計目標
========
1. 兩個 repo (my-stock-dashboard / my-fund-dashboard) 共用同一份檔案,
   消除指標重複實作與閾值不一致的維護成本。
2. **所有外部 HTTP 抓取統一透過 proxy_helper.fetch_url(),確保走家用 NAS
   中繼站**,避免雲端 IP 被台灣金融網站封鎖,且 yfinance 在境外節點
   常被限流的問題。

範圍邊界(v1.0 已釐清)
=====================
✅ 收錄:全球/美國總經指標(VIX / DXY / US10Y / CPI / Fed Rate / PMI /
        HY OAS / M2 / Fed BS / 殖利率利差),資料源 = FRED + Yahoo Chart
✅ 收錄:純數學工具(zscore / trend / recession_probability / spread_series)
✅ 收錄:統一 schema(make_indicator / flatten_snapshot)
❌ 不收錄:台灣獨有指標(台指選擇權 PCR、台灣 M1B/M2、外資期貨淨空、
          BIAS240、TWSE 漲跌家數、FinMind 籌碼)→ 留在 stock 端
          自有模組(leading_indicators.py / 後續 tw_macro.py)
❌ 不收錄:下游決策(台股曝險上限、基金資產配置)→ 留在各自的引擎

依賴限制
========
- 不依賴 streamlit(可在 CLI / pytest 環境直接 import)
- 不依賴 yfinance(改打 Yahoo Finance Chart API,走 proxy)
"""
from __future__ import annotations

import datetime as _dt
import json as _json
import math
import os as _os
import re as _re
from typing import Callable, Optional

import numpy as np
import pandas as pd

from src.data.proxy import fetch_url
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
# (v19.85)FINMIND_API_URL import 移除 — 唯一 caller _pmi_src_finmind 已拔(假 dataset)
from shared.fred_series import (
    FRED_BSCICP02,
    FRED_ISPMANPMI,
    FRED_NAPM,
    FRED_PHILLY_FED,
)
from shared.signal_thresholds import (  # v18.242 W3b SSOT consume
    MACRO_MERGE_ASOF_TOLERANCE_DAYS,
    MACRO_TREND_LOOKBACK_PERIODS,
    RECESSION_LOGIT_COEF_INTERCEPT,
    RECESSION_LOGIT_COEF_SPREAD,
    TNX_VALUATION_PRESSURE_PCT,  # v18.326 PR-D: macro_compass TNX 門檻
    TNX_NEUTRAL_PCT,
)
from shared.fetch_monitor import monitored  # v19.96 批次4 Item1:fetcher 自我登錄

__version__ = "1.0.0"

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_RELEASE_BASE = "https://api.stlouisfed.org/fred/series/release"
FRED_RELEASE_DATES_BASE = "https://api.stlouisfed.org/fred/release/dates"
YF_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# v18.225 T1：PMI / Export 9-10 段全失敗時的 stale-cache fallback；TTL 90 天
# (覆蓋 CIER 月度公布 + 假日緩衝)；只當 in-memory race 失敗時讀，UI 標 🟡 stale
_MACRO_CACHE_DIR = _os.path.join("cache", "macro_snapshot")
_MACRO_CACHE_TTL_DAYS = 90
# v19.118：durable（committed）快照層。`cache/` 為 Streamlit Cloud **ephemeral** 磁碟
# （每次 container 重啟/重部署/休眠喚醒即抹），故 v18.225 的「命中即存 cache/、全敗讀
# cache/」在雲端撐不過 recycle → 一次上游打嗝後 cache/ 被清空 → 全敗 → 卡片「待取得」。
# 改在 `data_cache/`（**已 committed**，隨 deploy 帶上）另存一份「上次已知值」，即時全敗
# 時讀它（帶 is_stale）。寫入僅由 cron（update_macro_history.yml, permissions: contents:write）
# 呼叫 `_macro_durable_save` + workflow `git add -f data_cache/` 提交;runtime（Cloud）**只讀**。
_MACRO_DURABLE_DIR = _os.path.join("data_cache", "macro_last_good")
# v19.119：PMI 8 源並行賽跑的**硬上限**。必須 < macro_trio_orchestrator 的
# inner_pool_timeout_s(70s),留餘裕給下方 durable/stale fallback。根因:v19.116 把
# dgtw metadata timeout 放寬到 25s×2 attempts×3 URL = 最壞 ~150s,而原碼
# `for _fut: _fut.result()` 無限等最慢源 → 雲端 data.gov.tw「連得上但 hang」時
# fetch_tw_pmi 要 ~150s 才回,orchestrator 70s 就砍掉整個 block → durable seed
# 根本讀不到 → 卡片「待取得」。設 45s 上限:慢源背景自生自滅,主流程準時回落 durable。
_PMI_RACE_DEADLINE_S = 45

# v18.225 T2：FRED 下次 Release 30 天 TTL cache（鏡像 Fund repositories/macro_repository.py）
_FRED_RELEASE_CACHE_DIR = _os.path.join("cache", "fred_release")
_FRED_RELEASE_CACHE_TTL_DAYS = 30


def _macro_cache_path(key: str) -> str:
    return _os.path.join(_MACRO_CACHE_DIR, f"{key}.json")


def _macro_cache_save(key: str, payload: dict) -> None:
    """命中時持久化快照；任何 IO 錯誤靜默吞（cache 失敗不該破壞 happy path）。"""
    try:
        _os.makedirs(_MACRO_CACHE_DIR, exist_ok=True)
        payload = dict(payload)
        payload["cached_at"] = _dt.datetime.now().isoformat()
        with open(_macro_cache_path(key), "w", encoding="utf-8") as fh:
            _json.dump(payload, fh, ensure_ascii=False)
    except Exception as e:
        print(f"[macro_core/cache] save 失敗 {key}: {e}")


def _macro_durable_save(key: str, payload: dict) -> None:
    """v19.118：寫 durable（committed）快照 → 供 **cron** 呼叫，寫後由 workflow
    `git add -f data_cache/` 提交。runtime（Streamlit Cloud）**不呼叫**此函式（無 repo
    寫權限，且雲端磁碟 ephemeral）。shape 同 `_macro_cache_save`（附 cached_at）。"""
    try:
        _os.makedirs(_MACRO_DURABLE_DIR, exist_ok=True)
        payload = dict(payload)
        payload["cached_at"] = _dt.datetime.now().isoformat()
        with open(_os.path.join(_MACRO_DURABLE_DIR, f"{key}.json"), "w",
                  encoding="utf-8") as fh:
            _json.dump(payload, fh, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[macro_core/durable] save 失敗 {key}: {e}")


def _macro_cache_load(key: str) -> Optional[dict]:
    """讀取 TTL 內快照；過期或解析失敗回 None。

    v19.118 兩層 fallback：先讀 ephemeral `cache/`（session 內最新、命中即用），
    miss/過期再讀 durable `data_cache/`（committed，撐得過 Streamlit Cloud 重啟）。
    任一命中即回;皆 miss/過期回 None（§1 誠實，不硬湊）。
    """
    for _dir in (_MACRO_CACHE_DIR, _MACRO_DURABLE_DIR):
        path = _os.path.join(_dir, f"{key}.json")
        if not _os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = _json.load(fh)
            ts = _dt.datetime.fromisoformat(data.get("cached_at", ""))
            if (_dt.datetime.now() - ts).days >= _MACRO_CACHE_TTL_DAYS:
                continue
            return data
        except Exception:
            continue
    return None


def _fred_release_cache_path(series_id: str) -> str:
    return _os.path.join(_FRED_RELEASE_CACHE_DIR, f"{series_id}.json")


def _fred_release_cache_load(series_id: str) -> Optional[dict]:
    path = _fred_release_cache_path(series_id)
    if not _os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        ts = _dt.datetime.fromisoformat(data["cached_at"])
        if (_dt.datetime.now() - ts).days >= _FRED_RELEASE_CACHE_TTL_DAYS:
            return None
        return data
    except Exception:
        return None


def _fred_release_cache_save(series_id: str, payload: dict) -> None:
    try:
        _os.makedirs(_FRED_RELEASE_CACHE_DIR, exist_ok=True)
        payload = dict(payload)
        payload["cached_at"] = _dt.datetime.now().isoformat()
        with open(_fred_release_cache_path(series_id), "w", encoding="utf-8") as fh:
            _json.dump(payload, fh, ensure_ascii=False)
    except Exception as e:
        print(f"[macro_core/fred_release] cache save 失敗 {series_id}: {e}")


def fred_get_next_release_date(series_id: str, api_key: str) -> Optional[_dt.date]:
    """查詢指定 FRED series 的下次預定 release 日（鏡像 Fund 端，30d cache）。

    流程：
      1. 先讀本地 cache（30 天 TTL，避免每次 rerun 都打 API）
      2. 呼叫 /fred/series/release 取 release_id
      3. 呼叫 /fred/release/dates 取「今日起」未來最近一筆 release date

    Returns
    -------
    datetime.date | None
        下次 release 日；任一步驟失敗回 None（呼叫端應 fallback 到舊閾值）。
    """
    if not series_id or not api_key:
        return None

    cached = _fred_release_cache_load(series_id)
    today = _dt.date.today()
    if cached:
        try:
            nrd = _dt.date.fromisoformat(cached.get("next_release_date", ""))
            if nrd >= today:
                return nrd
        except Exception:
            pass

    try:
        r1 = fetch_url(
            FRED_RELEASE_BASE,
            params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
            timeout=15,
        )
        if r1 is None:
            return None
        releases = r1.json().get("releases", [])
        if not releases:
            return None
        release_id = releases[0].get("id")
        if not release_id:
            return None
    except Exception as e:
        print(f"[macro_core/fred_release] {series_id} release_id 解析失敗: {e}")
        return None

    try:
        r2 = fetch_url(
            FRED_RELEASE_DATES_BASE,
            params={
                "release_id": release_id,
                "api_key":    api_key,
                "file_type":  "json",
                "include_release_dates_with_no_data": "true",
                "realtime_start": today.isoformat(),
                "realtime_end": (today + _dt.timedelta(days=120)).isoformat(),
                "sort_order": "asc",
                "limit":      20,
            },
            timeout=15,
        )
        if r2 is None:
            return None
        dates = r2.json().get("release_dates", [])
        for d in dates:
            try:
                cand = _dt.date.fromisoformat(d.get("date", ""))
                if cand >= today:
                    _fred_release_cache_save(series_id, {
                        "release_id": release_id,
                        "next_release_date": cand.isoformat(),
                    })
                    return cand
            except Exception:
                continue
    except Exception as e:
        print(f"[macro_core/fred_release] {series_id} release_dates 解析失敗: {e}")
        return None

    return None


# ══════════════════════════════════════════════════════════════
# 統一閾值表
#   全球/美國指標兩 repo 共用一份;台灣指標(v18.270 起)併入此表,
#   stock 端為主消費者,fund 端跨幣別配置需要時可借用。
# ══════════════════════════════════════════════════════════════
MACRO_THRESHOLDS: dict = {
    "VIX":         {"green_below": 18, "yellow_above": 22, "red_above": 30},
    "CPI":         {"green_low": 1.5, "green_high": 2.5, "yellow_above": 3.5, "red_above": 4.0},
    "US10Y":       {"yellow_above": 4.5, "red_above": 5.0},
    "DXY":         {"yellow_above": 105, "red_above": 110},
    "PMI":         {"red_below": 46, "yellow_below": 50, "green_above": 52},
    "HY_SPREAD":   {"green_below": 4.0, "yellow_below": 6.0, "red_above": 6.0},
    "YIELD_10Y2Y": {"red_below": 0.0, "yellow_below": 0.5},
    "YIELD_10Y3M": {"red_below": 0.0, "yellow_below": 0.5},
    "M2_YOY":      {"red_below": 0.0, "green_above": 5.0},
    "FED_BS_YOY":  {"red_below": -5.0, "green_above": 5.0},
    # v18.270 TW 央行政策階段判讀:CPI YoY / 失業率 / CBC 重貼現率 / USDTWD
    "TW_CPI_YOY":  {"green_low": 1.0, "green_high": 2.0, "yellow_above": 2.5, "red_above": 3.0},
    "TW_UNEMP":    {"green_below": 3.7, "yellow_above": 4.0, "red_above": 4.5},
    "CBC_RATE":    {"yellow_above": 2.125, "red_above": 2.5},  # v18.460: 2.0→2.125 現行 2.0% 不再卡邊界;下一升息步幅 2.125%
    # USDTWD:>32 yellow / >33 red(台幣明顯貶值,外資撤離壓力)
    "USDTWD":      {"green_below": 30.5, "yellow_above": 32.0, "red_above": 33.0},
    # v18.271 China macro 5 zone(對稱 Fund v19.113):服務中國終端需求 + 全球流動性判讀
    "CHN_CLI":     {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},
    "CHN_BCI":     {"green_above": 100.0, "yellow_below": 99.0, "red_below": 98.0},  # v18.459: renamed CHN_PMI→CHN_BCI (BSCICP03CNM665S = OECD Business Confidence, NOT PMI)
    "CHN_CPI":     {"green_low": 1.0, "green_high": 3.0, "yellow_above": 4.0, "red_above": 5.0},
    "CHN_M2":      {"red_below": 5.0, "green_above": 9.0},
    "USDCNY":      {"green_below": 7.1, "yellow_above": 7.3, "red_above": 7.45},  # v18.460: 7.0→7.1/7.2→7.3/7.4→7.45 人民幣 2022 後走弱,舊 green_below 7.0 已 2+ 年無法到達
}


# ══════════════════════════════════════════════════════════════
# 資料抓取(全部走 NAS proxy)
# ══════════════════════════════════════════════════════════════

# v18.231 P1-S3：fetch_fred 跨呼叫 (series_id, api_key, n) 集中
# 原本無 cache，risk_radar.py L246/L271 雙呼 BAMLH0A0HYM2/DGS10 每次都打 FRED API。
# 改 module-level TTL dict（30min，與 Fund repositories.macro_repository.fetch_fred
# `@_ttl_cache(ttl_sec=1800, maxsize=32)` 對齊）。
# 不用 @st.cache_data 是因為 macro_core 規定不依賴 streamlit，須能在 CLI/pytest 直接 import。
_FRED_CACHE: dict[tuple[str, str, int], tuple[float, pd.DataFrame]] = {}
_FRED_TTL = 1800.0  # 30min，FRED 日頻足夠
# S9 v19.78(第二份 review):fetch_china_macro(tw_macro)以 ThreadPoolExecutor(5)
# 併發呼叫 fetch_fred → module dict 無鎖 check-then-set 為 TOCTOU race
# (CPython dict 單操作原子不會壞結構,但重複抓取/覆寫)。補鎖保護讀寫臨界區。
import threading as _th_mc
_FRED_CACHE_LOCK = _th_mc.Lock()
_YF_CLOSE_CACHE_LOCK = _th_mc.Lock()


def fetch_fred(series_id: str, api_key: str, n: int = 250) -> pd.DataFrame:
    """
    抓取 FRED 經濟序列(透過 NAS proxy)。

    Returns
    -------
    pd.DataFrame  欄位:
        - `date` (Timestamp):資料歸屬日(observation_date)
        - `value` (float):指標數值(已排序去除空值)
        - `source` (str):血緣標識,例如 "FRED:DGS10"(S-PROV-1 v18.246 新增)
        - `fetched_at` (str):本次抓取的 UTC ISO 時間字串(S-PROV-1 v18.246 新增)

    失敗時回傳空 DataFrame(無欄位,caller 須先 `df.empty` 判斷)。

    v18.231 P1-S3:module-level TTL dict(30min)跨呼叫共享,
    cache key = (series_id, api_key, n);copy-on-read 防 caller mutation 污染。

    v18.246 S-PROV-1(§2.2 provenance):新增 `source` + `fetched_at` 兩欄,
    讓下游能追溯資料來源 + 抓取時間。schema-additive,既有 caller(讀 date/value)
    無需修改;新 caller 可選用 provenance 欄位做血緣追蹤。
    """
    if not api_key:
        # W5-2 §1: 沉默 return empty 改補 log,但不 raise(caller 已透過 empty 判斷 fallback)
        print(f"[macro_core/fred] {series_id} 跳過:無 api_key")
        return pd.DataFrame()

    import time as _time
    key = (series_id, api_key, n)
    now = _time.time()
    with _FRED_CACHE_LOCK:   # S9 v19.78
        cached = _FRED_CACHE.get(key)
    if cached is not None and (now - cached[0]) < _FRED_TTL:
        return cached[1].copy()

    r = fetch_url(
        FRED_BASE,
        params={
            "series_id":  series_id,
            "api_key":    api_key,
            "file_type":  "json",
            "sort_order": "desc",
            "limit":      n,
        },
        timeout=20,
    )
    if r is None:
        # W5-2 §1: fetch 失敗補 log(caller 走 fallback 鏈,故不 raise)
        print(f"[macro_core/fred] {series_id} fetch_url 回 None(network/timeout)")
        return pd.DataFrame()
    try:
        obs = r.json().get("observations", [])
    except Exception as e:
        print(f"[macro_core/fred] {series_id} JSON 解析失敗: {e}")
        return pd.DataFrame()
    if not obs:
        # W5-2 §1: FRED 回 200 但 observations 空 — 補 log
        print(f"[macro_core/fred] {series_id} observations 為空(可能新 series 尚未發布)")
        return pd.DataFrame()
    df = pd.DataFrame(obs)
    df = df[df["value"] != "."].copy()
    # v18.306:強制 float64(pd.to_numeric 對 int-only series 如 PAYEMS/HSN1F 會
    # 推得 int64;pandera MacroFredSchema 要求 float64,鎖死避免 schema 飄移)
    df["value"] = pd.to_numeric(df["value"], errors="coerce").astype("float64")
    df["date"]  = pd.to_datetime(df["date"])
    out = df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)
    # v18.246 S-PROV-1:provenance schema(§2.2)— source 標識 + 抓取時間
    out["source"] = f"FRED:{series_id}"
    out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    # v18.306 Pandera Phase A pilot:出口契約驗(best-effort,pandera 不在時不阻斷)
    try:
        from shared.schemas import validate_fred  # noqa: PLC0415
        validate_fred(out)
    except ImportError:
        pass
    with _FRED_CACHE_LOCK:   # S9 v19.78
        _FRED_CACHE[key] = (now, out.copy())
    return out


# v18.229 P1-S2：fetch_yf_close 跨 tab range_ 集中
# 原本無 cache，跨 tab 重複抓 ^VIX/^GSPC/^TNX 等指標 2~3 次。
# 改為固定 range='2y' 底層 + 記憶體切片 + 1hr TTL dict
# （不用 @st.cache_data 是因為 macro_core 規定不依賴 streamlit，須能在 CLI/pytest 直接 import）。
_YF_RANGE_TO_DAYS = {
    "5d": 7, "1mo": 31, "3mo": 93, "6mo": 186,
    "1y": 365, "2y": 365 * 2, "3y": 365 * 3, "5y": 365 * 5,
    "10y": 365 * 10, "ytd": 366, "max": None,
}
_YF_CLOSE_CACHE: dict[tuple[str, str], tuple[float, pd.Series]] = {}
_YF_CLOSE_TTL = 3600.0  # 1hr，與 st.cache_data 對齊


def _fetch_yf_close_base(ticker: str, interval: str = "1d") -> pd.Series:
    """共用底層 — 固定 range='2y' + 1hr TTL，跨 tab 共享。

    用 module-level TTL dict + copy-on-read 取代 @st.cache_data，
    維持 macro_core 不依賴 streamlit 的設計邊界。
    """
    import time as _time
    key = (ticker, interval)
    now = _time.time()
    with _YF_CLOSE_CACHE_LOCK:   # S9 v19.78
        cached = _YF_CLOSE_CACHE.get(key)
    if cached is not None and (now - cached[0]) < _YF_CLOSE_TTL:
        return cached[1].copy()

    url = f"{YF_CHART_BASE}/{ticker}"
    r = fetch_url(
        url,
        params={"interval": interval, "range": "2y"},
        timeout=15,
    )
    if r is None:
        return pd.Series(dtype=float, name=ticker)
    try:
        d = r.json()
        result = d["chart"]["result"][0]
        ts = result["timestamp"]
        close = result["indicators"]["quote"][0]["close"]
        s = pd.Series(close, index=pd.to_datetime(ts, unit="s"), dtype=float).dropna()
        s.name = ticker
        # v18.246 S-PROV-1 phase 2:provenance via Series.attrs(§2.2)
        # Series 無 column 概念,改用 pandas 內建 attrs dict 承載血緣。
        # caller 不存取 attrs 時無感;需要追溯時 s.attrs["source"] / s.attrs["fetched_at"]。
        s.attrs["source"] = f"Yahoo:{ticker}"
        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        with _YF_CLOSE_CACHE_LOCK:   # S9 v19.78
            _YF_CLOSE_CACHE[key] = (now, s.copy())
        return s
    except Exception as e:
        print(f"[macro_core/yf] {ticker} 解析失敗: {e}")
        return pd.Series(dtype=float, name=ticker)


def fetch_yf_close(ticker: str, range_: str = "2y", interval: str = "1d") -> pd.Series:
    """
    抓取 Yahoo Finance 收盤價序列(透過 NAS proxy 直打 Chart API)。

    為何不用 yfinance:yfinance 預設不走 proxy,且常因雲端節點 IP
    被 Yahoo 限流(429)而失敗。直接呼叫 Chart REST API + NAS 中繼,
    取得台灣 IP 出口,穩定許多。

    v18.229 起改為共用 'range=2y' 底層 + 記憶體切片，跨 tab 同 ticker
    從 2~3 次 fetch_url call → 1 次（cache key = (ticker, interval)）。
    公開簽章不變，14 個呼叫端 0 改動。

    Returns
    -------
    pd.Series  index 為 DatetimeIndex,value 為收盤價。失敗時回傳空 Series。
               provenance(S-PROV-1 v18.246):成功時 `s.attrs` 含
               `source="Yahoo:<ticker>"` + `fetched_at=UTC ISO`。
    """
    s = _fetch_yf_close_base(ticker, interval)
    if s.empty:
        return s
    days = _YF_RANGE_TO_DAYS.get(range_, 365 * 2)
    if days is None:
        return s
    cutoff = s.index.max() - pd.Timedelta(days=days)
    sliced = s.loc[s.index >= cutoff]
    # v18.246 S-PROV-1:pandas .loc 切片可能 lose attrs,顯式 copy 保留血緣
    sliced.attrs = dict(s.attrs)
    return sliced


def fetch_yf_latest(tickers: tuple[str, ...]) -> dict[str, Optional[float]]:
    """批次抓多個 ticker 最新收盤(空值代表抓不到)。

    S-PROV-1 P0 v18.434:批次結果寫 stderr prov_log。子呼叫 fetch_yf_close
    內部 Series.attrs 已有 source/fetched_at;此處 prov 識別 batch 聚合場景。
    """
    out: dict[str, Optional[float]] = {}
    for t in tickers:
        s = fetch_yf_close(t, range_="5d")
        out[t] = round(float(s.iloc[-1]), 4) if not s.empty else None
    try:
        from src.data.core.provenance import prov_log
        _filled = sum(1 for v in out.values() if v is not None)
        prov_log('fetch_yf_latest', 'Yahoo:batch(5d)->iloc[-1]',
                 f'dict:{_filled}/{len(tickers)}filled',
                 ticker=','.join(tickers)[:60])
    except Exception:
        pass
    return out


def fetch_yf_ohlcv(ticker: str, range_: str = "9mo", interval: str = "1d") -> pd.DataFrame:
    """
    抓取 Yahoo Finance OHLCV 序列(走 NAS proxy)。提供 Close + Volume 給
    需要量能判斷的場景(例如 market_strategy.get_market_assessment 需要
    rolling 20 日均量與當日成交量)。

    Returns
    -------
    pd.DataFrame
        index = DatetimeIndex
        columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        + S-PROV-1 phase 16 v18.262 schema-additive 'source' + 'fetched_at'
        失敗時回傳空 DataFrame。
    """
    url = f"{YF_CHART_BASE}/{ticker}"
    r = fetch_url(url, params={"interval": interval, "range": range_}, timeout=15)
    if r is None:
        return pd.DataFrame()
    try:
        result = r.json()["chart"]["result"][0]
        ts = pd.to_datetime(result["timestamp"], unit="s")
        q  = result["indicators"]["quote"][0]
        df = pd.DataFrame({
            "Open":   q.get("open"),
            "High":   q.get("high"),
            "Low":    q.get("low"),
            "Close":  q.get("close"),
            "Volume": q.get("volume"),
        }, index=ts)
        df = df.dropna(subset=["Close"])
        # S-PROV-1 phase 16 v18.262 — provenance(schema-additive)
        if not df.empty:
            df["source"] = f"Yahoo:chart:{ticker}:{range_}:{interval}"
            df["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        # Phase 2 pandera Priority 1 v18.433 — log-mode schema validation
        # (yfinance OHLCV 大寫 column,normalize_case=True);失敗只 stderr log,不擋 caller
        try:
            from shared.schemas import validate_in_log_mode, OHLCVSchema
            df = validate_in_log_mode(df, OHLCVSchema,
                                       label=f'fetch_yf_ohlcv:{ticker}:{range_}',
                                       normalize_case=True)
        except Exception:
            pass
        return df
    except Exception as e:
        print(f"[macro_core/yf_ohlcv] {ticker} 解析失敗: {e}")
        return pd.DataFrame()


# ══════════════════════════════════════════════════════════════
# 總經指南針 (Top-Down Macro Compass) — Phase 1 規格三大指標
#   VIX / TNX / GSPC + 60MA，固定於頁面頂部供新人秒懂市場大環境。
#   呼叫端：app.py 的 render_macro_compass()（在 st.tabs() 之前渲染）。
# ══════════════════════════════════════════════════════════════

def fetch_macro_compass(range_: str = "6mo") -> dict:
    """Phase 1 — 一次抓 ^VIX / ^TNX / ^GSPC 三大美股指標 + GSPC 60MA。

    所有抓取都走 macro_core.fetch_yf_close()（NAS proxy → Yahoo Chart REST API），
    避開 yfinance 直連被 Streamlit Cloud IP 限流。失敗欄位填 None，UI 端優雅降級。

    Returns dict:
      vix  : {'value', 'series', 'dates', 'signal':(light, label, color),
              'source', 'fetched_at'} | None
      tnx  : 同上                                                          | None
      gspc : 同上 + {'ma60', 'ma60_series'}                                | None

    v18.295 S-PROV-1 phase 2:每個 ticker 的 dict 補 `source` + `fetched_at`
    (從 fetch_yf_close 的 s.attrs 透傳),caller 無此欄位讀取者完全無感。
    """
    out: dict = {'vix': None, 'tnx': None, 'gspc': None}

    def _sig_vix(v):
        # v18.326 PR-D：黃線 25→22 對齊 C2 全站統一（複用 MACRO_THRESHOLDS['VIX'] SSOT）。
        # v18.459 Bug Fix：>red_above(30) 改⚫（恐慌≠平靜，不可同為🟢）
        # >red_above(30) 黑（極端恐慌，逢低加碼訊號）/ >yellow_above(22) 黃（波動加劇）/ 其餘綠（市場平靜）
        if v > MACRO_THRESHOLDS['VIX']['red_above']: return ('⚫', '極端恐慌（逢低加碼訊號）', '#8b949e')
        if v > MACRO_THRESHOLDS['VIX']['yellow_above']: return ('🟡', '波動加劇', TRAFFIC_YELLOW)
        return ('🟢', '市場平靜', TRAFFIC_GREEN)

    def _sig_tnx(t):
        # 估值壓力：≥4.5% 紅 / 3.5–4.5 黃 / <3.5 綠（寬鬆）— v18.326 PR-D SSOT 化（保行為）
        if t >= TNX_VALUATION_PRESSURE_PCT: return ('🔴', '估值壓力（科技股不利）', TRAFFIC_RED)
        if t >= TNX_NEUTRAL_PCT: return ('🟡', '中性區', TRAFFIC_YELLOW)
        return ('🟢', '寬鬆有利', TRAFFIC_GREEN)

    def _sig_gspc(g, ma):
        # Phase 1 規格：站上 60MA=多頭、跌破=趨勢轉弱
        if ma is None or g is None:
            return ('⚪', '60MA 計算中', '#8b949e')
        if g >= ma: return ('🟢', '多頭格局（股優於債）', TRAFFIC_GREEN)
        return ('🔴', '趨勢轉弱（提高防禦）', TRAFFIC_RED)

    # ── ^VIX ────────────────────────────────────────────────
    try:
        s = fetch_yf_close('^VIX', range_=range_)
        if not s.empty:
            v = round(float(s.iloc[-1]), 2)
            tail = s.tail(90)
            out['vix'] = {
                'value': v,
                'series': [round(float(x), 2) for x in tail.tolist()],
                'dates':  [d.strftime('%Y-%m-%d') for d in tail.index],
                'signal': _sig_vix(v),
                # v18.295 S-PROV-1 phase 2:provenance 透傳自 s.attrs
                'source': s.attrs.get('source', 'Yahoo:^VIX'),
                'fetched_at': s.attrs.get('fetched_at', ''),
            }
    except Exception as e:
        print(f'[macro_compass] VIX fetch failed: {e}')

    # ── ^TNX ────────────────────────────────────────────────
    try:
        s = fetch_yf_close('^TNX', range_=range_)
        if not s.empty:
            t = round(float(s.iloc[-1]), 3)
            tail = s.tail(90)
            out['tnx'] = {
                'value': t,
                'series': [round(float(x), 3) for x in tail.tolist()],
                'dates':  [d.strftime('%Y-%m-%d') for d in tail.index],
                'signal': _sig_tnx(t),
                # v18.295 S-PROV-1 phase 2:provenance 透傳自 s.attrs
                'source': s.attrs.get('source', 'Yahoo:^TNX'),
                'fetched_at': s.attrs.get('fetched_at', ''),
            }
    except Exception as e:
        print(f'[macro_compass] TNX fetch failed: {e}')

    # ── ^GSPC + 60MA ────────────────────────────────────────
    try:
        s = fetch_yf_close('^GSPC', range_=range_)
        if not s.empty:
            g = round(float(s.iloc[-1]), 2)
            ma60_ser = s.rolling(60).mean()
            ma60_last = ma60_ser.dropna()
            ma60 = round(float(ma60_last.iloc[-1]), 2) if not ma60_last.empty else None
            tail = s.tail(90)
            ma_tail = ma60_ser.tail(90)
            out['gspc'] = {
                'value': g,
                'ma60': ma60,
                'series': [round(float(x), 2) for x in tail.tolist()],
                'ma60_series': [None if pd.isna(x) else round(float(x), 2) for x in ma_tail.tolist()],
                'dates': [d.strftime('%Y-%m-%d') for d in tail.index],
                'signal': _sig_gspc(g, ma60),
                # v18.295 S-PROV-1 phase 2:provenance 透傳自 s.attrs
                'source': s.attrs.get('source', 'Yahoo:^GSPC'),
                'fetched_at': s.attrs.get('fetched_at', ''),
            }
    except Exception as e:
        print(f'[macro_compass] GSPC fetch failed: {e}')

    return out


# ══════════════════════════════════════════════════════════════
# ISM 製造業 PMI — 5 段備援共用函式（v1.1 兩端統一）
#
# 為什麼 5 段？
#   FRED NAPM / ISPMANPMI 自 2016-08 ISM 收回授權後停更，但保留以防重啟；
#   MacroMicro / ISM World 為主存活源但 HTML 結構易變動；
#   DBnomics 為 ISM JSON 鏡像（無需 key）；
#   OECD US Business Confidence 在 FRED 上仍持續更新，作為「概念替代指標」，
#   值約 98–102（非 PMI 的 30–70 區間），與 ISM PMI 相關性 ~0.7。
# ══════════════════════════════════════════════════════════════

def fetch_ism_pmi(fred_api_key: str = "", *, max_age_days: int = 90) -> dict:
    """抓取 ISM 製造業 PMI（5 段備援，月頻）。

    Returns
    -------
    dict
      命中：{'value': float, 'date': 'YYYY-MM-DD', 'label': str,
             'source': str, 'is_proxy': bool, 'series_id': str,
             'dates': [...], 'values': [...], 'proxy_note'?: str}
      失敗：{'_err_pmi': str, 'value': None}
    """
    import datetime as _dt
    import re as _re
    today = _dt.date.today()
    errs: list[str] = []

    # ── 方案 1+2: FRED NAPM / ISPMANPMI（max_age_days 時效檢查）──
    if fred_api_key:
        for sid, lbl in [(FRED_NAPM, 'FRED NAPM'), (FRED_ISPMANPMI, 'FRED ISPMANPMI')]:
            try:
                df = fetch_fred(sid, fred_api_key, n=36)
                if df.empty or len(df) < 5:
                    continue
                df = df.tail(24)
                last_date = pd.to_datetime(df['date'].iloc[-1]).date()
                age = (today - last_date).days
                if age > max_age_days:
                    print(f'[macro_core/PMI/FRED] ⚠️ {sid} 最新={last_date} '
                          f'已停更 {age} 天 > {max_age_days}，跳過')
                    continue
                v = round(float(df['value'].iloc[-1]), 1)
                print(f'[macro_core/PMI/FRED] ✅ {sid}={v} date={last_date}')
                return {
                    'value': v, 'date': str(last_date), 'label': lbl,
                    # S-PROV-1 v18.296 phase 3:source 帶 series ID(SSOT 精確度)
                    'source': f'FRED:{sid}', 'is_proxy': False, 'series_id': sid,
                    'fetched_at': pd.Timestamp.now('UTC').isoformat(),
                    'dates':  [str(pd.to_datetime(d).date()) for d in df['date']],
                    'values': [round(float(x), 1) for x in df['value']],
                }
            except Exception as e:
                errs.append(f'FRED.{sid}:{type(e).__name__}')
                print(f'[macro_core/PMI/FRED/{sid}] ❌ {e}')

    # ── 方案 3: MacroMicro 財經 M 平方（中文 HTML）──
    try:
        from bs4 import BeautifulSoup
        for url in ('https://www.macromicro.me/charts/950/us-ism-mfg-pmi',
                    'https://www.macromicro.me/charts/2/economic-monitor-pmi'):
            r = fetch_url(url, timeout=12, attempts=1)
            if r is None:
                continue
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(?:ISM[^。]{0,40}?PMI|製造業\s*PMI)[^。]{0,200}?'
                r'(\d{2}\.\d)[^。]{0,80}?(20\d{2})[\s/年-]+(\d{1,2})',
                txt)
            if m:
                v = float(m.group(1)); yr = m.group(2); mo = int(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    date = f'{yr}-{mo:02d}-01'
                    print(f'[macro_core/PMI/MacroMicro] ✅ {v} date={date}')
                    return {'value': v, 'date': date,
                            'label': 'MacroMicro ISM PMI',
                            # S-PROV-1 v18.296 phase 3:source 帶 chart ID(SSOT 精確度)
                            'source': 'MacroMicro:us-ism-mfg-pmi', 'is_proxy': False,
                            'series_id': '950',
                            'fetched_at': pd.Timestamp.now('UTC').isoformat()}
    except Exception as e:
        errs.append(f'MacroMicro:{type(e).__name__}')
        print(f'[macro_core/PMI/MacroMicro] ❌ {e}')

    # ── 方案 4: ISM World 官方月報（英文 HTML，最一手）──
    try:
        from bs4 import BeautifulSoup
        url = ('https://www.ismworld.org/supply-management-news-and-reports/'
               'reports/ism-report-on-business/pmi/')
        r = fetch_url(url, timeout=12, attempts=1)
        if r is not None:
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(?:Manufacturing\s+PMI[^.]{0,40}?(?:at|registered)|'
                r'PMI[^.]{0,15}?registered)[^\d]{0,15}(\d{2}\.\d)\s*(?:%|percent)',
                txt, _re.IGNORECASE)
            if m:
                v = float(m.group(1))
                if 30 <= v <= 70:
                    m_dt = _re.search(
                        r'(January|February|March|April|May|June|July|August|'
                        r'September|October|November|December)\s+(20\d{2})', txt)
                    date = ''
                    if m_dt:
                        MO = {'January':1,'February':2,'March':3,'April':4,
                              'May':5,'June':6,'July':7,'August':8,
                              'September':9,'October':10,'November':11,'December':12}
                        date = f'{m_dt.group(2)}-{MO[m_dt.group(1)]:02d}-01'
                    print(f'[macro_core/PMI/ISM] ✅ {v} date={date or "?"}')
                    return {'value': v, 'date': date,
                            'label': 'ISM World Official',
                            # S-PROV-1 v18.296 phase 3:source 帶 endpoint host
                            'source': 'ISM:ismworld.org', 'is_proxy': False,
                            'series_id': 'ismworld.org',
                            'fetched_at': pd.Timestamp.now('UTC').isoformat()}
    except Exception as e:
        errs.append(f'ISM:{type(e).__name__}')
        print(f'[macro_core/PMI/ISM] ❌ {e}')

    # ── 方案 5: DBnomics（純 JSON,ISM 鏡像,無需 key）──
    try:
        url = 'https://api.db.nomics.world/v22/series/ISM/pmi/pm'
        r = fetch_url(url, params={'observations': '1', 'limit': '24'}, timeout=15, attempts=1)
        if r is not None:
            d = r.json()
            docs = d.get('series', {}).get('docs', []) or []
            if docs:
                periods = docs[0].get('period', []) or []
                values  = docs[0].get('value',  []) or []
                last_idx = -1
                for i in range(len(values) - 1, -1, -1):
                    vi = values[i]
                    if vi is None: continue
                    try:
                        if isinstance(vi, float) and (vi != vi):  # NaN
                            continue
                    except Exception:
                        pass
                    last_idx = i; break
                if last_idx >= 0:
                    v = round(float(values[last_idx]), 1)
                    period_str = str(periods[last_idx])
                    last_date = _dt.datetime.strptime(period_str[:7], '%Y-%m').date()
                    age = (today - last_date).days
                    if age <= max_age_days and 30 <= v <= 70:
                        date = f'{period_str[:7]}-01'
                        print(f'[macro_core/PMI/DBnomics] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'DBnomics ISM/pmi/pm',
                                # S-PROV-1 v18.296 phase 3:source 帶 DBnomics dataset 路徑
                                'source': 'DBnomics:ISM/pmi/pm', 'is_proxy': False,
                                'series_id': 'ISM/pmi/pm',
                                'fetched_at': pd.Timestamp.now('UTC').isoformat()}
                    else:
                        print(f'[macro_core/PMI/DBnomics] ⚠️ '
                              f'最新={period_str} v={v} age={age}d 不通過防呆')
    except Exception as e:
        errs.append(f'DBnomics:{type(e).__name__}')
        print(f'[macro_core/PMI/DBnomics] ❌ {e}')

    # ── 方案 6: Phil Fed 製造業擴散指數（FRED GACDFSA066MSFRBPHI）──
    #   FRED 上仍持續更新；範圍 -50~+50；數學轉換為 PMI 等價刻度：
    #   PMI_eq = 50 + diffusion / 3 → 區間 33~67，與 ISM PMI 歷史相關性 ~0.85。
    #   標 is_proxy=True，UI 顯示「Phil Fed 替代計」。
    if fred_api_key:
        try:
            df = fetch_fred(FRED_PHILLY_FED, fred_api_key, n=36)
            if not df.empty and len(df) >= 5:
                df = df.tail(24).copy()
                last_date = pd.to_datetime(df['date'].iloc[-1]).date()
                age = (today - last_date).days
                if age <= max_age_days:
                    # 轉換為 PMI 等價刻度
                    df['value'] = 50.0 + df['value'] / 3.0
                    v = round(float(df['value'].iloc[-1]), 1)
                    print(f'[macro_core/PMI/PhilFed] ⚠️ 採用替代計 '
                          f'PMI_eq={v} (Phil Fed Diffusion 轉換) date={last_date}')
                    return {
                        'value': v, 'date': str(last_date),
                        'label': 'Phil Fed 製造業擴散（轉 PMI 刻度）',
                        # S-PROV-1 v18.296 phase 3:source 帶 FRED series ID(proxy 標記)
                        'source': f'FRED:{FRED_PHILLY_FED}:proxy', 'is_proxy': True,
                        'series_id': FRED_PHILLY_FED,
                        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
                        'dates':  [str(pd.to_datetime(d).date()) for d in df['date']],
                        'values': [round(float(x), 1) for x in df['value']],
                        'proxy_note': '⚠️ 替代指標：Phil Fed 製造業擴散指數，'
                                      '已用 PMI_eq = 50 + diffusion/3 轉換為 PMI 刻度。'
                                      '與 ISM PMI 歷史相關性 ~0.85。',
                    }
        except Exception as e:
            errs.append(f'PhilFed-Proxy:{type(e).__name__}')
            print(f'[macro_core/PMI/PhilFed] ❌ {e}')

    # ── 方案 7: OECD US Business Confidence（FRED BSCICP02USM460S, Proxy）──
    #   最後手段；非 ISM PMI；月頻；值 ~98–102（非 30–70）；與 ISM PMI 相關性 ~0.7。
    #   UI 必須以 is_proxy=True 標註，且分數刻度與 PMI 不同。
    if fred_api_key:
        try:
            df = fetch_fred(FRED_BSCICP02, fred_api_key, n=36)
            if not df.empty and len(df) >= 5:
                df = df.tail(24)
                last_date = pd.to_datetime(df['date'].iloc[-1]).date()
                age = (today - last_date).days
                if age <= max_age_days:
                    v = round(float(df['value'].iloc[-1]), 2)
                    print(f'[macro_core/PMI/OECD-Proxy] ⚠️ 採用替代指標 '
                          f'BSCICP02USM460S={v} date={last_date}')
                    return {
                        'value': v, 'date': str(last_date),
                        'label': 'OECD US Business Confidence (Proxy)',
                        # S-PROV-1 v18.296 phase 3:source 帶 FRED series ID(proxy 標記)
                        'source': f'FRED:{FRED_BSCICP02}:proxy', 'is_proxy': True,
                        'series_id': FRED_BSCICP02,
                        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
                        'dates':  [str(pd.to_datetime(d).date()) for d in df['date']],
                        'values': [round(float(x), 2) for x in df['value']],
                        'proxy_note': '⚠️ 替代指標：OECD 美國商業信心指數。'
                                      '值域 ~98–102（100 為長期平均,非 50 榮枯線）。'
                                      '與 ISM PMI 相關性 ~0.7,請參考趨勢方向而非絕對位階。',
                    }
                else:
                    errs.append(f'OECD-Proxy:過時 {age} 天')
        except Exception as e:
            errs.append(f'OECD-Proxy:{type(e).__name__}')
            print(f'[macro_core/PMI/OECD-Proxy] ❌ {e}')

    err_msg = ' | '.join(errs) or 'all 7 stages failed'
    print(f'[macro_core/PMI] ❌ 7 段備援全失敗：{err_msg}')
    # S-PROV-1 v18.296 phase 3:err path 也帶 provenance(diagnostic 用途)
    return {'_err_pmi': err_msg, 'value': None,
            'source': 'ISM-PMI:all_7_stages_failed',
            'fetched_at': pd.Timestamp.now('UTC').isoformat()}


# ══════════════════════════════════════════════════════════════
# 台灣製造業 PMI — CIER 中華經濟研究院（Stock 端使用）
#
# 為什麼台灣 PMI 不放 fund 端？
#   Fund 端是全球視角（看美國 ISM 即可）；
#   Stock 端是台股視角，台灣景氣與本地 PMI 直接相關（CIER 是官方發布單位，
#   每月第一個工作日上午 10:00 公布前一個月數據）。
#
# 備援順序：見檔末 PMI_SOURCE_REGISTRY(v19.113 起 8 源;本註解原列 4 段為
# v10 時代殘影,以 registry 為 SSOT 不再重複列舉)
# ══════════════════════════════════════════════════════════════

@monitored('fetch_tw_pmi', category='🇹🇼 台灣總經', frequency='monthly',
           registry_key='🇹🇼 台灣 PMI 製造業指數',   # v19.96 批次4 Item1
           # v19.118:治假綠燈——8 源全敗仍回 dict(value=None)不拋例外,舊版恆綠誤導。
           # 有值(含 durable stale 值)=綠;value=None(連 durable 都沒有)=紅。
           success_check=lambda r: isinstance(r, dict) and r.get('value') is not None)
def fetch_tw_pmi(*, max_age_days: int = 90) -> dict:
    """抓取台灣製造業 PMI（8 來源並行賽跑，依優先序取最高優先的有效值；月頻）。

    來源優先序：CIER-EN → data.gov.tw → NDC → CIER(首頁) → StockFeel
                → Cnyes → CIER(cid8) → MoneyDJ
    (v19.113 拔除 MacroMicro 段 — 探針 run 29182317622 實錘 host 級無回應;
    CIER 段的 cid=21 列表 URL 同輪實錘下架,改僅掃首頁。user 核准提案②。)
    (v19.85 拔除 FinMind 段 — 原打 dataset `TaiwanEconomicIndicator` 不存在於
    FinMind(SDK 2.0.4 枚舉 + 官方文件皆無此名),且 FinMind 無 PMI 資料集可替換,
    段位從未命中,只浪費一次 API 呼叫。§3.3 反捏造。)
    各來源彼此獨立、無共享狀態 → ThreadPoolExecutor 並行；關鍵路徑由原序列
    最壞 ~100s+ 降為 ~單一最慢源，順帶修掉「序列鏈超過 macro pool 70s
    timeout → PMI 被切成片段」。

    Returns
    -------
    dict
      命中：{'value': float, 'date': 'YYYY-MM-DD', 'label': str,
             'source': str, 'is_proxy': bool, 'series_id': str}
      失敗：{'_err_pmi': str, 'value': None}
    """
    from concurrent.futures import ThreadPoolExecutor as _TPE_pmi
    from concurrent.futures import as_completed as _as_completed_pmi
    from concurrent.futures import TimeoutError as _CFTimeout_pmi
    today = _dt.date.today()
    errs: list[str] = []
    # S-PROV-1 v18.254 phase 9:provenance fetched_at(orchestrator level)
    _fetched_at = pd.Timestamp.now('UTC').isoformat()

    # v18.240 SSOT：source 註冊清單抽到模組級 PMI_SOURCE_REGISTRY（見檔末）
    # 新增 source = 在 registry append 1 entry，driver 不動。
    _sources = PMI_SOURCE_REGISTRY
    _results: dict = {}
    # v19.119：race 設 _PMI_RACE_DEADLINE_S(45s)硬上限,as_completed 收在 deadline 內
    # 完成的源,逾時者 cancel + shutdown(wait=False)不等(否則 with __exit__ 會 block
    # 到最慢源 ~150s)。準時回 → orchestrator 70s 內拿得到 → 下方 durable fallback 才生效。
    _ex_pmi = _TPE_pmi(max_workers=len(_sources))
    try:
        _fut2name = {_ex_pmi.submit(_fn, today, max_age_days, errs): _nm
                     for _nm, _fn in _sources}
        try:
            for _fut in _as_completed_pmi(_fut2name, timeout=_PMI_RACE_DEADLINE_S):
                _nm = _fut2name[_fut]
                try:
                    _r = _fut.result()
                except Exception as _e_fut:
                    errs.append(f'{_nm}:future {type(_e_fut).__name__}')
                    _r = None
                if _r:
                    _results[_nm] = _r
        except _CFTimeout_pmi:
            _pending = [_fut2name[_f] for _f in _fut2name if not _f.done()]
            for _f in _fut2name:
                if not _f.done():
                    _f.cancel()
            errs.append(f'race-deadline {_PMI_RACE_DEADLINE_S}s 未回={_pending}')
            print(f'[macro_core/TW-PMI] ⏰ race {_PMI_RACE_DEADLINE_S}s 上限,'
                  f'未完成={_pending} → 走 durable/stale fallback')
    finally:
        _ex_pmi.shutdown(wait=False)   # 不等慢 thread(否則 block ~150s)
    # 依來源優先序回傳第一個命中（與原序列 fallback 語義一致）
    for _nm, _ in _sources:
        if _nm in _results:
            print(f'[macro_core/TW-PMI] ✅ 採用 {_nm}（8 源並行，依優先序）')
            # v18.225 T1：命中即 snapshot 持久化，作為後續全失敗時的 stale fallback
            _macro_cache_save('tw_pmi', _results[_nm])
            # S-PROV-1 v18.254:provenance fetched_at(orchestrator-level)
            _hit = dict(_results[_nm])
            _hit['fetched_at'] = _fetched_at
            return _hit
    err_msg = ' | '.join(errs) or 'all 8 stages failed'
    print(f'[macro_core/TW-PMI] ❌ 8 段並行全失敗：{err_msg}')
    # v18.225 T1：8 段全失敗 → 讀 stale cache（90 天 TTL），UI 端顯示 🟡 而非 🔴
    _stale = _macro_cache_load('tw_pmi')
    if _stale:
        _stale = dict(_stale)
        _stale_src = _stale.get('source', '?')
        _stale['source'] = f'stale-cache({_stale_src})'
        _stale['is_stale'] = True
        _stale['stale_err'] = err_msg
        # S-PROV-1 v18.254:fetched_at 為「本次嘗試時間」(stale 內容已含原 cached_at)
        _stale['fetched_at'] = _fetched_at
        print(f'[macro_core/TW-PMI] ⚠️ 採用 stale-cache (cached_at={_stale.get("cached_at","?")[:10]})')
        return _stale
    return {'_err_pmi': err_msg, 'value': None,
            'source': 'TW_PMI:all_tiers_failed', 'fetched_at': _fetched_at}


def _pmi_src_cier_en_monthly(today, max_age_days, errs):
    """方案 -1 (CIER 英文月度頁): 直接打 `/en/eco/taiwan-manufacturing-pmi-{月}-{年}/`。

    為什麼選這個當最高優先源？
    - CIER 是 PMI 官方發布單位（國發會委託），slug 結構自 2024 起穩定
    - HTML 簡潔（單篇報導 + 數字在標題與首段），正則命中率 >95%
    - 海外 IP 仍會 403 / cloudflare 攔截 → 走 fetch_url 自動 fallback NAS 中繼站
    - 失敗時不要拖時間：每個月最多 2 次 attempts，總共 3 個 slug
    """
    _month_names = ['january', 'february', 'march', 'april', 'may', 'june',
                    'july', 'august', 'september', 'october', 'november', 'december']
    try:
        from bs4 import BeautifulSoup
        # 嘗試 current / -1 / -2 month（PMI 報告通常於次月初公布，最近 1-2 月
        # slug 是命中熱區；再往前推 3 個月當保險）
        for _m_back in range(0, 3):
            _y, _m = today.year, today.month - _m_back
            while _m <= 0:
                _m += 12
                _y -= 1
            _slug = f'taiwan-manufacturing-pmi-{_month_names[_m - 1]}-{_y}'
            _url = f'https://www.cier.edu.tw/en/eco/{_slug}/'
            try:
                r = fetch_url(_url, timeout=12, attempts=1)
                if r is None or r.status_code != 200:
                    # v19.114:無回應原為靜默(SPEC §4:每段失敗必寫 errs)
                    errs.append(f'CIER-EN.{_slug}:HTTP{r.status_code}'
                                if r is not None
                                else f'CIER-EN.{_slug}:無回應')
                    continue
                r.encoding = 'utf-8'
                _txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
                # 模式：「Taiwan Manufacturing PMI ... 55.4」or 「PMI ... at 55.4%」
                # CIER 英文文體穩定，數值通常出現在標題與首段
                _m_pmi = _re.search(
                    r'(?:Manufacturing\s+PMI|PMI)[^.]{0,80}?'
                    r'(?:at|registered|reached|of|stood\s+at|rose\s+to|fell\s+to|was)?'
                    r'[^\d]{0,15}(\d{2}\.\d)\s*(?:%|percent)?',
                    _txt, _re.IGNORECASE)
                if _m_pmi:
                    _v = float(_m_pmi.group(1))
                    if 30 <= _v <= 70:
                        _last_date = _dt.date(_y, _m, 1)
                        if (today - _last_date).days <= max_age_days:
                            _d_iso = f'{_y}-{_m:02d}-01'
                            print(f'[macro_core/TW-PMI/CIER-EN] ✅ {_v} date={_d_iso} slug={_slug}')
                            return {'value': _v, 'date': _d_iso,
                                    'label': f'CIER Manufacturing PMI ({_month_names[_m - 1].title()} {_y})',
                                    'source': 'CIER-EN', 'is_proxy': False,
                                    'series_id': f'cier-en-{_y}{_m:02d}'}
                # v19.114:200 但無 match/值越界/過時 — 原為靜默
                errs.append(f'CIER-EN.{_slug}:no-parse/過時')
            except Exception as _e_slug:
                errs.append(f'CIER-EN.{_slug}:{type(_e_slug).__name__}')
                continue
    except Exception as e:
        errs.append(f'CIER-EN:{type(e).__name__}')
        print(f'[macro_core/TW-PMI/CIER-EN] ❌ {e}')
    return None


def _parse_dgtw_pmi_csv(text, *, today, max_age_days):
    """解析 dgtw 6100 PMI CSV（純函式,可單測）。

    探針 run 29186611230（美國 IP + NAS）實測真實格式:
        Date,PMI,NMI
        201207,47.1,-
        ...
        202606,60.7,-
    Date=YYYYMM 升序、PMI 為值、NMI 常為 '-'。取「最新且 PMI∈[30,70]」的列。
    §3.3 反捏造:值域 sanity;§2.4 age 超 max_age_days 回 None（不當新資料用）。

    Returns: {'value': float, 'date': 'YYYY-MM-01'} 或 None。
    """
    import csv as _csv2
    import datetime as _dt2
    import io as _io2
    _rows = list(_csv2.DictReader(_io2.StringIO(text)))
    if not _rows:
        return None
    _cols = list(_rows[0].keys())
    # PMI 欄:精確 'PMI' 優先,再模糊含 PMI（排除 NMI）
    _pmi_c = next((c for c in _cols if str(c).strip().upper() == 'PMI'), None) \
        or next((c for c in _cols if 'PMI' in str(c).upper()
                 and 'NMI' not in str(c).upper()), None)
    # Date 欄:名稱命中,或首列值像 YYYYMM
    _date_c = next((c for c in _cols
                    if str(c).strip().lower() in ('date', '日期', '年月')), None) \
        or next((c for c in _cols
                 if _re.match(r'^\s*20\d{4}\s*$', str(_rows[0].get(c, '')))), None)
    if not _pmi_c or not _date_c:
        return None
    _best = None   # (yyyymm_int, value, 'YYYY-MM-01')
    for _r in _rows:
        _md = _re.match(r'^\s*(20\d{2})[-/]?(\d{2})\s*$', str(_r.get(_date_c, '')))
        if not _md:
            continue
        try:
            _v = float(str(_r.get(_pmi_c, '')).strip())
        except (ValueError, TypeError):
            continue
        if not (30 <= _v <= 70):
            continue
        _ym = int(_md.group(1) + _md.group(2))
        if _best is None or _ym > _best[0]:
            _best = (_ym, round(_v, 1), f'{_md.group(1)}-{_md.group(2)}-01')
    if _best is None:
        return None
    _last = _dt2.date(_best[0] // 100, _best[0] % 100, 1)
    if (today - _last).days > max_age_days:
        return None
    return {'value': _best[1], 'date': _best[2]}


def _pmi_src_dgtw(today, max_age_days, errs):
    """方案 0 (Primary): data.gov.tw dataset/6100 官方開放資料（國發會 NDC 提供）。

    流程：① metadata API 取 resources URL → ② 下載 CSV 交 _parse_dgtw_pmi_csv 解析。
    v19.114:探針實錘現行 parser 從未真解析過活 CSV（見下 resource 段註解）→ 重接。
    """
    try:
        # metadata API 端點（多個變體：v1/v2 + .json + 直查 dataset id）
        for _meta_url in (
            'https://data.gov.tw/api/v2/rest/dataset/6100',
            'https://data.gov.tw/api/v1/rest/dataset/6100',
            'https://data.gov.tw/dataset/6100/resource',
        ):
            try:
                # v19.116:data.gov.tw 為慢速政府 API,實測回應常 12-18s。原
                # timeout=10/attempts=1 在「慢但活」時被殺 → 探針(20s/2)成功
                # 但 production 失敗的根因。放寬至 25s/2 attempts。
                _r_meta = fetch_url(_meta_url, timeout=25, attempts=2,
                                    headers={'Accept': 'application/json'})
                if _r_meta is None:
                    errs.append(f'dgtw.{_meta_url[-18:]}:無回應')
                    continue
                if _r_meta.status_code != 200:
                    errs.append(f'dgtw.{_meta_url[-18:]}:HTTP{_r_meta.status_code}')
                    continue
                try:
                    _j_meta = _r_meta.json()
                except Exception:
                    # v19.114:200 但非 JSON(如攔截頁/SPA 殼)原為靜默
                    errs.append(f'dgtw.{_meta_url[-18:]}:non-JSON')
                    continue
                # 解析 resources：常見 shape `result.resources[]` / `resources[]`
                _res = (_j_meta.get('result', {}).get('resources')
                        or _j_meta.get('resources')
                        or _j_meta.get('data', {}).get('resources')
                        or [])
                if not _res:
                    continue
                # v19.114:探針 run 29186611230 實錘 6100 resource =
                # ws.ndc.gov.tw/Download.ashx?u=...（URL 無 'csv' 字樣、format 常空）
                # → 原「format in (CSV,JSON)」+「'csv' in url 才解析」雙重 gate 使
                # 這條**活 CSV 從未被解析**（head='Date,PMI,NMI 201207,47.1,-...'）。
                # 改:收所有 resource url（CSV format 排前）、逐一下載 + 交
                # _parse_dgtw_pmi_csv 解析（不靠 URL 副檔名/format 判斷內容）。
                _urls = []
                for _it in _res:
                    _u2 = (_it.get('url') or _it.get('resourceDownloadUrl')
                           or _it.get('downloadUrl'))
                    if not _u2:
                        continue
                    if str(_it.get('format', '')).upper() == 'CSV':
                        _urls.insert(0, _u2)
                    else:
                        _urls.append(_u2)
                for _u2 in _urls:
                    _r_csv = fetch_url(_u2, timeout=25, attempts=2)  # v19.116 慢站放寬
                    if _r_csv is None or _r_csv.status_code != 200:
                        continue
                    _txt_csv = _r_csv.content.decode('utf-8-sig', errors='ignore')
                    _parsed = _parse_dgtw_pmi_csv(
                        _txt_csv, today=today, max_age_days=max_age_days)
                    if _parsed:
                        print(f"[macro_core/TW-PMI/data.gov.tw] ✅ "
                              f"{_parsed['value']} date={_parsed['date']}")
                        return {'value': _parsed['value'], 'date': _parsed['date'],
                                'label': '政府資料開放平臺 dataset/6100（國發會 NDC）',
                                'source': 'data.gov.tw/6100', 'is_proxy': True,
                                'series_id': 'dgtw-6100'}
            except Exception as _e_dg:
                errs.append(f'dgtw.{_meta_url[-15:]}:{type(_e_dg).__name__}')
    except Exception as _e_dg_outer:
        errs.append(f'dgtw_outer:{type(_e_dg_outer).__name__}')
        print(f'[macro_core/TW-PMI/data.gov.tw] ❌ outer {_e_dg_outer}')
    return None


def _pmi_src_ndc(today, max_age_days, errs):
    """方案 0b: 國發會 NDC 景氣指標 API（多 endpoint 變體 + 多 JSON shape parser）。"""
    for ndc_url in (
        'https://index.ndc.gov.tw/app/data/indicator/PMI',
        'https://index.ndc.gov.tw/app/data/indicator/pmi',
        'https://index.ndc.gov.tw/app/data/PMI/latest',
        'https://index.ndc.gov.tw/app/data/indicator/PMI/latest',
    ):
        try:
            r = fetch_url(ndc_url, timeout=12, attempts=1,
                          headers={'Accept': 'application/json'})
            if r is None:
                errs.append(f'NDC.{ndc_url[-15:]}:無回應')
                continue
            if r.status_code != 200:
                errs.append(f'NDC.{ndc_url[-15:]}:HTTP{r.status_code}')
                continue
            try:
                j = r.json()
            except Exception:
                # v19.114:200 但非 JSON(Angular SPA 殼,探針實錘)原為靜默
                errs.append(f'NDC.{ndc_url[-15:]}:non-JSON')
                continue
            # 解析多種 JSON shape：list / {data:[...]} / {items:[...]} / 單筆 dict
            items = j if isinstance(j, list) else (j.get('data') or j.get('items') or [j])
            if not items:
                continue
            latest = items[-1] if isinstance(items, list) and items else items
            if not isinstance(latest, dict):
                continue
            # 數值欄位常見 key：value / score / pmi / index / composite
            v_raw = (latest.get('value') or latest.get('score')
                     or latest.get('pmi') or latest.get('index')
                     or latest.get('composite'))
            # 日期欄位：date / yearMonth / period / month
            d_raw = (latest.get('date') or latest.get('yearMonth')
                     or latest.get('period') or latest.get('month'))
            if v_raw is None or not d_raw:
                continue
            try:
                v = float(v_raw)
            except (TypeError, ValueError):
                continue
            if not (30 <= v <= 70):
                continue
            # 日期 normalize：'2026-04' / '202604' / '2026/04' → 'YYYY-MM-01'
            d_str = str(d_raw)
            m_d = _re.search(r'(20\d{2})[-/]?(\d{2})', d_str)
            if not m_d:
                continue
            date = f'{m_d.group(1)}-{m_d.group(2)}-01'
            try:
                last_d = _dt.date(int(m_d.group(1)), int(m_d.group(2)), 1)
                if (today - last_d).days > max_age_days:
                    continue
            except Exception:
                pass
            print(f'[macro_core/TW-PMI/NDC] ✅ {v} date={date} via {ndc_url[-30:]}')
            return {'value': v, 'date': date,
                    'label': '國發會 NDC 景氣指標',
                    'source': 'NDC', 'is_proxy': True,
                    'series_id': 'ndc-pmi'}
        except Exception as e:
            errs.append(f'NDC.{ndc_url[-15:]}:{type(e).__name__}')
            print(f'[macro_core/TW-PMI/NDC/{ndc_url[-15:]}] ❌ {e}')
    return None


# (v19.113 拔除)_pmi_src_macromicro — 探針 run 29182317622 實錘
# macromicro.me host 級無回應(NAS+直連皆敗,charts/22 與 /16 同域同攔),
# 留著只是每輪賽跑多等一個必死源。user 核准提案②移除(§-1 實錯觸發)。


def _pmi_src_cier21(today, max_age_days, errs):
    """方案 2: CIER 官網首頁標題掃描(v19.113 起;原 cid=21 列表頁已下架)。"""
    try:
        from bs4 import BeautifulSoup
        # v19.113:原第一 URL news/list?cid=21 探針實錘無回應(站改版下架),
        # 僅保留首頁掃描(未實測死亡,不越權拔;標題常含最新 PMI 發布)。
        for cier_url in ('https://www.cier.edu.tw/',):
            r = fetch_url(cier_url, timeout=12, attempts=1)
            if r is None:
                errs.append(f'CIER.{cier_url[-15:]}:無回應')
                continue
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            # 標題模式：「2026年4月製造業採購經理人指數 PMI 為 49.0」
            m = _re.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,30}?'
                r'製造業[^。]{0,40}?PMI[^。]{0,30}?(\d{2}\.\d)',
                txt)
            if m:
                yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    last_date = _dt.date(int(yr), mo, 1)
                    age = (today - last_date).days
                    if age <= max_age_days:
                        date = f'{yr}-{mo:02d}-01'
                        print(f'[macro_core/TW-PMI/CIER] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'CIER 中華經濟研究院',
                                'source': 'CIER', 'is_proxy': False,
                                'series_id': 'cier-pmi'}
                    else:
                        errs.append(f'CIER:過時 {age} 天')
            else:
                # v19.114:200 但無 match — 原為靜默
                errs.append(f'CIER.{cier_url[-15:]}:no-parse')
    except Exception as e:
        errs.append(f'CIER:{type(e).__name__}')
        print(f'[macro_core/TW-PMI/CIER] ❌ {e}')
    return None


def _pmi_src_stockfeel(today, max_age_days, errs):
    """方案 3: StockFeel 股感（搜尋頁）。"""
    try:
        from bs4 import BeautifulSoup
        sf_url = 'https://www.stockfeel.com.tw/?s=%E5%8F%B0%E7%81%A3+PMI'
        r = fetch_url(sf_url, timeout=12, attempts=1)
        if r is None:
            errs.append('StockFeel:無回應')
        else:
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,40}?'
                r'(?:台灣|TW)\s*(?:製造業)?[^。]{0,40}?PMI[^。]{0,30}?(\d{2}\.\d)',
                txt)
            if m:
                yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    last_date = _dt.date(int(yr), mo, 1)
                    if (today - last_date).days <= max_age_days:
                        date = f'{yr}-{mo:02d}-01'
                        print(f'[macro_core/TW-PMI/StockFeel] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'StockFeel 股感（台灣 PMI 搜尋）',
                                'source': 'StockFeel', 'is_proxy': False,
                                'series_id': 'stockfeel-tw-pmi'}
                    errs.append('StockFeel:過時')   # v19.114:原為靜默
                else:
                    errs.append('StockFeel:no-parse或值越界')   # v19.114
            else:
                errs.append('StockFeel:no-parse')   # v19.114:200 無 match
    except Exception as e:
        errs.append(f'StockFeel:{type(e).__name__}')
        print(f'[macro_core/TW-PMI/StockFeel] ❌ {e}')
    return None


def _pmi_src_cnyes(today, max_age_days, errs):
    """方案 4: 鉅亨網新聞（搜尋台灣 PMI；JSON 解析，不需 BeautifulSoup）。"""
    try:
        cnyes_url = 'https://news.cnyes.com/api/v3/news/category/headline?limit=30&q=%E5%8F%B0%E7%81%A3+PMI'
        r = fetch_url(cnyes_url, timeout=12, attempts=1)
        if r is None:
            errs.append('Cnyes:無回應')
        else:
            try:
                d = r.json()
                items = (d.get('items', {}).get('data') or [])
                for it in items[:10]:
                    # v19.116:.get(k,'') 對「鍵存在但值=None」不套 default → 需 or ''
                    title = (it.get('title') or '') + ' ' + (it.get('summary') or '')
                    m = _re.search(
                        r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,30}?'
                        r'(?:台灣|TW)\s*(?:製造業)?[^。]{0,40}?PMI[^。]{0,30}?(\d{2}\.\d)',
                        title)
                    if m:
                        yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                        if 30 <= v <= 70 and 1 <= mo <= 12:
                            last_date = _dt.date(int(yr), mo, 1)
                            if (today - last_date).days <= max_age_days:
                                date = f'{yr}-{mo:02d}-01'
                                print(f'[macro_core/TW-PMI/Cnyes] ✅ {v} date={date}')
                                return {'value': v, 'date': date,
                                        'label': '鉅亨網新聞',
                                        'source': 'Cnyes', 'is_proxy': False,
                                        'series_id': 'cnyes-tw-pmi'}
                else:
                    # v19.114:近 10 篇皆無台灣 PMI 命中 — 原為靜默
                    errs.append('Cnyes:近10篇無PMI命中')
            except Exception as _e_cj:
                # v19.114:原 except:pass(§3.3 違憲)— API 改版須留痕
                errs.append(f'Cnyes:parse {type(_e_cj).__name__}')
                print(f'[macro_core/TW-PMI/Cnyes] ⚠️ 解析失敗: {_e_cj}')
    except Exception as e:
        errs.append(f'Cnyes:{type(e).__name__}')
        print(f'[macro_core/TW-PMI/Cnyes] ❌ {e}')
    return None


# (v19.85 拔除)原 `_pmi_src_finmind`(方案 5)— 打的 dataset
# `TaiwanEconomicIndicator` 不存在於 FinMind(SDK 2.0.4 Dataset 枚舉 + 官方
# 文件皆無此名),自建立起從未命中;FinMind 亦無 PMI 資料集可替換 → 整段移除,
# PMI_SOURCE_REGISTRY 同步 10 → 9 源。git history 可查回。§3.3 反捏造。


def _pmi_src_cier8(today, max_age_days, errs):
    """方案 6: CIER cid=8（PMI 專屬類別，非 cid=21 新聞稿）。"""
    try:
        from bs4 import BeautifulSoup
        for cier_url in ('https://www.cier.edu.tw/news/list?cid=8',
                         'https://www.cier.edu.tw/news/list?cid=8&page=1'):
            r = fetch_url(cier_url, timeout=12, attempts=1)
            if r is None:
                errs.append(f'CIER-cid8.{cier_url[-15:]}:無回應')
                continue
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,40}?'
                r'PMI[^。]{0,30}?(\d{2}\.\d)',
                txt)
            if m:
                yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    last_date = _dt.date(int(yr), mo, 1)
                    if (today - last_date).days <= max_age_days:
                        date = f'{yr}-{mo:02d}-01'
                        print(f'[macro_core/TW-PMI/CIER-cid8] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'CIER 中華經濟研究院（PMI 專欄）',
                                'source': 'CIER', 'is_proxy': False,
                                'series_id': 'cier-pmi-cid8'}
            else:
                errs.append(f'CIER-cid8.{cier_url[-15:]}:no-parse')   # v19.114
    except Exception as e:
        errs.append(f'CIER-cid8:{type(e).__name__}')
        print(f'[macro_core/TW-PMI/CIER-cid8] ❌ {e}')
    return None


def _pmi_src_moneydj(today, max_age_days, errs):
    """方案 7: MoneyDJ 財經知識庫（搜尋頁，HTML 含 PMI 圖表 alt）。"""
    try:
        from bs4 import BeautifulSoup
        mdj_url = ('https://www.moneydj.com/KMDJ/Search/SearchListNew.aspx'
                   '?keyword=%E5%8F%B0%E7%81%A3PMI&type=knowledge')
        r = fetch_url(mdj_url, timeout=12, attempts=1)
        if r is None:
            errs.append('MoneyDJ:無回應')
        else:
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月.{0,40}?'
                r'(?:台灣|TW)\s*(?:製造業)?[^。]{0,40}?PMI[^。]{0,30}?(\d{2}\.\d)',
                txt)
            if m:
                yr, mo, v = m.group(1), int(m.group(2)), float(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    last_date = _dt.date(int(yr), mo, 1)
                    if (today - last_date).days <= max_age_days:
                        date = f'{yr}-{mo:02d}-01'
                        print(f'[macro_core/TW-PMI/MoneyDJ] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'MoneyDJ 財經知識庫',
                                'source': 'MoneyDJ', 'is_proxy': False,
                                'series_id': 'mdj-tw-pmi'}
            else:
                errs.append('MoneyDJ:no-parse')   # v19.114:200 無 match 原為靜默
    except Exception as e:
        errs.append(f'MoneyDJ:{type(e).__name__}')
        print(f'[macro_core/TW-PMI/MoneyDJ] ❌ {e}')
    return None


# v18.240 SSOT — TW-PMI 來源註冊表
# 順序即優先序（越前面越權威）；fetch_tw_pmi 並行賽跑後依此序取第一個命中。
# 各 handler 線程安全：只讀 today/max_age_days、對共享 errs append、回傳新 dict 或 None。
# 新增 source：append 1 entry 即可，fetch_tw_pmi driver 0 改。
PMI_SOURCE_REGISTRY: list[tuple[str, Callable]] = [
    ('CIER-EN',     _pmi_src_cier_en_monthly),
    ('data.gov.tw', _pmi_src_dgtw),
    ('NDC',         _pmi_src_ndc),
    ('CIER',        _pmi_src_cier21),
    ('StockFeel',   _pmi_src_stockfeel),
    ('Cnyes',       _pmi_src_cnyes),
    ('CIER-cid8',   _pmi_src_cier8),
    ('MoneyDJ',     _pmi_src_moneydj),
]


# ══════════════════════════════════════════════════════════════
# 純數學工具(不需要網路,兩邊共用)
# ══════════════════════════════════════════════════════════════

def zscore(s: pd.Series) -> pd.Series:
    """標準分數(std=0 時回傳全 0,避免除零)。

    D2 v18.437:實作下沉 shared.stats_helpers.zscore(SSOT);本處保留為向後相容
    re-export(macro_core 公開數學工具 + test 介面),委派唯一實作避免雙寫。
    """
    from shared.stats_helpers import zscore as _z
    return _z(s)


def trend_arrow(vals: list[float]) -> str:
    """
    依最近 N 點走勢給出口語化趨勢標記。
    回傳: '持續上升 ↑' / '持續下降 ↓' / '最近反彈 ↗' / '最近回落 ↘' / ''
    """
    if len(vals) < 3:
        return ""
    diffs = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    pos = sum(1 for d in diffs if d > 0)
    neg = sum(1 for d in diffs if d < 0)
    if pos >= len(diffs) - 1:
        return "持續上升 ↑"
    if neg >= len(diffs) - 1:
        return "持續下降 ↓"
    return "最近反彈 ↗" if diffs[-1] > 0 else "最近回落 ↘"


def recession_probability(spread_10y3m: Optional[float]) -> Optional[float]:
    """
    用 10Y-3M 利差做 logistic 回歸估算未來 12 個月衰退機率(%)。
    spread_10y3m 為 None 時回傳 None。
    """
    if spread_10y3m is None:
        return None
    logit = RECESSION_LOGIT_COEF_SPREAD * spread_10y3m + RECESSION_LOGIT_COEF_INTERCEPT
    return round(1 / (1 + math.exp(-logit)) * 100, 1)


def spread_series(
    df_long: pd.DataFrame,
    df_short: pd.DataFrame,
    n_pts: int = 60,
) -> pd.Series:
    """
    計算兩個 FRED 序列的利差時序。
    優先用月頻對齊;若月頻 inner join 為空(例如 short 序列為日頻 TB3MS)
    則退回 merge_asof 容忍 40 天的回溯對齊。
    """
    if df_long.empty or df_short.empty:
        return pd.Series(dtype=float)

    dl = df_long[["date", "value"]].set_index("date").rename(columns={"value": "v_l"})
    ds = df_short[["date", "value"]].set_index("date").rename(columns={"value": "v_s"})
    dl_m = dl.resample("ME").last().ffill()
    ds_m = ds.resample("ME").last().ffill()
    merged = dl_m.join(ds_m, how="inner").dropna()
    if not merged.empty:
        return (merged["v_l"] - merged["v_s"]).tail(n_pts)

    dl2 = df_long[["date", "value"]].rename(columns={"value": "v_l"}).sort_values("date")
    ds2 = df_short[["date", "value"]].rename(columns={"value": "v_s"}).sort_values("date")
    m = pd.merge_asof(
        dl2, ds2, on="date",
        tolerance=pd.Timedelta(days=MACRO_MERGE_ASOF_TOLERANCE_DAYS), direction="backward",
    ).dropna().set_index("date")
    return (m["v_l"] - m["v_s"]).tail(n_pts)


# ══════════════════════════════════════════════════════════════
# 統一 snapshot schema 工具
# ══════════════════════════════════════════════════════════════

def make_indicator(
    key: str,
    name: str,
    value: float,
    *,
    prev: Optional[float] = None,
    unit: str = "",
    type_: str = "同時",
    date: str = "",
    series: Optional[pd.Series] = None,
    desc: str = "",
    weight: float = 1.0,
) -> dict:
    """
    建立統一格式的指標 dict。

    fund 端原本就用富 dict(value/prev/trend/series/...),stock 端用扁平 float。
    我們以富 dict 為共同 schema,扁平結構可由 flatten_snapshot() 動態產生。
    """
    trend = ""
    if series is not None and len(series) >= 3:
        trend = trend_arrow([float(x) for x in series.tail(MACRO_TREND_LOOKBACK_PERIODS).tolist()])
    return {
        "key":    key,
        "name":   name,
        "value":  value,
        "prev":   prev,
        "unit":   unit,
        "type":   type_,
        "date":   date,
        "desc":   desc,
        "trend":  trend,
        "series": series,
        "weight": weight,
    }


def flatten_snapshot(rich: dict) -> dict:
    """
    將富 dict snapshot 轉為扁平 dict(key 小寫),方便相容 stock 端
    macro_alert.py / macro_state_locker.py 既有 API。

    rich = {"VIX": {"value": 28.3, ...}, "CPI": {"value": 3.1, ...}}
    →     {"vix": 28.3, "cpi": 3.1}
    """
    out: dict = {}
    for k, v in (rich or {}).items():
        if isinstance(v, dict) and v.get("value") is not None:
            out[k.lower()] = v["value"]
    return out
