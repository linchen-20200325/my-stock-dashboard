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


# ════════════════════════════════════════════════════════════════
# 景氣對策信號 + 領先指標（FinMind TaiwanBusinessIndicator wide-format）
# ════════════════════════════════════════════════════════════════
def _fake_business_indicator_df(rows: list[dict]) -> pd.DataFrame:
    """Helper：偽造 TaiwanBusinessIndicator wide-format 回應。"""
    return pd.DataFrame(rows)


def test_datasets_includes_ndc_and_leading():
    """新增的兩個 dataset 必須註冊在 DATASETS 與 FETCHERS。"""
    import update_macro_history as umh
    assert "finmind_ndc_signal" in umh.DATASETS
    assert "finmind_leading_index" in umh.DATASETS
    # 都需要 FINMIND_TOKEN
    assert umh.FETCHERS["finmind_ndc_signal"][1] is True
    assert umh.FETCHERS["finmind_leading_index"][1] is True


def test_pick_macro_column_basic():
    """從 wide-format 抽出 [date, value] 並轉型；NaN 應 drop。"""
    from update_macro_history import _pick_macro_column
    df = _fake_business_indicator_df([
        {"date": "2024-01-31", "leading": 102.5, "monitoring": 25},
        {"date": "2024-02-29", "leading": 103.1, "monitoring": 30},
        {"date": "2024-03-31", "leading": None, "monitoring": 28},  # NaN drop
    ])
    out = _pick_macro_column(df, "monitoring")
    assert list(out.columns) == ["date", "value"]
    assert len(out) == 3
    assert out["value"].tolist() == [25.0, 30.0, 28.0]
    out2 = _pick_macro_column(df, "leading")
    assert len(out2) == 2  # NaN row 被 drop
    assert out2["value"].tolist() == [102.5, 103.1]


def test_pick_macro_column_missing_column():
    """請求的欄位不存在 → 回空（不 raise）。"""
    from update_macro_history import _pick_macro_column
    df = _fake_business_indicator_df([
        {"date": "2024-01-31", "leading": 102.5},
    ])
    assert _pick_macro_column(df, "monitoring").empty


def test_pick_macro_column_empty_input():
    """空 / None / 缺 date 欄 → 回空。"""
    from update_macro_history import _pick_macro_column
    assert _pick_macro_column(pd.DataFrame(), "monitoring").empty
    assert _pick_macro_column(None, "monitoring").empty
    assert _pick_macro_column(pd.DataFrame({"x": [1]}), "monitoring").empty


def test_macro_table_uses_taiwan_business_indicator(monkeypatch):
    """_finmind_macro_table 必須打 FinMind v4 的 TaiwanBusinessIndicator dataset。"""
    import update_macro_history as umh
    umh._MACRO_FULL_TABLE_CACHE.clear()
    captured = {"dataset": None}

    def _fake_finmind_get(dataset, data_id, start, end, token):
        captured["dataset"] = dataset
        return _fake_business_indicator_df([
            {"date": "2024-01-31", "leading": 102.5, "monitoring": 25},
        ])

    monkeypatch.setattr(umh, "_finmind_get", _fake_finmind_get)
    umh._finmind_macro_table(dt.date(2024, 1, 1), dt.date(2024, 2, 1), "tok")
    assert captured["dataset"] == "TaiwanBusinessIndicator"


def test_macro_table_cache_skips_second_call(monkeypatch):
    """_finmind_macro_table 同 key 第二次 call 應走 cache，不重打 API。"""
    import update_macro_history as umh
    umh._MACRO_FULL_TABLE_CACHE.clear()
    call_count = {"n": 0}

    def _fake_finmind_get(dataset, data_id, start, end, token):
        call_count["n"] += 1
        return _fake_business_indicator_df([
            {"date": "2024-01-31", "leading": 102.5, "monitoring": 25},
        ])

    monkeypatch.setattr(umh, "_finmind_get", _fake_finmind_get)
    start = dt.date(2024, 1, 1)
    end = dt.date(2024, 2, 1)
    umh._finmind_macro_table(start, end, "tok")
    umh._finmind_macro_table(start, end, "tok")  # 應走 cache
    assert call_count["n"] == 1


def test_fetch_ndc_signal_shape(monkeypatch):
    """fetch_finmind_ndc_signal 回 [date, ndc_signal] + Int64 + round。"""
    import update_macro_history as umh
    umh._MACRO_FULL_TABLE_CACHE.clear()
    fake = _fake_business_indicator_df([
        {"date": "2024-01-31", "leading": 102.5, "monitoring": 25.0},
        {"date": "2024-02-29", "leading": 103.1, "monitoring": 30.4},  # round → 30
    ])
    monkeypatch.setattr(umh, "_finmind_get", lambda *a, **kw: fake)
    out = umh.fetch_finmind_ndc_signal(
        dt.date(2024, 1, 1), dt.date(2024, 3, 1), "tok")
    assert list(out.columns) == ["date", "ndc_signal"]
    assert len(out) == 2
    assert out["ndc_signal"].iloc[1] == 30  # 30.4 → 30


def test_fetch_leading_index_shape(monkeypatch):
    """fetch_finmind_leading_index 回 [date, leading_index] float。"""
    import update_macro_history as umh
    umh._MACRO_FULL_TABLE_CACHE.clear()
    fake = _fake_business_indicator_df([
        {"date": "2024-01-31", "leading": 102.5, "monitoring": 25},
        {"date": "2024-02-29", "leading": 103.1, "monitoring": 30},
    ])
    monkeypatch.setattr(umh, "_finmind_get", lambda *a, **kw: fake)
    out = umh.fetch_finmind_leading_index(
        dt.date(2024, 1, 1), dt.date(2024, 3, 1), "tok")
    assert list(out.columns) == ["date", "leading_index"]
    assert len(out) == 2
    assert out["leading_index"].iloc[0] == 102.5


def test_fetch_ndc_signal_empty_when_column_missing(monkeypatch):
    """API 回的全表沒有 monitoring 欄時（FinMind 改 schema），fetcher 回空。"""
    import update_macro_history as umh
    umh._MACRO_FULL_TABLE_CACHE.clear()
    fake = _fake_business_indicator_df([
        {"date": "2024-01-31", "leading": 102.5},  # 缺 monitoring
    ])
    monkeypatch.setattr(umh, "_finmind_get", lambda *a, **kw: fake)
    out = umh.fetch_finmind_ndc_signal(
        dt.date(2024, 1, 1), dt.date(2024, 2, 1), "tok")
    assert out.empty


def test_ndc_and_leading_share_cache(monkeypatch):
    """同一段 (start, end) 內 NDC + 領先共抓一次 API（cache 共用驗證）。"""
    import update_macro_history as umh
    umh._MACRO_FULL_TABLE_CACHE.clear()
    call_count = {"n": 0}

    def _fake(*args, **kwargs):
        call_count["n"] += 1
        return _fake_business_indicator_df([
            {"date": "2024-01-31", "leading": 102.5, "monitoring": 25.0},
        ])

    monkeypatch.setattr(umh, "_finmind_get", _fake)
    start = dt.date(2024, 1, 1)
    end = dt.date(2024, 2, 1)
    umh.fetch_finmind_ndc_signal(start, end, "tok")
    umh.fetch_finmind_leading_index(start, end, "tok")
    assert call_count["n"] == 1, "兩個 fetcher 應共用一次 API call"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
