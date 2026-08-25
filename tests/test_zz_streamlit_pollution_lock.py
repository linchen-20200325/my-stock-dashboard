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
import types

import pytest

# ── 2026-08-25 新增的第四層:模組手上那份引用 ────────────────────────────
# 前三層都只看 `sys.modules['streamlit']` 這一個位置。但 stub 視窗真正的
# 破壞力在別處:視窗內**首次 import** 的模組,其 module-level `st` 會永久
# 綁在待丟棄的 stub 上 —— 就算 sys.modules 還原得乾乾淨淨。
#
# 實例(本次抓到的第三次同類事故):`src/ui/tabs/__init__.py` 是 eager barrel,
# 「import 一個 tab」連鎖拉進近千個模組。stub 視窗內做這件事,70 個模組
# 從此拿著死 stub,造成:
#   · 18 個測試在特定順序下紅(4 個檔),而全套件因字母序僥倖躲過
#   · `@st.cache_data` 在約 20 個 L1 fetcher 上**靜默變成 no-op**
#   · `config._st.secrets` 恆空 → FINMIND_TOKEN 讀不到
# 後兩項沒有任何測試在斷言,所以完全無聲。
_ST_HOLDER_PREFIXES: tuple[str, ...] = ("src", "shared", "infra")
_ST_ATTR_NAMES: tuple[str, ...] = ("st", "_st")


def _foreign_st_holders() -> list[str]:
    """回傳 module-level `st` / `_st` 指向「**不是**現行 streamlit」的模組。

    只認 `types.ModuleType` 且 `__name__ == 'streamlit'` 者 —— 這樣
    EX-CACHE-1 那種 `except ImportError: _NoOpST` 的 fallback 類別不會被誤判。
    """
    _real = sys.modules.get("streamlit")
    _out: list[str] = []
    for _name in sorted(k for k in list(sys.modules)
                        if any(k == p or k.startswith(p + ".") for p in _ST_HOLDER_PREFIXES)):
        _mod = sys.modules.get(_name)
        if _mod is None:
            continue
        for _attr in _ST_ATTR_NAMES:
            _obj = getattr(_mod, _attr, None)
            if (isinstance(_obj, types.ModuleType)
                    and getattr(_obj, "__name__", "") == "streamlit"
                    and _obj is not _real):
                _out.append(f"{_name}.{_attr}")
                break
    return _out


def _assert_no_module_holds_a_dead_stub():
    _holders = _foreign_st_holders()
    assert not _holders, (
        f"{len(_holders)} 個模組的 module-level st/_st 仍指向**已被丟棄的 stub**"
        f"(sys.modules['streamlit'] 本身是乾淨的,所以前三層鎖抓不到):\n"
        + "\n".join(f"  · {_h}" for _h in _holders[:25])
        + (f"\n  …另外 {len(_holders) - 25} 個" if len(_holders) > 25 else "")
        + "\n\n修法:裝 stub 的 fixture 要做兩件事 ——\n"
          "  ① 裝 stub **之前**先在真 streamlit 下 import 目標,"
          "讓視窗內不會有任何『首次 import』;\n"
          "  ② 收尾時呼叫 `tests.conftest.rebind_modules_bound_to(stub)` "
          "把漏網的模組 reload 回來。\n"
          "(別用無差別 `reload_prefixed_modules(('src',))` —— 慢,且大圖 reload "
          "有自己的身分風險。)"
    )


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


def test_no_module_holds_a_dead_stub_at_end_of_fast_lane():
    """第四層:沒有任何 src/shared/infra 模組還抓著被丟棄的 stub。"""
    _assert_no_module_holds_a_dead_stub()


@pytest.mark.slow
def test_streamlit_is_real_package_at_end_of_slow_lane():
    """slow lane(`pytest -m slow`)也要有同一把鎖 — AppTest 全在 slow lane,
    污染在這裡殺傷力最大(v19.74 起 24 個 AppTest 全 skip 就是這樣來的)。"""
    _assert_real_streamlit()


@pytest.mark.slow
def test_no_module_holds_a_dead_stub_at_end_of_slow_lane():
    _assert_no_module_holds_a_dead_stub()
