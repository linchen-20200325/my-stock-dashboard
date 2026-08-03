"""tests/test_efficient_frontier.py — v19.167 守衛:效率前緣（風險-報酬地圖,§1 誠實 + §5 可重現）。

釘死 L2 `etf_calc.compute_efficient_frontier` 的行為(**描述性**視覺化,非規範性最佳化):
  - §7 年化:μ_annual = mean(日報酬) × TRADING_DAYS_PER_YEAR;
             Σ_annual = 日報酬.cov(ddof=1) × TRADING_DAYS_PER_YEAR(math.isclose 容差)。
  - 組合 vol = sqrt(wᵀ Σ_annual w)(與純 Python 手算 wᵀΣw 對帳);Sharpe = ret/vol(rf=0)。
  - current_point 用**使用者給定權重**(只用有共同歷史者、重新正規化 Σ=1)。
  - §5 可重現:同 seed → 完全相同的雲;不同 seed → 不同。
  - 前緣包絡線非遞減 + 罩住雲(上緣)。
  - §1 fail-loud 邊界:單檔 / 空 / 共同日 <20 / 零共同日 → ok=False + 空,絕不捏造前緣。
測試路徑與正式 fetcher 物理隔離(純合成 Series,無 I/O;資料由 test RNG 生,參考值同陣列手算)。
"""
from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")

from shared.signal_thresholds import (
    EFFICIENT_FRONTIER_MIN_COMMON_DAYS,
    TRADING_DAYS_PER_YEAR,
)
from src.compute.etf.etf_calc import compute_efficient_frontier

_TOL = dict(rel_tol=1e-9, abs_tol=1e-12)
_ANN = float(TRADING_DAYS_PER_YEAR)


def _mk_returns(seed=0, n=120, start="2024-01-01"):
    """合成 3 檔日報酬(test RNG 決定;參考值一律從『同一批陣列』手算,非照抄實作)。"""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="B")
    specs = {"A": (0.0008, 0.010), "B": (0.0004, 0.006), "C": (0.0012, 0.015)}
    return {t: pd.Series(rng.normal(mu, sd, n), index=idx) for t, (mu, sd) in specs.items()}


def _cov(x, y):
    """純 Python 樣本共變異數(ddof=1),證明不是照抄 pandas.cov()。"""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (n - 1)


# ── 1. 年化 μ / σ 正確性(每檔單獨一點 = eᵢ)──────────────────────
def test_annualized_mu_sigma_per_asset():
    rets = _mk_returns(seed=1)
    out = compute_efficient_frontier(rets, {"A": 40, "B": 30, "C": 30})
    assert out["ok"] is True
    assert out["n_common"] == 120
    assert set(out["per_asset_points"].keys()) == {"A", "B", "C"}

    for t, s in rets.items():
        vals = s.tolist()
        exp_ret = (sum(vals) / len(vals)) * _ANN                 # μ_annual
        exp_vol = math.sqrt(_cov(vals, vals) * _ANN)             # σ_annual = sqrt(var*252)
        got = out["per_asset_points"][t]
        assert math.isclose(got["ret"], exp_ret, **_TOL), t
        assert math.isclose(got["vol"], exp_vol, **_TOL), t


# ── 2. 組合 vol = sqrt(wᵀ Σ w)(2 檔,純 Python 手算 wᵀΣw 對帳)──────
def test_portfolio_vol_matches_hand_wSw():
    rets = _mk_returns(seed=2)
    x, y = rets["A"].tolist(), rets["B"].tolist()
    w0, w1 = 0.6, 0.4                                            # 已 Σ=1(正規化為恆等)
    Sxx = _cov(x, x) * _ANN
    Syy = _cov(y, y) * _ANN
    Sxy = _cov(x, y) * _ANN
    exp_var = w0 * w0 * Sxx + w1 * w1 * Syy + 2 * w0 * w1 * Sxy
    exp_vol = math.sqrt(exp_var)
    exp_ret = w0 * (sum(x) / len(x)) * _ANN + w1 * (sum(y) / len(y)) * _ANN

    out = compute_efficient_frontier({"A": rets["A"], "B": rets["B"]},
                                     {"A": 0.6, "B": 0.4})
    cp = out["current_point"]
    assert cp is not None
    assert math.isclose(cp["vol"], exp_vol, **_TOL)
    assert math.isclose(cp["ret"], exp_ret, **_TOL)
    # Sharpe = ret / vol(rf=0)
    assert math.isclose(cp["sharpe"], exp_ret / exp_vol, **_TOL)


# ── 3. current_point 用給定權重、重新正規化、忽略 0 / 缺 ────────────
def test_current_point_normalizes_and_ignores_zero_weight():
    rets = _mk_returns(seed=3)
    # 給未加總=1 的權重 + 一檔 0 → 只用 A/B、正規化到 0.5/0.5(C 不佔分母)
    out = compute_efficient_frontier(rets, {"A": 50, "B": 50, "C": 0})
    x, y = rets["A"].tolist(), rets["B"].tolist()
    Sxx, Syy, Sxy = _cov(x, x) * _ANN, _cov(y, y) * _ANN, _cov(x, y) * _ANN
    exp_var = 0.25 * Sxx + 0.25 * Syy + 2 * 0.5 * 0.5 * Sxy
    exp_ret = 0.5 * (sum(x) / len(x)) * _ANN + 0.5 * (sum(y) / len(y)) * _ANN
    cp = out["current_point"]
    assert math.isclose(cp["vol"], math.sqrt(exp_var), **_TOL)
    assert math.isclose(cp["ret"], exp_ret, **_TOL)


def test_current_point_none_when_no_valid_weights():
    """無有效權重(全 0 / 缺)→ current_point=None,但仍畫地圖(cloud 存在)。"""
    rets = _mk_returns(seed=4)
    out = compute_efficient_frontier(rets, {"A": 0, "B": 0, "C": 0})
    assert out["ok"] is True
    assert out["current_point"] is None
    assert len(out["cloud"]["vol"]) > 0


# ── 4. §5 可重現:同 seed → 完全相同;不同 seed → 不同 ───────────────
def test_reproducibility_same_seed_identical_cloud():
    rets = _mk_returns(seed=5)
    a = compute_efficient_frontier(rets, {"A": 40, "B": 30, "C": 30}, seed=42)
    b = compute_efficient_frontier(rets, {"A": 40, "B": 30, "C": 30}, seed=42)
    assert a["cloud"]["vol"] == b["cloud"]["vol"]
    assert a["cloud"]["ret"] == b["cloud"]["ret"]
    assert a["cloud"]["sharpe"] == b["cloud"]["sharpe"]
    assert a["frontier"] == b["frontier"]


def test_reproducibility_different_seed_differs():
    rets = _mk_returns(seed=5)
    a = compute_efficient_frontier(rets, {"A": 40, "B": 30, "C": 30}, seed=42)
    c = compute_efficient_frontier(rets, {"A": 40, "B": 30, "C": 30}, seed=7)
    assert a["cloud"]["vol"] != c["cloud"]["vol"]


# ── 5. 前緣包絡線:非遞減 + 罩住雲(上緣)────────────────────────────
def test_frontier_non_decreasing_and_upper_bounds():
    rets = _mk_returns(seed=6)
    out = compute_efficient_frontier(rets, {"A": 40, "B": 30, "C": 30})
    fx = out["frontier"]["vol"]
    fy = out["frontier"]["ret"]
    assert len(fx) >= 2
    # x 遞增(箱中心)、y 非遞減(cummax)
    assert all(fx[i] < fx[i + 1] for i in range(len(fx) - 1))
    assert all(fy[i] <= fy[i + 1] + 1e-12 for i in range(len(fy) - 1))
    # 上緣:前緣最高點 == 雲最高報酬(cummax 必達全域最大且不超過)
    assert math.isclose(max(fy), max(out["cloud"]["ret"]), rel_tol=1e-9, abs_tol=1e-12)
    # 前緣所有值都 ≤ 雲最高報酬(不無中生有更高的點)
    assert max(fy) <= max(out["cloud"]["ret"]) + 1e-12


# ── 6. min-var / max-Sharpe 參考點取自雲 ──────────────────────────
def test_min_var_and_max_sharpe_from_cloud():
    rets = _mk_returns(seed=7)
    out = compute_efficient_frontier(rets, {"A": 40, "B": 30, "C": 30})
    vols = out["cloud"]["vol"]
    shs = [s for s in out["cloud"]["sharpe"] if s is not None]
    # 最小變異點的 vol = 雲最小 vol
    assert math.isclose(out["min_var_point"]["vol"], min(vols), **_TOL)
    # 最大夏普點的 sharpe = 雲最大(有限)sharpe
    assert math.isclose(out["max_sharpe_point"]["sharpe"], max(shs), **_TOL)


# ── 7. cloud Sharpe = ret / vol(rf=0)、雲每列權重 Σ=1(vol/ret 有限)──
def test_cloud_sharpe_is_ret_over_vol_rf_zero():
    rets = _mk_returns(seed=8)
    out = compute_efficient_frontier(rets, {"A": 40, "B": 30, "C": 30})
    v, r, s = out["cloud"]["vol"], out["cloud"]["ret"], out["cloud"]["sharpe"]
    for i in range(0, len(v), 137):   # 抽樣檢查
        if s[i] is not None and v[i] > 0:
            assert math.isclose(s[i], r[i] / v[i], **_TOL)
        assert v[i] >= 0.0
        assert math.isfinite(r[i])


# ── 8. §1 邊界:單檔 → ok=False(單檔無「配置」可言)──────────────────
def test_one_asset_ok_false():
    rets = _mk_returns(seed=9)
    out = compute_efficient_frontier({"A": rets["A"]}, {"A": 100})
    assert out["ok"] is False
    assert out["cloud"]["vol"] == [] and out["frontier"]["vol"] == []
    assert out["current_point"] is None
    assert out["min_var_point"] is None and out["max_sharpe_point"] is None


# ── 9. §1 邊界:空輸入 → ok=False ─────────────────────────────────
def test_empty_input_ok_false():
    out = compute_efficient_frontier({}, {})
    assert out["ok"] is False
    assert out["n_common"] == 0
    assert out["per_asset_points"] == {}


# ── 10. §1 邊界:共同日 <MIN_COMMON_DAYS → ok=False(不捏造前緣)──────
def test_insufficient_common_days_ok_false():
    n = EFFICIENT_FRONTIER_MIN_COMMON_DAYS - 1     # 剛好不足門檻
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(10)
    a = pd.Series(rng.normal(0, 0.01, n), index=idx)
    b = pd.Series(rng.normal(0, 0.01, n), index=idx)
    out = compute_efficient_frontier({"A": a, "B": b}, {"A": 50, "B": 50})
    assert out["ok"] is False
    assert str(n) in out["note"]


# ── 11. §1 邊界:兩檔但日期完全不重疊 → 共同日 0 → ok=False ──────────
def test_disjoint_dates_ok_false():
    a = pd.Series([0.01, 0.02, 0.03], index=pd.date_range("2024-01-01", periods=3, freq="B"))
    b = pd.Series([0.01, 0.02, 0.03], index=pd.date_range("2024-06-01", periods=3, freq="B"))
    out = compute_efficient_frontier({"A": a, "B": b}, {"A": 50, "B": 50})
    assert out["ok"] is False


# ── 12. §1 對齊:只取共同日(dropna),不補值 ──────────────────────────
def test_common_day_intersection_no_fill():
    rng = np.random.default_rng(11)
    # A: 40 個交易日;B: 後移 5 日、也 40 日 → 共同日 = 交集(<40 但仍 ≥20)
    idxA = pd.date_range("2024-01-01", periods=40, freq="B")
    idxB = pd.date_range("2024-01-08", periods=40, freq="B")
    a = pd.Series(rng.normal(0, 0.01, 40), index=idxA)
    b = pd.Series(rng.normal(0, 0.01, 40), index=idxB)
    out = compute_efficient_frontier({"A": a, "B": b}, {"A": 50, "B": 50})
    assert out["ok"] is True
    assert out["n_common"] == len(idxA.intersection(idxB))
    assert out["n_common"] < 40                       # 確有被交集壓縮
    # 無 NaN 汙染:雲全有限
    assert all(math.isfinite(v) for v in out["cloud"]["vol"])


# ── 13. tz-aware 索引 → 去 tz 後仍能對齊 ───────────────────────────
def test_tz_aware_index_aligns():
    rng = np.random.default_rng(12)
    idx_utc = pd.date_range("2024-01-01", periods=30, freq="B", tz="UTC")
    idx_naive = pd.date_range("2024-01-01", periods=30, freq="B")
    a = pd.Series(rng.normal(0, 0.01, 30), index=idx_utc)
    b = pd.Series(rng.normal(0, 0.01, 30), index=idx_naive)
    out = compute_efficient_frontier({"A": a, "B": b}, {"A": 50, "B": 50})
    assert out["ok"] is True
    assert out["n_common"] == 30


# ── 14. 契約 key 齊全 ─────────────────────────────────────────────
def test_contract_keys():
    rets = _mk_returns(seed=13)
    out = compute_efficient_frontier(rets, {"A": 40, "B": 30, "C": 30})
    for k in ("ok", "note", "tickers_used", "n_common", "cloud", "frontier",
              "current_point", "per_asset_points", "min_var_point", "max_sharpe_point"):
        assert k in out, f"缺 key: {k}"
    for ck in ("vol", "ret", "sharpe"):
        assert ck in out["cloud"]
    for fk in ("vol", "ret"):
        assert fk in out["frontier"]
    # 雲三陣列等長
    assert len(out["cloud"]["vol"]) == len(out["cloud"]["ret"]) == len(out["cloud"]["sharpe"])


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
