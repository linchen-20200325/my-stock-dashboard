"""shared/decision_digest_grounding.py — 摘要的 grounding 驗證 G1～G6（AB-2a；L0 純函式，**無 AI**）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
`docs/vnext/NEWUI_D25_C_AI_BRAIN_DATA_2026-10-27.md` §2.4 的 G1～G6，以規則式程式執行（不由 LLM 驗 LLM）。
輸入：(1) 一份 `DecisionDigest`；(2) 一份**結構化摘要** `SummaryDraft`（句子＋引用 id 列表＋段落鍵）。
輸出：`GroundingReport`。**規則式摘要**（本批）與**未來 AI 輸出**（AB-2b）走同一個檢查器 ——
規則式摘要是基準對照：它自己必須通過全部 G 檢查，否則是 bug（`src/services/decision_digest_summary.py` 自檢）。

═══ 輸出格式契約（刻意最小；AB-2b 不得因它而被迫採用某種 prompt／傳輸） ═══════════
    SummaryDraft(sections=(SummarySection(key, sentences=(SummarySentence(text, evidence_refs), ...)), ...))
僅此而已。本檔**不**定義 AI prompt、傳輸、金鑰、用量、解析器。AB-2b 要把 AI 文字解析成 `SummaryDraft`；
**無法解析的輸入（None、dict、字串、子類別…）一律視為驗證失敗**（`structural_failure=True`）。

═══ 引用 id 空間（evidence_refs 只能指向這些；G1 引用封閉） ═══════════════════════
- Digest 內任一 `Fact.fact_id`、`ActionRef.action_id`；
- `section:<digest 段名>`（market／tw_trend／intl_trend／valuation／industry／holdings／risk_cap／actions）
  —— 讓「這一段沒有資料」這種敘述也有可回溯的依據；
- `holding:<portfolio_id>:<symbol>` —— 持股 entry 本身。
每個引用項帶：狀態（決定要求的標示語）、逐字引用文字（quote）、可出現的數字字面、資料日、可出現的代號。

═══ G1～G6 在「無 AI」版本的落地方式 ═══════════════════════════════════════
關鍵設計：**逐字引用（quote）豁免** —— 句子中與「所引項目」的 `Fact.text`／`ActionRef.text`／
`strategy_source` 逐字相同的片段，視為 Digest 自己的文字，不做字眼檢查；**其餘部分**（殘餘文字）才檢查。
因此 AI 要表達行動／狀態／數字，只能逐字搬運 Digest，不能改寫。
G1 引用封閉   ① 每個 evidence ref 必須在 Digest 的引用 id 空間內；② 殘餘文字中的數字代號必須屬於 Digest
              持股／行動目標的代號；英文大寫代號必須屬於 Digest 或 `LATIN_ALLOWED_TOKENS`；
              ③ 產業名稱（官方 35 類）一律拒收 —— Digest 的 industry 段恆為「尚未定義」，沒有允許名單；
              ④ 狀態詞（燈號符號、regime 英文）只能出現在逐字引用內。
G2 數字一致   殘餘文字中每個數值 token 必須「字面」等於所引項目的值（`number_literal`：不補零、不四捨五入、
              不換算）且單位吻合（有 unit → 緊接 unit；無 unit → 後面不得緊接 `%`／文字）；ISO 日期必須等於
              所引項目的 as_of；Risk Cap 區段（未核准顯示）的數值**一律不得出現**；全形／非 ASCII 數字、
              NaN／inf 字樣一律拒收。（⚠️ 只擋阿拉伯數字；「七十二點五」之類中文數字擋不住，見 docs/vnext/NEWUI_D25_AB2A_SPEC_2026-10-27.md §7 限制。）
G3 狀態不可升  ① 洗白字眼（中性／正常／維持／續抱／HOLD…）不得出現在殘餘文字；② 缺值佔位字（沿用 AB-0
              `PLACEHOLDER_TEXTS`）不得單獨成段；③ 所引項目為 missing／failed／invalid → 句中須有「資料不足」
              或「無法判定」；stale → 須有「資料已過期」；proxy → 須有「代理估算」；未定義／未接線／研究框架
              → 須有對應標示；④ 所引項目非 ok 時不得出現確定語氣字眼。
G4 不新增結論 ① 行動字眼（買進／賣出／加碼／減碼／停利／換股／續抱…、buy／sell／hold）只能在逐字引用內；
              ② 方向字眼（變強／轉弱／衰退／崛起／偏多／偏空…）只能在逐字引用內（Digest 沒有任何方向欄位）；
              ③ 引用行動 id 的句子必須逐字包含該行動的 `ActionRef.text`。
G5 段落完整   五段齊全、唯一、依固定順序；每段至少一句；每段對 Digest 中「非 ok 的依據」都有明示
              （`section_basis`：缺資料的事實、未定義的趨勢／產業、Risk Cap 卡面措辭、未設定策略分類、
              未帶鍵持股、無行動…）；句子只能引用屬於該段的項目（防止以無關事實填充）。
G6 依據可回溯 evidence_refs 為空的句子**丟棄**（記為 G6 違規但不使整份失敗；丟棄後該段若因此缺依據，
              由 G5 抓出）。

回傳的 `GroundingReport.accepted`＝沒有任何 G1～G5／STRUCT／DIGEST 違規（G6 丟棄不影響 accepted）。
`failed_gates`＝出現過違規的 G 閘門（含 G6）；AB-2b 若要寫回 Digest 的 `ai_failed_checks`，
結構失敗（`structural_failure`）沒有對應的 G id，需自行決定映射 —— 本檔不替它決定。

分層（CLAUDE.md §8.2）：L0 —— 只 import 標準函式庫與 `shared.*`；零 I/O、零 streamlit、零 `src.*`。
"""
from __future__ import annotations

import math
import numbers
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from shared.decision_digest import (
    AiParticipation, Availability, DataStatus, DecisionDigest, Fact, MissingReason,
)
from shared.decision_digest_terms import (
    ACTION_TERMS_CJK, ACTION_TERMS_LATIN, ASSERTIVE_TERMS_CJK, DATE_PATTERN, DIGEST_SECTIONS,
    DIRECTION_TERMS_CJK, DIRECTION_TERMS_LATIN, FORBIDDEN_CHAR_CATEGORIES, GATE_DIGEST, GATE_G1, GATE_G2,
    GATE_G3, GATE_G4, GATE_G5, GATE_G6, GATE_STRUCT, GROUNDING_GATES, INDUSTRY_GENERIC_CODES,
    LATIN_ALLOWED_TOKENS, MARK_NO_ACTION, MARK_NOT_DEFINED, MARK_NOT_WIRED, MARK_PROXY,
    MARK_RESEARCH_ONLY, MARK_STALE, MARK_STRATEGY_UNSET, MARK_UNKEYED,
    MARKERS_SECTION_BROAD, MARKERS_UNDETERMINED, NONFINITE_PATTERN, NUMBER_PATTERN, PLACEHOLDER_SEGMENTS,
    REF_HOLDING_PREFIX, REF_SECTION_PREFIX, RISK_CAP_HIDDEN_WORDING, SEC_ACTIONS, SEC_BUY_AND_HOLD,
    SEC_CAPITAL_GAIN, SEC_INDUSTRY, SEC_MARKET, SECTION_KEYS, SEGMENT_SPLIT_CHARS, STATE_SYMBOLS,
    STATE_WORDS_LATIN, SYMBOL_LATIN_PATTERN, SYMBOL_NUMERIC_PATTERN, UNIT_FORBIDDEN_AFTER_NONE,
    WASHING_TERMS_CJK, WASHING_TERMS_LATIN,
)
from shared.decision_digest_validator import SummaryState, assess_digest, derive_state, strategy_entries
from shared.industry_codes import OFFICIAL_INDUSTRY_CODE_NAMES, loose_industry_name


# ══════════════════════════════════════════════════════════════════════
# 結構化摘要型別（最小格式契約）
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SummarySentence:
    """一句話＋它引用的 evidence id（見模組 docstring 的引用 id 空間）。"""
    text: str
    evidence_refs: tuple = ()


@dataclass(frozen=True)
class SummarySection:
    key: str                     # `SECTION_KEYS` 之一
    sentences: tuple = ()        # tuple[SummarySentence]


@dataclass(frozen=True)
class SummaryDraft:
    sections: tuple = ()         # tuple[SummarySection]


@dataclass(frozen=True)
class GroundingViolation:
    gate: str                    # G1～G6／STRUCT／DIGEST
    section: str                 # 段鍵；不屬任何段 → ""
    sentence_index: int          # 句序；不屬任何句 → -1
    code: str
    message: str


@dataclass(frozen=True)
class GroundingReport:
    accepted: bool
    violations: tuple            # tuple[GroundingViolation]
    dropped: tuple               # ((段鍵, 句序), ...) —— G6 丟棄
    failed_gates: tuple          # 出現過違規的 G 閘門（排序、去重；含 G6）
    structural_failure: bool
    digest_invalid: bool
    surviving: Optional[SummaryDraft]   # 丟棄 G6 句子後的摘要；結構失敗或 Digest 不合規 → None

    @property
    def passed_gates(self) -> tuple:
        """沒有違規的 G 閘門（結構失敗／Digest 不合規時為空 —— 沒檢查完就不宣稱通過）。"""
        if self.structural_failure or self.digest_invalid:
            return ()
        return tuple(g for g in GROUNDING_GATES if g not in self.failed_gates)


@dataclass(frozen=True)
class SummaryResult:
    """統一的摘要結果型別（規則式摘要與未來 AI 摘要共用；本批只產生 `mode=RULE_ONLY`）。

    不變量（建構即檢查）：
    - `mode` 必須是 AB-0 既有的 `AiParticipation`（不新增列舉值）；
    - `state` 必須等於由 `section_availability` 推導的狀態（INVALID 例外）—— 狀態不得被升格；
    - INVALID ⇒ `sections==()`、`retained_sections==()`、`section_availability==()`（不輸出任何投資結論）；
    - 非 INVALID ⇒ 五段齊全、依固定順序、`retained_sections==SECTION_KEYS`。
    """
    state: SummaryState
    mode: AiParticipation
    sections: tuple = ()
    section_availability: tuple = ()
    notices: tuple = ()
    invalid_sections: tuple = ()
    failed_gates: tuple = ()
    violations: tuple = ()
    retained_sections: tuple = ()

    def __post_init__(self) -> None:
        if type(self.mode) is not AiParticipation:
            raise ValueError(f"SummaryResult.mode 必須是 AiParticipation：{self.mode!r}")
        if type(self.state) is not SummaryState:
            raise ValueError(f"SummaryResult.state 必須是 SummaryState：{self.state!r}")
        if self.state is SummaryState.INVALID:
            if self.sections or self.retained_sections or self.section_availability:
                raise ValueError("INVALID 時不得輸出任何段落（sections／retained_sections／section_availability 必須為空）")
            if not self.invalid_sections:
                raise ValueError("INVALID 時必須指出哪一段 invalid（invalid_sections 不得為空）")
            return
        keys = tuple(s.key for s in self.sections if type(s) is SummarySection)
        if keys != SECTION_KEYS or self.retained_sections != SECTION_KEYS:
            raise ValueError(f"非 INVALID 時必須恰有五段且依固定順序：{keys!r}")
        if tuple(k for k, _ in self.section_availability) != SECTION_KEYS:
            raise ValueError("section_availability 必須涵蓋五段且依固定順序")
        if derive_state(self.section_availability) is not self.state:
            raise ValueError(f"state={self.state.value} 與各段可得性推導結果不符（不得升格／降格）")


# ══════════════════════════════════════════════════════════════════════
# 文字正規化與數字字面
# ══════════════════════════════════════════════════════════════════════
def _clean(s: str) -> str:
    """NFKC 並移除控制／零寬／格式字元（保留大小寫與空白）。"""
    return "".join(ch for ch in unicodedata.normalize("NFKC", s)
                   if unicodedata.category(ch) not in FORBIDDEN_CHAR_CATEGORIES)


def _norm(s: str) -> str:
    return _clean(s).casefold()


def _squash(s: str) -> str:
    """去所有空白的正規形（比對中文字眼／標示語用）。"""
    return "".join(_norm(s).split())


def _tokens(n1: str) -> list:
    return [t for t in re.split(r"[^0-9a-z]+", n1) if t]


def number_literal(value: Any) -> str:
    """數值 → 唯一的「字面」形式（G2 的基準）。整數 → `str(int)`；浮點 → 固定小數、不用科學記號、
    不補零不截斷（`repr` 最短往返表示）。非有限／非實數 → ValueError。"""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ValueError(f"不是實數：{value!r}")
    if isinstance(value, numbers.Integral):
        return str(int(value))
    f = float(value)
    if not math.isfinite(f):
        raise ValueError(f"非有限數值：{value!r}")
    return format(Decimal(repr(f)), "f")


# ══════════════════════════════════════════════════════════════════════
# 引用項索引
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class RefInfo:
    ref_id: str
    kind: str                    # fact／action／section／holding
    non_ok: bool                 # 所引項目是否「不是有值且新鮮的正式資料」（影響確定語氣禁用）
    markers: tuple               # 句子必須含其一（空 tuple＝無要求）
    scopes: frozenset            # 允許出現的摘要段
    quotes: tuple = ()           # 逐字引用豁免的文字
    literals: tuple = ()         # ((字面, 單位|None), ...) 允許出現的數字
    restricted: bool = False     # 未核准顯示的項目（Risk Cap 區段、僅供參考的觀測值）：不貢獻任何允許的數字
    restricted_literals: tuple = ()  # 未核准顯示的數字字面（出現即違規）
    dates: tuple = ()            # 允許出現的 ISO 日期
    symbols: tuple = ()          # 允許出現的代號
    action_text: Optional[str] = None


def _fact_markers(status: DataStatus) -> tuple:
    if status is DataStatus.OK:
        return ()
    if status is DataStatus.STALE:
        return (MARK_STALE,)
    if status is DataStatus.PROXY:
        return (MARK_PROXY,)
    return MARKERS_UNDETERMINED


def _avail_markers(av: Availability) -> tuple:
    return () if av is Availability.AVAILABLE else MARKERS_SECTION_BROAD


def _definition_marker(section_obj: Any, *, research: bool) -> tuple:
    if research:
        return (MARK_RESEARCH_ONLY,)
    return (MARK_NOT_WIRED,) if section_obj.missing_reason is MissingReason.NOT_WIRED else (MARK_NOT_DEFINED,)


def _fact_info(f: Fact, scopes: frozenset, *, restricted: bool, restricted_markers: tuple = ()) -> RefInfo:
    lits: tuple = ()
    if f.value is not None:
        try:
            lits = ((number_literal(f.value), f.unit),)
        except ValueError:
            lits = ()   # 非有限值由 assess_digest（AB-0）擋下；這裡不再 raise
    dates = (f.provenance.as_of.isoformat(),) if f.provenance.as_of is not None else ()
    return RefInfo(
        ref_id=f.fact_id, kind="fact", non_ok=f.status is not DataStatus.OK,
        markers=restricted_markers if restricted else _fact_markers(f.status), scopes=scopes,
        quotes=(f.text,) if f.text is not None else (),
        restricted=restricted, literals=() if restricted else lits,
        restricted_literals=lits if restricted else (),
        dates=() if restricted else dates)


def build_ref_index(digest: DecisionDigest) -> dict:
    """引用 id → `RefInfo`（假設 digest 已通過 `assess_digest`）。"""
    idx: dict = {}
    s_market = frozenset({SEC_MARKET})
    s_hold = frozenset({SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN, SEC_ACTIONS})

    for f in digest.market.facts:
        idx[f.fact_id] = _fact_info(f, s_market, restricted=False)
    for name in ("tw_trend", "intl_trend"):          # 均線等「僅供參考」的觀測值：不得被當成可引用的數字
        for f in getattr(digest, name).observations:
            idx[f.fact_id] = _fact_info(f, s_market, restricted=True,
                                        restricted_markers=(MARK_NOT_DEFINED, MARK_NOT_WIRED))
    rc = digest.risk_cap
    for f in rc.facts:                                # Risk Cap 獨立數字未核准顯示（DEC-081 Q2-2）
        idx[f.fact_id] = _fact_info(f, s_market, restricted=True, restricted_markers=(RISK_CAP_HIDDEN_WORDING,))
    for h in digest.holdings.entries:
        for f in h.facts:
            idx[f.fact_id] = _fact_info(f, s_hold, restricted=False)
    for a in digest.actions.items:
        idx[a.action_id] = RefInfo(
            ref_id=a.action_id, kind="action", non_ok=False, markers=(), scopes=frozenset({SEC_ACTIONS}),
            quotes=(a.text, *((a.target.symbol,) if a.target is not None else ())),
            symbols=(a.target.symbol,) if a.target is not None else (), action_text=a.text)

    def sec(name: str, scopes: frozenset, markers: tuple, **kw: Any) -> None:
        rid = REF_SECTION_PREFIX + name
        idx[rid] = RefInfo(ref_id=rid, kind="section", non_ok=bool(markers), markers=markers, scopes=scopes, **kw)

    sec("market", s_market, _avail_markers(digest.market.availability))
    sec("tw_trend", s_market, _definition_marker(digest.tw_trend, research=False))
    sec("intl_trend", s_market, _definition_marker(digest.intl_trend, research=False))
    sec("valuation", s_market, _definition_marker(digest.valuation, research=True))
    sec("industry", frozenset({SEC_INDUSTRY}), _definition_marker(digest.industry, research=False))
    unkeyed = digest.holdings.unkeyed_count
    sec("holdings", s_hold, _avail_markers(digest.holdings.availability),
        literals=((str(unkeyed), None),) if unkeyed > 0 else ())
    sec("risk_cap", s_market, (RISK_CAP_HIDDEN_WORDING,), quotes=(RISK_CAP_HIDDEN_WORDING,))
    acts = digest.actions
    if acts.availability is Availability.UNAVAILABLE:
        am = MARKERS_UNDETERMINED
    elif not acts.items:
        am = (MARK_NO_ACTION,)
    else:
        am = ()
    sec("actions", frozenset({SEC_ACTIONS}), am)

    for h in digest.holdings.entries:
        rid = holding_ref(h.key.portfolio_id, h.key.symbol)
        idx[rid] = RefInfo(
            ref_id=rid, kind="holding", non_ok=True, markers=(MARK_NOT_WIRED, *MARKERS_UNDETERMINED),
            scopes=s_hold,
            quotes=(*((h.strategy_source,) if h.strategy_source is not None else ()), h.key.symbol),
            symbols=(h.key.symbol,))
    return idx


def holding_ref(portfolio_id: str, symbol: str) -> str:
    return f"{REF_HOLDING_PREFIX}{portfolio_id}:{symbol}"


def section_ref(name: str) -> str:
    if name not in DIGEST_SECTIONS:
        raise ValueError(f"未知的 Digest 段名：{name!r}")
    return REF_SECTION_PREFIX + name


def symbol_allowlist(digest: DecisionDigest) -> frozenset:
    out = {h.key.symbol for h in digest.holdings.entries}
    out |= {a.target.symbol for a in digest.actions.items if a.target is not None}
    return frozenset(out)


def section_basis(digest: DecisionDigest, key: str, index: Optional[dict] = None) -> tuple:
    """G5 的「必須明示」清單：((引用 id, 可接受標示語 any-of), ...)。

    只列「Digest 中非 ok 的依據」：缺資料的事實、未定義的趨勢／產業、Risk Cap 卡面措辭、持股未讀到、
    未帶鍵持股、尚未設定策略分類／策略分類但判定未接線、無行動。全部由 Digest 資料推導。
    """
    idx = index if index is not None else build_ref_index(digest)
    out: list = []
    if key == SEC_MARKET:
        for f in digest.market.facts:
            if idx[f.fact_id].markers:
                out.append((f.fact_id, idx[f.fact_id].markers))
        for name in ("tw_trend", "intl_trend", "valuation", "risk_cap"):
            rid = section_ref(name)
            out.append((rid, idx[rid].markers))
    elif key == SEC_INDUSTRY:
        rid = section_ref("industry")
        out.append((rid, idx[rid].markers))
    elif key in (SEC_BUY_AND_HOLD, SEC_CAPITAL_GAIN):
        rid = section_ref("holdings")
        hs = digest.holdings
        if hs.availability is Availability.UNAVAILABLE:
            out.append((rid, MARKERS_UNDETERMINED))
        if hs.unkeyed_count > 0:
            out.append((rid, (MARK_UNKEYED,)))
        if hs.availability is not Availability.UNAVAILABLE:
            mine = strategy_entries(digest, key)
            if mine:
                for h in mine:
                    out.append((holding_ref(h.key.portfolio_id, h.key.symbol), (MARK_NOT_WIRED,)))
            else:
                out.append((rid, (MARK_STRATEGY_UNSET,)))
    elif key == SEC_ACTIONS:
        rid = section_ref("actions")
        if idx[rid].markers:
            out.append((rid, idx[rid].markers))
    else:
        raise ValueError(f"未知的摘要段：{key!r}")
    return tuple(out)


# ══════════════════════════════════════════════════════════════════════
# 逐字引用豁免
# ══════════════════════════════════════════════════════════════════════
_RE_NUMERIC_ONLY = re.compile(r"[0-9.+\-%\s]*")


def is_numeric_quote(q: str) -> bool:
    """引用文字只由數字／小數點／正負號／百分號／空白組成（需在日期遮罩之後才能安全移除）。"""
    return _RE_NUMERIC_ONLY.fullmatch(q) is not None


def remove_quotes(text: str, quotes: tuple) -> str:
    """把句中與 Digest 文字逐字相同的片段換成空白，回傳「殘餘文字」。

    邊界規則：引用首／尾若是 ASCII 英數字，其前／後不得緊接英數字（尾端還不得緊接 `.數字`），
    避免「引用 `7`」把 `72.5` 的一部分吃掉而洗白數字。長的引用優先。
    """
    out = text
    for q in sorted({q for q in quotes if type(q) is str and q != ""}, key=len, reverse=True):
        lead = r"(?<![0-9A-Za-z])" if (q[0].isascii() and q[0].isalnum()) else ""
        tail = r"(?![0-9A-Za-z]|\.[0-9])" if (q[-1].isascii() and q[-1].isalnum()) else ""
        out = re.sub(lead + re.escape(q) + tail, " ", out)
    return out


# ══════════════════════════════════════════════════════════════════════
# 單句檢查
# ══════════════════════════════════════════════════════════════════════
def _industry_terms() -> tuple:
    terms: set = set()
    for code, name in OFFICIAL_INDUSTRY_CODE_NAMES.items():
        if name is None or code in INDUSTRY_GENERIC_CODES:
            continue
        terms.add(_squash(name))
        loose = loose_industry_name(name)
        if len(loose) >= 2:
            terms.add(_squash(loose))
    return tuple(sorted(t for t in terms if t))


_INDUSTRY_TERMS: tuple = _industry_terms()
_RE_SYMBOL_NUM = re.compile(SYMBOL_NUMERIC_PATTERN)
_RE_SYMBOL_LATIN = re.compile(SYMBOL_LATIN_PATTERN)
_RE_DATE = re.compile(DATE_PATTERN)
_RE_NUMBER = re.compile(NUMBER_PATTERN)
_RE_NONFINITE = re.compile(NONFINITE_PATTERN)
_RE_SEGMENT = re.compile("[" + re.escape(SEGMENT_SPLIT_CHARS) + r"\s]+")
_PLACEHOLDER_SET: frozenset = frozenset(_squash(p) for p in PLACEHOLDER_SEGMENTS)


def _v(gate: str, section: str, idx: int, code: str, message: str) -> GroundingViolation:
    return GroundingViolation(gate=gate, section=section, sentence_index=idx, code=code, message=message)


def _unit_ok(after: str, unit: Optional[str]) -> bool:
    if unit is not None:
        return after.startswith(_clean(unit))
    if after == "" or after[0].isspace():
        return True
    return unicodedata.category(after[0]).startswith("P") and after[0] not in UNIT_FORBIDDEN_AFTER_NONE


def _check_numbers(resid: str, refs: list, symbols: frozenset, sec: str, i: int, numeric_quotes: tuple) -> list:
    """G2（含 G1 的「未知代號形狀的數字」）。resid 為殘餘文字（未 casefold）。"""
    out: list = []
    for ch in resid:
        cat = unicodedata.category(ch)
        if cat.startswith("N") and not (ch.isascii() and ch.isdigit()):
            out.append(_v(GATE_G2, sec, i, "non_ascii_digit", f"不得使用非 ASCII 數字字元：{ch!r}"))
            break
    text = _clean(resid)
    low = text.casefold()
    if _RE_NONFINITE.search(low):
        out.append(_v(GATE_G2, sec, i, "non_finite_token", "不得出現 NaN／inf 字樣"))

    allowed_dates = {d for r in refs for d in r.dates}
    for m in _RE_DATE.finditer(text):
        if m.group(0) not in allowed_dates:
            out.append(_v(GATE_G2, sec, i, "date_not_in_digest", f"日期不是所引項目的資料日：{m.group(0)!r}"))
    text = _RE_DATE.sub(lambda m: " " * len(m.group(0)), text)
    text = remove_quotes(text, numeric_quotes)   # 純數字的逐字引用：日期遮罩之後才移除，避免吃掉日期的一部分
    # 已知代號 → 遮罩（不算數字）
    text = _RE_SYMBOL_NUM.sub(lambda m: " " * len(m.group(0)) if m.group(0) in symbols else m.group(0), text)

    allowed = [lit for r in refs for lit in r.literals]
    restricted = {lit for r in refs for lit, _ in r.restricted_literals}
    lit_set = {lit for lit, _ in allowed}
    for m in _RE_NUMBER.finditer(text):
        tok, after = m.group(0), text[m.end():]
        if any(lit == tok and _unit_ok(after, unit) for lit, unit in allowed):
            continue
        if tok in restricted:
            out.append(_v(GATE_G2, sec, i, "restricted_value", f"Risk Cap 區段數字未核准顯示：{tok!r}"))
        else:
            out.append(_v(GATE_G2, sec, i, "number_not_literal",
                          f"數字 {tok!r} 不是所引項目的字面值（含單位與小數位）"))
    # G1：看起來像代號、卻不在 Digest 的數字
    for m in _RE_SYMBOL_NUM.finditer(text):
        digits = re.match(r"\d+", m.group(0)).group(0)
        if m.group(0) not in symbols and digits not in lit_set:
            out.append(_v(GATE_G1, sec, i, "symbol_not_in_digest", f"代號 {m.group(0)!r} 不在 Digest 的持股／行動目標"))
    return out


def _check_sentence(sent: SummarySentence, section: str, i: int, index: dict, symbols: frozenset) -> list:
    out: list = []
    refs: list = []
    for rid in sent.evidence_refs:
        info = index.get(rid)
        if info is None:
            out.append(_v(GATE_G1, section, i, "ref_not_in_digest", f"evidence ref 不在 Digest 的引用 id 空間：{rid!r}"))
            continue
        refs.append(info)
        if section not in info.scopes:
            out.append(_v(GATE_G5, section, i, "ref_out_of_scope",
                          f"{rid!r} 不屬於「{section}」段的依據（不得以無關項目填充）"))
    all_quotes = tuple(q for r in refs for q in r.quotes)
    rich_quotes = tuple(q for q in all_quotes if not is_numeric_quote(q))
    numeric_quotes = tuple(q for q in all_quotes if is_numeric_quote(q))
    resid = remove_quotes(sent.text, rich_quotes)
    clean = _clean(resid)
    n1 = clean.casefold()
    n2 = "".join(n1.split())
    toks = set(_tokens(n1))

    # ── G1 引用封閉 ────────────────────────────────────────────────
    for m in _RE_SYMBOL_LATIN.finditer(clean):
        w = m.group(0)
        if w not in symbols and w not in LATIN_ALLOWED_TOKENS:
            out.append(_v(GATE_G1, section, i, "symbol_not_in_digest", f"英文代號 {w!r} 不在 Digest"))
    for term in _INDUSTRY_TERMS:
        if term in n2:
            out.append(_v(GATE_G1, section, i, "industry_not_in_digest",
                          f"出現產業名稱 {term!r}：Digest 的產業段沒有任何允許名單（尚未定義）"))
            break
    for sym in STATE_SYMBOLS:
        if sym in clean:
            out.append(_v(GATE_G1, section, i, "state_word_not_in_digest", f"燈號符號 {sym!r} 只能逐字引用 Digest"))
    for w in sorted(toks & STATE_WORDS_LATIN):
        out.append(_v(GATE_G1, section, i, "state_word_not_in_digest", f"狀態詞 {w!r} 只能逐字引用 Digest"))

    # ── G2 數字字面一致 ───────────────────────────────────────────
    out += _check_numbers(resid, refs, symbols, section, i, numeric_quotes)

    # ── G3 狀態不可升級 ───────────────────────────────────────────
    for term in WASHING_TERMS_CJK:
        if _squash(term) in n2:
            out.append(_v(GATE_G3, section, i, "washing_term", f"洗白字眼 {term!r}（missing ≠ neutral／normal／HOLD）"))
    for w in sorted(toks & WASHING_TERMS_LATIN):
        out.append(_v(GATE_G3, section, i, "washing_term", f"洗白字眼 {w!r}（missing ≠ neutral／normal／HOLD）"))
    for seg in _RE_SEGMENT.split(n1):
        if seg and seg in _PLACEHOLDER_SET:
            out.append(_v(GATE_G3, section, i, "placeholder_segment", f"缺值佔位字單獨成段：{seg!r}"))
            break
    full = _squash(sent.text)
    for r in refs:
        if r.markers and not any(_squash(m) in full for m in r.markers):
            out.append(_v(GATE_G3, section, i, "missing_marker",
                          f"{r.ref_id!r} 非 ok／未定義：句中必須明示其一 {list(r.markers)}"))
    if any(r.non_ok for r in refs):
        for term in ASSERTIVE_TERMS_CJK:
            if _squash(term) in n2:
                out.append(_v(GATE_G3, section, i, "assertive_tone", f"所引項目非 ok，不得使用確定語氣 {term!r}"))
                break

    # ── G4 不得新增結論類別 ───────────────────────────────────────
    bad_act = [t for t in ACTION_TERMS_CJK if _squash(t) in n2] + sorted(toks & ACTION_TERMS_LATIN)
    if bad_act:
        out.append(_v(GATE_G4, section, i, "new_action_term",
                      f"行動字眼 {bad_act[0]!r} 只能逐字引用 Digest 的 actions[]／規則層文字"))
    bad_dir = [t for t in DIRECTION_TERMS_CJK if _squash(t) in n2] + sorted(toks & DIRECTION_TERMS_LATIN)
    if bad_dir:
        out.append(_v(GATE_G4, section, i, "new_direction_term",
                      f"方向字眼 {bad_dir[0]!r}：Digest 沒有對應欄位（趨勢／產業＝尚未定義）"))
    for r in refs:
        if r.kind == "action" and (r.action_text is None or r.action_text not in sent.text):
            out.append(_v(GATE_G4, section, i, "action_text_not_verbatim",
                          f"引用行動 {r.ref_id!r} 的句子必須逐字包含該行動文字"))
    return out


# ══════════════════════════════════════════════════════════════════════
# 結構檢查
# ══════════════════════════════════════════════════════════════════════
def _ref_problem(r: Any) -> Optional[str]:
    if type(r) is not str or r == "":
        return "evidence ref 必須是非空 str"
    if any(ch.isspace() for ch in r):
        return "evidence ref 不得含空白"
    if any(unicodedata.category(ch) in FORBIDDEN_CHAR_CATEGORIES for ch in r):
        return "evidence ref 不得含控制或零寬字元"
    return None


def _structure(draft: Any) -> list:
    """無法解析的輸入＝驗證失敗（STRUCT）。不 raise。"""
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
        if type(s.sentences) is not tuple:
            out.append(_v(GATE_STRUCT, str(s.key), -1, "sentences_not_tuple", "sentences 必須是 tuple"))
            continue
        for i, t in enumerate(s.sentences):
            if type(t) is not SummarySentence:
                out.append(_v(GATE_STRUCT, str(s.key), i, "sentence_type", "句子必須恰好是 SummarySentence"))
                continue
            if type(t.text) is not str or t.text.strip() == "":
                out.append(_v(GATE_STRUCT, str(s.key), i, "text_blank", "text 必須是非空 str"))
            elif any(unicodedata.category(ch) in FORBIDDEN_CHAR_CATEGORIES for ch in t.text):
                out.append(_v(GATE_STRUCT, str(s.key), i, "control_chars_in_text", "句子不得含控制或零寬字元"))
            if type(t.evidence_refs) is not tuple:
                out.append(_v(GATE_STRUCT, str(s.key), i, "refs_not_tuple", "evidence_refs 必須是 tuple"))
                continue
            for r in t.evidence_refs:
                p = _ref_problem(r)
                if p:
                    out.append(_v(GATE_STRUCT, str(s.key), i, "bad_ref", f"{p}：{r!r}"))
            if len(set(r for r in t.evidence_refs if type(r) is str)) != len(
                    [r for r in t.evidence_refs if type(r) is str]):
                out.append(_v(GATE_STRUCT, str(s.key), i, "duplicate_ref", "evidence_refs 不得重複"))
    return out


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
    symbols = symbol_allowlist(digest)
    violations: list = []
    dropped: list = []
    kept_sections: list = []

    # G5：段落鍵齊全、唯一、順序
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
        for i, sent in enumerate(s.sentences):
            if not sent.evidence_refs:                       # G6：無依據的句子丟棄
                violations.append(_v(GATE_G6, s.key, i, "no_evidence_ref", "結論句沒有綁定任何 evidence_ref，丟棄"))
                dropped.append((s.key, i))
                continue
            violations += _check_sentence(sent, s.key, i, index, symbols)
            surviving.append(sent)
        kept_sections.append(SummarySection(key=s.key, sentences=tuple(surviving)))
        if not surviving:
            violations.append(_v(GATE_G5, s.key, -1, "empty_section", "該段沒有任何有依據的句子（不得省略，須明示資料不足）"))
        else:
            for rid, markers in section_basis(digest, s.key, index):
                hit = any(rid in x.evidence_refs and any(_squash(m) in _squash(x.text) for m in markers)
                          for x in surviving)
                if not hit:
                    violations.append(_v(GATE_G5, s.key, -1, "missing_disclosure",
                                         f"「{s.key}」段未明示 {rid!r}（須含其一 {list(markers)}）"))
    surv = SummaryDraft(sections=tuple(kept_sections))
    return _report(violations, dropped, structural=False, digest_invalid=False, surviving=surv)


__all__ = [
    "SummarySentence", "SummarySection", "SummaryDraft", "GroundingViolation", "GroundingReport",
    "SummaryResult", "RefInfo", "number_literal", "build_ref_index", "holding_ref", "section_ref",
    "symbol_allowlist", "section_basis", "remove_quotes", "is_numeric_quote", "check_summary",
]
