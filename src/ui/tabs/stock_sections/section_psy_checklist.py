"""src/ui/tabs/stock_sections/section_psy_checklist.py — 心理檢查 + 勝利方程式 + 禁止操作 3 section(v18.406 U4 Phase 2-Psy).

從 tab_stock.py:826-909 抽出。原 3 個相連 section 共享 _q3 / _wr_margin2 / _wr_reg2 state,
合併為一個 render 函式維持原邏輯。

§8.2 layer:L5 UI Tab section helper。

對外 API:
- render_psy_checklist_section(sid2, df2, health2, _atr2_val) -> None
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED
from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
)
from src.ui.render.tab_sections import border_left_banner, box_wrapper_open


def render_psy_checklist_section(sid2: str, df2, health2,
                                   _atr2_val=None) -> None:
    """心理檢查 + 勝利方程式 + 禁止操作 3 連 section(SOP 進場檢核 +
    5 條件勝利方程式 + 4 條禁止操作清單)。

    Args:
        sid2: 股票代碼
        df2: 股價 DataFrame
        health2: 個股健康分(0-100)
        _atr2_val: ATR 值(None → 用 price × 7% 估算停損)
    """
    # ══ 操作前心理檢查 + 勝利方程式 ═══════════════════════
    st.markdown('---')
    st.markdown('#### 🧠 操作前必做：心理檢查 + 勝利方程式')

    _mc_cols = st.columns([3, 2])

    with _mc_cols[0]:
        st.markdown(box_wrapper_open('primary', padding=12), unsafe_allow_html=True)
        st.markdown('**📋 SOP 進場強制檢核表（4關卡全通過才顯示建議）**')
        _wr_reg_chk = st.session_state.get('mkt_info', {}).get('regime', 'neutral')
        _price_chk = float(df2['close'].iloc[-1]) if df2 is not None and not df2.empty else 0
        _open5_chk = (float(df2['close'].iloc[-6]) if df2 is not None and len(df2) >= 6
                      else _price_chk)
        _surge_chk = round((_price_chk - _open5_chk) / max(_open5_chk, 1) * 100, 1)
        # _atr2_val 來自 caller;若 None 則用價格 × 7% 估算停損距離
        _atr_eff = _atr2_val if _atr2_val is not None else _price_chk * 0.07
        _stop_chk = round(_price_chk - 1.5 * _atr_eff, 2)
        _q1 = st.checkbox(
            f'① 確認非空頭格局（目前：{_wr_reg_chk}）',
            value=_wr_reg_chk != 'bear', key=f't2_q1_{sid2}',
            disabled=_wr_reg_chk == 'bear'
        )
        _q2 = st.checkbox(
            f'② 確認未追高超過5%（近5日漲幅：{_surge_chk:+.1f}%）',
            value=abs(_surge_chk) <= 5, key=f't2_q2_{sid2}',
            disabled=abs(_surge_chk) > 10
        )
        _q3 = st.checkbox(
            f'③ 確認停損價（跌破 {_stop_chk} 元無條件出場）',
            key=f't2_q3_{sid2}'
        )
        _all_checked = _q1 and _q2 and _q3
        if _all_checked:
            st.success('✅ 心理狀態良好，可以繼續評估操作')
        else:
            st.warning('⚠️ 尚有項目未確認，建議先暫停，避免情緒化操作')
        st.markdown('</div>', unsafe_allow_html=True)

    with _mc_cols[1]:
        st.markdown(
            f'<div style="background:#0a1628;border:1px solid {TRAFFIC_GREEN};'
            f'border-radius:10px;padding:12px;">', unsafe_allow_html=True)
        st.markdown('**🏆 勝利方程式（需全部符合）**')
        _wr_mkt2 = st.session_state.get('mkt_info', {})
        _wr_reg2 = _wr_mkt2.get('regime', 'neutral') if _wr_mkt2 else 'neutral'
        _wr_margin2 = st.session_state.get('cl_data', {}).get('margin', 0) or 0
        _win_conds = [
            ('🌍 大盤多頭燈號',  _wr_reg2 == 'bull'),
            (f'💰 融資安全(<{MARGIN_BALANCE_WARN_THRESHOLD_YI:.0f}億)',
             _wr_margin2 < MARGIN_BALANCE_WARN_THRESHOLD_YI),
            ('🏥 個股健康度≥75', health2 >= 75 if df2 is not None else False),
            ('💎 非357昂貴區',
             '昂貴' not in str(st.session_state.get('t2_data', {}).get('val', ''))),
            ('✋ 已設停損點',     _q3),
        ]
        _win_count = sum(1 for _, v in _win_conds if v)
        for _wn, _wv in _win_conds:
            _wc = TRAFFIC_GREEN if _wv else TRAFFIC_RED
            _wi = '✅' if _wv else '❌'
            st.markdown(f'<div style="font-size:12px;color:{_wc};padding:2px 0;">{_wi} {_wn}</div>',
                        unsafe_allow_html=True)
        st.markdown(
            f'<div style="margin-top:8px;font-size:13px;font-weight:700;'
            f'color:{TRAFFIC_GREEN if _win_count >= 4 else TRAFFIC_RED};">'
            f'{"🚀 符合 " + str(_win_count) + "/5，可以考慮操作" if _win_count >= 4 else "⛔ 僅符合 " + str(_win_count) + "/5，建議等待"}'
            f'</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 今日禁止操作清單
    st.markdown('#### 🚫 今日禁止操作情況（有任何一項→今天暫停）')
    _ban_items = []
    _wr_price = float(df2['close'].iloc[-1]) if df2 is not None and not df2.empty else 0
    _wr_open = float(df2['close'].iloc[-5]) if df2 is not None and len(df2) >= 5 else _wr_price
    _today_surge = (round((_wr_price - _wr_open) / max(_wr_open, 1) * 100, 1)
                    if _wr_open else 0)
    if abs(_today_surge) > 4:
        _ban_items.append(f'📈 個股近5日漲幅 {_today_surge:+.1f}% 超過4%（追高風險）')
    _ml = st.session_state.get('monthly_loss_pct', 0)
    if _ml < -5:
        _ban_items.append(f'📉 本月已虧損 {abs(_ml):.1f}%（情緒操作風險上升）')
    if _wr_margin2 > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:
        _ban_items.append(f'💸 融資 {_wr_margin2:.0f}億 極度過熱（散戶追高期，等待）')
    if _wr_reg2 == 'bear':
        _ban_items.append('🔴 大盤空頭格局（禁止做多）')

    if _ban_items:
        for _bi in _ban_items:
            st.markdown(
                border_left_banner(TRAFFIC_RED, f'⛔ {_bi}',
                                   padding_y=7, margin_y=3, bg='#2a0d0d'),
                unsafe_allow_html=True,
            )
    else:
        st.success('✅ 今日無禁止操作情況，可以正常評估')
