"""New UI2 UI Correction P3 —— 「Human UI 不渲染 L2/L3 evidence，但 VM／Evidence 一字不丟」的雙向守衛。

出處：客戶 2026-11-03 (17)（DEC-131，A2 裁示）；Active Presentation Contract §3／§8；BACKLOG §5.1.26 P3。

**T_new_1b 規格錯誤（修正，非放寬）**：舊 T_new_1b 要求「三個投資頁 `PageVM.context.sections` 不得有 L2／L3 level」。
該斷言與 Active Contract §8（UI VM＝Human UI 全量、evidence 完整保留、只是不渲染）直接矛盾——它把
「Human UI 不渲染」錯誤地實作成「VM 不得含」，照做就必須**刪掉 evidence**（違反 §1／§8 與 DEC-129 §四〔「從 UI 移除 ≠ 刪資料」〕）。
正確的驗收對象有兩個，且**缺一不可**，都在本檔：
  (A) 渲染層：三個投資主頁不渲染 L2／L3 evidence expander（`test_T_new_1` 在 teeth 檔，這裡補全場景×Real×DOM 對映）；
  (B) VM 層：`PageVM`／`PageContext.sections`／lookup sections 仍完整保存 evidence（baseline 比對，防止被刪空）。
外加 (C) Digest 輸入不依賴 UI2 渲染（import 守衛）。

baseline（`tests/fixtures/ui2_p3_evidence_baseline.json`）＝P3 當下 FAKE 六場景×四頁（👤 三帳戶）＋ Real 固定 snapshot 九態×四頁
的 evidence 指紋（section id／level／title、每欄 label／語意軸／state／是否有 detail／來源／資料日／判定字樣）。
比對規則：**baseline 內每個 section／欄位都必須仍在、指紋不變**；新增 section／欄位 OK。
📌 QA 修正（擴大鎖定，不是縮小）：指紋原先只記 `bool(detail)`／`bool(value_text)`，evidence **內文被偷換**（detail 改成 "x"）測不到。
現改為同時記 `sha1(detail)`、`sha1(value_text)`、`sha1(status_text)`（全欄位），並把 `first_screen`（現況／行動／下一步／今日結論）與 `cards`
也納入；section title／欄位 label 本就以明文逐字鎖定（比雜湊更嚴）。因此**任何文案調整都會讓 baseline 紅**——這是刻意的：改了 evidence 就得
有意識地重新產生 baseline（見下）。baseline 檔本身的 sha256 另釘在 `tests/test_ui2_active_contract_docs.py`（防無聲洗白）。
⚠ 日後要改 evidence（例如 P2 把某欄由「尚未提供」改成真資料）＝有意識的變更：重新產生 baseline
（`python -m tests.test_ui2_p3_evidence_preservation --regen`），**再**把新檔的 sha256 更新到 `tests/test_ui2_active_contract_docs.py::_P3_BASELINE_SHA256`，並在 PR 描述說明；**不得為了讓測試通過而縮小 evidence**。
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import re
import sys
from pathlib import Path

import pytest

from shared import regime_arbiter as RA
from shared.ui2_contract import text as T
from shared.ui2_contract.models import CapabilityState, FieldState, FieldVM, JudgementState, PageVM
from shared.ui2_contract.pages import (
    ACCOUNT_IDS, MODE_LOOKUP, P4_HOLD, P4_MARKET, P4_ME, P4_TARGET, PAGE_IDS, SCENARIO_IDS,
)
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import get_real_page_vm
from src.ui2.views import _page

ROOT = Path(__file__).resolve().parent.parent
APP_UI2 = ROOT / "app_ui2.py"
BASELINE = ROOT / "tests" / "fixtures" / "ui2_p3_evidence_baseline.json"

#: 客戶核准保留的 L2／L3 expander（獨立於被測的 `_page.SHOWN_FOLDS`，避免 mutation 時檢查器跟著被改）。
EXPECTED_SHOWN_FOLDS = frozenset({("p4_target", "conditions"), ("p4_me", "digest"), ("p4_me", "registry")})

#: 舊 T_new_1b 的原文（保留供追溯；已被本檔取代，見檔頭）。
OLD_T_NEW_1B_ASSERTION = '[s.section_id for s in vm.context.sections if s.level in ("L2", "L3")] == []'


# ══════════════════════════════════════════════════════════════════ 指紋
def _h(x: str | None) -> str | None:
    return None if x is None else hashlib.sha1(x.encode("utf-8")).hexdigest()


def _ff(f: FieldVM) -> list:
    return [f.label, f.layer, f.state.value if f.state is not None else None,
            bool(f.detail), bool(f.value_text),
            f.freshness.source, f.freshness.as_of,
            f.status_text if f.layer == "judgement" else None,      # 判定字樣（Risk Cap「⬜ 無法判定」）逐字鎖
            _h(f.detail), _h(f.value_text), _h(f.status_text)]      # 內文雜湊（QA 修正：擴大鎖定）


def _sec(s) -> dict:
    return {"level": s.level, "title": s.title, "mode": s.mode, "fields": [_ff(f) for f in s.fields]}


def fingerprint(vm: PageVM) -> dict:
    ctx = vm.context
    lookup = {} if ctx.target is None else {s.section_id: _sec(s) for s in ctx.target.lookup.sections}
    return {"sections": {s.section_id: _sec(s) for s in ctx.sections},
            "lookup_sections": lookup,
            "context_rows": [_ff(f) for f in ctx.first_screen.context_rows],
            "first_screen": [_ff(f) for f in (ctx.first_screen.current_state, ctx.first_screen.action_needed,
                                              ctx.first_screen.next_step, ctx.first_screen.conclusion) if f is not None],
            "cards": [[c.card_id, c.title, *_ff(c.field)] for c in ctx.cards]}


def _snapshots():
    from tests.test_ui2_p1_human_text import _snapshots as snaps
    return snaps()


def all_vms() -> dict[str, PageVM]:
    out: dict[str, PageVM] = {}
    for page in PAGE_IDS:
        for sc in SCENARIO_IDS:
            for acct in (ACCOUNT_IDS if page == P4_ME else (None,)):
                out[f"fake/{page}/{sc}/{acct}"] = get_preview_page_vm(page, sc, account=acct)
    for name, snap in _snapshots().items():
        for page in PAGE_IDS:
            out[f"real/{page}/{name}"] = get_real_page_vm(page, snap)
    return out


def build_baseline() -> dict:
    return {k: fingerprint(v) for k, v in all_vms().items()}


def compare(base: dict, cur: dict) -> list[str]:
    """baseline 內每個 evidence 都必須仍在且指紋不變；新增 OK。回傳違規描述。"""
    bad: list[str] = []
    for kind in ("sections", "lookup_sections"):
        for sid, b in base[kind].items():
            c = cur[kind].get(sid)
            if c is None:
                bad.append(f"{kind}/{sid}: section 消失")
                continue
            for k in ("level", "title", "mode"):
                if c[k] != b[k]:
                    bad.append(f"{kind}/{sid}.{k}: {b[k]!r} → {c[k]!r}")
            if len(c["fields"]) < len(b["fields"]):
                bad.append(f"{kind}/{sid}: 欄位 {len(b['fields'])} → {len(c['fields'])}（被刪）")
            for i, (bf, cf) in enumerate(zip(b["fields"], c["fields"])):
                if bf != cf:
                    bad.append(f"{kind}/{sid}[{i}] {bf[0]}: {bf} → {cf}")
    for kind in ("context_rows", "first_screen", "cards"):
        if len(cur[kind]) < len(base[kind]):
            bad.append(f"{kind}: 列數減少")
        for i, (bf, cf) in enumerate(zip(base[kind], cur[kind])):
            if bf != cf:
                bad.append(f"{kind}[{i}] {bf[0]}: {bf} → {cf}")
    return bad


def _load_baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════ (B) VM evidence 保存
def test_baseline_covers_every_page_scenario_and_real_state():
    base = _load_baseline()
    assert set(base) == set(all_vms()), sorted(set(base) ^ set(all_vms()))[:10]
    # 基準本身要有東西：每個 fake 市場／標的／持股場景都有 L2／L3 evidence section（不是空基準）
    for k, v in base.items():
        if k.startswith(("fake/p4_market", "fake/p4_target", "fake/p4_hold", "real/p4_market", "real/p4_hold")):
            assert any(s["level"] in ("L2", "L3") for s in v["sections"].values()), k
    assert any(b["lookup_sections"] for k, b in base.items() if k.startswith("fake/p4_target"))


@pytest.mark.parametrize("key", sorted(all_vms()))
def test_vm_evidence_is_fully_preserved_against_the_baseline(key):
    assert compare(_load_baseline()[key], fingerprint(all_vms()[key])) == []


def test_every_investment_page_vm_still_carries_l2_l3_evidence_sections():
    """正向對照：舊 T_new_1b 要求這些頁**沒有** L2／L3——規格錯誤；現行規格要求它們**仍然有**（evidence 保留）。"""
    for page in (P4_MARKET, P4_TARGET, P4_HOLD):
        for vm in (get_preview_page_vm(page, "loaded"), get_real_page_vm(page, _snapshots()["loaded"])):
            assert [s.section_id for s in vm.context.sections if s.level in ("L2", "L3")], page
    assert {"why", "detail", "raw"} <= {s.section_id for s in get_preview_page_vm(P4_MARKET, "loaded").context.sections}
    assert {"lk_fundamental", "lk_valuation", "lk_research"} <= {
        s.section_id for s in get_preview_page_vm(P4_TARGET, "loaded").context.target.lookup.sections}


def _mut_empty_sections(vm):
    c = vm.context
    return dataclasses.replace(vm, context=dataclasses.replace(
        c, sections=tuple(dataclasses.replace(s, fields=()) for s in c.sections)))


def _mut_drop_l23(vm):
    c = vm.context
    return dataclasses.replace(vm, context=dataclasses.replace(
        c, sections=tuple(s for s in c.sections if s.level == "L1")))


def _mut_no_detail(vm):
    c = vm.context
    return dataclasses.replace(vm, context=dataclasses.replace(c, sections=tuple(
        dataclasses.replace(s, fields=tuple(dataclasses.replace(f, detail=None) for f in s.fields))
        for s in c.sections)))


def _mut_no_freshness(vm):
    from shared.ui2_contract.models import FreshnessInfo
    c = vm.context
    return dataclasses.replace(vm, context=dataclasses.replace(c, sections=tuple(
        dataclasses.replace(s, fields=tuple(dataclasses.replace(f, freshness=FreshnessInfo()) for f in s.fields))
        for s in c.sections)))


def _mut_detail_x(vm):
    """內文被偷換：detail 全改成 "x"（仍有 detail，bool 指紋看不出）。"""
    c = vm.context
    return dataclasses.replace(vm, context=dataclasses.replace(c, sections=tuple(
        dataclasses.replace(s, fields=tuple(dataclasses.replace(f, detail="x" if f.detail else None) for f in s.fields))
        for s in c.sections)))


def _mut_value_x(vm):
    """value_text 被偷換成 "x"（卡片與第一屏現況）。"""
    c = vm.context
    cards = tuple(dataclasses.replace(k, field=dataclasses.replace(k.field, value_text="x")
                                      if k.field.value_text else k.field) for k in c.cards)
    fs = c.first_screen
    cs = dataclasses.replace(fs.current_state, value_text="x") if fs.current_state.value_text else fs.current_state
    return dataclasses.replace(vm, context=dataclasses.replace(
        c, cards=cards, first_screen=dataclasses.replace(fs, current_state=cs)))


def _mut_title_swapped(vm):
    c = vm.context
    return dataclasses.replace(vm, context=dataclasses.replace(c, sections=tuple(
        dataclasses.replace(s, title=s.title + "（改）") for s in c.sections)))


def _mut_no_lookup_sections(vm):
    t = vm.context.target
    t2 = dataclasses.replace(t, lookup=dataclasses.replace(t.lookup, sections=()))
    return dataclasses.replace(vm, context=dataclasses.replace(vm.context, target=t2))


def _mut_no_context_rows(vm):
    fs = dataclasses.replace(vm.context.first_screen, context_rows=())
    return dataclasses.replace(vm, context=dataclasses.replace(vm.context, first_screen=fs))


def _mut_riskcap_weakened(vm):
    """把判定軸（Risk Cap「⬜ 無法判定」）換成 Missing——語意被偷換。"""
    fs = vm.context.first_screen

    def fix(f):
        if f.layer == "judgement":
            return FieldVM(f.label, FieldState.MISSING, None, "⬜ 資料未備", f.detail, f.freshness)
        return f
    return dataclasses.replace(vm, context=dataclasses.replace(
        vm.context, first_screen=dataclasses.replace(fs, context_rows=tuple(fix(f) for f in fs.context_rows))))


@pytest.mark.parametrize("mut,page,key", [
    (_mut_empty_sections, P4_MARKET, "fake/p4_market/loaded/None"),
    (_mut_drop_l23, P4_MARKET, "fake/p4_market/loaded/None"),
    (_mut_drop_l23, P4_HOLD, "real/p4_hold/loaded"),
    (_mut_no_detail, P4_MARKET, "real/p4_market/unloaded"),
    (_mut_detail_x, P4_MARKET, "real/p4_market/unloaded"),
    (_mut_detail_x, P4_MARKET, "fake/p4_market/unavailable/None"),
    (_mut_value_x, P4_MARKET, "fake/p4_market/loaded/None"),
    (_mut_value_x, P4_MARKET, "real/p4_market/loaded"),
    (_mut_title_swapped, P4_HOLD, "fake/p4_hold/loaded/None"),
    (_mut_no_freshness, P4_MARKET, "real/p4_market/loaded"),
    (_mut_no_lookup_sections, P4_TARGET, "fake/p4_target/loaded/None"),
    (_mut_no_context_rows, P4_HOLD, "fake/p4_hold/loaded/None"),
    (_mut_riskcap_weakened, P4_HOLD, "fake/p4_hold/loaded/None"),
])
def test_evidence_preservation_guard_has_teeth(mut, page, key):
    """evidence 被刪空／拿掉 detail／拿掉 freshness／刪 lookup sections／Risk Cap 被換語意 → 比對必須非空（轉紅）。"""
    base = _load_baseline()[key]
    mutated = mut(all_vms()[key])
    assert compare(base, fingerprint(mutated)) != [], mut.__name__


def test_specific_evidence_is_still_there():
    """承重 evidence 的具名守衛：位階完整說明逐字（含決策參照）、Risk Cap 無法判定、Missing／Stale／Unavailable 態。"""
    snaps = _snapshots()
    # L0 位階完整說明：逐字常數仍在 VM（P3 不渲染，P6 資料健康度承接）
    vm = get_real_page_vm(P4_MARKET, snaps["unloaded"])
    why = next(s for s in vm.context.sections if s.section_id == "why")
    expl = next(f for f in why.fields if f.label == "位階說明")
    assert RA.NOT_LOADED_PENDING_BREADTH_EXPLAIN in (expl.detail or "")
    vm2 = get_real_page_vm(P4_MARKET, snaps["unevaluated"])
    expl2 = next(f for s in vm2.context.sections if s.section_id == "why" for f in s.fields if f.label == "位階說明")
    assert RA.UNEVALUATED_BREADTH_EXPLAIN in (expl2.detail or "")
    # Risk Cap「⬜ 無法判定」：三個投資頁的 context row 都在，且是判定軸（不是 Missing／Not Evaluated）
    for page in (P4_MARKET, P4_TARGET, P4_HOLD):
        for v in (get_preview_page_vm(page, "loaded"), get_real_page_vm(page, snaps["loaded"])):
            rows = [f for f in v.context.first_screen.context_rows if "Risk Cap" in f.label]
            assert rows and all(f.state is JudgementState.UNDETERMINABLE and f.status_text.startswith("⬜ 無法判定")
                                for f in rows), (page, v.scenario_id)
    # 場景→態：Missing／Stale／Unavailable／Not Evaluated 仍分別存在於對應場景 VM（不被 UI 移除連帶抹掉）
    def states(vm):
        out = set()
        for s in (*vm.context.sections, *(vm.context.target.lookup.sections if vm.context.target else ())):
            out |= {f.state for f in s.fields if f.state is not None}
        out |= {c.field.state for c in vm.context.cards}
        out |= {f.state for f in vm.context.first_screen.context_rows}
        return out
    assert FieldState.MISSING in states(get_preview_page_vm(P4_MARKET, "missing")) | states(get_preview_page_vm(P4_HOLD, "missing"))
    assert FieldState.STALE in states(get_preview_page_vm(P4_MARKET, "stale"))
    assert FieldState.UNAVAILABLE in states(get_preview_page_vm(P4_MARKET, "unavailable"))
    assert FieldState.NOT_EVALUATED in states(get_preview_page_vm(P4_MARKET, "not_evaluated")) | states(
        get_preview_page_vm(P4_MARKET, "cold"))
    # 每個 evidence 欄位仍帶來源／資料日欄位（FreshnessInfo 結構還在；缺就是缺，不能被刪）
    for s in get_preview_page_vm(P4_MARKET, "loaded").context.sections:
        for f in s.fields:
            assert hasattr(f.freshness, "source") and hasattr(f.freshness, "as_of")


# ══════════════════════════════════════════════════════════════════ RuleID／治理參照（現況鎖定）
def test_governance_references_and_rule_id_allowlist_are_locked_as_is():
    """⚠ 現況鎖定：VM **目前沒有獨立的 RuleID 欄位**（grep `rule_?id` 於 src/services/ui2、shared/ui2_contract、src/ui2 皆 0 命中）。
    實際承載治理參照的是 `why` section 的「位階說明」`detail`（L0 `regime_arbiter.*_EXPLAIN` 逐字，含 DEC-074／DEC-075 參照）。
    本測試鎖：(1) 這些參照仍在 VM（P3 不渲染不等於刪）；(2) Digest 的 `RULE_ID_ALLOWLIST` 6 個 id 仍存在，且該模組不依賴 UI2。
    日後 VM 若新增 RuleID 欄位，須把它納入本測試與 baseline。"""
    for name, expect in (("unloaded", RA.NOT_LOADED_PENDING_BREADTH_EXPLAIN), ("unevaluated", RA.UNEVALUATED_BREADTH_EXPLAIN)):
        vm = get_real_page_vm(P4_MARKET, _snapshots()[name])
        why = next(s for s in vm.context.sections if s.section_id == "why")
        d = next(f.detail for f in why.fields if f.label == "位階說明")
        assert expect in d and "DEC-074" in d and "DEC-075" in d, name   # L0 逐字常數為 detail 的前綴（後接 Preview 連接句）
    from shared import decision_digest_rules as R
    assert set(R.RULE_ID_ALLOWLIST) == {"risk_cap", "cut", "take_profit_force", "take_profit_partial", "pause_add", "add"}
    assert not [m for m in _imports_of(ROOT / "shared" / "decision_digest_rules.py") if m.startswith(_UI2_PREFIXES)]
    # mutation：治理參照被洗掉 → baseline 比對紅（detail 雜湊）
    base = _load_baseline()["real/p4_market/unloaded"]
    vm = get_real_page_vm(P4_MARKET, _snapshots()["unloaded"])
    assert compare(base, fingerprint(_mut_detail_x(vm))) != []


# ══════════════════════════════════════════════════════════════════ (A) 渲染層
def _app(*, scenario="loaded", account=None, real_snap=None, mode=None, monkeypatch=None):
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    a.session_state["ui2_scenario"] = scenario
    if account:
        a.session_state["ui2_account"] = account
    if real_snap is not None:
        a.session_state["ui2_feed"] = "real"
        monkeypatch.setattr("src.ui2.shell.app.read_real_snapshot", lambda: real_snap)
    if mode:
        a.session_state["ui2_target_mode"] = mode
    return a


def _go(a, page):
    a.run(timeout=60)
    a.radio(key="ui2_page").set_value(page).run(timeout=60)
    return a


def _allowed_titles(page: str) -> set[str]:
    out: set[str] = set()
    for vm in (get_preview_page_vm(page, "loaded"),):
        secs = list(vm.context.sections) + (list(vm.context.target.lookup.sections) if vm.context.target else [])
        out |= {s.title for s in secs if (page, s.section_id) in EXPECTED_SHOWN_FOLDS}
    return out


def _evidence_titles(page: str) -> set[str]:
    """該頁 VM 內**不該被渲染**的 L2／L3 區塊標題（FAKE 與 Real 的併集；排除白名單）。"""
    titles: set[str] = set()
    vms = [get_preview_page_vm(page, "loaded"), get_real_page_vm(page, _snapshots()["loaded"])]
    for vm in vms:
        secs = list(vm.context.sections) + (list(vm.context.target.lookup.sections) if vm.context.target else [])
        titles |= {s.title for s in secs if s.level in ("L2", "L3") and (page, s.section_id) not in EXPECTED_SHOWN_FOLDS}
    return titles


def render_violations(at, page: str) -> list[str]:
    """渲染層違規：expander 不在白名單／含 evidence 字樣／evidence 區塊標題出現在畫面任何處／白名單 expander 非收合。"""
    bad = []
    allowed = _allowed_titles(page)
    banned_words = ("為什麼", "指標明細", "原始資料", "工程診斷", "完整分析", "Digest raw", "raw", "debug", "provenance")
    for e in at.expander:
        lb = e.label.removeprefix("▸ ")
        if lb not in allowed:
            bad.append(f"expander 不在白名單：{lb!r}")
        if any(w in lb for w in banned_words):
            bad.append(f"expander 含 evidence 字樣：{lb!r}")
        if e.proto.expanded:
            bad.append(f"expander 預設展開：{lb!r}")
    md = "\n".join(m.value for m in at.markdown)
    labels = {e.label.removeprefix("▸ ") for e in at.expander}
    for t in _evidence_titles(page):
        # 以「區塊標題」的兩種渲染形式比對（expander 標題／`ui2-section-title`）；不比對任意子字串
        # （「基本面」「估值」同時是 6 維 Snapshot 的維度名，不是 evidence 區塊）。
        if t in labels or f'ui2-section-title">{t}<' in md:
            bad.append(f"evidence 區塊標題出現在畫面：{t!r}")
    return bad


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_fake_pages_render_no_evidence_expander_in_any_scenario(page, scenario):
    for acct in (ACCOUNT_IDS if page == P4_ME else (None,)):
        for mode in ((None, MODE_LOOKUP) if page == P4_TARGET else (None,)):
            at = _go(_app(scenario=scenario, account=acct, mode=mode), page)
            assert render_violations(at, page) == [], (page, scenario, acct, mode)


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("name", ["loaded", "unloaded", "unevaluated", "stale", "missing", "upstream_error",
                                  "unavailable", "contract_error"])
def test_real_pages_render_no_evidence_expander_in_any_state(page, name, monkeypatch):
    for mode in ((None, MODE_LOOKUP) if page == P4_TARGET else (None,)):
        at = _go(_app(real_snap=_snapshots()[name], mode=mode, monkeypatch=monkeypatch), page)
        assert any(T.REAL_PREVIEW_BANNER_TEXT in m.value for m in at.markdown), "沒有走 Real 道（snapshot 注入失效）"
        assert render_violations(at, page) == [], (page, name, mode)


def test_user_functions_and_approved_audit_entries_are_still_rendered_collapsed():
    """保留項：🎯 選股條件（使用者功能）、👤 Decision Digest／Rule Registry 稽核入口（預設收合）；📊／💼 為 0 個 expander。"""
    labels = lambda p, **kw: [e.label.removeprefix("▸ ") for e in _go(_app(**kw), p).expander]   # noqa: E731
    assert labels(P4_MARKET) == []
    assert labels(P4_HOLD) == []
    assert labels(P4_TARGET) == ["選股條件（收合）"]
    assert labels(P4_ME) == ["Audit：Decision Digest", "Audit：Rule Registry（唯讀）"]
    # 👤 的 Data Freshness／System Information 不在核准的稽核入口（Contract §3.4 → P6 資料健康度）：VM 仍有、畫面不渲染
    ids = {s.section_id for s in get_preview_page_vm(P4_ME, "loaded").context.sections}
    assert {"fresh", "sysinfo"} <= ids


def test_whitelist_is_exactly_the_documented_set():
    assert _page.SHOWN_FOLDS == EXPECTED_SHOWN_FOLDS
    # 白名單裡的每一項都對得到真實存在的 L2／L3 section（不是死項目）
    for page, sid in _page.SHOWN_FOLDS:
        vm = get_preview_page_vm(page, "loaded")
        assert any(s.section_id == sid and s.level in ("L2", "L3") for s in vm.context.sections), (page, sid)


def test_render_policy_guard_has_teeth(monkeypatch):
    """mutation：(1) 把 L2 evidence 渲染放回（is_shown_fold 恆 True）→ 轉紅；(2) 稽核入口／使用者功能被當 L2 隱藏
    （SHOWN_FOLDS 清空）→ 保留項測試轉紅。"""
    with monkeypatch.context() as m:
        m.setattr(_page, "is_shown_fold", lambda p, s: True)
        assert render_violations(_go(_app(), P4_MARKET), P4_MARKET) != []
        assert render_violations(_go(_app(), P4_HOLD), P4_HOLD) != []
    with monkeypatch.context() as m:
        m.setattr(_page, "SHOWN_FOLDS", frozenset())
        at = _go(_app(), P4_ME)
        assert [e.label for e in at.expander] == []                      # 稽核入口被移除
        assert [e.label for e in _go(_app(), P4_TARGET).expander] == []  # 選股條件被當 evidence 隱藏
    with monkeypatch.context() as m:       # 展開預設值被改 → 抓到
        orig = _page.st.expander
        m.setattr(_page.st, "expander", lambda title, expanded=False, **k: orig(title, expanded=True, **k))
        assert any("預設展開" in b for b in render_violations(_go(_app(), P4_ME), P4_ME))


# ══════════════════════════════════════════════════════════════════ viewport 判定器單元測試（純合成資料）
def _p3_eval(**kw) -> list[str]:
    from tests.ui2_viewport import measure_viewport as MV
    out = {"p3_no_evidence_expander": []}
    MV._evaluate_p3(kw, out)
    return out["p3_no_evidence_expander"]


def test_viewport_p3_checker_unit():
    ok = lambda t, open_=False: {"title": "keyboard_arrow_right " + t, "open": open_}      # noqa: E731
    assert _p3_eval(page="p4_market", expanders=[]) == []
    assert _p3_eval(page="p4_target", expanders=[ok("選股條件（收合）")]) == []
    assert _p3_eval(page="p4_me", expanders=[ok("Audit：Decision Digest"), ok("Audit：Rule Registry（唯讀）")]) == []
    assert _p3_eval(page="p4_market", expanders=[ok("為什麼")]) != []                    # 白名單外
    assert _p3_eval(page="p4_hold", expanders=[ok("明細")]) != []
    assert _p3_eval(page="p4_target", expanders=[ok("選股條件（收合）", True)]) != []     # 預設展開
    assert _p3_eval(page="p4_me", expanders=[ok("Audit：Data Freshness")]) != []        # 👤 Data Freshness 判紅
    assert _p3_eval(page="p4_me", expanders=[ok("Audit：System Information")]) != []
    assert _p3_eval(page="p4_market") != []                                              # 缺 expanders 鍵＝紅
    assert _p3_eval() == []                                                              # 無 page 的合成／舊版 dict 略過


def test_viewport_checker_allowed_titles_match_the_pytest_whitelist_and_the_view():
    from tests.ui2_viewport import measure_viewport as MV
    derived: dict[str, set[str]] = {p: set() for p in PAGE_IDS}
    for page in PAGE_IDS:
        vm = get_preview_page_vm(page, "loaded")
        secs = list(vm.context.sections) + (list(vm.context.target.lookup.sections) if vm.context.target else [])
        derived[page] = {s.title for s in secs if (page, s.section_id) in EXPECTED_SHOWN_FOLDS}
    assert {p: set(v) for p, v in MV.P3_ALLOWED_EXPANDER_TITLES.items()} == derived
    assert _page.SHOWN_FOLDS == EXPECTED_SHOWN_FOLDS


# ══════════════════════════════════════════════════════════════════ (C) Digest 輸入不依賴 UI2
_UI2_PREFIXES = ("src.ui2", "src.services.ui2", "shared.ui2_contract", "app_ui2")
_DIGEST_ENTRY = ["src/services/decision_digest_builder.py", "src/services/decision_digest_summary.py",
                 "shared/decision_digest.py", "shared/decision_digest_rules.py", "shared/decision_digest_grounding.py",
                 "shared/decision_digest_terms.py", "shared/decision_digest_validator.py"]


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module)
            out |= {f"{n.module}.{a.name}" for a in n.names}
    return out


def _module_file(mod: str) -> Path | None:
    parts = mod.split(".")
    for end in range(len(parts), 0, -1):
        base = ROOT.joinpath(*parts[:end])
        if base.with_suffix(".py").is_file():
            return base.with_suffix(".py")
        if (base / "__init__.py").is_file():
            return base / "__init__.py"
    return None


def import_closure(entry_files: list[str], extra: dict[str, set[str]] | None = None) -> set[str]:
    """repo 內靜態 import 傳遞閉包（AST，含函式內 import；不含動態 import／getattr 轉發——限制見 BACKLOG）。"""
    seen: set[str] = set()
    todo = [ROOT / f for f in entry_files]
    visited: set[Path] = set()
    while todo:
        p = todo.pop()
        if p in visited:
            continue
        visited.add(p)
        imps = _imports_of(p) | (extra or {}).get(p.name, set())
        seen |= imps
        for m in imps:
            if m.split(".")[0] in ("src", "shared", "app_ui2"):
                f = _module_file(m)
                if f is not None:
                    todo.append(f)
    return seen


def test_digest_builder_inputs_are_not_derived_from_ui2_rendering():
    """OneBrain 未來取 evidence 走正式 headless Digest：Digest builder／schema 的 repo 內 import 傳遞閉包不含任何 UI2 模組，
    且 builder 的公開簽名不收 PageVM／View Model／渲染物。⇒ UI2 區塊（含 P3 移除的 expander）的增減不影響 Digest 輸入。"""
    closure = import_closure(_DIGEST_ENTRY)
    hits = sorted(m for m in closure if m.startswith(_UI2_PREFIXES))
    assert hits == [], hits
    from src.services.decision_digest_builder import build_decision_digest
    params = inspect.signature(build_decision_digest).parameters
    for name, p in params.items():
        ann = str(p.annotation)
        assert "PageVM" not in ann and "ui2" not in ann.lower(), (name, ann)
    assert not {"vm", "page_vm", "page", "sections", "context"} & set(params)


def test_ui2_does_not_import_the_digest_builder_or_feed_it():
    """反向：UI2 不呼叫 Digest builder（不產生 Digest 輸入）；兩邊互不依賴。"""
    files = [str(p.relative_to(ROOT)) for d in ("src/ui2", "src/services/ui2", "shared/ui2_contract")
             for p in (ROOT / d).rglob("*.py")]
    imps = set()
    for f in files:
        imps |= _imports_of(ROOT / f)
    assert [m for m in imps if "decision_digest_builder" in m] == []


def test_digest_import_guard_has_teeth(tmp_path, monkeypatch):
    """mutation：Digest builder 若 import src.ui2 → 閉包抓得到（以暫時副本驗證檢查器本身）。"""
    fake = tmp_path / "fake_digest.py"
    fake.write_text("from src.ui2.views import _page\n", encoding="utf-8")
    orig = sys.modules[__name__]
    assert any(m.startswith(_UI2_PREFIXES) for m in _imports_of(fake))
    # 閉包走訪：入口檔經一層轉發 import UI2 也要抓到
    assert any(m.startswith(_UI2_PREFIXES) for m in import_closure(["src/ui2/views/market.py"]))
    assert orig is not None


if __name__ == "__main__":       # pragma: no cover — baseline 重新產生器（見檔頭）
    if "--regen" in sys.argv:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(build_baseline(), ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                            encoding="utf-8")
        print("wrote", BASELINE)
