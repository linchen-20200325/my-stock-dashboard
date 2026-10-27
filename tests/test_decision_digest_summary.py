"""AB-2a 規則式摘要測試（fast lane）。

守的是 `src/services/decision_digest_summary.py`：只重新組織 Digest 已有內容、不產生新數值、不改行動文字、
缺值不變中性、未定義維持未定義、Risk Cap 數字不外露；Digest 不合規 → INVALID 且不輸出任何投資結論。
並含 property-style（固定種子的隨機 Digest）與健壯性（Unicode／NaN／重複 id／契約漂移／單段失敗）測試。
"""
from __future__ import annotations

import dataclasses
import random
import re
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from shared import decision_digest_terms as T
from shared import dividend_station_thresholds as TH
from shared.decision_digest import (
    ActionsSection, AiParticipation, Availability, DataStatus, HoldingKey, MissingReason, StrategyType,
)
from shared.decision_digest_grounding import (
    Lit, Ref, expand, SummaryDraft, SummarySection, SummarySentence, build_ref_index, check_summary,
)
from shared.decision_digest_rules import Q4_ACTION_PRIORITY
from shared.decision_digest_validator import SummaryState, assess_digest
from src.compute.etf import dividend_station as ds
from src.services import dividend_station_service as svc
from src.services import decision_digest_summary as SM
from src.services.decision_digest_builder import SourceStamp, build_decision_digest
from src.services.decision_digest_summary import build_rule_summary, compose_rule_draft
from tests.decision_digest_factory import (
    D, action, empty_digest, entry, failed, force_set, invalid, lint_hits, make_digest, missing, ok_text,
    ok_val, proxy_val, stale_text, stale_val,
)

ACT_CUT = "🔴 汰弱：吃本金"
ACT_TP = "💰 強制停利（>+3σ）：獲利轉回核心資產"
ACT_PAUSE = "🟡 訊號亮但季線轉弱 → 暫停加碼、先觀望"
ACT_ADD = "🟢 加碼 50%：連三月落入加碼區"
WASHING = (*T.WASHING_TERMS_CJK,)


def texts(res, key=None):
    return [t for k, ls in res.lines if key in (None, k) for t in ls]


def sec(res, key):
    return next(s for s in res.sections if s.key == key)


def all_text(res):
    return "\n".join(texts(res))


# ══════════════════════════════════════════════════════════════════════
# 形狀與內容
# ══════════════════════════════════════════════════════════════════════
def test_baseline_shape_state_and_mode():
    r = build_rule_summary(make_digest())
    assert r.state is SummaryState.PARTIAL and r.mode is AiParticipation.RULE_ONLY
    assert tuple(s.key for s in r.sections) == T.SECTION_KEYS == r.retained_sections
    assert r.notices == () and r.invalid_sections == () and r.failed_gates == () and r.violations == ()
    assert dict(r.section_availability)[T.SEC_ACTIONS] is Availability.AVAILABLE
    assert all(s.sentences for s in r.sections)                           # 五段都有內容（含「資料不足」說明）
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.state = SummaryState.VALID                                       # type: ignore[misc]


def test_summary_is_deterministic_and_does_not_mutate_digest():
    d = make_digest()
    before = d.to_dict()
    assert build_rule_summary(d) == build_rule_summary(d)
    assert d.to_dict() == before


def test_market_section_content_is_digest_verbatim():
    t = texts(build_rule_summary(make_digest()), T.SEC_MARKET)
    assert t[0] == "市場位階：bull（資料日 2026-10-26）"
    assert t[1] == "市場燈號：🟢（資料日 2026-10-26）"
    assert t[2] == "市場健康度：72.5（資料日 2026-10-26）"
    assert t[3] == T.RISK_CAP_HIDDEN_WORDING


def test_actions_are_verbatim_in_digest_order_and_one_to_three():
    items = [action("0050", ACT_CUT, "cut", 1), action("0056", ACT_TP, "take_profit_force", 2),
             action("00878", ACT_PAUSE, "pause_add", 3)]
    es = [entry("0050", ACT_CUT, "cut"), entry("0056", ACT_TP, "take_profit_force"),
          entry("00878", ACT_PAUSE, "pause_add")]
    for n in (1, 2, 3):
        d = make_digest(entries=es[:n], items=items[:n])
        r = build_rule_summary(d)
        sents = sec(r, T.SEC_ACTIONS).sentences
        assert len(sents) == n
        for s, a in zip(sents, d.actions.items):
            assert s.evidence_refs[0] == a.action_id
        for line, a in zip(texts(r, T.SEC_ACTIONS), d.actions.items):
            assert line == f"{a.target.symbol}：{a.text}"                              # 逐字、不改寫
        # Q4 序：與 Digest 的順序完全一致（不重排）
        assert [s.evidence_refs[0] for s in sents] == [a.action_id for a in d.actions.items]


def test_q4_order_is_never_repaired_by_the_summary():
    """Digest 若違反 Q4 序，摘要不得默默重排；它是 contract drift → INVALID。"""
    d = make_digest(items=[action("0056", ACT_TP, "take_profit_force", 1), action("0050", ACT_CUT, "cut", 2)])
    r = build_rule_summary(d)
    assert r.state is SummaryState.INVALID and r.sections == ()
    assert [name for name, _ in Q4_ACTION_PRIORITY] == ["汰弱", "停利", "趨勢暫停", "加碼"]


def test_no_new_numbers_beyond_digest_literals():
    """獨立 oracle：摘要中每個數字 token，不是 Digest 的值字面、資料日、unkeyed 計數，就是逐字引用內的數字。"""
    d = make_digest(market_facts=[ok_text("market.regime", "bull"), stale_val("market.health", 72.5),
                                  proxy_val("market.light", 3.5)], entries=[], items=[], unkeyed=2)
    allowed = {"72.5", "3.5", "2", "2026-10-26"}
    r = build_rule_summary(d)
    for line in texts(r):
        stripped = re.sub(r"\d{4}-\d{2}-\d{2}", "DATE", line)
        for tok in re.findall(r"\d+(?:\.\d+)?", stripped):
            assert tok in allowed, (line, tok)


def test_missing_never_becomes_neutral_or_zero():
    r = build_rule_summary(empty_digest())
    assert r.state is SummaryState.UNAVAILABLE
    txt = all_text(r)
    for w in WASHING:
        assert w not in txt, w
    assert not re.findall(r"(?<![\w.])0(?:\.0+)?%?(?![\w.])", txt)                      # 沒有任何被當成 0 的缺值
    for s in texts(r, T.SEC_MARKET)[:3]:
        assert s.startswith("⬜") and "資料不足" in s and "無法判定" in s
    assert "資料不足" in texts(r, T.SEC_ACTIONS)[0]
    assert len(sec(r, T.SEC_ACTIONS).sentences) == 1                                      # 沒有行動被編造


def test_unavailable_holdings_is_never_rendered_as_hold_or_normal():
    r = build_rule_summary(make_digest(entries=[], items=[]))
    t = texts(r, T.SEC_BUY_AND_HOLD) + texts(r, T.SEC_CAPITAL_GAIN) + texts(r, T.SEC_ACTIONS)
    assert all("資料不足" in x for x in t)
    assert not any(w in " ".join(t) for w in (*WASHING, "HOLD", "hold", "續抱"))


def test_tw_intl_industry_stay_undefined_without_direction():
    r = build_rule_summary(make_digest())
    tw, intl, val = texts(r, T.SEC_MARKET)[4:7]
    assert tw == "⬜ 台股趨勢：尚未定義，無法判定" and intl == "⬜ 國際趨勢：尚未定義，無法判定"
    assert val == "⬜ 大盤合理區間：研究框架，未啟用，無法判定"
    assert "尚未定義" in texts(r, T.SEC_INDUSTRY)[0] and "無法判定" in texts(r, T.SEC_INDUSTRY)[0]
    joined = all_text(r)
    for w in T.DIRECTION_TERMS_CJK:
        assert w not in joined.replace(ACT_PAUSE, ""), w


def test_valuation_never_emits_a_range_or_eps_pe():
    r = build_rule_summary(make_digest())
    val = texts(r, T.SEC_MARKET)[6]
    assert not re.search(r"\d", val) and "EPS" not in val and "PE" not in val and "區間" in val
    assert "研究框架，未啟用" in val


def test_risk_cap_numbers_never_leak_even_when_valid():
    d = make_digest(risk_valid=True)
    assert d.risk_cap.cap_pct.value == 60
    r = build_rule_summary(d)
    txt = all_text(r)
    assert T.RISK_CAP_HIDDEN_WORDING in txt
    for leak in ("60", "40", "60%", "40%"):
        assert leak not in txt, leak
    for s in (x for sec_ in r.sections for x in sec_.sentences):
        assert not any(ref.startswith("risk_cap.") for ref in s.evidence_refs)


def test_risk_cap_wording_shown_whether_or_not_cap_is_valid():
    a = texts(build_rule_summary(make_digest(risk_valid=True)), T.SEC_MARKET)[3]
    b = texts(build_rule_summary(make_digest(risk_valid=False)), T.SEC_MARKET)[3]
    assert a == b == T.RISK_CAP_HIDDEN_WORDING


def test_stale_proxy_failed_invalid_are_marked_not_upgraded():
    d = make_digest(market_facts=[stale_val("market.health", 72.5), proxy_val("market.light", 3.5),
                                  failed("market.regime")])
    t = texts(build_rule_summary(d), T.SEC_MARKET)
    health = next(x for x in t if "健康度" in x)
    light = next(x for x in t if "燈號" in x)
    regime = next(x for x in t if "位階" in x)
    assert "資料已過期" in health and "2026-10-26" in health
    assert "代理估算" in light and "非正式資料" in light
    assert regime.startswith("⬜") and "抓取失敗" in regime and "無法判定" in regime
    d2 = make_digest(market_facts=[invalid("market.health"), stale_text("market.regime", "bull"),
                                   missing("market.light", MissingReason.CONTRACT_DRIFT)])
    t2 = texts(build_rule_summary(d2), T.SEC_MARKET)
    assert "已丟棄" in next(x for x in t2 if "健康度" in x) and "資料契約異常" in next(x for x in t2 if "燈號" in x)
    assert "資料已過期" in next(x for x in t2 if "位階" in x)


def test_missing_reason_is_never_guessed():
    for reason in MissingReason:
        d = make_digest(market_facts=[missing("market.regime", reason) if reason in (
            MissingReason.NO_INPUT, MissingReason.FETCH_FAILED, MissingReason.NOT_ENOUGH_HISTORY,
            MissingReason.NOT_APPLICABLE, MissingReason.CONTRACT_DRIFT, MissingReason.NO_VARIATION,
            MissingReason.NOT_DEFINED, MissingReason.NOT_WIRED) else missing("market.regime"),
            ok_text("market.light", "🟢"), ok_val("market.health", 1.5)])
        line = texts(build_rule_summary(d), T.SEC_MARKET)[0]
        assert T.MISSING_REASON_LABELS[reason.value] in line


def test_action_sentence_stale_evidence_is_disclosed_and_out_of_scope_evidence_not_cited():
    stale_fact = dataclasses.replace(entry("0050", ACT_CUT, "cut").facts[0], status=DataStatus.STALE)
    e = entry("0050", None, facts=(stale_fact,))
    d = make_digest(entries=[e], items=[action("0050", ACT_CUT, "cut", 1,
                                               evidence=(stale_fact.fact_id, "market.health"))])
    r = build_rule_summary(d)
    s = sec(r, T.SEC_ACTIONS).sentences[0]
    assert "依據資料已過期" in texts(r, T.SEC_ACTIONS)[0] and "2026-10-26" in texts(r, T.SEC_ACTIONS)[0]
    assert s.evidence_refs == (d.actions.items[0].action_id, stale_fact.fact_id)      # 市場事實不在本段引用


def test_actions_available_with_zero_items_says_rule_layer_produced_none():
    d = make_digest(items=[])
    d2 = dataclasses.replace(d, actions=ActionsSection(Availability.AVAILABLE, ()))
    r = build_rule_summary(d2)
    assert texts(r, T.SEC_ACTIONS) == [f"本期行動：{T.MARK_NO_ACTION}"]
    assert not any(w in all_text(r) for w in ("維持", "續抱", "不動作", "HOLD"))      # 沒有行動 ≠ 持有


def test_strategy_classified_holdings_show_unwired_judgement_but_never_the_free_text_source():
    d = make_digest(entries=[entry("0050", "t", "add", strategy=StrategyType.BUY_AND_HOLD, source="客戶設定"),
                             entry("0056", "u", "cut", strategy=StrategyType.CAPITAL_GAIN, source="Sheet 設定")],
                    items=[action("0056", "u", "cut", 1)])
    r = build_rule_summary(d)
    bh, cg = texts(r, T.SEC_BUY_AND_HOLD), texts(r, T.SEC_CAPITAL_GAIN)
    assert bh == ["0050：策略分類為存股；基本面與配置判定尚未接線，無法判定"]            # 來源（使用者自由文字）不進摘要
    assert cg == ["0056：策略分類為資本利得；基本面與配置判定尚未接線，無法判定"]
    assert "客戶設定" not in all_text(r) and "Sheet 設定" not in all_text(r)
    assert dict(r.section_availability)[T.SEC_BUY_AND_HOLD] is Availability.PARTIAL      # 不升格為 AVAILABLE


def test_unclassified_holdings_say_strategy_unset():
    r = build_rule_summary(make_digest())
    assert texts(r, T.SEC_BUY_AND_HOLD) == ["⬜ 存股：尚未設定投資策略分類，無法判定"]
    assert texts(r, T.SEC_CAPITAL_GAIN) == ["⬜ 資本利得：尚未設定投資策略分類，無法判定"]


def test_portfolio_id_without_source_stays_honest_via_real_builder():
    """AB-4r 前沒有 portfolio_id：builder 把持股計為 unkeyed，摘要誠實揭露，且不以代號／Sheet 名稱當鍵。"""
    rows = [{"ticker": t, "name": "n", "held": True, "portfolio_name": "我的Sheet", "lots": 1} for t in ("0050", "0056")]
    d = build_decision_digest(generated_at=datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc), holdings_rows=rows)
    r = build_rule_summary(d)
    assert r.state is SummaryState.UNAVAILABLE
    bh = texts(r, T.SEC_BUY_AND_HOLD)
    assert any("持股資料不足" in x for x in bh) and any("另有 2 檔持股缺少投資組合鍵" in x for x in bh)
    assert "我的Sheet" not in all_text(r) and "pf-" not in all_text(r)
    assert "0050" not in all_text(r)                                                     # 沒有鍵 → 不列出個別持股


# ══════════════════════════════════════════════════════════════════════
# 真實引擎端對端（逐字）
# ══════════════════════════════════════════════════════════════════════
_IDX = pd.date_range("2023-01-01", periods=120, freq="W-SUN")
_I = np.arange(120)
_WEAK = pd.Series(np.r_[20 + 0.02 * _I[:112], (20 + 0.02 * 111) * np.cumprod(np.full(8, 0.98))], index=_IDX)
_UP = pd.Series(20 + 0.01 * _I + 0.05 * np.sin(_I), index=_IDX)


def _real_row(ticker, series, vix):
    a = ds.assess_holding(ticker=ticker, name=ticker, asset_class=TH.ASSET_CORE, weekly_close=series, vix=vix,
                          premium_pct=0.1, sharpe=0.8, total_return_1y_pct=10.0, annual_yield_pct=5.0,
                          inception_years=5, ann_return_3y_pct=5.0, cum_return_3y_pct=15.0, peer_ranks=None)
    r = svc.row_from_assessment(a)
    r["held"] = True
    return r


def test_end_to_end_with_real_engine_text_is_byte_identical():
    rows = [_real_row("0050", _WEAK, 18.0), _real_row("0056", _UP, 18.0)]
    keys = {t: HoldingKey("pf-A", t) for t in ("0050", "0056")}
    d = build_decision_digest(
        generated_at=datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc),
        station_rows=rows, station_stamp=SourceStamp("dividend_station_service", D),
        holdings_rows=[{"ticker": t, "held": True} for t in ("0050", "0056")], holding_keys=keys)
    r = build_rule_summary(d)
    assert r.state is SummaryState.PARTIAL
    want = [row["建議動作"] for row in rows if row["_action"] in ("cut", "take_profit_force", "take_profit_partial",
                                                              "pause_add", "add")]
    got = [x.split("：", 1)[1] for x in texts(r, T.SEC_ACTIONS)]
    assert got == want and len(got) >= 1


# ══════════════════════════════════════════════════════════════════════
# INVALID：不輸出任何投資結論
# ══════════════════════════════════════════════════════════════════════
def _corruptions():
    yield "schema", make_digest(schema_version="decision_digest.v0")
    yield "dup_fact", make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.regime", "x"),
                                                ok_val("market.health", 1.5)])
    yield "order", make_digest(items=[action("0056", ACT_TP, "take_profit_force", 1), action("0050", ACT_CUT, "cut", 2)])
    yield "no_holdings", make_digest(entries=[], items=[action("0050", ACT_CUT, "cut", 1)])
    d2 = make_digest()
    force_set(d2.actions.items[0], origin="ai_layer")
    yield "origin", d2
    yield "zero_width", make_digest(market_facts=[ok_text("market.regime", "bu​ll"), ok_text("market.light", "🟢"),
                                                  ok_val("market.health", 1.5)])
    d3 = make_digest()
    force_set(d3.market.facts[2], value=float("nan"))
    yield "nan", d3
    yield "not_digest", {"market": {}}
    yield "none", None


@pytest.mark.parametrize("name,digest", list(_corruptions()), ids=lambda x: x if isinstance(x, str) else "")
def test_invalid_digest_outputs_no_investment_conclusion(name, digest):
    r = build_rule_summary(digest)
    assert r.state is SummaryState.INVALID and r.mode is AiParticipation.RULE_ONLY
    assert r.sections == () and r.retained_sections == () and r.section_availability == ()
    assert r.invalid_sections and r.failed_gates and r.violations
    blob = "\n".join(r.notices)
    assert "不輸出任何投資結論" in blob and "其他段落：未保留" in blob
    assert "失敗閘門：" in blob and "無效段落：" in blob and "違規代碼：" in blob
    for gate in r.failed_gates:
        assert gate in blob
    for w in (ACT_CUT, ACT_TP, "bull", "72.5", *WASHING):                       # 不洩漏任何結論／數值，也不洗白
        assert w not in blob


def test_invalid_names_the_failing_section_and_gate():
    r = build_rule_summary(make_digest(items=[action("0056", ACT_TP, "take_profit_force", 1),
                                              action("0050", ACT_CUT, "cut", 2)]))
    assert T.SEC_ACTIONS in r.invalid_sections and T.GATE_AB1_ACTION_ORDER in r.failed_gates
    assert "本期行動" in r.notices[1] and T.GATE_AB1_ACTION_ORDER in r.notices[2]


def test_single_section_invalid_does_not_leave_other_sections_as_valid_output():
    """部分段落失敗 → 整份不採信；其餘（本身有效的）市場段也不輸出，且明說未保留。"""
    d = make_digest()
    force_set(d.holdings, unkeyed_count=-1)
    r = build_rule_summary(d)
    assert r.state is SummaryState.INVALID and r.sections == ()
    assert T.SEC_MARKET not in r.invalid_sections and "未保留" in "\n".join(r.notices)


# ══════════════════════════════════════════════════════════════════════
# 自檢：摘要若通不過自己的 G 檢查 → Fail Loud
# ══════════════════════════════════════════════════════════════════════
def _poison_first_market_sentence(monkeypatch, sentence):
    real = compose_rule_draft

    def poisoned(digest):
        draft = real(digest)
        secs = list(draft.sections)
        first = secs[0]
        secs[0] = SummarySection(first.key, (sentence, *first.sentences[1:]))
        return SummaryDraft(tuple(secs))
    monkeypatch.setattr(SM, "compose_rule_draft", poisoned)


@pytest.mark.parametrize("sentence", [
    SummarySentence((Lit("買進"), Ref("market.regime", T.FIELD_LABEL))),                      # 模板不在白名單
    SummarySentence((Ref("market.nope", T.FIELD_LABEL),)),                                   # 引用不存在
    SummarySentence((Ref("market.regime", T.FIELD_LABEL), Lit(T.TPL_UNDETERMINED_TAIL))),    # 骨架不在白名單
    SummarySentence((Ref("market.regime", T.FIELD_LABEL), Lit(T.TPL_COLON), Ref("market.regime", T.FIELD_VALUE),
                     Lit(T.TPL_DATE_OPEN), Ref("market.regime", T.FIELD_AS_OF), Lit(T.TPL_CLOSE))),   # 欄位不可展開
])
def test_self_check_fails_loud_when_summary_would_violate_grounding(monkeypatch, sentence):
    _poison_first_market_sentence(monkeypatch, sentence)
    with pytest.raises(ValueError, match="自檢"):
        build_rule_summary(make_digest())


def test_self_check_fails_loud_on_dropped_sentence(monkeypatch):
    _poison_first_market_sentence(monkeypatch, SummarySentence((Lit(T.TPL_GLYPH),)))        # 無 Ref → 會被 G6 丟棄
    with pytest.raises(ValueError, match="自檢"):
        build_rule_summary(make_digest())


def test_rule_summary_sentences_all_cite_known_refs_and_pass_gates():
    d = make_digest()
    r = build_rule_summary(d)
    idx = build_ref_index(d)
    for sec_ in r.sections:
        for s in sec_.sentences:
            assert s.evidence_refs and all(ref in idx for ref in s.evidence_refs)
            assert all(type(g) in (Lit, Ref) for g in s.segments)                      # 只有模板與欄位展開，沒有自由文字
    assert check_summary(d, SummaryDraft(r.sections)).clean


# ══════════════════════════════════════════════════════════════════════
# 健壯性：Unicode／重複／漂移／單段失敗
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("text", ["ＡＢＣ１２", "bull 🐂", "多頭排列", "é", "𝔹𝕦𝕝𝕝", "  padded  ", "x" * 5000, "中性", "N-A"])
def test_unusual_but_legal_digest_texts_are_carried_verbatim_and_pass_self_check(text):
    d = make_digest(market_facts=[ok_text("market.regime", text), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 72.5)])
    r = build_rule_summary(d)
    assert r.state is SummaryState.PARTIAL and text in texts(r, T.SEC_MARKET)[0]


@pytest.mark.parametrize("ch", ["​", "‍", "‮", "⁠", "\x07", "﻿", "\n", "\t"])
def test_invisible_chars_in_digest_text_are_contract_drift(ch):
    d = make_digest(market_facts=[ok_text("market.regime", f"bull{ch}"), ok_text("market.light", "🟢"),
                                  ok_val("market.health", 72.5)])
    assert build_rule_summary(d).state is SummaryState.INVALID


def test_duplicate_ids_and_partial_failure_do_not_produce_conclusions():
    d = make_digest(entries=[entry("0050", ACT_CUT, "cut")], items=[action("0050", ACT_CUT, "cut", 1)])
    force_set(d.holdings, entries=(d.holdings.entries[0], d.holdings.entries[0]))      # 建構期擋得住，漂移時 validate 擋
    r = build_rule_summary(d)
    assert r.state is SummaryState.INVALID and ACT_CUT not in "\n".join(r.notices)


def test_rule_summary_wording_survives_arbitrary_digest_numbers():
    for v in (0, 0.0, -0.0, 1e-9, 1e15, 123456789.123456789, -72.5, 7, 100):
        d = make_digest(market_facts=[ok_text("market.regime", "bull"), ok_text("market.light", "🟢"),
                                      ok_val("market.health", v)])
        r = build_rule_summary(d)
        assert r.state is SummaryState.PARTIAL
        assert check_summary(d, SummaryDraft(r.sections)).clean


# ══════════════════════════════════════════════════════════════════════
# Property-style：固定種子的隨機 Digest（沒有 hypothesis，刻意用標準庫 random，可重現）
# ══════════════════════════════════════════════════════════════════════
_TEXT_POOL = ["bull", "caution", "bear", "🟢", "🟡", "🔴", "⚪", "數字 12.5", "半導體", "加碼", "x" * 30, "  sp  ",
              "ＡＢＣ", "A-B", "強勢", "7", "2026", "0050"]
_ACTIONS = [("cut", ACT_CUT), ("take_profit_force", ACT_TP), ("pause_add", ACT_PAUSE), ("add", ACT_ADD)]


def _random_market_fact(rng, fid):
    kind = rng.choice(["ok_text", "ok_val", "stale", "proxy", "missing", "failed", "invalid"])
    if kind == "ok_text":
        return ok_text(fid, rng.choice(_TEXT_POOL))
    if kind == "ok_val":
        return ok_val(fid, rng.choice([0, 0.0, 1, -3.5, 72.5, 1e-7, 123456.789, 100]), rng.choice([None, "%"]))
    if kind == "stale":
        return stale_val(fid, rng.choice([1.5, 40, -2]), rng.choice([None, "%"]))
    if kind == "proxy":
        return proxy_val(fid, rng.choice([2.5, 9]), None, rng.choice([None, D]))
    if kind == "missing":
        return missing(fid, rng.choice(list(MissingReason)))
    if kind == "failed":
        return failed(fid, rng.choice([MissingReason.FETCH_FAILED, MissingReason.NO_INPUT]))
    return invalid(fid)


def _random_digest(rng):
    mf = [_random_market_fact(rng, f"market.{n}") for n in ("regime", "light", "health")]
    n_hold = rng.randint(0, 4)
    chosen = sorted(rng.sample(range(len(_ACTIONS)), rng.randint(0, min(3, len(_ACTIONS)))))
    symbols = ["0050", "0056", "00878", "00679B"]
    entries, items = [], []
    for i in range(n_hold):
        sym = symbols[i]
        strat = rng.choice([StrategyType.UNCLASSIFIED, StrategyType.BUY_AND_HOLD, StrategyType.CAPITAL_GAIN])
        src = None if strat is StrategyType.UNCLASSIFIED else rng.choice(["客戶設定", "Sheet X", "src 12"])
        entries.append(entry(sym, None, strategy=strat, source=src))
    for rank, ci in enumerate(chosen, start=1):
        if rank > len(entries):
            break
        code, text = _ACTIONS[ci]
        sym = entries[rank - 1].key.symbol
        entries[rank - 1] = entry(sym, text, code, strategy=entries[rank - 1].strategy,
                                  source=entries[rank - 1].strategy_source)
        items.append(action(sym, text, code, rank))
    return make_digest(market_facts=mf, risk_valid=rng.random() < 0.5, entries=entries, items=items,
                       unkeyed=rng.choice([0, 0, 1, 3]))


def _corrupt(rng, d):
    pick = rng.choice(["schema", "unkeyed", "market_none", "order", "zw"])
    if pick == "schema":
        force_set(d, schema_version="zzz")
    elif pick == "unkeyed":
        force_set(d.holdings, unkeyed_count=-5)
    elif pick == "market_none":
        force_set(d, market=None)
    elif pick == "order" and len(d.actions.items) >= 2:
        force_set(d.actions, items=tuple(reversed(d.actions.items)))
    else:
        force_set(d.market.facts[0], text=(d.market.facts[0].text or "x") + "​") if d.market.facts[0].text \
            else force_set(d, schema_version="zzz")
    return d


@pytest.mark.parametrize("seed", range(8))
def test_property_random_digests_never_raise_and_never_launder_missing(seed):
    rng = random.Random(seed)
    n_valid = n_invalid = 0
    for _ in range(120):
        try:
            d = _random_digest(rng)
        except ValueError:
            continue                                   # AB-0 建構期就拒收的組合不算（那是契約的工作）
        r = build_rule_summary(d)                       # 不得 raise（自檢通過）
        a = assess_digest(d)
        assert r.state is a.state
        if r.state is SummaryState.INVALID:
            n_invalid += 1
            assert r.sections == ()
            continue
        n_valid += 1
        assert r.state in (SummaryState.PARTIAL, SummaryState.UNAVAILABLE)           # 現行契約下 VALID 不可達
        assert tuple(s.key for s in r.sections) == T.SECTION_KEYS
        idx = build_ref_index(d)
        rep = check_summary(d, SummaryDraft(r.sections))
        assert rep.clean
        # 摘要自己寫的部分（模板＋標籤；不含 Digest 逐字內容）不得含任何被禁字眼
        for sec_ in r.sections:
            for sent in sec_.sentences:
                authored = "".join(
                    T.TEMPLATES[g.template_id] if type(g) is Lit
                    else ("" if g.field in (T.FIELD_TEXT, T.FIELD_SYMBOL, T.FIELD_VALUE, T.FIELD_AS_OF, T.FIELD_COUNT,
                                           T.FIELD_STRATEGY)
                          else expand(d, idx[g.ref_id], g.field)[0] or "")
                    for g in sent.segments)
                assert lint_hits(authored) == [], authored
        # 缺值句一定有明示
        for f in d.market.facts:
            if f.status.value in ("missing", "failed", "invalid"):
                line = next(s for s in texts(r, T.SEC_MARKET) if FACT_LABEL(f.fact_id) in s)
                assert "資料不足" in line and "無法判定" in line
        # 行動：筆數與順序與 Digest 完全一致
        assert [s.evidence_refs[0] for s in sec(r, T.SEC_ACTIONS).sentences if s.evidence_refs[0].startswith("action:")] \
            == [a_.action_id for a_ in d.actions.items]
    assert n_valid > 20                                 # 確認隨機產生器真的產生了可用 Digest


def FACT_LABEL(fid):
    return T.FACT_LABELS.get(fid, T.FACT_LABEL_FALLBACK)


@pytest.mark.parametrize("seed", range(4))
def test_property_corrupted_digests_always_degrade_to_invalid_without_raising(seed):
    rng = random.Random(1000 + seed)
    done = 0
    for _ in range(80):
        try:
            d = _random_digest(rng)
        except ValueError:
            continue
        d = _corrupt(rng, d)
        r = build_rule_summary(d)
        if assess_digest(d).state is SummaryState.INVALID:
            done += 1
            assert r.state is SummaryState.INVALID and r.sections == () and r.retained_sections == ()
    assert done > 10


def test_date_type_is_not_datetime_in_fixture():          # 夾具健全性：D 是 date，不是 datetime
    assert type(D) is date


# ══════════════════════════════════════════════════════════════════════
# 行動段：順序／證據（回修版補測）
# ══════════════════════════════════════════════════════════════════════
def test_actions_keep_digest_order_even_when_ids_are_not_sorted():
    d = make_digest(entries=[entry("0056", ACT_CUT, "cut"), entry("0050", ACT_ADD, "add")],
                    items=[action("0056", ACT_CUT, "cut", 1), action("0050", ACT_ADD, "add", 2)])
    r = build_rule_summary(d)
    assert texts(r, T.SEC_ACTIONS) == [f"0056：{ACT_CUT}", f"0050：{ACT_ADD}"]
    assert [a.action_id for a in d.actions.items] != sorted(a.action_id for a in d.actions.items)


@pytest.mark.parametrize("order", [("old_first", "new_second"), ("new_second", "old_first")])
def test_stale_evidence_discloses_the_oldest_date_regardless_of_evidence_order(order):
    from datetime import date as _date
    from shared.decision_digest import Fact, Provenance
    f_old = Fact("ev.old", DataStatus.STALE, Provenance("svc", as_of=_date(2026, 10, 20)), text="舊證據")
    f_new = Fact("ev.new", DataStatus.STALE, Provenance("svc", as_of=_date(2026, 10, 24)), text="新證據")
    from tests.decision_digest_factory import action_fact
    e = entry("0050", None, facts=(action_fact("0050", ACT_CUT, "cut"), f_old, f_new))
    ev = tuple({"old_first": "ev.old", "new_second": "ev.new"}[k] for k in order)
    d = make_digest(entries=[e], items=[action("0050", ACT_CUT, "cut", 1, evidence=ev)])
    assert texts(build_rule_summary(d), T.SEC_ACTIONS) == [f"0050：{ACT_CUT}（依據資料已過期，資料日 2026-10-20）"]


def test_restricted_stale_evidence_does_not_break_or_leak():
    """行動證據指向 Risk Cap 區段的 stale 事實：該事實整個受限（連資料日都不能展開），摘要照常用一般句型、不外露。"""
    from shared import decision_digest as AB0
    from shared.decision_digest import RiskCapSection
    from tests.decision_digest_factory import RISK_RULE, stale_val as _stale
    cap = _stale("risk_cap.cap_pct", 60, "%")
    force_set(cap, rule=RISK_RULE)
    base_rc = make_digest().risk_cap
    rc = RiskCapSection(True, cap, base_rc.exposure_lo_pct, base_rc.exposure_hi_pct, AB0.Availability.PARTIAL)
    d = make_digest(risk_cap=rc, items=[action("0050", ACT_CUT, "cut", 1, evidence=("risk_cap.cap_pct",))],
                    entries=[entry("0050", ACT_CUT, "cut")])
    r = build_rule_summary(d)
    assert texts(r, T.SEC_ACTIONS) == [f"0050：{ACT_CUT}"]
    assert "60" not in all_text(r)
