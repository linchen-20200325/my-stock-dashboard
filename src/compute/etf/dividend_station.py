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
from shared import station_specs as SS


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
    s = s.sort_index()          # ⚠️ 台股來源常新→舊排序;不排序會讓下方防呆誤刪整週(稽核 M2)
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
    last = float(weekly_close.iloc[-1])
    ma = float(window.mean())
    sd = float(window.std(ddof=0))
    if not (math.isfinite(last) and math.isfinite(ma) and math.isfinite(sd)):
        return None                      # NaN 污染 → 不判定,不可回 NaN 誤當「全清」(稽核 L5)
    if math.isclose(sd, 0.0, abs_tol=T.FLOAT_ABS_TOL):
        return None
    return (last - ma) / sd


# ── 報酬 / 配息 / 夏普（純函式,供 L3 抓到序列後計算）───────────────────
def annual_yield_pct(ttm_dividend: float | None, price: float | None) -> float | None:
    """年化配息率% = 近 12 月配息 / 現價 × 100。缺值或價<=0 → None。"""
    if ttm_dividend is None or price is None or price <= 0:
        return None
    return float(ttm_dividend) / float(price) * 100.0


def total_return_pct(start_close: float | None, end_close: float | None) -> float | None:
    """區間總報酬%（用還原價 → 已含息）=（end/start − 1）×100。start<=0 → None。"""
    if start_close is None or end_close is None or start_close <= 0:
        return None
    return (float(end_close) / float(start_close) - 1.0) * 100.0


def annualized_return_pct(start_close: float | None, end_close: float | None,
                          years: float) -> float | None:
    """年化報酬% =（(end/start)^(1/years) − 1）×100。years<=0 或 start<=0 → None。"""
    if start_close is None or end_close is None or start_close <= 0 or years <= 0:
        return None
    return ((float(end_close) / float(start_close)) ** (1.0 / years) - 1.0) * 100.0


def sharpe_weekly(weekly_close: pd.Series, *, min_weeks: int = T.MA_QUARTER_WEEKS,
                  rf_pct: float = 0.0) -> float | None:
    """用週報酬算年化夏普 =（週均超額報酬 − 週無風險利率）/ 週std × √52。

    rf_pct：無風險利率（年化 %，如 FEDFUNDS）。B2(v19.198)：原寫死 rf=0（MVP 簡化）
    系統性偏寬鬆（更多 ETF 被算成正夏普）→ 對齊 ETF `calc_sharpe` 的 rf SSOT
    (`ETF_SHARPE_RF_FALLBACK_PCT` / 注入的即時 FEDFUNDS) 後，health_b「承擔風險卻無超額
    報酬」名副其實。週無風險利率 = rf_pct/100/52（與 calc_sharpe 同刻度，年化 rf 除週數）。
    週數不足 min_weeks 或波動≈0 → None（§1 不猜）。已用還原價 → 週報酬含息。
    """
    if weekly_close is None or len(weekly_close) < min_weeks + 1:
        return None
    rets = pd.Series(weekly_close).pct_change().dropna()
    if len(rets) < min_weeks:
        return None
    _rf_weekly = float(rf_pct) / 100.0 / 52.0
    mu = float(rets.mean()) - _rf_weekly
    sd = float(rets.std(ddof=1))
    if not (math.isfinite(mu) and math.isfinite(sd)) or math.isclose(sd, 0.0, abs_tol=T.FLOAT_ABS_TOL):
        return None
    return mu / sd * math.sqrt(52.0)


def inception_years(first_date, as_of=None) -> float | None:
    """成立年數 =（as_of − 最早資料日）/ 365.25。缺 → None。"""
    if first_date is None:
        return None
    first = pd.Timestamp(first_date)
    ref = pd.Timestamp(as_of) if as_of is not None else first  # as_of 由 caller 傳(避免不純)
    if as_of is None:
        return None
    days = (ref - first).days
    return None if days < 0 else days / 365.25


# ── 健檢 A/B/C/D ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Flag:
    level: str      # 🔴 / 🟡 / 🟢 / ⚪(資料不足)
    msg: str
    #: level=="⚪" 時的缺值原因（`shared.station_specs.MISS_*`）。
    #: 2026-08-25 新增:原本「該項缺輸入」「整檔抓取失敗」「這類不適用」
    #: 三種處置完全不同的情況全部只有一個 ⚪,消費端無法分辨。
    #: **不改判燈**,只是把原因從中文 msg 裡抽成可程式判讀的欄位
    #: （解析 msg 字串太脆弱 —— 改一個字就壞）。
    miss_reason: str = ""


def health_a(total_return_1y_pct: float | None,
             annual_yield_pct: float | None) -> Flag:
    """A 不吃本金：近一年含息總報酬 < 年化配息率 → 🔴 賺息賠本（吃本金）。"""
    if total_return_1y_pct is None or annual_yield_pct is None:
        return Flag("⚪", "A 資料不足（缺報酬或配息率）", miss_reason=SS.MISS_NO_INPUT)
    if total_return_1y_pct < annual_yield_pct:
        return Flag("🔴", f"賺息賠本：年報酬 {total_return_1y_pct:.1f}% < 配息率 "
                          f"{annual_yield_pct:.1f}%（吃到本金）")
    return Flag("🟢", f"未吃本金：年報酬 {total_return_1y_pct:.1f}% ≥ 配息率 "
                      f"{annual_yield_pct:.1f}%")


def health_b(sharpe: float | None) -> Flag:
    """B 夏普：Sharpe < 0 → 🔴 承擔風險無超額報酬（ETF 亦套用,v19.166）。"""
    if sharpe is None:
        return Flag("⚪", "B 無夏普資料", miss_reason=SS.MISS_NO_INPUT)
    if sharpe < T.SHARPE_NEG_THRESHOLD:
        return Flag("🔴", f"Sharpe {sharpe:.2f} < 0：承擔風險卻無超額報酬")
    return Flag("🟢", f"Sharpe {sharpe:.2f} ≥ 0")


def health_c(weekly_close: pd.Series) -> Flag:
    """C 趨勢防守：週收 < 13週季線 且 季線下彎 → 🟡 趨勢轉弱,暫停加碼。"""
    ma13 = week_ma(weekly_close, T.MA_QUARTER_WEEKS)
    slope = week_ma_slope(weekly_close, T.MA_QUARTER_WEEKS)
    if ma13 is None or slope is None:
        return Flag("⚪", "C 週數不足（<13週季線）", miss_reason=SS.MISS_NOT_ENOUGH)
    close = float(weekly_close.iloc[-1])
    if close < ma13 and slope < 0:
        return Flag("🟡", f"趨勢轉弱：週收 {close:.2f} < 季線 {ma13:.2f} 且季線下彎 → 暫停加碼")
    return Flag("🟢", f"趨勢守穩：週收 {close:.2f} vs 季線 {ma13:.2f}")


def health_d(premium_pct: float | None) -> Flag:
    """D 折溢價（ETF專屬）：市價溢價 > 1.5% → 🟡 高溢價不追高。"""
    if premium_pct is None:
        return Flag("⚪", "D 無折溢價資料", miss_reason=SS.MISS_NO_INPUT)
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
    #: 三個軸(VIX / 週線 / 布林 z)**全部無值**時填 `MISS_NO_INPUT`。
    #: ⚠️ 這是 ⚪ 濫用最危險的一處:三軸全空時 `conds` 為空 → 落到
    #: `LIGHT_CRUISE`,畫面顯示「⚪ 巡航:維持定期定額」——
    #: **什麼都沒抓到，卻告訴使用者一切正常、繼續買**。
    #: 本欄不改判燈結果(仍是 cruise),只讓消費端能把這種 cruise
    #: 跟「真的很平靜」的 cruise 分開顯示(§1)。
    miss_reason: str = ""


def light_235(*, vix: float | None, weekly_close: float | None,
              ma4w: float | None, ma13w: float | None, ma52w: float | None,
              z: float | None) -> Light235:
    """依「VIX × 週線 × 20週布林」三取一,取最嚴重那一盞。純函式。

    參數皆為**最新值純量**（weekly_close = 最新週收）。缺值不觸發該條件（§1）。
    """
    conds: list[tuple[str, str]] = []
    _cruise_miss = ""          # 見下方 cruise 分支:三軸全空時才填

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
        # ⚠️ 區分兩種 cruise:三軸真的都沒觸發(平靜) vs 三軸根本沒資料。
        #    後者原本與前者完全同形,等於「沒抓到 → 顯示一切正常」。
        if vix is None and z is None and weekly_close is None:
            _cruise_miss = SS.MISS_NO_INPUT
            reasons = ["VIX / 週線 / 布林 三個判斷依據都沒有資料"]

    # 深水防守（§ 深水防守）：破年線後**站回季線** = 落底回升（較具體,優先）；
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
                    take_profit=None, deepwater_note=deepwater,
                    miss_reason=_cruise_miss)


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
    asset_kind: str = T.KIND_ETF     # stock / etf（個股 D折溢價、3-3-3 不適用）


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
                   peer_ranks: dict[int, float] | None,
                   asset_kind: str = T.KIND_ETF) -> HoldingAssessment:
    """把單一標的的預算指標 → 健檢 + 235燈 + 3-3-3 一列。純函式。

    asset_kind=stock（個股）：D 折溢價、3-3-3（ETF/基金挑選規則）**不適用**,標中性
    ⚪「個股不適用」而非誤導的 🔴/🟡/❌；A/B/C + 235 照跑（§1 不硬套 ETF 規則到個股）。
    """
    if weekly_close is None or len(weekly_close) == 0:
        raise ValueError(f"{ticker}: weekly_close 為空,無法評估（§1 不補假資料）")

    z = bollinger_z(weekly_close)
    ma4 = week_ma(weekly_close, T.MA_MONTH_WEEKS)
    ma13 = week_ma(weekly_close, T.MA_QUARTER_WEEKS)
    ma52 = week_ma(weekly_close, T.MA_YEAR_WEEKS)
    last_close = float(weekly_close.iloc[-1])
    _is_etf = asset_kind == T.KIND_ETF

    fa = health_a(total_return_1y_pct, annual_yield_pct)
    fb = health_b(sharpe)
    fc = health_c(weekly_close)
    fd = health_d(premium_pct) if _is_etf else Flag("⚪", "個股不適用（無折溢價/iNAV）", miss_reason=SS.MISS_NOT_APPLICABLE)
    lt = light_235(vix=vix, weekly_close=last_close, ma4w=ma4, ma13w=ma13, ma52w=ma52, z=z)
    if _is_etf:
        sc = screen_333(inception_years=inception_years, ann_return_3y_pct=ann_return_3y_pct,
                        cum_return_3y_pct=cum_return_3y_pct, peer_ranks=peer_ranks)
    else:                            # 個股：3-3-3 為 ETF/基金挑選規則,不適用
        sc = Screen333(passed=False, inception_ok=None, return_ok=None, peer_ok=None,
                       detail="個股不適用（3-3-3 為 ETF/基金挑選原則）")

    return HoldingAssessment(
        ticker=ticker, name=name, asset_class=asset_class, asset_kind=asset_kind,
        health_a=fa, health_b=fb, health_c=fc, health_d=fd,
        light=lt, screen=sc, worst_health=_worst_level(fa, fb, fc, fd))


def suggest_action(a: HoldingAssessment) -> str:
    """依優先序給單一建議（純函式）：汰弱 > 停利 > 趨勢暫停 > 加碼 > 高溢價 > 巡航。

    ⚠️ 存股防守邏輯：即使 235 亮加碼燈,若健檢 C「趨勢轉弱」→ **暫停加碼**（不追）。
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


# ── 個股汰換評估（財報體檢為主 · KD 為輔）─────────────────────────────────
@dataclass(frozen=True)
class StockAssessment:
    """個股「是否更換」評估（§ user 2026-08：個股改走 財報體檢 + KD,不套 235/3-3-3）。"""
    ticker: str
    name: str
    asset_class: str
    mj_grade: str | None             # A+/A/B/B+/C/F；None = 財報資料不足
    mj_score_pct: int | None
    mj_headline: str
    mj_fail_items: list[str]
    kd_k: float | None
    kd_d: float | None
    kd_label: str                    # 高檔鈍化/死亡交叉/... 或「無」/「資料不足」
    kd_cross: str | None             # golden / death / None
    swap_level: str                  # 🔴換出 / 🟡留意 / 🟢續抱 / ⚪資料不足
    swap_action: str
    trend_verdict: dict | None = None    # B3:財報趨勢(盈轉虧/逐季惡化)diff_fin_health 摘要


def assess_stock(*, ticker: str, name: str, asset_class: str,
                 mj_grade: str | None, mj_score_pct: int | None,
                 mj_headline: str, mj_fail_items: list[str] | None,
                 kd: dict | None, trend: dict | None = None) -> StockAssessment:
    """個股汰換判定（純函式,財報為主 · KD 為輔 · 財報趨勢提前預警）。

    決策（§ user 2026-08 核准）：
    - **財報 grade 決定汰弱**：grade ∈ STOCK_SWAP_GRADES(C/F) → 建議換出。
    - **財報趨勢(B3,v19.198)**：grade 尚 OK 但**盈轉虧 / 逐季多項轉差**(is_breakdown)→ 在
      grade 掉到 C 之前就提前 🟡 減碼觀察（user 核准「允許改判定」）。
    - **KD 只當進出場時機輔證**：死亡交叉 / 頂背離 = 賣點確認；黃金交叉 / 底背離 / 低檔鈍化
      = 轉強（留 / 分批）；高檔鈍化 = 強勢續抱。
    §1：財報資料不足 → grade=None → 標「資料不足」僅供 KD 參考,不猜、不捏 grade。
    """
    kd = kd or {}
    kd_label = str(kd.get("label") or ("資料不足" if not kd else "無"))
    cross = kd.get("cross")
    bearish_kd = (cross == "death") or bool(kd.get("bearish_divergence"))
    bullish_kd = ((cross == "golden") or bool(kd.get("bullish_divergence"))
                  or bool(kd.get("low_passivation")))
    strong_kd = bool(kd.get("high_passivation"))
    _fails = list(mj_fail_items or [])
    _fail_txt = "、".join(_fails[:3])
    trend = trend or {}
    _breakdown = bool(trend.get("is_breakdown"))     # 盈轉虧 / 逐季多項轉差
    _turnaround = bool(trend.get("is_turnaround"))   # 虧轉盈 / 逐季改善

    if mj_grade is None or mj_grade not in T.STOCK_HEALTH_GRADES:
        # 缺財報 或 grade 非已知分級（上游契約漂移/髒值）→ 不對不可信 grade 假裝有結論
        level = "⚪"
        action = f"⚪ 財報資料不足,僅供 KD 參考：{kd_label}"
    elif mj_grade in T.STOCK_SWAP_GRADES:            # 基本面汰弱（C/F）
        _bd = "，且本業由盈轉虧" if _breakdown else ""
        if bearish_kd:
            level = "🔴"
            action = (f"🔴 建議換出：財報 {mj_grade}"
                      + (f"（{_fail_txt}）" if _fail_txt else "")
                      + f" + KD 轉弱（{kd_label}）賣點確認{_bd}")
        elif bullish_kd:
            level = "🟡"
            action = (f"🟡 財報弱（{mj_grade}）但 KD 轉強（{kd_label}）→ 分批換 / 再觀察{_bd}")
        else:
            level = "🔴"
            action = (f"🔴 建議換出：財報體質 {mj_grade}"
                      + (f"（{_fail_txt}）" if _fail_txt else "") + _bd)
    elif _breakdown:                                 # B3:基本面 OK 但本業由盈轉虧 → 提前預警
        level = "🟡"
        action = (f"🟡 財報 {mj_grade} 但本業由盈轉虧 → "
                  f"減碼觀察、勿加碼（趁 grade 未掉到 C 前）")
    else:                                            # 基本面 OK（A+/A/B/B+）且無惡化
        _ta = "，本業由虧轉盈" if _turnaround else ""
        if bearish_kd:
            level = "🟡"
            action = (f"🟡 財報佳（{mj_grade}）但 KD 短線轉弱（{kd_label}）→ 留意、暫不加碼{_ta}")
        elif strong_kd:
            level = "🟢"
            action = f"🟢 強勢續抱：財報 {mj_grade} + KD 高檔鈍化{_ta}"
        else:
            _kd_txt = f"｜KD {kd_label}" if kd_label not in ("無", "資料不足") else ""
            level = "🟢"
            action = f"🟢 續抱：財報 {mj_grade}{_kd_txt}{_ta}"

    return StockAssessment(
        ticker=ticker, name=name, asset_class=asset_class,
        mj_grade=mj_grade, mj_score_pct=mj_score_pct, mj_headline=mj_headline,
        mj_fail_items=_fails,
        kd_k=kd.get("k"), kd_d=kd.get("d"), kd_label=kd_label, kd_cross=cross,
        swap_level=level, swap_action=action,
        trend_verdict=(trend or None))
