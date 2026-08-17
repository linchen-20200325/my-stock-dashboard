"""L2 純函式 — 💰 存股戰情室運算核心（健檢 ABCD + 235 加碼 + 3-3-3）。

無 I/O、不 import streamlit（§8.2 L2）。所有門檻自 L0
`shared.dividend_station_thresholds` 引入（§3.3）。資料不足一律回「不判定」
而非猜（§1 Fail Loud, Never Fake）。單位在參數名編碼（§4.1）。

週K 規則（§4.5 / §2.3 防 lookahead）：resample `W-FRI`（週五定案），且
**丟棄尚未收完的當週**（週五還沒到 → 不納入）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from shared import dividend_station_thresholds as T


# ── 週K / 均線 / 布林（純函式）─────────────────────────────────────────
def weekly_closes(daily_close: pd.Series) -> pd.Series:
    """日收盤 → 週五定案的週收盤序列，丟棄未收完的當週（防 lookahead）。"""
    if daily_close is None or len(daily_close) == 0:
        raise ValueError("weekly_closes: 日收盤為空")
    s = pd.Series(daily_close).dropna()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index)
    if s.empty:
        raise ValueError("weekly_closes: 去 NaN 後為空")
    wk = s.resample("W-FRI").last().dropna()
    # 當週未到週五 → 週標籤(Friday) > 最後交易日 → 丟棄（保守,寧可少一週不 lookahead）
    if len(wk) and wk.index[-1] > s.index[-1]:
        wk = wk.iloc[:-1]
    return wk


def week_ma(weekly_close: pd.Series, period_weeks: int) -> float | None:
    """最新 N 週均線；不足 N 週 → None。"""
    if weekly_close is None or len(weekly_close) < period_weeks:
        return None
    return float(weekly_close.iloc[-period_weeks:].mean())


def week_ma_slope(weekly_close: pd.Series, period_weeks: int) -> float | None:
    """N 週均線斜率（本週均 − 前一週均）；<0 = 下彎。不足 → None。"""
    if weekly_close is None or len(weekly_close) < period_weeks + 1:
        return None
    ma_now = weekly_close.iloc[-period_weeks:].mean()
    ma_prev = weekly_close.iloc[-period_weeks - 1:-1].mean()
    return float(ma_now - ma_prev)


def bollinger_z(weekly_close: pd.Series,
                period_weeks: int = T.BOLL_PERIOD_WEEKS) -> float | None:
    """20 週布林標準差位階 z =（週收 − N週均）/ N週std（母體 ddof=0）。

    不足 N 週或無波動（std≈0）→ None（§1 不猜）。
    """
    if weekly_close is None or len(weekly_close) < period_weeks:
        return None
    window = weekly_close.iloc[-period_weeks:]
    ma = float(window.mean())
    sd = float(window.std(ddof=0))
    if math.isclose(sd, 0.0, abs_tol=T.FLOAT_ABS_TOL):
        return None
    return (float(weekly_close.iloc[-1]) - ma) / sd


# ── 健檢 A/B/C/D ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Flag:
    level: str      # 🔴 / 🟡 / 🟢 / ⚪(資料不足)
    msg: str


def health_a(total_return_1y_pct: float | None,
             annual_yield_pct: float | None) -> Flag:
    """A 不吃本金：近一年含息總報酬 < 年化配息率 → 🔴 賺息賠本（吃本金）。"""
    if total_return_1y_pct is None or annual_yield_pct is None:
        return Flag("⚪", "A 資料不足（缺報酬或配息率）")
    if total_return_1y_pct < annual_yield_pct:
        return Flag("🔴", f"賺息賠本：年報酬 {total_return_1y_pct:.1f}% < 配息率 "
                          f"{annual_yield_pct:.1f}%（吃到本金）")
    return Flag("🟢", f"未吃本金：年報酬 {total_return_1y_pct:.1f}% ≥ 配息率 "
                      f"{annual_yield_pct:.1f}%")


def health_b(sharpe: float | None) -> Flag:
    """B 夏普：Sharpe < 0 → 🔴 承擔風險無超額報酬（ETF 亦套用,v19.166）。"""
    if sharpe is None:
        return Flag("⚪", "B 無夏普資料")
    if sharpe < T.SHARPE_NEG_THRESHOLD:
        return Flag("🔴", f"Sharpe {sharpe:.2f} < 0：承擔風險卻無超額報酬")
    return Flag("🟢", f"Sharpe {sharpe:.2f} ≥ 0")


def health_c(weekly_close: pd.Series) -> Flag:
    """C 趨勢防守：週收 < 13週季線 且 季線下彎 → 🟡 趨勢轉弱,暫停加碼。"""
    ma13 = week_ma(weekly_close, T.MA_QUARTER_WEEKS)
    slope = week_ma_slope(weekly_close, T.MA_QUARTER_WEEKS)
    if ma13 is None or slope is None:
        return Flag("⚪", "C 週數不足（<13週季線）")
    close = float(weekly_close.iloc[-1])
    if close < ma13 and slope < 0:
        return Flag("🟡", f"趨勢轉弱：週收 {close:.2f} < 季線 {ma13:.2f} 且季線下彎 → 暫停加碼")
    return Flag("🟢", f"趨勢守穩：週收 {close:.2f} vs 季線 {ma13:.2f}")


def health_d(premium_pct: float | None) -> Flag:
    """D 折溢價（ETF專屬）：市價溢價 > 1.5% → 🟡 高溢價不追高。"""
    if premium_pct is None:
        return Flag("⚪", "D 無折溢價資料")
    if premium_pct > T.PREMIUM_ALERT_PCT:
        return Flag("🟡", f"高溢價 {premium_pct:.2f}% > {T.PREMIUM_ALERT_PCT}% → 不追高")
    return Flag("🟢", f"折溢價 {premium_pct:.2f}%（正常）")


# ── 235 加碼引擎（三取一 Max 觸發）─────────────────────────────────────
@dataclass(frozen=True)
class Light235:
    light: str                       # T.LIGHT_* 常數
    icon: str
    label: str
    deploy_pct: float                # 動用閒置加碼金 %
    reasons: list[str] = field(default_factory=list)     # 哪個條件觸發（可多個）
    take_profit: str | None = None   # None / "partial"(+2σ) / "force"(+3σ)
    deepwater_note: str | None = None


def light_235(*, vix: float | None, weekly_close: float | None,
              ma4w: float | None, ma13w: float | None, ma52w: float | None,
              z: float | None) -> Light235:
    """依「VIX × 週線 × 20週布林」三取一,取最嚴重那一盞。純函式。

    參數皆為**最新值純量**（weekly_close = 最新週收）。缺值不觸發該條件（§1）。
    """
    conds: list[tuple[str, str]] = []

    # 燈三（最嚴重）
    if vix is not None and vix >= T.VIX_LIGHT3:
        conds.append((T.LIGHT_3, f"VIX≥{T.VIX_LIGHT3:.0f}"))
    if (weekly_close is not None and ma52w is not None and z is not None
            and weekly_close < ma52w and z < T.Z_LIGHT2):
        conds.append((T.LIGHT_3, "週收<年線且布林<-2σ"))
    if z is not None and z < T.Z_LIGHT3:
        conds.append((T.LIGHT_3, f"布林<{T.Z_LIGHT3:.0f}σ"))
    # 燈二
    if vix is not None and T.VIX_LIGHT2 <= vix < T.VIX_LIGHT3:
        conds.append((T.LIGHT_2, f"VIX {T.VIX_LIGHT2:.0f}~{T.VIX_LIGHT3:.0f}"))
    if weekly_close is not None and ma13w is not None and weekly_close < ma13w:
        conds.append((T.LIGHT_2, "週收<季線"))
    if z is not None and z < T.Z_LIGHT2:
        conds.append((T.LIGHT_2, f"布林<{T.Z_LIGHT2:.0f}σ"))
    # 燈一
    if vix is not None and T.VIX_LIGHT1 <= vix < T.VIX_LIGHT2:
        conds.append((T.LIGHT_1, f"VIX {T.VIX_LIGHT1:.0f}~{T.VIX_LIGHT2:.0f}"))
    if weekly_close is not None and ma4w is not None and weekly_close < ma4w:
        conds.append((T.LIGHT_1, "週收<月線"))
    if z is not None and z < T.Z_LIGHT1:
        conds.append((T.LIGHT_1, f"布林<{T.Z_LIGHT1:.0f}σ"))

    # 停利軸（超漲,與加碼互斥：z>+2 不可能同時 z<-1）
    take_profit = None
    if z is not None:
        if z > T.Z_TAKE_PROFIT_FORCE:
            take_profit = "force"
        elif z > T.Z_TAKE_PROFIT_PARTIAL:
            take_profit = "partial"

    if take_profit:
        meta = T.LIGHT_META[T.LIGHT_TAKE_PROFIT]
        _tp_txt = "強制停利(>+3σ)" if take_profit == "force" else "分批停利(>+2σ)"
        return Light235(light=T.LIGHT_TAKE_PROFIT, icon=meta["icon"], label=meta["label"],
                        deploy_pct=0.0, reasons=[_tp_txt], take_profit=take_profit)

    if conds:
        best = max((c[0] for c in conds), key=lambda l: T._SEVERITY[l])
        reasons = [r for (l, r) in conds if l == best]
    else:
        best, reasons = T.LIGHT_CRUISE, ["VIX/週線/布林 均未觸發"]

    # 深水防守（§ 郭俊宏）：破年線後**站回季線** = 落底回升（較具體,優先）；
    # 否則破年線但布林未達 -2σ（尚不夠深）→ 等共伴確認。已 <-2σ 則屬燈三,不另註。
    deepwater = None
    if (weekly_close is not None and ma52w is not None and weekly_close < ma52w):
        if ma13w is not None and weekly_close >= ma13w:
            deepwater = "已站回 13 週季線 → 留意落底回升訊號"
        elif z is not None and z >= T.Z_LIGHT2:
            deepwater = "週收破年線但布林未達 -2σ → 等共伴確認,先別重壓"

    meta = T.LIGHT_META[best]
    return Light235(light=best, icon=meta["icon"], label=meta["label"],
                    deploy_pct=meta["deploy_pct"], reasons=reasons,
                    take_profit=None, deepwater_note=deepwater)


# ── 3-3-3 挑三原則 ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class Screen333:
    passed: bool
    inception_ok: bool | None
    return_ok: bool | None
    peer_ok: bool | None
    detail: str


def screen_333(*, inception_years: float | None,
               ann_return_3y_pct: float | None,
               cum_return_3y_pct: float | None,
               peer_ranks: dict[int, float] | None) -> Screen333:
    """3-3-3：①成立≥3年 ②3年年化≥7%(或累積≥21%) ③同儕 3/6/12M 皆前 1/3。

    peer_ranks: {月數: 百分位}(0=最強,1=最弱);None 或不齊 → 該項不可判定。
    三項須皆 True 才 passed；任一不可判定 → passed=False（§1 不足不放行）。
    """
    inception_ok = (None if inception_years is None
                    else inception_years >= T.MIN_INCEPTION_YEARS)
    if ann_return_3y_pct is None and cum_return_3y_pct is None:
        return_ok = None
    else:
        return_ok = ((ann_return_3y_pct is not None and ann_return_3y_pct >= T.MIN_ANN_RETURN_3Y_PCT)
                     or (cum_return_3y_pct is not None and cum_return_3y_pct >= T.MIN_CUM_RETURN_3Y_PCT))
    peer_ok = None
    if peer_ranks:
        _vals = [peer_ranks.get(m) for m in T.PEER_WINDOWS_MONTHS]
        if all(v is not None for v in _vals):
            peer_ok = all(v <= T.PEER_TOP_FRACTION for v in _vals)

    passed = bool(inception_ok and return_ok and peer_ok)
    parts = [
        f"成立{'✅' if inception_ok else ('❔' if inception_ok is None else '❌')}",
        f"3年報酬{'✅' if return_ok else ('❔' if return_ok is None else '❌')}",
        f"同儕前1/3{'✅' if peer_ok else ('❔' if peer_ok is None else '❌')}",
    ]
    return Screen333(passed=passed, inception_ok=inception_ok, return_ok=return_ok,
                     peer_ok=peer_ok, detail="　".join(parts))


# ── 彙總單一標的 → 一列 ─────────────────────────────────────────────────
@dataclass(frozen=True)
class HoldingAssessment:
    ticker: str
    name: str
    asset_class: str                 # core / satellite
    health_a: Flag
    health_b: Flag
    health_c: Flag
    health_d: Flag
    light: Light235
    screen: Screen333
    worst_health: str                # 🔴/🟡/🟢/⚪ 取最嚴重


def _worst_level(*flags: Flag) -> str:
    order = {"🔴": 3, "🟡": 2, "🟢": 1, "⚪": 0}
    best = max(flags, key=lambda f: order.get(f.level, 0))
    return best.level


def assess_holding(*, ticker: str, name: str, asset_class: str,
                   weekly_close: pd.Series, vix: float | None,
                   premium_pct: float | None, sharpe: float | None,
                   total_return_1y_pct: float | None, annual_yield_pct: float | None,
                   inception_years: float | None, ann_return_3y_pct: float | None,
                   cum_return_3y_pct: float | None,
                   peer_ranks: dict[int, float] | None) -> HoldingAssessment:
    """把單一標的的預算指標 → 健檢 + 235燈 + 3-3-3 一列。純函式。"""
    if weekly_close is None or len(weekly_close) == 0:
        raise ValueError(f"{ticker}: weekly_close 為空,無法評估（§1 不補假資料）")

    z = bollinger_z(weekly_close)
    ma4 = week_ma(weekly_close, T.MA_MONTH_WEEKS)
    ma13 = week_ma(weekly_close, T.MA_QUARTER_WEEKS)
    ma52 = week_ma(weekly_close, T.MA_YEAR_WEEKS)
    last_close = float(weekly_close.iloc[-1])

    fa = health_a(total_return_1y_pct, annual_yield_pct)
    fb = health_b(sharpe)
    fc = health_c(weekly_close)
    fd = health_d(premium_pct)
    lt = light_235(vix=vix, weekly_close=last_close, ma4w=ma4, ma13w=ma13, ma52w=ma52, z=z)
    sc = screen_333(inception_years=inception_years, ann_return_3y_pct=ann_return_3y_pct,
                    cum_return_3y_pct=cum_return_3y_pct, peer_ranks=peer_ranks)

    return HoldingAssessment(
        ticker=ticker, name=name, asset_class=asset_class,
        health_a=fa, health_b=fb, health_c=fc, health_d=fd,
        light=lt, screen=sc, worst_health=_worst_level(fa, fb, fc, fd))


def suggest_action(a: HoldingAssessment) -> str:
    """依優先序給單一建議（純函式）：汰弱 > 停利 > 趨勢暫停 > 加碼 > 高溢價 > 巡航。

    ⚠️ 郭俊宏防守邏輯：即使 235 亮加碼燈,若健檢 C「趨勢轉弱」→ **暫停加碼**（不追）。
    """
    # 1) 吃本金 / 夏普<0 → 汰弱留強（最優先）
    if a.health_a.level == "🔴" or a.health_b.level == "🔴":
        _why = a.health_a.msg if a.health_a.level == "🔴" else a.health_b.msg
        return f"🔴 汰弱：{_why}"
    # 2) 停利（超漲）
    if a.light.take_profit == "force":
        return "💰 強制停利（>+3σ）：獲利轉回核心資產"
    if a.light.take_profit == "partial":
        return "💰 分批停利（>+2σ）：部分獲利轉回核心"
    # 3) 235 亮加碼燈,但趨勢轉弱 → 暫停加碼（防守優先）
    if a.light.light in (T.LIGHT_1, T.LIGHT_2, T.LIGHT_3):
        if a.health_c.level == "🟡":
            return f"🟡 {a.light.icon} 訊號亮但季線轉弱 → 暫停加碼、先觀望"
        _dw = f"（{a.light.deepwater_note}）" if a.light.deepwater_note else ""
        return f"{a.light.icon} 加碼 {a.light.deploy_pct:.0f}%：{'、'.join(a.light.reasons)}{_dw}"
    # 4) 高溢價不追高
    if a.health_d.level == "🟡":
        return f"🟡 {a.health_d.msg}"
    # 5) 巡航
    return "⚪ 巡航：維持定期定額"
