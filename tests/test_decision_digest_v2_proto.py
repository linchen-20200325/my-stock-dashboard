"""G-F4 / K2 組合式 `decision_digest.v2` tests-only 原型的測試（Issue #1199；fast lane；純離線）。

被測物：`tests/decision_digest_v2_proto.py`（型別＋驗證器；**不是 production 模組**，0 production caller）。
授權：客戶 G-F3＝A2-i（7109632982）；總管 G-F4 tests-only 範圍授權（7122310368／7122175708 §B §C）；設計來源 S1 v3.1（7110475027 §1）。

═══ 測什麼 ═══════════════════════════════════════════════════════════
0. 結構／授權邊界：frozen、`.digest` 唯讀且原封（同一物件、`type(x) is DecisionDigest`）、新欄只有 `evidence_freshness`／`fetched_at`、
   沒有任何「可用日」欄位、沒有 v1↔v2 互轉函式、v1 側欄位（`DigestCoverage`）一個欄位都沒多、0 production caller。
1. 驗證順序：型別 → v1 `validate_strict`（先行）→ coverage base → audit 對齊 → INV-1／INV-2／INV-4 → PIT／freshness；
   前一階段有違規即停（逐階段鎖定）。
2. 四條窄不變量（A2-i）：每條都有**正例**、**反例**（錯誤碼可斷言）、**控制組**（證明沒有過度拒絕：
   market 段 STALE、未被引用且無行動規則的 STALE entry 事實必須通過）。
3. PIT 單向上界／freshness 欄位間蘊含／audit 對齊／`evidence_freshness` 值域。
4. 與真 v1 組裝器的相容（`assemble_digest` 的 STALE 證據仍降級為 MISSING／NO_INPUT；原因只在 coverage／audit）。

⛔ 沒有 INV-5（來源 S5）、沒有 assembler／producer：不得由本檔宣稱 stale 已保留、可作投資行動證據，
也不得宣稱「STALE 不得冒充 fresh」已被強制（`evidence_freshness` 是自報、不可覆算）。
G1 類（v1 契約違規）只能用 `tests/decision_digest_factory.force_set` 製造（v1 型別建構即驗證）。
"""
from __future__ import annotations

import ast
import dataclasses
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from shared.decision_digest import (
    MAX_ACTIONS, Availability, DataStatus, DecisionDigest, Fact, MissingReason, RiskCapSection, RuleRef,
    derive_availability, validate,
)
from shared.decision_digest_coverage import (
    SEGMENT_ACTIONS, SEGMENT_HOLDINGS, SEGMENT_MARKET, SEGMENT_RISK_CAP, SEGMENTS, WITHHELD_NOT_LOADED,
    WITHHELD_PIT_VIOLATION, WITHHELD_STALE, DigestCoverage, SegmentEvidence,
)
from shared.decision_digest_rules import ACTION_RULE_IDS, ACTION_RULE_VERSION, assert_strict, validate_strict
from shared.freshness_policy import FreshnessStatus as F
from src.services.decision_digest_assembly import AssembledDigest
from src.services.decision_digest_summary import build_rule_summary
from tests import decision_digest_v2_proto as P
from tests.decision_digest_factory import (
    D, NOW, RISK_RULE, action, entry, force_set, make_digest, missing, ok_text, ok_val, prov, stale_text, stale_val,
)
from tests.decision_digest_v2_proto import (
    SCHEMA_VERSION_V2, STAGES, DecisionDigestV2, DigestCoverageV2, SegmentAudit, V2Violation,
    assert_v2_valid, validate_v2,
)

REPO = Path(__file__).resolve().parents[1]
PROTO_FILE = REPO / "tests" / "decision_digest_v2_proto.py"
FT = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)      # 擷取時間：D 當天、早於 NOW
T_CUT = "🔴 汰弱：吃本金"
T_TPF = "💰 強制停利（>+3σ）：獲利轉回核心資產"
T_TPP = "💰 分批停利：獲利轉回核心資產"


# ══════════════════════════════════════════════════════════════════════
# 夾具（全部由測試明確組裝；沒有任何「由 digest 推導 coverage／audit」的函式）
# ══════════════════════════════════════════════════════════════════════
def seg(name, used=True, reason=None, source="svc", as_of=D):
    return SegmentEvidence(name, used, source, as_of, None if used else reason)


def base_cov(*, total=2, shown=2, segs=None, hold=True, act=True, **over):
    kw = dict(actions_total_eligible=total, actions_shown=shown,
              actions_omitted_count=None if total is None else total - shown, actions_max=MAX_ACTIONS,
              excluded_invalid_rows=0, unkeyed_held_count=0, station_rows_unmatched=0,
              holdings_without_station_row=0, station_non_mapping_rows=0, holdings_non_mapping_rows=0,
              unrecognized_action_code_rows=0, duplicate_station_ticker_rows=0,
              digest_holdings_available=hold, digest_actions_available=act,
              segments=segs if segs is not None else tuple(seg(n) for n in SEGMENTS))
    kw.update(over)
    return DigestCoverage(**kw)


def segs_with(**by_name):
    """預設四段皆 used；以 `market=seg(...)` 之類覆蓋個別段。"""
    return tuple(by_name.get(n) or seg(n) for n in SEGMENTS)


def audit(m=F.FRESH, r=F.FRESH, h=F.FRESH, a=F.FRESH, *, fetched=FT):
    return tuple(SegmentAudit(n, fr, fetched) for n, fr in zip(SEGMENTS, (m, r, h, a)))


def v2_of(digest, base, aud):
    return DecisionDigestV2(digest, DigestCoverageV2(base, aud))


def codes(x):
    return {v.code for v in validate_v2(x)}


def stages(x):
    return {v.stage for v in validate_v2(x)}


STALE_MARKET = (stale_text("market.regime", "bull"), ok_text("market.light", "🟢"), ok_val("market.health", 72.5))
MARKET_STALE_SEGS = segs_with(market=seg(SEGMENT_MARKET, False, WITHHELD_STALE))
MARKET_STALE_AUDIT = audit(m=F.STALE)


def v2_ok():
    return v2_of(make_digest(), base_cov(), audit())


def v2_market_stale_uncited():
    """控制組 C：market 段有 STALE 事實，且沒有任何 ActionRef 引用它。"""
    return v2_of(make_digest(market_facts=STALE_MARKET), base_cov(segs=MARKET_STALE_SEGS), MARKET_STALE_AUDIT)


def v2_market_stale_cited(position=0, n_actions=2):
    """INV-1／INV-3：第 `position` 個 ActionRef 引用 STALE 的 market.regime（其餘引用自己標的的 OK 行動事實）。"""
    spec = [("0050", T_CUT, "cut"), ("0056", T_TPF, "take_profit_force"), ("0058", T_TPP, "take_profit_partial")][:n_actions]
    entries = [entry(s, t, c) for s, t, c in spec]
    items = [action(s, t, c, i + 1, evidence=("market.regime",) if i == position else None)
             for i, (s, t, c) in enumerate(spec)]
    d = make_digest(market_facts=STALE_MARKET, entries=entries, items=items)
    return v2_of(d, base_cov(total=n_actions, shown=n_actions, segs=MARKET_STALE_SEGS), MARKET_STALE_AUDIT)


def _stale_entry_fact(code="cut", symbol="0050", rule=True, fact_id=None):
    fid = fact_id or (f"action_fact:pf-A:{symbol}" if rule else f"note:{symbol}")
    return Fact(fid, DataStatus.STALE, prov(), text=T_CUT, rule=RuleRef(code, ACTION_RULE_VERSION) if rule else None)


def v2_stale_entry_fact(code="cut", rule=True, cited=False):
    """entry 內有一個 STALE 事實（rule 為行動規則或 None）；預設未被任何 ActionRef 引用。"""
    sa = _stale_entry_fact(code, rule=rule)
    item = (action("0050", T_CUT, code, 1) if cited
            else action("0056", T_TPF, "take_profit_force", 1, evidence=("market.regime",)))
    d = make_digest(entries=[entry("0050", facts=(sa,)), entry("0056", T_TPF, "take_profit_force")], items=[item])
    return v2_of(d, base_cov(total=1, shown=1, hold=False), audit())


def stale_cap_section(which):
    vals = {"cap_pct": 60, "exposure_lo_pct": 40, "exposure_hi_pct": 60}
    facts = {n: ok_val(f"risk_cap.{n}", v, "%", rule=RISK_RULE) for n, v in vals.items()}
    facts[which] = stale_val(f"risk_cap.{which}", vals[which], "%")
    facts[which] = dataclasses.replace(facts[which], rule=RISK_RULE)
    trio = (facts["cap_pct"], facts["exposure_lo_pct"], facts["exposure_hi_pct"])
    return RiskCapSection(True, *trio, derive_availability(trio))


RISK_STALE_SEGS = segs_with(risk_cap=seg(SEGMENT_RISK_CAP, False, WITHHELD_STALE))


def v2_risk_cap_stale(which="cap_pct"):
    d = make_digest(risk_cap=stale_cap_section(which))
    return v2_of(d, base_cov(segs=RISK_STALE_SEGS), audit(r=F.STALE))


def v2_zero_action(holdings_as_of=D, actions_as_of=D, aud=None):
    """零行動（v1 證據 fresh 時 holdings／actions 段 used=True 但無 OK 事實錨點，as_of 不受事實約束）。"""
    d = make_digest(entries=[], items=[])
    segs = segs_with(holdings=seg(SEGMENT_HOLDINGS, as_of=holdings_as_of), actions=seg(SEGMENT_ACTIONS, as_of=actions_as_of))
    return v2_of(d, base_cov(total=0, shown=0, segs=segs, hold=False, act=False), aud or audit())


# ══════════════════════════════════════════════════════════════════════
# 0. 結構與授權邊界
# ══════════════════════════════════════════════════════════════════════
def test_fixture_baseline_is_valid_and_v1_pieces_are_valid():
    x = v2_ok()
    assert validate_v2(x) == ()
    assert_v2_valid(x)                                   # 不 raise
    assert validate_strict(x.digest) == ()
    assert x.schema_version == "decision_digest.v2" == SCHEMA_VERSION_V2


def test_dataclasses_are_frozen_and_digest_is_read_only():
    x = v2_ok()
    for obj, name in ((x, "digest"), (x, "coverage"), (x, "schema_version"), (x.coverage, "base"),
                      (x.coverage, "audit"), (x.coverage.audit[0], "evidence_freshness"),
                      (x.coverage.audit[0], "fetched_at")):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, name, None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        del x.digest


def test_digest_is_the_original_v1_object_not_a_copy_or_wrapper():
    d = make_digest()
    base = base_cov()
    x = v2_of(d, base, audit())
    assert x.digest is d and type(x.digest) is DecisionDigest      # 同一物件、原封型別
    assert x.coverage.base is base and type(x.coverage.base) is DigestCoverage


def test_v1_tools_read_the_digest_field_directly_and_validation_does_not_mutate_it():
    d = make_digest()
    before = d.to_dict()
    x = v2_of(d, base_cov(), audit())
    assert_strict(x.digest)                                          # v1 驗證器直接吃 .digest
    assert build_rule_summary(x.digest).lines == build_rule_summary(d).lines
    validate_v2(x)
    assert x.digest.to_dict() == before and x.digest is d


def test_field_sets_are_locked_and_new_fields_are_only_evidence_freshness_and_fetched_at():
    names = lambda c: tuple(f.name for f in dataclasses.fields(c))   # noqa: E731
    assert names(DecisionDigestV2) == ("digest", "coverage", "schema_version")
    assert names(DigestCoverageV2) == ("base", "audit")
    assert names(SegmentAudit) == ("segment", "evidence_freshness", "fetched_at")
    # v1 側一個欄位都沒多：新欄只活在 v2 的 audit，不在 v1 的 coverage／digest 上
    v1_names = {f.name for c in (DigestCoverage, SegmentEvidence, DecisionDigest) for f in dataclasses.fields(c)}
    assert not v1_names & {"evidence_freshness", "fetched_at"}
    assert "decision_digest.v1" != SCHEMA_VERSION_V2


def test_no_availability_date_field_and_fetched_at_is_not_a_publication_date():
    forbidden = {"available_at", "published_at", "release_date", "observed_at", "confidence", "expected_count"}
    for c in (DecisionDigestV2, DigestCoverageV2, SegmentAudit):
        assert not {f.name for f in dataclasses.fields(c)} & forbidden
    # fetched_at 只是擷取時間：驗證器不會拿它填補 base 的 as_of（沒有 as_of 的 FRESH 段仍被拒）
    x = v2_of(make_digest(market_facts=[missing("market.regime"), missing("market.light"), missing("market.health")]),
              base_cov(segs=segs_with(market=seg(SEGMENT_MARKET, False, "no_stamp", source=None, as_of=None))),
              audit(m=F.FRESH))
    assert "freshness_without_as_of" in codes(x)


def test_evidence_freshness_value_domain_is_fresh_stale_subset_of_freshness_status():
    assert P.EVIDENCE_FRESHNESS_VALUES == frozenset({F.FRESH, F.STALE})
    assert {F.MISSING, F.UNDETERMINED}.isdisjoint(P.EVIDENCE_FRESHNESS_VALUES)


def _module_ast():
    return ast.parse(PROTO_FILE.read_text(encoding="utf-8"))


def test_module_has_no_conversion_or_rebuild_functions_only_validate_and_assert():
    tree = _module_ast()
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    public = sorted(n for n in funcs if not n.startswith("_") and n != "__str__")
    assert public == ["assert_v2_valid", "validate_v2"]
    banned = re.compile(r"to_v1|from_v1|to_v2|from_v2|upgrade|downgrade|rebuild|assemble|produce|build_cov|backfill|migrate", re.I)
    assert [n for n in funcs if banned.search(n)] == []


def test_validator_never_constructs_v1_or_v2_objects():
    """驗證器只驗證，不建構：不呼叫 v1／v2 型別建構子。唯一例外：`_stage_base` 內借用 `AssembledDigest.__post_init__`
    一致性檢查——全模組恰好 1 個呼叫、位於 `_stage_base`、且為獨立 Expr 語句（不得賦值／return／傳出）。"""
    tree = _module_ast()
    parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
    ad_calls = [n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and ((isinstance(n.func, ast.Name) and n.func.id == "AssembledDigest")
                                                or (isinstance(n.func, ast.Attribute) and n.func.attr == "AssembledDigest"))]
    assert len(ad_calls) == 1
    call = ad_calls[0]
    assert isinstance(parents[call], ast.Expr)                      # 結果丟棄：不賦值、不 return、不傳出
    fn = call
    while not isinstance(fn, ast.FunctionDef):
        fn = parents[fn]
    assert fn.name == "_stage_base"
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    called |= {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    banned = {"DecisionDigest", "DigestCoverage", "SegmentEvidence", "DecisionDigestV2", "DigestCoverageV2",
              "SegmentAudit", "replace", "deepcopy", "copy"}
    assert called & banned == set()


def test_zero_production_caller_for_the_prototype():
    """只准 tests/ 引用本原型（`ALLOWED_CALLERS` 與 v1 家族守衛都不動）。"""
    roots = [REPO / d for d in ("shared", "src", "scripts", "infra", "mcp_server", "tools")]   # 不存在的目錄略過
    files = [p for r in roots if r.exists() for p in r.rglob("*.py") if "__pycache__" not in p.parts]
    files += [p for p in REPO.glob("*.py")]
    hits = [str(p.relative_to(REPO)) for p in files if "decision_digest_v2_proto" in p.read_text(encoding="utf-8", errors="ignore")]
    assert hits == []


# ══════════════════════════════════════════════════════════════════════
# 1. 驗證順序（前一階段有違規即停）
# ══════════════════════════════════════════════════════════════════════
def test_stage_names_and_order_are_fixed():
    assert STAGES == ("type", "v1", "base", "audit", "inv", "pit_freshness")


def _invalid_v1_digest():
    return force_set(make_digest(), schema_version="decision_digest.v0")      # G1：只能 force_set 製造


def test_v1_validate_strict_runs_first_and_stops_everything_else():
    # v1 違規 ＋ base 壞 ＋ audit 壞 ＋ INV 違規 ＋ PIT 壞：只回報 v1 階段
    d = _invalid_v1_digest()
    x = v2_of(d, base_cov(actions_max=99), tuple(reversed(audit(fetched=NOW + timedelta(days=9)))))
    vs = validate_v2(x)
    assert {v.stage for v in vs} == {"v1"} and "v1_schema_version_mismatch" in {v.code for v in vs}


def _alias_stale_entry_digest(rid):
    sa = Fact("action_fact:pf-A:0050", DataStatus.STALE, prov(), text=T_CUT, rule=RuleRef(rid, ACTION_RULE_VERSION))
    return make_digest(entries=[entry("0050", facts=(sa,)), entry("0056", T_TPF, "take_profit_force")],
                       items=[action("0056", T_TPF, "take_profit_force", 1, evidence=("market.regime",))])


@pytest.mark.parametrize("rid", ["CUT", " cut", "Cut", "cut ", "premium", "cruise", "take_profit", "CUT​"])
def test_alias_rule_id_is_stopped_by_strict_before_inv4_could_miss_it(rid):
    """INV-4 以精確的 rule_id ∈ ACTION_RULE_IDS 比對；別名若沒被 v1 strict 先擋，STALE 行動事實會繞過 INV-4。"""
    d = _alias_stale_entry_digest(rid)
    assert validate(d) == ()                                  # 只換成 plain `validate` 的話，v1 這一關是放行的
    assert P._inv4_stale_action_entry_facts(d) == []          # 而 INV-4 本身對別名視而不見
    x = v2_of(d, base_cov(total=1, shown=1, hold=False), audit())
    vs = validate_v2(x)
    assert {v.stage for v in vs} == {"v1"} and "v1_rule_not_allowlisted" in {v.code for v in vs}


def test_base_violation_stops_before_audit_alignment():
    d = make_digest()
    x = v2_of(d, base_cov(actions_max=99), tuple(reversed(audit())))       # base 壞，audit 也壞
    vs = validate_v2(x)
    assert {v.stage for v in vs} == {"base"} and "base_actions_max_mismatch" in {v.code for v in vs}
    assert not any(v.code.startswith("audit_") for v in vs)


def test_base_digest_inconsistency_is_reported_in_base_stage():
    x = v2_of(make_digest(), base_cov(total=2, shown=1), audit())             # shown 與 digest 實際 2 筆不一致
    vs = validate_v2(x)
    assert {v.stage for v in vs} == {"base"} and "base_digest_inconsistent" in {v.code for v in vs}


def test_each_stage_reports_only_itself_when_all_later_stages_are_also_broken():
    late_pit = audit(fetched=NOW + timedelta(days=9))                         # PIT 壞（used 段 fetched 晚於 generated）
    # type：schema_version 壞（其餘全壞）
    x_type = dataclasses.replace(v2_of(_invalid_v1_digest(), base_cov(actions_max=99), tuple(reversed(late_pit))),
                                 schema_version="decision_digest.v1")
    # base：digest 合法但帶 INV 違規；base 壞；audit 壞
    base_x = v2_market_stale_cited()
    x_base = v2_of(base_x.digest, base_cov(actions_max=99), tuple(reversed(late_pit)))
    # audit：base 合法；audit 順序反（且 INV、PIT 也壞）
    x_audit = v2_of(base_x.digest, base_x.coverage.base, tuple(reversed(late_pit)))
    # inv：audit 合法；INV 違規；PIT 壞
    x_inv = v2_of(base_x.digest, base_x.coverage.base,
                  audit(m=F.STALE, fetched=NOW + timedelta(days=9)))
    # pit_freshness：只有 PIT 壞
    x_pit = v2_of(make_digest(), base_cov(), audit(fetched=NOW + timedelta(days=9)))
    assert [stages(x) for x in (x_type, x_base, x_audit, x_inv, x_pit)] == [
        {"type"}, {"base"}, {"audit"}, {"inv"}, {"pit_freshness"}]


def test_inv_stage_precedes_pit_and_freshness_checks():
    x = v2_market_stale_cited()
    bad = v2_of(x.digest, x.coverage.base, audit(m=F.STALE, h=F.STALE, fetched=NOW + timedelta(days=9)))
    assert stages(bad) == {"inv"} and "inv1_stale_evidence_ref" in codes(bad)


# ══════════════════════════════════════════════════════════════════════
# 型別階段／入口行為
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("junk", [None, 42, "x", {}, object(), make_digest(), (1, 2)])
def test_non_v2_root_is_rejected_without_raising(junk):
    vs = validate_v2(junk)
    assert [v.code for v in vs] == ["root_type"] and vs[0].stage == "type"
    with pytest.raises(ValueError):
        assert_v2_valid(junk)


def test_digest_and_coverage_container_types_are_exact():
    x = v2_ok()

    class _Wrapper:                                           # 鴨子型別包裝不是原封的 v1 DecisionDigest
        def __getattr__(self, n):
            return getattr(x.digest, n)
    assert "digest_type" in codes(dataclasses.replace(x, digest=_Wrapper()))
    assert "digest_type" in codes(dataclasses.replace(x, digest=x.digest.to_dict()))
    assert "coverage_type" in codes(dataclasses.replace(x, coverage=x.coverage.base))
    assert "schema_version_mismatch" in codes(dataclasses.replace(x, schema_version="decision_digest.v1"))
    assert "base_type" in codes(dataclasses.replace(x, coverage=DigestCoverageV2(None, x.coverage.audit)))


def test_validator_never_raises_on_garbage_internals():
    x = v2_ok()
    for bad in (dataclasses.replace(x, coverage=DigestCoverageV2(x.coverage.base, None)),
                dataclasses.replace(x, coverage=DigestCoverageV2(x.coverage.base, (None,) * 4)),
                dataclasses.replace(x, coverage=DigestCoverageV2(x.coverage.base, [])),
                dataclasses.replace(x, digest=None)):
        assert isinstance(validate_v2(bad), tuple) and validate_v2(bad)
    assert all(isinstance(v, V2Violation) for v in validate_v2(None))


def test_assert_v2_valid_raises_with_codes_in_message():
    with pytest.raises(ValueError, match="inv1_stale_evidence_ref"):
        assert_v2_valid(v2_market_stale_cited())


# ══════════════════════════════════════════════════════════════════════
# audit 對齊與 evidence_freshness／fetched_at 形狀
# ══════════════════════════════════════════════════════════════════════
def test_audit_aligned_with_base_segments_is_valid_in_all_none_form():
    x = v2_of(make_digest(), base_cov(), tuple(SegmentAudit(n, F.FRESH, None) for n in SEGMENTS))
    assert validate_v2(x) == ()                                              # fetched_at 可為 None


@pytest.mark.parametrize("aud, code", [
    (None, "audit_type"),
    (list(audit()), "audit_type"),
    (audit()[:3], "audit_length"),
    (audit() + (SegmentAudit("market", F.FRESH, FT),), "audit_length"),
    (tuple(reversed(audit())), "audit_segment_mismatch"),
    ((SegmentAudit("market", F.FRESH, FT),) * 4, "audit_segment_mismatch"),
    ((None,) + audit()[1:], "audit_item_type"),
    ((("market", F.FRESH, FT),) + audit()[1:], "audit_item_type"),
])
def test_audit_alignment_violations(aud, code):
    x = v2_of(make_digest(), base_cov(), aud)
    assert code in codes(x) and stages(x) == {"audit"}


def test_audit_misalignment_reports_the_index():
    swapped = (audit()[1], audit()[0]) + audit()[2:]
    msgs = [v.message for v in validate_v2(v2_of(make_digest(), base_cov(), swapped))]
    assert any("audit[0]" in m for m in msgs) and any("audit[1]" in m for m in msgs)


@pytest.mark.parametrize("val", ["fresh", "stale", F.MISSING, F.UNDETERMINED, "missing", True, 1, "FreshnessStatus.FRESH"])
def test_evidence_freshness_value_domain_rejects_everything_but_fresh_stale_none(val):
    aud = (SegmentAudit(SEGMENT_MARKET, val, FT),) + audit()[1:]
    x = v2_of(make_digest(), base_cov(), aud)
    assert "audit_freshness_domain" in codes(x) and stages(x) == {"audit"}


@pytest.mark.parametrize("val", [F.FRESH, F.STALE, None])
def test_evidence_freshness_accepts_fresh_stale_and_none_as_unjudged(val):
    # 未採用段：None＝未判定，合法；FRESH／STALE 需 base 該段 as_of 非 None（此處 as_of=D）
    segs = segs_with(market=seg(SEGMENT_MARKET, False, WITHHELD_NOT_LOADED))
    d = make_digest(market_facts=[missing("market.regime"), missing("market.light"), missing("market.health")])
    aud = (SegmentAudit(SEGMENT_MARKET, val, FT),) + audit()[1:]
    assert validate_v2(v2_of(d, base_cov(segs=segs), aud)) == ()


@pytest.mark.parametrize("fa", ["2026-10-26T10:00:00+00:00", date(2026, 10, 26), datetime(2026, 10, 26, 10, 0), 0, True])
def test_fetched_at_must_be_tz_aware_datetime_or_none(fa):
    aud = (SegmentAudit(SEGMENT_MARKET, F.FRESH, fa),) + audit()[1:]
    x = v2_of(make_digest(), base_cov(), aud)
    assert "audit_fetched_at_type" in codes(x) and stages(x) == {"audit"}


# ══════════════════════════════════════════════════════════════════════
# INV-1（evidence_refs 解析之事實不得 STALE）
# ══════════════════════════════════════════════════════════════════════
def test_inv1_positive_actions_citing_only_ok_facts_pass():
    assert validate_v2(v2_ok()) == ()


def test_inv1_negative_action_citing_stale_market_fact_is_rejected():
    x = v2_market_stale_cited()
    assert validate_strict(x.digest) == ()                    # v1 允許（_EVIDENCE_STATUSES={OK,STALE}）：擋的是 v2
    vs = validate_v2(x)
    assert [v.code for v in vs] == ["inv1_stale_evidence_ref"] and vs[0].stage == "inv"
    assert "market.regime" in vs[0].message


def test_inv1_negative_action_citing_stale_action_fact_is_rejected():
    x = v2_stale_entry_fact("cut", cited=True)
    assert validate_strict(x.digest) == ()
    assert {"inv1_stale_evidence_ref", "inv4_stale_action_fact"} <= codes(x)


def test_inv1_control_stale_market_fact_not_cited_by_any_action_passes():
    x = v2_market_stale_uncited()
    assert validate_strict(x.digest) == ()
    assert any(f.status is DataStatus.STALE for f in x.digest.market.facts)       # 前提：真的有 STALE 事實
    assert validate_v2(x) == ()


# ══════════════════════════════════════════════════════════════════════
# INV-3（INV-1 適用全部 ActionRef，不是只看第一個）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("position", [0, 1, 2])
def test_inv3_stale_ref_is_caught_in_every_action_position(position):
    x = v2_market_stale_cited(position=position, n_actions=3)
    assert validate_strict(x.digest) == () and len(x.digest.actions.items) == 3
    vs = validate_v2(x)
    assert [v.code for v in vs] == ["inv1_stale_evidence_ref"]
    assert f"actions.items[{position}]" in vs[0].message


def test_inv3_every_action_citing_stale_yields_one_violation_each():
    spec = [("0050", T_CUT, "cut"), ("0056", T_TPF, "take_profit_force"), ("0058", T_TPP, "take_profit_partial")]
    d = make_digest(market_facts=STALE_MARKET, entries=[entry(s, t, c) for s, t, c in spec],
                    items=[action(s, t, c, i + 1, evidence=("market.regime",)) for i, (s, t, c) in enumerate(spec)])
    x = v2_of(d, base_cov(total=3, shown=3, segs=MARKET_STALE_SEGS), MARKET_STALE_AUDIT)
    assert [v.code for v in validate_v2(x)] == ["inv1_stale_evidence_ref"] * 3


# ══════════════════════════════════════════════════════════════════════
# INV-2（risk_cap 的 cap／曝險不得 STALE）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("which", ["cap_pct", "exposure_lo_pct", "exposure_hi_pct"])
def test_inv2_negative_stale_risk_cap_value_is_rejected(which):
    x = v2_risk_cap_stale(which)
    assert validate_strict(x.digest) == ()                    # v1 的 _check_risk_cap_section 允許 cap stale
    assert getattr(x.digest.risk_cap, which).status is DataStatus.STALE
    vs = validate_v2(x)
    assert [v.code for v in vs] == ["inv2_stale_risk_cap"] and which in vs[0].message


def test_inv2_positive_ok_risk_cap_passes():
    x = v2_ok()
    rc = x.digest.risk_cap
    assert all(f.status is DataStatus.OK for f in (rc.cap_pct, rc.exposure_lo_pct, rc.exposure_hi_pct))
    assert validate_v2(x) == ()


def test_inv2_control_missing_risk_cap_stays_missing_and_is_not_rejected():
    """v1 的 MISSING／NO_INPUT 行為不動：缺值（≠ STALE）不被 INV-2 擋，也不被補成任何值。"""
    d = make_digest(risk_valid=False)
    assert d.risk_cap.cap_pct.status is DataStatus.MISSING
    segs = segs_with(risk_cap=seg(SEGMENT_RISK_CAP, False, WITHHELD_NOT_LOADED, source=None, as_of=None))
    x = v2_of(d, base_cov(segs=segs), audit(r=None))
    assert validate_v2(x) == ()


def test_inv2_control_stale_market_with_ok_risk_cap_passes():
    assert validate_v2(v2_market_stale_uncited()) == ()


# ══════════════════════════════════════════════════════════════════════
# INV-4（entry 內帶行動規則 id 的事實不得 STALE，不論是否被引用）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("code", ACTION_RULE_IDS)
def test_inv4_negative_uncited_stale_action_fact_is_rejected_for_every_action_rule_id(code):
    x = v2_stale_entry_fact(code, cited=False)
    assert validate_strict(x.digest) == ()                    # v1 valid；v1 摘要甚至不會標示過期
    cited = {r for a in x.digest.actions.items for r in a.evidence_refs}
    assert "action_fact:pf-A:0050" not in cited                # 前提：確實沒有任何 ActionRef 引用它
    vs = validate_v2(x)
    assert [v.code for v in vs] == ["inv4_stale_action_fact"] and code in vs[0].message


def test_inv4_action_rule_ids_come_from_the_ssot_and_are_the_five_known_codes():
    assert set(ACTION_RULE_IDS) == {"cut", "take_profit_force", "take_profit_partial", "pause_add", "add"}


def test_inv4_positive_ok_action_facts_pass():
    for code in ACTION_RULE_IDS:
        sa = dataclasses.replace(_stale_entry_fact(code), status=DataStatus.OK)
        d = make_digest(entries=[entry("0050", facts=(sa,)), entry("0056", T_TPF, "take_profit_force")],
                        items=[action("0056", T_TPF, "take_profit_force", 1)])
        assert validate_v2(v2_of(d, base_cov(total=1, shown=1), audit())) == ()


def test_inv4_control_stale_entry_fact_without_action_rule_not_rejected():
    """控制組 L2：entry 內無行動規則（rule=None）的 STALE 事實、未被引用 → 必須通過（A2-i 不得概括拒絕 STALE entry 事實）。"""
    x = v2_stale_entry_fact(rule=False)
    assert validate_strict(x.digest) == ()
    assert any(f.status is DataStatus.STALE for e in x.digest.holdings.entries for f in e.facts)
    assert validate_v2(x) == ()


def test_inv4_control_stale_market_fact_is_not_hit_by_inv4():
    x = v2_market_stale_uncited()
    assert P._inv4_stale_action_entry_facts(x.digest) == []
    assert validate_v2(x) == ()


# ══════════════════════════════════════════════════════════════════════
# 控制組總表：A2-i 不得概括拒絕 STALE（G-F3＝A2-i；v1 的 STALE 行為不動）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("make", [v2_market_stale_uncited, lambda: v2_stale_entry_fact(rule=False)],
                         ids=["market_stale_uncited", "entry_stale_no_action_rule_uncited"])
def test_control_stale_facts_outside_the_narrow_invariants_are_accepted(make):
    x = make()
    assert any(f.status is DataStatus.STALE for f in _every_fact(x.digest))
    assert validate_v2(x) == ()


def test_control_both_stale_kinds_together_still_pass():
    nf = _stale_entry_fact(rule=False)
    d = make_digest(market_facts=STALE_MARKET,
                    entries=[entry("0050", facts=(nf,)), entry("0056", T_TPF, "take_profit_force")],
                    items=[action("0056", T_TPF, "take_profit_force", 1)])
    x = v2_of(d, base_cov(total=1, shown=1, segs=MARKET_STALE_SEGS, hold=False), MARKET_STALE_AUDIT)
    assert validate_strict(d) == () and validate_v2(x) == ()


def _every_fact(d):
    rc = d.risk_cap
    return (list(d.market.facts) + [rc.cap_pct, rc.exposure_lo_pct, rc.exposure_hi_pct]
            + [f for e in d.holdings.entries for f in e.facts])


# ══════════════════════════════════════════════════════════════════════
# 位置覆蓋（N4／N5／N6）：INV 不得只看「第一個」
# ══════════════════════════════════════════════════════════════════════
def test_n4_stale_fact_in_second_evidence_ref_of_an_action_is_caught():
    spec = [("0050", T_CUT, "cut"), ("0056", T_TPF, "take_profit_force")]
    first = action("0050", T_CUT, "cut", 1, evidence=("action_fact:pf-A:0050", "market.regime"))   # STALE 在第 2 個 ref
    d = make_digest(market_facts=STALE_MARKET, entries=[entry(s, t, c) for s, t, c in spec],
                    items=[first, action("0056", T_TPF, "take_profit_force", 2)])
    assert validate_strict(d) == () and len(first.evidence_refs) == 2
    x = v2_of(d, base_cov(segs=MARKET_STALE_SEGS), MARKET_STALE_AUDIT)
    vs = validate_v2(x)
    assert [v.code for v in vs] == ["inv1_stale_evidence_ref"] and "market.regime" in vs[0].message


@pytest.mark.parametrize("position", [1, 2])
def test_n5_stale_action_fact_in_a_non_first_entry_is_caught(position):
    sa = _stale_entry_fact("cut", symbol="0050")
    ents = [entry("0056", T_TPF, "take_profit_force"), entry("0058", T_TPP, "take_profit_partial")]
    ents.insert(position, entry("0050", facts=(sa,)))
    d = make_digest(entries=ents, items=[action("0056", T_TPF, "take_profit_force", 1)])
    assert validate_strict(d) == () and ents[0].facts[0].status is DataStatus.OK
    x = v2_of(d, base_cov(total=1, shown=1, hold=False), audit())
    vs = validate_v2(x)
    assert [v.code for v in vs] == ["inv4_stale_action_fact"] and f"entries[{position}]" in vs[0].message


def test_n6_stale_action_fact_as_second_fact_of_an_entry_is_caught():
    note_ok = ok_text("note:0050", "備註")                                  # rule=None、OK
    sa = _stale_entry_fact("cut", symbol="0050")
    d = make_digest(entries=[entry("0050", facts=(note_ok, sa)), entry("0056", T_TPF, "take_profit_force")],
                    items=[action("0056", T_TPF, "take_profit_force", 1)])
    assert validate_strict(d) == ()
    x = v2_of(d, base_cov(total=1, shown=1, hold=False), audit())
    assert [v.code for v in validate_v2(x)] == ["inv4_stale_action_fact"]


# ══════════════════════════════════════════════════════════════════════
# PIT（單向上界；只對 used 段）
# ══════════════════════════════════════════════════════════════════════
def test_pit_zero_action_baseline_is_valid():
    assert validate_v2(v2_zero_action()) == ()


def test_pit_used_segment_as_of_after_generated_is_rejected():
    x = v2_zero_action(holdings_as_of=date(2099, 1, 1), actions_as_of=date(2099, 1, 1), aud=audit(fetched=None))
    assert validate_strict(x.digest) == ()                       # v1（含 AssembledDigest 一致性）放行 2099：只有 v2 的 PIT 上界擋得住
    assert AssembledDigest(x.digest, x.coverage.base)
    vs = validate_v2(x)
    assert {v.stage for v in vs} == {"pit_freshness"}
    assert [v.code for v in vs] == ["pit_as_of_after_generated"] * 2
    assert "holdings" in vs[0].message and "actions" in vs[1].message


def test_pit_boundary_as_of_equal_to_generated_taipei_date_passes():
    gen_tw = NOW.astimezone(timezone(timedelta(hours=8))).date()                    # 2026-10-27（17:00 TW）
    assert gen_tw == date(2026, 10, 27)
    assert validate_v2(v2_zero_action(holdings_as_of=gen_tw, actions_as_of=gen_tw, aud=audit(fetched=NOW))) == ()
    over = v2_zero_action(holdings_as_of=gen_tw + timedelta(days=1), aud=audit(fetched=NOW))
    assert "pit_as_of_after_generated" in codes(over)


def test_pit_fetched_at_after_generated_is_rejected_and_equal_passes():
    assert validate_v2(v2_of(make_digest(), base_cov(), audit(fetched=NOW))) == ()           # fetched == generated：合規
    x = v2_of(make_digest(), base_cov(), audit(fetched=NOW + timedelta(seconds=1)))
    assert set(codes(x)) == {"pit_fetched_after_generated"} and stages(x) == {"pit_freshness"}


def test_pit_as_of_after_fetched_taipei_date_is_rejected_and_same_taipei_day_passes():
    # as_of=D(2026-10-26)。fetched=10-25 10:00Z（TW 10-25）→ as_of 晚於 fetched 的台北日
    bad = v2_of(make_digest(), base_cov(), audit(fetched=datetime(2026, 10, 25, 10, 0, tzinfo=timezone.utc)))
    assert set(codes(bad)) == {"pit_as_of_after_fetched"}
    # fetched=10-25 16:30Z＝TW 10-26 00:30：同一個台北日 → 合規（若誤用 UTC 日會誤判）
    ok = v2_of(make_digest(), base_cov(), audit(fetched=datetime(2026, 10, 25, 16, 30, tzinfo=timezone.utc)))
    assert validate_v2(ok) == ()


def test_n10_taipei_day_differs_from_utc_day_boundary():
    """generated_at＝UTC 10-27 23:30（台北已是 10-28 07:30）：as_of／fetched 的比較必須用台北日，不是 UTC 日。"""
    gen = datetime(2026, 10, 27, 23, 30, tzinfo=timezone.utc)
    fetched = datetime(2026, 10, 27, 23, 0, tzinfo=timezone.utc)                 # 台北 10-28 07:00，早於 generated
    def x_with(as_of):
        d = make_digest(entries=[], items=[], generated_at=gen)
        segs = segs_with(holdings=seg(SEGMENT_HOLDINGS, as_of=as_of), actions=seg(SEGMENT_ACTIONS, as_of=as_of))
        return v2_of(d, base_cov(total=0, shown=0, segs=segs, hold=False, act=False), audit(fetched=fetched))
    assert gen.date() != gen.astimezone(timezone(timedelta(hours=8))).date()
    assert validate_v2(x_with(date(2026, 10, 28))) == ()                         # 台北日當天：合規（UTC 日會誤判）
    over = x_with(date(2026, 10, 29))
    assert set(codes(over)) == {"pit_as_of_after_generated", "pit_as_of_after_fetched"}


def test_pit_unused_segment_dates_are_audit_only_not_enforced():
    """未採用段（例如 pit_violation）的 as_of／fetched_at 只供稽核，本就可能帶未來日。"""
    d = make_digest(market_facts=[missing("market.regime"), missing("market.light"), missing("market.health")])
    segs = segs_with(market=seg(SEGMENT_MARKET, False, WITHHELD_PIT_VIOLATION, as_of=date(2099, 1, 1)))
    aud = (SegmentAudit(SEGMENT_MARKET, F.FRESH, NOW + timedelta(days=400)),) + audit()[1:]
    assert validate_v2(v2_of(d, base_cov(segs=segs), aud)) == ()


def test_pit_limitation_a_very_old_fake_as_of_is_not_caught():
    """單向上界的已知限制（寫成測試以免被誤當成已覆蓋）：很舊的假日期擋不了；沒有可驗的可用日。"""
    x = v2_zero_action(holdings_as_of=date(2000, 1, 1), actions_as_of=date(2000, 1, 1))
    assert validate_v2(x) == ()


# ══════════════════════════════════════════════════════════════════════
# freshness 欄位間蘊含（自報、不可覆算；只檢查欄位間蘊含）
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("fr", [F.STALE, None])
def test_used_segment_requires_fresh(fr):
    x = v2_of(make_digest(), base_cov(), audit(m=fr))
    assert [v.code for v in validate_v2(x)] == ["freshness_used_requires_fresh"]


def test_no_withheld_reason_to_freshness_implication_exists_no_source():
    """已移除 `withheld_reason=stale ⇒ STALE`（無來源出處）：withheld stale 的段不因 audit 自報而被額外拒絕。"""
    for fr in (F.FRESH, F.STALE, None):
        x = v2_of(make_digest(market_facts=STALE_MARKET), base_cov(segs=MARKET_STALE_SEGS), audit(m=fr))
        assert validate_v2(x) == ()


@pytest.mark.parametrize("fr", [F.FRESH, F.STALE])
def test_fresh_or_stale_requires_a_base_as_of(fr):
    d = make_digest(market_facts=[missing("market.regime"), missing("market.light"), missing("market.health")])
    segs = segs_with(market=seg(SEGMENT_MARKET, False, "no_stamp", source=None, as_of=None))
    assert [v.code for v in validate_v2(v2_of(d, base_cov(segs=segs), audit(m=fr)))] == ["freshness_without_as_of"]
    assert validate_v2(v2_of(d, base_cov(segs=segs), audit(m=None))) == ()                  # None＝未判定：合法


def test_stale_is_representable_in_audit_while_digest_facts_stay_missing_a2i():
    """A2-i 的合法表示：Digest 事實維持 MISSING／NO_INPUT；『過期』只在 coverage base（withheld stale）與 audit（STALE）。"""
    miss = [missing("market.regime"), missing("market.light"), missing("market.health")]
    d = make_digest(market_facts=miss)
    x = v2_of(d, base_cov(segs=MARKET_STALE_SEGS), MARKET_STALE_AUDIT)
    assert all(f.status is DataStatus.MISSING and f.missing_reason is MissingReason.NO_INPUT for f in d.market.facts)
    assert validate_v2(x) == ()
    assert x.coverage.base.segments[0].withheld_reason == "stale" and x.coverage.audit[0].evidence_freshness is F.STALE
    assert not hasattr(DataStatus, "STALE_RETAINED") and DataStatus.STALE.value == "stale"   # 沒有新增 DataStatus 成員


# ══════════════════════════════════════════════════════════════════════
# 與真 v1 組裝器的相容（v1 的 STALE → MISSING／NO_INPUT 降級行為不動）
# ══════════════════════════════════════════════════════════════════════
def _assemble(macro_freshness):
    from shared.allocation_decision import build_allocation_decision
    from shared.decision_digest import HoldingKey
    from shared.risk_cap_policy import RiskCapDisclosure
    from src.services.decision_digest_assembly import EvidenceInput, assemble_digest
    from src.services.decision_digest_builder import SourceStamp
    macro = {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5, "exposure_limit_pct": 60, "defense": False,
             "risk_cap_disclosure": RiskCapDisclosure(snapshot_ts="2026-10-26 18:30:00", not_evaluated=(), disabled=(),
                                                      sahm_status=None)}
    rows = [{"代號": f"T{i}", "held": True, "_action": c, "建議動作": f"txt-{c}-T{i}", "_detail": {}}
            for i, c in enumerate(("add", "pause_add", "cut"))]
    return assemble_digest(
        generated_at=NOW, macro_state=macro,
        macro_evidence=EvidenceInput(stamp=SourceStamp("macro_state.json", D), freshness=macro_freshness),
        allocation=build_allocation_decision(macro), station_rows=rows,
        station_evidence=EvidenceInput(stamp=SourceStamp("dividend_station_service", D), freshness=F.FRESH),
        holdings_rows=[{"ticker": r["代號"], "name": "n", "held": True} for r in rows],
        holding_keys={r["代號"]: HoldingKey("pf-A", r["代號"]) for r in rows})


def test_real_v1_assembly_fresh_composes_into_a_valid_v2():
    a = _assemble(F.FRESH)
    x = v2_of(a.digest, a.coverage, audit())                 # audit 由測試明確填寫，不從 v1 推導
    assert x.digest is a.digest and validate_v2(x) == ()
    assert build_rule_summary(x.digest).lines == build_rule_summary(a.digest).lines


def test_real_v1_assembly_stale_still_degrades_to_missing_no_input_and_reason_lives_in_coverage_and_audit():
    a = _assemble(F.STALE)
    assert all(f.status is DataStatus.MISSING and f.missing_reason is MissingReason.NO_INPUT for f in a.digest.market.facts)
    assert a.digest.risk_cap.cap_pct.status is DataStatus.MISSING                            # v1 行為一個字都沒動
    by = {s.segment: s for s in a.coverage.segments}
    assert by["market"].withheld_reason == "stale" and by["risk_cap"].withheld_reason == "stale"
    x = v2_of(a.digest, a.coverage, audit(m=F.STALE, r=F.STALE))
    assert validate_v2(x) == ()
    # 不得把『過期』偽裝成已採用：used=True 的段自報 STALE／None 會被 used⇒FRESH 擋下
    assert "freshness_used_requires_fresh" in codes(v2_of(a.digest, a.coverage, audit(h=F.STALE)))
