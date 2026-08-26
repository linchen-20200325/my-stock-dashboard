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
from shared.unified_verdict_thresholds import VERDICT_ICON, fin_trend_icon
from src.compute.scoring.unified_verdict import fundamental_grade_to_state


#: L2 **從未為這盞燈判過等級**時 `LightCell.level` 的值。
#:
#: 硬生一個等級出來就是新判燈（§1）,所以這裡誠實留空 —— 消費端看到空字串就知道
#: 「這格沒有判定可以填色」,而不是拿到一個看起來像判定、其實是本層發明的東西。
#:
#: ⚠️ 2026-08-25(B3)更正:原註寫「個股 4 盞裡有 3 盞（財報體檢 / 財報趨勢 / KD）
#: 是這種情況」—— 現在**只剩 KD 一盞**。財報體檢與財報趨勢的判定**本來就存在**
#: (前者 `unified_verdict.fundamental_grade_to_state`,後者 `diff_fin_health` 的
#: 四段 verdict),只是沒有被搬進燈裡;B3 把既有判定接上,**沒有發明新門檻**。
#: KD 沒有接上是因為它**根本沒有判燈邏輯**(要新造),那是另一件事。
LEVEL_UNJUDGED = ""


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


def week_ma_series(weekly_close: pd.Series, period_weeks: int) -> pd.Series:
    """N 週均線的**整條序列**版（`week_ma()` 的序列擴充,供走勢圖用）。

    與純量版**同源**:第 i 點 ≡ `week_ma(weekly_close.iloc[:i + 1], period_weeks)`,
    故 `week_ma_series(wk, N).iloc[-1]` 與 `week_ma(wk, N)` 相等（§4.3 對帳,
    `tests/test_dividend_station_series.py` 以 `math.isclose` 釘住,不用 `==`）。

    缺值語意（§1,逐條對齊純量版）:

    - **週數不足**（前 N−1 點）→ `NaN` **留白**。純量版在這種情況回 `None`;序列版
      沒有「回 None」這個位置,對應的誠實表示就是留白。**不 ffill、不補 0。**
    - **窗內有 NaN 破洞** → 與純量版一致:**跳過 NaN 取其餘平均**。純量版用
      `Series.mean()`（pandas 預設 `skipna=True`）,所以這裡用
      `rolling(..., min_periods=1)` 取得同一種 skipna 行為,再把前 N−1 點遮回 NaN
      補上「週數不足」那道關。⚠️ 直接寫 `rolling(N)`（等於 `min_periods=N`）會讓
      **整個窗**因為一個破洞就變 NaN —— 那是**另一把尺**,畫出來的線會跟燈用的
      均線對不起來。
    - **窗內全 NaN** → `NaN`（純量版此時算出的也是 `float('nan')` 而非 `None`）。
    - **輸入為 `None` / 空序列** → 回**空 Series**（float64）,不 raise。純量版回
      `None`;序列版的回傳型別是 Series,「沒有值」的對應物是空序列。（會 raise 的是
      `weekly_closes()`,因為它的契約是「一定要有日線才談得下去」;`week_ma` 這一族
      的契約是「算不出來就說算不出來」。）

    `period_weeks` < 1 → `raise ValueError`(§1:視窗長度無意義,不靜默給結果)。
    視窗長度請從 L0 `shared.dividend_station_thresholds` 引入(§3.3),勿 inline。
    """
    if period_weeks < 1:
        raise ValueError(f"week_ma_series: period_weeks 需 >= 1,收到 {period_weeks}")
    s = pd.Series(dtype="float64") if weekly_close is None else pd.Series(weekly_close, dtype="float64")
    if s.empty:
        return s
    ma = s.rolling(period_weeks, min_periods=1).mean()
    ma.iloc[: period_weeks - 1] = math.nan     # 週數不足 → 留白（不 ffill、不補 0）
    return ma


def bollinger_z_series(weekly_close: pd.Series,
                       period_weeks: int = T.BOLL_PERIOD_WEEKS) -> pd.Series:
    """布林標準差位階 z 的**整條序列**版（`bollinger_z()` 的序列擴充,供走勢圖用）。

    z_i =（週收_i − N週均_i）/ N週std_i,**母體標準差 `ddof=0`**,視窗 N 預設
    `T.BOLL_PERIOD_WEEKS` —— 與純量版**逐字同源**,故
    `bollinger_z_series(wk).iloc[-1]` 與 `bollinger_z(wk)` 相等（§4.3 對帳,測試釘住）。

    ⚠️ **不要**改用 `shared.stats_helpers` 的 `zscore`（全序列 mean/std）或
    `robust_z`（rolling median/MAD）—— 兩者公式都與本函式不同,拿來畫圖等於在同一頁
    上多放一把尺,線上的 z 會跟 235 燈用的 z 對不起來。

    缺值語意（§1,逐條對齊純量版的三條 `None` 路徑）:

    - **週數不足**（前 N−1 點）→ `NaN` **留白**（純量版回 `None`）。不 ffill、不補 0。
    - **NaN / inf 污染**(該點週收、其窗均、其窗 std 任一非有限)→ `NaN`。純量版是
      `math.isfinite` 三連檢後回 `None`,序列版同樣三個分量逐點檢查。**不可回 inf**,
      也不可讓 NaN 混進去被下游誤當成「z 很低 = 全清」(稽核 L5 同一個坑)。
    - **std ≈ 0**(一條水平線;判準 `|std| <= T.FLOAT_ABS_TOL`,與純量版
      `math.isclose(sd, 0.0, abs_tol=T.FLOAT_ABS_TOL)` 互補)→ `NaN`。
      實作上是**先把分母遮成 NaN 再除**,而不是除完再修 —— 除以近 0 會先炸出 ±inf
      (§4.4「大數除以小數」須 guard),遮分母讓那個 inf 根本不會產生。
    - **窗內有 NaN 破洞但該點與統計量仍有限** → 與純量版一致,`mean`/`std` **跳過
      NaN** 照算（同 `week_ma_series` 的說明,靠 `min_periods=1` + 前 N−1 遮罩達成）。
    - **輸入為 `None` / 空序列** → 回**空 Series**(float64),不 raise;整條全 NaN
      的輸入 → 回**等長全 NaN**。理由同 `week_ma_series`:與純量兄弟語意對齊。

    `period_weeks` < 1 → `raise ValueError`。視窗長度自 L0 引入,勿 inline(§3.3)。
    """
    if period_weeks < 1:
        raise ValueError(f"bollinger_z_series: period_weeks 需 >= 1,收到 {period_weeks}")
    s = pd.Series(dtype="float64") if weekly_close is None else pd.Series(weekly_close, dtype="float64")
    if s.empty:
        return s
    ma = s.rolling(period_weeks, min_periods=1).mean()
    sd = s.rolling(period_weeks, min_periods=1).std(ddof=0)
    # 三個分量都要有限(對齊純量版 math.isfinite 三連檢);`< inf` 對 NaN 亦為 False。
    usable = ((s.abs() < math.inf) & (ma.abs() < math.inf) & (sd.abs() < math.inf)
              & (sd.abs() > T.FLOAT_ABS_TOL))       # std≈0 → 不判定(§1 不猜)
    usable.iloc[: period_weeks - 1] = False          # 週數不足 → 留白
    return (s - ma) / sd.where(usable)               # 分母先遮再除,避免 ±inf(§4.4)


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
    """A 不吃本金：近一年含息總報酬 < 年化配息率 → 🔴 賺息賠本（吃本金）。

    ⚠️ 這盞燈**兩個輸入的缺法完全不同**,不能共用一個缺值原因（2026-08-25 稽核）：
    - 缺總報酬 → 上游是「日線回推 365 天取不到起點」= 日線歷史不足一年 = 新上市。
      標「可以重跑一次」是錯的指引:重跑一百次,新上市的 ETF 也不會多出一年歷史。
    - 缺配息率 → 上游是配息抓取失敗（該檔可能根本沒配息紀錄,也可能來源這輪掛了）,
      重跑確實有機會補回來。
    兩者皆缺 → 取較根本者（`most_fundamental_miss`,歷史不足擋在前面）。
    **不改判燈**:三種缺法一律 ⚪、一律不判定,只是各自說出自己為什麼缺。
    """
    if total_return_1y_pct is None and annual_yield_pct is None:
        return Flag("⚪", "A 資料不足（近一年報酬與配息率都缺）",
                    miss_reason=SS.most_fundamental_miss(
                        (SS.MISS_NOT_ENOUGH, SS.MISS_NO_INPUT)))
    if total_return_1y_pct is None:
        return Flag("⚪", "A 資料不足（缺近一年總報酬 —— 日線歷史不足一年）",
                    miss_reason=SS.MISS_NOT_ENOUGH)
    if annual_yield_pct is None:
        return Flag("⚪", "A 資料不足（缺年化配息率 —— 配息沒抓到）",
                    miss_reason=SS.MISS_NO_INPUT)
    if total_return_1y_pct < annual_yield_pct:
        return Flag("🔴", f"賺息賠本：年報酬 {total_return_1y_pct:.1f}% < 配息率 "
                          f"{annual_yield_pct:.1f}%（吃到本金）")
    return Flag("🟢", f"未吃本金：年報酬 {total_return_1y_pct:.1f}% ≥ 配息率 "
                      f"{annual_yield_pct:.1f}%")


def health_b(sharpe: float | None) -> Flag:
    """B 夏普：Sharpe < 0 → 🔴 承擔風險無超額報酬（ETF 亦套用,v19.166）。

    ⚠️ `sharpe=None` **不是**「沒抓到」（2026-08-25 稽核更正）：production 的唯一來源是
    `sharpe_weekly(weekly, ...)`,而它回 None 只有三條路 —— 週數不足、報酬筆數不足、
    波動≈0（算式分母為零）。三條都是「有資料但算不出來」,沒有一條是抓取失敗
    （抓取失敗的話 `assess_holding` 早在週K 為空時就 raise 了）。實測 health_b 與
    health_c 在**完全相同的週數**翻燈（13 週 ⚪ / 14 週 🟢）,同一個病因不該標成兩種原因。
    標成「可以重跑一次」對新上市 ETF 是錯誤指引 —— 該等的是時間,不是重跑。
    """
    if sharpe is None:
        return Flag("⚪", "B 無夏普（週數不足或波動為零,算不出來）",
                    miss_reason=SS.MISS_NOT_ENOUGH)
    if sharpe < T.SHARPE_NEG_THRESHOLD:
        return Flag("🔴", f"Sharpe {sharpe:.2f} < 0：承擔風險卻無超額報酬")
    return Flag("🟢", f"Sharpe {sharpe:.2f} ≥ 0")


def health_c(weekly_close: pd.Series) -> Flag:
    """C 趨勢防守：週收 < 13週季線 且 季線下彎 → 🟡 趨勢轉弱,暫停加碼。"""
    ma13 = week_ma(weekly_close, T.MA_QUARTER_WEEKS)
    slope = week_ma_slope(weekly_close, T.MA_QUARTER_WEEKS)
    if ma13 is None or slope is None:
        # 13 走 SSOT:門檻改了訊息要跟著改,否則畫面會出現「規格說 13、實作用別的」
        return Flag("⚪", f"C 週數不足（<{T.MA_QUARTER_WEEKS}週季線）",
                    miss_reason=SS.MISS_NOT_ENOUGH)
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
    #: 三個軸(VIX / 週線 / 布林 z)**全部不可用**時填 `MISS_NO_INPUT`。
    #: ⚠️ 這是 ⚪ 濫用最危險的一處:三軸全空時 `conds` 為空 → 落到
    #: `LIGHT_CRUISE`,畫面顯示「⚪ 巡航:維持定期定額」——
    #: **什麼都沒抓到，卻告訴使用者一切正常、繼續買**。
    #: 本欄不改判燈結果(仍是 cruise),只讓消費端能把這種 cruise
    #: 跟「真的很平靜」的 cruise 分開顯示(§1)。
    miss_reason: str = ""
    #: 這盞燈**實際用到**的判斷軸（`SS.LIGHT235_AXES` 的子集,順序固定）。
    #:
    #: 為什麼要有這欄:235 是三取一,少一個軸燈**照樣會亮** —— 只是它的根據變薄了。
    #: 「3 個依據都同意現在很平靜」跟「只剩布林能看,它說還好」在畫面上原本
    #: 長得一模一樣,而後者其實是 station_specs 四態裡的 **degraded**（有值、燈會亮、
    #: 但依據不完整）。消費端顯示 `len(axes_used)` / `len(SS.LIGHT235_AXES)` 即可揭露。
    #:
    #: 為什麼用「軸名 tuple」而不是「可用軸數量 int」:
    #:   (1) 少了哪一軸決定使用者該做什麼 —— 缺 VIX 是總經來源掛了(重跑或看 Tab1),
    #:       缺週線是這檔歷史太短(等時間),數量講不出這個差別;
    #:   (2) tuple 是 immutable,放進 frozen dataclass 不需要 default_factory,
    #:       也不會被消費端就地改掉。
    axes_used: tuple[str, ...] = ()


def light_235(*, vix: float | None, weekly_close: float | None,
              ma4w: float | None, ma13w: float | None, ma52w: float | None,
              z: float | None) -> Light235:
    """依「VIX × 週線 × 20週布林」三取一,取最嚴重那一盞。純函式。

    參數皆為**最新值純量**（weekly_close = 最新週收）。缺值不觸發該條件（§1）。
    ⚠️ `weekly_close` 在這裡是**純量**（最新週收）,不是序列 —— 別被名字騙了。

    ## 逐軸可用性（2026-08-25 稽核修正）

    原本只在「vix / z / weekly_close **三個都是 None**」時才標缺資料,那個條件
    在 production **永遠為 False**:唯一的呼叫端 `assess_holding` 會先把空序列
    raise 掉,再傳 `float(weekly_close.iloc[-1])` 進來 —— 這個參數保證非 None。
    實測 21,168 組真實輸入,`miss_reason` 無一非空 = 整段防護等於不存在。

    另外 `NaN` 也躲得過:`float("nan") is not None` 為真,但 NaN 與任何門檻比較
    都是 False → 該軸**靜默失效**卻不算缺資料。「沒判」長得跟「判了沒事」一樣,
    正是 §1 要擋的東西。

    故改為**逐軸**判可用性（見下方 `_ok`）。判燈邏輯一個字都沒動 —— 缺值仍然
    「不觸發該條件」（這是對的）,只是把「為什麼沒觸發」記下來。
    """
    conds: list[tuple[str, str]] = []

    def _ok(v: float | None) -> bool:
        """一個軸的輸入可不可用:有值**且**是有限數（NaN / ±inf 一律當沒有）。

        刻意不做 `float(v)` 轉型:非數值型別（如上游誤傳字串）應該跟改動前一樣
        在這裡就 `TypeError` 炸出來,而不是被轉型「救回來」變成一個假的可用軸（§1）。
        """
        return v is not None and math.isfinite(v)

    # 軸的判定順序刻意等同 `SS.LIGHT235_AXES` → `axes_used` 天生就是規範順序。
    _axes: list[str] = []
    if _ok(vix):
        _axes.append(SS.AXIS_VIX)
    # 週線軸要**兩邊都有**才算可用:只有週收沒有均線比不出高低,只有均線沒有週收也一樣。
    # 三條均線任一條在就夠(4/13/52 週各自對應燈一/燈二/燈三,不必湊齊)。
    if _ok(weekly_close) and any(_ok(m) for m in (ma4w, ma13w, ma52w)):
        _axes.append(SS.AXIS_WEEKLY)
    if _ok(z):
        _axes.append(SS.AXIS_BOLL)
    axes_used = tuple(_axes)
    _missing_axes = tuple(a for a in SS.LIGHT235_AXES if a not in axes_used)
    # 一軸都不可用 → 這盞燈沒有任何依據。`conds` 此時必然為空（所有條件都要求
    # 對應軸有可比的有限值）→ 必落 cruise 分支,所以這裡填了不會影響其他燈。
    _miss = "" if axes_used else SS.MISS_NO_INPUT

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
                        deploy_pct=0.0, reasons=[_tp_txt], take_profit=take_profit,
                        axes_used=axes_used)     # 停利只看布林軸,但仍如實回報用了哪幾軸

    if conds:
        best = max((c[0] for c in conds), key=lambda l: T._SEVERITY[l])
        reasons = [r for (l, r) in conds if l == best]
    else:
        best = T.LIGHT_CRUISE
        # ⚠️ 區分兩種 cruise:軸真的都沒觸發(平靜) vs 根本沒東西可觸發。
        #    後者原本與前者完全同形,等於「沒抓到 → 顯示一切正常、繼續買」。
        if axes_used:
            # 「均未觸發」只能宣告**實際看過的軸**。三個軸名寫死在字串裡,
            # 在 VIX 抓不到的那幾天就是在說謊（說我看過 VIX,其實沒有）。
            reasons = [f"{SS.axes_text(axes_used)} 均未觸發"
                       + (f"（缺 {SS.axes_text(_missing_axes)} 依據,"
                          f"{len(axes_used)}/{len(SS.LIGHT235_AXES)} 個依據可用）"
                          if _missing_axes else "")]
        else:
            _no_data = (f"{SS.axes_text(SS.LIGHT235_AXES)} "
                        f"{len(SS.LIGHT235_AXES)} 個判斷依據都沒有資料 —— "
                        f"不是「都沒觸發」,是沒東西可以判")
            reasons = [_no_data]

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
                    miss_reason=_miss, axes_used=axes_used)


# ── 3-3-3 挑三原則 ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class Screen333:
    passed: bool
    inception_ok: bool | None
    return_ok: bool | None
    peer_ok: bool | None
    detail: str
    #: 三個子項各自「為什麼是 ❔ 待資料」（值為 `shared.station_specs.MISS_*`）。
    #:
    #: 鍵刻意用規格表的 canonical key（`SS.KEY_SCREEN_*`）—— 消費端拿到鍵就能
    #: `SPECS_BY_KEY[k]` 查到那盞燈的 label / why / source,不必自己再維護一份對照表。
    #: **只有不可判定(None)的子項才會有鍵**:判得出來的子項不需要理由,硬塞空字串
    #: 會讓消費端誤以為它也缺（`in` 判斷就此失效）。
    #: 2026-08-25 新增。additive + 預設空 dict → 既有 positional 建構不受影響。
    miss_reasons: dict[str, str] = field(default_factory=dict)


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

    # ── 三個 ❔ 各自的病因（**不影響 passed / 三個 ok 旗標**,只是說明）─────────
    _miss: dict[str, str] = {}
    if inception_ok is None:
        # 成立年數算不出 = 上游沒給成立日/最早資料日。注意「年數不夠」不會走到這裡 ——
        # 那會算出 False（明確未過）,不是不可判定。故這裡是**輸入沒到**,不是資料不足。
        _miss[SS.KEY_SCREEN_INCEPTION] = SS.MISS_NO_INPUT
    if return_ok is None:
        # 年化與累積兩種算法**都**回 None → 上游取不到「3 年前那一天」的收盤,
        # 也就是日線歷史不足 3 年(新上市)。重跑不會生出歷史 → 是資料不足不是抓取失敗。
        _miss[SS.KEY_SCREEN_RETURN] = SS.MISS_NOT_ENOUGH
    if peer_ok is None:
        # 同儕不可判定有兩條上游路徑:
        #   (a) `peer_ranks` 整包缺 —— **主因**是同類 ETF 少於 `PEER_MIN_GROUP_SIZE`
        #       檔（分類表裡沒收這檔 → 直接 0 個同儕）,**少數**是同儕價格抓取失敗;
        #   (b) 有 dict 但三個時間框沒湊齊 —— 該時間框有效樣本不足。
        # L2 手上只有一個 dict,分不出 (a) 的哪一種 —— 猜一個填進來才是違憲(§1)。
        # 選 `MISS_NOT_ENOUGH`:它對主因(同類檔數不夠)與 (b) 都講得對,而
        # `MISS_NO_INPUT` 的文案「可以重跑一次」對主因是**錯的指引** —— 重跑不會
        # 讓同類多出一檔 ETF。**已知代價**:少數真的抓取失敗的情況會被標成資料不足;
        # 要分出來得由 L3 把 `compute_etf_peer_ranking` 的 `_err` 帶上來(現況未帶)。
        _miss[SS.KEY_SCREEN_PEER] = SS.MISS_NOT_ENOUGH

    passed = bool(inception_ok and return_ok and peer_ok)
    parts = [
        f"成立{'✅' if inception_ok else ('❔' if inception_ok is None else '❌')}",
        f"3年報酬{'✅' if return_ok else ('❔' if return_ok is None else '❌')}",
        f"同儕前1/3{'✅' if peer_ok else ('❔' if peer_ok is None else '❌')}",
    ]
    return Screen333(passed=passed, inception_ok=inception_ok, return_ok=return_ok,
                     peer_ok=peer_ok, detail="　".join(parts), miss_reasons=_miss)


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
    """四盞健檢燈 → 最嚴重那一級（**只回等級字串**）。

    ⚠️ 這個彙總天生會丟掉「為什麼」:四盞燈都 ⚪ 時回一個裸 ⚪,原因(四種,處置各不同)
    全部消失。**刻意不在這裡合併原因** —— 這個函式回的是「等級」,塞進第二種語意會讓
    型別變成 `str | tuple`,所有 caller 都要跟著改。四個 `Flag` 本來就完整掛在
    `HoldingAssessment.health_a/b/c/d` 上,原因並沒有真的不見;真正會丟失的是
    **組表那一步**（`HoldingAssessment` → row dict 只留一個 `健檢` 字串）,
    所以補救放在 L3 `row_from_assessment`（`_health_miss` / `_miss_reason` 兩個鍵）。
    """
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
        # 三個子項同樣是 None,但病因與 ETF 的「待資料」**完全不同**:個股永遠不會
        # 有這三項,叫使用者「等時間累積」是誤導。故標 NOT_APPLICABLE（§ 不是壞掉）。
        sc = Screen333(passed=False, inception_ok=None, return_ok=None, peer_ok=None,
                       detail="個股不適用（3-3-3 為 ETF/基金挑選原則）",
                       miss_reasons={k: SS.MISS_NOT_APPLICABLE
                                     for k in (SS.KEY_SCREEN_INCEPTION,
                                               SS.KEY_SCREEN_RETURN,
                                               SS.KEY_SCREEN_PEER)})

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
    #: `swap_level=="⚪"` 時的原因（`shared.station_specs.MISS_*`）;判得出來時為空字串。
    #: 2026-08-25 新增,additive + 預設值 → 既有 positional 建構不受影響。
    miss_reason: str = ""
    #: 「財報體檢」這盞燈**自己**的等級（🟢/🟡/🔴,判不出來 → `LEVEL_UNJUDGED`）。
    #:
    #: 門檻**零新增**:走既有 SSOT `unified_verdict.fundamental_grade_to_state`
    #: (KEEP=A+/A/B+ · WATCH=B · CUT=`STOCK_SWAP_GRADES`(C/F)),已有
    #: `tests/test_unified_verdict.py::test_fundamental_grade_to_state` 逐 grade 釘死。
    #: ⚠️ 與 `swap_level` **不是同一件事**:`swap_level` 還吃 KD 與趨勢,
    #: 例如「財報 C + KD 轉強」→ `swap_level` 是 🟡,而本欄仍是 🔴(體質就是不合格)。
    health_level: str = ""
    #: 「財報趨勢」這盞燈**自己**的等級（🟢/🟡/🔴/⚪,判不出來 → `LEVEL_UNJUDGED`）。
    #:
    #: 判定**零新增**:`diff_fin_health` 的四段 verdict 早就存在,對映走 L0
    #: `unified_verdict_thresholds.fin_trend_icon()`（B3 從 L5
    #: `tab_stock_grp._FIN_VERDICT_LABEL` 上提的那一份）。
    #: ⚠️ 這盞燈在規格表標了 `discriminative=False`（只比最近兩季,看不出趨勢）——
    #: 有了等級之後那個 degraded 標記**更重要**,不是可以拿掉。
    trend_level: str = ""


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

    _miss = ""
    if mj_grade is None or mj_grade not in T.STOCK_HEALTH_GRADES:
        # 缺財報 或 grade 非已知分級（上游契約漂移/髒值）→ 不對不可信 grade 假裝有結論。
        # ⚠️ 判燈不變(兩者都是 ⚪),但**病因與處置完全不同**,不能混成一句「資料不足」:
        #   - 沒抓到（None / 空字串）→ 上游這輪沒給,重跑或等下次批次就好。
        #   - 給了值但不在分級表裡 → 是**上下游契約破了**（財報體檢引擎改了分級、
        #     或回了髒值）。這是**程式 bug 訊號**,重跑一百次都一樣,把它畫成
        #     「資料不足」等於保證沒有人會去修它。
        level = "⚪"
        if mj_grade is None or not str(mj_grade).strip():
            _miss = SS.MISS_NO_INPUT
            action = f"⚪ 財報資料不足,僅供 KD 參考：{kd_label}"
        else:
            _miss = SS.MISS_CONTRACT_DRIFT
            action = (f"⚪ 財報評等「{mj_grade}」不在已知分級內（上游契約漂移,請回報）,"
                      f"僅供 KD 參考：{kd_label}")
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

    # ── 逐盞燈自己的等級（B3）───────────────────────────────────────
    # ⚠️ 這裡**沒有新的門檻**,兩行都是把「已經存在、但沒被搬出來」的判定接上:
    #   · 財報體檢 → `fundamental_grade_to_state`(L2 統一裁決引擎既有 SSOT)
    #   · 財報趨勢 → `fin_trend_icon`(L0;B3 從 L5 `_FIN_VERDICT_LABEL` 上提)
    # 放在這裡而不是放在 `light_cells`,是因為 `light_cells` 的鐵律是「純轉換,
    # 不得重新判燈」—— 判定一律出自本函式,轉換層只原樣讀出（見該段註解）。
    # KD 刻意**不接**:它到今天為止**沒有任何判燈邏輯**(`kd_label` 是描述字串,
    # 不是等級),要接就是新造一盞燈 —— user 2026-08-25 裁示切出去另案。
    _health_level = VERDICT_ICON.get(fundamental_grade_to_state(mj_grade),
                                     LEVEL_UNJUDGED)
    _trend_level = fin_trend_icon(trend.get("verdict")) or LEVEL_UNJUDGED

    return StockAssessment(
        ticker=ticker, name=name, asset_class=asset_class,
        mj_grade=mj_grade, mj_score_pct=mj_score_pct, mj_headline=mj_headline,
        mj_fail_items=_fails,
        kd_k=kd.get("k"), kd_d=kd.get("d"), kd_label=kd_label, kd_cross=cross,
        swap_level=level, swap_action=action,
        trend_verdict=(trend or None), miss_reason=_miss,
        health_level=_health_level, trend_level=_trend_level)


# ── 逐盞燈 → 可程式判讀的格子（**純轉換,不重新判燈**）───────────────────
#
# 為什麼需要這一段:組表那一步（L3 `row_from_assessment`）把四盞健檢燈壓成一個
# `worst_health`,把 3-3-3 三個子項壓成一個「✅合格 / ❌未過 / ❔待資料」字串 ——
# **逐盞燈的判定在那裡整個消失**。畫面要畫「逐盞燈的格子牆」或算「N/M 盞可信度」,
# 現況唯一的來源是 `_detail` 裡的中文 msg 字串,而解析字串太脆弱（改一個字就壞,
# 且不會有任何錯誤 —— 見 `Flag.miss_reason` 的註解）。
#
# ⚠️ 本段**一個判斷式都沒有新增**。所有 `level` 一律從既有的 `Flag` / `Light235` /
#    `Screen333` / `StockAssessment` **原樣讀出**,`state` 一律走 L0
#    `station_specs.classify_state()`。改判燈規則不該動這裡,改揭露方式才動這裡。

#: `Screen333` 三個 bool 子項的符號 —— **沿用 `Screen333.detail` 已經在用的那一組**。
#:
#: 為什麼不換成 🟢/🔴/⚪:3-3-3 是「挑選條件過不過」,不是健康度告警 ——
#: `_worst_level` 刻意只收四盞健檢 `Flag`,3-3-3 從來不參與 `worst_health`。
#: 把「未過」畫成 🔴,等於在格子牆上憑空多出一盞主表沒有的紅燈:那是**新判斷**,
#: 不是轉換（§1）。要不要把它上色成紅,是消費端的呈現決定,不該由本層偷渡。
_SCREEN_SYMBOL: dict = {True: "✅", False: "❌", None: "❔"}


@dataclass(frozen=True)
class LightCell:
    """一盞燈的「判定 ＋ 這盞燈可不可信」,給畫面逐格渲染用。

    - `key`:規格表 canonical key（`station_specs.KEY_*`）→ 消費端可
      `SS.SPECS_BY_KEY[key]` 查到 label / why / source / threshold_text,
      不必自己再維護一份對照表。
    - `level`:**該盞燈自己的判定符號,原樣搬運**。⚠️ 字母表**逐燈不同**,刻意的:
      健檢 A/B/C/D 與個股汰換是 🔴/🟡/🟢/⚪（`Flag.level` / `swap_level`）;
      235 是 `LIGHT_META` 的 icon（多一個 💰 停利）;3-3-3 三子項是 ✅/❌/❔
      （見 `_SCREEN_SYMBOL` 的理由）;沒有判定的是 `LEVEL_UNJUDGED`（空字串）。
      統一成同一組符號需要決定「未過算不算紅」—— 那是判斷,不是轉換。
    - `state`:四態,走 `station_specs.classify_state()`（唯一 SSOT,本層不自己判）。
    - `miss_reason`:`station_specs.MISS_*`,原樣搬運;上游沒登記就是空字串
      （**不猜** —— 挑錯 `MISS_*` 會給出「重跑一次就好」這種錯誤指引）。
    - `axes_used`:只有 235 燈有值（`SS.LIGHT235_AXES` 的子集,順序固定）。
      消費端用 `len(axes_used)/len(SS.LIGHT235_AXES)` 揭露「這盞燈幾個依據可用」。

    frozen dataclass 而非 dict:與本檔既有 `Flag` / `Light235` / `Screen333` 同一慣例,
    且欄名打錯會當場 `AttributeError`（dict 的 `.get("levl")` 只會靜默回 None,
    正是 §1 要擋的「看起來成功」）。
    """

    key: str
    level: str
    state: str
    miss_reason: str = ""
    axes_used: tuple[str, ...] = ()


def _cell(spec, *, level: str, has_value: bool, reason: str,
          axes: tuple[str, ...] = ()) -> LightCell:
    """組一格。`state` 一律由 L0 `classify_state` 決定,本層不自己判四態。"""
    return LightCell(key=spec.key, level=level, miss_reason=reason, axes_used=axes,
                     state=SS.classify_state(spec, has_value=has_value, reason=reason))


def _etf_light_cells(a: HoldingAssessment) -> tuple[LightCell, ...]:
    """ETF 8 盞（健檢 A/B/C/D ＋ 235 ＋ 3-3-3 三子項）。

    燈的清單走 `SS.specs_for(T.KIND_ETF)`,**不在這裡自己列** —— 規格表加一盞、
    這裡沒接上,下面的 `raise` 會當場炸（§1）,而不是畫面上永遠空著一格沒人發現。
    """
    _flags = {SS.KEY_HEALTH_A: a.health_a, SS.KEY_HEALTH_B: a.health_b,
              SS.KEY_HEALTH_C: a.health_c, SS.KEY_HEALTH_D: a.health_d}
    # `Screen333` 三個子項是 bool | None:None = 不可判定,對應規格表的 missing。
    _screen = {SS.KEY_SCREEN_INCEPTION: a.screen.inception_ok,
               SS.KEY_SCREEN_RETURN: a.screen.return_ok,
               SS.KEY_SCREEN_PEER: a.screen.peer_ok}

    _out: list[LightCell] = []
    for spec in SS.specs_for(T.KIND_ETF):
        if spec.key in _flags:
            _f = _flags[spec.key]
            # ⚪ 是 `Flag` 對「不判定」的唯一表示（四個 health_* 皆然）→ 直接當 has_value。
            _out.append(_cell(spec, level=_f.level, has_value=_f.level != "⚪",
                              reason=_f.miss_reason))
        elif spec.key == SS.KEY_LIGHT235:
            # 235 永遠有 light（三軸全空時落 cruise）→ 「有沒有值」看的是**有沒有依據**,
            # 也就是 `axes_used`。這正是「什麼都沒抓到卻顯示⚪巡航、繼續買」那個坑。
            _out.append(_cell(spec, level=a.light.icon, has_value=bool(a.light.axes_used),
                              reason=a.light.miss_reason, axes=a.light.axes_used))
        elif spec.key in _screen:
            _ok = _screen[spec.key]
            _out.append(_cell(spec, level=_SCREEN_SYMBOL[_ok], has_value=_ok is not None,
                              reason=a.screen.miss_reasons.get(spec.key, "")))
        else:
            raise KeyError(
                f"light_cells: 規格表有 ETF 燈 {spec.key!r} 但本函式沒接上 —— "
                f"新增 StationSpec 時必須同步這裡（§1 寧可炸掉,不可畫一格永遠空白的燈）")
    return tuple(_out)


def _stock_light_cells(sa: StockAssessment) -> tuple[LightCell, ...]:
    """個股 4 盞（財報體檢 / 財報趨勢 / KD / 汰換建議）。

    ⚠️ **本函式一個判斷式都沒有**:四盞燈的 `level` 全部從 `StockAssessment`
    原樣讀出（`health_level` / `trend_level` / `swap_level`）。判定一律在
    `assess_stock` 裡下 —— 這是本段的鐵律,也是 `tests/test_station_light_cells.py`
    整個檔案的前提。

    ⚠️ **KD 那一盞仍然是 `LEVEL_UNJUDGED`**,而且理由與另外兩盞不同:財報體檢與
    財報趨勢的判定**本來就存在**(只是沒被搬進燈裡),KD 則是**根本沒有判燈邏輯**
    (`kd_label` 是「高檔鈍化」這種描述字串,不是等級)。要給它等級 = 新造一盞燈,
    §1 禁止在轉換層做這件事;user 2026-08-25 裁示切出去另案。
    """
    _out: list[LightCell] = []
    for spec in SS.specs_for(T.KIND_STOCK):
        if spec.key == SS.KEY_STOCK_HEALTH:
            # `sa.miss_reason` 就是「grade 不可用」的登記（`assess_stock` 只在
            # grade 缺 / 不在分級表時才填）→ 直接讀,不在這裡重寫一次同樣的判斷。
            _out.append(_cell(spec, level=sa.health_level, has_value=not sa.miss_reason,
                              reason=sa.miss_reason))
        elif spec.key == SS.KEY_STOCK_TREND:
            # `assess_stock` 存的是 `trend or None` → None 就是「這輪沒有趨勢資料」。
            # 上游沒登記 MISS_* → 這裡留空,不代它挑一個（挑錯就是錯誤指引）。
            # ⚠️ `has_value` 判準**刻意不動**:仍看有沒有趨勢資料,不看有沒有等級。
            # 規格表的 `discriminative=False` → `classify_state` 會判 degraded,
            # 那個「門檻已失準（只比兩季）」的標記必須跟著等級一起出去(B3 硬要求)。
            _out.append(_cell(spec, level=sa.trend_level,
                              has_value=sa.trend_verdict is not None, reason=""))
        elif spec.key == SS.KEY_STOCK_KD:
            # 與 `stock_row_from_assessment` 的 KD 欄同一個判準:k / d 皆在才算有值
            # （只有 label 沒有 K/D 值時,那一欄顯示的就是「資料不足」）。
            _out.append(_cell(spec, level=LEVEL_UNJUDGED,
                              has_value=sa.kd_k is not None and sa.kd_d is not None,
                              reason=""))
        elif spec.key == SS.KEY_STOCK_SWAP:
            # 唯一有既有判定的一盞。⚪ 是 `assess_stock` 對「不判定」的表示。
            _out.append(_cell(spec, level=sa.swap_level, has_value=sa.swap_level != "⚪",
                              reason=sa.miss_reason))
        else:
            raise KeyError(
                f"light_cells: 規格表有個股燈 {spec.key!r} 但本函式沒接上 —— "
                f"新增 StationSpec 時必須同步這裡（§1 寧可炸掉,不可畫一格永遠空白的燈）")
    return tuple(_out)


def light_cells(assessment) -> tuple[LightCell, ...]:
    """`HoldingAssessment` / `StockAssessment` → 逐盞燈的格子。**純轉換**。

    燈的清單由 **assessment 的型別**決定,不是由 ticker 的 `asset_kind` 決定 ——
    這兩件事在本專案裡不總是一致:
      - `HoldingAssessment` 結構上**永遠**帶 ETF 那 8 盞。`assess_holding` 允許
        `asset_kind=stock`（此時 D 折溢價 / 3-3-3 標 `MISS_NOT_APPLICABLE`）,
        但它身上並沒有 `specs_for(KIND_STOCK)` 的那 4 盞可以回。
      - `StockAssessment` 結構上**永遠**帶個股那 4 盞。
    production 的 `build_station_rows` 本來就是二選一分流（`ak == KIND_STOCK` 走
    `assess_stock`）,故兩者一致;會不一致的是直接呼叫 L2 的測試/工具路徑。
    """
    if isinstance(assessment, HoldingAssessment):
        return _etf_light_cells(assessment)
    if isinstance(assessment, StockAssessment):
        return _stock_light_cells(assessment)
    raise TypeError(
        f"light_cells: 不認得的 assessment 型別 {type(assessment).__name__} —— "
        f"只吃 HoldingAssessment / StockAssessment（§1 不猜）")


def missing_light_cells(asset_kind: str, *, reason: str) -> tuple[LightCell, ...]:
    """**整檔**沒有 assessment（抓取/評估失敗）→ 該類別每一盞燈都標同一個原因。

    為什麼要有這個而不是讓那些列沒有 `_lights`:第 1 層的「N/M 盞」可信度是把
    每一列的格子加總 —— 抓取失敗的列若整個不出現,分母會**悄悄變小**,畫面就會
    顯示「可信度很高」（因為算不出來的都不算了）。那正是 §1 要擋的東西。

    ⚠️ **不要把「每一盞燈都要出現」讀成「每一盞燈都進分母」** —— 是兩件事:
    本函式負責讓這一列**照樣產出該類別的全部燈格**(不缺席);至於哪幾格算進
    「有判定」的分母,由消費端 `render.station_cards._in_judged_denominator`
    **統一**判(現況排除「結構上不適用」與規格表 `emits_level=False` 的燈,
    後者即個股 KD)。分母縮不縮水由那支函式決定,**不是**由「這一列有沒有出現」
    決定 —— 這裡缺席才是真正會讓分母悄悄變小的那種縮水。
    ⚠️ 原文此處寫死「N/40 盞」:那個 40 是某一次組合的格子總數,**分母是動態的**
    (ETF 8 盞、個股 4 盞畫在牆上而分母 3),隨持股檔數與成分改變。數字寫進敘述
    只會在下一次組合變動時變成假話,故一律不寫。

    `level` 一律 `LEVEL_UNJUDGED`:這一列**沒有任何一盞燈跑過**,不是判定為 ⚪。
    """
    _kind = T.KIND_STOCK if asset_kind == T.KIND_STOCK else T.KIND_ETF
    return tuple(_cell(_s, level=LEVEL_UNJUDGED, has_value=False, reason=reason)
                 for _s in SS.specs_for(_kind))
