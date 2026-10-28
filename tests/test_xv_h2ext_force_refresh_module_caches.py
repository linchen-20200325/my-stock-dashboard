"""XV-H2-EXT／XV-M1（AI 總管決定（DEC-101(5) 授權邊界內），2026-10-28）：側欄 🔄 強制刷新另清 macro_core 的**成功**快取。

⛔ 失敗退避表（`_FRED_FAIL_CACHE`／`_YF_CLOSE_EMPTY_FAIL_CACHE`／`_YF_OHLCV_*`）不得被清
（v3 §02「失敗時退避、不連續轟炸來源」）。無網路：只操作 module dict。
"""
from __future__ import annotations

import pandas as pd

from src.data.macro import macro_core as mc
from src.services.force_refresh_service import clear_module_success_caches


def _seed():
    mc._FRED_CACHE[("DGS10", "k", 10)] = (1.0, pd.DataFrame({"v": [1]}))
    mc._YF_CLOSE_CACHE[("^VIX", "1d")] = (1.0, pd.Series([20.0]))
    mc._FRED_FAIL_CACHE[("BAD", "k", 10)] = 2.0
    mc._YF_CLOSE_EMPTY_FAIL_CACHE[("BAD", "1d")] = 3.0
    mc._YF_OHLCV_FAIL_CACHE[("BAD", "1y", "1d")] = 4.0
    mc._YF_OHLCV_OK_GEN_CACHE[("OK", "1y", "1d")] = 5


def test_clears_success_only():
    _seed()
    out = mc.clear_success_caches()
    assert out == ("macro_core._FRED_CACHE", "macro_core._YF_CLOSE_CACHE")
    assert mc._FRED_CACHE == {} and mc._YF_CLOSE_CACHE == {}
    assert mc._FRED_FAIL_CACHE == {("BAD", "k", 10): 2.0}
    assert mc._YF_CLOSE_EMPTY_FAIL_CACHE == {("BAD", "1d"): 3.0}
    assert mc._YF_OHLCV_FAIL_CACHE == {("BAD", "1y", "1d"): 4.0}
    assert mc._YF_OHLCV_OK_GEN_CACHE == {("OK", "1y", "1d"): 5}


def test_l3_wrapper_delegates():
    _seed()
    assert clear_module_success_caches() == ("macro_core._FRED_CACHE", "macro_core._YF_CLOSE_CACHE")
    assert mc._FRED_CACHE == {} and mc._YF_CLOSE_CACHE == {}
    assert mc._FRED_FAIL_CACHE  # 退避表保留


def test_after_clear_next_call_refetches(monkeypatch):
    """清除後同鍵不再命中成功快取 ⇒ 會走取數（stub，無網路）。"""
    calls = []

    def _fake_fetch_url(url, *a, **k):
        calls.append(url)
        return None                      # 模擬失敗（不入成功快取）
    monkeypatch.setattr(mc, "fetch_url", _fake_fetch_url)
    mc._YF_CLOSE_CACHE.clear()
    mc._YF_CLOSE_EMPTY_FAIL_CACHE.clear()
    import time
    mc._YF_CLOSE_CACHE[("^VIX", "1d")] = (time.time(), pd.Series([20.0]))
    s1 = mc._fetch_yf_close_base("^VIX", "1d")
    assert list(s1) == [20.0] and calls == []          # 命中成功快取，不取數
    mc.clear_success_caches()
    mc._fetch_yf_close_base("^VIX", "1d")
    assert len(calls) == 1                              # 清後真的重抓


def test_decision_owner_is_ai_manager_not_client():
    """QA 回修 #8：XV-H2-EXT／XV-M1 是 AI 總管在 DEC-101(5) 授權邊界內的決定，⛔ 不得寫成客戶裁示。"""
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1]
    for rel in ("app.py", "src/data/macro/macro_core.py", "src/services/force_refresh_service.py",
                "tests/test_xview_v2_force_refresh_help.py", "tests/test_batch_z60.py"):
        txt = (root / rel).read_text(encoding="utf-8")
        for m in re.finditer(r"XV-H2-EXT／XV-M1（[^）\n]*", txt):
            assert "客戶" not in m.group(0), (rel, m.group(0))
