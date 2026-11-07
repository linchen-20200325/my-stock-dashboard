"""src/data/macro/macro_fwd_test_store.py — 總經燈號快照「本地落地」(L1 Data)。

職責一句話:把 `macro_forward_test.build_signal_row` 產出的列 append 進
git 追蹤的 parquet;純檔案 I/O,無業務邏輯、無 streamlit。

路徑 SSOT 在 L0 `shared.macro_forward_test_schema.MACRO_FWD_TEST_RELPATH`。
子目錄是刻意的 —— `.gitignore` 有 `data_cache/*.parquet` 頂層規則,
放子目錄才追蹤得到(同 `data_cache/forward_test/` 手法)。

§5 冪等:同 `date` 已存在 → **保留既有那筆、不覆寫**(2026-10-15 C-2 修正)
-------------------------------------------------------------------------
與 `forward_test_store.append_picks_local`「保留最早一筆」同慣例。

修前是「後寫者勝」,理由是「規則會改、重跑是為了記錄新規則」。實測(C-2)該設計
在 `date` 取「執行當下日期」時會**吃掉真實觀測**:cron 實際延遲到台北午夜後才跑,
同一個 `date` 被隔天另一次跑批覆寫,已有 5 筆真實觀測從 HEAD 消失(仍在 git 史)。
v2 起 `date` = 觀測所屬交易日,一個交易日只有一個市場觀測;帳本是凍結紀錄,
後寫不得蓋前寫。想記錄新規則對同一天的判定 → 另開檔(仍不在同一 date 下堆疊,
否則 precision 統計會把同一天算兩次)。

**為什麼是「最早一筆」**(2026-10-15 總管裁定):同一觀測日的多筆跑批中,
captured_at 最早者最接近該交易日收盤後的觀測;較晚的假日 / 跨日重跑已混入該交易日
**之後**其他腿(廣度 ADL、國際市場等)的變化,不屬於「該交易日的觀測」。
2026-10-15 歷史修復因此排除 3 列(仍在 git 史,列出其首次出現的 commit):
  - captured_at 2026-09-25T22:44:28+08:00 → 觀測日 09-24(f9aea73d)
  - captured_at 2026-09-29T01:48:58+08:00 → 觀測日 09-24(3390328b)
  - captured_at 2026-10-10T00:33:30+08:00 → 觀測日 10-08(2b1b71be)

§8.2 L1:純檔案 I/O。不 import L2(schema 走 L0),不重犯 V-FT-STORE-1。
"""
from __future__ import annotations

import os
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


class LedgerReadError(RuntimeError):
    """帳本檔「已存在」但讀不出來(損壞 / 不可讀 / 非 parquet / 權限 / 欄位無法解析)。

    與「檔不存在」(首次建檔,合法)嚴格區分。丟這個例外 = **fail-closed**:
    呼叫端不得把它當成空帳本繼續寫,否則 `append_signals` 會用「只有新列」的內容
    覆寫掉整本凍結帳本(§1:寧可炸掉,不可造假;帳本是唯一的無 lookahead 樣本)。
    """


def _ledger_error(p: Path, e: BaseException) -> LedgerReadError:
    return LedgerReadError(
        f'[macro_fwd_test_store] 帳本已存在但不可讀 {p}: {type(e).__name__}: {e} '
        f'—— 已 fail-closed,未覆寫、未寫入任何位元組;請人工檢查或自 git 史還原該檔')


def load_signals(path: Optional[Path] = None) -> list[dict]:
    """讀本地快照 → list[dict]。

    - 檔不存在 → [](首次建檔路徑,合法)。
    - 合法 parquet 但 0 列 → [](空帳本)。
    - 檔存在但讀取失敗(0 位元組 / 截斷 / 非 parquet / 目錄 / 權限 / 缺唯一鍵欄)
      → 丟 `LedgerReadError`,**不回 []**。
    """
    p = Path(path) if path else MACRO_FWD_TEST_PATH
    try:
        p.stat()
    except FileNotFoundError as _e:
        if os.path.lexists(p):  # 懸空 symlink:路徑存在但目標讀不到,不是「首次建檔」
            raise _ledger_error(p, _e) from _e
        return []
    except OSError as _e:  # PermissionError / ELOOP / ENOTDIR 等:存在性無法判定
        raise _ledger_error(p, _e) from _e
    if not p.is_file():
        raise _ledger_error(p, IsADirectoryError('路徑存在但不是一般檔案'))
    try:
        df = pd.read_parquet(p)
        if df is None:
            raise ValueError('read_parquet 回傳 None')
        # ⚠️ 不可用 `df.empty`:pandas 對「非零列、零欄」(shape=(n,0))也回 True,會把畸形表當空帳本。
        if len(df) == 0:          # 僅「零列」是合法空帳本(0 列 0 欄 / 0 列有欄)
            return []
        if MACRO_FWD_TEST_KEY not in df.columns:
            raise ValueError(f'缺唯一鍵欄 {MACRO_FWD_TEST_KEY!r},現有欄 {list(df.columns)}')
        return df.to_dict('records')
    except Exception as _e:  # noqa: BLE001 — 不吞:轉成明確的 fail-closed 例外
        raise _ledger_error(p, _e) from _e


def append_signals(rows: list[dict], path: Optional[Path] = None) -> int:
    """append 快照列,回「本次**實際新寫入**的列數」。

    同 `date` 已存在 → 保留既有那筆、跳過新列並 log(見模組 docstring);
    全部被跳過時不重寫檔案、回 0。

    Raises:
        LedgerReadError: 既有帳本存在但讀不出來 → **fail-closed**,不寫入任何位元組
            (讀舊檔發生在任何寫入之前;見 `load_signals`)。
        ValueError: 列缺唯一鍵、同批內唯一鍵重複,或帶了 schema 外的欄位。
            **不靜默丟棄** —— 靜默丟欄會讓下游以為欄位從來不存在。
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
    _batch_dup = _new[MACRO_FWD_TEST_KEY][_new[MACRO_FWD_TEST_KEY].duplicated()]
    if not _batch_dup.empty:
        raise ValueError(f'append_signals: 同批內唯一鍵重複 {sorted(set(_batch_dup))}')

    _old = pd.DataFrame(load_signals(path))
    if not _old.empty:
        _old[MACRO_FWD_TEST_KEY] = _old[MACRO_FWD_TEST_KEY].astype(str)
        _dupes = set(_new[MACRO_FWD_TEST_KEY]) & set(_old[MACRO_FWD_TEST_KEY])
        if _dupes:
            # 跳過必須說出來(§1「任何填補/覆蓋要顯式 + log」)。
            print(f'[macro_fwd_test_store] {len(_dupes)} 個觀測日已存在 → 保留既有列、'
                  f'不覆寫(凍結帳本):{sorted(_dupes)[:5]}'
                  f'{" ..." if len(_dupes) > 5 else ""}')
            _new = _new[~_new[MACRO_FWD_TEST_KEY].isin(_dupes)]
        if _new.empty:
            return 0
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
