# -*- coding: utf-8 -*-
"""tests/test_issue1140_price_asof_safety.py — Issue #1140 章節 C：兩項獨立安全修復的回歸防護。

C1 收盤價 ≤ 0／NaN／±Inf：UI2 卡片路徑（`get_twii_trend_view` 非 ohlc、`validate_twii_fact`）與 KBar 路徑
   （L0 `validate_ohlc_window`）對「價格」的有效性規則一致（L0 `price_problem` 為唯一規則）。
   ⛔ 只管價格類欄位：其他指標的合法 0（淨買超 0、持平、0 天）必須保持可用。
C2 未來 as_of：L1 D2（`compute_cache_staleness`）照實保留負 age_days 供診斷；下游（L3 `TwiiTrendView`、
   `stale_text`、UI2 契約驗證）一律不得出現「過期 -N 天」、不得截成 0 天、不得當 fresh。

測試以真實 L1（`macro_cache_reader`）讀 tmp parquet 做端到端；無網路、無 streamlit session、不碰真實 data_cache。
"""
from __future__ import annotations

import datetime as dt
import math
import re

import pandas as pd
import pytest

from shared import twii_ohlc_contract as OC
from shared.ui2_contract import text as T
from src.data.macro import macro_cache_reader as R
from src.services import market_twii_view_service as S
from src.services.ui2 import real_canonical as RC
from src.services.ui2.real_canonical import RealFeedContractError, TwiiFact, TwiiKbarFact

_NEG_DAYS_RX = re.compile(r"過期\s*-\s*\d+|-\d+\s*天")


# ── helpers ──────────────────────────────────────────────────────────────
def _write_twii(tmp_path, dates, closes, *, extra_cols=True):
    """寫一份 twii_ohlcv.parquet（日 K 欄位齊全；fetched_at 帶時區且晚於台北 17:00 ⇒ 合格收盤棒）。"""
    n = len(dates)
    df = pd.DataFrame({"date": pd.to_datetime(list(dates)), "close": list(closes)})
    if extra_cols:
        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
        df["volume"] = 1000
        df["fetched_at"] = [f"{pd.Timestamp(d).date().isoformat()}T10:00:00+00:00" for d in dates]
    df.to_parquet(tmp_path / "twii_ohlcv.parquet")
    return n


@pytest.fixture
def real_l1(tmp_path, monkeypatch):
    """讓 L3 service 讀 tmp 的 parquet（真實 L1 邏輯，只改 cache_dir）。"""
    orig_close, orig_ohlc = R.load_twii_close, R.load_twii_ohlc
    monkeypatch.setattr(R, "load_twii_close", lambda *a, **k: orig_close(cache_dir=tmp_path, **k))
    monkeypatch.setattr(R, "load_twii_ohlc", lambda *a, **k: orig_ohlc(cache_dir=tmp_path, **k))
    return tmp_path


def _days(end: dt.date, n: int):
    return [end - dt.timedelta(days=n - 1 - i) for i in range(n)]


_TODAY = dt.date(2026, 11, 11)


# ════════════════════════════════════════════════════════════════════
# C1｜價格有效性 canonical 規則（L0 price_problem）
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("v,code", [
    (0, OC.NON_POSITIVE), (0.0, OC.NON_POSITIVE), (-1.0, OC.NON_POSITIVE), (-23000.5, OC.NON_POSITIVE),
    (float("nan"), OC.NOT_FINITE), (float("inf"), OC.NOT_FINITE), (float("-inf"), OC.NOT_FINITE),
    (None, OC.NOT_FINITE), ("abc", OC.NOT_FINITE), (True, OC.NOT_FINITE), ([], OC.NOT_FINITE),
])
def test_price_problem_rejects_zero_negative_nonfinite_nonnumeric(v, code):
    assert OC.price_problem(v) == code


@pytest.mark.parametrize("v", [0.01, 1, 23456.78, 1e9])
def test_price_problem_accepts_finite_positive(v):
    assert OC.price_problem(v) is None


@pytest.mark.parametrize("bad", [0.0, -5.0, float("nan"), float("inf"), float("-inf")])
def test_kbar_contract_and_price_problem_agree_on_the_same_bad_close(bad):
    """日 K 契約（validate_ohlc_window）與卡片共用的 price_problem 對同一個壞 close 結論一致（同一條規則，不另寫）。"""
    ok, code, _ = OC.validate_ohlc_window(
        ("2026-11-10",), (100.0,), (100.0,), (100.0,), (bad,), ("2026-11-10T10:00:00+00:00",),
        as_of="2026-11-10", today=dt.date(2026, 11, 11))
    assert ok is False and code == OC.price_problem(bad)


def test_ohlc_contract_behaviour_unchanged_for_mixed_violations():
    """重構 validate_ohlc_window 內的檢查呼叫後，first-violation 順序不變：同一列 open=0 且 high=NaN → 先報 NOT_FINITE。"""
    ok, code, _ = OC.validate_ohlc_window(
        ("2026-11-10",), (0.0,), (float("nan"),), (0.0,), (1.0,), ("2026-11-10T10:00:00+00:00",),
        as_of=None, today=dt.date(2026, 11, 11))
    assert (ok, code) == (False, OC.NOT_FINITE)


# ── L3 卡片路徑（端到端：真實 L1 讀 tmp parquet）────────────────────────────
def _view(real_l1, closes, *, end=_TODAY - dt.timedelta(days=1), n=1, today=_TODAY, **kw):
    _write_twii(real_l1, _days(end, len(closes)), closes)
    return S.get_twii_trend_view(n, today=today, **kw)


def test_card_valid_close_is_ok(real_l1):
    v = _view(real_l1, [22000.0, 22100.5])
    assert v.ok and v.close == (22100.5,) and v.as_of == "2026-11-10" and v.is_stale is False


@pytest.mark.parametrize("bad", [0.0, -1.0, -23000.0, float("inf"), float("-inf")])
def test_card_rejects_latest_zero_negative_inf(real_l1, bad, capsys):
    v = _view(real_l1, [22000.0, bad])
    assert v.ok is False and v.failed is False        # 灰（讀不到語意），不是紅例外
    assert v.close == () and v.xs == ()               # ⛔ 不回壞值、不補 0
    assert v.error == S._UNREADABLE_TEXT              # 沿用既有字樣，不新增使用者可見文案
    assert "收盤價未通過價格有效性檢查" in capsys.readouterr().out   # 原因只進 log


def test_card_rejects_latest_nan_instead_of_showing_previous_close_as_latest(real_l1):
    """L1 對 NaN 只 dropna：最新列 close=NaN 時，尾端會變成前一天的值卻掛最新 as_of。必須拒用。"""
    v = _view(real_l1, [22000.0, float("nan")])
    assert v.ok is False and v.close == ()


def test_card_nan_in_older_row_outside_window_is_unaffected(real_l1):
    v = _view(real_l1, [float("nan"), 22000.0, 22100.0], n=2)
    assert v.ok and v.close == (22000.0, 22100.0)


def test_card_window_with_zero_inside_is_rejected_whole_not_filtered(real_l1):
    v = _view(real_l1, [22000.0, 0.0, 22100.0], n=3)
    assert v.ok is False and v.close == ()            # ⛔ 剔除壞值後照畫（與日 K 同：整段不合格）


def test_card_zero_outside_window_does_not_reject(real_l1):
    v = _view(real_l1, [0.0, 22000.0, 22100.0], n=2)
    assert v.ok and v.close == (22000.0, 22100.0)


def test_card_and_kbar_agree_on_rejection_zero_close(real_l1):
    """同一份壞檔：卡片 ok=False；日 K 路徑 ohlc_ok=False 且原因碼＝同一個 NON_POSITIVE。"""
    _write_twii(real_l1, _days(_TODAY - dt.timedelta(days=1), 3), [22000.0, 22100.0, 0.0])
    card = S.get_twii_trend_view(1, today=_TODAY)
    kbar = S.get_twii_trend_view(3, today=_TODAY, with_ohlc=True)
    assert card.ok is False
    assert kbar.ohlc_ok is False and kbar.ohlc_error == OC.NON_POSITIVE


def test_ohlc_path_behaviour_is_unchanged_by_card_guard(real_l1):
    """with_ohlc=True 的收盤卡欄位沿用原路徑（不被卡片守衛改成 ok=False）：合格資料照常。"""
    _write_twii(real_l1, _days(_TODAY - dt.timedelta(days=1), 5), [22000.0 + i for i in range(5)])
    v = S.get_twii_trend_view(5, today=_TODAY, with_ohlc=True)
    assert v.ok and v.ohlc_ok is True and v.n_ohlc == 5


# ── UI2 契約層（real_canonical）：不依賴 L3 守衛的第二道防線 ───────────────────
def _fact(**kw) -> TwiiFact:
    d = dict(ok=True, close=(23456.78,), as_of="2026-11-10", is_stale=False, stale_reason="", age_days=1,
             has_upstream_error=False, error_type="", failed=False, source="本地加權指數歷史快取", upstream_state="")
    d.update(kw)
    return TwiiFact(**d)


@pytest.mark.parametrize("bad", [0.0, 0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_validate_twii_fact_rejects_nonpositive_or_nonfinite_close(bad):
    with pytest.raises(RealFeedContractError):
        RC.validate_twii_fact(_fact(close=(bad,)))


def test_validate_twii_fact_rejects_zero_anywhere_in_close_tuple():
    with pytest.raises(RealFeedContractError):
        RC.validate_twii_fact(_fact(close=(0.0, 23456.78)))


def test_validate_twii_fact_still_accepts_valid_and_missing_states():
    RC.validate_twii_fact(_fact())
    RC.validate_twii_fact(_fact(ok=False, close=(), as_of=None))      # 讀不到：沒有收盤值本來就合法
    RC.validate_twii_fact(_fact(ok=False, failed=True, close=(), error_type="OSError"))


def test_card_spec_for_bad_close_fails_loud_instead_of_rendering_a_value():
    with pytest.raises(RealFeedContractError):
        RC.twii_card_spec(_snap(_fact(close=(0.0,))))


def test_legit_zero_is_not_rejected_for_non_price_fields():
    """C1 邊界：價格規則不一刀切。0 天、0 值的非價格欄（stale 天數 0、upstream 空）保持可用。"""
    RC.validate_twii_fact(_fact(age_days=0))
    assert T.stale_text(0) == "⚠ 過期 0 天"


# ════════════════════════════════════════════════════════════════════
# C2｜未來 as_of ⇒ 無「過期 -N 天」
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("n", [-1, -3, -44, -9999])
def test_stale_text_never_prints_negative_days(n):
    s = T.stale_text(n)
    assert s == T.TEXT_STALE_UNKNOWN and not _NEG_DAYS_RX.search(s)


@pytest.mark.parametrize("n,expected", [(None, T.TEXT_STALE_UNKNOWN), (0, "⚠ 過期 0 天"), (1, "⚠ 過期 1 天"),
                                       (44, "⚠ 過期 44 天")])
def test_stale_text_normal_and_unknown_unchanged(n, expected):
    assert T.stale_text(n) == expected


@pytest.mark.parametrize("age", [-1, -44])
def test_trend_view_normalises_negative_age_to_unknown_and_stale(age):
    v = S.TwiiTrendView(ok=True, xs=("2026-11-10",), close=(1.0,), as_of="2026-11-10", is_stale=False,
                        stale_reason="資料日晚於今日", age_days=age)
    assert v.age_days is None            # ⛔ 不是 -N、⛔ 不是 0
    assert v.is_stale is True            # ⛔ 不是 fresh
    assert v.stale_reason == "資料日晚於今日" and v.as_of == "2026-11-10"      # 來源可追溯


def test_trend_view_negative_age_with_unknown_freshness_becomes_stale_not_ok():
    v = S.TwiiTrendView(ok=True, xs=("2026-11-10",), close=(1.0,), as_of="2026-11-10", is_stale=None, age_days=-2)
    assert v.is_stale is True and v.age_days is None


@pytest.mark.parametrize("age", [0, 1, 5, None])
def test_trend_view_nonnegative_age_untouched(age):
    v = S.TwiiTrendView(ok=True, xs=("2026-11-10",), close=(1.0,), as_of="2026-11-10", is_stale=False, age_days=age)
    assert v.age_days == age and v.is_stale is False


@pytest.mark.parametrize("ahead", [1, 2, 44])
@pytest.mark.parametrize("with_ohlc", [False, True])
def test_end_to_end_future_asof_is_stale_without_negative_days(real_l1, ahead, with_ohlc):
    asof = _TODAY + dt.timedelta(days=ahead)
    _write_twii(real_l1, _days(asof, 5), [22000.0 + i for i in range(5)])
    v = S.get_twii_trend_view(5, today=_TODAY, with_ohlc=with_ohlc)
    assert v.ok
    assert v.as_of == asof.isoformat()               # 來源可追溯：原始資料日照實保留
    assert v.age_days is None                        # ⛔ 不是 -N、⛔ 不是 0
    assert v.is_stale is True                        # ⛔ 不是 fresh
    assert "無法判定" in v.stale_reason              # L1 D2 的原因原樣轉述
    if with_ohlc:
        assert v.ohlc_ok is False and v.ohlc_error == OC.FUTURE_DATE     # 日 K 本來就拒用


@pytest.mark.parametrize("ahead", [1, 44])
def test_end_to_end_future_asof_through_ui2_card_has_no_negative_text(real_l1, ahead):
    asof = _TODAY + dt.timedelta(days=ahead)
    _write_twii(real_l1, _days(asof, 5), [22000.0 + i for i in range(5)])
    v = S.get_twii_trend_view(1, today=_TODAY)
    fact = TwiiFact(ok=v.ok, close=v.close, as_of=v.as_of, is_stale=v.is_stale, stale_reason=v.stale_reason,
                    age_days=v.age_days, has_upstream_error=False, error_type="", failed=v.failed, source=v.source,
                    upstream_state=v.upstream_state)
    spec = RC.twii_card_spec(_snap(fact))
    assert spec["state"] == "stale" and spec["stale_days"] is None
    shown = " ".join(str(x) for x in (spec["stale_days"], T.stale_text(spec["stale_days"]), spec["reason"]))
    assert not _NEG_DAYS_RX.search(shown)


def _snap(twii_fact):
    from shared import regime_arbiter as RA
    regime = RC.RegimeFact(regime="unknown", light="⬜", source=RA.SOURCE_UNLOADED, is_loaded=False)
    return RC.RealFeedSnapshot.of(twii_fact, "", regime, "")


@pytest.mark.parametrize("ahead", [1, 44])
def test_chart_a_chips_for_future_asof_have_no_negative_days(real_l1, ahead):
    from src.ui.views import _market_blocks as B
    asof = _TODAY + dt.timedelta(days=ahead)
    _write_twii(real_l1, _days(asof, 5), [22000.0 + i for i in range(5)])
    v = S.get_twii_trend_view(5, today=_TODAY)
    chips = B.chart_a_chips(v, today_date=_TODAY)
    kinds = [c.kind for c in chips]
    assert "stale" in kinds and "readable" not in kinds
    basis = B.basis_chart_a(v, None)
    assert not _NEG_DAYS_RX.search(repr(chips) + repr(basis))


@pytest.mark.parametrize("age", [-1, -44])
def test_ui2_contract_rejects_negative_age_fact(age):
    with pytest.raises(RealFeedContractError):
        RC.validate_twii_fact(_fact(is_stale=True, age_days=age))


def test_ui2_contract_rejects_negative_age_kbar_fact():
    k = TwiiKbarFact(ok=True, failed=False, error_type="", ohlc_ok=False, ohlc_reason=OC.FUTURE_DATE, xs=(), opens=(),
                     highs=(), lows=(), closes=(), as_of="2026-11-12", is_stale=True, age_days=-1, stale_reason="",
                     upstream_state="", has_upstream_error=False, source="s")
    with pytest.raises(RealFeedContractError):
        RC.validate_twii_kbar_fact(k)


# ── 正常 stale / 新鮮 / 日界線（今日由呼叫端注入；台北 vs UTC）────────────────────
def test_normal_stale_keeps_positive_days(real_l1):
    _write_twii(real_l1, _days(_TODAY - dt.timedelta(days=10), 5), [22000.0 + i for i in range(5)])
    v = S.get_twii_trend_view(1, today=_TODAY)
    assert v.is_stale is True and v.age_days == 10
    assert T.stale_text(v.age_days) == "⚠ 過期 10 天"


def test_fresh_yesterday_is_not_stale(real_l1):
    _write_twii(real_l1, _days(_TODAY - dt.timedelta(days=1), 5), [22000.0 + i for i in range(5)])
    v = S.get_twii_trend_view(1, today=_TODAY)
    assert v.is_stale is False and v.age_days == 1


def _taipei_utc_today(utc_instant: dt.datetime):
    return utc_instant.astimezone(OC.taipei_tz()).date(), utc_instant.astimezone(dt.timezone.utc).date()


@pytest.mark.parametrize("utc_instant,asof,expect_future", [
    # 台北 2026-11-11 23:59（UTC 15:59，兩地同一天）
    (dt.datetime(2026, 11, 11, 15, 59, tzinfo=dt.timezone.utc), dt.date(2026, 11, 11), False),
    (dt.datetime(2026, 11, 11, 15, 59, tzinfo=dt.timezone.utc), dt.date(2026, 11, 12), True),
    # 台北 2026-11-12 00:00（UTC 16:00；台北已過日界、UTC 還是 11-11）——以「台北今日」為基準
    (dt.datetime(2026, 11, 11, 16, 0, tzinfo=dt.timezone.utc), dt.date(2026, 11, 12), False),
    (dt.datetime(2026, 11, 11, 16, 0, tzinfo=dt.timezone.utc), dt.date(2026, 11, 11), False),
    (dt.datetime(2026, 11, 11, 16, 0, tzinfo=dt.timezone.utc), dt.date(2026, 11, 13), True),
    # UTC 日界 00:00（台北 08:00）
    (dt.datetime(2026, 11, 12, 0, 0, tzinfo=dt.timezone.utc), dt.date(2026, 11, 12), False),
    (dt.datetime(2026, 11, 12, 0, 0, tzinfo=dt.timezone.utc), dt.date(2026, 11, 13), True),
])
def test_day_boundary_with_taipei_today(real_l1, utc_instant, asof, expect_future):
    tpe_today, _utc_today = _taipei_utc_today(utc_instant)
    _write_twii(real_l1, _days(asof, 5), [22000.0 + i for i in range(5)])
    v = S.get_twii_trend_view(1, today=tpe_today)
    assert v.ok and v.as_of == asof.isoformat()
    if expect_future:
        assert v.age_days is None and v.is_stale is True
    else:
        assert v.age_days is not None and v.age_days >= 0
        assert v.age_days == (tpe_today - asof).days


def test_utc_clock_would_misjudge_taipei_dated_data_as_future_but_never_prints_negative(real_l1):
    """殘餘風險的鎖定測試：若基準日用 UTC 今日（台北已跨日、UTC 未跨日），台北日期的當日資料會被 L1 判成未來日。
    本修復不改基準日來源（不在 C2 範圍），但保證即使發生也只會是「⚠ 可能已過期」，不會出現負天數。"""
    utc_instant = dt.datetime(2026, 11, 11, 16, 0, tzinfo=dt.timezone.utc)
    _tpe, utc_today = _taipei_utc_today(utc_instant)
    _write_twii(real_l1, _days(dt.date(2026, 11, 12), 5), [22000.0 + i for i in range(5)])
    v = S.get_twii_trend_view(1, today=utc_today)
    assert v.age_days is None and v.is_stale is True


# ── as_of 缺失／不可解析 ─────────────────────────────────────────────
def test_missing_date_column_is_unreadable_not_fresh(real_l1):
    pd.DataFrame({"close": [1.0, 2.0]}).to_parquet(real_l1 / "twii_ohlcv.parquet")
    v = S.get_twii_trend_view(1, today=_TODAY)
    assert v.ok is False and v.is_stale is None and v.age_days is None


def test_unparseable_dates_are_unreadable_not_fresh(real_l1):
    pd.DataFrame({"date": ["not-a-date", "garbage"], "close": [1.0, 2.0]}).to_parquet(real_l1 / "twii_ohlcv.parquet")
    v = S.get_twii_trend_view(1, today=_TODAY)
    assert v.ok is False and v.is_stale is None and v.age_days is None
    assert not _NEG_DAYS_RX.search(repr(v))


def test_all_null_dates_judged_stale_by_l1_and_no_negative_days(real_l1):
    """日期欄全 NaT：L1 判不出年齡 → is_stale=True、age_days=None（§1 不假設新鮮）。"""
    pd.DataFrame({"date": pd.to_datetime([None, None]), "close": [1.0, 2.0]}).to_parquet(real_l1 / "twii_ohlcv.parquet")
    st_ = R.compute_cache_staleness("twii_ohlcv", cache_dir=real_l1, today=_TODAY)
    assert st_["is_stale"] is True and st_["age_days"] is None


def test_l1_keeps_negative_age_for_diagnostics(tmp_path):
    """C2 修復不動 L1：compute_cache_staleness 仍照實保留負 age_days 供診斷（既有 D2 契約，test_macro_cache_reader_future_asof）。"""
    _write_twii(tmp_path, _days(_TODAY + dt.timedelta(days=44), 3), [1.0, 2.0, 3.0])
    r = R.compute_cache_staleness("twii_ohlcv", cache_dir=tmp_path, today=_TODAY)
    assert r["is_stale"] is True and r["age_days"] == -44 and "無法判定" in (r["reason"] or "")
    assert math.isfinite(r["age_days"])
