"""src/compute/strategy/stock_research_facts.py — 個股「事實前置」（L2 純函式）。

給單檔日K序列，輸出**確定性的技術事實**，供未來核准的 ad-hoc 研究 Digest 使用。
**不是 AI、不是評分、不是任何操作建議**；只陳述「這些數字在資料日當天是多少」，
以及「哪些數字因根數不足而算不出來」。

§8.2 layer：L2 —— 零 I/O、零時鐘、零 streamlit、不 import `src.data`。

════════════════════════════════════════════════════════════════════
介面
════════════════════════════════════════════════════════════════════
    build_stock_research_facts(bars, *, as_of, basis_verified=True) -> StockResearchFacts

- ``bars``：DataFrame，**小寫欄** open / high / low / close / volume；
  index 為日期（DatetimeIndex，或可無歧義轉成日期的 str / date 索引），
  **嚴格遞增、無重複**；價格為**原始未調整價**；volume 單位沿用輸入、不換算。
  純數字索引（例如 RangeIndex）一律拒絕 —— 否則會被當成 1970 年 epoch 靜默誤讀。
  含時區的索引取其牆上時間（tz_localize(None)）；同一天出現兩個時間點視為重複而 raise。
- ``as_of``：資料日（'YYYY-MM-DD' 字串或 ``datetime.date``），**必須等於 bars 最後一列日期**，
  否則 raise。資料日不得由呼叫端任意宣稱，也不得以抓取時間頂替；本函式不讀時鐘。
  ``datetime.datetime``（含 pandas Timestamp）因時間成分有歧義而拒絕。

- ``basis_verified``（keyword-only，預設 True）：價格口徑「未調整原始價」是否**已被驗證**。
  **呼叫端責任**：本機使用者匯入的日K（口徑僅為使用者聲明、系統無法驗證）**必須**傳
  ``basis_verified=False``；僅當呼叫端有**可驗證證據**證明為未調整價時才可用預設 True。
  預設 True 是為了讓既有 caller 行為不變（目前 repo 內 0 production caller）。
  False 時：``price_basis='unadjusted_declared'``、``price_basis_verified=False``，
  limitations 第一句改為「價格口徑由使用者聲明為未調整原始價，系統未驗證。」＋
  「除權息日前後指標可能失真。」兩句（不把未驗證口徑當事實）；其他事實值不變。
  非 ``bool``（含 int 0/1、None、numpy.bool_、字串）一律 raise —— 口徑未知不可當 verified，
  也不做 truthy 轉型。

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

════════════════════════════════════════════════════════════════════
數值安全（F1，非有限 / 溢位 / 下溢 → None + 具名限制，不設任何價量業務上限）
════════════════════════════════════════════════════════════════════
- 不對價格或成交量設任何上限 / 下限 / 裁切；1e300 這類可正常計算的值照常輸出。
- 既有函式在極端值下可能給出**有限的偽值**（例如前 5 日量加總溢位成 inf → 量比 0.0；
  價格 1e-300 時 RSI 的 +1e-10 epsilon 壓過全部漲跌 → 0.0；rolling 加總溢位 → NaN 被靜默吞掉）。
  本模組**不修改**那些函式，改以**獨立精確重算**驗證其輸出：
  * MA(n)：以整數精確平均（float.as_integer_ratio，不經浮點）對照 rolling mean；
  * 量比5：以精確分數算前 5 日均量與比值，檢查來源輸出落在四捨五入解析度內；
  * RSI14：以 2 的冪次正規化（精確、不引入誤差）後、不含 epsilon 的 Wilder 公式對照；
  * 價位類輸出（close / MA / 支撐 / 壓力）：驗證通過的正價格不得因四捨五入變成 0.0。
  任一驗證不通過 → 該指標 ``None``，並在 limitations 加一句僅列指標名稱的固定句。
- 量比5 四捨五入到 2 位後為 0.0（今日量相對均量不到 0.005）屬既有精度慣例，不在本節處理。

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
PRICE_BASIS_UNADJUSTED_DECLARED = "unadjusted_declared"   # 使用者聲明、系統未驗證
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
LIMITATION_UNADJUSTED_DECLARED = "價格口徑由使用者聲明為未調整原始價，系統未驗證。"
LIMITATION_EX_RIGHTS_DISTORTION = "除權息日前後指標可能失真。"
LIMITATION_MA_REFERENCE = "均線為參考，不等於正式台股趨勢判斷。"
_LIMITATION_INSUFFICIENT_PREFIX = "下列指標根數不足而無法計算："
_LIMITATION_OVEREXT_NO_RSI = "過熱評估缺 RSI 項而不予判定（乖離值仍照實列出）。"
_LIMITATION_RSI_FLAT = "RSI14 因整段收盤價完全沒有變動而無定義。"
# F1：數值不可穩定計算（溢位 / 下溢 / 精度不足）。僅列指標名稱，不含數值。
_LIMITATION_NUMERIC_PREFIX = "下列指標因數值超出可穩定計算的範圍而不予輸出："
_REL_TOL = 1e-9                  # 與精確重算比對的相對容差（浮點誤差遠小於此）
_RSI_TOL = 0.1                   # RSI 輸出 1 位小數 → 容許差一個四捨五入階
_VOL_RATIO_HALF_STEP = 0.005     # 量比輸出 2 位小數 → 容許半個四捨五入階


class StockResearchFactsInputError(ValueError):
    """輸入結構性錯誤（§1 Fail Loud）。訊息說明哪個欄位 / 條件違規。"""


@dataclass(frozen=True)
class StockResearchFacts:
    """單檔個股技術事實。不足的指標為 None（**不是** 0 / False）。"""

    as_of: _dt.date
    bar_count: int
    first_date: _dt.date
    price_basis: str
    close: float | None     # 正價格因四捨五入會變 0.0（< 5e-5）時為 None（F1，不輸出偽 0）
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
    # 放最後並給預設 True：既有（含位置式）建構不受影響；預設路徑恆為 True。
    price_basis_verified: bool = True


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


# ── F1 數值安全：獨立精確重算（只驗證既有函式輸出，不取代它）─────────────

def _positive_rounds_to_zero(x: float) -> bool:
    """正值經 ``_r`` 四捨五入後落成 0.0（價位類輸出不可能為 0，故屬偽 0）。"""
    return bool(x > 0 and not (_r(x) > 0))


def _exact_sum(values) -> tuple[int, int]:
    """float 序列的**精確**總和，以 (分子, 分母) 兩個整數表示（不經浮點、不溢位）。
    每個 float 皆為 m/2^k，故以最大分母通分即可；不 import fractions（沿用既有 import 集合）。"""
    ratios = [float(v).as_integer_ratio() for v in values]
    den = max(d for _, d in ratios)
    return sum(nu * (den // d) for nu, d in ratios), den


def _exact_mean_float(values) -> float | None:
    """精確平均轉 float（整數真除法為正確捨入）；超出 float 範圍 → None。"""
    num, den = _exact_sum(values)
    try:
        return num / (den * len(values))
    except OverflowError:
        return None


def _ma_valid(legacy: float, closes: np.ndarray, w: int) -> bool:
    """rolling mean 結果須為有限，且與精確平均相符（相對容差 1e-9）。"""
    if not np.isfinite(legacy):
        return False
    exact = _exact_mean_float(closes[-w:])
    return exact is not None and bool(np.isclose(legacy, exact, rtol=_REL_TOL, atol=0.0))


_FLOAT_MAX_INT_RATIO = float(np.finfo(np.float64).max).as_integer_ratio()


def _volume_ratio_valid(legacy: float | None, volumes: np.ndarray) -> bool | None:
    """檢查 ``calc_volume_ratio`` 輸出。

    回傳 True＝可採用；False＝數值失真（溢位 / 下溢，應改 None 並具名限制）；
    None＝前 5 日均量精確為 0，沿用來源「None」語意（無定義，非數值失真，行為不變）。
    前 5 日量的精確總和超過 float 上限時，來源的 rolling/mean 中間值為 inf，
    其輸出即使碰巧落在四捨五入範圍內也不採用（非有限中間值）。
    """
    num, den = _exact_sum(volumes[-(VOLUME_RATIO_PERIOD + 1):-1])
    if num <= 0:
        return None
    max_num, max_den = _FLOAT_MAX_INT_RATIO
    if num * max_den > max_num * den:       # 精確總和 > float 最大值 → 中間值溢位
        return False
    if legacy is None or not np.isfinite(legacy):
        return False
    t_num, t_den = float(volumes[-1]).as_integer_ratio()
    try:
        exact = (t_num * den * VOLUME_RATIO_PERIOD) / (t_den * num)
    except OverflowError:
        return False
    return bool(abs(legacy - exact) <= _VOL_RATIO_HALF_STEP + _REL_TOL * abs(exact) + 1e-12)


def _rsi_unbiased(closes: np.ndarray) -> float | None:
    """不含 epsilon 的 Wilder RSI（驗證用）。以 2 的冪次正規化尺度（精確），RSI 為尺度不變量。"""
    _, e = np.frexp(float(np.max(closes)))
    s = pd.Series(np.ldexp(closes, -int(e)))
    d = s.diff()
    alpha = 1 / RSI_PERIOD
    g = float(d.clip(lower=0).ewm(alpha=alpha, adjust=False).mean().iloc[-1])
    lo = float((-d.clip(upper=0)).ewm(alpha=alpha, adjust=False).mean().iloc[-1])
    if not (np.isfinite(g) and np.isfinite(lo)):
        return None
    if not lo > 0:
        return 100.0 if g > 0 else None
    return 100.0 - 100.0 / (1.0 + g / lo)


def _rsi_valid(legacy: float | None, exact: float | None) -> bool:
    if legacy is None or exact is None or not np.isfinite(legacy):
        return False
    return abs(legacy - exact) <= _RSI_TOL + _REL_TOL


def build_stock_research_facts(bars: pd.DataFrame, *,
                               as_of: str | _dt.date,
                               basis_verified: bool = True) -> StockResearchFacts:
    """由單檔日K建立 ``StockResearchFacts``。純函式、不改輸入、不讀時鐘。

    ``basis_verified``：價格口徑（未調整原始價）是否已被驗證。本機使用者匯入的日K
    （口徑僅為使用者聲明）必須傳 False；僅當呼叫端有可驗證證據時才可用預設 True。
    預設 True 保持既有行為不變。詳見模組 docstring。

    Raises:
        StockResearchFactsInputError: 輸入結構性錯誤、as_of 與最後一列日期不符，
            或 basis_verified 不是 bool。
    """
    if not isinstance(basis_verified, bool):   # 不 truthy 轉型；np.bool_ / int / None / str 皆拒
        raise StockResearchFactsInputError(
            f"basis_verified 必須是 bool，收到 {type(basis_verified).__name__}")
    as_of_date = _parse_as_of(as_of)
    dates, work = _validate_bars(bars)
    if dates[-1] != as_of_date:
        raise StockResearchFactsInputError(
            f"as_of={as_of_date} 與 bars 最後一列日期 {dates[-1]} 不符")

    n = len(work)
    close_s = work["close"]
    closes = close_s.to_numpy(dtype="float64")
    volumes = work["volume"].to_numpy(dtype="float64")
    last_close = float(close_s.iloc[-1])
    insufficient: list[str] = []
    notes: list[str] = []
    numeric_failed: list[str] = []   # F1：數值不可穩定計算而改 None 的指標名稱

    close_out: float | None = _r(last_close)
    if _positive_rounds_to_zero(last_close):
        close_out = None             # 正價格四捨五入成 0.0 = 偽 0
        numeric_failed.append("收盤價")

    # MA
    ma: dict[int, float | None] = {}
    ma20_ok = False
    for w in MA_WINDOWS:
        if n < w:
            ma[w] = None
            insufficient.append(f"MA{w}")
            continue
        v = calc_ma_series(close_s, w).iloc[-1]
        if pd.isna(v):
            # rolling 加總溢位會被靜默吞成 NaN：輸入皆有限，故 NaN 必為數值失真，不可無聲略過
            ma[w] = None
            numeric_failed.append(f"MA{w}")
            continue
        v = float(v)
        if not _ma_valid(v, closes, w) or _positive_rounds_to_zero(v):
            ma[w] = None
            numeric_failed.append(f"MA{w}")
            continue
        ma[w] = _r(v)
        if w == OVEREXT_MA_WINDOW:
            ma20_ok = True

    # RSI14
    rsi14: float | None = None
    rsi_undefined = False
    rsi_exact: float | None = None
    rsi_numeric_bad = False
    if n < MIN_BARS_RSI:
        insufficient.append(f"RSI{RSI_PERIOD}")
    elif not (close_s.diff().abs() > 0).any():
        rsi_undefined = True
        notes.append(_LIMITATION_RSI_FLAT)   # 全平盤：kernel 會給 0.0 偽值，不採用
    else:
        rsi_exact = _rsi_unbiased(closes)
        legacy_rsi = calc_rsi(work, RSI_PERIOD)
        if _rsi_valid(legacy_rsi, rsi_exact):
            rsi14 = legacy_rsi
        else:
            rsi_numeric_bad = True           # 例：價格極小時 +1e-10 epsilon 壓過全部漲跌 → 偽 0.0
            numeric_failed.append(f"RSI{RSI_PERIOD}")

    # 量比5
    volume_ratio5: float | None = None
    if n < MIN_BARS_VOLUME_RATIO:
        insufficient.append(f"量比{VOLUME_RATIO_PERIOD}")
    else:
        legacy_vr = calc_volume_ratio(work, VOLUME_RATIO_PERIOD)
        verdict = _volume_ratio_valid(legacy_vr, volumes)
        if verdict is None:
            volume_ratio5 = legacy_vr        # 前 5 日均量精確為 0：維持來源既有語意（None）
        elif verdict:
            volume_ratio5 = legacy_vr
        else:
            numeric_failed.append(f"量比{VOLUME_RATIO_PERIOD}")   # 例：均量加總溢位 → 偽 0.0

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
            bias_raw = oe["bias_pct"]
            bias_ok = (ma20_ok and bias_raw is not None
                       and np.isfinite(float(bias_raw)))
            oe_rsi = oe.get("rsi")
            # 過熱評估內部的 RSI 同樣可能因 epsilon / 溢位而失真，獨立驗證
            oe_rsi_ok = (rsi_undefined or (
                rsi_exact is not None and oe_rsi is not None
                and np.isfinite(float(oe_rsi))
                and abs(float(oe_rsi) - rsi_exact) <= _RSI_TOL + _REL_TOL))
            if not bias_ok:
                # MA20 失真時，來源會退用較早的 MA 算乖離（有限的偽值）→ 乖離與過熱全不採用
                numeric_failed.append("乖離20與過熱評估")
            else:
                bias20_pct = _r(bias_raw)
                if rsi_undefined:
                    # 過熱 = 乖離項 + RSI 項；RSI 項無定義（來源內部以偽 0.0 代入）→
                    # 整體不判定（None），不以「僅乖離項為正常 / False」代替。
                    notes.append(_LIMITATION_OVEREXT_NO_RSI)
                elif rsi_numeric_bad or not oe_rsi_ok:
                    if not rsi_numeric_bad:
                        numeric_failed.append("過熱評估")
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
            sup_f, res_f = float(sr.support), float(sr.resistance)
            if (np.isfinite(sup_f) and np.isfinite(res_f)
                    and sup_f > 0 and res_f > 0
                    and not _positive_rounds_to_zero(sup_f)
                    and not _positive_rounds_to_zero(res_f)):
                support, resistance = _r(sup_f), _r(res_f)
                sr_bars = int(sr.window_bars)
                if sr_bars < SR_WINDOW_BARS:
                    notes.append(f"支撐與壓力實際僅涵蓋 {sr_bars} 根日K，少於標準 {SR_WINDOW_BARS} 根。")
            else:
                numeric_failed.append("支撐壓力")   # 正價位經 2 位四捨五入落成 0.0 = 偽 0

    if basis_verified:
        limitations = [LIMITATION_UNADJUSTED, LIMITATION_MA_REFERENCE]
    else:
        limitations = [LIMITATION_UNADJUSTED_DECLARED, LIMITATION_EX_RIGHTS_DISTORTION,
                       LIMITATION_MA_REFERENCE]
    if insufficient:
        limitations.append(_LIMITATION_INSUFFICIENT_PREFIX + "、".join(insufficient) + "。")
    limitations.extend(notes)
    if numeric_failed:
        limitations.append(_LIMITATION_NUMERIC_PREFIX + "、".join(numeric_failed) + "。")

    return StockResearchFacts(
        as_of=as_of_date,
        bar_count=n,
        first_date=dates[0],
        price_basis=(PRICE_BASIS_UNADJUSTED if basis_verified
                     else PRICE_BASIS_UNADJUSTED_DECLARED),
        close=close_out,
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
        price_basis_verified=basis_verified,
    )
