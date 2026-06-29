"""src/services/data_registry_scanner.py — DataRegistry 掃描寫入(P1-X v18.393 抽出)。

從 tab_macro inline 抽出(原 line 373-647,~275 LOC):
- 2 個 inner helper(_reg_add / _reg_missing)→ module-level helper
- 8 個讀資料 phase:
  1. 大盤/總經(INTL/TW/TECH MAP) — 固定清單,每筆 add 或 missing
  2. ADL 市場廣度 + 上漲/下跌家數 + AD累計值(4 細項)
  3. 三大法人 + 融資餘額(籌碼面)
  4. 旌旗指數 + TWII 乖離率(20/240)
  5. M1B/M2 + M1B-M2 資金缺口(月)
  6. 6 個宏觀指標(VIX/CPI/Fed/PMI/出口/NDC)
  7. 先行指標 5 個分組(三大法人現貨/外資期貨/PCR/成交量/未平倉)
  8. 個股 5 細項 + 比較排行 + ETF 3 細項

§8.2 L3 service:純 compute + 1 個 session_state write。
caller(tab_macro)注入 INTL/TW/TECH MAP 對齊 macro_registry_patch /
macro_fetch_orchestrator DI 風格,亦避測試環境 streamlit cache 牽連。
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

# v18.394 SSOT 修法:category 對齊 static DATA_REGISTRY 的 11 個 emoji label。
from shared.data_categories import (
    CAT_CHIPS, CAT_ETF, CAT_INTL, CAT_STOCK,
    CAT_TW_MACRO, CAT_TW_MARKET, CAT_US_MACRO,
)


def _reg_add(_reg_new: dict, _rname: str, _rdf: Any,
             category: str = CAT_TW_MARKET, frequency: str = 'daily') -> None:
    """提取最新時間戳後寫入 registry(不儲存 df 本體,僅保留元資料)。"""
    if not isinstance(_rdf, pd.DataFrame) or _rdf.empty:
        return
    _d = _rdf
    if isinstance(_d.index, pd.DatetimeIndex):
        _latest = _d.index.max()
    else:
        _dcol = None
        _date_fmt = None
        for _c in _d.columns:
            _cl = str(_c).lower()
            if _cl == '_date':
                _dcol = _c
                _date_fmt = '%Y%m%d'
                break
            if _cl in ('date', 'datetime', 'timestamp', '日期', 'quarter', 'period'):
                _dcol = _c
                break
        if _dcol:
            try:
                _s = _d[_dcol]
                if _date_fmt:
                    _s = pd.to_datetime(_s, format=_date_fmt, errors='coerce')
                else:
                    _s = pd.to_datetime(_s, errors='coerce')
                _latest = _s.max()
            except Exception:
                _latest = None
        else:
            _latest = None
    try:
        _ls = (pd.Timestamp(_latest).strftime('%Y-%m-%d')
               if _latest is not None and not pd.isna(_latest) else 'N/A')
    except Exception:
        _ls = 'N/A'
    _reg_new[_rname] = {
        'last_updated': _ls, 'rows': len(_d),
        'category': category, 'frequency': frequency,
    }


def _reg_missing(_reg_new: dict, _rname: str,
                 category: str = CAT_TW_MARKET, frequency: str = 'daily') -> None:
    _reg_new[_rname] = {
        'last_updated': 'N/A', 'rows': 0,
        'category': category, 'frequency': frequency, 'missing': True,
    }


def scan_and_write_data_registry(*, intl_map: dict, tw_map: dict, tech_map: dict) -> None:
    """掃所有已載入 DF + session_state,寫 `st.session_state['data_registry']`。

    args:
        intl_map / tw_map / tech_map: 國際 / 台股 / 科技指數 → ticker 對應表
                                       (caller 注入,L3 service DI 風格)

    讀(session_state):
        cl_data / m1b_m2_info / bias_info / jingqi_info / macro_info /
        li_latest / cl_ts / t2_data / t3_data /
        etf_single_data / etf_portfolio_data / etf_backtest_data

    寫(session_state):
        data_registry: dict[name → {last_updated, rows, category, frequency, [missing]}]

    異常處理:整段 wrap try/except,失敗只 log,不 raise(對齊原 tab_macro 行為)。
    """
    try:
        _reg_new: dict = {}

        # ── 大盤/總經:國際、台股、科技指數(日更新,固定清單確保永遠顯示)──
        # v18.394 SSOT:INTL → 🌐 國際金融 / TW_MAP → 🇹🇼 台股大盤 /
        #              TECH_MAP → 🌐 國際金融(對齊 static DATA_REGISTRY)
        # C1-F v18.292:整個 registry 區塊 10 處 session_state.get 收斂成 1 處 SectionInputs
        from src.services import load_section_inputs as _load_si_reg
        _reg_inp = _load_si_reg(st.session_state)
        _cl_reg = _reg_inp.cl_data or {}
        _intl_d = _cl_reg.get('intl') or {}
        for _rn in intl_map:
            _rdf = _intl_d.get(_rn)
            if isinstance(_rdf, pd.DataFrame) and not _rdf.empty:
                _reg_add(_reg_new, _rn, _rdf, category=CAT_INTL, frequency='daily')
            else:
                _reg_missing(_reg_new, _rn, category=CAT_INTL, frequency='daily')
        _tw_d = _cl_reg.get('tw') or {}
        for _rn in tw_map:
            _rdf = _tw_d.get(_rn)
            if isinstance(_rdf, pd.DataFrame) and not _rdf.empty:
                _reg_add(_reg_new, _rn, _rdf, category=CAT_TW_MARKET, frequency='daily')
            else:
                _reg_missing(_reg_new, _rn, category=CAT_TW_MARKET, frequency='daily')
        _tech_d = _cl_reg.get('tech') or {}
        for _rn in tech_map:
            _rdf = _tech_d.get(_rn)
            if isinstance(_rdf, pd.DataFrame) and not _rdf.empty:
                _reg_add(_reg_new, _rn, _rdf, category=CAT_INTL, frequency='daily')
            else:
                _reg_missing(_reg_new, _rn, category=CAT_INTL, frequency='daily')

        # ── ADL 市場廣度 + 拆 3 細項 → 🇹🇼 台股大盤 ──────────
        _adl_reg = _cl_reg.get('adl')
        if isinstance(_adl_reg, pd.DataFrame) and not _adl_reg.empty:
            _reg_add(_reg_new, 'ADL 市場廣度', _adl_reg, category=CAT_TW_MARKET, frequency='daily')
            _adl_date_col = '_date' if '_date' in _adl_reg.columns else (
                'date' if 'date' in _adl_reg.columns else None)
            for _acname, _acol in [('上漲股票家數', 'up'), ('下跌股票家數', 'down'),
                                   ('ADL 累計廣度值', 'adl')]:
                if _acol in _adl_reg.columns:
                    _acsub = _adl_reg[[c for c in [_adl_date_col, _acol] if c]].copy()
                    _reg_add(_reg_new, _acname, _acsub, category=CAT_TW_MARKET, frequency='daily')
                else:
                    _reg_missing(_reg_new, _acname, category=CAT_TW_MARKET, frequency='daily')
        else:
            _reg_missing(_reg_new, 'ADL 市場廣度', category=CAT_TW_MARKET, frequency='daily')
            for _acname0 in ('上漲股票家數', '下跌股票家數', 'ADL 累計廣度值'):
                _reg_missing(_reg_new, _acname0, category=CAT_TW_MARKET, frequency='daily')

        # ── 三大法人 + 融資餘額 → 💰 籌碼 ──────────────────
        _cl_inst_reg = _cl_reg.get('inst') or (_reg_inp.last_inst or {})
        _inst_date_reg = (_cl_reg.get('inst_date') or _reg_inp.last_inst_date)
        try:
            _inst_ds = str(_inst_date_reg)[:10] if _inst_date_reg else 'N/A'
        except Exception:
            _inst_ds = 'N/A'
        for _ik, _iname in [('外資及陸資', '三大法人 外資買賣超'),
                            ('投信',       '三大法人 投信買賣超'),
                            ('自營商',     '三大法人 自營商買賣超')]:
            if _cl_inst_reg.get(_ik) is not None:
                _reg_new[_iname] = {'last_updated': _inst_ds, 'rows': 1,
                                    'category': CAT_CHIPS, 'frequency': 'daily'}
            else:
                _reg_missing(_reg_new, _iname, category=CAT_CHIPS, frequency='daily')
        _margin_reg2 = _cl_reg.get('margin') or _reg_inp.last_margin
        if _margin_reg2:
            _reg_new['融資餘額（台股）'] = {'last_updated': _inst_ds, 'rows': 1,
                                       'category': CAT_CHIPS, 'frequency': 'daily'}
        else:
            _reg_missing(_reg_new, '融資餘額（台股）', category=CAT_CHIPS, frequency='daily')

        # ── 旌旗指數 + 乖離率 → 🇹🇼 台股大盤 ──────────────
        _cl_ts_proxy = _reg_inp.cl_ts
        try:
            import re as _re_ts_reg
            _m_ts = _re_ts_reg.search(r'(\d{4}-\d{2}-\d{2})', _cl_ts_proxy)
            _proxy_date = _m_ts.group(1) if _m_ts else 'N/A'
        except Exception:
            _proxy_date = 'N/A'
        _jq_reg3 = _reg_inp.jingqi_info or {}
        if _jq_reg3.get('avg') is not None:
            _reg_new['旌旗指數（上漲佔比）'] = {'last_updated': _proxy_date, 'rows': 1,
                                          'category': CAT_TW_MARKET, 'frequency': 'daily'}
        else:
            _reg_missing(_reg_new, '旌旗指數（上漲佔比）', category=CAT_TW_MARKET, frequency='daily')
        _bias_reg3 = _reg_inp.bias_info or {}
        for _bk, _bn in [('bias_240', 'TWII 年線乖離率'), ('bias_20', 'TWII 月線乖離率')]:
            if _bias_reg3.get(_bk) is not None:
                _reg_new[_bn] = {'last_updated': _proxy_date, 'rows': 1,
                                 'category': CAT_TW_MARKET, 'frequency': 'daily'}
            else:
                _reg_missing(_reg_new, _bn, category=CAT_TW_MARKET, frequency='daily')

        # ── M1B / M2 貨幣資金 → 🇹🇼 台灣總經 ─────────────
        _m1b_reg3 = _reg_inp.m1b_m2_info or {}
        for _mk, _mn in [('m1b_yoy', 'M1B 資金活水年增率'), ('m2_yoy', 'M2 廣義貨幣年增率')]:
            if _m1b_reg3.get(_mk) is not None:
                _reg_new[_mn] = {'last_updated': _proxy_date, 'rows': 1,
                                 'category': CAT_TW_MACRO, 'frequency': 'monthly'}
            else:
                _reg_missing(_reg_new, _mn, category=CAT_TW_MACRO, frequency='monthly')
        if _m1b_reg3.get('m1b_yoy') is not None and _m1b_reg3.get('m2_yoy') is not None:
            _reg_new['M1B-M2 資金缺口'] = {'last_updated': _proxy_date, 'rows': 1,
                                       'category': CAT_TW_MACRO, 'frequency': 'monthly'}
        else:
            _reg_missing(_reg_new, 'M1B-M2 資金缺口', category=CAT_TW_MACRO, frequency='monthly')

        # ── 宏觀指標:VIX → 🌐 國際金融 / CPI+Fed → 🌍 美國總經 /
        #              PMI+出口+NDC → 🇹🇼 台灣總經 ─────────
        _macro_reg3 = _reg_inp.macro_info or {}
        _macro_cat_map = {
            'vix':         (CAT_INTL,     'VIX 波動率指數',           'daily'),
            'us_core_cpi': (CAT_US_MACRO, '美國核心CPI年增率',         'monthly'),
            'fed_funds':   (CAT_US_MACRO, '美國 Fed Funds Rate',       'monthly'),
            'ism_pmi':     (CAT_TW_MACRO, '🇹🇼 台灣 PMI 製造業指數',  'monthly'),
            'tw_export':   (CAT_TW_MACRO, '台灣出口年增率',             'monthly'),
            'ndc_signal':  (CAT_TW_MACRO, '景氣先行指標（NDC）',        'monthly'),
        }
        for _mkey, (_mcat, _mname, _mfreq) in _macro_cat_map.items():
            _msub = _macro_reg3.get(_mkey)
            if _msub:
                if isinstance(_msub, dict):
                    _raw_d = (_msub.get('date') or _msub.get('period')
                              or (_msub.get('dates') or [''])[-1] or _proxy_date)
                    _mdate = str(_raw_d)[:10]
                else:
                    _mdate = _proxy_date
                _reg_new[_mname] = {'last_updated': _mdate, 'rows': 1,
                                    'category': _mcat, 'frequency': _mfreq}
            else:
                _reg_missing(_reg_new, _mname, category=_mcat, frequency=_mfreq)

        # ── 先行指標:5 細項 → 💰 籌碼 ─────────────────────
        _li_reg = _reg_inp.li_latest
        _li_groups = {
            '[先行指標] 三大法人現貨':    ['外資', '投信', '自營'],
            '[先行指標] 外資期貨留倉':    ['外資大小'],
            '[先行指標] 選擇權PCR':       ['選PCR', '外(選)'],
            '[先行指標] 成交量（TWSE）':  ['成交量'],
            '[先行指標] 未平倉/韭菜指數': ['前五大留倉', '前十大留倉', '未平倉口數', '韭菜指數'],
        }
        if isinstance(_li_reg, pd.DataFrame) and not _li_reg.empty:
            _li_date_cols = [c for c in ['_date'] if c in _li_reg.columns]
            for _grp, _cols in _li_groups.items():
                _vcols = [c for c in _cols if c in _li_reg.columns]
                if not _vcols:
                    _reg_missing(_reg_new, _grp, category=CAT_CHIPS, frequency='daily')
                    continue
                _sub = _li_reg[_li_date_cols + _vcols].copy()
                _mask = _sub[_vcols].apply(
                    lambda s: s.notna() & (s.astype(str).str.strip() != '-')
                ).any(axis=1)
                _sub = _sub[_mask]
                if not _sub.empty:
                    _reg_add(_reg_new, _grp, _sub, category=CAT_CHIPS, frequency='daily')
                else:
                    _reg_missing(_reg_new, _grp, category=CAT_CHIPS, frequency='daily')
        else:
            for _grp in _li_groups:
                _reg_missing(_reg_new, _grp, category=CAT_CHIPS, frequency='daily')

        # ── 個股細項 → 🏢 個股財報 ──────────────────────
        _t2d_reg = st.session_state.get('t2_data')
        if _t2d_reg:
            _s2r = _t2d_reg.get('sid', '')
            _n2r = (_t2d_reg.get('name') or _s2r) or _s2r
            _pfx = f'[個股] {_s2r} {_n2r}'
            _lbl_freq = {
                '價格走勢': 'daily', '月營收': 'monthly',
                '季財報': 'quarterly', '現金流量': 'quarterly', '資產負債': 'quarterly'
            }
            for _lbl, _key in [('價格走勢','df'),('月營收','rev'),
                               ('季財報','qtr'),('現金流量','cl'),('資產負債','cx')]:
                _sub = _t2d_reg.get(_key)
                _rname = f'{_pfx} | {_lbl}'
                _f = _lbl_freq[_lbl]
                if isinstance(_sub, pd.DataFrame) and not _sub.empty:
                    _reg_add(_reg_new, _rname, _sub, category=CAT_STOCK, frequency=_f)
                else:
                    _reg_missing(_reg_new, _rname, category=CAT_STOCK, frequency=_f)
        else:
            _pfx0 = '[個股] — 尚未搜尋'
            for _lbl0, _f0 in [('價格走勢','daily'),('月營收','monthly'),
                               ('季財報','quarterly'),('現金流量','quarterly'),('資產負債','quarterly')]:
                _reg_missing(_reg_new, f'{_pfx0} | {_lbl0}', category=CAT_STOCK, frequency=_f0)

        # ── 比較排行 → 🏢 個股財報 ──────────────────────
        _t3d_reg = st.session_state.get('t3_data')
        if _t3d_reg and _t3d_reg.get('results'):
            _reg_new['[比較] 多股比較排行'] = {
                'last_updated': 'N/A', 'rows': len(_t3d_reg['results']),
                'category': CAT_STOCK, 'frequency': 'daily',
            }
        else:
            _reg_missing(_reg_new, '[比較] 多股比較排行', category=CAT_STOCK, frequency='daily')

        # ── ETF 細項 → 🏦 ETF / 基金 ────────────────────
        _etf1_reg = st.session_state.get('etf_single_data') or {}
        _etf_pdf  = _etf1_reg.get('price_df')
        _etf_tk   = _etf1_reg.get('ticker', '')
        _etf_nm   = _etf1_reg.get('name', '')
        _etf_pfx  = f'[ETF] {_etf_tk} {_etf_nm}'.strip() if _etf_tk else '[ETF] — 尚未搜尋'
        if isinstance(_etf_pdf, pd.DataFrame) and not _etf_pdf.empty:
            _reg_add(_reg_new, f'{_etf_pfx} | 價格走勢', _etf_pdf, category=CAT_ETF, frequency='daily')
        else:
            _reg_missing(_reg_new, f'{_etf_pfx} | 價格走勢', category=CAT_ETF, frequency='daily')
        if _etf1_reg.get('cur_yield') is not None:
            _reg_new[f'{_etf_pfx} | 殖利率與技術分析'] = {
                'last_updated': 'N/A', 'rows': 1, 'category': CAT_ETF, 'frequency': 'daily',
            }
        else:
            _reg_missing(_reg_new, f'{_etf_pfx} | 殖利率與技術分析', category=CAT_ETF, frequency='daily')
        _etf2_reg = st.session_state.get('etf_portfolio_data') or {}
        if _etf2_reg.get('rows'):
            _etf2n = len(_etf2_reg['rows'])
            _reg_new[f'[ETF組合] 再平衡分析（{_etf2n}檔）'] = {
                'last_updated': 'N/A', 'rows': _etf2n, 'category': CAT_ETF, 'frequency': 'daily',
            }
        else:
            _reg_missing(_reg_new, '[ETF組合] 再平衡分析', category=CAT_ETF, frequency='daily')
        _etf3_reg = st.session_state.get('etf_backtest_data') or {}
        if _etf3_reg.get('cagr') is not None:
            _etf3n = len(_etf3_reg.get('weights', {}))
            _reg_new[f'[ETF回測] 回測績效（{_etf3n}檔）'] = {
                'last_updated': 'N/A', 'rows': _etf3n, 'category': CAT_ETF, 'frequency': 'daily',
            }
        else:
            _reg_missing(_reg_new, '[ETF回測] 回測績效', category=CAT_ETF, frequency='daily')

        st.session_state['data_registry'] = _reg_new
        print(f'[DataRegistry] 已登錄 {len(_reg_new)} 個資料源，類別標籤已寫入')
    except Exception as _re:
        print(f'[DataRegistry] 建立失敗: {_re}')
