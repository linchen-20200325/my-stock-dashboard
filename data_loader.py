from data_config import CACHE_TTL
try:
    import nest_asyncio as _nest; _nest.apply()
except Exception:
    pass

import yfinance as yf
import pandas as pd
import datetime
try:
    from FinMind.data import DataLoader        # finmind < 1.x
except ImportError:
    try:
        from finmind.data import DataLoader    # finmind >= 1.x (撠神)
    except ImportError as _e:
        DataLoader = None
        import warnings
        warnings.warn(f"FinMind DataLoader ?⊥?頛嚗aw HTTP API 隞?剁?嚗_e}")
import streamlit as st
import requests as _req_dl
import urllib3 as _urllib3_dl
_urllib3_dl.disable_warnings(_urllib3_dl.exceptions.InsecureRequestWarning)
from proxy_helper import fetch_url as _fetch_url_dl

# v18.201 D2嚗inMind dataset 敺 update ??餈質馱
# raw fetcher 敺?response top-level ??`last_update`嚗DK 頝臬??⊥迨甈???蝛?
# caller ??attrs assign block 蝯曹?撖恍?df.attrs嚗策 chip hover tooltip ??
_FINMIND_META: dict = {}   # key: 'price'/'inst'/'margin', value: {last_update, fetched_at}


def _capture_finmind_meta(src_key: str, j_response: dict) -> None:
    """v18.201 D2嚗? FinMind response top-level last_update + ?? wallclock 摮?module dict??""
    try:
        _FINMIND_META[src_key] = {
            "last_update": str(j_response.get("last_update", "") if isinstance(j_response, dict) else ""),
            "fetched_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception:
        _FINMIND_META[src_key] = {"last_update": "", "fetched_at": ""}


def _stamp_finreport_attrs(df, src_key: str, src_val: str):
    """v18.202 E2嚗?鞎∪鞈?皞?+ ???撖恍?df.attrs??

    ?∪? v18.200 B1嚗蝺?蝐Ⅳ/?? src chip嚗? v18.201 D2嚗over tooltip嚗?
    鞎∪銝挾 fetcher ? (df, err) tuple 銝? @st.cache_data嚗? pandas
    DataFrame.attrs ?湔 pickle ?臭???app.py wrapper ?芸? df 頧?嚗?
    ? data_loader 撖怠?喳嚗? app.py attrs.update嚗? fetch_price_data
    韏?.tail().reset_index() ??attrs ??瘜?????
    """
    try:
        df.attrs[f"{src_key}_src"] = src_val
        df.attrs[f"{src_key}_fetched_at"] = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return df


def _bps_dl():
    try:
        from tw_stock_data_fetcher import build_proxy_session as _b
        s = _b()
    except Exception:
        s = _req_dl.Session()
    s.verify = False
    return s

def _yf_dl(symbol, **kwargs):
    """yfinance download嚗? os.environ 瘜典 proxy嚗摰寞?? yfinance嚗?""
    import os as _os_yfd
    try:
        from tw_stock_data_fetcher import _load_proxy_config as _lpc_yfd
        _px_url = ((_lpc_yfd() or {}).get('https') or (_lpc_yfd() or {}).get('http') or None)
    except Exception:
        _px_url = None
    _ek = ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy')
    _bak = {k: _os_yfd.environ.get(k) for k in _ek}
    if _px_url:
        for k in _ek:
            _os_yfd.environ[k] = _px_url
    try:
        return yf.download(symbol, **kwargs)
    finally:
        for k, v in _bak.items():
            if v is None:
                _os_yfd.environ.pop(k, None)
            else:
                _os_yfd.environ[k] = v

_TWSE_DL = _bps_dl()
from stock_names import get_stock_name

# ?? v4.5 ?湔摰??獢 ?????????????????????????????????????????????????
def safe_fetch_strict(data_name: str, fetch_func, ttl: int = 600):
    """
    ?湔???冽??????啁?銝蝙?刻?鞈?嚗?亙??喳仃????
    - ??嚗神??st.session_state.success_cache嚗TL ?勗?急蝞∠?嚗?
    - 憭望?嚗???{'status': 'failed', 'value': None, 'message': '...'}
    - ?交???嚗楊?亥???粹???銝楊?乩蝙?冽憭拙翰??
    """
    _today_str = datetime.date.today().isoformat()
    # 瑼Ｘ session_state 敹怠?
    _sc = getattr(st.session_state, '__dict__', {})
    _cache = st.session_state.get('success_cache', {}) if hasattr(st, 'session_state') else {}
    _entry = _cache.get(data_name)
    if _entry and _entry.get('date') == _today_str:
        _age = datetime.datetime.now().timestamp() - _entry.get('ts', 0)
        if _age < ttl:
            return _entry['data'], 'success'
    # 撖阡???
    try:
        result = fetch_func()
        if result is not None:
            if not hasattr(st.session_state, 'success_cache') or \
               not isinstance(st.session_state.get('success_cache'), dict):
                st.session_state['success_cache'] = {}
            st.session_state['success_cache'][data_name] = {
                'data': result,
                'date': _today_str,
                'ts': datetime.datetime.now().timestamp(),
            }
            return result, 'success'
    except Exception as _e:
        print(f'[safe_fetch] {data_name} ??{type(_e).__name__}: {_e}')
    # 憭望?嚗?蝣箸?閮?銝??喃遙雿???
    return {'status': 'failed', 'value': None,
            'message': f'{data_name} ?急??⊥?????啗???}, 'failed'


_T86_DAY_CACHE: dict = {}  # {?交?摮葡: {?∠巨隞?Ⅳ: {憭?,?縑,?芰??}} ?脩?蝝翰??憭?梁


def _get_t86_day(ds: str) -> dict:
    """?? T86 ?孵??交??撣瘜犖鞈?嚗脩??批翰???銴?瘙?
    ? {?∠巨隞?Ⅳ: {'憭?':float, '?縑':float, '?芰???:float}}嚗雿?撘?""
    if ds in _T86_DAY_CACHE:
        return _T86_DAY_CACHE[ds]
    HDR = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    try:
        r = _fetch_url_dl('https://www.twse.com.tw/fund/T86',
                          params={'response': 'json', 'date': ds, 'selectType': 'ALL'},
                          headers=HDR, timeout=5)
        if r is None:
            _T86_DAY_CACHE[ds] = {}
            return {}
        j = r.json()
        if j.get('stat') != 'OK' or not j.get('data'):
            _T86_DAY_CACHE[ds] = {}
            return {}
        fields = [str(f) for f in j.get('fields', [])]
        fi = {n: i for i, n in enumerate(fields)}
        # T86 甈??迂?具眺鞈?????楊??靘????貉?鞎瑁都頞?詻?靽∟眺鞈???⊥??
        f_idx = next((v for k, v in fi.items() if '憭? in k and '鞎瑁都頞? in k and '?芰?' not in k), None)
        t_idx = next((v for k, v in fi.items() if '?縑' in k and '鞎瑁都頞? in k), None)
        d_idx = next((v for k, v in fi.items() if '?芰?' in k and '鞎瑁都頞? in k and '?芾?' in k), None)
        print(f'[T86] {ds} fields={fields[:5]} f_idx={f_idx} t_idx={t_idx} d_idx={d_idx}')

        def _pn(row, idx):
            if idx is None or idx >= len(row): return 0.0
            try: return round(int(str(row[idx]).replace(',', '').replace('+', '') or 0) / 1000, 1)
            except: return 0.0

        day_data = {}
        for row in j['data']:
            code = str(row[0]).strip()
            if code:
                day_data[code] = {'憭?': _pn(row, f_idx), '?縑': _pn(row, t_idx), '?芰???: _pn(row, d_idx)}
        _T86_DAY_CACHE[ds] = day_data
        print(f'[TWSE T86] {ds}: {len(day_data)} ??)
        return day_data
    except Exception as e:
        print(f'[TWSE T86] {ds} 憭望?: {e}')
        _T86_DAY_CACHE[ds] = {}
        return {}


def _fetch_twse_inst_fallback(stock_id: str, df: pd.DataFrame) -> pd.DataFrame:
    """TWSE T86 ?嚗86 銝甈⊥??典??湛?憭?梁??隞賡脩?敹怠?嚗????潸?瘙?""
    try:
        rows = []
        base = datetime.date.today()
        checked = 0
        for delta in range(20):
            if checked >= 10: break
            d = base - datetime.timedelta(days=delta)
            if d.weekday() >= 5: continue
            day = _get_t86_day(d.strftime('%Y%m%d'))
            checked += 1
            if stock_id in day:
                rows.append({'date': d, **day[stock_id]})
        if rows:
            _df_tw = pd.DataFrame(rows)
            _df_tw['銝餃???'] = _df_tw['憭?'] + _df_tw['?縑'] + _df_tw['?芰???]
            df = pd.merge(df, _df_tw, on='date', how='left')
            print(f'[TWSE T86] {stock_id} 鋆? {len(rows)} ??)
    except Exception as e:
        print(f'[TWSE T86] {stock_id} 憭望?: {e}')
    return df


_TPEX_DAY_CACHE: dict = {}  # {?交?摮葡: {?∠巨隞?Ⅳ: {憭?,?縑,?芰??}} TPEx ?脩?蝝翰??


def _get_tpex_day(ds: str) -> dict:
    """?? TPEx ?孵??交??撣瘜犖鞈?嚗?瑹嚗??脩??批翰??
    ? {?∠巨隞?Ⅳ: {'憭?':float, '?縑':float, '?芰???:float}}嚗雿?撘?""
    if ds in _TPEX_DAY_CACHE:
        return _TPEX_DAY_CACHE[ds]
    HDR = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*',
           'Referer': 'https://www.tpex.org.tw/'}
    try:
        dt = datetime.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
        roc_year = dt.year - 1911
        roc_date = f'{roc_year}/{dt.month:02d}/{dt.day:02d}'
        r = _fetch_url_dl(
            'https://www.tpex.org.tw/web/stock/3insti/daily_report/3itrade_hedge_result.php',
            params={'l': 'zh-tw', 'se': 'EW', 't': 'D', 'd': roc_date, 'o': 'json'},
            headers=HDR, timeout=5)
        if r is None:
            _TPEX_DAY_CACHE[ds] = {}
            return {}
        j = r.json()
        rows_data = j.get('aaData', [])
        if not rows_data:
            _TPEX_DAY_CACHE[ds] = {}
            return {}

        def _pn_tp(row, idx):
            if idx is None or idx >= len(row): return 0.0
            try: return round(int(str(row[idx]).replace(',', '').replace('+', '') or 0) / 1000, 1)
            except: return 0.0

        def _int_tp(row, idx):
            try: return int(str(row[idx]).replace(',', '').replace('+', '') or 0)
            except: return 0

        # ?? ???菜葫甈?蝝Ｗ?嚗Columns ??buy-sell-net 撽?嚗??????????
        # TPEx 璅??澆?嚗0]隞?? [1]?迂
        # 憭? [2]鞎?[3]鞈?[4]瘛? ?縑 [5]鞎?[6]鞈?[7]瘛?
        # ?芰?(?芾?) [8]鞎?[9]鞈?[10]瘛? [11..13]?輸  [14]??
        f_idx, t_idx, d_idx = 4, 7, 10  # ?身蝝Ｗ?

        # ?函洵銝蝑?????霅?buy - sell ??net嚗捆閮?1 撘萎誑?扯炊撌殷?
        for _sample in rows_data[:5]:
            if len(_sample) < 11: continue
            _f_buy = _int_tp(_sample, 2); _f_sell = _int_tp(_sample, 3); _f_net = _int_tp(_sample, 4)
            _t_buy = _int_tp(_sample, 5); _t_sell = _int_tp(_sample, 6); _t_net = _int_tp(_sample, 7)
            if abs(_f_net - (_f_buy - _f_sell)) <= 1000 and abs(_t_net - (_t_buy - _t_sell)) <= 1000:
                break  # 撽???嚗蝙?券?閮剔揣撘?
        else:
            # ?仿?霅憭望?嚗?閰行?雿?撠??澆?嚗??TPEx API ???輸甈?
            # [0]隞?? [1]?迂 [2]憭眺 [3]憭都 [4]憭楊 [5]?眺 [6]?都 [7]?楊 [8]?芾眺 [9]?芾都 [10]?芣楊
            print(f'[TPEx] {ds} 甈?撽?憭望?嚗ow?瑕漲={len(rows_data[0]) if rows_data else 0}嚗蝙?券?閮剔揣撘?)

        day_data = {}
        for row in rows_data:
            code = str(row[0]).strip()
            if not code or len(row) < 11: continue
            day_data[code] = {
                '憭?': _pn_tp(row, f_idx),
                '?縑': _pn_tp(row, t_idx),
                '?芰???: _pn_tp(row, d_idx),
            }
        _TPEX_DAY_CACHE[ds] = day_data
        print(f'[TPEx] {ds} ({roc_date}): {len(day_data)} ??idx=({f_idx},{t_idx},{d_idx})')
        return day_data
    except Exception as e:
        print(f'[TPEx] {ds} 憭望?: {e}')
        _TPEX_DAY_CACHE[ds] = {}
        return {}


def _fetch_tpex_inst_fallback(stock_id: str, df: pd.DataFrame) -> pd.DataFrame:
    """TPEx 銝??⊥?鈭箏??湛??摩??TWSE T86嚗蝙??TPEx 銝之瘜犖 API??""
    try:
        rows = []
        base = datetime.date.today()
        checked = 0
        for delta in range(20):
            if checked >= 10: break
            d = base - datetime.timedelta(days=delta)
            if d.weekday() >= 5: continue
            day = _get_tpex_day(d.strftime('%Y%m%d'))
            checked += 1
            if stock_id in day:
                rows.append({'date': d, **day[stock_id]})
        if rows:
            _df_tp = pd.DataFrame(rows)
            _df_tp['銝餃???'] = _df_tp['憭?'] + _df_tp['?縑'] + _df_tp['?芰???]
            df = pd.merge(df, _df_tp, on='date', how='left')
            print(f'[TPEx] {stock_id} 鋆? {len(rows)} ??)
    except Exception as e:
        print(f'[TPEx] {stock_id} 憭望?: {e}')
    return df


def _normalize_inst_pivot(df_raw: pd.DataFrame) -> pd.DataFrame:
    """??FinMind/T86 ??瘜犖 DataFrame 頧???憭?/?縑/?芰???銝餃??? 甈???pivot??
    df_raw 敹???date / name / buy / sell 甈?嚗雿?～?""
    import re as _re_ni
    df_raw = df_raw.copy()
    df_raw['net_buy'] = (pd.to_numeric(df_raw['buy'],  errors='coerce').fillna(0) -
                         pd.to_numeric(df_raw['sell'], errors='coerce').fillna(0))
    df_raw['date'] = pd.to_datetime(df_raw['date']).dt.date
    pv = df_raw.pivot_table(index='date', columns='name', values='net_buy',
                             aggfunc='sum').reset_index()
    # ?﹦?撘?
    for c in pv.columns:
        if c != 'date':
            pv[c] = pv[c] / 1000
    # ????舀?望?嚗oreign_Investor嚗?銝剜?嚗??貉??佗?
    # 瘜冽?嚗?鞈?? 撅砍?鞈???飛?乓?鞈??????
    rn = {}
    for c in pv.columns:
        cs = str(c); cl = cs.lower()
        cb = _re_ni.split(r'[嚗?鞎瑁都]', cs)[0].strip()
        if ('憭? in cs and '鞈? in cs) or cs in ('憭?', '憭鞈?, '憭??鞈?):
            rn[c] = '憭?'          # 憭鞈?銝憭??芰??? + 憭??芰??????飛憭?
        elif '?縑' in cb:
            rn[c] = '?縑'
        elif '?芰?' in cb and '憭?' not in cs:  # 蝝??扯??
            rn[c] = '?芰???
        elif 'foreign' in cl:
            rn[c] = '憭?'          # ?望??迂嚗 dealer嚗?
        elif 'investment' in cl or 'trust' in cl:
            rn[c] = '?縑'
        elif 'dealer' in cl:
            rn[c] = '?芰???
    print(f'[INST-RENAME] 甈?撠?: {rn}')
    pv.rename(columns=rn, inplace=True)
    # ??甈?雿蛛?pandas 3.0 ?詨捆嚗?
    if pv.columns.duplicated().any():
        _dp = pv[['date']]
        _np = pv.drop(columns=['date'])
        _np = _np.T.groupby(level=0).sum().T
        pv = pd.concat([_dp, _np], axis=1)
    main = [c for c in ['憭?', '?縑', '?芰???] if c in pv.columns]
    if main:
        pv['銝餃???'] = pv[main].sum(axis=1)
    return pv


def _fetch_finmind_inst_raw(stock_id: str, df: pd.DataFrame, start_str: str) -> pd.DataFrame:
    """FinMind ?? API ?嚗?靘陷 Python SDK嚗?
    - ??FINMIND_TOKEN: 雿輻 token ?????
    - ??token: ?踹?隢?嚗inMind ?祇?鞈?嚗???3 req/min嚗??臬?敺?
    """
    import os
    _token = os.environ.get('FINMIND_TOKEN', '')
    _end_str = datetime.date.today().strftime('%Y-%m-%d')
    try:
        _params = {'dataset': 'TaiwanStockInstitutionalInvestorsBuySell',
                   'data_id': stock_id, 'start_date': start_str, 'end_date': _end_str}
        if _token:
            _params['token'] = _token
        _r = _bps_dl().get(
            'https://api.finmindtrade.com/api/v4/data',
            params=_params,
            headers={'Authorization': f'Bearer {_token}'} if _token else {},
            timeout=20)
        _j = _r.json()
        _capture_finmind_meta('inst', _j)   # v18.201 D2嚗???last_update + fetched_at
        if _j.get('data'):
            _first = _j['data'][0]
            _names = list(set(r.get('name','') for r in _j['data'][:20]))
        if _j.get('status') == 200 and _j.get('data'):
            _pv = _normalize_inst_pivot(pd.DataFrame(_j['data']))
            # 蝣箔??拙 date ?銝?游? merge
            _pv['date'] = pd.to_datetime(_pv['date']).dt.date
            df['date']  = pd.to_datetime(df['date']).dt.date
            _df_dates   = set(df['date'])
            _pv_dates   = set(_pv['date'])
            _overlap    = len(_df_dates & _pv_dates)
            df = pd.merge(df, _pv, on='date', how='left')
            _nz = (df.get('憭?', pd.Series(dtype=float)) != 0).sum()
            print(f'[FM-Raw] {stock_id}: ??{len(_j["data"])} 蝑???{len(_pv)} ?? 憭??={_nz}')
        else:
            print(f'[FM-Raw] {stock_id}: status={_j.get("status")} msg={_j.get("msg","")}')
    except Exception as _e:
        print(f'[FM-Raw] {stock_id}: ??{_e}')
    return df


def _fetch_finmind_price_raw(stock_id: str, start_str: str, end_str: str) -> pd.DataFrame:
    """FinMind ?? API ??仕嚗?靘陷 Python SDK嚗?靘?DataLoader=None ???氬?

    ???dl.taiwan_stock_daily ?詨?????雿?date/open/max/min/close/Trading_Volume?佗?嚗?
    ?澆蝡舀窒?冽??rename ?雿???憭望??征 DataFrame??
    """
    import os
    _token = os.environ.get('FINMIND_TOKEN', '')
    try:
        _params = {'dataset': 'TaiwanStockPrice', 'data_id': stock_id,
                   'start_date': start_str, 'end_date': end_str}
        if _token:
            _params['token'] = _token
        _r = _bps_dl().get(
            'https://api.finmindtrade.com/api/v4/data',
            params=_params,
            headers={'Authorization': f'Bearer {_token}'} if _token else {},
            timeout=20)
        _j = _r.json()
        _capture_finmind_meta('price', _j)   # v18.201 D2嚗???last_update + fetched_at
        if _j.get('status') == 200 and _j.get('data'):
            print(f'[FM-Raw price] {stock_id}: ??{len(_j["data"])} 蝑?SDK ?芾??伐?韏?HTTP ?嚗?)
            return pd.DataFrame(_j['data'])
        print(f'[FM-Raw price] {stock_id}: status={_j.get("status")} msg={_j.get("msg","")}')
    except Exception as _e:
        print(f'[FM-Raw price] {stock_id}: ??{_e}')
    return pd.DataFrame()


# ??蛛??孵? StockDataLoader ?摩??bump 甇文?銝莎?靘?app._get_loader 雿
# @st.cache_resource ??cache key???銝?hot-reload 敺??典?祕靘??瘜Ⅳ
# 嚗R #44 靽桐? NoneType 雿?cache_resource ?祕靘?????隞援嚗甇斗?嚗?
_LOADER_VERSION = 'v2-raw-http-fallback'


class StockDataLoader:
    """?啗?豢?撘? - FinMind ?芸?嚗ahoo ?"""

    def __init__(self):
        import os
        self.dl = DataLoader() if DataLoader is not None else None  # [Fixed] DataLoader ?芸?鋆?銝援瞏?
        _fm_token    = os.environ.get('FINMIND_TOKEN', '')
        _fm_user     = os.environ.get('FINMIND_USER', '')
        _fm_password = os.environ.get('FINMIND_PASSWORD', '')
        try:
            if self.dl is None:
                print('[FinMind] ??  SDK ?芾??伐?DataLoader=None嚗??寧 raw HTTP API ?')
                self._token = _fm_token
            elif _fm_token:
                self.dl.login_by_token(api_token=_fm_token)
                print(f'[FinMind] ??Token ?餃??嚗_fm_token[:12]}...嚗?)
                self._token = _fm_token
            elif _fm_user and _fm_password:
                self.dl.login(user_id=_fm_user, password=_fm_password)
                print('[FinMind] ??撣唾??餃??')
                self._token = ''
            else:
                print('[FinMind] ?對?  ?踹?璅∪?嚗?撠?600甈∴?')
                self._token = ''
        except Exception as e:
            print(f'[FinMind] ??  ?餃憭望?嚗e}')
            self._token = _fm_token  # 靽? token 靘?raw HTTP ?雿輻

    @st.cache_data(ttl=CACHE_TTL["price_data"])
    def get_combined_data(_self, stock_id, days, use_adjusted=True):
        """摰?豢?頛瘚?

        Args:
            stock_id: ?∠巨隞?Ⅳ
            days: 頛憭拇
            use_adjusted: True=??K蝺?敺拇?,?身), False=銝?春蝺?
        """
        try:
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=days + 150)
            start_str = start_date.strftime('%Y-%m-%d')

            # ========== 1. ?∪?豢? ==========

            df = None
            _price_src = 'unknown'
            _inst_src = 'unknown'
            _margin_src = 'unknown'

            # ??K蝺?敺拇?)嚗??亦 Yahoo auto_adjust=True ???歇敺拇? OHLC??
            if use_adjusted:
                try:
                    yf_symbol = f"{stock_id}.TW"
                    df_yf_adj = _yf_dl(
                        yf_symbol,
                        start=start_date,
                        end=end_date + datetime.timedelta(days=1),
                        auto_adjust=True,
                        progress=False
                    )
                    # ??.TW ?亦鞈?嚗?閰?.TWO嚗?瑹蟡剁?
                    if df_yf_adj.empty:
                        yf_symbol = f"{stock_id}.TWO"
                        df_yf_adj = _yf_dl(
                            yf_symbol,
                            start=start_date,
                            end=end_date + datetime.timedelta(days=1),
                            auto_adjust=True,
                            progress=False
                        )
                    if not df_yf_adj.empty:
                        df_yf_adj = df_yf_adj.reset_index()

                        # ?? MultiIndex
                        if isinstance(df_yf_adj.columns, pd.MultiIndex):
                            df_yf_adj.columns = df_yf_adj.columns.get_level_values(0)

                        df_yf_adj.columns = [str(c).lower() for c in df_yf_adj.columns]

                        # reset_index 敺虜??date 甈?
                        if 'date' not in df_yf_adj.columns and 'datetime' in df_yf_adj.columns:
                            df_yf_adj = df_yf_adj.rename(columns={'datetime': 'date'})

                        df_yf_adj['date'] = pd.to_datetime(df_yf_adj['date']).dt.date

                        # ?漱????-> 撘?
                        if 'volume' in df_yf_adj.columns:
                            df_yf_adj['volume'] = (df_yf_adj['volume'] / 1000).round().astype(int)
                        else:
                            df_yf_adj['volume'] = 0

                        df = df_yf_adj[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
                        _price_src = 'yahoo_adj'
                        print("????K蝺?Yahoo auto_adjust=True嚗?亦?????OHLC嚗?)
                except Exception as e:
                    print(f"?? ??K蝺?Yahoo auto_adjust 憭望?嚗??FinMind ???對?{e}")
                    df = None

            # ?交雿輻??K蝺? Yahoo 憭望?嚗?韏?FinMind嚗??春蝺?/ ?嚗?
            if df is None:
                if _self.dl is not None:
                    df_price = _self.dl.taiwan_stock_daily(
                        stock_id=stock_id,
                        start_date=start_str,
                        end_date=end_date.strftime('%Y-%m-%d'),
                    )
                    _fm_path = 'finmind_sdk'
                    _capture_finmind_meta('price', {})   # v18.201 D2嚗DK ??response ???芾? fetched_at
                else:
                    # FinMind SDK ?芾??伐?DataLoader=None嚗? raw HTTP ?嚗??NoneType 撏拇蔑
                    df_price = _fetch_finmind_price_raw(
                        stock_id, start_str, end_date.strftime('%Y-%m-%d'))
                    _fm_path = 'finmind_raw'

                if df_price.empty:
                    # Yahoo ?嚗? .TW嚗?閰?.TWO 銝?嚗?
                    yf_symbol = f"{stock_id}.TW"
                    df_yf = _yf_dl(yf_symbol, start=start_date, progress=False)
                    if df_yf.empty:
                        yf_symbol = f"{stock_id}.TWO"
                        df_yf = _yf_dl(yf_symbol, start=start_date, progress=False)
                    if df_yf.empty:
                        return None, "???亦鞈?", None

                    df_yf = df_yf.reset_index()

                    # ========== ???儔甈??刻?撠神銋?嚗?=========
                    has_adj = False
                    adj_ratio_values = None
                    if isinstance(df_yf.columns, pd.MultiIndex):
                        df_yf.columns = df_yf.columns.get_level_values(0)

                    # 瑼Ｘ銝西?蝞儔甈?靘??摮絲靘?
                    if 'Adj Close' in df_yf.columns and 'Close' in df_yf.columns and use_adjusted:
                        adj_ratio_values = (df_yf['Adj Close'] / df_yf['Close']).values
                        adj_close_values = df_yf['Adj Close'].values
                        has_adj = True
                        print("??Yahoo ?嚗蝙?典儔甈???)

                    # 頧?撖?
                    df_yf.columns = [str(c).lower() for c in df_yf.columns]
                    df_yf['date'] = pd.to_datetime(df_yf['date']).dt.date

                    # ?敺拇?
                    if has_adj and use_adjusted and adj_ratio_values is not None:
                        df_yf['open'] = df_yf['open'] * adj_ratio_values
                        df_yf['high'] = df_yf['high'] * adj_ratio_values
                        df_yf['low'] = df_yf['low'] * adj_ratio_values
                        df_yf['close'] = adj_close_values

                    df_yf['volume'] = (df_yf['volume'] / 1000).round().astype(int)
                    df = df_yf[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
                    _price_src = 'yahoo_fallback'
                else:
                    # FinMind ?豢?
                    _price_src = _fm_path
                    df = df_price.rename(columns={
                        'Trading_Volume': 'volume',
                        'max': 'high',
                        'min': 'low'
                    })[['date', 'open', 'high', 'low', 'close', 'volume']].copy()

                    df['date'] = pd.to_datetime(df['date']).dt.date
                    df['volume'] = (df['volume'] / 1000).astype(int)

                    # ========== 敺拇???嚗? Yahoo ?脣?嚗?=========
                    if use_adjusted:
                        try:
                            yf_symbol = f"{stock_id}.TW"
                            df_adj = _yf_dl(yf_symbol, start=start_date, progress=False)

                            if not df_adj.empty:
                                df_adj = df_adj.reset_index()

                                # ?? MultiIndex
                                if isinstance(df_adj.columns, pd.MultiIndex):
                                    df_adj.columns = df_adj.columns.get_level_values(0)

                                # 閮?敺拇?瘥?
                                if 'Adj Close' in df_adj.columns and 'Close' in df_adj.columns:
                                    df_adj['date_key'] = pd.to_datetime(df_adj['Date']).dt.date
                                    df_adj['adj_ratio'] = df_adj['Adj Close'] / df_adj['Close']

                                    # ?蔥敺拇?瘥?
                                    df = df.merge(df_adj[['date_key', 'adj_ratio']],
                                                  left_on='date', right_on='date_key', how='left')

                                    # 憛怨?蝻箏仃?潛 1.0嚗?隤踵嚗?
                                    df['adj_ratio'] = df['adj_ratio'].fillna(1.0)

                                    # ?敺拇??唳????
                                    df['open'] = df['open'] * df['adj_ratio']
                                    df['high'] = df['high'] * df['adj_ratio']
                                    df['low'] = df['low'] * df['adj_ratio']
                                    df['close'] = df['close'] * df['adj_ratio']

                                    # 皜?甈?
                                    df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
                                    print("??FinMind嚗儔甈???)
                                else:
                                    print("?? Yahoo ??Adj Close嚗蝙?典?憪??)
                            else:
                                print("?? Yahoo ?∟???雿輻???寞")
                        except Exception as e:
                            print(f"?? 敺拇?憭望?: {e}")
                            # 憭望??Ⅱ靽?df ?芣??箸甈?
                            df = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()

            # ========== 2. ?∠巨?迂 ==========

            stock_name = stock_id
            try:
                stock_info = _self.dl.taiwan_stock_info()
                if not stock_info.empty:
                    match = stock_info[stock_info['stock_id'] == stock_id]
                    if not match.empty:
                        stock_name = match.iloc[0]['stock_name']
            except:
                pass

            if stock_name == stock_id:
                stock_name = get_stock_name(stock_id)

            # ========== 3. ?? ==========
            for period in [5, 10, 20, 60, 100, 120, 240]:
                df[f'MA{period}'] = df['close'].rolling(window=period).mean()

            # ========== 4. 銝之瘜犖 ==========
            if _self.dl is not None:
                try:
                    df_inst = _self.dl.taiwan_stock_institutional_investors(
                        stock_id=stock_id,
                        start_date=start_str
                    )
                    _sdk_ok = (df_inst is not None and
                               hasattr(df_inst, 'empty') and
                               not df_inst.empty)
                    if _sdk_ok:
                        df_pivot = _normalize_inst_pivot(df_inst)
                        df_pivot['date'] = pd.to_datetime(df_pivot['date']).dt.date
                        df['date']       = pd.to_datetime(df['date']).dt.date
                        _overlap = len(set(df['date']) & set(df_pivot['date']))
                        df = pd.merge(df, df_pivot, on='date', how='left')
                        _nz = (df.get('憭?', pd.Series(dtype=float)) != 0).sum()
                        print(f'[蝐Ⅳ] {stock_id}: SDK ??憭??={_nz}', flush=True)
                        _sdk_used = True
                        _inst_src = 'finmind_sdk'
                        _capture_finmind_meta('inst', {})   # v18.201 D2
                    else:
                        _sdk_used = False
                except Exception as e:
                    _sdk_used = False
            else:
                _sdk_used = False

            if not _sdk_used:
                # SDK 銝????FinMind Raw HTTP API嚗?靘陷 SDK嚗?
                df = _fetch_finmind_inst_raw(stock_id, df, start_str)
                if '憭?' in df.columns:
                    _inst_src = 'finmind_raw'
                if '憭?' not in df.columns:
                    df = _fetch_twse_inst_fallback(stock_id, df)
                    if '憭?' in df.columns:
                        _inst_src = 'twse'
                if '憭?' not in df.columns:
                    df = _fetch_tpex_inst_fallback(stock_id, df)
                    if '憭?' in df.columns:
                        _inst_src = 'tpex'
                if _inst_src == 'unknown':
                    _inst_src = 'missing'

            # ========== 5. ??? ==========
            try:
                df_margin = _self.dl.taiwan_stock_margin_purchase_short_sale(
                    stock_id=stock_id,
                    start_date=start_str
                )

                if not df_margin.empty:
                    df_margin['date'] = pd.to_datetime(df_margin['date']).dt.date

                    margin_data = df_margin[['date', 'MarginPurchaseTodayBalance', 'ShortSaleTodayBalance']].copy()
                    margin_data.rename(columns={
                        'MarginPurchaseTodayBalance': '??擗?',
                        'ShortSaleTodayBalance': '?擗?'
                    }, inplace=True)

                    margin_data['??擗?'] = pd.to_numeric(margin_data['??擗?'], errors='coerce')
                    margin_data['?擗?'] = pd.to_numeric(margin_data['?擗?'], errors='coerce')

                    df = pd.merge(df, margin_data, on='date', how='left')
                    _margin_src = 'finmind_sdk'
                    _capture_finmind_meta('margin', {})   # v18.201 D2
                else:
                    _margin_src = 'missing'

            except Exception as e:
                print(f"???豢??航炊: {e}")
                _margin_src = 'missing'

            # ========== 6. ?豢?皜? ==========
            # 憛怨?0
            fill_cols = ['volume', '憭?', '?縑', '?芰???, '銝餃???']
            for col in fill_cols:
                if col in df.columns:
                    df[col] = df[col].fillna(0)

            # ???脣?嚗?蔥敺???銴???????嚗??pd.to_numeric ?嗅 DataFrame嚗?
            if df.columns.duplicated().any():
                # ??甈?隞亙?蝮賢?雿蛛?pandas 3.0 蝘駁 axis=1嚗??T.groupby.T嚗?
                df = df.T.groupby(level=0).sum().T

            # 撘瑕頧??
            numeric_cols = ['open', 'high', 'low', 'close', 'volume',
                          '憭?', '?縑', '?芰???, '銝餃???', '??擗?', '?擗?']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # ========== 7. ?蝯撓??==========
            # ?蕪??文???aN??嚗?翰??⊥?鞈?嚗?
            df = df[pd.to_numeric(df['close'], errors='coerce').fillna(0) > 0].copy()
            df = df.sort_values('date').tail(days).reset_index(drop=True)

            # ?日
            k_type = "??K蝺?敺拇?)" if use_adjusted else "銝?春蝺??芸儔甈?"
            print(f"\n????交??stock_id} {stock_name} - {k_type}")
            print(f"鞈?蝑: {len(df)}")
            if '憭?' in df.columns:
                print(f"憭?甈?憿?: {df['憭?'].dtype}")
                print(f"?敺?蝑?鞈?? {df['憭?'].tail(3).tolist()}")

            try:
                df.attrs['price_src'] = _price_src
                df.attrs['inst_src'] = _inst_src
                df.attrs['margin_src'] = _margin_src
                # v18.201 D2嚗inMind dataset 敺 update ?? + 摰Ｘ蝡舀???wallclock
                for _k in ('price', 'inst', 'margin'):
                    _meta = _FINMIND_META.get(_k, {}) or {}
                    df.attrs[f'{_k}_last_update'] = _meta.get('last_update', '')
                    df.attrs[f'{_k}_fetched_at'] = _meta.get('fetched_at', '')
            except Exception:
                pass

            return df, None, stock_name

        except Exception as e:
            import traceback
            traceback.print_exc()
            return None, f"蝟餌絞?航炊: {str(e)}", None

    @st.cache_data(ttl=CACHE_TTL["price_data"])
    def get_monthly_revenue(_self, stock_id):
        """???嗅??摨?MOPS(摰) ??FinMind"""
        import os as _os_rv, datetime as _dt_rv
        import pandas as _pd_rv
        _tok = (_os_rv.environ.get('FINMIND_TOKEN','') or
                _os_rv.environ.get('FM_TOKEN',''))
        end_date   = _dt_rv.date.today()
        start_date = end_date - _dt_rv.timedelta(days=1095)
        start_str  = start_date.strftime('%Y-%m-%d')
        df_revenue = None
        _rev_src = 'unknown'   # v18.202 E2嚗??鞈?皞?finmind / mops / missing嚗?

        # ?? ?寞?0: FinMind TaiwanStockMonthRevenue嚗??MOPS year-file?券404嚗?
        if _tok and df_revenue is None:
            try:
                _r_fm0 = _bps_dl().get(
                    'https://api.finmindtrade.com/api/v4/data',
                    params={'dataset':'TaiwanStockMonthRevenue',
                            'data_id':stock_id, 'start_date':start_str,
                            'token':_tok},
                    headers={'Authorization':f'Bearer {_tok}'}, timeout=20)
                _j0r = _r_fm0.json()
                print(f'[FM-Rev0] {stock_id}: status={_j0r.get("status")} rows={len(_j0r.get("data",[]))}')
                if _j0r.get('status')==200 and _j0r.get('data'):
                    _df0r = _pd_rv.DataFrame(_j0r['data'])
                    if 'revenue' in _df0r.columns:
                        if 'date' not in _df0r.columns:
                            _df0r['date'] = (_df0r['revenue_year'].astype(str)+'-'+
                                             _df0r['revenue_month'].astype(str).str.zfill(2)+'-01')
                        _df0r['date'] = _pd_rv.to_datetime(_df0r['date'])
                        df_revenue = _df0r.sort_values('date').reset_index(drop=True)
                        _rev_src = 'finmind'   # v18.202 E2
                        print(f'[FM-Rev0] {stock_id}: ??{len(df_revenue)}蝑?)
            except Exception as _e0r:
                print(f'[FM-Rev0] {stock_id}: ??{type(_e0r).__name__}: {_e0r}')


        # ?? ?寞?0: FinMind ???塚??芸?嚗?MOPS 撟港遢HTML?券404嚗????
        if df_revenue is None and _tok:
            try:
                _rfm0 = _bps_dl().get(
                    'https://api.finmindtrade.com/api/v4/data',
                    params={'dataset':'TaiwanStockMonthRevenue',
                            'data_id':stock_id,'start_date':start_str,'token':_tok},
                    headers={'Authorization':f'Bearer {_tok}'}, timeout=20)
                _jfm0 = _rfm0.json()
                print(f'[FM-Rev] {stock_id}: status={_jfm0.get("status")} rows={len(_jfm0.get("data",[]))}')
                if _jfm0.get('status')==200 and _jfm0.get('data'):
                    _dffm0 = _pd_rv.DataFrame(_jfm0['data'])
                    if 'revenue' in _dffm0.columns:
                        if 'date' not in _dffm0.columns:
                            _dffm0['date'] = (_dffm0['revenue_year'].astype(str)+'-'+
                                              _dffm0['revenue_month'].astype(str).str.zfill(2)+'-01')
                        _dffm0['date'] = _pd_rv.to_datetime(_dffm0['date'])
                        df_revenue = _dffm0.sort_values('date').reset_index(drop=True)
                        _rev_src = 'finmind'   # v18.202 E2
                        print(f'[FM-Rev] {stock_id}: ??{len(df_revenue)}蝑?)
            except Exception as _efm0:
                print(f'[FM-Rev] {stock_id}: ??{type(_efm0).__name__}: {_efm0}')

        # ?? ?寞?A: MOPS ???塚?摰靘?嚗? Token嚗??????????
        try:
            import pandas as _pd_mops
            _today_rv = _dt_rv.date.today()
            for _y_offset_rv in range(3):
                _yr = _today_rv.year - _y_offset_rv
                for _mops_url_rv in [
                    f'https://mops.twse.com.tw/nas/t21/sii/t21sc03_{_yr}_0.html',
                    f'https://mops.twse.com.tw/nas/t21/otc/t21sc03_{_yr}_0.html',
                    f'https://mops.twse.com.tw/nas/t21/sii/t21sc03_{_yr-1}_0.html',
                    f'https://mops.twse.com.tw/nas/t21/otc/t21sc03_{_yr-1}_0.html',
                ]:
                    try:
                        _rm2 = _fetch_url_dl(_mops_url_rv,
                                             headers={'User-Agent': 'Mozilla/5.0'},
                                             timeout=12)
                        if _rm2 is None: continue
                        _dfs_m2 = _pd_mops.read_html(_rm2.text)
                        _mops_rows2 = []
                        for _dm2 in _dfs_m2:
                            _dm2.columns = [str(c) for c in _dm2.columns]
                            _id_c = next((c for c in _dm2.columns if
                                any(k in c for k in ['隞??','?∠巨隞?Ⅳ','?砍隞??'])), None)
                            _rv_c = next((c for c in _dm2.columns if
                                '?嗆?' in c and ('?? in c or '?' in c)), None)
                            _yoy_c = next((c for c in _dm2.columns if
                                'YoY' in c or '撟游?' in c), None)
                            if not _id_c or not _rv_c: continue
                            _row2 = _dm2[_dm2[_id_c].astype(str).str.strip()==str(stock_id)]
                            if _row2.empty: continue
                            for _, _r2 in _row2.iterrows():
                                try:
                                    _rv2 = float(str(_r2[_rv_c]).replace(',',''))
                                    _yoy2 = float(str(_r2.get(_yoy_c,0)).replace(',','').replace('%','')) if _yoy_c else None
                                    if _rv2 > 0:
                                        _mops_rows2.append({
                                            'revenue': _rv2 * 1000,
                                            'date': f'{_yr}-{_today_rv.month:02d}-01',
                                            'yoy': _yoy2})
                                except: pass
                        if _mops_rows2:
                            df_revenue = _pd_mops.DataFrame(_mops_rows2)
                            df_revenue['date'] = _pd_mops.to_datetime(df_revenue['date'])
                            _rev_src = 'mops'   # v18.202 E2
                            print(f'[MOPS-Rev] {stock_id}: ??{len(df_revenue)} 蝑?)
                            break
                    except: continue
                if df_revenue is not None: break
        except Exception as _eM_rv:
            print(f'[MOPS-Rev] {stock_id}: {_eM_rv}')

        # ?? ?寞?B: FinMind TaiwanStockMonthRevenue嚗PI嚗?Token嚗??
        if df_revenue is None and _tok:
            try:
                import requests as _rq_fm_rv
                _r = _rq_fm_rv.get(
                    'https://api.finmindtrade.com/api/v4/data',
                    params={'dataset': 'TaiwanStockMonthRevenue',
                            'data_id': stock_id,
                            'start_date': start_str,
                            'token': _tok},
                    headers={'Authorization': f'Bearer {_tok}'},
                    timeout=20)
                _j = _r.json()
                print(f'[FM-Rev] {stock_id}: status={_j.get("status")} rows={len(_j.get("data",[]))}')
                if _j.get('status') == 200 and _j.get('data'):
                    _df = _pd_rv.DataFrame(_j['data'])
                    # 甈?嚗ate, revenue, revenue_year, revenue_month
                    # 蝯曹?甈???
                    _rename = {}
                    for _c in _df.columns:
                        if 'revenue' == _c.lower(): _rename[_c] = 'revenue'
                        elif 'year'  in _c.lower(): _rename[_c] = 'revenue_year'
                        elif 'month' in _c.lower(): _rename[_c] = 'revenue_month'
                    _df = _df.rename(columns=_rename)
                    if 'date' not in _df.columns and 'revenue_year' in _df.columns:
                        _df['date'] = _df['revenue_year'].astype(str) + '-' + _df['revenue_month'].astype(str).str.zfill(2) + '-01'
                    if 'revenue' in _df.columns:
                        _df['date'] = _pd_rv.to_datetime(_df['date'])
                        _df = _df.sort_values('date')
                        df_revenue = _df
                        _rev_src = 'finmind'   # v18.202 E2
                        print(f'[FM-Rev] {stock_id}: ??{len(df_revenue)} 蝑?)
            except Exception as _eF:
                print(f'[FM-Rev] {stock_id}: {_eF}')

        # ?? ?寞?B2: MOPS 瘥僑?遢蝯梯?銵剁???孵?嚗???????????????
        if df_revenue is None:
            try:
                _mops_rows = []
                _today = _dt_rv.date.today()
                for _y_offset in range(3):
                    _y = _today.year - _y_offset
                    _url_mops = ('https://mops.twse.com.tw/nas/t21/sii/'
                                 f't21sc03_{_y}_0.html')
                    _rm = _fetch_url_dl(_url_mops,
                                        headers={'User-Agent': 'Mozilla/5.0'},
                                        timeout=15)
                    if _rm is None: continue
                    _dfs_m = _pd_rv.read_html(_rm.text)
                    for _dm in _dfs_m:
                        _dm.columns = [str(c) for c in _dm.columns]
                        # ?曆誨蝣潭?
                        _id_col = next((c for c in _dm.columns
                                        if any(k in c for k in ['隞??','?∠巨隞?Ⅳ','?砍隞??'])), None)
                        _rv_col = next((c for c in _dm.columns
                                        if '?嗆?' in c and ('?? in c or '?' in c)), None)
                        if not _id_col or not _rv_col: continue
                        _row = _dm[_dm[_id_col].astype(str).str.strip() == str(stock_id)]
                        if _row.empty: continue
                        for _, _r in _row.iterrows():
                            try:
                                _rv = float(str(_r[_rv_col]).replace(',',''))
                                if _rv > 0:
                                    _mops_rows.append({'revenue': _rv * 1000,
                                                       'date': f'{_y}-{_today.month:02d}-01'})
                            except: pass
                if _mops_rows:
                    df_revenue = _pd_rv.DataFrame(_mops_rows)
                    df_revenue['date'] = _pd_rv.to_datetime(df_revenue['date'])
                    _rev_src = 'mops'   # v18.202 E2
                    print(f'[MOPS-Rev] {stock_id}: ??{len(df_revenue)} 蝑?)
            except Exception as _eM:
                print(f'[MOPS-Rev] {stock_id}: {_eM}')

        if df_revenue is not None and not df_revenue.empty:
            # 閮? YoY
            if 'revenue' in df_revenue.columns:
                df_revenue['yoy'] = df_revenue['revenue'].pct_change(12) * 100
            _stamp_finreport_attrs(df_revenue, 'rev', _rev_src)   # v18.202 E2
            return df_revenue, None
        return None, '???塚????皞?憭望?嚗OPS/FinMind嚗?

    def get_quarterly_data(_self, stock_id):
        """頛餈?撟游迤摨西瓷???摮???嗚迤瘥??

        ?箔??踹?銝?鞈?皞??ype??雿撘?銝?湛?靘?嚗1/Q2?迤?晞uarter 蝑?嚗?
        ?ㄐ?∠??撖祇??? ???閬?颲刻?摮?漲???孵?嚗?擃?????
        """
        try:
            import re
            # ??餈?3 撟渲???蝝?12 摮?+ buffer嚗?
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=1200)
            start_str = start_date.strftime('%Y-%m-%d')

            # ?岫 FinMind REST API
            df_fin = None
            _qtr_src = 'unknown'   # v18.202 E2嚗迤鞎∪鞈?皞?finmind_rest / finmind_sdk / yfinance / missing嚗?
            try:
                import os as _os_q; import requests as _rq_q
                _tok_q = _os_q.environ.get('FINMIND_TOKEN', '')
                # ?祥??TaiwanStockFinancialStatement嚗s嚗?隞祥???嚗?閰?
                _df_q_tmp = None
                for _ds_q in ['TaiwanStockFinancialStatement', 'TaiwanStockFinancialStatements']:
                    try:
                        _pq = {'dataset': _ds_q, 'data_id': stock_id, 'start_date': start_str}
                        if _tok_q: _pq['token'] = _tok_q  # FinMind v4 ?閬?token ??params
                        _resp_q = _rq_q.get('https://api.finmindtrade.com/api/v4/data',
                            params=_pq,
                            headers={'Authorization': f'Bearer {_tok_q}'} if _tok_q else {},
                            timeout=25)
                        _jd_q = _resp_q.json()
                        print(f'[摮?瓷?崇EST/{_ds_q}] {stock_id} status={_jd_q.get("status")}, rows={len(_jd_q.get("data",[]))}')
                        if _jd_q.get('data'):
                            _types = list(set(r.get('type','') for r in _jd_q['data'][:30]))
                        if _jd_q.get('status') == 200 and _jd_q.get('data'):
                            _df_q_tmp = pd.DataFrame(_jd_q['data'])
                            break
                    except Exception as _eq2:
                        print(f'[摮?瓷?崇EST/{_ds_q}] {_eq2}')
                if _df_q_tmp is not None and not _df_q_tmp.empty:
                    df_fin = _df_q_tmp
                    _qtr_src = 'finmind_rest'   # v18.202 E2
            except Exception as _eq:
                print(f'[摮?瓷?崇EST] {_eq}')

            # ?: FinMind Library
            if df_fin is None or df_fin.empty:
                try:
                    df_fin = _self.dl.taiwan_stock_financial_statement(
                        stock_id=stock_id, start_date=start_str)
                    if df_fin is not None and not df_fin.empty:
                        _qtr_src = 'finmind_sdk'   # v18.202 E2
                except Exception: pass

            if df_fin is None or df_fin.empty:
                # ?? ?: yfinance 摮?漲 ??
                try:
                    import yfinance as _yf_q
                    for _sfx_q in ('.TW', '.TWO'):
                        _tk_q = _yf_q.Ticker(f"{stock_id}{_sfx_q}")
                        _qf_q = (getattr(_tk_q, 'quarterly_income_stmt', None)
                                 or getattr(_tk_q, 'quarterly_financials', None))
                        if _qf_q is not None and not _qf_q.empty:
                            break
                    if _qf_q is not None and not _qf_q.empty:
                        _rows_yf = []
                        # ?曉 Revenue ??Gross Profit ??index label
                        _rev_row = next((idx for idx in _qf_q.index if any(k in str(idx) for k in ['Revenue','Total Revenue','revenue'])), None)
                        _gp_row  = next((idx for idx in _qf_q.index if 'Gross Profit' in str(idx) or 'GrossProfit' in str(idx)), None)
                        for _col_q in _qf_q.columns:
                            _dt_q = pd.Timestamp(_col_q)
                            _qt_num = ((_dt_q.month - 1) // 3) + 1
                            _rev_val = float(_qf_q.loc[_rev_row, _col_q]) if _rev_row is not None else float('nan')
                            _gp_val  = float(_qf_q.loc[_gp_row,  _col_q]) if _gp_row  is not None else float('nan')
                            _rows_yf.append({'date': _dt_q.strftime('%Y-%m-%d'),
                                              'type': f'Q{_qt_num}', 'value': _rev_val,
                                              'origin_name': '?平?嗅??', 'stock_id': stock_id})
                            if not pd.isna(_gp_val):
                                _rows_yf.append({'date': _dt_q.strftime('%Y-%m-%d'),
                                                  'type': f'Q{_qt_num}', 'value': _gp_val,
                                                  'origin_name': '瘥', 'stock_id': stock_id})
                        if _rows_yf:
                            df_fin = pd.DataFrame(_rows_yf)
                            _qtr_src = 'yfinance'   # v18.202 E2
                            print(f"[yfinance QTR] {stock_id}: ??{len(df_fin)}蝑?(?急???{_gp_row is not None})")
                except Exception as _eYF_q:
                    print(f"[yfinance QTR] {stock_id}: {_eYF_q}")

            if df_fin is None or df_fin.empty:
                return None, f"{stock_id} 摮?瓷?梧????皞?FinMind/yfinance嚗??∟???

            # ===== 0) ?斗?臬???∴??踹????砍?賊?頛臬??圈??嚗?====
            def _is_financial_stock(_sid: str) -> bool:
                try:
                    info = _self.dl.taiwan_stock_info()
                    if info is not None and not info.empty and 'stock_id' in info.columns:
                        m2 = info[info['stock_id'] == _sid]
                        if not m2.empty:
                            row = m2.iloc[0].to_dict()
                            # ?岫敺?賜??Ｘ平甈??斗
                            for k in ['industry_category', 'industry', 'category', 'type', '?Ｘ平??, '?Ｘ平憿', '?Ｘ平??', 'industry_category_zh']:
                                if k in row and row[k] is not None:
                                    s = str(row[k])
                                    if any(w in s for w in ['??', '靽', '?', '?銵?, '霅']):
                                        return True
                except Exception:
                    pass
                # 靽?嚗?⊿???蝢文虜閬誨蝣澆?蝬?
                return str(_sid).startswith(('28', '58'))

            is_finance = _is_financial_stock(stock_id)

            # ===== ???∴?摮???嗆?具???蜇??瘥??閮? =====
            if is_finance:
                try:
                    df_m, err_m = _self.get_monthly_revenue(stock_id)
                    if err_m is None and df_m is not None and not df_m.empty:
                        df_m = df_m.copy()
                        col_date = '?交?' if '?交?' in df_m.columns else ('date' if 'date' in df_m.columns else None)
                        col_rev  = '?' if '?' in df_m.columns else ('revenue' if 'revenue' in df_m.columns else None)
                        if col_date is not None and col_rev is not None:
                            df_m[col_date] = pd.to_datetime(df_m[col_date], errors='coerce')
                            df_m = df_m.dropna(subset=[col_date]).sort_values(col_date)
                            df_m['_y'] = df_m[col_date].dt.year.astype('int64')
                            df_m['_q'] = (((df_m[col_date].dt.month - 1) // 3) + 1).astype('int64')
                            df_m[col_rev] = pd.to_numeric(df_m[col_rev], errors='coerce')
                            qsum = df_m.groupby(['_y', '_q'])[col_rev].sum().reset_index()
                            qsum = qsum.rename(columns={'_y': '撟游漲', '_q': '摮?漲', col_rev: '?'})
                            qsum['摮?漲璅惜'] = qsum['撟游漲'].astype(str) + 'Q' + qsum['摮?漲'].astype(str)
                            qsum['瘥??] = pd.NA
                            qsum['瘥??蝔?] = '瘥??
                            qsum['?臬????] = True
                            return qsum, None
                except Exception:
                    # ?交???蜇銋仃???匱蝥粥銝???祇?頛荔??踹??湔挾銝剜嚗?
                    pass


            # ===== ?日鞈?嚗????其??斗 API 甈??澆?嚗?====
            print(f"甈?: {df_fin.columns.tolist()}")
            print(f"蝮賜??? {len(df_fin)}")

            # ===== 1) ??閰西儘霅迤摨艾???=====
            df_work = df_fin.copy()

            # ??鞈?? type 銵函內摮?漲/撟游漲嚗???type 頧?摮葡靘踵?斗
            if 'type' in df_work.columns:
                df_work['type'] = df_work['type'].astype(str)
                type_uniques = sorted(df_work['type'].dropna().unique().tolist())

                # 撣貉?摮?漲??嚗1/Q2/Q3/Q4??Q/2Q...?迤?晞uarter?迤
                q_mask = df_work['type'].str.contains(r"(?:^Q[1-4]$|^[1-4]Q$|摮ㄍ摮?|quarter)", case=False, na=False)
                df_q = df_work[q_mask].copy()

                # ?仿?瞈曉??蝛綽?隞?” type 銝?車?澆?嚗?憒?祆?????嚗停???券?鞈?
                if not df_q.empty:
                    df_work = df_q
                # else: type甈??澆?銝泵嚗匱蝥蝙?典????

            # ===== 2) Pivot嚗ate x 蝘 =====
            need_cols = {'date', 'origin_name', 'value'}
            if not need_cols.issubset(set(df_work.columns)):
                # 蝻箸?雿停?湔?嚗蒂???桀?甈?嚗靘踹?雿?
                return None, f"摮?漲鞎∪甈?銝雲嚗?閬?date/origin_name/value嚗??桀??芣?: {', '.join(df_work.columns.astype(str).tolist()[:20])}"

            df_pivot = df_work.pivot_table(
                index=['date'],
                columns='origin_name',
                values='value',
                aggfunc='first'
            ).reset_index()

            # date 頧???
            df_pivot['date'] = pd.to_datetime(df_pivot['date'], errors='coerce')
            df_pivot = df_pivot[df_pivot['date'].notna()].copy()
            if df_pivot.empty:
                return None, "摮?漲鞎∪?交?甈??⊥?閫??"

            # ===== 3) 撱箇?摮?漲璅惜 =====
            df_quarterly = pd.DataFrame()
            df_quarterly['撟游漲'] = df_pivot['date'].dt.year
            df_quarterly['摮?漲'] = ((df_pivot['date'].dt.month - 1) // 3) + 1
            df_quarterly['摮?漲璅惜'] = df_quarterly['撟游漲'].astype(int).astype(str) + 'Q' + df_quarterly['摮?漲'].astype(int).astype(str)

            # ===== 4) ?整??嗚?雿?銝?砍?詨????????冽???蜇雿摮?漲?嚗?====
            is_finance = False
            revenue_candidates = []
            for col in df_pivot.columns:
                c = str(col)
                if any(k in c for k in ['?平?嗅', '?嗅??', '?']) or re.search(r"\brevenue\b", c, re.I):
                    revenue_candidates.append(col)

            # ??/靽撣貉????嗡誨??雿?銝?摰??潛??塚?雿?其??斗?臬?粹??嚗?
            finance_candidates = []
            for col in df_pivot.columns:
                c = str(col)
                if any(k in c for k in ['瘛冽??, '?拇瘛冽??, '?拇隞亙?瘛冽??, '靽鞎皞?瘛刻???]) or re.search(r"interest\s*net\s*income|net\s*interest|net\s*revenue", c, re.I):
                    finance_candidates.append(col)

            if revenue_candidates:
                rev_col = revenue_candidates[0]
                df_quarterly['?'] = pd.to_numeric(df_pivot[rev_col], errors='coerce')
            else:
                # ?曆??唬??祉??嗆?雿?敺?賣?????
                is_finance = True if finance_candidates else True
                # ?鞎∪銝剔?隞??甈?憓?嚗?征?潘?嚗?蝥??具???蜇???迤摨衣???
                if finance_candidates:
                    rev_col = finance_candidates[0]
                    df_quarterly['?'] = pd.to_numeric(df_pivot[rev_col], errors='coerce')
                else:
                    df_quarterly['?'] = pd.NA

            # ???∴?摮?漲?銝敺誑??? 3 ???蜇?皞?撠??頠??迤?嚗?
            if is_finance:
                df_month, _merr = _self.get_monthly_revenue(stock_id)
                if df_month is not None and not df_month.empty:
                    dfm = df_month[['撟?, '??, '?']].copy()
                    dfm['?交?'] = pd.to_datetime(dfm['撟?].astype(str) + '-' + dfm['??].astype(int).astype(str).str.zfill(2) + '-01', errors='coerce')
                    dfm = dfm[dfm['?交?'].notna()].copy()
                    dfm['撟游漲'] = dfm['?交?'].dt.year.astype(int)
                    dfm['摮?漲'] = (((dfm['?交?'].dt.month - 1) // 3) + 1).astype(int)
                    qsum = dfm.groupby(['撟游漲', '摮?漲'], as_index=False)['?'].sum()
                    # ?典?銝脤?蔥嚗??pandas ?其??像?啁??int/int64 factorize mismatch
                    df_quarterly['yq_key'] = df_quarterly['撟游漲'].astype(int).astype(str) + 'Q' + df_quarterly['摮?漲'].astype(int).astype(str)
                    qsum['yq_key'] = qsum['撟游漲'].astype(int).astype(str) + 'Q' + qsum['摮?漲'].astype(int).astype(str)
                    df_quarterly = df_quarterly.merge(qsum[['yq_key', '?']].rename(columns={'?': '?_??蝮?}), on='yq_key', how='left')
                    df_quarterly['?'] = pd.to_numeric(df_quarterly['?_??蝮?], errors='coerce').fillna(pd.to_numeric(df_quarterly['?'], errors='coerce'))
                    df_quarterly = df_quarterly.drop(columns=['?_??蝮?])
                else:
                    pass  # ???嗅?蝮賢仃??蝜潛??刻瓷?勗?憪?

            # ?身???迂
            df_quarterly['瘥??蝔?] = '瘥??
            # ===== 5) 瘥???芸??冽??抬?瘝?撠梁(?-?) =====
            # ???∴?銝?蝞??拍?嚗?函?敺???(%) ?誨嚗蝞??箏??征
            if is_finance:
                net_col = None
                for col in df_pivot.columns:
                    c = str(col)
                    if any(k in c for k in ['?祆?蝔?瘛典', '蝔?瘛典', '瘛典嚗楊??', '蝜潛??平?桐??祆?瘛典']) or re.search(r"income\s*after\s*tax|net\s*income", c, re.I):
                        net_col = col
                        break
                if net_col is not None:
                    net_income = pd.to_numeric(df_pivot[net_col], errors='coerce')
                    df_quarterly['瘥??] = (net_income / pd.to_numeric(df_quarterly['?'], errors='coerce') * 100).round(2)
                    df_quarterly['瘥??蝔?] = '蝔?蝝???
                else:
                    df_quarterly['瘥??] = float('nan')
                    df_quarterly['瘥??蝔?] = '蝔?蝝???

            # 銝?砍?賂??扯?閮?瘥?????∪歇?其???if is_finance ?憛???甇方??仿?嚗?
            if not is_finance:
                # ?芸?嚗?交??拍?(%)甈?嚗?????湔蝯衣??嚗?
                _gm_pct_col = next((col for col in df_pivot.columns if '瘥?? in str(col)), None)
                if _gm_pct_col is not None:
                    _gm_vals = pd.to_numeric(df_pivot[_gm_pct_col], errors='coerce')
                    if _gm_vals.notna().any():
                        df_quarterly['瘥??] = _gm_vals.values
                        print(f'[瘥? ?湔甈? {_gm_pct_col}: ??)
                    else:
                        _gm_pct_col = None  # 甈??沐aN嚗匱蝥銝??蝞?

                if _gm_pct_col is None:
                    gp_col = None
                    for col in df_pivot.columns:
                        c = str(col)
                        if any(k in c for k in ['瘥', '?平瘥']) or re.search(r"gross\s*profit", c, re.I):
                            gp_col = col
                            break

                    if gp_col is not None:
                        gp = pd.to_numeric(df_pivot[gp_col], errors='coerce')
                        df_quarterly['瘥??] = (gp / df_quarterly['?'] * 100).round(2)
                    else:
                        cost_col = None
                        for col in df_pivot.columns:
                            c = str(col)
                            if any(k in c for k in ['?平?', '???']) or re.search(r"cost\s+of\s+revenue|cost\s+of\s+goods", c, re.I):
                                cost_col = col
                                break

                        if cost_col is not None:
                            cost = pd.to_numeric(df_pivot[cost_col], errors='coerce')
                            df_quarterly['瘥??] = ((df_quarterly['?'] - cost) / df_quarterly['?'] * 100).round(2)
                        else:
                            df_quarterly['瘥??] = float('nan')
                            print(f"?? ?⊥??曉瘥/?甈?嚗?冽?雿? {[str(c) for c in df_pivot.columns[:15]]}")
                            # ?? Fix C: 鋆? yfinance 瘥????????????????????????
                            try:
                                import yfinance as _yf_gps
                                for _sfx_g in ('.TW', '.TWO'):
                                    _tk_g = _yf_gps.Ticker(f'{stock_id}{_sfx_g}')
                                    _qi_g = (getattr(_tk_g, 'quarterly_income_stmt', None)
                                             or getattr(_tk_g, 'quarterly_financials', None))
                                    if _qi_g is not None and not _qi_g.empty:
                                        _gp_r = next((i for i in _qi_g.index if 'Gross Profit' in str(i)), None)
                                        _rv_r = next((i for i in _qi_g.index if 'Total Revenue' in str(i) or str(i)=='Revenue'), None)
                                        if _gp_r and _rv_r:
                                            for _qc in _qi_g.columns:
                                                _qts = f"{_qc.year}Q{((_qc.month-1)//3)+1}"
                                                _mk = df_quarterly['摮?漲璅惜'] == _qts
                                                if _mk.any():
                                                    _gv = float(_qi_g.loc[_gp_r, _qc])
                                                    _rv = float(_qi_g.loc[_rv_r, _qc])
                                                    if _rv > 0 and not pd.isna(_gv):
                                                        df_quarterly.loc[_mk, '瘥??] = round(_gv / _rv * 100, 2)
                                            _non_nan = df_quarterly['瘥??].notna().sum()
                                            print(f'[瘥? yfinance鋆? {stock_id}{_sfx_g}: ?aN={_non_nan}')
                                            if _non_nan > 0:
                                                break
                            except Exception as _egp:
                                print(f'[瘥? yfinance鋆?憭望?: {_egp}')

            # ===== 5b) EPS嚗??∠?擗?=====
            eps_col = None
            for col in df_pivot.columns:
                c = str(col)
                if any(k in c for k in ['瘥??', '?箸瘥', 'EPS']) or re.search(r"basic\s*eps|earnings\s*per\s*share", c, re.I):
                    eps_col = col
                    break
            if eps_col is not None:
                df_quarterly['EPS'] = pd.to_numeric(df_pivot[eps_col], errors='coerce')
            else:
                df_quarterly['EPS'] = float('nan')

            # ===== 5d) 瘥???湛?yfinance quarterly_income_stmt嚗??蝔梁摰對? =====
            if not is_finance and df_quarterly['瘥??].isna().all():
                try:
                    import yfinance as _yf_gp
                    for _yf_sfx in ('.TW', '.TWO'):
                        _tk_gp = _yf_gp.Ticker(f"{stock_id}{_yf_sfx}")
                        # yfinance ??.2.36: quarterly_income_stmt; ????quarterly_financials
                        _qfin = (getattr(_tk_gp, 'quarterly_income_stmt', None)
                                 or getattr(_tk_gp, 'quarterly_financials', None))
                        if _qfin is not None and not _qfin.empty:
                            break
                    if _qfin is not None and not _qfin.empty:
                        # ??GrossProfit ??Revenue嚗?蝔格?雿??詨捆嚗?
                        _gp_row = next((r for r in _qfin.index if 'Gross' in str(r) and 'Profit' in str(r)), None)
                        if _gp_row is None:
                            _gp_row = next((r for r in _qfin.index if 'GrossProfit' in str(r).replace(' ', '')), None)
                        _rv_row = next((r for r in _qfin.index if 'Total' in str(r) and 'Revenue' in str(r)), None)
                        if _rv_row is None:   # ?嚗peratingRevenue / 隞餅? Revenue
                            _rv_row = next((r for r in _qfin.index if 'Revenue' in str(r)), None)
                        print(f'[yfinance 瘥? {stock_id}: gp={_gp_row}, rv={_rv_row}, cols={list(_qfin.index)[:6]}')
                        if _gp_row and _rv_row:
                            _yf_updated = 0
                            for _col in _qfin.columns:
                                try:
                                    _ts = pd.Timestamp(_col)
                                    _yr_q = _ts.year; _mo_q = _ts.month
                                    _q_q  = ((_mo_q - 1) // 3) + 1
                                    _lbl  = f"{_yr_q}Q{_q_q}"
                                    _mk   = df_quarterly.index[df_quarterly['摮?漲璅惜'] == _lbl]
                                    if len(_mk) and pd.isna(df_quarterly.loc[_mk[0], '瘥??]):
                                        _gp_v = float(_qfin.loc[_gp_row, _col])
                                        _rv_v = float(_qfin.loc[_rv_row, _col])
                                        if (not pd.isna(_gp_v) and not pd.isna(_rv_v)
                                                and abs(_rv_v) > 0):
                                            df_quarterly.loc[_mk[0], '瘥??] = round(_gp_v / _rv_v * 100, 2)
                                            _yf_updated += 1
                                except Exception: pass
                            if _yf_updated > 0:
                                print(f'[yfinance 瘥? {stock_id}: ??{_yf_updated} 摮?)
                except Exception as _e_yf_gp:
                    print(f'[yfinance 瘥? {stock_id}: {_e_yf_gp}')

            # ===== 5e) 銝?嚗?璆剖?? + 瘛典??敺?銝隞?income statement pivot ??嚗?====
            if not is_finance:
                # ?平?拍? (Operating Income)
                _oi_col = None
                for col in df_pivot.columns:
                    c = str(col)
                    if any(k in c for k in ['?平?拍?', '璆剖??拍?', '?平??']) or \
                       re.search(r"operating.*(income|profit|loss)", c, re.I):
                        _oi_col = col; break
                if _oi_col is not None:
                    _oi = pd.to_numeric(df_pivot[_oi_col], errors='coerce')
                    _rev_denom = pd.to_numeric(df_quarterly['?'], errors='coerce').replace(0, float('nan'))
                    df_quarterly['?平?拍???] = (_oi.values / _rev_denom.values * 100).round(2)
                    print(f'[銝?] {stock_id}: ?平?拍???{_oi_col}')
                else:
                    df_quarterly['?平?拍???] = float('nan')

                # 蝔?蝝? / ?祆?瘛典 (Net Income)
                _ni_col = None
                for col in df_pivot.columns:
                    c = str(col)
                    if any(k in c for k in ['蝔?蝝?', '?祆?瘛典', '?祆???', '蝔?瘛典',
                                             '瘛典嚗楊??', '瘛冽???, '蝜潛??平?桐??祆?瘛典']) or \
                       re.search(r"net.*(income|profit|loss)|profit.*after.*tax", c, re.I):
                        _ni_col = col; break
                if _ni_col is not None:
                    _ni = pd.to_numeric(df_pivot[_ni_col], errors='coerce')
                    _rev_denom = pd.to_numeric(df_quarterly['?'], errors='coerce').replace(0, float('nan'))
                    df_quarterly['瘛典??] = (_ni.values / _rev_denom.values * 100).round(2)
                    print(f'[銝?] {stock_id}: 瘛典??{_ni_col}')
                else:
                    df_quarterly['瘛典??] = float('nan')
            else:
                # ???∴?銝?蝞???瘥??蝔勗歇?寧蝔?蝝???
                df_quarterly['?平?拍???] = float('nan')
                df_quarterly['瘛典??]     = float('nan')

            # ===== 6) 皜???摨?=====
            df_quarterly = df_quarterly.dropna(subset=['?']).copy()
            # ?????∴??迂鞎?嚗?鞈?憭梁?嚗?銝?砍?賂??蕪鞎
            if not is_finance:
                df_quarterly = df_quarterly[df_quarterly['?'] > 0].copy()
            df_quarterly = df_quarterly.drop_duplicates(subset=['摮?漲璅惜'], keep='last')
            df_quarterly = df_quarterly.sort_values(['撟游漲', '摮?漲']).tail(12).reset_index(drop=True)

            if df_quarterly.empty:
                return None, "?亦??摮?漲鞈?嚗?質府?砍/鞈?皞??餈僑摮?嚗?

            # ?? ?摮?璅? date 甈?嚗?鞈?閮箸?銵冽霈????????????????
            _QTR_END = {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}
            df_quarterly['date'] = (
                df_quarterly['撟游漲'].astype(int).astype(str) + '-'
                + df_quarterly['摮?漲'].astype(int).map(_QTR_END)
            )

            print(f"????頛 {len(df_quarterly)} 蝑迤摨西???)
            df_quarterly['?臬????] = is_finance

            # ???日嚗炎?交?行?鞎?
            if (df_quarterly['?'] < 0).any():
                print(f"?? ?潛鞎?嚗??={is_finance}嚗?")
                neg_data = df_quarterly[df_quarterly['?'] < 0][['摮?漲璅惜', '?']]
                print(neg_data.to_string(index=False))

            _stamp_finreport_attrs(df_quarterly, 'qtr', _qtr_src)   # v18.202 E2
            return df_quarterly, None

        except Exception as e:
            import traceback
            traceback.print_exc()
            return None, f"頛?航炊: {str(e)}"

    def get_quarterly_bs_cf(_self, stock_id):
        """
        ??餈?12 摮?????Ｚ??菔” + ?暸?瘚???摨????冽??閮???
        ?甈?嚗迤摨行?蝐? ??鞎, 摮疏, 鞈?臬嚗??箏?憪?憿??桐?嚗?????
        鞈?靘?嚗inMind TaiwanStockBalanceSheet + TaiwanStockCashFlowsStatement
        """
        try:
            import os as _os_bscf, datetime as _dt_bscf
            _qtr_extra_src = 'unknown'   # v18.202 E2嚗迤鞎∪-extra 鞈?皞?finmind / finmind_mops / missing嚗?
            _tok = _os_bscf.environ.get('FINMIND_TOKEN', '')
            _start = (_dt_bscf.date.today() - _dt_bscf.timedelta(days=365 * 3)).strftime('%Y-%m-%d')
            _hdrs = {'Authorization': f'Bearer {_tok}'} if _tok else {}

            def _fm_fetch(dataset):
                _p = {'dataset': dataset, 'data_id': stock_id, 'start_date': _start}
                if _tok: _p['token'] = _tok
                _r = _bps_dl().get('https://api.finmindtrade.com/api/v4/data',
                                    params=_p, headers=_hdrs, timeout=20)
                _j = _r.json()
                print(f'[BS/CF] {stock_id} {dataset}: status={_j.get("status")} rows={len(_j.get("data",[]))}')
                return _j.get('data', []) if _j.get('status') == 200 else []

            # ?? Balance Sheet ????????????????????????????????????????
            _bs_rows = _fm_fetch('TaiwanStockBalanceSheet')
            _bs_map = {}   # {date ??{type ??value}}
            for _row in _bs_rows:
                _d = _row.get('date', '')
                _bs_map.setdefault(_d, {})[_row.get('type', '')] = _row
                _bs_map[_d][_row.get('origin_name', '')] = _row

            # ?? Cash Flow ????????????????????????????????????????????
            _cf_rows = _fm_fetch('TaiwanStockCashFlowsStatement')
            _cf_map = {}   # {date ??{type ??value}}
            for _row in _cf_rows:
                _d = _row.get('date', '')
                _cf_map.setdefault(_d, {})[_row.get('type', '')] = _row
                _cf_map[_d][_row.get('origin_name', '')] = _row

            if not _bs_rows and not _cf_rows:
                return None, f"{stock_id} BS+CF嚗inMind ?∟???
            _qtr_extra_src = 'finmind'   # v18.202 E2嚗S/CF 銝餅??賭葉

            # ?? 敶???曄?摮?漲?交? ??????????????????????????????
            _all_dates = sorted(set(list(_bs_map.keys()) + list(_cf_map.keys())))

            def _val(d_map, d, keys):
                """敺?d_map[d] 鋆⊥??芸????洵銝???嗅?""
                slot = d_map.get(d, {})
                for k in keys:
                    r = slot.get(k)
                    if r is not None:
                        try:
                            v = float(str(r.get('value', 0)).replace(',', '') or 0)
                            if v != 0: return abs(v)
                        except: pass
                return float('nan')

            _CL_KEYS = ['CurrentContractLiabilities', 'NonCurrentContractLiabilities',
                        'ContractLiabilities', 'ContractLiabilitiesCurrent',
                        'ContractLiabilitiesNonCurrent',
                        '??鞎', '??鞎-瘚?', '??鞎嚗???,
                        '??鞎-????, '??鞎嚗?瘚?',
                        '憟?鞎', '?甈暸?']
            _INV_KEYS = ['Inventories', 'InventoriesNet', 'Inventories_Net',
                         '摮疏', '摮疏瘛券?', '??摮疏']
            _CX_KEYS  = ['AcquisitionOfPropertyPlantAndEquipment',
                         'PropertyAndPlantAndEquipment',
                         '??銝??Ｕ??踹?閮剖?', '鞈潛蔭銝??Ｕ??踹?閮剖?', '鞈?臬']
            # ??PP&E?暸?瘚嚗皜祈都撱??之鞈??嚗?
            _DISP_KEYS = ['ProceedsFromDisposalOfPropertyPlantAndEquipment',
                          'SaleOfPropertyPlantAndEquipment',
                          'DisposalOfPropertyPlantAndEquipment',
                          '??銝??Ｕ??踹?閮剖?銋????,
                          '?箏銝??Ｕ??踹?閮剖??嗅',
                          '???箏?鞈?嗅']

            # 撱箇? DataFrame 靘?蝝??菜芋蝟?撠?str.contains ??舫?嚗?
            _bs_df_raw = pd.DataFrame(_bs_rows) if _bs_rows else pd.DataFrame()
            _has_bs_df = (not _bs_df_raw.empty and
                          'type' in _bs_df_raw.columns and
                          'date' in _bs_df_raw.columns and
                          'value' in _bs_df_raw.columns)
            if _has_bs_df:
                _bs_df_raw = _bs_df_raw.sort_values('date', ascending=False)

            _records = []
            for _d in _all_dates:
                try:
                    _ts = pd.Timestamp(_d)
                    _yr = _ts.year; _qt = ((_ts.month - 1) // 3) + 1
                    _lbl = f'{_yr}Q{_qt}'
                except: continue

                # ?? ??鞎嚗ataFrame str.contains嚗??舫?嚗項????dash 霈?嚗??
                _cl = float('nan')
                if _has_bs_df:
                    _cl_rows = _bs_df_raw[(_bs_df_raw['date'] == _d) &
                                          _bs_df_raw['type'].str.contains('??鞎', na=False)]
                    if len(_cl_rows) > 0:
                        _cl_vals = pd.to_numeric(
                            _cl_rows['value'].astype(str).str.replace(',', '', regex=False),
                            errors='coerce').abs()
                        _cl_vals = _cl_vals[_cl_vals > 0]
                        if len(_cl_vals) > 0:
                            _cl = float(_cl_vals.sum())
                            print(f'[BS/CF] {stock_id} {_d} CL={_cl:.0f} ({len(_cl_rows)} rows via contains)')
                # ?嚗移蝣?key ?交 + dict fuzzy
                if isinstance(_cl, float) and _cl != _cl:  # isnan
                    _cl = _val(_bs_map, _d, _CL_KEYS)
                    if isinstance(_cl, float) and _cl != _cl:
                        _slot = _bs_map.get(_d, {})
                        _parts = [abs(float(str(_v.get('value', 0)).replace(',', '') or 0))
                                  for _k, _v in _slot.items()
                                  if '??鞎' in str(_k) and isinstance(_v, dict)]
                        _parts = [p for p in _parts if p > 0]
                        if _parts: _cl = sum(_parts)

                _inv  = _val(_bs_map, _d, _INV_KEYS)
                _cx   = _val(_cf_map, _d, _CX_KEYS)
                _disp = _val(_cf_map, _d, _DISP_KEYS)
                _records.append({'摮?漲璅惜': _lbl, '??鞎': _cl, '摮疏': _inv,
                                  '鞈?臬': _cx, '??鞈?暸?瘚': _disp})

            if not _records:
                return None, f"{stock_id} BS+CF嚗?圾?仃??

            df_extra = pd.DataFrame(_records)
            df_extra = df_extra.drop_duplicates(subset=['摮?漲璅惜'], keep='last')
            df_extra = df_extra.sort_values('摮?漲璅惜').tail(12).reset_index(drop=True)
            # ?? ?摮?璅? date 甈?嚗?鞈?閮箸?銵冽霈????????????????
            _QME = {1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31'}
            def _qe2date(lbl):
                try: return f'{lbl[:4]}-{_QME[int(lbl[5])]}'
                except: return None
            df_extra['date'] = df_extra['摮?漲璅惜'].apply(_qe2date)

            # ?? MOPS ?嚗inMind ???啣?蝝??菜?嚗???敺?1 摮???????????
            # 靘?嚗ops.twse.com.tw/mops/web/ajax_t164sb03 (?蔥鞈鞎銵?
            # 閫貊璇辣嚗?敺?1 摮?_cl ??NaN嚗??N?4 ?Ｙ?嚗?
            try:
                _last_cl_nan = (len(df_extra) > 0 and
                                pd.isna(df_extra['??鞎'].iloc[-1]))
                if _last_cl_nan:
                    from tw_stock_data_fetcher import (fetch_mops_financials as _fmf,
                                                       build_proxy_session as _bps_mops)
                    _last_lbl = df_extra['摮?漲璅惜'].iloc[-1]
                    _yr_m = int(_last_lbl[:4]); _q_m = int(_last_lbl[5])
                    _sess_m = _bps_mops()
                    _mops_df = _fmf(stock_id, _yr_m, _q_m, _sess_m)
                    _cl_mops = float('nan')
                    if _mops_df is not None and not _mops_df.empty:
                        # MOPS 銵冽?虜??[???, ??] ?拇? flat ?澆?
                        _flat = _mops_df.astype(str)
                        _mask = _flat.apply(
                            lambda row: row.str.contains('??鞎', na=False).any(),
                            axis=1)
                        _hit = _flat[_mask]
                        _vals = []
                        for _, _r_m in _hit.iterrows():
                            for _cell in _r_m.tolist():
                                _cs = str(_cell).replace(',', '').strip()
                                try:
                                    _vv = float(_cs)
                                    if _vv > 0:
                                        _vals.append(_vv)
                                except Exception:
                                    pass
                        if _vals:
                            _cl_mops = float(sum(_vals))
                    if _cl_mops == _cl_mops and _cl_mops > 0:
                        df_extra.loc[df_extra.index[-1], '??鞎'] = _cl_mops
                        _qtr_extra_src = 'finmind_mops'   # v18.202 E2嚗OPS 鋆?蝝???
                        print(f'[BS/CF/MOPS] {stock_id} {_last_lbl}: ??CL={_cl_mops:.0f} (??賭葉)')
                    else:
                        print(f'[BS/CF/MOPS] {stock_id} {_last_lbl}: ?? MOPS 鈭衣??鞎蝘嚗?賣迨?∠甇日?嚗?)
            except Exception as _e_mops:
                print(f'[BS/CF/MOPS] ?? {type(_e_mops).__name__}: {_e_mops}')

            print(f'[BS/CF] {stock_id}: ??{len(df_extra)} 摮?CL={df_extra["??鞎"].notna().sum()} INV={df_extra["摮疏"].notna().sum()} CX={df_extra["鞈?臬"].notna().sum()} DISP={df_extra["??鞈?暸?瘚"].notna().sum()}')
            _stamp_finreport_attrs(df_extra, 'qtr_extra', _qtr_extra_src)   # v18.202 E2
            return df_extra, None

        except Exception as _e_bscf:
            import traceback; traceback.print_exc()
            return None, f"BS+CF 頛?航炊: {_e_bscf}"


# ?? 璅∠?蝝撘?MJ 鞎∪擃炎?????豢? ?????????????????????
@st.cache_data(ttl=CACHE_TTL["price_data"], show_spinner=False)
def fetch_financial_statements(stock_id: str, token: str = "") -> dict:
    """
    敺?FinMind ????唬?摮???Ｚ??菔”????”???”嚗?
    閮? MJ 擃頂??????
    ? dict嚗仃??? {"error": "..."}??
    """
    import os as _os_ffs, requests as _rq_ffs, datetime as _dt_ffs

    _tok = token or _os_ffs.environ.get("FINMIND_TOKEN", "")
    _start = (_dt_ffs.date.today() - _dt_ffs.timedelta(days=730)).strftime("%Y-%m-%d")
    _hdrs = {"Authorization": f"Bearer {_tok}"} if _tok else {}

    def _fm(dataset):
        _p = {"dataset": dataset, "data_id": stock_id, "start_date": _start}
        if _tok:
            _p["token"] = _tok
        try:
            _r = _rq_ffs.get(
                "https://api.finmindtrade.com/api/v4/data",
                params=_p, headers=_hdrs, timeout=20,
            )
            _j = _r.json()
            _st = _j.get("status")
            if _st != 200:
                print(f"[fetch_fin/{dataset}] ??00??: status={_st} msg={_j.get('msg','')}")
            return _j.get("data", []) if _st == 200 else [], _st
        except Exception as _e:
            print(f"[fetch_fin/{dataset}] {_e}")
            return [], None

    # 3 ??dataset 敶潭迨?函? ??銝西???_fm 蝝蝡?requests??曹澈?航????蝺?摰嚗?
    # map 靽?嚗?銝閫??????_ds_ffs 銝?湛?蝮質?瘙銝?嚗inMind ???箸?撠??塚???
    from concurrent.futures import ThreadPoolExecutor as _TPE_ffs
    _ds_ffs = ("TaiwanStockBalanceSheet", "TaiwanStockCashFlowsStatement",
               "TaiwanStockFinancialStatements")
    with _TPE_ffs(max_workers=3) as _ex_ffs:
        _fm_res = list(_ex_ffs.map(_fm, _ds_ffs))
    (_bs_rows, _bs_st), (_cf_rows, _cf_st), (_is_rows, _is_st) = _fm_res

    if not _bs_rows and not _cf_rows:
        # ???Token ?? vs ?∠巨?祈澈?∟???
        _statuses = [s for s in [_bs_st, _cf_st] if s is not None]
        if not _tok:
            _err = f"{stock_id}嚗閮剖? FINMIND_TOKEN嚗瘜閰Ｚ瓷??
        elif any(s in (401, 403) for s in _statuses):
            _err = f"{stock_id}嚗INMIND_TOKEN ?⊥??歇??嚗TTP {_statuses[0]}嚗?
        else:
            _err = (f"{stock_id}嚗inMind ?⊥迨?∠巨鞎∪鞈?"
                    f"嚗?賜?唳??銝??? FinMind 鞈?皞??芣??")
        return {"error": _err}

    def _build(rows):
        """?? (date,key) 憭??潸?蝒???憭抒?撠潦?
        FinMind 撠?鈭蟡剁?靘? 6770嚗??憭? type=Revenue 雿?origin_name 銝?
        嚗?閮? + 摮??株?嚗??亦 last-wins 摮??格?閬???嚗???rev 鋡思?隡啜?
        om/nm ?箇 >100% ??雓祆????max(|val|) 隞乩?霅?閮?澆?蝘??""
        m: dict = {}
        for r in rows:
            d = r.get("date", "")
            try:
                v = float(str(r.get("value", 0) or 0).replace(",", ""))
            except Exception:
                v = 0.0
            slot = m.setdefault(d, {})
            for _key in (r.get("type", ""), r.get("origin_name", "")):
                if not _key:
                    continue
                _prev = slot.get(_key)
                if _prev is None or abs(v) > abs(float(_prev) if _prev else 0):
                    slot[_key] = v
        return m

    _bs = _build(_bs_rows)
    _cf = _build(_cf_rows)
    _is = _build(_is_rows)

    _dates = sorted(set(list(_bs.keys()) + list(_cf.keys())))
    if not _dates:
        return {"error": f"{stock_id}嚗瓷?望?圾?仃??}

    _lat = _dates[-1]
    _prv = _dates[-2] if len(_dates) >= 2 else _lat

    def _v(m, d, keys):
        slot = m.get(d, {})
        for k in keys:
            v = slot.get(k)
            if v is not None:
                try:
                    fv = float(str(v).replace(",", "") or 0)
                    if fv != 0:
                        return fv
                except Exception:
                    pass
        return 0.0

    def _vsum(m, d, keys):
        """?蜇 keys 銝剜????嗆?雿??冽?蟡冽?+撣單狡????內?銵剁?"""
        slot = m.get(d, {})
        total = 0.0
        for k in keys:
            v = slot.get(k)
            if v is not None:
                try:
                    fv = float(str(v).replace(",", "") or 0)
                    if fv > 0:
                        total += fv
                except Exception:
                    pass
        return total

    cash   = _v(_bs, _lat, ["CashAndCashEquivalents", "?暸????嗥??, "Cash",
                              "?暸???銵?甈?, "摨怠??暸????嗥??])
    assets = _v(_bs, _lat, ["TotalAssets", "鞈蝮質?", "鞈??", "鞈蝮賡?",
                              "鞈蝮質?嚗???", "Assets"])
    liab   = _v(_bs, _lat, ["TotalLiabilities", "鞎蝮質?", "鞎??", "鞎蝮賡?",
                             "Liabilities", "鞎??嚗???", "鞎蝮賡?嚗???",
                             "鞎蝮質?嚗???"])
    cur_assets = _v(_bs, _lat, ["CurrentAssets", "瘚?鞈??", "瘚?鞈蝮質?",
                                  "瘚?鞈", "瘚?鞈蝮賡?"])
    cur_liab = _v(_bs, _lat, ["CurrentLiabilities", "瘚?鞎??", "瘚?鞎蝮質?",
                                "瘚?鞎", "瘚?鞎蝮賡?"])
    # FinMind 銝?摰?靘??萄?閮?蝮質?嚗?亦 瘚?+?????詨?
    _non_cur_liab = _v(_bs, _lat, ["NoncurrentLiabilities", "?????萄?閮?,
                                    "?????萇蜇閮?, "??????])
    if liab == 0 and (cur_liab > 0 or _non_cur_liab > 0):
        liab = cur_liab + _non_cur_liab
        print(f"[fetch_fin] {stock_id} 鞎???亦嚗??瘚?({cur_liab:.0f})+????{_non_cur_liab:.0f})={liab:.0f}??)
    # FinMind 銝?摰?靘??Ｗ?閮?蝮質?嚗?亦 瘚?+?????詨?
    _non_cur_assets = _v(_bs, _lat, ["NoncurrentAssets", "?????Ｗ?閮?,
                                      "?????Ｙ蜇閮?, "??????])
    if assets == 0 and (cur_assets > 0 or _non_cur_assets > 0):
        assets = cur_assets + _non_cur_assets
        print(f"[fetch_fin] {stock_id} 鞈???亦嚗??瘚?({cur_assets:.0f})+????{_non_cur_assets:.0f})={assets:.0f}??)
    # AR嚗1 ??蝮賢???蝷箇?蟡冽?+撣單狡+??鈭綽??踹???閮???嚗?
    # 瘨菔?嚗??澆?嚗楊憿???鈭綽?+ IFRS ?祈??澆?嚗???鈭綽?/嚗?靽犖嚗? ?怎??澆?
    # + em-dash嚗?嚗?敶ａ????-嚗郭??嚗?銝車霈? + ?典耦?祈?嚗?+ ?耦?祈?()
    ar = _vsum(_bs, _lat, [
        "?蟡冽?瘛券?", "?撣單狡瘛券?", "?撣單狡嚗?靽犖瘛券?", "?甈暸?",
        "?撣單狡嚗???鈭綽?", "?撣單狡嚗?靽犖嚗?,
        "?撣單狡嚗???鈭綽?瘛券?", "?撣單狡嚗?靽犖嚗楊憿?,
        "?撣單狡嚗???鈭箸楊憿?,          # em-dash ??靽犖瘛券?
        "?蟡冽?嚗???鈭綽?", "?蟡冽?嚗?靽犖嚗?,
        "?撣單狡-??靽犖", "?撣單狡-??鈭?,
        "?撣單狡????鈭?, "?撣單狡??靽犖",          # ?典耦?湔???
        "?撣單狡 - ??靽犖", "?撣單狡 - ??鈭?,      # 撣嗥征??
        "?蟡冽?嚗???鈭箸楊憿?, "?蟡冽?嚗?靽犖瘛券?",  # 蟡冽? em-dash
        "?撣單狡-??靽犖瘛券?", "?撣單狡-??鈭箸楊憿?,   # ?耦 + 瘛券?
        "?撣單狡(??靽犖)", "?撣單狡(??鈭?",         # ?耦?祈?
    ])
    # L2 ??L1 = 0嚗??雿萄?蝷箇???銵?銝? L1 瘛瑕?嚗??銴?蝞?
    if ar == 0:
        ar = _vsum(_bs, _lat, ["?撣單狡?巨??, "?撣單狡?巨?楊憿?,
                                "?蟡冽??董甈暹楊憿?,                    # ?啣?
                                "?蟡冽????嗅董甈?, "?撣單狡",
                                "?撣單狡嚗蝔?", "?撣單狡瘛券?嚗蝔?"])
    if ar == 0:
        ar = _v(_bs, _lat, ["AccountsReceivable", "?撣單狡瘛券?", "?撣單狡",
                             "NoteAndAccountsReceivable", "?撣單狡?巨???嗆狡",
                             "?蟡冽??董甈?, "?撣單狡嚗楊憿?", "鞎踵??甈曉??嗡??甈?,
                             "鞎踵??隞??嗆狡",                          # ?啣?嚗?鞈??隡?
                             "?撣單狡嚗楊憿?, "鞎踵??甈?,
                             "?甈暸?", "?甈暸???", "?撣單狡?隞??嗆狡",
                             "ReceivablesNet", "NetReceivables",
                             "??鞈", "撌亦??甈?, "?撣單狡??蝝???,
                             "?蟡冽????嗅董甈?,
                             "?撣單狡嚗???鈭綽?", "?撣單狡嚗?靽犖嚗?])
    ap     = _v(_bs, _lat, ["AccountsPayable", "??撣單狡",
                             "NoteAndAccountsPayable", "??撣單狡?巨??隞狡",
                             "??蟡冽??董甈?, "鞎踵???甈?])
    inv    = _v(_bs, _lat, ["Inventories", "摮疏", "摮疏瘛券?"])
    inv_p  = _v(_bs, _prv, ["Inventories", "摮疏", "摮疏瘛券?"])
    ppe    = _v(_bs, _lat, ["PropertyPlantAndEquipmentNet", "銝??Ｕ??踹?閮剖?瘛券?",
                             "?箏?鞈瘛券?", "銝??Ｗ??踹?閮剖?",
                             "PropertyPlantAndEquipment", "銝??Ｗ??踹?閮剖?瘛券?",
                             "銝??Ｕ??踹?閮剖?"])
    lt_inv = _v(_bs, _lat, ["LongTermInvestments", "?瑟???", "?⊥???銋?鞈?])
    # ?? v10.57.0 ?啣?嚗J 擃炎鋆???嚗?瘥? / ?暸???鞈???/ EPS嚗??
    prepaid = _v(_bs, _lat, ["Prepayments", "??甈暸?", "??鞎餌", "??鞎冽狡",
                              "????甈?, "?嗡???甈暸?"])
    other_nca = _v(_bs, _lat, ["OtherNoncurrentAssets", "?嗡???????,
                                "?嗡??????Ｗ?閮?])
    # ?箸 EPS嚗S嚗?
    eps_v = _v(_is, _lat, ["BasicEarningsPerShare", "?箸瘥??", "瘥??",
                            "EPS", "Earnings Per Share", "蝔???∠?擗?])

    ocf    = _v(_cf, _lat, ["CashFlowsFromOperatingActivities",
                             "?平瘣餃?銋楊?暸?瘚嚗??綽?", "靘?平瘣餃?銋????])
    icf    = _v(_cf, _lat, ["CashFlowsFromInvestingActivities",
                             "??瘣餃?銋楊?暸?瘚嚗??綽?", "靘??瘣餃?銋????])
    fncf   = _v(_cf, _lat, ["CashFlowsFromFinancingActivities",
                             "蝐?瘣餃?銋楊?暸?瘚嚗??綽?", "靘蝐?瘣餃?銋????])
    capex  = abs(_v(_cf, _lat, ["AcquisitionOfPropertyPlantAndEquipment",
                                 "??銝??Ｕ??踹?閮剖?", "鞈潛蔭銝??Ｕ??踹?閮剖?", "鞈?臬"]))
    div_paid = abs(_v(_cf, _lat, ["CashDividendsPaid", "?潭?暸??∪", "?暸??∪"]))

    rev    = _v(_is, _lat, ["Revenue", "?平?嗅??", "?平?嗅", "NetRevenue",
                              "OperatingRevenue", "?平蝮賣??, "?平瘛冽??,
                              "?瑁疏?嗅瘛券?", "?瑁疏?嗅"])
    cogs   = abs(_v(_is, _lat, ["CostOfGoodsSold", "?平?", "?瑕?",
                                 "OperatingCosts", "?平蝮賣???]))
    oper_income = _v(_is, _lat, ["OperatingIncome", "?平?拍?嚗?憭梧?", "?平?拍?",
                                  "Operating Income", "OperatingProfit",
                                  "?平瘛典", "?平??"])
    net_ni = _v(_is, _lat, ["NetIncome", "?祆?瘛典嚗楊??", "瘛典", "蝔?瘛典",
                              "ProfitLoss", "?祆?蝬???蝮賡?",
                              "甇詨惇?潭??砍璆凋蜓銋楊?抬?瘛冽?嚗?])
    # ?? Sanity: oi/ni 銝?憭扳 rev ? 1.2嚗雿鈭?摮??株炊????????
    if rev > 0:
        if abs(oper_income) > rev * 1.2:
            print(f"[fetch_fin] {stock_id} ?? oper_income={oper_income:.0f} > rev={rev:.0f}?1.2嚗?隡潸炊??蝘嚗?蝵桃 0")
            oper_income = 0
        if abs(net_ni) > rev * 1.2:
            print(f"[fetch_fin] {stock_id} ?? net_ni={net_ni:.0f} > rev={rev:.0f}?1.2嚗?隡潸炊??蝘嚗?蝵桃 0")
            net_ni = 0

    rev_p  = _v(_is, _prv, ["Revenue", "?平?嗅??", "?平?嗅"])
    ar_p   = _v(_bs, _prv, [
        "AccountsReceivable", "?撣單狡瘛券?", "?撣單狡",
        "?撣單狡嚗???鈭綽?", "?撣單狡嚗?靽犖嚗?,
        "?撣單狡嚗???鈭綽?瘛券?", "?撣單狡?巨??, "?蟡冽????嗅董甈?,
        "?撣單狡嚗蝔?",
    ])
    equity = _v(_bs, _lat, ["TotalEquity", "甈?蝮賡?", "?⊥甈???",
                             "TotalStockholdersEquity", "?⊥甈?蝮賡?",
                             "EquityAttributableToOwnersOfParent",
                             "甇詨惇?潭??砍璆凋蜓銋???閮?,
                             "甈???"])
    # ??⊿?嚗quity < 0.1% of assets ???航?摮??株???嚗??assets?iab ??
    if 0 < equity < assets * 0.001 and liab > 0:
        recalc = max(assets - liab, 0)
        print(f"[fetch_fin] {stock_id} equity={equity:.0f}???撮甈?隤日?嚗equity/assets:.6%}嚗??寧 assets-liab={recalc:.0f}??)
        equity = recalc
    # Fallback: Assets = Liabilities + Equity嚗FRS ??撘?????嚗?
    if liab == 0 and assets > 0 and equity > 0:
        liab = max(assets - equity, 0)
        print(f"[fetch_fin] {stock_id} 鞎甈??亦鞈?嚗??鞈-甈? 閮?: {round(liab/1e3)}??)
    if assets == 0 and equity > 0 and liab > 0:
        assets = equity + liab
        print(f"[fetch_fin] {stock_id} 鞈甈??亦鞈?嚗??甈?+鞎 閮?: {round(assets/1e3)}??)

    # 璅∠?瘥???嚗? BS ???雿??憭批潘???銵虜?舀?憭抒?嚗?
    # 甇????key嚗?文敶??耦蝛箇嚗Ⅱ靽? ??蝮?閮??典耦蝛箇?澆??賢??
    _bs_slot = _bs.get(_lat, {})
    def _fuzzy_bs(_inc, _exc=()):
        _best = 0.0
        for _fk, _fvv in _bs_slot.items():
            _fks = str(_fk).replace(' ', '').replace('?', '')
            if all(_i in _fks for _i in _inc) and not any(_e in _fks for _e in _exc):
                try:
                    _ffv = float(str(_fvv).replace(",", "") or 0)
                    if _ffv > _best:
                        _best = _ffv
                except Exception:
                    pass
        return _best
    if assets == 0:
        assets = _fuzzy_bs(["鞈"], ["鞎", "鞈", "?辣"])
        if assets > 0:
            print(f"[fetch_fin] {stock_id} assets 璅∠?瘥?: {assets:.0f}??)
    if liab == 0:
        liab = _fuzzy_bs(["鞎"], ["鞈", "皞?", "甈?"])
        if liab == 0:
            # ?曉祝嚗宏?扎????歹??踹????菜???蝘鋡恍??
            liab = _fuzzy_bs(["鞎"], ["鞈", "甈?"])
        if liab > 0:
            print(f"[fetch_fin] {stock_id} liab 璅∠?瘥?: {liab:.0f}??)
        else:
            # 摰憭望?嚗??BS ???雿?蝔曹?閮箸
            _all_bs_keys = sorted(_bs_slot.keys())
            print(f"[fetch_fin] {stock_id} liab 璅∠??典仃??"
                  f"bs_keys={_all_bs_keys[:30]}")
    if ar == 0:
        ar = _fuzzy_bs(["?"], ["?拇", "?敺?", "?∪極", "?辣", "?蝔?])
        if ar == 0:
            ar = _fuzzy_bs(["??鞈"])  # IFRS 15 ??鞈
        if ar > 0:
            print(f"[fetch_fin] {stock_id} ar 璅∠?瘥?: {ar:.0f}??)

    # ?? Pandas regex 蝯扔??嚗迤閬???征?賢???str.contains嚗??典耦蝛箇蝘 ??
    if (ar == 0 or liab == 0) and _bs_slot:
        try:
            import pandas as _pd_regex
            _bsdf = _pd_regex.DataFrame(
                list(_bs_slot.items()), columns=['type', 'value']
            )
            _bsdf['type_n'] = _bsdf['type'].str.replace(r'\s+|?', '', regex=True)
            _bsdf['val_n'] = _pd_regex.to_numeric(
                _bsdf['value'].astype(str).str.replace(',', '', regex=False),
                errors='coerce'
            )
            _bsdf = _bsdf[_bsdf['val_n'].notna() & (_bsdf['val_n'] > 0)]
            if ar == 0:
                _ar_mask = (_bsdf['type_n'].str.contains('?撣單狡|?蟡冽?', regex=True, na=False) &
                            ~_bsdf['type_n'].str.contains('?拇|?敺?|?∪極|?辣|?蝔?, regex=True, na=False))
                if _ar_mask.any():
                    ar = float(_bsdf.loc[_ar_mask, 'val_n'].max())
                    print(f"[fetch_fin] {stock_id} ar pandas-regex??: {ar:.0f}??"
                          f"type={_bsdf.loc[_ar_mask, 'type'].iloc[0]!r}")
            if liab == 0:
                _lb_mask = (_bsdf['type_n'].str.contains('鞎蝮質?|鞎??|鞎蝮賡?', regex=True, na=False) &
                            ~_bsdf['type_n'].str.contains('???瘚?鞎', regex=True, na=False))
                if _lb_mask.any():
                    liab = float(_bsdf.loc[_lb_mask, 'val_n'].max())
                    print(f"[fetch_fin] {stock_id} liab pandas-regex??: {liab:.0f}??"
                          f"type={_bsdf.loc[_lb_mask, 'type'].iloc[0]!r}")
        except Exception as _e_regex:
            print(f"[fetch_fin] {stock_id} pandas-regex???啣虜: {_e_regex}")

    # ?? FinMind ????str.contains ??嚗?璅?蝘?賢?嚗????餌?嚗??
    if ar == 0 and _bs_rows:
        try:
            import pandas as _pd_ar_sc
            _bs_df_sc = _pd_ar_sc.DataFrame(_bs_rows)
            if not _bs_df_sc.empty and 'date' in _bs_df_sc.columns and 'type' in _bs_df_sc.columns:
                _lat_sc = _bs_df_sc[_bs_df_sc['date'] == _lat].copy()
                _excl_kw = '?拇|?敺?|?∪極|?辣|?蝔?
                _on_col = (_lat_sc['origin_name'] if 'origin_name' in _lat_sc.columns
                           else _pd_ar_sc.Series([''] * len(_lat_sc), index=_lat_sc.index))
                _ar_mask = (
                    (_lat_sc['type'].str.contains('?撣單狡', na=False) |
                     _on_col.str.contains('?撣單狡', na=False)) &
                    ~_lat_sc['type'].str.contains(_excl_kw, na=False)
                )
                _ar_match_sc = _lat_sc[_ar_mask]
                if not _ar_match_sc.empty:
                    ar = float(_ar_match_sc['value'].max() or 0)
                    if ar > 0:
                        print(f"[fetch_fin] {stock_id} ar str.contains??: {ar:.0f}??"
                              f"types={list(_ar_match_sc['type'].values)[:3]}")
        except Exception as _e_ar_sc:
            print(f"[fetch_fin] {stock_id} ar str.contains???啣虜: {_e_ar_sc}")

    # ?? yfinance ?嚗?隞?嗥??甈??岫鋆?????????????????????????
    if ar == 0 or liab == 0 or assets == 0:
        try:
            import yfinance as _yf_ffs, pandas as _pd_yf_ffs
            _yf_bs_df = None
            for _sfx_yf in (".TW", ".TWO"):
                _tk_yf = _yf_ffs.Ticker(f"{stock_id}{_sfx_yf}")
                _qbs_yf = getattr(_tk_yf, "quarterly_balance_sheet", None)
                if _qbs_yf is not None and not _qbs_yf.empty:
                    _yf_bs_df = _qbs_yf
                    break
            if _yf_bs_df is not None and not _yf_bs_df.empty:
                _yfc = _yf_bs_df.columns[0]
                def _yf_v(*_keys_yf):
                    for _k in _keys_yf:
                        for _idx in _yf_bs_df.index:
                            if _k.lower() in str(_idx).lower():
                                try:
                                    _v = float(_yf_bs_df.loc[_idx, _yfc])
                                    if _pd_yf_ffs.notna(_v) and _v != 0:
                                        return _v
                                except Exception:
                                    pass
                    return 0.0
                _filled_yf = []
                if assets == 0:
                    _va = _yf_v("total assets")
                    if _va > 0:
                        assets = _va; _filled_yf.append("assets")
                if liab == 0:
                    _vl = _yf_v("total liab", "total liabilities")
                    if _vl > 0:
                        liab = _vl; _filled_yf.append("liab")
                if ar == 0:
                    _var = _yf_v("net receivables", "accounts receivable", "receivables")
                    if _var > 0:
                        ar = _var; _filled_yf.append("ar")
                if _filled_yf:
                    print(f"[fetch_fin] {stock_id} yfinance?鋆?{_filled_yf}: "
                          f"assets={assets:.0f} liab={liab:.0f} ar={ar:.0f} ??)
                    # ??yfinance 鋆? assets/equity嚗?閰虫?甈?IFRS identity
                    if liab == 0 and assets > 0 and equity > 0:
                        liab = max(assets - equity, 0)
                    if assets == 0 and equity > 0 and liab > 0:
                        assets = equity + liab
        except Exception as _e_yf:
            print(f"[fetch_fin] {stock_id} yfinance??啣虜: {_e_yf}")

    _zero_fields = [f for f, v in [("ar", ar), ("ppe", ppe), ("liab", liab), ("equity", equity)] if v == 0]
    if _zero_fields:
        _all_bs_keys = list((_bs.get(_lat) or {}).keys())
        print(f"[fetch_fin] {stock_id} ?嗅潭?雿?{_zero_fields} ?券BS甈?({len(_all_bs_keys)})={_all_bs_keys}")
        # AR ?券憭望???憭?閰佗???鞈嚗FRS 15嚗? 鞎踵??甈?/ ?甈暸?嚗??怠?荔?
        if ar == 0 and _all_bs_keys:
            for _extra_ar in ["??鞈", "瘚???鞈", "鞎踵??隞??嗆狡??,
                               "?甈暸?嚗??恍?靽犖嚗?, "?剜??甈?]:
                _ev = _bs_slot.get(_extra_ar)
                if _ev:
                    try:
                        _ef = float(str(_ev).replace(',', ''))
                        if _ef > 0:
                            ar = _ef
                            print(f"[fetch_fin] {stock_id} ar 鋆??亙? '{_extra_ar}': {ar:.0f}??)
                            break
                    except Exception:
                        pass

    # ?蝯?sanity check嚗iab/assets < 1% ???撮摮??株炊???雿??嗥? cur+noncur嚗?
    # ?啣?????萸?甈?靘那?瘀??岫 IFRS identity嚗quity ?冽迨撌脰◤靽格迤??
    if 0 < liab < assets * 0.01 and assets > 0:
        _liab_keys = [(k, _bs_slot.get(k)) for k in sorted(_bs_slot.keys())
                      if '鞎' in str(k) and '鞈' not in str(k)]
        print(f"[fetch_fin] {stock_id} ?? liab={liab:.0f} ??{liab/assets:.4%} of assets={assets:.0f}嚗?
              f"cur_liab={cur_liab:.0f} ncl={_non_cur_liab:.0f}嚗?
              f"鞎甈?={_liab_keys[:10]}")
        # ??IFRS identity ?岫靽格迤嚗quity 撌脣 1700-1703 ?◤靽格迤??assets-old_liab ??assets嚗?
        # 甇斗? equity ??assets嚗???assets - equity 銝銵??寧 fuzzy 撘瑕??銝甈?
        _liab_fuzzy2 = _fuzzy_bs(["鞎"], ["鞈", "甈?"])
        if _liab_fuzzy2 > liab * 5:
            liab = _liab_fuzzy2
            print(f"[fetch_fin] {stock_id} liab sanity 靽格迤 via fuzzy: {liab:.0f}??)

    # AR sanity嚗r/摮???< 0.5% ???撮摮??株炊??憒?靽犖?撟曉???
    if 0 < ar < (rev * 0.005) and rev > 0:
        _ar_keys = [(k, _bs_slot.get(k)) for k in sorted(_bs_slot.keys())
                    if '?' in str(k) and '?拇' not in str(k) and '?敺?' not in str(k)]
        print(f"[fetch_fin] {stock_id} ?? ar={ar:.0f}????{ar/(rev*4)*360:.1f}憭抬?"
              f"?甈?={_ar_keys[:10]}")
        _ar_fuzzy2 = _fuzzy_bs(["?"], ["?拇", "?敺?", "?∪極", "?辣", "?蝔?])
        if _ar_fuzzy2 > ar * 5:
            ar = _ar_fuzzy2
            print(f"[fetch_fin] {stock_id} ar sanity 靽格迤 via fuzzy: {ar:.0f}??)

    cash_ratio = round(cash / assets * 100, 1) if assets > 0 else 0
    debt_ratio = round(liab / assets * 100, 1) if assets > 0 else 0
    gp         = rev - cogs
    gm         = round(gp / rev * 100, 1) if rev > 0 else 0
    # 撟游?嚗摮?摮?? 4嚗誑??DSO/DPO 鋡思?隡?4 ??憭拇?箸?蝯曹? 360 憭?
    ar_days = round(ar / (rev * 4) * 360, 1) if rev > 0 and ar > 0 else 0
    ap_days = round(ap / (cogs * 4) * 360, 1) if cogs > 0 and ap > 0 else 0
    fcf        = round(ocf - capex)
    ar_chg     = round((ar - ar_p) / abs(ar_p) * 100, 1) if ar_p != 0 else None
    rev_chg    = round((rev - rev_p) / abs(rev_p) * 100, 1) if rev_p != 0 else None

    print(f"[fetch_fin] {stock_id} {_lat}: cash={cash_ratio}% debt={debt_ratio}% "
          f"OCF={round(ocf/1e6,1)}?曇 AR_days={ar_days} AP_days={ap_days}")

    return {
        "stock_id":         stock_id,
        "period":           _lat,
        "?暸?雿蜇鞈(%)":  cash_ratio,
        "鞎瘥?(%)":      debt_ratio,
        "OCF(??":          round(ocf),
        "ICF(??":          round(icf),
        "蝐?CF(??":       round(fncf),
        "?芰?暸?瘚???":   fcf,
        "鞈?臬(??":     round(capex),
        "?撣單狡憭拇":     ar_days,
        "??撣單狡憭拇":     ap_days,
        "瘥??%)":        gm,
        "?平?嗅(??":      round(rev),
        "瘥(??":          round(gp),
        "?平?拍?(??":      round(oper_income),
        "蝔?瘛典(??":      round(net_ni),
        "?⊥甈?(??":      round(equity),
        "瘚?鞈(??":      round(cur_assets),
        "????????":    round(max(liab - cur_liab, 0)),
        "?平?(??":      round(cogs),
        "OCF蝚西?":          "甇? if ocf > 0 else "鞎?,
        "ICF蝚西?":          "甇? if icf > 0 else "鞎?,
        "蝐?CF蝚西?":       "甇? if fncf > 0 else "鞎?,
        "?撣單狡摮????%)": ar_chg,
        "?摮????%)":     rev_chg,
        "蝮質?????":        round(assets),
        "蝮質?????":        round(liab),
        "瘚?鞎(??":      round(cur_liab),
        "摮疏(??":          round(inv),
        "摮疏??(??":      round(inv_p),
        "?暸??∪(??":      round(div_paid),
        "?箏?鞈(??":      round(ppe),
        "?瑟???(??":      round(lt_inv),
        # ?? v10.57.0 ?啣?嚗J 擃炎??嚗? ????
        "?暸????嗥????": round(cash),
        "?撣單狡(??":      round(ar),
        "EPS":               round(eps_v, 2) if eps_v else 0,
        "??甈暸?(??":      round(prepaid),
        "?嗡?????????": round(other_nca),
        "is_finance":        stock_id.startswith(('28', '58')),
        # ?? ?? slot ?湧嚗?閮箸??颲具PI ?仃??/ 甇方?⊥迨蝘 / 閰脰?砍迤??0???
        "_bs_slot_latest":   dict(_bs_slot),
        "_cf_slot_latest":   dict(_cf.get(_lat, {})),
        "_is_slot_latest":   dict(_is.get(_lat, {})),
        "_period_latest":    _lat,
    }


def fetch_fund_nav(fund_id: str):
    """?粹?瘛典???MoneyDJ via NAS proxy + BeautifulSoup"""
    try:
        from proxy_helper import fetch_url as _fu_nav
        from bs4 import BeautifulSoup as _BS
        _r = _fu_nav(
            f'https://www.moneydj.com/funddj/yb/YP010001.djhtm?a={fund_id}',
            timeout=12,
        )
        if _r is None:
            return None
        _soup = _BS(_r.text, 'html.parser')
        _table = _soup.find('table', id='ctl00_ctl00_ContentPlaceHolder1_contentMain_gvReport')
        if _table is None:
            _table = _soup.find('table')
        if _table is None:
            return None
        for _row in _table.find_all('tr')[1:]:
            _cells = _row.find_all('td')
            if len(_cells) >= 2:
                try:
                    _date = _cells[0].get_text(strip=True)
                    _nav = float(_cells[1].get_text(strip=True).replace(',', ''))
                    if _nav > 0:
                        return {'date': _date, 'nav': _nav}
                except (ValueError, IndexError):
                    continue
        return None
    except Exception as _e:
        print(f'[fetch_fund_nav] ??{fund_id}: {_e}')
        return None



