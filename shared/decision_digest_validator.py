"""shared/decision_digest_validator.py — Decision Digest 自身的驗證＋四態降級（AB-2a；L0 純函式）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
資料流：`Digest → AB-2a Validator／Grounding → Rule-based Summary →（未來 AB-2b 才交給 AI）`。
本檔是第一關：**只看 Digest 自己**是否可信，並把結果降級成四態 `SummaryState`：

    VALID        Digest 合規，且五段摘要的依據全部 AVAILABLE（現行契約下**不可達**：產業趨勢與策略分類
                 的正式定義未核准，那兩段恆為 UNAVAILABLE —— 這是誠實，不是 bug）
    PARTIAL      Digest 合規，部分段落可用：只輸出可證明部分，**不得**把整體標 AVAILABLE
    UNAVAILABLE  Digest 合規，但五段依據全部不可用：顯示「⬜ 資料不足／無法判定」
    INVALID      Digest 不合規（contract drift）：**不輸出任何投資結論**

availability **只能由資料推導**（沿用 AB-0 `derive_availability`／各段已推導的 `availability`），
任何一段都不會因為「看起來沒問題」被升格。

═══ INVALID 的保留政策（AB-2a 內部決定，見 docs/vnext/NEWUI_D25_AB2A_SPEC_2026-10-27.md §7） ═══════════════════════
Digest 的跨物件不變量（fact_id 唯一、evidence 指向可用事實、行動 vs 持股一致…）一旦被破壞，代表
**產生這份 Digest 的 builder 違反了契約，其影響範圍未知**。因此 INVALID 時**整份不採信**：
`SummaryResult.retained_sections == ()`，只回報「哪一段 invalid、哪個閘門失敗」供診斷。
（替代方案「保留未受影響的段落」需要證明段落間無依賴；AB-0 的 evidence_refs 就是跨段依賴，
故不採。）

═══ 本檔只做三件 AB-0／AB-1 沒做的事（其餘一律沿用，不弱化） ═══════════════════
沿用：AB-0 `validate`、AB-1 `validate_rule_ids`、`validate_action_order`（三者逐一呼叫，各自標閘門）。
新增（皆為「只收緊」）：
1. `control_chars_in_text`：Fact.text／ActionRef.text／strategy_source 含控制／零寬／格式／私用區字元、行段分隔、非普通空格的空白或孤立組合記號
   （AB-0 沒禁；摘要要**逐字**引用這些文字，帶不可見字元會讓逐字比對與字眼檢查失真）。
2. `ref_id_reserved`／`ref_id_collision`：fact_id／action_id 以保留前綴（`section:`、`holding:`）開頭，
   或 fact_id 與 action_id 相同 —— 會讓 evidence_refs 的命名空間含糊。
3. 輸入不是 `DecisionDigest` → INVALID（不 raise）。
4. `unsupported_unit`：市場事實的 unit 不在 `terms.SUPPORTED_UNITS`（摘要的單位由模板決定，不展開 Digest 的 unit 字串）。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫與 `shared.*`；零 I/O、零 streamlit、零 `src.*`。
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any

from shared.decision_digest import (
    ActionRef, ActionsSection, Availability, DecisionDigest, DefinitionSection, Fact, FactSection,
    HoldingEntry, HoldingKey, HoldingsSection, RiskCapSection, StrategyType, validate,
)
from shared.decision_digest_rules import validate_action_order, validate_rule_ids
from shared.decision_digest_terms import (
    ALLOWED_SPACE, COMBINING_CATEGORIES, DIGEST_GATES_ORDER, FACT_LABELS, FORBIDDEN_CHAR_CATEGORIES, GATE_AB0_CONTRACT, GATE_AB1_ACTION_ORDER, GATE_AB1_RULE_ID, GATE_AB2A_REFS,
    GATE_AB2A_TEXT, REF_HOLDING_PREFIX, REF_SECTION_PREFIX, SEC_ACTIONS, SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN,
    SEC_INDUSTRY, SEC_MARKET, SECTION_KEYS, SUPPORTED_UNITS, INSUFFICIENT_FAMILY_REASONS, SYMBOL_PATTERN,
)

_SYMBOL_RE = re.compile(SYMBOL_PATTERN)


def holding_ref(portfolio_id: str, symbol: str) -> str:
    """持股的引用 id —— **無歧義編碼**：`holding:<portfolio_id 長度>:<portfolio_id>:<symbol>`。

    portfolio_id 是不透明鍵、可含 `:`（AB-0 允許），所以不能用分隔符拼接（("a:b","c") 與 ("a","b:c") 會碰撞）；
    以長度前綴後，任何 (portfolio_id, symbol) 都唯一對應一個字串，反之亦然（symbol 不含 `:`，見 `SYMBOL_PATTERN`）。
    """
    return f"{REF_HOLDING_PREFIX}{len(portfolio_id)}:{portfolio_id}:{symbol}"


#: 診斷用：不屬於任一摘要段（整份 Digest 層級）的違規，標為此鍵。
SECTION_ALL = "*"


class SummaryState(str, Enum):
    """摘要的四態降級（AB-2a）。⛔ 沒有 neutral／normal；UNAVAILABLE ≠ 中性。"""
    VALID = "valid"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


@dataclass(frozen=True)
class DigestViolation:
    gate: str            # GATE_AB0_CONTRACT／GATE_AB1_RULE_ID／GATE_AB1_ACTION_ORDER／GATE_AB2A_*
    section: str         # 受影響的摘要段（`SECTION_KEYS` 之一，或 `SECTION_ALL`）
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class DigestAssessment:
    state: SummaryState
    violations: tuple                 # tuple[DigestViolation]
    invalid_sections: tuple           # 受影響的摘要段鍵（去重、依 SECTION_KEYS 順序；整份層級 → ("*",)）
    failed_gates: tuple               # 去重排序的閘門識別碼
    section_availability: tuple       # ((段鍵, Availability), ...) —— INVALID 時為 ()


# ── 路徑 → 摘要段 ─────────────────────────────────────────────────────────
#: Digest 段（路徑第一節）→ 依賴它的摘要段。holdings 同時餵存股與資本利得兩段。
_PATH_TO_SECTIONS: dict = {
    "market": (SEC_MARKET,), "tw_trend": (SEC_MARKET,), "intl_trend": (SEC_MARKET,),
    "valuation": (SEC_MARKET,), "risk_cap": (SEC_MARKET,),
    "industry": (SEC_INDUSTRY,),
    "holdings": (SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN),
    "actions": (SEC_ACTIONS,),
}


def _sections_for_path(path: Any) -> tuple:
    head = str(path).split(".", 1)[0].split("[", 1)[0] if isinstance(path, str) else ""
    return _PATH_TO_SECTIONS.get(head, (SECTION_ALL,))


def _convert(gate: str, vs: tuple) -> list:
    out: list = []
    for v in vs:
        for sec in _sections_for_path(v.path):
            out.append(DigestViolation(gate=gate, section=sec, code=v.code, path=v.path, message=v.message))
    return out


def has_forbidden_char(s: Any) -> bool:
    """字串含不可見／不規範字元（非 str → False）：

    - 控制（Cc）、零寬／格式（Cf）、代理（Cs）、私用區（Co）、未指派（Cn）、行／段分隔（Zl／Zp）；
    - 普通空格 U+0020 以外的空白（Zs：NBSP、全形空白 U+3000…；全形空白的決定＝拒收）；
    - **孤立組合記號**：組合記號（M*）出現在字串開頭，或緊接在空白／控制字元之後（沒有基底字元可附著）。
      （`e` + U+0301、emoji + U+FE0F 這種附著在基底字元上的屬正常，不算。）
    """
    if type(s) is not str:
        return False
    prev = None
    for ch in s:
        cat = unicodedata.category(ch)
        if cat in FORBIDDEN_CHAR_CATEGORIES or (cat == "Zs" and ch != ALLOWED_SPACE):
            return True
        if cat in COMBINING_CATEGORIES and (prev is None or prev == ALLOWED_SPACE):
            return True
        prev = ch
    return False


# ── AB-2a 新增檢查（只收緊）────────────────────────────────────────────────
def _own_checks(d: DecisionDigest) -> list:
    out: list = []

    def text_check(path: str, value: Any, section: str) -> None:
        if has_forbidden_char(value):
            out.append(DigestViolation(GATE_AB2A_TEXT, section, "control_chars_in_text", path,
                                       f"文字含控制字元或零寬／格式字元（摘要須逐字引用）：{value!r}"))

    def walk_facts(path: str, facts: Any, section: str) -> None:
        if type(facts) is tuple:
            for i, f in enumerate(facts):
                if type(f) is Fact:
                    text_check(f"{path}[{i}].text", f.text, section)

    def key_check(path: str, key: Any, sections: tuple) -> None:
        if type(key) is not HoldingKey:
            return
        for sec in sections:
            if has_forbidden_char(key.portfolio_id):
                out.append(DigestViolation(GATE_AB2A_TEXT, sec, "bad_portfolio_id_chars", f"{path}.portfolio_id",
                                           f"portfolio_id 含不可見／不規範字元：{key.portfolio_id!r}"))
            if has_forbidden_char(key.symbol) or not _SYMBOL_RE.fullmatch(key.symbol):
                out.append(DigestViolation(GATE_AB2A_TEXT, sec, "bad_symbol", f"{path}.symbol",
                                           f"symbol 不在允許字元集 {SYMBOL_PATTERN!r}：{key.symbol!r}"))

    hs = getattr(d, "holdings", None)
    acts = getattr(d, "actions", None)
    fact_ids: list = []
    action_ids: list = []
    m = getattr(d, "market", None)
    if type(m) is FactSection:
        walk_facts("market.facts", m.facts, SEC_MARKET)
        if type(m.facts) is tuple:
            for i, f in enumerate(m.facts):
                if type(f) is Fact and f.unit is not None and f.unit not in SUPPORTED_UNITS:
                    out.append(DigestViolation(GATE_AB2A_TEXT, SEC_MARKET, "unsupported_unit",
                                               f"market.facts[{i}].unit",
                                               f"市場事實的單位不在摘要支援範圍 {SUPPORTED_UNITS}：{f.unit!r}"))
        fact_ids += [f.fact_id for f in m.facts if type(f) is Fact] if type(m.facts) is tuple else []
    for name in ("tw_trend", "intl_trend", "valuation", "industry"):
        s = getattr(d, name, None)
        if type(s) is DefinitionSection:
            # 定義狀態段的 observations 依 AB-0 不得帶 text，故不需文字檢查（只收集 id）
            if type(s.observations) is tuple:
                fact_ids += [f.fact_id for f in s.observations if type(f) is Fact]
    if type(hs) is HoldingsSection and type(hs.entries) is tuple:
        for i, h in enumerate(hs.entries):
            if type(h) is not HoldingEntry:
                continue
            for sec in (SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN):
                text_check(f"holdings.entries[{i}].strategy_source", h.strategy_source, sec)
            walk_facts(f"holdings.entries[{i}].facts", h.facts, SEC_ACTIONS)
            if type(h.facts) is tuple:
                fact_ids += [f.fact_id for f in h.facts if type(f) is Fact]
    rc = getattr(d, "risk_cap", None)
    if type(rc) is RiskCapSection:
        for name in ("cap_pct", "exposure_lo_pct", "exposure_hi_pct"):
            f = getattr(rc, name, None)
            if type(f) is Fact:
                fact_ids.append(f.fact_id)
    if type(acts) is ActionsSection and type(acts.items) is tuple:
        for i, a in enumerate(acts.items):
            if type(a) is ActionRef:
                text_check(f"actions.items[{i}].text", a.text, SEC_ACTIONS)
                action_ids.append(a.action_id)

    holding_refs: list = []
    if type(hs) is HoldingsSection and type(hs.entries) is tuple:
        for i, h in enumerate(hs.entries):
            if type(h) is HoldingEntry:
                key_check(f"holdings.entries[{i}].key", h.key, (SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN))
                holding_refs.append(holding_ref(h.key.portfolio_id, h.key.symbol))
    if type(acts) is ActionsSection and type(acts.items) is tuple:
        for i, a in enumerate(acts.items):
            if type(a) is ActionRef and a.target is not None:
                key_check(f"actions.items[{i}].target", a.target, (SEC_ACTIONS,))
    for sec_name, sec_obj in (("holdings", hs), ("actions", acts)):
        reason = getattr(sec_obj, "missing_reason", None)
        if (getattr(sec_obj, "availability", None) is Availability.UNAVAILABLE and reason is not None
                and getattr(reason, "value", None) not in INSUFFICIENT_FAMILY_REASONS):
            for sec in ((SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN) if sec_name == "holdings" else (SEC_ACTIONS,)):
                out.append(DigestViolation(GATE_AB2A_TEXT, sec, "unsupported_missing_reason", f"{sec_name}.missing_reason",
                                           f"{sec_name} 的缺值原因必須屬於「資料不足」家族 {INSUFFICIENT_FAMILY_REASONS}"
                                           f"（其餘原因摘要沒有對應句型）：{reason!r}"))
    unlabeled = [f.fact_id for f in (m.facts if type(m) is FactSection and type(m.facts) is tuple else ())
                 if type(f) is Fact and f.fact_id not in FACT_LABELS]
    if len(unlabeled) > 1:
        out.append(DigestViolation(GATE_AB2A_TEXT, SEC_MARKET, "ambiguous_fact_label", "market.facts",
                                   f"多個市場事實沒有專屬標籤（會共用 fallback 標籤而無法區分）：{unlabeled!r}"))
    for kind, ids, path in (("fact_id", fact_ids, "facts"), ("action_id", action_ids, "actions.items")):
        for rid in ids:
            if type(rid) is str and rid.startswith((REF_SECTION_PREFIX, REF_HOLDING_PREFIX)):
                out.append(DigestViolation(GATE_AB2A_REFS, SECTION_ALL, "ref_id_reserved", path,
                                           f"{kind} 不得以保留前綴開頭（evidence 命名空間）：{rid!r}"))
    all_refs = [*fact_ids, *action_ids, *holding_refs]
    for rid in sorted({r for r in all_refs if type(r) is str and all_refs.count(r) > 1}):
        out.append(DigestViolation(GATE_AB2A_REFS, SECTION_ALL, "ref_id_collision", "actions.items",
                                   f"引用 id 不唯一（fact／action／持股的 evidence 指向含糊）：{rid!r}"))
    return out


# ── 各摘要段的可得性（只由資料推導）────────────────────────────────────────
def _combine(avs: list) -> Availability:
    """多個依據的可得性合併：全 AVAILABLE → AVAILABLE；全 UNAVAILABLE → UNAVAILABLE；其餘 PARTIAL。"""
    if all(a is Availability.AVAILABLE for a in avs):
        return Availability.AVAILABLE
    if all(a is Availability.UNAVAILABLE for a in avs):
        return Availability.UNAVAILABLE
    return Availability.PARTIAL


def strategy_entries(digest: DecisionDigest, section: str) -> tuple:
    """持股中策略分類屬於該摘要段（存股／資本利得）的 entries。"""
    want = StrategyType.BUY_AND_HOLD if section == SEC_BUY_AND_HOLD else StrategyType.CAPITAL_GAIN
    return tuple(h for h in digest.holdings.entries if h.strategy is want)


def section_availability(digest: DecisionDigest, section: str) -> Availability:
    """單一摘要段的可得性（假設 digest 已通過 `assess_digest`）。

    - 市場：market／risk_cap／tw_trend／intl_trend／valuation 五個依據合併（定義狀態段恆 UNAVAILABLE，
      故市場段至多 PARTIAL）；
    - 產業：industry 段（恆 UNAVAILABLE）；
    - 存股／資本利得：持股讀不到 → UNAVAILABLE；沒有任何該策略的 entry → UNAVAILABLE（尚未設定投資策略分類）；
      有該策略的 entry → 至多 PARTIAL（基本面／配置判定尚未接線，Digest 沒有對應欄位）；
    - 本期行動：actions 段自己的可得性。
    """
    if section == SEC_MARKET:
        return _combine([digest.market.availability, digest.risk_cap.availability,
                         digest.tw_trend.availability, digest.intl_trend.availability,
                         digest.valuation.availability])
    if section == SEC_INDUSTRY:
        return digest.industry.availability
    if section in (SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN):
        if digest.holdings.availability is Availability.UNAVAILABLE:
            return Availability.UNAVAILABLE
        return Availability.PARTIAL if strategy_entries(digest, section) else Availability.UNAVAILABLE
    if section == SEC_ACTIONS:
        return digest.actions.availability
    raise ValueError(f"未知的摘要段：{section!r}")


def derive_state(availabilities: tuple) -> SummaryState:
    """由各段可得性推導整體狀態（INVALID 不在此：它來自契約違規）。"""
    avs = [a for _, a in availabilities]
    if avs and all(a is Availability.AVAILABLE for a in avs):
        return SummaryState.VALID
    if not avs or all(a is Availability.UNAVAILABLE for a in avs):
        return SummaryState.UNAVAILABLE
    return SummaryState.PARTIAL


def assess_digest(digest: Any) -> DigestAssessment:
    """純函式：Digest 自身檢查＋四態降級。**任何輸入都不 raise**。"""
    if type(digest) is not DecisionDigest:
        v = DigestViolation(GATE_AB0_CONTRACT, SECTION_ALL, "type", "digest",
                            f"必須恰好是 DecisionDigest：{type(digest).__name__}")
        return DigestAssessment(SummaryState.INVALID, (v,), (SECTION_ALL,), (GATE_AB0_CONTRACT,), ())
    vs: list = []
    vs += _convert(GATE_AB0_CONTRACT, tuple(validate(digest)))
    vs += _convert(GATE_AB1_RULE_ID, tuple(validate_rule_ids(digest)))
    vs += _convert(GATE_AB1_ACTION_ORDER, tuple(validate_action_order(digest)))
    if not vs:  # 前三者全過才檢查自有項（自有項會走訪內部結構，需先確保結構可檢查）
        vs += _own_checks(digest)
    if vs:
        secs = tuple(k for k in (*SECTION_KEYS, SECTION_ALL) if any(v.section == k for v in vs))
        gates = tuple(g for g in DIGEST_GATES_ORDER if any(v.gate == g for v in vs))
        return DigestAssessment(SummaryState.INVALID, tuple(vs), secs, gates, ())
    avail = tuple((k, section_availability(digest, k)) for k in SECTION_KEYS)
    return DigestAssessment(derive_state(avail), (), (), (), avail)


__all__ = [
    "SECTION_ALL", "SummaryState", "DigestViolation", "DigestAssessment", "has_forbidden_char",
    "strategy_entries", "section_availability", "derive_state", "assess_digest", "holding_ref",
]
