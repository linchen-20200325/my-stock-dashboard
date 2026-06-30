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

# ── Streamlit Cloud 防護（PR #82/#86 升級版）────────────────
# tab_*.py 用 `from app import X`，Python 走 sys.modules['app'] 找模組。
# Cloud 上 sys.modules['__main__'] 是 Streamlit CLI binary 不是 script，
# 所以 PR #82 的 `setdefault('app', sys.modules[__name__])` 指錯模組。
# PR #86 用 ModuleType proxy + closure，但 closure 經 method.__globals__
# 解析 `_app_globals` 名稱對 Streamlit rerun 行為有依賴。
# 改為把 globals dict 塞 proxy.__dict__，每次都 refresh，徹底解耦。
import types as _types  # noqa: E402
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.ttls import TTL_30MIN, TTL_1HOUR

class _AppProxy(_types.ModuleType):
    """Proxy：`from app import X` → 從 proxy 自己 dict 拿 live globals。"""
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

# ── 台灣時間（UTC+8）─────────────────────────────────────
_TW_TZ = datetime.timezone(datetime.timedelta(hours=8))
def _tw_now(): return datetime.datetime.now(_TW_TZ)
def _tw_now_str(): return _tw_now().strftime('%Y-%m-%d %H:%M')

def _bps():
    try:
        from src.data.stock import build_proxy_session as _b
        s = _b()
    except Exception:
        s = requests.Session()
    s.verify = False
    return s

print('[INFO] main.py v3.0 戰情室 載入完成')

from src.data.core import StockDataLoader, _LOADER_VERSION  # noqa: E402
# ── 新增模組（根據說明書 v1.0）──────────────────────────────
# ── v3.0 新增模組（§5-§11）──────────────────────────────────
from src.ui.etf import (  # noqa: E402
    render_etf_single, render_etf_portfolio,
    render_etf_ai,
    render_sector_heatmap,
)
from src.ui.pages import render_data_health_raw  # noqa: E402
from src.ui.pages import render_api_diagnostic  # noqa: E402
from src.ui.tabs import render_grape_ladder  # noqa: E402
from src.config import TAIWAN_ADVISOR_PERSONA as _PERSONA  # noqa: E402

def _get_secret(_key: str) -> str:
    """st.secrets 優先,降級 os.environ。

    st.secrets 在「無 secrets.toml」(本機 / CI fast lane)會 raise
    StreamlitSecretNotFoundError;在「streamlit 被 test stub 取代」時甚至缺
    `secrets` 屬性(AttributeError)。以 try/except 降級確保 app import 不炸
    (對齊 config.py EX-L0-1 + Fund data_registry 的 st.secrets guard)。
    """
    try:
        _v = st.secrets.get(_key, '')
    except Exception:
        _v = ''
    return _v or os.environ.get(_key, '')


api_key       = _get_secret('GEMINI_API_KEY')   # [Fixed] st.secrets 優先 + 缺失降級
FINMIND_TOKEN = _get_secret('FINMIND_TOKEN')    # [Fixed] st.secrets 優先 + 缺失降級

# [Fixed] 同步到 os.environ，讓子模組頂層讀取能拿到正確值
if FINMIND_TOKEN:
    os.environ['FINMIND_TOKEN'] = FINMIND_TOKEN
if api_key:
    os.environ['GEMINI_API_KEY'] = api_key

def _get_fm_token():
    """每次動態讀取最新 Token：st.secrets > os.environ"""
    _tok = (getattr(st, 'secrets', {}).get('FINMIND_TOKEN')
            or os.environ.get('FINMIND_TOKEN', ''))
    return _tok

st.set_page_config(page_title='台股AI戰情室 v3.0', layout='wide',
                   page_icon='📊', initial_sidebar_state='collapsed')

# ── OAuth callback：URL 帶 ?code= 時自動換 token（必須早於其他 query_params 操作）
# v18.400 D4:oauth_state 已從 src/ui/pages 歸位 src/data/portfolio
try:
    from src.data.portfolio.oauth_state import handle_oauth_callback as _oauth_cb
    _oauth_cb()
except Exception as _oauth_err:
    print(f'[oauth callback] {_oauth_err}')

# ── App 初始化閘門（每個 Session 僅執行一次，防重複迴圈）────────────
if '_app_boot_done' not in st.session_state:
    st.session_state['_app_boot_done'] = True
    # 首次啟動清除舊快取，後續 rerun 不再執行（防 API Storm）
    try:
        st.cache_data.clear()
    except Exception:
        pass
    # [Phase 3] 從 URL query_params 恢復關鍵狀態（手機斷線重連可保留設定）
    try:
        _qp = st.query_params
        if _qp.get('chips') == '1':
            st.session_state['chips_loaded'] = True
        _qp_sid = _qp.get('sid')
        if _qp_sid and isinstance(_qp_sid, str) and _qp_sid.isdigit():
            st.session_state['_qp_sid'] = _qp_sid  # 個股 Tab 啟動時讀取
    except Exception as _qpe:
        print(f'[query_params restore] {_qpe}')

# [Phase 3] 雙向同步：session_state → query_params（讓重連後 URL 仍帶狀態）
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

# ════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════
# v18.302 §8.3 app.py 拆檔:parse_stocks 已提至 shared/parse_helpers.py(L0)。
# 此處保 re-export 維持向後相容(tab_stock_grp.py:52 等 caller 0 改)。
from shared.parse_helpers import parse_stocks  # noqa: F401

# ── Gemini 金鑰池（做法 B：多帳號 key 自動換手，分散額度 / 速率限制）──────
# 讀 GEMINI_API_KEY + GEMINI_API_KEY_2 .. _6（st.secrets 優先，os.environ fallback）。
# gemini_call 以 round-robin 起手 key（不同呼叫/不同 tab 從不同把 key 開始 → 分散負載），
# 任一把遇到 429（速率/額度滿）或 403（無效）時自動換下一把，全部用盡才報錯。
_GEMINI_KEY_NAMES = ['GEMINI_API_KEY'] + [f'GEMINI_API_KEY_{_i}' for _i in range(2, 7)]
_gemini_rr = [0]  # round-robin 起手索引（每次呼叫遞增）


def _gemini_keys() -> list:
    """收集所有可用 Gemini API key（去重保序）。st.secrets 優先，os.environ fallback。"""
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
        return '⚠️ 請設定 GEMINI_API_KEY（可另加 GEMINI_API_KEY_2 ~ _6 分散額度）'
    # round-robin 起手：不同呼叫從不同把 key 開始，自然把負載分散到各帳號
    _start = _gemini_rr[0] % len(_keys)
    _gemini_rr[0] = (_gemini_rr[0] + 1) % 1_000_000
    _keys = _keys[_start:] + _keys[:_start]
    # 2026-03 有效模型：1.5系列全部退役，2.5為主力
    _models = ['gemini-2.5-flash-lite', 'gemini-2.5-flash',
               'gemini-2.0-flash', 'gemini-2.0-flash-lite']
    for _model in _models:
        # Gemini 2.5 預設開「思考模式」，思考 token 會跟輸出共用 maxOutputTokens 額度
        # → 常導致回覆只生成一半就被截斷。白話摘要不需深度推理，關閉思考（thinkingBudget=0）。
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
                    # safety 攔截：換 key 無助益 → 直接換下一個 model
                    if _cands and _cands[0].get('finishReason', '') == 'SAFETY':
                        break
                    continue  # 空回覆 → 試下一把 key
                elif _r.status_code == 400:
                    _err_msg = (_r.json() if _r.text else {}).get('error', {}).get('message', _r.text[:100])
                    print(f'[Gemini/{_model}] 400 Bad Request: {_err_msg}')
                    break  # 設定/prompt 問題，換 key 無用 → 換下一個 model
                elif _r.status_code == 403:
                    print(f'[Gemini/{_model}] 403 第 {_ki+1} 把 key 無效/無權限 → 換下一把')
                    continue  # 換 key
                elif _r.status_code == 404:
                    break  # 此 model 不存在 → 換下一個 model
                elif _r.status_code == 429:
                    print(f'[Gemini/{_model}] 429 第 {_ki+1} 把 key 額度/速率滿 → 換下一把')
                    continue  # 換 key（做法 B 核心：分散到別把帳號）
                else:
                    print(f'[Gemini/{_model}] HTTP {_r.status_code}: {_r.text[:200]}')
                    continue  # 換 key
            except Exception as _ge:
                print(f'[Gemini/{_model}] key#{_ki+1} {type(_ge).__name__}: {_ge}')
                continue  # 換 key
    return ('⚠️ AI 服務暫時無法使用（所有 key 與模型都試過了）—— '
            '請確認各把金鑰額度，或稍後再試')

# ── 本地快取（SQLite + Pickle 雙軌）───────────────────────
# v18.404 B3-α:cache helper 50 LOC 抽至 shared/app_cache.py(thin shim 保 caller API)。
from shared.app_cache import _cache_key, _load_cache, _save_cache, _CACHE_DIR  # noqa: F401

@st.cache_resource
def _get_loader(_v: str = _LOADER_VERSION):
    """快取單一 StockDataLoader 實例，避免每次 cache miss 都重新 login。

    `_v` 綁定 `data_loader._LOADER_VERSION`：改動 loader 邏輯並 bump 版本後，
    cache key 隨之改變 → 自動建立新實例，避免 Streamlit hot-reload 後仍用到
    舊實例的舊方法碼（stale @st.cache_resource，PR #44 NoneType 殘留即此故）。
    """
    return StockDataLoader()

def _expected_latest_trading_date():
    d = datetime.date.today()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d

@st.cache_data(ttl=TTL_30MIN, max_entries=10)
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
                # 5 個 calendar day 內視為新鮮（涵蓋週末 + 1 個連假）；超過 → 強制重抓
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
        # v18.351 PR-Q1 S-PROV-1 phase 19:確保 source/fetched_at 存在(§2.2)。
        # data_loader.get_combined_data 內部 fetchers (phase 15/16) 已寫 attrs;
        # 若上游缺(備援路徑),setdefault 補通用標籤 — 不覆蓋既有值
        result.attrs.setdefault('source', 'app:fetch_price_data:data_loader.get_combined_data')
        result.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
    except Exception:
        pass
    _save_cache('price', sid, (result, name), str(days))
    return result, name, None

@st.cache_data(ttl=TTL_30MIN, max_entries=10)
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
        print(f'[股利REST] {sid} status={_div_jd.get("status")}')
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
    # ── 備援2: yfinance（v18.209 K5：改走 yf_proxy.cached_dividends，proxy+cache 統一）──
    if avg_div == 0:
        try:
            from src.data.proxy import cached_dividends as _yp_div
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

    # ── 備援3: TWSE 除權息資料（官方，免Token）──
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
                    # 欄位：[日期, 股票代號, 名稱, 除權息前收盤, 開始交易基準價, 現金股利, 股票股利, ...]
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

    # v18.351 PR-Q1 S-PROV-1 phase 19:stderr 記 provenance(§2.2 audit trail)。
    # 介面 0 改:return 仍是 (avg_div, yearly, source) 3-tuple,caller 由 source 欄已可追溯;
    # fetched_at 走 stderr log(tuple 增欄會破 caller)
    try:
        import sys as _sys_prov
        _now = pd.Timestamp.now('UTC').isoformat()
        print(f'[fetch_dividend_data] sid={sid} source={source or "FAIL"} '
              f'fetched_at={_now} avg_div={avg_div:.4f} years={len(yearly)}',
              file=_sys_prov.stderr)
    except Exception:
        pass
    return avg_div, yearly, source

@st.cache_data(ttl=TTL_1HOUR, max_entries=10)
def fetch_financials(sid, industry: str = ""):
    """
    合約負債 + 固定資產 + 資本支出 — v3.35 簡化版
    100% FinMind（免費版已確認 status=200）
    type 欄位為主鍵，比 origin_name 更可靠。
    """
    import datetime as _dtf
    try:
        from src.data.stock import build_proxy_session as _bps_fin
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

    # ── Step 1: BalanceSheet → 合約負債 + 固定資產 ──────────────
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
            # 取最新一季
            _dates = sorted(set(r.get("date","") for r in _rows), reverse=True)
            _latest_dt = _dates[0] if _dates else None
            _latest = [r for r in _rows if r.get("date") == _latest_dt]
            print(f"[FM-BS] Latest={_latest_dt} rows={len(_latest)}")

            # 合約負債
            _CL_TYPES = ["CurrentContractLiabilities","ContractLiabilities"]
            _CL_NAMES = ["合約負債","契約負債","預收款項"]
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
                print(f"[FM-BS] ✅ 合約負債={cl/1e8:.2f}億")

            # 固定資產
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
                    if any(_k in _n for _k in ["不動產、廠房及設備","固定資產"]):
                        _v = float(str(_row.get("value",0)).replace(",","") or 0)
                        if _v > 0:
                            cx = _v
                            cx_src = "FinMind-name"
                            break
            if cx:
                print(f"[FM-BS] ✅ 固定資產={cx/1e8:.2f}億")
    except Exception as _e_bs:
        err_msg = f"FinMind-BS:{type(_e_bs).__name__}:{_e_bs}"
        fetch_errors.append(err_msg)
        print(f"[FM-BS] ❌ {err_msg}")

    # ── Step 2: CashFlowsStatement → 資本支出 ────────────────────
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
            _CX_NAMES = ["取得不動產、廠房及設備","購置不動產、廠房及設備","資本支出"]
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
                print(f"[FM-CF] ✅ 資本支出={_capex/1e8:.2f}億")
    except Exception as _e_cf:
        fetch_errors.append(f"FinMind-CF:{type(_e_cf).__name__}:{_e_cf}")
        print(f"[FM-CF] ❌ {_e_cf}")

    def _fmt(v): return f"{v/1e8:.1f}" if v else "-"
    print(f"[FIN] {sid}: cl={_fmt(cl)}億  cx={_fmt(cx)}億  capex={_fmt(_capex)}億")
    # v18.351 PR-Q1 S-PROV-1 phase 19:stderr 記 provenance(§2.2)。
    # 介面 0 改:cl_src/cx_src/cx_src_capex 3 個 source 欄已在 tuple 內,fetched_at 走 stderr。
    try:
        import sys as _sys_prov_fin
        _now_f = pd.Timestamp.now('UTC').isoformat()
        print(f'[fetch_financials] sid={sid} cl_src={cl_src or "-"} cx_src={cx_src or "-"} '
              f'capex_src={cx_src_capex or "-"} fetched_at={_now_f} '
              f'errors={len(fetch_errors)}',
              file=_sys_prov_fin.stderr)
    except Exception:
        pass
    return cl, cx, _capex, cl_src, cx_src, cx_src_capex, fetch_errors


@st.cache_data(ttl=TTL_1HOUR, max_entries=10)
def fetch_revenue(sid):
    try:
        loader = _get_loader()
        result = loader.get_monthly_revenue(sid)
        if result is None:
            return None, '月營收：內部回傳None'
        # v18.351 PR-Q1 S-PROV-1 phase 19:DataFrame 走 attrs(schema-additive)
        _df_attr = result[0] if isinstance(result, tuple) else result
        try:
            if hasattr(_df_attr, 'attrs'):
                _df_attr.attrs.setdefault('source',
                    'app:fetch_revenue:data_loader.get_monthly_revenue')
                _df_attr.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        if isinstance(result, tuple):
            return result
        return result, None  # single value
    except Exception as e:
        print(f"[fetch_revenue] {e}")
        return None, str(e)

@st.cache_data(ttl=TTL_1HOUR, max_entries=10)
def fetch_quarterly(sid, _ver=4):   # _ver 改變即清除舊快取
    try:
        loader = _get_loader()
        result = loader.get_quarterly_data(sid)
        if result is None:
            return None, '季財報：內部回傳None'
        # v18.351 PR-Q1 S-PROV-1 phase 19:DataFrame 走 attrs(schema-additive)
        _df_attr_q = result[0] if isinstance(result, tuple) else result
        try:
            if hasattr(_df_attr_q, 'attrs'):
                _df_attr_q.attrs.setdefault('source',
                    'app:fetch_quarterly:data_loader.get_quarterly_data')
                _df_attr_q.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        if isinstance(result, tuple):
            return result
        return result, None
    except Exception as e:
        print(f"[fetch_quarterly] {e}")
        return None, str(e)

@st.cache_data(ttl=TTL_1HOUR, show_spinner=False, max_entries=10)
def fetch_quarterly_extra(sid, _ver=2):   # _ver 改變即清除舊快取
    """取得近 12 季資產負債表 + 現金流量時序（合約負債、存貨、資本支出），用於前瞻動能分數"""
    try:
        loader = _get_loader()
        result = loader.get_quarterly_bs_cf(sid)
        if result is None:
            return None, 'BS/CF：內部回傳None'
        # v18.354 PR-Q4 S-PROV-1 phase 19:DataFrame 走 attrs(對齊 fetch_quarterly 模式)
        _df_attr_qe = result[0] if isinstance(result, tuple) else result
        try:
            if hasattr(_df_attr_qe, 'attrs'):
                _df_attr_qe.attrs.setdefault('source',
                    'app:fetch_quarterly_extra:data_loader.get_quarterly_bs_cf')
                _df_attr_qe.attrs.setdefault('fetched_at', pd.Timestamp.now('UTC').isoformat())
        except Exception:
            pass
        if isinstance(result, tuple):
            return result
        return result, None
    except Exception as e:
        print(f"[fetch_quarterly_extra] {e}")
        return None, str(e)

# ════════════════════════════════════════════════════════════════
# 技術指標計算 — 已抽出至 tech_indicators.py（PR P2-B Phase 1）
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# 健康度評分（0~100）— 已抽出至 scoring_helpers.py（PR P2-B Phase 3）
# ════════════════════════════════════════════════════════════════
from src.compute.scoring import (  # noqa: E402
    health_grade,
)

# ════════════════════════════════════════════════════════════════
# 初學者友善說明系統 — 已抽出至 ui_widgets.py（PR P2-B Phase 2）
# ════════════════════════════════════════════════════════════════
from src.ui.render import (  # noqa: E402
    traffic_light, show_term_help,
)
# P2-B Phase 5 A/B/C/D: 4 個 TAB 全部已抽到獨立模組（app.py 9208→1394 行，−85%）
from src.ui.tabs import render_tab_edu  # noqa: E402
from src.ui.tabs import render_stock_grp  # noqa: E402
from src.ui.tabs import render_tab_stock  # noqa: E402
from src.ui.tabs import render_tab_macro  # noqa: E402

# 在先行指標 section 使用
_TERM_HELP_LI = show_term_help('PCR') + show_term_help('ADL') + show_term_help('M1B-M2')

# generate_ai_comment 已抽至 src/services/app_ai_service.py(v18.398 P5-B3-β R7)
# caller 改走 `from src.services.app_ai_service import generate_ai_comment`

# ── kpi / teacher_conclusion / signal_box 已抽至 ui_widgets.py ──

# ════════════════════════════════════════════════════════════════
# 健康度分數顯示元件
# ════════════════════════════════════════════════════════════════
def render_health_score(score, details, sid='', fund_scores=None, tech_alerts=None):
    """個股健診 v2：SVG量表 + 四維評分 + 技術警示 + 因子條形圖"""
    grade, color, css_class, emoji = health_grade(score)
    import math as _mh

    # ① SVG 半圓量表
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
        '<text x="14" y="103" fill="#8b949e" font-size="8">注意</text>'
        '<text x="48" y="18" fill="#8b949e" font-size="8">較差</text>'
        '<text x="88" y="8" fill="#8b949e" font-size="8">普通</text>'
        '<text x="127" y="18" fill="#8b949e" font-size="8">良好</text>'
        f'<text x="100" y="82" text-anchor="middle" fill="{color}" font-size="26" font-weight="900">{score}</text>'
        f'<text x="100" y="97" text-anchor="middle" fill="{color}" font-size="10">{grade}</text>'
        '</svg></div>'
    )

    # ② 四維評分
    fund_html = ''
    if fund_scores:
        _cat_ic = {'profit':'💰','growth':'📈','dividend':'🎁','valuation':'⚖️'}
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
                chk += f'<div style="font-size:9px;color:{cc};margin-top:1px;">{"✓" if cp else "✗"} {cn}</div>'
            fund_html += (
                f'<div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:7px 4px;text-align:center;">'
                f'<div style="font-size:20px;font-weight:900;color:{cl};">{sc}</div>'
                f'<div style="font-size:9px;color:#8b949e;">{ic} {lb}</div>'
                f'{chk}</div>'
            )
        fund_html += '</div>'

    # ③ 技術警示
    tech_html = ''
    if tech_alerts:
        _pc = {'🔴':TRAFFIC_RED,'🟡':TRAFFIC_YELLOW,'🟢':TRAFFIC_GREEN}
        tech_html = '<div style="margin:8px 0;"><div style="font-size:11px;color:#8b949e;margin-bottom:4px;">⚡ 技術警示</div>'
        for pri,name,sig,desc in tech_alerts[:5]:
            bc = _pc.get(pri,'#484f58')
            sc2 = TRAFFIC_RED if any(k in sig for k in ['看跌','空頭','超賣']) else (TRAFFIC_GREEN if any(k in sig for k in ['看漲','多頭']) else TRAFFIC_YELLOW)
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

    # ④ 因子條形圖
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

# ── Sidebar: 整合 AI 分析 ───────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="text-align:center;padding:8px 0;font-size:15px;font-weight:900;color:#e6edf3;">&#128202; 台股AI戰情室 v3.0</div>', unsafe_allow_html=True)
    st.markdown('---')
    _today_sb = datetime.date.today()
    _wd_sb = {0:'一',1:'二',2:'三',3:'四',4:'五',5:'六',6:'日'}[_today_sb.weekday()]
    _trade_sb = '✅ 交易日' if _today_sb.weekday() < 5 else '❌ 非交易日'
    st.caption(f'{_today_sb.strftime("%Y/%m/%d")} 週{_wd_sb}  {_trade_sb}')
    st.markdown('---')
    st.markdown('### 🤖 AI 分析')
    st.caption('頁面底部有 AI 整合報告面板')
    ai_run = False  # AI button moved to bottom panel
    st.markdown('---')
    st.success('🟢 系統正常運作中')

    # ── Google 帳號（OAuth）— ETF 組合雲端存取用 ─────────────────
    st.markdown('---')
    st.markdown('### 🔐 Google 帳號')
    try:
        from src.data.portfolio.oauth_state import (
            get_oauth_cfg as _sb_get_cfg,
            _gsa_secret as _sb_gsa,
            _sheet_id_secret as _sb_sid,
        )
        from infra.oauth import build_authorize_url as _sb_buildurl
        # 每次 rerun 動態解析，避免 module-level cache 過期
        _sb_cfg = _sb_get_cfg()
        _sb_oc = _sb_cfg is not None
    except Exception:
        _sb_oc, _sb_cfg, _sb_gsa, _sb_sid, _sb_buildurl = False, None, None, '', None
    _sb_logged = bool(st.session_state.get('gsheet_tokens'))
    if _sb_oc:
        if _sb_logged:
            st.success('🟢 已登入')
            if st.button('🚪 登出', key='btn_oauth_logout_sb',
                          use_container_width=True):
                st.session_state.pop('gsheet_tokens', None)
                st.rerun()
            # ── Google Sheet ID（集中於帳號區；ETF 組合面板可從 Drive 挑選/新建）──
            _sb_sid_cur = str(st.session_state.get('portfolio_sheet_id', '') or '').strip()
            _sb_sid_raw = st.text_input(
                'Google Sheet ID 或完整 URL（系統會自動解析 ID）',
                value=_sb_sid_cur, key='sb_portfolio_sheet_id_input',
                placeholder='貼上 https://docs.google.com/spreadsheets/d/...',
                help='貼 URL/ID 設定投組資料庫；或到「ETF 組合」Tab 從 Drive 挑選 / 一鍵新建')
            _sb_m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', _sb_sid_raw)
            _sb_sid_new = _sb_m.group(1) if _sb_m else _sb_sid_raw.strip()
            if _sb_sid_new and _sb_sid_new != _sb_sid_cur:
                st.session_state['portfolio_sheet_id'] = _sb_sid_new
            if _sb_sid_new:
                st.caption(f'✅ Sheet ID：`{_sb_sid_new}`')
            else:
                st.caption('💡 未設定 — 貼上 URL/ID 或到「ETF 組合」Tab 挑選')
        elif _sb_buildurl and _sb_cfg:
            _sb_url = _sb_buildurl(_sb_cfg['client_id'], _sb_cfg['redirect_uri'])
            st.link_button('🔐 用 Google 登入', _sb_url, use_container_width=True)
            st.caption('登入後 ETF 組合 Tab 可雲端存取')
    elif _sb_gsa and _sb_sid:
        st.caption('ℹ️ 使用 Service Account（舊版部署）')
    else:
        st.caption('⚙️ OAuth 尚未設定 — 至「ETF 組合」Tab 展開「💾 雲端儲存」設定')

    st.markdown('---')
    st.markdown('### 🔌 連線狀態')
    # [Fixed] 與 line 73-74 對齊：st.secrets 優先，os.environ fallback
    _fm_tok  = str(st.secrets.get('FINMIND_TOKEN',  os.environ.get('FINMIND_TOKEN',  '')))
    # Gemini 改看整池 key（GEMINI_API_KEY + _2~_6），任一把有設就算通
    _gm_keys  = _gemini_keys()
    _gm_slots = [_n for _n in _GEMINI_KEY_NAMES
                 if str(st.secrets.get(_n, '') or os.environ.get(_n, '') or '').strip()]
    _px_host = str(st.secrets.get('PROXY_HOST',     os.environ.get('PROXY_HOST',     '')))
    # PROXY_URL 與 PROXY_HOST 二擇一即可亮 ✅
    if not _px_host:
        _px_host = str(st.secrets.get('PROXY_URL', os.environ.get('PROXY_URL', '')))
    _sb_c1, _sb_c2, _sb_c3 = st.columns(3)
    with _sb_c1:
        if _fm_tok:
            st.success('FinMind ✅')
        else:
            st.error('FinMind ❌')
    with _sb_c2:
        if _gm_keys:
            st.success(f'Gemini ✅ ×{len(_gm_keys)}')
        else:
            st.error('Gemini ❌')
    with _sb_c3:
        if _px_host:
            st.success('Proxy ✅')
        else:
            st.warning('Proxy —')
    # Gemini 金鑰池偵測明細（協助確認多帳號 key 有沒有被讀到）
    if _gm_slots:
        st.caption('🔑 偵測到 Gemini 金鑰：' + '、'.join(_gm_slots))
    else:
        st.caption('🔑 未偵測到任何 Gemini 金鑰（請確認 Secrets 內 '
                   'GEMINI_API_KEY 或 GEMINI_API_KEY_2~_6 的名稱與值）')
    if _px_host:
        _px_port = str(st.secrets.get('PROXY_PORT', os.environ.get('PROXY_PORT', '')))
        st.caption(f'🔒 {_px_host}:{_px_port}' if _px_port else '🔒 PROXY_URL 已設定')
        st.caption('💡 詳細診斷請看「🔎 資料診斷」Tab 的 API Key 診斷面板')
    if st.button('🔍 測試連線', key='sb_conn_test', use_container_width=True):
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
            st.success(f'✅ {_rn} 可達！HTTP {_rc}')
        else:
            st.error(f'❌ {_rn} 失敗：{_rc}')

    st.markdown('---')
    st.caption('⚠️ 僅供學術研究，非投資建議，盈虧自負')

# v3.0 RENDER FUNCTIONS (§9.3)
# ════════════════════════════════════════════════════════════════

# ── 旌旗指數計算（站上 MA20/MA60/MA120/MA240 的家數比例）──────
# ════════════════════════════════════════════════════════════════
# TABS: 3 主頁籤
# ════════════════════════════════════════════════════════════════
# ── Sidebar ────────────────────
with st.sidebar:
    st.markdown('<div style="text-align:center;padding:8px 0;font-size:15px;font-weight:900;color:#e6edf3;">&#128202; 台股AI戰情室 v3.0</div>', unsafe_allow_html=True)
    st.markdown('---')
    _today_sb = datetime.date.today()
    _wd_sb = {0:'一',1:'二',2:'三',3:'四',4:'五',5:'六',6:'日'}[_today_sb.weekday()]
    _trade_sb = '✅ 交易日' if _today_sb.weekday() < 5 else '❌ 非交易日'
    st.caption(f'{_today_sb.strftime("%Y/%m/%d")} 週{_wd_sb}  {_trade_sb}')
    st.markdown('---')
    if st.button('🔄 強制刷新數據', key='_sb_force_refresh', use_container_width=True,
                 help='清除所有快取並重新抓取最新資料'):
        st.cache_data.clear()
        st.rerun()
    st.markdown('---')

    # ── v18.203 F2：全局資料健康總覽（聚合個股六源 + 總經羅盤 → 一眼看哪舊）──
    try:
        from src.ui.pages import render_sidebar_data_health
        render_sidebar_data_health(st.session_state)
    except Exception as _e_sbh:
        print(f'[sidebar_health] {type(_e_sbh).__name__}: {_e_sbh}')
    st.markdown('---')

# 主標題
st.markdown(
    '<div style="display:flex;align-items:center;gap:10px;padding:4px 0 8px;">'    '<span style="font-size:22px;font-weight:900;color:#e6edf3;">&#128202; 台股 AI 戰情室</span>'    '<span style="font-size:10px;color:#484f58;background:#161b22;border-radius:10px;padding:2px 8px;">v4.0 Pro</span>'    '</div>',
    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 🧭 總經指南針 (Top-Down Macro) — Phase 1 規格頂部三大美股指標
# ══════════════════════════════════════════════════════
def _render_compass_card(col, info, title, ticker, fmt='{:.2f}', unit='', show_ma=False):
    """單張指標卡：值 + Phase 1 訊號燈 + 60D sparkline。info=None 顯示降級訊息。"""
    if info is None:
        col.markdown(
            f'<div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:10px;height:84px;">'
            f'<div style="font-size:11px;color:#8b949e;">{title}（{ticker}）</div>'
            f'<div style="font-size:13px;color:#8b949e;margin-top:6px;">🔴 未取得（yfinance 暫時失敗）</div>'
            f'</div>', unsafe_allow_html=True)
        return
    val = info.get('value')
    sig = info.get('signal') or ('⚪', '無訊號', '#8b949e')
    light, label, color = sig[0], sig[1], sig[2]
    val_str = fmt.format(val) + unit if val is not None else 'N/A'
    extra = ''
    if show_ma and info.get('ma60') is not None:
        extra = f' <span style="font-size:10px;color:#8b949e;font-weight:400;">/ 60MA {fmt.format(info["ma60"])}</span>'
    col.markdown(
        f'<div style="background:#0d1117;border:1px solid {color};border-radius:8px;padding:10px;">'
        f'<div style="font-size:11px;color:#8b949e;">{title}（{ticker}）</div>'
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
    """頂部三卡：VIX 恐慌指數 × 美 10Y 殖利率 × S&P 500 vs 60MA。
    預設不抓資料（避免顯示過時值誤判），按「📡 抓取最新」按鈕才打 yfinance。"""
    import datetime as _dt_mc

    def _do_fetch():
        try:
            from src.data.macro import fetch_macro_compass as _fmc
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
               if _has_data and _cache.get('_ts') else '尚未抓取')

    _header = st.columns([6, 1])
    _header[0].markdown(
        '<div style="font-size:14px;font-weight:900;color:#e6edf3;margin:4px 0 4px;">'
        '🧭 總經指南針 (Top-Down Macro)'
        '<span style="font-size:10px;color:#8b949e;font-weight:400;margin-left:8px;">'
        f'VIX × 10Y × S&amp;P 500 — {"即將抓取（無快取）" if not _has_data else f"更新於 {_ts_str}"}'
        '</span></div>',
        unsafe_allow_html=True)
    _header[1].button('📡 抓取最新' if not _has_data else '🔄 重抓',
                       key='_compass_fetch_btn', on_click=_do_fetch,
                       use_container_width=True)

    if not _has_data:
        st.info('💡 點擊右上「📡 抓取最新」按鈕載入即時 VIX / 10Y / S&P 500')
        return

    data = _cache.get('data') or {}
    c1, c2, c3 = st.columns(3)
    _render_compass_card(c1, data.get('vix'),  'VIX 恐慌指數',     '^VIX',  fmt='{:.2f}')
    _render_compass_card(c2, data.get('tnx'),  '美 10Y 殖利率',    '^TNX',  fmt='{:.2f}', unit='%')
    _render_compass_card(c3, data.get('gspc'), 'S&P 500 vs 60MA',  '^GSPC', fmt='{:,.2f}', show_ma=True)

render_macro_compass()

# v18.182 ARCHIVED: 🧪 回測找參數 Tab 暫封存
# 未來啟用：(1) tuple 加回 tab_backtest 在 tab_etf_margin 之後 tab_diag 之前
# (2) labels 加回 '🧪 回測找參數' 對應位置 (3) 取消下方 with tab_backtest 區塊註解
# v18.187 ARCHIVED: 📈 月營收進退 Tab 暫封存（FinMind batch endpoint 已不支援免費 tier）
# 未來啟用：(1) tuple 加回 tab_rev_screener 在 tab_screener 之後 tab_mj_diff 之前
# (2) labels 加回 '📈 月營收進退' 對應位置 (3) 取消下方 with tab_rev_screener 區塊註解
# v18.189 ARCHIVED: 📊 MJ 體檢變化 Tab 暫封存（功能改整合至「🏆 個股組合」批次體檢區塊下方）
# 未來啟用：(1) tuple 加回 tab_mj_diff 在 tab_screener 之後 tab_etf 之前
# (2) labels 加回 '📊 MJ 體檢變化' 對應位置 (3) 取消下方 with tab_mj_diff 區塊註解
tab_macro, tab_heatmap, tab_stock, tab_stock_grp, tab_screener, tab_etf, tab_etf_grp, tab_etf_margin, tab_diag, tab_edu = st.tabs([
    '🌍 總經', '🗺️ 產業熱力圖', '🔬 個股', '🏆 個股組合',
    '💎 高息網', '🏦 ETF', '⚖️ ETF組合', '💰 ETF質借模擬', '🔎 資料診斷', '📚 教學',
])

# ══════════════════════════════════════════════════════════════
# TAB 1: 總體經濟
# ══════════════════════════════════════════════════════════════

# ── 全域多空紅綠燈（頁面最頂端）─────────────────────────────
_mkt_top  = st.session_state.get('mkt_info', {})
_jq_top   = st.session_state.get('jingqi_info', {})
_ts_top   = st.session_state.get('cl_ts', '')
if (_mkt_top or _jq_top) and not st.session_state.get('_is_refreshing', False):
    _reg   = _mkt_top.get('regime', 'neutral')
    _jqpct = _jq_top.get('avg', 50) if _jq_top else None
    # 綜合信號
    _gl_color, _gl_label = traffic_light(
        None,
        _reg == 'bull' and (_jqpct is None or _jqpct >= 40),
        _reg == 'bear' or (_jqpct is not None and _jqpct < 20),
        '多頭市場（可積極操作）', '空頭市場（先觀望保守）', '🟡 震盪整理（謹慎操作）'
    )
    _gl_pos = _mkt_top.get('exposure_pct', '80%' if _reg=='bull' else ('20%' if _reg=='bear' else '50%'))

    st.markdown(
        f'<div style="background:#0d1117;border:1px solid {_gl_color};border-radius:8px;'
        f'padding:8px 14px;margin-bottom:8px;display:flex;align-items:center;gap:16px;">'
        f'<span style="font-size:16px;font-weight:900;color:{_gl_color};">{_gl_label}</span>'
        f'<span style="font-size:12px;color:#c9d1d9;">建議持股 <b>{_gl_pos}</b></span>'
        + (f'<span style="font-size:12px;color:#8b949e;">旌旗均值 {_jqpct:.0f}%</span>'
           if _jqpct is not None else '') +
        f'<span style="font-size:11px;color:#484f58;margin-left:auto;">更新：{_ts_top}</span>'
        f'</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# AI 總經戰情 — 新聞抓取已抽至 src/data/news/(v18.398 P5-B3-β R8)
# caller 改走 `from src.data.news import fetch_macro_news, fetch_stock_news`
# ══════════════════════════════════════════════════════════════


def _build_llm_context(macro_info: dict) -> str:
    """將 session_state 中的量化總經數據格式化為純文字供 LLM 使用"""
    _vix = macro_info.get('vix') or {}
    _exp = macro_info.get('tw_export') or {}
    _pmi = macro_info.get('ism_pmi') or {}
    _cpi = macro_info.get('us_core_cpi') or {}
    _ndc = macro_info.get('ndc_signal') or {}
    _mi  = st.session_state.get('m1b_m2_info') or {}
    _bi  = st.session_state.get('bias_info') or {}
    _lines = []
    if _vix.get('current'):
        _lines.append(f'• VIX 恐慌指數：{_vix["current"]} (MA20={_vix.get("ma20","N/A")})')
    if _exp.get('yoy') is not None:
        _lines.append(f'• 台灣外銷訂單 YoY：{_exp["yoy"]:+.1f}%  ({_exp.get("date","")})')
    if _pmi.get('value') is not None:
        _lines.append(f'• 🇹🇼 台灣 PMI：{_pmi["value"]}  ({_pmi.get("date","")}，>50 擴張)')
    if _cpi.get('yoy') is not None:
        _lines.append(f'• 美國核心 CPI YoY：{_cpi["yoy"]:+.1f}%  ({_cpi.get("date","")})')
    if _ndc.get('score') is not None:
        _lines.append(f'• NDC 景氣燈號分數：{_ndc["score"]:.0f}/45')
    if _mi.get('m1b_yoy') is not None and _mi.get('m2_yoy') is not None:
        _gap = round(float(_mi['m1b_yoy']) - float(_mi['m2_yoy']), 2)
        _lines.append(f'• 台灣 M1B={_mi["m1b_yoy"]:.1f}%  M2={_mi["m2_yoy"]:.1f}%  Gap={_gap:+.2f}%')
    if _bi.get('bias_240') is not None:
        _lines.append(f'• 台股大盤年線乖離率 BIAS240：{_bi["bias_240"]:+.1f}%')
    return '\n'.join(_lines) if _lines else '（量化數據載入中，請先點擊更新總經拼圖）'


# ══════════════════════════════════════════════════════════════
# TAB: ETF 單一深度診斷 + 多檔批次評分（v18.223 子分頁）
# ══════════════════════════════════════════════════════════════
with tab_etf:
    _etf_sub_tabs = st.tabs(['🔍 單檔深度診斷', '📊 多檔評分比較'])
    with _etf_sub_tabs[0]:
        render_etf_single(gemini_fn=gemini_call)
    with _etf_sub_tabs[1]:
        from src.ui.etf import render_etf_grp_compare
        render_etf_grp_compare()

# ══════════════════════════════════════════════════════════════
# TAB: ETF 組合戰情室（4 區段整合：組合配置 + 歷史回測 + AI + 葡萄串）
# ══════════════════════════════════════════════════════════════
with tab_etf_grp:
    # ── ① 組合配置與再平衡（唯一輸入來源，下游模組共享 etf_portfolio_rows）──
    render_etf_portfolio(gemini_fn=gemini_call)
    st.markdown('<hr style="margin:32px 0;border-color:#30363d;">', unsafe_allow_html=True)

    # ── ② 葡萄串領息法（自動讀取持股做月配息評估）──
    render_grape_ladder(gemini_fn=gemini_call)
    st.markdown('<hr style="margin:32px 0;border-color:#30363d;">', unsafe_allow_html=True)

    # ── ③ AI 綜合評斷 + 自由提問（壓軸區，整合所有上方分析）──
    render_etf_ai(gemini_fn=gemini_call)

# ══════════════════════════════════════════════════════════════
# TAB: ETF 質借倒金字塔加碼模擬器 (v18.162)
# ══════════════════════════════════════════════════════════════
with tab_etf_margin:
    from src.ui.tabs import render_etf_margin_simulator
    render_etf_margin_simulator()

# ══════════════════════════════════════════════════════════════
# TAB: 7% 高殖利率防禦網（Screener Mode）
# ══════════════════════════════════════════════════════════════
with tab_screener:
    from src.ui.tabs import render_yield_screener
    _picker_candidates = render_yield_screener()

    # ── 🎯 智慧選股（三階段濾網 + AI 三型建議）— 接續高息網候選清單 ──
    st.markdown('---')
    from src.ui.tabs import render_tab_stock_picker
    render_tab_stock_picker(gemini_fn=gemini_call, candidates=_picker_candidates)

# ══════════════════════════════════════════════════════════════
# TAB: 月營收進退篩選（v18.180） — v18.187 ARCHIVED
# FinMind TaiwanStockMonthRevenue batch endpoint (無 data_id) 已不支援免費/sponsor tier
# 模組 monthly_revenue_screener.py 保留磁碟，未來啟用：取消下方註解即可
# ══════════════════════════════════════════════════════════════
# with tab_rev_screener:
#     from monthly_revenue_screener import render_monthly_revenue_screener
#     render_monthly_revenue_screener()

# ══════════════════════════════════════════════════════════════
# TAB: MJ 體檢變化（v18.186 / v18.188 batch 版） — v18.189 ARCHIVED
# 功能改整合至「🏆 個股組合」批次體檢區塊下方「📊 MJ 趨勢分數」新區塊
# 模組 tab_mj_health_diff.py 與 mj_trend_score.py 保留磁碟，未來啟用：取消下方註解
# ══════════════════════════════════════════════════════════════
# with tab_mj_diff:
#     from tab_mj_health_diff import render_mj_health_diff_tab
#     render_mj_health_diff_tab()

# ══════════════════════════════════════════════════════════════
# TAB: 資料診斷（Raw Data only）
# ══════════════════════════════════════════════════════════════
with tab_diag:
    # v18.280 — 學 Fund 架構 + 預設視角:覆蓋率表(用戶視角)放最上方,
    # API Key / Proxy 雙跑(developer 視角)放後。對齊 Fund tab5 Section ⓪。
    from src.ui.pages import render_data_coverage, render_data_registry_panel, render_reconcile_panel
    render_data_coverage()
    st.markdown('---')
    # v18.394 Path C:資料源完整清單(50+ entries by SSOT 11 emoji category)。
    # coverage tab 4-row 是 Tab 級總覽;此 panel 是資料源級細項。語意分清楚不重複。
    render_data_registry_panel()
    st.markdown('---')
    # v18.403 #8+#12:§4.3 雙演算法對帳 panel(US10Y / 月營收 / 健康評分)。
    render_reconcile_panel()
    st.markdown('---')
    render_api_diagnostic()
    st.markdown('---')
    render_data_health_raw()
    st.markdown('---')
    from src.ui.pages import render_calibration_panel
    render_calibration_panel()

# ══════════════════════════════════════════════════════════════
# TAB: 產業熱力圖
# ══════════════════════════════════════════════════════════════
with tab_heatmap:
    render_sector_heatmap(gemini_fn=gemini_call)

st.markdown('<div style="text-align:center;font-size:10px;color:#484f58;padding:8px 0;">⚠️ 台股AI戰情室 v3.0 · 僅供學術研究，非投資建議，盈虧自負</div>', unsafe_allow_html=True)
