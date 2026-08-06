"""src/compute/etf/portfolio_fx.py — ETF 投組幣別換算 SSOT(L2 純函式,B1-a v19.179)。

為什麼有這個模組
================
`etf_tab_portfolio.py` 原本把**每一檔持股的原幣別金額直接相加**:

    r['current_value'] = r['shares'] * _cp      # BND 的 _cp 是 USD
    total_value        = sum(r['current_value'] for r in rows)   # 直接加進 TWD 總額

等於預設 **1 USD = 1 TWD**。實機(0050/00713/BND/00878)造成整頁每個數字都錯:
BND 現值被低估 32 倍 → 權重 6.8%(真值約 70%)、股債比 93/7(真值約 30/70)、
組合殖利率 12.20%(分子已換匯、分母沒有 → 真值約 3.9%),並連帶汙染
核心/衛星、產業曝險、風險貢獻分解、VaR 元金額、壓力測試、效率前緣權重。

設計原則
========
1. **單一換匯點**:整頁只在 rows 建構完成後呼叫一次 `convert_rows_to_twd()`,
   之後所有消費點(9 處)一律吃同一套 TWD 欄位,**不**在各消費點各自換。
2. **§1 Fail Loud, Never Fake**:匯率拿不到 / 超出 sanity 範圍時
   **絕不預設 1.0** —— 該檔標 `needs_fx=True` 並從 `rows` 移入 `excluded`,
   不計入任何總計;caller 負責在畫面顯示 ⚠️ 並 log。
3. **零 I/O**:匯率由 caller(L5,EX-PASSTHRU-1)fetch 後傳入,本模組純計算易測。
4. **原幣保留**:換匯後仍保留 `*_native` 欄供畫面顯示「BND 現價 72.50 USD」,
   避免把美元價格印成台幣數字誤導。

⚠️ 已知限制(誠實揭露,§1)
=========================
成本(`cost` / `avg_price`)與現值(`current_value` / `current_price`)**都用同一個
今日即期匯率**換算。因此 `capital_gain` 是**純價格報酬 × 今日匯率**,
**不含匯兌損益** —— 使用者真實的匯兌損益取決於當初買進時的換匯匯率,
本頁沒有那筆資料,故**不估**(估了就是捏造)。caller 須把這句話顯示給使用者。
"""
from __future__ import annotations

from shared.signal_thresholds import USDTWD_SANITY_MAX, USDTWD_SANITY_MIN

#: 幣別代碼(§3.3 反捏造:禁止各處 inline 'TWD'/'USD' 字串)
CURRENCY_TWD: str = 'TWD'
CURRENCY_USD: str = 'USD'

#: 需要 × 匯率的「金額 / 單價」欄位。ratio 類(capital_gain_pct / actual_pct /
#: target_pct / deviation)刻意**不**列入 —— 匯率在分子分母相消,換了反而錯。
FX_SCALED_FIELDS: tuple[str, ...] = (
    'cost',
    'current_value',
    'capital_gain',
    'dividend_received',
    'total_pnl',
    'current_price',
    'avg_price',
)


def holding_currency(ticker) -> str:
    """持股計價幣別 SSOT:台股 `.TW` / `.TWO` → 'TWD';其餘 → 'USD'。

    ⚠️ **限制**:本專案 ETF 只涵蓋台股 + 美股兩個市場(見 `etf_categories`),
    且**唯一可得的線索是代號後綴** —— yfinance 的 `info['currency']` 需要
    多一次網路往返、海外 IP 常被擋、且拿不到時會回 None(拿不到就得 fail loud,
    反而讓全台股組合也可能算不出來)。故此處用後綴判斷,並明講這是脆弱假設:

      * 代號沒後綴 → 一律當 USD(對美股 ETF 正確;若使用者少打 `.TW`,
        會被當美元 → 換匯後金額放大約 32 倍,屬**已知誤判方向**)。
      * 未來若新增第三個市場(港股 `.HK` / 日股 `.T` 等)**必須**回來擴充,
        否則會被當成 USD。

    `etf_dividend_schedule.dividend_currency` 已改為委派本函式(單一實作)。
    """
    _t = str(ticker or '').upper().strip()
    if _t.endswith('.TW') or _t.endswith('.TWO'):
        return CURRENCY_TWD
    return CURRENCY_USD


def normalize_usdtwd_rate(rate) -> float | None:
    """把 caller 傳來的 USD/TWD 匯率正規化成「可用的 float」或 None。

    §1:任何無法確信的輸入(None / 非數字 / NaN / 超出 §3.2 sanity 範圍
    [USDTWD_SANITY_MIN, USDTWD_SANITY_MAX])一律回 **None**,
    交給呼叫端 fail loud —— **不**退回 1.0、不夾到邊界值。
    """
    if rate is None:
        return None
    try:
        _r = float(rate)
    except (TypeError, ValueError):
        return None
    if _r != _r:  # NaN(不用 math.isnan 以免多一個 import;NaN != NaN)
        return None
    if not (USDTWD_SANITY_MIN <= _r <= USDTWD_SANITY_MAX):
        return None
    return _r


def convert_rows_to_twd(rows, usdtwd_rate=None) -> dict:
    """**單一換匯點** — 把投組 rows 統一換算成 TWD。

    Args:
        rows: list[dict],每筆至少含 `ticker`;金額欄位(見 FX_SCALED_FIELDS)
              為**該檔原幣別**金額。缺欄位者略過該欄(不補 0)。
        usdtwd_rate: USD/TWD 即期匯率(TWD per 1 USD)。None / 非法 → 見下。

    Returns:
        dict {
          'rows':      list[dict],  # 已全部是 TWD,可安全相加(caller 用這份取代原 rows)
          'excluded':  list[dict],  # 美元計價但換不了匯 → 原幣值原封不動 + needs_fx=True
          'rate_used': float|None,  # 實際採用的匯率(provenance;全台股組合為 None)
          'any_needs_fx': bool,     # 有檔被排除 → caller 必須顯示 ⚠️
          'usd_tickers': list[str], # 組合中所有美元計價代號(不論換不換得成)
        }

    每筆輸出 row 額外帶:
        `currency` / `fx_rate`(TWD 檔為 1.0)/ `needs_fx` /
        `<field>_native`(原幣別原值,供畫面顯示原幣單價)。

    §1:`usdtwd_rate` 無效時**不會**用 1.0 頂替 —— 美元檔一律進 `excluded`,
    不進 `rows`,因此不會被任何總計/權重/VaR/壓測吃到。
    """
    _rate = normalize_usdtwd_rate(usdtwd_rate)

    out_rows: list[dict] = []
    excluded: list[dict] = []
    usd_tickers: list[str] = []

    for _r in rows or []:
        if not isinstance(_r, dict):
            continue
        _row = dict(_r)  # 純函式:不就地改 caller 的 dict
        _cur = holding_currency(_row.get('ticker'))
        _row['currency'] = _cur

        # 原幣值先備份(不論幣別都存,讓畫面/測試有一致契約)
        for _f in FX_SCALED_FIELDS:
            if _f in _row:
                _row[f'{_f}_native'] = _row[_f]

        if _cur == CURRENCY_TWD:
            _row['fx_rate'] = 1.0
            _row['needs_fx'] = False
            out_rows.append(_row)
            continue

        usd_tickers.append(str(_row.get('ticker')))
        if _rate is None:
            # §1 Fail Loud:不腦補匯率、不用 1.0 → 該檔整筆排除出總計
            _row['fx_rate'] = None
            _row['needs_fx'] = True
            excluded.append(_row)
            continue

        _scaled = dict(_row)
        _bad_field = None
        for _f in FX_SCALED_FIELDS:
            if _f not in _scaled:
                continue
            try:
                _scaled[_f] = float(_scaled[_f]) * _rate
            except (TypeError, ValueError) as _e:
                # §1:換不成就是換不成 —— **不**留一個半換半沒換的混幣 row,
                # 整筆退回 excluded 讓畫面 fail loud。
                print(f'[portfolio_fx] {_row.get("ticker")} 欄位 {_f} 無法換匯'
                      f'({type(_e).__name__}: {_e}) → 整筆排除出 TWD 總計')
                _bad_field = _f
                break
        if _bad_field is not None:
            _row['fx_rate'] = None
            _row['needs_fx'] = True
            excluded.append(_row)
            continue

        _scaled['fx_rate'] = _rate
        _scaled['needs_fx'] = False
        out_rows.append(_scaled)

    return {
        'rows': out_rows,
        'excluded': excluded,
        'rate_used': _rate,
        'any_needs_fx': bool(excluded),
        'usd_tickers': usd_tickers,
    }


def fx_disclosure_caption(rate, as_of=None, source=None) -> str:
    """換匯揭露文案 SSOT(§2.2 provenance:匯率值 + as-of + 來源)。"""
    _r = normalize_usdtwd_rate(rate)
    if _r is None:
        return ''
    _base = f'💱 美元計價持股已用 **1 USD = {_r:.4f} TWD** 換算為台幣'
    _meta = []
    if as_of:
        _meta.append(f'匯率日期 {as_of}')
    if source:
        _meta.append(f'來源 {source}')
    return _base + (f'（{"、".join(_meta)}）' if _meta else '')
