# -*- coding: utf-8 -*-
"""v19.94 — 批次3(a) KD 鈍化背離（§7 user 核准:偵測 + 接進評分 + drift 修）。

- analyze_kd_state:高/低檔鈍化(連 KD_PASSIVATION_DAYS 日) + 頂/底背離(兩窗高低點)。
- calc_health_score KD tier 分流:高檔鈍化不誤扣(15)、頂背離降(5)、底背離加(13)。
- exit_signals KD高檔死叉 70 → SSOT KD_OVERBOUGHT_LEVEL(80) drift 修。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.compute.scoring.scoring_helpers import calc_health_score
from src.compute.strategy.tech_indicators import analyze_kd_state

REPO = Path(__file__).resolve().parent.parent


def _df(closes):
    """intraday range ±0.4% → 上升趨勢 K 落在 (80,100) 而非飽和 100(利於 K>D 判定)。"""
    c = [float(x) for x in closes]
    return pd.DataFrame({"close": c,
                         "high": [x * 1.004 for x in c],
                         "low": [x * 0.996 for x in c],
                         "volume": [1e6] * len(c)})


# ───────────────── analyze_kd_state 偵測 ─────────────────
class TestKdPassivation:
    def test_high_passivation_on_strong_uptrend(self):
        st = analyze_kd_state(_df(range(100, 130)))
        assert st is not None
        assert st["high_passivation"] is True
        assert st["low_passivation"] is False
        assert "高檔鈍化" in st["label"]

    def test_low_passivation_on_strong_downtrend(self):
        st = analyze_kd_state(_df(range(130, 100, -1)))
        assert st["low_passivation"] is True
        assert st["high_passivation"] is False

    def test_insufficient_data_returns_none(self):
        assert analyze_kd_state(_df([10, 11, 12])) is None

    def test_mild_chop_no_passivation(self):
        closes = 100 + np.sin(np.arange(60)) * 0.5   # 小幅震盪 → K 不黏極值
        st = analyze_kd_state(_df(closes))
        assert st is not None
        assert not st["high_passivation"] and not st["low_passivation"]


class TestKdDivergence:
    def test_bearish_divergence(self):
        # 前半急漲到 120 峰(K 飽和)→ 深跌 → 快速回到 121(略高高點,K 尚在追) = 頂背離
        lead = list(np.linspace(88, 100, 12))
        old = list(np.linspace(100, 120, 20))
        new = list(np.linspace(120, 95, 14)) + list(np.linspace(96, 121, 6))
        st = analyze_kd_state(_df(lead + old + new))
        assert st is not None
        assert st["bearish_divergence"] is True
        assert st["bullish_divergence"] is False
        assert "頂背離" in st["label"]

    def test_bullish_divergence(self):
        # 前半急跌到 100 谷(K 觸底)→ 急彈 → 回落到 99(略低低點,K 尚高) = 底背離
        lead = list(np.linspace(132, 120, 12))
        old = list(np.linspace(120, 100, 20))
        new = list(np.linspace(100, 125, 14)) + list(np.linspace(124, 99, 6))
        st = analyze_kd_state(_df(lead + old + new))
        assert st is not None
        assert st["bullish_divergence"] is True
        assert st["bearish_divergence"] is False


# ───────────────── calc_health_score 接線（monkeypatch 隔離 wiring 邏輯）─────────
class TestHealthScoreWiring:
    _DF = None

    def setup_method(self):
        self._DF = _df(range(100, 140))   # 內容不重要(analyze_kd_state 被 patch)

    def _kd_tier(self, monkeypatch, state, k_val, d_val):
        monkeypatch.setattr(
            "src.compute.strategy.tech_indicators.analyze_kd_state",
            lambda df, period=9: state)
        _, details = calc_health_score(self._DF, None, None, None, k_val, d_val, None)
        return details["KD"]

    def test_high_jaw_passivation_keeps_15(self, monkeypatch):
        # 高檔黃叉(K>D,K≥80) + 高檔鈍化 → 15/15(不誤扣為 8)
        tier = self._kd_tier(monkeypatch, {"high_passivation": True}, 90.0, 85.0)
        assert tier[1] == 15 and "鈍化" in tier[0]

    def test_high_jaw_bearish_div_downgrades_to_5(self, monkeypatch):
        tier = self._kd_tier(monkeypatch, {"bearish_divergence": True}, 90.0, 85.0)
        assert tier[1] == 5 and "頂背離" in tier[0]

    def test_high_jaw_no_signal_stays_8(self, monkeypatch):
        # 無鈍化/背離(或 analyze 回 None) → 退回原「高檔黃叉注意」8
        tier = self._kd_tier(monkeypatch, None, 90.0, 85.0)
        assert tier[1] == 8

    def test_low_death_cross_bullish_div_boosts_to_13(self, monkeypatch):
        # 低檔死叉(K<D,K≤20) + 底背離 → 13/15(反轉向上)
        tier = self._kd_tier(monkeypatch, {"bullish_divergence": True}, 15.0, 20.0)
        assert tier[1] == 13 and "底背離" in tier[0]

    def test_low_death_cross_no_signal_stays_10(self, monkeypatch):
        tier = self._kd_tier(monkeypatch, {}, 15.0, 20.0)
        assert tier[1] == 10

    def test_clean_golden_cross_unchanged_15(self, monkeypatch):
        # K>D 且 K<80(純黃金交叉) → 不受鈍化/背離影響,維持 15
        tier = self._kd_tier(monkeypatch, {"bearish_divergence": True}, 60.0, 55.0)
        assert tier[1] == 15 and "黃金交叉" in tier[0]


# ───────────────── exit_signals drift ─────────────────
class TestExitSignalsDrift:
    def test_uses_ssot_not_literal_70(self):
        src = (REPO / "src/compute/scoring/exit_signals.py").read_text(encoding="utf-8")
        assert "float(k) > KD_OVERBOUGHT_LEVEL" in src
        assert "float(k) > 70" not in src


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
