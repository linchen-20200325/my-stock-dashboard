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

from typing import Iterable, Optional, Sequence

# 呈現層預設色票(對齊 shared/colors 的紅綠燈 SSOT)
from shared.colors import (
    TRAFFIC_GREEN as _C_GREEN,
    TRAFFIC_NEUTRAL as _C_IDLE,
    TRAFFIC_RED as _C_RED,
    TRAFFIC_YELLOW as _C_YELLOW,
)
# 「合理最舊」天數門檻的 SSOT 在 staleness(頻率感知);本檔只負責翻成燈號,
# **不自己定義天數**(B4-a:診斷頁原本 inline 寫死 1/3 天,與此 SSOT 打架)。
from shared.staleness import stale_days_threshold

# 預設燈號 → 色票對照(呼叫端可用 color_map 覆寫)
_DEFAULT_COLOR_MAP = {
    "🟢": _C_GREEN,
    "🟡": _C_YELLOW,
    "🔴": _C_RED,
    "⬜": _C_IDLE,
}

# 燈號「壞度」排序:綠 < 未知 < 黃 < 紅。
# ⬜ 排在綠之後 —— 「不知道新不新鮮」比「確定很新」差,但比「確定過期」好。
_FRESH_RANK = {"🟢": 0, "⬜": 1, "🟡": 2, "🔴": 3}

# ── 先行指標「值凍結」監看契約 SSOT(E1 v19.185)────────────────────────────
# 為什麼放這裡:`detect_frozen_columns` 是純偵測器,**要看哪幾欄、連續幾期算凍結**
# 是它的輸入契約。原本這份契約只存在於 `src/ui/pages/data_coverage.py` 的私有常數
# `_LI_FROZEN_WATCH_COLS` / `_LI_FROZEN_STALE_PERIODS` / `_LI_DATE_COL`(L5),
# 於是「核心總表」要回答同一個問題(哪幾欄凍結)時,只能自己再寫一份欄位清單 ——
# 兩份清單一漂移,同一份 li_latest 在診斷頁和總表就會給出**互相否定的凍結欄數**。
#
# 收斂方式對齊 `shared/macro_buckets.py` 既有慣例(L0 鏡像 + CI drift test):
#   - 本檔為契約 SSOT;
#   - `data_coverage.py` 的私有副本由 `tests/test_e1_core_summary.py` 的
#     AST drift 守衛釘住(值不相等 → CI 紅燈,並印出該檔實際字面);
#   - 該檔不在本次可改範圍,待其可改時直接 import 本常數即可刪除副本。
FROZEN_WATCH_COLS_LEADING: tuple[str, ...] = (
    "外資", "投信", "自營", "外資大小",
    "前五大留倉", "前十大留倉", "未平倉口數",
)
"""先行指標(li_latest)受值凍結監看的欄位。

刻意**不含**「成交量」(字串 "1234.5億")與「融資/融券餘額」(四捨五入到整數億,
真有可能連續持平)—— 避免製造假紅燈。與 data_coverage 私有副本逐字相同。"""

FROZEN_STALE_PERIODS_LEADING: int = 3
"""連續 N 期一階差分為 0 才判凍結(3 = 3 個交易日 = 4 筆一模一樣的值)。"""

LEADING_DATE_COL: str = "_date"
"""li_latest 的時間欄名。`detect_frozen_columns` 明文要求 caller 先由舊到新排序。"""


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
        ≤ warn 仍算綠燈(可接受的自然延遲),預設 1。
        ⚠️ 綠燈**不等於**落後 0 日 —— label 仍會照實寫「落後N日」,見下方誠實條款。
    bad : int
        ≤ bad 視為警告(黃燈),超過即紅燈,預設 3(≈ 一個週末 + 一天)。
        呼叫端若要頻率感知的 SSOT 門檻,請改用 `freshness_level_for_cadence`。

    Returns
    -------
    tuple[str, str]
        `('⬜','未知')` / `('🟢','最新')` / `('🟢|🟡|🔴','落後N日')`

    §1 Fail Loud:`None` 明確回「未知」灰燈,**不**樂觀當成當日 —— 不知道新不新鮮
    本身就是要讓 user 看見的資訊。

    §1 標籤誠實(B4-a 修):**「最新」只保留給 lag ≤ 0**。原本 `lag <= warn` 一律
    回「當日」,在 warn>0 時等於把「落後 3 日」寫成「當日」—— 燈號寬容是設計選擇,
    把落後天數講成 0 則是說謊。綠燈仍是綠燈,但文字必須照實寫「落後N日」。
    """
    if lag_days is None:
        return ("⬜", "未知")
    try:
        _lag = int(lag_days)
    except (TypeError, ValueError):
        return ("⬜", "未知")
    if _lag <= 0:
        return ("🟢", "最新")
    _label = f"落後{_lag}日"
    if _lag <= warn:
        return ("🟢", _label)
    if _lag <= bad:
        return ("🟡", _label)
    return ("🔴", _label)


def freshness_level_for_cadence(
    lag_days: Optional[int],
    cadence: str = "daily",
    *,
    warn_days: Optional[int] = None,
) -> tuple[str, str]:
    """依「資料發布頻率」取 SSOT 門檻後翻燈號(B4-a 門檻收斂用)。

    Parameters
    ----------
    lag_days : int | None
        `shared.staleness.staleness_days()` 的回傳值(距預期最新交易日的日曆天)。
    cadence : str
        `'daily'` / `'monthly'` / `'quarterly'`。未知 → 退 daily(最嚴)。
    warn_days : int | None
        黃燈起點(日曆天)。None → 與紅燈同門檻(等於沒有黃燈帶,只有「在合理發布
        窗內 / 已逾窗」兩態)。給值時會被 `min(warn_days, bad)` 夾住,避免呼叫端
        設出「黃燈比紅燈還寬」的矛盾組合。

    Returns
    -------
    tuple[str, str]  同 `freshness_level`。

    Why
    ---
    紅燈門檻**一律**取自 `shared.staleness.stale_days_threshold(cadence)`
    (daily=7 / monthly=45 / quarterly=150),不再由各 UI 自己 inline 寫天數。
    月頻指標(CPI / PMI / 出口)的 as_of 天生就是上個月,拿日頻的 7 天去量它
    會永遠紅燈 —— 這是 B4-a 之前診斷頁「總經新鮮度」只好去量抓取時間的原因。
    """
    _bad = stale_days_threshold(cadence)
    _warn = _bad if warn_days is None else min(int(warn_days), _bad)
    return freshness_level(lag_days, warn=_warn, bad=_bad)


def worst_freshness(
    levels: Sequence[Optional[tuple[str, str]]],
) -> tuple[str, str]:
    """回一組 `(emoji, label)` 中**最差**的一組;全空 → `('⬜','未知')`。

    用於「一個 Tab 由多個資料源組成」的場景(如籌碼面 = 三大法人 + 融資 + 廣度 +
    先行指標):整列燈號取最差的那個源,並保留它的 label 供 UI 指名道姓,
    避免「其中一源 9 天沒動,但整列仍綠」這種被平均掉的假訊號(§1)。
    """
    _out: Optional[tuple[str, str]] = None
    for _lv in (levels or ()):
        if not _lv:
            continue
        if _out is None or _FRESH_RANK.get(_lv[0], 1) > _FRESH_RANK.get(_out[0], 1):
            _out = (_lv[0], _lv[1])
    return _out or ("⬜", "未知")


def downgrade_to_warn(emoji: str) -> str:
    """綠燈強制降黃(其餘不動)。供「有值但值可疑」的降級路徑共用。

    §1:凍結 / 沿用舊快取 / stale 旗標 等情況下,覆蓋率再滿也不得亮綠燈;
    但已經是黃/紅/未知的不再往上調(不製造更嚇人的假訊號)。
    """
    return "🟡" if emoji == "🟢" else emoji


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


def leading_frozen_columns(
    df,
    *,
    cols: Optional[Iterable[str]] = None,
    stale_periods: Optional[int] = None,
    date_col: Optional[str] = None,
) -> tuple[int, list]:
    """先行指標值凍結偵測的**單一實作**:排序 → 偵測 → 摘要,回 (凍結欄數, 欄名)。

    Parameters
    ----------
    df : pd.DataFrame | None
        `session_state['li_latest']`。None / 空 / 無受監看欄 → `(0, [])`。
    cols / stale_periods / date_col : 覆寫預設契約(預設走本檔 SSOT 常數)。

    Returns
    -------
    tuple[int, list]
        同 `frozen_summary`。

    Notes
    -----
    - **排序內建**:`detect_frozen_columns` 明文要求 caller 先把列由舊到新排好,
      漏排會讓「尾端 N 期」不是最近 N 期 → 誤判。把排序併進本函式,消除
      「每個 caller 各自記得要排序」這個必然會漏的步驟。
    - §1:偵測器自己壞掉一律回 `(0, [])` + log,**不**假裝有凍結結論
      (不確定 ≠ 凍結);同樣也不吞掉錯誤訊息。
    """
    _cols = tuple(cols) if cols is not None else FROZEN_WATCH_COLS_LEADING
    _n = FROZEN_STALE_PERIODS_LEADING if stale_periods is None else int(stale_periods)
    _dc = LEADING_DATE_COL if date_col is None else str(date_col)

    if df is None or getattr(df, "empty", True):
        return (0, [])
    # ⚠️ 不可寫成 `getattr(df, "columns", []) or []` —— `df.columns` 是 pandas
    # `Index`,對它取布林值會 `ValueError: The truth value of a Index is ambiguous`。
    # 任何**非空**的真實 DataFrame 都會踩到,等於這支函式在 production 必然拋例外。
    _cols_attr = getattr(df, "columns", None)
    _df_cols = list(_cols_attr) if _cols_attr is not None else []
    if not any(c in _df_cols for c in _cols):
        return (0, [])

    _sorted = df
    if _dc in _df_cols:
        try:
            _sorted = df.sort_values(_dc)
        except Exception as _e_sort:  # noqa: BLE001 — 排序失敗沿用原順序但要出聲
            print(f"[freshness] ⚠️ li 依 {_dc} 排序失敗,沿用原順序: "
                  f"{type(_e_sort).__name__}: {_e_sort}")
    try:
        _res = detect_frozen_columns(_sorted, _cols, stale_periods=_n)
    except Exception as _e_det:  # noqa: BLE001 — 偵測器壞掉不得反噬呼叫端
        print(f"[freshness] ⚠️ 凍結偵測失敗: {type(_e_det).__name__}: {_e_det}")
        return (0, [])
    return frozen_summary(_res)


def _emoji_worse(a: str, b: str) -> str:
    """回兩個燈號中「較差」的那個(⬜ 視為最不確定,排在綠之後)。

    供覆蓋率表這類「覆蓋率燈號 × 新鮮度燈號」需取交集降級的場景使用,
    避免各處自己寫 if/else 導致降級規則不一致。
    (排序表已抽 `_FRESH_RANK`,與 `worst_freshness` 共用同一份定義。)
    """
    return a if _FRESH_RANK.get(a, 1) >= _FRESH_RANK.get(b, 1) else b
