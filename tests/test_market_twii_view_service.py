"""tests/test_market_twii_view_service.py — UI-M 圖 A 的薄 L3 讀取層：attrs 透傳、讀不到不回空殼、不快取。"""
from __future__ import annotations

import ast
import pathlib

import pandas as pd
import pytest

from src.services import market_twii_view_service as S

_SRC = pathlib.Path(S.__file__).read_text(encoding="utf-8")


def _series(n=5, attrs=None):
    _idx = pd.date_range("2026-10-20", periods=n, freq="D")
    _s = pd.Series([22000.0 + i for i in range(n)], index=_idx, name="twii_close")
    _s.attrs.update(attrs if attrs is not None else {
        "is_stale": False, "stale_reason": None, "as_of": _idx[-1].date(),
        "age_days": 1, "upstream_error": None})
    return _s


def _patch(monkeypatch, s):
    import src.data.macro.macro_cache_reader as R
    monkeypatch.setattr(R, "load_twii_close", lambda *a, **k: s)


def test_attrs_are_passed_through(monkeypatch):
    _patch(monkeypatch, _series(5, {"is_stale": True, "stale_reason": "落後 4 個交易日",
                                    "as_of": pd.Timestamp("2026-10-24").date(),
                                    "age_days": 5, "upstream_error": "HTTP 429"}))
    v = S.get_twii_trend_view(3)
    assert v.ok and len(v.xs) == len(v.close) == 3 and v.n_available == 5
    assert v.is_stale is True and v.stale_reason == "落後 4 個交易日"
    assert v.age_days == 5 and v.upstream_error == "HTTP 429" and v.as_of == "2026-10-24"
    assert v.xs[-1] == "2026-10-24"


def test_window_larger_than_data_returns_all_rows_not_padded(monkeypatch):
    _patch(monkeypatch, _series(4))
    v = S.get_twii_trend_view(250)
    assert len(v.close) == 4 and v.n_available == 4   # ⛔ 不補到 250 筆


@pytest.mark.parametrize("bad", (pd.Series(dtype=float), None))
def test_unreadable_is_explicit_not_empty_shell(monkeypatch, bad):
    _patch(monkeypatch, bad)
    v = S.get_twii_trend_view(10)
    assert v.ok is False and v.xs == () and v.close == () and v.as_of is None
    assert v.error and v.is_stale is None
    assert v.failed is False       # 讀不到（灰）≠ 例外（紅）


def test_loader_exception_is_reported_not_swallowed(monkeypatch):
    import src.data.macro.macro_cache_reader as R

    def _boom(*a, **k):
        raise RuntimeError("disk gone")
    monkeypatch.setattr(R, "load_twii_close", _boom)
    v = S.get_twii_trend_view(10)
    assert v.ok is False and v.failed is True       # 真例外 → 紅
    assert "RuntimeError" in v.error and "disk gone" in v.error


def test_missing_attrs_means_staleness_unknown_not_fresh(monkeypatch):
    _patch(monkeypatch, _series(3, {}))
    v = S.get_twii_trend_view(3)
    assert v.ok and v.is_stale is None and v.age_days is None   # ⬜ 未判定，⛔ 不當成新鮮
    assert v.as_of == "2026-10-22"                              # 退回序列最後一筆（真實資料日，非今天）


def test_n_must_be_positive():
    with pytest.raises(ValueError):
        S.get_twii_trend_view(0)


def test_no_streamlit_cache_and_no_streamlit_import():
    """不快取（失敗不得被凍成 TTL）、L3 不依賴 UI 框架。"""
    _tree = ast.parse(_SRC)
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            assert not any(_a.name.split(".")[0] == "streamlit" for _a in _n.names)
        if isinstance(_n, ast.ImportFrom):
            assert (_n.module or "").split(".")[0] != "streamlit"
    assert "cache_data" not in _SRC and "cache_resource" not in _SRC


def test_real_parquet_roundtrip_if_present():
    """repo 內有快取檔時：真讀一次（attrs 事實存在、序列升序、無 NaN）。"""
    v = S.get_twii_trend_view(60)
    if not v.ok:
        pytest.skip(f"沙箱沒有 twii_ohlcv.parquet：{v.error}")
    assert list(v.xs) == sorted(v.xs) and all(c == c for c in v.close)
    assert v.is_stale in (True, False, None)
    assert v.as_of is not None
