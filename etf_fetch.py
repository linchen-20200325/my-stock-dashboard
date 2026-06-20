from data_config import CACHE_TTL
"""
ETF ??撅歹?fetch layer嚗?
敺?etf_dashboard.py ?賢?? I/O ?賢?嚗??/ ? / ?箸鞈? / 鞎餌??/ NAV / 憿瞍脰?
?∪?其?鞈湛??航◤ etf_calc?tf_render?ab_* 璅∠?摰 import??
"""
import streamlit as st
import pandas as pd
import yfinance as yf


def _fetch_news_for(ticker: str, name: str = "", n: int = 4) -> str:
    """???/ETF ?賊??啗?嚗??單撘?摮葡?仃???蝛箏?銝脯?
    韏?NAS 銝剔匱蝡???Squid proxy(撣?CONSENT cookie 蝜?Google ???? ???湧??""
    try:
        import feedparser as _fp
        import html as _h
        from urllib.parse import quote as _uq
    except ImportError:
        return ""
    try:
        from proxy_helper import fetch_url as _furl, nas_relay_fetch as _nasf
    except ImportError:
        _furl = _nasf = None
    _feeds = [
        f'https://news.google.com/rss/search?q={_uq(f"{ticker} {name}".strip())}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant',
        f'https://news.google.com/rss/search?q={_uq(f"Taiwan ETF {ticker}".strip())}&hl=en-US&gl=US&ceid=US:en',
    ]
    _hdr = {'Cookie': 'CONSENT=YES+cb; SOCS=CAI',
            'Accept': 'application/rss+xml, application/xml;q=0.9, */*;q=0.5'}
    _out = []
    for _url in _feeds:
        try:
            _fd = None
            if _nasf is not None:
                _rr = _nasf(_url, timeout=15)
                if _rr is not None:
                    _fd = _fp.parse(_rr.content)  # 擗?bytes嚗??str+encoding 摰??鋡急?閫??嚗?
            if (_fd is None or not getattr(_fd, 'entries', None)) and _furl is not None:
                _rs = _furl(_url, headers=_hdr, timeout=10)
                if _rs is not None:
                    _fd = _fp.parse(_rs.content)
            if _fd is None or not getattr(_fd, 'entries', None):
                _fd = _fp.parse(_url, request_headers=_hdr)
            for _e in _fd.entries:
                _t = _h.unescape(_e.get('title', '')).strip()
                _p = str(_e.get('published', ''))[:10]
                if _t:
                    _out.append(f'- {_t}嚗_p}嚗?)
                if len(_out) >= n:
                    break
        except Exception:
            pass
        if len(_out) >= n:
            break
    return '\n'.join(_out[:n]) if _out else '嚗?∠???'


# ?? MK 閬 璇辣 B嚗??ETF ?潸??孵??扯”嚗?潛?潭炎皜穿???????
# ?啁撣貉? ETF ?潸??對?憭 10/15/20/30/40 ??嚗??ETF 憭 40 ??
_TW_ETF_LAUNCH_PRICE = {
    '0050': 36.98, '0051': 25.57, '0052': 36.99, '0053': 22.20,
    '0055': 12.95, '0056': 25.20, '0057': 38.10,
    '006203': 25, '006204': 30, '006208': 30, '00646': 20,
    '00692': 20, '00701': 20, '00713': 20, '00730': 20,
    '00731': 20, '00733': 20, '00735': 20, '00850': 20,
    '00878': 15, '00881': 15, '00882': 15, '00891': 15,
    '00892': 15, '00893': 15, '00895': 15, '00896': 15,
    '00897': 15, '00898': 15, '00899': 15, '00900': 15,
    '00901': 15, '00902': 15, '00903': 15, '00904': 15,
    '00905': 15, '00907': 15, '00910': 15, '00911': 15,
    '00912': 15, '00913': 15, '00915': 15, '00916': 15,
    '00918': 15, '00919': 20, '00920': 15, '00921': 15,
    '00922': 15, '00923': 15, '00924': 15, '00925': 15,
    '00927': 15, '00929': 15, '00930': 15, '00932': 15,
    '00934': 10, '00935': 10, '00936': 10, '00939': 15,
    '00940': 10, '00941': 10, '00942B': 15, '00943': 15,
    '00944': 10, '00945B': 15, '00946': 10, '00947': 10,
    # ?萄 ETF 憭 40 ?絲憪?
    '00679B': 40, '00687B': 40, '00696B': 40, '00697B': 40,
    '00710B': 40, '00711B': 40, '00712':  20, '00714':  30,
    '00718B': 40, '00719B': 40, '00720B': 40, '00721B': 40,
    '00722B': 40, '00723B': 40, '00724B': 40, '00725B': 40,
    '00726B': 40, '00727B': 40, '00772B': 40, '00773B': 40,
    '00777B': 40, '00778B': 40, '00779B': 40, '00780B': 40,
    '00781B': 40, '00782B': 40, '00783B': 40, '00784B': 40,
    '00785B': 40, '00786B': 40, '00787B': 40, '00788B': 40,
    '00795B': 40, '00834B': 40, '00836B': 40, '00837B': 40,
    '00840B': 40, '00845B': 40, '00846B': 40, '00847B': 40,
    '00848B': 40, '00849B': 40, '00853B': 40, '00857B': 40,
    '00859B': 40, '00860B': 40, '00862B': 40, '00863B': 40,
    '00864B': 40, '00865B': 40, '00867B': 40, '00870B': 40,
    '00883B': 40, '00890B': 40, '00937B': 40,
}


def _get_etf_launch_price(ticker: str, df: "pd.DataFrame|None" = None):
    """?? ETF ?潸??對??冽 MK 閬璇辣 B ?渡瑼Ｘ葫嚗?

    ?芸?摨?
    1. ?批遣?啁 ETF 撠銵剁??蝎暹?嚗?
    2. df 擐漱??嗥?對?撌脤????荔??? fallback 隡啁?嚗?

    Returns
    -------
    float | None
    """
    _code = (ticker or '').replace('.TWO', '').replace('.TW', '').upper().strip()
    _v = _TW_ETF_LAUNCH_PRICE.get(_code)
    if _v is not None:
        return float(_v)
    # fallback嚗 df 蝚砌?蝑?支摯蝞??蝢 ETF / ?芣??
    try:
        if df is not None and len(df) > 0:
            return float(df['Close'].iloc[0])
    except Exception:
        pass
    return None


# v18.228 P1-S1嚗etch_etf_price 頝?tab period ?葉
# ? cache key = (ticker, period)嚗?瑼?ETF ??1y/5y/10y 銝? period ?? 2~3 甈～?
# ?寧?桐? 'max' fetch + 閮擃??嚗ache key ?芸 ticker??
_PERIOD_TO_DAYS = {
    '5d': 7, '1mo': 31, '3mo': 93, '6mo': 186,
    '1y': 365, '2y': 365 * 2, '3y': 365 * 3, '5y': 365 * 5,
    '10y': 365 * 10, 'ytd': 366, 'max': None,
}


@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=20)
def _fetch_etf_price_max(ticker: str) -> pd.DataFrame:
    """?梁摨惜 ??銝甈⊥? period='max'嚗? fetch_etf_price ????

    v18.228 ?葉??portfolio / single / grp_compare / backtest 頝?tab ??
    ETF 敺?2~3 甈?yfinance call ??1 甈∴?cache key ?芸 ticker嚗?
    """
    try:
        df = yf.Ticker(ticker).history(period='max', auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df.ffill()
    except Exception as e:
        st.error(f'???⊥??? {ticker} ?寞嚗e}')
        return pd.DataFrame()


def fetch_etf_price(ticker: str, period: str = '5y') -> pd.DataFrame:
    """?? ETF 甇瑕?寞嚗uto_adjust=True ??甈嚗?

    v18.228 韏瑟?箏??'max' 摨惜 + 閮擃???偷蝡?霈??澆蝡?0 ?孵???
    """
    df = _fetch_etf_price_max(ticker)
    if df.empty:
        return df
    days = _PERIOD_TO_DAYS.get(period, 365 * 5)
    if days is None or len(df) == 0:
        return df
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df.loc[df.index >= cutoff]


@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=10)
def fetch_etf_dividends(ticker: str) -> pd.Series:
    """?? ETF 甇瑕?"""
    try:
        divs = yf.Ticker(ticker).dividends
        if divs.empty:
            return pd.Series(dtype=float)
        divs.index = pd.to_datetime(divs.index).tz_localize(None)
        return divs
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=300, show_spinner=False)
def fetch_etf_meta_moneydj(ticker: str) -> dict:
    """敺?MoneyDJ Basic0004 銝甈∪?敺??ETF metadata嚗粥 NAS Squid + 銝剔匱蝡???

    ?箔??閬?yfinance.info ??Streamlit Cloud 蝬虜鋡?Yahoo 瘚瑕? IP 撠?
    ??rate limit嚗oneyDJ Basic0004 韏?NAS 銝剔匱蝡?摰嗥?啁 IP嚗蝛拙???
    ?啗 ETF ??AUM / 鞎餌??蝬?鞎?+ 靽恣鞎鳴?/ 璅?? / 銝剜???

    Returns
    -------
    dict  甈?蝻箸???None嚗憭望???{}
        keys: zh_name / aum_twd / expense / manager_fee /
              custodian_fee / underlying_index
    """
    import re as _re_meta
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return {}
    if '.' not in _t:
        _t = f'{_t}.TW'

    _url = f'https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={_t}'
    try:
        from proxy_helper import fetch_url as _fu_meta
        _r = _fu_meta(_url, headers={'Referer': 'https://www.moneydj.com/'},
                      timeout=12, attempts=2)
        if _r is None or _r.status_code != 200:
            _code = _r.status_code if _r is not None else 'None'
            print(f'[MDJ/meta] {_t}: HTTP {_code}嚗 NAS 銝剔匱?仃??')
            return {}
        _r.encoding = 'utf-8'
        _txt = _r.text
    except Exception as _e:
        print(f'[MDJ/meta] {_t}: {type(_e).__name__}: {_e}')
        return {}

    _out: dict = {}

    # 1. 銝剜???敺?<title> ?瑕?擐挾嚗?
    _m = _re_meta.search(
        r'<title>\s*([^<\-]{2,30}?)\s*-\s*[0-9]{4,5}[A-Z]?\.TW\s*-', _txt)
    if _m:
        _name = _m.group(1).strip()
        if any('銝' <= _c <= '橦? for _c in _name):
            _out['zh_name'] = _name

    # 2. ?粹?閬芋嚗? ????
    _m = _re_meta.search(
        r'(?:?粹?閬芋|鞈閬芋|瘛刻???[^\d]{0,30}?'
        r'(\d{1,5}(?:,\d{3})*(?:\.\d+)?)\s*??, _txt)
    if _m:
        try:
            _out['aum_twd'] = float(_m.group(1).replace(',', '')) * 1e8
        except ValueError:
            pass

    # 3-4. 蝬?鞎?/ 靽恣鞎鳴?% ??瘥?嚗?
    # MoneyDJ 璅惜憭???祥(%)???潭??%)嚗? regex ?◤璅惜??% ?游?嚗?
    # ?誑 _html_kv_pairs ?脣??潮?撠銝鳴????犖閫??瘜??egex ?箄???
    _kv_meta = _html_kv_pairs(_txt)

    def _pct_ratio(_raw):
        """摮葡?摮蒂頧?靘?1.00 ??0.01嚗??⊥摮? None??""
        _mm = _re_meta.search(r'(\d+(?:\.\d+)?)', str(_raw).replace(',', ''))
        if not _mm:
            return None
        try:
            return float(_mm.group(1)) / 100.0
        except ValueError:
            return None

    for _labels, _key in ((('蝬?鞎?, '蝞∠?鞎?), 'manager_fee'),
                          (('靽恣鞎?,), 'custodian_fee')):
        _v = None
        for _k, _vv in _kv_meta.items():               # KV 銝餉楝敺?
            if any(_lb in _k for _lb in _labels):
                _v = _pct_ratio(_vv)
                if _v is not None:
                    break
        if _v is None:                                  # regex ??
            for _lb in _labels:
                _m = _re_meta.search(rf'{_lb}[^\d%]{{0,30}}?(\d+(?:\.\d+)?)\s*%', _txt)
                if _m:
                    _v = _pct_ratio(_m.group(1))
                    break
        if _v is not None:
            _out[_key] = _v

    # 5. ??蝮質祥?函?嚗???+ 靽恣嚗??亙?銝??????嗆活
    if 'manager_fee' in _out and 'custodian_fee' in _out:
        _out['expense'] = round(_out['manager_fee'] + _out['custodian_fee'], 6)
    elif 'manager_fee' in _out:
        _out['expense'] = _out['manager_fee']
    else:
        # ??嚗?蜇鞎餌???扳鞎餌?銝甈?嚗V ?芸? ??regex嚗?
        for _k, _vv in _kv_meta.items():
            if any(_lb in _k for _lb in ('蝮質祥?函?', '?扳鞎餌??, '?批鞎餌??, '鞎餌??)):
                _ev = _pct_ratio(_vv)
                if _ev is not None:
                    _out['expense'] = _ev
                    break
        if 'expense' not in _out:
            _m = _re_meta.search(
                r'(?:蝮質祥?函?|?扳鞎餌??批鞎餌?鞎餌??[^\d%]{0,30}?(\d+(?:\.\d+)?)\s*%',
                _txt)
            if _m:
                _ev = _pct_ratio(_m.group(1))
                if _ev is not None:
                    _out['expense'] = _ev

    # 6. 餈質馱?嚗? fetch_etf_underlying_index ??regex 憸冽嚗TML entity ??瘣?
    _txt_c = (_txt.replace('&nbsp;', ' ').replace('&#160;', ' ')
                  .replace('&amp;', '&').replace('?', ' '))
    _m = _re_meta.search(
        r'(?:餈質馱|璅?|撠?)\s*?[^銝-橦澤-Za-z\d]{0,40}?'
        r'([銝-橦澤-Za-z0-9 &\.\-嚗?嚗?()]{4,80})', _txt_c)
    if _m:
        _idx = _m.group(1).strip().rstrip('嚗?????')
        if 4 <= len(_idx) <= 80 and not any(b in _idx for b in (
                '餈質馱隤文榆', '??∠巨??, '????, 'nbsp', 'amp;')):
            _out['underlying_index'] = _idx

    if _out:
        print(f'[MDJ/meta] OK {_t} = {list(_out.keys())}')
    else:
        print(f'[MDJ/meta] {_t}: 200 雿甈??寥?')
    return _out


@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=10)
def fetch_etf_info(ticker: str) -> dict:
    """?? ETF ?箸鞈?嚗祥?函? / Beta / AUM嚗?

    yfinance.info 銝餅?嚗 Beta?絲憭?ETF 敹?嚗? MoneyDJ Basic0004 鋆?
    AUM/expense嚗finance 瘚瑕? IP 蝬虜鋡急????雿??啗 ETF only嚗?
    """
    try:
        _info = yf.Ticker(ticker).info or {}
    except Exception:
        _info = {}

    # 鋆?嚗finance.info 蝛箸?蝻?AUM/expense ??敺?MoneyDJ Basic0004 fetch
    _t = (ticker or '').upper()
    _is_tw = _t.endswith('.TW') or _t.endswith('.TWO')
    if _is_tw and (not _info.get('totalAssets') or not _info.get('expenseRatio')):
        _meta = fetch_etf_meta_moneydj(ticker)
        if _meta:
            if not _info.get('totalAssets') and _meta.get('aum_twd'):
                _info['totalAssets'] = _meta['aum_twd']
            if not _info.get('expenseRatio') and _meta.get('expense'):
                _info['expenseRatio'] = _meta['expense']
            if not _info.get('annualReportExpenseRatio') and _meta.get('expense'):
                _info['annualReportExpenseRatio'] = _meta['expense']
            # longName 鋆葉??嚗finance 憭?望?嚗?
            if _meta.get('zh_name') and not any(
                    '銝' <= _c <= '橦? for _c in str(_info.get('longName', ''))):
                _info['longName'] = _meta['zh_name']
    return _info


def fetch_sitca_expense_ratio(ticker: str, *, attempts: int = 1):
    """敺?SITCA ?縑?“?祆????ETF ?扳鞎餌??Primary嚗絲憭?IP 韏?NAS proxy嚗?

    URL: https://www.sitca.org.tw/ROC/Industry/IN2211.aspx?pid=IN2222_01

    Returns
    -------
    float | None  瘥?敶Ｗ?嚗?.0036 = 0.36%嚗??曆???ticker ???仃?? None??
    """
    from proxy_helper import fetch_url as _fu_sit
    import pandas as _pd_sit, re as _re_sit
    _t = (ticker or '').replace('.TW', '').replace('.tw', '').strip()
    # 銝餃?撘?ETF 敺韌摮?嚗?0982A??0980A??0406A嚗? SITCA 銵冽?蝝摮誨????
    _t_num = _re_sit.sub(r'[A-Za-z]+$', '', _t)
    if not _t_num or not _t_num.isdigit():
        return None  # SITCA ?芣蝝??ETF ?詨?隞??嚗?050??0878?? 'A' 敺? 00982嚗?
    try:
        r = _fu_sit(
            'https://www.sitca.org.tw/ROC/Industry/IN2211.aspx?pid=IN2222_01',
            timeout=15, attempts=attempts,
        )
        if r is None or r.status_code != 200:
            return None
        r.encoding = 'utf-8'
        # ASP.NET ??虜銝撘萇蜇鞎餌?”嚗?銵券閰行?怒誨???祥?函???雿???撐
        tables = _pd_sit.read_html(r.text)
        # ticker 璅????餅? leading 0嚗祥 pandas ??"0050" parse ??int 50 ??荔?
        _tn = _t_num.lstrip('0') or '0'
        for tbl in tables:
            # 瘜冽?嚗olumn ?航??MultiIndex tuple嚗?撠 str(c)嚗??潛?隞?c
            code_col = next((c for c in tbl.columns
                             if any(k in str(c) for k in ('隞??', 'ETF', 'Code'))), None)
            rate_col = next((c for c in tbl.columns
                             if '鞎餌?? in str(c) or '鞎餌瘥?' in str(c)), None)
            if code_col is None or rate_col is None:
                continue
            # ?? leading-zero 摰孵?嚗ell 銋?strip leading 0 敺?撠?
            _digits = tbl[code_col].astype(str).str.replace(r'\D', '', regex=True)
            row = tbl[_digits.where(_digits != '', '0').str.lstrip('0').replace('', '0') == _tn]
            if row.empty:
                continue
            raw = str(row[rate_col].iloc[0])
            m = _re_sit.search(r'(\d+(?:\.\d+)?)', raw)
            if not m:
                continue
            v = float(m.group(1))
            # SITCA 銵冽?詨?撣貉?撌脫?曉?瘥?0.36 = 0.36%嚗?璅?????靘???
            print(f'[SITCA/expense] ??{_t} = {v}% (col={rate_col})')
            return v / 100.0
        print(f'[SITCA/expense] ?? {_t} ?芣?啁泵??column ?”??(tables={len(tables)})')
        return None
    except Exception as e:
        print(f'[SITCA/expense] ??{_t}: {type(e).__name__}: {e}')
        return None


def fetch_moneydj_expense_ratio(ticker: str):
    """敺?MoneyDJ ETF Basic0004 ????祥 + 靽恣鞎颯蜇鞎餌??蝘?/撌脖?撣?ETF ?嚗?

    URL: https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid=XXXX.TW

    Returns
    -------
    float | None  瘥?敶Ｗ?嚗?.0036 = 0.36%嚗??曆??唳???憭望???None??
    """
    import re as _re_mdje
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    # MoneyDJ etfid ?虜??'0050.TW' ?澆?嚗??詨?鋆?.TW
    if _t.isdigit():
        _t = f'{_t}.TW'
    _url = f'https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={_t}'
    try:
        # 韏?fetch_url嚗AS Squid ???湧???NAS 銝剔匱蝡?fallback嚗R #100嚗?
        from proxy_helper import fetch_url as _fu_mdje
        _r = _fu_mdje(_url, headers={'Referer': 'https://www.moneydj.com/'},
                      timeout=12, attempts=2)
        if _r is None or _r.status_code != 200:
            _code = _r.status_code if _r is not None else 'None'
            print(f'[MoneyDJ/expense] {_t}: HTTP {_code}嚗 NAS 銝剔匱?仃??')
            return None
        _txt = _r.text
        # ?湔????祥 X.XX%????蝞∟祥 X.XX%??閮?MoneyDJ Basic0004 銵冽撣訾誑 td 蝺?
        _mng = _re_mdje.search(r'蝬?鞎蒜^\d%]{0,30}?(\d+(?:\.\d+)?)\s*%', _txt)
        _cus = _re_mdje.search(r'靽恣鞎蒜^\d%]{0,30}?(\d+(?:\.\d+)?)\s*%', _txt)
        if _mng and _cus:
            _total = float(_mng.group(1)) + float(_cus.group(1))
            print(f'[MoneyDJ/expense] ??{_t} = {_total}% (mng={_mng.group(1)}+cus={_cus.group(1)})')
            return _total / 100.0
        # Fallback嚗?蜇鞎餌??/ ?批鞎餌?銝甈?
        _tot = _re_mdje.search(r'(?:蝮質祥?函?|?批鞎餌?鞎餌??[^\d%]{0,30}?(\d+(?:\.\d+)?)\s*%', _txt)
        if _tot:
            _v = float(_tot.group(1))
            print(f'[MoneyDJ/expense] ??{_t} = {_v}% (蝮質祥?函?甈?)')
            return _v / 100.0
        print(f'[MoneyDJ/expense] ?? {_t} ??～??祥/靽恣鞎?蝮質祥?函???雿?)
        return None
    except Exception as _e:
        print(f'[MoneyDJ/expense] ??{_t}: {type(_e).__name__}: {_e}')
        return None


def _fetch_holdings_yahoo_tw(symbol_yf: str):
    """?啁 Yahoo ?∪? ETF ??????Yahoo嚗絲憭?IP ?舐?????MoneyDJ 403嚗?

    URL嚗ttps://tw.stock.yahoo.com/quote/{symbol}/holding
    symbol_yf嚗finance ?澆?隞??嚗? '00980A.TW' / '0050.TW'嚗?
    閫?????伐?????批? JSON嚗?蝔?甈??蛛???BeautifulSoup 銵冽??銝剜???+ n.nn%嚗?
    ??{??迂: 甈?%} ??None嚗?銝 / 閫??銝嚗?
    """
    import re as _re_y
    try:
        from proxy_helper import fetch_url as _fu_y
    except Exception:
        return None
    _url = f'https://tw.stock.yahoo.com/quote/{symbol_yf}/holding'
    try:
        _r = _fu_y(_url, timeout=15, attempts=2)
    except Exception as _e:
        print(f'[Holdings/YahooTW] fetch ?啣虜 {symbol_yf}: {type(_e).__name__}: {_e}')
        return None
    if _r is None or getattr(_r, 'status_code', None) != 200:
        print(f'[Holdings/YahooTW] {symbol_yf} ?∪???/ ??200')
        return None
    try:
        _r.encoding = 'utf-8'
    except Exception:
        pass
    _html = _r.text or ''
    _out = {}
    # ?? 蝑 A嚗??Ｗ撋?JSON嚗?蝔梢 + 甈??萄停餈?撠???
    for _m in _re_y.finditer(
        r'"(?:name|symbolName|holdingName|stockName)"\s*:\s*"([^"]{1,40})"'
        r'[^{}]{0,200}?"(?:weighting|holdingPercent|percent|weight|ratio)"'
        r'\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',
        _html
    ):
        _nm = _m.group(1).strip()
        try:
            _w = float(_m.group(2))
        except ValueError:
            continue
        if _w <= 1.5:           # 撠銵函內嚗?.05嚗? 頧??
            _w *= 100
        if _nm and not _nm.isdigit() and 0 < _w <= 100 and _nm not in _out:
            _out[_nm] = round(_w, 4)
        if len(_out) >= 60:
            break
    if _out:
        print(f'[Holdings/YahooTW] ??JSON) {symbol_yf} {len(_out)} 瑼?)
        return _out
    # ?? 蝑 B嚗”?潛???嚗葉???+ n.nn% ??嚗??
    try:
        from bs4 import BeautifulSoup as _BS_y
        _txt = _BS_y(_html, 'html.parser').get_text(' ', strip=True)
        for _m in _re_y.finditer(
            r'([銝-橦瓢[銝-橦澤-Za-z0-9&\.\-]{1,29})\s+'
            r'([0-9]{1,2}\.[0-9]{1,2})\s*%', _txt
        ):
            _nm = _m.group(1).strip()
            try:
                _w = float(_m.group(2))
            except ValueError:
                continue
            if (_nm and not _nm.isdigit() and 0 < _w <= 100
                    and _nm not in _out
                    and _nm not in ('?甈?', '甈?', '瘥?', '?瘥?')):
                _out[_nm] = _w
            if len(_out) >= 60:
                break
    except Exception as _eb:
        print(f'[Holdings/YahooTW] BS 閫???啣虜 {symbol_yf}: {type(_eb).__name__}: {_eb}')
    if _out:
        print(f'[Holdings/YahooTW] ??HTML) {symbol_yf} {len(_out)} 瑼?)
        return _out
    print(f'[Holdings/YahooTW] ??{symbol_yf} ??∪閫???')
    return None


def _enrich_tw_holding_name(raw_name: str, symbol) -> str:
    """?憿舐內?葉?? (隞?Ⅳ)??

    - symbol 敶Ｗ? '2330.TW'嚗?∩誨??4-6 蝣潭摮??怠撣嗅?瘥???隞?
      stock_names.get_stock_name 鋆葉???亦銝剜??????(隞?Ⅳ)?撠葆?箔誨蝣潦?
    - 瘚瑕????∴?憒???ETF ??AAPL嚗??⊥??文 ???見?嚗??怨?瘛餉雲??
    """
    import re as _re_n
    _code = str(symbol or '').upper().replace('.TWO', '').replace('.TW', '').strip()
    if not _re_n.fullmatch(r'\d{4,6}[A-Z]?', _code):
        return raw_name
    _zh = ''
    try:
        from stock_names import get_stock_name as _gsn
        _zh = _gsn(_code) or ''
    except Exception:
        _zh = ''
    if _zh and _re_n.search(r'[銝-橦瓢', _zh):
        return f'{_zh} ({_code})'
    return f'{raw_name} ({_code})'


@st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
def fetch_etf_holdings(ticker: str):
    """??ETF ?遢?⊥??殷???迂 ??甈? %嚗??ETF ?箔蜓嚗絲憭?ETF 韏?yfinance ????

    憭挾?嚗????岫嚗遙銝???唾???嚗?
      1. yfinance `.funds_data.top_holdings` ??瘚瑕? ETF 銝餅?嚗?⊿虜 None
      1.5 ?啁 Yahoo ?∪? /quote/{sym}/holding ???啗 ETF 銝餅?嚗絲憭?IP ?舐???
      2. MoneyDJ 銝? URL 銝行?嚗?皞?瘚瑕? IP ? NAS proxy嚗?
         - Basic0007.xdjhtm嚗??⊥?蝝堆?
         - Basic0008.xdjhtm嚗?鞈?蝵殷?
         - RankA0001.xdjhtm嚗??⊥???
      3. ?典仃?? None嚗I 蝡舀? ??N/A嚗?

    Returns
    -------
    dict[str, float] | None
        key=??迂嚗葉/?望?嚗?value=甈??曉?瘥?憒?5.23 隞?” 5.23%嚗?
        ?∟???/ ??憭望???None??

    Cache
    -----
    TTL 86400 蝘?1 ?伐?嚗? ETF ?遢?⊥?摨行??湔??
    """
    import re as _re_h
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    _t_yf = _t if '.' in _t else (f'{_t}.TW' if _t.isdigit() else _t)
    _t_mdj = _t_yf  # MoneyDJ etfid ??yfinance ticker

    # ?? 1. yfinance funds_data嚗絲憭?ETF 銝餅?嚗??????????????????
    try:
        _yt = yf.Ticker(_t_yf)
        _fd = getattr(_yt, 'funds_data', None)
        if _fd is not None:
            _th = getattr(_fd, 'top_holdings', None)
            if _th is not None and hasattr(_th, 'iterrows') and not _th.empty:
                _out = {}
                for _idx, _row in _th.iterrows():
                    _name = str(_row.get('Name', _idx) or _idx).strip()
                    _sym  = _row.get('Symbol', _idx)  # top_holdings index 憭隞??
                    _w_raw = _row.get('Holding Percent', _row.get('% of Net Assets', None))
                    if _w_raw is None or _name == '':
                        continue
                    try:
                        _w = float(_w_raw)
                    except (TypeError, ValueError):
                        continue
                    # yfinance 憭誑撠銵函內嚗?.05 = 5%嚗?> 1 閬撌脫?曉?瘥?
                    if _w <= 1.5:
                        _w = _w * 100
                    if _w > 0:
                        _out[_enrich_tw_holding_name(_name, _sym)] = round(_w, 4)
                if _out:
                    print(f'[Holdings/yf] ??{_t_yf} {len(_out)} 瑼?)
                    return _out
    except Exception as _ey:
        print(f'[Holdings/yf] {_t_yf}: {type(_ey).__name__}: {_ey}')

    # ?? 1.5 ?啁 Yahoo ?∪?嚗??抒? Yahoo嚗??ETF 銝餅?嚗????????
    # Yahoo CDN 瘚瑕? IP ?舐???蝜? MoneyDJ 撠絲憭?IP ??403 撠?
    _yh = _fetch_holdings_yahoo_tw(_t_yf)
    if _yh:
        return _yh

    # ?? 2. MoneyDJ 銝? URL ?岫嚗??ETF ??嚗????????????????
    # 韏?proxy_helper嚗AS Squid ?啁 IP嚗銝餅? ??MoneyDJ ??絲憭?IP ??403嚗?
    # curl_cffi ?? fallback嚗璈??潭? proxy ????
    _urls = [
        f'https://www.moneydj.com/ETF/X/Basic/Basic0007.xdjhtm?etfid={_t_mdj}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0008.xdjhtm?etfid={_t_mdj}',
        f'https://www.moneydj.com/ETF/X/Basic/RankA0001.xdjhtm?etfid={_t_mdj}',
    ]
    for _url in _urls:
        _txt = None
        # ?? 2a. proxy_helper 銝餅? ???
        try:
            from proxy_helper import fetch_url as _fu_h
            _r = _fu_h(_url, timeout=15, attempts=2)
            if _r is not None and _r.status_code == 200:
                _r.encoding = 'utf-8'
                _txt = _r.text
        except Exception as _eph:
            print(f'[Holdings/MDJ] proxy ?啣虜 {_t_mdj}: {type(_eph).__name__}: {_eph}')
        # ?? 2b. curl_cffi fallback ?
        if _txt is None:
            try:
                from curl_cffi import requests as _cffi_h
                _r2 = _cffi_h.get(_url, impersonate='chrome124', timeout=15)
                if _r2.status_code == 200:
                    _txt = _r2.text
                else:
                    print(f'[Holdings/MDJ] curl_cffi {_t_mdj} {_url[-30:]}: HTTP {_r2.status_code}')
            except Exception as _eh:
                print(f'[Holdings/MDJ] curl_cffi ?啣虜 {_t_mdj} {_url[-30:]}: {type(_eh).__name__}: {_eh}')
        if _txt is None:
            continue
        # ?? 撖祇? regex ?瑕?嚗??銝剜?/?望嚗? 敺??曉?瘥???
        try:
            _stocks = {}
            for _m in _re_h.finditer(
                r'>([銝-橦?A-Z0-9&\.\-]{2,30})</[^>]+>[^<]*<[^>]+>\s*(\d{1,2}\.\d{1,3})\s*%',
                _txt
            ):
                _nm = _m.group(1).strip()
                if (_nm and not _nm.isdigit() and not _nm.replace('.', '').isdigit()
                        and _nm not in ('?瘥?', '瘥?', '?瘥?', '甈?', '??迂', '?迂')
                        and len(_nm) >= 2):
                    try:
                        _w = float(_m.group(2))
                        if 0 < _w <= 100 and _nm not in _stocks:
                            _stocks[_nm] = _w
                    except ValueError:
                        continue
                if len(_stocks) >= 50:
                    break
            if _stocks:
                print(f'[Holdings/MDJ] ??{_t_mdj} {len(_stocks)} 瑼?({_url[-30:]})')
                return _stocks
        except Exception as _eh2:
            print(f'[Holdings/MDJ] regex ?啣虜 {_t_mdj} {_url[-30:]}: {type(_eh2).__name__}: {_eh2}')
            continue

    print(f'[Holdings] ??{_t} ??yf/MoneyDJ 銝? URL ?典仃??)
    return None


# ??????????????????????????????????????????????????????????????
# 銝餃?撘?ETF ?文 + 蝬?鈭箸閰ｇ?PR ??claude/etf-weakness-manager嚗?
# ??????????????????????????????????????????????????????????????
# 銝餃?撘??ETF ?賢??殷?隞???怠?撣嗅?瘥?A/D/T嚗?024-2026 ?之/敺抵/??蝑???
# 鋆?蝝摮誨??銝餃?撘?ETF嚗??芯??啁?嚗????脖?
_ACTIVE_TW_ETF_WHITELIST = {
    # ?之銝餃?撘頂??2024 Q4 ~ 2026嚗?
    '00980A', '00982A', '00984A', '00989A', '00992A',
    '00982T', '00980D',
    # 敺抵 / ?陸 / 銝凋縑 / ?? 銝餃?撘?鋆?皜嚗??砍??貊??嚗?
    '00981A', '00983A', '00985A', '00986A', '00987A',
    '00988A', '00990A', '00991A', '00993A', '00994A',
    '00995A', '00996A', '00997A',
}


def is_active_etf(ticker: str) -> bool:
    """?文 ETF ?臭蜓?? (Active) ?鋡怠?撘?(Passive)??

    ?文?芸?摨?
      1. ?賢??桀銝???True
      2. 隞???思? = 'B' (?萄?? ??'K' (瑽▼) ??False嚗?鋡怠?嚗?
      3. 隞???思??箏?瘥?A/D/T 蝑? B/K嚗? True嚗??箔蜓??
      4. 蝝摮誨????False嚗??箄◤?蕭頩斗??賂?憒?0050/00878/00940嚗?
    """
    if not ticker:
        return False
    _code = str(ticker).replace('.TW', '').replace('.TWO', '').replace('.tw', '').upper().strip()
    if _code in _ACTIVE_TW_ETF_WHITELIST:
        return True
    if not _code:
        return False
    _last = _code[-1]
    if _last in ('B', 'K'):  # ?萄??/ 瑽▼??= 鋡怠?餈質馱
        return False
    if _last.isalpha():       # ?嗡?摮?蝯偏 (A/D/T) 憭銝餃?撘?
        return True
    return False              # 蝝摮?= 鋡怠?餈質馱?


def _fetch_yuanta_active_etf_meta(ticker: str) -> dict | None:
    """?之?縑摰雯 fallback ???蜓?? ETF 蝬?鈭?/ 鞎餌??/ NAV??

    ?箔??閬?MoneyDJ Basic0001/0006/0011 / SITCA 撠蜓?? ETF嚗?0980A 蝑?
    ?∠??犖甈?嚗?憭扳?靽∪?蝬脫??舀??准? URL ?岫嚗TML regex 閫????

    Returns
    -------
    dict | None
        ??嚗
            'manager':   str | None,    蝬?鈭箏???
            'expense':   float | None,  蝮質祥?函?嚗??賂?0.0085 = 0.85%嚗?
            'nav_latest': float | None, ?餈???NAV
            'nav_date':   str | None,   NAV ?交? YYYY-MM-DD
            'source':     'yuanta-official',
            'url':        str,
        }
        憭望?嚗one
    """
    import re as _re_y
    _code = (ticker or '').replace('.TW', '').replace('.TWO', '').strip().upper()
    if not _code or not is_active_etf(ticker):
        return None
    _urls = [
        f'https://www.yuantaetfs.com/product/detail/{_code}/profile',
        f'https://www.yuantaetfs.com/product/detail/{_code}',
        f'https://www.yuantaetfs.com/RtnPercent/Detail/{_code}',
    ]
    for _url in _urls:
        _txt = None
        try:
            from proxy_helper import fetch_url as _fu_y
            _r = _fu_y(_url, timeout=12, attempts=2)
            if _r is not None and _r.status_code == 200 and len(_r.text or '') > 500:
                _r.encoding = 'utf-8'
                _txt = _r.text
        except Exception as _ey:
            print(f'[Yuanta/{_code}] proxy ?啣虜 {_url}: {type(_ey).__name__}: {_ey}')
            continue
        if not _txt:
            continue
        _out: dict = {'manager': None, 'expense': None,
                      'nav_latest': None, 'nav_date': None,
                      'source': 'yuanta-official', 'url': _url}
        _m = _re_y.search(
            r'(?:?粹?)?蝬?鈭暨\s\:嚗*([銝-橦瓢{2,8}(?:\s*[\/??]\s*[銝-橦瓢{2,8})*)',
            _txt,
        )
        if _m:
            _out['manager'] = _m.group(1).strip().replace(' ', '')
        _e = _re_y.search(
            r'(?:蝮質祥?函?|蝬?鞎蒜\s\S]{0,80}?靽恣鞎蒜\s\S]{0,40}?)[\s\:嚗{0,5}(\d+\.\d{1,3})\s*%',
            _txt,
        )
        if _e:
            try:
                _out['expense'] = float(_e.group(1)) / 100.0
            except ValueError:
                pass
        _n = _re_y.search(
            r'(?:瘛典慝?桐?瘛典慝NAV)[\s\:嚗*(\d+\.\d{2,4})',
            _txt,
        )
        if _n:
            try:
                _out['nav_latest'] = float(_n.group(1))
            except ValueError:
                pass
        _nd = _re_y.search(r'(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})', _txt)
        if _nd:
            try:
                from datetime import date as _date_y
                _y, _mo, _d = (int(_nd.group(i)) for i in (1, 2, 3))
                _out['nav_date'] = _date_y(_y, _mo, _d).isoformat()
            except (ValueError, OverflowError):
                pass
        if any(_out.get(k) for k in ('manager', 'expense', 'nav_latest')):
            print(f'[Yuanta/{_code}] ??via {_url[:60]}... '
                  f'manager={_out.get("manager")} '
                  f'expense={_out.get("expense")} '
                  f'nav={_out.get("nav_latest")}')
            return _out
    return None


def _html_kv_pairs(html_text: str) -> dict:
    """??HTML 銵冽 td/th ?賊?脣??潮???{甈??? ?慕嚗窒?冽??獢圾??嚗?

    MoneyDJ 璅惜(憒??犖???祥(%)???澆?賊?脣???蝝?regex ?◤
    璅惜??% ??HTML 撟脫;?寧?脣??潮?撠蝛拙??具??澆?甈????思葉??
    ??2摮?????,瞈暹??勗??閮?
    """
    import re as _re_kv
    from html.parser import HTMLParser as _HP_kv

    class _Cells(_HP_kv):
        def __init__(self):
            super().__init__()
            self.cells, self._buf = [], None
        def handle_starttag(self, tag, attrs):
            if tag in ('td', 'th'):
                self._buf = []
        def handle_data(self, data):
            if self._buf is not None:
                self._buf.append(data)
        def handle_endtag(self, tag):
            if tag in ('td', 'th') and self._buf is not None:
                self.cells.append(_re_kv.sub(r'\s+', ' ', ''.join(self._buf)).strip())
                self._buf = None

    _p = _Cells()
    try:
        _p.feed(html_text or '')
    except Exception:
        return {}
    _cells = [c for c in _p.cells if c]
    _kv: dict = {}
    for _i in range(len(_cells) - 1):
        _key = _cells[_i].rstrip(':嚗?').strip()
        _val = _cells[_i + 1].strip()
        if _val and _key and _key not in _kv and len(_key) <= 12 and _re_kv.search(r'[銝-橦瓢', _key):
            _kv[_key] = _val
    return _kv


@st.cache_data(ttl=604800, show_spinner=False)
def fetch_etf_manager(ticker: str):
    """敺?MoneyDJ ETF ?隞餌??犖 + 隞餅?韏瑕??乓?

    ??蝑
    --------
    憭?URL ?岫嚗? proxy嚗???endpoint嚗?
      1. Basic0001.xdjhtm ???箸鞈?嚗蝯勗???
      2. Basic0006.xdjhtm ???粹?璁?嚗??閮?嚗 ETF ?航?冽迨嚗?
      3. Basic0011.xdjhtm ???粹??寡嚗?閬??典??粹???
    瘥?URL ?改?proxy_helper 銝餅? ??curl_cffi fallback??

    Regex 撖祇?蝑
    --------------
    ??嚗??犖????犖?隞餌??犖??銝剝??舀? HTML/whitespace) 敺銝剜? 2-8 摮?
    隞餅?嚗?瑟??隞餅?遙?恣???晷隞餅?銝凋?銝 + ?交?

    Returns
    -------
    dict | None
        ??嚗'name': '撘萎?', 'since': '2024-04-15', 'tenure_days': 400}
        憭望?嚗one嚗仃???神??st.session_state['_etf_manager_last_err'][ticker]
    """
    import re as _re_mg
    from datetime import date as _date_mg
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    if '.' not in _t:
        _t = f'{_t}.TW'

    # Basic0004(蝪∩???撠望????犖??(fetch_etf_meta_moneydj ??????嚗蝚砌??芸???
    _urls = [
        f'https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0006.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0011.xdjhtm?etfid={_t}',
    ]
    _err_trace: list[str] = []
    _best = None   # ??撌脫??唬?蝻箏?瑟?摮?蝥?嗡???行?隞餅??捱摰?

    for _url in _urls:
        _txt = None
        _endpoint = _url.split('/')[-1].split('?')[0]
        # ?? 1. proxy_helper嚗AS Squid ?啁 IP嚗蜓皞??????????????
        try:
            from proxy_helper import fetch_url as _fu_mg
            _r = _fu_mg(_url, timeout=12, attempts=2)
            if _r is not None and _r.status_code == 200 and len(_r.text or '') > 500:
                _r.encoding = 'utf-8'
                _txt = _r.text
            else:
                _code = _r.status_code if _r is not None else 'None'
                _ln = len(_r.text or '') if _r is not None else 0
                _err_trace.append(f'proxy {_endpoint}: HTTP {_code} len={_ln}')
                print(f'[MDJ/manager] proxy {_t} {_endpoint}: HTTP {_code} len={_ln}')
        except Exception as _ep:
            _err_trace.append(f'proxy {_endpoint}: {type(_ep).__name__}')
            print(f'[MDJ/manager] proxy ?啣虜 {_t} {_endpoint}: {type(_ep).__name__}: {_ep}')

        # ?? 2. curl_cffi fallback ????????????????????????????????
        if _txt is None:
            try:
                from curl_cffi import requests as _cffi_mg
                _r2 = _cffi_mg.get(_url, impersonate='chrome124', timeout=12)
                if _r2.status_code == 200 and len(_r2.text or '') > 500:
                    _txt = _r2.text
                else:
                    _err_trace.append(f'cffi {_endpoint}: HTTP {_r2.status_code}')
                    print(f'[MDJ/manager] curl_cffi {_t} {_endpoint}: HTTP {_r2.status_code}')
            except Exception as _ec:
                _err_trace.append(f'cffi {_endpoint}: {type(_ec).__name__}')
                print(f'[MDJ/manager] curl_cffi ?啣虜 {_t} {_endpoint}: {type(_ec).__name__}: {_ec}')

        if _txt is None:
            continue

        # ?? 3a. KV ?脣??潸圾??蝛拙嚗??regex嚗?蝬?鈭??啗?亙虜?刻”?潛?唳 ??
        try:
            _kv_mg = _html_kv_pairs(_txt)
            _nm_raw = ''
            for _k in ('?粹?蝬?鈭?, '?曆遙蝬?鈭?, '蝬?鈭?):
                if _k in _kv_mg:
                    _nm_raw = _kv_mg[_k]
                    break
            if not _nm_raw:
                for _k, _v in _kv_mg.items():
                    if '蝬?' in _k:
                        _nm_raw = _v
                        break
            _nm_m2 = _re_mg.search(r'[銝-橦瓢{2,8}', _nm_raw)  # ?洵銝畾萎葉???輸???鈭綽?
            if _nm_m2:
                _name = _nm_m2.group(0)
                _since, _days = None, None
                _dt_raw = ''
                for _k in ('?啗??, '銝遙??, '瘣曆遙??, '韏瑁???, '蝞∠??粹???, '隞餅?'):
                    if _k in _kv_mg:
                        _dt_raw = _kv_mg[_k]
                        break
                _dm2 = _re_mg.search(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', _dt_raw)
                if _dm2:
                    try:
                        _dtv = _date_mg(int(_dm2.group(1)), int(_dm2.group(2)), int(_dm2.group(3)))
                        _since = _dtv.strftime('%Y-%m-%d')
                        _days = (_date_mg.today() - _dtv).days
                    except ValueError:
                        pass
                if _since:
                    print(f'[MDJ/manager] ??KV) {_t} = {_name} via {_endpoint} (since={_since}, days={_days})')
                    return {'name': _name, 'since': _since, 'tenure_days': _days}
                if _best is None:   # ????瑟蝻????怠?嚗??亙隞?
                    _best = {'name': _name, 'since': None, 'tenure_days': None}
                    print(f'[MDJ/manager] (KV) {_t} = {_name} via {_endpoint}嚗?啗?伐?蝥?嗡???)
        except Exception as _ekv:
            print(f'[MDJ/manager] KV parse ?仿? {_endpoint}: {type(_ekv).__name__}')

        # ?? 3. 撖祇? regex ?岫閫?? ????????????????????????????????
        try:
            # ??嚗??犖 / ?粹?蝬?鈭?/ ?曆遙蝬?鈭?... 銝剜? 2-8 摮?
            _name_m = _re_mg.search(
                r'(?:?粹?|?曆遙)?\s*蝬?鈭暨^<>]{0,50}?>\s*([銝-橦瓢{2,8})\s*[<\(]',
                _txt,
            )
            # 撖祇? fallback嚗??犖敺?交銝剜?嚗 > 璅惜嚗?
            if not _name_m:
                _name_m = _re_mg.search(
                    r'(?:?粹?|?曆遙)?\s*蝬?鈭暨^銝-橦璞d]{0,30}?([銝-橦瓢{2,8})',
                    _txt,
                )
            _date_m = _re_mg.search(
                r'(?:?啗?四銝遙?四隞餅?|蝞∠??粹??四瘣曆遙?四韏瑁???[^\d]{0,30}?(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})',
                _txt,
            )
            if not _name_m:
                _err_trace.append(f'{_endpoint}: 200 雿?regex ?∠??犖')
                print(f'[MDJ/manager] ?? {_t} {_endpoint}: 200 雿?regex ?∠??犖')
                continue
            _name = _name_m.group(1).strip()
            _since, _days = None, None
            if _date_m:
                _y, _mo, _d = (int(_date_m.group(i)) for i in (1, 2, 3))
                try:
                    _dt = _date_mg(_y, _mo, _d)
                    _since = _dt.strftime('%Y-%m-%d')
                    _days = (_date_mg.today() - _dt).days
                except ValueError:
                    pass
            if _since:
                print(f'[MDJ/manager] ??{_t} = {_name} via {_endpoint} (since={_since}, days={_days})')
                return {'name': _name, 'since': _since, 'tenure_days': _days}
            if _best is None:
                _best = {'name': _name, 'since': None, 'tenure_days': None}
                print(f'[MDJ/manager] (regex) {_t} = {_name} via {_endpoint}嚗?啗?伐?蝥?嗡???)
        except Exception as _e:
            _err_trace.append(f'{_endpoint}: regex 靘? {type(_e).__name__}')
            print(f'[MDJ/manager] ??regex parse {_t} {_endpoint}: {type(_e).__name__}: {_e}')

    # MoneyDJ ????嚗???雿?∪?瑟 ????摮?隞餅? UI 憿舐內??剝?惇撖佗?
    if _best is not None:
        print(f'[MDJ/manager] ??{_t} = {_best["name"]}嚗oneyDJ ????啗?伐?')
        return _best

    # ?? 4. SITCA fallback ???祥?函???proxy 頝臬?嚗歇霅韏堆?????????
    if _t.replace('.TW', '').replace('.TWO', '').isdigit():
        _sitca = _fetch_sitca_manager(_t)
        if _sitca and _sitca.get('name'):
            print(f'[SITCA/manager] ??{_t} = {_sitca["name"]}')
            return _sitca
        else:
            _err_trace.append('sitca: 憭?URL/憭?column 瘥??典仃??)

    # ?? 5. Yuanta 摰雯 fallback ??銝餃?撘?ETF 撠惇嚗1.1嚗?????????????
    _yu = _fetch_yuanta_active_etf_meta(_t)
    if _yu and _yu.get('manager'):
        print(f'[Yuanta/manager] ??{_t} = {_yu["manager"]}')
        return {'name': _yu['manager'], 'since': None, 'tenure_days': None,
                'source': 'yuanta-official'}
    elif _yu is not None:
        _err_trace.append('yuanta: 200 雿?regex ?∠??犖')
    else:
        if is_active_etf(_t):
            _err_trace.append('yuanta: 3 URL ??fail')

    # ?券憭望? ??撖?session_state 蝯西那?琿?輯?
    try:
        if st is not None:
            _store = st.session_state.setdefault('_etf_manager_last_err', {})
            _store[_t] = ' | '.join(_err_trace) if _err_trace else 'unknown'
    except Exception:
        pass
    return None


import os as _os_mg
import json as _json_mg

_MGR_HISTORY_PATH = _os_mg.path.join('/tmp/st_cache', 'etf_manager_history.json')
# ??瑼???update_etf_managers.py嚗itHub Actions 瘥梧?蝬剛風銝?commit ??repo嚗?
# 頝?Streamlit Cloud 摰孵??隞?瘣鳴?閫?捱 /tmp 皜征撠蝝?銝歲??憿???
_ETF_MANAGERS_REPO_PATH = _os_mg.path.join(
    _os_mg.path.dirname(_os_mg.path.abspath(__file__)), 'etf_managers.json')
_RECENT_CHANGE_DAYS = 180   # ???菜葫?亙?憭??找???UI 鈭桃?獢?


def track_etf_manager_change(ticker: str, manager: dict | None) -> dict:
    """瘥? ETF 蝬?鈭箇??ETF 銵函???犖?賊?嚗?????嚗?

    ???箸??風?脩?銝颱?皞?= `etf_managers.json`嚗ctions 蝬剛風?ommit ??repo嚗?
    頝典捆?券???瘣鳴?嚗/tmp` ?箸活閬??拇活 Actions 銋? app ?芾??單??菜葫 + ?脩垢
    ?航????嚗???UI ?典???
      {'changed': bool, 'prev': str|None, 'detected_at': 'YYYY-MM-DD'|None,
       'is_new': bool, 'tenure_days': int|None}
    changed嚗?銋?餈?180 憭拇???蝝????live ???皞???
    is_new嚗?瑟?函?隞餅? < 180 憭抬??僑?扳隞?銵函敺?撖???
    """
    import datetime as _dt_mg
    _name = (manager or {}).get('name') or None
    _tenure = (manager or {}).get('tenure_days')
    _is_new = isinstance(_tenure, int) and _tenure < 180
    _out = {'changed': False, 'prev': None, 'detected_at': None,
            'is_new': _is_new, 'tenure_days': _tenure}
    if not _name:
        return _out
    _key = (ticker or '').replace('.tw', '.TW').strip()
    _today_d = _dt_mg.date.today()
    _today = _today_d.isoformat()

    # ?? 1. ??瑼?repo嚗?頝典捆?典?瘣餌????箸? + 甇瑕 ??????????????
    _repo_rec = {}
    try:
        if _os_mg.path.exists(_ETF_MANAGERS_REPO_PATH):
            with open(_ETF_MANAGERS_REPO_PATH, 'r', encoding='utf-8') as _f:
                _repo_db = _json_mg.load(_f) or {}
            _repo_rec = (_repo_db.get('managers') or {}).get(_key) or {}
    except Exception as _e_repo:
        print(f'[ETF Manager] 霈??瑼?? {_e_repo}')

    # 1a. ?? history 餈?180 憭拍??? ???喃蝙摰孵??隞漁蝝?
    for _h in reversed(_repo_rec.get('history') or []):
        _da = _h.get('detected_at')
        try:
            _dd = _dt_mg.date.fromisoformat(_da) if _da else None
        except ValueError:
            _dd = None
        if _dd and (_today_d - _dd).days <= _RECENT_CHANGE_DAYS:
            _out.update({'changed': True, 'prev': _h.get('from'), 'detected_at': _da})
            break

    # 1c. 隞餅? fallback嚗ive tenure_days 蝻????冽?銋? first_seen ?函?餈撮??
    #     嚗oneyDJ 銝?脣?瑟??ETF ?拍嚗? 'approx' 霈?UI ?仿??臭摯蝞?
    if _out['tenure_days'] is None and _repo_rec.get('first_seen'):
        try:
            _fs = _dt_mg.date.fromisoformat(_repo_rec['first_seen'])
            _approx_days = (_today_d - _fs).days
            if _approx_days >= 0:
                _out['tenure_days'] = _approx_days
                _out['tenure_approx'] = True   # UI ?內?撠?X 憭押?蝣箏?
                # ?閰摯 is_new嚗餈撮 tenure嚗?
                _out['is_new'] = _approx_days < 180
        except ValueError:
            pass

    # 1b. live ?? vs ???箸?銝? ???拇活 Actions 銋?銋?單??菜葫
    _repo_name = _repo_rec.get('name')
    if not _out['changed'] and _repo_name and _repo_name != _name:
        _out.update({'changed': True, 'prev': _repo_name, 'detected_at': _today})

    # ?? 2. /tmp ?單?瑼?甈∟?嚗ession ??+ ??瑼??臬神???湛???????
    try:
        _os_mg.makedirs('/tmp/st_cache', exist_ok=True)
        _db = {}
        if _os_mg.path.exists(_MGR_HISTORY_PATH):
            with open(_MGR_HISTORY_PATH, 'r', encoding='utf-8') as _f:
                _db = _json_mg.load(_f) or {}
        _rec = _db.get(_key) or {}
        _prev = _rec.get('name')
        if _prev and _prev != _name and not _out['changed']:
            _out.update({'changed': True, 'prev': _prev, 'detected_at': _today})
            _hist = _rec.get('history') or []
            _hist.append({'from': _prev, 'to': _name, 'detected_at': _today,
                          'since': (manager or {}).get('since')})
            _rec['history'] = _hist[-10:]
            # ?? ??first_seen ?身?箔?憭抬??唬遙?絲暺?
            _rec['first_seen'] = _today
        _rec.update({'name': _name, 'since': (manager or {}).get('since'),
                     'last_seen': _today})
        # 擐活蝝?迨 ticker ?身 first_seen嚗捆?典?瘣餅??抒隞餅??嚗?
        _rec.setdefault('first_seen', _today)
        _rec.setdefault('history', _rec.get('history', []))
        _db[_key] = _rec

        # ?交?銋?瘝?first_seen 雿?/tmp ????鋆? out ?函? tenure
        if _out['tenure_days'] is None and _rec.get('first_seen'):
            try:
                _fs2 = _dt_mg.date.fromisoformat(_rec['first_seen'])
                _ad2 = (_today_d - _fs2).days
                if _ad2 >= 0:
                    _out['tenure_days'] = _ad2
                    _out['tenure_approx'] = True
                    _out['is_new'] = _ad2 < 180
            except ValueError:
                pass
        with open(_MGR_HISTORY_PATH, 'w', encoding='utf-8') as _f:
            _json_mg.dump(_db, _f, ensure_ascii=False, indent=2)
    except Exception as _e_mg:
        print(f'[ETF Manager] ?啣?餈質馱?仿?嚗瘜?瑼?: {_e_mg}')
    return _out


@st.cache_data(ttl=604800, show_spinner=False)
def _fetch_sitca_manager(ticker: str):
    """SITCA fallback嚗?靽⊥?憿批????犖?亥岷??

    頝?fetch_sitca_expense_ratio ??proxy 頝臬?嚗歇撽??航粥嚗?pd.read_html 敺???
    ????”?潭?誨???粹?隞?Ⅳ?????犖嚗???犖??甈?

    Returns
    -------
    dict | None  {'name': ..., 'since': None, 'tenure_days': None}嚗遙??SITCA ?虜銝?莎?
    """
    from proxy_helper import fetch_url as _fu_sm
    import pandas as _pd_sm
    _t = (ticker or '').replace('.TW', '').replace('.tw', '').replace('.TWO', '').strip()
    if not _t or not _t.isdigit():
        return None
    _tn = _t.lstrip('0') or '0'

    _urls = [
        'https://www.sitca.org.tw/ROC/Industry/IN2401.aspx?pid=IN2401_01',
        'https://www.sitca.org.tw/ROC/Industry/IN2421.aspx?pid=IN2421_01',
        'https://www.sitca.org.tw/ROC/Industry/IN2422.aspx?pid=IN2422_01',
        'https://www.sitca.org.tw/ROC/Industry/IN2411.aspx?pid=IN2411_01',
    ]
    for _url in _urls:
        try:
            r = _fu_sm(_url, timeout=15, attempts=2)
            if r is None or r.status_code != 200 or len(r.text or '') < 500:
                continue
            r.encoding = 'utf-8'
            try:
                tables = _pd_sm.read_html(r.text)
            except ValueError:
                continue
            for tbl in tables:
                code_col = next((c for c in tbl.columns
                                 if any(k in str(c) for k in
                                        ('隞??', '隞?Ⅳ', '?粹?蝯梁楊', '蝯曹?蝺刻?', 'Code'))), None)
                mgr_col = next((c for c in tbl.columns
                                if any(k in str(c) for k in
                                       ('蝬?鈭?, '?粹?蝬?', '?曆遙蝬?'))), None)
                if code_col is None or mgr_col is None:
                    continue
                _digits = tbl[code_col].astype(str).str.replace(r'\D', '', regex=True)
                row = tbl[_digits.where(_digits != '', '0').str.lstrip('0').replace('', '0') == _tn]
                if row.empty:
                    continue
                _raw = str(row[mgr_col].iloc[0]).strip()
                if not _raw or _raw.lower() == 'nan' or _raw.isdigit():
                    continue
                # 憭犖?勗?蝬??具??????航??酉閮???雿楊??
                _name = _raw.split('??)[0].split(',')[0].split('(')[0].split('嚗?)[0].strip()
                if 2 <= len(_name) <= 8:
                    print(f'[SITCA/manager] ??{_t} = {_name} (url={_url[-30:]})')
                    return {'name': _name, 'since': None, 'tenure_days': None}
        except Exception as e:
            print(f'[SITCA/manager] {_t} {_url[-30:]}: {type(e).__name__}: {e}')
            continue
    return None


def get_etf_expense_ratio_safe(ticker: str):
    """摰霈??ETF 鞎餌??MoneyDJ Basic0004 ??SITCA ??Yuanta ??yfinance ?挾???

    ??霈嚗2嚗?MoneyDJ ?寧 primary嚗粥 NAS 銝剔匱蝡帘摰?蝜?SITCA/yfinance
    ??Streamlit Cloud 瘚瑕? IP 鋡怠????暺仃???撩憭勗? None??
    """
    # Primary嚗oneyDJ Basic0004 銝甈∪? metadata嚗 expense嚗???fetch_etf_info ?梁 cache
    _meta = fetch_etf_meta_moneydj(ticker)
    if _meta and _meta.get('expense') is not None:
        return _meta['expense']
    _sit = fetch_sitca_expense_ratio(ticker)
    if _sit is not None:
        return _sit
    _mdj = fetch_moneydj_expense_ratio(ticker)
    if _mdj is not None:
        return _mdj
    # v1.1嚗蜓?? ETF 撠惇嚗ITCA + MDJ ?賢仃??鋆?
    if is_active_etf(ticker):
        _yu = _fetch_yuanta_active_etf_meta(ticker)
        if _yu and _yu.get('expense') is not None:
            return _yu['expense']
    try:
        info = fetch_etf_info(ticker)
        return (info.get('annualReportExpenseRatio')
                or info.get('totalExpenseRatio')
                or info.get('expenseRatio'))
    except Exception:
        return None


# ?? NAV ??蝭?撣豢嚗??fetch_etf_nav_history 憭? sanity check嚗??
_NAV_MIN, _NAV_MAX = 0.5, 100000


def _safe_float(s, strip_chars: str = ',%') -> float | None:
    """摰 float 閫??嚗仃?? None??

    Replaces inline `try: float(...) except: pass` pattern嚗??bare except
    ?? KeyboardInterrupt / SystemExit??
    """
    try:
        _t = str(s).strip()
        for _c in strip_chars:
            _t = _t.replace(_c, '')
        return float(_t) if _t else None
    except (ValueError, TypeError):
        return None


@st.cache_data(ttl=7200, show_spinner=False, max_entries=10)
def fetch_etf_nav_history(ticker: str, days: int = 35, ver: int = 4) -> "pd.DataFrame":
    """ETF 甇瑕瘛典澆??滯?對??餈?N ?漱?嚗?

    鞈?靘??芸???嚗? 畾萄???+ 1 ??嚗?
      1. FinMind TaiwanETFNetAssetValue嚗甈∴?????token ?嚗?
      2. goodinfo.tw StockDetail嚗???TWSE IP 撠?嚗?
      3. TWSE OpenAPI嚗? NAS Proxy ?啣?嚗?
      4. MoneyDJ BeautifulSoup
      5. yfinance navPrice
      *. ??嚗inMind ??鞈?嚗?餈?5 畾萄憭望???

    Args
    ----
    ticker : str  ETF 隞??嚗 .TW 敺韌嚗?
    days   : int  ?格??滲鈭斗??伐??怎楨銵?+10 ?伐?
    ver    : int  cache key bumper ????閫貊 @st.cache_data 憭望?嚗??亙撘?頛胯?

    Returns
    -------
    pd.DataFrame  甈?嚗ate / price / nav / premium / premium_pct
    """
    import os
    import datetime as _dt
    code = ticker.replace('.TW', '').replace('.TWO', '')
    # st.secrets ?芸?嚗treamlit Cloud secrets 銝??箄 os.environ嚗?
    token = (getattr(st, 'secrets', {}).get('FINMIND_TOKEN')
             or os.environ.get('FINMIND_TOKEN', ''))
    start = (_dt.date.today() - _dt.timedelta(days=days + 10)).strftime('%Y-%m-%d')
    _df_stale = None       # ?嚗inMind ??鞈?
    _days_stale: int | None = None

    # ?單??勗憿?皞?goodinfo/TWSE/MoneyDJ/yfinance嚗????敺?蝑歇?砍?瘛典潦?
    # 雿蝖祆 today嚗??望/??? yfinance ?嗥?伐?銝?鈭斗??伐?撠?銝?inner-join ?賜征??
    # ?絞銝?喋?餈漱???隞予?臬極雿?其?憭抬??血?敺??唳?敺??極雿??
    def _last_business_day(_d):
        while _d.weekday() >= 5:   # 5=Sat, 6=Sun
            _d -= _dt.timedelta(days=1)
        return _d
    _last_bd = _last_business_day(_dt.date.today())

    # ?? 1. FinMind ETF NAV嚗岫?拙?dataset ?迂 + 憭車甈??迂嚗???????????
    from proxy_helper import fetch_url as _fu_etfnav  # NAS 銝剔匱 fallback
    for _ds1 in ['TaiwanETFNetAssetValue', 'TaiwanStockETFNAV']:
        try:
            _p = {'dataset': _ds1, 'data_id': code, 'start_date': start}
            if token: _p['token'] = token
            _r = _fu_etfnav('https://api.finmindtrade.com/api/v4/data', params=_p,
                            timeout=15, attempts=1)
            if _r is None:
                print(f'[ETF NAV] FinMind {_ds1} {code}: fetch_url ??None嚗 NAS 銝剔匱?仃??')
                continue
            _j = _r.json()
            _jstatus = _j.get('status')
            _jdata   = _j.get('data')
            # ?亙? status=200 / status=None嚗??proxy ?啣?嚗??撌脩?航炊蝣?
            _status_ok = str(_jstatus) not in ('400', '401', '402', '403', '404', '500')
            if _jdata and _status_ok:
                _df = pd.DataFrame(_jdata)
                # ?芸??菜葫 NAV 甈??迂嚗inMind ?拙??祆?雿?銝?嚗?
                _nav_field = next((f for f in ['nav', 'base_unit_net_value', 'NavPrice', 'netAssetValue']
                                   if f in _df.columns), None)
                if _nav_field is None:
                    print(f'[ETF NAV] {code} {_ds1}: ?曆???NAV 甈?嚗??{list(_df.columns)}')
                    continue
                _df['date'] = pd.to_datetime(_df['date']).dt.date
                _df['nav']  = pd.to_numeric(_df[_nav_field], errors='coerce')
                _df = _df[_df['nav'].notna() & (_df['nav'] > 0)].sort_values('date')
                if _df.empty:
                    print(f'[ETF NAV] {code} {_ds1}: ???nav 甈??箇征/NaN嚗歲??)
                    continue
                _latest_d   = _df['date'].iloc[-1]
                _days_stale = (_dt.date.today() - _latest_d).days
                _df_stale   = _df[['date', 'nav']]   # 靽?嚗? path 4 ?
                print(f'[ETF NAV] {code} {_ds1}(field={_nav_field}): {len(_df)} 蝑? ???{_latest_d}, 頝?={_days_stale}d')
                if _days_stale <= 14:          # 14憭拙閬?舐嚗???/?砍?撱園嚗?
                    return _df_stale
                print(f'[ETF NAV] {_ds1} {code} 鞈?頛?({_days_stale}d)嚗?閰血隞?皞?)
                break   # ?曉鞈?撠曹???閰衣洵鈭?dataset
            else:
                _msg = str(_j.get('msg', ''))[:80]
                print(f'[ETF NAV] FinMind {_ds1} {code}: status={_jstatus} data_len={len(_jdata) if _jdata else 0} msg={_msg}')
        except Exception as _e1:
            print(f'[ETF NAV] FinMind {_ds1} {code}: {_e1}')

    # ?? 2. goodinfo.tw ??銝? TWSE IP 撠?嚗???ETF 瘛典????????????????????
    try:
        from bs4 import BeautifulSoup as _BS4_gi
        import re as _re_gi
        _url_gi = f'https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={code}'
        # 韏?fetch_url嚗??NAS Squid ???湧???NAS 銝剔匱蝡?fallback嚗?
        _r_gi = _fu_etfnav(_url_gi, headers={'Referer': 'https://goodinfo.tw/tw/'},
                           timeout=12, attempts=2)
        if _r_gi is not None and _r_gi.status_code == 200:
            _soup_gi = _BS4_gi(_r_gi.text, 'lxml')
            _nav_gi, _prem_gi = None, None
            # 蝑1嚗 <td> 銝剜?楊?潦?蝐歹???銝?潭摮?
            for _td_gi in _soup_gi.find_all('td'):
                _txt_gi = _td_gi.get_text(strip=True)
                if _txt_gi in ('瘛典?, '瘥雿楊??, 'NAV'):
                    _sib_gi = _td_gi.find_next_sibling('td')
                    if _sib_gi:
                        _v = _safe_float(_sib_gi.get_text(strip=True))
                        if _v is not None and _NAV_MIN < _v < _NAV_MAX:
                            _nav_gi = _v
                    if _nav_gi:
                        break
            # 蝑2嚗egex ???
            if not _nav_gi:
                _m_gi = _re_gi.search(r'瘛典墩^\d<]{0,30}?(\d{1,5}\.\d{2,6})', _r_gi.text)
                if _m_gi:
                    _v = _safe_float(_m_gi.group(1))
                    if _v is not None and _NAV_MIN < _v < _NAV_MAX:
                        _nav_gi = _v
            # ?岫??皞Ｗ??
            if _nav_gi:
                for _td_gi2 in _soup_gi.find_all('td'):
                    if '?滯?? in _td_gi2.get_text(strip=True):
                        _sib_gi2 = _td_gi2.find_next_sibling('td')
                        if _sib_gi2:
                            _m_p = _re_gi.search(r'([+-]?\d+\.?\d*)', _sib_gi2.get_text(strip=True))
                            if _m_p:
                                _prem_gi = _safe_float(_m_p.group(1))
                        if _prem_gi is not None:
                            break
                _row_gi = {'date': _last_bd, 'nav': _nav_gi}
                if _prem_gi is not None: _row_gi['premium_pct'] = _prem_gi
                print(f'[ETF NAV] {code} goodinfo: nav={_nav_gi} prem={_prem_gi}%')
                return pd.DataFrame([_row_gi])
            else:
                print(f'[ETF NAV] {code} goodinfo: ?曆??唳楊?潭?雿?)
        else:
            print(f'[ETF NAV] {code} goodinfo: HTTP {_r_gi.status_code}')
    except Exception as _e_gi:
        print(f'[ETF NAV] goodinfo {code}: {_e_gi}')

    # ?? 3. TWSE OpenAPI嚗粥 fetch_url嚗 NAS Squid + NAS 銝剔匱蝡?fallback嚗?
    def _parse_twse_row(row_dict, ep_label):
        _nav2 = 0.0
        for _nk in ['?桐?瘛典?, '瘛典?, 'NetAssetValue', 'nav']:
            _v = _safe_float(row_dict.get(_nk, ''))
            if _v is not None:
                _nav2 = _v
                break
        _price2 = 0.0
        for _pk in ['?嗥??, 'ClosingPrice', 'close']:
            _v = _safe_float(row_dict.get(_pk, ''))
            if _v is not None:
                _price2 = _v
                break
        _prem_key = next((k for k in row_dict if '?滯?? in str(k)), None)
        _prem2 = _safe_float(row_dict[_prem_key]) if _prem_key else None
        if _prem2 is None and _nav2 > 0 and _price2 > 0:
            _prem2 = round((_price2 - _nav2) / _nav2 * 100, 2)
        if _nav2 > 0:
            _r_out = {'date': _last_bd, 'nav': _nav2}
            if _price2 > 0:
                _r_out['price'] = _price2
            if _prem2 is not None:
                _r_out['premium_pct'] = _prem2
            print(f'[ETF NAV] {code} TWSE({ep_label}): nav={_nav2} price={_price2} prem={_prem2}%')
            return _r_out
        return None

    for _op_id2 in ['TaiwanStockPremiumDiscountRatio', 'TaiwanStockNetValue']:
        try:
            _ep2 = f'https://openapi.twse.com.tw/v1/ETF/{_op_id2}'
            _r2 = _fu_etfnav(_ep2, headers={'Accept': 'application/json'},
                             timeout=10, attempts=1)
            if _r2 is None:
                print(f'[ETF NAV] TWSE {_op_id2}: fetch_url ??None'); continue
            _j2 = _r2.json()
            _df2 = pd.DataFrame(_j2 if isinstance(_j2, list) else [])
            if _df2.empty:
                print(f'[ETF NAV] TWSE {_op_id2}: ?蝛箄???); continue
            _code_col = next((c for c in _df2.columns if '霅隞??' in str(c) or c == 'code'), None)
            if _code_col is None:
                print(f'[ETF NAV] TWSE {_op_id2}: ?曆???霅隞?? 甈?'); continue
            _match = _df2[_df2[_code_col].astype(str).str.strip() == code]
            if _match.empty:
                print(f'[ETF NAV] TWSE {_op_id2}: ?曆???{code}'); continue
            _out2 = _parse_twse_row(_match.iloc[0].to_dict(), _op_id2)
            if _out2:
                return pd.DataFrame([_out2])
        except Exception as _e2:
            print(f'[ETF NAV] TWSE {_op_id2} {code}: {_e2}')

    # ?? 4. MoneyDJ Basic0003 瘛典潸”?潘?瘥 NAV 甇瑕嚗?????????????????????
    # 靽格迤嚗?雿輻 Basic0004嚗?祈???嚗 NAV 甇瑕嚗? etfid 蝻?.TW 敺韌
    # Basic0003 ?臬???楊?潸”?潘?銝餃?撘?ETF嚗?0982A.TW嚗??舀
    try:
        import re as _re_mdj
        # etfid ? .TW 敺韌嚗蜓?? ETF 'A' 靽?嚗? 00982A.TW嚗?
        _etfid_mdj = ticker.upper() if ticker.upper().endswith(('.TW', '.TWO')) else f'{code}.TW'

        # 4a. Basic0001 ?單??勗?????湔?怒楊??撣/?滯??%)???孵潘?
        #     銝???yfinance Close ?嚗?蝯楊靘??交??臭?嚗V 閫??頛?regex 蝛押?
        _url_q = f'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm?etfid={_etfid_mdj}'
        _r_q = _fu_etfnav(_url_q, headers={'Referer': 'https://www.moneydj.com/'},
                          timeout=12, attempts=2)
        if _r_q is not None and _r_q.status_code == 200:
            _r_q.encoding = 'utf-8'
            _kv_q = _html_kv_pairs(_r_q.text)

            def _kv_num_q(_keys, _excl=()):
                for _k, _v in _kv_q.items():
                    if any(_kk in _k for _kk in _keys) and not any(_xx in _k for _xx in _excl):
                        _m = _re_mdj.search(r'[-+]?\d+\.?\d*', _v.replace(',', ''))
                        if _m:
                            return _safe_float(_m.group(0))
                return None

            _nav_q   = _kv_num_q(['瘛典?])
            _price_q = _kv_num_q(['撣', '?漱??], _excl=['瞍脰?'])
            _prem_q  = _kv_num_q(['?滯??])
            if _nav_q is not None and _NAV_MIN < _nav_q < _NAV_MAX:
                _row_q = {'date': _last_bd, 'nav': _nav_q}
                if _price_q is not None and _price_q > 0:
                    _row_q['price'] = _price_q
                if _prem_q is None and _price_q and _nav_q:
                    _prem_q = round((_price_q - _nav_q) / _nav_q * 100, 2)
                if _prem_q is not None:
                    _row_q['premium_pct'] = _prem_q
                print(f'[ETF NAV] MoneyDJ-Q(Basic0001) {_etfid_mdj}: '
                      f'nav={_nav_q} price={_price_q} prem={_prem_q}%')
                return pd.DataFrame([_row_q])
            print(f'[ETF NAV] MoneyDJ-Q {_etfid_mdj}: 200 雿?KV ?⊥楊??'
                  f'(keys={list(_kv_q)[:8]})')
        else:
            _cq = _r_q.status_code if _r_q is not None else 'None'
            print(f'[ETF NAV] MoneyDJ-Q {_etfid_mdj}: HTTP {_cq}')

        # 4b. Basic0003 瘛典潸”????鋆?NAV 甇瑕嚗?a ?蹂??唳????湛?
        _url_mdj = f'https://www.moneydj.com/ETF/X/Basic/Basic0003.xdjhtm?etfid={_etfid_mdj}'
        _r_mdj = _fu_etfnav(_url_mdj, headers={'Referer': 'https://www.moneydj.com/'},
                            timeout=12, attempts=2)
        if _r_mdj is not None and _r_mdj.status_code == 200:
            _r_mdj.encoding = 'utf-8'
            _nav_mdj, _date_mdj = None, _last_bd
            # 蝑嚗asic0003 瘛典潸”??row = ?交? + ?桐?瘛典潦??餈?蝑?(date, nav) pair
            # ?詨??澆?嚗?td>2026/05/30</td><td>24.5678</td>
            _pairs = _re_mdj.findall(
                r'(\d{4}[/\-](?:1[0-2]|0?[1-9])[/\-](?:3[01]|[12]\d|0?[1-9]))'
                r'[^\d]{0,40}?(\d{1,4}\.\d{2,6})',
                _r_mdj.text)
            if _pairs:
                # ????啗?
                def _parse_d(_s):
                    try:
                        _y, _m_, _d_ = (int(x) for x in _s.replace('-', '/').split('/'))
                        return _dt.date(_y, _m_, _d_)
                    except (ValueError, IndexError):
                        return _dt.date.min
                _pairs.sort(key=lambda p: _parse_d(p[0]), reverse=True)
                for _ds, _vs in _pairs:
                    _v = _safe_float(_vs)
                    if _v is not None and _NAV_MIN < _v < _NAV_MAX:
                        _nav_mdj = _v
                        _date_mdj = _parse_d(_ds)
                        break
            if _nav_mdj and _nav_mdj > 0:
                print(f'[ETF NAV] MoneyDJ {_etfid_mdj}: nav={_nav_mdj} date={_date_mdj}')
                return pd.DataFrame([{'date': _date_mdj, 'nav': _nav_mdj}])
            print(f'[ETF NAV] MoneyDJ {_etfid_mdj}: 200 雿?regex ??date+nav pair')
        else:
            _code_st = _r_mdj.status_code if _r_mdj is not None else 'None'
            print(f'[ETF NAV] MoneyDJ {_etfid_mdj}: HTTP {_code_st}')
    except Exception as _e_mdj:
        print(f'[ETF NAV] MoneyDJ {code}: {type(_e_mdj).__name__}: {_e_mdj}')

    # ?? 5. yfinance ETF info.navPrice嚗???retry嚗??????????????????????
    import time as _t3
    for _sfx3 in ('.TW', '.TWO'):
        for _retry3 in range(3):
            try:
                import yfinance as _yf3
                _tk3 = _yf3.Ticker(f'{code}{_sfx3}')
                _info3 = _tk3.info
                _nav3 = _info3.get('navPrice') or _info3.get('regularMarketNAV')
                if _nav3 and float(_nav3) > 0:
                    print(f'[ETF NAV] yfinance {code}{_sfx3}: navPrice={_nav3}')
                    return pd.DataFrame([{'date': _last_bd, 'nav': float(_nav3)}])
                break  # 瘝???銝?retry
            except Exception as _e3:
                _e3s = str(_e3)
                if ('Too Many Requests' in _e3s or 'Rate' in _e3s) and _retry3 < 2:
                    _t3.sleep(2 + _retry3 * 2)  # 2s, 4s
                    print(f'[ETF NAV] yfinance {code}{_sfx3}: ??retry {_retry3+1}/3')
                    continue
                print(f'[ETF NAV] yfinance {code}{_sfx3}: {_e3}')
                break

    # ?? ?蝯?摨?FinMind ??鞈?嚗oodinfo/MoneyDJ/yfinance ?券憭望???????
    if _df_stale is not None and not _df_stale.empty:
        print(f'[ETF NAV] {code} ?蝯?摨? FinMind??鞈?({_days_stale}d)嚗????皞仃??)
        return _df_stale

    return pd.DataFrame()


@st.cache_data(ttl=CACHE_TTL["financial_data"], max_entries=10)
def _fetch_sector_returns(tickers: tuple, period: str) -> dict:
    """?寞活??憿瞍脰?撟?? {ticker: pct_change}"""
    result = {}
    try:
        raw = yf.download(list(tickers), period=period,
                          auto_adjust=True, progress=False, threads=True)
        if raw.empty:
            return result
        # yf.download 憭?ticker ??Close ??MultiIndex
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw['Close'] if 'Close' in raw.columns.get_level_values(0) else raw.xs('Close', axis=1, level=0)
        else:
            close = raw[['Close']] if 'Close' in raw.columns else raw
        close = close.ffill().dropna(how='all')
        for t in tickers:
            if t in close.columns:
                series = close[t].dropna()
                if len(series) >= 2:
                    pct = round((float(series.iloc[-1]) / float(series.iloc[0]) - 1) * 100, 2)
                    result[t] = pct
    except Exception as e:
        st.warning(f'憿鞈????典?憭望?嚗e}')
    return result


@st.cache_data(ttl=604800, max_entries=500, show_spinner=False)
def fetch_etf_zh_name(ticker: str):
    """敺?MoneyDJ ??ETF 銝剜??迂嚗finance 撠??ETF ?芣??望? longName嚗?

    ??蝑嚗oneyDJ Basic 蝟餃??嚗asic0003/0004/0001嚗? <title> 璅惜
    ?澆??箝銝剜??-{隞??}.TW-ETF{?憿?} - MoneyDJ?瓷蝬脯?regex ?瑕?擐挾銝剜???

    靘?
      <title>銝餃?蝢斤??啁撘瑟?-00982A.TW-ETF瘛典潸”??- MoneyDJ?瓷蝬?/title>
      ??銝餃?蝢斤??啁撘瑟?

      <title>?之?啁50-0050.TW-ETF?箸鞈? - MoneyDJ?瓷蝬?/title>
      ???之?啁50

    Returns
    -------
    str | None  銝剜???2-30 摮?嚗銝??None嚗?怎垢??fallback ??yfinance嚗?
    """
    import re as _re_zh
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    if '.' not in _t:
        _t = f'{_t}.TW'

    # Basic0003嚗楊?潸”?潘??虜?敹怒?蝛抬?fallback 0004/0001
    _urls = [
        f'https://www.moneydj.com/ETF/X/Basic/Basic0003.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm?etfid={_t}',
    ]
    for _url in _urls:
        try:
            from proxy_helper import fetch_url as _fu_zh
            _r = _fu_zh(_url, headers={'Referer': 'https://www.moneydj.com/'},
                        timeout=12, attempts=1)
            if _r is None or _r.status_code != 200:
                continue
            _r.encoding = 'utf-8'
            # Title pattern嚗銝剜??-{隞??}.TW-...??畾?capture
            _m = _re_zh.search(
                r'<title>\s*([^<\-]{2,30}?)\s*-\s*[0-9]{4,5}[A-Z]?\.TW\s*-',
                _r.text)
            if _m:
                _name = _m.group(1).strip()
                # ?嚗??詨????望嚗finance 銋????望???
                if (2 <= len(_name) <= 30 and not _name.isdigit()
                        and any('銝' <= _c <= '橦? for _c in _name)):
                    print(f'[MDJ/zhname] OK {_t} = {_name}')
                    return _name
        except Exception as _e:
            print(f'[MDJ/zhname] {_t} {_url[-30:]}: {type(_e).__name__}: {_e}')
    print(f'[MDJ/zhname] FAIL {_t}')
    return None


@st.cache_data(ttl=604800, max_entries=200, show_spinner=False)
def fetch_etf_underlying_index(ticker: str):
    """敺?MoneyDJ ??ETF 餈質馱??迂嚗finance 瘝?甇斗?嚗?

    ??蝑嚗???fetch_etf_manager ??proxy ?楝嚗AS Squid 銝餅? + curl_cffi fallback嚗?
    ?芸???嚗asic0001嚗?祈????撣貉?嚗? Basic0006嚗??閫嚗? Basic0007嚗??⊥?蝝堆??典?????

    Regex 銝惜撖祇?蝑嚗?
      1. 銵券 + 銵冽?脣??潘?>餈質馱?</??<td???批捆</td>
      2. ??敶Ｗ?嚗蕭頩斗??賂??批捆 / 璅??嚗摰?
      3. ?儔閰?摨?撠?/璅?/餈質馱 ? 敺銝剛???詨? 4-80 摮?

    Returns
    -------
    str | None
        ??迂嚗? '?箇???∪?梢?' / 'MSCI Taiwan ESG Index'嚗??曆??啣? None??
    """
    import re as _re_ui
    _t = (ticker or '').replace('.tw', '.TW').strip()
    if not _t:
        return None
    if '.' not in _t:
        _t = f'{_t}.TW'

    _urls = [
        f'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0006.xdjhtm?etfid={_t}',
        f'https://www.moneydj.com/ETF/X/Basic/Basic0007.xdjhtm?etfid={_t}',
    ]
    _err_trace: list[str] = []

    for _url in _urls:
        _txt = None
        _endpoint = _url.split('/')[-1].split('?')[0]
        try:
            from proxy_helper import fetch_url as _fu_ui
            _r = _fu_ui(_url, timeout=12, attempts=2)
            if _r is not None and _r.status_code == 200 and len(_r.text or '') > 500:
                _r.encoding = 'utf-8'
                _txt = _r.text
            else:
                _code = _r.status_code if _r is not None else 'None'
                _err_trace.append(f'proxy {_endpoint}: HTTP {_code}')
        except Exception as _epu:
            _err_trace.append(f'proxy {_endpoint}: {type(_epu).__name__}')

        if _txt is None:
            try:
                from curl_cffi import requests as _cffi_ui
                _r2 = _cffi_ui.get(_url, impersonate='chrome124', timeout=12)
                if _r2.status_code == 200 and len(_r2.text or '') > 500:
                    _txt = _r2.text
                else:
                    _err_trace.append(f'cffi {_endpoint}: HTTP {_r2.status_code}')
            except Exception as _ecu:
                _err_trace.append(f'cffi {_endpoint}: {type(_ecu).__name__}')

        if _txt is None:
            continue

        # HTML entity ??瘣????踹? lazy regex ?∪ &nbsp;
        _txt = (_txt.replace('&nbsp;', ' ').replace('&#160;', ' ')
                    .replace('&amp;', '&').replace('?', ' '))

        # ??蕭頩方炊撌柴??詨??粹?????扯?
        _idx = None
        try:
            # 1. 銵券 + ?脣??潘??撣貉???MoneyDJ ??嚗?
            _m = _re_ui.search(
                r'(?:餈質馱|璅?|撠?)\s*?\s*</[^>]+>\s*<[^>]+>\s*'
                r'([銝-橦澤-Za-z0-9 &\.\-嚗?嚗?()]{4,80})\s*<',
                _txt,
            )
            if not _m:
                # 2. ??敶Ｗ?
                _m = _re_ui.search(
                    r'(?:餈質馱|璅?|撠?)\s*?\s*[嚗?]\s*'
                    r'([銝-橦澤-Za-z0-9 &\.\-嚗?嚗?()]{4,80})',
                    _txt,
                )
            if not _m:
                # 3. 撖祇???嚗 HTML/whitespace ??嚗?
                _m = _re_ui.search(
                    r'(?:餈質馱|璅?|撠?)\s*?[^銝-橦澤-Za-z\d]{0,40}?'
                    r'([銝-橦澤-Za-z0-9 &\.\-嚗?嚗?()]{4,80})',
                    _txt,
                )
            if _m:
                _cand = _m.group(1)
                # HTML entity / ?典耦蝛箇皜? ?????扯??瑕漲銝雲
                _cand = (_cand.replace('&nbsp;', ' ').replace('?', ' ')
                              .replace('&amp;', '&').strip().rstrip('嚗?????'))
                _bad = ('餈質馱隤文榆', '??∠巨??, '????, '?粹?蝬?',
                        '蝞∠?鞎?, 'nbsp', 'amp;')
                if len(_cand) >= 4 and not any(_b in _cand for _b in _bad):
                    _idx = _cand
        except Exception as _ex:
            _err_trace.append(f'{_endpoint}: regex {type(_ex).__name__}')

        if _idx:
            print(f'[MDJ/index] OK {_t} = {_idx} via {_endpoint}')
            return _idx
        _err_trace.append(f'{_endpoint}: 200 雿?regex ?⊥???)

    try:
        if st is not None:
            _store = st.session_state.setdefault('_etf_index_last_err', {})
            _store[_t] = ' | '.join(_err_trace) if _err_trace else 'unknown'
    except Exception:
        pass
    print(f'[MDJ/index] FAIL {_t} ??{_err_trace[-1] if _err_trace else "no trace"}')
    return None

