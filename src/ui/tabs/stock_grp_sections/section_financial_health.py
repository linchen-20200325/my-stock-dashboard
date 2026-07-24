"""src/ui/tabs/stock_grp_sections/section_financial_health.py — 批次財報體檢
(v18.416 Batch 7-4).

從 tab_stock_grp.py:80-557 抽出。涵蓋:
- 並發抓財報 + 5 年現金流 + analyze_financial_health(ThreadPoolExecutor, max 3)
- 結果快取 st.session_state['_fh_t3_results'] + cache key
- 📊 體檢摘要比較表(現金水位 / OCF / 負債比 / DNA / 雷達均分 / 紅旗)
- ⚙️ 經營能力多檔比較表(DSO / DIO / DPO / 翻桌率)
- 💰 獲利能力多檔比較表(毛利 / 營業利益 / 安全邊際 / 淨利 / ROE)
- 🔍 個股詳細體檢報告(逐檔 expander,內含 5 子模組:
  生死燈號 / 雷達圖 / 存活模組 / 經營模組 / 獲利模組 / 財務結構 / 償債能力 / 綜合診斷)

§8.2 layer:L5 UI Tab section helper(🔴 高風險:約 470 LOC,
跨 L1 fetch / L3 service / plotly 圖表 + 巢狀 expander)。

對外 API:
- render_financial_health_section(*, stock_list, results_t3, finmind_token) -> dict
  回傳 _fh_t3_cached(同時寫 session_state['_fh_t3_results']),供下游 AI section 用。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from src.services import analyze_financial_health
from src.services.stock_grp_service import (
    get_5_years_cash_flow as fetch_5_years_cash_flow,
    get_financial_statements as fetch_financial_statements,
)
from src.ui.tabs.tab_helpers import format_condition_emoji, parse_cash_flow_ratio


def render_financial_health_section(
    *,
    stock_list: list[str],
    results_t3: list[dict],
    finmind_token: str,
) -> dict:
    """渲染批次財報體檢區。

    並發抓財報(max 3 thread)→ analyze_financial_health → 三張多檔比較表 +
    逐檔 expander 展開卡(5 子模組)。

    回傳 _fh_t3_cached:dict[stock_id, fd_dict];同時寫 session_state['_fh_t3_results']。
    若上游無 results_t3 → 不渲染,但仍回傳 session_state cache(可能為 {})。
    """
    if results_t3 and stock_list:
        st.markdown('---')
        st.markdown("""<div style="margin:16px 0 8px;padding:8px 16px;background:linear-gradient(90deg,#d2a8ff18,#0d1117);border-left:4px solid #d2a8ff;border-radius:0 6px 6px 0;"><span style="font-size:15px;font-weight:900;color:#d2a8ff;">🏥 批次財報體檢(策略2)</span><span style="font-size:11px;color:#8b949e;margin-left:8px;">4力1棒子 · 現金流矩陣 · OPM護城河</span></div>""", unsafe_allow_html=True)
        _fh3_trigger = '_'.join(sorted(r.get('stock_id', r.get('代碼','')) for r in results_t3[:10]))
        if st.session_state.get('_fh_t3_last_key') != _fh3_trigger or not st.session_state.get('_fh_t3_results'):
            if not finmind_token:
                st.warning('⚠️ 未設定 FINMIND_TOKEN,無法抓取財報資料。請在 Streamlit Secrets 或環境變數中設定 FINMIND_TOKEN。')
            _fh3_new = {}
            _prog3 = st.progress(0, text='財報體檢中(純計算,無 AI 呼叫)...')
            def _fh3_fn(sid):
                _fd3 = fetch_financial_statements(sid, finmind_token)
                if not _fd3.get('error'):
                    try:
                        _fd3['b_item_5y'] = fetch_5_years_cash_flow(sid, finmind_token)
                    except Exception:
                        pass
                return sid, analyze_financial_health("", sid, _fd3)
            _done3 = 0
            with ThreadPoolExecutor(max_workers=3) as _ex3:
                _fts3 = {_ex3.submit(_fh3_fn, s): s for s in stock_list}
                for _ft3 in as_completed(_fts3):
                    _done3 += 1
                    _prog3.progress(_done3 / len(stock_list), text=f'體檢 {_done3}/{len(stock_list)}...')
                    _sid3, _res3 = _ft3.result()
                    _fh3_new[_sid3] = _res3
            _prog3.empty()
            st.session_state['_fh_t3_results'] = _fh3_new
            st.session_state['_fh_t3_last_key'] = _fh3_trigger

    _fh_t3_cached = st.session_state.get('_fh_t3_results', {})

    if _fh_t3_cached:
        _render_summary_table(_fh_t3_cached)
        _render_operating_compare(_fh_t3_cached)
        _render_profitability_compare(_fh_t3_cached)
        _render_per_stock_detail(_fh_t3_cached)

    return _fh_t3_cached


def _render_summary_table(fh_cached: dict) -> None:
    """📊 體檢摘要比較表(現金水位 / OCF / 負債比 / DNA / 雷達均分 / 紅旗)。"""
    st.markdown('##### 📊 體檢摘要比較表')
    st.caption('🔰 欄位白話(老師 策略2):現金水位＝現金佔總資產(>25%佳);OCF＝營業現金流(須為正,否則「黑字破產」);'
               '負債比＝欠錢比例(<60%穩);企業DNA＝商業模式類型;雷達均分＝五力體質平均(越高越好)。')
    _fh_rows = []
    for _sid_f, _fd_f in fh_cached.items():
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


def _render_operating_compare(fh_cached: dict) -> None:
    """⚙️ 經營能力多檔比較表(老師 DSO/DIO/DPO)。"""
    _op_rows = []
    for _sid_o, _fd_o in fh_cached.items():
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
        st.markdown('##### ⚙️ 經營能力多檔比較(老師 DSO/DIO/DPO)')
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


def _render_profitability_compare(fh_cached: dict) -> None:
    """💰 獲利能力多檔比較表(老師 5大指標)。"""
    _pf_rows = []
    for _sid_p, _fd_p in fh_cached.items():
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
        st.markdown('##### 💰 獲利能力多檔比較(老師 5大指標)')
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


def _render_per_stock_detail(fh_cached: dict) -> None:
    """🔍 個股詳細體檢報告 — 逐檔 expander,內含 7 子模組。"""
    st.markdown('##### 🔍 個股詳細體檢報告')
    for _sid_f, _fd_f in fh_cached.items():
        _dna_f = _fd_f.get('business_model_dna', '無法判斷')
        _dna_color = (TRAFFIC_GREEN if _dna_f.startswith('A+') else
                      '#2ea043' if _dna_f.startswith('A') else
                      TRAFFIC_YELLOW if _dna_f.startswith('B') else
                      '#f97316' if _dna_f.startswith('C') else
                      TRAFFIC_RED)
        with st.expander(f'🏥 {_sid_f} — DNA: {_dna_f}', expanded=False):
            _render_vital_signs(_fd_f)
            _render_radar_chart(_fd_f, _sid_f)
            _render_dna_opm(_fd_f, _dna_f, _dna_color)
            _render_survival_module(_fd_f)
            _render_operating_module(_fd_f)
            _render_profitability_module(_fd_f)
            _render_financial_structure_module(_fd_f)
            _render_solvency_module(_fd_f)
            _render_advanced_diagnostic(_fd_f)
            _render_ai_insight_and_flags(_fd_f)


def _render_vital_signs(fd: dict) -> None:
    """生死燈號 3 metric(現金佔總資產 / OCF / 負債比率)。"""
    _gc1, _gc2, _gc3 = st.columns(3)
    _gc1.metric('現金佔總資產', fd.get('cash_ratio_value', 'N/A'),
                fd.get('cash_ratio_status', '🔴'))
    _gc2.metric('營業活動現金流', fd.get('ocf_value', 'N/A'),
                fd.get('ocf_status', '🔴'))
    _gc3.metric('負債比率', fd.get('debt_ratio_value', 'N/A'),
                fd.get('debt_ratio_status', '🔴'))


def _render_radar_chart(fd: dict, sid: str) -> None:
    """雷達圖(plotly Scatterpolar)。"""
    _scores_f = fd.get('radar_scores', {})
    if not _scores_f:
        return
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
    st.plotly_chart(_fig_f, width='stretch', key=f'radar_t3_{sid}')


def _render_dna_opm(fd: dict, dna: str, dna_color: str) -> None:
    """DNA 標籤 + OPM 護城河判定。"""
    st.markdown(
        f'<div style="display:inline-block;background:{dna_color}22;'
        f'border:1px solid {dna_color}66;border-radius:6px;'
        f'padding:4px 12px;font-size:13px;color:{dna_color};font-weight:700;">'
        f'企業DNA:{dna}</div>',
        unsafe_allow_html=True
    )
    _opm_f = fd.get('opm_data', {})
    if _opm_f:
        _pay_f = _opm_f.get('payable_days', 0)
        _rec_f = _opm_f.get('receivable_days', 0)
        _adv_f = _opm_f.get('advantage', False)
        if _adv_f:
            st.success(f'OPM護城河 ✅ 付款天數({_pay_f}天) > 收款天數({_rec_f}天),具議價優勢')
        else:
            st.warning(f'OPM護城河 ⚠️ 付款天數({_pay_f}天) ≤ 收款天數({_rec_f}天),議價能力待強化')


def _render_survival_module(fd: dict) -> None:
    """存活能力精細模組(老師 3 大生死指標)。"""
    _surv_f = fd.get('survival_module', {})
    if not _surv_f or fd.get('error'):
        return
    st.markdown('**🏥 存活能力精細診斷(老師 3大生死指標)**')
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
    # 各分項勾叉(門檻:A>100% / B≥100% / C>10%,與 financial_health_engine:416/423/431 對齊)
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


def _render_operating_module(fd: dict) -> None:
    """經營能力模組(DSO/DIO/DPO + 翻桌率 + CCC + OPM)。"""
    _oper_f = fd.get('operating_module', {})
    if not _oper_f or fd.get('error'):
        return
    st.markdown('**⚙️ 經營能力診斷(老師 DSO/DIO/DPO)**')
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


def _render_profitability_module(fd: dict) -> None:
    """獲利能力模組(老師 5 大指標)。"""
    _prof_f = fd.get('profitability_module', {})
    if not _prof_f or fd.get('error'):
        return
    st.markdown('**💰 獲利能力診斷(老師 5大指標)**')
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


def _render_financial_structure_module(fd: dict) -> None:
    """財務結構模組(那根棒子 + 以長支長)。"""
    _fstr_f = fd.get('financial_structure_module', {})
    if not _fstr_f or fd.get('error'):
        return
    st.markdown('**🏗️ 財務結構診斷(那根棒子 + 以長支長)**')
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


def _render_solvency_module(fd: dict) -> None:
    """償債能力模組(老師 300/150 嚴格 + 保命符例外)。"""
    _solv_f = fd.get('solvency_module', {})
    if not _solv_f or fd.get('error'):
        return
    st.markdown('**🛡️ 短期償債能力(老師 300/150 嚴格標準)**')
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
    _cr_label_f    = (f'流動比率(保命符放寬 >{_cr_thresh_f}%)'
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
                    _si_f_c, _si_f_s = TRAFFIC_GREEN, f'Pass(保命符 >{_cr_thresh_f}%)'
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
        st.info('🔍 收現行業保命符(DSO ≤ 15天,流動比率門檻 >150%)')
    elif _is_cash_exc_f:
        st.info('💰 現金充足保命符(現金佔總資產 >25%,流動比率門檻 >100%)')
    if _solv_f.get('Final_Insight'):
        st.caption(f'🛡️ {_solv_f["Final_Insight"]}')


def _render_advanced_diagnostic(fd: dict) -> None:
    """綜合診斷模組(盈餘品質 / 雙高 / DNA)。"""
    _adv_f = fd.get('advanced_diagnostic_module', {})
    if not _adv_f or fd.get('error'):
        return
    st.markdown('**🔬 綜合診斷與避雷(跨表勾稽)**')
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
            f'<div style="font-size:13px;font-weight:900;color:{_dh_f_c};">{"🔴 觸發!" if "Triggered" in _dh_f else ("✅ 安全" if "Clear" in _dh_f else "⬜ N/A")}</div>'
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


def _render_ai_insight_and_flags(fd: dict) -> None:
    """AI 診斷文字 + 紅旗警示。"""
    _insight_f = fd.get('ai_insight', '')
    if _insight_f:
        st.markdown(
            f'<div style="background:#161b22;border-left:3px solid {TRAFFIC_GREEN};'
            f'padding:10px 14px;border-radius:0 6px 6px 0;'
            f'font-size:13px;color:#c9d1d9;margin-top:8px;">'
            f'🤖 {_insight_f}</div>',
            unsafe_allow_html=True
        )
    # 紅旗
    _flags_f = fd.get('red_flags', 'None')
    if _flags_f and _flags_f not in ('None', ''):
        st.error(f'🚩 紅旗警示:{_flags_f}')
    else:
        st.success('✅ 未發現財報紅旗異常')
