"""daily_data_fetchers.py — daily_checklist L1 Data fetcher 集合。

v18.345 PR-N2 從 daily_checklist.py 開始抽出 fetcher 群:
- 本 PR (N2):fetch_single / fetch_flow_snapshot(yfinance + 並行)
- 後續 PR-N3:_fetch_otc_via_finmind / fetch_institutional
- 後續 PR-N4:fetch_adl (yfinance + ADL 公式 + cache,MEDIUM risk)
- 後續 PR-N5:fetch_margin_balance (5 路 fallback,MEDIUM-HIGH risk)

§8.2 L1 Data 層:HTTP fetch + cache,**不**得 import streamlit(EX-CACHE-1 例外:可條件
import 純 @st.cache_data,但本檔目前未用)。
"""
from __future__ import annotations

import os
import time

import pandas as pd


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
