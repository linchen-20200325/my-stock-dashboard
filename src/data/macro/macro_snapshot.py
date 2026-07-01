"""L1 macro-snapshot fetchers — 從 tab_macro._job_macro 漸進抽出的純抓取服務。

鏡像 Fund 端 `services/macro_service.fetch_all_indicators` 的 single-snapshot 方向：
把總經拼圖各指標的抓取邏輯從 5,245 LOC 的 `tab_macro.render_tab_macro` 巨型 UI 函式
下沉成可單測的純函式。每個 `fetch_*_block()` 回傳一個 dict 片段（命中 key，或
`_err_<name>` 診斷 key），由呼叫端平行 submit 後 merge 成單一 macro snapshot。

分層（§8.2）：**L1 Data** — 純抓取 + 解析，不碰 Streamlit UI（無 st.session_state /
st.markdown / st.error）。後續含 API key 的 fetcher 經 EX-L0-1 讀 st.secrets（config
bootstrap），不引入 UI lifecycle 依賴。

失敗約定（§1 Fail Loud, Never Fake）：每個 block 自帶 try/except，失敗回
`{'_err_<name>': reason}` 診斷 token —— **不捏造數值**、不靜默吞例外。呼叫端對缺漏
key 的指標退「待取得」placeholder（誠實顯示無資料）。

遷移進度：
- [x] VIX                              — fetch_vix_block（v18.332 slice 1）
- [x] CPI / Fed / PMI / NDC / Export   — P3-D1 v18.389 完整下沉
- [x] M1B/M2                           — fetch_m1b_m2_block（P3-D2 v18.389）
- [x] TWII bias                        — compute_twii_bias（P3-D3 v18.389）
"""
from __future__ import annotations

# v18.400 D1:EX-CACHE-1 letter-compliant — 9 fetcher 加 @st.cache_data(ttl=TTL_1HOUR)
# 解決原 `_job_macro` 平行呼叫 9 個 fetcher 每次 rerun 重抓的效能與 API quota 問題。
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

from shared.calc_helpers import calc_bias_pct
from src.config import FINMIND_API_URL  # Batch 10b v18.412 SSOT
from shared.ttls import TTL_1HOUR


def _make_proxy_session():
    """NAS proxy Session — 直接套用 proxy_helper.get_proxies(),retry adapter 含 429/503/504。

    P3-D1 v18.389:從 tab_macro._job_macro._mk_s 抽出。
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    try:
        from src.data.proxy import get_proxies
        _px = get_proxies()
    except Exception:
        _px = None
    _s = requests.Session()
    _adp = HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1.0,
                                          status_forcelist=[429, 503, 504],
                                          raise_on_status=False))
    _s.mount('https://', _adp)
    _s.mount('http://', _adp)
    if _px:
        _s.proxies.update(_px)
    _s.verify = False
    return _s


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_vix_block() -> dict:
    """VIX（^VIX, 3mo, 日線）→ `{'vix': {current, ma20, dates, values, date}}`。

    失敗回 `{'_err_vix': <reason>}`。verbatim 自 tab_macro._job_macro._fetch_vix
    （v18.332 抽出，邏輯 0 改動）。

    Returns:
        dict: 命中時含 'vix' key；失敗時含 '_err_vix' 診斷字串。
    """
    try:
        import yfinance as _yf_vix
        _df_v = _yf_vix.download('^VIX', period='3mo', interval='1d',
                                 progress=False, auto_adjust=True)
        if _df_v is None or _df_v.empty:
            return {'_err_vix': 'yfinance empty'}
        if hasattr(_df_v.columns, 'nlevels') and _df_v.columns.nlevels > 1:
            _df_v.columns = _df_v.columns.get_level_values(0)
        _df_v = _df_v.dropna(subset=['Close'])
        _vv = [round(float(v), 1) for v in _df_v['Close']]
        _vd = [str(d)[:10] for d in _df_v.index]
        if len(_vv) < 3:
            return {'_err_vix': 'not enough data'}
        _s20 = _vv[-20:] if len(_vv) >= 20 else _vv
        print(f'[Macro/VIX] ✅ current={_vv[-1]} date={_vd[-1]}')
        # v18.357 PR-Q5c S-PROV-1 phase 19:provenance 進入 dict(schema-additive)
        import datetime as _dt_vp
        return {'vix': {'current': _vv[-1], 'ma20': round(sum(_s20) / len(_s20), 1),
                        'dates': _vd[-60:], 'values': _vv[-60:], 'date': _vd[-1],
                        'source': 'yfinance:^VIX:3mo:1d',
                        'fetched_at': _dt_vp.datetime.utcnow().isoformat() + 'Z'}}
    except Exception as _e_vix:
        print(f'[Macro/VIX] ❌ {_e_vix}')
        return {'_err_vix': str(_e_vix)[:80]}


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_m1b_m2_block(fred_api_key: str = '') -> dict | None:
    """抓 TW M1B/M2 YoY,3 路 fallback。

    P3-D2 v18.389 深層拔毒:從 tab_macro.py:885-974 `_job_m1b` inline def 抽出(L5→L1)。

    路徑優先級(§2.1 衝突裁決):
        Tier 0: tw_macro.fetch_cbc_m1b_m2(CBC ms1.json + CPX + ^TWII proxy)
        Tier 1: FRED MYAGM1TWA189S / MYAGM2TWA189S(需 fred_api_key,可選)
        Tier 2: IMF DataMapper MANMM101 / MABMM301 / TW

    全敗回 None(§1 Fail Loud — UI 顯示「待更新」,不捏造)。

    參數:
        fred_api_key: str  FRED API key(空字串 = 不嘗試 FRED 路徑,跳到 IMF)

    Returns:
        dict | None: {'m1b_yoy': float, 'm2_yoy': float, 'gap': float, 'source': str}

    v18.454 hotfix:三個 return 皆補回 'gap' 欄(=round(m1b_yoy - m2_yoy, 2))。
    根因:tw_macro.fetch_cbc_m1b_m2() Tier 0 本就算好 gap,但此函式重新打包
    dict 時漏帶,導致 session_state['m1b_m2_info'] 從未有 'gap' 鍵 →
    macro_helpers.py 依 .get('gap') 算頂部燈號/KPI 卡恆得 None → UI 顯示「—」;
    而 section_long.py 的「策略3」區塊是自己重算 m1b_yoy-m2_yoy(未依賴此鍵),
    才會出現「頂部顯示 —,下方策略3卻顯示真實 -12.63%」的不一致(user 回報)。
    """
    import pandas as _pd_m1

    # ── Tier 0:tw_macro.fetch_cbc_m1b_m2 統一委派 ──
    try:
        from src.data.macro import fetch_cbc_m1b_m2 as _tw_cbc
        _cbc_snap = _tw_cbc()
        if _cbc_snap.get('m1b_yoy') is not None:
            _src_label = ('TWII-proxy' if _cbc_snap.get('is_proxy_tier')
                          else f'CBC-tier{_cbc_snap.get("tier_used")}')
            print(f'[M1B/tw_macro] ✅ {_src_label} '
                  f'M1B={_cbc_snap["m1b_yoy"]:.2f}% M2={_cbc_snap["m2_yoy"]:.2f}%')
            return {'m1b_yoy': _cbc_snap['m1b_yoy'],
                    'm2_yoy':  _cbc_snap['m2_yoy'],
                    'gap':     _cbc_snap.get('gap'),
                    'source':  _src_label}
    except Exception as _tw_e:
        print(f'[M1B/tw_macro] ❌ {_tw_e}')

    # ── Tier 1:FRED(台灣 M1B/M2,fetch_url + FRED_API_KEY)──
    try:
        from src.data.proxy import fetch_url as _fu_m1
        _fp_m1 = {'api_key': fred_api_key} if fred_api_key else {}
        _fred_base_p = {'file_type': 'json', 'sort_order': 'asc', 'limit': 36, **_fp_m1}
        _fred_m1b_r = _fu_m1('https://api.stlouisfed.org/fred/series/observations',
                             params={'series_id': 'MYAGM1TWA189S', **_fred_base_p},
                             timeout=12, attempts=1)
        _fred_m2_r = _fu_m1('https://api.stlouisfed.org/fred/series/observations',
                            params={'series_id': 'MYAGM2TWA189S', **_fred_base_p},
                            timeout=12, attempts=1)
        if _fred_m1b_r is None or _fred_m2_r is None:
            raise ValueError('FRED fetch_url 回傳 None')
        print('[M1B/FRED] M1 OK M2 OK')
        _obs_m1 = [o for o in _fred_m1b_r.json().get('observations', [])
                   if o.get('value', '.') != '.']
        _obs_m2 = [o for o in _fred_m2_r.json().get('observations', [])
                   if o.get('value', '.') != '.']
        _df_fred_m1 = _pd_m1.DataFrame(_obs_m1)
        _df_fred_m2 = _pd_m1.DataFrame(_obs_m2)
        for _dfm in [_df_fred_m1, _df_fred_m2]:
            _dfm['value'] = _pd_m1.to_numeric(_dfm['value'], errors='coerce')
        _df_fred_m1 = _df_fred_m1.dropna(subset=['value'])
        _df_fred_m2 = _df_fred_m2.dropna(subset=['value'])
        print(f'[M1B/FRED] M1 rows={len(_df_fred_m1)} M2 rows={len(_df_fred_m2)} '
              f'last={_df_fred_m1["date"].iloc[-1] if len(_df_fred_m1) else "?"}')
        if len(_df_fred_m1) >= 13 and len(_df_fred_m2) >= 13:
            _m1b_yoy_f = round((_df_fred_m1['value'].iloc[-1] /
                                _df_fred_m1['value'].iloc[-13] - 1) * 100, 2)
            _m2_yoy_f = round((_df_fred_m2['value'].iloc[-1] /
                               _df_fred_m2['value'].iloc[-13] - 1) * 100, 2)
            print(f'[M1B/FRED] ✅ M1B={_m1b_yoy_f:.2f}% M2={_m2_yoy_f:.2f}%')
            return {'m1b_yoy': _m1b_yoy_f, 'm2_yoy': _m2_yoy_f,
                    'gap': round(_m1b_yoy_f - _m2_yoy_f, 2), 'source': 'FRED'}
    except Exception as _fred_e:
        print(f'[M1B/FRED] ❌ {_fred_e}')

    # ── Tier 2:IMF DataMapper API(FRED 備援,全球可達)──
    try:
        # MABMM301 = M2 年增率%, MANMM101 = M1 年增率%(IMF IFS)
        from src.data.proxy import fetch_url as _fu_imf
        _imf_m1_r = _fu_imf(
            'https://www.imf.org/external/datamapper/api/v1/MANMM101/TW',
            timeout=15, attempts=1)
        _imf_m2_r = _fu_imf(
            'https://www.imf.org/external/datamapper/api/v1/MABMM301/TW',
            timeout=15, attempts=1)
        print(f'[M1B/IMF] M1={getattr(_imf_m1_r, "status_code", None)} '
              f'M2={getattr(_imf_m2_r, "status_code", None)}')
        if (_imf_m1_r is not None and _imf_m2_r is not None
                and _imf_m1_r.status_code == 200 and _imf_m2_r.status_code == 200):
            _imf_m1_vals = _imf_m1_r.json().get('values', {}).get('MANMM101', {}).get('TW', {})
            _imf_m2_vals = _imf_m2_r.json().get('values', {}).get('MABMM301', {}).get('TW', {})
            print(f'[M1B/IMF] M1 years={len(_imf_m1_vals)} M2 years={len(_imf_m2_vals)}')
            if _imf_m1_vals and _imf_m2_vals:
                # IMF 返回的已是 YoY 年增率%,取最新一年
                _imf_m1_sorted = sorted([(k, float(v)) for k, v in _imf_m1_vals.items()
                                         if v is not None], key=lambda x: x[0])
                _imf_m2_sorted = sorted([(k, float(v)) for k, v in _imf_m2_vals.items()
                                         if v is not None], key=lambda x: x[0])
                if _imf_m1_sorted and _imf_m2_sorted:
                    _m1b_yoy_imf = round(_imf_m1_sorted[-1][1], 2)
                    _m2_yoy_imf = round(_imf_m2_sorted[-1][1], 2)
                    print(f'[M1B/IMF] ✅ year={_imf_m1_sorted[-1][0]} '
                          f'M1B={_m1b_yoy_imf:.2f}% M2={_m2_yoy_imf:.2f}%')
                    return {'m1b_yoy': _m1b_yoy_imf, 'm2_yoy': _m2_yoy_imf,
                            'gap': round(_m1b_yoy_imf - _m2_yoy_imf, 2),
                            'source': f'IMF({_imf_m1_sorted[-1][0]})'}
    except Exception as _imf_e:
        print(f'[M1B/IMF] ❌ {_imf_e}')

    # 全敗回 None(§1 Fail Loud — UI 顯示「待更新」)
    print('[M1B] 所有路徑失敗,回傳 None')
    return None


def compute_twii_bias(twii_local) -> dict | None:
    """從 TWII 日線 df 算 MA20/60/120/240 + bias_*。

    P3-D3 v18.389 深層拔毒:從 tab_macro.py:976-1018 `_job_bias` inline def 抽出(L5→L1)。
    若 `twii_local` 資料不足 240 天(冷啟動 / 90 天 cache),fallback `fetch_twii_2y_for_ma240()`。
    全空仍回 None(§1 Fail Loud)。

    參數:
        twii_local: pd.DataFrame | None  ^TWII OHLCV(由 tab_macro 並行 fetch 結果取)

    Returns:
        dict | None:
            {bias_20/60/240, price, ma20/60/120/240, data_days, is_estimated}
            data_days < 240 時 is_estimated=True(caller 顯示「估算」chip)。
            twii 全空 / Close 欄缺失 / fetch 全敗 → None。
    """
    _twii = twii_local
    _cc_b = 'Close' if (_twii is not None and 'Close' in getattr(_twii, 'columns', [])) else 'close'
    _n_existing = len(_twii) if _twii is not None and not _twii.empty else 0
    if _n_existing < 240:
        try:
            _twii_2y = fetch_twii_2y_for_ma240()
            if _twii_2y is not None and len(_twii_2y) >= 240:
                _twii = _twii_2y
                _cc_b = 'Close'
            else:
                print(f'[Bias] 2y 資料不足,使用現有 {_n_existing} 天')
        except Exception as _yf_b_e:
            print(f'[Bias] yfinance 2y 失敗: {_yf_b_e}')
    if _twii is None or _twii.empty:
        return None
    # 寬鬆欄位查找:Close / close / Adj Close
    if _cc_b not in _twii.columns:
        _cc_b = next((c for c in _twii.columns
                      if str(c).lower() in ('close', 'adj close', 'adjclose')), None)
        if _cc_b is None:
            print(f'[Bias] 找不到 Close 欄,現有欄位={list(_twii.columns)[:6]}')
            return None
    _cs = _twii[_cc_b].dropna()
    _n = len(_cs)
    if _n == 0:
        return None
    _lp = float(_cs.iloc[-1])
    _ma20 = float(_cs.tail(min(20, _n)).mean())
    _ma60 = float(_cs.tail(min(60, _n)).mean())
    _ma120 = float(_cs.tail(min(120, _n)).mean())
    _ma240 = float(_cs.tail(min(240, _n)).mean())
    # R-CALC-3 v18.412:乖離率公式 SSOT 收(`(p-ma)/ma*100` → calc_bias_pct)
    _b240_log = calc_bias_pct(_lp, _ma240, decimals=1) or 0
    print(f'[Bias] price={_lp:.0f} MA240={_ma240:.0f} '
          f'bias240={_b240_log:.1f}% (n={_n})')
    return {
        'bias_20':  calc_bias_pct(_lp, _ma20,  decimals=1) or 0,
        'bias_60':  calc_bias_pct(_lp, _ma60,  decimals=1) or 0,
        'bias_240': calc_bias_pct(_lp, _ma240, decimals=1) or 0,
        'price': _lp, 'ma20': _ma20, 'ma60': _ma60, 'ma120': _ma120, 'ma240': _ma240,
        'data_days': _n, 'is_estimated': _n < 240,
    }


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_twii_2y_for_ma240():
    """抓 ^TWII 2 年 OHLCV(MA240 計算用)。

    P1-1c v18.376 深層拔毒:從 tab_macro.py:973 抽出(L5→L1)。
    auto_adjust=True + MultiIndex 展平。資料不足 240 天回 None(caller fallback)。

    Returns:
        pd.DataFrame | None:DataFrame 含 'Close' 欄;失敗或不足回 None。
    """
    try:
        import yfinance as _yf_bias
        import pandas as _pd_bias
        df = _yf_bias.download('^TWII', period='2y', progress=False, auto_adjust=True)
        if df is not None and isinstance(df.columns, _pd_bias.MultiIndex):
            try:
                df.columns = df.columns.get_level_values(0)
                print(f'[Bias] MultiIndex → 展平欄位: {list(df.columns)}')
            except Exception as _mi_e:
                print(f'[Bias] MultiIndex 展平失敗: {_mi_e}')
        if df is not None and len(df) >= 240:
            try:
                df.attrs.setdefault('source', 'yfinance:^TWII:2y:1d')
                df.attrs.setdefault('fetched_at', _pd_bias.Timestamp.now('UTC').isoformat())
            except Exception:
                pass
            print(f'[Bias] yfinance ^TWII 2y 抓到 {len(df)} 天,欄位={list(df.columns)[:4]}')
            return df
        print(f'[Bias] yfinance 2y 資料不足 ({len(df) if df is not None else 0} 天)')
        return None
    except Exception as _e:
        print(f'[Bias] yfinance ^TWII 2y 失敗: {_e}')
        return None


# ═══════════════════════════════════════════════════════════════════════════
# P3-D1 v18.389:_job_macro 5 sub-fetcher 完整下沉(L5→L1)
#   原 tab_macro.py:943-1451 inline def(共 604 LOC)→ 本檔 fetch_*_block。
#   接口契約:命中回 `{key: {...}}`,失敗回 `{'_err_<key>': reason}`(§1)。
# ═══════════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_cpi_block(fred_api_key: str = '') -> dict:
    """美國核心 CPI YoY(CPILFESL,3 路 fallback)。

    Tier 0: FRED 公開 fredgraph.csv(無需 key,最穩)
    Tier 1: FRED API(帶 fred_api_key 加速)
    Tier 2: BLS API(CUSR0000SA0L1E,系列 ID 不同)

    P3-D1 v18.389 抽出。logic verbatim from tab_macro._job_macro._fetch_cpi。
    """
    import datetime as _dt_cpi
    import io as _io_cpi
    import pandas as _pd_cpi
    _s = _make_proxy_session()
    _cpi_errs = []
    # ── 方案0: FRED 公開 fredgraph.csv(CPILFESL,無需 key)────────
    try:
        from src.data.proxy import fetch_url as _fu_cpi
        _r0 = _fu_cpi('https://fred.stlouisfed.org/graph/fredgraph.csv',
                      params={'id': 'CPILFESL'},
                      timeout=10, attempts=1)
        print(f'[Macro/CPI/fredgraph] response={"OK" if _r0 else "None"}')
        if _r0 is not None and _r0.status_code == 200:
            _df0 = _pd_cpi.read_csv(
                _io_cpi.StringIO(_r0.content.decode('utf-8', errors='ignore')))
            _df0 = _df0.dropna()
            if len(_df0) >= 13:
                _vals0 = _pd_cpi.to_numeric(_df0.iloc[:, 1],
                                            errors='coerce').dropna()
                if len(_vals0) >= 13:
                    _yoy = round((_vals0.iloc[-1] / _vals0.iloc[-13] - 1) * 100, 2)
                    # v18.169:補 prev_yoy 供 MK 黃金拐點偵測(CPI 月度變化)
                    _prev_yoy = (round((_vals0.iloc[-2] / _vals0.iloc[-14] - 1) * 100, 2)
                                 if len(_vals0) >= 14 else None)
                    _date = str(_df0.iloc[-1, 0])[:10]
                    print(f'[Macro/CPI/fredgraph] ✅ YoY={_yoy:.2f}% prev={_prev_yoy} date={_date}')
                    return {'us_core_cpi': {'yoy': _yoy, 'prev_yoy': _prev_yoy,
                                            'date': _date,
                                            'source': 'FRED/fredgraph.csv',
                                            'series_id': 'CPILFESL'}}
            _cpi_errs.append(f'fredgraph:rows<13({len(_df0)})')
        else:
            _cpi_errs.append(f'fredgraph:HTTP{_r0.status_code if _r0 else "None"}')
    except Exception as _e:
        _cpi_errs.append(f'fredgraph:{type(_e).__name__}')
        print(f'[Macro/CPI/fredgraph] ❌ {_e}')
    # ── 方案1: FRED API(CPILFESL + API key 加速)────────────────
    try:
        from src.data.proxy import fetch_url as _fu_cpi
        _cpi_start = (_dt_cpi.datetime.now() - _dt_cpi.timedelta(days=365 * 3)).strftime('%Y-%m-%d')
        _cpi_end = _dt_cpi.datetime.now().strftime('%Y-%m-%d')
        _cpi_p = {'series_id': 'CPILFESL', 'file_type': 'json',
                  'sort_order': 'asc', 'limit': 36,
                  'observation_start': _cpi_start,
                  'observation_end': _cpi_end}
        if fred_api_key:
            _cpi_p['api_key'] = fred_api_key
        _rc1 = _fu_cpi('https://api.stlouisfed.org/fred/series/observations',
                       params=_cpi_p, timeout=12, attempts=1)
        print(f'[Macro/CPI/FRED-API] response={"OK" if _rc1 else "None"}')
        if _rc1 is not None:
            _obs_c = [o for o in _rc1.json().get('observations', [])
                      if o.get('value', '.') != '.']
            if len(_obs_c) >= 13:
                _vals_c = [float(o['value']) for o in _obs_c]
                _yoy = round((_vals_c[-1] / _vals_c[-13] - 1) * 100, 2)
                _prev_yoy = (round((_vals_c[-2] / _vals_c[-14] - 1) * 100, 2)
                             if len(_vals_c) >= 14 else None)
                _date = _obs_c[-1]['date']
                print(f'[Macro/CPI/FRED-API] ✅ YoY={_yoy:.2f}% prev={_prev_yoy} date={_date}')
                return {'us_core_cpi': {'yoy': _yoy, 'prev_yoy': _prev_yoy,
                                        'date': _date,
                                        'source': 'FRED-API',
                                        'series_id': 'CPILFESL'}}
    except Exception as _e:
        _cpi_errs.append(f'FRED-API:{type(_e).__name__}')
        print(f'[Macro/CPI/FRED-API] ❌ {_e}')
    # ── 方案2: BLS API(CUSR0000SA0L1E 核心 CPI SA)───────────────
    try:
        _rc = _s.post('https://api.bls.gov/publicAPI/v2/timeseries/data/',
                      json={'seriesid': ['CUSR0000SA0L1E'],
                            'startyear': str(_dt_cpi.date.today().year - 2),
                            'endyear': str(_dt_cpi.date.today().year)},
                      headers={'Content-Type': 'application/json',
                               'User-Agent': 'Mozilla/5.0'},
                      timeout=15, verify=False)
        print(f'[Macro/CPI/BLS] status={_rc.status_code}')
        if _rc.status_code == 200:
            _j = _rc.json()
            _obs = (_j.get('Results') or {}).get('series', [{}])[0].get('data', [])
            if len(_obs) >= 13:
                _s2 = sorted([o for o in _obs if o.get('period', 'M13') != 'M13'],
                             key=lambda x: (x['year'], x['period']))
                _valid = []
                for _o in _s2:
                    try:
                        _v = float(str(_o.get('value', '')).replace(',', ''))
                        if _v > 0:
                            _valid.append((_o, _v))
                    except Exception:
                        pass
                if len(_valid) >= 13:
                    _ents = [o for o, _ in _valid]
                    _vals = [v for _, v in _valid]
                    _yoy = round((_vals[-1] / _vals[-13] - 1) * 100, 2)
                    _prev_yoy = (round((_vals[-2] / _vals[-14] - 1) * 100, 2)
                                 if len(_vals) >= 14 else None)
                    _last = _ents[-1]
                    _date = f"{_last['year']}-{int(_last['period'][1:]):02d}-01"
                    print(f'[Macro/CPI/BLS] ✅ YoY={_yoy:.2f}% prev={_prev_yoy} date={_date}')
                    return {'us_core_cpi': {'yoy': _yoy, 'prev_yoy': _prev_yoy,
                                            'date': _date,
                                            'source': 'BLS',
                                            'series_id': 'CUSR0000SA0L1E'}}
    except Exception as _e:
        _cpi_errs.append(f'BLS:{type(_e).__name__}')
        print(f'[Macro/CPI/BLS] ❌ {_e}')
    return {'_err_cpi': ' | '.join(_cpi_errs) or 'all failed'}


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_us10y_block(fred_api_key: str = '') -> dict:
    """美 10 年期殖利率 FRED DGS10(R3 v18.405)。

    對齊 reconcile_panel._get_us10y_pair 需要的 macro_info['us10y']['value']。
    Yahoo ^TNX 由既有 cl_data.intl['10Y公債殖利率'] 提供(雙源對帳 source B)。

    Tier 0:FRED 公開 fredgraph.csv(無需 key)
    Tier 1:FRED API(帶 key 加速,可選)

    Returns:
        {'us10y': {'current': float, 'date': 'YYYY-MM-DD',
                   'source': str, 'series_id': 'DGS10', 'fetched_at': ISO}}
        失敗 → {'us10y': {'_err': str, 'current': None}}
    """
    import io as _io_u
    import pandas as _pd_u
    _errs = []
    # Tier 0:FRED 公開 fredgraph.csv
    try:
        from src.data.proxy import fetch_url as _fu_u
        _r0 = _fu_u('https://fred.stlouisfed.org/graph/fredgraph.csv',
                    params={'id': 'DGS10'},
                    timeout=10, attempts=1)
        if _r0 is not None and _r0.status_code == 200:
            _df0 = _pd_u.read_csv(
                _io_u.StringIO(_r0.content.decode('utf-8', errors='ignore')))
            _df0 = _df0.dropna()
            if len(_df0) >= 1:
                _vals = _pd_u.to_numeric(_df0.iloc[:, 1], errors='coerce').dropna()
                if len(_vals) >= 1:
                    _curr = round(float(_vals.iloc[-1]), 3)
                    _date = str(_df0.iloc[-1, 0])[:10]
                    return {'us10y': {
                        'current': _curr, 'date': _date,
                        'value': _curr,  # 對齊 reconcile_panel._get_us10y_pair 取 .value
                        'source': 'FRED/fredgraph.csv:DGS10',
                        'series_id': 'DGS10',
                        'fetched_at': _pd_u.Timestamp.now('UTC').isoformat(),
                    }}
            _errs.append(f'fredgraph:rows<1({len(_df0)})')
        else:
            _errs.append(f'fredgraph:HTTP{_r0.status_code if _r0 else "None"}')
    except Exception as _e:
        _errs.append(f'fredgraph:{type(_e).__name__}:{_e}')
        print(f'[Macro/US10Y/fredgraph] ❌ {_e}')
    # 全敗
    print(f'[Macro/US10Y] ⚠️ 全敗 errs={_errs}')
    return {'us10y': {'_err': '|'.join(_errs), 'current': None, 'value': None}}


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_fed_funds_block(fred_api_key: str = '') -> dict:
    """Fed Funds Rate(FEDFUNDS,2 路 fallback)。

    Tier 0: FRED 公開 fredgraph.csv  Tier 1: FRED API(帶 key 加速)

    v18.169 起 MK 黃金拐點偵測需 CPI YoY × Fed Rate 同步月度比較。
    P3-D1 v18.389 抽出。logic verbatim from tab_macro._job_macro._fetch_fed_funds。
    """
    import datetime as _dt_ff
    import io as _io_ff
    import pandas as _pd_ff
    _ff_errs = []
    # ── 方案0: FRED 公開 fredgraph.csv(無需 key)────────────────
    try:
        from src.data.proxy import fetch_url as _fu_ff
        _r0 = _fu_ff('https://fred.stlouisfed.org/graph/fredgraph.csv',
                     params={'id': 'FEDFUNDS'},
                     timeout=10, attempts=1)
        print(f'[Macro/FedFunds/fredgraph] response={"OK" if _r0 else "None"}')
        if _r0 is not None and _r0.status_code == 200:
            _df0 = _pd_ff.read_csv(
                _io_ff.StringIO(_r0.content.decode('utf-8', errors='ignore')))
            _df0 = _df0.dropna()
            if len(_df0) >= 2:
                _vals0 = _pd_ff.to_numeric(_df0.iloc[:, 1],
                                           errors='coerce').dropna()
                if len(_vals0) >= 2:
                    _curr = round(float(_vals0.iloc[-1]), 2)
                    _prev = round(float(_vals0.iloc[-2]), 2)
                    _date = str(_df0.iloc[-1, 0])[:10]
                    print(f'[Macro/FedFunds/fredgraph] ✅ {_prev:.2f}%→{_curr:.2f}% date={_date}')
                    return {'fed_funds': {'current': _curr, 'prev': _prev,
                                          'date': _date,
                                          'source': 'FRED/fredgraph.csv',
                                          'series_id': 'FEDFUNDS'}}
            _ff_errs.append(f'fredgraph:rows<2({len(_df0)})')
        else:
            _ff_errs.append(f'fredgraph:HTTP{_r0.status_code if _r0 else "None"}')
    except Exception as _e:
        _ff_errs.append(f'fredgraph:{type(_e).__name__}')
        print(f'[Macro/FedFunds/fredgraph] ❌ {_e}')
    # ── 方案1: FRED API(FEDFUNDS + API key)────────────────────
    try:
        from src.data.proxy import fetch_url as _fu_ff
        _ff_start = (_dt_ff.datetime.now() - _dt_ff.timedelta(days=365 * 2)).strftime('%Y-%m-%d')
        _ff_end = _dt_ff.datetime.now().strftime('%Y-%m-%d')
        _ff_p = {'series_id': 'FEDFUNDS', 'file_type': 'json',
                 'sort_order': 'asc', 'limit': 24,
                 'observation_start': _ff_start,
                 'observation_end': _ff_end}
        if fred_api_key:
            _ff_p['api_key'] = fred_api_key
        _rc1 = _fu_ff('https://api.stlouisfed.org/fred/series/observations',
                      params=_ff_p, timeout=12, attempts=1)
        print(f'[Macro/FedFunds/FRED-API] response={"OK" if _rc1 else "None"}')
        if _rc1 is not None:
            _obs_f = [o for o in _rc1.json().get('observations', [])
                      if o.get('value', '.') != '.']
            if len(_obs_f) >= 2:
                _vals_f = [float(o['value']) for o in _obs_f]
                _curr = round(_vals_f[-1], 2)
                _prev = round(_vals_f[-2], 2)
                _date = _obs_f[-1]['date']
                print(f'[Macro/FedFunds/FRED-API] ✅ {_prev:.2f}%→{_curr:.2f}% date={_date}')
                return {'fed_funds': {'current': _curr, 'prev': _prev,
                                      'date': _date,
                                      'source': 'FRED-API',
                                      'series_id': 'FEDFUNDS'}}
    except Exception as _e:
        _ff_errs.append(f'FRED-API:{type(_e).__name__}')
        print(f'[Macro/FedFunds/FRED-API] ❌ {_e}')
    return {'_err_fed_funds': ' | '.join(_ff_errs) or 'all failed'}


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_tw_pmi_block() -> dict:
    """台灣 PMI(CIER 中華經濟研究院,委派 macro_core.fetch_tw_pmi 4 段備援)。

    session_state key 仍為 'ism_pmi' 維持向後相容(14 處讀取點不必動),
    內容是台灣 PMI;UI 顯示為「🇹🇼 台灣製造業 PMI」。
    P3-D1 v18.389 抽出。
    """
    from src.data.macro import fetch_tw_pmi as _ftp
    _result = _ftp()
    if _result.get('value') is not None:
        return {'ism_pmi': _result}
    return {'_err_pmi': _result.get('_err_pmi', '4 段備援全失敗')}


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_ndc_block() -> dict:
    """NDC 景氣對策信號(StockFeel + MacroMicro 雙源,v10.57.0 復活)。

    舊源全廢(FinMind/NDC JSON/CKAN/行動版 HTML 都失效),改抓第三方。
    P3-D1 v18.389 抽出。
    """
    import re as _re_ndc
    from src.data.proxy import fetch_url as _fu_ndc
    from bs4 import BeautifulSoup as _BS_ndc

    # 方案 A: StockFeel 股感(每月更新文章,HTML 含「綜合分數 39」)
    try:
        _sf_url = ('https://www.stockfeel.com.tw/'
                   '%E6%99%AF%E6%B0%A3%E5%B0%8D%E7%AD%96%E4%BF%A1%E8%99%9F-'
                   '%E6%99%AF%E6%B0%A3%E6%8C%87%E6%A8%99-%E7%B7%A8%E5%88%B6-'
                   '%E5%9C%8B%E7%99%BC%E6%9C%83/')
        _sf_r = _fu_ndc(_sf_url, timeout=12, attempts=1)
        if _sf_r is not None:
            _sf_r.encoding = 'utf-8'
            _txt_sf = _BS_ndc(_sf_r.text, 'html.parser').get_text(' ', strip=True)
            _m_sf = _re_ndc.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月[^。]{0,80}?綜合(?:判斷)?分數[^\d]{0,15}(\d{1,2})\s*分',
                _txt_sf)
            if _m_sf:
                _yr_sf, _mo_sf, _sc_sf = _m_sf.group(1), _m_sf.group(2), int(_m_sf.group(3))
                if 9 <= _sc_sf <= 45:
                    _date_sf = f'{_yr_sf}-{int(_mo_sf):02d}-01'
                    print(f'[NDC/StockFeel] ✅ score={_sc_sf} date={_date_sf}')
                    return {'ndc_signal': {'score': _sc_sf, 'signal': None,
                                           'date': _date_sf, 'source': 'StockFeel'}}
            print('[NDC/StockFeel] ⚠️ 未匹配「YYYY年M月...綜合分數N分」')
    except Exception as _e_sf:
        print(f'[NDC/StockFeel] ❌ {type(_e_sf).__name__}: {_e_sf}')

    # 方案 B: MacroMicro 財經 M 平方(UGC Charts 公開頁面)
    try:
        _mm_url = 'https://www.macromicro.me/collections/10/tw-monitoring-indicators-relative'
        _mm_r = _fu_ndc(_mm_url, timeout=12, attempts=1)
        if _mm_r is not None:
            _mm_r.encoding = 'utf-8'
            _txt_mm = _BS_ndc(_mm_r.text, 'html.parser').get_text(' ', strip=True)
            _m_mm = _re_ndc.search(
                r'景氣對策信號[^。]{0,200}?(\d{1,2})\s*分',
                _txt_mm)
            if _m_mm:
                _sc_mm = int(_m_mm.group(1))
                if 9 <= _sc_mm <= 45:
                    print(f'[NDC/MacroMicro] ✅ score={_sc_mm}')
                    return {'ndc_signal': {'score': _sc_mm, 'signal': None,
                                           'date': '', 'source': 'MacroMicro'}}
            print('[NDC/MacroMicro] ⚠️ 未匹配「景氣對策信號...N分」')
    except Exception as _e_mm:
        print(f'[NDC/MacroMicro] ❌ {type(_e_mm).__name__}: {_e_mm}')

    print('[NDC] ⚠️ 雙源皆失敗,回 _err_ndc 標記')
    return {'_err_ndc': 'StockFeel + MacroMicro 雙源皆失敗'}


@st.cache_data(ttl=TTL_1HOUR, show_spinner=False)
def fetch_export_block(fred_api_key: str = '', finmind_token: str = '') -> dict:
    """台灣出口 YoY(5 路 fallback)。

    Tier 0: stat.gov.tw(DGBAS 官方點資料頁,走 fetch_url NAS proxy)
    Tier 1: FinMind TaiwanEconomicIndicator(需 finmind_token)
    Tier 2: MOF 財政部統計處 CSV(NAS proxy 台灣 IP 可直接存取)
    Tier 3: data.gov.tw dataset 6053(海關進出口貿易統計)
    Tier 4: FRED XTEXVA01TWM664S(OECD MEI,延遲 2-3 月)
    Tier 5: data.gov.tw CKAN(財政部進出口統計 fallback)

    全敗回 {}(§1:**不捏造**任何數值),caller 顯示「待取得」placeholder。
    P3-D1 v18.389 抽出。logic verbatim from tab_macro._job_macro._fetch_export。
    """
    import datetime as _dt_ex
    import io as _io_ex
    import re as _re_ex
    import pandas as _pd7
    _s_ex = _make_proxy_session()
    _s_ex.verify = False
    _s_ex.headers.update({'User-Agent': 'Mozilla/5.0',
                          'Accept': 'application/json'})

    # 方案 0: 中華民國統計資訊網 stat.gov.tw 出口年增率
    try:
        from src.data.proxy import fetch_url as _fu_stat
        from bs4 import BeautifulSoup as _BS_stat
        _stat_url = ('https://www.stat.gov.tw/Point.aspx?'
                     'sid=t.8&n=3587&sms=11480')
        _r_stat = _fu_stat(_stat_url, timeout=12, attempts=1)
        if _r_stat is not None and _r_stat.status_code == 200:
            _r_stat.encoding = 'utf-8'
            _txt_stat = _BS_stat(_r_stat.text, 'html.parser').get_text(' ', strip=True)
            _m_stat = _re_ex.search(
                r'(20\d{2})\s*年\s*(\d{1,2})\s*月[^。]{0,80}?'
                r'出口[^。]{0,30}?年增率?[^\d\-]{0,15}(-?\d{1,3}\.\d)\s*%?',
                _txt_stat)
            if _m_stat:
                _yr_s, _mo_s = int(_m_stat.group(1)), int(_m_stat.group(2))
                _yoy_s = float(_m_stat.group(3))
                if 1 <= _mo_s <= 12 and -80 <= _yoy_s <= 200:
                    _date_s = f'{_yr_s}-{_mo_s:02d}'
                    print(f'[Export/stat.gov.tw] ✅ YoY={_yoy_s:.2f}% date={_date_s}')
                    return {'tw_export': {'yoy': _yoy_s, 'date': _date_s,
                                          'source': 'stat.gov.tw'}}
            print('[Export/stat.gov.tw] ❌ HTML 未含可解析 YoY')
        else:
            print(f'[Export/stat.gov.tw] ❌ HTTP {getattr(_r_stat, "status_code", "None")}')
    except Exception as _e_stat:
        print(f'[Export/stat.gov.tw] ❌ {type(_e_stat).__name__}: {_e_stat}')

    # 方案 FM: FinMind TaiwanEconomicIndicator
    try:
        if finmind_token:
            _ex_start_fm = (_dt_ex.date.today() - _dt_ex.timedelta(days=365 * 2)).strftime('%Y-%m-%d')
            _fm_ex_r = _s_ex.get(
                FINMIND_API_URL,
                params={'dataset': 'TaiwanEconomicIndicator',
                        'start_date': _ex_start_fm, 'token': finmind_token},
                timeout=10)
            if _fm_ex_r.status_code == 200:
                _fm_ex_data = _fm_ex_r.json().get('data', [])
                for _kw_ex in ('出口', '外銷', 'export', 'Export'):
                    _ex_rows = [r for r in _fm_ex_data
                                if _kw_ex in str(r.get('indicator', ''))]
                    if _ex_rows:
                        _ex_rows.sort(key=lambda r: r.get('date', ''))
                        _ind_name = _ex_rows[-1].get('indicator')
                        _same = [r for r in _ex_rows if r.get('indicator') == _ind_name]
                        if len(_same) >= 13:
                            _cur_ex = float(_same[-1].get('value', 0) or 0)
                            _prev_ex = float(_same[-13].get('value', 1) or 1)
                            if _prev_ex != 0:
                                _yoy_ex = round((_cur_ex - _prev_ex) / abs(_prev_ex) * 100, 2)
                                _date_ex = str(_same[-1].get('date', ''))[:7]
                                print(f'[Export/FinMind] ✅ YoY={_yoy_ex:.2f}% date={_date_ex} ind={_ind_name}')
                                return {'tw_export': {'yoy': _yoy_ex, 'date': _date_ex,
                                                      'source': f'FinMind/{_ind_name}'}}
                        break
    except Exception as _e_fm_ex:
        print(f'[Export/FinMind] ❌ {type(_e_fm_ex).__name__}: {_e_fm_ex}')

    # 方案 MOF: 財政部統計處 CSV — 透過 NAS proxy(台灣 IP)
    try:
        from src.data.proxy import fetch_url as _fu_ex
        _now_ex = _dt_ex.date.today()
        _mof_found = False
        for _m_off in range(0, 2):
            if _mof_found:
                break
            _chk = (_now_ex.replace(day=1) - _dt_ex.timedelta(days=_m_off * 30))
            for _mof_url in [
                f'https://service.mof.gov.tw/public/Data/statistic/trade/excel/{_chk.year}{_chk.month:02d}.csv',
                f'https://service.mof.gov.tw/public/Data/statistic/trade/html/{_chk.year}{_chk.month:02d}.csv',
            ]:
                try:
                    _r_mof = _fu_ex(_mof_url, timeout=10, attempts=1)
                    if _r_mof is not None and len(_r_mof.content) > 500:
                        _df_mof = _pd7.read_csv(
                            _io_ex.StringIO(_r_mof.content.decode('utf-8-sig', errors='ignore')),
                            header=None)
                        _vals_mof = _pd7.to_numeric(_df_mof.iloc[:, 1], errors='coerce').dropna()
                        if len(_vals_mof) >= 13:
                            _yoy_mof = round((_vals_mof.iloc[-1] - _vals_mof.iloc[-13]) /
                                             abs(_vals_mof.iloc[-13]) * 100, 2)
                            print(f'[Export/MOF] ✅ YoY={_yoy_mof:.2f}% url={_mof_url[-25:]}')
                            _mof_found = True
                            return {'tw_export': {'yoy': _yoy_mof,
                                                  'date': f'{_chk.year}-{_chk.month:02d}',
                                                  'source': 'MOF-proxy'}}
                except Exception:
                    continue
    except Exception as _e_mof:
        print(f'[Export/MOF] ❌ {type(_e_mof).__name__}: {_e_mof}')

    # 方案 DGTW: data.gov.tw dataset 6053
    try:
        from src.data.proxy import fetch_url as _fu_ex
        for _meta_url_ex in (
            'https://data.gov.tw/api/v2/rest/dataset/6053',
            'https://data.gov.tw/api/v1/rest/dataset/6053',
        ):
            try:
                _rm_ex = _fu_ex(_meta_url_ex, timeout=10, attempts=1,
                                headers={'Accept': 'application/json'})
                if _rm_ex is None or _rm_ex.status_code != 200:
                    continue
                _jm_ex = _rm_ex.json()
                _res_ex = (_jm_ex.get('result', {}).get('resources')
                           or _jm_ex.get('resources')
                           or _jm_ex.get('result', {}).get('distribution')
                           or [])
                _csv_url_ex = None
                for _it in _res_ex:
                    _fmt = str(_it.get('format', '')).upper()
                    _u = (_it.get('url') or _it.get('resourceDownloadUrl')
                          or _it.get('downloadUrl'))
                    if _fmt in ('CSV', 'TEXT', 'XLS', 'XLSX') and _u:
                        _csv_url_ex = _u
                        break
                if not _csv_url_ex:
                    continue
                _rc_ex = _fu_ex(_csv_url_ex, timeout=15, attempts=2)
                if _rc_ex is None or _rc_ex.status_code != 200:
                    continue
                _df_dgtw = _pd7.read_csv(_io_ex.StringIO(
                    _rc_ex.content.decode('utf-8-sig', errors='ignore')))
                _val_k = next((c for c in _df_dgtw.columns
                               if '出口' in str(c) and not any(
                                   _x in str(c) for _x in ('增', '率', '比', '差'))), None)
                _dt_k = next((c for c in _df_dgtw.columns
                              if any(_x in str(c) for _x in ('年月', '月份', '日期', 'DATE', 'date'))), None)
                if _val_k and _dt_k and len(_df_dgtw) >= 13:
                    _df_dgtw = _df_dgtw.dropna(subset=[_val_k]).copy()
                    _df_dgtw[_val_k] = _pd7.to_numeric(
                        _df_dgtw[_val_k].astype(str).str.replace(',', ''),
                        errors='coerce')
                    _df_dgtw = _df_dgtw.dropna(subset=[_val_k])
                    if len(_df_dgtw) >= 13:
                        _cur_d = float(_df_dgtw[_val_k].iloc[-1])
                        _prv_d = float(_df_dgtw[_val_k].iloc[-13])
                        if _prv_d != 0:
                            _yoy_d = round((_cur_d - _prv_d) / abs(_prv_d) * 100, 2)
                            _date_d = str(_df_dgtw[_dt_k].iloc[-1])[:7]
                            print(f'[Export/data.gov.tw-6053] ✅ YoY={_yoy_d:.2f}% date={_date_d}')
                            return {'tw_export': {'yoy': _yoy_d, 'date': _date_d,
                                                  'source': 'data.gov.tw/6053'}}
            except Exception:
                continue
    except Exception as _e_dgtw:
        print(f'[Export/data.gov.tw-6053] ❌ {type(_e_dgtw).__name__}: {_e_dgtw}')

    # 方案 FRED: FRED CSV(XTEXVA01TWM664S,OECD MEI,延遲 2-3 月)
    try:
        from src.data.proxy import fetch_url as _fu_ex
        _ex_start = (_dt_ex.datetime.now() - _dt_ex.timedelta(days=365 * 5)).strftime('%Y-%m-%d')
        _ex_end = _dt_ex.datetime.now().strftime('%Y-%m-%d')
        _fred_ex_p = {'id': 'XTEXVA01TWM664S', 'observation_start': _ex_start,
                      'observation_end': _ex_end}
        if fred_api_key:
            _fred_ex_p['api_key'] = fred_api_key
        _r_fred = _fu_ex('https://fred.stlouisfed.org/graph/fredgraph.csv',
                         params=_fred_ex_p, timeout=8, attempts=1)
        print(f'[Export/FRED-XTEXVA01TWM664S] response={"OK" if _r_fred else "None"}')
        if _r_fred is not None and _r_fred.text.strip():
            _df_fred = _pd7.read_csv(
                _io_ex.StringIO(_r_fred.text),
                names=['date', 'value'], skiprows=1)
            _df_fred['value'] = _pd7.to_numeric(_df_fred['value'], errors='coerce')
            _df_fred = _df_fred.dropna(subset=['value'])
            if len(_df_fred) >= 13:
                _cur_f = float(_df_fred['value'].iloc[-1])
                _prev_f = float(_df_fred['value'].iloc[-13])
                if _prev_f and _prev_f != 0:
                    _yoy_f = round((_cur_f - _prev_f) / abs(_prev_f) * 100, 2)
                    _date_f = str(_df_fred['date'].iloc[-1])[:7]
                    print(f'[Export/FRED-XTEXVA01TWM664S] ✅ YoY={_yoy_f:.2f}% date={_date_f}')
                    return {'tw_export': {'yoy': _yoy_f, 'date': _date_f,
                                          'source': 'FRED/XTEXVA01TWM664S'}}
    except Exception as _e_fred:
        print(f'[Export/FRED-XTEXVA01TWM664S] ❌ {type(_e_fred).__name__}: {_e_fred}')

    # 方案 GOV-MOF: data.gov.tw CKAN(財政部進出口統計)
    try:
        _pkg2 = _s_ex.get(
            'https://data.gov.tw/api/3/action/package_search',
            params={'q': '進出口貿易統計', 'fq': 'organization:mof', 'rows': 5},
            headers={'Accept': 'application/json'},
            timeout=5)
        _pkg2_j = _pkg2.json()
        _res_id2 = None
        for _pk2 in ((_pkg2_j.get('result') or {}).get('results') or []):
            for _rs2 in (_pk2.get('resources') or []):
                if _rs2.get('format', '').upper() in ('CSV', 'TEXT'):
                    _res_id2 = _rs2.get('url') or _rs2.get('download_url')
                    break
            if _res_id2:
                break
        if _res_id2:
            _csv_ex = _s_ex.get(_res_id2, timeout=10)
            _df_ex = _pd7.read_csv(
                _io_ex.StringIO(_csv_ex.content.decode('utf-8-sig', errors='ignore')))
            _val_k = next((c for c in _df_ex.columns
                           if '出口' in c and '值' in c and '增' not in c), None)
            _dt_k = next((c for c in _df_ex.columns
                          if '年月' in c or '月份' in c or 'DATE' in c.upper()), None)
            if _val_k and _dt_k and len(_df_ex) >= 13:
                _df_ex = _df_ex.dropna(subset=[_val_k])
                _cur = float(str(_df_ex[_val_k].iloc[-1]).replace(',', ''))
                _prev = float(str(_df_ex[_val_k].iloc[-13]).replace(',', ''))
                if _prev != 0:
                    _yoy = round((_cur - _prev) / abs(_prev) * 100, 2)
                    _dv = str(_df_ex[_dt_k].iloc[-1])[:7]
                    print(f'[Export/gov-mof] ✅ YoY={_yoy:.2f}% date={_dv}')
                    return {'tw_export': {'yoy': _yoy, 'date': _dv, 'source': 'MOF-CSV'}}
        print(f'[Export/gov-mof] ❌ res_id={_res_id2}')
    except Exception as _e_gov2:
        print(f'[Export/gov-mof] ❌ {type(_e_gov2).__name__}: {_e_gov2}')

    # §1 Fail Loud:所有方案全失敗 → **不捏造**任何數值(原 v18.330 修正)。
    print('[Export/fallback] ⚠️ 所有方案全失敗 → 回空(不捏造假值),UI 顯示「待取得」')
    return {}
