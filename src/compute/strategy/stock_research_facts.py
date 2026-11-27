"""src/compute/strategy/stock_research_facts.py — 個股「事實前置」（L2 純函式）。

給單檔日K序列，輸出**確定性的技術事實**，供未來核准的 ad-hoc 研究 Digest 使用。
**不是 AI、不是評分、不是任何操作建議**；只陳述「這些數字在資料日當天是多少」，
以及「哪些數字因根數不足而算不出來」。

§8.2 layer：L2 —— 零 I/O、零時鐘、零 streamlit、不 import `src.data`。

════════════════════════════════════════════════════════════════════
介面
════════════════════════════════════════════════════════════════════
    build_stock_research_facts(bars, *, as_of) -> StockResearchFacts

- ``bars``：DataFrame，**小寫欄** open / high / low / close / volume；
  index 為日期（DatetimeIndex，或可無歧義轉成日期的 str / date 索引），
  **嚴格遞增、無重複**；價格為**原始未調整價**；volume 單位沿用輸入、不換算。
  純數字索引（例如 RangeIndex）一律拒絕 —— 否則會被當成 1970 年 epoch 靜默誤讀。
  含時區的索引取其牆上時間（tz_localize(None)）；同一天出現兩個時間點視為重複而 raise。
- ``as_of``：資料日（'YYYY-MM-DD' 字串或 ``datetime.date``），**必須等於 bars 最後一列日期**，
  否則 raise。資料日不得由呼叫端任意宣稱，也不得以抓取時間頂替；本函式不讀時鐘。
  ``datetime.datetime``（含 pandas Timestamp）因時間成分有歧義而拒絕。

════════════════════════════════════════════════════════════════════
§1 Fail Loud / missing ≠ 0
════════════════════════════════════════════════════════════════════
- 結構性壞輸入（缺欄、索引非嚴格遞增、NaN/inf、價格 ≤ 0、high < low、volume < 0、
  空表、非 DataFrame、as_of 不符）一律 raise ``StockResearchFactsInputError``。
  不 dropna / ffill / fillna。volume == 0 合法（停牌 / 跌停鎖死仍是有效 bar）。
- 任何「根數不足」的指標一律回 ``None``，**不是** 0 / False / 0.5。
  本模組在呼叫既有函式**之前**先以具名常數做根數檢查，**不依賴**各函式自身的不足行為
  （例如 ``assess_price_overextension`` 不足時回 ``overheated=False`` 的偽值）。
- ``overheated`` 沿用 ``assess_price_overextension`` 的定義：**至少一項**過熱訊號成立即為 True
  （level == '偏熱' 或 '過熱'）；不足 → ``None``。
- RSI 在整段收盤價完全沒有變動時數學上無定義（既有 kernel 會給出 0.0 這種偽值），
  本模組此情況 ``rsi14=None``，並在 limitations 另寫一句，**不**輸出 0.0。
  同時 ``overheated`` / ``overextension_level`` 也為 ``None``（過熱評估含 RSI 項，來源函式內部
  以偽 0.0 代入而給出「正常 / False」，那是由缺值造成的偽值，故不採用）；
  ``bias20_pct`` 仍照實輸出（根數足夠時）。

════════════════════════════════════════════════════════════════════
輸入型別與 pandas 相容性（requirements：pandas>=2.0.0,<4）
════════════════════════════════════════════════════════════════════
- 欄名不可重複；五欄 dtype 僅收整數 / 浮點（含 nullable Int64 / Float64），
  bool、complex、object 一律 raise（不依賴 ``is_numeric_dtype``，它會放行 bool / complex）。
- 使用的 pandas API：``Index.is_unique/duplicated``、``is_integer_dtype/is_float_dtype/
  is_numeric_dtype/is_bool_dtype``、``pd.to_datetime``、``DatetimeIndex.hasnans/tz/tz_localize(None)``、
  ``Series.to_numpy(dtype, na_value)``、``rolling().mean()``、``ewm`` 皆在 pandas 2.0 即存在且語意相同
  （依文件 / 記憶判斷）。⚠️ **本環境只有 pandas 3.0.5，未實測 2.x**；
  其中 ``pd.to_datetime`` 對 str 索引的格式推斷在 2.x 與 3.x 可能不同（皆為「可轉就轉、
  不可轉 raise」），建議傳 DatetimeIndex。

════════════════════════════════════════════════════════════════════
最少根數（具名常數，來源對應既有函式實際門檻）
════════════════════════════════════════════════════════════════════
- MA(n)：n 根（``calc_ma_series`` = ``rolling(n).mean()``）。窗口 5 / 20 / 60 / 120 / 240。
- RSI14：15 根（``tech_indicators.calc_rsi`` 的 ``len < period + 1 → None``）。
- 量比5：6 根（``calc_volume_ratio`` 的 ``len < period + 1 → None``；今日量 / 前 5 日均量）。
  前 5 日均量為 0 時來源回 None → 本模組亦為 None。
- 乖離20 / 過熱：21 根（``assess_price_overextension`` 的 ``len < ma_window + 1 → 資料不足``）。
- 支撐 / 壓力：5 根（``entry_stop_levels.MIN_BARS``），窗口 20 根。

``support_resistance_bars`` 的選擇：**照實回報** ``compute_support_resistance`` 實際採用的根數
（= min(總根數, 20)）。5～19 根時仍計算，但 ``support_resistance_bars`` < 20 會如實顯示，
並在 limitations 加一句說明；< 5 根時支撐 / 壓力 / bars 皆為 None。
標籤寫「20 日」卻只涵蓋 10 根正是 S5 v19.78 已踩過的坑。

════════════════════════════════════════════════════════════════════
精度
════════════════════════════════════════════════════════════════════
- MA / 乖離 / close 統一 ``round(x, 4)``（``_ROUND_DIGITS``）。
- RSI14 沿用 ``calc_rsi`` 的 1 位小數；量比5 沿用 ``calc_volume_ratio`` 的 2 位小數；
  支撐 / 壓力沿用 ``compute_support_resistance`` 的 2 位小數（台股報價最小跳動不小於 0.01）。
  以上是既有 SSOT 函式本身的輸出精度，本模組不再重算以免雙寫。

不使用（有偽值或越界輸出目標價 / 停損 / 風報比）：calc_trend_score、compute_tech_bearish、
calc_ibs、calc_volume_score、calc_momentum_score、calc_atr_stop、compute_pattern_targets、
summarize_pattern、compute_entry_stop_levels、calc_rr_ratio、stock_score；
亦不 import scoring_engine 的評分函式與 exit_signals。
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np
import pandas as pd

from src.compute.strategy.entry_stop_levels import (
    MIN_BARS as _SR_MIN_BARS_SRC,
    compute_support_resistance,
)
from src.compute.strategy.overextension import assess_price_overextension
from src.compute.strategy.tech_indicators import (
    calc_ma_series,
    calc_rsi,
    calc_volume_ratio,
)

__all__ = [
    "StockResearchFacts",
    "StockResearchFactsInputError",
    "build_stock_research_facts",
]

# ── 具名常數（見模組 docstring「最少根數」）──────────────────────────
PRICE_BASIS_UNADJUSTED = "unadjusted"
REQUIRED_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")
MA_WINDOWS: tuple[int, ...] = (5, 20, 60, 120, 240)
RSI_PERIOD = 14
MIN_BARS_RSI = RSI_PERIOD + 1               # calc_rsi：len < period + 1 → None
VOLUME_RATIO_PERIOD = 5
MIN_BARS_VOLUME_RATIO = VOLUME_RATIO_PERIOD + 1   # calc_volume_ratio：len < period + 1 → None
OVEREXT_MA_WINDOW = 20                      # assess_price_overextension 預設 ma_window
MIN_BARS_OVEREXT = OVEREXT_MA_WINDOW + 1    # assess_price_overextension：len < ma_window + 1 → 資料不足
SR_WINDOW_BARS = 20                         # compute_support_resistance 預設 window
SR_MIN_BARS = _SR_MIN_BARS_SRC              # entry_stop_levels.MIN_BARS（=5）
_ROUND_DIGITS = 4

LIMITATION_UNADJUSTED = "價格為未調整原始價，除權息日前後指標可能失真。"
LIMITATION_MA_REFERENCE = "均線為參考，不等於正式台股趨勢判斷。"
_LIMITATION_INSUFFICIENT_PREFIX = "下列指標根數不足而無法計算："
_LIMITATION_OVEREXT_NO_RSI = "過熱評估缺 RSI 項而不予判定（乖離值仍照實列出）。"
_LIMITATION_RSI_FLAT = "RSI14 因整段收盤價完全沒有變動而無定義。"


class StockResearchFactsInputError(ValueError):
    """輸入結構性錯誤（§1 Fail Loud）。訊息說明哪個欄位 / 條件違規。"""


@dataclass(frozen=True)
class StockResearchFacts:
    """單檔個股技術事實。不足的指標為 None（**不是** 0 / False）。"""

    as_of: _dt.date
    bar_count: int
    first_date: _dt.date
    price_basis: str
    close: float
    ma: Mapping[int, float | None]
    rsi14: float | None
    volume_ratio5: float | None
    bias20_pct: float | None
    overextension_level: str | None
    overheated: bool | None
    support_20d: float | None
    resistance_20d: float | None
    support_resistance_bars: int | None
    limitations: tuple[str, ...]


# ── 輸入驗證 ─────────────────────────────────────────────────────────

def _parse_as_of(as_of) -> _dt.date:
    if isinstance(as_of, _dt.datetime):
        raise StockResearchFactsInputError(
            "as_of 不接受 datetime（時間成分有歧義）；請傳 date 或 'YYYY-MM-DD'")
    if isinstance(as_of, _dt.date):
        return as_of
    if isinstance(as_of, str):
        try:
            return _dt.datetime.strptime(as_of, "%Y-%m-%d").date()
        except ValueError as exc:
            raise StockResearchFactsInputError(
                f"as_of 無法解析為 'YYYY-MM-DD'：{as_of!r}") from exc
    raise StockResearchFactsInputError(
        f"as_of 型別不支援：{type(as_of).__name__}（需 str 或 date）")


def _extract_dates(index: pd.Index) -> list[_dt.date]:
    if isinstance(index, pd.MultiIndex):
        raise StockResearchFactsInputError("index 不可為 MultiIndex")
    if (pd.api.types.is_numeric_dtype(index.dtype)
            or pd.api.types.is_bool_dtype(index.dtype)):
        raise StockResearchFactsInputError(
            "index 必須是日期（DatetimeIndex 或可轉日期的索引），不可為純數字索引")
    try:
        dt = pd.DatetimeIndex(pd.to_datetime(index))
    except Exception as exc:  # pandas 對不可轉換的多種例外型別皆視為壞輸入
        raise StockResearchFactsInputError(f"index 無法轉為日期：{exc}") from exc
    if dt.hasnans:
        raise StockResearchFactsInputError("index 含 NaT（無效日期）")
    if dt.tz is not None:
        dt = dt.tz_localize(None)
    dates = [ts.date() for ts in dt]
    for prev, cur in zip(dates, dates[1:]):
        if cur == prev:
            raise StockResearchFactsInputError(f"index 有重複日期：{cur}")
        if cur < prev:
            raise StockResearchFactsInputError(
                f"index 非嚴格遞增：{prev} 之後出現 {cur}")
    return dates


def _validate_bars(bars) -> tuple[list[_dt.date], pd.DataFrame]:
    """回傳 (日期清單, 內部 float64 工作副本，RangeIndex)。不改傳入物件。"""
    if not isinstance(bars, pd.DataFrame):
        raise StockResearchFactsInputError(
            f"bars 必須是 pandas DataFrame，收到 {type(bars).__name__}")
    if bars.empty:
        raise StockResearchFactsInputError("bars 為空（無任何 K 線）")
    if not bars.columns.is_unique:
        dup = sorted({str(c) for c in bars.columns[bars.columns.duplicated()]})
        raise StockResearchFactsInputError(f"bars 欄名重複：{dup}")
    missing = [c for c in REQUIRED_COLUMNS if c not in bars.columns]
    if missing:
        raise StockResearchFactsInputError(f"bars 缺必要欄：{missing}（需小寫欄）")
    dates = _extract_dates(bars.index)

    cols: dict[str, np.ndarray] = {}
    for c in REQUIRED_COLUMNS:
        s = bars[c]
        # 只收整數 / 浮點（含 nullable Int64 / Float64）；bool、complex、object、
        # datetime 等一律拒絕（is_numeric_dtype 會放行 bool 與 complex，故不用它）。
        if not (pd.api.types.is_integer_dtype(s.dtype) or pd.api.types.is_float_dtype(s.dtype)):
            raise StockResearchFactsInputError(
                f"欄位 {c} 必須為實數數值型別（整數或浮點；dtype={s.dtype}）")
        arr = s.to_numpy(dtype="float64", na_value=np.nan)
        if not np.isfinite(arr).all():
            raise StockResearchFactsInputError(f"欄位 {c} 含 NaN 或 inf")
        cols[c] = arr
    for c in ("open", "high", "low", "close"):
        if (cols[c] <= 0).any():
            raise StockResearchFactsInputError(f"欄位 {c} 含 ≤ 0 的價格")
    if (cols["high"] < cols["low"]).any():
        raise StockResearchFactsInputError("存在 high < low 的 K 線")
    if (cols["volume"] < 0).any():
        raise StockResearchFactsInputError("欄位 volume 含負值")
    return dates, pd.DataFrame(cols)


# ── 主函式 ───────────────────────────────────────────────────────────

def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), _ROUND_DIGITS)


def build_stock_research_facts(bars: pd.DataFrame, *,
                               as_of: str | _dt.date) -> StockResearchFacts:
    """由單檔日K建立 ``StockResearchFacts``。純函式、不改輸入、不讀時鐘。

    Raises:
        StockResearchFactsInputError: 輸入結構性錯誤，或 as_of 與最後一列日期不符。
    """
    as_of_date = _parse_as_of(as_of)
    dates, work = _validate_bars(bars)
    if dates[-1] != as_of_date:
        raise StockResearchFactsInputError(
            f"as_of={as_of_date} 與 bars 最後一列日期 {dates[-1]} 不符")

    n = len(work)
    close_s = work["close"]
    last_close = float(close_s.iloc[-1])
    insufficient: list[str] = []
    notes: list[str] = []

    # MA
    ma: dict[int, float | None] = {}
    for w in MA_WINDOWS:
        if n < w:
            ma[w] = None
            insufficient.append(f"MA{w}")
            continue
        v = calc_ma_series(close_s, w).iloc[-1]
        ma[w] = _r(v) if pd.notna(v) else None

    # RSI14
    rsi14: float | None = None
    rsi_undefined = False
    if n < MIN_BARS_RSI:
        insufficient.append(f"RSI{RSI_PERIOD}")
    elif not (close_s.diff().abs() > 0).any():
        rsi_undefined = True
        notes.append(_LIMITATION_RSI_FLAT)   # 全平盤：kernel 會給 0.0 偽值，不採用
    else:
        rsi14 = calc_rsi(work, RSI_PERIOD)

    # 量比5
    volume_ratio5: float | None = None
    if n < MIN_BARS_VOLUME_RATIO:
        insufficient.append(f"量比{VOLUME_RATIO_PERIOD}")
    else:
        volume_ratio5 = calc_volume_ratio(work, VOLUME_RATIO_PERIOD)

    # 乖離 / 過熱
    bias20_pct: float | None = None
    level: str | None = None
    overheated: bool | None = None
    if n < MIN_BARS_OVEREXT:
        insufficient.append("乖離20與過熱評估")
    else:
        oe = assess_price_overextension(close_s, ma_window=OVEREXT_MA_WINDOW,
                                        rsi_period=RSI_PERIOD)
        if oe["level"] != "資料不足":
            bias20_pct = _r(oe["bias_pct"])
            if rsi_undefined:
                # 過熱 = 乖離項 + RSI 項；RSI 項無定義（來源內部以偽 0.0 代入）→
                # 整體不判定（None），不以「僅乖離項為正常 / False」代替。
                notes.append(_LIMITATION_OVEREXT_NO_RSI)
            else:
                level = str(oe["level"])
                overheated = bool(oe["overheated"])

    # 支撐 / 壓力
    support = resistance = None
    sr_bars: int | None = None
    if n < SR_MIN_BARS:
        insufficient.append("支撐壓力")
    else:
        sr = compute_support_resistance(work, current_price=last_close,
                                        window=SR_WINDOW_BARS, min_bars=SR_MIN_BARS)
        if sr.window_bars > 0 and sr.support is not None and sr.resistance is not None:
            support, resistance = _r(sr.support), _r(sr.resistance)
            sr_bars = int(sr.window_bars)
            if sr_bars < SR_WINDOW_BARS:
                notes.append(f"支撐與壓力實際僅涵蓋 {sr_bars} 根日K，少於標準 {SR_WINDOW_BARS} 根。")

    limitations = [LIMITATION_UNADJUSTED, LIMITATION_MA_REFERENCE]
    if insufficient:
        limitations.append(_LIMITATION_INSUFFICIENT_PREFIX + "、".join(insufficient) + "。")
    limitations.extend(notes)

    return StockResearchFacts(
        as_of=as_of_date,
        bar_count=n,
        first_date=dates[0],
        price_basis=PRICE_BASIS_UNADJUSTED,
        close=_r(last_close),
        ma=MappingProxyType(ma),
        rsi14=rsi14,
        volume_ratio5=volume_ratio5,
        bias20_pct=bias20_pct,
        overextension_level=level,
        overheated=overheated,
        support_20d=support,
        resistance_20d=resistance,
        support_resistance_bars=sr_bars,
        limitations=tuple(limitations),
    )
