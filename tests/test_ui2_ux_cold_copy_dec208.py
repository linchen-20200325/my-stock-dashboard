# -*- coding: utf-8 -*-
"""tests/test_ui2_ux_cold_copy_dec208.py — DEC-208：disabled 更新／搜尋的「誘導字樣」回歸守衛（UX-1 非凍結部分＋UX-2 U-1＋G-3）。

出處：Issue #1199 comment 7021221449（總管 UX Gate 裁示）／7013013852（精確 old/new）。

背景：Preview 期 📊／💼 的主 CTA 與 🎯 的搜尋 CTA 皆 `enabled=False`（disabled），但畫面卻寫著
「按 🚀 更新後載入」「按 🚀 更新」「請輸入代碼（名稱搜尋尚未提供）」「輸入代碼並查詢後顯示」——命令使用者去按／輸入一個
明寫「此功能尚未開放」的控制項，同頁自相矛盾。

本檔釘住：
- R1  📊／💼 FAKE cold 整頁渲染文字**不含** `按.*更新`／`更新後載入`／`請按更新`（**含** 📊 今日主要風險 chip）。
- G1  G-1(b)（使用者 2026-11-20「同意」，#1199 comment 7021388731）：僅 New UI2＋FAKE＋cold＋更新 CTA disabled 的 📊 今日主要風險
      chip 由 `⬜ 尚未載入，請按更新` 改 `⬜ 尚未載入`（detail＝既有 `FAKE 示意：尚未載入`）；**反向釘住**：全域常數
      `RISK_SENTENCE_NOT_LOADED` 仍為原句、Legacy `_market_blocks.py::NOT_LOADED` 仍含原句、其餘場景（missing／not_evaluated／
      unavailable／loaded／stale）與 Real 的主要風險字句逐字不變、灰態語意（⛔ 紅、⛔ 風險項列）不變。
- R2  disabled CTA／「此功能尚未開放」／四問／`⬜ 尚未載入` chip／FAKE banner／📊 下一步列（`⬜ 尚未提供（待系統動作整合）`）仍在。
- R3  🎯 FAKE 6 場景×2 模式＋Real×2 模式整頁無「請輸入代碼」；hint 為「名稱搜尋」label＋`⬜ 尚未提供` chip；
      CTA 理由「尚未開放查詢…」與搜尋框 `aria-disabled` 仍在；FAKE cold 查一檔不含「輸入代碼並查詢後顯示」。
- R4  render 單元：`CtaVM(enabled=True)` 的 `search_html` 仍輸出「請輸入代碼（名稱搜尋尚未提供）」，`enabled=False` 不輸出。
- R5  Real 五頁無 `按…更新`／`請按`／`更新後載入`／`請輸入代碼`（不退化）。

以下為自跑結論，未經第二組驗證；每條測試的「牙」（暫時突變→紅→還原）結果記在 PR 描述與 DEC-208。
"""
from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.models import CtaVM
from shared.ui2_contract.pages import (
    MODE_CURATED, MODE_LOOKUP, P4_DATA, P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE_IDS, SCENARIO_IDS,
)
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.scenarios import fake_canonical
from src.ui2.components.html import search_html

ROOT = Path(__file__).resolve().parent.parent
APP_UI2 = ROOT / "app_ui2.py"

#: 誘導字樣（命令使用者去按／輸入 disabled 控制項）。`按.*更新` 以「文字節點」為單位比對（見 `_nodes`），避免跨 HTML 標籤誤判。
_LURE_RX = re.compile(r"按.*更新|更新後載入|請按")
_LURE_SEARCH = ("請輸入代碼", "輸入代碼並查詢後顯示")


# ════════════════════════════════════════════════════════════════════
# helpers
# ════════════════════════════════════════════════════════════════════
def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, dict):
        for c in children.values():
            yield from _walk(c)


def _blob(at) -> str:
    """整頁 markdown／caption／label 等可見文字的聯集（HTML 原文保留；去 `<style>`）。"""
    parts: list[str] = []
    for blk in (at.main, at.sidebar):
        for el in _walk(blk):
            for attr in ("value", "label", "body", "placeholder"):     # Markdown 的 value／body 是同一份：每元素只取第一個
                v = getattr(el, attr, None)
                if isinstance(v, str) and v:
                    parts.append(v)
                    break
    return re.sub(r"<style.*?</style>", "", "\n".join(parts), flags=re.S)


def _nodes(blob: str) -> list[str]:
    """把 HTML 切成「文字節點」（使用者實際讀到的一段段字）。"""
    return [s.strip() for s in re.split(r"<[^>]+>", blob) if s.strip()]


def _fake_at(page: str, scenario: str, mode: str | None = None):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_UI2), default_timeout=60)
    at.query_params["ui2_dev"] = "1"            # 場景／帳戶／頁切換控制只在開發面
    at.run(timeout=60)
    at.selectbox(key="ui2_scenario").set_value(scenario).run(timeout=60)
    at.radio(key="ui2_page").set_value(page).run(timeout=60)
    if mode is not None:
        at.radio(key="ui2_target_mode").set_value(mode).run(timeout=60)
    assert not at.exception
    return at


def _real_at(page: str, mode: str | None = None):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_UI2), default_timeout=60)
    at.query_params["ui2_dev"] = "1"
    at.session_state["ui2_feed"] = "real"
    at.session_state["ui2_page"] = page
    if mode is not None:
        at.session_state["ui2_target_mode"] = mode
    at.run(timeout=60)
    assert not at.exception
    assert at.session_state["ui2_feed"] == "real"
    return at


def _lures(nodes: list[str]) -> list[str]:
    return [n for n in nodes if _LURE_RX.search(n)]


def _hint_of(blob: str) -> str:
    m = re.search(r'<div class="ui2-search__hint">(.*?)</div>', blob, flags=re.S)
    assert m, "找不到 ui2-search__hint"
    return m.group(1)


# ════════════════════════════════════════════════════════════════════
# R1｜📊／💼 FAKE cold：整頁不含誘導字樣（G-1(b) 後無任何例外）
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("page", [P4_MARKET, P4_HOLD])
def test_r1_fake_cold_page_has_no_update_lure(page):
    nodes = _nodes(_blob(_fake_at(page, "cold")))
    assert nodes, "整頁沒有文字節點（頁沒渲染？）"
    assert _lures(nodes) == []


@pytest.mark.parametrize("page", PAGE_IDS)
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_r1_fake_canonical_never_says_update_then_load(page, scenario):
    """VM／canonical 層（整個 FAKE 矩陣）：任何頁×場景都不再寫「更新後載入」「按 🚀」「請按更新」。"""
    dump = json.dumps(fake_canonical(page, scenario), ensure_ascii=False)
    assert "更新後載入" not in dump
    assert "按 🚀" not in dump
    assert "請按更新" not in dump


# ════════════════════════════════════════════════════════════════════
# G1｜G-1(b) 單一情境例外（FAKE cold＋更新 disabled）與其「反向」邊界
# ════════════════════════════════════════════════════════════════════
LEGACY_BLOCKS = (ROOT / "src" / "ui" / "views" / "_market_blocks.py").read_text(encoding="utf-8")


def test_g1_fake_cold_main_risk_chip_is_plain_not_loaded_in_the_rendered_page():
    nodes = _nodes(_blob(_fake_at(P4_MARKET, "cold")))
    assert T.RISK_SENTENCE_NOT_LOADED not in nodes and not any("請按更新" in n for n in nodes)
    blob = _blob(_fake_at(P4_MARKET, "cold"))
    m = re.search(r'<div class="ui2-risk" data-ui2-l1="main_risk"[^>]*>(.*?)</div></div>', blob, flags=re.S)
    assert m, "找不到 今日主要風險 區塊（不得被移除）"
    risk = _nodes(m.group(0))
    assert risk == ["今日主要風險", T.TEXT_NOT_LOADED, "FAKE 示意：尚未載入"], risk
    assert "danger" not in m.group(0) and 'data-state="not_evaluated"' in m.group(0)        # 灰態語意不變（⛔ 紅）


def test_g1_global_constant_and_legacy_source_are_verbatim_untouched():
    assert T.RISK_SENTENCE_NOT_LOADED == "⬜ 尚未載入，請按更新"
    assert 'NOT_LOADED: str = "⬜ 尚未載入，請按更新"' in LEGACY_BLOCKS
    assert T.RISK_SENTENCE_NOT_LOADED.startswith(T.TEXT_NOT_LOADED)


def test_g1_other_fake_scenarios_main_risk_sentences_are_unchanged():
    """例外只給 cold：其餘 5 場景的主要風險字句逐字同 main（DEC-117 Q6 原句／capability 欄）。"""
    def risk(sc):
        return get_preview_page_vm(P4_MARKET, sc).context.main_risk
    assert risk("missing").status_text == T.RISK_SENTENCE_ALL_INSUFFICIENT
    ne = risk("not_evaluated")
    assert ne.status_text == "⬜ 尚未評估" and ne.detail == T.RISK_NOTE_UNEVALUATED_NOT_SAFE
    un = risk("unavailable")
    assert un.detail == T.RISK_ERROR_FMT.format(error="FAKE 來源逾時（示意）")
    for sc in ("loaded", "stale"):
        f = risk(sc)
        assert f.status_text == T.TEXT_NOT_PROVIDED and f.detail == "風險摘要尚未提供；這裡不推導任何風險"


def test_g1_cold_exception_applies_only_to_the_cold_scenario():
    cold = get_preview_page_vm(P4_MARKET, "cold").context.main_risk
    assert cold.status_text == T.TEXT_NOT_LOADED and cold.detail == "FAKE 示意：尚未載入"
    assert cold.value_text is None and cold.layer == "data"
    assert cold.status_text != T.RISK_SENTENCE_NOT_LOADED


@pytest.mark.parametrize("page", [P4_MARKET, P4_HOLD])
def test_r1_fake_cold_next_step_is_aggregator_pending_not_a_button_hint(page):
    assert fake_canonical(page, "cold").get("next_step") is None               # 交給 vm_common 的既有 capability 欄
    ns = get_preview_page_vm(page, "cold").context.first_screen.next_step
    assert ns is not None and ns.status_text == T.TEXT_NOT_PROVIDED_AGGREGATOR
    assert ns.detail == "動作判斷功能尚未開放"


# ════════════════════════════════════════════════════════════════════
# R2｜誠實呈現不退化：disabled CTA／四問／未載入 chip／banner／下一步列
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("page,cta_label,qs", [
    (P4_MARKET, "🚀 更新今日戰情", ("q1", "q2", "q3", "q4")),
    (P4_HOLD, "🚀 更新持股戰情", ("q1", "q2", "q4")),          # 💼 第一屏本來就不渲染「下一步」列（next_step 僅 VM；#5 對 💼 為 VM-only）
])
def test_r2_fake_cold_keeps_honest_disabled_cta_and_structure(page, cta_label, qs):
    blob = _blob(_fake_at(page, "cold"))
    nodes = _nodes(blob)
    # disabled CTA 仍在（aria-disabled）＋理由
    assert re.search(r'class="ui2-cta ui2-cta--disabled" role="button" aria-disabled="true">' + re.escape(cta_label), blob)
    assert "此功能尚未開放" in nodes
    # 四問（量測錨點）仍在
    for q in qs:
        assert f'data-ui2-q="{q}"' in blob, f"{page}: 缺四問錨點 {q}"
    # 未載入 chip（灰）仍在
    assert T.TEXT_NOT_LOADED in nodes
    # FAKE banner 仍在
    assert T.PREVIEW_BANNER_TEXT in nodes
    if page != P4_MARKET:
        return
    # 📊「下一步」列仍在，且內容為既有 capability 欄（⛔「按 🚀 更新」）
    m = re.search(r'<div class="ui2-qrow" data-ui2-q="q3"[^>]*>(.*?)</div>(?=<div class="ui2-qrow|</div>)', blob, flags=re.S)
    assert m, "找不到「下一步」列（data-ui2-q=q3）"
    row = _nodes(m.group(0))
    assert "下一步" in row and T.TEXT_NOT_PROVIDED_AGGREGATOR in row
    assert not any("按" in n for n in row)


# ════════════════════════════════════════════════════════════════════
# R3｜🎯 搜尋 hint：「名稱搜尋」label＋`⬜ 尚未提供` chip；無「請輸入代碼」
# ════════════════════════════════════════════════════════════════════
def _assert_target_search_clean(blob: str, ctx: str):
    nodes = _nodes(blob)
    for bad in _LURE_SEARCH:
        assert not any(bad in n for n in nodes), f"{ctx}: 不得出現 {bad!r}"
    hint = _nodes(_hint_of(blob))
    assert hint == ["名稱搜尋", "⬜ 尚未提供"], f"{ctx}: hint 應為 label＋chip，實為 {hint!r}"
    # 搜尋框 disabled 與 CTA 理由仍在（Real 理由「尚未開放查詢」；FAKE 為「尚未開放查詢…」家族）
    assert 'role="searchbox" aria-disabled="true"' in blob
    reason = re.search(r'<div class="ui2-cta__reason">(.*?)</div>', blob, flags=re.S)
    assert reason and reason.group(1).startswith("尚未開放查詢"), f"{ctx}: CTA 理由不見了 {reason!r}"


@pytest.mark.parametrize("mode", [MODE_CURATED, MODE_LOOKUP])
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_r3_fake_target_search_hint_has_no_command(scenario, mode):
    _assert_target_search_clean(_blob(_fake_at(P4_TARGET, scenario, mode)), f"FAKE/{scenario}/{mode}")


@pytest.mark.parametrize("mode", [MODE_CURATED, MODE_LOOKUP])
def test_r3_real_target_search_hint_has_no_command(mode):
    _assert_target_search_clean(_blob(_real_at(P4_TARGET, mode)), f"Real/{mode}")


def test_r3_g3_fake_cold_lookup_says_not_loaded_not_type_a_code():
    """G-3：FAKE cold×查一檔的灰色說明改既有「FAKE 示意：尚未載入」；不再指示輸入／查詢已 disabled 的搜尋框。"""
    blob = _blob(_fake_at(P4_TARGET, "cold", MODE_LOOKUP))
    assert 'data-ui2-queried="false"' in blob
    nodes = _nodes(blob)
    assert "FAKE 示意：尚未載入" in nodes
    assert not any("輸入代碼並查詢後顯示" in n for n in nodes)
    assert fake_canonical(P4_TARGET, "cold")["target"]["lookup"]["summary"]["reason"] == "FAKE 示意：尚未載入"


def test_r3_fake_target_curated_cold_keeps_its_own_reason():
    """🎯 精選冷啟的 cold_reason（`FAKE 示意：精選尚未載入`）不併入其他頁的「尚未載入」。"""
    c = fake_canonical(P4_TARGET, "cold")
    assert c["current_state"]["reason"] == "FAKE 示意：精選尚未載入"


# ════════════════════════════════════════════════════════════════════
# R4｜render 單元：enabled 條件式（不是字串過濾）
# ════════════════════════════════════════════════════════════════════
def _search_vm(*, enabled: bool):
    s = get_preview_page_vm(P4_TARGET, "loaded").context.target.search
    return dataclasses.replace(s, cta=CtaVM(label=s.cta.label, enabled=enabled,
                                            disabled_reason=None if enabled else s.cta.disabled_reason))


def test_r4_search_html_enabled_true_keeps_the_honest_instruction():
    html = search_html(_search_vm(enabled=True))
    assert "請輸入代碼（名稱搜尋尚未提供）" in _nodes(html)


def test_r4_search_html_enabled_false_shows_label_and_chip_only():
    html = search_html(_search_vm(enabled=False))
    assert "請輸入代碼" not in html
    assert _nodes(_hint_of(html)) == ["名稱搜尋", "⬜ 尚未提供"]
    assert 'class="ui2-searchbox" role="searchbox" aria-disabled="true"' in html or 'role="searchbox" aria-disabled="true"' in html


def test_r4_disabled_branch_escapes_the_name_search_label():
    """U-1 disabled 分支把 `name_search.label` 直接放進 HTML：必須 `escape()`（防 label 含 HTML 特殊字元時注入）。"""
    base = _search_vm(enabled=False)
    evil = dataclasses.replace(base, name_search=dataclasses.replace(base.name_search, label="<b>x</b>&"))
    html = search_html(evil)
    hint = _hint_of(html)
    assert "&lt;b&gt;x&lt;/b&gt;&amp;" in hint
    assert "<b>" not in html and "</b>" not in html


def test_r4_enabled_branch_is_conditional_not_a_string_filter():
    """同一個 name_search.detail（「請輸入代碼…」）在 enabled=True 仍被渲染 → 證明 disabled 時是「不輸出」而非資料被改掉。"""
    on, off = _search_vm(enabled=True), _search_vm(enabled=False)
    assert on.name_search == off.name_search and "請輸入代碼" in (on.name_search.detail or "")
    assert "請輸入代碼" in search_html(on) and "請輸入代碼" not in search_html(off)


# ════════════════════════════════════════════════════════════════════
# R5｜Real 五頁不退化
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("page", PAGE_IDS)
def test_r5_real_pages_have_no_lure(page):
    blob = _blob(_real_at(page))
    assert T.REAL_PREVIEW_BANNER_TEXT in _nodes(blob)                           # 確實是 Real 軸
    nodes = _nodes(blob)
    assert _lures(nodes) == []
    for bad in _LURE_SEARCH:
        assert not any(bad in n for n in nodes)


# ════════════════════════════════════════════════════════════════════
# 轉換函式預設值（防「呼叫端都傳值、預設值悄悄回到舊句」）
# ════════════════════════════════════════════════════════════════════
def test_transform_defaults_for_cold_are_not_an_update_instruction():
    from src.services.ui2 import scenarios as SC
    spec = {"key": "x", "label": "X", "value": "1"}
    for out in (SC._transform(spec, "cold", 0), SC._transform_current(spec, "cold")):
        assert out["reason"] == "FAKE 示意：尚未載入" and out["sub_reason"] == T.TEXT_NOT_LOADED
        assert not _LURE_RX.search(out["reason"])
