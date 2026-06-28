"""src/ui/tabs/macro/section_mid.py — Section 4(§八)總經拼圖 v4.0(F-7.1 B-4 抽出)。

📈 中期｜🌐 總經拼圖 v4.0(景氣位階 × 前瞻需求 × 全球風險)

closure params(explicit pass):
- _load_heavy: bool  rendering control flag
- intl_s, tech_s, tw_s: dict  各市場 calc_stats 結果
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW  # noqa: F401
from src.ui.render.macro_ui_components import section_header
from src.ui.render.ui_widgets import kpi, cond_badge, teacher_conclusion
from src.ui.tabs.macro.helpers import add_danger_hlines  # noqa: F401
from src.data.macro import check_macro_alerts, fetch_macro_snapshot, render_macro_alerts


def render_section_mid(_load_heavy: bool, intl_s: dict, tech_s: dict, tw_s: dict) -> None:
    """渲染中期桶(§八 總經拼圖 v4.0,原 tab_macro line 2975-3411)。"""
    # ══════════════════════════════════════════════════════════════
    # SECTION 八: 總經拼圖 v4.0 (景氣位階 × 前瞻需求 × 全球風險)
    # ══════════════════════════════════════════════════════════════
    st.markdown(section_header('八','📈 中期｜🌐 總經拼圖 v4.0（景氣位階 × 前瞻需求 × 全球風險）','🌐'),unsafe_allow_html=True)
    
    # ── 🔰 故事化白話解讀（純疊加；解釋三塊拼圖如何「合在一起看」，非重複各 KPI 副標）──
    with st.expander('🔰 這張「總經拼圖」在拼什麼？三塊怎麼一起看？'):
        st.markdown('''這一區把三種「大環境訊號」拼起來，判斷台股的外部是順風還是逆風：
    
    1. **景氣位階（現在冷熱）** — NDC 景氣燈號：藍燈=景氣冷（衰退）、綠燈=穩定、紅燈=過熱，分數越高景氣越熱。
    2. **前瞻需求（未來動能）** — 外銷訂單 YoY、台灣 PMI，領先實際營收約 1~2 個月；PMI 以 **50 為榮枯線**（>50 擴張、<50 收縮）。
    3. **全球風險（外部壓力）** — 美國核心 CPI、VIX、美債殖利率、美元指數；通膨高或恐慌高 → 外資容易從台股提款。
    
    **怎麼合著看？**
    - 三塊都偏多（景氣穩+訂單成長+風險低）→ 基本面順風，可較積極。
    - 互相打架（如景氣熱但 PMI 轉弱、外銷成長但 CPI 飆高）→ 留意背離，降低部位。
    - 多塊轉空 → 基本面逆風，優先保留現金。
    
    > 💡 這區看的是「中長期基本面」，和最上方的紅綠燈（偏即時多空）互相搭配，不是互相取代。''')
    
    st.divider()
    
    # ── 總經自動警示看板（VIX / CPI / 10Y / DXY / PCR）────────
    if _load_heavy:
        _ma_snap   = fetch_macro_snapshot(
            session_macro=st.session_state.get('macro_info'),
            session_li=st.session_state.get('li_latest'),
            session_m1b2=st.session_state.get('m1b_m2_info'),
        )
        _ma_alerts = check_macro_alerts(_ma_snap)
        st.session_state['macro_alerts'] = _ma_alerts   # 供 Section 九/十共用
        st.session_state['ma_snap']      = _ma_snap     # 供 tab_stock AI Prompt 引用 VIX/CPI/US10Y/DXY
        render_macro_alerts(_ma_alerts)
    else:
        st.info('📡 點擊「🚀 一鍵更新全部數據」載入總經警示看板')
    
    _macro_info = st.session_state.get('macro_info') or {}
    _m8_ndc   = _macro_info.get('ndc_signal')
    _m8_exp   = _macro_info.get('tw_export')
    _m8_pmi   = _macro_info.get('ism_pmi')
    _m8_cpi   = _macro_info.get('us_core_cpi')
    _m8_fed   = _macro_info.get('fed_funds')  # v18.169: MK 黃金拐點配對指標
    _m8_vix   = _macro_info.get('vix')
    
    # ── Row 1: NDC燈號 | 外銷訂單YoY | 🇹🇼 台灣 PMI ──────────
    _s8c1 = st.columns(3)
    
    with _s8c1[0]:
        if _m8_ndc:
            _sc8   = float(_m8_ndc.get('score', 0))
            _nc8   = (TRAFFIC_RED if _sc8 >= 38 else TRAFFIC_YELLOW if _sc8 >= 32 else
                      TRAFFIC_GREEN if _sc8 >= 23 else '#58a6ff')
            _nl8   = ('🔴 紅燈 過熱' if _sc8 >= 38 else '🟡 黃紅燈 繁榮' if _sc8 >= 32 else
                      '🟢 綠燈 穩定' if _sc8 >= 23 else '🔵 黃藍燈 趨緩' if _sc8 >= 17 else '🔵 藍燈 衰退')
            _nd8   = f" ({_m8_ndc.get('date','')})" if _m8_ndc.get('date') else ''
            _ndc_title8 = 'NDC 景氣燈號'
            st.markdown(kpi(_ndc_title8, f'{_sc8:.0f} 分', f'{_nl8}{_nd8}', _nc8, '#0d1117'), unsafe_allow_html=True)
        else:
            st.markdown(kpi('NDC 景氣燈號', '待取得', '9分藍燈→45分紅燈（StockFeel+MacroMicro）', '#484f58', '#0d1117'), unsafe_allow_html=True)
    
    with _s8c1[1]:
        if _m8_exp:
            _ey8 = _m8_exp.get('yoy', 0)
            _ec8 = TRAFFIC_GREEN if _ey8 > 0 else TRAFFIC_RED
            _el8 = ('✅ 出口動能正成長，基本面有撐' if _ey8 > 0 else
                    ('🔴 外銷連兩月衰退，基本面警示！' if _ey8 < -5 else '⚠️ 外銷轉弱，留意基本面背離'))
            st.markdown(kpi('外銷訂單 YoY', f'{_ey8:+.1f}%', _el8, _ec8, '#0d1117'), unsafe_allow_html=True)
        else:
            st.markdown(kpi('外銷訂單 YoY', '待取得', '領先實際營收 1~2 月', '#484f58', '#0d1117'), unsafe_allow_html=True)
    
    with _s8c1[2]:
        if _m8_pmi:
            _pv8 = _m8_pmi.get('value', 50)
            _pmi_title = '🇹🇼 台灣 PMI'
            _pmi_榮枯 = 50
            _pc8 = TRAFFIC_GREEN if _pv8 >= _pmi_榮枯 else (TRAFFIC_YELLOW if _pv8 >= (_pmi_榮枯-3) else TRAFFIC_RED)
            _pl8 = ('✅ 製造業擴張' if _pv8 >= _pmi_榮枯 else
                    ('⚠️ 輕微收縮，留意內需與外銷動能' if _pv8 >= (_pmi_榮枯-3) else '🔴 嚴重收縮，台股出口/電子股承壓'))
            _pd8 = f" ({_m8_pmi.get('date','')})" if _m8_pmi.get('date') else ''
            st.markdown(kpi(_pmi_title, f'{_pv8:.1f}', f'{_pl8}{_pd8}', _pc8, '#0d1117'), unsafe_allow_html=True)
        else:
            st.markdown(kpi('🇹🇼 台灣 PMI', '待取得', '50為榮枯線（CIER 中華經濟研究院）', '#484f58', '#0d1117'), unsafe_allow_html=True)
    
    # ── Row 2: 美國核心CPI | Fed Funds Rate | VIX 時間序列圖 ──────
    # v18.169：CPI + Fed Funds 並排呈現「MK 黃金拐點」配對指標
    _s8c2 = st.columns([1, 1, 2])
    
    with _s8c2[0]:
        if _m8_cpi:
            _cy8 = _m8_cpi.get('yoy', 0)
            _cpv8 = _m8_cpi.get('prev_yoy')  # v18.169
            _cc8 = TRAFFIC_RED if _cy8 > 3.5 else (TRAFFIC_YELLOW if _cy8 > 2.5 else TRAFFIC_GREEN)
            _cl8 = ('🔴 通膨偏高，Fed升息壓力大' if _cy8 > 3.5 else
                    ('⚠️ 通膨黏性，降息路徑放緩' if _cy8 > 2.5 else '✅ 通膨受控，降息可期'))
            _cdate8 = f" ({_m8_cpi.get('date','')})" if _m8_cpi.get('date') else ''
            _ctrend = ''
            if _cpv8 is not None:
                _cdelta = _cy8 - _cpv8
                _ctrend = (f"｜上月 {_cpv8:+.2f}% ({'↓' if _cdelta<-0.05 else ('↑' if _cdelta>0.05 else '→')}"
                           f"{abs(_cdelta):.2f})")
            st.markdown(kpi('美國核心CPI YoY', f'{_cy8:+.2f}%',
                            f'{_cl8}{_ctrend}{_cdate8}', _cc8, '#0d1117'), unsafe_allow_html=True)
            st.caption('💡 Fed 目標值 = 2%。CPI > 3.5% 時升息預期升高，外資易從台股提款。')
        else:
            st.markdown(kpi('美國核心CPI YoY', '待取得', 'Fed 目標值 = 2%', '#484f58', '#0d1117'), unsafe_allow_html=True)
    
    with _s8c2[1]:
        # v18.169：美國 Fed Funds Rate（CPI 配對 → MK 黃金拐點判讀）
        if _m8_fed:
            _fc = _m8_fed.get('current', 0)
            _fp = _m8_fed.get('prev', 0)
            _fdelta = _fc - _fp
            _fc8 = (TRAFFIC_RED if _fc >= 5.0 else
                    (TRAFFIC_YELLOW if _fc >= 3.0 else TRAFFIC_GREEN))
            _fl8 = ('🔴 利率高位（>5%），緊縮壓力大' if _fc >= 5.0 else
                    ('⚠️ 中性偏緊（3-5%）' if _fc >= 3.0 else '✅ 寬鬆環境（<3%）'))
            _fdate8 = f" ({_m8_fed.get('date','')})" if _m8_fed.get('date') else ''
            _farrow = '↓' if _fdelta < -0.05 else ('↑' if _fdelta > 0.05 else '→')
            _ftrend = f"｜上月 {_fp:.2f}% ({_farrow}{abs(_fdelta):.2f})"
            st.markdown(kpi('美國 Fed Funds Rate', f'{_fc:.2f}%',
                            f'{_fl8}{_ftrend}{_fdate8}', _fc8, '#0d1117'), unsafe_allow_html=True)
            st.caption('💡 與 CPI 配對：兩者同步月降 → ⭐ MK 黃金拐點（多頭最佳買點）')
        else:
            st.markdown(kpi('美國 Fed Funds Rate', '待取得',
                            '聯邦資金月均利率（FRED FEDFUNDS）',
                            '#484f58', '#0d1117'), unsafe_allow_html=True)
    
    with _s8c2[2]:
        if _m8_vix and _m8_vix.get('dates'):
            _vcur8 = _m8_vix.get('current', 0)
            _vma8  = _m8_vix.get('ma20', 0)
            # v18.284：VIX 燈號門檻統一至 SSOT（macro_buckets / MACRO_THRESHOLDS：22 黃 / 30 紅）
            _vc8   = TRAFFIC_RED if _vcur8 >= 30 else (TRAFFIC_YELLOW if _vcur8 >= 22 else TRAFFIC_GREEN)
            _vl8   = ('🚨 恐慌衝頂，強制空手' if _vcur8 >= 30 else
                      ('⚠️ 市場緊張，降低持倉' if _vcur8 >= 22 else '✅ 市場平靜'))
            import plotly.graph_objects as _go8
            _vfig8 = _go8.Figure()
            _vfig8.add_trace(_go8.Scatter(
                x=_m8_vix['dates'], y=_m8_vix['values'],
                mode='lines', line=dict(color='#58a6ff', width=1.5),
                fill='tozeroy', fillcolor='rgba(88,166,255,0.08)', name='VIX'))
            # v18.284：危險標準線改讀 SSOT（22 黃 / 30 紅），與頂部五桶 bar、SPEC §11 同源
            add_danger_hlines(_vfig8, 'vix')
            _vfig8.add_annotation(x=_m8_vix['dates'][-1], y=_vcur8,
                                  text=f'<b>{_vcur8}</b>', showarrow=True, arrowhead=2,
                                  font=dict(color=_vc8, size=12),
                                  bgcolor='#0d1117', bordercolor=_vc8)
            _vfig8.update_layout(
                height=170, margin=dict(l=35, r=60, t=30, b=20),
                paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
                font=dict(color='#8b949e', size=10), showlegend=False,
                xaxis=dict(showgrid=False, color='#484f58'),
                yaxis=dict(showgrid=True, gridcolor='#21262d', color='#484f58'),
                title=dict(text=f'VIX 恐慌指數 {_vcur8}（MA20={_vma8}）— {_vl8}',
                           font=dict(size=11, color=_vc8), x=0))
            st.plotly_chart(_vfig8, width='stretch')
        else:
            st.markdown(kpi('VIX 恐慌指數', '待取得', '≥22警戒 / ≥30危機→強制空手', '#484f58', '#0d1117'), unsafe_allow_html=True)
    
    # v18.194 fail trace：失敗 fetcher 錯誤碼浮上 UI（仿 Fund v19.43 RadarFailTrace）
    # 三狀態：① _macro_info 為空 → 未刷新或 outer 80s timeout 全失敗；② 有 _err_* → 局部失敗；③ 全綠 → 不顯示
    _err_label_map = {
        '_err_vix': 'VIX 恐慌指數',
        '_err_cpi': '美國核心 CPI',
        '_err_fed_funds': 'Fed Funds Rate',
        '_err_pmi': '🇹🇼 台灣 PMI',
        '_err_ndc': 'NDC 景氣燈號',
        '_err_export': '外銷訂單 YoY',
    }
    _macro_errs = {k: v for k, v in _macro_info.items() if k.startswith('_err_')}
    # v18.349:6 個核心 macro_info key 走 SSOT,與「🔎 資料診斷」覆蓋率表
    #   (data_coverage._macro_keys)共用同一清單,杜絕 v18.282 類 key 漂移。
    from shared.macro_buckets import MACRO_INFO_KEYS
    _macro_has_data = any(k in _macro_info for k in MACRO_INFO_KEYS)
    if not _macro_has_data and _macro_info.get('_loaded_at'):
        with st.expander('🚨 總經拼圖全部失敗 — 點開看可能原因', expanded=True):
            st.markdown(f"- **載入時間**：`{_macro_info.get('_loaded_at', 'N/A')}`")
            st.markdown('- **全部 6 個 fetcher 都沒拿到資料**，可能原因（按機率）：')
            st.markdown('  1. **outer 80s timeout** — Streamlit Cloud → FRED/stat.gov.tw RTT 太慢')
            st.markdown('  2. **proxy_helper 失效** — NAS Squid proxy 連線異常')
            st.markdown('  3. **FRED API key 未設** — CPI/Fed Funds fallback 到公開 csv 較慢')
            if _macro_errs:
                st.markdown('- **各 fetcher 回報的錯誤碼**：')
                for _ek, _ev in _macro_errs.items():
                    st.markdown(f'  - **{_err_label_map.get(_ek, _ek)}**：`{_ev}`')
    elif _macro_errs:
        with st.expander(f'🔍 部分指標載入失敗（{len(_macro_errs)} 項）— 點開看錯誤碼', expanded=False):
            for _ek, _ev in _macro_errs.items():
                st.markdown(f'- **{_err_label_map.get(_ek, _ek)}**：`{_ev}`')
            st.caption('💡 截圖此面板回報 → 可定位是 API timeout / proxy / FRED key / data source down')
    
    # ── v4.0 總經否決權 ─────────────────────────────────────
    _veto8 = []
    if _m8_vix and _m8_vix.get('current', 0) >= 30:
        _veto8.append(('🚨', f'VIX={_m8_vix["current"]} ≥ 30：全球流動性危機，無視所有技術面買訊，強制空手！', TRAFFIC_RED))
    if _m8_pmi and _m8_pmi.get('value', 55) < 48:
        _veto8.append(('⚠️', f'🇹🇼 台灣 PMI={_m8_pmi["value"]} < 48：在地製造業需求急凍，若 SOX 仍漲為「無基之彈」，降低持股水位', TRAFFIC_YELLOW))
    if _m8_cpi and _m8_cpi.get('yoy', 0) > 4.0:
        _veto8.append(('⚠️', f'核心CPI={_m8_cpi["yoy"]:.1f}% > 4%：通膨嚴峻，外資提款風險升高，注意匯率變動', TRAFFIC_YELLOW))
    if _m8_exp and _m8_exp.get('yoy', 0) < -5:
        _veto8.append(('⚠️', f'外銷訂單 YoY={_m8_exp["yoy"]:.1f}%：連續衰退，股價與基本面嚴重背離，謹慎追高', TRAFFIC_YELLOW))
    _crisis_buy = _m8_ndc and _m8_ndc.get('score', 25) <= 16
    if _crisis_buy:
        _veto8.append(('💡', f'NDC燈號={_m8_ndc["score"]:.0f}分（藍燈）：實體景氣衰退但為左側交易黃金布局時機！低基期好股勇敢建倉', TRAFFIC_GREEN))
    
    if _veto8:
        _has_veto = any(e[0] != '💡' for e in _veto8)
        _exp_title = ('🚨 v4.0 總經否決權已觸發（展開看詳情）' if _has_veto else
                      '💡 v4.0 危機入市訊號（展開看詳情）')
        with st.expander(_exp_title, expanded=_has_veto):
            for _icon8, _msg8, _col8 in _veto8:
                st.markdown(
                    f'<div style="border-left:3px solid {_col8};padding:6px 12px;'
                    f'margin:4px 0;color:{_col8};font-size:13px;">{_icon8} {_msg8}</div>',
                    unsafe_allow_html=True)
    elif any([_m8_vix, _m8_pmi, _m8_cpi, _m8_ndc]):
        st.success('✅ v4.0 總經否決權：無觸發 — 當前宏觀環境無系統性風險訊號')
    
    # ── Section 八 v4.0 動態結論（宏爺VIX否決權 × 孫慶龍估值/CLI矩陣）────
    _bias_info8 = st.session_state.get('bias_info') or {}
    _b240_8     = float(_bias_info8.get('bias_240', 0))
    _vix_now8   = float(_m8_vix.get('current', 0)) if _m8_vix else None
    # CLI：OECD CLI 榮枯線 = 100，取自 _m8_pmi（is_oecd_cli=True 時）
    _cli_8 = None
    if _m8_pmi and _m8_pmi.get('is_oecd_cli'):
        _cli_8 = float(_m8_pmi.get('value', 100))
    
    # VIX 防呆：若值 > 100 代表 API 錯置
    if _vix_now8 is not None and _vix_now8 > 100:
        st.error(f'❌ VIX 數值異常（{_vix_now8:.0f}），疑似 API 變數映射錯誤，結論暫不顯示。請重新整理。')
    else:
        # ── 宏爺：VIX 總經否決權 ──────────────────────────────
        if _vix_now8 is not None:
            if _vix_now8 >= 30:
                _hyc8 = TRAFFIC_RED
                _hyi8 = f'VIX {_vix_now8:.1f} ≥ 30'
                _hyc8t = '🔴 系統性風險爆發，觸發否決權！無視所有技術面多頭訊號，強制清倉，建議持股 0~10%，現金為王。'
            elif _vix_now8 >= 20:
                _hyc8 = TRAFFIC_YELLOW
                _hyi8 = f'VIX {_vix_now8:.1f}（20~30 警戒）'
                _hyc8t = '🟡 波動率飆升，市場情緒轉恐慌。停止加槓桿，汰弱留強，持股上限壓縮在 30% 以下。'
            else:
                _hyc8 = TRAFFIC_GREEN
                _hyi8 = f'VIX {_vix_now8:.1f} < 20（平靜期）'
                _hyc8t = '🟢 全球風險情緒穩定，未觸發否決權。回歸個股籌碼面與基本面操作。'
            st.markdown(teacher_conclusion('弘爺', _hyi8, _hyc8t, color=_hyc8), unsafe_allow_html=True)
        else:
            st.info('VIX 數據載入中，宏爺否決權暫無法判斷')
    
        # ── 宏爺：M1B-M2 資金動能（三段公式）────────────────────
        _m1b8_info = st.session_state.get('m1b_m2_info', {})
        if _m1b8_info and _m1b8_info.get('m1b_yoy') is not None and _m1b8_info.get('m2_yoy') is not None:
            _m1b8 = float(_m1b8_info.get('m1b_yoy', 0))
            _m2b8 = float(_m1b8_info.get('m2_yoy', 0))
            _gap8 = round(_m1b8 - _m2b8, 2)
            if _gap8 >= 1.0:
                _m1bc8 = TRAFFIC_GREEN
                _m1bi8 = f'M1B-M2 Gap = +{_gap8:.2f}%（黃金交叉·熱錢狂潮）'
                _m1bt8 = (f'🔥 資金動能強勁（M1B={_m1b8:.1f}% > M2={_m2b8:.1f}%），'
                          '熱錢湧入股市，積極作多強勢股。')
            elif _gap8 >= 0:
                _m1bc8 = TRAFFIC_GREEN
                _m1bi8 = f'M1B-M2 Gap = +{_gap8:.2f}%（資金溫和·中性擴張）'
                _m1bt8 = (f'💧 資金動能溫和（M1B={_m1b8:.1f}% ≥ M2={_m2b8:.1f}%），'
                          '無失血風險，回歸個股基本面與籌碼面操作。')
            else:
                _m1bc8 = TRAFFIC_YELLOW
                _m1bi8 = f'M1B-M2 Gap = {_gap8:.2f}%（死亡交叉·資金退潮）'
                _m1bt8 = (f'📉 資金動能趨緩（M1B={_m1b8:.1f}% < M2={_m2b8:.1f}%），'
                          '資金轉向定存或匯出，減碼等待訊號確認。')
            st.markdown(teacher_conclusion('宏爺', _m1bi8, _m1bt8, color=_m1bc8), unsafe_allow_html=True)
        else:
            st.info('M1B/M2 數據載入後自動顯示宏爺資金動能判斷')
    
        # ── 策略1：BIAS240 × 外銷訂單 二維矩陣（v5.0）──────────────
        if _bias_info8:
            _sql_b    = _b240_8
            _exp_yoy8 = float(_m8_exp.get('yoy', 0)) if _m8_exp else None
            _exp_dt8  = _m8_exp.get('date', '') if _m8_exp else ''
            if _exp_yoy8 is not None:
                _exp_txt8 = f'外銷訂單 YoY={_exp_yoy8:+.1f}%（{_exp_dt8}）'
                if _sql_b >= 15 and _exp_yoy8 >= 10:
                    _sqc8  = TRAFFIC_RED
                    _sqi8  = f'年線乖離 +{_sql_b:.1f}% × {_exp_txt8} → 🚀 有基之彈'
                    _sqc8t = ('🚀 有基之彈（主升段狂熱）：高估值由強勁出口基本面支撐，'
                              '資金面與基本面完美共振。順勢作多，但需以月線作為嚴格停損，'
                              '跌破月線即走，切勿因多頭情緒追漲加碼。')
                elif _sql_b >= 15 and _exp_yoy8 < 0:
                    _sqc8  = TRAFFIC_RED
                    _sqi8  = f'年線乖離 +{_sql_b:.1f}% × {_exp_txt8} → ⚠️ 無基之彈'
                    _sqc8t = ('⚠️ 無基之彈（史詩級泡沫）：股價嚴重高估且出口動能衰退，'
                              '純粹資金炒作泡沫，均值回歸壓力極大。'
                              '全面出清高本夢比個股，啟動長線倉位停利，切勿追高。')
                elif _sql_b >= 15:  # Export 0~10%
                    _sqc8  = TRAFFIC_YELLOW
                    _sqi8  = f'年線乖離 +{_sql_b:.1f}% × {_exp_txt8} → ⚡ 高估技術整理'
                    _sqc8t = ('⚡ 技術嚴重過熱，出口尚可但未爆發：高位持多需謹慎，'
                              '嚴設 ATR 動態停損，逢高獲利了結部分倉位，'
                              '等待出口數據確認是否升為「有基之彈」格局。')
                elif _sql_b > 0 and _exp_yoy8 > 0:
                    _sqc8  = TRAFFIC_GREEN
                    _sqi8  = f'年線乖離 +{_sql_b:.1f}% × {_exp_txt8} → 🟢 趨勢多頭'
                    _sqc8t = ('🟢 趨勢多頭（基本面支撐）：均線多頭發散且出口擴張，'
                              '可持股按原計畫操作，回歸個股財報與籌碼面選股，'
                              '等待更明確的突破訊號加碼。')
                elif _sql_b <= 0 and _exp_yoy8 > 0:
                    _sqc8  = '#58a6ff'
                    _sqi8  = f'年線乖離 {_sql_b:.1f}% × {_exp_txt8} → 💎 長線黃金坑'
                    _sqc8t = ('💎 長線黃金坑（超跌買點）：大盤超跌至年線之下，'
                              '但出口正在成長，實體基本面有撐。'
                              '大膽重壓具備 EPS 支撐的低基期錯殺股，左側分批建倉。')
                elif _sql_b <= 0 and _exp_yoy8 <= 0:
                    _sqc8  = '#8b949e'
                    _sqi8  = f'年線乖離 {_sql_b:.1f}% × {_exp_txt8} → 📉 景氣寒冬'
                    _sqc8t = ('📉 景氣寒冬（空頭格局）：技術面與基本面雙殺，'
                              '出口衰退且指數跌破年線，景氣收縮中。'
                              '多看少做，保留高比例現金，等待出口數據翻正再佈局。')
                else:
                    _sqc8  = '#8b949e'
                    _sqi8  = f'年線乖離 {_sql_b:.1f}% × {_exp_txt8} → 🟡 整理觀望'
                    _sqc8t = '🟡 指數在年線附近整理，等待方向確認後再布局，持股偏保守。'
            else:
                # Export 無資料 → 降級用 CLI
                _cli_txt8 = (f'CLI={_cli_8:.1f}（{"擴張" if _cli_8 >= 100 else "收縮"}）'
                             if _cli_8 is not None else 'CLI未知')
                if _sql_b >= 15 and _cli_8 is not None and _cli_8 >= 100:
                    _sqc8  = TRAFFIC_RED
                    _sqi8  = f'年線乖離 +{_sql_b:.1f}% × {_cli_txt8}（CLI備援·有基之彈）'
                    _sqc8t = '🔥 技術嚴重過熱且 CLI 擴張，可順勢持多，嚴設月線停損。'
                elif _sql_b >= 15:
                    _sqc8  = TRAFFIC_RED
                    _sqi8  = f'年線乖離 +{_sql_b:.1f}% × {_cli_txt8}（CLI備援·無基之彈）'
                    _sqc8t = '⚠️ 史詩級過熱，外銷訂單無資料，謹慎追高，嚴防崩盤。'
                elif _sql_b >= 0:
                    _sqc8  = TRAFFIC_GREEN
                    _sqi8  = f'年線乖離 +{_sql_b:.1f}%（趨勢多頭） {_cli_txt8}'
                    _sqc8t = '🟢 均線多頭，可持股操作，等待外銷訂單資料補充判斷。'
                elif _cli_8 is not None and _cli_8 > 100:
                    _sqc8  = '#58a6ff'
                    _sqi8  = f'年線乖離 {_sql_b:.1f}% × {_cli_txt8}（CLI備援·黃金坑）'
                    _sqc8t = '💎 CLI 擴張中大盤超跌，分批建倉低基期優質股。'
                else:
                    _sqc8  = '#8b949e'
                    _sqi8  = f'年線乖離 {_sql_b:.1f}%（整理·觀望） {_cli_txt8}'
                    _sqc8t = '🟡 外銷訂單待取得，景氣尚未明確擴張，持股保守等待訊號。'
            st.markdown(teacher_conclusion('孫慶龍', _sqi8, _sqc8t, color=_sqc8), unsafe_allow_html=True)
    
        # ── ⚔️ 攻擊火力分級（三環公式 SSS/A/B）────────────────────
        with st.expander('⚔️ 攻擊發動判定 — 三環公式 + 火力分級', expanded=True):
            # 取得需要的變數
            _li8      = st.session_state.get('li_latest')
            _fut8     = None
            if _li8 is not None and hasattr(_li8, 'empty') and not _li8.empty and '外資大小' in _li8.columns:
                try:
                    _fut8 = float(_li8.iloc[-1].get('外資大小', 0))
                except Exception:
                    pass
            _cl8d     = st.session_state.get('cl_data', {})
            _inst8    = _cl8d.get('inst', {})
            _fk8      = next((k for k in _inst8 if '外資' in k), None)
            _fnet8    = _inst8.get(_fk8, {}).get('net', None) if _fk8 else None
            _twii8    = tw_s.get('台股加權指數', {})
            _twd8     = tw_s.get('新台幣匯率', {})
            _sox8     = intl_s.get('費城半導體 SOX', {})
            _nvda8    = tech_s.get('輝達 NVDA', {})
            _exp_c    = float(_m8_exp.get('yoy', 0)) if _m8_exp else None
            _gap8c    = None
            if (_m1b8_info and _m1b8_info.get('m1b_yoy') is not None and
                    _m1b8_info.get('m2_yoy') is not None):
                try:
                    _gap8c = round(float(_m1b8_info['m1b_yoy']) -
                                   float(_m1b8_info['m2_yoy']), 2)
                except Exception:
                    pass
    
            # 三環條件評估
            _cA = _vix_now8 is not None and _vix_now8 < 20
            _cB = _fut8 is not None and _fut8 > -15000
            _cC = _exp_c is not None and _exp_c >= 10
            _cD = _gap8c is not None and _gap8c >= 1.0
            _cE = _fnet8 is not None and _fnet8 >= 100
            _cF = (float(_twii8.get('pct') or 0) > 0 and
                   float(_twd8.get('pct') or 0) < 0)
            _cG = (float(_sox8.get('pct') or 0) >= 1.5 or
                   float(_nvda8.get('pct') or 0) >= 2.0)
    
            _ring1_pass = _cA and _cB
            _ring2_cnt  = int(_cC) + int(_cD)
            _ring3_cnt  = int(_cE) + int(_cF) + int(_cG)
    
            _r1_html = (cond_badge(_cA, f'A VIX={_vix_now8:.1f}<20' if _vix_now8 else 'A VIX未知') + ' ' +
                        cond_badge(_cB, f'B 期貨={_fut8:,.0f}口' if _fut8 is not None else 'B 期貨未知'))
            _r2_html = (cond_badge(_cC, f'C 出口={_exp_c:+.1f}%' if _exp_c is not None else 'C 出口未知') + ' ' +
                        cond_badge(_cD, f'D M1B-M2={_gap8c:+.2f}%' if _gap8c is not None else 'D M1B-M2未知'))
            _r3_html = (cond_badge(_cE, f'E 外資={_fnet8:+.0f}億' if _fnet8 is not None else 'E 外資未知') + ' ' +
                        cond_badge(_cF, 'F 股匯雙漲' if _cF else 'F 股匯雙漲') + ' ' +
                        cond_badge(_cG, 'G SOX/NVDA點火'))
    
            if not _ring1_pass:
                _atk_color = TRAFFIC_RED
                _atk_grade = '🚫 禁止攻擊'
                _atk_pct = '持股 0~20%'
                _atk_txt = ('第一環未通過（VIX過高 或 外資重兵空單）：'
                            '大環境有鬼，任何技術面突破均為誘多，嚴格停損保留現金。')
            elif _ring2_cnt >= 2 and _ring3_cnt >= 2:
                _atk_color = '#f0e040'
                _atk_grade = '🚀 SSS 級全面總攻'
                _atk_pct = '持股 80~100%'
                _atk_txt = ('三環齊備、資金面與基本面完美共振：天時地利人和。'
                            '勇敢追擊強勢突破股，重壓半導體主流。')
            elif _ring2_cnt >= 1 and _ring3_cnt >= 1:
                _atk_color = TRAFFIC_RED
                _atk_grade = '🔥 A 級強勢進攻'
                _atk_pct = '持股 60~80%'
                _atk_txt = ('標準順風局：第二環（燃料）、第三環（點火）各至少一條通過。'
                            '順勢佈局，汰弱留強，跌破 10MA 停損。')
            elif _ring3_cnt >= 1:
                _atk_color = TRAFFIC_YELLOW
                _atk_grade = '🛡️ B 級試探性建倉'
                _atk_pct = '持股 30~50%'
                _atk_txt = ('大環境無足夠燃料，但短線有點火訊號。'
                            '屬於「跌深反彈」或「區間震盪」，打帶跑策略，見好就收。')
            else:
                _atk_color = '#8b949e'
                _atk_grade = '⏸️ 暫不進攻'
                _atk_pct = '持股 30% 以下'
                _atk_txt = '三環條件均不足，等待更明確訊號，保守觀望。'
    
            st.markdown(
                f'<div style="background:#0d1117;border:2px solid {_atk_color};border-radius:12px;padding:16px;margin:8px 0;">'
                f'<div style="font-size:18px;font-weight:900;color:{_atk_color};">{_atk_grade}</div>'
                f'<div style="font-size:14px;color:#c9d1d9;margin:4px 0;">{_atk_pct} — {_atk_txt}</div>'
                f'<div style="margin-top:10px;font-size:12px;color:#8b949e;">第一環（解除保險）：{_r1_html}<br>'
                f'第二環（確認燃料）：{_r2_html}<br>'
                f'第三環（點火訊號）：{_r3_html}</div>'
                f'</div>', unsafe_allow_html=True)
    
