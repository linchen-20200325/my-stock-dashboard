from data_config import CACHE_TTL
"""TAB ?瘛勗漲?? + ?亙熒摨西?????敺?app.py ?賢嚗R P2-B Phase 5-C嚗?

靘陷蝑
========
- Top-level: streamlit嚗?蝛拙?嚗?
- ?賢???late import 41 ??鞈湛??踹?敺芰 import嚗?
  * stdlib: datetime, pandas, plotly
  * 閮剖?: config.FINMIND_TOKEN
  * 憭璅∠?: v4_strategy_engine / daily_checklist / v5_modules
    / financial_health_engine / tech_indicators / scoring_helpers / scoring_engine
    / ui_widgets / chart_plotter / data_loader
  * app.py ?折 (11): _fetch_stock_news / api_key / fetch_dividend_data
    / fetch_financials / fetch_price_data / fetch_quarterly / fetch_quarterly_extra
    / fetch_revenue / gemini_call / generate_ai_comment / render_health_score

?澆蝡?
======
- app.py: `with tab_stock: render_tab_stock()`
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW
from tab_helpers import format_condition_emoji, parse_cash_flow_ratio, safe_ma


@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def _fetch_share_capital(sid: str) -> float:
    """FinMind ???唬?摮??穿??桅?⊥嚗?????潘?憭望???0??

    靘??剝?霅血?閮???蝝???鞈?臬 撠??⊥瘥?撖行?靘??誨?? >0 ??瘀???
    Cache TTL 1 ?伐??⊥霈?璆萎??鳴???
    """
    import os as _os_sc
    import datetime as _dt_sc
    import requests as _rq_sc
    try:
        _tok = _os_sc.environ.get('FINMIND_TOKEN', '')
        _start = (_dt_sc.date.today() - _dt_sc.timedelta(days=540)).strftime('%Y-%m-%d')
        _p = {'dataset': 'TaiwanStockBalanceSheet', 'data_id': sid, 'start_date': _start}
        if _tok:
            _p['token'] = _tok
        _r = _rq_sc.get('https://api.finmindtrade.com/api/v4/data',
                        params=_p, timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        if not _data:
            return 0.0
        _dates = sorted({_row.get('date', '') for _row in _data}, reverse=True)
        _latest = _dates[0] if _dates else ''
        for _row in _data:
            if _row.get('date') != _latest:
                continue
            _t = str(_row.get('type', ''))
            _nm = str(_row.get('origin_name', ''))
            if (_t in ('CommonStock', 'OrdinaryShare', 'ShareCapital')
                    or '?⊥' in _t or '?桅?⊥' in _nm or '?⊥' in _nm):
                try:
                    _v = float(str(_row.get('value', 0) or 0).replace(',', ''))
                    if _v > 0:
                        return _v
                except (TypeError, ValueError):
                    continue
        return 0.0
    except Exception:
        return 0.0


# ????????????????????????????????????????????????????????????????????
# v18.175 P/B 隡啣潸????? ??TWSE BWIBBU_d 甈???PRIMARY
# ????????????????????????????????????????????????????????????????????

@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def _fetch_pbratio_from_twse(sid: str) -> float:
    """v18.175嚗? TWSE OpenAPI BWIBBU_d ?游?? P/B ?∪瘛典潭?嚗撩?蝡舀?憡潘???

    ??Ｘ? yield_screener.fetch_twse_yield_pe() 1 ?亙翰???典???DataFrame嚗?
    ?蕪?箸?摰?sid ??寞楊?潭???雿項? TWSE 銝??∴?TPEx ? FinMind嚗?
    """
    try:
        from yield_screener import fetch_twse_yield_pe
        _df = fetch_twse_yield_pe()
        if _df is None or _df.empty:
            return 0.0
        _hit = _df[_df['隞?Ⅳ'].astype(str) == str(sid)]
        if _hit.empty:
            return 0.0
        _pb = _hit.iloc[0].get('?∪瘛典潭?')
        if _pb is None:
            return 0.0
        _pb_v = float(_pb)
        if not (0.01 < _pb_v < 100):
            return 0.0
        return _pb_v
    except Exception:
        return 0.0


# ?? ?Ｘ平??P/B ?曉澆??扯”嚗???/ ?蝘? / 鋆賡?default嚗?????????????
_PB_BANDS_FINANCIAL = (0.5, 0.9, 1.2)   # ??靽 / ?銵平
_PB_BANDS_GROWTH    = (1.5, 2.5, 4.0)   # ??擃?/ ?餃? / ? / ?縑蝬脰楝 / ?餉?券? / ?嗡??餃?
_PB_BANDS_MFG       = (0.8, 1.5, 2.5)   # 鋆賡平 default

_FINANCIAL_INDUSTRIES = ('??靽璆?, '?銵平', '霅璆?, '靽璆?, '??璆?)
_GROWTH_INDUSTRIES = (
    '??擃平', '?餃?撌交平', '?璆?, '?縑蝬脰楝璆?,
    '?餉?梢?閮剖?璆?, '?嗡??餃?璆?, '?餃??嗥?隞嗆平',
)


def _get_pb_bands(industry: str | None) -> tuple[float, float, float]:
    """v18.175嚗??Ｘ平憿? P/B 瘝單??帖撣園?潘?雿?銝?擃???

    - ??璆哨?(0.5, 0.9, 1.2) ???銵??ａ???PB<1 撅祆迤撣?
    - ?蝘?嚗?1.5, 2.5, 4.0) ??擃?ROE / ?箄瓷甈滯??
    - 鋆賡平 default嚗?0.8, 1.5, 2.5) ??????潘?靽? v18.174 銵嚗?
    """
    if not industry:
        return _PB_BANDS_MFG
    _ind = str(industry)
    if any(_kw in _ind for _kw in _FINANCIAL_INDUSTRIES):
        return _PB_BANDS_FINANCIAL
    if any(_kw in _ind for _kw in _GROWTH_INDUSTRIES):
        return _PB_BANDS_GROWTH
    return _PB_BANDS_MFG


def _pb_bands_label(industry: str | None) -> str:
    """v18.175嚗璆剖?曉潭?蝐????冽 caption 憿舐內??""
    if not industry:
        return '鋆賡平?身'
    _ind = str(industry)
    if any(_kw in _ind for _kw in _FINANCIAL_INDUSTRIES):
        return f'??璆哨?{_ind}嚗?
    if any(_kw in _ind for _kw in _GROWTH_INDUSTRIES):
        return f'?蝘?嚗_ind}嚗?
    return f'鋆賡平嚗_ind}嚗?


@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def _fetch_industry_category(sid: str) -> str:
    """v18.175嚗? FinMind TaiwanStockInfo ??Ｘ平憿摮葡?仃?? ''??

    ?冽 P/B 瘝單???澆??矽?湛???/?蝘?/鋆賡??? ?亙翰??
    """
    import os as _os_ic
    import requests as _rq_ic
    try:
        _tok = _os_ic.environ.get('FINMIND_TOKEN', '')
        _p = {'dataset': 'TaiwanStockInfo', 'data_id': sid}
        if _tok:
            _p['token'] = _tok
        _r = _rq_ic.get('https://api.finmindtrade.com/api/v4/data',
                        params=_p, timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        if not _data:
            return ''
        for _row in _data:
            _ind = _row.get('industry_category', '')
            if _ind:
                return str(_ind)
        return ''
    except Exception:
        return ''


@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def _fetch_bps_from_finmind(sid: str) -> float:
    """v18.174嚗inMind TaiwanStockBalanceSheet 閮???啣迤摨行??⊥楊?潘?BPS嚗?

    ?砍?嚗PS = ?⊥甈?蝮賡? / 瘚憭??⊥
         瘚??= ?桅?⊥ / ?ａ? 10 ???啗???嚗?

    PRIMARY 鞈?皞???瘥?yfinance bookValue ?單?銝項??TPEx??
    ?? 540 ??BS嚗?霅?餈摮????嚗??餈?蝑?date ?拙?雿?
      - ?⊥甈?蝮賡?嚗ype ??{Equity, TotalEquity} ??origin_name ??'?⊥甈?'/'甈?蝮賡?'
      - ?桅?⊥嚗? type ??{CommonStock, OrdinaryShare, ShareCapital} ??origin_name ??'?⊥'

    Sanity 摰?嚗PS ??(0.1, 5000)??????0.0嚗?雿???賂???
    BPS 摮????????敹怠? 1 ?乓?
    """
    import os as _os_bf
    import datetime as _dt_bf
    import requests as _rq_bf
    try:
        _tok = _os_bf.environ.get('FINMIND_TOKEN', '')
        _start = (_dt_bf.date.today() - _dt_bf.timedelta(days=540)).strftime('%Y-%m-%d')
        _p = {'dataset': 'TaiwanStockBalanceSheet', 'data_id': sid, 'start_date': _start}
        if _tok:
            _p['token'] = _tok
        _r = _rq_bf.get('https://api.finmindtrade.com/api/v4/data',
                        params=_p, timeout=15)
        _data = _r.json().get('data', []) if _r.status_code == 200 else []
        if not _data:
            return 0.0
        _dates = sorted({_row.get('date', '') for _row in _data}, reverse=True)
        _latest = _dates[0] if _dates else ''
        _equity = 0.0
        _common_stock = 0.0
        for _row in _data:
            if _row.get('date') != _latest:
                continue
            _t = str(_row.get('type', ''))
            _nm = str(_row.get('origin_name', ''))
            try:
                _v = float(str(_row.get('value', 0) or 0).replace(',', ''))
            except (TypeError, ValueError):
                continue
            if _v <= 0:
                continue
            # ?⊥甈?蝮賡?嚗????閮?蝮賡???摮??格毽瘛?
            if (not _equity and (_t in ('Equity', 'TotalEquity', 'StockholdersEquity')
                                  or '?⊥甈?蝮賡?' in _nm or '甈?蝮賡?' in _nm
                                  or '?⊥甈???' in _nm or '甈???' in _nm)):
                _equity = _v
            # ?桅?⊥嚗?潛?瘚?賂?
            elif (not _common_stock and (_t in ('CommonStock', 'OrdinaryShare', 'ShareCapital')
                                          or '?桅?⊥' in _nm
                                          or ('?⊥' in _nm and '?孵?? not in _nm))):
                _common_stock = _v
        if _equity <= 0 or _common_stock <= 0:
            return 0.0
        # BPS = ?⊥甈? / (?⊥/10 ?憿?
        _shares_outstanding = _common_stock / 10.0
        _bps = _equity / _shares_outstanding
        # Sanity嚗??BPS ??蝭? 0.1 ~ 5000 ??頞??0.0 ??yfinance ?交?
        if not (0.1 < _bps < 5000):
            return 0.0
        return float(_bps)
    except Exception:
        return 0.0


@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def _fetch_bps(sid: str) -> float:
    """瘥瘛典潘?BPS嚗?v18.174 靽格迤鞈?皞?FinMind BS PRIMARY嚗finance FALLBACK??

    ???桅? yfinance.Ticker().info['bookValue']嚗?∪迤?勗???畾萄虜?賢?
    1-3 ???撩?潘??啁??孵?韏?FinMind TaiwanStockBalanceSheet 蝞??啣迤摨?
    BPS嚗撘??⊥甈?蝮賡? / (?桅?⊥ / 10 ?憿?嚗?憭望????yfinance??

    BPS 摮????????敹怠? 1 ?伐??踹?瘥活 Streamlit rerun ?賡憛雯頝臬?怒?
    """
    # PRIMARY: FinMind BS嚗??啣迤摨佗??啗甈?嚗?
    _bps_fm = _fetch_bps_from_finmind(sid)
    if _bps_fm > 0:
        return _bps_fm
    # FALLBACK: yfinance bookValue嚗??stale嚗?瘥??撥嚗?
    try:
        import yfinance as _yf_pb
        for _sfx_pb in ('.TW', '.TWO'):
            try:
                _info_pb = _yf_pb.Ticker(f'{sid}{_sfx_pb}').info or {}
                _bps_v = _info_pb.get('bookValue')
                if _bps_v and float(_bps_v) > 0:
                    return float(_bps_v)
            except Exception:
                continue
    except Exception:
        pass
    return 0.0


def render_tab_stock():
    # ? Late imports嚗?儐??import嚗?
    import datetime
    import pandas as pd
    import plotly.graph_objects as go
    from config import FINMIND_TOKEN
    # 憭璅∠?
    from v4_strategy_engine import V4StrategyEngine
    from daily_checklist import analyze_20d_chips_from_df
    from exit_signals import (
        compute_tech_bearish, judge_news_sentiment_cached, evaluate_exit_signals,
    )
    from v5_modules import (
        analyze_fundamental_leading,
        calc_dividend_yield_357,
        detect_bollinger_breakout,
    )
    from financial_health_engine import analyze_financial_health, no_ai_overall_verdict
    from tech_indicators import (
        calc_rsi, calc_ibs, calc_volume_ratio,
        calc_kd, calc_bollinger, calc_vcp,
    )
    from scoring_helpers import calc_fundamental_score, calc_health_score, health_grade
    from scoring_engine import calc_rs_score, rs_slope
    from ui_widgets import kpi, signal_box, teacher_conclusion
    from chart_plotter import plot_combined_chart, plot_quarterly_chart, plot_revenue_chart
    from data_loader import fetch_financial_statements
    # app.py ?折 helper
    from app import (
        _fetch_stock_news, api_key,
        fetch_dividend_data, fetch_financials, fetch_price_data,
        fetch_quarterly, fetch_quarterly_extra, fetch_revenue,
        gemini_call, generate_ai_comment, render_health_score,
    )

    st.markdown('''<div style="background:#0a1628;border:1px solid #1f6feb;border-radius:12px;padding:16px;margin-bottom:12px;">
<div style="font-size:18px;font-weight:900;color:#58a6ff;margin-bottom:8px;">? ?瘛勗漲?? ????∠巨?澆?鞎瑕?嚗?/div>
<div style="font-size:13px;color:#c9d1d9;line-height:1.8;">
頛詨雿??閎?蟡其誨蝣潘?蝟餌絞??閮港?嚗?br>
??<b>?曉鞎港?鞎湛?</b>嚗?57隡啣?+ 瘝單???<br>
??<b>頞典?????嚗?/b>嚗摨瑕漲閰?嚗?br>
??<b>憭扯?勗鞎琿??航都嚗?/b>嚗?鈭箇?蝣潘?<br>
??<b>隞暻潭??府?脣??湛?</b>嚗脣?渲???<br>
? <b>撱箄降嚗?/b>???頛?? ??????啣?∴????ㄐ??敺Ⅱ隤?
</div></div>''', unsafe_allow_html=True)
    st.markdown("""<div style="padding:6px 0 4px;">
<span style="font-size:20px;font-weight:900;color:#e6edf3;">? ?瘛勗漲??</span>
<span style="font-size:11px;color:#484f58;margin-left:10px;">?亙熒閰? 繚 357閰 繚 ???? 繚 VCP 繚 撣? 繚 K蝺?繚 AI鈭雁</span>
</div>""", unsafe_allow_html=True)

    # ?? ??????????????????????????????????????????????????
    t2_r1c1, t2_r1c2, t2_r1c3, t2_r1c4 = st.columns([2, 1, 1, 1])
    with t2_r1c1:
        t2_sid = st.text_input('?隞?Ⅳ', value='2330', key='t2_sid', placeholder='憒?2330')
    with t2_r1c2:
        t2_days = st.slider('憭拇', 60, 400, 250, 10, key='t2_days')
    with t2_r1c3:
        t2_use_normal = st.checkbox('銝?春蝺?, value=False, key='t2_use_normal')
        t2_adjusted   = not t2_use_normal
    with t2_r1c4:
        t2_run = st.button('?? 頛摰??', key='t2_run', type='primary', use_container_width=True)

    # ?? ???豢?嚗宏?冉ab2嚗?撅?嚗??????????????????????
    with st.container(border=True):
        st.markdown('<span style="font-size:11px;color:#8b949e;">?? ??憿舐內閮剖?</span>', unsafe_allow_html=True)
        ma_c1,ma_c2,ma_c3,ma_c4,ma_c5,ma_c6 = st.columns(6)
        with ma_c1:
            show_ma5   = st.checkbox('MA5',      value=False, key='t2_ma5')
        with ma_c2:
            show_ma20  = st.checkbox('MA20 ??', value=True,  key='t2_ma20')
        with ma_c3:
            show_ma60  = st.checkbox('MA60 摮??', value=False, key='t2_ma60')
        with ma_c4:
            show_ma100 = st.checkbox('MA100',     value=True,  key='t2_ma100')
        with ma_c5:
            show_ma120 = st.checkbox('MA120',     value=False, key='t2_ma120')
        with ma_c6:
            show_ma240 = st.checkbox('MA240 撟渡?',value=False, key='t2_ma240')
    show_ma_dict = {'MA5':show_ma5,'MA20':show_ma20,'MA60':show_ma60,
                    'MA100':show_ma100,'MA120':show_ma120,'MA240':show_ma240}

    st.markdown("""<div style="background:#161b22;border:1px solid #21262d;border-left:4px solid #ffd700;
border-radius:8px;padding:10px 14px;font-size:12px;color:#8b949e;">
<b style="color:#ffd700;">?芸?敺雯頝舀???</b><br>
K蝺???(FinMind) 繚 銝之瘜犖蝐Ⅳ 繚 ??? 繚 357?∪閰 繚 ??摮???嗆??拍? 繚 ??鞎/鞈?臬 繚 ?亙熒閰?(RSI+??+IBS+KD+撣?)
</div>""", unsafe_allow_html=True)

    if t2_run:
        sid2 = t2_sid or '2330'
        st.info(f'?? ?? {sid2} ?冽雿??..')
        # v18.196 銝西???7 ?蝡?IO嚗?箏暺?RSS ??嚗?摨???ThreadPoolExecutor ??
        # cold-start ??30-50s + ?? RSS 璅??踹?銝虜?箏暺?憛憛?3-5s
        from concurrent.futures import ThreadPoolExecutor as _TPE_t2
        with _TPE_t2(max_workers=7) as _ex_t2:
            _fu_price = _ex_t2.submit(fetch_price_data, sid2, t2_days)
            _fu_div   = _ex_t2.submit(fetch_dividend_data, sid2)
            _fu_fin   = _ex_t2.submit(fetch_financials, sid2, '')
            _fu_rev   = _ex_t2.submit(fetch_revenue, sid2)
            _fu_qtr   = _ex_t2.submit(fetch_quarterly, sid2)
            _fu_qtr_extra = _ex_t2.submit(fetch_quarterly_extra, sid2)
            _fu_news  = _ex_t2.submit(_fetch_stock_news, sid2, sid2, 8, recency='3m')
            df2, name2, err2 = _fu_price.result()
            avg_div2, yearly2, div_src2 = _fu_div.result()
            cl2, cx2, _capex2, _cl_src2, _cx_src2, _, _fin_errs2 = _fu_fin.result()
            rev2, _ = _fu_rev.result()
            qtr2, _ = _fu_qtr.result()
            qtr_extra2, _ = _fu_qtr_extra.result()   # BS+CF??嚗?蝝???摮疏/鞈?臬嚗?
            try:
                _raw_news_pre = _fu_news.result() or []
                st.session_state[f'_exit_news_titles_{sid2}'] = [
                    n.get('title', '') for n in _raw_news_pre if n.get('title')
                ]
            except Exception:
                pass
        rsi2     = calc_rsi(df2)
        ibs2     = calc_ibs(df2)
        vr2      = calc_volume_ratio(df2)
        k2, d2   = calc_kd(df2)
        bb2      = calc_bollinger(df2)
        vcp2     = calc_vcp(df2)
        health2, details2 = calc_health_score(df2, rsi2, ibs2, vr2, k2, d2, bb2)
        cur_price2 = float(df2['close'].iloc[-1]) if df2 is not None and not df2.empty else 0
        from stock_names import get_stock_name as _gsn2
        _name2_resolved = (name2 if name2 and name2 != sid2 else None) or _gsn2(sid2) or sid2
        st.session_state['t2_data'] = {
            'sid':sid2,'name':_name2_resolved,'df':df2,'err':err2,
            'avg_div':avg_div2,'yearly':yearly2,'div_src':div_src2,
            'cl':cl2,'cx':cx2,'rev':rev2,'qtr':qtr2,'qtr_extra':qtr_extra2,
            'cl_src': _cl_src2,'cx_src': _cx_src2,'fin_errs': _fin_errs2,
            'rsi':rsi2,'ibs':ibs2,'vr':vr2,'k':k2,'d':d2,'bb':bb2,'vcp':vcp2,
            'health':health2,'details':details2,'price':cur_price2,
            'fetched_at': pd.Timestamp.now(),
        }
        # 敹怠??敺?甈⊥????啁?????摮?瓷?梧?靘?甈∪仃?? fallback
        if rev2 is not None and not rev2.empty:
            st.session_state[f'_last_rev_{sid2}'] = rev2
        if qtr2 is not None and not qtr2.empty:
            st.session_state[f'_last_qtr_{sid2}'] = qtr2

    t2d = st.session_state.get('t2_data')
    if not t2d:
        st.info('?? 頛詨?∠巨隞?Ⅳ敺????頛摰????)
    else:
        sid2   = t2d['sid']
        name2  = t2d['name']
        price2 = t2d['price']
        df2    = t2d['df']
        health2 = t2d['health']
        details2 = t2d['details']
        rsi2=t2d['rsi']
        ibs2=t2d['ibs']
        vr2=t2d['vr']
        k2=t2d['k']
        d2=t2d['d']
        bb2=t2d['bb']
        vcp2=t2d['vcp']
        avg_div2=t2d['avg_div']
        yearly2=t2d['yearly']
        cl2=t2d['cl']
        cx2=t2d['cx']
        _cl_src2=t2d.get('cl_src','')
        _cx_src2=t2d.get('cx_src','')
        _fin_errs2=t2d.get('fin_errs',[])
        rev2=t2d['rev']
        qtr2=t2d['qtr']
        qtr_extra2=t2d.get('qtr_extra')
        # Fallback ?啣翰???交甈⊥??仃??
        _rev2_cached = False
        _qtr2_cached = False
        if (rev2 is None or rev2.empty) and st.session_state.get(f'_last_rev_{sid2}') is not None:
            rev2 = st.session_state[f'_last_rev_{sid2}']
            _rev2_cached = True
        if (qtr2 is None or qtr2.empty) and st.session_state.get(f'_last_qtr_{sid2}') is not None:
            qtr2 = st.session_state[f'_last_qtr_{sid2}']
            _qtr2_cached = True

        # v18.197 ?? ?? 鞈??圈悅摨行?嚗甇Ｘ + ???? + age + fallback 霅衣內 + 撘瑕??嚗???
        _fetched_at = t2d.get('fetched_at')
        _df_end_date = None
        try:
            if df2 is not None and not df2.empty:
                if hasattr(df2, 'index') and len(df2.index):
                    _df_end_date = pd.to_datetime(df2.index[-1])
                if (_df_end_date is None or pd.isna(_df_end_date)) and 'date' in df2.columns:
                    _df_end_date = pd.to_datetime(df2['date'].iloc[-1])
        except Exception:
            _df_end_date = None
        _fresh_cols = st.columns([5, 1])
        with _fresh_cols[0]:
            if _fetched_at is not None:
                _age_min = (pd.Timestamp.now() - _fetched_at).total_seconds() / 60
                _age_color = TRAFFIC_GREEN if _age_min < 60 else (TRAFFIC_YELLOW if _age_min < 240 else TRAFFIC_RED)
                _age_label = (f'{int(_age_min)} ???? if _age_min < 60
                              else f'{_age_min/60:.1f} 撠???)
                _end_str = _df_end_date.strftime('%Y-%m-%d') if _df_end_date is not None else '??
                _attrs = (df2.attrs or {}) if (df2 is not None and hasattr(df2, 'attrs')) else {}
                _ps = str(_attrs.get('price_src', 'unknown'))
                _is = str(_attrs.get('inst_src', 'unknown'))
                _ms = str(_attrs.get('margin_src', 'unknown'))
                _PRICE_LABEL = {
                    'yahoo_adj': '? Yahoo??', 'finmind_sdk': '?? FinMind??(??)',
                    'finmind_raw': '?? FinMind HTTP(??)', 'yahoo_fallback': '?? Yahoo?(??)',
                    'unknown': '漎??芰',
                }
                _INST_LABEL = {
                    'finmind_sdk': '? FinMind', 'finmind_raw': '?? FinMind HTTP(??)',
                    'twse': '?? TWSE??', 'tpex': '?? TPEX??',
                    'missing': '? 蝻箏仃', 'unknown': '漎??芰',
                }
                _MARGIN_LABEL = {
                    'finmind_sdk': '? FinMind', 'missing': '? 蝻箏仃', 'unknown': '漎??芰',
                }
                # v18.201 D2嚗inMind 敺 update + ???? hover tooltip
                def _fm_tooltip(_key: str, _label: str) -> str:
                    _lu = str(_attrs.get(f'{_key}_last_update', '') or '').strip()
                    _fa = str(_attrs.get(f'{_key}_fetched_at', '') or '').strip()
                    _parts = [_label.upper()]
                    if _lu:
                        _parts.append(f'敺 update {_lu}')
                    if _fa:
                        _parts.append(f'????{_fa}')
                    if len(_parts) == 1:
                        return ''
                    return ' 嚚?'.join(_parts)
                _tip_p = _fm_tooltip('price', 'K 蝺?)
                _tip_i = _fm_tooltip('inst', '蝐Ⅳ')
                _tip_m = _fm_tooltip('margin', '??')
                _ps_html = (f'<b style="color:#c9d1d9;" title="{_tip_p}">{_PRICE_LABEL.get(_ps, _ps)}</b>'
                            if _tip_p else f'<b style="color:#c9d1d9;">{_PRICE_LABEL.get(_ps, _ps)}</b>')
                _is_html = (f'<b style="color:#c9d1d9;" title="{_tip_i}">{_INST_LABEL.get(_is, _is)}</b>'
                            if _tip_i else f'<b style="color:#c9d1d9;">{_INST_LABEL.get(_is, _is)}</b>')
                _ms_html = (f'<b style="color:#c9d1d9;" title="{_tip_m}">{_MARGIN_LABEL.get(_ms, _ms)}</b>'
                            if _tip_m else f'<b style="color:#c9d1d9;">{_MARGIN_LABEL.get(_ms, _ms)}</b>')

                # v18.202 E2嚗瓷?曹?畾菔??? chip嚗?? / 摮?瓷??/ 摮?瓷??extra嚗?
                # rev2 / qtr2 / qtr_extra2 ??.attrs ??data_loader 撖怠嚗? @st.cache_data
                # pickle 靽?嚗pp.py wrapper ?芾???df嚗one/empty ??missing??
                def _fin_attrs(_df, _key):
                    _a = (_df.attrs or {}) if (_df is not None and hasattr(_df, 'attrs')) else {}
                    _src = str(_a.get(f'{_key}_src', '') or '')
                    if (_df is None) or (hasattr(_df, 'empty') and _df.empty):
                        _src = 'missing'
                    elif not _src:
                        _src = 'unknown'
                    return _src, str(_a.get(f'{_key}_fetched_at', '') or '')
                _rev_src, _rev_fa = _fin_attrs(rev2, 'rev')
                _qtr_src, _qtr_fa = _fin_attrs(qtr2, 'qtr')
                _qe_src, _qe_fa = _fin_attrs(qtr_extra2, 'qtr_extra')
                _REVENUE_LABEL = {
                    'finmind': '? FinMind', 'mops': '?? MOPS(?)',
                    'missing': '? 蝻箏仃', 'unknown': '漎??芰',
                }
                _QTR_LABEL = {
                    'finmind_rest': '? FinMind', 'finmind_sdk': '?? FinMind SDK(?)',
                    'yfinance': '?? yfinance(?)', 'missing': '? 蝻箏仃', 'unknown': '漎??芰',
                }
                _QTR_EXTRA_LABEL = {
                    'finmind': '? FinMind', 'finmind_mops': '?? FinMind+MOPS鋆?,
                    'missing': '? 蝻箏仃', 'unknown': '漎??芰',
                }
                def _fin_chip(_src, _fa, _label_map, _label):
                    _parts = [_label.upper()]
                    if _src and _src not in ('unknown', 'missing'):
                        _parts.append(f'皞?{_src}')
                    if _fa:
                        _parts.append(f'????{_fa}')
                    _tip = ' 嚚?'.join(_parts) if len(_parts) > 1 else ''
                    _txt = _label_map.get(_src, _src)
                    if _tip:
                        return f'<b style="color:#c9d1d9;" title="{_tip}">{_txt}</b>'
                    return f'<b style="color:#c9d1d9;">{_txt}</b>'
                _rev_html = _fin_chip(_rev_src, _rev_fa, _REVENUE_LABEL, '????)
                _qtr_html = _fin_chip(_qtr_src, _qtr_fa, _QTR_LABEL, '摮?瓷??)
                _qe_html = _fin_chip(_qe_src, _qe_fa, _QTR_EXTRA_LABEL, '摮?瓷?庸xtra')
                st.markdown(
                    f'<div style="background:#0d1117;border-left:4px solid {_age_color};'
                    f'border-radius:4px;padding:6px 12px;margin-bottom:6px;font-size:11px;color:#8b949e;">'
                    f'?? <b>鞈??圈悅摨?/b>?'
                    f'?? K蝺甇ｇ?<b style="color:#c9d1d9;">{_end_str}</b>?'
                    f'?? ??嚗?b style="color:#c9d1d9;">{_fetched_at.strftime("%H:%M:%S")}</b>?'
                    f'?梧? <span style="color:{_age_color};font-weight:700;">{_age_label}</span>?'
                    f'? K蝺?{_ps_html}?'
                    f'? 蝐Ⅳ嚗_is_html}?'
                    f'? ??嚗_ms_html}'
                    f'<br/>'
                    f'?? ???塚?{_rev_html}?'
                    f'?? 摮?瓷?梧?{_qtr_html}?'
                    f'?? 摮?瓷?庸xtra嚗_qe_html}'
                    f'</div>', unsafe_allow_html=True)
                _degraded = (
                    _ps in ('finmind_sdk', 'finmind_raw', 'yahoo_fallback')
                    or _is in ('finmind_raw', 'twse', 'tpex', 'missing')
                    or _ms == 'missing'
                )
                # v18.202 E2嚗瓷?曹?畾菟?蝝?蝝霅衣內
                _fin_degraded = (
                    _rev_src in ('mops', 'missing')
                    or _qtr_src in ('finmind_sdk', 'yfinance', 'missing')
                    or _qe_src in ('finmind_mops', 'missing')
                )
                if _degraded:
                    st.caption(
                        '?? 銝餉???皞仃?歇??嚗?銵?璅?/ 蝐Ⅳ / ???詨澆?質?甇?虜??銝?嚗?
                        '撱箄降????? 撘瑕?? ?岫銝餅???
                    )
                if _fin_degraded:
                    st.caption(
                        '?? 鞎∪鞈?嚗?? / 摮?瓷?梧??典?韏啣??湔??撩憭梧?EPS / ? / ??鞎 '
                        '?詨澆?質?銝餅??交?撌桃嚗over chip ??????????
                    )
        with _fresh_cols[1]:
            if st.button('?? 撘瑕??', key='t2_force_refresh',
                         help='皜???@st.cache_data 敹怠? + 皜?session 畾??潘?靽?銝活頛???啗???):
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                for _k_pop in ('t2_data',
                               f'_exit_news_titles_{sid2}',
                               f'_last_rev_{sid2}',
                               f'_last_qtr_{sid2}'):
                    st.session_state.pop(_k_pop, None)
                st.rerun()
        if _rev2_cached or _qtr2_cached:
            _stale_parts = []
            if _rev2_cached:
                _stale_parts.append('????)
            if _qtr2_cached:
                _stale_parts.append('摮?瓷??)
            st.markdown(
                f'<div style="background:#3a2814;border-left:4px solid {TRAFFIC_YELLOW};'
                f'border-radius:4px;padding:8px 12px;margin-bottom:8px;font-size:12px;color:#ffd33d;">'
                f'?? <b>{"嚗?.join(_stale_parts)} ?祆活??憭望?嚗?＊蝷箔?甈⊥?????/b>'
                f'????銝??撘瑕????岫'
                f'</div>', unsafe_allow_html=True)

        # ?? v18.204 I4嚗 ??蝮賜? regime ?臬?嚗?蝮賜? Tab mkt_info嚗楊 Tab 閮?嚗??
        try:
            from macro_stock_link import render_macro_stock_backdrop
            render_macro_stock_backdrop(st.session_state)
        except Exception as _e_msl:
            print(f'[macro_stock_link] {type(_e_msl).__name__}: {_e_msl}')

        # ?? v18.207 I5嚗 ??ETF ?? / 蝯?瘥? 頝?Tab ???banner ??
        try:
            from portfolio_linkage import render_stock_portfolio_membership
            render_stock_portfolio_membership(st.session_state, sid2, name2)
        except Exception as _e_pfl:
            print(f'[portfolio_linkage] {type(_e_pfl).__name__}: {_e_pfl}')

        # ?? ?單??寞 + 頞典?銵冽 ????????????????????????????????
        if df2 is not None and not df2.empty and len(df2) >= 20:
            _p_now   = float(df2['close'].iloc[-1])
            _p_prev  = float(df2['close'].iloc[-2]) if len(df2) >= 2 else _p_now
            _p_chg   = round((_p_now - _p_prev) / _p_prev * 100, 2) if _p_prev else 0
            _ma20_v  = float(df2['close'].rolling(20).mean().iloc[-1])
            _ma60_v  = float(df2['close'].rolling(60).mean().iloc[-1]) if len(df2) >= 60 else None
            _ma120_v = float(df2['close'].rolling(120).mean().iloc[-1]) if len(df2) >= 120 else None
            # 頞典??
            _above_ma20  = _p_now > _ma20_v
            _above_ma60  = (_p_now > _ma60_v) if _ma60_v else None
            _above_ma120 = (_p_now > _ma120_v) if _ma120_v else None
            _trend_score = sum([_above_ma20,
                                _above_ma60  if _above_ma60  is not None else False,
                                _above_ma120 if _above_ma120 is not None else False])
            _trend_label = {3: '? 撘瑕憭', 2: '? 銝剜批?憭?, 1: '? 撘勗', 0: '? 蝛粹???}[_trend_score]
            _chg_color   = TRAFFIC_GREEN if _p_chg >= 0 else TRAFFIC_RED
            _chg_arrow   = '?? if _p_chg >= 0 else '??
            st.markdown(f'''<div style="background:#0d1117;border:2px solid #21262d;border-radius:12px;
padding:14px 18px;margin-bottom:12px;">
<div style="font-size:22px;font-weight:900;color:#e6edf3;margin-bottom:8px;">
  ?? {name2}嚗sid2}嚗?
  <span style="font-size:14px;color:#8b949e;margin-left:8px;">?單?頞典蝮質汗</span>
</div>
<div style="display:flex;gap:24px;flex-wrap:wrap;align-items:center;">
  <div><span style="font-size:28px;font-weight:900;color:#e6edf3;">{_p_now:.2f}</span>
       <span style="font-size:16px;color:{_chg_color};margin-left:6px;">{_chg_arrow} {abs(_p_chg):.2f}%</span></div>
  <div style="font-size:13px;color:#8b949e;line-height:2;">
    MA20嚗?b style="color:{TRAFFIC_GREEN if _above_ma20 else TRAFFIC_RED}">{_ma20_v:.2f}</b>
    {'?? if _above_ma20 else '??}&nbsp;&nbsp;
    {'MA60嚗?b style="color:' + (TRAFFIC_GREEN if _above_ma60 else TRAFFIC_RED) + '">' + f'{_ma60_v:.2f}</b> ' + ("?? if _above_ma60 else "??) + "&nbsp;&nbsp;" if _ma60_v else ""}
    {'MA120嚗?b style="color:' + (TRAFFIC_GREEN if _above_ma120 else TRAFFIC_RED) + '">' + f'{_ma120_v:.2f}</b> ' + ("?? if _above_ma120 else "??) if _ma120_v else ""}
  </div>
  <div style="font-size:18px;font-weight:700;">{_trend_label}</div>
</div></div>''', unsafe_allow_html=True)

        st.markdown("""<div style="margin:20px 0 8px;padding:8px 16px;background:linear-gradient(90deg,#f0883e18,#0d1117);border-left:4px solid #f0883e;border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:#f0883e;">? 撱箄降?寞 & ?脣?游???/span><span style="font-size:11px;color:#8b949e;margin-left:8px;">??? 繚 憸典瘥?繚 ?脣璇辣 繚 ??閮?</span></div>""", unsafe_allow_html=True)
        # ?? 0. ??? + ?舀?憯? ????????????????????????????????
        st.markdown('---')
        st.markdown('#### ? ???撱箄降 + 餈??舀?憯?')
        _sp_c1, _sp_c2, _sp_c3, _sp_c4 = st.columns(4)
        _cur_p  = float(df2['close'].iloc[-1]) if df2 is not None and not df2.empty else 0
        _hi20_p = float(df2['high'].tail(20).max()) if df2 is not None and len(df2) >= 5 else 0
        _lo20_p = float(df2['low'].tail(20).min())  if df2 is not None and len(df2) >= 5 else 0
        _tp1_p  = round(_cur_p * 1.05, 2)
        _tp2_p  = round(_cur_p * 1.10, 2)
        _sl_p   = round(_cur_p * 0.92, 2)
        _rr_p   = round((_tp1_p - _cur_p) / max(_cur_p - _sl_p, 0.01), 2)
        with _sp_c1:
            st.markdown(kpi('??格?1 (+5%)', f'{_tp1_p}', '?剔??鋡?, TRAFFIC_GREEN, '#0d2818'), unsafe_allow_html=True)
        with _sp_c2:
            st.markdown(kpi('??格?2 (+10%)', f'{_tp2_p}', '瘜Ｘ挾?格?', '#58a6ff', '#0d1f3c'), unsafe_allow_html=True)
        with _sp_c3:
            st.markdown(kpi('撱箄降?? (-8%)', f'{_sl_p}', '頝隤?', TRAFFIC_RED, '#2a0d0d'), unsafe_allow_html=True)
        with _sp_c4:
            st.markdown(kpi('?瘥?, f'{_rr_p}x', '??.5 頛???, '#ffd700', '#1a1000'), unsafe_allow_html=True)
        _sp_c5, _sp_c6 = st.columns(2)
        _dist_hi = round((_hi20_p/_cur_p-1)*100, 1) if _cur_p > 0 else 0
        _dist_lo = round((1-_lo20_p/_cur_p)*100, 1) if _cur_p > 0 else 0
        # ?? 憭折?蝝 ?脣?寡?蝞???????????????????????????????
        _entry_half = None
        _abs_sl     = None
        if df2 is not None and not df2.empty and len(df2) >= 5:
            # ?曇?20?交?憭折???K
            _red_k = df2[(df2['close'] > df2['open']) if 'open' in df2.columns
                         else df2['close'] > df2['close'].shift(1)].tail(20)
            if 'volume' in _red_k.columns and not _red_k.empty:
                _big_red = _red_k.nlargest(1, 'volume').iloc[0]
                _rk_high = float(_big_red.get('high', _big_red['close']))
                _rk_low  = float(_big_red.get('low',  _big_red['close']) )
                _entry_half = round((_rk_high + _rk_low) / 2, 2)  # 1/2 ?脣??
                _abs_sl     = round(_rk_low * 0.995, 2)             # 蝝雿?-0.5%

        _sp_c5b, _sp_c6b, _sp_c7b = st.columns(3)
        with _sp_c5b:
            if _entry_half:
                st.markdown(kpi('憭折?蝝 1/2 ?脣', f'{_entry_half:.2f}',
                                '?勗振瘜?憸券鞎琿?', '#58a6ff', '#1a2744'), unsafe_allow_html=True)
            else:
                st.markdown(kpi('憭折?蝝 1/2', '閮?銝?, '', '#484f58', '#0d1117'), unsafe_allow_html=True)
        with _sp_c6b:
            if _abs_sl:
                _bias_sl = round((_cur_p - _abs_sl) / _cur_p * 100, 1) if _cur_p else 0
                _sl_color = TRAFFIC_RED if _bias_sl < 5 else TRAFFIC_YELLOW
                st.markdown(kpi('蝯???蝺?, f'{_abs_sl:.2f}',
                                f'蝝雿?嚗?{_bias_sl:.1f}%嚗?, _sl_color, '#2a0d0d'), unsafe_allow_html=True)
            else:
                st.markdown(kpi('蝯???蝺?, _sl_p.__str__(), '頝?喳??, TRAFFIC_RED, '#2a0d0d'), unsafe_allow_html=True)
        with _sp_c7b:
            _rr2 = round((_tp1_p - _cur_p) / max(_cur_p - (_abs_sl or _sl_p), 0.01), 2) if _cur_p else 0
            _rr_color = TRAFFIC_GREEN if _rr2 >= 1.5 else (TRAFFIC_YELLOW if _rr2 >= 1 else TRAFFIC_RED)
            st.markdown(kpi('撖阡??瘥?, f'{_rr2}x', '??.5 ?舀?雿?, _rr_color, '#0d1117'), unsafe_allow_html=True)

        with _sp_c5:
            st.markdown(kpi('餈?0?亙???, f'{_hi20_p:.2f}', f'頝??+{_dist_hi}%', TRAFFIC_RED, '#2a0d0d'), unsafe_allow_html=True)
        with _sp_c6:
            st.markdown(kpi('餈?0?交??, f'{_lo20_p:.2f}', f'頝??-{_dist_lo}%', TRAFFIC_GREEN, '#0d2818'), unsafe_allow_html=True)

        # ?? ?脣?渲???憭??葦?寞??游?嚗???????????????????????
        st.markdown('---')

        # ?? ?????炎??+ ??寧?撘?????????????????????????
        st.markdown('---')
        st.markdown('#### ?? ??????敹?瑼Ｘ + ??寧?撘?)

        _mc_cols = st.columns([3, 2])

        with _mc_cols[0]:
            st.markdown('<div style="background:#0a1628;border:1px solid #1f6feb;border-radius:10px;padding:12px;">', unsafe_allow_html=True)
            st.markdown('**?? SOP ?脣撘瑕瑼Ｘ銵剁?4??券??＊蝷箏遣霅堆?**')
            _wr_reg_chk = st.session_state.get('mkt_info', {}).get('regime','neutral')
            _price_chk  = float(df2['close'].iloc[-1]) if df2 is not None and not df2.empty else 0
            _open5_chk  = float(df2['close'].iloc[-6]) if df2 is not None and len(df2)>=6 else _price_chk
            _surge_chk  = round((_price_chk - _open5_chk) / max(_open5_chk,1) * 100, 1)
            _stop_chk   = round(_price_chk - 1.5 * (_atr2_val if '_atr2_val' in dir() else _price_chk*0.07), 2)  # noqa: F821
            _q1 = st.checkbox(
                f'??蝣箄??征?剜撅嚗??{_wr_reg_chk}嚗?,
                value=_wr_reg_chk != 'bear', key=f't2_q1_{sid2}',
                disabled=_wr_reg_chk == 'bear'
            )
            _q2 = st.checkbox(
                f'??蝣箄??芾蕭擃???%嚗?5?交撞撟?{_surge_chk:+.1f}%嚗?,
                value=abs(_surge_chk) <= 5, key=f't2_q2_{sid2}',
                disabled=abs(_surge_chk) > 10
            )
            _q3 = st.checkbox(
                f'??蝣箄????對?頝 {_stop_chk} ?璇辣?箏嚗?,
                key=f't2_q3_{sid2}'
            )
            _all_checked = _q1 and _q2 and _q3
            if _all_checked:
                st.success('??敹???憟踝??臭誑蝜潛?閰摯??')
            else:
                st.warning('?? 撠???芰Ⅱ隤?撱箄降????踹?????雿?)
            st.markdown('</div>', unsafe_allow_html=True)

        with _mc_cols[1]:
            st.markdown(f'<div style="background:#0a1628;border:1px solid {TRAFFIC_GREEN};border-radius:10px;padding:12px;">', unsafe_allow_html=True)
            st.markdown('**?? ??寧?撘???券蝚血?嚗?*')
            _wr_mkt2 = st.session_state.get('mkt_info', {})
            _wr_reg2 = _wr_mkt2.get('regime','neutral') if _wr_mkt2 else 'neutral'
            _wr_margin2 = st.session_state.get('cl_data',{}).get('margin', 0) or 0
            _win_conds = [
                ('?? 憭抒憭??',  _wr_reg2 == 'bull'),
                ('? ??摰(<2500??', _wr_margin2 < 2500),
                ('? ??亙熒摨色75', health2 >= 75 if df2 is not None else False),
                ('?? ??57?眼?',   '?眼' not in str(st.session_state.get('t2_data',{}).get('val',''))),
                ('??撌脰身??暺?,     _q3),
            ]
            _win_count = sum(1 for _, v in _win_conds if v)
            for _wn, _wv in _win_conds:
                _wc = TRAFFIC_GREEN if _wv else TRAFFIC_RED
                _wi = '?? if _wv else '??
                st.markdown(f'<div style="font-size:12px;color:{_wc};padding:2px 0;">{_wi} {_wn}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="margin-top:8px;font-size:13px;font-weight:700;color:{TRAFFIC_GREEN if _win_count>=4 else TRAFFIC_RED};">'
                       f'{"?? 蝚血? " + str(_win_count) + "/5嚗隞亥??" if _win_count>=4 else "???泵??" + str(_win_count) + "/5嚗遣霅啁?敺?}'
                       f'</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # 隞蝳迫??皜
        st.markdown('#### ? 隞蝳迫????嚗?隞颱?銝??隞予?怠?嚗?)
        _ban_items = []
        _wr_mkt3 = st.session_state.get('mkt_info', {})
        _wr_price = float(df2['close'].iloc[-1]) if df2 is not None and not df2.empty else 0
        _wr_open  = float(df2['close'].iloc[-5]) if df2 is not None and len(df2)>=5 else _wr_price
        _today_surge = round((_wr_price - _wr_open) / max(_wr_open,1) * 100, 1) if _wr_open else 0
        if abs(_today_surge) > 4:
            _ban_items.append(f'?? ?餈??交撞撟?{_today_surge:+.1f}% 頞?4%嚗蕭擃◢?迎?')
        _ml = st.session_state.get('monthly_loss_pct', 0)
        if _ml < -5:
            _ban_items.append(f'?? ?祆?撌脰??{abs(_ml):.1f}%嚗?蝺?雿◢?芯???')
        if _wr_margin2 > 3400:
            _ban_items.append(f'? ?? {_wr_margin2:.0f}??璆萄漲?嚗?嗉蕭擃?嚗?敺?')
        if _wr_reg2 == 'bear':
            _ban_items.append('? 憭抒蝛粹?澆?嚗?甇Ｗ?憭?')

        if _ban_items:
            for _bi in _ban_items:
                st.markdown(f'<div style="background:#2a0d0d;border-left:3px solid {TRAFFIC_RED};border-radius:0 6px 6px 0;padding:7px 12px;margin:3px 0;font-size:12px;color:{TRAFFIC_RED};">'
                           f'??{_bi}</div>', unsafe_allow_html=True)
        else:
            st.success('??隞?∠?甇Ｘ?雿?瘜??臭誑甇?虜閰摯')

        st.markdown('---')
        st.markdown('#### ? 隞暻潭??眺嚗?暻潭??都嚗?)
        st.markdown(
            '<div style="background:#0a1628;border-left:3px solid #58a6ff;padding:8px 12px;'            'border-radius:0 6px 6px 0;margin-bottom:8px;font-size:12px;color:#c9d1d9;">'
            '? 蝟餌絞?芸?撟思?瑼Ｘ<b>憭?蝑?脣?湔?隞?/b>嚗泵??憭?隞嗉??舫???
            '<br>? <b>?脣閮?</b>嚗?璇辣?箇隞?”?臭誑?鞎琿?
            '<br>? <b>?箏閮?</b>嚗?璇辣?箇隞?”閬鞈???蝣?
            '<br>? <b>?格???/b>嚗?閮隞亦?拍??格? | ?? <b>??</b>嚗??圈ㄐ閬?鞈??
            '</div>', unsafe_allow_html=True)
        if df2 is not None and not df2.empty:
            _p2    = float(df2['close'].iloc[-1])
            _ma5   = safe_ma(df2, 5)
            _ma20  = safe_ma(df2, 20)
            _ma60  = safe_ma(df2, 60)
            _ma240 = safe_ma(df2, 240)

            # 頞典??
            _bull_align  = _p2 > _ma20 > _ma60   # 憭??
            _bear_align  = _p2 < _ma20 < _ma60   # 蝛粹??
            _bias_i      = round((_p2 - _ma240) / _ma240 * 100, 1) if _ma240 else 0
            _bias_20_i   = round((_p2 - _ma20) / _ma20 * 100, 1)   if _ma20  else 0

            # 撣?撣嗉???
            _bb_upper    = (bb2.get('upper', 0) if isinstance(bb2, dict) else 0) or float('inf')
            _bb_ma       = (bb2.get('ma', 0)    if isinstance(bb2, dict) else 0)
            _bb_near_up  = bool(bb2) and _p2 >= _bb_upper * 0.97
            _bb_drop_out = bool(bb2) and _p2 < _bb_upper * 0.95 and _p2 > _bb_ma

            # KD 閮?
            _kd_gold = k2 and d2 and k2 > d2  # 暺?鈭文??孵?
            _kd_dead = k2 and d2 and k2 < d2 and k2 > 70  # 擃?甇颱滿鈭文?

            # VCP 閮?
            _vcp_ok = bool(vcp2 and isinstance(vcp2, dict) and vcp2.get('contracting'))

            # ?格??對??⊥ㄝ銝瘥?撠迂瘜?
            _hi20_i = float(df2['high'].tail(20).max())
            _lo20_i = float(df2['low'].tail(20).min())
            _range20 = _hi20_i - _lo20_i
            _target1 = round(_p2 + _range20, 2)  # ?郊?格?嚗??+ 20?仿?撟?

            # ?? ? ?箏暺???蝷綽?銝雁嚗蝛箸??+ ?銵?+ 蝐Ⅳ嚗?????????
            try:
                _ex_tech = compute_tech_bearish(df2, k=k2, d=d2)
                _ex_chip = analyze_20d_chips_from_df(df2)
                _ex_chip_sig = _ex_chip.get('signal', '') if isinstance(_ex_chip, dict) else ''
                # ?啗?璅?嚗 session ?批翰???踹?瘥活 rerun ?? RSS嚗?
                _ex_news_key = f'_exit_news_titles_{sid2}'
                _ex_titles = st.session_state.get(_ex_news_key)
                if _ex_titles is None:
                    _ex_raw = _fetch_stock_news(sid2, name2, 8, recency='3m')
                    _ex_titles = [n.get('title', '') for n in (_ex_raw or []) if n.get('title')]
                    st.session_state[_ex_news_key] = _ex_titles
                _ex_news = (judge_news_sentiment_cached(gemini_call, sid2, name2, _ex_titles)
                            if _ex_titles else None)
                _ex = evaluate_exit_signals(_ex_tech, _ex_chip_sig, _ex_news)
                _ex_dim_html = ''.join(
                    f'<span style="display:inline-block;margin:2px 6px 2px 0;padding:2px 8px;border-radius:10px;'
                    f'font-size:11px;background:{"#3a1414" if _hit else "#161b22"};'
                    f'color:{"#ff7b72" if _hit else "#8b949e"};border:1px solid '
                    f'{TRAFFIC_RED if _hit else "#30363d"};">{"??" if _hit else "??} {_nm}嚗_desc}</span>'
                    for _nm, _hit, _desc in _ex['dims'])
                st.markdown(
                    f'<div style="margin:6px 0 12px;padding:10px 14px;border-radius:8px;'
                    f'background:linear-gradient(90deg,{_ex["color"]}1f,#0d1117);'
                    f'border-left:5px solid {_ex["color"]};">'
                    f'<div style="font-size:15px;font-weight:900;color:{_ex["color"]};">'
                    f'? ?箏暺???蝷???{_ex["headline"]}</div>'
                    f'<div style="margin-top:6px;">{_ex_dim_html}</div>'
                    f'<div style="font-size:10px;color:{TRAFFIC_NEUTRAL};margin-top:4px;">'
                    f'銝雁閮?嚗蝛箸? Gemini ???方?嚗?h 敹怠?嚗?銝?箏?蝑閰喟敦閮?</div>'
                    f'</div>', unsafe_allow_html=True)
            except Exception as _ex_err:
                st.caption(f'???箏暺???蝷箸銝?剁?{_ex_err}')

            _sig_cols = st.columns(3)

            with _sig_cols[0]:
                st.markdown('<div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:10px;">', unsafe_allow_html=True)
                st.markdown('**?? ?脣閮?**')
                _entry = []
                if _bull_align:
                    _entry.append('??憭??嚗>??摮?????勗振瘜??舫脣?孵?')
                if _vcp_ok:
                    _entry.append('??VCP瘜Ｗ??嗥葬 ??蝑3嚗撠??湛?撱箏???0-50%')
                if k2 and k2 < 30:
                    _entry.append(f'??KD雿? K={k2:.0f} ??蝑1嚗??券脣?')
                if rsi2 and rsi2 < 30:
                    _entry.append(f'??RSI頞都 {rsi2:.0f} ????璈?')
                if _bias_i < -20:
                    _entry.append(f'??撟渡?鞎???{_bias_i:+.0f}% ??蝑1嚗椰?游?撅?')
                # RS ?詨?撘瑕漲
                try:
                    _rs_val  = calc_rs_score(df2)
                    _rs_up   = rs_slope(df2)
                    _rs_color= TRAFFIC_GREEN if _rs_val >= 75 else (TRAFFIC_YELLOW if _rs_val >= 50 else TRAFFIC_RED)
                    _rs_trend= '?撥?? if _rs_up else ('?摹?? if _rs_up is False else '')
                    _entry.append(f'<span style="color:{_rs_color}">?? RS?詨?撘瑕漲 {_rs_val:.0f}??{_rs_trend}</span>')
                except Exception:
                    pass
                if not _entry:
                    _entry.append('???怎?Ⅱ?脣閮?')
                for _e in _entry:
                    st.markdown(f'<div style="font-size:12px;color:#c9d1d9;padding:2px 0;">{_e}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with _sig_cols[1]:
                st.markdown('<div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:10px;">', unsafe_allow_html=True)
                st.markdown('**?? 皜Ⅳ/?箏閮?**')
                _exit = []
                if _bear_align:
                    _exit.append('? 蝛粹?? ???勗振瘜?蝳迫??嚗?箸?')
                if _kd_dead:
                    _exit.append(f'?? KD擃?甇餃? K={k2:.0f} ??蝑3嚗?憪?蝣?)
                if _bb_drop_out:
                    _exit.append('?? ?恍撣?銝? ??蝑3嚗?蝣?0%')
                if _bias_20_i > 15:
                    _exit.append(f'?? ??銋 {_bias_20_i:+.0f}% ???嚗??拚??)
                if _bias_i > 20:
                    _exit.append(f'?? 撟渡?銋 {_bias_i:+.0f}% ??蝑1嚗??孵??)
                if _p2 < _ma5:
                    _exit.append(f'?? 頝5MA({_ma5:.1f}) ????嚗蝺???)
                # ?專ACD 霅衣內嚗?2/26/9 EMA on weekly bars
                try:
                    if df2 is not None and len(df2) >= 30:
                        _wdf = df2.copy()
                        _wdf.index = range(len(_wdf))
                        # 餈?0?仕蝺???密嚗?5?孵?銝嚗?
                        _wclose = [float(_wdf['close'].iloc[min(i+4, len(_wdf)-1)])
                                   for i in range(0, min(30, len(_wdf)), 5)]
                        if len(_wclose) >= 6:
                            _we12 = pd.Series(_wclose).ewm(span=3,adjust=False).mean()
                            _we26 = pd.Series(_wclose).ewm(span=5,adjust=False).mean()
                            _wmacd= _we12 - _we26
                            _whist= (_wmacd - _wmacd.ewm(span=3,adjust=False).mean()).tolist()
                            # ?專ACD蝝蝮桃嚗??2?寧葬撠?
                            if len(_whist)>=3 and _whist[-1]>0 and _whist[-1]<_whist[-2]<_whist[-3]:
                                _exit.append('?? ?專ACD蝝??葬 ??銝撞?銵唳?嚗???蝣?)
                            elif len(_whist)>=2 and _whist[-2]>0 and _whist[-1]<=0:
                                _exit.append('? ?專ACD蝧餉? ??銝剔?頞典頧摹嚗皜???)
                except Exception:
                    pass
                if not _exit:
                    _exit.append('???怎?Ⅱ?箏閮?')
                for _ex in _exit:
                    st.markdown(f'<div style="font-size:12px;color:#c9d1d9;padding:2px 0;">{_ex}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with _sig_cols[2]:
                st.markdown('<div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:10px;">', unsafe_allow_html=True)
                st.markdown('**? ?格? + ??**')
                st.markdown(f'<div style="font-size:12px;color:#c9d1d9;padding:2px 0;">?? ?曉嚗?b>{_p2:.2f}</b></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:12px;color:{TRAFFIC_GREEN};padding:2px 0;">? ?郊?格?嚗??? 銝瘥?撠迂嚗?<b>{_target1:.2f}</b></div>', unsafe_allow_html=True)
                _sl_hard = round(_p2 * 0.93, 2)
                _sl_ma20 = round(_ma20 * 0.99, 2)
                _dist_hard = round((_p2 - _sl_hard) / _p2 * 100, 1) if _p2 else 0
                _dist_ma20 = round((_p2 - _sl_ma20) / _p2 * 100, 1) if _p2 else 0
                _dist_ma5  = round((_p2 - _ma5) / _p2 * 100, 1) if _p2 and _ma5 else 0
                st.markdown(f'<div style="font-size:12px;color:{TRAFFIC_RED};padding:2px 0;">?? 蝖砍???-7%)嚗?b>{_sl_hard:.2f}</b> <span style="color:#484f58;">嚗?撌徒_dist_hard:.1f}%嚗?/span></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:12px;color:{TRAFFIC_YELLOW};padding:2px 0;">?? ????嚗?b>{_sl_ma20:.2f}</b> <span style="color:#484f58;">嚗?撌徒_dist_ma20:.1f}%嚗?/span></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:12px;color:#58a6ff;padding:2px 0;">?? 5MA?嚗?b>{_ma5:.2f}</b> <span style="color:#484f58;">嚗?撌徒_dist_ma5:.1f}%嚗?/span></div>', unsafe_allow_html=True)
                # ?Ⅳ暺?
                if _bull_align and vcp2 and not _vcp_ok:
                    _add_pt = round(_hi20_i * 1.01, 2)
                    st.markdown(f'<div style="font-size:12px;color:#58a6ff;padding:2px 0;">???Ⅳ暺?蝑3 蝒瘜?嚗?{_add_pt:.2f}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            # ?? ??嫣? K 蝺?嚗?????/?舀?憯??湔?怠 K 蝺?嚗?????
            try:
                from plotly.subplots import make_subplots
                _kdf = df2.tail(180).copy()
                _fig_kl = make_subplots(
                    rows=2, cols=1, shared_xaxes=True,
                    row_heights=[0.78, 0.22], vertical_spacing=0.03,
                )
                _open_s = _kdf['open'] if 'open' in _kdf.columns else _kdf['close']
                _fig_kl.add_trace(go.Candlestick(
                    x=_kdf.index, open=_open_s,
                    high=_kdf['high'], low=_kdf['low'], close=_kdf['close'],
                    increasing_line_color='#da3633', decreasing_line_color='#2ea043',
                    name='K蝺?, showlegend=False,
                ), row=1, col=1)
                _ma20s = _kdf['MA20'] if 'MA20' in _kdf.columns else df2['close'].rolling(20).mean().tail(len(_kdf))
                _ma100s = _kdf['MA100'] if 'MA100' in _kdf.columns else df2['close'].rolling(100).mean().tail(len(_kdf))
                _fig_kl.add_trace(go.Scatter(x=_kdf.index, y=_ma20s,
                    line=dict(color='#FF69B4', width=1.4), name='MA20'), row=1, col=1)
                _fig_kl.add_trace(go.Scatter(x=_kdf.index, y=_ma100s,
                    line=dict(color='#00CED1', width=1.4), name='MA100'), row=1, col=1)
                if 'volume' in _kdf.columns:
                    _vc = ['#da3633' if c >= o else '#2ea043'
                           for c, o in zip(_kdf['close'], _open_s)]
                    _fig_kl.add_trace(go.Bar(x=_kdf.index, y=_kdf['volume'],
                        marker_color=_vc, name='??, showlegend=False), row=2, col=1)
                # 9 璇??萄雿偌撟喟?
                _add_pt_v = locals().get('_add_pt')
                _hlines = [
                    (_tp2_p,   '#58a6ff', 'dash',    f'?2 +10% {_tp2_p:.2f}'),
                    (_tp1_p,   TRAFFIC_GREEN, 'dash',    f'?1 +5% {_tp1_p:.2f}'),
                    (_hi20_p,  '#f0883e', 'dot',     f'憯? {_hi20_p:.2f}'),
                    (_target1, '#2ea043', 'dashdot', f'?郊?格? {_target1:.2f}'),
                    (_ma5,     '#FFD700', 'solid',   f'5MA {_ma5:.2f}'),
                    (_lo20_p,  '#1f6feb', 'dot',     f'?舀? {_lo20_p:.2f}'),
                    (_sl_ma20, '#8b949e', 'dot',     f'???? {_sl_ma20:.2f}'),
                    (_sl_p,    TRAFFIC_RED, 'dash',    f'?? -8% {_sl_p:.2f}'),
                    (_sl_hard, '#a40e26', 'dashdot', f'蝖砍???-7% {_sl_hard:.2f}'),
                ]
                if _add_pt_v:
                    _hlines.append((_add_pt_v, '#a371f7', 'dashdot', f'?Ⅳ暺?>{_add_pt_v:.2f}'))
                for _y, _c, _ds, _txt in _hlines:
                    if _y and _y > 0:
                        _fig_kl.add_hline(
                            y=_y, line=dict(color=_c, width=1, dash=_ds),
                            annotation_text=_txt, annotation_position='top left',
                            annotation_font=dict(color=_c, size=10),
                            row=1, col=1,
                        )
                _fig_kl.update_layout(
                    title=dict(text=f'{sid2} {name2} K蝺?+ ??嫣?嚗?????/?舀?憯?嚗?,
                               font=dict(size=13)),
                    height=460, margin=dict(l=10, r=10, t=40, b=10),
                    template='plotly_dark', showlegend=True,
                    legend=dict(orientation='h', yanchor='bottom', y=1.02,
                                x=1, xanchor='right', font=dict(size=10)),
                    xaxis_rangeslider_visible=False,
                )
                _fig_kl.update_yaxes(title_text='?寞', row=1, col=1)
                _fig_kl.update_yaxes(title_text='??, row=2, col=1)
                st.plotly_chart(_fig_kl, use_container_width=True,
                                config={'displayModeBar': False})
            except Exception as _kl_err:
                st.caption(f'?? K 蝺鼓鋆賢仃??{_kl_err}')

        else:
            st.info('頛?鞈?敺＊蝷粹脣?渲???)

        # ?? 樴?郎?嚗重?園?樴?蝑?擃?蝝???????????????????
        # cl2 / cx2 ??FinMind ???潘?撠?研??祕瘥?嚗?隞????>0 ??瘀?
        _is_dragon = False
        _dragon_reasons = []
        try:
            _capital = _fetch_share_capital(sid2)  # ?⊥嚗?嚗?
            if _capital > 0:
                if cl2 is not None and cl2 > 0 and cl2 / _capital >= 0.5:
                    _dragon_reasons.append(
                        f'??鞎 {cl2/1e8:.1f}?????{cl2/_capital*100:.0f}% ???芯?3-6???桐???')
                    _is_dragon = True
                if cx2 is not None and cx2 > 0 and cx2 / _capital >= 0.8:
                    _dragon_reasons.append(
                        f'鞈?臬 {cx2/1e8:.1f}?????{cx2/_capital*100:.0f}% ??憭扳撱??末?芯??瘙?')
                    _is_dragon = True
        except Exception:
            pass

        if _is_dragon:
            st.markdown(
                '<div style="background:linear-gradient(135deg,#2a1f00,#3d2d00);'
                'border:2px solid #ffd700;border-radius:10px;padding:12px 16px;margin-bottom:10px;">'
                '<div style="font-size:14px;font-weight:900;color:#ffd700;margin-bottom:6px;">'
                '?? 樴?郎? ??璆萇????璅?</div>' +
                ''.join(f'<div style="font-size:12px;color:#ffe066;padding:2px 0;">??{r}</div>' for r in _dragon_reasons) +
                '<div style="font-size:11px;color:#997a00;margin-top:4px;">'
                '蝑1嚗?閬??隤芯?暻潘?閬?隞?隞暻潦??隤祕????璅?/div>'
                '</div>', unsafe_allow_html=True)

        st.markdown("""<div style="margin:24px 0 8px;padding:8px 16px;background:linear-gradient(90deg,#58a6ff18,#0d1117);border-left:4px solid #58a6ff;border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:#58a6ff;">?? ?銵??</span><span style="font-size:11px;color:#8b949e;margin-left:8px;">?亙熒摨西???繚 VCP瘜Ｗ??嗥葬 繚 K蝺?銵? 繚 ?單???撱箄降</span></div>""", unsafe_allow_html=True)
        # ?? A. ?亙熒摨西?????????????????????????????????????????
        st.markdown('#### ? A. ??亙熒摨西???0~100嚗?)
        st.caption('? ???質店嚗SI >70 ???30 頞都嚚D 暺?鈭文?嚗 ? D嚗?憭香鈭∩漱??蝛綽?'
                   'IBS ??方?函?仿?雿???蝵殷?頞?頞撥嚗???嚗??仿? 繩 餈???嚗?1 ?暸?嚗?)
        if health2 >= 80:
            _ha = f'?亙熒摨?{health2:.0f}???銵撘瑕'
            _hb = '蝣箄?憭抒?孵?敺撱箏???閮剜?蝺???
        elif health2 >= 60:
            _ha = f'?亙熒摨?{health2:.0f}??銝剜批?憭?撠?脣璅?'
            _hb = '蝑?蝒80???暸?蝒??????
        else:
            _ha = f'?亙熒摨?{health2:.0f}???銵?摹嚗歲??
            _hb = '銝?撘瑟?嚗?暹憟賣???
        st.markdown(teacher_conclusion('摰', f'{sid2} ?亙熒摨?{health2:.0f}??, _ha, _hb), unsafe_allow_html=True)
        # 閰?靽∪???牧??
        _score_help = (
            '<div style="background:#0a1628;border-left:3px solid #58a6ff;'
            'padding:8px 12px;border-radius:0 6px 6px 0;margin-bottom:8px;font-size:11px;color:#8b949e;">'
            '?? <b>閰?銝靽?嚗璈?</b>嚗?
            '?亙熒摨?0????甇瑕??蝝?5%嚗?0甈∩葉6-7甈∪?嚗?
            '??蝝敺捱摰??賢敺??撟暹活鞈箏??Ｕ?
            '</div>'
        )

        ha, hb = st.columns([1, 2])
        with ha:
            # ?箸?Ｚ???
            _fund_sc = calc_fundamental_score(qtr2, yearly2, avg_div2)
            # ?銵郎蝷?
            _tech_al = []
            if rsi2 and rsi2 < 30:
                _tech_al.append(('?','RSI??','????',f'RSI={rsi2:.0f}嚗?鞈??賢?敶?))
            elif rsi2 and rsi2 > 70:
                _tech_al.append(('?','RSI頞眺','頞眺瘜冽?',f'RSI={rsi2:.0f}嚗?瑼???))
            if df2 is not None and 'MA5' in df2.columns and 'MA10' in df2.columns and len(df2)>=2:
                _m5,_m10  = float(df2['MA5'].iloc[-1]),  float(df2['MA10'].iloc[-1])
                _m5p,_m10p= float(df2['MA5'].iloc[-2]),  float(df2['MA10'].iloc[-2])
                if _m5<_m10 and _m5p>=_m10p:
                    _tech_al.insert(0,('?','MA5銝忽MA10','??',  '?剖?甇餃?嚗隅?Ｚ?撘?))
                elif _m5>_m10 and _m5p<=_m10p:
                    _tech_al.insert(0,('?','MA5銝忽MA10','?撞','?剖?暺?鈭文?嚗?撘?))
            if vr2 and vr2 < 0.5:
                _tech_al.append(('?','?銝雲','閫撖?,f'??={vr2:.2f}嚗??渲???))
            if k2 and d2:
                if k2<d2 and k2>20:
                    _tech_al.append(('?','KD甇颱滿鈭文?','??',f'K={k2:.0f} D={d2:.0f}'))
                elif k2>d2 and k2<80:
                    _tech_al.append(('?','KD暺?鈭文?','?撞',f'K={k2:.0f} D={d2:.0f}'))
            st.markdown(render_health_score(health2, details2, sid2, _fund_sc, _tech_al), unsafe_allow_html=True)
        with hb:
            # ?剖之?銵?璅??
            ind1, ind2, ind3 = st.columns(3)
            ind4, ind5, ind6 = st.columns(3)
            with ind1:
                rsi_c = TRAFFIC_YELLOW if rsi2 and rsi2>70 else (TRAFFIC_GREEN if rsi2 and rsi2<30 else '#58a6ff')
                rsi_txt = '頞眺??' if rsi2 and rsi2>70 else ('頞都??' if rsi2 and rsi2<30 else '銝剜?)
                st.markdown(kpi('RSI(14)',f'{rsi2}' if rsi2 else '-',rsi_txt,rsi_c,rsi_c),unsafe_allow_html=True)
            with ind2:
                vr_c = TRAFFIC_GREEN if vr2 and vr2>=1.5 else (TRAFFIC_YELLOW if vr2 and vr2>=1.0 else '#484f58')
                vr_txt = '?啣虜?暸?' if vr2 and vr2>=1.5 else ('皞怠??暸?' if vr2 and vr2>=1.0 else '?葬')
                st.markdown(kpi('??(5??',f'{vr2}' if vr2 else '-',vr_txt,vr_c,vr_c),unsafe_allow_html=True)
            with ind3:
                ibs_c = TRAFFIC_GREEN if ibs2 is not None and ibs2<=0.2 else (TRAFFIC_RED if ibs2 is not None and ibs2>=0.8 else '#58a6ff')
                ibs_txt = '?嗡???0%??敶? if ibs2 is not None and ibs2<=0.2 else ('?園???0%?都憯? if ibs2 is not None and ibs2>=0.8 else '銝剜找?蝵?)
                st.markdown(kpi('IBS',f'{ibs2}' if ibs2 is not None else '-',ibs_txt,ibs_c,ibs_c),unsafe_allow_html=True)
            with ind4:
                kd_c = TRAFFIC_GREEN if k2 and d2 and k2>d2 and k2<80 else (TRAFFIC_YELLOW if k2 and d2 and k2>d2 else TRAFFIC_RED)
                kd_txt = '暺?鈭文?' if k2 and d2 and k2>d2 else '甇颱滿鈭文?'
                st.markdown(kpi('KD',f'K={k2}/D={d2}' if k2 else '-',kd_txt,kd_c,kd_c),unsafe_allow_html=True)
            with ind5:
                if df2 is not None and 'MA20' in df2.columns and 'MA100' in df2.columns:
                    p=price2
                    m20=float(df2['MA20'].iloc[-1])
                    m100=float(df2['MA100'].iloc[-1])
                    if p>m20>m100:
                        tr_txt='憭??'
                        tr_c=TRAFFIC_GREEN
                    elif p<m20<m100:
                        tr_txt='蝛粹??'
                        tr_c=TRAFFIC_RED
                    elif p>m100:
                        tr_txt='憭拳?渡?'
                        tr_c=TRAFFIC_YELLOW
                    else:
                        tr_txt='蝛箇拳?渡?'
                        tr_c=TRAFFIC_YELLOW
                    st.markdown(kpi('頞典',tr_txt,f'MA20={m20:.1f}',tr_c,tr_c),unsafe_allow_html=True)
                else:
                    st.markdown(kpi('頞典','-','?﹐A?豢?','#484f58'),unsafe_allow_html=True)
            with ind6:
                if bb2:
                    bw_c=TRAFFIC_GREEN if bb2['bw']<bb2['bw_mean']*0.7 else '#58a6ff'
                    bw_txt='撣嗅祝璆萇葬?? if bb2['bw']<bb2['bw_mean']*0.7 else ('暺?銝?' if bb2['near_upper'] else f'?慮bb2["bw_mean"]:.1f}%')
                    st.markdown(kpi('撣?撣嗅祝',f'{bb2["bw"]:.1f}%',bw_txt,bw_c,bw_c),unsafe_allow_html=True)
                else:
                    st.markdown(kpi('撣?撣嗅祝','-','?豢?銝雲','#484f58'),unsafe_allow_html=True)

        # ?? ??憭批葦撱箄降嚗?澆祕??????????????????????????
        _grade_label, _grade_color, _, _grade_emoji = health_grade(health2)
        _price_pos = ''
        if df2 is not None and 'MA20' in df2.columns and 'MA100' in df2.columns:
            _p2 = price2
            _m20 = float(df2['MA20'].iloc[-1])
            _m100 = float(df2['MA100'].iloc[-1])
            if _p2 > _m20 > _m100:
                _price_pos = '憭??嚗?銵撘瑕'
            elif _p2 < _m20 < _m100:
                _price_pos = '蝛粹??嚗?銵?摹'
            elif _p2 > _m100:
                _price_pos = '憭拳?渡?嚗?敺???
            else:
                _price_pos = '蝛箇拳?渡?嚗牲??雿?
        _verdict_color = TRAFFIC_GREEN if health2>=80 else (TRAFFIC_YELLOW if health2>=50 else TRAFFIC_RED)
        _verdict = ('?銝?嚗?蝟餌?敺????璅?銵函?芰嚗匱蝥??? if health2>=80
                    else ('蝑?蝒閮?嚗?餈賡?嚗?蝛箔漱?堆??孵??芣?嚗?撣??? if health2>=50
                          else '????????頞典?摹嚗誑靽?箏??))
        st.markdown(f"""<div style="background:#161b22;border:1px solid {_verdict_color};
border-left:4px solid {_verdict_color};border-radius:8px;padding:12px 14px;margin:8px 0;">
<span style="font-size:13px;font-weight:800;color:{_verdict_color};">{_grade_emoji} 憭批葦蝬?撱箄降嚗_verdict}</span>
<div style="font-size:11px;color:#8b949e;margin-top:4px;">?銵?蝵殷?{_price_pos} | RSI={rsi2} | ??={vr2} | KD=K{k2}/D{d2}</div>
</div>""", unsafe_allow_html=True)

        st.caption('?? 閰?璅???璅牧????閰唾????交??ab')


        # ?? v4.0 ?脣?蝺?+ 蝐Ⅳ + 憟鞈?? ?????????????????????????????
        try:
            if df2 is not None and not df2.empty:
                # Build df for V4 engine (map column names)
                _v4_df = df2.copy()
                _col_map = {}
                for _c in _v4_df.columns:
                    if _c in ('close','Close','adj close'):
                        _col_map[_c] = 'close'
                    elif _c in ('open','Open'):
                        _col_map[_c] = 'open'
                    elif _c in ('low','Low'):
                        _col_map[_c] = 'low'
                    elif _c in ('volume','Volume','Trading_Volume'):
                        _col_map[_c] = 'volume'
                _v4_df = _v4_df.rename(columns=_col_map)

                # Try to get chip data from session state
                _inst2 = st.session_state.get('t2_inst', {})
                if '憭?' in _inst2:
                    _v4_df['foreign_net'] = _inst2.get('憭?', 0)
                    _v4_df['trust_net']   = _inst2.get('?縑', 0)

                # Macro data from li_latest
                _li_for_v4 = st.session_state.get('li_latest')
                _v4_fut2 = 0.0
                _v4_pcr2 = 100.0
                if _li_for_v4 is not None and not _li_for_v4.empty:
                    try:
                        _v4_fut2 = float(_li_for_v4.iloc[-1].get('憭?憭批?', 0) or 0)
                    except Exception:
                        pass
                    try:
                        _v4_pcr2 = float(_li_for_v4.iloc[-1].get('?碓CR', 100) or 100)
                    except Exception:
                        pass

                _shares = st.session_state.get(f't2_shares_{sid2}', 1000000)
                _v4eng  = V4StrategyEngine(_v4_df,
                                           {'vix': 15, 'foreign_futures': _v4_fut2, 'pcr': _v4_pcr2},
                                           max(int(_shares), 1))
                _v4rep  = _v4eng.generate_report()

                st.markdown('---')
                _v4c1, _v4c2, _v4c3 = st.columns(3)

                # Task 4: Stop Loss
                with _v4c1:
                    _sl = _v4rep['stop_loss']
                    _sl_color = '#da3633' if _sl['stop_loss'] else '#484f58'
                    st.markdown(
                        f'<div style="background:#0d1117;border:1px solid {_sl_color};'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:10px;color:#484f58;">?儭?v4 ?脣???/div>'
                        f'<div style="font-size:20px;font-weight:900;color:{_sl_color};">'
                        f'{_sl["stop_loss"] or "N/A"} ??/div>'
                        f'<div style="font-size:11px;color:#8b949e;">MA20={_sl["ma20"]} | '
                        f'憸券 {_sl["risk_pct"]}%</div>'
                        f'<div style="font-size:10px;color:#da3633;">頝?⊥?隞嗅???/div>'
                        f'</div>', unsafe_allow_html=True)

                # Task 3: VPOC Resistance
                with _v4c2:
                    _rs = _v4rep['resistance']
                    _rs_color = '#da3633' if _rs['has_pressure'] else '#2ea043'
                    st.markdown(
                        f'<div style="background:#0d1117;border:1px solid {_rs_color};'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:10px;color:#484f58;">?? v4 銝鞈??</div>'
                        f'<div style="font-size:14px;font-weight:900;color:{_rs_color};">'
                        f'{"?? ?圾憟都憯? if _rs["has_pressure"] else "??憯???"}</div>'
                        f'<div style="font-size:11px;color:#8b949e;">'
                        f'VPOC={_rs["vpoc_price"] or "N/A"} ??/div>'
                        f'</div>', unsafe_allow_html=True)

                # Task 1: Chip Ratio
                with _v4c3:
                    _ch = _v4rep['chip_analysis']
                    _ch_color = '#da3633' if '撘瑕' in _ch['signal'] else ('#2ea043' if '皜' in _ch['signal'] else '#388bfd')
                    st.markdown(
                        f'<div style="background:#0d1117;border:1px solid {_ch_color};'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:10px;color:#484f58;">? v4 ?詨?蝐Ⅳ</div>'
                        f'<div style="font-size:13px;font-weight:900;color:{_ch_color};">'
                        f'{_ch["signal"][:10]}</div>'
                        f'<div style="font-size:10px;color:#8b949e;">'
                        f'憭瘥?{_ch["foreign_ratio"] or "--"}%</div>'
                        f'</div>', unsafe_allow_html=True)
        except Exception as _v4_err:
            st.caption(f'v4.0 ???仿?嚗type(_v4_err).__name__}')


        # ?? v5.0 RS撘瑕漲 + 隡啣?+ 撣??菜葫 ?????????????????????????????
        try:
            if df2 is not None and not df2.empty and len(df2) >= 20:
                _v5_r1, _v5_r2, _v5_r3 = st.columns(3)

                # Task 9: Bollinger Breakout
                with _v5_r1:
                    _bb5 = detect_bollinger_breakout(df2)
                    _bb5c = _bb5['color']
                    st.markdown(
                        f'<div style="background:#0d1117;border:1px solid {_bb5c};'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:10px;color:#484f58;">?? v5 撣??菜葫</div>'
                        f'<div style="font-size:13px;font-weight:900;color:{_bb5c};">'
                        f'{_bb5["signal"][:10]}</div>'
                        f'<div style="font-size:10px;color:#8b949e;">BW={_bb5["bw"]}%</div>'
                        f'</div>', unsafe_allow_html=True)

                # Task 10: 357 摮畾??
                with _v5_r2:
                    _dy5 = calc_dividend_yield_357(
                        price2 or 0,
                        pd.to_numeric((qtr2['EPS'] if qtr2 is not None and not qtr2.empty and 'EPS' in qtr2.columns else pd.Series(dtype=float)).head(4), errors='coerce').fillna(0).sum(),
                        avg_div2 / max(price2, 1) if avg_div2 and price2 else 0,
                        len([d for d in (st.session_state.get('t2_div_hist',[]) or []) if d > 0])
                    )
                    _dy5c = _dy5['color']
                    st.markdown(
                        f'<div style="background:#0d1117;border:1px solid {_dy5c};'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:10px;color:#484f58;">? v5 摮畾??/div>'
                        f'<div style="font-size:14px;font-weight:900;color:{_dy5c};">'
                        f'{_dy5["est_yield"] or "N/A"}%</div>'
                        f'<div style="font-size:10px;color:#8b949e;">{_dy5["signal"][:8]}</div>'
                        f'</div>', unsafe_allow_html=True)

                # Task 5: 鞎∪??
                with _v5_r3:
                    _fl5 = analyze_fundamental_leading(cl2, None, None, None,
                                                       st.session_state.get(f't2_equity_{sid2}'))
                    _fl5c = _fl5['color']
                    st.markdown(
                        f'<div style="background:#0d1117;border:1px solid {_fl5c};'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:10px;color:#484f58;">? v5 鞎∪??</div>'
                        f'<div style="font-size:13px;font-weight:900;color:{_fl5c};">'
                        f'{_fl5["signal"][:8]}</div>'
                        f'<div style="font-size:10px;color:#8b949e;">'
                        f'{"??鞎 ?? if cl2 and cl2>0 else "?∪?蝝???}</div>'
                        f'</div>', unsafe_allow_html=True)
        except Exception as _v5e2:
            st.caption(f'v5.0 ?脤????仿?嚗type(_v5e2).__name__}')

        # ?? E. VCP + 撣? ??????????????????????????????????????
        st.markdown('---')
        st.markdown('#### ? E. VCP瘜Ｗ??嗥葬 + 撣???')
        st.caption('? ???質店嚗CP嚗?寞郭??瘜Ｘ?銝瘜Ｗ?嚗?敶飢憯?嚗?撣豢?游???渡?嚗?
                   '撣???嚗?寧?銝?頠?嚗葆撖祆蝮桐誨銵刻??文?喋?寡票銝??撥??)
        if vcp2 and vcp2.get('contracting'):
            _sw = vcp2.get('swings', [])
            _ea = f'VCP蝣箄??嗥葬嚗len(_sw)}瘜Ｘ挾嚗???葬嚗?敺葆???湧脣'
            _eb = '蝒??銝??鞎瑕嚗??身?郭雿?'
        elif vcp2:
            _sw = vcp2.get('swings', [])
            _ea = f'VCP撠敶Ｘ?嚗len(_sw)}瘜Ｘ挾嚗?瘜Ｗ?隞之嚗?摰脣'
            _eb = '蝑??游??渡???嚗?蝑?
        else:
            _ea = '?豢?銝雲嚗CP?⊥?閮?嚗??喳?30?亙?潸???'
            _eb = ''
        st.markdown(teacher_conclusion('?勗振瘜?, f'{sid2} VCP??', _ea, _eb), unsafe_allow_html=True)
        ec1,ec2=st.columns(2)
        with ec1:
            st.markdown('**VCP [Mark Minervini]**')
            if vcp2:
                sw=' ??'.join([f'{s:.1f}%' for s in vcp2['swings']])
                vc=TRAFFIC_GREEN if vcp2['contracting'] else TRAFFIC_YELLOW
                st.markdown(kpi('VCP???,'?泵?蝮? if vcp2['contracting'] else '???芣蝮?,
                                f'瘜Ｗ?嚗sw}',vc,vc),unsafe_allow_html=True)
                if vcp2['contracting']:
                    st.markdown(signal_box('?蝑?撣園?蝒?貊?','green','蝣箄?蝒?脣'),unsafe_allow_html=True)
            else:
                st.info('?豢?銝雲嚗???0?伐?')
        with ec2:
            st.markdown('**撣??? [蝑3]**')
            if bb2:
                b1,b2=st.columns(2)
                with b1:
                    st.markdown(kpi('?曉',f'{bb2["price"]:.2f}','','#e6edf3'),unsafe_allow_html=True)
                    st.markdown(kpi('撣?銝?',f'{bb2["upper"]:.2f}','憯?',TRAFFIC_RED,TRAFFIC_RED),unsafe_allow_html=True)
                with b2:
                    bw_c=TRAFFIC_GREEN if bb2['bw']<bb2['bw_mean']*0.7 else TRAFFIC_YELLOW
                    st.markdown(kpi('撣嗅祝',f'{bb2["bw"]:.1f}%',
                                    f'?慮bb2["bw_mean"]:.1f}% {"漎??嗥葬" if bb2["bw"]<bb2["bw_mean"] else "漎??游撐"}',
                                    bw_c,bw_c),unsafe_allow_html=True)
                    st.markdown(kpi('撣?銝?',f'{bb2["lower"]:.2f}','?舀?',TRAFFIC_GREEN,TRAFFIC_GREEN),unsafe_allow_html=True)
                if bb2['bw']<bb2['bw_mean']*0.6:
                    st.markdown(signal_box('?撣?撣嗅祝璆萄漲?嗥葬','blue','?喳??嚗釣???賣??),unsafe_allow_html=True)
                if bb2['near_upper']:
                    st.markdown(signal_box('??∪暺?銝?','green','撘瑕蝒閮?嚗?之??臭縑'),unsafe_allow_html=True)
        # ?? VCP+撣???撱箄降 ??
        _vcp_verdict = ''
        _bb_verdict  = ''
        if vcp2:
            _vcp_verdict = ('??VCP蝣箄??嗥葬嚗?敺葆???湧蝺??舫?蝣箔縑?脣暺?[蝑3]'
                            if vcp2['contracting']
                            else '??瘜Ｗ?撠?嗥葬嚗?敺??????撖?)
        if bb2:
            if bb2['bw'] < bb2['bw_mean']*0.6:
                _bb_verdict = '? 撣?撣嗅祝璆萄漲?嗥葬嚗撠??潘?瘜冽??蝣箄??孵? [蝑3]'
            elif bb2['near_upper']:
                _bb_verdict = '? ?∪暺?銝?嚗撥?ｇ??剝?憭折??舐??渡Ⅱ隤???[蝑3]'
            else:
                _bb_verdict = f'??撣?撣嗅祝{bb2["bw"]:.1f}%嚗??慮bb2["bw_mean"]:.1f}%嚗?撠?圈??萎?蝵?
        if _vcp_verdict or _bb_verdict:
            for _msg in [m for m in [_vcp_verdict, _bb_verdict] if m]:
                _mc2 = TRAFFIC_GREEN if '?? in _msg or '?' in _msg else ('#58a6ff' if '?' in _msg else '#8b949e')
                st.markdown(f'<div style="border-left:3px solid {_mc2};padding:8px 12px;background:#0d1117;border-radius:0 6px 6px 0;font-size:12px;color:{_mc2};margin:4px 0;">{_msg}</div>', unsafe_allow_html=True)

        # VCP+撣?蝯?嚗??函?嚗???_msg ?身?潘?
        _msg = _msg if '_msg' in dir() else '??VCP/撣?鞈?銝雲'
        _vcp_c = TRAFFIC_GREEN if '?? in _msg or '?' in _msg else (TRAFFIC_YELLOW if '??' in _msg else '#484f58')
        st.markdown(
            f'<div style="background:#0d1117;border-left:3px solid {_vcp_c};padding:7px 12px;border-radius:0 6px 6px 0;margin:4px 0;">'
            f'<span style="font-size:11px;color:#8b949e;">?? 蝑3 繚 VCP</span>?'
            f'<span style="font-size:13px;font-weight:700;color:{_vcp_c};">{_msg}</span>'
            f'</div>', unsafe_allow_html=True
        )
        if bb2:
            _bb_verdict_safe = _bb_verdict if '_bb_verdict' in dir() else '??撣?鞈?銝雲'
            _bb_c = TRAFFIC_GREEN if '?? in _bb_verdict_safe or '?' in _bb_verdict_safe else ('#3aa2f5' if '?' in _bb_verdict_safe else TRAFFIC_YELLOW)
            st.markdown(
                f'<div style="background:#0d1117;border-left:3px solid {_bb_c};padding:7px 12px;border-radius:0 6px 6px 0;margin:4px 0;">'
                f'<span style="font-size:11px;color:#8b949e;">?? 蝑3 繚 撣?</span>?'
                f'<span style="font-size:13px;font-weight:700;color:{_bb_c};">{_bb_verdict_safe}</span>'
                f'</div>', unsafe_allow_html=True
            )

        # ?? G. 餈?20 ?亦?蝣潮?銝剖漲嚗?鞈??縑 vs 蝮賣?鈭日?嚗???????????
        st.markdown('---')
        st.markdown('#### ? G. 餈?20 ?亦?蝣潮?銝剖漲')
        st.caption('? ???質店嚗?銝剖漲嚗之?塚?憭?+?縑嚗楊鞎琿?雿蜇?漱??瘥?嚗迤?潸?擃?憭扳暺??貉疏嚗?憭???
                   '鞎潘??疏嚗辣蝥改??餈?撠?靘?鈭斗??交?蝥眺頞???亙??芯???K 蝺?銝之瘜犖/?漱??)
        # v18.196 ?渡?嚗f2 撌脣銝之瘜犖甈???蝘駁 spinner ?踹?閬死頝喳???
        # 蝘駁 analyze_20d_chips(sid2) fallback ?踹?蝚砌?甈?FinMind API ?澆
        _chip20 = analyze_20d_chips_from_df(df2)
        if _chip20.get('error'):
            st.caption(f'??蝐Ⅳ?葉摨血?敺仃??{_chip20["error"]}')
        else:
            _sig20  = _chip20['signal']
            _con20  = _chip20['concentration']   # % ?葉摨?
            _cty20  = _chip20['continuity']       # % 撱嗥???
            _days20 = _chip20['days']
            _pos20  = _chip20['pos_days']
            _sig20_c = (TRAFFIC_RED if '?貊?' in _sig20
                        else ('#da3633' if '?疏' in _sig20 else TRAFFIC_YELLOW))
            st.markdown(
                f'<div style="background:#0d1117;border:1px solid {_sig20_c};'
                f'border-radius:8px;padding:10px 14px;margin:6px 0;">'
                f'<span style="font-size:14px;font-weight:900;color:{_sig20_c};">'
                f'{_sig20}</span>'
                f'<span style="font-size:11px;color:#8b949e;margin-left:12px;">'
                f'餈?{_days20} ??| 憭??敞閮?{_chip20["total_net_k"]:.1f}?撐 | '
                f'?漱??{_chip20["total_vol_k"]:.1f}?撐</span>'
                f'</div>', unsafe_allow_html=True)
            _g20c1, _g20c2 = st.columns(2)
            with _g20c1:
                st.metric(
                    label='??A嚗?銝剖漲嚗?+?楊鞎瘀?蝮賡?嚗?,
                    value=f'{_con20:+.2f}%',
                    delta='?貊?' if _con20 >= 0 else '?疏',
                    delta_color='normal' if _con20 >= 0 else 'inverse',
                    help='> +5% 銝辣蝥?> 50% ??憭扳?貊?嚗? -5% ??憭扳?疏')
                st.progress(min(abs(_con20) / 20.0, 1.0),
                            text=f'?葉摨衣?撠?{abs(_con20):.1f}% / 20%銝?')
            with _g20c2:
                st.metric(
                    label=f'??B嚗辣蝥改?{_days20}?乩葉鞎瑁? {_pos20} 憭抬?',
                    value=f'{_cty20:.0f}%',
                    help='> 50% 銵函內憭鈭斗??亙?+??蝥眺頞?)
                st.progress(_cty20 / 100.0,
                            text=f'鞎瑁?憭拇雿? {_cty20:.0f}%')

        # ?? F. K蝺?銵? ????????????????????????????????????????
        st.markdown('---')
        st.markdown('#### ?? F. K蝺?銵?銵剁??思?憭扳?鈭箇?蝣潘?')
        _fa = f'{sid2} K蝺?銵?
        _fb_txt = ''
        _fc_txt = ''
        if df2 is not None and not df2.empty and len(df2) >= 20:
            _p_now_f = float(df2['close'].iloc[-1])
            _ma20_f  = float(df2['close'].rolling(20).mean().iloc[-1])
            _cl_trend = '銝撞' if float(df2['close'].iloc[-1]) > float(df2['close'].iloc[-5]) else '銝?'
            _above_f = _p_now_f > _ma20_f
            _inst_f = st.session_state.get('t2_inst', {})
            _fnet_f = _inst_f.get('憭?', 0) if _inst_f else 0
            if _above_f and _fnet_f > 0:
                _fb_txt = '蝡??? + 憭?鞎瑁?嚗蜓?脤?閮?嚗頝?
                _fc_txt = '??閮剜?蝺???
            elif _above_f and _fnet_f < 0:
                _fb_txt = '蝡???雿?鞈都頞??雓寞?蝣箄?銝餃??孵?'
                _fc_txt = '蝑?憭?頧眺敺?銵?'
            elif not _above_f and _fnet_f > 0:
                _fb_txt = '??銝雿?鞈眺頞??航甇?蝭?'
                _fc_txt = '蝑?????蝣箄?敺?閰摯'
            else:
                _fb_txt = '??銝銝?鞈都頞?頞典?征嚗?艘??
                _fc_txt = '蝑??湔?蝣箇?憭閮?'
            _fa = f'{sid2} ?曉{_p_now_f:.1f}嚗"蝡?蝺? if _above_f else "頝?蝺?}嚗 憭?{"鞎瑁?" if _fnet_f>0 else "鞈??" if _fnet_f<0 else "銝剜?}'
        else:
            _fb_txt = '?銵????乩葉嚗??????頛摰????
        st.markdown(teacher_conclusion('?勗振瘜?, _fa, _fb_txt, _fc_txt), unsafe_allow_html=True)
        if df2 is not None and not df2.empty:
            fig_k = plot_combined_chart(df2, sid2, name2, show_ma_dict, k_line_type='??K蝺? if t2_adjusted else '銝?春蝺?)
            st.plotly_chart(fig_k, width='stretch',
                            config={'displayModeBar':True,'displaylogo':False,
                                    'modeBarButtonsToRemove':['lasso2d','select2d']})
        else:
            if t2d.get('err'):
                st.error(f'??{t2d["err"]}')
        # ?? K蝺??隅?Ｗ遣霅???
        if df2 is not None and 'MA20' in df2.columns and 'MA100' in df2.columns:
            _kp = price2
            _km20 = float(df2['MA20'].iloc[-1])
            _km100 = float(df2['MA100'].iloc[-1])
            if _kp > _km20 > _km100:
                _trend_msg = f'?? 憭??嚗??{_kp:.1f} 嚗?MA20 {_km20:.1f} 嚗?MA100 {_km100:.1f} ??摰嚗?嚗之?文??剜??'
                _tc = TRAFFIC_GREEN
            elif _kp < _km20 < _km100:
                _trend_msg = f'?? 蝛粹??嚗??{_kp:.1f} 嚗?MA20 {_km20:.1f} 嚗?MA100 {_km100:.1f} ??摰嚗???嚗?澆???
                _tc = TRAFFIC_RED
            elif _kp > _km100:
                _trend_msg = f'?? 憭拳?渡?嚗?孵 MA100 銋? ??摰嚗?敺?銝?MA20({_km20:.1f})蝣箄??孵?'
                _tc = TRAFFIC_YELLOW
            else:
                _trend_msg = '?? 蝛箇拳?渡?嚗?嫣???MA100 ??摰嚗?蝑?憭閮?嚗??詨?'
                _tc = TRAFFIC_YELLOW
            st.markdown(f'<div style="border-left:4px solid {_tc};padding:10px 14px;background:#0d1117;border-radius:0 8px 8px 0;font-size:13px;font-weight:700;color:{_tc};margin:8px 0;">{_trend_msg}</div>', unsafe_allow_html=True)

        # K蝺?蝺?隢?摰??
        _trend_msg_safe = _trend_msg if '_trend_msg' in dir() else '??K蝺???頞?
        _kl_c = TRAFFIC_GREEN if '憭' in _trend_msg_safe or '?? in _trend_msg_safe else (TRAFFIC_RED if '蝛粹' in _trend_msg_safe else TRAFFIC_YELLOW)
        st.markdown(
            f'<div style="background:#0d1117;border-left:3px solid {_kl_c};padding:7px 12px;border-radius:0 6px 6px 0;margin:4px 0;">'
            f'<span style="font-size:11px;color:#8b949e;">?? 摰 繚 ????</span>?'
            f'<span style="font-size:13px;font-weight:700;color:{_kl_c};">{_trend_msg_safe}</span>'
            f'</div>', unsafe_allow_html=True
        )

        # ?? 餈??亥??粥?ｇ??脣??祆活閰??唳風?莎????????????????????
        _score_hist_key = f'score_hist_{sid2}'
        _score_hist = st.session_state.get(_score_hist_key, [])
        # ?隞閰?
        _today_str = datetime.date.today().strftime('%m/%d')
        _last_entry = _score_hist[-1] if _score_hist else {}
        if _last_entry.get('date') != _today_str:
            _score_hist.append({
                'date':    _today_str,
                'health':  health2,
                'rsi':     rsi2 or 0,
                'total':   0,  # 憭?摮?? Tab3 銝?
            })
            _score_hist = _score_hist[-7:]  # ?芯???餈?憭?
            st.session_state[_score_hist_key] = _score_hist

        if len(_score_hist) >= 2:
            st.markdown('---')
            st.markdown('##### ?? ?亙熒摨西粥?ｇ?餈??伐?')
            _fig_sh = go.Figure()
            _sh_dates  = [r['date']   for r in _score_hist]
            _sh_health = [r['health'] for r in _score_hist]
            # 憛怨???
            _fig_sh.add_hrect(y0=80, y1=100, fillcolor='rgba(63,185,80,0.08)',  line_width=0)
            _fig_sh.add_hrect(y0=50, y1=80,  fillcolor='rgba(210,153,34,0.05)', line_width=0)
            _fig_sh.add_hrect(y0=0,  y1=50,  fillcolor='rgba(248,81,73,0.05)',  line_width=0)
            _fig_sh.add_trace(go.Scatter(
                x=_sh_dates, y=_sh_health, mode='lines+markers',
                line=dict(color='#58a6ff', width=2.5),
                marker=dict(size=8, color=[TRAFFIC_GREEN if v>=80 else (TRAFFIC_YELLOW if v>=50 else TRAFFIC_RED)
                                           for v in _sh_health]),
                text=[str(v) for v in _sh_health], textposition='top center',
                hovertemplate='%{x}<br>?亙熒摨佗?%{y:.0f}<extra></extra>'
            ))
            _fig_sh.update_layout(
                height=180, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                font=dict(color='white',size=10), margin=dict(l=10,r=10,t=10,b=20),
                xaxis=dict(gridcolor='#21262d'), yaxis=dict(gridcolor='#21262d',range=[0,105]),
                showlegend=False)
            st.plotly_chart(_fig_sh, width='stretch', config={'displayModeBar':False})
            # 閰?蝒??菜葫嚗??賊??20??
            if len(_sh_health) >= 2 and _sh_health[-1] - _sh_health[-2] >= 20:
                st.success(f'?? 閰?蝒?嚗摨瑕漲敺?{_sh_health[-2]:.0f} ??{_sh_health[-1]:.0f}嚗?{_sh_health[-1]-_sh_health[-2]:.0f}嚗??航?臭蜓?挾韏琿?嚗?)

        # ?? G. AI 鈭雁?勗? ??????????????????????????????????????
        st.markdown('---')

        # ?? ?單???撱箄降嚗ule-based嚗?? AI API嚗??????????????
        st.markdown('#### ? ?單???撱箄降嚗?????')
        _reg_op = st.session_state.get('mkt_info', {}).get('regime', 'neutral')
        _sig_count = sum([
            1 if health2 >= 80 else 0,
            1 if _reg_op == 'bull' else 0,
            1 if (vcp2 and vcp2.get('contracting')) else 0,
            1 if (avg_div2 > 0 and price2 > 0 and price2 <= round(avg_div2/0.05, 1)) else 0,
        ])
        if _reg_op == 'bear':
            _op_a = f'憭抒蝛粹?澆?嚗sid2} ?∟?閰?憭?嚗??20%隞乩?'
            _op_b = '撣頞典?芸?嚗撘瑚?蝑?質竟??
        elif _sig_count >= 3:
            _op_a = f'{_sig_count}????荔??亙熒摨?憭抒+VCP+隡啣潘?嚗蝛扔?脣'
            _op_b = '?撱箏???閮剖摨瑕漲頝60'
        elif _sig_count >= 2:
            _op_a = f'{_sig_count}????荔?銝剜批?憭??臬??岫瘞湔澈'
            _op_b = '頛岫?ｇ?蝑??游?蝣箄?閮?'
        else:
            _op_a = f'?芣?{_sig_count}????璇辣銝雲嚗??乩??? {sid2}'
            _op_b = '??蝑?嚗祐?舫?撘瑟?'
        st.markdown(teacher_conclusion('摰', f'{sid2} ?望閮? {_sig_count}/4', _op_a, _op_b), unsafe_allow_html=True)
        try:
            _mkt_top_g = st.session_state.get('mkt_info', {})
            _m1b_top_g = st.session_state.get('m1b_m2_info', {})
            _bias_g    = st.session_state.get('bias_info', {})
            _m1b_diff_g= _m1b_top_g.get('m1b_yoy',0)-_m1b_top_g.get('m2_yoy',0) if _m1b_top_g else 0
            # ??Tab3 ?餈???憭?鞈?
            _cd_g = st.session_state.get('cl_data',{})
            _inst_g = _cd_g.get('inst',{})
            _fk_g = next((k for k in _inst_g if '憭?' in k), None)
            _tk_g = next((k for k in _inst_g if '?縑' in k), None)
            _comment_data = {
                'health':      health2,
                'score':       0,  # Tab3 憭?摮???甇方??⊥???嚗0嚗?
                'rsi':         rsi2,
                'vcp_ok':      bool(vcp2 and isinstance(vcp2,dict) and vcp2.get('contracting')),
                'bias_240':    _bias_g.get('bias_240', 0),
                'bias_20':     _bias_g.get('bias_20', 0),
                'val_label':   _357_label2 if '_357_label2' in dir() else '',  # noqa: F821
                'trend':       _trend_text2 if '_trend_text2' in dir() else '',  # noqa: F821
                'cl':          cl2 / 1e8 if cl2 and cl2 > 0 else 0,
                'cx':          cx2 / 1e8 if cx2 and cx2 > 0 else 0,
                'foreign_buy': _inst_g.get(_fk_g,{}).get('net',0) if _fk_g else 0,
                'trust_buy':   _inst_g.get(_tk_g,{}).get('net',0) if _tk_g else 0,
                'm1b_diff':    _m1b_diff_g,
            }
            _comment_txt = generate_ai_comment(_comment_data)
            if _comment_txt:
                st.markdown(
                    '<div style="background:#0d1117;border:1px solid #30363d;'
                    'border-radius:10px;padding:14px;margin-bottom:10px;'
                    'font-size:13px;color:#c9d1d9;line-height:1.7;">'
                    + _comment_txt.replace(chr(10), '<br>') +
                    '</div>', unsafe_allow_html=True)
        except Exception as _ce:
            pass

        st.markdown(f"""<div style="margin:24px 0 8px;padding:8px 16px;background:linear-gradient(90deg,{TRAFFIC_GREEN}18,#0d1117);border-left:4px solid {TRAFFIC_GREEN};border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:{TRAFFIC_GREEN};">?? ?箸?Ｗ???/span><span style="font-size:11px;color:#8b949e;margin-left:8px;">357畾????繚 鞎∪???? 繚 ???嗉隅??繚 ?剖之????</span></div>""", unsafe_allow_html=True)
        # ?? B. 357 閰 ????????????????????????????????????????
        st.markdown('---')
        st.markdown('#### ? B. 357畾????[蝑1]')
        if avg_div2 > 0 and price2 > 0:
            _cp2 = round(avg_div2/0.07, 1)
            _fp2 = round(avg_div2/0.05, 1)
            _dp2 = round(avg_div2/0.03, 1)
            if price2 <= _cp2:
                _ba = f'?曉 {price2:.1f} ??靘踹???{_cp2:.1f}嚗??拍?>7%嚗?蝛扔鞎琿脣?'
                _bb = '?臬之?質眺?莎??⊥?賡脣鋡?
            elif price2 <= _fp2:
                _ba = f'?曉 {price2:.1f} ?典??? {_cp2:.1f}?_fp2:.1f}嚗??拍?5-7%嚗?
                _bb = '?臬??孵?撅嚗銝甈⊥╲??
            elif price2 <= _dp2:
                _ba = f'?曉 {price2:.1f} ?冽?鞎游? {_fp2:.1f}?_dp2:.1f}嚗??拍?3-5%嚗?
                _bb = '雓寞?嚗??矽?喳???脣'
            else:
                _ba = f'?曉 {price2:.1f} > ?眼??{_dp2:.1f}嚗??拍?<3%嚗??渡?餈賡?'
                _bb = '?曆?嚗?憭扯???'
        else:
            _ba = '?∟?抵????⊥?憟357閰'
            _bb = '隞交?銵?亙熒摨衣銝餉??斗'
        st.markdown(teacher_conclusion('摮急樴?, f'{sid2} ?曉{price2:.1f} vs 357???, _ba, _bb), unsafe_allow_html=True)
        if avg_div2 > 0:
            cheap2=round(avg_div2/0.07,1)
            fair2=round(avg_div2/0.05,1)
            dear2=round(avg_div2/0.03,1)
            if price2<=cheap2:
                sig2,sc2='?靘踹?????蝛扔鞎琿?,TRAFFIC_GREEN
            elif price2<=fair2:
                sig2,sc2='????????臬??孵?撅',TRAFFIC_YELLOW
            elif price2<=dear2:
                sig2,sc2='??眼????雓寞???',TRAFFIC_RED
            else:
                sig2,sc2='?頞??眼 ???踹?餈賡?',TRAFFIC_RED
            st.markdown(f"""<div style="background:#161b22;border:2px solid {sc2};border-radius:10px;
padding:12px 16px;margin:8px 0;">
<div style="font-size:16px;font-weight:900;color:{sc2};">{sig2}</div>
<div style="font-size:11px;color:#8b949e;margin-top:4px;">
  {sid2} {name2} | ?曉 <b style="color:#58a6ff;">{price2:.2f}</b> |
  餈?撟游??∪ <b style="color:#ffd700;">{avg_div2:.2f}??/b> ({t2d.get('div_src','')})
</div></div>""", unsafe_allow_html=True)
            v1,v2,v3,v4=st.columns(4)
            for vc,vl,vp,vcol in [(v1,'?曉',price2,'#58a6ff'),(v2,'?靘踹?(7%)',cheap2,TRAFFIC_GREEN),
                                   (v3,'???(5%)',fair2,TRAFFIC_YELLOW),(v4,'??眼(3%)',dear2,TRAFFIC_RED)]:
                with vc:
                    st.markdown(kpi(vl,f'{vp:.1f}','',vcol,vcol),unsafe_allow_html=True)
            if yearly2:
                fig_d=go.Figure(go.Bar(
                    x=[str(int(y['year'])) for y in yearly2],
                    y=[y['cash'] for y in yearly2],
                    marker_color='#ffd700',
                    text=[f'{y["cash"]:.2f}' for y in yearly2],textposition='auto'))
                fig_d.update_layout(height=180,plot_bgcolor='#0e1117',paper_bgcolor='#0e1117',
                                    font=dict(color='white'),margin=dict(l=20,r=20,t=30,b=20),
                                    title=dict(text=f'{sid2} 餈?撟渡???,font=dict(color='#ffd700',size=12)),
                                    yaxis=dict(gridcolor='#333'),xaxis=dict(gridcolor='#333'))
                st.plotly_chart(fig_d,width='stretch',config={'displayModeBar':False})
        else:
            st.warning('?? ?⊿??航?????∴???撱箄降?寧?祉?瘥?隡?)
        # ?? 357 ??撱箄降 ??
        _asset_type = '?? 憭抒' if sid2 in ('^TWII', 'TAIEX') else '?? ?'
        if avg_div2 > 0:
            _grade = ("靘踹??屢????蝑1嚗?璆菔眺?莎?" if price2<=cheap2
                      else ("???屢????蝑1嚗?撣?嚗?畾?????Ⅳ" if price2<=fair2
                            else ("?眼?屢????蝑1嚗牲??雿?蝑????脣" if price2<=dear2
                                  else "頞??眼?屢????蝑1嚗?撠?餈賡?嚗?敺之撟耨甇?)))
            _357_verdict = f'**{sid2} {name2}** ?曉 {price2:.1f} ? {_grade}嚗?5撟游??∪ {avg_div2:.2f} ??
            _357_c = TRAFFIC_GREEN if price2<=cheap2 else (TRAFFIC_YELLOW if price2<=fair2 else TRAFFIC_RED)
            st.markdown(
                f'{_asset_type} **`{sid2}` {name2}** 嚚?蝑1繚357瘜??斗'
            )
            st.markdown(f'<div style="background:#161b22;border-left:4px solid {_357_c};padding:10px 14px;border-radius:0 8px 8px 0;font-size:13px;font-weight:700;color:{_357_c};margin:6px 0;">{_357_verdict}</div>', unsafe_allow_html=True)
            # 357蝯?嚗?仿＊蝷箇??隡堆?銝????交???
            st.markdown(
                f'<div style="background:#0d1117;border-left:4px solid {_357_c};'
                f'padding:10px 14px;border-radius:0 8px 8px 0;margin:6px 0;">'
                f'<span style="font-size:12px;color:#8b949e;">{_asset_type} <code>{sid2}</code> {name2} 嚚??? 蝑1 繚 357瘜??斗</span><br>'
                f'<span style="font-size:14px;font-weight:800;color:{_357_c};">{_357_verdict}</span><br>'
                f'<span style="font-size:11px;color:#8b949e;">?方??摩嚗??拍???%=靘踹?憭扯眺嚗?-7%=??嚗?-5%=?眼??嚗?lt;3%=?眼?</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        # ?? 隡啣潭眾瘚?嚗?57畾?眾瘚?? TTM嚗????????????????????
        st.caption('? 瘝單??獐???噶摰???嚗?鞎氬?蝔桐摯?潭偌雿?撣塚???對?蝺??賢?芯?璇???'
                   '??蝺???詨?靘踹???銝楠嚗撠眼???嫣?撘萇銝?閫漲隡啣潘?'
                   '畾?眾瘚??券??荔?畾??嚗噶摰????瘝單?嚗瘥?? EPS嚗?帘摰?拙?賂???
                   '?∪瘛典潭?瘝單?嚗瘥瘛典?BPS嚗???Ｚ??? EPS ????)
        if df2 is not None and not df2.empty:
            # ?? 1. 撠?yearly2 頧??x-div 鈭辣摨???撟港葉 7/1 ?箏???舀嚗???
            # ?脰風嚗??? > 隞予嚗? 2026/5 頝? 2026/7/1 ?冽靘?嚗?65D rolling
            # 瘨菔?銝 ???湔挾 TTM ??0 ??瘝單?瘨仃?歲???靘?隞嗚?
            _today_ts = pd.Timestamp(datetime.date.today())
            _riv_events = []
            if yearly2:
                for _y in yearly2:
                    try:
                        _y_cash = float(_y.get('cash', 0) or 0)
                        if _y_cash > 0:
                            _ev_dt = pd.Timestamp(int(_y['year']), 7, 1)
                            if _ev_dt > _today_ts:
                                continue
                            _riv_events.append({'date': _ev_dt, 'div': _y_cash})
                    except Exception:
                        pass
            # ?亦?僑鞈?嚗 avg_div2 鋆撟?7/1??銝隞僑???冽靘?
            if not _riv_events and avg_div2 and avg_div2 > 0:
                _riv_events.append({
                    'date': pd.Timestamp(datetime.date.today().year - 1, 7, 1),
                    'div':  float(avg_div2)
                })

            if _riv_events:
                # ?? 2. 撠?df2 瘥漱???365D rolling sum (TTM ?∪) ??
                _rdates_s   = pd.to_datetime(
                    df2['date'] if 'date' in df2.columns else pd.RangeIndex(len(df2)))
                _rclose_riv = pd.to_numeric(df2['close'], errors='coerce').reset_index(drop=True)
                _rdates_riv = _rdates_s.reset_index(drop=True)

                # ?蔥??拐?隞嗚??漱???銝璇?????閮? 365D rolling sum
                _ev_df = pd.DataFrame(_riv_events).sort_values('date').reset_index(drop=True)
                _ev_df['kind'] = 'ev'
                _td_df = pd.DataFrame({'date': _rdates_riv, 'div': 0.0, 'kind': 'td'})
                _all_df = (pd.concat([_ev_df, _td_df], ignore_index=True)
                           .sort_values('date')
                           .reset_index(drop=True))
                _all_df['ttm'] = (_all_df.set_index('date')['div']
                                  .rolling('365D', min_periods=1).sum().values)

                # ?賢鈭斗??亙??? TTM嚗蒂 forward-fill 銝?甈⊥??潘??踹?撟湔蝒蝛箸?嚗?
                _td_only = _all_df[_all_df['kind'] == 'td'].copy()
                _td_only['ttm'] = _td_only['ttm'].mask(_td_only['ttm'] <= 0).ffill()
                _ttm_series = pd.to_numeric(_td_only['ttm'], errors='coerce').reset_index(drop=True)

                # ?? 摰蝬莎?TTM ?湔挾??0 / NaN嚗???12 ?????斗嚗? ???avg_div2 璈怠葆 ??
                _ttm_valid = _ttm_series.dropna()
                _is_fallback_flat = (_ttm_valid.empty or float(_ttm_valid.max()) <= 0) \
                    and avg_div2 and avg_div2 > 0
                if _is_fallback_flat:
                    _ttm_series = pd.Series([float(avg_div2)] * len(_rdates_riv))

                # ?? 3. 閮?瘝單?撣塚?P = TTM ?∪ / 畾??潘??嚗???
                _band7_riv = (_ttm_series / 0.07).round(2)
                _band5_riv = (_ttm_series / 0.05).round(2)
                _band3_riv = (_ttm_series / 0.03).round(2)

                _cur_div_riv = float(_ttm_series.dropna().iloc[-1]) if not _ttm_series.dropna().empty else 0
                _p7r = float(_band7_riv.dropna().iloc[-1]) if not _band7_riv.dropna().empty else 0
                _p5r = float(_band5_riv.dropna().iloc[-1]) if not _band5_riv.dropna().empty else 0
                _p3r = float(_band3_riv.dropna().iloc[-1]) if not _band3_riv.dropna().empty else 0

                # ?? 5. 蝜芸? ??
                _fig_riv = go.Figure()
                _fig_riv.add_trace(go.Scatter(
                    x=_rdates_riv, y=_rclose_riv, name='?嗥??,
                    line=dict(color='#e6edf3', width=2.5),
                    hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>'))

                for _bs, _lbl_base, _last_val, _col in [
                    (_band7_riv, '7%靘踹?', _p7r, TRAFFIC_GREEN),
                    (_band5_riv, '5%??', _p5r, TRAFFIC_YELLOW),
                    (_band3_riv, '3%?眼', _p3r, TRAFFIC_RED)
                ]:
                    _lbl = f'{_lbl_base}:{_last_val:.0f}' if _last_val > 0 else _lbl_base
                    _fig_riv.add_trace(go.Scatter(
                        x=_rdates_riv, y=_bs, name=_lbl,
                        line=dict(color=_col, width=1.5, dash='dot'),
                        hovertemplate=f'{_lbl_base}: %{{y:.0f}}<extra></extra>'))

                # ?脣葆嚗誑??唬??亦?撣嗅潛?箸?嚗?
                _b7_last = float(_band7_riv.dropna().iloc[-1]) if not _band7_riv.dropna().empty else 0
                _b5_last = float(_band5_riv.dropna().iloc[-1]) if not _band5_riv.dropna().empty else 0
                _b3_last = float(_band3_riv.dropna().iloc[-1]) if not _band3_riv.dropna().empty else 0
                if _b7_last > 0:
                    _fig_riv.add_hrect(y0=0, y1=_b7_last, fillcolor='rgba(63,185,80,0.07)', line_width=0)
                if _b5_last > _b7_last:
                    _fig_riv.add_hrect(y0=_b7_last, y1=_b5_last, fillcolor='rgba(210,153,34,0.07)', line_width=0)
                if _b3_last > _b5_last:
                    _fig_riv.add_hrect(y0=_b5_last, y1=_b3_last, fillcolor='rgba(248,81,73,0.05)', line_width=0)

                # Y 頠賂??芸?瘨菔??∪???眾瘚葆
                _all_riv_vals = (
                    list(_rclose_riv.dropna()) +
                    list(_band3_riv.dropna()) +
                    list(_band7_riv.dropna())
                )
                _ymax_riv = max(_all_riv_vals) * 1.05 if _all_riv_vals else 100
                _ymin_riv = max(0, min(_all_riv_vals) * 0.7) if _all_riv_vals else 0

                _div_label = '餈?撟游??∪' if _is_fallback_flat else 'TTM ?∪'
                _fig_riv.update_layout(
                    title=dict(
                        text=f'?? {sid2} {name2} 畾?眾瘚?嚗_div_label} {_cur_div_riv:.2f}??',
                        font=dict(color='#8b949e', size=12)),
                    height=300, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                    font=dict(color='white', size=11),
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis=dict(gridcolor='#21262d'),
                    yaxis=dict(range=[_ymin_riv, _ymax_riv], gridcolor='#21262d'),
                    hovermode='x unified', showlegend=True,
                    legend=dict(orientation='h', y=1.08, x=0, font=dict(size=10)))
                st.plotly_chart(_fig_riv, width='stretch', config={'displayModeBar': False})

                _cur_price_riv = float(_rclose_riv.dropna().iloc[-1]) if not _rclose_riv.dropna().empty else 0
                if _is_fallback_flat:
                    # Fallback 璅∪?嚗? 12 ??斗嚗?璈怠葆靽?雿風?脫?頛?雿宏?支噶摰???/?眼/頞?鞎游霈?踹?隤文?
                    st.caption(
                        f'?? 甇瑕?葆嚗_div_label} {_cur_div_riv:.2f}?????TTM嚗'
                        f'7%?廾_p7r:.0f} / 5%?廾_p5r:.0f} / 3%?廾_p3r:.0f}??曉 {_cur_price_riv:.0f}')
                    st.info('?對? 甇方餈?12 ???⊿?臭?隞塚?畾?眾瘚? 5 撟游??∪璈怠葆嚗?雿風?脣??改?嚗?*銝???箏?摯?潔???*?遣霅唳?冽?? / ?∪瘛典潭?蝑隞摯?澆極?瑯?)
                else:
                    _cur_zone = ('? 靘踹??' if _cur_price_riv < _p7r else
                                 '? ???' if _cur_price_riv < _p5r else
                                 '? ?眼?' if _cur_price_riv < _p3r else '??頞?鞎?)
                    st.caption(
                        f'?桀?雿 {_cur_zone}嚗??{_cur_price_riv:.0f} / '
                        f'靘踹??廾_p7r:.0f} / ???廾_p5r:.0f} / ?眼?廾_p3r:.0f}嚗?
                        f'?{_div_label} {_cur_div_riv:.2f}??)
                    if _cur_div_riv < 0.5:
                        st.info('?對? 甇方餈僑?暸??∪璆萎?嚗? 0.5??嚗??拍?瘝單?????蝢拇???撱箄降?剝??祉?瘥??嗡?隡啣澆極?瑯?)

        # ?? 隡啣潭眾瘚?嚗E ?祉?瘥眾瘚?? TTM EPS嚗???????????????????
        # TTM EPS = ?餈?4 摮?EPS ?蜇嚗風??TTM = 4 摮?rolling sum嚗??砍????亙???亦?
        _has_eps = (qtr2 is not None and not qtr2.empty
                    and 'EPS' in qtr2.columns and 'date' in qtr2.columns)
        _eps_q_clean = (pd.to_numeric(qtr2['EPS'], errors='coerce').dropna()
                        if _has_eps else pd.Series(dtype=float))

        if df2 is not None and not df2.empty and _has_eps and len(_eps_q_clean) >= 4:
            # PE ?曉潔?蝯?selectbox嚗??Ｘ平撅祆批???
            _pe_preset_label = st.selectbox(
                'PE 隡啣澆???,
                ['? 10/15/20', '靽? 8/12/16嚗瘞?儐?啗嚗?, '? 12/18/25'],
                index=0, key=f'pe_preset_{sid2}',
                help='?嚗??貊璆哨?靽?嚗?撠?隞?極/?Ｘ/DRAM 蝑?瘜Ｗ??舀除敺芰?∴??嚗??/瘨祥/頠???)
            _PE_BANDS = {
                '? 10/15/20': (10, 15, 20),
                '靽? 8/12/16嚗瘞?儐?啗嚗?: (8, 12, 16),
                '? 12/18/25': (12, 18, 25),
            }
            _pe_low, _pe_mid, _pe_high = _PE_BANDS[_pe_preset_label]

            # ?? 1. 閮??迤 TTM EPS嚗? 摮?rolling sum嚗???
            _qs = qtr2.sort_values(['撟游漲', '摮?漲']).reset_index(drop=True).copy()
            _qs['ttm_eps'] = pd.to_numeric(_qs['EPS'], errors='coerce').rolling(4, min_periods=4).sum()
            # ?砍????伐?摮? + 60 憭抬?瘨菔??啗鞎∪?砍???Q1=5/15?2=8/14?3=11/14?僑??3/31嚗?
            _qs['announce'] = pd.to_datetime(_qs['date'], errors='coerce') + pd.Timedelta(days=60)
            _qa = _qs.dropna(subset=['ttm_eps', 'announce']).sort_values('announce').reset_index(drop=True)

            # ?? 2. asof 撠??唳蝺?瘥漱??∠閰脫銋??敺?蝑歇?砍???TTM EPS ??
            _rdates_pe = pd.to_datetime(
                df2['date'] if 'date' in df2.columns else pd.RangeIndex(len(df2)),
                errors='coerce').reset_index(drop=True)
            _rclose_pe = pd.to_numeric(df2['close'], errors='coerce').reset_index(drop=True)
            _df_p = pd.DataFrame({'date': _rdates_pe, 'close': _rclose_pe}).sort_values('date').reset_index(drop=True)
            _df_a = _qa[['announce', 'ttm_eps']].rename(columns={'announce': 'date'})
            _merged_pe = pd.merge_asof(_df_p, _df_a, on='date', direction='backward')
            _ttm_eps_series = _merged_pe['ttm_eps']

            # ?? 3. 閮????TTM EPS + ?扳??⊥炎????
            _cur_eps_pe = float(_ttm_eps_series.dropna().iloc[-1]) if not _ttm_eps_series.dropna().empty else 0
            _cur_price_pe = float(_rclose_pe.dropna().iloc[-1]) if not _rclose_pe.dropna().empty else 0

            if _cur_eps_pe <= 0:
                st.warning(f'?? {sid2} 餈?4 摮?TTM EPS = {_cur_eps_pe:.2f} ???扳?嚗??祉?瘥摯?潔??拍??????P/B ?∪瘛典潭?瘝單???)
            else:
                # ?? 4. 閮?瘝單?撣塚??嚗???
                _band_pe_low  = (_ttm_eps_series * _pe_low).round(2)
                _band_pe_mid  = (_ttm_eps_series * _pe_mid).round(2)
                _band_pe_high = (_ttm_eps_series * _pe_high).round(2)
                _p_lo = float(_band_pe_low.dropna().iloc[-1])  if not _band_pe_low.dropna().empty  else 0
                _p_mi = float(_band_pe_mid.dropna().iloc[-1])  if not _band_pe_mid.dropna().empty  else 0
                _p_hi = float(_band_pe_high.dropna().iloc[-1]) if not _band_pe_high.dropna().empty else 0

                # ?? 5. 蝜芸? ??
                _fig_pe = go.Figure()
                _fig_pe.add_trace(go.Scatter(
                    x=_rdates_pe, y=_rclose_pe, name='?嗥??,
                    line=dict(color='#e6edf3', width=2.5),
                    hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>'))
                for _bs, _lbl_base, _last_val, _col in [
                    (_band_pe_low,  f'PE{_pe_low}靘踹?',  _p_lo, TRAFFIC_GREEN),
                    (_band_pe_mid,  f'PE{_pe_mid}??',  _p_mi, TRAFFIC_YELLOW),
                    (_band_pe_high, f'PE{_pe_high}?眼', _p_hi, TRAFFIC_RED),
                ]:
                    _lbl = f'{_lbl_base}:{_last_val:.0f}' if _last_val > 0 else _lbl_base
                    _fig_pe.add_trace(go.Scatter(
                        x=_rdates_pe, y=_bs, name=_lbl,
                        line=dict(color=_col, width=1.5, dash='dot'),
                        hovertemplate=f'{_lbl_base}: %{{y:.0f}}<extra></extra>'))
                if _p_lo > 0:
                    _fig_pe.add_hrect(y0=0, y1=_p_lo, fillcolor='rgba(63,185,80,0.07)', line_width=0)
                if _p_mi > _p_lo:
                    _fig_pe.add_hrect(y0=_p_lo, y1=_p_mi, fillcolor='rgba(210,153,34,0.07)', line_width=0)
                if _p_hi > _p_mi:
                    _fig_pe.add_hrect(y0=_p_mi, y1=_p_hi, fillcolor='rgba(248,81,73,0.05)', line_width=0)

                _all_pe_vals = (list(_rclose_pe.dropna())
                                + list(_band_pe_high.dropna()) + list(_band_pe_low.dropna()))
                _ymax_pe = max(_all_pe_vals) * 1.05 if _all_pe_vals else 100
                _ymin_pe = max(0, min(_all_pe_vals) * 0.7) if _all_pe_vals else 0

                _fig_pe.update_layout(
                    title=dict(
                        text=f'?? {sid2} {name2} ?祉?瘥眾瘚?嚗TM EPS {_cur_eps_pe:.2f}??? PE {_pe_low}/{_pe_mid}/{_pe_high}嚗?,
                        font=dict(color='#8b949e', size=12)),
                    height=300, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                    font=dict(color='white', size=11),
                    margin=dict(l=10, r=10, t=40, b=10),
                    xaxis=dict(gridcolor='#21262d'),
                    yaxis=dict(range=[_ymin_pe, _ymax_pe], gridcolor='#21262d'),
                    hovermode='x unified', showlegend=True,
                    legend=dict(orientation='h', y=1.08, x=0, font=dict(size=10)))
                st.plotly_chart(_fig_pe, width='stretch', config={'displayModeBar': False})

                _cur_pe_ratio = _cur_price_pe / _cur_eps_pe if _cur_eps_pe > 0 else 0
                _cur_zone_pe = ('? 靘踹??' if _cur_price_pe < _p_lo else
                                '? ???' if _cur_price_pe < _p_mi else
                                '? ?眼?' if _cur_price_pe < _p_hi else '??頞?鞎?)
                st.caption(
                    f'?桀?雿 {_cur_zone_pe}嚗??{_cur_price_pe:.0f} / '
                    f'PE{_pe_low}?廾_p_lo:.0f} / PE{_pe_mid}?廾_p_mi:.0f} / PE{_pe_high}?廾_p_hi:.0f}嚗'
                    f'TTM EPS {_cur_eps_pe:.2f}???嗅? PE ??{_cur_pe_ratio:.1f} ??)
        elif df2 is not None and not df2.empty:
            st.info(f'?對? {sid2} 摮? EPS 鞈?銝雲 4 摮???? {len(_eps_q_clean)} 摮??嚗瘜鼓鋆賣??瘝單???)

        # ?? 隡啣潭眾瘚?嚗B ?∪瘛典潭?瘝單?嚗?????????????????????????
        # v18.175 銝挾鞈?皞?chain嚗?
        #   PRIMARY:  TWSE BWIBBU_d ?游?? PBratio嚗撩?蝡臬??寞?憡潘?
        #             ??BPS ? = ?嗅??∪ / PBratio
        #   SECONDARY: FinMind TaiwanStockBalanceSheet 蝞?BPS = ?⊥甈?/(?⊥/10)
        #   FALLBACK:  yfinance bookValue
        # v18.175 璈怠葆?曉潭靘璆剖??隤踵嚗???0.5/0.9/1.2 /
        #   ?蝘? 1.5/2.5/4.0 / 鋆賡平 default 0.8/1.5/2.5
        _rdates_pb_pre = pd.to_datetime(
            df2['date'] if 'date' in df2.columns else pd.RangeIndex(len(df2)),
            errors='coerce').reset_index(drop=True) if df2 is not None else None
        _rclose_pb_pre = (pd.to_numeric(df2['close'], errors='coerce').reset_index(drop=True)
                          if df2 is not None and 'close' in df2.columns else None)
        _cur_price_pb_pre = (float(_rclose_pb_pre.dropna().iloc[-1])
                              if _rclose_pb_pre is not None and not _rclose_pb_pre.dropna().empty else 0.0)

        # PRIMARY: TWSE 摰 PBratio ??BPS ?
        _twse_pb = _fetch_pbratio_from_twse(sid2)
        _bps_val = 0.0
        _bps_source = ''
        if _twse_pb > 0 and _cur_price_pb_pre > 0:
            _bps_val = _cur_price_pb_pre / _twse_pb
            _bps_source = 'TWSE BWIBBU_d 摰 PBratio ?'
        else:
            # SECONDARY + FALLBACK: ?? _fetch_bps嚗inMind PRIMARY ??yfinance fallback嚗?
            _bps_val = _fetch_bps(sid2)
            if _bps_val > 0:
                _bps_source = 'FinMind TaiwanStockBalanceSheet 摮?漲 / yfinance bookValue'

        # ?Ｘ平?仿??
        _industry = _fetch_industry_category(sid2)
        _PB_LOW, _PB_MID, _PB_HIGH = _get_pb_bands(_industry)
        _industry_label = _pb_bands_label(_industry)

        if df2 is not None and not df2.empty and _bps_val > 0:
            _b_lo_pb = round(_bps_val * _PB_LOW, 2)
            _b_mi_pb = round(_bps_val * _PB_MID, 2)
            _b_hi_pb = round(_bps_val * _PB_HIGH, 2)

            _rdates_pb = _rdates_pb_pre if _rdates_pb_pre is not None else pd.to_datetime(
                df2['date'] if 'date' in df2.columns else pd.RangeIndex(len(df2)),
                errors='coerce').reset_index(drop=True)
            _rclose_pb = (_rclose_pb_pre if _rclose_pb_pre is not None
                          else pd.to_numeric(df2['close'], errors='coerce').reset_index(drop=True))

            _fig_pb = go.Figure()
            _fig_pb.add_trace(go.Scatter(
                x=_rdates_pb, y=_rclose_pb, name='?嗥??,
                line=dict(color='#e6edf3', width=2.5),
                hovertemplate='%{x|%Y-%m-%d}<br>%{y:.2f}<extra></extra>'))
            for _v_pb, _lbl_pb, _col_pb in [
                (_b_lo_pb, f'PB{_PB_LOW}靘踹?:{_b_lo_pb:.0f}',  TRAFFIC_GREEN),
                (_b_mi_pb, f'PB{_PB_MID}??:{_b_mi_pb:.0f}',  TRAFFIC_YELLOW),
                (_b_hi_pb, f'PB{_PB_HIGH}?眼:{_b_hi_pb:.0f}', TRAFFIC_RED),
            ]:
                _fig_pb.add_hline(y=_v_pb, line=dict(color=_col_pb, width=1.5, dash='dot'),
                                  annotation_text=_lbl_pb, annotation_position='right',
                                  annotation_font=dict(color=_col_pb, size=10))
            _fig_pb.add_hrect(y0=0, y1=_b_lo_pb, fillcolor='rgba(63,185,80,0.07)', line_width=0)
            _fig_pb.add_hrect(y0=_b_lo_pb, y1=_b_mi_pb, fillcolor='rgba(210,153,34,0.07)', line_width=0)
            _fig_pb.add_hrect(y0=_b_mi_pb, y1=_b_hi_pb, fillcolor='rgba(248,81,73,0.05)', line_width=0)

            _all_pb_vals = list(_rclose_pb.dropna()) + [_b_hi_pb, _b_lo_pb]
            _ymax_pb = max(_all_pb_vals) * 1.05 if _all_pb_vals else 100
            _ymin_pb = max(0, min(_all_pb_vals) * 0.7) if _all_pb_vals else 0
            _cur_price_pb = float(_rclose_pb.dropna().iloc[-1]) if not _rclose_pb.dropna().empty else 0
            # v18.175嚗??TWSE 摰 PBratio ?典??孵潘??血??芰?
            _cur_pb_ratio = _twse_pb if _twse_pb > 0 else (
                _cur_price_pb / _bps_val if _bps_val > 0 else 0)

            _fig_pb.update_layout(
                title=dict(
                    text=f'?? {sid2} {name2} ?∪瘛典潭?瘝單???BPS {_bps_val:.2f}??? PB {_PB_LOW}/{_PB_MID}/{_PB_HIGH} 繚 {_industry_label}嚗?,
                    font=dict(color='#8b949e', size=12)),
                height=280, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                font=dict(color='white', size=11),
                margin=dict(l=10, r=10, t=40, b=10),
                xaxis=dict(gridcolor='#21262d'),
                yaxis=dict(range=[_ymin_pb, _ymax_pb], gridcolor='#21262d'),
                hovermode='x unified', showlegend=False)
            st.plotly_chart(_fig_pb, width='stretch', config={'displayModeBar': False})

            _cur_zone_pb = ('? 靘踹??' if _cur_price_pb < _b_lo_pb else
                            '? ???' if _cur_price_pb < _b_mi_pb else
                            '? ?眼?' if _cur_price_pb < _b_hi_pb else '??頞?鞎?)
            st.caption(
                f'?桀?雿 {_cur_zone_pb}嚗??{_cur_price_pb:.0f} / '
                f'PB{_PB_LOW}?廾_b_lo_pb:.0f} / PB{_PB_MID}?廾_b_mi_pb:.0f} / PB{_PB_HIGH}?廾_b_hi_pb:.0f}嚗'
                f'BPS {_bps_val:.2f}???嗅? PB ??{_cur_pb_ratio:.2f} ??)
            st.info(
                f'?對? **P/B 鞈?皞?*嚗_bps_source}嚗18.175 銝挾 chain嚗WSE BWIBBU_d ??FinMind BS ??yfinance嚗? \n'
                f'**BPS ?砍?**嚗?望??蜇憿?繩 瘚憭?賂?= ?桅?⊥ 繩 10 ?憿?嚗???TWSE 摰 PBratio ?嚗PS = ?∪ / PBratio嚗? \n'
                f'**?曉潔???*嚗_industry_label} ??PB {_PB_LOW}/{_PB_MID}/{_PB_HIGH}嚗18.175 ?Ｘ平?亙????? 0.5/0.9/1.2 / ?蝘? 1.5/2.5/4.0 / 鋆賡平 0.8/1.5/2.5嚗???啣潔?璈怠葆嚗?? rolling嚗?
            )
        elif df2 is not None and not df2.empty:
            st.caption('?對? ?∪瘛典潭?瘝單???TWSE/FinMind/yfinance 銝楝敺???BPS 鞈?嚗歲??)

        # ?? C. ???? ????????????????????????????????????????
        st.markdown('---')
        st.markdown('#### ? C. ?砍???刻竟?Ｗ?嚗?鞎∪????嚗?)
        if cl2 and cl2 > 0 and cx2 and cx2 > 0:
            _ca = f'??鞎 {cl2/1e8:.1f}??+ 鞈?臬 {cx2/1e8:.1f}????蝣箄?樴???
            _cb = '?箸?Ｗ撥?ｇ??拙??瑟???'
        elif cl2 and cl2 > 0:
            _ca = f'??鞎 {cl2/1e8:.1f}??閮鞊?嚗?鞈?臬鞈?銝雲'
            _cb = '?箸?Ｚ憟踝?雿撱?憿?蝣箄?'
        elif cx2 and cx2 > 0:
            _ca = f'鞈?臬 {cx2/1e8:.1f}??蝛扔?渡嚗???鞎鞈?銝雲'
            _cb = '?游???撘瘀?雿??株閬漲敺Ⅱ隤?
        else:
            _ca = '??鞎+鞈?臬?鞈?嚗?賜???⊥?鞈?皞??塚?'
            _cb = '隢 MOPS ?僑?望??
        st.markdown(teacher_conclusion('摮急樴?, f'{sid2} 鞎∪????', _ca, _cb), unsafe_allow_html=True)
        st.markdown(
            '<div style="background:#0a1628;border-left:3px solid #bc8cff;padding:8px 12px;'
            'border-radius:0 6px 6px 0;margin-bottom:8px;font-size:12px;color:#c9d1d9;">'
            '? ??瓷?望摮?葫?芯?3-6????拇??'
            '<br>?? <b>??鞎</b> = 摰Ｘ撌脖??Ｖ????箄疏??????頞?隞?”閮敺??平蝮暹?靽?'
            '<br>?? <b>鞈?臬</b> = ?砍?梢???輯眺閮剖? ??頞?隞?”?末?芯????之撟??
            '<br>潃??拙敺? = 蝑1?隤芰???憭???臬??⊿???
            '</div>', unsafe_allow_html=True)
        fc1,fc2=st.columns(2)
        cl_ok=cl2 is not None and cl2>0
        cx_ok=cx2 is not None and cx2>0
        _cl_st = _fin_st2.get('contract_liabilities') if '_fin_st2' in dir() else None  # noqa: F821
        _cx_st = _fin_st2.get('fixed_assets')         if '_fin_st2' in dir() else None  # noqa: F821
        _cl_label = "--" if cl_ok else '?⊥??
        _cx_label = "--" if cx_ok else '?⊥??
        _cl_color_map = {'ok':TRAFFIC_GREEN,'missing':TRAFFIC_YELLOW,'not_applicable':'#484f58','fetch_error':TRAFFIC_RED}
        _cx_color_map = {'ok':'#58a6ff','missing':TRAFFIC_YELLOW,'not_applicable':'#484f58','fetch_error':TRAFFIC_RED}
        with fc1:
            _cl_val_txt = f'{cl2/1e8:.1f}?? if cl_ok else '??憭望?'
            _cl_c = '#2ea043' if cl_ok else '#da3633'
            st.markdown(kpi('??鞎', _cl_val_txt,
                            '>?⊥50%?靘?-6???桐???, _cl_c,
                            _cl_c if cl_ok else '#21262d'),unsafe_allow_html=True)
            if not cl_ok:
                st.caption('靘?嚗inMind ????憭望??甇方瓷??)
        with fc2:
            _cx_val_txt = f'{cx2/1e8:.1f}?? if cx_ok else '??憭望?'
            _cx_c = '#2ea043' if cx_ok else '#da3633'
            st.markdown(kpi('?箏?鞈/鞈?臬', _cx_val_txt,
                            '>?⊥80%?之?游??末?芯??瘙?, _cx_c,
                            _cx_c if cx_ok else '#21262d'),unsafe_allow_html=True)
            if not cx_ok:
                st.caption(f'靘?嚗_cl_src2 or _cx_src2 or "?芰"}')
        if not cl_ok and not cx_ok:
            _na = (not _fin_errs2 and not cl_ok and not cx_ok)
            _fe = bool(_fin_errs2)
            if _na:
                st.info('?對? 甇斤璆哨???/靽蝑?銝?典?蝝????箏?鞈??嚗頝喲?')
            elif _fe:
                # 憿舐內?琿??航炊蝯虫蝙?刻?
                _err_src = (_cl_src2 + '/' + _cx_src2).strip('/')
                _err_msg = '; '.join(_fin_errs2) if _fin_errs2 else '??憭望?'
                st.error(f'??鞎∪鞈???憭望? ??靘?:{_err_src or "銝???賭葉"} | ?航炊:{_err_msg}')
                st.caption('? ?航??嚗? FinMind Token 憭望? ??MOPS ?急??∪???????⊥迨鞎∪')
            else:
                st.info('?對? ?亦?剝嚗??平/頠?璆剝虜?⊥迨?豢?嚗頝喲?')
                st.caption(f'靘?嚗_cl_src2 or _cx_src2 or "?芰"}')
        # 鞎∪蝯?嚗???鞎+?箏?鞈??策?箏??
        _fin_color = TRAFFIC_GREEN if cl_ok and cx_ok else (TRAFFIC_YELLOW if cl_ok or cx_ok else '#484f58')
        _fin_label = ('??樴?蝣箄?嚗?蝝??菟?嚗??祆?粹? = 閮皛踴撱葉' if cl_ok and cx_ok
                      else ('?? ?典?閮?嚗? + ('??鞎??' if cl_ok else '鞈?臬蝛扔')
                            if cl_ok or cx_ok else '??鞈?銝雲嚗瘜??))
        st.markdown(
            f'<div style="background:#0d1117;border-left:4px solid {_fin_color};'
            f'padding:10px 14px;border-radius:0 8px 8px 0;margin:6px 0;">'
            f'<span style="font-size:12px;color:#8b949e;">?? 蝑1 繚 鞎∪????</span><br>'
            f'<span style="font-size:14px;font-weight:800;color:{_fin_color};">{_fin_label}</span><br>'
            f'<span style="font-size:11px;color:#8b949e;">?拇?璅?擃?= 樴??⊿??賂?閰喟敦?瑼餉????交??ab</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        # ?? D. ????+ 摮???拍? ??????????????????????????????
        st.markdown('---')
        st.markdown('#### ?? D. ?砍瘥?鞈箏?撠嚗??頞典嚗?)
        _d_ind = f'{sid2} ???跎oY%'
        _da = '???嗆???芾???
        _db = ''
        if rev2 is not None and not rev2.empty and len(rev2) >= 3:
            _yoy_col = next((c for c in rev2.columns if 'yoy' in str(c).lower() or '撟游?' in str(c) or 'YoY' in str(c)), None)
            if _yoy_col:
                _yoy3 = pd.to_numeric(rev2[_yoy_col].tail(3), errors='coerce').dropna()
                if len(_yoy3) >= 2:
                    _avg_y = float(_yoy3.mean())
                    _last_y = float(_yoy3.iloc[-1])
                    _d_ind = f'{sid2} 餈??像?oY {_avg_y:+.1f}%'
                    if _avg_y > 15 and (_yoy3 > 0).all():
                        _da = f'餈??oY撟喳? {_avg_y:+.1f}%嚗???{_last_y:+.1f}%嚗?璆剔蜀?嚗?暺?瘜?
                        _db = '???銵鞎琿??舫脣'
                    elif _avg_y > 0:
                        _da = f'餈??oY撟喳? {_avg_y:+.1f}%嚗澈????
                        _db = '??餈質馱嚗?敺??楚鞊?
                    else:
                        _da = f'餈??oY撟喳? {_avg_y:+.1f}%嚗平蝮曇※?'
                        _db = '銝恣K蝺?憟賜?嚗?閫??
        st.markdown(teacher_conclusion('摮急樴?, _d_ind, _da, _db), unsafe_allow_html=True)
        st.markdown(
            f'<div style="background:#0a1628;border-left:3px solid {TRAFFIC_GREEN};padding:8px 12px;'
            'border-radius:0 6px 6px 0;margin-bottom:8px;font-size:12px;color:#c9d1d9;">'
            '? ???嗅僑憓?嚗oY%嚗? 隞僑??瘥撟游???鞈箔?撟?'
            '<br>? <b>???3??YoY>15%</b> = 璆剔蜀?嚗?孵?質??撞'
            '<br>? <b>???3??YoY<0%</b> = 璆剔蜀銵圈嚗?撠?'
            '</div>', unsafe_allow_html=True)
        if rev2 is not None and not rev2.empty:
            if _rev2_cached:
                st.caption('?? ???嗡蝙?典翰?????祆活 API ?芸???')
            st.plotly_chart(plot_revenue_chart(rev2,sid2,name2),
                            width='stretch',config={'displayModeBar':False})
        else:
            st.warning('?? ???嗆??∴?隢Ⅱ隤?FINMIND_TOKEN ?臬甇?Ⅱ嚗??頛嚗?)
            st.caption('? 擐活?亥岷?蝬脰楝??嚗??憭望?隢炎??Token ??敺?閰?)
        if qtr2 is not None and not qtr2.empty:
            if _qtr2_cached:
                st.caption('?? 摮?瓷?曹蝙?典翰?????祆活 API ?芸???')
            st.plotly_chart(plot_quarterly_chart(qtr2,sid2,name2),
                            width='stretch',config={'displayModeBar':False})
        with st.expander('?? 蝑1 蝯?', expanded=True):
            if rev2 is not None and not rev2.empty and 'yoy' in rev2.columns:
                _yoy_last3 = rev2['yoy'].dropna().tail(3).tolist()
                if len(_yoy_last3) >= 2:
                    _yoy_trend = all(_yoy_last3[i] > _yoy_last3[i-1] for i in range(1,len(_yoy_last3)))
                    _yoy_latest = _yoy_last3[-1]
                    _rev_signal = '?????跎oY????? if _yoy_trend and _yoy_latest>0 else ('?? ???嗆??瑁隅蝺? if _yoy_latest>0 else '? ???嗅僑皜?)
                    st.markdown(f'<div style="color:#c9d1d9;font-size:13px;padding:3px 0;">??{_rev_signal}嚗?餈oY: {_yoy_latest:+.1f}%嚗?/div>', unsafe_allow_html=True)
            # ???嗥?隢?蝘餃 if ?改??踹? _rev_signal ?芸?蝢抬?
            if rev2 is not None and not rev2.empty and 'yoy' in rev2.columns:
                _yoy_s2 = rev2['yoy'].dropna().tail(3).tolist()
                if _yoy_s2:
                    _rv_latest = _yoy_s2[-1]
                    _rv_trend  = len(_yoy_s2)>=2 and all(_yoy_s2[i]>_yoy_s2[i-1] for i in range(1,len(_yoy_s2)))
                    _rv_sig = ('?????跎oY????? if _rv_trend and _rv_latest>0
                               else ('?? ???嗆??瑁隅蝺? if _rv_latest>0 else '? ???嗅僑皜?))
                    _rv_c = TRAFFIC_GREEN if '?? in _rv_sig else (TRAFFIC_RED if '?' in _rv_sig else TRAFFIC_YELLOW)
                    st.markdown(
                        f'<div style="background:#0d1117;border-left:3px solid {_rv_c};padding:7px 12px;border-radius:0 6px 6px 0;margin:4px 0;">'
                        f'<span style="font-size:11px;color:#8b949e;">?? 蝑1 繚 ????/span>?'
                        f'<span style="font-size:13px;font-weight:700;color:{_rv_c};">{_rv_sig}嚗oY:{_rv_latest:+.1f}%嚗?/span>'
                        f'</div>', unsafe_allow_html=True
                    )
                else:
                    st.caption('???嗉???頞喉??⊥??斗頞典')
            else:
                st.caption('?? ???嗉??撩憭梧?隢Ⅱ隤?FinMind Token嚗?)
            # 瘥??隢?+ ?脣?釭敺? (SQ)
            if qtr2 is not None and not qtr2.empty:
                _gp_col = '瘥?? if '瘥?? in qtr2.columns else None  # 蝎曄Ⅱ瘥?嚗?銝?瘥??蝔?
                if _gp_col:
                    import pandas as _pd_gp
                    _gp_series = _pd_gp.to_numeric(qtr2[_gp_col].tail(4), errors='coerce').dropna()
                    if len(_gp_series) >= 2:
                        _gp_now = float(_gp_series.iloc[-1])
                        _gp_trend = float(_gp_series.iloc[-1]) - float(_gp_series.iloc[-2])
                        _gp_c = TRAFFIC_GREEN if _gp_now >= 30 and _gp_trend >= 0 else (TRAFFIC_YELLOW if _gp_now >= 20 else TRAFFIC_RED)
                        _gp_msg = (f'??{_gp_now:.1f}%嚗?瘥??0%嚗風?眾撖穿?' if _gp_now >= 30
                                   else f'?? {_gp_now:.1f}%嚗葉蝑???0~30%嚗? if _gp_now >= 20
                                   else f'? {_gp_now:.1f}%嚗?瘥<20%嚗?)
                        st.markdown(
                            f'<div style="background:#0d1117;border-left:3px solid {_gp_c};padding:7px 12px;border-radius:0 6px 6px 0;margin:4px 0;">'
                            f'<span style="font-size:11px;color:#8b949e;">?? ?喲???繚 瘥??/span>?'
                            f'<span style="font-size:13px;font-weight:700;color:{_gp_c};">{_gp_msg}</span>'
                            f'</div>', unsafe_allow_html=True
                        )
                # ?脣?釭敺? (SQ)
                try:
                    from scoring_engine import calc_quality_score as _cqs
                    _sq_res = _cqs(qtr2)
                    if _sq_res.get('sq') is not None:
                        _sq_v = _sq_res['sq']
                        _sq_lbl = _sq_res['sq_label']
                        _sq_gm = _sq_res['gm_trend']
                        _sq_rv = _sq_res['rev_trend']
                        _sq_c  = TRAFFIC_GREEN if _sq_v >= 75 else (TRAFFIC_YELLOW if _sq_v >= 55 else TRAFFIC_RED)
                        st.markdown(
                            f'<div style="background:#0d1117;border-left:3px solid {_sq_c};padding:7px 12px;border-radius:0 6px 6px 0;margin:4px 0;">'
                            f'<span style="font-size:11px;color:#8b949e;">?? ?脣?釭 SQ</span>?'
                            f'<span style="font-size:13px;font-weight:700;color:{_sq_c};">SQ {_sq_v:.0f}??繚 {_sq_lbl}</span>'
                            f'<span style="font-size:11px;color:#8b949e;margin-left:8px;">瘥{_sq_gm} ?{_sq_rv}</span>'
                            f'</div>', unsafe_allow_html=True
                        )
                except Exception:
                    pass
                # ???? (FGMS)
                try:
                    from scoring_engine import calc_forward_momentum_score as _cfgms
                    _is_fin2 = bool(qtr2.get('?臬????, pd.Series([False])).iloc[0]) if qtr2 is not None and '?臬???? in qtr2.columns else False
                    print(f'[FGMS_UI] qtr2={qtr2 is not None and not qtr2.empty}, qtr_extra2={qtr_extra2 is not None and not qtr_extra2.empty}')
                    _fgms_r = _cfgms(qtr2, qtr_extra2, is_finance=_is_fin2)
                    print(f'[FGMS_UI] fgms={_fgms_r.get("fgms")}, three_rate={_fgms_r.get("three_rate")}')
                    if _fgms_r.get('fgms') is not None:
                        _fv = _fgms_r['fgms']
                        _fl = _fgms_r['fgms_label']
                        _fc = TRAFFIC_GREEN if _fv >= 60 else (TRAFFIC_YELLOW if _fv >= 45 else TRAFFIC_RED)
                        # 摮雁摨行?閬?敺?嚗?
                        _fd_parts = []
                        if _fgms_r['cl_momentum']    is not None:
                            _fd_parts.append(f"??鞎:{_fgms_r['cl_momentum']:.0f}")
                        if _fgms_r['inv_divergence']  is not None:
                            _fd_parts.append(f"摮疏?:{_fgms_r['inv_divergence']:.0f}")
                        if _fgms_r['three_rate']      is not None:
                            _fd_parts.append(f"銝?:{_fgms_r['three_rate']:.0f}")
                        if _fgms_r['capex_intensity'] is not None:
                            _fd_parts.append(f"鞈?臬:{_fgms_r['capex_intensity']:.0f}")
                        _fd_str = '  '.join(_fd_parts)
                        # 銝?撖阡??詨潘???啣迤嚗?
                        _rate_parts = []
                        if qtr2 is not None and not qtr2.empty:
                            def _last_rate(col):
                                if col in qtr2.columns:
                                    _s = pd.to_numeric(qtr2[col], errors='coerce').dropna()
                                    return f"{_s.iloc[-1]:.1f}%" if len(_s) else None
                                return None
                            _gm_v = _last_rate('瘥??)
                            _oi_v = _last_rate('?平?拍???)
                            _ni_v = _last_rate('瘛典??)
                            if _gm_v:
                                _rate_parts.append(f"瘥?_gm_v}")
                            if _oi_v:
                                _rate_parts.append(f"?平?拍??_oi_v}")
                            if _ni_v:
                                _rate_parts.append(f"瘛典?_ni_v}")
                        _rate_str = '  '.join(_rate_parts)
                        _rate_line = (f'<div style="font-size:11px;color:#8b949e;margin-top:3px;">?? 銝?撖血潘?{_rate_str}</div>'
                                      if _rate_str else '')
                        st.markdown(
                            f'<div style="background:#0d1117;border-left:3px solid {_fc};padding:7px 12px;border-radius:0 6px 6px 0;margin:4px 0;">'
                            f'<span style="font-size:11px;color:#8b949e;">? ?? FGMS</span>?'
                            f'<span style="font-size:13px;font-weight:700;color:{_fc};">FGMS {_fv:.0f}??繚 {_fl}</span>'
                            f'<span style="font-size:11px;color:#8b949e;margin-left:8px;">{_fd_str}</span>'
                            f'{_rate_line}'
                            f'</div>', unsafe_allow_html=True
                        )
                except Exception as _efgms2:
                    import traceback as _tb2
                    print(f'[FGMS_UI] 憿舐內?航炊: {_efgms2}')
                    _tb2.print_exc()

        # ?? D2. ?箸?Ｗ?銵?璅?6憭扳?璅???????????????????????
        st.markdown('---')
        st.markdown('#### ? D2. ?箸?Ｗ?銵?璅?6憭扳?璅?')
        try:
            from scoring_engine import calc_leading_indicators_detail as _cli_fn
            _li_results = _cli_fn(rev_df=rev2, qtr_df=qtr2, bs_cf_df=qtr_extra2)
            _li_green = sum(1 for _r in _li_results if _r['signal'] == '?')
            _li_yellow = sum(1 for _r in _li_results if _r['signal'] == '?')
            _li_red = sum(1 for _r in _li_results if _r['signal'] == '?')
            _li_total_scored = _li_green + _li_yellow + _li_red
            if _li_total_scored > 0:
                _li_bar_c = TRAFFIC_GREEN if _li_green >= _li_total_scored * 0.6 else (
                             TRAFFIC_YELLOW if _li_green >= _li_total_scored * 0.3 else TRAFFIC_RED)
                st.markdown(
                    f'<div style="background:#0d1117;border-left:3px solid {_li_bar_c};'
                    f'padding:6px 12px;border-radius:0 6px 6px 0;margin:4px 0 8px 0;">'
                    f'<span style="font-size:11px;color:#8b949e;">?? ?箸?Ｗ?銵?璅蜇閬?/span>?'
                    f'<span style="font-size:13px;font-weight:700;color:{_li_bar_c};">'
                    f'??{_li_green}  ??{_li_yellow}  ??{_li_red}</span>'
                    f'</div>', unsafe_allow_html=True
                )
            # ?芋蝯＊蝷?
            _li_modules = {}
            for _r in _li_results:
                _li_modules.setdefault(_r['module'], []).append(_r)
            _li_module_list = ['璅∠?銝', '璅∠?鈭?, '璅∠?銝?, '璅∠???]
            _li_module_labels = {
                '璅∠?銝': '?? 璅∠?銝嚗??餅平蝮曉??鳴????塚?',
                '璅∠?鈭?: '??儭?璅∠?鈭?鞈鞎?嚗迤?鳴?',
                '璅∠?銝?: '? 璅∠?銝?摮疏?望?',
                '璅∠???: '?? 璅∠???蝐Ⅳ瘛勗漲?',
            }
            _li_col1, _li_col2 = st.columns(2)
            _li_cols = [_li_col1, _li_col2]
            _li_col_idx = 0
            for _mod in _li_module_list:
                if _mod not in _li_modules:
                    continue
                with _li_cols[_li_col_idx % 2]:
                    st.markdown(f'**{_li_module_labels.get(_mod, _mod)}**')
                    for _ind in _li_modules[_mod]:
                        _ic = (TRAFFIC_GREEN if _ind['signal'] == '?' else
                               TRAFFIC_YELLOW if _ind['signal'] == '?' else
                               TRAFFIC_RED if _ind['signal'] == '?' else '#8b949e')
                        st.markdown(
                            f'<div style="background:#0d1117;border-left:3px solid {_ic};'
                            f'padding:6px 10px;border-radius:0 4px 4px 0;margin:3px 0;">'
                            f'<div style="font-size:12px;font-weight:700;color:{_ic};">'
                            f'{_ind["signal"]} {_ind["name"]}</div>'
                            f'<div style="font-size:11px;color:#e6edf3;margin:1px 0;">{_ind["value"]}</div>'
                            f'<div style="font-size:10px;color:#8b949e;">{_ind["detail"]}</div>'
                            f'</div>', unsafe_allow_html=True
                        )
                _li_col_idx += 1
        except Exception as _eli_err:
            import traceback as _li_tb
            print(f'[????-D2] 憿舐內?航炊: {_eli_err}')
            _li_tb.print_exc()

        # ?? D2 ????撱箄降嚗??憭批?銵?璅?????????????????
        try:
            from scoring_engine import calc_leading_indicators_detail as _cli_fn2
            _li2 = _cli_fn2(rev_df=rev2, qtr_df=qtr2, bs_cf_df=qtr_extra2)
            _li2_map = {r['id']: r for r in _li2}

            # ?? ??靽∟? ?????????????????????????????????????
            _pros  = []   # 憭?
            _cons  = []   # 蝛箸?
            _notes = []   # 瘜冽?鈭?嚗?隞園???銝剜改?
            _event_driven_flags = []

            # I1 ???跎oY??
            _r1 = _li2_map.get('I1', {})
            if _r1.get('signal') == '?':
                _pros.append(f"???跎oY?????{_r1.get('value','').split(':')[-1].strip()}嚗?璆剔蜀?蝣箇?")
            elif _r1.get('signal') == '?':
                _cons.append('???嗅僑皜葉嚗?祇韏啣摹')

            # I2 ??鈭文?
            _r2 = _li2_map.get('I2', {})
            if _r2.get('signal') == '?':
                _pros.append(f"????M??雿12M??銋?嚗_r2.get('value','').split(':')[-1].strip()}嚗?銝剜????")
            elif _r2.get('signal') == '?':
                _cons.append('???嗅?蝺香??銝剜?頞典頧摹')

            # I3 ??鞎
            _r3 = _li2_map.get('I3', {})
            if _r3.get('signal') == '?':
                _v3 = _r3.get('value','')
                _pros.append(f"??鞎??憓?嚗_v3}嚗??芯???質?摨阡?")
            elif _r3.get('signal') == '?':
                _cons.append('??鞎皜?嚗??株閬漲銝?')

            # I4 CapEx嚗鈭辣撽??斗嚗?
            _r4 = _li2_map.get('I4', {})
            if '鈭辣撽?' in _r4.get('detail', ''):
                _event_driven_flags.append('鞈?臬瘥??箸???憭扯??Ｚ??仃??)
                _notes.append(f"?? CapEx嚗_r4.get('detail','')}")
            elif _r4.get('signal') == '?':
                _pros.append(f"鞈?臬撘瑕漲??嚗_r4.get('value','')}嚗?蝛扔?渡雿??芯?")
            elif _r4.get('signal') == '?':
                _cons.append(f"鞈?臬憭批?蝮格?嚗_r4.get('value','')}嚗??游撐??雿?)

            # I5 摮疏?餃?嚗鈭辣撽?嚗?
            _r5 = _li2_map.get('I5', {})
            if '鈭辣撽?' in _r5.get('detail', ''):
                _event_driven_flags.append('摮疏?仿???敺Ⅱ隤?鞈???航撣嗉粥摮疏嚗?)
                _notes.append(f"?? 摮疏嚗_r5.get('detail','')}")
            elif _r5.get('signal') == '?':
                _pros.append(f"摮疏???餃?嚗_r5.get('value','')}嚗?靘????孵?")
            elif _r5.get('signal') == '?':
                _cons.append(f"摮疏蝛?憸券嚗_r5.get('value','')}嚗??舀除銝?憯?")

            # ?? 蝬?閰摯 ????????????????????????????????????
            _n_green = sum(1 for r in _li2 if r['signal'] == '?')
            _n_red   = sum(1 for r in _li2 if r['signal'] == '?')
            _n_scored = sum(1 for r in _li2 if r['signal'] in ('?','?','?'))

            if _event_driven_flags:
                _stance = 'event'
                _stance_label = '?? 鈭辣撽?閫撖?
                _stance_color = TRAFFIC_YELLOW
                _stance_desc  = '?菜葫?圈?憭扯??Ｚ????典????箸?憭梁??遣霅圈?瘜券?蝯????祇?蝵格??????蝭憟??思??拍蝝?祇?獢閰摯??
            elif _n_scored == 0:
                _stance = 'na'
                _stance_label = '??鞈?銝雲'
                _stance_color = '#8b949e'
                _stance_desc  = '?箸?Ｗ?銵?璅????芸??渲??伐??⊥?????撱箄降??
            elif _n_green >= _n_scored * 0.6:
                _stance = 'bull'
                _stance_label = '? 憭??'
                _stance_color = TRAFFIC_GREEN
                _stance_desc  = f'{_n_green}/{_n_scored} ??璅?憭??箸?Ｗ??賢撥??
            elif _n_red >= _n_scored * 0.6:
                _stance = 'bear'
                _stance_label = '? ?箸?Ｗ?撘?
                _stance_color = TRAFFIC_RED
                _stance_desc  = f'{_n_red}/{_n_scored} ??璅?蝛綽??箸?Ｗ???憿胯?
            else:
                _stance = 'neutral'
                _stance_label = '? 銝剜扯?撖?
                _stance_color = TRAFFIC_YELLOW
                _stance_desc  = f'憭征??鈭日嚗?┐_n_green}/?{_n_red}嚗??箸?Ｗ??芸耦??蝣箸??

            # ?? 撱箄降銵? ????????????????????????????????????
            _action_map = {
                'bull':    '?箸?Ｗ??賢?銝??舀??銵嚗CP/撣?嚗Ⅱ隤脣??嚗?葉?瑞?雿???,
                'bear':    '?箸?Ｗ??曉???撱箄降???????蝑???頧?敺?閰摯??,
                'neutral': '?箸?Ｘ??銝???撱箄降頛?蝑??游?摮?漲?豢?蝣箄?敺?銵???,
                'event':   '頧??⊿?餈質馱嚗?敺?鞈?臬?遣蝭憟??⊥璆剖?嚗?HBM敺挾嚗??株閬漲 ?Ｘ??拍??臬???單迤撣豢偌雿?,
                'na':      '隢Ⅱ隤?FINMIND_TOKEN ?臬甇?Ⅱ嚗蒂?頛敺?遣霅啜?,
            }
            _action = _action_map.get(_stance, '')

            # ?? 皜脫? ????????????????????????????????????????
            _pros_html  = ''.join(f'<li style="margin:2px 0;">??{p}</li>' for p in _pros)  if _pros  else ''
            _cons_html  = ''.join(f'<li style="margin:2px 0;">??{c}</li>' for c in _cons)  if _cons  else ''
            _notes_html = ''.join(f'<li style="margin:2px 0;">{n}</li>'    for n in _notes) if _notes else ''

            _pros_section  = (f'<div style="margin-top:6px;"><span style="font-size:11px;color:{TRAFFIC_GREEN};font-weight:600;">憭??</span>'
                              f'<ul style="margin:2px 0 0 12px;padding:0;font-size:11px;color:#e6edf3;">{_pros_html}</ul></div>') if _pros_html else ''
            _cons_section  = (f'<div style="margin-top:4px;"><span style="font-size:11px;color:{TRAFFIC_RED};font-weight:600;">憸券??</span>'
                              f'<ul style="margin:2px 0 0 12px;padding:0;font-size:11px;color:#e6edf3;">{_cons_html}</ul></div>') if _cons_html else ''
            _notes_section = (f'<div style="margin-top:4px;"><span style="font-size:11px;color:{TRAFFIC_YELLOW};font-weight:600;">瘜冽?鈭?</span>'
                              f'<ul style="margin:2px 0 0 12px;padding:0;font-size:11px;color:#8b949e;">{_notes_html}</ul></div>') if _notes_html else ''

            st.markdown(
                f'<div style="background:#161b22;border:1px solid {_stance_color};border-left:4px solid {_stance_color};'
                f'padding:10px 14px;border-radius:6px;margin:8px 0;">'
                f'<div style="font-size:12px;color:#8b949e;margin-bottom:4px;">? ?箸?Ｗ?銵?璅?繚 ????撱箄降</div>'
                f'<div style="font-size:15px;font-weight:700;color:{_stance_color};">{_stance_label}</div>'
                f'<div style="font-size:12px;color:#e6edf3;margin-top:4px;">{_stance_desc}</div>'
                f'{_pros_section}{_cons_section}{_notes_section}'
                f'<div style="margin-top:8px;padding-top:6px;border-top:1px solid #30363d;">'
                f'<span style="font-size:11px;color:#8b949e;">?? 撱箄降銵?嚗?/span>'
                f'<span style="font-size:12px;color:#e6edf3;">{_action}</span>'
                f'</div>'
                f'</div>', unsafe_allow_html=True
            )
        except Exception as _eli2_err:
            import traceback as _li2_tb
            print(f'[????-撱箄降] 憿舐內?航炊: {_eli2_err}')
            _li2_tb.print_exc()

        # ?? 鞈?敶嚗? AI 蝮賜?雿輻嚗??????????????????????????
        _regime2 = st.session_state.get('mkt_info', {}).get('regime', 'neutral')
        _rev_yoy_list = []
        if rev2 is not None and not rev2.empty and 'yoy' in rev2.columns:
            # P4b: vectorized ??撠? date/index 敺?甈?apply
            _r3 = rev2.tail(3).copy()
            _r3['_lbl'] = _r3['date'].astype(str) if 'date' in _r3.columns else _r3.index.astype(str)
            _rev_yoy_list = [
                f'{lbl}: {yoy:+.1f}%'
                for lbl, yoy in zip(_r3['_lbl'], pd.to_numeric(_r3['yoy'], errors='coerce'))
                if not pd.isna(yoy)
            ]
        _vcp_ok2 = bool(vcp2 and isinstance(vcp2, dict) and vcp2.get('signal'))
        _ma_above2 = {}
        if df2 is not None and not df2.empty:
            for _mn, _mc in [('20MA', 'MA20'), ('60MA', 'MA60'), ('240MA', 'MA240')]:
                if _mc in df2.columns:
                    _ma_above2[_mn] = price2 > float(df2[_mc].iloc[-1])

        st.markdown("""<div style="margin:24px 0 8px;padding:8px 16px;background:linear-gradient(90deg,#d2a8ff18,#0d1117);border-left:4px solid #d2a8ff;border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:#d2a8ff;">? 擃炎銵?/span><span style="font-size:11px;color:#8b949e;margin-left:8px;">蝑2 繚 4??璉? 繚 ?暸?瘚??繚 OPM霅瑕?瘝?/span></div>""", unsafe_allow_html=True)

        # ?? ? ???閰梧?鞎∪??敹急嚗???嚗?券?瑼?expander 憭??踹?撌Ｙ?嚗??
        with st.expander('? ??銝??鞎∪??嚗????30 蝘?'):
            st.markdown('''銝?I 鞎∪擃炎?? MJ嚗???嚗瓷?勗????塚????質店撠嚗?

| ?? | ?質店??|
|---|---|
| **瘞?銝**嚗??> 蝮質???25%嚗?| ?砍???暸?憭?憭?嚗??嚗除?瑯?敺????頧???|
| **???脣 / OCF**嚗?璆剔???箸迤嚗?| 撣喃?鞈粹??????啁??OCF ?箸迤??竟嚗董?Ｚ竟?餅??嗅?暸?嚗?*暺??渡**憸券 |
| **??璉?**嚗??菜? < 60%嚗?| ?砍甈??靘?頞?頞帘嚗?60% 隞?”瑽▼?? |
| **?刻???** | 鞈?疏?撣喟??漲嚗?敹恬?鞈?頞暑???∪澈摮??董 |
| **隞仿?舫** | ?具???Ｕ??⊥嚗?狡嚗眺????Ｕ?撱閮剖?嚗?瘥?憭?銝??剖擗?頧???|
| **MJ 300 / 150** | MJ ??潭?皞?瘚?瘥? >300%??瘥? >150%嚗???菟?鋆之嚗?曇?璆剜??暸??雲???曉祝?瑼鳴????賜泵?? |
| **頝刻”?曄里 + ?圈** | ???”嚗??Ｚ??菔”嚗???”銝撐銵其漱??撽??芸????????瑁???|

> ? ??嚗??摰???瘜冽?????梢?遙銝?香??鈭桃?????瘛梁弦???捱摰?銝?蝣啜?'')

        with st.expander('? AI 鞎∪擃炎嚗???嚗?, expanded=True):
            _fh_key2 = f'_fh_{sid2}'
            if _fh_key2 not in st.session_state:
                with st.spinner('?? 甇?敺?FinMind ??鞎∪?豢???):
                    try:
                        _fin_raw = fetch_financial_statements(sid2, FINMIND_TOKEN)
                        if _fin_raw.get('error'):
                            st.session_state[_fh_key2] = {'error': True, 'ai_insight': _fin_raw['error']}
                        else:
                            # B???‵ 5 撟渡?????嗆???蝎曄Ⅱ??
                            try:
                                from tw_stock_data_fetcher import fetch_5_years_cash_flow
                                _fin_raw['b_item_5y'] = fetch_5_years_cash_flow(sid2, FINMIND_TOKEN)
                            except Exception:
                                pass  # fallback ??1Q 隡啁?
                            # 餈??啗?嚗? MJ 擃炎 AI insight 蝯?撣??
                            _mj_news = _fetch_stock_news(sid2, name2, 3)
                            _mj_news_str = '\n'.join(
                                f'- {_n["title"]}嚗_n.get("source","RSS")} 繚 {_n.get("published","")}嚗?
                                for _n in _mj_news
                            ) if _mj_news else '嚗?∟???啗?嚗?
                            _fh_out = analyze_financial_health(api_key, sid2, _fin_raw,
                                                               news_context=_mj_news_str)
                            st.session_state[_fh_key2] = _fh_out
                            # 靽???鞎∪?豢?靘那?琿?蹂蝙?剁?ar_days/liab/b_item_5y 蝑?
                            st.session_state[f'_fin_raw_{sid2}'] = _fin_raw
                    except Exception as _fh_exc:
                        st.session_state[_fh_key2] = {'error': True, 'ai_insight': f'鞎∪擃炎?潛?靘?嚗_fh_exc}'}
            _fh = st.session_state.get(_fh_key2)
            if not _fh or _fh.get('error'):
                st.error(_fh.get('ai_insight', '鞎∪擃炎憭望?嚗?蝣箄? FINMIND_TOKEN 撌脰身摰?) if _fh else '頛銝?..')
            else:
                # ?? 蝚砌???銝之?香?? ????????????????????
                st.markdown('#### ?儭?蝚砌????香??鞈芷蝳?)
                _fh_c1, _fh_c2, _fh_c3 = st.columns(3)
                with _fh_c1:
                    st.metric(
                        label='瘞?銝嚗??蝮質???> 25%嚗?,
                        value=f"{_fh.get('cash_ratio_status','?')} {_fh.get('cash_ratio_value','N/A')}",
                        delta='摰' if _fh.get('cash_ratio_status') == '?' else
                              '瘜冽?' if _fh.get('cash_ratio_status') == '?' else '?梢',
                        delta_color='normal' if _fh.get('cash_ratio_status') == '?' else 'inverse',
                    )
                with _fh_c2:
                    st.metric(
                        label='???脣嚗CF 敹??箸迤嚗?,
                        value=f"{_fh.get('ocf_status','?')} {_fh.get('ocf_value','N/A')}",
                        delta='蝛拙?瘚' if _fh.get('ocf_status') == '?' else '暺??渡霅行?',
                        delta_color='normal' if _fh.get('ocf_status') == '?' else 'inverse',
                    )
                with _fh_c3:
                    st.metric(
                        label='??璉?嚗??菜? < 60%嚗?,
                        value=f"{_fh.get('debt_ratio_status','?')} {_fh.get('debt_ratio_value','N/A')}",
                        delta='蝛拙' if _fh.get('debt_ratio_status') == '?' else
                              '??' if _fh.get('debt_ratio_status') == '?' else '?梢',
                        delta_color='normal' if _fh.get('debt_ratio_status') == '?' else 'inverse',
                    )

                st.markdown('<hr style="border-color:#21262d;margin:10px 0;">', unsafe_allow_html=True)

                # ?? 鈭??琿???+ 隡平DNA / 霅瑕?瘝???????????
                _fh_left, _fh_right = st.columns([1, 1])

                with _fh_left:
                    st.markdown('#### ? 鈭?擃釭?琿???)
                    _radar = _fh.get('radar_scores', {})
                    if _radar:
                        import plotly.graph_objects as _go_fh
                        _cats = list(_radar.keys()) + [list(_radar.keys())[0]]
                        _vals = [max(0, min(100, int(v))) for v in _radar.values()]
                        _vals += [_vals[0]]
                        _fig_fh = _go_fh.Figure(_go_fh.Scatterpolar(
                            r=_vals, theta=_cats, fill='toself',
                            line_color=TRAFFIC_GREEN, fillcolor='rgba(63,185,80,0.2)',
                        ))
                        _fig_fh.update_layout(
                            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            margin=dict(l=20, r=20, t=20, b=20),
                            showlegend=False,
                        )
                        st.plotly_chart(_fig_fh, width='stretch')
                    else:
                        st.warning('?⊥???鈭?閰?鞈?')

                with _fh_right:
                    st.markdown('#### ?妞 隡平 DNA ?風?眾')
                    _dna = _fh.get('business_model_dna', '?⊥??斗')
                    _dna_clr = (TRAFFIC_GREEN if 'A+' in _dna or _dna.startswith('A ')
                                else TRAFFIC_YELLOW if 'B' in _dna or 'C' in _dna
                                else TRAFFIC_RED)
                    st.markdown(
                        f'<div style="background:#161b22;border-left:4px solid {_dna_clr};'
                        f'border-radius:8px;padding:14px 16px;margin-bottom:10px;">'
                        f'<div style="font-size:11px;color:#484f58;margin-bottom:4px;">?暸?瘚??摰?/div>'
                        f'<div style="font-size:18px;font-weight:900;color:{_dna_clr};">{_dna}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown('**OPM ?平閰梯?甈炎撽?*')
                    _opm = _fh.get('opm_data', {})
                    _p_days = _opm.get('payable_days', 0)
                    _r_days = _opm.get('receivable_days', 0)
                    _adv = _opm.get('advantage', False)
                    if _adv:
                        st.success(
                            f'?? ?瑕?敹急?Ｖ??芸\n\n'
                            f'??撣單狡 **{_p_days}憭?* > ?撣單狡 **{_r_days}憭?*'
                        )
                    elif _r_days == 0:
                        st.info('DSO (?撣單狡憭拇) 鞈?蝻箸?嚗瘜摰?OPM 霅瑕?瘝?)
                    else:
                        st.warning(
                            f'?? ??鞈?憯?頛之\n\n'
                            f'??撣單狡 **{_p_days}憭?* < ?撣單狡 **{_r_days}憭?*'
                        )

                st.markdown('<hr style="border-color:#21262d;margin:10px 0;">', unsafe_allow_html=True)

                # ?? 摮暑?賢?蝎曄敦璅∠?嚗urvival Module嚗??????????
                _surv2 = _fh.get('survival_module', {})
                if _surv2:
                    st.markdown('#### ? 摮暑?賢?蝎曄敦閮箸嚗J 3憭抒?甇餅?璅?')
                    _sc_map = {'Pass': TRAFFIC_GREEN, 'Acceptable': TRAFFIC_YELLOW, 'Fail': TRAFFIC_RED}
                    _s2c = st.columns(3)
                    for _col2, (_key2, _lbl2) in zip(_s2c, [
                        ('Cash_Ratio', '? 瘞?銝'), ('DSO_Speed', '???嗥?漲')
                    ]):
                        _si2 = _surv2.get(_key2, {})
                        _sc2 = _sc_map.get(_si2.get('Status', 'Fail'), TRAFFIC_RED)
                        with _col2:
                            st.markdown(
                                f'<div style="background:{_sc2}18;border:1px solid {_sc2}55;'
                                f'border-radius:8px;padding:10px;text-align:center;">'
                                f'<div style="font-size:11px;color:#8b949e;">{_lbl2}</div>'
                                f'<div style="font-size:20px;font-weight:900;color:{_sc2};">{_si2.get("Value","N/A")}</div>'
                                f'<div style="font-size:11px;color:{_sc2};">{_si2.get("Status","?")}</div>'
                                f'<div style="font-size:10px;color:#8b949e;margin-top:4px;">{_si2.get("Insight","")}</div>'
                                f'</div>', unsafe_allow_html=True)
                    _r1102 = _surv2.get('Rule_100_100_10', {})
                    _r110c2 = _sc_map.get(_r1102.get('Status', 'Fail'), TRAFFIC_RED)
                    # ??????瑼鳴?A>100% / B??00% / C>10%嚗? financial_health_engine:416/423/431 撠?嚗?
                    _a_ok2 = parse_cash_flow_ratio(_r1102.get('Cash_Flow_Ratio',''), 100, strict=True)
                    _b_ok2 = parse_cash_flow_ratio(_r1102.get('Cash_Flow_Adequacy',''), 100, strict=False)
                    _c_ok2 = parse_cash_flow_ratio(_r1102.get('Cash_Reinvestment',''), 10, strict=True)
                    with _s2c[2]:
                        st.markdown(
                            f'<div style="background:{_r110c2}18;border:1px solid {_r110c2}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">?? 100/100/10</div>'
                            f'<div style="font-size:11px;color:#c9d1d9;">'
                            f'A{format_condition_emoji(_a_ok2)}{_r1102.get("Cash_Flow_Ratio","N/A")} '
                            f'B{format_condition_emoji(_b_ok2)}{_r1102.get("Cash_Flow_Adequacy","N/A")} '
                            f'C{format_condition_emoji(_c_ok2)}{_r1102.get("Cash_Reinvestment","N/A")}</div>'
                            f'<div style="font-size:12px;font-weight:700;color:{_r110c2};">{_r1102.get("Status","?")}</div>'
                            f'<div style="font-size:10px;color:#8b949e;margin-top:4px;">{_r1102.get("Insight","")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _v2 = _surv2.get('Final_Survival_Verdict', '')
                    if _v2:
                        st.caption(f'? {_v2}')

                # ?? 蝬??賢?璅∠?嚗perating Module嚗??????????????
                _oper2 = _fh.get('operating_module', {})
                if _oper2:
                    st.markdown('#### ?? 蝬??賢?閮箸嚗頧???+ 鞈?憯?嚗?)
                    _oc1, _oc2, _oc3, _oc4 = st.columns(4)
                    _ccc_str = str(_oper2.get('Cash_Gap_Days', 'N/A'))
                    try:
                        _ccc_num = float(_ccc_str.split()[0].replace('憭?, '').strip())
                        _ccc_is_num = True
                    except (ValueError, AttributeError):
                        _ccc_num, _ccc_is_num = 0.0, False
                    # OPM 霅瑕?瘝喉?撘??文? Yes 銝?CCC ?箏祕鞈芾??賂??抵???蝡?憿舐內
                    _opm_yes = (_oper2.get('OPM_Strategy', 'No') == 'Yes') and _ccc_is_num and (_ccc_num < 0)
                    _ccc_color = TRAFFIC_GREEN if _opm_yes else ('#8b949e' if not _ccc_is_num else TRAFFIC_YELLOW)
                    with _oc1:
                        st.metric('DSO ?憭拇', _oper2.get('DSO', 'N/A'))
                    with _oc2:
                        st.metric('DIO 摮疏憭拇', _oper2.get('DIO', 'N/A'))
                    with _oc3:
                        st.metric('DPO ??憭拇', _oper2.get('DPO', 'N/A'))
                    with _oc4:
                        st.metric('蝮質??Ｙ蕃獢?', _oper2.get('Asset_Turnover', 'N/A'))
                    _oc5, _oc6 = st.columns(2)
                    with _oc5:
                        st.markdown(
                            f'<div style="background:#161b22;border-radius:8px;padding:10px;">'
                            f'<div style="font-size:11px;color:#8b949e;">?????湧望?</div>'
                            f'<div style="font-size:18px;font-weight:900;color:#58a6ff;">{_oper2.get("Complete_Cycle","N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    with _oc6:
                        st.markdown(
                            f'<div style="background:#161b22;border-radius:8px;padding:10px;">'
                            f'<div style="font-size:11px;color:#8b949e;">蝻粹憭拇 (CCC)</div>'
                            f'<div style="font-size:18px;font-weight:900;color:{_ccc_color};">{_oper2.get("Cash_Gap_Days","N/A")}</div>'
                            f'<div style="font-size:11px;color:{_ccc_color};">{"??OPM霅瑕?瘝喉??踹鈭箇??Ｗ???" if _opm_yes else ("??CCC 鞈?銝雲" if not _ccc_is_num else "?? ??芸???鞈?")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _oper2.get('Verdict'):
                        st.caption(f'? {_oper2["Verdict"]}')

                # ?? ?脣?賢?璅∠?嚗rofitability Module嚗?????????
                _prof2 = _fh.get('profitability_module', {})
                if _prof2:
                    st.markdown('#### ? ?脣?賢?閮箸嚗J 5憭扳?璅?')
                    _p5c = st.columns(5)
                    # 1 瘥??
                    _gm2 = _prof2.get('Gross_Margin', {})
                    _gm2_ok = _gm2.get('Status', '') == 'Good'
                    with _p5c[0]:
                        st.markdown(
                            f'<div style="background:{"{TRAFFIC_GREEN}18" if _gm2_ok else "{TRAFFIC_RED}18"};'
                            f'border:1px solid {"{TRAFFIC_GREEN}55" if _gm2_ok else "{TRAFFIC_RED}55"};'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">瘥??/div>'
                            f'<div style="font-size:17px;font-weight:900;color:{TRAFFIC_GREEN if _gm2_ok else TRAFFIC_RED};">{_gm2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{TRAFFIC_GREEN if _gm2_ok else TRAFFIC_RED};">{"憟賜??? if _gm2_ok else "颲??"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 2 ?平?拍???
                    _om2 = _prof2.get('Operating_Margin', {})
                    _om2_ok = _om2.get('Core_Business_Profitable', 'No') == 'Yes'
                    with _p5c[1]:
                        st.markdown(
                            f'<div style="background:{"{TRAFFIC_GREEN}18" if _om2_ok else "{TRAFFIC_RED}18"};'
                            f'border:1px solid {"{TRAFFIC_GREEN}55" if _om2_ok else "{TRAFFIC_RED}55"};'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">?平?拍???/div>'
                            f'<div style="font-size:17px;font-weight:900;color:{TRAFFIC_GREEN if _om2_ok else TRAFFIC_RED};">{_om2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{TRAFFIC_GREEN if _om2_ok else TRAFFIC_RED};">{"?祆平?脣?? if _om2_ok else "?祆平?扳???}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 3 摰??
                    _mos2 = _prof2.get('Margin_Of_Safety', {})
                    _mos2_ok = _mos2.get('Status', '') == 'Strong'
                    with _p5c[2]:
                        st.markdown(
                            f'<div style="background:{"{TRAFFIC_GREEN}18" if _mos2_ok else "{TRAFFIC_YELLOW}18"};'
                            f'border:1px solid {"{TRAFFIC_GREEN}55" if _mos2_ok else "{TRAFFIC_YELLOW}55"};'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">摰??</div>'
                            f'<div style="font-size:17px;font-weight:900;color:{TRAFFIC_GREEN if _mos2_ok else TRAFFIC_YELLOW};">{_mos2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{TRAFFIC_GREEN if _mos2_ok else TRAFFIC_YELLOW};">{"??璆萄撥?? if _mos2_ok else "鞎餌敺??}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 4 蝔?瘛典??
                    _nm2 = _prof2.get('Net_Margin', {})
                    _nm2_s = _nm2.get('Status', '')
                    _nm2_c = TRAFFIC_GREEN if _nm2_s == 'Pass' else (TRAFFIC_YELLOW if _nm2_s == 'Thin Profit' else TRAFFIC_RED)
                    with _p5c[3]:
                        st.markdown(
                            f'<div style="background:{_nm2_c}18;border:1px solid {_nm2_c}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">蝔?瘛典??/div>'
                            f'<div style="font-size:17px;font-weight:900;color:{_nm2_c};">{_nm2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_nm2_c};">{_nm2_s}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 5 ROE
                    _roe2 = _prof2.get('ROE', {})
                    _roe2_warn = _roe2.get('Leverage_Warning', 'None') != 'None'
                    try:
                        _roe2_num = float(_roe2.get('Value', '0').replace('%', '').strip())
                    except (ValueError, AttributeError):
                        _roe2_num = None
                    _roe2_positive = _roe2_num is not None and _roe2_num > 0
                    _roe2_c = TRAFFIC_YELLOW if _roe2_warn else (TRAFFIC_GREEN if _roe2_positive else TRAFFIC_RED)
                    with _p5c[4]:
                        st.markdown(
                            f'<div style="background:{_roe2_c}18;border:1px solid {_roe2_c}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">ROE</div>'
                            f'<div style="font-size:17px;font-weight:900;color:{_roe2_c};">{_roe2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_roe2_c};">{"?? 擃?獢輸??? if _roe2_warn else ("???祕?脣" if _roe2_positive else "???祆平?扳?")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _prof2.get('Final_Insight'):
                        st.caption(f'? {_prof2["Final_Insight"]}')

                # ?? 鞎∪?蝯?璅∠?嚗inancial Structure Module嚗????
                _fstr2 = _fh.get('financial_structure_module', {})
                if _fstr2:
                    st.markdown('#### ??儭?鞎∪?蝯?閮箸嚗?寞?摮?+ 隞仿?舫嚗?)
                    _fs2c = st.columns(2)
                    # 1 鞎雿??Ｘ???
                    _dr2 = _fstr2.get('Debt_Ratio', {})
                    _dr2_s = _dr2.get('Status', '')
                    _dr2_c = {'Pass': TRAFFIC_GREEN, 'Warning': TRAFFIC_YELLOW, 'Fail': TRAFFIC_RED, 'N/A': '#8b949e'}.get(_dr2_s, '#8b949e')
                    with _fs2c[0]:
                        st.markdown(
                            f'<div style="background:{_dr2_c}18;border:1px solid {_dr2_c}55;'
                            f'border-radius:10px;padding:14px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">鞎雿??Ｘ???/div>'
                            f'<div style="font-size:26px;font-weight:900;color:{_dr2_c};">{_dr2.get("Value","N/A")}</div>'
                            f'<div style="font-size:11px;color:{_dr2_c};">'
                            f'{"??蝛拙嚗?60%嚗? if _dr2_s=="Pass" else ("?? ??嚗?0-70%嚗? if _dr2_s=="Warning" else ("? 擃嚗?70%嚗? if _dr2_s=="Fail" else ("? ?寡迂銵平" if "??" in _dr2.get("Value","") else "??鞈?蝻箸?")))}'
                            f'</div></div>', unsafe_allow_html=True)
                    # 2 隞仿?舫瘥?
                    _ltf2 = _fstr2.get('Long_Term_Funding_Ratio', {})
                    _ltf2_s = _ltf2.get('Status', '')
                    _ltf2_c = TRAFFIC_GREEN if _ltf2_s == 'Pass' else ('#8b949e' if _ltf2_s == 'N/A' else TRAFFIC_RED)
                    _ltf2_label = ('??鞈??蔭甇?Ⅱ嚗?100%嚗? if _ltf2_s == 'Pass'
                                   else ('??鞈?銝雲嚗瘜?? if _ltf2_s == 'N/A'
                                         else '? ?剖?瑟?嚗????望?'))
                    with _fs2c[1]:
                        st.markdown(
                            f'<div style="background:{_ltf2_c}18;border:1px solid {_ltf2_c}55;'
                            f'border-radius:10px;padding:14px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">隞仿?舫瘥?</div>'
                            f'<div style="font-size:26px;font-weight:900;color:{_ltf2_c};">{_ltf2.get("Value","N/A")}</div>'
                            f'<div style="font-size:11px;color:{_ltf2_c};">{_ltf2_label}'
                            f'</div></div>', unsafe_allow_html=True)
                    if _fstr2.get('Final_Insight'):
                        st.caption(f'??儭?{_fstr2["Final_Insight"]}')

                # ?? ??賢?璅∠?嚗olvency Module嚗?????????????
                _solv2 = _fh.get('solvency_module', {})
                if _solv2:
                    st.markdown('#### ?儭??剜???賢?閮箸嚗J 300/150 ?湔璅?嚗?)
                    # ?蝯?瘙?banner
                    _sv2_v = _solv2.get('Final_Solvency_Verdict', '')
                    _sv2_pass = 'Pass' in _sv2_v
                    _sv2_exc  = 'Exception' in _sv2_v
                    _sv2_bc   = TRAFFIC_GREEN if _sv2_pass and not _sv2_exc else (TRAFFIC_YELLOW if _sv2_exc else TRAFFIC_RED)
                    _sv2_icon = '?? if _sv2_pass and not _sv2_exc else ('?? if _sv2_exc else '?')
                    st.markdown(
                        f'<div style="background:{_sv2_bc}18;border:2px solid {_sv2_bc};'
                        f'border-radius:10px;padding:10px 16px;margin-bottom:10px;">'
                        f'<span style="font-size:14px;font-weight:900;color:{_sv2_bc};">'
                        f'{_sv2_icon} {_sv2_v}</span></div>', unsafe_allow_html=True)
                    # 靽蝚佗?靘?Final_Solvency_Verdict ???憭???
                    _is_dso_exception  = "璇辣B嚗予憭拇?? in _sv2_v
                    _is_cash_exception = "璇辣A嚗??頞? in _sv2_v
                    _is_any_exception  = _is_dso_exception or _is_cash_exception
                    # 瘚?瘥??瑼鳴?璇辣B??50%嚗?隞詛??00%嚗靘???00%
                    _cr_thresh = 150 if _is_dso_exception else (100 if _is_cash_exception else 300)
                    _cr_label  = (f'瘚?瘥?嚗??賜泵?曉祝 >{_cr_thresh}%嚗?
                                  if _is_any_exception else '瘚?瘥?嚗J?湔 >300%嚗?)
                    _sv2c = st.columns(2)
                    for _col, (_key, _label, _thresh) in zip(_sv2c, [
                        ('Current_Ratio', _cr_label, _cr_thresh),
                        ('Quick_Ratio', '??瘥?嚗J?湔 >150%嚗?, 150),
                    ]):
                        _si = _solv2.get(_key, {})
                        _si_s = _si.get('Status', '')
                        # 靽蝚血???嚗??唬誑?曉祝?曉澆摰??????脰?璅惜
                        if _key == 'Current_Ratio' and _is_any_exception:
                            try:
                                _cr_num = float(_si.get('Value', '0').replace('%', '').strip())
                                if _cr_num > _thresh:
                                    _si_c, _si_s = TRAFFIC_GREEN, f'Pass嚗??賜泵 >{_thresh}%嚗?
                                else:
                                    _si_c = TRAFFIC_RED
                            except (ValueError, AttributeError):
                                _si_c = TRAFFIC_GREEN if 'Pass' in _si_s else TRAFFIC_RED
                        else:
                            _si_c = TRAFFIC_GREEN if 'Pass' in _si_s else TRAFFIC_RED
                        with _col:
                            st.markdown(
                                f'<div style="background:{_si_c}18;border:1px solid {_si_c}55;'
                                f'border-radius:10px;padding:12px;text-align:center;">'
                                f'<div style="font-size:11px;color:#8b949e;">{_label}</div>'
                                f'<div style="font-size:24px;font-weight:900;color:{_si_c};">{_si.get("Value","N/A")}</div>'
                                f'<div style="font-size:11px;color:{_si_c};">{_si_s}</div>'
                                f'</div>', unsafe_allow_html=True)
                    # Banner嚗?靘?憿?憿舐內銝??內
                    if _is_dso_exception:
                        st.info('?? 撌脣???曇?璆凋漱??霅??賜泵嚗SO ??15憭抬?瘚?瘥??瑼餅撖祈 >150%嚗?)
                    elif _is_cash_exception:
                        st.info('? 撌脣????頞喃漱??霅??賜泵嚗??蝮質???>25%嚗?????瑼餅撖祈 >100%嚗?)
                    if _solv2.get('Final_Insight'):
                        st.caption(f'?儭?{_solv2["Final_Insight"]}')

                # ?? 蝬?閮箸璅∠?嚗dvanced Diagnostic Module嚗????
                _adv2 = _fh.get('advanced_diagnostic_module', {})
                if _adv2:
                    st.markdown('#### ? 蝬?閮箸??瘀?頝刻”?曄里 + ?圈?菜葫嚗?)
                    # 蝚砌??????釭 + ? + ??
                    _ad2r1 = st.columns(3)
                    # ???釭
                    _eq2 = _adv2.get('Earnings_Quality', {})
                    _eq2_s = _eq2.get('Status', '')
                    _eq2_c = TRAFFIC_GREEN if _eq2_s == 'Pass' else (TRAFFIC_RED if _eq2_s == 'Fail' else '#8b949e')
                    with _ad2r1[0]:
                        st.markdown(
                            f'<div style="background:{_eq2_c}18;border:1px solid {_eq2_c}55;'
                            f'border-radius:10px;padding:12px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">???恍???/div>'
                            f'<div style="font-size:22px;font-weight:900;color:{_eq2_c};">{_eq2.get("Value","N/A")}</div>'
                            f'<div style="font-size:11px;color:{_eq2_c};">{"?????賡?" if _eq2_s=="Pass" else ("? 蝝?撖眼" if _eq2_s=="Fail" else "N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # ???
                    _dp2 = _adv2.get('DuPont_Health', '')
                    _dp2_c = TRAFFIC_RED if '霅血' in _dp2 else (TRAFFIC_GREEN if '?亙熒' in _dp2 else TRAFFIC_YELLOW)
                    _dp2_icon = '?' if '霅血' in _dp2 else ('?? if '?亙熒' in _dp2 else '??')
                    with _ad2r1[1]:
                        st.markdown(
                            f'<div style="background:{_dp2_c}18;border:1px solid {_dp2_c}55;'
                            f'border-radius:10px;padding:12px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">???</div>'
                            f'<div style="font-size:13px;font-weight:900;color:{_dp2_c};line-height:1.4;">{_dp2_icon} {_dp2}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # ???望?
                    _dh2 = _adv2.get('Double_High_Warning', '')
                    _dh2_danger = 'Triggered' in _dh2
                    _dh2_c = TRAFFIC_RED if _dh2_danger else (TRAFFIC_GREEN if 'Clear' in _dh2 else '#8b949e')
                    with _ad2r1[2]:
                        st.markdown(
                            f'<div style="background:{_dh2_c}18;border:1px solid {_dh2_c}55;'
                            f'border-radius:10px;padding:12px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">???望??菜葫</div>'
                            f'<div style="font-size:13px;font-weight:900;color:{_dh2_c};">{"? 閫貊霅血嚗? if _dh2_danger else ("??摰" if "Clear" in _dh2 else "漎?鞈?銝雲")}</div>'
                            f'<div style="font-size:10px;color:{_dh2_c};">{_dh2}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 蝚砌???隡平 DNA ?典祝
                    _dna2 = _adv2.get('Business_DNA', '')
                    _dna2_c = TRAFFIC_GREEN if 'A+' in _dna2 else (TRAFFIC_YELLOW if '?' in _dna2 or '?啣' in _dna2 else (TRAFFIC_RED if '?香' in _dna2 else '#58a6ff'))
                    st.markdown(
                        f'<div style="background:{_dna2_c}18;border:1px solid {_dna2_c}55;'
                        f'border-radius:10px;padding:10px 16px;margin-top:8px;">'
                        f'<span style="font-size:11px;color:#8b949e;">隡平 DNA嚗???拚嚗?</span>'
                        f'<span style="font-size:14px;font-weight:900;color:{_dna2_c};margin-left:8px;">{_dna2}</span>'
                        f'</div>', unsafe_allow_html=True)
                    if _adv2.get('Final_Verdict'):
                        st.caption(f'? {_adv2["Final_Verdict"]}')

                # ?? ?葦??蝮賜?隢??????????????????????????????????
                _ov = no_ai_overall_verdict(
                    fin_data=st.session_state.get('t2_fin_data', {}),
                    fh_result=_fh,
                )
                _ovc = _ov.get("grade_color", "#58a6ff")
                st.markdown('<hr style="border-color:#30363d;margin:14px 0 10px;">', unsafe_allow_html=True)
                st.markdown(
                    f'<div style="background:{_ovc}12;border:2px solid {_ovc};border-radius:12px;padding:16px 20px;">'
                    f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:8px;">'
                    f'<span style="font-size:36px;font-weight:900;color:{_ovc};font-family:monospace;">'
                    f'{_ov.get("grade","?")}</span>'
                    f'<div>'
                    f'<div style="font-size:14px;font-weight:900;color:{_ovc};">{_ov.get("headline","")}</div>'
                    f'<div style="font-size:10px;color:#8b949e;margin-top:2px;">'
                    f'蝑2 繚 6憭扳芋蝯???隡?繚 '
                    f'??{_ov.get("pass_count",0)} ??璅'
                    f'? {_ov.get("fail_count",0)} ?郎蝷箝'
                    f'隡平DNA嚗_ov.get("dna","--")}'
                    f'</div></div></div>'
                    f'<div style="font-size:12px;color:#c9d1d9;line-height:1.7;">{_ov.get("comment","")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ?? ?? ??蝐Ⅳ憭扳?琿?嚗銝颱誨蝣?sid2 ?芸??亥岷嚗蔭??AI 蝮賜?銝靘撘嚗???
        st.markdown('---')
        from chip_radar import render_chip_radar
        _chip_radar_summary = render_chip_radar(sid2)

        # ?? ?? AI 擐葉憿批?蝮賜? ????????????????????????????????????
        st.markdown("""<div style="margin:28px 0 8px;padding:8px 16px;background:linear-gradient(90deg,#76e3ea18,#0d1117);border-left:4px solid #76e3ea;border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:#76e3ea;">?? AI 擐葉憿批?蝮賜?</span><span style="font-size:11px;color:#8b949e;margin-left:8px;">?銵 繚 銝之瘜犖 繚 ??憭扳蝐Ⅳ 繚 ?箸??繚 鞎∪擃炎嚗???嚗?蝮賜?嚚?蝬剔???隡?/span></div>""", unsafe_allow_html=True)

        _ai_sum_key = f'_ai_sum_{sid2}'
        _ai_sum_cached = st.session_state.get(_ai_sum_key, '')

        def _fmt_news_list(_news):
            if not _news:
                return '嚗?∠??啗?嚗?
            _ls = []
            for _nn in _news:
                _t = _nn.get('title', '')
                _lk = _nn.get('link', '')
                _src = _nn.get('source', 'RSS')
                _pb = _nn.get('published', '') or '??
                _head = f'[{_t}]({_lk})' if _lk else _t
                _ls.append(f'- `{_pb}` 繚 {_head}?_{_src}_')
            return '\n'.join(_ls)

        def _show_news_expander(_news, _diag=None):
            _cnt = len(_news) if _news else 0
            with st.expander(f'? 餈??賊??啗?嚗_cnt} ??繚 Google News RSS 繚 餈??箔蜓嚗?, expanded=bool(_news)):
                st.caption('靘?嚗oogle News RSS嚗葉?望?嚗??摨西??????誑餈??勗??箔蜓嚗?璅?????)
                if _news:
                    st.markdown(_fmt_news_list(_news))
                else:
                    st.info('?祆活?芸?敺?啗? ???航 Google News RSS ?急???/撠?嚗蝡舀絲憭?IP嚗?餈??∠?撠??舐?敺?閰艾?)
                    if _diag:
                        st.caption('? ??閮箸嚗roxy/?湧?繚 HTTP 繚 entries 繚 ?航炊嚗?')
                        st.code('\n'.join(_diag), language='text')

        _ai_sum_c1, _ai_sum_c2 = st.columns([3, 1])
        with _ai_sum_c1:
            _do_ai_sum = st.button('?? ?? AI 擐葉憿批??啁閰摯?勗?', key='btn_ai_sum2', type='primary')
        with _ai_sum_c2:
            if st.button('??儭?皜?勗?', key='btn_ai_sum2_clr'):
                st.session_state.pop(_ai_sum_key, None)
                st.rerun()

        if _do_ai_sum:
            # ?? 敶?銵?豢? ????????????????????????????????????
            _atr2 = float(df2['high'].sub(df2['low']).tail(14).mean()) if df2 is not None and len(df2) >= 14 else 0
            _ibs2 = round((float(df2['close'].iloc[-1]) - float(df2['low'].iloc[-1])) /
                          max(float(df2['high'].iloc[-1]) - float(df2['low'].iloc[-1]), 0.01), 2) if df2 is not None and not df2.empty else 'N/A'
            _vol_ratio2 = round(float(df2['volume'].iloc[-1]) / float(df2['volume'].tail(20).mean()), 2) if df2 is not None and len(df2) >= 20 else 'N/A'
            _bb_pos2 = 'N/A'
            if df2 is not None and 'BB_upper' in df2.columns and 'BB_lower' in df2.columns:
                _bb_u = float(df2['BB_upper'].iloc[-1])
                _bb_l = float(df2['BB_lower'].iloc[-1])
                _bb_pos2 = f'{round((price2 - _bb_l) / max(_bb_u - _bb_l, 0.01) * 100, 1)}%'
            _ma_str2 = ', '.join(f'{k}:{"銝?? if v else "銝??"}' for k,v in _ma_above2.items()) if _ma_above2 else 'N/A'
            _rsi_str2 = f'{rsi2:.1f}' if rsi2 else 'N/A'
            _k_str2   = f'{k2:.1f}' if k2 else 'N/A'
            _d_str2   = f'{d2:.1f}' if d2 else 'N/A'
            _tech_data2 = (
                f"?曉={price2:.2f} | ?亙熒摨?{health2:.0f}/100 | RSI={_rsi_str2} | "
                f"KD=K:{_k_str2}/D:{_d_str2} | "
                f"IBS={_ibs2} | ??={_vol_ratio2} | ATR={_atr2:.2f} | 撣?雿?={_bb_pos2}\n"
                f"??雿?={_ma_str2}\n"
                f"VCP={'蝒閮??? if _vcp_ok2 else ('?渡??嗥葬銝? if vcp2 else '?芸耦??)}"
            )
            # ?? 敶蝐Ⅳ?豢? ??????????????????????????????????????
            _chip_str2 = '?⊥???銝之瘜犖?敦'
            if df2 is not None and not df2.empty:
                _fb = next((df2[c].tail(10).sum() for c in df2.columns if '憭?' in str(c) and '鞎? in str(c)), None)
                _tb = next((df2[c].tail(10).sum() for c in df2.columns if '?縑' in str(c)), None)
                _db = next((df2[c].tail(10).sum() for c in df2.columns if '?芰?' in str(c)), None)
                _parts = []
                if _fb is not None:
                    _parts.append(f'憭?10??{_fb/1e8:+.1f}??)
                if _tb is not None:
                    _parts.append(f'?縑10??{_tb/1e8:+.1f}??)
                if _db is not None:
                    _parts.append(f'?芰?10??{_db/1e8:+.1f}??)
                if _parts:
                    _chip_str2 = ' | '.join(_parts)
            # ?? 敶?箸?Ｘ??????????????????????????????????????
            _fund_str2 = []
            if _rev_yoy_list:
                _fund_str2.append(f'???跎oY餈???{", ".join(_rev_yoy_list)}')
            if qtr2 is not None and not qtr2.empty:
                _gm_col = next((c for c in qtr2.columns if '瘥' in str(c)), None)
                _eps_col = next((c for c in qtr2.columns if 'eps' in str(c).lower() or 'EPS' in str(c)), None)
                if _gm_col:
                    _gm_vals = pd.to_numeric(qtr2[_gm_col].tail(4), errors='coerce').dropna()
                    _fund_str2.append(f'餈?摮???拍?={[round(v,1) for v in _gm_vals.tolist()]}%')
                if _eps_col:
                    _eps_vals = pd.to_numeric(qtr2[_eps_col].tail(4), errors='coerce').dropna()
                    _fund_str2.append(f'餈?摮ΒPS={_eps_vals.tolist()}')
            if cl2 and cl2 > 0:
                _fund_str2.append(f'??鞎={cl2/1e8:.1f}??)
            if cx2 and cx2 > 0:
                _fund_str2.append(f'鞈?臬={cx2/1e8:.1f}??)
            if avg_div2 > 0 and price2 > 0:
                _cp2_ai = round(avg_div2/0.07, 1)
                _fp2_ai = round(avg_div2/0.05, 1)
                _dp2_ai = round(avg_div2/0.03, 1)
                _zone2 = ('靘踹?' if price2 <= _cp2_ai else '??' if price2 <= _fp2_ai
                          else '?眼' if price2 <= _dp2_ai else '頞??眼')
                _fund_str2.append(f'357隡啣?{_zone2}嚗噶摰?{_cp2_ai}/??:{_fp2_ai}/?眼:{_dp2_ai}嚗?)
            _fund_data2 = '\n'.join(_fund_str2) if _fund_str2 else '?箸?Ｚ???頞?
            # ?? 敶鞎∪擃炎蝯? ??????????????????????????????????
            _fh_res2 = st.session_state.get(f'_fh_{sid2}', {})
            _health_check_str2 = '撠?瑁?鞎∪擃炎'
            if _fh_res2 and not _fh_res2.get('error'):
                _opm2 = _fh_res2.get('opm_data', {})
                _opm_str2 = (f"??撣單狡憭拇={_opm2.get('payable_days','N/A')}憭?/ "
                             f"?撣單狡憭拇={_opm2.get('receivable_days','N/A')}憭???"
                             f"{'?瑕?敹急?Ｖ??芸' if _opm2.get('advantage') else '隞狡?望?銝'}"
                             if _opm2 else '??OPM 鞈?')
                _red2 = _fh_res2.get('red_flags', '')
                _flags_str2 = (_red2 if _red2 and _red2.strip().lower() not in ('none', '??, '') else '?⊥?憿臬??)
                _health_check_str2 = (
                    f"?暸?瘞港?={_fh_res2.get('cash_ratio_status','')} {_fh_res2.get('cash_ratio_value','')} | "
                    f"OCF={_fh_res2.get('ocf_status','')} {_fh_res2.get('ocf_value','')} | "
                    f"鞎瘥?{_fh_res2.get('debt_ratio_status','')} {_fh_res2.get('debt_ratio_value','')}\n"
                    f"隡平DNA={_fh_res2.get('business_model_dna','N/A')}\n"
                    f"OPM?平閰梯?甈?{_opm_str2}\n"
                    f"鈭??琿?={_fh_res2.get('radar_scores',{})}\n"
                    f"AI鞎∪瘣?={_fh_res2.get('ai_insight','')}\n"
                    f"?圈霅衣內={_flags_str2}"
                )
            # ?? 敶撣? ??????????????????????????????????????
            _mkt_info2 = st.session_state.get('mkt_info', {})
            _regime_txt2 = {'bull':'憭撣嚗?璆菜?雿?','neutral':'??渡?嚗牲????','bear':'蝛粹撣嚗葬皜雿?'}.get(_regime2, _regime2)
            # 摰???敶嚗IX / 蝢敹PI / ?? ?啁 PMI / 蝢?0Y / 鞎餃? SOX嚗?靘?AI 頝刻??Ｗ霈
            _macro_info2 = st.session_state.get('macro_info', {}) or {}
            _ma_snap2    = st.session_state.get('ma_snap', {}) or {}
            _intl_snap2  = st.session_state.get('intl_snap', {}) or {}
            _macro_lines2 = []
            _vix_v2 = (_macro_info2.get('vix') or {}).get('current') or _ma_snap2.get('vix')
            if _vix_v2 is not None:
                try:
                    _macro_lines2.append(f"VIX ???={float(_vix_v2):.2f}嚗?20 霅行???30 ??嚗?)
                except (TypeError, ValueError):
                    pass
            _cpi_v2 = (_macro_info2.get('us_core_cpi') or {}).get('yoy') or _ma_snap2.get('cpi')
            if _cpi_v2 is not None:
                try:
                    _macro_lines2.append(f"蝢敹?CPI YoY={float(_cpi_v2):+.2f}%嚗ed ?格? 2%嚗?3% ?憯?嚗?)
                except (TypeError, ValueError):
                    pass
            _pmi_v2 = (_macro_info2.get('ism_pmi') or {}).get('value')
            if _pmi_v2 is not None:
                try:
                    _macro_lines2.append(f"?? ?啁 PMI={float(_pmi_v2):.1f}嚗IER嚗?0=璁格蝺?<45=鋆賡平銵圈撘瑁?嚗??ˊ?平?舀除????嚗?)
                except (TypeError, ValueError):
                    pass
            _tnx_v2 = (_intl_snap2.get('tnx') or {}).get('last') or _ma_snap2.get('us10y')
            if _tnx_v2 is not None:
                try:
                    _macro_lines2.append(f"蝢?10Y 畾??{float(_tnx_v2):.2f}%嚗?4% 隡啣澆???5% 畾箸?嚗?)
                except (TypeError, ValueError):
                    pass
            _sox_obj2 = _intl_snap2.get('sox') or {}
            _sox_pct2 = _sox_obj2.get('pct')
            _sox_last2 = _sox_obj2.get('last')
            if _sox_pct2 is not None:
                try:
                    _sl_str = f"嚚??{float(_sox_last2):.0f}" if _sox_last2 is not None else ""
                    _macro_lines2.append(f"鞎餃? SOX={float(_sox_pct2):+.2f}%{_sl_str}嚗???∠????2-4 ?梧?")
                except (TypeError, ValueError):
                    pass
            _macro_extra2 = "\n  ??" + "\n  ??".join(_macro_lines2) if _macro_lines2 else "嚗?∴?隢??啜?閫?澆?????堆?"
            _mkt_ctx2 = (
                f"憭抒?澆?={_regime_txt2} | ?亙熒閰?={_mkt_info2.get('market_score','N/A')} | "
                f"撱箄降?={_mkt_info2.get('exposure_limit_pct', st.session_state.get('macro_state',{}).get('exposure_limit_pct','N/A'))}%\n"
                f"摰?頝刻??Ｚ??荔?{_macro_extra2}"
            )
            # ?? ????啗?嚗???RSS ??????????????????????
            _news_diag2 = []
            _stock_news2 = _fetch_stock_news(sid2, name2, 25, recency='6m', _diag=_news_diag2)
            st.session_state[_ai_sum_key + '_news'] = _stock_news2
            st.session_state[_ai_sum_key + '_newsdiag'] = _news_diag2
            _show_news_expander(_stock_news2, _news_diag2)
            _news_str2 = '\n'.join(
                f'- {_n["title"]}嚗_n.get("source","RSS")} 繚 {_n.get("published","")}嚗?
                for _n in _stock_news2
            ) if _stock_news2 else '嚗?∠??啗?嚗?
            # ?? 鋆今銝撌脩?蝡?嚗???芰??圈＊蝷箝閮???撏抬???????
            try:
                _sr_parts2 = [
                    f'?曉={_cur_p:.2f}',
                    f'餈?0?亙???{_hi20_p:.2f}(頝??{_dist_hi}%)',
                    f'餈?0?交??{_lo20_p:.2f}(頝??{_dist_lo}%)',
                    f'??格?1(+5%)={_tp1_p} / ?格?2(+10%)={_tp2_p}',
                    f'撱箄降??(-8%)={_sl_p} | ?瘥?{_rr_p}x',
                ]
                if _entry_half:
                    _sr_parts2.append(f'?勗振瘜之??K 1/2 雿◢?芾眺暺?{_entry_half}')
                if _abs_sl:
                    _sr_parts2.append(f'蝝雿?蝯???={_abs_sl}')
                _sr_str2 = ' | '.join(_sr_parts2)
            except Exception:
                _sr_str2 = '嚗????????芾?蝞?'
            try:
                _conc_str2 = (f'?葉摨?{_con20:+.1f}%嚗之?嗅?鞈??縑瘛刻眺雿?鈭日?嚗 '
                              f'撱嗥???{_cty20:.0f}%嚗眺頞雿?嚗 閮?={_sig20}')
            except Exception:
                _conc_str2 = '嚗?20?亦?蝣潮?銝剖漲?芸?敺?'
            try:
                _li_str2 = (f'蝮質汗 ??{_li_green} ??{_li_yellow} ??{_li_red}嚗?
                            + '嚗?.join(f'{_r["signal"]}{_r["name"]}={_r["value"]}'
                                       for _r in _li_results[:8]))
            except Exception:
                _li_str2 = '嚗?祇?????芾?蝞?'
            _rs_v = locals().get('_rs_val')
            _rs_str2 = (f'{_rs_v:.0f} ????5 撘瑕?撞??0-75 銝剜扼?50 ?賢?憭抒嚗撠?甈??賂?'
                        if isinstance(_rs_v, (int, float)) else '嚗閮?嚗?)
            try:
                _cap_v = locals().get('_capital')
                if _cap_v and _cap_v > 0:
                    _cl_r = (locals().get('cl2') or 0) / _cap_v * 100
                    _cx_r = (locals().get('cx2') or 0) / _cap_v * 100
                    _is_lead = '??蝚血?樴擃??瑞敺? if (_cl_r >= 50 or _cx_r >= 80) else '?芷?樴?瑼?
                    _lead_str2 = (f'??鞎/?⊥={_cl_r:.0f}%???祆???⊥={_cx_r:.0f}% ??{_is_lead}'
                                  '嚗重?園?樴?嚗?蝝??菊?⊥50%=摰Ｘ???箝??祆?算?⊥80%=蝛扔?渡嚗?)
                else:
                    _lead_str2 = '嚗?祈????嚗瘜摰??剜?Ｙ敺蛛?'
            except Exception:
                _lead_str2 = '嚗??剝?霅行閮?嚗?
            # ?? 撱箸??質店蝯???Prompt嚗?典?隞?ai_structured_summary嚗??
            from ai_structured_summary import build_structured_summary_prompt
            _sections_ai = [
                {'name': '???曉撘瑚?撘瑯?蝵株眼銝眼嚗?銵嚗?,
                 'data': f'{_tech_data2}\nRS ?詨?撘瑕漲嚗_rs_str2}'},
                {'name': '憒?閬眺鞈???????萄雿?,
                 'data': _sr_str2},
                {'name': '憭扳??鈭箏鞎琿??臬鞈??蝐Ⅳ嚗?,
                 'data': (f'銝之瘜犖嚗_chip_str2}\n'
                          f'{_chip_radar_summary or "??憭扳/??嚗鞈?嚗?????⊥??銵剁?"}\n'
                          f'餈?0?亦?蝣潮?銝剖漲嚗_conc_str2}')},
                {'name': '?砍???鞈粹??寡眼銝眼嚗?祇?摯?潘?',
                 'data': (f'{_fund_data2}\n'
                          f'?箸?Ｗ?銵?璅??雿??銝剜??撌殷?嚗_li_str2}\n'
                          f'樴?渡瑼Ｘ葫嚗_lead_str2}')},
                {'name': '鞎∪擃釭?乩??亙熒??瘝??圈',
                 'data': _health_check_str2},
                {'name': '憭抒憓?銝?嚗之?方???嚗?,
                 'data': _mkt_ctx2},
            ]
            _ai_sum_prompt = build_structured_summary_prompt(
                f'{sid2} {name2}', _sections_ai, news_text=_news_str2,
                overall_question=('???∠巨?曉?湧??絲靘?雿?函??詨?憟賜?'
                                  '???閬?敹?閰脫釣??暻潮◢?芥?))

            # 銝脫?頛詨嚗?摮???嚗?L5嚗霈 _ai_sum_prompt嚗?????
            def _ai_stream_gen():
                _full = gemini_call(_ai_sum_prompt, max_tokens=1800)
                _chunk = 80
                import time as _t_ai
                for _i in range(0, len(_full), _chunk):
                    yield _full[_i:_i + _chunk]
                    _t_ai.sleep(0.015)
            _ai_sum_result = st.write_stream(_ai_stream_gen())
            st.session_state[_ai_sum_key] = _ai_sum_result

        if _ai_sum_cached and not _do_ai_sum:
            _cached_news = st.session_state.get(_ai_sum_key + '_news')
            if _cached_news is not None:
                _show_news_expander(_cached_news, st.session_state.get(_ai_sum_key + '_newsdiag'))
            st.markdown(_ai_sum_cached)
        elif not _do_ai_sum:
            st.caption('??暺?銝??嚗I 撠???銵??祇?瓷?梢?瑼Ｕ????憭折?????湔?亥?隡啣??)

# ??????????????????????????????????????????????????????????????
# ??????????????????????????????????????????????????????????????
# TAB 3: 蝬?閰??唳?摰歹?瘙啣摹?撥 ? 憭?摮????蔥??
# ??????????????????????????????????????????????????????????????

    st.markdown(f"""<div style="background:#2a0d0d;border:1px solid {TRAFFIC_RED};border-radius:8px;
padding:10px 14px;font-size:11px;color:{TRAFFIC_RED};margin-top:12px;">
?? ?祆????之撣怠?玨蝔摰對???摮貉??弦???脩??
??瘨?憸券嚗遙雿?雿??銵?瘀???芾??蝟餌絞??鞈“??銝??眺鞈?遣霅啜?
</div>""", unsafe_allow_html=True)

