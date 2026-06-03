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
# 景氣對策信號 + 領先指標（data.gov.tw NDC dataset；v18.154 NDC SPA OpenAPI 確認 dead）
# ════════════════════════════════════════════════════════════════
class _FakeResp:
    """Mock requests.Response for proxy_helper.fetch_url 回傳。"""
    def __init__(self, json_data=None, status_code=200, content_bytes=None,
                 content_type="application/json"):
        self._j = json_data
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        import json as _json
        if content_bytes is not None:
            self.content = content_bytes
            self.text = content_bytes.decode("utf-8", errors="ignore")
        else:
            self.text = _json.dumps(json_data) if isinstance(json_data, (dict, list)) else (json_data or "")
            self.content = self.text.encode("utf-8")

    def json(self):
        if self._j is None:
            import json as _json
            return _json.loads(self.text)
        return self._j


def test_datasets_includes_ndc_and_leading():
    """兩個 dataset 必須註冊在 DATASETS 與 FETCHERS；v18.154 data.gov.tw 免 token。"""
    import update_macro_history as umh
    assert "finmind_ndc_signal" in umh.DATASETS
    assert "finmind_leading_index" in umh.DATASETS
    assert umh.FETCHERS["finmind_ndc_signal"][1] is False
    assert umh.FETCHERS["finmind_leading_index"][1] is False


def test_dgtw_constants_defined():
    """關鍵 constants 必須非空（避免被誤改）。"""
    import update_macro_history as umh
    assert len(umh._DGTW_SIGNAL_KEYWORDS) >= 1
    assert len(umh._DGTW_LEADING_KEYWORDS) >= 1
    assert len(umh._DGTW_CANDIDATE_IDS) >= 5
    assert len(umh._DGTW_SIGNAL_VALUE_KEYWORDS) >= 2
    assert len(umh._DGTW_LEADING_VALUE_KEYWORDS) >= 2


def test_fetch_dgtw_search_parses_top_results(monkeypatch):
    """search API 回 {result:{results:[...]}} → 應抽出 dataset IDs。"""
    import update_macro_history as umh
    fake = {"result": {"results": [
        {"identifier": "6101", "title": "景氣對策信號A"},
        {"identifier": "6102", "title": "景氣對策信號B"},
    ]}}
    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", lambda *a, **kw: _FakeResp(fake))
    ids = umh._fetch_dgtw_search_dataset_ids("景氣對策信號", "signal")
    assert ids == ["6101", "6102"]


def test_fetch_dgtw_search_handles_empty_results(monkeypatch):
    """search API 回 0 results → 空 list 不 raise。"""
    import update_macro_history as umh
    fake = {"result": {"results": []}}
    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", lambda *a, **kw: _FakeResp(fake))
    ids = umh._fetch_dgtw_search_dataset_ids("xxxxx", "signal")
    assert ids == []


def test_fetch_dgtw_search_handles_html_fallback(monkeypatch):
    """search API 回 HTML（非 JSON）→ 全 3 個 URL 都試完仍回空 list。"""
    import update_macro_history as umh

    def _fake(*a, **kw):
        return _FakeResp(content_bytes=b"<html>not json</html>",
                         content_type="text/html")
    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", _fake)
    ids = umh._fetch_dgtw_search_dataset_ids("景氣對策信號", "signal")
    assert ids == []


def test_fetch_dgtw_dataset_csv_full_parses_csv(monkeypatch):
    """metadata 回 CSV resource → 抓 CSV → 解 [date, value]。"""
    import update_macro_history as umh
    meta = {"result": {"resources": [
        {"format": "CSV", "url": "https://example.com/data.csv"},
    ]}}
    csv_bytes = (
        "年月,景氣對策信號分數,其他欄\n"
        "2024-01,25,a\n"
        "2024-02,30,b\n"
        "2024-03,28,c\n"
    ).encode("utf-8-sig")

    call_count = {"n": 0}

    def _fake(url, **kw):
        call_count["n"] += 1
        if "rest/dataset/" in url and not url.endswith(".csv"):
            return _FakeResp(meta)
        return _FakeResp(content_bytes=csv_bytes, content_type="text/csv")

    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", _fake)
    df = umh._fetch_dgtw_dataset_csv_full(
        "6101", umh._DGTW_SIGNAL_VALUE_KEYWORDS, "signal")
    assert len(df) == 3
    assert list(df.columns) == ["date", "value"]
    assert df["value"].tolist() == [25.0, 30.0, 28.0]


def test_fetch_dgtw_dataset_csv_no_csv_resource(monkeypatch):
    """metadata 無 CSV resource → 回空（不 raise）。"""
    import update_macro_history as umh
    meta = {"result": {"resources": [
        {"format": "PDF", "url": "https://example.com/doc.pdf"},
    ]}}
    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url",
                        lambda *a, **kw: _FakeResp(meta))
    df = umh._fetch_dgtw_dataset_csv_full(
        "6101", umh._DGTW_SIGNAL_VALUE_KEYWORDS, "signal")
    assert df.empty


def test_fetch_dgtw_dataset_csv_no_value_col(monkeypatch):
    """CSV 沒有 value keyword 命中的欄位 → 回空 + 印警告。"""
    import update_macro_history as umh
    meta = {"result": {"resources": [
        {"format": "CSV", "url": "https://example.com/data.csv"},
    ]}}
    csv_bytes = b"yearmonth,unrelated\n2024-01,foo\n"

    def _fake(url, **kw):
        if "rest/dataset/" in url and not url.endswith(".csv"):
            return _FakeResp(meta)
        return _FakeResp(content_bytes=csv_bytes, content_type="text/csv")

    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", _fake)
    df = umh._fetch_dgtw_dataset_csv_full(
        "6101", umh._DGTW_SIGNAL_VALUE_KEYWORDS, "signal")
    assert df.empty


def test_fetch_dgtw_indicator_search_path_succeeds(monkeypatch):
    """search 找到 ID → 直接拿 CSV → 不走 probe。"""
    import update_macro_history as umh
    search_payload = {"result": {"results": [
        {"identifier": "6101", "title": "景氣對策信號歷史"},
    ]}}
    meta = {"result": {"resources": [
        {"format": "CSV", "url": "https://example.com/data.csv"},
    ]}}
    csv_bytes = b"\xef\xbb\xbf\xe5\xb9\xb4\xe6\x9c\x88,\xe6\x99\xaf\xe6\xb0\xa3\xe5\xb0\x8d\xe7\xad\x96\xe4\xbf\xa1\xe8\x99\x9f\xe5\x88\x86\xe6\x95\xb8\n2024-01,25\n"
    # 上行是 BOM + "年月,景氣對策信號分數\n2024-01,25\n"

    probe_called = {"n": 0}

    def _fake(url, **kw):
        if "search?q=" in url:
            return _FakeResp(search_payload)
        # 命中 6101 metadata
        if "/dataset/6101" in url and not url.endswith(".csv"):
            return _FakeResp(meta)
        if url.endswith(".csv"):
            return _FakeResp(content_bytes=csv_bytes, content_type="text/csv")
        # probe 其他 ID → 應該不該被呼叫
        probe_called["n"] += 1
        return _FakeResp({"err": "x"}, status_code=404)

    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", _fake)
    df = umh._fetch_dgtw_indicator(
        ("景氣對策信號",), umh._DGTW_SIGNAL_VALUE_KEYWORDS,
        ("6099", "6102"), "signal")
    assert len(df) == 1
    assert probe_called["n"] == 0, "search 成功不該再走 probe"


def test_fetch_dgtw_indicator_falls_through_to_probe(monkeypatch):
    """search 全失敗 → 改 probe candidate ID 範圍。"""
    import update_macro_history as umh
    meta = {"result": {"resources": [
        {"format": "CSV", "url": "https://example.com/data.csv"},
    ]}}
    csv_bytes = b"\xef\xbb\xbf\xe5\xb9\xb4\xe6\x9c\x88,\xe6\x99\xaf\xe6\xb0\xa3\xe5\xb0\x8d\xe7\xad\x96\xe4\xbf\xa1\xe8\x99\x9f\xe5\x88\x86\xe6\x95\xb8\n2024-02,28\n"

    def _fake(url, **kw):
        if "search?q=" in url:
            return _FakeResp({"result": {"results": []}})
        # probe 第二個 ID 才中
        if "/dataset/6102" in url and not url.endswith(".csv"):
            return _FakeResp(meta)
        if url.endswith(".csv"):
            return _FakeResp(content_bytes=csv_bytes, content_type="text/csv")
        return _FakeResp({"err": "x"}, status_code=404)

    import proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", _fake)
    df = umh._fetch_dgtw_indicator(
        ("景氣對策信號",), umh._DGTW_SIGNAL_VALUE_KEYWORDS,
        ("6099", "6102", "6105"), "signal")
    assert len(df) == 1


def test_fetch_ndc_signal_uses_dgtw(monkeypatch):
    """fetch_ndc_signal → 走 dgtw → 回 [date, ndc_signal] Int64 + filter 範圍。"""
    import update_macro_history as umh
    fake_df = pd.DataFrame({
        "date": [dt.date(2023, 12, 1), dt.date(2024, 1, 1), dt.date(2024, 2, 1)],
        "value": [21.0, 25.0, 30.4],
    })
    monkeypatch.setattr(umh, "_fetch_dgtw_indicator",
                        lambda *a, **kw: fake_df)
    out = umh.fetch_ndc_signal(dt.date(2024, 1, 1), dt.date(2024, 3, 1))
    assert list(out.columns) == ["date", "ndc_signal"]
    assert len(out) == 2  # 12 月被剃掉
    assert out["ndc_signal"].iloc[1] == 30  # 30.4 → 30
    assert str(out["ndc_signal"].dtype) == "Int64"


def test_fetch_ndc_leading_index_uses_dgtw(monkeypatch):
    """fetch_ndc_leading_index → 走 dgtw → 回 [date, leading_index] float。"""
    import update_macro_history as umh
    fake_df = pd.DataFrame({
        "date": [dt.date(2024, 1, 1), dt.date(2024, 2, 1)],
        "value": [102.5, 103.1],
    })
    monkeypatch.setattr(umh, "_fetch_dgtw_indicator",
                        lambda *a, **kw: fake_df)
    out = umh.fetch_ndc_leading_index(dt.date(2024, 1, 1), dt.date(2024, 3, 1))
    assert list(out.columns) == ["date", "leading_index"]
    assert len(out) == 2
    assert out["leading_index"].iloc[0] == 102.5


def test_fetch_ndc_signal_empty_when_dgtw_fails(monkeypatch):
    """dgtw 全失敗 → fetch_ndc_signal 回空（不 raise）。"""
    import update_macro_history as umh
    monkeypatch.setattr(umh, "_fetch_dgtw_indicator",
                        lambda *a, **kw: pd.DataFrame())
    out = umh.fetch_ndc_signal(dt.date(2024, 1, 1), dt.date(2024, 2, 1))
    assert out.empty


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
