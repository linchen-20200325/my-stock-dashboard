"""src/ui/tabs/stock_sections/section_when_buy_sell.py — 什麼時候買/賣 section(v18.410 U4 Phase 3-WBS).

從 tab_stock.py:796-1029 抽出。
- 🚨 出場點綜合提示(三維:利空新聞 + 技術 + 籌碼)
- 📈 進場訊號 + 📉 減碼/出場訊號 + 🎯 目標+停損 3 columns
- 關鍵價位 K 線圖(停利/停損/支撐壓力/加碼點 9 條水平線)

§8.2 layer:L5 UI Tab section helper(中-高風險:234 LOC,含 plotly K 線)。

對外 API:
- render_when_buy_sell_section(sid2, name2, df2, bb2, k2, d2, rsi2, vcp2,
                                tp1_p, tp2_p, hi20_p, lo20_p, sl_p,
                                gemini_call) -> None
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.signal_thresholds import (
    BB_DROP_OUT_RATIO,
    BB_NEAR_UPPER_RATIO,
    STOCK_BIAS_DEEP_DEVIATION_PCT,
    STOCK_BIAS_MILD_DEVIATION_PCT,
    STOCK_BIAS_OVERHEAT_PCT,
    STOCK_RS_NEUTRAL_MIN,
    STOCK_RS_STRONG_MIN,
)
from src.compute.scoring import (
    compute_tech_bearish,
    evaluate_exit_signals,
    judge_news_sentiment_cached,
)
from src.compute.scoring import calc_rs_score, rs_slope
from src.data.news import fetch_stock_news as _fetch_stock_news
from src.services import analyze_20d_chips_from_df
from src.ui.render.tab_sections import box_wrapper_open
from src.ui.tabs.tab_helpers import safe_ma
from shared.calc_helpers import calc_bias_pct


def render_when_buy_sell_section(sid2: str, name2: str, df2, bb2, k2, d2,
                                  rsi2, vcp2,
                                  tp1_p: float, tp2_p: float,
                                  hi20_p: float, lo20_p: float, sl_p: float,
                                  gemini_call) -> None:
    """什麼時候買?什麼時候賣? — 進出場訊號 + 關鍵價位 K 線圖。

    Args:
        sid2: 股票代碼
        name2: 股票名稱
        df2: 股價 DataFrame
        bb2: Bollinger dict(upper/ma)
        k2: KD 中 K 值
        d2: KD 中 D 值
        rsi2: RSI
        vcp2: VCP dict
        tp1_p / tp2_p: 停利目標 1 / 2(從操作雷達傳入)
        hi20_p / lo20_p: 近 20 日壓力 / 支撐(從操作雷達傳入)
        sl_p: 建議停損(從操作雷達傳入)
        gemini_call: AI 呼叫函式(從 app.py 注入)
    """
    st.markdown('---')
    st.markdown('#### 🎯 什麼時候買？什麼時候賣？')
    st.markdown(
        '<div style="background:#0a1628;border-left:3px solid #58a6ff;padding:8px 12px;'            'border-radius:0 6px 6px 0;margin-bottom:8px;font-size:12px;color:#c9d1d9;">'
        '💡 系統自動幫你檢查<b>多套策略的進出場條件</b>，符合越多條件越可靠。'
        '<br>🔵 <b>進場訊號</b>：這些條件出現代表可以考慮買進'
        '<br>🔴 <b>出場訊號</b>：這些條件出現代表要考慮賣出或減碼'
        '<br>🎯 <b>目標價</b>：預計可以獲利的目標 | 🛑 <b>停損</b>：跌到這裡要認賠出場'
        '</div>', unsafe_allow_html=True)
    if df2 is not None and not df2.empty:
        _p2    = float(df2['close'].iloc[-1])
        _ma5   = safe_ma(df2, 5)
        _ma20  = safe_ma(df2, 20)
        _ma60  = safe_ma(df2, 60)
        _ma240 = safe_ma(df2, 240)

        # 趨勢排列
        _bull_align  = _p2 > _ma20 > _ma60   # 多頭排列
        _bear_align  = _p2 < _ma20 < _ma60   # 空頭排列
        _bias_i      = calc_bias_pct(_p2, _ma240, decimals=1) or 0
        _bias_20_i   = calc_bias_pct(_p2, _ma20,  decimals=1) or 0

        # ── 🧭 加碼三問(規則化,防攤平弱勢 / 追高;v19.62 Feature 3)──
        try:
            from shared.position_throttle import assess_add_gate
            from src.compute.etf.etf_smart_analysis import compute_std_bands
            _sb = compute_std_bands(df2['close'], window=252)
            _sz = _sb.get('sigma_z') if _sb.get('has_data') else None
            _ms = st.session_state.get('macro_state', {}) or {}
            _macro_def = bool(_ms.get('defense')) or (_ms.get('regime') in ('bear', 'caution'))
            _gate = assess_add_gate(_sz, _bear_align, _macro_def)
            _glabel = '🟢 可考慮加碼' if _gate['can_add'] else '🔴 不建議加碼'
            _rows = ''.join(
                f'<div style="font-size:12px;color:#c9d1d9;margin-top:2px;">'
                f'{"✅" if ok else "❌"} {name} '
                f'<span style="color:#8b949e;">— {note}</span></div>'
                for name, ok, note in _gate['checks'])
            st.markdown(
                f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;'
                f'padding:10px 14px;margin:6px 0;">'
                f'<b>🧭 加碼三問</b>：<b>{_glabel}</b>{_rows}</div>',
                unsafe_allow_html=True)
            st.caption('💡 三個都 ✅ 才考慮加碼 —— **σ 夠低(不追高)＋ 趨勢沒壞(不攤平弱勢)'
                       '＋ 總經沒防守**。任一 ❌ 就先別加，等條件到齊再說。')
        except Exception as _e_gate:
            print(f'[when_buy_sell] add_gate: {type(_e_gate).__name__}: {_e_gate}')

        # 布林帶訊號
        _bb_upper    = (bb2.get('upper', 0) if isinstance(bb2, dict) else 0) or float('inf')
        _bb_ma       = (bb2.get('ma', 0)    if isinstance(bb2, dict) else 0)
        _bb_near_up  = bool(bb2) and _p2 >= _bb_upper * BB_NEAR_UPPER_RATIO
        _bb_drop_out = bool(bb2) and _p2 < _bb_upper * BB_DROP_OUT_RATIO and _p2 > _bb_ma

        # KD 訊號
        _kd_gold = k2 and d2 and k2 > d2  # 黃金交叉方向
        _kd_dead = k2 and d2 and k2 < d2 and k2 > 70  # 高檔死亡交叉

        # VCP 訊號
        _vcp_ok = bool(vcp2 and isinstance(vcp2, dict) and vcp2.get('contracting'))

        # 目標價(蔡森一比一對稱法)
        _hi20_i = float(df2['high'].tail(20).max())
        _lo20_i = float(df2['low'].tail(20).min())
        _range20 = _hi20_i - _lo20_i
        _target1 = round(_p2 + _range20, 2)  # 初步目標:現價 + 20日震幅

        # ══ 🚨 出場點綜合提示(三維:利空新聞 + 技術 + 籌碼)═════════
        try:
            _ex_tech = compute_tech_bearish(df2, k=k2, d=d2)
            _ex_chip = analyze_20d_chips_from_df(df2)
            _ex_chip_sig = _ex_chip.get('signal', '') if isinstance(_ex_chip, dict) else ''
            # 新聞標題(本 session 內快取,避免每次 rerun 重打 RSS)
            _ex_news_key = f'_exit_news_titles_{sid2}'
            _ex_titles = st.session_state.get(_ex_news_key)
            if _ex_titles is None:
                _ex_raw = _fetch_stock_news(sid2, name2, 8, recency='3m')
                _ex_titles = [n.get('title', '') for n in (_ex_raw or []) if n.get('title')]
                st.session_state[_ex_news_key] = _ex_titles
            _ex_news = (judge_news_sentiment_cached(gemini_call, sid2, name2, _ex_titles)
                        if _ex_titles else None)
            _ex = evaluate_exit_signals(_ex_tech, _ex_chip_sig, _ex_news)
            _ex_dim_html = ''.join(
                f'<span style="display:inline-block;margin:2px 6px 2px 0;padding:2px 8px;border-radius:10px;'
                f'font-size:11px;background:{"#3a1414" if _hit else "#161b22"};'
                f'color:{"#ff7b72" if _hit else "#8b949e"};border:1px solid '
                f'{TRAFFIC_RED if _hit else "#30363d"};">{"⚠️" if _hit else "✓"} {_nm}：{_desc}</span>'
                for _nm, _hit, _desc in _ex['dims'])
            st.markdown(
                f'<div style="margin:6px 0 12px;padding:10px 14px;border-radius:8px;'
                f'background:linear-gradient(90deg,{_ex["color"]}1f,#0d1117);'
                f'border-left:5px solid {_ex["color"]};">'
                f'<div style="font-size:15px;font-weight:900;color:{_ex["color"]};">'
                f'🚨 出場點綜合提示 — {_ex["headline"]}</div>'
                f'<div style="margin-top:6px;">{_ex_dim_html}</div>'
                f'<div style="font-size:10px;color:{TRAFFIC_NEUTRAL};margin-top:4px;">'
                f'三維計分(利空新聞為 Gemini 情緒判讀,6h 快取);下方為各策略詳細訊號</div>'
                f'</div>', unsafe_allow_html=True)
        except Exception as _ex_err:
            st.caption(f'⚪ 出場點綜合提示暫不可用：{_ex_err}')

        _sig_cols = st.columns(3)

        with _sig_cols[0]:
            st.markdown(box_wrapper_open('neutral'), unsafe_allow_html=True)
            st.markdown('**📈 進場訊號**')
            _entry = []
            if _bull_align:
                _entry.append('✅ 多頭排列（股>月>季）→ 朱家泓：可進場方向')
            if _vcp_ok:
                _entry.append('✅ VCP波幅收縮 → 策略3：即將突破，建底倉30-50%')
            if k2 and k2 < 30:
                _entry.append(f'✅ KD低檔 K={k2:.0f} → 策略1：底部進場區')
            if rsi2 and rsi2 < 30:
                _entry.append(f'✅ RSI超賣 {rsi2:.0f} → 反彈機會')
            if _bias_i < -STOCK_BIAS_DEEP_DEVIATION_PCT:
                _entry.append(f'✅ 年線負乖離 {_bias_i:+.0f}% → 策略1：左側布局區')
            # RS 相對強度
            try:
                _rs_val  = calc_rs_score(df2)
                _rs_up   = rs_slope(df2)
                _rs_color= TRAFFIC_GREEN if _rs_val >= STOCK_RS_STRONG_MIN else (TRAFFIC_YELLOW if _rs_val >= STOCK_RS_NEUTRAL_MIN else TRAFFIC_RED)
                _rs_trend= '↑強勢' if _rs_up else ('↓弱勢' if _rs_up is False else '')
                _entry.append(f'<span style="color:{_rs_color}">📊 RS相對強度 {_rs_val:.0f}分 {_rs_trend}</span>')
            except Exception:
                pass
            if not _entry:
                _entry.append('⚪ 暫無明確進場訊號')
            for _e in _entry:
                st.markdown(f'<div style="font-size:12px;color:#c9d1d9;padding:2px 0;">{_e}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with _sig_cols[1]:
            st.markdown(box_wrapper_open('neutral'), unsafe_allow_html=True)
            st.markdown('**📉 減碼/出場訊號**')
            _exit = []
            if _bear_align:
                _exit.append('🔴 空頭排列 → 朱家泓：禁止做多，考慮出清')
            if _kd_dead:
                _exit.append(f'⚠️ KD高檔死叉 K={k2:.0f} → 策略3：開始減碼')
            if _bb_drop_out:
                _exit.append('⚠️ 脫離布林上軌 → 策略3：減碼50%')
            if _bias_20_i > STOCK_BIAS_MILD_DEVIATION_PCT:
                _exit.append(f'⚠️ 月線乖離 {_bias_20_i:+.0f}% → 過熱，停利部分')
            if _bias_i > STOCK_BIAS_OVERHEAT_PCT:
                _exit.append(f'⚠️ 年線乖離 {_bias_i:+.0f}% → 策略1：分批出場')
            if _p2 < _ma5:
                _exit.append(f'⚠️ 跌破5MA({_ma5:.1f}) → 林穎：短線停利')
            # 週MACD 警示:12/26/9 EMA on weekly bars
            try:
                if df2 is not None and len(df2) >= 30:
                    _wdf = df2.copy()
                    _wdf.index = range(len(_wdf))
                    # 近30日K線轉換為週K(每5根合一)
                    _wclose = [float(_wdf['close'].iloc[min(i+4, len(_wdf)-1)])
                               for i in range(0, min(30, len(_wdf)), 5)]
                    if len(_wclose) >= 6:
                        _we12 = pd.Series(_wclose).ewm(span=3,adjust=False).mean()
                        _we26 = pd.Series(_wclose).ewm(span=5,adjust=False).mean()
                        _wmacd= _we12 - _we26
                        _whist= (_wmacd - _wmacd.ewm(span=3,adjust=False).mean()).tolist()
                        # 週MACD紅柱縮短(連續2根縮小)
                        if len(_whist)>=3 and _whist[-1]>0 and _whist[-1]<_whist[-2]<_whist[-3]:
                            _exit.append('⚠️ 週MACD紅柱連縮 → 上漲動能衰減，準備減碼')
                        elif len(_whist)>=2 and _whist[-2]>0 and _whist[-1]<=0:
                            _exit.append('🔴 週MACD翻負 → 中線趨勢轉弱，出清訊號')
            except Exception:
                pass
            if not _exit:
                _exit.append('⚪ 暫無明確出場訊號')
            for _ex in _exit:
                st.markdown(f'<div style="font-size:12px;color:#c9d1d9;padding:2px 0;">{_ex}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with _sig_cols[2]:
            st.markdown(box_wrapper_open('neutral'), unsafe_allow_html=True)
            st.markdown('**🎯 目標 + 停損**')
            st.markdown(f'<div style="font-size:12px;color:#c9d1d9;padding:2px 0;">📌 現價：<b>{_p2:.2f}</b></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:12px;color:{TRAFFIC_GREEN};padding:2px 0;">🎯 初步目標（策略3 一比一對稱）：<b>{_target1:.2f}</b></div>', unsafe_allow_html=True)
            _sl_hard = round(_p2 * 0.93, 2)
            _sl_ma20 = round(_ma20 * 0.99, 2)
            _dist_hard = round((_p2 - _sl_hard) / _p2 * 100, 1) if _p2 else 0
            _dist_ma20 = round((_p2 - _sl_ma20) / _p2 * 100, 1) if _p2 else 0
            _dist_ma5  = round((_p2 - _ma5) / _p2 * 100, 1) if _p2 and _ma5 else 0
            st.markdown(f'<div style="font-size:12px;color:{TRAFFIC_RED};padding:2px 0;">🛑 硬停損(-7%)：<b>{_sl_hard:.2f}</b> <span style="color:#484f58;">（尚差{_dist_hard:.1f}%）</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:12px;color:{TRAFFIC_YELLOW};padding:2px 0;">⚠️ 月線停損：<b>{_sl_ma20:.2f}</b> <span style="color:#484f58;">（尚差{_dist_ma20:.1f}%）</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:12px;color:#58a6ff;padding:2px 0;">📍 5MA停利：<b>{_ma5:.2f}</b> <span style="color:#484f58;">（尚差{_dist_ma5:.1f}%）</span></div>', unsafe_allow_html=True)
            # 加碼點
            if _bull_align and vcp2 and not _vcp_ok:
                _add_pt = round(_hi20_i * 1.01, 2)
                st.markdown(f'<div style="font-size:12px;color:#58a6ff;padding:2px 0;">➕ 加碼點（策略3 突破法）：>{_add_pt:.2f}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # ══ 關鍵價位 K 線圖(停利/停損/支撐壓力直接畫在 K 線上)═════
        try:
            from plotly.subplots import make_subplots
            _kdf = df2.tail(180).copy()
            _fig_kl = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                row_heights=[0.78, 0.22], vertical_spacing=0.03,
            )
            _open_s = _kdf['open'] if 'open' in _kdf.columns else _kdf['close']
            _fig_kl.add_trace(go.Candlestick(
                x=_kdf.index, open=_open_s,
                high=_kdf['high'], low=_kdf['low'], close=_kdf['close'],
                increasing_line_color='#da3633', decreasing_line_color='#2ea043',
                name='K線', showlegend=False,
            ), row=1, col=1)
            _ma20s = _kdf['MA20'] if 'MA20' in _kdf.columns else df2['close'].rolling(20).mean().tail(len(_kdf))
            _ma100s = _kdf['MA100'] if 'MA100' in _kdf.columns else df2['close'].rolling(100).mean().tail(len(_kdf))
            _fig_kl.add_trace(go.Scatter(x=_kdf.index, y=_ma20s,
                line=dict(color='#FF69B4', width=1.4), name='MA20'), row=1, col=1)
            _fig_kl.add_trace(go.Scatter(x=_kdf.index, y=_ma100s,
                line=dict(color='#00CED1', width=1.4), name='MA100'), row=1, col=1)
            if 'volume' in _kdf.columns:
                _vc = ['#da3633' if c >= o else '#2ea043'
                       for c, o in zip(_kdf['close'], _open_s)]
                _fig_kl.add_trace(go.Bar(x=_kdf.index, y=_kdf['volume'],
                    marker_color=_vc, name='量', showlegend=False), row=2, col=1)
            # 9 條關鍵價位水平線
            _add_pt_v = locals().get('_add_pt')
            _hlines = [
                (tp2_p,    '#58a6ff', 'dash',    f'停利2 +10% {tp2_p:.2f}'),
                (tp1_p,    TRAFFIC_GREEN, 'dash',    f'停利1 +5% {tp1_p:.2f}'),
                (hi20_p,   '#f0883e', 'dot',     f'壓力 {hi20_p:.2f}'),
                (_target1, '#2ea043', 'dashdot', f'初步目標 {_target1:.2f}'),
                (_ma5,     '#FFD700', 'solid',   f'5MA {_ma5:.2f}'),
                (lo20_p,   '#1f6feb', 'dot',     f'支撐 {lo20_p:.2f}'),
                (_sl_ma20, '#8b949e', 'dot',     f'月線停損 {_sl_ma20:.2f}'),
                (sl_p,     TRAFFIC_RED, 'dash',    f'停損 -8% {sl_p:.2f}'),
                (_sl_hard, '#a40e26', 'dashdot', f'硬停損 -7% {_sl_hard:.2f}'),
            ]
            if _add_pt_v:
                _hlines.append((_add_pt_v, '#a371f7', 'dashdot', f'加碼點 >{_add_pt_v:.2f}'))
            for _y, _c, _ds, _txt in _hlines:
                if _y and _y > 0:
                    _fig_kl.add_hline(
                        y=_y, line=dict(color=_c, width=1, dash=_ds),
                        annotation_text=_txt, annotation_position='top left',
                        annotation_font=dict(color=_c, size=10),
                        row=1, col=1,
                    )
            _fig_kl.update_layout(
                title=dict(text=f'{sid2} {name2} K線 + 關鍵價位（停利/停損/支撐壓力）',
                           font=dict(size=13)),
                height=460, margin=dict(l=10, r=10, t=40, b=10),
                template='plotly_dark', showlegend=True,
                legend=dict(orientation='h', yanchor='bottom', y=1.02,
                            x=1, xanchor='right', font=dict(size=10)),
                xaxis_rangeslider_visible=False,
            )
            _fig_kl.update_yaxes(title_text='價格', row=1, col=1)
            _fig_kl.update_yaxes(title_text='量', row=2, col=1)
            st.plotly_chart(_fig_kl, use_container_width=True,
                            config={'displayModeBar': False})
        except Exception as _kl_err:
            st.caption(f'⚠️ K 線繪製失敗：{_kl_err}')

    else:
        st.info('載入個股資料後顯示進出場訊號')
