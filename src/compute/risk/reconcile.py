"""src/compute/risk/reconcile.py — 雙演算法對帳工具(S-RECON-1 v18.252)

§4.3 重算對帳:關鍵指標應有第二種演算法/源頭做交叉驗證,降低單源偏差風險。

範疇(per CLAUDE.md §4.3):
- 殖利率:FRED DGS10 vs Yahoo ^TNX(TNX = 10Y treasury × 10)
- 健康評分:目前單一 path,缺對照演算法
- 月營收 YoY:`(本月 / 12 月前) - 1` vs FinMind 預算 YoY

本模組為 L2 Compute 純函式,無 I/O。caller 傳入兩個源頭的數據,本模組做比對 +
回 reconcile 結果 dict。

對外 API:
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
        Yahoo ^TNX 報價(=殖利率 × 10,需除 10 才是 %)。

    對照:
        FRED DGS10 = TNX / 10 → 兩源頭應約相等。

    Returns
    -------
    dict
        reconcile_pair 標準回傳(name="US10Y_YIELD")。
        容差預設 abs_tol=0.05(0.05 個百分點 = 5bp 內視為一致)。
    """
    converted_yahoo = (yahoo_tnx / 10.0) if yahoo_tnx is not None else None
    # bond yield 容差:5bp = 0.05%
    return reconcile_pair(
        name="US10Y_YIELD",
        value_a=fred_dgs10,
        value_b=converted_yahoo,
        source_a="FRED:DGS10",
        source_b="Yahoo:^TNX/10",
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
