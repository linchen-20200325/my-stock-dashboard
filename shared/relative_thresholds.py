"""shared/relative_thresholds.py — 相對化門檻判定（L0 純函式，v19.170）

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

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from shared.stats_helpers import robust_z, rolling_pct_rank

# 分位數判級的預設視窗：756 ≈ 3 年交易日（252 × 3），涵蓋一輪中期景氣循環。
DEFAULT_PCT_RANK_WINDOW: int = 756
# 穩健 z 的視窗：252 ≈ 1 年，回報「現值偏離近一年中位數幾個 σ」。
DEFAULT_ROBUST_Z_WINDOW: int = 252


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


def vol_normalized_bias(bias_pct: Optional[float],
                        ann_vol_pct: Optional[float]) -> Optional[float]:
    """波動度標準化乖離＝BIAS / 年化波動度（無單位「σ 數」），v19.170。

    公式
    ----
        bias_sigma = bias_pct / ann_vol_pct

    為何需要（解 P1-2）
    -------------------
    BIAS240 固定 ±20% 沒有考慮「這 20% 相對市場自身波動算大還算小」。
    台股年化波動約 18%~25%：
        年化波動 18% → +20% 乖離 ≈ 1.11σ（確實偏高）
        年化波動 30% → +20% 乖離 ≈ 0.67σ（其實還在常態範圍）
    實測 +29.6% 在高波動的結構多頭裡並不極端，固定門檻卻直接判「過熱」→ 誤判。
    改用「幾個 σ」後門檻自動隨波動 regime 伸縮。
    建議再把本函式輸出丟進 `classify_by_pct_rank` 取歷史分位，雙保險。

    Args
    ----
    bias_pct : float | None      年線乖離率（%，正=正乖離）
    ann_vol_pct : float | None   年化波動度（%，需與 bias 同為「%」單位）

    Returns
    -------
    float | None
        σ 倍數（小數 3 位）。任一不可用或 `ann_vol_pct <= 0` → 回 None
        （§1：不捏造 σ=20% 這類預設值）。
    """
    b = _to_finite_float(bias_pct)
    v = _to_finite_float(ann_vol_pct)
    if b is None or v is None or v <= 0:
        return None
    return round(b / v, 3)


def _to_finite_float(x) -> Optional[float]:
    """把任意輸入轉成有限 float；None / 非數值 / NaN / inf 一律回 None（不代入預設值）。"""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None
