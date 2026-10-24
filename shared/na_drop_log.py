"""shared/na_drop_log.py — 缺值清理（dropna）筆數 log 的共用 helper（L0 Infra）。

DEC-077 第 2 點／BACKLOG `DH-C1-NA-DROP-LOG`（C1，客戶 2026-10-24）：
C1 只增加「我們知道清掉多少缺值」的能力 —— **純觀測、零投資輸出變更**。

為什麼要有這支
--------------
CLAUDE.md §3.3「`fillna` / `ffill` / `dropna` 必須顯式呼叫 + log 受影響筆數」。
既有幾處 production 取數路徑（^TWII／^VIX 收盤、Yahoo 收盤序列…）`dropna` 之後沒有任何紀錄：
上游某天收盤是 null 被默默清掉，下游看到的只是「少一根 K 棒」，沒人知道。

契約（呼叫端只需遵守這三條）
----------------------------
1. **dropna 照原寫法先做完**，再把「清理前那個物件」與「清理後那個物件」交給
   `log_na_drop`；本函式**不改**任何傳入物件、**不回傳**東西給呼叫端用。
2. **只在被清筆數 > 0 時才 print**（被清 0 筆時 stdout 一個字元都不多 —— 多個既有測試比對 stdout 全文）。
3. **不因 log 改變取數回傳**（逐條對照實際行為）：
   - 筆數算不出來 ⇒ 印一行「筆數取不到」；日期樣本算不出來 ⇒ 筆數照印、樣本改印「取不到」；
   - stdout 非 UTF-8 ⇒ 改印 ASCII 跳脫版；
   - stdout 為 None（fd 1 關閉）、已關閉、broken pipe，或 write 拋任何其他 `Exception`（例：RuntimeError
     reentrant call、TypeError）⇒ 改寫 `sys.__stderr__`（ASCII 跳脫版，後者附註 stdout 的例外型別）；
   - stderr 也寫不出去（`sys.__stderr__` 為 None，或寫入拋 OSError／ValueError）⇒ 放棄這一行（唯一放棄點）。
   ⚠️ 據實揭露兩個**不**攔的情形：(a) `sys.__stderr__` 寫入拋 OSError／ValueError **以外**的例外會往外拋
   （總管規格：stderr 端不擴大成 `except Exception`）；(b) `BaseException`（KeyboardInterrupt／SystemExit）
   一律不攔。除此之外本模組不拋例外。

⛔ 不寫 `ADL_LOG_PATH`（`_alog`）—— UI 會讀那個檔顯示；本 log 走 stdout（寫不出去時才走 `sys.__stderr__`）。
§8.2：L0，零 import（純 duck typing，不 import pandas）。
"""
from __future__ import annotations

import sys
from typing import Any, Optional, Sequence

#: 日期樣本最多列幾個（其餘以「…」表示）。
NA_DROP_SAMPLE_N: int = 5


def _row_count(x: Any) -> int:
    return len(x)


def _dropped_mask(before: Any, subset: Optional[Sequence[str]]) -> list:
    """與 `dropna` 同一判準重算「哪幾列被清掉」（只供 log 用）。"""
    if hasattr(before, "columns"):          # DataFrame：dropna(subset=…) 或全欄 any
        _part = before[list(subset)] if subset else before
        return [bool(v) for v in _part.isna().any(axis=1).tolist()]
    return [bool(v) for v in before.isna().tolist()]   # Series：dropna()


def _row_dates(before: Any, date_col: Optional[str]) -> list:
    if date_col is not None:
        return list(before[date_col].tolist())
    return list(before.index)


def _fmt_date(d: Any) -> str:
    return str(d)[:10]


def _is_missing_date(d: Any) -> bool:
    """None／NaN／NaT／pd.NA ⇒ True（自比不相等、或連比較都做不了的都算缺）。L0 不 import pandas。"""
    if d is None:
        return True
    try:
        return bool(d != d)
    except Exception:   # noqa: BLE001 — pd.NA 之類 `!=` 回傳不可轉 bool ⇒ 視為缺值（只影響「含最新一根」）
        return True


def _latest_flag(dates: list, gone: list) -> str:
    """被清掉的列裡有沒有「最新那一根」：'是'／'否'／'未知'。

    最新一根只在**非缺值、可互相比較**的日期上取 max；取不到（全缺、型別混雜不可比）⇒ '未知'，
    ⛔ 不退回看實體末列（末列不一定是最新日期，也可能本身就是 NaT）。
    """
    try:
        _valid = [d for d in dates if not _is_missing_date(d)]
        if not _valid:
            return "未知"
        _latest = max(_valid)
        return "是" if any((not _is_missing_date(g)) and bool(g == _latest) for g in gone) else "否"
    except Exception:   # noqa: BLE001 — 不可比較 ⇒ 未知（說出來，不猜）
        return "未知"


def _to_stderr(ascii_msg: str) -> None:
    """stdout 不能寫時的備援出口：寫到 `sys.__stderr__`（ASCII 跳脫版，避免再撞編碼）。

    刻意用 `sys.__stderr__`（行程原始 stderr）而非可能被轉向的 `sys.stderr`，取捨見 `_safe_print`。
    """
    _err = sys.__stderr__
    if _err is None:
        # 沒有 stderr（例：pythonw）＝沒有可出聲的管道 ⇒ 放棄這行 log（理由同下）。
        return
    try:
        _err.write(ascii_msg + "\n")
        _err.flush()
    except (OSError, ValueError):
        # ⚠️ 本模組**唯一**允許的放棄點（C1 第三輪，總管規格）：log 是純觀測，⛔ 不得改變取數函式的回傳；
        #   stdout 與 stderr 都寫不出去（已關閉／broken pipe）時已沒有任何可出聲的管道，只能放棄這一行。
        #   只攔 OSError／ValueError（關閉的檔、broken pipe），⛔ 不擴大成 `except Exception`。
        return


def _safe_print(msg: str) -> None:
    """print 到 stdout；stdout 寫不出去時改寫 `sys.__stderr__`。log 不得改變取數函式的回傳。

    逐條對照實際行為：
    - `sys.stdout is None`（fd 1 關閉時 Python 會這樣設；此時 `print` 會**無聲丟棄**）⇒ 直接寫 stderr；
    - stdout 不是 UTF-8（例：`PYTHONIOENCODING=ascii`、Windows cp950 主控台）⇒ `print` 拋 UnicodeEncodeError
      ⇒ 改印 ASCII 跳脫版（`\\uXXXX`）；這次再失敗（例：ascii 編碼 ＋ `| head` 的 broken pipe）⇒ 寫 stderr；
    - stdout 已關閉（ValueError）或 broken pipe（BrokenPipeError ⊂ OSError）⇒ 寫 stderr；
    - stdout 的 write 拋其他 `Exception`（例：RuntimeError reentrant call、TypeError）⇒ 寫 stderr，
      句尾附 `(stdout <例外型別>)`；
    - stderr 也寫不出去 ⇒ 見 `_to_stderr`（唯一放棄點；該處只攔 OSError／ValueError，其餘照拋）。
    ⚠️ UnicodeEncodeError 是 ValueError 的子類 ⇒ 必須先攔它（順序不可對調）。

    為什麼備援寫 `sys.__stderr__` 而不是 `sys.stderr`：`sys.stderr` 常被轉向（pytest capture、Streamlit、
    其他 redirect），而 stdout 會寫不出去的情境多半正是「整個 I/O 管道被動過」；直接寫行程原始的 stderr
    最有機會真的出聲。代價是它**繞過**被轉向的 `sys.stderr` —— 那些框架的 capture／畫面不會收到這行
    （例：pytest 的 capsys 看不到）。取捨：這只發生在 stdout 已經寫不出去的少見情境，讓訊息能在行程層級
    （終端機、cron／CI log）被看到，比留在一個可能同樣失效的轉向目標更重要。
    """
    _ascii = msg.encode("ascii", "backslashreplace").decode("ascii")
    if sys.stdout is None:
        _to_stderr(_ascii)
        return
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(_ascii)
        except (OSError, ValueError):
            _to_stderr(_ascii)
        except Exception as _e:  # noqa: BLE001 — 理由同下方外層同名分支（有出聲到 stderr，不是吞例外）
            _to_stderr(_ascii + f" (stdout {type(_e).__name__})")
    except (OSError, ValueError):
        _to_stderr(_ascii)
    except Exception as _e:  # noqa: BLE001
        # log 屬純觀測，⛔ 不得改變取數函式的回傳（例外往外拋會被取數函式的 except 吃成失敗、或直接中斷）；
        # 這裡**有出聲**（寫到 stderr，並附 stdout 的例外型別），所以不是吞例外。
        _to_stderr(_ascii + f" (stdout {type(_e).__name__})")


def na_drop_note(before: Any, after: Any, *, tag: str, series: str,
                 subset: Optional[Sequence[str]] = None,
                 date_col: Optional[str] = None) -> Optional[str]:
    """回 log 句子；被清 0 筆（或筆數算不出來）→ None。不拋例外（唯二例外見模組 docstring 契約 3 的 (a)(b)）。

    筆數算不出來時**印一行**「[tag] 缺值清理筆數取不到（型別名）」再回 None（⛔ 不沉默）。

    Args:
        before / after: dropna 前、後的 DataFrame 或 Series（同一份資料）。
        tag: 前綴 `[tag]`，慣例 '模組/函式'。
        series: ticker／序列名（顯示用）。
        subset: dropna 的 `subset`（DataFrame 時用；None ＝ 全欄 any，Series 不用）。
        date_col: 日期在欄位裡（不是 index）時給欄名；None ＝ 取 index。
    """
    try:
        _n = _row_count(before) - _row_count(after)
    except Exception as _e:   # noqa: BLE001 — 筆數算不出來 ⇒ 不知道有沒有清：說出來，不猜
        _safe_print(f"[{tag}] 缺值清理筆數取不到（{type(_e).__name__}）")
        return None
    if _n <= 0:
        return None
    _head = f"[{tag}] ⚠️ 缺值清理：{series} 清掉 {_n} 筆收盤為空值的列"
    try:
        _mask = _dropped_mask(before, subset)
        _dates = _row_dates(before, date_col)
        _gone = [d for d, m in zip(_dates, _mask) if m]
        if len(_gone) != _n:
            # 重算判準與實際 dropna 不一致（例：subset 傳錯）⇒ 樣本不可信，⛔ 不印一份對不上的日期。
            return f"{_head}（日期樣本與筆數不一致（重算 {len(_gone)} 筆）；含最新一根：未知）"
        _sample = "、".join(_fmt_date(d) for d in _gone[:NA_DROP_SAMPLE_N])
        _more = f" …（共 {len(_gone)} 筆）" if len(_gone) > NA_DROP_SAMPLE_N else ""
        return (f"{_head}（日期樣本：{_sample}{_more}；"
                f"含最新一根：{_latest_flag(_dates, _gone)}）")
    except Exception as _e:   # noqa: BLE001 — 只影響樣本，筆數照印
        return f"{_head}（日期樣本取不到：{type(_e).__name__}）"


def log_na_drop(before: Any, after: Any, *, tag: str, series: str,
                subset: Optional[Sequence[str]] = None,
                date_col: Optional[str] = None) -> None:
    """`na_drop_note` 有句子才 print（stdout）；被清 0 筆不印任何字元。

    print 走 `_safe_print`：stdout 寫不出去時改寫 `sys.__stderr__`，不因 log 改變呼叫端回傳
    （逐條行為與唯二不攔的情形見模組 docstring 契約 3）。
    """
    _msg = na_drop_note(before, after, tag=tag, series=series,
                        subset=subset, date_col=date_col)
    if _msg:
        _safe_print(_msg)
