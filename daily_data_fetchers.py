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


# ═════════════════════════════════════════════════════
# 騰落指標 (ADL) — v18.347 PR-N4 抽出
# yfinance ^TWII 估算(🚫 TWSE MI_INDEX 已永久停用)
# ═════════════════════════════════════════════════════
def fetch_adl(days: int = 60, token=None):
    """騰落指標 ADL v5 — yfinance ^TWII 估算。

    ① yfinance ^TWII — 立即可用估算值
       並發 5 線程逐日抓取;精確值自動覆蓋估算值

    根本原因修正:TaiwanStockMarketCondition 不在 FinMind v4 有效資料集中
    """
    import datetime as _dt
    import pickle as _pk
    import os as _os2
    import time as _tm2
    import pandas as _pd_adl
    # ── 日誌 helper ────────────────────────────────────
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

    # ── Cache ────────────────────────────────────────
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

    today = _dt.date.today()
    s_date = today - _dt.timedelta(days=days + 14)
    s_dash = s_date.strftime('%Y-%m-%d')
    e_dash = today.strftime('%Y-%m-%d')
    rows: dict = {}   # {ymd: {'up':int, 'down':int, 'is_proxy':bool}}

    # ════════════════════════════════════════════════════════════════
    # ① yfinance ^TWII — 估算(立即可用,is_proxy=True)
    # 公式:漲跌幅 ±1% ≈ ±150 家,以 900/900 為基準
    # ════════════════════════════════════════════════════════════════
    _alog('[ADL-①] yfinance ^TWII 估算...')
    try:
        import yfinance as _yf_adl
        import os as _os_yf
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
            _twii = _yf_adl.download('^TWII', start=s_dash, end=e_dash,
                                      progress=False, auto_adjust=True)
        finally:
            for k, v in _ebak.items():
                if v is None:
                    _os_yf.environ.pop(k, None)
                else:
                    _os_yf.environ[k] = v
        if not _twii.empty:
            # [Fix] yfinance 新版可能回傳 MultiIndex columns,需先攤平
            if isinstance(_twii.columns, pd.MultiIndex):
                _twii.columns = _twii.columns.get_level_values(0)
            _twii = _twii.dropna(subset=['Close'])
            for _ix in _twii.index:
                _dk = str(_ix)[:10].replace('-', '')
                _cl = float(_twii.loc[_ix, 'Close'])
                _op = float(_twii.loc[_ix, 'Open'])
                _pct = (_cl - _op) / _op if _op > 0 else 0.0
                # 估算公式:中性=900,每±1%約±150家,限制在50~1750
                _up = max(50, min(1750, int(900 + _pct * 15000)))
                rows[_dk] = {'up': _up, 'down': max(50, 1800 - _up), 'is_proxy': True}
            _alog(f'[ADL-①] ✅ {len(rows)} 天估算完成')
        else:
            _alog('[ADL-①] ⚠️ yfinance 回傳空資料')
    except Exception as _e1:
        _alog(f'[ADL-①] ❌ {type(_e1).__name__}: {_e1}')

    # Edge Case 6: 完全沒有資料(🚫 TWSE MI_INDEX 已移除)
    if not rows:
        _alog('[ADL] ⚠️ 所有來源均失敗,回傳 None')
        return None

    # ── 組合 DataFrame ──────────────────────────────
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
    df['ad'] = df['up'] - df['down']
    df['adl'] = df['ad'].cumsum()
    df['adl_ma20'] = df['adl'].rolling(20, min_periods=1).mean()
    df['ad_ratio'] = (df['up'] / (df['up'] + df['down']).replace(0, 1) * 100).round(1)
    df['date'] = _pd_adl.to_datetime(df['date'], format='%Y%m%d')

    _proxy_n = int(df['is_proxy'].sum())
    _exact_n = int((~df['is_proxy']).sum())
    _alog(
        f'[ADL] ✅ 完成 {len(df)} 筆 '
        f'精確={_exact_n} 估算={_proxy_n} '
        f'上漲佔比:{df["ad_ratio"].iloc[-1]:.1f}%'
    )

    # ── 快取 ────────────────────────────────────────
    try:
        with open(_ck, 'wb') as _f:
            _pk.dump(df.tail(days).reset_index(drop=True), _f)
    except Exception:
        pass

    return df.tail(days).reset_index(drop=True)


# ── ADL Self-Test(邊界測試)─────────────────────────
def _adl_selftest():
    """在 Colab 外部可執行此函數驗證解析邏輯。"""
    import re

    def _parse(s):
        m = re.match(r'^([\d,]+)', str(s).strip())
        return int(m.group(1).replace(',', '')) if m else 0

    assert _parse('7,768(403)') == 7768, "Test1 failed"
    assert _parse('3,644') == 3644, "Test2 failed"
    assert _parse('') == 0, "Test3 failed"
    assert _parse('上漲') == 0, "Test4 failed"
    assert _parse('19,039') == 19039, "Test5 failed"
    print("[ADL selftest] ✅ 全部通過")
