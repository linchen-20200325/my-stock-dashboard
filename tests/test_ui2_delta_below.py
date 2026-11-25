"""📊／💼「今日變化」Delta Strip BELOW（唯讀、恆不可比較）守衛。

授權：客戶 #1199 comment 7131915767、總管 7132044876（B 單一寫入；D1＝BELOW；D4＝專用唯讀欄位；D5＝既有合法文案；
僅「不可比較」）。本批**不**算 Diff、**不**接比較 producer、**不**補 0、**不**顯示 changed／unchanged／「今日無重大訊號變更」；
目標句「⬜ 暫無足夠資料比較今日變化」未經 Copy Gate，**不得**進任何 UI 字串。

契約最小差額：`PageContext.delta: FieldVM | None = None`（📊／💼 恆為 capability `⬜ 尚未提供`＋原因；其餘三頁 None）。
語意軸＝capability（DEC-124；不新增資料態／Enum）。本檔鎖定：
  (a) 所有場景（FAKE 六態＋Real 各態＋降級）📊／💼 的 delta 一律 NOT_PROVIDED、無 value、有原因、無 freshness；
  (b) 全站輸出（view 層＋AppTest）不含目標句／「今日無重大訊號變更」／「無變化」／「維持昨日」／changed／unchanged；
  (c) 🎯 👤 🗂 delta＝None、輸出無 `data-ui2-delta`；
  (d) Real 與 FAKE 不互相借用（Real 不含 FAKE 前綴）；
  (e) 突變負控：改成帶 value／changed 字樣 → 必紅。
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.models import (
    CapabilityState, FieldState, FieldVM, FirstScreenVM, FreshnessInfo, JudgementState, PageContext,
)
from shared.ui2_contract.pages import (
    P4_DATA, P4_HOLD, P4_ME, P4_MARKET, P4_TARGET, PAGE_IDS, SCENARIO_IDS,
)
from src.services.ui2 import real_feed as RF
from src.services.ui2 import vm_common
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import RealFeedSnapshot, get_real_page_vm
from src.ui2.components import html as H
from src.ui2.views import _page, hold, market

ROOT = Path(__file__).resolve().parent.parent
DELTA_PAGES = (P4_MARKET, P4_HOLD)
OTHER_PAGES = tuple(p for p in PAGE_IDS if p not in DELTA_PAGES)
EXPECTED_LABEL = "今日變化"
EXPECTED_DETAIL = "今日變化比較功能尚未開放"

#: 全站任何 UI 輸出不得出現的字樣（目標句未經 Copy Gate；「無變化」類＝把「不可比較」讀成「沒變」）。
FORBIDDEN_DELTA_PHRASES = (
    "今日無重大訊號變更", "暫無足夠資料比較", "無變化", "沒有變化", "維持昨日", "與昨日相同", "較昨日",
    "changed", "unchanged", "no change", "Δ", "↑", "↓",
)


def _real_degraded() -> RealFeedSnapshot:
    return RealFeedSnapshot.of(None, "Exception", None, "Exception", kbar_error="Exception")


def _all_vms():
    """(label, page, vm)：FAKE 六場景×五頁＋Real（降級 snapshot＋沙箱真實 snapshot）×五頁。"""
    out = []
    for p in PAGE_IDS:
        for sc in SCENARIO_IDS:
            out.append((f"fake/{sc}", p, get_preview_page_vm(p, sc)))
    for name, snap in (("real/degraded", _real_degraded()), ("real/sandbox", RF.read_real_snapshot())):
        for p in PAGE_IDS:
            out.append((name, p, get_real_page_vm(p, snap)))
    return out


ALL_VMS = _all_vms()
DELTA_VMS = [(lab, p, vm) for lab, p, vm in ALL_VMS if p in DELTA_PAGES]
OTHER_VMS = [(lab, p, vm) for lab, p, vm in ALL_VMS if p in OTHER_PAGES]


def check_delta_field(f: FieldVM | None) -> list[str]:
    """delta 欄位的完整形狀檢查器（供正向斷言與突變負控共用）。回傳違規清單，空＝合格。"""
    if f is None:
        return ["delta 缺（📊／💼 必須恆有誠實的『不可比較』列）"]
    bad: list[str] = []
    if f.capability is not CapabilityState.NOT_PROVIDED:
        bad.append(f"capability={f.capability!r}（只准 NOT_PROVIDED）")
    if f.state is not None:
        bad.append(f"state={f.state!r}（capability 軸不得帶資料／判定語意）")
    if f.value_text is not None:
        bad.append(f"value_text={f.value_text!r}（不可比較不得帶值）")
    if f.label != EXPECTED_LABEL:
        bad.append(f"label={f.label!r}")
    if not (f.status_text or "").startswith(T.TEXT_NOT_PROVIDED):
        bad.append(f"status_text={f.status_text!r}（須以既有 `⬜ 尚未提供` 開頭）")
    if not f.detail:
        bad.append("缺原因 detail")
    if f.freshness != FreshnessInfo():
        bad.append(f"freshness={f.freshness!r}（無比較來源／資料日，不得補）")
    blob = " ".join(x for x in (f.label, f.value_text, f.status_text, f.detail) if x)
    for w in FORBIDDEN_DELTA_PHRASES:
        if w in blob:
            bad.append(f"含禁用字樣 {w!r}")
    if re.search(r"\d", blob):
        bad.append("delta 字樣含數字（不得有變動量）")
    return bad


# ════════════════════════════════════════════════════════════════════
# (a) 契約欄位與所有場景的 producer
# ════════════════════════════════════════════════════════════════════
def test_pagecontext_delta_defaults_to_none_and_is_frozen():
    f = next(x for x in dataclasses.fields(PageContext) if x.name == "delta")
    assert f.default is None
    vm = get_preview_page_vm(P4_MARKET, "loaded")
    with pytest.raises(dataclasses.FrozenInstanceError):
        vm.context.delta = None                # type: ignore[misc]
    # 向後相容：不帶 delta 建構照舊可用
    fs = vm.context.first_screen
    assert PageContext(first_screen=fs).delta is None


@pytest.mark.parametrize("label,page,vm", DELTA_VMS, ids=lambda x: x if isinstance(x, str) else None)
def test_market_and_hold_always_carry_the_not_comparable_delta(label, page, vm):
    assert check_delta_field(vm.context.delta) == [], f"{label}/{page}"
    assert vm.context.delta.detail == EXPECTED_DETAIL
    assert vm.context.delta.status_text == T.TEXT_NOT_PROVIDED
    assert vm.context.delta.layer == "capability"


@pytest.mark.parametrize("label,page,vm", OTHER_VMS, ids=lambda x: x if isinstance(x, str) else None)
def test_other_pages_have_no_delta(label, page, vm):
    assert vm.context.delta is None, f"{label}/{page}"


def test_delta_never_borrows_across_feeds():
    """(d) Real 的 delta 不含 FAKE 前綴／FAKE 資料；FAKE 的 delta 也不冒充 Real（兩軸都是無資料的 capability 欄）。"""
    for lab, p, vm in DELTA_VMS:
        d = vm.context.delta
        blob = " ".join(x for x in (d.label, d.status_text, d.detail,
                                    d.freshness.source, d.freshness.as_of) if x)
        if not vm.is_fake:
            assert T.FAKE_SOURCE_PREFIX not in blob and "示意" not in blob, f"{lab}/{p}: Real delta 借用了 FAKE"
        assert d.freshness.source is None and d.freshness.as_of is None


@pytest.mark.parametrize("page", PAGE_IDS)
def test_canonical_cannot_inject_a_delta(page):
    """沒有比較管線：canonical 夾帶 delta（不論哪頁）一律 raise（VM 不接收、不創造變化量）。"""
    from src.services.ui2.scenarios import fake_canonical
    c = fake_canonical(page, "loaded")
    c["delta"] = {"label": "今日變化", "value": "+1.2%"}
    with pytest.raises(ValueError):
        vm_common.build_page_vm(c)


# ── PageContext 型別層：delta 若非 capability 一律 raise（fail closed）──
@pytest.mark.parametrize("bad", [
    FieldVM("今日變化", FieldState.OK, "無變化", None, None, FreshnessInfo()),
    FieldVM("今日變化", FieldState.MISSING, None, T.TEXT_MISSING_NOT_FETCHED, "x", FreshnessInfo()),
    FieldVM("今日變化", FieldState.STALE, "x", "⚠ 可能已過期", None, FreshnessInfo()),
    FieldVM("今日變化", JudgementState.UNDETERMINABLE, None, T.TEXT_RISK_CAP_UNDETERMINABLE, "x", FreshnessInfo()),
])
def test_pagecontext_rejects_a_non_capability_delta(bad):
    fs = get_preview_page_vm(P4_MARKET, "loaded").context.first_screen
    with pytest.raises((ValueError, TypeError)):
        PageContext(first_screen=fs, delta=bad)


def test_pagecontext_rejects_a_non_fieldvm_delta():
    fs = get_preview_page_vm(P4_MARKET, "loaded").context.first_screen
    with pytest.raises(TypeError):
        PageContext(first_screen=fs, delta="今日無重大訊號變更")     # type: ignore[arg-type]


def test_capability_delta_with_a_value_cannot_even_be_constructed():
    with pytest.raises(ValueError):
        FieldVM("今日變化", None, "無變化", T.TEXT_NOT_PROVIDED, "x", FreshnessInfo(), capability=CapabilityState.NOT_PROVIDED)


# ════════════════════════════════════════════════════════════════════
# 渲染：view 層（所有場景）
# ════════════════════════════════════════════════════════════════════
def _render(monkeypatch, vm, fn, *, allow_expander: bool = True) -> list[str]:
    import contextlib
    out: list[str] = []
    monkeypatch.setattr(_page.st, "markdown", lambda html, **kw: out.append(html))
    if allow_expander:      # 🎯 👤 🗂 有既有的預設收合 expander（本批不新增、不改）；這裡只收集 markdown
        monkeypatch.setattr(_page.st, "expander", lambda *a, **k: contextlib.nullcontext(), raising=False)
    else:
        monkeypatch.setattr(_page.st, "expander", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no expander")), raising=False)
    fn(vm)
    return out


def _view_of(page):
    from src.ui2.views import VIEWS
    return VIEWS[page]


@pytest.mark.parametrize("label,page,vm", DELTA_VMS, ids=lambda x: x if isinstance(x, str) else None)
def test_exactly_one_delta_row_rendered_on_market_and_hold(monkeypatch, label, page, vm):
    html = "".join(_render(monkeypatch, vm, _view_of(page), allow_expander=False))      # 📊／💼：本批不新增 expander
    assert html.count('data-ui2-delta="1"') == 1
    row = re.search(r'<div class="ui2-delta"[^>]*data-ui2-delta="1".*?</div>', html, re.S).group(0)
    assert 'data-axis="capability"' in row and 'data-state="not_provided"' in row
    assert EXPECTED_LABEL in row and T.TEXT_NOT_PROVIDED in row and EXPECTED_DETAIL in row
    assert "data-ui2-q" not in row                      # 不是量測錨點（不影響 q1～q4 排序／量測）
    assert "ui2-chip--axis-capability" in row           # 第二載體：虛線（capability 軸）
    assert "ui2-chip--danger" not in row                # 不可比較不是系統故障


@pytest.mark.parametrize("label,page,vm", OTHER_VMS, ids=lambda x: x if isinstance(x, str) else None)
def test_other_pages_render_no_delta_row(monkeypatch, label, page, vm):
    html = "".join(_render(monkeypatch, vm, _view_of(page)) if page != P4_DATA else
                   _render(monkeypatch, vm, lambda v: _view_of(page)(v, diag_check=None)))
    assert "data-ui2-delta" not in html and "ui2-delta" not in html


def test_market_dom_order_is_primary_then_delta_then_cards(monkeypatch):
    """📊：L1 → Primary（日 K／誠實空槽）→ Delta → 核心指標卡 → OneBrain（DEC-157 序不變，Delta 只插在 Primary 與卡片之間）。"""
    for sc in SCENARIO_IDS:
        vm = get_preview_page_vm(P4_MARKET, sc)
        out = _render(monkeypatch, vm, market.render)
        idx = {k: next(i for i, h in enumerate(out) if tok in h) for k, tok in (
            ("l1", 'class="ui2-m-l1"'), ("primary", "ui2-primary-slot"), ("delta", "data-ui2-delta"),
            ("grid", 'class="ui2-grid"'), ("onebrain", "ui2-m-onebrain"))}
        assert idx["l1"] < idx["primary"] < idx["delta"] < idx["grid"] < idx["onebrain"], (sc, idx)
    # Real（有日 K 事實時 Primary＝日 K 主圖）
    vm = get_real_page_vm(P4_MARKET, RF.read_real_snapshot())
    out = _render(monkeypatch, vm, market.render)
    prim = "ui2-kbar" if vm.context.kbar is not None else "ui2-primary-slot"
    i_p = next(i for i, h in enumerate(out) if prim in h)
    i_d = next(i for i, h in enumerate(out) if "data-ui2-delta" in h)
    i_g = next(i for i, h in enumerate(out) if 'class="ui2-grid"' in h)
    assert i_p < i_d < i_g


@pytest.mark.parametrize("sc", SCENARIO_IDS)
def test_hold_delta_is_inside_the_h_l1_container_right_after_the_qa_block(monkeypatch, sc):
    """💼：同一個 `.ui2-h-l1` 容器內、`.ui2-qa`（含主 CTA 列）之後、容器結尾之前；標題／狀態行／qa 內容不變。"""
    vm = get_preview_page_vm(P4_HOLD, sc)
    h = _render(monkeypatch, vm, hold.render)[0]
    assert h.startswith('<div class="ui2-h-l1">') and h.endswith("</div>")
    i_cta = h.index('data-ui2-q="q4"')
    i_delta = h.index('data-ui2-delta="1"')
    assert i_cta < i_delta and h.count("data-ui2-delta") == 1
    assert re.findall(r'data-ui2-q="(\w+)"', h) == ["q1", "ctx", "ctx", "q2", "q4"]      # 錨點與順序不變
    assert h.rstrip().endswith("</div></div>")                                             # delta 後直接收容器
    # 與沒有 delta 的舊版輸出相比：只多出 delta 那一個元素（其餘逐位相同）
    old_vm = dataclasses.replace(vm, context=dataclasses.replace(vm.context, delta=None))
    old = _render(monkeypatch, old_vm, hold.render)[0]
    delta_el = re.search(r'<div class="ui2-delta"[^>]*>.*?</div>(?=</div>$)', h, re.S).group(0)
    assert h == old[:-len("</div>")] + delta_el + "</div>"


def test_delta_html_none_renders_nothing():
    assert H.delta_below_html(None) == ""


def test_delta_html_is_a_pure_function_of_the_field_and_has_no_diff_logic():
    f = get_preview_page_vm(P4_MARKET, "loaded").context.delta
    assert H.delta_below_html(f) == H.delta_below_html(f)
    src = Path(H.__file__).read_text(encoding="utf-8")
    body = src[src.index("def delta_below_html"):]
    body = body[:body.index("\ndef ", 10)]
    for w in ("pct_change", "diff(", "subtract", " - ", "prev", "yesterday", "昨日", "compare("):
        assert w not in body, f"delta renderer 不得含比較運算：{w!r}"


# ════════════════════════════════════════════════════════════════════
# (b) 全站字樣守衛：view 層全場景＋原始碼
# ════════════════════════════════════════════════════════════════════
def _page_html(monkeypatch, page, vm) -> str:
    if page == P4_DATA:
        return "".join(_render(monkeypatch, vm, lambda v: _view_of(page)(v, diag_check=None)))
    return "".join(_render(monkeypatch, vm, _view_of(page)))


def _forbidden_in_html(html: str) -> list[str]:
    return [w for w in ("今日無重大訊號變更", "暫無足夠資料比較", "無變化", "維持昨日", "unchanged") if w in html]


@pytest.mark.parametrize("label,page,vm", ALL_VMS, ids=lambda x: x if isinstance(x, str) else None)
def test_no_forbidden_delta_phrase_in_any_rendered_page(monkeypatch, label, page, vm):
    assert _forbidden_in_html(_page_html(monkeypatch, page, vm)) == [], f"{label}/{page}"


def _string_literals(source: str) -> list[str]:
    """原始碼中的字串常數（去掉 docstring／註解：它們可以『提到』禁用句，但不得成為會被畫出或比對的字串值）。"""
    import ast
    tree = ast.parse(source)
    doc_ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant):
            doc_ids.add(id(n.body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc_ids]


_TARGET_PHRASES = ("今日無重大訊號變更", "暫無足夠資料比較")


def _scan_phrase_strings(source: str) -> list[str]:
    return [lit for lit in _string_literals(source) if any(w in lit for w in _TARGET_PHRASES)]


def test_no_target_or_no_change_sentence_in_any_source_string():
    """目標句與「今日無重大訊號變更」未經 Copy Gate：不得成為 src／shared 任何字串常數（含 text.py）。"""
    bad = []
    for d in ("src", "shared"):
        for p in (ROOT / d).rglob("*.py"):
            hit = _scan_phrase_strings(p.read_text(encoding="utf-8"))
            if hit:
                bad.append(f"{p.relative_to(ROOT)}: {hit}")
    assert bad == []


@pytest.mark.parametrize("inject", ['X = "今日無重大訊號變更"\n', 'def f():\n    return "⬜ 暫無足夠資料比較今日變化"\n'])
def test_phrase_scanner_has_teeth(inject):
    assert _scan_phrase_strings("x = 1\n") == []
    assert _scan_phrase_strings('"""doc 提到 今日無重大訊號變更 不算"""\nx = 1\n') == []     # docstring／註解可敘述禁令
    assert _scan_phrase_strings(inject)


def test_text_py_whitelists_are_unchanged_by_this_batch():
    """DEC-124：不新增資料態／前綴白名單。三張表的內容逐一釘死。"""
    assert set(T.ALLOWED_STATUS_PREFIXES) == {"ok", "missing", "stale", "unavailable", "not_evaluated"}
    assert T.CAPABILITY_STATUS_PREFIXES == {"not_provided": (T.TEXT_NOT_PROVIDED,)}
    assert T.JUDGEMENT_STATUS_PREFIXES == {"undeterminable": (T.TEXT_RISK_CAP_UNDETERMINABLE, T.TEXT_NOT_EVALUATED_DATA_SHORT)}
    assert {s.value for s in FieldState} == {"ok", "missing", "stale", "unavailable", "not_evaluated"}
    assert {s.value for s in CapabilityState} == {"provided", "not_provided"}


# ════════════════════════════════════════════════════════════════════
# (e) 突變負控：改成帶 value／changed 字樣 → 必紅
# ════════════════════════════════════════════════════════════════════
def _mutate_factory(monkeypatch, make):
    monkeypatch.setattr(vm_common, "delta_not_comparable_field", make)


def test_mutation_value_bearing_delta_cannot_be_built(monkeypatch):
    """producer 被改成『OK 帶值』→ 型別層（PageContext）直接 raise，頁面根本建不起來。"""
    _mutate_factory(monkeypatch, lambda: FieldVM(EXPECTED_LABEL, FieldState.OK, "無變化", None, None, FreshnessInfo()))
    with pytest.raises((ValueError, TypeError)):
        get_preview_page_vm(P4_MARKET, "loaded")
    with pytest.raises((ValueError, TypeError)):
        get_real_page_vm(P4_HOLD, _real_degraded())


@pytest.mark.parametrize("detail", ["今日無重大訊號變更", "⬜ 暫無足夠資料比較今日變化", "較昨日無變化 +0.0%", "unchanged"])
def test_mutation_forbidden_wording_is_caught_by_the_field_checker(monkeypatch, detail):
    """producer 被改成 capability 欄但原因句帶『無變化／changed』字樣（型別層放行）→ 形狀檢查器必紅。"""
    _mutate_factory(monkeypatch, lambda: FieldVM(
        EXPECTED_LABEL, None, None, T.TEXT_NOT_PROVIDED, detail, FreshnessInfo(), capability=CapabilityState.NOT_PROVIDED))
    vm = get_preview_page_vm(P4_MARKET, "loaded")
    assert check_delta_field(vm.context.delta), f"檢查器沒抓到 {detail!r}"


def test_mutation_missing_or_borrowed_freshness_is_caught():
    ok = get_preview_page_vm(P4_MARKET, "loaded").context.delta
    assert check_delta_field(ok) == []
    assert check_delta_field(None)
    assert check_delta_field(dataclasses.replace(ok, freshness=FreshnessInfo("2026-11-24", "FAKE:x")))
    assert check_delta_field(dataclasses.replace(ok, detail=None))
    assert check_delta_field(dataclasses.replace(ok, label="較昨日"))


def test_mutation_rendered_forbidden_text_is_caught_by_the_page_scan(monkeypatch):
    """渲染層被改成輸出『今日無重大訊號變更』→ 全站掃描必紅（掃描器本身不是 tautology）。"""
    monkeypatch.setattr(market, "delta_below_html", lambda f: '<div class="ui2-delta" data-ui2-delta="1">今日無重大訊號變更</div>')
    vm = get_preview_page_vm(P4_MARKET, "loaded")
    html = _page_html(monkeypatch, P4_MARKET, vm)
    assert _forbidden_in_html(html) == ["今日無重大訊號變更"]


# ════════════════════════════════════════════════════════════════════
# AppTest 整頁（slow lane）：全站任何輸出 markdown 掃描＋DOM 計數
# ════════════════════════════════════════════════════════════════════
def _at(feed: str, page: str, scenario: str | None = None):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app_ui2.py"), default_timeout=60)
    at.session_state["ui2_feed"] = feed
    at.query_params["ui2_dev"] = "1"
    at.run(timeout=60)
    if scenario:
        at.selectbox(key="ui2_scenario").set_value(scenario).run(timeout=60)
    at.radio(key="ui2_page").set_value(page).run(timeout=60)
    assert not at.exception
    return at


@pytest.mark.slow
@pytest.mark.parametrize("feed,scenario", [("real", None), ("fake", "cold"), ("fake", "stale"), ("fake", "unavailable")])
def test_apptest_every_page_has_no_forbidden_phrase_and_delta_only_on_market_and_hold(feed, scenario):
    for page in PAGE_IDS:
        at = _at(feed, page, scenario)
        blob = "\n".join(m.value for m in at.markdown)
        for w in ("今日無重大訊號變更", "暫無足夠資料比較", "無變化", "維持昨日", "unchanged"):
            assert w not in blob, f"{feed}/{scenario}/{page}: {w!r}"
        n = blob.count('data-ui2-delta="1"')
        assert n == (1 if page in DELTA_PAGES else 0), f"{feed}/{scenario}/{page}: delta 元素 {n} 個"
        if page in DELTA_PAGES:
            assert EXPECTED_LABEL in blob and EXPECTED_DETAIL in blob


@pytest.mark.slow
def test_apptest_no_new_expander_on_market_and_hold():
    for feed, sc in (("real", None), ("fake", "loaded")):
        for page in DELTA_PAGES:
            assert len(_at(feed, page, sc).expander) == 0, f"{feed}/{page}: 📊／💼 不得有 expander"
