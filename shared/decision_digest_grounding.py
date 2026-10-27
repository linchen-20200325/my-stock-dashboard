"""shared/decision_digest_grounding.py — 摘要的 grounding 驗證 G1～G6（AB-2a；L0 純函式，**無 AI**）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
`docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §2.4 的 G1～G6，以規則式程式執行（不由 LLM 驗 LLM）。
輸入：(1) 一份 `DecisionDigest`；(2) 一份**結構化摘要** `SummaryDraft`。
輸出：`GroundingReport`。規則式摘要（本批）與未來 AI 輸出（AB-2b）走同一個檢查器。

═══ 主防線：句型白名單（fail-closed；取代「黑名單字眼＋quote 豁免」） ═══════════
一句話 `SummarySentence` ＝ **segment 序列**，每個 segment 只能是：
- `Lit(template_id)`：`terms.TEMPLATES` 的固定模板片段（以 id 引用；沒有任意字串的位置）；
- `Ref(ref_id, field)`：對某個 Digest 項目的**欄位展開**（文字／數值字面／資料日／代號…由本檔從 Digest 取出；
  呼叫端不能提供內容）。
整句還必須吻合 `SHAPES` 中**唯一**一個句型的骨架（模板與欄位的排列、每個 slot 的項目種類），並通過該句型的
**前置條件**（例如「缺資料」句型只能用在 status 真的是 missing 的事實上；行動句型只能用在 Digest `actions[]` 內的行動上）。
同一個 slot 的所有 segment 必須指向同一個項目 —— 每個引用文字／數字都屬於它自己綁定的項目，**不池化**；
也沒有「把任意 ref 掛在句上搭便車」的位置。
結果：同形異字、簡體、同義詞、中文數字、否定／矛盾、夾帶結論、標示語子字串偽造、行動句加字／換代號／換順序／
漏項／重複，在結構上沒有表達的位置（不是靠字眼清單擋）。
⚠️ 字眼清單（`terms.WASHING_*` 等）降級為 **L0 模板與標籤的建置期 lint**（測試保證模板不含那些字眼），不再是執行期依據。

═══ 輸出格式契約（刻意最小；AB-2b 不得因它而被迫採用某種 prompt／傳輸） ═══════════
    SummaryDraft(sections=(SummarySection(key, sentences=(SummarySentence(segments=(Lit|Ref, ...)), ...)), ...))
本檔**不**定義 AI prompt、傳輸、金鑰、用量、解析器。⚠️ **AB-2b 要上線，AI 必須以「選句型＋填 slot（Ref）」的受限格式輸出**；
自由文字的 AI 輸出不可能通過本檢查器（這是設計，不是缺陷）。無法解析的輸入（None、dict、字串、子類別…）一律視為
驗證失敗（`structural_failure=True`）。

═══ 引用 id 空間（Ref.ref_id 只能指向這些） ═══════════════════════════════════
Digest 內的 `fact_id`、`action_id`；`section:<digest 段名>`；`holding:<portfolio_id>:<symbol>`。
欄位展開的限制：Risk Cap 區段與「僅供參考」的趨勢觀測值**整個受限**（不能展開值、資料日或文字）；
`strategy_source`（使用者自由文字）**沒有任何欄位可展開**（不得進摘要）。

═══ G1～G6 的對映 ═══════════════════════════════════════════════════════
G1 引用封閉   ref 必須在 Digest 內；欄位必須是該項目允許展開的（`ref_not_in_digest`／`field_not_quotable`／`slot_ref_mismatch`）。
G2 數字一致   數字只能來自 `value`（`number_literal`）、`as_of`、`count` 的展開；單位由**模板**決定（`%` 為獨立模板，
              項目的 unit 必須吻合：`unit_mismatch`）；Risk Cap／觀測值數字受限（`restricted_value`）。
G3 狀態不可升  句型前置條件綁定項目狀態：ok／stale／proxy／missing／failed／invalid 各有固定句型，用錯即
              `status_mismatch`；標示語由模板產生，不做「子字串存在」判斷。
G4 不新增結論  句型不在白名單（`shape_not_whitelisted`／`template_not_whitelisted`）；行動段必須與 Digest `actions[]`
              **一對一、同順序、無重複、無遺漏**（`action_list_mismatch`）；行動句＝代號（取自 `ActionRef.target`）＋
              `ActionRef.text` 逐字展開，不得加前後字。
G5 段落完整   五段齊全、唯一、固定順序；每段至少一句；對 Digest 中非 ok 的依據都須有對應句型（`section_basis`）；
              句型須屬於該段（`shape_out_of_section`）；段內不得有重複句。
G6 依據可回溯 沒有任何 `Ref` segment 的句子**丟棄**（記為 G6 違規，不使整份失敗）。

═══ accepted／usable／surviving 的語意（寫死） ═══════════════════════════════
- `accepted`：沒有任何 STRUCT／DIGEST／G1～G5 違規（G6 丟棄不算）。
- `surviving`：丟棄 G6 句子之後的摘要（結構失敗或 Digest 不合規時為 None）。**消費端只能使用 `surviving`，
  不得使用原始 draft** —— 有 G6 丟棄時原始 draft 含未綁定依據的句子。
- `usable`＝`accepted` 且 `surviving` 非 None。`clean`＝`usable` 且沒有任何丟棄（`surviving == draft`）。
- `SummaryResult` 只接受 `clean` 的內容（建構時重跑本檢查器並與 Digest 綁定）。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫與 `shared.*`；零 I/O、零 streamlit、零 `src.*`。
"""
from __future__ import annotations

import math
import numbers
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Optional

from shared.decision_digest import (
    AiParticipation, Availability, DataStatus, DecisionDigest, Fact, MissingReason,
)
from shared.decision_digest_terms import (
    FIELD_AS_OF, FIELD_BIND, FIELD_COUNT, FIELD_LABEL, FIELD_MARKER, FIELD_REASON, FIELD_STRATEGY, FIELD_SYMBOL,
    DIGEST_SECTIONS, FIELD_TEXT, FIELD_VALUE, FIELD_WORDING, FACT_LABEL_FALLBACK, FACT_LABELS, FORBIDDEN_CHAR_CATEGORIES,
    GATE_DIGEST, GATE_G1, GATE_G2, GATE_G3, GATE_G4, GATE_G5, GATE_G6, GATE_STRUCT, GROUNDING_GATES,
    LABEL_ALL_SECTIONS, MARK_NOT_DEFINED, MARK_NOT_WIRED, MARK_RESEARCH_ONLY, MISSING_REASON_LABEL_UNKNOWN,
    MISSING_REASON_LABELS, REF_HOLDING_PREFIX, REF_SECTION_PREFIX, RISK_CAP_HIDDEN_WORDING, SEC_ACTIONS,
    SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN, SEC_INDUSTRY, SEC_MARKET, SECTION_KEYS, SECTION_LABELS,
    SECTION_REF_LABELS, TEMPLATES, TPL_ACT_NONE, TPL_ACT_STALE_OPEN, TPL_ACT_UNAVAILABLE_OPEN,
    TPL_CLOSE, TPL_COLON, TPL_DATE_OPEN, TPL_ENTRY_TAIL, TPL_GLYPH, TPL_HOLDINGS_UNAVAILABLE_MID,
    TPL_INVALID_TAIL, TPL_MISSING_OPEN, TPL_PCT, TPL_PROXY_TAIL, TPL_SECTION_LABEL, TPL_STALE_DATE_OPEN,
    TPL_STRATEGY_IS, TPL_STRATEGY_UNSET_TAIL, TPL_UNDETERMINED_TAIL, TPL_UNKEYED_OPEN, TPL_UNKEYED_TAIL,
)
from shared.decision_digest_validator import (
    SECTION_ALL, DigestAssessment, SummaryState, assess_digest, strategy_entries,
)


# ══════════════════════════════════════════════════════════════════════
# 結構化摘要型別（最小格式契約）
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Lit:
    """固定模板片段（`terms.TEMPLATES` 的 id）。沒有承載任意字串的欄位。"""
    template_id: str


@dataclass(frozen=True)
class Ref:
    """對某個 Digest 項目的欄位展開（`terms.FIELDS` 之一）。內容由 checker 從 Digest 取出。"""
    ref_id: str
    field: str


@dataclass(frozen=True)
class SummarySentence:
    segments: tuple = ()

    @property
    def evidence_refs(self) -> tuple:
        """這句話綁定的項目（`Ref` segment 的 ref_id，去重、保序）。沒有任何 `Ref` → 空 tuple（G6 丟棄）。"""
        seen: list = []
        for g in self.segments if type(self.segments) is tuple else ():
            if type(g) is Ref and type(g.ref_id) is str and g.ref_id not in seen:
                seen.append(g.ref_id)
        return tuple(seen)


@dataclass(frozen=True)
class SummarySection:
    key: str
    sentences: tuple = ()


@dataclass(frozen=True)
class SummaryDraft:
    sections: tuple = ()


@dataclass(frozen=True)
class GroundingViolation:
    gate: str                    # G1～G6／STRUCT／DIGEST
    section: str                 # 段鍵；不屬任何段 → ""
    sentence_index: int          # 句序；不屬任何句 → -1
    code: str
    message: str


@dataclass(frozen=True)
class GroundingReport:
    accepted: bool               # 無 STRUCT／DIGEST／G1～G5 違規（G6 丟棄不算）
    violations: tuple
    dropped: tuple               # ((段鍵, 句序), ...) —— G6 丟棄
    failed_gates: tuple          # 出現過違規的 G 閘門（固定順序；含 G6）
    structural_failure: bool
    digest_invalid: bool
    surviving: Optional[SummaryDraft]   # 丟棄 G6 句子後的摘要；結構失敗或 Digest 不合規 → None

    @property
    def usable(self) -> bool:
        """可用：`accepted` 且 `surviving` 非 None。消費端只能用 `surviving`，不得用原始 draft。"""
        return self.accepted and self.surviving is not None

    @property
    def clean(self) -> bool:
        """乾淨：可用且沒有任何丟棄（`surviving` 與原始 draft 完全相同）。"""
        return self.usable and not self.dropped

    @property
    def passed_gates(self) -> tuple:
        """沒有違規的 G 閘門（結構失敗／Digest 不合規時為空 —— 沒檢查完就不宣稱通過）。"""
        if self.structural_failure or self.digest_invalid:
            return ()
        return tuple(g for g in GROUNDING_GATES if g not in self.failed_gates)


# ══════════════════════════════════════════════════════════════════════
# 數字字面
# ══════════════════════════════════════════════════════════════════════
def number_literal(value: Any) -> str:
    """數值 → 唯一的「字面」形式。整數 → `str(int)`；浮點 → 最短往返固定小數（不用科學記號、不補零、不截斷）。
    非有限／非實數／bool → ValueError。"""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"不是實數：{value!r}")
    if isinstance(value, numbers.Integral):
        return str(int(value))
    f = float(value)
    if not math.isfinite(f):
        raise ValueError(f"非有限數值：{value!r}")
    return format(Decimal(repr(f)), "f")


# ══════════════════════════════════════════════════════════════════════
# 引用項索引與欄位展開
# ══════════════════════════════════════════════════════════════════════
KIND_FACT, KIND_ACTION, KIND_HOLDING, KIND_SECTION = "fact", "action", "holding", "section"
GROUP_MARKET, GROUP_HOLDING, GROUP_RESTRICTED = "market", "holding", "restricted"


@dataclass(frozen=True)
class RefInfo:
    ref_id: str
    kind: str
    obj: Any = None              # Fact／ActionRef／HoldingEntry／None（section）
    group: str = ""              # fact 的來源群：market／holding／restricted（Risk Cap 與趨勢觀測值）
    name: str = ""               # section 的 Digest 段名


def holding_ref(portfolio_id: str, symbol: str) -> str:
    return f"{REF_HOLDING_PREFIX}{portfolio_id}:{symbol}"


def section_ref(name: str) -> str:
    if name not in DIGEST_SECTIONS:
        raise ValueError(f"未知的 Digest 段名：{name!r}")
    return REF_SECTION_PREFIX + name


def build_ref_index(digest: DecisionDigest) -> dict:
    """引用 id → `RefInfo`（假設 digest 已通過 `assess_digest`）。"""
    idx: dict = {}
    for f in digest.market.facts:
        idx[f.fact_id] = RefInfo(f.fact_id, KIND_FACT, f, GROUP_MARKET)
    for name in ("tw_trend", "intl_trend"):          # 均線等「僅供參考」的觀測值：整個受限
        for f in getattr(digest, name).observations:
            idx[f.fact_id] = RefInfo(f.fact_id, KIND_FACT, f, GROUP_RESTRICTED)
    for f in digest.risk_cap.facts:                  # Risk Cap 獨立數字未核准顯示（DEC-081 Q2-2）：整個受限
        idx[f.fact_id] = RefInfo(f.fact_id, KIND_FACT, f, GROUP_RESTRICTED)
    for h in digest.holdings.entries:
        for f in h.facts:
            idx[f.fact_id] = RefInfo(f.fact_id, KIND_FACT, f, GROUP_HOLDING)
        rid = holding_ref(h.key.portfolio_id, h.key.symbol)
        idx[rid] = RefInfo(rid, KIND_HOLDING, h)
    for a in digest.actions.items:
        idx[a.action_id] = RefInfo(a.action_id, KIND_ACTION, a)
    for name in DIGEST_SECTIONS:
        rid = REF_SECTION_PREFIX + name
        idx[rid] = RefInfo(rid, KIND_SECTION, None, name=name)
    return idx


def _reason_label(reason: Any) -> str:
    return MISSING_REASON_LABELS.get(getattr(reason, "value", None), MISSING_REASON_LABEL_UNKNOWN)


def _section_marker(digest: DecisionDigest, name: str) -> Optional[str]:
    if name == "valuation":
        return MARK_RESEARCH_ONLY
    if name in ("tw_trend", "intl_trend", "industry"):
        sec = getattr(digest, name)
        return MARK_NOT_WIRED if sec.missing_reason is MissingReason.NOT_WIRED else MARK_NOT_DEFINED
    return None


def expand(digest: DecisionDigest, info: RefInfo, fld: str) -> tuple:
    """欄位展開。回傳 (字串 | None, 失敗閘門, 失敗代碼)。字串非 None ⇒ 展開成功。

    展開成功的字串**只可能**來自 Digest 或 `terms` 的常數 —— 呼叫端無從提供內容。
    """
    bad = (None, GATE_G1, "field_not_quotable")
    restricted = (None, GATE_G2, "restricted_value")
    k = info.kind
    if k == KIND_FACT:
        f: Fact = info.obj
        if info.group == GROUP_RESTRICTED:
            return restricted if fld in (FIELD_VALUE, FIELD_TEXT, FIELD_AS_OF) else bad
        if info.group == GROUP_HOLDING:                 # 持股事實：只開放資料日（行動句型的 stale 揭露用）；文字由 ActionRef 展開
            if fld == FIELD_AS_OF and f.provenance.as_of is not None:
                return f.provenance.as_of.isoformat(), None, None
            return bad
        if fld == FIELD_LABEL:
            return FACT_LABELS.get(f.fact_id, FACT_LABEL_FALLBACK), None, None
        if fld == FIELD_TEXT:
            return (f.text, None, None) if f.text is not None else bad
        if fld == FIELD_VALUE:
            if f.value is None:
                return bad
            return number_literal(f.value), None, None      # 假設 Digest 已通過 assess（值必為有限實數）；否則 ValueError（Fail Loud）
        if fld == FIELD_AS_OF:
            return (f.provenance.as_of.isoformat(), None, None) if f.provenance.as_of is not None else bad
        if fld == FIELD_REASON:
            return (_reason_label(f.missing_reason), None, None) if f.missing_reason is not None else bad
        return bad
    if k == KIND_ACTION:
        a = info.obj
        if fld == FIELD_TEXT:
            return a.text, None, None
        if fld == FIELD_SYMBOL:
            return (a.target.symbol, None, None) if a.target is not None else bad
        return bad
    if k == KIND_HOLDING:
        h = info.obj
        if fld == FIELD_SYMBOL:
            return h.key.symbol, None, None
        if fld == FIELD_STRATEGY:
            return h.strategy.value, None, None
        return bad                                      # ⛔ strategy_source 沒有任何欄位可展開（使用者自由文字）
    # section
    n = info.name
    if fld == FIELD_BIND:
        return "", None, None
    if fld == FIELD_LABEL:
        return (SECTION_REF_LABELS[n], None, None) if n in SECTION_REF_LABELS else bad
    if fld == FIELD_MARKER:
        m = _section_marker(digest, n)
        return (m, None, None) if m is not None else bad
    if fld == FIELD_WORDING:
        return (RISK_CAP_HIDDEN_WORDING, None, None) if n == "risk_cap" else bad
    if fld == FIELD_COUNT:
        return (str(digest.holdings.unkeyed_count), None, None) if n == "holdings" else bad
    if fld == FIELD_REASON:
        if n == "holdings":
            return _reason_label(digest.holdings.missing_reason), None, None
        if n == "actions":
            return _reason_label(digest.actions.missing_reason), None, None
    return bad


# ══════════════════════════════════════════════════════════════════════
# 句型白名單
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Ctx:
    digest: DecisionDigest
    index: dict
    section: str
    slots: dict                  # slot 序號 → RefInfo


@dataclass(frozen=True)
class Shape:
    sid: str
    sections: frozenset
    skeleton: tuple              # ("L", 模板id) | ("R", slot, 項目種類, 欄位)
    pre: Callable                # (Ctx) -> None | (閘門, 代碼, 訊息)

    @property
    def signature(self) -> tuple:
        return tuple(("L", e[1]) if e[0] == "L" else ("R", e[2], e[3]) for e in self.skeleton)


def _L(tpl: str) -> tuple:
    return ("L", tpl)


def _R(slot: int, kind: str, fld: str) -> tuple:
    return ("R", slot, kind, fld)


def _status_pre(group: str, status: DataStatus, *, unit: Optional[str] = None, check_unit: bool = False) -> Callable:
    def pre(c: Ctx):
        info = c.slots[0]
        f: Fact = info.obj
        if info.group != group:
            return (GATE_G4, "wrong_group", "此句型只能用在市場事實上")
        if f.status is not status:
            return (GATE_G3, "status_mismatch",
                    f"項目 status={f.status.value}，句型要求 {status.value}（狀態不得升級／降級）")
        if check_unit and f.unit != unit:
            return (GATE_G2, "unit_mismatch", f"單位由模板決定：項目 unit={f.unit!r}，句型要求 {unit!r}")
        return None
    return pre


def _section_name_pre(*names: str) -> Callable:
    def pre(c: Ctx):
        if c.slots[0].name not in names:
            return (GATE_G4, "wrong_section_ref", f"此句型只能引用 {names}")
        return None
    return pre


def _section_pre(sec_key: str, name: str, cond: Callable) -> Callable:
    def pre(c: Ctx):
        if c.slots[0].name != name:
            return (GATE_G4, "wrong_section_ref", f"此句型只能引用 section:{name}")
        if not cond(c.digest):
            return (GATE_G3, "precondition_failed", "Digest 狀態不符此句型的前置條件（不得用於未缺資料的項目）")
        return None
    return pre


def _entry_pre(c: Ctx):
    if c.digest.holdings.availability is Availability.UNAVAILABLE:
        return (GATE_G3, "precondition_failed", "持股讀不到時不得列出個別持股")
    if c.slots[0].obj not in strategy_entries(c.digest, c.section):
        return (GATE_G4, "wrong_strategy", "持股的策略分類不屬於此段")
    return None


def oldest_stale_evidence(digest: DecisionDigest, index: dict, a: Any) -> Optional[str]:
    """行動證據中**最舊**的 stale 事實 id（確定性：as_of、再依 evidence 順序）；沒有 → None。"""
    best = None
    for pos, rid in enumerate(a.evidence_refs):
        info = index.get(rid)
        if (info is not None and info.kind == KIND_FACT and info.group != GROUP_RESTRICTED
                and info.obj.status is DataStatus.STALE):
            key = (info.obj.provenance.as_of, pos)
            if best is None or key < best[0]:
                best = (key, rid)
    return best[1] if best else None


def _action_pre(with_target: bool, stale: bool) -> Callable:
    def pre(c: Ctx):
        a = c.slots[0].obj
        if (a.target is not None) is not with_target:
            return (GATE_G4, "target_mismatch", "行動句型必須與 ActionRef.target 是否存在一致（代號只能取自 target）")
        want = oldest_stale_evidence(c.digest, c.index, a)
        if stale:
            if want is None or c.slots[1].ref_id != want:
                return (GATE_G3, "stale_evidence_mismatch", "stale 句型的第二個項目必須是該行動最舊的 stale 證據")
        elif want is not None:
            return (GATE_G3, "stale_evidence_mismatch", "行動有 stale 證據時必須使用 stale 句型（不得隱藏過期）")
        return None
    return pre


def _build_shapes() -> tuple:
    out: list = []
    S_MKT = frozenset({SEC_MARKET})
    heads = {"text": [(_R(0, KIND_FACT, FIELD_TEXT),), None],
             "value": [(_R(0, KIND_FACT, FIELD_VALUE),), None],
             "value_pct": [(_R(0, KIND_FACT, FIELD_VALUE), _L(TPL_PCT)), "%"]}
    for status, tails in ((DataStatus.OK, (_L(TPL_DATE_OPEN), _R(0, KIND_FACT, FIELD_AS_OF), _L(TPL_CLOSE))),
                          (DataStatus.STALE, (_L(TPL_STALE_DATE_OPEN), _R(0, KIND_FACT, FIELD_AS_OF), _L(TPL_CLOSE))),
                          (DataStatus.PROXY, (_L(TPL_PROXY_TAIL),))):
        for hk, (body, unit) in heads.items():
            skel = (_R(0, KIND_FACT, FIELD_LABEL), _L(TPL_COLON), *body, *tails)
            pre = _status_pre(GROUP_MARKET, status, unit=unit, check_unit=hk != "text")
            out.append(Shape(f"fact_{hk}_{status.value}", S_MKT, skel, pre))
    # 缺值／失敗：兩種 status 共用一個句型
    miss_pre = _status_pre(GROUP_MARKET, DataStatus.MISSING)

    def missing_pre(c: Ctx):
        f: Fact = c.slots[0].obj
        if f.status is DataStatus.FAILED and c.slots[0].group == GROUP_MARKET:
            return None
        return miss_pre(c)
    out.append(Shape("fact_missing", S_MKT,
                     (_L(TPL_GLYPH), _R(0, KIND_FACT, FIELD_LABEL), _L(TPL_MISSING_OPEN),
                      _R(0, KIND_FACT, FIELD_REASON), _L(TPL_CLOSE)), missing_pre))
    out.append(Shape("fact_invalid", S_MKT,
                     (_L(TPL_GLYPH), _R(0, KIND_FACT, FIELD_LABEL), _L(TPL_INVALID_TAIL)),
                     _status_pre(GROUP_MARKET, DataStatus.INVALID)))
    out.append(Shape("risk_wording", S_MKT, (_R(0, KIND_SECTION, FIELD_WORDING),), _section_name_pre("risk_cap")))
    # 趨勢／合理區間／產業：未定義
    und_skel = (_L(TPL_GLYPH), _R(0, KIND_SECTION, FIELD_LABEL), _L(TPL_COLON), _R(0, KIND_SECTION, FIELD_MARKER),
                _L(TPL_UNDETERMINED_TAIL))

    def undefined_pre(c: Ctx):
        names = ("industry",) if c.section == SEC_INDUSTRY else ("tw_trend", "intl_trend", "valuation")
        return _section_name_pre(*names)(c)
    out.append(Shape("section_undefined", frozenset({SEC_MARKET, SEC_INDUSTRY}), und_skel, undefined_pre))
    # 存股／資本利得
    for sk in (SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN):
        sset = frozenset({sk})
        lab = TPL_SECTION_LABEL[sk]
        out.append(Shape(f"holdings_unavailable:{sk}", sset,
                         (_L(TPL_GLYPH), _L(lab), _L(TPL_HOLDINGS_UNAVAILABLE_MID),
                          _R(0, KIND_SECTION, FIELD_REASON), _L(TPL_CLOSE)),
                         _section_pre(sk, "holdings", lambda d: d.holdings.availability is Availability.UNAVAILABLE)))
        out.append(Shape(f"strategy_unset:{sk}", sset,
                         (_L(TPL_GLYPH), _L(lab), _L(TPL_STRATEGY_UNSET_TAIL), _R(0, KIND_SECTION, FIELD_BIND)),
                         _section_pre(sk, "holdings", lambda d, sk=sk: (
                             d.holdings.availability is not Availability.UNAVAILABLE
                             and not strategy_entries(d, sk)))))
    out.append(Shape("strategy_entry", frozenset({SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN}),
                     (_R(0, KIND_HOLDING, FIELD_SYMBOL), _L(TPL_STRATEGY_IS), _R(0, KIND_HOLDING, FIELD_STRATEGY),
                      _L(TPL_ENTRY_TAIL)), _entry_pre))
    out.append(Shape("holdings_unkeyed", frozenset({SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN}),
                     (_L(TPL_UNKEYED_OPEN), _R(0, KIND_SECTION, FIELD_COUNT), _L(TPL_UNKEYED_TAIL)),
                     _section_pre("", "holdings", lambda d: d.holdings.unkeyed_count > 0)))
    # 本期行動
    S_ACT = frozenset({SEC_ACTIONS})
    out.append(Shape("actions_unavailable", S_ACT,
                     (_L(TPL_ACT_UNAVAILABLE_OPEN), _R(0, KIND_SECTION, FIELD_REASON), _L(TPL_CLOSE)),
                     _section_pre(SEC_ACTIONS, "actions", lambda d: d.actions.availability is Availability.UNAVAILABLE)))
    out.append(Shape("actions_none", S_ACT, (_L(TPL_ACT_NONE), _R(0, KIND_SECTION, FIELD_BIND)),
                     _section_pre(SEC_ACTIONS, "actions", lambda d: (
                         d.actions.availability is Availability.AVAILABLE and not d.actions.items))))
    for with_target in (True, False):
        head = ((_R(0, KIND_ACTION, FIELD_SYMBOL), _L(TPL_COLON)) if with_target else ()) + (_R(0, KIND_ACTION, FIELD_TEXT),)
        out.append(Shape("action_item" if with_target else "action_item_nt", S_ACT, head, _action_pre(with_target, False)))
        out.append(Shape("action_item_stale" if with_target else "action_item_nt_stale", S_ACT,
                         head + (_L(TPL_ACT_STALE_OPEN), _R(1, KIND_FACT, FIELD_AS_OF), _L(TPL_CLOSE)),
                         _action_pre(with_target, True)))
    return tuple(out)


SHAPES: tuple = _build_shapes()
#: 骨架簽名 → 句型（簽名必須唯一：`tests` 的 `test_every_shape_signature_is_unique...` 鎖死）。
_SHAPE_BY_SIG: dict = {_s.signature: _s for _s in SHAPES}
ACTION_SHAPE_IDS: frozenset = frozenset(s.sid for s in SHAPES if s.sid.startswith("action_item"))


# ══════════════════════════════════════════════════════════════════════
# 渲染（展開成文字；呼叫端只能拿到由 Digest／模板展開出來的字串）
# ══════════════════════════════════════════════════════════════════════
def render_sentence(digest: DecisionDigest, sentence: SummarySentence, index: Optional[dict] = None) -> str:
    """把（已通過 `check_summary` 的）句子展開成文字。未通過者 → ValueError（不渲染不可信內容）。"""
    idx = index if index is not None else build_ref_index(digest)
    parts: list = []
    for g in sentence.segments:
        if type(g) is Lit:
            parts.append(TEMPLATES[g.template_id])
        else:
            text, gate, code = expand(digest, idx[g.ref_id], g.field)
            if text is None:
                raise ValueError(f"無法展開 {g.ref_id!r}.{g.field}：[{gate}/{code}]")
            parts.append(text)
    return "".join(parts)


def render_draft(digest: DecisionDigest, draft: SummaryDraft) -> tuple:
    """((段鍵, (句子文字, ...)), ...)。只應對 `clean` 的 draft 使用。"""
    idx = build_ref_index(digest)
    return tuple((s.key, tuple(render_sentence(digest, x, idx) for x in s.sentences)) for s in draft.sections)


# ══════════════════════════════════════════════════════════════════════
# 結構檢查（無法解析＝驗證失敗）
# ══════════════════════════════════════════════════════════════════════
def _v(gate: str, section: str, idx: int, code: str, message: str) -> GroundingViolation:
    return GroundingViolation(gate=gate, section=section, sentence_index=idx, code=code, message=message)


def _ref_problem(r: Any) -> Optional[str]:
    if type(r) is not str or r == "":
        return "ref_id 必須是非空 str"
    if any(ch.isspace() for ch in r):
        return "ref_id 不得含空白"
    if any(unicodedata.category(ch) in FORBIDDEN_CHAR_CATEGORIES for ch in r):
        return "ref_id 不得含控制或零寬字元"
    return None


def _structure(draft: Any) -> list:
    if type(draft) is not SummaryDraft:
        return [_v(GATE_STRUCT, "", -1, "type", f"摘要必須恰好是 SummaryDraft：{type(draft).__name__}")]
    if type(draft.sections) is not tuple:
        return [_v(GATE_STRUCT, "", -1, "sections_not_tuple", "sections 必須是 tuple")]
    out: list = []
    for si, s in enumerate(draft.sections):
        if type(s) is not SummarySection:
            out.append(_v(GATE_STRUCT, "", -1, "section_type", f"sections[{si}] 必須恰好是 SummarySection"))
            continue
        if type(s.key) is not str:
            out.append(_v(GATE_STRUCT, "", -1, "section_key_type", f"sections[{si}].key 必須是 str"))
        key = str(s.key)
        if type(s.sentences) is not tuple:
            out.append(_v(GATE_STRUCT, key, -1, "sentences_not_tuple", "sentences 必須是 tuple"))
            continue
        for i, t in enumerate(s.sentences):
            if type(t) is not SummarySentence:
                out.append(_v(GATE_STRUCT, key, i, "sentence_type", "句子必須恰好是 SummarySentence"))
                continue
            if type(t.segments) is not tuple:
                out.append(_v(GATE_STRUCT, key, i, "segments_not_tuple", "segments 必須是 tuple"))
                continue
            for g in t.segments:
                if type(g) is Lit:
                    if type(g.template_id) is not str:
                        out.append(_v(GATE_STRUCT, key, i, "template_id_type", "template_id 必須是 str"))
                elif type(g) is Ref:
                    p = _ref_problem(g.ref_id)
                    if p:
                        out.append(_v(GATE_STRUCT, key, i, "bad_ref", f"{p}：{g.ref_id!r}"))
                    if type(g.field) is not str:
                        out.append(_v(GATE_STRUCT, key, i, "field_type", "field 必須是 str"))
                else:
                    out.append(_v(GATE_STRUCT, key, i, "segment_type",
                                  f"segment 必須恰好是 Lit 或 Ref（沒有任意字串的位置）：{type(g).__name__}"))
    return out


# ══════════════════════════════════════════════════════════════════════
# 單句檢查
# ══════════════════════════════════════════════════════════════════════
def _check_sentence(sent: SummarySentence, section: str, i: int, digest: DecisionDigest, index: dict) -> tuple:
    """回傳 (違規 list, 吻合的 Shape | None, slots dict)。"""
    out: list = []
    for g in sent.segments:
        if type(g) is Lit and g.template_id not in TEMPLATES:
            out.append(_v(GATE_G4, section, i, "template_not_whitelisted", f"模板不在白名單：{g.template_id!r}"))
        if type(g) is Ref and g.ref_id not in index:
            out.append(_v(GATE_G1, section, i, "ref_not_in_digest", f"ref 不在 Digest 的引用 id 空間：{g.ref_id!r}"))
    if out:
        return out, None, {}
    sig = tuple(("L", g.template_id) if type(g) is Lit else ("R", index[g.ref_id].kind, g.field) for g in sent.segments)
    shape = _SHAPE_BY_SIG.get(sig)
    if shape is None:
        return [_v(GATE_G4, section, i, "shape_not_whitelisted", "句子的骨架不吻合任何白名單句型（fail-closed）")], None, {}
    slots: dict = {}
    for el, g in zip(shape.skeleton, sent.segments):
        if el[0] != "R":
            continue
        info = index[g.ref_id]
        if slots.setdefault(el[1], info).ref_id != info.ref_id:
            out.append(_v(GATE_G1, section, i, "slot_ref_mismatch",
                          f"同一個 slot 的 segment 必須指向同一個項目：{slots[el[1]].ref_id!r} ≠ {info.ref_id!r}"))
        text, gate, code = expand(digest, info, g.field)
        if text is None:
            out.append(_v(gate, section, i, code, f"{g.ref_id!r} 不能展開欄位 {g.field!r}"))
    if section not in shape.sections:
        out.append(_v(GATE_G4, section, i, "shape_out_of_section", f"句型 {shape.sid!r} 不屬於「{section}」段"))
    fail = shape.pre(Ctx(digest, index, section, slots))     # 前置條件一律檢查（與欄位展開失敗並列回報）
    if fail is not None:
        out.append(_v(fail[0], section, i, fail[1], fail[2]))
    return out, shape, slots


# ══════════════════════════════════════════════════════════════════════
# G5 的「必須明示」清單
# ══════════════════════════════════════════════════════════════════════
def _fact_shape_ids(status: DataStatus) -> tuple:
    if status is DataStatus.STALE:
        return tuple(f"fact_{k}_stale" for k in ("text", "value", "value_pct"))
    if status is DataStatus.PROXY:
        return tuple(f"fact_{k}_proxy" for k in ("text", "value", "value_pct"))
    if status is DataStatus.INVALID:
        return ("fact_invalid",)
    return ("fact_missing",)


def section_basis(digest: DecisionDigest, key: str) -> tuple:
    """G5 的「必須明示」清單：((引用 id, 可接受的句型 id tuple), ...)。

    只列「Digest 中非 ok 的依據」：缺資料／過期／代理的市場事實、未定義的趨勢／產業／合理區間、Risk Cap 卡面措辭、
    持股讀不到／未帶鍵持股／尚未設定策略分類／已分類持股（判定未接線）、行動不可得／規則層未產出行動。全部由 Digest 推導。
    行動段不列在此（見下方註解）：各項行動由 `action_list_mismatch`（一對一）檢查。
    """
    out: list = []
    if key == SEC_MARKET:
        for f in digest.market.facts:
            if f.status is not DataStatus.OK:
                out.append((f.fact_id, _fact_shape_ids(f.status)))
        for name in ("tw_trend", "intl_trend", "valuation"):
            out.append((section_ref(name), ("section_undefined",)))
        out.append((section_ref("risk_cap"), ("risk_wording",)))
    elif key == SEC_INDUSTRY:
        out.append((section_ref("industry"), ("section_undefined",)))
    elif key in (SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN):
        hs = digest.holdings
        rid = section_ref("holdings")
        if hs.availability is Availability.UNAVAILABLE:
            out.append((rid, (f"holdings_unavailable:{key}",)))
        if hs.unkeyed_count > 0:
            out.append((rid, ("holdings_unkeyed",)))
        if hs.availability is not Availability.UNAVAILABLE:
            mine = strategy_entries(digest, key)
            for h in mine:
                out.append((holding_ref(h.key.portfolio_id, h.key.symbol), ("strategy_entry",)))
            if not mine:
                out.append((rid, (f"strategy_unset:{key}",)))
    elif key == SEC_ACTIONS:
        pass       # 行動段：不可得／無行動由「句型前置條件＋非空段」涵蓋，各項行動由 `action_list_mismatch` 一對一檢查
    else:
        raise ValueError(f"未知的摘要段：{key!r}")
    return tuple(out)


# ══════════════════════════════════════════════════════════════════════
# 報告與入口
# ══════════════════════════════════════════════════════════════════════
def _report(violations: list, dropped: list, *, structural: bool, digest_invalid: bool,
            surviving: Optional[SummaryDraft]) -> GroundingReport:
    gates = tuple(g for g in GROUNDING_GATES if any(v.gate == g for v in violations))
    blocking = [v for v in violations if v.gate != GATE_G6]
    return GroundingReport(accepted=not blocking, violations=tuple(violations), dropped=tuple(dropped),
                           failed_gates=gates, structural_failure=structural, digest_invalid=digest_invalid,
                           surviving=surviving)


def check_summary(digest: Any, draft: Any) -> GroundingReport:
    """對一份摘要執行 G1～G6。**任何輸入都不 raise**（無法解析＝驗證失敗）。"""
    assessment = assess_digest(digest)
    if assessment.state is SummaryState.INVALID:
        v = _v(GATE_DIGEST, "", -1, "digest_invalid",
               "Digest 不合規（contract drift），無從對照；先看 assess_digest 的違規")
        return _report([v], [], structural=False, digest_invalid=True, surviving=None)
    struct = _structure(draft)
    if struct:
        return _report(struct, [], structural=True, digest_invalid=False, surviving=None)

    index = build_ref_index(digest)
    violations: list = []
    dropped: list = []
    kept_sections: list = []

    keys = [s.key for s in draft.sections]
    for k in keys:
        if k not in SECTION_KEYS:
            violations.append(_v(GATE_G5, str(k), -1, "unknown_section", f"未知的段落鍵：{k!r}"))
    for k in SECTION_KEYS:
        n = keys.count(k)
        if n == 0:
            violations.append(_v(GATE_G5, k, -1, "missing_section", f"五段必須齊全：缺 {k!r}"))
        elif n > 1:
            violations.append(_v(GATE_G5, k, -1, "duplicate_section", f"段落重複：{k!r}"))
    if all(k in SECTION_KEYS for k in keys) and len(set(keys)) == len(keys) == len(SECTION_KEYS) \
            and tuple(keys) != SECTION_KEYS:
        violations.append(_v(GATE_G5, "", -1, "section_order", f"段落必須依固定順序 {SECTION_KEYS}"))

    for s in draft.sections:
        if s.key not in SECTION_KEYS:
            continue
        surviving: list = []
        matched: list = []                     # [(Shape, slots)]，與 surviving 對齊
        for i, sent in enumerate(s.sentences):
            if not sent.evidence_refs:         # G6：沒有任何 Ref segment 的句子丟棄
                violations.append(_v(GATE_G6, s.key, i, "no_evidence_ref", "結論句沒有綁定任何項目，丟棄"))
                dropped.append((s.key, i))
                continue
            vs, shape, slots = _check_sentence(sent, s.key, i, digest, index)
            violations += vs
            surviving.append(sent)
            if not vs:
                matched.append((shape, slots))
        kept_sections.append(SummarySection(key=s.key, sentences=tuple(surviving)))
        if not surviving:
            violations.append(_v(GATE_G5, s.key, -1, "empty_section", "該段沒有任何有依據的句子（不得省略，須明示資料不足）"))
            continue
        if len(set(surviving)) != len(surviving):
            violations.append(_v(GATE_G5, s.key, -1, "duplicate_sentence", "段內不得有重複的句子"))
        for rid, sids in section_basis(digest, s.key):
            if not any(sh.sid in sids and sl[0].ref_id == rid for sh, sl in matched):
                violations.append(_v(GATE_G5, s.key, -1, "missing_disclosure",
                                     f"「{s.key}」段未以白名單句型明示 {rid!r}（須為 {list(sids)}）"))
        if s.key == SEC_ACTIONS:
            got = [sl[0].ref_id for sh, sl in matched if sh.sid in ACTION_SHAPE_IDS]
            want = [a.action_id for a in digest.actions.items]
            if got != want:
                violations.append(_v(GATE_G4, s.key, -1, "action_list_mismatch",
                                     f"行動必須與 Digest actions[] 一對一、同順序、無重複、無遺漏：{got!r} ≠ {want!r}"))
    surv = SummaryDraft(sections=tuple(kept_sections))
    return _report(violations, dropped, structural=False, digest_invalid=False, surviving=surv)


# ══════════════════════════════════════════════════════════════════════
# INVALID 的診斷文字
# ══════════════════════════════════════════════════════════════════════
def invalid_notices(assessment: DigestAssessment) -> tuple:
    secs = "、".join(LABEL_ALL_SECTIONS if k == SECTION_ALL else SECTION_LABELS[k]
                    for k in assessment.invalid_sections)
    codes = "、".join(sorted({v.code for v in assessment.violations}))
    return (
        "⛔ Decision Digest 契約不合規（contract drift）：不輸出任何投資結論。",
        f"無效段落：{secs}",
        f"失敗閘門：{'、'.join(assessment.failed_gates)}",
        f"違規代碼：{codes}",
        "其他段落：未保留（違規影響範圍未知，整份 Digest 不採信）。",
    )


# ══════════════════════════════════════════════════════════════════════
# 統一摘要結果（與 Digest 綁定；只暴露「通過檢查」的內容）
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SummaryResult:
    """統一的摘要結果型別（規則式摘要與未來 AI 摘要共用；本批只產生 `mode=RULE_ONLY`）。

    只有三個可傳入欄位：`digest`、`mode`、`sections`。其餘（state、section_availability、notices、
    invalid_sections、failed_gates、violations、retained_sections）**全部在建構時由 Digest 推導**
    （`init=False`），所以無法手造不一致的組合；`dataclasses.replace` 會重跑 `__post_init__`。
    建構時強制：
    - `mode` 必須是 AB-0 既有的 `AiParticipation`（不新增列舉值）；
    - Digest INVALID ⇒ `sections` 必須為空（不輸出任何投資結論）；
    - 否則 `sections` 必須通過 `check_summary` 且**乾淨**（無丟棄、`surviving == 原內容`）—— 摘要內容與 Digest 綁定。
    """
    digest: Any
    mode: AiParticipation
    sections: tuple = ()
    state: SummaryState = field(init=False)
    section_availability: tuple = field(init=False)
    notices: tuple = field(init=False)
    invalid_sections: tuple = field(init=False)
    failed_gates: tuple = field(init=False)
    violations: tuple = field(init=False)
    retained_sections: tuple = field(init=False)

    def __post_init__(self) -> None:
        if type(self.mode) is not AiParticipation:
            raise ValueError(f"SummaryResult.mode 必須是 AiParticipation：{self.mode!r}")
        a = assess_digest(self.digest)
        sset = object.__setattr__
        sset(self, "state", a.state)
        sset(self, "section_availability", a.section_availability)
        sset(self, "violations", a.violations)
        sset(self, "invalid_sections", a.invalid_sections)
        sset(self, "failed_gates", a.failed_gates)
        if a.state is SummaryState.INVALID:
            if self.sections != ():
                raise ValueError("INVALID 時不得輸出任何段落（sections 必須為空）")
            sset(self, "notices", invalid_notices(a))
            sset(self, "retained_sections", ())
            return
        rep = check_summary(self.digest, SummaryDraft(self.sections))
        if not rep.clean:
            raise ValueError("摘要未通過自檢（grounding）：" + "；".join(
                f"[{v.gate}/{v.code}] {v.section}#{v.sentence_index}: {v.message}" for v in rep.violations))
        sset(self, "notices", ())
        sset(self, "retained_sections", SECTION_KEYS)

    @property
    def lines(self) -> tuple:
        """((段鍵, (句子文字, ...)), ...) —— 由 Digest＋模板展開的唯一文字來源。INVALID → ()。"""
        if self.state is SummaryState.INVALID:
            return ()
        return render_draft(self.digest, SummaryDraft(self.sections))


__all__ = [
    "Lit", "Ref", "SummarySentence", "SummarySection", "SummaryDraft", "GroundingViolation", "GroundingReport",
    "SummaryResult", "RefInfo", "Shape", "SHAPES", "number_literal", "build_ref_index", "holding_ref",
    "section_ref", "expand", "oldest_stale_evidence", "render_sentence", "render_draft", "section_basis", "check_summary", "invalid_notices",
]
