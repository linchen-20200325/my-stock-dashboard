"""tests/test_xvext_revert_chain.py — XV 客戶裁示批（XV-H1-EXT／XV-H3／XV-H2-EXT／XV-M1，2026-10-28）的還原鏈新頭節。

為什麼需要：本批改了被舊鏈（`sheet_safety_revert_for` → … → `c1_revert_for`／`dec074_revert_for` 等）以
基底 sha 守衛的檔 ⇒ 在鏈頭**往前接一節**，先把本批改動換回（比照 `xview_revert_for` 接
`sheet_safety_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha）。

基底 ＝ `f3d77703`（本批開工前的 main）。pair 於產生時驗證「套用後逐字等於基底、
每個新寫法在現行檔恰出現 1 次、在基底 0 次」。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

XVEXT_BASE_SHA = {'src/data/macro/macro_core.py': '68cb0fb283bb473031e423e47f0696dea0d02d871c3fea519d8a1a767a75ac9c'}

XVEXT_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'src/data/macro/macro_core.py': (('\n'
                                   '\n'
                                   'def clear_success_caches() -> tuple[str, ...]:\n'
                                   '    """清掉本模組的**成功**快取（`_YF_CLOSE_CACHE`、`_FRED_CACHE`），回傳實際清了哪幾層。\n'
                                   '\n'
                                   '    XV-H2-EXT／XV-M1（客戶 2026-10-28 裁示）：側欄「🔄 強制刷新數據」原本只做\n'
                                   '    `st.cache_data.clear()`，本模組自建的成功快取（VIX／匯率等 Yahoo 收盤 1hr、FRED 30min）\n'
                                   '    沒有任何 production 清除路徑 ⇒ 按了刷新仍拿舊值。由 L6 `app.py` 該按鈕經 L3 `force_refresh_service` 呼叫。\n'
                                   '    ⛔ **刻意不清**失敗退避表（`_FRED_FAIL_CACHE`、`_YF_CLOSE_EMPTY_FAIL_CACHE`、\n'
                                   '    `_YF_OHLCV_FAIL_CACHE`／`_YF_OHLCV_OK_GEN_CACHE`）：v3 §02「失敗時退避、不連續轟炸來源」\n'
                                   '    不得因為使用者按了刷新就破功。讀寫持與抓取端同一把鎖。\n'
                                   '    """\n'
                                   '    with _FRED_CACHE_LOCK:\n'
                                   '        _FRED_CACHE.clear()\n'
                                   '    with _YF_CLOSE_CACHE_LOCK:\n'
                                   '        _YF_CLOSE_CACHE.clear()\n'
                                   '    return ("macro_core._FRED_CACHE", "macro_core._YF_CLOSE_CACHE")\n',
                                   ''),)}



def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def xvext_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = XVEXT_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} XV 客戶裁示批還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_xvext_revert_is_exact_base_source():
    assert set(XVEXT_REVERT_PAIRS) == set(XVEXT_BASE_SHA)
    for rel in sorted(XVEXT_REVERT_PAIRS):
        code = xvext_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == XVEXT_BASE_SHA[rel], rel


def test_xvext_revert_is_idempotent():
    for rel in sorted(XVEXT_REVERT_PAIRS):
        once = xvext_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert xvext_revert_for(rel, once) == once, rel


def test_chain_head_calls_xvext_before_xview():
    """原鏈頭 `sheet_safety_revert_for` 必須先呼叫本節，再呼叫 xview 節。"""
    import inspect

    from tests.test_sheet_safety_revert_chain import sheet_safety_revert_for
    src = inspect.getsource(sheet_safety_revert_for)
    assert src.index("xvext_revert_for(rel, code)") < src.index("xview_revert_for(rel, code)")
