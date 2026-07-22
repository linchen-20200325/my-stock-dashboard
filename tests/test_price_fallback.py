"""tests/test_price_fallback.py — 價格第二來源備援 normalizer(v19.144 建議#2）。

驗 FinMind TaiwanStockPrice 原始 df → 標準 K 線 df（Close + DatetimeIndex）的純函式。
（Yahoo 全敗→FinMind 的 live fetch 需連外，容器測不了；此處測可離線的標準化。）
"""
from __future__ import annotations

import pandas as pd

from src.data.stock.picker_fetcher import _finmind_raw_to_close_df


def _raw(rows):
    return pd.DataFrame(rows)


def test_normalize_basic():
    raw = _raw([
        {"date": "2025-01-02", "open": 100, "max": 105, "min": 99, "close": 104, "Trading_Volume": 1200},
        {"date": "2025-01-03", "open": 104, "max": 108, "min": 103, "close": 107, "Trading_Volume": 900},
    ])
    out = _finmind_raw_to_close_df(raw)
    assert list(out.columns[:1]) == ["Close"]
    assert set(["Close", "Open", "High", "Low", "Volume"]).issubset(out.columns)
    assert isinstance(out.index, pd.DatetimeIndex)
    assert out["Close"].tolist() == [104.0, 107.0]        # close→Close，數值化
    assert out["High"].tolist() == [105.0, 108.0]


def test_sorted_by_date():
    raw = _raw([
        {"date": "2025-02-01", "close": 200},
        {"date": "2025-01-01", "close": 100},
    ])
    out = _finmind_raw_to_close_df(raw)
    assert list(out.index) == [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")]
    assert out["Close"].tolist() == [100.0, 200.0]        # 依日期排序


def test_bad_dates_and_nan_close_dropped():
    raw = _raw([
        {"date": "not-a-date", "close": 50},               # 壞日期 → 剔除
        {"date": "2025-01-05", "close": None},             # close NaN → 剔除
        {"date": "2025-01-06", "close": 60},               # 有效
    ])
    out = _finmind_raw_to_close_df(raw)
    assert len(out) == 1 and out["Close"].iloc[0] == 60.0


def test_missing_close_col_returns_empty():
    raw = _raw([{"date": "2025-01-01", "open": 100}])       # 無 close 欄
    assert _finmind_raw_to_close_df(raw).empty


def test_empty_and_none():
    assert _finmind_raw_to_close_df(pd.DataFrame()).empty
    assert _finmind_raw_to_close_df(None).empty


def test_only_close_available():
    # 只有 date + close（無 OHLV）→ 仍回 Close-only df（RS/報酬夠用）
    raw = _raw([{"date": "2025-01-01", "close": 10}, {"date": "2025-01-02", "close": 11}])
    out = _finmind_raw_to_close_df(raw)
    assert "Close" in out.columns and "Open" not in out.columns
    assert out["Close"].tolist() == [10.0, 11.0]
