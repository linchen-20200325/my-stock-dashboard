"""src/compute/risk/reconcile.py — 雙演算法對帳工具(S-RECON-1 v18.252)

§4.3 重算對帳:關鍵指標應有第二種演算法/源頭做交叉驗證,降低單源偏差風險。

範疇(per CLAUDE.md §4.3):
- 殖利率:FRED DGS10 vs Yahoo ^TNX(**刻度自動偵測**,v19.177;原寫死 ÷10)
- 健康評分:目前單一 path,缺對照演算法
- 月營收 YoY:`(本月 / 12 月前) - 1` vs FinMind 預算 YoY

本模組為 L2 Compute 純函式,無 I/O。caller 傳入兩個源頭的數據,本模組做比對 +
回 reconcile 結果 dict。

對外 API:
- normalize_tnx_quote(yahoo_tnx_value) -> (pct | None, source_label)
- reconcile_us10y_yield(fred_value, yahoo_tnx_value) -> dict
- reconcile_pair(name, value_a, value_b, *, source_a, source_b, abs_tol=1e-4,
                  rel_tol=1e-3) -> dict
"""
from __future__ import annotations

import math
from typing import Optional


def reconcile_pair(
    name: str,
    value_a: Optional[float],
    value_b: Optional[float],
    *,
    source_a: str,
    source_b: str,
    abs_tol: float = 1e-4,
    rel_tol: float = 1e-3,
) -> dict:
    """通用雙源對帳工具。

    Parameters
    ----------
    name : str
        指標名稱,例如 "US10Y_YIELD"。
    value_a, value_b : float | None
        兩源頭的數值;None 視為 source 失敗。
    source_a, source_b : str
        兩源頭的識別,例如 "FRED:DGS10" / "Yahoo:^TNX/10"。
    abs_tol, rel_tol : float
        math.isclose 容差(預設絕對 1e-4 + 相對 1e-3,適用百分點/比率場景)。

    Returns
    -------
    dict
        {
            'name': str,
            'value_a': float | None,
            'value_b': float | None,
            'source_a': str,
            'source_b': str,
            'delta_abs': float | None,    abs(a - b)
            'delta_rel': float | None,    abs(a - b) / max(abs(a), abs(b))
            'agree':     bool,             math.isclose pass
            'status':    'agree' | 'disagree' | 'a_missing' | 'b_missing' | 'both_missing',
        }
    """
    if value_a is None and value_b is None:
        return {
            'name': name, 'value_a': None, 'value_b': None,
            'source_a': source_a, 'source_b': source_b,
            'delta_abs': None, 'delta_rel': None,
            'agree': False, 'status': 'both_missing',
        }
    if value_a is None:
        return {
            'name': name, 'value_a': None, 'value_b': value_b,
            'source_a': source_a, 'source_b': source_b,
            'delta_abs': None, 'delta_rel': None,
            'agree': False, 'status': 'a_missing',
        }
    if value_b is None:
        return {
            'name': name, 'value_a': value_a, 'value_b': None,
            'source_a': source_a, 'source_b': source_b,
            'delta_abs': None, 'delta_rel': None,
            'agree': False, 'status': 'b_missing',
        }
    delta_abs = abs(value_a - value_b)
    _denom = max(abs(value_a), abs(value_b))
    delta_rel = delta_abs / _denom if _denom > 0 else 0.0
    agree = math.isclose(value_a, value_b, abs_tol=abs_tol, rel_tol=rel_tol)
    return {
        'name': name, 'value_a': value_a, 'value_b': value_b,
        'source_a': source_a, 'source_b': source_b,
        'delta_abs': delta_abs, 'delta_rel': delta_rel,
        'agree': agree, 'status': 'agree' if agree else 'disagree',
    }


# ══════════════════════════════════════════════════════════════════
# v19.177 P1-B ③ — `^TNX` 報價刻度偵測(§1 + §4.1 量綱)
#
# 【原本錯在哪】本檔舊版寫死 `yahoo_tnx / 10.0`,docstring 也宣告
# 「^TNX = 殖利率 × 10」。但**實機不是**:國際指標卡印的
# `cl_data['intl']['10Y公債殖利率']`(= Yahoo ^TNX 收盤)是 4.63,
# 且 `macro_core._sig_tnx` 直接拿它去比 4.5 / 3.5 的門檻
# (macro_core.py:571-573,605-611)—— 全站現行慣例是**直接 %**。
# ⇒ 舊碼把 4.63 除成 0.463,與 FRED 的 4.63 對帳必然 disagree,
#   「🔎 對帳面板」的 US10Y 那列**永久紅**(假紅,§1 錯的數字比沒有數字更危險)。
#
# 【為何不是直接把 ÷10 拿掉】Yahoo 對 `^TNX` 在不同時期 / 不同端點確實出現過
# 「殖利率 × 10」(42.5 表 4.25%)的慣例 —— 本 repo 既有測試就是照那個寫的
# (tests/test_reconcile.py:59 / tests/test_risk_radar.py:225)。硬 pin 任一邊
# 都會在另一邊產生假紅。
#
# 【處理原則】**偵測刻度,不猜換算**,與 `shared/macro_buckets.py` 的
# `valid_min/max` 守衛同款思路:
#   - 值 ∈ [0, 20]    → 直接 % 慣例(對齊 CLAUDE.md §3.2「US10Y (%) [0, 20]」)
#   - 值 ∈ (20, 200]  → ×10 慣例(= [0,20] 的十倍),除以 10 後仍在合理範圍
#   - 其餘(負值 / >200 / NaN)→ **回 None + log**,絕不硬湊
# 兩個區間**不重疊**,故判定是確定性的,不依賴 FRED 的值 —— 這點很重要:
# 若拿 FRED 去挑「比較接近的那個刻度」,等於為了讓兩邊一致而選答案,
# 對帳就失去意義了(§4.3 比的是獨立來源,不是比誰湊得比較準)。
#
# 【殘留模糊區的誠實揭露】若哪天 10Y 殖利率跌回 2% 以下且上游同時改用 ×10
# 慣例(raw ∈ [0,20] 但實為 0.x~2%),本函式會判成「直接 %」而讀錯。
# 那種情況下對帳結果會是 **disagree(大聲)**,不是靜默算錯 —— 這正是對帳面板
# 存在的目的。要根治需上游提供 provenance 欄位標明刻度,屬另案。
# ══════════════════════════════════════════════════════════════════
#: 直接 % 慣例的合理上限 —— 對齊 CLAUDE.md §3.2「US10Y (%) [0, 20]」
TNX_DIRECT_PCT_MIN: float = 0.0
TNX_DIRECT_PCT_MAX: float = 20.0
#: ×10 慣例的合理上限 = 直接 % 上限 × 10
TNX_X10_MAX: float = TNX_DIRECT_PCT_MAX * 10.0


def normalize_tnx_quote(yahoo_tnx: Optional[float]) -> tuple[Optional[float], str]:
    """把 Yahoo `^TNX` 原始報價收斂成「百分點」,並回報偵測到的刻度慣例。

    Parameters
    ----------
    yahoo_tnx : float | None
        Yahoo `^TNX` 收盤原始值(可能是 4.63 直接 %,也可能是 46.3 的 ×10 慣例)。

    Returns
    -------
    (value_pct, source_label)
        value_pct    : float | None —— 百分點;無法判定刻度時為 None(§1 不猜)。
        source_label : str          —— 帶偵測結果的來源字串,直接餵給
                                        `reconcile_pair(source_b=...)`,
                                        讓對帳面板看得到「這次讀成哪一種刻度」。
    """
    if yahoo_tnx is None:
        return None, "Yahoo:^TNX(未取得)"
    try:
        v = float(yahoo_tnx)
    except (TypeError, ValueError):
        print(f"[reconcile/us10y] ⚠️ ^TNX 值無法轉 float: {yahoo_tnx!r} → 視為未取得(§1)")
        return None, "Yahoo:^TNX(型別錯誤)"
    if v != v:  # NaN guard(NaN 的任何比較皆 False,顯式處理避免誤讀)
        print("[reconcile/us10y] ⚠️ ^TNX 值為 NaN → 視為未取得(§1)")
        return None, "Yahoo:^TNX(NaN)"

    if TNX_DIRECT_PCT_MIN <= v <= TNX_DIRECT_PCT_MAX:
        return v, "Yahoo:^TNX(直接%)"
    if TNX_DIRECT_PCT_MAX < v <= TNX_X10_MAX:
        return v / 10.0, "Yahoo:^TNX(×10慣例→/10)"

    # 負殖利率 / >200 → 兩種慣例都解釋不通(§3.2 US10Y 合理範圍 [0,20]%)。
    # 常見主因:上游 fallback 換成不同標的、或報價欄位被改成 price 而非 yield。
    print(f"[reconcile/us10y] ⚠️ ^TNX 值 {v} 落在兩種慣例的合理範圍外 "
          f"(直接% [{TNX_DIRECT_PCT_MIN}, {TNX_DIRECT_PCT_MAX}] / "
          f"×10 ({TNX_DIRECT_PCT_MAX}, {TNX_X10_MAX}]) → 回 None,**不猜換算**(§1)。")
    return None, f"Yahoo:^TNX(越界 {v:g},刻度不明)"


def reconcile_us10y_yield(
    fred_dgs10: Optional[float],
    yahoo_tnx: Optional[float],
) -> dict:
    """美 10 年期殖利率雙源對帳。

    Parameters
    ----------
    fred_dgs10 : float | None
        FRED DGS10 直接報率(% 單位,例如 4.25)。
    yahoo_tnx : float | None
        Yahoo `^TNX` **原始**報價。刻度由 `normalize_tnx_quote()` 偵測 ——
        4.63 讀成 4.63%、46.3 讀成 4.63%、越界則回 None(不猜)。
        v19.177 前本參數的 docstring 寫死「= 殖利率 × 10」,與實機不符,
        導致對帳面板 US10Y 那列永久紅,詳見本檔上方 P1-B ③ 區塊。

    對照:
        FRED DGS10(T1 官方)vs Yahoo ^TNX 正規化後(T2)→ 兩源頭應約相等。

    Returns
    -------
    dict
        reconcile_pair 標準回傳(name="US10Y_YIELD")。
        `source_b` 會帶偵測到的刻度(直接% / ×10慣例 / 越界),供 UI 顯示。
        容差預設 abs_tol=0.05(0.05 個百分點 = 5bp 內視為一致)。
    """
    converted_yahoo, _src_b = normalize_tnx_quote(yahoo_tnx)
    # bond yield 容差:5bp = 0.05%
    return reconcile_pair(
        name="US10Y_YIELD",
        value_a=fred_dgs10,
        value_b=converted_yahoo,
        source_a="FRED:DGS10",
        source_b=_src_b,
        abs_tol=0.05,
        rel_tol=0.02,
    )


def reconcile_monthly_revenue_yoy(
    self_calc_yoy_pct: Optional[float],
    finmind_yoy_pct: Optional[float],
) -> dict:
    """月營收 YoY 雙演算法對帳。

    對照:`(本月 / 12 月前) - 1`(自算) vs FinMind 直接提供的 YoY 欄。
    容差:絕對 0.1 個百分點(營收 YoY 浮動大,放寬點)。
    """
    return reconcile_pair(
        name="MONTHLY_REVENUE_YOY",
        value_a=self_calc_yoy_pct,
        value_b=finmind_yoy_pct,
        source_a="self_calc:(now/y_ago - 1)",
        source_b="FinMind:revenue_yoy_field",
        abs_tol=0.1,
        rel_tol=0.05,
    )


# ──────────────────────────────────────────────────────────────────
# 健康評分雙演算法(v18.396 P5-B5 新增,§4.3 補完最後一項)
# ──────────────────────────────────────────────────────────────────
# 背景:`compute_macro_health` 目前單一 path(`calc_traffic_light` 內 weighted-avg)。
# §4.3 要求雙演算法對帳。本檔新增 v2 算法:`min_of_factors`(Liebig 短板原則)
# 與 v1 對帳。差異超容差 → 警告短板隱藏(arithmetic mean 掩蓋了某因子過弱)。


def compute_health_score_arithmetic(
    jqavg: Optional[float],
    score_pct: Optional[float],
    fnet: Optional[float],
    *,
    weight_jq: Optional[float] = None,
    weight_score: Optional[float] = None,
    fnet_bonus: Optional[float] = None,
) -> Optional[float]:
    """v1 健康評分:加權平均(對齊 calc_traffic_light L94-98 既有計算)。

    Health = jqavg × HEALTH_WEIGHT_JQ + min(score_pct, 100) × HEALTH_WEIGHT_SCORE
             + (HEALTH_FNET_BONUS if fnet>0 else 0)

    v18.397 SSOT 對齊:預設值從 `macro_helpers` 既有 SSOT
    (HEALTH_WEIGHT_JQ / HEALTH_WEIGHT_SCORE / HEALTH_FNET_BONUS)引入,
    取代原 inline 0.4 / 0.4 / 20 預設(§3.3 反捏造)。

    Args:
        jqavg / score_pct / fnet: 同前
        weight_jq / weight_score / fnet_bonus: caller 可覆寫(校準腳本用);
          None → 用 SSOT 預設。

    Returns:
        健康分數(0-100,round 1 位)或 None(輸入缺值)
    """
    if jqavg is None or score_pct is None or fnet is None:
        return None
    # SSOT lazy import 避 module-level cross-link
    if weight_jq is None or weight_score is None or fnet_bonus is None:
        from src.compute.macro.macro_helpers import (
            HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE, HEALTH_FNET_BONUS,
        )
        if weight_jq is None:
            weight_jq = HEALTH_WEIGHT_JQ
        if weight_score is None:
            weight_score = HEALTH_WEIGHT_SCORE
        if fnet_bonus is None:
            fnet_bonus = HEALTH_FNET_BONUS
    return round(
        jqavg * weight_jq
        + min(score_pct, 100) * weight_score
        + (fnet_bonus if fnet > 0 else 0),
        1,
    )


def compute_health_score_min_of_factors(
    jqavg: Optional[float],
    score_pct: Optional[float],
    fnet: Optional[float],
    *,
    fnet_penalty_cap: float = 40.0,
) -> Optional[float]:
    """v2 健康評分:min-of-factors(Liebig 短板原則 — 木桶最短板決定容量)。

    Health = min(jqavg, min(score_pct, 100), [fnet_penalty_cap if fnet<=0])

    語意:任一因子過弱 → 整體健康度被該因子限制。比 arithmetic mean 更保守,
    可揭露被「平均」掩蓋的短板因子。

    Args:
        jqavg / score_pct / fnet: 同 arithmetic 版
        fnet_penalty_cap: 外資淨賣懲罰上限(視為 40 分壓制)

    Returns:
        健康分數(0-100,round 1 位)或 None
    """
    if jqavg is None or score_pct is None or fnet is None:
        return None
    factors = [jqavg, min(score_pct, 100)]
    if fnet <= 0:
        factors.append(fnet_penalty_cap)
    return round(min(factors), 1)


def reconcile_health_score(
    jqavg: Optional[float],
    score_pct: Optional[float],
    fnet: Optional[float],
    *,
    abs_tol: float = 15.0,
) -> dict:
    """健康評分雙演算法對帳(v1 arithmetic vs v2 min_of_factors)。

    對照:weighted-avg(常用)vs min-of-factors(保守 / 短板揭露)。
    容差:絕對 15 分(健康評分 0-100 量級,15 分內視為一致)。

    Returns:
        reconcile_pair 標準回傳(name="MACRO_HEALTH")。
        delta > abs_tol → 警告:arithmetic 可能掩蓋短板因子(查 jqavg / score / fnet)。
    """
    v1 = compute_health_score_arithmetic(jqavg, score_pct, fnet)
    v2 = compute_health_score_min_of_factors(jqavg, score_pct, fnet)
    return reconcile_pair(
        name="MACRO_HEALTH",
        value_a=v1,
        value_b=v2,
        source_a="weighted_avg(SSOT HEALTH_WEIGHT_*)",  # v19.102:值隨校準變,label 不寫死
        source_b="min_of_factors(Liebig)",
        abs_tol=abs_tol,
        rel_tol=0.30,  # 健康評分本身分散性大,30% rel 容差
    )
