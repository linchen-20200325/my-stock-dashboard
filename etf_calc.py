from data_config import CACHE_TTL
"""
ETF 閮?撅歹?calc layer嚗?
敺?etf_dashboard.py ?賢??閮??賢?嚗??拍? / 蝮賢??/ ?滯??/ 憸券?? / ???? / ?唳?摰文?閮?
靘陷嚗tf_fetch嚗??calc 瘞賊?銝?鞈?render嚗?
"""
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import timedelta

from etf_fetch import (
    fetch_etf_price, fetch_etf_dividends, fetch_etf_info,
    fetch_etf_nav_history, _get_etf_launch_price,
)


@st.cache_data(ttl=CACHE_TTL["tech_indicators"], max_entries=50, show_spinner=False)
def _compute_etf_warroom_row(ticker: str, name: str, role: str) -> dict:
    """ETF 餈質馱?唳?摰文?瑼Ｚ?蝞??詨?/銵?靘?role ?????摩嚗?

    ?詨?鞈嚗帘?嚗??????摨瑞???雿?
        ? 鞈箸鞈嚗蜇?梢 < 畾??????
        ? 頞典頧摹嚗???MA60嚗?
        ? 擃釭?亙熒嚗蜇?梢 ??畾??銝?蝡? MA60嚗?
        ?嗡??葆霅衣內嚗?隞?B ?渡 / 璇辣 C 皞Ｗ>1% ?酉?潛???摮?

    銵?鞈嚗竟?孵榆嚗?鈭停鞎?? ??嚗?????????雿?
        ??? ?∠?對?< MA20-3?嚗? 憭扯眺 50%
        ??   頞??對?< MA20-2?嚗? 鞎?30%
        ?     靘踹??對?< MA20-1?嚗? 撠眺 20%
        ??    銝剜批?嚗A20-1? ~ MA20+1.5?嚗?
        ??     ??嚗 MA20+1.5?嚗? 銝蕭擃?
        ?     皞??嚗 MA20+2?嚗?

    ?甈?嚗?
        隞?? / ?迂 / 憿? / 撣 / ?滯?? / 撟游???? / 1撟游?臬?? /
        頝?蝺? / 頝迤蝺? / ?雿? / 韏啣嚗?0?伐?/ ?亙熒?? / ??撱箄降
    """
    _empty = {
        '隞??': ticker, '?迂': name, '憿?': role,
        '撣': None, '?滯??': None, '撟游????': None,
        '1撟游?臬??': None, '頝?蝺?': None, '頝迤蝺?': None,
        '?雿?': None, '韏啣': [], '?亙熒??': '??鞈?銝雲', '??撱箄降': '??,
    }
    try:
        df = fetch_etf_price(ticker, period='1y')
        if df.empty or 'Close' not in df.columns:
            return _empty
        divs = fetch_etf_dividends(ticker)
        info = fetch_etf_info(ticker)

        _cur = float(df['Close'].iloc[-1])
        _ttl = calc_total_return_1y(df, divs)
        _yld = calc_current_yield(df, divs)
        _prem = calc_premium_discount(info, df, ticker)
        _prem_pct = _prem.get('premium_pct') if isinstance(_prem, dict) else None

        # ?? & 銋
        _ma20v = float(df['Close'].rolling(20).mean().iloc[-1]) if len(df) >= 20 else None
        _ma60v = float(df['Close'].rolling(60).mean().iloc[-1]) if len(df) >= 60 else None
        _bias20 = round((_cur - _ma20v) / _ma20v * 100, 2) if (_ma20v and _ma20v > 0) else None
        _bias60 = round((_cur - _ma60v) / _ma60v * 100, 2) if (_ma60v and _ma60v > 0) else None

        # MA20 簣 ?嚗???鈭停鞎瑯?蝝?嚗餈?1 撟?daily close ??皞榆
        _sigma_label, _sigma_action, _sigma_emoji = None, None, None
        if _ma20v is not None and len(df) >= 60:
            _std = float(df['Close'].tail(252).std())  # 餈?1 撟?daily std
            if _std > 0:
                _lo3 = _ma20v - 3 * _std
                _lo2 = _ma20v - 2 * _std
                _lo1 = _ma20v - 1 * _std
                _hi15 = _ma20v + 1.5 * _std
                _hi2 = _ma20v + 2 * _std
                if _cur < _lo3:
                    _sigma_emoji, _sigma_label, _sigma_action = '???', '?∠??<-3?)', '憭扯眺 50%'
                elif _cur < _lo2:
                    _sigma_emoji, _sigma_label, _sigma_action = '??', '頞???<-2?)', '鞎?30%'
                elif _cur < _lo1:
                    _sigma_emoji, _sigma_label, _sigma_action = '?', '靘踹???<-1?)', '撠眺 20%'
                elif _cur >= _hi2:
                    _sigma_emoji, _sigma_label, _sigma_action = '?', '皞??(??2?)', '??'
                elif _cur >= _hi15:
                    _sigma_emoji, _sigma_label, _sigma_action = '??', '??(??1.5?)', '銝蕭擃?皜Ⅳ'
                else:
                    _sigma_emoji, _sigma_label, _sigma_action = '??, '銝剜批?(簣1?)', '??閮?'

        # 30 ??sparkline
        _spark = [float(x) for x in df['Close'].tail(30).tolist()]

        # ?? ????嚗敹?vs 銵? ??????????????????????????????
        _is_core = (role == '?詨?')
        _is_sat = (role == '銵?')

        if _is_core:
            # ?詨?嚗蜇?梢 vs 畾??+ MA60 頞典
            _below_ma60 = (_ma60v is not None and _cur < _ma60v)
            _has_yld = _yld and _yld > 0
            _extra = []
            # 璇辣 B ?渡
            _lp = _get_etf_launch_price(ticker, df)
            if _lp and _cur < _lp:
                _extra.append(f'?渡(<{_lp:.1f})')
            # 璇辣 C 皞Ｗ
            if _prem_pct is not None and _prem_pct > 1:
                _extra.append(f'皞Ｗ??({_prem_pct:+.2f}%)')
            elif _prem_pct is not None and _prem_pct < 0:
                _extra.append(f'?({_prem_pct:+.2f}%)')

            if _has_yld and _ttl < _yld:
                _lamp = f'? 鞈箸鞈({_ttl:.1f}%<{_yld:.1f}%)??'
                _action_hint = '??嚗敹?敺?摰嫣噩???'
            elif _below_ma60:
                _lamp = f'? 頞典頧摹嚗???MA60 {_ma60v:.2f}嚗?
                _action_hint = '閫撖?蝺迫頝?銝?蝣?
            elif _has_yld:
                _lamp = f'? 擃釭?亙熒嚗_ttl:.1f}% ??{_yld:.1f}%嚗?
                _action_hint = '甇?虜蝥?'
            else:
                _lamp = '? 銝剜扳????⊿??航???'
                _action_hint = '閫撖?
            if _extra:
                _lamp += ' 嚚?' + ' / '.join(_extra)

        elif _is_sat:
            # 銵?嚗?交 ? 雿??嗥???
            if _sigma_emoji:
                _lamp = f'{_sigma_emoji} {_sigma_label}'
                _action_hint = _sigma_action or '??
            else:
                _lamp = '??? 鞈?銝雲'
                _action_hint = '??

        else:
            # ?嗡?閫嚗????摩蝎曄陛??
            _warns = []
            if _yld and _yld > 0 and _ttl < _yld:
                _warns.append('鞈箸鞈')
            if _prem_pct is not None and _prem_pct > 1:
                _warns.append(f'皞Ｗ{_prem_pct:+.2f}%')
            _lamp = ('? ' + ' 嚚?'.join(_warns)) if _warns else '? 銝剜扳???
            _action_hint = '??

        return {
            '隞??': ticker, '?迂': name, '憿?': role,
            '撣': round(_cur, 2),
            '?滯??': (round(_prem_pct, 2) if _prem_pct is not None else None),
            '撟游????': (round(_yld, 2) if _yld else None),
            '1撟游?臬??': round(_ttl, 2),
            '頝?蝺?': _bias20,
            '頝迤蝺?': _bias60,
            '?雿?': (f'{_sigma_emoji} {_sigma_label}' if _sigma_emoji else None),
            '韏啣': _spark,
            '?亙熒??': _lamp,
            '??撱箄降': _action_hint,
        }
    except Exception as e:
        print(f'[warroom/{ticker}] {type(e).__name__}: {e}')
        _empty['?亙熒??'] = f'??閮?憭望?嚗type(e).__name__}'
        return _empty


def calc_current_yield(df: pd.DataFrame, divs: pd.Series) -> float:
    """餈?2???暸?畾??%)"""
    if df.empty or divs.empty:
        return 0.0
    try:
        cutoff = df.index[-1] - timedelta(days=365)
        annual_div = float(divs[divs.index >= cutoff].sum())
        price = float(df['Close'].iloc[-1])
        return round(annual_div / price * 100, 2) if price > 0 else 0.0
    except Exception:
        return 0.0


def calc_total_return_1y(df: pd.DataFrame, divs: pd.Series) -> float:
    """餈?撟游?舐蜇?梢??%)"""
    if df.empty:
        return 0.0
    try:
        cutoff = df.index[-1] - timedelta(days=365)
        df_1y = df[df.index >= cutoff]
        if len(df_1y) < 2:
            return 0.0
        p_start = float(df_1y['Close'].iloc[0])
        p_end   = float(df_1y['Close'].iloc[-1])
        div_sum = float(divs[divs.index >= cutoff].sum()) if not divs.empty else 0.0
        return round((p_end - p_start + div_sum) / p_start * 100, 2)
    except Exception:
        return 0.0


def calc_avg_yield(df: pd.DataFrame, divs: pd.Series, years: int = 5) -> float:
    """餈撟游像???拍?嚗重?園?7%?砍?嚗?""
    if df.empty or divs.empty:
        return 0.0
    try:
        now = df.index[-1]
        result = []
        for y in range(years):
            y_start = now - timedelta(days=365 * (y + 1))
            y_end   = now - timedelta(days=365 * y)
            y_div   = float(divs[(divs.index >= y_start) & (divs.index < y_end)].sum())
            df_y    = df[(df.index >= y_start) & (df.index < y_end)]
            if df_y.empty or y_div <= 0:
                continue
            avg_p = float(df_y['Close'].mean())
            if avg_p > 0:
                result.append(y_div / avg_p * 100)
        return round(sum(result) / len(result), 2) if result else 0.0
    except Exception:
        return 0.0


def check_vcp_signal(df: pd.DataFrame) -> dict:
    """?亙 VCP 瘜Ｗ??嗥葬?菜葫"""
    r = {'signal': False, 'above_ma50': False, 'above_ma200': False,
         'vol_confirm': False, 'weekly_ranges': [], 'stop_loss': None}
    if df is None or len(df) < 210:
        return r
    try:
        close  = df['Close']
        last_c = float(close.iloc[-1])
        ma50   = float(close.rolling(50).mean().iloc[-1])
        ma200  = float(close.rolling(200).mean().iloc[-1])
        r['above_ma50']  = last_c > ma50
        r['above_ma200'] = last_c > ma200
        r['stop_loss']   = round(last_c * 0.92, 2)

        # ?密瘜Ｗ?嚗?5?梧?
        df_w = df.resample('W').agg({'High':'max','Low':'min',
                                       'Close':'last','Volume':'sum'}).dropna()
        if len(df_w) >= 6:
            ranges = []
            for i in range(-5, 0):
                row = df_w.iloc[i]
                mid = (float(row['High']) + float(row['Low'])) / 2
                if mid > 0:
                    ranges.append(round((float(row['High']) - float(row['Low'])) / mid * 100, 1))
            r['weekly_ranges'] = ranges
            if len(ranges) >= 5:
                early_avg = sum(ranges[:2]) / 2
                late_avg  = sum(ranges[-2:]) / 2
                shrinking = late_avg < early_avg * 0.6
                vol_ma50  = float(df['Volume'].rolling(50).mean().iloc[-1])
                vol_now   = float(df['Volume'].iloc[-1])
                r['vol_confirm'] = vol_now > vol_ma50
                r['signal'] = (r['above_ma50'] and r['above_ma200']
                                and shrinking and r['vol_confirm'])
    except Exception:
        pass
    return r


def calc_premium_discount(info: dict, df: "pd.DataFrame", ticker: str = '') -> dict:
    """?滯?寧? = (撣 - 瘛典? / 瘛典?? 100
    ?詨???嚗AV ???孵????芸?銝?伐??踹?頝其?皞?雿?
    銝餃?撘?ETF嚗誨?蝣澆?瘥?e.g. 00980A嚗AV ?砍?撣?T+1 撱園嚗?銝???∴?
      G1嚗AV ??唳 vs 撣??唳?詨榆 ?? 鈭斗?????stale嚗???N/A
      G2嚗蜓?? ETF |prem| > 2.0% ????NAV ?撖怠雿?潭?湔 ??? N/A
      G3嚗AV ??唳?拇??銝鈭斗??乓? ???郊?賢?嚗inMind+yfinance ??⊿?嚗?
    鞈?靘?嚗?. TWSE OpenAPI ?渲?嚗???NAV+撣+?滯?寧?嚗?
              2. FinMind NAV history + df ? inner join嚗移蝣箸??撠?
              3. yfinance info navPrice
    """
    import pandas as _pd_prem
    import re as _re_prem
    import datetime as _dt_prem
    _code_clean = ticker.replace('.TW', '').replace('.TWO', '') if ticker else ''
    _is_active_etf = bool(_re_prem.match(r'^\d{4,5}[A-Z]$', _code_clean))
    _ACTIVE_PREM_MAX = 2.0  # 銝餃?撘?ETF |prem| ?瑼鳴?頞??文? NAV stale

    def _prev_business_day(_d):
        _d2 = _d - _dt_prem.timedelta(days=1)
        while _d2.weekday() >= 5:   # 5=Sat, 6=Sun
            _d2 -= _dt_prem.timedelta(days=1)
        return _d2
    _PREV_BD = _prev_business_day(_dt_prem.date.today())

    _stale_payload = {'nav': None, 'price': None, 'premium_pct': None,
                      'warning': False, 'stale_nav': True}
    try:
        if ticker:
            _nav_hist = fetch_etf_nav_history(ticker, days=10)
            if not _nav_hist.empty and 'nav' in _nav_hist.columns:
                _last = _nav_hist.iloc[-1]

                # ?? 頝臬?A嚗WSE 撌脣??滯?寧?嚗?乩蝙????
                if 'premium_pct' in _nav_hist.columns:
                    _prem_val = _last.get('premium_pct')
                    _price_val = _last.get('price', None)
                    if _prem_val is not None and not _pd_prem.isna(_prem_val):
                        _pv = float(_prem_val)
                        if _is_active_etf and abs(_pv) > _ACTIVE_PREM_MAX:
                            print(f'[?滯??A/stale] {ticker}: prem={_pv}% > 簣{_ACTIVE_PREM_MAX}%')
                            return _stale_payload
                        _latest_nav = float(_last['nav'])
                        _pr = float(_price_val) if _price_val else (_latest_nav * (1 + _pv / 100))
                        print(f'[?滯??A] {ticker}: nav={_latest_nav} prem={_pv}% (TWSE?渲?)')
                        return {'nav': _latest_nav, 'price': round(_pr, 4),
                                'premium_pct': _pv, 'warning': _pv > 1.0}

                # ?? 頝臬?B嚗inMind NAV history + df Same-Date Inner Join ??
                # ??30?交楊?潦”?潛??蝎曄Ⅱ?交????摩嚗?蝯?雿?
                if not df.empty and 'Close' in df.columns:
                    _nav_df = _nav_hist[['date', 'nav']].copy()
                    _nav_df['date'] = _pd_prem.to_datetime(_nav_df['date']).dt.normalize()
                    _nav_df = _nav_df.set_index('date')
                    _price_s = df[['Close']].copy()
                    _price_s.index = _pd_prem.to_datetime(_price_s.index).normalize()
                    _merged = _nav_df.join(_price_s, how='inner').dropna()
                    if not _merged.empty:
                        _nav_date_used = _merged.index[-1]
                        _nav_d_only = _nav_date_used.date()
                        _price_latest = _price_s.index.max()
                        _gap_days = (_price_latest - _nav_date_used).days
                        if _gap_days >= 1:
                            print(f'[?滯??B/stale-G1] {ticker}: NAV={_nav_d_only} ?賢? {_gap_days}d')
                            return _stale_payload
                        # G3嚗?皞?甇亥敺???NAV ?拇??鈭斗??伐??? OK 雿擃?????
                        if _nav_d_only < _PREV_BD:
                            print(f'[?滯??B/stale-G3] {ticker}: NAV={_nav_d_only} < prev BD {_PREV_BD}')
                            return _stale_payload
                        _row = _merged.iloc[-1]  # ?餈?蝑??仿?撠?
                        _nav_v = float(_row['nav'])
                        _pr_v  = float(_row['Close'])
                        _prem  = round((_pr_v - _nav_v) / _nav_v * 100, 2)
                        if _is_active_etf and abs(_prem) > _ACTIVE_PREM_MAX:
                            print(f'[?滯??B/stale-G2] {ticker}: prem={_prem}% > 簣{_ACTIVE_PREM_MAX}%')
                            return _stale_payload
                        print(f'[?滯??B] {ticker}: date={_nav_d_only} nav={_nav_v} price={_pr_v} prem={_prem}%')
                        return {'nav': _nav_v, 'price': _pr_v,
                                'premium_pct': _prem, 'warning': _prem > 1.0,
                                'data_date': _nav_d_only}
                    else:
                        # ?/?????嚗??皞?goodinfo/TWSE/MoneyDJ)撣詨??蝑楊?潘?
                        # ?嗆?? yfinance ?嗥??銝?鈭斗???撠?銝?? join ?賜征??
                        # ?寧???唳楊??vs ??唳?扎?雿??? ?? 憭?瘨菔????)嚗?
                        # ?踹??輸??楊?潛′?迨?喋??敺???敺漱?瘛典潦?
                        _nav_df = _nav_df.sort_index()
                        _price_s = _price_s.sort_index()
                        _nav_last_d = _nav_df.index.max()
                        _price_last_d = _price_s.index.max()
                        _gap = abs((_price_last_d - _nav_last_d).days)
                        if _gap <= 4:
                            _nav_v = float(_nav_df['nav'].iloc[-1])
                            _pr_v  = float(_price_s['Close'].iloc[-1])
                            _prem  = round((_pr_v - _nav_v) / _nav_v * 100, 2)
                            if _is_active_etf and abs(_prem) > _ACTIVE_PREM_MAX:
                                print(f'[?滯??B2/stale-G2] {ticker}: prem={_prem}% > 簣{_ACTIVE_PREM_MAX}%')
                                return _stale_payload
                            _dd = min(_nav_last_d, _price_last_d).date()
                            print(f'[?滯??B2/???] {ticker}: nav??{_nav_last_d.date()} '
                                  f'?寞={_price_last_d.date()} gap={_gap}d '
                                  f'nav={_nav_v} price={_pr_v} prem={_prem}%')
                            return {'nav': _nav_v, 'price': _pr_v,
                                    'premium_pct': _prem, 'warning': _prem > 1.0,
                                    'data_date': _dd}
                        print(f'[?滯??B2] {ticker}: nav?亥??寞?賢榆 {_gap}d >4嚗???')

        print(f'[?滯?鉛 {ticker}: ??楝敺仃??? N/A')
    except Exception as _ep:
        import traceback as _tb_p; print(f'[?滯?鉛 ?航炊: {_ep}'); _tb_p.print_exc()
    return {'nav': None, 'price': None, 'premium_pct': None, 'warning': False}


def calc_avg_volume_20d(df: pd.DataFrame) -> float:
    """20 ?亙???撘菜嚗?⊥靘?1 撘?= 1000 ?∴???

    ?冽??yfinance df ?芰?嚗?憿???????頞喳? None??
    """
    try:
        if df is None or df.empty or 'Volume' not in df.columns:
            return None
        _vol = df['Volume'].tail(20).dropna()
        if len(_vol) < 5:
            return None
        return round(float(_vol.mean()) / 1000.0, 1)
    except Exception:
        return None


def calc_liquidity_score(df: pd.DataFrame, aum=None) -> dict:
    """瘚??抒??郎蝷綽??⊿??啗???嚗 Volume + AUM ?芰?嚗?

    Parameters
    ----------
    df  : ??Volume 甈? ETF ?寞 df嚗etch_etf_price ??喳嚗?
    aum : 閬芋嚗?啣馳??嚗???fetch_etf_info()['totalAssets']嚗one ?????

    ?文?嚗???湧???蝝?
      ? 甇?虜       avg_vol_20d >= 1000 撘?銝?aum >= 10 ??
      ? 瘚??批?撘? 500 <= avg_vol_20d < 1000 ??5 ??<= aum < 10 ??
      ? 瘚??折◢?? avg_vol_20d < 500 ??aum < 5 ??

    Returns
    -------
    dict {'level': '?/?/?', 'avg_vol_20d': float, 'reasons': [str, ...]}
        鞈?銝雲??{'level': '??, 'avg_vol_20d': None, 'reasons': ['鞈?銝雲']}
    """
    _avg = calc_avg_volume_20d(df)
    _reasons: list[str] = []
    if _avg is None:
        return {'level': '??, 'avg_vol_20d': None, 'reasons': ['鞈?銝雲']}

    _level = '?'
    if _avg < 500:
        _level = '?'
        _reasons.append(f'20?亙??? {_avg:,.0f} 撘蛛?< 500嚗?)
    elif _avg < 1000:
        _level = '?'
        _reasons.append(f'20?亙???{_avg:,.0f} 撘蛛?< 1000嚗?)

    try:
        if aum is not None and aum > 0:
            _aum_e = float(aum) / 1e8  # ??????
            if _aum_e < 5:
                _level = '?'
                _reasons.append(f'閬芋??{_aum_e:.1f} ??< 5嚗?)
            elif _aum_e < 10 and _level == '?':
                _level = '?'
                _reasons.append(f'閬芋 {_aum_e:.1f} ??< 10嚗?)
    except (TypeError, ValueError):
        pass

    if not _reasons:
        _reasons.append('瘚??扯?閬芋??頞?)
    return {'level': _level, 'avg_vol_20d': _avg, 'reasons': _reasons}


def calc_tracking_error(df: pd.DataFrame, bench_df: pd.DataFrame) -> float:
    """餈質馱隤文榆 = std(ETF?亙??- ?箸??亙?? ? ??52 ? 100"""
    try:
        if df.empty or bench_df.empty:
            return None
        etf_r   = df['Close'].pct_change().dropna()
        bench_r = bench_df['Close'].pct_change().dropna()
        common  = etf_r.index.intersection(bench_r.index)
        if len(common) < 20:
            return None
        diff = etf_r.loc[common] - bench_r.loc[common]
        return round(float(diff.std() * (252 ** 0.5) * 100), 2)
    except Exception:
        return None


def calc_mdd(df: pd.DataFrame) -> float:
    """?憭批???MDD(%)"""
    try:
        close    = df['Close']
        roll_max = close.cummax()
        return round(float(((close - roll_max) / roll_max * 100).min()), 2)
    except Exception:
        return None


def calc_cagr(df: pd.DataFrame) -> float:
    """撟游??梢??CAGR(%)"""
    try:
        if len(df) < 2:
            return 0.0
        days  = (df.index[-1] - df.index[0]).days
        if days < 30:
            return 0.0
        y     = days / 365.25
        start = float(df['Close'].iloc[0])
        end   = float(df['Close'].iloc[-1])
        return round(((end / start) ** (1 / y) - 1) * 100, 2)
    except Exception:
        return 0.0


def calc_sharpe(df: pd.DataFrame, rf: float = 5.33) -> float:
    """憭?潘?撟游?嚗f?身5.33% FEDFUNDS嚗?""
    try:
        ret     = df['Close'].pct_change().dropna()
        if len(ret) < 20:
            return 0.0
        ann_ret = float(ret.mean() * 252 * 100)
        ann_vol = float(ret.std() * (252 ** 0.5) * 100)
        return round((ann_ret - rf) / ann_vol, 2) if ann_vol > 0 else 0.0
    except Exception:
        return 0.0


def auto_detect_benchmark(ticker: str) -> str:
    t = ticker.upper()
    if t.endswith('.TW') or t.endswith('.TWO'):
        return '0050.TW'
    return '^GSPC'


@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=50, show_spinner=False)
def compute_etf_peer_ranking(ticker: str, periods: tuple = (63, 126, 252)) -> dict:
    """ETF ??餈?3M/6M/1Y ?梢??嚗蜇?梢??荔???yfinance Adj Close嚗?

    Parameters
    ----------
    ticker : str
        ?格? ETF 隞??嚗? '0050.TW'??
    periods : tuple[int, ...]
        鈭斗??亥?蝒??身 63=3M??26=6M??52=1Y嚗?

    Returns
    -------
    dict
      ?賭葉嚗63: {'self_ret': float, 'peer_median': float, 'percentile': float,
                  'peer_count': int}, 126: {...}, 252: {...},
             'category': str, 'peers': list[str]}
      ?∪???{'_err': '??鞈?銝雲', 'category': ''}
    """
    from etf_categories import get_peers, get_category_name
    _peers = get_peers(ticker)
    _category = get_category_name(ticker)
    if len(_peers) < 3:
        return {'_err': '??鞈?銝雲', 'category': _category, 'peers': _peers}
    _all = [ticker] + _peers
    _result: dict = {'category': _category, 'peers': _peers}
    try:
        _hist = yf.download(_all, period='2y', auto_adjust=True,
                            progress=False, threads=False)
        # yf.download 憭?ticker ??MultiIndex (column 0=field, 1=ticker)嚗銝??撟?
        if isinstance(_hist.columns, pd.MultiIndex):
            _close = _hist['Close']
        else:
            _close = _hist[['Close']].rename(columns={'Close': _all[0]})
        if _close.empty:
            return {'_err': 'yfinance ???啣??, 'category': _category, 'peers': _peers}
        for _p in periods:
            if len(_close) < _p + 1:
                _result[_p] = {'_err': f'鞈?銝雲 {_p} ??}
                continue
            _window = _close.iloc[-(_p + 1):]
            _rets = (_window.iloc[-1] / _window.iloc[0] - 1.0) * 100.0
            _rets = _rets.dropna()
            if ticker not in _rets.index or len(_rets) < 3:
                _result[_p] = {'_err': '??璅?銝雲'}
                continue
            _self = float(_rets[ticker])
            _peer_only = _rets.drop(ticker)
            _median = float(_peer_only.median())
            # percentile嚗elf 擃 N% ??嚗 strict less 閮?
            _pct = float((_peer_only < _self).sum()) / len(_peer_only) * 100.0
            _result[_p] = {
                'self_ret': round(_self, 2),
                'peer_median': round(_median, 2),
                'percentile': round(_pct, 1),
                'peer_count': len(_peer_only),
            }
        return _result
    except Exception as _e:
        import traceback as _tb_pr
        print(f'[peer-rank] {ticker} ??{type(_e).__name__}: {_e}')
        _tb_pr.print_exc()
        return {'_err': f'{type(_e).__name__}', 'category': _category, 'peers': _peers}


# ??????????????????????????????????????????????????????????????
# ???摨佗?Holdings Overlap嚗?蝝撘??嗅??其?鞈?
# ??????????????????????????????????????????????????????????????
def _canonical_holding_key(name) -> str:
    """???∪?蝔望迤閬??楊靘?瘥??具? key??

    銝?靘???隞質?迂?澆?銝?嚗?
      - yfinance嚗?銝剜?敺?嚗蝛 (2330)??
      - ?啁 Yahoo / MoneyDJ嚗蝛??
    ?亦?亦??銝脫?撠????航蟡冽?鋡怎?????overlap 隤文??0%??
    ?ㄐ蝯曹??餅???隞?Ⅳ)?????征?賬?撠神嚗??抵?敺???
    """
    import re as _re_c
    _s = str(name or '').strip()
    _s = _re_c.sub(r'[嚗?]\s*\d{3,6}[A-Za-z]?\s*[)嚗', '', _s)  # ?颱誨蝣潭??
    _s = _re_c.sub(r'\s+', '', _s).replace('?', '')          # ?餌征?踝??怠敶ｇ?
    return _s.lower()


def _canonical_weight_map(h) -> dict:
    """??{???? 甈?} 頧? {甇????key: 甈?}嚗? key ?詨??脣?嚗?""
    _out = {}
    for _k, _v in (h or {}).items():
        _ck = _canonical_holding_key(_k)
        if not _ck:
            continue
        try:
            _out[_ck] = _out.get(_ck, 0.0) + float(_v)
        except (TypeError, ValueError):
            continue
    return _out


def calc_holdings_overlap_pct(h1, h2):
    """甈? Overlap%嚗 ETF ?勗????頛?甈??蜇?平??皞?鞈芣扳?璅?

    ?砍?嚗?min(w_A_i, w_B_i)  for i in (A ??B)

    隤?嚗瑼?ETF ???航蟡剁?A ??5%? ??10% ???芰? 5%嚗??????
    蝯? 0-100%嚗?潸?擃”蝷箇????釭??

    Parameters
    ----------
    h1, h2 : dict[str, float] | None
        ?????甈??曉?瘥?憒?5.0 銵函內 5%嚗one/蝛?dict ??0.0??
        ??誑 `_canonical_holding_key` 甇????瘥?嚗楊靘?嚗/銝隞?Ⅳ嚗??臬?銝?

    Returns
    -------
    float  0-100嚗歇?鈭?啣??賊? 2 雿?
    """
    if not h1 or not h2:
        return 0.0
    _m1 = _canonical_weight_map(h1)
    _m2 = _canonical_weight_map(h2)
    _common = set(_m1.keys()) & set(_m2.keys())
    if not _common:
        return 0.0
    _overlap = 0.0
    for _k in _common:
        _overlap += min(_m1[_k], _m2[_k])
    return round(min(_overlap, 100.0), 2)


def calc_jaccard_overlap(h1, h2):
    """Jaccard ????嚗A ??B| / |A ??B| ? 100%??

    ?芰???瘝????航蟡具?**摰敹賜甈?**???頛??⊥??桅爸?嗆?阡??
    ??`calc_holdings_overlap_pct` 鈭?嚗?
      - Jaccard 擃?+ Overlap 雿??????瑕?雿???撣榆?啣之
      - Jaccard 雿?+ Overlap 擃???撠?勗??鋡恍?憯?憸券?葉嚗?
      - ?抵擃????釭?扳扔擃????撌?

    Parameters
    ----------
    h1, h2 : dict[str, float] | None | iterable
        ?芸? keys嚗???one/蝛箏? 0.0??

    Returns
    -------
    float  0-100嚗歇?鈭?啣??賊? 2 雿?
    """
    if not h1 or not h2:
        return 0.0
    _s1 = {_canonical_holding_key(_k) for _k in (h1.keys() if hasattr(h1, 'keys') else h1)}
    _s2 = {_canonical_holding_key(_k) for _k in (h2.keys() if hasattr(h2, 'keys') else h2)}
    _s1.discard('')
    _s2.discard('')
    _union = _s1 | _s2
    if not _union:
        return 0.0
    return round(len(_s1 & _s2) / len(_union) * 100, 2)


def build_holdings_overlap_matrix(holdings_dict, method='weight'):
    """撱箇? ETF ? ETF ????拚嚗?-100%嚗?閫?? 100??

    Parameters
    ----------
    holdings_dict : dict[str, dict[str, float] | None]
        key=ETF ticker嚗alue=閰?ETF ??隞質摮嚗alc_holdings_overlap_pct ?撓?伐???
        value ??None / 蝛箄?閰?ETF 撠?銵??冽? NaN嚗I 蝡舫＊蝷箇?啗 N/A嚗?
    method : 'weight' | 'jaccard'
        'weight' ????`calc_holdings_overlap_pct`嚗平??皞?
        'jaccard' ????`calc_jaccard_overlap`嚗?????

    Returns
    -------
    pandas.DataFrame  N?N 撠迂?拚嚗ndex/columns ?賣 ticker??
    """
    import pandas as _pd
    import numpy as _np
    _tickers = list(holdings_dict.keys())
    _func = calc_jaccard_overlap if method == 'jaccard' else calc_holdings_overlap_pct
    _n = len(_tickers)
    _mat = _np.full((_n, _n), _np.nan, dtype=float)
    for _i, _ta in enumerate(_tickers):
        _ha = holdings_dict.get(_ta)
        if not _ha:
            continue
        _mat[_i, _i] = 100.0
        for _j in range(_i + 1, _n):
            _tb = _tickers[_j]
            _hb = holdings_dict.get(_tb)
            if not _hb:
                continue
            _v = _func(_ha, _hb)
            _mat[_i, _j] = _v
            _mat[_j, _i] = _v
    return _pd.DataFrame(_mat, index=_tickers, columns=_tickers)


# ??????????????????????????????????????????????????????????????
# 銝餃? ETF 撘勗摨行炎皜穿?PR ??claude/etf-weakness-manager嚗?
# Gemini ?摩嚗之頝?頝?瘥之?斗楛 + ???撞敺?憭抒??+ ??摮?撓??= 閰脫?
# ??????????????????????????????????????????????????????????????
def calc_weakness_metrics(etf_returns, bench_returns):
    """銝餃? ETF 撘勗摨行敹?璅?蝝撘???I/O嚗?

    頛詨?拇??亙?砍???pct_change 撌脩?憟踝?嚗?朣?閮?嚗?
      - 憭扯?撘勗??down_ratio: 憭抒頝銝?ETF 頝瘛梁?瘥? (0-100%)
      - ??撘勗??up_ratio:   憭抒瞍脫銝?ETF 瞍脫?Ｙ?瘥? (0-100%)
      - 摮??祈撓?日????quarter_lose_streak: ??quarter ?璅?
        ?餈?N 摮?ETF 摮???< bench 摮??祉??????餈迤??
      - Tracking error te_pct: ?亙?砍榆?僑??皞榆 (%)

    Returns
    -------
    dict 7 ??key嚗???< 30 憭???{'_err': 'insufficient_data', 'sample': N}
    """
    import pandas as _pd_w
    import numpy as _np_w
    if etf_returns is None or bench_returns is None:
        return {'_err': 'none_input'}
    _df = _pd_w.concat([etf_returns, bench_returns], axis=1, keys=['etf', 'bench']).dropna()
    if len(_df) < 30:
        return {'_err': 'insufficient_data', 'sample': int(len(_df))}

    _down = _df[_df['bench'] < 0]
    _up = _df[_df['bench'] > 0]
    _down_n = len(_down)
    _up_n = len(_up)
    _down_lose = int((_down['etf'] < _down['bench']).sum()) if _down_n > 0 else 0
    _up_lose = int((_up['etf'] < _up['bench']).sum()) if _up_n > 0 else 0
    _down_ratio = round(_down_lose / _down_n * 100, 1) if _down_n > 0 else 0.0
    _up_ratio = round(_up_lose / _up_n * 100, 1) if _up_n > 0 else 0.0

    # 摮??穿?cumprod 蝞?quarterly compound return
    _etf_q = (1 + _df['etf']).resample('QE').prod() - 1
    _bench_q = (1 + _df['bench']).resample('QE').prod() - 1
    _q_cmp = _pd_w.concat([_etf_q, _bench_q], axis=1, keys=['etf', 'bench']).dropna()
    _streak = 0
    for _i in range(len(_q_cmp) - 1, -1, -1):
        if _q_cmp['etf'].iloc[_i] < _q_cmp['bench'].iloc[_i]:
            _streak += 1
        else:
            break

    _diff = _df['etf'] - _df['bench']
    _te = float(_diff.std() * _np_w.sqrt(252) * 100) if _diff.std() > 0 else 0.0

    return {
        'down_days': _down_n,
        'down_loss_days': _down_lose,
        'down_ratio': _down_ratio,
        'up_days': _up_n,
        'up_miss_days': _up_lose,
        'up_ratio': _up_ratio,
        'quarter_lose_streak': _streak,
        'te_pct': round(_te, 2),
        'sample': len(_df),
    }


def _auto_bench_for_etf(ticker: str) -> str:
    """?寞? ETF ticker suffix ?芸???benchmark??

    .TW / .TWO / 蝝摮???^TWII嚗?∪?甈?嚗隞???^GSPC嚗&P 500嚗?
    """
    _t = (ticker or '').upper().strip()
    if _t.endswith('.TW') or _t.endswith('.TWO') or _t.replace('.', '').isalnum() and any(c.isdigit() for c in _t[:4]):
        _code = _t.replace('.TW', '').replace('.TWO', '')
        if _code and _code[0].isdigit():
            return '^TWII'
    return '^GSPC'


@st.cache_data(ttl=CACHE_TTL["tech_indicators"], max_entries=50, show_spinner=False)
def compute_etf_weakness_row(ticker: str, name: str = '',
                              bench_ticker: str | None = None,
                              period: str = '1y') -> dict:
    """擃?蝯?嚗? ETF / benchmark ?寞 ??蝞?returns ???澆 calc_weakness_metrics
    + ???犖???喟策 UI 雿輻???dict??
    """
    from etf_fetch import is_active_etf, fetch_etf_manager
    _bench = bench_ticker or _auto_bench_for_etf(ticker)
    _is_act = is_active_etf(ticker)

    _row = {
        '隞??': ticker, '?迂': name or ticker,
        '銝餉◤??: '銝餃?撘? if _is_act else '鋡怠?撘?,
        'benchmark': _bench,
        '蝬?鈭?: '??, '隞餅?': '??,
        '憭扯?撘勗??': None, '??撘勗??': None,
        '???摮?': None, 'TE%': None, '璅???: 0,
        '??': '???芣炎皜?, '??撱箄降': '??,
    }
    if not _is_act:
        _row['??'] = '??鋡怠?餈質馱???葫撘勗'
        _row['??撱箄降'] = '?瑟???嚗?撖?tracking error'

    try:
        _etf_df = fetch_etf_price(ticker, period=period)
        _bench_df = fetch_etf_price(_bench, period=period)
        if _etf_df.empty or _bench_df.empty:
            _row['??'] = '???寞鞈?銝雲'
            return _row
        _er = _etf_df['Close'].pct_change()
        _br = _bench_df['Close'].pct_change()
        _m = calc_weakness_metrics(_er, _br)
        if '_err' in _m:
            _row['??'] = f'??{_m.get("_err", "calc_err")} (n={_m.get("sample", 0)})'
            return _row
        _row['憭扯?撘勗??'] = _m['down_ratio']
        _row['??撘勗??'] = _m['up_ratio']
        _row['???摮?'] = _m['quarter_lose_streak']
        _row['TE%'] = _m['te_pct']
        _row['璅???] = _m['sample']
    except Exception as _e:
        print(f'[weakness/{ticker}] {type(_e).__name__}: {_e}')
        _row['??'] = f'????憭望?嚗type(_e).__name__}'
        return _row

    _tenure_days = None
    # 蝬?鈭?隞餅?嚗????ETF ?賣?嚗TF 銵函???犖?賊?嚗◤????銋澆??仿?嚗?
    # 瘚瑕? ETF嚗? BND嚗oneyDJ ?∟??????芰???撠?∩誨? proxy 隢???
    if ticker.endswith(('.TW', '.TWO')):
        _mg = fetch_etf_manager(ticker)
        if _mg:
            _row['蝬?鈭?] = _mg.get('name', '??)
            _tenure_days = _mg.get('tenure_days')
            if _tenure_days is not None:
                _row['隞餅?'] = (f'{_tenure_days // 30} ??' if _tenure_days < 365
                              else f'{_tenure_days / 365:.1f} 撟?)
            elif _mg.get('since'):
                _row['隞餅?'] = f'??{_mg["since"]}'

    if _is_act:
        _down = _row['憭扯?撘勗??'] or 0
        _up = _row['??撘勗??'] or 0
        _streak = _row['???摮?'] or 0
        _new_manager = isinstance(_tenure_days, int) and _tenure_days < 180
        if _streak >= 2:
            _row['??'] = f'? ???{_streak}摮?撓??
            _row['??撱箄降'] = ('???啁??犖 <6 ???策??'
                              if _new_manager
                              else '??憭抒鋡怠?撘?ETF嚗? 0050嚗?)
        elif _down > 60 and _up > 60:
            _row['??'] = '? ??撘勗'
            _row['??撱箄降'] = '餈?銵函???賢?憭抒嚗?撖?1-2 摮?
        elif _down > 60:
            _row['??'] = '? 憭扯?撘勗'
            _row['??撱箄降'] = '銝??脩戌??頞喉?瘜冽?'
        elif _up > 60:
            _row['??'] = '? ???∪?'
            _row['??撱箄降'] = '??餈賭?銝之?歹?蝮暹??賢?'
        else:
            _row['??'] = '? 擃釭甇?虜'
            _row['??撱箄降'] = '蝥閫撖?

    return _row

