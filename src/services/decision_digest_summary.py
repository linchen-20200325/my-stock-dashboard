"""L3 Service — 規則式摘要（AB-2a）：把 `DecisionDigest` **重新組織**成五段摘要，**無 AI**。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
資料流：`Digest → AB-2a Validator／Grounding → Rule-based Summary →（未來 AB-2b 才交給 AI）`。
`build_rule_summary(digest)` 是純函式：不取數、不讀檔、不碰 streamlit／session、不呼叫任何 LLM。
它只**重新排列** Digest 已有的內容 ——

- ⛔ 不新增數值（數字一律是 Digest 的字面值，見 `grounding.number_literal`）；
- ⛔ 不新增買賣判斷（行動文字逐字展開自 `ActionRef.text`，依 Digest 既有順序，不重排、不改寫）；
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

═══ 句型白名單與自檢（基準對照） ═══════════════════════════════════════
摘要句是 **segment 序列**（`Lit` 模板 id＋`Ref` 欄位展開），由 `grounding.SHAPES` 的骨架組出 —— 本檔**不寫任何字串**，
文字只在 `SummaryResult.lines` 由 Digest＋`terms.TEMPLATES` 展開。`SummaryResult` 建構時重跑 `check_summary` 並與 Digest 綁定；
未通過（或有 G6 丟棄）即 `ValueError`（Fail Loud：規則式摘要若自己都過不了關，代表摘要或驗證器有 bug）。
`strategy_source`（使用者自由文字）不進摘要。行動句＝代號（`ActionRef.target`）＋`ActionRef.text` 逐字展開，與 Digest
`actions[]` 一對一、同順序；證據中有 stale 事實時改用 stale 句型（取最舊的資料日）。

分層（CLAUDE.md §8.2）：L3 —— 只 import 標準函式庫與 L0（`shared.*`）。
"""
from __future__ import annotations

from typing import Any

from shared.decision_digest import AiParticipation, Availability, DataStatus, DecisionDigest, Fact, StrategyType
from shared.decision_digest_grounding import (
    SHAPES, Lit, Ref, SummaryDraft, SummaryResult, SummarySection, SummarySentence, build_ref_index, holding_ref,
    oldest_stale_evidence, section_ref,
)
from shared.decision_digest_terms import INSUFFICIENT_FAMILY_REASONS, SEC_ACTIONS, SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN, SEC_INDUSTRY, SEC_MARKET
from shared.decision_digest_validator import SummaryState, assess_digest, strategy_entries

def _expand_shape(sid: str, *ref_ids: str) -> SummarySentence:
    """依句型骨架組句：Lit 取模板 id，Ref 依 slot 填入對應 ref_id。骨架是唯一來源 —— 這裡不寫任何字串。"""
    shape = next(sh for sh in SHAPES if sh.sid == sid)
    segs: list = []
    for el in shape.skeleton:
        segs.append(Lit(el[1]) if el[0] == "L" else Ref(ref_ids[el[1]], el[3]))
    return SummarySentence(tuple(segs))


def _fact_sentence(f: Fact) -> SummarySentence:
    st = f.status
    if st in (DataStatus.OK, DataStatus.STALE, DataStatus.PROXY):
        kind = "text" if f.text is not None else ("value_pct" if f.unit == "%" else "value")
        return _expand_shape(f"fact_{kind}_{st.value}", f.fact_id)
    if st is DataStatus.INVALID:
        return _expand_shape("fact_invalid", f.fact_id)
    reason = f.missing_reason.value                                  # MISSING／FAILED：依缺值原因選忠實的句型
    return _expand_shape("fact_missing" if reason in INSUFFICIENT_FAMILY_REASONS else f"fact_{reason}", f.fact_id)


def _market_section(digest: DecisionDigest) -> SummarySection:
    sents = [_fact_sentence(f) for f in digest.market.facts]
    sents.append(_expand_shape("risk_wording", section_ref("risk_cap")))
    for name in ("tw_trend", "intl_trend", "valuation"):
        sents.append(_expand_shape("section_undefined", section_ref(name)))
    return SummarySection(SEC_MARKET, tuple(sents))


def _industry_section() -> SummarySection:
    return SummarySection(SEC_INDUSTRY, (_expand_shape("section_undefined", section_ref("industry")),))


def _strategy_section(digest: DecisionDigest, key: str) -> SummarySection:
    hs = digest.holdings
    rid = section_ref("holdings")
    sents: list = []
    if hs.availability is Availability.UNAVAILABLE:
        sents.append(_expand_shape(f"holdings_unavailable:{key}", rid))
    if hs.unkeyed_count > 0:
        sents.append(_expand_shape("holdings_unkeyed", rid))
    if hs.availability is not Availability.UNAVAILABLE:
        mine = strategy_entries(digest, key)
        for h in mine:
            sents.append(_expand_shape("strategy_entry", holding_ref(h.key.portfolio_id, h.key.symbol)))
        if not mine:
            classified = any(h.strategy is not StrategyType.UNCLASSIFIED for h in hs.entries)
            sents.append(_expand_shape(f"strategy_{'none' if classified else 'unset'}:{key}", rid))
    return SummarySection(key, tuple(sents))


def _actions_section(digest: DecisionDigest, idx: dict) -> SummarySection:
    acts = digest.actions
    rid = section_ref("actions")
    if acts.availability is Availability.UNAVAILABLE:
        return SummarySection(SEC_ACTIONS, (_expand_shape("actions_unavailable", rid),))
    if not acts.items:
        return SummarySection(SEC_ACTIONS, (_expand_shape("actions_none", rid),))
    sents: list = []
    for a in acts.items:
        base = "action_item" if a.target is not None else "action_item_nt"
        ev = oldest_stale_evidence(digest, idx, a)
        if ev is None:
            sents.append(_expand_shape(base, a.action_id))
        else:
            sents.append(_expand_shape(base + "_stale", a.action_id, ev))
    return SummarySection(SEC_ACTIONS, tuple(sents))


def compose_rule_draft(digest: DecisionDigest) -> SummaryDraft:
    """（假設 digest 已通過 `assess_digest`）把 Digest 組成五段 `SummaryDraft`（segment 序列）。不做自檢。"""
    idx = build_ref_index(digest)
    return SummaryDraft(sections=(
        _market_section(digest),
        _industry_section(),
        _strategy_section(digest, SEC_BUY_AND_HOLD),
        _strategy_section(digest, SEC_CAPITAL_GAIN),
        _actions_section(digest, idx),
    ))


def build_rule_summary(digest: Any) -> SummaryResult:
    """純函式：Digest → 規則式摘要（`mode=RULE_ONLY`）。

    Digest 不合規 → INVALID（`SummaryResult` 不帶任何段落）；合規 → 五段，缺資料處以白名單句型明示。
    `SummaryResult` 建構時會重跑 `check_summary`（自檢）；未通過即 `ValueError`（摘要或驗證器有 bug，Fail Loud）。
    """
    if assess_digest(digest).state is SummaryState.INVALID:
        return SummaryResult(digest=digest, mode=AiParticipation.RULE_ONLY, sections=())
    return SummaryResult(digest=digest, mode=AiParticipation.RULE_ONLY, sections=compose_rule_draft(digest).sections)


__all__ = ["compose_rule_draft", "build_rule_summary"]
