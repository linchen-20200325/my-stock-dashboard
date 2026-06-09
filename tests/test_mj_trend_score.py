"""tests/test_mj_trend_score.py — v18.189 雙頻率融合分數測試"""
from __future__ import annotations

import pytest

from mj_trend_score import (
    _label_from_score,
    _safe_num,
    _squash,
    _yoy_step_score,
    compute_mj_trend_subscore,
    compute_monthly_revenue_subscore,
    compute_trend_score,
)


# ════════════════════════════════════════════════════════════════
# Helper purity tests
# ════════════════════════════════════════════════════════════════
class TestSafeNum:
    def test_none_returns_none(self):
        assert _safe_num(None) is None

    def test_int_pass(self):
        assert _safe_num(5) == 5.0

    def test_float_pass(self):
        assert _safe_num(3.14) == 3.14

    def test_string_number(self):
        assert _safe_num("2.5") == 2.5

    def test_string_garbage_none(self):
        assert _safe_num("abc") is None

    def test_nan_none(self):
        assert _safe_num(float("nan")) is None

    def test_inf_none(self):
        assert _safe_num(float("inf")) is None


class TestYoyStepScore:
    def test_strong_up(self):
        assert _yoy_step_score(15.0) == 2.0
        assert _yoy_step_score(10.0) == 2.0  # 邊界包含

    def test_mild_up(self):
        assert _yoy_step_score(5.0) == 1.0
        assert _yoy_step_score(0.01) == 1.0

    def test_zero(self):
        assert _yoy_step_score(0.0) == 0.0

    def test_mild_down(self):
        assert _yoy_step_score(-5.0) == -1.0
        assert _yoy_step_score(-0.01) == -1.0

    def test_strong_down(self):
        assert _yoy_step_score(-15.0) == -2.0
        assert _yoy_step_score(-10.0) == -2.0  # 邊界包含


class TestSquash:
    def test_zero(self):
        assert _squash(0) == 0.0

    def test_one(self):
        assert abs(_squash(1) - 1 / 3) < 1e-9

    def test_three(self):
        assert _squash(3) == 1.0

    def test_above_three_saturates(self):
        assert _squash(10) == 1.0

    def test_below_neg_three_saturates(self):
        assert _squash(-10) == -1.0


class TestLabelFromScore:
    def test_strong_up(self):
        lbl, code = _label_from_score(2.0)
        assert "強進步" in lbl and code == "strong_up"
        # 邊界
        lbl, code = _label_from_score(1.5)
        assert code == "strong_up"

    def test_up(self):
        lbl, code = _label_from_score(1.0)
        assert "進步" in lbl and code == "up"
        # 邊界
        assert _label_from_score(0.5)[1] == "up"

    def test_neutral(self):
        lbl, code = _label_from_score(0.0)
        assert "中性" in lbl and code == "neutral"
        # 邊界
        assert _label_from_score(-0.5)[1] == "neutral"

    def test_down(self):
        lbl, code = _label_from_score(-1.0)
        assert "退步" in lbl and code == "down"
        # 邊界
        assert _label_from_score(-1.5)[1] == "down"

    def test_strong_down(self):
        lbl, code = _label_from_score(-2.0)
        assert "強退步" in lbl and code == "strong_down"

    def test_extreme_high(self):
        assert _label_from_score(99.0)[1] == "strong_up"


# ════════════════════════════════════════════════════════════════
# 月營收子分數
# ════════════════════════════════════════════════════════════════
class TestMonthlyRevenueSubscore:
    def test_empty_list(self):
        score, det = compute_monthly_revenue_subscore([])
        assert score == 0.0 and det["reason"] == "no_data"

    def test_bad_input(self):
        score, det = compute_monthly_revenue_subscore("not_a_list")  # type: ignore[arg-type]
        assert score == 0.0 and det["reason"] == "no_data"

    def test_all_strong_up_with_mom_up(self):
        data = [
            {"yoy_pct": 15.0, "mom_pct": 5.0},
            {"yoy_pct": 12.0, "mom_pct": 3.0},
            {"yoy_pct": 18.0, "mom_pct": 8.0},
        ]
        score, det = compute_monthly_revenue_subscore(data)
        # YoY avg = 15 → +2, MoM = +8 → +0.5
        assert score == 2.5
        assert det["yoy_score"] == 2.0 and det["mom_score"] == 0.5
        assert det["n_months"] == 3

    def test_all_strong_down_with_mom_down(self):
        data = [
            {"yoy_pct": -15.0, "mom_pct": -5.0},
            {"yoy_pct": -12.0, "mom_pct": -3.0},
            {"yoy_pct": -18.0, "mom_pct": -8.0},
        ]
        score, det = compute_monthly_revenue_subscore(data)
        # YoY avg = -15 → -2, MoM = -8 → -0.5
        assert score == -2.5

    def test_mild_up_with_zero_mom(self):
        data = [
            {"yoy_pct": 5.0, "mom_pct": 0.0},
            {"yoy_pct": 3.0, "mom_pct": 0.0},
            {"yoy_pct": 7.0, "mom_pct": 0.0},
        ]
        score, det = compute_monthly_revenue_subscore(data)
        # YoY avg = 5 → +1, MoM = 0 → 0
        assert score == 1.0
        assert det["mom_score"] == 0.0

    def test_missing_yoy_returns_zero(self):
        data = [
            {"yoy_pct": None, "mom_pct": 5.0},
            {"yoy_pct": "garbage", "mom_pct": 3.0},
        ]
        score, det = compute_monthly_revenue_subscore(data)
        assert score == 0.0
        assert det["reason"] == "no_yoy"

    def test_missing_mom_falls_back_zero(self):
        data = [
            {"yoy_pct": 5.0},
            {"yoy_pct": 3.0},
            {"yoy_pct": 7.0, "mom_pct": None},
        ]
        score, det = compute_monthly_revenue_subscore(data)
        # YoY avg = 5 → +1, MoM 缺失 → 0
        assert score == 1.0
        assert det["last_mom"] is None

    def test_non_dict_items_skipped(self):
        data = [
            "not_a_dict",  # type: ignore[list-item]
            {"yoy_pct": 5.0, "mom_pct": 1.0},
        ]
        score, det = compute_monthly_revenue_subscore(data)
        assert det["n_months"] == 1


# ════════════════════════════════════════════════════════════════
# MJ 季財報 trend 子分數
# ════════════════════════════════════════════════════════════════
def _make_snapshot(survival_status: str = "Pass") -> dict:
    """簡化 MJ 體檢 snapshot fixture，僅含 Survival_Module/Cash_Ratio 一項。

    Key 須用大寫 Survival_Module 對齊 mj_health_diff._walk_statuses 掃描清單。
    """
    return {
        "Survival_Module": {
            "Cash_Ratio": {"Status": survival_status, "Insight": ""},
        },
    }


class TestMjTrendSubscore:
    def test_bad_input(self):
        s, det = compute_mj_trend_subscore("not_a_list")  # type: ignore[arg-type]
        assert s == 0.0 and det["reason"] == "bad_input"

    def test_empty(self):
        s, det = compute_mj_trend_subscore([])
        assert s == 0.0 and det["reason"] == "insufficient_snapshots"

    def test_only_one_snapshot(self):
        s, det = compute_mj_trend_subscore([_make_snapshot("Pass")])
        assert s == 0.0 and det["n_snapshots"] == 1

    def test_two_snapshots_improvement(self):
        snaps = [_make_snapshot("Fail"), _make_snapshot("Pass")]
        s, det = compute_mj_trend_subscore(snaps)
        # net_delta = +1 (Fail→Pass) → squash(1)*2 = ~0.667
        assert s > 0
        assert det["delta_1"] == 1
        assert det["delta_2"] is None

    def test_two_snapshots_deterioration(self):
        snaps = [_make_snapshot("Pass"), _make_snapshot("Fail")]
        s, _ = compute_mj_trend_subscore(snaps)
        assert s < 0

    def test_three_snapshots_same_dir_up(self):
        # 三季：Fail → Acceptable → Pass（一路改善）
        snaps = [
            _make_snapshot("Fail"),
            _make_snapshot("Acceptable"),
            _make_snapshot("Pass"),
        ]
        s, det = compute_mj_trend_subscore(snaps)
        # delta_1 = +1, delta_2 = +1, same_direction → s1+s2 ≈ 0.667
        assert s > 0
        assert det["same_direction"] is True

    def test_three_snapshots_divergent(self):
        # 三季：Fail → Pass → Fail（先升後降）
        snaps = [
            _make_snapshot("Fail"),
            _make_snapshot("Pass"),
            _make_snapshot("Fail"),
        ]
        s, det = compute_mj_trend_subscore(snaps)
        # delta_1 = +1, delta_2 = -1, divergent → (0.333 + -0.333)*0.5 = 0
        assert det["same_direction"] is False
        assert abs(s) < 0.1

    def test_more_than_three_uses_latest_3(self):
        snaps = [
            _make_snapshot("Pass"),  # 古早，被丟棄
            _make_snapshot("Fail"),
            _make_snapshot("Acceptable"),
            _make_snapshot("Pass"),
        ]
        s, det = compute_mj_trend_subscore(snaps)
        assert det["n_snapshots"] == 3
        # 應吃最新 3 季 Fail→Acceptable→Pass 同向改善
        assert s > 0


# ════════════════════════════════════════════════════════════════
# 整合：compute_trend_score
# ════════════════════════════════════════════════════════════════
class TestComputeTrendScore:
    def test_both_empty(self):
        out = compute_trend_score(None, None)
        assert out["score"] == 0.0
        assert out["label_code"] == "neutral"

    def test_strong_up_both_sources(self):
        monthly = [
            {"yoy_pct": 15.0, "mom_pct": 5.0},
            {"yoy_pct": 12.0, "mom_pct": 3.0},
            {"yoy_pct": 20.0, "mom_pct": 8.0},
        ]
        mj_snaps = [
            _make_snapshot("Fail"),
            _make_snapshot("Acceptable"),
            _make_snapshot("Pass"),
        ]
        out = compute_trend_score(monthly, mj_snaps)
        # mon = 2.5, mj ≈ 0.667 → 2.5*0.65 + 0.667*0.35 ≈ 1.625+0.233 ≈ 1.86 → strong_up
        assert out["label_code"] == "strong_up"
        assert out["monthly_subscore"] == 2.5

    def test_strong_down_both_sources(self):
        monthly = [
            {"yoy_pct": -20.0, "mom_pct": -10.0},
            {"yoy_pct": -15.0, "mom_pct": -8.0},
            {"yoy_pct": -25.0, "mom_pct": -12.0},
        ]
        mj_snaps = [
            _make_snapshot("Pass"),
            _make_snapshot("Acceptable"),
            _make_snapshot("Fail"),
        ]
        out = compute_trend_score(monthly, mj_snaps)
        assert out["label_code"] == "strong_down"

    def test_monthly_drives_when_mj_missing(self):
        monthly = [
            {"yoy_pct": 15.0, "mom_pct": 5.0},
            {"yoy_pct": 12.0, "mom_pct": 3.0},
            {"yoy_pct": 18.0, "mom_pct": 8.0},
        ]
        out = compute_trend_score(monthly, None)
        # mon = 2.5, mj = 0 → 2.5*0.65 = 1.625 → strong_up
        assert out["label_code"] == "strong_up"
        assert out["mj_subscore"] == 0.0

    def test_mj_alone_cant_reach_strong(self):
        # MJ 滿分但月營收缺 → mj=2.0*0.35=0.7 → up（達不到 strong_up）
        mj_snaps = [
            _make_snapshot("Fail"),
            _make_snapshot("Pass"),
        ]
        out = compute_trend_score(None, mj_snaps)
        # mj ≈ 0.667 → 0.667*0.35 ≈ 0.23 → neutral
        # 邊界：用較強樣本
        assert out["label_code"] in ("neutral", "up")

    def test_custom_weight(self):
        monthly = [{"yoy_pct": 15.0, "mom_pct": 5.0}]
        mj_snaps = [_make_snapshot("Pass"), _make_snapshot("Fail")]
        out = compute_trend_score(monthly, mj_snaps, w_monthly=0.5)
        assert out["w_monthly"] == 0.5
        assert out["w_quarterly"] == 0.5

    def test_invalid_weight_falls_back_to_default(self):
        out = compute_trend_score(None, None, w_monthly=1.5)
        assert out["w_monthly"] == 0.65

        out2 = compute_trend_score(None, None, w_monthly="abc")  # type: ignore[arg-type]
        assert out2["w_monthly"] == 0.65

    def test_output_shape(self):
        out = compute_trend_score(None, None)
        for key in (
            "score", "label", "label_code",
            "monthly_subscore", "mj_subscore",
            "w_monthly", "w_quarterly",
            "monthly_detail", "mj_detail",
        ):
            assert key in out

    def test_monthly_dominates_at_65_weight(self):
        # 月營收 +2.5 vs MJ -2.0 → 0.65*2.5 + 0.35*-2.0 = 1.625 - 0.7 = 0.925 → up
        monthly = [{"yoy_pct": 15.0, "mom_pct": 5.0}, {"yoy_pct": 12.0}, {"yoy_pct": 18.0}]
        mj_snaps = [
            _make_snapshot("Pass"),
            _make_snapshot("Acceptable"),
            _make_snapshot("Fail"),
        ]
        out = compute_trend_score(monthly, mj_snaps)
        # mon = 2.5+0.5 = 3 → cap 不需要，但 mon = yoy(+2)+mom(+0.5)=2.5
        assert out["monthly_subscore"] >= 2.0
        # 整體因月權重主導 → 仍偏正
        assert out["score"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
