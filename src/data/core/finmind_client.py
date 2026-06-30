"""src/data/core/finmind_client.py — FinMind API v4 統一 client(L1 SSOT)。

D5 v18.437:收斂全專案散落 ~12 處手寫的
`requests.get(FINMIND_API_URL, params=..., headers=..., timeout=...)
 → .json() → status==200 → pd.DataFrame(data)` 請求樣板。

設計原則 — **零行為漂移**:
各 caller 原本的差異(timeout / 是否重試 / 是否帶 end_date / 日期格式)全部以
**參數**保留,本 client 只集中「request + status 判讀 + DataFrame 構造」這段唯一重複的
boilerplate。caller 端各自的 parse / 欄位處理仍留在原處(本來就 site-specific,非重複)。

歷史:原始 helper 位於 `leading_indicators.finmind_get`(總經模組,放錯位置 —
被 data/UI 多層 caller 共用卻住在 macro 檔)。此處為正規 L1 home;
`leading_indicators.finmind_get` 改為 thin re-export,行為(timeout=25, retries=2)不變。

§8.2:L1 Data,可被 L1/L2/L3/L5 import;不 import streamlit / 上層。

適用範圍(D5 step2 實證結論 — 勿再機械收斂)
=============================================
本 client 僅適用「plain requests + 以 JSON body `status==200` 判讀」的 FinMind v4 GET。
已收斂 4 站:monthly_revenue_fetcher ×2、data_loader 月營收方案B、data_loader 季財報REST。

以下 ~14 站「看似重複,語意實不同」,經實測(暫遷後 7 測試紅 → 全數還原)確認**不可收斂**,維持原樣:
- **Proxy Session 站**(`_bps_dl()` / `_bps()` / `_make_proxy_session()` / `_rq_f` / `proxy_helper.fetch_url`):
  帶 NAS Squid proxy 路由 + Retry adapter + `verify=False`(geo-block 繞道核心)。
  本 client 用 plain `requests.get`(verify=True、無代理、無 retry)→ 會丟失代理鏈直接失敗。
  涵蓋 data_loader(_fetch_finmind_inst/price_raw、月營收方案0、get_quarterly_extra、
  fetch_financial_statements 多走 _bps_dl)、app_stock_fetchers(fetch_dividend_data/financials)、
  daily_data_fetchers(_fetch_otc_via_finmind)、macro_core(_pmi_src_finmind 走 fetch_url)。
- **HTTP-status-gating 站**:gate on `resp.status_code==200`(HTTP)而非 JSON `status==200`,
  或消費 status_code 區分 401/403 token 錯誤 / 消費 JSON `msg` 區分額度上限 vs 無資料。
  與本 client 的 JSON-status 語意不同,收斂會改變判讀。涵蓋 share_capital_fetcher、
  tab_stock_picker(_fetch_quarterly_is / _check_* 等)、data_loader(fetch_industry_category /
  fetch_bps_from_finmind)。

若未來要納入上述:需先讓 client 支援「proxy session 注入」+「HTTP-status 模式 / 回傳 status_code」
(屬另案設計,§8 先對齊),**禁止為了 DRY 硬收而丟失代理 / 改變 status 判讀**。
"""
from __future__ import annotations

import time

import pandas as pd

from src.config import FINMIND_API_URL

try:
    import requests
except ImportError:  # 純 .py 環境護欄(同 §1 fail-safe:無 requests → 空結果而非炸)
    requests = None  # type: ignore

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko)")


def _to_dash(d) -> str | None:
    """日期正規化:'YYYYMMDD' / 'YYYY-MM-DD' / date-like → 'YYYY-MM-DD';None → None。

    支援兩種 caller 慣例(leading_indicators 用 YMD 緊湊;多數 fetcher 用 dash)。
    """
    if d is None:
        return None
    s = str(d)
    if '-' in s:
        return s
    if len(s) == 8 and s.isdigit():
        return f'{s[:4]}-{s[4:6]}-{s[6:]}'
    return s


def finmind_get(dataset: str, *, data_id=None, start_date=None, end_date=None,
                token: str = "", timeout: int = 20, retries: int = 1) -> "pd.DataFrame":
    """FinMind v4 `data` endpoint 統一查詢。

    Args:
        dataset:    FinMind dataset 名(必填)。
        data_id:    股票/期貨代號;None / '' → 不送(避免 422)。
        start_date: 'YYYY-MM-DD' 或 'YYYYMMDD' 或 None(None → 不送)。
        end_date:   同上;None → 不送(保留 caller 原本省略 end_date 的行為)。
        token:      FinMind API token;空 → 不送(免費額度)。
        timeout:    單次請求秒數(預設 20,對齊多數 fetcher)。
        retries:    嘗試次數(預設 1 = 不重試;leading_indicators 等傳 2)。

    Returns:
        status==200 → `pd.DataFrame(data)`(可能空);否則 / 例外 / 無 requests → 空 DataFrame。
        §1 Fail-safe:回空 DataFrame 而非 raise,由 caller 依空判斷走 fallback(沿用原行為)。
    """
    if requests is None:
        print("[FinMind] requests 未安裝,回空 DataFrame")
        return pd.DataFrame()

    params: dict = {"dataset": dataset}
    _sd, _ed = _to_dash(start_date), _to_dash(end_date)
    if _sd:
        params["start_date"] = _sd
    if _ed:
        params["end_date"] = _ed
    if data_id:
        params["data_id"] = data_id
    if token:
        params["token"] = token

    hdrs = {"User-Agent": _UA, "Accept": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"

    _attempts = max(1, retries)
    for _i in range(_attempts):
        try:
            r = requests.get(FINMIND_API_URL, params=params, headers=hdrs, timeout=timeout)
            d = r.json()
            if d.get("status") == 200:
                df = pd.DataFrame(d.get("data", []))
                print(f"[FinMind] {dataset} ✅ {len(df)} rows")
                return df
            print(f"[FinMind] {dataset} HTTP={r.status_code} "
                  f"status={d.get('status')} msg={d.get('msg', '')}")
            return pd.DataFrame()
        except Exception as _e:
            print(f"[FinMind] {dataset} attempt {_i + 1} ❌ {type(_e).__name__}: {_e}")
            if _i == _attempts - 1:
                return pd.DataFrame()
            time.sleep(1)
    return pd.DataFrame()
