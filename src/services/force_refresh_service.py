"""src/services/force_refresh_service.py — 側欄「🔄 強制刷新數據」的模組層快取清除（L3）。

XV-H2-EXT／XV-M1（客戶 2026-10-28 裁示）：按鈕除 `st.cache_data.clear()` 外，另清 L1
`macro_core` 的**成功**快取（`_YF_CLOSE_CACHE`／`_FRED_CACHE`）。⛔ 不清失敗退避表
（v3 §02 失敗退避不得因刷新破功）；session 總經快照、pkl 本批不動。

為什麼有這一層：CLAUDE.md §8.2 硬規則「L5/L6 不得直呼 L1」—— L6 `app.py` 經本模組轉呼叫，
不另立 L6→L1 例外。純轉發、無業務邏輯（實作與鎖在 L1 `macro_core.clear_success_caches`）。
"""
from __future__ import annotations


def clear_module_success_caches() -> tuple[str, ...]:
    """清 macro_core 的成功快取；回傳實際清了哪幾層（只清成功、不清失敗退避）。"""
    from src.data.macro.macro_core import clear_success_caches
    return clear_success_caches()
