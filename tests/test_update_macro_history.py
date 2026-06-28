"""tests/test_update_macro_history.py — Parquet 讀寫 + 增量去重邏輯 smoke。"""
from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


def test_merge_dedupe_keeps_latest_on_collision():
    """同 date 同時出現在 old 與 new → 應保留 new 的版本（資料修正情境）。"""
    from scripts.update_macro_history import _merge_dedupe
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
    from scripts.update_macro_history import _merge_dedupe
    old = pd.DataFrame({"date": [dt.date(2026, 1, 3)], "close": [15000.0]})
    new = pd.DataFrame({"date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2)],
                        "close": [14000.0, 14500.0]})
    out = _merge_dedupe(old, new, key="date")
    assert list(out["date"]) == [dt.date(2026, 1, 1), dt.date(2026, 1, 2), dt.date(2026, 1, 3)]


def test_parquet_roundtrip_preserves_dtypes():
    """Parquet 寫入後讀回必須維持 date / numeric 型別。"""
    from scripts.update_macro_history import CACHE_DIR
    with tempfile.TemporaryDirectory() as tmpdir:
        # monkey-patch CACHE_DIR for isolation
        original_cache = CACHE_DIR
        try:
            from scripts import update_macro_history as umh
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
    from scripts.update_macro_history import _last_date
    assert _last_date(None) is None
    assert _last_date(pd.DataFrame()) is None
    assert _last_date(pd.DataFrame({"other": [1, 2]})) is None


def test_last_date_returns_max():
    """正常情境回最大 date。"""
    from scripts.update_macro_history import _last_date
    df = pd.DataFrame({"date": [dt.date(2026, 1, 5), dt.date(2026, 1, 3),
                                 dt.date(2026, 1, 4)]})
    assert _last_date(df) == dt.date(2026, 1, 5)


def test_update_one_skips_when_up_to_date(monkeypatch):
    """如果 existing 的 last_date 已 ≥ today，應跳過抓取（避免空打 API）。"""
    from scripts import update_macro_history as umh

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
    from scripts import update_macro_history as umh
    with tempfile.TemporaryDirectory() as tmpdir:
        umh.CACHE_DIR = Path(tmpdir)
        today = dt.date.today()
        meta = umh.update_one("finmind_inst", today, bootstrap=False, years=5, token="")
        assert meta["last_error"] is not None
        assert "FINMIND_TOKEN" in meta["last_error"]


# ════════════════════════════════════════════════════════════════
# v18.176 Phase D — 台灣 PMI Parquet（data.gov.tw dataset/6100）
# ════════════════════════════════════════════════════════════════
def _mk_dgtw_meta_resp(csv_url: str) -> MagicMock:
    """模擬 dgtw metadata API 回 resources 含 CSV URL。"""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "result": {"resources": [{"format": "CSV", "url": csv_url}]}
    }
    return resp


def _mk_csv_resp(csv_text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.content = csv_text.encode("utf-8")
    return resp


class TestPmiDatasets:
    def test_pmi_in_DATASETS(self):
        from scripts import update_macro_history as umh
        assert "tw_pmi" in umh.DATASETS, "PMI 必須註冊在 DATASETS"

    def test_pmi_in_FETCHERS(self):
        from scripts import update_macro_history as umh
        assert "tw_pmi" in umh.FETCHERS
        fn, needs_token = umh.FETCHERS["tw_pmi"]
        assert callable(fn)
        assert needs_token is False, "PMI 走 dgtw 不需 FinMind token"


class TestPmiCsvParser:
    def test_parses_full_csv_to_dataframe(self):
        """全 CSV → [date, pmi] DataFrame，月頻保留全列。"""
        from scripts import update_macro_history as umh
        csv = "年月,PMI\n2024-01,48.5\n2024-02,51.2\n2024-03,53.0\n"
        df = umh._parse_pmi_csv_full(csv)
        assert len(df) == 3
        assert list(df.columns) == ["date", "pmi"]
        assert df.iloc[0]["date"] == dt.date(2024, 1, 1)
        assert abs(df.iloc[1]["pmi"] - 51.2) < 0.01

    def test_sanity_filters_out_of_range(self):
        """PMI 超出 [20, 80] 視為髒值 skip。"""
        from scripts import update_macro_history as umh
        csv = "年月,PMI\n2024-01,150.0\n2024-02,50.0\n"  # 150 髒
        df = umh._parse_pmi_csv_full(csv)
        assert len(df) == 1
        assert df.iloc[0]["date"] == dt.date(2024, 2, 1)

    def test_dedupe_keeps_last_for_same_month(self):
        """同月重複 row 取最新（修正情境）。"""
        from scripts import update_macro_history as umh
        csv = "年月,PMI\n2024-01,48.5\n2024-01,49.0\n"
        df = umh._parse_pmi_csv_full(csv)
        assert len(df) == 1
        assert abs(df.iloc[0]["pmi"] - 49.0) < 0.01

    def test_empty_csv_returns_empty_df(self):
        from scripts import update_macro_history as umh
        df = umh._parse_pmi_csv_full("")
        assert df.empty
        assert list(df.columns) == ["date", "pmi"]


class TestFetchTwPmiHistory:
    def test_full_chain_success(self, monkeypatch):
        """metadata → CSV URL → 下載 → 解析 → 範圍 filter."""
        from scripts import update_macro_history as umh
        csv = "年月,PMI\n2023-12,50.1\n2024-01,52.3\n2024-02,53.5\n"
        responses = iter([
            _mk_dgtw_meta_resp("https://example.tw/pmi.csv"),
            _mk_csv_resp(csv),
        ])
        monkeypatch.setattr(umh, "_fetch_url_via_proxy",
                             lambda *a, **kw: next(responses))
        df = umh.fetch_tw_pmi_history(dt.date(2024, 1, 1), dt.date(2024, 12, 31))
        assert len(df) == 2  # 2023-12 被 filter 掉
        assert df.iloc[0]["date"] == dt.date(2024, 1, 1)

    def test_metadata_fail_returns_empty(self, monkeypatch):
        """3 個 metadata URL 全 500 → 回空 DataFrame，不 raise。"""
        from scripts import update_macro_history as umh
        bad = MagicMock()
        bad.status_code = 500
        monkeypatch.setattr(umh, "_fetch_url_via_proxy", lambda *a, **kw: bad)
        df = umh.fetch_tw_pmi_history(dt.date(2024, 1, 1), dt.date(2024, 12, 31))
        assert df.empty
        assert list(df.columns) == ["date", "pmi"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
