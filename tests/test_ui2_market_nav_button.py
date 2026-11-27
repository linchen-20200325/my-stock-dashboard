# -*- coding: utf-8 -*-
"""tests/test_ui2_market_nav_button.py — 📊 市場頁「接入狀態」之下一顆原生「🗂 資料」按鈕（N1；Real-data Preview only）。

授權（#1199）：客戶 R23.26（7213913793）／R23.27／R23.28 核准 N1——「📊 市場頁『接入狀態』區塊下方附加一顆原生『🗂 資料』按鈕→切到資料頁」，
**僅 Real 正常態且接入狀態已呈現時顯示**；不改既有導覽、不改 Contract 對 👤 的規定、不是替代既有動線；沿既有標籤、無新 I/O、無守衛／資料／正式判定變更。
B 設計與線框：#1199 留言 7212932356（B-NEXT-r01）。

⚠️ 價值有限（誠實揭露）：頂部導覽列本來就固定置頂，這顆按鈕只省一步，不是大功能。

本檔鎖定：
- 顯示條件：Real 且「接入狀態」區塊已畫出才有；FAKE、Real 降級、接入狀態未畫出（unavailable／上游 FETCH_FAILED）、其他四頁一律沒有；
- 點擊：`ui2_page` 變 `p4_data` 且資料頁真的渲染；Real 模式 session 寫入紀錄在不點擊時 0 次、點擊時只寫 `ui2_page`；
- 位置：DOM 順序在「接入狀態」區塊之後（且是 main 的最後一個元素）；
- 標籤＝既有 `PAGE_LABELS[P4_DATA]`（零新文案）；widget key `ui2_` 前綴＋模組頂層常數（G9）；與殼的 `KEY_PAGE` 同值；
- 量測器判定 `evaluate_nav_button` 的牙（注入反例必紅）。
⛔ 本檔不出現該區塊的 section id 字面（N5 守衛：識別字只准在 `real_canonical.py`＋核准的測試清單）。
以下為實作者自跑結論，未經第二組驗證。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.ui2_contract.pages import P4_DATA, P4_HOLD, P4_MARKET, P4_ME, P4_TARGET, PAGE_LABELS
from src.ui2.shell import app as shell
from src.ui2.views import market as MK
from src.services.ui2.real_canonical import CONTRACT_ERROR
from tests import test_ui2_data_freshness_overview as OV
from tests.test_ui2_guards import check_not_a_producer
from tests.ui2_viewport import measure_viewport as MV

ROOT = Path(__file__).resolve().parent.parent
APP_UI2 = ROOT / "app_ui2.py"
TITLE = "接入狀態"                 # 區塊標題（既有字串；⛔ 本檔不寫該區塊的 section id，N5 守衛）
twii, regime, snap = OV.twii, OV.regime, OV.snap

#: 接入狀態區塊會畫出的 Real snapshot（正常缺值／過期／未評估／無法判定／上游非 FETCH_FAILED）。
DRAW = {
    "loaded": snap(twii(), "", regime("bull")),
    "unloaded": snap(twii(), "", regime("unloaded")),
    "breadth_undeterminable": snap(twii(), "", regime("breadth")),
    "missing": snap(twii(ok=False, close=(), as_of=None, is_stale=None), "", regime("bull")),
    "stale": snap(twii(is_stale=True, age_days=5), "", regime("unloaded")),
    "no_new_data": snap(twii(upstream_state="NO_NEW_DATA"), "", regime("bull")),
    "undetermined": snap(twii(upstream_state="UNDETERMINED"), "", regime("bull")),
}
#: 不畫：任一已接入項 unavailable，或台股上游 FETCH_FAILED（含 legacy）。
NO_DRAW = {
    "twii_exception": snap(None, "OSError", regime("bull")),
    "twii_contract_error": snap(None, CONTRACT_ERROR, regime("bull")),
    "regime_exception": snap(twii(), "", None, "OSError"),
    "both_unavailable": snap(None, "OSError", None, "OSError"),
    "fetch_failed": snap(twii(upstream_state="FETCH_FAILED", has_upstream_error=True), "", regime("bull")),
    "fetch_failed_no_flag": snap(twii(upstream_state="FETCH_FAILED"), "", regime("bull")),
    "legacy_empty_state_with_error": snap(twii(upstream_state="", has_upstream_error=True), "", regime("bull")),
}


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
KEY = "ui2_market_go_data"        # 逐字釘死（⛔ 不從 production 取，否則自比永遠綠）
LABEL = "🗂 資料"                  # 既有導覽頁名；零新文案（DEC-208）


def go_buttons(at):
    return [b for b in at.button if b.key == KEY]


def _flat(block):
    """AppTest 元素樹依文件順序攤平（只取葉節點）。"""
    out = []
    for ch in block.children.values():
        if hasattr(ch, "children") and getattr(ch, "children", None) is not None and not hasattr(ch, "proto"):
            out.extend(_flat(ch))
        else:
            out.append(ch)
    return out


# ═══════════════════════════ 常數／標籤／G9
def test_constants_label_key_and_shell_page_key_are_pinned():
    assert MK.KEY_GO_DATA == KEY and MK.KEY_GO_DATA.startswith("ui2_")
    assert MK.KEY_PAGE == shell.KEY_PAGE == "ui2_page"                # 殼的 radio key 與按鈕 callback 寫的 key 同值
    assert PAGE_LABELS[P4_DATA] == LABEL                              # 標籤沿用既有字串（零新文案）
    assert MK.GO_DATA_LABEL == PAGE_LABELS[P4_DATA]


def test_g9_market_view_passes_producer_and_session_key_guard_and_the_guard_has_teeth():
    src = (ROOT / "src/ui2/views/market.py").read_text(encoding="utf-8")
    assert check_not_a_producer(src) == []
    bad_widget = src.replace(f'KEY_GO_DATA = "{KEY}"', 'KEY_GO_DATA = "market_go_data"')
    assert bad_widget != src and check_not_a_producer(bad_widget)     # widget key 非 ui2_ 前綴 → 紅
    bad_ss = src.replace('KEY_PAGE = "ui2_page"', 'KEY_PAGE = "page"')
    assert bad_ss != src and check_not_a_producer(bad_ss)             # callback 寫非 ui2_ 前綴的 session key → 紅


# ═══════════════════════════ 顯示條件
@pytest.mark.parametrize("name", ["loaded", "missing", "stale", "unloaded", "no_new_data", "undetermined", "breadth_undeterminable"])
def test_button_is_drawn_exactly_once_when_the_wired_status_block_is_drawn(monkeypatch, name):
    at = _real_at(monkeypatch, DRAW[name])
    assert TITLE in _blob(at)
    bs = go_buttons(at)
    assert len(bs) == 1 and bs[0].label == LABEL
    assert not bs[0].disabled
    assert at.expander == []


@pytest.mark.parametrize("name", sorted(NO_DRAW))
def test_no_button_when_the_wired_status_block_is_not_drawn(monkeypatch, name):
    at = _real_at(monkeypatch, NO_DRAW[name])
    assert TITLE not in _blob(at)
    assert go_buttons(at) == []


def test_no_button_in_real_degraded(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from tests import test_ui2_real_feed as RF
    RF._boom_shell(monkeypatch)
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    a.query_params["ui2_dev"] = "1"
    a.run(timeout=60)
    a.selectbox(key="ui2_feed").set_value("real").run(timeout=60)
    a.radio(key="ui2_page").set_value(P4_MARKET).run(timeout=60)
    assert not a.exception and 'data-ui2-degraded="1"' in _blob(a), "沒有走降級路徑"
    assert go_buttons(a) == []


@pytest.mark.parametrize("scenario", ["cold", "loaded", "missing", "stale", "unavailable", "not_evaluated"])
def test_no_button_in_fake(scenario):
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(APP_UI2), default_timeout=60)
    a.session_state["ui2_feed"] = "fake"
    a.session_state["ui2_scenario"] = scenario
    a.run(timeout=60)
    a.radio(key="ui2_page").set_value(P4_MARKET).run(timeout=60)
    assert not a.exception
    assert go_buttons(a) == [] and TITLE not in _blob(a)


@pytest.mark.parametrize("page", [P4_TARGET, P4_HOLD, P4_ME, P4_DATA])
def test_no_button_on_other_pages(monkeypatch, page):
    at = _real_at(monkeypatch, DRAW["loaded"], page=page)
    assert at.session_state["ui2_page"] == page
    assert go_buttons(at) == []


# ═══════════════════════════ 顯示條件的純函式判斷（VM 層）
def test_status_block_drawn_predicate_follows_the_vm_and_fails_closed_on_fake():
    import dataclasses

    from src.services.ui2.real_canonical import get_real_page_vm
    vm = get_real_page_vm(P4_MARKET, DRAW["loaded"])
    assert MK._status_block_drawn(vm) is True
    assert MK._status_block_drawn(dataclasses.replace(vm, is_fake=True)) is False          # 即使有該區塊，FAKE 一律不畫
    no_block = dataclasses.replace(vm, context=dataclasses.replace(
        vm.context, sections=tuple(x for x in vm.context.sections if x.title != TITLE)))
    assert MK._status_block_drawn(no_block) is False
    l2 = dataclasses.replace(vm, context=dataclasses.replace(
        vm.context, sections=tuple(dataclasses.replace(x, level="L2") if x.title == TITLE else x for x in vm.context.sections)))
    assert MK._status_block_drawn(l2) is False                                              # 只認 L1 區塊
    assert MK._status_block_drawn(get_real_page_vm(P4_MARKET, NO_DRAW["fetch_failed"])) is False


# ═══════════════════════════ 點擊
def test_click_switches_to_the_data_page_and_renders_it(monkeypatch):
    at = _real_at(monkeypatch, DRAW["loaded"])
    assert at.session_state["ui2_page"] == P4_MARKET
    at = go_buttons(at)[0].click().run(timeout=60)
    assert not at.exception, at.exception
    assert at.session_state["ui2_page"] == P4_DATA
    assert at.radio(key="ui2_page").value == P4_DATA                    # 導覽列同步（同一個 widget key）
    blob = _blob(at)
    assert f'data-ui2-page="{P4_DATA}"' in blob and f'data-ui2-page="{P4_MARKET}"' not in blob
    assert go_buttons(at) == []                                          # 資料頁沒有這顆按鈕


def test_click_on_a_stale_state_still_switches(monkeypatch):
    at = _real_at(monkeypatch, DRAW["stale"])
    at = go_buttons(at)[0].click().run(timeout=60)
    assert at.session_state["ui2_page"] == P4_DATA and not at.exception


def test_navigating_back_to_market_shows_the_button_again(monkeypatch):
    at = _real_at(monkeypatch, DRAW["loaded"])
    at = go_buttons(at)[0].click().run(timeout=60)
    at = at.radio(key="ui2_page").set_value(P4_MARKET).run(timeout=60)
    assert len(go_buttons(at)) == 1


# ═══════════════════════════ 位置（DOM 順序）
def test_button_comes_after_the_wired_status_block_and_is_the_last_main_element(monkeypatch):
    at = _real_at(monkeypatch, DRAW["loaded"])
    els = _flat(at.main)
    idx_btn = [i for i, e in enumerate(els) if getattr(e, "key", None) == KEY]
    assert len(idx_btn) == 1
    idx_title = [i for i, e in enumerate(els) if e.type == "markdown" and f'class="ui2-section-title">{TITLE}<' in e.value]
    assert len(idx_title) == 1 and idx_title[0] < idx_btn[0]
    # 其他任何 markdown 區塊（主圖槽／今日變化／指標卡／OneBrain）都在按鈕之前；按鈕之後沒有任何元素
    assert all(i < idx_btn[0] for i, e in enumerate(els) if e.type == "markdown")
    assert idx_btn[0] == len(els) - 1


# ═══════════════════════════ session 寫入
@pytest.fixture
def session_write_log(monkeypatch):
    from streamlit.runtime.state.session_state_proxy import SessionStateProxy
    log: list[tuple[str, str]] = []
    for meth in ("__setitem__", "__delitem__", "__setattr__", "__delattr__"):
        orig = getattr(SessionStateProxy, meth)

        def rec(self, key, *a, _orig=orig, _m=meth):
            log.append((_m, str(key)))
            return _orig(self, key, *a)
        monkeypatch.setattr(SessionStateProxy, meth, rec)
    return log


def test_real_mode_writes_nothing_without_a_click_and_only_ui2_page_with_one(monkeypatch, session_write_log):
    from tests.test_ui2_real_feed import ALLOWED_UI2_WRITES
    at = _real_at(monkeypatch, DRAW["loaded"])
    session_write_log.clear()
    at.run(timeout=60)                                                   # 不點擊：再跑一輪
    assert session_write_log == [], session_write_log
    at = go_buttons(at)[0].click().run(timeout=60)
    assert {k for _, k in session_write_log} == {"ui2_page"}, session_write_log
    assert {k for _, k in session_write_log} <= ALLOWED_UI2_WRITES
    assert at.session_state["ui2_page"] == P4_DATA


# ═══════════════════════════ 量測器判定 evaluate_nav_button 的牙
def _good(**kw) -> dict:
    nb = {"wired_title_present": True, "count": 1, "label": LABEL, "visible": True,
          "box": {"top": 1500.0, "bottom": 1540.0, "left": 16.0, "right": 140.0, "width": 124.0, "height": 40.0},
          "last_wired_row_bottom": 1480.0, "viewport_w": 390, "doc_scroll_w": 390, "doc_client_w": 390,
          "click_switches": True, "keyboard_switches": True, "tab_reaches_button": True}
    nb.update(kw)
    return nb


def test_evaluate_nav_button_accepts_the_good_shape_and_the_not_drawn_shape():
    assert MV.evaluate_nav_button(_good(), expected_label=LABEL) == []
    absent = {"wired_title_present": False, "count": 0}
    assert MV.evaluate_nav_button(absent, expected_label=LABEL) == []


@pytest.mark.parametrize("what,nb", [
    ("沒量到（None）", None),
    ("接入狀態已畫出卻沒有按鈕", _good(count=0, box=None, visible=False)),
    ("按鈕兩顆", _good(count=2)),
    ("接入狀態沒畫卻有按鈕", {"wired_title_present": False, "count": 1}),
    ("標籤不是既有字串", _good(label="前往資料頁")),
    ("看不見", _good(visible=False)),
    ("在接入狀態之上", _good(box={"top": 1000.0, "bottom": 1040.0, "left": 16.0, "right": 140.0, "width": 124.0, "height": 40.0})),
    ("水平溢出視窗右緣", _good(box={"top": 1500.0, "bottom": 1540.0, "left": 16.0, "right": 400.0, "width": 384.0, "height": 40.0})),
    ("頁面水平溢出", _good(doc_scroll_w=500)),
    ("點擊沒有切頁", _good(click_switches=False)),
    ("鍵盤 Enter 沒有切頁", _good(keyboard_switches=False)),
    ("Tab 到不了按鈕", _good(tab_reaches_button=False)),
])
def test_evaluate_nav_button_rejects_every_injected_counterexample(what, nb):
    assert MV.evaluate_nav_button(nb, expected_label=LABEL), what
