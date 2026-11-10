"""Issue #1127 P-4（S8）— `shared/decision_digest_coverage.py`（Digest 完整性「側車」契約）測試（fast lane）。

為什麼是側車：Decision Digest v1 凍結（不得改欄位、不得升 `SCHEMA_VERSION`、不得動 `MAX_ACTIONS`、
不得新增列舉成員／confidence 語意），但它在形成前就把行動截到 `MAX_ACTIONS`、並靜默排除資料異常列，
讀者看不出少了什麼。完整性揭露因此由**獨立版本**的 `DigestCoverage` 攜帶（`digest_coverage.v1`）。

本檔守的是側車契約本身：
- `is_complete` 是唯一的完整性判定，且 fail-closed（未知＝None≠0；不合法物件＝False）；
- 嚴格 int（bool／float 偽裝計數被拒）；
- `used=True` 必有 source＋as_of；`used=False` 必有受限的 withheld_reason；
- `actions_max` 取自 `shared.decision_digest.MAX_ACTIONS`，不得硬編碼；
- 不含 confidence／score／neutral／safe 語意，也不沿用或擴充 Digest 的列舉；
- 純 L0：只 import 標準函式庫＋`shared.decision_digest`。
組裝與證據規則見 `tests/test_decision_digest_assembly.py`。
"""
from __future__ import annotations

import ast
import dataclasses
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

import shared.decision_digest_coverage as C
from shared.decision_digest import MAX_ACTIONS
from shared.decision_digest_coverage import (
    COVERAGE_SCHEMA_VERSION, SEGMENTS, WITHHELD_REASONS, DigestCoverage, SegmentEvidence,
    assert_coverage_valid, validate_coverage,
)

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "shared" / "decision_digest_coverage.py"
D = date(2026, 10, 26)


def used_seg(name, source="svc", as_of=D):
    return SegmentEvidence(name, True, source, as_of, None)


def unused_seg(name, reason="stale", source=None, as_of=None):
    return SegmentEvidence(name, False, source, as_of, reason)


def complete_cov(**over):
    base = dict(actions_total_eligible=2, actions_shown=2, actions_omitted_count=0, actions_max=MAX_ACTIONS,
                excluded_invalid_rows=0, unkeyed_held_count=0,
                segments=tuple(used_seg(n) for n in SEGMENTS))
    base.update(over)
    return DigestCoverage(**base)


def codes(c):
    return {v.split(":", 1)[0] for v in validate_coverage(c)}


# ════════════════════════════════════════════════════════════════════════
# 基本形狀與常數
# ════════════════════════════════════════════════════════════════════════
def test_version_is_independent_of_digest_schema():
    from shared.decision_digest import SCHEMA_VERSION
    assert COVERAGE_SCHEMA_VERSION == "digest_coverage.v1"
    assert COVERAGE_SCHEMA_VERSION != SCHEMA_VERSION


def test_segments_fixed_four_in_order():
    assert SEGMENTS == ("market", "risk_cap", "holdings", "actions")


def test_complete_fixture_is_valid_and_complete():
    c = complete_cov()
    assert validate_coverage(c) == ()
    assert c.is_complete is True
    assert c.actions_max == MAX_ACTIONS


def test_actions_max_comes_from_digest_constant_not_hardcoded(monkeypatch):
    """actions_max 必須等於 `MAX_ACTIONS`；常數若變動，舊值立即被拒（證明 validator 不是寫死 3）。"""
    assert validate_coverage(complete_cov()) == ()
    monkeypatch.setattr(C, "MAX_ACTIONS", MAX_ACTIONS + 2)
    assert "actions_max_mismatch" in codes(complete_cov())
    assert complete_cov().is_complete is False


def test_actions_max_other_than_constant_rejected():
    assert "actions_max_mismatch" in codes(complete_cov(actions_max=MAX_ACTIONS + 1))
    assert "actions_max_mismatch" in codes(complete_cov(actions_max=MAX_ACTIONS - 1))


def test_frozen_immutable():
    c = complete_cov()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.actions_shown = 0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.segments[0].used = False  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════════
# is_complete：唯一的完整性判定（fail-closed）
# ════════════════════════════════════════════════════════════════════════
def test_omitted_nonzero_is_incomplete():
    c = complete_cov(actions_total_eligible=5, actions_shown=3, actions_omitted_count=2)
    assert validate_coverage(c) == () and c.is_complete is False


@pytest.mark.parametrize("field", ["excluded_invalid_rows", "unkeyed_held_count"])
def test_nonzero_exclusion_or_unkeyed_is_incomplete(field):
    c = complete_cov(**{field: 1})
    assert validate_coverage(c) == () and c.is_complete is False


@pytest.mark.parametrize("seg", SEGMENTS)
def test_any_unused_segment_is_incomplete(seg):
    segs = tuple(unused_seg(n) if n == seg else used_seg(n) for n in SEGMENTS)
    c = complete_cov(segments=segs)
    # actions／holdings 段未採用時，對應計數可以是 None；這裡刻意保持已知，專測 used 軸
    assert c.is_complete is False


@pytest.mark.parametrize("field", ["actions_total_eligible", "actions_omitted_count",
                                   "excluded_invalid_rows", "unkeyed_held_count"])
def test_unknown_count_is_none_not_zero_and_blocks_completeness(field):
    """未知計數用 None；None 與 0 不得混淆 → is_complete 為 False。"""
    over = {field: None}
    if field == "actions_total_eligible":
        over["actions_omitted_count"] = None
    if field == "actions_omitted_count":
        over["actions_total_eligible"] = None
    segs = tuple(unused_seg(n, "not_loaded") for n in SEGMENTS)
    c = complete_cov(segments=segs, **over)
    assert c.is_complete is False
    zero = complete_cov()
    assert zero.is_complete is True                      # 同樣情形下「真的 0」才是完整
    assert getattr(zero, field) == 0 or field == "actions_total_eligible"


def test_none_is_not_equal_to_zero_semantics():
    c = complete_cov(excluded_invalid_rows=None)
    assert c.excluded_invalid_rows is None and c.excluded_invalid_rows != 0
    assert c.is_complete is False


def test_invalid_object_is_never_complete_even_if_it_looks_complete():
    """bool 偽裝計數：False==0、True==1，但型別不合法 → is_complete 必為 False（fail-closed）。"""
    c = complete_cov(unkeyed_held_count=False)
    assert c.unkeyed_held_count == 0                      # 值相等…
    assert "unkeyed_held_count_type" in codes(c)
    assert c.is_complete is False                         # …但仍不完整


def test_total_unknown_segments_used_is_rejected():
    segs = tuple(used_seg(n) for n in SEGMENTS)
    c = complete_cov(actions_total_eligible=None, actions_omitted_count=None, segments=segs)
    assert "actions_used_with_unknown_counts" in codes(c)
    assert c.is_complete is False


def test_actions_unused_with_known_counts_rejected():
    """證據未採用 ⇒ 其上的計數不可信 ⇒ 必須是 None（不得把『未知』偽裝成 0）。"""
    segs = tuple(unused_seg(n) if n == "actions" else used_seg(n) for n in SEGMENTS)
    assert "actions_unused_with_known_counts" in codes(complete_cov(segments=segs))
    partial_unknown = complete_cov(segments=segs, actions_total_eligible=None, actions_omitted_count=None)
    assert "actions_unused_with_known_counts" in codes(partial_unknown)   # excluded 仍是 0 → 三者須「全部」為 None
    ok = complete_cov(segments=segs, actions_total_eligible=None, actions_omitted_count=None,
                      excluded_invalid_rows=None)
    assert validate_coverage(ok) == () and ok.is_complete is False


def test_holdings_used_with_unknown_unkeyed_rejected():
    c = complete_cov(unkeyed_held_count=None)
    assert "holdings_used_with_unknown_unkeyed" in codes(c)
    assert c.is_complete is False


# ════════════════════════════════════════════════════════════════════════
# 計數驗證（嚴格 int）
# ════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", [True, False, 2.0, 1.5, "2", float("nan"), -1])
@pytest.mark.parametrize("field", ["actions_total_eligible", "actions_shown", "actions_omitted_count",
                                   "excluded_invalid_rows", "unkeyed_held_count"])
def test_counts_reject_bool_float_str_negative(field, bad):
    v = validate_coverage(complete_cov(**{field: bad}))
    assert any(x.startswith(f"{field}_") for x in v), (field, bad, v)


def test_actions_shown_none_rejected():
    assert "actions_shown_type" in codes(complete_cov(actions_shown=None))


def test_actions_max_bool_rejected():
    assert "actions_max_type" in codes(complete_cov(actions_max=True))


def test_total_must_be_at_least_shown():
    assert "actions_omitted_count_negative" in codes(      # total<shown 時 omitted 只能是負數 → 被拒
        complete_cov(actions_total_eligible=1, actions_shown=2, actions_omitted_count=-1))
    assert "total_below_shown" in codes(
        complete_cov(actions_total_eligible=1, actions_shown=2, actions_omitted_count=0))


@pytest.mark.parametrize("omitted", [0, 1, 3])
def test_omitted_must_equal_total_minus_shown(omitted):
    c = complete_cov(actions_total_eligible=4, actions_shown=3, actions_omitted_count=omitted)
    assert ("omitted_mismatch" in codes(c)) is (omitted != 1)


def test_shown_cannot_exceed_max():
    c = complete_cov(actions_total_eligible=MAX_ACTIONS + 1, actions_shown=MAX_ACTIONS + 1,
                     actions_omitted_count=0)
    assert "shown_exceeds_max" in codes(c)


def test_total_and_omitted_unknown_together_only():
    assert "total_omitted_unknown_mismatch" in codes(
        complete_cov(actions_total_eligible=None, actions_omitted_count=0))
    assert "total_omitted_unknown_mismatch" in codes(
        complete_cov(actions_total_eligible=2, actions_omitted_count=None))


@pytest.mark.parametrize("total,shown", [(0, 0), (1, 1), (2, 2), (3, 3), (4, 3), (7, 3)])
def test_valid_total_shown_omitted_combinations(total, shown):
    c = complete_cov(actions_total_eligible=total, actions_shown=shown, actions_omitted_count=total - shown)
    assert validate_coverage(c) == ()
    assert c.is_complete is (total == shown)


# ════════════════════════════════════════════════════════════════════════
# 證據段驗證
# ════════════════════════════════════════════════════════════════════════
def test_used_true_requires_source_and_as_of():
    segs = (SegmentEvidence("market", True, None, D, None),) + tuple(used_seg(n) for n in SEGMENTS[1:])
    assert "used_without_source" in codes(complete_cov(segments=segs))
    segs = (SegmentEvidence("market", True, "svc", None, None),) + tuple(used_seg(n) for n in SEGMENTS[1:])
    assert "used_without_as_of" in codes(complete_cov(segments=segs))


def test_used_true_must_not_carry_reason():
    segs = (SegmentEvidence("market", True, "svc", D, "stale"),) + tuple(used_seg(n) for n in SEGMENTS[1:])
    assert "used_with_reason" in codes(complete_cov(segments=segs))


def test_used_false_requires_reason_from_closed_set():
    segs = (SegmentEvidence("market", False, None, None, None),) + tuple(used_seg(n) for n in SEGMENTS[1:])
    assert "unused_without_reason" in codes(complete_cov(segments=segs))
    segs = (SegmentEvidence("market", False, None, None, "safe"),) + tuple(used_seg(n) for n in SEGMENTS[1:])
    assert "withheld_reason_unknown" in codes(complete_cov(segments=segs))


@pytest.mark.parametrize("reason", sorted(WITHHELD_REASONS))
def test_every_declared_reason_is_accepted(reason):
    segs = (unused_seg("market", reason),) + tuple(used_seg(n) for n in SEGMENTS[1:])
    assert validate_coverage(complete_cov(segments=segs)) == ()


def test_unused_segment_may_carry_traceable_source_and_as_of():
    """stale 的證據仍可追溯它是哪個來源、哪一天的資料（不補、不頂替；沒有就是 None）。"""
    segs = (unused_seg("market", "stale", "FRED", date(2026, 10, 1)),) + tuple(used_seg(n) for n in SEGMENTS[1:])
    assert validate_coverage(complete_cov(segments=segs)) == ()


def test_used_must_be_real_bool():
    segs = (SegmentEvidence("market", 1, "svc", D, None),) + tuple(used_seg(n) for n in SEGMENTS[1:])  # type: ignore[arg-type]
    assert "used_type" in codes(complete_cov(segments=segs))


def test_as_of_must_be_plain_date_not_datetime():
    dt = datetime(2026, 10, 26, tzinfo=timezone.utc)
    segs = (SegmentEvidence("market", True, "svc", dt, None),) + tuple(used_seg(n) for n in SEGMENTS[1:])  # type: ignore[arg-type]
    assert "as_of_type" in codes(complete_cov(segments=segs))


def test_blank_source_rejected():
    segs = (SegmentEvidence("market", True, "  ", D, None),) + tuple(used_seg(n) for n in SEGMENTS[1:])
    assert "source_type" in codes(complete_cov(segments=segs))


def test_segments_must_be_exactly_four_unique_in_order():
    base = [used_seg(n) for n in SEGMENTS]
    assert "segments_set" in codes(complete_cov(segments=tuple(base[:3])))
    assert "segments_set" in codes(complete_cov(segments=tuple(base + [used_seg("market")])))
    assert "segments_set" in codes(complete_cov(segments=tuple(reversed(base))))
    assert "segments_set" in codes(complete_cov(segments=(base[0], base[0], base[2], base[3])))
    assert "segments_type" in codes(complete_cov(segments=list(base)))   # list ≠ tuple
    assert "segment_type" in codes(complete_cov(segments=("market", "risk_cap", "holdings", "actions")))


def test_unknown_segment_name_rejected():
    segs = (SegmentEvidence("industry", True, "svc", D, None),) + tuple(used_seg(n) for n in SEGMENTS[1:])
    assert "segment_name" in codes(complete_cov(segments=segs))


def test_schema_version_mismatch_rejected():
    assert "schema_version_mismatch" in codes(complete_cov(schema_version="digest_coverage.v2"))
    assert "schema_version_mismatch" in codes(complete_cov(schema_version=1))


# ════════════════════════════════════════════════════════════════════════
# validator／assert／to_dict 行為
# ════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("garbage", [None, 0, "x", [], {}, object(), SegmentEvidence("market", True, "s", D)])
def test_validate_never_raises_on_garbage(garbage):
    v = validate_coverage(garbage)
    assert isinstance(v, tuple) and v and all(isinstance(x, str) for x in v)


def test_validate_never_raises_on_broken_inner_fields():
    class Weird:
        def __eq__(self, o):
            raise RuntimeError("boom")
    c = complete_cov(actions_total_eligible=Weird(), actions_omitted_count=Weird())
    v = validate_coverage(c)
    assert v and c.is_complete is False


def test_assert_coverage_valid_raises_valueerror_with_all_violations():
    assert_coverage_valid(complete_cov())
    with pytest.raises(ValueError) as ei:
        assert_coverage_valid(complete_cov(actions_shown=True, unkeyed_held_count=2.0))
    assert "actions_shown" in str(ei.value) and "unkeyed_held_count" in str(ei.value)


def test_to_dict_is_deterministic_json_serializable_and_has_is_complete():
    c = complete_cov()
    a, b = c.to_dict(), complete_cov().to_dict()
    assert a == b
    assert json.dumps(a, ensure_ascii=False, sort_keys=False) == json.dumps(b, ensure_ascii=False, sort_keys=False)
    assert a["is_complete"] is True and a["schema_version"] == COVERAGE_SCHEMA_VERSION
    assert a["segments"][0] == {"segment": "market", "used": True, "source": "svc", "as_of": "2026-10-26",
                                "withheld_reason": None}
    assert list(a)[:2] == ["schema_version", "actions_total_eligible"]      # 欄位順序固定


def test_to_dict_serializes_unknown_as_null_not_zero():
    segs = tuple(unused_seg(n, "not_loaded") for n in SEGMENTS)
    c = complete_cov(actions_total_eligible=None, actions_omitted_count=None, excluded_invalid_rows=None,
                     unkeyed_held_count=None, actions_shown=0, segments=segs)
    d = c.to_dict()
    assert d["actions_total_eligible"] is None and d["actions_omitted_count"] is None
    assert d["excluded_invalid_rows"] is None and d["unkeyed_held_count"] is None
    assert d["is_complete"] is False


def test_to_dict_of_invalid_object_raises():
    with pytest.raises(ValueError):
        complete_cov(actions_shown=2.0).to_dict()


# ════════════════════════════════════════════════════════════════════════
# 結構守衛：L0、無 confidence／score／neutral／safe、不沿用 Digest 列舉
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


def test_module_is_pure_l0_imports():
    mods = _imports(MODULE)
    assert {m.split(".")[0] for m in mods} <= {"__future__", "dataclasses", "datetime", "typing", "shared"}
    assert {m for m in mods if m.startswith("shared")} <= {"shared.decision_digest"}
    for banned in ("streamlit", "requests", "src", "app", "pandas", "numpy"):
        assert not any(m == banned or m.startswith(banned + ".") for m in mods), banned


def test_only_max_actions_is_taken_from_digest():
    """不沿用、不擴充 Digest 的列舉：只 import `MAX_ACTIONS`。"""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                and n.module == "shared.decision_digest" for a in n.names}
    assert imported == {"MAX_ACTIONS"}


_BANNED_SEMANTICS = ("confidence", "score", "neutral", "safe", "safety", "trust", "reliab")


def test_no_confidence_score_neutral_safe_semantics_in_fields_or_names():
    names = {f.name for cls in (DigestCoverage, SegmentEvidence) for f in dataclasses.fields(cls)}
    names |= {n for n in dir(C) if not n.startswith("__")}
    names |= {r for r in WITHHELD_REASONS}
    names |= {n for n in dir(DigestCoverage) if not n.startswith("__")}
    for n in names:
        assert not any(b in n.lower() for b in _BANNED_SEMANTICS), n


def test_withheld_reasons_are_plain_strings_not_enum_members():
    import enum
    assert all(type(r) is str for r in WITHHELD_REASONS)
    assert not any(isinstance(getattr(C, n), enum.Enum) for n in dir(C) if not n.startswith("_"))
