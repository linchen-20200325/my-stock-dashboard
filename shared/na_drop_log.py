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
3. **不拋例外**：筆數算不出來 ⇒ 印一行「筆數取不到」；日期樣本算不出來 ⇒ 筆數照印、樣本改印「取不到」；
   stdout 非 UTF-8 ⇒ 改印 ASCII 跳脫版。取數流程（回傳值）不受影響。

⛔ 不寫 `ADL_LOG_PATH`（`_alog`）—— UI 會讀那個檔顯示；本 log 只走 stdout。
§8.2：L0，零 import（純 duck typing，不 import pandas）。
"""
from __future__ import annotations

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


def _safe_print(msg: str) -> None:
    """print 到 stdout；stdout 不是 UTF-8（例：`PYTHONIOENCODING=ascii`、Windows cp950 主控台）時
    原樣 print 會拋 UnicodeEncodeError —— 那會讓「只是記 log」改變取數函式的回傳（被外層 except 吃成失敗）。
    故只攔 UnicodeEncodeError，改印 ASCII 跳脫版（`\\uXXXX`），訊息仍完整出聲；⛔ 不吞成沉默。
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "backslashreplace").decode("ascii"))


def na_drop_note(before: Any, after: Any, *, tag: str, series: str,
                 subset: Optional[Sequence[str]] = None,
                 date_col: Optional[str] = None) -> Optional[str]:
    """回 log 句子；被清 0 筆（或筆數算不出來）→ None。**不拋例外。**

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

    `na_drop_note` 不拋例外；print 走 `_safe_print`（非 UTF-8 stdout 改印 ASCII 跳脫版，不拋、不沉默）。
    """
    _msg = na_drop_note(before, after, tag=tag, series=series,
                        subset=subset, date_col=date_col)
    if _msg:
        _safe_print(_msg)
