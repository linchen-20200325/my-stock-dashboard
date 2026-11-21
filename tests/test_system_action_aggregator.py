"""System Action Aggregator 行為測試（M-A2；Architecture Gate §4.6.8 A-T2～A-T7、A-T9、A-T10）。

檢查本體在 `tests/_system_action_checks.py`（突變測試共用同一份；突變證明見
`tests/test_system_action_aggregator_mutation.py`）。A-T1 見 `..._contract.py`、A-T8 見 `..._parity.py`。
A-T11（Stage H，跨 consumer 一致）不在本批。
"""
from __future__ import annotations

import pytest

from shared import system_action_contract as C
from src.services import system_action_aggregator as A
from tests import _system_action_checks as K


def test_a_t2_table_driven_all_combinations():
    # 七分支 × Risk Cap 三態 ＋ 四級 × Risk Cap 三態 ＝ 33 組
    assert K.check_t2_table(A, C) == 33


def test_a_t2_data_short_mapping_and_class_separation():
    K.check_t2_data_short(A, C)


def test_a_t3_w5_counting():
    K.check_t3_w5(A, C)


def test_a_t3_watchlist_not_portfolio_action():
    K.check_t3_watchlist(A, C)


def test_a_t4_day_status():
    K.check_t4_day_status(A, C)


def test_a_t4_contract_defence_in_depth():
    K.check_t4_contract_guard(A, C)


def test_a_t5_no_forbidden_ratio_or_new_action_code():
    K.check_t5_forbidden(A, C)


def test_a_t6_rule_ids_within_allowlist():
    K.check_t6_rule_ids(A, C)


def test_a_t7_formal_label_byte_identical():
    K.check_t7_verbatim(A, C)


def test_a_t9_presentation_slice_independent():
    K.check_t9_slice_independent(A, C)


def test_a_t10_risk_cap_passthrough_and_exposure_gate():
    K.check_t10_risk_cap(A, C)


def test_deterministic_and_does_not_mutate_inputs():
    import copy
    g = K.golden_scenarios()
    rows = g["seven_branches"] + g["four_levels"]   # 不含錯誤列（其走勢圖 payload 帶 pandas Series，無法 == 比對）
    snap = copy.deepcopy(rows)
    dig = K.digest(rows)
    dig_snap = copy.deepcopy(dig)
    a = K.run(A, C, rows, dig=dig)
    b = K.run(A, C, rows, dig=dig)
    assert a == b
    assert rows == snap and dig == dig_snap


def test_provenance_carries_stamps_and_version():
    st = K.run(A, C, K.golden_scenarios()["all_cruise_full"])
    assert st.provenance.contract_version == C.CONTRACT_VERSION
    ins = dict(st.provenance.inputs)
    assert ins["station"] == C.ActionSourceStamp(**K.STAMP_KW)
    assert all(i.stamp == ins["station"] for i in st.items)
    # 缺 → None（照實標缺，⛔ 補今天）
    st2 = A.aggregate_system_actions(station_rows=[], station_digest=K.digest([]),
                                     risk_cap=C.RiskCapState(status=C.RISK_CAP_MISSING),
                                     station_stamp=C.ActionSourceStamp())
    assert dict(st2.provenance.inputs)["station"] == C.ActionSourceStamp(as_of=None, source=None)


# ── 輸入驗證：未知枚舉／缺鍵 fail loud，⛔ 靜默補值 ─────────────────────────
def _run_rows(rows):
    return A.aggregate_system_actions(station_rows=rows, station_digest={"total": 1},
                                      risk_cap=C.RiskCapState(status=C.RISK_CAP_MISSING),
                                      station_stamp=C.ActionSourceStamp())


@pytest.mark.parametrize("mutate, exc", [
    (lambda r: r.__setitem__("_action", "reduce_half"), ValueError),     # 新／未知分支碼
    (lambda r: r.pop("建議動作"), ValueError),
    (lambda r: r.pop("held"), ValueError),
    (lambda r: r.__setitem__("held", "yes"), TypeError),
    (lambda r: r.__setitem__("代號", ""), ValueError),
    (lambda r: r.__setitem__("建議動作", ""), ValueError),
    (lambda r: r.__setitem__("_detail", "oops"), TypeError),
    (lambda r: r.__setitem__("_detail", {"error": "x"}), ValueError),   # _action 與 error 並存
])
def test_etf_row_validation_fails_loud(mutate, exc):
    r = K.etf_row("cruise", "0050")
    mutate(r)
    with pytest.raises(exc):
        _run_rows([r])


def test_stock_and_error_row_validation_fails_loud():
    r = K.stock_row("🟢", "2330")
    r["健檢"] = "🟣"
    with pytest.raises(ValueError):
        _run_rows([r])
    r = K.stock_row("🟢", "2330")
    r["種類"] = "基金"                     # 既無 _action、也不是個股
    with pytest.raises(ValueError):
        _run_rows([r])
    e = K.error_row("9999")
    e["種類"] = "基金"
    with pytest.raises(ValueError):
        _run_rows([e])


@pytest.mark.parametrize("kw, exc", [
    ({"station_rows": None}, TypeError),
    ({"station_rows": "0050"}, TypeError),
    ({"station_rows": [1]}, TypeError),
    ({"station_digest": None}, TypeError),
    ({"risk_cap": {"status": "valid"}}, TypeError),
    ({"station_stamp": ("2026-11-20", "x")}, TypeError),
])
def test_aggregate_argument_types(kw, exc):
    base = dict(station_rows=[], station_digest={}, risk_cap=C.RiskCapState(status=C.RISK_CAP_MISSING),
                station_stamp=C.ActionSourceStamp())
    base.update(kw)
    with pytest.raises(exc):
        A.aggregate_system_actions(**base)


def test_risk_cap_state_from_allocation_edges():
    from shared.allocation_decision import Cap
    with pytest.raises(ValueError):
        A.risk_cap_state_from_allocation(object(), error="boom")
    with pytest.raises(TypeError):
        A.risk_cap_state_from_allocation(None, error=None)

    class _Alloc:
        caps = (Cap(C.SYSTEM_RISK_CAP_NAME, 40), Cap(C.SYSTEM_RISK_CAP_NAME, 30))
    with pytest.raises(ValueError):
        A.risk_cap_state_from_allocation(_Alloc())
    assert A.risk_cap_state_from_allocation(None).status == C.RISK_CAP_MISSING

    class _Zero:
        caps = (Cap(C.SYSTEM_RISK_CAP_NAME, 0, "全面防守"),)
    rc = A.risk_cap_state_from_allocation(_Zero())
    # 0 是真的 0（⛔ 當成缺）；reason 原樣
    assert (rc.status, rc.system_cap_pct, rc.system_cap_reason) == (C.RISK_CAP_VALID, 0, "全面防守")
