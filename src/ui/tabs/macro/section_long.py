"""src/ui/tabs/macro/section_long.py — Section 3 長期桶 LONG(F-7.1 B-5 抽出)。

🌳 長期｜💰 資金環境 × 估值(M1B-M2 + 年線乖離 + 國際市場 + 技術指標)

closure params(7 explicit pass + ~13 re-import):
- _load_heavy: bool
- intl, intl_s, tech, tech_s, tw, tw_s: dict
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW  # noqa: F401
from src.config import FINMIND_TOKEN  # noqa: F401
from src.ui.render.macro_ui_components import section_header
from src.ui.render.ui_widgets import kpi, teacher_conclusion
from src.ui.tabs.macro.helpers import add_danger_hlines, render_macro_bucket_summary_bar  # noqa: F401
from src.services.daily_checklist import (
    multi_chart, sparkline, stat_card,
    COLORS_7, INTL_UNIT, TECH_MAP, TW_UNIT,
    _fetch_otc_via_finmind, fetch_flow_snapshot,
)


def render_section_long(_load_heavy: bool, intl: dict, intl_s: dict,
                        tech: dict, tech_s: dict, tw: dict, tw_s: dict) -> None:
    """渲染長期桶 LONG(§七 + 國際/技術市場列,原 tab_macro line 2580-2978)。"""
    # ══════════════════════════════════════════════════════════════
    # SECTION 七: 資金環境 × 估值 (C1-Z v18.293 物理重排前置至 §一)
    # 對齊 5 桶 reading order:🌳 長期 → §七 為首
    # ══════════════════════════════════════════════════════════════
    # v18.310 桶群組 banner：載入後 deep section 視覺歸位成 5 桶(user 反饋「版面太散」)
    from shared.macro_buckets import bucket_group_banner_html as _bgb
    st.markdown(_bgb('long', 1), unsafe_allow_html=True)
    st.markdown(section_header('七','🌳 長期｜💰 資金環境 × 估值（M1B-M2 + 年線乖離）','💰'),unsafe_allow_html=True)
    # v18.338：🌳 長期桶 = Fund 式分組卡片模板（小圖 + 值 + 燈號 + SPEC）。滿意後再套其餘 4 桶。
    # v18.313/314 桶輕量總結 bar(整體燈號 + 指標 chip + SPEC §11)；詳細 raw 維持下方收合。
    render_macro_bucket_summary_bar('long', with_cards=True)  # v18.338 Fund 式分組卡片模板
    
    # ── M1B-M2 年增率（FinMind）──────────────────────────────
    _m1b_info = st.session_state.get('m1b_m2_info')
    _bias_info = st.session_state.get('bias_info')
    
    # ── 弘爺 × 孫慶龍 結論（標題下方直接顯示）──────────────────
    _macro_concl = []
    if _m1b_info:
        _diff2 = _m1b_info.get('m1b_yoy', 0) - _m1b_info.get('m2_yoy', 0)
        if _diff2 > 0:
            _macro_concl.append(f'✅ M1B-M2={_diff2:+.2f}% 正值 → 策略3：資金行情啟動，大膽做多！（領先大盤3~6月）')
        elif _diff2 > -2:
            _macro_concl.append(f'⚠️ M1B-M2={_diff2:+.2f}% 接近0 → 策略3：資金動能趨緩，減碼等待訊號確認')
        else:
            _macro_concl.append(f'🔴 M1B-M2={_diff2:+.2f}% 負值 → 策略3：資金撤離，空手觀望！')
    if _bias_info:
        _bv2 = _bias_info.get('bias_240', 0)
        if _bv2 > 20:
            _macro_concl.append(f'⚠️ 年線乖離 {_bv2:+.1f}% 過大 → 策略1：開始分批減碼（乖離>20%啟動停利）')
        elif _bv2 < -20:
            _macro_concl.append(f'✅ 年線乖離 {_bv2:+.1f}% 嚴重低估 → 策略1：左側交易最佳布局區，大膽加碼！')
        else:
            _macro_concl.append(f'✅ 年線乖離 {_bv2:+.1f}% 正常 → 策略1：可持股，按計畫操作')
    for _mc2 in _macro_concl:
        _mc3 = _mc2.replace('✅','').replace('⚠️','').replace('🔴','').strip()
        if '→' in _mc3:
            _ind7, _res7 = _mc3.split('→', 1)
            _col7 = TRAFFIC_RED if any(k in _mc2 for k in ['🔴','⚠️']) else TRAFFIC_GREEN
            _tchr7 = '弘爺' if 'M1B' in _mc2 else '孫慶龍'
            st.markdown(teacher_conclusion(_tchr7, _ind7.strip(), _res7.strip(), color=_col7), unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="color:#c9d1d9;font-size:12px;padding:2px 6px;">• {_mc2}</div>', unsafe_allow_html=True)
    
    # v18.169：3 卡 → 2 卡精簡（月線乖離併入年線副標；詳細訊號歸頂部拐點面板）
    _m_cols = st.columns(2)
    with _m_cols[0]:
        if _m1b_info:
            _m1b_v  = _m1b_info.get('m1b_yoy', 0)
            _m2_v   = _m1b_info.get('m2_yoy', 0)
            _diff   = round(_m1b_v - _m2_v, 2)
            _mc     = '#da3633' if _diff > 0 else '#2ea043'
            _ml     = '✅ 資金流入股市' if _diff > 0 else '🔴 資金撤離股市'
            _proxy_note = '（大盤動能代理估算）' if _m1b_info.get('is_proxy') else ''
            st.markdown(kpi('M1B-M2 差距', f'{_diff:+.2f}%{_proxy_note}',
                            f'M1B:{_m1b_info.get("m1b_yoy",0):.1f}%  M2:{_m1b_info.get("m2_yoy",0):.1f}%  {_ml}', _mc, '#0d1117'), unsafe_allow_html=True)
        else:
            st.markdown(kpi('M1B-M2 差距', '抓取中', '更新總經數據後自動計算', '#484f58', '#0d1117'), unsafe_allow_html=True)
    
    with _m_cols[1]:
        if _bias_info:
            _bias_v = _bias_info.get('bias_240', 0)
            _bias_20 = _bias_info.get('bias_20', 0)
            _bc     = TRAFFIC_RED if _bias_v > 20 else (TRAFFIC_GREEN if _bias_v < -20 else TRAFFIC_YELLOW)
            _bl     = ('⚠️ 乖離過大，考慮減碼' if _bias_v > 20
                       else ('✅ 嚴重低估，可積極布局' if _bias_v < -20
                       else '⚪ 乖離正常區間'))
            _est_note = '（估算）' if _bias_info.get('is_estimated') else ''
            _days_note = f" {_bias_info.get('data_days',0)}天資料" if _bias_info.get('is_estimated') else ''
            # 月線乖離併入副標（過熱/超賣時加 emoji 提示）
            _bl20_short = ('⚠️過熱' if _bias_20 > 10 else
                           ('✅機會' if _bias_20 < -10 else '正常'))
            st.markdown(kpi(f'年線乖離率(240MA){_est_note}', f'{_bias_v:+.1f}%',
                            f'{_bl}{_days_note}　｜　月線20MA: {_bias_20:+.1f}% ({_bl20_short})',
                            _bc, '#0d1117'), unsafe_allow_html=True)
        else:
            st.markdown(kpi('年線乖離率(240MA)', '計算中', '大盤收盤/年線（月線乖離併顯示）', '#484f58', '#0d1117'), unsafe_allow_html=True)
    
    st.caption('📖 完整乖離訊號與門檻判讀 → 詳見頂部「📊 拐點詳細分析」第 2 面向')
    st.markdown('<hr style="border-color:#21262d;margin:14px 0;">',unsafe_allow_html=True)
    
    from shared.macro_buckets import bucket_group_banner_html as _bgb  # v18.310 桶群組 banner
    st.markdown(_bgb('mid', 2), unsafe_allow_html=True)
    st.markdown(section_header('一','📈 中期｜🌍 國際市場動態（影響台股的全球指標）','🌐'), unsafe_allow_html=True)
    render_macro_bucket_summary_bar('mid')  # v18.314 桶輕量總結 bar
    _sox1 = intl_s.get('費城半導體 SOX')
    _dji1 = intl_s.get('道瓊工業 DJI')
    _dxy1 = intl_s.get('美元指數 DXY')
    _tyx1 = intl_s.get('10Y公債殖利率')
    
    # ── 老師：SOX × DXY 動態結論 ─────────────────────────────
    _sox_pct = _sox1.get('pct', None) if _sox1 else None
    _dxy_val = _dxy1.get('last', None) if _dxy1 else None
    _tyx_val = _tyx1.get('last', None) if _tyx1 else None
    
    if _sox_pct is not None and _dxy_val is not None:
        if _sox_pct >= 1.5 and _dxy_val < 100:
            _i1c = f'SOX {_sox_pct:+.1f}% / DXY {_dxy_val:.1f} → 熱錢狂潮，重壓電子強勢股'
            _i1a = '台積電/矽力/聯發科可積極持有'
        elif _sox_pct <= -1.5 and _dxy_val >= 103:
            _i1c = f'SOX {_sox_pct:+.1f}% / DXY {_dxy_val:.1f} → 外資提款，電子股嚴格減碼'
            _i1a = '降倉至 3 成以下，等待 DXY 回落'
        elif _sox_pct >= 1.0 and _dxy_val >= 100:
            _i1c = f'SOX {_sox_pct:+.1f}% / DXY {_dxy_val:.1f} → 內資控盤，精選中小型題材股'
            _i1a = '避開外資重倉大型權值，找內資題材'
        elif _sox_pct <= -1.5:
            _i1c = f'SOX {_sox_pct:+.1f}% / DXY {_dxy_val:.1f} → 費半重挫，台股科技開低機率高'
            _i1a = '設好停損，避免隔日追殺'
        else:
            _i1c = f'SOX {_sox_pct:+.1f}% / DXY {_dxy_val:.1f} → 走勢分化，方向未明'
            _i1a = '降部位等待費半方向確認'
        _i1_ind = f'SOX {_sox_pct:+.1f}% / DXY {_dxy_val:.1f}'
    elif _sox1 and _dji1:
        _sp = _sox1.get('pct', 0)
        _dp = _dji1.get('pct', 0)
        _i1c = f'費半 {_sp:+.1f}% / 道瓊 {_dp:+.1f}%（DXY 資料未載入）'
        _i1a = '等待完整數據確認'
        _i1_ind = f'SOX {_sp:+.1f}%'
    else:
        _i1c = '數據尚未載入，請點擊「🚀 一鍵更新全部數據」'
        _i1a = ''
        _i1_ind = '費半+美元'
    st.markdown(teacher_conclusion('宏爺', _i1_ind, _i1c, _i1a), unsafe_allow_html=True)
    
    # ── 策略1：10Y Yield 動態結論 ─────────────────────────────
    if _tyx_val is not None:
        if _tyx_val >= 4.8:
            _sql_c = f'10Y殖利率 {_tyx_val:.2f}% → 系統風險！無風險利率飆升，本益比大幅下修'
            _sql_a = '保留現金，嚴格控制槓桿'
        elif _tyx_val >= 4.5:
            _sql_c = f'10Y殖利率 {_tyx_val:.2f}% → 估值承壓，資金成本上升'
            _sql_a = '避開高本夢比個股，轉向低本益比價值股'
        else:
            _sql_c = f'10Y殖利率 {_tyx_val:.2f}% → 總經安全，利率溫和股市友善'
            _sql_a = '精選低基期價值股，可適度持有'
        st.markdown(teacher_conclusion('孫慶龍', f'10Y {_tyx_val:.2f}%', _sql_c, _sql_a), unsafe_allow_html=True)
    if _load_heavy:
        ci = st.columns(len(INTL_UNIT))
        for col,(name,unit) in zip(ci,INTL_UNIT.items()):
            with col:
                st.markdown(stat_card(name,intl_s.get(name),unit,name in intl_s),unsafe_allow_html=True)
    idx_d = {k:v for k,v in intl.items() if k in ['道瓊工業 DJI','納斯達克 IXIC','費城半導體 SOX']}
    if idx_d:
        st.plotly_chart(multi_chart(idx_d,'美股三大指數標準化比較',norm=True,height=220),
                        width='stretch', config={'displayModeBar':False})
    bc,dc = st.columns(2)
    with bc:
        if '10Y公債殖利率' in intl:
            _sp_10y = sparkline(intl['10Y公債殖利率'],'10Y公債殖利率',TRAFFIC_RED)
            # v18.286:加 SSOT 危險標準線(MACRO_THRESHOLDS.US10Y 4.5/5.0)
            try:
                add_danger_hlines(_sp_10y, 'us10y')
            except Exception:
                pass
            st.plotly_chart(_sp_10y, width='stretch',
                            config={'displayModeBar':False})
    with dc:
        if '美元指數 DXY' in intl:
            _sp_dxy = sparkline(intl['美元指數 DXY'],'美元指數 DXY','#ffd700')
            # v18.286:加 SSOT 危險標準線(MACRO_THRESHOLDS.DXY 105/110)
            try:
                add_danger_hlines(_sp_dxy, 'dxy')
            except Exception:
                pass
            st.plotly_chart(_sp_dxy, width='stretch',
                            config={'displayModeBar':False})
    
    # ══ 全球資金流向（世界區域股市 × 跨資產 Risk-on/off 代理指標）═══════════
    st.markdown('<hr style="border-color:#21262d;margin:14px 0;">', unsafe_allow_html=True)
    st.markdown('<div style="background:linear-gradient(90deg,#161b22,transparent);'
                'border-left:3px solid #1f6feb;border-radius:0 6px 6px 0;padding:8px 14px;margin:16px 0 10px 0;">'
                '<span style="color:#1f6feb;font-weight:700;">🌊 全球資金流向（世界區域股市 × 跨資產 Risk-on/off）'
                '</span></div>', unsafe_allow_html=True)
    st.caption('💡 真實基金流量為付費資料；本區以各區域／資產代表性 ETF 的相對強弱當「資金流向代理」'
               '（強勢＝資金流入、弱勢＝流出），風險情緒採 252 日滾動 Z-score＋clip(-3,3) 合成。')
    from src.compute.macro import flow_engine as _fe
    if _load_heavy:
        with st.spinner('🌐 載入全球資金流向…'):
            _flow_raw = fetch_flow_snapshot()
    else:
        _flow_raw = {}
    _flow_close = {n: _fe.to_close_list(df) for n, df in (_flow_raw or {}).items()}
    _reg_close = {n: _flow_close[n] for n in _fe.REGIONAL_ETFS if _flow_close.get(n)}
    if not _reg_close:
        if not _load_heavy:
            st.info('📡 點擊「🚀 一鍵更新全部數據」載入全球資金流向')
        else:
            st.info('ℹ️ 全球資金流向資料暫時無法取得（yfinance 海外來源可能限流），可稍後重試。')
    else:
        # 1. 世界區域股市：標準化走勢 + 流入流出排名
        _reg_df = {n: _flow_raw[n] for n in _reg_close}
        st.plotly_chart(multi_chart(_reg_df, '各區域股市近 45 日標準化比較（起點＝100）', norm=True, height=240),
                        width='stretch', config={'displayModeBar': False})
        _rank5 = _fe.rank_regional_flow(_reg_close, days=5)
        _rank20 = dict(_fe.rank_regional_flow(_reg_close, days=20))
        if _rank5:
            _rcols = st.columns(len(_rank5))
            for _rc, (_nm, _p5) in zip(_rcols, _rank5):
                _p20 = _rank20.get(_nm)
                with _rc:
                    st.metric(_nm, f'{_p5:+.1f}%', f'20日 {_p20:+.1f}%' if _p20 is not None else None)
            st.caption(f'📥 近 5 日資金流入最強：**{_rank5[0][0]}**（{_rank5[0][1]:+.1f}%）　｜　'
                       f'📤 流出最弱：**{_rank5[-1][0]}**（{_rank5[-1][1]:+.1f}%）')
        # 2. 新台幣／外資視角
        _inst_f = (st.session_state.get('cl_data') or {}).get('inst') or {}
        _frn = _inst_f.get('外資及陸資') or _inst_f.get('外資')
        _frn_net = _frn.get('net') if isinstance(_frn, dict) else None
        _ewt5 = dict(_rank5).get('台灣 EWT')
        _twd_pct = (tw_s.get('新台幣匯率') or {}).get('pct')
        _tw_bits = []
        if _frn_net is not None:
            _tw_bits.append(f'外資買賣超 **{_frn_net:+.0f} 億**')
        if _ewt5 is not None:
            _tw_bits.append(f'台股 ETF（EWT）近 5 日 **{_ewt5:+.1f}%**')
        if _twd_pct is not None:
            _tw_bits.append(f'新台幣 **{float(_twd_pct):+.2f}%**')
        if _tw_bits:
            st.markdown('**🇹🇼 新台幣／外資視角**：' + '　｜　'.join(_tw_bits))
            st.caption('EWT（美國掛牌台股 ETF）相對強弱反映海外資金對台股偏好，與外資買賣超、台幣走勢合看。')
        # 3. 跨資產 Risk-on／Risk-off 風險情緒分數
        _risk = _fe.compute_risk_score(_flow_close)
        st.markdown('**⚖️ 跨資產 Risk-on／Risk-off 風險情緒**（252 日滾動 Z-score 合成）')
        if _risk.get('score') is None:
            st.info('ℹ️ 跨資產風險情緒資料不足（需約 1 年歷史），暫無法計算。')
        else:
            _kc1, _kc2 = st.columns([1, 2])
            with _kc1:
                st.metric('風險情緒分數', f"{_risk['score']:+d}")
            with _kc2:
                st.markdown(f"目前研判：**{_risk['label']}**　"
                            "<span style='color:#8b949e;font-size:12px;'>"
                            "（＋100 極度追逐風險　↔　−100 極度避險）</span>", unsafe_allow_html=True)
            if _risk.get('components'):
                _det = '　｜　'.join(
                    f"{_lbl} {'＋' if _z * _d >= 0 else ''}{round(_z * _d, 1)}"
                    for _lbl, _z, _d in _risk['components'])
                st.caption(f'貢獻明細（已乘方向，正＝偏 risk-on）：{_det}')
            st.caption('📖 領先／滯後：MOVE/VIX 債市壓力為領先訊號——債市波動先飆，常於 1–4 週內傳導至股市；'
                       'USD/JPY 急貶（carry 平倉）多伴隨風險資產同步下殺。XCCY 基差、穩定幣 SSR 因免費資料源不可得，未納入。')
    
    st.markdown('<hr style="border-color:#21262d;margin:14px 0;">',unsafe_allow_html=True)
    st.markdown(section_header('二','📈 中期｜🇹🇼 台股大盤（今日漲跌 + 台幣匯率）','🇹🇼'),unsafe_allow_html=True)
    _twii2 = tw_s.get('台股加權指數')
    _twd2 = tw_s.get('新台幣匯率')
    if _twii2 and _twd2:
        _tp = _twii2.get('pct')
        _fp = _twd2.get('pct')
        # 邊界防呆：API 回傳 None 時不崩潰
        _tp = float(_tp) if _tp is not None else None
        _fp = float(_fp) if _fp is not None else None
        if _tp is not None and _fp is not None:
            # 四象限資金流向判斷（fx>0=台幣貶值，fx<0=台幣升值）
            if _tp > 0 and _fp < 0:
                # 股匯雙漲：外資真實匯入
                _t2c = f'台股 {_tp:+.1f}% ／ 台幣升值 {_fp:+.2f}% → 股匯雙漲，外資真金白銀匯入，權值股領軍'
                _t2a = '順勢大膽作多，持股建議 80~100%'
            elif _tp > 0 and _fp > 0:
                # 股漲匯貶：疑似拉高出貨
                _t2c = f'台股 {_tp:+.1f}% ／ 台幣貶值 {_fp:+.2f}% → 股漲匯貶，指數虛漲，疑似外資拉高出貨'
                _t2a = '不追高，謹慎觀察，持股建議 50%'
            elif _tp < 0 and _fp > 0:
                # 股匯雙殺：外資大舉提款
                _t2c = f'台股 {_tp:+.1f}% ／ 台幣貶值 {_fp:+.2f}% → 股匯雙殺，外資無情提款撤出'
                _t2a = '嚴格減碼防守，持股建議 0~30%（現金為王）'
            elif _tp < 0 and _fp < 0:
                # 股跌匯升：技術性洗盤
                _t2c = f'台股 {_tp:+.1f}% ／ 台幣升值 {_fp:+.2f}% → 股跌匯升，外資資金停泊未撤，技術性洗盤'
                _t2a = '尋找錯殺優質股逢低布局，持股建議 50~70%'
            else:
                _t2c = f'台股 {_tp:+.1f}% ／ 台幣 {_fp:+.2f}%，無明顯方向性波動'
                _t2a = '維持現有部位，靜待表態'
        else:
            _t2c = '台股資料載入中'
            _t2a = '等待完整數據'
            _tp = _twii2.get('pct', 0) or 0
            _fp = _twd2.get('pct', 0) or 0
        _t2_ind = f'加權 {_twii2.get("last",0):,.0f}pt {(_tp or 0):+.1f}% | 台幣 {_twd2.get("last",0):.2f}'
    elif _twii2:
        _tp = _twii2.get('pct', 0) or 0
        _t2c = f'台股 {_tp:+.1f}%，{"偏多" if _tp > 0 else "偏空"}（台幣資料未載入）'
        _t2a = '參考其他指標確認方向'
        _t2_ind = f'加權 {_twii2.get("last",0):,.0f}pt {_tp:+.1f}%'
    else:
        _t2c = '數據尚未載入，請點擊「🚀 一鍵更新全部數據」'
        _t2a = ''
        _t2_ind = '台股加權 + 台幣'
    st.markdown(teacher_conclusion('宏爺', _t2_ind, _t2c, _t2a), unsafe_allow_html=True)
    if _load_heavy:
        tc = st.columns(len(TW_UNIT))
        for col,(name,unit) in zip(tc,TW_UNIT.items()):
            with col:
                st.markdown(stat_card(name,tw_s.get(name),unit,name in tw_s),unsafe_allow_html=True)
    tw1,tw2 = st.columns(2)
    with tw1:
        if '台股加權指數' in tw:
            _twii_ohlc = tw['台股加權指數']
            if all(c in _twii_ohlc.columns for c in ['open', 'high', 'low', 'close']):
                import plotly.graph_objects as _go_kl
                _ohlc_tail = _twii_ohlc.tail(60)
                _fig_kl = _go_kl.Figure(data=[_go_kl.Candlestick(
                    x=_ohlc_tail.index,
                    open=_ohlc_tail['open'], high=_ohlc_tail['high'],
                    low=_ohlc_tail['low'],   close=_ohlc_tail['close'],
                    increasing_line_color=TRAFFIC_RED, increasing_fillcolor='rgba(248,81,73,0.75)',
                    decreasing_line_color=TRAFFIC_GREEN, decreasing_fillcolor='rgba(63,185,80,0.75)',
                    name='加權指數',
                )])
                _fig_kl.update_layout(
                    title=dict(text='台股加權指數（日K）', font=dict(size=11, color='#8b949e'), x=0),
                    height=220, margin=dict(l=40, r=15, t=30, b=20),
                    paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
                    font=dict(color='#8b949e', size=10), showlegend=False,
                    xaxis=dict(showgrid=False, color='#484f58', rangeslider=dict(visible=False)),
                    yaxis=dict(showgrid=True, gridcolor='#21262d', color='#484f58'),
                )
                st.plotly_chart(_fig_kl, width='stretch', config={'displayModeBar': False})
            else:
                st.plotly_chart(sparkline(_twii_ohlc, '台股加權指數', '#58a6ff'),
                                width='stretch', config={'displayModeBar': False})
    with tw2:
        if not _load_heavy:
            st.caption('📡 點擊「🚀 一鍵更新全部數據」載入櫃買指數 OTC')
        else:
            try:
                otc = _fetch_otc_via_finmind(FINMIND_TOKEN)
                if otc is not None and not otc.empty:
                    st.plotly_chart(sparkline(otc,'櫃買指數 OTC',TRAFFIC_GREEN),
                                    width='stretch',config={'displayModeBar':False})
            except Exception:
                pass
    st.markdown('<hr style="border-color:#21262d;margin:14px 0;">',unsafe_allow_html=True)
    st.markdown('<hr style="border-color:#21262d;margin:8px 0;">', unsafe_allow_html=True)
    
    st.markdown('<hr style="border-color:#21262d;margin:8px 0;">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:10px;color:#484f58;text-transform:uppercase;letter-spacing:1px;margin:4px 0;">📊 市場廣度</div>', unsafe_allow_html=True)
    st.markdown(section_header('六','📈 中期｜🖥️ 美股科技巨頭（台股明天的風向球）','🖥️'),unsafe_allow_html=True)
    _sox6 = intl_s.get('費城半導體 SOX') or tech_s.get('費城半導體 SOX')
    _nvda6 = next((tech_s[k] for k in tech_s if 'NVDA' in k or '輝達' in k), None)
    if _sox6:
        _sp6 = _sox6.get('pct', 0)
        if _sp6 > 2:
            _t6c = f'費半強漲 {_sp6:+.1f}%，明日台積電/聯發科可望跟漲'
            _t6a = '科技類股可持有或加碼'
        elif _sp6 > 0:
            _t6c = f'費半小漲 {_sp6:+.1f}%，台股科技偏多但力道有限'
            _t6a = '持有觀察，不急著追高'
        elif _sp6 < -2:
            _t6c = f'費半重挫 {_sp6:+.1f}%，明日台股科技開低機率高'
            _t6a = '設好停損，避免隔日追殺'
        else:
            _t6c = f'費半小跌 {_sp6:+.1f}%，短線偏空但未破關鍵支撐'
            _t6a = '觀望等待方向確認'
        _nvda_txt = f' | NVDA {_nvda6.get("pct",0):+.1f}%' if _nvda6 else ''
        _t6_ind = f'費半 SOX {_sp6:+.1f}%{_nvda_txt}'
    else:
        _t6c = '技術股數據尚未載入，請點擊「🚀 一鍵更新全部數據」'
        _t6a = ''
        _t6_ind = '費半+美股科技'
    st.markdown(teacher_conclusion('蔡森', _t6_ind, _t6c, _t6a), unsafe_allow_html=True)
    if _load_heavy:
        tc_list = list(TECH_MAP.keys())
        tr1=st.columns(4)
        tr2=st.columns(len(tc_list[4:]) if len(tc_list)>4 else 1)
        for i,(col,name) in enumerate(zip(tr1,tc_list[:4])):
            with col:
                st.markdown(stat_card(name,tech_s.get(name),'USD',name in tech_s),unsafe_allow_html=True)
        for i,(col,name) in enumerate(zip(tr2,tc_list[4:])):
            with col:
                st.markdown(stat_card(name,tech_s.get(name),'USD',name in tech_s),unsafe_allow_html=True)
    if tech:
        st.plotly_chart(multi_chart(tech,'科技巨頭標準化比較',norm=True,height=250),
                        width='stretch',config={'displayModeBar':False})
        clrs=COLORS_7 if isinstance(COLORS_7,list) else list(COLORS_7.values())
        sp1=st.columns(4)
        sp2=st.columns(len(tc_list[4:]) if len(tc_list)>4 else 1)
        for i,(col,name) in enumerate(zip(sp1,tc_list[:4])):
            with col:
                if name in tech:
                    st.plotly_chart(sparkline(tech[name],name,clrs[i] if i<len(clrs) else '#58a6ff'),
                                    width='stretch',config={'displayModeBar':False})
        for i,(col,name) in enumerate(zip(sp2,tc_list[4:])):
            with col:
                if name in tech:
                    st.plotly_chart(sparkline(tech[name],name,clrs[i+4] if i+4<len(clrs) else '#ffd700'),
                                    width='stretch',config={'displayModeBar':False})
    _tsm = tech_s.get('台積電 ADR')
    _nvda = tech_s.get('輝達 NVDA')
    _concl_tech = []
    if _tsm:
        _concl_tech.append(f'TSM ADR {_tsm["last"]:.2f} ({_tsm["pct"]:+.1f}%) → {"✅ 台積電強→明日2330有望跟漲" if _tsm["pct"]>1 else ("⚠️ 台積電弱→注意2330壓力" if _tsm["pct"]<-1 else "⚪ 台積電持平")}')
    if _nvda:
        _concl_tech.append(f'NVDA {_nvda["last"]:.2f} ({_nvda["pct"]:+.1f}%) → {"✅ AI族群情緒熱" if _nvda["pct"]>2 else ("🔴 AI族群降溫" if _nvda["pct"]<-2 else "⚪ AI族群穩定")}')
    for _tc2 in _concl_tech:
        st.markdown(f'<div style="color:#c9d1d9;font-size:13px;padding:3px 0;">• {_tc2}</div>', unsafe_allow_html=True)
    
    st.markdown('<hr style="border-color:#21262d;margin:14px 0;">',unsafe_allow_html=True)
