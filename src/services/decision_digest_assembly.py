"""L3 Service — Decision Digest Headless 組裝（Issue #1127 P-4：S7 headless 組裝＋S8 省略揭露）。

═══ 這個檔是什麼 ═══════════════════════════════════════════════════════
`assemble_digest` 是一支**純函式**，把「各段上游輸出＋各段證據（日期戳／新鮮度／抓取結果）」組成
`AssembledDigest(digest, coverage)` envelope：

- **S7 headless**：不讀 `st.session_state`、不取數、不呼叫時鐘、不碰 UI／app；呼叫端（未來的 canonical
  service）把證據明確傳進來，不因「使用者有沒有按『更新今日戰情』」而讓內容不同
  （契約 §2.1／§9；`P1R-DIGEST-HEADLESS-ASSEMBLY` 的組裝點）。
- **S8 省略揭露**：Digest v1 凍結，行動在形成前就被截到 `MAX_ACTIONS`、資料異常列被靜默排除、
  無鍵持股只剩一個計數。完整性由**側車** `shared.decision_digest_coverage.DigestCoverage` 攜帶
  （理由與設計鐵則見該檔 docstring）；Digest 本身一個欄位都沒有動。

═══ 證據規則（fail-closed，不自創門檻）════════════════════════════════
一段證據（`EvidenceInput`）只有**同時**滿足下列條件才會把 `SourceStamp` 交給 `build_decision_digest`：
1. 有 `stamp`；
2. `upstream_state` 不是 `FETCH_FAILED`／`UNDETERMINED`（`NO_NEW_DATA` 與 None 不擋）；
3. `freshness is FreshnessStatus.FRESH`（`STALE`／`MISSING`／`UNDETERMINED`／None 一律不採用）；
4. 時序（PIT）通過：沿用 Digest／Provenance 既有規則——`as_of` ≤ `fetched_at` 的台北日、
   `fetched_at` ≤ `generated_at`、`as_of` ≤ `generated_at` 的台北日（不自創）。

⚠️ **兩軸不互相蘊含**（`shared/fetch_outcome.py`／`shared/upstream_state.py` 檔頭）：
`NO_NEW_DATA` ≠ 資料新鮮（來源可能本來就很久沒更新）→ `NO_NEW_DATA × STALE` 仍然不採用；
`FETCH_FAILED` ≠ 資料過期，但「這次抓取失敗」時不採用該段證據（保守），並在 coverage 記錄 `fetch_failed`。

不採用 = 該段的 stamp 不傳 **且** 該段的上游輸出也不傳（`macro_state`／`allocation` 或 `station_rows` 設為 None）。
理由：stamp 被拒時若仍把 `macro_state` 交給 builder，`risk_cap.cap_pct` 會以快照時間（另一個日期）
變成 OK，讓一份「證據被拒用」的資料仍以 OK 進 Digest。builder 對缺 stamp 的處置（MISSING＋NO_INPUT）
不變；本檔**不補日期、不補 0、不補 neutral／HOLD**，也不把 builder 的 MISSING 描述成「安全」。

═══ coverage 的語意（描述「證據」，不是描述 Digest 段落的 availability）══════════
- market／risk_cap：該段的**全部**事實皆為 OK 才 `used=True`；否則 `used=False`＋原因
  （證據被拒用 → 該證據的原因；證據可用但上游沒載入 → `not_loaded`；只採到一部分 → `partial`）。
  risk_cap 段的 source／as_of 記的是**證據戳**（macro stamp）；快照時間（`snapshot_ts`）在 Digest 的事實上。
- holdings／actions：v1 的 holdings entry 只有行動事實，兩段都由「站內證據＋`holdings_rows`＋`station_rows`」
  決定；全部就緒才 `used=True`。⚠️ v1 builder 對「沒有任何行動」會讓 holdings／actions 段為
  UNAVAILABLE（無法區分「沒事做」與「判不出來」）；coverage 不改寫這點，只說「證據有沒有被讀進來、
  有幾個候選被省略」。
- 計數：不能評估 → None（**不是 0**）。`is_complete` 為 False。

分層（CLAUDE.md §8.2）：L3 —— 只 import 標準函式庫、L0（`shared.*`）與同層
`src.services.decision_digest_builder`；⛔ streamlit／`src.ui*`／`app`／requests／`src.data`／session／
時鐘（`now()`／`today()`）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from shared.decision_digest import (
    MAX_ACTIONS, TW_TZ, Availability, DataStatus, DecisionDigest, HoldingKey,
)
from shared.decision_digest_coverage import (
    SEGMENT_ACTIONS, SEGMENT_HOLDINGS, SEGMENT_MARKET, SEGMENT_RISK_CAP, WITHHELD_FETCH_FAILED,
    WITHHELD_NO_STAMP, WITHHELD_NOT_LOADED, WITHHELD_PARTIAL, WITHHELD_PIT_VIOLATION, WITHHELD_STALE,
    WITHHELD_UNDETERMINED, DigestCoverage, SegmentEvidence, assert_coverage_valid,
)
from shared.decision_digest_rules import assert_strict
from shared.fetch_outcome import FetchOutcome
from shared.freshness_policy import FreshnessStatus
from src.services.decision_digest_builder import (
    SourceStamp, build_decision_digest, plan_action_selection,
)


# ══════════════════════════════════════════════════════════════════════
# 證據輸入
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class EvidenceInput:
    """一段上游輸出的證據（呼叫端明確提供；本檔不自己判新鮮度、不自己產生日期）。

    - `stamp`：資料日戳（`SourceStamp`）；None＝沒有日期戳。
    - `freshness`：沿用 `shared.freshness_policy.FreshnessStatus`（呼叫端依 L0 規則判好再傳入）；
      None＝呼叫端沒判，視同無法判定（**不採用**）。
    - `upstream_state`：沿用 `shared.fetch_outcome.FetchOutcome`（`shared.upstream_state.classify_upstream` 的輸出）；
      None＝沒有上游問題。
    型別不對 → `TypeError`（Fail Loud；不接受字串冒充列舉）。
    """
    stamp: SourceStamp | None = None
    freshness: FreshnessStatus | None = None
    upstream_state: FetchOutcome | None = None

    def __post_init__(self) -> None:
        if self.stamp is not None and type(self.stamp) is not SourceStamp:
            raise TypeError(f"EvidenceInput.stamp 必須是 SourceStamp 或 None：{type(self.stamp).__name__}")
        if self.freshness is not None and type(self.freshness) is not FreshnessStatus:
            raise TypeError(f"EvidenceInput.freshness 必須是 FreshnessStatus 或 None：{type(self.freshness).__name__}")
        if self.upstream_state is not None and type(self.upstream_state) is not FetchOutcome:
            raise TypeError(
                f"EvidenceInput.upstream_state 必須是 FetchOutcome 或 None：{type(self.upstream_state).__name__}")


def _pit_ok(stamp: SourceStamp, generated_at: datetime) -> bool:
    """時序（PIT）檢查：只用 Digest／Provenance 既有規則（`shared/decision_digest.py`），不自創。"""
    if stamp.as_of > generated_at.astimezone(TW_TZ).date():          # as_of_after_generated
        return False
    if stamp.fetched_at is not None:
        if stamp.as_of > stamp.fetched_at.astimezone(TW_TZ).date():  # as_of_after_fetched
            return False
        if stamp.fetched_at > generated_at:                          # fetched_after_generated
            return False
    return True


def _classify(evidence: EvidenceInput | None, generated_at: datetime) -> str | None:
    """證據可用 → None；否則回 `WITHHELD_*` 原因（先到先得：無戳 → 抓取結果 → 新鮮度 → 時序）。"""
    if evidence is None or evidence.stamp is None:
        return WITHHELD_NO_STAMP
    if evidence.upstream_state is FetchOutcome.FETCH_FAILED:
        return WITHHELD_FETCH_FAILED
    if evidence.upstream_state is FetchOutcome.UNDETERMINED:
        return WITHHELD_UNDETERMINED
    # NO_NEW_DATA／None 不擋，但**不蘊含**新鮮：一律還要看 freshness 軸。
    if evidence.freshness is FreshnessStatus.FRESH:
        return None if _pit_ok(evidence.stamp, generated_at) else WITHHELD_PIT_VIOLATION
    if evidence.freshness is FreshnessStatus.STALE:
        return WITHHELD_STALE
    if evidence.freshness is FreshnessStatus.MISSING:
        return WITHHELD_NO_STAMP
    return WITHHELD_UNDETERMINED   # UNDETERMINED 或 None（沒判 ＝ 不採用）


def _seg(name: str, evidence: EvidenceInput | None, *, used: bool, reason: str | None) -> SegmentEvidence:
    """source／as_of 取證據戳（被拒用時「若有」才帶；沒有就是 None，不補）。"""
    stamp = evidence.stamp if evidence is not None else None
    return SegmentEvidence(segment=name, used=used,
                           source=stamp.source if stamp is not None else None,
                           as_of=stamp.as_of if stamp is not None else None,
                           withheld_reason=None if used else reason)


def _all_ok(facts: Sequence) -> bool:
    return len(facts) > 0 and all(f.status is DataStatus.OK for f in facts)


# ══════════════════════════════════════════════════════════════════════
# envelope
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class AssembledDigest:
    """`DecisionDigest` ＋ 側車 `DigestCoverage`。建構時強制兩者一致，不一致 → `ValueError`。

    `assemble_digest` 是**唯一**由證據推導 coverage 的入口；直接建構也會被同一套一致性檢查擋下，
    所以不可能存在「coverage 與 digest 對不上」的 `AssembledDigest`。
    """
    digest: DecisionDigest
    coverage: DigestCoverage

    def __post_init__(self) -> None:
        problems = _consistency_problems(self.digest, self.coverage)
        if problems:
            raise ValueError("AssembledDigest：coverage 與 digest 不一致：\n  " + "\n  ".join(problems))

    def to_dict(self) -> dict:
        """envelope dict：`{"digest": <Digest v1 原樣>, "coverage": <側車>}`（決定性）。"""
        return {"digest": self.digest.to_dict(), "coverage": self.coverage.to_dict()}


def _consistency_problems(digest: Any, coverage: Any) -> list:
    if type(digest) is not DecisionDigest:
        return [f"digest 必須是 DecisionDigest：{type(digest).__name__}"]
    if type(coverage) is not DigestCoverage:
        return [f"coverage 必須是 DigestCoverage：{type(coverage).__name__}"]
    out: list = []
    try:
        assert_coverage_valid(coverage)
        assert_strict(digest)
    except ValueError as e:   # 各自的契約違規：照實回報，不再做後續比對（欄位可能不可信）
        return [str(e)]

    shown = len(digest.actions.items)
    if coverage.actions_shown != shown:
        out.append(f"actions_shown({coverage.actions_shown}) != len(digest.actions.items)({shown})")
    if coverage.actions_max != MAX_ACTIONS:
        out.append(f"actions_max({coverage.actions_max}) != MAX_ACTIONS({MAX_ACTIONS})")
    total = coverage.actions_total_eligible
    if total is not None and shown != min(total, coverage.actions_max):
        out.append(f"shown({shown}) 必須等於 min(total({total}), max({coverage.actions_max}))")

    # 無鍵持股：已知 → 必須與 Digest 的計數相同；未知(None) → Digest 的 0 只是「未知」，holdings 必為 UNAVAILABLE
    hs = digest.holdings
    if coverage.unkeyed_held_count is not None:
        if coverage.unkeyed_held_count != hs.unkeyed_count:
            out.append(f"unkeyed_held_count({coverage.unkeyed_held_count}) != "
                       f"digest.holdings.unkeyed_count({hs.unkeyed_count})")
    elif hs.availability is not Availability.UNAVAILABLE or hs.unkeyed_count != 0:
        out.append("unkeyed_held_count 為 None（未知）時，digest.holdings 必須是 unavailable 且 unkeyed_count==0")

    seg = {s.segment: s for s in coverage.segments}
    # market／risk_cap：used ⇔ 該段全部事實為 OK
    market_ok = _all_ok(digest.market.facts)
    if seg[SEGMENT_MARKET].used != market_ok:
        out.append(f"market 段 used({seg[SEGMENT_MARKET].used}) 與事實狀態（全 OK＝{market_ok}）不一致")
    rc = digest.risk_cap
    rc_ok = _all_ok((rc.cap_pct, rc.exposure_lo_pct, rc.exposure_hi_pct))
    if seg[SEGMENT_RISK_CAP].used != rc_ok:
        out.append(f"risk_cap 段 used({seg[SEGMENT_RISK_CAP].used}) 與事實狀態（全 OK＝{rc_ok}）不一致")
    # holdings／actions：未採用 ⇒ Digest 不得帶任何行動事實／行動
    if not seg[SEGMENT_HOLDINGS].used and any(e.facts for e in hs.entries):
        out.append("holdings 段 used=False 但 digest.holdings 帶有行動事實")
    if not seg[SEGMENT_ACTIONS].used and shown != 0:
        out.append("actions 段 used=False 但 digest.actions 帶有行動")
    if seg[SEGMENT_ACTIONS].used and total is None:
        out.append("actions 段 used=True 但 actions_total_eligible 為 None")
    return out


# ══════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════
def _check_dropped_input_types(macro_state: Any, allocation: Any, station_rows: Any) -> None:
    """證據被拒用時這三個輸入不會交給 builder（builder 因而不會驗型別）；型別錯誤仍須 Fail Loud，
    不得因「證據剛好被拒用」就悄悄放過（與 builder 同一套規則）。"""
    if macro_state is not None and not isinstance(macro_state, Mapping):
        raise TypeError(f"macro_state 必須是 Mapping 或 None：{type(macro_state).__name__}")
    if allocation is not None and not all(hasattr(allocation, a) for a in ("is_loaded", "final_lo", "final_hi")):
        raise TypeError(f"allocation 必須是 None 或帶 is_loaded／final_lo／final_hi 的物件：{type(allocation).__name__}")
    if station_rows is not None and type(station_rows) not in (list, tuple):
        raise TypeError(f"station_rows 必須是 list／tuple 或 None：{type(station_rows).__name__}")


def assemble_digest(*, generated_at: datetime,
                    macro_state: Mapping | None = None,
                    macro_evidence: EvidenceInput | None = None,
                    allocation: Any = None,
                    station_rows: Sequence[Mapping] | None = None,
                    station_evidence: EvidenceInput | None = None,
                    holdings_rows: Sequence[Mapping] | None = None,
                    holding_keys: Mapping[str, HoldingKey] | None = None) -> AssembledDigest:
    """純函式、無 I/O：依證據規則（見模組 docstring）組出 `AssembledDigest`。

    macro 證據同時管 market 與 risk_cap（兩段共用 `macro_state`／`allocation`）；站內證據管 holdings 與 actions。
    輸入型別不對 → `TypeError`（沿用 builder 的驗證）；違反 Digest 契約（例如重複的持股鍵）→ `ValueError`。
    """
    if type(generated_at) is not datetime or generated_at.utcoffset() is None:
        raise ValueError(f"generated_at 必須是 tz-aware datetime（本檔不呼叫時鐘）：{generated_at!r}")
    for name, ev in (("macro_evidence", macro_evidence), ("station_evidence", station_evidence)):
        if ev is not None and type(ev) is not EvidenceInput:
            raise TypeError(f"{name} 必須是 EvidenceInput 或 None：{type(ev).__name__}")

    _check_dropped_input_types(macro_state, allocation, station_rows)
    macro_reason = _classify(macro_evidence, generated_at)
    station_reason = _classify(station_evidence, generated_at)
    macro_usable = macro_reason is None
    station_usable = station_reason is None

    # 證據被拒用 ⇒ 該段的 stamp **與**上游輸出都不傳（見模組 docstring）
    digest = build_decision_digest(
        generated_at=generated_at,
        macro_state=macro_state if macro_usable else None,
        macro_stamp=macro_evidence.stamp if macro_usable else None,
        allocation=allocation if macro_usable else None,
        station_rows=station_rows if station_usable else None,
        station_stamp=station_evidence.stamp if station_usable else None,
        holdings_rows=holdings_rows,
        holding_keys=holding_keys,
    )
    plan = plan_action_selection(
        station_rows=station_rows if station_usable else None,
        station_stamp=station_evidence.stamp if station_usable else None,
        holdings_rows=holdings_rows, holding_keys=holding_keys)

    # ── 各段證據 ──
    macro_loaded = isinstance(macro_state, Mapping) and macro_state.get("is_loaded") is True
    market_all_ok = _all_ok(digest.market.facts)
    rc = digest.risk_cap
    rc_all_ok = _all_ok((rc.cap_pct, rc.exposure_lo_pct, rc.exposure_hi_pct))

    def fact_segment(name: str, all_ok: bool, loaded: bool) -> SegmentEvidence:
        if not macro_usable:
            return _seg(name, macro_evidence, used=False, reason=macro_reason)
        if all_ok:
            return _seg(name, macro_evidence, used=True, reason=None)
        return _seg(name, macro_evidence, used=False, reason=WITHHELD_PARTIAL if loaded else WITHHELD_NOT_LOADED)

    # holdings／actions：站內證據可用、且持有列與站內列都有給、且計畫可評估 → 採用
    if not station_usable:
        station_state, station_why = False, station_reason
    elif not plan.evaluated:
        station_state, station_why = False, WITHHELD_NOT_LOADED
    else:
        station_state, station_why = True, None

    segments = (
        fact_segment(SEGMENT_MARKET, market_all_ok, macro_loaded),
        fact_segment(SEGMENT_RISK_CAP, rc_all_ok, isinstance(macro_state, Mapping)),
        _seg(SEGMENT_HOLDINGS, station_evidence, used=station_state, reason=station_why),
        _seg(SEGMENT_ACTIONS, station_evidence, used=station_state, reason=station_why),
    )
    coverage = DigestCoverage(
        actions_total_eligible=plan.total_eligible,
        actions_shown=len(digest.actions.items),
        actions_omitted_count=plan.omitted_count,
        actions_max=MAX_ACTIONS,
        excluded_invalid_rows=plan.excluded_invalid_rows,
        unkeyed_held_count=plan.unkeyed_held_count,
        segments=segments,
    )
    return AssembledDigest(digest=digest, coverage=coverage)


__all__ = ["EvidenceInput", "AssembledDigest", "assemble_digest"]
