"""latest_published_quarter 邊界測試(純函式,依台股財報公告截止日推算季別)+
latest.json 磁碟實況重算測試(補舊季不把指標往回移)。"""
import datetime
import json

import pandas as pd

from scripts.update_fundamentals_snapshot import (
    _scan_cached_quarters,
    _write_latest_json,
    latest_published_quarter,
)


def _q(y, m, d):
    return latest_published_quarter(datetime.date(y, m, d))


def _touch_parquet(cache_dir, market, roc_year, season):
    """寫一個最小 parquet 模擬某市場某季快照存在。"""
    pd.DataFrame({"stock_id": ["2330"]}).to_parquet(
        cache_dir / f"{market}_{roc_year}Q{season}.parquet", index=False
    )


def test_quarter_boundaries_2026():
    # Q1 公布 5/15 前 → 仍是去年年報(民國114 Q4)
    assert _q(2026, 5, 14) == (114, 4)
    # 5/15 起 → 民國115 Q1
    assert _q(2026, 5, 15) == (115, 1)
    # 8/14 起 → Q2
    assert _q(2026, 8, 14) == (115, 2)
    # 11/14 起 → Q3
    assert _q(2026, 11, 14) == (115, 3)


def test_year_annual_and_pre_annual():
    # 3/31 起 → 去年年報(民國114 Q4)
    assert _q(2026, 3, 31) == (114, 4)
    # 年初(年報未出)→ 去年 Q3(民國114 Q3)
    assert _q(2026, 1, 10) == (114, 3)
    assert _q(2026, 3, 30) == (114, 3)


def test_roc_year_conversion():
    # 西元 2026 → 民國 115
    ry, _ = _q(2026, 6, 1)
    assert ry == 115


# ── latest.json 磁碟實況重算 ────────────────────────────────────────────
def test_scan_cached_quarters(tmp_path):
    _touch_parquet(tmp_path, "sii", 115, 1)
    _touch_parquet(tmp_path, "otc", 115, 1)
    _touch_parquet(tmp_path, "sii", 114, 1)
    (tmp_path / "latest.json").write_text("{}")     # 非 parquet 應被忽略
    assert _scan_cached_quarters(tmp_path) == {(115, 1), (114, 1)}


def test_latest_json_points_to_newest_with_prev(tmp_path):
    # 有 115Q1(上市+上櫃)與 114Q1 → latest 指 115Q1、prev 標 114
    _touch_parquet(tmp_path, "sii", 115, 1)
    _touch_parquet(tmp_path, "otc", 115, 1)
    _touch_parquet(tmp_path, "sii", 114, 1)
    assert _write_latest_json(tmp_path) == (115, 1)
    meta = json.loads((tmp_path / "latest.json").read_text())
    assert (meta["roc_year"], meta["season"]) == (115, 1)
    assert meta["prev_roc_year"] == 114          # 去年同季存在 → YoY 可用


def test_latest_json_prev_null_when_missing(tmp_path):
    # 只有 115Q1、無 114Q1 → prev_roc_year 應為 None(YoY 不可用)
    _touch_parquet(tmp_path, "sii", 115, 1)
    assert _write_latest_json(tmp_path) == (115, 1)
    meta = json.loads((tmp_path / "latest.json").read_text())
    assert meta["prev_roc_year"] is None


def test_backfill_old_quarter_does_not_move_pointer_back(tmp_path):
    # 已有 115Q1,補抓 114Q1 後重算 → latest 仍指 115Q1(不往回移),prev 補上 114
    _touch_parquet(tmp_path, "sii", 115, 1)
    assert _write_latest_json(tmp_path) == (115, 1)
    _touch_parquet(tmp_path, "sii", 114, 1)      # 補舊季
    assert _write_latest_json(tmp_path) == (115, 1)
    meta = json.loads((tmp_path / "latest.json").read_text())
    assert (meta["roc_year"], meta["season"]) == (115, 1)
    assert meta["prev_roc_year"] == 114


def test_empty_dir_writes_nothing(tmp_path):
    assert _write_latest_json(tmp_path) is None
    assert not (tmp_path / "latest.json").exists()


# ── _parse_seasons ─────────────────────────────────────────────────────
import pytest  # noqa: E402

from scripts.update_fundamentals_snapshot import _parse_seasons  # noqa: E402


def test_parse_seasons_single_and_multi():
    assert _parse_seasons("1") == [1]
    assert _parse_seasons("2,3,4") == [2, 3, 4]
    assert _parse_seasons("1,2,3,4") == [1, 2, 3, 4]
    assert _parse_seasons(" 2 , 3 ") == [2, 3]        # 容空白
    assert _parse_seasons("3,3,2") == [3, 2]          # 去重保序


def test_parse_seasons_empty():
    assert _parse_seasons(None) == []
    assert _parse_seasons("") == []
    assert _parse_seasons("  ") == []


def test_parse_seasons_invalid_raises():
    with pytest.raises(ValueError):
        _parse_seasons("5")            # 超出 1-4
    with pytest.raises(ValueError):
        _parse_seasons("abc")          # 非數字


# ── main() 抓幾季的決策(手動=單季 / 自動=本季+缺才補去年同季)──────────
import scripts.update_fundamentals_snapshot as _ufs  # noqa: E402


def _patch_main(monkeypatch, tmp_path):
    """把 CACHE_DIR 導到 tmp、_fetch_market 換成記錄呼叫的假抓取。"""
    calls: list[tuple[int, int, str]] = []

    def _fake_fetch(typek, roc_year, season):
        calls.append((roc_year, season, typek))
        return pd.DataFrame({"stock_id": ["2330"], "revenue": [100]})

    monkeypatch.setattr(_ufs, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(_ufs, "_fetch_market", _fake_fetch)
    return calls


def test_manual_mode_fetches_single_quarter(monkeypatch, tmp_path):
    calls = _patch_main(monkeypatch, tmp_path)
    rc = _ufs.main(["--roc-year", "114", "--season", "1", "--markets", "sii"])
    assert rc == 0
    # 只抓 114Q1 一季(不連 113Q1 去年同季一起抓)
    assert calls == [(114, 1, "sii")]


def test_manual_mode_multi_season(monkeypatch, tmp_path):
    # --season 2,3,4 → 一次補三季(不連去年同季),latest 仍不被舊季往回移
    _touch_parquet(tmp_path, "sii", 115, 1)     # 已有最新季
    calls = _patch_main(monkeypatch, tmp_path)
    rc = _ufs.main(["--roc-year", "114", "--season", "2,3,4", "--markets", "sii"])
    assert rc == 0
    assert set(calls) == {(114, 2, "sii"), (114, 3, "sii"), (114, 4, "sii")}
    meta = json.loads((tmp_path / "latest.json").read_text())
    assert (meta["roc_year"], meta["season"]) == (115, 1)   # 補舊季不動最新指標


def test_auto_mode_skips_prev_when_cached(monkeypatch, tmp_path):
    # 先讓去年同季 114Q1 已在快取(上市+上櫃都在)
    _touch_parquet(tmp_path, "sii", 114, 1)
    _touch_parquet(tmp_path, "otc", 114, 1)
    calls = _patch_main(monkeypatch, tmp_path)
    monkeypatch.setattr(_ufs, "latest_published_quarter", lambda _today: (115, 1))
    rc = _ufs.main(["--markets", "sii,otc"])
    assert rc == 0
    # 只抓本季 115Q1(去年同季已在快取 → 略過)
    assert set(calls) == {(115, 1, "sii"), (115, 1, "otc")}


def test_auto_mode_backfills_prev_when_missing(monkeypatch, tmp_path):
    calls = _patch_main(monkeypatch, tmp_path)
    monkeypatch.setattr(_ufs, "latest_published_quarter", lambda _today: (115, 1))
    rc = _ufs.main(["--markets", "sii"])
    assert rc == 0
    # 快取無去年同季 → 本季 + 去年同季都抓
    assert set(calls) == {(115, 1, "sii"), (114, 1, "sii")}
