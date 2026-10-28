"""XV-H3（客戶 2026-10-28 裁示 A）：外幣資產不得直接與 TWD 加總。

L0 `shared/asset_currency_gate.is_confirmed_twd_ticker`：只有能確定為台股者視為 TWD；其餘一律「幣別未確認」→ 排除。
排除後：不計入總市值／未實現損益合計／80/20；個別列損益%不可判定；只要有排除，總市值與配置比例處改顯示
`⬜ 部分外幣資產未納入，總市值／配置比例無法完整判定`，並列出未納入代號與原因。
涵蓋：dividend_station_service（列／totals／allocation／digest／prompt）、LINE、page_hold ①⑤⑥、
portfolio_deep_service（壓測／VaR 權重與總市值）。無網路（全部 stub）。
"""
from __future__ import annotations

import pandas as pd
import pytest

from shared import asset_currency_gate as FXG
from src.compute.notify import holdings_digest_message as M
from src.services import dividend_station_service as S

FX_TEXT = "⬜ 部分外幣資產未納入，總市值／配置比例無法完整判定"
REASON_LINE = "VOO、BND｜原因：外幣資產，匯率與成本幣別未定義"


# ── L0 ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("tk", ["2330", "0050", "00878", "00631L", "2881A", "006208",
                                "2330.TW", "5314.TWO", "00679b.two", " 0056 ", "VOO.TW"])
def test_confirmed_twd(tk):
    assert FXG.is_confirmed_twd_ticker(tk) is True


@pytest.mark.parametrize("tk", ["VOO", "BND", "^TWII", "00631l", "233", "1234567", "2330AB",
                                ".TW", "", "  ", None, 2330, "BRK.B"])
def test_unconfirmed_is_excluded(tk):
    assert FXG.is_confirmed_twd_ticker(tk) is False


def test_text_constants_verbatim():
    assert FXG.FX_PARTIAL_TEXT == FX_TEXT
    assert FXG.fx_excluded_text(["VOO", "BND", "VOO"]) == "未納入：" + REASON_LINE


@pytest.mark.parametrize("tk", ["２３３０", "٢٣٣٠", "２３３０.TW".replace(".TW", "")])
def test_non_ascii_digits_rejected(tk):
    """QA 回修：`\\d` 會收全形／非 ASCII 數字 → 改 `[0-9]`。"""
    assert FXG.is_confirmed_twd_ticker(tk) is False


def test_exclusion_reason_split():
    """QA 回修：明確外幣 vs 幣別未確認兩種原因。"""
    for tk in ("VOO", "BND", "BRK.B"):
        assert FXG.fx_exclusion_reason(tk) == FXG.FX_EXCLUDED_REASON
    for tk in ("50", "^TWII", "1234567", "00631l", ""):
        assert FXG.fx_exclusion_reason(tk) == FXG.FX_UNCONFIRMED_REASON == "幣別未確認"
    assert FXG.fx_excluded_text(["50", "VOO", "^TWII"]) == (
        "未納入：VOO｜原因：外幣資產，匯率與成本幣別未定義；50、^TWII｜原因：幣別未確認")
    assert FXG.fx_excluded_text(["50"]) == "未納入：50｜原因：幣別未確認"


# ── L3 dividend_station_service ─────────────────────────────────────
_WK = pd.Series([20.0 + i * 0.1 for i in range(60)],
                index=pd.date_range("2025-01-03", periods=60, freq="W-FRI"))


def _rows():
    def mf(tk, kind):
        if kind == "etf":
            return {"weekly_close": _WK, "current_price": {"0050": 180.0, "VOO": 550.0,
                                                           "BND": 72.0}[tk]}
        return {"mj_grade": "A", "kd_state": None, "current_price": 500.0}
    return S.build_station_rows(
        [{"ticker": "0050", "lots": 10, "avg_price": 150},
         {"ticker": "VOO", "lots": 10, "avg_price": 17000},
         {"ticker": "BND", "lots": 1, "avg_price": 2300},
         {"ticker": "2330", "lots": 1, "avg_price": 400}], vix=15.0, metrics_fn=mf)


def test_rows_flag_and_drop_value_pnl():
    r = {x["代號"]: x for x in _rows()}
    for tk in ("VOO", "BND"):
        assert r[tk][FXG.KEY_FX_UNCONFIRMED] is True
        assert r[tk]["市值"] is None and r[tk]["損益%"] is None
        assert r[tk]["現價"] is not None          # 原值照列，只是不加總、不算損益
    for tk in ("0050", "2330"):
        assert FXG.KEY_FX_UNCONFIRMED not in r[tk] and r[tk]["市值"] and r[tk]["損益%"] is not None


def test_totals_and_allocation_not_computed():
    rows = _rows()
    assert S.fx_excluded_codes(rows) == ["VOO", "BND"]
    assert S.compute_portfolio_totals(rows) is None
    assert S.compute_allocation_split(rows) is None
    tw = [x for x in rows if not x.get(FXG.KEY_FX_UNCONFIRMED)]
    assert S.compute_portfolio_totals(tw)["value_twd"] == pytest.approx((10 * 180 + 500) * 1000)


def test_watchlist_foreign_not_flagged():
    rows = S.build_station_rows([{"ticker": "VOO", "held": False}], vix=None,
                                metrics_fn=lambda tk, k: {"weekly_close": _WK, "current_price": 1.0})
    assert FXG.KEY_FX_UNCONFIRMED not in rows[0]


def test_digest_and_prompt_have_no_mixed_total():
    d = S.build_station_digest(_rows(), vix=15.0)
    assert d["fx_excluded"] == ["VOO", "BND"] and d["allocation"] is None
    p = S.build_summary_prompt(d)
    assert "實際配置" not in p
    assert ("- 未納入總市值與配置比例：VOO、BND｜原因：外幣資產，匯率與成本幣別未定義"
            "（總市值／配置比例無法完整判定）\n") in p


def test_tw_only_digest_unchanged_keys():
    rows = [x for x in _rows() if not x.get(FXG.KEY_FX_UNCONFIRMED)]
    d = S.build_station_digest(rows, vix=15.0)
    assert "fx_excluded" not in d and d["allocation"] is not None


def test_line_allocation_line():
    msg = M.format_holdings_message(S.build_station_digest(_rows(), vix=15.0), None, as_of="t")
    assert f"⚖️ 配置：{FX_TEXT}（未納入：{REASON_LINE}）" in msg
    assert "核心 " not in msg


# ── page_hold ① ⑤ ⑥ ─────────────────────────────────────────────────
def _station():
    import src.ui.views.page_hold as P
    rows = tuple(_rows())
    return P, P.StationReadout(requested=True, submitted=True, bound=True, holdings_n=4,
                               rows=rows, totals=None, split=None,
                               digest=S.build_station_digest(list(rows), vix=15.0))


def test_page_totals_facts():
    P, st = _station()
    facts = dict(P._totals_facts(st))
    assert facts["總市值／配置比例"] == FX_TEXT
    assert facts["未納入"] == REASON_LINE
    assert not any("總市值（元）" in k for k in facts)


@pytest.mark.parametrize("builder", ["build_allocation_split_card", "build_core_satellite_card"])
def test_page_split_cards(builder):
    P, st = _station()
    card, facts, sig = getattr(P, builder)(st)
    assert card.state != "live" and not card.value
    assert card.note.now == P.FX_PARTIAL_NOW == FX_TEXT.removeprefix("⬜ ")
    assert card.note.why == "未納入：" + REASON_LINE
    assert (P.FX_PARTIAL_FACT, FX_TEXT) in facts
    P.v2_short_rows(card)                     # 短句表有登記、摘錄對得上（否則 KeyError）
    assert "%" not in "".join(v for _k, v in facts if "比例" in _k and v != FX_TEXT)
    # QA 回修 #6：徽章用既有「不適用 · 重跑無效」（#8），⛔ 不是「缺漏 · 可重跑」。
    from shared.ui_state import UI_NOT_APPLICABLE
    assert card.state == UI_NOT_APPLICABLE
    html = P.v2_card_html(card, facts, sig)
    assert "重跑無效" in html and "可重跑" not in html.replace("重跑無效", "")


# ── portfolio_deep_service ───────────────────────────────────────────
def _deep_rows():
    return [{"代號": "0050", "held": True, "張數": 10.0, "均價": 150.0, "現價": 180.0, "_detail": {}},
            {"代號": "VOO", "held": True, "張數": 10.0, "均價": 17000.0, "現價": 550.0, "_detail": {}}]


def test_deep_priced_rows_exclude_foreign():
    import src.services.portfolio_deep_service as D
    assert [r["ticker"] for r in D.priced_rows(_deep_rows())] == ["0050.TW"]
    assert D._fx_excluded(_deep_rows()) == ("VOO",)


def test_deep_stress_weights_tw_only_and_flags(monkeypatch):
    import src.services.portfolio_deep_service as D
    import src.ui.views.page_hold as P
    seen = {}
    monkeypatch.setattr(D, "_yf_tickers", lambda w, failed=None: {t: t for t in w})

    def _fake(rows, total_value, drop_pct=None):
        seen["rows"], seen["total"] = rows, total_value
        return {"drop_pct": drop_pct, "total_loss": -10.0, "loss_pct": 1.0}
    monkeypatch.setattr("src.compute.etf.etf_calc.calc_portfolio_stress_test", _fake)
    res = D.get_portfolio_stress(_deep_rows())
    assert [r["ticker"] for r in seen["rows"]] == ["0050.TW"]
    assert seen["total"] == pytest.approx(10 * 1000 * 180.0)
    assert res.fx_excluded == ("VOO",) and res.reconciled is True
    bits = P._degraded_bits(res)
    assert bits and bits[-1][0].startswith("**" + P.FX_PARTIAL_NOW)
    deep = P.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                         has_station_rows=True, stress=res)
    card, facts, sig = P.build_stress_card(deep)
    assert card.state == "degraded" and sig == ""
    assert (P.FX_PARTIAL_FACT, FX_TEXT) in facts
    assert not any(k == "納入計算的組合總市值（元）" for k, _v in facts)
    P.v2_short_rows(card)


def test_page_split_card_unconfirmed_only_reason():
    """QA 回修：只有「幣別未確認」的列（例 `^TWII`）→ 原因句與短句表候選都對得上。"""
    import src.ui.views.page_hold as P
    rows = ({"代號": "^TWII", "種類": "ETF", "held": True, "現價": 1.0, "_detail": {},
             FXG.KEY_FX_UNCONFIRMED: True},)
    st = P.StationReadout(requested=True, submitted=True, bound=True, holdings_n=1,
                          rows=rows, totals=None, split=None)
    card, facts, _sig = P.build_allocation_split_card(st)
    assert card.note.why == "未納入：^TWII｜原因：幣別未確認"
    P.v2_short_rows(card)


def test_take_profit_foreign_satellite_is_unjudged():
    """QA 回修 #10：外幣衛星損益% None → 判不了，⛔ 不落到「沒有任何一檔達門檻（有效結果）」。"""
    import src.ui.views.page_hold as P
    from shared.ui_state import UI_NOT_APPLICABLE
    rows = ({"代號": "AAPL", "種類": "個股", "held": True, "現價": 200.0, "損益%": None,
             "_detail": {}, FXG.KEY_FX_UNCONFIRMED: True},
            {"代號": "2330", "種類": "個股", "held": True, "現價": 500.0, "損益%": 3.0, "_detail": {}})
    st = P.StationReadout(requested=True, submitted=True, bound=True, holdings_n=2, rows=rows,
                          take_profit=())
    card, facts, sig = P.build_take_profit_card(st)
    assert card.state == UI_NOT_APPLICABLE and card.note.now == P.TP_FAILED_NOW
    assert card.note.now != P.TP_EMPTY_NOW
    assert card.note.why == "未納入：AAPL｜原因：外幣資產，匯率與成本幣別未定義"
    P.v2_short_rows(card)
    P.v2_card_html(card, facts, sig)


# ── QA 回修 #5：壓測／VaR 外幣排除時的涵蓋範圍、標籤、全外幣 ─────────────────
def _stub_stress(monkeypatch):
    import src.services.portfolio_deep_service as D
    monkeypatch.setattr(D, "_yf_tickers", lambda w, failed=None: {t: t for t in w})
    monkeypatch.setattr("src.compute.etf.etf_calc.calc_portfolio_stress_test",
                        lambda rows, total_value, drop_pct=None:
                        {"drop_pct": drop_pct, "total_loss": -10.0, "loss_pct": 1.0})
    return D


def test_stress_coverage_counts_tw_only_and_names_fx(monkeypatch):
    import src.ui.views.page_hold as P
    D = _stub_stress(monkeypatch)
    res = D.get_portfolio_stress(_deep_rows())
    assert (res.valued_n, res.held_n) == (1, 1) and res.coverage_pct == pytest.approx(100.0)
    deep = P.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                         has_station_rows=True, stress=res)
    card, facts, _s = P.build_stress_card(deep)
    f = dict(facts)
    assert "缺張數" not in f["涵蓋範圍"]
    assert f["涵蓋範圍"] == ("1 檔台股持有列裡納入了 1 檔；另外 未納入：VOO｜原因：外幣資產，"
                          "匯率與成本幣別未定義 —— **不進分子也不進分母**")
    assert "現值（僅已納入台股部分，已失準，別照門檻讀）" in f
    assert not any("總市值（元）" in k for k in f)


def test_stress_and_var_all_foreign(monkeypatch):
    import src.ui.views.page_hold as P
    from shared.ui_state import UI_NOT_APPLICABLE
    D = _stub_stress(monkeypatch)
    rows = [_deep_rows()[1]]
    st, va = D.get_portfolio_stress(rows), D.get_portfolio_var(rows)
    for res in (st, va):
        assert res.reason == FXG.FX_ONLY_REASON and res.fx_excluded == ("VOO",)
    deep = P.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=1,
                         has_station_rows=True, stress=st, var=va)
    for card, facts, sig in (P.build_stress_card(deep), P.build_var_card(deep)):
        assert card.state == UI_NOT_APPLICABLE
        assert card.note.why == "未納入：VOO｜原因：外幣資產，匯率與成本幣別未定義"
        assert "張數" not in card.note.where and "均價" not in card.note.where
        P.v2_short_rows(card)
        P.v2_card_html(card, facts, sig)


def test_var_known_limit_text_is_truthful():
    import src.ui.views.page_hold as P
    deep = P.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=1,
                         has_station_rows=True)
    f = dict(P.build_var_card(deep)[1])
    assert f["已知限制"] == "外幣／幣別未確認的持股**不納入**本格（匯率與成本幣別未定義，不換算）"
