"""v18.323 財報體檢門檻 SSOT + 3 漂移修正 golden test。

涵蓋:
1. shared/financial_health_thresholds 常數值
2. golden — prompt 文字內的數值 == SSOT 常數（防 prompt 與 code 再次漂移）
3. 3 漂移修正的功能驗證（_no_ai_profitability 邊界行為）
4. _no_ai_* 計算端不再 inline（改 import 常數）
5. v19.174 去識別化過渡期 alias（舊 `MJ_*` 名同值並存）

v19.174：常數前綴 `MJ_*` → `FH_*`（FH = Financial Health），**數值 0 改**。
"""
from __future__ import annotations

import sys
import types

# ── Minimal Streamlit stub so financial_health_engine can import ──────────────
_st = types.ModuleType("streamlit")
_st.cache_data = lambda **kw: (lambda f: f)
_st.secrets = {}
sys.modules.setdefault("streamlit", _st)

import shared.financial_health_thresholds as FH  # noqa: E402
from src.services import financial_health_engine as fhe  # noqa: E402
from src.services import _no_ai_profitability  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# 1. 常數值
# ─────────────────────────────────────────────────────────────────────────────
class TestFhConstants:
    def test_values(self):
        assert FH.FH_CASH_RATIO_SAFE_PCT == 25.0
        assert FH.FH_CASH_RATIO_WATCH_PCT == 10.0
        assert FH.FH_DSO_FAST_DAYS == 15.0
        assert FH.FH_DSO_SLOW_DAYS == 90.0
        assert FH.FH_DEBT_RATIO_EXCELLENT_PCT == 40.0
        assert FH.FH_DEBT_RATIO_PASS_PCT == 60.0
        assert FH.FH_DEBT_RATIO_WARN_PCT == 70.0
        assert FH.FH_CURRENT_RATIO_MIN_PCT == 300.0
        assert FH.FH_QUICK_RATIO_MIN_PCT == 150.0
        assert FH.FH_GROSS_MARGIN_GOOD_PCT == 40.0
        assert FH.FH_MOS_STRONG_PCT == 60.0
        assert FH.FH_DUPONT_LEVERAGE_DEBT_PCT == 65.0
        assert FH.FH_ROE_LEVERAGE_CHECK_PCT == 15.0
        assert FH.FH_EARNINGS_QUALITY_MIN_PCT == 100.0

    def test_debt_separation_invariant(self):
        # 一般負債結構安全線 vs 杜邦槓桿警報 為兩個不同用途常數，刻意不相等
        assert FH.FH_DEBT_RATIO_PASS_PCT != FH.FH_DUPONT_LEVERAGE_DEBT_PCT  # 60 vs 65
        assert FH.FH_DEBT_RATIO_PASS_PCT < FH.FH_DUPONT_LEVERAGE_DEBT_PCT < FH.FH_DEBT_RATIO_WARN_PCT


# ─────────────────────────────────────────────────────────────────────────────
# 2. golden — prompt 文字 == SSOT 常數（防再漂移）
# ─────────────────────────────────────────────────────────────────────────────
class TestPromptGoldenAgainstSSOT:
    def test_survival_prompt(self):
        assert f">= {int(FH.FH_CASH_RATIO_SAFE_PCT)}%" in fhe._SURVIVAL_PROMPT
        assert f"< {int(FH.FH_DSO_FAST_DAYS)}天" in fhe._SURVIVAL_PROMPT

    def test_profitability_prompt_drift_fixed(self):
        # 漂移2修正：毛利率 Good 對齊 40%
        assert f"> {int(FH.FH_GROSS_MARGIN_GOOD_PCT)}% (Good)" in fhe._PROFITABILITY_PROMPT
        assert "> 20% (Good)" not in fhe._PROFITABILITY_PROMPT
        # 漂移3修正：安全邊際 Strong 對齊 60%
        assert f"> {int(FH.FH_MOS_STRONG_PCT)}% (Strong)" in fhe._PROFITABILITY_PROMPT
        # 漂移1修正：負債槓桿警報對齊 65%
        assert f"負債比 > {int(FH.FH_DUPONT_LEVERAGE_DEBT_PCT)}%" in fhe._PROFITABILITY_PROMPT
        assert "負債比 > 60%" not in fhe._PROFITABILITY_PROMPT

    def test_structure_prompt(self):
        assert f"< {int(FH.FH_DEBT_RATIO_PASS_PCT)}%" in fhe._FINANCIAL_STRUCTURE_PROMPT

    def test_solvency_prompt(self):
        assert f"> {int(FH.FH_CURRENT_RATIO_MIN_PCT)}%" in fhe._SOLVENCY_PROMPT
        assert f"> {int(FH.FH_QUICK_RATIO_MIN_PCT)}%" in fhe._SOLVENCY_PROMPT

    def test_advanced_prompt(self):
        assert f"> {int(FH.FH_EARNINGS_QUALITY_MIN_PCT)}%" in fhe._ADVANCED_DIAGNOSTIC_PROMPT
        # advanced 槓桿門檻一致採 65
        assert f"負債比率(%) > {int(FH.FH_DUPONT_LEVERAGE_DEBT_PCT)}%" in fhe._ADVANCED_DIAGNOSTIC_PROMPT


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


# ─────────────────────────────────────────────────────────────────────────────
# 5. v19.174 去識別化 — 常數改名不得動到數值 + 過渡期 alias 仍在
# ─────────────────────────────────────────────────────────────────────────────
class TestDeidentifiedAliases:
    """新 `FH_*` 與舊 `MJ_*` 必須同值（改名 = 純 rename，不是調參）。

    舊名為過渡期 alias，待授權範圍外的 caller 全遷移後連同本 test 一起移除。
    """

    _PAIRS = (
        "CASH_RATIO_SAFE_PCT", "CASH_RATIO_WATCH_PCT",
        "DSO_FAST_DAYS", "DSO_SLOW_DAYS",
        "CASHFLOW_RATIO_MIN_PCT", "CASHFLOW_ADEQUACY_MIN_PCT", "CASH_REINVEST_MIN_PCT",
        "DEBT_RATIO_EXCELLENT_PCT", "DEBT_RATIO_PASS_PCT", "DEBT_RATIO_WARN_PCT",
        "LONG_TERM_FUNDING_MIN_PCT",
        "CURRENT_RATIO_MIN_PCT", "QUICK_RATIO_MIN_PCT",
        "GROSS_MARGIN_GOOD_PCT", "OPERATING_MARGIN_EXCELLENT_PCT", "MOS_STRONG_PCT",
        "NET_MARGIN_PASS_PCT", "ROE_TOP_PCT", "ROE_LEVERAGE_CHECK_PCT",
        "DUPONT_LEVERAGE_DEBT_PCT",
        "ASSET_TURNOVER_MIN", "EARNINGS_QUALITY_MIN_PCT",
    )

    def test_all_19_plus_aliases_match(self):
        for suffix in self._PAIRS:
            new = getattr(FH, f"FH_{suffix}")
            old = getattr(FH, f"MJ_{suffix}")
            assert new == old, f"FH_{suffix} != MJ_{suffix}（改名不該動數值）"

    def test_no_person_name_in_ssot_module(self):
        """L0 門檻模組不得殘留人名／稱謂（`MJ_` 過渡 alias 例外）。

        ⚠️ 下方 `banned` tuple 是**去識別化守衛黑名單**，不是殘留 ——
        全 repo 掃人名時請跳過本行（v19.174 AI-D 收尾註記）。
        """
        src = open(FH.__file__, encoding="utf-8").read()
        for banned in ("老師", "大師", "林明樟", "明樟", "超級數字力"):
            assert banned not in src, f"financial_health_thresholds 殘留「{banned}」"

    def test_l0_l2_no_ui_or_network_import(self):
        """§8.2 硬規則：L0 shared / L2 compute 不得 import streamlit / requests。

        ⚠️ v19.174 修：原實作用 `"import streamlit" not in body` 做**字串比對**，
        會被 docstring／註解裡的同一句話誤判。實測紅在
        `shared/financial_health_thresholds.py:15` ——
        那行寫的是「純常數模組，零 import 依賴（L0，**不得 import streamlit /
        requests**）」，是**在宣告遵守規則**，卻被守衛當成違規抓出來。

        改用 AST 走訪真正的 `Import` / `ImportFrom` 節點，只認**可執行的
        import 陳述式**，註解與 docstring 一律不算。順便涵蓋
        `import streamlit as st` / `from streamlit import x` 這些原本
        字串比對抓不到的變體（原實作只抓得到 `import streamlit` 這一種寫法）。
        """
        import ast

        import src.compute.health.fin_health_diff as _d
        import src.compute.health.fin_snapshot_io as _io
        import src.compute.health.fin_trend_score as _t

        _BANNED_ROOTS = {"streamlit", "requests"}
        for mod in (FH, _d, _io, _t):
            body = open(mod.__file__, encoding="utf-8").read()
            tree = ast.parse(body, filename=mod.__file__)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    # `from . import x` 的 node.module 為 None → 相對匯入，跳過
                    roots = {(node.module or "").split(".")[0]}
                else:
                    continue
                hit = roots & _BANNED_ROOTS
                assert not hit, (
                    f"{mod.__name__}:{node.lineno} 違憲 import {sorted(hit)} "
                    f"(§8.2 L0/L2 不得依賴 UI/網路層)"
                )
