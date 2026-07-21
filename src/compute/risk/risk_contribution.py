"""src/compute/risk/risk_contribution.py — 投組風險貢獻分解(Risk Contribution, L2 純函式).

給投組各資產「日報酬 + 權重」,依 Euler 分解把組合波動 σ_p 拆到每一檔,揭露
「市值佔比 vs 風險佔比」的落差(某檔市值只佔 40%,卻可能扛了 60% 的組合波動 =
分散效果被高估,風險其實壓在一檔)。概念取自 PyPortfolioOpt 的 risk contribution,
但**不做**均值-變異數最佳化(那有「假精準」不穩問題,牴觸 §1)。

數學(§7 已與 user 對齊):
    σ_p   = sqrt(wᵀ Σ w)            組合日波動(w=權重向量, Σ=日報酬共變異數)
    RC_i  = w_i · (Σw)_i / σ_p       第 i 檔風險貢獻   → Σ RC_i = σ_p (Euler 定理)
    PRC_i = RC_i / σ_p               第 i 檔風險佔比   → Σ PRC_i = 1 (100%)

只用 Σw(**不需反矩陣**)→ 數值穩定;不受共變異數奇異/病態影響。

§1 fail-loud / §3.3 反捏造:
  - 缺日報酬(無價格歷史)的資產 → 剔除並記 excluded(不灌 0 假裝),回報被剔除市值%。
  - 重疊觀測 < RC_MIN_OVERLAP_DAYS → low_confidence 旗標(仍算但誠實標低可信度)。
  - 組合零波動(全常數/停牌) → PRC 無意義,回 note 不硬除(不回 inf/NaN 假數)。
  - 權重未正規化(給 % 或未加總=1)→ 內部正規化(scale-free),不報錯。
§4.3 對帳:Σ RC_i 必 = σ_p,不符 → raise(算錯自曝,非 assert 以免 -O 被剝除)。
§8.2:L2 純函式,零 I/O、零 streamlit;年化交易日走 signal_thresholds SSOT。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from shared.risk_contribution_thresholds import (
    RC_CONCENTRATION_GAP_PCT,
    RC_MIN_OVERLAP_DAYS,
)
from shared.signal_thresholds import TRADING_DAYS_PER_YEAR

_TABLE_COLS = ("ticker", "weight_pct", "risk_pct", "gap_pct", "concentrated")


@dataclass(frozen=True)
class RiskContributionResult:
    """風險貢獻分解結果。

    table               每檔一列:ticker / weight_pct(納入後正規化市值%) /
                        risk_pct(風險佔比%) / gap_pct(風險−市值,正=風險放大) /
                        concentrated(bool,gap ≥ 門檻),依 risk_pct 由大到小排。
    portfolio_vol_annual_pct  組合年化波動 σ_p × sqrt(252)(%);零波動時為 nan。
    n_obs               實際採用的重疊交易日數。
    excluded            無日報酬被剔除的 ticker。
    excluded_weight_pct 被剔除資產佔原始市值的 %。
    low_confidence      重疊觀測 < RC_MIN_OVERLAP_DAYS。
    note                白話診斷(空字串=正常)。
    """

    table: pd.DataFrame
    portfolio_vol_annual_pct: float
    n_obs: int
    excluded: tuple[str, ...]
    excluded_weight_pct: float
    low_confidence: bool
    note: str

    @property
    def ok(self) -> bool:
        """有可顯示的分解結果(table 非空)。"""
        return self.table is not None and not self.table.empty


def _empty(note: str) -> RiskContributionResult:
    return RiskContributionResult(
        table=pd.DataFrame(columns=list(_TABLE_COLS)),
        portfolio_vol_annual_pct=float("nan"),
        n_obs=0, excluded=(), excluded_weight_pct=0.0,
        low_confidence=True, note=note,
    )


def compute_risk_contribution(
    returns: pd.DataFrame,
    weights,
    *,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    min_overlap: int = RC_MIN_OVERLAP_DAYS,
    concentration_gap_pct: float = RC_CONCENTRATION_GAP_PCT,
) -> RiskContributionResult:
    """把組合波動 σ_p 依 Euler 分解到每檔,回 RiskContributionResult。

    Args:
        returns: 日報酬 DataFrame,index=date,columns=ticker,values=pct_change。
                 未對齊 / 含 NaN 皆可(內部取交集日 dropna)。
        weights: ticker -> 權重(市值佔比;可為 % 或未加總=1,內部正規化)。
                 dict / pd.Series 皆可。
        periods_per_year: 年化倍數(σ_daily × sqrt(此值));預設 252 交易日 SSOT。
        min_overlap: 重疊觀測低於此 → low_confidence 旗標。
        concentration_gap_pct: 風險%−市值% ≥ 此百分點 → concentrated=True。

    Returns:
        RiskContributionResult(見 dataclass docstring)。
        缺資料 / 零波動等 → table 空 + note 說明(§1 不回假數)。
    """
    # 1. 權重正規化為 Series(float),丟掉 ≤0 / NaN
    try:
        w_all = pd.Series(weights, dtype="float64")
    except (TypeError, ValueError):
        return _empty("權重格式無法解析")
    w_all = w_all[w_all.notna() & (w_all > 0)]
    if w_all.empty:
        return _empty("沒有有效權重(市值佔比皆 0 或缺)")
    w_all.index = w_all.index.astype(str)
    total_w = float(w_all.sum())

    if not isinstance(returns, pd.DataFrame) or returns.empty:
        return _empty("無報酬資料,無法算風險貢獻")
    ret_cols = {str(c): c for c in returns.columns}

    # 2. 交集:同時「有權重」+「有報酬欄」的 ticker;其餘剔除(不造假)
    cols = [t for t in w_all.index if t in ret_cols]
    excluded = [t for t in w_all.index if t not in ret_cols]
    excluded_w_pct = (round(float(w_all[excluded].sum()) / total_w * 100, 1)
                      if excluded else 0.0)
    if not cols:
        return _empty("持股都沒有價格歷史,無法算風險貢獻")

    # 3. 對齊觀測:所有納入資產都有報酬的交集日(dropna how=any)
    ret = returns[[ret_cols[t] for t in cols]].copy()
    ret.columns = cols
    ret = ret.apply(pd.to_numeric, errors="coerce").dropna(how="any")
    n_obs = int(len(ret))
    if n_obs < 2:
        return _empty(f"重疊交易日不足({n_obs} 日),無法估共變異數")

    # 4. 權重正規化(僅納入資產,加總=1)
    w = w_all[cols].astype("float64")
    w = w / w.sum()

    # 5. 共變異數 + Euler 分解(只用 Σw,不需反矩陣)
    cov = ret.cov()                                   # 日報酬共變異數(ddof=1)
    order = list(cov.index)
    w_vec = w.reindex(order).to_numpy()
    sigma_w = cov.to_numpy() @ w_vec                  # (Σw)_i
    var_p = float(w_vec @ sigma_w)                    # wᵀ Σ w
    if not np.isfinite(var_p) or var_p <= 0:
        return _empty("組合日波動為 0(持股價格無變動/停牌),風險佔比無意義")
    sigma_p = math.sqrt(var_p)
    rc = w_vec * sigma_w / sigma_p                    # RC_i,理論上 Σ = sigma_p

    # §4.3 對帳:Σ RC_i 必 = σ_p(代數保證;不符=實作 bug,fail-loud)
    if not math.isclose(float(rc.sum()), sigma_p, rel_tol=1e-7, abs_tol=1e-12):
        raise ValueError(
            f"風險貢獻 Euler 對帳失敗:Σ RC_i={rc.sum():.6g} ≠ σ_p={sigma_p:.6g}"
        )
    prc = rc / sigma_p                                # PRC_i,Σ = 1

    w_pct = np.round(w_vec * 100, 1)
    risk_pct = np.round(prc * 100, 1)
    gap_pct = np.round(risk_pct - w_pct, 1)
    table = pd.DataFrame({
        "ticker": order,
        "weight_pct": w_pct,
        "risk_pct": risk_pct,
        "gap_pct": gap_pct,
        "concentrated": gap_pct >= float(concentration_gap_pct),
    }).sort_values("risk_pct", ascending=False).reset_index(drop=True)

    sigma_annual_pct = round(sigma_p * math.sqrt(periods_per_year) * 100, 2)
    low_conf = n_obs < min_overlap

    notes: list[str] = []
    if excluded:
        notes.append(
            f"剔除 {len(excluded)} 檔無價格歷史(佔市值 {excluded_w_pct}%):"
            f"{'、'.join(excluded)}"
        )
    if low_conf:
        notes.append(f"重疊觀測僅 {n_obs} 日(<{min_overlap}),風險估計可信度較低")

    return RiskContributionResult(
        table=table,
        portfolio_vol_annual_pct=sigma_annual_pct,
        n_obs=n_obs,
        excluded=tuple(excluded),
        excluded_weight_pct=excluded_w_pct,
        low_confidence=low_conf,
        note="；".join(notes),
    )
