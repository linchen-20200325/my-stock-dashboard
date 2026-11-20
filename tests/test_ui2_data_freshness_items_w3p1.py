# -*- coding: utf-8 -*-
"""tests/test_ui2_data_freshness_items_w3p1.py — W3-P1：🗂 Real-data Preview 預設收合 L2「各項明細」（八項固定順序）。

授權：#1199 comment 7025346343（客戶「同意」＝GPT 總管對客戶本輪直接回答的轉錄；非原生 GitHub 客戶留言）、7025269520（總管技術限縮）、
7024073040（方案 A）、7021701891（總管裁示）。範圍：只在 Real 軸、🗂 資料頁新增**一個**預設收合 L2 區塊
`data_freshness_items`（標題「各項明細」＝DEC-177 B 既有名稱），按 `FRESHNESS_ITEMS` 固定順序逐行；僅 twii（索引 0）與 regime（索引 6）
轉述同一份 snapshot 的 `twii_card_spec`／`regime_spec`／`freshness_states`（不重算新鮮度、不讀時鐘），其餘六項逐項既有 `⬜ 尚未提供`。

本檔鎖定：
- S 結構／順序／預設收合／FAKE 零真值／首屏四列與免責·CTA·Q3 一字不動；
- M 狀態×八項矩陣：twii 五態＋歧義＋未來日＋FETCH_FAILED；regime 四態（e／n／missing／unavailable 互斥、不退化成只顯缺日）；
- R1（只有 in_rule／stale 且日期有效才顯示日期）／R2（FETCH_FAILED 即使 in_rule 也帶抓取失敗人話）／R3（日 K 不計入、不背書）；
- C 與 📊 同一 snapshot 的一致性與守恆 `a+b+c+d+e+n=2`；未接六項無值／來源／資料日、不被算失敗；
- N 不外洩（規則分支 id／fetched_at／published_at／「最新」）、不補造 regime.as_of；
- G 守衛精確同步與負例：`SHOWN_FOLDS`／`EXPECTED_SHOWN_FOLDS`／`P3_ALLOWED_EXPANDER_TITLES` 三方一致、`WIRED_PATHS` 只多兩個精確 tuple、
  無 prefix／wildcard、移除或多加一個條目即轉紅；明細區形狀補償檢查器（WIRED_PATHS 對放行路徑整個放行，所以兩列的形狀在此精確鎖定）。

以下為自跑結論，未經第二組驗證；每條測試的「牙」（暫時突變→紅→還原）結果記在 PR 描述與 DEC-209。
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from shared import regime_arbiter as RA
from shared.ui2_contract import text as T
from shared.ui2_contract.models import CapabilityState, FieldState, FieldVM, JudgementState, PageVM
from shared.ui2_contract.pages import P4_DATA, P4_HOLD, P4_MARKET, P4_ME, P4_TARGET, PAGE_IDS, SCENARIO_IDS
from shared.upstream_state import UPSTREAM_TEXT_FETCH_FAILED
from src.services.ui2 import data_page as DP
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import (
    CONTRACT_ERROR, FUTURE_AS_OF_ERROR, RealFeedContractError, RealFeedSnapshot, freshness_states, get_real_page_vm,
)
from src.ui2.views import _page
from tests import test_ui2_data_freshness_overview as OV
from tests import test_ui2_real_feed as RF
from tests.test_ui2_p3_evidence_preservation import EXPECTED_SHOWN_FOLDS
from tests.test_ui2_p1_human_text import hits_in, vm_visible_text

ROOT = Path(__file__).resolve().parent.parent
APP_UI2 = ROOT / "app_ui2.py"

SEC_ID = "data_freshness_items"
SEC_TITLE = "各項明細"
#: 線框 §1.2／DEC-177（客戶同意 §1.2 的 8 項與其順序）；字面釘死，不從實作取。
ITEM_LABELS = ("台股加權指數", "外資買賣超", "融資餘額", "M1B／M2", "台灣 PMI", "板塊資金流", "市場位階", "基本面季報")
TWII_I, REGIME_I = 0, 6
UNWIRED_IS = (1, 2, 3, 4, 5, 7)
NOT_PROVIDED = "⬜ 尚未提供"
# 既有字句（逐字；repo 內 grep 驗證存在）
IN_RULE = "資料日在規則內"
STALE_CHIP = "⚠ 過期或可能已過期"
MISSING = "⬜ 資料未備"
UNAVAIL = "🔴 來源目前不可用或資料異常"
UNDET = "⬜ 無法判定"
NOT_LOADED = "⬜ 尚未載入"
ASOF_MISSING = "⬜ 資料日未提供"

twii, regime, snap = OV.twii, OV.regime, OV.snap


def items_section(vm: PageVM):
    secs = [s for s in vm.context.sections if s.section_id == SEC_ID]
    assert len(secs) == 1, [s.section_id for s in vm.context.sections]
    return secs[0]


def items(s: RealFeedSnapshot) -> list[FieldVM]:
    return list(items_section(get_real_page_vm(P4_DATA, s)).fields)


def row_text(f: FieldVM) -> str:
    return "｜".join(x for x in (f.label, f.value_text, f.status_text, f.detail, f.freshness.as_of, f.freshness.source) if x)


TWII_CASES = {
    "in_rule": twii(),
    "in_rule_fetch_failed": twii(upstream_state="FETCH_FAILED", has_upstream_error=True),
    "in_rule_legacy_upstream_error": twii(has_upstream_error=True),
    "stale": twii(is_stale=True, age_days=5, stale_reason="已 5 天沒有新資料", as_of="2026-11-10"),
    "stale_unknown": twii(is_stale=None, age_days=None, as_of="2026-11-10"),
    "stale_fetch_failed": twii(is_stale=True, age_days=5, as_of="2026-11-10", upstream_state="FETCH_FAILED",
                               has_upstream_error=True),
    "stale_no_date": twii(is_stale=True, age_days=5, as_of=None),
    "missing_residual_date": twii(ok=False, close=(), as_of="2026-11-12", is_stale=None),
    "missing_no_date_with_value": twii(as_of=None),
    "unavailable_residual_date": twii(ok=False, close=(), as_of="2026-11-12", failed=True, error_type="OSError", is_stale=None),
    "ambiguous": twii(as_of_ambiguous=True, as_of="2026-11-12"),
}
TWII_SNAPS = {
    **{k: snap(v, "", regime("unloaded")) for k, v in TWII_CASES.items()},
    "future_error": snap(None, FUTURE_AS_OF_ERROR, regime("unloaded")),
    "contract_error": snap(None, CONTRACT_ERROR, regime("unloaded")),
    "exception": snap(None, "OSError", regime("unloaded")),
}
REGIME_SNAPS = {"unloaded": snap(twii(), "", regime("unloaded")), "breadth": snap(twii(), "", regime("breadth")),
                "loaded": snap(twii(), "", regime("bull")), "exception": snap(twii(), "", None, "OSError"),
                "contract": snap(twii(), "", None, CONTRACT_ERROR)}
EVERY_SNAP = {**OV.ALL_SNAPS, **{f"t:{k}": v for k, v in TWII_SNAPS.items()}, **{f"r:{k}": v for k, v in REGIME_SNAPS.items()}}


# ═══════════════════════════ S 結構
def test_real_data_page_has_exactly_one_collapsed_l2_items_section_in_fixed_order():
    vm = get_real_page_vm(P4_DATA, snap(twii(), "", regime("unloaded")))
    sec = items_section(vm)
    assert (sec.section_id, sec.title, sec.level, sec.mode) == (SEC_ID, SEC_TITLE, "L2", None)
    assert tuple(f.label for f in sec.fields) == ITEM_LABELS
    assert tuple(f.label for f in sec.fields) == tuple(DP.FRESHNESS_ITEM_LABELS[k] for k, _ in DP.FRESHNESS_ITEMS)
    assert [k for k, _ in DP.FRESHNESS_ITEMS][TWII_I] == "twii" and [k for k, _ in DP.FRESHNESS_ITEMS][REGIME_I] == "regime"
    assert [k for k, fact in DP.FRESHNESS_ITEMS if fact is None] == [DP.FRESHNESS_ITEMS[i][0] for i in UNWIRED_IS]
    assert [s.section_id for s in vm.context.sections] == ["data_overview", SEC_ID]


@pytest.mark.parametrize("name", sorted(EVERY_SNAP))
def test_the_first_screen_is_byte_identical_with_and_without_the_items_section(name):
    """首屏 `first/context_rows/0..3` 恰四列、四問、CTA、免責、Q3 一字不動：有明細區的 VM 首屏＝沒有明細區的 VM 首屏。"""
    s = EVERY_SNAP[name]
    with_items = get_real_page_vm(P4_DATA, s)
    from src.services.ui2.vm_common import build_page_vm
    c = DP.data_page_canonical(DP.counts_from_states(freshness_states(s)))
    c.update(scenario="real", is_fake=False)
    assert c["sections"][-1]["key"] != SEC_ID                      # 對照組：不帶 items 的 canonical
    base = build_page_vm(c)
    assert with_items.context.first_screen == base.context.first_screen
    assert len(with_items.context.first_screen.context_rows) == 4
    assert with_items.banner_text == base.banner_text and with_items.context.cards == base.context.cards == ()
    assert OV.check_freshness_shapes(with_items) == []


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_fake_axis_has_no_items_section_and_no_real_value(scenario):
    vm = get_preview_page_vm(P4_DATA, scenario)
    assert [s.section_id for s in vm.context.sections] == ["data_overview"]
    blob = repr(vm)
    assert SEC_TITLE not in blob and SEC_ID not in blob and "台股加權指數" not in blob
    assert DP.data_page_canonical()["sections"] == DP.data_page_canonical(None)["sections"]
    assert all(s["key"] != SEC_ID for s in DP.data_page_canonical()["sections"])


def test_items_requires_real_counts_and_is_never_added_to_the_fake_canonical():
    with pytest.raises((ValueError, TypeError)):
        DP.data_page_canonical(None, items=[{"key": "x"}])


def test_other_pages_are_unchanged_by_the_new_section():
    s = snap(twii(), "", regime("unloaded"))
    for p in (P4_MARKET, P4_TARGET, P4_HOLD, P4_ME):
        assert SEC_ID not in {x.section_id for x in get_real_page_vm(p, s).context.sections}


# ═══════════════════════════ M 狀態×八項矩陣
def test_twii_in_rule_shows_rule_wording_and_the_valid_date_only():
    f = items(snap(twii(), "", regime("unloaded")))[TWII_I]
    assert (f.state, f.value_text, f.status_text) == (FieldState.OK, IN_RULE, None)
    assert f.detail == "資料日 2026-11-13" and f.freshness.as_of == "2026-11-13" and f.freshness.source is None


def test_twii_stale_and_unknown_freshness_show_the_stale_chip_and_the_date():
    for k in ("stale", "stale_unknown"):
        f = items(TWII_SNAPS[k])[TWII_I]
        assert (f.state, f.status_text, f.value_text) == (FieldState.STALE, STALE_CHIP, "資料日 2026-11-10"), k
        assert f.freshness.as_of == "2026-11-10"


def test_twii_stale_without_a_date_says_date_not_provided_and_never_invents_one():
    f = items(TWII_SNAPS["stale_no_date"])[TWII_I]
    assert (f.state, f.status_text, f.value_text) == (FieldState.STALE, STALE_CHIP, ASOF_MISSING)
    assert f.freshness.as_of is None and not re.search(r"\d{4}-\d{2}-\d{2}", row_text(f))


@pytest.mark.parametrize("k", ["missing_residual_date", "missing_no_date_with_value"])
def test_twii_missing_is_data_not_ready_without_any_date(k):
    f = items(TWII_SNAPS[k])[TWII_I]
    assert (f.state, f.status_text, f.value_text) == (FieldState.MISSING, MISSING, None)
    assert f.freshness.as_of is None and not re.search(r"\d{4}-\d{2}-\d{2}", row_text(f))


@pytest.mark.parametrize("k", ["unavailable_residual_date", "future_error", "contract_error", "exception"])
def test_twii_unavailable_is_red_without_value_or_date(k):
    f = items(TWII_SNAPS[k])[TWII_I]
    assert (f.state, f.status_text, f.value_text) == (FieldState.UNAVAILABLE, UNAVAIL, None)
    assert f.freshness.as_of is None and not re.search(r"\d{4}-\d{2}-\d{2}", row_text(f))


def test_twii_ambiguous_as_of_is_undeterminable_without_date_or_value():
    f = items(TWII_SNAPS["ambiguous"])[TWII_I]
    assert (f.state, f.status_text, f.value_text) == (JudgementState.UNDETERMINABLE, UNDET, None)
    assert f.freshness.as_of is None and not re.search(r"\d{4}-\d{2}-\d{2}", row_text(f))


def test_a_future_dated_fact_that_bypasses_the_feed_fails_loud_like_the_card():
    with pytest.raises(RealFeedContractError):
        items(snap(twii(as_of="2026-11-20", as_of_future=True), "", regime("unloaded")))


# R1：只有 in_rule／stale 且日期有效才顯示日期（對所有 twii 組合逐列驗；同時驗「顯示的日期＝該 fact 的 as_of」）
@pytest.mark.parametrize("k", sorted(TWII_SNAPS))
def test_r1_a_date_is_shown_only_for_in_rule_or_stale_and_equals_the_facts_date(k):
    s = TWII_SNAPS[k]
    f = items(s)[TWII_I]
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", row_text(f))
    if f.state in (FieldState.OK, FieldState.STALE) and s.twii.as_of:
        assert dates and set(dates) == {s.twii.as_of}
        assert f.freshness.as_of == s.twii.as_of
    else:
        assert dates == [] and f.freshness.as_of is None


# R2：FETCH_FAILED 即使 in_rule 也必須帶既有抓取失敗人話；且不得宣稱成功／最新
@pytest.mark.parametrize("k", ["in_rule_fetch_failed", "in_rule_legacy_upstream_error", "stale_fetch_failed"])
def test_r2_fetch_failed_is_reminded_even_when_the_item_is_in_rule(k):
    f = items(TWII_SNAPS[k])[TWII_I]
    assert UPSTREAM_TEXT_FETCH_FAILED in (f.detail or "")
    assert not any(w in row_text(f) for w in ("更新成功", "抓取成功", "最新", "今日", "已更新", "來源正常"))
    if k.startswith("in_rule"):
        assert f.state is FieldState.OK and f.value_text == IN_RULE


@pytest.mark.parametrize("k", ["in_rule", "stale", "stale_unknown"])
def test_r2_no_fetch_failed_sentence_when_upstream_is_fine(k):
    assert UPSTREAM_TEXT_FETCH_FAILED not in row_text(items(TWII_SNAPS[k])[TWII_I])


# R3：日 K 不計入、不替日 K 品質背書
def test_r3_kbar_status_never_changes_the_twii_row_and_is_never_endorsed():
    base = items(snap(twii(), "", regime("unloaded")))
    for kerr in ("OSError", CONTRACT_ERROR):
        s = RealFeedSnapshot.of(twii(), "", regime("unloaded"), "", kbar=None, kbar_error=kerr)
        got = items(s)
        assert got == base
        assert not any("日 K" in row_text(f) or "K 線" in row_text(f) for f in got)


# regime 四態（D-5 不改守衛；e／n／missing／unavailable 互斥，不得只顯缺日）
def test_regime_not_evaluated_uses_the_existing_not_loaded_chip_plus_missing_date():
    f = items(REGIME_SNAPS["unloaded"])[REGIME_I]
    assert (f.state, f.status_text, f.value_text, f.detail) == (FieldState.NOT_EVALUATED, NOT_LOADED, None, ASOF_MISSING)


def test_regime_undeterminable_uses_the_existing_undeterminable_chip_with_only_safe_existing_reason():
    f = items(REGIME_SNAPS["breadth"])[REGIME_I]
    assert (f.state, f.status_text, f.value_text) == (JudgementState.UNDETERMINABLE, UNDET, None)
    assert f.detail == f"{ASOF_MISSING}；原因：尚缺正式的市場廣度（漲跌家數）資料"


def test_regime_loaded_without_a_date_is_missing_and_never_shows_the_label():
    f = items(REGIME_SNAPS["loaded"])[REGIME_I]
    assert (f.state, f.status_text, f.value_text, f.detail) == (FieldState.MISSING, MISSING, None, ASOF_MISSING)


@pytest.mark.parametrize("k", ["exception", "contract"])
def test_regime_unavailable_stays_red(k):
    f = items(REGIME_SNAPS[k])[REGIME_I]
    assert (f.state, f.status_text, f.value_text) == (FieldState.UNAVAILABLE, UNAVAIL, None)


def test_regime_e_n_missing_unavailable_are_mutually_distinct_not_collapsed_into_missing_date():
    seen = {k: (items(REGIME_SNAPS[k])[REGIME_I].state, items(REGIME_SNAPS[k])[REGIME_I].status_text)
            for k in ("unloaded", "breadth", "loaded", "exception")}
    assert len(set(seen.values())) == 4, seen


@pytest.mark.parametrize("name", sorted(EVERY_SNAP))
def test_regime_row_never_carries_a_date_a_value_or_a_source(name):
    f = items(EVERY_SNAP[name])[REGIME_I]
    assert f.value_text is None and f.freshness.as_of is None and f.freshness.source is None
    assert not re.search(r"\d{4}-\d{2}-\d{2}", row_text(f))


# ═══════════════════════════ C 與 📊 同 snapshot 一致、守恆
_BUCKET = {FieldState.OK: "a", FieldState.STALE: "b", FieldState.MISSING: "c", FieldState.UNAVAILABLE: "d",
           FieldState.NOT_EVALUATED: "e", JudgementState.UNDETERMINABLE: "n"}


@pytest.mark.parametrize("name", sorted(EVERY_SNAP))
def test_items_buckets_equal_the_first_screen_counts_and_conserve_k_equals_2(name):
    s = EVERY_SNAP[name]
    rows = items(s)
    got = {x: 0 for x in "abcden"}
    for i in (TWII_I, REGIME_I):
        got[_BUCKET[rows[i].state]] += 1
    assert sum(got.values()) == 2
    p = OV._parse(s)                                  # 首屏四列解析出的 a..e、n
    assert got == {x: p[x] for x in "abcden"}
    if not (s.twii is not None and s.twii.as_of_ambiguous):       # 既有獨立算式不建模「台股歧義→無法判定」；該情況只比首屏與 counts
        assert got == OV._independent_counts(s)       # 與 📊 卡片／位階欄位本身另算的結果一致
    c = DP.counts_from_states(freshness_states(s))
    assert (got["a"], got["b"], got["c"], got["d"], got["e"], got["n"]) == (
        c.in_rule, c.stale, c.missing, c.unavailable, c.not_evaluated, c.undeterminable)


@pytest.mark.parametrize("name", sorted(EVERY_SNAP))
def test_items_state_text_equals_the_market_page_state_of_the_same_snapshot(name):
    """與 📊 同 snapshot：台股列的語意軸與 📊 台股卡一致；位階列與 📊 現況一致（互斥態逐一對上）。"""
    s = EVERY_SNAP[name]
    vm = get_real_page_vm(P4_MARKET, s)
    card = next(c.field for c in vm.context.cards if c.card_id == "twii")
    cur = vm.context.first_screen.current_state
    rows = items(s)
    if card.state is FieldState.OK and card.freshness.as_of is None:
        assert rows[TWII_I].state is FieldState.MISSING
    else:
        assert rows[TWII_I].state == card.state
    if cur.state is FieldState.OK and cur.freshness.as_of is None:       # 已載入、位階契約無資料日
        assert rows[REGIME_I].state is FieldState.MISSING
    else:
        assert rows[REGIME_I].state == cur.state


# ═══════════════════════════ 未接六項
@pytest.mark.parametrize("name", sorted(EVERY_SNAP))
def test_the_six_unwired_items_are_capability_not_provided_without_value_source_or_date(name):
    rows = items(EVERY_SNAP[name])
    for i in UNWIRED_IS:
        f = rows[i]
        assert f.label == ITEM_LABELS[i]
        assert f.capability is CapabilityState.NOT_PROVIDED and f.state is None and f.layer == "capability"
        assert f.status_text == NOT_PROVIDED and f.value_text is None
        assert f.freshness.as_of is None and f.freshness.source is None
        assert f.detail == DP.R_DATA_NEXT_STEP == "完整資料健康度開放後才可查看"
        assert not re.search(r"\d", f"{f.value_text}{f.status_text}{f.detail}")


def test_unwired_rows_are_identical_whatever_the_snapshot_and_are_not_counted_as_failures():
    ref = [items(snap(twii(), "", regime("unloaded")))[i] for i in UNWIRED_IS]
    for s in EVERY_SNAP.values():
        assert [items(s)[i] for i in UNWIRED_IS] == ref
        assert OV.counts(s).not_provided == 6 and OV.counts(s).wired == 2


# ═══════════════════════════ N 不外洩
_LEAK_WORDS = ("fetched_at", "published_at", "最新", "今日", "已更新", "更新成功", "抓取成功", "規則分支", "非資料來源",
               "REGIME_LABEL", "source", "TWII", "本地加權指數歷史快取", "freshness", "STALE_DAYS", "MAX_LAG")


@pytest.mark.parametrize("name", sorted(EVERY_SNAP))
def test_items_do_not_leak_branch_ids_timestamps_sources_or_regime_labels(name):
    s = EVERY_SNAP[name]
    rows = items(s)
    blob = "\n".join(row_text(f) for f in rows)
    assert not [w for w in _LEAK_WORDS if w in blob], blob
    for src in (RA.SOURCE_UNLOADED, RA.SOURCE_UNEVALUATED_BREADTH, RA.SOURCE_BULL_SCORE):
        assert src not in blob
    assert not [lbl for lbl in ("多頭", "震盪", "轉守", "空頭", "未評估") if lbl in blob]
    assert all(f.freshness.source is None for f in rows)
    assert hits_in(blob) == []
    assert hits_in(vm_visible_text(get_real_page_vm(P4_DATA, s))) == []


# ═══════════════════════════ 渲染（AppTest）：預設收合、八行順序、FAKE 無明細
def _real_app(monkeypatch, s: RealFeedSnapshot):
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    a.session_state["ui2_feed"] = "real"
    monkeypatch.setattr("src.ui2.shell.app.read_real_snapshot", lambda: s)
    a.run(timeout=60)
    a.radio(key="ui2_page").set_value(P4_DATA).run(timeout=60)
    return a


def _blob(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _row_texts(html: str) -> list[str]:
    out = []
    for m in re.finditer(r'<div class="ui2-row" [^>]*>(.*?)</div></div>|<div class="ui2-row" [^>]*>(.*?)</div>(?=<div class="ui2-row"|$)',
                         html, flags=re.S):
        out.append(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(0))).strip())
    return out


def test_expander_is_rendered_collapsed_with_the_eight_rows_in_fixed_order(monkeypatch):
    at = _real_app(monkeypatch, snap(twii(), "", regime("unloaded")))
    assert not at.exception
    ex = [e for e in at.expander if e.label.removeprefix("▸ ") == SEC_TITLE]
    assert len(ex) == 1 and not ex[0].proto.expanded
    assert [e.label.removeprefix("▸ ") for e in at.expander] == [SEC_TITLE]
    inside = "\n".join(m.value for m in ex[0].markdown)
    labels = re.findall(r'<div class="ui2-row__label">([^<]*)</div>', inside)
    assert labels == list(ITEM_LABELS)
    assert inside.count('class="ui2-row"') == 8
    # 八行文字（old→new 證據用）
    txt = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"^[^>]*>", "", seg))).strip()
           for seg in inside.split('<div class="ui2-row"')[1:]]
    assert txt[0] == f"台股加權指數 {IN_RULE} 資料日 2026-11-13"
    assert txt[REGIME_I] == f"市場位階 {NOT_LOADED} {ASOF_MISSING}"
    for i in UNWIRED_IS:
        assert txt[i] == f"{ITEM_LABELS[i]} {NOT_PROVIDED} 完整資料健康度開放後才可查看"


def test_collapsed_expander_does_not_change_the_first_screen_dom(monkeypatch):
    """展開區在首屏四列之後；首屏（ctx 列、免責、四問、CTA）DOM 與無明細區時相同（只多一個收合 expander）。"""
    at = _real_app(monkeypatch, snap(twii(), "", regime("unloaded")))
    inside = {id(m) for e in at.expander for m in e.markdown}
    blob = re.sub(r"<style.*?</style>", "", "\n".join(m.value for m in at.markdown if id(m) not in inside), flags=re.S)
    assert blob.count('data-ui2-q="ctx"') == 4
    for w in ("固定清單 8 項", "已接入畫面 2 項｜尚未提供 6 項", DP.FRESHNESS_DISCLAIMER, DP.R_DATA_FIRST_SCREEN, DP.R_DATA_NEXT_STEP):
        assert w in blob
    first_ctx = blob.index('data-ui2-q="ctx"')
    assert blob.index(IN_RULE + " 1 項") > first_ctx
    # 明細列在 expander 內，不在首屏 markdown
    assert SEC_TITLE not in blob and 'class="ui2-row__label">台股加權指數' not in blob


def test_fake_axis_renders_no_items_expander(monkeypatch):
    from streamlit.testing.v1 import AppTest
    for sc in SCENARIO_IDS:
        a = AppTest.from_file(str(APP_UI2), default_timeout=60)
        a.session_state["ui2_scenario"] = sc
        a.run(timeout=60)
        a.radio(key="ui2_page").set_value(P4_DATA).run(timeout=60)
        assert [e.label for e in a.expander] == [] and SEC_TITLE not in _blob(a)


def test_degraded_real_page_shows_red_items_without_regime_label_residue(monkeypatch):
    """降級頁（讀取整體失敗）：明細區顯示兩項紅態、六項尚未提供；且不引入位階字殘留（D-5 守衛不改）。"""
    with pytest.MonkeyPatch.context() as mp:
        RF._boom_shell(mp)
        from streamlit.testing.v1 import AppTest
        a = AppTest.from_file(str(APP_UI2), default_timeout=60)
        a.query_params["ui2_dev"] = "1"
        a.run(timeout=60)
        a.selectbox(key="ui2_feed").set_value("real").run(timeout=60)
        a.radio(key="ui2_page").set_value(P4_DATA).run(timeout=60)
        blob = RF._blob(a)
        ex = [e for e in a.expander if e.label.removeprefix("▸ ") == SEC_TITLE]
        assert len(ex) == 1 and not ex[0].proto.expanded
        inside = "\n".join(m.value for m in ex[0].markdown)
        assert inside.count(UNAVAIL) == 2 and inside.count(NOT_PROVIDED) == 6
        assert RF.regime_label_residue(blob, P4_DATA) == []


# ═══════════════════════════ G 守衛精確同步與負例
_NEW_WIRED = {(P4_DATA, f"sections/{SEC_ID}/{i}") for i in (TWII_I, REGIME_I)}


def test_shown_folds_gain_exactly_one_entry_and_three_places_agree():
    from tests.ui2_viewport import measure_viewport as MV
    assert _page.SHOWN_FOLDS == EXPECTED_SHOWN_FOLDS
    assert (P4_DATA, SEC_ID) in _page.SHOWN_FOLDS
    assert _page.SHOWN_FOLDS - {(P4_DATA, SEC_ID)} == frozenset({("p4_target", "conditions"), ("p4_me", "digest"), ("p4_me", "registry")})
    assert MV.P3_ALLOWED_EXPANDER_TITLES["p4_data"] == frozenset({SEC_TITLE})
    assert all(MV.P3_ALLOWED_EXPANDER_TITLES[p] == v for p, v in MV.P3_ALLOWED_EXPANDER_TITLES.items() if p != "p4_data"
               for v in [MV.P3_ALLOWED_EXPANDER_TITLES[p]])
    assert {p: v for p, v in MV.P3_ALLOWED_EXPANDER_TITLES.items() if p != "p4_data"} == {
        "p4_market": frozenset(), "p4_hold": frozenset(), "p4_target": frozenset({"選股條件（收合）"}),
        "p4_me": frozenset({"Audit：Decision Digest", "Audit：Rule Registry（唯讀）"})}


def test_wired_paths_gain_exactly_two_exact_tuples_and_no_wildcard_or_prefix():
    data_paths = {k for k in RF.WIRED_PATHS if k[0] == P4_DATA}
    assert data_paths == {(P4_DATA, f"first/context_rows/{i}") for i in range(4)} | _NEW_WIRED
    assert RF.WIRED_PATHS - data_paths == frozenset({
        (P4_MARKET, "cards/twii"), (P4_MARKET, "first/current_state"), (P4_MARKET, "sections/why/0"),
        (P4_TARGET, "first/context_rows/0"), (P4_TARGET, "lookup/snapshot/5")})
    assert not any(("*" in p or p.endswith("/") or p.endswith(f"{SEC_ID}")) for _, p in RF.WIRED_PATHS)
    # 精確對到真實存在的列（二個 index 由最終 VM 實證）
    vm = get_real_page_vm(P4_DATA, snap(twii(), "", regime("unloaded")))
    paths = {p for p, _ in RF._paths(vm)}
    assert {p for _, p in _NEW_WIRED} <= paths
    wired_rows = {i for i, (k, fact) in enumerate(DP.FRESHNESS_ITEMS) if fact is not None}
    assert wired_rows == {TWII_I, REGIME_I}


def _vms(s):
    return RF._vms(s)


def _replace_item(vm: PageVM, i: int, **kw) -> PageVM:
    secs = []
    for s in vm.context.sections:
        if s.section_id == SEC_ID:
            fs = list(s.fields)
            fs[i] = dataclasses.replace(fs[i], **kw)
            s = dataclasses.replace(s, fields=tuple(fs))
        secs.append(s)
    return dataclasses.replace(vm, context=dataclasses.replace(vm.context, sections=tuple(secs)))


def test_real_vms_pass_the_unchanged_allowlist_checker_on_every_combination():
    for name, s in EVERY_SNAP.items():
        assert RF.check_only_wired_fields_carry_data(_vms(s)) == [], name


@pytest.mark.parametrize("i", UNWIRED_IS)
def test_an_unwired_row_that_carries_data_is_rejected_by_the_existing_checker(i):
    """未接六項**不在**豁免內：帶值／來源／資料日／失敗態一律被既有檢查器擋下。"""
    base = _vms(snap(twii(), "", regime("unloaded")))
    for kw in (dict(value_text="1", state=FieldState.OK, status_text=None, capability=CapabilityState.PROVIDED),
               dict(freshness=dataclasses.replace(base[P4_DATA].context.sections[1].fields[i].freshness, as_of="2026-11-13")),
               dict(freshness=dataclasses.replace(base[P4_DATA].context.sections[1].fields[i].freshness, source="X")),
               dict(detail=None)):
        bad = {**base, P4_DATA: _replace_item(base[P4_DATA], i, **kw)}
        assert RF.check_only_wired_fields_carry_data(bad), (i, kw)


def test_removing_a_new_wired_tuple_turns_the_checker_red_and_extra_tuple_is_detected(monkeypatch):
    base = _vms(snap(twii(), "", regime("unloaded")))
    for gone in _NEW_WIRED:
        with monkeypatch.context() as m:
            m.setattr(RF, "WIRED_PATHS", frozenset(RF.WIRED_PATHS - {gone}))
            assert RF.check_only_wired_fields_carry_data(base), gone
    # 多加（一個未接列）→ 本檔的精確清單測試轉紅
    extra = frozenset(RF.WIRED_PATHS | {(P4_DATA, f"sections/{SEC_ID}/1")})
    with monkeypatch.context() as m:
        m.setattr(RF, "WIRED_PATHS", extra)
        with pytest.raises(AssertionError):
            test_wired_paths_gain_exactly_two_exact_tuples_and_no_wildcard_or_prefix()


def test_shown_folds_negative_cases_turn_red(monkeypatch):
    with monkeypatch.context() as m:        # 移除
        m.setattr(_page, "SHOWN_FOLDS", frozenset(_page.SHOWN_FOLDS - {(P4_DATA, SEC_ID)}))
        with pytest.raises(AssertionError):
            test_shown_folds_gain_exactly_one_entry_and_three_places_agree()
    with monkeypatch.context() as m:        # 多加
        m.setattr(_page, "SHOWN_FOLDS", frozenset(_page.SHOWN_FOLDS | {(P4_DATA, "data_overview")}))
        with pytest.raises(AssertionError):
            test_shown_folds_gain_exactly_one_entry_and_three_places_agree()


# ── 形狀補償檢查器：WIRED_PATHS 對 (P4_DATA, sections/data_freshness_items/{0,6}) 整個放行，所以兩列內容在此精確鎖定 ──
_ALLOWED_TWII = {
    FieldState.OK: (IN_RULE, None), FieldState.STALE: (None, STALE_CHIP), FieldState.MISSING: (None, MISSING),
    FieldState.UNAVAILABLE: (None, UNAVAIL), JudgementState.UNDETERMINABLE: (None, UNDET),
}
_ALLOWED_REGIME = {
    FieldState.NOT_EVALUATED: NOT_LOADED, FieldState.MISSING: MISSING, FieldState.UNAVAILABLE: UNAVAIL,
    JudgementState.UNDETERMINABLE: UNDET,
}
_DATE_RX = re.compile(r"\d{4}-\d{2}-\d{2}")
_ITEM_DETAIL_TWII_OK = re.compile(r"資料日 \d{4}-\d{2}-\d{2}(；" + re.escape(UPSTREAM_TEXT_FETCH_FAILED) + r")?")
_ITEM_DETAIL_TWII_STALE = re.compile(re.escape(UPSTREAM_TEXT_FETCH_FAILED))


def check_items_shapes(vm: PageVM) -> list[str]:
    """兩個已接入列的精確形狀 + 六個未接列的強制形狀 + 標題／層級／順序／列數。"""
    bad: list[str] = []
    secs = [s for s in vm.context.sections if s.section_id == SEC_ID]
    if len(secs) != 1:
        return [f"{SEC_ID} 必須恰一個，收到 {len(secs)}"]
    sec = secs[0]
    if (sec.title, sec.level, sec.mode) != (SEC_TITLE, "L2", None):
        bad.append(f"區塊標題／層級被改：{(sec.title, sec.level, sec.mode)!r}")
    if tuple(f.label for f in sec.fields) != ITEM_LABELS:
        bad.append(f"八項名稱／順序不符：{[f.label for f in sec.fields]!r}")
        return bad
    for i, f in enumerate(sec.fields):
        blob = row_text(f)
        if f.freshness.source is not None:
            bad.append(f"#{i}: 不得帶 source")
        if any(w in blob for w in _LEAK_WORDS) or hits_in(blob) or any(l in blob for l in ("多頭", "震盪", "轉守", "空頭", "未評估")):
            bad.append(f"#{i}: 外洩字樣 {blob!r}")
        if i in UNWIRED_IS:
            if not (f.capability is CapabilityState.NOT_PROVIDED and f.state is None and f.status_text == NOT_PROVIDED
                    and f.value_text is None and f.freshness.as_of is None and f.detail == DP.R_DATA_NEXT_STEP):
                bad.append(f"#{i}: 未接列形狀被改 {f!r}")
        elif i == TWII_I:
            if f.state not in _ALLOWED_TWII or f.capability is not CapabilityState.PROVIDED:
                bad.append(f"#{i}: twii 狀態不合法 {f.state!r}")
                continue
            want_val, want_chip = _ALLOWED_TWII[f.state]
            if f.state is FieldState.STALE:
                ok_val = f.value_text == (f"資料日 {f.freshness.as_of}" if f.freshness.as_of else ASOF_MISSING)
            else:
                ok_val = f.value_text == want_val
            if not (ok_val and f.status_text == want_chip):
                bad.append(f"#{i}: twii 值／字樣不符 {f.value_text!r}／{f.status_text!r}")
            if f.state in (FieldState.OK, FieldState.STALE):
                if f.freshness.as_of is not None and not _DATE_RX.fullmatch(f.freshness.as_of):
                    bad.append(f"#{i}: as_of 格式不合法")
                rx = _ITEM_DETAIL_TWII_OK if f.state is FieldState.OK else _ITEM_DETAIL_TWII_STALE
                if f.state is FieldState.OK and (f.freshness.as_of is None or not rx.fullmatch(f.detail or "")
                                                 or f.detail.split("；")[0] != f"資料日 {f.freshness.as_of}"):
                    bad.append(f"#{i}: in_rule 的 detail 不合核准形狀 {f.detail!r}")
                if f.state is FieldState.STALE and f.detail is not None and not rx.fullmatch(f.detail):
                    bad.append(f"#{i}: stale 的 detail 不合核准形狀 {f.detail!r}")
            else:       # R1：missing／unavailable／undeterminable 不得帶日期、不得有 detail
                if f.freshness.as_of is not None or _DATE_RX.search(blob) or f.detail is not None:
                    bad.append(f"#{i}: {f.state!r} 不得顯示日期／detail（R1）")
        else:           # regime（索引 6）
            if f.state not in _ALLOWED_REGIME or f.capability is not CapabilityState.PROVIDED:
                bad.append(f"#{i}: regime 狀態不合法 {f.state!r}")
                continue
            if f.status_text != _ALLOWED_REGIME[f.state] or f.value_text is not None:
                bad.append(f"#{i}: regime 字樣／值不符 {f.status_text!r}／{f.value_text!r}")
            if f.freshness.as_of is not None or _DATE_RX.search(blob):
                bad.append(f"#{i}: regime 不得補日期")
            if f.state is not FieldState.UNAVAILABLE and not (f.detail or "").startswith(ASOF_MISSING):
                bad.append(f"#{i}: regime 缺日必須明寫 {f.detail!r}")
            if f.state is FieldState.UNAVAILABLE and f.detail is not None:
                bad.append(f"#{i}: regime 紅態不帶 detail")
    return bad


@pytest.mark.parametrize("name", sorted(EVERY_SNAP))
def test_items_shape_checker_passes_on_every_real_combination(name):
    assert check_items_shapes(get_real_page_vm(P4_DATA, EVERY_SNAP[name])) == []


def _base():
    return get_real_page_vm(P4_DATA, snap(twii(), "", regime("unloaded")))


@pytest.mark.parametrize("what, mutate", [
    ("twii 帶 source", lambda v: _replace_item(v, TWII_I, freshness=dataclasses.replace(
        v.context.sections[1].fields[TWII_I].freshness, source="TWII"))),
    ("twii 日期被改格式", lambda v: _replace_item(v, TWII_I, detail="資料日 2026/11/13")),
    ("twii in_rule 缺日期", lambda v: _replace_item(v, TWII_I, detail=None)),
    ("twii 寫成『最新』", lambda v: _replace_item(v, TWII_I, value_text="最新資料日在規則內")),
    ("twii 值被換成收盤值", lambda v: _replace_item(v, TWII_I, value_text="23,456.78")),
    ("twii 帶 fetched_at", lambda v: _replace_item(v, TWII_I, detail="資料日 2026-11-13；fetched_at")),
    ("regime 補日期", lambda v: _replace_item(v, REGIME_I, detail=f"{ASOF_MISSING}　2026-11-13")),
    ("regime 帶 as_of", lambda v: _replace_item(v, REGIME_I, freshness=dataclasses.replace(
        v.context.sections[1].fields[REGIME_I].freshness, as_of="2026-11-13"))),
    ("regime 缺日被拿掉（只剩狀態）", lambda v: _replace_item(v, REGIME_I, detail=None)),
    ("regime 帶規則分支來源", lambda v: _replace_item(v, REGIME_I, freshness=dataclasses.replace(
        v.context.sections[1].fields[REGIME_I].freshness, source="規則分支 id：x（非資料來源）"))),
    ("regime 洩漏位階標籤", lambda v: _replace_item(v, REGIME_I, detail=f"{ASOF_MISSING}；震盪")),
    ("未接列帶資料日", lambda v: _replace_item(v, 1, freshness=dataclasses.replace(
        v.context.sections[1].fields[1].freshness, as_of="2026-11-13"))),
    ("未接列原因被改", lambda v: _replace_item(v, 3, detail="x")),
    ("未接列被標成失敗", lambda v: _replace_item(v, 4, state=FieldState.UNAVAILABLE, status_text=UNAVAIL,
                                                  capability=CapabilityState.PROVIDED)),
])
def test_items_shape_checker_has_teeth_against_illegal_data_on_the_exempted_paths(what, mutate):
    assert check_items_shapes(mutate(_base())), what


def test_items_shape_checker_rejects_reorder_missing_section_and_wrong_title():
    vm = _base()
    sec = vm.context.sections[1]
    swapped = dataclasses.replace(sec, fields=(sec.fields[1], sec.fields[0]) + sec.fields[2:])
    retitled = dataclasses.replace(sec, title="明細")
    relevel = dataclasses.replace(sec, level="L1")
    for bad_sec in (swapped, retitled, relevel):
        v = dataclasses.replace(vm, context=dataclasses.replace(vm.context, sections=(vm.context.sections[0], bad_sec)))
        assert check_items_shapes(v)
    nosec = dataclasses.replace(vm, context=dataclasses.replace(vm.context, sections=vm.context.sections[:1]))
    assert check_items_shapes(nosec)


def test_second_items_section_or_an_items_section_on_another_page_is_not_wired():
    """明細區只放行 🗂 的那兩個精確路徑：同 id 的區塊出現在別頁、或 🗂 多一個同 id 區塊，仍被既有檢查器擋。"""
    base = _vms(snap(twii(), "", regime("unloaded")))
    sec = base[P4_DATA].context.sections[1]
    other = dataclasses.replace(base[P4_MARKET], context=dataclasses.replace(
        base[P4_MARKET].context, sections=base[P4_MARKET].context.sections + (sec,)))
    assert RF.check_only_wired_fields_carry_data({**base, P4_MARKET: other})
    dup = dataclasses.replace(sec, section_id="data_freshness_items2")
    dd = dataclasses.replace(base[P4_DATA], context=dataclasses.replace(
        base[P4_DATA].context, sections=base[P4_DATA].context.sections + (dup,)))
    assert RF.check_only_wired_fields_carry_data({**base, P4_DATA: dd})


# ═══════════════════════════ DEC-137 證據：Real 存證帶「展開後」量測（額外欄位；headless 模擬 ≠ Cloud）
@pytest.mark.parametrize("name", ["viewport_measurements.json", "viewport_measurements_streamlit156.json"])
def test_real_viewport_evidence_carries_the_expanded_items_measurement(name):
    import json
    j = json.loads((ROOT / "docs" / "vnext" / "newui2_realfeed" / name).read_text(encoding="utf-8"))
    recs = [r for r in j["results"] if r["page"] == P4_DATA]
    assert {r["viewport_name"] for r in recs} == {"mobile", "desktop"}
    for r in recs:
        e = r["expanded"]
        assert r["pass"] and e["failures"] == [] and e["collapsed_before"] is True and e["open"] is True
        assert e["row_count"] == 8 and tuple(e["row_labels"]) == ITEM_LABELS
        assert [x["title"].removeprefix("keyboard_arrow_right ") for x in r["expanders"]] == [SEC_TITLE]
        assert all(x["open"] is False for x in r["expanders"])             # 預設量測＝收合
        for k in ("doc", "main"):
            assert e["hscroll"][k]["scrollWidth"] <= e["hscroll"][k]["clientWidth"]
