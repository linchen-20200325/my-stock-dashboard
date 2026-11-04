"""New UI2 UI Correction P2（客戶 2026-11-04 (19)；DEC-133）：OneBrain 位置＋台股 Primary 誠實空槽＋一行 SPEC。

驗收對象：
  (a) DOM 順序：今日主要風險 → OneBrain → 台股趨勢空槽 → 指標卡（FAKE 六場景＋Real 固定 snapshot）。
  (b) SPEC 的來源／資料日與 TWII 卡 freshness **逐字一致**；缺值不顯示偽資料日。
  (c) SPEC 含「最新收盤參考」、不含「日頻」；空槽 0 個圖形元素、含 `⬜ 尚未提供`、不是紅色。
  (d) OneBrain 內容與位置前後只差位置（文字集合相同）。
  (e) `market.render` 仍呼叫 `render_sections`（L2／L3 呈現政策仍受 P3 守衛約束）。
  (f) viewport 判定器新檢查的單元測試（含 mutation 轉紅）。
⛔ 不接歷史序列、不畫假走勢、不新增 MA、不改 VM／canonical（見 test_ui2_p3_evidence_preservation 的 baseline）。
"""
from __future__ import annotations

import re
from html import unescape
from pathlib import Path

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.models import CardVM, FieldState, FreshnessInfo
from shared.ui2_contract.pages import P4_HOLD, P4_MARKET, PAGE_IDS, SCENARIO_IDS
from src.services.ui2.preview_feed import get_preview_page_vm
from src.ui2.components import html as H
from src.ui2.shell import css as CSS
from src.ui2.views import _page, market
from tests.test_ui2_p1_human_text import _snapshots, hits_in

ROOT = Path(__file__).resolve().parent.parent
APP_UI2 = ROOT / "app_ui2.py"


# ── 以 stub 擷取 market.render 的 markdown 輸出（不需啟動 Streamlit）──────────────────────────
def _render_chunks(vm, monkeypatch) -> list[str]:
    out: list[str] = []
    monkeypatch.setattr(market, "_md", out.append)
    monkeypatch.setattr(_page, "_md", out.append)
    market.render(vm)
    return out


def _all_vms():
    for sc in SCENARIO_IDS:
        yield f"fake/{sc}", get_preview_page_vm(P4_MARKET, sc)
    from src.services.ui2.real_canonical import get_real_page_vm
    for name, snap in _snapshots().items():
        yield f"real/{name}", get_real_page_vm(P4_MARKET, snap)


def _twii(vm) -> CardVM:
    return next(c for c in vm.context.cards if c.card_id == "twii")


def _spec_of(html: str) -> str:
    m = re.search(r'data-ui2-spec="1">(.*?)</div>', html, flags=re.S)
    assert m, "找不到 SPEC 行"
    return unescape(m.group(1))


def _slot_of(chunks: list[str]) -> str:
    slots = [c for c in chunks if 'data-ui2-l1="primary_slot"' in c]
    assert len(slots) == 1
    return slots[0]


# ══════════════════════════════════════════════════════════════════ (a) 順序
def test_dom_order_risk_then_onebrain_then_primary_slot_then_cards(monkeypatch):
    for label, vm in _all_vms():
        chunks = _render_chunks(vm, monkeypatch)
        blob = "\n".join(chunks)
        pos = {k: blob.index(k) for k in ('class="ui2-pagetitle"', 'class="ui2-m-l1"', 'class="ui2-risk"',
                                          'data-ui2-l1="onebrain"', 'data-ui2-l1="primary_slot"', 'class="ui2-grid"')}
        order = ['class="ui2-pagetitle"', 'class="ui2-m-l1"', 'class="ui2-risk"', 'data-ui2-l1="onebrain"',
                 'data-ui2-l1="primary_slot"', 'class="ui2-grid"']
        assert [pos[k] for k in order] == sorted(pos[k] for k in order), label
        # 今日主要風險在 L1 容器內（與 OneBrain 之間沒有別的區塊）；OneBrain 緊接 L1 容器，空槽緊接 OneBrain
        i_l1 = next(i for i, c in enumerate(chunks) if 'class="ui2-m-l1"' in c)
        assert 'class="ui2-risk"' in chunks[i_l1], label
        assert 'data-ui2-l1="onebrain"' in chunks[i_l1 + 1], label
        assert 'data-ui2-l1="primary_slot"' in chunks[i_l1 + 2], label
        assert 'class="ui2-grid"' in chunks[i_l1 + 3], label
        assert blob.count("OneBrain Outlook") == 1, label


def test_dom_order_in_the_real_streamlit_page_default_lane():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(APP_UI2), default_timeout=60).run(timeout=60)
    assert not at.exception
    blob = "\n".join(m.value for m in at.markdown)
    idx = [blob.index(k) for k in ('class="ui2-risk"', 'data-ui2-l1="onebrain"', 'data-ui2-l1="primary_slot"', 'class="ui2-grid"')]
    assert idx == sorted(idx)
    assert "SPEC｜" in blob


def test_desktop_css_keeps_l1_grid_and_onebrain_is_single_row_only_on_desktop():
    css = CSS.CSS
    assert ".ui2-m-l1>.ui2-risk{grid-column:3;grid-row:3;margin:0}" in css                 # 三 tile 沒被動
    assert re.search(r"@media \(min-width:769px\)\{\s*\.ui2-m-onebrain\{display:flex", css)  # 桌機單行
    assert ".ui2-m-onebrain{display:flex" not in css.split("@media (min-width:769px){")[0].split("P2：OneBrain")[-1]


# ══════════════════════════════════════════════════════════════════ (b)(c) SPEC
def test_spec_source_and_asof_are_verbatim_from_the_twii_card_for_every_state(monkeypatch):
    for label, vm in _all_vms():
        card, fr = _twii(vm), _twii(vm).field.freshness
        spec = _spec_of(_slot_of(_render_chunks(vm, monkeypatch)))
        parts = spec.split("｜")
        assert parts[0] == "SPEC" and parts[1] == "最新收盤參考" and parts[-1] == "缺值不補", (label, spec)
        want = ["SPEC", "最新收盤參考"] + ([fr.source] if fr.source else []) + \
               [f"資料日 {fr.as_of}" if fr.as_of else T.TEXT_ASOF_MISSING] + ["缺值不補"]
        assert parts == want, (label, spec, fr)
        if not fr.source:
            assert len(parts) == 4, (label, spec)              # 來源缺值→整欄省略（不補預設來源）
        if not fr.as_of:
            assert re.search(r"\d{4}-\d{2}-\d{2}", spec) is None, (label, spec)    # 缺資料日不得出現任何日期
        assert card.card_id == "twii"


def test_real_spec_examples_are_exact(monkeypatch):
    from src.services.ui2.real_canonical import get_real_page_vm
    snaps = _snapshots()
    spec = lambda name: _spec_of(_slot_of(_render_chunks(get_real_page_vm(P4_MARKET, snaps[name]), monkeypatch)))  # noqa: E731
    assert spec("loaded") == "SPEC｜最新收盤參考｜本地加權指數歷史快取｜資料日 2026-11-02｜缺值不補"
    assert spec("stale") == "SPEC｜最新收盤參考｜本地加權指數歷史快取｜資料日 2026-11-02｜缺值不補"     # 過期仍標原資料日
    for name in ("unavailable", "contract_error"):
        assert spec(name) == "SPEC｜最新收盤參考｜⬜ 資料日未提供｜缺值不補", name
    # 卡缺資料日但仍帶來源（原樣）：SPEC 照卡——來源逐字帶出、資料日用既有字樣，⛔ 補日期
    assert spec("missing") == "SPEC｜最新收盤參考｜本地加權指數歷史快取｜⬜ 資料日未提供｜缺值不補"


def test_spec_never_says_daily_frequency_and_always_says_latest_close_reference(monkeypatch):
    for label, vm in _all_vms():
        spec = _spec_of(_slot_of(_render_chunks(vm, monkeypatch)))
        assert "最新收盤參考" in spec and "日頻" not in spec and "頻" not in spec.replace("最新收盤參考", ""), label
        assert hits_in(spec) == [], label                     # 新文案不得含工程詞
    assert "日頻" not in H.spec_line_text(FreshnessInfo(as_of="2026-11-02", source="X"))


def test_spec_with_no_card_or_empty_freshness_never_invents_source_or_date():
    assert H.spec_line_text(None) == "SPEC｜最新收盤參考｜⬜ 資料日未提供｜缺值不補"
    assert H.spec_line_text(FreshnessInfo()) == "SPEC｜最新收盤參考｜⬜ 資料日未提供｜缺值不補"
    assert "TWSE" not in H.spec_line_text(None)


# ══════════════════════════════════════════════════════════════════ (c) 空槽
def test_slot_is_an_honest_capability_placeholder_without_any_graphic(monkeypatch):
    for label, vm in _all_vms():
        slot = _slot_of(_render_chunks(vm, monkeypatch))
        low = slot.lower()
        for tag in ("<svg", "<polyline", "<canvas", "<img", "<path", "<line", "vega", "sparkline"):
            assert tag not in low, (label, tag)
        assert "🇹🇼 台股趨勢" in slot and T.TEXT_NOT_PROVIDED in slot and "此項目尚未開放" in slot, label
        assert 'data-axis="capability"' in slot and 'data-state="not_provided"' in slot, label
        assert "ui2-chip--danger" not in slot and "ui2-chip--warning" not in slot, label     # 灰底說明，⛔ 紅
        assert "MA" not in re.sub(r"<[^>]+>", " ", slot), label


def test_unavailable_or_missing_twii_card_does_not_turn_the_slot_into_a_data_state(monkeypatch):
    """槽是 Capability（DEC-124 三軸）：卡 Unavailable／Missing 時槽仍是 not_provided、非紅。"""
    from src.services.ui2.real_canonical import get_real_page_vm
    for name in ("unavailable", "contract_error", "missing"):
        vm = get_real_page_vm(P4_MARKET, _snapshots()[name])
        assert _twii(vm).field.state in (FieldState.UNAVAILABLE, FieldState.MISSING), name
        slot = _slot_of(_render_chunks(vm, monkeypatch))
        assert 'data-state="not_provided"' in slot and "unavailable" not in slot and "ui2-chip--danger" not in slot, name


def test_slot_height_follows_content_not_a_reserved_220px_frame():
    css = CSS.CSS
    block = re.search(r"\.ui2-primary-slot\{[^}]*\}", css).group(0)
    assert "height" not in block and "min-height" not in block                       # G-1=A
    assert "min-height" not in "".join(re.findall(r"\.ui2-primary-slot[^{]*\{[^}]*\}", css))
    assert "220px" not in css


# ══════════════════════════════════════════════════════════════════ (d) OneBrain 只差位置
def test_onebrain_content_is_unchanged_only_its_position_moves(monkeypatch):
    for label, vm in _all_vms():
        new = _render_chunks(vm, monkeypatch)
        # 舊畫面（P2 前）＝title → L1 → cards → render_sections(全部)
        old: list[str] = []
        monkeypatch.setattr(_page, "_md", old.append)
        _page.render_title(vm)
        old.append(H.market_l1_html(vm.context.first_screen, vm.context.main_risk))
        _page.render_cards(vm)
        _page.render_sections(vm)
        strip = lambda cs: sorted(re.sub(r"<[^>]+>", " ", "\n".join(cs)).split())   # noqa: E731
        slot_txt = sorted(re.sub(r"<[^>]+>", " ", _slot_of(new)).split())
        new_wo_slot = [c for c in new if 'data-ui2-l1="primary_slot"' not in c]
        wrapper = re.compile(r'^<div class="ui2-m-onebrain" data-ui2-l1="onebrain">(.*)</div>$', re.S)
        for i, c in enumerate(new_wo_slot):                         # 去掉 OneBrain 外層 wrapper 後與舊版區塊逐字相同
            m = wrapper.match(c)
            if m:
                new_wo_slot[i] = m.group(1)
        assert sorted(new_wo_slot) == sorted(old), label            # 區塊集合逐字相同（只差順序）
        assert strip(new) == sorted(strip(old) + slot_txt), label    # 文字集合＝舊＋空槽


def test_vm_onebrain_section_is_untouched():
    for sc in SCENARIO_IDS:
        vm = get_preview_page_vm(P4_MARKET, sc)
        sec = next(s for s in vm.context.sections if s.section_id == "onebrain")
        assert sec.level == "L1" and sec.title == "🤖 OneBrain Outlook"
        assert [f.status_text for f in sec.fields] == [T.TEXT_NOT_PROVIDED]
        assert [s.section_id for s in vm.context.sections][0] == "onebrain"      # VM 內順序沒動（只動畫的位置）


# ══════════════════════════════════════════════════════════════════ (e) render_sections 仍被呼叫
def test_market_render_still_goes_through_render_sections_with_onebrain_skipped(monkeypatch):
    calls: list[frozenset] = []
    real = _page.render_sections

    def spy(vm, **kw):
        calls.append(frozenset(kw.get("skip", ())))
        return real(vm, **kw)

    monkeypatch.setattr(market, "render_sections", spy)
    _render_chunks(get_preview_page_vm(P4_MARKET, "loaded"), monkeypatch)
    assert calls == [frozenset({"onebrain"})]


def test_other_pages_are_not_affected_by_the_skip_parameter():
    vm = get_preview_page_vm(P4_HOLD, "loaded")
    import inspect
    assert inspect.signature(_page.render_sections).parameters["skip"].default == frozenset()
    assert vm.page_id == P4_HOLD


# ══════════════════════════════════════════════════════════════════ (f) viewport 判定器單元測試
def _mv(**kw):
    from tests.ui2_viewport import measure_viewport as MV
    return MV, kw


def _p2_eval(m: dict) -> dict[str, list[str]]:
    from tests.ui2_viewport import measure_viewport as MV
    out = {t["id"]: [] for t in MV.THRESHOLDS}
    MV._evaluate_p2(m, out)
    return out


def _good(mobile=True, scenario="loaded") -> dict:
    return {"page": "p4_market", "scenario": scenario,
            "viewport": {"w": 390 if mobile else 1440, "h": 844 if mobile else 900},
            "nav": {"top": 791.0}, "first_block_after_l1_top": 600.0,
            "risk": {"top": 500.0, "bottom": 560.0},
            "elements": [{"q": "q2", "bottom": 300.0}, {"q": "q3", "bottom": 340.0}],
            "p2": {"onebrain": {"top": 570.0, "bottom": 620.0}, "slot": {"top": 630.0, "bottom": 720.0},
                   "grid": {"top": 730.0, "bottom": 900.0}, "slot_graphics": 0, "slot_danger": 0,
                   "slot_text": "🇹🇼 台股趨勢 ⬜ 尚未提供 此項目尚未開放 SPEC｜最新收盤參考｜X｜資料日 2026-11-02｜缺值不補",
                   "spec_text": "SPEC｜最新收盤參考｜X｜資料日 2026-11-02｜缺值不補"}}


def test_viewport_p2_checker_passes_the_good_layout_and_ignores_other_pages():
    assert not any(_p2_eval(_good()).values())
    assert not any(_p2_eval(_good(mobile=False)).values())
    other = _good()
    other["page"] = "p4_hold"
    other.pop("p2")
    assert not any(_p2_eval(other).values())
    assert not any(_p2_eval({"viewport": {"w": 390, "h": 844}}).values())            # 無 page 的舊 dict 略過


def test_viewport_p2_checker_has_teeth():
    k = "p2_onebrain_primary_slot_order"
    m = _good(); m["p2"]["grid"] = {"top": 640.0, "bottom": 800.0}                    # 手機指標卡跑到空槽之前
    assert _p2_eval(m)[k] != []
    m = _good(); m["p2"]["onebrain"] = {"top": 700.0, "bottom": 750.0}               # OneBrain 在空槽之後
    assert _p2_eval(m)[k] != []
    m = _good(); m["p2"]["onebrain"] = {"top": 300.0, "bottom": 350.0}               # OneBrain 在今日主要風險之前
    assert _p2_eval(m)[k] != []
    m = _good(mobile=False); m["p2"]["onebrain"] = {"top": 320.0, "bottom": 360.0}   # 桌機：在 q3 之前
    assert _p2_eval(m)[k] != []
    m = _good(); m["p2"]["slot_graphics"] = 1                                         # 假走勢
    assert _p2_eval(m)[k] != []
    m = _good(); m["p2"]["slot_text"] = "🇹🇼 台股趨勢 此項目尚未開放"                     # 缺 ⬜ 尚未提供
    assert _p2_eval(m)[k] != []
    m = _good(); m["p2"]["spec_text"] = "SPEC｜日頻｜X｜資料日 2026-11-02｜缺值不補"        # 缺最新收盤參考＋日頻
    assert _p2_eval(m)[k] != []
    m = _good(); m["p2"]["slot_danger"] = 1
    assert _p2_eval(m)[k] != []
    m = _good(); m["p2"] = None
    assert _p2_eval(m)[k] != []                                                       # 缺量測鍵＝紅


def test_viewport_nav_margin_160_applies_to_mobile_stale_and_unavailable_only():
    k = "p2_nav_margin_160"
    for sc in ("stale", "unavailable"):
        ok = _good(scenario=sc); ok["first_block_after_l1_top"] = 791.0 - 162.5
        assert _p2_eval(ok)[k] == []
        bad = _good(scenario=sc); bad["first_block_after_l1_top"] = 791.0 - 159.0
        assert _p2_eval(bad)[k] != []
    other = _good(scenario="loaded"); other["first_block_after_l1_top"] = 791.0 - 100.0
    assert _p2_eval(other)[k] == []
    desk = _good(mobile=False, scenario="stale"); desk["first_block_after_l1_top"] = 10.0
    assert _p2_eval(desk)[k] == []


def test_viewport_thresholds_registered_and_in_evaluate():
    from tests.ui2_viewport import measure_viewport as MV
    ids = {t["id"] for t in MV.THRESHOLDS}
    assert {"p2_onebrain_primary_slot_order", "p2_nav_margin_160"} <= ids
    assert MV.P2_NAV_MARGIN_MIN_PX == 160
