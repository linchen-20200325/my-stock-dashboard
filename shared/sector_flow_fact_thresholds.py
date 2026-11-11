"""shared/sector_flow_fact_thresholds.py — 板塊事實(L3 `sector_flow_fact_service`)容差常數 SSOT(L0).

Issue #1140 §B／G-3。純常數、零 import。
為何不放進 `shared/sector_flow_thresholds.py`:該檔被 `tests/test_batch_z42.py` 以 sha256 釘住原始內容
(突變還原檢查),新增常數會無端改動該釘值;故另立同領域的小檔,語意上仍是 sector_flow 常數 SSOT。
"""
from __future__ import annotations

#: 「最新交易日」各板塊淨額(億)的正/負/持平判定帶寬。|net| <= EPS 視為持平(含 0.0、-0.0),
#: 避免浮點 `== 0` 判定。依據:net_amt_yi 由 `張(round 0.1) × 1000 股 × 收盤(≥0.01 元) ÷ 1e8` 而來,
#: 最小的非零量化單位約 1e-7~1e-8 億;EPS 取 1e-9 億(= 0.1 元)明顯低於該單位(真實的非零淨額不會被
#: 吞成持平),又遠高於千億量級 float 加總誤差(~1e-13)。**0.0 是有效觀測**,計入持平,不是缺值。
SECTOR_NET_FLAT_EPS_YI: float = 1e-9

#: 對帳容差(絕對,億):逐列 `net == foreign+trust+dealer`、原始合計 vs 標準化合計、Σ列 vs 合計。
#: 取一個最小量化單位(1e-7 億 = 10 元);真實資料誤差 ~2e-13,偏移一個量化單位以上即視為對帳失敗。
SECTOR_NET_RECONCILE_ABS_TOL_YI: float = 1e-7

#: 對帳容差(相對):與上同時作為 `math.isclose(rel_tol=, abs_tol=)` 兩參數。
SECTOR_NET_RECONCILE_REL_TOL: float = 1e-9
