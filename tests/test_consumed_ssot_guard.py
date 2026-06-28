"""v18.325 PR-C 守衛：A 類「既有 SSOT 常數被 inline 繞過」回歸防護。

稽核發現 daily_checklist / tab_macro / tab_stock 把**已存在的** SSOT 常數
（MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI=3400 / HEALTH_GRADE_A_MIN=80 /
HEALTH_GRADE_B_MIN=50 / CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT=80）寫死成 inline。
PR-C 改 import 消費。本測試釘住「改 import + 不得再 inline 同值比較」。
"""
from __future__ import annotations

import re


def _src(path):
    return open(path, encoding="utf-8").read()


class TestMarginBalanceConsumed:
    def test_imports_and_no_inline(self):
        for f in ("src/services/daily_checklist.py", "src/ui/tabs/tab_macro.py"):
            src = _src(f)
            assert "MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI" in src, f"{f} 未 import 融資紅線 SSOT"
        # 不得再有 inline 的 3400 程式比較；顯示標籤「>3400億」用 (?!\s*億) 排除
        code_cmp = re.compile(r"(>=|>)\s*3400(?!\s*億)")
        assert not code_cmp.search(_src("src/services/daily_checklist.py"))
        assert not code_cmp.search(_src("src/ui/tabs/tab_macro.py"))


class TestHealthGradeConsumed:
    def test_imports_and_no_inline(self):
        src = _src("src/ui/tabs/tab_stock.py")
        assert "HEALTH_GRADE_A_MIN" in src and "HEALTH_GRADE_B_MIN" in src
        assert "CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT" in src
        # health2 不得再 inline 比較 80 / 50；龍頭資本支出不得再 inline 80
        assert not re.search(r"health2\s*(>=|>)\s*80", src)
        assert not re.search(r"health2\s*(>=|>)\s*50", src)
        assert "_cx_r >= 80" not in src


class TestConstantValuesUnchanged:
    """PR-C 為零行為變動：確認消費的常數值即原 inline 值。"""
    def test_values(self):
        from shared.signal_thresholds import (
            MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI, CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT,
        )
        from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
        assert MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI == 3400.0
        assert CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT == 80.0
        assert HEALTH_GRADE_A_MIN == 80
        assert HEALTH_GRADE_B_MIN == 50
