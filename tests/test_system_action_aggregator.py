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


# ══════════════════════════════════════════════════════════════════════
# A-T5／A-T7 選項 1（#1199 comment 7062611025；客戶核定總管建議 2026-11-21）驗收案例 (a)～(g)
# 突變證明見 test_system_action_aggregator_mutation.py（A-T5／A-T7 新增項）。
# ══════════════════════════════════════════════════════════════════════
def test_option1_a_add_three_lights_and_g_real_format_cut_premium_verbatim():
    """(a) add 三盞燈「加碼 20／30／50%」、(g) 真實格式 cut（賺息賠本 x%／y%）與 premium（高溢價 p%）：
    formal_label 與來源 byte-identical、符合規則複本句型、A-T5 通過（字串全由來源函式／常數組出）。"""
    assert K.check_t7_option1_real_labels(A, C) == 5


def test_option1_f_rule_copies_pinned_to_source_constants():
    """(f) DEPLOY_LIGHT*_PCT 值、LIGHT_META 對映、PREMIUM_ALERT_PCT 與規則複本相等（來源改動即紅、人工複核）。"""
    from shared import dividend_station_thresholds as T
    K.check_rule_copies_pinned()
    assert K.PINNED_DEPLOY_PCT == {"DEPLOY_LIGHT1_PCT": 20.0, "DEPLOY_LIGHT2_PCT": 30.0, "DEPLOY_LIGHT3_PCT": 50.0}
    # 句型複本自我檢查：複本確實區分「改字樣」
    assert K.PINNED_ADD_RE.match(f"🟢 加碼 {T.DEPLOY_LIGHT1_PCT:.0f}%：x")
    assert not K.PINNED_ADD_RE.match("🟢 加碼 25%：x") and not K.PINNED_ADD_RE.match("🟢 加碼 20％：x")
    assert not K.PINNED_CUT_RE.match("🔴 汰弱：賺息賠本：年報酬 3.2% < 配息率 5.0%")
    assert not K.PINNED_PREMIUM_RE.match("🟡 高溢價 1.87% > 2.0% → 不追高")


_SELF_PRODUCED_RATIOS = ("30%", "30％", "３０％", "1/3", "1／3", "三成", "3成", "減半", "三分之一")


def _fresh_state():
    return K.run(A, C, K.golden_scenarios()["seven_branches"], risk="valid")


@pytest.mark.parametrize("bad", _SELF_PRODUCED_RATIOS)
@pytest.mark.parametrize("where", ["item.action_class", "item.group", "item.risk_cap_tag", "item.source_kind",
                                   "item.source_rule", "item.rule_id", "item.data_short_kind", "state.day_status",
                                   "counts.today_n", "counts.by_group<key>", "exposure_gate.status",
                                   "provenance.contract_version", "provenance.inputs<name>"])
def test_option1_b_ratio_in_any_self_produced_field_is_red(where, bad):
    """(b) 任一自產欄位被注入比例（含全形％、半、N 成、分之）→ A-T5 紅。以 object.__setattr__ 繞過契約建構
    驗證，直接驗掃描器的範圍（契約驗證是另一層縱深）。"""
    st = _fresh_state()
    it = st.items[4]                      # add 列
    if where.startswith("item."):
        object.__setattr__(it, where.split(".")[1], f"x {bad}")
    elif where == "state.day_status":
        object.__setattr__(st, "day_status", f"undeterminable {bad}")
    elif where == "counts.today_n":
        object.__setattr__(st.counts, "today_n", f"{bad}")
    elif where == "counts.by_group<key>":
        object.__setattr__(st.counts, "by_group", {f"加 {bad}": 1, "留": 0, "換": 0, "減": 0})
    elif where == "exposure_gate.status":
        object.__setattr__(st.exposure_gate, "status", f"undeterminable {bad}")
    elif where == "provenance.contract_version":
        object.__setattr__(st.provenance, "contract_version", f"system_action.v1 {bad}")
    else:
        object.__setattr__(st.provenance, "inputs", ((f"station {bad}", st.provenance.inputs[0][1]),))
    v = K.t5_violations(st)
    assert any(r == "ratio" for _p, _s, r in v), (where, bad, v)


def test_option1_b_passthrough_scope_is_exactly_the_declared_fields():
    """比例豁免只落在宣告的來源透傳欄位；其餘（自產）路徑一律受掃（預設全掃，⛔ 放寬）。"""
    import re as _re
    assert K.T5_PASSTHROUGH_FIELDS == ("items[*].formal_label", "items[*].ticker", "items[*].name",
                                       "items[*].stamp.*", "risk_cap_state.*", "provenance.inputs[*][1].*")
    st = _fresh_state()
    # 宣告字串 → 獨立 regex（[*]＝任一索引、尾端 .*＝任一子欄位）；與檢查碼的 _PASSTHROUGH_PATH_RE 對照
    pats = [_re.compile("^state\\." + _re.escape(p).replace(r"\[\*\]", r"\[\d+\]").replace(r"\.\*", r"\..+") + "$")
            for p in K.T5_PASSTHROUGH_FIELDS]
    seen_pass, seen_self = set(), set()
    for path, _s in K._strings(st):
        norm = _re.sub(r"\[\d+\]", "[#]", path[len("state."):])
        declared = any(p.match(path) for p in pats)
        assert K.is_t5_passthrough(path) == declared, (path, declared)
        (seen_pass if declared else seen_self).add(norm.split("<")[0])
    for must in ("items[#].action_class", "items[#].group", "items[#].risk_cap_tag", "day_status",
                 "counts.by_group", "exposure_gate.status", "provenance.contract_version",
                 "provenance.inputs[#][#]"):
        assert must in seen_self, (must, seen_self)
    assert "items[#].formal_label" in seen_pass


def test_option1_c_formal_label_rewritten_to_other_ratio_passes_t5_but_fails_t7():
    """(c) formal_label「加碼 20%」被改成「加碼 25%」：A-T5（選項 1）不管 formal_label 的來源比例，
    由 A-T7 逐字比對擋下（專門突變見 mutation 檔）。"""
    rows = K.golden_scenarios()["add_three_lights"]
    st = K.run(A, C, rows)
    it = st.items[0]
    assert "加碼 20%" in it.formal_label
    object.__setattr__(it, "formal_label", it.formal_label.replace("加碼 20%", "加碼 25%"))
    assert K.t5_violations(st) == []
    assert it.formal_label.encode("utf-8") != rows[0]["建議動作"].encode("utf-8")
    assert not K.PINNED_ADD_RE.match(it.formal_label)


@pytest.mark.parametrize("bad", ["（減碼 1/2）", "減碼1/2", "（全出）", "½", "１/２"])
@pytest.mark.parametrize("where", ["formal_label", "group", "risk_cap_tag", "day_status"])
def test_option1_d_forbidden_anywhere_including_formal_label(where, bad):
    """(d) 整份輸出（含 formal_label）出現「減碼 1/2」「全出」等 → A-T5 紅。"""
    st = _fresh_state()
    it = st.items[2]
    if where == "day_status":
        object.__setattr__(st, "day_status", st.day_status + bad)
    else:
        object.__setattr__(it, where, getattr(it, where) + bad)
    v = K.t5_violations(st)
    assert any(r.startswith("forbidden:") for _p, _s, r in v), (where, bad, v)
