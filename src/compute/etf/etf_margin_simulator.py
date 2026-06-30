"""src/compute/etf/etf_margin_simulator.py — ETF 質借倒金字塔加碼模擬器引擎 (v18.162).

核心邏輯：
1. 依景氣階段（復甦/擴張/放緩/衰退）+ 風格 preset（保守/平衡/積極/極限）選加碼觸發表
2. 倒金字塔加碼：價格從歷史高點（HWM）回撤 -X% 時依 preset 質借 Y% 現金加碼
3. 每根 K 線檢查擔保維持率：
       擔保維持率 = (持股市值 + 現金) / 借款餘額 × 100%
   < 140% → ⚠️ 追繳保證金；< 130% → 💥 強制平倉

公式鏡像台股券商實務。純函式 + frozen dataclass，無 streamlit 相依。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

# ── 維持率門檻（台股保守實務值）─────────────────────────────
# v18.436 #2 翻案結論:此兩常數為「ETF 質借模擬」單一功能專屬風控門檻,
# 唯一 caller = 本模組 + tab_etf_margin_simulator.py(同功能 UI)。已是具名 SSOT,
# 屬正確的 domain-local 放置 — 不外移至 shared/(§-1:單功能常數移共用層 = 多餘抽象,
# 反增跨模組依賴)。若未來其他風控模組需共用維持率,再升格 shared/。
MARGIN_CALL_RATIO = 140.0  # %，低於此追繳保證金（本功能 SSOT）
LIQUIDATION_RATIO = 130.0  # %，低於此強制平倉（本功能 SSOT）

# ── 4 風格 × 3 階梯觸發表（drawdown_pct → leverage_add_pct）───
#  drawdown_pct: 從歷史最高點回撤幅度（正數，%）
#  leverage_add_pct: 該檔加碼時動用「初始本金」的百分比作為質借
LEVERAGE_PRESETS: dict[str, dict] = {
    "conservative": {
        "label": "🛡️ 保守加碼",
        "desc": "深跌才動手、單次加幅小；犧牲反彈報酬換爆倉容忍度。",
        "triggers": [
            {"drawdown_pct": 5,  "leverage_add_pct": 5},
            {"drawdown_pct": 15, "leverage_add_pct": 10},
            {"drawdown_pct": 25, "leverage_add_pct": 15},
        ],
    },
    "balanced": {
        "label": "⚖️ 平衡加碼",
        "desc": "經典倒金字塔節奏：剛跌 5% 加 10%、跌 10% 再加 20%、跌 20% 再加 30%。",
        "triggers": [
            {"drawdown_pct": 5,  "leverage_add_pct": 10},
            {"drawdown_pct": 10, "leverage_add_pct": 20},
            {"drawdown_pct": 20, "leverage_add_pct": 30},
        ],
    },
    "aggressive": {
        "label": "🚀 積極加碼",
        "desc": "提早出手 + 加幅放大；追求反彈最大化但提高爆倉機率。",
        "triggers": [
            {"drawdown_pct": 3,  "leverage_add_pct": 15},
            {"drawdown_pct": 8,  "leverage_add_pct": 25},
            {"drawdown_pct": 15, "leverage_add_pct": 35},
        ],
    },
    "extreme": {
        "label": "💥 極限加碼",
        "desc": "短跌即重壓、總槓桿可達初始本金 1 倍；2008/2020 等暴跌恐強平。",
        "triggers": [
            {"drawdown_pct": 3,  "leverage_add_pct": 20},
            {"drawdown_pct": 7,  "leverage_add_pct": 30},
            {"drawdown_pct": 12, "leverage_add_pct": 50},
        ],
    },
}

# ── 4 景氣階段 × 4 風格推薦對應（依美林時鐘邏輯）────────────
#  使用者切階段時 UI 可自動高亮推薦 preset；非強制
PHASE_RECOMMENDATION: dict[str, str] = {
    "復甦 Recovery":    "aggressive",   # 谷底反轉，敢加才有利
    "過熱 Overheat":    "conservative", # 接近循環頂，避免槓桿
    "停滯 Stagflation": "conservative", # 盈餘收縮 + 殖利率風險
    "衰退 Recession":   "balanced",     # 跌深可加但需控制
}


@dataclass(frozen=True)
class SimulationParams:
    """模擬參數（不可變，方便快取）。"""
    preset_key: str
    initial_capital: float = 1_000_000.0   # 初始自有資金（TWD）
    margin_call_ratio: float = MARGIN_CALL_RATIO
    liquidation_ratio: float = LIQUIDATION_RATIO


@dataclass
class SimulationDay:
    """單日狀態快照。"""
    date: pd.Timestamp
    price: float
    hwm: float                 # 歷史最高價
    drawdown_pct: float        # 從 hwm 的回撤（正數%）
    shares: float              # 持股數
    cash: float                # 帳上現金
    borrowed: float            # 借款餘額
    equity: float              # 淨值 = shares*price + cash - borrowed
    maintenance_ratio: float   # 擔保維持率 %（borrowed=0 時記 999）
    status: Literal["normal", "margin_call", "liquidated"]
    event: str = ""            # 觸發事件文字（加碼/追繳/強平）


@dataclass
class SimulationResult:
    """模擬完整結果。"""
    params: SimulationParams
    daily: list[SimulationDay] = field(default_factory=list)
    margin_call_count: int = 0
    liquidation_count: int = 0
    triggered_levels: list[int] = field(default_factory=list)  # 已觸發的 trigger index

    @property
    def final_equity(self) -> float:
        return self.daily[-1].equity if self.daily else 0.0

    @property
    def total_return_pct(self) -> float:
        if not self.daily:
            return 0.0
        return (self.final_equity / self.params.initial_capital - 1) * 100

    @property
    def max_drawdown_pct(self) -> float:
        if not self.daily:
            return 0.0
        equities = [d.equity for d in self.daily]
        peak = equities[0]
        max_dd = 0.0
        for e in equities:
            peak = max(peak, e)
            if peak > 0:
                dd = (peak - e) / peak * 100
                max_dd = max(max_dd, dd)
        return max_dd

    @property
    def avg_leverage_ratio(self) -> float:
        """平均槓桿 = mean(borrowed / equity) × 100；無借款日不計入。"""
        ratios = [d.borrowed / d.equity * 100
                  for d in self.daily
                  if d.borrowed > 0 and d.equity > 0]
        return sum(ratios) / len(ratios) if ratios else 0.0


def get_preset(preset_key: str) -> dict:
    """取出 preset 的 deep copy，防止呼叫端污染原表。"""
    if preset_key not in LEVERAGE_PRESETS:
        raise KeyError(
            f"未知 preset_key: {preset_key!r}（可選：{list(LEVERAGE_PRESETS)}）"
        )
    return copy.deepcopy(LEVERAGE_PRESETS[preset_key])


def _compute_maintenance_ratio(shares: float, price: float,
                                cash: float, borrowed: float) -> float:
    """擔保維持率 = (持股市值 + 現金) / 借款 × 100；borrowed=0 回 999。"""
    if borrowed <= 0:
        return 999.0
    collateral = shares * price + cash
    return collateral / borrowed * 100


def simulate_margin_strategy(price_series: pd.Series,
                              params: SimulationParams) -> SimulationResult:
    """跑倒金字塔加碼模擬。

    Parameters
    ----------
    price_series : pd.Series
        index 為日期 / value 為收盤價（升序）。
    params : SimulationParams
        模擬參數。

    Returns
    -------
    SimulationResult
        每日狀態 + 統計摘要。
    """
    if price_series is None or len(price_series) == 0:
        return SimulationResult(params=params)

    preset = get_preset(params.preset_key)
    triggers = preset["triggers"]

    # 初始：用全部自有資金買入（Day 0 全押）
    initial_price = float(price_series.iloc[0])
    if initial_price <= 0:
        return SimulationResult(params=params)
    shares = params.initial_capital / initial_price
    cash = 0.0
    borrowed = 0.0
    hwm = initial_price
    triggered: list[int] = []
    result = SimulationResult(params=params)

    for date, price in price_series.items():
        price = float(price)
        if price <= 0:
            continue
        hwm = max(hwm, price)
        drawdown_pct = (hwm - price) / hwm * 100 if hwm > 0 else 0.0
        event = ""
        status: Literal["normal", "margin_call", "liquidated"] = "normal"

        # 1) 倒金字塔加碼：依序檢查每個 trigger，未觸發過且回撤 ≥ 門檻就動作
        for i, trig in enumerate(triggers):
            if i in triggered:
                continue
            if drawdown_pct >= trig["drawdown_pct"]:
                loan = params.initial_capital * trig["leverage_add_pct"] / 100
                add_shares = loan / price
                shares += add_shares
                borrowed += loan
                triggered.append(i)
                event = (f"🟢 觸發 L{i+1}（跌 {drawdown_pct:.1f}%）"
                         f"質借 {loan:,.0f} 加碼 {add_shares:.0f} 股")
                break  # 同一日只觸發一個 level

        # 2) 維持率檢查
        m_ratio = _compute_maintenance_ratio(shares, price, cash, borrowed)
        if borrowed > 0 and m_ratio < params.liquidation_ratio:
            # 💥 強平：賣光持股還借款，剩餘進現金
            cash += shares * price - borrowed
            shares = 0.0
            borrowed = 0.0
            status = "liquidated"
            event = (event + " | " if event else "") + \
                    f"💥 強制平倉（維持率 {m_ratio:.1f}% < {params.liquidation_ratio}%）"
            result.liquidation_count += 1
            m_ratio = 999.0  # reset
        elif borrowed > 0 and m_ratio < params.margin_call_ratio:
            status = "margin_call"
            event = (event + " | " if event else "") + \
                    f"⚠️ 追繳保證金（維持率 {m_ratio:.1f}% < {params.margin_call_ratio}%）"
            result.margin_call_count += 1

        equity = shares * price + cash - borrowed
        result.daily.append(SimulationDay(
            date=pd.Timestamp(date), price=price, hwm=hwm,
            drawdown_pct=drawdown_pct, shares=shares, cash=cash,
            borrowed=borrowed, equity=equity,
            maintenance_ratio=m_ratio, status=status, event=event,
        ))

    result.triggered_levels = triggered
    return result


def result_to_dataframe(result: SimulationResult) -> pd.DataFrame:
    """轉成 DataFrame 給 UI 顯示 / CSV 下載。"""
    return pd.DataFrame([{
        "date": d.date, "price": d.price, "hwm": d.hwm,
        "drawdown_pct": d.drawdown_pct, "shares": d.shares,
        "cash": d.cash, "borrowed": d.borrowed, "equity": d.equity,
        "maintenance_ratio": d.maintenance_ratio,
        "status": d.status, "event": d.event,
    } for d in result.daily])
