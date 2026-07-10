"""daily_data_fetchers.py — daily_checklist L1 Data fetcher 集合。

v18.345 PR-N2 起從 daily_checklist.py 分批抽出 fetcher 群:
- PR-N2:fetch_single / fetch_flow_snapshot(yfinance + 並行)
- PR-N3:_fetch_otc_via_finmind / fetch_institutional
- PR-N4:fetch_adl (yfinance + ADL 公式 + cache + log)
- 本 PR (N5):fetch_margin_balance (6 路 fallback,MEDIUM-HIGH risk) — 拆檔收尾

§8.2 L1 Data 層:HTTP fetch + cache。
v18.400 D2:6 fetcher 加 @st.cache_data,改採 EX-CACHE-1 letter-compliant pattern
(條件 try import streamlit + _NoOpST fallback),既滿足 cache 需求又保持 CLI/pytest
純 .py 環境可 import 不爆。
"""
from __future__ import annotations

import datetime
import os
import re

import pandas as pd

# v18.400 D2:EX-CACHE-1 letter-compliant — 6 fetcher 加 @st.cache_data
try:
    import streamlit as st
except ImportError:
    class _NoOpST:
        @staticmethod
        def cache_data(*args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            return lambda f: f
        cache_resource = cache_data
        secrets: dict = {}
    st = _NoOpST()  # noqa

# v18.346 PR-N3:fetch_institutional 用 cache_layer + _bps + FINMIND_TOKEN
from shared.cache_layer import _CACHE_SENTINEL, _pkl_get, _pkl_put
from src.config import FINMIND_API_URL  # Batch 10b v18.412 SSOT
from shared.macro_compute import _recent_date
from shared.signal_thresholds import (  # v19.72 融資餘額 §3.2 合理區間 SSOT
    MARGIN_BALANCE_SANITY_MAX_YI,
    MARGIN_BALANCE_SANITY_MIN_YI,
)
from shared.ttls import TTL_30MIN, TTL_1HOUR
from src.config import TTL_CONFIG as _TTL_CFG


# v18.354 PR-Q4 — S-PROV-1 phase 19 helper
# 6 fetcher (fetch_single / fetch_flow_snapshot / _fetch_otc_via_finmind /
# fetch_institutional / fetch_adl / fetch_margin_balance) 共用 audit trail。
# 介面 0 改(對齊 etf_fetch._prov_log 既有模式,PR-Q2 v18.352)。
# P2-1 v18.380:_prov_log 統一至 src/data/core/provenance.py
from src.data.core.provenance import prov_log as _prov_log_unified


def _prov_log(fn_name: str, source: str, ticker: str, result_summary: str):
    """§2.2 provenance — backward-compat shim。"""
    try:
        _prov_log_unified(fn_name, source, result_summary, ticker=ticker)
    except Exception:
        pass


def _bps():
    """Squid Proxy session(對齊 daily_checklist._bps 行為)。"""
    import requests as _rq
    try:
        from src.data.stock import build_proxy_session as _b
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
@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_single(symbol, period: str = "60d"):
    """yfinance 單檔抓取(走 yf_proxy 內含 proxy env + cache_data 1h)+ /tmp pickle 30 分快取。

    跨 process 重啟存活(pkl)+ 同 process 內秒讀(yf_proxy cache_data)兩層保護。
    """
    import hashlib as _hs2
    # D3 v18.437:pkl 快取改用 cache_layer SSOT(_pkl_get/_pkl_put,同檔 fetch_institutional 模式);
    # key 沿用 md5(yf_{symbol}_{period}),TTL 30 分。壞檔 fallback 重抓由 _pkl_get 內建(§1 stderr log)。
    _ck2 = _hs2.md5(f'yf_{symbol}_{period}'.encode()).hexdigest()
    _c2 = _pkl_get(_ck2, TTL_30MIN)
    if _c2 is not _CACHE_SENTINEL:
        return _c2
    # 美元指數備援 symbol 清單
    _sym_list = [symbol]
    if symbol in ('DX-Y.NYB', 'DX=F'):
        _sym_list = ['DX-Y.NYB', 'DX=F', 'UUP']  # NYB→期貨→ETF
    # v18.209 K5:改走 yf_proxy.cached_history(內含 proxy env + st.cache_data 1h),
    # 加 pkl 30min cache 兩層保護 → 跨 process 重啟存活 + 同 process 內秒讀。
    try:
        from src.data.proxy import cached_history as _yp_hist
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
            _prov_log('fetch_single', 'yf_proxy.cached_history', symbol, 'None:empty')
            return None
        _pkl_put(_ck2, h)
        _prov_log('fetch_single', 'yf_proxy.cached_history', symbol, f'df:{len(h)}rows')
        return h
    except Exception as e:
        print(f'[yf:{symbol}] {e}')
        _prov_log('fetch_single', 'yf_proxy.cached_history', symbol,
                  f'None:exc:{type(e).__name__}')
        return None


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_flow_snapshot(period: str = "2y"):
    """全球資金流向所需的區域 / 跨資產 ETF 收盤序列:並行抓取 + /tmp pickle 快取 30 分。

    回 {顯示名: DataFrame}(沿用 fetch_single 結構)。只在核心 SPY 抓到時才寫快取,
    避免暫時性全失敗被黏住。供總經 tab「全球資金流向」一節使用。
    """
    from concurrent.futures import ThreadPoolExecutor as _TPE_fl
    from shared.etf_universe import all_symbols as _all_fl  # Phase 2 Batch 2b v18.424:L1→L0 直 import,解 L1→L2 反向違規

    # D3 v18.437:pkl 快取改用 cache_layer SSOT(key=_flow_snapshot,TTL 30 分)。
    _c_fl = _pkl_get('_flow_snapshot', TTL_30MIN)
    if _c_fl is not _CACHE_SENTINEL:
        return _c_fl

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

    if _by_sym.get('SPY') is not None:     # 核心抓到才快取(避免暫時全失敗被黏住)
        _pkl_put('_flow_snapshot', out)
    _prov_log('fetch_flow_snapshot', 'flow_engine+yf_proxy(parallel)',
              f'period={period}', f'dict:{sum(1 for v in out.values() if v is not None)}/{len(out)}symbols')
    return out


# ═══════════════════════════════════════════════
# OTC 指數 (FinMind) — v18.346 PR-N3 抽出
# ═══════════════════════════════════════════════
@st.cache_data(ttl=TTL_30MIN, show_spinner=False)
def _fetch_otc_via_finmind(token: str = ""):
    if not FINMIND_TOKEN:
        _prov_log('_fetch_otc_via_finmind', 'FinMind:TaiwanStockDaily:OTC',
                  'OTC', 'None:no-token')
        return None
    try:
        start = (datetime.date.today() - datetime.timedelta(days=90)).strftime('%Y-%m-%d')
        r = _bps().get(FINMIND_API_URL,
                       params={"dataset": "TaiwanStockDaily", "data_id": "OTC", "start_date": start},
                       headers={"Authorization": f"Bearer {FINMIND_TOKEN}"}, timeout=20)
        j = r.json()
        if j.get("status") == 200 and j.get("data"):
            df = pd.DataFrame(j["data"])
            if 'close' in df.columns:
                df['Date'] = pd.to_datetime(df['date'])
                _result = df.sort_values('Date').set_index('Date')[['close']].rename(columns={'close': 'Close'})
                _prov_log('_fetch_otc_via_finmind', 'FinMind:TaiwanStockDaily:OTC',
                          'OTC', f'df:{len(_result)}rows')
                return _result
    except Exception as e:
        print(f"[OTC] {e}")
        _prov_log('_fetch_otc_via_finmind', 'FinMind:TaiwanStockDaily:OTC',
                  'OTC', f'None:exc:{type(e).__name__}')
        return None
    _prov_log('_fetch_otc_via_finmind', 'FinMind:TaiwanStockDaily:OTC',
              'OTC', 'None:no-data')
    return None


# ═══════════════════════════════════════════════
# 三大法人 (TWSE BFI82U via Squid Proxy) — v18.346 PR-N3 抽出
# 收盤後 15:30 才有當日資料
# ═══════════════════════════════════════════════
def _parse_bfi82u_rows(fields: list, data: list) -> dict | None:
    """BFI82U 三大法人列 → {'外資及陸資': {'net': 億}, '投信': ..., '自營商': ...}。

    v19.72 review 修正:買賣超欄位用 fields 欄名「買賣差額」定位,不再寫死 row[3]
    （TWSE 改版欄序位移時,寫死索引會抓到「買進金額」等錯欄 → isdigit 仍通過 →
    靜默回反向籌碼結論,§1 Fail Loud 違憲）。對齊同檔 MI_MARGN fields 定位既有模式。
    fields 無「買賣差額/買賣超」欄 → 回 None,caller 應 log + 換日重試/放棄,不猜位置。
    """
    _net_idx = next((_i for _i, _f in enumerate(fields)
                     if '買賣差額' in str(_f) or '買賣超' in str(_f)), None)
    if _net_idx is None:
        return None
    _inst = {'外資及陸資': {'net': 0.0}, '投信': {'net': 0.0}, '自營商': {'net': 0.0}}
    for _row in data:
        if not _row or len(_row) <= _net_idx:
            continue
        _nm = str(_row[0])
        # 買賣差額(元,帶千分位逗號);lstrip('-') 支援負值
        _vs = str(_row[_net_idx]).replace(',', '').strip()
        if not _vs.lstrip('-').isdigit():
            continue
        _net = round(int(_vs) / 1e8, 2)  # 元 → 億元
        if '外資及陸資' in _nm:
            _inst['外資及陸資']['net'] = _net
        elif '投信' in _nm:
            _inst['投信']['net'] = _net
        elif '自營' in _nm:
            _inst['自營商']['net'] += _net
    return _inst


@st.cache_data(ttl=TTL_30MIN, show_spinner=False)
def fetch_institutional(date_str: str | None = None):
    if date_str is None:
        date_str = _recent_date()
    _inst_ttl = _TTL_CFG.get('institutional', 600)
    _inst_cached = _pkl_get('institutional', _inst_ttl)
    if _inst_cached is not _CACHE_SENTINEL:
        return _inst_cached

    try:
        from src.data.proxy import fetch_url as _furl_i
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
            # BFI82U 可能回傳 data 或 tables[0].data(fields 跟著同一容器走)
            _data_i = _resp_i.get('data', [])
            _fields_i = _resp_i.get('fields', [])
            if not _data_i and 'tables' in _resp_i:
                _tbl0_i = (_resp_i['tables'][0] if _resp_i['tables'] else {})
                _data_i = _tbl0_i.get('data', [])
                _fields_i = _tbl0_i.get('fields', []) or _fields_i
            if not _data_i:
                continue
            # v19.72:欄名定位取代寫死 row[3](TWSE 改版防呆,詳 _parse_bfi82u_rows)
            _inst = _parse_bfi82u_rows(_fields_i, _data_i)
            if _inst is None:
                print(f'[三大法人/BFI82U] ❌ date={_ds} fields 無「買賣差額」欄'
                      f'(疑 TWSE 改版): {_fields_i}')
                continue
            print(f'[三大法人/BFI82U] ✅ date={_ds} {_inst}')
            _prov_log('fetch_institutional', 'TWSE:BFI82U(via Squid Proxy)',
                      date_str or 'recent', f'tuple:date={_ds}')
            return _pkl_put('institutional', (_inst, _ds))
    except Exception as _e_inst:
        print(f'[三大法人/BFI82U] ❌ {type(_e_inst).__name__}: {_e_inst}')

    _prov_log('fetch_institutional', 'TWSE:BFI82U(via Squid Proxy)',
              date_str or 'recent', 'tuple:empty:all-dates-fail')
    return {}, date_str


# ═════════════════════════════════════════════════════
# 騰落指標 (ADL) — v18.347 PR-N4 抽出
# yfinance ^TWII 估算(🚫 TWSE MI_INDEX 已永久停用)
# ═════════════════════════════════════════════════════
@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
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
                # v18.435 WONTFIX-翻案 Bug #2:原 `_pk.load(open(...))` 未用 with,
                # 若 pickle.load raise,traceback 持有期間 file handle 不釋放;
                # 改 with block 保證即時關閉。
                with open(_ck, 'rb') as _f_adl:
                    _c = _pk.load(_f_adl)
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
            from src.data.stock import _load_proxy_config as _lpc_adl
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

    _result_adl = df.tail(days).reset_index(drop=True)
    _prov_log('fetch_adl', 'yfinance:^TWII(估算 ADL)', f'days={days}',
              f'df:{len(_result_adl)}rows:proxy={_proxy_n}+exact={_exact_n}')
    return _result_adl


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


# ═══════════════════════════════════════════════
# 融資餘額 — v18.348 PR-N5 抽出 (MEDIUM-HIGH)
# 6 路 fallback:FinMind → MI_MARGN → HiStock → Goodinfo → Yahoo → 鉅亨網
# ═══════════════════════════════════════════════
def _margin_sanity_ok(v_yi: float) -> bool:
    """融資餘額合理區間檢查（單位:億,§3.2）。

    超出 [MARGIN_BALANCE_SANITY_MIN_YI, MARGIN_BALANCE_SANITY_MAX_YI] →
    疑似單位/欄位誤判,呼叫端應棄用該來源改走下一 fallback（§1 寧缺勿錯）。
    """
    return MARGIN_BALANCE_SANITY_MIN_YI < v_yi < MARGIN_BALANCE_SANITY_MAX_YI


def _finmind_margin_to_yi(raw: float) -> float | None:
    """FinMind TaiwanStockTotalMarginPurchaseShortSale 餘額 → 億。

    v19.72 review 修正:該 dataset 鏡射 TWSE MI_MARGN,MarginPurchaseMoney 餘額
    單位**固定「仟元」** → ÷1e5 = 億（同檔方案A 註解「仟元÷100,000=億」同源印證）。
    原 v6 用數值區間反猜單位（億/元/千元/萬元 四分支）,來源改單位時會靜默錯
    1 個數量級（§4.1 單位陷阱違憲）。換算後過 _margin_sanity_ok 才回值,否則回
    None（log + 棄用,讓 fallback 鏈接手）。
    """
    if raw <= 0:
        return None
    _yi = raw / 1e5
    if _margin_sanity_ok(_yi):
        return round(_yi, 1)
    print(f'[融資餘額/FinMind] ⚠️ {raw} 仟元 → {_yi:.1f}億 超出合理區間 '
          f'({MARGIN_BALANCE_SANITY_MIN_YI:.0f}~{MARGIN_BALANCE_SANITY_MAX_YI:.0f}億),棄用')
    return None


@st.cache_data(ttl=TTL_30MIN, show_spinner=False)
def fetch_margin_balance(date_str=None):
    """融資餘額 — FinMind → MI_MARGN → HiStock → Goodinfo → Yahoo → 鉅亨網,單位:億元

    v7(v19.72):Plan 0 廢除數值區間猜單位,改固定仟元換算 + §3.2 sanity 區間
        （見 _finmind_margin_to_yi;超區間 → 棄用改走下一 fallback）。
    v6:Plan 0 = FinMind TaiwanStockTotalMarginPurchaseShortSale
        (Streamlit Cloud 海外 IP 唯一可達來源)
    v5:Plan A = MI_MARGN (mi-margn.html 後端 JSON),扁平 data/fields 解析。
    """
    _mb_ttl = _TTL_CFG.get('margin_balance', 600)
    _mb_cached = _pkl_get('margin_balance', _mb_ttl)
    if _mb_cached is not _CACHE_SENTINEL:
        return _mb_cached

    # 取最近一個交易日(週末往前推)
    _now_mb = datetime.datetime.now()
    while _now_mb.weekday() >= 5:
        _now_mb -= datetime.timedelta(days=1)
    _ds_mb = _now_mb.strftime('%Y%m%d')

    # 方案0: FinMind TaiwanStockTotalMarginPurchaseShortSale (v6 新增)
    # 治本:海外 IP 也可達,原 TWSE/HiStock/Goodinfo/Yahoo/cnyes 全部需要台灣 IP
    try:
        from src.data.macro import finmind_get as _fm_mb
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
                # 長格式:每一列代表「融資/融券」單一指標
                for _, _r0 in _grp0.iterrows():
                    _nm0 = str(_r0.get('name', '')).lower()
                    if not ('融資' in _nm0 or 'margin' in _nm0 or 'purchase' in _nm0):
                        continue
                    for _bc0 in _bal_cols0:
                        try:
                            _raw0 = float(str(_r0.get(_bc0, 0)).replace(',', '') or 0)
                        except Exception:
                            continue
                        # v19.72:固定仟元→億換算 + sanity(取代原四分支區間猜單位)
                        _cand0 = _finmind_margin_to_yi(_raw0)
                        if _cand0 is not None:
                            _v_mb0 = _cand0; break
                    if _v_mb0 is not None: break
            elif 'TotalMarginPurchaseTodayBalance' in _cols_mb0:
                _raw0 = float(str(_grp0['TotalMarginPurchaseTodayBalance'].iloc[-1]).replace(',', '') or 0)
                _v_mb0 = _finmind_margin_to_yi(_raw0)
            elif 'MarginPurchaseTodayBalance' in _cols_mb0:
                _raw0 = float(str(_grp0['MarginPurchaseTodayBalance'].iloc[-1]).replace(',', '') or 0)
                _v_mb0 = _finmind_margin_to_yi(_raw0)
            if _v_mb0 is not None:
                print(f'[融資餘額/FinMind] ✅ {_v_mb0}億 date={_last_d0}')
                return _pkl_put('margin_balance', _v_mb0)
            print(f'[融資餘額/FinMind] ⚠️ date={_last_d0} 解析未命中(cols={_cols_mb0[:6]})')
        else:
            print('[融資餘額/FinMind] ⚠️ 回傳空 DataFrame')
    except Exception as _e_mb0:
        print(f'[融資餘額/FinMind] ❌ {type(_e_mb0).__name__}: {_e_mb0}')

    # 方案A: TWSE rwd MI_MARGN(單次嘗試最近交易日;MS→ALL 雙 selectType 容錯)
    # 對齊 leading_indicators._twse_margin_day 已驗證有效邏輯:頂層 data/fields,
    # 欄名偵測「融資...餘額」(排除「限」),reversed 取彙總列,仟元÷100,000=億
    try:
        from src.data.proxy import fetch_url as _furl_mb
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
                    if _margin_sanity_ok(_v_mb):
                        print(f'[融資餘額/MI_MARGN/{_sel_mb}] ✅ {_v_mb}億 date={_ds_mb}')
                        return _pkl_put('margin_balance', _v_mb)
            print(f'[融資餘額/MI_MARGN/{_sel_mb}] ⚠️ date={_ds_mb} 解析未命中(fa_col={_fa_col})')
            _hit_mb = True
        if not _hit_mb:
            print(f'[融資餘額/MI_MARGN] ⚠️ MS/ALL 皆無回應')
    except Exception as _e_mb:
        print(f'[融資餘額/MI_MARGN] ❌ {type(_e_mb).__name__}: {_e_mb}')

    # 方案B: HiStock 網頁爬蟲(公開,BeautifulSoup)
    try:
        from src.data.proxy import fetch_url as _furl_hi
        from bs4 import BeautifulSoup as _BS_mb
        _rh = _furl_hi('https://histock.tw/stock/margin.aspx', timeout=12)
        if _rh is not None:
            _soup_h = _BS_mb(_rh.text, 'html.parser')
            _txt_h = _soup_h.get_text(' ', strip=True)
            _m_h = re.search(r'融資餘額[^\d]{0,20}([\d,]+(?:\.\d+)?)\s*億', _txt_h)
            if _m_h:
                _v_h = round(float(_m_h.group(1).replace(',', '')), 1)
                if _margin_sanity_ok(_v_h):
                    print(f'[融資餘額/HiStock] ✅ {_v_h}億')
                    return _pkl_put('margin_balance', _v_h)
    except Exception as _e_hi:
        print(f'[融資餘額/HiStock] ❌ {type(_e_hi).__name__}: {_e_hi}')

    # 方案C: Goodinfo 加權指數融資融券日統計(公開 HTML,BeautifulSoup)
    try:
        from src.data.proxy import fetch_url as _furl_gi
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
                            if _margin_sanity_ok(_vc):
                                _gi_val = round(_vc, 1); break
                        if _gi_val is not None: break
                if _gi_val is not None: break
            if _gi_val is None:
                _txt_g = _soup_g.get_text(' ', strip=True)
                _m_g = re.search(r'融資餘額[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*億', _txt_g)
                if _m_g:
                    _vg2 = round(float(_m_g.group(1).replace(',', '')), 1)
                    if _margin_sanity_ok(_vg2):
                        _gi_val = _vg2
            if _gi_val is not None:
                print(f'[融資餘額/Goodinfo] ✅ {_gi_val}億')
                return _pkl_put('margin_balance', _gi_val)
            print('[融資餘額/Goodinfo] ⚠️ 表格 + 正則皆未命中')
    except Exception as _e_gi:
        print(f'[融資餘額/Goodinfo] ❌ {type(_e_gi).__name__}: {_e_gi}')

    # 方案D: Yahoo 股市資券餘額(HTML,整頁正則)
    try:
        from src.data.proxy import fetch_url as _furl_yh
        from bs4 import BeautifulSoup as _BS_yh
        _ry = _furl_yh('https://tw.stock.yahoo.com/margin-balance', timeout=12)
        if _ry is not None:
            _ry.encoding = 'utf-8'
            _txt_y = _BS_yh(_ry.text, 'html.parser').get_text(' ', strip=True)
            _m_y = re.search(r'融資餘額[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*(?:億|$)', _txt_y)
            if _m_y:
                _vy = round(float(_m_y.group(1).replace(',', '')), 1)
                if _margin_sanity_ok(_vy):
                    print(f'[融資餘額/Yahoo] ✅ {_vy}億')
                    return _pkl_put('margin_balance', _vy)
            print('[融資餘額/Yahoo] ⚠️ 正則未命中')
    except Exception as _e_yh:
        print(f'[融資餘額/Yahoo] ❌ {type(_e_yh).__name__}: {_e_yh}')

    # 方案E: 鉅亨網盤後資券餘額(HTML,整頁正則)
    try:
        from src.data.proxy import fetch_url as _furl_cy
        from bs4 import BeautifulSoup as _BS_cy
        _rc = _furl_cy('https://www.cnyes.com/twstock/a_margin.aspx', timeout=12)
        if _rc is not None:
            _rc.encoding = 'utf-8'
            _txt_c = _BS_cy(_rc.text, 'html.parser').get_text(' ', strip=True)
            _m_c = re.search(r'融資餘額[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*(?:億|$)', _txt_c)
            if _m_c:
                _vc = round(float(_m_c.group(1).replace(',', '')), 1)
                if _margin_sanity_ok(_vc):
                    print(f'[融資餘額/cnyes] ✅ {_vc}億')
                    return _pkl_put('margin_balance', _vc)
            print('[融資餘額/cnyes] ⚠️ 正則未命中')
    except Exception as _e_cy:
        print(f'[融資餘額/cnyes] ❌ {type(_e_cy).__name__}: {_e_cy}')

    # fetch_margin_balance: 6 路 fallback 全失敗時 return None
    # 各成功路徑(FinMind/MI_MARGN/HiStock/Goodinfo/Yahoo/cnyes)的 _pkl_put 已含
    # source 標記在 print log;此處只記「全敗」的 audit trail。
    _prov_log('fetch_margin_balance', '6-fallback-all-fail',
              date_str or 'recent', 'None:all-routes-empty')
    return None
