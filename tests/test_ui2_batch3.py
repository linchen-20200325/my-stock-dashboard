"""New UI2 Batch 3（presentation）：📊 今日結論＋今日主要風險、🎯 雙模式＋搜尋＋查一檔 FAKE、👤 帳戶 skeleton。

驗收（客戶 2026-11-03 (10)-B～F）：
1. 今日結論**無方向推導**（只並列、缺值明寫、⛔「但／因此」；VM 原樣帶出，不由位階／指標推導）。
2. 今日主要風險**緊接第一屏、不被插隊**（DOM 順序＋量測）；退化句逐字取自 DEC-117 Q6（與 Legacy 原始碼逐字比對）；
   冷啟動不出風險項列，灰色說明（⛔ 紅）。
3. 🎯 模式切換**不同時完整展開**（兩模式內容都在 context、只有 slice 決定展開哪個）；搜尋／查一檔 **session-only**，
   不寫 `ui2_` 以外狀態、不 import 任何寫入／取數路徑；加入觀察 CTA 恆 disabled；⛔ 買賣判斷字樣；W-4 輕量 context。
4. 👤 我的頁 signed-out／signed-in／unavailable：**AST／import 守衛**證明無 OAuth／Sheet 呼叫。
5. 三軸（資料語意／判定結果／capability）不混層；UI2 無人名字樣（PROJECT_RULES §28）。

守衛皆為「純函式檢查器吃原始碼字串」：對真檔必須 0 違規、對注入違規必須 >0（mutation：拔掉守衛轉紅）。
⛔ 本檔不改任何既有守衛斷言。
"""
from __future__ import annotations

import ast
import pathlib
import re
from dataclasses import replace

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.models import CapabilityState, FieldState, FieldVM, JudgementState, PageVM
from shared.ui2_contract.pages import (
    ACCOUNT_IDS, ACCOUNT_SIGNED_IN, ACCOUNT_SIGNED_OUT, ACCOUNT_UNAVAILABLE, MODE_CURATED, MODE_IDS,
    MODE_LABELS, MODE_LOOKUP, P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE_IDS, SCENARIO_IDS,
)
from src.services.ui2 import vm_common
from src.services.ui2.market_vm import build_market_page_vm
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.scenarios import fake_canonical
from src.ui2.components import html as H

ROOT = pathlib.Path(__file__).resolve().parents[1]
UI2_DIRS = [ROOT / "shared" / "ui2_contract", ROOT / "src" / "services" / "ui2", ROOT / "src" / "ui2"]
UI2_FILES = sorted(p for d in UI2_DIRS for p in d.rglob("*.py") if "__pycache__" not in p.parts) + [
    ROOT / "app_ui2.py"]


def _txt(html_: str) -> str:
    return re.sub(r"<[^>]+>", " ", html_)


# ════════════════════════════════════════════════════════════════════
# 1. 今日結論：無方向推導
# ════════════════════════════════════════════════════════════════════
_DIRECTION_WORDS = ("多頭", "空頭", "偏多", "偏空", "看多", "看空", "轉守", "牛市", "熊市",
                    "bull", "bear", "risk-on", "risk-off", "Risk-on", "Risk-off")
_CAUSAL_WORDS = ("但", "因此", "所以", "因為", "導致", "由於", "故")
_ACTION_WORDS = ("加碼", "減碼", "買進", "賣出", "建議", "今日無需調整", "今日需處理", "全出")


def check_conclusion_text(text: str) -> list[str]:
    """DEC-081 Q2-1：各判斷獨立並列（「；」）、⛔「但／因此」硬做因果、⛔ 方向／動作字樣。"""
    bad = []
    for w in _DIRECTION_WORDS:
        if w in text:
            bad.append(f"方向字樣 {w!r}")
    for w in _CAUSAL_WORDS:
        if w in text:
            bad.append(f"因果連接詞 {w!r}")
    for w in _ACTION_WORDS:
        if w in text:
            bad.append(f"動作字樣 {w!r}")
    return bad


def _conclusion(scenario: str, **kw) -> FieldVM:
    c = get_preview_page_vm(P4_MARKET, scenario, **kw).context.first_screen.conclusion
    assert c is not None
    return c


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_conclusion_has_no_direction_causality_or_action(scenario):
    c = _conclusion(scenario)
    blob = " ".join([c.value_text or "", c.status_text or "", c.detail or ""])
    assert check_conclusion_text(blob) == [], blob


def test_conclusion_checker_has_teeth():
    assert check_conclusion_text("震盪；但外資偏多")                       # 因果＋方向
    assert check_conclusion_text("因此建議加碼")
    assert check_conclusion_text("市場目前狀態 空頭")


@pytest.mark.parametrize("scenario", [s for s in SCENARIO_IDS if s != "cold"])
def test_conclusion_is_parallel_clauses_and_names_every_non_ok_state(scenario):
    """每個非 OK 指標卡都在結論句**明寫**（missing 不當中性；DEC-081 Q2-1）。"""
    vm = get_preview_page_vm(P4_MARKET, scenario)
    text = vm.context.first_screen.conclusion.value_text
    assert text.startswith("FAKE 示意結論：")                         # 明確標 FAKE（⛔ 當真結論）
    clauses = text.split("：", 1)[1].split("；")
    assert len(clauses) >= 2 and all(c.strip() for c in clauses)
    for card in vm.context.cards:
        f = card.field
        if f.status_text:
            assert f"{f.label} {f.status_text}" in clauses, f"{scenario}: {f.label} 缺值沒有在結論句明寫"
    cur = vm.context.first_screen.current_state
    assert any(c.startswith("市場目前狀態 ") and (cur.value_text or cur.status_text) in c for c in clauses)


def test_conclusion_cold_is_gray_not_loaded_not_a_sentence():
    c = _conclusion("cold")
    assert c.state is FieldState.NOT_EVALUATED and c.status_text == T.TEXT_NOT_LOADED and c.value_text is None
    h = H.conclusion_row_html(c)
    assert "ui2-chip--danger" not in h and T.TEXT_NOT_LOADED in h


def test_vm_passes_conclusion_through_verbatim_never_derives_it():
    """VM 原樣帶出 canonical 的句子；改 regime 值不會讓 VM 長出任何結論字樣。"""
    c = fake_canonical(P4_MARKET, "loaded")
    c["conclusion"]["value"] = "FAKE 任意句子 XYZ；第二句"
    assert build_market_page_vm(c).context.first_screen.conclusion.value_text == "FAKE 任意句子 XYZ；第二句"
    c2 = fake_canonical(P4_MARKET, "loaded")
    c2["current_state"]["value"] = "ZZZ"
    del c2["conclusion"]                                               # 沒給結論 → VM 不得自己生一句
    assert build_market_page_vm(c2).context.first_screen.conclusion is None


def test_conclusion_and_main_risk_only_on_market_page():
    for page in (P4_TARGET, P4_HOLD, P4_ME):
        c = fake_canonical(page, "loaded")
        assert c.get("conclusion") is None and c.get("main_risk") is None
        for key, spec in (("conclusion", {"label": "今日結論", "value": "x"}),
                          ("main_risk", {"label": "今日主要風險", "value": "x"})):
            bad = dict(c, **{key: spec})
            with pytest.raises(ValueError):
                vm_common.build_page_vm(bad)


_VM_DIRECTION_SOURCES = [p for p in UI2_FILES]


@pytest.mark.parametrize("path", _VM_DIRECTION_SOURCES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_direction_words_anywhere_in_ui2_source(path):
    """VM／UI2 原始碼（含 FAKE 值）不含多空方向字樣 → 結論不可能由 UI2 推導出方向。"""
    src = path.read_text(encoding="utf-8")
    for w in _DIRECTION_WORDS:
        assert w not in src, f"{path.name} 含方向字樣 {w!r}"


def test_conclusion_is_first_row_of_the_first_screen_block():
    vm = get_preview_page_vm(P4_MARKET, "loaded")
    h = H.first_screen_html(vm.context.first_screen)
    qs = re.findall(r'data-ui2-q="(\w+)"', h)
    assert qs == ["concl", "q1", "ctx", "q2", "q3", "q4"]


# ════════════════════════════════════════════════════════════════════
# 2. 今日主要風險：L1、緊接第一屏、退化句逐字（DEC-117 Q6）
# ════════════════════════════════════════════════════════════════════
LEGACY_BLOCKS = (ROOT / "src" / "ui" / "views" / "_market_blocks.py").read_text(encoding="utf-8")


def test_dec117_q6_sentences_are_verbatim_with_legacy_source():
    """退化／護欄句與 Legacy `_market_blocks.py` 逐字比對（不 import；讀原始碼）。"""
    assert f'NOT_LOADED: str = "{T.RISK_SENTENCE_NOT_LOADED}"' in LEGACY_BLOCKS
    assert f'UNDETERMINED: str = "{T.TEXT_RISK_CAP_UNDETERMINABLE}"' in LEGACY_BLOCKS
    assert "（五桶資料皆不足）" in LEGACY_BLOCKS and T.RISK_SENTENCE_ALL_INSUFFICIENT == "⬜ 無法判定（五桶資料皆不足）"
    assert T.RISK_NOTE_UNEVALUATED_NOT_SAFE in LEGACY_BLOCKS
    assert T.RISK_ERROR_FMT.split("{")[0] in LEGACY_BLOCKS
    assert T.RISK_SENTENCE_NOT_LOADED.startswith(T.TEXT_NOT_LOADED)               # 前綴落在既有 Not Evaluated 表
    assert T.RISK_SENTENCE_ALL_INSUFFICIENT.startswith(T.TEXT_RISK_CAP_UNDETERMINABLE)   # 前綴落在判定結果表


def _risk(scenario: str) -> FieldVM:
    r = get_preview_page_vm(P4_MARKET, scenario).context.main_risk
    assert r is not None
    return r


def test_main_risk_per_scenario_uses_the_right_axis_and_verbatim_sentence():
    cold = _risk("cold")
    assert cold.state is FieldState.NOT_EVALUATED and cold.status_text == T.RISK_SENTENCE_NOT_LOADED
    assert cold.value_text is None and "danger" not in H.status_chip_html(cold)       # 冷啟動：灰、不出風險項列
    miss = _risk("missing")
    assert miss.state is JudgementState.UNDETERMINABLE and miss.status_text == T.RISK_SENTENCE_ALL_INSUFFICIENT
    assert miss.layer == "judgement" and miss.state != FieldState.NOT_EVALUATED
    ne = _risk("not_evaluated")
    assert ne.state is FieldState.NOT_EVALUATED and ne.detail == T.RISK_NOTE_UNEVALUATED_NOT_SAFE
    un = _risk("unavailable")
    assert un.state is FieldState.UNAVAILABLE and un.detail.startswith("五桶風險摘要算不出來：")
    assert "ui2-chip--danger" in H.status_chip_html(un)                                  # 真錯誤才紅
    for sc in ("loaded", "stale"):
        f = _risk(sc)
        assert f.capability is CapabilityState.NOT_PROVIDED and f.state is None and f.layer == "capability"


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_main_risk_never_says_safe_or_no_risk_and_never_lists_items(scenario):
    f = _risk(scenario)
    h = H.main_risk_html(f)
    text = _txt(h)
    for bad in ("無風險", "沒有風險", "安全無虞", "✅", "ui2-chip--positive", "可加碼", "無需調整"):
        assert bad not in h and bad not in text
    assert f.value_text is None                        # Preview：不產生風險項（燈色＋桶名＋燈名＋方向）
    assert 'data-ui2-l1="main_risk"' in h


def test_main_risk_directly_follows_first_screen_block_in_one_l1_container():
    vm = get_preview_page_vm(P4_MARKET, "loaded")
    h = H.market_l1_html(vm.context.first_screen, vm.context.main_risk)
    assert h.startswith('<div class="ui2-m-l1"><div class="ui2-qa">')
    i_q4 = h.index('data-ui2-q="q4"')
    i_risk = h.index('class="ui2-risk"')
    assert i_q4 < i_risk and h.count('class="ui2-risk"') == 1
    between = h[i_q4:i_risk]
    assert "ui2-card" not in between and "ui2-grid" not in between and "stExpander" not in between


def _market_dom_order(scenario: str) -> list[str]:
    """整頁實際渲染的元素順序（AppTest；每個元素一個標記）。"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.query_params["ui2_dev"] = "1"          # P1：場景／帳戶切換控制只在開發面（?ui2_dev=1）
    at.run(timeout=60)
    at.selectbox(key="ui2_scenario").set_value(scenario).run(timeout=60)
    assert not at.exception
    out: list[str] = []
    for node in at.main:
        t = getattr(node, "type", "")
        if t == "expander":
            out.append("expander")
        else:
            v = getattr(node, "value", "") or ""
            for tok in ("ui2-m-l1", "ui2-risk", "ui2-grid", "ui2-section-title", "ui2-banner", "ui2-pagetitle"):
                if f'class="{tok}"' in v or f'class="{tok} ' in v:
                    out.append(tok)
    return out


@pytest.mark.parametrize("scenario", ["cold", "loaded", "unavailable"])
def test_main_risk_is_not_interleaved_by_expanders_in_the_real_page(scenario):
    order = _market_dom_order(scenario)
    assert order.index("ui2-m-l1") < order.index("ui2-grid")
    first_after = [t for t in order[order.index("ui2-m-l1") + 1:] if t in ("ui2-grid", "ui2-section-title", "expander")]
    # DEC-128／129：舊版強制「緊接 L1 之後必為卡片」（會擋住 Wireframes 的 OneBrain／Primary 圖順序，且以 L2／L3 為前提）
    # ——改為只守「L1 之後不得被 expander 插隊」；整頁 0 個完整 evidence expander 見 tests/test_ui2_contract_teeth_pending.py。
    assert first_after and first_after[0] != "expander"
    # 今日主要風險與四問同在 ui2-m-l1 這一個元素內（不可能被其他元素插隊）
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.query_params["ui2_dev"] = "1"          # P1：場景／帳戶切換控制只在開發面（?ui2_dev=1）
    at.run(timeout=60)
    at.selectbox(key="ui2_scenario").set_value(scenario).run(timeout=60)
    l1 = [m.value for m in at.markdown if 'class="ui2-m-l1"' in m.value]
    assert len(l1) == 1 and l1[0].index('data-ui2-q="q4"') < l1[0].index("ui2-risk")


# （原 order_checker_has_teeth 為自證式 tautology，已刪；真正的牙＝上方 AppTest 整頁順序測試，mutation「卡片先於 L1」實測轉紅）


# ════════════════════════════════════════════════════════════════════
# 3. 🎯 標的：雙模式、搜尋、查一檔 FAKE、session 隔離
# ════════════════════════════════════════════════════════════════════
def _target(scenario="loaded", mode=None) -> PageVM:
    return get_preview_page_vm(P4_TARGET, scenario, mode=mode)


def test_target_has_exactly_two_modes_curated_default():
    vm = _target()
    t = vm.context.target
    assert tuple(m.mode_id for m in t.modes) == MODE_IDS == (MODE_CURATED, MODE_LOOKUP)
    assert [m.label for m in t.modes] == ["市場精選", "即時查一檔"] == [MODE_LABELS[m] for m in MODE_IDS]
    assert t.default_mode == MODE_CURATED and vm.slice.active_mode == MODE_CURATED


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_mode_changes_only_the_slice_never_the_context(scenario):
    """Presentation Slice ≠ Decision Context：兩個模式的 context 逐欄相等，只有 slice 不同。"""
    a, b = _target(scenario, MODE_CURATED), _target(scenario, MODE_LOOKUP)
    assert a.context == b.context
    assert a.slice.active_mode == MODE_CURATED and b.slice.active_mode == MODE_LOOKUP
    assert a.slice.visible_card_ids and b.slice.visible_card_ids == ()          # 查一檔：精選收合
    assert len(b.context.cards) == len(a.context.cards) > 0                     # 但完整候選仍在 context


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        get_preview_page_vm(P4_TARGET, "loaded", mode="both")


def _at_target(scenario: str):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.query_params["ui2_dev"] = "1"          # P1：場景／帳戶切換控制只在開發面（?ui2_dev=1）
    at.run(timeout=60)
    at.selectbox(key="ui2_scenario").set_value(scenario).run(timeout=60)
    at.radio(key="ui2_page").set_value(P4_TARGET).run(timeout=60)
    assert not at.exception
    return at


def _page_blob(at) -> str:
    return "\n".join(m.value for m in at.markdown)


@pytest.mark.parametrize("scenario", ["cold", "loaded", "unavailable"])
def test_modes_are_never_fully_expanded_together(scenario):
    at = _at_target(scenario)
    blob = _page_blob(at)
    assert 'data-ui2-mode-content="curated"' in blob and 'data-ui2-mode-content="lookup"' not in blob
    at.radio(key="ui2_target_mode").set_value(MODE_LOOKUP).run(timeout=60)
    assert not at.exception
    blob = _page_blob(at)
    assert 'data-ui2-mode-content="lookup"' in blob and 'data-ui2-mode-content="curated"' not in blob
    assert 'class="ui2-grid"' not in blob and 'class="ui2-grid" ' not in blob   # 精選卡網格收合
    at.radio(key="ui2_target_mode").set_value(MODE_CURATED).run(timeout=60)
    blob = _page_blob(at)
    assert 'data-ui2-mode-content="curated"' in blob and 'data-ui2-mode-content="lookup"' not in blob


# （原 mode_exclusivity_checker_has_teeth 為自證式 tautology，已刪；真正的牙＝test_modes_are_never_fully_expanded_together，mutation「兩模式同時渲染」實測轉紅）


def test_search_box_and_cta_present_in_both_modes_and_not_actionable():
    for mode in MODE_IDS:
        vm = _target("loaded", mode)
        s = vm.context.target.search
        h = H.search_html(s)
        assert 'role="searchbox" aria-disabled="true"' in h and "查詢" in h and 'data-ui2-q="q4"' in h   # 搜尋框本身也是 disabled 示意
        assert s.cta.enabled is False and 'aria-disabled="true"' in h
        for token in ("<input", "<button", "<form", "href=", "onclick"):
            assert token not in h
    s = _target().context.target.search
    assert s.name_search.layer == "capability" and "名稱搜尋" in s.name_search.label    # 名稱搜尋 capability 誠實提示


def test_fake_lookup_result_is_labelled_fake_and_has_no_real_ticker():
    lk = _target("loaded", MODE_LOOKUP).context.target.lookup
    h = H.lookup_result_html(lk)
    assert lk.ticker_text.startswith("FAKE") and lk.name_text.startswith("FAKE")
    assert not re.search(r"(?<![\w-])\d{4}(?![\w])", _txt(h)), "不得出現真實股票代號樣式"
    assert 'data-ui2-mode-content="lookup"' in h
    assert all(c.tone.value == "neutral_info" for c in lk.chips)                  # 類型／產業＝Neutral/Info


def test_six_dim_snapshot_order_and_semantics():
    lk = _target("loaded", MODE_LOOKUP).context.target.lookup
    labels = [f.label for f in lk.snapshot]
    assert labels == ["基本面", "估值", "籌碼", "趨勢", "產業", "市場環境"]
    assert labels[0] != "市場環境"                                  # W-4：市場環境不排第一格
    byl = {f.label: f for f in lk.snapshot}
    for k in ("趨勢", "產業"):                                       # DEC-092 Q2：尚未定義（固定）
        assert byl[k].state is FieldState.NOT_EVALUATED and byl[k].status_text == T.TEXT_NOT_DEFINED


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_target_creates_no_buy_judgement_or_action_authority(scenario):
    vm = _target(scenario, MODE_LOOKUP)
    t = vm.context.target
    texts = [t.lookup.ticker_text, t.lookup.name_text, t.lookup.isolation_note, t.lookup.add_watch_cta.label,
             t.lookup.add_watch_cta.disabled_reason or "", t.search.cta.label]
    for f in (*t.lookup.snapshot, t.lookup.summary, t.search.name_search, *vm.context.first_screen.context_rows):
        texts += [f.label, f.value_text or "", f.status_text or "", f.detail or ""]
    blob = "\n".join(texts).replace(T.TEXT_NOT_PROVIDED_AGGREGATOR, "")
    for w in ("加碼", "減碼 1/2", "全出", "買進", "賣出", "可以買", "不能買", "不可買", "建議買", "今日無需調整",
              "今日需處理", "可買", "強烈"):
        assert w not in blob, f"{scenario}: 出現買賣／動作字樣 {w!r}"
    a = vm.context.first_screen.action_needed
    assert a.capability is CapabilityState.NOT_PROVIDED and "動作權威＝💼 持股" in (a.detail or "")  # 無第二套 action authority


def test_add_to_watch_cta_is_disabled_and_has_no_write_logic():
    for sc in SCENARIO_IDS:
        c = _target(sc, MODE_LOOKUP).context.target.lookup.add_watch_cta
        assert c.enabled is False and "尚未提供" in c.label and c.disabled_reason
        h = H.cta_html(c)
        assert 'aria-disabled="true"' in h and "ui2-cta--disabled" in h
        assert "<button" not in h and "onclick" not in h


def test_w4_context_row_is_light_neutral_and_below_summary():
    vm = _target("loaded")
    rows = vm.context.first_screen.context_rows
    assert [r.label for r in rows] == ["市場位階", "Risk Cap"]
    h = H.target_first_screen_html(vm.context.first_screen, vm.context.first_screen.current_state)
    assert re.findall(r'data-ui2-q="(\w+)"', h) == ["q1", "ctx", "q2", "q3"]
    ctx = h[h.index('data-ui2-q="ctx"'):h.index('data-ui2-q="q2"')]
    for cls in ("ui2-chip--warning", "ui2-chip--danger", "ui2-chip--positive"):
        assert cls not in ctx                                       # loaded：市場訊號不以警示色主導
    assert "ui2-chip--neutral" in ctx and T.TEXT_RISK_CAP_UNDETERMINABLE in ctx
    assert ".ui2-ctxline{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:.78rem}" in __import__(
        "src.ui2.shell.css", fromlist=["CSS"]).CSS                   # 字級小於查詢摘要（16px）


def test_target_market_regime_follows_the_same_market_context():
    """同一份 market context：標的頁位階值＝市場頁位階值（各場景同步，⛔ 各說各話）。"""
    for sc in SCENARIO_IDS:
        m = get_preview_page_vm(P4_MARKET, sc).context.first_screen.current_state
        t = next(r for r in _target(sc).context.first_screen.context_rows if r.label == "市場位階")
        assert (t.state, t.value_text, t.status_text) == (m.state, m.value_text, m.status_text)


_ISOLATION_BANNED = ("gspread", "gsheet", "worksheet", "append_row", "update_cell", "requests", "read_csv",
                     "to_csv", "to_parquet", "to_json", "sqlite3", "yfinance", "urlopen", "fetch_", "watchlist",
                     "portfolio_write", "set_candidate", "save_strategy")


def check_adhoc_isolation(source: str) -> list[str]:
    """Ad-hoc 查詢 session-only：UI2 原始碼不得出現任何寫入／取數識別字。"""
    bad = []
    for n in ast.walk(ast.parse(source)):
        names: list[str] = []
        if isinstance(n, ast.Name):
            names.append(n.id)
        elif isinstance(n, ast.Attribute):
            names.append(n.attr)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            names += [a.name for a in n.names] + ([n.module] if isinstance(n, ast.ImportFrom) and n.module else [])
        for nm in names:
            for b in _ISOLATION_BANNED:
                if b.lower() in nm.lower():
                    bad.append(f"L{getattr(n, 'lineno', '?')}: 識別字 {nm!r} 含 {b!r}")
    return bad


_TARGET_FILES = [ROOT / "src/ui2/views/target.py", ROOT / "src/ui2/shell/app.py", ROOT / "src/ui2/components/html.py"]


@pytest.mark.parametrize("path", _TARGET_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_adhoc_lookup_code_has_no_write_or_fetch_identifiers(path):
    assert check_adhoc_isolation(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("injected", [
    "import gspread\n", "ws.append_row([1])\n", "import requests\n", "df.to_csv('x')\n",
    "from src.data.core.data_loader import fetch_price\n", "save_watchlist(x)\n",
])
def test_adhoc_isolation_guard_has_teeth(injected):
    clean = (ROOT / "src/ui2/views/target.py").read_text(encoding="utf-8")
    assert check_adhoc_isolation(clean) == []
    assert check_adhoc_isolation(injected + clean)


def test_lookup_writes_only_ui2_prefixed_session_state():
    """查詢（模式切換）前後，session_state 只有 `ui2_` 前綴 key；⛔ 持股／觀察／Sheet／strategy 類 key。"""
    at = _at_target("loaded")
    before = set(at.session_state.filtered_state)
    at.radio(key="ui2_target_mode").set_value(MODE_LOOKUP).run(timeout=60)
    after = set(at.session_state.filtered_state)
    for k in before | after:
        assert str(k).startswith("ui2_"), f"非 ui2_ 前綴的 session key：{k}"
        for w in ("watch", "portfolio", "gsheet", "sheet", "strategy", "candidate", "holding"):
            assert w not in str(k).lower()
    assert "ui2_target_mode" in after


def test_target_mode_key_constants_agree_between_shell_and_view():
    from src.ui2.shell import app as shell_app
    from src.ui2.views import target as target_view
    assert shell_app.KEY_TARGET_MODE == target_view.KEY_TARGET_MODE == "ui2_target_mode"


# ════════════════════════════════════════════════════════════════════
# 4. 👤 我的：三種帳戶狀態；無 OAuth／Sheet
# ════════════════════════════════════════════════════════════════════
def _me(account: str, scenario="loaded") -> PageVM:
    return get_preview_page_vm(P4_ME, scenario, account=account)


_PRIMARY = {ACCOUNT_SIGNED_OUT: "Google 登入", ACCOUNT_SIGNED_IN: "切換 Sheet", ACCOUNT_UNAVAILABLE: "重新讀取"}


@pytest.mark.parametrize("account", ACCOUNT_IDS)
def test_me_three_account_states_have_the_right_primary_cta_and_disabled_actions(account):
    vm = _me(account)
    assert vm.context.account.account_state == account
    assert vm.context.first_screen.primary_cta.label == _PRIMARY[account]
    assert vm.context.first_screen.primary_cta.enabled is False
    assert vm.context.account.actions and all(a.enabled is False for a in vm.context.account.actions)
    assert _PRIMARY[account] in [a.label for a in vm.context.account.actions]
    h = H.account_actions_html(vm.context.account)
    assert h.count('aria-disabled="true"') == len(vm.context.account.actions)
    assert "<button" not in h and "onclick" not in h and "href=" not in h


def test_me_signed_out_signed_in_unavailable_semantics_and_axes():
    out, sin, un = _me(ACCOUNT_SIGNED_OUT), _me(ACCOUNT_SIGNED_IN), _me(ACCOUNT_UNAVAILABLE)
    by = lambda vm: {c.card_id: c.field for c in vm.context.cards}
    assert by(out)["google"].state is FieldState.OK and by(out)["google"].value_text == "尚未登入"
    for k in ("sheet", "portfolio", "watchlist"):                      # 登入前：依賴登入的欄位＝Missing 未備（不適用）
        assert by(out)[k].state is FieldState.MISSING and by(out)[k].status_text == T.TEXT_MISSING_NOT_READY
    assert by(sin)["sheet"].state is FieldState.OK
    assert by(un)["sheet"].state is FieldState.UNAVAILABLE and "Sheet 讀取失敗" in by(un)["sheet"].detail
    assert by(un)["portfolio"].state is FieldState.MISSING             # 讀不到＝未取得（⛔ 補 0／當空）
    # 連線事實全落在「資料語意」軸；不借用判定結果或 capability
    for vm in (out, sin, un):
        fs = vm.context.first_screen
        for f in (fs.current_state, fs.action_needed, fs.next_step, *[c.field for c in vm.context.cards]):
            if vm.context.account.account_state != ACCOUNT_SIGNED_IN or vm.scenario_id == "loaded":
                assert f.layer == "data", f"{vm.context.account.account_state}/{f.label}: {f.layer}"
    # unavailable 只有真錯誤才紅；signed-out 是灰
    assert "ui2-chip--danger" in H.status_chip_html(by(un)["sheet"])
    for f in (by(out)["sheet"], by(out)["google"]):
        assert "ui2-chip--danger" not in H.status_chip_html(f)


def test_me_account_param_validated_and_ignored_by_other_pages():
    with pytest.raises(ValueError):
        get_preview_page_vm(P4_ME, "loaded", account="admin")
    for page in (P4_MARKET, P4_TARGET, P4_HOLD):
        assert get_preview_page_vm(page, "loaded", account=ACCOUNT_SIGNED_OUT) == get_preview_page_vm(page, "loaded")


def test_me_default_account_is_unchanged_from_batch2_content():
    vm = get_preview_page_vm(P4_ME, "loaded")
    assert vm.context.account.account_state == ACCOUNT_SIGNED_IN
    assert [c.card_id for c in vm.context.cards] == ["google", "sheet", "portfolio", "watchlist"]


def test_me_page_switches_account_in_the_real_app():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.query_params["ui2_dev"] = "1"          # P1：場景／帳戶切換控制只在開發面（?ui2_dev=1）
    at.run(timeout=60)
    at.radio(key="ui2_page").set_value(P4_ME).run(timeout=60)
    for acct in ACCOUNT_IDS:
        at.selectbox(key="ui2_account").set_value(acct).run(timeout=60)
        assert not at.exception
        blob = _page_blob(at)
        assert f'data-ui2-account="{acct}"' in blob and _PRIMARY[acct] in blob
    assert all(str(k).startswith("ui2_") for k in at.session_state.filtered_state)


_OAUTH_SHEET_BANNED = ("oauth", "gsheet", "gspread", "google_auth", "googleapiclient", "st.login", "st.user",
                       "experimental_user", "secrets", "access_token", "refresh_token", "client_secret",
                       "get_finmind_token", "append_row", "worksheet", "requests")


def check_no_oauth_or_sheet(source: str) -> list[str]:
    """👤 我的頁：⛔ 真 Google OAuth／Sheet 讀寫／secrets。檢查 import、識別字與屬性鏈（AST；字串字面值不算）。"""
    bad = []
    tree = ast.parse(source)
    for n in ast.walk(tree):
        names: list[str] = []
        if isinstance(n, ast.Import):
            names += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            names += [n.module or ""] + [a.name for a in n.names]
        elif isinstance(n, ast.Name):
            names.append(n.id)
        elif isinstance(n, ast.Attribute):
            try:
                names.append(ast.unparse(n))
            except Exception:
                names.append(n.attr)
        for nm in names:
            low = nm.lower()
            for b in _OAUTH_SHEET_BANNED:
                if b in low:
                    bad.append(f"L{getattr(n, 'lineno', '?')}: {nm!r} 含 {b!r}")
    return bad


@pytest.mark.parametrize("path", UI2_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_ui2_has_no_oauth_sheet_or_secrets_call(path):
    assert check_no_oauth_or_sheet(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("injected", [
    "from src.data.portfolio import oauth_state\n", "from src.data.portfolio.gsheet_portfolio import load\n",
    "import gspread\n", "x = st.secrets['k']\n", "st.login()\n", "from google.oauth2 import service_account\n"
    "import google_auth_oauthlib\n", "tok = session.access_token\n",
])
def test_oauth_sheet_guard_has_teeth(injected):
    clean = (ROOT / "src/ui2/views/me.py").read_text(encoding="utf-8")
    assert check_no_oauth_or_sheet(clean) == []
    assert check_no_oauth_or_sheet(injected + clean)


# ════════════════════════════════════════════════════════════════════
# 5. 三軸不混層；無人名
# ════════════════════════════════════════════════════════════════════
def _batch3_fields() -> list[tuple[str, str, FieldVM]]:
    out = []
    for sc in SCENARIO_IDS:
        m = get_preview_page_vm(P4_MARKET, sc)
        out += [(f"market/{sc}", "conclusion", m.context.first_screen.conclusion),
                (f"market/{sc}", "main_risk", m.context.main_risk)]
        t = get_preview_page_vm(P4_TARGET, sc).context.target
        out += [(f"target/{sc}", f"dim:{f.label}", f) for f in t.lookup.snapshot] + [
            (f"target/{sc}", "summary", t.lookup.summary), (f"target/{sc}", "name_search", t.search.name_search)]
    for a in ACCOUNT_IDS:
        vm = _me(a)
        out += [(f"me/{a}", c.card_id, c.field) for c in vm.context.cards]
    return out


def check_axis_consistency(fields) -> list[str]:
    """每個欄位：layer 與 state／capability／status_text 所屬字樣表一致（三軸不混層）。"""
    bad = []
    tables = {"data": [p for v in T.ALLOWED_STATUS_PREFIXES.values() for p in v],
              "judgement": [p for v in T.JUDGEMENT_STATUS_PREFIXES.values() for p in v],
              "capability": [p for v in T.CAPABILITY_STATUS_PREFIXES.values() for p in v]}
    for where, name, f in fields:
        layer = f.layer
        if layer == "capability" and f.state is not None:
            bad.append(f"{where}/{name}: capability 帶了 state")
        if layer == "judgement" and not isinstance(f.state, JudgementState):
            bad.append(f"{where}/{name}: judgement 軸的 state 型別錯誤")
        if layer == "data" and not isinstance(f.state, FieldState):
            bad.append(f"{where}/{name}: data 軸的 state 型別錯誤")
        if f.status_text:
            owners = [k for k, v in tables.items() if f.status_text.startswith(tuple(v))]
            if owners != [layer]:
                bad.append(f"{where}/{name}: 字樣 {f.status_text!r} 屬 {owners}，欄位宣告 {layer}")
    return bad


def test_batch3_fields_never_cross_axes():
    fields = _batch3_fields()
    assert len(fields) > 60
    assert check_axis_consistency(fields) == []


def test_axis_checker_has_teeth():
    f = FieldVM("x", FieldState.NOT_EVALUATED, None, T.TEXT_NOT_EVALUATED)
    # 偽造：把判定結果字樣掛到資料語意軸（FieldVM 建構會擋；此處用 object.__setattr__ 繞過，證明 checker 也會抓）
    g = FieldVM("x", FieldState.NOT_EVALUATED, None, T.TEXT_NOT_EVALUATED)
    object.__setattr__(g, "status_text", T.TEXT_RISK_CAP_UNDETERMINABLE)
    assert check_axis_consistency([("w", "ok", f)]) == []
    assert check_axis_consistency([("w", "bad", g)])
    h = FieldVM("x", None, None, T.TEXT_NOT_PROVIDED, capability=CapabilityState.NOT_PROVIDED)
    object.__setattr__(h, "state", FieldState.OK)
    assert check_axis_consistency([("w", "cap+state", h)])


def test_unable_to_determine_is_never_not_evaluated_in_batch3():
    for _, name, f in _batch3_fields():
        if f.status_text and f.status_text.startswith(T.TEXT_RISK_CAP_UNDETERMINABLE):
            assert f.layer == "judgement" and f.state is not FieldState.NOT_EVALUATED
        if f.state is FieldState.NOT_EVALUATED:
            assert not (f.status_text or "").startswith(T.TEXT_RISK_CAP_UNDETERMINABLE)


# 名單與 tests/test_b2a_breach_and_naming.py 的守衛黑名單同源（刻意保留的檢查清單，非去識別化殘留）
_BANNED_PERSON_TOKENS = ("陳重銘", "林明樟", "明樟", "孫慶龍", "郭俊宏", "蔡森", "春哥", "弘爺", "宏爺", "妮可",
                         "朱家泓", "林穎", "老師", "大師", "師父", "超級數字力", "Minervini", "caisen")
_MJ_RE = re.compile(r"(?<![0-9A-Za-z])MJ(?![0-9A-Za-z])")


def check_no_person_names(src: str) -> list[str]:
    hits = [t for t in _BANNED_PERSON_TOKENS if t.lower() in src.lower()]
    if _MJ_RE.search(src):
        hits.append("MJ")
    return hits


@pytest.mark.parametrize("path", UI2_FILES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_person_names_in_ui2_source(path):
    """PROJECT_RULES §28：New UI2 字樣與識別字不得出現人名。"""
    assert check_no_person_names(path.read_text(encoding="utf-8")) == []


def test_no_person_names_in_any_rendered_text():
    blob = []
    for sc in SCENARIO_IDS:
        for p in PAGE_IDS:
            for acct in ACCOUNT_IDS:
                vm = get_preview_page_vm(p, sc, account=acct, mode=MODE_LOOKUP)
                blob.append(repr(vm))
    s = "\n".join(blob)
    for tok in _BANNED_PERSON_TOKENS:
        assert tok.lower() not in s.lower()


def test_name_guard_has_teeth():
    clean = (ROOT / "src/ui2/views/me.py").read_text(encoding="utf-8")
    assert check_no_person_names(clean) == []
    for inj in ("# 蔡森\n", "x = 'MJ'\n", "# caisen_x\n", "label = '老師'\n"):
        assert check_no_person_names(inj + clean), inj


# ════════════════════════════════════════════════════════════════════
# 6. 既有契約不被削弱（Batch 3 新增欄位 frozen、additive）
# ════════════════════════════════════════════════════════════════════
def test_new_vm_fields_are_frozen_and_optional():
    vm = get_preview_page_vm(P4_MARKET, "loaded")
    with pytest.raises(Exception):
        vm.context.main_risk = None            # type: ignore[misc]
    with pytest.raises(Exception):
        vm.context.first_screen.conclusion = None   # type: ignore[misc]
    hold = get_preview_page_vm(P4_HOLD, "loaded")
    assert hold.context.main_risk is None and hold.context.target is None and hold.context.account is None
    assert hold.context.first_screen.conclusion is None and hold.slice.active_mode is None


def test_context_independent_of_top_n_still_holds_with_modes():
    base = _target("loaded").context
    for n in (None, 0, 1, 5, 99):
        assert get_preview_page_vm(P4_TARGET, "loaded", top_n=n).context == base


# ════════════════════════════════════════════════════════════════════
# 7. viewport 判定器（Batch 3 新增檢查）：對好資料必綠、對注入違規必紅（判定器有牙）
# ════════════════════════════════════════════════════════════════════
import copy  # noqa: E402

from tests.test_ui2_batch2 import _good_desktop, _good_mobile  # noqa: E402
from tests.ui2_viewport import measure_viewport as MV  # noqa: E402


def _el(q, top, bottom, left=14.0):
    return {"q": q, "text": q, "top": top, "bottom": bottom, "left": left, "right": left + 300, "height": bottom - top,
            "width": 300.0}


def _m_market(desktop: bool = False) -> dict:
    m = _good_desktop() if desktop else _good_mobile()
    left = 200.0 if desktop else 14.0
    if desktop:   # 三 tile：q1／ctx／risk 同列
        els = [_el("q4", 60, 98, left), _el("concl", 100, 150, left), _el("q1", 160, 260, left), _el("ctx", 160, 260, 500),
               _el("q2", 270, 330, left), _el("q3", 340, 400, left)]
        risk = {"top": 160.0, "bottom": 260.0, "left": 900.0, "right": 1300.0, "inside_l1": True, "text": "r"}
    else:
        els = [_el("q4", 60, 98), _el("concl", 100, 150), _el("q1", 150, 210), _el("ctx", 210, 260),
               _el("q2", 260, 320), _el("q3", 320, 380)]
        risk = {"top": 455.0, "bottom": 520.0, "left": 14.0, "right": 376.0, "inside_l1": True, "text": "r"}
    m.update(page="p4_market", scenario="loaded", expanders=[],     # P3：真瀏覽器量測 dict 必須帶 expanders 鍵
             elements=els, risk=risk, first_block_after_l1_top=530.0,
             risk_line_height=24.0, scroll_end_bottom=764.0, risk_bottom_at_scroll_end=300.0)
    # P2（DEC-133）：真瀏覽器 market 量測 dict 必須帶 `p2` 鍵（OneBrain → 空槽 → 指標卡，皆在今日主要風險／q3 之後）
    spec = "SPEC｜最新收盤參考｜X｜資料日 2026-11-02｜缺值不補"
    ob, sl, gr = (({"top": 410.0, "bottom": 440.0}, {"top": 448.0, "bottom": 540.0}, {"top": 548.0, "bottom": 700.0})
                  if desktop else
                  ({"top": 530.0, "bottom": 560.0}, {"top": 568.0, "bottom": 650.0}, {"top": 658.0, "bottom": 780.0}))
    m["p2"] = {"onebrain": ob, "slot": sl, "grid": gr, "slot_graphics": 0, "slot_danger": 0,
               "slot_text": "🇹🇼 台股趨勢 ⬜ 尚未提供 此項目尚未開放 " + spec, "spec_text": spec}
    return m


def _m_target() -> dict:
    m = _good_mobile()
    els = [_el("q4", 140, 190), _el("q1", 200, 260), _el("ctx", 262, 290), _el("q2", 292, 340), _el("q3", 342, 390)]
    m.update(page="p4_target", scenario="loaded", elements=els, expanders=[],
             mode_box={"top": 90.0, "bottom": 130.0, "labels": ["市場精選", "即時查一檔"], "checked_count": 1,
                       "checked_index": 0},
             mode_content={"curated": True, "lookup": False}, font_sizes={"q1": 16.0, "ctx": 12.5},
             snapshot_labels=[])
    return m


def _m_me() -> dict:
    m = _good_mobile()
    for e in m["elements"]:
        if e["q"] == "q4":
            e["text"] = "④ 主 CTA 切換 Sheet"
    m.update(page="p4_me", scenario="loaded", expanders=[], account={"top": 460.0, "bottom": 520.0, "state": "signed_in"})
    return m


def _mut3(base, fn) -> set[str]:
    m = copy.deepcopy(base())
    fn(m)
    return {k for k, v in MV.evaluate(m).items() if v}


def test_batch3_evaluator_accepts_good_states():
    for m in (_m_market(), _m_market(desktop=True), _m_target(), _m_me()):
        assert {k for k, v in MV.evaluate(m).items() if v} == set()


def test_batch3_thresholds_registered_with_sources():
    ids = {t["id"] for t in MV.THRESHOLDS}
    for i in ("market_conclusion_in_first_screen", "market_main_risk_follows_first_screen",
              "target_mode_search_first_screen", "target_mode_exclusive", "target_w4_context_light",
              "me_account_state_first_screen"):
        assert i in ids
    for t in MV.THRESHOLDS:
        assert re.search(r"Freeze|Gate|Wireframes|客戶|Checklist", t["source"])


def _el_of(m, q):
    return next(e for e in m["elements"] if e["q"] == q)


@pytest.mark.parametrize("name,base,fn,check", [
    ("結論缺", _m_market, lambda m: m["elements"].remove(_el_of(m, "concl")), "market_conclusion_in_first_screen"),
    ("結論太低", _m_market, lambda m: _el_of(m, "concl").update(bottom=792.0), "market_conclusion_in_first_screen"),
    ("結論在 ① 之下", _m_market, lambda m: _el_of(m, "concl").update(top=300.0, bottom=330.0),
     "market_conclusion_in_first_screen"),
    ("風險缺", _m_market, lambda m: m.update(risk=None), "market_main_risk_follows_first_screen"),
    ("風險被移出 L1", _m_market, lambda m: m["risk"].update(inside_l1=False), "market_main_risk_follows_first_screen"),
    ("風險早於四問", _m_market, lambda m: m["risk"].update(top=300.0, bottom=360.0),
     "market_main_risk_follows_first_screen"),
    ("風險後被插隊", _m_market, lambda m: m.update(first_block_after_l1_top=500.0),
     "market_main_risk_follows_first_screen"),
    ("CTA 在結論之後（移回最後）", _m_market,
     lambda m: _el_of(m, "q4").update(top=400.0, bottom=450.0), "market_cta_before_conclusion"),
    ("桌機 CTA 在結論之後", lambda: _m_market(True),
     lambda m: _el_of(m, "q4").update(top=410.0, bottom=470.0), "market_cta_before_conclusion"),
    ("缺主 CTA", _m_market, lambda m: m["elements"].remove(_el_of(m, "q4")), "market_cta_before_conclusion"),
    ("主要風險後區塊貼著導覽（2.5px）", _m_market, lambda m: m.update(first_block_after_l1_top=788.5),
     "market_main_risk_nav_margin"),
    ("捲到底後內容被導覽遮住", _m_market, lambda m: m.update(scroll_end_bottom=800.0), "content_not_covered_by_nav"),
    ("桌機不同列", lambda: _m_market(True), lambda m: m["risk"].update(top=400.0, bottom=480.0),
     "market_main_risk_follows_first_screen"),
    ("模式項錯", _m_target, lambda m: m["mode_box"].update(labels=["市場精選", "即時查一檔", "第三種"]),
     "target_mode_search_first_screen"),
    ("兩個都選", _m_target, lambda m: m["mode_box"].update(checked_count=2), "target_mode_search_first_screen"),
    ("搜尋在模式之上", _m_target, lambda m: _el_of(m, "q4").update(top=40.0, bottom=80.0),
     "target_mode_search_first_screen"),
    ("摘要在搜尋之上", _m_target, lambda m: _el_of(m, "q1").update(top=100.0, bottom=130.0),
     "target_mode_search_first_screen"),
    ("兩模式同時展開", _m_target, lambda m: m.update(mode_content={"curated": True, "lookup": True}),
     "target_mode_exclusive"),
    ("選精選卻出查一檔", _m_target, lambda m: m.update(mode_content={"curated": False, "lookup": True}),
     "target_mode_exclusive"),
    ("context 在摘要之上", _m_target, lambda m: _el_of(m, "ctx").update(top=150.0, bottom=180.0),
     "target_w4_context_light"),
    ("context 字級不小", _m_target, lambda m: m.update(font_sizes={"q1": 16.0, "ctx": 16.0}),
     "target_w4_context_light"),
    ("市場環境第一格", _m_target, lambda m: m.update(snapshot_labels=["市場環境", "基本面"]),
     "target_w4_context_light"),
    ("帳戶列缺", _m_me, lambda m: m.update(account=None), "me_account_state_first_screen"),
    ("帳戶狀態未知", _m_me, lambda m: m["account"].update(state="admin"), "me_account_state_first_screen"),
    ("主 CTA 字樣不符", _m_me, lambda m: m["account"].update(state="signed_out"), "me_account_state_first_screen"),
    ("帳戶列太低", _m_me, lambda m: m["account"].update(bottom=815.0), "me_account_state_first_screen"),
])
def test_batch3_evaluator_has_teeth(name, base, fn, check):
    assert check in _mut3(base, fn), f"判定器沒抓到：{name}"


# ════════════════════════════════════════════════════════════════════
# 8. 獨立 QA 修正（F2／F3／F4）
# ════════════════════════════════════════════════════════════════════
def test_f3_lookup_cold_shows_only_search_and_gray_note():
    """Wireframes §6：查一檔冷啟動只有搜尋框＋灰色說明；⛔ FAKE 結果頭／Snapshot／加入觀察。"""
    vm = _target("cold", MODE_LOOKUP)
    lk = vm.context.target.lookup
    assert lk.queried is False and lk.summary.state is FieldState.NOT_EVALUATED
    h = H.lookup_result_html(lk)
    for bad in ("FAKE-0001", "ui2-snapshot", "加入觀察", "ui2-chip--danger"):
        assert bad not in h, bad
    assert 'data-ui2-queried="false"' in h and T.TEXT_NOT_LOADED in h
    for sc in SCENARIO_IDS:
        if sc != "cold":
            assert _target(sc, MODE_LOOKUP).context.target.lookup.queried is True
            assert "FAKE-0001" in H.lookup_result_html(_target(sc, MODE_LOOKUP).context.target.lookup)


def test_f3_lookup_cold_in_real_app_has_no_result_blocks():
    at = _at_target("cold")
    at.radio(key="ui2_target_mode").set_value(MODE_LOOKUP).run(timeout=60)
    blob = _page_blob(at)
    assert 'data-ui2-queried="false"' in blob and 'class="ui2-snapshot"' not in blob and "加入觀察" not in blob
    assert len(at.expander) == 0 or all("研究解釋" not in e.label for e in at.expander)


@pytest.mark.parametrize("scenario", ["stale", "unavailable", "not_evaluated", "missing"])
def test_f2_w4_context_and_market_env_are_neutral_tone_with_text_state(scenario):
    vm = _target(scenario, MODE_LOOKUP)
    ctx = H.ctxline_html(vm.context.first_screen.context_rows)
    snap = H.snapshot_html(vm.context.target.lookup.snapshot)
    env = snap[snap.index('data-dim="市場環境"'):]
    for h in (ctx, env):
        for cls in ("ui2-chip--warning", "ui2-chip--danger", "ui2-chip--positive"):
            assert cls not in h, f"{scenario}: W-4 context 出現 {cls}"
    reg = next(r for r in vm.context.first_screen.context_rows if r.label == "市場位階")
    if reg.status_text:                                   # 狀態以文字標示（⚠／🔴／⬜ 字樣），不靠色調
        assert reg.status_text in _txt(ctx)


def test_f2_non_context_chips_keep_state_tone():
    """只放寬 W-4 的 context／市場環境；其他欄位的 Unavailable 仍紅、Stale 仍琥珀（Freeze §4.1）。"""
    un = _target("unavailable", MODE_LOOKUP).context.target.lookup.snapshot
    assert "ui2-chip--danger" in H.snapshot_html(un)       # 籌碼 Unavailable 仍紅
    st = _target("stale", MODE_LOOKUP).context.target.lookup.snapshot
    assert "ui2-chip--warning" in H.snapshot_html(st)


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_f4_nothing_but_title_precedes_market_l1_in_default_lane(scenario):
    """預設道：市場頁 L1 區塊之前不得有 expander／L2／L3／卡片（含 section 標題）。"""
    order = _market_dom_order(scenario)
    i = order.index("ui2-m-l1")
    before = order[:i]
    assert set(before) <= {"ui2-banner", "ui2-pagetitle"}, f"L1 之前出現 {before}"


# ════════════════════════════════════════════════════════════════════
# 9. 客戶 2026-11-03 裁示（DEC-127）：市場更新 CTA 順序／W-4 驗收／底部導覽餘裕（presentation-only）
# ════════════════════════════════════════════════════════════════════
_MARKET_ORDER = ["q4", "concl", "q1", "ctx", "q2", "q3"]


def _css() -> str:
    from src.ui2.shell.css import CSS
    return CSS


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_cta_order_market_l1_html_puts_refresh_cta_before_conclusion(scenario):
    """Wireframes §2.1／§2.2、DEC-117 Q5：頁首→更新 CTA→今日結論→核心狀態…；risk 仍緊接其後。"""
    vm = get_preview_page_vm(P4_MARKET, scenario)
    h = H.market_l1_html(vm.context.first_screen, vm.context.main_risk)
    qs = re.findall(r'data-ui2-q="(\w+)"', h)
    assert qs[0] == "q4" and qs.index("q4") < qs.index("concl") < qs.index("q1") < qs.index("q2") < qs.index("q3")
    assert h.index('data-ui2-q="q4"') < h.index('data-ui2-q="concl"') < h.index("ui2-risk")


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_cta_order_in_real_page_default_lane(scenario):
    """預設道（AppTest 整頁）：實際輸出的市場 L1 區塊內，CTA 在今日結論之前。"""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.query_params["ui2_dev"] = "1"          # P1：場景／帳戶切換控制只在開發面（?ui2_dev=1）
    at.run(timeout=60)
    at.selectbox(key="ui2_scenario").set_value(scenario).run(timeout=60)
    assert not at.exception
    l1 = [m.value for m in at.markdown if 'class="ui2-m-l1"' in m.value]
    assert len(l1) == 1
    assert l1[0].index('data-ui2-q="q4"') < l1[0].index('data-ui2-q="concl"') < l1[0].index('data-ui2-q="q1"')


def test_cta_first_changes_order_only_not_content():
    """不改 VM 語意：cta_first 與預設版的**文字內容集合**一致（只差順序；唯一差別＝省去 ④ 編號標籤）。"""
    for sc in SCENARIO_IDS:
        fs = get_preview_page_vm(P4_MARKET, sc).context.first_screen
        a, b = H.first_screen_html(fs), H.first_screen_html(fs, cta_first=True)
        assert sorted(re.findall(r'data-ui2-q="(\w+)"', a)) == sorted(re.findall(r'data-ui2-q="(\w+)"', b))
        ta, tb = _txt(a).replace("④ 主 CTA", ""), _txt(b)
        assert sorted(ta.split()) == sorted(tb.split()), sc
        assert fs.primary_cta.label in b and (fs.primary_cta.disabled_reason or "") in b


def test_cta_order_other_pages_keep_four_question_order():
    """只動市場頁：持股／我的（render_page）預設仍 ①②③④。"""
    for pid in (P4_HOLD, P4_ME):
        fs = get_preview_page_vm(pid, "loaded").context.first_screen
        assert re.findall(r'data-ui2-q="(\w+)"', H.first_screen_html(fs))[-1] == "q4"


def test_cta_order_desktop_grid_places_cta_row_above_conclusion():
    css = _css()
    r_cta = int(re.search(r'\[data-ui2-q="q4"\]\{grid-row:(\d+)\}', css).group(1))
    r_concl = int(re.search(r'\[data-ui2-q="concl"\]\{grid-row:(\d+)\}', css).group(1))
    r_q1 = int(re.search(r'\[data-ui2-q="q1"\]\{grid-column:1;grid-row:(\d+)\}', css).group(1))
    r_q2 = int(re.search(r'\[data-ui2-q="q2"\]\{grid-row:(\d+)\}', css).group(1))
    assert r_cta < r_concl < r_q1 < r_q2
    assert re.search(r">\.ui2-risk\{grid-column:3;grid-row:%d;" % r_q1, css)        # 三 tile 仍同列


def test_cta_top_row_is_not_a_semantics_change_for_system_action_or_risk_cap():
    """CTA 仍 disabled 示意、⚡ 欄位仍是 capability 未提供、Risk Cap 仍無法判定（本批不碰 System Action／Risk Cap）。"""
    for sc in SCENARIO_IDS:
        fs = get_preview_page_vm(P4_MARKET, sc).context.first_screen
        assert fs.primary_cta.enabled is False
        assert fs.action_needed.capability is CapabilityState.NOT_PROVIDED
        rc = next(r for r in fs.context_rows if r.label == "Risk Cap")
        assert rc.status_text == T.TEXT_RISK_CAP_UNDETERMINABLE


# ── 底部導覽餘裕（presentation-only）──────────────────────────────
def test_nav_margin_content_bottom_reserve_covers_nav_height_and_safe_area():
    """手機內容底部保留量 ＝ 5rem（80px）＋ env(safe-area-inset-bottom)；必須 ≥ 導覽高 53px，且帶 safe-area 項。
    ⚠️ env() 在 Chromium 實測為 0；iOS Safari 未驗（viewport-fit 未設時亦可能為 0）——本測試只鎖 CSS 規則存在。"""
    css = _css()
    m = re.search(r"@supports \(padding-bottom:env\(safe-area-inset-bottom\)\)\{\s*@media \(max-width:768px\)\{\.block-container"
                  r"\{padding-bottom:calc\((\d+(?:\.\d+)?)rem \+ env\(safe-area-inset-bottom,0px\)\) !important\}", css)
    assert m, "手機 block-container padding-bottom 必須含 env(safe-area-inset-bottom)（@supports 覆寫；基礎 5rem 規則保留）"
    assert ".block-container{padding-bottom:5rem !important}" in css      # 基礎規則（無 env 支援時的後備）不動
    # D-9（DEC-137 改寫，等價）：底部固定導覽已由抽屜取代，53px 改為「底部保留帶」（Manage app／家的指示條）；
    # 保留量仍須 ≥ 保留帶 53 + 16px。不再覆蓋的舊斷言：從 CSS 解析 `.st-key-ui2_nav{…bottom:0;height:53px` 的導覽高（該規則已不存在，
    # 且其不存在本身由 test_ui2_batch2.check_mobile_drawer_css 守）。
    assert not re.search(r"\.st-key-ui2_nav\{[^}]*bottom:0;height:\d+px", css)
    assert float(m.group(1)) * 16 >= MV.NAV_MOBILE_H + 16, "保留量至少要多於底部保留帶一個基本間距（16px）"
    assert MV.NAV_MOBILE_H == 53


def test_nav_margin_cta_row_puts_reason_beside_button_not_below():
    css = _css()
    assert ".ui2-qrow--cta-top .ui2-ctawrap{display:flex;flex-wrap:wrap" in css       # B：原因與按鈕同列（窄時才折行）
    assert ".ui2-qrow--cta-top .ui2-cta__reason{margin:0}" in css
    # 未縮字、未刪資訊：CTA 原因句仍在 DOM
    fs = get_preview_page_vm(P4_MARKET, "loaded").context.first_screen
    assert fs.primary_cta.disabled_reason in H.first_screen_html(fs, cta_first=True)


def test_nav_margin_thresholds_registered_and_stress_evaluator_has_teeth():
    ids = {t["id"] for t in MV.THRESHOLDS}
    assert {"market_cta_before_conclusion", "market_main_risk_nav_margin", "market_stress_reachable"} <= ids
    nav = {"top": 791.0}
    good = {"nav": nav, "scroll_end_bottom": 764.0, "risk_bottom_at_scroll_end": 400.0,
            "hscroll": {"doc": {"scrollWidth": 390, "clientWidth": 390}, "main": {"scrollWidth": 390, "clientWidth": 390}},
            "elements": [_el("q4", 100, 150), _el("concl", 150, 220)]}
    assert not any(MV.evaluate_stress(good).values())
    for name, fn in [("內容被導覽遮住", lambda m: m.update(scroll_end_bottom=800.0)),
                     ("風險捲不出導覽", lambda m: m.update(risk_bottom_at_scroll_end=900.0)),
                     ("水平捲動", lambda m: m["hscroll"]["doc"].update(scrollWidth=500)),
                     ("CTA 不在結論前", lambda m: _el_of(m, "q4").update(top=300.0, bottom=350.0)),
                     ("缺量測", lambda m: m.update(scroll_end_bottom=None))]:
        m = copy.deepcopy(good)
        fn(m)
        assert any(MV.evaluate_stress(m).values()), name


def test_nav_margin_evidence_json_locks_real_browser_numbers():
    """證據 JSON（Chromium 實測；1.59 與 1.56 各一份）：手機市場頁六場景 nav_margin_after_risk ≥ 1 行行高，
    壓力態全過；CTA 在結論之前。檔不存在（尚未重量）→ fail（證據必須隨批次提交）。"""
    import json
    for name in ("viewport_measurements.json", "viewport_measurements_streamlit156.json"):
        d = json.loads((ROOT / "docs" / "vnext" / "newui2_batch3b" / name).read_text(encoding="utf-8"))
        assert d["summary"]["failed"] == [], name
        mk = [r for r in d["results"] if r["page"] == "p4_market" and r["viewport_name"] == "mobile" and r.get("mode") is None]
        st = [r for r in d["results"] if r.get("mode") == "stress"]
        assert len(mk) == 6 and len(st) == 6, name
        for r in mk:
            b = r["batch3"]
            assert b["nav_margin_after_risk"] >= b["risk_line_height"], (name, r["scenario"], b["nav_margin_after_risk"])
            q = {e["q"]: e for e in r["elements"]}
            assert q["q4"]["bottom"] <= q["concl"]["top"] + 0.5
        for r in st:
            assert r["pass"] and r["stress"]["scroll_end_gap_to_nav"] >= 0, (name, r["scenario"])


# ── W-4 驗收收斂（客戶 2026-11-03：目前 Neutral／Info 方向接受；對照 Gate／Wireframes §9 W-4 逐點鎖定）──
def test_w4_contract_points_are_each_locked_by_a_test():
    """對照表（逐點→鎖定測試）；本測試確認被引用的測試函式都真實存在（防文件與測試脫鉤）。"""
    locks = {
        "輕量 context row／chip（一行、僅 市場位階＋Risk Cap）": "test_w4_context_row_is_light_neutral_and_below_summary",
        "Neutral／Info 外觀（含 Stale／Unavailable 場景）": "test_f2_w4_context_and_market_env_are_neutral_tone_with_text_state",
        "字級低於查詢摘要與 6 維格": "test_w4_context_font_is_smaller_than_summary_and_snapshot_cells",
        "置於查詢摘要之下、搜尋之後（整頁 DOM 順序）": "test_w4_context_sits_after_search_and_summary_in_real_page",
        "不搶過查一檔／基本面：『市場環境』不排第一格、Neutral": "test_six_dim_snapshot_order_and_semantics",
        "市場技術訊號不成為單一股票主要判斷（無方向／買賣字樣）": "test_target_creates_no_buy_judgement_or_action_authority",
        "與市場頁位階同源（不各說各話）": "test_target_market_regime_follows_the_same_market_context",
        "真瀏覽器：context 在摘要之下、字級較小（viewport 判定器）": "test_batch3_evaluator_has_teeth",
    }
    g = globals()
    for point, name in locks.items():
        assert name in g and callable(g[name]), f"W-4 點『{point}』引用的測試 {name} 不存在"


def test_w4_context_font_is_smaller_than_summary_and_snapshot_cells():
    css = _css()
    ctx = float(re.search(r"\.ui2-ctxline\{[^}]*font-size:([\d.]+)rem", css).group(1))
    dim = float(re.search(r"\.ui2-dim\{[^}]*font-size:([\d.]+)rem", css).group(1))
    assert ctx < 1.0 and ctx < dim          # 查詢摘要＝內文 1rem；基本面等 6 維格 .85rem


@pytest.mark.parametrize("scenario", ["cold", "loaded", "stale", "unavailable"])
def test_w4_context_sits_after_search_and_summary_in_real_page(scenario):
    at = _at_target(scenario)
    blob = _page_blob(at)
    i_search, i_q1, i_ctx = blob.index('class="ui2-searchbox"'), blob.index('class="ui2-qrow" data-ui2-q="q1"'), blob.index('class="ui2-qrow ui2-ctxline" data-ui2-q="ctx"')
    assert i_search < i_q1 < i_ctx
    at.radio(key="ui2_target_mode").set_value(MODE_LOOKUP).run(timeout=60)
    blob = _page_blob(at)
    if scenario == "cold":          # F3：冷啟動查一檔不畫 Snapshot（只有搜尋框＋灰色說明）
        assert 'class="ui2-snapshot"' not in blob
        return
    assert 'class="ui2-snapshot"' in blob
    assert blob.index('class="ui2-qrow ui2-ctxline" data-ui2-q="ctx"') < blob.index('class="ui2-snapshot"')
