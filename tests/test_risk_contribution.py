"""tests/test_risk_contribution.py — 投組風險貢獻分解(v19.137 Risk Contribution）。

驗 Euler 分解正確性 + §1 誠實邊界:
  - 風險佔比加總 = 100%(Euler)
  - 等 vol 正交資產等權 → 風險 50/50
  - 高 vol 資產風險佔比 > 市值佔比(集中警示)
  - 單檔 = 100%;缺價剔除不灌 0;樣本不足旗標;零波動 note。

用「符號樣式」合成序列建構已知共變異(正交 + 可控 vol),斷言為精確值而非估計。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.compute.risk.risk_contribution import compute_risk_contribution


def _orthogonal_returns(n_tiles: int = 25, scales=(1.0, 1.0)):
    """回 DataFrame:兩檔『正交、零相關、vol 由 scales 控制』的日報酬。

    a 樣式 [+1,-1,+1,-1]、b 樣式 [+1,+1,-1,-1] → 均值 0、相互正交(cov=0)。
    tile 加長 → 觀測數充足(> min_overlap)。
    """
    a = np.tile([1.0, -1.0, 1.0, -1.0], n_tiles) * scales[0]
    b = np.tile([1.0, 1.0, -1.0, -1.0], n_tiles) * scales[1]
    idx = pd.date_range("2024-01-01", periods=len(a), freq="D")
    return pd.DataFrame({"AAA": a, "BBB": b}, index=idx)


# ── Euler / 基本正確性 ────────────────────────────────────────
def test_risk_pct_sums_to_100():
    ret = _orthogonal_returns()
    res = compute_risk_contribution(ret, {"AAA": 1.0, "BBB": 1.0})
    assert res.ok
    assert abs(float(res.table["risk_pct"].sum()) - 100.0) < 0.2   # 加總=100(±rounding)


def test_equal_vol_equal_weight_splits_5050():
    ret = _orthogonal_returns(scales=(1.0, 1.0))
    res = compute_risk_contribution(ret, {"AAA": 50.0, "BBB": 50.0})  # 給 % 也可(scale-free)
    _risk = dict(zip(res.table["ticker"], res.table["risk_pct"]))
    assert abs(_risk["AAA"] - 50.0) < 0.1 and abs(_risk["BBB"] - 50.0) < 0.1


def test_high_vol_asset_carries_more_risk_than_weight():
    # AAA vol = 3×BBB;等權 → 風險應約 90/10(w·σ²w 比 = 9:1)
    ret = _orthogonal_returns(scales=(3.0, 1.0))
    res = compute_risk_contribution(ret, {"AAA": 1.0, "BBB": 1.0})
    _row = res.table.set_index("ticker")
    assert abs(_row.loc["AAA", "weight_pct"] - 50.0) < 0.1
    assert _row.loc["AAA", "risk_pct"] > 85.0            # 風險遠高於市值
    assert _row.loc["AAA", "gap_pct"] > 30.0             # 風險放大顯著
    assert bool(_row.loc["AAA", "concentrated"]) is True  # 觸發集中警示
    assert bool(_row.loc["BBB", "concentrated"]) is False


def test_sorted_by_risk_desc():
    ret = _orthogonal_returns(scales=(3.0, 1.0))
    res = compute_risk_contribution(ret, {"AAA": 1.0, "BBB": 1.0})
    assert list(res.table["ticker"]) == ["AAA", "BBB"]   # 高風險在前


def test_annualized_vol_positive():
    ret = _orthogonal_returns()
    res = compute_risk_contribution(ret, {"AAA": 1.0, "BBB": 1.0})
    assert res.portfolio_vol_annual_pct > 0 and np.isfinite(res.portfolio_vol_annual_pct)


# ── §1 誠實邊界 ──────────────────────────────────────────────
def test_single_asset_is_100pct():
    idx = pd.date_range("2024-01-01", periods=80, freq="D")
    ret = pd.DataFrame({"AAA": np.tile([1.0, -1.0], 40)}, index=idx)
    res = compute_risk_contribution(ret, {"AAA": 1.0})
    assert res.ok and len(res.table) == 1
    assert abs(float(res.table["risk_pct"].iloc[0]) - 100.0) < 0.1


def test_missing_price_history_excluded_not_zero_filled():
    # CCC 有權重但 returns 無此欄 → 剔除 + 記市值%,不灌 0 假裝
    ret = _orthogonal_returns()
    res = compute_risk_contribution(ret, {"AAA": 1.0, "BBB": 1.0, "CCC": 2.0})
    assert "CCC" not in list(res.table["ticker"])
    assert res.excluded == ("CCC",)
    assert abs(res.excluded_weight_pct - 50.0) < 0.1     # CCC 佔 2/4 原始市值
    assert "CCC" in res.note


def test_low_confidence_flag_when_few_obs():
    # 僅 12 觀測 < 60 → low_confidence，但仍給結果
    ret = _orthogonal_returns(n_tiles=3)   # 12 obs
    res = compute_risk_contribution(ret, {"AAA": 1.0, "BBB": 1.0})
    assert res.ok and res.n_obs == 12 and res.low_confidence is True
    assert "可信度較低" in res.note


def test_zero_variance_portfolio_returns_note_not_fake():
    idx = pd.date_range("2024-01-01", periods=80, freq="D")
    ret = pd.DataFrame({"AAA": np.zeros(80), "BBB": np.zeros(80)}, index=idx)
    res = compute_risk_contribution(ret, {"AAA": 1.0, "BBB": 1.0})
    assert not res.ok and "波動為 0" in res.note


def test_empty_returns_and_empty_weights():
    assert not compute_risk_contribution(pd.DataFrame(), {"AAA": 1.0}).ok
    ret = _orthogonal_returns()
    assert not compute_risk_contribution(ret, {}).ok
    assert not compute_risk_contribution(ret, {"AAA": 0.0, "BBB": -3.0}).ok  # 無正權重


def test_weights_scale_free():
    # 權重給比例 vs 給張數市值,結果相同(內部正規化)
    ret = _orthogonal_returns(scales=(2.0, 1.0))
    r1 = compute_risk_contribution(ret, {"AAA": 0.5, "BBB": 0.5})
    r2 = compute_risk_contribution(ret, {"AAA": 1_000_000, "BBB": 1_000_000})
    pd.testing.assert_frame_equal(r1.table, r2.table)


def test_euler_reconciliation_holds_on_correlated_assets():
    # 加入相關性(非正交)仍須 Σ RC = σ_p → 不 raise + 加總 100
    a = np.tile([1.0, -1.0, 0.5, -0.5], 25)
    b = a * 0.6 + np.tile([0.2, -0.1, -0.2, 0.1], 25)   # 與 a 正相關
    idx = pd.date_range("2024-01-01", periods=len(a), freq="D")
    ret = pd.DataFrame({"AAA": a, "BBB": b}, index=idx)
    res = compute_risk_contribution(ret, {"AAA": 0.7, "BBB": 0.3})
    assert res.ok and abs(float(res.table["risk_pct"].sum()) - 100.0) < 0.2


# ── property-based:任意權重/vol,風險佔比恆加總 100 且非負 ──
@pytest.mark.parametrize("wa,wb,sa,sb", [
    (0.3, 0.7, 1.0, 2.0), (0.9, 0.1, 1.5, 0.5), (0.5, 0.5, 1.0, 1.0),
    (0.2, 0.8, 3.0, 1.0),
])
def test_property_risk_sums_100_and_nonneg(wa, wb, sa, sb):
    ret = _orthogonal_returns(scales=(sa, sb))
    res = compute_risk_contribution(ret, {"AAA": wa, "BBB": wb})
    assert res.ok
    assert abs(float(res.table["risk_pct"].sum()) - 100.0) < 0.2
    assert (res.table["risk_pct"] >= 0).all()   # 正交 → 風險貢獻非負
