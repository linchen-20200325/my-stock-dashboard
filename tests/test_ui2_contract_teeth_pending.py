"""New UI2 最新 presentation contract 的「防復活 teeth」（DEC-128／DEC-129）。

分兩區：
  A. 現在就綠的 teeth（資料不得因 UI 移除而被刪；導覽仍只有四頁；不得從 URL／query 猜登入狀態）。
  B. **尚待 UI correction 批**才會綠的新 UI 行為斷言：寫成 `xfail(strict=True)`——
     * UI 還沒改 → 預期失敗（xfail）；
     * UI 一修好（XPASS）→ strict 使本測試**轉紅**，逼修的人**移除 xfail 標記**，之後它就是永久防復活守衛。
     * ⛔ 這裡只放「新 contract」的斷言；**不得**把任何現有資料／語意安全測試改成 xfail／skip。
reason 內的 P# 對應 docs/BACKLOG.md §5.1.26 批次表。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from shared.ui2_contract.pages import PAGE_IDS
from src.services.ui2.preview_feed import get_preview_page_vm

ROOT = Path(__file__).resolve().parent.parent
APP_UI2 = ROOT / "app_ui2.py"

_BANNED_EXPANDER_WORDS = ("為什麼", "指標明細", "原始資料", "工程診斷", "raw", "debug", "provenance", "L2", "L3")
_ENGINEERING_TOKENS = ("PORT", "Gate", "Stage", "Aggregator", "路徑 C", "nonce", "traceback", "Exception", "src.", ".py")


def _at():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(str(APP_UI2), default_timeout=60).run(timeout=60)


def _blob(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _xfail(p: str):
    return pytest.mark.xfail(strict=True, reason=f"待 UI correction 批 {p}，DEC-128")


# ══════════════════════════════════════════════════════════════════ A. 現在就綠
def test_removed_human_sections_keep_their_data_in_the_vm_for_now():
    """「從 UI 移除 ≠ 刪資料」：📊 的 why／detail／raw sections 目前仍在 VM（P3 只改 render policy，不得刪）。"""
    vm = get_preview_page_vm("p4_market", "loaded")
    ids = {s.section_id for s in vm.context.sections}
    assert {"why", "detail", "raw"} <= ids, ids


def test_nav_is_still_exactly_four_pages_account_area_is_not_a_fifth():
    from shared.ui2_contract.pages import PAGE4_LABELS
    at = _at()
    assert list(at.radio(key="ui2_page").options) == [PAGE4_LABELS[p] for p in PAGE_IDS]
    assert len(PAGE_IDS) == 4


def test_ui2_never_derives_auth_state_from_url_or_query_params():
    """(14) §1：Authentication State 不得由 URL／query parameter 猜。UI2 目前不讀 query params；日後 `?ui2_dev=1`
    只准用於開發面旗標（P1），不得讀登入狀態——此守衛抓 `query_params` 與 auth／login／signed 識別字在同一函式內共現。"""
    offenders = []
    for p in list((ROOT / "src" / "ui2").rglob("*.py")) + list((ROOT / "src" / "services" / "ui2").rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
            src = ast.get_source_segment(p.read_text(encoding="utf-8"), fn) or ""
            if re.search(r"query_params|experimental_get_query_params", src) and re.search(
                    r"login|logged|signed|auth|oauth|account", src, re.I):
                offenders.append(f"{p.relative_to(ROOT)}::{fn.name}")
    assert offenders == []


def test_mobile_nav_stays_four_cells_in_css():
    css = (ROOT / "src" / "ui2" / "shell" / "css.py").read_text(encoding="utf-8")
    assert "ui2_nav" in css                                     # 導覽 container 錨點仍在
    # Account Area 若加入，只能出現在桌機 media query（手機仍固定四格）：此處只釘「手機底部導覽規則存在」
    assert "position: fixed" in css or "position:fixed" in css


# ══════════════════════════════════════════════════════════════════ B. 待 UI 批（strict xfail）
@_xfail("P3")
@pytest.mark.parametrize("page", ["p4_market", "p4_target", "p4_hold"])     # 👤 的 Audit 為稽核面（PROVISIONAL (b)），不在此列
def test_T_new_1_human_pages_have_no_full_evidence_expander(page):
    at = _at()
    at.radio(key="ui2_page").set_value(page).run(timeout=60)
    labels = [e.label for e in at.expander if not e.label.startswith("Preview 控制")]
    bad = [lb for lb in labels if any(w in lb for w in _BANNED_EXPANDER_WORDS)]
    assert bad == [], bad


@_xfail("P3")
@pytest.mark.parametrize("page", ["p4_market", "p4_target", "p4_hold"])
def test_T_new_1b_human_vm_sections_are_not_l2_l3(page):
    vm = get_preview_page_vm(page, "loaded")
    assert [s.section_id for s in vm.context.sections if s.level in ("L2", "L3")] == []


@_xfail("P1")
@pytest.mark.parametrize("page", ["p4_market", "p4_hold", "p4_me"])         # FAKE loaded 場景；🎯 的工程字樣只在 Real 模式出現
def test_T_new_2_human_text_has_no_engineering_tokens(page):
    at = _at()
    at.radio(key="ui2_page").set_value(page).run(timeout=60)
    text = re.sub(r"<[^>]+>", " ", _blob(at))
    hits = sorted({t for t in _ENGINEERING_TOKENS if t in text})
    assert hits == [], hits


@_xfail("P6")
def test_T_new_3_me_page_has_layered_data_health_section():
    vm = get_preview_page_vm("p4_me", "loaded")
    assert any("資料健康度" in (s.title or "") for s in vm.context.sections)


@_xfail("P1")
def test_T_new_5_preview_controls_are_dev_surface_only():
    at = _at()                                                  # 預設道（無開發旗標）
    assert [e.label for e in at.expander if e.label.startswith("Preview 控制")] == []


@_xfail("P2")
def test_T_new_6_main_chart_has_short_spec_line():
    at = _at()
    assert "SPEC｜" in _blob(at)


@_xfail("P7")
def test_T_new_7_desktop_navigation_rail_has_account_area_with_auth_status():
    at = _at()
    blob = _blob(at)
    assert "登入" in blob and "尚未登入" in blob and 'data-ui2-account-area' in blob
