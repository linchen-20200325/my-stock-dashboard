"""v18.323 財報體檢 MJ 門檻 SSOT + 3 漂移修正 golden test。

涵蓋:
1. shared/financial_health_thresholds 常數值
2. golden — prompt 文字內的數值 == SSOT 常數（防 prompt 與 code 再次漂移）
3. 3 漂移修正的功能驗證（_no_ai_profitability 邊界行為）
4. _no_ai_* 計算端不再 inline（改 import 常數）
"""
from __future__ import annotations

import sys
import types

# ── Minimal Streamlit stub so financial_health_engine can import ──────────────
_st = types.ModuleType("streamlit")
_st.cache_data = lambda **kw: (lambda f: f)
_st.secrets = {}
sys.modules.setdefault("streamlit", _st)

import shared.financial_health_thresholds as MJ  # noqa: E402
from src.services import financial_health_engine as fhe  # noqa: E402
from src.services import _no_ai_profitability  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# 1. 常數值
# ─────────────────────────────────────────────────────────────────────────────
class TestMjConstants:
    def test_values(self):
        assert MJ.MJ_CASH_RATIO_SAFE_PCT == 25.0
        assert MJ.MJ_CASH_RATIO_WATCH_PCT == 10.0
        assert MJ.MJ_DSO_FAST_DAYS == 15.0
        assert MJ.MJ_DSO_SLOW_DAYS == 90.0
        assert MJ.MJ_DEBT_RATIO_EXCELLENT_PCT == 40.0
        assert MJ.MJ_DEBT_RATIO_PASS_PCT == 60.0
        assert MJ.MJ_DEBT_RATIO_WARN_PCT == 70.0
        assert MJ.MJ_CURRENT_RATIO_MIN_PCT == 300.0
        assert MJ.MJ_QUICK_RATIO_MIN_PCT == 150.0
        assert MJ.MJ_GROSS_MARGIN_GOOD_PCT == 40.0
        assert MJ.MJ_MOS_STRONG_PCT == 60.0
        assert MJ.MJ_DUPONT_LEVERAGE_DEBT_PCT == 65.0
        assert MJ.MJ_ROE_LEVERAGE_CHECK_PCT == 15.0
        assert MJ.MJ_EARNINGS_QUALITY_MIN_PCT == 100.0

    def test_debt_separation_invariant(self):
        # 一般負債結構安全線 vs 杜邦槓桿警報 為兩個不同用途常數，刻意不相等
        assert MJ.MJ_DEBT_RATIO_PASS_PCT != MJ.MJ_DUPONT_LEVERAGE_DEBT_PCT  # 60 vs 65
        assert MJ.MJ_DEBT_RATIO_PASS_PCT < MJ.MJ_DUPONT_LEVERAGE_DEBT_PCT < MJ.MJ_DEBT_RATIO_WARN_PCT


# ─────────────────────────────────────────────────────────────────────────────
# 2. golden — prompt 文字 == SSOT 常數（防再漂移）
# ─────────────────────────────────────────────────────────────────────────────
class TestPromptGoldenAgainstSSOT:
    def test_survival_prompt(self):
        assert f">= {int(MJ.MJ_CASH_RATIO_SAFE_PCT)}%" in fhe._SURVIVAL_PROMPT
        assert f"< {int(MJ.MJ_DSO_FAST_DAYS)}天" in fhe._SURVIVAL_PROMPT

    def test_profitability_prompt_drift_fixed(self):
        # 漂移2修正：毛利率 Good 對齊 40%
        assert f"> {int(MJ.MJ_GROSS_MARGIN_GOOD_PCT)}% (Good)" in fhe._PROFITABILITY_PROMPT
        assert "> 20% (Good)" not in fhe._PROFITABILITY_PROMPT
        # 漂移3修正：安全邊際 Strong 對齊 60%
        assert f"> {int(MJ.MJ_MOS_STRONG_PCT)}% (Strong)" in fhe._PROFITABILITY_PROMPT
        # 漂移1修正：負債槓桿警報對齊 65%
        assert f"負債比 > {int(MJ.MJ_DUPONT_LEVERAGE_DEBT_PCT)}%" in fhe._PROFITABILITY_PROMPT
        assert "負債比 > 60%" not in fhe._PROFITABILITY_PROMPT

    def test_structure_prompt(self):
        assert f"< {int(MJ.MJ_DEBT_RATIO_PASS_PCT)}%" in fhe._FINANCIAL_STRUCTURE_PROMPT

    def test_solvency_prompt(self):
        assert f"> {int(MJ.MJ_CURRENT_RATIO_MIN_PCT)}%" in fhe._SOLVENCY_PROMPT
        assert f"> {int(MJ.MJ_QUICK_RATIO_MIN_PCT)}%" in fhe._SOLVENCY_PROMPT

    def test_advanced_prompt(self):
        assert f"> {int(MJ.MJ_EARNINGS_QUALITY_MIN_PCT)}%" in fhe._ADVANCED_DIAGNOSTIC_PROMPT
        # advanced 槓桿門檻一致採 65
        assert f"負債比率(%) > {int(MJ.MJ_DUPONT_LEVERAGE_DEBT_PCT)}%" in fhe._ADVANCED_DIAGNOSTIC_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# 3. 3 漂移修正的功能驗證
# ─────────────────────────────────────────────────────────────────────────────
class TestDriftFixesFunctional:
    def _prof(self, fd):
        return _no_ai_profitability(fd)["Profitability_Module"]

    def test_mos_strong_now_requires_60(self):
        # MOS = 營業利益/毛利 = 50/100*100 = 50% → 修正後應為 Acceptable（修正前為 Strong）
        fd = {"毛利率(%)": 30, "營業收入(千)": 1000, "毛利(千)": 100,
              "營業利益(千)": 50, "稅後淨利(千)": 40, "股東權益(千)": 200, "負債比率(%)": 30}
        assert self._prof(fd)["Margin_Of_Safety"]["Status"] == "Acceptable"

    def test_mos_strong_at_60(self):
        # MOS = 60/100*100 = 60% → Strong
        fd = {"毛利率(%)": 30, "營業收入(千)": 1000, "毛利(千)": 100,
              "營業利益(千)": 60, "稅後淨利(千)": 40, "股東權益(千)": 200, "負債比率(%)": 30}
        assert self._prof(fd)["Margin_Of_Safety"]["Status"] == "Strong"

    def test_gross_good_now_requires_40(self):
        fd_good = {"毛利率(%)": 45, "營業收入(千)": 1000, "毛利(千)": 450,
                   "營業利益(千)": 100, "稅後淨利(千)": 80, "股東權益(千)": 200, "負債比率(%)": 30}
        fd_avg = {"毛利率(%)": 35, "營業收入(千)": 1000, "毛利(千)": 350,
                  "營業利益(千)": 100, "稅後淨利(千)": 80, "股東權益(千)": 200, "負債比率(%)": 30}
        assert self._prof(fd_good)["Gross_Margin"]["Status"] == "Good"
        assert self._prof(fd_avg)["Gross_Margin"]["Status"] == "Average"

    def test_leverage_alarm_separation(self):
        # debt=62（介於結構線 60 與槓桿線 65 之間）+ ROE>15 → 槓桿警報不應觸發（用 65 而非 60）
        # roe = (ni*4)/eq*100 = (10*4)/200*100 = 20 > 15
        fd_no = {"毛利率(%)": 30, "營業收入(千)": 1000, "毛利(千)": 300,
                 "營業利益(千)": 100, "稅後淨利(千)": 10, "股東權益(千)": 200, "負債比率(%)": 62}
        fd_yes = {**fd_no, "負債比率(%)": 70}
        assert self._prof(fd_no)["ROE"]["Leverage_Warning"] == "None"
        assert self._prof(fd_yes)["ROE"]["Leverage_Warning"] == "槓桿膨脹警報"


# ─────────────────────────────────────────────────────────────────────────────
# 4. 計算端不再 inline（改 import 常數）
# ─────────────────────────────────────────────────────────────────────────────
class TestNoInlineMagicInCode:
    def test_code_imports_ssot(self):
        src = open(fhe.__file__, encoding="utf-8").read()
        assert "from shared.financial_health_thresholds import" in src
        # _no_ai_profitability 安全邊際不再 inline 20
        assert "mos >= 20" not in src
        # _no_ai_solvency 不再 inline 300/150
        assert "cr > 300" not in src
        assert "qr > 150" not in src
