"""v18.326 PR-D 守衛：B 類新增常數 + VIX 25→22 對齊 + 分歧旗標。

涵蓋:
1. 新增常數值（融資黃線/廣度/TNX/health-label-mid）
2. macro_compass VIX 黃線 = 22（C2 對齊，行為變動）；紅線 = 30
3. 消費端 import + 不再 inline 同值比較
4. 分歧旗標常數存在（2800 / 廣度 30 / health 60 各自具名保行為）
"""
from __future__ import annotations

import re


def _src(p):
    return open(p, encoding="utf-8").read()


class TestNewConstants:
    def test_signal_thresholds(self):
        import shared.signal_thresholds as st
        assert st.MARGIN_BALANCE_WARN_THRESHOLD_YI == 2500.0
        assert st.MARGIN_BALANCE_WARN_HIGH_THRESHOLD_YI == 2800.0
        assert st.BREADTH_BULL_PCT == 60.0
        assert st.BREADTH_NEUTRAL_PCT == 40.0
        assert st.BREADTH_BEAR_PCT == 20.0
        assert st.BREADTH_KPI_YELLOW_PCT == 30.0
        assert st.TNX_VALUATION_PRESSURE_PCT == 4.5
        assert st.TNX_NEUTRAL_PCT == 3.5

    def test_health_label_mid(self):
        from shared.health_thresholds import HEALTH_LABEL_MID_MIN, HEALTH_GRADE_B_MIN
        assert HEALTH_LABEL_MID_MIN == 60
        # 分歧旗標：標籤中間級 60 ≠ B 級 50（兩個不同常數，SPEC §15 待統一）
        assert HEALTH_LABEL_MID_MIN != HEALTH_GRADE_B_MIN


class TestVixAlignedToC2:
    def test_macro_compass_vix_yellow_is_22(self):
        # macro_compass _sig_vix 複用 MACRO_THRESHOLDS['VIX']，黃線 25→22 對齊 C2
        from macro_core import MACRO_THRESHOLDS
        assert MACRO_THRESHOLDS['VIX']['yellow_above'] == 22
        assert MACRO_THRESHOLDS['VIX']['red_above'] == 30
        src = _src("macro_core.py")
        # _sig_vix 不再 inline 25
        assert "if v > 25:" not in src
        assert "MACRO_THRESHOLDS['VIX']['yellow_above']" in src


class TestConsumersWired:
    def test_no_inline_residual(self):
        tm = _src("tab_macro.py")
        dc = _src("daily_checklist.py")
        mc = _src("macro_core.py")
        ts = _src("tab_stock.py")
        # 融資黃線
        assert not re.search(r"(>|<=)\s*2500(?!\s*億)", tm)
        assert not re.search(r"margin>2500", dc)
        assert "MARGIN_BALANCE_WARN_THRESHOLD_YI" in tm and "MARGIN_BALANCE_WARN_THRESHOLD_YI" in dc
        # 廣度
        for v in ("_jq_ratio>=60", "_breadth_score>=40", "_adl_ratio>=60", "_ov_jqp>=30"):
            assert v not in tm, f"廣度殘留 inline: {v}"
        assert "BREADTH_BULL_PCT" in tm
        # TNX
        assert "t >= 4.5" not in mc and "t >= 3.5" not in mc
        assert "TNX_VALUATION_PRESSURE_PCT" in mc
        # health label mid
        assert "health2 >= 60" not in ts
        assert "HEALTH_LABEL_MID_MIN" in ts
