"""AB-2a 第二輪收緊測試（fast lane）：holding_ref 編碼、鍵字元、G5 涵蓋、mode 綁定、措辭忠實度、診斷歸屬。

每個測試守一個紅隊發現（Q 編號見 spec §8.1）；斷言閘門＋具體 code，不接受「反正有紅」。
"""
from __future__ import annotations

import dataclasses
import random

import pytest

from shared import decision_digest_terms as T
from shared.decision_digest import (
    AiParticipation, DataStatus, MissingReason, StrategyType,
)
from shared.decision_digest_grounding import (
    expand, SummaryDraft, SummaryResult, SummarySection, build_ref_index, check_summary, holding_ref, invalid_notices,
    render_draft, section_basis,
)
from shared.decision_digest_validator import SECTION_ALL, SummaryState, assess_digest
from src.services.decision_digest_summary import build_rule_summary, compose_rule_draft
from tests.decision_digest_factory import (
    action, entry, force_set, make_digest, missing, ok_text, ok_val,
)

BH, CG, MKT, ACT = T.SEC_BUY_AND_HOLD, T.SEC_CAPITAL_GAIN, T.SEC_MARKET, T.SEC_ACTIONS


def vcodes(d):
    return {(v.gate, v.section, v.code) for v in assess_digest(d).violations}


def gcodes(rep):
    return {(v.gate, v.code) for v in rep.violations}


def with_key(d, *, symbol=None, pid=None, idx=0):
    """合法 Digest → 繞過 frozen 把第 idx 檔持股的鍵改成壞值（模擬 AB-0 漏網／被竄改；assess 必須擋）。"""
    k = d.holdings.entries[idx].key
    force_set(k, **({"symbol": symbol} if symbol is not None else {}), **({"portfolio_id": pid} if pid is not None else {}))
    return d


def lines(d, sec):
    r = build_rule_summary(d)
    return [t for k, ts in render_draft(d, SummaryDraft(r.sections)) if k == sec for t in ts]


# ── 紅隊 1：holding_ref 無歧義 ────────────────────────────────────────────
def test_holding_ref_is_unambiguous_for_colon_keys():
    assert holding_ref("a:b", "c") != holding_ref("a", "b:c")
    assert holding_ref("pf-A", "0050") == "holding:4:pf-A:0050"


def test_portfolio_id_with_colon_still_has_unique_refs_and_build_never_raises():
    es = [entry("c", "t", "add", pid="a:b"), entry("b:c", "t", "add", pid="a")]
    d = make_digest(entries=es, items=[])
    # symbol "b:c" 不在字元集 → INVALID（不是靜默通過）；但 portfolio_id 含冒號的合法鍵 ref 唯一
    d2 = make_digest(entries=[entry("c", "t", "add", pid="a:b"), entry("c", "t", "add", pid="a")], items=[])
    assert not any(c == "ref_id_collision" for _, _, c in vcodes(d2))
    assert assess_digest(d).state is SummaryState.INVALID
    build_rule_summary(d2)                               # 不得 raise


def test_ref_collision_is_invalid():
    # fact_id 與 action_id 相同 → evidence 指向含糊（AB-0 不檢查跨命名空間唯一）
    a = action("0050", "t", "add")
    d = make_digest(market_facts=[ok_text("market.regime", "x"), ok_text(a.action_id, "y")],
                    entries=[entry("0050", "t", "add")], items=[a])
    got = vcodes(d)
    assert got == {(T.GATE_AB2A_REFS, SECTION_ALL, "ref_id_collision")}
    assert assess_digest(d).state is SummaryState.INVALID


def test_assess_build_consistency_fuzz():
    rng = random.Random(7)
    pids = ["pf-A", "a:b", "a", "x:1:y", "1", ""]
    syms = ["0050", "2330", "00878", "00679B", "b:c", "A.B", "x y", "中文"]
    n_valid = 0
    for _ in range(300):
        try:
            es = [entry(rng.choice(syms), "t", "add", pid=rng.choice(pids)) for _ in range(rng.randint(0, 4))]
            d = make_digest(entries=es, items=[])
        except ValueError:
            continue                                      # AB-0 建構期就擋掉的不屬本檢查
        a = assess_digest(d)
        if a.state is SummaryState.INVALID:
            continue
        n_valid += 1
        r = build_rule_summary(d)                         # assess 通過 → build 不得 raise
        assert check_summary(d, SummaryDraft(r.sections)).clean
    assert n_valid > 20


def test_draft_omitting_holdings_sentences_is_rejected():
    d = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定")],
                    items=[])
    b = compose_rule_draft(d)
    cut = SummaryDraft(tuple(SummarySection(s.key, ()) if s.key == BH else s for s in b.sections))
    rep = check_summary(d, cut)
    assert not rep.accepted and gcodes(rep) == {(T.GATE_G5, "empty_section")}


# ── 紅隊 2：鍵字元與 symbol 字元集 ─────────────────────────────────────────
# AB-0 建構期已擋掉一部分壞鍵（空字串、空白、零寬 → fact_id 檢查）；validator 是第二道（繞過 frozen／AB-0 漏網），
# 故以 force_set 注入，斷言 assess 自己會擋，build 不會與 assess 不一致。
@pytest.mark.parametrize("bad", ["\ue000", "\u0301", "\u200b", "a\u2028b", "\u0378", "a b", "中文", "", "-x",
                                 "a" * 13, "a:b", "ａ", "\ud800"])
def test_bad_symbol_rejected(bad):
    d = with_key(make_digest(entries=[entry("0050", "t", "add")], items=[]), symbol=bad)
    assert assess_digest(d).state is SummaryState.INVALID
    assert {c for _, _, c in vcodes(d)} & {"bad_key", "bad_symbol"}      # AB-0 先擋，或 AB-2a 第二道擋
    assert build_rule_summary(d).state is SummaryState.INVALID           # build 與 assess 一致，不 raise


@pytest.mark.parametrize("sym", ["0050", "2330", "6488", "00878", "006208", "00679B", "2330.TW", "BRK-B"])
def test_tw_codes_accepted(sym):
    d = make_digest(entries=[entry(sym, "t", "add")], items=[])
    assert not any(c == "bad_symbol" for _, _, c in vcodes(d))
    build_rule_summary(d)


@pytest.mark.parametrize("bad", ["pf\ue000", "\u0301pf", "pf\u200b", "pf\u2028", "pf\u0378", "pf\ud800", "pf\u3000",
                                 "pf\xa0"])
def test_bad_portfolio_id_rejected(bad):
    d = with_key(make_digest(entries=[entry("0050", "t", "add")], items=[]), pid=bad)
    assert {c for _, _, c in vcodes(d)} & {"bad_key", "bad_portfolio_id_chars"}
    assert assess_digest(d).state is SummaryState.INVALID


# AB-0 不擋、只有 AB-2a 第二道擋的壞字元（私用區／未指派／孤立組合記號）：精確斷言 code 與歸屬段
@pytest.mark.parametrize("bad", ["\ue000", "\u0301", "\u0378"])
def test_ab2a_second_gate_catches_what_ab0_lets_through(bad):
    d = make_digest(entries=[entry("0050", "t", "add")], items=[action("0050", "t", "add")])
    force_set(d.holdings.entries[0].key, portfolio_id="pf" + bad if bad != "\u0301" else bad + "pf")
    force_set(d.actions.items[0].target, portfolio_id=d.holdings.entries[0].key.portfolio_id)
    got = vcodes(d)
    assert (T.GATE_AB2A_TEXT, BH, "bad_portfolio_id_chars") in got or (T.GATE_AB0_CONTRACT, BH, "bad_key") in got
    d2 = make_digest(entries=[entry("0050", "t", "add")], items=[action("0050", "t", "add")])
    force_set(d2.holdings.entries[0].key, symbol="0050" + bad)
    force_set(d2.actions.items[0].target, symbol="0050" + bad)
    assert {c for _, _, c in vcodes(d2)} & {"bad_key", "bad_symbol"}
    assert (T.GATE_AB2A_TEXT, ACT, "bad_symbol") in vcodes(d2) or (T.GATE_AB0_CONTRACT, ACT, "bad_key") in vcodes(d2)


# ── 紅隊 3：G5 涵蓋 ───────────────────────────────────────────────────────
def test_omitting_an_ok_market_fact_is_rejected():
    d = make_digest()
    b = compose_rule_draft(d)
    mk = next(s for s in b.sections if s.key == MKT)
    cut = SummaryDraft(tuple(SummarySection(MKT, mk.sentences[1:]) if s.key == MKT else s for s in b.sections))
    rep = check_summary(d, cut)
    assert not rep.accepted and gcodes(rep) == {(T.GATE_G5, "missing_disclosure")}
    assert rep.surviving is None                          # 未通過者沒有可用內容（Q37）


def test_omitting_holdings_entry_and_action_is_rejected():
    d = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.CAPITAL_GAIN, source="客戶設定")],
                    items=[action("0050", "t", "add")])
    b = compose_rule_draft(d)
    for key in (CG, ACT):
        cut = SummaryDraft(tuple(SummarySection(key, ()) if s.key == key else s for s in b.sections))
        rep = check_summary(d, cut)
        assert not rep.accepted and gcodes(rep) == {(T.GATE_G5, "empty_section")}, key


def test_section_basis_covers_ok_market_facts():
    d = make_digest()
    ids = [r for r, _ in section_basis(d, MKT)]
    assert all(f.fact_id in ids for f in d.market.facts)


# ── 紅隊 4：mode 綁定 ─────────────────────────────────────────────────────
_ALL_G = ("G1", "G2", "G3", "G4", "G5", "G6")


def _ai_digest(mode):
    d = make_digest()
    if mode is AiParticipation.AI_EXPLAINED:
        return dataclasses.replace(d, ai_participation=mode, ai_passed_checks=_ALL_G)
    return dataclasses.replace(d, ai_participation=mode, ai_failed_checks=("G3",))


@pytest.mark.parametrize("mode", [AiParticipation.AI_EXPLAINED, AiParticipation.AI_REJECTED])
def test_non_rule_only_mode_is_never_constructible_even_with_a_consistent_ai_digest(mode):
    d = _ai_digest(mode)                                  # AB-0 層合法的 AI Digest（mode 與 digest 一致）
    assert assess_digest(d).state is not SummaryState.INVALID
    r = build_rule_summary(make_digest())
    with pytest.raises(ValueError, match="只允許 mode=rule_only"):
        SummaryResult(d, mode, r.sections)


@pytest.mark.parametrize("mode", [AiParticipation.AI_EXPLAINED, AiParticipation.AI_REJECTED])
def test_mode_must_match_digest_participation(mode):
    d = make_digest()
    r = build_rule_summary(d)
    with pytest.raises(ValueError, match="只允許 mode=rule_only"):
        SummaryResult(d, mode, r.sections)                # digest rule_only、mode 非 rule_only
    with pytest.raises(ValueError, match="必須與 digest.ai_participation 一致"):
        SummaryResult(_ai_digest(mode), AiParticipation.RULE_ONLY, r.sections)   # mode rule_only、digest 非 rule_only


def test_mode_must_be_an_ai_participation_member():
    d = make_digest()
    with pytest.raises(ValueError, match="必須是 AiParticipation"):
        SummaryResult(d, "rule_only", build_rule_summary(d).sections)


def test_q26_holding_fact_as_of_none_is_not_quotable_and_does_not_raise():
    d = make_digest()
    f = d.holdings.entries[0].facts[0]
    force_set(f.provenance, as_of=None)
    idx = build_ref_index(d)
    assert expand(d, idx[f.fact_id], T.FIELD_AS_OF) == (None, T.GATE_G1, "field_not_quotable")


# ── 語意 5：strategy wording（Defect A）────────────────────────────────────
def test_capital_gain_section_does_not_claim_unset_when_holdings_are_classified():
    d = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定")],
                    items=[])
    cg = lines(d, CG)
    assert cg == ["⬜ 資本利得：此策略下無歸類持股"] or "此策略下無歸類持股" in cg[0]
    assert "尚未設定" not in cg[0]


def test_unset_wording_only_when_all_unclassified():
    d = make_digest(entries=[entry("0050", "t", "add")], items=[])
    assert "尚未設定投資策略分類" in lines(d, CG)[0] and "尚未設定投資策略分類" in lines(d, BH)[0]


# ── 語意 6：原因忠實措辭（Defect B）與 fallback 標籤（Defect C）────────────
@pytest.mark.parametrize("reason,word", [
    (MissingReason.NOT_APPLICABLE, "不適用"), (MissingReason.NO_VARIATION, "期間無變異"),
    (MissingReason.CONTRACT_DRIFT, "資料契約不一致"), (MissingReason.NOT_DEFINED, "尚未定義"),
    (MissingReason.NOT_WIRED, "尚未接線")])
def test_non_insufficient_reasons_have_own_wording(reason, word):
    d = make_digest(market_facts=[missing("market.regime", reason), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 1.5)])
    line = lines(d, MKT)[0]
    assert word in line and "資料不足" not in line and line.endswith("無法判定")


@pytest.mark.parametrize("reason,label", [(MissingReason.NO_INPUT, "尚無輸入"), (MissingReason.FETCH_FAILED, "抓取失敗"),
                                          (MissingReason.NOT_ENOUGH_HISTORY, "歷史長度不足")])
def test_insufficient_family_keeps_data_insufficient_wording(reason, label):
    d = make_digest(market_facts=[missing("market.regime", reason), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 1.5)])
    line = lines(d, MKT)[0]
    assert label in line and "資料不足" in line


def test_missing_reason_labels_are_pinned_and_distinct():
    assert T.MISSING_REASON_LABELS == {
        "no_input": "尚無輸入", "fetch_failed": "抓取失敗", "not_enough_history": "歷史長度不足",
        "not_applicable": "不適用", "contract_drift": "資料契約異常", "no_variation": "期間無變異",
        "not_defined": "尚未定義", "not_wired": "尚未接線"}
    assert len(set(T.MISSING_REASON_LABELS.values())) == len(T.MISSING_REASON_LABELS)


def test_more_than_one_fallback_labelled_market_fact_is_rejected():
    d = make_digest(market_facts=[ok_text("market.regime", "x"), ok_text("market.zzz1", "a"), ok_text("market.zzz2", "b")])
    assert (T.GATE_AB2A_TEXT, MKT, "ambiguous_fact_label") in vcodes(d)
    assert assess_digest(d).state is SummaryState.INVALID
    assert build_rule_summary(d).state is SummaryState.INVALID


def test_one_fallback_labelled_fact_is_still_allowed():
    d = make_digest(market_facts=[ok_text("market.zzz1", "a")])
    assert not any(c == "ambiguous_fact_label" for _, _, c in vcodes(d))


# ── 補洞測試：Q08 / Q22 / Q26 / Q41 ────────────────────────────────────────
def test_q08_action_id_reserved_prefix():
    a = action("0050", "t", "add")
    a = dataclasses.replace(a, action_id="section:holdings")
    d = make_digest(entries=[entry("0050", "t", "add")], items=[a])
    assert (T.GATE_AB2A_REFS, SECTION_ALL, "ref_id_reserved") in vcodes(d)


def test_q22_unkeyed_sentence_needs_positive_count():
    d = make_digest(unkeyed=2)
    b = compose_rule_draft(d)
    assert check_summary(d, b).clean
    rep = check_summary(make_digest(unkeyed=0), b)        # 同一份草稿，Digest 沒有未帶鍵持股 → 句型前提不成立
    assert not rep.accepted and gcodes(rep) == {(T.GATE_G3, "precondition_failed")}


def test_q26_holding_fact_without_as_of_does_not_make_check_raise():
    e = entry("0050", "t", "add")
    f = dataclasses.replace(e.facts[0], status=DataStatus.STALE,
                            provenance=dataclasses.replace(e.facts[0].provenance, as_of=e.facts[0].provenance.as_of))
    d = make_digest(entries=[dataclasses.replace(e, facts=(f,))], items=[action("0050", "t", "add")])
    force_set(f.provenance, as_of=None)                   # AB-0 建構期不允許；模擬繞過後 check 不得 raise
    b = compose_rule_draft(make_digest(entries=[entry("0050", "t", "add")], items=[action("0050", "t", "add")]))
    check_summary(d, b)                                   # 不得 raise（拒收即可）


@pytest.mark.parametrize("reason", [MissingReason.FETCH_FAILED, MissingReason.NO_INPUT])
def test_q41_holdings_reason_expansion_uses_holdings_own_reason(reason):
    d = make_digest(entries=[], items=[], holdings_reason=reason)
    line = lines(d, BH)[0]
    assert T.MISSING_REASON_LABELS[reason.value] in line


def test_q35_intl_trend_observations_are_restricted_group():
    from tests.decision_digest_factory import RISK_RULE
    from shared.decision_digest import DefinitionSection, DefinitionState
    obs = ok_val("intl.obs1", 123.4, rule=RISK_RULE)
    d = dataclasses.replace(make_digest(), intl_trend=DefinitionSection(DefinitionState.NOT_DEFINED, observations=(obs,)))
    idx = build_ref_index(d)
    assert idx["intl.obs1"].group == "restricted" and idx["risk_cap.cap_pct"].group == "restricted"
    assert idx["market.health"].group == "market"
    assert expand(d, idx["intl.obs1"], T.FIELD_VALUE) == (None, T.GATE_G2, "restricted_value")   # 數值不得出現在摘要


@pytest.mark.parametrize("cat_char", ["́", "ः", "⃝"])      # Mn / Mc / Me
def test_q49_combining_categories_all_rejected(cat_char):
    d = make_digest(market_facts=[ok_text("market.regime", cat_char + "a")])
    assert assess_digest(d).state is SummaryState.INVALID


def test_q34_invalid_notices_ordering_is_deterministic():
    d = make_digest(entries=[entry("0050\ue000", "t", "add")], items=[], market_facts=[ok_text("market.regime", "\ue000")])
    n = invalid_notices(assess_digest(d))
    assert n == invalid_notices(assess_digest(d))
    assert n[3] == "違規代碼：bad_symbol、control_chars_in_text"          # 代碼依字典序，與違規產生順序無關
    assert n[1] == "無效段落：市場、存股、資本利得" and n[2] == "失敗閘門：AB2A_TEXT"


# ── 診斷歸屬：違規落在哪一段、順序、閘門 ────────────────────────────────────
def test_violation_attribution_text_chars_per_section():
    d = make_digest(market_facts=[ok_text("market.regime", "a\ue000")])
    a = assess_digest(d)
    assert {(v.gate, v.section, v.code) for v in a.violations} == {(T.GATE_AB2A_TEXT, MKT, "control_chars_in_text")}
    assert a.invalid_sections == (MKT,) and a.failed_gates == (T.GATE_AB2A_TEXT,)


def test_invalid_sections_follow_section_key_order():
    d = make_digest(entries=[entry("0050\ue000", "t", "add")], items=[], market_facts=[ok_text("market.regime", "\ue000")])
    a = assess_digest(d)
    assert a.invalid_sections == (MKT, BH, CG)
    assert {(v.gate, v.section, v.code) for v in a.violations} == {
        (T.GATE_AB2A_TEXT, MKT, "control_chars_in_text"), (T.GATE_AB2A_TEXT, BH, "bad_symbol"),
        (T.GATE_AB2A_TEXT, CG, "bad_symbol")}


def test_restricted_value_vs_field_not_quotable_are_different_codes_and_gates():
    d = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定")], items=[])
    idx = build_ref_index(d)
    assert expand(d, idx["risk_cap.cap_pct"], T.FIELD_VALUE) == (None, T.GATE_G2, "restricted_value")
    assert expand(d, idx["risk_cap.cap_pct"], T.FIELD_WORDING) == (None, T.GATE_G1, "field_not_quotable")
    assert expand(d, idx[holding_ref("pf-A", "0050")], "strategy_source") == (None, T.GATE_G1, "field_not_quotable")
    assert expand(d, idx[holding_ref("pf-A", "0050")], T.FIELD_STRATEGY)[0] == "存股"


# ══════════════════════════════════════════════════════════════════════
# 突變補強（第二輪 mutation 倖存者的對應測試）
# ══════════════════════════════════════════════════════════════════════
from shared.decision_digest_grounding import SHAPES, Lit, Ref, SummarySentence, section_ref      # noqa: E402
from shared.decision_digest_validator import _sections_for_path                                        # noqa: E402


def _shape_sentence(shape_id, ref_id):
    sh = next(x for x in SHAPES if x.sid == shape_id)
    return SummarySentence(tuple(Lit(e[1]) if e[0] == "L" else Ref(ref_id, e[3]) for e in sh.skeleton))


def _with_sentence(draft, key, sentence):
    return SummaryDraft(tuple(SummarySection(s.key, s.sentences + (sentence,)) if s.key == key else s
                              for s in draft.sections))


def test_holding_ref_encoding_pins_length_of_portfolio_id_not_symbol():
    assert holding_ref("a:b", "c") == "holding:3:a:b:c"
    assert holding_ref("a", "b") == "holding:1:a:b"
    assert holding_ref("", "x") == "holding:0::x"


@pytest.mark.parametrize("path,secs", [
    ("market.facts[0].text", (MKT,)), ("tw_trend.observations[0]", (MKT,)), ("intl_trend.x", (MKT,)),
    ("valuation.x", (MKT,)), ("risk_cap.cap_pct", (MKT,)), ("industry.x", (T.SEC_INDUSTRY,)),
    ("holdings.entries[0]", (BH, CG)), ("holdings[0]", (BH, CG)), ("actions.items[0]", (ACT,)),
    ("actions[0]", (ACT,)), ("nope.x", (SECTION_ALL,)), ("", (SECTION_ALL,)), (None, (SECTION_ALL,))])
def test_path_to_summary_section_mapping_is_pinned(path, secs):
    assert _sections_for_path(path) == secs


def test_q05_holding_fact_text_violation_is_attributed_to_actions():
    e = entry("0050", "t", "add")                        # 持股事實文字（行動文字的來源）含私用區字元
    d = make_digest(entries=[e], items=[action("0050", "t", "add")])
    got = {(v.gate, v.section, v.code, v.path) for v in assess_digest(d).violations}
    assert got == {(T.GATE_AB2A_TEXT, ACT, "control_chars_in_text", "holdings.entries[0].facts[0].text")}


def test_q06_strategy_source_violation_is_attributed_to_both_strategy_sections():
    d = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="x")],
                    items=[action("0050", "t", "add")])
    got = {(v.section, v.code) for v in assess_digest(d).violations}
    assert got == {(BH, "control_chars_in_text"), (CG, "control_chars_in_text")}


def test_q03_q04_risk_cap_and_industry_violations_are_attributed():
    d = make_digest()
    force_set(d.risk_cap.cap_pct, text="x")                  # AB-0 契約違規（Risk Cap 不得帶 text）→ 歸屬市場段
    got = {(v.gate, v.section) for v in assess_digest(d).violations}
    assert got and {sec for _, sec in got} == {MKT}
    d2 = make_digest()
    force_set(d2.industry, observations=("x",))
    got2 = {(v.gate, v.section) for v in assess_digest(d2).violations}
    assert got2 and {sec for _, sec in got2} == {T.SEC_INDUSTRY}


def test_q12_all_scope_comes_last_in_invalid_sections():
    a = make_digest(market_facts=[ok_text("market.regime", "a"), ok_text("market.zzz1", "x"),
                                  ok_text("market.zzz2", "y")])
    rep = assess_digest(a)
    assert {(v.section, v.code) for v in rep.violations} == {(MKT, "control_chars_in_text"), (MKT, "ambiguous_fact_label")}
    dd = make_digest(market_facts=[ok_text("market.regime", "a"), ok_text("market.light", "🟢"),
                                   ok_text("market.health", "x")])
    force_set(dd.market.facts[1], fact_id="section:evil")
    rep2 = assess_digest(dd)
    assert rep2.invalid_sections[-1] == SECTION_ALL and rep2.invalid_sections[0] == MKT


def test_q16_collision_violation_reports_actions_items_path():
    a = action("0050", "t", "add")
    d = make_digest(market_facts=[ok_text("market.regime", "x"), ok_text(a.action_id, "y")],
                    entries=[entry("0050", "t", "add")], items=[a])
    assert {(v.code, v.path) for v in assess_digest(d).violations} == {("ref_id_collision", "actions.items")}


def test_q27_unknown_missing_reason_label_is_explicit_not_empty():
    d = make_digest(entries=[], items=[])
    force_set(d.holdings, missing_reason=None)               # AB-0 不允許；模擬漂移後 expand 必須明示「原因不明」
    idx = build_ref_index(d)
    assert expand(d, idx[section_ref("holdings")], T.FIELD_REASON) == (T.MISSING_REASON_LABEL_UNKNOWN, None, None)
    assert T.MISSING_REASON_LABEL_UNKNOWN == "原因不明"
    idx2 = build_ref_index(make_digest(market_facts=[missing("market.regime")]))
    f = idx2["market.regime"].obj
    force_set(f, missing_reason=None)
    assert expand(d, idx2["market.regime"], T.FIELD_REASON) == (None, T.GATE_G1, "field_not_quotable")


def test_q28_duplicate_section_keys_with_right_length_are_rejected():
    d = make_digest()
    b = compose_rule_draft(d)
    secs = list(b.sections)
    dup = SummaryDraft(tuple([secs[0], secs[0], *secs[2:]]))           # 長度仍是 5，但缺 industry、market 重複
    rep = check_summary(d, dup)
    assert not rep.accepted and {c for _, c in gcodes(rep)} >= {"duplicate_section", "missing_section"}
    assert "section_order" not in {c for _, c in gcodes(rep)}


def test_q37_section_with_only_a_bad_sentence_is_not_reported_empty():
    d = make_digest()
    b = compose_rule_draft(d)
    bad = SummarySentence((Lit(T.TPL_GLYPH), Ref("market.regime", T.FIELD_LABEL)))
    forged = SummaryDraft(tuple(SummarySection(MKT, (bad,)) if s.key == MKT else s for s in b.sections))
    rep = check_summary(d, forged)
    assert not rep.accepted and "empty_section" not in {c for _, c in gcodes(rep)}
    assert rep.surviving is None


def test_q57_restricted_group_fields_have_distinct_exact_codes():
    d = make_digest()
    idx = build_ref_index(d)
    for fld in (T.FIELD_VALUE, T.FIELD_TEXT, T.FIELD_AS_OF):
        assert expand(d, idx["risk_cap.cap_pct"], fld) == (None, T.GATE_G2, "restricted_value"), fld
    assert expand(d, idx["risk_cap.cap_pct"], T.FIELD_LABEL) == (None, T.GATE_G1, "field_not_quotable")


def test_q58_q59_wrong_group_gate_and_code_for_holding_fact_in_market_shapes():
    d = make_digest()
    b = compose_rule_draft(d)
    hf = d.holdings.entries[0].facts[0].fact_id
    for sid in ("fact_missing", "fact_not_applicable", "fact_text_ok", "fact_invalid"):
        rep = check_summary(d, _with_sentence(b, MKT, _shape_sentence(sid, hf)))
        assert (T.GATE_G4, "wrong_group") in gcodes(rep), sid
        assert (T.GATE_G3, "wrong_group") not in gcodes(rep)


def test_z18_missing_shape_for_a_different_non_insufficient_reason_is_rejected():
    d = make_digest(market_facts=[missing("market.regime", MissingReason.NO_VARIATION), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 1.5)])
    b = compose_rule_draft(d)
    s = _shape_sentence("fact_not_applicable", "market.regime")
    rep = check_summary(d, _with_sentence(b, MKT, s))
    assert (T.GATE_G3, "reason_mismatch") in gcodes(rep)
    s2 = _shape_sentence("fact_missing", "market.regime")                       # 非資料不足原因不得用資料不足句型
    assert (T.GATE_G3, "reason_mismatch") in gcodes(check_summary(d, _with_sentence(b, MKT, s2)))


def test_z24_z25_strategy_unset_and_none_preconditions_are_disjoint():
    classified = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定")],
                             items=[action("0050", "t", "add")])
    unclassified = make_digest(entries=[entry("0050", "t", "add")], items=[action("0050", "t", "add")])
    rid = section_ref("holdings")
    unset_s = _shape_sentence(f"strategy_unset:{CG}", rid)
    none_s = _shape_sentence(f"strategy_none:{CG}", rid)
    b1, b0 = compose_rule_draft(classified), compose_rule_draft(unclassified)
    def with_only(draft, key, sent):
        return SummaryDraft(tuple(SummarySection(key, (sent,)) if s.key == key else s for s in draft.sections))
    assert (T.GATE_G3, "precondition_failed") in gcodes(check_summary(classified, with_only(b1, CG, unset_s)))
    assert (T.GATE_G3, "precondition_failed") in gcodes(check_summary(unclassified, with_only(b0, CG, none_s)))
    assert check_summary(classified, with_only(b1, CG, none_s)).clean
    assert check_summary(unclassified, with_only(b0, CG, unset_s)).clean


def test_g20_usable_requires_accepted_even_if_surviving_present():
    d = make_digest()
    b = compose_rule_draft(d)
    ok = check_summary(d, b)
    forged = dataclasses.replace(ok, accepted=False)
    assert forged.surviving is not None and forged.usable is False and forged.clean is False


def test_q24b_strategy_none_is_not_allowed_when_holdings_are_unavailable_even_if_entries_classified():
    d = make_digest(entries=[entry("0050", None, strategy=StrategyType.BUY_AND_HOLD, source="客戶設定")], items=[])
    assert d.holdings.availability.value == "unavailable" and d.holdings.entries      # 有 entry 但沒有任何事實
    b = compose_rule_draft(d)
    none_s = _shape_sentence(f"strategy_none:{CG}", section_ref("holdings"))
    forged = SummaryDraft(tuple(SummarySection(CG, (none_s,)) if s.key == CG else s for s in b.sections))
    assert (T.GATE_G3, "precondition_failed") in gcodes(check_summary(d, forged))
    assert check_summary(d, b).clean


def test_q34_many_codes_are_listed_sorted_regardless_of_hash_order():
    d = make_digest(
        market_facts=[ok_text("market.regime", "a"), ok_text("market.zzz1", "x"), ok_text("market.zzz2", "y"),
                      ok_val("market.health", 1.5)],
        entries=[entry("0050", "t", "add"), entry("0056", "t", "add")], items=[])
    force_set(d.holdings.entries[0].key, symbol="a:b", portfolio_id="p")
    force_set(d.market.facts[3], unit="bps")
    force_set(d.market.facts[1], fact_id="section:evil")
    force_set(d.holdings.entries[1].key, symbol="0056")
    codes_ = {v.code for v in assess_digest(d).violations}
    assert codes_ >= {"control_chars_in_text", "ambiguous_fact_label", "bad_symbol", "bad_portfolio_id_chars",
                      "unsupported_unit", "ref_id_reserved"}
    line = invalid_notices(assess_digest(d))[3]
    assert line == "違規代碼：" + "、".join(sorted(codes_))
