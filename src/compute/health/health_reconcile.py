"""src/compute/health/health_reconcile.py — 健康評分對照演算法(L2 純函式,v18.300)

CLAUDE.md §4.3:
- 健康評分:目前單一 path(macro_helpers.calc_traffic_light health 欄位),
  缺對照演算法 → 步驟 3 audit 後補。
- 浮點比較禁用 ==,須用 math.isclose / np.isclose。

本檔提供第二個健康評分計算 path,用於對帳(reconciliation):
- Method A(生產):macro_helpers.calc_traffic_light 內 `_health` 計算
                  = jqavg*0.6 + min(score/max_score*100,100)*0.4 + (0 if fnet>0)
                  (v19.102 校準採納方案 B;fnet bonus 歸零)
- Method B(對照,本檔):**等權**平均兩個正規化分數
                  = (jqavg + min(score/max_score*100, 100)) / 2
                  v19.102:fnet 自平均中移除 — 校準(AUC 0.753,n=4748)顯示
                  fnet 對 20 日回撤預測力 ≈ 0,Method A 已歸零;Method B 若仍
                  1/3 等權 fnet,兩法常態性偏差 >tolerance = 恆噪音,失去對帳意義。
                  參數保留(向後相容+未來重校準)但不計分。

兩種 method 業務語意相同(評估 macro 健康度,值域 0-100),但加權不同
(A=0.6/0.4,B=0.5/0.5)→ 提供 cross-check;兩組件分歧大時 B 自然偏離 A
→ drift_warning 提示「廣度與市場分數打架」,是有效訊號非誤報。
abs diff > 5 視為告警(可能 method A weight 飄移 / 邊界極端值意外行為)。

設計
----
- L2 純函式,無 I/O,無 streamlit
- 對照 method 與生產 method 為獨立 path:不共用 weight 常數,獨立邏輯
- caller 對帳:`reconcile_health_score(method_a_result, **inputs) → diff dict`
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


# 對照演算法獨立常數(刻意**不**讀 shared/signal_thresholds 的 HEALTH_WEIGHT_*)
# 目的:第二 path 須獨立邏輯,若也讀 SSOT 則等同 method A copy,失去對帳意義
_METHOD_B_DEFAULT_MAX_SCORE: float = 4.0
"""Method B 內 score 正規化預設滿分(market_regime 基本滿分 4;
ad_ratio/m1b_m2 有傳才 5/6 — caller 可經 max_score 參數傳真值)。
v19.102:原 _METHOD_B_SCORE_SCALE=20(隱含 /5 錯配)退役,改 /max*100。"""

# 對帳容差 — abs diff > 此值視為告警
HEALTH_RECONCILE_TOLERANCE: float = 5.0
"""健康評分對帳容差(分)。
abs(method_a - method_b) > 5 → 告警:可能 method A weight 飄移或邊界值意外行為。
caller 應 log + 在輸出帶 reconcile_warning 旗標(§1 Fail Loud 對齊)。"""


@dataclass(frozen=True)
class HealthReconcileResult:
    """健康評分對帳結果。"""
    method_a: float          # 生產 method 分數(caller 傳入,通常從 calc_traffic_light['health'] 取)
    method_b: float          # 本檔對照 method 分數
    diff: float              # method_a - method_b(可正可負)
    abs_diff: float          # |diff|
    within_tolerance: bool   # abs_diff <= HEALTH_RECONCILE_TOLERANCE
    reason: str              # 'aligned' / 'drift_warning' / 'extreme_divergence'


def compute_method_b_health(
    jqavg: Optional[float],
    score: Optional[float],
    fnet: Optional[float] = None,
    *,
    max_score: Optional[float] = None,
) -> float:
    """Method B(對照演算法):等權平均兩個正規化分數(v19.102)。

    Parameters
    ----------
    jqavg : float | None
        旌旗指數(0-100)。None → 視為 50(中性)。
    score : float | None
        market_regime score(0~max_score)。None → 視為 0(無資料保守)。
    fnet : float | None
        v19.102 起**不計分**(校準顯示零預測力,Method A bonus 已歸零)。
        參數保留供向後相容與未來重校準,傳入值被忽略。
    max_score : float | None
        score 的真實滿分(market_regime 回傳 4/5/6)。None → 4.0(基本滿分)。

    Returns
    -------
    float
        Method B 健康分數(0-100,四捨五入到 1 位小數)。

    Examples
    --------
    >>> compute_method_b_health(60, 3, max_score=4)   # (60 + 75) / 2
    67.5
    >>> compute_method_b_health(0, 0)                 # 兩項都壞
    0.0
    """
    _ = fnet  # v19.102:保留參數,不參與計分(見 docstring)
    _jq = float(jqavg) if jqavg is not None else 50.0
    _sc = float(score) if score is not None else 0.0
    _max = float(max_score) if max_score else _METHOD_B_DEFAULT_MAX_SCORE

    # 正規化兩組件(0-100)
    _jq_norm = max(0.0, min(100.0, _jq))                      # jqavg 本身 0-100,clamp
    _sc_norm = max(0.0, min(100.0, _sc / _max * 100.0))       # score/max → 0-100

    return round((_jq_norm + _sc_norm) / 2.0, 1)


def reconcile_health_score(
    method_a_score: float,
    *,
    jqavg: Optional[float],
    score: Optional[float],
    fnet: Optional[float] = None,
    max_score: Optional[float] = None,
    tolerance: float = HEALTH_RECONCILE_TOLERANCE,
) -> HealthReconcileResult:
    """對帳生產 method A 與對照 method B,回報差異。

    Parameters
    ----------
    method_a_score : float
        生產演算法結果(從 calc_traffic_light(...)['health'] 取)。
    jqavg / score / fnet : 與 method A 同樣的輸入。
    tolerance : float
        容差,預設讀 SSOT。

    Returns
    -------
    HealthReconcileResult

    Notes
    -----
    浮點比較用 math.isclose 容差(§4.3 禁用 ==)。
    diff 極端(> 30)額外標 'extreme_divergence' 提醒可能輸入錯。
    """
    method_b = compute_method_b_health(jqavg, score, fnet, max_score=max_score)
    diff = method_a_score - method_b
    abs_diff = abs(diff)

    # 用 math.isclose 判斷在容差內(§4.3 浮點比較)
    within = abs_diff <= tolerance or math.isclose(
        abs_diff, tolerance, rel_tol=1e-9, abs_tol=1e-9
    )

    if abs_diff > 30.0:
        reason = 'extreme_divergence'
    elif within:
        reason = 'aligned'
    else:
        reason = 'drift_warning'

    return HealthReconcileResult(
        method_a=method_a_score,
        method_b=method_b,
        diff=diff,
        abs_diff=abs_diff,
        within_tolerance=within,
        reason=reason,
    )
