"""「💼 我的持股」P1a 四項守衛（Q1-r4／Q3-r6／Q4-r2／SEC-r4①）。

一條測試對應一種說謊方式；每一條都以「修前行為會紅」為準（突變驗證見交付報告）。
"""
from __future__ import annotations

import pytest

from shared.ui_state import UI_DEGRADED, UI_EMPTY, UI_FAILED
from src.ui.views import page_hold as P

_E = "RuntimeError('boom')"


def _var_res(**kw):
    from src.services.portfolio_deep_service import VarResult

    base = dict(computed=True, hist_95_twd=16817.0, hist_99_twd=25000.0,
                param_95_twd=16000.0, param_99_twd=24000.0, monthly_99_twd=95000.0,
                monthly_99_pct=8.63, warn_pct=10.0, total_value_twd=1_100_000.0,
                n_common=119, n_union=120, first_day="2025-01-02",
                last_day="2025-06-17", valued_n=2, held_n=2)
    base.update(kw)
    return VarResult(**base)


def _holdings_failed() -> P.HoldingsReadout:
    return P.HoldingsReadout(requested=True, submitted=True, error=_E)


# ── Q1-r4：持股讀不到 ⇒ 戰情表家族的卡把出處寫成持股清單，⛔ 不寫戰情表 ──────────────
class TestQ1r4HoldingsErrorIsBlamedOnHoldings:
    def _station(self) -> P.StationReadout:
        return P.load_station(_holdings_failed())

    def test_station_carries_holdings_source(self):
        assert self._station().error_src == P.SRC_HOLDINGS

    @pytest.mark.parametrize("build", [
        P.build_action_card, P.build_confidence_card, P.build_todo_card,
        P.build_lightwall_card, P.build_allocation_split_card,
        P.build_take_profit_card])
    def test_station_cards_name_holdings(self, build):
        card = build(self._station())[0]
        assert card.state == UI_FAILED
        assert card.note.why.startswith(P.SRC_HOLDINGS), card.note.why
        assert P.SRC_STATION not in card.note.why

    def test_ai_upstream_names_holdings(self):
        st = self._station()
        ai = P.load_ai_summary(True, st, P.SwitchReadout(requested=True, error=st.error))
        card = P.build_ai_summary_card(ai, st)[0]
        assert card.note.why.startswith(P.SRC_HOLDINGS), card.note.why

    def test_station_own_error_still_names_station(self):
        st = P.StationReadout(requested=True, submitted=True, error=_E)
        card = P.build_action_card(st)[0]
        assert card.note.why.startswith(P.SRC_STATION)

    @pytest.mark.parametrize("build", [
        P.build_action_card, P.build_lightwall_card, P.build_allocation_split_card,
        P.build_take_profit_card])
    def test_v2_short_rows_still_resolve(self, build):
        # 出處換了，v2 卡面的原文摘錄仍要對得上（否則渲染當下轉紅卡）。
        card = build(self._station())[0]
        short, _full = P.v2_short_rows(card)
        assert short


# ── Q3-r6：灰卡 ⛔ 不寫「判『已失準』（橘）」────────────────────────────────
class TestQ3r6NoOrangeVerdictOnGrayCard:
    def _deep(self, res) -> P.DeepReadout:
        return P.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                             has_station_rows=True, var=res)

    def test_gray_var_with_reconcile_gap_has_no_orange_row(self):
        res = _var_res(computed=False, reason="共同交易日不足一個月，樣本太短的尾部估計會過度樂觀", reconciled=False,
                       reference_value_twd=1_000_000.0)
        card, facts, _ = P.build_var_card(self._deep(res))
        assert card.state == UI_EMPTY
        assert not any("已失準」（橘）" in v for _k, v in facts), facts

    def test_gray_stress_with_reconcile_gap_has_no_orange_row(self):
        # 真實 L3 下壓測灰卡時 reconciled 恆為 True；這裡直接造出組合，守住呼叫點的 `red=`。
        from src.services.portfolio_deep_service import StressResult

        res = StressResult(computed=False, reason="沒有任何一列同時有張數與現價",
                           valued_n=0, held_n=2, reconciled=False,
                           reference_value_twd=1_000_000.0)
        deep = P.DeepReadout(requested=True, submitted=True, bound=True, holdings_n=2,
                             has_station_rows=True, stress=res)
        card, facts, _ = P.build_stress_card(deep)
        assert card.state == UI_EMPTY
        assert not any("已失準」（橘）" in v for _k, v in facts), facts

    def test_degraded_var_still_has_orange_row(self):
        res = _var_res(reconciled=False, reference_value_twd=1_000_000.0)
        card, facts, _ = P.build_var_card(self._deep(res))
        assert card.state == UI_DEGRADED
        assert any("已失準」（橘）" in v for _k, v in facts)


# ── Q4-r2：金額只涵蓋一部分時，缺的那幾檔要列出代號 ─────────────────────────
class TestQ4r2ListUncountedCodes:
    @staticmethod
    def _row(code, lots, avg, cur, held=True):
        return {"代號": code, "held": held, "張數": lots, "均價": avg, "現價": cur}

    def _station(self, rows, held_n, valued_n) -> P.StationReadout:
        return P.StationReadout(
            requested=True, submitted=True, bound=True, holdings_n=len(rows),
            rows=tuple(rows),
            totals={"pnl_twd": 1.0, "pnl_pct": 1.0, "value_twd": 10.0,
                    "held_n": held_n, "valued_n": valued_n, "partial": True})

    def test_codes_listed(self):
        rows = [self._row("0050", 1, 100.0, 110.0), self._row("2330", None, 500.0, 600.0),
                self._row("00878", 2, None, 20.0), self._row("2317", None, None, None, held=False)]
        facts = dict(P._totals_facts(self._station(rows, 3, 1)))
        v = facts["⚠️ 上面兩個金額只涵蓋一部分"]
        assert v.endswith("；沒有納入：2330、00878"), v

    def test_count_mismatch_lists_nothing(self):
        # 列上反推出的檔數與 L3 的 `held_n - valued_n` 對不上 ⇒ 不列（⛔ 不給矛盾清單）。
        rows = [self._row("0050", 1, 100.0, 110.0), self._row("2330", None, 500.0, 600.0)]
        v = dict(P._totals_facts(self._station(rows, 3, 1)))["⚠️ 上面兩個金額只涵蓋一部分"]
        assert "沒有納入：" not in v


# ── SEC-r4①：綁定／持股讀取失敗時，伺服器 log 也 ⛔ 不印 secrets 原文 ────────────
_SECRET = "GOCSPX-abcdefghijklmnopqrstuvwx"


class TestSecR4LogScrubbed:
    def test_load_holdings_log(self, monkeypatch, capsys):
        import src.services.holdings_service as H

        def _boom(**_kw):
            raise ValueError(f"client_secret = \"{_SECRET}\"")
        monkeypatch.setattr(H, "get_holdings", _boom)
        r = P.load_holdings(P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING))
        assert r.error
        assert _SECRET not in capsys.readouterr().out

    def test_load_binding_exception_log(self, monkeypatch, capsys):
        import src.services.portfolio_binding_service as B

        def _boom():
            raise ValueError(f"client_secret = \"{_SECRET}\"")
        monkeypatch.setattr(B, "get_binding_state", _boom)
        r = P.load_binding(P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING))
        assert r.error
        assert _SECRET not in capsys.readouterr().out

    def test_load_binding_read_error_log(self, monkeypatch, capsys):
        import types

        import src.services.portfolio_binding_service as B
        monkeypatch.setattr(B, "get_binding_state", lambda: types.SimpleNamespace(
            status=B.STATUS_UNBOUND, portfolio_count=None,
            read_error=f"ValueError('client_secret = \"{_SECRET}\"')"))
        r = P.load_binding(P.HoldRequest(submitted=True, mode=P.SCOPE_WITH_BINDING))
        assert r.error
        assert _SECRET not in capsys.readouterr().out
