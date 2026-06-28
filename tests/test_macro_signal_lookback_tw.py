"""test_macro_signal_lookback_tw.py — Phase 3 台股訊號回看引擎單元測試 (v18.159)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.compute.macro import (  # noqa: E402
    DEFAULT_TW_SIGNALS,
    TW_SIGNAL_FETCHERS,
    TwSignalLookback,
    TwSignalSpec,
    _is_warning,
    compute_signal_hit_rate,
    evaluate_signal_at_event,
    fetch_all_tw_signal_series,
    fetch_foreign_sell_5d_series,
    fetch_m1b_m2_diff_series,
    fetch_margin_balance_series,
    fetch_margin_growth_5d_series,
    fetch_twii_drop_20d_series,
    fetch_twii_realized_vol_20d_series,
    fetch_twse_vol_ratio_series,
    lookback_all_signals_tw,
)
from src.compute.macro import TwiiCrisisEvent  # noqa: E402


# ════════════════════════════════════════════════════════════════
# DEFAULT_TW_SIGNALS / Registry 完整性
# ════════════════════════════════════════════════════════════════
def test_default_signals_count_and_keys():
    # v18.178 Phase E：4 → 5（加 PMI_BELOW_50）
    assert len(DEFAULT_TW_SIGNALS) == 5
    keys = {s.key for s in DEFAULT_TW_SIGNALS}
    assert keys == {"FOREIGN_SELL_5D", "MARGIN_BALANCE",
                    "M1B_M2_DIFF", "TWII_DROP_20D", "PMI_BELOW_50"}


def test_fetchers_registry_covers_all_default_keys():
    for spec in DEFAULT_TW_SIGNALS:
        assert spec.key in TW_SIGNAL_FETCHERS


# ════════════════════════════════════════════════════════════════
# _is_warning 邊界
# ════════════════════════════════════════════════════════════════
def test_is_warning_above_inclusive_at_threshold():
    assert _is_warning(5.0, threshold=5.0, direction="above") is True
    assert _is_warning(5.01, threshold=5.0, direction="above") is True
    assert _is_warning(4.99, threshold=5.0, direction="above") is False


def test_is_warning_below_inclusive_at_threshold():
    assert _is_warning(-500.0, threshold=-500.0, direction="below") is True
    assert _is_warning(-501.0, threshold=-500.0, direction="below") is True
    assert _is_warning(-499.0, threshold=-500.0, direction="below") is False


# ════════════════════════════════════════════════════════════════
# Series fetchers — 缺檔 graceful
# ════════════════════════════════════════════════════════════════
def test_fetch_foreign_sell_5d_missing_returns_empty(tmp_path: Path):
    assert fetch_foreign_sell_5d_series(tmp_path).empty


def test_fetch_margin_balance_missing_returns_empty(tmp_path: Path):
    assert fetch_margin_balance_series(tmp_path).empty


def test_fetch_m1b_m2_diff_missing_returns_empty(tmp_path: Path):
    assert fetch_m1b_m2_diff_series(tmp_path).empty


def test_fetch_twii_drop_20d_missing_returns_empty(tmp_path: Path):
    assert fetch_twii_drop_20d_series(tmp_path).empty


# ════════════════════════════════════════════════════════════════
# Series fetchers — 正常 schema 解析
# ════════════════════════════════════════════════════════════════
def test_fetch_foreign_sell_5d_computes_rolling_sum(tmp_path: Path):
    """foreign_buy 連 5 日 [-100, -120, -110, -140, -150] → sum5 應為 -620。"""
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "foreign_buy": [-100, -120, -110, -140, -150, -200],
    })
    df.to_parquet(tmp_path / "finmind_inst.parquet", index=False)
    s = fetch_foreign_sell_5d_series(tmp_path)
    # 第 5 個位置（index 4）為 sum 前 5 筆
    assert s.iloc[0] == -620
    assert s.iloc[1] == -720


def test_fetch_margin_balance_converts_to_billions(tmp_path: Path):
    """margin_balance 原始單位元，÷ 1e8 → 億。"""
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "margin_balance": [340_000_000_000, 280_000_000_000, 350_000_000_000],
    })
    df.to_parquet(tmp_path / "finmind_margin.parquet", index=False)
    s = fetch_margin_balance_series(tmp_path)
    assert abs(s.iloc[0] - 3400.0) < 0.01
    assert abs(s.iloc[1] - 2800.0) < 0.01
    assert abs(s.iloc[2] - 3500.0) < 0.01


def test_fetch_m1b_m2_diff_computes_monthly_change(tmp_path: Path):
    """m1b_m2_gap [-30, -32, -28] → diff [NaN, -2, +4]."""
    dates = pd.date_range("2024-01-01", periods=3, freq="MS")
    df = pd.DataFrame({"date": dates, "m1b_m2_gap": [-30.0, -32.0, -28.0]})
    df.to_parquet(tmp_path / "finmind_m1m2.parquet", index=False)
    s = fetch_m1b_m2_diff_series(tmp_path)
    # 第一筆 NaN 經 dropna 已剔除
    assert len(s) == 2
    assert abs(s.iloc[0] - (-2.0)) < 0.01
    assert abs(s.iloc[1] - 4.0) < 0.01


def test_fetch_twii_drop_20d_computes_pct_change(tmp_path: Path):
    """close 從 100 → 90（20 日後）→ pct_change(20) = -10%."""
    dates = pd.date_range("2024-01-01", periods=22, freq="D")
    closes = [100.0] * 20 + [95.0, 90.0]
    df = pd.DataFrame({"date": dates, "close": closes})
    df.to_parquet(tmp_path / "twii_ohlcv.parquet", index=False)
    s = fetch_twii_drop_20d_series(tmp_path)
    # 倒數第二位（21 日，index 20）：close[20]=95 vs close[0]=100 → -5%
    assert abs(s.iloc[0] - (-5.0)) < 0.01
    # 最末（22 日，index 21）：close[21]=90 vs close[1]=100 → -10%
    assert abs(s.iloc[1] - (-10.0)) < 0.01


# ════════════════════════════════════════════════════════════════
# v18.168：3 個新 fetcher 缺檔 + 計算驗證
# ════════════════════════════════════════════════════════════════
def test_fetch_twse_vol_ratio_missing_returns_empty(tmp_path: Path):
    assert fetch_twse_vol_ratio_series(tmp_path).empty


def test_fetch_margin_growth_5d_missing_returns_empty(tmp_path: Path):
    assert fetch_margin_growth_5d_series(tmp_path).empty


def test_fetch_twii_realized_vol_20d_missing_returns_empty(tmp_path: Path):
    assert fetch_twii_realized_vol_20d_series(tmp_path).empty


def test_fetch_twse_vol_ratio_zscore_centered_zero(tmp_path: Path):
    """正常 60 日 SMA 後 z-score 平均應 ≈ 0；異常高量點應顯著正值."""
    import numpy as np
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    rng = np.random.default_rng(0)
    volumes = rng.normal(1e10, 1e9, n).clip(min=1e9)
    df = pd.DataFrame({"date": dates, "volume": volumes})
    df.to_parquet(tmp_path / "twii_ohlcv.parquet", index=False)
    s = fetch_twse_vol_ratio_series(tmp_path)
    assert not s.empty
    # z-score 全段平均應接近 0
    assert abs(s.mean()) < 0.1
    # 標準差應接近 1
    assert abs(s.std() - 1.0) < 0.05


def test_fetch_margin_growth_5d_diff(tmp_path: Path):
    """margin_balance 從 100 → 105（5 日後）億 → diff(5) = +5 億."""
    n = 7
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    # 100, 101, 102, 103, 104, 105 億；index 5 處 diff(5) = 105 - 100 = +5
    balances_billions = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 110.0]
    margin_raw = [b * 1e8 for b in balances_billions]
    df = pd.DataFrame({"date": dates, "margin_balance": margin_raw})
    df.to_parquet(tmp_path / "finmind_margin.parquet", index=False)
    s = fetch_margin_growth_5d_series(tmp_path)
    # dropna 後剩 index 5 = +5 億 / index 6 = +9 億
    assert len(s) == 2
    assert abs(s.iloc[0] - 5.0) < 0.01
    assert abs(s.iloc[1] - 9.0) < 0.01


def test_fetch_twii_realized_vol_20d_positive(tmp_path: Path):
    """波動率為正且 dropna 後長度合理（21 日 - 20 視窗 + 1 = 2，但 pct_change 又少 1）."""
    import numpy as np
    n = 50
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    rng = np.random.default_rng(0)
    closes = (100 * np.cumprod(1 + rng.normal(0, 0.01, n))).tolist()
    df = pd.DataFrame({"date": dates, "close": closes})
    df.to_parquet(tmp_path / "twii_ohlcv.parquet", index=False)
    s = fetch_twii_realized_vol_20d_series(tmp_path)
    assert not s.empty
    # 年化波動率合理區間（這資料 σ ≈ 1% daily → 年化 ≈ 16%）
    assert 5.0 < s.mean() < 50.0
    # 全為正
    assert (s >= 0).all()


def test_fetchers_registry_covers_v18_168_keys():
    """3 個新 key 都在 TW_SIGNAL_FETCHERS registry."""
    for key in ("TWSE_VOL_RATIO", "MARGIN_GROWTH_5D", "TWII_REALIZED_VOL_20D"):
        assert key in TW_SIGNAL_FETCHERS, f"{key} 未註冊"


# ════════════════════════════════════════════════════════════════
# fetch_all_tw_signal_series 批次
# ════════════════════════════════════════════════════════════════
def test_fetch_all_tw_signal_series_missing_dir(tmp_path: Path):
    out = fetch_all_tw_signal_series(tmp_path)
    assert set(out.keys()) == {s.key for s in DEFAULT_TW_SIGNALS}
    assert all(out[k].empty for k in out)


# ════════════════════════════════════════════════════════════════
# evaluate_signal_at_event 邊界
# ════════════════════════════════════════════════════════════════
def _mock_event(peak: str) -> TwiiCrisisEvent:
    return TwiiCrisisEvent(
        peak_date=pd.Timestamp(peak),
        peak_close=18000.0,
        trough_date=pd.Timestamp(peak) + pd.Timedelta(days=60),
        trough_close=15000.0,
        recovery_date=None,
        drawdown_pct=-0.20,
    )


def _spec_above(threshold=25.0):
    return TwSignalSpec(key="X", label="X", threshold=threshold,
                        direction="above", unit="", note="")


def _spec_below(threshold=-5.0):
    return TwSignalSpec(key="Y", label="Y", threshold=threshold,
                        direction="below", unit="", note="")


def test_evaluate_empty_series_returns_none_fields():
    ev = _mock_event("2024-06-01")
    spec = _spec_above(25.0)
    lb = evaluate_signal_at_event(ev, pd.Series(dtype=float), spec)
    assert lb.value_at_lookback is None
    assert lb.triggered_at_lookback is False
    assert lb.first_warning_date is None
    assert lb.lead_time_days is None


def test_evaluate_value_at_lookback_picks_on_or_before():
    """peak=2024-06-01, lookback=90 → target=2024-03-03，取 ≤ target 最後一筆。"""
    ev = _mock_event("2024-06-01")
    idx = pd.date_range("2024-01-01", "2024-05-31", freq="D")
    s = pd.Series([10.0] * len(idx), index=idx)
    spec = _spec_above(25.0)
    lb = evaluate_signal_at_event(ev, s, spec, lookback_days=90)
    assert lb.value_at_lookback == 10.0
    assert lb.triggered_at_lookback is False  # 10 < 25 不警戒


def test_evaluate_triggered_at_lookback_above():
    ev = _mock_event("2024-06-01")
    idx = pd.date_range("2024-01-01", "2024-05-31", freq="D")
    s = pd.Series([30.0] * len(idx), index=idx)  # 全 30 ≥ 25
    spec = _spec_above(25.0)
    lb = evaluate_signal_at_event(ev, s, spec, lookback_days=90)
    assert lb.triggered_at_lookback is True


def test_evaluate_first_warning_finds_earliest():
    """edge mode：series 在 2024-04-01 從非警戒（10）跨越進警戒（30）→ 最早 crossing 為 2024-04-01。"""
    ev = _mock_event("2024-06-01")
    idx_before = pd.date_range("2023-06-01", "2024-03-31", freq="D")
    s_before = pd.Series([10.0] * len(idx_before), index=idx_before)
    idx_warn = pd.date_range("2024-04-01", "2024-05-31", freq="D")
    s_warn = pd.Series([30.0] * len(idx_warn), index=idx_warn)
    s = pd.concat([s_before, s_warn])
    spec = _spec_above(25.0)
    lb = evaluate_signal_at_event(ev, s, spec, lookback_days=90,
                                   max_lookback_days=365)
    assert lb.first_warning_date == pd.Timestamp("2024-04-01")
    assert lb.lead_time_days == (pd.Timestamp("2024-06-01")
                                  - pd.Timestamp("2024-04-01")).days


# ════════════════════════════════════════════════════════════════
# v18.160 edge mode：避免「整窗都在警戒」假預警
# ════════════════════════════════════════════════════════════════
def test_evaluate_edge_mode_no_crossing_returns_none():
    """series 一直在警戒區（無 transition）→ edge mode 應回 None（不算預警）。

    這是 v18.160 修 bug 的核心：v1 state mode 會誤判成「提前 max_lookback 天」。
    """
    ev = _mock_event("2024-06-01")
    idx = pd.date_range("2024-01-01", "2024-05-31", freq="D")
    s = pd.Series([30.0] * len(idx), index=idx)  # 全在警戒
    spec = _spec_above(25.0)
    lb = evaluate_signal_at_event(ev, s, spec, lookback_days=90,
                                   max_lookback_days=180, mode="edge")
    # edge mode：沒看到 transition → None
    assert lb.first_warning_date is None
    assert lb.lead_time_days is None


def test_evaluate_state_mode_legacy_still_works():
    """state mode（legacy）：series 一直在警戒區，回最早一日（v1 行為）。"""
    ev = _mock_event("2024-06-01")
    idx = pd.date_range("2024-01-01", "2024-05-31", freq="D")
    s = pd.Series([30.0] * len(idx), index=idx)
    spec = _spec_above(25.0)
    lb = evaluate_signal_at_event(ev, s, spec, lookback_days=90,
                                   max_lookback_days=180, mode="state")
    # state mode：仍會回 window 內最早一日
    assert lb.first_warning_date is not None


def test_evaluate_edge_mode_picks_transition_in_window():
    """series 早期在警戒，中期回到非警戒，晚期再次警戒 → edge 應抓晚期的 transition。"""
    ev = _mock_event("2024-12-01")
    # 早期窗外警戒（被忽略）→ 警戒退出 → window 內再次警戒（這才是 edge）
    idx1 = pd.date_range("2024-01-01", "2024-03-31", freq="D")  # 全 30 警戒
    idx2 = pd.date_range("2024-04-01", "2024-08-31", freq="D")  # 全 10 非警戒
    idx3 = pd.date_range("2024-09-01", "2024-11-30", freq="D")  # 全 30 警戒
    s = pd.concat([
        pd.Series([30.0] * len(idx1), index=idx1),
        pd.Series([10.0] * len(idx2), index=idx2),
        pd.Series([30.0] * len(idx3), index=idx3),
    ])
    spec = _spec_above(25.0)
    lb = evaluate_signal_at_event(ev, s, spec, lookback_days=90,
                                   max_lookback_days=180, mode="edge")
    assert lb.first_warning_date == pd.Timestamp("2024-09-01")
    assert lb.lead_time_days == (pd.Timestamp("2024-12-01")
                                  - pd.Timestamp("2024-09-01")).days


def test_evaluate_default_mode_is_edge():
    """v18.160 起 mode 預設值為 'edge'，UI 不傳 mode 也應走 edge 邏輯。"""
    ev = _mock_event("2024-06-01")
    idx = pd.date_range("2024-01-01", "2024-05-31", freq="D")
    s = pd.Series([30.0] * len(idx), index=idx)  # 全警戒，edge 應回 None
    spec = _spec_above(25.0)
    lb = evaluate_signal_at_event(ev, s, spec)  # 不傳 mode
    assert lb.first_warning_date is None


def test_evaluate_below_direction_works():
    """direction='below'：series 全 -10，threshold=-5 → 觸發。"""
    ev = _mock_event("2024-06-01")
    idx = pd.date_range("2024-01-01", "2024-05-31", freq="D")
    s = pd.Series([-10.0] * len(idx), index=idx)
    spec = _spec_below(-5.0)
    lb = evaluate_signal_at_event(ev, s, spec, lookback_days=90)
    assert lb.triggered_at_lookback is True


# ════════════════════════════════════════════════════════════════
# lookback_all_signals_tw
# ════════════════════════════════════════════════════════════════
def test_lookback_all_signals_tw_returns_dict_keyed_by_spec():
    # v18.178 Phase E：DEFAULT_TW_SIGNALS 加 PMI_BELOW_50 → 5 keys
    ev = _mock_event("2024-06-01")
    series_by_key = {
        "FOREIGN_SELL_5D": pd.Series(dtype=float),
        "MARGIN_BALANCE": pd.Series(dtype=float),
        "M1B_M2_DIFF": pd.Series(dtype=float),
        "TWII_DROP_20D": pd.Series(dtype=float),
        "PMI_BELOW_50": pd.Series(dtype=float),
    }
    out = lookback_all_signals_tw([ev], series_by_key)
    assert set(out.keys()) == set(series_by_key.keys())
    assert all(len(v) == 1 for v in out.values())


# ════════════════════════════════════════════════════════════════
# compute_signal_hit_rate
# ════════════════════════════════════════════════════════════════
def _mock_lookback(value=None, lead=None, first_warn=None) -> TwSignalLookback:
    return TwSignalLookback(
        event_peak_date=pd.Timestamp("2024-06-01"),
        signal_key="X", signal_label="X",
        threshold=0.0, direction="above",
        lookback_days=90,
        value_at_lookback=value,
        triggered_at_lookback=False,
        first_warning_date=first_warn,
        lead_time_days=lead,
    )


def test_hit_rate_empty_returns_zero_total():
    stats = compute_signal_hit_rate([])
    assert stats["n_total"] == 0
    assert stats["hit_rate"] is None


def test_hit_rate_mixed_coverage_and_hits():
    """3 個 lookback：1 命中（lead=100）/ 1 涵蓋未命中 / 1 不涵蓋."""
    lbs = [
        _mock_lookback(value=30.0, lead=100, first_warn=pd.Timestamp("2024-02-01")),
        _mock_lookback(value=20.0, lead=None, first_warn=None),
        _mock_lookback(value=None, lead=None, first_warn=None),
    ]
    stats = compute_signal_hit_rate(lbs)
    assert stats["n_total"] == 3
    assert stats["n_covered"] == 2
    assert stats["n_hit"] == 1
    assert stats["hit_rate"] == 0.5    # 1/2
    assert stats["avg_lead_days"] == 100


# ════════════════════════════════════════════════════════════════
# v18.163：訊號精確率（forward-looking）測試
# ════════════════════════════════════════════════════════════════
from src.compute.macro import compute_signal_precision  # noqa: E402


class TestComputeSignalPrecision:
    def test_empty_series_returns_zero(self):
        stat = compute_signal_precision(
            pd.Series([], dtype=float), [_mock_event("2020-01-01")],
            _spec_above(25.0))
        assert stat["n_crossings"] == 0
        assert stat["precision_pct"] is None

    def test_all_true_positives(self):
        """每個 crossing 後 30 天就有 event 命中 → 100% precision。"""
        idx = pd.date_range("2020-01-01", "2023-12-31", freq="MS")
        # 5 個月 below + 1 月 above + 5 月 below + 1 月 above ... → 多次 crossing
        values = [30.0 if i % 6 == 5 else 10.0 for i in range(len(idx))]
        series = pd.Series(values, index=idx, name="X")
        # 每個 crossing 日後 30 天剛好放一個 event
        crossing_dates = [idx[i] for i in range(len(idx)) if i % 6 == 5]
        events = [_mock_event(str((d + pd.Timedelta(days=30)).date()))
                  for d in crossing_dates]
        stat = compute_signal_precision(series, events, _spec_above(25.0),
                                          max_forward_days=365)
        assert stat["n_crossings"] == len(crossing_dates)
        assert stat["n_true_positives"] == stat["n_crossings"]
        assert stat["n_false_positives"] == 0
        assert stat["precision_pct"] == 100.0
        assert stat["false_alert_rate_pct"] == 0.0

    def test_all_false_positives(self):
        """crossings 都在 events 之後很遠 → 全 FP。"""
        idx = pd.date_range("2020-01-01", "2023-12-31", freq="MS")
        values = [10.0] * 12 + [30.0] * (len(idx) - 12)
        series = pd.Series(values, index=idx, name="X")
        # event 在 2015，遠在 series 起點之前 → crossing 後找不到 future event
        events = [_mock_event("2015-06-01")]
        stat = compute_signal_precision(series, events, _spec_above(25.0),
                                          max_forward_days=365)
        assert stat["n_crossings"] == 1  # 只 1 個 transition
        assert stat["n_true_positives"] == 0
        assert stat["n_false_positives"] == 1
        assert stat["precision_pct"] == 0.0
        assert stat["false_alert_rate_pct"] == 100.0

    def test_mixed_tp_fp(self):
        """2 crossings：第 1 個有 event 命中，第 2 個沒。"""
        idx = pd.date_range("2020-01-01", periods=400, freq="D")
        # day 50 transition up，day 150 down，day 250 transition up
        values = [10.0] * 50 + [30.0] * 100 + [10.0] * 100 + [30.0] * 150
        series = pd.Series(values, index=idx, name="X")
        # event 在 day 100 → 第 1 個 crossing (day 50) 在 365 天內命中
        # 第 2 個 crossing (day 250) 在 365 天內無 event → FP
        events = [_mock_event(str(idx[100].date()))]
        stat = compute_signal_precision(series, events, _spec_above(25.0),
                                          max_forward_days=365)
        assert stat["n_crossings"] == 2
        assert stat["n_true_positives"] == 1
        assert stat["n_false_positives"] == 1
        assert stat["precision_pct"] == 50.0
        assert stat["false_alert_rate_pct"] == 50.0

    def test_window_boundary_inclusive(self):
        """event 剛好在 crossing + max_forward_days 邊界 → 算 TP（≤ 包含）."""
        idx = pd.date_range("2020-01-01", periods=400, freq="D")
        values = [10.0] * 50 + [30.0] * 350
        series = pd.Series(values, index=idx, name="X")
        # crossing 在 day 50；event 剛好在 day 50 + 365
        events = [_mock_event(str((idx[50] + pd.Timedelta(days=365)).date()))]
        stat = compute_signal_precision(series, events, _spec_above(25.0),
                                          max_forward_days=365)
        assert stat["n_true_positives"] == 1
        assert stat["precision_pct"] == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
