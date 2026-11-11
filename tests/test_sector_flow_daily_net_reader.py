"""tests/test_sector_flow_daily_net_reader.py — L1 新增唯讀函式(Issue #1140 板塊事實).

守的是 `src/data/sector_flow/reader.py::read_sector_daily_net_latest` / `read_sector_flow_cron_coverage`:
純讀既有 daily_net.parquet / metadata.json;缺檔、空檔、缺欄、壞檔以不同 status 區分(§1:不折成同一種「沒資料」)。
零網路、tmp_path + monkeypatch 路徑。
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest

from src.data.sector_flow import reader as R


def _frame(dates, sectors=("甲", "乙")):
    rows = []
    for d in dates:
        for s in sectors:
            rows.append({"date": pd.Timestamp(d), "sector": s, "net_amt_yi": 1.0, "foreign_yi": 0.5,
                         "trust_yi": 0.25, "dealer_yi": 0.25, "n_stocks": 3})
    return pd.DataFrame(rows)


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "DAILY_NET_PATH", tmp_path / "daily_net.parquet")
    monkeypatch.setattr(R, "META_PATH", tmp_path / "metadata.json")
    return tmp_path


def test_ok_returns_only_latest_day_raw_rows(paths):
    _frame(["2026-11-06", "2026-11-09"]).to_parquet(paths / "daily_net.parquet")
    r = R.read_sector_daily_net_latest()
    assert r["status"] == "ok" and r["data_date"] == date(2026, 11, 9) and r["n_rows_total"] == 4
    assert len(r["rows"]) == 2 and set(r["rows"]["sector"]) == {"甲", "乙"}
    assert (pd.to_datetime(r["rows"]["date"]) == pd.Timestamp("2026-11-09")).all()


def test_does_not_normalize_or_alias_labels(paths):
    _frame(["2026-11-09"], sectors=("上櫃ETF", "ETF ")).to_parquet(paths / "daily_net.parquet")
    r = R.read_sector_daily_net_latest()
    assert set(r["rows"]["sector"]) == {"上櫃ETF", "ETF "}            # 原始標籤原樣,不合併不 strip


def test_does_not_dedupe_or_fill(paths):
    df = pd.concat([_frame(["2026-11-09"]), _frame(["2026-11-09"]).iloc[:1]])
    df.loc[df.index[0], "net_amt_yi"] = float("nan")
    df.to_parquet(paths / "daily_net.parquet")
    r = R.read_sector_daily_net_latest()
    assert len(r["rows"]) == 3 and r["rows"]["net_amt_yi"].isna().sum() >= 1


def test_missing_file(paths):
    assert R.read_sector_daily_net_latest()["status"] == "missing"


def test_empty_file(paths):
    _frame(["2026-11-09"]).iloc[0:0].to_parquet(paths / "daily_net.parquet")
    assert R.read_sector_daily_net_latest()["status"] == "empty"


def test_missing_required_columns(paths):
    _frame(["2026-11-09"]).drop(columns=["trust_yi"]).to_parquet(paths / "daily_net.parquet")
    r = R.read_sector_daily_net_latest()
    assert r["status"] == "missing_columns" and r["missing"] == ["trust_yi"]


def test_flag_and_n_stocks_columns_are_optional(paths):
    _frame(["2026-11-09"]).drop(columns=["n_stocks"]).to_parquet(paths / "daily_net.parquet")
    assert R.read_sector_daily_net_latest()["status"] == "ok"


def test_corrupt_file_is_not_reported_as_missing(paths):
    (paths / "daily_net.parquet").write_bytes(b"not parquet at all")
    r = R.read_sector_daily_net_latest()
    assert r["status"] == "corrupt" and r["status"] != "missing"


def test_unparseable_date_rows_are_corrupt_not_silently_dropped(paths):
    df = _frame(["2026-11-09"])
    df["date"] = ["2026-11-09", "garbage"]
    df.to_parquet(paths / "daily_net.parquet")
    assert R.read_sector_daily_net_latest()["status"] == "corrupt"


def test_cron_coverage(paths):
    assert R.read_sector_flow_cron_coverage() is None                       # 缺檔
    (paths / "metadata.json").write_text("{bad", encoding="utf-8")
    assert R.read_sector_flow_cron_coverage() is None                       # 壞檔
    (paths / "metadata.json").write_text(json.dumps({"last_updated": "x"}), encoding="utf-8")
    assert R.read_sector_flow_cron_coverage() is None                       # 無 coverage
    (paths / "metadata.json").write_text(json.dumps({"coverage": {"n_sectors": 3}}), encoding="utf-8")
    assert R.read_sector_flow_cron_coverage() == {"n_sectors": 3}


def test_read_does_not_modify_files(paths):
    _frame(["2026-11-09"]).to_parquet(paths / "daily_net.parquet")
    before = (paths / "daily_net.parquet").stat().st_mtime_ns
    R.read_sector_daily_net_latest()
    assert (paths / "daily_net.parquet").stat().st_mtime_ns == before
    assert sorted(p.name for p in paths.iterdir()) == ["daily_net.parquet"]
