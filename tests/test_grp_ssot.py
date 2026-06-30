"""v18.322 個股組合 SSOT 化 + 舊評分退役(Option A)守衛測試。

涵蓋:
1. shared/signal_thresholds 新增的 GRP_* / MULTIFACTOR_* 常數值 + 排序
2. scoring_engine grade 分界走 SSOT(不再 inline 75/55)
3. tab_stock_grp「舊評分」已退役(④ 改純健康度排)+ 門檻全走 SSOT
"""
from __future__ import annotations

import shared.signal_thresholds as st_mod


class TestGrpSSOTConstants:
    def test_constants_exist_and_values(self):
        assert st_mod.GRP_VOL_SHRINK_RATIO == 0.7
        assert st_mod.GRP_NEAR_MA20_BIAS_PCT == 3.0
        assert st_mod.GRP_BIAS_OVERHEAT_WARN_PCT == 25.0
        assert st_mod.GRP_NEWS_BEARISH_CONFIDENCE_MIN == 50.0
        assert st_mod.MULTIFACTOR_GRADE_A_MIN == 75.0
        assert st_mod.MULTIFACTOR_GRADE_B_MIN == 55.0
        assert st_mod.MULTIFACTOR_ENTRY_MIN == 70.0

    def test_multifactor_grade_order(self):
        assert st_mod.MULTIFACTOR_GRADE_B_MIN < st_mod.MULTIFACTOR_GRADE_A_MIN
        # 多因子分級與健康度分級為不同體系，門檻各自獨立（不應相等耦合）
        from shared.health_thresholds import HEALTH_GRADE_A_MIN
        assert st_mod.MULTIFACTOR_GRADE_A_MIN != HEALTH_GRADE_A_MIN  # 75 vs 80


class TestScoringEngineGradeSSOT:
    def test_grade_uses_ssot_not_inline(self):
        from src.compute.scoring import scoring_engine
        src = open(scoring_engine.__file__, encoding="utf-8").read()
        assert "MULTIFACTOR_GRADE_A_MIN" in src
        assert "MULTIFACTOR_GRADE_B_MIN" in src
        # 不再用 inline 75/55 做 grade 分界
        assert "total >= 75" not in src
        assert "total >= 55" not in src


def _grp_combined_src() -> str:
    """v18.413+ 拆檔後,grp tab 邏輯散在 tab_stock_grp + stock_grp_sections/*.py 全 file。

    本 helper 合併讀,供守衛測「字串存在於組合 tab 任一 module」。
    """
    import glob

    paths = ['src/ui/tabs/tab_stock_grp.py']
    paths += sorted(glob.glob('src/ui/tabs/stock_grp_sections/*.py'))
    chunks = []
    for p in paths:
        with open(p, encoding='utf-8') as f:
            chunks.append(f.read())
    return '\n'.join(chunks)


class TestOldScoreRetired:
    def test_no_old_score_variable_or_column(self):
        src = _grp_combined_src()
        assert "old_score4" not in src          # 計算變數已刪
        assert "'舊評分':" not in src            # dict key / column_config 已刪
        assert "['舊評分'," not in src           # col_order 已刪

    def test_elim_sorts_by_pure_health(self):
        src = _grp_combined_src()
        # ④ 汰弱留強改以純健康度排序(對齊頁面說明)
        assert "sort_values('健康度', ascending=False)" in src
        assert "sort_values(['舊評分'" not in src


class TestGrpThresholdsSSOT:
    def test_imports_ssot_constants(self):
        """守衛:grp tab 邏輯使用的 SSOT 常數應出現在 grp tab/sections 任一檔。

        v18.415 Batch 7-3 後:GRP_VOL_SHRINK_RATIO / GRP_NEAR_MA20_BIAS_PCT /
        GRP_BIAS_OVERHEAT_WARN_PCT 改透過 tab_helpers.classify_stock_status_lamp
        間接使用(consumer 在 tab_helpers 而非 grp tab),所以這 3 個改測 tab_helpers。
        """
        src = _grp_combined_src()
        for name in ("HEALTH_GRADE_A_MIN", "HEALTH_GRADE_B_MIN",
                     "GRP_NEWS_BEARISH_CONFIDENCE_MIN",
                     "MULTIFACTOR_ENTRY_MIN"):
            assert name in src, f"tab_stock_grp(含 sections) 缺 SSOT import: {name}"
        # 操作狀態燈 3 magic 改測 tab_helpers(consumer SSOT)
        with open('src/ui/tabs/tab_helpers.py', encoding='utf-8') as f:
            tab_helpers_src = f.read()
        for name in ("GRP_VOL_SHRINK_RATIO", "GRP_NEAR_MA20_BIAS_PCT",
                     "GRP_BIAS_OVERHEAT_WARN_PCT"):
            assert name in tab_helpers_src, \
                f"tab_helpers(classify_stock_status_lamp consumer)缺 SSOT: {name}"

    def test_no_inline_opstate_magic(self):
        src = _grp_combined_src()
        # 操作狀態燈 / 入選 / 淘汰 不再用 inline 數字
        assert "_vol4 < _avgvol4 * 0.7" not in src
        assert "abs(_bias4) < 3" not in src
        assert "health4 >= 80" not in src
        assert "_bias4 > 25" not in src
        assert "r.get('total', 0) >= 70" not in src
