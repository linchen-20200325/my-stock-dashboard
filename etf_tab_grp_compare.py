from data_config import CACHE_TTL
"""ETF 憭??寞活閰?瘥? Tab (v18.223)??

UI嚗extarea 憭?頛詨嚗?憭?10 瑼??啗?舐? .TW嚗? ThreadPool 銝西???5y ??
    7 蝬剖漲璅???甈???5 ??蝑?摨”??

銴?Ｘ?撅歹??園?蝞?嚗?
- etf_fetch: fetch_etf_price / fetch_etf_dividends / fetch_etf_info
- etf_calc: calc_total_return_1y / calc_current_yield / calc_sharpe / calc_mdd / calc_cagr
- etf_quality.compute_etf_quality: ? yield_cv 摮?嚗??拍?蝛拙?摨佗?
- etf_scoring_helpers.compute_etf_composite_score: 7 蝬剖漲??
"""
from __future__ import annotations

import re as _re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

from etf_fetch import fetch_etf_price, fetch_etf_dividends, fetch_etf_info
from etf_calc import (
    calc_total_return_1y, calc_current_yield,
    calc_sharpe, calc_mdd, calc_cagr,
    calc_avg_yield, calc_premium_discount,
)
from etf_quality import compute_etf_quality
from etf_scoring_helpers import compute_etf_composite_score
from etf_helpers import normalize_etf_ticker

_TOKEN_RE = _re.compile(r'[A-Za-z0-9.]+')


def parse_etf_codes(raw: str, limit: int = 10) -> list[str]:
    """閫??憭? ETF嚗?/蝛箸/??嚗??normalize_etf_ticker SSOT ???啗蝝?4-6 蝣潸?? .TW??""
    if not raw:
        return []
    _out: list[str] = []
    _seen: set = set()
    for _t in _TOKEN_RE.findall(raw):
        _t = normalize_etf_ticker(_t)
        if not _t or _t in _seen:
            continue
        _seen.add(_t)
        _out.append(_t)
        if len(_out) >= limit:
            break
    return _out


def _yield_valuation_zone(cur_yield: float | None, avg_yield: float | None) -> str:
    """7% 摮隡啣潸眺鞈?? ???∪? etf_tab_single L262-298 摮急樴??乓?

    ? 5y 撟喳?畾???潭??文?嚗??"????
    """
    if not avg_yield or avg_yield <= 0 or cur_yield is None:
        return '??
    if cur_yield >= 7:
        return '? 撘瑞?鞎琿?
    if cur_yield <= 3:
        return '? ?脣鈭?'
    if cur_yield <= 5:
        return '? ?拙漲皜Ⅳ'
    return '??銝剜扳???


def _dividend_health_label(cur_yield: float | None,
                           total_ret_1y: float | None,
                           cagr_3y: float | None) -> str:
    """??亙熒摨????∪? etf_tab_single L231-246 MK 獢 #1+#2??

    ?急?梢 ??畾??= ?? ???急 < 畾??= ?祇?靘菔? ?嚗?
    ?⊿??舐?亦? 3Y CAGR ??7% ?? ???血? ???
    """
    if cur_yield is None or cur_yield <= 0:
        if cagr_3y is None:
            return '漎?鞈?銝雲'
        return '???⊥雿?璅? if cagr_3y >= 7 else '? ?⊥銝??'
    if total_ret_1y is None:
        return '漎?1Y ?梢蝻?
    if total_ret_1y < cur_yield:
        return f'? ???{total_ret_1y - cur_yield:+.1f}pp'
    return f'???? {total_ret_1y - cur_yield:+.1f}pp'


def _fetch_one_etf(ticker: str) -> dict:
    """?格? ETF 5y ?? + 7 蝬剖漲?? + 4 SSOT 鋆?嚗?皞Ｗ/7%隡啣???亙熒/?釭嚗?蝔??剁???st.* ?游??""
    _r = {
        'ticker': ticker, 'name': '', 'error': None,
        'price': None, 'total_ret_1y': None, 'cagr_3y': None,
        'sharpe': None, 'mdd': None,
        'expense_ratio': None, 'aum': None,
        'div_yield': None, 'beta': None, 'quality': None,
        # v18.224嚗??格?????4 SSOT 甈?
        'premium_pct': None, 'stale_nav': False,
        'avg_yield_5y': None, 'valuation_zone': '??,
        'dividend_health': '漎?鞈?銝雲',
    }
    try:
        _df = fetch_etf_price(ticker, period='5y')
        if _df is None or _df.empty or 'Close' not in _df.columns:
            _r['error'] = '??K 蝺???
            return _r
        _divs = fetch_etf_dividends(ticker)
        _info = fetch_etf_info(ticker) or {}
        _r['name'] = (_info.get('shortName') or _info.get('longName')
                      or ticker)[:30]
        _r['price'] = round(float(_df['Close'].iloc[-1]), 2)
        _r['total_ret_1y'] = calc_total_return_1y(_df, _divs)
        _r['div_yield'] = calc_current_yield(_df, _divs)
        _r['cagr_3y'] = calc_cagr(_df)
        _r['sharpe'] = calc_sharpe(_df)
        _r['mdd'] = calc_mdd(_df)
        _r['expense_ratio'] = _info.get('annualReportExpenseRatio')
        _r['aum'] = _info.get('totalAssets')
        _r['beta'] = _info.get('beta') or _info.get('beta3Year')
        # compute_etf_quality ??@st.cache_data(ttl=CACHE_TTL["daily_snapshot"]) ??蝺??批?怠??剁?Streamlit cache ?芸葆 lock嚗?
        _r['quality'] = compute_etf_quality(ticker)

        # v18.224嚗? SSOT 鋆?嚗?皞Ｗ / 7% 隡啣?/ ??亙熒摨佗?
        try:
            _pd_res = calc_premium_discount(_info, _df, ticker)
            _r['premium_pct'] = _pd_res.get('premium_pct')
            _r['stale_nav'] = bool(_pd_res.get('stale_nav'))
        except Exception:
            pass
        try:
            _r['avg_yield_5y'] = calc_avg_yield(_df, _divs, years=5)
        except Exception:
            pass
        _r['valuation_zone'] = _yield_valuation_zone(
            _r['div_yield'], _r['avg_yield_5y'])
        _r['dividend_health'] = _dividend_health_label(
            _r['div_yield'], _r['total_ret_1y'], _r['cagr_3y'])
    except Exception as _e:
        _r['error'] = f'{type(_e).__name__}: {str(_e)[:50]}'
    return _r


def render_etf_grp_compare() -> None:
    """憭? ETF ?寞活閰?瘥?銝餃????7 蝬剖漲?? 5 ? PK 銵具?""
    st.markdown('### ?? 憭? ETF 閰?瘥? ??7 蝬剖漲?? 5 ??蝑?)
    st.caption(
        '頛詨?憭?10 瑼?ETF嚗?/蝛箸/??嚗?∠??詨??芸?鋆?.TW嚗?'
        '蝟餌絞銝西???5y ?豢? + 蝞?7 蝬剖漲嚗?Y 蝝舐? / 3Y CAGR / 憭 / MDD / '
        '鞎餌??/ AUM / 畾?帘摰漲嚗? ?? ??1~5 ??蝑帖??PK??
    )

    raw = st.text_area(
        'ETF 隞?Ⅳ嚗?/蝛箸/??嚗?憭?10 瑼?',
        value='0050 0056 00878 00919 00929',
        height=80, key='_etf_grp_input',
    )
    tickers = parse_etf_codes(raw, limit=10)
    if not tickers:
        st.info('隢撓?亥撠?1 瑼?ETF 隞?Ⅳ??)
        return
    st.caption(f'?? 敺???{", ".join(tickers)}嚗 {len(tickers)} 瑼?')

    if not st.button('? ???寞活閰?', type='primary',
                     use_container_width=True, key='_etf_grp_run'):
        st.info('? 暺??寞??蒂銵? 5y ?豢? + 閮? 7 蝬剖漲嚗?甈?~20s嚗歇敹怠?蝘?嚗?)
        return

    # 敹怠???rerun ??嚗ey ??tickers tuple嚗?
    _cache_key = f'_etf_grp_results_{hash(tuple(tickers))}'
    rows = st.session_state.get(_cache_key)
    if rows is None:
        rows = []
        prog = st.progress(0.0, text=f'?寞活閰?銝哨?{len(tickers)} 瑼蒂銵?...')
        with ThreadPoolExecutor(max_workers=5) as _ex:
            _futs = {_ex.submit(_fetch_one_etf, _t): _t for _t in tickers}
            _done = 0
            for _fut in as_completed(_futs):
                _done += 1
                prog.progress(_done / len(tickers),
                              text=f'[{_done}/{len(tickers)}] 摰?')
                try:
                    rows.append(_fut.result())
                except Exception as _e:
                    rows.append({'ticker': _futs[_fut],
                                 'error': f'{type(_e).__name__}: {str(_e)[:50]}'})
        prog.empty()
        # 蝬剜?頛詨????嚗s_completed ?臬???摨?
        _order = {_t: _i for _i, _t in enumerate(tickers)}
        rows.sort(key=lambda r: _order.get(r['ticker'], 999))
        st.session_state[_cache_key] = rows

    # ??閰?
    for _r in rows:
        if _r.get('error'):
            _r['composite'] = None
            _r['stars'] = None
            continue
        _r['composite'], _r['stars'] = compute_etf_composite_score(_r)

    # ?? 蝯梯?????
    _n_ok = sum(1 for r in rows if r.get('stars'))
    _n_5 = sum(1 for r in rows if r.get('stars') == 5)
    _n_4 = sum(1 for r in rows if r.get('stars') == 4)
    _n_3 = sum(1 for r in rows if r.get('stars') == 3)
    _n_low = sum(1 for r in rows if r.get('stars') and r['stars'] <= 2)
    cols = st.columns(5)
    cols[0].metric('?? 5 ??, _n_5)
    cols[1].metric('潃?4 ??, _n_4)
    cols[2].metric('??3 ??, _n_3)
    cols[3].metric('? ?? ??, _n_low)
    cols[4].metric('????憭望?', len(rows) - _n_ok)

    # ?? 閰?銵???
    def _stars_str(s):
        return ('?? * s + '?? * (5 - s)) if s else '??

    df = pd.DataFrame([{
        '隞??':     r['ticker'],
        '?迂':     r.get('name', ''),
        '??':     _stars_str(r.get('stars')),
        '蝬???:   r.get('composite'),
        '撣':     r.get('price'),
        # v18.224嚗?皞Ｗ SSOT嚗tale ?葆 ??嚗?
        '?滯??':  ('?? NAV stale' if r.get('stale_nav')
                    else r.get('premium_pct')),
        '1Y 蝝舐?%': r.get('total_ret_1y'),
        '3Y CAGR%': r.get('cagr_3y'),
        '憭??:   r.get('sharpe'),
        'MDD%':     r.get('mdd'),
        '鞎餌??':  (r['expense_ratio'] * 100
                    if r.get('expense_ratio') is not None else None),
        'AUM(??':  (r['aum'] / 1e8
                    if r.get('aum') and r['aum'] > 0 else None),
        '畾??':  r.get('div_yield'),
        '5Y??%':  r.get('avg_yield_5y'),
        '7%隡啣?:   r.get('valuation_zone', '??),
        '??亙熒': r.get('dividend_health', '漎?),
        '?酉':     r.get('error') or '',
    } for r in rows])

    # ??嚗???擃?雿?None 畾踹?嚗?
    df = df.sort_values(
        by='蝬???, ascending=False, na_position='last', kind='stable',
    )
    st.dataframe(
        df, hide_index=True, use_container_width=True,
        column_config={
            '蝬???:   st.column_config.NumberColumn('蝬???, format='%.2f'),
            '?滯??':  st.column_config.Column(
                '?滯??',
                help='(撣 ??NAV) / NAV ? 100嚗? +1% 霅衣內?蜓?? ETF NAV stale 憿舐內 ??'),
            '1Y 蝝舐?%': st.column_config.NumberColumn('1Y 蝝舐?%', format='%.2f'),
            '3Y CAGR%': st.column_config.NumberColumn('3Y CAGR%', format='%.2f'),
            '憭??:   st.column_config.NumberColumn('憭??, format='%.2f'),
            'MDD%':     st.column_config.NumberColumn('MDD%', format='%.2f'),
            '鞎餌??':  st.column_config.NumberColumn('鞎餌??', format='%.2f'),
            'AUM(??':  st.column_config.NumberColumn('AUM(??', format='%,.1f'),
            '畾??':  st.column_config.NumberColumn('畾??', format='%.2f'),
            '5Y??%':  st.column_config.NumberColumn(
                '5Y??%', format='%.2f',
                help='餈?5 撟游像???拍?嚗重?園? 7% 摮??隡啣澆皞?'),
            '7%隡啣?:   st.column_config.TextColumn(
                '7%隡啣?,
                help='摮急樴??伐?畾?7%?撘瑞?鞎琿?/ 5%~7%?芯葉??/ 3%~5%?皜Ⅳ / ??%??脣鈭?'),
            '??亙熒': st.column_config.TextColumn(
                '??亙熒',
                help='MK 獢 #1+#2嚗?臬????畾??= ??韐?< 畾??= ????),
        },
    )
    st.caption(
        '? **7 蝬剜???*嚗?Y 蝝舐? 25% / 3Y CAGR 20% / 憭 15% / MDD 15% / '
        '鞎餌??12% / AUM 8% / 畾?帘摰漲 5%??
        '**????**嚗???嚗???.80 5?0.65 4?0.50 3?0.35 2??0.35 1??
        '蝻箄???摮??rescale ??甈???
        '**4 SSOT 鋆?**嚗?皞Ｗ嚗alc_premium_discount嚗? 7%隡啣潘?calc_avg_yield + 摮急樴??伐?'
        '/ ??亙熒嚗K 獢 #1+#2 ??韐?????/ ?釭??嚗歇?急蝬?????
    )

