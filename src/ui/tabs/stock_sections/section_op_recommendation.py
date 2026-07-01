"""src/ui/tabs/stock_sections/section_op_recommendation.py — 即時操作建議規則引擎 section(v18.406 U4 Phase 2-OpRec).

從 tab_stock.py:1698-1753 抽出。
對齊 TAB_STOCK_AUDIT.md Phase 2 低風險 section batch。

§8.2 layer:L5 UI Tab section helper。

對外 API:
- render_op_recommendation_section(sid2, health2, vcp2, avg_div2, price2, rsi2, cl2, cx2) -> None
"""
from __future__ import annotations

import streamlit as st

from shared.health_thresholds import HEALTH_GRADE_A_MIN
from shared.thresholds import YIELD_MID_DEC
from src.services.app_ai_service import generate_ai_comment
from src.ui.render import teacher_conclusion


def render_op_recommendation_section(sid2: str, health2,
                                       vcp2, avg_div2, price2, rsi2,
                                       cl2, cx2) -> None:
    """即時操作建議(規則引擎):4 訊號共振判定 + AI 文案。

    Args:
        sid2: 股票代碼
        health2: 個股健康分(0-100)
        vcp2: VCP dict(`contracting`)
        avg_div2: 5 年平均配息
        price2: 當前股價
        rsi2: RSI 值
        cl2: 合約負債(元)
        cx2: 資本支出(元)
    """
    st.markdown('#### 💡 即時操作建議（規則引擎）')
    _reg_op = st.session_state.get('mkt_info', {}).get('regime', 'neutral')
    _sig_count = sum([
        1 if health2 >= HEALTH_GRADE_A_MIN else 0,
        1 if _reg_op == 'bull' else 0,
        1 if (vcp2 and vcp2.get('contracting')) else 0,
        1 if (avg_div2 > 0 and price2 > 0
              and price2 <= round(avg_div2 / YIELD_MID_DEC, 1)) else 0,
    ])
    if _reg_op == 'bear':
        _op_a = f'大盤空頭格局，{sid2} 無論評分多高，先降倉至20%以下'
        _op_b = '市場趨勢優先，個股強不等於能賺錢'
    elif _sig_count >= 3:
        _op_a = f'{_sig_count}個訊號共振（健康度+大盤+VCP+估值），可積極進場'
        _op_b = '分批建倉，停損設健康度跌破60'
    elif _sig_count >= 2:
        _op_a = f'{_sig_count}個訊號共振，中性偏多，可小倉試水溫'
        _op_b = '輕倉試探，等待更多確認訊號'
    else:
        _op_a = f'只有{_sig_count}個訊號，條件不足，今日不操作 {sid2}'
        _op_b = '耐心等待，寧可錯過勿強求'
    st.markdown(teacher_conclusion('宏爺', f'{sid2} 共振訊號 {_sig_count}/4', _op_a, _op_b),
                unsafe_allow_html=True)
    try:
        _mkt_top_g = st.session_state.get('mkt_info', {})
        _m1b_top_g = st.session_state.get('m1b_m2_info', {})
        _bias_g = st.session_state.get('bias_info', {})
        _m1b_diff_g = (_m1b_top_g.get('m1b_yoy', 0) - _m1b_top_g.get('m2_yoy', 0)
                       if _m1b_top_g else 0)
        # 取 Tab3 最近分析的外資資料
        _cd_g = st.session_state.get('cl_data', {})
        _inst_g = _cd_g.get('inst', {})
        _fk_g = next((k for k in _inst_g if '外資' in k), None)
        _tk_g = next((k for k in _inst_g if '投信' in k), None)
        _comment_data = {
            'health':      health2,
            'score':       0,  # Tab3 多因子評分(此處無法取得,用0)
            'rsi':         rsi2,
            'vcp_ok':      bool(vcp2 and isinstance(vcp2, dict) and vcp2.get('contracting')),
            'bias_240':    _bias_g.get('bias_240', 0),
            'bias_20':     _bias_g.get('bias_20', 0),
            # val_label / trend 在原 tab_stock 內走 `if 'xx' in dir()`,但 _357_label2 /
            # _trend_text2 從未在 render_tab_stock 內被定義,故 dir() 永遠 False,實質 ''
            'val_label':   '',
            'trend':       '',
            'cl':          cl2 / 1e8 if cl2 and cl2 > 0 else 0,
            'cx':          cx2 / 1e8 if cx2 and cx2 > 0 else 0,
            'foreign_buy': _inst_g.get(_fk_g, {}).get('net', 0) if _fk_g else 0,
            'trust_buy':   _inst_g.get(_tk_g, {}).get('net', 0) if _tk_g else 0,
            'm1b_diff':    _m1b_diff_g,
        }
        _comment_txt = generate_ai_comment(_comment_data)
        if _comment_txt:
            st.markdown(
                '<div style="background:#0d1117;border:1px solid #30363d;'
                'border-radius:10px;padding:14px;margin-bottom:10px;'
                'font-size:13px;color:#c9d1d9;line-height:1.7;">'
                + _comment_txt.replace(chr(10), '<br>') +
                '</div>', unsafe_allow_html=True)
    except Exception as _ai_err:
        st.warning(f'⚠️ AI 分析暫時無法使用（{type(_ai_err).__name__}），以上為規則引擎建議。')
