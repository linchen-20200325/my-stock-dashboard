"""
test_macro_core.py — macro_core 單元測試

驗證重點:
1. 純數學函式正確(zscore / trend_arrow / recession_probability / spread_series)
2. **所有外部 HTTP 抓取(fetch_fred / fetch_yf_close)都會呼叫 proxy_helper.fetch_url**,
   也就是必走 NAS 中繼站,不會繞道直連 yfinance / requests。
3. snapshot schema 工具(make_indicator / flatten_snapshot)雙向相容。
"""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

import macro_core


# ══════════════════════════════════════════════════════════════
# 1. 純數學函式
# ══════════════════════════════════════════════════════════════

def test_zscore_basic():
    s = pd.Series([1, 2, 3, 4, 5])
    z = macro_core.zscore(s)
    assert abs(float(z.mean())) < 1e-9
    assert abs(float(z.std()) - 1.0) < 1e-9


def test_zscore_zero_std_no_div_zero():
    s = pd.Series([5, 5, 5, 5])
    z = macro_core.zscore(s)
    assert (z == 0).all()


def test_trend_arrow_strictly_up():
    assert macro_core.trend_arrow([1, 2, 3, 4, 5]) == "持續上升 ↑"


def test_trend_arrow_strictly_down():
    assert macro_core.trend_arrow([5, 4, 3, 2, 1]) == "持續下降 ↓"


def test_trend_arrow_recent_rebound():
    assert macro_core.trend_arrow([5, 4, 3, 2, 3]) == "最近反彈 ↗"


def test_trend_arrow_too_short():
    assert macro_core.trend_arrow([1, 2]) == ""


def test_recession_probability_inverted():
    # 倒掛 -1% → 機率應顯著 > 50%
    p = macro_core.recession_probability(-1.0)
    assert p is not None and p > 60


def test_recession_probability_normal():
    # 正斜率 1.5% → 機率應 < 10%
    p = macro_core.recession_probability(1.5)
    assert p is not None and p < 10


def test_recession_probability_none():
    assert macro_core.recession_probability(None) is None


def test_spread_series_basic():
    dates_long = pd.date_range("2024-01-01", periods=12, freq="MS")
    dates_short = pd.date_range("2024-01-01", periods=12, freq="MS")
    df_long  = pd.DataFrame({"date": dates_long,  "value": np.linspace(4.0, 5.0, 12)})
    df_short = pd.DataFrame({"date": dates_short, "value": np.linspace(3.0, 4.5, 12)})
    sp = macro_core.spread_series(df_long, df_short, n_pts=12)
    assert not sp.empty
    # 第一筆與最後一筆都應為正值(long > short)
    assert float(sp.iloc[0])  > 0
    assert float(sp.iloc[-1]) >= 0


def test_spread_series_empty_input():
    assert macro_core.spread_series(pd.DataFrame(), pd.DataFrame()).empty


# ══════════════════════════════════════════════════════════════
# 2. NAS Proxy 強制使用驗證
# ══════════════════════════════════════════════════════════════

def test_fetch_fred_goes_through_proxy_helper(monkeypatch):
    """
    確認 fetch_fred() 一定透過 proxy_helper.fetch_url(走 NAS),
    不會自己 import requests 或 yfinance 直連。
    """
    captured = {}

    def fake_fetch_url(url, headers=None, params=None, timeout=20):
        captured["url"] = url
        captured["params"] = params
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "observations": [
                {"date": "2025-01-01", "value": "50.5"},
                {"date": "2025-02-01", "value": "51.2"},
                {"date": "2025-03-01", "value": "52.0"},
            ]
        }
        return mock_resp

    monkeypatch.setattr(macro_core, "fetch_url", fake_fetch_url)
    df = macro_core.fetch_fred("NAPM", "fake_key", n=10)

    assert captured["url"] == macro_core.FRED_BASE
    assert captured["params"]["series_id"] == "NAPM"
    assert captured["params"]["api_key"] == "fake_key"
    assert len(df) == 3
    # S-PROV-1 v18.246:fetch_fred 新增 source + fetched_at provenance 欄位
    assert {"date", "value", "source", "fetched_at"}.issubset(df.columns)
    assert df["value"].dtype == float
    assert (df["source"] == "FRED:NAPM").all()
    assert df["fetched_at"].notna().all()


def test_fetch_fred_empty_key_no_network():
    """空 api_key 直接回傳空 DataFrame,不應觸發任何 HTTP 呼叫。"""
    df = macro_core.fetch_fred("NAPM", "", n=10)
    assert df.empty


def test_fetch_fred_proxy_unreachable(monkeypatch):
    """fetch_url 回 None(NAS 與直連都失敗)→ 回傳空 DataFrame,不可拋。"""
    monkeypatch.setattr(macro_core, "fetch_url", lambda *a, **kw: None)
    df = macro_core.fetch_fred("NAPM", "key", n=10)
    assert df.empty


def test_fetch_yf_close_goes_through_proxy_helper(monkeypatch):
    """
    確認 fetch_yf_close() 走 proxy_helper.fetch_url 打 Chart API,
    而非直接 import yfinance。
    """
    captured = {}
    timestamps = [1735689600, 1735776000, 1735862400]  # 2025-01-01..03 UTC
    closes = [28.5, 29.1, 27.8]

    def fake_fetch_url(url, headers=None, params=None, timeout=15):
        captured["url"] = url
        captured["params"] = params
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "chart": {
                "result": [{
                    "timestamp": timestamps,
                    "indicators": {"quote": [{"close": closes}]},
                }]
            }
        }
        return mock_resp

    monkeypatch.setattr(macro_core, "fetch_url", fake_fetch_url)
    s = macro_core.fetch_yf_close("^VIX", range_="5d")

    assert captured["url"].endswith("/^VIX")
    assert captured["params"]["range"] == "5d"
    assert len(s) == 3
    assert float(s.iloc[-1]) == 27.8
    assert s.name == "^VIX"


def test_fetch_yf_close_proxy_failure(monkeypatch):
    monkeypatch.setattr(macro_core, "fetch_url", lambda *a, **kw: None)
    s = macro_core.fetch_yf_close("^VIX")
    assert s.empty


def test_fetch_yf_latest_batch(monkeypatch):
    timestamps = [1735862400]
    def fake_fetch_url(url, headers=None, params=None, timeout=15):
        if "VIX" in url:
            close_val = [22.5]
        elif "DX-Y" in url:
            close_val = [104.3]
        else:
            close_val = [None]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "chart": {"result": [{
                "timestamp": timestamps,
                "indicators": {"quote": [{"close": close_val}]},
            }]}
        }
        return mock_resp

    monkeypatch.setattr(macro_core, "fetch_url", fake_fetch_url)
    out = macro_core.fetch_yf_latest(("^VIX", "DX-Y.NYB"))
    assert out["^VIX"]     == 22.5
    assert out["DX-Y.NYB"] == 104.3


# ══════════════════════════════════════════════════════════════
# 3. snapshot schema 工具
# ══════════════════════════════════════════════════════════════

def test_make_indicator_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0],
                  index=pd.date_range("2025-01-01", periods=5))
    ind = macro_core.make_indicator(
        "PMI", "ISM 製造業 PMI", 52.5,
        prev=51.8, unit="", type_="領先",
        date="2025-04", series=s, weight=2.0,
    )
    assert ind["key"] == "PMI"
    assert ind["value"] == 52.5
    assert ind["weight"] == 2.0
    # 序列遞增 → trend 應為「持續上升」
    assert ind["trend"] == "持續上升 ↑"


def test_make_indicator_no_series_no_trend():
    ind = macro_core.make_indicator("VIX", "VIX 恐慌指數", 25.0)
    assert ind["trend"] == ""


def test_flatten_snapshot_round_trip():
    rich = {
        "VIX": macro_core.make_indicator("VIX", "VIX", 28.3),
        "CPI": macro_core.make_indicator("CPI", "CPI", 3.1, unit="%"),
    }
    flat = macro_core.flatten_snapshot(rich)
    assert flat == {"vix": 28.3, "cpi": 3.1}


def test_flatten_snapshot_skips_none():
    rich = {
        "VIX": macro_core.make_indicator("VIX", "VIX", 28.3),
        "CPI": {"value": None},
        "X":   "not a dict",  # noqa: 不該 crash
    }
    flat = macro_core.flatten_snapshot(rich)
    assert flat == {"vix": 28.3}


# ══════════════════════════════════════════════════════════════
# 4. 統一閾值表健全性
# ══════════════════════════════════════════════════════════════

def test_thresholds_table_present():
    keys = {"VIX", "CPI", "PMI", "HY_SPREAD", "YIELD_10Y2Y", "YIELD_10Y3M"}
    assert keys.issubset(macro_core.MACRO_THRESHOLDS.keys())


def test_thresholds_consistent_red_yellow_ordering():
    """red/yellow_above 應 red > yellow;red/yellow_below 應 red < yellow。"""
    for key, rule in macro_core.MACRO_THRESHOLDS.items():
        if "red_above" in rule and "yellow_above" in rule:
            assert rule["red_above"] >= rule["yellow_above"], f"{key} above 反序"
        if "red_below" in rule and "yellow_below" in rule:
            assert rule["red_below"] <= rule["yellow_below"], f"{key} below 反序"
