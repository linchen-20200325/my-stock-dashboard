"""New UI2 P-1「🎯／💼 detail 對齊 📊」最小施工守衛（客戶核准 #1199 comment 7148847917「P-1 A」）。

範圍（只有這三件事；其餘一律不動）
1. 🎯 `ctxline_html`（市場位階／Risk Cap 一行）：每個 FieldVM 若有可顯示的 `detail`，在該項 chip 之後補畫一小行
   `<div class="ui2-row__detail">`（與 📊 `qa_row_html` 完全同一個 class／escape／`shown()` 過濾）。
2. 💼 `hold_action_row_html`（今日需處理）：`field` 非 None 且 detail 可顯示 → 同上；`field is None` 分支逐位不變。
3. 🎯 `snapshot_html`（六維格）：客戶明確暫不納入 → **輸出逐位不變**（本檔以字面常數釘死）。

⛔ 未授權：新欄位／新 Copy／新狀態／新 expander／新 CSS class／任何公式或資料來源改動。detail 缺值（None／空字串／被
`shown()` 過濾的治理參照句）→ 輸出與 base **逐位相同**（不補 0、不補任何字）。

本檔三層：
(A) 純函式：新行為、負控（空 detail／None 分支／snapshot）、錨點與 DOM 順序；
(B) 頁面層：FAKE 全場景＋Real 全 snapshot（含降級用的 unavailable／contract_error）渲染後 🎯／💼 文字無工程字樣、
    無補 0；
(C) AppTest 整頁（slow）：Real 降級（`read_real_snapshot` raise）＋FAKE 三態，🎯／💼 真正走過 shell。
"""
from __future__ import annotations

import re
from html import escape

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.models import CapabilityState, FieldState, FieldVM, JudgementState
from shared.ui2_contract.pages import P4_HOLD, P4_TARGET, SCENARIO_IDS
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import get_real_page_vm
from src.ui2.components import html as H
from tests.test_ui2_p1_human_text import ENGINEERING_VOCAB, _snapshots, hits_in

DETAIL_RISK = "必要輸入不足：目前曝險尚無正式來源"
DETAIL_ACT = "動作判斷功能尚未開放"


def _fv(label, state, *, value=None, status=None, detail=None, cap=CapabilityState.PROVIDED):
    return FieldVM(label=label, state=state, value_text=value, status_text=status, detail=detail, capability=cap)


def _risk(detail=DETAIL_RISK):
    return _fv("Risk Cap", JudgementState.UNDETERMINABLE, status=T.TEXT_RISK_CAP_UNDETERMINABLE, detail=detail)


def _regime_ok(detail=None):
    return _fv("市場位階", FieldState.OK, value="震盪", detail=detail)


def _regime_stale(detail=None):
    return _fv("市場位階", FieldState.STALE, value="震盪", status=T.stale_text(3), detail=detail)


def _regime_unavailable(detail="市場位階暫時無法讀取"):
    return _fv("市場位階", FieldState.UNAVAILABLE, status=T.TEXT_UNAVAILABLE, detail=detail)


def _action(detail=DETAIL_ACT):
    return _fv("是否需要行動", None, status=T.TEXT_NOT_PROVIDED_AGGREGATOR, detail=detail, cap=CapabilityState.NOT_PROVIDED)


# ══════════════════════════════════════════════════════════════════════
# base 參照（逐字複製 origin/main 8d6e50be 的實作；供「空 detail 與 base 逐位相同」比對。⛔ 不得隨實作一起改）
# ══════════════════════════════════════════════════════════════════════
def _base_ctxline_html(rows):
    items = "".join(f'<span class="ui2-ctxline__item"><span class="ui2-row__label">{escape(r.label)}</span> '
                    f'{H._ctx_chip(r)}</span>' for r in rows)
    return f'<div class="ui2-qrow ui2-ctxline" data-ui2-q="ctx">{items}</div>'


def _base_hold_action_row_html(field):
    if field is None:
        axis, state, chip = "capability", "not_provided", H._hold_slot_chip()
    else:
        axis, state, chip = field.layer, H._state_attr(field), H.status_chip_html(field)
    return (f'<div class="ui2-qrow" data-ui2-q="q2" data-ui2-qname="是否需要行動" data-axis="{axis}" '
            f'data-state="{state}"><span class="ui2-row__label">{escape(T.HOLD_ACTION_LABEL)}</span> {chip}</div>')


# ══════════════════════════════════════════════════════════════════════
# (A-1) 🎯 ctxline_html
# ══════════════════════════════════════════════════════════════════════
def test_ctxline_draws_detail_after_the_chip_inside_its_own_item():
    html = H.ctxline_html((_risk(),))
    chip = H.neutral_status_chip_html(_risk())
    assert chip and "ui2-chip" in chip
    assert html == ('<div class="ui2-qrow ui2-ctxline" data-ui2-q="ctx"><span class="ui2-ctxline__item">'
                    f'<span class="ui2-row__label">Risk Cap</span> {chip}'
                    f'<div class="ui2-row__detail">{escape(DETAIL_RISK)}</div></span></div>')
    # DOM 順序：label → chip → detail；detail 在 item 內（不新增容器）
    assert html.index("ui2-row__label") < html.index("ui2-chip") < html.index("ui2-row__detail")
    assert html.count("ui2-ctxline__item") == 1 and html.count('data-ui2-q="ctx"') == 1


def test_ctxline_detail_uses_the_same_class_and_escape_as_the_market_qa_row():
    f = _risk('含 <b>標籤</b> & "引號"')
    qa = H.qa_row_html(None, f)
    ctx = H.ctxline_html((f,))
    m = re.search(r'<div class="ui2-row__detail">.*?</div>', qa)
    assert m, qa
    assert m.group(0) in ctx                          # 與 📊 qa_row_html 的 detail 片段逐字相同（同 class、同 escape）
    assert "<b>" not in ctx and "&lt;b&gt;" in ctx


def test_ctxline_shows_detail_for_every_state_that_has_one():
    for f in (_regime_unavailable(), _regime_stale("補充一句"), _regime_ok("補充二句"), _risk()):
        html = H.ctxline_html((f,))
        assert f'<div class="ui2-row__detail">{escape(f.detail)}</div>' in html, f.label


@pytest.mark.parametrize("detail", [None, "", ])
def test_ctxline_empty_or_none_detail_is_bit_identical_to_base(detail):
    rows = (_regime_ok(detail), _regime_stale(detail), _regime_unavailable(detail), _risk(detail))
    assert H.ctxline_html(rows) == _base_ctxline_html(rows)
    assert "ui2-row__detail" not in H.ctxline_html(rows)


@pytest.mark.parametrize("dev_only", ["規則分支（DEC-074）", "見 macro_state.json", "含 `code` 標記"])
def test_ctxline_dev_only_detail_is_not_drawn_and_output_equals_base(dev_only):
    rows = (_regime_ok(dev_only), _risk(dev_only))
    out = H.ctxline_html(rows)
    assert out == _base_ctxline_html(rows)
    assert "DEC-074" not in out and "macro_state" not in out and "`" not in out


def test_ctxline_no_rows_and_mixed_rows():
    assert H.ctxline_html(()) == _base_ctxline_html(())
    mixed = (_regime_ok(None), _risk())            # 只有有 detail 的那一項多一行；另一項與 base 逐位相同
    out = H.ctxline_html(mixed)
    first_item = _base_ctxline_html((mixed[0],)).split('data-ui2-q="ctx">')[1].removesuffix("</div>")
    assert first_item in out
    assert out.count("ui2-row__detail") == 1


def test_ctxline_never_invents_a_value_when_detail_is_missing():
    out = H.ctxline_html((_regime_ok(None), _risk(None)))
    assert "ui2-row__detail" not in out
    assert not re.search(r">\s*0\s*<", out) and "0%" not in out and ">—<" not in out and "nan" not in out.lower()


# ══════════════════════════════════════════════════════════════════════
# (A-2) 💼 hold_action_row_html
# ══════════════════════════════════════════════════════════════════════
def test_hold_action_row_draws_detail_after_the_chip():
    f = _action()
    html = H.hold_action_row_html(f)
    chip = H.status_chip_html(f)
    assert html == ('<div class="ui2-qrow" data-ui2-q="q2" data-ui2-qname="是否需要行動" data-axis="capability" '
                    f'data-state="not_provided"><span class="ui2-row__label">{escape(T.HOLD_ACTION_LABEL)}</span> {chip}'
                    f'<div class="ui2-row__detail">{escape(DETAIL_ACT)}</div></div>')
    assert html.index("ui2-row__label") < html.index("ui2-chip") < html.index("ui2-row__detail")
    # 與 📊 同一個 detail 片段
    assert re.search(r'<div class="ui2-row__detail">.*?</div>', H.qa_row_html("是否需要行動", f)).group(0) in html


def test_hold_action_row_field_none_branch_is_bit_identical_to_base():
    assert H.hold_action_row_html(None) == _base_hold_action_row_html(None)
    assert "ui2-row__detail" not in H.hold_action_row_html(None)
    # 釘死字面（防「base 參照」本身被一起改壞）
    assert H.hold_action_row_html(None) == (
        '<div class="ui2-qrow" data-ui2-q="q2" data-ui2-qname="是否需要行動" data-axis="capability" '
        f'data-state="not_provided"><span class="ui2-row__label">{escape(T.HOLD_ACTION_LABEL)}</span> '
        f'{H._hold_slot_chip()}</div>')


@pytest.mark.parametrize("detail", [None, ""])
def test_hold_action_row_empty_detail_is_bit_identical_to_base(detail):
    f = _action(detail)
    assert H.hold_action_row_html(f) == _base_hold_action_row_html(f)
    assert "ui2-row__detail" not in H.hold_action_row_html(f)


@pytest.mark.parametrize("dev_only", ["規則分支（DEC-074）", "見 macro_state.json", "含 `code` 標記"])
def test_hold_action_row_dev_only_detail_is_not_drawn(dev_only):
    f = _action(dev_only)
    out = H.hold_action_row_html(f)
    assert out == _base_hold_action_row_html(f)
    assert "DEC-074" not in out and "macro_state" not in out and "`" not in out


def test_hold_action_row_anchors_unchanged_with_and_without_detail():
    for f in (None, _action(), _action(None)):
        out = H.hold_action_row_html(f)
        assert out.count('data-ui2-q="q2"') == 1 and 'data-ui2-qname="是否需要行動"' in out
        assert 'data-axis="capability"' in out and 'data-state="not_provided"' in out
        assert out.startswith('<div class="ui2-qrow" data-ui2-q="q2"') and out.endswith("</div>")


def test_hold_first_screen_keeps_dom_order_and_anchors():
    vm = get_preview_page_vm(P4_HOLD, "loaded")
    html = H.hold_first_screen_html(vm.context.first_screen)
    qs = re.findall(r'data-ui2-q="(\w+)"', html)
    assert qs == ["q1", "ctx", "ctx", "q2", "q4"]
    assert html.count('<div class="ui2-qa">') == 1
    # 今日需處理列的 detail 在 q2 列內、q4（主 CTA）之前
    assert html.index('data-ui2-q="q2"') < html.index(escape(DETAIL_ACT)) < html.index('data-ui2-q="q4"')


# ══════════════════════════════════════════════════════════════════════
# (A-3) 🎯 snapshot_html：客戶暫不納入 → 輸出逐位不變（字面釘死；輸入刻意帶 detail 證明它被忽略）
# ══════════════════════════════════════════════════════════════════════
_SNAP_FIELDS = (
    _fv("基本面", FieldState.OK, value="穩健", detail="SNAP-DETAIL-1"),
    _fv("估值", FieldState.STALE, value="偏高", status=T.stale_text(3), detail="SNAP-DETAIL-2"),
    _fv("籌碼", FieldState.UNAVAILABLE, status=T.TEXT_UNAVAILABLE, detail="SNAP-DETAIL-3"),
    _fv("趨勢", FieldState.NOT_EVALUATED, status=T.TEXT_NOT_DEFINED, detail="SNAP-DETAIL-4"),
    _fv("產業", FieldState.MISSING, status=T.TEXT_MISSING_NOT_READY, detail="SNAP-DETAIL-5"),
    _fv("市場環境", FieldState.STALE, value="多頭", status=T.stale_text(5), detail="SNAP-DETAIL-6"),
)

#: 於 origin/main 8d6e50be 以 `H.snapshot_html(_SNAP_FIELDS)` 取得的逐字輸出（含 detail 輸入，但 base 不畫）。
_SNAPSHOT_GOLDEN = (
    '<div class="ui2-snapshot">'
    '<div class="ui2-dim" data-dim="基本面" data-axis="data" data-state="ok"><span class="ui2-row__label">基本面</span> '
    '<span class="ui2-row__value">穩健</span></div>'
    '<div class="ui2-dim" data-dim="估值" data-axis="data" data-state="stale"><span class="ui2-row__label">估值</span> '
    '<span class="ui2-row__value">偏高</span><span class="ui2-chip ui2-chip--warning ui2-chip--axis-data" data-axis="data" data-state="stale">⚠ 過期 3 天</span></div>'
    '<div class="ui2-dim" data-dim="籌碼" data-axis="data" data-state="unavailable"><span class="ui2-row__label">籌碼</span> '
    '<span class="ui2-chip ui2-chip--danger ui2-chip--axis-data" data-axis="data" data-state="unavailable">🔴 來源目前不可用</span></div>'
    '<div class="ui2-dim" data-dim="趨勢" data-axis="data" data-state="not_evaluated"><span class="ui2-row__label">趨勢</span> '
    '<span class="ui2-chip ui2-chip--neutral ui2-chip--axis-data" data-axis="data" data-state="not_evaluated">⬜ 尚未定義</span></div>'
    '<div class="ui2-dim" data-dim="產業" data-axis="data" data-state="missing"><span class="ui2-row__label">產業</span> '
    '<span class="ui2-chip ui2-chip--neutral ui2-chip--axis-data" data-axis="data" data-state="missing">⬜ 資料未備</span></div>'
    '<div class="ui2-dim" data-dim="市場環境" data-axis="data" data-state="stale"><span class="ui2-row__label">市場環境</span> '
    '<span class="ui2-row__value">多頭</span><span class="ui2-chip ui2-chip--neutral ui2-chip--axis-data" data-axis="data" data-state="stale">⚠ 過期 5 天</span></div>'
    '</div>')


def test_snapshot_html_is_bit_identical_and_never_draws_detail():
    out = H.snapshot_html(_SNAP_FIELDS)
    assert out == _SNAPSHOT_GOLDEN
    assert "SNAP-DETAIL" not in out and "ui2-row__detail" not in out


def test_snapshot_html_in_real_lookup_result_has_no_detail_rows():
    for name, snap in _snapshots().items():
        vm = get_real_page_vm(P4_TARGET, snap)
        out = H.snapshot_html(vm.context.target.lookup.snapshot)
        assert "ui2-row__detail" not in out, name
    for sc in SCENARIO_IDS:
        vm = get_preview_page_vm(P4_TARGET, sc)
        assert "ui2-row__detail" not in H.snapshot_html(vm.context.target.lookup.snapshot), sc


# ══════════════════════════════════════════════════════════════════════
# (A-4) 📊 與其他共用元件不受影響（P-1 不得外溢）
# ══════════════════════════════════════════════════════════════════════
def test_market_first_screen_and_qa_row_unchanged():
    f = _risk()
    assert H.qa_row_html(None, f) == (
        f'<div class="ui2-qrow" data-ui2-q="ctx" data-axis="judgement" data-state="undeterminable">'
        f'<span class="ui2-row__label">Risk Cap</span> {H.status_chip_html(f)}'
        f'<div class="ui2-row__detail">{escape(DETAIL_RISK)}</div></div>')
    vm = get_preview_page_vm("p4_market", "loaded")
    fs = H.first_screen_html(vm.context.first_screen, cta_first=True)
    assert re.findall(r'data-ui2-q="(\w+)"', fs) == ["q4", "concl", "q1", "ctx", "q2", "q3"]


# ══════════════════════════════════════════════════════════════════════
# (A-5) CSS：P-1 只准多一條規則（`.ui2-ctxline__item` 是 nowrap；不放開則長 detail 會把手機頁撐出水平捲動）
# ══════════════════════════════════════════════════════════════════════
def test_css_has_exactly_the_one_p1_rule_and_no_new_class():
    from src.ui2.shell import css as C
    sheet = C.CSS if hasattr(C, "CSS") else next(v for k, v in vars(C).items() if isinstance(v, str) and ".ui2-ctxline" in v)
    rule = ".ui2-ctxline__item .ui2-row__detail{white-space:normal}"
    assert sheet.count(rule) == 1
    assert ".ui2-ctxline__item{white-space:nowrap}" in sheet            # 原規則仍在（item 內 label／chip 不換行）
    assert sheet.count("ui2-ctxline__item") == 2                       # 原 1 條＋本規則 1 條；沒有其他針對 ctxline item 的規則
    # 沒有為 P-1 新增任何 class：本檔輸出只用既有 class
    used = set(re.findall(r'class="([^"]+)"', H.ctxline_html((_risk(),)) + H.hold_action_row_html(_action())))
    assert {c for u in used for c in u.split()} <= {"ui2-qrow", "ui2-ctxline", "ui2-ctxline__item", "ui2-row__label", "ui2-row__detail",
                                                    "ui2-chip", "ui2-chip--neutral", "ui2-chip--axis-judgement", "ui2-chip--axis-capability"}


# ══════════════════════════════════════════════════════════════════════
# (B) 頁面層：FAKE 全場景＋Real 全 snapshot（含降級路徑用的 unavailable／contract_error）
# ══════════════════════════════════════════════════════════════════════
def _plain(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", re.sub(r"<style>.*?</style>", "", html, flags=re.S))


def _target_html(vm) -> str:
    fs = vm.context.first_screen
    return H.target_first_screen_html(fs, fs.current_state)


def _hold_html(vm) -> str:
    return H.hold_l1_v2_html("", vm.context.first_screen, vm.context.delta) + H.hold_body_html()


def _all_vms():
    for sc in SCENARIO_IDS:
        yield f"fake/{sc}", get_preview_page_vm(P4_TARGET, sc), get_preview_page_vm(P4_HOLD, sc)
    for name, snap in _snapshots().items():
        yield f"real/{name}", get_real_page_vm(P4_TARGET, snap), get_real_page_vm(P4_HOLD, snap)


@pytest.mark.parametrize("name,target_vm,hold_vm", list(_all_vms()), ids=[n for n, *_ in _all_vms()])
def test_rendered_target_and_hold_have_no_engineering_vocabulary(name, target_vm, hold_vm):
    for page_name, html in (("target", _target_html(target_vm)), ("hold", _hold_html(hold_vm))):
        text = _plain(html)
        assert hits_in(text) == [], (name, page_name, hits_in(text))
        for w in ENGINEERING_VOCAB:
            assert w not in text, (name, page_name, w)


@pytest.mark.parametrize("name,target_vm,hold_vm", list(_all_vms()), ids=[n for n, *_ in _all_vms()])
def test_detail_rows_equal_exactly_the_shown_details_of_the_fields(name, target_vm, hold_vm):
    """🎯 context 列／💼 動作列：畫出的 detail 集合 ＝ VM 該欄位的 `shown()` detail 集合（不多、不少、不補值）。"""
    fs = target_vm.context.first_screen
    ctx = H.ctxline_html(fs.context_rows)
    want = [escape(r.detail) for r in fs.context_rows if H.shown(r.detail)]
    assert re.findall(r'<div class="ui2-row__detail">(.*?)</div>', ctx) == want, name

    hfs = hold_vm.context.first_screen
    act = H.hold_action_row_html(hfs.action_needed)
    a = hfs.action_needed
    want_a = [escape(a.detail)] if a is not None and H.shown(a.detail) else []
    assert re.findall(r'<div class="ui2-row__detail">(.*?)</div>', act) == want_a, name


def test_target_page_html_still_has_every_anchor_in_order():
    for name, tvm, _ in _all_vms():
        html = _target_html(tvm)
        assert re.findall(r'data-ui2-q="(\w+)"', html) == ["q1", "ctx", "q2", "q3"], name
        assert html.count('class="ui2-qrow ui2-ctxline"') == 1, name


def test_detail_text_never_appears_as_a_zero_or_filled_value():
    for name, tvm, hvm in _all_vms():
        for html in (_target_html(tvm), _hold_html(hvm)):
            for seg in re.findall(r'<div class="ui2-row__detail">(.*?)</div>', html):
                assert seg.strip() and seg.strip() not in {"0", "0.0", "—", "nan", "None"}, (name, seg)


# ══════════════════════════════════════════════════════════════════════
# (C) AppTest 整頁（slow）：FAKE 三態＋Real＋Real 降級
# ══════════════════════════════════════════════════════════════════════
def _at(feed: str, scenario: str | None = None):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest
    root = Path(__file__).resolve().parents[1]
    a = AppTest.from_file(str(root / "app_ui2.py"), default_timeout=60)
    a.session_state["ui2_feed"] = feed
    if scenario:
        a.session_state["ui2_scenario"] = scenario
    return a.run(timeout=60)


def _rendered_page_html(at) -> str:
    return "\n".join(m.value for m in at.markdown if 'data-ui2-dev="1"' not in m.value)


def _page(at, page_id: str) -> str:
    at.radio(key="ui2_page").set_value(page_id).run(timeout=60)
    assert not at.exception, (page_id, at.exception)
    return _rendered_page_html(at)


@pytest.mark.slow
@pytest.mark.parametrize("scenario", ["cold", "stale", "unavailable"])
def test_apptest_fake_target_and_hold_show_detail_without_engineering_words(scenario):
    at = _at("fake", scenario)
    tgt = _page(at, P4_TARGET)
    ctx = re.search(r'<div class="ui2-qrow ui2-ctxline".*?</div></span></div>', tgt, re.S)
    assert ctx and "ui2-row__detail" in ctx.group(0), scenario        # Risk Cap 的原因句一定在
    assert escape(DETAIL_RISK) in ctx.group(0)
    hold = _page(at, P4_HOLD)
    assert escape(DETAIL_ACT) in hold, scenario
    for html in (tgt, hold):
        assert hits_in(_plain(html)) == [], scenario


@pytest.mark.slow
def test_apptest_real_and_real_degraded_target_and_hold(monkeypatch):
    at = _at("real")
    for pid in (P4_TARGET, P4_HOLD):
        html = _page(at, pid)
        assert hits_in(_plain(html)) == [], pid
    assert escape(DETAIL_RISK) in _page(at, P4_TARGET)
    assert escape(DETAIL_ACT) in _page(at, P4_HOLD)

    from src.ui2.shell import app as shell

    def boom():
        raise RuntimeError("secret-token")
    monkeypatch.setattr(shell, "read_real_snapshot", boom)
    at2 = _at("real")
    for pid in (P4_TARGET, P4_HOLD):
        html = _page(at2, pid)
        assert 'data-ui2-degraded="1"' in html, pid
        assert hits_in(_plain(html)) == [], pid
        assert "secret-token" not in html, pid
