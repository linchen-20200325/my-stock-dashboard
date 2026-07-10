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
from src.data.core.finmind_client import finmind_get  # D5 step2 v18.437 SSOT client


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
        # D14c v19.75(review):原靜默回空 → 補 log(§5 可觀測性,診斷可分辨「無 token」vs「API 失敗」)
        print(f"[mrev-fetcher] {stock_id} 無 FinMind token(FINMIND_TOKEN/FM_TOKEN 皆空)→ 回空")
        return pd.DataFrame()
    _end = _dt.date.today()
    _start = (_end - _dt.timedelta(days=months * 31 + 31)).strftime("%Y-%m-%d")
    try:
        _df = finmind_get(
            "TaiwanStockMonthRevenue",
            data_id=stock_id,
            start_date=_start,
            token=_tok,
            timeout=20,
        )
        if _df.empty:
            return pd.DataFrame()
        if "revenue" not in _df.columns:
            return pd.DataFrame()
        if "date" not in _df.columns and "revenue_year" in _df.columns:
            _df["date"] = (
                _df["revenue_year"].astype(str) + "-" +
                _df["revenue_month"].astype(str).str.zfill(2) + "-01"
            )
        _df["date"] = pd.to_datetime(_df["date"], errors="coerce")
        # D13 v19.75:revenue 強制 float64 — FinMind JSON 整數營收會推成 int64,
        # 違反 MonthlyRevenueSchema float 契約 → blocking 模式整檔誤殺
        # (同 Fund repo v19.172 FRED 全整數 series 教訓;非數值 coerce 成 NaN 由下行 dropna 接手)
        _df["revenue"] = pd.to_numeric(_df["revenue"], errors="coerce").astype("float64")
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
        # D13 v19.75(review,user 核准):log-mode → blocking。schema 違反 → 整檔
        # 棄用回空(§1 錯值比缺值危險),下游走既有「無資料」路徑 + 診斷 Tab 亮紅。
        try:
            from src.compute.risk.schemas import validate_or_reject, MonthlyRevenueSchema
            _result = validate_or_reject(_result, MonthlyRevenueSchema,
                                         label=f'fetch_monthly_revenue:{stock_id}')
        except ImportError as _e_sch:
            print(f'[mrev-fetcher] schema 模組不可用,跳過驗證: {_e_sch}')
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
        # D14c v19.75(review):同單檔版,無 token 補 log 不再靜默
        print("[mrev-fetcher] batch 無 FinMind token(FINMIND_TOKEN/FM_TOKEN 皆空)→ 回空")
        return pd.DataFrame()
    _end = _dt.date.today()
    _start = (_end - _dt.timedelta(days=months * 31 + 31)).strftime("%Y-%m-%d")
    try:
        _df = finmind_get(
            "TaiwanStockMonthRevenue",
            start_date=_start,
            token=_tok,
            timeout=60,
        )
        if _df.empty:
            print("[mrev-fetcher] batch fetch 回空(status!=200 或無資料)")
            return pd.DataFrame()
        if "revenue" not in _df.columns or "stock_id" not in _df.columns:
            return pd.DataFrame()
        if "date" not in _df.columns and "revenue_year" in _df.columns:
            _df["date"] = (
                _df["revenue_year"].astype(str) + "-" +
                _df["revenue_month"].astype(str).str.zfill(2) + "-01"
            )
        _df["date"] = pd.to_datetime(_df["date"], errors="coerce")
        # D13 v19.75:同單檔版,revenue 強制 float64(schema float 契約;int64 會誤殺)
        _df["revenue"] = pd.to_numeric(_df["revenue"], errors="coerce").astype("float64")
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
        # D13 v19.75(review,user 核准):log-mode → blocking(batch 含 stock_id 多檔)。
        # 取首檔 36 列當代表驗(完整驗會誤判 date dup 跨股);樣本違反 = 系統性 shape
        # 問題 → 整批棄用回空(§1),下游走既有「無資料」路徑。
        try:
            from src.compute.risk.schemas import validate_or_reject, MonthlyRevenueSchema
            _sample_v = validate_or_reject(_result_b.head(36), MonthlyRevenueSchema,
                                           label='fetch_batch_monthly_revenue:sample')
            if _sample_v.empty and not _result_b.empty:
                print('[mrev-fetcher] batch 樣本 schema 違反 → 整批棄用(§1 錯值比缺值危險)')
                return _result_b.iloc[0:0]
        except ImportError as _e_sch:
            print(f'[mrev-fetcher] schema 模組不可用,跳過驗證: {_e_sch}')
        return _result_b
    except Exception as _e:
        print(f"[mrev-fetcher] batch fetch 失敗: {type(_e).__name__}: {_e}")
        return pd.DataFrame()
