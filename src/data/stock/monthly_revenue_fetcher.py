"""src/data/stock/monthly_revenue_fetcher.py — 月營收 L1 fetcher(v18.400 U1).

從 `src/ui/tabs/monthly_revenue_screener.py` 抽出 fetch 層(原 L1 邏輯誤放 L5),
配合 U1 修反向違憲(原 `src/compute/health/mj_trend_score.py:250` 反向 import L5)。

§8.2 layer:L1 Data — FinMind TaiwanStockMonthRevenue 抓單股 / 全市場月營收。
§8.2.A EX-CACHE-1 letter-compliant(try/except + `_NoOpST` fallback + secrets dict)。
§2.2 / S-PROV-1 phase 19 provenance(source + fetched_at)注入 DataFrame.attrs。

對外 API:
- `fetch_monthly_revenue(stock_id, months=18) -> pd.DataFrame`:單股 N 月營收
- `fetch_batch_monthly_revenue(months=18) -> pd.DataFrame`:全市場(不帶 data_id)
"""
from __future__ import annotations

import datetime as _dt
import os

import pandas as pd
import requests

try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

from shared.ttls import TTL_6HOUR

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


def _get_token() -> str:
    """讀 FinMind token:FINMIND_TOKEN > FM_TOKEN > ''。"""
    return (os.environ.get("FINMIND_TOKEN", "") or
            os.environ.get("FM_TOKEN", ""))


@st.cache_data(ttl=TTL_6HOUR, show_spinner=False)
def fetch_monthly_revenue(stock_id: str, months: int = 18) -> pd.DataFrame:
    """抓單股近 N 月營收(FinMind TaiwanStockMonthRevenue)。

    Args:
        stock_id: 純台股代碼如 '2330'
        months: 回溯月數(預設 18 = 12 YoY 基期 + 6 分析窗口緩衝)

    Returns:
        DataFrame columns: date / revenue / revenue_year / revenue_month
        失敗回空 DataFrame
    """
    _tok = _get_token()
    if not _tok:
        return pd.DataFrame()
    _end = _dt.date.today()
    _start = (_end - _dt.timedelta(days=months * 31 + 31)).strftime("%Y-%m-%d")
    try:
        _r = requests.get(
            FINMIND_URL,
            params={
                "dataset": "TaiwanStockMonthRevenue",
                "data_id": stock_id,
                "start_date": _start,
                "token": _tok,
            },
            headers={"Authorization": f"Bearer {_tok}"},
            timeout=20,
        )
        _j = _r.json()
        if _j.get("status") != 200 or not _j.get("data"):
            return pd.DataFrame()
        _df = pd.DataFrame(_j["data"])
        if "revenue" not in _df.columns:
            return pd.DataFrame()
        if "date" not in _df.columns and "revenue_year" in _df.columns:
            _df["date"] = (
                _df["revenue_year"].astype(str) + "-" +
                _df["revenue_month"].astype(str).str.zfill(2) + "-01"
            )
        _df["date"] = pd.to_datetime(_df["date"], errors="coerce")
        _df = _df.dropna(subset=["date", "revenue"]).sort_values("date").reset_index(drop=True)
        _result = _df[["date", "revenue", "revenue_year", "revenue_month"]] if all(
            c in _df.columns for c in ["revenue_year", "revenue_month"]
        ) else _df[["date", "revenue"]]
        # v18.356 PR-Q5b S-PROV-1 phase 19
        try:
            _result.attrs.setdefault('source', 'FinMind:TaiwanStockMonthRevenue:single')
            _result.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        return _result
    except Exception as _e:
        print(f"[mrev-fetcher] fetch {stock_id} 失敗: {type(_e).__name__}: {_e}")
        return pd.DataFrame()


@st.cache_data(ttl=TTL_6HOUR, show_spinner=False)
def fetch_batch_monthly_revenue(months: int = 18) -> pd.DataFrame:
    """一次抓全市場月營收(不帶 data_id,避開逐股迴圈)。

    Args:
        months: 回溯月數(預設 18)

    Returns:
        DataFrame columns: stock_id / date / revenue(多股長表)
        失敗或無 token 回空 DataFrame
    """
    _tok = _get_token()
    if not _tok:
        return pd.DataFrame()
    _end = _dt.date.today()
    _start = (_end - _dt.timedelta(days=months * 31 + 31)).strftime("%Y-%m-%d")
    try:
        _r = requests.get(
            FINMIND_URL,
            params={
                "dataset": "TaiwanStockMonthRevenue",
                "start_date": _start,
                "token": _tok,
            },
            headers={"Authorization": f"Bearer {_tok}"},
            timeout=60,
        )
        _j = _r.json()
        if _j.get("status") != 200 or not _j.get("data"):
            print(f"[mrev-fetcher] batch status={_j.get('status')} msg={_j.get('msg', '')}")
            return pd.DataFrame()
        _df = pd.DataFrame(_j["data"])
        if "revenue" not in _df.columns or "stock_id" not in _df.columns:
            return pd.DataFrame()
        if "date" not in _df.columns and "revenue_year" in _df.columns:
            _df["date"] = (
                _df["revenue_year"].astype(str) + "-" +
                _df["revenue_month"].astype(str).str.zfill(2) + "-01"
            )
        _df["date"] = pd.to_datetime(_df["date"], errors="coerce")
        _df = _df.dropna(subset=["date", "revenue", "stock_id"])
        _result_b = _df[["stock_id", "date", "revenue"]].sort_values(
            ["stock_id", "date"]
        ).reset_index(drop=True)
        # v18.356 PR-Q5b S-PROV-1 phase 19
        try:
            _result_b.attrs.setdefault('source', 'FinMind:TaiwanStockMonthRevenue:batch(all-market)')
            _result_b.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        return _result_b
    except Exception as _e:
        print(f"[mrev-fetcher] batch fetch 失敗: {type(_e).__name__}: {_e}")
        return pd.DataFrame()
