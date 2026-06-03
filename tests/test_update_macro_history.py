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
# 景氣對策信號 + 領先指標（國發會 NDC OpenAPI，v18.152 取代 FinMind 付費牆）
# ════════════════════════════════════════════════════════════════
class _FakeResp:
    """Mock requests.Response for proxy_helper.fetch_url 回傳。"""
    def __init__(self, json_data, status_code=200):
        self._j = json_data
        self.status_code = status_code
        import json as _json
        self.text = _json.dumps(json_data) if isinstance(json_data, (dict, list)) else str(json_data)

    def json(self):
        return self._j


def test_datasets_includes_ndc_and_leading():
    """兩個 dataset 必須註冊在 DATASETS 與 FETCHERS；v18.152 後無需 FINMIND_TOKEN。"""
    import update_macro_history as umh
    assert "finmind_ndc_signal" in umh.DATASETS
    assert "finmind_leading_index" in umh.DATASETS
    # v18.152 改 NDC OpenAPI 免 token
    assert umh.FETCHERS["finmind_ndc_signal"][1] is False
    assert umh.FETCHERS["finmind_leading_index"][1] is False


def test_ndc_url_candidates_listed():
    """確保 candidate URL constants 已定義且非空（避免被誤改空）。"""
    import update_macro_history as umh
    assert len(umh._NDC_SIGNAL_URL_CANDIDATES) >= 3
    assert len(umh._NDC_LEADING_URL_CANDIDATES) >= 3
    # 所有 URL 都應指向 index.ndc.gov.tw
    for url in umh._NDC_SIGNAL_URL_CANDIDATES + umh._NDC_LEADING_URL_CANDIDATES:
        assert "index.ndc.gov.tw" in url


def test_fetch_ndc_indicator_full_first_url_success(monkeypatch):
    """第一個 candidate URL 回 200 + 有 items → 走第一個就回 DataFrame。"""
    import update_macro_history as umh
    fake_payload = [
        {"date": "2024-01", "value": 25},
        {"date": "2024-02", "value": 30},
    ]
    call_log = []

    def _fake_fetch_url(url, **kw):
        call_log.append(url)
        return _FakeResp(fake_payload)

    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", _fake_fetch_url)
    df = umh._fetch_ndc_indicator_full(
        ("https://index.ndc.gov.tw/app/data/indicator/test",
         "https://index.ndc.gov.tw/app/data/indicator/test2"),
        "signal",
    )
    assert len(call_log) == 1, "第一個成功就不該打第二個"
    assert len(df) == 2
    assert list(df.columns) == ["date", "value"]
    assert df["value"].tolist() == [25.0, 30.0]


def test_fetch_ndc_indicator_full_fallback_to_second_url(monkeypatch):
    """第一個 404 → 嘗試第二個；第二個成功就回它的 data。"""
    import update_macro_history as umh
    call_log = []

    def _fake_fetch_url(url, **kw):
        call_log.append(url)
        if "first" in url:
            return _FakeResp({"err": "not found"}, status_code=404)
        return _FakeResp([{"date": "2024-01", "value": 25}])

    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", _fake_fetch_url)
    df = umh._fetch_ndc_indicator_full(
        ("https://index.ndc.gov.tw/app/data/indicator/first",
         "https://index.ndc.gov.tw/app/data/indicator/second"),
        "signal",
    )
    assert len(call_log) == 2
    assert len(df) == 1


def test_fetch_ndc_indicator_full_all_fail(monkeypatch):
    """全 candidate fail → 回空 DataFrame（不 raise）。"""
    import update_macro_history as umh

    def _fake_fetch_url(url, **kw):
        return _FakeResp({"err": "500"}, status_code=500)

    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", _fake_fetch_url)
    df = umh._fetch_ndc_indicator_full(
        ("https://index.ndc.gov.tw/app/data/indicator/x",),
        "signal",
    )
    assert df.empty


def test_fetch_ndc_indicator_full_handles_data_wrap(monkeypatch):
    """JSON shape={'data': [...]} 應被解 unwrap。"""
    import update_macro_history as umh
    fake = {"data": [{"date": "2024-01", "score": 28},
                       {"date": "2024-02", "score": 30}]}

    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url",
                        lambda *a, **kw: _FakeResp(fake))
    df = umh._fetch_ndc_indicator_full(
        ("https://index.ndc.gov.tw/app/data/indicator/x",), "signal")
    assert len(df) == 2
    # score 是 fallback value key
    assert df["value"].tolist() == [28.0, 30.0]


def test_fetch_ndc_indicator_full_handles_yearmonth_key(monkeypatch):
    """date key 改用 yearMonth → 也能解析。"""
    import update_macro_history as umh
    fake = [{"yearMonth": "202401", "value": 25}]

    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url",
                        lambda *a, **kw: _FakeResp(fake))
    df = umh._fetch_ndc_indicator_full(
        ("https://index.ndc.gov.tw/app/data/indicator/x",), "signal")
    assert len(df) == 1
    assert df["date"].iloc[0] == dt.date(2024, 1, 1)


def test_fetch_ndc_signal_shape(monkeypatch):
    """fetch_ndc_signal 回 [date, ndc_signal] + Int64 + round + 在範圍內。"""
    import update_macro_history as umh
    fake = [
        {"date": "2024-01", "value": 25.0},
        {"date": "2024-02", "value": 30.4},  # round → 30
        {"date": "2023-12", "value": 21.0},  # 早於 start，應被 filter
    ]
    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", lambda *a, **kw: _FakeResp(fake))
    out = umh.fetch_ndc_signal(dt.date(2024, 1, 1), dt.date(2024, 3, 1))
    assert list(out.columns) == ["date", "ndc_signal"]
    assert len(out) == 2  # 12 月被剃掉
    assert out["ndc_signal"].iloc[1] == 30  # 30.4 → 30
    assert str(out["ndc_signal"].dtype) == "Int64"


def test_fetch_ndc_leading_index_shape(monkeypatch):
    """fetch_ndc_leading_index 回 [date, leading_index] float。"""
    import update_macro_history as umh
    fake = [
        {"date": "2024-01", "value": 102.5},
        {"date": "2024-02", "value": 103.1},
    ]
    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", lambda *a, **kw: _FakeResp(fake))
    out = umh.fetch_ndc_leading_index(dt.date(2024, 1, 1), dt.date(2024, 3, 1))
    assert list(out.columns) == ["date", "leading_index"]
    assert len(out) == 2
    assert out["leading_index"].iloc[0] == 102.5


def test_fetch_ndc_signal_empty_when_all_urls_fail(monkeypatch):
    """全 URL fail → fetcher 回空 DataFrame，不 raise。"""
    import update_macro_history as umh
    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url",
                        lambda *a, **kw: _FakeResp({}, status_code=404))
    out = umh.fetch_ndc_signal(dt.date(2024, 1, 1), dt.date(2024, 2, 1))
    assert out.empty


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
