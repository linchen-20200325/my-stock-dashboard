"""tests/test_macro_validation_tw.py — Phase C 台股總經 tab 歷史驗證引擎 (v18.150)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from macro_validation_tw import (
    NdcVerifyResult,
    LeadingIndexVerifyResult,
    TwiiCrisisEvent,
    compute_hit_rate,
    compute_smoothed_change_pct,
    detect_twii_crisis_events,
    load_leading_index_from_parquet,
    load_ndc_signal_from_parquet,
    load_twii_close_from_parquet,
    verify_leading_index_vs_crises,
    verify_ndc_signal_vs_crises,
)


# ════════════════════════════════════════════════════════════════
# Parquet 讀取 helpers + tests
# ════════════════════════════════════════════════════════════════
def _write_ndc_parquet(cache_dir: Path, points: list[tuple]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{"date": d, "ndc_signal": int(v)} for d, v in points])
    df.to_parquet(cache_dir / "finmind_ndc_signal.parquet", index=False)


def _write_li_parquet(cache_dir: Path, points: list[tuple]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{"date": d, "leading_index": float(v)} for d, v in points])
    df.to_parquet(cache_dir / "finmind_leading_index.parquet", index=False)


def _write_twii_parquet(cache_dir: Path, points: list[tuple]) -> None:
    """points: [(date_str, close_float), ...]; OHLCV 都填 close."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for d, c in points:
        rows.append({"date": d, "open": c, "high": c, "low": c,
                     "close": c, "volume": 1_000_000})
    pd.DataFrame(rows).to_parquet(
        cache_dir / "twii_ohlcv.parquet", index=False)


def test_load_ndc_missing_file_returns_empty_series(tmp_path: Path):
    s = load_ndc_signal_from_parquet(tmp_path / "noexist")
    assert s.empty
    assert s.name == "ndc_signal"


def test_load_ndc_parses_correctly(tmp_path: Path):
    _write_ndc_parquet(tmp_path, [("2024-01-01", 25), ("2024-02-01", 30)])
    s = load_ndc_signal_from_parquet(tmp_path)
    assert len(s) == 2
    assert s.iloc[0] == 25.0
    assert s.iloc[1] == 30.0
    assert isinstance(s.index, pd.DatetimeIndex)


def test_load_li_missing_file(tmp_path: Path):
    assert load_leading_index_from_parquet(tmp_path / "noexist").empty


def test_load_li_parses_correctly(tmp_path: Path):
    _write_li_parquet(tmp_path, [("2024-01-01", 102.5), ("2024-02-01", 103.1)])
    s = load_leading_index_from_parquet(tmp_path)
    assert len(s) == 2
    assert s.iloc[0] == 102.5


def test_load_twii_missing_file(tmp_path: Path):
    assert load_twii_close_from_parquet(tmp_path / "noexist").empty


def test_load_twii_extracts_close_column(tmp_path: Path):
    _write_twii_parquet(tmp_path, [("2024-01-01", 17500.0),
                                    ("2024-01-02", 17600.0)])
    s = load_twii_close_from_parquet(tmp_path)
    assert len(s) == 2
    assert s.iloc[1] == 17600.0


def test_load_handles_corrupt_parquet_graceful(tmp_path: Path):
    """壞 Parquet 檔不該 raise — 印警告然後跳過。"""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "finmind_ndc_signal.parquet").write_bytes(b"not_real_parquet")
    s = load_ndc_signal_from_parquet(tmp_path)
    assert s.empty


# ════════════════════════════════════════════════════════════════
# detect_twii_crisis_events
# ════════════════════════════════════════════════════════════════
def _make_close_series(daily_values: list[float], start: str = "2020-01-01"
                      ) -> pd.Series:
    """建合成 TWII 收盤序列：start 起連續日。"""
    idx = pd.date_range(start, periods=len(daily_values), freq="D")
    return pd.Series(daily_values, index=idx, name="twii_close")


def test_detect_twii_crisis_basic_v_shape():
    """100 → 70 → 100 = 30% 回撤事件，應命中。"""
    # 30 天先穩定 100，然後線性跌到 70，然後回升到 100，後面繼續
    rise = [100.0 + i * 0.1 for i in range(40)]   # peak 上揚
    fall = list(map(lambda x: 100.0 * (1 - x * 0.01), range(31)))   # 100 → 70
    recover = list(map(lambda x: 70.0 + x, range(31)))   # 70 → 100
    plateau = [100.0] * 30
    s = _make_close_series(rise + fall + recover + plateau)
    events = detect_twii_crisis_events(s, drop_threshold=0.20)
    assert len(events) >= 1
    ev = events[0]
    assert ev.drawdown_pct < -0.20
    assert ev.trough_close < ev.peak_close


def test_detect_twii_no_crisis_below_threshold():
    """只回撤 10% → 在 20% 門檻下無事件。"""
    rise = [100.0] * 30
    minor_dip = [100.0 - i * 0.5 for i in range(20)]   # 100 → 90
    recover = [90.0 + i * 0.5 for i in range(20)]      # 90 → 100
    s = _make_close_series(rise + minor_dip + recover)
    events = detect_twii_crisis_events(s, drop_threshold=0.20)
    assert events == []


def test_detect_twii_empty_series_returns_empty():
    assert detect_twii_crisis_events(pd.Series(dtype=float)) == []


def test_detect_twii_too_short_returns_empty():
    """少於 30 日無法穩定偵測，回空。"""
    s = _make_close_series([100.0] * 10 + [70.0] * 5)
    assert detect_twii_crisis_events(s) == []


def test_detect_twii_open_ended_crisis_no_recovery():
    """到序列結尾仍在 crisis（未 recovery） → recovery_date=None."""
    rise = [100.0] * 40
    fall = [100.0 - i * 0.5 for i in range(60)]   # 100 → 70
    s = _make_close_series(rise + fall)
    events = detect_twii_crisis_events(s, drop_threshold=0.20)
    assert len(events) >= 1
    assert events[-1].recovery_date is None


def test_detect_twii_multiple_events_with_recovery():
    """100 → 70 → 100 → 60 → 100：兩個 crisis 事件。"""
    rise = [100.0] * 30
    fall1 = [100.0 - i * 1.0 for i in range(31)]   # 100→70
    recover1 = [70.0 + i for i in range(31)]        # 70→100
    plateau = [100.0] * 20
    fall2 = [100.0 - i * 1.0 for i in range(41)]    # 100→60
    recover2 = [60.0 + i for i in range(41)]        # 60→100
    s = _make_close_series(rise + fall1 + recover1 + plateau + fall2 + recover2)
    events = detect_twii_crisis_events(s, drop_threshold=0.20)
    assert len(events) >= 2


# ════════════════════════════════════════════════════════════════
# verify_ndc_signal_vs_crises
# ════════════════════════════════════════════════════════════════
def _fake_twii_event(peak_date: str, drawdown: float = -0.30) -> TwiiCrisisEvent:
    return TwiiCrisisEvent(
        peak_date=pd.Timestamp(peak_date),
        peak_close=100.0,
        trough_date=pd.Timestamp(peak_date) + pd.DateOffset(months=3),
        trough_close=100.0 * (1 + drawdown),
        recovery_date=pd.Timestamp(peak_date) + pd.DateOffset(months=12),
        drawdown_pct=drawdown,
    )


def test_verify_ndc_hit_exact_4_pts_threshold():
    """峰前 6 月 NDC=25（2020-06）→ 峰時 NDC=21（2020-12）→ drop=-4 → 命中（門檻 4 分）。

    idx 18 = 2020-07-01 為跨界，lead_dt=2020-06-01 落在 index 17（val=25），
    peak_dt=2020-12-01 落在 index 23（val=21）。
    """
    idx = pd.date_range("2019-01-01", periods=36, freq="MS")
    vals = [25] * 18 + [21] * 18
    ndc = pd.Series(vals, index=idx, dtype=float)
    events = [_fake_twii_event("2020-12-01")]
    out = verify_ndc_signal_vs_crises(ndc, events, lead_months=6,
                                       drop_pts_threshold=4)
    assert len(out) == 1
    r = out[0]
    assert r.ndc_at_lead == 25
    assert r.ndc_at_peak == 21
    assert r.ndc_drop_pts == -4
    assert r.hit   # -4 ≤ -4 → 命中


def test_verify_ndc_hit_clear_drop():
    """峰前 6 月 NDC=30 → 峰時 NDC=22（下降 8 分） → 命中。"""
    idx = pd.date_range("2019-01-01", periods=36, freq="MS")
    vals = [30] * 18 + [22] * 18
    ndc = pd.Series(vals, index=idx, dtype=float)
    events = [_fake_twii_event("2020-12-01")]
    out = verify_ndc_signal_vs_crises(ndc, events, lead_months=6,
                                       drop_pts_threshold=4)
    r = out[0]
    assert r.ndc_drop_pts == -8
    assert r.hit


def test_verify_ndc_no_event_returns_empty():
    ndc = pd.Series([25] * 12, index=pd.date_range("2020-01-01", periods=12,
                                                     freq="MS"))
    out = verify_ndc_signal_vs_crises(ndc, [], lead_months=6,
                                       drop_pts_threshold=4)
    assert out == []


def test_verify_ndc_empty_series_returns_empty():
    out = verify_ndc_signal_vs_crises(
        pd.Series(dtype=float), [_fake_twii_event("2020-12-01")],
        lead_months=6, drop_pts_threshold=4)
    assert out == []


# ════════════════════════════════════════════════════════════════
# compute_smoothed_change_pct + verify_leading_index_vs_crises
# ════════════════════════════════════════════════════════════════
def test_compute_smoothed_change_constant_returns_zero():
    """常數序列 → MA 不變 → smoothed change = 0%."""
    idx = pd.date_range("2020-01-01", periods=24, freq="MS")
    s = pd.Series([100.0] * 24, index=idx)
    sm = compute_smoothed_change_pct(s, window=6)
    assert not sm.empty
    assert (abs(sm) < 1e-9).all()   # 全為 0


def test_compute_smoothed_change_rising_positive():
    """線性升 → smoothed change 全正。"""
    idx = pd.date_range("2020-01-01", periods=24, freq="MS")
    s = pd.Series([100.0 + i * 1.0 for i in range(24)], index=idx)
    sm = compute_smoothed_change_pct(s, window=6)
    assert (sm > 0).all()


def test_compute_smoothed_change_empty_input():
    assert compute_smoothed_change_pct(pd.Series(dtype=float)).empty


def test_verify_li_hit_when_peak_smooth_negative():
    """構造：peak 月時 6M smoothed change < 0 → 命中。"""
    # 24 月線性升，後 18 月線性降 → peak 在 ~36 月處
    rise = [100.0 + i * 1.0 for i in range(24)]
    fall = [124.0 - i * 1.5 for i in range(18)]
    idx = pd.date_range("2018-01-01", periods=42, freq="MS")
    li = pd.Series(rise + fall, index=idx)
    # crisis peak 在 fall 開始後 6 月
    events = [_fake_twii_event(str(idx[30].date()))]
    out = verify_leading_index_vs_crises(li, events, lead_months=6,
                                          smooth_window=6)
    assert len(out) == 1
    # 30 月時剛開始下降幾個月，smoothed change 應已轉負
    assert out[0].li_smooth_at_peak is not None
    assert out[0].li_smooth_at_peak < 0
    assert out[0].hit


def test_verify_li_miss_when_peak_smooth_positive():
    """單調上升序列 → smoothed change 永正 → 從不命中。"""
    idx = pd.date_range("2020-01-01", periods=36, freq="MS")
    li = pd.Series([100.0 + i for i in range(36)], index=idx)
    events = [_fake_twii_event(str(idx[24].date()))]
    out = verify_leading_index_vs_crises(li, events, lead_months=6,
                                          smooth_window=6)
    assert len(out) == 1
    assert not out[0].hit


def test_verify_li_empty_inputs():
    assert verify_leading_index_vs_crises(
        pd.Series(dtype=float),
        [_fake_twii_event("2020-12-01")]) == []
    idx = pd.date_range("2020-01-01", periods=24, freq="MS")
    li = pd.Series([100.0] * 24, index=idx)
    assert verify_leading_index_vs_crises(li, []) == []


# ════════════════════════════════════════════════════════════════
# compute_hit_rate
# ════════════════════════════════════════════════════════════════
def test_compute_hit_rate_mixed():
    results = [
        NdcVerifyResult(pd.Timestamp("2020-01-01"), -0.3, 25, 20, -5, True),
        NdcVerifyResult(pd.Timestamp("2021-01-01"), -0.25, 30, 28, -2, False),
        NdcVerifyResult(pd.Timestamp("2022-01-01"), -0.4, 32, 22, -10, True),
    ]
    n_hit, n_total, rate = compute_hit_rate(results)
    assert n_hit == 2
    assert n_total == 3
    assert abs(rate - 2 / 3) < 1e-6


def test_compute_hit_rate_empty():
    assert compute_hit_rate([]) == (0, 0, 0.0)


def test_compute_hit_rate_all_none_drop_pts():
    """全部 drop_pts=None → n_total=0 → rate=0."""
    results = [
        NdcVerifyResult(pd.Timestamp("2020-01-01"), -0.3, None, None, None, False),
    ]
    n_hit, n_total, rate = compute_hit_rate(results)
    assert n_total == 0
    assert rate == 0.0


# ════════════════════════════════════════════════════════════════
# UI source-level（不 mock-render，僅驗結構）
# ════════════════════════════════════════════════════════════════
def test_ui_section_in_tab_macro_source():
    """tab_macro.py 必須 import render_history_validation_section 且呼叫。"""
    src = (Path(__file__).parent.parent / "tab_macro.py").read_text(encoding="utf-8")
    assert "from tab_macro_validation import render_history_validation_section" in src
    assert "render_history_validation_section()" in src


def test_ui_module_exposes_render_function():
    """tab_macro_validation.py 必須 export render_history_validation_section."""
    import tab_macro_validation as tmv
    assert hasattr(tmv, "render_history_validation_section")
    assert callable(tmv.render_history_validation_section)


def test_ui_section_after_section_ten():
    """新 section 必須在 section 十 之後（保持原 1-10 順序不破壞）。"""
    src = (Path(__file__).parent.parent / "tab_macro.py").read_text(encoding="utf-8")
    idx_10 = src.find("'十'")
    idx_new = src.find("render_history_validation_section()")
    assert idx_10 > 0 and idx_new > 0
    assert idx_10 < idx_new, "新 section 必須在 section 十 之後"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
