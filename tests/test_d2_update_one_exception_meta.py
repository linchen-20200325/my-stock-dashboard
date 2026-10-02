# -*- coding: utf-8 -*-
"""批 D2 — DL-f1-s55：`update_one` 抓取拋例外、既有檔正常時，metadata 的 row_count／last_updated
描述現有 parquet（原本捏成 0／null）；last_error 照舊記例外。

三個最容易出錯的輸入（§6）：
1. 抓取拋例外 ＋ 既有檔正常 → row_count／last_updated 取自既有檔
2. 抓取拋例外 ＋ 沒有既有檔 → 照舊 0／null（真的沒有）
3. 抓取拋例外 ＋ 既有檔 sanity 不過 → 照舊既有分支（不背書 last_updated）
"""
from __future__ import annotations

import pandas as pd

import scripts.update_macro_history as umh
from tests.test_dl_f1_r4_batch import _INST_DATES, _TODAY, _inst_parquet


def _boom(*a, **k):
    raise RuntimeError("upstream down")


def test_exception_with_existing_describes_parquet(monkeypatch, tmp_path):
    monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
    _inst_parquet(tmp_path / "finmind_inst.parquet", _INST_DATES[:3])
    monkeypatch.setitem(umh.FETCHERS, "finmind_inst", (_boom, True))
    meta = umh.update_one("finmind_inst", _TODAY, False, 20, "tok")
    assert meta == {"name": "finmind_inst", "last_updated": "2026-09-23", "row_count": 3,
                    "last_error": "RuntimeError: upstream down"}


def test_exception_without_existing_stays_zero_and_null(monkeypatch, tmp_path):
    monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
    monkeypatch.setitem(umh.FETCHERS, "finmind_inst", (_boom, True))
    meta = umh.update_one("finmind_inst", _TODAY, False, 20, "tok")
    assert (meta["row_count"], meta["last_updated"]) == (0, None)
    assert meta["last_error"] == "RuntimeError: upstream down"


def test_exception_with_bad_existing_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(umh, "CACHE_DIR", tmp_path)
    _inst_parquet(tmp_path / "zz_probe.parquet", _INST_DATES[:2])
    monkeypatch.setitem(umh.FETCHERS, "zz_probe", (_boom, True))
    monkeypatch.setitem(umh._EXISTING_SANITY_GATES, "zz_probe", lambda df: (False, "壞"))
    meta = umh.update_one("zz_probe", _TODAY, False, 20, "tok")
    assert meta == {"name": "zz_probe", "last_updated": None, "row_count": 2,
                    "last_error": "RuntimeError: upstream down；既有檔 sanity 不過,待重建"}
