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
# 新增：景氣對策信號 + 領先指標（FinMind TaiwanMacroEconomics）
# ════════════════════════════════════════════════════════════════
def test_datasets_includes_ndc_and_leading():
    """新增的兩個 dataset 必須註冊在 DATASETS 與 FETCHERS。"""
    import update_macro_history as umh
    assert "finmind_ndc_signal" in umh.DATASETS
    assert "finmind_leading_index" in umh.DATASETS
    # 都需要 FINMIND_TOKEN
    assert umh.FETCHERS["finmind_ndc_signal"][1] is True
    assert umh.FETCHERS["finmind_leading_index"][1] is True


def test_filter_macro_indicator_exact_match():
    """exact match：indicator 名稱完全相等時應抽出對應列。"""
    from update_macro_history import _filter_macro_indicator, NDC_SIGNAL_KEYS
    df = pd.DataFrame({
        "date": ["2024-01-31", "2024-02-29", "2024-01-31"],
        "name": ["景氣對策信號(分)", "景氣對策信號(分)", "CPI"],
        "value": [25, 30, 102.5],
    })
    out = _filter_macro_indicator(df, NDC_SIGNAL_KEYS)
    assert len(out) == 2
    assert list(out.columns) == ["date", "value"]
    assert sorted(out["value"].tolist()) == [25.0, 30.0]


def test_filter_macro_indicator_contains_fallback():
    """exact 找不到時用 contains 兜底（FinMind 名稱版本變體）。"""
    from update_macro_history import _filter_macro_indicator
    df = pd.DataFrame({
        "date": ["2024-01-31"],
        "name": ["景氣對策信號 v2"],   # 帶後綴的變體
        "value": [28],
    })
    out = _filter_macro_indicator(df, ("景氣對策信號",))
    assert len(out) == 1
    assert out["value"].iloc[0] == 28.0


def test_filter_macro_indicator_no_match():
    """完全找不到時回空 DataFrame，不 raise。"""
    from update_macro_history import _filter_macro_indicator
    df = pd.DataFrame({
        "date": ["2024-01-31"],
        "name": ["CPI"],
        "value": [102.5],
    })
    out = _filter_macro_indicator(df, ("景氣對策信號",))
    assert out.empty


def test_filter_macro_indicator_empty_input():
    """空 df / None 應回空 DataFrame。"""
    from update_macro_history import _filter_macro_indicator
    assert _filter_macro_indicator(pd.DataFrame(), ("X",)).empty
    assert _filter_macro_indicator(None, ("X",)).empty


def test_filter_macro_indicator_missing_columns():
    """缺 indicator / value / date 欄位 → 回空（不 raise）。"""
    from update_macro_history import _filter_macro_indicator
    df = pd.DataFrame({"some_col": [1, 2]})
    assert _filter_macro_indicator(df, ("X",)).empty


def test_filter_macro_indicator_alt_column_names():
    """indicator / name / metric + value / data 任一組合都要 work。"""
    from update_macro_history import _filter_macro_indicator
    df = pd.DataFrame({
        "date": ["2024-01-31"],
        "metric": ["景氣對策信號(分)"],
        "data": [25],
    })
    out = _filter_macro_indicator(df, ("景氣對策信號(分)",))
    assert len(out) == 1
    assert out["value"].iloc[0] == 25.0


def test_macro_table_cache_skips_second_call(monkeypatch):
    """_finmind_macro_table 同 key 第二次 call 應走 cache，不重打 API。"""
    import update_macro_history as umh
    # 清快取
    umh._MACRO_FULL_TABLE_CACHE.clear()
    call_count = {"n": 0}

    def _fake_finmind_get(dataset, data_id, start, end, token):
        call_count["n"] += 1
        return pd.DataFrame({
            "date": ["2024-01-31"],
            "name": ["景氣對策信號(分)"],
            "value": [25],
        })

    monkeypatch.setattr(umh, "_finmind_get", _fake_finmind_get)
    start = dt.date(2024, 1, 1)
    end = dt.date(2024, 2, 1)
    umh._finmind_macro_table(start, end, "tok")
    umh._finmind_macro_table(start, end, "tok")  # 應走 cache
    assert call_count["n"] == 1


def test_fetch_ndc_signal_shape(monkeypatch):
    """fetch_finmind_ndc_signal 回 [date, ndc_signal] 兩欄、ndc_signal 為整數型別。"""
    import update_macro_history as umh
    umh._MACRO_FULL_TABLE_CACHE.clear()
    fake = pd.DataFrame({
        "date": ["2024-01-31", "2024-02-29"],
        "name": ["景氣對策信號(分)", "景氣對策信號(分)"],
        "value": [25.0, 30.4],   # 含小數應被 round
    })
    monkeypatch.setattr(umh, "_finmind_get",
                        lambda *a, **kw: fake)
    out = umh.fetch_finmind_ndc_signal(
        dt.date(2024, 1, 1), dt.date(2024, 3, 1), "tok")
    assert list(out.columns) == ["date", "ndc_signal"]
    assert len(out) == 2
    assert out["ndc_signal"].iloc[1] == 30   # 30.4 → 30


def test_fetch_leading_index_shape(monkeypatch):
    """fetch_finmind_leading_index 回 [date, leading_index]，不含 smooth 欄。"""
    import update_macro_history as umh
    umh._MACRO_FULL_TABLE_CACHE.clear()
    fake = pd.DataFrame({
        "date": ["2024-01-31", "2024-02-29"],
        "name": ["領先指標綜合指數", "領先指標綜合指數"],
        "value": [102.5, 103.1],
    })
    monkeypatch.setattr(umh, "_finmind_get",
                        lambda *a, **kw: fake)
    out = umh.fetch_finmind_leading_index(
        dt.date(2024, 1, 1), dt.date(2024, 3, 1), "tok")
    assert list(out.columns) == ["date", "leading_index"]
    assert len(out) == 2
    assert out["leading_index"].iloc[0] == 102.5


def test_fetch_ndc_signal_empty_when_no_match(monkeypatch):
    """API 回的全表沒有 NDC 信號名稱時，fetcher 應回空 DataFrame、不 raise。"""
    import update_macro_history as umh
    umh._MACRO_FULL_TABLE_CACHE.clear()
    fake = pd.DataFrame({
        "date": ["2024-01-31"],
        "name": ["CPI"],
        "value": [102.5],
    })
    monkeypatch.setattr(umh, "_finmind_get",
                        lambda *a, **kw: fake)
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
        return pd.DataFrame({
            "date": ["2024-01-31", "2024-01-31"],
            "name": ["景氣對策信號(分)", "領先指標綜合指數"],
            "value": [25.0, 102.5],
        })

    monkeypatch.setattr(umh, "_finmind_get", _fake)
    start = dt.date(2024, 1, 1)
    end = dt.date(2024, 2, 1)
    umh.fetch_finmind_ndc_signal(start, end, "tok")
    umh.fetch_finmind_leading_index(start, end, "tok")
    assert call_count["n"] == 1, "兩個 fetcher 應共用一次 API call"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
