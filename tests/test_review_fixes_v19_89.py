# -*- coding: utf-8 -*-
"""v19.89 — A~E backlog 批次3(a) 標準公式:RSI Wilder + ATR True Range。

user 授權位移訊號(§7):
- RSI:SMA → Wilder RMA(ewm α=1/period),對齊券商平台 70/30 門檻。
- ATR:當根 high-low → True Range max(H-L,|H-prevC|,|L-prevC|)+ Wilder 平滑,
  跳空計入波動 → 停損距離更貼實。SSOT compute_atr 收斂風險分級 + 停損兩處用途。
  VCP 收縮比刻意保留 high-low(門檻對其校準,列待一起回測)。
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from src.compute.scoring.scoring_engine import compute_atr, compute_rsi

REPO = Path(__file__).resolve().parent.parent


class TestRsiWilder:
    def test_all_up_near_100(self):
        assert float(compute_rsi(pd.Series(range(1, 31), dtype=float)).iloc[-1]) >= 99

    def test_all_down_near_0(self):
        assert float(compute_rsi(pd.Series(range(30, 0, -1), dtype=float)).iloc[-1]) <= 1

    def test_matches_wilder_ewm_not_sma(self):
        """數值須等於 Wilder(ewm α=1/period),且與舊 SMA 版不同。"""
        close = pd.Series([10, 11, 10.5, 12, 11.5, 13, 12, 14, 13, 15,
                           14, 16, 15, 17, 16, 18], dtype=float)
        period = 14
        got = float(compute_rsi(close, period).iloc[-1])
        # 手算 Wilder 參考
        delta = close.diff()
        g = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
        want = float((100 - 100 / (1 + g / (loss + 1e-10))).iloc[-1])
        assert math.isclose(got, want, rel_tol=1e-9)
        # 與 SMA 版不同(證實已改 Wilder)
        g_sma = delta.clip(lower=0).rolling(period).mean()
        l_sma = (-delta.clip(upper=0)).rolling(period).mean()
        sma_val = float((100 - 100 / (1 + g_sma / (l_sma + 1e-10))).iloc[-1])
        assert not math.isclose(got, sma_val, rel_tol=1e-6)

    def test_source_uses_ewm(self):
        src = (REPO / "src/compute/scoring/scoring_engine.py").read_text(encoding="utf-8")
        assert "ewm(alpha=1 / period, adjust=False)" in src
        # compute_rsi 不得再用 rolling(period).mean() 算 gain/loss
        assert "delta.clip(lower=0).rolling(period).mean()" not in src


class TestAtrTrueRange:
    def test_captures_overnight_gap(self):
        # 第 3 根隔夜跳空(前收 10.1 → 當根 low 14.8):TR 應遠大於 high-low
        df = pd.DataFrame({"high": [10, 10.2, 15, 15.1],
                           "low": [9.8, 10, 14.8, 15],
                           "close": [10, 10.1, 14.9, 15.05]})
        atr_tr = float(compute_atr(df, 2).iloc[-1])
        atr_hl = float((df["high"] - df["low"]).rolling(2).mean().iloc[-1])
        assert atr_tr > atr_hl

    def test_wilder_vs_simple_differ(self):
        df = pd.DataFrame({"high": [10 + i * 0.1 for i in range(30)],
                           "low": [9.5 + i * 0.1 for i in range(30)],
                           "close": [9.8 + i * 0.1 for i in range(30)]})
        w = float(compute_atr(df, 14, wilder=True).iloc[-1])
        s = float(compute_atr(df, 14, wilder=False).iloc[-1])
        assert w > 0 and s > 0

    def test_missing_high_low_degrades_no_crash(self):
        df = pd.DataFrame({"close": [10, 11, 10.5, 12]})
        assert float(compute_atr(df, 2).iloc[-1]) >= 0

    def test_atr_stop_and_risk_use_compute_atr(self):
        src = (REPO / "src/compute/scoring/scoring_engine.py").read_text(encoding="utf-8")
        # 風險分級 + 停損兩處改 compute_atr;VCP 保留 high-low(有註)
        assert "compute_atr(df, 14)" in src
        assert "(_hi - _lo).rolling(14).mean()" not in src, "風險分級舊 high-low 應已移除"
        assert "刻意保留當根 high-low range" in src, "VCP 保留須有說明註"


class TestAtrStopFunctional:
    def test_atr_stop_still_returns_valid_dict(self):
        import numpy as np
        from src.compute.scoring.scoring_engine import calc_atr_stop
        rng = np.linspace(100, 110, 30)
        df = pd.DataFrame({"high": rng + 1, "low": rng - 1, "close": rng})
        out = calc_atr_stop(df, entry_price=110.0)
        assert out["error"] is None
        assert out["atr"] is not None and out["atr"] > 0
        assert 0 < out["stop_pct"] < 50


class TestRsScoreNearZeroGuard:
    """v19.90 批次3(b):calc_rs_score 近零大盤分母防爆炸。"""

    def test_near_zero_index_routes_to_absolute(self):
        import pandas as pd
        from src.compute.scoring.scoring_engine import calc_rs_score
        stock = pd.DataFrame({"close": [100] * 250 + [105]})   # +5%
        idx = pd.DataFrame({"close": [100] * 250 + [100.01]})  # +0.01% 近零
        # 應走絕對漲幅路徑(+5% → 60),而非 rs=500 爆炸成 100
        assert calc_rs_score(stock, idx, period=250) == 60

    def test_normal_index_still_relative(self):
        import pandas as pd
        from src.compute.scoring.scoring_engine import calc_rs_score
        idx = pd.DataFrame({"close": [100] * 250 + [102.5]})   # +2.5%
        stock = pd.DataFrame({"close": [100] * 250 + [110]})   # +10% → rs=4 → 100
        assert calc_rs_score(stock, idx, period=250) == 100

    def test_source_uses_eps_not_eq_zero(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent
               / "src/compute/scoring/scoring_engine.py").read_text(encoding="utf-8")
        assert "abs(idx_chg) < RS_IDX_FLAT_EPS_PCT" in src
        assert "if idx_chg == 0:" not in src
