"""New UI2 市場頁補強守衛（Issue #1138 工作 B；tests-only，只釘**現行**行為，不改 production）。

三個「被測行為正確、但缺回歸測試」的缺口：
- B  渲染層（U1／U5）：無值卡片 → 空白 value 樣式（`ui2-card__value--blank`，內容 `—`，不含數字）＋狀態 chip；
     真實 0.0／0 → 渲染 `0.0`／`0`（⛔ 變空白／未提供）；value=None → 恆為 MISSING 且不渲染數字（⛔ 補 0）。
- C  核心卡 id 完整性：`build_market_page_vm` 對「多 1 張／順序顛倒／重複 id」都 raise（match= 鎖原因）。
- A  日 K 掃描覆蓋：`vm.context.kbar`（field＋notes＋渲染）不在 `_all_fields` 的掃描範圍內 → 本檔補上
     與其他欄位相同的禁詞掃描，以及「非 OK／Stale 態不得帶 value_text」。（補強掃描範圍，不是修 bug。）
一般道：不連網、不啟瀏覽器、不依賴 Playwright。
"""
from __future__ import annotations

import dataclasses
import re
from html import unescape

import pytest

from shared.ui2_contract import text as T
from shared.ui2_contract.models import CardVM, FieldState, JudgementState, KbarChartVM
from shared.ui2_contract.pages import P4_HOLD, P4_MARKET, SCENARIO_IDS
from src.services import market_twii_view_service as TWS  # noqa: F401  (與 kbar 測試同源 fixture)
from src.services.market_twii_view_service import TwiiTrendView
from src.services.ui2 import market_vm, vm_common
from src.services.ui2.market_vm import MARKET_CARD_IDS
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import RealFeedSnapshot, get_real_page_vm
from src.services.ui2.scenarios import fake_canonical
from src.ui2.components import html as H
from src.ui2.views import _page, market
from tests.test_ui2_guards import _FORBIDDEN_ACTION_WORDS, _FORBIDDEN_TERMS
from tests.test_ui2_p1_human_text import _snapshots
from tests.test_ui2_twii_kbar import _card_view, _feed, _kbar_view, _matching_card

# 本測試自帶的方向／推薦詞（與 guards 的 _FORBIDDEN_ACTION_WORDS 取聯集）
_EXTRA_FORBIDDEN = ("加碼", "減碼", "看多", "看空", "買進", "賣出", "推薦", "排名")
_BANNED = tuple(dict.fromkeys(_FORBIDDEN_ACTION_WORDS + _FORBIDDEN_TERMS + _EXTRA_FORBIDDEN))


def _visible(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", html))


_VALUE_DIV = re.compile(r'<div class="ui2-card__value( ui2-card__value--blank)?">(.*?)</div>', re.S)


def _value_div(html: str) -> tuple[bool, str]:
    """回 (是否 blank 樣式, value 內文)。恰好一個 value div。"""
    ms = _VALUE_DIV.findall(html)
    assert len(ms) == 1, html
    return bool(ms[0][0]), ms[0][1]


def _card_in(blob: str, cid: str) -> str:
    """從整頁輸出切出單張卡（每張卡以 `<div class="ui2-card" data-card-id=` 起頭）。"""
    parts = re.split(r'(?=<div class="ui2-card" data-card-id=)', blob)
    hit = [p for p in parts if p.startswith(f'<div class="ui2-card" data-card-id="{cid}"')]
    assert len(hit) == 1, cid
    return hit[0]


def _chip_text(html: str) -> str:
    m = re.search(r'<div class="ui2-card__chips">(.*?)</div>', html, re.S)
    assert m, html
    return _visible(m.group(1)).strip()


# ══════════════════════════════════════════════════════════════════ B 渲染層
def _market_cards_html(vm) -> list[tuple[CardVM, str]]:
    return [(c, H.metric_card_html(c)) for c in vm.context.cards]


def _no_value_cards() -> list[tuple[str, CardVM, str]]:
    """跨 FAKE 六場景＋Real 全部快照，市場頁所有 value_text=None 的卡片。"""
    out: list[tuple[str, CardVM, str]] = []
    for sc in SCENARIO_IDS:
        vm = get_preview_page_vm(P4_MARKET, sc)
        out += [(f"fake/{sc}/{c.card_id}", c, h) for c, h in _market_cards_html(vm) if c.field.value_text is None]
    for name, snap in _snapshots().items():
        vm = get_real_page_vm(P4_MARKET, snap)
        out += [(f"real/{name}/{c.card_id}", c, h) for c, h in _market_cards_html(vm) if c.field.value_text is None]
    return out


def test_the_no_value_sweep_actually_covers_each_empty_axis():
    """守衛本身有料可掃：missing／unavailable／not_provided（capability）／stale-unknown 以外的無值態都出現過。"""
    seen = {(c.field.layer, c.field.capability.value if c.field.layer == "capability" else c.field.state.value)
            for _, c, _ in _no_value_cards()}
    assert ("capability", "not_provided") in seen
    assert any(s == "missing" for _, s in seen) and any(s == "unavailable" for _, s in seen)


def test_every_no_value_card_renders_blank_dash_without_digits_and_with_a_status_chip():
    cards = _no_value_cards()
    assert len(cards) >= 20
    for tag, card, h in cards:
        blank, body = _value_div(h)
        assert blank, f"{tag}: 無值卡片須用 ui2-card__value--blank"
        assert body == "—", f"{tag}: blank value 內容須為 —，收到 {body!r}"
        assert not re.search(r"\d", body), f"{tag}: blank value 不得含數字"
        chip = _chip_text(h)
        assert card.field.status_text and card.field.status_text in chip, f"{tag}: 須附狀態 chip（{chip!r}）"


def test_render_path_writes_blank_cards_for_a_missing_fake_market_page(monkeypatch):
    """經 `market.render` 真走一遍（不只是組件）：missing 場景的 vix／spread 兩卡是 blank。"""
    out: list[str] = []
    monkeypatch.setattr(market, "_md", out.append)
    monkeypatch.setattr(_page, "_md", out.append)
    market.render(get_preview_page_vm(P4_MARKET, "missing"))
    blob = "\n".join(out)
    for cid in ("vix", "spread"):
        h = _card_in(blob, cid)
        blank, body = _value_div(h)
        assert blank and body == "—" and 'data-state="missing"' in h, cid
    # 有值卡不得被誤標 blank
    assert _value_div(_card_in(blob, "twii")) == (False, "12,345.67")


@pytest.mark.parametrize("hint", ["unavailable", "not_evaluated", "undeterminable", "not_provided"])
def test_explicit_non_value_hints_drop_even_a_supplied_value_and_render_blank(hint):
    spec = {"key": "k", "label": "測試", "value": 123.45, "state": hint, "as_of": None, "source": None}
    card = vm_common.card_from_spec(spec)
    assert card.field.value_text is None
    blank, body = _value_div(H.metric_card_html(card))
    assert blank and body == "—"


@pytest.mark.parametrize("value, shown", [(0.0, "0.0"), (0, "0"), (-0.0, "-0.0")])
def test_a_real_zero_is_rendered_as_zero_not_blank_not_missing(value, shown):
    spec = {"key": "k", "label": "測試", "value": value, "as_of": "2026-10-20", "source": "測試源"}
    f = vm_common.field_from_spec(spec)
    assert f.state is FieldState.OK and f.value_text == shown and f.status_text is None
    h = H.metric_card_html(CardVM("k", "測試", f))
    blank, body = _value_div(h)
    assert not blank and body == shown
    assert 'data-state="ok"' in h and T.TEXT_MISSING_NOT_FETCHED not in h and T.TEXT_NOT_PROVIDED not in h


def test_a_real_zero_survives_the_whole_market_page_render_path(monkeypatch):
    c = fake_canonical(P4_MARKET, "loaded")
    c["cards"][1] = {**c["cards"][1], "value": 0.0}                       # vix 真實 0.0
    vm = market_vm.build_market_page_vm(c)
    vix = next(x for x in vm.context.cards if x.card_id == "vix")
    assert vix.field.state is FieldState.OK and vix.field.value_text == "0.0"
    out: list[str] = []
    monkeypatch.setattr(market, "_md", out.append)
    monkeypatch.setattr(_page, "_md", out.append)
    market.render(vm)
    assert _value_div(_card_in("\n".join(out), "vix")) == (False, "0.0")


@pytest.mark.parametrize("extra", [{}, {"state": "stale", "stale_days": 3}, {"missing_kind": "not_ready"}])
def test_value_none_is_always_missing_and_never_renders_a_number(extra):
    spec = {"key": "k", "label": "測試", "value": None, "as_of": None, "source": None, **extra}
    f = vm_common.field_from_spec(spec)
    assert f.state is FieldState.MISSING and f.value_text is None and f.status_text
    h = H.metric_card_html(CardVM("k", "測試", f))
    blank, body = _value_div(h)
    assert blank and body == "—" and not re.search(r"\d", body)
    assert 'data-state="missing"' in h and f.status_text in _chip_text(h)


# ══════════════════════════════════════════════════════════════════ C 核心卡 id 完整性
def _market_canonical() -> dict:
    return fake_canonical(P4_MARKET, "loaded")


def test_core_card_ids_positive_control():
    vm = market_vm.build_market_page_vm(_market_canonical())
    assert tuple(c.card_id for c in vm.context.cards) == MARKET_CARD_IDS


def test_one_extra_card_raises():
    c = _market_canonical()
    c["cards"] = [*c["cards"], {**c["cards"][0], "key": "extra_card"}]
    with pytest.raises(ValueError, match="市場頁核心指標卡須為"):
        market_vm.build_market_page_vm(c)


def test_reordered_cards_raise():
    c = _market_canonical()
    cards = list(c["cards"])
    cards[0], cards[1] = cards[1], cards[0]
    c["cards"] = cards
    assert {x["key"] for x in cards} == set(MARKET_CARD_IDS)             # 同一組 id，只有順序不同
    with pytest.raises(ValueError, match="市場頁核心指標卡須為"):
        market_vm.build_market_page_vm(c)


def test_reversed_cards_raise():
    c = _market_canonical()
    c["cards"] = list(reversed(c["cards"]))
    with pytest.raises(ValueError, match="市場頁核心指標卡須為"):
        market_vm.build_market_page_vm(c)


def test_duplicate_id_replacing_another_card_raises():
    c = _market_canonical()
    cards = list(c["cards"])
    cards[-1] = {**cards[0]}                                              # 張數不變，但 twii 出現兩次、pmi 消失
    c["cards"] = cards
    with pytest.raises(ValueError, match="市場頁核心指標卡須為"):
        market_vm.build_market_page_vm(c)


def test_duplicate_id_appended_raises():
    c = _market_canonical()
    c["cards"] = [*c["cards"], {**c["cards"][2]}]
    with pytest.raises(ValueError, match="市場頁核心指標卡須為"):
        market_vm.build_market_page_vm(c)


@pytest.mark.parametrize("n", [0, 5])
def test_missing_cards_raise(n):
    c = _market_canonical()
    c["cards"] = c["cards"][:n]
    with pytest.raises(ValueError, match="市場頁核心指標卡須為"):
        market_vm.build_market_page_vm(c)


def test_wrong_page_raises_with_its_own_message():
    with pytest.raises(ValueError, match="只接受市場頁"):
        market_vm.build_market_page_vm(fake_canonical(P4_HOLD, "loaded"))


# ══════════════════════════════════════════════════════════════════ A 日 K 掃描覆蓋
def _kbar_strings(k: KbarChartVM) -> list[str]:
    f = k.field
    out = [f.label, f.value_text or "", f.status_text or "", f.detail or "",
           f.freshness.as_of or "", f.freshness.source or "", *k.notes, *(c.date for c in k.candles)]
    return out


def _kbar_cases(monkeypatch) -> dict[str, KbarChartVM]:
    from shared import twii_ohlc_contract as OC
    from tests.test_ui2_twii_kbar import _bars, _dates

    good = _kbar_view()
    o, _h, _l, _c = _bars(20)
    bad_ohlc = _kbar_view(ohlc_ok=False, ohlc_error=sorted(OC.OHLC_REASON_CODES - {OC.READ_FAILED})[0],
                          open=(), high=(), low=(), n_ohlc=0)
    missing = TwiiTrendView(ok=False, error="讀不到", ohlc_requested=True, ohlc_ok=False, ohlc_error=OC.EMPTY,
                            ohlc_detail="讀不到")
    failed = TwiiTrendView(ok=False, failed=True, error="OSError: x", ohlc_requested=True, ohlc_ok=False,
                           ohlc_error=OC.READ_FAILED, ohlc_detail="OSError: x")
    specs = {
        "ok": dict(kbar=good),
        "partial": dict(kbar=_kbar_view(7)),
        "stale": dict(kbar=_kbar_view(is_stale=True, age_days=4, stale_reason="已 4 天沒有新資料")),
        "stale_unknown": dict(kbar=_kbar_view(is_stale=None, age_days=None)),
        "undeterminable": dict(kbar=bad_ohlc),
        "missing": dict(kbar=missing, card=TwiiTrendView(ok=False, error="讀不到")),
        "failed": dict(kbar=failed, card=_card_view(20000.0, "2026-10-20")),
        "contract_violation": dict(kbar=_kbar_view(open=o[:-1]), card=_matching_card(good)),
        "mismatch": dict(kbar=good, card=dataclasses.replace(_matching_card(good), as_of="2026-10-21")),
        "card_unavailable": dict(kbar=good, card=TwiiTrendView(ok=False, error="讀不到")),
    }
    _ = _dates
    out: dict[str, KbarChartVM] = {}
    for name, kw in specs.items():
        snap = _feed(monkeypatch, **kw)
        k = get_real_page_vm(P4_MARKET, snap).context.kbar
        assert k is not None, name
        out[name] = k
    return out


def test_kbar_matrix_covers_every_chart_state(monkeypatch):
    states = {k.field.state for k in _kbar_cases(monkeypatch).values()}
    assert {FieldState.OK, FieldState.STALE, FieldState.MISSING, FieldState.UNAVAILABLE,
            JudgementState.UNDETERMINABLE} <= states


def test_kbar_strings_and_rendering_carry_no_action_or_direction_words(monkeypatch):
    for name, k in _kbar_cases(monkeypatch).items():
        blob = "\n".join(_kbar_strings(k)) + "\n" + _visible(H.kbar_chart_html(k))
        for w in _BANNED:
            assert w not in blob, f"kbar/{name}: 出現禁用字樣 {w!r}"


def test_kbar_non_value_states_never_carry_a_value_text_or_candles(monkeypatch):
    for name, k in _kbar_cases(monkeypatch).items():
        f = k.field
        if f.state in (FieldState.OK, FieldState.STALE):
            assert f.value_text and re.fullmatch(r"[\d,]+\.\d{2}", f.value_text), f"kbar/{name}: {f.value_text!r}"
            assert k.candles, name
        else:
            assert f.value_text is None, f"kbar/{name}: 非 OK／Stale 態不得帶 value_text（{f.value_text!r}）"
            assert not k.candles, f"kbar/{name}: 非 OK／Stale 態不得帶 K 棒"
            assert f.status_text, f"kbar/{name}: 非 OK／Stale 態須有狀態字樣"


def test_kbar_scan_has_teeth_against_a_direction_word_in_field_or_notes(monkeypatch):
    """守衛自證：把『建議加碼』塞進 detail／notes／value，上面兩個掃描的判準都會抓到。"""
    k = _kbar_cases(monkeypatch)["partial"]
    dirty_detail = dataclasses.replace(k, field=dataclasses.replace(k.field, detail="建議加碼"))
    dirty_notes = dataclasses.replace(k, notes=(*k.notes, "看多"))
    for dirty in (dirty_detail, dirty_notes):
        blob = "\n".join(_kbar_strings(dirty)) + "\n" + _visible(H.kbar_chart_html(dirty))
        assert any(w in blob for w in _BANNED)
    # 非 OK 態帶值（補 0）：FieldVM 建構期即 raise——本檔的 value_text 檢查是第二道（針對 canonical → VM 全路徑）
    miss = _kbar_cases(monkeypatch)["missing"]
    with pytest.raises(ValueError, match="不得帶 value_text"):
        dataclasses.replace(miss.field, value_text="0.00")
