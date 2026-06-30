"""src/ui/tabs/stock_sections/section_kline_chart.py — F. K線技術圖 + 健康度走勢 section(v18.409 U4 Phase 3-F).

從 tab_stock.py:1199-1313 抽出。
- F K線技術圖文案 + plot_combined_chart(含三大法人籌碼)
- K線動態趨勢建議(classify_trend_4tier + border_left_banner)
- 健康度走勢圖(近 5 日 plotly + 評分突變偵測)

§8.2 layer:L5 UI Tab section helper(中風險:115 LOC,含 plotly 圖)。

對外 API:
- render_kline_chart_section(sid2, name2, df2, price2, health2, rsi2,
                              show_ma_dict, t2_adjusted, t2d) -> None
"""
from __future__ import annotations

import datetime

import plotly.graph_objects as go
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from src.ui.render import plot_combined_chart, teacher_conclusion
from src.ui.render.tab_sections import border_left_banner
from src.ui.tabs.tab_helpers import classify_trend_4tier


def render_kline_chart_section(sid2: str, name2: str, df2, price2,
                                health2, rsi2, show_ma_dict,
                                t2_adjusted: bool, t2d: dict) -> None:
    """F. K線技術圖表 + 近 5 日健康度走勢。

    Args:
        sid2: 股票代碼
        name2: 股票名稱
        df2: 股價 DataFrame(含 MA20/MA100)
        price2: 當前股價
        health2: 當前健康分
        rsi2: 當前 RSI
        show_ma_dict: 均線顯示設定 dict
        t2_adjusted: 是否還原權息(True → 還原 K 線)
        t2d: tab2 data dict(從 session_state)用於 err 訊息
    """
    # ══ F. K線技術圖 ═══════════════════════════════════════
    st.markdown('---')
    st.markdown('#### 📊 F. K線技術圖表（含三大法人籌碼）')
    _fa = f'{sid2} K線技術'
    _fb_txt = ''
    _fc_txt = ''
    if df2 is not None and not df2.empty and len(df2) >= 20:
        _p_now_f = float(df2['close'].iloc[-1])
        _ma20_f = float(df2['close'].rolling(20).mean().iloc[-1])
        _above_f = _p_now_f > _ma20_f
        _inst_f = st.session_state.get('t2_inst', {})
        _fnet_f = _inst_f.get('外資', 0) if _inst_f else 0
        if _above_f and _fnet_f > 0:
            _fb_txt = '站上月線 + 外資買超，主力進駐訊號，可跟進'
            _fc_txt = '停損設月線下方'
        elif _above_f and _fnet_f < 0:
            _fb_txt = '站上月線但外資賣超，需謹慎確認主力方向'
            _fc_txt = '等待外資轉買後再行動'
        elif not _above_f and _fnet_f > 0:
            _fb_txt = '月線下方但外資買超，可能正在築底'
            _fc_txt = '等待重回月線確認後再評估'
        else:
            _fb_txt = '月線下方且外資賣超，趨勢偏空，暫時迴避'
            _fc_txt = '等待更明確的多頭訊號'
        _fa = f'{sid2} 現價{_p_now_f:.1f}（{"站月線" if _above_f else "跌月線"}）| 外資{"買超" if _fnet_f > 0 else "賣超" if _fnet_f < 0 else "中性"}'
    else:
        _fb_txt = '技術資料載入中，請先點擊「🔍 載入完整分析」'
    st.markdown(teacher_conclusion('朱家泓', _fa, _fb_txt, _fc_txt), unsafe_allow_html=True)
    if df2 is not None and not df2.empty:
        fig_k = plot_combined_chart(df2, sid2, name2, show_ma_dict,
                                     k_line_type='還原K線' if t2_adjusted else '一般K線')
        st.plotly_chart(fig_k, width='stretch',
                        config={'displayModeBar': True, 'displaylogo': False,
                                'modeBarButtonsToRemove': ['lasso2d', 'select2d']})
    else:
        if t2d.get('err'):
            st.error(f'❌ {t2d["err"]}')
    # ── K線動態趨勢建議(SSOT: tab_helpers.classify_trend_4tier,組合 Tab 共用)──
    if df2 is not None and 'MA20' in df2.columns and 'MA100' in df2.columns:
        _kp = price2
        _km20 = float(df2['MA20'].iloc[-1])
        _km100 = float(df2['MA100'].iloc[-1])
        _trend_lbl, _tc = classify_trend_4tier(_kp, _km20, _km100)
        if '多頭' in _trend_lbl:
            _trend_msg = (f'{_trend_lbl}：股價 {_kp:.1f} ＞ MA20 {_km20:.1f} ＞ MA100 {_km100:.1f}'
                          ' — 宏爺：可持股，大盤多頭才做個股')
        elif '空頭' in _trend_lbl:
            _trend_msg = (f'{_trend_lbl}：股價 {_kp:.1f} ＜ MA20 {_km20:.1f} ＜ MA100 {_km100:.1f}'
                          ' — 宏爺：不做多，嚴格停損')
        elif '多箱' in _trend_lbl:
            _trend_msg = (f'{_trend_lbl}：股價在 MA100 之上'
                          f' — 宏爺：等待站上 MA20({_km20:.1f})確認方向')
        else:
            _trend_msg = (f'{_trend_lbl}：股價低於 MA100'
                          ' — 宏爺：耐心等待多頭訊號，不摸底')
        st.markdown(
            border_left_banner(_tc, _trend_msg, border_width=4,
                               font_size=13, padding_y=10, padding_x=14,
                               margin_y=8, bold=True),
            unsafe_allow_html=True,
        )

    # K線均線結論(安全版)
    # R-UI-1 v18.412:inline `<div border-left>` → border_left_banner SSOT
    _trend_msg_safe = _trend_msg if '_trend_msg' in dir() else '⚪ K線資料不足'
    _kl_c = TRAFFIC_GREEN if '多頭' in _trend_msg_safe or '✅' in _trend_msg_safe else (TRAFFIC_RED if '空頭' in _trend_msg_safe else TRAFFIC_YELLOW)
    st.markdown(border_left_banner(
        _kl_c,
        f'<span style="font-size:11px;color:#8b949e;">🎓 宏爺 · 均線排列</span>　'
        f'<span style="font-weight:700;">{_trend_msg_safe}</span>',
        padding_y=7, font_size=13,
    ), unsafe_allow_html=True)

    # ── 近5日評分走勢(儲存本次評分到歷史)───────────────────
    _score_hist_key = f'score_hist_{sid2}'
    _score_hist = st.session_state.get(_score_hist_key, [])
    # 加入今日評分
    _today_str = datetime.date.today().strftime('%m/%d')
    _last_entry = _score_hist[-1] if _score_hist else {}
    if _last_entry.get('date') != _today_str:
        _score_hist.append({
            'date':    _today_str,
            'health':  health2,
            'rsi':     rsi2 or 0,
            'total':   0,  # 多因子評分在 Tab3 中
        })
        _score_hist = _score_hist[-7:]  # 只保留最近7天
        st.session_state[_score_hist_key] = _score_hist

    if len(_score_hist) >= 2:
        st.markdown('---')
        st.markdown('##### 📈 健康度走勢（近5日）')
        _fig_sh = go.Figure()
        _sh_dates = [r['date'] for r in _score_hist]
        _sh_health = [r['health'] for r in _score_hist]
        # 填色區間
        _fig_sh.add_hrect(y0=80, y1=100, fillcolor='rgba(63,185,80,0.08)',  line_width=0)
        _fig_sh.add_hrect(y0=50, y1=80,  fillcolor='rgba(210,153,34,0.05)', line_width=0)
        _fig_sh.add_hrect(y0=0,  y1=50,  fillcolor='rgba(248,81,73,0.05)',  line_width=0)
        _fig_sh.add_trace(go.Scatter(
            x=_sh_dates, y=_sh_health, mode='lines+markers',
            line=dict(color='#58a6ff', width=2.5),
            marker=dict(size=8, color=[TRAFFIC_GREEN if v >= 80 else (TRAFFIC_YELLOW if v >= 50 else TRAFFIC_RED)
                                       for v in _sh_health]),
            text=[str(v) for v in _sh_health], textposition='top center',
            hovertemplate='%{x}<br>健康度：%{y:.0f}<extra></extra>'
        ))
        _fig_sh.update_layout(
            height=180, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
            font=dict(color='white', size=10), margin=dict(l=10, r=10, t=10, b=20),
            xaxis=dict(gridcolor='#21262d'), yaxis=dict(gridcolor='#21262d', range=[0, 105]),
            showlegend=False)
        st.plotly_chart(_fig_sh, width='stretch', config={'displayModeBar': False})
        # 評分突變偵測(分數飆升≥20分)
        if len(_sh_health) >= 2 and _sh_health[-1] - _sh_health[-2] >= 20:
            st.success(f'🚀 評分突變！健康度從 {_sh_health[-2]:.0f} → {_sh_health[-1]:.0f}（+{_sh_health[-1] - _sh_health[-2]:.0f}），可能是主升段起點！')
