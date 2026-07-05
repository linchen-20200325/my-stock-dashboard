"""src/compute/etf/etf_dividend_schedule.py — ETF 每月配息明細(L2 純函式,v19.64)。

ETF 組合已有「配息日曆」但只畫**加總**月度長條圖,看不出「哪一檔在哪個月、配多少」。
user 要「看每月月配息」,參考基金面板的「累積 TWD 配息」。本模組把各檔已算好的
`compute_etf_annual_cashflow(...)['monthly_distribution']` 收成 **ETF × 12 月矩陣**,
並處理 §4.1 幣別陷阱:

  ⚠️ 美元計價 ETF(如 BND/AGG)配息是 USD,台股 .TW/.TWO ETF 是 TWD。
  **禁止**把 USD 金額直接加進 TWD 總額(§4.1 TWD vs USD)。做法:
  caller 傳入 USD/TWD 即期匯率 → 本模組把 USD 配息換成 TWD;
  拿不到匯率 → 該檔標 needs_fx=True 且**不計入** TWD 總額(§1 fail loud,不腦補匯率)。

純計算層,零 I/O(匯率由 caller fetch 後傳入),易測。頻率門檻走
shared/dividend_frequency SSOT。
"""
from __future__ import annotations

from shared.dividend_frequency import (
    PAY_FREQ_ANNUAL_MIN,
    PAY_FREQ_BIMONTHLY_MIN,
    PAY_FREQ_LABEL_ANNUAL,
    PAY_FREQ_LABEL_BIMONTHLY,
    PAY_FREQ_LABEL_MONTHLY,
    PAY_FREQ_LABEL_NONE,
    PAY_FREQ_LABEL_QUARTERLY,
    PAY_FREQ_LABEL_SEMIANNUAL,
    PAY_FREQ_MONTHLY_MIN,
    PAY_FREQ_QUARTERLY_MIN,
    PAY_FREQ_SEMIANNUAL_MIN,
)

_MONTH_LABELS = [f'{m}月' for m in range(1, 13)]


def classify_pay_frequency(n_payments) -> str:
    """近 1 年配息次數 → 頻率標籤。門檻走 shared/dividend_frequency SSOT。"""
    try:
        n = int(n_payments or 0)
    except (TypeError, ValueError):
        n = 0
    if n >= PAY_FREQ_MONTHLY_MIN:
        return PAY_FREQ_LABEL_MONTHLY
    if n >= PAY_FREQ_BIMONTHLY_MIN:
        return PAY_FREQ_LABEL_BIMONTHLY
    if n >= PAY_FREQ_QUARTERLY_MIN:
        return PAY_FREQ_LABEL_QUARTERLY
    if n >= PAY_FREQ_SEMIANNUAL_MIN:
        return PAY_FREQ_LABEL_SEMIANNUAL
    if n >= PAY_FREQ_ANNUAL_MIN:
        return PAY_FREQ_LABEL_ANNUAL
    return PAY_FREQ_LABEL_NONE


def dividend_currency(ticker) -> str:
    """ETF 配息幣別:台股 .TW/.TWO → 'TWD';其餘(美股 ETF)→ 'USD'。

    註:本專案 ETF 只涵蓋台股 + 美股兩市場(見 etf_categories);
    如未來擴充其他市場需再細分。
    """
    _t = str(ticker or '').upper().strip()
    if _t.endswith('.TW') or _t.endswith('.TWO'):
        return 'TWD'
    return 'USD'


def build_monthly_dividend_rows(holdings, usdtwd_rate=None) -> dict:
    """把各檔 monthly_distribution 收成 ETF × 12 月矩陣 + TWD 總額(含幣別換算)。

    Args:
        holdings: list of dict,每檔需含:
            ticker(str)、name(str,可省)、
            monthly_distribution({1..12: 該月配息「原幣別」金額}) 或空、
            n_payments(int)。
            金額為「該檔幣別」(TWD ETF 即 TWD,USD ETF 即 USD)。
        usdtwd_rate: USD/TWD 即期匯率(float>0)。None / 無效 → USD 檔無法換匯。

    Returns:
        dict {
          'rows': [ {ticker, name, freq, currency, pay_months(list[int]),
                     monthly_twd({1..12}), annual_twd, needs_fx(bool)} ],
          'monthly_totals': {1..12: TWD 加總(只計已換算成 TWD 者)},
          'annual_total_twd': float,
          'any_needs_fx': bool,        # 有 USD 檔換不了匯 → UI 顯示 ⚠️
          'rate_used': float | None,   # 實際採用的 USD/TWD(供 provenance)
        }

    §4.1:USD 金額**只有**在 rate 有效時才 × rate 計入 TWD 總額;否則該檔
    needs_fx=True 且其月額**不**進 monthly_totals / annual_total_twd(不靜默混幣)。
    """
    try:
        _rate = float(usdtwd_rate) if usdtwd_rate is not None else None
    except (TypeError, ValueError):
        _rate = None
    if _rate is not None and _rate <= 0:
        _rate = None

    rows: list[dict] = []
    monthly_totals = {m: 0.0 for m in range(1, 13)}
    any_needs_fx = False

    for h in holdings or []:
        _tk = (h or {}).get('ticker')
        if not _tk:
            continue
        _cur = dividend_currency(_tk)
        _md_raw = (h or {}).get('monthly_distribution') or {}
        _n_pay = (h or {}).get('n_payments', 0)

        # 幣別換算:TWD 直接用;USD 有匯率 → ×rate,無匯率 → needs_fx(原幣顯示)。
        _needs_fx = False
        if _cur == 'USD':
            if _rate is None:
                _needs_fx = True
                _conv = 1.0  # 顯示原幣(USD),不進 TWD 總額
            else:
                _conv = _rate
        else:
            _conv = 1.0

        _monthly_twd = {}
        _annual = 0.0
        _pay_months = []
        for m in range(1, 13):
            try:
                _amt_native = float(_md_raw.get(m, 0.0) or 0.0)
            except (TypeError, ValueError):
                _amt_native = 0.0
            _amt = _amt_native * _conv
            _monthly_twd[m] = _amt
            if _amt_native > 0:
                _pay_months.append(m)
                _annual += _amt
                # 只有能換成 TWD(TWD 檔 或 USD 有匯率)才進組合總額
                if not _needs_fx:
                    monthly_totals[m] += _amt

        if _needs_fx:
            any_needs_fx = True

        rows.append({
            'ticker': _tk,
            'name': (h or {}).get('name') or _tk,
            'freq': classify_pay_frequency(_n_pay),
            'currency': _cur,
            'pay_months': _pay_months,
            'monthly_twd': _monthly_twd,
            'annual_twd': _annual,
            'needs_fx': _needs_fx,
        })

    annual_total_twd = sum(monthly_totals.values())
    return {
        'rows': rows,
        'monthly_totals': monthly_totals,
        'annual_total_twd': annual_total_twd,
        'any_needs_fx': any_needs_fx,
        'rate_used': _rate,
    }


def pay_months_str(pay_months) -> str:
    """[1,4,7,10] → '1,4,7,10月';空 → '—'。"""
    if not pay_months:
        return '—'
    return ','.join(str(m) for m in pay_months) + '月'
