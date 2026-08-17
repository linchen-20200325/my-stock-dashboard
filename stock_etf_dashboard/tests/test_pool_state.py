"""L2 雙池單向狀態機：轉移守衛、置信度鎖定、帳本、出場訊號。"""
import pytest

from stock_etf_dashboard.core import constants as C
from stock_etf_dashboard.core.circuit_breaker import FailLoudError
from stock_etf_dashboard.repositories.sheets_repo import InMemoryStore
from stock_etf_dashboard.services import pool_state_service as ps


def _fresh():
    store = InMemoryStore()
    return store, ps.PoolStateService(store)


# ── 單向轉移 ────────────────────────────────────────────────────────────
def test_add_then_buy_moves_to_portfolio():
    store, svc = _fresh()
    svc.add_to_watchlist("2330.TW", name="台積電")
    assert svc.state_of("2330.TW") == C.STATE_WATCHLIST
    r = svc.confirm_buy("2330.TW", lots=2, price=900, confidence_score=85)
    assert r.from_state == C.STATE_WATCHLIST and r.to_state == C.STATE_PORTFOLIO
    assert svc.state_of("2330.TW") == C.STATE_PORTFOLIO
    assert store.get_watchlist("2330.TW") is None   # 已移出觀察池


def test_buy_not_in_watchlist_refused():
    _, svc = _fresh()
    with pytest.raises(FailLoudError, match="不在觀察池"):
        svc.confirm_buy("2317.TW", lots=1, price=100, confidence_score=90)


def test_buy_locked_when_confidence_below_threshold():
    _, svc = _fresh()
    svc.add_to_watchlist("2330.TW")
    with pytest.raises(FailLoudError, match="鎖定"):
        svc.confirm_buy("2330.TW", lots=1, price=900,
                        confidence_score=C.CONFIDENCE_LOCK_THRESHOLD - 1)


def test_buy_boundary_confidence_exactly_threshold_ok():
    _, svc = _fresh()
    svc.add_to_watchlist("2330.TW")
    r = svc.confirm_buy("2330.TW", lots=1, price=900,
                        confidence_score=C.CONFIDENCE_LOCK_THRESHOLD)
    assert r.ok is True


def test_sell_partial_stays_in_portfolio():
    _, svc = _fresh()
    svc.add_to_watchlist("2330.TW")
    svc.confirm_buy("2330.TW", lots=3, price=900, confidence_score=85)
    r = svc.confirm_sell("2330.TW", lots=1, price=950)
    assert r.to_state == C.STATE_PORTFOLIO
    assert svc.state_of("2330.TW") == C.STATE_PORTFOLIO


def test_sell_full_back_to_watchlist():
    _, svc = _fresh()
    svc.add_to_watchlist("2330.TW")
    svc.confirm_buy("2330.TW", lots=2, price=900, confidence_score=85)
    r = svc.confirm_sell("2330.TW", lots=2, price=950, back_to_watchlist=True)
    assert r.to_state == C.STATE_WATCHLIST
    assert svc.state_of("2330.TW") == C.STATE_WATCHLIST


def test_sell_full_exit_when_not_back():
    _, svc = _fresh()
    svc.add_to_watchlist("2330.TW")
    svc.confirm_buy("2330.TW", lots=2, price=900, confidence_score=85)
    r = svc.confirm_sell("2330.TW", lots=2, price=950, back_to_watchlist=False)
    assert r.to_state == C.STATE_EXITED
    assert svc.state_of("2330.TW") == C.STATE_EXITED


def test_sell_more_than_held_refused():
    _, svc = _fresh()
    svc.add_to_watchlist("2330.TW")
    svc.confirm_buy("2330.TW", lots=2, price=900, confidence_score=85)
    with pytest.raises(FailLoudError, match="持有"):
        svc.confirm_sell("2330.TW", lots=5, price=950)


def test_sell_not_in_portfolio_refused():
    _, svc = _fresh()
    with pytest.raises(FailLoudError, match="不在持股"):
        svc.confirm_sell("9999.TW", lots=1, price=10)


def test_ledger_records_each_transition():
    store, svc = _fresh()
    svc.add_to_watchlist("2330.TW")
    svc.confirm_buy("2330.TW", lots=2, price=900, confidence_score=85)
    svc.confirm_sell("2330.TW", lots=1, price=950)
    svc.confirm_sell("2330.TW", lots=1, price=960)
    led = store.list_ledgers()
    assert len(led) == 3
    assert [x["action"] for x in led] == [C.LEDGER_ACTION_BUY,
                                          C.LEDGER_ACTION_SELL, C.LEDGER_ACTION_SELL]


# ── 出場訊號 + 除權息防呆整合 ───────────────────────────────────────────
def test_check_exit_take_profit():
    sig = ps.check_exit(avg_price=100, high_watermark=130,
                        trailing_stop_pct=8, take_profit_pct=20,
                        prev_close=119, today_open=120, today_low=118,
                        today_high=121)
    assert sig.take_triggered is True   # high 121 >= 100*1.2=120


def test_check_exit_ex_dividend_not_false_triggered():
    # 除息跳空但還原後未破停損 → 不觸損
    sig = ps.check_exit(avg_price=100, high_watermark=110,
                        trailing_stop_pct=8, take_profit_pct=50,
                        prev_close=110, today_open=104, today_low=101,
                        today_high=105, dividend_amount=6)
    # 停損線 110*0.92=101.2；還原低點 101+6=107 > 101.2 → 不觸
    assert sig.guard.is_ex_dividend is True
    assert sig.stop_triggered is False
