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

遷移進度（v18.332 Tier2 2-D，逐 fetcher 抽出，每步 behavior-preserving + 單測）：
- [x] VIX        — fetch_vix_block（slice 1）
- [ ] CPI / Fed / PMI / NDC / Export —— 後續 slice（需共用 _mk_s session 工廠）
"""
from __future__ import annotations


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
    print(f'[Bias] price={_lp:.0f} MA240={_ma240:.0f} '
          f'bias240={((_lp-_ma240)/_ma240*100):.1f}% (n={_n})')
    return {
        'bias_20':  round((_lp - _ma20) / _ma20 * 100, 1) if _ma20 else 0,
        'bias_60':  round((_lp - _ma60) / _ma60 * 100, 1) if _ma60 else 0,
        'bias_240': round((_lp - _ma240) / _ma240 * 100, 1) if _ma240 else 0,
        'price': _lp, 'ma20': _ma20, 'ma60': _ma60, 'ma120': _ma120, 'ma240': _ma240,
        'data_days': _n, 'is_estimated': _n < 240,
    }


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
