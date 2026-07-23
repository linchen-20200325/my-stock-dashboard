"""src/data/macro/foreign_flow_fetcher.py — 外資資金流量 fetcher(L1 Data)。

v18.425 Phase 2 Batch 3a:從 `src/ui/tabs/hot_money.py:135`(L5 UI)抽出。

**動機**:Phase 1 §0.11 audit 點名 R-UI-FETCH-1 — L5 UI Tab 不應定義 L1 fetcher
(違反 §8.2 + EX-PASSTHRU-1 規範只允許 pass-through,不允許新建 fetcher)。

**回溯相容**:`src/ui/tabs/hot_money.py:fetch_foreign_flow_series` 改 thin re-export,
caller(本檔 `render_hot_money_section` / tab_macro.py)無需改 import path。

**§8.2.A EX-CACHE-1 letter compliance**:條件 import streamlit + _NoOpST fallback,
僅用 `@st.cache_data` 裝飾器(無 UI 呼叫)。

對外 API:
- `fetch_foreign_flow_series(days: int, token: str) -> tuple[pd.DataFrame, str]`
  回 (df[date, foreign_net_yi 億元], error_msg or "")
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd

# §8.2.A EX-CACHE-1:條件 import streamlit + 無 UI 呼叫 fallback。
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
    st = _NoOpST()  # noqa

from shared.ttls import TTL_30MIN
from src.data.core.provenance import prov_log


@st.cache_data(ttl=TTL_30MIN, show_spinner=False)
def fetch_foreign_flow_series(days: int, token: str) -> tuple[pd.DataFrame, str]:
    """抓最近 N 天外資買賣超(複用 leading_indicators.finmind_get)。

    Args:
        days: 抓取天數(實際多抓 14 天緩衝日曆 vs 交易日差異)
        token: FinMind API token

    Returns:
        (df[date, foreign_net_yi 億元], error_msg or "")
    """
    try:
        from src.data.macro import finmind_get
        end_d = _dt.date.today()
        start_d = end_d - _dt.timedelta(days=days + 14)
        df = finmind_get("TaiwanStockTotalInstitutionalInvestors",
                          "", start_d.strftime("%Y%m%d"),
                          end_d.strftime("%Y%m%d"), token or "")
    except Exception as e:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind 抓取失敗:{e}"

    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "無資料回傳(可能為非交易日區間)"

    # 過濾「外資」類別(含 Foreign_Investor / 外資及陸資 等變體)
    name_col = next((c for c in ("name", "institutional_investors") if c in df.columns), None)
    if name_col is None:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind 缺類別欄(cols={list(df.columns)[:8]})"
    mask = df[name_col].astype(str).str.contains("Foreign|外資", case=False, na=False, regex=True)
    fdf = df.loc[mask].copy()
    if fdf.empty:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "FinMind 無 Foreign 類別資料"

    fdf["net"] = pd.to_numeric(fdf["buy"], errors="coerce") - pd.to_numeric(fdf["sell"], errors="coerce")
    out = (fdf.groupby("date", as_index=False)["net"].sum()
              .assign(foreign_net_yi=lambda d: d["net"] / 1e8)
              .loc[:, ["date", "foreign_net_yi"]])
    out["date"] = pd.to_datetime(out["date"])
    _result = out.sort_values("date").reset_index(drop=True)
    # v18.357 PR-Q5c S-PROV-1 phase 19:DataFrame attrs
    try:
        _result.attrs.setdefault('source',
            'FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign(via leading_indicators.finmind_get)')
        _result.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
    except Exception:
        pass
    # provenance log
    prov_log('fetch_foreign_flow_series',
             'FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign',
             f'days={days}:DataFrame:rows={len(_result)}')
    # Phase 2 pandera Priority 2 v18.434:log-mode foreign flow schema
    # (date ascending + foreign_net_yi 億 TWD ∈ ±9999 防單位混淆)
    try:
        from shared.schemas import validate_in_log_mode, ForeignFlowSchema
        validate_in_log_mode(_result, ForeignFlowSchema,
                              label=f'fetch_foreign_flow_series:days={days}')
    except Exception:
        pass
    return _result, ""
