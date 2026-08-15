"""T4(2026-08)— 大量紅 K 進場價 / 絕對停損 L2 純函式測試。

受測：`src/compute/strategy/entry_stop_levels.py`
（抽自 `tab_stock.py:800-850` 的行內邏輯，供個股 / 個股組合兩頁共用）

本檔要釘住的四類事
──────────────────
1. **抽取後行為與原碼等價** —— 含三個踩過坑的防呆（見下）
2. **§1：算不出來時給 None + 原因，絕不用固定 % 停損頂替**
3. **「近 20 根紅 K」的現行語意**（不是「近 20 日」）—— 釘住現況，
   哪天要改成日數會紅燈提醒那是行為變更
4. L2 純度（零 I/O）

三個被保留的既有防呆（都是實際踩過的坑，勿回退）
──────────────────────────────────────────────
· **S4 v19.78**：`volume` 全 NaN 時，舊 pandas `nlargest` 回空 → `.iloc[0]`
  IndexError；pandas 3.x 回含 NaN 的任意列 → **靜默選錯紅 K**（進場價與停損
  算在錯的 bar 上，畫面看起來正常）。故先濾 NaN 再取。
· **v19.179 B1-b**：無錨點時**不可**退回固定 −8% —— 那算出來就是結構常數
  0.625，卻掛「實際盈虧比」的名字。
· **v19.179 B1-b**：現價跌破紅 K 低點時分母為負，舊碼 `max(..., 0.01)`
  會把盈虧比夾成數千倍的假數字。
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from shared.signal_thresholds import BIG_RED_STOP_BUFFER_PCT
from src.compute.strategy.entry_stop_levels import (
    DEFAULT_LOOKBACK_BARS,
    EntryStopLevels,
    SupportResistance,
    compute_entry_stop_levels,
    compute_support_resistance,
)


def _bar(o, h, l, c, v):
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def _df(bars: list[dict]):
    return pd.DataFrame(bars)


def _flat(n: int, *, close=100.0, vol=1000):
    """n 根平盤黑 K（close < open）—— 不會被選為紅 K。"""
    return [_bar(close + 1, close + 1, close - 1, close, vol) for _ in range(n)]


# ════════════════════════════════════════════════════════════════════
# 1. 核心數學
# ════════════════════════════════════════════════════════════════════
class TestMath:

    def _one_big_red(self):
        # 5 根填充 + 1 根大量紅 K（low=90, high=110）
        return _df(_flat(5) + [_bar(95.0, 110.0, 90.0, 105.0, 99999)])

    def test_entry_half_is_midpoint(self):
        _r = compute_entry_stop_levels(self._one_big_red(), current_price=100.0)
        assert math.isclose(_r.entry_half, 100.0, rel_tol=1e-9), "(110+90)/2 = 100"

    def test_abs_stop_uses_ssot_buffer(self):
        _r = compute_entry_stop_levels(self._one_big_red(), current_price=100.0)
        _expect = round(90.0 * (1 - BIG_RED_STOP_BUFFER_PCT / 100.0), 2)
        assert math.isclose(_r.abs_stop, _expect, rel_tol=1e-9)
        assert math.isclose(_r.abs_stop, 89.55, rel_tol=1e-9), "紅K低點 90 × 0.995"

    def test_stop_distance_pct(self):
        _r = compute_entry_stop_levels(self._one_big_red(), current_price=100.0)
        # (100 − 89.55) / 100 × 100 = 10.45%
        # ⚠️ abs_tol 不可設 0.05：(100−89.55) 在二進位下是 10.450000000000003，
        #    round(...,1) 給 10.5，而 |10.5 − 10.45| = 0.05000000000000071 > 0.05
        #    → 剛好卡在邊界外。容差要大於「四捨五入到小數 1 位」的半格（0.05）。
        assert math.isclose(_r.stop_distance_pct, 10.45, abs_tol=0.1)

    def test_risk_reward_varies_with_anchor(self):
        """核心賣點：盈虧比必須**因股而異**（分母是紅K低點，不是現價的固定倍數）。

        這正是 v19.179 B1-b 保留下來的那一個 —— 固定 % 版的 RR 恆為 0.625。
        """
        _a = compute_entry_stop_levels(
            _df(_flat(5) + [_bar(95.0, 110.0, 90.0, 105.0, 99999)]),
            current_price=100.0, take_profit_price=105.0)
        _b = compute_entry_stop_levels(
            _df(_flat(5) + [_bar(95.0, 110.0, 98.0, 105.0, 99999)]),
            current_price=100.0, take_profit_price=105.0)
        assert _a.risk_reward is not None and _b.risk_reward is not None
        assert not math.isclose(_a.risk_reward, _b.risk_reward, rel_tol=1e-6), (
            "兩檔錨點不同卻算出同一個盈虧比 → 又變回結構常數了"
        )

    def test_risk_reward_formula(self):
        _r = compute_entry_stop_levels(self._one_big_red(),
                                       current_price=100.0, take_profit_price=105.0)
        # (105 − 100) / (100 − 89.55) = 5 / 10.45 ≈ 0.48
        assert math.isclose(_r.risk_reward, 0.48, abs_tol=0.01)

    def test_picks_highest_volume_red_candle(self):
        _r = compute_entry_stop_levels(_df(_flat(5) + [
            _bar(95.0, 100.0, 94.0, 99.0, 500),      # 紅K，量小
            _bar(95.0, 120.0, 80.0, 110.0, 99999),   # 紅K，量最大 ← 應選這根
            _bar(95.0, 101.0, 93.0, 98.0, 800),      # 紅K，量小
        ]), current_price=100.0)
        assert math.isclose(_r.abs_stop, round(80.0 * 0.995, 2), rel_tol=1e-9)


# ════════════════════════════════════════════════════════════════════
# 2. §1：算不出來時的三態
# ════════════════════════════════════════════════════════════════════
class TestUnavailableStates:

    def test_no_red_candle(self):
        """全黑 K → 無錨點。§1：不可退回固定 % 停損。"""
        _r = compute_entry_stop_levels(_df(_flat(30)), current_price=100.0)
        assert not _r.has_anchor
        assert _r.abs_stop is None and _r.risk_reward is None
        assert _r.unavailable_reason and "錨點" in _r.unavailable_reason

    def test_price_below_anchor(self):
        """現價已跌破紅K低點 → 分母為負。舊碼會夾成 0.01 噴出數千倍假數字。"""
        _r = compute_entry_stop_levels(
            _df(_flat(5) + [_bar(95.0, 110.0, 90.0, 105.0, 99999)]),
            current_price=80.0, take_profit_price=105.0)
        assert _r.has_anchor, "錨點本身仍算得出來"
        assert _r.risk_reward is None, "分母為負卻算出盈虧比"
        assert "跌破" in (_r.unavailable_reason or "")
        assert _r.stop_distance_pct is not None and _r.stop_distance_pct < 0, (
            "現價低於停損線時距離應為負，讓畫面看得出已破線"
        )

    def test_no_take_profit_price(self):
        _r = compute_entry_stop_levels(
            _df(_flat(5) + [_bar(95.0, 110.0, 90.0, 105.0, 99999)]),
            current_price=100.0)
        assert _r.has_anchor and _r.risk_reward is None
        assert "停利" in (_r.unavailable_reason or "")

    def test_reason_always_present_when_rr_none(self):
        """§1：不可只給 None 不說為什麼。"""
        for _kw in (
            dict(df=_df(_flat(30)), current_price=100.0),
            dict(df=_df(_flat(2)), current_price=100.0),
            dict(df=_df(_flat(5) + [_bar(95.0, 110.0, 90.0, 105.0, 99999)]),
                 current_price=100.0),
        ):
            _r = compute_entry_stop_levels(**_kw)
            assert _r.risk_reward is None
            assert _r.unavailable_reason, "算不出盈虧比卻沒說原因"

    def test_never_returns_zero_as_stop(self):
        """絕不可回 0 —— 「停損價 0 元」會被讀成有效價位。"""
        _r = compute_entry_stop_levels(_df(_flat(30)), current_price=100.0)
        assert _r.abs_stop is None and _r.abs_stop != 0


# ════════════════════════════════════════════════════════════════════
# 3. S4 v19.78：NaN volume（新舊 pandas 行為統一）
# ════════════════════════════════════════════════════════════════════
class TestNaNVolume:

    def test_all_nan_volume_returns_none(self):
        """全 NaN → 不選任何紅K。舊 pandas 會 IndexError、新版會靜默選錯。"""
        _r = compute_entry_stop_levels(_df(_flat(5) + [
            _bar(95.0, 110.0, 90.0, 105.0, float("nan")),
            _bar(95.0, 120.0, 80.0, 110.0, float("nan")),
        ]), current_price=100.0)
        assert not _r.has_anchor
        assert _r.unavailable_reason and "成交量" in _r.unavailable_reason

    def test_partial_nan_picks_valid_max(self):
        """部分 NaN → 從有效的那些裡選最大量，不因 NaN 而整個放棄。"""
        _r = compute_entry_stop_levels(_df(_flat(5) + [
            _bar(95.0, 120.0, 80.0, 110.0, float("nan")),   # 量未知，不可選
            _bar(95.0, 110.0, 90.0, 105.0, 5000),           # ← 應選這根
        ]), current_price=100.0)
        assert math.isclose(_r.abs_stop, round(90.0 * 0.995, 2), rel_tol=1e-9)

    def test_no_volume_column(self):
        _d = _df(_flat(5) + [_bar(95.0, 110.0, 90.0, 105.0, 1)]).drop(columns=["volume"])
        assert not compute_entry_stop_levels(_d, current_price=100.0).has_anchor


# ════════════════════════════════════════════════════════════════════
# 4. 紅 K 定義的兩套 fallback
# ════════════════════════════════════════════════════════════════════
class TestRedCandleDefinition:

    def test_uses_open_when_available(self):
        _r = compute_entry_stop_levels(
            _df(_flat(5) + [_bar(95.0, 110.0, 90.0, 105.0, 99999)]),
            current_price=100.0)
        assert _r.has_anchor

    def test_falls_back_to_prev_close(self):
        """無 open 欄 → 退為「上漲日」（close > 前一日 close）。"""
        _d = pd.DataFrame({
            "close": [100.0] * 5 + [120.0],
            "high": [101.0] * 5 + [125.0],
            "low": [99.0] * 5 + [115.0],
            "volume": [100] * 5 + [99999],
        })
        _r = compute_entry_stop_levels(_d, current_price=120.0)
        assert _r.has_anchor
        assert math.isclose(_r.abs_stop, round(115.0 * 0.995, 2), rel_tol=1e-9)

    def test_missing_high_low_falls_back_to_close(self):
        _d = pd.DataFrame({
            "open": [101.0] * 5 + [95.0],
            "close": [100.0] * 5 + [105.0],
            "volume": [100] * 5 + [99999],
        })
        _r = compute_entry_stop_levels(_d, current_price=105.0)
        # high/low 缺 → 都用 close=105 → entry_half=105、stop=105×0.995
        assert math.isclose(_r.entry_half, 105.0, rel_tol=1e-9)


# ════════════════════════════════════════════════════════════════════
# 5. lookback 語意：現行是「近 N 根紅 K」不是「近 N 日」
# ════════════════════════════════════════════════════════════════════
class TestLookbackSemantics:

    def test_counts_red_candles_not_calendar_days(self):
        """釘住**現行行為**：先濾紅K、再取最後 N 根。

        ⚠️ 這與畫面標籤「近20日最大量的紅K」不符 —— 一檔震盪股的 20 根紅 K
        可能橫跨兩三個月。抽取階段刻意維持原行為（§8.5 重構不改行為）。
        哪天要改成真正的「近 N 日」，本測試會紅燈提醒**那是行為變更**：
        錨點會變 → 停損線會變 → 盈虧比會變，屬影響決策的改動，需 user 裁示。
        """
        # 前面放一根「很久以前」的超大量紅K，中間插 100 根黑K，
        # 再放 lookback_bars 根小量紅K。
        _bars = (
            [_bar(95.0, 200.0, 50.0, 150.0, 999999)]      # 遠古大量紅K
            + _flat(100)                                   # 100 根黑K
            + [_bar(95.0, 110.0, 90.0, 105.0, 10)          # N 根小量紅K
               for _ in range(DEFAULT_LOOKBACK_BARS)]
        )
        _r = compute_entry_stop_levels(_df(_bars), current_price=100.0)
        # 現行行為：tail(20) 只取最後 20 根**紅K** → 遠古那根被排除
        assert math.isclose(_r.abs_stop, round(90.0 * 0.995, 2), rel_tol=1e-9), (
            "遠古紅K 被選中了 —— lookback 語意變了"
        )

    def test_lookback_is_parameterised(self):
        """參數化過，改語意時不必動函式本體。"""
        _bars = ([_bar(95.0, 200.0, 50.0, 150.0, 999999)]
                 + [_bar(95.0, 110.0, 90.0, 105.0, 10) for _ in range(30)])
        _wide = compute_entry_stop_levels(_df(_bars), current_price=100.0,
                                          lookback_bars=100)
        assert math.isclose(_wide.abs_stop, round(50.0 * 0.995, 2), rel_tol=1e-9)


# ════════════════════════════════════════════════════════════════════
# 6. 邊界
# ════════════════════════════════════════════════════════════════════
class TestEdgeCases:

    @pytest.mark.parametrize("df", [None, pd.DataFrame(), pd.DataFrame({"close": [1.0]})])
    def test_insufficient_data(self, df):
        _r = compute_entry_stop_levels(df, current_price=100.0)
        assert not _r.has_anchor and _r.unavailable_reason

    def test_missing_close_column(self):
        _d = pd.DataFrame({"open": [1.0] * 10, "volume": [1] * 10})
        assert not compute_entry_stop_levels(_d, current_price=100.0).has_anchor

    @pytest.mark.parametrize("price", [0, -1])
    def test_bad_current_price(self, price):
        """0 / 負值 = 真的壞值 → 不算距離與盈虧比（錨點本身仍算得出）。

        ⚠️ `None` **不在**本清單：它是**文件化的預設行為**（退回 df 末根 close），
        由 `test_current_price_defaults_to_last_close` 覆蓋。
        原先把 None 併進來測，與那條測試自相矛盾 —— 錯的是這裡。
        """
        _r = compute_entry_stop_levels(
            _df(_flat(5) + [_bar(95.0, 110.0, 90.0, 105.0, 99999)]),
            current_price=price, take_profit_price=105.0)
        assert _r.has_anchor, "錨點不該因為現價壞掉而消失"
        assert _r.risk_reward is None and _r.stop_distance_pct is None

    def test_current_price_defaults_to_last_close(self):
        _d = _df(_flat(5) + [_bar(95.0, 110.0, 90.0, 105.0, 99999)])
        _r = compute_entry_stop_levels(_d, take_profit_price=120.0)
        assert _r.stop_distance_pct is not None, "未傳現價時應由 df 末根 close 取"

    def test_never_raises(self):
        for _bad in (None, pd.DataFrame(),
                     pd.DataFrame({"close": ["x"] * 10, "volume": ["y"] * 10})):
            assert isinstance(
                compute_entry_stop_levels(_bad, current_price=100.0), EntryStopLevels)

    def test_result_is_frozen(self):
        with pytest.raises(Exception):
            compute_entry_stop_levels(_df(_flat(10))).abs_stop = 1.0  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════
# 6b. 近 N 日壓力 / 支撐
# ════════════════════════════════════════════════════════════════════
class TestSupportResistance:

    def _ramp(self):
        """10 根，high 由 100 遞增到 109、low 由 90 遞減到 81。"""
        return _df([_bar(95.0, 100.0 + i, 90.0 - i, 95.0, 100) for i in range(10)])

    def test_high_low_and_distances(self):
        _r = compute_support_resistance(self._ramp(), current_price=100.0)
        assert math.isclose(_r.resistance, 109.0, rel_tol=1e-9)
        assert math.isclose(_r.support, 81.0, rel_tol=1e-9)
        assert math.isclose(_r.distance_to_resistance_pct, 9.0, abs_tol=0.1)
        assert math.isclose(_r.distance_to_support_pct, 19.0, abs_tol=0.1)

    def test_window_bars_reports_actual(self):
        """S5 v19.78 教訓：資料不足時 tail(20) 只涵蓋實際根數，
        標籤卻寫死「近20日」→ 壓力/支撐被高估卻標 20 日。故回實際值供標示。"""
        assert compute_support_resistance(self._ramp(), current_price=100.0).window_bars == 10

    def test_window_caps_at_available(self):
        _long = _df([_bar(95.0, 100.0, 90.0, 95.0, 100) for _ in range(50)])
        assert compute_support_resistance(_long, current_price=95.0).window_bars == 20

    @pytest.mark.parametrize("df", [None, pd.DataFrame(), pd.DataFrame({"close": [1.0] * 3})])
    def test_insufficient_returns_all_none(self, df):
        """§1：算不出來回 None，**不可**回 0（「支撐 0 元」會被讀成有效價位）。"""
        _r = compute_support_resistance(df, current_price=100.0)
        assert _r.resistance is None and _r.support is None
        assert _r.distance_to_support_pct is None

    def test_missing_high_low_columns(self):
        _d = pd.DataFrame({"close": [100.0] * 10, "volume": [1] * 10})
        assert compute_support_resistance(_d, current_price=100.0).resistance is None

    def test_price_defaults_to_last_close(self):
        assert compute_support_resistance(self._ramp()).distance_to_support_pct is not None

    def test_frozen(self):
        with pytest.raises(Exception):
            compute_support_resistance(self._ramp()).support = 1.0  # type: ignore[misc]

    def test_window_semantics_differ_from_entry_stop(self):
        """釘住兩個 lookback 的**語意差異**（兩者都預設 20，但意思不同）。

        `compute_support_resistance` 的 window = 最後 N 根 **K 線**（真的是近 N 日）；
        `compute_entry_stop_levels` 的 lookback = 最後 N 根 **紅 K**（可橫跨數月）。
        這條測試存在的理由：兩個 20 擺在一起太容易被後人當成同一個東西而「統一」掉。
        """
        _bars = ([_bar(95.0, 200.0, 50.0, 150.0, 999999)]      # 遠古大量紅K
                 + _flat(100)                                   # 100 根黑K
                 + [_bar(95.0, 110.0, 90.0, 105.0, 10)
                    for _ in range(DEFAULT_LOOKBACK_BARS)])
        _d = _df(_bars)
        # 壓力/支撐只看最後 20 根 K 線 → 看不到遠古那根的 low=50
        _sr = compute_support_resistance(_d, current_price=100.0, window=20)
        assert _sr.support is not None and _sr.support > 50.0
        # 紅K錨點取最後 20 根**紅K** → 同樣排除遠古那根（但理由不同）
        _esl = compute_entry_stop_levels(_d, current_price=100.0)
        assert _esl.abs_stop is not None and _esl.abs_stop > 50.0


# ════════════════════════════════════════════════════════════════════
# 7. L2 純度 + SSOT
# ════════════════════════════════════════════════════════════════════
def test_no_io_or_ui_imports():
    import ast

    import src.compute.strategy.entry_stop_levels as _m

    _tree = ast.parse(open(_m.__file__, encoding="utf-8").read())
    _mods: set[str] = set()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            _mods.update(a.name for a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            _mods.add(_n.module)
    _banned = ("requests", "streamlit", "yfinance", "src.data", "src.ui")
    _hits = sorted(m for m in _mods
                   if any(m == b or m.startswith(b + ".") for b in _banned))
    assert not _hits, f"L2 純函式出現 I/O / UI import：{_hits}"


def test_buffer_comes_from_ssot():
    """緩衝值必須來自 L0，不得在本模組寫死（§3.3）。

    原碼是 `round(_rk_low * 0.995, 2)` 的裸數字，抽取時一併收斂。
    """
    import ast

    import src.compute.strategy.entry_stop_levels as _m

    _tree = ast.parse(open(_m.__file__, encoding="utf-8").read())
    _imported = {
        a.name
        for _n in ast.walk(_tree)
        if isinstance(_n, ast.ImportFrom) and _n.module == "shared.signal_thresholds"
        for a in _n.names
    }
    assert "BIG_RED_STOP_BUFFER_PCT" in _imported

    _bad = [
        f"line {_n.lineno}: {_n.value}"
        for _n in ast.walk(_tree)
        if isinstance(_n, ast.Constant)
        and isinstance(_n.value, float)
        and math.isclose(_n.value, 0.995, rel_tol=1e-9)
    ]
    assert not _bad, "裸數字 0.995 又出現了：\n  " + "\n  ".join(_bad)
