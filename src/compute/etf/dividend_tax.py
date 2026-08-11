"""src/compute/etf/dividend_tax.py — 股利稅後試算(L2 純函式)。

台股配息「稅後」核心:二代健保補充保費(逐筆)+ 綜所稅股利二擇一(年度)。零 I/O、零
streamlit,可單測。門檻/稅率全走 shared.dividend_tax_thresholds SSOT(§3.3)。

⚠️ 僅適用**國內台幣配息**;海外/美元 ETF(海外所得+最低稅負制)不適用本模組,
由 caller 先排除並標記(§4.6 不混算)。
"""
from __future__ import annotations

import math

from shared.dividend_tax_thresholds import (
    DIVIDEND_SEPARATE_TAX_RATE,
    DIVIDEND_TAX_CREDIT_CAP_TWD,
    DIVIDEND_TAX_CREDIT_RATE,
    NHI_SINGLE_PAYMENT_CAP_TWD,
    NHI_SINGLE_PAYMENT_MIN_TWD,
    NHI_SUPPLEMENTARY_RATE,
)


def nhi_premium(payment_twd) -> int:
    """單筆股利給付的二代健保補充保費(TWD 整元)。

    規則:單筆 < 門檻(20,000)→ 0;達門檻 → floor( min(單筆, 上限) × 2.11% )。
    §實務:券商扣繳以「元」為單位無條件捨去(floor),避免帳目對不上(如 25,000×2.11%
    =527.5 → 527)。單筆上限 1,000 萬(超過部分不計)。
    """
    _d = float(payment_twd or 0.0)
    if _d < NHI_SINGLE_PAYMENT_MIN_TWD:
        return 0
    _base = min(_d, float(NHI_SINGLE_PAYMENT_CAP_TWD))
    return int(math.floor(_base * NHI_SUPPLEMENTARY_RATE))


def annual_dividend_tax(total_dividend_twd, marginal_rate) -> dict:
    """年度股利綜所稅:合併(可負=退稅) vs 分開,取較省者。

    合併 T_A = D × R − min(D × 8.5%, 80,000)   # 邊際率 R 低於 8.5% 時 T_A 可為負(節稅/退稅)
    分開 T_B = D × 28%
    Returns: {combined, separate, best, method}(金額四捨五入至整元;best=min(T_A,T_B))。
    """
    _d = float(total_dividend_twd or 0.0)
    _r = float(marginal_rate or 0.0)
    _credit = min(_d * DIVIDEND_TAX_CREDIT_RATE, float(DIVIDEND_TAX_CREDIT_CAP_TWD))
    _t_combined = _d * _r - _credit                       # 可為負
    _t_separate = _d * DIVIDEND_SEPARATE_TAX_RATE
    if _t_combined <= _t_separate:
        _best, _method = _t_combined, "合併"
    else:
        _best, _method = _t_separate, "分開"
    return {
        "combined": round(_t_combined),
        "separate": round(_t_separate),
        "best": round(_best),
        "method": _method,
    }


def after_tax_dividend(payments, marginal_rate=None) -> dict:
    """一組**單筆**股利金額(TWD)→ 稅後試算。

    Args:
        payments: 逐筆股利金額 list(每筆 = 該次除息 每股配息 × 持有股數;僅台幣)。
        marginal_rate: 綜所稅邊際稅率(0.05/.../0.40);None → 只算二代健保、不算綜所稅。

    Returns dict:
        gross          年度稅前總配息
        nhi_premium    二代健保補充保費合計(逐筆 floor 後加總)
        net_after_nhi  扣二代健保後
        income_tax     綜所稅(取較省;可負=退稅);marginal_rate None → None
        tax_method     '合併'/'分開';None
        tax_detail     annual_dividend_tax 明細;None
        net_after_all  稅後淨額 = gross − nhi − income_tax

    §1:無配息 → gross 0、稅後 0,不捏造。二代健保逐筆判門檻(月配每月各自比)。
    """
    _pays = [float(p or 0.0) for p in (payments or []) if float(p or 0.0) > 0]
    _gross = sum(_pays)
    _total_nhi = sum(nhi_premium(_p) for _p in _pays)
    _net_after_nhi = _gross - _total_nhi

    out = {
        "gross": round(_gross),
        "nhi_premium": _total_nhi,
        "net_after_nhi": round(_net_after_nhi),
        "income_tax": None,
        "tax_method": None,
        "tax_detail": None,
        "net_after_all": round(_net_after_nhi),
    }
    if marginal_rate is not None and _gross > 0:
        _tax = annual_dividend_tax(_gross, marginal_rate)
        out["income_tax"] = _tax["best"]
        out["tax_method"] = _tax["method"]
        out["tax_detail"] = _tax
        out["net_after_all"] = round(_net_after_nhi - _tax["best"])
    return out
