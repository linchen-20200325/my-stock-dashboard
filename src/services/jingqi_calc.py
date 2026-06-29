"""src/services/jingqi_calc.py — 旌旗指數(全市場廣度)計算 + session_state write(P3-D11 v18.392)。

從 tab_macro inline 抽出(原 line 347-378,~32 LOC)。

「旌旗」= 站在均線上股票%,代表市場廣度健康度:
- ADL ad_ratio 是主源(tail(5).mean)
- 大盤漲跌備援(正日 +5%,4 漲日 = 60%, 5 跌日 = 40%)
- 三段燈號(BULL/NEUTRAL/BEAR SSOT from shared.signal_thresholds)
- 寫 session_state['jingqi_info'] 8 keys(供戰情概覽/作戰室/section_inputs 讀)

§8.2 L3 service:純 compute + 1 個 session_state write。
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.signal_thresholds import (
    BREADTH_BEAR_PCT,
    BREADTH_BULL_PCT,
    BREADTH_NEUTRAL_PCT,
)


def compute_and_store_jingqi(df_adl_raw: Any) -> None:
    """從 ADL(主)或大盤漲跌(備援)算旌旗 ratio 並寫 session_state。

    df_adl_raw: DataFrame | None — 含 'ad_ratio' 欄(由 fetch_adl 抓);
                None / 空 / 缺欄 → fallback 用 cl_data.tw['台股加權指數'] 估算。

    成功時寫 `st.session_state['jingqi_info']` = {avg/pos/regime/color/label/
    total/source/pct20/pct60/pct120/pct240}。
    全敗(無 ADL + 無大盤資料)→ 不寫(誠實顯示未載入,§1)。
    """
    _jq_ratio_src = None
    _jq_ratio = None
    if df_adl_raw is not None and not df_adl_raw.empty and 'ad_ratio' in df_adl_raw.columns:
        _jq_ratio_src = 'ADL'
        _jq_ratio = float(df_adl_raw['ad_ratio'].tail(5).mean())
    else:
        # 備援:用大盤漲跌估算(正日=60%上漲,負日=40%)
        _tw_d = st.session_state.get('cl_data', {}).get('tw', {})
        _twii_d = _tw_d.get('台股加權指數')
        if _twii_d is not None and not _twii_d.empty:
            _cc_d = 'close' if 'close' in _twii_d.columns else 'Close'
            if _cc_d in _twii_d.columns:
                _ret5 = _twii_d[_cc_d].pct_change().tail(5)
                _up_days = (_ret5 > 0).sum()
                _jq_ratio = 40 + _up_days * 5  # 全漲=65%, 全跌=40%
                _jq_ratio_src = '大盤估算'

    if _jq_ratio_src and _jq_ratio_src != '預設值':
        _jq_ratio = float(_jq_ratio)
        _jq_pos = ('80~100%' if _jq_ratio >= BREADTH_BULL_PCT
                   else ('50~70%' if _jq_ratio >= BREADTH_NEUTRAL_PCT
                         else ('20~40%' if _jq_ratio >= BREADTH_BEAR_PCT else '0~20%')))
        _jq_reg = ('bull' if _jq_ratio >= BREADTH_BULL_PCT
                   else ('neutral' if _jq_ratio >= BREADTH_NEUTRAL_PCT else 'bear'))
        _jq_col = (TRAFFIC_GREEN if _jq_ratio >= BREADTH_BULL_PCT
                   else (TRAFFIC_YELLOW if _jq_ratio >= BREADTH_NEUTRAL_PCT else TRAFFIC_RED))
        _jq_lbl = ('🟢 多頭積極' if _jq_ratio >= BREADTH_BULL_PCT
                   else ('🟡 中性均衡' if _jq_ratio >= BREADTH_NEUTRAL_PCT else '🔴 保守防禦'))
        st.session_state['jingqi_info'] = {
            'avg': _jq_ratio, 'pos': _jq_pos, 'regime': _jq_reg,
            'color': _jq_col, 'label': _jq_lbl, 'total': 0,
            'source': _jq_ratio_src,
            'pct20': _jq_ratio, 'pct60': _jq_ratio * 0.9,
            'pct120': _jq_ratio * 0.8, 'pct240': _jq_ratio * 0.7,
        }
