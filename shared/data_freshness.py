# -*- coding: utf-8 -*-
"""shared/data_freshness.py — 資料「新鮮度」SSOT(L0 純函式,v19.170 P0-4)。

═══ 為什麼需要這個模組(稽核發現的真實事故)═══════════════════════════
v19.170 稽核:先行指標的「前五大留倉 / 前十大留倉 / 未平倉口數」三欄,自 7/21 到
7/31 **連續 9 個交易日數值完全不變**(FinMind 免費版無此資料 + stale pickle 天天
沿用),但 🔎 資料診斷頁的覆蓋率表仍顯示「🟢 3/3 完整」。

根因是覆蓋率表的判定只問「這個 key 有沒有值(is not None)」——
    **覆蓋率(coverage)≠ 新鮮度(freshness)**
一個從 9 天前凍結至今的數字,覆蓋率永遠 100%,但它對「今天該不該進場」毫無資訊量,
甚至有害(user 會以為外資留倉沒變化 = 盤勢穩定,實際是資料管線壞了)。

因此本模組補上覆蓋率查不到的兩個維度:
1. `detect_frozen_columns` — **值凍結偵測**:欄位有值,但一階差分連續 N 期為 0。
2. `freshness_level` / `staleness_badge_html` — **落後天數的燈號與呈現**。

═══ 與 shared/staleness.py 的分工(避免 SSOT 打架)═══════════════════
- `shared/staleness.py`:算「資料最新日期 vs 預期最新交易日」差幾天(日期維度),
  並提供即時決策閘 `gate_for_realtime`。**日期層面的 SSOT 在那邊,本檔不重複實作。**
- `shared/data_freshness.py`(本檔):
  (a) 值維度 —— 日期看起來很新,但數值其實是死的(本次事故正是這種);
  (b) 呈現層 —— 把 lag_days 翻成 emoji / label / badge HTML 供各 UI 共用。
  `freshness_level(lag_days=...)` 的 lag_days 可直接吃 `staleness.staleness_days()`
  的回傳值,兩者串接使用。

§8.2 分層:L0 Infra —— **不得 import streamlit**(本檔僅 pandas,且延遲於函式內
import,確保純算力/純字串組裝,可單測、可被任一層 import)。
§1 Fail Loud:無法判定一律回「未知(⬜/None)」,不假裝新鮮,也不假裝凍結。
"""
from __future__ import annotations

from typing import Iterable, Optional

# 呈現層預設色票(對齊 shared/colors 的紅綠燈 SSOT)
from shared.colors import (
    TRAFFIC_GREEN as _C_GREEN,
    TRAFFIC_NEUTRAL as _C_IDLE,
    TRAFFIC_RED as _C_RED,
    TRAFFIC_YELLOW as _C_YELLOW,
)

# 預設燈號 → 色票對照(呼叫端可用 color_map 覆寫)
_DEFAULT_COLOR_MAP = {
    "🟢": _C_GREEN,
    "🟡": _C_YELLOW,
    "🔴": _C_RED,
    "⬜": _C_IDLE,
}


def detect_frozen_columns(
    df,
    cols: Iterable[str],
    *,
    stale_periods: int = 3,
    tol: float = 1e-9,
) -> dict[str, dict]:
    """偵測「有值但數值凍結」的欄位(向量化,無逐列 for 迴圈)。

    Parameters
    ----------
    df : pd.DataFrame
        時序資料,**列須已依時間由舊到新排序**(本函式不重排,避免誤判 caller 的
        排序意圖;順序錯 → 尾端 N 期就不是最近 N 期)。
    cols : Iterable[str]
        要檢查的欄位名。不存在 / 全非數值的欄位不會拋例外,而是回
        `frozen=False, flat_ratio=0.0, last_change_idx=None`(§1:不確定 ≠ 凍結)。
    stale_periods : int
        判定凍結所需的「連續無變化期數」,預設 3(以日頻資料 = 3 個交易日)。
    tol : float
        一階差分絕對值的容忍值,預設 1e-9(浮點雜訊)。

    Returns
    -------
    dict[str, dict]
        `{欄名: {'frozen': bool, 'flat_ratio': float, 'last_change_idx': Any|None}}`
        - `frozen`         最後 `stale_periods` 期的 |diff| **全部有效且全 ≤ tol**
        - `flat_ratio`     全期中 |diff| ≤ tol 的比例(分母 = 有效 diff 數,非總列數)
        - `last_change_idx` 最後一次真正變動那列的 index label;從未變動 → None

    Notes
    -----
    - **NaN 不算凍結**:diff 為 NaN 代表「不知道有沒有變」,`NaN <= tol` 在 pandas
      為 False,故不會灌水成 frozen;同時 NaN 也不計入 flat_ratio 分母。
      這是刻意的 —— 資料缺失要顯示成缺失,不能被包裝成「穩定」。
    - 列數不足(有效 diff < stale_periods)→ `frozen=False`(樣本不足不下結論)。
    - 複雜度 O(n×m)(n 列 m 欄),單次 `diff()` 向量化完成;僅對「欄」做迴圈
      (欄數為個位數),**無逐列 Python 迴圈**。
    """
    import pandas as _pd

    _cols = list(cols)
    _out: dict[str, dict] = {}
    _blank = {"frozen": False, "flat_ratio": 0.0, "last_change_idx": None}

    if df is None or _cols == [] or getattr(df, "empty", True):
        return {c: dict(_blank) for c in _cols}

    _df_cols = list(getattr(df, "columns", []))
    _have: list[str] = []
    for c in _cols:                      # 保序去重(重複欄名會讓 df[c] 回 DataFrame)
        if c in _df_cols and c not in _have:
            _have.append(c)
    for c in _cols:
        if c not in _df_cols:
            # §1 Fail Loud:缺欄要出聲,但不炸掉整個診斷頁
            print(f"[freshness] ⚠️ 欄位不存在,跳過凍結偵測: {c}")
            _out[c] = dict(_blank)
    if not _have:
        return {c: _out.get(c, dict(_blank)) for c in _cols}

    # ── 向量化核心:一次 diff() 算完所有欄 ──────────────────────
    # to_numeric(errors='coerce') 而非硬 astype(float):混入 '-' / '' 的欄位
    # 直接 astype 會 ValueError 炸掉整張診斷表;coerce 成 NaN 後由上述 NaN 規則
    # 處理(不知道 → 不判凍結),語意正確且不吞例外。
    try:
        _num = df[_have].apply(_pd.to_numeric, errors="coerce").astype(float)
    except Exception as _e_num:  # noqa: BLE001 — 診斷用途,不可反噬呼叫端
        # 出聲但不假裝有結論(§1:不確定 ≠ 凍結,回 blank 而非 frozen=True)
        print(f"[freshness] ⚠️ 欄位無法轉數值,跳過凍結偵測: "
              f"{type(_e_num).__name__}: {_e_num}")
        return {c: _out.get(c, dict(_blank)) for c in _cols}
    _diff = _num.diff().abs()
    _flat = _diff.le(tol)          # NaN <= tol → False(NaN 不算持平)
    _valid = _diff.notna()

    _n_flat = _flat.sum()
    _n_valid = _valid.sum()
    _tail_flat = _flat.iloc[-stale_periods:] if stale_periods > 0 else _flat.iloc[0:0]
    _tail_valid = _valid.iloc[-stale_periods:] if stale_periods > 0 else _valid.iloc[0:0]
    _changed = _valid & (~_flat)   # 真正變動過的位置

    for c in _have:
        _vn = int(_n_valid[c])
        _frozen = bool(
            stale_periods > 0
            and _vn >= stale_periods
            and len(_tail_flat) == stale_periods
            and bool(_tail_valid[c].all())
            and bool(_tail_flat[c].all())
        )
        _ratio = float(_n_flat[c]) / _vn if _vn else 0.0
        _chg_col = _changed[c]
        _last_idx = _chg_col[_chg_col].index[-1] if bool(_chg_col.any()) else None
        _out[c] = {
            "frozen": _frozen,
            "flat_ratio": round(_ratio, 4),
            "last_change_idx": _last_idx,
        }
    # 依 caller 傳入順序回傳
    return {c: _out.get(c, dict(_blank)) for c in _cols}


def freshness_level(
    lag_days: Optional[int],
    *,
    warn: int = 1,
    bad: int = 3,
) -> tuple[str, str]:
    """把「落後天數」翻成 (emoji, label) 燈號。

    Parameters
    ----------
    lag_days : int | None
        資料落後天數(可直接吃 `shared.staleness.staleness_days()` 回傳值)。
        None = 無法判定(缺日期欄 / 空資料)。
    warn : int
        ≤ warn 視為當日(綠燈),預設 1(容忍收盤前一日的自然延遲)。
    bad : int
        ≤ bad 視為警告(黃燈),超過即紅燈,預設 3(≈ 一個週末 + 一天)。

    Returns
    -------
    tuple[str, str]
        `('⬜','未知')` / `('🟢','當日')` / `('🟡','落後N日')` / `('🔴','落後N日')`

    §1 Fail Loud:`None` 明確回「未知」灰燈,**不**樂觀當成當日 —— 不知道新不新鮮
    本身就是要讓 user 看見的資訊。
    """
    if lag_days is None:
        return ("⬜", "未知")
    try:
        _lag = int(lag_days)
    except (TypeError, ValueError):
        return ("⬜", "未知")
    if _lag <= warn:
        return ("🟢", "當日")
    if _lag <= bad:
        return ("🟡", f"落後{_lag}日")
    return ("🔴", f"落後{_lag}日")


def staleness_badge_html(
    level_emoji: str,
    label: str,
    *,
    color_map: Optional[dict] = None,
) -> str:
    """組一段 inline-style 的 `<span>` 徽章字串(純字串組裝,不碰 streamlit)。

    Parameters
    ----------
    level_emoji : str
        `freshness_level()` 回傳的 emoji(🟢/🟡/🔴/⬜)。
    label : str
        顯示文字(如「當日」「落後9日」)。
    color_map : dict | None
        `{emoji: hex}` 覆寫;None → `_DEFAULT_COLOR_MAP`(對齊 shared.colors)。

    Returns
    -------
    str
        例:`<span style="...">🟡 落後9日</span>`。呼叫端自行決定要不要
        `unsafe_allow_html=True`(本檔為 L0,不得也不會呼叫 streamlit)。

    Notes
    -----
    label 會做最小化 HTML 逸出(`& < >`),避免上游字串意外破版/注入。
    """
    _cm = color_map or _DEFAULT_COLOR_MAP
    _color = _cm.get(level_emoji, _DEFAULT_COLOR_MAP["⬜"])
    _safe = (str(label).replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;"))
    _style = (
        f"display:inline-block;padding:1px 6px;border-radius:4px;"
        f"font-size:10px;font-weight:600;line-height:1.5;"
        f"color:{_color};border:1px solid {_color}66;background:{_color}1a;"
    )
    return f'<span style="{_style}">{level_emoji} {_safe}</span>'


def frozen_summary(result: dict[str, dict]) -> tuple[int, list]:
    """把 `detect_frozen_columns` 的結果壓成 (凍結欄數, 凍結欄名 list)。

    給 UI 一行摘要用(如「3 欄資料凍結:前五大留倉/前十大留倉/未平倉口數」),
    避免各呼叫端各自 for 迴圈統計而漂移。
    """
    _frozen = [c for c, v in (result or {}).items() if v and v.get("frozen")]
    return (len(_frozen), _frozen)


def _emoji_worse(a: str, b: str) -> str:
    """回兩個燈號中「較差」的那個(⬜ 視為最不確定,排在綠之後)。

    供覆蓋率表這類「覆蓋率燈號 × 新鮮度燈號」需取交集降級的場景使用,
    避免各處自己寫 if/else 導致降級規則不一致。
    """
    _rank = {"🟢": 0, "⬜": 1, "🟡": 2, "🔴": 3}
    return a if _rank.get(a, 1) >= _rank.get(b, 1) else b
