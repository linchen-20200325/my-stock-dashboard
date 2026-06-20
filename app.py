from data_config import CACHE_TTL
import streamlit as st
import pandas as pd
import datetime
import os
import re
import time
import requests
import json
import pickle
import hashlib
import sys

# ?? Streamlit Cloud ?脰風嚗R #82/#86 ????????????????????
# tab_*.py ??`from app import X`嚗ython 韏?sys.modules['app'] ?暹芋蝯?
# Cloud 銝?sys.modules['__main__'] ??Streamlit CLI binary 銝 script嚗?
# ?隞?PR #82 ??`setdefault('app', sys.modules[__name__])` ?璅∠???
# PR #86 ??ModuleType proxy + closure嚗? closure 蝬?method.__globals__
# 閫?? `_app_globals` ?迂撠?Streamlit rerun 銵??鞈氬?
# ?寧??globals dict 憛?proxy.__dict__嚗?甈⊿ refresh嚗器摨圾?艾?
import types as _types  # noqa: E402
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

class _AppProxy(_types.ModuleType):
    """Proxy嚗from app import X` ??敺?proxy ?芸楛 dict ??live globals??""
    def __getattr__(self, name):
        g = self.__dict__.get('__app_globals__')
        if g is None:
            raise AttributeError(f"module 'app' proxy uninitialized; missing {name!r}")
        try:
            return g[name]
        except KeyError:
            raise AttributeError(
                f"module 'app' has no attribute {name!r} "
                f"(globals has {len(g)} keys)"
            ) from None

_existing = sys.modules.get('app')
if isinstance(_existing, _AppProxy):
    _existing.__dict__['__app_globals__'] = globals()
else:
    _proxy = _AppProxy('app')
    _proxy.__dict__['__app_globals__'] = globals()
    sys.modules['app'] = _proxy

# ?? ?啁??嚗TC+8嚗?????????????????????????????????????
_TW_TZ = datetime.timezone(datetime.timedelta(hours=8))
def _tw_now(): return datetime.datetime.now(_TW_TZ)
def _tw_now_str(): return _tw_now().strftime('%Y-%m-%d %H:%M')

def _bps():
    try:
        from tw_stock_data_fetcher import build_proxy_session as _b
        s = _b()
    except Exception:
        s = requests.Session()
    s.verify = False
    return s
import yfinance as yf  # noqa: E402

print('[INFO] main.py v3.0 ?唳?摰?頛摰?')

from data_loader import StockDataLoader, _LOADER_VERSION  # noqa: E402
# ?? ?啣?璅∠?嚗?牧? v1.0嚗??????????????????????????????
# ?? v3.0 ?啣?璅∠?嚗?-禮11嚗??????????????????????????????????
from etf_dashboard import (  # noqa: E402
    render_etf_single, render_etf_portfolio,
    # v18.182 ARCHIVED: render_etf_backtest ?葫?怠?摮?
    render_etf_ai,
    render_sector_heatmap,
)
from health_inspector import render_data_health_raw  # noqa: E402
from api_diagnostic import render_api_diagnostic  # noqa: E402
from grape_ladder import render_grape_ladder  # noqa: E402
from persona import TAIWAN_ADVISOR_PERSONA as _PERSONA  # noqa: E402

api_key       = st.secrets.get('GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY', ''))  # [Fixed] st.secrets ?芸?
FINMIND_TOKEN = st.secrets.get('FINMIND_TOKEN',  os.environ.get('FINMIND_TOKEN', ''))   # [Fixed] st.secrets ?芸?

# [Fixed] ?郊??os.environ嚗?摮芋蝯?撅方???踹甇?Ⅱ??
if FINMIND_TOKEN:
    os.environ['FINMIND_TOKEN'] = FINMIND_TOKEN
if api_key:
    os.environ['GEMINI_API_KEY'] = api_key

def _get_fm_token():
    """瘥活??霈????Token嚗t.secrets > os.environ"""
    _tok = (getattr(st, 'secrets', {}).get('FINMIND_TOKEN')
            or os.environ.get('FINMIND_TOKEN', ''))
    return _tok

st.set_page_config(page_title='?啗AI?唳?摰?v3.0', layout='wide',
                   page_icon='??', initial_sidebar_state='collapsed')

# ?? OAuth callback嚗RL 撣??code= ??? token嚗???澆隞?query_params ??嚗?
try:
    from oauth_state import handle_oauth_callback as _oauth_cb
    _oauth_cb()
except Exception as _oauth_err:
    print(f'[oauth callback] {_oauth_err}')

# ?? App ?????嚗???Session ?銵?甈∴??脤?銴艘??????????????
if '_app_boot_done' not in st.session_state:
    st.session_state['_app_boot_done'] = True
    # 擐活??皜?翰??敺? rerun 銝??瑁?嚗 API Storm嚗?
    try:
        st.cache_data.clear()
    except Exception:
        pass
    # [Phase 3] 敺?URL query_params ?Ｗ儔???????瑞???靽?閮剖?嚗?
    try:
        _qp = st.query_params
        if _qp.get('chips') == '1':
            st.session_state['chips_loaded'] = True
        _qp_sid = _qp.get('sid')
        if _qp_sid and isinstance(_qp_sid, str) and _qp_sid.isdigit():
            st.session_state['_qp_sid'] = _qp_sid  # ? Tab ??????
    except Exception as _qpe:
        print(f'[query_params restore] {_qpe}')

# [Phase 3] ???郊嚗ession_state ??query_params嚗???? URL 隞葆???
try:
    _qp_w = st.query_params
    if st.session_state.get('chips_loaded') and _qp_w.get('chips') != '1':
        _qp_w['chips'] = '1'
    elif not st.session_state.get('chips_loaded') and _qp_w.get('chips') == '1':
        del _qp_w['chips']
except Exception:
    pass

st.markdown(f"""<style>
.main{{background:#0e1117;}}
[data-testid="stSidebar"]{{background:#161b22;}}
.stTabs [data-baseweb="tab-list"]{{gap:2px;}}
.stTabs [data-baseweb="tab"]{{background:#161b22;color:#8b949e;border-radius:6px 6px 0 0;padding:8px 16px;font-size:13px;}}
.stTabs [aria-selected="true"]{{background:linear-gradient(135deg,#1f6feb,#0d4faa);color:#fff;font-weight:700;}}
.teacher-card{{background:#0d1117;border-left:3px solid #ffd700;border-radius:0 8px 8px 0;padding:10px 14px;margin:6px 0;}}
.health-A{{background:linear-gradient(90deg,#0d2818,#0d1117);border:2px solid {TRAFFIC_GREEN};border-radius:12px;padding:16px;text-align:center;}}
.health-B{{background:linear-gradient(90deg,#2a1f00,#0d1117);border:2px solid {TRAFFIC_YELLOW};border-radius:12px;padding:16px;text-align:center;}}
.health-C{{background:linear-gradient(90deg,#2a0d0d,#0d1117);border:2px solid {TRAFFIC_RED};border-radius:12px;padding:16px;text-align:center;}}
</style>""", unsafe_allow_html=True)

# ????????????????????????????????????????????????????????????????
# HELPERS
# ????????????????????????????????????????????????????????????????
def parse_stocks(raw):
    stocks = re.split(r'[,\s\n嚗?]+', raw.strip())
    return [s.strip() for s in stocks if s.strip() and re.match(r'^\d{4,6}[A-Z]?$', s.strip())]

# ?? Gemini ?瘙??? B嚗?撣唾? key ?芸???嚗????摨?/ ???嚗??????
# 霈 GEMINI_API_KEY + GEMINI_API_KEY_2 .. _6嚗t.secrets ?芸?嚗s.environ fallback嚗?
# gemini_call 隞?round-robin 韏瑟? key嚗????銝? tab 敺??? key ?? ???鞎?嚗?
# 隞颱?????429嚗?/憿漲皛選???403嚗?????銝????券?函??胯?
_GEMINI_KEY_NAMES = ['GEMINI_API_KEY'] + [f'GEMINI_API_KEY_{_i}' for _i in range(2, 7)]
_gemini_rr = [0]  # round-robin 韏瑟?蝝Ｗ?嚗?甈∪?恍?憓?


def _gemini_keys() -> list:
    """?園?????Gemini API key嚗??摨??t.secrets ?芸?嚗s.environ fallback??""
    _keys = []
    for _n in _GEMINI_KEY_NAMES:
        try:
            _v = st.secrets.get(_n, '') or os.environ.get(_n, '')
        except Exception:
            _v = os.environ.get(_n, '')
        _v = str(_v or '').strip()
        if _v and _v not in _keys:
            _keys.append(_v)
    if api_key and api_key not in _keys:
        _keys.append(api_key)
    return _keys


def gemini_call(prompt, max_tokens=2048):
    _keys = _gemini_keys()
    if not _keys:
        return '?? 隢身摰?GEMINI_API_KEY嚗?血? GEMINI_API_KEY_2 ~ _6 ?憿漲嚗?
    # round-robin 韏瑟?嚗???怠?銝???key ??嚗?嗆?鞎???啣?撣唾?
    _start = _gemini_rr[0] % len(_keys)
    _gemini_rr[0] = (_gemini_rr[0] + 1) % 1_000_000
    _keys = _keys[_start:] + _keys[:_start]
    # 2026-03 ??璅∪?嚗?.5蝟餃??券?敶對?2.5?箔蜓??
    _models = ['gemini-2.5-flash-lite', 'gemini-2.5-flash',
               'gemini-2.0-flash', 'gemini-2.0-flash-lite']
    for _model in _models:
        # Gemini 2.5 ?身?芋撘???token ??頛詨?梁 maxOutputTokens 憿漲
        # ??撣詨??游?閬??銝?停鋡急?瑯閰望?閬??瘛勗漲?函?嚗???thinkingBudget=0嚗?
        _gen_cfg = {'temperature': 0.3, 'maxOutputTokens': max_tokens}
        if _model.startswith('gemini-2.5'):
            _gen_cfg['thinkingConfig'] = {'thinkingBudget': 0}
        for _ki, _key in enumerate(_keys):
            try:
                _r = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{_model}:generateContent',
                    params={'key': _key},
                    json={'systemInstruction': {'parts': [{'text': _PERSONA}]},
                          'contents': [{'parts': [{'text': prompt}]}],
                          'generationConfig': _gen_cfg},
                    timeout=120
                )
                if _r.status_code == 200:
                    _d = _r.json()
                    _cands = _d.get('candidates', [])
                    if _cands:
                        _parts = _cands[0].get('content', {}).get('parts', [])
                        if _parts and _parts[0].get('text'):
                            return _parts[0]['text']
                    # safety ?嚗? key ?∪?????湔??銝??model
                    if _cands and _cands[0].get('finishReason', '') == 'SAFETY':
                        break
                    continue  # 蝛箏?閬???閰虫?銝??key
                elif _r.status_code == 400:
                    _err_msg = (_r.json() if _r.text else {}).get('error', {}).get('message', _r.text[:100])
                    print(f'[Gemini/{_model}] 400 Bad Request: {_err_msg}')
                    break  # 閮剖?/prompt ??嚗? key ?∠ ????銝??model
                elif _r.status_code == 403:
                    print(f'[Gemini/{_model}] 403 蝚?{_ki+1} ??key ?⊥?/?⊥???????銝??)
                    continue  # ??key
                elif _r.status_code == 404:
                    break  # 甇?model 銝???????銝??model
                elif _r.status_code == 429:
                    print(f'[Gemini/{_model}] 429 蝚?{_ki+1} ??key 憿漲/??皛?????銝??)
                    continue  # ??key嚗?瘜?B ?詨?嚗????交?撣唾?嚗?
                else:
                    print(f'[Gemini/{_model}] HTTP {_r.status_code}: {_r.text[:200]}')
                    continue  # ??key
            except Exception as _ge:
                print(f'[Gemini/{_model}] key#{_ki+1} {type(_ge).__name__}: {_ge}')
                continue  # ??key
    return ('?? AI ???急??⊥?雿輻嚗???key ?芋?閰阡?鈭???'
            '隢Ⅱ隤????圈?摨佗???敺?閰?)

# ?? ?砍敹怠?嚗QLite + Pickle ??嚗???????????????????????
_CACHE_DIR = '/tmp/stock_cache'
os.makedirs(_CACHE_DIR, exist_ok=True)

def _cache_key(prefix, sid, extra=''):
    raw = f'{prefix}_{sid}_{extra}_{datetime.date.today()}'
    return os.path.join(_CACHE_DIR, hashlib.md5(raw.encode()).hexdigest() + '.pkl')

def _load_cache(prefix, sid, extra='', ttl_hours=6):
    path = _cache_key(prefix, sid, extra)
    if os.path.exists(path):
        age = (time.time() - os.path.getmtime(path)) / 3600
        if age < ttl_hours:
            try:
                with open(path,'rb') as f:
                    return pickle.load(f)
            except Exception:
                pass
    return None

def _save_cache(prefix, sid, data, extra=''):
    path = _cache_key(prefix, sid, extra)
    try:
        with open(path,'wb') as f:
            pickle.dump(data, f)
    except Exception:
        pass

@st.cache_resource
def _get_loader(_v: str = _LOADER_VERSION):
    """敹怠??桐? StockDataLoader 撖虫?嚗??甈?cache miss ?賡???login??

    `_v` 蝬? `data_loader._LOADER_VERSION`嚗??loader ?摩銝?bump ?敺?
    cache key ?其??寡? ???芸?撱箇??啣祕靘??踹? Streamlit hot-reload 敺??典
    ?祕靘??瘜Ⅳ嚗tale @st.cache_resource嚗R #44 NoneType 畾??單迨????
    """
    return StockDataLoader()

def _expected_latest_trading_date():
    d = datetime.date.today()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d

@st.cache_data(ttl=CACHE_TTL["financial_data"], max_entries=10)
def fetch_price_data(sid, days):
    _c = _load_cache('price', sid, str(days), ttl_hours=0.5)
    if _c is not None:
        df_c, name_c = _c
        if df_c is not None and not df_c.empty and float(df_c['close'].max()) > 0:
            try:
                _latest = df_c['date'].iloc[-1]
                if hasattr(_latest, 'date'):
                    _latest = _latest.date()
                elif isinstance(_latest, str):
                    _latest = datetime.datetime.strptime(str(_latest)[:10], '%Y-%m-%d').date()
                # 5 ??calendar day ?扯??箸擙殷?瘨菔??望 + 1 ???嚗?頞? ??撘瑕??
                if (_expected_latest_trading_date() - _latest).days <= 5:
                    return df_c, name_c, None
            except Exception:
                return df_c, name_c, None
    loader = _get_loader()
    df, err, name = loader.get_combined_data(sid, days + 60, True)
    if err or df is None:
        return None, None, err
    result = df.tail(days).reset_index(drop=True)
    try:
        result.attrs.update(df.attrs)
    except Exception:
        pass
    _save_cache('price', sid, (result, name), str(days))
    return result, name, None

@st.cache_data(ttl=CACHE_TTL["financial_data"], max_entries=10)
def fetch_dividend_data(sid):
    avg_div, yearly, source = 0.0, [], ''
    try:
        try:
            from FinMind.data import DataLoader as FM
        except ImportError:
            from finmind.data import DataLoader as FM
        dl = FM()
        _fm_tok_div = _get_fm_token()
        if _fm_tok_div:
            try:
                dl.login_by_token(api_token=_fm_tok_div)
            except Exception:
                pass
        end = datetime.date.today()
        # First try REST API with proper auth
        _div_resp = _bps().get('https://api.finmindtrade.com/api/v4/data',
            params={'dataset':'TaiwanStockDividend','data_id':sid,
                    'start_date':(end-datetime.timedelta(days=365*6)).strftime('%Y-%m-%d')},
            headers={'Authorization':f'Bearer {_get_fm_token()}'},timeout=20)
        _div_jd = _div_resp.json()
        print(f'[?∪REST] {sid} status={_div_jd.get("status")}')
        ddf = pd.DataFrame(_div_jd['data']) if _div_jd.get('status')==200 and _div_jd.get('data') else None
        if ddf is None or ddf.empty:
            ddf = dl.taiwan_stock_dividend(stock_id=sid,
                                           start_date=(end-datetime.timedelta(days=365*6)).strftime('%Y-%m-%d'))
        if ddf is not None and not ddf.empty:
            cash_col = next((c for c in ['CashDividend','cash_dividend','StockEarningsDistribution']
                             if c in ddf.columns), None)
            if cash_col is None:
                nums = ddf.select_dtypes(include='number').columns.tolist()
                if nums:
                    cash_col = nums[0]
            if cash_col:
                ddf['date'] = pd.to_datetime(ddf['date'], errors='coerce')
                ddf['year'] = ddf['date'].dt.year
                ddf['cash'] = pd.to_numeric(ddf[cash_col], errors='coerce').fillna(0)
                yr = ddf.groupby('year')['cash'].sum().reset_index().tail(5)
                avg_div = float(yr['cash'].mean()) if len(yr) > 0 else 0
                yearly = yr.to_dict('records')
                source = 'FinMind'
    except Exception:
        pass
    # ?? ?2: yfinance嚗18.209 K5嚗韏?yf_proxy.cached_dividends嚗roxy+cache 蝯曹?嚗??
    if avg_div == 0:
        try:
            from yf_proxy import cached_dividends as _yp_div
            divs = _yp_div(f'{sid}.TW')
            if divs is not None and len(divs) > 0:
                divs.index = pd.DatetimeIndex(divs.index).tz_localize(None)
                rec = divs[divs.index >= pd.Timestamp.now()-pd.DateOffset(years=5)]
                if len(rec) > 0:
                    ann = rec.resample('YE').sum().reset_index()
                    ann.columns = ['date','cash']
                    ann['year'] = pd.to_datetime(ann['date']).dt.year
                    yr = ann[['year','cash']].tail(5)
                    avg_div = float(yr['cash'].mean())
                    yearly = yr.to_dict('records')
                    source = 'yfinance'
        except Exception:
            pass

    # ?? ?3: TWSE ?斗??航???摰嚗?Token嚗??
    if avg_div == 0:
        try:
            _tw_div_url = 'https://www.twse.com.tw/rwd/zh/exRight/TWT49U'
            _start_dt_div = (datetime.date.today()-datetime.timedelta(days=365*6)).strftime('%Y%m%d')
            _end_dt_div   = datetime.date.today().strftime('%Y%m%d')
            _tw_div_r = _bps().get(
                _tw_div_url,
                params={'response': 'json', 'strDate': _start_dt_div,
                        'endDate': _end_dt_div, 'stockNo': sid},
                headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                         'Referer':'https://www.twse.com.tw/',
                         'Accept':'application/json, text/javascript, */*; q=0.01',
                         'Accept-Language':'zh-TW,zh;q=0.9,en;q=0.8',
                         'X-Requested-With':'XMLHttpRequest'},
                timeout=15)
            _tw_div_j = _tw_div_r.json()
            if _tw_div_j.get('stat') == 'OK' and _tw_div_j.get('data'):
                _tw_div_rows = []
                for _dr in _tw_div_j['data']:
                    # 甈?嚗?交?, ?∠巨隞??, ?迂, ?斗??臬??嗥, ??鈭斗??箸??? ?暸??∪, ?∠巨?∪, ...]
                    try:
                        _yr_div = int(str(_dr[0]).split('/')[0])
                        if _yr_div < 1000:
                            _yr_div += 1911
                        _cash_d = float(str(_dr[5]).replace(',','')) if len(_dr) > 5 else 0
                        if _cash_d > 0:
                            _tw_div_rows.append({'year': _yr_div, 'cash': _cash_d})
                    except Exception:
                        pass
                if _tw_div_rows:
                    _tw_div_df = pd.DataFrame(_tw_div_rows)
                    yr = _tw_div_df.groupby('year')['cash'].sum().reset_index().tail(5)
                    avg_div = float(yr['cash'].mean())
                    yearly = yr.to_dict('records')
                    source = 'TWSE'
        except Exception as _eTD:
            pass

    return avg_div, yearly, source

@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=10)
def fetch_financials(sid, industry: str = ""):
    """
    ??鞎 + ?箏?鞈 + 鞈?臬 ??v3.35 蝪∪???
    100% FinMind嚗?鞎餌?撌脩Ⅱ隤?status=200嚗?
    type 甈??箔蜓?蛛?瘥?origin_name ?游??
    """
    import datetime as _dtf
    try:
        from tw_stock_data_fetcher import build_proxy_session as _bps_fin
        _rq_f = _bps_fin()
    except Exception:
        import requests as _rq_f_fallback
        _rq_f = _rq_f_fallback.Session()
    _rq_f.verify = False

    cl = cx = _capex = None
    cl_src = cx_src = cx_src_capex = ""
    fetch_errors = []
    _tok = _get_fm_token()
    _start = (_dtf.date.today() - _dtf.timedelta(days=365*3)).strftime('%Y-%m-%d')

    # ?? Step 1: BalanceSheet ????鞎 + ?箏?鞈 ??????????????
    try:
        _params = {"dataset":"TaiwanStockBalanceSheet","data_id":sid,"start_date":_start}
        if _tok:
            _params["token"] = _tok
        _hdrs = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}
        if _tok:
            _hdrs["Authorization"] = f"Bearer {_tok}"
        _r = _rq_f.get("https://api.finmindtrade.com/api/v4/data",
                        params=_params, headers=_hdrs, timeout=20)
        _j = _r.json()
        _rows = _j.get("data", [])
        _fm_status = _j.get("status")
        _fm_msg = _j.get("msg","")
        print(f"[FM-BS] {sid} HTTP {_r.status_code} status={_fm_status} rows={len(_rows)}")
        if _fm_status != 200:
            fetch_errors.append(f"FinMind-BS:HTTP{_r.status_code}:{_fm_msg or _fm_status}")
        if _fm_status == 200 and _rows:
            # ???唬?摮?
            _dates = sorted(set(r.get("date","") for r in _rows), reverse=True)
            _latest_dt = _dates[0] if _dates else None
            _latest = [r for r in _rows if r.get("date") == _latest_dt]
            print(f"[FM-BS] Latest={_latest_dt} rows={len(_latest)}")

            # ??鞎
            _CL_TYPES = ["CurrentContractLiabilities","ContractLiabilities"]
            _CL_NAMES = ["??鞎","憟?鞎","?甈暸?"]
            _cl_total = 0.0
            for _row in _latest:
                _t = str(_row.get("type",""))
                if any(_t == _ct or _t.startswith(_ct) for _ct in _CL_TYPES):
                    _v = float(str(_row.get("value",0)).replace(",","") or 0)
                    if _v > 0:
                        _cl_total += _v
            if _cl_total == 0:  # fallback: origin_name
                for _row in _latest:
                    _n = str(_row.get("origin_name",""))
                    if any(_k in _n for _k in _CL_NAMES):
                        _v = float(str(_row.get("value",0)).replace(",","") or 0)
                        if _v > 0:
                            _cl_total += _v
            if _cl_total > 0:
                cl = _cl_total
                cl_src = "FinMind"
                print(f"[FM-BS] ????鞎={cl/1e8:.2f}??)

            # ?箏?鞈
            _FA_TYPE = "PropertyPlantAndEquipment"
            for _row in _latest:
                _t = str(_row.get("type",""))
                if _t == _FA_TYPE or (_FA_TYPE in _t and "_per" not in _t):
                    _v = float(str(_row.get("value",0)).replace(",","") or 0)
                    if _v > 0:
                        cx = _v
                        cx_src = "FinMind"
                        break
            if cx is None:
                for _row in _latest:
                    _n = str(_row.get("origin_name",""))
                    if any(_k in _n for _k in ["銝??Ｕ??踹?閮剖?","?箏?鞈"]):
                        _v = float(str(_row.get("value",0)).replace(",","") or 0)
                        if _v > 0:
                            cx = _v
                            cx_src = "FinMind-name"
                            break
            if cx:
                print(f"[FM-BS] ???箏?鞈={cx/1e8:.2f}??)
    except Exception as _e_bs:
        err_msg = f"FinMind-BS:{type(_e_bs).__name__}:{_e_bs}"
        fetch_errors.append(err_msg)
        print(f"[FM-BS] ??{err_msg}")

    # ?? Step 2: CashFlowsStatement ??鞈?臬 ????????????????????
    try:
        _params2 = {"dataset":"TaiwanStockCashFlowsStatement","data_id":sid,"start_date":_start}
        if _tok:
            _params2["token"] = _tok
        _hdrs2 = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}
        if _tok:
            _hdrs2["Authorization"] = f"Bearer {_tok}"
        _r2 = _rq_f.get("https://api.finmindtrade.com/api/v4/data",
                         params=_params2, headers=_hdrs2, timeout=20)
        _j2 = _r2.json()
        _rows2 = _j2.get("data",[])
        _fm2_status = _j2.get("status")
        _fm2_msg = _j2.get("msg","")
        print(f"[FM-CF] {sid} HTTP {_r2.status_code} status={_fm2_status} rows={len(_rows2)}")
        if _fm2_status != 200:
            fetch_errors.append(f"FinMind-CF:HTTP{_r2.status_code}:{_fm2_msg or _fm2_status}")
        if _fm2_status == 200 and _rows2:
            _dates2 = sorted(set(r.get("date","") for r in _rows2), reverse=True)
            _latest2 = [r for r in _rows2 if r.get("date") == (_dates2[0] if _dates2 else None)]
            _CX_TYPES = ["PropertyAndPlantAndEquipment","AcquisitionOfPropertyPlantAndEquipment"]
            _CX_NAMES = ["??銝??Ｕ??踹?閮剖?","鞈潛蔭銝??Ｕ??踹?閮剖?","鞈?臬"]
            _cx2 = None
            for _row in _latest2:
                _t = str(_row.get("type",""))
                if any(_ct in _t for _ct in _CX_TYPES):
                    _v = float(str(_row.get("value",0)).replace(",","") or 0)
                    if _v != 0:
                        _cx2 = abs(_v)
                        break
            if _cx2 is None:
                for _row in _latest2:
                    _n = str(_row.get("origin_name",""))
                    if any(_k in _n for _k in _CX_NAMES):
                        _v = float(str(_row.get("value",0)).replace(",","") or 0)
                        if _v != 0:
                            _cx2 = abs(_v)
                            break
            if _cx2 and _cx2 > 0:
                _capex = _cx2
                cx_src_capex = "FinMind-CF"
                if cx is None:
                    cx = _capex
                    cx_src = "FinMind-CF"
                print(f"[FM-CF] ??鞈?臬={_capex/1e8:.2f}??)
    except Exception as _e_cf:
        fetch_errors.append(f"FinMind-CF:{type(_e_cf).__name__}:{_e_cf}")
        print(f"[FM-CF] ??{_e_cf}")

    def _fmt(v): return f"{v/1e8:.1f}" if v else "-"
    print(f"[FIN] {sid}: cl={_fmt(cl)}?? cx={_fmt(cx)}?? capex={_fmt(_capex)}??)
    return cl, cx, _capex, cl_src, cx_src, cx_src_capex, fetch_errors


@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=10)
def fetch_revenue(sid):
    try:
        loader = _get_loader()
        result = loader.get_monthly_revenue(sid)
        if result is None:
            return None, '???塚??折?None'
        if isinstance(result, tuple):
            return result
        return result, None  # single value
    except Exception as e:
        print(f"[fetch_revenue] {e}")
        return None, str(e)

@st.cache_data(ttl=CACHE_TTL["price_data"], max_entries=10)
def fetch_quarterly(sid, _ver=4):   # _ver ?寡??單??方?敹怠?
    try:
        loader = _get_loader()
        result = loader.get_quarterly_data(sid)
        if result is None:
            return None, '摮?瓷?梧??折?None'
        if isinstance(result, tuple):
            return result
        return result, None
    except Exception as e:
        print(f"[fetch_quarterly] {e}")
        return None, str(e)

@st.cache_data(ttl=CACHE_TTL["price_data"], show_spinner=False, max_entries=10)
def fetch_quarterly_extra(sid, _ver=2):   # _ver ?寡??單??方?敹怠?
    """??餈?12 摮???Ｚ??菔” + ?暸?瘚???嚗?蝝??萸?鞎具??祆?綽?嚗?澆??餃??賢???""
    try:
        loader = _get_loader()
        result = loader.get_quarterly_bs_cf(sid)
        if result is None:
            return None, 'BS/CF嚗?典??術one'
        if isinstance(result, tuple):
            return result
        return result, None
    except Exception as e:
        print(f"[fetch_quarterly_extra] {e}")
        return None, str(e)

# ????????????????????????????????????????????????????????????????
# ?銵?璅?蝞???撌脫?箄 tech_indicators.py嚗R P2-B Phase 1嚗?
# ????????????????????????????????????????????????????????????????

# ????????????????????????????????????????????????????????????????
# ?亙熒摨西???0~100嚗?撌脫?箄 scoring_helpers.py嚗R P2-B Phase 3嚗?
# ????????????????????????????????????????????????????????????????
from scoring_helpers import (  # noqa: E402
    health_grade,
)

# ????????????????????????????????????????????????????????????????
# ?飛???牧?頂蝯???撌脫?箄 ui_widgets.py嚗R P2-B Phase 2嚗?
# ????????????????????????????????????????????????????????????????
from ui_widgets import (  # noqa: E402
    traffic_light, show_term_help,
)
# P2-B Phase 5 A/B/C/D: 4 ??TAB ?券撌脫?啁蝡芋蝯?app.py 9208??394 銵???5%嚗?
from tab_edu import render_tab_edu  # noqa: E402
from tab_stock_grp import render_stock_grp  # noqa: E402
from tab_stock import render_tab_stock  # noqa: E402
from tab_macro import render_tab_macro  # noqa: E402

# ?典?銵?璅?section 雿輻
_TERM_HELP_LI = show_term_help('PCR') + show_term_help('ADL') + show_term_help('M1B-M2')

# ????????????????????????????????????????????????????????????????
# generate_ai_comment嚗ule-based ???撱箄降嚗? AI API嚗?
# 頛詨嚗ict ?怨瓷???銵?蝐Ⅳ?豢?
# 頛詨嚗?銵遣霅唳?摮?
# ????????????????????????????????????????????????????????????????

# ?? 鞈?臬蝝航??園???v4.0 靽格迤嚗??????????????????????????
def generate_ai_comment(data: dict) -> str:
    """
    瘙箇?璅寞?摮遣霅啁?
    data ?萄潘?
      health, rsi, vcp_ok, bias_240, bias_20
      val_label (357閰), trend, cl (??鞎??, cx (鞈?臬??
      foreign_buy, trust_buy (銝之瘜犖, ??, score (憭?摮蜇??
      m1b_diff (M1B-M2 撌株?%)
    """
    lines = []
    score  = data.get('score', 0)
    rsi    = data.get('rsi') or 50
    val    = str(data.get('val_label', ''))
    trend  = str(data.get('trend', ''))
    cl     = data.get('cl') or 0
    cx     = data.get('cx') or 0
    fb     = data.get('foreign_buy') or 0   # 憭?鞎瑁都??
    tb     = data.get('trust_buy') or 0     # ?縑
    vcp_ok = data.get('vcp_ok', False)
    b240   = data.get('bias_240') or 0
    b20    = data.get('bias_20') or 0
    m1b    = data.get('m1b_diff') or 0      # M1B-M2 撌株?

    # ?? ?舀除?啣??韌 ??????????????????????????????????????????
    if m1b < 0:
        lines.append('?? ?瘞?憓1B-M2?箄?嚗???潸??葬皜???
                     '撱箄降蝬剜?雿??∴?30%隞乩?嚗??芸??豢?雿????∪璅???)
    elif m1b > 2:
        lines.append('?? ?瘞?憓1B-M2?箸迤銝撥??鞈?銵???銝哨??舐?璆菜??～?)

    # ?? 鞎∪閰摯 ?????????????????????????????????????????????
    fin_msg = []
    # ??鞎???????瘚????亙????嗆狡??
    if cl > 0:
        fin_msg.append(f'??鞎{cl:.1f}??瘚?+????閮??恍??嗆狡??')
    if cx > 0:
        fin_msg.append(f'鞈?臬{cx:.1f}??憭扯?璅⊥撱?2-3撟游????舀?嚗?)
    if fin_msg:
        lines.append('?? ?瓷?梯??? + '嚗?.join(fin_msg) + '??)

    # ?? 撘瑞?鞎瑕璇辣嚗85??????????????????????????????????
    if score >= 85 and '靘踹?' in val and '憭' in trend:
        lines.append('?? ?撥?眺?乓??85 + 357靘踹???+ 憭????
                     '撱箄降蝒60?亦拳????脣嚗?皜祉?K雿?銝?臬?蝣潦?)
    elif score >= 75 and '靘踹?' in val:
        lines.append('????璆菔眺?乓??75銝???57靘踹??嚗?撣???)
    elif score >= 75:
        lines.append('??????胯???閰???5嚗?銵?亙熒嚗?撱箇?摨?)

    # ?? 蝐Ⅳ閰摯 ?????????????????????????????????????????????
    if fb > 5 and tb > 0:
        lines.append(f'? ??蝣澆?胯?鞈?{fb:.1f}??& ?縑+{tb:.1f}??銝餃??勗?鞎琿莎?閮?撘瑞???)
    elif fb > 5:
        lines.append(f'? ??鞈眺?脯?鞈?{fb:.1f}??頝?憭扳韏堆?摰蝑嚗?)
    elif fb < -10:
        lines.append(f'?? ??鞈都頞?鞈?{abs(fb):.1f}??蝐Ⅳ?Ｚ?撘梧?撱箄降蝑???)

    # ?? VCP ?脣閮? ?????????????????????????????????????????
    if vcp_ok:
        lines.append('? ?CP蝐Ⅳ摰??郭撟?蝥蝮殷?蝐Ⅳ?葉?澆撥??
                     '撱箄降撣園?蝒擃??誑30~50%撱箇?摨?蝑3嚗?)

    # ?? ?銵閰摯 ???????????????????????????????????????????
    if rsi < 30:
        lines.append(f'?? RSI={rsi:.0f}嚗?鞈??嚗??剔???璈?擃??臬??岫?柴?)
    elif rsi > 75:
        lines.append(f'?? RSI={rsi:.0f}嚗?鞎瑕?嚗?瘜冽??剔??矽憸券嚗?摰蕭擃?)

    # ?? 銋??隡????????????????????????????????????????????
    if b240 > 25:
        lines.append(f'? ???梯郎?僑蝺迤銋{b240:.0f}%嚗?25%嚗?蝑1嚗?憪??寞?蝣潦?
                     '撱箄降??祇?嚗擗雿?10?梁?嚗?50MA嚗?)
    elif b240 < -20:
        lines.append(f'????隡唳??僑蝺?銋{abs(b240):.0f}%嚗?-20%嚗?'
                     '蝑1嚗椰?游?撅?雿單?璈???脣嚗?008/2020璅∪?嚗?)

    # ?? ?皜Ⅳ璇辣 ?????????????????????????????????????????
    if b240 > 25 and b20 > 10:
        lines.append('?? ???寞?蝣潦僑蝺???25% + ??銋>10%???嚗?
                     '撱箄降??50%?其?嚗擗?5MA???)

    # ?? 蝯???閫貊 ?????????????????????????????????????????
    if score < 60 and '蝛粹' in trend:
        lines.append('?? ??撠??郎蝷箝???閰?<60 + 蝛粹??嚗??望?憭勗?箏??
                     '?箸?敺???蝑?閰???60隞乩??????)

    # ?? 357隡啣潭?蝷??????????????????????????????????????????
    if '靘踹?' in val:
        lines.append('?? ??57隡啣潦???%畾??隞乩?嚗噶摰?嚗?蝑1隤???鞎琿?憿?)
    elif '?眼' in val or '頞眼' in val:
        lines.append('?? ??57隡啣潦???%畾??隞乩?嚗?鞎游?嚗?銝?餈賡?嚗?敺?隤踴?)

    if not lines:
        lines.append('???桀??⊥?憿航眺鞈????撱箄降蝜潛?閫撖?)

    return '\n'.join(f'??{_ln}' for _ln in lines)

# ?? kpi / teacher_conclusion / signal_box 撌脫??ui_widgets.py ??

# ????????????????????????????????????????????????????????????????
# ?亙熒摨血??賊＊蝷箏?隞?
# ????????????????????????????????????????????????????????????????
def render_health_score(score, details, sid='', fund_scores=None, tech_alerts=None):
    """??亥那 v2嚗VG?” + ?雁閰? + ?銵郎蝷?+ ??璇耦??""
    grade, color, css_class, emoji = health_grade(score)
    import math as _mh

    # ??SVG ???”
    angle = (-180 + score * 1.8) * _mh.pi / 180
    cx, cy, r = 100, 90, 70
    nx = cx + r * _mh.cos(angle)
    ny = cy + r * _mh.sin(angle)
    gauge = (
        '<div style="text-align:center;padding:4px 0;">'
        '<svg viewBox="0 0 200 110" style="width:175px;height:92px;">'
        '<path d="M20,90 A80,80 0 0,1 60,22" stroke="#4c1d95" stroke-width="14" fill="none" stroke-linecap="round"/>'
        '<path d="M60,22 A80,80 0 0,1 100,10" stroke="#1e3a5f" stroke-width="14" fill="none" stroke-linecap="round"/>'
        '<path d="M100,10 A80,80 0 0,1 140,22" stroke="#1a4a1a" stroke-width="14" fill="none" stroke-linecap="round"/>'
        '<path d="M140,22 A80,80 0 0,1 180,90" stroke="#3d2000" stroke-width="14" fill="none" stroke-linecap="round"/>'
        f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
        f'<circle cx="{cx}" cy="{cy}" r="5" fill="{color}"/>'
        '<text x="14" y="103" fill="#8b949e" font-size="8">瘜冽?</text>'
        '<text x="48" y="18" fill="#8b949e" font-size="8">頛榆</text>'
        '<text x="88" y="8" fill="#8b949e" font-size="8">?桅?/text>'
        '<text x="127" y="18" fill="#8b949e" font-size="8">?臬末</text>'
        f'<text x="100" y="82" text-anchor="middle" fill="{color}" font-size="26" font-weight="900">{score}</text>'
        f'<text x="100" y="97" text-anchor="middle" fill="{color}" font-size="10">{grade}</text>'
        '</svg></div>'
    )

    # ???雁閰?
    fund_html = ''
    if fund_scores:
        _cat_ic = {'profit':'?','growth':'??','dividend':'??','valuation':'??'}
        _sc_cl  = {0:'#8b949e',1:TRAFFIC_YELLOW,2:TRAFFIC_GREEN,3:'#2ea043'}
        fund_html = '<div style="display:flex;gap:4px;margin:10px 0;">'
        for cat in ['profit','growth','dividend','valuation']:
            fs  = fund_scores.get(cat,{})
            sc  = fs.get('score',0)
            lb  = fs.get('label',cat)
            ic=_cat_ic.get(cat,'')
            cl  = _sc_cl.get(min(sc,3),'#8b949e')
            chk = ''
            for cn,cv,cp in fs.get('checks',[])[:3]:
                cc = TRAFFIC_GREEN if cp else TRAFFIC_RED
                chk += f'<div style="font-size:9px;color:{cc};margin-top:1px;">{"?? if cp else "??} {cn}</div>'
            fund_html += (
                f'<div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:7px 4px;text-align:center;">'
                f'<div style="font-size:20px;font-weight:900;color:{cl};">{sc}</div>'
                f'<div style="font-size:9px;color:#8b949e;">{ic} {lb}</div>'
                f'{chk}</div>'
            )
        fund_html += '</div>'

    # ???銵郎蝷?
    tech_html = ''
    if tech_alerts:
        _pc = {'?':TRAFFIC_RED,'?':TRAFFIC_YELLOW,'?':TRAFFIC_GREEN}
        tech_html = '<div style="margin:8px 0;"><div style="font-size:11px;color:#8b949e;margin-bottom:4px;">???銵郎蝷?/div>'
        for pri,name,sig,desc in tech_alerts[:5]:
            bc = _pc.get(pri,'#484f58')
            sc2 = TRAFFIC_RED if any(k in sig for k in ['??','蝛粹','頞都']) else (TRAFFIC_GREEN if any(k in sig for k in ['?撞','憭']) else TRAFFIC_YELLOW)
            tech_html += (
                f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0;background:#0d1117;border-left:3px solid {bc};padding:4px 8px;border-radius:0 4px 4px 0;">'
                f'<span style="font-size:10px;">{pri}</span>'
                f'<div style="flex:1;">'
                f'<span style="font-size:11px;font-weight:700;color:#c9d1d9;">{name}</span>'
                f'<span style="font-size:9px;background:{sc2}33;color:{sc2};padding:1px 4px;border-radius:3px;margin-left:5px;">{sig}</span>'
                f'<div style="font-size:9px;color:#8b949e;">{desc}</div>'
                f'</div></div>'
            )
        tech_html += '</div>'

    # ????璇耦??
    breakdown = '<div style="margin-top:8px;">'
    for factor, (desc, got, total) in details.items():
        pct = got / total * 100
        bc  = TRAFFIC_GREEN if pct>=70 else (TRAFFIC_YELLOW if pct>=40 else TRAFFIC_RED)
        breakdown += (
            f'<div style="display:flex;align-items:center;gap:6px;margin:2px 0;">'
            f'<div style="width:45px;font-size:10px;color:#8b949e;text-align:right;">{factor}</div>'
            f'<div style="flex:1;background:#21262d;border-radius:4px;height:7px;">'
            f'<div style="width:{pct:.0f}%;background:{bc};border-radius:4px;height:7px;"></div></div>'
            f'<div style="width:85px;font-size:9px;color:{bc};">{got}/{total} {desc[:8]}</div>'
            f'</div>'
        )
    breakdown += '</div>'
    return gauge + fund_html + tech_html + breakdown


primary_stock = '2330'

# ?? Sidebar: ?游? AI ?? ???????????????????????????????????????
with st.sidebar:
    st.markdown('<div style="text-align:center;padding:8px 0;font-size:15px;font-weight:900;color:#e6edf3;">&#128202; ?啗AI?唳?摰?v3.0</div>', unsafe_allow_html=True)
    st.markdown('---')
    _today_sb = datetime.date.today()
    _wd_sb = {0:'銝',1:'鈭?,2:'銝?,3:'??,4:'鈭?,5:'??,6:'??}[_today_sb.weekday()]
    _trade_sb = '??鈭斗??? if _today_sb.weekday() < 5 else '???漱?'
    st.caption(f'{_today_sb.strftime("%Y/%m/%d")} ?惋_wd_sb}  {_trade_sb}')
    st.markdown('---')
    st.markdown('### ?? AI ??')
    st.caption('?摨??AI ?游??勗??Ｘ')
    ai_run = False  # AI button moved to bottom panel
    st.markdown('---')
    st.success('? 蝟餌絞甇?虜??銝?)

    # ?? Google 撣唾?嚗Auth嚗?ETF 蝯??脩垢摮????????????????????
    st.markdown('---')
    st.markdown('### ?? Google 撣唾?')
    try:
        from oauth_state import (
            get_oauth_cfg as _sb_get_cfg,
            _gsa_secret as _sb_gsa,
            _sheet_id_secret as _sb_sid,
        )
        from infra.oauth import build_authorize_url as _sb_buildurl
        # 瘥活 rerun ??閫??嚗??module-level cache ??
        _sb_cfg = _sb_get_cfg()
        _sb_oc = _sb_cfg is not None
    except Exception:
        _sb_oc, _sb_cfg, _sb_gsa, _sb_sid, _sb_buildurl = False, None, None, '', None
    _sb_logged = bool(st.session_state.get('gsheet_tokens'))
    if _sb_oc:
        if _sb_logged:
            st.success('? 撌脩??)
            if st.button('? ?餃', key='btn_oauth_logout_sb',
                          use_container_width=True):
                st.session_state.pop('gsheet_tokens', None)
                st.rerun()
            # ?? Google Sheet ID嚗?銝剜撣唾??嚗TF 蝯??Ｘ?臬? Drive ?/?啣遣嚗??
            _sb_sid_cur = str(st.session_state.get('portfolio_sheet_id', '') or '').strip()
            _sb_sid_raw = st.text_input(
                'Google Sheet ID ????URL嚗頂蝯望??芸?閫?? ID嚗?,
                value=_sb_sid_cur, key='sb_portfolio_sheet_id_input',
                placeholder='鞎潔? https://docs.google.com/spreadsheets/d/...',
                help='鞎?URL/ID 閮剖???鞈?摨恬???TF 蝯??ab 敺?Drive ? / 銝?菜撱?)
            _sb_m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', _sb_sid_raw)
            _sb_sid_new = _sb_m.group(1) if _sb_m else _sb_sid_raw.strip()
            if _sb_sid_new and _sb_sid_new != _sb_sid_cur:
                st.session_state['portfolio_sheet_id'] = _sb_sid_new
            if _sb_sid_new:
                st.caption(f'??Sheet ID嚗{_sb_sid_new}`')
            else:
                st.caption('? ?芾身摰???鞎潔? URL/ID ??TF 蝯??ab ?')
        elif _sb_buildurl and _sb_cfg:
            _sb_url = _sb_buildurl(_sb_cfg['client_id'], _sb_cfg['redirect_uri'])
            st.link_button('?? ??Google ?餃', _sb_url, use_container_width=True)
            st.caption('?餃敺?ETF 蝯? Tab ?舫蝡臬???)
    elif _sb_gsa and _sb_sid:
        st.caption('?對? 雿輻 Service Account嚗??蝵莎?')
    else:
        st.caption('?? OAuth 撠閮剖? ???喋TF 蝯??ab 撅?????脩垢?脣??身摰?)

    st.markdown('---')
    st.markdown('### ?? ??????)
    # [Fixed] ??line 73-74 撠?嚗t.secrets ?芸?嚗s.environ fallback
    _fm_tok  = str(st.secrets.get('FINMIND_TOKEN',  os.environ.get('FINMIND_TOKEN',  '')))
    # Gemini ?寧??湔? key嚗EMINI_API_KEY + _2~_6嚗?隞颱???閮剖停蝞?
    _gm_keys  = _gemini_keys()
    _gm_slots = [_n for _n in _GEMINI_KEY_NAMES
                 if str(st.secrets.get(_n, '') or os.environ.get(_n, '') or '').strip()]
    _px_host = str(st.secrets.get('PROXY_HOST',     os.environ.get('PROXY_HOST',     '')))
    # PROXY_URL ??PROXY_HOST 鈭?銝?喳鈭???
    if not _px_host:
        _px_host = str(st.secrets.get('PROXY_URL', os.environ.get('PROXY_URL', '')))
    _sb_c1, _sb_c2, _sb_c3 = st.columns(3)
    with _sb_c1:
        if _fm_tok:
            st.success('FinMind ??)
        else:
            st.error('FinMind ??)
    with _sb_c2:
        if _gm_keys:
            st.success(f'Gemini ???{len(_gm_keys)}')
        else:
            st.error('Gemini ??)
    with _sb_c3:
        if _px_host:
            st.success('Proxy ??)
        else:
            st.warning('Proxy ??)
    # Gemini ?瘙皜祆?蝝堆??蝣箄?憭董??key ???◤霈?堆?
    if _gm_slots:
        st.caption('?? ?菜葫??Gemini ?嚗? + '??.join(_gm_slots))
    else:
        st.caption('?? ?芸皜砍隞颱? Gemini ?嚗?蝣箄? Secrets ??'
                   'GEMINI_API_KEY ??GEMINI_API_KEY_2~_6 ??蝔梯??潘?')
    if _px_host:
        _px_port = str(st.secrets.get('PROXY_PORT', os.environ.get('PROXY_PORT', '')))
        st.caption(f'?? {_px_host}:{_px_port}' if _px_port else '?? PROXY_URL 撌脰身摰?)
        st.caption('? 閰喟敦閮箸隢????鞈?閮箸?ab ??API Key 閮箸?Ｘ')
    if st.button('?? 皜祈岫???', key='sb_conn_test', use_container_width=True):
        import requests as _rq_sb
        import urllib3 as _ul3
        _ul3.disable_warnings(_ul3.exceptions.InsecureRequestWarning)
        _test_targets = [
            ('FinMind', 'https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo&stock_id=2330&date=2024-01-01', False),
            ('TWSE',    'https://openapi.twse.com.tw/v1/opendata/t187ap03_L', True),
            ('Yahoo',   'https://query1.finance.yahoo.com/v8/finance/chart/2330.TW?range=1d&interval=1d', False),
        ]
        _conn_res = []
        for _tn, _tu, _skip_ssl in _test_targets:
            try:
                _tr = _rq_sb.get(_tu, timeout=6, verify=not _skip_ssl,
                                  headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
                _conn_res.append((_tn, _tr.status_code, _tr.status_code < 400))
            except Exception as _te:
                _conn_res.append((_tn, type(_te).__name__, False))
        st.session_state['_sb_conn_results'] = _conn_res
    for _rn, _rc, _rok in st.session_state.get('_sb_conn_results', []):
        if _rok:
            st.success(f'??{_rn} ?舫?嚗TTP {_rc}')
        else:
            st.error(f'??{_rn} 憭望?嚗_rc}')

    st.markdown('---')
    st.caption('?? ??摮貉??弦嚗???撱箄降嚗??扯鞎?)

# v3.0 RENDER FUNCTIONS (禮9.3)
# ????????????????????????????????????????????????????????????????

# ?? ???閮?嚗?銝?MA20/MA60/MA120/MA240 ?振?豢?靘???????
def calc_jingqi(scan_results):
    """
    ?喳 Tab5 ??蝯? list嚗?蝞?????
    scan_results: [{隞?Ⅳ, 頞典, ?亙熒摨? ...}, ...]
    """
    if not scan_results:
        return {}
    total = len(scan_results)
    # P4靽格迤嚗??雁摨衣絞銝?具摨瑕漲?瑼颯?銝阡?銝??牧??
    # pct20 = ?亙熒摨?=40嚗?砍摨瘀??航?撖?
    # pct60 = ?亙熒摨?=60嚗葉蝑撥?ｇ?
    # pct120= ?亙熒摨?=70嚗撥?ｇ?
    # pct240= ?亙熒摨?=80嚗鞈芸撥?ｇ?
    above_ma20  = sum(1 for r in scan_results if r.get('?亙熒摨?,0) >= 40)
    above_ma60  = sum(1 for r in scan_results if r.get('?亙熒摨?,0) >= 60)
    above_ma120 = sum(1 for r in scan_results if r.get('?亙熒摨?,0) >= 70)
    above_ma240 = sum(1 for r in scan_results if r.get('?亙熒摨?,0) >= 80)
    pct20  = round(above_ma20  / total * 100, 1) if total else 0
    pct60  = round(above_ma60  / total * 100, 1) if total else 0
    pct120 = round(above_ma120 / total * 100, 1) if total else 0
    pct240 = round(above_ma240 / total * 100, 1) if total else 0
    avg    = round((pct20+pct60+pct120+pct240)/4, 1)

    # ????撱箄降嚗??箇??伐?
    if avg >= 60:
        pos = '80~100%'
        regime = 'bull'
        color = TRAFFIC_GREEN
        label = '? 憭蝛扔'
    elif avg >= 40:
        pos = '50~70%'
        regime = 'neutral'
        color = TRAFFIC_YELLOW
        label = '? 銝剜批?銵?
    elif avg >= 20:
        pos = '20~40%'
        regime = 'caution'
        color = TRAFFIC_RED
        label = '?? 靽??脩戌'
    else:
        pos = '0~20%'
        regime = 'bear'
        color = '#c00000'
        label = '? 璆萄漲靽?'

    return {
        'pct20':pct20,'pct60':pct60,'pct120':pct120,'pct240':pct240,
        'avg':avg,'pos':pos,'regime':regime,'color':color,'label':label,
        'total':total
    }

def render_market_overview(market_info: dict):
    """擐?撣?? (禮9.2)"""
    if not market_info:
        st.warning('?? ?⊥???憭抒?豢?')
        return
    regime   = market_info.get('regime', 'neutral')
    label    = market_info.get('label', '?')
    score    = market_info.get('score', 0)
    mx       = market_info.get('max_score', 4)
    idx      = market_info.get('index_price', 0)
    exposure = market_info.get('exposure_pct', '50%')
    signals  = market_info.get('signals', [])
    color_map = {'bull': TRAFFIC_GREEN, 'neutral': TRAFFIC_YELLOW, 'bear': TRAFFIC_RED}
    bg_map    = {'bull': '#0d2818', 'neutral': '#2a1f00', 'bear': '#2a0d0d'}
    color = color_map.get(regime, '#8b949e')
    bg    = bg_map.get(regime, '#161b22')
    st.markdown(f"""
<div style="background:{bg};border:2px solid {color};border-radius:12px;padding:16px 20px;margin-bottom:12px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div>
      <span style="font-size:22px;font-weight:900;color:{color};">{label}</span>
      <span style="font-size:13px;color:#8b949e;margin-left:10px;">閰? {score}/{mx} 嚚?憭抒 {idx:,.0f}</span>
    </div>
    <div style="text-align:right;">
      <span style="font-size:15px;color:#e6edf3;">撱箄降? <b style="color:{color};">{exposure}</b></span>
    </div>
  </div>
  <div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;">
    {"".join('<span style="background:#161b22;border-radius:6px;padding:3px 8px;font-size:12px;color:#e6edf3;">' + str(s) + '</span>' for s in signals)}
  </div>
</div>""", unsafe_allow_html=True)

def render_top_rankings(results: list, top_n: int = 10):
    """?∠巨閰???璁?(禮9.1)"""
    if not results:
        st.info('撠閰?鞈?')
        return
    from scoring_engine import rank_stocks as _rank
    ranked = _rank(results)[:top_n]
    if not ranked:
        st.info('撠??閰?鞈?')
        return
    rows = []
    for i, r in enumerate(ranked):
        rows.append({
            '??': i + 1, '隞?Ⅳ': r.get('stock_id', ''), '?迂': r.get('stock_name', ''),
            '蝮賢?': f"{r.get('total', 0):.1f}", '頞典': f"{r.get('trend', 0):.0f}",
            '?': f"{r.get('momentum', 0):.0f}", '蝐Ⅳ': f"{r.get('chip', 0):.0f}",
            '?': f"{r.get('volume', 0):.0f}", '憸券': f"{r.get('risk', 0):.0f}",
            '閰?': r.get('grade', '-'), '?閮?': '?? if r.get('momentum_signal') else '?',
        })
    df_rank = pd.DataFrame(rows)
    st.dataframe(df_rank, use_container_width=True, hide_index=True,
                 column_config={'蝮賢?': st.column_config.ProgressColumn('蝮賢?', min_value=0, max_value=100, format='%.1f')})

# ????????????????????????????????????????????????????????????????
# TABS: 3 銝駁?蝐?
# ????????????????????????????????????????????????????????????????
# ?? Sidebar ????????????????????
with st.sidebar:
    st.markdown('<div style="text-align:center;padding:8px 0;font-size:15px;font-weight:900;color:#e6edf3;">&#128202; ?啗AI?唳?摰?v3.0</div>', unsafe_allow_html=True)
    st.markdown('---')
    _today_sb = datetime.date.today()
    _wd_sb = {0:'銝',1:'鈭?,2:'銝?,3:'??,4:'鈭?,5:'??,6:'??}[_today_sb.weekday()]
    _trade_sb = '??鈭斗??? if _today_sb.weekday() < 5 else '???漱?'
    st.caption(f'{_today_sb.strftime("%Y/%m/%d")} ?惋_wd_sb}  {_trade_sb}')
    st.markdown('---')
    if st.button('?? 撘瑕?瑟?豢?', key='_sb_force_refresh', use_container_width=True,
                 help='皜??翰?蒂?????啗???):
        st.cache_data.clear()
        st.rerun()
    st.markdown('---')

    # ?? v18.203 F2嚗撅鞈??亙熒蝮質汗嚗???剜? + 蝮賜?蝢 ??銝?潛??芾?嚗??
    try:
        from sidebar_health import render_sidebar_data_health
        render_sidebar_data_health(st.session_state)
    except Exception as _e_sbh:
        print(f'[sidebar_health] {type(_e_sbh).__name__}: {_e_sbh}')
    st.markdown('---')

# 銝餅?憿?
st.markdown(
    '<div style="display:flex;align-items:center;gap:10px;padding:4px 0 8px;">'    '<span style="font-size:22px;font-weight:900;color:#e6edf3;">&#128202; ?啗 AI ?唳?摰?/span>'    '<span style="font-size:10px;color:#484f58;background:#161b22;border-radius:10px;padding:2px 8px;">v4.0 Pro</span>'    '</div>',
    unsafe_allow_html=True)

# ??????????????????????????????????????????????????????
# ?妣 蝮賜?????(Top-Down Macro) ??Phase 1 閬?銝之蝢??
# ??????????????????????????????????????????????????????
def _render_compass_card(col, info, title, ticker, fmt='{:.2f}', unit='', show_ma=False):
    """?桀撐???∴???+ Phase 1 閮???+ 60D sparkline?nfo=None 憿舐內??閮??""
    if info is None:
        col.markdown(
            f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:10px;height:84px;">'
            f'<div style="font-size:11px;color:#8b949e;">{title}嚗ticker}嚗?/div>'
            f'<div style="font-size:13px;color:#8b949e;margin-top:6px;">? ?芸?敺?yfinance ?急?憭望?嚗?/div>'
            f'</div>', unsafe_allow_html=True)
        return
    val = info.get('value')
    sig = info.get('signal') or ('??, '?∟???, '#8b949e')
    light, label, color = sig[0], sig[1], sig[2]
    val_str = fmt.format(val) + unit if val is not None else 'N/A'
    extra = ''
    if show_ma and info.get('ma60') is not None:
        extra = f' <span style="font-size:10px;color:#8b949e;font-weight:400;">/ 60MA {fmt.format(info["ma60"])}</span>'
    col.markdown(
        f'<div style="background:#0d1117;border:1px solid {color};border-radius:8px;padding:10px;">'
        f'<div style="font-size:11px;color:#8b949e;">{title}嚗ticker}嚗?/div>'
        f'<div style="font-size:22px;font-weight:900;color:#e6edf3;margin:2px 0;">{val_str}{extra}</div>'
        f'<div style="font-size:11px;font-weight:700;color:{color};">{light} {label}</div>'
        f'</div>', unsafe_allow_html=True)
    ser = info.get('series') or []
    if ser:
        try:
            import pandas as _pd_mc
            col.line_chart(_pd_mc.Series(ser, name=title), height=80, use_container_width=True)
        except Exception:
            pass

def render_macro_compass():
    """?銝嚗IX ??? ? 蝢?10Y 畾??? S&P 500 vs 60MA??
    ?身銝?鞈?嚗?＊蝷粹??潸炊?歹?嚗????????啜?????yfinance??""
    import datetime as _dt_mc

    def _do_fetch():
        try:
            from macro_core import fetch_macro_compass as _fmc
            _data = _fmc()
        except Exception as e:
            print(f'[render_macro_compass] fetch failed: {e}')
            _data = {}
        st.session_state['_macro_compass_cache'] = {
            '_ts': _dt_mc.datetime.now(), 'data': _data,
        }

    _cache = st.session_state.get('_macro_compass_cache')
    _has_data = bool(_cache and _cache.get('data'))
    _ts_str = (_cache.get('_ts').strftime('%H:%M:%S')
               if _has_data and _cache.get('_ts') else '撠??')

    _header = st.columns([6, 1])
    _header[0].markdown(
        '<div style="font-size:14px;font-weight:900;color:#e6edf3;margin:4px 0 4px;">'
        '?妣 蝮賜?????(Top-Down Macro)'
        '<span style="font-size:10px;color:#8b949e;font-weight:400;margin-left:8px;">'
        f'VIX ? 10Y ? S&amp;P 500 ??{"?喳???嚗敹怠?嚗? if not _has_data else f"?湔??{_ts_str}"}'
        '</span></div>',
        unsafe_allow_html=True)
    _header[1].button('? ????? if not _has_data else '?? ??',
                       key='_compass_fetch_btn', on_click=_do_fetch,
                       use_container_width=True)

    if not _has_data:
        st.info('? 暺??喃????????啜????亙??VIX / 10Y / S&P 500')
        return

    data = _cache.get('data') or {}
    c1, c2, c3 = st.columns(3)
    _render_compass_card(c1, data.get('vix'),  'VIX ???',     '^VIX',  fmt='{:.2f}')
    _render_compass_card(c2, data.get('tnx'),  '蝢?10Y 畾??,    '^TNX',  fmt='{:.2f}', unit='%')
    _render_compass_card(c3, data.get('gspc'), 'S&P 500 vs 60MA',  '^GSPC', fmt='{:,.2f}', show_ma=True)

render_macro_compass()

# v18.182 ARCHIVED: ?妒 ?葫?曉???Tab ?怠?摮?
# ?芯??嚗?1) tuple ?? tab_backtest ??tab_etf_margin 銋? tab_diag 銋?
# (2) labels ?? '?妒 ?葫?曉??? 撠?雿蔭 (3) ??銝 with tab_backtest ?憛酉閫?
# v18.187 ARCHIVED: ?? ???園脤 Tab ?怠?摮?FinMind batch endpoint 撌脖??舀?祥 tier嚗?
# ?芯??嚗?1) tuple ?? tab_rev_screener ??tab_screener 銋? tab_mj_diff 銋?
# (2) labels ?? '?? ???園脤' 撠?雿蔭 (3) ??銝 with tab_rev_screener ?憛酉閫?
# v18.189 ARCHIVED: ?? MJ 擃炎霈? Tab ?怠?摮???寞?????蝯??甈⊿?瑼Ｗ?憛??對?
# ?芯??嚗?1) tuple ?? tab_mj_diff ??tab_screener 銋? tab_etf 銋?
# (2) labels ?? '?? MJ 擃炎霈?' 撠?雿蔭 (3) ??銝 with tab_mj_diff ?憛酉閫?
tab_macro, tab_heatmap, tab_stock, tab_stock_grp, tab_screener, tab_etf, tab_etf_grp, tab_etf_margin, tab_diag, tab_edu = st.tabs([
    '?? 蝮賜?', '?儭??Ｘ平?勗???, '? ?', '?? ?蝯?',
    '?? 擃蝬?, '? ETF', '?? ETF蝯?', '? ETF鞈芸芋??, '?? 鞈?閮箸', '?? ?飛',
])

# ??????????????????????????????????????????????????????????????
# TAB 1: 蝮賡?蝬?
# ??????????????????????????????????????????????????????????????

# ?? ?典?憭征蝝??????垢嚗?????????????????????????????
_mkt_top  = st.session_state.get('mkt_info', {})
_jq_top   = st.session_state.get('jingqi_info', {})
_ts_top   = st.session_state.get('cl_ts', '')
if (_mkt_top or _jq_top) and not st.session_state.get('_is_refreshing', False):
    _reg   = _mkt_top.get('regime', 'neutral')
    _jqpct = _jq_top.get('avg', 50) if _jq_top else None
    # 蝬?靽∟?
    _gl_color, _gl_label = traffic_light(
        None,
        _reg == 'bull' and (_jqpct is None or _jqpct >= 40),
        _reg == 'bear' or (_jqpct is not None and _jqpct < 20),
        '憭撣嚗蝛扔??嚗?, '蝛粹撣嚗?閫??摰?', '? ??渡?嚗牲??雿?'
    )
    _gl_pos = _mkt_top.get('exposure_pct', '80%' if _reg=='bull' else ('20%' if _reg=='bear' else '50%'))

    st.markdown(
        f'<div style="background:#0d1117;border:1px solid {_gl_color};border-radius:8px;'
        f'padding:8px 14px;margin-bottom:8px;display:flex;align-items:center;gap:16px;">'
        f'<span style="font-size:16px;font-weight:900;color:{_gl_color};">{_gl_label}</span>'
        f'<span style="font-size:12px;color:#c9d1d9;">撱箄降? <b>{_gl_pos}</b></span>'
        + (f'<span style="font-size:12px;color:#8b949e;">????{_jqpct:.0f}%</span>'
           if _jqpct is not None else '') +
        f'<span style="font-size:11px;color:#484f58;margin-left:auto;">?湔嚗_ts_top}</span>'
        f'</div>', unsafe_allow_html=True)

# ??????????????????????????????????????????????????????????????
# AI 蝮賜??唳? ???啗??? + LLM ? 撌亙?賣
# ??????????????????????????????????????????????????????????????

@st.cache_data(ttl=CACHE_TTL["financial_data"], show_spinner=False, max_entries=10)
def _fetch_macro_news(n: int = 5) -> list:
    """???函?蝮賜?鞎∠??啗? ??銝剛??憭?嚗頂蝯望折◢?芸皜祉嚗?
    靘?嚗NYES?漕 / 蝬??亙 / Google News(銝? / Google News(?? /
          Yahoo Finance / Reuters Biz / CNBC Economy / Bloomberg Markets
    蝑嚗?皞?憭? 3 ?????冽??駁?嚗?璅?嚗? 銝?????嚗??RSS ??published嚗?
          ?～?皞?round-robin?毽??綽?蝣箔?銝剛靘??質◤蝝 AI ?方???
    ttl=1800嚗? 30 ???芸??湔銝甈∪翰??
    """
    try:
        import feedparser as _fp
        import html as _h
        import re as _re2
    except ImportError:
        print('[AI-News] ?? feedparser ?芸?鋆?頝喲??啗???')
        return []
    try:
        from proxy_helper import fetch_url as _furl_news
    except ImportError:
        _furl_news = None

    # 銝剜??芸?嚗?啁頂蝯望折◢?芾圾霈嚗??望?鋆撥嚗?憭拚????郊嚗?
    _feeds = [
        ('?漕蝬?,       'https://www.cnyes.com/rss/cat/headline'),
        ('蝬??亙',     'https://money.udn.com/rssfeed/news/1001/5589/12017?ch=money'),
        ('Google銝剜?',   'https://news.google.com/rss/search'
                         '?q=%E5%8F%B0%E8%82%A1+%E8%81%AF%E6%BA%96%E6%9C%83+%E5%88%A9%E7%8E%87+%E5%B9%B3%E5%84%B9'
                         '&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'),
        ('Google?望?',   'https://news.google.com/rss/search'
                         '?q=stock+market+economy+fed+interest+rate'
                         '&hl=en-US&gl=US&ceid=US:en'),
        ('Yahoo Finance','https://finance.yahoo.com/news/rssindex'),
        ('Reuters Biz',  'https://feeds.reuters.com/reuters/businessNews'),
        ('CNBC Economy', 'https://search.cnbc.com/rs/search/combinedcms/view.xml'
                         '?partnerId=wrss01&id=20910258'),
        ('Bloomberg',    'https://feeds.bloomberg.com/markets/news.rss'),
    ]
    _per_src = 3  # 瘥?銝?嚗?銝靘?瘣?
    _by_src: dict[str, list] = {}
    for _src, _url in _feeds:
        _by_src[_src] = []
        try:
            # 韏?NAS Squid proxy ??RSS ??嚗treamlit Cloud IP 憭◤ RSS 靘?撠?嚗?
            _fd = None
            if _furl_news is not None:
                _r_rss = _furl_news(_url, timeout=10)
                if _r_rss is not None:
                    _fd = _fp.parse(_r_rss.content)  # 擗?bytes嚗??str+encoding 摰??鋡?feedparser ?圾??
            if _fd is None or not getattr(_fd, 'entries', None):
                # ???湧??proxy 憭望???
                _fd = _fp.parse(_url)
            for _e in _fd.entries:
                _title = _h.unescape(_e.get('title', '')).strip()
                _summ  = _h.unescape(_e.get('summary', _e.get('description', ''))).strip()
                _summ  = _re2.sub(r'<[^>]+>', '', _summ)[:300].strip()
                _pub   = str(_e.get('published', ''))[:16]
                if _title:
                    _by_src[_src].append({'title': _title, 'summary': _summ,
                                          'source': _src, 'published': _pub})
                if len(_by_src[_src]) >= _per_src:
                    break
            print(f'[AI-News/{_src}] ??{len(_by_src[_src])} ??)
        except Exception as _ne:
            print(f'[AI-News/{_src}] ??{_ne}')

    # round-robin 瘛瑕???嚗?摨??
    _seen: set[str] = set()
    _out: list = []
    _max_round = max((len(v) for v in _by_src.values()), default=0)
    for _i in range(_max_round):
        for _src, _items in _by_src.items():
            if _i < len(_items):
                _t = _items[_i]['title']
                if _t and _t not in _seen:
                    _seen.add(_t)
                    _out.append(_items[_i])
                    if len(_out) >= n:
                        return _out
    return _out[:n]


def _rss_items_from_bytes(_content) -> list:
    """敺?RSS bytes ??item嚗eedparser 銝颯lementTree ?嚗???feedparser 撠?
    ??encoding 摰?? / ?寞??賢?蝛粹? RSS ?芰?嚗???dict list??""
    if not _content:
        return []
    _cb = _content if isinstance(_content, bytes) else str(_content).encode('utf-8', 'ignore')
    try:
        import feedparser as _fp2
        _e = list(getattr(_fp2.parse(_cb), 'entries', []) or [])
        if _e:
            return _e
    except Exception:
        pass
    if b'<item' not in _cb:
        return []
    try:
        import xml.etree.ElementTree as _ET
        import email.utils as _eu
        _items = []
        for _it in _ET.fromstring(_cb).iter('item'):
            _title = (_it.findtext('title') or '').strip()
            if not _title:
                continue
            _pub = (_it.findtext('pubDate') or '').strip()
            _items.append({'title': _title, 'link': (_it.findtext('link') or '').strip(),
                           'summary': (_it.findtext('description') or '').strip(),
                           'published': _pub, 'published_parsed': _eu.parsedate(_pub) if _pub else None})
        return _items
    except Exception:
        return []


def _fetch_stock_news(stock_id: str, stock_name: str = "", n: int = 5, recency: str = "", _diag=None) -> list:
    """????賊??啗?嚗oogle News RSS 銝剛????嚗仃???蝛箔葡??
    ?? NAS Squid proxy 頝舐嚗treamlit Cloud IP ?◤ Google News RSS ??撠?嚗?
    recency嚗oogle News ????摮?憒?'6m' 餈?撟?/ '7d'嚗?蝛箏?銝?銝???
    瘥???link ??摨 _ts嚗蒂靘撣????????
    _diag嚗??list ??feed 閮??????proxy/?湧?繚 HTTP 繚 entries 繚 ?航炊嚗? UI 閮箸??
    """
    try:
        import feedparser as _fp
        import html as _h
        import re as _re2
        import time as _time_sn
        from urllib.parse import quote as _uq
    except ImportError:
        if _diag is not None:
            _diag.append('feedparser/urllib ?臬憭望?')
        return []
    try:
        from proxy_helper import fetch_url as _furl_sn, nas_relay_fetch as _nas_rf
    except ImportError:
        _furl_sn = None
        _nas_rf = None
        if _diag is not None:
            _diag.append('proxy_helper ?芾???????湧???脩垢??403嚗?)
    # 銝 Google News `when:` ??摮?RSS 銝帘?虜?征 channel嚗??孵??身餈???
    _q_tw = f"{stock_id} {stock_name}".strip()
    _q_en = f"Taiwan stock {stock_id} {stock_name}".strip()
    _feeds = [
        ('Google?啗?(銝剜?)', f'https://news.google.com/rss/search?q={_uq(_q_tw)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant'),
        ('Google?啗?(?望?)', f'https://news.google.com/rss/search?q={_uq(_q_en)}&hl=en-US&gl=US&ceid=US:en'),
    ]
    _news_hdr = {
        'Cookie': 'CONSENT=YES+cb; SOCS=CAI',  # 蝜? Google ????靽嚗?
        'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5',
    }
    _out = []
    for _src, _url in _feeds:
        _via = ''
        _content = None
        try:
            # 頝臬???NAS FastAPI 銝剔匱蝡?摰嗥?啁 IP嚗?
            if _nas_rf is not None:
                _rr = _nas_rf(_url, timeout=15)
                if _rr is not None:
                    _content = _rr.content
                    _via = f'NAS銝剔匱 HTTP {getattr(_rr, "status_code", "?")}'
                else:
                    _via = 'NAS銝剔匱?芾身摰?憭望?'
            # 頝臬??∴?Squid proxy
            if not _content and _furl_sn is not None:
                _rs = _furl_sn(_url, headers=_news_hdr, timeout=10)
                if _rs is not None:
                    _content = _rs.content
                    _via += f' | Squid HTTP {getattr(_rs, "status_code", "?")}'
                else:
                    _via += ' | Squid?one'
            # 閫??嚗eedparser ??ElementTree ?嚗今 bytes嚗?
            _items = _rss_items_from_bytes(_content)
            # 頝臬??ｇ??湧???頝臬??賣? item ?岫嚗蝡舀???IP 憭?403嚗?
            if not _items:
                try:
                    _items = list(getattr(_fp.parse(_url, request_headers=_news_hdr), 'entries', []) or [])
                    _via += f' | ?湧ㄌlen(_items)}??
                except Exception:
                    _via += ' | ?湧?仃??
            _itag = _content.count(b'<item') if _content else 0
            _via += f'嚚tem璅惜={_itag}/閫??{len(_items)}??
            if not _items and _content:
                _via += f'嚚ody[:100]={_content[:100].decode("utf-8", "ignore").strip()!r}'
            for _e in _items:
                _title = _h.unescape(_e.get('title', '')).strip()
                _summ  = _h.unescape(_e.get('summary', _e.get('description', ''))).strip()
                _summ  = _re2.sub(r'<[^>]+>', '', _summ)[:150].strip()
                _pub   = str(_e.get('published', ''))[:16]
                _pp    = _e.get('published_parsed')
                try:
                    _ts = _time_sn.mktime(_pp) if _pp else 0.0
                except Exception:
                    _ts = 0.0
                if _title:
                    _out.append({'title': _title, 'summary': _summ, 'source': _src,
                                 'published': _pub, 'link': _e.get('link', ''), '_ts': _ts})
                if len(_out) >= n:
                    break
            if _diag is not None:
                _diag.append(f'{_src}: {_via} ????{len(_out)} ??)
            print(f'[StockNews/{_src}] ??{stock_id} 蝝航? {len(_out)} ??)
        except Exception as _ne:
            if _diag is not None:
                _diag.append(f'{_src}: ??{_via} {type(_ne).__name__}: {str(_ne)[:80]}')
            print(f'[StockNews/{_src}] ??{_ne}')
        if len(_out) >= n:
            break
    _out.sort(key=lambda _x: _x.get('_ts', 0.0), reverse=True)  # ?售???
    return _out[:n]


def _build_llm_context(macro_info: dict) -> str:
    """撠?session_state 銝剔???蝮賜??豢??澆??蝝?摮? LLM 雿輻"""
    _vix = macro_info.get('vix') or {}
    _exp = macro_info.get('tw_export') or {}
    _pmi = macro_info.get('ism_pmi') or {}
    _cpi = macro_info.get('us_core_cpi') or {}
    _ndc = macro_info.get('ndc_signal') or {}
    _mi  = st.session_state.get('m1b_m2_info') or {}
    _bi  = st.session_state.get('bias_info') or {}
    _lines = []
    if _vix.get('current'):
        _lines.append(f'??VIX ???嚗_vix["current"]} (MA20={_vix.get("ma20","N/A")})')
    if _exp.get('yoy') is not None:
        _lines.append(f'???啁憭閮 YoY嚗_exp["yoy"]:+.1f}%  ({_exp.get("date","")})')
    if _pmi.get('value') is not None:
        _lines.append(f'???? ?啁 PMI嚗_pmi["value"]}  ({_pmi.get("date","")}嚗?50 ?游撐)')
    if _cpi.get('yoy') is not None:
        _lines.append(f'??蝢??詨? CPI YoY嚗_cpi["yoy"]:+.1f}%  ({_cpi.get("date","")})')
    if _ndc.get('score') is not None:
        _lines.append(f'??NDC ?舀除???嚗_ndc["score"]:.0f}/45')
    if _mi.get('m1b_yoy') is not None and _mi.get('m2_yoy') is not None:
        _gap = round(float(_mi['m1b_yoy']) - float(_mi['m2_yoy']), 2)
        _lines.append(f'???啁 M1B={_mi["m1b_yoy"]:.1f}%  M2={_mi["m2_yoy"]:.1f}%  Gap={_gap:+.2f}%')
    if _bi.get('bias_240') is not None:
        _lines.append(f'???啗憭抒撟渡?銋??BIAS240嚗_bi["bias_240"]:+.1f}%')
    return '\n'.join(_lines) if _lines else '嚗?????乩葉嚗?????啁蜇蝬??'


def _run_llm_analysis(macro_info: dict, news: list) -> dict:
    """?澆 Gemini API ?脰?蝮賜??嚗??唾圾????dict??
    雿輻?Ｘ???gemini_call() ?賣嚗??2.5-flash-lite/2.5-flash/2.0-flash ?芸? fallback嚗?
    ?航炊????{'error': '...'}嚗??靘???
    """
    _macro_str = _build_llm_context(macro_info)
    _news_lines = []
    for i, _nw in enumerate(news, 1):
        _news_lines.append(f'{i}. [{_nw["source"]}] {_nw["title"]}')
        if _nw.get('summary'):
            _news_lines.append(f'   {_nw["summary"][:150]}')
    _news_str = '\n'.join(_news_lines) if _news_lines else '嚗瘜?敺??交??隢????豢??斗嚗?

    _prompt = (
        '雿銝雿恣???璅∠?鞈楛???粹?蝬?嚗???20 撟游?∟??函?摰???蝬???
        '隞餃?嚗???蜇蝬?璅??單?鞎∠??啗?嚗?啗??鈭箸?靘移蝣箇??啗????
        '???蝡雲?潭?靘??豢?鈭祕嚗?征瘜?餈啜n\n'
        f'????嚗_tw_now_str()}嚗????\n\n'
        f'## ?嗅???蝮賜??豢?\n{_macro_str}\n\n'
        f'## 隞??鞎∠??之?啗?\n{_news_str}\n\n'
        '## 頛詨?誘\n'
        '隢??餈唳???啗?嚗撓?箏?⊥?鞈??扎n'
        '閬?嚗? stock_pct + cash_pct = 100 ?????銝脣潔蝙?函?擃葉?n'
        '??risk_level嚗IX??0??憭批蝺?◢?芬?high嚗IX 20~30????edium嚗擗?low\n'
        '?芾撓??JSON嚗?閬遙雿牧??摮? markdown 璅?嚗n'
        '{\n'
        '  "sentiment": "璆萄漲??|霅行?|銝剜坑璅?|璆萄漲?",\n'
        '  "sentiment_reason": "撣???文??敹???15摮誑?改?",\n'
        '  "macro_reading": "?游??豢????蝮賜??暹?蝎曄?閫??嚗?0摮誑?改?",\n'
        '  "stock_pct": 撱箄降?瘞港??湔,\n'
        '  "cash_pct": 撱箄降?暸?瘞港??湔,\n'
        '  "action": "銝?亥店?琿????寥?嚗?嚗?5摮誑?改?",\n'
        '  "risk_level": "high|medium|low",\n'
        '  "key_risk": "?嗅??憭找?銵◢?迎?20摮誑?改?",\n'
        '  "opportunity": "?嗅??憭扳?鞈???20摮誑?改?"\n'
        '}'
    )

    _raw = gemini_call(_prompt, max_tokens=600)
    print(f'[AI-LLM/Gemini] raw={_raw[:120]}')
    if _raw.startswith('??'):
        return {'error': _raw}
    try:
        _match = re.search(r'\{[\s\S]*\}', _raw)
        if _match:
            _parsed = json.loads(_match.group())
            _s = int(_parsed.get('stock_pct', 50))
            _parsed['stock_pct'] = max(0, min(100, _s))
            _parsed['cash_pct']  = 100 - _parsed['stock_pct']
            return _parsed
        return {'error': f'JSON 閫??憭望?嚗?憪???{_raw[:100]}'}
    except Exception as _le:
        print(f'[AI-LLM/Gemini] ??{_le}')
        return {'error': str(_le)[:150]}




with tab_macro:
    render_tab_macro()




with tab_stock:
    render_tab_stock()


with tab_stock_grp:
    render_stock_grp()




with tab_edu:
    render_tab_edu()


# ??????????????????????????????????????????????????????????????
# TAB: ETF ?桐?瘛勗漲閮箸 + 憭??寞活閰?嚗18.223 摮???
# ??????????????????????????????????????????????????????????????
with tab_etf:
    _etf_sub_tabs = st.tabs(['?? ?格?瘛勗漲閮箸', '?? 憭?閰?瘥?'])
    with _etf_sub_tabs[0]:
        render_etf_single(gemini_fn=gemini_call)
    with _etf_sub_tabs[1]:
        from etf_tab_grp_compare import render_etf_grp_compare
        render_etf_grp_compare()

# ??????????????????????????????????????????????????????????????
# TAB: ETF 蝯??唳?摰歹?4 ?畾菜??蝯??蔭 + 甇瑕?葫 + AI + ?∟?銝莎?
# ??????????????????????????????????????????????????????????????
with tab_etf_grp:
    # ?? ??蝯??蔭??撟唾﹛嚗銝頛詨靘?嚗?皜豢芋蝯鈭?etf_portfolio_rows嚗??
    render_etf_portfolio(gemini_fn=gemini_call)
    st.markdown('<hr style="margin:32px 0;border-color:#30363d;">', unsafe_allow_html=True)

    # ?? ??甇瑕?葫嚗18.182 ARCHIVED ?怠?摮?璅∠? etf_tab_backtest.py 靽?蝤?嚗??
    # render_etf_backtest(gemini_fn=gemini_call)
    # st.markdown('<hr style="margin:32px 0;border-color:#30363d;">', unsafe_allow_html=True)

    # ?? ???∟?銝脤??舀?嚗?????∪????航?隡堆???
    render_grape_ladder(gemini_fn=gemini_call)
    st.markdown('<hr style="margin:32px 0;border-color:#30363d;">', unsafe_allow_html=True)

    # ?? ??AI 蝬?閰 + ?芰??嚗?頠詨?嚗?????孵?????
    render_etf_ai(gemini_fn=gemini_call)

# ??????????????????????????????????????????????????????????????
# TAB: ETF 鞈芸?摮??Ⅳ璅⊥??(v18.162)
# ??????????????????????????????????????????????????????????????
with tab_etf_margin:
    from tab_etf_margin_simulator import render_etf_margin_simulator
    render_etf_margin_simulator()

# ??????????????????????????????????????????????????????????????
# v18.182 ARCHIVED: ?妒 ?葫?曉???Tab ?怠?摮?
# 璅∠?瑼?tab_backtest_optimization.py + backtest_engine.py + tw_backtest.py 摰靽?蝤?
# ?芯??嚗?瘨???import (etf_dashboard) + tab tuple + 隞乩? with-block 閮餉圾?喳
# ??????????????????????????????????????????????????????????????
# with tab_backtest:
#     from tab_backtest_optimization import render_backtest_optimization_tab
#     render_backtest_optimization_tab()

# ??????????????????????????????????????????????????????????????
# TAB: 7% 擃??拍??脩戌蝬莎?Screener Mode嚗?
# ??????????????????????????????????????????????????????????????
with tab_screener:
    from yield_screener import render_yield_screener
    _picker_candidates = render_yield_screener()

    # ?? ? ?箸?貉嚗??挾瞈曄雯 + AI 銝?撱箄降嚗??亦?擃蝬脣皜 ??
    st.markdown('---')
    from tab_stock_picker import render_tab_stock_picker
    render_tab_stock_picker(gemini_fn=gemini_call, candidates=_picker_candidates)

# ??????????????????????????????????????????????????????????????
# TAB: ???園脤蝭拚嚗18.180嚗???v18.187 ARCHIVED
# FinMind TaiwanStockMonthRevenue batch endpoint (??data_id) 撌脖??舀?祥/sponsor tier
# 璅∠? monthly_revenue_screener.py 靽?蝤?嚗靘??剁???銝閮餉圾?喳
# ??????????????????????????????????????????????????????????????
# with tab_rev_screener:
#     from monthly_revenue_screener import render_monthly_revenue_screener
#     render_monthly_revenue_screener()

# ??????????????????????????????????????????????????????????????
# TAB: MJ 擃炎霈?嚗18.186 / v18.188 batch ?? ??v18.189 ARCHIVED
# ??寞?????蝯??甈⊿?瑼Ｗ?憛??嫘??MJ 頞典???憛?
# 璅∠? tab_mj_health_diff.py ??mj_trend_score.py 靽?蝤?嚗靘??剁???銝閮餉圾
# ??????????????????????????????????????????????????????????????
# with tab_mj_diff:
#     from tab_mj_health_diff import render_mj_health_diff_tab
#     render_mj_health_diff_tab()

# ??????????????????????????????????????????????????????????????
# TAB: 鞈?閮箸嚗aw Data only嚗?
# ??????????????????????????????????????????????????????????????
with tab_diag:
    render_api_diagnostic()
    st.markdown('---')
    render_data_health_raw()
    st.markdown('---')
    from calibration_ui import render_calibration_panel
    render_calibration_panel()

# ??????????????????????????????????????????????????????????????
# TAB: ?Ｘ平?勗???
# ??????????????????????????????????????????????????????????????
with tab_heatmap:
    render_sector_heatmap(gemini_fn=gemini_call)

st.markdown('<div style="text-align:center;font-size:10px;color:#484f58;padding:8px 0;">?? ?啗AI?唳?摰?v3.0 繚 ??摮貉??弦嚗???撱箄降嚗??扯鞎?/div>', unsafe_allow_html=True)

