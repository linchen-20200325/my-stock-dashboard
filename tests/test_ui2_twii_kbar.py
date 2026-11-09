"""New UI2 📊 台股加權指數日 K 主圖（Issue #1099 PR-2；DEC-156 A／B／A）。

驗收對象（一般道，不連網、不啟瀏覽器；真瀏覽器量測見 `tests/ui2_viewport/measure_viewport.py --feed real`）：
- §1 讀取：卡片那次 `get_twii_trend_view(TWII_CARD_DAYS=1)` 不動；日 K 第二次呼叫 `(TWII_KBAR_DAYS=20, with_ohlc=True)`。
- §2 canonical 事實＋自洽檢查：每一種違反 → 日 K 紅色 Unavailable（契約違反），卡片與位階照常（隔離）。
- §3 卡片／日 K 同源對帳：as_of／最新收盤／is_stale／age_days／upstream_state／來源不一致 → 紅；卡片讀不到 → 灰（無法判定）。
- §4 狀態矩陣：ok／不足 20 根／stale／新鮮度未判定／ohlc 不合格（各原因碼→類別人話句）／missing／failed／例外。
- §5 VM 不變量（`KbarChartVM`／`CandleVM`）與 FAKE 軸恆無日 K（⛔ FAKE K 棒）。
- §6 渲染：紅綠灰逐根、文字圖例逐字、y 軸／起訖日期／資料日＋來源、不足字樣、stale 字樣同卡片、灰紅分離、
  ⛔ 量／均線／按鈕／FAKE 字樣／工程詞；版面只換 Primary 位置。
- §7 viewport 判定器新項 `kbar_primary_chart` 的牙。
"""
from __future__ import annotations

import dataclasses
import re
from html import unescape

import pytest

from shared import regime_arbiter as RA
from shared import twii_ohlc_contract as OC
from shared.allocation_decision import REGIME_LABEL
from shared.ui2_contract import text as T
from shared.ui2_contract.models import (
    CandleVM, FieldState, FieldVM, FreshnessInfo, JudgementState, KbarChartVM,
)
from shared.ui2_contract.pages import P4_MARKET, PAGE_IDS, SCENARIO_IDS
from src.services import allocation_service, market_twii_view_service as TWS
from src.services.market_twii_view_service import TWII_SOURCE_TEXT, TwiiTrendView
from src.services.ui2 import real_canonical as RC, real_feed as RF
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import RealFeedSnapshot, get_real_page_vm
from src.ui2.components import html as H
from src.ui2.views import _page, market
from tests.test_ui2_p1_human_text import _snapshots, hits_in, vm_visible_text
from tests.ui2_viewport import measure_viewport as MV

LEGEND = "紅｜收盤＞開盤　綠｜收盤＜開盤　灰｜收盤＝開盤"


# ── fixtures ─────────────────────────────────────────────────────────────
def _dates(n: int) -> tuple[str, ...]:
    return tuple(f"2026-10-{d:02d}" for d in range(1, n + 1))


def _bars(n: int):
    """n 根合法日 K：第 0 根紅（收>開）、第 1 根綠（收<開）、第 2 根灰十字（收==開），其後交替。"""
    o, h, lo, c = [], [], [], []
    for i in range(n):
        base = 20000.0 + i * 10
        if i % 3 == 0:
            op, cl = base, base + 50
        elif i % 3 == 1:
            op, cl = base + 50, base
        else:
            op = cl = base + 20
        o.append(op); c.append(cl); h.append(max(op, cl) + 30); lo.append(min(op, cl) - 30)
    return tuple(o), tuple(h), tuple(lo), tuple(c)


def _card_view(n_last_close: float, as_of: str, **kw) -> TwiiTrendView:
    d = dict(ok=True, xs=(as_of,), close=(n_last_close,), n_available=100, as_of=as_of, is_stale=False,
             stale_reason="", age_days=1, upstream_error="", error="", failed=False)
    d.update(kw)
    return TwiiTrendView(**d)


def _kbar_view(n: int = 20, **kw) -> TwiiTrendView:
    o, h, lo, c = _bars(n)
    xs = _dates(n)
    d = dict(ok=True, xs=xs, close=c, n_available=100, as_of=xs[-1], is_stale=False, stale_reason="", age_days=1,
             upstream_error="", error="", failed=False, ohlc_requested=True, ohlc_ok=True, ohlc_error="",
             ohlc_detail="", open=o, high=h, low=lo, n_ohlc=n)
    d.update(kw)
    return TwiiTrendView(**d)


def _matching_card(kv: TwiiTrendView, **kw) -> TwiiTrendView:
    return _card_view(kv.close[-1], kv.as_of, is_stale=kv.is_stale, age_days=kv.age_days,
                      stale_reason=kv.stale_reason, **kw)


def _regime_dict():
    return {"regime": "bull", "light": "🟢", "source": RA.SOURCE_BULL_SCORE, "trend_regime": None, "health": None,
            "defense": False, "exposure_limit_pct": None, "traffic_light": None, "is_loaded": True,
            "risk_cap_disclosure": None}


def _feed(monkeypatch, *, card=None, kbar=None, card_exc=None, kbar_exc=None, calls=None) -> RealFeedSnapshot:
    """經**真 feed** 跑：只把 canonical service 換成注入版本（支援 `with_ohlc` 關鍵字）。"""
    calls = calls if calls is not None else []
    kbar = kbar if kbar is not None else _kbar_view()
    card = card if card is not None else _matching_card(kbar)

    def fake_twii(n, **kw):
        calls.append((n, kw))
        if kw.get("with_ohlc"):
            if kbar_exc:
                raise kbar_exc
            return kbar
        if card_exc:
            raise card_exc
        return card

    monkeypatch.setattr(TWS, "get_twii_trend_view", fake_twii)
    monkeypatch.setattr(allocation_service, "get_macro_regime", lambda **kw: _regime_dict())
    return RF.read_real_snapshot()


def _chart(snap) -> KbarChartVM:
    k = get_real_page_vm(P4_MARKET, snap).context.kbar
    assert k is not None
    return k


def _card_field(snap) -> FieldVM:
    return get_real_page_vm(P4_MARKET, snap).context.cards[0].field


def _render(vm, monkeypatch) -> list[str]:
    out: list[str] = []
    monkeypatch.setattr(market, "_md", out.append)
    monkeypatch.setattr(_page, "_md", out.append)
    market.render(vm)
    return out


def _visible(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", html))


# ══════════════════════════════════════════════════════════════════ §1 讀取
def test_card_read_is_unchanged_and_kbar_is_a_second_read_of_the_same_service(monkeypatch):
    calls: list = []
    _feed(monkeypatch, calls=calls)
    assert calls[0] == (RF.TWII_CARD_DAYS, {}) and RF.TWII_CARD_DAYS == 1           # 卡片那次：1 日、無關鍵字（不變）
    assert calls[1] == (RF.TWII_KBAR_DAYS, {"with_ohlc": True})
    assert len(calls) == 2


def test_kbar_window_is_the_dec156_mobile_default_and_pinned_across_feed_and_canonical():
    assert RF.TWII_KBAR_DAYS == RC.KBAR_VISIBLE_BARS == 20


def test_real_parquet_end_to_end_is_same_source_as_the_service(monkeypatch):
    """真 git 追蹤 parquet（相對斷言，⛔ 寫死數值／ohlc_ok）：日 K 事實＝service 直接結果；合格時畫的就是那 20 根。"""
    snap = RF.read_real_snapshot()
    direct = TWS.get_twii_trend_view(RF.TWII_KBAR_DAYS, with_ohlc=True)
    chart = _chart(snap)
    if snap.kbar is None:                                   # 讀不到／契約違反：只能是紅
        assert chart.field.state is FieldState.UNAVAILABLE and not chart.candles
        return
    k = snap.kbar
    assert (k.ok, k.ohlc_ok, k.ohlc_reason, k.xs, k.opens, k.highs, k.lows, k.closes, k.as_of, k.is_stale) == (
        direct.ok, direct.ohlc_ok, direct.ohlc_error, direct.xs, direct.open, direct.high, direct.low, direct.close,
        direct.as_of, direct.is_stale)
    if direct.ohlc_ok is True and snap.twii is not None and snap.twii.as_of == direct.as_of:
        assert [c.date for c in chart.candles] == list(direct.xs)
        assert [(c.open, c.high, c.low, c.close) for c in chart.candles] == list(
            zip(direct.open, direct.high, direct.low, direct.close))
        assert chart.field.value_text == _card_field(snap).value_text           # 卡片與圖同值
        assert chart.field.freshness.as_of == _card_field(snap).freshness.as_of == direct.as_of
        assert chart.field.freshness.source == TWII_SOURCE_TEXT
    else:
        assert not chart.candles


# ══════════════════════════════════════════════════════════════════ §2 契約違反（隔離）
def _swap(t: tuple, i: int, v):
    return t[:i] + (v,) + t[i + 1:]


_o, _h, _l, _c = _bars(20)
_VIOLATIONS = {
    "length_mismatch": dict(open=_o[:-1]),
    "not_ascending": dict(xs=_swap(_dates(20), 5, "2026-10-01")),
    "duplicate_date": dict(xs=_swap(_dates(20), 3, "2026-10-03")),
    "bad_date": dict(xs=_swap(_dates(20), 2, "2026/10/03")),
    "nan_open": dict(open=_swap(_o, 4, float("nan"))),
    "inf_high": dict(high=_swap(_h, 4, float("inf"))),
    "zero_low": dict(low=_swap(_l, 4, 0.0)),
    "negative_close": dict(close=_swap(_c, 19, -1.0)),
    "bool_price": dict(open=_swap(_o, 0, True)),
    "high_below_close": dict(high=_swap(_h, 0, _c[0] - 1)),
    "low_above_open": dict(low=_swap(_l, 1, _o[1] + 1)),
    "too_many_bars": "21",
    "zero_bars_but_ok": dict(xs=(), open=(), high=(), low=(), close=(), n_ohlc=0),
    "last_date_ne_as_of": dict(as_of="2026-10-19"),
    "ohlc_ok_none": dict(ohlc_ok=None),
    "ohlc_ok_with_reason": dict(ohlc_error=OC.NOT_FINITE),
    "failed_but_ohlc_ok": dict(failed=True, ok=False),
    "unknown_reason": dict(ohlc_ok=False, ohlc_error="MYSTERY", open=(), high=(), low=()),
    "partial_fill_when_bad": dict(ohlc_ok=False, ohlc_error=OC.INCOMPLETE_BAR),      # 不合格卻仍帶開高低
    "is_stale_not_bool": dict(is_stale=1),
    "ok_and_failed": dict(failed=True),
    "bad_upstream_state": dict(upstream_state="WHATEVER"),
}


def _bad_view(name: str) -> TwiiTrendView:
    spec = _VIOLATIONS[name]
    if spec == "21":
        o, h, lo, c = _bars(21)
        xs = tuple(f"2026-09-{d:02d}" for d in range(10, 31))
        return _kbar_view(21, xs=xs, open=o, high=h, low=lo, close=c, as_of=xs[-1], n_ohlc=21)
    if name == "is_stale_not_bool":
        return dataclasses.replace(_kbar_view(), is_stale=1)
    if name == "bad_upstream_state":
        return dataclasses.replace(_kbar_view(), upstream_state="WHATEVER")
    return _kbar_view(**spec)


@pytest.mark.parametrize("name", list(_VIOLATIONS))
def test_every_contract_violation_makes_only_the_chart_red(monkeypatch, capsys, name):
    good = _kbar_view()
    snap = _feed(monkeypatch, kbar=_bad_view(name), card=_matching_card(good))
    assert snap.kbar is None and snap.kbar_error == RC.CONTRACT_ERROR, name
    chart = _chart(snap)
    assert chart.field.state is FieldState.UNAVAILABLE and not chart.candles, name
    assert "資料格式異常" in (chart.field.detail or "")
    assert "RealFeedContractError" in capsys.readouterr().out                 # 全文只進 log
    # 隔離：卡片與位階照常
    assert _card_field(snap).state is FieldState.OK and _card_field(snap).value_text == f"{good.close[-1]:,.2f}"
    vm = get_real_page_vm(P4_MARKET, snap)
    assert vm.context.first_screen.current_state.value_text == REGIME_LABEL["bull"]


@pytest.mark.parametrize("name", list(_VIOLATIONS))
def test_pure_validator_rejects_each_violation_directly(name):
    v = _bad_view(name)
    with pytest.raises(RC.RealFeedContractError):
        RC.twii_kbar_fact_of(v)


def test_pure_converter_still_raises_on_a_bad_fact_fed_directly():
    """防呆：直接建 snapshot 塞壞 fact（繞過 feed）→ 純轉換 fail loud（程式錯誤，不是資料狀態）。"""
    good = RC.twii_kbar_fact_of(_kbar_view())
    bad = dataclasses.replace(good, xs=tuple(reversed(good.xs)))
    snap = RealFeedSnapshot.of(_snapshots()["loaded"].twii, "", _snapshots()["loaded"].regime, "", kbar=bad)
    with pytest.raises(RC.RealFeedContractError):
        get_real_page_vm(P4_MARKET, snap)


def test_kbar_exception_is_red_and_isolated(monkeypatch, capsys):
    snap = _feed(monkeypatch, kbar_exc=RuntimeError("boom token=SECRET"))
    assert snap.kbar is None and snap.kbar_error == "RuntimeError"
    chart = _chart(snap)
    assert chart.field.state is FieldState.UNAVAILABLE and "台股日 K暫時無法讀取" == chart.field.detail
    assert "SECRET" not in repr(snap) and "SECRET" not in vm_visible_text(get_real_page_vm(P4_MARKET, snap))
    assert "boom" in capsys.readouterr().out
    assert _card_field(snap).state is FieldState.OK


def test_card_failure_does_not_crash_the_chart_and_the_chart_is_grey_not_drawn(monkeypatch):
    """卡片讀不到 → 日 K 無法對帳（⛔ 假裝同源）→ 灰 `⬜ 無法判定`、不畫；不是紅（日 K 本身沒有出錯）。"""
    snap = _feed(monkeypatch, card_exc=OSError("disk"))
    assert snap.twii is None and snap.kbar is not None
    chart = _chart(snap)
    assert chart.field.state is JudgementState.UNDETERMINABLE and not chart.candles
    assert chart.field.status_text == T.TEXT_RISK_CAP_UNDETERMINABLE
    assert "無法確認日 K 與其同步" in chart.field.detail
    assert _card_field(snap).state is FieldState.UNAVAILABLE


def test_snapshot_kbar_error_must_be_an_identifier_and_exclusive():
    base = _snapshots()["loaded"]
    good = RC.twii_kbar_fact_of(_kbar_view())
    with pytest.raises(ValueError):
        RealFeedSnapshot(base.twii, "", base.regime, "", kbar=good, kbar_error="OSError")
    with pytest.raises(ValueError):
        RealFeedSnapshot(base.twii, "", base.regime, "", kbar_error="OSError: /home token=X")
    assert RealFeedSnapshot.of(base.twii, "", base.regime, "", kbar_error="x: y").kbar_error == "Exception"


# ══════════════════════════════════════════════════════════════════ §3 同源對帳
@pytest.mark.parametrize("card_kw", [
    dict(as_of="2026-10-21"),                       # 卡片資料日不同（兩次讀取之間 cron 寫入）
    dict(close=(1.0,)),                             # 最新收盤不同
    dict(is_stale=True),                            # 新鮮度不同
    dict(age_days=9),
    dict(upstream_error="HTTP 500"),                # 上游三態不同（FETCH_FAILED vs ""）
    dict(source="別的來源"),
])
def test_card_and_chart_must_be_the_same_snapshot_or_the_chart_is_red(monkeypatch, card_kw):
    kv = _kbar_view()
    card = _matching_card(kv)
    card = dataclasses.replace(card, **card_kw)
    snap = _feed(monkeypatch, kbar=kv, card=card)
    chart = _chart(snap)
    assert chart.field.state is FieldState.UNAVAILABLE and not chart.candles
    assert chart.field.detail == RC.KBAR_MISMATCH_TEXT
    assert _card_field(snap).state in (FieldState.OK, FieldState.STALE)        # 卡片照常


def test_same_snapshot_passes_the_cross_check(monkeypatch):
    chart = _chart(_feed(monkeypatch))
    assert chart.field.state is FieldState.OK and len(chart.candles) == 20


# ══════════════════════════════════════════════════════════════════ §4 狀態矩陣
def test_ok_twenty_bars(monkeypatch):
    kv = _kbar_view()
    snap = _feed(monkeypatch, kbar=kv)
    chart = _chart(snap)
    assert chart.field.state is FieldState.OK and chart.field.status_text is None
    assert len(chart.candles) == 20 and chart.notes == () and chart.target_n == 20
    assert chart.field.value_text == _card_field(snap).value_text == f"{kv.close[-1]:,.2f}"
    assert chart.field.freshness == FreshnessInfo(as_of=kv.as_of, source=TWII_SOURCE_TEXT)


@pytest.mark.parametrize("n", [1, 7, 19])
def test_fewer_than_twenty_bars_draws_what_exists_and_says_so(monkeypatch, n):
    chart = _chart(_feed(monkeypatch, kbar=_kbar_view(n)))
    assert len(chart.candles) == n                                   # ⛔ 補棒
    assert chart.notes == (f"僅 {n} 根（不足 20）",)


def test_stale_draws_bars_with_the_same_badge_as_the_card(monkeypatch):
    kv = _kbar_view(is_stale=True, age_days=4, stale_reason="已 4 天沒有新資料")
    snap = _feed(monkeypatch, kbar=kv)
    chart, card = _chart(snap), _card_field(snap)
    assert chart.field.state is FieldState.STALE and len(chart.candles) == 20
    assert chart.field.status_text == card.status_text == "⚠ 過期 4 天"
    assert chart.field.detail == card.detail == "已 4 天沒有新資料"


def test_unknown_freshness_is_stale_never_ok(monkeypatch):
    kv = _kbar_view(is_stale=None, age_days=None)
    snap = _feed(monkeypatch, kbar=kv)
    chart, card = _chart(snap), _card_field(snap)
    assert chart.field.state is FieldState.STALE and chart.field.status_text == T.TEXT_STALE_UNKNOWN
    assert "新鮮度未判定" in chart.field.detail and chart.field.detail == card.detail
    assert len(chart.candles) == 20


@pytest.mark.parametrize("code", sorted(OC.OHLC_REASON_CODES - {OC.READ_FAILED}))
def test_ohlc_not_ok_is_grey_with_a_human_category_never_the_code(monkeypatch, code):
    kv = _kbar_view(ohlc_ok=False, ohlc_error=code, open=(), high=(), low=(), n_ohlc=0)
    snap = _feed(monkeypatch, kbar=kv)
    chart = _chart(snap)
    assert chart.field.state is JudgementState.UNDETERMINABLE and not chart.candles
    assert code not in (chart.field.detail or "") and "，這次不畫日 K（缺值不補）" in chart.field.detail
    assert _card_field(snap).state is FieldState.OK


def test_missing_cache_is_grey_missing(monkeypatch):
    kv = TwiiTrendView(ok=False, error="讀不到", ohlc_requested=True, ohlc_ok=False, ohlc_error=OC.EMPTY,
                       ohlc_detail="讀不到")
    card = TwiiTrendView(ok=False, error="讀不到")
    chart = _chart(_feed(monkeypatch, kbar=kv, card=card))
    assert chart.field.state is FieldState.MISSING and chart.field.status_text == T.TEXT_MISSING_NOT_FETCHED
    assert not chart.candles


def test_service_failed_is_red(monkeypatch):
    kv = TwiiTrendView(ok=False, failed=True, error="OSError: x", ohlc_requested=True, ohlc_ok=False,
                       ohlc_error=OC.READ_FAILED, ohlc_detail="OSError: x")
    chart = _chart(_feed(monkeypatch, kbar=kv, card=_card_view(20000.0, "2026-10-20")))
    assert chart.field.state is FieldState.UNAVAILABLE and chart.field.detail == "台股日 K暫時無法讀取"
    assert not re.search(r"\w+(Error|Exception)", chart.field.detail)


# ══════════════════════════════════════════════════════════════════ §5 VM 不變量／FAKE 軸
def _f_ok(v="1.00") -> FieldVM:
    return FieldVM("x", FieldState.OK, v)


def test_kbar_vm_invariants():
    c = CandleVM("2026-10-01", 10.0, 12.0, 9.0, 11.0)
    KbarChartVM(_f_ok(), (c,))
    with pytest.raises(ValueError):
        KbarChartVM(_f_ok(), ())                                                 # OK 卻沒 K 棒
    with pytest.raises(ValueError):
        KbarChartVM(FieldVM("x", FieldState.MISSING, None, T.TEXT_MISSING_NOT_FETCHED), (c,))   # 灰態帶棒
    with pytest.raises(ValueError):
        KbarChartVM(_f_ok(), (c, c))                                             # 日期重複
    with pytest.raises(ValueError):
        KbarChartVM(_f_ok(), tuple(CandleVM(f"2026-10-{d:02d}", 10.0, 12.0, 9.0, 11.0) for d in range(1, 4)),
                    target_n=2)                                                  # 超過可見根數
    for bad in [("2026-10-01", 10.0, 12.0, 9.0, 13.0), ("2026-10-01", 10.0, 12.0, 10.5, 11.0),
                ("2026-10-01", float("nan"), 12.0, 9.0, 11.0), ("2026-10-01", 0.0, 12.0, 0.0, 11.0),
                ("10/01", 10.0, 12.0, 9.0, 11.0)]:
        with pytest.raises(ValueError):
            CandleVM(*bad)


@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_fake_axis_never_carries_a_kbar(scenario):
    """FAKE 示意軸 ⇒ 沒有日 K 事實（⛔ FAKE K 棒；P2 規格：FAKE 台股值不得當歷史序列）→ 主圖照舊誠實空槽。"""
    for p in PAGE_IDS:
        assert get_preview_page_vm(p, scenario).context.kbar is None


def test_kbar_only_on_the_market_page(monkeypatch):
    snap = _feed(monkeypatch)
    for p in PAGE_IDS:
        vm = get_real_page_vm(p, snap)
        assert (vm.context.kbar is not None) == (p == P4_MARKET), p


def test_snapshot_without_a_kbar_fact_keeps_the_honest_slot(monkeypatch):
    vm = get_real_page_vm(P4_MARKET, _snapshots()["loaded"])
    assert vm.context.kbar is None
    chunks = _render(vm, monkeypatch)
    assert sum('data-ui2-l1="primary_slot"' in c for c in chunks) == 1
    assert not any('data-ui2-l1="primary_chart"' in c for c in chunks)


def test_vm_context_independent_of_presentation_slice(monkeypatch):
    snap = _feed(monkeypatch)
    base = get_real_page_vm(P4_MARKET, snap)
    for n in (0, 2, 99):
        assert get_real_page_vm(P4_MARKET, snap, top_n=n).context == base.context


# ══════════════════════════════════════════════════════════════════ §6 渲染
def _chart_html(monkeypatch, **kw) -> str:
    vm = get_real_page_vm(P4_MARKET, _feed(monkeypatch, **kw))
    chunks = _render(vm, monkeypatch)
    charts = [c for c in chunks if 'data-ui2-l1="primary_chart"' in c]
    assert len(charts) == 1 and not any('data-ui2-l1="primary_slot"' in c for c in chunks)
    return charts[0]


def test_each_bar_is_coloured_by_same_day_open_vs_close(monkeypatch):
    kv = _kbar_view()
    html = _chart_html(monkeypatch, kbar=kv)
    dirs = re.findall(r'data-kbar-dir="(\w+)" data-kbar-date="([\d-]+)"', html)
    assert len(dirs) == 20
    for (d, date), o, c in zip(dirs, kv.open, kv.close):
        want = "up" if c > o else ("down" if c < o else "flat")
        assert d == want, (date, o, c)
    groups = re.findall(r'<g class="ui2-kbar__c ui2-kbar__c--(\w+)"[^>]*>(.*?)</g>', html)
    want_col = {"up": "#ef5564", "down": "#25be87", "flat": "#9aaec0"}
    assert {d for d, _ in groups} == {"up", "down", "flat"}
    for d, inner in groups:
        assert f'stroke="{want_col[d]}"' in inner and f'fill="{want_col[d]}"' in inner


def test_direction_is_strict_and_equal_is_grey():
    assert H.kbar_direction(100.0, 100.01) == "up"
    assert H.kbar_direction(100.01, 100.0) == "down"
    assert H.kbar_direction(100.0, 100.0) == "flat"
    assert H.kbar_direction(0.1 + 0.2, 0.3) == "flat"                      # 只吸收浮點表示誤差


def test_legend_is_verbatim_text_and_colour_is_not_the_only_carrier(monkeypatch):
    html = _chart_html(monkeypatch)
    leg = re.search(r'data-ui2-kbar-legend="1">(.*?)</div>', html).group(1)
    assert _visible(leg).replace(" ", "") == LEGEND.replace(" ", "") and unescape(re.sub(r"<[^>]+>", "", leg)) == LEGEND
    assert H.kbar_legend_text() == LEGEND == MV.KBAR_LEGEND_TEXT


def test_axis_dates_meta_and_height(monkeypatch):
    kv = _kbar_view()
    html = _chart_html(monkeypatch, kbar=kv)
    assert 'height="220"' in html and 'width="100%"' in html                    # DEC-156 B：約 220px
    ylabels = re.findall(r'<svg class="ui2-kbar__yaxis"[^>]*>(.*?)</svg>', html)[0]
    nums = [float(x.replace(",", "")) for x in re.findall(r">([\d,]+)</text>", ylabels)]
    assert len(nums) == 5 and nums == sorted(nums, reverse=True)
    assert min(kv.low) >= nums[-1] and max(kv.high) <= nums[0]                  # 刻度涵蓋全部價格
    vis = _visible(html)
    assert kv.xs[0] in vis and kv.xs[-1] in vis                                 # 起訖日期
    meta = unescape(re.search(r'data-ui2-kbar-meta="1">(.*?)</div>', html).group(1))
    assert meta == f"資料日 {kv.as_of}｜{TWII_SOURCE_TEXT}｜缺值不補"
    assert "單位：指數點" in vis and "不是相對前一日漲跌" in vis


def test_no_volume_ma_signals_or_controls(monkeypatch):
    html = _chart_html(monkeypatch)
    vis = _visible(html)
    for w in ("MA", "均線", "成交量", "volume", "量能", "買", "賣", "訊號"):
        assert w not in vis, w
    for tag in ("<button", "<input", "<select", "<a ", "onclick", "<script", "<canvas", "<img"):
        assert tag not in html.lower(), tag
    assert "FAKE" not in html and "示意" not in vis
    assert hits_in(vis) == []


def test_partial_text_is_shown(monkeypatch):
    html = _chart_html(monkeypatch, kbar=_kbar_view(7))
    assert "僅 7 根（不足 20）" in _visible(html)
    assert len(re.findall(r"data-kbar-dir=", html)) == 7


def test_stale_badge_is_rendered_like_the_card(monkeypatch):
    kv = _kbar_view(is_stale=True, age_days=4, stale_reason="已 4 天沒有新資料")
    html = _chart_html(monkeypatch, kbar=kv)
    assert 'data-state="stale"' in html and "ui2-chip--warning" in html and "⚠ 過期 4 天" in html
    assert len(re.findall(r"data-kbar-dir=", html)) == 20 and "ui2-chip--danger" not in html


@pytest.mark.parametrize("kw,state,tone,axis", [
    (dict(kbar_exc=RuntimeError("x")), "unavailable", "ui2-chip--danger", "data"),
    (dict(kbar=_kbar_view(ohlc_ok=False, ohlc_error=OC.INCOMPLETE_BAR, open=(), high=(), low=(), n_ohlc=0)),
     "undeterminable", "ui2-chip--neutral", "judgement"),
    (dict(card_exc=OSError("x")), "undeterminable", "ui2-chip--neutral", "judgement"),
])
def test_empty_and_error_states_have_no_graphics_and_grey_red_split(monkeypatch, kw, state, tone, axis):
    html = _chart_html(monkeypatch, **kw)
    assert f'data-state="{state}"' in html and f'data-axis="{axis}"' in html and tone in html
    for tag in ("<svg", "<rect", "<line", "data-kbar-dir", "data-ui2-kbar-legend"):
        assert tag not in html, tag
    if state != "unavailable":
        assert "ui2-chip--danger" not in html                                   # 灰 ≠ 紅（§1.A-4）
    assert hits_in(_visible(html)) == [] and not re.search(r"\w+(Error|Exception)", _visible(html))


def test_chart_takes_exactly_the_primary_slot_position(monkeypatch):
    vm = get_real_page_vm(P4_MARKET, _feed(monkeypatch))
    chunks = _render(vm, monkeypatch)
    i_l1 = next(i for i, c in enumerate(chunks) if 'class="ui2-m-l1"' in c)
    assert 'data-ui2-l1="onebrain"' in chunks[i_l1 + 1]
    assert 'data-ui2-l1="primary_chart"' in chunks[i_l1 + 2]
    assert 'class="ui2-grid"' in chunks[i_l1 + 3]
    # 與空槽版逐塊相同（只差 Primary 那一塊）
    slot_vm = dataclasses.replace(vm, context=dataclasses.replace(vm.context, kbar=None))
    slot_chunks = _render(slot_vm, monkeypatch)
    assert [c for i, c in enumerate(chunks) if i != i_l1 + 2] == [c for i, c in enumerate(slot_chunks) if i != i_l1 + 2]


def test_real_app_renders_the_chart_and_default_lane_does_not(monkeypatch):
    from tests.test_ui2_real_feed import _at, _blob
    at = _at()
    assert 'data-ui2-l1="primary_slot"' in _blob(at) and 'data-ui2-l1="primary_chart"' not in _blob(at)
    at = _at(dev=True)
    at.selectbox(key="ui2_feed").set_value("real").run(timeout=60)
    blob = _blob(at)
    assert not at.exception
    assert 'data-ui2-l1="primary_chart"' in blob and 'data-ui2-l1="primary_slot"' not in blob
    assert "FAKE" not in blob


# ══════════════════════════════════════════════════════════════════ §7 viewport 判定器
def _p2(**chart) -> dict:
    p2 = {"onebrain": {"top": 570.0, "bottom": 620.0}, "slot": None, "grid": {"top": 900.0, "bottom": 1000.0},
          "slot_graphics": 0, "slot_text": None, "spec_text": None, "slot_danger": 0,
          "chart": {"top": 630.0, "bottom": 890.0}, "chart_state": "ok", "chart_bars": 20, "chart_graphics": 2,
          "chart_svg_h": 220.0, "chart_legend": LEGEND, "chart_text": "🇹🇼 台股趨勢 " + LEGEND, "chart_danger": 0}
    p2.update(chart)
    return p2


def _eval(p2) -> dict[str, list[str]]:
    m = {"page": "p4_market", "scenario": "real", "viewport": {"w": 390, "h": 844}, "nav": {"top": 791.0},
         "first_block_after_l1_top": 560.0, "risk": {"top": 500.0, "bottom": 560.0},
         "elements": [{"q": "q2", "bottom": 300.0}, {"q": "q3", "bottom": 340.0}], "p2": p2}
    out = {t["id"]: [] for t in MV.THRESHOLDS}
    MV._evaluate_p2(m, out)
    return out


def test_viewport_kbar_check_passes_good_and_registered():
    out = _eval(_p2())
    assert out["kbar_primary_chart"] == [] and out["p2_onebrain_primary_slot_order"] == []
    t = next(x for x in MV.THRESHOLDS if x["id"] == "kbar_primary_chart")
    assert "DEC-156" in t["source"]
    for st_ in ("unavailable",):
        assert _eval(_p2(chart_state=st_, chart_bars=0, chart_graphics=0, chart_danger=1))["kbar_primary_chart"] == []


@pytest.mark.parametrize("mut", [
    dict(slot={"top": 630.0, "bottom": 700.0}),                       # 空槽與主圖並存
    dict(chart_bars=0), dict(chart_bars=21),
    dict(chart_svg_h=140.0), dict(chart_svg_h=300.0), dict(chart_svg_h=None),
    dict(chart_legend="紅漲綠跌"), dict(chart_text="🇹🇼 台股趨勢 MA20"), dict(chart_text="成交量"),
    dict(chart_danger=1),
    dict(chart_state="undeterminable", chart_bars=3, chart_graphics=2),
    dict(chart_state="missing", chart_bars=0, chart_graphics=0, chart_danger=1),
])
def test_viewport_kbar_check_has_teeth(mut):
    assert _eval(_p2(**mut))["kbar_primary_chart"] != [], mut


def test_viewport_order_check_still_applies_to_the_chart():
    out = _eval(_p2(grid={"top": 700.0, "bottom": 800.0}))           # 指標卡跑到主圖之前
    assert out["p2_onebrain_primary_slot_order"] != []
    out = _eval(_p2(chart=None))                                      # 主圖與空槽都沒有
    assert out["p2_onebrain_primary_slot_order"] != []


def test_evidence_git_head_reads_worktree_layout(tmp_path):
    """量測工具在 git worktree（`.git` 是 `gitdir:` 檔）也讀得到 HEAD sha（否則證據 meta git_sha＝None → DEC-137 判紅）。"""
    common = tmp_path / "main.git"
    wt_git = common / "worktrees" / "wt"
    (common / "refs" / "heads" / "feat").mkdir(parents=True)
    wt_git.mkdir(parents=True)
    (common / "refs" / "heads" / "feat" / "x").write_text("a" * 40 + "\n", encoding="utf-8")
    (wt_git / "HEAD").write_text("ref: refs/heads/feat/x\n", encoding="utf-8")
    (wt_git / "commondir").write_text("../..\n", encoding="utf-8")
    repo = tmp_path / "wt"
    repo.mkdir()
    (repo / ".git").write_text(f"gitdir: {wt_git}\n", encoding="utf-8")
    assert MV._git_head(repo) == "a" * 40
    # packed-refs 也找得到；一般 clone（.git 目錄）行為不變
    (common / "refs" / "heads" / "feat" / "x").unlink()
    (common / "packed-refs").write_text("# pack-refs\n" + "b" * 40 + " refs/heads/feat/x\n", encoding="utf-8")
    assert MV._git_head(repo) == "b" * 40
    plain = tmp_path / "plain"
    (plain / ".git").mkdir(parents=True)
    (plain / ".git" / "HEAD").write_text("c" * 40 + "\n", encoding="utf-8")
    assert MV._git_head(plain) == "c" * 40
    assert MV._git_head(tmp_path / "nothing") is None


# ══════════════════════════════════════════════════════════════════ §8 G2F 白名單只多 1 個名稱（Issue #1099 PR-2）
#: 本 PR 之前 `real_canonical` 的 G2F 精確白名單（main e5a429c）；本 PR 只准多 `twii_kbar_fact_of` 一個名稱。
_G2F_RC_BEFORE = frozenset({"ERROR_CODE_RE", "RealFeedSnapshot", "RegimeFact", "TwiiFact", "exception_code",
                            "validate_regime_fact", "validate_twii_fact"})


def test_g2f_allowlist_gained_exactly_one_pure_name():
    from tests import test_ui2_guards as G
    rc = G.G2F_IMPORT_ALLOWLIST["src.services.ui2.real_canonical"]
    assert rc == _G2F_RC_BEFORE | {"twii_kbar_fact_of"}
    assert set(G.G2F_IMPORT_ALLOWLIST) == {"__future__", "src.services.market_twii_view_service",
                                           "src.services.allocation_service", "src.services.ui2.real_canonical"}
    assert G.G2F_IMPORT_ALLOWLIST["src.services.market_twii_view_service"] == frozenset({"get_twii_trend_view"})
    assert "open" in G._G2F_BANNED_NAMES                                      # `.open` 禁令未放寬
    assert callable(RC.twii_kbar_fact_of) and not hasattr(RealFeedSnapshot, "kbar_fact_of")


@pytest.mark.parametrize("name", ["TwiiKbarFact", "validate_twii_kbar_fact", "kbar_chart_spec",
                                  "kbar_same_source_problem", "KBAR_VISIBLE_BARS", "real_canonical"])
def test_g2f_still_rejects_any_other_new_name_from_real_canonical(name):
    from tests import test_ui2_guards as G
    clean = (G.FEED_FILES[0]).read_text(encoding="utf-8")
    assert G.check_feed_boundary(clean) == []
    assert G.check_feed_boundary(f"from src.services.ui2.real_canonical import {name}\n" + clean)


def test_g2f_still_rejects_open_attribute_in_the_feed():
    from tests import test_ui2_guards as G
    clean = (G.FEED_FILES[0]).read_text(encoding="utf-8")
    assert G.check_feed_boundary("o = v.open\n" + clean)
