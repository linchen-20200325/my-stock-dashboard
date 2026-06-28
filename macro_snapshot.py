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
