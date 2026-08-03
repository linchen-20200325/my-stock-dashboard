"""tests/test_portfolio_vs_benchmark.py — v19.166 守衛:組合 vs 0050 累積報酬(§1 誠實)。

釘死 L2 `etf_calc.compute_portfolio_vs_benchmark` 的行為:
  - 累積報酬 = (1+日報酬).cumprod()-1(§7 對齊,decimal;math.isclose 容差比較)。
  - 三曲線(組合/基準/個別)一律在**同一組共同交易日**上算(§1 交集,絕不 ffill / fillna(0))。
  - 基準空 / 無共同日 → benchmark_ok=False + 空 Series(交 UI fail loud,不畫假曲線)。
測試路徑與正式 fetcher 物理隔離(純合成 Series,無 I/O)。
"""
from __future__ import annotations

import math

import pytest

pd = pytest.importorskip("pandas")

from src.compute.etf.etf_calc import compute_portfolio_vs_benchmark

_TOL = dict(rel_tol=1e-9, abs_tol=1e-12)


def _series(vals, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(vals), freq="D")
    return pd.Series([float(v) for v in vals], index=idx)


def _cumprod_expected(vals):
    """獨立參考實作:純 Python 手算 (1+r).cumprod()-1,證明不是照抄 pandas。"""
    out, acc = [], 1.0
    for v in vals:
        acc *= (1.0 + v)
        out.append(acc - 1.0)
    return out


# ── 1. cumprod 正確性(已知輸入,math.isclose 容差)──────────────────
def test_cumprod_known_input_single_asset():
    A = _series([0.10, -0.05, 0.20])          # weight 100 → 組合 == A
    bench = _series([0.01, 0.02, 0.03])
    out = compute_portfolio_vs_benchmark({"A": A}, {"A": 100}, bench)

    assert out["benchmark_ok"] is True
    assert out["n_common"] == 3

    exp_port = _cumprod_expected([0.10, -0.05, 0.20])   # [0.10, 0.045, 0.254]
    got_port = out["portfolio_cum"].tolist()
    assert len(got_port) == len(exp_port)
    for g, e in zip(got_port, exp_port):
        assert math.isclose(g, e, **_TOL)
    assert math.isclose(out["final"]["portfolio"], 0.254, **_TOL)

    exp_bench = _cumprod_expected([0.01, 0.02, 0.03])
    for g, e in zip(out["benchmark_cum"].tolist(), exp_bench):
        assert math.isclose(g, e, **_TOL)
    # 個別 A 曲線 == 組合曲線(單檔滿權重)
    assert math.isclose(out["final"]["per_asset"]["A"],
                        out["final"]["portfolio"], **_TOL)


# ── 2. 共同日對齊:資產不同日期範圍 → 只取交集,不補值 ──────────────
def test_common_day_intersection_no_fill():
    # A: D1..D5;B: D3..D7 → 資產共同日 D3..D5(3 天);bench 覆蓋全段
    A = _series([0.01, 0.02, -0.01, 0.03, 0.00], start="2024-01-01")
    B = _series([0.05, -0.02, 0.01, 0.02, -0.01], start="2024-01-03")
    bench = _series([0.001] * 10, start="2024-01-01")
    out = compute_portfolio_vs_benchmark({"A": A, "B": B}, {"A": 50, "B": 50}, bench)

    assert out["n_common"] == 3
    idx = out["dates"]
    assert str(idx.min().date()) == "2024-01-03"
    assert str(idx.max().date()) == "2024-01-05"
    assert out["limiter"] == "B"
    assert str(out["limiter_start"].date()) == "2024-01-03"
    # 絕不補值:所有輸出無 NaN
    assert not out["portfolio_cum"].isna().any()
    assert not out["benchmark_cum"].isna().any()
    for s in out["per_asset_cum"].values():
        assert not s.isna().any()
    # 手算:共同日 D3..D5 的加權日報酬(0.5A+0.5B)再 cumprod
    a = [-0.01, 0.03, 0.00]      # A 於 D3..D5
    b = [0.05, -0.02, 0.01]      # B 於 D3..D5
    port_r = [0.5 * x + 0.5 * y for x, y in zip(a, b)]
    for g, e in zip(out["portfolio_cum"].tolist(), _cumprod_expected(port_r)):
        assert math.isclose(g, e, **_TOL)


# ── 3. 基準對齊:基準缺某共同日 → 進一步剔除,只留三方共同日 ──────────
def test_benchmark_alignment_drops_non_common():
    A = _series([0.01, 0.02, 0.03], start="2024-01-01")   # D1..D3
    B = _series([0.00, 0.01, -0.01], start="2024-01-01")  # D1..D3
    # 基準只有 D1、D3(缺 D2)→ 最終共同日 D1、D3
    bench = pd.Series([0.02, 0.04],
                      index=pd.to_datetime(["2024-01-01", "2024-01-03"]))
    out = compute_portfolio_vs_benchmark({"A": A, "B": B}, {"A": 50, "B": 50}, bench)

    assert out["n_common"] == 2
    assert out["n_common_assets"] == 3       # 資產本身有 3 共同日
    assert out["dropped_vs_benchmark"] == 1  # 基準缺 D2 → 剔 1 天
    assert [str(d.date()) for d in out["dates"]] == ["2024-01-01", "2024-01-03"]
    # 基準曲線就 2 點,cumprod 從 D1 重新起算(不含被剔的 D2)
    for g, e in zip(out["benchmark_cum"].tolist(), _cumprod_expected([0.02, 0.04])):
        assert math.isclose(g, e, **_TOL)


# ── 4. 個別持股曲線:每檔都在同一共同 index 上、weight=0 檔不列入 ──────
def test_per_asset_curves_and_zero_weight_excluded():
    A = _series([0.01, 0.02, 0.03])
    B = _series([0.02, -0.01, 0.04])
    C = _series([0.05, 0.05, 0.05])
    bench = _series([0.01, 0.01, 0.01])
    # C 權重 0 → 不進組合、不畫個別線(align 只留有權重且有資料者)
    out = compute_portfolio_vs_benchmark(
        {"A": A, "B": B, "C": C}, {"A": 70, "B": 30, "C": 0}, bench)

    assert set(out["per_asset_cum"].keys()) == {"A", "B"}
    assert "C" not in out["tickers_used"]
    # A 個別曲線 == 自身 cumprod
    for g, e in zip(out["per_asset_cum"]["A"].tolist(), _cumprod_expected([0.01, 0.02, 0.03])):
        assert math.isclose(g, e, **_TOL)
    # 組合 = 0.7A + 0.3B(重新正規化,C 不佔分母)
    port_r = [0.7 * x + 0.3 * y for x, y in zip([0.01, 0.02, 0.03], [0.02, -0.01, 0.04])]
    for g, e in zip(out["portfolio_cum"].tolist(), _cumprod_expected(port_r)):
        assert math.isclose(g, e, **_TOL)


# ── 5. 邊界:空持股 → benchmark_ok=False + 空 Series(不腦補)──────────
def test_empty_assets_fail_loud():
    bench = _series([0.01, 0.02, 0.03])
    out = compute_portfolio_vs_benchmark({}, {}, bench)
    assert out["benchmark_ok"] is False
    assert out["portfolio_cum"].empty and out["benchmark_cum"].empty
    assert out["per_asset_cum"] == {}
    assert out["n_common"] == 0
    assert out["final"]["portfolio"] is None and out["final"]["benchmark"] is None


# ── 6. 邊界:空基準 → benchmark_ok=False(UI 該 fail loud,不畫假曲線)──
def test_empty_benchmark_fail_loud():
    A = _series([0.01, 0.02, 0.03])
    out = compute_portfolio_vs_benchmark({"A": A}, {"A": 100}, pd.Series(dtype="float64"))
    assert out["benchmark_ok"] is False
    assert out["portfolio_cum"].empty
    assert out["dates"].empty if hasattr(out["dates"], "empty") else len(out["dates"]) == 0


# ── 7. 邊界:單檔持股 → 組合曲線 == 該檔曲線 ──────────────────────
def test_one_asset_portfolio_equals_asset():
    A = _series([0.02, -0.03, 0.05, 0.01])
    bench = _series([0.01, 0.01, 0.01, 0.01])
    out = compute_portfolio_vs_benchmark({"A": A}, {"A": 100}, bench)
    assert out["tickers_used"] == ["A"]
    assert list(out["portfolio_cum"].values) == pytest.approx(
        list(out["per_asset_cum"]["A"].values), rel=1e-12, abs=1e-12)


# ── 8. 邊界:組合與基準零共同日 → benchmark_ok=False + 診斷正確 ──────
def test_no_common_days_between_portfolio_and_benchmark():
    A = _series([0.01, 0.02, 0.03], start="2024-01-01")   # D1..D3
    bench = _series([0.01, 0.02], start="2024-06-01")      # 完全不重疊
    out = compute_portfolio_vs_benchmark({"A": A}, {"A": 100}, bench)
    assert out["benchmark_ok"] is False
    assert out["n_common"] == 0
    assert out["dropped_vs_benchmark"] == 3   # 3 個資產共同日全被基準剔掉


# ── 9. tz-aware 索引 → 內部去 tz 後仍能交集(不因 tz 不一致漏日)──────
def test_tz_aware_index_aligns():
    idx = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    A = pd.Series([0.01, 0.02, 0.03], index=idx)
    bench = pd.Series([0.01, 0.01, 0.01],
                      index=pd.date_range("2024-01-01", periods=3, freq="D"))  # tz-naive
    out = compute_portfolio_vs_benchmark({"A": A}, {"A": 100}, bench)
    assert out["benchmark_ok"] is True
    assert out["n_common"] == 3


# ── 10. 契約 key 齊全 ─────────────────────────────────────────────
def test_contract_keys():
    A = _series([0.01, 0.02, 0.03])
    bench = _series([0.01, 0.02, 0.03])
    out = compute_portfolio_vs_benchmark({"A": A}, {"A": 100}, bench)
    for k in ("dates", "portfolio_cum", "benchmark_cum", "per_asset_cum",
              "n_common", "tickers_used", "final", "benchmark_ok",
              "n_union", "n_common_assets", "dropped_assets",
              "dropped_vs_benchmark", "limiter", "limiter_start"):
        assert k in out, f"缺 key: {k}"
    for fk in ("portfolio", "benchmark", "per_asset"):
        assert fk in out["final"]
