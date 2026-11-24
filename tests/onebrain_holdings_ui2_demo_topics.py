"""OneBrain 持股槽「可操作四主題」FAKE 預覽的內容與 SectionVM（C-OB-TOPICS-DEMO；延續 #1268；**tests-only**）。

四個主題：大盤／產業前瞻／持股健檢／反方風險。launcher 依 `st.radio`（key＝`KEY_TOPIC`）的選擇，在 `?ui2_dev=1` 的 FAKE／cold／💼 持股頁
把預設的「🤖 OneBrain 持股摘要：⬜ 尚未提供」槽換成**所選主題**的單一 `onebrain` L1 `SectionVM`（位置不變、仍在現行槽內）。

⛔ 0 production caller：src／shared／app*／scripts 不得 import 本檔。⛔ 不改 `src/ui2`、`shared/ui2_contract`、`app_ui2.py`。
⛔ 零正式 LLM／Provider／網路／時鐘／Secrets／快取寫入：內容只來自 #1265 的離線合成 Digest（`demo.assemble`）與規則層既有句。
⛔ Real 不經本檔（launcher 只在 FAKE 路徑包 wrapper）。

═══ 每個主題的固定行內版面（不用 expander）═════════════════════════════════
示意（逐字揭露）→ 核心觀察（≤3 句）→ 觀察重點（最多 3 點）→ 支持證據／反面證據（逐列：證據編號・來源・時點・狀態）→ 缺項 → 來源時點（併成一列）。
- 大盤：C3 未裁示 ⇒ 一律 unavailable，不顯示任何大盤內容句（暫定原因碼 LENS_MARKET_SURFACE_PENDING，標「暫定名稱、文案待 Copy Gate」）。
- 產業前瞻：恆 unavailable；只顯示 Digest 既有句「⬜ 產業趨勢：尚未定義，無法判定」；該句本身沒有來源／時點／狀態 ⇒ 照實寫「無」。
- 持股健檢：沿用 #1268 已 PASS 的列（Digest 原句逐字、持股判讀、D3 註記），再補行內證據列（Digest 原句所引用欄位的證據編號）。
- 反方風險：v1 沒有反證欄位 ⇒ 預設「⬜ 無法判定（無反證輸入）」；只在 `COUNTER_FIXTURE` 指名的案例顯示**明標「FAKE-SYN 合成反證（非 Digest 欄位）」**的測試夾具，
  任何時候不得由 Risk Cap 或其他 Digest 欄位推導反證。

═══ 預覽暫行口徑（D7 未裁；⛔ 不是正式規則）══════════════════════════════════
核心觀察至多 3 句且各 <100 字、觀察重點至多 3 點且每點 <25 字；字數＝Unicode 字元數（`len(str)`），徽章另列不計入；
超限**不截斷、不丟句**：核心觀察超限 ⇒ 該主題改列「⬜ 無法判定」＋說明徽章；觀察重點不合格的句子標「未列入觀察重點」。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from shared.decision_digest import Availability, DataStatus, StrategyType
from shared.decision_digest_grounding import Ref
from shared.decision_digest_terms import (
    MARK_PROXY, MARK_STALE, MARK_STRATEGY_UNSET, MARK_UNKEYED, MISSING_REASON_LABELS,
)
from shared.ui2_contract.models import FieldState, FieldVM, JudgementState, SectionVM
from shared.ui2_contract.text import TEXT_MISSING_NOT_READY, TEXT_RISK_CAP_UNDETERMINABLE, stale_text
from tests import onebrain_holdings_ui2_demo as demo
from tests import onebrain_holdings_ui2_demo_vm as VM

_log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════
# 主題與選擇狀態
# ══════════════════════════════════════════════════════════════════════
TOPIC_MARKET = "大盤"
TOPIC_INDUSTRY = "產業前瞻"
TOPIC_HOLDINGS = "持股健檢"
TOPIC_RISK = "反方風險"
TOPICS = (TOPIC_MARKET, TOPIC_INDUSTRY, TOPIC_HOLDINGS, TOPIC_RISK)
#: 預設主題＝持股健檢：維持 #1268 既有內容為預設（最小合法原則；避免退化）。
DEFAULT_TOPIC = TOPIC_HOLDINGS
KEY_TOPIC = "ui2_obdemo_topic"              # st.radio 的 session key（ui2_ 前綴；與 ui2_obdemo_testinfo 同類的測試控制）

# ══════════════════════════════════════════════════════════════════════
# label（槽內）；沿用 #1268 的 示意／持股判讀／存股／資本利得，新增版面用 label
# ══════════════════════════════════════════════════════════════════════
L_DEMO, L_JUDGE = VM.LABEL_DEMO, VM.LABEL_JUDGEMENT
L_CORE, L_POINTS, L_SUPPORT, L_COUNTER, L_GAP, L_SRC = "核心觀察", "觀察重點", "支持證據", "反面證據", "缺項", "來源時點"
#: Digest 原句所引用的欄位（`section:*`）：只是「引用」，**不是**支持證據（本預覽的原句皆為「無法判定」類句子，標成支持證據會被讀成「無法判定卻有支持證據」）。
L_CITE = "引用（非支持證據）"
LABELS = (L_DEMO, L_CORE, L_JUDGE, VM.LABEL_BUY_AND_HOLD, VM.LABEL_CAPITAL_GAIN, L_POINTS, L_CITE, L_COUNTER, L_GAP, L_SRC)

# ══════════════════════════════════════════════════════════════════════
# 預覽暫行口徑（D7 未裁）
# ══════════════════════════════════════════════════════════════════════
D7_MARK = "預覽暫行口徑（D7 未裁，非正式）"
CORE_MAX_SENTENCES = 3
CORE_LT_CODEPOINTS = 100
POINT_MAX_LISTED = 3
POINT_LT_CODEPOINTS = 25
D7_DETAIL = (f"{D7_MARK}：核心觀察≤{CORE_MAX_SENTENCES} 句且各＜{CORE_LT_CODEPOINTS} 字、重點≤{POINT_MAX_LISTED} 點且每點＜{POINT_LT_CODEPOINTS} 字")

# ══════════════════════════════════════════════════════════════════════
# 固定文案（本模組自有；只組合既有字樣，不新增正式句型）
# ══════════════════════════════════════════════════════════════════════
LENS_MARKET_REASON = "LENS_MARKET_SURFACE_PENDING"
MARKET_DETAIL = (f"大盤對外句型尚未裁示，本預覽不顯示任何大盤句；暫定原因碼 {LENS_MARKET_REASON}（暫定名稱，文案待 Copy Gate）")
RISK_NO_INPUT_DETAIL = "無反證輸入：Digest 沒有反證欄位，不由其他欄位推導"
POINTS_NONE_UNAVAILABLE = "無（本主題無法判定，沒有可列入的重點）"
POINTS_NONE_TOO_LONG = "無（核心觀察各句皆超過預覽暫行字數上限，未列入觀察重點）"
CITED_CLAIM = "原句引用"
GAP_MARKET = "大盤對外句型尚未裁示；支持證據：無｜反面證據：無"
GAP_INDUSTRY = "產業趨勢尚未定義；支持證據：無｜反面證據：無"
GAP_RISK_NO_INPUT = "無反證輸入（Digest 沒有反證欄位）；支持證據：無｜反面證據：無"
GAP_RISK_FIXTURE = "支持證據：無（本主題只呈現反面證據）"
GAP_DEGRADED = "示意內容未能產生；支持證據：無｜反面證據：無"
SRC_NONE = "來源 無（本主題沒有顯示任何來源資料）｜時點 無"
SRC_INDUSTRY = "來源 無（該句本身沒有來源、時點、狀態）｜時點 無"
SRC_HOLDINGS = f"來源 {VM.SOURCE_VALUE}｜時點 {VM.ASOF_VALUE}"
SRC_RISK_FIXTURE = "來源 FAKE-SYN 合成反證（非 Digest 欄位）｜時點 見各列（FAKE 示意日）"
NO_VALUE = "無"
STATUS_OK = "有資料"
STATUS_INSUFFICIENT = "資料不足"
_CIRCLED = "①②③"


def _over_limit_detail(reason: str) -> str:
    """暫行口徑超限而降級的原因（與「資料不可用」在文字上可區分）：⛔ 不截斷、不丟句。"""
    return f"{D7_MARK}｜原因：預覽暫行口徑超限（D7 未裁）：{reason}；不截斷、不丟句；並非資料不可用"


class TopicError(RuntimeError):
    """主題內容與預期不符（漂移）。builder 對**正常**內容拋出時，由 `build_topic_view` 降級成固定 fail-closed 版面並留 log。"""


# ══════════════════════════════════════════════════════════════════════
# 證據
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Evidence:
    kind: str                       # "cite"（Digest 原句引用）｜"counter"（合成反證）｜"support"（保留給日後真正的支持證據；本預覽不使用）
    ev_id: str                      # 證據編號：Digest 的引用 id，或 `fake-syn:` 開頭的合成夾具 id
    claim: str
    source: Optional[str]           # None＝該引用本身沒有來源 ⇒ 照實顯示「無」
    as_of: Optional[str]
    status: Optional[DataStatus]    # None＝該引用本身沒有狀態
    fixture: bool                   # True＝測試夾具（非 Digest 欄位）


#: 合成反面證據夾具：明標「FAKE-SYN 合成反證（非 Digest 欄位）」，只在這裡指名的案例出現；來源／時點一律 FAKE 開頭。
FIXTURE_SOURCE = "FAKE-SYN 合成反證（非 Digest 欄位）"
COUNTER_FIXTURE: dict = {
    "L2": (
        Evidence("counter", "fake-syn:counter:L2:1", "FAKE-SYN 合成反面證據 1（非 Digest 欄位）", FIXTURE_SOURCE,
                 "FAKE 示意日 2026-10-26", DataStatus.OK, True),
        Evidence("counter", "fake-syn:counter:L2:2", "FAKE-SYN 合成反面證據 2（非 Digest 欄位）", FIXTURE_SOURCE,
                 "FAKE 示意日 2026-10-20", DataStatus.STALE, True),
    ),
}


def counter_fixture(case_id: str) -> tuple:
    """該案例的合成反證夾具（沒有 ⇒ 空 tuple）。讀 module 全域（測試可替換）。"""
    return tuple(COUNTER_FIXTURE.get(case_id, ()))


_STATUS_TEXT = {None: NO_VALUE, DataStatus.OK: STATUS_OK, DataStatus.STALE: MARK_STALE, DataStatus.PROXY: MARK_PROXY,
                DataStatus.MISSING: STATUS_INSUFFICIENT}


def _evidence_text(ev: Evidence) -> str:
    if (ev.status is not None and type(ev.status) is not DataStatus) or ev.status not in _STATUS_TEXT:     # DataStatus 是 str 子類：裸字串 "ok" 也會命中 dict ⇒ 先擋型別
        raise ValueError(f"預覽不支援的證據狀態：{ev.status!r}")
    return (f"{ev.claim}｜證據編號 {ev.ev_id}｜來源 {ev.source or NO_VALUE}｜時點 {ev.as_of or NO_VALUE}｜"
            f"狀態 {_STATUS_TEXT[ev.status]}")


def evidence_field(ev: Evidence) -> FieldVM:
    """證據一列（行內，逐項帶 證據編號／來源／時點／狀態；缺值明寫「無」，⛔ 不補 0）。
    STALE ⇒ 既有「資料已過期」字樣＋`⚠` 徽章；PROXY ⇒ 既有「代理估算」字樣；MISSING ⇒ 缺值態（不帶 value）。"""
    if ev.kind == "support":
        label = L_SUPPORT
    elif ev.kind == "cite":
        label = L_CITE
    elif ev.kind == "counter":
        label = L_COUNTER
    else:
        raise ValueError(f"證據種類不明：{ev.kind!r}")
    text = _evidence_text(ev)
    if ev.status is DataStatus.STALE:
        return FieldVM(label, FieldState.STALE, value_text=text, status_text=stale_text(None))
    if ev.status is DataStatus.MISSING:
        return FieldVM(label, FieldState.MISSING, status_text=TEXT_MISSING_NOT_READY, detail=text)
    return FieldVM(label, FieldState.OK, value_text=text)


# ══════════════════════════════════════════════════════════════════════
# 預覽暫行口徑的檢查
# ══════════════════════════════════════════════════════════════════════
def check_core(sentences) -> Optional[str]:
    """核心觀察是否在暫行口徑內。回 None＝合格；否則回原因字串（⛔ 不截斷、不丟句）。"""
    ss = list(sentences)
    if len(ss) > CORE_MAX_SENTENCES:
        return f"Digest 原句 {len(ss)} 句，超過核心觀察上限 {CORE_MAX_SENTENCES} 句"
    for i, s in enumerate(ss, 1):
        if len(s) >= CORE_LT_CODEPOINTS:
            return f"第 {i} 句 {len(s)} 字元，達到核心觀察單句上限 {CORE_LT_CODEPOINTS}"
    return None


@dataclass(frozen=True)
class Points:
    listed: tuple
    excluded: int


def _point_indexes(sentences) -> list:
    return [i for i, x in enumerate(sentences) if len(x) < POINT_LT_CODEPOINTS][:POINT_MAX_LISTED]


def select_points(sentences) -> Points:
    """觀察重點：依原順序取至多 3 句、且每句 <25 字元者（逐字，不改寫）；其餘算「未列入觀察重點」（只計數、不截斷）。"""
    ss = list(sentences)
    idx = _point_indexes(ss)
    return Points(tuple(ss[i] for i in idx), len(ss) - len(idx))


# ══════════════════════════════════════════════════════════════════════
# 列建構
# ══════════════════════════════════════════════════════════════════════
def _d(label: str, text: str, detail: Optional[str] = None) -> FieldVM:
    return FieldVM(label, FieldState.OK, value_text=text, detail=detail)   # D 型＝文字載體（DOM data-state=ok ≠ 持股／投資狀態正常）


def _undeterminable(label: str, detail: str) -> FieldVM:
    return FieldVM(label, JudgementState.UNDETERMINABLE, status_text=TEXT_RISK_CAP_UNDETERMINABLE, detail=detail)


def _points_row(items) -> FieldVM:
    """觀察重點列。`items`＝[(label, 核心觀察句)]。合格的句子（<25 字、至多 3 點）**以其 label 指向上方原句**（①存股 ②資本利得…），
    不在這裡重複整句（原句逐字只出現一次，槽才不會被同一句撐長；手機首屏密度 SF1）；不合格者只計數、標「未列入觀察重點」。"""
    items = list(items)
    if not items:
        return _d(L_POINTS, POINTS_NONE_UNAVAILABLE, D7_DETAIL)
    idx = _point_indexes([t for _l, t in items])
    if not idx:
        return _d(L_POINTS, POINTS_NONE_TOO_LONG, D7_DETAIL)
    text = " ".join(f"{_CIRCLED[k]}{items[i][0]}" for k, i in enumerate(idx)) + "（原句見上）"
    excluded = len(items) - len(idx)
    if excluded:
        text += f"｜未列入觀察重點 {excluded} 句（超過預覽暫行字數上限）"
    return _d(L_POINTS, text, D7_DETAIL)


@dataclass(frozen=True)
class TopicView:
    topic: str
    fields: tuple


def _unavailable(topic: str, core_detail: str, gap: str, source: str = SRC_NONE) -> TopicView:
    return TopicView(topic, (_d(L_DEMO, VM.DISCLOSURE_FIRST), _undeterminable(L_CORE, core_detail), _points_row(()),
                             _d(L_GAP, gap), _d(L_SRC, source)))


def _degraded(topic: str) -> TopicView:
    return _unavailable(topic, f"{topic}：{VM.FAILCLOSED_NOTE}", GAP_DEGRADED)      # 帶主題名：切換主題在降級時也看得到有反應


def _chain(case_id: str):
    """合成 Digest＋規則式摘要（與 `demo.build_case_block` 同一條離線鏈，經 `demo.assemble` ⇒ 測試可介入）。"""
    case = demo.CASES[case_id]
    res = demo.A.adapt_holdings_read(case.snapshot)
    a = demo.assemble(case, res.rows_for_digest())
    return a.digest, demo.S.build_rule_summary(a.digest)


def _lines(summary, *keys) -> tuple:
    lines = dict(summary.lines)
    out = []
    for k in keys:
        got = lines.get(k)
        if not got or any(type(x) is not str or not x for x in got):
            raise TopicError(f"Digest 段 {k} 缺句或非字串")
        out += list(got)
    return tuple(out)


def _cited_refs(summary, *keys) -> list:
    out: list = []
    for sec in summary.sections:
        if sec.key in keys:
            for sent in sec.sentences:
                for seg in sent.segments:
                    if isinstance(seg, Ref) and seg.ref_id not in out:
                        out.append(seg.ref_id)
    return out


def _cited_evidence(ref_ids) -> tuple:
    """Digest 原句所引用的欄位：`section:*`／`holding:*` 引用本身沒有 source／as_of／status ⇒ 照實「無」。"""
    return tuple(Evidence("cite", rid, CITED_CLAIM, None, None, None, False) for rid in ref_ids)


def _holdings_gaps(digest) -> str:
    h = digest.holdings
    gaps = []
    if h.missing_reason is not None:
        gaps.append(f"持股資料：{MISSING_REASON_LABELS[h.missing_reason.value]}")
    if h.unkeyed_count > 0:
        gaps.append(f"{MARK_UNKEYED} {h.unkeyed_count} 檔")
    n_unset = sum(1 for e in h.entries if e.strategy is StrategyType.UNCLASSIFIED)
    if n_unset > 0:
        gaps.append(f"{MARK_STRATEGY_UNSET} {n_unset} 檔")
    return "；".join([*gaps, "支持證據：無"])


def _view_market() -> TopicView:
    return _unavailable(TOPIC_MARKET, MARKET_DETAIL, GAP_MARKET)


def _view_industry(case_id: str) -> TopicView:
    _digest, summary = _chain(case_id)
    sents = _lines(summary, "industry")
    if len(sents) != 1:
        raise TopicError("產業段應恰有 1 句")
    reason = check_core(sents)
    if reason is not None:
        return _unavailable(TOPIC_INDUSTRY, _over_limit_detail(reason), GAP_INDUSTRY, SRC_INDUSTRY)
    sup = [evidence_field(e) for e in _cited_evidence(_cited_refs(summary, "industry"))]
    # 核心觀察列與大盤／反方風險同一種狀態標記（⬜ 無法判定徽章＋judgement/undeterminable）；Digest 原句逐字放在徽章列的說明行。
    return TopicView(TOPIC_INDUSTRY, (_d(L_DEMO, VM.DISCLOSURE_FIRST), _undeterminable(L_CORE, sents[0]), _points_row([(L_CORE, sents[0])]), *sup,
                                      _d(L_GAP, GAP_INDUSTRY), _d(L_SRC, SRC_INDUSTRY)))


def _view_holdings(case_id: str) -> TopicView:
    digest, summary = _chain(case_id)
    sents = [(VM.SECTION_TO_LABEL[k], t) for k in ("buy_and_hold", "capital_gain") for t in _lines(summary, k)]
    gap_text = _holdings_gaps(digest)
    reason = check_core([t for _l, t in sents])
    if reason is not None:
        return TopicView(TOPIC_HOLDINGS, (
            _d(L_DEMO, VM.DISCLOSURE_FIRST),
            _undeterminable(L_CORE, _over_limit_detail(reason)),
            _points_row(()), _d(L_GAP, gap_text), _d(L_SRC, SRC_HOLDINGS)))
    rows = [_d(L_DEMO, VM.DISCLOSURE_FIRST)]
    if digest.holdings.availability is not Availability.AVAILABLE:
        rows.append(_undeterminable(L_JUDGE, VM.DERIVED_FOOTNOTE))
    rows += [_d(label, text) for label, text in sents]                  # 逐字：不 strip、不改寫、不重排
    rows.append(_points_row(sents))
    rows += [evidence_field(e) for e in _cited_evidence(_cited_refs(summary, "buy_and_hold", "capital_gain"))]
    note = VM.NOTE_D3 if any(VM.NOTE_TRIGGER in t for _l, t in sents) else None
    rows.append(_d(L_GAP, gap_text, note))
    rows.append(_d(L_SRC, SRC_HOLDINGS))
    return TopicView(TOPIC_HOLDINGS, tuple(rows))


def _view_risk(case_id: str) -> TopicView:
    items = counter_fixture(case_id)
    if not items:
        return _unavailable(TOPIC_RISK, RISK_NO_INPUT_DETAIL, GAP_RISK_NO_INPUT)
    n_stale = sum(1 for e in items if e.status is DataStatus.STALE)
    core = f"FAKE-SYN 合成示意：有 {len(items)} 筆合成反面證據（其中 {n_stale} 筆資料已過期），僅供版面示意，非正式內容"
    reason = check_core([core])
    if reason is not None:
        raise TopicError(reason)
    return TopicView(TOPIC_RISK, (_d(L_DEMO, VM.DISCLOSURE_FIRST), _d(L_CORE, core), _points_row([(L_CORE, core)]),
                                  *[evidence_field(e) for e in items], _d(L_GAP, GAP_RISK_FIXTURE), _d(L_SRC, SRC_RISK_FIXTURE)))


_BUILDERS = {TOPIC_INDUSTRY: _view_industry, TOPIC_HOLDINGS: _view_holdings, TOPIC_RISK: _view_risk}


def build_topic_view(topic: str, case_id: str, *, fail_closed: bool) -> TopicView:
    """（主題, 案例）⇒ 該主題的行內版面。未知主題 ⇒ ValueError、未知案例 ⇒ KeyError（呼叫端錯誤，照常往上拋）。
    `fail_closed`（launcher 讓 `assemble_digest` 暫時 raise）或建構途中任何例外 ⇒ 固定的誠實降級（記 log 只含例外型別名，⛔ 不記訊息）。
    大盤主題與 Digest 無關（C3 未裁示 ⇒ 恆 unavailable），所以 fail-closed 時也維持同一個誠實畫面。"""
    if topic not in TOPICS:
        raise ValueError(f"未知主題：{topic!r}（{TOPICS}）")
    if case_id not in demo.CASES:
        raise KeyError(case_id)
    if topic == TOPIC_MARKET:
        return _view_market()
    if fail_closed:
        return _degraded(topic)
    try:
        return _BUILDERS[topic](case_id)
    except Exception as e:  # noqa: BLE001 — 降級成固定 fail-closed 版面；記 log（只記型別名）
        _log.warning("onebrain topics demo %s/%s fail-closed: %s", topic, case_id, type(e).__name__)
        return _degraded(topic)


def build_topic_section(topic: str, case_id: str, *, fail_closed: bool) -> SectionVM:
    """單一 `onebrain` L1 SectionVM（與預設槽同 section_id／level；標題帶主題名）。"""
    view = build_topic_view(topic, case_id, fail_closed=fail_closed)
    return SectionVM(section_id=VM.SECTION_ID, title=f"{VM.SECTION_TITLE}｜{view.topic}", level=VM.SECTION_LEVEL, fields=view.fields)


def test_info_text(case_id: str) -> str:
    """槽外「測試輸入說明」＝既有整句（合成測試輸入；與主題無關）。"""
    return VM.test_info_text(case_id)
