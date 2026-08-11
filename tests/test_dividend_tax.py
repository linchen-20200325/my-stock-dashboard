"""tests/test_dividend_tax.py — 股利稅後試算 純函式測試(L2)。

釘死使用者拍板的修正算式:
- 二代健保逐筆 floor(整元無條件捨去)+ 單筆門檻/上限
- 綜所稅合併(可負=退稅)vs 分開,取較省
- §1:無配息→0,不捏造
"""
from __future__ import annotations

import math

from shared.dividend_tax_thresholds import (
    DIVIDEND_TAX_CREDIT_CAP_TWD,
    NHI_SINGLE_PAYMENT_CAP_TWD,
    NHI_SUPPLEMENTARY_RATE,
)
from src.compute.etf.dividend_tax import (
    after_tax_dividend,
    annual_dividend_tax,
    nhi_premium,
)


# ── 二代健保補充保費 ────────────────────────────────────────────────────
def test_nhi_below_threshold_is_zero():
    assert nhi_premium(19_999) == 0
    assert nhi_premium(0) == 0
    assert nhi_premium(None) == 0


def test_nhi_at_threshold_charged():
    # 20,000 × 2.11% = 422.0 → 422
    assert nhi_premium(20_000) == 422


def test_nhi_floor_not_round_user_example():
    """使用者舉例:25,000 × 2.11% = 527.5 → 無條件捨去 527(不是四捨五入 528)。"""
    assert nhi_premium(25_000) == 527
    assert 25_000 * NHI_SUPPLEMENTARY_RATE == 527.5   # 佐證未捨去前為 .5


def test_nhi_single_payment_cap():
    """超過單筆上限 1,000 萬的部分不計:min(D, cap) × 2.11%。"""
    _expected = int(math.floor(NHI_SINGLE_PAYMENT_CAP_TWD * NHI_SUPPLEMENTARY_RATE))
    assert nhi_premium(20_000_000) == _expected           # 遠超上限 → 以上限計
    assert nhi_premium(NHI_SINGLE_PAYMENT_CAP_TWD) == _expected


# ── 綜所稅(合併 vs 分開)─────────────────────────────────────────────────
def test_income_tax_low_bracket_combined_is_refund():
    """邊際率 5% < 8.5% → 合併產生退稅(T_A 負),且比分開省。"""
    t = annual_dividend_tax(100_000, 0.05)
    # T_A = 100000×0.05 − min(100000×0.085, 80000) = 5000 − 8500 = −3500
    assert t["combined"] == -3500
    assert t["separate"] == 28_000
    assert t["best"] == -3500 and t["method"] == "合併"


def test_income_tax_high_bracket_separate_wins():
    """高額 + 高邊際率 → 分開 28% 較省。"""
    t = annual_dividend_tax(1_000_000, 0.40)
    # T_A = 1,000,000×0.40 − min(85,000,80,000)=400,000−80,000=320,000;T_B=280,000
    assert t["combined"] == 320_000
    assert t["separate"] == 280_000
    assert t["best"] == 280_000 and t["method"] == "分開"


def test_income_tax_credit_capped_at_80k():
    """8.5% 抵減以 8 萬為上限:股利 100 萬(×8.5%=85,000>80,000)→ 抵減僅 80,000。

    (精算上,抵減恰達 8 萬上限的臨界股利為 80,000/0.085 ≈ 941,177 元;此處用 100 萬
    確保已越過上限,避免踩在臨界點浮點邊界。)
    """
    _d = 1_000_000
    assert _d * 0.085 > DIVIDEND_TAX_CREDIT_CAP_TWD           # 85,000 > 80,000 → 抵減封頂
    t = annual_dividend_tax(_d, 0.20)
    # T_A = 1,000,000×0.20 − 80,000 = 120,000(抵減以上限 8 萬計,非 85,000)
    assert t["combined"] == 120_000


# ── after_tax_dividend 整合 ─────────────────────────────────────────────
def test_after_tax_monthly_each_below_threshold_no_nhi():
    """月配每月各 <2 萬 → 逐筆免二代健保(不年度加總比門檻)。"""
    pays = [15_000] * 12          # 年 18 萬,但每筆 <2 萬
    r = after_tax_dividend(pays)  # 不帶邊際率 → 只算健保
    assert r["nhi_premium"] == 0
    assert r["gross"] == 180_000
    assert r["net_after_nhi"] == 180_000
    assert r["income_tax"] is None
    assert r["net_after_all"] == 180_000


def test_after_tax_with_income_tax_full_chain():
    """含綜所稅:兩筆各 3 萬(各扣健保)+ 邊際率 20%。"""
    pays = [30_000, 30_000]       # 各 ≥2萬 → 各 floor(30000×0.0211)=633
    r = after_tax_dividend(pays, marginal_rate=0.20)
    assert r["nhi_premium"] == 633 * 2
    assert r["gross"] == 60_000
    assert r["net_after_nhi"] == 60_000 - 1266
    # T_A = 60000×0.20 − min(5100,80000)=12000−5100=6900;T_B=16800 → best 合併 6900
    assert r["tax_method"] == "合併"
    assert r["income_tax"] == 6900
    assert r["net_after_all"] == round(60_000 - 1266 - 6900)


def test_after_tax_no_dividend_is_zero():
    """§1:無配息 → 全 0,不捏造。"""
    r = after_tax_dividend([], marginal_rate=0.20)
    assert r["gross"] == 0 and r["nhi_premium"] == 0
    assert r["net_after_all"] == 0
    assert r["income_tax"] is None    # gross 0 → 不算綜所稅
