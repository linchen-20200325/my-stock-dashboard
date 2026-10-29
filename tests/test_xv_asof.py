"""XV-ASOF：價格旁的「資料時間＋來源」（客戶 2026-10-28 確認線框 Q1＝A、Q2＝A、Q3＝A，DEC-102）。

規格：`docs/vnext/NEWUI_D25_XVIEW_ASOF_WIREFRAME_2026-10-28.md`。無網路（L1 一律 stub）。
守的事：
- L0 字樣全狀態（正常／未確認／stale／fallback／ffill／拿不到），⛔ 不寫「收盤」、⛔ 不用今天代替；
- stale 判定只走 `expected_latest_trading_day()` ＋ freshness SSOT 上限（⛔ 不自創天數）；
- L3 非顯示鍵加性：現價與市值／損益% 一個數字都不變；
- UI：P1／P2 小字、P4 方案 A（多數／例外／無多數退回逐列）、💼 E17 與 ⑤ 指回一行。
"""
from __future__ import annotations

import datetime as dt
import types

import pandas as pd
import pytest

from shared import price_asof_label as PAL
from shared.freshness_policy import DAILY_MAX_LAG_TRADING_DAYS

WED = dt.date(2026, 10, 28)   # 週三
SAT = dt.date(2026, 10, 31)


def _p(as_of=WED, src=PAL.SRC_YAHOO_ADJ, *, today=WED, ff=False, ff_from=None) -> PAL.PriceAsOf:
    _stale, _exp, _lag = PAL.assess_price_freshness(as_of, today=today)
    return PAL.PriceAsOf(as_of=as_of, src=src, is_stale=_stale,
                         is_fallback=PAL.is_fallback_source(src), ffilled_last=ff,
                         ffilled_from=ff_from, expected_day=_exp, lag_weekdays=_lag)


# ══════════════════════════ L0：字樣全狀態 ══════════════════════════
class TestLabels:
    def test_normal_is_unconfirmed_never_close(self):
        _l = PAL.price_asof_label(_p())
        assert _l == "2026-10-28｜Yahoo（盤中或收盤未確認）"
        assert "收盤（" not in _l and not _l.endswith("收盤") and "盤中或收盤未確認" in _l

    def test_fallback_names_source_in_words(self):
        _l = PAL.price_asof_label(_p(dt.date(2026, 10, 27), PAL.SRC_FINMIND_SDK))
        assert _l == "2026-10-27｜備援來源：FinMind（盤中或收盤未確認）"
        assert PAL.price_asof_label(_p(WED, PAL.SRC_FINMIND_RAW)).count("備援來源：FinMind") == 1
        assert "備援來源：Yahoo（預設參數）" in PAL.price_asof_label(_p(WED, PAL.SRC_YAHOO_FALLBACK))

    def test_stale_has_text_mark(self):
        _l = PAL.price_asof_label(_p(dt.date(2026, 10, 20)))
        assert _l.startswith("⚠ 非最新（上次成功 2026-10-20；盤中或收盤未確認）｜Yahoo")

    def test_ffill_last(self):
        _l = PAL.price_asof_label(_p(ff=True, ff_from=dt.date(2026, 10, 27)))
        assert _l == "⚠ 含補值日（2026-10-28 沿用 2026-10-27；盤中或收盤未確認）｜Yahoo"
        assert "為補值" in PAL.price_asof_label(_p(ff=True))

    def test_missing_time_never_today(self):
        assert PAL.price_asof_label(None) == "資料時間：⬜ 未提供"
        assert PAL.price_asof_label(PAL.PriceAsOf()) == "資料時間：⬜ 未提供"
        assert PAL.price_asof_label(PAL.PriceAsOf.from_mapping({})) == "資料時間：⬜ 未提供"
        assert WED.isoformat() not in PAL.price_asof_label(PAL.PriceAsOf())

    def test_unknown_source_is_written_not_guessed(self):
        _l = PAL.price_asof_label(_p(WED, None))
        assert "來源：⬜ 未提供" in _l and "Yahoo" not in _l
        assert PAL.is_fallback_source("unknown") is None and PAL.is_fallback_source("") is None

    def test_meaning_survives_without_colour(self):
        """每個非正常狀態都靠文字（⚠／備援來源／⬜）可辨，不靠顏色。"""
        for _x in (_p(dt.date(2026, 10, 20)), _p(ff=True), _p(WED, PAL.SRC_FINMIND_SDK), None):
            _l = PAL.price_asof_label(_x)
            assert any(_m in _l for _m in ("⚠", "備援來源", "⬜"))


# ══════════════════════════ L0：stale 判定 ══════════════════════════
class TestFreshness:
    def test_uses_ssot_limit(self):
        # 週三：上限 3 個平日 → 前一週五（3 平日前）仍新鮮、前一週四（4）非最新
        assert PAL.assess_price_freshness(dt.date(2026, 10, 23), today=WED)[0] is False
        assert PAL.assess_price_freshness(dt.date(2026, 10, 22), today=WED)[0] is True
        assert DAILY_MAX_LAG_TRADING_DAYS == 3

    def test_expected_day_skips_weekend(self):
        _s, _exp, _lag = PAL.assess_price_freshness(dt.date(2026, 10, 30), today=SAT)
        assert (_s, _exp, _lag) == (False, dt.date(2026, 10, 30), 0)

    def test_unparseable_or_future_is_undetermined(self):
        assert PAL.assess_price_freshness(None, today=WED)[0] is None
        assert PAL.assess_price_freshness("2026-10-1", today=WED)[0] is None
        assert PAL.assess_price_freshness(dt.date(2026, 10, 29), today=WED)[0] is None


# ══════════════════════════ L0：分組（方案 A） ══════════════════════════
class TestGrouping:
    def test_majority_and_exceptions(self):
        _g = PAL.group_price_asof([("a", _p()), ("b", _p()), ("c", _p(dt.date(2026, 10, 20)))])
        assert _g.majority_label == PAL.price_asof_label(_p())
        assert [_k for _, _k in _g.exceptions] == [("c",)]

    def test_tie_or_all_different_has_no_majority(self):
        assert PAL.group_price_asof([("a", _p()), ("b", _p(dt.date(2026, 10, 20)))]).majority_label is None
        _g = PAL.group_price_asof([("a", _p()), ("b", _p(dt.date(2026, 10, 20))),
                                   ("c", _p(WED, PAL.SRC_FINMIND_SDK))])
        assert _g.majority_label is None and len(_g.exceptions) == 3

    def test_basis_facts_two_cells(self):
        _f = PAL.price_basis_facts(_p(WED, PAL.SRC_FINMIND_SDK))
        assert [_k for _k, _ in _f] == ["使用的資料（價格）", "資料日期（價格）"]
        assert "本次實際：備援來源：FinMind（原始價，試還原）" in _f[0][1]
        assert "盤中或收盤未確認" in _f[1][1]


# ══════════════════════════ L3：非顯示鍵 ══════════════════════════
@pytest.fixture
def _today(monkeypatch):
    import src.services.trading_calendar_service as TCS
    monkeypatch.setattr(TCS, "taipei_today", lambda now=None: WED)


def _stub_stock(monkeypatch, df):
    import src.data.core.data_loader as DL
    import src.data.core.financial_statements_fetcher as FS

    class _L:
        def get_combined_data(self, *_a, **_k):
            return df, "", "x"
    monkeypatch.setattr(DL, "StockDataLoader", _L)
    monkeypatch.setattr(FS, "fetch_financial_statements",
                        lambda *a, **k: {"error": "stub"})


def _stock_df(last=WED, src="yahoo_adj"):
    _d = [last - dt.timedelta(days=i) for i in range(30)][::-1]
    _df = pd.DataFrame({"date": _d, "close": [100.0 + i for i in range(30)],
                        "high": [101.0 + i for i in range(30)], "low": [99.0 + i for i in range(30)]})
    if src:
        _df.attrs["price_src"] = src
    return _df


class TestL3Keys:
    def test_stock_normal(self, monkeypatch, _today):
        from src.services import dividend_station_service as S
        _stub_stock(monkeypatch, _stock_df())
        _m = S.fetch_metrics("2330", "stock")
        assert _m["current_price"] == 129.0
        assert _m["price_as_of"] == WED and _m["price_src"] == "yahoo_adj"
        assert _m["is_stale"] is False and _m["is_fallback"] is False and _m["ffilled_last"] is False

    def test_stock_stale_and_fallback(self, monkeypatch, _today):
        from src.services import dividend_station_service as S
        _stub_stock(monkeypatch, _stock_df(dt.date(2026, 10, 20), "finmind_raw"))
        _m = S.fetch_metrics("2330", "stock")
        assert _m["is_stale"] is True and _m["is_fallback"] is True
        assert _m["price_lag_weekdays"] == 6

    def test_stock_missing_src_attr(self, monkeypatch, _today):
        from src.services import dividend_station_service as S
        _stub_stock(monkeypatch, _stock_df(src=None))
        _m = S.fetch_metrics("2330", "stock")
        assert _m["price_src"] is None and _m["is_fallback"] is None and _m["price_as_of"] == WED

    def test_stock_no_price_all_none(self, monkeypatch, _today):
        from src.services import dividend_station_service as S
        _stub_stock(monkeypatch, None)
        _m = S.fetch_metrics("2330", "stock")
        assert _m["current_price"] is None
        assert all(_m[_k] in (None, False) for _k in PAL.PRICE_ASOF_KEYS)

    def test_etf_ffill_last(self, monkeypatch, _today):
        import src.data.etf.etf_fetch as EF
        from src.services import dividend_station_service as S
        _idx = pd.bdate_range(end=pd.Timestamp(WED), periods=400)
        _px = pd.DataFrame({"Close": [50.0 + i * 0.01 for i in range(400)]}, index=_idx)
        _px.attrs[EF.PRICE_CLOSE_FFILLED_ATTR] = (_idx[-1].strftime("%Y-%m-%d"),)
        monkeypatch.setattr(EF, "fetch_etf_price", lambda *a, **k: _px)
        monkeypatch.setattr(EF, "fetch_etf_dividends", lambda *a, **k: pd.Series(dtype=float))
        monkeypatch.setattr(EF, "fetch_etf_info", lambda *a, **k: {})
        import src.services.etf_scoring_service as ES
        monkeypatch.setattr(ES, "ensure_etf_rf_injected", lambda: None)
        import src.compute.etf.etf_quality as EQ
        monkeypatch.setattr(EQ, "compute_etf_quality", lambda *_a: {})
        monkeypatch.setattr(S, "_fetch_peer_ranks", lambda *a, **k: None)
        _m = S.fetch_metrics("0050", "etf")
        assert _m["current_price"] == pytest.approx(53.99)
        assert _m["price_src"] == "yahoo_adj" and _m["is_fallback"] is False
        assert _m["ffilled_last"] is True and _m["ffilled_from"] == dt.date(2026, 10, 27)
        assert PAL.price_asof_label(PAL.PriceAsOf.from_mapping(_m)).startswith("⚠ 含補值日")

    def test_rows_carry_keys_numbers_unchanged(self):
        from src.services import dividend_station_service as S
        _base = {"mj_grade": "A", "kd_state": None, "current_price": 500.0}
        _extra = dict(_base, price_as_of=dt.date(2026, 10, 20), price_src="finmind_sdk",
                      is_stale=True, is_fallback=True)
        _h = [{"ticker": "2330", "lots": 1, "avg_price": 400}]
        _r0 = S.build_station_rows(_h, vix=None, metrics_fn=lambda *_a: _base)[0]
        _r1 = S.build_station_rows(_h, vix=None, metrics_fn=lambda *_a: _extra)[0]
        for _k in ("市值", "損益%", "現價", "建議動作"):
            assert _r0[_k] == _r1[_k]                   # 過期價照樣計入，只標示
        assert _r1["is_stale"] is True and _r1["price_src"] == "finmind_sdk"
        _skip = set(PAL.PRICE_ASOF_KEYS) | {S.KEY_WEEKLY_SERIES}   # 後者含 Series，另比
        assert {_k: _v for _k, _v in _r0.items() if _k not in _skip} == \
               {_k: _v for _k, _v in _r1.items() if _k not in _skip}


# ══════════════════════════ UI：🔬 ══════════════════════════
def _m(p: PAL.PriceAsOf) -> dict:
    return {"price_as_of": p.as_of, "price_src": p.src, "is_stale": p.is_stale,
            "is_fallback": p.is_fallback, "ffilled_last": p.ffilled_last}


class TestInspect:
    def test_health_card_line_and_basis(self):
        import src.ui.views.page_inspect as V
        _s = V.StockReadout(requested=True, score_pct=80.0, grade="A", name="台積電",
                            price=600.0, price_asof=_p())
        _c, _f, _ = V.build_health_card(_s)
        _d = dict(_f)
        assert _d[V.PRICE_ASOF_FACT_KEY] == "2026-10-28｜Yahoo（盤中或收盤未確認）"
        _keys = [_k for _k, _ in _f]
        assert _keys.index(V.PRICE_ASOF_FACT_KEY) == _keys.index("現價") + 1
        # 正常資料時，其餘既有 fact 一字不變
        _c0, _f0, _ = V.build_health_card(V.StockReadout(
            requested=True, score_pct=80.0, grade="A", name="台積電", price=600.0))
        _new = {V.PRICE_ASOF_FACT_KEY} | V.V2_FOLD_ONLY_FACT_KEYS
        assert [_x for _x in _f if _x[0] not in _new] == [_x for _x in _f0 if _x[0] not in _new]
        assert _c == _c0
        # 查看依據只進摺疊區
        _html = V.v2_card_html(_c, _f)
        assert "使用的資料（價格）" in _html

    def test_health_card_no_price_no_line(self):
        import src.ui.views.page_inspect as V
        _c, _f, _ = V.build_health_card(V.StockReadout(requested=True, score_pct=80.0))
        assert V.PRICE_ASOF_FACT_KEY not in dict(_f)

    def test_health_card_missing_time(self):
        import src.ui.views.page_inspect as V
        _f = dict(V.build_health_card(V.StockReadout(requested=True, price=600.0))[1])
        assert _f[V.PRICE_ASOF_FACT_KEY] == "資料時間：⬜ 未提供"

    def test_valuation_same_as_above(self):
        import src.ui.views.page_inspect as V
        _v = V.ValuationReadout(requested=True, price=600.0, price_asof=_p(dt.date(2026, 10, 20)))
        _f = dict(V.build_valuation_card(_v)[1])
        assert _f[V.PRICE_ASOF_FACT_KEY].startswith("同上：⚠ 非最新")
        assert V.PRICE_ASOF_FACT_KEY not in dict(V.build_valuation_card(
            V.ValuationReadout(requested=True))[1])

    def test_load_stock_readout_carries_asof(self, monkeypatch):
        import src.ui.views.page_inspect as V
        _pp = _p()
        monkeypatch.setattr(V, "_fetch_metrics", lambda *a, **k: (
            {"current_price": 600.0, "mj_score_pct": 80.0, **_m(_pp)}, ""))
        _s = V.load_stock_readout(types.SimpleNamespace(requested=True, is_stock=True,
                                                        code="2330", kind="stock"))
        assert _s.price_asof.as_of == WED and _s.price_asof.src == "yahoo_adj"


def _brow(code, p, *, ok=True):
    import src.ui.views.page_inspect as V
    return V.BatchRow(code=code, kind="stock", kind_label="個股", is_stock=True,
                      metrics=(("名稱", "x"), ("現價", "1.00")),
                      error="" if ok else "boom", price_asof=p)


class TestBatchPlanA:
    def test_majority_header_only_exceptions_tagged(self):
        import src.ui.views.page_inspect as V
        _rows = (_brow("2330", _p()), _brow("2317", _p()),
                 _brow("2454", _p(dt.date(2026, 10, 20))), _brow("9999", None, ok=False))
        _v = V.batch_price_asof_view(_rows)
        assert _v.header == ("價格資料時間：2026-10-28｜Yahoo（盤中或收盤未確認）"
                             + V.BATCH_ASOF_EXCEPTION_TAIL)
        assert _v.suffix[0] == _v.suffix[1] == "" and _v.suffix[3] == ""
        assert _v.suffix[2].startswith("（⚠ 非最新")
        _d = dict(V.batch_detail_metrics(_rows[2], _v.suffix[2]))
        assert _d["現價"].startswith("1.00（⚠ 非最新") and _d["名稱"] == "x"
        assert V.batch_detail_metrics(_rows[0], "") == _rows[0].metrics   # 正常列明細一字不變

    def test_all_same_no_exception_tail(self):
        import src.ui.views.page_inspect as V
        _v = V.batch_price_asof_view((_brow("a", _p()), _brow("b", _p())))
        assert _v.header == "價格資料時間：2026-10-28｜Yahoo（盤中或收盤未確認）"
        assert _v.suffix == ("", "")

    def test_no_majority_falls_back_to_per_row(self):
        import src.ui.views.page_inspect as V
        _v = V.batch_price_asof_view((_brow("a", _p()), _brow("b", _p(dt.date(2026, 10, 20)))))
        assert _v.header == V.BATCH_ASOF_NO_MAJORITY
        assert all(_s.startswith("（") for _s in _v.suffix)

    def test_no_priced_rows_no_header(self):
        import src.ui.views.page_inspect as V
        _v = V.batch_price_asof_view((_brow("a", None),))
        assert _v.header == "" and _v.suffix == ("",)


# ══════════════════════════ UI：💼 ══════════════════════════
def _hrow(code, p, *, kind="個股", price=100.0, held=True):
    _r = {"代號": code, "種類": kind, "held": held, "現價": price, "_detail": {}}
    _r.update(_m(p) if p is not None else {})
    return _r


class TestHold:
    def _st(self, rows):
        import src.ui.views.page_hold as H
        return H.StationReadout(requested=True, submitted=True, rows=tuple(rows))

    def test_e17_majority_and_named_exceptions(self):
        import src.ui.views.page_hold as H
        _st = self._st([_hrow("0050", _p(), kind="ETF"), _hrow("2330", _p()),
                        _hrow("2454", _p(dt.date(2026, 10, 20))),
                        _hrow("00878", _p(), held=False)])
        _f = H._price_asof_facts(_st)
        assert _f[0] == ("價格資料時間", "2026-10-28｜Yahoo（盤中或收盤未確認）（2 檔）")
        assert _f[1][0] == "價格資料時間 · 另 1 檔" and _f[1][1].endswith("：2454")
        _tp = dict(H._take_profit_asof_fact(_st))[H.TP_ASOF_FACT_KEY]
        assert _tp == H.TP_ASOF_POINTER + "（⚠ 非最新的 1 檔已點名）"

    def test_e17_not_provided(self):
        import src.ui.views.page_hold as H
        assert H._price_asof_facts(self._st([_hrow("2330", None, price=None)])) == \
            [("價格資料時間", "⬜ 未提供")]
        assert H._price_asof_facts(self._st([_hrow("2330", None)]))[0][1].startswith(
            "資料時間：⬜ 未提供")

    def test_idle_no_line(self):
        import src.ui.views.page_hold as H
        assert H._price_asof_facts(self._st([])) == []
        assert H._take_profit_asof_fact(self._st([])) == []

    def test_action_card_e17_after_total(self):
        import src.ui.views.page_hold as H
        _st = H.StationReadout(requested=True, submitted=True,
                               rows=(_hrow("2330", _p()),),
                               totals={"pnl_twd": 10, "pnl_pct": 1.0, "value_twd": 100})
        _keys = [_k for _k, _ in H.build_action_card(_st)[1]]
        assert _keys.index("價格資料時間") == _keys.index("總市值（元）") + 1
        _tpk = [_k for _k, _ in H.build_take_profit_card(_st)[1]]
        assert H.TP_ASOF_FACT_KEY in _tpk
