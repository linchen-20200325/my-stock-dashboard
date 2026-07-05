"""全台股基本面快照 L1 loader 測試(讀 parquet + latest.json;fail-loud)。"""
import json

import pandas as pd
import pytest

from src.data.stock.fundamentals_snapshot_loader import (
    FUNDAMENTALS_CACHE_DIR,
    _load_impl,
    _read_market_quarter,
)


def _write_snapshot(cache_dir, market, roc_year, season, ids):
    pd.DataFrame({"stock_id": ids, "eps": [1.0] * len(ids)}).to_parquet(
        cache_dir / f"{market}_{roc_year}Q{season}.parquet", index=False
    )


def _write_meta(cache_dir, roc_year, season, prev_roc_year):
    (cache_dir / "latest.json").write_text(json.dumps({
        "roc_year": roc_year, "season": season, "prev_roc_year": prev_roc_year,
    }), encoding="utf-8")


def test_read_market_quarter_concats_both_markets(tmp_path):
    _write_snapshot(tmp_path, "sii", 115, 1, ["2330", "2454"])
    _write_snapshot(tmp_path, "otc", 115, 1, ["6488"])
    df = _read_market_quarter(tmp_path, 115, 1)
    assert set(df["stock_id"]) == {"2330", "2454", "6488"}


def test_read_market_quarter_missing_returns_empty(tmp_path):
    assert _read_market_quarter(tmp_path, 199, 1).empty


def test_load_impl_current_and_prev(tmp_path):
    _write_snapshot(tmp_path, "sii", 115, 1, ["2330"])
    _write_snapshot(tmp_path, "otc", 115, 1, ["6488"])
    _write_snapshot(tmp_path, "sii", 114, 1, ["2330"])
    _write_meta(tmp_path, 115, 1, 114)
    cur, prev, meta = _load_impl(tmp_path)
    assert set(cur["stock_id"]) == {"2330", "6488"}
    assert list(prev["stock_id"]) == ["2330"]
    assert meta["roc_year"] == 115 and meta["prev_roc_year"] == 114


def test_load_impl_no_prev(tmp_path):
    _write_snapshot(tmp_path, "sii", 115, 1, ["2330"])
    _write_meta(tmp_path, 115, 1, None)
    cur, prev, meta = _load_impl(tmp_path)
    assert not cur.empty
    assert prev.empty                          # 無去年同季 → 空(不猜)


def test_load_impl_missing_latest_json_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        _load_impl(tmp_path)


def test_load_impl_current_parquet_missing_raises(tmp_path):
    # latest.json 指向某季但 parquet 全缺 → fail-loud
    _write_meta(tmp_path, 115, 2, 114)
    with pytest.raises(FileNotFoundError):
        _load_impl(tmp_path)


def test_real_snapshot_load_smoke():
    if not (FUNDAMENTALS_CACHE_DIR / "latest.json").exists():
        pytest.skip("無快照資料")
    cur, prev, meta = _load_impl(FUNDAMENTALS_CACHE_DIR)
    assert len(cur) > 1500
    assert "revenue" in cur.columns and "total_liab" in cur.columns
    assert meta["roc_year"] >= 115
    # 有去年同季(114Q1 已補)→ prev 非空,供 YoY
    if meta.get("prev_roc_year") is not None:
        assert not prev.empty
