"""tests/test_v4_strategy_engine_coverage.py — V4StrategyEngine 純函式覆蓋測試。

對應 src/compute/strategy/v4_strategy_engine.py (L2 純 compute 策略引擎)。

涵蓋:
- __init__:股本=0 raise / 欄位大小寫正規化 / foreign·trust 別名匹配 / NaN ffill
- check_macro_veto:紅/黃/綠燈三態 + SSOT 門檻 + API 斷線預設綠 + 壞值降級
- calc_relative_chips:外本比·投本比公式 / 無籌碼欄位降級 / 連續流入旗標
- find_overhead_resistance:<60 日不足 / VPOC 計算
- calculate_stop_loss:<5 筆新股 / min(MA20, 爆量紅K低) 防守線
- detect_vcp_breakout:資料不足 NONE / 結構欄位
- detect_false_breakout_v4:<20 不足 / SELL 假突破
- generate_report:六模組整合鍵

門檻 SSOT(shared/signal_thresholds.py):
  VIX_HIGH=25 / VIX_MEDIUM=20 / FUTURES_HIGH=-20000 / FUTURES_MEDIUM=-10000
  VPOC_PRESSURE_DISTANCE_THRESHOLD=0.15
顏色 SSOT(shared/colors.py): TRAFFIC_YELLOW="#eab308"
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.compute.strategy.v4_strategy_engine import V4StrategyEngine


def _make_df(n=150, seed=0):
    """穩定可重現的 K 線 DataFrame(固定 seed)。"""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n)
    return pd.DataFrame(
        {
            "close":       rng.uniform(50, 100, n),
            "open":        rng.uniform(50, 100, n),
            "low":         rng.uniform(40, 90, n),
            "volume":      rng.integers(1000, 10000, n),
            "foreign_net": rng.integers(-500, 2000, n),
            "trust_net":   rng.integers(-100, 500, n),
        },
        index=dates,
    )


# ── __init__ ───────────────────────────────────────────────────────────
class TestInit:
    def test_shares_total_zero_raises(self):
        with pytest.raises(ValueError):
            V4StrategyEngine(_make_df(60), {}, 0)

    def test_shares_total_negative_raises(self):
        with pytest.raises(ValueError):
            V4StrategyEngine(_make_df(60), {}, -100)

    def test_shares_total_none_raises(self):
        with pytest.raises(ValueError):
            V4StrategyEngine(_make_df(60), {}, None)

    def test_column_normalization_case_insensitive(self):
        df = pd.DataFrame(
            {
                "Close":            [10.0, 11.0],
                "Open":             [9.0, 10.5],
                "Low":              [8.0, 9.5],
                "Trading_Volume":   [100, 200],
                "Foreign_Investor": [50, 60],
                "Investment_Trust": [5, 6],
            }
        )
        eng = V4StrategyEngine(df, {}, 1000)
        # 正規化後標準欄位皆存在
        for col in ("close", "open", "low", "volume", "foreign_net", "trust_net"):
            assert col in eng.df.columns

    def test_macro_none_becomes_empty_dict(self):
        eng = V4StrategyEngine(_make_df(60), None, 1000)
        assert eng.macro == {}

    def test_nan_filled_no_inf(self):
        df = _make_df(60).astype({"close": float, "low": float})
        df.iloc[0, df.columns.get_loc("close")] = np.nan
        df.iloc[5, df.columns.get_loc("low")] = np.inf
        eng = V4StrategyEngine(df, {}, 1000)
        # ffill + fillna(0) + inf→0 後不應殘留 NaN / inf
        assert not eng.df["close"].isna().any()
        assert not np.isinf(eng.df[["close", "low"]].to_numpy(dtype=float)).any()


# ── Task 2: check_macro_veto ───────────────────────────────────────────
class TestMacroVeto:
    def _eng(self, macro):
        return V4StrategyEngine(_make_df(60), macro, 100000)

    def test_red_light_high_vix(self):
        # VIX 26 > 25(HIGH) → 紅燈, 持股上限 20
        r = self._eng({"vix": 26, "foreign_futures": 0}).check_macro_veto()
        assert r["level"] == "High Risk"
        assert r["max_position"] == 20
        assert r["color"] == "#da3633"

    def test_red_light_deep_short_futures(self):
        # 外資期貨 -25000 < -20000 → 紅燈(即使 VIX 低)
        r = self._eng({"vix": 12, "foreign_futures": -25000}).check_macro_veto()
        assert r["level"] == "High Risk"
        assert r["max_position"] == 20

    def test_yellow_light_medium(self):
        # VIX 22:>20(MEDIUM) 但 <=25(HIGH), 期貨不觸發 → 黃燈
        r = self._eng({"vix": 22, "foreign_futures": 0}).check_macro_veto()
        assert r["level"] == "Medium Risk"
        assert r["max_position"] == 50
        assert r["color"] == "#eab308"  # TRAFFIC_YELLOW SSOT

    def test_green_light_safe(self):
        r = self._eng({"vix": 15, "foreign_futures": 0}).check_macro_veto()
        assert r["level"] == "Safe"
        assert r["max_position"] == 100
        assert r["color"] == "#2ea043"

    def test_api_disconnect_defaults_green(self):
        # 空 macro → vix 預設 15 → 綠燈(保守安全)
        r = self._eng({}).check_macro_veto()
        assert r["level"] == "Safe"
        assert r["vix"] == 15

    def test_bad_vix_value_degrades_to_default(self):
        # 壞字串 vix → 降級 15 → 綠燈
        r = self._eng({"vix": "garbage", "foreign_futures": "nope"}).check_macro_veto()
        assert r["level"] == "Safe"
        assert r["vix"] == 15
        assert r["futures"] == 0


# ── Task 1: calc_relative_chips ────────────────────────────────────────
class TestRelativeChips:
    def test_missing_chip_columns_returns_none(self):
        df = _make_df(60)[["close", "open", "low", "volume"]]
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.calc_relative_chips()
        assert r["foreign_ratio"] is None
        assert r["trust_ratio"] is None
        assert r["signal"] == "⚪ 無籌碼資料"

    def test_strong_concentration_signal(self):
        # 外資 5 日各 +2000 張, 股本 100000 → 外本比 = 10000/100000*100 = 10% > 0.5
        df = pd.DataFrame(
            {
                "close":       [50.0] * 5,
                "open":        [50.0] * 5,
                "low":         [49.0] * 5,
                "volume":      [1000] * 5,
                "foreign_net": [2000] * 5,
                "trust_net":   [0] * 5,
            }
        )
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.calc_relative_chips()
        assert r["foreign_ratio"] == pytest.approx(10.0)
        assert r["trust_ratio"] == pytest.approx(0.0)
        assert "強勢集中" in r["signal"]
        # 連續 3 日流入 >0.1% → 旗標
        assert r["consecutive"] == 3
        assert "連續3日流入" in r["signal"]

    def test_outflow_signal(self):
        # 外資 5 日各 -2000 → 外本比 -10% < -0.5 → 渙散出逃
        df = pd.DataFrame(
            {
                "close":       [50.0] * 5,
                "open":        [50.0] * 5,
                "low":         [49.0] * 5,
                "volume":      [1000] * 5,
                "foreign_net": [-2000] * 5,
                "trust_net":   [0] * 5,
            }
        )
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.calc_relative_chips()
        assert r["foreign_ratio"] == pytest.approx(-10.0)
        assert "渙散出逃" in r["signal"]
        assert r["consecutive"] == 0

    def test_neutral_signal_small_flow(self):
        # 小流量 → 中性(各 +10 張 / 100000 → 0.01% 遠低門檻)
        df = pd.DataFrame(
            {
                "close":       [50.0] * 5,
                "open":        [50.0] * 5,
                "low":         [49.0] * 5,
                "volume":      [1000] * 5,
                "foreign_net": [10] * 5,
                "trust_net":   [5] * 5,
            }
        )
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.calc_relative_chips()
        assert "中性" in r["signal"]


# ── Task 3: find_overhead_resistance ───────────────────────────────────
class TestOverheadResistance:
    def test_insufficient_data_under_60(self):
        eng = V4StrategyEngine(_make_df(30), {}, 100000)
        r = eng.find_overhead_resistance()
        assert r["vpoc_price"] is None
        assert r["has_pressure"] is False
        assert "資料不足60日" in r["msg"]

    def test_vpoc_overhead_pressure_detected(self):
        # 大量集中在高價區(90~92), 現價在低位 80 → 上方套牢壓力
        n = 120
        close = np.full(n, 80.0)
        close[:60] = 91.0  # 前 60 日在 91, 大量
        volume = np.full(n, 100)
        volume[:60] = 100000  # 高價區為最大量 → VPOC 在高位
        df = pd.DataFrame(
            {
                "close":  close,
                "open":   close,
                "low":    close - 1,
                "volume": volume,
            },
            index=pd.date_range("2023-01-01", periods=n),
        )
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.find_overhead_resistance()
        assert r["vpoc_price"] is not None
        # VPOC(~91) 高於現價(80) 且距離 (91-80)/80 ≈ 13.75% < 15% → 有壓力
        assert r["vpoc_price"] > r["current_price"]
        assert r["has_pressure"] is True

    def test_price_above_vpoc_no_pressure(self):
        # 大量集中在低價(70), 現價在高位(95) → 站上 VPOC, 壓力解除
        n = 120
        close = np.full(n, 95.0)
        close[:60] = 70.0
        volume = np.full(n, 100)
        volume[:60] = 100000
        df = pd.DataFrame(
            {
                "close":  close,
                "open":   close,
                "low":    close - 1,
                "volume": volume,
            },
            index=pd.date_range("2023-01-01", periods=n),
        )
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.find_overhead_resistance()
        assert r["has_pressure"] is False
        assert r["current_price"] >= r["vpoc_price"]


# ── Task 4: calculate_stop_loss ────────────────────────────────────────
class TestStopLoss:
    def test_insufficient_data_under_5(self):
        eng = V4StrategyEngine(_make_df(4), {}, 100000)
        r = eng.calculate_stop_loss()
        assert r["stop_loss"] is None
        assert "新股觀望" in r["msg"]

    def test_stop_loss_is_min_of_ma_and_breakout(self):
        # 全平盤(close=open=50, low=48) → 無爆量紅K → breakout_low = 48*0.98
        # MA20 = 50 → stop_loss = min(50, 47.04) = 47.04
        df = pd.DataFrame(
            {
                "close":  [50.0] * 30,
                "open":   [50.0] * 30,
                "low":    [48.0] * 30,
                "volume": [1000] * 30,
            },
            index=pd.date_range("2023-01-01", periods=30),
        )
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.calculate_stop_loss()
        assert r["ma20"] == pytest.approx(50.0)
        assert r["breakout_low"] == pytest.approx(round(48.0 * 0.98, 2))
        assert r["stop_loss"] == pytest.approx(min(50.0, round(48.0 * 0.98, 2)))
        assert r["current_price"] == pytest.approx(50.0)

    def test_short_history_uses_ma5_fallback(self):
        # 6 筆(>=5 但 <20) → 用 MA5 降級, 不崩潰
        df = _make_df(6)
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.calculate_stop_loss()
        assert r["stop_loss"] is not None
        assert r["ma20"] is not None  # 此處實為 MA5 值, 但鍵仍叫 ma20


# ── Task 5: detect_vcp_breakout ────────────────────────────────────────
class TestVcpBreakout:
    def test_insufficient_data_returns_none_signal(self):
        eng = V4StrategyEngine(_make_df(30), {}, 100000)
        r = eng.detect_vcp_breakout(lookback_days=60)
        assert r["signal"] == "NONE"
        assert "資料不足" in r["message"]

    def test_returns_expected_structure(self):
        eng = V4StrategyEngine(_make_df(80), {}, 100000)
        r = eng.detect_vcp_breakout(lookback_days=60)
        assert r["signal"] in ("BUY", "HOLD")
        assert len(r["vcp_stages"]) == 3
        # volume_dry / breakout 為布林語意(可能是 numpy bool)
        assert bool(r["volume_dry"]) in (True, False)
        assert bool(r["breakout"]) in (True, False)
        assert "target_price" in r and "stop_loss" in r


# ── Task 6: detect_false_breakout_v4 ───────────────────────────────────
class TestFalseBreakout:
    def test_insufficient_data_holds(self):
        eng = V4StrategyEngine(_make_df(10), {}, 100000)
        r = eng.detect_false_breakout_v4()
        assert r["signal"] == "HOLD"
        assert "資料不足" in r["message"]

    def test_false_breakout_sell_signal(self):
        # 構造:今日創新高 + 天量 + 黑K(收<開) → SELL
        n = 30
        df = pd.DataFrame(
            {
                "high":   [100.0] * (n - 1) + [120.0],   # 末日創新高
                "close":  [98.0] * (n - 1) + [101.0],    # 收盤遠低於高(黑K)
                "open":   [97.0] * (n - 1) + [115.0],    # 末日 open>close → 黑K
                "low":    [95.0] * n,
                "volume": [1000] * (n - 1) + [999999],   # 末日天量
            },
            index=pd.date_range("2023-01-01", periods=n),
        )
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.detect_false_breakout_v4()
        assert r["is_new_high"] is True
        assert r["is_huge_vol"] is True
        assert r["is_ugly_k"] is True
        assert r["signal"] == "SELL"

    def test_normal_no_false_breakout_holds(self):
        # 平穩量價, 無創高無天量 → HOLD
        df = pd.DataFrame(
            {
                "high":   [100.0] * 30,
                "close":  [99.0] * 30,
                "open":   [98.0] * 30,
                "low":    [97.0] * 30,
                "volume": [1000] * 30,
            },
            index=pd.date_range("2023-01-01", periods=30),
        )
        eng = V4StrategyEngine(df, {}, 100000)
        r = eng.detect_false_breakout_v4()
        assert r["signal"] == "HOLD"


# ── generate_report 整合 ───────────────────────────────────────────────
def test_generate_report_keys():
    eng = V4StrategyEngine(_make_df(150), {"vix": 26, "foreign_futures": -25000}, 100000)
    r = eng.generate_report()
    for key in ("macro_veto", "chip_analysis", "resistance", "stop_loss",
                "vcp_breakout", "false_breakout"):
        assert key in r


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
