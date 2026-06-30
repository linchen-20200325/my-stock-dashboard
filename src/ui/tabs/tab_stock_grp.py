"""TAB 比較 × 排行（多股比較 / 多因子排行 / 汰弱留強）— 從 app.py 抽出（PR P2-B Phase 5-B）

依賴策略
========
- Top-level: streamlit
- 函式內 late import: 27 個依賴（含 app.py 內部 helper 與外部模組函式），
  避免循環 import（tab_stock_grp.py ← app.py ← tab_stock_grp.py）。

呼叫端
======
- app.py: `with tab_stock_grp: render_stock_grp()`
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from src.ui.tabs.tab_helpers import (
    format_condition_emoji,
    parse_cash_flow_ratio,
)


def render_stock_grp():
    # ─ Late imports(避免循環 import)─
    import pandas as pd
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.config import FINMIND_TOKEN  # noqa: F401  (some sub-features may use)
    # 外部模組
    from src.services import analyze_financial_health
    from src.services import build_structured_summary_prompt
    from src.services.stock_grp_service import get_news_for as _fetch_news_for  # R1 v18.405
    # app.py 內部 helper
    from app import gemini_call, parse_stocks
    # v18.405 R1:L3 wrapper 統一,移除原 try/except 雙 path 不一致行為
    from src.services.stock_grp_service import get_financial_statements as fetch_financial_statements

    st.markdown("""<div style="padding:6px 0 4px;">
<span style="font-size:20px;font-weight:900;color:#e6edf3;">📊 比較 × 排行</span>
<span style="font-size:11px;color:#484f58;margin-left:10px;">市場狀態 · 多股比較 · 多因子排行 · 汰弱留強 · 最終建議</span>
</div>""", unsafe_allow_html=True)

    # ══ ① 市場狀態快覽(Batch 7-1 v18.413:抽至 stock_grp_sections.section_market_status)══
    from src.ui.tabs.stock_grp_sections import render_market_status_section
    render_market_status_section()

    # ══ ② 輸入多檔代碼 ══════════════════════════════════════════
    with st.container(border=True):
        t3c1, t3c2 = st.columns([4, 1])
        with t3c1:
            multi_input = st.text_area(
                '輸入多檔代碼（逗號/空格/換行，最多10檔）',
                value='2330 2454 2317 2382 3017 2308 2303 2376 6669 3661',
                height=68, key='multi_input',
                placeholder='例：2330 2454 2317 2382 3017')
        with t3c2:
            st.markdown('<br>', unsafe_allow_html=True)
            t3_run_btn = st.button('🚀 批次分析', type='primary',
                                   use_container_width=True, key='t3_run_btn')

    stock_list_t3 = parse_stocks(multi_input)[:10]
    if stock_list_t3:
        st.caption(f'待分析：{", ".join(stock_list_t3)}（共{len(stock_list_t3)}檔）')
    elif t3_run_btn:
        st.warning('⚠️ 請先在上方輸入至少一個有效股票代碼，再按「🚀 批次分析」')

    # ══ 批次分析邏輯(Batch 7-2 v18.414:抽至 stock_grp_sections.section_batch_fetcher)══
    if t3_run_btn and stock_list_t3:
        from src.ui.tabs.stock_grp_sections import run_batch_fetch
        run_batch_fetch(stock_list_t3)

    # ══ 顯示結果(Batch 7-3 v18.415:抽至 stock_grp_sections.section_portfolio_summary)══
    from src.ui.tabs.stock_grp_sections import render_portfolio_summary_section
    _t3_summary = render_portfolio_summary_section(gemini_call_fn=gemini_call)
    results_t3  = _t3_summary.get("results_t3", [])
    score_t3    = _t3_summary.get("score_t3", [])
    risk_alerts = _t3_summary.get("risk_alerts", [])
    _fund_map   = _t3_summary.get("fund_map", {})

    # ══ 批次財報體檢（自動執行）══════════════════════════════════
    if results_t3 and stock_list_t3:
        st.markdown('---')
        st.markdown("""<div style="margin:16px 0 8px;padding:8px 16px;background:linear-gradient(90deg,#d2a8ff18,#0d1117);border-left:4px solid #d2a8ff;border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:#d2a8ff;">🏥 批次財報體檢（策略2）</span><span style="font-size:11px;color:#8b949e;margin-left:8px;">4力1棒子 · 現金流矩陣 · OPM護城河</span></div>""", unsafe_allow_html=True)
        _fh3_trigger = '_'.join(sorted(r.get('stock_id', r.get('代碼','')) for r in results_t3[:10]))
        if st.session_state.get('_fh_t3_last_key') != _fh3_trigger or not st.session_state.get('_fh_t3_results'):
            _asc = as_completed  # L2: 使用頂層已匯入的 as_completed
            _fk3 = FINMIND_TOKEN    # 使用全域 FINMIND_TOKEN（含 os.environ fallback）
            if not _fk3:
                st.warning('⚠️ 未設定 FINMIND_TOKEN，無法抓取財報資料。請在 Streamlit Secrets 或環境變數中設定 FINMIND_TOKEN。')
            _fh3_new = {}
            _prog3 = st.progress(0, text='財報體檢中（純計算，無 AI 呼叫）...')
            def _fh3_fn(sid):
                _fd3 = fetch_financial_statements(sid, _fk3)
                if not _fd3.get('error'):
                    try:
                        from src.services.stock_grp_service import get_5_years_cash_flow as fetch_5_years_cash_flow  # R1 v18.405
                        _fd3['b_item_5y'] = fetch_5_years_cash_flow(sid, _fk3)
                    except Exception:
                        pass
                return sid, analyze_financial_health("", sid, _fd3)
            _done3 = 0
            with ThreadPoolExecutor(max_workers=3) as _ex3:
                _fts3 = {_ex3.submit(_fh3_fn, s): s for s in stock_list_t3}
                for _ft3 in _asc(_fts3):
                    _done3 += 1
                    _prog3.progress(_done3 / len(stock_list_t3), text=f'體檢 {_done3}/{len(stock_list_t3)}...')
                    _sid3, _res3 = _ft3.result()
                    _fh3_new[_sid3] = _res3
            _prog3.empty()
            st.session_state['_fh_t3_results'] = _fh3_new
            st.session_state['_fh_t3_last_key'] = _fh3_trigger

    _fh_t3_cached = st.session_state.get('_fh_t3_results', {})

    if _fh_t3_cached:
        # ── 摘要比較表 ────────────────────────────────────────────
        st.markdown('##### 📊 體檢摘要比較表')
        st.caption('🔰 欄位白話（MJ 策略2）：現金水位＝現金佔總資產（>25%佳）；OCF＝營業現金流（須為正，否則「黑字破產」）；'
                   '負債比＝欠錢比例（<60%穩）；企業DNA＝商業模式類型；雷達均分＝五力體質平均（越高越好）。')
        _fh_rows = []
        for _sid_f, _fd_f in _fh_t3_cached.items():
            _scores_f = _fd_f.get('radar_scores', {})
            _avg_f = round(sum(_scores_f.values()) / len(_scores_f), 1) if _scores_f else 0
            _fh_rows.append({
                '代碼':     _sid_f,
                '現金水位':  _fd_f.get('cash_ratio_status', '?') + ' ' + _fd_f.get('cash_ratio_value', ''),
                'OCF':      _fd_f.get('ocf_status', '?') + ' ' + _fd_f.get('ocf_value', ''),
                '負債比':   _fd_f.get('debt_ratio_status', '?') + ' ' + _fd_f.get('debt_ratio_value', ''),
                '企業DNA':  _fd_f.get('business_model_dna', 'N/A'),
                '雷達均分': _avg_f,
                '紅旗':     '⚠️' if (_fd_f.get('red_flags', 'None') not in ('None', '', None)) else '✅',
            })
        _df_fh = pd.DataFrame(_fh_rows).sort_values('雷達均分', ascending=False).reset_index(drop=True)
        st.dataframe(
            _df_fh, use_container_width=True, hide_index=True,
            column_config={
                '代碼':     st.column_config.TextColumn('代碼',   width='small'),
                '現金水位': st.column_config.TextColumn('現金水位'),
                'OCF':      st.column_config.TextColumn('OCF'),
                '負債比':   st.column_config.TextColumn('負債比'),
                '企業DNA':  st.column_config.TextColumn('企業DNA', width='medium'),
                '雷達均分': st.column_config.NumberColumn('雷達均分', format='%.1f ⭐'),
                '紅旗':     st.column_config.TextColumn('紅旗', width='small'),
            }
        )

        # v18.213 L2：多檔模組比較表（鏡像 Fund L1 expander → 合併表 pattern）
        # ── 經營能力多檔比較表 ───────────────────────────────────
        _op_rows = []
        for _sid_o, _fd_o in _fh_t3_cached.items():
            _oper_o = _fd_o.get('operating_module', {}) or {}
            if not _oper_o or _fd_o.get('error'):
                continue
            _op_rows.append({
                '代碼':     _sid_o,
                'DSO 應收': _oper_o.get('DSO', 'N/A'),
                'DIO 存貨': _oper_o.get('DIO', 'N/A'),
                'DPO 應付': _oper_o.get('DPO', 'N/A'),
                '翻桌率':   _oper_o.get('Asset_Turnover', 'N/A'),
                '完整循環': _oper_o.get('Complete_Cycle', 'N/A'),
                '現金缺口': _oper_o.get('Cash_Gap_Days', 'N/A'),
            })
        if _op_rows:
            st.markdown('##### ⚙️ 經營能力多檔比較（MJ DSO/DIO/DPO）')
            _df_op = pd.DataFrame(_op_rows)
            st.dataframe(
                _df_op, use_container_width=True, hide_index=True,
                column_config={
                    '代碼':     st.column_config.TextColumn('代碼', width='small'),
                    'DSO 應收': st.column_config.TextColumn('DSO 應收'),
                    'DIO 存貨': st.column_config.TextColumn('DIO 存貨'),
                    'DPO 應付': st.column_config.TextColumn('DPO 應付'),
                    '翻桌率':   st.column_config.TextColumn('翻桌率'),
                    '完整循環': st.column_config.TextColumn('完整循環'),
                    '現金缺口': st.column_config.TextColumn('現金缺口'),
                }
            )

        # ── 獲利能力多檔比較表 ───────────────────────────────────
        _pf_rows = []
        for _sid_p, _fd_p in _fh_t3_cached.items():
            _prof_p = _fd_p.get('profitability_module', {}) or {}
            if not _prof_p or _fd_p.get('error'):
                continue
            _pf_rows.append({
                '代碼':       _sid_p,
                '毛利率':     _prof_p.get('Gross_Margin', {}).get('Value', 'N/A'),
                '營業利益率': _prof_p.get('Operating_Margin', {}).get('Value', 'N/A'),
                '安全邊際':   _prof_p.get('Margin_Of_Safety', {}).get('Value', 'N/A'),
                '淨利率':     _prof_p.get('Net_Margin', {}).get('Value', 'N/A'),
                'ROE':        _prof_p.get('ROE', {}).get('Value', 'N/A'),
            })
        if _pf_rows:
            st.markdown('##### 💰 獲利能力多檔比較（MJ 5大指標）')
            _df_pf = pd.DataFrame(_pf_rows)
            st.dataframe(
                _df_pf, use_container_width=True, hide_index=True,
                column_config={
                    '代碼':       st.column_config.TextColumn('代碼', width='small'),
                    '毛利率':     st.column_config.TextColumn('毛利率'),
                    '營業利益率': st.column_config.TextColumn('營業利益率', width='medium'),
                    '安全邊際':   st.column_config.TextColumn('安全邊際'),
                    '淨利率':     st.column_config.TextColumn('淨利率'),
                    'ROE':        st.column_config.TextColumn('ROE'),
                }
            )

        # ── 個股詳細展開卡片 ──────────────────────────────────────
        st.markdown('##### 🔍 個股詳細體檢報告')
        for _sid_f, _fd_f in _fh_t3_cached.items():
            _dna_f = _fd_f.get('business_model_dna', '無法判斷')
            _dna_color = (TRAFFIC_GREEN if _dna_f.startswith('A+') else
                          '#2ea043' if _dna_f.startswith('A') else
                          TRAFFIC_YELLOW if _dna_f.startswith('B') else
                          '#f97316' if _dna_f.startswith('C') else
                          TRAFFIC_RED)
            with st.expander(f'🏥 {_sid_f} — DNA: {_dna_f}', expanded=False):
                # 生死燈號
                _gc1, _gc2, _gc3 = st.columns(3)
                _gc1.metric('現金佔總資產', _fd_f.get('cash_ratio_value', 'N/A'),
                            _fd_f.get('cash_ratio_status', '🔴'))
                _gc2.metric('營業活動現金流', _fd_f.get('ocf_value', 'N/A'),
                            _fd_f.get('ocf_status', '🔴'))
                _gc3.metric('負債比率', _fd_f.get('debt_ratio_value', 'N/A'),
                            _fd_f.get('debt_ratio_status', '🔴'))

                # 雷達圖
                _scores_f = _fd_f.get('radar_scores', {})
                if _scores_f:
                    import plotly.graph_objects as go
                    _cats_f = list(_scores_f.keys())
                    _vals_f = list(_scores_f.values()) + [list(_scores_f.values())[0]]
                    _cats_f_closed = _cats_f + [_cats_f[0]]
                    _fig_f = go.Figure(go.Scatterpolar(
                        r=_vals_f, theta=_cats_f_closed,
                        fill='toself', fillcolor='rgba(63,185,80,0.15)',
                        line=dict(color=TRAFFIC_GREEN, width=2),
                        marker=dict(size=6, color=TRAFFIC_GREEN),
                    ))
                    _fig_f.update_layout(
                        polar=dict(
                            radialaxis=dict(range=[0, 100], tickfont=dict(size=9), showticklabels=True),
                            angularaxis=dict(tickfont=dict(size=11)),
                            bgcolor='#0d1117',
                        ),
                        paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
                        showlegend=False, height=280,
                        margin=dict(l=40, r=40, t=20, b=20),
                    )
                    st.plotly_chart(_fig_f, width='stretch',
                                    key=f'radar_t3_{_sid_f}')

                # DNA + OPM
                st.markdown(
                    f'<div style="display:inline-block;background:{_dna_color}22;'
                    f'border:1px solid {_dna_color}66;border-radius:6px;'
                    f'padding:4px 12px;font-size:13px;color:{_dna_color};font-weight:700;">'
                    f'企業DNA：{_dna_f}</div>',
                    unsafe_allow_html=True
                )
                _opm_f = _fd_f.get('opm_data', {})
                if _opm_f:
                    _pay_f = _opm_f.get('payable_days', 0)
                    _rec_f = _opm_f.get('receivable_days', 0)
                    _adv_f = _opm_f.get('advantage', False)
                    if _adv_f:
                        st.success(f'OPM護城河 ✅ 付款天數({_pay_f}天) > 收款天數({_rec_f}天)，具議價優勢')
                    else:
                        st.warning(f'OPM護城河 ⚠️ 付款天數({_pay_f}天) ≤ 收款天數({_rec_f}天)，議價能力待強化')

                # ── 存活能力精細模組（Survival Module）──────────
                _surv_f = _fd_f.get('survival_module', {})
                if _surv_f and not _fd_f.get('error'):
                    st.markdown('**🏥 存活能力精細診斷（MJ 3大生死指標）**')
                    _s_cols = st.columns(3)
                    _status_color = {'Pass': TRAFFIC_GREEN, 'Acceptable': TRAFFIC_YELLOW, 'Fail': TRAFFIC_RED}
                    for _col, (_key, _label) in zip(_s_cols, [
                        ('Cash_Ratio', '💰 氣長不長'),
                        ('DSO_Speed',  '⚡ 收現速度'),
                    ]):
                        _si = _surv_f.get(_key, {})
                        _sc = _status_color.get(_si.get('Status', 'Fail'), TRAFFIC_RED)
                        with _col:
                            st.markdown(
                                f'<div style="background:{_sc}18;border:1px solid {_sc}55;'
                                f'border-radius:8px;padding:10px;text-align:center;">'
                                f'<div style="font-size:11px;color:#8b949e;">{_label}</div>'
                                f'<div style="font-size:18px;font-weight:900;color:{_sc};">{_si.get("Value","N/A")}</div>'
                                f'<div style="font-size:11px;color:{_sc};">{_si.get("Status","?")}</div>'
                                f'<div style="font-size:10px;color:#8b949e;margin-top:4px;">{_si.get("Insight","")}</div>'
                                f'</div>', unsafe_allow_html=True)
                    _r110 = _surv_f.get('Rule_100_100_10', {})
                    _r110_sc = _status_color.get(_r110.get('Status', 'Fail'), TRAFFIC_RED)
                    # 各分項勾叉（門檻：A>100% / B≥100% / C>10%，與 financial_health_engine:416/423/431 對齊）
                    _a_ok = parse_cash_flow_ratio(_r110.get('Cash_Flow_Ratio',''), 100, strict=True)
                    _b_ok = parse_cash_flow_ratio(_r110.get('Cash_Flow_Adequacy',''), 100, strict=False)
                    _c_ok = parse_cash_flow_ratio(_r110.get('Cash_Reinvestment',''), 10, strict=True)
                    with _s_cols[2]:
                        st.markdown(
                            f'<div style="background:{_r110_sc}18;border:1px solid {_r110_sc}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">🔄 100/100/10</div>'
                            f'<div style="font-size:11px;color:#c9d1d9;">'
                            f'A{format_condition_emoji(_a_ok)}{_r110.get("Cash_Flow_Ratio","N/A")} '
                            f'B{format_condition_emoji(_b_ok)}{_r110.get("Cash_Flow_Adequacy","N/A")} '
                            f'C{format_condition_emoji(_c_ok)}{_r110.get("Cash_Reinvestment","N/A")}</div>'
                            f'<div style="font-size:12px;font-weight:700;color:{_r110_sc};">{_r110.get("Status","?")}</div>'
                            f'<div style="font-size:10px;color:#8b949e;margin-top:4px;">{_r110.get("Insight","")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _verdict_f = _surv_f.get('Final_Survival_Verdict', '')
                    if _verdict_f:
                        st.caption(f'🎯 {_verdict_f}')

                # ── 經營能力模組（Operating Module）──────────────
                _oper_f = _fd_f.get('operating_module', {})
                if _oper_f and not _fd_f.get('error'):
                    st.markdown('**⚙️ 經營能力診斷（MJ DSO/DIO/DPO）**')
                    _o4c = st.columns(4)
                    with _o4c[0]:
                        st.metric('DSO 應收天數', _oper_f.get('DSO', 'N/A'))
                    with _o4c[1]:
                        st.metric('DIO 存貨天數', _oper_f.get('DIO', 'N/A'))
                    with _o4c[2]:
                        st.metric('DPO 應付天數', _oper_f.get('DPO', 'N/A'))
                    with _o4c[3]:
                        st.metric('總資產翻桌率', _oper_f.get('Asset_Turnover', 'N/A'))
                    _o2c = st.columns(2)
                    with _o2c[0]:
                        st.markdown(
                            f'<div style="text-align:center;padding:8px;background:#161b22;border-radius:6px;">'
                            f'<div style="font-size:11px;color:#8b949e;">完整循環天數</div>'
                            f'<div style="font-size:18px;font-weight:900;color:#58a6ff;">{_oper_f.get("Complete_Cycle","N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    with _o2c[1]:
                        _ccc_f = str(_oper_f.get('Cash_Gap_Days', '0'))
                        _ccc_num_f = float(''.join(c for c in _ccc_f if c in '0123456789.-') or '0')
                        _ccc_color_f = TRAFFIC_GREEN if _ccc_num_f <= 0 else (TRAFFIC_YELLOW if _ccc_num_f <= 30 else TRAFFIC_RED)
                        _opm_yes_f = _oper_f.get('OPM_Strategy', 'No') == 'Yes'
                        st.markdown(
                            f'<div style="text-align:center;padding:8px;background:#161b22;border-radius:6px;">'
                            f'<div style="font-size:11px;color:#8b949e;">現金缺口天數 {"🏰 OPM護城河" if _opm_yes_f else ""}</div>'
                            f'<div style="font-size:18px;font-weight:900;color:{_ccc_color_f};">{_ccc_f}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _oper_f.get('Verdict'):
                        st.caption(f'💡 {_oper_f["Verdict"]}')

                # ── 獲利能力模組（Profitability Module）─────────
                _prof_f = _fd_f.get('profitability_module', {})
                if _prof_f and not _fd_f.get('error'):
                    st.markdown('**💰 獲利能力診斷（MJ 5大指標）**')
                    _p5f = st.columns(5)
                    _gm_f = _prof_f.get('Gross_Margin', {})
                    _gm_f_ok = _gm_f.get('Status', '') == 'Good'
                    with _p5f[0]:
                        st.markdown(
                            f'<div style="background:{f"{TRAFFIC_GREEN}18" if _gm_f_ok else f"{TRAFFIC_RED}18"};border:1px solid {f"{TRAFFIC_GREEN}55" if _gm_f_ok else f"{TRAFFIC_RED}55"};'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">毛利率</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{TRAFFIC_GREEN if _gm_f_ok else TRAFFIC_RED};">{_gm_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{TRAFFIC_GREEN if _gm_f_ok else TRAFFIC_RED};">{"好生意" if _gm_f_ok else "辛苦"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _om_f = _prof_f.get('Operating_Margin', {})
                    _om_f_ok = _om_f.get('Core_Business_Profitable', 'No') == 'Yes'
                    with _p5f[1]:
                        st.markdown(
                            f'<div style="background:{f"{TRAFFIC_GREEN}18" if _om_f_ok else f"{TRAFFIC_RED}18"};border:1px solid {f"{TRAFFIC_GREEN}55" if _om_f_ok else f"{TRAFFIC_RED}55"};'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">營業利益率</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{TRAFFIC_GREEN if _om_f_ok else TRAFFIC_RED};">{_om_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{TRAFFIC_GREEN if _om_f_ok else TRAFFIC_RED};">{"本業獲利✅" if _om_f_ok else "本業虧損❌"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _mos_f = _prof_f.get('Margin_Of_Safety', {})
                    _mos_f_ok = _mos_f.get('Status', '') == 'Strong'
                    with _p5f[2]:
                        st.markdown(
                            f'<div style="background:{f"{TRAFFIC_GREEN}18" if _mos_f_ok else f"{TRAFFIC_YELLOW}18"};border:1px solid {f"{TRAFFIC_GREEN}55" if _mos_f_ok else f"{TRAFFIC_YELLOW}55"};'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">安全邊際</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{TRAFFIC_GREEN if _mos_f_ok else TRAFFIC_YELLOW};">{_mos_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{TRAFFIC_GREEN if _mos_f_ok else TRAFFIC_YELLOW};">{"抗震極強" if _mos_f_ok else "費用偏高"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _nm_f = _prof_f.get('Net_Margin', {})
                    _nm_f_s = _nm_f.get('Status', '')
                    _nm_f_c = TRAFFIC_GREEN if _nm_f_s == 'Pass' else (TRAFFIC_YELLOW if _nm_f_s == 'Thin Profit' else TRAFFIC_RED)
                    with _p5f[3]:
                        st.markdown(
                            f'<div style="background:{_nm_f_c}18;border:1px solid {_nm_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">稅後淨利率</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{_nm_f_c};">{_nm_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{_nm_f_c};">{_nm_f_s}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _roe_f = _prof_f.get('ROE', {})
                    _roe_f_warn = _roe_f.get('Leverage_Warning', 'None') != 'None'
                    try:
                        _roe_f_num = float(_roe_f.get('Value', '0').replace('%', '').strip())
                    except (ValueError, AttributeError):
                        _roe_f_num = None
                    _roe_f_positive = _roe_f_num is not None and _roe_f_num > 0
                    _roe_f_c = TRAFFIC_YELLOW if _roe_f_warn else (TRAFFIC_GREEN if _roe_f_positive else TRAFFIC_RED)
                    with _p5f[4]:
                        st.markdown(
                            f'<div style="background:{_roe_f_c}18;border:1px solid {_roe_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">ROE</div>'
                            f'<div style="font-size:15px;font-weight:900;color:{_roe_f_c};">{_roe_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:9px;color:{_roe_f_c};">{"⚠️ 高槓桿" if _roe_f_warn else ("✅ 真實獲利" if _roe_f_positive else "❌ 本業虧損")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _prof_f.get('Final_Insight'):
                        st.caption(f'🎯 {_prof_f["Final_Insight"]}')

                # ── 財務結構模組（Financial Structure Module）────
                _fstr_f = _fd_f.get('financial_structure_module', {})
                if _fstr_f and not _fd_f.get('error'):
                    st.markdown('**🏗️ 財務結構診斷（那根棒子 + 以長支長）**')
                    _fsf2c = st.columns(2)
                    _dr_f = _fstr_f.get('Debt_Ratio', {})
                    _dr_f_s = _dr_f.get('Status', '')
                    _dr_f_c = {'Pass': TRAFFIC_GREEN, 'Warning': TRAFFIC_YELLOW, 'Fail': TRAFFIC_RED, 'N/A': '#8b949e'}.get(_dr_f_s, '#8b949e')
                    with _fsf2c[0]:
                        st.markdown(
                            f'<div style="background:{_dr_f_c}18;border:1px solid {_dr_f_c}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">負債佔資產比率</div>'
                            f'<div style="font-size:20px;font-weight:900;color:{_dr_f_c};">{_dr_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_dr_f_c};">'
                            f'{"✅ 穩健" if _dr_f_s=="Pass" else ("⚠️ 偏高" if _dr_f_s=="Warning" else ("🔴 高危" if _dr_f_s=="Fail" else ("🏦 特許行業" if "金融" in _dr_f.get("Value","") else "⚪ 資料缺漏")))}'
                            f'</div></div>', unsafe_allow_html=True)
                    _ltf_f = _fstr_f.get('Long_Term_Funding_Ratio', {})
                    _ltf_f_s = _ltf_f.get('Status', '')
                    _ltf_f_c = TRAFFIC_GREEN if _ltf_f_s == 'Pass' else ('#8b949e' if _ltf_f_s == 'N/A' else TRAFFIC_RED)
                    _ltf_f_label = ('✅ 資金配置正確' if _ltf_f_s == 'Pass'
                                    else ('⚪ 資料不足' if _ltf_f_s == 'N/A'
                                          else '🔴 短債長投危機'))
                    with _fsf2c[1]:
                        st.markdown(
                            f'<div style="background:{_ltf_f_c}18;border:1px solid {_ltf_f_c}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">以長支長比率</div>'
                            f'<div style="font-size:20px;font-weight:900;color:{_ltf_f_c};">{_ltf_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_ltf_f_c};">'
                            f'{_ltf_f_label}'
                            f'</div></div>', unsafe_allow_html=True)
                    if _fstr_f.get('Final_Insight'):
                        st.caption(f'🏗️ {_fstr_f["Final_Insight"]}')

                # ── 償債能力模組（Solvency Module）─────────────
                _solv_f = _fd_f.get('solvency_module', {})
                if _solv_f and not _fd_f.get('error'):
                    st.markdown('**🛡️ 短期償債能力（MJ 300/150 嚴格標準）**')
                    _sv_f_v = _solv_f.get('Final_Solvency_Verdict', '')
                    _sv_f_pass = 'Pass' in _sv_f_v
                    _sv_f_exc  = 'Exception' in _sv_f_v
                    _sv_f_bc   = TRAFFIC_GREEN if _sv_f_pass and not _sv_f_exc else (TRAFFIC_YELLOW if _sv_f_exc else TRAFFIC_RED)
                    _sv_f_icon = '✅' if _sv_f_pass and not _sv_f_exc else ('⚡' if _sv_f_exc else '🔴')
                    st.markdown(
                        f'<div style="background:{_sv_f_bc}18;border:1px solid {_sv_f_bc}55;'
                        f'border-radius:8px;padding:6px 12px;margin-bottom:6px;">'
                        f'<span style="font-size:12px;font-weight:700;color:{_sv_f_bc};">'
                        f'{_sv_f_icon} {_sv_f_v}</span></div>', unsafe_allow_html=True)
                    _is_dso_exc_f  = "條件B：天天收現" in _sv_f_v
                    _is_cash_exc_f = "條件A：現金充足" in _sv_f_v
                    _is_any_exc_f  = _is_dso_exc_f or _is_cash_exc_f
                    _cr_thresh_f   = 150 if _is_dso_exc_f else (100 if _is_cash_exc_f else 300)
                    _cr_label_f    = (f'流動比率（保命符放寬 >{_cr_thresh_f}%）'
                                      if _is_any_exc_f else '流動比率 >300%')
                    _svf2c = st.columns(2)
                    for _col_s, (_key_s, _label_s) in zip(_svf2c, [
                        ('Current_Ratio', _cr_label_f),
                        ('Quick_Ratio',   '速動比率 >150%'),
                    ]):
                        _si_f = _solv_f.get(_key_s, {})
                        _si_f_s = _si_f.get('Status', '')
                        if _key_s == 'Current_Ratio' and _is_any_exc_f:
                            try:
                                _cr_f_num = float(_si_f.get('Value', '0').replace('%', '').strip())
                                if _cr_f_num > _cr_thresh_f:
                                    _si_f_c, _si_f_s = TRAFFIC_GREEN, f'Pass（保命符 >{_cr_thresh_f}%）'
                                else:
                                    _si_f_c = TRAFFIC_RED
                            except (ValueError, AttributeError):
                                _si_f_c = TRAFFIC_GREEN if 'Pass' in _si_f_s else TRAFFIC_RED
                        else:
                            _si_f_c = TRAFFIC_GREEN if 'Pass' in _si_f_s else TRAFFIC_RED
                        with _col_s:
                            st.markdown(
                                f'<div style="background:{_si_f_c}18;border:1px solid {_si_f_c}55;'
                                f'border-radius:8px;padding:8px;text-align:center;">'
                                f'<div style="font-size:10px;color:#8b949e;">{_label_s}</div>'
                                f'<div style="font-size:18px;font-weight:900;color:{_si_f_c};">{_si_f.get("Value","N/A")}</div>'
                                f'<div style="font-size:10px;color:{_si_f_c};">{_si_f_s}</div>'
                                f'</div>', unsafe_allow_html=True)
                    if _is_dso_exc_f:
                        st.info('🔍 收現行業保命符（DSO ≤ 15天，流動比率門檻 >150%）')
                    elif _is_cash_exc_f:
                        st.info('💰 現金充足保命符（現金佔總資產 >25%，流動比率門檻 >100%）')
                    if _solv_f.get('Final_Insight'):
                        st.caption(f'🛡️ {_solv_f["Final_Insight"]}')

                # ── 綜合診斷模組（Advanced Diagnostic Module）────
                _adv_f = _fd_f.get('advanced_diagnostic_module', {})
                if _adv_f and not _fd_f.get('error'):
                    st.markdown('**🔬 綜合診斷與避雷（跨表勾稽）**')
                    _adf3c = st.columns(3)
                    # 盈餘品質
                    _eq_f = _adv_f.get('Earnings_Quality', {})
                    _eq_f_s = _eq_f.get('Status', '')
                    _eq_f_c = TRAFFIC_GREEN if _eq_f_s == 'Pass' else (TRAFFIC_RED if _eq_f_s == 'Fail' else '#8b949e')
                    with _adf3c[0]:
                        st.markdown(
                            f'<div style="background:{_eq_f_c}18;border:1px solid {_eq_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">盈餘含金量</div>'
                            f'<div style="font-size:16px;font-weight:900;color:{_eq_f_c};">{_eq_f.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_eq_f_c};">{"✅ 真金白銀" if _eq_f_s=="Pass" else ("🔴 紙上富貴" if _eq_f_s=="Fail" else "N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 雙高危機
                    _dh_f = _adv_f.get('Double_High_Warning', '')
                    _dh_f_c = TRAFFIC_RED if 'Triggered' in _dh_f else (TRAFFIC_GREEN if 'Clear' in _dh_f else '#8b949e')
                    with _adf3c[1]:
                        st.markdown(
                            f'<div style="background:{_dh_f_c}18;border:1px solid {_dh_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">雙高危機</div>'
                            f'<div style="font-size:13px;font-weight:900;color:{_dh_f_c};">{"🔴 觸發！" if "Triggered" in _dh_f else ("✅ 安全" if "Clear" in _dh_f else "⬜ N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 企業 DNA
                    _dna_f = _adv_f.get('Business_DNA', 'N/A')
                    _dna_f_c = TRAFFIC_GREEN if 'A+' in _dna_f else (TRAFFIC_RED if '瀕死' in _dna_f else '#58a6ff')
                    with _adf3c[2]:
                        st.markdown(
                            f'<div style="background:{_dna_f_c}18;border:1px solid {_dna_f_c}55;'
                            f'border-radius:8px;padding:8px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">企業 DNA</div>'
                            f'<div style="font-size:11px;font-weight:900;color:{_dna_f_c};">{_dna_f}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _adv_f.get('Final_Verdict'):
                        st.caption(f'🔬 {_adv_f["Final_Verdict"]}')

                # AI 診斷
                _insight_f = _fd_f.get('ai_insight', '')
                if _insight_f:
                    st.markdown(
                        f'<div style="background:#161b22;border-left:3px solid {TRAFFIC_GREEN};'
                        f'padding:10px 14px;border-radius:0 6px 6px 0;'
                        f'font-size:13px;color:#c9d1d9;margin-top:8px;">'
                        f'🤖 {_insight_f}</div>',
                        unsafe_allow_html=True
                    )

                # 紅旗
                _flags_f = _fd_f.get('red_flags', 'None')
                if _flags_f and _flags_f not in ('None', ''):
                    st.error(f'🚩 紅旗警示：{_flags_f}')
                else:
                    st.success('✅ 未發現財報紅旗異常')

    # ══ 📊 MJ 趨勢分數（v18.189）+ 🎯 三階段濾網（v19.58）═══════════
    # v18.223 一鍵化：吃 batch 跑完時鎖定的 codes（t3_batch_codes），自動跑 MJ + picker + AI。
    # 不再依賴 stock_list_t3（避免 textarea 改動觸發重跑），改 textarea 後須按「批次分析」才更新。
    _batch_codes = st.session_state.get('t3_batch_codes')
    if _batch_codes:
        _bc_list = list(_batch_codes)
        _render_mj_trend_section(_bc_list, auto_run=True)
        _render_stage_picker_section(_bc_list, auto_run=True)
    elif stock_list_t3:
        st.info('💡 上方按「🚀 批次分析」會自動串跑 MJ 趨勢分數 + 三階段濾網 + AI 三型建議。')

    # ── 🤖 AI 投資組合綜合判讀(v18.327 PR-B 搬至最下方 — Tab 三層化下層)──
    # 設計:讀 raw data 區(③④⑤ 多因子 / 汰弱 + 體檢 + MJ 趨勢 / 三階段)所有指標 →
    # 結構化 prompt → Gemini 判讀。位於 Tab 最下方,確保 user 看完所有資料後才看 AI。
    if results_t3:
        st.markdown('---')
        st.markdown("""<div style="margin:16px 0 8px;padding:8px 16px;background:linear-gradient(90deg,#76e3ea18,#0d1117);border-left:4px solid #76e3ea;border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:#76e3ea;">🤖 AI 投資組合綜合判讀</span><span style="font-size:11px;color:#8b949e;margin-left:8px;">台股資深基金經理人 · 強弱排序 · 汰弱留強 · 風險診斷</span></div>""", unsafe_allow_html=True)
        _t3ai_key = 't3_port_' + '_'.join(sorted(r.get('stock_id', r.get('代碼','')) for r in results_t3[:10]))
        _t3ai_cached = st.session_state.get(_t3ai_key, '')
        _t3ai_c1, _t3ai_c2 = st.columns([3, 1])
        with _t3ai_c1:
            _t3ai_btn = st.button('🤖 生成 AI 投資組合分析報告', key='t3_ai_gen', type='primary')
        with _t3ai_c2:
            if st.button('🔄 重新生成', key='t3_ai_regen'):
                st.session_state.pop(_t3ai_key, None)
                st.rerun()
        if _t3ai_btn:
            _sc_map3 = {s.get('stock_id'): s for s in score_t3}
            _port_lines = []
            for _rp in results_t3:
                _sid_p = _rp.get('stock_id', _rp.get('代碼',''))
                _nm_p  = _rp.get('stock_name', _rp.get('名稱', _sid_p))
                _ht_p  = _rp.get('_health', 0)
                _sc_p  = _rp.get('total', _rp.get('健康度', 0))
                _fd_p  = _fund_map.get(_sid_p, {})
                _fhp   = _fh_t3_cached.get(_sid_p, {})
                _dna_p = _fhp.get('business_model_dna', 'N/A') if _fhp else 'N/A'
                _fb_p  = _rp.get('foreign_buy', 0) or 0
                _rsi_p = _rp.get('rsi', 'N/A')
                _ma_p  = '多頭排列' if (_rp.get('ma_above', 0) or 0) >= 2 else '空頭排列'
                _vcp_p = 'VCP突破' if _rp.get('vcp_signal') else '未突破'
                _scf   = _sc_map3.get(_sid_p, {})
                try:
                    _dim_p = (f" 五維(趨{_scf.get('trend',0):.0f}/動{_scf.get('momentum',0):.0f}/籌{_scf.get('chip',0):.0f}"
                              f"/量{_scf.get('volume',0):.0f}/RS{_scf.get('rs_score',50):.0f})") if _scf else ''
                except (TypeError, ValueError):
                    _dim_p = ''
                _rad_p = _fhp.get('radar_scores', {}) if _fhp else {}
                _rad_avg_p = f"{sum(_rad_p.values())/len(_rad_p):.1f}" if _rad_p else '-'
                # v18.349 PR-O1:單位「張」(SSOT data_loader.py:286 /1000 後),原 /1e8「億」是錯誤假設元的舊 bug
                _port_lines.append(
                    f"[{_sid_p} {_nm_p}] 健康度={_ht_p:.0f} 評分={_sc_p:.0f}{_dim_p} | "
                    f"技術: 均線={_ma_p} RSI={_rsi_p} {_vcp_p} | "
                    f"籌碼: 外資近20日{'買超' if _fb_p>0 else '賣超'}{abs(_fb_p):,.0f}張 | "
                    f"基本面: EPS={_fd_p.get('近4季EPS','-')} 毛利={_fd_p.get('毛利率%','-')}% "
                    f"殖利率={_fd_p.get('殖利率%','-')} SQ品質={_fd_p.get('SQ評分','-')} "
                    f"FGMS={_fd_p.get('FGMS','-')} P/B={_fd_p.get('P/B評價','-')} | "
                    f"財報體檢: DNA={_dna_p} 現金水位={_fhp.get('cash_ratio_value','-') if _fhp else '-'} "
                    f"OCF={_fhp.get('ocf_value','-') if _fhp else '-'} 負債比={_fhp.get('debt_ratio_value','-') if _fhp else '-'} 雷達均分={_rad_avg_p}"
                )
            _reg_p = st.session_state.get('mkt_info', {}).get('regime', 'neutral')
            _reg_txt_p = '多頭市場（積極操作）' if _reg_p == 'bull' else ('空頭市場（縮減部位）' if _reg_p == 'bear' else '震盪整理（謹慎觀望）')
            _exp_p = st.session_state.get('macro_state', {}).get('exposure_limit_pct', 'N/A')
            # ── 依綜合評分排出強弱順序（重用上方已算好的資料）──────────
            _ranked_t3 = sorted(
                results_t3,
                key=lambda _r: _r.get('total', _r.get('健康度', 0)) or 0,
                reverse=True,
            )
            _strong_lines = []
            for _ri, _rr in enumerate(_ranked_t3, 1):
                _sid_r = _rr.get('stock_id', _rr.get('代碼', ''))
                _nm_r  = _rr.get('stock_name', _rr.get('名稱', _sid_r))
                _sc_r  = _rr.get('total', _rr.get('健康度', 0)) or 0
                _ht_r  = _rr.get('_health', 0) or 0
                _ma_r  = '均線多頭排列' if (_rr.get('ma_above', 0) or 0) >= 2 else '均線空頭排列'
                _fb_r  = _rr.get('foreign_buy', 0) or 0
                # v18.349 PR-O1:單位「張」(同上),原 /1e8「億」是錯誤假設元的舊 bug
                _strong_lines.append(
                    f"第{_ri}名 [{_sid_r} {_nm_r}] 綜合評分={_sc_r:.0f} 健康度={_ht_r:.0f} | "
                    f"{_ma_r}、外資近20日{'買超' if _fb_r > 0 else '賣超'}{abs(_fb_r):,.0f}張"
                )
            _strong_str = '\n'.join(_strong_lines) if _strong_lines else '（沒有可排序的股票）'
            # ── 風險診斷字串（大盤格局 + 建議上限 + 系統風控警示）──────
            _risk_str = (
                f"目前大盤格局：{_reg_txt_p}\n"
                f"系統建議的持股上限：{_exp_p}%\n"
                "系統風控警示：\n"
                + ('\n'.join(f'⚠️ {_a}' for _a in risk_alerts) if risk_alerts else '（目前沒有觸發任何風控警示）')
            )
            # ── 時事新聞：抓組合中評分最高的 1~2 檔（重用排序結果）──────
            _news_blocks = []
            for _rn in _ranked_t3[:2]:
                _sid_news = _rn.get('stock_id', _rn.get('代碼', ''))
                _nm_news  = _rn.get('stock_name', _rn.get('名稱', _sid_news))
                if not _sid_news:
                    continue
                _nblk = _fetch_news_for(_sid_news, _nm_news, 3)
                if _nblk:
                    _news_blocks.append(f'【{_sid_news} {_nm_news}】\n{_nblk}')
            _t3_news_str = '\n\n'.join(_news_blocks) if _news_blocks else None
            _t3ai_sections = [
                {'name': '這個組合裡有哪些股票、各檔現在的體質',
                 'data': '\n'.join(_port_lines)},
                {'name': '哪幾檔比較強、哪幾檔在拖後腿',
                 'data': _strong_str},
                {'name': '這個組合有沒有押太集中、現在風險在哪',
                 'data': _risk_str},
            ]
            _t3ai_prompt = build_structured_summary_prompt(
                subject_title='我的個股組合',
                sections=_t3ai_sections,
                news_text=_t3_news_str,
                overall_question='這個組合整體狀況如何、要不要調整、最該注意什麼風險。',
            )
            with st.spinner('AI 基金經理人分析中（約 30 秒）...'):
                _t3ai_result = gemini_call(_t3ai_prompt, max_tokens=2000)
            st.session_state[_t3ai_key] = _t3ai_result
        if _t3ai_cached:
            st.markdown(_t3ai_cached)
        elif not _t3ai_btn:
            st.caption('▲ 點擊上方按鈕，AI 將生成投資組合強弱排序矩陣與汰弱留強建議。')


def _render_stage_picker_section(stock_list: list[str], *,
                                  auto_run: bool = False) -> None:
    """v19.58 個股組合內三階段濾網 — 直接拿 stock_list_t3 為 candidates，共用 picker 子函式。

    v18.223：auto_run=True 串接「批次分析」一鍵流程（picker 跳過按鈕直接跑、AI 也自動）。
    與 _render_mj_trend_section 互補：MJ 趨勢分數看「最近 3 月/3 季的進步退步」，
    三階段濾網看「當下是否進場（基本面 9 項 ＋ 籌碼技術 6 項 ＋ AI 三型建議）」。
    共用 data_loader.fetch_financial_statements + financial_health_engine（與 MJ 同源）。
    """
    import pandas as pd
    import streamlit as _st  # noqa: F811

    from app import gemini_call  # late import 沿用 render_stock_grp 同模式避循環
    from src.ui.tabs.tab_stock_picker import render_tab_stock_picker

    _st.markdown('---')
    _st.markdown(
        '<div style="margin:16px 0 8px;padding:8px 16px;'
        'background:linear-gradient(90deg,#3b82f622,#0d1117);'
        'border-left:4px solid #3b82f6;border-radius:0 6px 6px 0;">'
        '<span style="font-size:15px;font-weight:900;color:#3b82f6;">'
        '🎯 三階段濾網（基本面 → 籌碼技術 → AI 建議）</span>'
        '<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
        f'直接用上方輸入的 {len(stock_list)} 檔當候選</span></div>',
        unsafe_allow_html=True,
    )

    # 把純代碼 list 轉成 picker 需要的最小 DataFrame
    _df = pd.DataFrame({'代碼': stock_list})
    render_tab_stock_picker(
        gemini_fn=gemini_call,
        candidates=_df,
        source_label='個股組合輸入',
        key_prefix='picker_t3',
        auto_run=auto_run,
    )


def _render_mj_trend_section(stock_list: list[str], *,
                              auto_run: bool = False) -> None:
    """v18.189 個股組合內「MJ 趨勢分數」區塊。

    v18.223：auto_run=True 串接「批次分析」一鍵流程（移除手動按鈕，自動跑全程 + cache）。
    對 stock_list 每檔合議「近 3 月月營收動能」+「近 3 季 MJ 體檢 status delta」
    產出 5 段判定（🚀 強進步 / 📈 進步 / ➖ 中性 / 📉 退步 / 🔻 強退步）。
    月權重 65%（先行）/ 季權重 35%（落後但見品質）。
    """
    import pandas as pd
    from datetime import date

    import streamlit as _st  # noqa: F811 — explicit local alias
    from src.config import FINMIND_TOKEN as _TOK
    from src.services.stock_grp_service import get_financial_statements as fetch_financial_statements  # R1 v18.405
    from src.services import analyze_financial_health
    from src.compute.health import diff_mj_health  # noqa: F401 — used transitively by score
    from src.compute.health import (
        current_finmind_yyyymm,
        list_snapshots,
        load_snapshot,
        save_snapshot,
    )
    from src.compute.health import compute_one_stock_trend, compute_trend_score  # noqa: F401

    _st.markdown('---')
    _st.markdown(
        '<div style="margin:16px 0 8px;padding:8px 16px;'
        'background:linear-gradient(90deg,#22c55e22,#0d1117);'
        'border-left:4px solid #22c55e;border-radius:0 6px 6px 0;">'
        '<span style="font-size:15px;font-weight:900;color:#22c55e;">'
        '📊 MJ 趨勢分數（v18.189）</span>'
        '<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
        '月營收動能 × 季財報體檢 · 65/35 雙頻率合議</span></div>',
        unsafe_allow_html=True,
    )
    _st.caption(
        '🔰 **判定規則**：≥+1.5 🚀 強進步 / +0.5~+1.5 📈 進步 / -0.5~+0.5 ➖ 中性 / '
        '-1.5~-0.5 📉 退步 / ≤-1.5 🔻 強退步。'
        '**月權重高**因月營收 10 日公布（先行指標），季財報 45 天遞延（落後但見獲利品質）。'
        '近 3 季 MJ 不足時自動補抓本季快照。'
    )

    # v18.223：auto_run 模式移除手動按鈕；slider 保留以利使用者觀察/調整權重
    _w_mon = _st.slider(
        '月營收權重',
        min_value=0.4, max_value=0.9, value=0.65, step=0.05,
        key='_mj_trend_w_mon',
        help='月營收動能占比，季財報自動 = 1 - 此值。改動後下次按「批次分析」生效。',
    )

    if not auto_run:
        _st.caption('💡 上方按「🚀 批次分析」自動跑 MJ 趨勢分數（首次 ~30-60s）')
        return

    if not _TOK:
        _st.error('🔴 未設定 `FINMIND_TOKEN` → 無法抓財報與月營收')
        return

    yyyymm_curr = current_finmind_yyyymm(date.today())
    # v18.223 cache 防 rerun 重跑（key 含 codes + 權重 + 當前季）
    _mj_cache_key = (
        f'_mj_trend_rows_{hash(tuple(stock_list))}_'
        f'{round(float(_w_mon) * 100)}_{yyyymm_curr}'
    )
    rows = _st.session_state.get(_mj_cache_key)
    if rows is None:
        rows = []
        prog = _st.progress(0.0, text=f'MJ 趨勢分數中 {len(stock_list)} 檔...')
        for i, sid in enumerate(stock_list, 1):
            prog.progress(i / len(stock_list),
                          text=f'[{i}/{len(stock_list)}] {sid} 趨勢計算中...')
            row = compute_one_stock_trend(
                sid, yyyymm_curr, _TOK, float(_w_mon),
                fetch_financial_statements=fetch_financial_statements,
                analyze_financial_health=analyze_financial_health,
                list_snapshots=list_snapshots,
                load_snapshot=load_snapshot,
                save_snapshot=save_snapshot,
            )
            rows.append(row)
        prog.empty()
        _st.session_state[_mj_cache_key] = rows

    _render_mj_trend_table(rows, pd, _st, yyyymm_curr)


_TREND_SORT_ORDER = {
    'strong_down': 0, 'down': 1, 'neutral': 2,
    'up': 3, 'strong_up': 4, 'error': 5,
}


def _fmt_quarter(yyyymm: str) -> str:
    """202503 → 2025Q1（季底月份對應季）；格式不符回原字串。"""
    s = str(yyyymm or '').strip()
    if len(s) != 6 or not s.isdigit():
        return s or '—'
    q = {'03': 'Q1', '06': 'Q2', '09': 'Q3', '12': 'Q4'}.get(s[4:6], s[4:6])
    return f'{s[:4]}{q}'


def _render_mj_trend_table(rows: list[dict], pd, st_mod, yyyymm_curr: str = '') -> None:
    """渲染結果表（退步在前）+ 統計 KPI。"""
    if not rows:
        return
    cnt = {k: 0 for k in _TREND_SORT_ORDER}
    for r in rows:
        cnt[r['label_code']] = cnt.get(r['label_code'], 0) + 1
    cols = st_mod.columns(5)
    cols[0].metric('🔻 強退步', cnt.get('strong_down', 0))
    cols[1].metric('📉 退步', cnt.get('down', 0))
    cols[2].metric('➖ 中性', cnt.get('neutral', 0))
    cols[3].metric('📈 進步', cnt.get('up', 0))
    cols[4].metric('🚀 強進步', cnt.get('strong_up', 0))

    # v18.199 ── 📊 快照新鮮度條（MJ 季財報分來自哪季 — 防補抓失敗靜默沿用舊季）──
    _fresh = sum(1 for r in rows if r.get('snap_stale') is False)
    _stale = sum(1 for r in rows if r.get('snap_stale') is True)
    _missing = sum(1 for r in rows if r.get('snap_stale') is None)
    if _stale == 0 and _missing == 0:
        _fc, _ft = TRAFFIC_GREEN, '🟢 全部最新'
    elif _fresh == 0:
        _fc, _ft = TRAFFIC_RED, '🔴 全部落後或缺'
    else:
        _fc, _ft = TRAFFIC_YELLOW, '🟡 部分落後'
    st_mod.markdown(
        f'<div style="margin:8px 0;padding:8px 14px;border-left:4px solid {_fc};'
        f'background:{_fc}14;border-radius:0 6px 6px 0;font-size:13px;">'
        f'<b style="color:{_fc};">📊 MJ 快照新鮮度</b>　'
        f'📅 應有最新季 <b>{_fmt_quarter(yyyymm_curr)}</b>　'
        f'<span style="color:{_fc};">{_ft}</span>　'
        f'<span style="color:#8b949e;">🟢 最新 {_fresh} ／ 🟡 落後 {_stale} ／ ⬜ 無快照 '
        f'{_missing}（共 {len(rows)} 檔）</span></div>',
        unsafe_allow_html=True,
    )

    def _quarter_cell(r: dict) -> str:
        _ym = r.get('snap_ym') or ''
        if not _ym:
            return '⬜ 無'
        _q = _fmt_quarter(_ym)
        return f'🟡 {_q}（舊）' if r.get('snap_stale') else f'🟢 {_q}'

    rows_sorted = sorted(rows, key=lambda r: _TREND_SORT_ORDER.get(r['label_code'], 99))
    df = pd.DataFrame([{
        '代碼': r['sid'],
        '判定': r['label'],
        '綜合分數': round(r['score'], 2),
        '月營收分': round(r['mon_sub'], 2),
        'MJ 季財報分': round(r['mj_sub'], 2),
        '季別': _quarter_cell(r),
        '備註': r['note'].strip().rstrip(';') if r['note'] else '',
    } for r in rows_sorted])
    st_mod.dataframe(df, use_container_width=True, hide_index=True)

    with st_mod.expander('🛠️ 逐檔細節（分子分數推導）', expanded=False):
        for r in rows_sorted:
            st_mod.markdown(f"**{r['sid']}**：{r['label']}（合分 {r['score']:.2f}）")
            st_mod.json({
                'monthly_detail': r.get('mon_detail', {}),
                'mj_detail': r.get('mj_detail', {}),
            })
