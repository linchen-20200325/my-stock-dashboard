"""tests/test_macro_validation_tw.py — Phase C 台股總經 tab 歷史驗證引擎 (v18.150)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.compute.macro import (
    detect_twii_crisis_events,
    load_twii_close_from_parquet,
)

# ════════════════════════════════════════════════════════════════
# Parquet 讀取 helpers + tests
# ════════════════════════════════════════════════════════════════
def _write_twii_parquet(cache_dir: Path, points: list[tuple]) -> None:
    """points: [(date_str, close_float), ...]; OHLCV 都填 close."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for d, c in points:
        rows.append({"date": d, "open": c, "high": c, "low": c,
                     "close": c, "volume": 1_000_000})
    pd.DataFrame(rows).to_parquet(
        cache_dir / "twii_ohlcv.parquet", index=False)

def test_load_twii_missing_file(tmp_path: Path):
    assert load_twii_close_from_parquet(tmp_path / "noexist").empty

def test_load_twii_extracts_close_column(tmp_path: Path):
    _write_twii_parquet(tmp_path, [("2024-01-01", 17500.0),
                                    ("2024-01-02", 17600.0)])
    s = load_twii_close_from_parquet(tmp_path)
    assert len(s) == 2
    assert s.iloc[1] == 17600.0

def test_load_twii_handles_corrupt_parquet_graceful(tmp_path: Path):
    """壞 Parquet 檔不該 raise — 印警告然後跳過。"""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "twii_ohlcv.parquet").write_bytes(b"not_real_parquet")
    s = load_twii_close_from_parquet(tmp_path)
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

# UI 守衛測試已退役(v18.399 R6 真刪)
# tab_macro_validation.py 整檔已刪除(audit 確認 UI 0 unique 邏輯,backend
# macro_validation_tw / macro_signal_lookback_tw / multi_factor_optimization 全保留)。
# 原 3 個 source-string 守衛測試(test_ui_section_in_tab_macro_source /
# test_ui_module_exposes_render_function / test_ui_validation_section_before_ai_verdict)
# 因失去保護對象,同步退役。Backend 邏輯測試(本檔上方 9 個 case)全保留。

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
