"""批 X2：DL-f1-s56 —— `update_macro_history.fetch_finmind_inst` 缺 `name` 欄改 raise（客戶 2026-10-03 放行 L3-G4 之 s56）。

修前：缺 `name` 欄印「缺欄位 name」後回空表 → `update_one` 把空表記成 `EMPTY_FETCH_MARKER`
（「抓取結果為空」）＝ 讀取端當「沒有新資料」；同函式缺 date／buy／sell 卻是 raise（DL-f1-s43）。
修後：缺 `name` 欄 → raise，訊息與缺 date／buy／sell 同一句（欄名換成 name）；`update_one` 接住 →
last_error 記真正原因、既有 parquet 一個 byte 不動。

範圍外（照舊、本檔釘住不變）：`name` 欄在但沒有 'Foreign' 列 → 仍回空表（另登待辦）；
上游回空表 → 照舊回空表；資料齊全 → 輸出逐位不變。無網路：`_finmind_get` 一律 monkeypatch。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import scripts.update_macro_history as umh
from shared.staleness import EMPTY_FETCH_MARKER
from tests.test_dl_f1_r4_batch import _INST_SRC, _assert_bitwise, _pre_s43_formula, _raw_inst, _run_inst

_TODAY = dt.date(2026, 9, 28)


def _seed_parquet(path) -> bytes:
    pd.DataFrame({"date": [dt.date(2026, 9, 18)], "foreign_buy": [12.5], "source": [_INST_SRC],
                  "fetched_at": ["2026-09-18T12:00:00+00:00"]}).to_parquet(path, index=False)
    return path.read_bytes()


class TestS56MissingNameFailsLoud:
    def test_missing_name_column_raises(self, monkeypatch):
        raw = _raw_inst().drop(columns=["name"])
        with pytest.raises(RuntimeError) as ei:
            _run_inst(monkeypatch, raw)
        msg = str(ei.value)
        assert msg.startswith("缺欄 ['name']（欄位=['buy', 'date', 'sell']）"), msg
        # 與缺 date／buy／sell 同一句（DL-f1-s43 的既有訊息，只換欄名）
        assert msg.endswith("→ 算不出外資淨買賣超；不寫入 parquet（§1：不以 0 代入、不猜欄位）"), msg

    def test_message_matches_the_existing_missing_buy_sentence(self, monkeypatch):
        with pytest.raises(RuntimeError) as e_name:
            _run_inst(monkeypatch, _raw_inst().drop(columns=["name"]))
        with pytest.raises(RuntimeError) as e_buy:
            _run_inst(monkeypatch, _raw_inst().drop(columns=["buy"]))
        tail = lambda e: str(e.value).split("）", 1)[1]                  # 欄位清單之後的部分
        assert tail(e_name) == tail(e_buy)

    def test_update_one_records_the_cause_not_empty_and_keeps_parquet(self, monkeypatch, tmp_path):
        monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
        before = _seed_parquet(tmp_path / "finmind_inst.parquet")
        raw = _raw_inst().drop(columns=["name"])
        monkeypatch.setattr(umh, "_finmind_get", lambda *a, **k: raw.copy())
        meta = umh.update_one("finmind_inst", _TODAY, False, 20, "tok")
        assert meta["last_error"].startswith("RuntimeError: 缺欄 ['name']"), meta
        assert meta["last_error"] != EMPTY_FETCH_MARKER
        assert EMPTY_FETCH_MARKER not in meta["last_error"]
        assert (tmp_path / "finmind_inst.parquet").read_bytes() == before
        # 抓取拋例外 ≠ 表是空的（DL-f1-s55 既有分支）：描述現有 parquet
        assert (meta["row_count"], meta["last_updated"]) == (1, "2026-09-18")


class TestS56OutOfScopeUnchanged:
    def test_all_present_output_bitwise_unchanged(self, monkeypatch):
        raw = _raw_inst()
        got = _run_inst(monkeypatch, raw)
        _assert_bitwise(got, _pre_s43_formula(raw))
        assert list(got.columns) == ["date", "foreign_buy", "source", "fetched_at"]

    def test_upstream_empty_still_returns_empty(self, monkeypatch):
        assert _run_inst(monkeypatch, pd.DataFrame()).empty

    def test_name_present_without_foreign_rows_still_returns_empty(self, monkeypatch, capsys):
        raw = _raw_inst()
        raw = raw[~raw["name"].str.contains("Foreign")]
        got = _run_inst(monkeypatch, raw)
        assert got.empty
        assert "name 欄位無 'Foreign' 列" in capsys.readouterr().out
