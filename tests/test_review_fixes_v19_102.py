# -*- coding: utf-8 -*-
"""v19.102 — 紅綠燈權重校準採納(Phase 3 收官,user 核准方案 B)。

依 MACRO_HEALTH_WEIGHT_PROPOSAL.md(真實 2006~2026、n=4748、val AUC 0.753、
overfit_flag=False;本地復算一字不差):
- HEALTH_WEIGHT_JQ 0.4→0.6(jqavg:score 相對重要性 ≈ 60:40)
- HEALTH_FNET_BONUS 20→0(fnet 對 20 日回撤零預測力)
- score 正規化 /CONFIDENCE_SOURCE_COUNT(5,錯配)→ /mkt_info['max_score'](4/6)
- 對帳 Method B 同步(兩組件等權、fnet 不計分、/max*100)
"""
from __future__ import annotations

import math
from pathlib import Path

from shared.signal_thresholds import (
    HEALTH_FNET_BONUS,
    HEALTH_WEIGHT_JQ,
    HEALTH_WEIGHT_SCORE,
)

REPO = Path(__file__).resolve().parent.parent


class TestCalibratedConstants:
    def test_weights_adopted(self):
        assert HEALTH_WEIGHT_JQ == 0.6
        assert HEALTH_WEIGHT_SCORE == 0.4
        assert HEALTH_FNET_BONUS == 0

    def test_weights_sum_to_one(self):
        # CLAUDE.md §4.2「權重和 ≈ 1.0」— v19.102 起真正成立
        assert math.isclose(HEALTH_WEIGHT_JQ + HEALTH_WEIGHT_SCORE, 1.0, abs_tol=1e-9)

    def test_proposal_doc_exists_as_evidence(self):
        # 採納證據鏈:提案檔須在 repo(由 Calibrate workflow commit)
        assert (REPO / "MACRO_HEALTH_REWEIGHT_PROPOSAL.md").exists()


class TestNoStaleDivisorInHealth:
    def test_health_formula_uses_max_score_not_confidence_count(self):
        src = (REPO / "src/compute/macro/macro_helpers.py").read_text(encoding="utf-8")
        # 健康公式不得再用 CONFIDENCE_SOURCE_COUNT 當 score 除數(錯配已修)
        assert "_score / CONFIDENCE_SOURCE_COUNT" not in src
        assert "_score / _max_score * 100" in src
        # CONFIDENCE_SOURCE_COUNT 保留其真用途(信心度)
        assert "/ CONFIDENCE_SOURCE_COUNT * 100)" in src


class TestEndToEndHealth:
    def test_default_mode_perfect_score_reaches_ceiling(self):
        # 修除5錯配後:預設模式(max_score=4)score=4 → score 分項可達 100
        from src.compute.macro.macro_helpers import calc_traffic_light
        tl = calc_traffic_light(
            {"score": 4, "max_score": 4, "regime": "bull"},
            {"avg": 100}, {"inst": {}}, None,
        )
        assert tl["health"] == 100.0   # 100*0.6 + 100*0.4 + 0

    def test_method_a_b_aligned_on_typical_input(self):
        # 校準後兩法在典型輸入須對齊(不再因 fnet 常態偏差)
        from src.compute.health.health_reconcile import reconcile_health_score
        a = 70 * 0.6 + (3 / 4 * 100) * 0.4    # 42 + 30 = 72
        r = reconcile_health_score(a, jqavg=70, score=3, fnet=500, max_score=4)
        assert r.within_tolerance             # B = (70+75)/2 = 72.5,diff 0.5
