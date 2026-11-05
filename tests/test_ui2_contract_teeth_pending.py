"""New UI2 最新 presentation contract 的「防復活 teeth」（DEC-128／DEC-129）。

分兩區：
  A. 現在就綠的 teeth（資料不得因 UI 移除而被刪；導覽仍只有四頁；不得從 URL／query 猜登入狀態）。
  B. **尚待 UI correction 批**才會綠的新 UI 行為斷言：寫成 `xfail(strict=True)`——
     * UI 還沒改 → 預期失敗（xfail）；
     * UI 一修好（XPASS）→ strict 使本測試**轉紅**，逼修的人**移除 xfail 標記**，之後它就是永久防復活守衛。
     * ⛔ 這裡只放「新 contract」的斷言；**不得**把任何現有資料／語意安全測試改成 xfail／skip。
reason 內的 P# 對應 docs/BACKLOG.md §5.1.26 批次表。

📌 P2（2026-11-04；客戶 (19)；DEC-133）：`T_new_6` 已於 UI 真正修好（台股 Primary 空槽＋SPEC 行）後移除 xfail（畢業，見 `GRADUATED_TEETH`）。

📌 P3（2026-11-03；客戶 (17) A2；DEC-131）：`T_new_1` 已於 UI 真正修好後移除 xfail（畢業，見 `GRADUATED_TEETH`）；
舊 `T_new_1b`（「三個投資頁 `PageVM.context.sections` 不得有 L2／L3」）是**測試規格錯誤**（與 Active Contract §8 矛盾：
它把「Human UI 不渲染」錯寫成「VM 不得含」，照做就得刪 evidence），已由 `test_T_new_1b_vm_keeps_evidence_while_human_ui_hides_it`
取代（驗收對象改為：渲染層無 evidence expander ＋ VM 仍完整保留）；完整的 evidence-preservation 守衛在
`tests/test_ui2_p3_evidence_preservation.py`。舊斷言原文：
`[s.section_id for s in vm.context.sections if s.level in ("L2", "L3")] == []`（保留於此供追溯，不得復活）。
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


def _at(dev: bool = False):
    """`dev=True`：開發面（`?ui2_dev=1`）。預設道（無旗標）不得有任何 Preview 控制（P1 起）。"""
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    if dev:
        a.query_params["ui2_dev"] = "1"
    return a.run(timeout=60)


def _blob(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _human_text(at) -> str:
    """使用者可見文字：去掉 `<style>` 區塊（CSS 不是人讀的字）與開發面標題區塊、再去 HTML 標籤。"""
    parts = [m.value for m in at.markdown if 'data-ui2-dev="1"' not in m.value]
    return re.sub(r"<[^>]+>", " ", re.sub(r"<style>.*?</style>", "", "\n".join(parts), flags=re.S))


def _xfail(p: str):
    return pytest.mark.xfail(strict=True, reason=f"待 UI correction 批 {p}，DEC-128")


def _xfail130(p: str):
    """DEC-130（客戶 (15) 覆核 PROVISIONAL (a)(b)(c) 升為 Active）新增的待 UI 批 teeth；reason 同時含 DEC-128／DEC-130。"""
    return pytest.mark.xfail(strict=True, reason=f"待 UI correction 批 {p}，DEC-128／DEC-130")


# ══════════════════════════════════════════════════════════════════ A. 現在就綠
def test_removed_human_sections_keep_their_data_in_the_vm_for_now():
    """「從 UI 移除 ≠ 刪資料」：📊 的 why／detail／raw sections 仍在 VM（P3 只改 render policy，不得刪；
    完整比對見 test_ui2_p3_evidence_preservation.py）。"""
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
    # D-12 加嚴（DEC-134／DEC-137；名稱保留以利追溯，「四格」現指「恰四頁」）：手機 @media 內有抽屜收合態、☰ 規則存在、
    # ⛔ 底部固定 53px 主導覽；恰四頁由 test_ui2_batch2::test_w1_nav_is_exactly_four_fixed_pages_no_fifth 守。
    from src.ui2.shell.css import CSS
    mobile = CSS[CSS.index("@media (max-width:768px){\n  .st-key-ui2_nav{"):]
    mobile = mobile[:mobile.index("\n}")]
    assert "transform:translateX(-105%);visibility:hidden" in mobile
    assert ".ui2-dr-toggle{position:fixed;top:0;left:0;" in CSS
    assert "bottom:0;height:53px" not in CSS


def test_me_page_audit_surface_exception_does_not_allow_evidence_expanders():
    """👤 的稽核面入口（Digest Viewer L1、Rule Registry，預設收合；PROVISIONAL (b)①）是明列例外，
    所以 T_new_1 不涵蓋 👤 的全部 expander；但 👤 同樣**不得**有 evidence 類 expander（為什麼／指標明細／原始資料／工程診斷）。"""
    at = _at()
    at.radio(key="ui2_page").set_value("p4_me").run(timeout=60)
    labels = [e.label for e in at.expander]
    assert [lb for lb in labels if any(w in lb for w in ("為什麼", "指標明細", "原始資料", "工程診斷"))] == []


# ══════════════════════════════════════════════════════════════════ B. 待 UI 批（strict xfail）
@pytest.mark.parametrize("page", ["p4_market", "p4_target", "p4_hold"])     # 👤 的 Audit 為稽核面（PROVISIONAL (b)），不在此列
def test_T_new_1_human_pages_have_no_full_evidence_expander(page):
    """P3 起轉綠（永久守衛）：三個投資頁不渲染 L2／L3 evidence expander。
    允許的 expander 只有 `SHOWN_FOLDS` 白名單內的使用者功能（🎯 選股條件）；其餘 expander 標題不得含 evidence 字樣、
    也不得等於 VM 的任何 L2／L3 區塊標題（結構判準）。"""
    from src.ui2.views._page import SHOWN_FOLDS
    at = _at()
    at.radio(key="ui2_page").set_value(page).run(timeout=60)
    labels = [e.label.removeprefix("▸ ") for e in at.expander]
    vm = get_preview_page_vm(page, "loaded")
    sections = list(vm.context.sections)
    if page == "p4_target":
        sections += list(vm.context.target.lookup.sections)
    shown = {s_.title for s_ in sections if (page, s_.section_id) in SHOWN_FOLDS}
    l23 = {s_.title for s_ in sections if s_.level in ("L2", "L3")} - shown
    bad = [lb for lb in labels if lb not in shown]
    bad += [lb for lb in labels if any(w in lb for w in _BANNED_EXPANDER_WORDS)]
    bad += [lb for lb in labels if lb in l23]
    assert bad == [], bad


@pytest.mark.parametrize("page", ["p4_market", "p4_target", "p4_hold"])
def test_T_new_1b_vm_keeps_evidence_while_human_ui_hides_it(page):
    """取代舊 T_new_1b（規格錯誤，見檔頭）。正確驗收對象：(a) 渲染層不出現 L2／L3 evidence expander（T_new_1）；
    (b) `PageVM.context.sections`（及 🎯 lookup sections）**仍保有** L2／L3 evidence——Active Contract §8：UI VM 全量、evidence 完整保留。
    逐欄 baseline 比對與 mutation 在 tests/test_ui2_p3_evidence_preservation.py。"""
    vm = get_preview_page_vm(page, "loaded")
    l23 = [s_.section_id for s_ in vm.context.sections if s_.level in ("L2", "L3")]
    assert l23, f"{page} 的 VM 不得被刪掉 L2／L3 evidence（舊 T_new_1b 的反面）"
    if page == "p4_target":
        assert [s_.section_id for s_ in vm.context.target.lookup.sections if s_.level in ("L2", "L3")]
    at = _at()
    at.radio(key="ui2_page").set_value(page).run(timeout=60)
    from src.ui2.views._page import SHOWN_FOLDS
    rendered = {e.label.removeprefix("▸ ") for e in at.expander}
    titles = {s_.title: s_.section_id for s_ in vm.context.sections if s_.level in ("L2", "L3")}
    leaked = [sid for t, sid in titles.items() if t in rendered and (page, sid) not in SHOWN_FOLDS]
    assert leaked == [], leaked


@pytest.mark.parametrize("page", ["p4_market", "p4_target", "p4_hold", "p4_me"])   # P1 起轉綠（四頁預設道）；完整詞彙清單×場景×Real 見 test_ui2_p1_human_text.py
def test_T_new_2_human_text_has_no_engineering_tokens(page):
    at = _at()
    at.radio(key="ui2_page").set_value(page).run(timeout=60)
    text = _human_text(at)
    hits = sorted({t for t in _ENGINEERING_TOKENS if t in text})
    assert hits == [], hits


@_xfail("P6")
def test_T_new_3_me_page_has_layered_data_health_section():
    vm = get_preview_page_vm("p4_me", "loaded")
    assert any("資料健康度" in (s.title or "") for s in vm.context.sections)


def test_T_new_5_preview_controls_are_dev_surface_only():
    # DEC-130 註：T_new_5 管「預設道 0 個 Preview 控制」；「`ui2_dev=1` 才顯示、且不影響 account 顯示」見 T_new_9（不重複）。
    at = _at()                                                  # 預設道（無開發旗標）
    assert [e.label for e in at.expander if e.label.startswith("Preview 控制")] == []
    assert len(at.selectbox) == 0                               # 資料來源／場景／帳戶三個控制一個都沒有（不是收合、是不存在）
    assert "開發／測試工具" not in _human_text(at) and 'data-ui2-dev="1"' not in _blob(at)
    # 其他旗標值（含看起來像「開」的）也不開（只認精確 "1"）
    from streamlit.testing.v1 import AppTest
    for v in ("0", "true", "yes", "1 ", ""):
        a = AppTest.from_file(str(APP_UI2), default_timeout=60)
        a.query_params["ui2_dev"] = v
        a.run(timeout=60)
        assert len(a.selectbox) == 0, v


def test_T_new_6_main_chart_has_short_spec_line():
    """（P2 畢業，DEC-133）原斷言不放寬：預設頁（📊 FAKE 冷啟動）任一 markdown 含 `SPEC｜`。
    加強版（位置／來源資料日與 TWII 卡逐字一致／最新收盤參考／無假圖）見 tests/test_ui2_p2_primary_slot.py。"""
    at = _at()
    assert "SPEC｜" in _blob(at)


@_xfail("P7")
def test_T_new_7_desktop_navigation_rail_has_account_area_with_auth_status():
    at = _at()
    blob = _blob(at)
    assert "登入" in blob and "尚未登入" in blob and 'data-ui2-account-area' in blob


# ── DEC-130（客戶 2026-11-03 (15)）：資料健康度兩軸分離／ui2_dev 只控開發面 ──────────────────
@_xfail130("P6")
def test_T_new_8_data_health_rows_separate_data_state_from_capability():
    """資料健康度每列：Data State（五態）與 Capability（接線）必為**不同欄位**，禁止單一 status 欄混用。
    DOM 標記名（`data-ui2-col="data-state"`／`"capability"`）於 P6 實作時定案；若實作選用別名，同步改本測試（XPASS 會逼你來改）。"""
    at = _at()
    at.radio(key="ui2_page").set_value("p4_me").run(timeout=60)
    blob = _blob(at)
    ds = re.findall(r'<[^>]*data-ui2-col="data-state"[^>]*>(.*?)</', blob, re.S)
    cap = re.findall(r'<[^>]*data-ui2-col="capability"[^>]*>(.*?)</', blob, re.S)
    assert ds and len(ds) == len(cap), (len(ds), len(cap))              # 每列兩欄都在
    assert not any("尚未接線" in c for c in ds)                          # ⬜ 尚未接線 不得出現在 Data State 欄


def test_T_new_9_ui2_dev_shows_preview_controls_and_never_changes_account_area():
    """`?ui2_dev=1` 才顯示 Preview 控制（開發面）；且該 query parameter 不得影響帳戶顯示（不是登入證據）。
    （預設道 0 控制見 T_new_5；Account Area 本體屬 P7，見 T_new_7。）

    P1 斷言：(1) 開發面只在 dev 道出現且帶「非產品內容」標示；(2) 四頁的**產品內容**（去掉開發面標題區塊後的全部 markdown）
    在 dev／非 dev 兩道逐字相同——`ui2_dev` 不改任何頁面內容，特別是 👤 我的的連線狀態／帳戶動作；
    (3) 若日後 Account Area（`data-ui2-account-area`）存在，同樣兩道相同。"""
    def _area(b: str) -> str:
        m = re.search(r'<[^>]*data-ui2-account-area[^>]*>.*?</(?:div|section|aside)>', b, re.S)
        return m.group(0) if m else ""

    plain, dev = _at(), _at(dev=True)
    assert len(plain.selectbox) == 0 and len(dev.selectbox) == 3
    assert {s_.key for s_ in dev.selectbox} == {"ui2_feed", "ui2_scenario", "ui2_account"}   # 且仍是 ui2_ 前綴
    assert "開發／測試工具（非產品內容）" in "\n".join(m.value for m in dev.markdown)
    assert "開發／測試工具" not in _human_text(plain) and 'data-ui2-dev="1"' not in _blob(plain)
    for page in PAGE_IDS:
        for a_ in (plain, dev):
            a_.radio(key="ui2_page").set_value(page).run(timeout=60)

        def _product(at):
            return "\n".join(m.value for m in at.markdown if 'data-ui2-dev="1"' not in m.value)
        assert _product(plain) == _product(dev), page
        assert _area(_product(plain)) == _area(_product(dev))
