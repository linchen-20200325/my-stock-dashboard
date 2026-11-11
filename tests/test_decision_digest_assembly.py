"""Issue #1127 P-4（S7 headless 組裝＋S8 省略揭露）— `src/services/decision_digest_assembly.py` 測試（fast lane）。

為什麼是側車（sidecar）而不是升 Digest v2：Decision Digest v1 凍結（Phase 1：不得改 `shared/decision_digest*.py`、
不得動 `MAX_ACTIONS=3`、不得新增列舉成員／confidence 語意、不得升 `SCHEMA_VERSION`）。
Digest 在形成前把行動截到 3、靜默排除資料異常列，讀者看不出少了什麼 → 完整性揭露由**獨立版本**的
`DigestCoverage`（`digest_coverage.v1`）＋ `AssembledDigest` envelope 攜帶；Digest 本身一個欄位都沒動。
升 v2（A1～A7）屬另案 Stage F。側車契約本身見 `tests/test_decision_digest_coverage.py`。

本檔守：
- 證據規則 fail-closed：只有 fresh＋PIT 通過才把 stamp 交給 builder；stale／undetermined／missing／FETCH_FAILED／
  UNDETERMINED／PIT 違反一律不採用並在 coverage 記錄原因；`NO_NEW_DATA` 與 freshness 是兩軸、不互相蘊含；
- 省略揭露：候選數／shown／omitted 精確（0／1／2／3／4／7，含剛好 MAX 與 MAX+1）、排除列、無鍵持股；
- builder 純加性修改的 parity：`plan_action_selection` 的 `chosen` ＝ `build_decision_digest` 實際搬運者
  ＝ 舊路徑 `sorted(candidates)[:MAX_ACTIONS]`（固定種子隨機輸入）；
- 純函式／無副作用／不讀 session／決定性；
- 突變測試（teeth）：暫時拔掉關鍵邏輯，對應檢查必須轉紅。
"""
from __future__ import annotations

import ast
import builtins
import dataclasses
import inspect
import json
import random
import socket
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

import src.services.decision_digest_assembly as A
import src.services.decision_digest_builder as B
from shared.allocation_decision import build_allocation_decision
from shared.decision_digest import (
    MAX_ACTIONS, SCHEMA_VERSION, Availability, DataStatus, HoldingKey, MissingReason, validate,
)
from shared.decision_digest_coverage import (
    COVERAGE_SCHEMA_VERSION, SEGMENT_ACTIONS, SEGMENT_HOLDINGS, SEGMENT_MARKET, SEGMENT_RISK_CAP, SEGMENTS,
    WITHHELD_FETCH_FAILED, WITHHELD_NO_STAMP, WITHHELD_NOT_LOADED, WITHHELD_PARTIAL, WITHHELD_PIT_VIOLATION,
    WITHHELD_STALE, WITHHELD_UNDETERMINED, DigestCoverage, validate_coverage,
)
from shared.decision_digest_rules import ACTION_RULE_IDS, validate_strict
from shared.fetch_outcome import FetchOutcome as O
from shared.freshness_policy import FreshnessStatus as F
from shared.risk_cap_policy import RiskCapDisclosure
from shared.station_specs import KEY_INVALID_INPUTS, KEY_INVALID_LIGHTS
from src.services.decision_digest_assembly import AssembledDigest, EvidenceInput, assemble_digest
from src.services.decision_digest_builder import SourceStamp, build_decision_digest, plan_action_selection

REPO = Path(__file__).resolve().parents[1]
ASSEMBLY = REPO / "src" / "services" / "decision_digest_assembly.py"
NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)          # 台北 2026-10-27 17:00
D = date(2026, 10, 26)
MACRO_STAMP = SourceStamp("macro_state.json", D)
STATION_STAMP = SourceStamp("dividend_station_service", D)


# ── 夾具 ─────────────────────────────────────────────────────────────────
def disclosure(ts="2026-10-26 18:30:00"):
    return RiskCapDisclosure(snapshot_ts=ts, not_evaluated=(), disabled=(), sahm_status=None)


def macro(**over):
    base = {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5,
            "exposure_limit_pct": 60, "defense": False, "risk_cap_disclosure": disclosure()}
    base.update(over)
    return base


def alloc(ms=None):
    return build_allocation_decision(ms if ms is not None else macro())


def fresh(stamp=MACRO_STAMP, up=None):
    return EvidenceInput(stamp=stamp, freshness=F.FRESH, upstream_state=up)


def row(ticker, code="add", held=True, **extra):
    r = {"代號": ticker, "held": held, "_action": code, "建議動作": f"txt-{code}-{ticker}", "_detail": {}}
    r.update(extra)
    return r


def holdings_for(*tickers, held=True):
    return [{"ticker": t, "name": f"n-{t}", "held": held} for t in tickers]


def keys_for(*tickers, pid="pf-A"):
    return {t: HoldingKey(pid, t) for t in tickers}


_CODES = ("add", "pause_add", "cut", "take_profit_force", "take_profit_partial", "add", "pause_add")


def candidate_rows(n):
    return [row(f"T{i}", _CODES[i % len(_CODES)]) for i in range(n)]


def full_kwargs(n_candidates=2, **over):
    rows = candidate_rows(n_candidates)
    tickers = [r["代號"] for r in rows]
    kw = dict(generated_at=NOW, macro_state=macro(), macro_evidence=fresh(MACRO_STAMP), allocation=alloc(),
              station_rows=rows, station_evidence=fresh(STATION_STAMP),
              holdings_rows=holdings_for(*tickers), holding_keys=keys_for(*tickers))
    kw.update(over)
    return kw


def seg(a, name):
    return {s.segment: s for s in a.coverage.segments}[name]


def facts_all(d):
    out = list(d.market.facts) + [d.risk_cap.cap_pct, d.risk_cap.exposure_lo_pct, d.risk_cap.exposure_hi_pct]
    for e in d.holdings.entries:
        out += list(e.facts)
    return out


# ════════════════════════════════════════════════════════════════════════
# 0 evidence／缺資料：fail-closed
# ════════════════════════════════════════════════════════════════════════
def test_zero_evidence_everything_missing_and_incomplete():
    a = assemble_digest(generated_at=NOW)
    assert validate_strict(a.digest) == () and validate_coverage(a.coverage) == ()
    assert a.digest == build_decision_digest(generated_at=NOW)               # 沒證據 ＝ 沒輸入
    assert a.coverage.is_complete is False
    assert all(not s.used and s.withheld_reason == WITHHELD_NO_STAMP and s.source is None and s.as_of is None
               for s in a.coverage.segments)
    assert [s.segment for s in a.coverage.segments] == list(SEGMENTS)


def test_zero_evidence_unknown_counts_are_none_not_zero():
    c = assemble_digest(generated_at=NOW).coverage
    assert c.actions_total_eligible is None and c.actions_omitted_count is None
    assert c.excluded_invalid_rows is None and c.unkeyed_held_count is None
    assert c.actions_shown == 0 and c.actions_max == MAX_ACTIONS


def test_missing_is_never_described_as_safe_neutral_or_zero():
    """digest 端：市場事實 MISSING＋NO_INPUT、無數值、無任何 OK 事實；coverage 端：沒有 safe／neutral／confidence 欄。"""
    a = assemble_digest(generated_at=NOW)
    assert all(f.status is DataStatus.MISSING and f.missing_reason is MissingReason.NO_INPUT
               and f.value is None and f.text is None for f in a.digest.market.facts)
    assert not any(f.status is DataStatus.OK for f in facts_all(a.digest))
    names = {f.name for f in dataclasses.fields(DigestCoverage)}
    assert not any(b in n for n in names for b in ("confidence", "score", "neutral", "safe"))


def test_missing_with_holdings_rows_but_no_station_evidence():
    a = assemble_digest(generated_at=NOW, holdings_rows=holdings_for("A", "B"), holding_keys=keys_for("A"))
    assert a.coverage.unkeyed_held_count == 1          # 持有列有給 → 無鍵數已知（與證據無關）
    assert a.coverage.actions_total_eligible is None    # 站內證據缺 → 候選數未知
    assert a.coverage.is_complete is False


def test_envelope_to_dict_keeps_digest_v1_untouched_and_is_json_serializable():
    a = assemble_digest(**full_kwargs(2))
    d = a.to_dict()
    assert set(d) == {"digest", "coverage"}
    assert d["digest"] == a.digest.to_dict() and d["digest"]["schema_version"] == SCHEMA_VERSION == "decision_digest.v1"
    assert d["coverage"]["schema_version"] == COVERAGE_SCHEMA_VERSION == "digest_coverage.v1"
    assert "coverage" not in d["digest"]                 # 側車不進 Digest 本體
    json.dumps(d, ensure_ascii=False)


# ════════════════════════════════════════════════════════════════════════
# 完整路徑 ＋ provenance
# ════════════════════════════════════════════════════════════════════════
def test_all_fresh_complete_and_digest_equals_direct_builder_call():
    kw = full_kwargs(2)
    a = assemble_digest(**kw)
    direct = build_decision_digest(
        generated_at=NOW, macro_state=kw["macro_state"], macro_stamp=MACRO_STAMP, allocation=kw["allocation"],
        station_rows=kw["station_rows"], station_stamp=STATION_STAMP, holdings_rows=kw["holdings_rows"],
        holding_keys=kw["holding_keys"])
    assert a.digest == direct                                       # 全 fresh 時組裝器是純 pass-through
    assert a.coverage.is_complete is True
    assert (a.coverage.actions_total_eligible, a.coverage.actions_shown, a.coverage.actions_omitted_count) == (2, 2, 0)
    assert (a.coverage.excluded_invalid_rows, a.coverage.unkeyed_held_count) == (0, 0)


def test_provenance_source_and_as_of_traceable_into_coverage():
    a = assemble_digest(**full_kwargs(2))
    s = seg(a, SEGMENT_MARKET)
    assert (s.used, s.source, s.as_of, s.withheld_reason) == (True, "macro_state.json", D, None)
    s = seg(a, SEGMENT_RISK_CAP)       # 取該段所有 OK 事實中最舊的 provenance；同日取第一個（cap_pct，來源是快照）
    assert (s.used, s.source, s.as_of, s.withheld_reason) == (True, "risk_cap_snapshot", D, None)
    for name in (SEGMENT_HOLDINGS, SEGMENT_ACTIONS):
        s = seg(a, name)
        assert (s.used, s.source, s.as_of, s.withheld_reason) == (True, "dividend_station_service", D, None)
    # 與 Digest 內事實的血緣一致
    assert all(f.provenance.as_of == D and f.provenance.source == "macro_state.json" for f in a.digest.market.facts)
    assert all(f.provenance.source == "dividend_station_service" for e in a.digest.holdings.entries for f in e.facts)


def test_zero_actions_is_not_complete_because_v1_cannot_tell_nothing_to_do_from_cannot_tell():
    """v1 builder 對「沒有任何行動」讓 holdings／actions 段 UNAVAILABLE（無法區分『沒事做』與『判不出來』）。
    coverage 以 digest_*_available 納入 is_complete：零行動 ⇒ is_complete=False（保守 fail-closed）。
    這是 v1 限制，**不是**「有東西漏了」——計數都是已知的 0，證據段也都 used。"""
    for kw in (full_kwargs(0, station_rows=[], holdings_rows=[]),
               full_kwargs(0, station_rows=[], holdings_rows=holdings_for("A"), holding_keys=keys_for("A"))):
        a = assemble_digest(**kw)
        assert a.digest.actions.availability is Availability.UNAVAILABLE
        assert (a.coverage.digest_holdings_available, a.coverage.digest_actions_available) == (False, False)
        assert a.coverage.actions_total_eligible == 0 and a.coverage.actions_omitted_count == 0
        assert all(s.used for s in a.coverage.segments)
        assert a.coverage.is_complete is False


# ════════════════════════════════════════════════════════════════════════
# 證據被拒用（stale／undetermined／missing／FETCH_FAILED／UNDETERMINED／NO_NEW_DATA×stale／PIT）
# ════════════════════════════════════════════════════════════════════════
_WITHHELD_CASES = [
    pytest.param(F.STALE, None, WITHHELD_STALE, id="stale"),
    pytest.param(F.MISSING, None, WITHHELD_NO_STAMP, id="freshness-missing"),
    pytest.param(F.UNDETERMINED, None, WITHHELD_UNDETERMINED, id="freshness-undetermined"),
    pytest.param(None, None, WITHHELD_UNDETERMINED, id="freshness-not-judged"),
    pytest.param(F.FRESH, O.FETCH_FAILED, WITHHELD_FETCH_FAILED, id="fresh-but-fetch-failed"),
    pytest.param(F.FRESH, O.UNDETERMINED, WITHHELD_UNDETERMINED, id="fresh-but-fetch-undetermined"),
    pytest.param(F.STALE, O.NO_NEW_DATA, WITHHELD_STALE, id="NO_NEW_DATA-x-stale-still-withheld"),
    pytest.param(F.UNDETERMINED, O.NO_NEW_DATA, WITHHELD_UNDETERMINED, id="NO_NEW_DATA-x-undetermined"),
    pytest.param(F.STALE, O.FETCH_FAILED, WITHHELD_FETCH_FAILED, id="stale-and-failed-first-reason-wins"),
]


@pytest.mark.parametrize("freshness,up,reason", _WITHHELD_CASES)
def test_macro_evidence_withheld_never_reaches_digest(freshness, up, reason):
    ev = EvidenceInput(MACRO_STAMP, freshness, up)
    a = assemble_digest(**full_kwargs(2, macro_evidence=ev))
    for name in (SEGMENT_MARKET, SEGMENT_RISK_CAP):
        s = seg(a, name)
        assert s.used is False and s.withheld_reason == reason
        assert (s.source, s.as_of) == ("macro_state.json", D)          # 被拒的證據仍可追溯來源與日期
    d = a.digest
    assert all(f.status is DataStatus.MISSING and f.provenance.as_of is None for f in d.market.facts)
    assert d.risk_cap.cap_valid is False and d.risk_cap.availability is Availability.UNAVAILABLE
    assert not any(f.provenance.as_of == D and f.provenance.source == "macro_state.json" for f in facts_all(d))
    assert a.coverage.is_complete is False
    # 站內證據不受影響
    assert seg(a, SEGMENT_ACTIONS).used is True and a.coverage.actions_total_eligible == 2


@pytest.mark.parametrize("freshness,up,reason", _WITHHELD_CASES)
def test_station_evidence_withheld_never_reaches_digest(freshness, up, reason):
    ev = EvidenceInput(STATION_STAMP, freshness, up)
    a = assemble_digest(**full_kwargs(5, station_evidence=ev))
    for name in (SEGMENT_HOLDINGS, SEGMENT_ACTIONS):
        s = seg(a, name)
        assert s.used is False and s.withheld_reason == reason and s.as_of == D
    assert a.digest.actions.items == () and a.digest.actions.availability is Availability.UNAVAILABLE
    assert not any(e.facts for e in a.digest.holdings.entries)
    c = a.coverage
    assert (c.actions_total_eligible, c.actions_omitted_count, c.excluded_invalid_rows) == (None, None, None)
    assert c.actions_shown == 0 and c.is_complete is False
    assert c.unkeyed_held_count == 0                                    # 持有列有給 → 已知，與證據無關
    assert seg(a, SEGMENT_MARKET).used is True                           # macro 不受影響


def test_fresh_with_no_new_data_is_used_but_stale_is_not():
    """兩軸不互相蘊含：NO_NEW_DATA 只表示『這次抓取成功但來源無新資料』，不是新鮮。"""
    ok = assemble_digest(**full_kwargs(2, macro_evidence=fresh(MACRO_STAMP, O.NO_NEW_DATA)))
    assert seg(ok, SEGMENT_MARKET).used is True
    bad = assemble_digest(**full_kwargs(2, macro_evidence=EvidenceInput(MACRO_STAMP, F.STALE, O.NO_NEW_DATA)))
    assert seg(bad, SEGMENT_MARKET).used is False and seg(bad, SEGMENT_MARKET).withheld_reason == WITHHELD_STALE
    assert not any(f.status is DataStatus.OK for f in bad.digest.market.facts)


def test_evidence_without_stamp_or_evidence_none_is_no_stamp():
    for ev in (None, EvidenceInput(None, F.FRESH, None), EvidenceInput()):
        a = assemble_digest(**full_kwargs(2, macro_evidence=ev))
        assert seg(a, SEGMENT_MARKET).withheld_reason == WITHHELD_NO_STAMP
        assert (seg(a, SEGMENT_MARKET).source, seg(a, SEGMENT_MARKET).as_of) == (None, None)   # 不補日期


def test_never_substitutes_generated_at_for_missing_as_of():
    a = assemble_digest(**full_kwargs(2, macro_evidence=None))
    dates = {s.as_of for s in a.coverage.segments if s.segment in (SEGMENT_MARKET, SEGMENT_RISK_CAP)}
    assert dates == {None}
    assert not any(f.provenance.as_of == NOW.astimezone(timezone(timedelta(hours=8))).date()
                   for f in a.digest.market.facts)


def test_withheld_macro_equals_builder_with_no_macro_inputs():
    """被拒用 ⇒ stamp 與 macro_state／allocation 都不傳：digest 的 market／risk_cap 與「沒給 macro」完全相同。"""
    a = assemble_digest(**full_kwargs(2, macro_evidence=EvidenceInput(MACRO_STAMP, F.STALE)))
    nothing = build_decision_digest(generated_at=NOW)
    assert a.digest.market == nothing.market and a.digest.risk_cap == nothing.risk_cap


def test_partial_macro_used_station_withheld_and_vice_versa():
    a = assemble_digest(**full_kwargs(2, station_evidence=EvidenceInput(STATION_STAMP, F.STALE)))
    assert [seg(a, n).used for n in SEGMENTS] == [True, True, False, False]
    b = assemble_digest(**full_kwargs(2, macro_evidence=EvidenceInput(MACRO_STAMP, F.UNDETERMINED)))
    assert [seg(b, n).used for n in SEGMENTS] == [False, False, True, True]
    assert a.coverage.is_complete is False and b.coverage.is_complete is False


# ── 證據可用，但上游這一段沒載入／只採到一部分 ──────────────────────────────
def test_macro_not_loaded_is_not_used_even_with_fresh_evidence():
    a = assemble_digest(**full_kwargs(2, macro_state=macro(is_loaded=False)))
    assert seg(a, SEGMENT_MARKET).used is False and seg(a, SEGMENT_MARKET).withheld_reason == WITHHELD_NOT_LOADED
    assert a.coverage.is_complete is False


def test_macro_state_none_means_not_loaded():
    a = assemble_digest(**full_kwargs(2, macro_state=None, allocation=None))
    assert seg(a, SEGMENT_MARKET).withheld_reason == WITHHELD_NOT_LOADED
    assert seg(a, SEGMENT_RISK_CAP).withheld_reason == WITHHELD_NOT_LOADED


def test_missing_allocation_makes_risk_cap_partial():
    a = assemble_digest(**full_kwargs(2, allocation=None))
    assert seg(a, SEGMENT_MARKET).used is True
    assert seg(a, SEGMENT_RISK_CAP).used is False and seg(a, SEGMENT_RISK_CAP).withheld_reason == WITHHELD_PARTIAL
    assert a.digest.risk_cap.availability is Availability.PARTIAL


def test_invalid_health_makes_market_partial():
    a = assemble_digest(**full_kwargs(2, macro_state=macro(health=float("nan"))))
    assert seg(a, SEGMENT_MARKET).used is False and seg(a, SEGMENT_MARKET).withheld_reason == WITHHELD_PARTIAL
    assert a.coverage.is_complete is False


def test_station_rows_missing_with_fresh_evidence_is_not_loaded():
    a = assemble_digest(**full_kwargs(2, station_rows=None))
    assert seg(a, SEGMENT_ACTIONS).withheld_reason == WITHHELD_NOT_LOADED
    assert a.coverage.actions_total_eligible is None


def test_holdings_rows_missing_with_fresh_evidence_is_not_loaded_and_unkeyed_none():
    a = assemble_digest(**full_kwargs(2, holdings_rows=None))
    assert seg(a, SEGMENT_HOLDINGS).withheld_reason == WITHHELD_NOT_LOADED
    assert a.coverage.unkeyed_held_count is None          # 不是 0
    assert a.digest.holdings.unkeyed_count == 0 and a.digest.holdings.availability is Availability.UNAVAILABLE
    assert a.coverage.is_complete is False


# ════════════════════════════════════════════════════════════════════════
# PIT（沿用 Provenance／Digest 既有規則）
# ════════════════════════════════════════════════════════════════════════
def _pit_stamp(as_of=D, fetched=None):
    return SourceStamp("src", as_of, fetched)


@pytest.mark.parametrize("as_of,fetched,gen,expect_ok", [
    (D, None, NOW, True),
    (date(2026, 10, 27), None, NOW, True),                                       # as_of＝generated 台北日：合法
    (date(2026, 10, 28), None, NOW, False),                                      # as_of > generated 台北日
    (D, datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc), NOW, False),         # as_of > fetched 台北日
    (D, datetime(2026, 10, 26, 1, 0, tzinfo=timezone.utc), NOW, True),           # fetched 台北日 10-26 ＝ as_of
    (D, datetime(2026, 10, 27, 9, 30, tzinfo=timezone.utc), NOW, False),         # fetched_at > generated_at
    (date(2026, 10, 27), None, datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc), False),  # TW 10-26 18:00 < as_of
    (date(2026, 10, 27), None, datetime(2026, 10, 26, 20, 0, tzinfo=timezone.utc), True),   # TW 10-27 04:00（UTC 與 TW 差一天）
])
def test_pit_rules(as_of, fetched, gen, expect_ok):
    stamp = _pit_stamp(as_of, fetched)
    a = assemble_digest(generated_at=gen, macro_state=macro(), macro_evidence=fresh(stamp), allocation=alloc())
    s = seg(a, SEGMENT_MARKET)
    assert s.used is expect_ok
    if not expect_ok:
        assert s.withheld_reason == WITHHELD_PIT_VIOLATION
        assert (s.source, s.as_of) == ("src", as_of)                              # 照實記錄，不改日期
        assert not any(f.status is DataStatus.OK for f in a.digest.market.facts)
        # 若直接把違規 stamp 交給 builder 會 fail loud —— 組裝器改為不採用並揭露
        with pytest.raises(ValueError):
            build_decision_digest(generated_at=gen, macro_state=macro(), macro_stamp=stamp)


def test_pit_violation_on_station_evidence_withholds_holdings_and_actions():
    bad = fresh(_pit_stamp(date(2026, 10, 28)))
    a = assemble_digest(**full_kwargs(3, station_evidence=bad))
    for n in (SEGMENT_HOLDINGS, SEGMENT_ACTIONS):
        assert seg(a, n).withheld_reason == WITHHELD_PIT_VIOLATION
    assert a.digest.actions.items == ()


def test_naive_or_non_datetime_generated_at_fails_loud():
    with pytest.raises(ValueError):
        assemble_digest(generated_at=datetime(2026, 10, 27, 9, 0))
    with pytest.raises(ValueError):
        assemble_digest(generated_at="2026-10-27")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        assemble_digest(generated_at=datetime(2026, 10, 27, 17, 0, tzinfo=timezone(timedelta(hours=8))))  # 非 UTC → builder 拒


# ════════════════════════════════════════════════════════════════════════
# 候選數／omitted_count 精確
# ════════════════════════════════════════════════════════════════════════
def _expected_shown_tickers(n):
    rows = candidate_rows(n)
    order = sorted(rows, key=lambda r: ACTION_RULE_IDS.index(r["_action"]))   # 穩定排序 ＝ Q4 序
    return [r["代號"] for r in order[:MAX_ACTIONS]]


def _check_counts_exact(n):
    a = assemble_digest(**full_kwargs(n))
    c = a.coverage
    assert c.actions_total_eligible == n
    assert c.actions_shown == min(n, MAX_ACTIONS) == len(a.digest.actions.items)
    assert c.actions_omitted_count == max(n - MAX_ACTIONS, 0)
    assert c.actions_max == MAX_ACTIONS
    assert [i.target.symbol for i in a.digest.actions.items] == _expected_shown_tickers(n)
    assert a.coverage.is_complete is (1 <= n <= MAX_ACTIONS)     # n=0：v1 無法區分「沒事做」與「判不出來」→ False


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 7])
def test_candidate_counts_and_omitted_are_exact(n):
    _check_counts_exact(n)


def test_exactly_max_is_complete_and_max_plus_one_is_not():
    assert assemble_digest(**full_kwargs(MAX_ACTIONS)).coverage.is_complete is True
    over = assemble_digest(**full_kwargs(MAX_ACTIONS + 1))
    assert over.coverage.actions_omitted_count == 1 and over.coverage.is_complete is False


def test_omitted_candidates_are_the_lowest_priority_ones():
    rows = [row("A", "add"), row("B", "pause_add"), row("C", "cut"), row("D", "take_profit_force")]
    plan = plan_action_selection(station_rows=rows, station_stamp=STATION_STAMP,
                                 holdings_rows=holdings_for("A", "B", "C", "D"), holding_keys=keys_for("A", "B", "C", "D"))
    assert [k.symbol for k, _, _ in plan.ordered] == ["C", "D", "B", "A"]
    assert [k.symbol for k, _, _ in plan.chosen] == ["C", "D", "B"]
    assert plan.total_eligible == 4 and plan.omitted_count == 1


def test_shown_never_exceeds_max_and_actions_max_is_the_digest_constant():
    a = assemble_digest(**full_kwargs(7))
    assert a.coverage.actions_shown <= MAX_ACTIONS and a.coverage.actions_max == MAX_ACTIONS
    assert a.coverage.actions_total_eligible == 7 and a.coverage.actions_omitted_count == 4
    # 組裝檔內不得硬編碼 3：actions_max 必須經由 MAX_ACTIONS
    tree = ast.parse(ASSEMBLY.read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) is int and n.value == 3]


def test_candidates_beyond_ui_top_n_are_still_counted():
    """契約 §2／§9：不因 UI Top-N 少算；候選全量進 coverage。"""
    a = assemble_digest(**full_kwargs(50))
    assert a.coverage.actions_total_eligible == 50 and a.coverage.actions_omitted_count == 47


# ── 排除列 ──────────────────────────────────────────────────────────────
def _check_excluded_counts():
    rows = [row("A", "cut"),
            row("B", "cut", **{KEY_INVALID_LIGHTS: ["x"]}),
            row("C", "add", **{KEY_INVALID_INPUTS: ["y"]}),
            row("D", "add", _detail={"error": "boom"}),
            row("E", "premium", **{KEY_INVALID_LIGHTS: ["x"]}),       # 非行動碼但資料異常 → 仍計入排除
            row("F", "cut", held=False, **{KEY_INVALID_LIGHTS: ["x"]}),   # 非持有 → 不計
            row("G", "add", **{KEY_INVALID_LIGHTS: []}),               # 空 list ＝ 無異常
            row("H", "pause_add", _detail={})]
    ts = [r["代號"] for r in rows]
    a = assemble_digest(**full_kwargs(0, station_rows=rows, holdings_rows=holdings_for(*ts), holding_keys=keys_for(*ts)))
    return a


def test_excluded_invalid_rows_counted_and_rows_not_carried():
    a = _check_excluded_counts()
    assert a.coverage.excluded_invalid_rows == 4                        # B C D E
    assert a.coverage.actions_total_eligible == 3                       # A G H
    assert {i.target.symbol for i in a.digest.actions.items} == {"A", "G", "H"}
    assert a.coverage.is_complete is False                              # 有被排除的列 → 不完整


def test_excluded_zero_when_no_invalid_rows():
    a = assemble_digest(**full_kwargs(2))
    assert a.coverage.excluded_invalid_rows == 0


def test_excluded_unknown_when_station_not_evaluated():
    a = assemble_digest(**full_kwargs(2, station_rows=None))
    assert a.coverage.excluded_invalid_rows is None


# ── 無鍵持股 ────────────────────────────────────────────────────────────
def test_unkeyed_held_count_matches_digest_and_blocks_completeness():
    rows = candidate_rows(1)
    a = assemble_digest(**full_kwargs(0, station_rows=rows,
                                      holdings_rows=holdings_for("T0", "X", "Y") + holdings_for("Z", held=False),
                                      holding_keys=keys_for("T0")))
    assert a.coverage.unkeyed_held_count == 2 == a.digest.holdings.unkeyed_count      # X、Y；Z 非持有不計
    assert a.coverage.is_complete is False


def test_unkeyed_zero_means_known_zero():
    a = assemble_digest(**full_kwargs(2))
    assert a.coverage.unkeyed_held_count == 0


# ── 重複鍵 ──────────────────────────────────────────────────────────────
def test_duplicate_holding_keys_fail_loud():
    with pytest.raises(ValueError, match="duplicate_holding_key"):
        assemble_digest(**full_kwargs(0, station_rows=[row("A")], holdings_rows=holdings_for("A", "A"),
                                      holding_keys=keys_for("A")))


def test_duplicate_station_rows_for_one_holding_fail_loud():
    with pytest.raises(ValueError, match="duplicate_action_id"):
        assemble_digest(**full_kwargs(0, station_rows=[row("A"), row("A", "cut")], holdings_rows=holdings_for("A"),
                                      holding_keys=keys_for("A")))


def test_rule_layer_drift_still_fails_loud_through_assembly():
    with pytest.raises(ValueError, match="建議動作"):
        assemble_digest(**full_kwargs(0, station_rows=[row("A", "cut", **{"建議動作": ""})],
                                      holdings_rows=holdings_for("A"), holding_keys=keys_for("A")))


# ════════════════════════════════════════════════════════════════════════
# 決定性／排序穩定
# ════════════════════════════════════════════════════════════════════════
def test_same_input_twice_is_equal_including_serialization():
    a, b = assemble_digest(**full_kwargs(7)), assemble_digest(**full_kwargs(7))
    assert a == b and a.coverage == b.coverage
    assert json.dumps(a.to_dict(), ensure_ascii=False) == json.dumps(b.to_dict(), ensure_ascii=False)


def test_input_order_shuffle_keeps_q4_order_for_distinct_tiers():
    rows = [row("A", "add"), row("B", "pause_add"), row("C", "cut"), row("D", "take_profit_force"),
            row("E", "take_profit_partial")]
    ts = [r["代號"] for r in rows]
    base = assemble_digest(**full_kwargs(0, station_rows=rows, holdings_rows=holdings_for(*ts), holding_keys=keys_for(*ts)))
    assert [i.target.symbol for i in base.digest.actions.items] == ["C", "D", "E"]
    rng = random.Random(7)
    for _ in range(25):
        sh = rows[:]
        rng.shuffle(sh)
        hs = holdings_for(*ts)
        rng.shuffle(hs)
        got = assemble_digest(**full_kwargs(0, station_rows=sh, holdings_rows=hs, holding_keys=keys_for(*ts)))
        assert [i.target.symbol for i in got.digest.actions.items] == ["C", "D", "E"]
        assert got.coverage == base.coverage


def test_same_tier_ties_follow_input_order_stably():
    rows = [row(t, "add") for t in ("Q", "P", "R", "S", "T")]
    ts = [r["代號"] for r in rows]
    a = assemble_digest(**full_kwargs(0, station_rows=rows, holdings_rows=holdings_for(*ts), holding_keys=keys_for(*ts)))
    assert [i.target.symbol for i in a.digest.actions.items] == ["Q", "P", "R"]
    assert a.coverage.actions_omitted_count == 2


# ════════════════════════════════════════════════════════════════════════
# envelope：不一致被拒、frozen、型別
# ════════════════════════════════════════════════════════════════════════
def _good():
    return assemble_digest(**full_kwargs(5))


@pytest.mark.parametrize("mutate", [
    lambda c: dataclasses.replace(c, actions_shown=c.actions_shown - 1, actions_omitted_count=c.actions_omitted_count + 1),
    lambda c: dataclasses.replace(c, actions_total_eligible=2, actions_omitted_count=0),   # total<shown(3)：自相矛盾
    lambda c: dataclasses.replace(c, unkeyed_held_count=1),
    lambda c: dataclasses.replace(c, unkeyed_held_count=None),
    lambda c: dataclasses.replace(c, segments=tuple(
        dataclasses.replace(s, used=False, withheld_reason="stale") if s.segment == "market" else s for s in c.segments)),
    lambda c: dataclasses.replace(c, segments=tuple(
        dataclasses.replace(s, used=False, withheld_reason="stale") if s.segment == "actions" else s for s in c.segments)),
    lambda c: dataclasses.replace(c, actions_shown=True),                # 型別偽裝 → coverage 本身違規
    lambda c: dataclasses.replace(c, actions_max=MAX_ACTIONS + 1),
])
def test_inconsistent_envelope_is_rejected(mutate):
    good = _good()
    with pytest.raises(ValueError):
        AssembledDigest(digest=good.digest, coverage=mutate(good.coverage))


def test_envelope_rejects_wrong_types_and_mismatched_digest():
    good = _good()
    with pytest.raises(ValueError):
        AssembledDigest(digest=None, coverage=good.coverage)               # type: ignore[arg-type]
    with pytest.raises(ValueError):
        AssembledDigest(digest=good.digest, coverage="x")                  # type: ignore[arg-type]
    other = assemble_digest(**full_kwargs(0, station_rows=[], holdings_rows=[]))
    with pytest.raises(ValueError):                                         # 別份 digest 的 coverage
        AssembledDigest(digest=good.digest, coverage=other.coverage)


def test_market_segment_claiming_used_when_facts_missing_is_rejected():
    empty = assemble_digest(generated_at=NOW)
    forged = dataclasses.replace(empty.coverage, segments=tuple(
        dataclasses.replace(s, used=True, source="x", as_of=D, withheld_reason=None) if s.segment == "market" else s
        for s in empty.coverage.segments))
    with pytest.raises(ValueError):
        AssembledDigest(digest=empty.digest, coverage=forged)


def test_envelope_frozen_and_evidence_frozen():
    a = _good()
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.coverage = a.coverage                                             # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        fresh().freshness = F.STALE                                         # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan_action_selection().evaluated = True                            # type: ignore[misc]


def test_evidence_input_type_checks_fail_loud():
    with pytest.raises(TypeError):
        EvidenceInput(stamp="2026-10-26")                                   # type: ignore[arg-type]
    with pytest.raises(TypeError):
        EvidenceInput(stamp=MACRO_STAMP, freshness="fresh")                 # type: ignore[arg-type]
    with pytest.raises(TypeError):
        EvidenceInput(stamp=MACRO_STAMP, freshness=F.FRESH, upstream_state="FETCH_FAILED")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        assemble_digest(generated_at=NOW, macro_evidence=MACRO_STAMP)      # type: ignore[arg-type]
    with pytest.raises(TypeError):
        assemble_digest(generated_at=NOW, station_rows={"a": 1})           # builder 的輸入驗證仍然生效


def test_assemble_signature_accepts_no_ui_parameters():
    params = set(inspect.signature(assemble_digest).parameters)
    assert params == {"generated_at", "macro_state", "macro_evidence", "allocation", "station_rows",
                      "station_evidence", "holdings_rows", "holding_keys"}
    assert not any(k in p for p in params for k in ("top_n", "expanded", "session", "industry", "pick"))


# ════════════════════════════════════════════════════════════════════════
# builder 純加性修改的 parity（固定種子隨機輸入）
# ════════════════════════════════════════════════════════════════════════
def _random_case(rng):
    pool = [f"T{i}" for i in range(12)]
    tickers = rng.sample(pool, rng.randrange(0, 9))
    codes = list(ACTION_RULE_IDS) + ["premium", "cruise", "zzz", None]
    rows = []
    for t in tickers:
        r = {"代號" if rng.random() < .7 else "ticker": t, "_action": rng.choice(codes),
             "建議動作": "txt-" + t, "_detail": rng.choice([{}, {}, {"error": "x"}, None])}
        h = rng.random()
        if h < .85:
            r["held"] = True
        elif h < .95:
            r["held"] = False
        if rng.random() < .15:
            r[KEY_INVALID_LIGHTS] = ["a"]
        if rng.random() < .1:
            r[KEY_INVALID_INPUTS] = ["b"]
        rows.append(r)
    hold = []
    for t in tickers:                                 # 持有列：多數同 ticker；有些大小寫不符、有些缺席
        x = rng.random()
        if x < .70:
            hold.append({"ticker": t, "held": rng.random() < .85})
        elif x < .80:
            hold.append({"ticker": t.lower(), "held": True})
    for t in rng.sample(pool, rng.randrange(0, 3)):   # 站內沒有的額外持股
        if t not in tickers:
            hold.append({"ticker": t, "held": True})
    rng.shuffle(hold)
    keys = {h["ticker"]: HoldingKey("pf", h["ticker"]) for h in hold if rng.random() < .8}
    return rows, hold, keys


def _tk(r):
    t = r.get("ticker")
    if t is None:
        t = r.get("代號")
    return t if type(t) is str and t.strip() else None


def _brute_excluded(rows):
    n = 0
    for r in rows:
        if r.get("held") is not True:
            continue
        d = r.get("_detail")
        if r.get(KEY_INVALID_LIGHTS) or r.get(KEY_INVALID_INPUTS) or (isinstance(d, dict) and d.get("error")):
            n += 1
    return n


def _brute_unmatched(rows, hold, keys):
    """獨立的 oracle：held、無異常、有行動碼，但 ticker 對不上（持有且有鍵的）持股。"""
    keyed = {keys.get(_tk(h)) for h in hold if h.get("held") is True and keys.get(_tk(h)) is not None}
    n = 0
    for r in rows:
        d = r.get("_detail")
        if (r.get("held") is True and not r.get(KEY_INVALID_LIGHTS) and not r.get(KEY_INVALID_INPUTS)
                and not (isinstance(d, dict) and d.get("error")) and r.get("_action") in ACTION_RULE_IDS):
            k = keys.get(_tk(r))
            if k is None or k not in keyed:
                n += 1
    return n


def _brute_without_station(rows, hold):
    covered = {_tk(r) for r in rows if r.get("held") is True and _tk(r) is not None}
    return sum(1 for h in hold if h.get("held") is True and (_tk(h) is None or _tk(h) not in covered))


def _parity_run(seed, cases):
    rng = random.Random(seed)
    built = unmatched_seen = without_seen = 0
    for _ in range(cases):
        rows, hold, keys = _random_case(rng)
        plan = plan_action_selection(station_rows=rows, station_stamp=STATION_STAMP, holdings_rows=hold, holding_keys=keys)
        assert plan.unmatched_station_rows == _brute_unmatched(rows, hold, keys)
        assert plan.holdings_without_station_row == _brute_without_station(rows, hold)
        assert plan.excluded_invalid_rows == _brute_excluded(rows)
        unmatched_seen += plan.unmatched_station_rows > 0
        without_seen += plan.holdings_without_station_row > 0
        try:
            d = build_decision_digest(generated_at=NOW, station_rows=rows, station_stamp=STATION_STAMP,
                                      holdings_rows=hold, holding_keys=keys)
        except ValueError as e:
            assert str(e).startswith("Decision Digest 契約違規")             # 只有 Digest 契約違規可以讓兩者分歧
            continue
        built += 1
        # 舊路徑：候選（保持輸入順序）→ 穩定依 Q4 序排序 → 截斷到 MAX_ACTIONS
        keyed = frozenset(keys[_tk(h)] for h in hold if h.get("held") is True and _tk(h) in keys)
        legacy = sorted(B._action_candidates(rows, STATION_STAMP, keyed, keys),
                        key=lambda c: ACTION_RULE_IDS.index(c[1]))
        assert list(plan.ordered) == legacy
        assert list(plan.chosen) == legacy[:MAX_ACTIONS]
        carried = [(i.target, i.rule.rule_id, i.text) for i in d.actions.items]
        assert carried == [(k, c, t) for k, c, t in plan.chosen]
        assert plan.total_eligible - plan.omitted_count == len(d.actions.items)
        assert plan.unkeyed_held_count == d.holdings.unkeyed_count
    return built, unmatched_seen, without_seen


@pytest.mark.parametrize("seed", [20261110, 7, 99991])
def test_plan_parity_with_build_decision_digest_on_seeded_random_inputs(seed):
    built, unmatched_seen, without_seen = _parity_run(seed, 500)
    assert built > 100                                      # 夠多案例真的走到「建出 Digest」
    assert unmatched_seen > 50 and without_seen > 50        # 隨機輸入確實涵蓋 unmatched／無站內列情形


def test_plan_unknown_is_none_not_zero_and_validates_types():
    p = plan_action_selection()
    assert (p.evaluated, p.ordered, p.chosen, p.excluded_invalid_rows, p.unkeyed_held_count) == (False, (), (), None, None)
    assert p.total_eligible is None and p.omitted_count is None
    p2 = plan_action_selection(holdings_rows=holdings_for("A"), holding_keys=keys_for("A"))   # 沒站內列
    assert p2.evaluated is False and p2.unkeyed_held_count == 0 and p2.excluded_invalid_rows is None
    with pytest.raises(TypeError):
        plan_action_selection(station_rows={"a": 1})                        # type: ignore[arg-type]
    with pytest.raises(TypeError):
        plan_action_selection(station_stamp="x")                            # type: ignore[arg-type]


def test_builder_public_surface_is_additive_only():
    assert {"SourceStamp", "build_decision_digest", "ActionSelectionPlan", "plan_action_selection"} == set(B.__all__)
    params = set(inspect.signature(build_decision_digest).parameters)
    assert params == {"generated_at", "macro_state", "macro_stamp", "allocation", "station_rows", "station_stamp",
                      "holdings_rows", "holding_keys"}


# ════════════════════════════════════════════════════════════════════════
# 純函式／無副作用／不讀 session／AST 守衛
# ════════════════════════════════════════════════════════════════════════
def _imports(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.level == 0:
            mods.add(n.module or "")
    return mods


def test_assembly_imports_whitelist():
    mods = _imports(ASSEMBLY)
    assert {m.split(".")[0] for m in mods} <= {"__future__", "dataclasses", "datetime", "typing", "shared", "src"}
    assert {m for m in mods if m.startswith("src")} == {"src.services.decision_digest_builder"}
    for banned in ("streamlit", "requests", "yfinance", "FinMind", "src.ui", "src.ui2", "src.ui_v2", "src.data",
                   "src.compute", "app", "app_ui2", "os", "sys", "pathlib", "socket", "subprocess", "time", "random",
                   "pandas", "numpy", "json", "logging"):
        assert not any(m == banned or m.startswith(banned + ".") for m in mods), banned


def test_assembly_has_no_clock_session_or_io_calls():
    tree = ast.parse(ASSEMBLY.read_text(encoding="utf-8"))
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not ({"now", "utcnow", "today", "fromtimestamp", "session_state", "time", "sleep"} & attrs)
    assert not ({"open", "print", "input", "exec", "eval", "__import__", "st", "session_state"} & names)


def test_not_imported_by_app_or_ia_nav():
    for rel in ("app.py", "shared/ia_nav.py"):
        assert not any("decision_digest" in m for m in _imports(REPO / rel)), rel


def test_no_io_network_subprocess_or_session_access_at_runtime(monkeypatch, tmp_path):
    real_open = builtins.open

    def guarded_open(file, mode="r", *a, **k):
        if any(ch in str(mode) for ch in "wax+"):
            raise AssertionError(f"assemble_digest 不得寫檔：open({file!r}, {mode!r})")
        return real_open(file, mode, *a, **k)

    def boom(*a, **k):
        raise AssertionError("assemble_digest 不得碰網路／subprocess")

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    try:
        import streamlit as st

        class NoSession:
            def __getattr__(self, name):
                raise AssertionError("assemble_digest 不得讀 st.session_state")

            def __getitem__(self, k):
                raise AssertionError("assemble_digest 不得讀 st.session_state")

            def get(self, *a, **k):
                raise AssertionError("assemble_digest 不得讀 st.session_state")
        monkeypatch.setattr(st, "session_state", NoSession(), raising=False)
    except ImportError:
        pass
    before = sorted(p.name for p in tmp_path.iterdir())
    a = assemble_digest(**full_kwargs(7))
    assert a.coverage.actions_total_eligible == 7
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_inputs_are_not_mutated():
    kw = full_kwargs(5)
    rows_before = json.dumps(kw["station_rows"], ensure_ascii=False, sort_keys=True)
    hold_before = json.dumps(kw["holdings_rows"], ensure_ascii=False, sort_keys=True)
    ms_before = {k: v for k, v in kw["macro_state"].items()}
    assemble_digest(**kw)
    assert json.dumps(kw["station_rows"], ensure_ascii=False, sort_keys=True) == rows_before
    assert json.dumps(kw["holdings_rows"], ensure_ascii=False, sort_keys=True) == hold_before
    assert kw["macro_state"] == ms_before


def test_digest_is_valid_under_frozen_contract_for_every_scenario():
    """Digest v1 的所有既有檢查（AB-0 ＋ AB-1 allowlist）對每一種組裝結果都成立 —— 側車沒有污染 Digest。"""
    scenarios = [full_kwargs(n) for n in (0, 1, 3, 4, 7)] + [
        full_kwargs(3, macro_evidence=EvidenceInput(MACRO_STAMP, F.STALE)),
        full_kwargs(3, station_evidence=EvidenceInput(STATION_STAMP, F.UNDETERMINED, O.NO_NEW_DATA)),
        full_kwargs(3, macro_state=None, allocation=None, holdings_rows=None)]
    for kw in scenarios:
        a = assemble_digest(**kw)
        assert validate(a.digest) == () and validate_strict(a.digest) == ()
        assert a.digest.ai_participation.value == "rule_only"


# ════════════════════════════════════════════════════════════════════════
# 突變測試（teeth）：拔掉關鍵邏輯 → 對應檢查必須轉紅
# ════════════════════════════════════════════════════════════════════════
def _check_stale_is_withheld():
    ev = EvidenceInput(MACRO_STAMP, F.STALE, O.NO_NEW_DATA)
    a = assemble_digest(**full_kwargs(2, macro_evidence=ev))
    assert seg(a, SEGMENT_MARKET).used is False
    assert seg(a, SEGMENT_MARKET).withheld_reason == WITHHELD_STALE
    assert not any(f.status is DataStatus.OK for f in a.digest.market.facts)
    assert a.digest.risk_cap.cap_valid is False


def test_stale_is_withheld_baseline():
    _check_stale_is_withheld()


def test_teeth_removing_stale_rule_turns_the_check_red(monkeypatch):
    real = A._classify

    def no_stale_rule(evidence, generated_at):
        if evidence is not None and evidence.freshness is F.STALE:
            return None                                            # 突變：把 stale 當成可用
        return real(evidence, generated_at)
    monkeypatch.setattr(A, "_classify", no_stale_rule)
    with pytest.raises(AssertionError):
        _check_stale_is_withheld()


def _check_pit_violation_withheld():
    a = assemble_digest(generated_at=NOW, macro_state=macro(), allocation=alloc(),
                        macro_evidence=fresh(_pit_stamp(date(2026, 10, 28))))
    assert seg(a, SEGMENT_MARKET).withheld_reason == WITHHELD_PIT_VIOLATION


def test_teeth_removing_pit_check_turns_the_check_red(monkeypatch):
    _check_pit_violation_withheld()
    monkeypatch.setattr(A, "_pit_ok", lambda stamp, generated_at: True)    # 突變：不檢查 PIT
    with pytest.raises((AssertionError, ValueError)):                       # 違規 stamp 進 builder → fail loud
        _check_pit_violation_withheld()


def test_teeth_removing_omitted_calculation_turns_the_check_red(monkeypatch):
    _check_counts_exact(7)
    monkeypatch.setattr(B.ActionSelectionPlan, "omitted_count", property(lambda self: 0))   # 突變：永遠回報 0 個被省略
    with pytest.raises((AssertionError, ValueError)):
        _check_counts_exact(7)


def test_teeth_dropping_exclusion_count_turns_the_check_red(monkeypatch):
    assert _check_excluded_counts().coverage.excluded_invalid_rows == 4
    real = B._scan_action_rows
    monkeypatch.setattr(B, "_scan_action_rows", lambda *a, **k: (real(*a, **k)[0], 0, real(*a, **k)[2]))      # 突變：排除數歸零
    assert _check_excluded_counts().coverage.excluded_invalid_rows != 4


def test_teeth_unknown_counts_collapsing_to_zero_is_caught(monkeypatch):
    """突變：把『未知』偽裝成 0 → 側車 validator 必須擋下（actions 段未採用卻宣稱計數已知）或 is_complete 不得為 True。"""
    base = assemble_digest(generated_at=NOW)
    faked = dataclasses.replace(base.coverage, actions_total_eligible=0, actions_omitted_count=0,
                                excluded_invalid_rows=0, unkeyed_held_count=0, station_rows_unmatched=0,
                                holdings_without_station_row=0)
    with pytest.raises(ValueError):                                         # 與 digest 的未知狀態不一致 → 拒收
        AssembledDigest(digest=base.digest, coverage=faked)
    assert faked.is_complete is False                                       # 且即使單獨看，段落未採用 → 不完整


# ════════════════════════════════════════════════════════════════════════
# Issue #1127 QA 回修 M1：is_complete 的空洞（unmatched／holdings_without_station_row／digest_*_available）
# ════════════════════════════════════════════════════════════════════════
def _good_complete():
    a = assemble_digest(**full_kwargs(2))
    assert a.coverage.is_complete is True
    return a


def _custom(station, holdings, keys, **over):
    return assemble_digest(**full_kwargs(0, station_rows=station, holdings_rows=holdings, holding_keys=keys, **over))


# ── (a) 行動列對不上持股鍵：不得被靜默丟棄 ───────────────────────────────
def test_unmatched_ticker_case_mismatch_is_counted_and_blocks_completeness():
    a = _custom([row("t0", "cut")], holdings_for("T0"), keys_for("T0"))
    c = a.coverage
    assert c.station_rows_unmatched == 1 and a.digest.actions.items == ()
    assert c.actions_total_eligible == 0 and c.is_complete is False


def test_unmatched_ticker_not_in_holdings_rows():
    a = _custom([row("T0", "cut"), row("ZZ", "add")], holdings_for("T0"), keys_for("T0", "ZZ"))
    assert a.coverage.station_rows_unmatched == 1               # ZZ 有行動碼但不是持股
    assert [i.target.symbol for i in a.digest.actions.items] == ["T0"]
    assert a.coverage.is_complete is False


def test_unmatched_held_holding_without_holding_key():
    a = _custom([row("T0", "cut"), row("T1", "add")], holdings_for("T0", "T1"), keys_for("T0"))
    assert a.coverage.station_rows_unmatched == 1 and a.coverage.unkeyed_held_count == 1
    assert a.coverage.is_complete is False


def test_unmatched_not_counted_for_nonheld_invalid_nonaction_or_error_rows():
    rows = [row("A", "cut"),
            row("B", "cut", held=False),                                  # 非持有
            row("C", "cut", **{KEY_INVALID_LIGHTS: ["x"]}),               # 資料異常 → 屬於 excluded，不是 unmatched
            row("D", "premium"),                                          # 非行動碼
            row("E", "cut", _detail={"error": "boom"})]                   # 資料異常
    a = _custom(rows, holdings_for("A"), keys_for("A"))
    assert a.coverage.station_rows_unmatched == 0
    assert a.coverage.excluded_invalid_rows == 2


def test_unmatched_is_none_when_not_evaluated_not_zero():
    for kw in (dict(station_evidence=None), dict(station_rows=None), dict(holdings_rows=None)):
        assert assemble_digest(**full_kwargs(2, **kw)).coverage.station_rows_unmatched is None


def _check_unmatched_counted():
    a = _custom([row("t0", "cut")], holdings_for("T0"), keys_for("T0"))
    assert a.coverage.station_rows_unmatched == 1
    assert a.coverage.is_complete is False


def test_teeth_dropping_unmatched_count_turns_the_check_red(monkeypatch):
    _check_unmatched_counted()
    real = B._scan_action_rows
    monkeypatch.setattr(B, "_scan_action_rows", lambda *a, **k: (*real(*a, **k)[:2], 0))
    with pytest.raises(AssertionError):
        _check_unmatched_counted()


# ── (b) 持股沒有站內列 ─────────────────────────────────────────────────
def test_holdings_without_station_row_three_holdings_one_covered():
    a = _custom([row("A", "cut")], holdings_for("A", "B", "C"), keys_for("A", "B", "C"))
    assert a.coverage.holdings_without_station_row == 2
    assert a.coverage.is_complete is False


def test_holdings_without_station_row_ignores_nonheld_holdings_and_nonheld_station_rows():
    a = _custom([row("A", "cut"), row("B", "cut", held=False)],
                holdings_for("A") + holdings_for("B", "C", held=False) + holdings_for("D"),
                keys_for("A", "B", "C", "D"))
    assert a.coverage.holdings_without_station_row == 1          # 只有 D（B 的站內列 held=False 不算涵蓋；非持有不計）


def test_holdings_without_station_row_nonaction_and_invalid_rows_still_cover():
    rows = [row("A", "cut"), row("B", "premium"), row("C", "cut", **{KEY_INVALID_INPUTS: ["x"]})]
    a = _custom(rows, holdings_for("A", "B", "C"), keys_for("A", "B", "C"))
    assert a.coverage.holdings_without_station_row == 0
    assert a.coverage.excluded_invalid_rows == 1 and a.coverage.is_complete is False   # C 被排除仍不完整


def test_holdings_without_station_row_blank_ticker_counts_and_exact_match_only():
    a = _custom([row("A ", "cut")], [{"ticker": "A", "held": True}, {"ticker": "  ", "held": True}], keys_for("A"))
    assert a.coverage.holdings_without_station_row == 2            # "A " ≠ "A"（精確比對）；空白 ticker 無從比對


def test_holdings_without_station_row_is_none_when_not_evaluated():
    for kw in (dict(station_evidence=EvidenceInput(STATION_STAMP, F.STALE)), dict(station_rows=None),
               dict(holdings_rows=None)):
        assert assemble_digest(**full_kwargs(2, **kw)).coverage.holdings_without_station_row is None
    assert plan_action_selection().holdings_without_station_row is None


def test_all_holdings_covered_with_actions_is_complete():
    assert _good_complete().coverage.holdings_without_station_row == 0


def _check_without_station_counted():
    a = _custom([row("A", "cut")], holdings_for("A", "B"), keys_for("A", "B"))
    assert a.coverage.holdings_without_station_row == 1
    assert a.coverage.is_complete is False


def test_teeth_dropping_holdings_without_station_row_turns_the_check_red(monkeypatch):
    _check_without_station_counted()
    monkeypatch.setattr(B, "_count_holdings_without_station_row", lambda *a, **k: 0)
    with pytest.raises(AssertionError):
        _check_without_station_counted()


# ── (c) v1 無法區分「沒事做」與「判不出來」 ───────────────────────────────
def test_digest_available_flags_true_when_actions_present():
    c = _good_complete().coverage
    assert (c.digest_holdings_available, c.digest_actions_available) == (True, True)


def test_digest_available_flags_false_when_station_withheld():
    c = assemble_digest(**full_kwargs(3, station_evidence=EvidenceInput(STATION_STAMP, F.STALE))).coverage
    assert (c.digest_holdings_available, c.digest_actions_available) == (False, False)


def test_digest_holdings_partial_when_unkeyed_makes_holdings_flag_false_but_actions_true():
    a = _custom([row("A", "cut")], holdings_for("A", "B"), keys_for("A"))
    assert a.digest.holdings.availability is Availability.PARTIAL
    assert (a.coverage.digest_holdings_available, a.coverage.digest_actions_available) == (False, True)
    assert a.coverage.is_complete is False


def test_station_rows_empty_with_fresh_evidence_is_incomplete_per_v1_limitation():
    a = assemble_digest(**full_kwargs(0, station_rows=[], holdings_rows=[]))
    assert a.coverage.is_complete is False and all(s.used for s in a.coverage.segments)


# ════════════════════════════════════════════════════════════════════════
# Issue #1127 QA 回修 M2：envelope 交叉驗證（每個檢查各有「只有它能擋」的測試；以 match 鎖定訊息）
# ════════════════════════════════════════════════════════════════════════
def _swap_seg(c, name, **kw):
    return dataclasses.replace(c, segments=tuple(dataclasses.replace(s, **kw) if s.segment == name else s
                                                 for s in c.segments))


def _forge(a, match, **changes):
    with pytest.raises(ValueError, match=match):
        AssembledDigest(digest=a.digest, coverage=dataclasses.replace(a.coverage, **changes))


def test_envelope_rejects_risk_cap_used_when_facts_not_all_ok():
    a = assemble_digest(**full_kwargs(2, allocation=None))               # cap OK，lo／hi MISSING → 未採用(partial)
    prov = A._oldest(A._segment_facts(a.digest, SEGMENT_RISK_CAP))
    forged = _swap_seg(a.coverage, SEGMENT_RISK_CAP, used=True, source=prov[0], as_of=prov[1], withheld_reason=None)
    with pytest.raises(ValueError, match="risk_cap 段 used"):            # provenance 對得上，只有 used 檢查能擋
        AssembledDigest(digest=a.digest, coverage=forged)


def test_envelope_rejects_market_used_when_facts_not_all_ok():
    a = assemble_digest(**full_kwargs(2, macro_state=macro(health=float("nan"))))
    prov = A._oldest(A._segment_facts(a.digest, SEGMENT_MARKET))
    forged = _swap_seg(a.coverage, SEGMENT_MARKET, used=True, source=prov[0], as_of=prov[1], withheld_reason=None)
    with pytest.raises(ValueError, match="market 段 used"):
        AssembledDigest(digest=a.digest, coverage=forged)


def test_envelope_rejects_market_unused_when_facts_all_ok():
    a = _good_complete()
    with pytest.raises(ValueError, match="market 段 used"):
        AssembledDigest(digest=a.digest, coverage=_swap_seg(a.coverage, SEGMENT_MARKET, used=False,
                                                            withheld_reason="stale"))


def test_envelope_rejects_holdings_unused_but_digest_carries_facts():
    a = _good_complete()
    with pytest.raises(ValueError, match="holdings 段 used=False 但 digest.holdings 帶有行動事實"):
        AssembledDigest(digest=a.digest, coverage=_swap_seg(a.coverage, SEGMENT_HOLDINGS, used=False,
                                                            withheld_reason="stale"))


def test_envelope_rejects_actions_unused_but_digest_carries_actions():
    a = _good_complete()
    forged = _swap_seg(a.coverage, SEGMENT_ACTIONS, used=False, withheld_reason="stale")
    forged = dataclasses.replace(forged, actions_total_eligible=None, actions_omitted_count=None,
                                 excluded_invalid_rows=None, station_rows_unmatched=None,
                                 holdings_without_station_row=None)            # coverage 本身合法
    assert validate_coverage(forged) == ()
    with pytest.raises(ValueError, match="actions 段 used=False 但 digest.actions 帶有行動"):
        AssembledDigest(digest=a.digest, coverage=forged)


def test_envelope_rejects_unkeyed_none_when_digest_holdings_available():
    a = _good_complete()
    forged = _swap_seg(a.coverage, SEGMENT_HOLDINGS, used=False, withheld_reason="not_loaded")
    forged = dataclasses.replace(forged, unkeyed_held_count=None)
    assert validate_coverage(forged) == ()
    with pytest.raises(ValueError, match="unkeyed_held_count 為 None"):
        AssembledDigest(digest=a.digest, coverage=forged)


def test_envelope_rejects_unkeyed_count_that_differs_from_digest():
    _forge(_good_complete(), r"unkeyed_held_count\(1\)", unkeyed_held_count=1)


def test_envelope_rejects_shown_not_equal_min_total_max():
    a = _good_complete()                                                   # shown=2
    _forge(a, "必須等於 min", actions_total_eligible=5, actions_omitted_count=3)   # coverage 合法，但 digest 只有 2 個


def test_envelope_rejects_actions_shown_mismatch():
    a = assemble_digest(**full_kwargs(5))                                  # shown=3
    _forge(a, r"actions_shown\(2\)", actions_shown=2, actions_omitted_count=3)


def test_envelope_rejects_digest_availability_flag_mismatch():
    a = _good_complete()
    _forge(a, "digest_holdings_available", digest_holdings_available=False)
    _forge(a, "digest_actions_available", digest_actions_available=False)
    z = assemble_digest(**full_kwargs(0, station_rows=[], holdings_rows=[]))
    _forge(z, "digest_actions_available", digest_actions_available=True)


def test_envelope_rejects_segment_provenance_that_differs_from_digest_facts():
    a = _good_complete()
    for name in (SEGMENT_MARKET, SEGMENT_RISK_CAP, SEGMENT_HOLDINGS, SEGMENT_ACTIONS):
        for kw in (dict(as_of=D - timedelta(days=1)), dict(source="forged-source")):
            with pytest.raises(ValueError, match=f"{name} 段 source／as_of"):
                AssembledDigest(digest=a.digest, coverage=_swap_seg(a.coverage, name, **kw))


def test_envelope_unverifiable_counts_are_a_documented_limitation_not_a_guard():
    """據實：total／excluded／unmatched／holdings_without_station_row 在 digest 內看不到 → envelope 無法驗證。
    本測試把這個限制釘住（自洽的偽造值會通過；它們只靠 builder parity 與測試保證）。見模組 docstring「已知限制」。"""
    a = _good_complete()
    forged = dataclasses.replace(a.coverage, excluded_invalid_rows=0, station_rows_unmatched=0,
                                 holdings_without_station_row=0)           # 與真值相同，僅示範：這些欄位不被 digest 驗證
    assert AssembledDigest(digest=a.digest, coverage=forged).coverage == a.coverage
    assert "不防惡意偽造" in (A.AssembledDigest.__doc__ or "")
    assert "不可能存在" not in (A.AssembledDigest.__doc__ or "")


# ── 最舊 provenance（fresh macro＋舊 snapshot_ts 不得讓 coverage 看起來比 cap 事實新）──────────
def test_risk_cap_segment_as_of_is_oldest_ok_fact_not_the_fresh_macro_stamp():
    ms = macro(risk_cap_disclosure=disclosure("2026-10-20 18:30:00"))
    a = assemble_digest(**full_kwargs(2, macro_state=ms, allocation=alloc(ms)))
    rc, mk = seg(a, SEGMENT_RISK_CAP), seg(a, SEGMENT_MARKET)
    assert rc.used is True and (rc.source, rc.as_of) == ("risk_cap_snapshot", date(2026, 10, 20))
    assert (mk.source, mk.as_of) == ("macro_state.json", D)               # market 仍是 macro 戳日期
    assert rc.as_of == a.digest.risk_cap.cap_pct.provenance.as_of


def test_envelope_rejects_risk_cap_segment_claiming_the_newer_macro_stamp_date():
    ms = macro(risk_cap_disclosure=disclosure("2026-10-20 18:30:00"))
    a = assemble_digest(**full_kwargs(2, macro_state=ms, allocation=alloc(ms)))
    with pytest.raises(ValueError, match="risk_cap 段 source／as_of"):
        AssembledDigest(digest=a.digest, coverage=_swap_seg(a.coverage, SEGMENT_RISK_CAP, source="macro_state.json", as_of=D))


# ── minor：全無事實時不用 partial ─────────────────────────────────────
def test_all_facts_missing_is_not_loaded_not_partial():
    ms = macro(regime="unknown", light="⬜", health=None, exposure_limit_pct=None)
    a = assemble_digest(**full_kwargs(2, macro_state=ms, allocation=None))
    assert not any(f.status is DataStatus.OK for f in a.digest.market.facts)
    assert seg(a, SEGMENT_MARKET).withheld_reason == WITHHELD_NOT_LOADED
    assert seg(a, SEGMENT_RISK_CAP).withheld_reason == WITHHELD_NOT_LOADED


def test_partial_only_when_some_but_not_all_facts_ok():
    a = assemble_digest(**full_kwargs(2, macro_state=macro(health=None)))   # regime／light OK，health 缺
    assert seg(a, SEGMENT_MARKET).withheld_reason == WITHHELD_PARTIAL


def test_station_rows_row_level_type_error_is_not_loud_when_evidence_withheld_documented_limit():
    """已知限制（模組 docstring）：證據被拒用時，station_rows 列層級型別錯誤不會 fail loud；證據可用時會。"""
    bad_rows = [row("A", "cut", held="yes")]
    a = assemble_digest(**full_kwargs(0, station_rows=bad_rows, holdings_rows=holdings_for("A"),
                                      holding_keys=keys_for("A"),
                                      station_evidence=EvidenceInput(STATION_STAMP, F.STALE)))
    assert a.coverage.is_complete is False
    with pytest.raises(TypeError):
        assemble_digest(**full_kwargs(0, station_rows=bad_rows, holdings_rows=holdings_for("A"),
                                      holding_keys=keys_for("A")))
    assert "已知限制" in (A.__doc__ or "")
