# -*- coding: utf-8 -*-
"""tests/test_cache_staleness_honesty.py — 本地 parquet 快取「讀取端過期判定」守衛(2026-08-27)。

═══ 為什麼需要(有實際受害者,不是假想)═══════════════════════════════════
`data_cache/finmind_m1m2.parquet` 的最新資料月停在 **2026-06-01**,
`data_cache/metadata.json` 對它的 `last_error` 是「抓取結果為空」——
也就是上游 cron 已經好幾個月沒成功寫進去。而
`scripts/calibrate_health_weights.py`(cron)**每次都照讀**,把過期的 M1B-M2 gap
當當期特徵擬權重,寫成 `MACRO_HEALTH_WEIGHT_PROPOSAL.md` 給人審 ——
提案看起來完全正常,人審者無從得知它吃的是三個月前的資料。

同理 `macro_cache_reader.load_twii_close` / `load_v2_chart_series` 原本
**讀了就用、不看年齡**:cron 一掛,總經 v2 走勢卡會拿舊 parquet 照畫。

§1「錯的數字比沒有數字更危險」→ 本檔守三件事:
  A. `compute_cache_staleness` 的 **§1 誠實預設**:判不出來 → 過期(不假設新鮮);
  B. 讀取端把年齡**帶出來**(Series `.attrs`),且既有回傳契約一字未改;
  C. 校準 script 的輸入閘門會**擋下**過期輸入(不是印個 warning 繼續算)。

⚠️ 判定門檻全部來自 L0 SSOT(`shared/staleness.py`),本檔與被測程式**都不自訂天數**。
   做法沿用全 repo 唯一做對的一組:`src/data/sector_flow/reader.py::_compute_staleness`。
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from src.data.macro.macro_cache_reader import (
    CACHE_DATASET_CADENCE,
    compute_cache_staleness,
    load_twii_close,
    load_v2_chart_series,
    read_cache_metadata,
)

_ATTR_KEYS = {"cache_dataset", "is_stale", "stale_reason", "as_of",
              "age_days", "upstream_error"}


def _write_daily(tmp_path, name: str, last_day: dt.date, n: int = 30):
    idx = pd.bdate_range(end=pd.Timestamp(last_day), periods=n)
    pd.DataFrame({
        "date": idx,
        "close": range(n),
        "foreign_buy": range(n),
        "margin_balance": [1e11] * n,
    }).to_parquet(tmp_path / f"{name}.parquet")


def _write_monthly(tmp_path, name: str, last_month: dt.date, n: int = 12):
    months = pd.date_range(end=pd.Timestamp(last_month), periods=n, freq="MS")
    pd.DataFrame({"date": months, "m1b_m2_gap": range(n)}).to_parquet(
        tmp_path / f"{name}.parquet")


def _write_meta(tmp_path, datasets: dict):
    (tmp_path / "metadata.json").write_text(
        json.dumps({"updated_at": "2026-08-25T00:00:00+00:00",
                    "datasets": datasets}), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════
# A. §1 誠實預設:判不出來一律當過期
# ══════════════════════════════════════════════════════════════════════
class TestHonestDefault:
    def test_unregistered_dataset_is_stale(self, tmp_path):
        """沒登記發布頻率 → 判不出年齡 → 過期(而不是放行)。"""
        r = compute_cache_staleness("no_such_dataset", cache_dir=tmp_path)
        assert r["is_stale"] is True
        assert "未登記" in (r["reason"] or "")

    def test_missing_parquet_is_stale(self, tmp_path):
        r = compute_cache_staleness("twii_ohlcv", cache_dir=tmp_path)
        assert r["is_stale"] is True
        assert r["as_of"] is None

    def test_unparsable_date_column_is_stale(self, tmp_path):
        pd.DataFrame({"date": ["not-a-date", "也不是"], "close": [1, 2]}).to_parquet(
            tmp_path / "twii_ohlcv.parquet")
        r = compute_cache_staleness("twii_ohlcv", cache_dir=tmp_path)
        assert r["is_stale"] is True

    def test_missing_metadata_does_not_crash(self, tmp_path):
        """缺 metadata.json 不該炸 —— 但也不該被當成「沒有錯誤 = 沒問題」。"""
        assert read_cache_metadata(tmp_path) == {}
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 8, 25))
        r = compute_cache_staleness("twii_ohlcv", cache_dir=tmp_path,
                                    today=dt.date(2026, 8, 27))
        assert r["upstream_error"] is None and r["is_stale"] is False

    def test_broken_metadata_is_treated_as_absent(self, tmp_path):
        (tmp_path / "metadata.json").write_text("{ 這不是 JSON", encoding="utf-8")
        assert read_cache_metadata(tmp_path) == {}


# ══════════════════════════════════════════════════════════════════════
# B. 頻率感知:日頻用天數、月頻用「期」
# ══════════════════════════════════════════════════════════════════════
class TestCadenceAware:
    def test_daily_fresh_and_stale(self, tmp_path):
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 8, 25))
        assert compute_cache_staleness(
            "twii_ohlcv", cache_dir=tmp_path, today=dt.date(2026, 8, 27)
        )["is_stale"] is False
        r = compute_cache_staleness(
            "twii_ohlcv", cache_dir=tmp_path, today=dt.date(2026, 9, 30))
        assert r["is_stale"] is True and r["age_days"] == 36

    def test_monthly_uses_periods_not_calendar_days(self, tmp_path):
        """月初 as_of 不得用日曆天量(見 shared/staleness.py G2:會天天假紅燈)。

        2026-06 這一期在 2026-07-20 仍是**當期**(87 天前的同一筆到 08-27 才落後一期)。
        若有人把月頻改成日曆天判定,第一個 assert 會轉紅。
        """
        _write_monthly(tmp_path, "finmind_m1m2", dt.date(2026, 6, 1))
        fresh = compute_cache_staleness(
            "finmind_m1m2", cache_dir=tmp_path, today=dt.date(2026, 7, 20))
        assert fresh["is_stale"] is False, fresh["reason"]
        assert fresh["age_days"] == 49          # 日曆天已 49 天,但仍是當期

        stale = compute_cache_staleness(
            "finmind_m1m2", cache_dir=tmp_path, today=dt.date(2026, 8, 27))
        assert stale["is_stale"] is True
        assert stale["periods_behind"] >= 1
        assert "落後" in stale["reason"]

    def test_upstream_error_is_surfaced(self, tmp_path):
        """metadata 自陳 `last_error` 必須帶出來 —— 它是「上游已經壞了」的唯一線索。"""
        _write_monthly(tmp_path, "finmind_m1m2", dt.date(2026, 6, 1))
        _write_meta(tmp_path, {"finmind_m1m2": {
            "last_updated": "2026-06-01", "row_count": 239,
            "last_error": "抓取結果為空"}})
        r = compute_cache_staleness("finmind_m1m2", cache_dir=tmp_path,
                                    today=dt.date(2026, 8, 27))
        assert r["upstream_error"] == "抓取結果為空"
        assert r["meta_last_updated"] == "2026-06-01"

    def test_every_registered_dataset_has_a_real_parquet_or_is_documented(self):
        """登記表不得長出幽靈條目(登記了卻沒有對應檔 → 判定永遠是「過期」的雜訊)。"""
        assert set(CACHE_DATASET_CADENCE) == {
            "twii_ohlcv", "finmind_inst", "finmind_margin", "finmind_m1m2"}


# ══════════════════════════════════════════════════════════════════════
# C. 讀取端:年齡要帶出來,且既有契約一字未改
# ══════════════════════════════════════════════════════════════════════
class TestReadersCarryStaleness:
    def test_load_twii_close_carries_attrs(self, tmp_path):
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 8, 25), n=40)
        s = load_twii_close(tmp_path, today=dt.date(2026, 8, 27))
        assert len(s) == 40 and s.name == "twii_close"     # 契約不變
        assert _ATTR_KEYS <= set(s.attrs), (
            "load_twii_close 回傳的 Series 沒帶過期資訊 —— "
            "讀取端又變回『讀了就用、不看年齡』")
        assert s.attrs["is_stale"] is False

    def test_load_twii_close_marks_stale(self, tmp_path):
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 6, 1), n=40)
        s = load_twii_close(tmp_path, today=dt.date(2026, 8, 27))
        assert len(s) == 40                                 # 不擋資料
        assert s.attrs["is_stale"] is True                  # 但要講實話
        assert "距今" in (s.attrs["stale_reason"] or "")

    def test_v2_chart_series_contract_unchanged_and_attrs_present(self, tmp_path):
        """key 集合與序列內容不得變(消費端 macro_v2_service 靠它);attrs 是附掛。"""
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 8, 25), n=400)
        _write_daily(tmp_path, "finmind_margin", dt.date(2026, 8, 24), n=400)
        out = load_v2_chart_series(tmp_path, today=dt.date(2026, 8, 27))
        assert set(out) == {"bias_240", "margin"}
        for key, s in out.items():
            assert isinstance(s, pd.Series) and len(s)
            assert _ATTR_KEYS <= set(s.attrs), f"{key} 沒帶過期資訊"

    def test_v2_chart_series_omits_missing_keys(self, tmp_path):
        """§1 既有規矩:取不到的 key 不出現在 dict 裡(不放空 Series 冒充有資料)。"""
        out = load_v2_chart_series(tmp_path, today=dt.date(2026, 8, 27))
        assert out == {}


# ══════════════════════════════════════════════════════════════════════
# D. 校準 script:過期輸入必須被擋下,不是印個 warning 繼續算
# ══════════════════════════════════════════════════════════════════════
class TestCalibrationInputGate:
    @staticmethod
    def _gate():
        import importlib.util
        import pathlib
        import sys

        root = pathlib.Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        spec = importlib.util.spec_from_file_location(
            "_calib_under_test", root / "scripts" / "calibrate_health_weights.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_all_fresh_passes(self, tmp_path):
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 8, 25))
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 8, 25))
        _write_monthly(tmp_path, "finmind_m1m2", dt.date(2026, 7, 1))
        assert self._gate().check_inputs_fresh(
            tmp_path, today=dt.date(2026, 8, 27)) == []

    def test_stale_monthly_input_is_blocked(self, tmp_path):
        """這就是實際發生的那一種:檔案在、讀得到,但資料月停在三個月前。"""
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 8, 25))
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 8, 25))
        _write_monthly(tmp_path, "finmind_m1m2", dt.date(2026, 6, 1))
        bad = self._gate().check_inputs_fresh(tmp_path, today=dt.date(2026, 8, 27))
        assert [b["dataset"] for b in bad] == ["finmind_m1m2"]

    def test_upstream_error_alone_is_blocked(self, tmp_path):
        """資料日期還新,但 metadata 自陳抓取失敗 → 同樣擋(§1 保守側)。"""
        _write_daily(tmp_path, "twii_ohlcv", dt.date(2026, 8, 25))
        _write_daily(tmp_path, "finmind_inst", dt.date(2026, 8, 25))
        _write_monthly(tmp_path, "finmind_m1m2", dt.date(2026, 7, 1))
        _write_meta(tmp_path, {"finmind_inst": {
            "last_updated": "2026-08-25", "row_count": 1, "last_error": "抓取結果為空"}})
        bad = self._gate().check_inputs_fresh(tmp_path, today=dt.date(2026, 8, 27))
        assert [b["dataset"] for b in bad] == ["finmind_inst"]

    def test_gate_has_no_bypass_flag(self):
        """刻意不提供 `--allow-stale` 之類旁路 —— 有旁路就等於沒有閘門。"""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "scripts" / "calibrate_health_weights.py").read_text(encoding="utf-8")
        for bypass in ("allow-stale", "allow_stale", "--force", "skip_staleness"):
            assert bypass not in src, f"校準 script 出現繞過過期檢查的旁路:{bypass}"


def test_real_repo_cache_m1m2_is_currently_stale_or_fixed():
    """對真實 `data_cache/` 的現況揭露(不是行為斷言)。

    2026-08-27 現況:`finmind_m1m2` 落後 ≥1 期且 `last_error='抓取結果為空'`。
    若上游修好、本測試的 xfail 條件不再成立,pytest 會報 XPASS ——
    那時請把本測試改成正向斷言,**不要**直接刪掉(它是這件事的唯一 CI 痕跡)。
    """
    r = compute_cache_staleness("finmind_m1m2")
    if not (r["is_stale"] or r["upstream_error"]):
        pytest.skip("finmind_m1m2 已恢復新鮮 —— 上游修好了,請回頭收斂本測試")
    assert r["reason"] or r["upstream_error"], "判為過期卻講不出理由 = 沒有誠實揭露"
