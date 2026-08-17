"""L2 Service — 左右雙池單向狀態機。

狀態：觀察池(WATCHLIST) → 持股組合(PORTFOLIO) → 出場(EXITED)/退回觀察池。
單向規則（§4.1）：
- 買入只能「從觀察池」進持股（進場訊號確認）；不在觀察池 → 拒絕（先加觀察）。
- 賣出只能「從持股」出場；可全出(EXITED)或退回觀察池。
- 置信度 < 門檻 → 鎖定,拒絕買入（§4.6 confidence gate）。
每次轉移寫交易帳本(ledger,append-only)。依賴 PoolStore 介面（正式/離線同碼）。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core import constants as C
from ..core.circuit_breaker import (ExDividendGuard, ex_dividend_guard,
                                    isclose, require)
from ..repositories.sheets_repo import PoolStore


@dataclass(frozen=True)
class TransitionResult:
    ok: bool
    action: str
    ticker: str
    from_state: str
    to_state: str
    message: str


class PoolStateService:
    def __init__(self, store: PoolStore) -> None:
        self._store = store

    # ── 查詢 ────────────────────────────────────────────────────────────
    def state_of(self, ticker: str) -> str:
        if self._store.get_holding(ticker) is not None:
            return C.STATE_PORTFOLIO
        if self._store.get_watchlist(ticker) is not None:
            return C.STATE_WATCHLIST
        return C.STATE_EXITED

    # ── 進觀察池 ────────────────────────────────────────────────────────
    def add_to_watchlist(self, ticker: str, *, name: str = "", note: str = "") -> TransitionResult:
        require(self._store.get_holding(ticker) is None,
                f"{ticker} 已在持股組合,不需加入觀察池")
        self._store.add_watchlist({"ticker": ticker, "name": name, "note": note})
        return TransitionResult(True, "ADD_WATCH", ticker, C.STATE_EXITED,
                                C.STATE_WATCHLIST, f"{ticker} 已加入觀察池")

    # ── 確認買入：觀察池 → 持股 ─────────────────────────────────────────
    def confirm_buy(
        self, ticker: str, *, lots: float, price: float, confidence_score: float,
        reason: str = "進場訊號確認",
        trailing_stop_pct: float = C.DEFAULT_TRAILING_STOP_PCT,
        take_profit_pct: float = C.DEFAULT_TAKE_PROFIT_PCT,
    ) -> TransitionResult:
        require(lots > 0, f"買入張數必須 > 0,得到 {lots}")
        require(price > 0, f"買入價必須 > 0,得到 {price}")
        # 單向守衛：必須先在觀察池
        require(self._store.get_watchlist(ticker) is not None,
                f"{ticker} 不在觀察池,不可直接買入（請先加入觀察池確認訊號）")
        require(self._store.get_holding(ticker) is None,
                f"{ticker} 已在持股組合（加碼請走另案,不走單向進場）")
        # 置信度鎖定
        require(confidence_score >= C.CONFIDENCE_LOCK_THRESHOLD,
                f"置信度 {confidence_score:.0f} < {C.CONFIDENCE_LOCK_THRESHOLD:.0f},"
                f"建議已鎖定,不可買入")

        existing = self._store.get_watchlist(ticker) or {}
        self._store.upsert_holding({
            "ticker": ticker, "name": existing.get("name", ""),
            "lots": lots, "avg_price": price,
            "trailing_stop_pct": trailing_stop_pct,
            "take_profit_pct": take_profit_pct,
        })
        self._store.remove_watchlist(ticker)
        self._store.append_ledger({
            "ticker": ticker, "action": C.LEDGER_ACTION_BUY,
            "lots": lots, "price": price, "reason": reason,
        })
        return TransitionResult(True, C.LEDGER_ACTION_BUY, ticker,
                                C.STATE_WATCHLIST, C.STATE_PORTFOLIO,
                                f"{ticker} 買入 {lots} 張 @ {price}")

    # ── 確認賣出：持股 → 出場 / 退回觀察池 ──────────────────────────────
    def confirm_sell(
        self, ticker: str, *, lots: float, price: float,
        reason: str = "觸及停損停利", back_to_watchlist: bool = True,
    ) -> TransitionResult:
        require(price > 0, f"賣出價必須 > 0,得到 {price}")
        require(lots > 0, f"賣出張數必須 > 0,得到 {lots}")
        holding = self._store.get_holding(ticker)
        require(holding is not None, f"{ticker} 不在持股組合,無法賣出")
        held_lots = float(holding.get("lots", 0))
        require(lots <= held_lots + 1e-9,
                f"賣出 {lots} 張 > 持有 {held_lots} 張")

        self._store.append_ledger({
            "ticker": ticker, "action": C.LEDGER_ACTION_SELL,
            "lots": lots, "price": price, "reason": reason,
        })
        remaining = held_lots - lots
        if remaining <= 1e-9 or isclose(remaining, 0.0):
            # 全數出場
            self._store.remove_holding(ticker)
            if back_to_watchlist:
                self._store.add_watchlist({
                    "ticker": ticker, "name": holding.get("name", ""),
                    "note": f"出場後回觀察（{reason}）"})
                to = C.STATE_WATCHLIST
                msg = f"{ticker} 全數賣出,退回觀察池"
            else:
                to = C.STATE_EXITED
                msg = f"{ticker} 全數賣出,移出（已出場）"
            return TransitionResult(True, C.LEDGER_ACTION_SELL, ticker,
                                    C.STATE_PORTFOLIO, to, msg)
        # 部分減碼,仍在持股
        self._store.upsert_holding({**holding, "lots": remaining})
        return TransitionResult(True, C.LEDGER_ACTION_SELL, ticker,
                                C.STATE_PORTFOLIO, C.STATE_PORTFOLIO,
                                f"{ticker} 減碼 {lots} 張,剩 {remaining} 張")


# ── 出場訊號（純函式,含除權息防呆）─────────────────────────────────────
@dataclass(frozen=True)
class ExitSignal:
    stop_triggered: bool
    take_triggered: bool
    stop_price: float
    take_price: float
    guard: ExDividendGuard
    suggestion: str


def check_exit(
    *, avg_price: float, high_watermark: float,
    trailing_stop_pct: float, take_profit_pct: float,
    prev_close: float, today_open: float, today_low: float, today_high: float,
    dividend_amount: float = 0.0,
) -> ExitSignal:
    """移動停損（距波段高點回落）+ 停利目標,含除權息還原防呆。"""
    require(avg_price > 0 and high_watermark > 0, "avg_price/high_watermark 必須 > 0")
    stop_price = high_watermark * (1 - trailing_stop_pct / 100.0)
    take_price = avg_price * (1 + take_profit_pct / 100.0)

    guard = ex_dividend_guard(
        prev_close=prev_close, today_open=today_open, today_low=today_low,
        dividend_amount=dividend_amount, stop_price=stop_price,
    )
    stop_hit = guard.stop_triggered
    take_hit = today_high >= take_price

    if take_hit:
        suggestion = f"🎯 觸及停利 {take_price:.2f}，建議確認賣出"
    elif stop_hit:
        suggestion = f"🛑 跌破移動停損 {stop_price:.2f}，建議確認賣出"
    elif guard.is_ex_dividend:
        suggestion = f"🟢 除息跳空但還原後未破停損（{guard.note}）"
    else:
        suggestion = "持有：未觸及停損停利"

    return ExitSignal(stop_triggered=stop_hit, take_triggered=take_hit,
                      stop_price=round(stop_price, 2), take_price=round(take_price, 2),
                      guard=guard, suggestion=suggestion)
