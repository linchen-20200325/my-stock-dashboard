"""v18.326 PR-D + v18.327 PR-E 守衛：B 類常數 + VIX 對齊 + 分歧統一。

PR-D 新增常數 + macro_compass VIX 25→22 對齊 C2。
PR-E（user MK 邏輯拍板）將 3 組分歧門檻**全面統一對齊標準值**（50/2500/40），
移除分歧變體常數（HEALTH_LABEL_MID_MIN / MARGIN_BALANCE_WARN_HIGH_THRESHOLD_YI /
BREADTH_KPI_YELLOW_PCT），消滅語意與行為不一致。
"""
from __future__ import annotations

import re


def _src(p):
    return open(p, encoding="utf-8").read()


class TestStandardConstants:
    def test_signal_thresholds(self):
        import shared.signal_thresholds as st
        assert st.MARGIN_BALANCE_WARN_THRESHOLD_YI == 2500.0
        assert st.BREADTH_BULL_PCT == 60.0
        assert st.BREADTH_NEUTRAL_PCT == 40.0
        assert st.BREADTH_BEAR_PCT == 20.0
        assert st.TNX_VALUATION_PRESSURE_PCT == 4.5
        assert st.TNX_NEUTRAL_PCT == 3.5

    def test_health_grades(self):
        from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
        assert HEALTH_GRADE_A_MIN == 80
        assert HEALTH_GRADE_B_MIN == 50


class TestDivergenceHarmonized:
    """PR-E：3 組分歧變體常數已移除，全部對齊標準值。"""
    def test_divergent_constants_removed(self):
        import shared.signal_thresholds as st
        import shared.health_thresholds as ht
        assert not hasattr(st, "MARGIN_BALANCE_WARN_HIGH_THRESHOLD_YI"), "2800 分歧變體應已移除"
        assert not hasattr(st, "BREADTH_KPI_YELLOW_PCT"), "廣度 30 分歧變體應已移除"
        assert not hasattr(ht, "HEALTH_LABEL_MID_MIN"), "健康度 60 分歧變體應已移除"

    def test_consumers_use_standard(self):
        tm = _src("src/ui/tabs/tab_macro.py")
        ts = _src("src/ui/tabs/tab_stock.py")
        # 融資 SQL 卡片 + 廣度 KPI 皆改用標準常數，不得殘留分歧
        assert "MARGIN_BALANCE_WARN_HIGH_THRESHOLD_YI" not in tm
        assert "BREADTH_KPI_YELLOW_PCT" not in tm
        assert "_ov_jqp>=BREADTH_NEUTRAL_PCT" in tm  # KPI 黃線統一 40
        # 健康度標籤改用 B 級線 50（與評語一致）
        assert "HEALTH_LABEL_MID_MIN" not in ts
        assert "health2 >= HEALTH_GRADE_B_MIN" in ts
        # 不得再有 inline 60 標籤 / 2800 / KPI-30
        assert "health2 >= 60" not in ts
        assert not re.search(r"(>|>=)\s*2800\b", tm)
        assert "_ov_jqp>=30" not in tm


class TestVixAlignedToC2:
    def test_macro_compass_vix_yellow_is_22(self):
        from src.data.macro import MACRO_THRESHOLDS
        assert MACRO_THRESHOLDS['VIX']['yellow_above'] == 22
        assert MACRO_THRESHOLDS['VIX']['red_above'] == 30
        src = _src("src/data/macro/macro_core.py")
        assert "if v > 25:" not in src
        assert "MACRO_THRESHOLDS['VIX']['yellow_above']" in src


class TestConsumersWired:
    def test_no_inline_residual(self):
        tm = _src("src/ui/tabs/tab_macro.py")
        dc = _src("src/services/daily_checklist.py")
        mc = _src("src/data/macro/macro_core.py")
        # 融資黃線
        assert not re.search(r"(>|<=)\s*2500(?!\s*億)", tm)
        assert not re.search(r"margin>2500", dc)
        assert "MARGIN_BALANCE_WARN_THRESHOLD_YI" in tm and "MARGIN_BALANCE_WARN_THRESHOLD_YI" in dc
        # 廣度
        for v in ("_jq_ratio>=60", "_breadth_score>=40", "_adl_ratio>=60"):
            assert v not in tm, f"廣度殘留 inline: {v}"
        assert "BREADTH_BULL_PCT" in tm
        # TNX
        assert "t >= 4.5" not in mc and "t >= 3.5" not in mc
        assert "TNX_VALUATION_PRESSURE_PCT" in mc
