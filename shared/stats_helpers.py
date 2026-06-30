"""shared/stats_helpers.py — 純函式股票統計 helpers(L0 Shared,v18.301)

CLAUDE.md §8.3 灰區 — daily_checklist.py 跨 L1+L2+L3 拆檔最小提取。
從 daily_checklist.py:974 提取 `calc_stats`(無 I/O 純函式,適合 L0)。

設計
----
- L0 純函式,無 I/O,無 streamlit
- 接 DataFrame(close/Close 欄)→ 回 dict(last/pct/status/chg)
- 'status' 三態:多頭排列↑ / 空頭排列↓ / 整理中

歷史
----
原位置 daily_checklist.py:974(L1+L2+L3 混雜檔),v18.301 提取到 shared/。
為向後相容,daily_checklist 仍 re-export(`from shared.stats_helpers import calc_stats`)。
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd


def zscore(s: "pd.Series") -> "pd.Series":
    """標準分數 z = (s - mean) / std(L0 SSOT)。

    D2 v18.437 收斂:統一原 `macro_core.zscore` + `multi_factor_optimization._zscore`
    兩份近乎逐字相同實作(僅 std=0 guard 寫法略異)。採較廣的 `not np.isfinite` guard
    (同時涵蓋 NaN 與 inf),避免除零 / 不捏造。

    參數:
        s: pd.Series 數值序列

    回傳:
        pd.Series z-score;空序列原樣返回;std=0 或非有限 → 全 0(同 index)。
    """
    if s.empty:
        return s
    sd = float(s.std())
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / sd


def calc_stats(df: Any) -> Optional[dict]:
    """計算股票統計數據(last / pct / status / chg)。

    Parameters
    ----------
    df : pandas.DataFrame | None
        含 'close' 或 'Close' 欄位的 OHLC DataFrame。

    Returns
    -------
    dict | None
        成功:{'last': float, 'pct': float, 'status': str, 'chg': float}
        失敗(None / empty / 缺欄 / 行數 < 2):None

    status 規則
    -----------
    - last > MA5 > MA20 → '多頭排列↑'
    - last < MA5 < MA20 → '空頭排列↓'
    - 其他 → '整理中'
    """
    if df is None or df.empty:
        return None
    col = next((c for c in ['close', 'Close'] if c in df.columns), None)
    if not col:
        return None
    s = df[col].dropna()
    if len(s) < 2:
        return None
    last = float(s.iloc[-1])
    prev = float(s.iloc[-2])
    pct = (last - prev) / prev * 100 if prev else 0
    ma5 = float(s.tail(5).mean())
    ma20 = float(s.tail(20).mean()) if len(s) >= 20 else ma5
    if last > ma5 > ma20:
        status = '多頭排列↑'
    elif last < ma5 < ma20:
        status = '空頭排列↓'
    else:
        status = '整理中'
    return {
        'last': round(last, 2),
        'pct': round(pct, 2),
        'status': status,
        'chg': round(last - prev, 2),
    }
