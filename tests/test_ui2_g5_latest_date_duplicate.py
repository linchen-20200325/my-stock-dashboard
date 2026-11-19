# -*- coding: utf-8 -*-
"""tests/test_ui2_g5_latest_date_duplicate.py — G-5（#1199 總管裁示 2，comment 7011701691）：最新日重複 → 卡片 fail-closed。

缺陷（修前）：L1 `load_twii_close` 保留重複日期（`sort_index`＋`dropna` 不去重）；L3 `get_twii_trend_view` 只看尾端單一收盤，
最新日若有兩列（值相同或不同），卡片 `ok=True` 顯示最後一個值（看似正常的歧義值）；日 K 在視窗內以 `DUPLICATE_DATE` 拒畫。

核准語意（本檔斷言）：
- **卡片實際採用的最新觀測日期**在輸入序列中有多列（值相同或不同）→ 來源歧義：卡片不顯任何收盤數字、不取末筆／平均／去重擇一；
  走**既有灰色「無法判定」**（`JudgementState.UNDETERMINABLE`，字樣 `⬜ 無法判定`）——不是紅色 Unavailable、不是「資料未取得」、
  不新增 FieldState／文案；日 K 維持既有 `DUPLICATE_DATE` 保守不畫。
- 特例限制：重複只在遠端歷史而最近收盤唯一 → 卡片照常（與日 K 的隔離語意保留）。
- 不回歸：NaN 最新日、future_as_of、上游失敗、stale、無資料、FAKE 控制組。
- L1 不去重（`load_twii_close` 全域行為不變）；L0 OHLC 契約不放寬。
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import re
from html import unescape

import pandas as pd
import pytest

from shared import twii_ohlc_contract as OC
from shared.ui2_contract import text as T
from shared.ui2_contract.models import FieldState, JudgementState
from shared.ui2_contract.pages import P4_MARKET, SCENARIO_IDS
from src.data.macro import macro_cache_reader as R
from src.services import market_twii_view_service as S
from src.services.ui2 import real_canonical as RC
from src.services.ui2.preview_feed import get_preview_page_vm
from src.services.ui2.real_canonical import RealFeedContractError, RealFeedSnapshot, TwiiFact, get_real_page_vm
from src.ui2.views import _page, market
from tests.test_issue1202_future_as_of import BASE, _Env


# ── helpers ──────────────────────────────────────────────────────────────
def _write(tmp_path, dates, closes):
    """寫 twii_ohlcv.parquet（日期可重複；open/high/low=close；fetched_at 在台北收盤後 ⇒ 完整棒）。"""
    ds = [pd.Timestamp(d) for d in dates]
    df = pd.DataFrame({"date": ds, "close": list(closes)})
    df["open"] = df["high"] = df["low"] = df["close"]
    df["volume"] = 1000
    df["fetched_at"] = [f"{d.date().isoformat()}T10:00:00+00:00" for d in ds]
    df.to_parquet(tmp_path / "twii_ohlcv.parquet")


def _seq(end: dt.date, n: int) -> list[dt.date]:
    return [end - dt.timedelta(days=n - 1 - i) for i in range(n)]


_Y = BASE - dt.timedelta(days=1)          # 昨日：新鮮的最新資料日


@pytest.fixture
def env(monkeypatch, tmp_path):
    return _Env(monkeypatch, tmp_path)


def _dup_latest(env, closes_last_two=(300.0, 400.0), n_before=3):
    """n_before 筆各日唯一 ＋ 最新日 _Y 兩列。"""
    prior = _seq(_Y - dt.timedelta(days=1), n_before)
    base_closes = [22000.0 + i for i in range(n_before)]
    _write(env.tmp, prior + [_Y, _Y], base_closes + list(closes_last_two))


def _render(snap, monkeypatch) -> str:
    out: list[str] = []
    monkeypatch.setattr(market, "_md", out.append)
    monkeypatch.setattr(_page, "_md", out.append)
    market.render(get_real_page_vm(P4_MARKET, snap))
    return unescape(re.sub(r"<[^>]+>", " ", "".join(out)))


# ════════════════════════════════════════════════════════════════════
# 0｜前提：L1 不去重（G-5 修在 L3，不改 L1 全域行為）
# ════════════════════════════════════════════════════════════════════
def test_l1_load_twii_close_still_keeps_duplicate_dates(tmp_path):
    _write(tmp_path, [_Y - dt.timedelta(days=1), _Y, _Y], [100.0, 200.0, 300.0])
    s = R.load_twii_close(cache_dir=tmp_path, today=BASE)
    assert len(s) == 3 and list(s.index.strftime("%Y-%m-%d")).count(_Y.isoformat()) == 2   # 重複列原樣保留


# ════════════════════════════════════════════════════════════════════
# 1｜L3：最新日重複 → 卡片 fail-closed（值相同或不同皆然）
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("last_two", [(300.0, 400.0), (400.0, 300.0), (300.0, 300.0)],
                         ids=["different-asc", "different-desc", "same-value"])
@pytest.mark.parametrize("n", [1, 2, 5, 252])
def test_card_latest_date_duplicated_is_fail_closed(env, last_two, n, capsys):
    _dup_latest(env, last_two)
    v = S.get_twii_trend_view(n)
    assert v.ok is False and v.failed is False                 # 灰（不是紅例外）
    assert v.close == () and v.xs == ()                        # ⛔ 不取末筆、不平均、不去重擇一
    assert v.as_of_ambiguous is True
    assert v.error == S._UNREADABLE_TEXT                       # 不新增使用者可見字樣（legacy 沿用既有灰字）
    out = capsys.readouterr().out                              # 具體原因只進 log（含歧義日期與列數）
    assert "最新資料日" in out and _Y.isoformat() in out and "2 列" in out


def test_card_unique_latest_date_is_not_killed(env):
    prior = _seq(_Y, 4)
    _write(env.tmp, prior, [22000.0, 22001.0, 22002.0, 22003.5])
    v = S.get_twii_trend_view(1)
    assert v.ok and v.close == (22003.5,) and v.as_of == _Y.isoformat() and v.as_of_ambiguous is False


def test_card_historical_duplicate_with_unique_latest_stays_ok(env):
    """重複只在遠端歷史、最近收盤唯一 ⇒ 不因與最新值無關的重複就把卡片一律判無效。"""
    d = _seq(_Y, 6)
    dates = [d[0], d[1], d[1]] + d[2:]            # 歷史重複在 d[1]
    _write(env.tmp, dates, [22000.0 + i for i in range(7)])
    for n in (1, 2, 3):                            # 窗口不含重複
        v = S.get_twii_trend_view(n)
        assert v.ok and v.as_of_ambiguous is False and v.close[-1] == 22006.0
    v = S.get_twii_trend_view(7)                   # 窗口含歷史重複：卡片行為與修前相同（不在 G-5 範圍）
    assert v.ok and v.as_of_ambiguous is False


@pytest.mark.parametrize("n", [1, 20])
def test_kbar_still_rejects_duplicate_and_card_isolation_is_kept(env, n):
    """with_ohlc：視窗含重複 → DUPLICATE_DATE；`ok` 仍 True（日 K 與卡片的隔離語意：日 K 不因此變成『資料未取得』）；旗標與卡片一致。"""
    _dup_latest(env)
    k = S.get_twii_trend_view(n, with_ohlc=True)
    assert k.ohlc_ok is False and k.ohlc_error == OC.DUPLICATE_DATE
    assert k.open == () and k.n_ohlc == 0                      # ⛔ 部分填
    assert k.ok is True                                        # 日 K 走自己的 DUPLICATE_DATE 灰態，不連動成 missing
    assert k.as_of_ambiguous is True


def test_kbar_n1_window_that_misses_the_other_duplicate_row_is_still_rejected(env):
    """修前：n=1 時 tail(1) 只含兩列重複中的一列，L0 契約看不到重複 ⇒ 日 K 以單根合格；修後與卡片一致保守不畫。"""
    _dup_latest(env)
    k = S.get_twii_trend_view(1, with_ohlc=True)
    assert k.ohlc_ok is False and k.ohlc_error == OC.DUPLICATE_DATE


def test_both_modes_agree_on_ambiguity_flag_across_cases(env):
    cases = {
        "dup-latest-diff": ([*_seq(_Y - dt.timedelta(days=1), 3), _Y, _Y], [1.0, 2.0, 3.0, 300.0, 400.0], True),
        "dup-latest-same": ([*_seq(_Y - dt.timedelta(days=1), 3), _Y, _Y], [1.0, 2.0, 3.0, 300.0, 300.0], True),
        "unique": ([*_seq(_Y, 5)], [1.0, 2.0, 3.0, 4.0, 5.0], False),
        "hist-dup": ([*_seq(_Y - dt.timedelta(days=4), 2), _Y - dt.timedelta(days=4), *_seq(_Y, 2)],
                     [1.0, 2.0, 3.0, 4.0, 5.0], False),
    }
    for name, (dates, closes, want) in cases.items():
        _write(env.tmp, dates, closes)
        for n in (1, 3):
            c = S.get_twii_trend_view(n)
            k = S.get_twii_trend_view(n, with_ohlc=True)
            assert c.as_of_ambiguous is want and k.as_of_ambiguous is want, (name, n)


def test_nan_latest_row_is_not_conflated_with_ambiguity(env):
    """NaN 最新日（單列）：沿用 #1140 C1 既有 fail-closed，不是歧義旗標。"""
    _write(env.tmp, _seq(_Y, 3), [22000.0, 22001.0, float("nan")])
    v = S.get_twii_trend_view(1)
    assert v.ok is False and v.as_of_ambiguous is False and v.error == S._UNREADABLE_TEXT


def test_documented_boundary_duplicate_latest_with_one_nan_close(env):
    """已知邊界（單組判斷，登記）：卡片的輸入是 L1 dropna 之後的收盤序列。最新日兩列但其中一列 close=NaN → 卡片輸入只剩一列，
    不判歧義（L1 已把 NaN 剔除並 log）；日 K 看原始視窗 → 仍以 DUPLICATE_DATE 拒畫。"""
    prior = _seq(_Y - dt.timedelta(days=1), 3)
    _write(env.tmp, prior + [_Y, _Y], [1.0, 2.0, 3.0, 22100.0, float("nan")])
    c = S.get_twii_trend_view(1)
    assert c.as_of_ambiguous is False
    k = S.get_twii_trend_view(5, with_ohlc=True)
    assert k.ohlc_ok is False and k.open == ()            # 日 K 仍不畫（本 fixture 的 open=close 也含 NaN ⇒ 原因碼可為 NOT_FINITE 或 DUPLICATE_DATE）
    assert k.ohlc_error in (OC.DUPLICATE_DATE, OC.NOT_FINITE)


# ── 不回歸對照組（L3）──────────────────────────────────────────────────────
def test_future_as_of_still_confirmed_future_not_ambiguity(env):
    _write(env.tmp, _seq(BASE + dt.timedelta(days=2), 3), [22000.0, 22001.0, 22002.0])
    v = S.get_twii_trend_view(1)
    assert v.ok and v.as_of_future is True and v.as_of_ambiguous is False


def test_stale_is_not_ambiguity(env):
    _write(env.tmp, _seq(BASE - dt.timedelta(days=60), 3), [22000.0, 22001.0, 22002.0])
    v = S.get_twii_trend_view(1)
    assert v.ok and v.is_stale is True and v.as_of_ambiguous is False


def test_no_data_and_upstream_failure_are_not_ambiguity(env, monkeypatch):
    v = S.get_twii_trend_view(1)                     # 檔不存在
    assert v.ok is False and v.failed is False and v.as_of_ambiguous is False

    def boom(*a, **k):
        raise OSError("disk")
    monkeypatch.setattr(R, "load_twii_close", boom)
    v = S.get_twii_trend_view(1)
    assert v.ok is False and v.failed is True and v.as_of_ambiguous is False


# ════════════════════════════════════════════════════════════════════
# 2｜UI2 canonical 契約層：既有灰色「無法判定」
# ════════════════════════════════════════════════════════════════════
def _fact(**kw) -> TwiiFact:
    d = dict(ok=False, close=(), as_of=None, is_stale=None, stale_reason="", age_days=None, has_upstream_error=False,
             error_type="", failed=False, source="本地加權指數歷史快取", upstream_state="", as_of_future=None,
             as_of_ambiguous=True)
    d.update(kw)
    return TwiiFact(**d)


def _snap(fact) -> RealFeedSnapshot:
    from shared import regime_arbiter as RA
    regime = RC.RegimeFact(regime="unknown", light="⬜", source=RA.SOURCE_UNLOADED, is_loaded=False)
    return RealFeedSnapshot.of(fact, "", regime, "")


def test_twii_fact_new_field_is_additive_trailing_default_false():
    f = TwiiFact(True, (1.0,), "2026-01-01", False, "", 1, False, "", False, "s")     # 既有 10 個位置參數建構不受影響
    assert f.as_of_ambiguous is False
    assert dataclasses.fields(TwiiFact)[-1].name == "as_of_ambiguous"


def test_card_spec_for_ambiguous_fact_is_existing_grey_undeterminable_without_value():
    spec = RC.twii_card_spec(_snap(_fact()))
    assert spec["state"] == "undeterminable" and spec["value"] is None
    assert "missing_kind" not in spec                         # 不是「資料未取得」
    f = get_real_page_vm(P4_MARKET, _snap(_fact())).context.cards[0].field
    assert f.state is JudgementState.UNDETERMINABLE           # 既有判定結果態（不新增 FieldState）
    assert f.value_text is None
    assert f.status_text == T.TEXT_RISK_CAP_UNDETERMINABLE == "⬜ 無法判定"
    assert f.status_text not in (T.TEXT_MISSING_NOT_FETCHED, T.TEXT_UNAVAILABLE, T.TEXT_MISSING_NOT_READY)
    assert f.detail is None                                   # 不新增使用者可見文案


def test_ambiguity_flag_wins_even_if_a_value_is_attached_fail_closed():
    """防呆：就算 fact 同時 ok=True 且帶了收盤值，歧義旗標也不得讓數字上畫面。"""
    f = _fact(ok=True, close=(300.0,), as_of="2026-11-10", is_stale=False, age_days=1)
    spec = RC.twii_card_spec(_snap(f))
    assert spec["state"] == "undeterminable" and spec["value"] is None
    assert "300" not in repr(get_real_page_vm(P4_MARKET, _snap(f)).context.cards[0].field)


@pytest.mark.parametrize("bad", [1, 0, "True", None, "yes"])
def test_validate_twii_fact_rejects_non_bool_ambiguity_flag(bad):
    with pytest.raises(RealFeedContractError):
        RC.validate_twii_fact(_fact(as_of_ambiguous=bad))


def test_failed_fact_is_still_red_and_not_overridden_by_flag_default():
    f = _fact(as_of_ambiguous=False, failed=True, error_type="OSError")
    assert RC.twii_card_spec(_snap(f))["state"] == "unavailable"


def test_not_ambiguous_missing_card_is_unchanged():
    spec = RC.twii_card_spec(_snap(_fact(as_of_ambiguous=False)))
    assert spec.get("missing_kind") == "not_fetched" and spec.get("state") is None


# ════════════════════════════════════════════════════════════════════
# 3｜端到端：真 L1 parquet → 真 feed → canonical → VM → 畫面
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("last_two", [(30011.25, 40022.75), (30011.25, 30011.25)], ids=["different", "same"])
def test_end_to_end_latest_duplicate_card_shows_no_number_and_kbar_stays_rejected(env, monkeypatch, last_two):
    _dup_latest(env, last_two)
    snap = env.snapshot()
    assert snap.twii is not None and snap.twii.as_of_ambiguous is True and snap.twii.ok is False   # feed 拷貝旗標
    vm = get_real_page_vm(P4_MARKET, snap)
    card = vm.context.cards[0].field
    assert card.state is JudgementState.UNDETERMINABLE and card.value_text is None
    kbar = vm.context.kbar
    assert kbar is not None and kbar.candles == ()              # 日 K 仍拒畫
    assert kbar.field.state is JudgementState.UNDETERMINABLE    # DUPLICATE_DATE → 既有類別句，灰
    assert "日 K 日期或筆數異常" in (kbar.field.detail or "")
    shown = _render(snap, monkeypatch)
    for v in last_two:
        assert f"{v:,.2f}" not in shown and f"{v:,.0f}" not in shown and str(v) not in shown     # 任何位置都沒有歧義值
    assert "無法判定" in shown


def test_end_to_end_unique_latest_is_not_killed(env, monkeypatch):
    _write(env.tmp, _seq(_Y, 22), [22000.0 + i for i in range(22)])
    snap = env.snapshot()
    assert snap.twii.as_of_ambiguous is False and snap.twii.ok is True
    vm = get_real_page_vm(P4_MARKET, snap)
    assert vm.context.cards[0].field.value_text == "22,021.00"
    assert vm.context.kbar is not None and len(vm.context.kbar.candles) == 20


def test_end_to_end_historical_duplicate_card_ok_kbar_isolated(env, monkeypatch):
    d = _seq(_Y, 22)
    dates = d[:10] + [d[9]] + d[10:]                              # 歷史重複在視窗內（第 10 日）
    _write(env.tmp, dates, [22000.0 + i for i in range(23)])
    snap = env.snapshot()
    vm = get_real_page_vm(P4_MARKET, snap)
    assert vm.context.cards[0].field.value_text == "22,022.00"    # 卡片正常
    assert vm.context.kbar.candles == () and vm.context.kbar.field.state is JudgementState.UNDETERMINABLE   # 日 K 自己拒畫


def test_end_to_end_other_failure_modes_are_not_regressed(env, monkeypatch):
    # NaN 最新日：卡片灰 missing（既有）
    _write(env.tmp, _seq(_Y, 3), [22000.0, 22001.0, float("nan")])
    snap = env.snapshot()
    assert snap.twii.as_of_ambiguous is False
    f = get_real_page_vm(P4_MARKET, snap).context.cards[0].field
    assert f.state is FieldState.MISSING and f.status_text == T.TEXT_MISSING_NOT_FETCHED
    # future_as_of：專用紅字
    _write(env.tmp, _seq(BASE + dt.timedelta(days=2), 3), [22000.0, 22001.0, 22002.0])
    snap = env.snapshot()
    assert snap.twii is None and snap.twii_error == RC.FUTURE_AS_OF_ERROR
    # stale：照畫＋過期字樣
    _write(env.tmp, _seq(BASE - dt.timedelta(days=60), 3), [22000.0, 22001.0, 22002.0])
    f = get_real_page_vm(P4_MARKET, env.snapshot()).context.cards[0].field
    assert f.state is FieldState.STALE and f.value_text == "22,002.00"
    # 無資料（檔不存在）
    (env.tmp / "twii_ohlcv.parquet").unlink()
    f = get_real_page_vm(P4_MARKET, env.snapshot()).context.cards[0].field
    assert f.state is FieldState.MISSING and f.value_text is None


def test_freshness_overview_counts_ambiguous_card_as_undeterminable_not_ok(env):
    _dup_latest(env)
    snap = env.snapshot()
    assert RC.item_state_of_spec(RC.twii_card_spec(snap)) == "undeterminable"


# ════════════════════════════════════════════════════════════════════
# 4｜FAKE 控制組：FAKE 示意軸完全不經過 L3 service
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("scenario", SCENARIO_IDS)
def test_fake_axis_never_calls_the_service_and_never_uses_ambiguity(scenario, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("FAKE 軸不得呼叫 L3 get_twii_trend_view")
    monkeypatch.setattr(S, "get_twii_trend_view", boom)
    card = get_preview_page_vm(P4_MARKET, scenario).context.cards[0].field
    assert card.state in (FieldState.OK, FieldState.STALE, FieldState.NOT_EVALUATED)      # FAKE 軸從不出現「無法判定」
    assert card.freshness.source in (None, "FAKE 示意資料")
