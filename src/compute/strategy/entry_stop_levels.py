"""src/compute/strategy/entry_stop_levels.py — 大量紅 K 進場價與絕對停損（L2 純函式）。

T4(2026-08)：把 `tab_stock.py:800-850` 的行內邏輯抽成純函式，
讓**個股頁**與**個股組合頁**共用同一份判定（§2.1 SSOT）。

§8.2 layer：**L2 純函式** —— 零 I/O、零 streamlit。輸入 OHLCV DataFrame，輸出數值。

════════════════════════════════════════════════════════════════════
為什麼這幾個數字值得放進「多筆比較表」
════════════════════════════════════════════════════════════════════
`tab_stock.py:648-677` 的 v19.179 B1-b 已經證明：以**固定百分比**推出的
停利停損價與盈虧比是**結構常數**，與個股無關 ——

    RR = (P×1.05 − P) / (P − P×0.92) = 0.05P / 0.08P = 0.625　（P 完全約掉）

該處畫面已正名為「固定方案盈虧比」並明寫「換任何一檔股票都是同兩個數字」。
⇒ 那組數字放進 20 檔的比較表毫無意義（20 列一模一樣）。

本模組算的是**以大量紅 K 低點為錨點**的版本 —— 錨點來自各股自己的價量結構，
**因股而異**，才具備比較價值。這正是 v19.179 保留的「實際盈虧比（紅K低點停損）」。

════════════════════════════════════════════════════════════════════
抽取時發現、但**刻意不改**的兩件事（行為保持等價）
════════════════════════════════════════════════════════════════════

**① 標籤說「近 20 日」，程式實際取「近 20 根紅 K」。**
原碼 `df[紅K條件].tail(20)` 是**先濾紅 K、再取最後 20 根**，
所以涵蓋的日曆區間可能遠超 20 個交易日（一檔震盪股 20 根紅 K 可能橫跨兩三個月）。
畫面標籤卻寫「近20日最大量的紅K」。

抽取階段**維持原行為**（§8.5：重構不得改變既有行為）。
要改成真正的「近 20 日內的紅 K」是**行為變更**，需另案裁示 ——
改了之後錨點會變、停損線會變、盈虧比會變，屬影響決策的改動。
`lookback_bars` 參數已預留，改判定時只要換傳入值即可。

**② 紅 K 的定義有兩套 fallback。**
有 `open` 欄時用 `close > open`（真紅 K）；無 `open` 時退為 `close > 前一日 close`
（其實是「上漲日」不是「紅 K」）。原碼如此，維持不動。

════════════════════════════════════════════════════════════════════
既有的 §1 防呆全部保留（都是踩過坑寫下的）
════════════════════════════════════════════════════════════════════
- **S4 v19.78**：`volume` 全 NaN 時，舊版 pandas `nlargest` 剔 NaN 回空 df →
  `.iloc[0]` IndexError；pandas 3.x 則回含 NaN 的任意列 → **靜默選錯紅 K**
  （進場價與停損算在錯的 bar 上）。故先濾 NaN 再取，兩版行為統一。
- **v19.179 B1-b**：`_abs_sl` 為 None 時**不可**偷偷退回固定 −8% ——
  那算出來的就是上面那個常數 0.625，卻掛「實際盈虧比」的名字，
  等於拿方案常數冒充個股實測值。
- **v19.179 B1-b**：現價已跌破紅 K 低點時分母為負，舊碼 `max(..., 0.01)`
  會把盈虧比夾成數千倍的假數字。本模組明確回 None + 原因。
"""
from __future__ import annotations

from dataclasses import dataclass

from shared.signal_thresholds import BIG_RED_STOP_BUFFER_PCT

__all__ = [
    "EntryStopLevels",
    "SupportResistance",
    "compute_entry_stop_levels",
    "compute_support_resistance",
]

#: 取最後幾根紅 K 找最大量。見模組 docstring「①」—— 這是**根數**不是日數。
DEFAULT_LOOKBACK_BARS = 20

#: 低於此根數不計算（原碼 `len(df2) >= 5`）。
MIN_BARS = 5


@dataclass(frozen=True)
class EntryStopLevels:
    """大量紅 K 錨點衍生的價位。全部算不出來時各欄為 None（**不是 0**）。"""

    entry_half: float | None = None
    """大量紅 K 的 1/2 位置（(high+low)/2），技術面低風險買點。"""

    abs_stop: float | None = None
    """絕對停損線 = 紅 K 低點 × (1 − BIG_RED_STOP_BUFFER_PCT/100)。"""

    stop_distance_pct: float | None = None
    """現價距絕對停損的百分比。負值代表**現價已跌破停損線**。"""

    risk_reward: float | None = None
    """實際盈虧比 =（停利目標 − 現價）/（現價 − 絕對停損）。算不出回 None。"""

    unavailable_reason: str | None = None
    """`risk_reward` 為 None 的原因。§1：不可只給 None 不說為什麼。"""

    @property
    def has_anchor(self) -> bool:
        """是否找到大量紅 K 錨點。False 時**不可**用固定 % 停損冒充。"""
        return self.abs_stop is not None


@dataclass(frozen=True)
class SupportResistance:
    """近 N 個交易日的高低點與距現價百分比。

    ⚠️ 與 `EntryStopLevels` 的 `lookback_bars` **語意不同**：
    本結構的 `window_bars` 是**日曆上的最後 N 根 K 線**（真的是「近 N 日」）；
    `EntryStopLevels` 取的是「最後 N 根**紅 K**」（見該處 docstring ①）。
    兩者剛好都預設 20，但涵蓋範圍不同 —— 不要因為數字一樣就以為是同一件事。
    """

    resistance: float | None = None
    """近 N 日最高價。"""

    support: float | None = None
    """近 N 日最低價。"""

    distance_to_resistance_pct: float | None = None
    """現價距壓力的百分比（正值 = 壓力在上方）。"""

    distance_to_support_pct: float | None = None
    """現價距支撐的百分比（正值 = 支撐在下方）。"""

    window_bars: int = 0
    """**實際**採用的根數。原碼 S5 v19.78 的教訓：資料不足 20 根時
    `tail(20)` 只涵蓋實際根數，標籤卻寫死「近20日」→ 壓力/支撐被高估卻標 20 日。
    故回傳實際值供畫面標示。"""


def compute_support_resistance(
    df,
    *,
    current_price: float | None = None,
    window: int = 20,
    min_bars: int = MIN_BARS,
) -> SupportResistance:
    """近 N 日高低點與距現價百分比。

    抽自 `tab_stock.py:637-638` + `:798-799`，供個股 / 個股組合共用。
    §1：資料不足回各欄 None（**不是 0**）—— 「支撐 0 元」會被讀成有效價位。
    """
    if df is None or len(df) < min_bars:
        return SupportResistance()
    _cols = getattr(df, "columns", [])
    if "high" not in _cols or "low" not in _cols:
        return SupportResistance()

    _n = min(len(df), int(window))
    try:
        _hi = float(df["high"].tail(_n).max())
        _lo = float(df["low"].tail(_n).min())
    except Exception:
        return SupportResistance()
    if not (_hi > 0 and _lo > 0):
        return SupportResistance()

    _cur = current_price
    if _cur is None:
        try:
            _cur = float(df["close"].iloc[-1])
        except Exception:
            _cur = None
    if not _cur or _cur <= 0:
        return SupportResistance(resistance=round(_hi, 2), support=round(_lo, 2),
                                 window_bars=_n)

    return SupportResistance(
        resistance=round(_hi, 2),
        support=round(_lo, 2),
        distance_to_resistance_pct=round((_hi / _cur - 1) * 100, 1),
        distance_to_support_pct=round((1 - _lo / _cur) * 100, 1),
        window_bars=_n,
    )


def _pick_big_red_candle(df, lookback_bars: int):
    """從最後 `lookback_bars` 根紅 K 中取成交量最大的那一根。找不到回 None。"""
    _cols = getattr(df, "columns", [])
    if "close" not in _cols:
        return None
    try:
        if "open" in _cols:
            _mask = df["close"] > df["open"]
        else:
            # 無 open 欄 → 退為「上漲日」。見模組 docstring「②」。
            _mask = df["close"] > df["close"].shift(1)
        _red = df[_mask].tail(int(lookback_bars))
    except Exception:
        return None
    if _red is None or len(_red) == 0 or "volume" not in getattr(_red, "columns", []):
        return None
    # S4 v19.78：先濾 NaN 再取，統一新舊 pandas 行為（見模組 docstring）。
    _valid = _red[_red["volume"].notna()]
    if len(_valid) == 0:
        return None
    try:
        _top = _valid.nlargest(1, "volume")
    except Exception:
        return None
    return None if len(_top) == 0 else _top.iloc[0]


def compute_entry_stop_levels(
    df,
    *,
    current_price: float | None = None,
    take_profit_price: float | None = None,
    lookback_bars: int = DEFAULT_LOOKBACK_BARS,
    min_bars: int = MIN_BARS,
) -> EntryStopLevels:
    """計算大量紅 K 進場價 / 絕對停損 / 實際盈虧比。

    Args:
        df: OHLCV，需含 `close`；`open` / `high` / `low` / `volume` 選用
            （缺 high/low 時以 close 代替，同原碼）。
        current_price: 現價。None → 由 df 最後一根 close 取。
        take_profit_price: 停利目標價（算盈虧比用）。None → 不算盈虧比。
        lookback_bars: 取最後幾**根紅 K**（不是日數，見模組 docstring）。
        min_bars: 低於此根數直接不算。

    Returns:
        `EntryStopLevels`。**不拋例外** —— 單一檔算不出來不該讓批次中斷，
        但也不會靜默給 0：各欄為 None 且 `unavailable_reason` 說明原因。
    """
    if df is None or len(df) < min_bars:
        return EntryStopLevels(unavailable_reason="K 線根數不足")

    _big = _pick_big_red_candle(df, lookback_bars)
    if _big is None:
        return EntryStopLevels(
            unavailable_reason=f"近 {lookback_bars} 根紅K無有效成交量 → 無停損錨點")

    try:
        _close = float(_big["close"])
        _hi = float(_big.get("high", _close))
        _lo = float(_big.get("low", _close))
    except Exception:
        return EntryStopLevels(unavailable_reason="紅K價格欄無法解析")
    if not (_lo > 0 and _hi > 0):
        return EntryStopLevels(unavailable_reason="紅K價格非正值")

    _entry_half = round((_hi + _lo) / 2, 2)
    _abs_stop = round(_lo * (1 - BIG_RED_STOP_BUFFER_PCT / 100.0), 2)

    # 現價
    _cur = current_price
    if _cur is None:
        try:
            _cur = float(df["close"].iloc[-1])
        except Exception:
            _cur = None
    if not _cur or _cur <= 0:
        return EntryStopLevels(
            entry_half=_entry_half, abs_stop=_abs_stop,
            unavailable_reason="無現價 → 無法計算距離與盈虧比")

    _dist_pct = round((_cur - _abs_stop) / _cur * 100, 1)

    # 盈虧比：§1 —— 兩種算不出的情形各自具名，不可用固定 % 停損頂替
    if take_profit_price is None:
        return EntryStopLevels(
            entry_half=_entry_half, abs_stop=_abs_stop,
            stop_distance_pct=_dist_pct,
            unavailable_reason="未提供停利目標價")
    if _cur <= _abs_stop:
        return EntryStopLevels(
            entry_half=_entry_half, abs_stop=_abs_stop,
            stop_distance_pct=_dist_pct,
            unavailable_reason="現價已跌破紅K低點 → 停損距離為負")

    _rr = round((float(take_profit_price) - _cur) / (_cur - _abs_stop), 2)
    return EntryStopLevels(
        entry_half=_entry_half, abs_stop=_abs_stop,
        stop_distance_pct=_dist_pct, risk_reward=_rr,
    )
