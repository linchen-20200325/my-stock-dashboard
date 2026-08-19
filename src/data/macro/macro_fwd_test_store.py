"""src/data/macro/macro_fwd_test_store.py — 總經燈號快照「本地落地」(L1 Data)。

職責一句話:把 `macro_forward_test.build_signal_row` 產出的列 append 進
git 追蹤的 parquet;純檔案 I/O,無業務邏輯、無 streamlit。

路徑 SSOT 在 L0 `shared.macro_forward_test_schema.MACRO_FWD_TEST_RELPATH`。
子目錄是刻意的 —— `.gitignore` 有 `data_cache/*.parquet` 頂層規則,
放子目錄才追蹤得到(同 `data_cache/forward_test/` 手法)。

§5 冪等 vs `forward_test_store` 的差異(刻意不同,不是抄漏)
--------------------------------------------------------
`forward_test_store` 是「同 (cohort, stock_id) 已存在 → 保留最早那筆」——
因為那存的是**真實進場價**,改掉就等於竄改成交紀錄。

本檔相反:同 `date` 重跑 → **後寫者勝**。因為這裡存的是「這套規則對那天的
判定」,而規則會改(2026-08-19 一天就改三次)。重跑通常正是為了記錄新規則的
判定;保留舊列反而會讓 `ruleset_hash` 與內容對不上。**兩列都想留的話,
應該分兩個檔而不是在同一個 date 下堆疊** —— 否則 precision 統計會把同一天
算兩次。

§8.2 L1:純檔案 I/O。不 import L2(schema 走 L0),不重犯 V-FT-STORE-1。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from shared.macro_forward_test_schema import (
    MACRO_FWD_TEST_HEADERS,
    MACRO_FWD_TEST_KEY,
    MACRO_FWD_TEST_RELPATH,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
MACRO_FWD_TEST_PATH: Path = _REPO_ROOT.joinpath(*MACRO_FWD_TEST_RELPATH)


def load_signals(path: Optional[Path] = None) -> list[dict]:
    """讀本地快照 → list[dict]。檔不存在 → []。

    讀檔失敗**不吞**:print 明確訊息後回 []。§1 的「不可靜默」在這裡的
    平衡點是 —— 一個壞掉的歷史檔不該讓 cron 整個掛掉(那會連新的一天也記不到),
    但一定要在 log 留下痕跡,否則會出現「資料悄悄停止累積」而沒人發現。
    """
    p = Path(path) if path else MACRO_FWD_TEST_PATH
    if not p.exists():
        return []
    try:
        df = pd.read_parquet(p)
    except Exception as _e:  # noqa: BLE001
        print(f'[macro_fwd_test_store] ⚠️ 讀取失敗 {p}: {type(_e).__name__}: {_e} '
              f'—— 本次視為無歷史,新列仍會寫入(舊檔請人工檢查)')
        return []
    if df is None or df.empty:
        return []
    return df.to_dict('records')


def append_signals(rows: list[dict], path: Optional[Path] = None) -> int:
    """append 快照列,回「本次寫入的列數」。同 `date` → 後寫者勝(見模組 docstring)。

    Raises:
        ValueError: 列缺唯一鍵,或帶了 schema 外的欄位。**不靜默丟棄** ——
            靜默丟欄會讓下游以為欄位從來不存在。
    """
    _rows = [r for r in (rows or []) if r]
    if not _rows:
        return 0
    for r in _rows:
        if not r.get(MACRO_FWD_TEST_KEY):
            raise ValueError(f'append_signals: 列缺唯一鍵 {MACRO_FWD_TEST_KEY!r}:{r}')
        _extra = set(r) - set(MACRO_FWD_TEST_HEADERS)
        if _extra:
            raise ValueError(f'append_signals: schema 外的欄位 {sorted(_extra)}')

    _new = pd.DataFrame(_rows)
    _new[MACRO_FWD_TEST_KEY] = _new[MACRO_FWD_TEST_KEY].astype(str)

    _old = pd.DataFrame(load_signals(path))
    if not _old.empty:
        _old[MACRO_FWD_TEST_KEY] = _old[MACRO_FWD_TEST_KEY].astype(str)
        _dupes = set(_new[MACRO_FWD_TEST_KEY]) & set(_old[MACRO_FWD_TEST_KEY])
        if _dupes:
            # 覆寫必須說出來(§1「任何填補/覆蓋要顯式 + log」)。
            print(f'[macro_fwd_test_store] {len(_dupes)} 個日期已存在,以新列覆蓋'
                  f'(規則可能已改):{sorted(_dupes)[:5]}'
                  f'{" ..." if len(_dupes) > 5 else ""}')
            _old = _old[~_old[MACRO_FWD_TEST_KEY].isin(_dupes)]
        _out = pd.concat([_old, _new], ignore_index=True)
    else:
        _out = _new

    # 欄序固定成 schema 順序;舊檔缺的新欄補 None(不補 0 —— §1)。
    for _c in MACRO_FWD_TEST_HEADERS:
        if _c not in _out.columns:
            _out[_c] = None
    _out = _out[list(MACRO_FWD_TEST_HEADERS)]
    _out = _out.sort_values(MACRO_FWD_TEST_KEY).reset_index(drop=True)

    p = Path(path) if path else MACRO_FWD_TEST_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    _out.to_parquet(p, index=False)
    return len(_new)
