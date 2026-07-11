"""src/ui/tabs/macro/section_short.py — Section 6 短線急殺桶(F-7.1 B-2 抽出)。

⚡ 全市場健康度 × 騰落指標(ADL)+ 國際市場列。

closure params(explicit pass,因原 render_tab_macro 內 local var):
- load_heavy: bool   渲染權重控制(降階模式時跳過部分繪圖)
- tw: dict           tw 台股原資料(fetched)
- tw_s: dict         tw 計算 stats(來自 calc_stats)
"""
from __future__ import annotations

import os

import plotly.graph_objects as go
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.signal_thresholds import BREADTH_BULL_PCT, BREADTH_NEUTRAL_PCT
from src.config import FINMIND_TOKEN  # noqa: F401
from src.ui.render.macro_ui_components import section_header
from src.ui.render.ui_widgets import kpi, teacher_conclusion
from src.ui.tabs.macro.helpers import add_danger_hlines, render_macro_bucket_summary_bar


def render_section_short(_load_heavy: bool, tw: dict, tw_s: dict) -> None:
    """渲染短線急殺桶(原 tab_macro line 3421-3741)。"""
    # ══════════════════════════════════════════════════════════════
    # SECTION 九: 總經 AI 投資決策分析（五維度綜合研判）
    # ══════════════════════════════════════════════════════════════
    from shared.macro_buckets import bucket_group_banner_html as _bgb  # v18.310 桶群組 banner
    st.markdown(_bgb('short', 3), unsafe_allow_html=True)
    st.markdown(section_header('五','⚡ 短線急殺｜📊 全市場健康度 × 騰落指標（ADL）','📉'),unsafe_allow_html=True)
    render_macro_bucket_summary_bar('short')  # v18.314 桶輕量總結 bar
    _adl5 = st.session_state.get('cl_data', {}).get('adl')
    _mkt5 = st.session_state.get('mkt_info', {})
    # v18.450 hotfix:df_adl 只在 132 行(_load_heavy 補救分支)被賦值,Python 因此把它
    # 視為整個函式的區域變數 —— 但 72 行早於該賦值就讀取,production 炸
    # UnboundLocalError。此處補初始化(與 _adl5 同一 session_state 來源),132 行的
    # 補救邏輯仍可在需要時覆寫。
    df_adl = _adl5
    if _adl5 is not None and not _adl5.empty:
        _ac5 = next((c for c in _adl5.columns if 'adl' in c.lower()), _adl5.columns[0])
        _adl_vals5 = _adl5[_ac5].dropna().tail(5)
        _adl_up5 = (len(_adl_vals5) >= 2 and float(_adl_vals5.iloc[-1]) > float(_adl_vals5.iloc[0]))
        # 優先從 tw_s 取當日漲跌 %（比 mkt_info 更可靠），fallback 到 mkt5
        _twii_s5 = tw_s.get('台股加權指數') or {}
        _twii_p5 = _twii_s5.get('pct') if isinstance(_twii_s5, dict) and _twii_s5.get('pct') is not None \
                   else (_mkt5.get('台股加權指數', {}).get('pct', None) if isinstance(_mkt5.get('台股加權指數'), dict) else None)
        # Bug fix：_twii_p5=0 或 None 時，依 ADL 方向判斷（不能落入空頭 else）
        _idx_up = (_twii_p5 is not None and _twii_p5 > 0)
        _idx_dn = (_twii_p5 is not None and _twii_p5 < 0)
        if _adl_up5 and _idx_up:
            _a5c = '廣泛多頭：ADL↑+指數↑，市場健康，全面性上漲'
            _a5a = '可積極持股'
        elif _adl_up5 and _idx_dn:
            _a5c = 'ADL↑但指數跌，廣度健康，或為技術回調非崩盤'
            _a5a = '可留意回調後逢低布局'
        elif _adl_up5:
            # ADL上升但指數資料不足/持平 → 廣度健康，中性偏多
            _a5c = 'ADL↑廣度健康，指數方向待確認（持平或資料更新中）'
            _a5a = '維持現有部位，等待指數方向確認'
        elif not _adl_up5 and _idx_up:
            _a5c = '⚠️ 背離警訊：指數漲但ADL↓，行情由少數權值股撐，不可追'
            _a5a = '謹慎，不追高，等待廣度改善'
        else:
            _a5c = '廣泛賣壓：ADL↓+指數↓，空頭格局，降低部位'
            _a5a = '降低持倉，保護本金'
        _a5_ind = f'ADL近5日{"↑上升" if _adl_up5 else "↓下降"}'
    else:
        _a5c = 'ADL數據尚未載入，請點擊「🚀 一鍵更新全部數據」'
        _a5a = ''
        _a5_ind = 'ADL騰落線'
    st.markdown(teacher_conclusion('宏爺', _a5_ind, _a5c, _a5a), unsafe_allow_html=True)
    st.caption('💡 衡量「多少股票真的在漲」—— 分數越高 = 廣度越健康；ADL 趨勢 vs 指數是否背離是最重要的觀察點')
    # 如果是代理資料，顯示提示
    _adl_chk = st.session_state.get('cl_data',{}).get('adl')
    if _adl_chk is not None and not _adl_chk.empty:
        if 'is_proxy' in _adl_chk.columns and _adl_chk['is_proxy'].any():
            st.caption('⚠️ 目前顯示 yfinance 代理數據（TWSE 上漲/下跌家數暫時無法取得），上漲佔比為估算值')
    
    # ── 宏爺策略 + 上漲佔比動態結論（移至 Section 標題下方）──────────
    if df_adl is not None and not df_adl.empty:
        st.caption('💡 宏爺策略：ADL 趨勢比今日漲跌更重要，要看「方向」是否與指數一致。')
        _ar2 = df_adl.iloc[-1]
        _ad2 = _ar2.get('ad', 0)
        _ratio2 = _ar2.get('ad_ratio', 50)
        _adl2 = _ar2.get('adl', 0)
        _ma2  = df_adl['adl_ma20'].dropna().iloc[-1] if df_adl['adl_ma20'].notna().any() else _adl2
        _twii_pct2 = tw_s.get('台股加權指數', {}).get('pct', 0) if tw_s.get('台股加權指數') else 0
        _ad_ratio_int  = int(round(_ratio2)) if _ratio2 else 0
        _adl_above_ma  = (_adl2 is not None and _ma2 is not None and _adl2 > _ma2)
        _adl_below_ma  = (_adl2 is not None and _ma2 is not None and _adl2 < _ma2)
        _adl_concl = []
        if _twii_pct2 > 0.5 and _ad2 < -50:
            _adl_concl.append(
                f'🔴 指數漲({_twii_pct2:+.1f}%) 但 AD值({_ad2:+,}) < -50 → '
                f'背離！僅少數大型股撐盤，廣度萎縮，建議準備降倉')
        elif _twii_pct2 < -0.5 and _ad2 > 50:
            _adl_concl.append(
                f'🟢 指數跌({_twii_pct2:+.1f}%) 但 AD值({_ad2:+,}) > 50 → '
                f'底部擴散！多數股票止跌，可留意逢低布局機會')
        elif _ratio2 >= 70 and _adl_above_ma:
            _adl_concl.append(
                f'✅ 上漲佔比 {_ad_ratio_int}%（>70%）+ ADL在MA上 → '
                f'全面多頭，市場廣度充足，可積極持股')
        elif _ratio2 >= 60 and _adl_above_ma:
            _adl_concl.append(
                f'✅ 上漲佔比 {_ad_ratio_int}%（60~70%）+ ADL在MA上 → '
                f'多頭健康，可持股偏多，注意量能配合')
        elif _ratio2 < 40 and _adl_below_ma:
            _adl_concl.append(
                f'🔴 上漲佔比 {_ad_ratio_int}%（<40%）+ ADL破MA → '
                f'廣泛賣壓，空頭格局，建議降倉保守')
        elif _ratio2 < 40:
            _adl_concl.append(
                f'⚠️ 上漲佔比 {_ad_ratio_int}%（<40%）→ '
                f'廣度不足，多數股票弱勢，不宜追高')
        elif _adl_below_ma:
            _adl_concl.append(
                f'⚠️ 上漲佔比 {_ad_ratio_int}% 但 ADL跌破MA → '
                f'趨勢轉弱訊號，觀望等方向確認')
        else:
            _adl_concl.append(
                f'⚪ 上漲佔比 {_ad_ratio_int}%（40~60%）→ '
                f'廣度中性，盤整格局，等待方向選擇')
        for _ac in _adl_concl:
            _ac_c = ('#2ea043' if '✅' in _ac or '可進攻' in _ac
                     else '#da3633' if '🔴' in _ac or '警告' in _ac
                     else TRAFFIC_YELLOW if '⚠️' in _ac else '#388bfd')
            _ac_dot = '🟢' if '✅' in _ac else ('🔴' if '🔴' in _ac else ('🟡' if '⚠️' in _ac else '⚪'))
            _ac_clean = _ac.lstrip('✅⚠️🔴⚪').strip()
            st.markdown(
                f'<div style="border-left:5px solid {_ac_c};background:#0d1117;'
                f'padding:9px 14px;border-radius:0 8px 8px 0;margin:5px 0;">'
                f'<span style="font-size:14px;font-weight:900;color:{_ac_c};">{_ac_dot} {_ac_clean}</span><br>'
                f'<span style="font-size:10px;color:#484f58;">詳細判讀 → 「策略手冊」Tab</span>'
                f'</div>',
                unsafe_allow_html=True
            )
    
    # ── ADL 即時補救（TWSE 封鎖時自動觸發 FinMind）─────────────────
    if _load_heavy and (df_adl is None or df_adl.empty):
        _adl_ph = st.empty()
        _adl_ph.info('⏳ ADL 資料載入中...')
        try:
            from src.services import fetch_adl as _fa
            _tok_rt = os.environ.get('FINMIND_TOKEN','') or FINMIND_TOKEN
            _df_rt  = _fa(days=60, token=_tok_rt)
            if _df_rt is not None and not _df_rt.empty:
                df_adl = _df_rt
                _cd_u  = st.session_state.get('cl_data', {})
                _cd_u['adl'] = df_adl
                st.session_state['cl_data'] = _cd_u
        except Exception as _adl_e:
            print(f'[ADL補救] {_adl_e}')
        finally:
            _adl_ph.empty()
    
    if df_adl is not None and not df_adl.empty:
        _adl_last   = df_adl.iloc[-1]
        _adl_up     = int(_adl_last.get('up', 0))
        _adl_down   = int(_adl_last.get('down', 0))
        _adl_ad     = int(_adl_last.get('ad', 0))
        _adl_ratio  = float(_adl_last.get('ad_ratio', 50))
        _adl_val    = float(_adl_last.get('adl', 0))
        _adl_ma20   = df_adl['adl_ma20'].dropna().iloc[-1] if df_adl['adl_ma20'].notna().any() else _adl_val
        _adl_trend  = '↑' if _adl_val > _adl_ma20 else '↓'
        _adl_color  = '#da3633' if _adl_ad > 0 else '#2ea043'
        _adl_signal = ('🟢 廣度擴張，多頭健康' if _adl_ad > 200
                       else ('🟡 廣度收窄，市場整理' if _adl_ad >= -100
                       else '🔴 廣度萎縮，主力集中在少數股'))
        # 背離偵測（指數上漲但 ADL 下跌 = 警告）
        _twii_pct = tw_s.get('台股加權指數', {}).get('pct', 0) if tw_s.get('台股加權指數') else 0
        _divergence = _twii_pct > 0.5 and _adl_ad < -50
    
        # KPI 卡片
        _adl_cols = st.columns(4)
        with _adl_cols[0]:
            st.markdown(kpi('今日上漲家數', f'{_adl_up:,}', '上漲股票總數', TRAFFIC_GREEN, '#0d2818'), unsafe_allow_html=True)
        with _adl_cols[1]:
            st.markdown(kpi('今日下跌家數', f'{_adl_down:,}', '下跌股票總數', TRAFFIC_RED, '#2a0d0d'), unsafe_allow_html=True)
        with _adl_cols[2]:
            st.markdown(kpi('AD值（今日）', f'{_adl_ad:+,}', '漲家－跌家', _adl_color, '#0d1117'), unsafe_allow_html=True)
        with _adl_cols[3]:
            # 廣度健康評分：0-100（對應全市場健康度）
            _breadth_score = round(_adl_ratio)  # 直接用上漲佔比%當分數
            _bs_color = TRAFFIC_GREEN if _breadth_score>=BREADTH_BULL_PCT else (TRAFFIC_YELLOW if _breadth_score>=BREADTH_NEUTRAL_PCT else TRAFFIC_RED)
            _bs_label = '🟢 廣度健康' if _breadth_score>=BREADTH_BULL_PCT else ('🟡 中性' if _breadth_score>=BREADTH_NEUTRAL_PCT else '🔴 廣度不足')
            st.markdown(kpi('全市場健康度', f'{_breadth_score}分', _bs_label, _bs_color, '#0d1117'), unsafe_allow_html=True)
            # 同步更新旌旗指數（如果尚未由 ADL 計算）
            # v19.84:刪 pct20/60/120/240 捏造鍵(同 jingqi_calc,§1 寧缺勿假 + 0 讀者)
            if not st.session_state.get('jingqi_info'):
                st.session_state['jingqi_info'] = {
                    'avg': _adl_ratio, 'pos': ('80~100%' if _adl_ratio>=BREADTH_BULL_PCT else ('50~70%' if _adl_ratio>=BREADTH_NEUTRAL_PCT else '20~40%')),
                    'regime': ('bull' if _adl_ratio>=BREADTH_BULL_PCT else ('neutral' if _adl_ratio>=BREADTH_NEUTRAL_PCT else 'bear')),
                    'color': _bs_color, 'label': _bs_label, 'source': 'ADL廣度',
                }
    
        # 信號提示
        _sig_color = TRAFFIC_GREEN if _adl_ad > 200 else (TRAFFIC_YELLOW if _adl_ad >= -100 else TRAFFIC_RED)
        st.markdown(
            f'<div style="background:#0d1117;border-left:4px solid {_sig_color};border-radius:0 8px 8px 0;'
            f'padding:10px 14px;margin:8px 0;">'
            f'<span style="color:{_sig_color};font-weight:700;">{_adl_signal}</span>'
            f'　｜　騰落線 {_adl_val:,.0f} {_adl_trend} MA20({_adl_ma20:,.0f})'
            + (f'　⚠️ <span style="color:{TRAFFIC_RED};font-weight:700;">背離警告：指數漲但廣度萎縮！</span>' if _divergence else '') +
            '</div>', unsafe_allow_html=True)
    
        # 騰落線圖（ADL + MA20 + 上漲佔比）
        _fig_adl = go.Figure()
        # 上漲佔比柱狀圖（背景）
        _ratio_colors = ['rgba(63,185,80,0.4)' if v >= 50 else 'rgba(248,81,73,0.4)' for v in df_adl['ad_ratio'].fillna(50)]
        _fig_adl.add_trace(go.Bar(
            x=df_adl['date'], y=df_adl['ad_ratio'],
            name='上漲佔比%', marker_color=_ratio_colors,
            yaxis='y2', opacity=0.5,
            hovertemplate='%{x|%Y-%m-%d}<br>上漲佔比: %{y:.1f}%<extra></extra>'
        ))
        # ADL 線
        _fig_adl.add_trace(go.Scatter(
            x=df_adl['date'], y=df_adl['adl'],
            name='騰落線 ADL', line=dict(color='#58a6ff', width=2.5),
            hovertemplate='%{x|%Y-%m-%d}<br>ADL: %{y:,.0f}<extra></extra>'
        ))
        # ADL MA20
        _fig_adl.add_trace(go.Scatter(
            x=df_adl['date'], y=df_adl['adl_ma20'],
            name='ADL MA20', line=dict(color='#ffd700', width=1.5, dash='dot'),
            hovertemplate='%{x|%Y-%m-%d}<br>MA20: %{y:,.0f}<extra></extra>'
        ))
        # 零軸
        _fig_adl.add_hline(y=0, line_dash='dash', line_color='#484f58', opacity=0.5)
        # v18.284：上漲佔比（y2 軸 0-100）危險標準線 — 50 黃 / 35 紅（廣度崩），讀 SSOT
        add_danger_hlines(_fig_adl, 'adl', yref='y2')
        _fig_adl.update_layout(
            title=dict(text='台股騰落線（ADL）— 衡量多數股票是否真的在漲', font=dict(color='#8b949e', size=13)),
            height=320, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
            font=dict(color='white', size=11),
            legend=dict(orientation='h', y=-0.15, bgcolor='rgba(0,0,0,0)'),
            margin=dict(l=10, r=10, t=40, b=10),
            hovermode='x unified',
            yaxis=dict(title='ADL 累積值', gridcolor='#21262d', zeroline=True),
            yaxis2=dict(title='上漲佔比%', gridcolor='rgba(0,0,0,0)',
                        overlaying='y', side='right', range=[0, 100], showgrid=False),
            xaxis=dict(gridcolor='#21262d', tickformat='%m/%d'),
        )
        st.plotly_chart(_fig_adl, width='stretch', config={'displayModeBar': False})
    
        # ── ADL vs 加權指數 雙軸背離圖 ──────────────────────────
        _twii_data = tw.get('台股加權指數')
        if _twii_data is not None and not _twii_data.empty:
            _cc_t = 'close' if 'close' in _twii_data.columns else 'Close'
            if _cc_t in _twii_data.columns:
                # 對齊日期
                _adl_dates = df_adl['date'].dt.date.tolist()
                _twii_sub = _twii_data.copy()
                _twii_sub.index = _twii_sub.index.date if hasattr(_twii_sub.index, 'date') else _twii_sub.index
                _twii_aligned = [float(_twii_sub.loc[d, _cc_t]) if d in _twii_sub.index else None
                                 for d in _adl_dates]
                _fig_div = go.Figure()
                _fig_div.add_trace(go.Scatter(
                    x=df_adl['date'], y=df_adl['adl'],
                    name='騰落線 ADL', line=dict(color='#58a6ff', width=2),
                    hovertemplate='%{x|%m/%d}<br>ADL: %{y:,.0f}<extra></extra>'
                ))
                _fig_div.add_trace(go.Scatter(
                    x=df_adl['date'], y=_twii_aligned,
                    name='加權指數', line=dict(color='#ffd700', width=2, dash='dot'),
                    yaxis='y2',
                    hovertemplate='%{x|%m/%d}<br>指數: %{y:,.0f}<extra></extra>'
                ))
                # 背離區域標示
                if _divergence:
                    _fig_div.add_annotation(
                        x=df_adl['date'].iloc[-1], y=_adl_val,
                        text='⚠️ 背離警告', showarrow=True, arrowhead=2,
                        font=dict(color=TRAFFIC_RED, size=12), bgcolor='#2a0d0d'
                    )
                _fig_div.update_layout(
                    title=dict(text='🔍 ADL vs 加權指數（看背離是否存在）', font=dict(color='#8b949e', size=12)),
                    height=280, plot_bgcolor='#0e1117', paper_bgcolor='#0e1117',
                    font=dict(color='white', size=10),
                    legend=dict(orientation='h', y=-0.2, bgcolor='rgba(0,0,0,0)'),
                    margin=dict(l=10,r=60,t=40,b=10),
                    hovermode='x unified',
                    yaxis=dict(title='ADL', gridcolor='#21262d'),
                    yaxis2=dict(title='加權指數', overlaying='y', side='right',
                               gridcolor='rgba(0,0,0,0)', showgrid=False),
                    xaxis=dict(gridcolor='#21262d', tickformat='%m/%d'),
                )
                st.plotly_chart(_fig_div, width='stretch', config={'displayModeBar': False})
                if _divergence:
                    st.error('⚠️ 背離警告：大盤指數上漲，但騰落線下跌！代表只有少數權值股在撐盤，市場廣度惡化，要注意風險！')
    
        # 近5日 AD 明細表
        _adl_tbl = df_adl.tail(5)[['date','up','down','ad','ad_ratio','adl']].copy()
        _adl_tbl['date'] = _adl_tbl['date'].dt.strftime('%m/%d')
        _adl_tbl = _adl_tbl.rename(columns={
            'date':'日期','up':'上漲','down':'下跌','ad':'AD值','ad_ratio':'上漲佔比%','adl':'ADL累積'
        }).sort_values('日期', ascending=False)
        st.dataframe(_adl_tbl, use_container_width=True, hide_index=True,
            column_config={
                '上漲佔比%': st.column_config.NumberColumn('上漲佔比%', format='%.1f%%'),
                'ADL累積': st.column_config.NumberColumn('ADL累積', format='%,.0f'),
                'AD值': st.column_config.NumberColumn('AD值', format='%+d'),
            })
    
    
    else:
        _adl_debug = st.session_state.get('adl_debug_msg', '')
        if _adl_debug:
            st.error(f'❌ 騰落指標抓取失敗：{_adl_debug}')
            st.caption('💡 請到 Colab 查看 [ADL] 開頭的輸出訊息')
        else:
            st.info('📡 點擊「🚀 一鍵更新全部數據」載入騰落指標')
        # [Step 4] 備援：即時抓取漲跌家數 — 委派 tw_macro.fetch_twse_breadth()（走 NAS proxy）
        _adl_today_cols = st.columns(3)
        try:
            if not _load_heavy:
                raise RuntimeError('未按一鍵更新，跳過 TWSE breadth 即時抓取')
            from src.data.macro import fetch_twse_breadth
            _bd = fetch_twse_breadth()
            _up_v, _dn_v = _bd.get('adv'), _bd.get('dec')
            if _up_v is not None and _dn_v is not None and (_up_v + _dn_v) > 50:
                _ratio_v = round(_up_v / (_up_v + _dn_v) * 100, 1)
                _col_v = TRAFFIC_GREEN if _ratio_v >= 60 else (TRAFFIC_YELLOW if _ratio_v >= 40 else TRAFFIC_RED)
                with _adl_today_cols[0]:
                    st.markdown(kpi('今日上漲家數', f'{_up_v:,}', '即時TWSE', TRAFFIC_GREEN, '#0d2818'), unsafe_allow_html=True)
                with _adl_today_cols[1]:
                    st.markdown(kpi('今日下跌家數', f'{_dn_v:,}', '即時TWSE', TRAFFIC_RED, '#2a0d0d'), unsafe_allow_html=True)
                with _adl_today_cols[2]:
                    st.markdown(kpi('全市場健康度', f'{_ratio_v:.1f}%',
                                    ('廣度健康' if _ratio_v >= 60 else ('中性' if _ratio_v >= 40 else '廣度不足')),
                                    _col_v, '#0d1117'), unsafe_allow_html=True)
                # 同步旌旗指數（v19.84:刪 pct20/60/120/240 捏造鍵,同 jingqi_calc）
                if not st.session_state.get('jingqi_info'):
                    st.session_state['jingqi_info'] = {
                        'avg': _ratio_v,
                        'pos': ('80~100%' if _ratio_v >= 60 else ('50~70%' if _ratio_v >= 40 else '20~40%')),
                        'regime': ('bull' if _ratio_v >= 60 else ('neutral' if _ratio_v >= 40 else 'bear')),
                        'color': _col_v,
                        'label': ('🟢 多頭積極' if _ratio_v >= 60 else ('🟡 中性均衡' if _ratio_v >= 40 else '🔴 保守防禦')),
                        'source': 'TWSE即時',
                    }
        except Exception as _adl_e:
            # v19.84 §3.3:原裸 pass 補 log(即時 TWSE 廣度為 best-effort 區塊,失敗留跡)
            print(f'[section_short] TWSE 即時廣度區塊失敗: '
                  f'{type(_adl_e).__name__}: {_adl_e}')
    
    st.markdown('<hr style="border-color:#21262d;margin:8px 0;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:10px;color:#484f58;text-transform:uppercase;letter-spacing:1px;margin:4px 0;">🌐 國際市場</div>', unsafe_allow_html=True)
    
