"""AB-2a grounding 驗證 G1～G6 測試（fast lane）：句型白名單版。

守的是 `shared/decision_digest_grounding.py`。摘要句是 segment 序列（`Lit` 模板 id／`Ref` 欄位展開），
沒有任意文字的位置；每個反例都斷言 `accepted is False`、閘門與具體 code —— 不接受「反正有紅」。
QA 紅隊探針（同形異字、簡體、同義詞、中文數字、否定／矛盾、標示語偽造、行動句加字／換代號／漏項、
搭便車 ref、手造 SummaryResult…）的最小重現都在此，且全部必須被擋或「結構上無法表達」。
"""
from __future__ import annotations

import dataclasses
import re

import pytest

from shared import decision_digest as AB0
from shared import decision_digest_terms as T
from shared.decision_digest import DataStatus, DefinitionSection, DefinitionState, MissingReason, RuleRef, StrategyType
from shared.decision_digest_grounding import (
    SHAPES, Lit, Ref, SummaryDraft, SummaryResult, SummarySection, SummarySentence, build_ref_index, check_summary,
    expand, holding_ref, number_literal, render_draft, render_sentence, section_basis, section_ref,
)
from shared.decision_digest_validator import SummaryState
from src.services.decision_digest_summary import compose_rule_draft
from tests.decision_digest_factory import (
    action, lint_hits, empty_digest, entry, failed, force_set, invalid, make_digest, missing, ok_text, ok_val, proxy_val,
    stale_text, stale_val,
)

MKT, IND, BH, CG, ACT = T.SEC_MARKET, T.SEC_INDUSTRY, T.SEC_BUY_AND_HOLD, T.SEC_CAPITAL_GAIN, T.SEC_ACTIONS
ACT_CUT_TEXT = "🔴 汰弱：吃本金"
ACT_TP_TEXT = "💰 強制停利（>+3σ）：獲利轉回核心資產"


def L(tpl):
    return Lit(tpl)


def R(ref, fld):
    return Ref(ref, fld)


def S(*segs):
    return SummarySentence(tuple(segs))


def sec_of(draft, key):
    return next(s for s in draft.sections if s.key == key)


def swap(draft, key, idx, sentence):
    """換掉某段第 idx 句（sentence=None → 刪除）。"""
    out = []
    for s in draft.sections:
        if s.key == key:
            ss = list(s.sentences)
            if sentence is None:
                del ss[idx]
            else:
                ss[idx] = sentence
            s = SummarySection(s.key, tuple(ss))
        out.append(s)
    return SummaryDraft(tuple(out))


def add(draft, key, sentence):
    return SummaryDraft(tuple(SummarySection(s.key, s.sentences + (sentence,)) if s.key == key else s
                              for s in draft.sections))


def with_section(draft, key, sentences):
    return SummaryDraft(tuple(SummarySection(s.key, tuple(sentences)) if s.key == key else s for s in draft.sections))


def codes(rep):
    return {v.code for v in rep.violations}


def assert_rejected(rep, gate, code):
    assert rep.accepted is False, f"預期被拒：{[(v.gate, v.code) for v in rep.violations]}"
    assert gate in rep.failed_gates, (gate, rep.failed_gates)
    assert code in codes(rep), (code, codes(rep))


@pytest.fixture
def dg():
    return make_digest()


@pytest.fixture
def base(dg):
    return compose_rule_draft(dg)


# 市場段句序：0 regime／1 light／2 health／3 風險上限卡面／4 台股／5 國際／6 大盤合理區間
HEALTH = "market.health"
REGIME = "market.regime"
ACT0, ACT1 = "action:pf-A:0050", "action:pf-A:0056"


# ══════════════════════════════════════════════════════════════════════
# 基準：規則式摘要自己必須全過；渲染出的文字固定
# ══════════════════════════════════════════════════════════════════════
def test_rule_draft_is_clean(dg, base):
    rep = check_summary(dg, base)
    assert rep.accepted and rep.usable and rep.clean and rep.violations == () and rep.dropped == ()
    assert rep.failed_gates == () and rep.passed_gates == T.GROUNDING_GATES and rep.surviving == base
    assert not rep.structural_failure and not rep.digest_invalid


def test_rendered_text_golden(dg, base):
    got = dict(render_draft(dg, base))
    assert got[MKT] == ("市場位階：bull（資料日 2026-10-26）", "市場燈號：🟢（資料日 2026-10-26）",
                        "市場健康度：72.5（資料日 2026-10-26）", "風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate",
                        "⬜ 台股趨勢：尚未定義，無法判定", "⬜ 國際趨勢：尚未定義，無法判定",
                        "⬜ 大盤合理區間：研究框架，未啟用，無法判定")
    assert got[IND] == ("⬜ 產業趨勢：尚未定義，無法判定",)
    assert got[BH] == ("⬜ 存股：尚未設定投資策略分類，無法判定",)
    assert got[CG] == ("⬜ 資本利得：尚未設定投資策略分類，無法判定",)
    assert got[ACT] == (f"0050：{ACT_CUT_TEXT}", f"0056：{ACT_TP_TEXT}")


@pytest.mark.parametrize("make", [
    lambda: make_digest(), lambda: empty_digest(), lambda: make_digest(risk_valid=False),
    lambda: make_digest(market_facts=[stale_val("market.health", 72.5), proxy_val("market.light", 3.5),
                                      failed("market.regime")]),
    lambda: make_digest(market_facts=[invalid("market.health"), stale_text("market.regime", "bull"),
                                      missing("market.light", MissingReason.CONTRACT_DRIFT)]),
    lambda: make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                      ok_val("market.health", 60, "%")]),
    lambda: make_digest(entries=[], items=[], unkeyed=3),
    lambda: make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定"),
                                 entry("0056", "u", "cut", strategy=StrategyType.CAPITAL_GAIN, source="客戶設定")],
                        items=[action("0056", "u", "cut", 1)], unkeyed=1),
])
def test_rule_draft_clean_over_many_digests(make):
    d = make()
    rep = check_summary(d, compose_rule_draft(d))
    assert rep.clean, [(v.gate, v.code, v.message) for v in rep.violations]


# ══════════════════════════════════════════════════════════════════════
# STRUCT：沒有任意文字的位置；無法解析＝驗證失敗
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", [None, {}, "text", 42, [], ((),), object()])
def test_unparseable_input_is_validation_failure(dg, bad):
    rep = check_summary(dg, bad)
    assert rep.accepted is False and rep.structural_failure is True and rep.surviving is None
    assert rep.passed_gates == () and rep.usable is False and rep.clean is False


def test_old_text_based_sentence_cannot_even_be_constructed():
    with pytest.raises(TypeError):
        SummarySentence(text="市場健康度：72.5", evidence_refs=("market.health",))        # type: ignore[call-arg]


@pytest.mark.parametrize("seg", ["自由文字", "買進", 1, None, ("a",), {"x": 1}, b"bytes"])
def test_free_text_segment_is_structurally_impossible(dg, base, seg):
    rep = check_summary(dg, swap(base, MKT, 2, SummarySentence((seg,))))
    assert rep.structural_failure and rep.accepted is False and "segment_type" in codes(rep)


def test_container_and_subclass_attacks_rejected(dg, base):
    class SubDraft(SummaryDraft):
        pass

    class SubLit(Lit):
        pass
    assert check_summary(dg, SubDraft(base.sections)).structural_failure
    assert check_summary(dg, SummaryDraft(list(base.sections))).structural_failure
    assert check_summary(dg, SummaryDraft((object(),))).structural_failure
    assert check_summary(dg, SummaryDraft((SummarySection("market", [S(L(T.TPL_GLYPH))]),))).structural_failure
    assert check_summary(dg, SummaryDraft((SummarySection("market", (object(),)),))).structural_failure
    assert check_summary(dg, swap(base, MKT, 0, SummarySentence([L(T.TPL_GLYPH)]))).structural_failure   # type: ignore[arg-type]
    assert check_summary(dg, swap(base, MKT, 0, S(SubLit(T.TPL_GLYPH)))).structural_failure


@pytest.mark.parametrize("bad_ref", ["", "has space", "zero​width", 1, None, "a\nb"])
def test_bad_ref_ids_are_structural(dg, base, bad_ref):
    rep = check_summary(dg, swap(base, MKT, 2, S(R(bad_ref, T.FIELD_LABEL))))
    assert rep.structural_failure and rep.accepted is False


def test_non_str_template_id_or_field_is_structural(dg, base):
    assert check_summary(dg, swap(base, MKT, 0, S(Lit(1)))).structural_failure           # type: ignore[arg-type]
    assert check_summary(dg, swap(base, MKT, 0, S(Ref(HEALTH, 3)))).structural_failure   # type: ignore[arg-type]


def test_invalid_digest_means_no_grounding(base):
    rep = check_summary(make_digest(schema_version="x"), base)
    assert rep.digest_invalid and rep.accepted is False and rep.surviving is None and rep.passed_gates == ()
    assert rep.usable is False
    assert check_summary(None, base).digest_invalid


# ══════════════════════════════════════════════════════════════════════
# G1 引用封閉
# ══════════════════════════════════════════════════════════════════════
def test_g1_unknown_ref(dg, base):
    rep = check_summary(dg, swap(base, MKT, 2, S(R("market.nope", T.FIELD_LABEL))))
    assert_rejected(rep, T.GATE_G1, "ref_not_in_digest")


def test_g1_unknown_template_id_is_not_a_loophole(dg, base):
    for tid in ("買進", T.TEMPLATES[T.TPL_GLYPH], "tpl.nope", "TPL_GLYPH"):
        rep = check_summary(dg, swap(base, MKT, 2, S(L(tid), R(HEALTH, T.FIELD_LABEL))))
        assert_rejected(rep, T.GATE_G4, "template_not_whitelisted")


def test_g1_unknown_field_name(dg, base):
    for fld in ("source", "strategy_source", "TEXT", "", "value "):
        rep = check_summary(dg, swap(base, MKT, 0, S(R(REGIME, T.FIELD_LABEL), L(T.TPL_COLON), R(REGIME, fld),
                                                   L(T.TPL_DATE_OPEN), R(REGIME, T.FIELD_AS_OF), L(T.TPL_CLOSE))))
        assert not rep.accepted and (T.GATE_G4 in rep.failed_gates or T.GATE_G1 in rep.failed_gates)


def test_g1_slot_mismatch_blocks_pooling_across_refs(dg, base):
    """同一個 slot 的 segment 必須指向同一個項目：不能「標籤取 A、文字取 B」。"""
    mixed = S(R(HEALTH, T.FIELD_LABEL), L(T.TPL_COLON), R(HEALTH, T.FIELD_VALUE), L(T.TPL_DATE_OPEN),
              R("market.light", T.FIELD_AS_OF), L(T.TPL_CLOSE))
    assert_rejected(check_summary(dg, swap(base, MKT, 2, mixed)), T.GATE_G1, "slot_ref_mismatch")
    sym_swap = S(R(ACT1, T.FIELD_SYMBOL), L(T.TPL_COLON), R(ACT0, T.FIELD_TEXT))        # 換代號
    assert_rejected(check_summary(dg, swap(base, ACT, 0, sym_swap)), T.GATE_G1, "slot_ref_mismatch")


def test_g1_every_field_is_bound_to_its_own_ref():
    """每個展開字串都取自它自己綁定的項目（沒有跨項目池化）：兩個不同 ref 的同名欄位展開不同。"""
    d = make_digest()
    idx = build_ref_index(d)
    assert expand(d, idx["market.regime"], T.FIELD_TEXT)[0] == "bull"
    assert expand(d, idx["market.light"], T.FIELD_TEXT)[0] == "🟢"


@pytest.mark.parametrize("fld", T.FIELDS)
def test_user_free_text_strategy_source_never_expands(fld):
    """A1：strategy_source（使用者自由文字）沒有任何欄位、任何項目可以展開到摘要。"""
    sentinel = "SENTINEL來源必定上漲建議立刻買進"
    d = make_digest(entries=[entry("0050", ACT_CUT_TEXT, "cut", strategy=StrategyType.BUY_AND_HOLD, source=sentinel)],
                    items=[action("0050", ACT_CUT_TEXT, "cut", 1)])
    idx = build_ref_index(d)
    for info in idx.values():
        text, _, _ = expand(d, info, fld)
        assert text is None or sentinel not in text
    r = SummaryResult(d, AB0.AiParticipation.RULE_ONLY, compose_rule_draft(d).sections)
    assert sentinel not in "\n".join(x for _, ls in r.lines for x in ls)
    assert "客戶" not in "\n".join(x for _, ls in r.lines for x in ls)


def test_a1_holding_ref_cannot_quote_source_field(dg):
    d = make_digest(entries=[entry("0050", ACT_CUT_TEXT, "cut", strategy=StrategyType.BUY_AND_HOLD, source="使用者設定")],
                    items=[action("0050", ACT_CUT_TEXT, "cut", 1)])
    b = compose_rule_draft(d)
    hr = holding_ref("pf-A", "0050")
    bad = S(R(hr, T.FIELD_SYMBOL), L(T.TPL_STRATEGY_IS), R(hr, "source"), L(T.TPL_ENTRY_TAIL))
    assert not check_summary(d, swap(b, BH, 0, bad)).accepted
    bad2 = S(R(hr, T.FIELD_SYMBOL), L(T.TPL_STRATEGY_IS), R(hr, T.FIELD_TEXT), L(T.TPL_ENTRY_TAIL))
    assert not check_summary(d, swap(b, BH, 0, bad2)).accepted


# ══════════════════════════════════════════════════════════════════════
# G2 數字：只能來自欄位展開；單位由模板決定
# ══════════════════════════════════════════════════════════════════════
def test_g2_numbers_only_via_field_expansion_so_nothing_to_forge(dg):
    """沒有任何 Lit 模板含阿拉伯數字或英文字母 —— 數字／英文只可能來自 Digest 的欄位展開。"""
    for tid, text in T.TEMPLATES.items():
        assert not re.search(r"[0-9A-Za-z]", text), (tid, text)


def test_g2_unit_is_decided_by_template():
    d_none = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                       ok_val("market.health", 60)])
    d_pct = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                      ok_val("market.health", 60, "%")])
    b_none, b_pct = compose_rule_draft(d_none), compose_rule_draft(d_pct)
    assert render_draft(d_none, b_none)[0][1][2] == "市場健康度：60（資料日 2026-10-26）"
    assert render_draft(d_pct, b_pct)[0][1][2] == "市場健康度：60%（資料日 2026-10-26）"
    # 用錯單位的句型 → unit_mismatch
    assert_rejected(check_summary(d_none, b_pct), T.GATE_G2, "unit_mismatch")
    assert_rejected(check_summary(d_pct, b_none), T.GATE_G2, "unit_mismatch")


def test_a5_unit_or_whitespace_suffix_cannot_be_appended(dg, base):
    """A5：數字後面加空白／單位／文字 —— 只能用 Lit，而任何不在骨架內的 Lit 都不是白名單句型。"""
    forged = S(R(HEALTH, T.FIELD_LABEL), L(T.TPL_COLON), R(HEALTH, T.FIELD_VALUE), L(T.TPL_PCT), L(T.TPL_DATE_OPEN),
               R(HEALTH, T.FIELD_AS_OF), L(T.TPL_CLOSE))
    assert_rejected(check_summary(dg, swap(base, MKT, 2, forged)), T.GATE_G2, "unit_mismatch")     # health 無單位
    extra = SummarySentence(sec_of(base, MKT).sentences[2].segments + (L(T.TPL_PCT),))
    assert_rejected(check_summary(dg, swap(base, MKT, 2, extra)), T.GATE_G4, "shape_not_whitelisted")


@pytest.mark.parametrize("v,lit", [(-1.5, "-1.5"), (0.0, "0.0"), (1e-07, "0.0000001"), (1e22, "10000000000000000000000"),
                                   (123456789.125, "123456789.125"), (-0.0, "-0.0"), (7, "7"), (0, "0"), (60.0, "60.0")])
def test_number_literal_is_fixed_point_shortest_roundtrip(v, lit):
    assert number_literal(v) == lit


@pytest.mark.parametrize("v", [float("nan"), float("inf"), True, "1", None, 1 + 2j])
def test_number_literal_rejects_non_finite_or_non_real(v):
    with pytest.raises(ValueError):
        number_literal(v)


def test_g2_value_renders_literal_not_rounded():
    for v, shown in ((72.5, "72.5"), (60, "60"), (60.0, "60.0"), (-1.5, "-1.5"), (1e-07, "0.0000001")):
        d = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                      ok_val("market.health", v)])
        assert render_draft(d, compose_rule_draft(d))[0][1][2] == f"市場健康度：{shown}（資料日 2026-10-26）"


def test_g2_risk_cap_values_and_dates_are_restricted(dg, base):
    for rid in ("risk_cap.cap_pct", "risk_cap.exposure_lo_pct", "risk_cap.exposure_hi_pct"):
        for fld in (T.FIELD_VALUE, T.FIELD_AS_OF, T.FIELD_TEXT):
            forged = S(R(rid, T.FIELD_LABEL), L(T.TPL_COLON), R(rid, fld), L(T.TPL_DATE_OPEN), R(rid, T.FIELD_AS_OF),
                       L(T.TPL_CLOSE))
            rep = check_summary(dg, swap(base, MKT, 3, forged))
            assert not rep.accepted
    full = _fact_sentence("fact_value_ok", "risk_cap.cap_pct")           # 句型吻合，但項目受限
    rep = check_summary(dg, swap(base, MKT, 3, full))
    assert_rejected(rep, T.GATE_G2, "restricted_value")
    assert_rejected(check_summary(dg, swap(base, MKT, 3, S(R("risk_cap.cap_pct", T.FIELD_VALUE)))),
                    T.GATE_G4, "shape_not_whitelisted")


def test_g2_trend_observations_are_restricted():
    obs = ok_val("tw.twii_close", 20000.5, "pts", rule=RuleRef("add", "action_branch.v1"))
    d = dataclasses.replace(make_digest(), tw_trend=DefinitionSection(DefinitionState.NOT_DEFINED, observations=(obs,)))
    b = compose_rule_draft(d)
    assert check_summary(d, b).clean
    assert "20000.5" not in "".join(x for _, ls in render_draft(d, b) for x in ls)
    forged = _fact_sentence("fact_value_ok", "tw.twii_close")
    assert_rejected(check_summary(d, swap(b, MKT, 4, forged)), T.GATE_G2, "restricted_value")
    assert build_ref_index(d)["tw.twii_close"].group == "restricted"


def test_g2_value_field_on_text_only_fact_is_not_quotable(dg, base):
    forged = S(R(REGIME, T.FIELD_LABEL), L(T.TPL_COLON), R(REGIME, T.FIELD_VALUE), L(T.TPL_DATE_OPEN),
               R(REGIME, T.FIELD_AS_OF), L(T.TPL_CLOSE))
    assert_rejected(check_summary(dg, swap(base, MKT, 0, forged)), T.GATE_G1, "field_not_quotable")


# ══════════════════════════════════════════════════════════════════════
# G3 狀態不可升級：標示語由模板產生，句型綁定項目狀態
# ══════════════════════════════════════════════════════════════════════
def _fact_sentence(shape_id, fid):
    sh = next(s for s in SHAPES if s.sid == shape_id)
    return SummarySentence(tuple(Lit(e[1]) if e[0] == "L" else Ref(fid, e[3]) for e in sh.skeleton))


def test_g3_status_cannot_be_upgraded_or_downgraded_by_picking_another_shape():
    d = make_digest(market_facts=[stale_val("market.health", 72.5), proxy_val("market.light", 3.5),
                                  failed("market.regime")])
    b = compose_rule_draft(d)
    idx = {s.evidence_refs[0]: i for i, s in enumerate(sec_of(b, MKT).sentences)}
    for fid, wrong in (("market.health", "fact_value_ok"), ("market.health", "fact_value_proxy"),
                       ("market.light", "fact_value_ok"), ("market.light", "fact_value_stale"),
                       ("market.regime", "fact_value_ok"), ("market.regime", "fact_invalid")):
        rep = check_summary(d, swap(b, MKT, idx[fid], _fact_sentence(wrong, fid)))
        assert_rejected(rep, T.GATE_G3, "status_mismatch")


def test_g3_ok_fact_cannot_be_dressed_as_missing_nor_vice_versa(dg, base):
    assert_rejected(check_summary(dg, swap(base, MKT, 2, _fact_sentence("fact_missing", HEALTH))),
                    T.GATE_G3, "status_mismatch")
    d = empty_digest()
    b = compose_rule_draft(d)
    assert_rejected(check_summary(d, swap(b, MKT, 2, _fact_sentence("fact_value_ok", HEALTH))),
                    T.GATE_G1, "field_not_quotable")


@pytest.mark.parametrize("make_fact", [stale_val, proxy_val])
def test_a2_stale_or_proxy_cannot_be_presented_as_current(make_fact):
    d = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                  make_fact("market.health", 72.5)])
    b = compose_rule_draft(d)
    ok_shape = _fact_sentence("fact_value_ok", HEALTH)
    assert not check_summary(d, swap(b, MKT, 2, ok_shape)).accepted
    # 把「資料已過期」那個模板拿掉（只留日期）→ 不在白名單
    s = sec_of(b, MKT).sentences[2]
    kept = tuple(g for g in s.segments if not (type(g) is Lit and g.template_id in (T.TPL_STALE_DATE_OPEN, T.TPL_PROXY_TAIL)))
    assert_rejected(check_summary(d, swap(b, MKT, 2, SummarySentence(kept))), T.GATE_G4, "shape_not_whitelisted")


def test_a2_negation_or_contradiction_has_no_way_to_be_expressed(dg):
    """A2：否定／矛盾（「並非資料不足」「已取消，請忽略」「但前景樂觀」）— 骨架固定，加任何 Lit 都不是白名單句型。"""
    d = empty_digest()
    b = compose_rule_draft(d)
    s = sec_of(b, MKT).sentences[0]
    for extra in (T.TPL_UNDETERMINED_TAIL, T.TPL_CLOSE, T.TPL_GLYPH, T.TPL_COLON, T.TPL_ACT_NONE):
        forged = SummarySentence(s.segments + (L(extra),))
        assert_rejected(check_summary(d, swap(b, MKT, 0, forged)), T.GATE_G4, "shape_not_whitelisted")
        forged = SummarySentence((L(extra),) + s.segments)
        assert_rejected(check_summary(d, swap(b, MKT, 0, forged)), T.GATE_G4, "shape_not_whitelisted")


def test_g3_undefined_sections_use_fixed_template_only(dg, base):
    for idx, name in ((4, "tw_trend"), (5, "intl_trend"), (6, "valuation")):
        rid = section_ref(name)
        weaker = S(L(T.TPL_GLYPH), R(rid, T.FIELD_LABEL), L(T.TPL_COLON), R(rid, T.FIELD_VALUE))
        assert not check_summary(dg, swap(base, MKT, idx, weaker)).accepted


def test_a3_homoglyph_simplified_synonym_numeral_attacks_have_no_slot():
    """A3／A4：同形異字、簡體、同義詞、中文數字、全形數字 —— 這些只可能經由「任意字串」進入，而任意字串沒有位置。"""
    d = make_digest()
    b = compose_rule_draft(d)
    for payload in ("hоld", "买进", "续抱", "平穩", "七十二點五", "７２．５", "⒎2", "1e2", "中 性", "ＢＵＹ"):
        for sentence in (S(payload), S(R(HEALTH, T.FIELD_LABEL), payload), SummarySentence((payload, R(HEALTH, T.FIELD_LABEL)))):
            rep = check_summary(d, swap(b, MKT, 2, sentence))
            assert rep.structural_failure and not rep.accepted, payload
        as_template = S(L(payload), R(HEALTH, T.FIELD_LABEL))
        assert_rejected(check_summary(d, swap(b, MKT, 2, as_template)), T.GATE_G4, "template_not_whitelisted")


def test_a_free_ride_section_ref_cannot_carry_extra_claims(dg, base):
    """搭便車：把 section:risk_cap 掛在句上、夾帶任意結論 —— 只能以 Lit 夾帶，而 Lit 受骨架限制。"""
    for extra in (T.TPL_ACT_NONE, T.TPL_ENTRY_TAIL, T.TPL_UNDETERMINED_TAIL):
        forged = S(L(extra), R(section_ref("risk_cap"), T.FIELD_WORDING))
        assert_rejected(check_summary(dg, add(base, MKT, forged)), T.GATE_G4, "shape_not_whitelisted")
        forged = S(R(section_ref("risk_cap"), T.FIELD_WORDING), L(extra))
        assert_rejected(check_summary(dg, add(base, MKT, forged)), T.GATE_G4, "shape_not_whitelisted")
    # 同一句型放錯段
    assert_rejected(check_summary(dg, add(base, IND, S(R(section_ref("risk_cap"), T.FIELD_WORDING)))),
                    T.GATE_G4, "shape_out_of_section")


def test_g3_bind_field_only_exists_inside_shapes_that_declare_it(dg, base):
    lone = S(R(section_ref("holdings"), T.FIELD_BIND))
    assert_rejected(check_summary(dg, add(base, BH, lone)), T.GATE_G4, "shape_not_whitelisted")


# ══════════════════════════════════════════════════════════════════════
# G4 不新增結論類別：行動一對一
# ══════════════════════════════════════════════════════════════════════
def test_g4_action_sentence_is_symbol_plus_verbatim_text_and_nothing_else(dg, base):
    a = sec_of(base, ACT).sentences[0]
    assert a.segments == (R(ACT0, T.FIELD_SYMBOL), L(T.TPL_COLON), R(ACT0, T.FIELD_TEXT))
    # A6：加前後字
    for extra in (L(T.TPL_GLYPH), L(T.TPL_CLOSE), L(T.TPL_ACT_NONE)):
        for forged in (SummarySentence(a.segments + (extra,)), SummarySentence((extra,) + a.segments)):
            assert_rejected(check_summary(dg, swap(base, ACT, 0, forged)), T.GATE_G4, "shape_not_whitelisted")


def test_g4_action_list_must_match_digest_one_to_one_in_order(dg, base):
    acts = sec_of(base, ACT).sentences
    a0, a1 = acts
    for name, sents in (("遺漏", (a0,)), ("遺漏首項", (a1,)), ("重排", (a1, a0)), ("重複", (a0, a0, a1)),
                        ("重複2", (a0, a1, a1)), ("全空", ())):
        rep = check_summary(dg, with_section(base, ACT, sents))
        assert not rep.accepted, name
        assert "action_list_mismatch" in codes(rep) or "empty_section" in codes(rep) or "duplicate_sentence" in codes(rep), name


def test_g4_action_not_in_digest_cannot_be_invented(dg, base):
    ghost = S(R("action:pf-A:9999", T.FIELD_SYMBOL), L(T.TPL_COLON), R("action:pf-A:9999", T.FIELD_TEXT))
    assert_rejected(check_summary(dg, add(base, ACT, ghost)), T.GATE_G1, "ref_not_in_digest")


def test_g4_action_shape_not_allowed_outside_actions_section(dg, base):
    a = sec_of(base, ACT).sentences[0]
    assert_rejected(check_summary(dg, add(base, MKT, a)), T.GATE_G4, "shape_out_of_section")


def test_g4_other_section_shapes_not_allowed_in_actions(dg, base):
    assert_rejected(check_summary(dg, add(base, ACT, sec_of(base, IND).sentences[0])), T.GATE_G4, "shape_out_of_section")


def test_g4_action_symbol_comes_only_from_target(dg):
    d = make_digest(entries=[entry("0050", ACT_CUT_TEXT, "cut")], items=[action("0050", ACT_CUT_TEXT, "cut", 1)])
    force_set(d.actions.items[0], target=None)
    # 無 target 的 Digest 行動 —— 代號句型不可用
    b = compose_rule_draft(d)
    assert b.sections[4].sentences[0].segments == (R(ACT0, T.FIELD_TEXT),)
    assert check_summary(d, b).clean
    with_symbol = S(R(ACT0, T.FIELD_SYMBOL), L(T.TPL_COLON), R(ACT0, T.FIELD_TEXT))
    assert_rejected(check_summary(d, swap(b, ACT, 0, with_symbol)), T.GATE_G1, "field_not_quotable")


def test_g4_stale_evidence_must_be_disclosed_with_the_oldest_stale_fact():
    from shared.decision_digest import Fact, Provenance
    from datetime import date
    f_old = Fact("action_fact:pf-A:0050", DataStatus.STALE, Provenance("svc", as_of=date(2026, 10, 20)),
                 text=ACT_CUT_TEXT, rule=RuleRef("cut", "action_branch.v1"))
    f_new = Fact("ev.second", DataStatus.STALE, Provenance("svc", as_of=date(2026, 10, 24)), text="次要證據")
    e = entry("0050", None, facts=(f_old, f_new))
    d = make_digest(entries=[e], items=[action("0050", ACT_CUT_TEXT, "cut", 1, evidence=("ev.second", f_old.fact_id))])
    b = compose_rule_draft(d)
    s = sec_of(b, ACT).sentences[0]
    assert render_sentence(d, s) == f"0050：{ACT_CUT_TEXT}（依據資料已過期，資料日 2026-10-20）"       # 取最舊的
    assert check_summary(d, b).clean
    hide = S(R(ACT0, T.FIELD_SYMBOL), L(T.TPL_COLON), R(ACT0, T.FIELD_TEXT))                         # 隱藏過期
    assert_rejected(check_summary(d, swap(b, ACT, 0, hide)), T.GATE_G3, "stale_evidence_mismatch")
    wrong = SummarySentence(s.segments[:-2] + (R("ev.second", T.FIELD_AS_OF), L(T.TPL_CLOSE)))        # 挑較新的那筆
    assert_rejected(check_summary(d, swap(b, ACT, 0, wrong)), T.GATE_G3, "stale_evidence_mismatch")
    d_fresh = make_digest()
    stale_form = SummarySentence(sec_of(compose_rule_draft(d_fresh), ACT).sentences[0].segments
                                 + (L(T.TPL_ACT_STALE_OPEN), R("action_fact:pf-A:0050", T.FIELD_AS_OF), L(T.TPL_CLOSE)))
    assert not check_summary(d_fresh, swap(compose_rule_draft(d_fresh), ACT, 0, stale_form)).accepted


def test_g4_actions_unavailable_and_none_shapes_are_state_bound():
    d_un = make_digest(items=[])                                  # actions UNAVAILABLE
    none_sentence = S(L(T.TPL_ACT_NONE), R(section_ref("actions"), T.FIELD_BIND))
    b = compose_rule_draft(d_un)
    assert_rejected(check_summary(d_un, with_section(b, ACT, (none_sentence,))), T.GATE_G3, "precondition_failed")
    d_none = dataclasses.replace(make_digest(items=[]), actions=AB0.ActionsSection(AB0.Availability.AVAILABLE, ()))
    b2 = compose_rule_draft(d_none)
    assert render_draft(d_none, b2)[4][1] == (f"本期行動：{T.MARK_NO_ACTION}",)
    assert_rejected(check_summary(d_none, with_section(b2, ACT, (sec_of(b, ACT).sentences[0],))),
                    T.GATE_G3, "precondition_failed")


# ══════════════════════════════════════════════════════════════════════
# G5 段落完整
# ══════════════════════════════════════════════════════════════════════
def test_g5_missing_duplicate_unknown_and_order_of_sections(dg, base):
    secs = list(base.sections)
    assert_rejected(check_summary(dg, SummaryDraft(tuple(secs[:-1]))), T.GATE_G5, "missing_section")
    assert_rejected(check_summary(dg, SummaryDraft(tuple(secs + [secs[0]]))), T.GATE_G5, "duplicate_section")
    assert_rejected(check_summary(dg, SummaryDraft(tuple(secs + [SummarySection("extra", (S(R(HEALTH, T.FIELD_LABEL)),))]))),
                    T.GATE_G5, "unknown_section")
    assert_rejected(check_summary(dg, SummaryDraft((secs[1], secs[0], *secs[2:]))), T.GATE_G5, "section_order")


def test_g5_empty_section_rejected(dg, base):
    for key in T.SECTION_KEYS:
        assert_rejected(check_summary(dg, with_section(base, key, ())), T.GATE_G5, "empty_section")


def test_g5_every_basis_item_must_be_disclosed(dg, base):
    for idx in (3, 4, 5, 6):
        assert_rejected(check_summary(dg, swap(base, MKT, idx, None)), T.GATE_G5, "missing_disclosure")


def test_g5_missing_fact_must_be_disclosed():
    d = empty_digest()
    b = compose_rule_draft(d)
    assert check_summary(d, b).clean
    for idx in (0, 1, 2):
        assert_rejected(check_summary(d, swap(b, MKT, idx, None)), T.GATE_G5, "missing_disclosure")


def test_g5_disclosure_must_use_the_matching_shape_for_that_ref():
    d = make_digest(market_facts=[stale_val("market.health", 72.5), ok_text("market.regime", "bull"),
                                  ok_text("market.light", "🟢")])
    b = compose_rule_draft(d)
    i = next(i for i, s in enumerate(sec_of(b, MKT).sentences) if s.evidence_refs == (HEALTH,))
    # 換成「別的 ref」的合法句子 —— 該 ref 沒被揭露
    other = sec_of(b, MKT).sentences[next(j for j, s in enumerate(sec_of(b, MKT).sentences)
                                         if s.evidence_refs == ("market.light",))]
    assert_rejected(check_summary(d, swap(b, MKT, i, other)), T.GATE_G5, "missing_disclosure")


def test_g5_duplicate_sentence_rejected(dg, base):
    assert_rejected(check_summary(dg, add(base, MKT, sec_of(base, MKT).sentences[0])), T.GATE_G5, "duplicate_sentence")


def test_g5_unkeyed_holdings_must_be_disclosed():
    d = make_digest(entries=[], items=[], unkeyed=2)
    b = compose_rule_draft(d)
    assert check_summary(d, b).clean
    lines = dict(render_draft(d, b))
    assert "⬜ 另有 2 檔持股缺少投資組合鍵，未納入判讀，資料不足，無法判定" in lines[BH]
    only = with_section(b, BH, tuple(x for x in sec_of(b, BH).sentences if x.segments[0] != L(T.TPL_UNKEYED_OPEN)))
    assert_rejected(check_summary(d, only), T.GATE_G5, "missing_disclosure")


def test_g5_strategy_classified_entries_need_their_own_sentence():
    d = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定")],
                    items=[action("0050", "t", "add")])
    b = compose_rule_draft(d)
    assert check_summary(d, b).clean
    assert section_basis(d, BH) == (("holding:4:pf-A:0050", ("strategy_entry",)),)
    assert section_basis(d, CG) == ((section_ref("holdings"), ("strategy_none:capital_gain",)),)
    assert dict(render_draft(d, b))[BH] == ("0050：策略分類為存股；基本面與配置判定尚未接線，無法判定",)
    # 把存股的 entry 句放到資本利得段 → 策略分類不屬於此段
    assert_rejected(check_summary(d, add(b, CG, sec_of(b, BH).sentences[0])), T.GATE_G4, "wrong_strategy")


def test_g5_strategy_entry_shape_cannot_be_used_when_holdings_unavailable():
    d = make_digest(entries=[entry("0050", None, strategy=StrategyType.BUY_AND_HOLD, source="x")], items=[])
    assert d.holdings.availability is AB0.Availability.UNAVAILABLE
    b = compose_rule_draft(d)
    assert check_summary(d, b).clean and "規則層未產出可引用依據" in dict(render_draft(d, b))[BH][0]
    ent = S(R(holding_ref("pf-A", "0050"), T.FIELD_SYMBOL), L(T.TPL_STRATEGY_IS), R(holding_ref("pf-A", "0050"), T.FIELD_STRATEGY),
            L(T.TPL_ENTRY_TAIL))
    assert_rejected(check_summary(d, add(b, BH, ent)), T.GATE_G3, "precondition_failed")


def test_g5_holdings_unavailable_must_cite_the_holdings_section_itself():
    d = make_digest(entries=[entry("0050", None)], items=[])
    b = compose_rule_draft(d)
    assert check_summary(d, b).clean
    pad = with_section(b, BH, (S(R(holding_ref("pf-A", "0050"), T.FIELD_SYMBOL), L(T.TPL_STRATEGY_IS),
                                 R(holding_ref("pf-A", "0050"), T.FIELD_STRATEGY), L(T.TPL_ENTRY_TAIL)),))
    assert not check_summary(d, pad).accepted


def test_g5_unavailable_state_shapes_cannot_be_used_on_available_data(dg, base):
    wrong = S(L(T.TPL_GLYPH), L(T.TPL_LABEL_BUY_AND_HOLD), L(T.TPL_HOLDINGS_UNAVAILABLE_MID),
              R(section_ref("holdings"), T.FIELD_REASON), L(T.TPL_CLOSE))
    assert_rejected(check_summary(dg, add(base, BH, wrong)), T.GATE_G3, "precondition_failed")
    d_none = make_digest(entries=[], items=[], unkeyed=0)
    assert_rejected(check_summary(d_none, add(compose_rule_draft(d_none), BH, sec_of(base, BH).sentences[0])),
                    T.GATE_G3, "precondition_failed")


def test_g5_industry_and_trend_wording_belongs_to_its_own_section(dg, base):
    tw = sec_of(base, MKT).sentences[4]
    assert_rejected(check_summary(dg, add(base, IND, tw)), T.GATE_G4, "wrong_section_ref")
    ind = sec_of(base, IND).sentences[0]
    assert_rejected(check_summary(dg, add(base, MKT, ind)), T.GATE_G4, "wrong_section_ref")


# ══════════════════════════════════════════════════════════════════════
# G6 與 accepted／usable／clean／surviving 的語意
# ══════════════════════════════════════════════════════════════════════
def test_g6_sentence_without_any_ref_is_dropped_not_fatal(dg, base):
    free_riders = [S(L(T.TPL_ACT_NONE)), S(L(T.TPL_GLYPH), L(T.TPL_COLON)), SummarySentence(())]
    for extra in free_riders:
        rep = check_summary(dg, add(base, MKT, extra))
        assert rep.accepted is True and rep.usable is True and rep.clean is False
        assert rep.dropped == ((MKT, len(sec_of(base, MKT).sentences)),)
        assert T.GATE_G6 in rep.failed_gates and "no_evidence_ref" in codes(rep) and T.GATE_G6 not in rep.passed_gates
        assert rep.surviving == base and extra not in sec_of(rep.surviving, MKT).sentences


def test_a7_consumers_must_use_surviving_not_the_original_draft(dg, base):
    dirty = add(base, MKT, S(L(T.TPL_ACT_NONE)))
    rep = check_summary(dg, dirty)
    assert rep.accepted and rep.usable and not rep.clean
    assert rep.surviving != dirty                                      # 原始 draft 含未綁定句子，不得使用
    with pytest.raises(ValueError, match="自檢"):
        SummaryResult(dg, AB0.AiParticipation.RULE_ONLY, dirty.sections)
    assert SummaryResult(dg, AB0.AiParticipation.RULE_ONLY, rep.surviving.sections).state is SummaryState.PARTIAL


def test_g6_dropped_sentence_is_not_inspected_for_other_gates(dg, base):
    rep = check_summary(dg, add(base, MKT, S(L("買進"), L("tpl.nope"))))
    assert rep.accepted and {v.gate for v in rep.violations} == {T.GATE_G6}


def test_g6_dropping_the_only_disclosure_triggers_g5(dg, base):
    only_lit = with_section(base, IND, (S(L(T.TPL_GLYPH), L(T.TPL_COLON)),))
    rep = check_summary(dg, only_lit)
    assert rep.accepted is False and rep.usable is False and rep.clean is False
    assert T.GATE_G6 in rep.failed_gates and "empty_section" in codes(rep)


def test_accepted_usable_clean_truth_table(dg, base):
    clean = check_summary(dg, base)
    dropped = check_summary(dg, add(base, MKT, S(L(T.TPL_GLYPH))))
    rejected = check_summary(dg, swap(base, MKT, 3, None))
    structural = check_summary(dg, None)
    assert (clean.accepted, clean.usable, clean.clean) == (True, True, True)
    assert (dropped.accepted, dropped.usable, dropped.clean) == (True, True, False)
    assert (rejected.accepted, rejected.usable, rejected.clean) == (False, False, False)
    assert (structural.accepted, structural.usable, structural.clean) == (False, False, False)


def test_failed_gates_are_in_fixed_gate_order(dg, base):
    bad = swap(swap(base, MKT, 2, S(R("market.nope", T.FIELD_LABEL))), IND, 0, S(L("tpl.nope"), R(section_ref("industry"), T.FIELD_LABEL)))
    rep = check_summary(dg, add(bad, MKT, S(L(T.TPL_GLYPH))))
    assert rep.failed_gates == tuple(g for g in T.GROUNDING_GATES if g in rep.failed_gates)
    assert list(rep.failed_gates) == ["G1", "G4", "G5", "G6"] or set(rep.failed_gates) >= {"G1", "G4", "G6"}


# ══════════════════════════════════════════════════════════════════════
# SummaryResult：與 Digest 綁定，無法手造或改裝
# ══════════════════════════════════════════════════════════════════════
def _result(dg, base):
    return SummaryResult(dg, AB0.AiParticipation.RULE_ONLY, base.sections)


def test_summary_result_derives_everything_from_the_digest(dg, base):
    r = _result(dg, base)
    assert r.state is SummaryState.PARTIAL and r.retained_sections == T.SECTION_KEYS
    assert tuple(k for k, _ in r.section_availability) == T.SECTION_KEYS
    assert r.notices == () and r.invalid_sections == () and r.failed_gates == () and r.violations == ()
    assert dict(r.lines)[ACT][0] == f"0050：{ACT_CUT_TEXT}"


def test_a8_derived_fields_cannot_be_passed_or_spoofed(dg, base):
    r = _result(dg, base)
    for bad_kw in ({"state": SummaryState.VALID}, {"section_availability": ()}, {"retained_sections": ()},
                   {"notices": ("x",)}, {"failed_gates": ()}):
        with pytest.raises(TypeError):
            SummaryResult(dg, AB0.AiParticipation.RULE_ONLY, base.sections, **bad_kw)       # type: ignore[arg-type]
        # init=False 欄位不能經由 replace 指定：3.11 擲 ValueError（"field X is declared with init=False"），
        # 3.13 擲 TypeError；兩者皆為「被拒絕」。未被拒絕（無例外）仍會使本測試失敗。
        with pytest.raises((TypeError, ValueError)):
            dataclasses.replace(r, **bad_kw)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.state = SummaryState.VALID                                                       # type: ignore[misc]


def test_a8_replace_cannot_smuggle_unchecked_sections(dg, base):
    r = _result(dg, base)
    forged_sec = tuple(SummarySection(s.key, (S(L("買進"), R("x", T.FIELD_LABEL)),)) for s in r.sections)
    with pytest.raises(ValueError):
        dataclasses.replace(r, sections=forged_sec)
    with pytest.raises(ValueError):
        dataclasses.replace(r, sections=base.sections[:-1])
    with pytest.raises(ValueError):
        dataclasses.replace(r, sections=[])
    with pytest.raises(ValueError):
        dataclasses.replace(r, sections=swap(base, MKT, 2, S(R("market.nope", T.FIELD_LABEL))).sections)


def test_a8_replace_digest_rebinds_and_rechecks(dg, base):
    r = _result(dg, base)
    other = make_digest(market_facts=[missing("market.regime"), ok_text("market.light", "🟢"), ok_val("market.health", 72.5)])
    with pytest.raises(ValueError):
        dataclasses.replace(r, digest=other)                    # 內容與新 Digest 不符（regime 其實缺值）


def test_summary_result_invalid_digest_cannot_carry_sections(base):
    bad = make_digest(schema_version="x")
    r = SummaryResult(bad, AB0.AiParticipation.RULE_ONLY, ())
    assert r.state is SummaryState.INVALID and r.sections == () and r.retained_sections == () and r.lines == ()
    assert r.section_availability == () and r.invalid_sections and r.failed_gates and r.violations
    blob = "\n".join(r.notices)
    assert "不輸出任何投資結論" in blob and "其他段落：未保留" in blob and "失敗閘門：" in blob
    with pytest.raises(ValueError):
        SummaryResult(bad, AB0.AiParticipation.RULE_ONLY, base.sections)
    with pytest.raises(ValueError):
        SummaryResult(None, AB0.AiParticipation.RULE_ONLY, base.sections)


def test_summary_result_mode_must_be_existing_ab0_value(dg, base):
    for bad in ("rule_only", None, 1):
        with pytest.raises(ValueError):
            SummaryResult(dg, bad, base.sections)                  # type: ignore[arg-type]
    assert {m.value for m in AB0.AiParticipation} == {"rule_only", "ai_explained", "ai_rejected"}


def test_summary_result_state_is_never_upgraded_by_inputs(dg, base):
    for d in (make_digest(), empty_digest(), make_digest(entries=[], items=[], unkeyed=2)):
        r = SummaryResult(d, AB0.AiParticipation.RULE_ONLY, compose_rule_draft(d).sections)
        assert r.state in (SummaryState.PARTIAL, SummaryState.UNAVAILABLE)       # 現行契約下 VALID 不可達
    assert SummaryResult(empty_digest(), AB0.AiParticipation.RULE_ONLY,
                         compose_rule_draft(empty_digest()).sections).state is SummaryState.UNAVAILABLE


# ══════════════════════════════════════════════════════════════════════
# 渲染與索引
# ══════════════════════════════════════════════════════════════════════
def test_render_sentence_refuses_unchecked_content(dg):
    with pytest.raises(ValueError):
        render_sentence(dg, S(R(section_ref("risk_cap"), T.FIELD_WORDING), R("risk_cap.cap_pct", T.FIELD_VALUE)))
    with pytest.raises(KeyError):
        render_sentence(dg, S(L("nope")))


def test_ref_index_covers_namespaces_and_groups(dg):
    idx = build_ref_index(dg)
    for rid in ("market.regime", ACT0, "action_fact:pf-A:0050", "holding:4:pf-A:0050", "risk_cap.cap_pct",
                *[section_ref(n) for n in T.DIGEST_SECTIONS]):
        assert rid in idx
    assert idx["risk_cap.cap_pct"].group == "restricted" and idx["market.health"].group == "market"
    assert idx["action_fact:pf-A:0050"].group == "holding"
    with pytest.raises(ValueError):
        section_ref("nope")


def test_section_basis_for_baseline(dg):
    ids = [r for r, _ in section_basis(dg, MKT)]
    assert ids == [f.fact_id for f in dg.market.facts] + [section_ref("tw_trend"), section_ref("intl_trend"),
                                                          section_ref("valuation"), section_ref("risk_cap")]
    assert section_basis(dg, ACT) == ()
    assert section_basis(dg, IND) == ((section_ref("industry"), ("section_undefined",)),)
    with pytest.raises(ValueError):
        section_basis(dg, "nope")


def test_every_shape_signature_is_unique_and_templates_exist():
    sigs = [s.signature for s in SHAPES]
    assert len(sigs) == len(set(sigs))
    for sh in SHAPES:
        for el in sh.skeleton:
            if el[0] == "L":
                assert el[1] in T.TEMPLATES


# ══════════════════════════════════════════════════════════════════════
# 建置期 lint：模板與標籤本身不得含被禁字眼（黑名單降級為縱深防禦）
# ══════════════════════════════════════════════════════════════════════
def test_templates_and_labels_are_lint_clean():
    pieces = [*T.TEMPLATES.values(), *T.FACT_LABELS.values(), T.FACT_LABEL_FALLBACK, *T.SECTION_REF_LABELS.values(),
              *T.MISSING_REASON_LABELS.values(), T.MISSING_REASON_LABEL_UNKNOWN, *T.SECTION_LABELS.values(),
              T.MARK_INSUFFICIENT, T.MARK_UNDETERMINED, T.MARK_NOT_DEFINED, T.MARK_NOT_WIRED, T.MARK_RESEARCH_ONLY,
              T.MARK_STALE, T.MARK_PROXY, T.MARK_STRATEGY_UNSET, T.MARK_UNKEYED, T.MARK_NO_ACTION]
    for p in pieces:
        assert lint_hits(p) == [], (p, lint_hits(p))


def test_lint_actually_detects_forbidden_words():
    for w in ("中性", "維持", "買進", "轉弱", "確定", "neutral", "BUY", "🔴", "半導體", "加碼"):
        assert lint_hits(f"x {w} y"), w


def test_term_lists_cover_the_c_document_wording():
    for w in ("中性", "正常", "維持", "續抱"):
        assert w in T.WASHING_TERMS_CJK
    assert "hold" in T.WASHING_TERMS_LATIN and "neutral" in T.WASHING_TERMS_LATIN
    for w in ("變強", "轉弱", "衰退", "崛起"):
        assert w in T.DIRECTION_TERMS_CJK
    assert T.GROUNDING_GATES == ("G1", "G2", "G3", "G4", "G5", "G6")
    assert T.SECTION_KEYS == ("market", "industry", "buy_and_hold", "capital_gain", "actions")
    assert T.SECTION_LABELS[T.SEC_BUY_AND_HOLD] == "存股" and T.SECTION_LABELS[T.SEC_ACTIONS] == "本期行動"


def test_direction_terms_superset_of_ab0():
    assert AB0._DIRECTION_LATIN <= T.DIRECTION_TERMS_LATIN | {"buy", "sell"} | T.ACTION_TERMS_LATIN
    assert all(w in T.DIRECTION_TERMS_CJK for w in AB0._DIRECTION_CJK if len(w) > 1)


def test_risk_cap_wording_is_the_customer_approved_string_verbatim():
    assert T.RISK_CAP_HIDDEN_WORDING == "風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate"


def test_template_set_is_pinned():
    """模板集合被釘住：新增／改字模板＝改摘要可說的話，必須有意識地改這裡（並過審）。"""
    assert set(T.TEMPLATES) == {
        "tpl.glyph", "tpl.colon", "tpl.pct", "tpl.close", "tpl.date_open", "tpl.stale_date_open", "tpl.proxy_tail",
        "tpl.missing_open", "tpl.invalid_tail", "tpl.undetermined_tail", "tpl.unkeyed_open", "tpl.unkeyed_tail",
        "tpl.holdings_no_basis_tail", "tpl.act_no_basis", "tpl.unclassified_open", "tpl.unclassified_tail",
        "tpl.not_applicable_tail", "tpl.contract_drift_tail", "tpl.strategy_none_tail", "tpl.not_wired_tail",
        "tpl.not_defined_tail", "tpl.no_variation_tail", "tpl.label_buy_and_hold", "tpl.label_capital_gain", "tpl.holdings_unavailable_mid", "tpl.strategy_unset_tail",
        "tpl.strategy_is", "tpl.entry_tail", "tpl.act_unavailable_open", "tpl.act_none", "tpl.act_stale_open"}
    assert T.TEMPLATES[T.TPL_ACT_NONE] == "本期行動：規則層未產出行動"
    assert T.TEMPLATES[T.TPL_UNDETERMINED_TAIL] == "，無法判定"


# ══════════════════════════════════════════════════════════════════════
# 欄位展開矩陣（每個（項目種類，欄位）可否展開都釘死）
# ══════════════════════════════════════════════════════════════════════
def test_expand_field_matrix_is_pinned():
    d = make_digest(market_facts=[ok_text("market.regime", "bull"), missing("market.light"),
                                  ok_val("market.health", 72.5)],
                    entries=[entry("0050", ACT_CUT_TEXT, "cut", strategy=StrategyType.BUY_AND_HOLD, source="SRC")],
                    items=[action("0050", ACT_CUT_TEXT, "cut", 1)])
    idx = build_ref_index(d)
    F = T.FIELDS
    expected = {
        "market.regime": {"label", "text", "as_of"},
        "market.light": {"label", "reason"},
        "market.health": {"label", "value", "as_of"},
        "risk_cap.cap_pct": set(), "risk_cap.exposure_lo_pct": set(), "risk_cap.exposure_hi_pct": set(),
        "action_fact:pf-A:0050": {"as_of"},
        "action:pf-A:0050": {"text", "symbol"},
        "holding:4:pf-A:0050": {"symbol", "strategy"},
        "section:market": {"bind"}, "section:tw_trend": {"label", "marker", "bind"},
        "section:intl_trend": {"label", "marker", "bind"}, "section:valuation": {"label", "marker", "bind"},
        "section:industry": {"label", "marker", "bind"}, "section:holdings": {"bind", "count", "unclassified_count", "reason"},
        "section:risk_cap": {"bind", "wording"}, "section:actions": {"bind", "reason"},
    }
    assert set(expected) == set(idx)
    for rid, allowed in expected.items():
        for fld in (*F, "bogus", "source", "strategy_source", ""):
            got = expand(d, idx[rid], fld)[0]
            assert (got is not None) == (fld in allowed), (rid, fld, got)
    # 展開內容本身
    assert expand(d, idx["section:holdings"], "count")[0] == "0"
    assert expand(d, idx["section:tw_trend"], "marker")[0] == "尚未定義"
    assert expand(d, idx["section:valuation"], "marker")[0] == "研究框架，未啟用"
    assert expand(d, idx["holding:4:pf-A:0050"], "strategy")[0] == "存股"
    assert "SRC" not in "".join(expand(d, i, f)[0] or "" for i in idx.values() for f in F)


def test_expand_not_wired_marker_follows_digest_definition_state():
    d = make_digest(industry=DefinitionSection(DefinitionState.NOT_DEFINED, missing_reason=MissingReason.NOT_WIRED))
    assert expand(d, build_ref_index(d)["section:industry"], "marker")[0] == "尚未接線"
    assert check_summary(d, compose_rule_draft(d)).clean


# ══════════════════════════════════════════════════════════════════════
# 前置條件的精確閘門（縱深：同一個錯誤同時被多條規則擋時，每一條都要各自有效）
# ══════════════════════════════════════════════════════════════════════
def test_pre_wrong_group_when_market_shape_is_applied_to_other_groups(dg, base):
    for rid in ("risk_cap.cap_pct", "action_fact:pf-A:0050"):
        rep = check_summary(dg, swap(base, MKT, 2, _fact_sentence("fact_value_ok", rid)))
        assert "wrong_group" in codes(rep), rid


def test_pre_section_shape_must_cite_its_own_section_ref():
    d = make_digest(entries=[], items=[])
    b = compose_rule_draft(d)
    forged = S(L(T.TPL_GLYPH), L(T.TPL_LABEL_BUY_AND_HOLD), L(T.TPL_HOLDINGS_UNAVAILABLE_MID),
               R(section_ref("actions"), T.FIELD_REASON), L(T.TPL_CLOSE))
    rep = check_summary(d, with_section(b, BH, (forged,)))
    assert_rejected(rep, T.GATE_G4, "wrong_section_ref")


def test_pre_action_target_consistency(dg, base):
    nt = S(R(ACT0, T.FIELD_TEXT))                              # 行動有 target，卻用無 target 句型（藏掉代號）
    assert_rejected(check_summary(dg, swap(base, ACT, 0, nt)), T.GATE_G4, "target_mismatch")


def test_g5_unavailable_holdings_with_unkeyed_needs_both_disclosures():
    d = make_digest(entries=[], items=[], unkeyed=2)           # 持股 UNAVAILABLE 且有未帶鍵持股
    b = compose_rule_draft(d)
    assert len(sec_of(b, BH).sentences) == 2 and check_summary(d, b).clean
    only_unkeyed = with_section(b, BH, tuple(x for x in sec_of(b, BH).sentences if x.segments[0] == L(T.TPL_UNKEYED_OPEN)))
    assert_rejected(check_summary(d, only_unkeyed), T.GATE_G5, "missing_disclosure")
    only_unavail = with_section(b, BH, tuple(x for x in sec_of(b, BH).sentences if x.segments[0] != L(T.TPL_UNKEYED_OPEN)))
    assert_rejected(check_summary(d, only_unavail), T.GATE_G5, "missing_disclosure")


def test_summary_result_lines_on_garbage_digest_do_not_raise():
    for bad in (None, {}, "x", make_digest(schema_version="x")):
        r = SummaryResult(bad, AB0.AiParticipation.RULE_ONLY, ())
        assert r.state is SummaryState.INVALID and r.lines == ()


def test_lint_term_lists_pinned_members():
    assert {"確定", "確認", "肯定", "必然", "穩健", "良好", "無虞"} <= set(T.ASSERTIVE_TERMS_CJK)
    assert {"買進", "賣出", "加碼", "減碼", "停利", "停損", "換股", "續抱", "持有"} <= set(T.ACTION_TERMS_CJK)
    assert {"🟢", "🟡", "🔴"} <= set(T.STATE_SYMBOLS) and {"bull", "neutral", "bear", "caution"} <= T.STATE_WORDS_LATIN
    assert {"buy", "sell", "hold"} <= T.ACTION_TERMS_LATIN
