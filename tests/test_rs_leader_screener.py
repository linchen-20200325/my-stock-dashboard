"""tests/test_rs_leader_screener.py — 抗跌 RS 選股 L2 純函式測試（v19.70）。

不觸網:用合成 K 線（含日內波動，讓大盤 σ>0）驗計分/排序/邊界。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared.rs_screen_thresholds import (
    RS_MIN_ALIGNED_ROWS,
    TIER_INSUFFICIENT,
    TIER_LAG,
    TIER_LEAD,
    TIER_MILD,
    TIER_SYNC,
)
from src.compute.screener import rs_leader_screener as rl


# ── SSOT 門檻（§3.3 反捏造）──────────────────────────────────
def test_rs_sigma_ssot_values_and_classify_boundaries():
    from shared.signal_thresholds import (
        RS_SIGMA_LAG_MAX,
        RS_SIGMA_LEAD_MIN,
        RS_SIGMA_MILD_MIN,
    )
    assert (RS_SIGMA_LEAD_MIN, RS_SIGMA_MILD_MIN, RS_SIGMA_LAG_MAX) == (1.0, 0.3, -0.3)
    assert rl._classify(1.0) == TIER_LEAD
    assert rl._classify(0.99) == TIER_MILD
    assert rl._classify(0.3) == TIER_MILD
    assert rl._classify(0.29) == TIER_SYNC
    assert rl._classify(-0.3) == TIER_SYNC
    assert rl._classify(-0.31) == TIER_LAG
    assert rl._classify(None) == TIER_INSUFFICIENT


def test_v5_modules_consumes_rs_sigma_ssot_not_inline():
    """v5_modules.calc_relative_strength 分級須用 SSOT 常數，不得再 inline 1.0/0.3。"""
    src = open("src/compute/strategy/v5_modules.py", encoding="utf-8").read()
    assert "RS_SIGMA_LEAD_MIN" in src and "RS_SIGMA_MILD_MIN" in src
    assert "avg_rs >= 1.0" not in src and "avg_rs >= 0.3" not in src


# ── 合成 K 線工廠：帶波動的等比路徑（保證 σ_market > 0）──────────
def _series(total_ret: float, n: int = 160, noise: float = 0.012,
            base: str = "2026-01-01", seed: int = 0) -> pd.DataFrame:
    """n 天日線，總報酬 = total_ret（如 -0.30 = 期末跌 30%），疊加日內雜訊。"""
    rng = np.random.RandomState(seed)
    drift = (1 + total_ret) ** (1 / (n - 1)) - 1
    rets = drift + rng.normal(0, noise, n)
    rets[0] = 0.0
    close = 100 * np.cumprod(1 + rets)
    idx = pd.date_range(base, periods=n, freq="D")
    return pd.DataFrame({"Close": close}, index=idx)   # 大寫 Close = 模擬 yfinance


def _market_down(n=160):
    return _series(-0.30, n=n, seed=1)   # 大盤跌 30%（疫情式崩盤）


# ── 分級 ──────────────────────────────────────────────────────
def test_lead_when_stock_beats_falling_market():
    mkt = _market_down()
    stk = _series(+0.05, seed=2)          # 大盤 -30% 期間個股 +5% → 大幅逆勢
    s = rl.score_rs_leader({"stock_id": "2330", "name": "台積電", "df": stk},
                           mkt, lookback=120)
    assert s.avg_rs is not None and s.avg_rs > 0
    assert s.beat_market is True
    assert s.excess_pct > 0
    assert s.tier == TIER_LEAD          # 顯著強於大盤


def test_lag_when_stock_worse_than_market():
    mkt = _market_down()
    stk = _series(-0.55, seed=3)          # 跌得比大盤更慘
    s = rl.score_rs_leader({"stock_id": "9999", "name": "弱雞", "df": stk},
                           mkt, lookback=120)
    assert s.beat_market is False
    assert s.excess_pct < 0
    assert s.tier == TIER_LAG


def test_excess_is_stock_minus_market():
    mkt = _market_down()
    stk = _series(-0.10, seed=4)
    s = rl.score_rs_leader({"stock_id": "1234", "name": "", "df": stk},
                           mkt, lookback=120)
    assert s.excess_pct == pytest.approx(
        round(s.stock_ret_pct - s.market_ret_pct, 2), abs=0.05)


# ── 邊界（§1 fail-loud）────────────────────────────────────────
def test_insufficient_when_too_few_common_days():
    mkt = _market_down(n=160)
    stk = _series(+0.05, n=RS_MIN_ALIGNED_ROWS - 2, seed=5)  # 個股太短
    s = rl.score_rs_leader({"stock_id": "5555", "name": "", "df": stk},
                           mkt, lookback=120)
    assert s.tier == TIER_INSUFFICIENT
    assert s.avg_rs is None
    assert "資料不足" in s.reason_text or "不足" in s.reason_text


def test_missing_close_column_insufficient():
    mkt = _market_down()
    bad = pd.DataFrame({"open": [1, 2, 3]}, index=pd.date_range("2026-01-01", periods=3))
    s = rl.score_rs_leader({"stock_id": "7777", "name": "", "df": bad},
                           mkt, lookback=60)
    assert s.tier == TIER_INSUFFICIENT


def test_empty_market_insufficient():
    stk = _series(+0.05, seed=6)
    s = rl.score_rs_leader({"stock_id": "8888", "name": "", "df": stk},
                           pd.DataFrame(), lookback=60)
    assert s.tier == TIER_INSUFFICIENT


def test_none_df_insufficient():
    s = rl.score_rs_leader({"stock_id": "1111", "name": "", "df": None},
                           _market_down(), lookback=60)
    assert s.tier == TIER_INSUFFICIENT


# ── 日曆日對齊（個股/大盤時間戳含時分秒仍要對得上）──────────────
def test_intraday_timestamps_still_align():
    mkt = _market_down()
    stk = _series(+0.05, seed=2)
    # 把個股 index 加上盤中時間、大盤保持 00:00 → normalize 後仍應對齊
    stk2 = stk.copy()
    stk2.index = stk2.index + pd.Timedelta(hours=13, minutes=30)
    s = rl.score_rs_leader({"stock_id": "2330", "name": "", "df": stk2},
                           mkt, lookback=120)
    assert s.avg_rs is not None   # 沒被時分秒差清掉


def test_tz_aware_stock_vs_tz_naive_market_aligns():
    """真實情境:yfinance 個股 tz-aware(Asia/Taipei) vs fetch_yf_close 大盤 tz-naive。
    不脫 tz → intersection 全空。修後應對齊。"""
    mkt = _market_down()                      # tz-naive
    stk = _series(+0.05, seed=2).copy()
    stk.index = stk.index.tz_localize("Asia/Taipei")   # tz-aware
    s = rl.score_rs_leader({"stock_id": "2330", "name": "", "df": stk},
                           mkt, lookback=120)
    assert s.avg_rs is not None and s.beat_market is True


# ── 排序取前 N ────────────────────────────────────────────────
def test_rank_sorts_desc_and_caps_top_n():
    mkt = _market_down()
    stocks = [
        {"stock_id": "A", "name": "強", "df": _series(+0.10, seed=11)},
        {"stock_id": "B", "name": "中", "df": _series(-0.05, seed=12)},
        {"stock_id": "C", "name": "弱", "df": _series(-0.50, seed=13)},
        {"stock_id": "D", "name": "短", "df": _series(+0.10, n=10, seed=14)},  # 資料不足
    ]
    ranked = rl.rank_rs_leaders(stocks, mkt, lookback=120, top_n=2)
    assert len(ranked) == 2                       # top_n 上限
    assert ranked[0].avg_rs >= ranked[1].avg_rs   # 降冪
    assert "D" not in [s.stock_id for s in ranked]  # 資料不足被排除


def test_rank_beat_only_filters_losers():
    mkt = _market_down()
    stocks = [
        {"stock_id": "A", "name": "", "df": _series(+0.10, seed=21)},
        {"stock_id": "C", "name": "", "df": _series(-0.50, seed=22)},
    ]
    ranked = rl.rank_rs_leaders(stocks, mkt, lookback=120, beat_only=True)
    assert all(s.beat_market for s in ranked)
    assert "C" not in [s.stock_id for s in ranked]


def test_to_row_shape():
    mkt = _market_down()
    s = rl.score_rs_leader({"stock_id": "2330", "name": "台積電",
                            "df": _series(+0.05, seed=2)}, mkt, lookback=120)
    row = s.to_row()
    assert set(row) >= {"代碼", "名稱", "RS(σ)", "個股報酬%", "大盤報酬%",
                        "超額%", "贏過大盤", "訊號", "_tier"}
    assert row["代碼"] == "2330"


def test_count_insufficient():
    mkt = _market_down()
    stocks = [
        {"stock_id": "A", "name": "", "df": _series(+0.10, seed=31)},
        {"stock_id": "D", "name": "", "df": _series(+0.10, n=8, seed=32)},
    ]
    assert rl.count_insufficient(stocks, mkt, lookback=120) == 1
