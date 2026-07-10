"""test_china_macro_stock.py — v18.271 China macro 補完(Stock 端,方向 B)

驗證重點:
1. shared/fred_series 5 個 China 常數對齊文件 ID
2. tw_macro.fetch_china_macro 走 macro_core.fetch_fred(NAS proxy)
3. macro_core.MACRO_THRESHOLDS 5 個 China zone 齊全
4. macro_helpers.calc_china_credit_impulse_proxy 邊界條件
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from src.data.macro import macro_core
from src.compute.macro import macro_helpers
from src.data.macro import tw_macro


# ══════════════════════════════════════════════════════════════
# 1. SSOT 常數對齊
# ══════════════════════════════════════════════════════════════

def test_china_fred_ids_match_documented():
    from shared.fred_series import (
        FRED_CHN_CPI,
        FRED_CHN_M2,
        FRED_CHN_OECD_CLI,
        FRED_CHN_PMI,
        FRED_USDCNY,
    )
    assert FRED_CHN_OECD_CLI == "CHNLOLITONOSTSAM"
    assert FRED_CHN_CPI == "CPALTT01CNM659N"
    assert FRED_CHN_M2 == "MABMM301CNM189S"
    assert FRED_CHN_PMI == "BSCICP03CNM665S"
    assert FRED_USDCNY == "DEXCHUS"


def test_china_fred_specs_uses_ssot():
    specs = tw_macro._china_fred_specs()
    assert len(specs) == 5
    ids = {sid for sid, _ in specs}
    assert ids == {"DEXCHUS", "CHNLOLITONOSTSAM", "CPALTT01CNM659N",
                   "MABMM301CNM189S", "BSCICP03CNM665S"}


# ══════════════════════════════════════════════════════════════
# 2. MACRO_THRESHOLDS 5 個 China zone
# ══════════════════════════════════════════════════════════════

def test_macro_thresholds_china_keys_present():
    # v19.74:CHN_PMI → CHN_BCI 對齊 macro_core.py:241 v18.459 刻意改名
    # (BSCICP03CNM665S = OECD Business Confidence,非 PMI;測試原漏同步)
    keys = {"CHN_CLI", "CHN_BCI", "CHN_CPI", "CHN_M2", "USDCNY"}
    assert keys.issubset(macro_core.MACRO_THRESHOLDS.keys())


def test_macro_thresholds_china_red_yellow_ordering():
    for key in ("CHN_CLI", "CHN_BCI", "CHN_CPI", "CHN_M2", "USDCNY"):
        rule = macro_core.MACRO_THRESHOLDS[key]
        if "red_above" in rule and "yellow_above" in rule:
            assert rule["red_above"] >= rule["yellow_above"], f"{key} above 反序"
        if "red_below" in rule and "yellow_below" in rule:
            assert rule["red_below"] <= rule["yellow_below"], f"{key} below 反序"


# ══════════════════════════════════════════════════════════════
# 3. fetch_china_macro
# ══════════════════════════════════════════════════════════════

def test_fetch_china_macro_no_key_returns_empty():
    tw_macro.fetch_china_macro.cache_clear()
    assert tw_macro.fetch_china_macro("") == {}


def test_fetch_china_macro_via_proxy(monkeypatch):
    """確認 fetch_china_macro 透過 macro_core.fetch_url 並抓 5 series"""
    captured_series = []

    def fake_fetch_url(url, headers=None, params=None, timeout=20):
        captured_series.append(params.get("series_id", ""))
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "observations": [
                {"date": "2025-01-01", "value": "100.5"},
                {"date": "2025-02-01", "value": "101.0"},
                {"date": "2025-03-01", "value": "100.8"},
            ]
        }
        return mock_resp

    monkeypatch.setattr(macro_core, "fetch_url", fake_fetch_url)
    tw_macro.fetch_china_macro.cache_clear()

    out = tw_macro.fetch_china_macro(fred_api_key="fake_key")

    assert len(out) == 5
    expected_ids = {"DEXCHUS", "CHNLOLITONOSTSAM", "CPALTT01CNM659N",
                    "MABMM301CNM189S", "BSCICP03CNM665S"}
    assert set(captured_series) == expected_ids
    # 每個 series 都有 DataFrame
    for sid, df in out.items():
        assert df is not None and not df.empty, f"{sid} empty"
        assert {"date", "value", "source", "fetched_at"}.issubset(df.columns)


# ══════════════════════════════════════════════════════════════
# 4. calc_china_credit_impulse_proxy
# ══════════════════════════════════════════════════════════════

def test_credit_impulse_none():
    assert macro_helpers.calc_china_credit_impulse_proxy(None) is None


def test_credit_impulse_short_series():
    s = pd.Series([8.0] * 10)
    assert macro_helpers.calc_china_credit_impulse_proxy(s, lag_months=12) is None


def test_credit_impulse_accelerating():
    """近期 M2 YoY 加速 → 正值"""
    s = pd.Series([6.0] * 12 + [10.0])
    assert macro_helpers.calc_china_credit_impulse_proxy(s, lag_months=12) == 4.0


def test_credit_impulse_decelerating():
    s = pd.Series([10.0] * 12 + [6.0])
    assert macro_helpers.calc_china_credit_impulse_proxy(s, lag_months=12) == -4.0


def test_credit_impulse_lag_param():
    s = pd.Series([5.0] * 6 + [9.0])
    assert macro_helpers.calc_china_credit_impulse_proxy(s, lag_months=6) == 4.0
