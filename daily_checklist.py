"""
daily_checklist.py v6.0 — Squid Proxy 模式
🔄 三大法人：TWSE BFI82U via Squid Proxy（5天回溯，row[3] 買賣超，元÷1e8=億）
🔄 融資餘額：5 段備援 — rwd MI_MARGN → HiStock → Goodinfo → Yahoo → 鉅亨網（仟元÷100,000=億）
🔄 ADL / yfinance / FinMind：不受 geo-block 影響，直連
"""
import requests, pandas as pd, datetime, os, time, re
import urllib3
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.ttls import TTL_1HOUR
# v18.325 PR-C: 融資餘額紅線改用既有 SSOT（原 inline 3400，§3.3 反捏造）
from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,  # v18.326 PR-D: 融資黃線
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _bps():
    try:
        from tw_stock_data_fetcher import build_proxy_session as _b
        s = _b()
    except Exception:
        s = requests.Session()
    s.verify = False
    return s

import streamlit as st

DISABLE_TWSE: bool = True  # 🚫 TWSE 已永久停用


# ── 快取基礎設施 (v18.344 PR-N1 抽至 shared/cache_layer.py)─────────────
# 原 v4.5 SSOT cache 邏輯遷出,保留 re-export 維持向後相容(caller 不必改)。
from data_config import TTL_CONFIG as _TTL_CFG, PKL_DIR as _PKL_DIR  # noqa: F401
from shared.cache_layer import (
    _CACHE_SENTINEL,  # noqa: F401
    _pkl_get,         # noqa: F401
    _pkl_put,         # noqa: F401
    _pkl_clear_all,   # noqa: F401
)


import plotly.graph_objects as go

# v18.344 PR-N1:`st.secrets.get(...)` 即使無 secrets.toml 也會觸發 StreamlitSecretNotFoundError
# (st.secrets 物件 lazy parse),原 getattr 防護不夠;改 try/except 包,僅在 secrets.toml
# 存在時走 st.secrets,否則 fallback 到 os.environ(headless / CLI test 場景無 secrets)。
try:
    FINMIND_TOKEN = (getattr(st, 'secrets', {}).get('FINMIND_TOKEN', '')
                     or os.environ.get('FINMIND_TOKEN', ''))
except Exception:
    FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN', '')
HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}
# v18.344 PR-N1:COLORS_7 抽至 macro_ui_components.py(L4 Render),re-export 維持相容
from macro_ui_components import COLORS_7  # noqa: F401
INTL_MAP = {"道瓊工業 DJI":"^DJI","納斯達克 IXIC":"^IXIC","費城半導體 SOX":"^SOX","10Y公債殖利率":"^TNX","美元指數 DXY":"DX-Y.NYB"}
INTL_UNIT = {k:("%" if "殖利率" in k else "指數") for k in INTL_MAP}
TW_MAP   = {"台股加權指數":"^TWII","新台幣匯率":"TWD=X"}
TW_UNIT  = {"台股加權指數":"pts","新台幣匯率":"TWD/USD"}
TECH_MAP = {"台積電 ADR":"TSM","微軟 MSFT":"MSFT","蘋果 AAPL":"AAPL","谷歌 GOOGL":"GOOGL","輝達 NVDA":"NVDA","AMD":"AMD","博通 AVGO":"AVGO"}

# v18.344 PR-N1:_num / _TW_TZ_DL / _tw_today_dl / _recent_date 抽至 shared/macro_compute.py
# (L2 純函式),re-export 維持向後相容(無 caller 直引但保險起見)
from shared.macro_compute import (
    _num,           # noqa: F401
    _TW_TZ_DL,      # noqa: F401
    _tw_today_dl,   # noqa: F401
    _recent_date,   # noqa: F401
)

# ═══════════════════════════════════════════════
# 三大法人 (v18.346 PR-N3 抽至 daily_data_fetchers.py)
# ═══════════════════════════════════════════════
from daily_data_fetchers import fetch_institutional  # noqa: F401


# ═══════════════════════════════════════════════
# 融資餘額（NAS 中繼站）
# ═══════════════════════════════════════════════
def fetch_margin_balance(date_str=None):
    """融資餘額 — FinMind → MI_MARGN → HiStock → Goodinfo → Yahoo → 鉅亨網，單位：億元
    v6：Plan 0 = FinMind TaiwanStockTotalMarginPurchaseShortSale（Streamlit Cloud 海外 IP 唯一可達來源）
    v5：Plan A = MI_MARGN（mi-margn.html 後端 JSON），扁平 data/fields 解析。"""
    _mb_ttl = _TTL_CFG.get('margin_balance', 600)
    _mb_cached = _pkl_get('margin_balance', _mb_ttl)
    if _mb_cached is not _CACHE_SENTINEL:
        return _mb_cached

    # 取最近一個交易日（週末往前推）
    _now_mb = datetime.datetime.now()
    while _now_mb.weekday() >= 5:
        _now_mb -= datetime.timedelta(days=1)
    _ds_mb = _now_mb.strftime('%Y%m%d')

    # 方案0: FinMind TaiwanStockTotalMarginPurchaseShortSale（v6 新增）
    # 治本：海外 IP 也可達，原 TWSE/HiStock/Goodinfo/Yahoo/cnyes 全部需要台灣 IP
    try:
        from leading_indicators import finmind_get as _fm_mb
        _tok_mb = os.environ.get('FINMIND_TOKEN', '')
        _start_mb = (_now_mb - datetime.timedelta(days=10)).strftime('%Y%m%d')
        _df_mb0 = _fm_mb('TaiwanStockTotalMarginPurchaseShortSale', '', _start_mb, _ds_mb, _tok_mb)
        if _df_mb0 is not None and not _df_mb0.empty:
            _cols_mb0 = list(_df_mb0.columns)
            _bal_cols0 = [c for c in _cols_mb0 if any(k in c for k in
                          ['alance', '餘額', 'amount', 'Amount'])]
            _df_mb0 = _df_mb0.sort_values('date')
            _last_d0 = str(_df_mb0['date'].iloc[-1])
            _grp0 = _df_mb0[_df_mb0['date'] == _last_d0]
            _v_mb0 = None
            if 'name' in _cols_mb0 and _bal_cols0:
                # 長格式：每一列代表「融資/融券」單一指標
                for _, _r0 in _grp0.iterrows():
                    _nm0 = str(_r0.get('name', '')).lower()
                    if not ('融資' in _nm0 or 'margin' in _nm0 or 'purchase' in _nm0):
                        continue
                    for _bc0 in _bal_cols0:
                        try:
                            _raw0 = float(str(_r0.get(_bc0, 0)).replace(',', '') or 0)
                        except Exception:
                            continue
                        # 自動偵測單位：億 / 元 / 千元 / 萬元
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
                print(f'[融資餘額/FinMind] ✅ {_v_mb0}億 date={_last_d0}')
                return _pkl_put('margin_balance', _v_mb0)
            print(f'[融資餘額/FinMind] ⚠️ date={_last_d0} 解析未命中（cols={_cols_mb0[:6]}）')
        else:
            print('[融資餘額/FinMind] ⚠️ 回傳空 DataFrame')
    except Exception as _e_mb0:
        print(f'[融資餘額/FinMind] ❌ {type(_e_mb0).__name__}: {_e_mb0}')

    # 方案A: TWSE rwd MI_MARGN（單次嘗試最近交易日；MS→ALL 雙 selectType 容錯）
    # 對齊 leading_indicators._twse_margin_day 已驗證有效邏輯：頂層 data/fields，
    # 欄名偵測「融資...餘額」(排除「限」)，reversed 取彙總列，仟元÷100,000=億
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
                print(f'[融資餘額/MI_MARGN/{_sel_mb}] ⚠️ date={_ds_mb} stat={_stat_mb}')
                continue
            _fields_mb = [str(_f) for _f in _resp_mb.get('fields', [])]
            _fa_col = next((_i for _i, _f in enumerate(_fields_mb)
                           if '融資' in _f and '餘額' in _f and '限' not in _f), 6)
            for _row_mb in reversed(_resp_mb.get('data', [])):
                if not _row_mb or len(_row_mb) <= _fa_col:
                    continue
                _vs_mb = str(_row_mb[_fa_col]).replace(',', '').replace(' ', '').strip()
                try:
                    _v_raw_mb = float(_vs_mb)
                except Exception:
                    continue
                if _v_raw_mb > 10_000_000:  # 仟元 → 億
                    _v_mb = round(_v_raw_mb / 100_000, 1)
                    if 100 < _v_mb < 30_000:
                        print(f'[融資餘額/MI_MARGN/{_sel_mb}] ✅ {_v_mb}億 date={_ds_mb}')
                        return _pkl_put('margin_balance', _v_mb)
            print(f'[融資餘額/MI_MARGN/{_sel_mb}] ⚠️ date={_ds_mb} 解析未命中（fa_col={_fa_col}）')
            _hit_mb = True
        if not _hit_mb:
            print(f'[融資餘額/MI_MARGN] ⚠️ MS/ALL 皆無回應')
    except Exception as _e_mb:
        print(f'[融資餘額/MI_MARGN] ❌ {type(_e_mb).__name__}: {_e_mb}')

    # 方案B: HiStock 網頁爬蟲（公開，BeautifulSoup）
    try:
        from proxy_helper import fetch_url as _furl_hi
        from bs4 import BeautifulSoup as _BS_mb
        _rh = _furl_hi('https://histock.tw/stock/margin.aspx', timeout=12)
        if _rh is not None:
            _soup_h = _BS_mb(_rh.text, 'html.parser')
            # 搜尋含「融資餘額」文字附近的數字（億元）；L3: 使用頂層已匯入的 re
            _txt_h = _soup_h.get_text(' ', strip=True)
            _m_h = re.search(r'融資餘額[^\d]{0,20}([\d,]+(?:\.\d+)?)\s*億', _txt_h)
            if _m_h:
                _v_h = round(float(_m_h.group(1).replace(',', '')), 1)
                if 100 < _v_h < 30_000:
                    print(f'[融資餘額/HiStock] ✅ {_v_h}億')
                    return _pkl_put('margin_balance', _v_h)
    except Exception as _e_hi:
        print(f'[融資餘額/HiStock] ❌ {type(_e_hi).__name__}: {_e_hi}')

    # 方案C: Goodinfo 加權指數融資融券日統計（公開 HTML，BeautifulSoup）
    # 補強：表頭判斷放寬（任一含「融資」即可）+ 整頁正則 fallback
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
            # 第一輪：表頭含「融資」的表格
            for _tbl in _soup_g.find_all('table'):
                _heads = ' '.join(th.get_text(' ', strip=True)
                                  for th in _tbl.find_all('th'))
                if '融資' not in _heads:
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
            # 第二輪 fallback：整頁正則「融資餘額 12,345 億」
            if _gi_val is None:
                _txt_g = _soup_g.get_text(' ', strip=True)
                _m_g = re.search(r'融資餘額[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*億', _txt_g)
                if _m_g:
                    _vg2 = round(float(_m_g.group(1).replace(',', '')), 1)
                    if 100 < _vg2 < 30_000:
                        _gi_val = _vg2
            if _gi_val is not None:
                print(f'[融資餘額/Goodinfo] ✅ {_gi_val}億')
                return _pkl_put('margin_balance', _gi_val)
            print('[融資餘額/Goodinfo] ⚠️ 表格 + 正則皆未命中')
    except Exception as _e_gi:
        print(f'[融資餘額/Goodinfo] ❌ {type(_e_gi).__name__}: {_e_gi}')

    # 方案D: Yahoo 股市資券餘額（HTML，整頁正則）
    try:
        from proxy_helper import fetch_url as _furl_yh
        from bs4 import BeautifulSoup as _BS_yh
        _ry = _furl_yh('https://tw.stock.yahoo.com/margin-balance', timeout=12)
        if _ry is not None:
            _ry.encoding = 'utf-8'
            _txt_y = _BS_yh(_ry.text, 'html.parser').get_text(' ', strip=True)
            # Yahoo 顯示「融資餘額 1,234 億」或「融資餘額(億) 1,234」
            _m_y = re.search(r'融資餘額[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*(?:億|$)', _txt_y)
            if _m_y:
                _vy = round(float(_m_y.group(1).replace(',', '')), 1)
                if 100 < _vy < 30_000:
                    print(f'[融資餘額/Yahoo] ✅ {_vy}億')
                    return _pkl_put('margin_balance', _vy)
            print('[融資餘額/Yahoo] ⚠️ 正則未命中')
    except Exception as _e_yh:
        print(f'[融資餘額/Yahoo] ❌ {type(_e_yh).__name__}: {_e_yh}')

    # 方案E: 鉅亨網盤後資券餘額（HTML，整頁正則）
    try:
        from proxy_helper import fetch_url as _furl_cy
        from bs4 import BeautifulSoup as _BS_cy
        _rc = _furl_cy('https://www.cnyes.com/twstock/a_margin.aspx', timeout=12)
        if _rc is not None:
            _rc.encoding = 'utf-8'
            _txt_c = _BS_cy(_rc.text, 'html.parser').get_text(' ', strip=True)
            _m_c = re.search(r'融資餘額[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*(?:億|$)', _txt_c)
            if _m_c:
                _vc = round(float(_m_c.group(1).replace(',', '')), 1)
                if 100 < _vc < 30_000:
                    print(f'[融資餘額/cnyes] ✅ {_vc}億')
                    return _pkl_put('margin_balance', _vc)
            print('[融資餘額/cnyes] ⚠️ 正則未命中')
    except Exception as _e_cy:
        print(f'[融資餘額/cnyes] ❌ {type(_e_cy).__name__}: {_e_cy}')

    return None


# v18.344 PR-N1:evaluate_market_status_v4_final 抽至 shared/macro_compute.py(L2 純函式)
from shared.macro_compute import evaluate_market_status_v4_final  # noqa: F401


# ═══════════════════════════════════════════════
# yfinance (v18.345 PR-N2 抽至 daily_data_fetchers.py)
# ═══════════════════════════════════════════════
# caller 用 `from daily_checklist import fetch_single` 形式,re-export 維持 0 改動
from daily_data_fetchers import (  # noqa: F401
    fetch_single,
    fetch_flow_snapshot,
)

# v18.346 PR-N3:_fetch_otc_via_finmind 抽至 daily_data_fetchers.py
from daily_data_fetchers import _fetch_otc_via_finmind  # noqa: F401



# ═════════════════════════════════════════════════════
# 騰落指標（ADL）— FinMind 唯一來源（🚫 TWSE MI_INDEX 已移除）
# ═════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════
# 騰落指標（ADL）— 完整重寫版
# 不用 @st.cache_data（在 thread 中失敗），改用 pickle cache
# 資料來源: yfinance ^TWII（🚫 TWSE MI_INDEX 已移除）
# ═════════════════════════════════════════════════════
def fetch_adl(days=60, token=None):
    """
    騰落指標 ADL v5 — yfinance ^TWII 估算（🚫 TWSE MI_INDEX 已永久停用）
    ① yfinance ^TWII  — 立即可用估算值
       並發 5 線程逐日抓取；精確值自動覆蓋估算值

    根本原因修正：TaiwanStockMarketCondition 不在 FinMind v4 有效資料集中
    """
    import datetime as _dt
    import pickle as _pk
    import os as _os2
    import time as _tm2
    import pandas as _pd_adl
# ── 日誌 helper ──────────────────────────────────────────────
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

    # ── Cache ────────────────────────────────────────────────────
    _ck = '/tmp/stock_cache/adl_data.pkl'
    _os2.makedirs('/tmp/stock_cache', exist_ok=True)
    if _os2.path.exists(_ck):
        _age = _tm2.time() - _os2.path.getmtime(_ck)
        if _age < 1800:
            try:
                _c = _pk.load(open(_ck, 'rb'))
                if _c is not None and not _c.empty:
                    _alog(f'[ADL] 快取命中 {len(_c)} 筆 (age={_age/60:.1f}min)')
                    return _c
            except Exception:
                pass

    today  = _dt.date.today()
    s_date = today - _dt.timedelta(days=days + 14)
    s_dash = s_date.strftime('%Y-%m-%d')
    e_dash = today.strftime('%Y-%m-%d')
    rows: dict = {}   # {ymd: {'up':int, 'down':int, 'is_proxy':bool}}

    # ════════════════════════════════════════════════════════════════
    # ① yfinance ^TWII — 估算（立即可用，is_proxy=True）
    # 公式：漲跌幅 ±1% ≈ ±150 家，以 900/900 為基準
    # ════════════════════════════════════════════════════════════════
    _alog('[ADL-①] yfinance ^TWII 估算...')
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
            # [Fix] yfinance 新版可能回傳 MultiIndex columns，需先攤平
            if isinstance(_twii.columns, pd.MultiIndex):
                _twii.columns = _twii.columns.get_level_values(0)
            _twii = _twii.dropna(subset=['Close'])
            for _ix in _twii.index:
                _dk = str(_ix)[:10].replace('-', '')
                _cl = float(_twii.loc[_ix, 'Close'])
                _op = float(_twii.loc[_ix, 'Open'])
                _pct = (_cl - _op) / _op if _op > 0 else 0.0
                # 估算公式：中性=900，每±1%約±150家，限制在50~1750
                _up = max(50, min(1750, int(900 + _pct * 15000)))
                rows[_dk] = {'up': _up, 'down': max(50, 1800 - _up), 'is_proxy': True}
            _alog(f'[ADL-①] ✅ {len(rows)} 天估算完成')
        else:
            _alog('[ADL-①] ⚠️ yfinance 回傳空資料')
    except Exception as _e1:
        _alog(f'[ADL-①] ❌ {type(_e1).__name__}: {_e1}')

    # Edge Case 6: 完全沒有資料（🚫 TWSE MI_INDEX 已移除）
    if not rows:
        _alog('[ADL] ⚠️ 所有來源均失敗，回傳 None')
        return None

    # ── 組合 DataFrame ──────────────────────────────────────────
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

    # Edge Case 7: 過濾後仍無記錄
    if not _records:
        _alog('[ADL] ⚠️ 有效記錄為空')
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
        f'[ADL] ✅ 完成 {len(df)} 筆 '
        f'精確={_exact_n} 估算={_proxy_n} '
        f'上漲佔比:{df["ad_ratio"].iloc[-1]:.1f}%'
    )

    # ── 快取 ────────────────────────────────────────────────────
    try:
        with open(_ck, 'wb') as _f:
            _pk.dump(df.tail(days).reset_index(drop=True), _f)
    except Exception:
        pass

    return df.tail(days).reset_index(drop=True)


# ── 4. Self-Test（邊界測試）────────────────────────────────────
def _adl_selftest():
    """在 Colab 外部可執行此函數驗證解析邏輯"""
    import re

    def _parse(s):
        m = re.match(r'^([\d,]+)', str(s).strip())
        return int(m.group(1).replace(',', '')) if m else 0

    # Test 1: 正常格式
    assert _parse('7,768(403)') == 7768, "Test1 failed"
    # Test 2: 無括號
    assert _parse('3,644') == 3644, "Test2 failed"
    # Test 3: 空字串
    assert _parse('') == 0, "Test3 failed"
    # Test 4: 只有漢字（類型欄誤傳）
    assert _parse('上漲') == 0, "Test4 failed"
    # Test 5: 大值
    assert _parse('19,039') == 19039, "Test5 failed"
    print("[ADL selftest] ✅ 全部通過")




# v18.344 PR-N1:UI 渲染元件抽至 macro_ui_components.py(L4 Render),re-export 維持相容。
# 8 個函式:_hex2rgba / _base_layout / sparkline / multi_chart /
# bar_chart_institutional / stat_card / margin_card / section_header
from macro_ui_components import (  # noqa: F401
    _hex2rgba,
    _base_layout,
    sparkline,
    multi_chart,
    bar_chart_institutional,
    stat_card,
    margin_card,
    section_header,
)

def analyze_20d_chips(stock_id: str) -> dict:
    """
    近 20 日個股籌碼集中度分析（外資 + 投信 vs 總成交量）

    指標 A 集中度 = (外資+投信) 20日淨買總和 / 20日總成交量  × 100%
    指標 B 延續性 = 20日中 (外資+投信) 淨買 > 0 的天數佔比 (%)

    買賣超單位：張 (FinMind TaiwanStockTotalInstitutionalInvestors)
    成交量單位：張 (FinMind TaiwanStockPrice Trading_Volume)
    → 兩者單位相同，集中度為無因次百分比
    """
    import datetime as _dt20
    try:
        import pandas as _pd20
        _start = (_dt20.date.today() - _dt20.timedelta(days=50)).strftime('%Y-%m-%d')
        _base  = 'https://api.finmindtrade.com/api/v4/data'
        _hdrs  = {'Authorization': f'Bearer {FINMIND_TOKEN}'} if FINMIND_TOKEN else {}
        _common = {'token': FINMIND_TOKEN} if FINMIND_TOKEN else {}

        # ── 1. 個股三大法人每日買賣超（單位：張）────────────────────
        _p_inst = {**_common, 'dataset': 'TaiwanStockTotalInstitutionalInvestors',
                   'stock_id': stock_id, 'start_date': _start}
        _r_inst = _bps().get(_base, params=_p_inst, headers=_hdrs, timeout=20, verify=False)
        _j_inst = _r_inst.json()
        _inst_ok = (not (isinstance(_j_inst.get('status'), int)
                         and _j_inst['status'] >= 400)) and bool(_j_inst.get('data'))
        if not _inst_ok:
            return {'error': f'法人資料失敗 status={_j_inst.get("status")}',
                    'signal': '⚫ 資料不足'}

        _df_i = _pd20.DataFrame(_j_inst['data'])
        _df_i.columns = [str(c).lower() for c in _df_i.columns]
        _df_i['buy']  = _pd20.to_numeric(_df_i.get('buy',  0), errors='coerce').fillna(0)
        _df_i['sell'] = _pd20.to_numeric(_df_i.get('sell', 0), errors='coerce').fillna(0)
        _df_i['net']  = _df_i['buy'] - _df_i['sell']
        # 辨識外資 / 投信（相容 FinMind 英文或中文 name 欄位）
        _is_fi = _df_i['name'].apply(
            lambda n: str(n) == 'Foreign_Investor' or ('外資' in str(n) and '自營' not in str(n)))
        _is_tr = _df_i['name'].apply(
            lambda n: str(n) == 'Investment_Trust' or '投信' in str(n))
        _df_fi = _df_i[_is_fi][['date','net']].rename(columns={'net':'foreign_net'})
        _df_tr = _df_i[_is_tr][['date','net']].rename(columns={'net':'trust_net'})
        _df_m  = _pd20.merge(_df_fi, _df_tr, on='date', how='outer').fillna(0)
        _df_m['combined'] = _df_m['foreign_net'] + _df_m['trust_net']
        _df_m  = _df_m.sort_values('date').tail(20)

        # ── 2. 每日成交量（單位：張，來自 TaiwanStockPrice）─────────
        _p_vol = {**_common, 'dataset': 'TaiwanStockPrice',
                  'stock_id': stock_id, 'start_date': _start}
        _r_vol = _bps().get(_base, params=_p_vol, headers=_hdrs, timeout=20, verify=False)
        _j_vol = _r_vol.json()
        _vol_ok = (not (isinstance(_j_vol.get('status'), int)
                        and _j_vol['status'] >= 400)) and bool(_j_vol.get('data'))
        if not _vol_ok:
            return {'error': '價量資料失敗', 'signal': '⚫ 資料不足'}

        _df_v  = _pd20.DataFrame(_j_vol['data'])
        _df_v.columns = [str(c).lower() for c in _df_v.columns]
        # 相容 trading_volume / volume 欄名
        _vcol  = next((c for c in _df_v.columns if 'trading_volume' in c or c == 'volume'), None)
        if _vcol is None:
            return {'error': '找不到成交量欄位', 'signal': '⚫ 資料不足'}
        _df_v[_vcol] = _pd20.to_numeric(_df_v[_vcol], errors='coerce').fillna(0)
        _df_v  = _df_v[['date', _vcol]].rename(columns={_vcol: 'volume'})
        _df_v  = _df_v.sort_values('date').tail(20)

        # ── 3. 合併：只取法人與成交量均有資料的交易日 ──────────────
        _df    = _pd20.merge(_df_m, _df_v, on='date', how='inner').tail(20)
        if len(_df) < 5:
            return {'error': f'有效天數不足（{len(_df)}天）', 'signal': '⚫ 資料不足'}

        # ── 4. 計算兩大指標 ──────────────────────────────────────────
        _tot_net = float(_df['combined'].sum())          # 外+投 累計淨買（張）
        _tot_vol = float(_df['volume'].sum())            # 總成交量（張）
        _concentration = (_tot_net / _tot_vol * 100) if _tot_vol > 0 else 0.0   # %
        _pos_days  = int((_df['combined'] > 0).sum())
        _continuity = _pos_days / len(_df) * 100                                  # %

        # ── 5. 判定訊號 ──────────────────────────────────────────────
        if _concentration > 5 and _continuity > 50:
            _signal = '🔥 大戶吸籌'
        elif _concentration < -5:
            _signal = '🔴 大戶倒貨'
        else:
            _signal = '🟡 籌碼發散'

        print(f'[20d_chips/{stock_id}] 集中度={_concentration:.2f}% 延續性={_continuity:.0f}% '
              f'days={len(_df)} signal={_signal}')
        return {
            'concentration': round(_concentration, 2),   # %（可正可負）
            'continuity':    round(_continuity, 1),       # 0~100%
            'signal':        _signal,
            'days':          len(_df),
            'pos_days':      _pos_days,
            'total_net_k':   round(_tot_net / 1e3, 1),   # 千張
            'total_vol_k':   round(_tot_vol / 1e3, 1),   # 千張
            'error':         None,
        }
    except Exception as _e20:
        print(f'[20d_chips/{stock_id}] ❌ {type(_e20).__name__}: {_e20}')
        return {'error': str(_e20), 'signal': '⚫ 計算失敗'}


# v18.344 PR-N1:analyze_20d_chips_from_df 抽至 shared/macro_compute.py(L2 純函式)。
# 三個 caller (tab_macro / tab_stock x2 / tab_stock_grp) 用 `from daily_checklist
# import analyze_20d_chips_from_df` 形式,re-export 維持 0 caller 改動。
from shared.macro_compute import analyze_20d_chips_from_df  # noqa: F401


# v18.301 §8.3 拆檔:calc_stats 已提取至 shared/stats_helpers.py(L0 純函式)。
# 此處保 re-export 維持向後相容(tab_macro.py:358 等 caller 0 改)。
from shared.stats_helpers import calc_stats  # noqa: F401


# ═══════════════════════════════════════════════════════════
# v5.0 Wrapper 函數 — NAS 優先，快取裝飾，統一 N/A 邏輯
# ═══════════════════════════════════════════════════════════

@st.cache_data(ttl=TTL_1HOUR, show_spinner=False, max_entries=10)
def get_export_yoy() -> dict | None:
    return None


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False, max_entries=10)
def get_business_indicator() -> dict | None:
    return None
