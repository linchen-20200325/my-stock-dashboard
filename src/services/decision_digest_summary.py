"""L3 Service — 規則式摘要（AB-2a）：把 `DecisionDigest` **重新組織**成五段摘要，**無 AI**。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
資料流：`Digest → AB-2a Validator／Grounding → Rule-based Summary →（未來 AB-2b 才交給 AI）`。
`build_rule_summary(digest)` 是純函式：不取數、不讀檔、不碰 streamlit／session、不呼叫任何 LLM。
它只**重新排列** Digest 已有的內容 ——

- ⛔ 不新增數值（數字一律是 Digest 的字面值，見 `grounding.number_literal`）；
- ⛔ 不新增買賣判斷（行動文字逐字取自 `ActionRef.text`，依 Digest 既有順序，不重排、不改寫）；
- ⛔ 不新增門檻／權重／產業結論／趨勢結論／候選股／AI 信心機率；
- 台股趨勢／國際趨勢／產業趨勢維持「尚未定義」；大盤合理區間維持「研究框架，未啟用」（不出區間）；
- Risk Cap 未核准顯示（DEC-081 Q2-2）：只顯示客戶核准的卡面措辭，**不顯示 Risk Cap 區段任何數值**；
- `portfolio_id` 無正式來源：持股維持 Digest 的 PARTIAL／UNAVAILABLE，缺鍵持股只以 `unkeyed_count` 揭露。

═══ 五段（C §3.1）與降級 ═══════════════════════════════════════════════
市場／產業／存股／資本利得／本期行動。每段的可得性只由 Digest 推導（`section_availability`），
整體狀態四態：VALID／PARTIAL／UNAVAILABLE／INVALID（見 `shared.decision_digest_validator`）。
- INVALID（契約漂移）：`sections=()`，**不輸出任何投資結論**，`notices` 指出哪一段 invalid、哪個閘門失敗、
  其他段落是否保留（一律不保留）；
- 其餘三態：五段都輸出；缺資料的項目以「⬜ …資料不足，無法判定」明示，**不省略、不以中性／正常／維持代替**。

═══ 自檢（基準對照） ═══════════════════════════════════════════════════
產生的 `SummaryDraft` 在回傳前一律通過 `check_summary`（G1～G6）；未通過即 `ValueError`（Fail Loud：
規則式摘要若自己都過不了關，代表摘要或驗證器有 bug，不得把它端出去）。

行動句引用：行動 id＋其 evidence 中**屬於「本期行動」段依據**的事實（持股事實）；evidence 若指向市場／
Risk Cap 事實，該事實不在本段引用（行動 id 本身已可回溯到 Digest 內的 evidence_refs）。

分層（CLAUDE.md §8.2）：L3 —— 只 import 標準函式庫與 L0（`shared.*`）。
"""
from __future__ import annotations

from typing import Any

from shared.decision_digest import (
    ActionRef, AiParticipation, Availability, DataStatus, DecisionDigest, Fact,
)
from shared.decision_digest_grounding import (
    SummaryDraft, SummaryResult, SummarySection, SummarySentence, build_ref_index, check_summary,
    holding_ref, number_literal, section_ref,
)
from shared.decision_digest_terms import (
    FACT_LABEL_FALLBACK, FACT_LABELS, LABEL_INDUSTRY_TREND, LABEL_INTL_TREND, LABEL_TW_TREND,
    LABEL_VALUATION, MARK_NO_ACTION, MARK_NOT_WIRED, MARK_STRATEGY_UNSET, MARK_UNDETERMINED, MARK_UNKEYED,
    MISSING_GLYPH, MISSING_REASON_LABEL_UNKNOWN, MISSING_REASON_LABELS, RISK_CAP_HIDDEN_WORDING, SEC_ACTIONS,
    SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN, SEC_INDUSTRY, SEC_MARKET, SECTION_KEYS, SECTION_LABELS,
)
from shared.decision_digest_validator import (
    SECTION_ALL, SummaryState, assess_digest, strategy_entries,
)

#: 診斷用：整份 Digest 層級（不屬任一摘要段）的顯示名。
_LABEL_ALL = "整份 Digest（跨段／結構）"


def _reason_label(reason: Any) -> str:
    value = getattr(reason, "value", None)
    return MISSING_REASON_LABELS.get(value, MISSING_REASON_LABEL_UNKNOWN)


def _fact_rendered(f: Fact) -> str:
    if f.text is not None:
        return f.text
    return f"{number_literal(f.value)}{f.unit or ''}"


def _fact_sentence(f: Fact) -> SummarySentence:
    label = FACT_LABELS.get(f.fact_id, FACT_LABEL_FALLBACK)
    d = f.provenance.as_of.isoformat() if f.provenance.as_of is not None else None
    refs = (f.fact_id,)
    if f.status is DataStatus.OK:
        return SummarySentence(f"{label}：{_fact_rendered(f)}（資料日 {d}）", refs)
    if f.status is DataStatus.STALE:
        return SummarySentence(f"{label}：{_fact_rendered(f)}（資料已過期，資料日 {d}）", refs)
    if f.status is DataStatus.PROXY:
        tail = f"，資料日 {d}" if d is not None else ""
        return SummarySentence(f"{label}：{_fact_rendered(f)}（代理估算值，非正式資料{tail}）", refs)
    if f.status is DataStatus.INVALID:
        return SummarySentence(f"{MISSING_GLYPH} {label}：資料不合法，已丟棄，資料不足，{MARK_UNDETERMINED}", refs)
    # MISSING／FAILED
    return SummarySentence(
        f"{MISSING_GLYPH} {label}：資料不足，{MARK_UNDETERMINED}（{_reason_label(f.missing_reason)}）", refs)


def _market_section(digest: DecisionDigest, idx: dict) -> SummarySection:
    sents = [_fact_sentence(f) for f in digest.market.facts]
    sents.append(SummarySentence(RISK_CAP_HIDDEN_WORDING, (section_ref("risk_cap"),)))
    for name, label in (("tw_trend", LABEL_TW_TREND), ("intl_trend", LABEL_INTL_TREND),
                        ("valuation", LABEL_VALUATION)):
        rid = section_ref(name)
        sents.append(SummarySentence(f"{MISSING_GLYPH} {label}：{idx[rid].markers[0]}，{MARK_UNDETERMINED}", (rid,)))
    return SummarySection(SEC_MARKET, tuple(sents))


def _industry_section(idx: dict) -> SummarySection:
    rid = section_ref("industry")
    return SummarySection(SEC_INDUSTRY, (SummarySentence(
        f"{MISSING_GLYPH} {LABEL_INDUSTRY_TREND}：{idx[rid].markers[0]}，資料不足，{MARK_UNDETERMINED}", (rid,)),))


def _strategy_section(digest: DecisionDigest, key: str) -> SummarySection:
    label = SECTION_LABELS[key]
    hs = digest.holdings
    rid = section_ref("holdings")
    sents: list = []
    if hs.availability is Availability.UNAVAILABLE:
        sents.append(SummarySentence(
            f"{MISSING_GLYPH} {label}：持股資料不足，{MARK_UNDETERMINED}（{_reason_label(hs.missing_reason)}）", (rid,)))
    if hs.unkeyed_count > 0:
        sents.append(SummarySentence(
            f"{MISSING_GLYPH} 另有 {hs.unkeyed_count} 檔持股{MARK_UNKEYED}，未納入判讀，資料不足，{MARK_UNDETERMINED}",
            (rid,)))
    if hs.availability is not Availability.UNAVAILABLE:
        mine = strategy_entries(digest, key)
        for h in mine:
            sents.append(SummarySentence(
                f"{h.key.symbol}：策略分類為{h.strategy.value}（來源：{h.strategy_source}）；"
                f"基本面與配置判定{MARK_NOT_WIRED}，{MARK_UNDETERMINED}",
                (holding_ref(h.key.portfolio_id, h.key.symbol),)))
        if not mine:
            sents.append(SummarySentence(f"{MISSING_GLYPH} {label}：{MARK_STRATEGY_UNSET}，{MARK_UNDETERMINED}", (rid,)))
    return SummarySection(key, tuple(sents))


def _action_sentence(a: ActionRef, idx: dict, facts_by_id: dict) -> SummarySentence:
    head = f"{a.target.symbol}：{a.text}" if a.target is not None else a.text
    refs = [a.action_id]
    for r in a.evidence_refs:
        info = idx.get(r)
        if info is not None and SEC_ACTIONS in info.scopes and not info.restricted:
            refs.append(r)
            f = facts_by_id.get(r)
            if f is not None and f.status is DataStatus.STALE:
                head += f"（依據資料已過期，資料日 {f.provenance.as_of.isoformat()}）"
    return SummarySentence(head, tuple(refs))


def _actions_section(digest: DecisionDigest, idx: dict) -> SummarySection:
    acts = digest.actions
    rid = section_ref("actions")
    if acts.availability is Availability.UNAVAILABLE:
        return SummarySection(SEC_ACTIONS, (SummarySentence(
            f"{MISSING_GLYPH} 本期行動：資料不足，{MARK_UNDETERMINED}（{_reason_label(acts.missing_reason)}）",
            (rid,)),))
    if not acts.items:
        return SummarySection(SEC_ACTIONS, (SummarySentence(f"本期行動：{MARK_NO_ACTION}", (rid,)),))
    facts_by_id = {f.fact_id: f for h in digest.holdings.entries for f in h.facts}
    return SummarySection(SEC_ACTIONS, tuple(_action_sentence(a, idx, facts_by_id) for a in acts.items))


def compose_rule_draft(digest: DecisionDigest) -> SummaryDraft:
    """（假設 digest 已通過 `assess_digest`）把 Digest 組成五段 `SummaryDraft`。不做自檢。"""
    idx = build_ref_index(digest)
    return SummaryDraft(sections=(
        _market_section(digest, idx),
        _industry_section(idx),
        _strategy_section(digest, SEC_BUY_AND_HOLD),
        _strategy_section(digest, SEC_CAPITAL_GAIN),
        _actions_section(digest, idx),
    ))


def _invalid_notices(assessment: Any) -> tuple:
    secs = "、".join(_LABEL_ALL if k == SECTION_ALL else SECTION_LABELS[k] for k in assessment.invalid_sections)
    codes = "、".join(sorted({v.code for v in assessment.violations}))
    return (
        "⛔ Decision Digest 契約不合規（contract drift）：不輸出任何投資結論。",
        f"無效段落：{secs}",
        f"失敗閘門：{'、'.join(assessment.failed_gates)}",
        f"違規代碼：{codes}",
        "其他段落：未保留（違規影響範圍未知，整份 Digest 不採信）。",
    )


def build_rule_summary(digest: Any) -> SummaryResult:
    """純函式：Digest → 規則式摘要（`mode=RULE_ONLY`）。任何輸入都不會產出投資結論的「猜測」：
    Digest 不合規 → INVALID（不輸出段落）；合規 → 五段，缺資料處明示。自檢未過 → `ValueError`。"""
    a = assess_digest(digest)
    if a.state is SummaryState.INVALID:
        return SummaryResult(
            state=SummaryState.INVALID, mode=AiParticipation.RULE_ONLY, sections=(), section_availability=(),
            notices=_invalid_notices(a), invalid_sections=a.invalid_sections, failed_gates=a.failed_gates,
            violations=a.violations, retained_sections=())
    draft = compose_rule_draft(digest)
    report = check_summary(digest, draft)
    if not report.accepted or report.dropped:
        raise ValueError("規則式摘要未通過自檢（摘要或驗證器有 bug）：" + "；".join(
            f"[{v.gate}/{v.code}] {v.section}#{v.sentence_index}: {v.message}" for v in report.violations))
    return SummaryResult(
        state=a.state, mode=AiParticipation.RULE_ONLY, sections=draft.sections,
        section_availability=a.section_availability, notices=(), invalid_sections=(), failed_gates=(),
        violations=(), retained_sections=SECTION_KEYS)


__all__ = ["compose_rule_draft", "build_rule_summary"]
