"""G-F4 / K2 組合式 `decision_digest.v2` — **tests-only 原型**（型別＋驗證器；Issue #1199）。

不是測試檔（檔名不以 test_ 開頭，不會被收集）；**不是 production 模組**：
- 只在 `tests/` 內被 import；`shared/`、`src/`、`app*.py`、`scripts/` 一律不得 import 本檔（0 production caller）。
- 授權：客戶 G-F3＝A2-i（#1199 7109632982）；總管 G-F4 範圍授權（7122310368：R1＝(a) tests-only、R2＝K2、
  R3／R4 照推薦；範圍細節見 7122175708 §B／§C）；設計來源 S1 v3.1（7110475027 §1）。
- **不是**正式型別、不是 DEC、不是 Contract；**不退役、不修改** `DigestCoverage`／`AssembledDigest`
  （S1 結束時兩者與本原型並存，沒有任何東西退役）。

═══ 設計（K2 組合根）═══════════════════════════════════════════════════
`DecisionDigestV2`（frozen）＝
  - `digest`：**原封不動**的 v1 `DecisionDigest`（唯讀欄位；`type(x) is DecisionDigest`，v1 驗證器與摘要管線可直接讀）；
  - `coverage`：`DigestCoverageV2` ＝ `base`（原封的 v1 `DigestCoverage`）＋ `audit`（`SegmentAudit` × 4，固定順序）；
  - `schema_version = "decision_digest.v2"`。
新欄**只有兩個**，且只在 `SegmentAudit`：
  - `evidence_freshness`：段級；值只能是 `FreshnessStatus.FRESH`／`FreshnessStatus.STALE` 或 `None`（None＝未判定）。
    ⚠️ 這是**呼叫端自報**，v2 **不可覆算**（無 producer；v2 不強制「STALE 不得冒充 fresh」——只檢查欄位間蘊含）。
    值域嚴格要求 `FreshnessStatus` 成員本身（裸字串 "fresh" 一律拒收）。
  - `fetched_at`：擷取時間（tz-aware datetime 或 None）。**≠ 資料可用日**；本檔刻意**沒有**任何「可用日」欄位
    （PIT 因此只有單向上界：擋得了未來日，擋不了很舊的假日期）。

═══ 刻意「沒有」的東西（授權明文排除；有人加進來＝越權）═══════════════════
- 任何 v1↔v2 互轉函式、由 v1 補建 coverage／audit 的函式、由 v2 重建 v1 的函式。驗證器**只驗證，不建構**：不產生也不回傳任何 v1／v2 物件；
  僅在 `_stage_base` 借用 `AssembledDigest.__post_init__` 一致性檢查（結果丟棄；測試以 AST 守衛鎖定恰好 1 處、且為獨立 Expr 語句）。
  （測試內的 v2 實例由測試明確組裝；`tests/test_decision_digest_v2_proto.py` 有反射／AST 守衛鎖住本檔的公開名單。）
- assembler／producer／快取／Topic Lens／expected_*／N·M／INV-5（來源 S5：ActionRef 須有標的自己的 OK 行動事實）。
  ⇒ 「System Action 方向」僅**部分**強制；「STALE 不得冒充 fresh」**不**強制；**不得**宣稱 stale 已保留、
  可作投資行動證據（沒有 producer、沒有可驗的 stale 可用日）。

═══ 驗證順序（強制；前一階段有違規即停，只回報該階段）═════════════════════
1. `type`：根／digest／coverage 容器型別與 schema_version。
2. `v1`：v1 `validate_strict`（AB-0 `validate` ＋ rule_id 允許名單 ＋ 行動排序）。有違規即停——
   INV-4 以 `rule_id ∈ ACTION_RULE_IDS` 精確比對，**別名 rule_id（`CUT`、` cut`…）必須先由 strict 擋掉**，否則會繞過 INV-4。
3. `base`：v1 `validate_coverage` ＋ base 與 digest 的一致性（沿用 v1 `AssembledDigest` 的建構檢查）。
4. `audit`：audit 與 base.segments **逐 index** 對齊（base 不合法時不會走到這裡）。
5. `inv`：INV-1／INV-2／INV-4（INV-3＝INV-1 適用全部 ActionRef）。
6. `pit_freshness`：PIT 單向上界＋段級 freshness 的欄位間蘊含。

═══ 窄不變量（G-F3＝A2-i；**不是**「拒絕任何 STALE」）═════════════════════
- INV-1：`evidence_refs` 解析到的事實不得 STALE。
- INV-2：`risk_cap.cap_pct／exposure_lo_pct／exposure_hi_pct` 不得 STALE。
- INV-3：INV-1 適用**全部** ActionRef（不是只看第一個）。
- INV-4：`holdings.entries[*].facts` 中 `rule.rule_id ∈ ACTION_RULE_IDS` 的事實不得 STALE（不論是否被引用）——
  這是對「不拒絕未被引用的 STALE 事實」的**明確窄例外**，射程只限帶行動規則 id 的 entry 事實。
**不拒絕**：market 段 STALE 事實、未被引用且無行動規則的 STALE 事實（控制組）。v1 對 STALE 的降級行為
（MISSING／NO_INPUT）一個字都不動。

⚠️ 欄位間蘊含只有兩條，出處據實如下：
  - fresh／stale ⇒ base 該段 as_of 非 None：出自公開 7110475027「矛盾輸入 Fail Loud」條款（戳 None 但 freshness 為 FRESH／STALE ＝矛盾資料）。
  - used ⇒ FRESH：僅出自 C 線私有草稿 v3_draft.md，**INFERENCE**；與 R4「None＝未判定」有張力（used 段若自報 None 會被拒），待總管確認。
  - 已移除 `withheld_reason == stale ⇒ STALE`（無來源出處）。

PIT（單向上界）只對 `used=True` 的段強制；未採用段的 as_of／fetched_at 只供稽核（例如 `pit_violation` 段本來就可能帶未來日）。

分層：L0 風格；執行期無 I/O、不呼叫 streamlit。⚠️ 但 import 圖經 `src.services.decision_digest_assembly`（`AssembledDigest`）
會帶入該模組的依賴（含 streamlit 等），所以**不是**純 L0 import 閉包。
⚠️ `_all_facts` 是 v1 `shared.decision_digest` 的**私有**依賴（取 evidence_refs 解析的同一份事實集）；v1 frozen，
但若 v1 改名／移除會直接 ImportError——這是刻意的 fail-loud，不是 bug。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from shared.decision_digest import (
    TW_TZ, DataStatus, DecisionDigest, _all_facts,
)
from shared.decision_digest_coverage import (
    SEGMENTS, DigestCoverage, validate_coverage,
)
from shared.decision_digest_rules import ACTION_RULE_IDS, validate_strict
from shared.freshness_policy import FreshnessStatus
from src.services.decision_digest_assembly import AssembledDigest

SCHEMA_VERSION_V2: str = "decision_digest.v2"

#: `evidence_freshness` 的合法值（另加 None＝未判定）。刻意只取 fresh／stale 子集。
EVIDENCE_FRESHNESS_VALUES: frozenset = frozenset({FreshnessStatus.FRESH, FreshnessStatus.STALE})

STAGE_TYPE, STAGE_V1, STAGE_BASE, STAGE_AUDIT, STAGE_INV, STAGE_PIT_FRESHNESS = (
    "type", "v1", "base", "audit", "inv", "pit_freshness")
#: 驗證階段（固定順序；前一階段有違規即停）。
STAGES: tuple = (STAGE_TYPE, STAGE_V1, STAGE_BASE, STAGE_AUDIT, STAGE_INV, STAGE_PIT_FRESHNESS)


# ══════════════════════════════════════════════════════════════════════
# 型別（建構時不檢查；由 validate_v2 收口，與 v1 `DigestCoverage` 同風格）
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SegmentAudit:
    """單一證據段的稽核側欄（v2 唯二新欄所在）。`segment` 與 base.segments 同 index 對齊。"""
    segment: str
    evidence_freshness: FreshnessStatus | None
    fetched_at: datetime | None


@dataclass(frozen=True)
class DigestCoverageV2:
    """`base`（原封 v1 `DigestCoverage`）＋ `audit`（`SegmentAudit` × 4，固定順序，與 base.segments 逐 index 對齊）。"""
    base: DigestCoverage
    audit: tuple


@dataclass(frozen=True)
class DecisionDigestV2:
    """K2 組合根。`digest` 為唯讀、原封不動的 v1 `DecisionDigest`。"""
    digest: DecisionDigest
    coverage: DigestCoverageV2
    schema_version: str = SCHEMA_VERSION_V2


@dataclass(frozen=True)
class V2Violation:
    stage: str
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.stage}] {self.code}: {self.message}"


def _viol(stage: str, code: str, message: str) -> V2Violation:
    return V2Violation(stage, code, message)


# ══════════════════════════════════════════════════════════════════════
# 階段 1：容器型別
# ══════════════════════════════════════════════════════════════════════
def _stage_type(x: Any) -> list:
    if type(x) is not DecisionDigestV2:
        return [_viol(STAGE_TYPE, "root_type", f"必須是 DecisionDigestV2：{type(x).__name__}")]
    out: list = []
    if type(x.schema_version) is not str or x.schema_version != SCHEMA_VERSION_V2:
        out.append(_viol(STAGE_TYPE, "schema_version_mismatch",
                         f"期望 {SCHEMA_VERSION_V2!r}，實得 {x.schema_version!r}"))
    if type(x.digest) is not DecisionDigest:
        out.append(_viol(STAGE_TYPE, "digest_type",
                         f"digest 必須恰好是原封的 v1 DecisionDigest（子類／包裝／dict 一律拒收）：{type(x.digest).__name__}"))
    if type(x.coverage) is not DigestCoverageV2:
        out.append(_viol(STAGE_TYPE, "coverage_type", f"coverage 必須是 DigestCoverageV2：{type(x.coverage).__name__}"))
    return out


# ══════════════════════════════════════════════════════════════════════
# 階段 2：v1 validate_strict（先行；有違規即停）
# ══════════════════════════════════════════════════════════════════════
def _stage_v1(x: DecisionDigestV2) -> list:
    return [_viol(STAGE_V1, f"v1_{v.code}", f"{v.path}: {v.message}") for v in validate_strict(x.digest)]


# ══════════════════════════════════════════════════════════════════════
# 階段 3：coverage base（v1 validate_coverage ＋ 與 digest 的一致性）
# ══════════════════════════════════════════════════════════════════════
def _stage_base(x: DecisionDigestV2) -> list:
    base = x.coverage.base
    vs = validate_coverage(base)
    if vs:
        out = []
        for s in vs:
            code, _, msg = s.partition(": ")
            out.append(_viol(STAGE_BASE, f"base_{code}", msg))
        return out
    try:
        AssembledDigest(x.digest, base)   # 只借 __post_init__ 一致性檢查；結果丟棄（不賦值、不 return、不傳出）
    except ValueError as e:
        return [_viol(STAGE_BASE, "base_digest_inconsistent", str(e))]
    return []


# ══════════════════════════════════════════════════════════════════════
# 階段 4：audit 與 base.segments 逐 index 對齊（base 合法後才進行）
# ══════════════════════════════════════════════════════════════════════
def _is_aware_datetime(v: Any) -> bool:
    return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None


def _stage_audit(x: DecisionDigestV2) -> list:
    audit, segs = x.coverage.audit, x.coverage.base.segments
    if type(audit) is not tuple:
        return [_viol(STAGE_AUDIT, "audit_type", f"audit 必須是 tuple：{type(audit).__name__}")]
    out: list = []
    if len(audit) != len(SEGMENTS):
        out.append(_viol(STAGE_AUDIT, "audit_length", f"audit 必須恰為 {len(SEGMENTS)} 項：{len(audit)}"))
    for i, a in enumerate(audit):
        path = f"audit[{i}]"
        if type(a) is not SegmentAudit:
            out.append(_viol(STAGE_AUDIT, "audit_item_type", f"{path} 必須是 SegmentAudit：{type(a).__name__}"))
            continue
        if i < len(segs) and a.segment != segs[i].segment:
            out.append(_viol(STAGE_AUDIT, "audit_segment_mismatch",
                             f"{path}.segment({a.segment!r}) 必須等於 base.segments[{i}].segment({segs[i].segment!r})"))
        fr = a.evidence_freshness
        if fr is not None and not (type(fr) is FreshnessStatus and fr in EVIDENCE_FRESHNESS_VALUES):
            out.append(_viol(STAGE_AUDIT, "audit_freshness_domain",
                             f"{path}.evidence_freshness 只能是 FreshnessStatus.FRESH／STALE 或 None：{fr!r}"))
        if a.fetched_at is not None and not _is_aware_datetime(a.fetched_at):
            out.append(_viol(STAGE_AUDIT, "audit_fetched_at_type",
                             f"{path}.fetched_at 必須是 tz-aware datetime 或 None：{a.fetched_at!r}"))
    return out


# ══════════════════════════════════════════════════════════════════════
# 階段 5：窄不變量 INV-1／INV-2／INV-4（INV-3＝INV-1 適用全部 ActionRef）
# ══════════════════════════════════════════════════════════════════════
def _inv1_inv3_stale_evidence_refs(d: DecisionDigest) -> list:
    by_id = {f.fact_id: f for _p, f, is_obs in _all_facts(d) if not is_obs}
    out: list = []
    for i, act in enumerate(d.actions.items):                      # INV-3：全部 ActionRef，不是只看第一個
        for ref in act.evidence_refs:
            f = by_id.get(ref)
            if f is not None and f.status is DataStatus.STALE:
                out.append(_viol(STAGE_INV, "inv1_stale_evidence_ref",
                                 f"actions.items[{i}]({act.action_id}) 的 evidence_refs 引用 STALE 事實 {ref!r}"))
    return out


def _inv2_stale_risk_cap(d: DecisionDigest) -> list:
    rc = d.risk_cap
    return [_viol(STAGE_INV, "inv2_stale_risk_cap", f"risk_cap.{name} 不得是 STALE（Risk Cap cap／曝險判定）")
            for name in ("cap_pct", "exposure_lo_pct", "exposure_hi_pct")
            if getattr(rc, name).status is DataStatus.STALE]


def _inv4_stale_action_entry_facts(d: DecisionDigest) -> list:
    out: list = []
    for i, e in enumerate(d.holdings.entries):
        for f in e.facts:
            if f.status is DataStatus.STALE and f.rule is not None and f.rule.rule_id in ACTION_RULE_IDS:
                out.append(_viol(STAGE_INV, "inv4_stale_action_fact",
                                 f"holdings.entries[{i}] 的行動事實 {f.fact_id!r}（rule_id={f.rule.rule_id!r}）不得是 STALE"))
    return out


def _stage_inv(x: DecisionDigestV2) -> list:
    d = x.digest
    return _inv1_inv3_stale_evidence_refs(d) + _inv2_stale_risk_cap(d) + _inv4_stale_action_entry_facts(d)


# ══════════════════════════════════════════════════════════════════════
# 階段 6：PIT（單向上界）＋ 段級 freshness 欄位間蘊含
# ══════════════════════════════════════════════════════════════════════
def _stage_pit_freshness(x: DecisionDigestV2) -> list:
    gen = x.digest.generated_at
    gen_tw_date: date = gen.astimezone(TW_TZ).date()
    out: list = []
    for i, (seg, a) in enumerate(zip(x.coverage.base.segments, x.coverage.audit)):
        path = f"audit[{i}]({seg.segment})"
        if seg.used:   # PIT 只對「採用」的段強制；未採用段的日期只供稽核
            if seg.as_of is not None and seg.as_of > gen_tw_date:
                out.append(_viol(STAGE_PIT_FRESHNESS, "pit_as_of_after_generated",
                                 f"{path}: as_of({seg.as_of}) 晚於 generated_at 的台北日({gen_tw_date})"))
            if a.fetched_at is not None:
                if a.fetched_at > gen:
                    out.append(_viol(STAGE_PIT_FRESHNESS, "pit_fetched_after_generated",
                                     f"{path}: fetched_at({a.fetched_at.isoformat()}) 晚於 generated_at({gen.isoformat()})"))
                if seg.as_of is not None and seg.as_of > a.fetched_at.astimezone(TW_TZ).date():
                    out.append(_viol(STAGE_PIT_FRESHNESS, "pit_as_of_after_fetched",
                                     f"{path}: as_of({seg.as_of}) 晚於 fetched_at 的台北日"))
        fr = a.evidence_freshness
        if seg.used and fr is not FreshnessStatus.FRESH:
            out.append(_viol(STAGE_PIT_FRESHNESS, "freshness_used_requires_fresh",
                             f"{path}: used=True 時 evidence_freshness 必須是 FRESH（STALE／None 不得冒充已採用）：{fr!r}"))
        if fr in EVIDENCE_FRESHNESS_VALUES and seg.as_of is None:
            out.append(_viol(STAGE_PIT_FRESHNESS, "freshness_without_as_of",
                             f"{path}: evidence_freshness={fr!r} 時 base 該段 as_of 必須非 None（無戳＋FRESH／STALE 是矛盾資料）"))
    return out


_PIPELINE: tuple = (_stage_type, _stage_v1, _stage_base, _stage_audit, _stage_inv, _stage_pit_freshness)


# ══════════════════════════════════════════════════════════════════════
# 入口（只驗證，不建構；任何輸入都不 raise）
# ══════════════════════════════════════════════════════════════════════
def validate_v2(x: Any) -> tuple:
    """回傳 `V2Violation` tuple（空＝合規）。**前一階段有違規即停**，只回報該階段（階段順序見模組 docstring）。"""
    try:
        for stage_fn in _PIPELINE:
            vs = stage_fn(x)
            if vs:
                return tuple(vs)
        return ()
    except Exception as e:  # noqa: BLE001 —— 驗證器本身不得因髒輸入而 raise（回報成違規）
        return (_viol("validator_error", "validator_error", f"{type(e).__name__}: {e}"),)


def assert_v2_valid(x: Any) -> None:
    """Fail Loud：有任何違規即 `ValueError`（附全部違規）。"""
    vs = validate_v2(x)
    if vs:
        raise ValueError("DecisionDigestV2 違反契約：\n  " + "\n  ".join(str(v) for v in vs))


__all__ = [
    "SCHEMA_VERSION_V2", "EVIDENCE_FRESHNESS_VALUES", "STAGES", "SegmentAudit", "DigestCoverageV2",
    "DecisionDigestV2", "V2Violation", "validate_v2", "assert_v2_valid",
]
