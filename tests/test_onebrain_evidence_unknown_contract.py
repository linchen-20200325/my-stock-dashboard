"""C-OB-EVIDENCE-UNKNOWN-TESTS — OneBrain「證據不可用 ⇒ unknown」離線契約快照（fast lane；tests-only）。

**離線測試護欄，不增加可用性、不修復 Top-N 輸入錯誤、不是 OneBrain 已可用。**
授權：Issue #1199 GPT 總管裁示 https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7038579891
（決策 1：候選 A「CONDITIONAL APPROVE tests-only 最小 PR」），脈絡
https://github.com/linchen-20200325/my-stock-dashboard/issues/1199#issuecomment-7037529004 。

═══ 本檔釘什麼（只釘「目前真實契約」與「明示危險反例」）══════════════════════════
1. 不可用原因（no_stamp／stale／fetch_failed／undetermined／pit_violation）在現行 Digest v1 與規則式摘要下
   **保持缺值**：不同原因產出逐字相同的 `digest.to_dict()` 與 `build_rule_summary(...).lines`，
   原因只存在 coverage 側車的 `withheld_reason`。
2. `ProviderRequest` 目前欄位恰為 `{digest, task}`：Provider 看不到 coverage／原因。
3. **KNOWN_UNFIXED_RISK**：Top-N 截斷。7 筆合格行動 ⇒ coverage 為 total=7／shown=3／omitted=4／`is_complete=False`；
   若把摘要只列出的 Top-3 **回灌**為輸入 ⇒ coverage 變 total=3／omitted=0／`is_complete=True`（**錯判完整性**）。
4. stale／fetch_failed／PIT／unavailable 時，未使用的資料不得以 0／OK／正常／安全代替 unknown。

═══ ⚠️ 必讀：這些是「目前契約快照」，不是「永久禁止演進」══════════════════════════
- 斷言 1、2：屬 Digest v1／現行 Provider 契約的**快照**。未來若經 OB-1-D3／Digest v2 **正式批准**
  讓摘要或 Provider 帶出缺值原因，**應同步更新本檔對應斷言（那不是回歸）**；本檔不得被引用來阻止合理演進，
  只要求「演進必須是被批准的、並顯式改測試」，而不是被悄悄洗掉。
- 斷言 3：回灌後 `is_complete=True` 是**已知的錯誤行為**，**不是**產品契約；本檔沒有宣稱它正確，
  只釘「它與完整輸入的結論不同」這個**危險事實**。若日後 assembler 被修好（例如能偵測截斷），
  本檔該測試**會轉紅 —— 屆時須同步更新（改為斷言修復後的行為），這是預期的**。
  ⛔ `assemble_digest` **無法偵測**輸入是否已被截斷；「Evidence 必須由未來 headless evidence builder 使用
  **完整 eligible input**、**不能由 UI Top-N 反推**」是另需實作的**硬性 invariant／Gate**
  （BACKLOG `OB-ASSEMBLER-FULL-INPUT-INVARIANT`），**本 tests-only PR 不阻止任何實際 production caller 截斷**，
  也不放行 Stage F。

═══ 邊界 ═════════════════════════════════════════════════════════════════
確定性、匿名合成（重用 `tests/onebrain_anon_demo` 的固定合成輸入，只讀）、0 付費 API、0 外部 IO、不呼叫時鐘；
本檔 AST 不直接 import streamlit／網路客戶端／LLM SDK。不修改任何 src／shared／既有測試。
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import pathlib
from datetime import date

import pytest

from shared.decision_digest import Availability, DataStatus
from shared.decision_digest_coverage import (
    SEGMENT_ACTIONS, SEGMENT_HOLDINGS, SEGMENT_MARKET, SEGMENT_RISK_CAP, WITHHELD_FETCH_FAILED,
    WITHHELD_NO_STAMP, WITHHELD_PIT_VIOLATION, WITHHELD_STALE, WITHHELD_UNDETERMINED,
)
from shared.fetch_outcome import FetchOutcome
from shared.freshness_policy import FreshnessStatus
from shared.onebrain_provider import ProviderRequest
from src.services.decision_digest_assembly import EvidenceInput, assemble_digest
from src.services.decision_digest_builder import SourceStamp
from src.services.decision_digest_summary import build_rule_summary
from src.services.onebrain_shadow import run_shadow
from tests import onebrain_anon_demo as demo
from tests.onebrain_fake_provider import FakeProvider
from tests.test_ui2_no_second_ai_guard import scan_no_second_ai

THIS_FILE = pathlib.Path(__file__).resolve()

# ── 五種「證據不可用」原因（以實際 assemble_digest 可表達者為準；皆由輸入推導，不注入內部狀態）──────
#: reason → (EvidenceInput 工廠, 預期 coverage.withheld_reason)。每個案例都帶**不同 source 名稱**的戳（no_stamp 除外，
#: 它本來就沒有戳），這樣「被拒用證據的內容外洩進 Digest」會讓各原因的 Digest 變得不同而被抓到。
_FUTURE = date(2000, 1, 5)    # 晚於 demo 的 generated_at 台北日（2000-01-04）＝ PIT 違反（合成日期）


def _stamp(tag: str, as_of: date = demo._ASOF) -> SourceStamp:
    return SourceStamp(f"synthetic-{tag}", as_of)


UNAVAILABLE_REASONS = {
    "no_stamp": (lambda: EvidenceInput(None, FreshnessStatus.FRESH), WITHHELD_NO_STAMP),
    "stale": (lambda: EvidenceInput(_stamp("stale"), FreshnessStatus.STALE), WITHHELD_STALE),
    "fetch_failed": (lambda: EvidenceInput(_stamp("fetch_failed"), FreshnessStatus.FRESH, FetchOutcome.FETCH_FAILED),
                     WITHHELD_FETCH_FAILED),
    "undetermined": (lambda: EvidenceInput(_stamp("undetermined"), FreshnessStatus.UNDETERMINED),
                     WITHHELD_UNDETERMINED),
    "pit_violation": (lambda: EvidenceInput(_stamp("pit_violation", _FUTURE), FreshnessStatus.FRESH),
                      WITHHELD_PIT_VIOLATION),
}
SIDES = {"macro": (SEGMENT_MARKET, SEGMENT_RISK_CAP), "station": (SEGMENT_HOLDINGS, SEGMENT_ACTIONS)}
#: 站內側「不可評估 ⇒ 必須是 None（未知不是 0）」的計數欄位（與 coverage validator 的 `_eval_counts` 同集合）。
STATION_COUNT_FIELDS = (
    "actions_total_eligible", "actions_omitted_count", "excluded_invalid_rows", "station_rows_unmatched",
    "holdings_without_station_row", "station_non_mapping_rows", "unrecognized_action_code_rows",
    "duplicate_station_ticker_rows",
)
#: 「把缺資料描述成沒事」的字眼（斷言 4：摘要與 coverage 輸出不得出現）。
FORBIDDEN_REASSURANCE = ("正常", "中性", "安全", "neutral", "safe")


def _assemble(side: str, reason: str):
    factory, _ = UNAVAILABLE_REASONS[reason]
    return assemble_digest(**demo._kwargs(2, **{f"{side}_evidence": factory()}))


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _all_keys(obj) -> set:
    out: set = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            out |= _all_keys(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= _all_keys(v)
    return out


def _seg_map(a) -> dict:
    return {s.segment: s for s in a.coverage.segments}


# ════════════════════════════════════════════════════════════════════
# 斷言群 1：不同不可用原因 ⇒ Digest／摘要逐字相同；原因只在 coverage
#   （目前契約快照；OB-1-D3／Digest v2 正式批准後可同步更新，不是回歸）
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("side", sorted(SIDES))
def test_coverage_carries_distinct_reasons_for_each_unavailable_cause(side):
    """各原因在 coverage 的 withheld_reason 各自不同，且等於預期原因（該側兩段皆是）。"""
    seen = {}
    for reason, (_, expected) in UNAVAILABLE_REASONS.items():
        a = _assemble(side, reason)
        segs = _seg_map(a)
        for name in SIDES[side]:
            assert segs[name].used is False, (side, reason, name)
            assert segs[name].withheld_reason == expected, (side, reason, name)
        seen[reason] = _canon(a.coverage.to_dict())
    assert len(set(seen.values())) == len(UNAVAILABLE_REASONS), "不同原因的 coverage 應可區分"
    assert len({UNAVAILABLE_REASONS[r][1] for r in UNAVAILABLE_REASONS}) == len(UNAVAILABLE_REASONS)


@pytest.mark.parametrize("side", sorted(SIDES))
def test_current_v1_digest_is_verbatim_identical_across_unavailable_reasons(side):
    """CURRENT CONTRACT SNAPSHOT（Digest v1 無缺值原因欄；OB-1-D3）。用比較而非硬編碼：各原因的 Digest dict 逐字相同。
    同時證明被拒用證據的內容（各案例 source 名稱不同）沒有外洩進 Digest。"""
    digests = {r: _assemble(side, r).digest.to_dict() for r in UNAVAILABLE_REASONS}
    assert len({_canon(d) for d in digests.values()}) == 1, "不同不可用原因不應改變 Digest v1 內容"
    some = next(iter(digests.values()))
    assert "withheld_reason" not in _all_keys(some)                 # Digest 沒有缺值原因欄
    blob = _canon(some)
    assert not any(f"synthetic-{r}" in blob for r in UNAVAILABLE_REASONS if r != "no_stamp"), "被拒用證據的來源不得進 Digest"


@pytest.mark.parametrize("side", sorted(SIDES))
def test_current_v1_rule_summary_is_verbatim_identical_across_unavailable_reasons(side):
    """CURRENT CONTRACT SNAPSHOT：規則式摘要字面不區分 stale／fetch_failed／pit／no_stamp／undetermined。"""
    lines = {r: build_rule_summary(_assemble(side, r).digest).lines for r in UNAVAILABLE_REASONS}
    assert len({_canon(v) for v in lines.values()}) == 1, "不同不可用原因不應改變規則式摘要字面"


def test_reasons_do_not_appear_in_summary_text():
    """原因字串（機器常數）不得出現在摘要字面 —— 原因只留在 coverage 側車（目前契約快照）。"""
    machine_reasons = {v[1] for v in UNAVAILABLE_REASONS.values()}
    for side in SIDES:
        for reason in UNAVAILABLE_REASONS:
            text = _canon(build_rule_summary(_assemble(side, reason).digest).lines)
            assert not any(m in text for m in machine_reasons), (side, reason)


# ════════════════════════════════════════════════════════════════════
# 斷言群 2：ProviderRequest 目前恰為 {digest, task}
# ════════════════════════════════════════════════════════════════════
def test_provider_request_fields_are_exactly_digest_and_task():
    """CURRENT CONTRACT SNAPSHOT：Provider 看不到 coverage／withheld_reason，因此 stale、fetch_failed 與「尚無輸入」
    對 Provider 是同一件事。⛔ 不得據此宣稱 Provider（或任何只吃 ProviderRequest 的下游）能完整判斷資料可用性。
    若 OB-1-D3／Digest v2／OB-2 正式批准讓 Provider 看見 coverage，請同步更新本測試。"""
    assert {f.name for f in dataclasses.fields(ProviderRequest)} == {"digest", "task"}
    assert set(ProviderRequest.__annotations__) == {"digest", "task"}
    assert not any(n in {"coverage", "withheld_reason", "assembled", "segments"} for n in ProviderRequest.__annotations__)


def test_provider_actually_receives_a_request_without_coverage():
    """經 run_shadow 實跑一次：Provider 實際收到的請求物件沒有 coverage 資訊，且 run_shadow 只收 digest 與 provider。"""
    a = _assemble("macro", "stale")
    provider = FakeProvider("echo")
    run_shadow(a.digest, provider)
    assert provider.calls == 1
    (req,) = provider.requests
    assert type(req) is ProviderRequest
    assert set(vars(req)) == {"digest", "task"}
    assert not hasattr(req, "coverage") and not hasattr(req.digest, "coverage")
    assert list(inspect.signature(run_shadow).parameters) == ["digest", "provider"]   # 沒有傳 coverage 的通道


# ════════════════════════════════════════════════════════════════════
# 斷言群 3：Top-N 截斷反例（KNOWN_UNFIXED_RISK）
# ════════════════════════════════════════════════════════════════════
def _top_n_feedback_input(full):
    """把「摘要實際列出的 Top-N」反推回輸入（模擬『由 UI Top-N 反推 Evidence』的錯誤做法）。"""
    shown = [it.target.symbol for it in full.digest.actions.items]
    kw = demo._kwargs(7)
    kw["station_rows"] = [r for r in kw["station_rows"] if r["代號"] in shown]
    kw["holdings_rows"] = [r for r in kw["holdings_rows"] if r["ticker"] in shown]
    kw["holding_keys"] = {k: v for k, v in kw["holding_keys"].items() if k in shown}
    return kw, shown


def test_full_eligible_input_discloses_truncation_in_coverage():
    """完整輸入（7 筆合格行動，demo 情境 E 的輸入）：coverage 如實揭露 total=7／shown=3／omitted=4，且不完整。"""
    c = assemble_digest(**demo._kwargs(7)).coverage
    assert (c.actions_total_eligible, c.actions_shown, c.actions_omitted_count) == (7, 3, 4)
    assert c.is_complete is False


def test_KNOWN_UNFIXED_RISK_top_n_feedback_makes_truncated_input_look_complete():
    """KNOWN_UNFIXED_RISK（未修復）：把摘要只列出的 Top-3 回灌為輸入再組一次，coverage 變 total=3／omitted=0／complete
    —— **錯判完整性**：真正的候選有 7 筆、省略 4 筆。

    ⛔ 本測試**不是**在宣稱「回灌後 complete」是正確的產品契約；它釘的是危險事實：
    回灌後的 `is_complete` 與完整輸入的 `is_complete` **不同**，而消費端能看到的 Digest 行動與規則式摘要卻**一樣**
    —— 光看摘要無法分辨。`assemble_digest` 無法偵測輸入是否已被截斷；呼叫端契約（future headless evidence builder
    必須用完整 eligible input、不可由 UI Top-N 反推）另需實作為硬性 invariant／Gate
    （BACKLOG `OB-ASSEMBLER-FULL-INPUT-INVARIANT`）。本 tests-only PR **不阻止**任何 production caller 截斷。
    若日後 assembler 被修復使此測試轉紅：請改寫為斷言修復後的行為（預期的測試更新，不是回歸）。"""
    full = assemble_digest(**demo._kwargs(7))
    kw, shown = _top_n_feedback_input(full)
    assert len(shown) == 3 and len(kw["station_rows"]) == 3
    fed = assemble_digest(**kw)

    # 危險事實（必須同時成立）：完整性結論不同…
    assert fed.coverage.is_complete != full.coverage.is_complete
    assert full.coverage.is_complete is False
    # …現行錯誤行為快照（不是產品契約）：回灌後被當成完整、省略數歸 0
    assert (fed.coverage.actions_total_eligible, fed.coverage.actions_omitted_count) == (3, 0)
    # …而消費端看到的行動與規則式摘要與完整輸入一模一樣 —— 摘要本身不揭露被省略的 4 筆（OB-1-D3）
    assert fed.digest.actions == full.digest.actions
    assert build_rule_summary(fed.digest).lines == build_rule_summary(full.digest).lines


def test_assembler_has_no_input_channel_declaring_truncation():
    """assemble_digest 的簽章沒有任何能宣告「輸入是否已被截斷／是否為完整 eligible set」的參數 —— 這就是它『無法偵測』
    的結構性原因。CURRENT CONTRACT SNAPSHOT：未來經批准新增此類宣告（例如 headless builder 的完整性 invariant）
    時，應同步更新本測試。"""
    assert set(inspect.signature(assemble_digest).parameters) == {
        "generated_at", "macro_state", "macro_evidence", "allocation", "station_rows", "station_evidence",
        "holdings_rows", "holding_keys"}


# ════════════════════════════════════════════════════════════════════
# 斷言群 4：未使用資料不得以 0／OK／正常／安全代替 unknown
# ════════════════════════════════════════════════════════════════════
def _cases():
    cases = [(side, reason) for side in sorted(SIDES) for reason in UNAVAILABLE_REASONS]
    return cases


def _facts_of(a, segment: str) -> list:
    d = a.digest
    if segment == SEGMENT_MARKET:
        return list(d.market.facts)
    if segment == SEGMENT_RISK_CAP:
        return [d.risk_cap.cap_pct, d.risk_cap.exposure_lo_pct, d.risk_cap.exposure_hi_pct]
    return [f for e in d.holdings.entries for f in e.facts]


def _assert_not_reassuring(a) -> None:
    text = ("\n".join(s for _, ss in build_rule_summary(a.digest).lines for s in ss)
            + "\n" + _canon(a.coverage.to_dict())).lower()
    hit = [w for w in FORBIDDEN_REASSURANCE if w in text]
    assert not hit, f"缺資料不得被描述成正常／中性／安全：{hit}"


@pytest.mark.parametrize("side,reason", _cases())
def test_unavailable_evidence_is_unknown_not_zero_ok_or_safe(side, reason):
    a = _assemble(side, reason)
    c, segs = a.coverage, _seg_map(a)
    assert type(c.is_complete) is bool and c.is_complete is False          # False（布林），不是 None／真
    for name in SIDES[side]:
        assert segs[name].used is False
        assert segs[name].withheld_reason is not None
        facts = _facts_of(a, name)
        assert all(f.status is not DataStatus.OK for f in facts), (name, "未使用段不得有 OK 事實")
        assert all(f.value is None for f in facts), (name, "未使用段不得帶數值（0 也不行）")
    if side == "station":
        for field in STATION_COUNT_FIELDS:
            assert getattr(c, field) is None, f"{field} 應為 None（未知不是 0）"
        assert a.digest.actions.availability is Availability.UNAVAILABLE and a.digest.actions.items == ()
    else:
        assert a.digest.risk_cap.cap_valid is False
        assert a.digest.market.availability is not Availability.AVAILABLE
    _assert_not_reassuring(a)


def test_zero_evidence_everything_unknown_and_incomplete():
    """全段無證據（demo 情境 B）：四段皆未使用、站內計數皆 None、is_complete 為 False、無安心字眼。"""
    a = assemble_digest(generated_at=demo._NOW)
    assert all(s.used is False and s.withheld_reason is not None for s in a.coverage.segments)
    assert all(getattr(a.coverage, f) is None for f in STATION_COUNT_FIELDS)
    assert a.coverage.is_complete is False
    _assert_not_reassuring(a)


# ════════════════════════════════════════════════════════════════════
# 斷言 5：確定性 ＋ 衛生（本檔自身）
# ════════════════════════════════════════════════════════════════════
def test_results_are_deterministic():
    for side, reason in _cases():
        x, y = _assemble(side, reason), _assemble(side, reason)
        assert _canon(x.to_dict()) == _canon(y.to_dict())
        assert build_rule_summary(x.digest).lines == build_rule_summary(y.digest).lines


_BANNED_IMPORT_ROOTS = {"streamlit", "requests", "httpx", "aiohttp", "urllib", "urllib3", "socket", "time", "subprocess",
                        "random", "os"}
_BANNED_CLOCK_CALLS = {"now", "today", "utcnow", "monotonic", "perf_counter", "sleep", "urlopen", "getenv"}


def test_this_file_is_offline_and_clockless_by_ast():
    """本檔 AST：不直接 import streamlit／網路客戶端／LLM SDK／時鐘／隨機／環境變數，也不呼叫時鐘函式。
    （經由既有 tests helper 的傳遞性載入不算；LLM SDK 沿用 UI2 No-Second-AI 守衛的同一支掃描器。）"""
    source = THIS_FILE.read_text(encoding="utf-8")
    assert scan_no_second_ai(source) == []
    bad: list = []
    for n in ast.walk(ast.parse(source)):
        mods: list = []
        if isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mods = [n.module or ""]
        for m in mods:
            if m.split(".")[0] in _BANNED_IMPORT_ROOTS:
                bad.append(f"L{n.lineno}: import {m}")
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if name in _BANNED_CLOCK_CALLS:
                bad.append(f"L{n.lineno}: call {name}()")
    assert bad == []
