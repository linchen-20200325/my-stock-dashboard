"""v18.184 fundamental_screener 純函式單元測試（不打網路）。"""
from __future__ import annotations

from src.compute.screener import (
    ConditionResult,
    _safe_num,
    check_eps_growth_or_turnaround,
    check_revenue_dual_growth,
    check_triple_margin_up,
    filter_passed,
    screen_stocks,
    to_json_rows,
)


# ════════════════════════════════════════════════════════════════
# _safe_num
# ════════════════════════════════════════════════════════════════
class TestSafeNum:
    def test_valid_number(self):
        assert _safe_num({"a": 5.0}, "a") == 5.0

    def test_nested(self):
        assert _safe_num({"a": {"b": 3}}, "a", "b") == 3.0

    def test_string_number_coerce(self):
        assert _safe_num({"a": "5.5"}, "a") == 5.5

    def test_none_value(self):
        assert _safe_num({"a": None}, "a") is None

    def test_missing_key(self):
        assert _safe_num({"a": 1}, "b") is None

    def test_nested_missing(self):
        assert _safe_num({"a": {}}, "a", "b") is None

    def test_not_dict_root(self):
        assert _safe_num(None, "a") is None
        assert _safe_num([], "a") is None
        assert _safe_num("string", "a") is None

    def test_not_dict_nested(self):
        assert _safe_num({"a": 5}, "a", "b") is None

    def test_nan(self):
        assert _safe_num({"a": float("nan")}, "a") is None

    def test_invalid_string(self):
        assert _safe_num({"a": "abc"}, "a") is None


# ════════════════════════════════════════════════════════════════
# 條件 A：營收雙增
# ════════════════════════════════════════════════════════════════
class TestRevenueDualGrowth:
    def test_both_positive_pass(self):
        r = check_revenue_dual_growth({"mom": 5.0, "yoy": 30.0})
        assert r.passed
        assert r.code == "A"

    def test_mom_zero_fail(self):
        # strict > 0
        assert not check_revenue_dual_growth({"mom": 0, "yoy": 30}).passed

    def test_yoy_zero_fail(self):
        assert not check_revenue_dual_growth({"mom": 5, "yoy": 0}).passed

    def test_mom_negative_fail(self):
        assert not check_revenue_dual_growth({"mom": -1.0, "yoy": 30}).passed

    def test_yoy_negative_fail(self):
        assert not check_revenue_dual_growth({"mom": 5, "yoy": -10}).passed

    def test_none_input_fail(self):
        assert not check_revenue_dual_growth(None).passed

    def test_missing_yoy_fail(self):
        assert not check_revenue_dual_growth({"mom": 5}).passed

    def test_no_crash_on_bad_type(self):
        assert not check_revenue_dual_growth("not a dict").passed
        assert not check_revenue_dual_growth(12345).passed


# ════════════════════════════════════════════════════════════════
# 條件 B：三率三升
# ════════════════════════════════════════════════════════════════
def _mk_margins(
    g_cur=50, g_pq=48, g_py=47,
    o_cur=25, o_pq=22, o_py=20,
    n_cur=18, n_pq=15, n_py=12,
):
    return {
        "gross_margin": {"current": g_cur, "prev_q": g_pq, "prev_year_q": g_py},
        "operating_margin": {"current": o_cur, "prev_q": o_pq, "prev_year_q": o_py},
        "net_margin": {"current": n_cur, "prev_q": n_pq, "prev_year_q": n_py},
    }


class TestTripleMarginUp:
    def test_all_three_up_pass(self):
        r = check_triple_margin_up(_mk_margins())
        assert r.passed
        assert r.code == "B"

    def test_gross_qoq_flat_fail(self):
        # QoQ = 0 → strict > 失敗
        assert not check_triple_margin_up(_mk_margins(g_cur=48, g_pq=48)).passed

    def test_operating_yoy_flat_fail(self):
        assert not check_triple_margin_up(_mk_margins(o_cur=20, o_py=20)).passed

    def test_net_margin_down_fail(self):
        assert not check_triple_margin_up(_mk_margins(n_cur=10, n_pq=15)).passed

    def test_partial_missing_fail(self):
        m = _mk_margins()
        m["net_margin"] = {"current": 18, "prev_q": None, "prev_year_q": 12}
        assert not check_triple_margin_up(m).passed

    def test_none_input_fail(self):
        r = check_triple_margin_up(None)
        assert not r.passed
        assert "無" in r.reason

    def test_not_dict_fail(self):
        assert not check_triple_margin_up("bad").passed
        assert not check_triple_margin_up([]).passed


# ════════════════════════════════════════════════════════════════
# 條件 C：獲利成長與轉機
# ════════════════════════════════════════════════════════════════
class TestEpsGrowthOrTurnaround:
    def test_eps_positive_yoy_positive_pass(self):
        r = check_eps_growth_or_turnaround({"current": 2.5, "yoy": 30.0})
        assert r.passed
        assert not r.is_turnaround

    def test_eps_zero_fail(self):
        assert not check_eps_growth_or_turnaround({"current": 0, "yoy": 100}).passed

    def test_eps_negative_fail(self):
        assert not check_eps_growth_or_turnaround({"current": -1.0, "yoy": 100}).passed

    def test_yoy_negative_fail(self):
        assert not check_eps_growth_or_turnaround({"current": 2.5, "yoy": -10}).passed

    def test_net_margin_turnaround_pass(self):
        # 即使 EPS YoY 為負，淨利率虧轉盈獨立 True
        margins = _mk_margins(n_cur=5.0, n_py=-3.0)
        r = check_eps_growth_or_turnaround({"current": 1.5, "yoy": -50}, margins)
        assert r.passed
        assert r.is_turnaround
        assert "虧轉盈" in r.reason

    def test_net_margin_not_turnaround_yoy_positive_pass(self):
        margins = _mk_margins(n_cur=18, n_py=12)
        r = check_eps_growth_or_turnaround({"current": 2.5, "yoy": 20}, margins)
        assert r.passed
        assert not r.is_turnaround

    def test_no_margins_yoy_positive_pass(self):
        r = check_eps_growth_or_turnaround({"current": 2.5, "yoy": 30})
        assert r.passed

    def test_eps_missing_fail(self):
        assert not check_eps_growth_or_turnaround(None).passed
        assert not check_eps_growth_or_turnaround({}).passed

    def test_yoy_missing_no_turnaround_fail(self):
        # cur>0 但缺 YoY 且無 margins → false
        assert not check_eps_growth_or_turnaround({"current": 2.5}).passed

    def test_net_margin_zero_prev_no_turnaround(self):
        # prev_year_q = 0 不算虧轉盈（strict < 0）
        margins = _mk_margins(n_cur=5, n_py=0)
        r = check_eps_growth_or_turnaround({"current": 2.5, "yoy": -10}, margins)
        assert not r.passed


# ════════════════════════════════════════════════════════════════
# Orchestrator: screen_stocks
# ════════════════════════════════════════════════════════════════
def _good_stock(sid="2330"):
    return {
        "id": sid,
        "monthly_revenue": {"mom": 5.0, "yoy": 30.0},
        "quarterly_margins": _mk_margins(),
        "eps": {"current": 2.5, "yoy": 45.0},
    }


class TestScreenStocks:
    def test_all_pass(self):
        out = screen_stocks([_good_stock()])
        assert len(out) == 1
        assert out[0].passed
        assert set(out[0].conditions.keys()) == {"A", "B", "C"}

    def test_only_a_enabled(self):
        s = _good_stock()
        s["quarterly_margins"] = None
        s["eps"] = None
        out = screen_stocks([s], enable_a=True, enable_b=False, enable_c=False)
        # B/C disabled → A pass 即整體 pass
        assert out[0].passed

    def test_fail_one_disables_all(self):
        s = _good_stock()
        s["monthly_revenue"] = {"mom": -1, "yoy": 30}
        out = screen_stocks([s])
        assert not out[0].passed

    def test_empty_input(self):
        assert screen_stocks([]) == []

    def test_non_list_input(self):
        assert screen_stocks(None) == []
        assert screen_stocks("not a list") == []
        assert screen_stocks({"id": "X"}) == []

    def test_skip_invalid_stock(self):
        out = screen_stocks([
            _good_stock(),
            None,
            {"no_id_field": True},
            {"id": ""},
            "not a dict",
        ])
        assert len(out) == 1

    def test_no_conditions_enabled_means_not_passed(self):
        out = screen_stocks(
            [_good_stock()], enable_a=False, enable_b=False, enable_c=False,
        )
        assert not out[0].passed
        assert out[0].conditions == {}

    def test_extra_check_pass(self):
        def tech_above_ma(_s):
            return ConditionResult("D", True, "MA 突破")

        out = screen_stocks([_good_stock()], extra_checks=[tech_above_ma])
        assert "D" in out[0].conditions
        assert out[0].passed

    def test_extra_check_exception_isolated(self):
        def broken(_s):
            raise RuntimeError("boom")

        # A/B/C 全過 + extra 拋例外 → 例外吞掉、不影響原 conds
        out = screen_stocks([_good_stock()], extra_checks=[broken])
        assert out[0].passed

    def test_extra_check_can_block_pass(self):
        def reject(_s):
            return ConditionResult("D", False, "技術面不過")

        out = screen_stocks([_good_stock()], extra_checks=[reject])
        assert not out[0].passed

    def test_does_not_crash_on_malformed_nested(self):
        s = {
            "id": "9999",
            "monthly_revenue": "not_a_dict",
            "quarterly_margins": [],
            "eps": 12345,
        }
        out = screen_stocks([s])
        assert len(out) == 1
        assert not out[0].passed
        for c in out[0].conditions.values():
            assert not c.passed


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════
class TestHelpers:
    def test_filter_passed(self):
        good = _good_stock("A")
        bad = _good_stock("B")
        bad["monthly_revenue"]["mom"] = -1
        out = screen_stocks([good, bad])
        passed = filter_passed(out)
        assert len(passed) == 1
        assert passed[0].stock_id == "A"

    def test_to_json_rows(self):
        out = screen_stocks([_good_stock()])
        rows = to_json_rows(out)
        assert isinstance(rows, list)
        assert rows[0]["stock_id"] == "2330"
        assert rows[0]["passed"] is True
        assert "A" in rows[0]["conditions"]
        assert rows[0]["conditions"]["A"]["passed"] is True

    def test_is_turnaround_property_true(self):
        s = _good_stock()
        s["quarterly_margins"]["net_margin"] = {
            "current": 5.0, "prev_q": 2.0, "prev_year_q": -3.0,
        }
        s["eps"]["yoy"] = -50  # EPS YoY 故意負，靠淨利率虧轉盈過關
        out = screen_stocks(
            [s], enable_a=False, enable_b=False, enable_c=True,
        )
        assert out[0].passed
        assert out[0].is_turnaround

    def test_is_turnaround_property_false(self):
        out = screen_stocks([_good_stock()])
        assert not out[0].is_turnaround
