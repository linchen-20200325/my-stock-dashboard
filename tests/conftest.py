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
#   存 backup;autouse fixture 每 test 結束後若 sys.modules['streamlit'] 是 stub
#   且 caller 真需要 divider 等完整 API,還原回 pristine。
#   tests/test_data_coverage.py:43 module-level _stub_st() 永久替換,沒 cleanup,
#   F-6.5 後 collection 順序變,macro_classroom 在它之後跑時 stub 卡住 st.divider。
try:
    import streamlit as _STREAMLIT_PRISTINE  # noqa: F401
except Exception:
    _STREAMLIT_PRISTINE = None


def _restore_streamlit() -> None:
    """若 sys.modules['streamlit'] 是 stub,還原為 pristine 版本(若有)。"""
    cur = sys.modules.get("streamlit")
    if cur is not None and getattr(cur, "_stub", False) and _STREAMLIT_PRISTINE is not None:
        sys.modules["streamlit"] = _STREAMLIT_PRISTINE


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
    """每個測試前後清空 module-level 快取,杜絕跨測試污染。"""
    _restore_streamlit()
    _clear_module_caches()
    yield
    _restore_streamlit()
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
