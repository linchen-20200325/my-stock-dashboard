"""Issue #1138 A 線（tests-only）— Decision Digest 證據採用資格「全組合矩陣」守衛（fast lane）。

═══ 守什麼 ═══════════════════════════════════════════════════════════
`src/services/decision_digest_assembly.assemble_digest` 的證據規則（DEC-159 第 7 點「證據 fail-closed」；
DEC-160 裁示 2「stale／來源失敗／PIT 不合格的值不得當 fresh／eligible 進入決策、動作、Risk Cap」）：
一段證據只有在「有 stamp ∧ freshness 為 FRESH ∧ upstream 不是 FETCH_FAILED／UNDETERMINED ∧ PIT 通過」
時才被採用；否則該段 stamp **與**上游輸出都不交給 builder。

既有 `tests/test_decision_digest_assembly.py` 以**挑選過的樣本**（`_WITHHELD_CASES` 9 組＋若干 PIT 例）守這條規則；
本檔補上**笛卡兒積全組合**，使任何「某一格被放行」的回歸都不能從樣本間隙溜過：

    stamp {無, 正常, as_of 晚於 generated_at（台北日）, fetched_at 晚於 generated_at}
  × FreshnessStatus（全部成員＋None）
  × FetchOutcome（全部成員＋None）
  × {macro 側, station 側}

列舉一律**由 enum 推導**（`list(FreshnessStatus)`／`list(FetchOutcome)`），不寫死成員數；
日後 enum 新增成員會自動進矩陣（新成員依現行規則必為「不採用」，除非刻意改規則）。

═══ 斷言（每一格）═══════════════════════════════════════════════════════
- 採用 ⇔ 上述四條件同時成立（oracle 由規則文字直寫，不呼叫被測模組的私有函式）；
- 不採用時：`withheld_reason ∈ WITHHELD_REASONS`、該側段落無任何 OK 事實、
  macro 側 `risk_cap.cap_valid is False`、station 側 `actions.items == ()` 且不可評估的計數為 None（不是 0）、
  `is_complete is False`；
- 另一側不受影響（仍為採用、內容照常）；
- Digest／coverage 皆通過既有 validator（不新增門檻、不改 schema）。

⚠️ **刻意不 pin 拒用原因的優先順序**：多個條件同時不成立時回哪個原因屬已知開放限制 (f)（Issue #1139），
本檔只斷言原因屬於合法集合。⛔ 本檔不改任何 src／shared，Digest v1 schema 凍結。
"""
from __future__ import annotations

import itertools
from datetime import date, datetime, timedelta, timezone

import pytest

from shared.allocation_decision import build_allocation_decision
from shared.decision_digest import MAX_ACTIONS, Availability, DataStatus, HoldingKey
from shared.decision_digest_coverage import (
    SEGMENT_ACTIONS, SEGMENT_HOLDINGS, SEGMENT_MARKET, SEGMENT_RISK_CAP, WITHHELD_REASONS, validate_coverage,
)
from shared.decision_digest_rules import validate_strict
from shared.fetch_outcome import FetchOutcome
from shared.freshness_policy import FreshnessStatus
from shared.risk_cap_policy import RiskCapDisclosure
from src.services.decision_digest_assembly import EvidenceInput, assemble_digest
from src.services.decision_digest_builder import SourceStamp

NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)          # 台北 2026-10-27 17:00
D = date(2026, 10, 26)
MACRO_SRC = "macro_state.json"
STATION_SRC = "dividend_station_service"

#: stamp 軸：名稱 → (source → SourceStamp | None)。PIT 兩種違反各取一個代表（規則文字見 assembly 模組 docstring 第 4 條）。
STAMP_KINDS = {
    "none": lambda src: None,
    "ok": lambda src: SourceStamp(src, D),
    "pit_as_of_after_generated": lambda src: SourceStamp(src, NOW.date() + timedelta(days=1)),
    "pit_fetched_after_generated": lambda src: SourceStamp(src, D, NOW + timedelta(hours=1)),
}
#: 只有這個 stamp 種類同時「有 stamp」且「PIT 通過」。
_PIT_PASSING_STAMP = "ok"
FRESHNESS_AXIS = [*FreshnessStatus, None]
UPSTREAM_AXIS = [*FetchOutcome, None]
_BLOCKING_UPSTREAM = frozenset({FetchOutcome.FETCH_FAILED, FetchOutcome.UNDETERMINED})

CASES = [
    pytest.param(s, f, u, id=f"{s}-{getattr(f, 'name', 'None')}-{getattr(u, 'name', 'None')}")
    for s, f, u in itertools.product(STAMP_KINDS, FRESHNESS_AXIS, UPSTREAM_AXIS)
]

#: 站內 5 列候選 ⇒ 採用時 shown＝MAX_ACTIONS、omitted＝5−MAX_ACTIONS（用來確認「另一側不受影響」是真的有內容）。
_STATION_CODES = ("cut", "add", "pause_add", "take_profit_partial", "add")


def _expected_used(stamp_kind: str, freshness, upstream) -> bool:
    """oracle：規則四條件的直寫（不呼叫被測模組的私有函式）。"""
    return (stamp_kind == _PIT_PASSING_STAMP
            and freshness is FreshnessStatus.FRESH
            and upstream not in _BLOCKING_UPSTREAM)


def _macro_state() -> dict:
    return {"is_loaded": True, "regime": "bull", "light": "🟢", "health": 72.5, "exposure_limit_pct": 60,
            "defense": False,
            "risk_cap_disclosure": RiskCapDisclosure(snapshot_ts="2026-10-26 18:30:00", not_evaluated=(),
                                                     disabled=(), sahm_status=None)}


def _kwargs(macro_evidence: EvidenceInput, station_evidence: EvidenceInput) -> dict:
    rows = [{"代號": f"T{i}", "held": True, "_action": c, "建議動作": f"txt-{c}-{i}", "_detail": {}}
            for i, c in enumerate(_STATION_CODES)]
    tickers = [r["代號"] for r in rows]
    ms = _macro_state()
    return dict(generated_at=NOW, macro_state=ms, macro_evidence=macro_evidence,
                allocation=build_allocation_decision(ms), station_rows=rows, station_evidence=station_evidence,
                holdings_rows=[{"ticker": t, "held": True} for t in tickers],
                holding_keys={t: HoldingKey("pf-A", t) for t in tickers})


def _good(src: str) -> EvidenceInput:
    return EvidenceInput(SourceStamp(src, D), FreshnessStatus.FRESH, None)


def _ev(stamp_kind: str, freshness, upstream, src: str) -> EvidenceInput:
    return EvidenceInput(stamp=STAMP_KINDS[stamp_kind](src), freshness=freshness, upstream_state=upstream)


def _segments(a) -> dict:
    return {s.segment: s for s in a.coverage.segments}


def _risk_cap_facts(d) -> list:
    return [d.risk_cap.cap_pct, d.risk_cap.exposure_lo_pct, d.risk_cap.exposure_hi_pct]


def _assert_station_side_intact(a) -> None:
    seg = _segments(a)
    assert seg[SEGMENT_HOLDINGS].used is True and seg[SEGMENT_ACTIONS].used is True
    assert len(a.digest.actions.items) == MAX_ACTIONS
    assert a.coverage.actions_total_eligible == len(_STATION_CODES)
    assert a.coverage.actions_omitted_count == len(_STATION_CODES) - MAX_ACTIONS


def _assert_macro_side_intact(a) -> None:
    seg = _segments(a)
    assert seg[SEGMENT_MARKET].used is True and seg[SEGMENT_RISK_CAP].used is True
    assert a.digest.risk_cap.cap_valid is True
    assert all(f.status is DataStatus.OK for f in a.digest.market.facts)


# ════════════════════════════════════════════════════════════════════════
# 矩陣本身的健全性（防止日後有人把軸縮小、讓矩陣變成裝飾品）
# ════════════════════════════════════════════════════════════════════════
def test_matrix_axes_are_derived_from_enums_and_cover_every_member():
    assert set(FRESHNESS_AXIS) == set(FreshnessStatus) | {None}
    assert set(UPSTREAM_AXIS) == set(FetchOutcome) | {None}
    assert len(CASES) == len(STAMP_KINDS) * (len(FreshnessStatus) + 1) * (len(FetchOutcome) + 1)
    used = [c for c in CASES if _expected_used(*c.values)]
    # 採用格 ＝ 1（PIT 通過的 stamp）× 1（FRESH）×（upstream 中非阻擋者數）
    assert len(used) == len([u for u in UPSTREAM_AXIS if u not in _BLOCKING_UPSTREAM])
    assert 0 < len(used) < len(CASES)


def test_baseline_both_sides_used():
    a = assemble_digest(**_kwargs(_good(MACRO_SRC), _good(STATION_SRC)))
    _assert_macro_side_intact(a)
    _assert_station_side_intact(a)


# ════════════════════════════════════════════════════════════════════════
# macro 側（管 market＋risk_cap）
# ════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("stamp_kind,freshness,upstream", CASES)
def test_macro_evidence_matrix(stamp_kind, freshness, upstream):
    a = assemble_digest(**_kwargs(_ev(stamp_kind, freshness, upstream, MACRO_SRC), _good(STATION_SRC)))
    assert validate_strict(a.digest) == () and validate_coverage(a.coverage) == ()
    seg = _segments(a)
    want = _expected_used(stamp_kind, freshness, upstream)
    for name in (SEGMENT_MARKET, SEGMENT_RISK_CAP):
        assert seg[name].used is want, name
        if want:
            assert seg[name].withheld_reason is None
        else:
            assert seg[name].withheld_reason in WITHHELD_REASONS, seg[name].withheld_reason
    if want:
        _assert_macro_side_intact(a)
    else:
        d = a.digest
        assert not any(f.status is DataStatus.OK for f in d.market.facts)
        assert not any(f.status is DataStatus.OK for f in _risk_cap_facts(d))
        assert d.risk_cap.cap_valid is False
        assert a.coverage.is_complete is False
    _assert_station_side_intact(a)                     # 另一側不受影響


# ════════════════════════════════════════════════════════════════════════
# station 側（管 holdings＋actions）
# ════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("stamp_kind,freshness,upstream", CASES)
def test_station_evidence_matrix(stamp_kind, freshness, upstream):
    a = assemble_digest(**_kwargs(_good(MACRO_SRC), _ev(stamp_kind, freshness, upstream, STATION_SRC)))
    assert validate_strict(a.digest) == () and validate_coverage(a.coverage) == ()
    seg = _segments(a)
    want = _expected_used(stamp_kind, freshness, upstream)
    for name in (SEGMENT_HOLDINGS, SEGMENT_ACTIONS):
        assert seg[name].used is want, name
        if want:
            assert seg[name].withheld_reason is None
        else:
            assert seg[name].withheld_reason in WITHHELD_REASONS, seg[name].withheld_reason
    if want:
        _assert_station_side_intact(a)
    else:
        d, c = a.digest, a.coverage
        assert d.actions.items == () and d.actions.availability is Availability.UNAVAILABLE
        assert not any(f.status is DataStatus.OK for e in d.holdings.entries for f in e.facts)
        # 不能評估 → None（不是 0）
        assert c.actions_total_eligible is None and c.actions_omitted_count is None
        assert c.excluded_invalid_rows is None
        assert c.actions_shown == 0
        assert c.is_complete is False
    _assert_macro_side_intact(a)                       # 另一側不受影響
