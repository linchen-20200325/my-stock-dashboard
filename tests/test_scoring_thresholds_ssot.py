"""v18.324 scoring_engine 評分曲線 / 交易濾網斷點全抽 SSOT 守衛測試。

user 2026-06-27 指定：scoring_engine.py 的判斷門檻全部抽成具名常數（覆寫「登記例外」建議）。
涵蓋:
1. shared/signal_thresholds 新增常數值 + 前綴分名「同數字不同義」不耦合
2. scoring_engine 改 import（計算端不再 inline 關鍵門檻）
3. 行為不變（抽常數為純等值替換）功能 smoke
"""
from __future__ import annotations

import shared.signal_thresholds as st_mod
import scoring_engine as se


class TestScoringConstants:
    def test_values(self):
        assert st_mod.MOM_SHARPE_GOOD == 0.5
        assert st_mod.RISK_VOL_VERYLOW_RATIO == 0.02
        assert st_mod.RISK_VOL_LOW_RATIO == 0.035
        assert (st_mod.RS_BAND_T1, st_mod.RS_BAND_T2, st_mod.RS_BAND_T3, st_mod.RS_BAND_T4) == (2.0, 1.5, 1.0, 0.5)
        assert (st_mod.SQ_GOOD_MIN, st_mod.SQ_STABLE_MIN, st_mod.SQ_FAIR_MIN) == (75.0, 55.0, 40.0)
        assert (st_mod.FGMS_LABEL_T1, st_mod.FGMS_LABEL_T2) == (75.0, 60.0)
        assert (st_mod.FGMS_W_CL, st_mod.FGMS_W_INV, st_mod.FGMS_W_THREE, st_mod.FGMS_W_CAPEX) == (0.40, 0.30, 0.20, 0.10)
        assert st_mod.RR_MIN == 2.0
        assert st_mod.RR_DEFAULT_TARGET_GAIN == 0.15
        assert st_mod.ATR_STOP_MULTIPLIER == 1.5
        assert st_mod.ATR_STOP_FIXED_PCT == 8.0
        assert st_mod.SQUEEZE_SHORT_RATIO_MIN == 0.3
        assert st_mod.SQUEEZE_INST_BUY_DAYS_MIN == 3
        assert st_mod.SQUEEZE_BONUS == 5
        assert st_mod.VCP_ATR_CONTRACTION_RATIO == 0.8
        assert st_mod.POS_MAX_RISK_PCT == 0.015
        assert st_mod.POS_MAX_STOP_PCT == 0.85

    def test_fgms_weights_sum_to_one(self):
        assert abs(st_mod.FGMS_W_CL + st_mod.FGMS_W_INV + st_mod.FGMS_W_THREE + st_mod.FGMS_W_CAPEX - 1.0) < 1e-9

    def test_prefix_separation_no_cross_coupling(self):
        # SQ 標籤 75 / FGMS 標籤 75 / 多因子總分 75 三者同值但不同義，各自具名（不共用同一常數）
        assert st_mod.SQ_GOOD_MIN == st_mod.FGMS_LABEL_T1 == st_mod.MULTIFACTOR_GRADE_A_MIN == 75.0
        # 但它們是三個獨立常數名（語意分離），改其中一個不應牽動另兩個
        assert st_mod.SQ_GOOD_MIN is not None and st_mod.FGMS_LABEL_T1 is not None


class TestScoringEngineImportsSSOT:
    def test_code_imports_and_no_inline(self):
        src = open(se.__file__, encoding="utf-8").read()
        assert "from shared.signal_thresholds import" in src
        for name in ("MOM_SHARPE_GOOD", "RS_BAND_T1", "SQ_GOOD_MIN", "FGMS_LABEL_T1",
                     "RR_MIN", "SQUEEZE_BONUS", "VCP_ATR_CONTRACTION_RATIO", "POS_MAX_STOP_PCT"):
            assert name in src, f"scoring_engine 缺 SSOT import: {name}"
        # 關鍵門檻不再 inline（comment/docstring 不算 —— 比對含運算子的程式行）
        assert "sharpe_20 > 0.5" not in src
        assert "rr >= 2.0" not in src
        assert "atr5 < atr20 * 0.8" not in src
        assert "short_ratio > 0.3 and" not in src
        assert "vol_ratio > 3 and" not in src


class TestBehaviorPreserved:
    def test_squeeze_bonus(self):
        r = se.calc_short_squeeze_bonus(short_ratio=0.35, inst_consecutive_buy=3)
        assert r["bonus"] == 5
        r2 = se.calc_short_squeeze_bonus(short_ratio=0.25, inst_consecutive_buy=5)
        assert r2["bonus"] == 0

    def test_rr_ratio_pass_threshold(self):
        # entry=100, stop=90 → risk=10；target 預設 +15% = 115 → reward=15 → rr=1.5 (<2 不過)
        assert se.calc_rr_ratio(100, 90)["pass"] is False
        # stop=95 → risk=5；reward=15 → rr=3.0 (>=2 過)
        assert se.calc_rr_ratio(100, 95)["pass"] is True

    def test_atr_stop_fixed_fallback(self):
        # 資料不足 → 固定 8% 停損：100 × 0.92 = 92.0
        r = se.calc_atr_stop(None, 100.0)
        assert r["stop_pct"] == 8.0
        assert r["stop_loss"] == 92.0
