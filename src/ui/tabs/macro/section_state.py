"""src/ui/tabs/macro/section_state.py — Section 2 拐點偵測 + 市場狀態卡(F-7.1 B-S2 抽出)。

📊 整合六大面向 + MK 黃金拐點(v18.169);結論寫入 st.session_state['regime_data']
供其他 tab 共用。

closure params(4 explicit pass):
- _mkt_info: dict | None  market_regime() 結果(從 S1 算出)
- _mkt_placeholder, _tl_placeholder: streamlit placeholder(S1 預留)
- cd: dict  cl_data alias
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from shared.calc_helpers import calc_bias_pct  # R-CALC-3 v18.412
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW  # noqa: F401
from src.config import FINMIND_TOKEN  # noqa: F401
from src.compute.macro import calc_traffic_light  # noqa: F401
from src.ui.tabs.macro.handlers import _render_traffic_light  # noqa: F401


def render_section_state(_mkt_info, _mkt_placeholder, _tl_placeholder, cd) -> None:
    """渲染 §二 拐點偵測 + 市場狀態(原 tab_macro line 2186-2565)。"""
    # ══════════════════════════════════════════════════════════════
    # 拐點偵測系統（整合六大面向 + MK 黃金拐點，v18.169）
    # ══════════════════════════════════════════════════════════════
    if _mkt_info:
        _mi2    = _mkt_info
        _ma60   = _mi2.get('ma60', 0)
        _ma120  = _mi2.get('ma120', 0)
        _ma200  = _mi2.get('ma200', 0)
        _idx2   = _mi2.get('index_price', 0)
        _sigs2  = _mi2.get('signals', [])
        _regime2= _mi2.get('regime','neutral')
        _m1b2   = st.session_state.get('m1b_m2_info', {})
        _bias2  = st.session_state.get('bias_info', {})
        _li2    = st.session_state.get('li_latest')
        _cd2    = st.session_state.get('cl_data', {})
        _tw2    = _cd2.get('tw', {})
        _twd_df = _tw2.get('新台幣匯率')
    
        # ── 計算各項拐點訊號 ─────────────────────────────────────
        pivot_signals = []  # (label, icon, color, detail)
    
        # 1. 技術面：均線方向（MA60/MA120 彎折）
        if _ma60 and _ma120 and _idx2:
            _turn_up   = any('向上彎折' in s for s in _sigs2)
            _turn_down = any('向下' in s and 'MA' in s for s in _sigs2)
            _above60   = _idx2 > _ma60
            _above120  = _idx2 > _ma120
            _above200  = _idx2 > _ma200 if _ma200 else None
            # R-CALC-3 v18.412:乖離率公式 SSOT(calc_bias_pct)
            _d60  = calc_bias_pct(_idx2, _ma60)  or 0.0
            _d120 = calc_bias_pct(_idx2, _ma120) or 0.0
    
            if _turn_up and _above60 and _above120:
                pivot_signals.append(('均線多頭確認','🟢',TRAFFIC_GREEN,
                    f'站上MA60(+{_d60:.1f}%) & MA120(+{_d120:.1f}%) + 均線向上彎折 → 中長線起漲點'))
            elif _turn_up and _above60:
                pivot_signals.append(('均線初步翻多','🟡',TRAFFIC_YELLOW,
                    f'站上MA60(+{_d60:.1f}%) + 向上彎折，待突破MA120({_ma120:,.0f})確認'))
            elif not _above60 and _turn_down:
                pivot_signals.append(('均線空頭確認','🔴',TRAFFIC_RED,
                    f'跌破MA60({_d60:.1f}%) + 均線向下 → 中期起跌訊號'))
            elif _above60 and not _above120:
                pivot_signals.append(('整理區間','⚪','#8b949e',
                    '站上MA60但未過MA120 → 等待方向確認'))
    
        # 2. 乖離率（與台股體質 ±7~10% 門檻）
        if _bias2:
            _b240 = _bias2.get('bias_240', 0)
            _b60  = _bias2.get('bias_60', _bias2.get('bias_20', 0))
            _b20  = _bias2.get('bias_20', 0)
            if _b240 > 10:
                pivot_signals.append(('年線乖離過大','⚠️',TRAFFIC_RED,
                    f'年線乖離 +{_b240:.1f}% > 10% → 頂部拐點區間，考慮減碼'))
            elif _b240 < -10:
                pivot_signals.append(('年線深度低估','💡',TRAFFIC_GREEN,
                    f'年線乖離 {_b240:.1f}% < -10% → 底部拐點區間，考慮布局'))
            if abs(_b20) > 8:
                _bl20 = '過熱' if _b20 > 0 else '超賣'
                pivot_signals.append((f'月線{_bl20}',
                    '⚠️' if _b20 > 0 else '💡',
                    '#da3633' if _b20>0 else '#2ea043',
                    f'月線乖離 {_b20:+.1f}% → 短線{_bl20}修正機率高'))
    
        # 3. M1B-M2（資金面黃金/死亡交叉）
        if _m1b2 and not _m1b2.get('is_proxy'):
            _m1b_y = _m1b2.get('m1b_yoy', 0)
            _m2_y  = _m1b2.get('m2_yoy', 0)
            _diff  = _m1b_y - _m2_y
            if _diff > 0:
                pivot_signals.append(('M1B>M2 黃金交叉','✅',TRAFFIC_GREEN,
                    f'M1B({_m1b_y:.1f}%) > M2({_m2_y:.1f}%) → 資金由定存轉入股市，長線起漲徵兆'))
            elif _diff < -1:
                pivot_signals.append(('M1B<M2 死亡交叉','❌',TRAFFIC_RED,
                    f'M1B({_m1b_y:.1f}%) < M2({_m2_y:.1f}%) → 資金撤離股市，長線起跌警示'))
    
        # 4. 台幣匯率（貶轉升=外資流入，升轉貶=外資撤退）
        if _twd_df is not None and not _twd_df.empty:
            _twd_col = 'close' if 'close' in _twd_df.columns else 'Close'
            if _twd_col in _twd_df.columns and len(_twd_df) >= 10:
                _twd_now   = float(_twd_df[_twd_col].iloc[-1])
                _twd_prev5 = float(_twd_df[_twd_col].iloc[-5])
                _twd_chg   = (_twd_now - _twd_prev5) / _twd_prev5 * 100
                # 注意：TWD=X 是 USD/TWD，數字越小=台幣越升值
                if _twd_chg < -0.5:  # 台幣升值 (匯率數字下降)
                    pivot_signals.append(('台幣升值','✅',TRAFFIC_GREEN,
                        f'台幣近5日升值 {abs(_twd_chg):.1f}% → 外資熱錢流入，指數底部反彈訊號'))
                elif _twd_chg > 0.5:  # 台幣貶值 (匯率數字上升)
                    pivot_signals.append(('台幣貶值','⚠️',TRAFFIC_YELLOW,
                        f'台幣近5日貶值 {_twd_chg:.1f}% → 外資撤退觀察，留意資金流出風險'))
    
        # 5. 外資期貨 + 散戶比（先行指標）
        if _li2 is not None and not _li2.empty:
            _last_li = _li2.iloc[-1]
            _fut_net = _last_li.get('外資大小')
            _leek    = _last_li.get('韭菜指數')
            _pcr     = _last_li.get('選PCR')
            if _fut_net is not None:
                _fut_net_v = float(_fut_net)
                if _fut_net_v < -30000:
                    pivot_signals.append(('外資期貨大量空單','🔴',TRAFFIC_RED,
                        f'外資期貨淨空 {abs(_fut_net_v):,.0f}口 > 3萬口 → 頂部起跌訊號'))
                elif _fut_net_v < 0 and abs(_fut_net_v) < 10000:
                    pivot_signals.append(('外資空單縮減','🟡',TRAFFIC_YELLOW,
                        f'外資期貨淨空 {abs(_fut_net_v):,.0f}口（補回中）→ 底部拐點觀察'))
                elif _fut_net_v > 10000:
                    pivot_signals.append(('外資期貨多方','✅',TRAFFIC_GREEN,
                        f'外資期貨淨多 {_fut_net_v:,.0f}口 → 多頭強勢確認'))
            if _leek is not None:
                _leek_v = float(_leek)
                if _leek_v > 20:
                    pivot_signals.append(('散戶極度看多（危險）','⚠️',TRAFFIC_RED,
                        f'韭菜指數 +{_leek_v:.1f}% > 20% → 散戶過熱，頂部拐點警示（反向指標）'))
                elif _leek_v < -20:
                    pivot_signals.append(('散戶極度悲觀（機會）','💡',TRAFFIC_GREEN,
                        f'韭菜指數 {_leek_v:.1f}% < -20% → 散戶極度看空，底部拐點機會（反向指標）'))
    
        # ── 6. 台灣領先指標拐點（景氣對策 / 領先指標 / 外資連續日數）─────
        try:
            from src.data.macro import (
                fetch_ndc_signal_history as _f_ndc_h,
                fetch_ndc_leading_index as _f_ndc_li,
                fetch_foreign_consecutive_days as _f_fi_streak,
            )
            _FMD_TK = st.secrets.get('FINMIND_TOKEN', '') \
                if hasattr(st, 'secrets') else ''
            _ndc_h = st.session_state.get('_ndc_hist_cache')
            if _ndc_h is None:
                _ndc_h = _f_ndc_h(months_back=12, token=_FMD_TK or '')
                st.session_state['_ndc_hist_cache'] = _ndc_h
            _ndc_li = st.session_state.get('_ndc_li_cache')
            if _ndc_li is None:
                _ndc_li = _f_ndc_li(months_back=18, token=_FMD_TK or '')
                st.session_state['_ndc_li_cache'] = _ndc_li
            _fi_st = st.session_state.get('_fi_streak_cache')
            if _fi_st is None:
                _fi_st = _f_fi_streak(days_back=30, token=_FMD_TK or '')
                st.session_state['_fi_streak_cache'] = _fi_st
    
            # 6-A 景氣對策信號拐點
            _inf = (_ndc_h or {}).get('inflection', '')
            _sc, _spv = (_ndc_h or {}).get('score_latest'), (_ndc_h or {}).get('score_prev')
            if '翻多' in _inf:
                pivot_signals.append(('景氣對策連2月翻多','🚀',TRAFFIC_GREEN,
                    f'分數 {_spv}→{_sc} 由跌轉升 → 景氣領先翻揚拐點'))
            elif '翻空' in _inf:
                pivot_signals.append(('景氣對策連2月翻空','⚠️',TRAFFIC_RED,
                    f'分數 {_spv}→{_sc} 由升轉跌 → 景氣動能衰退拐點'))
            elif '連3月上升' in _inf:
                pivot_signals.append(('景氣對策連3月上升','✅',TRAFFIC_GREEN,
                    f'分數穩步上升至 {_sc}/45 → 景氣擴張持續'))
            elif '連3月下降' in _inf:
                pivot_signals.append(('景氣對策連3月下降','❌',TRAFFIC_RED,
                    f'分數連續下滑至 {_sc}/45 → 景氣收縮持續'))
    
            # 6-B 領先指標 6M smoothed change
            _li_inf = (_ndc_li or {}).get('inflection', '')
            _s6m = (_ndc_li or {}).get('smooth6m')
            _ps6m = (_ndc_li or {}).get('prev_s6m')
            if '由負轉正' in _li_inf and _s6m is not None and _ps6m is not None:
                pivot_signals.append(('領先指標 6M 由負轉正','🚀',TRAFFIC_GREEN,
                    f'6M smoothed change：{_ps6m:+.2f}%→{_s6m:+.2f}% → 景氣翻揚黃金拐點'))
            elif '由正轉負' in _li_inf and _s6m is not None and _ps6m is not None:
                pivot_signals.append(('領先指標 6M 由正轉負','⚠️',TRAFFIC_RED,
                    f'6M smoothed change：{_ps6m:+.2f}%→{_s6m:+.2f}% → 景氣轉折下行'))
            elif '持續擴張' in _li_inf and _s6m is not None:
                pivot_signals.append(('領先指標持續擴張','✅',TRAFFIC_GREEN,
                    f'6M smoothed change {_s6m:+.2f}% 維持正值 → 景氣擴張'))
            elif '持續收縮' in _li_inf and _s6m is not None:
                pivot_signals.append(('領先指標持續收縮','❌',TRAFFIC_RED,
                    f'6M smoothed change {_s6m:+.2f}% 維持負值 → 景氣收縮'))
    
            # 6-C 外資連續日數反轉
            _fi_inf = (_fi_st or {}).get('inflection', '')
            _cd = (_fi_st or {}).get('consec_days')
            _ps = (_fi_st or {}).get('prev_streak')
            if '賣→買' in _fi_inf:
                pivot_signals.append(('外資由連賣轉買','🚀',TRAFFIC_GREEN,
                    f'外資連 {-_ps if _ps else 0} 賣後首日翻買 → 籌碼面拐點'))
            elif '買→賣' in _fi_inf:
                pivot_signals.append(('外資由連買轉賣','⚠️',TRAFFIC_RED,
                    f'外資連 {_ps if _ps else 0} 買後首日翻賣 → 籌碼動能減弱'))
            elif '連' in _fi_inf and '買超' in _fi_inf and _cd is not None:
                pivot_signals.append(('外資連續買超','✅',TRAFFIC_GREEN,
                    f'外資已連 {_cd} 日買超 → 籌碼穩健'))
            elif '連' in _fi_inf and '賣超' in _fi_inf and _cd is not None:
                pivot_signals.append(('外資連續賣超','❌',TRAFFIC_RED,
                    f'外資已連 {abs(_cd)} 日賣超 → 籌碼流出警示'))
        except Exception as _e_tp6:
            print(f'[tab_macro/拐點面板6] {type(_e_tp6).__name__}: {_e_tp6}')
    
        # ── 7. MK 黃金拐點（CPI YoY × Fed Funds Rate 雙頂回落）─────────────
        # v18.169：鏡像 fund services/macro_service.py::_detect_inflection
        # 規則：CPI 月降 + Fed Funds 月降/持平 → ⭐ 強訊號（多頭最佳買點）
        # 邏輯純函式集中於 macro_helpers.detect_mk_golden_inflection（可單測）
        try:
            from src.compute.macro import detect_mk_golden_inflection as _det_mk
            _mi_mk = st.session_state.get('macro_info') or {}
            _cpi_mk = _mi_mk.get('us_core_cpi') or {}
            _fed_mk = _mi_mk.get('fed_funds') or {}
            _mk_sig = _det_mk(
                cpi_yoy=_cpi_mk.get('yoy'),
                cpi_prev_yoy=_cpi_mk.get('prev_yoy'),
                fed_rate=_fed_mk.get('current'),
                fed_prev_rate=_fed_mk.get('prev'),
            )
            if _mk_sig is not None:
                pivot_signals.append((
                    _mk_sig['label'], _mk_sig['icon'],
                    _mk_sig['color'], _mk_sig['detail'],
                ))
        except Exception as _e_tp7:
            print(f'[tab_macro/拐點面板7-MK] {type(_e_tp7).__name__}: {_e_tp7}')
    
        # v1.2 暫存供 AI 首席總經分析師讀（章節：拐點訊號摘要）
        st.session_state['_pivot_signals'] = list(pivot_signals)
    
        # ── 綜合評分 & 顯示 ──────────────────────────────────────
        _bull_pts = sum(1 for _,_,c,_ in pivot_signals if c == TRAFFIC_GREEN)
        _bear_pts = sum(1 for _,_,c,_ in pivot_signals if c == TRAFFIC_RED)
        _warn_pts = sum(1 for _,_,c,_ in pivot_signals if c in (TRAFFIC_YELLOW,''))
    
        if _bull_pts > _bear_pts and _bull_pts >= 2:
            _pivot_overall = f'🟢 綜合拐點：{_bull_pts} 個多頭訊號 → 偏向底部起漲'
            _pivot_color   = TRAFFIC_GREEN
        elif _bear_pts > _bull_pts and _bear_pts >= 2:
            _pivot_overall = f'🔴 綜合拐點：{_bear_pts} 個空頭訊號 → 偏向頂部起跌'
            _pivot_color   = TRAFFIC_RED
        else:
            _pivot_overall = f'⚪ 訊號分歧：多頭{_bull_pts} vs 空頭{_bear_pts}，方向待確認'
            _pivot_color   = TRAFFIC_YELLOW
    
        # v18.321：🔮 拐點群組 banner（與其他桶一致的分隔條，分組化收尾）
        from shared.macro_buckets import bucket_group_banner_html as _bgb_pv
        st.markdown(_bgb_pv('pivot', 0), unsafe_allow_html=True)
    
        st.markdown(f'<div style="background:#161b22;border-left:4px solid {_pivot_color};'
                    f'border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;'
                    f'font-size:13px;font-weight:600;color:{_pivot_color};">'
                    f'{_pivot_overall}</div>', unsafe_allow_html=True)
    
        # v18.319：六大面向 → verdict 小卡格（比照桶卡片，常駐可見），
        #          完整訊號敘述 + 判斷參考收進 Raw expander（要看才打開）。
        st.markdown('##### 📊 拐點詳細分析 — 六大面向 + MK 黃金拐點')
        if pivot_signals:
            _pv_cols = st.columns(3)
            for _pi, (_label, _icon, _color, _detail) in enumerate(pivot_signals):
                with _pv_cols[_pi % 3]:
                    st.markdown(
                        f"<div style='background:#0d1117;border:1px solid #21262d;"
                        f"border-top:3px solid {_color};border-radius:8px;"
                        f"padding:8px 10px;margin:3px 0;min-height:54px;"
                        f"display:flex;align-items:center;'>"
                        f"<span style='color:{_color};font-weight:700;font-size:13px;'>"
                        f"{_icon} {_label}</span></div>", unsafe_allow_html=True)
            with st.expander('🔍 拐點六大面向 — 完整訊號明細 + 判斷參考', expanded=False):
                for _label, _icon, _color, _detail in pivot_signals:
                    st.markdown(
                        f'<div style="background:#0d1117;border-left:3px solid {_color};'
                        f'border-radius:0 6px 6px 0;padding:6px 10px;margin:4px 0;">'
                        f'<span style="color:{_color};font-weight:600;">{_icon} {_label}</span>'
                        f'<br><span style="color:#8b949e;font-size:12px;">{_detail}</span>'
                        f'</div>', unsafe_allow_html=True)
                # 拐點參考表 → 已移至 Tab5 策略手冊
                st.caption('📖 拐點判斷參考表 → 詳見「策略手冊」Tab')
        else:
            st.info('尚無足夠資料計算拐點，請點擊「🚀 一鍵更新全部數據」')
    
        # ── 熱錢深度監測（三角交叉：外資 × 匯率 × 背離偵測）─────────────
        # 拉到 expander 同層 sibling — Streamlit 禁止 expander 巢狀（原 #101 為 bug）
        # ── v1.2 倒掛翻正後 ^TWII 6/12/18M 表現歷史回測 ────────────────
        import os as _os_tw_bt
        _fred_key_tw_bt = (_os_tw_bt.environ.get('FRED_API_KEY') or
                            (st.secrets.get('FRED_API_KEY')
                             if hasattr(st, 'secrets') else None) or '')
        with st.expander(
            '📊 歷史回測：美債倒掛翻正後 ^TWII 6/12/18M 表現',
            expanded=False,
        ):
            try:
                from src.compute.strategy import backtest_twii_turning_points as _bt_twii
                _bt = _bt_twii(_fred_key_tw_bt)
            except Exception as _bt_e:
                _bt = {"source_ok": False, "note": str(_bt_e)[:120],
                       "events": [], "summary": {"n_events": 0},
                       "twii_series": None, "t10y2y_series": None}
            if not _bt.get('source_ok'):
                st.info(f"⚠️ FRED 或 ^TWII 抓取失敗，回測暫不可用。{_bt.get('note','')}")
            elif _bt['summary']['n_events'] == 0:
                st.info(f"近 30 年無符合條件之倒掛翻正事件（{_bt.get('note','')}）")
            else:
                _sm = _bt['summary']
                _bk1, _bk2, _bk3, _bk4, _bk5 = st.columns(5)
                _bk1.metric('事件數', f"{_sm['n_events']}",
                             help=f"完整 18M 窗口：{_sm['n_complete_18m']}")
                _bk2.metric('+6M 中位數',
                             f"{_sm['median_6m']:+.1f}%" if _sm['median_6m'] is not None else '—',
                             delta=f"勝率 {_sm['win_rate_6m']:.0f}%"
                                    if _sm['win_rate_6m'] is not None else None)
                _bk3.metric('+12M 中位數',
                             f"{_sm['median_12m']:+.1f}%" if _sm['median_12m'] is not None else '—',
                             delta=f"勝率 {_sm['win_rate_12m']:.0f}%"
                                    if _sm['win_rate_12m'] is not None else None)
                _bk4.metric('+18M 中位數',
                             f"{_sm['median_18m']:+.1f}%" if _sm['median_18m'] is not None else '—',
                             delta=f"勝率 {_sm['win_rate_18m']:.0f}%"
                                    if _sm['win_rate_18m'] is not None else None)
                _bk5.metric('資料涵蓋',
                             f"{len(_bt['twii_series']):,} 日"
                             if _bt['twii_series'] is not None else '—')
                # 事件清單表
                _ev_df = pd.DataFrame(_bt['events'])
                if not _ev_df.empty:
                    _ev_df['翻正日'] = pd.to_datetime(_ev_df['date']).dt.date
                    _ev_df_disp = _ev_df[['翻正日', 't10y2y_min_pre',
                                            'ret_6m', 'ret_12m', 'ret_18m']].rename(
                        columns={'t10y2y_min_pre': '倒掛最深(%)',
                                 'ret_6m':  '+6M (%)',
                                 'ret_12m': '+12M (%)',
                                 'ret_18m': '+18M (%)'})
                    st.dataframe(_ev_df_disp, use_container_width=True,
                                  hide_index=True, height=240)
                st.caption(
                    '💡 **解讀**：美債 10Y-2Y 倒掛翻正後 6~18 個月內，'
                    '^TWII 歷史中位數正報酬率 = 底部累積期布局訊號；'
                    '但台股與美股相關性 ~0.6，需搭配 NDC 景氣燈號雙重確認。'
                )
    
        if _twd_df is not None and not _twd_df.empty:
            # v18.321：💵 現金流向群組 banner（與其他桶一致的分隔條，分組化收尾）
            from shared.macro_buckets import bucket_group_banner_html as _bgb_cf
            st.markdown(_bgb_cf('cashflow', 0), unsafe_allow_html=True)
            # v18.319：現金流向 Raw（三角交叉 + sliders）預設收合（要看才打開），
            #          比照基金面板「Raw data 縮起來」；互動內容不動。
            with st.expander("💵 熱錢深度監測 — 三角交叉（外資 × 匯率 × 背離）",
                             expanded=False):
                st.caption(
                    "上方「台幣升貶」訊號的深化版：把**外資買賣超**與**台幣匯率**"
                    "做交叉分析，找出「背離」時刻——例如台幣升值但外資沒買，"
                    "代表熱錢可能停泊匯市觀望，往往是行情前奏。"
                )
                try:
                    from src.ui.tabs import render_hot_money_section
                    render_hot_money_section(
                        _twd_df, FINMIND_TOKEN, key_prefix="tab_macro_hm")
                except Exception as _hme:
                    st.error(f"熱錢監測渲染失敗：[{type(_hme).__name__}] {_hme}")
    
    elif not cd:
        with _mkt_placeholder.container():
            st.info('📡 請點擊「🚀 一鍵更新全部數據」載入大盤數據')
    # ── ③ 資料到位後，回填紅綠燈佔位符（修復「未審先判」Bug）────
    # C1-E v18.291:走 section_inputs SSOT(對齊 C1-D 紅綠燈初次計算路徑)
    from src.services import load_section_inputs as _load_si_tl2
    _tl2_inp = _load_si_tl2(st.session_state)
    _tl2_mkt = _tl2_inp.mkt_info or {}
    _tl_final = calc_traffic_light(
        _tl2_mkt,
        _tl2_inp.jingqi_info or {},
        _tl2_inp.cl_data or {},
        _tl2_inp.li_latest,
    )
    _render_traffic_light(_tl_placeholder, _tl_final, _tl2_mkt)
    # v19.62 — 建議持股油門(姿態非開關):總經健康分 → 建議持股區間
    try:
        from src.ui.tabs.macro.section_traffic_light import render_position_throttle
        render_position_throttle(_tl_final)
    except Exception as _e_thr:
        print(f"[position_throttle] {type(_e_thr).__name__}: {_e_thr}")
    # v18.277 — 為何這個顏色?(展開講判讀規則 + 推導,for 新手)
    try:
        from src.ui.tabs import render_traffic_light_explainer
        render_traffic_light_explainer(_tl_final)
    except Exception as _e_exp:
        print(f"[macro_classroom/explainer] {type(_e_exp).__name__}: {_e_exp}")
    if _tl_final:
        st.session_state['warroom_summary'] = {
            'traffic_light': _tl_final['label'],
            'health_score':  _tl_final['health'],
            'regime': _tl2_mkt.get('regime', 'neutral'),
            'market_score':  _tl_final['score'],
            'jingqi_avg':    _tl_final['jqavg'],
            'leek_index':    _tl_final['leek'],
            'foreign_net_bn':_tl_final['fnet'],
            'futures_net':   _tl_final['fut_net'],
            'confidence_pct':_tl_final['conf'],
        }
    
