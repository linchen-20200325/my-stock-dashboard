"""
共用測試夾具 (Fixtures)
提供 bull_df / bear_df / short_df / minimal_df 等標準 OHLCV DataFrame。

v18.359 併入 root conftest._isolate_module_caches:
原 root 的 conftest.py 持有 module-level cache 清空 autouse fixture
(tw_macro `_ttl_cache` + macro_core `_FRED_CACHE` / `_YF_CLOSE_CACHE`),
防測試污染。原 root conftest 的覆蓋範圍僅限 root test_*.py;Phase 2 F-1.3
將 root test_*.py 全搬入 tests/ 後,該 fixture 必須隨之併入本檔覆蓋。
"""
import sys
import os

# 確保專案根目錄在 Python 路徑中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd

# v18.361 F-6.5 R5:在 conftest load 時(test_data_coverage 之前)捕捉真實 streamlit,
#   存 backup。
# v19.107 生命週期重整(CI slow lane 全滅根因):
#   舊制靠「stub 掛 `_stub` 記號 + 每 test 前後還原」,但三代 stub 記號不一致
#   (`_stub` / `_is_test_stub` / 無記號),classroom 的 `_is_test_stub` 永不被還原
#   → collection 期模組級 stub 卡住整個 run phase → slow lane 24 個 AppTest
#   全 skip(守衛偵測到 stub)+ test_screener_candidates 硬炸
#   「'streamlit' is not a package」。CI run 對照:main 8b071cb 同紅,非 PR 引入。
#   新制:
#   ① stub 檔各自用 module-scoped autouse fixture 管生命週期(裝 stub → 測完
#      還原 pristine + reload 被綁模組),不再模組級永久替換;
#   ② conftest 只留 pytest_collection_finish **身分還原**(identity check,
#      不認記號)作為未來漏網 stub 的 backstop — collection 一結束全域必乾淨;
#   ③ tests/test_zz_streamlit_pollution_lock.py(字母序最後)鎖 run phase 尾端
#      streamlit 仍為真 package — 未來任何測試內 stub 沒收尾,CI 直接紅。
try:
    import streamlit as _STREAMLIT_PRISTINE  # noqa: F401
except Exception:
    _STREAMLIT_PRISTINE = None


def reload_prefixed_modules(prefixes: tuple[str, ...]) -> None:
    """就地 reload 指定前綴的已載入模組(rebind 它們的 module-level `st`)。

    importlib.reload 是 in-place 重執行 → 既有引用(package `_SUBMODULES`
    tuple、`from x import fn` 拿到的函式所屬 globals)全部看到新綁定,
    不會產生「兩份模組」。供 stub fixture 在裝 stub 後/還原後各呼叫一次。
    """
    import importlib
    for _name in sorted(k for k in list(sys.modules)
                        if any(k == p or k.startswith(p + ".") for p in prefixes)):
        _mod = sys.modules.get(_name)
        if _mod is None or not hasattr(_mod, "__spec__") or _mod.__spec__ is None:
            continue
        try:
            importlib.reload(_mod)
        except Exception:
            pass  # smoke-allow-pass — 個別模組 reload 失敗不炸整個 fixture


def restore_pristine_streamlit() -> bool:
    """把 sys.modules['streamlit'] 換回 conftest 載入時捕捉的真身(身分比對,
    不認任何 stub 記號)。回傳是否有做置換。"""
    cur = sys.modules.get("streamlit")
    if _STREAMLIT_PRISTINE is not None and cur is not _STREAMLIT_PRISTINE:
        sys.modules["streamlit"] = _STREAMLIT_PRISTINE
        return True
    return False


def pytest_collection_finish(session):  # noqa: ARG001
    """collection(=全部 test 模組 import)結束 → 全域 streamlit 必須是真身。

    backstop:未來若有測試檔又在模組層裝 stub 忘了收,run phase 一開始就被
    這裡矯正,而非讓字母序在後的整批測試陪葬(v19.74 CI run #422 病史)。
    """
    restore_pristine_streamlit()


def _clear_module_caches() -> None:
    """清空 tw_macro / macro_core 的 module-level in-process 快取。

    防禦式實作:模組未 import / 屬性不存在皆靜默跳過,不讓 fixture 自身炸測試。
    正式執行(Streamlit Cloud)每個 session 自然有 TTL 失效 + 跨 session 隔離,
    故此污染**僅存在於測試環境**(同一 pytest process 內跨測試殘留)。
    """
    try:
        from src.data.macro import tw_macro
        for _name in dir(tw_macro):
            _fn = getattr(tw_macro, _name, None)
            _clear = getattr(_fn, "cache_clear", None)
            if callable(_clear):
                _clear()
    except Exception:
        pass

    try:
        from src.data.macro import macro_core
        for _name in dir(macro_core):
            if _name.endswith("_CACHE"):
                _obj = getattr(macro_core, _name, None)
                if isinstance(_obj, dict):
                    _obj.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _isolate_module_caches():
    """每個測試前後清空 module-level 快取,杜絕跨測試污染。

    v19.107:移除舊的每-test streamlit 還原 — 它與 module-scoped stub fixture
    衝突(function fixture 跑在 module fixture 之內,會把該模組自己的 stub
    中途拔掉)。streamlit 生命週期改由 stub 檔自身 fixture + collection_finish
    backstop + zz 鎖尾測試三層負責(見檔頭 v19.107 註)。
    """
    _clear_module_caches()
    yield
    _clear_module_caches()


def _make_ohlcv(prices, atr_pct=0.01, volumes=None):
    """從收盤價列表建立最小 OHLCV DataFrame。
    high = close * (1 + atr_pct), low = close * (1 - atr_pct)
    """
    n = len(prices)
    return pd.DataFrame({
        "close":  [float(p) for p in prices],
        "open":   [float(p) for p in prices],
        "high":   [float(p) * (1 + atr_pct) for p in prices],
        "low":    [float(p) * (1 - atr_pct) for p in prices],
        "volume": volumes if volumes is not None else [1_000_000] * n,
    })


@pytest.fixture
def bull_df():
    """130 天穩定上漲序列（100→229）。所有 MA 趨勢條件均應成立。"""
    prices = [float(100 + i) for i in range(130)]
    return _make_ohlcv(prices, atr_pct=0.01)


@pytest.fixture
def bear_df():
    """130 天穩定下跌序列（229→100）。所有 MA 趨勢條件均不成立。"""
    prices = [float(229 - i) for i in range(130)]
    return _make_ohlcv(prices, atr_pct=0.01)


@pytest.fixture
def short_df():
    """59 天 DataFrame——不足以計算趨勢分數（需 >=60）。"""
    prices = [float(100 + i) for i in range(59)]
    return _make_ohlcv(prices)


@pytest.fixture
def minimal_df():
    """恰好 20 天 DataFrame——大多數評分函數的最小有效輸入。"""
    prices = [float(100 + i) for i in range(20)]
    return _make_ohlcv(prices)
