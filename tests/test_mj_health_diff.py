"""v18.185 mj_health_diff 純函式單元測試（不打網路/LLM）。"""
from __future__ import annotations

from src.compute.health import (
    STATUS_SCORES,
    HealthDiffVerdict,
    MetricDiff,
    _score,
    _walk_statuses,
    diff_mj_health,
    screen_health_changes,
    to_json_rows,
)


# ════════════════════════════════════════════════════════════════
# STATUS_SCORES 對照表
# ════════════════════════════════════════════════════════════════
class TestStatusScores:
    def test_survival_three_tier(self):
        assert STATUS_SCORES["Pass"] == 2
        assert STATUS_SCORES["Acceptable"] == 1
        assert STATUS_SCORES["Fail"] == 0

    def test_emoji_lights(self):
        assert STATUS_SCORES["🟢"] == 2
        assert STATUS_SCORES["🟡"] == 1
        assert STATUS_SCORES["🔴"] == 0

    def test_profitability_labels(self):
        assert STATUS_SCORES["Good"] == 2
        assert STATUS_SCORES["Hard Work"] == 1
        assert STATUS_SCORES["Top Tier"] == 2
        assert STATUS_SCORES["Weak"] == 0
        assert STATUS_SCORES["Strong"] == 2
        assert STATUS_SCORES["Excellent"] == 2
        assert STATUS_SCORES["Moderate"] == 1
        assert STATUS_SCORES["Thin Profit"] == 1

    def test_binary_yes_no(self):
        assert STATUS_SCORES["Yes"] == 2
        assert STATUS_SCORES["No"] == 0
        assert STATUS_SCORES["None"] == 2  # leverage warning None = good


# ════════════════════════════════════════════════════════════════
# _score
# ════════════════════════════════════════════════════════════════
class TestScore:
    def test_direct_hit(self):
        assert _score("Pass") == 2
        assert _score("Fail") == 0

    def test_strip_whitespace(self):
        assert _score("  Pass  ") == 2

    def test_prefix_match(self):
        # MJ engine 偶爾吐 "Exception_Pass (條件A：現金充足)"
        assert _score("Exception_Pass (條件A)") is None  # 不在表內、不命中前綴

    def test_high_debt_special(self):
        assert _score("High Debt Ratio (>60%)") == 0

    def test_none_value(self):
        assert _score(None) is None

    def test_non_string(self):
        assert _score(123) is None
        assert _score({}) is None
        assert _score([]) is None

    def test_empty_string(self):
        assert _score("") is None
        assert _score("   ") is None

    def test_unknown_status(self):
        assert _score("Unknown_Label") is None


# ════════════════════════════════════════════════════════════════
# _walk_statuses
# ════════════════════════════════════════════════════════════════
def _mj_mini(cash="Pass", dso="Acceptable", gm="Good", om="Moderate",
             cbp="Yes", roe_lev="None"):
    """簡化版 MJ 體檢回傳結構供測試。"""
    return {
        "cash_ratio_status": "🟢",
        "ocf_status": "🟢",
        "debt_ratio_status": "🟡",
        "Survival_Module": {
            "Cash_Ratio": {"Value": "30%", "Status": cash},
            "DSO_Speed": {"Value": "20 天", "Status": dso},
            "Final_Survival_Verdict": "高",
        },
        "Operating_Module": {
            "DSO": "20 天",
            "Verdict": "做生意本事 OK",
        },
        "Profitability_Module": {
            "Gross_Margin": {"Value": "45%", "Status": gm},
            "Operating_Margin": {
                "Value": "12%",
                "Core_Business_Profitable": cbp,
            },
            "Net_Margin": {"Value": "10%", "Status": om},
            "ROE": {"Value": "18%", "Leverage_Warning": roe_lev},
        },
    }


class TestWalkStatuses:
    def test_top_level_lights_captured(self):
        out = _walk_statuses(_mj_mini())
        assert out[("TopLevel", "cash_ratio_status")] == "🟢"
        assert out[("TopLevel", "debt_ratio_status")] == "🟡"

    def test_module_status_captured(self):
        out = _walk_statuses(_mj_mini())
        assert out[("Survival_Module", "Cash_Ratio")] == "Pass"
        assert out[("Profitability_Module", "Gross_Margin")] == "Good"

    def test_core_business_profitable_captured(self):
        out = _walk_statuses(_mj_mini())
        key = ("Profitability_Module",
               "Operating_Margin.Core_Business_Profitable")
        assert out[key] == "Yes"

    def test_leverage_warning_captured(self):
        out = _walk_statuses(_mj_mini())
        key = ("Profitability_Module", "ROE.Leverage_Warning")
        assert out[key] == "None"

    def test_skip_plain_string_verdict(self):
        # Operating_Module.Verdict 純字串非 status → 不抓
        out = _walk_statuses(_mj_mini())
        assert ("Operating_Module", "Verdict") not in out

    def test_non_dict_input(self):
        assert _walk_statuses(None) == {}
        assert _walk_statuses("bad") == {}
        assert _walk_statuses([]) == {}

    def test_partial_module(self):
        partial = {"Survival_Module": {"Cash_Ratio": {"Status": "Fail"}}}
        out = _walk_statuses(partial)
        assert out == {("Survival_Module", "Cash_Ratio"): "Fail"}


# ════════════════════════════════════════════════════════════════
# diff_mj_health — 核心比對
# ════════════════════════════════════════════════════════════════
class TestDiffMjHealth:
    def test_all_improved(self):
        prev = _mj_mini(cash="Fail", dso="Fail", gm="Hard Work")
        curr = _mj_mini(cash="Pass", dso="Acceptable", gm="Good")
        v = diff_mj_health(prev, curr, stock_id="2330")
        assert v.improve_count >= 3
        assert v.deteriorate_count == 0
        assert v.verdict == "improving"
        assert v.stock_id == "2330"

    def test_all_deteriorated(self):
        prev = _mj_mini(cash="Pass", dso="Acceptable", gm="Good", om="Excellent")
        curr = _mj_mini(cash="Fail", dso="Fail", gm="Hard Work", om="Fail")
        v = diff_mj_health(prev, curr, stock_id="2330")
        assert v.deteriorate_count >= 3
        assert v.improve_count == 0
        assert v.verdict == "deteriorating"

    def test_stable_no_changes(self):
        prev = _mj_mini()
        curr = _mj_mini()
        v = diff_mj_health(prev, curr)
        assert v.improve_count == 0
        assert v.deteriorate_count == 0
        assert v.verdict == "stable"

    def test_mixed_signals(self):
        # 兩個變好、兩個變差，平手 → mixed
        prev = _mj_mini(cash="Fail", dso="Pass", gm="Hard Work", om="Excellent")
        curr = _mj_mini(cash="Pass", dso="Fail", gm="Good", om="Fail")
        v = diff_mj_health(prev, curr, min_net_delta=1)
        # 2 改善 + 2 惡化, net = 0 → mixed
        assert v.verdict == "mixed"

    def test_min_net_delta_buffer(self):
        # 只有 1 項變好 → 預設 min=1 → improving
        prev = _mj_mini(cash="Fail")
        curr = _mj_mini(cash="Pass")
        v = diff_mj_health(prev, curr, min_net_delta=1)
        assert v.verdict == "improving"
        # 提高門檻 min=2 → 應降為 mixed
        v2 = diff_mj_health(prev, curr, min_net_delta=2)
        assert v2.verdict == "mixed"

    def test_is_turnaround_flag(self):
        # Core_Business_Profitable No → Yes（本業由賠轉賺）
        prev = _mj_mini(cbp="No")
        curr = _mj_mini(cbp="Yes")
        v = diff_mj_health(prev, curr)
        assert v.is_turnaround is True
        assert v.is_breakdown is False

    def test_is_breakdown_flag(self):
        prev = _mj_mini(cbp="Yes")
        curr = _mj_mini(cbp="No")
        v = diff_mj_health(prev, curr)
        assert v.is_breakdown is True
        assert v.is_turnaround is False

    def test_unchanged_stays_in_list(self):
        prev = _mj_mini()
        curr = _mj_mini()
        v = diff_mj_health(prev, curr)
        # 應有多筆 unchanged
        assert len(v.unchanged) > 0
        for m in v.unchanged:
            assert m.direction == "unchanged"
            assert m.delta == 0

    def test_missing_prev_returns_empty_verdict(self):
        v = diff_mj_health(None, _mj_mini(), stock_id="X")
        assert v.improve_count == 0
        assert v.deteriorate_count == 0
        assert v.verdict == "stable"

    def test_missing_curr_returns_empty_verdict(self):
        v = diff_mj_health(_mj_mini(), None)
        assert v.verdict == "stable"

    def test_only_common_keys_compared(self):
        prev = {"Survival_Module": {"Cash_Ratio": {"Status": "Pass"}}}
        curr = {"Survival_Module": {"Cash_Ratio": {"Status": "Fail"},
                                    "DSO_Speed": {"Status": "Pass"}}}
        v = diff_mj_health(prev, curr)
        # 只比 Cash_Ratio（DSO_Speed 在 prev 沒有）
        assert v.deteriorate_count == 1
        assert v.improve_count == 0

    def test_unknown_status_skipped(self):
        # status 對應不到 _score → 跳過
        prev = {"Survival_Module": {"Cash_Ratio": {"Status": "WeirdLabel"}}}
        curr = {"Survival_Module": {"Cash_Ratio": {"Status": "Pass"}}}
        v = diff_mj_health(prev, curr)
        assert v.improve_count == 0
        assert v.deteriorate_count == 0

    def test_emoji_light_diff(self):
        prev = {"cash_ratio_status": "🔴"}
        curr = {"cash_ratio_status": "🟢"}
        v = diff_mj_health(prev, curr)
        assert v.improve_count == 1
        assert v.verdict == "improving"


# ════════════════════════════════════════════════════════════════
# screen_health_changes — 漏斗篩選器
# ════════════════════════════════════════════════════════════════
def _snap(sid, prev_mj, curr_mj):
    return {"id": sid, "prev": prev_mj, "curr": curr_mj}


class TestScreenHealthChanges:
    def test_mode_improving_only(self):
        snaps = [
            _snap("UP", _mj_mini(cash="Fail"), _mj_mini(cash="Pass")),
            _snap("DOWN", _mj_mini(cash="Pass"), _mj_mini(cash="Fail")),
            _snap("STABLE", _mj_mini(), _mj_mini()),
        ]
        out = screen_health_changes(snaps, mode="improving")
        assert len(out) == 1
        assert out[0].stock_id == "UP"

    def test_mode_deteriorating_only(self):
        snaps = [
            _snap("UP", _mj_mini(cash="Fail"), _mj_mini(cash="Pass")),
            _snap("DOWN", _mj_mini(cash="Pass"), _mj_mini(cash="Fail")),
        ]
        out = screen_health_changes(snaps, mode="deteriorating")
        assert len(out) == 1
        assert out[0].stock_id == "DOWN"

    def test_mode_both_filters_stable(self):
        snaps = [
            _snap("UP", _mj_mini(cash="Fail"), _mj_mini(cash="Pass")),
            _snap("DOWN", _mj_mini(cash="Pass"), _mj_mini(cash="Fail")),
            _snap("STABLE", _mj_mini(), _mj_mini()),
        ]
        out = screen_health_changes(snaps, mode="both")
        assert len(out) == 2
        assert {v.stock_id for v in out} == {"UP", "DOWN"}

    def test_mode_all_includes_stable(self):
        snaps = [
            _snap("UP", _mj_mini(cash="Fail"), _mj_mini(cash="Pass")),
            _snap("STABLE", _mj_mini(), _mj_mini()),
        ]
        out = screen_health_changes(snaps, mode="all")
        assert len(out) == 2

    def test_invalid_mode_defaults_to_both(self):
        snaps = [_snap("UP", _mj_mini(cash="Fail"), _mj_mini(cash="Pass"))]
        out = screen_health_changes(snaps, mode="garbage")
        assert len(out) == 1  # 預設 both 仍會抓 improving

    def test_skip_invalid_snapshot(self):
        snaps = [
            _snap("UP", _mj_mini(cash="Fail"), _mj_mini(cash="Pass")),
            None,
            {"no_id": True},
            {"id": ""},
            "not a dict",
        ]
        out = screen_health_changes(snaps, mode="improving")
        assert len(out) == 1

    def test_non_list_input(self):
        assert screen_health_changes(None) == []
        assert screen_health_changes("bad") == []
        assert screen_health_changes({}) == []

    def test_min_net_delta_propagated(self):
        snaps = [_snap("X", _mj_mini(cash="Fail"), _mj_mini(cash="Pass"))]
        # 只 1 項變好，min=2 → mixed → 不入 both 篩選
        out = screen_health_changes(snaps, mode="both", min_net_delta=2)
        assert len(out) == 0


# ════════════════════════════════════════════════════════════════
# 輔助工具 + Dataclass property
# ════════════════════════════════════════════════════════════════
class TestHelpers:
    def test_net_delta_property(self):
        v = HealthDiffVerdict(stock_id="X")
        v.improvements.append(MetricDiff("M", "x", "Fail", "Pass", +1, "improved"))
        v.improvements.append(MetricDiff("M", "y", "Fail", "Pass", +1, "improved"))
        v.deteriorations.append(MetricDiff("M", "z", "Pass", "Fail", -1, "deteriorated"))
        assert v.improve_count == 2
        assert v.deteriorate_count == 1
        assert v.net_delta == 1

    def test_to_json_rows(self):
        snaps = [_snap("X", _mj_mini(cash="Fail"), _mj_mini(cash="Pass"))]
        verdicts = screen_health_changes(snaps, mode="improving")
        rows = to_json_rows(verdicts)
        assert isinstance(rows, list)
        assert rows[0]["stock_id"] == "X"
        assert rows[0]["verdict"] == "improving"
        assert rows[0]["improve_count"] >= 1
        assert "improvements" in rows[0]
        assert "is_turnaround" in rows[0]

    def test_verdict_to_dict_full_shape(self):
        v = diff_mj_health(_mj_mini(cash="Fail"), _mj_mini(cash="Pass"))
        d = v.to_dict()
        for k in ("stock_id", "verdict", "improve_count", "deteriorate_count",
                  "net_delta", "is_turnaround", "is_breakdown",
                  "improvements", "deteriorations", "unchanged"):
            assert k in d
