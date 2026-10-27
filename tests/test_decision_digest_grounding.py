"""AB-2a grounding 驗證 G1～G6 測試（fast lane）。

守的是 `shared/decision_digest_grounding.py`。每個閘門都有正例（合規句子通過）與反例（違規句子被抓），
反例同時斷言 `accepted is False`、該閘門在 `failed_gates`、並指出具體 code —— 不接受「反正有紅」。
"""
from __future__ import annotations

import dataclasses

import pytest

from shared import decision_digest as AB0
from shared import decision_digest_terms as T
from shared.decision_digest import MissingReason, StrategyType
from shared.decision_digest_grounding import (
    SummaryDraft, SummaryResult, SummarySection, SummarySentence, build_ref_index, check_summary,
    is_numeric_quote, number_literal, remove_quotes, section_basis, section_ref,
)
from shared.decision_digest_validator import SummaryState
from src.services.decision_digest_summary import compose_rule_draft
from tests.decision_digest_factory import (
    D, action, empty_digest, entry, failed, force_set, invalid, make_digest, market_section, missing, ok_text,
    ok_val, proxy_val, stale_text, stale_val,
)

S = SummarySentence
MKT, IND, BH, CG, ACT = T.SEC_MARKET, T.SEC_INDUSTRY, T.SEC_BUY_AND_HOLD, T.SEC_CAPITAL_GAIN, T.SEC_ACTIONS
ACT_CUT_TEXT = "🔴 汰弱：吃本金"
ACT_TP_TEXT = "💰 強制停利（>+3σ）：獲利轉回核心資產"


def sec_of(draft, key):
    return next(s for s in draft.sections if s.key == key)


def swap(draft, key, idx, sentence):
    """換掉某段第 idx 句（sentence=None → 刪除該句）。"""
    out = []
    for s in draft.sections:
        if s.key == key:
            sents = list(s.sentences)
            if sentence is None:
                del sents[idx]
            else:
                sents[idx] = sentence
            s = SummarySection(s.key, tuple(sents))
        out.append(s)
    return SummaryDraft(tuple(out))


def add(draft, key, sentence):
    return SummaryDraft(tuple(SummarySection(s.key, s.sentences + (sentence,)) if s.key == key else s
                              for s in draft.sections))


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
HEALTH_REFS = ("market.health",)


def health(text):
    return S(text, HEALTH_REFS)


# ══════════════════════════════════════════════════════════════════════
# 基準：規則式摘要自己必須全過
# ══════════════════════════════════════════════════════════════════════
def test_rule_summary_passes_all_gates(dg, base):
    rep = check_summary(dg, base)
    assert rep.accepted and rep.violations == () and rep.dropped == () and rep.failed_gates == ()
    assert rep.passed_gates == T.GROUNDING_GATES and rep.surviving == base
    assert not rep.structural_failure and not rep.digest_invalid


@pytest.mark.parametrize("make", [
    lambda: make_digest(), lambda: empty_digest(),
    lambda: make_digest(risk_valid=False),
    lambda: make_digest(market_facts=[stale_val("market.health", 72.5), proxy_val("market.light", 3.5),
                                      failed("market.regime")]),
    lambda: make_digest(market_facts=[invalid("market.health"), stale_text("market.regime", "bull"),
                                      missing("market.light", MissingReason.CONTRACT_DRIFT)]),
    lambda: make_digest(entries=[], items=[], unkeyed=3),
    lambda: make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定"),
                                 entry("0056", "u", "cut", strategy=StrategyType.CAPITAL_GAIN, source="客戶設定")],
                        items=[action("0056", "u", "cut", 1)], unkeyed=1),
])
def test_rule_summary_passes_over_many_digests(make):
    d = make()
    rep = check_summary(d, compose_rule_draft(d))
    assert rep.accepted, [(v.gate, v.code, v.message) for v in rep.violations]


# ══════════════════════════════════════════════════════════════════════
# STRUCT：無法解析＝驗證失敗
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", [None, {}, "text", 42, [], ((),), object()])
def test_unparseable_input_is_validation_failure(dg, bad):
    rep = check_summary(dg, bad)
    assert rep.accepted is False and rep.structural_failure is True and rep.surviving is None
    assert rep.passed_gates == ()


def test_draft_subclass_and_wrong_container_types_rejected(dg, base):
    class Sub(SummaryDraft):
        pass
    assert check_summary(dg, Sub(base.sections)).structural_failure
    assert check_summary(dg, SummaryDraft(list(base.sections))).structural_failure
    assert check_summary(dg, SummaryDraft((object(),))).structural_failure
    bad_sec = SummarySection("market", [S("x", ("a",))])
    assert check_summary(dg, SummaryDraft((bad_sec,))).structural_failure
    assert check_summary(dg, SummaryDraft((SummarySection("market", (object(),)),))).structural_failure


@pytest.mark.parametrize("text", ["", "   ", "含\n換行", "零寬​字", "bom﻿", None, 123])
def test_bad_sentence_text_is_structural(dg, base, text):
    rep = check_summary(dg, swap(base, MKT, 2, S(text, HEALTH_REFS)))
    assert rep.structural_failure and rep.accepted is False


@pytest.mark.parametrize("refs", [["market.health"], ("market.health", "market.health"), ("",), (1,),
                                  ("has space",), ("zero​width",), None])
def test_bad_refs_container_is_structural(dg, base, refs):
    rep = check_summary(dg, swap(base, MKT, 2, S("市場健康度：72.5（資料日 2026-10-26）", refs)))
    assert rep.structural_failure and rep.accepted is False


def test_invalid_digest_means_no_grounding(base):
    rep = check_summary(make_digest(schema_version="x"), base)
    assert rep.digest_invalid and rep.accepted is False and rep.surviving is None and rep.passed_gates == ()
    assert check_summary(None, base).digest_invalid


# ══════════════════════════════════════════════════════════════════════
# G1 引用封閉
# ══════════════════════════════════════════════════════════════════════
def test_g1_unknown_evidence_ref(dg, base):
    rep = check_summary(dg, swap(base, MKT, 2, S("市場健康度：72.5（資料日 2026-10-26）", ("market.nope",))))
    assert_rejected(rep, T.GATE_G1, "ref_not_in_digest")


def test_g1_known_symbol_ok_unknown_symbol_rejected(dg, base):
    ok = S("⬜ 存股：0050 尚未設定投資策略分類，無法判定", ("section:holdings",))
    assert check_summary(dg, swap(base, BH, 0, ok)).accepted
    for sym in ("2330", "00679B", "0051"):
        bad = S(f"⬜ 存股：{sym} 尚未設定投資策略分類，無法判定", ("section:holdings",))
        assert_rejected(check_summary(dg, swap(base, BH, 0, bad)), T.GATE_G1, "symbol_not_in_digest")


def test_g1_latin_ticker(dg, base):
    for w in ("TSLA", "NVDA", "AI"):
        bad = S(f"⬜ 存股：{w} 尚未設定投資策略分類，無法判定", ("section:holdings",))
        assert_rejected(check_summary(dg, swap(base, BH, 0, bad)), T.GATE_G1, "symbol_not_in_digest")
    ok = S("⬜ 存股：ETF 尚未設定投資策略分類，無法判定", ("section:holdings",))
    assert check_summary(dg, swap(base, BH, 0, ok)).accepted


@pytest.mark.parametrize("name", ["半導體", "半導體業", "航運", "生技醫療業", "電子零組件", "金融保險"])
def test_g1_industry_name_rejected_because_digest_has_no_industry_allowlist(dg, base, name):
    bad = S(f"⬜ 產業趨勢：{name}，尚未定義，資料不足，無法判定", ("section:industry",))
    assert_rejected(check_summary(dg, swap(base, IND, 0, bad)), T.GATE_G1, "industry_not_in_digest")


@pytest.mark.parametrize("word", ["🔴", "🟡", "caution", "BULL"])
def test_g1_state_words_only_via_verbatim_quote(dg, base, word):
    bad = S(f"市場健康度：72.5（資料日 2026-10-26）{word}", HEALTH_REFS)
    rep = check_summary(dg, swap(base, MKT, 2, bad))
    assert T.GATE_G1 in rep.failed_gates or T.GATE_G4 in rep.failed_gates
    assert rep.accepted is False
    # 逐字引用（Digest 自己的文字）則放行：actions 句內的 🔴 來自 ActionRef.text
    assert check_summary(dg, base).accepted


# ══════════════════════════════════════════════════════════════════════
# G2 數字字面一致
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("text", [
    "市場健康度：72.5（資料日 2026-10-26）",
    "市場健康度：約72.5（資料日 2026-10-26）",
    "市場健康度：72.5。",
])
def test_g2_literal_numbers_pass(dg, base, text):
    assert check_summary(dg, swap(base, MKT, 2, health(text))).accepted


@pytest.mark.parametrize("text", [
    "市場健康度：72.50（資料日 2026-10-26）",       # 補零 ≠ 字面
    "市場健康度：73（資料日 2026-10-26）",           # 四捨五入
    "市場健康度：72（資料日 2026-10-26）",           # 截斷
    "市場健康度：7.25（資料日 2026-10-26）",         # 位移小數點
    "市場健康度：72.5%（資料日 2026-10-26）",        # 憑空加單位
    "市場健康度：72.5分（資料日 2026-10-26）",       # 憑空加單位（文字）
    "市場健康度：+72.5（資料日 2026-10-26）",        # 憑空加正負號
    "市場健康度：725（資料日 2026-10-26）",
    "市場健康度：1,234（資料日 2026-10-26）",        # 千分位 → 拆成兩個 token
    "市場健康度：72.5（資料日 2026-10-25）",         # 日期不是所引項目的資料日
    "市場健康度：72.5（資料日 2026-10-26），較前期高 3.2",
])
def test_g2_non_literal_numbers_rejected(dg, base, text):
    rep = check_summary(dg, swap(base, MKT, 2, health(text)))
    assert rep.accepted is False and T.GATE_G2 in rep.failed_gates


@pytest.mark.parametrize("text", ["市場健康度：72.5，nan", "市場健康度：72.5，inf", "市場健康度：72.5，∞",
                                  "市場健康度：72.5，Infinity", "市場健康度：72.5，NaN"])
def test_g2_non_finite_tokens_rejected(dg, base, text):
    assert_rejected(check_summary(dg, swap(base, MKT, 2, health(text))), T.GATE_G2, "non_finite_token")


@pytest.mark.parametrize("text", ["市場健康度：７２．５", "市場健康度：72.5①", "市場健康度：٧٢.5", "市場健康度：72.5²"])
def test_g2_non_ascii_digits_rejected(dg, base, text):
    assert_rejected(check_summary(dg, swap(base, MKT, 2, health(text))), T.GATE_G2, "non_ascii_digit")


def test_g2_units_must_match_exactly():
    d = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 60, "%")])
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted                          # "60%"
    for bad in ("60", "60.0%", "60 %", "60‰", "0.6", "60點"):
        rep = check_summary(d, swap(b, MKT, 2, health(f"市場健康度：{bad}（資料日 2026-10-26）")))
        assert rep.accepted is False and T.GATE_G2 in rep.failed_gates, bad


def test_g2_int_vs_float_literals_are_distinct():
    d_int = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                      ok_val("market.health", 60)])
    d_flt = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                      ok_val("market.health", 60.0)])
    for d, good, bad in ((d_int, "60", "60.0"), (d_flt, "60.0", "60")):
        b = compose_rule_draft(d)
        assert check_summary(d, b).accepted
        assert good in sec_of(b, MKT).sentences[2].text
        rep = check_summary(d, swap(b, MKT, 2, health(f"市場健康度：{bad}（資料日 2026-10-26）")))
        assert rep.accepted is False and T.GATE_G2 in rep.failed_gates


@pytest.mark.parametrize("v,lit", [(-1.5, "-1.5"), (0.0, "0.0"), (1e-07, "0.0000001"), (1e22, "10000000000000000000000"),
                                   (123456789.125, "123456789.125"), (-0.0, "-0.0"), (7, "7"), (0, "0")])
def test_number_literal_is_fixed_point_shortest_roundtrip(v, lit):
    assert number_literal(v) == lit


@pytest.mark.parametrize("v", [float("nan"), float("inf"), True, "1", None, 1 + 2j])
def test_number_literal_rejects_non_finite_or_non_real(v):
    with pytest.raises(ValueError):
        number_literal(v)


def test_g2_negative_and_zero_values_and_exponent_forms():
    d = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                  ok_val("market.health", -1.5)])
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted and "-1.5" in sec_of(b, MKT).sentences[2].text
    for bad in ("1.5", "−1.5", "-1.50", "-1.5e0", "1.5e0"):
        assert check_summary(d, swap(b, MKT, 2, health(f"市場健康度：{bad}（資料日 2026-10-26）"))).accepted is False


def test_g2_true_zero_is_a_value_but_zero_text_is_not_a_literal():
    d = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 0)])
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted                              # 真的 0 是資料
    d2 = empty_digest()
    b2 = compose_rule_draft(d2)
    rep = check_summary(d2, swap(b2, MKT, 2, health("⬜ 市場健康度：0，資料不足，無法判定")))
    assert rep.accepted is False and T.GATE_G2 in rep.failed_gates     # missing 不能被寫成 0


def test_g2_risk_cap_numbers_are_restricted(dg, base):
    wording = T.RISK_CAP_HIDDEN_WORDING
    rc_refs = (section_ref("risk_cap"), "risk_cap.cap_pct", "risk_cap.exposure_lo_pct", "risk_cap.exposure_hi_pct")
    for num in ("60", "60%", "40%", "40"):
        rep = check_summary(dg, swap(base, MKT, 3, S(f"{wording} {num}", rc_refs)))
        assert_rejected(rep, T.GATE_G2, "restricted_value")
    rep = check_summary(dg, swap(base, MKT, 3, S(f"{wording} 60%", (section_ref("risk_cap"),))))
    assert_rejected(rep, T.GATE_G2, "number_not_literal")
    assert check_summary(dg, swap(base, MKT, 3, S(wording, rc_refs))).accepted


def test_g2_quote_cannot_launder_a_digit_inside_a_longer_number():
    d = make_digest(market_facts=[ok_text("market.regime", "7"), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 72.5)])
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted
    sneaky = S("市場位階：7，另有 72.5（資料日 2026-10-26）", ("market.regime",))
    rep = check_summary(d, swap(b, MKT, 0, sneaky))
    assert rep.accepted is False and T.GATE_G2 in rep.failed_gates
    assert is_numeric_quote("7") and not is_numeric_quote("bull")


def test_remove_quotes_boundaries():
    assert remove_quotes("abc 72.5 def", ("7",)).count("72.5") == 1                # 不吃進長數字
    assert "bull" not in remove_quotes("市場位階：bull", ("bull",))
    assert "bullish" in remove_quotes("bullish", ("bull",))                          # 不吃進較長英文字
    assert remove_quotes("x", ("",)) == "x"
    assert "風險" not in remove_quotes(T.RISK_CAP_HIDDEN_WORDING, (T.RISK_CAP_HIDDEN_WORDING,))


# ══════════════════════════════════════════════════════════════════════
# G3 狀態不可升級
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("word", list(T.WASHING_TERMS_CJK) + sorted(T.WASHING_TERMS_LATIN))
def test_g3_washing_terms_rejected_anywhere_outside_quotes(word):
    d = empty_digest()
    b = compose_rule_draft(d)
    bad = S(f"⬜ 市場健康度：資料不足，無法判定，目前{word}", HEALTH_REFS)
    assert_rejected(check_summary(d, swap(b, MKT, 2, bad)), T.GATE_G3, "washing_term")


@pytest.mark.parametrize("spelled", ["中 性", "中　性", "ＮＥＵＴＲＡＬ", "Ｈｏｌｄ", "Ｎormal", "續　抱"])
def test_g3_washing_terms_survive_whitespace_and_fullwidth_tricks(spelled):
    d = empty_digest()
    b = compose_rule_draft(d)
    bad = S(f"⬜ 市場健康度：資料不足，無法判定，{spelled}", HEALTH_REFS)
    rep = check_summary(d, swap(b, MKT, 2, bad))
    assert rep.accepted is False and T.GATE_G3 in rep.failed_gates


def test_g3_washing_allowed_only_inside_verbatim_digest_text():
    d = make_digest(market_facts=[ok_text("market.regime", "neutral"), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 72.5)])
    assert check_summary(d, compose_rule_draft(d)).accepted          # regime 的真實輸出是 neutral（規則層文字）
    b = compose_rule_draft(d)
    bad = S("市場位階：neutral，整體正常（資料日 2026-10-26）", ("market.regime",))
    assert_rejected(check_summary(d, swap(b, MKT, 0, bad)), T.GATE_G3, "washing_term")


def test_g3_missing_fact_requires_insufficient_marker():
    d = empty_digest()
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted
    for text in ("市場健康度：不明", "⬜ 市場健康度：待補", "市場健康度（尚無輸入）"):
        assert_rejected(check_summary(d, swap(b, MKT, 2, health(text))), T.GATE_G3, "missing_marker")
    for text in ("市場健康度：資料不足", "市場健康度：無法判定", "⬜ 市場健康度：資料 不足"):
        assert check_summary(d, swap(b, MKT, 2, health(text))).accepted


def test_g3_stale_and_proxy_markers():
    d = make_digest(market_facts=[stale_val("market.health", 72.5), proxy_val("market.light", 3.5),
                                  ok_text("market.regime", "bull")])
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted
    stale_idx = next(i for i, s in enumerate(sec_of(b, MKT).sentences) if s.evidence_refs == ("market.health",))
    proxy_idx = next(i for i, s in enumerate(sec_of(b, MKT).sentences) if s.evidence_refs == ("market.light",))
    rep = check_summary(d, swap(b, MKT, stale_idx, health("市場健康度：72.5（資料日 2026-10-26）")))
    assert_rejected(rep, T.GATE_G3, "missing_marker")
    rep = check_summary(d, swap(b, MKT, proxy_idx, S("市場燈號：3.5", ("market.light",))))
    assert_rejected(rep, T.GATE_G3, "missing_marker")


@pytest.mark.parametrize("term", ["確定", "確認", "肯定", "必然", "穩健", "良好", "無虞"])
def test_g3_assertive_tone_forbidden_for_non_ok_refs_only(term):
    d = empty_digest()
    b = compose_rule_draft(d)
    bad = S(f"⬜ 市場健康度：資料不足，無法判定，{term}", HEALTH_REFS)
    assert_rejected(check_summary(d, swap(b, MKT, 2, bad)), T.GATE_G3, "assertive_tone")
    dg_ok = make_digest()
    ok = health(f"市場健康度：72.5（資料日 2026-10-26），{term}")        # 引用 ok 項目時，確定語氣字眼不在此閘門
    assert "assertive_tone" not in codes(check_summary(dg_ok, swap(compose_rule_draft(dg_ok), MKT, 2, ok)))


@pytest.mark.parametrize("lone", ["N/A", "n/a", "NaN", "none", "null", "—", "-", "無資料", "未評估", "unknown", "?"])
def test_g3_placeholder_segment_rejected(lone):
    d = empty_digest()
    b = compose_rule_draft(d)
    # 標示語齊全（不會因 missing_marker 被擋），只差一個單獨成段的缺值佔位字 —— 必須由 placeholder_segment 抓到
    bad = S(f"⬜ 市場位階：資料不足，無法判定，{lone}", ("market.regime",))
    assert_rejected(check_summary(d, swap(b, MKT, 0, bad)), T.GATE_G3, "placeholder_segment")
    inside = S(f"⬜ 市場位階：資料不足，無法判定，（{lone}）", ("market.regime",))
    assert "placeholder_segment" in codes(check_summary(d, swap(b, MKT, 0, inside)))


def test_g3_undefined_trend_requires_not_defined_marker(dg, base):
    for idx, rid, label in ((4, "tw_trend", "台股趨勢"), (5, "intl_trend", "國際趨勢")):
        bad = S(f"{label}：資料不足，無法判定", (section_ref(rid),))
        assert_rejected(check_summary(dg, swap(base, MKT, idx, bad)), T.GATE_G3, "missing_marker")
    bad = S("大盤合理區間：資料不足，無法判定", (section_ref("valuation"),))
    assert_rejected(check_summary(dg, swap(base, MKT, 6, bad)), T.GATE_G3, "missing_marker")


# ══════════════════════════════════════════════════════════════════════
# G4 不得新增結論類別
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("term", ["買進", "賣出", "加碼", "減碼", "停利", "停損", "換股", "續抱", "BUY", "sell", "Hold",
                                  "ＢＵＹ", "出清", "降低持股"])
def test_g4_new_action_terms_rejected_outside_quotes(dg, base, term):
    bad = S(f"本期行動：建議{term}", ("section:actions",))
    rep = check_summary(dg, add(base, ACT, bad))
    assert rep.accepted is False and T.GATE_G4 in rep.failed_gates and "new_action_term" in codes(rep)


def test_g4_actions_only_via_verbatim_digest_action(dg, base):
    assert check_summary(dg, base).accepted                         # 行動文字本身含「汰弱」「停利」，逐字引用放行
    para = S("0050：建議出清", ("action:pf-A:0050", "action_fact:pf-A:0050"))
    rep = check_summary(dg, swap(base, ACT, 0, para))
    assert_rejected(rep, T.GATE_G4, "action_text_not_verbatim")
    assert "new_action_term" in codes(rep)
    only_symbol = S("0050：請留意", ("action:pf-A:0050",))
    assert_rejected(check_summary(dg, swap(base, ACT, 0, only_symbol)), T.GATE_G4, "action_text_not_verbatim")


def test_g4_cannot_cite_action_a_but_quote_action_b(dg, base):
    swapped = S(f"0056：{ACT_TP_TEXT}", ("action:pf-A:0050",))
    assert_rejected(check_summary(dg, swap(base, ACT, 0, swapped)), T.GATE_G4, "action_text_not_verbatim")


@pytest.mark.parametrize("term", ["變強", "轉弱", "衰退", "崛起", "偏多", "偏空", "多頭", "空頭", "利多", "強勢", "bullish",
                                  "Bear", "downtrend", "看好"])
def test_g4_direction_terms_rejected(dg, base, term):
    for key, idx, rid in ((IND, 0, "section:industry"), (MKT, 4, "section:tw_trend")):
        bad = S(f"⬜ 產業趨勢：尚未定義，無法判定，{term}", (rid,))
        rep = check_summary(dg, swap(base, key, idx, bad))
        assert rep.accepted is False and "new_direction_term" in codes(rep) and T.GATE_G4 in rep.failed_gates


def test_g4_direction_allowed_inside_verbatim_rule_text():
    d = make_digest(entries=[entry("0050", "🟡 訊號亮但季線轉弱 → 暫停加碼、先觀望", "pause_add")],
                    items=[action("0050", "🟡 訊號亮但季線轉弱 → 暫停加碼、先觀望", "pause_add", 1)])
    assert check_summary(d, compose_rule_draft(d)).accepted         # 「轉弱」「暫停加碼」「觀望」來自規則層逐字文字


# ══════════════════════════════════════════════════════════════════════
# G5 段落完整
# ══════════════════════════════════════════════════════════════════════
def test_g5_missing_duplicate_unknown_and_order_of_sections(dg, base):
    secs = list(base.sections)
    rep = check_summary(dg, SummaryDraft(tuple(secs[:-1])))
    assert_rejected(rep, T.GATE_G5, "missing_section")
    rep = check_summary(dg, SummaryDraft(tuple(secs + [secs[0]])))
    assert_rejected(rep, T.GATE_G5, "duplicate_section")
    rep = check_summary(dg, SummaryDraft(tuple(secs + [SummarySection("extra", (S("x", ("market.regime",)),))])))
    assert_rejected(rep, T.GATE_G5, "unknown_section")
    rep = check_summary(dg, SummaryDraft((secs[1], secs[0], *secs[2:])))
    assert_rejected(rep, T.GATE_G5, "section_order")


def test_g5_empty_section_rejected(dg, base):
    for key in T.SECTION_KEYS:
        d = SummaryDraft(tuple(SummarySection(s.key, ()) if s.key == key else s for s in base.sections))
        assert_rejected(check_summary(dg, d), T.GATE_G5, "empty_section")


def test_g5_every_basis_item_must_be_disclosed(dg, base):
    # 刪掉市場段的 Risk Cap 卡面／台股／國際／合理區間 任一句 → missing_disclosure
    for idx in (3, 4, 5, 6):
        rep = check_summary(dg, swap(base, MKT, idx, None))
        assert_rejected(rep, T.GATE_G5, "missing_disclosure")
    # 產業段、存股段、資本利得段的唯一說明句不可缺（刪掉就是空段）
    for key in (IND, BH, CG):
        d = SummaryDraft(tuple(SummarySection(s.key, ()) if s.key == key else s for s in base.sections))
        assert not check_summary(dg, d).accepted


def test_g5_missing_fact_must_be_disclosed():
    d = empty_digest()
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted
    for idx in (0, 1, 2):
        assert_rejected(check_summary(d, swap(b, MKT, idx, None)), T.GATE_G5, "missing_disclosure")


def test_g5_unkeyed_holdings_must_be_disclosed():
    d = make_digest(entries=[], items=[], unkeyed=2)
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted
    txt = sec_of(b, BH).sentences
    assert any("2 檔" in s.text and T.MARK_UNKEYED in s.text for s in txt)
    only = SummaryDraft(tuple(SummarySection(s.key, tuple(x for x in s.sentences if "2 檔" not in x.text))
                              if s.key == BH else s for s in b.sections))
    assert_rejected(check_summary(d, only), T.GATE_G5, "missing_disclosure")
    wrong_count = SummaryDraft(tuple(SummarySection(s.key, tuple(
        S(x.text.replace("2 檔", "3 檔"), x.evidence_refs) for x in s.sentences)) if s.key == BH else s
                                     for s in b.sections))
    assert_rejected(check_summary(d, wrong_count), T.GATE_G2, "number_not_literal")


def test_g5_strategy_classified_entries_need_not_wired_disclosure():
    d = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定")],
                    items=[action("0050", "t", "add")])
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted
    assert section_basis(d, BH) == (("holding:pf-A:0050", (T.MARK_NOT_WIRED,)),)
    assert section_basis(d, CG) == ((section_ref("holdings"), (T.MARK_STRATEGY_UNSET,)),)
    lazy = S("0050：策略分類為存股（來源：客戶設定）；基本面良好", ("holding:pf-A:0050",))
    rep = check_summary(d, swap(b, BH, 0, lazy))
    assert rep.accepted is False and T.GATE_G5 in rep.failed_gates and T.GATE_G3 in rep.failed_gates


def test_g5_no_action_and_unavailable_actions_disclosure():
    d = make_digest(items=[])        # actions UNAVAILABLE（AB-1 的 0 筆行動語意）
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted and "資料不足" in sec_of(b, ACT).sentences[0].text
    bad = S("本期行動：本期無事", ("section:actions",))
    assert not check_summary(d, swap(b, ACT, 0, bad)).accepted


def test_g5_ref_out_of_scope_blocks_padding(dg, base):
    pad = S("⬜ 產業趨勢：尚未定義，資料不足，無法判定", ("section:industry", "market.regime"))
    assert_rejected(check_summary(dg, swap(base, IND, 0, pad)), T.GATE_G5, "ref_out_of_scope")
    pad2 = S("市場健康度：72.5（資料日 2026-10-26）", ("market.health", "action:pf-A:0050"))
    assert_rejected(check_summary(dg, swap(base, MKT, 2, pad2)), T.GATE_G5, "ref_out_of_scope")
    # 一個與「該段」無關的事實不能拿來墊在別段的說明句上
    pad3 = S("⬜ 存股：尚未設定投資策略分類，無法判定", ("market.regime",))
    assert not check_summary(dg, swap(base, BH, 0, pad3)).accepted


# ══════════════════════════════════════════════════════════════════════
# G6 依據可回溯
# ══════════════════════════════════════════════════════════════════════
def test_g6_sentence_without_refs_is_dropped_not_fatal(dg, base):
    extra = S("市場表現亮眼，建議買進", ())
    rep = check_summary(dg, add(base, MKT, extra))
    assert rep.accepted is True and rep.dropped == ((MKT, len(sec_of(base, MKT).sentences)),)
    assert T.GATE_G6 in rep.failed_gates and "no_evidence_ref" in codes(rep)
    assert extra not in sec_of(rep.surviving, MKT).sentences
    assert sec_of(rep.surviving, MKT).sentences == sec_of(base, MKT).sentences
    assert T.GATE_G6 not in rep.passed_gates


def test_g6_dropped_sentence_is_not_inspected_for_other_gates(dg, base):
    rep = check_summary(dg, add(base, MKT, S("中性 TSLA 99.9 買進", ())))
    assert rep.accepted and {v.gate for v in rep.violations} == {T.GATE_G6}


def test_g6_dropping_the_only_disclosure_triggers_g5(dg, base):
    sole = SummaryDraft(tuple(SummarySection(s.key, (S(s.sentences[0].text, ()),)) if s.key == IND else s
                              for s in base.sections))
    rep = check_summary(dg, sole)
    assert rep.accepted is False and T.GATE_G6 in rep.failed_gates and T.GATE_G5 in rep.failed_gates
    assert "empty_section" in codes(rep)


# ══════════════════════════════════════════════════════════════════════
# 引用索引／基準資料
# ══════════════════════════════════════════════════════════════════════
def test_ref_index_covers_namespaces_and_restricts_risk_cap(dg):
    idx = build_ref_index(dg)
    for rid in ("market.regime", "action:pf-A:0050", "action_fact:pf-A:0050", "holding:pf-A:0050",
                "risk_cap.cap_pct", *[section_ref(n) for n in T.DIGEST_SECTIONS]):
        assert rid in idx
    assert idx["risk_cap.cap_pct"].restricted and idx["risk_cap.cap_pct"].literals == ()
    assert idx["risk_cap.cap_pct"].restricted_literals == (("60", "%"),)
    assert idx["market.health"].literals == (("72.5", None),) and idx["market.health"].dates == ("2026-10-26",)
    assert idx["action:pf-A:0050"].action_text == ACT_CUT_TEXT and "0050" in idx["action:pf-A:0050"].quotes
    with pytest.raises(ValueError):
        section_ref("nope")


def test_ref_index_unkeyed_literal():
    d = make_digest(entries=[], items=[], unkeyed=4)
    idx = build_ref_index(d)
    assert idx[section_ref("holdings")].literals == (("4", None),)


def test_section_basis_for_baseline(dg):
    b = section_basis(dg, MKT)
    ids = [r for r, _ in b]
    assert ids == [section_ref("tw_trend"), section_ref("intl_trend"), section_ref("valuation"),
                   section_ref("risk_cap")]
    assert dict(b)[section_ref("risk_cap")] == (T.RISK_CAP_HIDDEN_WORDING,)
    assert section_basis(dg, ACT) == ()                                  # 有行動、無需額外明示
    with pytest.raises(ValueError):
        section_basis(dg, "nope")


# ══════════════════════════════════════════════════════════════════════
# SummaryResult 不變量（狀態不得升格）
# ══════════════════════════════════════════════════════════════════════
def _avail(*vs):
    return tuple(zip(T.SECTION_KEYS, vs))


def _five():
    return tuple(SummarySection(k, ()) for k in T.SECTION_KEYS)


A, P, U = AB0.Availability.AVAILABLE, AB0.Availability.PARTIAL, AB0.Availability.UNAVAILABLE


def test_summary_result_rejects_upgraded_state():
    ok = SummaryResult(SummaryState.PARTIAL, AB0.AiParticipation.RULE_ONLY, _five(), _avail(U, U, U, U, A),
                       retained_sections=T.SECTION_KEYS)
    assert ok.state is SummaryState.PARTIAL
    for state in (SummaryState.VALID, SummaryState.UNAVAILABLE):
        with pytest.raises(ValueError):
            SummaryResult(state, AB0.AiParticipation.RULE_ONLY, _five(), _avail(U, U, U, U, A),
                          retained_sections=T.SECTION_KEYS)
    with pytest.raises(ValueError):
        SummaryResult(SummaryState.VALID, AB0.AiParticipation.RULE_ONLY, _five(), _avail(A, A, A, A, P),
                      retained_sections=T.SECTION_KEYS)


def test_summary_result_invalid_cannot_carry_conclusions():
    with pytest.raises(ValueError):
        SummaryResult(SummaryState.INVALID, AB0.AiParticipation.RULE_ONLY, _five(), (), invalid_sections=("*",))
    with pytest.raises(ValueError):
        SummaryResult(SummaryState.INVALID, AB0.AiParticipation.RULE_ONLY, (), (), invalid_sections=("*",),
                      retained_sections=("market",))
    with pytest.raises(ValueError):
        SummaryResult(SummaryState.INVALID, AB0.AiParticipation.RULE_ONLY, (), ())     # 必須指出哪一段 invalid


def test_summary_result_mode_must_be_existing_ab0_value_and_five_sections():
    with pytest.raises(ValueError):
        SummaryResult(SummaryState.PARTIAL, "rule_only", _five(), _avail(U, U, U, U, A),
                      retained_sections=T.SECTION_KEYS)
    with pytest.raises(ValueError):
        SummaryResult("partial", AB0.AiParticipation.RULE_ONLY, _five(), _avail(U, U, U, U, A),
                      retained_sections=T.SECTION_KEYS)
    with pytest.raises(ValueError):
        SummaryResult(SummaryState.PARTIAL, AB0.AiParticipation.RULE_ONLY, _five()[:-1], _avail(U, U, U, U, A),
                      retained_sections=T.SECTION_KEYS)
    assert {m.value for m in AB0.AiParticipation} == {"rule_only", "ai_explained", "ai_rejected"}


# ══════════════════════════════════════════════════════════════════════
# 字眼清單釘住（防漂移）
# ══════════════════════════════════════════════════════════════════════
def test_terms_cover_the_c_document_wording():
    for w in ("中性", "正常", "維持", "續抱"):          # C §2.4 G3 明列
        assert w in T.WASHING_TERMS_CJK
    assert "hold" in T.WASHING_TERMS_LATIN and "neutral" in T.WASHING_TERMS_LATIN
    for w in ("變強", "轉弱", "衰退", "崛起"):           # C §2.4 G4 明列
        assert w in T.DIRECTION_TERMS_CJK
    assert T.PLACEHOLDER_SEGMENTS is AB0.PLACEHOLDER_TEXTS
    assert T.GROUNDING_GATES == ("G1", "G2", "G3", "G4", "G5", "G6")
    assert T.SECTION_KEYS == ("market", "industry", "buy_and_hold", "capital_gain", "actions")
    assert T.SECTION_LABELS[T.SEC_BUY_AND_HOLD] == "存股" and T.SECTION_LABELS[T.SEC_ACTIONS] == "本期行動"


def test_direction_terms_superset_of_ab0_and_ab1_rule_codes():
    assert AB0._DIRECTION_LATIN <= T.DIRECTION_TERMS_LATIN | {"buy", "sell"} | T.ACTION_TERMS_LATIN
    multi = [w for w in AB0._DIRECTION_CJK if len(w) > 1]
    assert all(w in T.DIRECTION_TERMS_CJK for w in multi)


def test_boilerplate_never_contains_forbidden_terms():
    """摘要自己的標示語與標籤不得含任何會被自己的檢查器拒絕的字眼（否則自檢永遠過不了）。"""
    boiler = [*T.FACT_LABELS.values(), T.FACT_LABEL_FALLBACK, T.LABEL_TW_TREND, T.LABEL_INTL_TREND,
              T.LABEL_VALUATION, T.LABEL_INDUSTRY_TREND, *T.MISSING_REASON_LABELS.values(),
              T.MISSING_REASON_LABEL_UNKNOWN, T.MARK_INSUFFICIENT, T.MARK_UNDETERMINED, T.MARK_NOT_DEFINED,
              T.MARK_NOT_WIRED, T.MARK_RESEARCH_ONLY, T.MARK_STALE, T.MARK_PROXY, T.MARK_STRATEGY_UNSET,
              T.MARK_UNKEYED, T.MARK_NO_ACTION, *T.SECTION_LABELS.values()]
    banned = (*T.WASHING_TERMS_CJK, *T.ACTION_TERMS_CJK, *T.DIRECTION_TERMS_CJK, *T.ASSERTIVE_TERMS_CJK)
    for text in boiler:
        for term in banned:
            assert term not in text, (text, term)


def test_force_set_helper_really_bypasses_frozen():
    f = ok_val("x.y", 1.5)
    force_set(f, value=2.5)
    assert f.value == 2.5
    assert dataclasses.is_dataclass(f) and market_section((f,)) is not None and D.year == 2026


def test_trend_observations_are_reference_only_and_never_citable_as_numbers():
    """均線等「僅供參考」的觀測值（DEC-092 Q2）：Digest 可攜帶，摘要不渲染，AI 也不得把它寫成數字。"""
    from shared.decision_digest import DefinitionSection, DefinitionState, RuleRef
    obs = ok_val("tw.twii_close", 20000.5, "pts", rule=RuleRef("add", "action_branch.v1"))
    d = dataclasses.replace(make_digest(), tw_trend=DefinitionSection(
        DefinitionState.NOT_DEFINED, observations=(obs,)))
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted
    assert "20000.5" not in "".join(s.text for sec in b.sections for s in sec.sentences)
    idx = build_ref_index(d)
    assert idx["tw.twii_close"].restricted and idx["tw.twii_close"].literals == ()
    refs = (section_ref("tw_trend"), "tw.twii_close")
    cited = S("⬜ 台股趨勢：尚未定義，無法判定，收盤 20000.5pts", refs)
    assert_rejected(check_summary(d, swap(b, MKT, 4, cited)), T.GATE_G2, "restricted_value")
    uncited = S("⬜ 台股趨勢：尚未定義，無法判定，收盤 20000.5", (section_ref("tw_trend"),))
    assert_rejected(check_summary(d, swap(b, MKT, 4, uncited)), T.GATE_G2, "number_not_literal")


def test_summary_result_availability_must_cover_five_sections_in_order():
    bad = tuple(zip(reversed(T.SECTION_KEYS), (U, U, U, U, A)))
    with pytest.raises(ValueError):
        SummaryResult(SummaryState.PARTIAL, AB0.AiParticipation.RULE_ONLY, _five(), bad,
                      retained_sections=T.SECTION_KEYS)


def test_g5_actions_disclosure_must_cite_the_actions_section_itself():
    """actions 不可得時，必須有句子明示 `section:actions`；用別的（同樣在本段範圍內）引用湊數不算。"""
    d = make_digest(items=[])
    b = compose_rule_draft(d)
    pad = S("⬜ 本期行動：持股資料不足，無法判定", ("section:holdings",))       # 有標示語、引用在範圍內，但不是 actions 本身
    rep = check_summary(d, swap(b, ACT, 0, pad))
    assert_rejected(rep, T.GATE_G5, "missing_disclosure")


def test_g5_industry_disclosure_must_cite_the_industry_section_itself():
    d = make_digest()
    b = compose_rule_draft(d)
    # 產業段只允許引用 section:industry；任何其他引用都會先被範圍檢查擋下
    pad = S("⬜ 產業趨勢：尚未定義，資料不足，無法判定", ("section:holdings",))
    rep = check_summary(d, swap(b, IND, 0, pad))
    assert rep.accepted is False and ("ref_out_of_scope" in codes(rep) or "missing_disclosure" in codes(rep))


def test_g2_restricted_fact_dates_are_not_citable_either(dg, base):
    """Risk Cap 區段的項目整個受限：連它的資料日也不能拿來當句內日期的依據。"""
    refs = (section_ref("risk_cap"), "risk_cap.cap_pct")
    rep = check_summary(dg, swap(base, MKT, 3, S(f"{T.RISK_CAP_HIDDEN_WORDING}（資料日 2026-10-26）", refs)))
    assert_rejected(rep, T.GATE_G2, "date_not_in_digest")


def test_quote_removal_start_boundary_blocks_digit_laundering():
    """引用 `7`、值 `5`：句子寫 `57` 不得被「吃掉 7、剩 5 剛好是字面」而放行。"""
    d = make_digest(market_facts=[ok_text("market.regime", "7"), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 5)])
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted
    sneaky = S("市場健康度：57（資料日 2026-10-26）", ("market.health", "market.regime"))
    rep = check_summary(d, swap(b, MKT, 2, sneaky))
    assert rep.accepted is False and T.GATE_G2 in rep.failed_gates
    assert remove_quotes("57", ("7",)) == "57" and remove_quotes("5 7", ("7",)).strip() == "5"


def test_action_text_is_a_verbatim_quote_even_without_the_evidence_fact(dg, base):
    """只引用行動 id（不帶 evidence 事實）時，行動文字仍是逐字引用（否則「汰弱」「停利」會被當成新行動字眼）。"""
    only_action = S(f"0050：{ACT_CUT_TEXT}", ("action:pf-A:0050",))
    rep = check_summary(dg, swap(base, ACT, 0, only_action))
    assert rep.accepted, [(v.code, v.message) for v in rep.violations]


def test_g5_holdings_unavailable_must_cite_the_holdings_section_itself():
    d = make_digest(entries=[entry("0050", None)], items=[])             # 有持股 entry 但沒有任何事實 → holdings UNAVAILABLE
    assert d.holdings.availability is AB0.Availability.UNAVAILABLE
    b = compose_rule_draft(d)
    assert check_summary(d, b).accepted
    pad = S("⬜ 存股：0050 基本面尚未接線，無法判定", ("holding:pf-A:0050",))      # 範圍內、有標示語，但不是 section:holdings
    rep = check_summary(d, swap(b, BH, 0, pad))
    assert_rejected(rep, T.GATE_G5, "missing_disclosure")


def test_risk_cap_wording_is_the_customer_approved_string_verbatim():
    """DEC-081 Q2-2 客戶卡面措辭（逐字；改字＝改客戶核准的文案，必須走 Gate）。"""
    assert T.RISK_CAP_HIDDEN_WORDING == "風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate"
