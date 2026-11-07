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

import numpy as np
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


class LedgerWriteError(RuntimeError):
    """寫入新帳本失敗(寫暫存檔 / fsync / 驗證 / replace)。**正式檔位元組完全不變**,暫存檔已清。"""


def _is_null(v) -> bool:
    return v is None or (pd.api.types.is_scalar(v) and bool(pd.isna(v)))


def _value_category(v) -> str:
    if isinstance(v, (bool, np.bool_)):
        return 'bool'
    if isinstance(v, (int, np.integer)):
        return 'int'
    if isinstance(v, (float, np.floating)):
        return 'float'
    if isinstance(v, str):
        return 'str'
    return type(v).__name__


def _verify_roundtrip(chk: pd.DataFrame, df: pd.DataFrame) -> None:
    """讀回的暫存檔必須與準備寫入的 `df` **逐格精確相等**,否則 raise ValueError。

    比「逐格相等」更嚴的三層(都不允許容差 —— 帳本是凍結紀錄,任何位元級漂移都是損壞):
      1. 列數 / 欄位集合與順序 / 唯一鍵集合一致。
      2. 型別不可互換:非 object 欄的 dtype kind 必須相同(bool/int/float 不可互換);
         每個非空格子的型別類別(bool / int / float / str)必須相同
         (bool→int、int→float 都會被擋)。
      3. 數值 `assert_frame_equal(check_exact=True)`:無 rtol/atol(預設 rtol=1e-5 會放行
         ≤9e-6 相對偏移、0.0→1e-9、float32 截斷、四捨五入)。
    **唯一的良性差異白名單**(以真實帳本往返實測決定):
      (a) None ↔ NaN 視為同為「空值」(arrow 字串欄讀回會把 None 變 NaN);
      (b) df 端為 object 欄(含全 None、或 None 與數值混合)時,讀回 dtype 可能變
          float64 / str —— 不比 dtype kind,但**逐格型別類別與值仍須完全一致**。
    """
    if len(chk) != len(df):
        raise ValueError(f'列數 {len(chk)} != {len(df)}')
    if list(chk.columns) != list(df.columns):
        raise ValueError(f'欄位 {list(chk.columns)} != {list(df.columns)}')
    if set(chk[MACRO_FWD_TEST_KEY].astype(str)) != set(df[MACRO_FWD_TEST_KEY].astype(str)):
        raise ValueError('唯一鍵集合不一致')
    a = df.reset_index(drop=True)
    b = chk.reset_index(drop=True)
    for c in a.columns:
        ka, kb = a[c].dtype.kind, b[c].dtype.kind
        if ka in 'biufcM' and ka != kb:
            raise ValueError(f'欄 {c!r} dtype kind 不一致:{a[c].dtype} → {b[c].dtype}')
        for i, (x, y) in enumerate(zip(a[c].tolist(), b[c].tolist())):
            nx, ny = _is_null(x), _is_null(y)
            if nx != ny:
                raise ValueError(f'欄 {c!r} 第 {i} 列空值不一致:{x!r} → {y!r}')
            if not nx and _value_category(x) != _value_category(y):
                raise ValueError(f'欄 {c!r} 第 {i} 列型別改變:{type(x).__name__} → {type(y).__name__}')

    def _norm(x: pd.DataFrame) -> pd.DataFrame:
        # 只把非數值欄(字串 / object)轉 object 並讓 None≡NaN;bool/int/float 欄保持原生 dtype,
        # 使 `check_exact=True` 真正作用在浮點數上(若全轉 object,容差參數就形同虛設)。
        x = x.copy()
        for col in x.columns:
            if x[col].dtype.kind not in 'biuf':
                s = x[col].astype(object)
                x[col] = s.where(s.notna(), None)
        return x
    from pandas.testing import assert_frame_equal
    assert_frame_equal(_norm(b), _norm(a), check_dtype=False, check_exact=True)


def _atomic_write_parquet(df: pd.DataFrame, target: Path) -> None:
    """原子寫入:同目錄暫存檔 → fsync → 讀回驗證 → `os.replace` → (POSIX)fsync 父目錄。

    為什麼這樣做:舊版直接 `df.to_parquet(正式路徑)`,寫到一半失敗(磁碟滿 / 被中斷)
    會留下半個 parquet,而帳本是唯一的無 lookahead 樣本 → 歷史被毀(§1)。
    `os.replace` 在同一檔案系統內是原子的:讀者永遠只看到「完整舊檔」或「完整新檔」。

    - 目標先 `realpath` 解 symlink:維持既有行為(寫到 symlink 指向的檔、symlink 本身保留)。
    - 暫存檔 `.{name}.{pid}.<random>.tmp` 與目標**同目錄**(跨檔案系統 replace 不原子)。
    - 驗證失敗 / 任何例外 → `finally` 刪暫存檔,正式檔不動,丟 `LedgerWriteError`(`__cause__` 保留)。
    - 權限:目標已存在 → `copymode` 沿用舊檔權限;首次建檔 → 0o644(mkstemp 預設 0o600,
      與一般 `to_parquet` 新檔在 umask 022 下的 0o644 對齊)。

    殘留風險(寫在這裡以免被讀成「已完全無風險」):
    - 行程被 SIGKILL / 斷電時 `finally` 不會跑 → 可能殘留 `.signals.parquet.*.tmp` 孤兒
      (**不影響正式檔**,但目前未被 .gitignore 忽略;見 BACKLOG `P0-FWD-STORE-ATOMIC-WRITE`)。
    - 目錄 fsync 是 best-effort:Windows 無法對目錄 fsync(`os.name == 'nt'` 略過),
      斷電後「replace 是否已落盤」在 Windows 上沒有保證。
    - 並行 append 無鎖:兩個行程同時 read-modify-write 仍可能互相蓋掉對方的新列
      (不會損壞檔案,但會丟一列)。cron 為單一行程,故本批不處理。
    """
    import shutil
    import tempfile

    real = Path(os.path.realpath(target))
    real.parent.mkdir(parents=True, exist_ok=True)
    tmp: Optional[str] = None
    try:
        # 唯讀帳本:舊版 `to_parquet` 會 PermissionError 拒寫,但 `os.replace` 只看目錄權限、會繞過
        # 檔案權限靜默替換 → 在建暫存檔**之前**顯式拒絕,維持原行為。
        # (root 下 `os.access` 恆真,屬已知限制:root 本來就能寫任何檔。)
        if real.exists() and not os.access(real, os.W_OK):
            raise LedgerWriteError(
                f'[macro_fwd_test_store] 帳本唯讀，已拒絕寫入 {real} —— 未建暫存檔、原檔位元組不變')
        try:
            fd, tmp = tempfile.mkstemp(dir=str(real.parent), prefix=f'.{real.name}.{os.getpid()}.',
                                       suffix='.tmp')
            try:
                f = os.fdopen(fd, 'wb')
            except BaseException:
                os.close(fd)
                raise
            with f:
                df.to_parquet(f, index=False)
                f.flush()
                os.fsync(f.fileno())
            if real.exists():
                shutil.copymode(real, tmp)
            else:
                os.chmod(tmp, 0o644)
        except Exception as e:  # noqa: BLE001 — 包成明確例外,保留 __cause__
            raise LedgerWriteError(
                f'[macro_fwd_test_store] 寫入暫存檔失敗 {real}: {type(e).__name__}: {e} '
                f'—— 未替換正式檔(原檔位元組不變)') from e
        try:
            chk = pd.read_parquet(tmp)
            _verify_roundtrip(chk, df)
        except Exception as e:  # noqa: BLE001
            raise LedgerWriteError(
                f'[macro_fwd_test_store] 新檔驗證失敗 {real}: {type(e).__name__}: {e} '
                f'—— 未替換正式檔(原檔位元組不變)') from e
        try:
            os.replace(tmp, real)
        except Exception as e:  # noqa: BLE001
            raise LedgerWriteError(
                f'[macro_fwd_test_store] os.replace 失敗 {real}: {type(e).__name__}: {e} '
                f'—— 未替換正式檔(原檔位元組不變)') from e
        tmp = None  # 已成為正式檔,不可再刪
        # 目錄 fsync:讓 rename 本身落盤。Windows 無法開目錄做 fsync → 略過;失敗不回頭
        # (replace 已完成,正式檔已是完整新檔),只 log。
        if os.name != 'nt':
            try:
                dfd = os.open(str(real.parent), os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except OSError as e:
                print(f'[macro_fwd_test_store] ⚠️ 父目錄 fsync 失敗(best-effort,已 replace){real.parent}: '
                      f'{type(e).__name__}: {e}')
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
            except OSError as e:  # 不吞原例外:只 log 孤兒位置
                print(f'[macro_fwd_test_store] ⚠️ 暫存檔清理失敗(請人工刪除){tmp}: '
                      f'{type(e).__name__}: {e}')


def append_signals(rows: list[dict], path: Optional[Path] = None) -> int:
    """append 快照列,回「本次**實際新寫入**的列數」。

    同 `date` 已存在 → 保留既有那筆、跳過新列並 log(見模組 docstring);
    全部被跳過時不重寫檔案、不建暫存檔、回 0。寫入為原子(見 `_atomic_write_parquet`)。

    Raises:
        LedgerWriteError: 新檔寫入 / 驗證 / replace 失敗 → 正式檔不變、暫存檔已清。
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
    _atomic_write_parquet(_out, p)
    return len(_new)
