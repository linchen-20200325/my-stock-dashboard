"""Issue #1144 A2：Digest builder `market.regime`／`market.light` 輸入邊界白名單（Gate §7.2 第 1–8、10 條）。

白名單由 `shared.regime_arbiter.REGIME_LIGHT` 推導（不新增真相源）；比對 `strip().lower()`，Fact.text 逐字保留；
名單外非空值 → INVALID；既有佔位字／未載入／無 stamp → 仍 MISSING（MISSING 優先於 INVALID）。
（第 9 條 A3 配對一致性：本批不做。）
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

import src.services.decision_digest_builder as B
from shared.decision_digest import DataStatus, MissingReason
from shared.freshness_policy import FreshnessStatus
from shared.regime_arbiter import REGIME_LIGHT
from src.services.decision_digest_assembly import EvidenceInput, assemble_digest
from src.services.decision_digest_builder import SourceStamp, build_decision_digest
from src.services.decision_digest_summary import build_rule_summary

NOW = datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc)
STAMP = SourceStamp("macro_state.json", date(2026, 10, 26))

GARBAGE = ["載入中", "待評估", "pending", "loading", "foo", "TBD", "⚪", "多頭", "bullish", "🟣", "Bull!", "bull bear"]


def macro(**over):
    base = {"is_loaded": True, "regime": "caution", "light": "🔴", "health": 60.0}
    base.update(over)
    return base


def facts(ms=None, stamp=STAMP):
    d = build_decision_digest(generated_at=NOW, macro_state=macro(**(ms or {})), macro_stamp=stamp)
    return d, {f.fact_id: f for f in d.market.facts}


# 1 ─ 垃圾值 → INVALID
@pytest.mark.parametrize("bad", GARBAGE)
def test_garbage_regime_is_invalid(bad):
    _, fm = facts({"regime": bad})
    f = fm["market.regime"]
    assert f.status is DataStatus.INVALID and f.text is None and f.value is None
    assert fm["market.light"].status is DataStatus.OK            # 只影響該事實


@pytest.mark.parametrize("bad", GARBAGE)
def test_garbage_light_is_invalid(bad):
    _, fm = facts({"light": bad})
    f = fm["market.light"]
    assert f.status is DataStatus.INVALID and f.text is None
    assert fm["market.regime"].status is DataStatus.OK


# 2 ─ 正例
@pytest.mark.parametrize("regime", sorted(set(REGIME_LIGHT) - {"unknown"}))
def test_every_valid_regime_and_its_light_are_ok_verbatim(regime):
    light = REGIME_LIGHT[regime]
    _, fm = facts({"regime": regime, "light": light})
    assert (fm["market.regime"].status, fm["market.regime"].text) == (DataStatus.OK, regime)
    assert (fm["market.light"].status, fm["market.light"].text) == (DataStatus.OK, light)


# 3 ─ 大小寫／空白：比對通過、text 逐字
@pytest.mark.parametrize("raw", [" Bull ", "Bull", "BULL", "\tneutral\n", " Caution", "BEAR "])
def test_case_and_whitespace_variants_pass_and_text_is_verbatim(raw):
    _, fm = facts({"regime": raw})
    assert fm["market.regime"].status is DataStatus.OK and fm["market.regime"].text == raw


def test_light_whitespace_variant_verbatim():
    _, fm = facts({"light": " 🟡 "})
    assert fm["market.light"].status is DataStatus.OK and fm["market.light"].text == " 🟡 "


# 4 ─ MISSING 保持
def test_not_loaded_stays_missing_even_with_garbage():
    _, fm = facts({"is_loaded": False, "regime": "載入中", "light": "⚪"})
    for k in ("market.regime", "market.light"):
        assert fm[k].status is DataStatus.MISSING and fm[k].missing_reason is MissingReason.NO_INPUT


def test_no_stamp_stays_missing_even_with_garbage():
    _, fm = facts({"regime": "foo", "light": "⚪"}, stamp=None)
    assert all(f.status is DataStatus.MISSING for f in fm.values())


@pytest.mark.parametrize("ms", [{"regime": None}, {"regime": ""}, {"regime": "  "}, {"regime": 5}])
def test_blank_or_non_str_regime_is_missing_not_invalid(ms):
    _, fm = facts(ms)
    assert fm["market.regime"].status is DataStatus.MISSING


# 5 ─ 佔位字保持 MISSING
@pytest.mark.parametrize("ph", ["unknown", " UNKNOWN ", "N/A", "n/a", "--", "-", "0", "0.0"])
def test_placeholders_stay_missing_for_regime(ph):
    _, fm = facts({"regime": ph})
    assert fm["market.regime"].status is DataStatus.MISSING


@pytest.mark.parametrize("ph", ["⬜", " ⬜ ", "N/A", "--", "0"])
def test_placeholders_stay_missing_for_light(ph):
    _, fm = facts({"light": ph})
    assert fm["market.light"].status is DataStatus.MISSING


# 6 ─ 端到端：摘要不含垃圾字串
@pytest.mark.parametrize("bad", ["載入中", "待評估", "pending", "foo"])
def test_rule_summary_never_contains_garbage(bad):
    d, _ = facts({"regime": bad, "light": bad})
    res = build_rule_summary(d)
    assert bad not in repr(res.sections) + repr(res.lines)


# 7 ─ assembly：垃圾值 → market.used=False
def test_assembly_market_not_used_on_garbage_and_used_on_valid():
    ev = EvidenceInput(stamp=STAMP, freshness=FreshnessStatus.FRESH)

    def market_seg(**ms):
        a = assemble_digest(generated_at=NOW, macro_state=macro(**ms), macro_evidence=ev)
        return next(s for s in a.coverage.segments if s.segment == "market")

    assert market_seg(regime="載入中").used is False
    assert market_seg(light="待評估").used is False
    assert market_seg().used is True


# 8 ─ SSOT 等式
def test_whitelists_are_derived_from_regime_light_ssot():
    assert B._VALID_REGIMES == set(REGIME_LIGHT) - {"unknown"}
    assert B._VALID_LIGHTS == {REGIME_LIGHT[r] for r in B._VALID_REGIMES}
    assert "⬜" not in B._VALID_LIGHTS and "unknown" not in B._VALID_REGIMES


# 10 ─ 突變：白名單放寬為接受任何字串 → 反例必須轉紅
class _AcceptAll:
    def __contains__(self, _):
        return True


def test_mutation_relaxed_whitelist_turns_counterexamples_red(monkeypatch):
    _, fm = facts({"regime": "foo", "light": "⚪"})
    assert fm["market.regime"].status is DataStatus.INVALID          # 未突變：綠
    monkeypatch.setattr(B, "_VALID_REGIMES", _AcceptAll())
    monkeypatch.setattr(B, "_VALID_LIGHTS", _AcceptAll())
    _, fm = facts({"regime": "foo", "light": "⚪"})
    # 突變後，上面 INVALID 反例的斷言會失敗（＝守衛有效）
    assert fm["market.regime"].status is DataStatus.OK
    assert fm["market.light"].status is DataStatus.OK
    with pytest.raises(AssertionError):
        assert fm["market.regime"].status is DataStatus.INVALID
