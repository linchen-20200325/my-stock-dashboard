from data_config import CACHE_TTL
"""鞈??亥那?銵冽嚗aw Data Health Inspector嚗?

敺?etf_dashboard.py ?賢 ??render_data_health_raw() 銝餉?鞎痊憿舐內??蝬脰楝 API
?湔???洵銝??憪??摨瑞???

蝯?蝳迫嚗?蝺?/ RSI / 銋??/ AI 閰?蝑遙雿?蝞潦?
甈?嚗???蝔?| ?敺??| ?????

?澆蝡荔?app.py:9055 `render_data_health_raw()`
"""
import streamlit as st
from shared.colors import MATERIAL_ORANGE, TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW

# ??????????????????????????????????????????????????????????????????
# 鞈?閮箸 v2嚗??Raw-only ??
# ??????????????????????????????????????????????????????????????????
def render_data_health_raw():
    """
    ?芷＊蝷箏?蝬脰楝 API ?湔???洵銝??憪???
    蝯?蝳迫嚗?蝺?/ RSI / 銋??/ AI 閰?蝑遙雿?蝞潦?
    甈?嚗???蝔?| ?敺??| ?????
    """
    import pandas as _pd_r
    import datetime as _dt_r

    _today = _pd_r.Timestamp.now().normalize()

    def _last_date(df):
        """敺?DataFrame ???唳??銝?YYYY-MM-DD"""
        try:
            if df is None or (hasattr(df, 'empty') and df.empty):
                return None
            if isinstance(df.index, _pd_r.DatetimeIndex):
                v = _pd_r.Timestamp(df.index.max())
                return v.strftime('%Y-%m-%d') if not _pd_r.isna(v) else None
            for col in (['_date', 'date', 'Date', '?交?', 'period', 'quarter', '摮?漲璅惜']
                        if hasattr(df, 'columns') else []):
                if col in df.columns:
                    v = _pd_r.to_datetime(df[col], errors='coerce').max()
                    if not _pd_r.isna(v):
                        return v.strftime('%Y-%m-%d')
        except Exception:
            pass
        return None

    def _last_date_col(df, col):
        """敺?DataFrame ?摰?雿??潛???唳??""
        try:
            if df is None or (hasattr(df, 'empty') and df.empty):
                return None
            if col not in df.columns:
                return None
            sub = df[df[col].notna()]
            return _last_date(sub) if not sub.empty else None
        except Exception:
            return None

    def _probe_col(df, col):
        """甈?銝??Ｘ葫嚗?颲具etch 憭望? / 甇方?⊥迨甈?/ 閰脰?祆??箇征 / 撌脫??啜?
        Returns: (status, last_date)
          status: 'fail' (df ?游??) / 'na' (df ???⊥迨甈? / 'zero' (??雿蝛? / 'ok'
        """
        try:
            if df is None or (hasattr(df, 'empty') and df.empty):
                return ('fail', None)
            if col not in df.columns:
                return ('na', None)
            sub = df[df[col].notna()]
            if sub.empty:
                return ('zero', None)
            return ('ok', _last_date(sub))
        except Exception:
            return ('fail', None)

    def _probe_fin_field(fin_raw, key, aliases, slot='_bs_slot_latest'):
        """鞎∪甈?銝??Ｘ葫嚗?撠?_fin_raw2 ?抒? dict嚗?
        Returns: (status, value)
          'fail': fin_raw ?湧??航炊嚗PI 瘝?嚗?
          'na'  : raw slot ?抒隞颱? alias嚗迨?∠甇斤??殷?
          'zero': raw slot ??alias 雿潛 0嚗府?⊥摮? 0嚗?
          'ok'  : ??> 0
        """
        try:
            if not fin_raw or fin_raw.get('error'):
                return ('fail', None)
            v = float(fin_raw.get(key) or 0)
            if v > 0:
                return ('ok', v)
            _slot = fin_raw.get(slot) or {}
            if not _slot:
                # 瘝? raw slot嚗???fetcher ?圾?仃?????? 'fail'
                return ('fail', None)
            for _a in aliases:
                if _a in _slot:
                    try:
                        return ('zero', float(str(_slot[_a]).replace(',', '') or 0))
                    except Exception:
                        return ('zero', 0.0)
            return ('na', None)
        except Exception:
            return ('fail', None)

    def _light(date_str, freq='daily'):
        """? (icon, label)嚗req: daily / monthly / quarterly / yearly"""
        if not date_str:
            return '?', '?芸?敺?
        try:
            age = max(0, (_today - _pd_r.Timestamp(date_str)).days)
        except Exception:
            return '?', '?⊥?閫??'
        if freq == 'yearly':
            return '?', f'{age}憭拙?'
        lbl = '隞予' if age == 0 else ('?典予' if age == 1 else f'{age}憭拙?')
        if freq == 'daily':
            return ('?', lbl) if age <= 5 else ('?', f'{age}憭拙? ??')
        if freq == 'monthly':
            if age <= 90: return '?', lbl
            if age <= 120: return '?', f'{age}憭拙?'
            return '?', f'{age}憭拙? ??'
        if freq == 'quarterly':
            return ('?', lbl) if age <= 150 else ('?', f'{age}憭拙? ??')
        return ('?', lbl) if age <= 5 else ('?', f'{age}憭拙? ??')

    _FREQ_LBL = {'daily': '?仿', 'monthly': '?', 'quarterly': '摮?', 'yearly': '銝???}

    def _row(name, date_str, freq='daily', error_msg=None, optional=False,
             source='', endpoint='', proxy=False, probe_status=None):
        """鞈??圈悅摨血??
        source: 靘?蝟餌絞嚗? FRED / yfinance / FinMind嚗?
        endpoint: API 蝡舫? / Ticker嚗? NAPM / ^VIX嚗?
        proxy: ?臬蝬?Squid Proxy ?箏嚗rue=??/ False=??
        probe_status: 銝??Ｘ葫蝯?嚗???閮剔???頛?
          'na'   ????甇方?⊥迨蝘嚗??啣虜嚗??亦撣豢??殷?
          'zero' ??? 閰脰?祆???0嚗??啣虜嚗?
          'fail' ??? fetch 憭望?嚗??啣虜嚗?
          'ok'   ??憟??_light 瘚?
        """
        _fl = _FREQ_LBL.get(freq, freq)
        _px = '?? if proxy else '??
        _base = {'鞈??迂': name, '?餌?': _fl, '靘?': source or '??,
                 '蝡舫?': endpoint or '??, 'Proxy': _px}
        # ?? probe_status ?芸?嚗?颲?N/A vs zero vs fail ?????????????
        if probe_status == 'na':
            # error_msg 撣嗉閮?N/A 隤芣?嚗絲憭?ETF / 甇方?⊥迨蝘 蝑?憓?
            _na_lbl = f'??{str(error_msg)[:55]}' if error_msg else '??甇方?⊥迨蝘'
            return {**_base, '?敺??: _na_lbl, '?交?': '??, '???: '??}
        if probe_status == 'zero':
            return {**_base, '?敺??: '? 閰脰?祆???0',
                    '?交?': '??, '???: '?'}
        if probe_status == 'fail':
            _emsg = f'? ??憭望?嚗str(error_msg)[:50]}' if error_msg else '? ??憭望?'
            return {**_base, '?敺??: _emsg, '?交?': '??, '???: '?'}
        # ?? ?Ｘ??摩 ?????????????????????????????????????????????
        if not date_str and error_msg:
            short = str(error_msg)[:55]
            return {**_base, '?敺??: f'??{short}', '?交?': '??, '???: '?'}
        if not date_str and optional:
            # 韏啣?誨銵?caller 瘝策 probe_status ??靽?璅???N/A嚗???抒???
            return {**_base, '?敺??: '??甇方?⊥迨蝘', '?交?': '??, '???: '??}
        if not date_str:
            return {**_base, '?敺??: '? ?芸?敺?, '?交?': '??, '???: '?'}
        icon, lbl = _light(date_str, freq)
        return {**_base, '?敺??: lbl, '?交?': str(date_str)[:10], '???: icon}

    def _tbl(rows):
        if not rows:
            st.info('撠鞈?嚗??孛?澆???????嚗?)
            return
        _df_t = _pd_r.DataFrame(rows)
        # ?箏?甈???嚗? MJ ?? ???迂/MJ?? ??靘?/蝡舫?/Proxy ???? ?????
        _order = ['MJ 璅∠?', '鞈??迂', '?拍 MJ ??', '靘?', '蝡舫?', 'Proxy',
                  '?餌?', '?交?', '?敺??, '???]
        _cols  = [c for c in _order if c in _df_t.columns] + \
                 [c for c in _df_t.columns if c not in _order]
        st.dataframe(_df_t[_cols], use_container_width=True, hide_index=True)

    # ?? 璅? ?????????????????????????????????????????????????????
    st.markdown('### ?? ??鞈??亥那?銵冽')
    st.caption(
        '?? **?＊蝷箏?蝬脰楝 API ?湔???洵銝??憪???*??
        '???SI???Ｙ??I 閰?蝑?蝞?璅?*銝甇文?**??
    )

    # ?? ???? + ??渡???嚗???瘙?嗆??孛?潭???蝔???
    _bn1, _bn2 = st.columns([8, 2])
    with _bn1:
        st.info(
            '? **??隤?**嚗?
            '? 撌脫????圈悅 嚚?? ??撱園??鋆? 嚚?'
            '? 閰脰?祆??詨潛 0嚗??啣虜嚗?嚚???甇方?⊥迨蝘嚗??啣虜嚗?嚚?'
            '? ?仃??API/proxy/蝬脰楝??嚗?
        )
    with _bn2:
        if st.button('?? ??渡?', key='btn_diag_rerun', use_container_width=True):
            st.rerun()

    # ?? [v10.56.0] 蝡皜祈岫??擗? 6 畾萄??湛?FinMind + 5 畾萇雯?穿???
    _diag_c1, _diag_c2 = st.columns([3, 7])
    with _diag_c1:
        if st.button('?征 蝡皜祈岫??擗?嚗?畾萄??湛?',
                     key='btn_test_margin', use_container_width=True):
            try:
                from daily_checklist import fetch_margin_balance as _fmb_test
                from data_config import PKL_DIR as _pkl_dir_t
                import os as _os_t
                # ?芣? margin_balance 敹怠?嚗?敶梢?嗡? fetcher 敹怠?
                _mb_pkl = _os_t.path.join(_pkl_dir_t, 'margin_balance.pkl')
                try:
                    if _os_t.path.exists(_mb_pkl):
                        _os_t.remove(_mb_pkl)
                except Exception:
                    pass
                with st.spinner('皜祈岫銝哨??憭?35 蝘?靘?閰?6 畾萄??湛???):
                    _mb_v = _fmb_test()
                if _mb_v is not None:
                    st.session_state.setdefault('cl_data', {})['margin'] = _mb_v
                    st.session_state['_diag_margin_msg'] = (
                        f'????擗?????嚗?*{_mb_v} ??**嚗???console log ?斗?芣挾?賭葉嚗?
                    )
                else:
                    st.session_state['_diag_margin_msg'] = (
                        '??6 畾萄??游?典仃??賢???FinMind Token 憿漲? / NAS proxy ?瑞? / ?券靘??冽? / ?漱??n\n'
                        '隢 console log ??`[??擗?/...]` ?賊?閮??
                    )
                st.rerun()
            except Exception as _emb:
                st.session_state['_diag_margin_msg'] = f'??皜祈岫?啣虜嚗type(_emb).__name__}: {_emb}'
                st.rerun()
    with _diag_c2:
        _diag_msg = st.session_state.get('_diag_margin_msg')
        if _diag_msg:
            if _diag_msg.startswith('??):
                st.success(_diag_msg)
            else:
                st.error(_diag_msg)

    # ?? ?儭?NAS 隞?? + ETF ???⊥???炎皜穿?蝣箄? PROXY_URL ?臬??嚗??
    _px_c1, _px_c2 = st.columns([3, 7])
    with _px_c1:
        if st.button('?儭?皜祈岫 NAS 隞?? + ????,
                     key='btn_test_proxy', use_container_width=True):
            import time as _tt
            import re as _re_px
            _lines = []
            _ok = True
            try:
                from proxy_helper import get_proxy_config, get_nas_relay, fetch_url
                # 1) 隞???菜葫嚗?蝣潮?踝?銝?瘣?secret嚗?
                _pc = get_proxy_config()
                if _pc and _pc.get('http'):
                    _masked = _re_px.sub(r'//([^:/]+):[^@]+@', r'//\1:***@',
                                         str(_pc['http']))
                    _lines.append(f'?? Squid 隞?? PROXY_URL 撌脣皜穿?`{_masked}`')
                else:
                    _ok = False
                    _lines.append('??**?芸皜砍 PROXY_URL**嚗treamlit Cloud ??Settings ??'
                                  'Secrets 撠閮剖? NAS Squid 隞??嚗?)
                _relay = get_nas_relay()
                _lines.append(f'?? NAS FastAPI 銝剔匱蝡?'
                              f'{"撌脰身摰?`" + _relay[0] + "`" if _relay else "?芾身摰?}')
                # 2) ?箏 IP嚗?隞??嚗?蝣箄??臬韏啣??IP
                try:
                    _rip = fetch_url('https://api.ipify.org?format=json',
                                     timeout=10, attempts=1)
                    if _rip is not None and _rip.status_code == 200:
                        _ip = _re_px.search(r'"ip"\s*:\s*"([^"]+)"', _rip.text)
                        _lines.append(f'?? 撠??箏 IP嚗{_ip.group(1) if _ip else _rip.text[:40]}`'
                                      '嚗??箔? NAS ???IP嚗?箸絲憭???IP 隞?”隞???芰???')
                    else:
                        _lines.append('?? ?箏 IP 皜祈岫?∪???銝?摰蔣?踵??嚗????孵祕皜穿?')
                except Exception as _eip:
                    _lines.append(f'?? ?箏 IP 皜祈岫?仿?嚗type(_eip).__name__}')
                # 3) ?啁 Yahoo ?∪??湔葫嚗??抒? Yahoo嚗絲憭?IP ?舐???
                from etf_fetch import _fetch_holdings_yahoo_tw, fetch_etf_holdings
                try:
                    _yh = _fetch_holdings_yahoo_tw('0050.TW')
                    if _yh:
                        _lines.append(f'?? ?啁 Yahoo ?∪?嚗? 0050.TW ?? {len(_yh)} 瑼??∴?銝餅???嚗?)
                    else:
                        _lines.append('?? ?啁 Yahoo ?∪?嚗 0050.TW 閫??銝?'
                                      '嚗??Ｙ?瑽?賣??蝥?銝?游?蝯?嚗?)
                except Exception as _eyh:
                    _lines.append(f'?? ?啁 Yahoo ?∪?嚗葫閰衣撣?{type(_eyh).__name__}')
                # 4) 撖行葫?游??? 0050.TW ???∴?皜翰?Ⅱ靽??雯頝荔?
                try:
                    fetch_etf_holdings.clear()
                except Exception:
                    pass
                _t0 = _tt.time()
                with st.spinner('撖行葫?游??? 0050.TW ???∩葉??):
                    _h = fetch_etf_holdings('0050.TW')
                _dt = _tt.time() - _t0
                if _h:
                    _lines.append(f'??**0050.TW ???⊥?????{len(_h)} 瑼?*嚗_dt:.1f}s嚗?
                                  '??隞????嚗隞??ETF嚗銝餃?撘???雿菜敺?)
                else:
                    _ok = False
                    _lines.append(f'??**0050.TW ???∩?????*嚗_dt:.1f}s嚗?
                                  '??隞???芰???靘??冽?嚗???console `[Holdings/...]` log')
            except Exception as _epx:
                _ok = False
                _lines.append(f'??皜祈岫?啣虜嚗type(_epx).__name__}: {_epx}')
            st.session_state['_diag_proxy_ok']  = _ok
            st.session_state['_diag_proxy_msg'] = '\n\n'.join(_lines)
            st.rerun()
    with _px_c2:
        _pm = st.session_state.get('_diag_proxy_msg')
        if _pm:
            (st.success if st.session_state.get('_diag_proxy_ok') else st.warning)(_pm)

    # ??????????????????????????????????????????????????????????????
    # ?? ?典?鞈??亙熒蝮質”嚗絞銝閬?嚗?
    # ??????????????????????????????????????????????????????????????
    st.markdown('#### ?? ?典?鞈??亙熒蝮質”')
    st.caption('銝閬賣?????皞???啁???嚚??脣?隞?”?圈悅摨佗???圈悅 / ??舀??/ ???嚗? 銝活 Release 靘 FRED API嚗?0 憭?cache嚗?)

    _ma_g  = st.session_state.get('macro_info') or {}
    _cl_g  = st.session_state.get('cl_data')    or {}
    _mi_g  = st.session_state.get('m1b_m2_info') or {}
    _li_g  = st.session_state.get('li_latest')
    _t2_g  = st.session_state.get('t2_data')    or {}
    _e1_g  = st.session_state.get('etf_single_data') or {}
    _cl_ts_g = str(st.session_state.get('cl_ts', ''))[:10] or None

    # v18.225 T2嚗RED 銝活 release ?潘?30 憭?cache ??rerun 銝???API嚗?
    import os as _os_hi
    _fred_key_hi = (_os_hi.environ.get('FRED_API_KEY') or
                    (st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else None) or '')
    try:
        from macro_core import fred_get_next_release_date as _fred_nrd
    except Exception:
        _fred_nrd = None

    @st.cache_data(ttl=CACHE_TTL["daily_snapshot"], show_spinner=False)
    def _next_release_cached(series_id: str, api_key_present: bool) -> str:
        """Streamlit 撅文???撅?1 ??cache嚗??macro_core 30 憭?disk cache 銋?隞?銴???
        api_key_present ?脣 cache key 蝣箔??? secrets ??invalidates??""
        if not series_id or not api_key_present or _fred_nrd is None:
            return ''
        try:
            _d = _fred_nrd(series_id, _fred_key_hi)
            return _d.isoformat() if _d else ''
        except Exception:
            return ''

    _global_rows = []

    def _g_add(name, source, freq, df=None, date_str=None, count=None,
               fred_series_id: str = ''):
        if isinstance(df, _pd_r.DataFrame) and not df.empty:
            _d = _last_date(df)
            _cnt = len(df) if count is None else count
        else:
            _d = date_str
            _cnt = count
        if _d:
            icon, lbl = _light(_d, freq)
            _fresh = f'{icon} {lbl}'
        else:
            _fresh = '? ?芸?敺?
        # v18.225 T2嚗? FRED-backed ???乩?甈?release嚗擗?蝛?"??
        _nr = _next_release_cached(fred_series_id, bool(_fred_key_hi)) if fred_series_id else ''
        _global_rows.append({
            '鞈??迂': name,
            '靘?':     source,
            '?餌?':     _FREQ_LBL.get(freq, freq),
            '??唳??: _d or '??,
            '?圈悅摨?:   _fresh,
            '銝活Release': _nr or '??,
            '蝑':     _cnt if _cnt is not None else '??,
        })

    # 蝮賜?
    _g_add('VIX ???',     'yfinance',       'daily',
           date_str=str((_ma_g.get('vix') or {}).get('date',''))[:10] or _cl_ts_g
                    if (_ma_g.get('vix') or {}).get('current') is not None else None)
    _g_add('蝢??詨? CPI YoY', 'FRED',           'monthly',
           date_str=str((_ma_g.get('us_core_cpi') or {}).get('date',''))[:10] or None,
           fred_series_id='CPILFESL')
    _g_add('?? ?啁鋆賡平 PMI',
           'CIER-EN+data.gov.tw+NDC+MacroMicro+CIER+StockFeel+?漕+FinMind+MoneyDJ 9 畾?, 'monthly',
           date_str=str((_ma_g.get('ism_pmi') or {}).get('date',''))[:10] or None)
    _g_add('NDC ?舀除??',      'StockFeel+MacroMicro ??', 'monthly',
           date_str=str((_ma_g.get('ndc_signal') or {}).get('date',''))[:10] or None)
    _g_add('?啁?箏 YoY',      'stat.gov.tw+FinMind+MOF+FRED+data.gov.tw+?? 6畾萄???, 'monthly',
           date_str=str((_ma_g.get('tw_export') or {}).get('date',''))[:10] or None)
    _g_add('?啁 M1B / M2',    'CBC + FinMind ??',         'monthly',
           date_str=(_cl_ts_g if _mi_g.get('m1b_yoy') is not None else None))

    # v18.226嚗?鞈???交嚗etch_foreign_consecutive_days ??_fi_streak_cache嚗?
    _fi_streak_g = st.session_state.get('_fi_streak_cache') or {}
    _g_add('憭?????交', 'FinMind TaiwanStockTotalInstitutionalInvestors', 'daily',
           date_str=(_fi_streak_g.get('date_latest') or None)
                    if _fi_streak_g.get('consec_days') is not None else None)

    # 憭抒? + 蝐Ⅳ
    for _gk, _glbl, _gsrc in [
        ('intl', '??? OHLCV',    'yfinance'),
        ('tw',   '?啗? OHLCV',    'yfinance'),
        ('tech', '蝘??⊥???OHLCV',  'yfinance'),
    ]:
        _grp = _cl_g.get(_gk) or {}
        _dfs = [df for df in _grp.values() if isinstance(df, _pd_r.DataFrame) and not df.empty] \
               if isinstance(_grp, dict) else []
        _maxd = max((_last_date(d) for d in _dfs), default=None) if _dfs else None
        _cnt  = sum(len(d) for d in _dfs) if _dfs else None
        _g_add(_glbl, _gsrc, 'daily', date_str=_maxd or _cl_ts_g, count=_cnt)

    _inst_df = _cl_g.get('inst')
    # inst ??dict嚗? DataFrame嚗? 敹???key ????鞈?嚗??{} 鋡怨炊???
    _inst_has_data = (isinstance(_inst_df, dict) and len(_inst_df) > 0) or \
                     (isinstance(_inst_df, _pd_r.DataFrame) and not _inst_df.empty)
    _g_add('銝之瘜犖?曇疏鞎瑁都頞?, 'TWSE BFI82U', 'daily',
           df=_inst_df if isinstance(_inst_df, _pd_r.DataFrame) else None,
           date_str=(_cl_ts_g if _inst_has_data and not isinstance(_inst_df, _pd_r.DataFrame) else None))
    _g_add('??擗?',           'FinMind+TWSE+HiStock+Goodinfo+Yahoo+?漕 6畾萄???, 'daily',
           date_str=(_cl_ts_g if _cl_g.get('margin') is not None else None))
    _adl_df = _cl_g.get('adl')
    _g_add('ADL 瞍脰?摰嗆',       'yfinance/TWSE', 'daily',
           df=_adl_df if isinstance(_adl_df, _pd_r.DataFrame) else None,
           date_str=_cl_ts_g if _adl_df is not None and not isinstance(_adl_df, _pd_r.DataFrame) else None)

    # ????
    if isinstance(_li_g, _pd_r.DataFrame) and not _li_g.empty:
        _g_add('????嚗?鞈?鞎?瘜犖/PCR嚗?, 'FinMind/TAIFEX', 'daily', df=_li_g)
    else:
        _g_add('????嚗?鞈?鞎?瘜犖/PCR嚗?, 'FinMind/TAIFEX', 'daily', date_str=None)

    # ?
    if _t2_g.get('df') is not None:
        _g_add(f'? K蝺?{_t2_g.get("sid","-")}', 'FinMind / yfinance', 'daily',
               df=_t2_g.get('df'))
        _g_add(f'?????{_t2_g.get("sid","-")}', 'FinMind', 'monthly',
               df=_t2_g.get('rev'))
        _g_add(f'?摮?瓷??{_t2_g.get("sid","-")}', 'FinMind', 'quarterly',
               df=_t2_g.get('qtr'))

    # ETF
    if _e1_g.get('ticker'):
        _g_add(f'ETF K蝺?{_e1_g.get("ticker")}', 'yfinance', 'daily',
               df=_e1_g.get('price_df'))

    if _global_rows:
        _fresh_cnt = {'?': 0, '?': 0, '?': 0}
        for _r in _global_rows:
            _ic = (_r['?圈悅摨?] or '')[:1]
            if _ic in _fresh_cnt: _fresh_cnt[_ic] += 1
        _total = len(_global_rows)
        _ok_pct = round(_fresh_cnt['?'] / _total * 100) if _total else 0
        _light_color = (TRAFFIC_GREEN if _ok_pct >= 80 else
                        TRAFFIC_YELLOW if _ok_pct >= 50 else TRAFFIC_RED)
        _light_label = ('? 蝬?嚗??摨瘀?' if _ok_pct >= 80 else
                        '? 暺?嚗?撩憭梧?AI 隞?瑁?嚗??折?雿?' if _ok_pct >= 50 else
                        '? 蝝?嚗???頞喉?撱箄降??湔嚗?)
        st.markdown(
            f'<div style="background:#0d1117;border-left:4px solid {_light_color};border-radius:0 6px 6px 0;'
            f'padding:8px 14px;margin-bottom:10px;font-size:13px;">'
            f'<b style="color:{_light_color};">{_light_label}</b>'
            f'<span style="color:#8b949e;margin-left:14px;">'
            f'??{_total} ???? 嚚?? {_fresh_cnt["?"]} 嚚?? {_fresh_cnt["?"]} 嚚?? {_fresh_cnt["?"]} 嚚??亙熒摨?{_ok_pct}%'
            f'</span></div>', unsafe_allow_html=True)

        # ?? [v10.55.1 蝯曹? UI] 銝? multiselect 蝭拚?剁????/ 靘? / ?餌?嚗??
        _opts_status_g = sorted({(r['?圈悅摨?] or '')[:1] for r in _global_rows
                                 if (r['?圈悅摨?] or '')[:1] in ('?', '?', '?')})
        _opts_source_g = sorted({r['靘?'] for r in _global_rows if r.get('靘?')})
        _opts_freq_g   = sorted({r['?餌?'] for r in _global_rows if r.get('?餌?')})
        _flt_g1, _flt_g2, _flt_g3 = st.columns([1, 2, 1])
        with _flt_g1:
            _sel_status_g = st.multiselect(
                '???, _opts_status_g, default=_opts_status_g, key='glb_flt_status'
            )
        with _flt_g2:
            _sel_source_g = st.multiselect(
                '靘?', _opts_source_g, default=_opts_source_g, key='glb_flt_source'
            )
        with _flt_g3:
            _sel_freq_g = st.multiselect(
                '?餌?', _opts_freq_g, default=_opts_freq_g, key='glb_flt_freq'
            )

        _rows_filtered = [
            r for r in _global_rows
            if (r['?圈悅摨?] or '')[:1] in _sel_status_g
            and (r.get('靘?', '') in _sel_source_g or not r.get('靘?'))
            and (r.get('?餌?', '') in _sel_freq_g or not r.get('?餌?'))
        ]

        # ?? ?餌?敺賜?憿嚗??粹?蝡臬?朣???
        _FREQ_COLOR = {
            '?仿':   '#42a5f5',
            '?':   MATERIAL_ORANGE,
            '摮?':   '#ef5350',
            '銝???: '#9e9e9e',
        }
        _th_g = ('font-size:10px;color:#888;font-weight:700;padding:4px 8px;'
                 'border-bottom:1px solid #30363d')
        _td_g = 'font-size:11px;padding:4px 8px'
        # v18.225 T2嚗rid 6?? 甈?蝚?6 甈??甈?Release??FRED-backed ???潘?
        _hdr_g = (
            f"<div style='display:grid;grid-template-columns:2fr 1.6fr 0.7fr 1fr 1.4fr 1fr 0.7fr;"
            f"background:#0d1117;border-radius:6px 6px 0 0'>"
            f"<span style='{_th_g}'>鞈??迂</span>"
            f"<span style='{_th_g}'>靘?</span>"
            f"<span style='{_th_g}'>?餌?</span>"
            f"<span style='{_th_g}'>??唳??/span>"
            f"<span style='{_th_g}'>?圈悅摨?/span>"
            f"<span style='{_th_g}'>銝活 Release</span>"
            f"<span style='{_th_g}'>蝑</span>"
            f"</div>"
        )
        _rows_html_g = _hdr_g
        for _r in _rows_filtered:
            _ic_r = (_r['?圈悅摨?] or '')[:1]
            _row_bg = ('#161b22' if _ic_r == '?' else
                       '#1a1200' if _ic_r == '?' else '#1a0808')
            _fcol_r = (TRAFFIC_GREEN if _ic_r == '?' else
                       TRAFFIC_YELLOW if _ic_r == '?' else TRAFFIC_RED)
            _fq = _r.get('?餌?', '')
            _fc = _FREQ_COLOR.get(_fq, '#9e9e9e')
            _rows_html_g += (
                f"<div style='display:grid;grid-template-columns:2fr 1.6fr 0.7fr 1fr 1.4fr 1fr 0.7fr;"
                f"background:{_row_bg};border-bottom:1px solid #21262d'>"
                f"<span style='{_td_g};color:#e6edf3'>{_r.get('鞈??迂','')}</span>"
                f"<span style='{_td_g};color:#888'>{_r.get('靘?','')}</span>"
                f"<span style='{_td_g}'>"
                f"<span style='background:{_fc}22;color:{_fc};border:1px solid {_fc};"
                f"border-radius:10px;padding:1px 7px;font-size:10px;font-weight:700'>"
                f"{_fq}</span></span>"
                f"<span style='{_td_g};color:#aaa'>{_r.get('??唳??,'??)}</span>"
                f"<span style='{_td_g};color:{_fcol_r};font-weight:600'>{_r.get('?圈悅摨?,'')}</span>"
                f"<span style='{_td_g};color:#aaa'>{_r.get('銝活Release','??)}</span>"
                f"<span style='{_td_g};color:#aaa'>{_r.get('蝑','??)}</span>"
                f"</div>"
            )
        st.markdown(
            f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
            f"{_rows_html_g}</div>",
            unsafe_allow_html=True,
        )
        _shown_g = len(_rows_filtered)
        if _shown_g < _total:
            st.caption(f'撌脩祟?賂?憿舐內 {_shown_g}/{_total}?嚚? {_fresh_cnt["?"]}?? {_fresh_cnt["?"]}?? {_fresh_cnt["?"]}')
    else:
        st.info('撠頛隞颱?鞈??頂蝯望??潔?甈∟??航憚閰Ｚ?????舫?銝?????渡??????)

    # ??????????????????????????????????????????????????????????????
    # ?? 閰喟敦?賣嚗?鞈?憿嚗?
    # ??????????????????????????????????????????????????????????????
    st.markdown('---')
    st.markdown('#### ?? 閰喟敦?賣嚗?鞈?憿嚗?)

    # 蝝舐???expander ?抒? detail rows嚗?銝??儭?鞈??啣虜皜?蔥?伐??+ETF granular missing 銋?嚗?
    _all_section_rows: list = []

    # ???? 1. 蝮賜? Raw ????????????????????????????????????????????
    with st.expander('?? 蝮賜? Raw Data', expanded=False):
        _ma = st.session_state.get('macro_info') or {}
        # 銝??斗嚗?
        # 1. _ma ?湧?蝻???敺??嚗?蝷箇?園? Tab 4 銝?菜?堆?
        # 2. _ma ??_all_failed ????雿憭望?嚗雯頝?proxy ??嚗?
        # 3. _ma ???keys ???蝻箏仃?? ?
        _ma_never = not _ma
        _ma_all_failed = bool(_ma.get('_all_failed'))
        _ma_loaded_at = str(_ma.get('_loaded_at', ''))[:16]
        rows = []
        for label, key, freq, err_key, src, ep, px in [
            ('VIX ???',          'vix',         'daily',   '_err_vix',
             'yfinance',                      '^VIX',                                False),
            ('蝢??詨? CPI YoY',       'us_core_cpi', 'monthly', '_err_cpi',
             'FRED',                          'CPILFESL',                            True),
            ('?? ?啁鋆賡平 PMI',     'ism_pmi',     'monthly', '_err_pmi',
             'data.gov.tw+NDC+MacroMicro+CIER+StockFeel+?漕+FinMind+MoneyDJ 8畾?,
             'data.gov.tw/dataset/6100 / index.ndc / charts/22 / cier / stockfeel / cnyes / FinMind / MoneyDJ', True),
            ('NDC ?舀除???',        'ndc_signal',  'monthly', '_err_ndc',
             'StockFeel+MacroMicro ??',     'stockfeel/biz-light + charts/2',      True),
            ('?啁?箏 YoY',           'tw_export',   'monthly', '_err_export',
             'stat.gov.tw+FinMind+MOF+FRED+data.gov.tw+?? 6畾?, 'XTEXVA01TWM657S',  True),
        ]:
            item = _ma.get(key) or {}
            date = (item.get('date') or item.get('period') or
                    str(item.get('year', ''))[:7] or None)
            if not date:
                if _ma_never:
                    # ?湔瘝? ??暺????內嚗頂蝯望??芸?鋆?嚗?
                    rows.append({**{'鞈??迂': label, '?餌?': _FREQ_LBL.get(freq, freq),
                                    '靘?': src, '蝡舫?': ep, 'Proxy': '?? if px else '??},
                                 '?敺??: '? 敺???蝟餌絞銝活?頛芾岷?芸???嚗?,
                                 '?交?': '??, '???: '?'})
                    continue
                if _ma_all_failed:
                    err = (f'??憭望?嚗_ma_loaded_at}嚗??券 5 畾萄??游??∪???'
                           f'?虜??Streamlit Cloud 瘚瑕? IP 撠????')
                else:
                    # 銝惜 fallback嚗rr_key ??_all_failed ???ey 蝻箏仃雿隞?皞歇??
                    err = (_ma.get(err_key)
                           or f'甇支?皞??喟撩 date/period嚗歇??{_ma_loaded_at}嚗??嗡?蝮賜? keys 甇?虜嚗?
                              f'憭???HTML 蝯??寧???proxy 撠蝡?block')
                rows.append(_row(label, None, freq,
                                 error_msg=err, source=src, endpoint=ep, proxy=px))
            else:
                rows.append(_row(label, str(date)[:10], freq,
                                 source=src, endpoint=ep, proxy=px))
        # M1B / M2嚗?函? date 甈?嚗誑 cl_ts 隞??嚗?
        _mi = st.session_state.get('m1b_m2_info') or {}
        _mi_date = None
        if _mi.get('m1b_yoy') is not None:
            _mi_date = str(st.session_state.get('cl_ts', ''))[:10] or str(_dt_r.date.today())
        if _mi_date:
            rows.append(_row('M1B / M2 鞎典馳靘策', _mi_date, 'monthly',
                             source='CBC + FinMind ??',
                             endpoint='cbc.gov.tw / TaiwanStockMonetaryAggregates',
                             proxy=True))
        else:
            # m1b_m2_info 撠?? ??暺??內嚗?銝 5 ??macro 銝??
            _m1b_never = not _mi
            rows.append({'鞈??迂': 'M1B / M2 鞎典馳靘策',
                         '?餌?': _FREQ_LBL.get('monthly', 'monthly'),
                         '靘?': 'CBC + FinMind ??',
                         '蝡舫?': 'cbc.gov.tw / TaiwanStockMonetaryAggregates',
                         'Proxy': '??,
                         '?敺??: ('? 敺???蝟餌絞銝活?頛芾岷?芸???嚗?
                                      if _m1b_never else '????憭望?'),
                         '?交?': '??,
                         '???: '?' if _m1b_never else '?'})
        _all_section_rows.extend(rows)
        _tbl(rows)
        st.caption('?? M1B-M2 ?拙榆?僑憓??箄?蝞潘?銝＊蝷箸甇扎?
                   ' Proxy=??銵函內蝬?Squid Proxy ?箏嚗??IP ??瘙???)

    # ???? 2. 憭抒? & 蝐Ⅳ Raw ??????????????????????????????????
    with st.expander('?? 憭抒? & 蝐Ⅳ Raw Data', expanded=False):
        _cl = st.session_state.get('cl_data') or {}
        _cl_ts = str(st.session_state.get('cl_ts', ''))[:10] or None
        rows = []
        for gkey, glabel, _ep_g in [
            ('intl',  '??? OHLCV',    'SPY/QQQ/MSCI/^GSPC'),
            ('tw',    '?啗? OHLCV',    '^TWII/^TWOII'),
            ('tech',  '蝘??⊥???OHLCV',  'SOXX/SMH'),
        ]:
            grp = _cl.get(gkey) or {}
            dates = [_last_date(df) for df in grp.values()
                     if isinstance(df, _pd_r.DataFrame)] if isinstance(grp, dict) else []
            dates = [d for d in dates if d]
            rows.append(_row(glabel, max(dates) if dates else _cl_ts, 'daily',
                             source='yfinance', endpoint=_ep_g, proxy=False))

        # 蝢10Y畾?XY蝢?? ??敺?intl group 霈? key
        _intl_grp = _cl.get('intl') or {}
        for _ik, _ilabel, _ep_y in [
            ('10Y?砍畾??, '蝢 10Y 畾??, '^TNX'),
            ('蝢?? DXY',  '蝢?? DXY',    'DX-Y.NYB'),
        ]:
            _idf = _intl_grp.get(_ik)
            rows.append(_row(_ilabel,
                             _last_date(_idf) if isinstance(_idf, _pd_r.DataFrame) else _cl_ts,
                             'daily', source='yfinance', endpoint=_ep_y, proxy=False))

        for key, label, _src, _ep, _px in [
            ('inst',   '銝之瘜犖?曇疏鞎瑁都頞?,
             'TWSE BFI82U',
             'twse.com.tw/rwd/zh/fund/BFI82U', True),
            ('margin', '??擗?',
             'FinMind+TWSE+HiStock+Goodinfo+Yahoo+?漕 6畾萄???,
             'TaiwanStockTotalMarginPurchaseShortSale ??MI_MARGN ??4 憭抒雯??, True),
        ]:
            val = _cl.get(key)
            if isinstance(val, _pd_r.DataFrame):
                date = _last_date(val) or _cl_ts
            elif val is not None:
                date = _cl_ts
            else:
                date = None
            rows.append(_row(label, date, 'daily',
                             source=_src, endpoint=_ep, proxy=_px))

        _adl = _cl.get('adl')
        rows.append(_row(
            'ADL 瞍脰?摰嗆',
            _last_date(_adl) if isinstance(_adl, _pd_r.DataFrame) else _cl_ts,
            'daily',
            source='yfinance + TWSE',
            endpoint='^TWII 隡啁? + MI_INDEX 蝎曄Ⅱ',
            proxy=True))
        _all_section_rows.extend(rows)
        _tbl(rows)
        st.caption('?? ADL 蝝航??潦僑蝺??Ｙ??箄?蝞潘?銝＊蝷箸甇扎?)

    # ???? 3. ???? Raw ????????????????????????????????????????
    with st.expander('?? ???? Raw Data', expanded=False):
        _li = st.session_state.get('li_latest')
        _li_date = _last_date(_li) if isinstance(_li, _pd_r.DataFrame) else None
        _pcr_date = _last_date_col(_li, '?碓CR') if isinstance(_li, _pd_r.DataFrame) else None
        rows = [
            _row('憭??疏??, _li_date, 'daily',
                 source='FinMind', endpoint='TaiwanFuturesInstitutionalInvestors TX+MTX',
                 proxy=False),
            _row('憭??疏瘛典嚗??征?0.25 ??嚗?, _li_date, 'daily',
                 source='TAIFEX', endpoint='OpenData/Future/MarketDataDaily', proxy=True),
            _row('?豢?甈?鈭粹雿?, _li_date, 'daily',
                 source='FinMind', endpoint='TaiwanOptionInstitutionalInvestors TXO',
                 proxy=False),
            _row('銝之瘜犖?曇疏', _li_date, 'daily',
                 source='FinMind', endpoint='TaiwanStockTotalInstitutionalInvestors',
                 proxy=False),
            _row('PCR ?豢?甈?Put/Call 瘥?, _pcr_date or _li_date, 'daily',
                 source='TAIFEX', endpoint='pcRatio.aspx', proxy=True),
        ]
        _all_section_rows.extend(rows)
        _tbl(rows)
        st.caption('?? 憭??疏瘛券??CR ?箄?蝞?甈?嚗??∠蝡????瘝輻?????敺??)

    # ???? 4. ? Raw ????????????????????????????????????????????
    with st.expander('? ? Raw Data', expanded=False):
        _t2 = st.session_state.get('t2_data') or {}
        if not _t2:
            st.info('撠頛???敺?????ab 頛詨隞?Ⅳ銝阡????亙??游???)
        else:
            sid2 = _t2.get('sid', '')
            name2 = _t2.get('name', sid2)
            st.markdown(f'**?嗅??嚗name2}嚗sid2}嚗?*')
            rows = []
            rows.append(_row('K蝺?OHLCV', _last_date(_t2.get('df')), 'daily',
                             source='FinMind / yfinance',
                             endpoint='TaiwanStockPrice / Ticker.history', proxy=False))
            rows.append(_row('????, _last_date(_t2.get('rev')), 'monthly',
                             source='FinMind', endpoint='TaiwanStockMonthRevenue',
                             proxy=False))
            # qtr ???甈?
            _qtr2 = _t2.get('qtr')
            rows.append(_row('摮????, _last_date_col(_qtr2, '?'), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockFinancialStatement',
                             proxy=False))
            rows.append(_row('EPS 瘥??', _last_date_col(_qtr2, 'EPS'), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockFinancialStatement',
                             proxy=False))
            rows.append(_row('瘥??, _last_date_col(_qtr2, '瘥??), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockFinancialStatement',
                             proxy=False))
            # qtr_extra ???甈?嚗宏?日?銴???鞎 TaiwanStockBalanceSheet 銵?
            _qte = _t2.get('qtr_extra')
            rows.append(_row('摮疏', _last_date_col(_qte, '摮疏'), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockBalanceSheet',
                             proxy=False))
            # ??鞎嚗??皜穿?fail/na/zero/ok嚗?銝?蝖祆? ?
            _cl_st, _cl_dt = _probe_col(_qte, '??鞎')
            rows.append(_row('??鞎',
                             _cl_dt if _cl_st == 'ok' else None, 'quarterly',
                             optional=True,
                             probe_status=None if _cl_st == 'ok' else _cl_st,
                             source='FinMind + MOPS ??',
                             endpoint='TaiwanStockBalanceSheet ??ajax_t164sb03',
                             proxy=True))
            rows.append(_row('CapEx 鞈?臬', _last_date_col(_qte, '鞈?臬'), 'quarterly',
                             source='FinMind', endpoint='TaiwanStockCashFlowsStatement',
                             proxy=False))
            # ?∪
            _yr = _t2.get('yearly') or []
            _yr_date = None
            if _yr:
                _yr_raw = str(_yr[-1].get('year', ''))[:4]
                _yr_date = f'{_yr_raw}-12-31' if _yr_raw.isdigit() else None
            rows.append(_row('?∪甇瑕', _yr_date, 'yearly',
                             source='FinMind', endpoint='TaiwanStockDividend',
                             proxy=False))
            # MJ 擃炎鞎∪
            _fh2 = st.session_state.get(f'_fh_{sid2}')
            _fh2_date = (str(_dt_r.date.today())
                         if _fh2 and not _fh2.get('error') else None)
            rows.append(_row('MJ擃炎鞎∪?? BS+CF+IS', _fh2_date, 'quarterly',
                             source='FinMind 3 datasets',
                             endpoint='BalanceSheet+CashFlows+IncomeStatement',
                             proxy=False))
            # ?? MJ 擃炎蝘???閮箸嚗????擃炎銵具/A ? 1:1 撠?嚗??
            #   甇方??芸?蝑府蝘?砍迤???臬???銝＊蝷箄?蝞潭??暹??詨???
            _fin_raw2 = st.session_state.get(f'_fin_raw_{sid2}') or {}
            if _fh2_date and _fin_raw2:
                _b5_2 = _fin_raw2.get('b_item_5y') or {}
                _is_finance = _fin_raw2.get('is_finance', False)

                def _add_field(name, key, mj_indicator, optional=False,
                               source='FinMind', endpoint='', proxy=False,
                               module='', aliases=None, slot='_bs_slot_latest'):
                    """瑼Ｘ?桐?鞎∪??甈????皜穿??? optional=True嚗?
                      ? 撌脫??堆?value > 0嚗?
                      ? 閰脰?祆???0嚗aw slot ??alias 雿?= 0嚗?
                      ??甇方?⊥迨蝘嚗aw slot 摰瘝迨 alias嚗?
                      ? fetch 憭望?嚗fin_raw2 ?湧??航炊??raw slot 蝻綽?
                    aliases: FinMind 閰脫?雿?????list嚗?仿?′蝺函雁霅瑟??穿?
                    slot: '_bs_slot_latest' / '_cf_slot_latest' / '_is_slot_latest'
                    """
                    _meta = {
                        'MJ 璅∠?': module,
                        '鞈??迂': f'{name}',
                        '?拍 MJ ??': mj_indicator,
                        '?餌?': '摮?',
                        '靘?': source,
                        '蝡舫?': endpoint or '??,
                        'Proxy': '?? if proxy else '??,
                        '?交?': '??,
                    }
                    if optional and aliases:
                        # 銝??Ｘ葫嚗?颲具?憭望? / 甇方?⊥迨蝘 / 閰脰?砍迤??0??
                        _st_p, _val_p = _probe_fin_field(_fin_raw2, key, aliases, slot=slot)
                        if _st_p == 'ok':
                            rows.append({**_meta, '?敺??: f'撌脫???{_val_p:,.0f}??',
                                         '???: '?'})
                        elif _st_p == 'na':
                            rows.append({**_meta, '?敺??: '??甇方?⊥迨蝘',
                                         '???: '??})
                        elif _st_p == 'zero':
                            rows.append({**_meta, '?敺??: '? 閰脰?祆???0',
                                         '???: '?'})
                        else:
                            rows.append({**_meta, '?敺??: '? ??憭望?',
                                         '???: '?'})
                        return
                    # ?? 敹?甈? / ?芣?靘?aliases嚗?0 ?唾??箏仃???????????????
                    _v = float(_fin_raw2.get(key) or 0)
                    if _v > 0:
                        rows.append({**_meta, '?敺??: '撌脫???, '???: '?'})
                    elif optional:
                        # 瘝策 aliases ??optional 甈? ?????????蝝?嚗?炊??
                        rows.append({**_meta, '?敺??: '??甇方?祆??∪?,
                                     '???: '??})
                    else:
                        rows.append({**_meta, '?敺??: '??蝻箏仃', '???: '?'})

                _BS_EP = 'TaiwanStockBalanceSheet'
                _CF_EP = 'TaiwanStockCashFlowsStatement'
                _IS_EP = 'TaiwanStockFinancialStatement'

                # ????銝?????瘞?銝嚗???????????????????????
                _M1 = '銝?????瘞?)'
                _add_field('?暸????嗥????', '?暸????嗥????',
                           '?暸????嗥????, module=_M1, endpoint=_BS_EP)
                _add_field('鞈蝮質? / 蝮質??ｇ???', '蝮質?????',
                           '?暸????嗥????+ 蝮質??ａ梯???+ 鞎瘥?',
                           module=_M1, endpoint=_BS_EP)
                _add_field('OCF ?平瘣餃?銋楊?暸?瘚嚗?嚗?, 'OCF(??',
                           '?暸?瘚?瘥?(>100) + ?暸?瘚??瘥?(>100) + ?暸???鞈???>10)',
                           module=_M1, endpoint=_CF_EP)
                _add_field('鞈?臬 ??銝??Ｗ??輯身????', '鞈?臬(??',
                           '?暸?瘚??瘥?嚗?撟游?蝮踝? + ?暸???鞈???,
                           module=_M1, endpoint=_CF_EP)
                _add_field('?潭?暸??∪嚗?嚗?, '?暸??∪(??',
                           '?暸?瘚??瘥?嚗?撟游?蝮踝? + ?暸???鞈???,
                           module=_M1, endpoint=_CF_EP, optional=True,
                           aliases=['CashDividendsPaid', '?潭?暸??∪',
                                    '?暸??∪', '?臭?銋???,
                                    '?祆??臭?銋??],
                           slot='_cf_slot_latest')
                _add_field('?箏?鞈瘥?嚗?嚗?, '?箏?鞈(??',
                           '?暸???鞈?????嚗?,
                           module=_M1, endpoint=_BS_EP)
                _add_field('?瑟???嚗?嚗?, '?瑟???(??',
                           '?暸???鞈?????嚗?,
                           module=_M1, endpoint=_BS_EP, optional=True,
                           aliases=['LongTermInvestments', '?瑟???',
                                    '?⊥???銋?鞈?,
                                    '?∠甈?瘜???'])
                _add_field('?嗡??????ｇ???', '?嗡?????????',
                           '?暸???鞈?????嚗?,
                           module=_M1, endpoint=_BS_EP, optional=True,
                           aliases=['OtherNoncurrentAssets', '?嗡???????,
                                    '?嗡??????Ｗ?閮?])

                # ????鈭?抵??憟賜???????????????????????????
                _M2 = '鈭?抵??憟賜???'
                _add_field('?平?嗅??嚗?嚗?, '?平?嗅(??',
                           '瘥??+ ?平?拍???+ 瘛典??+ ROA + 蝮質??ａ梯???+ DSO + 摰??',
                           module=_M2, endpoint=_IS_EP)
                _add_field('?平瘥嚗?嚗?, '瘥(??',
                           '瘥??= 瘥 / ?平?嗅',
                           module=_M2, endpoint=_IS_EP)
                _add_field('?平?拍?嚗?憭梧?嚗?嚗?, '?平?拍?(??',
                           '?平?拍???= ?平?拍? / ?平?嗅',
                           module=_M2, endpoint=_IS_EP)
                _add_field('?祆?瘛典嚗楊??嚗?敺楊?抬???', '蝔?瘛典(??',
                           '瘛典??+ ROE嚗?摮?',
                           module=_M2, endpoint=_IS_EP)
                _add_field('甈?蝮質?嚗?望?????', '?⊥甈?(??',
                           'ROE = 瘛典 / ?⊥甈?嚗?瘥?',
                           module=_M2, endpoint=_BS_EP)
                _add_field('?箸瘥?? EPS嚗?嚗?, 'EPS',
                           '瘥?? EPS嚗?交???',
                           module=_M2, endpoint=_IS_EP)

                # ????銝????蝧餅???????????????????????????
                _M3 = '銝????蝧餅???'
                _add_field('?撣單狡嚗??鈭?蟡冽?嚗?嚗?, '?撣單狡(??',
                           'DSO ?撣單狡?嗥憭拇 + CCC',
                           module=_M3, endpoint=_BS_EP, optional=True,
                           aliases=['AccountsReceivable', '?撣單狡瘛券?',
                                    '?撣單狡', '?撣單狡?巨??, '?蟡冽??董甈?,
                                    '?撣單狡??蝝???, '?甈暸?', '鞎踵??甈?])
                _add_field('?撣單狡?嗥憭拇嚗SO嚗?蝞潘?', '?撣單狡憭拇',
                           'DSO = ? / ? ? 360嚗???',
                           module=_M3, endpoint=_BS_EP, optional=True)  # 閮??潛 raw alias
                _add_field('摮疏嚗?嚗?, '摮疏(??',
                           'DIO 摮疏?梯?憭拇 + ??瘥?嚗?日?嚗?,
                           module=_M3, endpoint=_BS_EP, optional=_is_finance,
                           aliases=['Inventories', '摮疏', '摮疏瘛券?'])
                _add_field('?平???嚗?嚗?, '?平?(??',
                           'DIO = 摮疏 / ?平? ? 360嚗?瘥?',
                           module=_M3, endpoint=_IS_EP)
                _add_field('??撣單狡嚗?嚗?, '??撣單狡憭拇',
                           'DPO ??撣單狡隞狡憭拇 + CCC',
                           module=_M3, endpoint=_BS_EP)

                # ???????菔???嚗???????????????????????????
                _M4 = '???菔???)'
                _add_field('瘚?鞈??嚗?嚗?, '瘚?鞈(??',
                           '瘚?瘥? + ??瘥?嚗?摮?',
                           module=_M4, endpoint=_BS_EP)
                _add_field('瘚?鞎??嚗?嚗?, '瘚?鞎(??',
                           '瘚?瘥? + ??瘥? + ?暸?瘚?瘥?嚗?瘥?',
                           module=_M4, endpoint=_BS_EP)
                _add_field('??甈暸?嚗?嚗?, '??甈暸?(??',
                           '??瘥?嚗?日?嚗?,
                           module=_M4, endpoint=_BS_EP, optional=True,
                           aliases=['Prepayments', '??甈暸?', '??鞎餌',
                                    '??鞎冽狡', '????甈?, '?嗡???甈暸?'])

                # ????鈭瓷??瑽???璉?嚗???????????????????????
                _M5 = '鈭瓷??瑽???璉?)'
                _add_field('鞎蝮質?嚗?嚗?, '蝮質?????',
                           '鞎雿??Ｘ???= 鞎 / 鞈',
                           module=_M5, endpoint=_BS_EP, optional=_is_finance,
                           aliases=['TotalLiabilities', '鞎蝮質?', '鞎??',
                                    '鞎蝮賡?'])

                # ????5 撟游?蝮踝??瘥? B ????????????????????????
                _b5_ok = _b5_2.get('status') == 'ok'
                rows.append({
                    'MJ 璅∠?':   _M1,
                    '鞈??迂':  '5 撟渡???蜇嚗CF + Capex + 摮疏憓? + ?暸??∪嚗?,
                    '?拍 MJ ??': '?暸?瘚??瘥?嚗? 撟渡?嚗?,
                    '?餌?':     '撟湧',
                    '靘?':     'FinMind',
                    '蝡舫?':     'TaiwanStockCashFlowsStatement (5y)',
                    'Proxy':    '??,
                    '?交?':     '??,
                    '?敺??: '撌脫??? if _b5_ok else f'??蝻箏仃嚗_b5_2.get("label","?芸?敺?)}嚗?,
                    '???:     '?' if _b5_ok else '?',
                })
            _all_section_rows.extend(rows)
            _tbl(rows)
            st.caption(
                '?征 **?祈”??蝑府甈??砍迤?臬???*嚗?憿舐內?詨潭??暹?嚗?
                '?仿?瑼Ｚ”?箇 N/A嚗?撠?祈”蝝?蝘?n\n'
                '?? **MJ 鈭之璅∠?撠**嚗??????瘞?嚗?鈭?抵??憟賜???嚚?
                '銝????蝧餅???嚚????菔???嚗?鈭瓷??瑽???璉?嚗?)

        # ?????????? ?蝯?嚗??寞活??閮箸 ?????????????????
        _t3 = st.session_state.get('t3_data') or {}
        _t3_results = _t3.get('results') or []
        if _t3_results:
            st.markdown('---')
            st.markdown(f'**?? ?蝯???閮箸嚗len(_t3_results)} 瑼?**')
            _grp_diag_rows = []
            _today_grp = str(_dt_r.date.today())
            for _gr in _t3_results:
                _sid = _gr.get('stock_id') or _gr.get('隞?Ⅳ') or '?'
                _nm  = _gr.get('?迂', _sid)
                _err = _gr.get('_fetch_err')
                # K蝺?OHLCV
                _grp_diag_rows.append(_row(
                    f'{_sid} {_nm} K蝺?,
                    _gr.get('_price_date'), 'daily',
                    error_msg=_err or None,
                    source='FinMind / yfinance',
                    endpoint='TaiwanStockPrice / Ticker.history',
                    proxy=False))
                # ??鞎嚗???
                _grp_diag_rows.append(_row(
                    f'{_sid} ??鞎',
                    _today_grp if _gr.get('_cl_ok') else None, 'quarterly',
                    optional=True,
                    probe_status=None if _gr.get('_cl_ok') else 'na',
                    source='FinMind + MOPS ??',
                    endpoint='TaiwanStockBalanceSheet ??ajax_t164sb03',
                    proxy=True))
                # 鞈?臬嚗???
                _grp_diag_rows.append(_row(
                    f'{_sid} 鞈?臬 / ?箏?鞈',
                    _today_grp if _gr.get('_cx_ok') else None, 'quarterly',
                    optional=True,
                    probe_status=None if _gr.get('_cx_ok') else 'na',
                    source='FinMind',
                    endpoint='TaiwanStockCashFlowsStatement',
                    proxy=False))
                # ?∪嚗???
                _grp_diag_rows.append(_row(
                    f'{_sid} ?∪甇瑕',
                    _today_grp if _gr.get('_has_div') else None, 'yearly',
                    optional=True,
                    probe_status=None if _gr.get('_has_div') else 'zero',
                    source='FinMind',
                    endpoint='TaiwanStockDividend',
                    proxy=False))
            _all_section_rows.extend(_grp_diag_rows)
            _tbl(_grp_diag_rows)
            st.caption(
                '? ?寞活??瘨菔? K蝺???鞎+鞈?臬+?∪ 4 憭抒雁摨佗?銝 MJ 鈭之璅∠? N/A 撠嚗?
                '?仿??格?瘛勗漲閮箸隢?????ab 頛摰????)

    # ???? 5. ETF Raw ??????????????????????????????????????????????
    with st.expander('? ETF Raw Data', expanded=False):
        _e1 = st.session_state.get('etf_single_data') or {}
        if not _e1.get('ticker'):
            st.info('撠頛 ETF??敺???ETF?ab 頛詨隞??銝西那?瑯?)
        else:
            tk = _e1.get('ticker', '')
            nm = _e1.get('name', tk)
            st.markdown(f'**?嗅? ETF嚗nm}嚗tk}嚗?*')
            rows = []
            _pdf = _e1.get('price_df')
            rows.append(_row(f'ETF K蝺?OHLCV {tk}', _last_date(_pdf), 'daily',
                             source='yfinance', endpoint=f'Ticker({tk}).history(auto_adjust=True)',
                             proxy=False))
            # AUM / Beta / 鞎餌?????銵??芣炎??
            _is_oversea_etf = bool(_e1.get('_is_overseas'))
            _is_private_etf = bool(_e1.get('_likely_private'))
            _is_active_etf_main = bool(_e1.get('_is_active_etf'))
            _oversea_msg = '瘚瑕? ETF 銝?剁??祉頂蝯?5 皞????ETF嚗?
            _private_msg = '蝘?/?寞? ETF ??AUM?祥?函??AV 銝餅?鞈?皞??芣??
            _active_msg  = '銝餃?撘?ETF ???祇?鞈???嚗?靽∪?蝬脫??剝雿撘?銝?湛??祉頂蝯望?⊥?蝛拙???嚗?
            # v1.1嚗蜓?? ETF 憭望?雿萄 na嚗???嚗????亦???
            _restricted = _is_private_etf or _is_active_etf_main
            _aum_na = _restricted and not _e1.get('aum')
            rows.append(_row('ETF 閬芋 AUM',
                             str(_dt_r.date.today()) if _e1.get('aum') else None, 'daily',
                             error_msg=((_active_msg if _is_active_etf_main else _private_msg)
                                        if _aum_na else None),
                             probe_status=('na' if _aum_na else None),
                             source='yfinance', endpoint='.info[totalAssets]', proxy=False))
            rows.append(_row('ETF Beta',
                             str(_dt_r.date.today()) if _e1.get('beta') is not None else None,
                             'daily',
                             source='yfinance', endpoint='.info[beta]', proxy=False))
            _exp_na = (_is_oversea_etf or _restricted) and not _e1.get('expense')
            rows.append(_row('ETF 鞎餌??,
                             str(_dt_r.date.today()) if _e1.get('expense') else None, 'daily',
                             optional=False,
                             error_msg=(_oversea_msg if _is_oversea_etf
                                        else _active_msg if _is_active_etf_main
                                        else _private_msg if _is_private_etf
                                        else _e1.get('_err_expense')),
                             probe_status=('na' if _exp_na else None),
                             source='SITCA + MoneyDJ + Yuanta + yfinance 4 皞?,
                             endpoint='sitca.org.tw / moneydj Basic0004 / yuantaetfs / .info',
                             proxy=True))
            # NAV 瘛典?
            _prem = _e1.get('premium') or {}
            _nav_ok = _prem.get('nav') is not None
            _nav_na = (_is_oversea_etf or _restricted) and not _nav_ok
            rows.append(_row('NAV 瘛典?,
                             str(_dt_r.date.today()) if _nav_ok else None, 'daily',
                             error_msg=(_oversea_msg if _is_oversea_etf
                                        else _active_msg if _is_active_etf_main
                                        else _private_msg if _is_private_etf
                                        else _e1.get('_err_nav')),
                             probe_status=('na' if _nav_na else None),
                             source='FinMind / TWSE OpenAPI',
                             endpoint='TaiwanETFNetAssetValue / opendata',
                             proxy=True))
            # ?粹?蝬?鈭綽?ETF 銵函???犖?賊?嚗?????嚗?
            try:
                from etf_fetch import fetch_etf_manager as _fem_r
                _mgr_r = _fem_r(tk)
            except Exception:
                _mgr_r = None
            _mgr_name = (_mgr_r or {}).get('name')
            rows.append(_row('?粹?蝬?鈭?,
                             str(_dt_r.date.today()) if _mgr_name else None, 'static',
                             optional=True,
                             error_msg=(None if _mgr_name
                                        else st.session_state.get(
                                            '_etf_manager_last_err', {}).get(
                                            tk.replace('.tw', '.TW'))),
                             source='MoneyDJ / SITCA / Yuanta',
                             endpoint='Basic0004/0001/0006/0011 ??SITCA ??摰雯',
                             proxy=True))
            _all_section_rows.extend(rows)
            _tbl(rows)
            st.caption('?? 畾?蕭頩方炊撌柴AGR?harpe??皞Ｗ?閮??潘?銝＊蝷箸甇扎?)

        # ?????????? ETF 蝯?嚗??閮箸 ??????????????????????
        _ep = st.session_state.get('etf_portfolio_data') or {}
        _ep_rows = _ep.get('rows') or []
        if _ep_rows:
            st.markdown('---')
            st.markdown(f'**??儭?ETF 蝯???閮箸嚗len(_ep_rows)} 瑼?**')
            _today_ep = str(_dt_r.date.today())
            _port_diag_rows = []
            for _pr in _ep_rows:
                _tk_p = _pr.get('ticker', '')
                if not _tk_p:
                    continue
                _cp  = _pr.get('current_price') or 0
                _shr = _pr.get('shares') or 0
                _dvr = _pr.get('dividend_received') or 0
                _is_tw = _tk_p.endswith('.TW') or _tk_p.endswith('.TWO')
                # ?曉嚗蝺?
                _port_diag_rows.append(_row(
                    f'{_tk_p} ?曉 / K蝺?,
                    _today_ep if _cp > 0 else None, 'daily',
                    error_msg=None if _cp > 0 else 'yfinance ???唳?文嚗誨?隤斗?銝?嚗?,
                    source='yfinance',
                    endpoint=f'Ticker({_tk_p}).history(5d)',
                    proxy=False))
                # ?
                _div_st = None
                _div_err = None
                if _dvr > 0:
                    _div_st = None  # green
                elif _is_tw and _shr > 0:
                    _div_st = 'zero'  # ?啗 ETF 雿? 1 撟渡?嚗??瑕? / ?唬?撣?/ yfinance 蝻綽?
                else:
                    _div_st = 'na'  # 瘚瑕???⊥
                    _div_err = '瘚瑕? ETF 銝?冽蝟餌絞?閮?' if not _is_tw else None
                _port_diag_rows.append(_row(
                    f'{_tk_p} ?嚗?1撟湛?',
                    _today_ep if _dvr > 0 else None, 'yearly',
                    optional=True,
                    probe_status=_div_st,
                    error_msg=_div_err,
                    source='yfinance',
                    endpoint=f'Ticker({_tk_p}).dividends',
                    proxy=False))
            _all_section_rows.extend(_port_diag_rows)
            _tbl(_port_diag_rows)
            st.caption('? ????閰脰?祆???0??賜???ETF嚗??嚗??唬?撣皛?1 撟湛?? 銝?具瘚瑕? ETF??)

            # ?????? 銝餃? ETF 蝬?鈭?/ ??Ｘ葫 ??????
            try:
                from etf_fetch import is_active_etf, fetch_etf_manager, fetch_etf_holdings
            except ImportError:
                is_active_etf = fetch_etf_manager = fetch_etf_holdings = None

            if is_active_etf is not None and fetch_etf_manager is not None:
                st.markdown('---')
                _h1, _h2, _h3 = st.columns([4, 1, 1])
                _h1.markdown('**?? 銝餃? ETF 蝬?鈭?/ ? MoneyDJ ?Ｘ葫**')
                if _h2.button('??儭?皜翰??閰?, key='_etf_mgr_clear',
                               use_container_width=True,
                               help='皜? fetch_etf_manager + fetch_etf_holdings ??None 敹怠?嚗??啗粥 proxy ??):
                    try:
                        fetch_etf_manager.clear()
                    except Exception:
                        pass
                    try:
                        fetch_etf_holdings.clear()
                    except Exception:
                        pass
                    st.rerun()
                _do_deep = _h3.button('? 瘛勗漲閮箸', key='_etf_mgr_deep',
                                       use_container_width=True,
                                       help='??瑼蜓?? ETF嚗?交? MoneyDJ 銝粥敹怠?嚗?憿舐內 HTTP status / regex match')
                st.caption('閮箸?摹?Ｗ漲瑼Ｘ葫?”?潦??犖?遙?蝛箇??孵?嚗?
                           'MoneyDJ ??絲憭?IP嚗?韏?proxy_helper嚗AS Squid ?啁 IP嚗?
                           '?交?摰? ??雿?proxy ????????????瘛勗漲閮箸?? MoneyDJ ?臬??NAS IP / regex 瞍???)

                # ?????? ? 瘛勗漲閮箸嚗?韏啣翰??raw probe ??????
                if _do_deep:
                    _active_tks = [_pr.get('ticker', '') for _pr in _ep_rows
                                   if is_active_etf(_pr.get('ticker', ''))]
                    if not _active_tks:
                        st.warning('蝯??抒銝餃?撘?ETF嚗◤??銝??亦??犖嚗?)
                    else:
                        _tk_probe = _active_tks[0]
                        _url_probe = (
                            'https://www.moneydj.com/ETF/X/Basic/Basic0001.xdjhtm'
                            f'?etfid={_tk_probe}')
                        st.markdown(f'**? ?Ｘ葫撠情嚗{_tk_probe}`** ??`{_url_probe}`')
                        # 皞?1嚗roxy_helper.fetch_url
                        try:
                            from proxy_helper import fetch_url as _fu_d
                            _r_p = _fu_d(_url_probe, timeout=12, attempts=2)
                            if _r_p is None:
                                st.error('??**proxy_helper.fetch_url** ??None嚗roxy ?典仃?? 403?2 敺?蝝?憭望?嚗?)
                            else:
                                _len_p = len(_r_p.text) if _r_p.text else 0
                                _msg = f'**proxy_helper.fetch_url** ??HTTP `{_r_p.status_code}` 繚 ?瑕漲 `{_len_p}` chars'
                                if _r_p.status_code == 200 and _len_p > 1000:
                                    st.success(f'??{_msg}')
                                    _r_p.encoding = 'utf-8'
                                    import re as _re_d
                                    _txt = _r_p.text
                                    _nm_m = _re_d.search(r'蝬?鈭暨^<>\d]{0,30}?>?\s*([銝-橦瓢{2,8})\s*<', _txt)
                                    _dt_m = _re_d.search(
                                        r'(?:?啗?四銝遙?四隞餅?|蝞∠??粹???[^\d]{0,30}?(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})',
                                        _txt)
                                    if _nm_m:
                                        st.success(f'??regex 蝬?鈭綽?`{_nm_m.group(1)}`')
                                    else:
                                        st.warning('?? regex 瘝??啜??犖??雿???MoneyDJ HTML 蝯??航?寧?')
                                    if _dt_m:
                                        st.success(f'??regex ?啗?伐?`{_dt_m.group(1)}-{_dt_m.group(2)}-{_dt_m.group(3)}`')
                                    else:
                                        st.info('?對? regex 瘝??啜?瑟 / 銝遙?乓??芣?蝬?鈭箸?隞餅?銋??典???嚗?)
                                    # ?汗?怒??犖???潮?餈?200 摮?
                                    _pos = _txt.find('蝬?鈭?)
                                    if _pos >= 0:
                                        st.code(_txt[max(0, _pos - 50):_pos + 250], language='html')
                                    else:
                                        st.warning('?? ?渡???????犖??摮瘝? ???航?舫隤日???/ ?撟脫??)
                                else:
                                    st.error(f'??{_msg} ??MoneyDJ ?? NAS IP ??鈭征??)
                        except Exception as _ep_d:
                            st.error(f'??proxy_helper 靘?嚗type(_ep_d).__name__}: {_ep_d}')
                        # 皞?2嚗url_cffi ?湧?
                        try:
                            from curl_cffi import requests as _cffi_d
                            _r_c = _cffi_d.get(_url_probe, impersonate='chrome124', timeout=12)
                            _len_c = len(_r_c.text) if _r_c.text else 0
                            _msg = f'**curl_cffi ?湧?* ??HTTP `{_r_c.status_code}` 繚 ?瑕漲 `{_len_c}` chars'
                            if _r_c.status_code == 200 and _len_c > 1000:
                                st.success(f'??{_msg}嚗allback ?舐嚗?)
                            else:
                                st.warning(f'?? {_msg}嚗allback 銋仃???? ??瘚瑕? IP 鋡急?嚗?)
                        except Exception as _ec_d:
                            st.warning(f'?? curl_cffi 靘?嚗type(_ec_d).__name__}: {_ec_d}')

                _probe_rows = []
                _tk_seen: set[str] = set()
                for _pr in _ep_rows:
                    _tk_p = _pr.get('ticker', '')
                    if not _tk_p or _tk_p in _tk_seen:
                        continue
                    _tk_seen.add(_tk_p)
                    _active = is_active_etf(_tk_p)
                    # 蝬?鈭箸皜?
                    if not _active:
                        _probe_rows.append(_row(
                            f'{_tk_p} 蝬?鈭?, None, 'static',
                            optional=True, probe_status='na',
                            source='MoneyDJ', endpoint='Basic0001.xdjhtm',
                            proxy=True))
                    else:
                        try:
                            _mgr = fetch_etf_manager(_tk_p)
                        except Exception as _emgr:
                            _mgr = None
                            print(f'[diag/manager] {_tk_p}: {type(_emgr).__name__}: {_emgr}')
                        if _mgr and _mgr.get('name'):
                            _nm_mgr = _mgr['name']
                            _tn = _mgr.get('tenure_days')
                            _label = f'{_nm_mgr}' + (f'嚗遙??{_tn} 憭抬?' if _tn else '嚗遙??嚗?)
                            _probe_rows.append(_row(
                                f'{_tk_p} 蝬?鈭?= {_label}',
                                _mgr.get('since') or _today_ep, 'static',
                                source='MoneyDJ', endpoint='Basic0001.xdjhtm',
                                proxy=True))
                        else:
                            _last_err = (st.session_state.get('_etf_manager_last_err') or {}).get(_tk_p)
                            # v1.1嚗蜓?? ETF Yuanta 銋仃????暺? na嚗??????
                            _err_str = (
                                '銝餃?撘?ETF ???祇?鞈???'
                                f'嚗race: {_last_err}嚗? if _last_err
                                else '銝餃?撘?ETF ???祇?鞈???'
                            )
                            _probe_rows.append(_row(
                                f'{_tk_p} 蝬?鈭?,
                                None, 'static',
                                probe_status='na',
                                error_msg=_err_str,
                                source='MoneyDJ + SITCA + Yuanta',
                                endpoint='Basic0001/0006/0011 + SITCA IN24XX + yuantaetfs',
                                proxy=True))
                    # ??Ｘ葫嚗陛????/ ?∴?
                    try:
                        _hd = fetch_etf_holdings(_tk_p) if fetch_etf_holdings else None
                    except Exception as _ehd:
                        _hd = None
                        print(f'[diag/holdings] {_tk_p}: {type(_ehd).__name__}: {_ehd}')
                    if _hd:
                        _probe_rows.append(_row(
                            f'{_tk_p} ? = {len(_hd)} 瑼?,
                            _today_ep, 'monthly',
                            source='yfinance/MoneyDJ',
                            endpoint='funds_data ??Basic0007/0008/RankA0001',
                            proxy=True))
                    else:
                        _probe_rows.append(_row(
                            f'{_tk_p} ?',
                            None, 'monthly', optional=True,
                            error_msg='銝?? URL ?典仃??403 / 蝡舫?霈?嚗?,
                            source='yfinance/MoneyDJ',
                            endpoint='funds_data ??Basic0007/0008/RankA0001',
                            proxy=True))
                _all_section_rows.extend(_probe_rows)
                _tbl(_probe_rows)
                st.caption('? 蝬?鈭箝 銝?具? 鋡怠?撘?ETF ?⊿??伐??? ??憭望??? 銝餃?撘? proxy/regex ?啣虜??)

    # ??????????????????????????????????????????????????????????????
    # ?? 鞈??啣虜皜嚗?銝銝閬踝??函??潔??寧蜇銵??賣嚗?
    # ??????????????????????????????????????????????????????????????
    st.markdown('---')
    st.markdown('#### ?? 鞈??啣虜皜')
    # ?蔥?????rows???? ??expander ??detail rows???+ETF granular missing)
    # detail rows schema ?具??????典??具??唳???圈悅摨艾?蝯曹? normalize
    def _norm_anom(_r):
        _ic = (_r.get('?圈悅摨?) or _r.get('???) or '')[:1]
        return {
            '鞈??迂': _r.get('鞈??迂', '??),
            '靘?':     _r.get('靘?', '??) or '??,
            '?餌?':     _r.get('?餌?', '??),
            '??唳??: _r.get('??唳??) or _r.get('?交?', '??) or '??,
            '?圈悅摨?:   _r.get('?圈悅摨?) or _r.get('?敺??) or _ic,
            '_icon':    _ic,
        }
    _anom_combined = (
        [_norm_anom(r) for r in _global_rows]
        + [_norm_anom(r) for r in _all_section_rows]
    )
    # 靘???蝔勗??靽?蝚砌?蝑?
    _seen_anom: set = set()
    _anom_dedup = []
    for _r in _anom_combined:
        _k = _r.get('鞈??迂', '')
        if _k and _k not in _seen_anom:
            _seen_anom.add(_k)
            _anom_dedup.append(_r)
    _anom_rows = [r for r in _anom_dedup if r['_icon'] in ('?', '?')]
    # ??嚗???典?嚗???典?嚗??找?鞈??迂摮?摨?
    _anom_rows.sort(key=lambda r: (
        0 if r['_icon'] == '?' else 1,
        r.get('鞈??迂', ''),
    ))
    if not _anom_rows:
        st.success('???冽鞈?皞??迤撣賂?? ? ??堆?')
    else:
        _a_red = sum(1 for r in _anom_rows if r['_icon'] == '?')
        _a_yel = sum(1 for r in _anom_rows if r['_icon'] == '?')
        st.caption(
            f'??{len(_anom_rows)} 蝑撣詻嚚? ?????? {_a_red}?? ??撱園 {_a_yel}'
            f'?嚚靘?漲??嚗?+ETF detail rows嚗?
        )
        _FREQ_COLOR_A = {'?仿': '#42a5f5', '?': MATERIAL_ORANGE,
                        '摮?': '#ef5350', '銝???: '#9e9e9e'}
        _td_aa = ('padding:6px 10px;border-bottom:1px solid #21262d;'
                  'font-size:12px')
        _hd_aa = (
            f"<div style='display:grid;grid-template-columns:2.4fr 1.4fr 0.8fr 1.2fr 1.6fr;"
            f"background:#0d1117'>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>鞈??迂</div>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>靘?</div>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>?餌?</div>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>??唳??/div>"
            f"<div style='{_td_aa};color:#888;font-weight:700;font-size:10px'>???/div>"
            f"</div>"
        )
        _rows_aa = _hd_aa
        for _ar in _anom_rows:
            _aic = _ar['_icon']
            _abg2 = '#1a0808' if _aic == '?' else '#1a1200'
            _acol2 = '#ef5350' if _aic == '?' else '#ffb74d'
            _afq = _ar.get('?餌?', '') or '??
            _afq_color = _FREQ_COLOR_A.get(_afq, '#555')
            _rows_aa += (
                f"<div style='display:grid;grid-template-columns:2.4fr 1.4fr 0.8fr 1.2fr 1.6fr;"
                f"background:{_abg2}'>"
                f"<div style='{_td_aa};color:#e6edf3'>{_ar.get('鞈??迂','??)}</div>"
                f"<div style='{_td_aa};color:#888'>{_ar.get('靘?','??) or '??}</div>"
                f"<div style='{_td_aa}'>"
                f"<span style='background:{_afq_color}22;color:{_afq_color};"
                f"border:1px solid {_afq_color};border-radius:10px;padding:1px 7px;"
                f"font-size:10px;font-weight:700'>{_afq}</span></div>"
                f"<div style='{_td_aa};color:#aaa'>{_ar.get('??唳??,'??) or '??}</div>"
                f"<div style='{_td_aa};color:{_acol2};font-weight:600'>"
                f"{_ar.get('?圈悅摨?,'??)}</div>"
                f"</div>"
            )
        st.markdown(
            f"<div style='border:1px solid #30363d;border-radius:6px;overflow:hidden'>"
            f"{_rows_aa}</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            '? **??隤?**嚗???仃??API/proxy/蝬脰楝??嚗?? ??撱園??鋆?嚗??臬???嚗?
            '??甇方?⊥迨蝘???閰脰?祆???0 ???抵?*?撣?*嚗歇敺皜?嚗??喳? Tab 閰單嚗?
        )

