"""daily_data_fetchers.py — daily_checklist L1 Data fetcher 集合。

v18.345 PR-N2 起從 daily_checklist.py 分批抽出 fetcher 群:
- PR-N2:fetch_single / fetch_flow_snapshot(yfinance + 並行)
- 本 PR (N3):_fetch_otc_via_finmind(FinMind OTC)+ fetch_institutional(TWSE BFI82U 三大法人)
- 後續 PR-N4:fetch_adl (yfinance + ADL 公式 + cache,MEDIUM risk)
- 後續 PR-N5:fetch_margin_balance (5 路 fallback,MEDIUM-HIGH risk)

§8.2 L1 Data 層:HTTP fetch + cache,**不**得 import streamlit(EX-CACHE-1 例外:可條件
import 純 @st.cache_data,但本檔目前未用)。
"""
from __future__ import annotations

import datetime
import os
import time

import pandas as pd

# v18.346 PR-N3:fetch_institutional 用 cache_layer + _bps + FINMIND_TOKEN
from shared.cache_layer import _CACHE_SENTINEL, _pkl_get, _pkl_put
from shared.macro_compute import _recent_date
from data_config import TTL_CONFIG as _TTL_CFG


def _bps():
    """Squid Proxy session(對齊 daily_checklist._bps 行為)。"""
    import requests as _rq
    try:
        from tw_stock_data_fetcher import build_proxy_session as _b
        s = _b()
    except Exception:
        s = _rq.Session()
    s.verify = False
    return s


# FINMIND_TOKEN lazy 讀(避免 module-level import streamlit 違反 PR-N2 守衛
# + headless/CLI 場景無 secrets.toml 不爆)。caller 直接 import FINMIND_TOKEN
# 取得當下值;若需即時更新 token 用 _get_finmind_token()。
def _get_finmind_token() -> str:
    _env = os.environ.get('FINMIND_TOKEN', '')
    if _env:
        return _env
    try:
        import streamlit as _st_ddf  # 條件 import,失敗 fallback env
        return getattr(_st_ddf, 'secrets', {}).get('FINMIND_TOKEN', '') or ''
    except Exception:
        return ''


# Module-level FINMIND_TOKEN 仍提供(向後相容 + 大多數 caller 一次取即可)
FINMIND_TOKEN = _get_finmind_token()


# ═══════════════════════════════════════════════
# yfinance 單檔 + 並行批次
# ═══════════════════════════════════════════════
def fetch_single(symbol, period: str = "60d"):
    """yfinance 單檔抓取(走 yf_proxy 內含 proxy env + cache_data 1h)+ /tmp pickle 30 分快取。

    跨 process 重啟存活(pkl)+ 同 process 內秒讀(yf_proxy cache_data)兩層保護。
    """
    import os as _os2, pickle as _pk2, hashlib as _hs2
    _ck2 = '/tmp/stock_cache/' + _hs2.md5(f'yf_{symbol}_{period}'.encode()).hexdigest() + '.pkl'
    _os2.makedirs('/tmp/stock_cache', exist_ok=True)
    if _os2.path.exists(_ck2) and (time.time() - _os2.path.getmtime(_ck2)) / 60 < 30:
        try:
            with open(_ck2, 'rb') as _f:
                return _pk2.load(_f)
        except (OSError, EOFError, _pk2.UnpicklingError) as _e_pkl:
            # W5-2 §1: pickle 反序列化失敗(壞檔/版本不容)補 log,fallback 重新 fetch
            print(f"[daily_checklist yf cache] {symbol} pkl 載入失敗,重抓:{_e_pkl}")
    # 美元指數備援 symbol 清單
    _sym_list = [symbol]
    if symbol in ('DX-Y.NYB', 'DX=F'):
        _sym_list = ['DX-Y.NYB', 'DX=F', 'UUP']  # NYB→期貨→ETF
    # v18.209 K5:改走 yf_proxy.cached_history(內含 proxy env + st.cache_data 1h),
    # 加 pkl 30min cache 兩層保護 → 跨 process 重啟存活 + 同 process 內秒讀。
    try:
        from yf_proxy import cached_history as _yp_hist
        h = None
        for _sym in _sym_list:
            _h = _yp_hist(_sym, period=period)
            if _h is not None and not _h.empty:
                h = _h
                break
        if h is None or h.empty:
            return None
        h.index = pd.DatetimeIndex(h.index).tz_localize(None)
        h.columns = [c.lower().replace(' ', '_') for c in h.columns]
        if 'close' in h.columns:
            h = h.dropna(subset=['close'])
        elif 'Close' in h.columns:
            h = h.dropna(subset=['Close'])
        if h.empty:
            return None
        with open(_ck2, 'wb') as _f:
            _pk2.dump(h, _f)
        return h
    except Exception as e:
        print(f'[yf:{symbol}] {e}')
        return None


def fetch_flow_snapshot(period: str = "2y"):
    """全球資金流向所需的區域 / 跨資產 ETF 收盤序列:並行抓取 + /tmp pickle 快取 30 分。

    回 {顯示名: DataFrame}(沿用 fetch_single 結構)。只在核心 SPY 抓到時才寫快取,
    避免暫時性全失敗被黏住。供總經 tab「全球資金流向」一節使用。
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

    _syms = _all_fl()                      # {名稱: 代號}
    _uniq = sorted(set(_syms.values()))    # 去重後實際抓取(SPY 等共用代號只抓一次)

    def _one(sym):
        return sym, fetch_single(sym, period=period)

    _by_sym = {}
    try:
        with _TPE_fl(max_workers=min(8, len(_uniq))) as _ex_fl:
            for _sym, _df in _ex_fl.map(_one, _uniq):
                _by_sym[_sym] = _df
    except Exception as _e_fl:
        print(f'[flow] ❌ 並行抓取異常: {_e_fl}')

    out = {name: _by_sym.get(sym) for name, sym in _syms.items()}

    if _by_sym.get('SPY') is not None:     # 核心抓到才快取
        try:
            with open(_ck_fl, 'wb') as _f_fl:
                _pk_fl.dump(out, _f_fl)
        except Exception:
            pass
    return out


# ═══════════════════════════════════════════════
# OTC 指數 (FinMind) — v18.346 PR-N3 抽出
# ═══════════════════════════════════════════════
def _fetch_otc_via_finmind(token: str = ""):
    if not FINMIND_TOKEN:
        return None
    try:
        start = (datetime.date.today() - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
        r = _bps().get("https://api.finmindtrade.com/api/v4/data",
                       params={"dataset": "TaiwanStockDaily", "data_id": "OTC", "start_date": start},
                       headers={"Authorization": f"Bearer {FINMIND_TOKEN}"}, timeout=20)
        j = r.json()
        if j.get("status") == 200 and j.get("data"):
            df = pd.DataFrame(j["data"])
            if 'close' in df.columns:
                df['Date'] = pd.to_datetime(df['date'])
                return df.sort_values('Date').set_index('Date')[['close']].rename(columns={'close': 'Close'})
    except Exception as e:
        print(f"[OTC] {e}")
    return None


# ═══════════════════════════════════════════════
# 三大法人 (TWSE BFI82U via Squid Proxy) — v18.346 PR-N3 抽出
# 收盤後 15:30 才有當日資料
# ═══════════════════════════════════════════════
def fetch_institutional(date_str: str | None = None):
    if date_str is None:
        date_str = _recent_date()
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
                print(f'[三大法人/BFI82U] ⚠️ date={_ds} 無回應')
                continue
            try:
                _resp_i = _r_i.json()
            except Exception:
                continue
            if not (isinstance(_resp_i, dict) and _resp_i.get('stat') == 'OK'):
                print(f'[三大法人/BFI82U] ⚠️ date={_ds} stat={(_resp_i or {}).get("stat")}')
                continue
            # BFI82U 可能回傳 data 或 tables[0].data
            _data_i = _resp_i.get('data', [])
            if not _data_i and 'tables' in _resp_i:
                _data_i = (_resp_i['tables'][0] if _resp_i['tables'] else {}).get('data', [])
            if not _data_i:
                continue
            _inst = {'外資及陸資': {'net': 0.0}, '投信': {'net': 0.0}, '自營商': {'net': 0.0}}
            for _row_i in _data_i:
                _nm_i = str(_row_i[0])
                # row[3] = 買賣超(元,帶千分位逗號);lstrip('-') 支援負值
                _vs_i = str(_row_i[3]).replace(',', '').strip()
                if not _vs_i.lstrip('-').isdigit():
                    continue
                _net_i = round(int(_vs_i) / 1e8, 2)  # 元 → 億元
                if '外資及陸資' in _nm_i:
                    _inst['外資及陸資']['net'] = _net_i
                elif '投信' in _nm_i:
                    _inst['投信']['net'] = _net_i
                elif '自營' in _nm_i:
                    _inst['自營商']['net'] += _net_i
            print(f'[三大法人/BFI82U] ✅ date={_ds} {_inst}')
            return _pkl_put('institutional', (_inst, _ds))
    except Exception as _e_inst:
        print(f'[三大法人/BFI82U] ❌ {type(_e_inst).__name__}: {_e_inst}')

    return {}, date_str
