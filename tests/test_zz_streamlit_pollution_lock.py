# -*- coding: utf-8 -*-
"""tests/test_zz_streamlit_pollution_lock.py — streamlit 污染鎖(v19.107)。

檔名刻意 `zz` 開頭 = 字母序最後執行:整個 run phase 跑完後,
sys.modules['streamlit'] 必須仍是「真 package」— 任何測試把它換成 stub
沒收尾,本檔在 CI 直接紅,不必再等 AppTest 全 skip / 隔壁測試炸
「'streamlit' is not a package」才發現(v19.74 CI run #422 + main 8b071cb
slow lane 全滅病史,根因兩度實錘)。

三層防線的第三層(前兩層見 tests/conftest.py v19.107 檔頭註):
  ① stub 檔自身 module fixture 收尾 ② collection_finish 身分還原 backstop
  ③ 本檔鎖 run phase 尾端狀態。
"""
from __future__ import annotations

import sys

import pytest


def _assert_real_streamlit():
    st = sys.modules.get("streamlit")
    assert st is not None, "streamlit 不在 sys.modules(測試環境必裝)"
    assert not getattr(st, "_stub", False) and not getattr(st, "_is_test_stub", False), (
        "run phase 尾端 streamlit 仍是 stub — 某測試裝了 stub 沒收尾"
        "(找最近新增/修改的 sys.modules['streamlit'] 賦值處)")
    assert hasattr(st, "__path__"), (
        "streamlit 非 package(被 types.ModuleType stub 取代)— "
        "AppTest 的 `from streamlit.testing.v1 import ...` 會炸")
    # 真正走一次 submodule import(= test_screener_candidates 的死法重現檢查)
    from streamlit.testing.v1 import AppTest  # noqa: F401


def test_streamlit_is_real_package_at_end_of_fast_lane():
    _assert_real_streamlit()


@pytest.mark.slow
def test_streamlit_is_real_package_at_end_of_slow_lane():
    """slow lane(`pytest -m slow`)也要有同一把鎖 — AppTest 全在 slow lane,
    污染在這裡殺傷力最大(v19.74 起 24 個 AppTest 全 skip 就是這樣來的)。"""
    _assert_real_streamlit()
