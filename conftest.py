"""根目錄 conftest — 全測試共用的測試隔離夾具。

CLAUDE.md §5 流程層「冪等性」:同輸入重跑得同結果。本檔解決一個**測試污染**
(test pollution)問題,**非**修改 production 行為:

`tw_macro.py` 多個 fetcher 帶 module-level `_ttl_cache`(in-process TTL+LRU),
`macro_core.py` 帶 module-level `_FRED_CACHE` / `_YF_CLOSE_CACHE` dict。這些快取
在**同一 pytest process 內跨測試殘留** — 早一個測試(如 test_finmind_via_proxy
回 fii_net=4e9)填入快取後,後續測試(test_finmind_no_data 期望 None)即使
monkeypatch 了 fetch_url 仍讀到舊快取值 → 假性失敗。

正式執行(Streamlit Cloud)每個 session 自然有 TTL 失效 + 跨 session 隔離,
故此污染**僅存在於測試環境**。修法:每個測試前清空所有 module-level 快取,
讓每個測試都跑真實 code path 的全新狀態(= 強化測試真實性,非掩蓋 bug)。

註:`tests/conftest.py` 僅覆蓋 `tests/` 子目錄;根目錄 test_*.py
(test_tw_macro / test_macro_core / test_app_step4 等)需本檔覆蓋。
"""
from __future__ import annotations

import pytest


def _clear_module_caches() -> None:
    """清空 tw_macro / macro_core 的 module-level in-process 快取。

    防禦式實作:模組未 import / 屬性不存在皆靜默跳過,不讓 fixture 自身炸測試。
    """
    # tw_macro：所有帶 `_ttl_cache` 的 fetcher 都掛了 `.cache_clear`
    try:
        import tw_macro
        for _name in dir(tw_macro):
            _fn = getattr(tw_macro, _name, None)
            _clear = getattr(_fn, "cache_clear", None)
            if callable(_clear):
                _clear()
    except Exception:
        pass

    # macro_core：module-level dict 快取(_FRED_CACHE / _YF_CLOSE_CACHE 等)
    try:
        import macro_core
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
    _clear_module_caches()
    yield
    _clear_module_caches()
