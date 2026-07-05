"""src/data/stock/mops_bulk_fetcher.py — MOPS 全市場財報彙總 bulk fetcher(L1 Data)。

全台股基本面選股網 Phase 1:一次抓「整季、全上市/上櫃公司」的兩張彙總表,供
L2 fundamental_prescreen 算 4 項基本面(負債比 / 三率 / 淨流動值 / 估值 EPS)。

資料源(2026-07-04 GitHub Actions POC 三輪實測確認,見 scripts/poc_mops_bulk.py):
  - 網域 mopsov.twse.com.tw(舊 mops.twse.com.tw 回錯誤頁)
  - ajax_t163sb04 = 綜合損益表彙總 → 營收/營業成本/毛利/營益/淨利/EPS
  - ajax_t163sb05 = 資產負債表彙總 → 資產總計/負債總計/流動資產/權益總計
  - POST 帶 TYPEK(sii=上市 / otc=上櫃)+ year(民國)+ season(01~04)
  - 全市場一次回(上市 ~1011 檔、上櫃 ~740 檔),GitHub runner IP 不被 geo-block

§8.2:L1 Data,不 import streamlit。批次腳本(GitHub Actions)直連即可(POC 證實);
若未來從 app 端呼叫需 geo-block 中繼,再接 proxy_helper(升級觸發,先不做)。

§1 Fail-loud:抓不到 / 解析空 → 回空 DataFrame + print 說明,由 caller(批次腳本)
決定是否保留上季 parquet,不靜默偽裝成功。
"""
from __future__ import annotations

import re
import time
from io import StringIO

import pandas as pd

try:
    import requests
except ImportError:  # 純環境護欄
    requests = None  # type: ignore

MOPS_BULK_BASE = "https://mopsov.twse.com.tw/mops/web/"
MOPS_IS_ENDPOINT = "ajax_t163sb04"   # 綜合損益表彙總
MOPS_BS_ENDPOINT = "ajax_t163sb05"   # 資產負債表彙總

# 重試 / 退避(MOPS 對 CI runner 有間歇性連線逾時 / 短暫封鎖;§5 冪等,重抓不產重複)。
# 純網路例外(timeout / 連線重置)與 5xx / 429 才重試;其餘 4xx 視為永久錯誤直接放棄。
_MAX_RETRIES = 4          # 總嘗試次數
_BACKOFF_BASE_SEC = 8     # 第 n 次失敗後等 base * n 秒(8/16/24…),避開短暫節流
_RETRY_STATUS = {429, 500, 502, 503, 504}

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# 產業表欄名 → 標準欄名（子字串比對；不同產業別欄名略異，取第一個命中）
_IS_FIELD_MAP = {
    "revenue":      ["營業收入"],
    "gross_profit": ["營業毛利（毛損）淨額", "營業毛利（毛損）", "營業毛利"],
    "op_income":    ["營業利益"],
    "net_income":   ["本期淨利（淨損）", "本期淨利", "稅後淨利"],
    "eps":          ["基本每股盈餘（元）", "基本每股盈餘"],
}
_BS_FIELD_MAP = {
    "total_assets": ["資產總計", "資產總額"],
    "total_liab":   ["負債總計", "負債總額"],
    "current_assets": ["流動資產"],
    "total_equity": ["權益總計", "權益總額"],
}

_CODE_RE = re.compile(r"^\d{4,6}[A-Z]?$")


def _flatten_col(col) -> str:
    """MultiIndex / tuple 欄名攤平成單一字串。"""
    if isinstance(col, tuple):
        parts = [str(c) for c in col if c is not None and "Unnamed" not in str(c)]
        return "".join(dict.fromkeys(parts))  # 去重保序
    return str(col)


def _find_col(cols: list[str], keys: list[str]) -> str | None:
    for key in keys:
        for c in cols:
            if key in c:
                return c
    return None


def _parse_mops_aggregate(html: str, field_map: dict[str, list[str]]) -> pd.DataFrame:
    """純解析:MOPS 彙總 HTML(多產業別表格)→ 每檔一列的長表。

    回傳欄:stock_id + field_map 的標準欄(缺該欄 → NaN)。可單元測試,無 I/O。
    """
    try:
        tables = pd.read_html(StringIO(html), flavor="lxml")
    except Exception as _e:
        print(f"[mops_bulk] read_html 失敗:{type(_e).__name__}: {_e}")
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for t in tables:
        t = t.copy()
        t.columns = [_flatten_col(c) for c in t.columns]
        code_col = _find_col(list(t.columns), ["公司代號", "公司 代號", "代號"])
        if code_col is None:
            continue
        out = pd.DataFrame()
        out["stock_id"] = t[code_col].astype(str).str.strip()
        out = out[out["stock_id"].str.match(_CODE_RE)]
        if out.empty:
            continue
        for std_name, keys in field_map.items():
            src = _find_col(list(t.columns), keys)
            if src is not None:
                out[std_name] = pd.to_numeric(
                    t.loc[out.index, src].astype(str).str.replace(",", "", regex=False),
                    errors="coerce",
                )
            else:
                out[std_name] = pd.NA
        frames.append(out)

    if not frames:
        print("[mops_bulk] 解析後無任何含『公司代號』的表格")
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True, sort=False)
    df = df.drop_duplicates(subset="stock_id", keep="first").reset_index(drop=True)
    return df


def _fetch_bulk(endpoint: str, typek: str, roc_year: int, season: int,
                *, timeout: int = 60, max_retries: int = _MAX_RETRIES,
                _sleep=time.sleep) -> str | None:
    """POST MOPS 彙總 endpoint,回原始 HTML;失敗回 None。

    對暫時性失敗(網路 timeout / 連線重置 / 5xx / 429)重試 max_retries 次、
    退避 _BACKOFF_BASE_SEC * n 秒;永久性 4xx(如 400/404)不重試直接放棄。
    """
    if requests is None:
        print("[mops_bulk] requests 未安裝")
        return None
    payload = {
        "encodeURIComponent": "1", "step": "1", "firstin": "1", "off": "1",
        "isnew": "false", "TYPEK": typek,
        "year": str(roc_year), "season": f"{season:02d}",
    }
    hdrs = {"User-Agent": _UA, "Accept": "text/html",
            "Referer": MOPS_BULK_BASE, "Origin": "https://mopsov.twse.com.tw"}
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(MOPS_BULK_BASE + endpoint, data=payload,
                              headers=hdrs, timeout=timeout)
            if r.status_code == 200:
                return r.text
            if r.status_code in _RETRY_STATUS and attempt < max_retries:
                wait = _BACKOFF_BASE_SEC * attempt
                print(f"[mops_bulk] {endpoint} {typek} HTTP={r.status_code} "
                      f"(第 {attempt}/{max_retries} 次) → 等 {wait}s 重試")
                _sleep(wait)
                continue
            print(f"[mops_bulk] {endpoint} {typek} HTTP={r.status_code} → 放棄")
            return None
        except Exception as _e:
            if attempt < max_retries:
                wait = _BACKOFF_BASE_SEC * attempt
                print(f"[mops_bulk] {endpoint} {typek} ❌ {type(_e).__name__} "
                      f"(第 {attempt}/{max_retries} 次) → 等 {wait}s 重試")
                _sleep(wait)
                continue
            print(f"[mops_bulk] {endpoint} {typek} ❌ {type(_e).__name__}: {_e} → 放棄")
            return None
    return None


def _fetch_and_parse(endpoint: str, field_map: dict, typek: str,
                     roc_year: int, season: int, tag: str) -> pd.DataFrame:
    html = _fetch_bulk(endpoint, typek, roc_year, season)
    if not html:
        return pd.DataFrame()
    df = _parse_mops_aggregate(html, field_map)
    if df.empty:
        return df
    # provenance(schema-additive,對齊 S-PROV-1 慣例)
    df["market"] = typek
    df["roc_year"] = roc_year
    df["season"] = season
    df["source"] = f"MOPS:{tag}:{typek}:Y{roc_year}S{season:02d}"
    df["fetched_at"] = pd.Timestamp.now("UTC").isoformat()
    return df


def fetch_mops_income_bulk(typek: str, roc_year: int, season: int) -> pd.DataFrame:
    """綜合損益表彙總(全市場一次)→ stock_id + revenue/gross_profit/op_income/net_income/eps。

    typek: 'sii'(上市)/ 'otc'(上櫃)。roc_year: 民國年。season: 1~4。
    """
    return _fetch_and_parse(MOPS_IS_ENDPOINT, _IS_FIELD_MAP, typek,
                            roc_year, season, "t163sb04")


def fetch_mops_balance_bulk(typek: str, roc_year: int, season: int) -> pd.DataFrame:
    """資產負債表彙總(全市場一次)→ stock_id + total_assets/total_liab/current_assets/total_equity。"""
    return _fetch_and_parse(MOPS_BS_ENDPOINT, _BS_FIELD_MAP, typek,
                            roc_year, season, "t163sb05")
