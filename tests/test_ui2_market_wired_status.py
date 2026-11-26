# -*- coding: utf-8 -*-
"""tests/test_ui2_market_wired_status.py — 📊 市場頁尾「接入狀態」（B 線，方案 A；Real-data Preview only）。

授權與設計出處（#1199）：客戶 comment 7167315139（授權施工）；最終 Copy／線框／顯示條件／allowlist／N1–N11＝7160953590；
三點守衛補強＝7162031909；兩條測試定位＝7164432247；Work 設計 PASS 與兩條最小修正＝7165666659。**衝突以原文為準。**

範圍（production 僅 `src/services/ui2/real_canonical.py` 一檔）：📊 sections 尾端新增**一個** L1 區塊 `market_wired_status`
（標題＝既有「接入狀態」），恰 2 欄——`/0`＝「🗂 資料｜固定清單 N 項」、`/1`＝「其中｜已接入畫面 K 項｜尚未提供 M 項」＋單一 Q 句 detail。
只在 Real 且 (a) 已接入兩項狀態皆非 unavailable、(b) 台股上游訊號不是 FETCH_FAILED（含 legacy）時畫；FAKE 結構上無路徑。

本檔鎖定：
- N1 正常缺值必畫；N2／N3 unavailable／contract_error／混合／Real degraded（真 shell AppTest）不畫；N6 upstream 三態分流（含 legacy）；
- N4 FAKE 五頁×全場景 VM 不含該區塊且與 P3 baseline 的 FAKE 指紋逐值相等；
- N5 識別字在 production 只准出現在 `real_canonical.py`（注入到其他檔須紅）；測試端只准本檔＋`WIRED_PATHS` 兩個精確 tuple＋既有精確集合測試只讀引用；
- N7「接入狀態」在 📊 渲染 markdown 恰 1 次；N8 與 🗂 資料頁 `fresh_total`／`fresh_wired` 逐字一致；
- N9 其餘四頁 VM 與 base 逐位相同（以 base 計算的雜湊釘死）、📊 去掉新區塊後與 base 逐位相同；
- N10 `at.expander==[]`、`SHOWN_FOLDS` 仍 4 項；N11 `ENGINEERING_VOCAB`＋`shown()` 掃描含兩個新字串；
- 形狀補償守衛（`WIRED_PATHS` 命中會**跳過整欄檢查**，所以被跳過的檢查全補在 `shape_violations`），含負控；
- DOM 順序：新區塊在 OneBrain／指標卡／今日變化／主圖槽之後、恰 1 次，既有輸出與關閉該功能時逐位相同。

以下為實作者自跑結論，未經第二組驗證；每條守衛的「牙」（暫時突變→紅→還原）結果見 PR 描述。
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
from pathlib import Path

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.models import CapabilityState, FieldState, FieldVM, FreshnessInfo, PageVM, SectionVM
from shared.ui2_contract.pages import (
    ACCOUNT_IDS, P4_DATA, P4_HOLD, P4_MARKET, P4_ME, PAGE_IDS, PAGE_LABELS, SCENARIO_IDS,
)
from shared.upstream_state import UPSTREAM_TEXT_FETCH_FAILED
from src.services.ui2 import data_page as DP
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import FUTURE_AS_OF_ERROR, CONTRACT_ERROR, get_real_page_vm
from src.ui2.components.html import shown, status_chip_html
from src.ui2.views import _page
from tests import test_ui2_data_freshness_overview as OV
from tests import test_ui2_real_feed as RF
from tests.test_ui2_p1_human_text import ENGINEERING_VOCAB, hits_in, vm_visible_text
from tests.test_ui2_p3_evidence_preservation import BASELINE, EXPECTED_SHOWN_FOLDS, fingerprint

ROOT = Path(__file__).resolve().parent.parent
APP_UI2 = ROOT / "app_ui2.py"

# ── 核准文案（逐字釘死；⛔ 不從 production 取，否則自比永遠綠）──
SEC_ID = "market_wired_status"
TITLE = "接入狀態"
LABEL0 = "🗂 資料"
LABEL1 = "其中"
Q = "已接入只表示畫面已有讀取路徑，不代表今日有值，也不是市場判斷依據。"
N_TOTAL = len(DP.FRESHNESS_ITEMS)
N_WIRED = len(DP.WIRED_ITEM_KEYS)
VAL0 = f"固定清單 {N_TOTAL} 項"
VAL1 = f"已接入畫面 {N_WIRED} 項｜尚未提供 {N_TOTAL - N_WIRED} 項"

twii, regime, snap = OV.twii, OV.regime, OV.snap


# ═══════════════════════════ 輸入矩陣（Real snapshot）
def _R(kind="bull"):
    return regime(kind)


#: 必須畫（顯示條件 (a)(b) 皆成立）：正常缺值、過期、未評估、無法判定、upstream 非 FETCH_FAILED。
DRAW = {
    "loaded": snap(twii(), "", _R("bull")),
    "unloaded": snap(twii(), "", _R("unloaded")),
    "breadth_undeterminable": snap(twii(), "", _R("breadth")),
    "missing": snap(twii(ok=False, close=(), as_of=None, is_stale=None), "", _R("bull")),
    "missing_no_date": snap(twii(as_of=None), "", _R("bull")),
    "stale": snap(twii(is_stale=True, age_days=5), "", _R("unloaded")),
    "stale_unknown": snap(twii(is_stale=None, age_days=None), "", _R("unloaded")),
    "ambiguous_undeterminable": snap(twii(as_of_ambiguous=True), "", _R("bull")),
    "no_new_data": snap(twii(upstream_state="NO_NEW_DATA"), "", _R("bull")),
    "undetermined": snap(twii(upstream_state="UNDETERMINED"), "", _R("bull")),
    "no_new_data_with_error_flag": snap(twii(upstream_state="NO_NEW_DATA", has_upstream_error=True), "", _R("bull")),
    "empty_upstream_no_error": snap(twii(upstream_state="", has_upstream_error=False), "", _R("bull")),
}
#: 必須不畫：任一已接入項 unavailable，或台股上游 FETCH_FAILED（含 legacy）。
NO_DRAW_UNAVAILABLE = {
    "twii_exception": snap(None, "OSError", _R("bull")),
    "twii_contract_error": snap(None, CONTRACT_ERROR, _R("bull")),
    "twii_future_as_of": snap(None, FUTURE_AS_OF_ERROR, _R("bull")),
    "twii_failed_fact": snap(twii(ok=False, close=(), as_of=None, failed=True, error_type="OSError", is_stale=None), "", _R("bull")),
    "regime_exception": snap(twii(), "", None, "OSError"),
    "regime_contract_error": snap(twii(), "", None, CONTRACT_ERROR),
    "mixed_twii_ok_regime_unavailable": snap(twii(is_stale=True, age_days=3), "", None, "RuntimeError"),
    "mixed_twii_missing_regime_unavailable": snap(twii(ok=False, close=(), as_of=None, is_stale=None), "", None, "OSError"),
    "both_unavailable": snap(None, "OSError", None, "OSError"),
}
NO_DRAW_UPSTREAM = {
    "fetch_failed": snap(twii(upstream_state="FETCH_FAILED", has_upstream_error=True), "", _R("bull")),
    "fetch_failed_no_flag": snap(twii(upstream_state="FETCH_FAILED"), "", _R("bull")),
    "legacy_empty_state_with_error": snap(twii(upstream_state="", has_upstream_error=True), "", _R("bull")),
    "fetch_failed_and_stale": snap(twii(is_stale=True, age_days=5, upstream_state="FETCH_FAILED", has_upstream_error=True),
                                   "", _R("unloaded")),
    "fetch_failed_and_missing": snap(twii(ok=False, close=(), as_of=None, is_stale=None, upstream_state="FETCH_FAILED",
                                          has_upstream_error=True), "", _R("bull")),
}
NO_DRAW = {**NO_DRAW_UNAVAILABLE, **NO_DRAW_UPSTREAM}
ALL = {**{f"draw:{k}": v for k, v in DRAW.items()}, **{f"skip:{k}": v for k, v in NO_DRAW.items()}}


def market_vm(s) -> PageVM:
    return get_real_page_vm(P4_MARKET, s)


def wired_secs(vm: PageVM) -> list[SectionVM]:
    return [s for s in vm.context.sections if s.section_id == SEC_ID]


def _all_fields(vm: PageVM):
    fs = vm.context.first_screen
    for f in (fs.current_state, fs.action_needed, fs.next_step, fs.conclusion, vm.context.main_risk, vm.context.delta):
        if f is not None:
            yield "first/*", f
    for i, f in enumerate(fs.context_rows):
        yield f"first/context_rows/{i}", f
    for c in vm.context.cards:
        yield f"cards/{c.card_id}", c.field
    for s in vm.context.sections:
        for i, f in enumerate(s.fields):
            yield f"sections/{s.section_id}/{i}", f
    t = vm.context.target
    if t is not None:
        for s in t.lookup.sections:
            for i, f in enumerate(s.fields):
                yield f"lookup/sections/{s.section_id}/{i}", f
        for i, f in enumerate(t.lookup.snapshot):
            yield f"lookup/snapshot/{i}", f


def _looks_like_wired_status(f: FieldVM) -> bool:
    """同形欄位＝label「其中」或 detail＝Q 句，或 label「🗂 資料」配「固定清單」值。
    （🗂 資料頁既有第一屏列的 label 是「資料新鮮度總覽」「接入狀態」，value 同字串但 label 不同，**不是**同形。）"""
    return f.label == LABEL1 or f.detail == Q or (f.label == LABEL0 and (f.value_text or "").startswith("固定清單"))


# ═══════════════════════════ 形狀補償守衛（allowlist 命中會跳過整欄檢查，被跳過的檢查全補在這裡）
def _field_problems(f: FieldVM, *, label: str, value: str, detail: str | None, where: str) -> list[str]:
    bad = []
    if f.label != label:
        bad.append(f"{where}: label {f.label!r} ≠ {label!r}")
    if f.value_text != value:
        bad.append(f"{where}: value {f.value_text!r} ≠ {value!r}")
    if f.detail != detail:
        bad.append(f"{where}: detail {f.detail!r} ≠ {detail!r}")
    if f.state is not FieldState.OK or f.capability is not CapabilityState.PROVIDED:
        bad.append(f"{where}: state/capability 不是 OK＋PROVIDED（{f.state!r}／{f.capability!r}）")
    if f.status_text is not None:
        bad.append(f"{where}: status_text 非空 {f.status_text!r}")
    if f.freshness.source is not None or f.freshness.as_of is not None:
        bad.append(f"{where}: 偷帶 freshness {f.freshness!r}")
    if status_chip_html(f):
        bad.append(f"{where}: 有 chip")
    return bad


def shape_violations(vms: dict[str, PageVM], *, expect_present: bool) -> list[str]:
    """(1) 📊 恰一個 id、L1、位於尾端；(2) 恰 2 欄；(3) 標題＝既有「接入狀態」；(4) `/0` 鎖 label／value／detail None；
    (5) `/1` 鎖 label／value／detail＝Q；(6) 兩欄無 status／freshness／chip／capability；(7) 其他頁／其他 section／其他索引不得出現同形欄位。"""
    bad: list[str] = []
    for page, vm in vms.items():
        for path, f in _all_fields(vm):
            if page == P4_MARKET and path in (f"sections/{SEC_ID}/0", f"sections/{SEC_ID}/1"):
                continue
            if _looks_like_wired_status(f):
                bad.append(f"{page}/{path}: 出現同形欄位（label={f.label!r} value={f.value_text!r}）")
        if page != P4_MARKET and any(s.section_id == SEC_ID for s in vm.context.sections):
            bad.append(f"{page}: 他頁出現 section {SEC_ID}")
    m = vms[P4_MARKET]
    secs = wired_secs(m)
    if not expect_present:
        return bad + ([f"不該畫卻出現 {len(secs)} 個區塊"] if secs else [])
    if len(secs) != 1:
        return bad + [f"📊 {SEC_ID} 區塊數 {len(secs)} ≠ 1"]
    sec = secs[0]
    if sec.level != "L1":
        bad.append(f"level {sec.level!r} ≠ L1")
    if m.context.sections[-1] is not sec:
        bad.append("不在 sections 尾端")
    if sec.title != TITLE:
        bad.append(f"標題 {sec.title!r} ≠ {TITLE!r}")
    if sec.mode is not None:
        bad.append(f"mode {sec.mode!r} 非 None")
    if len(sec.fields) != 2:
        bad.append(f"欄數 {len(sec.fields)} ≠ 2")
        return bad
    bad += _field_problems(sec.fields[0], label=LABEL0, value=VAL0, detail=None, where="/0")
    bad += _field_problems(sec.fields[1], label=LABEL1, value=VAL1, detail=Q, where="/1")
    for i, f in enumerate(sec.fields):
        if f.label.strip() in sec.title:
            bad.append(f"/{i}: label 與標題重複（{f.label!r}）")
    return bad


def _vms(s) -> dict[str, PageVM]:
    return {p: get_real_page_vm(p, s) for p in PAGE_IDS}


def _with_market_sections(vms, fn):
    m = vms[P4_MARKET]
    secs = fn(list(m.context.sections))
    return {**vms, P4_MARKET: dataclasses.replace(m, context=dataclasses.replace(m.context, sections=tuple(secs)))}


def _with_wired_fields(vms, fn):
    def go(secs):
        return [dataclasses.replace(s, fields=tuple(fn(list(s.fields)))) if s.section_id == SEC_ID else s for s in secs]
    return _with_market_sections(vms, go)


# ═══════════════════════════ N1／N2／N3／N6 顯示條件矩陣
@pytest.mark.parametrize("name", sorted(DRAW))
def test_n1_n6_every_drawable_state_draws_exactly_one_correctly_shaped_block(name):
    vms = _vms(DRAW[name])
    assert shape_violations(vms, expect_present=True) == [], name
    # 既有檢查器不改（WIRED_PATHS 只多兩個精確 tuple）：全 Real 組合仍綠
    assert RF.check_only_wired_fields_carry_data(vms) == [], name


@pytest.mark.parametrize("name", sorted(NO_DRAW))
def test_n2_n6_unavailable_and_fetch_failed_states_draw_nothing(name):
    vms = _vms(NO_DRAW[name])
    assert wired_secs(vms[P4_MARKET]) == [], name
    assert shape_violations(vms, expect_present=False) == [], name
    assert RF.check_only_wired_fields_carry_data(vms) == [], name


def test_n6_exact_upstream_rule_reuses_the_card_expression():
    """(b) 僅 `up == UPSTREAM_TEXT_FETCH_FAILED` 隱藏：NO_NEW_DATA／UNDETERMINED／無錯誤照畫；FETCH_FAILED 與 legacy 不畫。
    期望值由本檔以卡片自己的算式獨立算出（⛔ 呼叫 production 的內部旗標）。"""
    from shared.upstream_state import upstream_state_text
    for name, s in {**DRAW, **NO_DRAW_UPSTREAM}.items():
        t = s.twii
        up = upstream_state_text(t.upstream_state) or (UPSTREAM_TEXT_FETCH_FAILED if t.has_upstream_error else "")
        drawn = bool(wired_secs(market_vm(s)))
        assert drawn == (up != UPSTREAM_TEXT_FETCH_FAILED), (name, up, drawn)


def test_n1_normal_gaps_are_drawn_not_hidden():
    """正常缺值（missing／stale／stale_unknown／unevaluated／loaded／unloaded）全部畫；「任何 None／缺值就隱藏」會使本測試紅。"""
    for n in ("missing", "missing_no_date", "stale", "stale_unknown", "unloaded", "breadth_undeterminable", "loaded"):
        assert len(wired_secs(market_vm(DRAW[n]))) == 1, n


def test_n3_dropping_the_unavailable_gate_would_flip_n2(monkeypatch):
    """變異驗證（在測試內做）：把 `freshness_states` 的 unavailable 換成非 unavailable → 該區塊出現，N2 的斷言會紅。"""
    from src.services.ui2 import real_canonical as RC
    s = NO_DRAW_UNAVAILABLE["mixed_twii_ok_regime_unavailable"]       # 台股本身可畫、只有位階 unavailable → 純粹由 unavailable 閘擋下
    assert wired_secs(market_vm(s)) == []
    real_fn = RC.freshness_states
    monkeypatch.setattr(RC, "freshness_states",
                        lambda sn: {k: (DP.S_MISSING if v == DP.S_UNAVAILABLE else v) for k, v in real_fn(sn).items()})
    assert len(wired_secs(market_vm(s))) == 1


def test_only_market_page_of_real_axis_ever_gets_the_block():
    for name, s in DRAW.items():
        for p in PAGE_IDS:
            assert bool(wired_secs(get_real_page_vm(p, s))) == (p == P4_MARKET), (name, p)


# ═══════════════════════════ N4 FAKE 結構上無路徑
@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_n4_fake_pages_never_carry_the_block_and_match_the_p3_baseline_exactly(page, scenario):
    import json
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    for acct in (ACCOUNT_IDS if page == P4_ME else (None,)):
        vm = get_preview_page_vm(page, scenario, account=acct)
        assert wired_secs(vm) == []
        blob = vm_visible_text(vm)
        assert TITLE not in blob and "已接入畫面" not in blob and Q not in blob and LABEL1 not in {f.label for _, f in _all_fields(vm)}
        assert fingerprint(vm) == base[f"fake/{page}/{scenario}/{acct}"], (page, scenario, acct)


# ═══════════════════════════ N8 與 🗂 逐字一致
@pytest.mark.parametrize("name", sorted(DRAW))
def test_n8_market_block_equals_the_data_page_fresh_total_and_fresh_wired_verbatim(name):
    s = DRAW[name]
    sec = wired_secs(market_vm(s))[0]
    data_rows = get_real_page_vm(P4_DATA, s).context.first_screen.context_rows
    assert sec.fields[0].value_text == data_rows[0].value_text == VAL0
    assert sec.fields[1].value_text == data_rows[1].value_text == VAL1
    assert data_rows[0].label == "資料新鮮度總覽" and data_rows[1].label == TITLE     # 既有標籤沒被借走
    assert sec.fields[0].label == LABEL0 == PAGE_LABELS[P4_DATA]


def test_counts_follow_the_fixed_list_when_it_changes(monkeypatch):
    """N 與 K 由 `FRESHNESS_ITEMS` 現算（⛔ 寫死 8／2／6）：把清單暫時加一項未接入項目，📊 的兩個字串跟著變。"""
    items = DP.FRESHNESS_ITEMS + (("extra_unwired", None),)
    monkeypatch.setattr(DP, "FRESHNESS_ITEMS", items)
    s = DRAW["loaded"]
    sec = wired_secs(market_vm(s))[0]
    assert sec.fields[0].value_text == f"固定清單 {len(items)} 項"
    assert sec.fields[1].value_text == f"已接入畫面 {N_WIRED} 項｜尚未提供 {len(items) - N_WIRED} 項"


# ═══════════════════════════ N9 其餘四頁／既有輸出與 base 逐位相同
def _vm_hash(vm: PageVM) -> str:
    return hashlib.sha1(repr(vm).encode("utf-8")).hexdigest()[:16]


#: 在 base（origin/main 2fd0773e）上以同一組 snapshot 計算的 `repr(PageVM)` 雜湊（前 16 碼）。key＝「{snapshot}|{page}」。
#: 📊 的值＝**未含新區塊**的 base VM；實作後以「去掉新區塊」的 VM 比對（見下）。
BASE_HASHES: dict[str, str] = {
    "draw:ambiguous_undeterminable|p4_market": "d85f83e48807ddd8",
    "draw:ambiguous_undeterminable|p4_target": "9b478f5ccf805a53",
    "draw:ambiguous_undeterminable|p4_hold": "e60abdf657e21661",
    "draw:ambiguous_undeterminable|p4_me": "7964a7d44ed0ccd7",
    "draw:ambiguous_undeterminable|p4_data": "6ec638cc3e40cef1",
    "draw:breadth_undeterminable|p4_market": "3931581f13c026c9",
    "draw:breadth_undeterminable|p4_target": "181fbb4353757a39",
    "draw:breadth_undeterminable|p4_hold": "e60abdf657e21661",
    "draw:breadth_undeterminable|p4_me": "7964a7d44ed0ccd7",
    "draw:breadth_undeterminable|p4_data": "e54bfacb8141e33a",
    "draw:empty_upstream_no_error|p4_market": "69fc5c228cdea350",
    "draw:empty_upstream_no_error|p4_target": "9b478f5ccf805a53",
    "draw:empty_upstream_no_error|p4_hold": "e60abdf657e21661",
    "draw:empty_upstream_no_error|p4_me": "7964a7d44ed0ccd7",
    "draw:empty_upstream_no_error|p4_data": "fb586fd826dc46e6",
    "draw:loaded|p4_market": "69fc5c228cdea350",
    "draw:loaded|p4_target": "9b478f5ccf805a53",
    "draw:loaded|p4_hold": "e60abdf657e21661",
    "draw:loaded|p4_me": "7964a7d44ed0ccd7",
    "draw:loaded|p4_data": "fb586fd826dc46e6",
    "draw:missing|p4_market": "b2a8ab7e7f97cfd6",
    "draw:missing|p4_target": "9b478f5ccf805a53",
    "draw:missing|p4_hold": "e60abdf657e21661",
    "draw:missing|p4_me": "7964a7d44ed0ccd7",
    "draw:missing|p4_data": "3834ed2aef0595ed",
    "draw:missing_no_date|p4_market": "5716cf8f1f5b08f8",
    "draw:missing_no_date|p4_target": "9b478f5ccf805a53",
    "draw:missing_no_date|p4_hold": "e60abdf657e21661",
    "draw:missing_no_date|p4_me": "7964a7d44ed0ccd7",
    "draw:missing_no_date|p4_data": "3834ed2aef0595ed",
    "draw:no_new_data|p4_market": "0a29fa176bcf9957",
    "draw:no_new_data|p4_target": "9b478f5ccf805a53",
    "draw:no_new_data|p4_hold": "e60abdf657e21661",
    "draw:no_new_data|p4_me": "7964a7d44ed0ccd7",
    "draw:no_new_data|p4_data": "fb586fd826dc46e6",
    "draw:no_new_data_with_error_flag|p4_market": "0a29fa176bcf9957",
    "draw:no_new_data_with_error_flag|p4_target": "9b478f5ccf805a53",
    "draw:no_new_data_with_error_flag|p4_hold": "e60abdf657e21661",
    "draw:no_new_data_with_error_flag|p4_me": "7964a7d44ed0ccd7",
    "draw:no_new_data_with_error_flag|p4_data": "fb586fd826dc46e6",
    "draw:stale|p4_market": "720d3e07d3d2be39",
    "draw:stale|p4_target": "f9244552097e9153",
    "draw:stale|p4_hold": "e60abdf657e21661",
    "draw:stale|p4_me": "7964a7d44ed0ccd7",
    "draw:stale|p4_data": "e022917ca8a7673d",
    "draw:stale_unknown|p4_market": "41c967a74195ca1c",
    "draw:stale_unknown|p4_target": "f9244552097e9153",
    "draw:stale_unknown|p4_hold": "e60abdf657e21661",
    "draw:stale_unknown|p4_me": "7964a7d44ed0ccd7",
    "draw:stale_unknown|p4_data": "be0134d54c0b665c",
    "draw:undetermined|p4_market": "2368f705916d8adc",
    "draw:undetermined|p4_target": "9b478f5ccf805a53",
    "draw:undetermined|p4_hold": "e60abdf657e21661",
    "draw:undetermined|p4_me": "7964a7d44ed0ccd7",
    "draw:undetermined|p4_data": "fb586fd826dc46e6",
    "draw:unloaded|p4_market": "f42bc50500cd070e",
    "draw:unloaded|p4_target": "f9244552097e9153",
    "draw:unloaded|p4_hold": "e60abdf657e21661",
    "draw:unloaded|p4_me": "7964a7d44ed0ccd7",
    "draw:unloaded|p4_data": "264cad281b6aa885",
    "skip:both_unavailable|p4_market": "65608f259643f1ad",
    "skip:both_unavailable|p4_target": "6e276b26584d1823",
    "skip:both_unavailable|p4_hold": "e60abdf657e21661",
    "skip:both_unavailable|p4_me": "7964a7d44ed0ccd7",
    "skip:both_unavailable|p4_data": "7f8342da57952b0c",
    "skip:fetch_failed|p4_market": "c57748b66baeae88",
    "skip:fetch_failed|p4_target": "9b478f5ccf805a53",
    "skip:fetch_failed|p4_hold": "e60abdf657e21661",
    "skip:fetch_failed|p4_me": "7964a7d44ed0ccd7",
    "skip:fetch_failed|p4_data": "68147486fb4d363d",
    "skip:fetch_failed_and_missing|p4_market": "b2a8ab7e7f97cfd6",
    "skip:fetch_failed_and_missing|p4_target": "9b478f5ccf805a53",
    "skip:fetch_failed_and_missing|p4_hold": "e60abdf657e21661",
    "skip:fetch_failed_and_missing|p4_me": "7964a7d44ed0ccd7",
    "skip:fetch_failed_and_missing|p4_data": "3834ed2aef0595ed",
    "skip:fetch_failed_and_stale|p4_market": "a7f6e95210665d51",
    "skip:fetch_failed_and_stale|p4_target": "f9244552097e9153",
    "skip:fetch_failed_and_stale|p4_hold": "e60abdf657e21661",
    "skip:fetch_failed_and_stale|p4_me": "7964a7d44ed0ccd7",
    "skip:fetch_failed_and_stale|p4_data": "c21528f5642b9154",
    "skip:fetch_failed_no_flag|p4_market": "c57748b66baeae88",
    "skip:fetch_failed_no_flag|p4_target": "9b478f5ccf805a53",
    "skip:fetch_failed_no_flag|p4_hold": "e60abdf657e21661",
    "skip:fetch_failed_no_flag|p4_me": "7964a7d44ed0ccd7",
    "skip:fetch_failed_no_flag|p4_data": "68147486fb4d363d",
    "skip:legacy_empty_state_with_error|p4_market": "c57748b66baeae88",
    "skip:legacy_empty_state_with_error|p4_target": "9b478f5ccf805a53",
    "skip:legacy_empty_state_with_error|p4_hold": "e60abdf657e21661",
    "skip:legacy_empty_state_with_error|p4_me": "7964a7d44ed0ccd7",
    "skip:legacy_empty_state_with_error|p4_data": "68147486fb4d363d",
    "skip:mixed_twii_missing_regime_unavailable|p4_market": "e31e4caab2854e2e",
    "skip:mixed_twii_missing_regime_unavailable|p4_target": "6e276b26584d1823",
    "skip:mixed_twii_missing_regime_unavailable|p4_hold": "e60abdf657e21661",
    "skip:mixed_twii_missing_regime_unavailable|p4_me": "7964a7d44ed0ccd7",
    "skip:mixed_twii_missing_regime_unavailable|p4_data": "0cd1f5da2215d1d3",
    "skip:mixed_twii_ok_regime_unavailable|p4_market": "9268c277241e7fda",
    "skip:mixed_twii_ok_regime_unavailable|p4_target": "6e276b26584d1823",
    "skip:mixed_twii_ok_regime_unavailable|p4_hold": "e60abdf657e21661",
    "skip:mixed_twii_ok_regime_unavailable|p4_me": "7964a7d44ed0ccd7",
    "skip:mixed_twii_ok_regime_unavailable|p4_data": "f7b0f77ac1d3943f",
    "skip:regime_contract_error|p4_market": "d53ce4641b42e90c",
    "skip:regime_contract_error|p4_target": "2899740e67ed17d8",
    "skip:regime_contract_error|p4_hold": "e60abdf657e21661",
    "skip:regime_contract_error|p4_me": "7964a7d44ed0ccd7",
    "skip:regime_contract_error|p4_data": "84a68272d81fc73c",
    "skip:regime_exception|p4_market": "733f2d84f1c97596",
    "skip:regime_exception|p4_target": "6e276b26584d1823",
    "skip:regime_exception|p4_hold": "e60abdf657e21661",
    "skip:regime_exception|p4_me": "7964a7d44ed0ccd7",
    "skip:regime_exception|p4_data": "84a68272d81fc73c",
    "skip:twii_contract_error|p4_market": "04c8143a88f9b404",
    "skip:twii_contract_error|p4_target": "9b478f5ccf805a53",
    "skip:twii_contract_error|p4_hold": "e60abdf657e21661",
    "skip:twii_contract_error|p4_me": "7964a7d44ed0ccd7",
    "skip:twii_contract_error|p4_data": "8af7abef76ead3ff",
    "skip:twii_exception|p4_market": "b404e96007079e00",
    "skip:twii_exception|p4_target": "9b478f5ccf805a53",
    "skip:twii_exception|p4_hold": "e60abdf657e21661",
    "skip:twii_exception|p4_me": "7964a7d44ed0ccd7",
    "skip:twii_exception|p4_data": "8af7abef76ead3ff",
    "skip:twii_failed_fact|p4_market": "f76cbc9fe6a77109",
    "skip:twii_failed_fact|p4_target": "9b478f5ccf805a53",
    "skip:twii_failed_fact|p4_hold": "e60abdf657e21661",
    "skip:twii_failed_fact|p4_me": "7964a7d44ed0ccd7",
    "skip:twii_failed_fact|p4_data": "8af7abef76ead3ff",
    "skip:twii_future_as_of|p4_market": "f759d4443b35d4f9",
    "skip:twii_future_as_of|p4_target": "9b478f5ccf805a53",
    "skip:twii_future_as_of|p4_hold": "e60abdf657e21661",
    "skip:twii_future_as_of|p4_me": "7964a7d44ed0ccd7",
    "skip:twii_future_as_of|p4_data": "8af7abef76ead3ff",
}


@pytest.mark.parametrize("name", sorted(ALL))
def test_n9_other_four_pages_and_market_minus_the_block_are_bit_identical_to_base(name):
    s = ALL[name]
    for p in PAGE_IDS:
        vm = get_real_page_vm(p, s)
        if p == P4_MARKET:
            vm = dataclasses.replace(vm, context=dataclasses.replace(
                vm.context, sections=tuple(x for x in vm.context.sections if x.section_id != SEC_ID)))
        assert _vm_hash(vm) == BASE_HASHES[f"{name}|{p}"], (name, p)


# ═══════════════════════════ N5 識別字 production 只准出現在 real_canonical.py
ALLOWED_PROD = "src/services/ui2/real_canonical.py"
_ID_TOKENS = ("market_wired_status", "WIRED_STATUS_", "已接入只表示畫面已有讀取路徑")


def scan_production(root: Path) -> list[str]:
    hits = []
    files = [*root.glob("src/**/*.py"), *root.glob("shared/**/*.py"), *root.glob("app*.py")]
    for p in files:
        rel = p.relative_to(root).as_posix()
        if rel == ALLOWED_PROD:
            continue
        txt = p.read_text(encoding="utf-8")
        if any(tok in txt for tok in _ID_TOKENS):
            hits.append(rel)
    return sorted(hits)


def test_n5_identifiers_live_only_in_real_canonical_in_the_real_repo():
    assert scan_production(ROOT) == []
    own = (ROOT / ALLOWED_PROD).read_text(encoding="utf-8")
    assert all(tok in own for tok in _ID_TOKENS), "守衛空轉：real_canonical.py 內找不到識別字"


@pytest.mark.parametrize("rel", [
    "src/services/ui2/scenarios.py", "src/services/ui2/vm_common.py", "src/services/ui2/preview_feed.py",
    "src/services/ui2/market_vm.py", "src/services/ui2/skeleton_vm.py", "src/services/ui2/real_feed.py",
    "src/ui2/views/market.py", "src/ui2/views/_page.py", "src/ui2/shell/app.py", "src/ui2/components/html.py",
    "shared/ui2_contract/models.py", "app_ui2.py", "app.py",
])
@pytest.mark.parametrize("token", _ID_TOKENS)
def test_n5_guard_has_teeth_injecting_an_identifier_anywhere_else_turns_red(tmp_path, rel, token):
    f = tmp_path / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f'X = "{token}"\n', encoding="utf-8")
    assert scan_production(tmp_path) == [rel]
    ok = tmp_path / ALLOWED_PROD
    ok.parent.mkdir(parents=True, exist_ok=True)
    ok.write_text(f'X = "{token}"\n', encoding="utf-8")
    assert scan_production(tmp_path) == [rel]          # 允許檔不被報；其他檔仍被報


_TEST_ALLOWED = {
    "tests/test_ui2_market_wired_status.py",
    "tests/test_ui2_real_feed.py",                      # 只准 WIRED_PATHS 內兩個精確 tuple
    "tests/test_ui2_data_freshness_items_w3p1.py",      # 既有精確集合測試：只讀引用
    "tests/test_ui2_data_freshness_overview.py",        # 既有精確集合測試：只讀引用
    "tests/test_ui2_digest_excerpt_parity.py",          # 既有「逐值相等於 baseline」測試：只 import 本檔 SEC_ID 常數剪掉該區塊再比對（只讀）
}
def test_n5_test_side_references_are_limited_to_the_approved_places():
    import ast
    seen = set()
    for p in (ROOT / "tests").rglob("*.py"):
        if "market_wired_status" in p.read_text(encoding="utf-8"):
            seen.add(p.relative_to(ROOT).as_posix())
    assert seen <= _TEST_ALLOWED, sorted(seen - _TEST_ALLOWED)
    # test_ui2_real_feed.py：該識別字只准出現在 `WIRED_PATHS` 這個 frozenset 字面值內的兩個精確 tuple（⛔ 其他引用／產生 VM）
    src = (ROOT / "tests/test_ui2_real_feed.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    wp = next(n for n in tree.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "WIRED_PATHS" for t in n.targets))
    inside = {(c.lineno, c.value) for c in ast.walk(wp.value) if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    mine_inside = sorted(v for _, v in inside if "market_wired_status" in v)
    assert mine_inside == [f"sections/{SEC_ID}/0", f"sections/{SEC_ID}/1"], mine_inside
    every = [c for c in ast.walk(tree) if isinstance(c, ast.Constant) and isinstance(c.value, str) and "market_wired_status" in c.value]
    assert len(every) == 2, [c.lineno for c in every]
    tuples = [t for t in ast.walk(wp.value) if isinstance(t, ast.Tuple) and len(t.elts) == 2
              and isinstance(t.elts[1], ast.Constant) and "market_wired_status" in str(t.elts[1].value)]
    assert len(tuples) == 2 and all(isinstance(t.elts[0], ast.Name) and t.elts[0].id == "P4_MARKET" for t in tuples)


# ═══════════════════════════ N11／N10 文案掃描與無 expander
def test_n11_new_strings_pass_engineering_vocab_and_shown_scans():
    for txt in (LABEL1, Q, VAL0, VAL1, LABEL0, TITLE):
        assert [w for w in ENGINEERING_VOCAB if w in txt] == [], txt
        assert hits_in(txt) == [], txt
        assert not re.search(r"DEC-\d+|`|macro_state\.json", txt), txt
    assert shown(Q) is True                      # Q 句真的會畫（沒被當成治理參照句吞掉）
    from src.services.ui2 import real_canonical as RC
    assert (RC.WIRED_STATUS_DETAIL, RC.WIRED_STATUS_LABEL) == (Q, LABEL1)     # production 常數＝本檔逐字
    assert RC.WIRED_STATUS_SECTION_ID == SEC_ID


@pytest.mark.parametrize("name", sorted(DRAW))
def test_n11_vm_visible_text_of_the_market_page_has_no_engineering_words(name):
    assert hits_in(vm_visible_text(market_vm(DRAW[name]))) == []


def test_n10_no_expander_and_shown_folds_unchanged():
    assert _page.SHOWN_FOLDS == EXPECTED_SHOWN_FOLDS and len(_page.SHOWN_FOLDS) == 4
    assert (P4_MARKET, SEC_ID) not in _page.SHOWN_FOLDS


# ═══════════════════════════ 形狀補償守衛的負控
def _good():
    return _vms(DRAW["loaded"])


def test_shape_guard_accepts_the_real_thing_and_rejects_every_mutation():
    assert shape_violations(_good(), expect_present=True) == []

    def wired(vms):
        return wired_secs(vms[P4_MARKET])[0]

    def sec_swap(vms, **kw):
        return _with_market_sections(vms, lambda secs: [dataclasses.replace(s, **kw) if s.section_id == SEC_ID else s for s in secs])

    f0 = lambda v: wired(v).fields[0]    # noqa: E731
    f1 = lambda v: wired(v).fields[1]    # noqa: E731
    cases = {
        "多一列(/2)": lambda v: _with_wired_fields(v, lambda fs: [*fs, fs[1]]),
        "少一列": lambda v: _with_wired_fields(v, lambda fs: fs[:1]),
        "/2 帶 Q 句": lambda v: _with_wired_fields(v, lambda fs: [*fs, dataclasses.replace(fs[0], label="第三列", detail=Q)]),
        "/0 帶 detail（Q）": lambda v: _with_wired_fields(v, lambda fs: [dataclasses.replace(fs[0], detail=Q), fs[1]]),
        "/0 帶 detail（任意字串）": lambda v: _with_wired_fields(v, lambda fs: [dataclasses.replace(fs[0], detail="x"), fs[1]]),
        "/1 detail 改字": lambda v: _with_wired_fields(v, lambda fs: [fs[0], dataclasses.replace(fs[1], detail=Q + "。")]),
        "/1 detail 缺": lambda v: _with_wired_fields(v, lambda fs: [fs[0], dataclasses.replace(fs[1], detail=None)]),
        "/0 value 改字": lambda v: _with_wired_fields(v, lambda fs: [dataclasses.replace(fs[0], value_text="固定清單 9 項"), fs[1]]),
        "/1 value 改字": lambda v: _with_wired_fields(v, lambda fs: [fs[0], dataclasses.replace(fs[1], value_text="已接入畫面 3 項｜尚未提供 5 項")]),
        "/1 label 改字": lambda v: _with_wired_fields(v, lambda fs: [fs[0], dataclasses.replace(fs[1], label="其中的")]),
        "/0 label 等於標題": lambda v: _with_wired_fields(v, lambda fs: [dataclasses.replace(fs[0], label=TITLE), fs[1]]),
        "/1 label 等於標題": lambda v: _with_wired_fields(v, lambda fs: [fs[0], dataclasses.replace(fs[1], label=TITLE)]),
        "偷帶 freshness.source": lambda v: _with_wired_fields(v, lambda fs: [dataclasses.replace(fs[0], freshness=FreshnessInfo(source="X")), fs[1]]),
        "偷帶 freshness.as_of": lambda v: _with_wired_fields(v, lambda fs: [fs[0], dataclasses.replace(fs[1], freshness=FreshnessInfo(as_of="2026-11-13"))]),
        "偷帶 chip（stale）": lambda v: _with_wired_fields(v, lambda fs: [dataclasses.replace(fs[0], state=FieldState.STALE, status_text=T.stale_text(3)), fs[1]]),
        "capability 改 NOT_PROVIDED": lambda v: _with_wired_fields(v, lambda fs: [fs[0], FieldVM(LABEL1, None, None, T.TEXT_NOT_PROVIDED, Q, capability=CapabilityState.NOT_PROVIDED)]),
        "level 改 L2": lambda v: sec_swap(v, level="L2"),
        "標題改字": lambda v: sec_swap(v, title="接入狀態說明"),
        "section id 改名（≠恰一個）": lambda v: sec_swap(v, section_id="market_wired_status_x"),
        "不在尾端": lambda v: _with_market_sections(v, lambda secs: [secs[-1], *secs[:-1]]),
        "重複區塊": lambda v: _with_market_sections(v, lambda secs: [*secs, secs[-1]]),
        "別頁(💼)出現同 section": lambda v: {**v, P4_HOLD: dataclasses.replace(v[P4_HOLD], context=dataclasses.replace(
            v[P4_HOLD].context, sections=(*v[P4_HOLD].context.sections, wired(v))))},
        "別頁(🗂)首屏出現同形欄位": lambda v: {**v, P4_DATA: dataclasses.replace(v[P4_DATA], context=dataclasses.replace(
            v[P4_DATA].context, first_screen=dataclasses.replace(
                v[P4_DATA].context.first_screen,
                context_rows=(*v[P4_DATA].context.first_screen.context_rows, f1(v)))))},
        "📊 其他 section 出現同形欄位": lambda v: _with_market_sections(v, lambda secs: [
            dataclasses.replace(secs[0], fields=(*secs[0].fields, f1(v))), *secs[1:]]),
        "📊 卡片換成同形欄位": lambda v: {**v, P4_MARKET: dataclasses.replace(v[P4_MARKET], context=dataclasses.replace(
            v[P4_MARKET].context, cards=(dataclasses.replace(v[P4_MARKET].context.cards[0], field=f1(v)),
                                         *v[P4_MARKET].context.cards[1:])))},
    }
    for what, mut in cases.items():
        assert shape_violations(mut(_good()), expect_present=True), what
    assert f0(_good()).label == LABEL0 and f1(_good()).label == LABEL1


def test_shape_guard_rejects_a_block_that_should_not_be_drawn():
    ok = _vms(DRAW["loaded"])
    assert shape_violations(ok, expect_present=False)          # 該畫的態卻被要求「不該畫」→ 守衛要能抓到
    assert shape_violations(_vms(NO_DRAW["both_unavailable"]), expect_present=False) == []


# ═══════════════════════════ AppTest（真 shell；Real 注入 snapshot）
def _real_at(monkeypatch, s, *, page=P4_MARKET):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr("src.ui2.shell.app.read_real_snapshot", lambda: s)
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    a.session_state["ui2_feed"] = "real"
    a.run(timeout=60)
    if page != P4_MARKET:
        a.radio(key="ui2_page").set_value(page).run(timeout=60)
    assert not a.exception, a.exception
    return a


def _blob(at) -> str:
    return "\n".join(m.value for m in at.markdown)


_DOM_ANCHORS = ('class="ui2-primary-slot"', 'data-ui2-delta="1"', 'class="ui2-grid"', 'class="ui2-m-onebrain"')


@pytest.mark.parametrize("name", ["loaded", "missing", "stale", "unloaded", "no_new_data", "undetermined"])
def test_n7_n10_dom_order_and_exactly_one_title_in_the_rendered_market_page(monkeypatch, name):
    at = _real_at(monkeypatch, DRAW[name])
    md = [m.value for m in at.markdown]
    blob = "\n".join(md)
    assert T.REAL_PREVIEW_BANNER_TEXT in blob, "沒有走 Real 道（snapshot 注入失效）"
    assert blob.count(TITLE) == 1                                  # N7（SF-B1）：「接入狀態」只在標題出現一次
    assert blob.count(Q) == 1 and blob.count(VAL0) == 1 and blob.count(VAL1) == 1
    assert blob.count(f'class="ui2-row__label">{LABEL1}<') == 1 and blob.count(f'class="ui2-row__label">{LABEL0}<') == 1
    # DOM 順序：新區塊在 主圖槽／今日變化／核心指標卡／OneBrain 之後；且每個錨點恰 1 次
    pos = []
    for a in _DOM_ANCHORS:
        assert blob.count(a) == 1, a
        pos.append(blob.index(a))
    assert pos == sorted(pos)
    new = blob.index(f'class="ui2-section-title">{TITLE}<')
    assert new > max(pos)
    assert at.expander == []                                       # N10
    assert [e.label for e in at.expander] == []


def test_dom_everything_else_is_bit_identical_to_the_feature_switched_off(monkeypatch):
    """既有錨點與輸出與 base 逐位相同：只把新區塊那一個 markdown 元素拿掉，其餘與「關掉該功能」的渲染逐元素相等。"""
    from src.services.ui2 import real_canonical as RC
    s = DRAW["loaded"]
    on = [m.value for m in _real_at(monkeypatch, s).markdown]
    with monkeypatch.context() as mp:
        mp.setattr(RC, "freshness_states", lambda sn: {"twii": DP.S_UNAVAILABLE, "regime": DP.S_UNAVAILABLE})
        off = [m.value for m in _real_at(mp, s).markdown]
    extra = [i for i, v in enumerate(on) if f'class="ui2-section-title">{TITLE}<' in v]
    assert len(extra) == 1
    assert [v for i, v in enumerate(on) if i != extra[0]] == off
    assert not any(TITLE in v and "ui2-section-title" in v for v in off)


@pytest.mark.parametrize("name", ["twii_exception", "regime_exception", "mixed_twii_ok_regime_unavailable", "both_unavailable",
                                  "fetch_failed", "legacy_empty_state_with_error"])
def test_n2_n6_rendered_market_page_has_no_block_for_unavailable_and_fetch_failed(monkeypatch, name):
    blob = _blob(_real_at(monkeypatch, NO_DRAW[name]))
    assert TITLE not in blob and Q not in blob and "已接入畫面" not in blob and VAL0 not in blob


def test_n2_real_degraded_shell_draws_no_block(monkeypatch):
    """Real degraded（`read_real_snapshot` 整體 raise；shell 以全 None＋『Exception』snapshot 進來）→ 無該列（真 shell AppTest）。"""
    from streamlit.testing.v1 import AppTest
    RF._boom_shell(monkeypatch)
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    a.query_params["ui2_dev"] = "1"
    a.run(timeout=60)
    a.selectbox(key="ui2_feed").set_value("real").run(timeout=60)
    a.radio(key="ui2_page").set_value(P4_MARKET).run(timeout=60)
    blob = _blob(a)
    assert not a.exception
    assert T.REAL_PREVIEW_BANNER_TEXT in blob and 'data-ui2-degraded="1"' in blob, "沒有走降級路徑"
    assert TITLE not in blob and Q not in blob and "已接入畫面" not in blob and LABEL1 not in blob


def test_n4_fake_rendered_market_page_has_no_block(monkeypatch):
    from streamlit.testing.v1 import AppTest
    for sc in ("loaded", "missing", "unavailable"):
        a = AppTest.from_file(str(APP_UI2), default_timeout=60)
        a.session_state["ui2_feed"] = "fake"
        a.session_state["ui2_scenario"] = sc
        a.run(timeout=60)
        a.radio(key="ui2_page").set_value(P4_MARKET).run(timeout=60)
        blob = _blob(a)
        assert TITLE not in blob and Q not in blob and "已接入畫面" not in blob


def test_n8_rendered_market_and_data_pages_show_the_same_two_strings(monkeypatch):
    s = DRAW["stale"]
    m = _blob(_real_at(monkeypatch, s))
    d = _blob(_real_at(monkeypatch, s, page=P4_DATA))
    for v in (VAL0, VAL1):
        assert v in m and v in d
