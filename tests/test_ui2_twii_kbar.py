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
import datetime as _dt
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
PICKER_MARK = "<!--kbar-period-picker-->"


# ── fixtures ─────────────────────────────────────────────────────────────
def _dates(n: int) -> tuple[str, ...]:
    """n 個嚴格升序的 ISO 日期（自 2026-10-01 起每日一個；n ≤ 31 與舊版逐字相同，n > 31 才跨月——60 根測試用）。"""
    return tuple((_dt.date(2026, 10, 1) + _dt.timedelta(days=i)).isoformat() for i in range(n))


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


def _feed(monkeypatch, *, card=None, kbar=None, card_exc=None, kbar_exc=None, calls=None, days=None) -> RealFeedSnapshot:
    """經**真 feed** 跑：只把 canonical service 換成注入版本（支援 `with_ohlc` 關鍵字）。
    `days=None`＝既有無參呼叫（預設路徑，必須與期間切換之前逐值相同）；給值＝經核准的所選期間。"""
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
    return RF.read_real_snapshot() if days is None else RF.read_real_snapshot(days=days)


def _chart(snap) -> KbarChartVM:
    k = get_real_page_vm(P4_MARKET, snap).context.kbar
    assert k is not None
    return k


def _card_field(snap) -> FieldVM:
    return get_real_page_vm(P4_MARKET, snap).context.cards[0].field


def _render(vm, monkeypatch, events: list[str] | None = None) -> list[str]:
    """渲染 market 頁並收集 `_md` 區塊。期間 radio（原生 st widget，不經 `_md`）在這裡換成記號：
    預設不記錄（既有逐塊斷言不受影響）；給 `events` 時，`_md` 區塊與 radio 位置依實際呼叫順序一起記進去。"""
    out: list[str] = []

    def md(x):
        out.append(x)
        if events is not None:
            events.append(x)
    monkeypatch.setattr(market, "_md", md)
    monkeypatch.setattr(_page, "_md", md)
    monkeypatch.setattr(market, "_kbar_period_picker", lambda: events.append(PICKER_MARK) if events is not None else None)
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
    # B-UI2-STALE-COPY-1（DEC-214）：L1 `stale_reason` 不上畫面（卡片與日 K 同規則）；天數由 chip 呈現。
    assert chart.field.detail == card.detail is None
    assert "已 4 天沒有新資料" not in (chart.field.detail or "") + (card.detail or "")


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
    # Issue #1108 方向 B：L1 → 日 K 主圖 →（B-UI2-DELTA-BELOW）今日變化 → 指標卡 → OneBrain
    assert 'data-ui2-l1="primary_chart"' in chunks[i_l1 + 1]
    assert 'data-ui2-delta="1"' in chunks[i_l1 + 2]
    assert 'class="ui2-grid"' in chunks[i_l1 + 3]
    assert 'data-ui2-l1="onebrain"' in chunks[i_l1 + 4]
    # 與空槽版逐塊相同（只差 Primary 那一塊）
    slot_vm = dataclasses.replace(vm, context=dataclasses.replace(vm.context, kbar=None))
    slot_chunks = _render(slot_vm, monkeypatch)
    assert [c for i, c in enumerate(chunks) if i != i_l1 + 1] == [c for i, c in enumerate(slot_chunks) if i != i_l1 + 1]


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
    p2 = {"onebrain": {"top": 1010.0, "bottom": 1060.0}, "slot": None, "grid": {"top": 900.0, "bottom": 1000.0},
          "slot_graphics": 0, "slot_text": None, "spec_text": None, "slot_danger": 0,
          "chart": {"top": 630.0, "bottom": 890.0}, "chart_state": "ok", "chart_bars": 20, "chart_graphics": 2,
          "chart_svg_h": 220.0, "chart_legend": LEGEND, "chart_text": "🇹🇼 台股趨勢 " + LEGEND, "chart_danger": 0,
          # 期間 radio（圖之後、指標卡之前；預設選中 20）
          "kbar_picker": {"top": 892.0, "bottom": 898.0}, "kbar_picker_title": "期間",
          "kbar_picker_labels": ["20 日", "60 日"], "kbar_picker_checked": 1, "chart_period": 20}
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


@pytest.mark.parametrize("period,bars", [(20, 20), (20, 1), (60, 60), (60, 20), (None, 20)])
def test_viewport_kbar_check_accepts_each_approved_period_up_to_its_own_cap(period, bars):
    assert _eval(_p2(chart_period=period, chart_bars=bars))["kbar_primary_chart"] == []


@pytest.mark.parametrize("mut", [
    dict(chart_period=20, chart_bars=21),                            # 預設窗正負控：仍 20 為上限
    dict(chart_period=None, chart_bars=21),                          # 量不到選中值＝當預設 20（fail closed）
    dict(chart_period=60, chart_bars=61),
    dict(chart_period=20, chart_bars=60), dict(chart_period=60, chart_bars=120),   # 不得拿較寬的窗當上限
    dict(chart_period=120, chart_bars=1), dict(chart_period=120, chart_bars=61), dict(chart_period=120, chart_bars=120),  # R20：120 另案，選中 120＝未核准
    dict(chart_period=252, chart_bars=100), dict(chart_period=252, chart_bars=20),  # 未核准期間
    dict(chart_period=True, chart_bars=1), dict(chart_period=0, chart_bars=1), dict(chart_period="60", chart_bars=60),
    dict(kbar_picker=None),                                          # Real 日 K 圖卻沒有 radio
    dict(kbar_picker_labels=["20 日", "60 日", "120 日"]),           # R20：不得再出現 120 日選項（加回 120＝紅）
    dict(kbar_picker_labels=["20 日", "60 日", "252 日"]), dict(kbar_picker_labels=["20 日"]),
    dict(kbar_picker_labels=["60 日", "20 日"]), dict(kbar_picker_labels=["20", "60"]),
    dict(kbar_picker_title="區間"), dict(kbar_picker_title=None),
    dict(kbar_picker_checked=0), dict(kbar_picker_checked=2),
    dict(kbar_picker={"top": 600.0, "bottom": 620.0}),               # radio 跑到圖之前
    dict(kbar_picker={"top": 895.0, "bottom": 1100.0}),              # radio 壓到指標卡
])
def test_viewport_kbar_picker_and_period_checks_have_teeth(mut):
    assert _eval(_p2(**mut))["kbar_primary_chart"] != [], mut


def test_viewport_picker_must_not_exist_without_a_chart():
    """FAKE／誠實空槽（沒有日 K 圖）卻有期間 radio → 紅；沒有 radio 的 FAKE 空槽照舊過。"""
    slot = dict(chart=None, chart_state=None, chart_bars=0, chart_graphics=0, chart_svg_h=None, chart_legend=None,
                chart_text=None, slot={"top": 630.0, "bottom": 700.0}, slot_text="🇹🇼 台股趨勢 ⬜ 尚未提供",
                spec_text="SPEC｜最新收盤參考｜來源｜資料日 2026-10-20｜缺值不補", grid={"top": 900.0, "bottom": 1000.0})
    no_picker = dict(slot, kbar_picker=None, kbar_picker_title=None, kbar_picker_labels=[], kbar_picker_checked=0, chart_period=None)
    assert _eval(_p2(**no_picker))["kbar_primary_chart"] == []
    assert _eval(_p2(**slot))["kbar_primary_chart"] != []        # _p2 預設帶 radio → 紅


def test_real_measurement_actually_clicks_60_and_records_it_in_the_market_row():
    """R20：量測器在真瀏覽器實際點選 60 日（結果掛在既有市場列 `kbar_period60`，⛔ 新增量測列〔`states` 數量由 test_ui2_batch2 以公式釘住〕），
    失敗會讓該列 pass=False；判定常數只有 20／60。（真瀏覽器執行見 ui2 browser lane；這裡釘結構。）"""
    import inspect
    run_src = inspect.getsource(MV._run_real)
    assert "measure_kbar_period_60(page, vw, vh, streamlit_version)" in run_src and 'results[-1]["kbar_period60"]' in run_src
    i = run_src.index("measure_kbar_period_60(page, vw, vh, streamlit_version)")
    assert 'results[-1]["pass"] = False' in run_src[i:run_src.index("_record_stress", i)]
    fn_src = inspect.getsource(MV.measure_kbar_period_60)
    for need in ("lab(60).click()", "ArrowRight", "lab(20).click()", "20 < bars <= 60", "doc_scroll_w"):
        assert need in fn_src, need
    assert MV.KBAR_PERIOD_CAPS == {20: 20, 60: 60} and MV.KBAR_PICKER_LABELS == ["20 日", "60 日"] and 120 not in MV.KBAR_PERIOD_CAPS


# ── MF1：方向鍵不離頁（客戶方案 B：#1199 7192913294／7193549716／AUTH-B-r01；僅 1.56.0 認列已知平台限制；R23.8 最嚴解讀）────────────────
def _arrow_cases(*, leak: bool = False, **over) -> list[dict]:
    """20／60 × 四個方向鍵的合成量測案例。`leak=True`＝模擬 1.56.0 的洩漏（頁面→資料、焦點離開、期間 radio 消失）。"""
    out = []
    for start in MV.ARROW_STARTS:
        for key in MV.ARROW_KEYS:
            c = {"start": start, "key": key, "nav_before": "📊 市場", "nav_after": "📊 市場", "market_after": True,
                 "picker_present": True, "focus_in_picker": True, "focus_in_nav": False, "active_label": "期間",
                 "picker_after": 60 if start == 20 else 20}
            if leak:
                c.update(nav_after="🗂 資料", market_after=False, picker_present=False, focus_in_picker=False,
                         focus_in_nav=True, active_label="🗂 資料", picker_after=None)
            out.append(c)
    out[0].update(over)
    return out


_NAMES_156 = {"nav": ["", "", "", "", ""], "picker": ["", ""]}


def _ak(version: str, cases: list[dict], leak: dict | None = None) -> dict:
    ak = {"streamlit_version": version, "policy": MV.arrow_policy(version), "cases": cases}
    if leak is not None:
        ak["arrow_leak"] = leak
    return ak


def _leak_rec(cases: list[dict], **over) -> dict:
    rec = {"observed": any(MV.arrow_case_leaked(c) for c in cases), "left_from_20": "導覽→🗂 資料", "right_from_60": "焦點→導覽",
           "up_from_20": "導覽→🗂 資料", "down_from_60": "焦點→導覽", "input_names": _NAMES_156, "cause": MV.ARROW_LEAK_CAUSE}
    rec.update(over)
    return rec


@pytest.mark.parametrize("version,policy", [
    ("1.59.2", "required"), ("1.59.0", "required"), ("1.59.1", "required"),
    ("1.56.0", "known_limitation"),                                              # 僅 1.56.0 精確
    # R23.8 最嚴：其餘一律 unsupported（未核准／未量測）
    ("1.55.0", "unsupported"), ("1.55.9", "unsupported"), ("1.56.1", "unsupported"), ("1.56.2", "unsupported"), ("1.56.9", "unsupported"),
    ("1.57.0", "unsupported"), ("1.57.3", "unsupported"), ("1.58.0", "unsupported"), ("1.58.1", "unsupported"),
    ("1.60.0", "unsupported"), ("1.60.1", "unsupported"), ("2.0.0", "unsupported"),
    ("1.59", "unsupported"), ("1.56", "unsupported"), ("1.5", "unsupported"), ("1.59.2.dev0", "unsupported"), ("1.56.0rc1", "unsupported"),
    ("", "unsupported"), (None, "unsupported"), ("garbage", "unsupported"), ("v1.59.2", "unsupported"), (1.59, "unsupported"),
])
def test_arrow_policy_is_split_by_the_actually_loaded_streamlit_version(version, policy):
    assert MV.arrow_policy(version) == policy


def test_arrow_required_policy_passes_the_good_record():
    assert MV.evaluate_arrow_keys(_ak("1.59.2", _arrow_cases())) == []


@pytest.mark.parametrize("over", [
    dict(nav_after="🗂 資料", market_after=False),                      # 離開市場頁
    dict(market_after=False),
    dict(nav_after="🎯 標的"),                                           # 導覽選中項改變（即使 market_after 仍 True）
    dict(picker_present=False),                                        # 期間 radio 消失
    dict(focus_in_picker=False, focus_in_nav=True),                    # 焦點離開期間 radiogroup（1.56 的 ArrowRight-from-60 型態）
    dict(picker_after=None), dict(picker_after=120), dict(picker_after=252),      # 值不在 20↔60 環繞
    dict(picker_after=20),                                             # 從 20 按鍵後沒動（預期環繞到 60）
])
def test_arrow_required_policy_goes_red_on_any_leak_or_wrong_value_a(over):
    """(a) ≥1.59：模擬離頁／焦點離開／導覽選中項改變／值錯 → 必紅。"""
    assert MV.evaluate_arrow_keys(_ak("1.59.2", _arrow_cases(**over))) != [], over
    assert MV.evaluate_arrow_keys(_ak("1.59.0", _arrow_cases(**over))) != [], over


def test_arrow_required_policy_all_leaking_is_red_and_cannot_be_excused_by_a_leak_record():
    cases = _arrow_cases(leak=True)
    assert MV.evaluate_arrow_keys(_ak("1.59.2", cases)) != []
    assert MV.evaluate_arrow_keys(_ak("1.59.2", cases, _leak_rec(cases))) != []      # 1.59 不得靠附上 arrow_leak 過關


@pytest.mark.parametrize("bad_cases", [
    None, [], "x", _arrow_cases()[:-1], _arrow_cases() + _arrow_cases()[:1], list(reversed(_arrow_cases())),
])
def test_arrow_record_must_contain_exactly_the_eight_cases(bad_cases):
    for v in ("1.59.2", "1.56.0"):
        assert MV.evaluate_arrow_keys({"streamlit_version": v, "cases": bad_cases, "arrow_leak": _leak_rec(_arrow_cases(leak=True))}) != []


def test_arrow_missing_record_is_red_never_silently_skipped():
    for v in ("1.59.2", "1.56.0"):
        assert MV.evaluate_arrow_keys(None) != [] and MV.evaluate_arrow_keys({}) != []


def test_arrow_known_limitation_leak_is_recorded_and_does_not_fail_b():
    """(b) 1.56：模擬洩漏 → 不紅；known_limitation 欄位必存在且 observed=True。"""
    cases = _arrow_cases(leak=True)
    leak = _leak_rec(cases)
    assert leak["observed"] is True
    assert MV.evaluate_arrow_keys(_ak("1.56.0", cases, leak)) == []
    for v in ("1.56.1", "1.56.2", "1.57.0", "1.58.1"):                       # R23.8：1.56.0 以外一律不放寬（即使附完整記錄也紅）
        assert MV.evaluate_arrow_keys(_ak(v, cases, leak)) != [], v


def test_arrow_known_limitation_honestly_records_no_leak_when_there_is_none():
    cases = _arrow_cases()
    leak = _leak_rec(cases)
    assert leak["observed"] is False
    assert MV.evaluate_arrow_keys(_ak("1.56.0", cases, leak)) == []
    assert MV.evaluate_arrow_keys(_ak("1.56.0", cases, _leak_rec(cases, observed=True))) != []       # 沒洩漏卻宣稱洩漏＝假記錄


def test_arrow_known_limitation_without_the_record_is_red_c():
    """(c) 1.56 缺 known_limitation 欄位 → 必紅（防止靜默略過）；欄位不全／與實測不符亦紅。"""
    cases = _arrow_cases(leak=True)
    assert MV.evaluate_arrow_keys(_ak("1.56.0", cases)) != []
    assert MV.evaluate_arrow_keys(_ak("1.56.0", cases, None)) != []
    assert MV.evaluate_arrow_keys({"streamlit_version": "1.56.0", "cases": cases, "arrow_leak": "洩漏"}) != []
    for k in ("observed", "left_from_20", "right_from_60", "input_names", "cause"):
        rec = _leak_rec(cases)
        del rec[k]
        assert MV.evaluate_arrow_keys(_ak("1.56.0", cases, rec)) != [], k
    for over in (dict(observed=False), dict(observed="yes"), dict(input_names={}), dict(input_names={"nav": [], "picker": []}),
                 dict(input_names={"nav": [""], "picker": []}), dict(cause=""), dict(cause=None)):
        assert MV.evaluate_arrow_keys(_ak("1.56.0", cases, _leak_rec(cases, **over))) != [], over


_UNAPPROVED_VERSIONS = ["1.55.0", "1.56.1", "1.56.2", "1.57.0", "1.58.1", "1.60.0", "1.61.2", "2.0.0", "garbage", "", None]


@pytest.mark.parametrize("version", _UNAPPROVED_VERSIONS, ids=repr)
def test_arrow_unapproved_versions_are_red_d(version):
    """(d) 未核准版本負控表（R23.8；僅 1.56.0 為已知限制、≥1.59.0 且 <1.60 為必過）：<1.56、1.56.1 以上、1.57.x、1.58.x、≥1.60、無法解析、None
    一律 `arrow_policy`＝unsupported 並被判失敗，即使案例完美、附有 leak 記錄；失敗訊息明講「未獲核准／未量測」（不是靜默略過）。"""
    assert MV.arrow_policy(version) == "unsupported"
    good, leaky = _arrow_cases(), _arrow_cases(leak=True)
    for cases, leak in ((good, None), (good, _leak_rec(good)), (leaky, _leak_rec(leaky)), (leaky, None)):
        rec = {"streamlit_version": version, "cases": cases}
        if leak is not None:
            rec["arrow_leak"] = leak
        fails = MV.evaluate_arrow_keys(rec)
        assert fails and "未獲核准／未量測" in fails[0], (version, fails)


@pytest.mark.parametrize("version", _UNAPPROVED_VERSIONS, ids=repr)
def test_arrow_unapproved_version_makes_the_market_row_fail_when_judged_d2(version):
    """量測列層級：`measure_kbar_period_60` 的失敗清單來自 `evaluate_arrow_keys`（不允許放寬），未核准版本 → failures 非空 → 該列 pass=False。"""
    fails = [f"[arrow_keys] {x}" for x in MV.evaluate_arrow_keys({"streamlit_version": version, "cases": _arrow_cases(),
                                                                  "arrow_leak": _leak_rec(_arrow_cases())})]
    assert fails and any("未獲核准／未量測" in f for f in fails)


def test_arrow_only_exact_1_56_0_is_a_known_limitation_and_1_59_x_is_strict():
    leaky = _arrow_cases(leak=True)
    assert MV.arrow_policy("1.56.0") == "known_limitation"
    assert MV.evaluate_arrow_keys(_ak("1.56.0", leaky)) != []                                    # 缺記錄＝紅
    assert MV.evaluate_arrow_keys(_ak("1.56.0", leaky, _leak_rec(leaky))) == []                 # 如實記錄＝不判失敗
    for v in ("1.59.0", "1.59.1", "1.59.2"):
        assert MV.arrow_policy(v) == "required"
        assert MV.evaluate_arrow_keys(_ak(v, _arrow_cases())) == []
        assert MV.evaluate_arrow_keys(_ak(v, leaky)) != []                                       # 離頁＝紅
        assert MV.evaluate_arrow_keys(_ak(v, leaky, _leak_rec(leaky))) != []                     # 附記錄也不能過關


def test_arrow_measurement_is_wired_into_the_real_market_row_and_uses_the_loaded_version():
    import inspect
    k60 = inspect.getsource(MV.measure_kbar_period_60)
    assert "measure_arrow_keys(page, streamlit_version, lab, cond)" in k60 and "evaluate_arrow_keys(ak)" in k60
    assert '"arrow_keys": ak' in k60                                        # 記錄進 JSON
    run_src = inspect.getsource(MV._run_real)
    assert run_src.index("_streamlit_version(server_python)") < run_src.index("for vp_name, (vw, vh) in VIEWPORTS.items()")
    fn = inspect.getsource(MV.measure_arrow_keys)
    for key in MV.ARROW_KEYS:
        assert key in inspect.getsource(MV) and MV.ARROW_KEYS.count(key) == 1
    assert "arrow_policy(streamlit_version)" in fn and '"arrow_leak"' in fn and "input_names" in fn
    assert 'if ak["policy"] == "known_limitation":' in fn and 'ak["arrow_leak"] = {' in fn      # 1.56 一定產出記錄（拔掉＝缺記錄＝紅）
    assert MV.ARROW_STARTS == (20, 60) and MV.ARROW_KEYS == ("ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown")


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


# ══════════════════════════════════════════════════════════════════ §9 期間切換（20／60 日）
# 授權：#1199 留言 7186846291（施工包）＋7191058929（客戶 R20 具名授權，取代 7186895108 的選項集：全裝置 20／60 日、預設 20、
# 120 日另案；修正包 7190796719 方案 A）。120／252／縮放／捲動／降採樣皆未核准。以下全是離線測試（注入 service／真 git 追蹤 parquet；不連網）。
import hashlib as _hashlib

DAY_OPTIONS = (20, 60)
APPROVED_LABELS = ["20 日", "60 日"]
KEY_DAYS = "ui2_kbar_days"
#: 期間切換之前（main 0ceeb97）的預設路徑基準：以同一組注入 fixture 量到的 sha256（逐位元組）。
_BASE_HTML_SHA = {
    "ok20": "d11a7772673c5820e27190d5a08fd6c4a13dbeebc10bf74194e1d914d0309605",
    "partial7": "9326f732d1fc0970698c908a606828fc18d13a3bdbcf2b85d09062aee986f411",
    "stale": "e3a269b4e9e6266392c6ceef9a032bcde8ef0b477feee347fb5f1400d71a61ba",
}
_BASE_VM_SHA = {
    "p4_market": "9fd1b135597c7f2cc7b5e4ae499992a911bfdf50eebb93f846a258204f5b9986",
    "p4_target": "047664aad9a6d2ca314f2b0e5ffc10bd775ca4272a02ddae2f465b0519ea198f",
    "p4_hold": "187b6de4c3102974fdab82ddedc3ed4d1b3230fd0cf811f43a47c29449789e78",
    "p4_me": "f906e7446ee8eb6cfafcda09ffa79b527f44c2b0ad82d08ffe4407de94ee75cb",
    "p4_data": "a2adcd28c1dbbd4d9d445d673f602424b0d2047b1123ebc1c9295ae0f413f7d5",
}
#: 不得被接受的「期間」（含 bool、未核准的 252、非 int 型別、邊界值）。選擇：**fail closed＝明示錯誤（ValueError），
#: 且在觸及快取讀取（`get_twii_trend_view`）之前**；殼（shell）則把殘留的非法 session 值收斂回預設 20。
_BAD_DAYS = [120, 119, 121, True, False, 252, 0, -20, 19, 21, 59, 61, 120.0, 20.0, 60.0, "20", "60", "120", "60 日", None, (20,), [20], 2**40]


def _sha(text: str) -> str:
    return _hashlib.sha256(text.encode()).hexdigest()


def _option_tables_pinned() -> bool:
    return RF.TWII_KBAR_DAY_OPTIONS == RC.KBAR_DAY_OPTIONS == market.KBAR_DAY_OPTIONS == DAY_OPTIONS == (20, 60)


def test_120_is_not_offered_or_accepted_anywhere_r20():
    """R20（#1199 7191058929）：120 日另案——三份選項表、canonical 判斷、feed 讀取守衛、標籤全無 120。"""
    for t in (RF.TWII_KBAR_DAY_OPTIONS, RC.KBAR_DAY_OPTIONS, market.KBAR_DAY_OPTIONS):
        assert 120 not in t and t == (20, 60)
    assert not RC.kbar_days_ok(120) and RC.kbar_days_ok(20) and RC.kbar_days_ok(60)
    with pytest.raises(ValueError):
        RF.read_real_snapshot(days=120)
    assert [market.kbar_days_label(n) for n in market.KBAR_DAY_OPTIONS] == ["20 日", "60 日"]


def test_adding_120_back_to_the_option_tables_is_caught(monkeypatch):
    """突變：任一份選項表加回 120 → 釘相等轉紅（上面的 `_option_tables_pinned()` 與 120 被拒測試因此會紅）。"""
    assert _option_tables_pinned()
    for mod, attr in ((RF, "TWII_KBAR_DAY_OPTIONS"), (RC, "KBAR_DAY_OPTIONS"), (market, "KBAR_DAY_OPTIONS")):
        with monkeypatch.context() as mp:
            mp.setattr(mod, attr, (20, 60, 120))
            assert not _option_tables_pinned(), attr
    with monkeypatch.context() as mp:                                     # 三份一起加回：120 變成「被接受」＝被拒測試會紅
        for mod, attr in ((RF, "TWII_KBAR_DAY_OPTIONS"), (RC, "KBAR_DAY_OPTIONS"), (market, "KBAR_DAY_OPTIONS")):
            mp.setattr(mod, attr, (20, 60, 120))
        assert RC.kbar_days_ok(120) and not _option_tables_pinned()


def test_option_table_and_keys_are_pinned_across_feed_canonical_view_and_shell():
    from src.ui2.shell import app as shell
    assert _option_tables_pinned()
    assert RF.TWII_KBAR_DAY_OPTIONS == RC.KBAR_DAY_OPTIONS == market.KBAR_DAY_OPTIONS == DAY_OPTIONS
    assert RF.TWII_KBAR_DAYS == RC.KBAR_VISIBLE_BARS == market.KBAR_DAYS_DEFAULT == DAY_OPTIONS[0] == 20
    assert market.KEY_KBAR_DAYS == shell.KEY_KBAR_DAYS == KEY_DAYS
    assert market.KEY_KBAR_DAYS_BOX == "ui2_kbar_days_box"
    assert market.KBAR_DAYS_LABEL == "期間"
    assert [market.kbar_days_label(n) for n in DAY_OPTIONS] == APPROVED_LABELS
    assert not {120, 252, 5, 10, 30, 90}.intersection(DAY_OPTIONS)


def test_default_path_is_byte_identical_to_the_pre_change_baseline(monkeypatch):
    """預設（20）時圖的 HTML 與 5 頁 VM 與期間切換之前逐位元組同基準；明示傳 20 與不傳完全相同。"""
    for name, kw in {"ok20": {}, "partial7": {"kbar": _kbar_view(7)},
                     "stale": {"kbar": _kbar_view(is_stale=True, age_days=4, stale_reason="x")}}.items():
        a = _feed(monkeypatch, **kw)
        b = _feed(monkeypatch, days=20, **kw)
        assert a == b and a.kbar_days == 20
        html = H.kbar_chart_html(get_real_page_vm(P4_MARKET, a).context.kbar)
        assert _sha(html) == _BASE_HTML_SHA[name], name
        assert html == H.kbar_chart_html(get_real_page_vm(P4_MARKET, b).context.kbar)
    snap = _feed(monkeypatch)
    assert {p: _sha(repr(get_real_page_vm(p, snap))) for p in PAGE_IDS} == _BASE_VM_SHA


@pytest.mark.parametrize("days", [60])
def test_selected_window_card_stays_one_day_and_kbar_reads_the_selected_days_once(monkeypatch, days):
    calls: list = []
    kv = _kbar_view(days)
    snap = _feed(monkeypatch, kbar=kv, calls=calls, days=days)
    assert calls == [(1, {}), (days, {"with_ohlc": True})]                    # 卡片仍 1 日；日 K 只一次、所選窗
    assert snap.kbar_days == days and snap.kbar is not None and len(snap.kbar.xs) == days
    chart = _chart(snap)
    assert chart.field.state is FieldState.OK and len(chart.candles) == days
    assert chart.target_n == days and chart.notes == ()
    assert [c.date for c in chart.candles] == list(kv.xs)
    assert [(c.open, c.high, c.low, c.close) for c in chart.candles] == list(zip(kv.open, kv.high, kv.low, kv.close))
    assert chart.field.value_text == _card_field(snap).value_text == f"{kv.close[-1]:,.2f}"      # 與收盤卡同源同值
    assert RC.kbar_same_source_problem(snap.kbar, snap.twii) == ""
    html = H.kbar_chart_html(chart)
    assert len(re.findall(r"data-kbar-dir=", html)) == days
    assert f"共 {days} 根" in html                                                       # aria-label
    assert kv.xs[0] in _visible(html) and kv.xs[-1] in _visible(html)               # 起訖日期


@pytest.mark.parametrize("days", [60])
def test_selected_window_html_has_no_controls_volume_ma_or_fake(monkeypatch, days):
    html = H.kbar_chart_html(_chart(_feed(monkeypatch, kbar=_kbar_view(days), days=days)))
    low = html.lower()
    for tag in ("<button", "<input", "<select", "<a ", "onclick", "<script", "<canvas", "<img"):
        assert tag not in low, tag
    vis = _visible(html)
    for w in ("MA", "均線", "成交量", "volume", "量能", "買", "賣", "訊號", "FAKE", "示意"):
        assert w not in vis, w
    assert hits_in(vis) == []
    assert re.findall(r'<svg class="ui2-kbar__svg" width="100%" height="(\d+)"', html) == ["220"]   # 圖高不變（不縮放）


@pytest.mark.parametrize("days,n", [(60, 45), (60, 1), (60, 59)])
def test_fewer_bars_than_the_selected_window_are_drawn_as_is_with_the_honest_note(monkeypatch, days, n):
    chart = _chart(_feed(monkeypatch, kbar=_kbar_view(n), days=days))
    assert len(chart.candles) == n and chart.target_n == days                  # ⛔ 補棒
    assert chart.notes == (f"僅 {n} 根（不足 {days}）",)
    assert f"僅 {n} 根（不足 {days}）" in _visible(H.kbar_chart_html(chart))


def test_selected_window_is_the_upper_bound_of_the_bar_count(monkeypatch):
    """所選窗＝根數上限：60 窗收到 61 根、20 窗收到 60 根（反過來也不行）都是契約違反（紅），卡片照常。"""
    good = _kbar_view(20)
    for days, view in ((60, _kbar_view(61)), (20, _kbar_view(60))):
        snap = _feed(monkeypatch, kbar=view, card=_matching_card(good), days=days)
        assert snap.kbar is None and snap.kbar_error == RC.CONTRACT_ERROR, days
        assert _chart(snap).field.state is FieldState.UNAVAILABLE
        assert _card_field(snap).state is FieldState.OK
    with pytest.raises(RC.RealFeedContractError):
        RC.twii_kbar_fact_of(_kbar_view(61), days=60)
    with pytest.raises(RC.RealFeedContractError):
        RC.twii_kbar_fact_of(_kbar_view(21))                                       # 預設窗：行為不變
    RC.twii_kbar_fact_of(_kbar_view(60), days=60)
    RC.twii_kbar_fact_of(_kbar_view(21), days=60)                                  # 21 ≤ 60：合法（只是不足 60）


@pytest.mark.parametrize("days", [60])
@pytest.mark.parametrize("name", [n for n in _VIOLATIONS if n != "too_many_bars"])
def test_every_contract_violation_is_still_red_at_the_selected_window(monkeypatch, days, name):
    """同一組契約違反（長度／日期／OHLC／as_of…）在 60 窗同樣把日 K 變紅、卡片照常。"""
    base = _kbar_view(days)
    spec = _VIOLATIONS[name]
    if name in ("is_stale_not_bool", "bad_upstream_state"):
        view = dataclasses.replace(base, **{"is_stale": 1} if name == "is_stale_not_bool" else {"upstream_state": "WHATEVER"})
    else:
        spec = {k: v for k, v in spec.items()}
        # 長度類違反以所選窗的根數重建；其餘照原值（欄位位置 < 20 在 60 窗內同樣存在）
        if name == "zero_bars_but_ok":
            view = _kbar_view(days, **spec)
        else:
            view = _kbar_view(days, **{k: (v if not isinstance(v, tuple) or len(v) != 20 else v + base.__dict__[k][20:])
                                       for k, v in spec.items()})
    snap = _feed(monkeypatch, kbar=view, card=_matching_card(base), days=days)
    assert snap.kbar is None and snap.kbar_error, (days, name)
    chart = _chart(snap)
    assert chart.field.state is FieldState.UNAVAILABLE and not chart.candles
    assert _card_field(snap).state is FieldState.OK


@pytest.mark.parametrize("days", [60])
def test_selected_window_stale_unknown_not_ok_and_degraded_matrix(monkeypatch, days):
    stale = _chart(_feed(monkeypatch, kbar=_kbar_view(days, is_stale=True, age_days=4, stale_reason="x"), days=days))
    assert stale.field.state is FieldState.STALE and stale.field.status_text == "⚠ 過期 4 天" and len(stale.candles) == days
    unk = _chart(_feed(monkeypatch, kbar=_kbar_view(days, is_stale=None, age_days=None), days=days))
    assert unk.field.state is FieldState.STALE and unk.field.status_text == T.TEXT_STALE_UNKNOWN
    bad = _kbar_view(days, ohlc_ok=False, ohlc_error=OC.INCOMPLETE_BAR, open=(), high=(), low=(), n_ohlc=0)
    g = _chart(_feed(monkeypatch, kbar=bad, days=days))
    assert g.field.state is JudgementState.UNDETERMINABLE and not g.candles and g.target_n == days
    r = _chart(_feed(monkeypatch, kbar_exc=RuntimeError("boom"), days=days))
    assert r.field.state is FieldState.UNAVAILABLE and not r.candles and r.target_n == days
    c = _chart(_feed(monkeypatch, card_exc=OSError("x"), kbar=_kbar_view(days), days=days))
    assert c.field.state is JudgementState.UNDETERMINABLE and not c.candles
    mm = _kbar_view(days)
    m = _chart(_feed(monkeypatch, kbar=mm, card=dataclasses.replace(_matching_card(mm), as_of="2026-01-01"), days=days))
    assert m.field.state is FieldState.UNAVAILABLE and m.field.detail == RC.KBAR_MISMATCH_TEXT and not m.candles


@pytest.mark.parametrize("bad", _BAD_DAYS, ids=repr)
def test_illegal_days_fail_closed_before_any_cache_read(monkeypatch, bad):
    """非法期間（含 bool、252、非 int、未核准值）→ `ValueError`，且 `get_twii_trend_view`／位階讀取一次都沒被呼叫。"""
    calls: list = []
    regime_calls: list = []
    monkeypatch.setattr(TWS, "get_twii_trend_view", lambda n, **kw: calls.append((n, kw)))
    monkeypatch.setattr(allocation_service, "get_macro_regime", lambda **kw: regime_calls.append(kw))
    with pytest.raises(ValueError):
        RF.read_real_snapshot(days=bad)
    with pytest.raises(ValueError):
        RF._read_twii_kbar(bad)
    assert calls == [] and regime_calls == []
    with pytest.raises(ValueError):
        RealFeedSnapshot.of(None, "E", None, "E", kbar_error="E", kbar_days=bad)
    with pytest.raises(ValueError):
        RC.twii_kbar_fact_of(_kbar_view(), days=bad)
    with pytest.raises(ValueError):
        RC.validate_twii_kbar_fact(RC.twii_kbar_fact_of(_kbar_view()), days=bad)


def test_illegal_days_guard_has_teeth(monkeypatch):
    """突變：拔掉 feed 的期間守衛 → 非法值會一路觸及 service 讀取（上面的『讀取前』斷言因此會轉紅）。"""
    calls: list = []
    monkeypatch.setattr(TWS, "get_twii_trend_view", lambda n, **kw: (calls.append((n, kw)), _kbar_view())[1])
    monkeypatch.setattr(allocation_service, "get_macro_regime", lambda **kw: _regime_dict())
    monkeypatch.setattr(RF, "_require_kbar_days", lambda d: d)
    RF._read_twii_kbar(252)
    assert calls and calls[0][0] == 252                                    # 守衛被拔掉＝252 真的被讀（測試會抓到）


def test_default_call_never_passes_through_the_selection_guard_differently(monkeypatch):
    """既有無參呼叫＝預設路徑：`read_real_snapshot()`、`_read_twii_kbar()` 簽名相容。"""
    import inspect
    assert inspect.signature(RF.read_real_snapshot).parameters["days"].default == 20
    assert inspect.signature(RF._read_twii_kbar).parameters["days"].default == 20


# ── view：radio 的位置與只在 Real 日 K 出現 ─────────────────────────────────
def test_picker_sits_after_the_chart_and_before_delta_only_when_the_vm_has_a_kbar(monkeypatch):
    vm = get_real_page_vm(P4_MARKET, _feed(monkeypatch))
    ev: list[str] = []
    _render(vm, monkeypatch, ev)
    i_l1 = next(i for i, c in enumerate(ev) if 'class="ui2-m-l1"' in c)
    assert 'data-ui2-l1="primary_chart"' in ev[i_l1 + 1]                    # 圖（含圖例、附註、資料日）
    assert ev[i_l1 + 2] == PICKER_MARK                                          # 圖之後
    assert 'data-ui2-delta="1"' in ev[i_l1 + 3]                                # 今日變化之前
    assert 'class="ui2-grid"' in ev[i_l1 + 4] and 'data-ui2-l1="onebrain"' in ev[i_l1 + 5]   # DEC-157 頁序不變
    assert ev.count(PICKER_MARK) == 1
    # 沒有日 K 事實（FAKE 軸／無 kbar 的 snapshot）→ 誠實空槽，沒有 radio
    for slot_vm in (get_real_page_vm(P4_MARKET, _snapshots()["loaded"]), get_preview_page_vm(P4_MARKET, "loaded")):
        assert slot_vm.context.kbar is None
        ev2: list[str] = []
        _render(slot_vm, monkeypatch, ev2)
        assert PICKER_MARK not in ev2 and any('data-ui2-l1="primary_slot"' in c for c in ev2)


@pytest.mark.parametrize("kw", [dict(kbar_exc=RuntimeError("x")), dict(card_exc=OSError("x")),
                                dict(kbar=_kbar_view(ohlc_ok=False, ohlc_error=OC.INCOMPLETE_BAR, open=(), high=(), low=(), n_ohlc=0)),
                                dict(kbar=_kbar_view(is_stale=True, age_days=3, stale_reason="x"))],
                         ids=["red", "card_failed_grey", "ohlc_not_ok_grey", "stale"])
def test_picker_stays_available_when_the_window_is_in_an_error_or_grey_state(monkeypatch, kw):
    ev: list[str] = []
    _render(get_real_page_vm(P4_MARKET, _feed(monkeypatch, **kw)), monkeypatch, ev)
    assert ev.count(PICKER_MARK) == 1


@pytest.mark.parametrize("p", [p for p in PAGE_IDS if p != P4_MARKET])
def test_other_pages_never_get_a_picker(monkeypatch, p):
    import inspect
    from src.ui2.views import VIEWS
    snap = _feed(monkeypatch)
    for vm in (get_real_page_vm(p, snap), get_preview_page_vm(p, "loaded")):
        assert vm.context.kbar is None
    assert "_kbar_period_picker" not in inspect.getsource(VIEWS[p])


# ── 真殼＋AppTest：radio、重跑讀取次數、FAKE／其他頁無 radio ─────────────────
def _real_at(**kw):
    from tests.test_ui2_real_feed import _at
    return _at(seed_fake=False, **kw)


def _bars_in(at) -> int:
    from tests.test_ui2_real_feed import _blob
    return len(re.findall(r"data-kbar-dir=", _blob(at)))


def _picker(at):
    return at.radio(key=KEY_DAYS)


def test_real_market_shows_the_picker_with_the_approved_labels_and_default_20(monkeypatch):
    at = _real_at()
    assert not at.exception
    r = _picker(at)
    assert r.label == "期間" and list(r.options) == APPROVED_LABELS
    assert "120" not in "".join(r.options)                                  # R20：不出現 120 日
    assert r.index == 0 and r.value == 20 and r.value == market.KBAR_DAYS_DEFAULT
    assert _bars_in(at) == 20
    assert [x.key for x in at.radio] == ["ui2_page", KEY_DAYS]              # 導覽之後、只多這一組


def test_picker_dom_order_is_chart_then_picker_then_delta_then_cards(monkeypatch):
    at = _real_at()
    kinds: list[str] = []
    for el in at.main:
        if el.type == "markdown":
            v = el.value
            kinds.append("chart" if 'data-ui2-l1="primary_chart"' in v else
                         "delta" if 'data-ui2-delta="1"' in v else
                         "grid" if 'class="ui2-grid"' in v else
                         "onebrain" if 'data-ui2-l1="onebrain"' in v else "")
        elif el.type == "radio" and getattr(el, "key", None) == KEY_DAYS:
            kinds.append("picker")
    order = [k for k in kinds if k]
    assert order[:5] == ["chart", "picker", "delta", "grid", "onebrain"], order


@pytest.mark.parametrize("days", [60])
def test_selecting_a_window_redraws_that_many_bars_with_one_snapshot_per_rerun(monkeypatch, days):
    calls: list = []
    orig = TWS.get_twii_trend_view

    def counted(n, **kw):
        calls.append((n, kw))
        return orig(n, **kw)
    monkeypatch.setattr(TWS, "get_twii_trend_view", counted)
    at = _real_at()
    assert calls == [(1, {}), (20, {"with_ohlc": True})]                    # 首跑：卡片 1 次＋日 K 1 次（預設 20）
    calls.clear()
    _picker(at).set_value(days).run(timeout=60)
    assert not at.exception
    assert calls == [(1, {}), (days, {"with_ohlc": True})]                  # 切換那次 rerun：仍恰各讀一次
    from tests.test_ui2_real_feed import _blob
    blob = _blob(at)
    assert _bars_in(at) == days and f"共 {days} 根" in blob
    snap_direct = TWS.get_twii_trend_view(days, with_ohlc=True)
    assert [d for d in re.findall(r'data-kbar-date="([\d-]+)"', blob)] == list(snap_direct.xs)
    calls.clear()
    _picker(at).set_value(20).run(timeout=60)                               # 可切回
    assert _bars_in(at) == 20 and calls == [(1, {}), (20, {"with_ohlc": True})]


def test_card_and_chart_stay_same_source_after_switching(monkeypatch):
    from tests.test_ui2_real_feed import _blob
    at = _real_at()
    _picker(at).set_value(60).run(timeout=60)
    blob = _blob(at)
    card_val = re.search(r'data-card-id="twii".*?ui2-card__value[^>]*>([\d,\.]+)<', blob, re.S)
    kbar_val = re.search(r'data-ui2-l1="primary_chart".*?ui2-(?:field|kbar)__value[^>]*>([\d,\.]+)<', blob, re.S)
    direct = TWS.get_twii_trend_view(60, with_ohlc=True)
    assert f"{direct.close[-1]:,.2f}" in blob
    if card_val and kbar_val:
        assert card_val.group(1) == kbar_val.group(1)


def test_fake_axis_and_other_pages_have_no_picker(monkeypatch):
    from tests.test_ui2_real_feed import _at
    at = _at()                                                          # FAKE（預設播種為 fake）
    assert not at.exception and [x.key for x in at.radio] == ["ui2_page"]
    assert 'data-ui2-l1="primary_chart"' not in "\n".join(m.value for m in at.markdown)
    at = _real_at()
    for p in PAGE_IDS:
        at.radio(key="ui2_page").set_value(p).run(timeout=60)
        keys = [x.key for x in at.radio]
        assert (KEY_DAYS in keys) == (p == P4_MARKET), (p, keys)
    # Real → 回 FAKE（開發面）：radio 消失
    at = _real_at(dev=True)
    at.selectbox(key="ui2_feed").set_value("fake").run(timeout=60)
    assert KEY_DAYS not in [x.key for x in at.radio]


def test_other_pages_read_the_default_window_even_if_a_non_default_was_selected(monkeypatch):
    calls: list = []
    orig = TWS.get_twii_trend_view
    monkeypatch.setattr(TWS, "get_twii_trend_view", lambda n, **kw: (calls.append((n, kw)), orig(n, **kw))[1])
    at = _real_at()
    _picker(at).set_value(60).run(timeout=60)
    calls.clear()
    at.radio(key="ui2_page").set_value("p4_data").run(timeout=60)
    assert not at.exception and calls == [(1, {}), (20, {"with_ohlc": True})]    # 其他頁走原路徑（預設窗）


def test_illegal_session_value_is_reset_to_the_default_and_nothing_wider_is_read(monkeypatch):
    from streamlit.testing.v1 import AppTest
    from tests.test_ui2_real_feed import APP_UI2
    for bad in (120, 252, True, "60", "120", 20.0, 60.0, None):
        calls: list = []
        orig = TWS.get_twii_trend_view
        monkeypatch.setattr(TWS, "get_twii_trend_view", lambda n, _o=orig, **kw: (calls.append((n, kw)), _o(n, **kw))[1])
        a = AppTest.from_file(str(APP_UI2), default_timeout=60)
        a.session_state[KEY_DAYS] = bad
        a.run(timeout=60)
        assert not a.exception, bad
        assert calls == [(1, {}), (20, {"with_ohlc": True})], (bad, calls)
        assert _bars_in(a) == 20 and a.session_state[KEY_DAYS] == 20
        monkeypatch.setattr(TWS, "get_twii_trend_view", orig)


def test_picker_survives_a_red_chart_and_still_switches(monkeypatch):
    """整窗錯誤（日 K 讀取失敗）→ 圖是紅色 Unavailable，radio 仍在、仍可切、切到的窗被傳進讀取。"""
    calls: list = []
    orig = TWS.get_twii_trend_view

    def flaky(n, **kw):
        calls.append((n, kw))
        if kw.get("with_ohlc"):
            raise RuntimeError("boom")
        return orig(n, **kw)
    monkeypatch.setattr(TWS, "get_twii_trend_view", flaky)
    at = _real_at()
    assert not at.exception and KEY_DAYS in [x.key for x in at.radio]
    calls.clear()
    _picker(at).set_value(60).run(timeout=60)
    assert not at.exception and calls == [(1, {}), (60, {"with_ohlc": True})]
    from tests.test_ui2_real_feed import _blob
    assert 'data-state="unavailable"' in _blob(at) and _bars_in(at) == 0


def test_shell_whole_read_failure_keeps_the_picker_and_the_selected_window(monkeypatch):
    from src.ui2.shell import app as shell

    def boom(*a, **k):
        raise RuntimeError("secret-token")
    monkeypatch.setattr(shell, "read_real_snapshot", boom)
    at = _real_at()
    assert not at.exception and KEY_DAYS in [x.key for x in at.radio]
    _picker(at).set_value(60).run(timeout=60)
    assert not at.exception
    from tests.test_ui2_real_feed import _blob
    assert "secret-token" not in _blob(at)


def test_shell_passes_no_argument_for_the_default_window_and_days_for_the_others(monkeypatch):
    """預設窗維持**無參**呼叫（既有注入點 `lambda: snap` 的測試／入口包裝不受影響）；非預設才帶 `days`。"""
    from src.ui2.shell import app as shell
    seen: list = []
    orig = shell.read_real_snapshot

    def spy(*a, **k):
        seen.append((a, k))
        return orig(*a, **k)
    monkeypatch.setattr(shell, "read_real_snapshot", spy)
    at = _real_at()
    assert seen == [((), {})]
    seen.clear()
    _picker(at).set_value(60).run(timeout=60)
    assert seen == [((), {"days": 60})]
    seen.clear()
    _picker(at).set_value(20).run(timeout=60)
    assert seen == [((), {})]


def test_g9_and_g2f_guards_stay_green_and_the_allowlist_is_untouched():
    from tests import test_ui2_guards as G
    for path in (G.ROOT / "src/ui2/views/market.py", G.ROOT / "src/ui2/shell/app.py"):
        assert G.check_not_a_producer(path.read_text(encoding="utf-8")) == [], path.name
        assert G.check_independence(path.read_text(encoding="utf-8")) == []
        assert G.check_l5_service_reads(path.read_text(encoding="utf-8"), path.relative_to(G.ROOT).as_posix()) == []
    feed = G.FEED_FILES[0].read_text(encoding="utf-8")
    assert G.check_feed_boundary(feed) == []
    assert G.G2F_IMPORT_ALLOWLIST["src.services.ui2.real_canonical"] == _G2F_RC_BEFORE | {"twii_kbar_fact_of"}
