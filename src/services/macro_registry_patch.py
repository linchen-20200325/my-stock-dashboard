"""src/services/macro_registry_patch.py — Registry 常態 Patch(P3-D8 v18.390 抽出)。

從 tab_macro.render_tab_macro 內 inline 抽出(原 line 977-1139,~161 LOC)。

職責(L3 service):
- 每次頁面渲染補建 data_registry 中的個股(t2_data)、ETF 單一(etf_single_data)、
  ETF 組合(etf_portfolio_data)、ETF 回測(etf_backtest_data)、比較排行(t3_data)
- 缺失大盤項目時從 cl_data + macro_info 補建(rebuild fallback)
- 整段 try/except 內聚,失敗 print 不向 caller 拋

不負責:
- 不重發 API 請求(只從 session_state 既有 data 補 registry entries)
- 不寫除 `data_registry` 外的 session_state key

§8.2 L5 → L3:caller(tab_macro)只 call `patch_registry(...)`,session
read/write 全部在 service 內;rp_entry/rp_scalar/rp_ts 由 caller 注入避循環。
"""
from __future__ import annotations

import streamlit as st

# v18.394 SSOT 修法:category 對齊 static DATA_REGISTRY 的 11 個 emoji label。
from shared.data_categories import (
    CAT_CHIPS, CAT_ETF, CAT_INTL, CAT_STOCK,
    CAT_TW_MACRO, CAT_TW_MARKET, CAT_US_MACRO,
)


def patch_registry(
    *,
    intl_map: dict,
    tw_map: dict,
    tech_map: dict,
    rp_entry,
    rp_scalar,
    rp_ts,
) -> None:
    """常態 patch data_registry,每次 rerun 都跑(不重發請求)。

    參數(全部由 caller 注入,避 L3→L2 循環):
        intl_map / tw_map / tech_map: 國際 / 台股 / 科技股 ticker map(L0)
        rp_entry / rp_scalar / rp_ts: data_registry 格式化 helper(L2)

    回傳: None。直接寫 st.session_state['data_registry']。
    """
    try:
        import pandas as _pd_rp
        _rp = dict(st.session_state.get('data_registry') or {})
        # proxy 日期:優先用總經更新時間;未更新過則用今天
        import datetime as _dt_prp
        _cl_ts_rp = st.session_state.get('cl_ts', '')
        try:
            import re as _re_rp
            _m_rp = _re_rp.search(r'(\d{4}-\d{2}-\d{2})', _cl_ts_rp)
            _proxy_rp = _m_rp.group(1) if _m_rp else _dt_prp.date.today().strftime('%Y-%m-%d')
        except Exception:
            _proxy_rp = _dt_prp.date.today().strftime('%Y-%m-%d')

        # 移除所有舊的個股 / ETF 單一 / ETF組合 / ETF回測 / 比較 key
        # S13 v19.78(第二份 review 查證時挖出):B5 v19.75 三條 [個股] 監控條目
        # (籌碼集中度/股本/5年現金流量允當比率)由 data_registry_scanner **只在
        # 「資料刷新」按鈕分支**寫入;本 patch 每次 render 都跑,原本無差別刪光
        # `[個股]` 前綴 → B5 條目在下一次非刷新 render 即被清掉(監控形同虛設)。
        # 刪除迴圈排除 B5 後綴(producer 為 scanner,非本 patch,故保留不重建)。
        _b5_keep_suffixes = (' | 籌碼集中度', ' | 股本', ' | 5年現金流量允當比率')
        for _ok in list(_rp.keys()):
            if _ok.startswith('[個股]') and _ok.endswith(_b5_keep_suffixes):
                continue
            if (_ok.startswith('[個股]') or _ok.startswith('[比較]')
                    or (_ok.startswith('[ETF]') and '|' in _ok)
                    or '[ETF組合]' in _ok or '[ETF回測]' in _ok):
                del _rp[_ok]

        # ── 個股 ──────────────────────────────────────────────────────
        _t2rp = st.session_state.get('t2_data')
        if _t2rp:
            _spfx = f'[個股] {_t2rp.get("sid","")} {(_t2rp.get("name") or _t2rp.get("sid",""))}'
            # DataFrame 型資料
            for _lbl, _key, _f in [('價格走勢', 'df', 'daily'), ('月營收', 'rev', 'monthly'),
                                   ('季財報', 'qtr', 'quarterly')]:
                _rp[f'{_spfx} | {_lbl}'] = rp_entry(_t2rp.get(_key), CAT_STOCK, _f)
            # cl/cx 為 fetch_financials 回傳的純量金額(非 DataFrame),須用 rp_scalar
            _rp[f'{_spfx} | 現金流量'] = rp_scalar(_t2rp.get('cl'), CAT_STOCK, 'quarterly', _proxy_rp)
            _rp[f'{_spfx} | 資產負債'] = rp_scalar(_t2rp.get('cx'), CAT_STOCK, 'quarterly', _proxy_rp)
            # 年度股利(list of dicts)
            import datetime as _dt_yr_rp
            _yr_rp = _t2rp.get('yearly') or []
            if _yr_rp:
                _yr_raw = str(_yr_rp[-1].get('year', ''))[:4]
                if _yr_raw.isdigit():
                    _yr_date = f'{_yr_raw}-12-31'
                    # 若為未來日期(如年度=當年但12月尚未到),截斷至今天
                    _today_cap = _dt_yr_rp.date.today().strftime('%Y-%m-%d')
                    _yr_date = min(_yr_date, _today_cap)
                else:
                    _yr_date = _proxy_rp
                _rp[f'{_spfx} | 年度股利'] = {'last_updated': _yr_date,
                                              'rows': len(_yr_rp), 'category': CAT_STOCK, 'frequency': 'yearly'}
            else:
                _rp[f'{_spfx} | 年度股利'] = {'last_updated': 'N/A', 'rows': 0,
                                              'category': CAT_STOCK, 'frequency': 'yearly', 'missing': True}
            # 健康度評分(純量)
            _rp[f'{_spfx} | 健康度評分'] = rp_scalar(_t2rp.get('health'), CAT_STOCK, 'daily', _proxy_rp)
            # 技術指標:各自獨立
            _rp[f'{_spfx} | RSI'] = rp_scalar(_t2rp.get('rsi'), CAT_STOCK, 'daily', _proxy_rp)
            _rp[f'{_spfx} | KD (K值)'] = rp_scalar(_t2rp.get('k'), CAT_STOCK, 'daily', _proxy_rp)
            _rp[f'{_spfx} | IBS 內部強弱'] = rp_scalar(_t2rp.get('ibs'), CAT_STOCK, 'daily', _proxy_rp)
            _rp[f'{_spfx} | 量比 VR'] = rp_scalar(_t2rp.get('vr'), CAT_STOCK, 'daily', _proxy_rp)
            _rp[f'{_spfx} | 布林帶'] = rp_scalar(_t2rp.get('bb'), CAT_STOCK, 'daily', _proxy_rp)
            _rp[f'{_spfx} | VCP 波幅收縮'] = rp_scalar(_t2rp.get('vcp'), CAT_STOCK, 'daily', _proxy_rp)
            # 財報延伸(合約負債/存貨/資本支出時序)
            _rp[f'{_spfx} | 合約負債/資本支出'] = rp_entry(_t2rp.get('qtr_extra'), CAT_STOCK, 'quarterly')
        else:
            _spfx0 = '[個股] — 尚未搜尋'
            for _lbl0, _f0 in [
                ('價格走勢', 'daily'), ('月營收', 'monthly'), ('季財報', 'quarterly'),
                ('現金流量', 'quarterly'), ('資產負債', 'quarterly'), ('年度股利', 'yearly'),
                ('健康度評分', 'daily'), ('RSI', 'daily'), ('KD (K值)', 'daily'),
                ('IBS 內部強弱', 'daily'), ('量比 VR', 'daily'), ('布林帶', 'daily'),
                ('VCP 波幅收縮', 'daily'), ('合約負債/資本支出', 'quarterly'),
            ]:
                _rp[f'{_spfx0} | {_lbl0}'] = {'last_updated': 'N/A', 'rows': 0,
                                              'category': CAT_STOCK, 'frequency': _f0, 'missing': True}

        # ── 比較排行 ──────────────────────────────────────────────────
        _t3rp = st.session_state.get('t3_data')
        if _t3rp and _t3rp.get('results'):
            _rp['[比較] 多股比較排行'] = {'last_updated': _proxy_rp, 'rows': len(_t3rp['results']),
                                          'category': CAT_STOCK, 'frequency': 'daily'}
        else:
            _rp['[比較] 多股比較排行'] = {'last_updated': 'N/A', 'rows': 0,
                                          'category': CAT_STOCK, 'frequency': 'daily', 'missing': True}

        # ── ETF 單一 ──────────────────────────────────────────────────
        _e1rp = st.session_state.get('etf_single_data') or {}
        _etkrp = _e1rp.get('ticker', '')
        _epfxrp = f'[ETF] {_etkrp} {_e1rp.get("name","")}'.strip() if _etkrp else '[ETF] — 尚未搜尋'
        _rp[f'{_epfxrp} | 價格走勢'] = rp_entry(_e1rp.get('price_df'), CAT_ETF, 'daily')
        _rp[f'{_epfxrp} | 現金殖利率'] = rp_scalar(_e1rp.get('cur_yield'), CAT_ETF, 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 近5年平均殖利率'] = rp_scalar(_e1rp.get('avg_yield'), CAT_ETF, 'yearly', _proxy_rp)
        _rp[f'{_epfxrp} | 近1年含息總報酬'] = rp_scalar(_e1rp.get('total_ret'), CAT_ETF, 'daily', _proxy_rp)
        _e1_prem = (_e1rp.get('premium') or {})
        _rp[f'{_epfxrp} | 折溢價率'] = rp_scalar(_e1_prem.get('premium_pct'), CAT_ETF, 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 淨值 (NAV)'] = rp_scalar(_e1_prem.get('nav'), CAT_ETF, 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 追蹤誤差'] = rp_scalar(_e1rp.get('te'), CAT_ETF, 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | VCP 波幅收縮'] = rp_scalar(_e1rp.get('vcp'), CAT_ETF, 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 內控費用率'] = rp_scalar(_e1rp.get('expense'), CAT_ETF, 'yearly', _proxy_rp)
        _rp[f'{_epfxrp} | Beta'] = rp_scalar(_e1rp.get('beta'), CAT_ETF, 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | AuM 規模'] = rp_scalar(_e1rp.get('aum'), CAT_ETF, 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | KD 技術指標'] = rp_scalar(_e1rp.get('k_val'), CAT_ETF, 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 年線乖離率 BIAS240'] = rp_scalar(_e1rp.get('bias240'), CAT_ETF, 'daily', _proxy_rp)

        # ── ETF 組合 ──────────────────────────────────────────────────
        _e2rp = st.session_state.get('etf_portfolio_data') or {}
        if _e2rp.get('rows'):
            _e2n = len(_e2rp['rows'])
            _rp[f'[ETF組合] 再平衡分析（{_e2n}檔）'] = {'last_updated': _proxy_rp, 'rows': _e2n,
                                                       'category': CAT_ETF, 'frequency': 'daily'}
        else:
            _rp['[ETF組合] 再平衡分析'] = {'last_updated': 'N/A', 'rows': 0,
                                          'category': CAT_ETF, 'frequency': 'daily', 'missing': True}

        # ── ETF 回測 ──────────────────────────────────────────────────
        _e3rp = st.session_state.get('etf_backtest_data') or {}
        if _e3rp.get('cagr') is not None:
            _e3n = len(_e3rp.get('weights', {}))
            _rp[f'[ETF回測] 回測績效（{_e3n}檔）'] = {'last_updated': _proxy_rp, 'rows': _e3n,
                                                     'category': CAT_ETF, 'frequency': 'daily'}
        else:
            _rp['[ETF回測] 回測績效'] = {'last_updated': 'N/A', 'rows': 0,
                                        'category': CAT_ETF, 'frequency': 'daily', 'missing': True}

        # 若大盤層項目(INTL/TW/TECH/籌碼/總經)完全缺失,從 cl_data 補建。
        # v18.394 SSOT:檢查 4 個 SSOT category(CAT_INTL/CAT_TW_MARKET/CAT_CHIPS/CAT_TW_MACRO/CAT_US_MACRO),
        # 取代原 '大盤' 單一字串(scanner 已分散成 5 個 SSOT category,不會再有單一 '大盤')。
        _market_cats = {CAT_INTL, CAT_TW_MARKET, CAT_CHIPS, CAT_TW_MACRO, CAT_US_MACRO}
        if not any(v.get('category') in _market_cats for v in _rp.values()):
            _cd_rb = st.session_state.get('cl_data', {})
            if _cd_rb:
                def _rb_add(_n, _df, _cat=CAT_TW_MARKET, _freq='daily'):
                    if isinstance(_df, _pd_rp.DataFrame) and not _df.empty:
                        _rp[_n] = {'last_updated': rp_ts(_df), 'rows': len(_df),
                                   'category': _cat, 'frequency': _freq}
                    else:
                        _rp[_n] = {'last_updated': 'N/A', 'rows': 0,
                                   'category': _cat, 'frequency': _freq, 'missing': True}
                for _n in intl_map:
                    _rb_add(_n, (_cd_rb.get('intl') or {}).get(_n), _cat=CAT_INTL)
                for _n in tw_map:
                    _rb_add(_n, (_cd_rb.get('tw') or {}).get(_n), _cat=CAT_TW_MARKET)
                for _n in tech_map:
                    _rb_add(_n, (_cd_rb.get('tech') or {}).get(_n), _cat=CAT_INTL)
                _rb_add('ADL 市場廣度', _cd_rb.get('adl'), _cat=CAT_TW_MARKET)
                _inst_rb = _cd_rb.get('inst') or {}
                for _ik, _iname in [('外資及陸資', '三大法人 外資買賣超'),
                                    ('投信', '三大法人 投信買賣超'),
                                    ('自營商', '三大法人 自營商買賣超')]:
                    _rp[_iname] = {'last_updated': 'N/A', 'rows': 1 if _inst_rb.get(_ik) else 0,
                                   'category': CAT_CHIPS, 'frequency': 'daily',
                                   **({} if _inst_rb.get(_ik) else {'missing': True})}
                _rp['融資餘額（台股）'] = {
                    'last_updated': 'N/A',
                    'rows': 1 if _cd_rb.get('margin') else 0,
                    'category': CAT_CHIPS, 'frequency': 'daily',
                    **({} if _cd_rb.get('margin') else {'missing': True})}
                _macro_rb = st.session_state.get('macro_info') or {}
                # v18.394:VIX → 🌐 國際金融;CPI/Fed → 🌍 美國總經;PMI/出口/NDC → 🇹🇼 台灣總經
                _macro_rb_map = [
                    ('vix',         'VIX 波動率指數',           'daily',   CAT_INTL),
                    ('us_core_cpi', '美國核心CPI年增率',         'monthly', CAT_US_MACRO),
                    ('fed_funds',   '美國 Fed Funds Rate',       'monthly', CAT_US_MACRO),
                    ('ism_pmi',     '🇹🇼 台灣 PMI 製造業指數',  'monthly', CAT_TW_MACRO),
                    ('tw_export',   '台灣出口年增率',             'monthly', CAT_TW_MACRO),
                    ('ndc_signal',  '景氣先行指標（NDC）',        'monthly', CAT_TW_MACRO),
                ]
                for _mk, _mn, _mf, _mc in _macro_rb_map:
                    _msub_rb = _macro_rb.get(_mk)
                    if _msub_rb:
                        _raw_rb = ((_msub_rb.get('date') or _msub_rb.get('period')
                                    or (_msub_rb.get('dates') or [''])[-1])
                                   if isinstance(_msub_rb, dict) else None) or _proxy_rp
                        _rp[_mn] = {'last_updated': str(_raw_rb)[:10], 'rows': 1,
                                    'category': _mc, 'frequency': _mf}
                    else:
                        _rp[_mn] = {'last_updated': 'N/A', 'rows': 0,
                                    'category': _mc, 'frequency': _mf, 'missing': True}
                print('[RegistryPatch] 大盤項目補建完成')

        st.session_state['data_registry'] = _rp
    except Exception as _rpe:
        print(f'[RegistryPatch] {_rpe}')
