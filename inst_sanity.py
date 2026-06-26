"""inst_sanity.py — 三大法人單日買賣超 sanity 檢查(L2 純函式)

CLAUDE.md §3.2 / §4.6 — |inst_net_shares| > 30D 均量 × 5 → 異常旗標。
v18.299 audit 落地:從 §3.2 「待 audit 落地」改為產線可用 helper。

L2 Compute 純函式,無 I/O。caller(L1 fetcher / L2 strategy)可:
- 拿 fetcher 回的 inst_net + 該股 30D 均量 → 呼叫 `is_inst_net_outlier`
- 拿 batch 處理 → 呼叫 `flag_inst_net_outliers_batch`
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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
