"""「💼 我的持股」P1a 後續三項守衛（Q1-r4-f1／P1a-f1／P1a-f2／P1a-f3）。

每一條都以「修前行為會紅」為準（突變驗證見交付報告）。
"""
from __future__ import annotations

import pytest

from shared.ui_state import UI_FAILED
from src.ui.views import page_hold as P

_E = "RuntimeError('boom')"


def _station_holdings_failed() -> P.StationReadout:
    return P.load_station(P.HoldingsReadout(requested=True, submitted=True, error=_E))


# ── Q1-r4-f1：換股／壓測／VaR／配息卡 ⇒ 持股讀不到時出處寫持股清單 ─────────────────
class TestQ1r4f1DeepAndSwitchNameHoldings:
    def test_switch_carries_and_names_holdings(self):
        st = _station_holdings_failed()
        sw = P.load_switch(st, P.MacroReadout(requested=True),
                           P.HoldingsReadout(requested=True, submitted=True, error=_E))
        assert sw.error_src == P.SRC_HOLDINGS
        card = P.build_switch_card(sw, st)[0]
        assert card.state == UI_FAILED
        assert card.note.why.startswith(P.SRC_HOLDINGS), card.note.why
        assert P.v2_short_rows(card)[0]

    @pytest.mark.parametrize("build", [
        P.build_stress_card, P.build_var_card, P.build_dividend_cash_card])
    def test_deep_cards_name_holdings(self, build):
        deep = P.load_deep(_station_holdings_failed())
        assert deep.error_src == P.SRC_HOLDINGS
        card = build(deep)[0]
        assert card.state == UI_FAILED
        assert card.note.why.startswith(P.SRC_HOLDINGS), card.note.why
        assert P.v2_short_rows(card)[0]

    def test_switch_own_error_still_names_switch(self):
        sw = P.SwitchReadout(requested=True, submitted=True, error=_E)
        st = P.StationReadout(requested=True, submitted=True)
        assert P.build_switch_card(sw, st)[0].note.why.startswith(P.SRC_SWITCH)

    def test_deep_own_error_still_names_own_source(self):
        deep = P.DeepReadout(requested=True, submitted=True, has_station_rows=True,
                             var_error=_E, error_src=P.SRC_HOLDINGS)
        assert P.build_var_card(deep)[0].note.why.startswith(P.SRC_VAR)


# ── P1a-f1：AI 卡 now ⇒ 持股讀不到時 ⛔ 不說「上游的戰情表這一輪就壞了」 ────────────
class TestP1af1AiNowOnHoldingsError:
    def test_holdings_error_uses_preview_now(self):
        st = _station_holdings_failed()
        ai = P.load_ai_summary(True, st, P.SwitchReadout(requested=True, error=st.error))
        card = P.build_ai_summary_card(ai, st)[0]
        assert card.note.now == P.PREVIEW_FAILED_NOW
        assert "戰情表這一輪就壞了" not in card.note.now
        assert P.v2_short_rows(card)[0]

    def test_station_own_error_keeps_upstream_now(self):
        st = P.StationReadout(requested=True, submitted=True, error=_E)
        ai = P.load_ai_summary(True, st, P.SwitchReadout(requested=True, error=_E))
        card = P.build_ai_summary_card(ai, st)[0]
        assert card.note.now == P.AI_UPSTREAM_NOW
        assert P.v2_short_rows(card)[0]


# ── P1a-f2／P1a-f3：金額只涵蓋一部分那一列 ──────────────────────────────────
def _row(code, lots, avg, cur):
    return {"代號": code, "held": True, "張數": lots, "均價": avg, "現價": cur}


def _partial_value(rows, held_n, valued_n) -> str:
    st = P.StationReadout(
        requested=True, submitted=True, bound=True, holdings_n=len(rows), rows=tuple(rows),
        totals={"pnl_twd": 1.0, "pnl_pct": 1.0, "value_twd": 10.0,
                "held_n": held_n, "valued_n": valued_n, "partial": True})
    return dict(P._totals_facts(st))["⚠️ 上面兩個金額只涵蓋一部分"]


class TestP1af2DuplicateCodesListedOnce:
    def test_duplicate_listed_once(self):
        rows = [_row("0050", 1, 100.0, 110.0), _row("2330", None, 500.0, 600.0),
                _row("2330", 1, None, 600.0)]
        v = _partial_value(rows, 3, 1)
        assert v.endswith("；沒有納入：2330"), v

    def test_count_guard_uses_raw_list(self):
        # 原清單 2 列（去重後 1 個代號）；L3 說缺 1 檔 ⇒ 對不上 ⇒ 不列（⛔ 拿去重後的長度核對）。
        rows = [_row("0050", 1, 100.0, 110.0), _row("2330", None, 500.0, 600.0),
                _row("2330", 1, None, 600.0)]
        assert "沒有納入：" not in _partial_value(rows, 2, 1)


class TestP1af3PriceOnlyMissingNamedAccurately:
    def test_sentence_names_all_three(self):
        rows = [_row("0050", 1, 100.0, 110.0), _row("2330", 1, 500.0, None)]
        v = _partial_value(rows, 2, 1)
        assert v.startswith("1/2 檔持股缺張數／均價／現價，**沒有**納入"), v
        assert "缺張數或均價" not in v
