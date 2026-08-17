"""L0 core：置信度、除權息防呆、浮點容差、schema。"""
import numpy as np
import pandas as pd
import pytest

from stock_etf_dashboard.core import constants as C
from stock_etf_dashboard.core import circuit_breaker as cb
from stock_etf_dashboard.core.schemas import (OHLCVSchema, ValuationSchema,
                                              validate_or_reject)


# ── 置信度 ──────────────────────────────────────────────────────────────
def test_confidence_lock_below_threshold():
    r = cb.compute_confidence(completeness=0.4, freshness=0.4, source_reliability=0.5)
    assert r.score < C.CONFIDENCE_LOCK_THRESHOLD
    assert r.is_locked is True


def test_confidence_full_is_100_and_unlocked():
    r = cb.compute_confidence(completeness=1.0, freshness=1.0, source_reliability=1.0)
    assert cb.isclose(r.score, 100.0)
    assert r.is_locked is False


def test_confidence_rejects_out_of_range():
    with pytest.raises(cb.FailLoudError):
        cb.compute_confidence(completeness=1.2, freshness=1.0, source_reliability=1.0)


def test_freshness_linear_decay():
    assert cb.freshness_score(0) == 1.0
    assert cb.freshness_score(C.FRESHNESS_ZERO_DAYS + 5) == 0.0
    mid = cb.freshness_score((C.FRESHNESS_FULL_DAYS + C.FRESHNESS_ZERO_DAYS) / 2)
    assert 0.0 < mid < 1.0


# ── 除權息防呆（核心：避免除息跳空誤觸停損）──────────────────────────────
def test_ex_dividend_restores_reference_and_avoids_false_stop():
    # 前收100 開95(跌5%>3%門檻) 配息6 停損96：
    # 原始低點94 <= 96 會誤觸；還原低點 94+6=100 > 96 → 不觸
    g = cb.ex_dividend_guard(prev_close=100, today_open=95, today_low=94,
                             dividend_amount=6, stop_price=96)
    assert g.is_ex_dividend is True
    assert cb.isclose(g.adjusted_low, 100.0)
    assert g.stop_triggered is False


def test_non_ex_dividend_real_break_triggers():
    # 無配息、正常跌破：低點94 <= 停損96 → 真的觸損
    g = cb.ex_dividend_guard(prev_close=100, today_open=99, today_low=94,
                             dividend_amount=0, stop_price=96)
    assert g.is_ex_dividend is False
    assert g.stop_triggered is True


def test_ex_dividend_still_triggers_when_truly_broken():
    # 除息但真的跌很深：還原後仍破停損
    g = cb.ex_dividend_guard(prev_close=100, today_open=95, today_low=80,
                             dividend_amount=6, stop_price=90)
    assert g.is_ex_dividend is True
    assert g.stop_triggered is True   # 80+6=86 <= 90


def test_ex_dividend_guard_rejects_bad_input():
    with pytest.raises(cb.FailLoudError):
        cb.ex_dividend_guard(prev_close=0, today_open=95, today_low=94,
                             dividend_amount=6, stop_price=96)


# ── schema 出口驗證 ─────────────────────────────────────────────────────
def _good_ohlcv():
    return pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "open": [10.0, 11.0], "high": [12.0, 13.0], "low": [9.0, 10.0],
        "close": [11.0, 12.0], "volume": [100.0, 200.0]})


def test_ohlcv_valid_passes():
    df = validate_or_reject(_good_ohlcv(), OHLCVSchema, name="OHLCV")
    assert len(df) == 2


def test_ohlcv_low_above_high_rejected_to_empty_shell():
    bad = _good_ohlcv()
    bad.loc[0, "low"] = 999.0     # low > high 破壞不變量
    out = validate_or_reject(bad, OHLCVSchema, name="OHLCV")
    assert out.empty                 # §1：壞值不放行,回空殼
    assert out.attrs.get("rejected") is True


def test_valuation_allows_nan_pe():
    df = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]),
                       "pe": [np.nan], "pb": [1.5]})
    out = validate_or_reject(df, ValuationSchema, name="Valuation")
    assert len(out) == 1             # NaN PE 合法（EPS<=0 時不捏造）
