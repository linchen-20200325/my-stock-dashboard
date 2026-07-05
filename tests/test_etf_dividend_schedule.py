"""tests/test_etf_dividend_schedule.py — ETF 每月配息明細(L2 純函式)。

覆蓋 3 個最容易出錯的輸入:
1. 幣別混算(§4.1):USD ETF 無匯率→needs_fx 且不進 TWD 總額;有匯率→×rate。
2. 頻率分類邊界:12/11→月配、9→雙月配、4→季配、2→半年配、1→年配、0→不配息。
3. 空配息 / 缺月份 → pay_months 正確 + 不炸。
"""
from __future__ import annotations

from shared.dividend_frequency import (
    PAY_FREQ_LABEL_ANNUAL,
    PAY_FREQ_LABEL_BIMONTHLY,
    PAY_FREQ_LABEL_MONTHLY,
    PAY_FREQ_LABEL_NONE,
    PAY_FREQ_LABEL_QUARTERLY,
    PAY_FREQ_LABEL_SEMIANNUAL,
)
from src.compute.etf.etf_dividend_schedule import (
    build_monthly_dividend_rows,
    classify_pay_frequency,
    dividend_currency,
    pay_months_str,
)


# ── 1. 頻率分類邊界 ──
def test_frequency_boundaries():
    assert classify_pay_frequency(13) == PAY_FREQ_LABEL_MONTHLY
    assert classify_pay_frequency(12) == PAY_FREQ_LABEL_MONTHLY
    assert classify_pay_frequency(10) == PAY_FREQ_LABEL_MONTHLY
    assert classify_pay_frequency(9) == PAY_FREQ_LABEL_BIMONTHLY
    assert classify_pay_frequency(6) == PAY_FREQ_LABEL_BIMONTHLY
    assert classify_pay_frequency(5) == PAY_FREQ_LABEL_QUARTERLY
    assert classify_pay_frequency(4) == PAY_FREQ_LABEL_QUARTERLY
    assert classify_pay_frequency(3) == PAY_FREQ_LABEL_QUARTERLY
    assert classify_pay_frequency(2) == PAY_FREQ_LABEL_SEMIANNUAL
    assert classify_pay_frequency(1) == PAY_FREQ_LABEL_ANNUAL
    assert classify_pay_frequency(0) == PAY_FREQ_LABEL_NONE
    assert classify_pay_frequency(None) == PAY_FREQ_LABEL_NONE


# ── 幣別判斷 ──
def test_currency_detection():
    assert dividend_currency('0056.TW') == 'TWD'
    assert dividend_currency('006208.TWO') == 'TWD'
    assert dividend_currency('BND') == 'USD'
    assert dividend_currency('AGG') == 'USD'


# ── 2. §4.1 幣別混算 ──
def _twd_holding():
    return {'ticker': '00878.TW', 'name': '國泰永續高股息',
            'monthly_distribution': {m: (100.0 if m in (1, 4, 7, 10) else 0.0)
                                     for m in range(1, 13)},
            'n_payments': 4}


def _usd_holding():
    return {'ticker': 'BND', 'name': 'Vanguard Total Bond',
            'monthly_distribution': {m: 10.0 for m in range(1, 13)},
            'n_payments': 12}


def test_usd_without_rate_flagged_and_excluded_from_twd_total():
    out = build_monthly_dividend_rows([_twd_holding(), _usd_holding()],
                                      usdtwd_rate=None)
    assert out['any_needs_fx'] is True
    # TWD 檔一年 400,USD 檔未換匯不計入 → 組合年合計 = 400(只 TWD)
    assert out['annual_total_twd'] == 400.0
    _usd_row = next(r for r in out['rows'] if r['ticker'] == 'BND')
    assert _usd_row['needs_fx'] is True
    # USD 檔的月額仍以原幣顯示(×1),但沒進 monthly_totals
    assert out['monthly_totals'][2] == 0.0  # 2 月只有 USD,未換匯 → 0


def test_usd_with_rate_converted_into_twd_total():
    out = build_monthly_dividend_rows([_twd_holding(), _usd_holding()],
                                      usdtwd_rate=32.0)
    assert out['any_needs_fx'] is False
    assert out['rate_used'] == 32.0
    # TWD 400 + USD(10×12 = 120)×32 = 400 + 3840 = 4240
    assert out['annual_total_twd'] == 400.0 + 120.0 * 32.0
    _usd_row = next(r for r in out['rows'] if r['ticker'] == 'BND')
    assert _usd_row['needs_fx'] is False
    assert _usd_row['monthly_twd'][2] == 10.0 * 32.0  # 2 月 USD 已換匯


def test_invalid_rate_treated_as_no_rate():
    out = build_monthly_dividend_rows([_usd_holding()], usdtwd_rate=-5)
    assert out['any_needs_fx'] is True
    assert out['rate_used'] is None


def test_all_twd_rate_irrelevant():
    a = build_monthly_dividend_rows([_twd_holding()], usdtwd_rate=None)
    b = build_monthly_dividend_rows([_twd_holding()], usdtwd_rate=32.0)
    assert a['annual_total_twd'] == b['annual_total_twd'] == 400.0
    assert a['any_needs_fx'] is False


# ── 3. 空 / 缺月份 ──
def test_pay_months_and_empty():
    assert pay_months_str([1, 4, 7, 10]) == '1,4,7,10月'
    assert pay_months_str([]) == '—'
    out = build_monthly_dividend_rows([], usdtwd_rate=None)
    assert out['rows'] == []
    assert out['annual_total_twd'] == 0.0
    assert out['any_needs_fx'] is False


def test_holding_missing_distribution_no_crash():
    out = build_monthly_dividend_rows(
        [{'ticker': '0050.TW', 'n_payments': 0}], usdtwd_rate=None)
    r = out['rows'][0]
    assert r['pay_months'] == []
    assert r['annual_twd'] == 0.0
    assert r['freq'] == PAY_FREQ_LABEL_NONE


def test_pay_months_reflect_only_positive_months():
    h = {'ticker': '0056.TW', 'monthly_distribution': {3: 50.0, 9: 50.0},
         'n_payments': 2}
    out = build_monthly_dividend_rows([h], usdtwd_rate=None)
    assert out['rows'][0]['pay_months'] == [3, 9]
    assert out['rows'][0]['annual_twd'] == 100.0
