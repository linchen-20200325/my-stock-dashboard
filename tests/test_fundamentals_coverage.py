"""tests/test_fundamentals_coverage.py — 快照涵蓋率診斷（v19.71）。

驗:① script _count_quarter / _write_latest_json 寫 coverage；② L3 describe_snapshot_coverage
完整 / 偏低 / 舊版無 coverage 三態。不觸網。
"""
from __future__ import annotations

import json

import pandas as pd

from scripts.update_fundamentals_snapshot import _count_quarter, _write_latest_json
from src.services.fundamental_screener_service import describe_snapshot_coverage


def _mk(cache_dir, market, roc, season, n):
    df = pd.DataFrame({"stock_id": [str(1000 + i) for i in range(n)], "eps": [1.0] * n})
    df.to_parquet(cache_dir / f"{market}_{roc}Q{season}.parquet", index=False)


# ── script 端 ─────────────────────────────────────────────────
def test_count_quarter(tmp_path):
    _mk(tmp_path, "sii", 115, 1, 10)
    _mk(tmp_path, "otc", 115, 1, 7)
    per, total = _count_quarter(tmp_path, 115, 1)
    assert per == {"sii": 10, "otc": 7}
    assert total == 17


def test_count_quarter_missing_market(tmp_path):
    _mk(tmp_path, "sii", 115, 1, 5)   # 只有上市
    per, total = _count_quarter(tmp_path, 115, 1)
    assert per == {"sii": 5} and total == 5


def test_write_latest_json_records_coverage(tmp_path):
    _mk(tmp_path, "sii", 115, 1, 10)
    _mk(tmp_path, "otc", 115, 1, 7)
    _mk(tmp_path, "sii", 114, 1, 8)   # 去年同季 → prev_total
    _mk(tmp_path, "otc", 114, 1, 6)
    res = _write_latest_json(tmp_path)
    assert res == (115, 1)
    meta = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert meta["prev_roc_year"] == 114
    assert meta["coverage"] == {"sii": 10, "otc": 7, "total": 17, "prev_total": 14}


def test_write_latest_json_no_prev(tmp_path):
    _mk(tmp_path, "sii", 115, 1, 10)
    _write_latest_json(tmp_path)
    meta = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert meta["coverage"]["total"] == 10
    assert meta["coverage"]["prev_total"] is None   # 無去年同季 → None


# ── L3 診斷 helper ────────────────────────────────────────────
def test_describe_complete():
    meta = {"roc_year": 115, "season": 1, "updated_at": "2026-07-05T02:33:21+00:00",
            "coverage": {"sii": 1078, "otc": 891, "total": 1969, "prev_total": 1934}}
    r = describe_snapshot_coverage(meta)
    assert r["possibly_incomplete"] is False
    assert "1,969" in r["text"] and "上市 1,078" in r["text"]
    assert "2026-07-05" in r["text"] and "兩趟" in r["text"]


def test_describe_incomplete_flags_low_coverage():
    # 900 < 1934 × 0.90 = 1740.6 → 可能尚缺慢公布
    meta = {"roc_year": 115, "season": 1, "updated_at": "2026-05-22T06:00:00+00:00",
            "coverage": {"sii": 500, "otc": 400, "total": 900, "prev_total": 1934}}
    r = describe_snapshot_coverage(meta)
    assert r["possibly_incomplete"] is True
    assert "偏低" in r["text"] and "慢公布" in r["text"]


def test_describe_boundary_not_flagged_at_ratio():
    # 剛好 = prev × 0.90 → 不算偏低（用 < 判定）
    meta = {"roc_year": 115, "season": 1, "updated_at": "2026-07-05",
            "coverage": {"sii": 900, "otc": 900, "total": 1800, "prev_total": 2000}}
    r = describe_snapshot_coverage(meta)  # 1800 == 2000×0.9 → not <
    assert r["possibly_incomplete"] is False


def test_describe_missing_coverage_old_snapshot():
    r = describe_snapshot_coverage({"roc_year": 114, "season": 4})  # 舊版無 coverage
    assert r["possibly_incomplete"] is False   # 不誤報
    assert "未記錄" in r["text"]


def test_describe_none_meta():
    r = describe_snapshot_coverage(None)
    assert r["total"] is None and r["possibly_incomplete"] is False


def test_get_snapshot_coverage_note_failsafe(monkeypatch):
    import src.services.fundamental_screener_service as svc

    def _boom(*a, **k):
        raise FileNotFoundError("no snapshot")
    monkeypatch.setattr(svc, "get_fundamental_prescreen", _boom)
    assert svc.get_snapshot_coverage_note() == ""   # 快照缺 → 空字串,不炸
