"""shared/relative_thresholds.py — 相對化門檻判定（L0 純函式，v19.170；v19.172 修正）

⚠️ v19.172 重要更正：`vol_normalized_bias()` 原本除以「年化波動」是**量綱錯誤**
（BIAS_N 的 σ 只有年化波動的 0.5617 倍，N=240/T=252），舊式**系統性低估
1.4~1.8 倍**。v19.170 據此導出的「實測 +29.6% 並不極端」結論**已撤回**——
正確值是 1.76σ~2.64σ，**確實極端**。完整推導、影響表與撤回聲明見該函式 docstring。


【解決什麼】P1-1：絕對值門檻沒有隨市值 / 指數水位縮放，久了必然失效。
稽核實測：
    融資餘額門檻 2,500 / 3,400 億  vs  現值 5,148 億   → 永遠 🔴，資訊量 = 0
    外資期貨淨口 −10,000 / −20,000 口 vs 現值 −87,626 口 → 同上
    年線乖離 BIAS240 固定 ±20%      vs  現值 +29.6%     → 結構多頭下必然誤判

絕對門檻的隱含假設是「市值 / 未平倉 / 指數水位不變」。台股總市值十年成長數倍，
分子（融資、口數、乖離）跟著長大，分母卻寫死在常數裡 → 門檻被通膨式地淹沒。
本模組提供兩類修法：
    (A) 分位數化：拿「現值在自身滾動歷史的位置」判級（`classify_by_pct_rank`）
    (B) 比率化  ：把絕對量除以同步成長的分母（`margin_leverage_ratio` 等）

【重要 — 本模組不改動既有判級行為】
本模組**只提供計算**，不 patch、不 monkey-patch、不改寫
`shared/macro_buckets.BUCKET_DANGER_SPECS` 的任何門檻數值或 `classify_danger()`
的判級結果。門檻數值變更屬行為變更，需獨立回測後才可上線；
是否採用相對化結論，完全由呼叫端（UI / 決策層）自行決定。
本版只在 macro_buckets 相關 spec 的 note 補一行指路註解，不動數值。

【架構】L0：不得 import streamlit、不得 import requests、不得 import L1+ 模組。
只依賴 numpy / pandas（皆已在 requirements.txt，未新增依賴）。

【Fail Loud（CLAUDE.md §1）】資料長度不足時回 `level='unknown'` +
`basis='insufficient_data'`，**不會**偷偷退回絕對門檻假裝有結論。
"""
from __future__ import annotations

import math  # v19.172：BIAS 的 σ 換算係數由 (N, T) 推導，需 sqrt
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from shared.signal_thresholds import TRADING_DAYS_PER_YEAR  # v19.172 SSOT，禁 inline 252
from shared.stats_helpers import robust_z, rolling_pct_rank

# 分位數判級的預設視窗：756 ≈ 3 年交易日（252 × 3），涵蓋一輪中期景氣循環。
DEFAULT_PCT_RANK_WINDOW: int = 756
# 穩健 z 的視窗：252 ≈ 1 年，回報「現值偏離近一年中位數幾個 σ」。
DEFAULT_ROBUST_Z_WINDOW: int = 252

# v19.172：BIAS 均線長度預設 240（年線）。
# 與 `src/config/config.py:14 MA_ANNUAL = 240` 同值，但**刻意不 import src.config** ——
# 該檔為讀 `st.secrets` 而條件 import streamlit（CLAUDE.md §8.2.A EX-L0-1），
# shared/ 這層純函式不該把 UI 框架拖進 import chain。
# 接線時建議由呼叫端顯式傳 `ma_len=config.MA_ANNUAL`，讓 SSOT 留在 config。
DEFAULT_BIAS_MA_LEN: int = 240


@dataclass(frozen=True)
class RelativeVerdict:
    """相對化判級結果（frozen：判級結果不可就地竄改，避免下游偷改燈號）。

    Attributes
    ----------
    level : str
        'green' / 'yellow' / 'red' / 'unknown'。'unknown' = 資料不足，**不是**綠燈。
    pct_rank : float | None
        最新值在滾動視窗內的分位（0~1，1 = 視窗內歷史新高）。算不出 → None。
    z : float | None
        最新值的穩健 z-score（中位數 / MAD，見 stats_helpers.robust_z）。算不出 → None。
    basis : str
        判級依據：
          'pct_rank'           → 用滾動分位判的（本模組唯一會產出的成功路徑）
          'absolute_fallback'  → 保留給呼叫端：呼叫端自行決定退回絕對門檻時標這個
          'insufficient_data'  → 樣本不足，未給結論
    note : str
        中文說明，可直接顯示給使用者（含實際樣本數 / 分位數等佐證）。
    """
    level: str
    pct_rank: Optional[float]
    z: Optional[float]
    basis: str
    note: str


def classify_by_pct_rank(series, *, window: int = DEFAULT_PCT_RANK_WINDOW,
                         yellow: float = 0.75, red: float = 0.90,
                         high_bad: bool = True,
                         min_periods: Optional[int] = None) -> RelativeVerdict:
    """用「最新值在滾動視窗內的分位數」判燈號（v19.170）。

    判定式
    ------
        p    = rolling_pct_rank(series, window).iloc[-1]        # 0~1
        p_bad = p            (high_bad=True，值越高越危險)
              = 1 − p        (high_bad=False，值越低越危險)

        p_bad >= red     → 'red'
        p_bad >= yellow  → 'yellow'
        否則              → 'green'

    預設 yellow=0.75 / red=0.90 的意思是：「贏過自己過去 3 年 75% / 90% 的日子」。
    這條線**自動**跟著市值、指數水位一起長大，不會像絕對門檻那樣被淹沒。

    Args
    ----
    series : pd.Series | Sequence[float]
        時間遞增的數值序列（最後一筆 = 最新值）。可傳 list / np.ndarray，內部轉 Series。
    window : int
        滾動視窗（交易日），預設 756 ≈ 3 年。
    yellow / red : float
        黃 / 紅分位門檻，需滿足 0 < yellow < red < 1。
    high_bad : bool
        True = 值越高越危險（融資餘額、BIAS 正乖離、VIX）；
        False = 值越低越危險（ADL 廣度、PMI）。
    min_periods : int | None
        最少有效樣本數；None → `max(20, window // 4)`。
        注意實際生效的下限是 `max(min_periods, max(20, window // 4))`
        （後者由 stats_helpers.rolling_pct_rank 內部設定，此處不重複實作以免 SSOT 漂移）。

    Returns
    -------
    RelativeVerdict
        樣本不足 → `level='unknown'`, `basis='insufficient_data'`，
        **不會**退回絕對門檻假裝有結論（CLAUDE.md §1 Fail Loud）。

    效能
    ----
    全向量化：rolling().rank(pct=True) + rolling median/MAD，O(n·log(window))。
    """
    if not (0.0 < yellow < red < 1.0):
        raise ValueError(
            f"classify_by_pct_rank: 需 0 < yellow < red < 1,收到 yellow={yellow}, red={red}")
    if window < 2:
        raise ValueError(f"classify_by_pct_rank: window 需 >= 2,收到 {window}")

    s = series if isinstance(series, pd.Series) else pd.Series(series, dtype='float64')
    s = pd.to_numeric(s, errors='coerce')

    floor = max(20, window // 4)
    need = floor if min_periods is None else max(int(min_periods), floor)
    n_valid = int(s.notna().sum())
    if n_valid < need:
        return RelativeVerdict(
            level='unknown', pct_rank=None, z=None, basis='insufficient_data',
            note=(f'樣本不足:有效點數 {n_valid} < 需求 {need}'
                  f'(視窗 {window} 日)→ 不給結論,不退回絕對門檻(§1 Fail Loud)'))

    pr_series = rolling_pct_rank(s, window=window)
    pr_last = pr_series.iloc[-1] if len(pr_series) else np.nan
    if pr_last is None or not np.isfinite(pr_last):
        return RelativeVerdict(
            level='unknown', pct_rank=None, z=None, basis='insufficient_data',
            note=(f'最新值分位算不出(視窗尾端有效點數不足或最新值為 NaN),'
                  f'有效點數 {n_valid}'))

    z_series = robust_z(s, window=min(window, DEFAULT_ROBUST_Z_WINDOW))
    z_last = z_series.iloc[-1] if len(z_series) else np.nan
    z_out = float(round(float(z_last), 2)) if np.isfinite(z_last) else None

    p = float(pr_last)
    p_bad = p if high_bad else (1.0 - p)
    if p_bad >= red:
        level = 'red'
    elif p_bad >= yellow:
        level = 'yellow'
    else:
        level = 'green'

    side = '高位' if high_bad else '低位'
    note = (f'滾動 {window} 日分位 {p * 100:.1f}%(危險側={side},'
            f'危險側分位 {p_bad * 100:.1f}%;黃 {yellow * 100:.0f}% / 紅 {red * 100:.0f}%)'
            f',有效樣本 {n_valid}')
    if z_out is None:
        note += ';穩健 z 不可得(MAD=0 或樣本不足)'
    return RelativeVerdict(level=level, pct_rank=round(p, 4), z=z_out,
                           basis='pct_rank', note=note)


def margin_leverage_ratio(margin_yi: Optional[float],
                          market_cap_yi: Optional[float]) -> Optional[float]:
    """融資槓桿比＝融資餘額 / 上市總市值（%），v19.170。

    公式
    ----
        ratio(%) = margin_yi / market_cap_yi × 100

    為何比絕對金額有意義
    --------------------
    絕對門檻（2,500 / 3,400 億）的隱含假設是「總市值不變」。台股總市值長期成長，
    融資餘額的名目值跟著抬升 —— 實測 5,148 億早已把兩條線都踩穿，於是燈號永遠 🔴，
    **鑑別力歸零**。改看「融資佔總市值幾 %」，分子分母同步成長，
    才真的在衡量「散戶槓桿相對市場規模是高是低」。
    此比率通常落在 1%~2% 量級，可再丟進 `classify_by_pct_rank` 做歷史分位判級。

    Args
    ----
    margin_yi : float | None      融資餘額（億 TWD）
    market_cap_yi : float | None  上市總市值（億 TWD，需與分子同單位）

    Returns
    -------
    float | None
        比率（%，四捨五入到小數 3 位）。
        任一為 None / 非數值 / 非有限，或 `market_cap_yi <= 0` → **回 None**
        （§1：算不出就說算不出，不回 0，0 會被下游誤讀成「槓桿極低」）。
    """
    m = _to_finite_float(margin_yi)
    cap = _to_finite_float(market_cap_yi)
    if m is None or cap is None or cap <= 0:
        return None
    return round(m / cap * 100.0, 3)


def foreign_futures_share(net_lots: Optional[float],
                          total_oi_lots: Optional[float]) -> Optional[float]:
    """外資期貨淨口佔比＝外資淨口數 / 全市場未平倉口數（%），v19.170。

    公式
    ----
        share(%) = net_lots / total_oi_lots × 100     （net_lots 可為負 = 淨空）

    為何比絕對口數有意義
    --------------------
    絕對門檻 −10,000 / −20,000 口在契約規模、市場參與度變動後同樣被淹沒
    （實測 −87,626 口，兩條線早就穿透）。改看「佔全市場未平倉的百分比」，
    才是「外資相對整個期貨市場壓了多重的空單」。

    資料一致性防禦
    --------------
    稽核實測出現 |net_lots| = 87,626 > total_oi_lots = 39,503 —— 部位絕對值
    大於全市場未平倉，**物理上不可能**，代表兩欄位不同源
    （例如一邊是「口數（含各契約加總 / 大小台未換算）」、另一邊是「特定契約未平倉」，
    或一邊是交易口數、另一邊是未平倉口數）。此時仍回傳比值，但 print 一行警告留跡，
    不靜默吞掉（§1 禁止 `except: pass` 式的沉默）。

    Args
    ----
    net_lots : float | None       外資期貨淨口數（正=淨多、負=淨空）
    total_oi_lots : float | None  全市場未平倉口數（應為正值）

    Returns
    -------
    float | None
        佔比（%，小數 2 位）。`total_oi_lots` 為 None / 0 / 負 / 非有限 → 回 None。
    """
    net = _to_finite_float(net_lots)
    oi = _to_finite_float(total_oi_lots)
    if net is None or oi is None or oi <= 0:
        return None
    if abs(net) > oi:
        print(f'[relative_thresholds] ⚠️ 資料一致性警告:|外資淨口|={abs(net):,.0f} '
              f'> 全市場未平倉={oi:,.0f} —— 物理上不可能,兩欄位極可能不同源'
              f'(契約別 / 口數定義 / 大小台未換算)。佔比 {net / oi * 100:.2f}% 僅供參考,'
              f'請先修資料源。')
    return round(net / oi * 100.0, 2)


def _bias_sd_factor(ma_len: int, trading_days: int) -> float:
    """BIAS_N 的標準差 ÷ 年化波動＝ sqrt((N−1)(2N−1) / (6·N·T))，v19.172。

    由 `vol_normalized_bias` docstring 的隨機漫步推導而來，**不硬寫常數**：
    只要換 N（BIAS20 / BIAS60 / BIAS240）或換 T，係數自動跟著變。

    N=240, T=252 → sqrt(239×479 / (6×240×252)) = sqrt(114481/362880)
                 = sqrt(0.315479) = **0.56168**（稽核報告寫 0.5616 是截斷，同一個數）
    N=60,  T=252 → sqrt(59×119 / (6×60×252)) = sqrt(7021/90720) = 0.27819
    N=20,  T=252 → sqrt(19×39 / (6×20×252))  = sqrt(741/30240)  = 0.15654

    大 N 近似式 sqrt(N/(3T))：N=240 → sqrt(240/756) = 0.56344，
    與精確值差 +0.31%。此處**採精確式**（成本一樣是一次 sqrt，沒有理由用近似）。
    """
    return math.sqrt((ma_len - 1) * (2 * ma_len - 1) / (6.0 * ma_len * trading_days))


def _bias_drift_factor(ma_len: int, trading_days: int) -> float:
    """BIAS_N 的期望值 ÷ 年化漂移＝(N−1) / (2T)，v19.172。

    N=240, T=252 → 239/504 = **0.474206**。
    即：年漂移 10%/年 的多頭，BIAS240 的**期望值**本來就有 +4.74%，
    那 4.74% 不是「過熱」，是趨勢本身，扣掉才是真正的超漲。
    """
    return (ma_len - 1) / (2.0 * trading_days)


def vol_normalized_bias(bias_pct: Optional[float],
                        ann_vol_pct: Optional[float],
                        *,
                        ma_len: int = DEFAULT_BIAS_MA_LEN,
                        trading_days: int = TRADING_DAYS_PER_YEAR,
                        drift_ann_pct: Optional[float] = None) -> Optional[float]:
    """波動度標準化乖離＝BIAS 對「BIAS 自己的 σ」的倍數（v19.172 修 🔴 量綱錯誤）。

    ⚠️ v19.170 舊版是**錯的**（本版撤回）
    ------------------------------------
    舊式 `bias_sigma = bias_pct / ann_vol_pct` 把「價格對 240 日均線的偏離」
    直接除以「**年化**波動」。兩者不是同一個尺度：年化波動描述的是「一整年
    (T=252 個交易日) 累積報酬的 σ」，而 BIAS240 是「當前價 vs 過去 240 日均價」，
    後者是一組**加權報酬和**，其 σ 只有年化波動的 0.56 倍。除錯分母 = 量綱錯誤。

    正確推導（log 價格帶漂移隨機漫步；N = 均線長度、T = 年交易日）
    ------------------------------------------------------------
    設 L_t = log P_t、日報酬 r_t = L_t − L_{t−1}，r 為 i.i.d.（μ_d, σ_d²）。

        X_t = L_t − (1/N)·Σ_{k=0}^{N−1} L_{t−k}
            = (1/N)·Σ_{k=0}^{N−1} (L_t − L_{t−k})
            = (1/N)·Σ_{j=0}^{N−2} (N−1−j)·r_{t−j}          ← r_{t−j} 出現 (N−1−j) 次

        Var(X) = (σ_d²/N²)·Σ_{m=1}^{N−1} m²                 ← m = N−1−j
               = (σ_d²/N²)·(N−1)N(2N−1)/6
               = σ_d²·(N−1)(2N−1)/(6N)                      [N=240 → 79.5007·σ_d²]
               ≈ σ_d²·N/3                                   [大 N 近似，N=240 → 80]

        SD(X) = σ_d·sqrt((N−1)(2N−1)/(6N))
              = σ_a·sqrt((N−1)(2N−1)/(6·N·T))               [σ_a = σ_d·√T]
              = σ_a·**0.56168**                             [N=240, T=252]

        E[X]  = (μ_d/N)·Σ_{m=1}^{N−1} m = μ_d·(N−1)/2
              = μ_a·(N−1)/(2T) = μ_a·**0.474206**           [N=240, T=252]

    ⇒ **BIAS240 的標準差約為年化波動的 0.5617 倍，不是 1 倍。**

    本版判定式
    ----------
        sd_bias   = ann_vol_pct   · sqrt((N−1)(2N−1) / (6·N·T))
        mu_bias   = drift_ann_pct · (N−1) / (2T)            （未給 drift → 0）
        bias_sigma = (bias_pct − mu_bias) / sd_bias

    實際影響（以線上實測 BIAS240 = +32.7%、μ=0 為例）
    -------------------------------------------------
    ==========  ===============  ==============  ==============
    年化波動 σ_a  SD = 0.5617·σ_a   正確 σ 數        舊式（錯）給的
    ==========  ===============  ==============  ==============
    20%          11.23%           **+2.91σ**      +1.64σ
    25%          14.04%           **+2.33σ**      +1.31σ
    30%          16.85%           **+1.94σ**      +1.09σ
    ==========  ===============  ==============  ==============

    舊式在 μ=0 時**恆定低估 1/0.5617 = 1.780 倍**（不是「有時候」）；
    若再加上漂移修正（年漂移 10%~15% 的結構多頭），低估倍率落在 1.4~1.5 倍。
    綜合區間 **1.4~1.8 倍**。
    若照舊式接線，+32.7%（實際 1.9~2.9σ，**是真的極端**）會被算成 1.1~1.6σ →
    落在黃甚至綠 → 相對化不但沒解決 P1-2，**反而製造新的誤判**。

    🔴 v19.172 撤回 v19.170 的錯誤結論
    ---------------------------------
    v19.170 原文寫：「實測 +29.6% 在高波動的結構多頭裡**並不極端**」——
    那句話是由上面那條錯誤公式導出的（29.6 / 30 = 0.99σ），**現正式撤回**。
    用正確係數重算 +29.6%（μ=0）：

        σ_a = 20% → 29.6 / 11.23 = **2.64σ**
        σ_a = 25% → 29.6 / 14.04 = **2.11σ**
        σ_a = 30% → 29.6 / 16.85 = **1.76σ**

    即使假設台股年化波動高達 30%，+29.6% 仍是 **1.76σ**（常態雙尾約 8%）；
    在 20% 波動下更是 2.63σ（雙尾約 0.8%）。**它確實極端**。
    （尾端機率僅供量級參考 —— 真實報酬厚尾，實際尾端機率會更高。）
    同理原文「18% 波動下 +20% 乖離 ≈ 1.11σ、30% 下 ≈ 0.67σ」兩個數字亦錯，
    正確為 **1.98σ** 與 **1.19σ**。

    已知二階近似（誠實揭露，不宣稱本式精確）
    --------------------------------------
    1. 推導在 **log 空間**，但 `bias_pct` 慣例是算術乖離 (P/MA − 1)×100。
       log(1+0.327) = 0.2830 → 若改用 log 乖離，+32.7% 的 σ 數會是 2.91 × 0.865
       = **2.52σ**（本式偏高 ~15%，方向偏保守/偏「更極端」）。
       |bias| ≤ 10% 時兩者差 < 5%，可忽略；尾端才明顯。
    2. 分母的均線是**價格算術平均**，推導用的是 **log 價格平均**。
       由 Jensen，mean(log P) ≤ log(mean P)，故 X 略大於 log(P/MA)，同樣偏保守。
    3. r_t 假設 i.i.d.：真實報酬有波動叢聚與弱負自相關，Var(X) 會偏離；
       故本函式輸出**建議再丟進 `classify_by_pct_rank` 取歷史分位**做雙保險，
       不要單獨拿 ±2σ 當硬門檻。

    Args
    ----
    bias_pct : float | None
        乖離率（%，正=正乖離）。定義須為 (P / MA_N − 1) × 100。
    ann_vol_pct : float | None
        **年化**波動度（%，需與 bias 同為「%」單位，例如 25.0 代表 25%）。
    ma_len : int
        均線長度 N（交易日）。預設 240（年線）；BIAS20 傳 20、BIAS60 傳 60。
    trading_days : int
        年交易日 T，預設 `TRADING_DAYS_PER_YEAR`（252）。
        **必須與 `ann_vol_pct` 年化時所用的 T 一致**，否則又是一個量綱錯誤。
    drift_ann_pct : float | None
        年化漂移 μ_a（%/年）。**可選**：
          - 給定 → 扣掉 `μ_a·(N−1)/(2T)`（N=240,T=252 時 = 0.4742·μ_a）。
          - **不給（預設 None）→ 視為 0**，即假設無漂移。這在多頭期會讓
            σ 數**略偏高**（趨勢本身帶來的正乖離被算進「超漲」）。
            方向是**保守**的（傾向多喊過熱、少漏警訊），但呼叫端要知道：
            年漂移 12% 時 BIAS240 的期望值就有 +5.7%，在 σ_a=25%
            （SD=14.04%）下相當於白送 0.41σ。
          - 給了但不是有限數（NaN / inf）→ **回 None**，不當作 0
            （§1：資料壞掉 ≠ 沒有資料，不可靜默降級）。

    Returns
    -------
    float | None
        σ 倍數（小數 3 位）。下列情形一律 **回 None**，不除零、不填 0
        （§1：算不出就說算不出；填 0 會被下游誤讀成「完全沒有乖離」）：
          - `bias_pct` 為 None / 非數值 / NaN / inf
          - `ann_vol_pct` 為 None / 非數值 / NaN / inf / **<= 0**
          - `drift_ann_pct` 有給但為 NaN / inf

    Raises
    ------
    ValueError
        `ma_len < 2` 或 `trading_days < 1`（這是**參數**錯誤而非資料缺漏，
        §1 Fail Loud，與 `classify_by_pct_rank` 對 window 的處理一致）。

    效能
    ----
    O(1)，兩次乘除 + 一次 sqrt，無迴圈、無配置。
    """
    if ma_len < 2:
        raise ValueError(f"vol_normalized_bias: ma_len 需 >= 2,收到 {ma_len}")
    if trading_days < 1:
        raise ValueError(
            f"vol_normalized_bias: trading_days 需 >= 1,收到 {trading_days}")

    b = _to_finite_float(bias_pct)
    v = _to_finite_float(ann_vol_pct)
    if b is None or v is None or v <= 0:
        return None

    # 漂移修正：None = 呼叫端明說「不修正」→ 0；有給但壞掉 → 不猜，回 None。
    if drift_ann_pct is None:
        mu_bias = 0.0
    else:
        mu_a = _to_finite_float(drift_ann_pct)
        if mu_a is None:
            return None
        mu_bias = mu_a * _bias_drift_factor(ma_len, trading_days)

    sd_bias = v * _bias_sd_factor(ma_len, trading_days)
    if not np.isfinite(sd_bias) or sd_bias <= 0:
        return None
    return round((b - mu_bias) / sd_bias, 3)


def _to_finite_float(x) -> Optional[float]:
    """把任意輸入轉成有限 float；None / 非數值 / NaN / inf 一律回 None（不代入預設值）。"""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None
