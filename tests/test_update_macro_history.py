"""tests/test_update_macro_history.py — Parquet 讀寫 + 增量去重邏輯 smoke。"""
from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import pandas as pd
import pytest


def test_merge_dedupe_keeps_latest_on_collision():
    """同 date 同時出現在 old 與 new → 應保留 new 的版本（資料修正情境）。"""
    from update_macro_history import _merge_dedupe
    old = pd.DataFrame({
        "date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2)],
        "close": [15000.0, 15100.0],
    })
    new = pd.DataFrame({
        "date": [dt.date(2026, 1, 2), dt.date(2026, 1, 3)],
        "close": [15150.0, 15200.0],  # 1/2 被修正
    })
    out = _merge_dedupe(old, new, key="date")
    assert len(out) == 3
    assert float(out.loc[out["date"] == dt.date(2026, 1, 2), "close"].iloc[0]) == 15150.0


def test_merge_dedupe_sorts_by_key():
    """合併結果必須按 date 升序排列。"""
    from update_macro_history import _merge_dedupe
    old = pd.DataFrame({"date": [dt.date(2026, 1, 3)], "close": [15000.0]})
    new = pd.DataFrame({"date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2)],
                        "close": [14000.0, 14500.0]})
    out = _merge_dedupe(old, new, key="date")
    assert list(out["date"]) == [dt.date(2026, 1, 1), dt.date(2026, 1, 2), dt.date(2026, 1, 3)]


def test_parquet_roundtrip_preserves_dtypes():
    """Parquet 寫入後讀回必須維持 date / numeric 型別。"""
    from update_macro_history import CACHE_DIR
    with tempfile.TemporaryDirectory() as tmpdir:
        # monkey-patch CACHE_DIR for isolation
        original_cache = CACHE_DIR
        try:
            import update_macro_history as umh
            umh.CACHE_DIR = Path(tmpdir)
            df = pd.DataFrame({
                "date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2)],
                "close": [15000.5, 15100.3],
            })
            umh._write_parquet("test_roundtrip", df)
            out = umh._load_existing("test_roundtrip")
            assert out is not None
            assert len(out) == 2
            assert pd.api.types.is_numeric_dtype(out["close"])
        finally:
            umh.CACHE_DIR = original_cache


def test_last_date_handles_empty_and_missing():
    """空 df / 缺欄位 / None 都應回 None 而非 raise。"""
    from update_macro_history import _last_date
    assert _last_date(None) is None
    assert _last_date(pd.DataFrame()) is None
    assert _last_date(pd.DataFrame({"other": [1, 2]})) is None


def test_last_date_returns_max():
    """正常情境回最大 date。"""
    from update_macro_history import _last_date
    df = pd.DataFrame({"date": [dt.date(2026, 1, 5), dt.date(2026, 1, 3),
                                 dt.date(2026, 1, 4)]})
    assert _last_date(df) == dt.date(2026, 1, 5)


def test_update_one_skips_when_up_to_date(monkeypatch):
    """如果 existing 的 last_date 已 ≥ today，應跳過抓取（避免空打 API）。"""
    import update_macro_history as umh

    with tempfile.TemporaryDirectory() as tmpdir:
        umh.CACHE_DIR = Path(tmpdir)
        # 預埋一份 cache，last_date = today
        today = dt.date.today()
        df_old = pd.DataFrame({"date": [today], "close": [15000.0]})
        umh._write_parquet("twii_ohlcv", df_old)

        # mock fetch_twii_ohlcv 不應被呼叫
        call_count = {"n": 0}
        def _fake_fetch(start, end):
            call_count["n"] += 1
            return pd.DataFrame()
        monkeypatch.setitem(umh.FETCHERS, "twii_ohlcv", (_fake_fetch, False))
        meta = umh.update_one("twii_ohlcv", today, bootstrap=False, years=5, token="")
        assert call_count["n"] == 0, "已是最新時不應呼叫 fetch"
        assert meta["last_updated"] == today.isoformat()


def test_update_one_handles_finmind_without_token():
    """FinMind 缺 token 應 graceful 跳過、不 raise。"""
    import update_macro_history as umh
    with tempfile.TemporaryDirectory() as tmpdir:
        umh.CACHE_DIR = Path(tmpdir)
        today = dt.date.today()
        meta = umh.update_one("finmind_inst", today, bootstrap=False, years=5, token="")
        assert meta["last_error"] is not None
        assert "FINMIND_TOKEN" in meta["last_error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
