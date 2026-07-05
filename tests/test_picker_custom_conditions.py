"""選股網「自訂必過條件」純函式測試(15 項中選任意項 + 至少過 N)。"""
from src.ui.tabs.tab_stock_picker import (
    PICKER_ALL_CONDITIONS,
    PICKER_S1_CONDITIONS,
    PICKER_S2_CONDITIONS,
    count_condition_passes,
    filter_by_custom_conditions,
)


def _stock(tid, passes):
    """passes: set of label_key 該檔通過的條件;其餘給 ❌。"""
    r = {"ticker": tid}
    for key, _ in PICKER_ALL_CONDITIONS:
        r[key] = "✅ ok" if key in passes else "❌ no"
    return r


def test_conditions_ssot_counts():
    assert len(PICKER_S1_CONDITIONS) == 9
    assert len(PICKER_S2_CONDITIONS) == 6
    assert len(PICKER_ALL_CONDITIONS) == 15
    # 無重複 key
    keys = [k for k, _ in PICKER_ALL_CONDITIONS]
    assert len(set(keys)) == 15


def test_count_condition_passes():
    r = _stock("2330", {"debt_ratio_label", "three_rate_label", "ma20_label"})
    assert count_condition_passes(r, ["debt_ratio_label", "three_rate_label"]) == 2
    assert count_condition_passes(r, ["debt_ratio_label", "div_5y_label"]) == 1
    assert count_condition_passes(r, ["div_5y_label", "kd_label"]) == 0


def test_count_ignores_warning_and_question_labels():
    # ⚠️ / ❓ / 缺欄 都不算過(只有 ✅ 算)
    r = {"a": "⚠️ 季末連增", "b": "❓ N/A", "c": "✅ good"}
    assert count_condition_passes(r, ["a", "b", "c", "missing"]) == 1


def test_filter_empty_selection_returns_none():
    # 未選任何條件 → 回 None(caller 走預設門檻)
    assert filter_by_custom_conditions([_stock("1", set())], [], 0) is None


def test_filter_at_least_n():
    stocks = [
        _stock("A", {"debt_ratio_label", "three_rate_label", "book_value_label"}),  # 3 過
        _stock("B", {"debt_ratio_label"}),                                          # 1 過
        _stock("C", {"debt_ratio_label", "three_rate_label"}),                      # 2 過
    ]
    sel = ["debt_ratio_label", "three_rate_label", "book_value_label"]
    # 至少過 3 → 只有 A
    assert [r["ticker"] for r in filter_by_custom_conditions(stocks, sel, 3)] == ["A"]
    # 至少過 2 → A、C
    assert [r["ticker"] for r in filter_by_custom_conditions(stocks, sel, 2)] == ["A", "C"]
    # 至少過 1 → 全部
    assert len(filter_by_custom_conditions(stocks, sel, 1)) == 3


def test_filter_mixed_s1_s2_conditions():
    # 混選基本面 + 籌碼:負債比 + MA20站穩,至少過 2(= 兩者都要過)
    stocks = [
        _stock("X", {"debt_ratio_label", "ma20_label"}),   # 兩者都過
        _stock("Y", {"debt_ratio_label"}),                 # 只過基本面
    ]
    sel = ["debt_ratio_label", "ma20_label"]
    assert [r["ticker"] for r in filter_by_custom_conditions(stocks, sel, 2)] == ["X"]


def test_filter_min_pass_clamped_to_one():
    # min_pass < 1 → 視為 1(不會回全空)
    stocks = [_stock("A", {"debt_ratio_label"})]
    out = filter_by_custom_conditions(stocks, ["debt_ratio_label"], 0)
    assert [r["ticker"] for r in out] == ["A"]
