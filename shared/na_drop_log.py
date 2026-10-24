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
3. **不拋例外**：筆數算不出來 ⇒ 整句略過；日期樣本算不出來 ⇒ 筆數照印、樣本改印「取不到」。取數流程不受影響。

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


def na_drop_note(before: Any, after: Any, *, tag: str, series: str,
                 subset: Optional[Sequence[str]] = None,
                 date_col: Optional[str] = None) -> Optional[str]:
    """回 log 句子；被清 0 筆（或筆數算不出來）→ None。**絕不拋例外。**

    Args:
        before / after: dropna 前、後的 DataFrame 或 Series（同一份資料）。
        tag: 前綴 `[tag]`，慣例 '模組/函式'。
        series: ticker／序列名（顯示用）。
        subset: dropna 的 `subset`（DataFrame 時用；None ＝ 全欄 any，Series 不用）。
        date_col: 日期在欄位裡（不是 index）時給欄名；None ＝ 取 index。
    """
    try:
        _n = _row_count(before) - _row_count(after)
    except Exception:   # noqa: BLE001 — 筆數算不出來 ⇒ 不知道有沒有清，不印（不猜）
        return None
    if _n <= 0:
        return None
    _head = f"[{tag}] ⚠️ 缺值清理：{series} 清掉 {_n} 筆收盤為空值的列"
    try:
        _mask = _dropped_mask(before, subset)
        _dates = _row_dates(before, date_col)
        _gone = [d for d, m in zip(_dates, _mask) if m]
        try:
            _latest = max(_dates)
            _has_last = any(d == _latest for d in _gone)
        except Exception:   # noqa: BLE001 — 日期不可比較 ⇒ 退回「最後一列」
            _has_last = bool(_mask[-1]) if _mask else False
        _sample = "、".join(_fmt_date(d) for d in _gone[:NA_DROP_SAMPLE_N])
        _more = f" …（共 {len(_gone)} 筆）" if len(_gone) > NA_DROP_SAMPLE_N else ""
        return (f"{_head}（日期樣本：{_sample}{_more}；"
                f"含最新一根：{'是' if _has_last else '否'}）")
    except Exception as _e:   # noqa: BLE001 — 只影響樣本，筆數照印
        return f"{_head}（日期樣本取不到：{type(_e).__name__}）"


def log_na_drop(before: Any, after: Any, *, tag: str, series: str,
                subset: Optional[Sequence[str]] = None,
                date_col: Optional[str] = None) -> None:
    """`na_drop_note` 有句子才 print（stdout）；被清 0 筆不印任何字元。

    `na_drop_note` 不拋例外；`print` 本身與檔內其他既有 print 同等級（不另包 try，避免 `except: pass`）。
    """
    _msg = na_drop_note(before, after, tag=tag, series=series,
                        subset=subset, date_col=date_col)
    if _msg:
        print(_msg)
