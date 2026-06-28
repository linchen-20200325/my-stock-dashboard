"""test_tw_macro_policy.py — v18.270 TW 央行政策階段判讀 4 大缺口補完

驗證重點:
1. 4 個 fetcher 都走 proxy_helper.fetch_url(NAS 中繼,不直連)
2. provenance 欄(source / fetched_at)正確
3. sanity 範圍過濾(CPI [-5,20] / Unemp [2,8] / CBC rate [0,5] / USDTWD [25,40])
4. 3 個衍生函式邊界條件(None / 空 / 單筆)
5. MACRO_THRESHOLDS 新 zone 4 項齊全
"""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from src.data.macro import macro_core
import macro_helpers
from src.data.macro import tw_macro


# ══════════════════════════════════════════════════════════════
# 1. MACRO_THRESHOLDS 新 zone
# ══════════════════════════════════════════════════════════════

def test_macro_thresholds_tw_policy_keys_present():
    keys = {"TW_CPI_YOY", "TW_UNEMP", "CBC_RATE", "USDTWD"}
    assert keys.issubset(macro_core.MACRO_THRESHOLDS.keys())


def test_macro_thresholds_tw_policy_red_yellow_ordering():
    for key in ("TW_CPI_YOY", "TW_UNEMP", "CBC_RATE", "USDTWD"):
        rule = macro_core.MACRO_THRESHOLDS[key]
        if "red_above" in rule and "yellow_above" in rule:
            assert rule["red_above"] >= rule["yellow_above"], f"{key} above 反序"


# ══════════════════════════════════════════════════════════════
# 2. TW CPI YoY fetcher
# ══════════════════════════════════════════════════════════════

def test_fetch_tw_cpi_yoy_via_proxy(monkeypatch):
    captured = {}

    def fake_fetch_url(url, headers=None, params=None, timeout=15):
        captured["url"] = url
        captured["params"] = params
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"date": "2025-01-01", "indicator": "消費者物價指數(CPI)-總指數年增率(%)", "value": 2.30},
                {"date": "2025-02-01", "indicator": "消費者物價指數(CPI)-總指數年增率(%)", "value": 1.97},
                {"date": "2025-03-01", "indicator": "消費者物價指數(CPI)-總指數年增率(%)", "value": 2.15},
            ]
        }
        return mock_resp

    monkeypatch.setattr(tw_macro, "fetch_url", fake_fetch_url)
    # bypass _ttl_cache
    tw_macro.fetch_tw_cpi_yoy.cache_clear()
    df = tw_macro.fetch_tw_cpi_yoy(months_back=12)
    assert df is not None and not df.empty
    assert "finmindtrade" in captured["url"]
    assert captured["params"]["dataset"] == "TaiwanMacroEconomics"
    assert {"date", "value", "source", "fetched_at"}.issubset(df.columns)
    assert (df["source"] == "FinMind:TaiwanMacroEconomics:CPI_YoY").all()
    assert df["value"].between(-5, 20).all()


def test_fetch_tw_cpi_yoy_sanity_filters_out_of_range(monkeypatch):
    """超出 [-5, 20] 的值應被過濾(疑似指標名比對誤觸 level 而非 YoY)"""

    def fake_fetch_url(url, headers=None, params=None, timeout=15):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"date": "2025-01-01", "indicator": "CPI", "value": 105.5},  # level 非 YoY
                {"date": "2025-02-01", "indicator": "CPI", "value": 106.0},
            ]
        }
        return mock_resp

    monkeypatch.setattr(tw_macro, "fetch_url", fake_fetch_url)
    tw_macro.fetch_tw_cpi_yoy.cache_clear()
    df = tw_macro.fetch_tw_cpi_yoy(months_back=12)
    assert df is None  # sanity 過濾後全空,回 None


def test_fetch_tw_cpi_yoy_proxy_fail_returns_none(monkeypatch):
    monkeypatch.setattr(tw_macro, "fetch_url", lambda *a, **kw: None)
    tw_macro.fetch_tw_cpi_yoy.cache_clear()
    df = tw_macro.fetch_tw_cpi_yoy()
    assert df is None


# ══════════════════════════════════════════════════════════════
# 3. TW 失業率 fetcher
# ══════════════════════════════════════════════════════════════

def test_fetch_tw_unemployment_via_proxy(monkeypatch):
    def fake_fetch_url(url, headers=None, params=None, timeout=15):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"date": "2025-01-01", "indicator": "失業率(%)", "value": 3.42},
                {"date": "2025-02-01", "indicator": "失業率(%)", "value": 3.38},
            ]
        }
        return mock_resp

    monkeypatch.setattr(tw_macro, "fetch_url", fake_fetch_url)
    tw_macro.fetch_tw_unemployment.cache_clear()
    df = tw_macro.fetch_tw_unemployment(months_back=12)
    assert df is not None and not df.empty
    assert df["value"].between(2, 8).all()
    assert (df["source"] == "FinMind:TaiwanMacroEconomics:Unemployment").all()


# ══════════════════════════════════════════════════════════════
# 4. CBC 重貼現率 (FRED)
# ══════════════════════════════════════════════════════════════

def test_fetch_cbc_discount_rate_via_fred(monkeypatch):
    captured = {}

    def fake_fetch_url(url, headers=None, params=None, timeout=20):
        captured["url"] = url
        captured["params"] = params
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "observations": [
                {"date": "2024-10-01", "value": "1.875"},
                {"date": "2024-11-01", "value": "2.000"},
                {"date": "2024-12-01", "value": "2.000"},
            ]
        }
        return mock_resp

    # macro_core.fetch_fred 透過 fetch_url(同一 namespace 為 macro_core)
    monkeypatch.setattr(macro_core, "fetch_url", fake_fetch_url)
    tw_macro.fetch_cbc_discount_rate.cache_clear()
    df = tw_macro.fetch_cbc_discount_rate(months_back=24, fred_api_key="fake_key")
    assert df is not None and not df.empty
    assert "INTDSRTWM193N" in captured["params"]["series_id"]
    assert df["value"].between(0, 5).all()
    # source 已被改寫為 CBC 語意標籤
    assert (df["source"].str.contains("CBC_DiscountRate")).all()


def test_fetch_cbc_discount_rate_no_api_key():
    tw_macro.fetch_cbc_discount_rate.cache_clear()
    assert tw_macro.fetch_cbc_discount_rate(fred_api_key="") is None


# ══════════════════════════════════════════════════════════════
# 5. USDTWD
# ══════════════════════════════════════════════════════════════

def test_fetch_usdtwd_via_yahoo(monkeypatch):
    captured = {}
    timestamps = [1735689600, 1735776000, 1735862400]
    closes = [32.45, 32.51, 32.38]

    def fake_fetch_url(url, headers=None, params=None, timeout=15):
        captured["url"] = url
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "chart": {"result": [{
                "timestamp": timestamps,
                "indicators": {"quote": [{"close": closes}]},
            }]}
        }
        return mock_resp

    monkeypatch.setattr(macro_core, "fetch_url", fake_fetch_url)
    tw_macro.fetch_usdtwd_close.cache_clear()
    df = tw_macro.fetch_usdtwd_close(days_back=60)
    assert df is not None and not df.empty
    assert "TWD=X" in captured["url"]
    assert df["value"].between(25, 40).all()
    assert (df["source"] == "Yahoo:TWD=X:Close").all()


# ══════════════════════════════════════════════════════════════
# 6. 衍生函式 - calc_real_rate
# ══════════════════════════════════════════════════════════════

def test_calc_real_rate_normal():
    # 2% 利率 − 1.5% 通膨 = +0.5% 實質(略緊)
    assert macro_helpers.calc_real_rate(2.0, 1.5) == 0.5


def test_calc_real_rate_negative_means_loose():
    # 1.5% 利率 − 3.0% 通膨 = -1.5% 實質(寬鬆)
    assert macro_helpers.calc_real_rate(1.5, 3.0) == -1.5


def test_calc_real_rate_none_input():
    assert macro_helpers.calc_real_rate(None, 2.0) is None
    assert macro_helpers.calc_real_rate(2.0, None) is None


def test_calc_real_rate_nan_input():
    assert macro_helpers.calc_real_rate(float("nan"), 2.0) is None


# ══════════════════════════════════════════════════════════════
# 7. 衍生函式 - classify_rate_cycle
# ══════════════════════════════════════════════════════════════

def test_classify_rate_cycle_hiking():
    s = pd.Series([1.5, 1.625, 1.75, 1.875, 2.0])
    assert macro_helpers.classify_rate_cycle(s) == "🟢 升息中"


def test_classify_rate_cycle_cutting():
    s = pd.Series([2.0, 1.875, 1.75, 1.625, 1.5])
    assert macro_helpers.classify_rate_cycle(s) == "🔴 降息中"


def test_classify_rate_cycle_flat():
    s = pd.Series([2.0, 2.0, 2.0, 2.0])
    assert macro_helpers.classify_rate_cycle(s) == "⚪ 持平"


def test_classify_rate_cycle_empty():
    assert macro_helpers.classify_rate_cycle(None) == "⬜ 資料不足"
    assert macro_helpers.classify_rate_cycle(pd.Series([])) == "⬜ 資料不足"
    assert macro_helpers.classify_rate_cycle(pd.Series([2.0])) == "⬜ 資料不足"


# ══════════════════════════════════════════════════════════════
# 8. 衍生函式 - calc_twd_trend
# ══════════════════════════════════════════════════════════════

def test_calc_twd_trend_depreciation():
    """60 日線性上升 → 台幣貶值"""
    s = pd.Series(np.linspace(30.0, 32.0, 60))
    out = macro_helpers.calc_twd_trend(s, window_days=60)
    assert out is not None
    assert out["latest"] == 32.0
    assert out["ma_60d"] is not None and 30.0 < out["ma_60d"] < 32.0
    assert out["slope_per_month"] is not None and out["slope_per_month"] > 0.1
    assert out["direction"] == "🔴 台幣貶"


def test_calc_twd_trend_appreciation():
    s = pd.Series(np.linspace(32.0, 30.0, 60))
    out = macro_helpers.calc_twd_trend(s, window_days=60)
    assert out is not None
    assert out["slope_per_month"] is not None and out["slope_per_month"] < -0.1
    assert out["direction"] == "🟢 台幣升"


def test_calc_twd_trend_short_data():
    """資料不足 60 天 → 回 latest 但 ma_60d/slope None"""
    s = pd.Series([32.0, 32.1, 32.05])
    out = macro_helpers.calc_twd_trend(s, window_days=60)
    assert out is not None
    assert out["latest"] == 32.05
    assert out["ma_60d"] is None
    assert out["slope_per_month"] is None


def test_calc_twd_trend_none_empty():
    assert macro_helpers.calc_twd_trend(None) is None
    assert macro_helpers.calc_twd_trend(pd.Series([])) is None
