"""tests/test_position_sizing_wiring.py — 斷鏈② 接線契約測試（v19.146）。

驗「個股頁 → 建議部位」實際走的呼叫鏈：
    calc_atr_stop(df, 現價) → atr → calculate_position_size(總資金, 現價, atr)

UI（section_when_buy_sell.py）用的就是這兩個 L2 純函式，這裡釘住 §6 三個最容易
出錯的輸入 + 單位（元 vs 張，1張=1000股）+ 15% 停損上限截斷 + 風險金額對帳。
（純函式離線可測，不碰網路。）
"""
from __future__ import annotations

import pandas as pd

from src.compute.scoring import calc_atr_stop, calculate_position_size
from shared.signal_thresholds import POS_MAX_RISK_PCT, POS_MAX_STOP_PCT


def _make_df(n: int, price: float = 100.0, hl_span: float = 1.0) -> pd.DataFrame:
    """n 根 K 線，收盤固定 price，高低各 ±hl_span → True Range ≈ 2×hl_span。"""
    close = [price] * n
    return pd.DataFrame({
        "open": close,
        "high": [price + hl_span] * n,
        "low": [price - hl_span] * n,
        "close": close,
        "volume": [1000] * n,
    })


def test_normal_position_whole_lots_and_risk_reconciles():
    """一般低波動股：算得出整張、成本>0、停損錨進場價、風險金額 = 資金×1.5%。"""
    df = _make_df(30, price=100.0, hl_span=1.0)   # TR≈2 → ATR≈2
    atr = calc_atr_stop(df, 100.0)["atr"]
    assert atr and atr > 0

    pos = calculate_position_size(1_000_000, 100.0, atr)
    assert "error" not in pos
    # 整張：position_sh 必為 1000 的倍數
    assert pos["position_sh"] % 1000 == 0
    assert pos["position_lot"] >= 1
    assert pos["cost"] > 0
    # 停損錨定進場價，且在 [15%上限, 進場價) 之間
    assert 100.0 * POS_MAX_STOP_PCT <= pos["stop_loss"] < 100.0
    # 風險金額對帳：總資金 × 1.5%
    assert pos["max_risk"] == round(1_000_000 * POS_MAX_RISK_PCT, 0)
    assert pos["rr_ratio"] > 0


def test_data_insufficient_atr_is_none():
    """K線 <14 根 → calc_atr_stop 回 atr=None（UI 據此顯示「資料不足」不硬算 §1）。"""
    df = _make_df(10, price=100.0, hl_span=1.0)
    info = calc_atr_stop(df, 100.0)
    assert info["atr"] is None
    assert info["method"] == "fixed_8pct"


def test_capital_too_small_zero_lots():
    """資金太小 → 買不到 1 整張 → position_lot == 0（UI 顯示誠實提示，非灌 1 張）。"""
    df = _make_df(30, price=100.0, hl_span=1.0)   # ATR≈2 → risk/股≈3
    atr = calc_atr_stop(df, 100.0)["atr"]
    pos = calculate_position_size(1000, 100.0, atr)   # 風險額=15 元，買不到整張
    assert pos["position_lot"] == 0
    assert pos["position_sh"] == 0


def test_high_vol_stop_floored_at_15pct():
    """高波動股：1.5×ATR 超過 15% → 停損被 15% 上限截斷（防單筆停損過寬）。"""
    df = _make_df(30, price=100.0, hl_span=20.0)  # TR≈40 → ATR≈40，1.5×40=60 > 15
    atr = calc_atr_stop(df, 100.0)["atr"]
    assert atr and atr > 10
    pos = calculate_position_size(1_000_000, 100.0, atr)
    # 停損被夾在 entry×0.85 = 85（不會跌到 40）
    assert pos["stop_loss"] == round(100.0 * POS_MAX_STOP_PCT, 2)
    assert pos["risk_per_sh"] == round(100.0 * (1 - POS_MAX_STOP_PCT), 2)


def test_lots_cost_consistent():
    """成本 = 張數×1000×現價（單位一致性：不會元/張混用）。"""
    df = _make_df(30, price=50.0, hl_span=0.5)
    atr = calc_atr_stop(df, 50.0)["atr"]
    pos = calculate_position_size(2_000_000, 50.0, atr)
    assert pos["cost"] == round(pos["position_sh"] * 50.0, 0)
    assert pos["position_sh"] == pos["position_lot"] * 1000
