from data_config import CACHE_TTL
"""
daily_checklist.py v6.0 ??Squid Proxy 璅∪?
?? 銝之瘜犖嚗WSE BFI82U via Squid Proxy嚗?憭拙?皞荔?row[3] 鞎瑁都頞???e8=??
?? ??擗?嚗? 畾萄?????rwd MI_MARGN ??HiStock ??Goodinfo ??Yahoo ???漕蝬莎?隞?繩100,000=??
?? ADL / yfinance / FinMind嚗???geo-block 敶梢嚗??
"""
import requests, pandas as pd, datetime, os, time, re
import urllib3
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ?? Proxy 摮暑敹怠?嚗芋蝯惜蝝?60s TTL嚗?誨?蝺??格????嚗??????????
_proxy_health: dict = {}  # {url: (is_alive, checked_at)}
_PROXY_TTL = 60

def _proxy_alive(url: str, timeout: float = 2.0) -> bool:
    """TCP 敹急葫隞???臬?舫?嚗??翰??60s??""
    import socket, time as _t
    from urllib.parse import urlparse
    now = _t.time()
    if url in _proxy_health:
        alive, ts = _proxy_health[url]
        if now - ts < _PROXY_TTL:
            return alive
    try:
        _p = urlparse(url)
        _h, _port = _p.hostname or 'localhost', _p.port or 3128
        with socket.create_connection((_h, _port), timeout=timeout):
            alive = True
    except Exception:
        alive = False
    _proxy_health[url] = (alive, now)
    if not alive:
        print(f'[Proxy] ?? {url} ?⊥????嚗頛芾歲?誨???)
    return alive

def _bps():
    try:
        from tw_stock_data_fetcher import build_proxy_session as _b
        s = _b()
    except Exception:
        s = requests.Session()
    s.verify = False
    return s

import streamlit as st

def get_nas_proxy():
    """敺?proxy_helper 霈?誨?身摰?銝血???TCP 摮暑瑼Ｘ葫??""
    try:
        from proxy_helper import get_proxy_config as _gpc
        _cfg = _gpc()
    except Exception:
        _cfg = None
    if not _cfg:
        return None
    _url = _cfg.get('http', '')
    if _url and _proxy_alive(_url):
        return _cfg
    return None

DISABLE_TWSE: bool = True  # ? TWSE 撌脫偶銋???


# ?? 敹怠??箇?閮剜 (v4.5) ???????????????????????????????????????????????????
from data_config import TTL_CONFIG as _TTL_CFG, PKL_DIR as _PKL_DIR
_CACHE_SENTINEL = object()  # ??亙翰??賭葉??瘜?None ??

def _pkl_get(key: str, ttl: int):
    """霈??pickle 敹怠?嚗?賭葉??????_CACHE_SENTINEL??""
    import pickle as _pk_, time as _tm_
    _path = f'{_PKL_DIR}/{key}.pkl'
    try:
        if os.path.exists(_path) and _tm_.time() - os.path.getmtime(_path) < ttl:
            with open(_path, 'rb') as _f_:
                _v_ = _pk_.load(_f_)
            if _v_ is not None:
                print(f'[Cache] ??{key} ?賭葉嚗tl={ttl}s嚗?)
                return _v_
    except Exception:
        pass
    return _CACHE_SENTINEL

def _pkl_put(key: str, value):
    """撖怠 pickle 敹怠?嚗甈∪銵???鞈?嚗? return value??""
    import pickle as _pk_
    try:
        os.makedirs(_PKL_DIR, exist_ok=True)
        with open(f'{_PKL_DIR}/{key}.pkl', 'wb') as _f_:
            _pk_.dump(value, _f_)
    except Exception:
        pass
    return value

def _pkl_clear_all():
    """撘瑕?瑟嚗??斗???pickle 敹怠?瑼?嚗??垢?撥?嗆?啜??蝙?剁???""
    import glob as _glob_
    _removed = 0
    for _f_ in _glob_.glob(f'{_PKL_DIR}/*.pkl'):
        try:
            os.remove(_f_)
            _removed += 1
        except Exception:
            pass
    print(f'[Cache] ??儭?撌脫???{_removed} ?翰??獢?)


import plotly.graph_objects as go

FINMIND_TOKEN = (getattr(st, 'secrets', {}).get('FINMIND_TOKEN', '')
                 or os.environ.get('FINMIND_TOKEN', ''))
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}
COLORS_7 = ["#58a6ff",TRAFFIC_GREEN,"#ffd700",TRAFFIC_RED,"#bc8cff","#79c0ff","#ff9f43"]
INTL_MAP = {"??撌交平 DJI":"^DJI","蝝?? IXIC":"^IXIC","鞎餃???擃?SOX":"^SOX","10Y?砍畾??:"^TNX","蝢?? DXY":"DX-Y.NYB"}
INTL_UNIT = {k:("%" if "畾?? in k else "?") for k in INTL_MAP}
TW_MAP   = {"?啗???":"^TWII","?啣撟???:"TWD=X"}
TW_UNIT  = {"?啗???":"pts","?啣撟???:"TWD/USD"}
TECH_MAP = {"?啁???ADR":"TSM","敺株? MSFT":"MSFT","?? AAPL":"AAPL","靚瑟? GOOGL":"GOOGL","頛? NVDA":"NVDA","AMD":"AMD","??AVGO":"AVGO"}

def _num(s):
    try: return float(str(s).replace(",","").replace(" ","").replace("+",""))
    except: return None

_TW_TZ_DL = datetime.timezone(datetime.timedelta(hours=8))

def _tw_today_dl():
    return datetime.datetime.now(_TW_TZ_DL).date()

def _recent_date(fmt="%Y%m%d"):
    d = _tw_today_dl()
    # ?望?湔??圈曹?
    while d.weekday() >= 5: d -= datetime.timedelta(days=1)
    return d.strftime(fmt)

# ????????????????????????????????????????????????
# 銝之瘜犖嚗AS 銝剔匱蝡????嗥敺?5:30???嗆鞈?
# ????????????????????????????????????????????????
def fetch_institutional(date_str=None):
    if date_str is None: date_str = _recent_date()
    _inst_ttl = _TTL_CFG.get('institutional', 600)
    _inst_cached = _pkl_get('institutional', _inst_ttl)
    if _inst_cached is not _CACHE_SENTINEL:
        return _inst_cached

    try:
        from proxy_helper import fetch_url as _furl_i
        _base_dt_i = datetime.datetime.now()
        for _di in range(7):
            _d = _base_dt_i - datetime.timedelta(days=_di)
            if _d.weekday() >= 5:
                continue
            _ds = _d.strftime('%Y%m%d')
            _r_i = _furl_i(
                f'https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&date={_ds}')
            if not _r_i:
                print(f'[銝之瘜犖/BFI82U] ?? date={_ds} ?∪???)
                continue
            try:
                _resp_i = _r_i.json()
            except Exception:
                continue
            if not (isinstance(_resp_i, dict) and _resp_i.get('stat') == 'OK'):
                print(f'[銝之瘜犖/BFI82U] ?? date={_ds} stat={(_resp_i or {}).get("stat")}')
                continue
            # BFI82U ?航? data ??tables[0].data
            _data_i = _resp_i.get('data', [])
            if not _data_i and 'tables' in _resp_i:
                _data_i = (_resp_i['tables'][0] if _resp_i['tables'] else {}).get('data', [])
            if not _data_i:
                continue
            _inst = {'憭??鞈?: {'net': 0.0}, '?縑': {'net': 0.0}, '?芰???: {'net': 0.0}}
            for _row_i in _data_i:
                _nm_i = str(_row_i[0])
                # row[3] = 鞎瑁都頞???撣嗅?????嚗?lstrip('-') ?舀鞎?
                _vs_i = str(_row_i[3]).replace(',', '').strip()
                if not _vs_i.lstrip('-').isdigit():
                    continue
                _net_i = round(int(_vs_i) / 1e8, 2)  # ??????
                if '憭??鞈? in _nm_i:
                    _inst['憭??鞈?]['net'] = _net_i
                elif '?縑' in _nm_i:
                    _inst['?縑']['net'] = _net_i
                elif '?芰?' in _nm_i:
                    _inst['?芰???]['net'] += _net_i
            print(f'[銝之瘜犖/BFI82U] ??date={_ds} {_inst}')
            return _pkl_put('institutional', (_inst, _ds))
    except Exception as _e_inst:
        print(f'[銝之瘜犖/BFI82U] ??{type(_e_inst).__name__}: {_e_inst}')

    return {}, date_str


# ????????????????????????????????????????????????
# ??擗?嚗AS 銝剔匱蝡?
# ????????????????????????????????????????????????
def fetch_margin_balance(date_str=None):
    """??擗? ??FinMind ??MI_MARGN ??HiStock ??Goodinfo ??Yahoo ???漕蝬莎??桐?嚗???
    v6嚗lan 0 = FinMind TaiwanStockTotalMarginPurchaseShortSale嚗treamlit Cloud 瘚瑕? IP ?臭??舫?靘?嚗?
    v5嚗lan A = MI_MARGN嚗i-margn.html 敺垢 JSON嚗??像 data/fields 閫????""
    _mb_ttl = _TTL_CFG.get('margin_balance', 600)
    _mb_cached = _pkl_get('margin_balance', _mb_ttl)
    if _mb_cached is not _CACHE_SENTINEL:
        return _mb_cached

    # ??餈??漱?嚗望敺?嚗?
    _now_mb = datetime.datetime.now()
    while _now_mb.weekday() >= 5:
        _now_mb -= datetime.timedelta(days=1)
    _ds_mb = _now_mb.strftime('%Y%m%d')

    # ?寞?0: FinMind TaiwanStockTotalMarginPurchaseShortSale嚗6 ?啣?嚗?
    # 瘝餅嚗絲憭?IP 銋????TWSE/HiStock/Goodinfo/Yahoo/cnyes ?券?閬??IP
    try:
        from leading_indicators import finmind_get as _fm_mb
        _tok_mb = os.environ.get('FINMIND_TOKEN', '')
        _start_mb = (_now_mb - datetime.timedelta(days=10)).strftime('%Y%m%d')
        _df_mb0 = _fm_mb('TaiwanStockTotalMarginPurchaseShortSale', '', _start_mb, _ds_mb, _tok_mb)
        if _df_mb0 is not None and not _df_mb0.empty:
            _cols_mb0 = list(_df_mb0.columns)
            _bal_cols0 = [c for c in _cols_mb0 if any(k in c for k in
                          ['alance', '擗?', 'amount', 'Amount'])]
            _df_mb0 = _df_mb0.sort_values('date')
            _last_d0 = str(_df_mb0['date'].iloc[-1])
            _grp0 = _df_mb0[_df_mb0['date'] == _last_d0]
            _v_mb0 = None
            if 'name' in _cols_mb0 and _bal_cols0:
                # ?瑟撘?瘥??誨銵具?鞈???銝??
                for _, _r0 in _grp0.iterrows():
                    _nm0 = str(_r0.get('name', '')).lower()
                    if not ('??' in _nm0 or 'margin' in _nm0 or 'purchase' in _nm0):
                        continue
                    for _bc0 in _bal_cols0:
                        try:
                            _raw0 = float(str(_r0.get(_bc0, 0)).replace(',', '') or 0)
                        except Exception:
                            continue
                        # ?芸??菜葫?桐?嚗? / ??/ ?? / ?砍?
                        if 100 <= _raw0 <= 30_000:        _cand0 = _raw0
                        elif _raw0 > 1e9:                  _cand0 = _raw0 / 1e8
                        elif _raw0 > 1e6:                  _cand0 = _raw0 / 1e5
                        elif _raw0 > 1e4:                  _cand0 = _raw0 / 1e4
                        else:                              continue
                        if 100 < _cand0 < 30_000:
                            _v_mb0 = round(_cand0, 1); break
                    if _v_mb0 is not None: break
            elif 'TotalMarginPurchaseTodayBalance' in _cols_mb0:
                _raw0 = float(str(_grp0['TotalMarginPurchaseTodayBalance'].iloc[-1]).replace(',', '') or 0)
                if _raw0 > 1e6: _v_mb0 = round(_raw0 / 1e5, 1)
                elif 100 <= _raw0 <= 30_000: _v_mb0 = round(_raw0, 1)
            elif 'MarginPurchaseTodayBalance' in _cols_mb0:
                _raw0 = float(str(_grp0['MarginPurchaseTodayBalance'].iloc[-1]).replace(',', '') or 0)
                if _raw0 > 1e6: _v_mb0 = round(_raw0 / 1e5, 1)
                elif 100 <= _raw0 <= 30_000: _v_mb0 = round(_raw0, 1)
            if _v_mb0 is not None and 100 < _v_mb0 < 30_000:
                print(f'[??擗?/FinMind] ??{_v_mb0}??date={_last_d0}')
                return _pkl_put('margin_balance', _v_mb0)
            print(f'[??擗?/FinMind] ?? date={_last_d0} 閫???芸銝哨?cols={_cols_mb0[:6]}嚗?)
        else:
            print('[??擗?/FinMind] ?? ?蝛?DataFrame')
    except Exception as _e_mb0:
        print(f'[??擗?/FinMind] ??{type(_e_mb0).__name__}: {_e_mb0}')

    # ?寞?A: TWSE rwd MI_MARGN嚗甈∪?閰行?餈漱?嚗S?LL ??selectType 摰寥嚗?
    # 撠? leading_indicators._twse_margin_day 撌脤?霅???頛荔??惜 data/fields嚗?
    # 甈??菜葫??鞈?..擗????????嚗eversed ??蝮賢?嚗???00,000=??
    try:
        from proxy_helper import fetch_url as _furl_mb
        _hdr_mb = {'Referer': 'https://www.twse.com.tw/zh/trading/margin/mi-margn.html'}
        _hit_mb = False
        for _sel_mb in ('MS', 'ALL'):
            _r_mb = _furl_mb(
                'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN'
                f'?response=json&date={_ds_mb}&selectType={_sel_mb}',
                headers=_hdr_mb, timeout=12)
            if _r_mb is None:
                continue
            try:
                _resp_mb = _r_mb.json()
            except Exception:
                _resp_mb = None
            if not (isinstance(_resp_mb, dict) and _resp_mb.get('stat') == 'OK'):
                _stat_mb = (_resp_mb or {}).get('stat') if isinstance(_resp_mb, dict) else 'no-json'
                print(f'[??擗?/MI_MARGN/{_sel_mb}] ?? date={_ds_mb} stat={_stat_mb}')
                continue
            _fields_mb = [str(_f) for _f in _resp_mb.get('fields', [])]
            _fa_col = next((_i for _i, _f in enumerate(_fields_mb)
                           if '??' in _f and '擗?' in _f and '?? not in _f), 6)
            for _row_mb in reversed(_resp_mb.get('data', [])):
                if not _row_mb or len(_row_mb) <= _fa_col:
                    continue
                _vs_mb = str(_row_mb[_fa_col]).replace(',', '').replace(' ', '').strip()
                try:
                    _v_raw_mb = float(_vs_mb)
                except Exception:
                    continue
                if _v_raw_mb > 10_000_000:  # 隞? ????
                    _v_mb = round(_v_raw_mb / 100_000, 1)
                    if 100 < _v_mb < 30_000:
                        print(f'[??擗?/MI_MARGN/{_sel_mb}] ??{_v_mb}??date={_ds_mb}')
                        return _pkl_put('margin_balance', _v_mb)
            print(f'[??擗?/MI_MARGN/{_sel_mb}] ?? date={_ds_mb} 閫???芸銝哨?fa_col={_fa_col}嚗?)
            _hit_mb = True
        if not _hit_mb:
            print(f'[??擗?/MI_MARGN] ?? MS/ALL ???')
    except Exception as _e_mb:
        print(f'[??擗?/MI_MARGN] ??{type(_e_mb).__name__}: {_e_mb}')

    # ?寞?B: HiStock 蝬脤??祈嚗??BeautifulSoup嚗?
    try:
        from proxy_helper import fetch_url as _furl_hi
        from bs4 import BeautifulSoup as _BS_mb
        _rh = _furl_hi('https://histock.tw/stock/margin.aspx', timeout=12)
        if _rh is not None:
            _soup_h = _BS_mb(_rh.text, 'html.parser')
            # ???怒?鞈?憿?摮?餈??詨?嚗???嚗3: 雿輻?惜撌脣?亦? re
            _txt_h = _soup_h.get_text(' ', strip=True)
            _m_h = re.search(r'??擗?[^\d]{0,20}([\d,]+(?:\.\d+)?)\s*??, _txt_h)
            if _m_h:
                _v_h = round(float(_m_h.group(1).replace(',', '')), 1)
                if 100 < _v_h < 30_000:
                    print(f'[??擗?/HiStock] ??{_v_h}??)
                    return _pkl_put('margin_balance', _v_h)
    except Exception as _e_hi:
        print(f'[??擗?/HiStock] ??{type(_e_hi).__name__}: {_e_hi}')

    # ?寞?C: Goodinfo ???????亦絞閮??祇? HTML嚗eautifulSoup嚗?
    # 鋆撥嚗”?剖?瑟撖穿?隞颱??怒?鞈?荔?+ ?湧?甇?? fallback
    try:
        from proxy_helper import fetch_url as _furl_gi
        from bs4 import BeautifulSoup as _BS_gi
        _gi_url = ('https://goodinfo.tw/tw/ShowMarginChart.asp'
                   '?STOCK_ID=%E5%8A%A0%E6%AC%8A%E6%8C%87%E6%95%B8'
                   '&CHT_CAT=DATE&PRICE_ADJ=F'
                   '&SHEET=%E8%9E%8D%E8%B3%87%E8%9E%8D%E5%88%B8%E9%A4%98%E9%A1%8D')
        _gi_hdr = {'Referer': 'https://goodinfo.tw/tw2/index.asp'}
        _rg = _furl_gi(_gi_url, headers=_gi_hdr, timeout=15)
        if _rg is not None:
            _rg.encoding = 'utf-8'
            _soup_g = _BS_gi(_rg.text, 'html.parser')
            _gi_val = None
            # 蝚砌?頛迎?銵券?怒?鞈?銵冽
            for _tbl in _soup_g.find_all('table'):
                _heads = ' '.join(th.get_text(' ', strip=True)
                                  for th in _tbl.find_all('th'))
                if '??' not in _heads:
                    continue
                _rows = _tbl.find_all('tr')
                for _row_g in _rows[1:]:
                    _cells = [c.get_text(' ', strip=True)
                              for c in _row_g.find_all(['td', 'th'])]
                    _nums = [c for c in _cells
                             if re.match(r'^[\d,]+(\.\d+)?$', c.replace(',', ''))]
                    if len(_nums) >= 3:
                        for _cand in _nums[:5]:
                            _vc = float(_cand.replace(',', ''))
                            if _vc > 100_000:
                                _vc = round(_vc / 100_000, 1)
                            if 100 < _vc < 30_000:
                                _gi_val = round(_vc, 1); break
                        if _gi_val is not None: break
                if _gi_val is not None: break
            # 蝚砌?頛?fallback嚗?迤??鞈?憿?12,345 ??
            if _gi_val is None:
                _txt_g = _soup_g.get_text(' ', strip=True)
                _m_g = re.search(r'??擗?[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*??, _txt_g)
                if _m_g:
                    _vg2 = round(float(_m_g.group(1).replace(',', '')), 1)
                    if 100 < _vg2 < 30_000:
                        _gi_val = _vg2
            if _gi_val is not None:
                print(f'[??擗?/Goodinfo] ??{_gi_val}??)
                return _pkl_put('margin_balance', _gi_val)
            print('[??擗?/Goodinfo] ?? 銵冽 + 甇????賭葉')
    except Exception as _e_gi:
        print(f'[??擗?/Goodinfo] ??{type(_e_gi).__name__}: {_e_gi}')

    # ?寞?D: Yahoo ?∪?鞈擗?嚗TML嚗?迤??
    try:
        from proxy_helper import fetch_url as _furl_yh
        from bs4 import BeautifulSoup as _BS_yh
        _ry = _furl_yh('https://tw.stock.yahoo.com/margin-balance', timeout=12)
        if _ry is not None:
            _ry.encoding = 'utf-8'
            _txt_y = _BS_yh(_ry.text, 'html.parser').get_text(' ', strip=True)
            # Yahoo 憿舐內??鞈?憿?1,234 ????鞈?憿??? 1,234??
            _m_y = re.search(r'??擗?[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*(?:?$)', _txt_y)
            if _m_y:
                _vy = round(float(_m_y.group(1).replace(',', '')), 1)
                if 100 < _vy < 30_000:
                    print(f'[??擗?/Yahoo] ??{_vy}??)
                    return _pkl_put('margin_balance', _vy)
            print('[??擗?/Yahoo] ?? 甇???芸銝?)
    except Exception as _e_yh:
        print(f'[??擗?/Yahoo] ??{type(_e_yh).__name__}: {_e_yh}')

    # ?寞?E: ?漕蝬脩敺??賊?憿?HTML嚗?迤??
    try:
        from proxy_helper import fetch_url as _furl_cy
        from bs4 import BeautifulSoup as _BS_cy
        _rc = _furl_cy('https://www.cnyes.com/twstock/a_margin.aspx', timeout=12)
        if _rc is not None:
            _rc.encoding = 'utf-8'
            _txt_c = _BS_cy(_rc.text, 'html.parser').get_text(' ', strip=True)
            _m_c = re.search(r'??擗?[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*(?:?$)', _txt_c)
            if _m_c:
                _vc = round(float(_m_c.group(1).replace(',', '')), 1)
                if 100 < _vc < 30_000:
                    print(f'[??擗?/cnyes] ??{_vc}??)
                    return _pkl_put('margin_balance', _vc)
            print('[??擗?/cnyes] ?? 甇???芸銝?)
    except Exception as _e_cy:
        print(f'[??擗?/cnyes] ??{type(_e_cy).__name__}: {_e_cy}')

    return None


def evaluate_market_status_v4_final(current_price: float, ma_240: float,
                                    futures_net_oi: int) -> dict:
    """?啗 AI ?唳?摰?v4.0 ?詨?撘?嚗?瘜典???蝮賜?嚗?""
    current_price = current_price or 1.0
    ma_240 = ma_240 or current_price
    futures_net_oi = futures_net_oi or 0

    bias_240 = ((current_price - ma_240) / ma_240) * 100
    is_bull_market = current_price >= (ma_240 * 0.99)
    is_overheated = bias_240 > 20.0
    is_foreign_hedging = futures_net_oi < -30000

    if is_bull_market:
        if is_overheated or is_foreign_hedging:
            signal = "? 憭? / ?霅行?"
            action = "憭抒銋??鞈?芷?擃遣霅唳??璆萄??粹??桃??唾頃嚗??箏???憿?銝行?擃蝳血?/撟唾﹛?????
            hold_ratio = "50% - 70%"
        else:
            signal = "? 撘瑕憭"
            action = "??憭??銝?蝣潛帘摰遣霅唳憭扳敹雿?憓???蟡典???芥?
            hold_ratio = "80% - 100%"
    else:
        signal = "? 蝛粹?脩戌"
        action = "頝撟渡?嚗隅?Ｗ?蝛箝雁?????憿??桃???摰???
        hold_ratio = "20% - 40%"

    return {
        "Signal": signal,
        "Action_Advice": action,
        "Suggested_Holding": hold_ratio,
        "Bias_240": round(bias_240, 2),
        "Is_Bull": is_bull_market,
        "Is_Overheated": is_overheated,
        "Is_Foreign_Hedging": is_foreign_hedging,
    }


# ????????????????????????????????????????????????
# yfinance
# ????????????????????????????????????????????????
def fetch_single(symbol, period="60d"):
    import os as _os2, pickle as _pk2, hashlib as _hs2
    _ck2 = '/tmp/stock_cache/' + _hs2.md5(f'yf_{symbol}_{period}'.encode()).hexdigest() + '.pkl'
    _os2.makedirs('/tmp/stock_cache', exist_ok=True)
    if _os2.path.exists(_ck2) and (time.time()-_os2.path.getmtime(_ck2))/60 < 30:
        try:
            with open(_ck2,'rb') as _f: return _pk2.load(_f)
        except: pass
    # 蝢??? symbol 皜
    _sym_list = [symbol]
    if symbol in ('DX-Y.NYB', 'DX=F'):
        _sym_list = ['DX-Y.NYB', 'DX=F', 'UUP']  # NYB??鞎兩?ETF
    # v18.209 K5嚗韏?yf_proxy.cached_history嚗??proxy env + st.cache_data 1h嚗?
    # ??pkl 30min cache ?拙惜靽風 ??頝?process ??摮暑 + ??process ?抒?霈??
    try:
        from yf_proxy import cached_history as _yp_hist
        h = None
        for _sym in _sym_list:
            _h = _yp_hist(_sym, period=period)
            if _h is not None and not _h.empty:
                h = _h
                break
        if h is None or h.empty: return None
        h.index = pd.DatetimeIndex(h.index).tz_localize(None)
        h.columns = [c.lower().replace(' ','_') for c in h.columns]
        if 'close' in h.columns:
            h = h.dropna(subset=['close'])
        elif 'Close' in h.columns:
            h = h.dropna(subset=['Close'])
        if h.empty: return None
        with open(_ck2,'wb') as _f: _pk2.dump(h, _f)
        return h
    except Exception as e:
        print(f'[yf:{symbol}] {e}'); return None
    # v18.209 K5嚗? finally env restore 蝘駁嚗roxy_env ??yf_proxy ??contextmanager ??


def fetch_flow_snapshot(period="2y"):
    """?函?鞈?瘚???????/ 頝刻???ETF ?嗥摨?嚗蒂銵???+ /tmp pickle 敹怠? 30 ??

    ??{憿舐內?? DataFrame}嚗窒??fetch_single 蝯?嚗?冽敹?SPY ???撖怠翰??
    ?踹??急??批憭望?鋡恍?雿?蝮賜? tab???????蝭雿輻??
    """
    import os as _os_fl
    import pickle as _pk_fl
    import time as _tm_fl
    from concurrent.futures import ThreadPoolExecutor as _TPE_fl
    from flow_engine import all_symbols as _all_fl

    _ck_fl = '/tmp/stock_cache/_flow_snapshot.pkl'
    _os_fl.makedirs('/tmp/stock_cache', exist_ok=True)
    if _os_fl.path.exists(_ck_fl) and (_tm_fl.time() - _os_fl.path.getmtime(_ck_fl)) / 60 < 30:
        try:
            with open(_ck_fl, 'rb') as _f_fl:
                return _pk_fl.load(_f_fl)
        except Exception:
            pass

    _syms = _all_fl()                      # {?迂: 隞??}
    _uniq = sorted(set(_syms.values()))    # ?駁?敺祕????SPY 蝑?其誨???甈∴?

    def _one(sym):
        return sym, fetch_single(sym, period=period)

    _by_sym = {}
    try:
        with _TPE_fl(max_workers=min(8, len(_uniq))) as _ex_fl:
            for _sym, _df in _ex_fl.map(_one, _uniq):
                _by_sym[_sym] = _df
    except Exception as _e_fl:
        print(f'[flow] ??銝西????啣虜: {_e_fl}')

    out = {name: _by_sym.get(sym) for name, sym in _syms.items()}

    if _by_sym.get('SPY') is not None:     # ?詨???翰??
        try:
            with open(_ck_fl, 'wb') as _f_fl:
                _pk_fl.dump(out, _f_fl)
        except Exception:
            pass
    return out

def _fetch_otc_via_finmind(token=""):
    if not FINMIND_TOKEN: return None
    try:
        start=(datetime.date.today()-datetime.timedelta(days=90)).strftime('%Y-%m-%d')
        r=_bps().get("https://api.finmindtrade.com/api/v4/data",
                       params={"dataset":"TaiwanStockDaily","data_id":"OTC","start_date":start},
                       headers={"Authorization":f"Bearer {FINMIND_TOKEN}"},timeout=20)
        j=r.json()
        if j.get("status")==200 and j.get("data"):
            df=pd.DataFrame(j["data"])
            if 'close' in df.columns:
                df['Date']=pd.to_datetime(df['date'])
                return df.sort_values('Date').set_index('Date')[['close']].rename(columns={'close':'Close'})
    except Exception as e: print(f"[OTC] {e}")
    return None



# ??????????????????????????????????????????????????????
# 擉啗??嚗DL嚗?FinMind ?臭?靘?嚗??TWSE MI_INDEX 撌脩宏?歹?
# ??????????????????????????????????????????????????????

# ??????????????????????????????????????????????????????
# 擉啗??嚗DL嚗?摰?神??
# 銝 @st.cache_data嚗 thread 銝剖仃??嚗??pickle cache
# 鞈?靘?: yfinance ^TWII嚗??TWSE MI_INDEX 撌脩宏?歹?
# ??????????????????????????????????????????????????????
def fetch_adl(days=60, token=None):
    """
    擉啗?? ADL v5 ??yfinance ^TWII 隡啁?嚗??TWSE MI_INDEX 撌脫偶銋??剁?
    ??yfinance ^TWII  ??蝡?舐隡啁???
       銝衣 5 蝺????嚗移蝣箏潸???摯蝞?

    ?寞??靽格迤嚗aiwanStockMarketCondition 銝 FinMind v4 ??鞈??葉
    """
    import datetime as _dt
    import pickle as _pk
    import os as _os2
    import time as _tm2
    import pandas as _pd_adl
# ?? ?亥? helper ??????????????????????????????????????????????
    _log_path = '/tmp/_adl_log.txt'
    def _alog(msg):
        print(msg, flush=True)
        try:
            with open(_log_path, 'a', encoding='utf-8') as _f:
                _f.write(msg + '\n')
        except Exception:
            pass
    try:
        open(_log_path, 'w').close()
    except Exception:
        pass

    # ?? Cache ????????????????????????????????????????????????????
    _ck = '/tmp/stock_cache/adl_data.pkl'
    _os2.makedirs('/tmp/stock_cache', exist_ok=True)
    if _os2.path.exists(_ck):
        _age = _tm2.time() - _os2.path.getmtime(_ck)
        if _age < 1800:
            try:
                _c = _pk.load(open(_ck, 'rb'))
                if _c is not None and not _c.empty:
                    _alog(f'[ADL] 敹怠??賭葉 {len(_c)} 蝑?(age={_age/60:.1f}min)')
                    return _c
            except Exception:
                pass

    today  = _dt.date.today()
    s_date = today - _dt.timedelta(days=days + 14)
    s_dash = s_date.strftime('%Y-%m-%d')
    e_dash = today.strftime('%Y-%m-%d')
    rows: dict = {}   # {ymd: {'up':int, 'down':int, 'is_proxy':bool}}

    # ????????????????????????????????????????????????????????????????
    # ??yfinance ^TWII ??隡啁?嚗??喳?剁?is_proxy=True嚗?
    # ?砍?嚗撞頝? 簣1% ??簣150 摰塚?隞?900/900 ?箏皞?
    # ????????????????????????????????????????????????????????????????
    _alog('[ADL-? yfinance ^TWII 隡啁?...')
    try:
        import yfinance as _yf_adl, os as _os_yf
        try:
            from tw_stock_data_fetcher import _load_proxy_config as _lpc_adl
            _yf_px = (_lpc_adl() or {})
            _yf_px = _yf_px.get('https') or _yf_px.get('http') or None
        except Exception:
            _yf_px = None
        _ek = ('HTTPS_PROXY', 'HTTP_PROXY', 'https_proxy', 'http_proxy')
        _ebak = {k: _os_yf.environ.get(k) for k in _ek}
        if _yf_px:
            for k in _ek:
                _os_yf.environ[k] = _yf_px
        try:
            _twii = _yf_adl.download('^TWII', start=s_dash, end=e_dash, progress=False, auto_adjust=True)
        finally:
            for k, v in _ebak.items():
                if v is None:
                    _os_yf.environ.pop(k, None)
                else:
                    _os_yf.environ[k] = v
        if not _twii.empty:
            # [Fix] yfinance ?啁??航? MultiIndex columns嚗??撟?
            if isinstance(_twii.columns, pd.MultiIndex):
                _twii.columns = _twii.columns.get_level_values(0)
            _twii = _twii.dropna(subset=['Close'])
            for _ix in _twii.index:
                _dk = str(_ix)[:10].replace('-', '')
                _cl = float(_twii.loc[_ix, 'Close'])
                _op = float(_twii.loc[_ix, 'Open'])
                _pct = (_cl - _op) / _op if _op > 0 else 0.0
                # 隡啁??砍?嚗葉??900嚗?簣1%蝝?50摰塚????0~1750
                _up = max(50, min(1750, int(900 + _pct * 15000)))
                rows[_dk] = {'up': _up, 'down': max(50, 1800 - _up), 'is_proxy': True}
            _alog(f'[ADL-? ??{len(rows)} 憭拐摯蝞???)
        else:
            _alog('[ADL-? ?? yfinance ?蝛箄???)
    except Exception as _e1:
        _alog(f'[ADL-? ??{type(_e1).__name__}: {_e1}')

    # Edge Case 6: 摰瘝?鞈?嚗??TWSE MI_INDEX 撌脩宏?歹?
    if not rows:
        _alog('[ADL] ?? ???皞?憭望?嚗???None')
        return None

    # ?? 蝯? DataFrame ??????????????????????????????????????????
    _records = []
    for _dk in sorted(rows):
        if not (s_date.strftime('%Y%m%d') <= _dk <= today.strftime('%Y%m%d')):
            continue
        _v = rows[_dk]
        _records.append({
            'date':     _dk,
            'up':       _v['up'],
            'down':     _v['down'],
            'is_proxy': _v['is_proxy'],
        })

    # Edge Case 7: ?蕪敺??∟???
    if not _records:
        _alog('[ADL] ?? ??閮??箇征')
        return None

    df = _pd_adl.DataFrame(_records)
    df['ad']       = df['up'] - df['down']
    df['adl']      = df['ad'].cumsum()
    df['adl_ma20'] = df['adl'].rolling(20, min_periods=1).mean()
    df['ad_ratio'] = (df['up'] / (df['up'] + df['down']).replace(0, 1) * 100).round(1)
    df['date']     = _pd_adl.to_datetime(df['date'], format='%Y%m%d')

    _proxy_n = int(df['is_proxy'].sum())
    _exact_n = int((~df['is_proxy']).sum())
    _alog(
        f'[ADL] ??摰? {len(df)} 蝑?'
        f'蝎曄Ⅱ={_exact_n} 隡啁?={_proxy_n} '
        f'銝撞雿?:{df["ad_ratio"].iloc[-1]:.1f}%'
    )

    # ?? 敹怠? ????????????????????????????????????????????????????
    try:
        with open(_ck, 'wb') as _f:
            _pk.dump(df.tail(days).reset_index(drop=True), _f)
    except Exception:
        pass

    return df.tail(days).reset_index(drop=True)


# ?? 4. Self-Test嚗??葫閰佗?????????????????????????????????????
def _adl_selftest():
    """??Colab 憭?臬銵迨?賣撽?閫???摩"""
    import re

    def _parse(s):
        m = re.match(r'^([\d,]+)', str(s).strip())
        return int(m.group(1).replace(',', '')) if m else 0

    # Test 1: 甇?虜?澆?
    assert _parse('7,768(403)') == 7768, "Test1 failed"
    # Test 2: ?⊥??
    assert _parse('3,644') == 3644, "Test2 failed"
    # Test 3: 蝛箏?銝?
    assert _parse('') == 0, "Test3 failed"
    # Test 4: ?芣?瞍Ｗ?嚗???隤文嚗?
    assert _parse('銝撞') == 0, "Test4 failed"
    # Test 5: 憭批?
    assert _parse('19,039') == 19039, "Test5 failed"
    print("[ADL selftest] ???券??")




def _hex2rgba(color, alpha=0.12):
    try:
        c=color.lstrip('#'); r,g,b=int(c[0:2],16),int(c[2:4],16),int(c[4:6],16)
        return f"rgba({r},{g},{b},{alpha})"
    except: return "rgba(88,166,255,0.12)"

def _base_layout(title="", height=260):
    return dict(title=dict(text=title,font=dict(color="#8b949e",size=12)),
                height=height,plot_bgcolor="#0e1117",paper_bgcolor="#0e1117",
                font=dict(color="#e6edf3",size=11),
                margin=dict(l=8,r=8,t=35,b=20),
                xaxis=dict(gridcolor="#21262d",showgrid=True,zeroline=False),
                yaxis=dict(gridcolor="#21262d",showgrid=True,zeroline=False),
                legend=dict(bgcolor="rgba(0,0,0,0)",font=dict(size=10)))

def sparkline(df, title="", color="#58a6ff"):
    col=next((c for c in ['close','Close'] if c in df.columns),None)
    if col is None: return go.Figure()
    s=df[col].dropna().tail(45)
    fig=go.Figure(go.Scatter(x=list(s.index),y=list(s.values),mode='lines',
                             line=dict(color=color,width=2),fill='tozeroy',
                             fillcolor=_hex2rgba(color) if color.startswith('#') else color))
    fig.update_layout(**_base_layout(title,200)); return fig

def multi_chart(data_dict, title="", norm=False, height=250):
    fig=go.Figure()
    for i,(name,df) in enumerate(data_dict.items()):
        col=next((c for c in ['close','Close'] if c in df.columns),None)
        if col is None: continue
        s=df[col].dropna().tail(45)
        y=(s/s.iloc[0]*100).round(2) if (norm and len(s)>0) else s
        fig.add_trace(go.Scatter(x=list(s.index),y=list(y.values),mode='lines',name=name,
                                 line=dict(color=COLORS_7[i%len(COLORS_7)],width=2)))
    fig.update_layout(**_base_layout(title,height)); return fig

def bar_chart_institutional(inst_dict, title="銝之瘜犖鞎瑁都頞????梁???", height=300):
    """???????梁???銝之瘜犖?銝甈?憿???"""
    # ?銝?鈭?
    _inst_keys = ['憭?', '?縑', '?芰???]
    _inst_colors = {'憭?': '#58a6ff', '?縑': TRAFFIC_GREEN, '?芰???: '#bc8cff'}
    # ??? float嚗耨敺抬?? [] 撠 >= 瘥? TypeError嚗?
    _data_by = {k: 0.0 for k in _inst_keys}
    # inst_dict ?澆?: {瘜犖?? {net, buy, sell, ...}}
    if inst_dict and isinstance(inst_dict, dict):
        for _name, _val in inst_dict.items():
            if '??' in _name: continue
            if not isinstance(_val, dict): continue
            _matched = next((k for k in _inst_keys if k in str(_name)), None)
            if _matched:
                try: _data_by[_matched] = float(_val.get('net', 0) or 0)
                except: pass
    # ?亦?交?蝬剖漲嚗??格璈怠???
    fig = go.Figure()
    for _ik in _inst_keys:
        _v = float(_data_by.get(_ik, 0.0))  # 蝣箔???float
        _c = '#da3633' if _v > 0 else ('#2ea043' if _v < 0 else '#388bfd')
        fig.add_trace(go.Bar(
            name=_ik, x=[_ik], y=[_v],
            marker_color=_inst_colors.get(_ik, _c),
            text=[f'{_v:+.1f}??],
            textposition='outside',
            cliponaxis=False,
            opacity=0.9,
        ))
    # ?亙?函 0嚗PI ?芸??單?蝭?嚗?? annotation ?內
    _total = sum(float(v) for v in _data_by.values())
    _all_zero = all(v == 0.0 for v in _data_by.values())
    _layout = _base_layout(title, height)
    _layout.update({
        'barmode': 'group',
        'showlegend': True,
        'legend': {'orientation': 'h', 'y': 1.08, 'font': {'size': 10, 'color': '#8b949e'}},
        'shapes': [{'type': 'line', 'x0': -0.5, 'x1': 2.5, 'y0': 0, 'y1': 0,
                    'line': {'color': '#484f58', 'width': 1, 'dash': 'dot'}}],
        'annotations': [{'text': f'??: {_total:+.1f}??,
                         'xref': 'paper', 'yref': 'paper', 'x': 0.98, 'y': 0.95,
                         'showarrow': False, 'font': {'size': 12, 'color': '#da3633' if _total > 0 else ('#2ea043' if _total < 0 else '#388bfd')}}]
    })
    if _all_zero:
        # ??潛 0嚗‵??雿?bar 霈?銵其?蝛箇嚗蒂??蝷箸?摮?
        for _ik in _inst_keys:
            fig.add_trace(go.Bar(
                name=_ik, x=[_ik], y=[0.001],
                marker_color='#21262d', opacity=0.3,
                showlegend=False,
            ))
        _layout['annotations'] = [{'text': '?? 鞈?敺?堆??嗥敺?15:30 ??嚗?,
                                    'xref': 'paper', 'yref': 'paper', 'x': 0.5, 'y': 0.5,
                                    'showarrow': False, 'font': {'size': 13, 'color': TRAFFIC_YELLOW}}]
    fig.update_layout(**_layout)
    return fig

def stat_card(name, stats, unit="", has_data=True):
    if not has_data or stats is None:
        return (f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
                f'padding:12px;text-align:center;opacity:0.5;"><div style="font-size:10px;color:#484f58;">{name}</div>'
                f'<div style="font-size:13px;color:#484f58;">頛銝?..</div></div>')
    pct=stats.get('pct',0); pc='#da3633' if pct>0 else ('#2ea043' if pct<0 else '#388bfd'); arrow='?? if pct>0 else ('?? if pct<0 else '?')
    return (f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px;text-align:center;">'
            f'<div style="font-size:10px;color:#484f58;">{name}</div>'
            f'<div style="font-size:18px;font-weight:900;color:#e6edf3;">{stats.get("last","?")} '
            f'<span style="font-size:10px;color:#8b949e;">{unit}</span></div>'
            f'<div style="font-size:12px;font-weight:700;color:{pc};">{arrow} {abs(pct):.2f}%</div>'
            f'<div style="font-size:10px;color:#484f58;">{stats.get("status","")}</div></div>')

def margin_card(margin):
    if margin is None:
        return ('<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px;">'
                '<div style="font-size:11px;color:#484f58;">??擗?</div>'
                f'<div style="font-size:12px;color:{TRAFFIC_YELLOW};margin-top:6px;">????銝哨?TWSE 15:30敺?堆?</div>'
                '<div style="font-size:10px;color:#484f58;margin-top:4px;">?嗥敺???啣?函蜇蝬??閰?/div></div>')
    mc=TRAFFIC_RED if margin>3400 else (TRAFFIC_YELLOW if margin>2500 else TRAFFIC_GREEN)
    label='?頞?3400???? if margin>3400 else ('?∟???500?郎?? if margin>2500 else '???冽偌雿?)
    return (f'<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;padding:14px;">'
            f'<div style="font-size:11px;color:#484f58;">??擗?</div>'
            f'<div style="font-size:28px;font-weight:900;color:{mc};">{margin:.0f}'
            f'<span style="font-size:12px;">??/span></div>'
            f'<div style="font-size:10px;color:#8b949e;">{label}</div></div>')

def section_header(num, title, icon=""):
    return (f'<div style="background:linear-gradient(90deg,#161b22,transparent);'
            f'border-left:3px solid #1f6feb;border-radius:0 6px 6px 0;'
            f'padding:8px 14px;margin:16px 0 10px 0;">'
            f'<span style="color:#1f6feb;font-weight:700;">{icon} {num}?title}</span></div>')

def analyze_20d_chips(stock_id: str) -> dict:
    """
    餈?20 ?亙蝐Ⅳ?葉摨血???憭? + ?縑 vs 蝮賣?鈭日?嚗?

    ?? A ?葉摨?= (憭?+?縑) 20?交楊鞎瑞蜇??/ 20?亦蜇?漱?? ? 100%
    ?? B 撱嗥???= 20?乩葉 (憭?+?縑) 瘛刻眺 > 0 ?予?訾?瘥?(%)

    鞎瑁都頞雿?撘?(FinMind TaiwanStockTotalInstitutionalInvestors)
    ?漱?雿?撘?(FinMind TaiwanStockPrice Trading_Volume)
    ???抵雿???葉摨衣?∪?甈∠??
    """
    import datetime as _dt20
    try:
        import pandas as _pd20
        _start = (_dt20.date.today() - _dt20.timedelta(days=50)).strftime('%Y-%m-%d')
        _base  = 'https://api.finmindtrade.com/api/v4/data'
        _hdrs  = {'Authorization': f'Bearer {FINMIND_TOKEN}'} if FINMIND_TOKEN else {}
        _common = {'token': FINMIND_TOKEN} if FINMIND_TOKEN else {}

        # ?? 1. ?銝之瘜犖瘥鞎瑁都頞??桐?嚗撐嚗????????????????????
        _p_inst = {**_common, 'dataset': 'TaiwanStockTotalInstitutionalInvestors',
                   'stock_id': stock_id, 'start_date': _start}
        _r_inst = _bps().get(_base, params=_p_inst, headers=_hdrs, timeout=20, verify=False)
        _j_inst = _r_inst.json()
        _inst_ok = (not (isinstance(_j_inst.get('status'), int)
                         and _j_inst['status'] >= 400)) and bool(_j_inst.get('data'))
        if not _inst_ok:
            return {'error': f'瘜犖鞈?憭望? status={_j_inst.get("status")}',
                    'signal': '??鞈?銝雲'}

        _df_i = _pd20.DataFrame(_j_inst['data'])
        _df_i.columns = [str(c).lower() for c in _df_i.columns]
        _df_i['buy']  = _pd20.to_numeric(_df_i.get('buy',  0), errors='coerce').fillna(0)
        _df_i['sell'] = _pd20.to_numeric(_df_i.get('sell', 0), errors='coerce').fillna(0)
        _df_i['net']  = _df_i['buy'] - _df_i['sell']
        # 颲刻?憭? / ?縑嚗摰?FinMind ?望??葉??name 甈?嚗?
        _is_fi = _df_i['name'].apply(
            lambda n: str(n) == 'Foreign_Investor' or ('憭?' in str(n) and '?芰?' not in str(n)))
        _is_tr = _df_i['name'].apply(
            lambda n: str(n) == 'Investment_Trust' or '?縑' in str(n))
        _df_fi = _df_i[_is_fi][['date','net']].rename(columns={'net':'foreign_net'})
        _df_tr = _df_i[_is_tr][['date','net']].rename(columns={'net':'trust_net'})
        _df_m  = _pd20.merge(_df_fi, _df_tr, on='date', how='outer').fillna(0)
        _df_m['combined'] = _df_m['foreign_net'] + _df_m['trust_net']
        _df_m  = _df_m.sort_values('date').tail(20)

        # ?? 2. 瘥?漱???桐?嚗撐嚗???TaiwanStockPrice嚗?????????
        _p_vol = {**_common, 'dataset': 'TaiwanStockPrice',
                  'stock_id': stock_id, 'start_date': _start}
        _r_vol = _bps().get(_base, params=_p_vol, headers=_hdrs, timeout=20, verify=False)
        _j_vol = _r_vol.json()
        _vol_ok = (not (isinstance(_j_vol.get('status'), int)
                        and _j_vol['status'] >= 400)) and bool(_j_vol.get('data'))
        if not _vol_ok:
            return {'error': '?寥?鞈?憭望?', 'signal': '??鞈?銝雲'}

        _df_v  = _pd20.DataFrame(_j_vol['data'])
        _df_v.columns = [str(c).lower() for c in _df_v.columns]
        # ?詨捆 trading_volume / volume 甈?
        _vcol  = next((c for c in _df_v.columns if 'trading_volume' in c or c == 'volume'), None)
        if _vcol is None:
            return {'error': '?曆??唳?鈭日?甈?', 'signal': '??鞈?銝雲'}
        _df_v[_vcol] = _pd20.to_numeric(_df_v[_vcol], errors='coerce').fillna(0)
        _df_v  = _df_v[['date', _vcol]].rename(columns={_vcol: 'volume'})
        _df_v  = _df_v.sort_values('date').tail(20)

        # ?? 3. ?蔥嚗??鈭箄??漱??????鈭斗?????????????????
        _df    = _pd20.merge(_df_m, _df_v, on='date', how='inner').tail(20)
        if len(_df) < 5:
            return {'error': f'??憭拇銝雲嚗len(_df)}憭抬?', 'signal': '??鞈?銝雲'}

        # ?? 4. 閮??拙之?? ??????????????????????????????????????????
        _tot_net = float(_df['combined'].sum())          # 憭???蝝航?瘛刻眺嚗撐嚗?
        _tot_vol = float(_df['volume'].sum())            # 蝮賣?鈭日?嚗撐嚗?
        _concentration = (_tot_net / _tot_vol * 100) if _tot_vol > 0 else 0.0   # %
        _pos_days  = int((_df['combined'] > 0).sum())
        _continuity = _pos_days / len(_df) * 100                                  # %

        # ?? 5. ?文?閮? ??????????????????????????????????????????????
        if _concentration > 5 and _continuity > 50:
            _signal = '? 憭扳?貊?'
        elif _concentration < -5:
            _signal = '? 憭扳?疏'
        else:
            _signal = '? 蝐Ⅳ?潭'

        print(f'[20d_chips/{stock_id}] ?葉摨?{_concentration:.2f}% 撱嗥???{_continuity:.0f}% '
              f'days={len(_df)} signal={_signal}')
        return {
            'concentration': round(_concentration, 2),   # %嚗甇?鞎?
            'continuity':    round(_continuity, 1),       # 0~100%
            'signal':        _signal,
            'days':          len(_df),
            'pos_days':      _pos_days,
            'total_net_k':   round(_tot_net / 1e3, 1),   # ?撐
            'total_vol_k':   round(_tot_vol / 1e3, 1),   # ?撐
            'error':         None,
        }
    except Exception as _e20:
        print(f'[20d_chips/{stock_id}] ??{type(_e20).__name__}: {_e20}')
        return {'error': str(_e20), 'signal': '??閮?憭望?'}


def analyze_20d_chips_from_df(df) -> dict:
    """餈?20 ?亦?蝣潮?銝剖漲 ???湔銴? K 蝺歇頛??df嚗 憭?/?縑/volume 甈?
    ?桐??撘蛛?嚗????澆 FinMind嚗???quota 憭望?嚗?
    ??澆???analyze_20d_chips 摰?詨?嚗?雿?頞單???error 靘?怎垢???API ??""
    try:
        import pandas as _pd
        if df is None or len(df) < 5:
            return {'error': 'df鞈?銝雲', 'signal': '??鞈?銝雲'}
        if not all(c in df.columns for c in ('憭?', '?縑', 'volume')):
            return {'error': 'df蝻箸?鈭???', 'signal': '??鞈?銝雲'}
        _d   = df.tail(20)
        _net = (_pd.to_numeric(_d['憭?'], errors='coerce').fillna(0)
                + _pd.to_numeric(_d['?縑'], errors='coerce').fillna(0))
        _vol = _pd.to_numeric(_d['volume'], errors='coerce').fillna(0)
        if not (_net != 0).any():        # 瘜犖甈??0 ??df ?芾??啁?蝣潘????API ??
            return {'error': 'df瘜犖甈??', 'signal': '??鞈?銝雲'}
        _tot_net = float(_net.sum())
        _tot_vol = float(_vol.sum())
        if _tot_vol <= 0:
            return {'error': '?漱?0', 'signal': '??鞈?銝雲'}
        _concentration = _tot_net / _tot_vol * 100
        _pos_days   = int((_net > 0).sum())
        _continuity = _pos_days / len(_d) * 100
        if _concentration > 5 and _continuity > 50:
            _signal = '? 憭扳?貊?'
        elif _concentration < -5:
            _signal = '? 憭扳?疏'
        else:
            _signal = '? 蝐Ⅳ?潭'
        return {
            'concentration': round(_concentration, 2),
            'continuity':    round(_continuity, 1),
            'signal':        _signal,
            'days':          len(_d),
            'pos_days':      _pos_days,
            'total_net_k':   round(_tot_net / 1e3, 1),
            'total_vol_k':   round(_tot_vol / 1e3, 1),
            'error':         None,
        }
    except Exception as _edf:
        return {'error': str(_edf), 'signal': '??閮?憭望?'}


def calc_stats(df):
    """閮??∠巨蝯梯??豢?嚗ast/pct/status嚗?""
    if df is None or df.empty: return None
    col = next((c for c in ['close','Close'] if c in df.columns), None)
    if not col: return None
    s = df[col].dropna()
    if len(s) < 2: return None
    last = float(s.iloc[-1])
    prev = float(s.iloc[-2])
    pct  = (last - prev) / prev * 100 if prev else 0
    ma5  = float(s.tail(5).mean())
    ma20 = float(s.tail(20).mean()) if len(s) >= 20 else ma5
    if last > ma5 > ma20:   status = '憭????
    elif last < ma5 < ma20: status = '蝛粹????
    else:                   status = '?渡?銝?
    return {'last': round(last,2), 'pct': round(pct,2),
            'status': status, 'chg': round(last-prev,2)}


# ????????????????????????????????????????????????????????????
# v5.0 Wrapper ?賣 ??NAS ?芸?嚗翰??憌橘?蝯曹? N/A ?摩
# ????????????????????????????????????????????????????????????

@st.cache_data(ttl=CACHE_TTL["price_data"], show_spinner=False, max_entries=10)
def get_export_yoy() -> dict | None:
    return None


@st.cache_data(ttl=CACHE_TTL["price_data"], show_spinner=False, max_entries=10)
def get_business_indicator() -> dict | None:
    return None

