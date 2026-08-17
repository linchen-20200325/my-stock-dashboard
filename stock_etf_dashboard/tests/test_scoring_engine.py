"""L2 個股評分：估值河流圖位階、均線/MACD、籌碼同步、綜合分。"""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from stock_etf_dashboard.core import constants as C
from stock_etf_dashboard.core.circuit_breaker import FailLoudError, isclose
from stock_etf_dashboard.services import stock_scoring_engine as se


def _ohlcv(closes, start="2024-01-01"):
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="B")
    c = pd.Series(closes, dtype=float)
    return pd.DataFrame({"date": dates, "open": c, "high": c + 1,
                         "low": c - 1, "close": c, "volume": 1000.0})


# ── 估值河流圖位階 ──────────────────────────────────────────────────────
def test_valuation_zone_cheap_when_low_in_history():
    # 歷史 10~30，當前 10 → 最低 → 便宜區
    val = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="B"),
                        "pe": np.linspace(30, 10, 100)})
    vp = se.valuation_position(val, metric="pe")
    assert vp.zone == "便宜區"
    assert vp.percentile <= C.VALUATION_CHEAP_PCTL


def test_valuation_zone_expensive_when_high():
    val = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=100, freq="B"),
                        "pe": np.linspace(10, 30, 100)})
    vp = se.valuation_position(val, metric="pe")
    assert vp.zone == "昂貴區"


def test_valuation_all_nan_raises():
    val = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5, freq="B"),
                        "pe": [np.nan] * 5})
    with pytest.raises(FailLoudError):
        se.valuation_position(val, metric="pe")


def test_valuation_insufficient_samples_flagged():
    val = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5, freq="B"),
                        "pe": [10, 11, 12, 13, 14]})
    vp = se.valuation_position(val, metric="pe")
    assert vp.sufficient is False    # < VALUATION_MIN_SAMPLES


# ── 均線 / MACD ─────────────────────────────────────────────────────────
def test_trend_bullish_on_uptrend():
    ts = se.trend_state(_ohlcv(list(np.linspace(80, 120, 120))))
    assert ts.ma_bullish is True
    assert ts.label == "多頭排列"


def test_trend_short_history_has_none_ma_mid():
    ts = se.trend_state(_ohlcv([100, 101, 102]))   # < MA_MID
    assert ts.ma_mid is None
    assert ts.label == "盤整"        # 無法確認排列 → 保守中性


# ── 籌碼同步 ────────────────────────────────────────────────────────────
def test_chip_sync_buy():
    chip = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5, freq="B"),
                         "foreign_net": [100, 200, 50, 80, 60],
                         "trust_net": [10, 20, 5, 8, 6],
                         "dealer_net": [0] * 5})
    cs = se.chip_state(chip)
    assert cs.sync_buy is True
    assert cs.label == "外資投信同步買超"


def test_chip_sync_sell():
    chip = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5, freq="B"),
                         "foreign_net": [-100, -50, -30, -20, -10],
                         "trust_net": [-5, -8, -3, -2, -1],
                         "dealer_net": [0] * 5})
    cs = se.chip_state(chip)
    assert cs.sync_sell is True


# ── 綜合分 ──────────────────────────────────────────────────────────────
def test_score_weights_sum_to_one():
    assert isclose(C.SCORE_WEIGHT_VALUATION + C.SCORE_WEIGHT_TREND
                   + C.SCORE_WEIGHT_CHIP, 1.0)


def test_score_high_for_cheap_uptrend_syncbuy():
    ohlcv = _ohlcv(list(np.linspace(80, 120, 120)))
    val = pd.DataFrame({"date": ohlcv["date"], "pe": np.linspace(30, 10, 120)})
    chip = pd.DataFrame({"date": ohlcv["date"].tail(5).values,
                         "foreign_net": [100] * 5, "trust_net": [50] * 5,
                         "dealer_net": [0] * 5})
    sc = se.score_stock("X", ohlcv, valuation=val, chip=chip, as_of=date(2024, 6, 20))
    assert sc.total_score >= 80
    assert 0 <= sc.total_score <= 100


def test_score_without_ohlcv_raises():
    with pytest.raises(FailLoudError):
        se.score_stock("X", pd.DataFrame())


def test_single_row_ohlcv_degrades_not_crashes():
    # 新上市/資料極少：不崩、不捏造,趨勢保守中性、置信度鎖定
    one = _ohlcv([100.0])
    sc = se.score_stock("NEW", one, valuation=None, chip=None, as_of=date(2024, 1, 1))
    assert sc.trend.ma_mid is None and sc.trend.macd_hist is None
    assert sc.trend.label == "盤整"
    assert 0 <= sc.total_score <= 100


def test_score_missing_chip_is_neutral_not_fabricated():
    ohlcv = _ohlcv(list(np.linspace(80, 120, 120)))
    sc = se.score_stock("X", ohlcv, valuation=None, chip=None, as_of=date(2024, 6, 20))
    assert sc.chip.label == "無籌碼資料"
    assert 0 <= sc.total_score <= 100
