"""
風險控制模組 v4.0 (§6)
單股風控 + ATR 動態停損 + 移動停利 + 組合風控

v4.0 更新：
  - 停損改為 ATR 動態停損（Buy_Price - ATR×1.5），取代固定 -8%
  - ATR=None 時自動降級為固定 8% 安全備援
  - RiskController 新增 atr 參數，check_exit() 接受 per-call ATR
"""
try:
    from src.config import (MAX_POSITION_PER_STOCK, MAX_PORTFOLIO_DRAWDOWN,
                        STOP_LOSS_PCT, TRAILING_STOP_PCT, MIN_CASH_RATIO,
                        MAX_POSITIONS, EXPOSURE_BULL, EXPOSURE_NEUTRAL, EXPOSURE_BEAR)
except ImportError:
    MAX_POSITION_PER_STOCK=0.10; MAX_PORTFOLIO_DRAWDOWN=0.15
    STOP_LOSS_PCT=0.08; TRAILING_STOP_PCT=0.07; MIN_CASH_RATIO=0.10
    MAX_POSITIONS=10; EXPOSURE_BULL=0.8; EXPOSURE_NEUTRAL=0.5; EXPOSURE_BEAR=0.2

ATR_MULTIPLIER = 1.5   # §6.2 ATR 動態停損倍率（固定值，不對外暴露設定）


# ── 組合曝險（依市場狀態）(§6.3) ─────────────────────────────
def portfolio_exposure(regime: str) -> float:
    """
    依市場狀態決定建議總股票曝險比例（§6.3）
    bull → 80%、neutral → 50%、bear → 20%
    """
    return {
        'bull':    EXPOSURE_BULL,
        'neutral': EXPOSURE_NEUTRAL,
        'bear':    EXPOSURE_BEAR,
    }.get(regime, EXPOSURE_NEUTRAL)


# ── 投組層級集中度守門 (§6.3;v19.151 接線) ─────────────────────
def check_portfolio_limits(weights: dict,
                           *,
                           single_max_pct: float = MAX_POSITION_PER_STOCK,
                           max_positions: int = MAX_POSITIONS) -> dict:
    """投組層級集中度上限檢查(單股權重上限 + 持股檔數上限)。純函式,零 I/O。

    把 RiskController 早已定義卻空轉的兩條上限(單股 ≤10% / 最多 10 檔)接成
    「輸入權重 → 回違反清單」,供個股組合風險貢獻區塊顯示(v19.151 接線)。

    Args:
        weights: {code: 市值權重}(scale-free;本函式內部正規化為 % of total)。
                 ≤0 / None 的檔視為未持有,不計入。
        single_max_pct: 單股權重上限(小數,預設 MAX_POSITION_PER_STOCK=0.10)。
        max_positions: 持股檔數上限(預設 MAX_POSITIONS=10)。

    Returns:
        dict {
          'n_positions':        int    有效持股檔數,
          'weights_pct':        dict   {code: 權重%},依權重降冪,
          'over_concentration': list   [(code, pct)] 單股 > single_max_pct×100(降冪),
          'too_many_positions': bool   n_positions > max_positions,
          'max_weight_pct':     float|None  最大單股權重%(空投組 None),
          'single_max_pct':     float  回傳門檻(供 UI 顯示),
          'max_positions':      int,
          'ok':                 bool   無任何違反,
        }
        空 / 全 ≤0 → n_positions=0, ok=True(無持股不算違反)。
    """
    _w = {str(k): float(v) for k, v in (weights or {}).items()
          if v is not None and _is_pos(v)}
    _total = sum(_w.values())
    _thresh_pct = float(single_max_pct) * 100.0
    if not _w or _total <= 0:
        return {'n_positions': 0, 'weights_pct': {}, 'over_concentration': [],
                'too_many_positions': False, 'max_weight_pct': None,
                'single_max_pct': single_max_pct, 'max_positions': max_positions,
                'ok': True}
    _pct = {c: v / _total * 100.0 for c, v in _w.items()}
    _pct_sorted = dict(sorted(_pct.items(), key=lambda kv: -kv[1]))
    _over = [(c, round(p, 1)) for c, p in _pct_sorted.items() if p > _thresh_pct]
    _n = len(_w)
    _too_many = _n > int(max_positions)
    return {
        'n_positions': _n,
        'weights_pct': {c: round(p, 1) for c, p in _pct_sorted.items()},
        'over_concentration': _over,
        'too_many_positions': _too_many,
        'max_weight_pct': round(next(iter(_pct_sorted.values())), 1),
        'single_max_pct': single_max_pct,
        'max_positions': int(max_positions),
        'ok': (not _over) and (not _too_many),
    }


def _is_pos(v) -> bool:
    """v 為有限正數(擋 NaN / inf / 負 / 非數字);集中度只計有效持股。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return f == f and f not in (float('inf'), float('-inf')) and f > 0


# ── ATR 動態停損工具函數 (§6.2) ──────────────────────────────
def atr_stop_price(buy_price: float, atr: float | None,
                   multiplier: float = ATR_MULTIPLIER,
                   fallback_pct: float = STOP_LOSS_PCT) -> float:
    """
    ATR 動態停損價 = Buy_Price - ATR × 1.5
    atr=None 時降級為固定比例 (buy_price × (1 - fallback_pct))
    """
    if atr is not None and atr > 0:
        return round(buy_price - atr * multiplier, 2)
    return round(buy_price * (1 - fallback_pct), 2)


def stop_loss_trigger(buy_price: float, current_price: float,
                      stop_pct: float | None = None,
                      atr: float | None = None) -> bool:
    """
    ATR 動態停損觸發（§6.2）。
    優先使用 atr；atr=None 時退回固定比例 stop_pct。
    """
    sp = atr_stop_price(buy_price, atr,
                        fallback_pct=(stop_pct if stop_pct is not None else STOP_LOSS_PCT))
    return current_price <= sp


def trailing_stop_trigger(buy_price, peak_price, current_price,
                           trail_pct=None, min_profit_pct=0.03) -> bool:
    """
    移動停利觸發判斷（§6.2 修正版）
    只要 peak_price 曾達到最小獲利門檻（預設3%），即使現價低於買入價也應觸發，
    防止回吐大波段利潤。
    """
    pct = trail_pct if trail_pct is not None else TRAILING_STOP_PCT
    if peak_price < buy_price * (1 + min_profit_pct):
        return False
    return current_price <= peak_price * (1 - pct)


# ── 主控制器 ─────────────────────────────────────────────────
class RiskController:
    """
    風險控制器 v4.0

    規則（根據說明書 §6）：
      - 單一股票不超過投資組合 10%          (§6.1)
      - ATR 動態停損：Buy - ATR×1.5        (§6.2) ← v4.0 新規則
        （ATR=None 時自動降級為固定 -8%）
      - 移動停利：獲利後回撤 7%             (§6.2)
      - 最大持股數：10 檔                    (§6.3)
      - 現金部位下限：10%                    (§6.3)
      - 最大回撤 15%，超過暫停交易          (§6.3)
      - 市場轉空時持股降至 20%               (§6.3)
    """

    def __init__(self, portfolio_value=1_000_000, regime='neutral', atr: float | None = None):
        self.portfolio_value   = portfolio_value
        self.regime            = regime
        self.atr               = atr          # ATR14 供動態停損使用
        self.max_single_weight = MAX_POSITION_PER_STOCK
        self.trail_pct         = TRAILING_STOP_PCT
        self.max_drawdown_pct  = MAX_PORTFOLIO_DRAWDOWN
        self.min_cash_ratio    = MIN_CASH_RATIO
        self.max_positions     = MAX_POSITIONS
        self.peak_value        = portfolio_value
        self.trading_suspended = False
        self._peak_prices      = {}

    @property
    def target_exposure(self) -> float:
        """目前市場狀態建議持股比例"""
        return portfolio_exposure(self.regime)

    @property
    def max_stock_budget(self) -> float:
        """最大可用於股票的資金"""
        return self.portfolio_value * self.target_exposure

    def position_size(self, price, weight=None) -> dict:
        """計算單股可買張數（以投組 10% 為上限）"""
        w = weight if weight is not None else self.max_single_weight
        allocated = self.portfolio_value * w
        shares = int(allocated / price / 1000) * 1000
        return {
            'allocated': round(allocated, 0),
            'shares': shares,
            'lots': shares // 1000,
            'actual_cost': shares * price
        }

    def stop_price(self, buy_price: float, atr: float | None = None) -> float:
        """
        ATR 動態停損價 = Buy_Price - ATR×1.5（§6.2）
        atr 未提供時使用 self.atr；仍為 None 則降級為 -8%。
        """
        _atr = atr if atr is not None else self.atr
        return atr_stop_price(buy_price, _atr)

    def check_exit(self, stock_id: str, buy_price: float, current_price: float,
                   atr: float | None = None) -> dict:
        """
        整合 ATR 動態停損 + 移動停利 出場判斷

        Parameters:
            atr: 個別呼叫的 ATR14（優先於 self.atr）

        Returns:
            dict: exit_type ('stop_loss'/'trailing'/'hold'), action, pnl_pct
        """
        prev_peak = self._peak_prices.get(stock_id, buy_price)
        new_peak  = max(prev_peak, current_price)
        self._peak_prices[stock_id] = new_peak

        pnl_pct = (current_price - buy_price) / buy_price * 100
        _atr    = atr if atr is not None else self.atr
        sp      = self.stop_price(buy_price, _atr)

        # ATR 動態停損（優先）
        if stop_loss_trigger(buy_price, current_price, atr=_atr):
            _method = f'ATR×{ATR_MULTIPLIER}' if (_atr is not None and _atr > 0) else '固定-8%'
            return {
                'exit_type':  'stop_loss',
                'action':     f'🔴 動態停損出場（{_method}）',
                'pnl_pct':    round(pnl_pct, 2),
                'stop_price': sp,
                'peak_price': new_peak,
            }

        # 移動停利
        if trailing_stop_trigger(buy_price, new_peak, current_price, self.trail_pct):
            return {
                'exit_type':  'trailing',
                'action':     '🟡 移動停利出場',
                'pnl_pct':    round(pnl_pct, 2),
                'stop_price': sp,
                'peak_price': new_peak,
            }

        return {
            'exit_type':  'hold',
            'action':     '✅ 持倉正常',
            'pnl_pct':    round(pnl_pct, 2),
            'stop_price': sp,
            'peak_price': new_peak,
        }

    # 舊版相容
    def check_stop_loss(self, buy_price, current_price) -> dict:
        return self.check_exit('_', buy_price, current_price)

    def update_drawdown(self, current_value) -> dict:
        """更新最大回撤狀態"""
        if current_value > self.peak_value:
            self.peak_value = current_value
        drawdown = (self.peak_value - current_value) / self.peak_value
        if drawdown >= self.max_drawdown_pct:
            self.trading_suspended = True
        elif drawdown < self.max_drawdown_pct * 0.5:
            self.trading_suspended = False
        return {
            'peak_value':        self.peak_value,
            'current_value':     current_value,
            'drawdown_pct':      round(drawdown * 100, 2),
            'trading_suspended': self.trading_suspended,
            'status': '🔴 已暫停交易（回撤超15%）' if self.trading_suspended else '✅ 交易正常',
        }

    def can_add_position(self, current_positions: int) -> bool:
        """是否可以新增持倉（最大10檔）"""
        return current_positions < self.max_positions

    def cash_check(self, equity_value, portfolio_total) -> dict:
        """現金水位檢查（下限10%）"""
        cash = portfolio_total - equity_value
        cash_ratio = cash / portfolio_total if portfolio_total > 0 else 0
        ok = cash_ratio >= self.min_cash_ratio
        return {
            'cash': cash,
            'cash_ratio': round(cash_ratio * 100, 2),
            'ok': ok,
            'status': f"{'✅' if ok else '⚠️'} 現金比例 {cash_ratio*100:.1f}% （下限{self.min_cash_ratio*100:.0f}%）"
        }

    def full_report(self, positions: list) -> dict:
        """全倉風控報告"""
        total_cost  = sum(p['buy_price']     * p['lots'] * 1000 for p in positions)
        total_value = sum(p['current_price'] * p['lots'] * 1000 for p in positions)
        total_pnl   = total_value - total_cost
        pnl_pct     = total_pnl / total_cost * 100 if total_cost else 0
        alerts = []
        for p in positions:
            chk = self.check_exit(p.get('stock_id',''), p['buy_price'], p['current_price'],
                                  atr=p.get('atr'))
            if chk['exit_type'] != 'hold':
                alerts.append(f"{chk['action']}：{p.get('stock_id','')} "
                               f"(現{p['current_price']} 成本{p['buy_price']})")
        dd = self.update_drawdown(total_value)
        return {
            'total_cost':        total_cost,
            'total_value':       total_value,
            'total_pnl':         total_pnl,
            'total_pnl_pct':     round(pnl_pct, 2),
            'drawdown':          dd,
            'exit_alerts':       alerts,
            'positions':         len(positions),
            'can_add':           self.can_add_position(len(positions)),
            'target_exposure':   f"{self.target_exposure*100:.0f}%",
        }


# ── 便利函數 ─────────────────────────────────────────────────
def calc_position_size(portfolio_value, price, weight=MAX_POSITION_PER_STOCK):
    return RiskController(portfolio_value).position_size(price, weight)

def calc_stop_loss(buy_price, atr=None, stop_pct=STOP_LOSS_PCT):
    """ATR 動態停損價（atr=None 時退回固定比例）"""
    return atr_stop_price(buy_price, atr, fallback_pct=stop_pct)
