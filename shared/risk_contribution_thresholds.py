"""shared/risk_contribution_thresholds.py — 投組風險貢獻分解門檻 SSOT(L0).

風險貢獻(Risk Contribution)分解用的語意常數。年化交易日走
`shared/signal_thresholds.TRADING_DAYS_PER_YEAR`(252),**不在此重複定義**(§3.3)。
"""
from __future__ import annotations

RC_MIN_OVERLAP_DAYS: int = 60
"""共變異數估計的最少重疊交易日;不足 → low_confidence 旗標(§1 誠實,仍算但標低可信度)。
   60 ≈ 一季,足夠估短期共變異結構,又不過度被單一事件左右。"""

RC_CONCENTRATION_GAP_PCT: float = 10.0
"""風險集中警示:某檔「風險佔比 − 市值佔比」≥ 此百分點 → 標記風險放大。
   10 個百分點 = 使用者一眼能感受的顯著落差(如市值 30% / 風險 42%)。"""
