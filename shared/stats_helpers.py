"""shared/stats_helpers.py — 純函式股票統計 helpers(L0 Shared,v18.301)

CLAUDE.md §8.3 灰區 — daily_checklist.py 跨 L1+L2+L3 拆檔最小提取。
從 daily_checklist.py:974 提取 `calc_stats`(無 I/O 純函式,適合 L0)。

設計
----
- L0 純函式,無 I/O,無 streamlit
- 接 DataFrame(close/Close 欄)→ 回 dict(last/pct/status/chg)
- 'status' 三態:多頭排列↑ / 空頭排列↓ / 整理中

歷史
----
原位置 daily_checklist.py:974(L1+L2+L3 混雜檔),v18.301 提取到 shared/。
為向後相容,daily_checklist 仍 re-export(`from shared.stats_helpers import calc_stats`)。
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd


def zscore(s: "pd.Series") -> "pd.Series":
    """標準分數 z = (s - mean) / std(L0 SSOT)。

    D2 v18.437 收斂:統一原 `macro_core.zscore` + `multi_factor_optimization._zscore`
    兩份近乎逐字相同實作(僅 std=0 guard 寫法略異)。採較廣的 `not np.isfinite` guard
    (同時涵蓋 NaN 與 inf),避免除零 / 不捏造。

    參數:
        s: pd.Series 數值序列

    回傳:
        pd.Series z-score;空序列原樣返回;std=0 或非有限 → 全 0(同 index)。
    """
    if s.empty:
        return s
    sd = float(s.std())
    if not np.isfinite(sd) or sd == 0:
        return pd.Series(0.0, index=s.index)
    return (s - s.mean()) / sd


def calc_stats(df: Any) -> Optional[dict]:
    """計算股票統計數據(last / pct / status / chg)。

    Parameters
    ----------
    df : pandas.DataFrame | None
        含 'close' 或 'Close' 欄位的 OHLC DataFrame。

    Returns
    -------
    dict | None
        成功:{'last': float, 'pct': float, 'status': str, 'chg': float}
        失敗(None / empty / 缺欄 / 行數 < 2):None

    status 規則
    -----------
    - last > MA5 > MA20 → '多頭排列↑'
    - last < MA5 < MA20 → '空頭排列↓'
    - 其他 → '整理中'
    """
    if df is None or df.empty:
        return None
    col = next((c for c in ['close', 'Close'] if c in df.columns), None)
    if not col:
        return None
    s = df[col].dropna()
    if len(s) < 2:
        return None
    last = float(s.iloc[-1])
    prev = float(s.iloc[-2])
    pct = (last - prev) / prev * 100 if prev else 0
    ma5 = float(s.tail(5).mean())
    ma20 = float(s.tail(20).mean()) if len(s) >= 20 else ma5
    if last > ma5 > ma20:
        status = '多頭排列↑'
    elif last < ma5 < ma20:
        status = '空頭排列↓'
    else:
        status = '整理中'
    return {
        'last': round(last, 2),
        'pct': round(pct, 2),
        'status': status,
        'chg': round(last - prev, 2),
    }


# ════════════════════════════════════════════════════════════════
# v19.170 — P1 量化方法論修正：穩健 / 滾動統計工具組
#
# 【為何新增而非改 zscore()】
# 上方 `zscore()` 是「全樣本、非滾動、無 winsorize」的母體式 z-score，
# 已被多處消費（macro_core 等），改它＝行為變更。
# 本區塊只**新增**工具，呼叫端自行決定是否採用，零回歸風險。
#
# 【本組工具解決的稽核問題】
# - P1-2 BIAS240 固定 ±20%：結構多頭下實測 +29.6% 必然誤判
#   → `rolling_pct_rank()` / 波動度標準化取代固定百分比門檻。
# - P1-3 風險情緒等權相加、成分共線 → `winsorize()` 去尾端槓桿點。
# - P1-4 缺死區：-0.06%（約 0.05σ）被判「股匯雙殺」
#   → `ewma_vol()` 估當期 σ + `signal_with_deadband()` 開死區。
#
# 全部向量化（rolling / ewm / quantile），無 Python for 迴圈。
# 本模組屬 L0：不得 import streamlit、不得 import requests。
# ════════════════════════════════════════════════════════════════

# 常態分佈下 MAD → σ 的一致性校正常數。
# 推導：X ~ N(μ, σ²) 時 MAD = median(|X − μ|) = σ·Φ⁻¹(0.75) ≈ 0.6745σ，
# 故 σ ≈ MAD / 0.6745 = 1.4826 · MAD。乘上它之後，robust_z 的尺度才與
# 傳統 (x−mean)/std 可比（同一組常態資料兩者期望值相同）。
#
# ⚠️ v19.171 誠實揭露：上述 1.4826 是為**教科書 MAD**（視窗內共用同一個中心
# med_t）推導的。`robust_z()` 實作的是**滾動近似版**（rolling MAD proxy，
# 各點減各自的滾動中位數），兩者在趨勢序列下並不等價 —— proxy 偏小，
# 故 1.4826 校正後的 z 仍會**偏大**。詳見 `robust_z()` docstring「已知偏誤」。
_MAD_TO_SIGMA: float = 1.4826


def robust_z(s: "pd.Series", window: int = 252,
             min_periods: Optional[int] = None) -> "pd.Series":
    """穩健滾動 z-score（中位數 / **rolling MAD proxy** 版，v19.170）。

    實際計算式（⚠️ 這是近似版，不是教科書 MAD）
    -------------------------------------------
        med_t   = rolling_median(x, window)
        dev_i   = |x_i − med_i|                     ← 每點減「自己那一期」的中位數
        MADp_t  = rolling_median(dev, window)       ← 再對 dev 做一次滾動中位數
        z_t     = (x_t − med_t) / (1.4826 · MADp_t)

    教科書 MAD（Hampel 1974）則是

        MAD_t   = median_{i ∈ window}( |x_i − med_t| )   ← 視窗內共用**同一個** med_t

    已知偏誤（v19.171 誠實揭露，不得再宣稱這是「標準作法」）
    ------------------------------------------------------
    兩式差在**中心**：本實作的 dev_i 減的是 med_i（隨 i 滑動），教科書減的是
    med_t（視窗末端那一個，對整個視窗固定）。

    - **平穩序列**：med_i ≈ med_t，兩者幾乎相同，偏誤可忽略。
    - **趨勢序列**：med_i 一路跟著 x_i 走，dev_i 只反映「對自己近期中位數的偏離」，
      而非「對視窗中心的偏離」→ dev 被系統性壓小 → **MADp_t < MAD_t**
      → 分母偏小 → **|z| 系統性偏大（訊號被高估、更容易誤觸門檻）**。
      趨勢越陡、window 越長，高估越明顯。
    - 因此 `_MAD_TO_SIGMA = 1.4826`（為教科書 MAD 推導的一致性常數）在此
      **只是尺度上的近似**，不保證常態下 E[MADp·1.4826] = σ。

    為何不改成教科書版
    ------------------
    教科書 MAD 需要「對每個 t 用固定的 med_t 重掃整個視窗」，pandas / numpy
    沒有對應的向量化 rolling 原語，只能走 `rolling().apply(...)` 的 Python 回呼
    ——實測慢 20~50 倍，而本函式在 `relative_thresholds` 中是逐序列熱路徑。
    取捨結論：**保留快的近似版 + 誠實標註偏誤方向**，由呼叫端在解讀
    「z 偏大」時自行留裕度；若日後有嚴格統計需求，請另開一個明確命名的
    `robust_z_exact()`，不要偷偷替換本函式的實作。

    為何需要（相對於既有 `zscore()`）
    ---------------------------------
    既有 `zscore()` 用「全樣本 mean/std」：
      1. 非滾動 → 用到未來資料（look-ahead bias），回測失真；
      2. mean/std 的 breakdown point = 0 → 一根 2020/03 崩盤棒就把整條
         序列的 σ 撐大，之後所有訊號都被壓到 ±1 以內，永遠不觸發。
    中位數 / MAD（含本近似版）的 breakdown point = 50%，對離群值免疫，
    適合金融厚尾資料 —— 這個優勢不受上述中心偏誤影響。

    Args
    ----
    s : pd.Series
        數值序列（時間遞增排序）。
    window : int
        滾動視窗長度（交易日），預設 252 ≈ 1 年。
    min_periods : int | None
        視窗內最少有效點數；None → 自動取 `max(2, window // 2)`。
        未達門檻的位置回 NaN（§1 Fail Loud：不足就不給數字，不外插）。

    真實暖機期（**比 min_periods 長很多，別誤判**）
    ---------------------------------------------
    本函式疊了**兩層** rolling：第一層 med 要 min_periods 筆才出值，
    第二層 MADp 又要 min_periods 筆**非 NaN 的 dev**。
    以預設 window=252 / min_periods=126 為例：
      - med 從第 126 筆（0-based index 125）起非 NaN；
      - dev 同步從 index 125 起非 NaN；
      - MADp 在 index t 的視窗是 [t−251, t]，其中非 NaN 的 dev 有
        `t − 124` 筆，需 ≥ 126 → t ≥ 250。
    ⇒ **第一個非 NaN 的 z 落在第 251 筆（0-based index 250）**，不是第 126 筆。
    序列長度 < 251 時本函式會全回 NaN —— 那是正確行為（樣本不足），
    呼叫端不要誤判成「函式壞了」而去填 0。

    Returns
    -------
    pd.Series
        與 `s` 同 index 的穩健 z-score。
        **MADp == 0（視窗內過半 dev 為 0）→ 該點回 NaN**，
        不除零、不填 0（填 0 等同宣稱「恰好在中位數」，是捏造）。
        空序列原樣返回。
    """
    if s.empty:
        return s
    if window < 2:
        raise ValueError(f"robust_z: window 需 >= 2,收到 {window}")
    if min_periods is None:
        min_periods = max(2, window // 2)

    med = s.rolling(window, min_periods=min_periods).median()
    # ⚠️ 這是 **rolling MAD proxy**，非教科書 MAD：
    #   本行  = median_i( |x_i − med_i| )   ← 每點各自的滾動中位數為中心
    #   教科書 = median_i( |x_i − med_t| )   ← 視窗內共用同一個 med_t
    # 兩者皆 causal（不看未來），但趨勢序列下 proxy 偏小 → z 偏大。
    # 取這個寫法純粹是為效能（教科書版只能走 rolling().apply，慢 20~50×）。
    # 詳細偏誤方向與取捨見本函式 docstring「已知偏誤」；不要把它描述成「標準作法」。
    mad = (s - med).abs().rolling(window, min_periods=min_periods).median()
    scale = _MAD_TO_SIGMA * mad
    # MAD <= 0 或非有限 → 轉 NaN（.where 條件不成立即填 NaN），下一行除法自然傳播 NaN
    scale = scale.where(np.isfinite(scale) & (scale > 0))
    return (s - med) / scale


def rolling_pct_rank(s: "pd.Series", window: int = 756) -> "pd.Series":
    """滾動百分位排名（0~1，v19.170）。

    數學式
    ------
        pr_t = rank(x_t 於 {x_{t−window+1} … x_t}) / (視窗內有效點數)

    Args
    ----
    s : pd.Series
        數值序列（時間遞增排序）。
    window : int
        滾動視窗長度（交易日），預設 **756 ≈ 3 年**（252 × 3）。
        取 3 年是為了涵蓋一輪完整的中期景氣循環，讓「現在算高還是低」
        有跨牛熊的參照，而不是只跟最近半年比。

    Returns
    -------
    pd.Series
        與 `s` 同 index、值域 [0, 1] 的分位數。1.0 = 視窗內歷史新高。
        視窗內有效點數不足 `max(20, window // 4)` → NaN（不足就不給數字）。
        空序列原樣返回。

    為何需要
    --------
    P1-1 / P1-2：融資餘額 2500/3400 億、BIAS240 ±20% 這類**絕對門檻**，
    在市值成長 / 結構多頭下會被淹沒（實測融資 5,148 億、BIAS +29.6%），
    永遠亮紅 → 資訊量 = 0。改成「相對自身歷史分位」才有鑑別力。

    效能
    ----
    使用 `rolling().rank(pct=True)`（pandas C 實作，pandas >= 1.4）。
    **不可**改寫成 `rolling().apply(lambda ...)` — 後者走 Python 回呼，
    實測慢 20~50 倍。
    """
    if s.empty:
        return s
    if window < 2:
        raise ValueError(f"rolling_pct_rank: window 需 >= 2,收到 {window}")
    min_periods = max(20, window // 4)
    # Rolling.rank 回傳「視窗內最後一個元素」的排名（pct=True → 除以視窗有效點數）
    return s.rolling(window, min_periods=min_periods).rank(pct=True)


def ewma_vol(r: "pd.Series", lam: float = 0.94) -> "pd.Series":
    """RiskMetrics EWMA 波動度（v19.170）。

    數學式
    ------
        σ²_t = λ · σ²_{t−1} + (1 − λ) · r²_{t−1}
        σ_t  = sqrt(σ²_t)

    λ = 0.94 出自 J.P. Morgan / Reuters《RiskMetrics — Technical Document》
    (4th ed., 1996) 對**日頻**資料的建議衰減因子（月頻建議 0.97）；
    等價半衰期 = ln(0.5)/ln(0.94) ≈ 11.2 個交易日。

    實作對應
    --------
        r.pow(2).ewm(alpha=1-lam, adjust=False).mean().pow(0.5)

    `adjust=False` 才是上式的遞迴形式（adjust=True 會做有限樣本再權重化，
    與 RiskMetrics 定義不同）。註：pandas 的 `ewm` 在 t 期會納入 r²_t 本身，
    與上式「用到 t−1」差一期；若需嚴格 lagged 估計，呼叫端自行 `.shift(1)`。

    Args
    ----
    r : pd.Series
        **報酬率**序列（非價格）。單位自訂（%或小數），輸出同單位。
    lam : float
        衰減因子 λ，需落在 (0, 1)。

    Returns
    -------
    pd.Series
        與 `r` 同 index 的條件波動度 σ_t（同 r 的單位）。空序列原樣返回。

    為何需要
    --------
    P1-4 死區判定需要「當期」波動尺度。用全樣本 std 會把平靜期的 σ 高估
    （被歷史崩盤撐大）、把急拉期的 σ 低估；EWMA 讓 σ 跟著市況呼吸。
    """
    if not (0.0 < lam < 1.0):
        raise ValueError(f"ewma_vol: lam 需落在 (0,1),收到 {lam}")
    if r.empty:
        return r
    return r.pow(2).ewm(alpha=1.0 - lam, adjust=False).mean().pow(0.5)


def signal_with_deadband(ret: Optional[float], sigma: Optional[float],
                         k: float = 0.5) -> str:
    """帶死區（dead-band）的方向判定（v19.170）。

    判定式
    ------
        band = k · σ
        |ret| <= band          → 'neutral'   （雜訊區，不宣稱方向）
        ret  >  band           → 'bullish'
        ret  < −band           → 'bearish'
        σ 為 None / <= 0 / 非有限、或 ret 為 None → 'unknown'

    Args
    ----
    ret : float | None
        當期報酬（與 sigma 同單位，例如兩者都用「%」）。
    sigma : float | None
        當期波動尺度 σ（建議用 `ewma_vol()` 的最新值）。
    k : float
        死區寬度倍數，預設 0.5σ。k=0.5 對常態約 38% 的日子落在死區，
        是「不要為半根雜訊寫敘事」與「不要漏掉真訊號」的常用折衷。
        **必須是 >= 0 的有限數**，否則 raise ValueError。

    Returns
    -------
    str : 'bearish' | 'neutral' | 'bullish' | 'unknown'

    Raises
    ------
    ValueError
        `k` 非有限數或 < 0（§1 Fail Loud，不靜默修正）。
        v19.171：本檢查已移到函式**最前面** —— 原本排在 `ret is None` /
        `sigma <= 0` 的 early return 之後，導致 `signal_with_deadband(None, None,
        k=-1)` 悄悄回 'unknown' 而不 raise，呼叫端的參數 bug 會被資料缺漏掩蓋，
        等到資料齊全的那天才炸。參數合法性與資料可用性是兩件事，先驗參數。

    為何需要
    --------
    P1-4：實測台股 −0.06%（約 0.05σ）被判「股匯雙殺，外資無情提款撤出」。
    只看漲跌**符號**、不看**幅度是否超過雜訊**，必然把盤整日講成崩盤。
    σ 拿不到時回 'unknown' 而非猜一個方向 —— CLAUDE.md §1 Fail Loud。
    """
    # ── ① 參數合法性（與資料是否齊全無關，必須最先驗）────────────────
    try:
        _k = float(k)
    except (TypeError, ValueError):
        raise ValueError(
            f"signal_with_deadband: k 需為 >= 0 的有限數,收到 {k!r}") from None
    if not np.isfinite(_k) or _k < 0:
        raise ValueError(f"signal_with_deadband: k 需為 >= 0 的有限數,收到 {k}")

    # ── ② 資料可用性（缺就誠實回 'unknown'，不猜方向）───────────────
    if ret is None or sigma is None:
        return 'unknown'
    try:
        r = float(ret)
        sd = float(sigma)
    except (TypeError, ValueError):
        return 'unknown'
    if not np.isfinite(r) or not np.isfinite(sd) or sd <= 0:
        return 'unknown'
    band = _k * sd
    if abs(r) <= band:
        return 'neutral'
    return 'bullish' if r > 0 else 'bearish'


def winsorize(s: "pd.Series", lower: float = 0.01, upper: float = 0.99) -> "pd.Series":
    """分位數縮尾（winsorize，v19.170）。

    數學式
    ------
        q_lo = quantile(s, lower)、q_hi = quantile(s, upper)
        s'_i = min(max(s_i, q_lo), q_hi)

    與「hard clip on z」的差別
    --------------------------
    常見寫法是先算 z 再 `clip(-3, 3)` —— 那是**事後**截掉極端 z，
    但 mean / std 早已被離群值汙染（分母被撐大 → 所有 z 被壓小）。
    真正的 winsorize 是**先**把原始資料尾端壓回分位數，**再**算統計量，
    離群值就不會流進 mean / std。兩者可並存：winsorize 治因、clip 治果。

    Args
    ----
    s : pd.Series
        數值序列。
    lower / upper : float
        下 / 上分位（0~1），需滿足 0 <= lower < upper <= 1。

    Returns
    -------
    pd.Series
        縮尾後序列（同 index、同長度，NaN 保持 NaN）。
        空序列原樣返回；分位數算不出來（全 NaN）時原樣返回（不捏造邊界）。

    Raises
    ------
    ValueError : lower/upper 不合法（§1 Fail Loud，不靜默修正）。
    """
    if not (0.0 <= lower < upper <= 1.0):
        raise ValueError(
            f"winsorize: 需 0 <= lower < upper <= 1,收到 lower={lower}, upper={upper}")
    if s.empty:
        return s
    q_lo = s.quantile(lower)
    q_hi = s.quantile(upper)
    if not (np.isfinite(q_lo) and np.isfinite(q_hi)):
        # 全 NaN / 全 inf → 沒有可信的邊界，原樣返回而非填假值
        return s
    return s.clip(lower=q_lo, upper=q_hi)
