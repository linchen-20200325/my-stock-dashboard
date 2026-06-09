"""v18.186 mj_snapshot_io 純函式單元測試（tmp_path 隔離不污染本地 cache）。"""
from __future__ import annotations

import json
from pathlib import Path

from mj_snapshot_io import (
    _sanitize_sid,
    _sanitize_yyyymm,
    list_all_stocks_with_snapshots,
    list_snapshots,
    load_latest_two,
    load_snapshot,
    save_snapshot,
)


# ════════════════════════════════════════════════════════════════
# Sanitizers
# ════════════════════════════════════════════════════════════════
class TestSanitize:
    def test_sid_keeps_alnum_dot_dash(self):
        assert _sanitize_sid("2330") == "2330"
        assert _sanitize_sid("00878") == "00878"
        assert _sanitize_sid("BRK.B") == "BRK.B"
        assert _sanitize_sid("00929-DR") == "00929-DR"

    def test_sid_strips_unsafe_chars(self):
        # 防路徑注入：strip 掉 / \ 空白等危險字元；dots 保留供 BRK.B 之類
        # （無 / 或 \ 就無法逃出 base_dir，安全）
        assert _sanitize_sid("../etc/passwd") == "..etcpasswd"
        assert _sanitize_sid("2330/../../") == "2330...."
        assert _sanitize_sid("a b c") == "abc"
        assert "/" not in _sanitize_sid("2330/../../")
        assert "\\" not in _sanitize_sid("2330\\..\\..\\")

    def test_sid_empty_handling(self):
        assert _sanitize_sid("") == ""
        assert _sanitize_sid(None) == ""
        assert _sanitize_sid("   ") == ""

    def test_yyyymm_valid(self):
        assert _sanitize_yyyymm("202503") == "202503"
        assert _sanitize_yyyymm(202503) == "202503"

    def test_yyyymm_invalid(self):
        assert _sanitize_yyyymm("2025-03") == ""
        assert _sanitize_yyyymm("25Q1") == ""
        assert _sanitize_yyyymm("") == ""
        assert _sanitize_yyyymm(None) == ""


# ════════════════════════════════════════════════════════════════
# save_snapshot
# ════════════════════════════════════════════════════════════════
def _fake_mj(cash="Pass"):
    return {
        "Survival_Module": {"Cash_Ratio": {"Status": cash}},
        "cash_ratio_status": "🟢",
    }


class TestSaveSnapshot:
    def test_basic_roundtrip(self, tmp_path: Path):
        fp = save_snapshot("2330", "202503", _fake_mj(), base_dir=tmp_path)
        assert fp is not None
        assert fp.exists()
        assert fp.name == "2330_202503.json"
        # JSON 內容正確
        loaded = json.loads(fp.read_text(encoding="utf-8"))
        assert loaded["cash_ratio_status"] == "🟢"

    def test_atomic_write_no_leftover_tmp(self, tmp_path: Path):
        save_snapshot("2330", "202503", _fake_mj(), base_dir=tmp_path)
        # 不應留 .tmp
        tmps = list(tmp_path.glob("*.tmp"))
        assert tmps == []

    def test_invalid_sid_returns_none(self, tmp_path: Path):
        assert save_snapshot("", "202503", _fake_mj(), base_dir=tmp_path) is None
        assert save_snapshot(None, "202503", _fake_mj(), base_dir=tmp_path) is None

    def test_invalid_yyyymm_returns_none(self, tmp_path: Path):
        assert save_snapshot("2330", "25Q1", _fake_mj(), base_dir=tmp_path) is None
        assert save_snapshot("2330", "", _fake_mj(), base_dir=tmp_path) is None

    def test_non_dict_payload_returns_none(self, tmp_path: Path):
        assert save_snapshot("2330", "202503", "not dict", base_dir=tmp_path) is None
        assert save_snapshot("2330", "202503", None, base_dir=tmp_path) is None
        assert save_snapshot("2330", "202503", [1, 2, 3], base_dir=tmp_path) is None

    def test_overwrites_existing(self, tmp_path: Path):
        save_snapshot("2330", "202503", _fake_mj(cash="Pass"), base_dir=tmp_path)
        save_snapshot("2330", "202503", _fake_mj(cash="Fail"), base_dir=tmp_path)
        loaded = load_snapshot("2330", "202503", base_dir=tmp_path)
        assert loaded["Survival_Module"]["Cash_Ratio"]["Status"] == "Fail"


# ════════════════════════════════════════════════════════════════
# load_snapshot
# ════════════════════════════════════════════════════════════════
class TestLoadSnapshot:
    def test_missing_file_returns_none(self, tmp_path: Path):
        assert load_snapshot("9999", "202503", base_dir=tmp_path) is None

    def test_corrupt_json_returns_none(self, tmp_path: Path):
        tmp_path.mkdir(exist_ok=True)
        bad = tmp_path / "2330_202503.json"
        bad.write_text("{{{not valid json", encoding="utf-8")
        assert load_snapshot("2330", "202503", base_dir=tmp_path) is None

    def test_non_dict_json_returns_none(self, tmp_path: Path):
        tmp_path.mkdir(exist_ok=True)
        bad = tmp_path / "2330_202503.json"
        bad.write_text('["not", "a", "dict"]', encoding="utf-8")
        assert load_snapshot("2330", "202503", base_dir=tmp_path) is None

    def test_invalid_inputs(self, tmp_path: Path):
        assert load_snapshot("", "202503", base_dir=tmp_path) is None
        assert load_snapshot("2330", "bad", base_dir=tmp_path) is None


# ════════════════════════════════════════════════════════════════
# list_snapshots
# ════════════════════════════════════════════════════════════════
class TestListSnapshots:
    def test_empty_dir(self, tmp_path: Path):
        assert list_snapshots("2330", base_dir=tmp_path) == []

    def test_descending_sort(self, tmp_path: Path):
        for ym in ("202403", "202506", "202509", "202412", "202503"):
            save_snapshot("2330", ym, _fake_mj(), base_dir=tmp_path)
        out = list_snapshots("2330", base_dir=tmp_path)
        assert out == ["202509", "202506", "202503", "202412", "202403"]

    def test_filter_by_sid(self, tmp_path: Path):
        save_snapshot("2330", "202503", _fake_mj(), base_dir=tmp_path)
        save_snapshot("0050", "202503", _fake_mj(), base_dir=tmp_path)
        save_snapshot("2330", "202506", _fake_mj(), base_dir=tmp_path)
        assert list_snapshots("2330", base_dir=tmp_path) == ["202506", "202503"]
        assert list_snapshots("0050", base_dir=tmp_path) == ["202503"]

    def test_ignores_unrelated_files(self, tmp_path: Path):
        save_snapshot("2330", "202503", _fake_mj(), base_dir=tmp_path)
        (tmp_path / "README.md").write_text("hi", encoding="utf-8")
        (tmp_path / "2330_bad.json").write_text("{}", encoding="utf-8")
        out = list_snapshots("2330", base_dir=tmp_path)
        assert out == ["202503"]


# ════════════════════════════════════════════════════════════════
# load_latest_two
# ════════════════════════════════════════════════════════════════
class TestLoadLatestTwo:
    def test_no_snapshots(self, tmp_path: Path):
        prev, curr, p_ym, c_ym = load_latest_two("2330", base_dir=tmp_path)
        assert (prev, curr, p_ym, c_ym) == (None, None, None, None)

    def test_one_snapshot_only(self, tmp_path: Path):
        save_snapshot("2330", "202506", _fake_mj(), base_dir=tmp_path)
        prev, curr, p_ym, c_ym = load_latest_two("2330", base_dir=tmp_path)
        assert prev is None
        assert curr is not None
        assert p_ym is None
        assert c_ym == "202506"

    def test_two_snapshots_descending(self, tmp_path: Path):
        save_snapshot("2330", "202503", _fake_mj(cash="Acceptable"), base_dir=tmp_path)
        save_snapshot("2330", "202506", _fake_mj(cash="Pass"), base_dir=tmp_path)
        prev, curr, p_ym, c_ym = load_latest_two("2330", base_dir=tmp_path)
        assert p_ym == "202503"
        assert c_ym == "202506"
        assert prev["Survival_Module"]["Cash_Ratio"]["Status"] == "Acceptable"
        assert curr["Survival_Module"]["Cash_Ratio"]["Status"] == "Pass"

    def test_three_snapshots_takes_top_two(self, tmp_path: Path):
        for ym in ("202412", "202503", "202506"):
            save_snapshot("2330", ym, _fake_mj(), base_dir=tmp_path)
        _, _, p_ym, c_ym = load_latest_two("2330", base_dir=tmp_path)
        assert (p_ym, c_ym) == ("202503", "202506")


# ════════════════════════════════════════════════════════════════
# list_all_stocks_with_snapshots
# ════════════════════════════════════════════════════════════════
class TestListAllStocks:
    def test_dedupe_and_sort(self, tmp_path: Path):
        save_snapshot("2330", "202503", _fake_mj(), base_dir=tmp_path)
        save_snapshot("2330", "202506", _fake_mj(), base_dir=tmp_path)
        save_snapshot("0050", "202506", _fake_mj(), base_dir=tmp_path)
        save_snapshot("6770", "202506", _fake_mj(), base_dir=tmp_path)
        out = list_all_stocks_with_snapshots(base_dir=tmp_path)
        assert out == ["0050", "2330", "6770"]

    def test_empty(self, tmp_path: Path):
        assert list_all_stocks_with_snapshots(base_dir=tmp_path) == []
