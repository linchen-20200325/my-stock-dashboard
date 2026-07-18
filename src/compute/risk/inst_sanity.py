"""src/compute/risk/inst_sanity.py — 三大法人單日買賣超 sanity 檢查(L2 純函式)

CLAUDE.md §3.2 / §4.6 — |inst_net_shares| > 30D 均量 × 5 → 異常旗標。
v18.299 audit 落地:從 §3.2 「待 audit 落地」改為產線可用 helper。
v19.135 wiring:新增 `flag_latest_inst_outlier_from_df` adapter,讓已握有個股
K 線 df(含 主力合計 + volume,單位皆張)的 consumer(section_chips_20d)一行取用。

L2 Compute 純函式,無 I/O。caller(L1 fetcher / L2 strategy / L5 UI)可:
- 拿 fetcher 回的 inst_net + 該股 30D 均量 → 呼叫 `is_inst_net_outlier`
- 拿 batch 處理 → 呼叫 `flag_inst_net_outliers_batch`
- 拿個股 K 線 df(已載入)→ 呼叫 `flag_latest_inst_outlier_from_df`(最新一日)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from shared.signal_thresholds import INST_NET_OUTLIER_VOLUME_RATIO


@dataclass(frozen=True)
class InstNetSanityResult:
    """三大法人 sanity 檢查結果。"""
    is_outlier: bool
    ratio: Optional[float]  # |inst_net| / vol_30d_avg(均量為 0 / None 時為 None)
    reason: str             # 'ok' / 'outlier' / 'vol_unavailable' / 'inst_net_zero'


def is_inst_net_outlier(
    inst_net_shares: Optional[float],
    vol_30d_avg_shares: Optional[float],
    *,
    threshold_ratio: float = INST_NET_OUTLIER_VOLUME_RATIO,
) -> InstNetSanityResult:
    """判定三大法人單日買賣超是否超過 30D 均量 × threshold(預設 5×)。

    §1 Fail Loud:vol_30d_avg <= 0 或 None → reason='vol_unavailable',
    is_outlier=False(無法判定 ≠ 確認異常,caller 應另外處理 missing volume)。

    Parameters
    ----------
    inst_net_shares : float | None
        三大法人單日淨買賣超(股數,可為負,代表賣超)。None / 0 → skip。
    vol_30d_avg_shares : float | None
        該股 30 個交易日成交均量(股)。None / <=0 → 無法判定。
    threshold_ratio : float
        outlier 倍數,預設讀 SSOT `INST_NET_OUTLIER_VOLUME_RATIO`(= 5.0)。

    Returns
    -------
    InstNetSanityResult

    Examples
    --------
    >>> is_inst_net_outlier(1_000_000, 100_000)  # 10x 均量 → outlier
    InstNetSanityResult(is_outlier=True, ratio=10.0, reason='outlier')
    >>> is_inst_net_outlier(50_000, 100_000)     # 0.5x 均量 → ok
    InstNetSanityResult(is_outlier=False, ratio=0.5, reason='ok')
    >>> is_inst_net_outlier(1_000_000, 0)        # 均量 0 → 無法判定
    InstNetSanityResult(is_outlier=False, ratio=None, reason='vol_unavailable')
    """
    if inst_net_shares is None:
        return InstNetSanityResult(is_outlier=False, ratio=None, reason='inst_net_zero')
    if inst_net_shares == 0:
        return InstNetSanityResult(is_outlier=False, ratio=0.0, reason='inst_net_zero')
    if vol_30d_avg_shares is None or vol_30d_avg_shares <= 0:
        # 均量缺值或非正 → 無法計算 ratio,**不**標 outlier(避免偽陽)
        return InstNetSanityResult(is_outlier=False, ratio=None, reason='vol_unavailable')

    ratio = abs(inst_net_shares) / vol_30d_avg_shares
    if ratio > threshold_ratio:
        return InstNetSanityResult(is_outlier=True, ratio=ratio, reason='outlier')
    return InstNetSanityResult(is_outlier=False, ratio=ratio, reason='ok')


def flag_inst_net_outliers_batch(
    inst_net_series: list[Optional[float]],
    vol_30d_avg_shares: Optional[float],
    *,
    threshold_ratio: float = INST_NET_OUTLIER_VOLUME_RATIO,
) -> list[InstNetSanityResult]:
    """批次判定一連串 inst_net 樣本(共用同一個 vol_30d_avg)。

    Parameters
    ----------
    inst_net_series : list[float | None]
        每筆對應一個交易日的法人淨買賣超(股)。
    vol_30d_avg_shares : float | None
        該股當前 30D 均量(股)— 假設批次內 vol 變化不大。
    threshold_ratio : float
        outlier 倍數,預設 SSOT。

    Returns
    -------
    list[InstNetSanityResult] 對應每筆 inst_net 的判定。
    """
    return [
        is_inst_net_outlier(net, vol_30d_avg_shares, threshold_ratio=threshold_ratio)
        for net in inst_net_series
    ]


def flag_latest_inst_outlier_from_df(
    df: Optional[pd.DataFrame],
    *,
    inst_col: str = '主力合計',
    vol_col: str = 'volume',
    window: int = 30,
    threshold_ratio: float = INST_NET_OUTLIER_VOLUME_RATIO,
) -> InstNetSanityResult:
    """從個股 K 線 df(data_loader 已載入)判定**最新一日**三大法人淨買賣超
    是否 > 該股 `window` 日均量 × `threshold_ratio`。

    薄 adapter:把「取最新一日 inst_net + 算 window 日均量」封裝於 L2,
    consumer(L5 UI section_chips_20d)一行取用 + 只負責顯示徽章(不寫計算)。

    **單位(§4.1)**:`主力合計` 與 `volume` 皆為「張」(data_loader 已 股→張 /1000,
    見 data_loader.py:385/742/914)。`ratio = |inst_net| / vol_avg` 無量綱 →
    張/張 與 股/股 同值,**無需換價**。

    **嚴格 window(§4.6 新上市/停牌)**:要求最近 `window` 列皆有有效量,
    不足 → `reason='vol_unavailable'`,**不誤報**(短史資料 outlier 意義弱)。

    **Fail-soft(UI 情境)**:df 為 None / 空 / 缺欄 / 最新日 inst_net 為 NaN →
    回 `vol_unavailable` 或 `inst_net_zero`,**不拋例外**(不炸 UI);caller 依
    `is_outlier` / `reason` 決定是否顯示徽章。§1 精神:寧可不報,不假報。

    Parameters
    ----------
    df : pd.DataFrame | None
        個股 K 線,須含 `inst_col`(單日三大法人淨買賣超,張)+ `vol_col`(成交量,張),
        date 軸升冪(與 tab_stock 其餘用法一致)。
    inst_col : str
        法人淨買賣超欄名,預設 `主力合計`(外資+投信+自營商)。
    vol_col : str
        成交量欄名,預設 `volume`。
    window : int
        均量窗口(交易日),預設 30。
    threshold_ratio : float
        outlier 倍數,預設 SSOT `INST_NET_OUTLIER_VOLUME_RATIO`(= 5.0)。

    Returns
    -------
    InstNetSanityResult
    """
    if df is None or len(df) == 0:
        return InstNetSanityResult(is_outlier=False, ratio=None, reason='vol_unavailable')
    if inst_col not in df.columns or vol_col not in df.columns:
        # 缺欄 → 無法判定(fail-soft,不炸 UI)
        return InstNetSanityResult(is_outlier=False, ratio=None, reason='vol_unavailable')

    # 最新一日 inst_net(只判當日;當日缺值 → 不用舊值冒充)
    _net_latest = pd.to_numeric(df[inst_col], errors='coerce').iloc[-1]
    if pd.isna(_net_latest):
        return InstNetSanityResult(is_outlier=False, ratio=None, reason='inst_net_zero')

    # 嚴格 window 日均量:最近 window 列須皆有有效量,否則不判定
    _vol_win = pd.to_numeric(df[vol_col], errors='coerce').tail(window)
    if int(_vol_win.notna().sum()) < window:
        return InstNetSanityResult(is_outlier=False, ratio=None, reason='vol_unavailable')
    _vol_avg = float(_vol_win.mean())

    return is_inst_net_outlier(
        float(_net_latest), _vol_avg, threshold_ratio=threshold_ratio
    )
