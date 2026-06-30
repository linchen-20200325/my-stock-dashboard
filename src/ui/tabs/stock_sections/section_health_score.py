"""src/ui/tabs/stock_sections/section_health_score.py — A 健康度評分 + v4/v5 卡片(v18.407 U4 Phase 3-A).

從 tab_stock.py:1101-1368 抽出。含 A 健康度評分(SVG 量表 + 四維 + 6 技術指標
KPI + 大師建議)、v4 防守線+VPOC+籌碼 3 卡、v5 布林+殖利率+財報領先 3 卡。

§8.2 layer:L5 UI Tab section helper(中風險:依賴 15+ locals / 8 helpers /
5 session_state keys,但無下游 state 寫回問題)。

對外 API:
- render_health_score_section(...) -> None
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
from shared.signal_thresholds import (
    VOLUME_RATIO_DRY,
    VOLUME_RATIO_MILD,
    VOLUME_RATIO_SURGE,
)
from src.compute.scoring import health_grade
from src.compute.scoring.scoring_helpers import calc_fundamental_score
from src.compute.strategy import (
    analyze_fundamental_leading,
    calc_dividend_yield_357,
    detect_bollinger_breakout,
)
from src.compute.strategy.v4_strategy_engine import V4StrategyEngine
from src.ui.render import kpi, teacher_conclusion
from src.ui.render.app_render import render_health_score


def render_health_score_section(
    sid2: str, health2, details2,
    df2, price2, qtr2, yearly2, avg_div2,
    rsi2, vr2, ibs2, k2, d2, bb2, vcp2, cl2,
) -> None:
    """A. 個股健康度評分(0~100) + v4/v5 卡片群。

    Args:
        sid2: 股票代碼
        health2: 健康分(0-100)
        details2: 因子 detail dict
        df2: 股價 DataFrame
        price2: 當前股價
        qtr2, yearly2: 季財報 / 年配息
        avg_div2: 5 年平均配息
        rsi2 / vr2 / ibs2 / k2 / d2 / bb2 / vcp2: 6 技術指標 + bb + vcp
        cl2: 合約負債
    """
    # ══ A. 健康度評分 ══════════════════════════════════════
    st.markdown('#### 🏥 A. 個股健康度評分（0~100）')
    st.caption('🔰 指標白話：RSI >70 過熱、<30 超賣｜KD 黃金交叉（K 升破 D）偏多、死亡交叉偏空｜'
               'IBS 看收盤落在當日高低點的位置（越高越強）｜量比＝今日量 ÷ 近期均量（>1 放量）。')
    if health2 >= HEALTH_GRADE_A_MIN:
        _ha = f'健康度 {health2:.0f}分，技術面強勢'
        _hb = '確認大盤方向後可建倉，停損設月線下方'
    elif health2 >= HEALTH_GRADE_B_MIN:
        _ha = f'健康度 {health2:.0f}分，中性偏多，尚未達進場標準'
        _hb = '等待突破80分或放量突破前高再行動'
    else:
        _ha = f'健康度 {health2:.0f}分，技術面偏弱，跳過'
        _hb = '不要強求，另找更好標的'
    st.markdown(teacher_conclusion('宏爺', f'{sid2} 健康度 {health2:.0f}分', _ha, _hb),
                unsafe_allow_html=True)
    # 評分信心區間說明(_score_help 變數定義保留語意,但實際從未渲染:對齊原 inline 行為)
    _ = (
        '<div style="background:#0a1628;border-left:3px solid #58a6ff;'
        'padding:8px 12px;border-radius:0 6px 6px 0;margin-bottom:8px;font-size:11px;color:#8b949e;">'
        '📊 <b>評分不是保證,是機率</b>:'
        '健康度80分 → 歷史勝率約65%(10次中6-7次對)。'
        '停損紀律決定你能否從對的那幾次賺夠錢。'
        '</div>'
    )

    ha, hb = st.columns([1, 2])
    with ha:
        # 基本面評分
        _fund_sc = calc_fundamental_score(qtr2, yearly2, avg_div2)
        # 技術警示
        _tech_al = []
        if rsi2 and rsi2 < 30:
            _tech_al.append(('🟡', 'RSI過低', '看跌反彈', f'RSI={rsi2:.0f}，超賣可能反彈'))
        elif rsi2 and rsi2 > 70:
            _tech_al.append(('🔴', 'RSI超買', '超買注意', f'RSI={rsi2:.0f}，高檔過熱'))
        if df2 is not None and 'MA5' in df2.columns and 'MA10' in df2.columns and len(df2) >= 2:
            _m5, _m10 = float(df2['MA5'].iloc[-1]), float(df2['MA10'].iloc[-1])
            _m5p, _m10p = float(df2['MA5'].iloc[-2]), float(df2['MA10'].iloc[-2])
            if _m5 < _m10 and _m5p >= _m10p:
                _tech_al.insert(0, ('🔴', 'MA5下穿MA10', '看跌', '短均死叉，趨勢轉弱'))
            elif _m5 > _m10 and _m5p <= _m10p:
                _tech_al.insert(0, ('🟢', 'MA5上穿MA10', '看漲', '短均黃金交叉，轉強'))
        if vr2 and vr2 < VOLUME_RATIO_DRY:
            _tech_al.append(('🟡', '量能不足', '觀察', f'量比={vr2:.2f}，市場觀望'))
        if k2 and d2:
            if k2 < d2 and k2 > 20:
                _tech_al.append(('🟡', 'KD死亡交叉', '看跌', f'K={k2:.0f} D={d2:.0f}'))
            elif k2 > d2 and k2 < 80:
                _tech_al.append(('🟢', 'KD黃金交叉', '看漲', f'K={k2:.0f} D={d2:.0f}'))
        st.markdown(render_health_score(health2, details2, sid2, _fund_sc, _tech_al),
                    unsafe_allow_html=True)
    with hb:
        # 六大技術指標卡片
        ind1, ind2, ind3 = st.columns(3)
        ind4, ind5, ind6 = st.columns(3)
        with ind1:
            rsi_c = TRAFFIC_YELLOW if rsi2 and rsi2 > 70 else (TRAFFIC_GREEN if rsi2 and rsi2 < 30 else '#58a6ff')
            rsi_txt = '超買⚠️' if rsi2 and rsi2 > 70 else ('超賣反彈' if rsi2 and rsi2 < 30 else '中性')
            st.markdown(kpi('RSI(14)', f'{rsi2}' if rsi2 else '-', rsi_txt, rsi_c, rsi_c),
                        unsafe_allow_html=True)
        with ind2:
            vr_c = TRAFFIC_GREEN if vr2 and vr2 >= VOLUME_RATIO_SURGE else (TRAFFIC_YELLOW if vr2 and vr2 >= VOLUME_RATIO_MILD else '#484f58')
            vr_txt = '異常放量' if vr2 and vr2 >= VOLUME_RATIO_SURGE else ('溫和放量' if vr2 and vr2 >= VOLUME_RATIO_MILD else '量縮')
            st.markdown(kpi('量比(5日)', f'{vr2}' if vr2 else '-', vr_txt, vr_c, vr_c),
                        unsafe_allow_html=True)
        with ind3:
            ibs_c = TRAFFIC_GREEN if ibs2 is not None and ibs2 <= 0.2 else (TRAFFIC_RED if ibs2 is not None and ibs2 >= 0.8 else '#58a6ff')
            ibs_txt = '收低≤20%易反彈' if ibs2 is not None and ibs2 <= 0.2 else ('收高≥80%易賣壓' if ibs2 is not None and ibs2 >= 0.8 else '中性位置')
            st.markdown(kpi('IBS', f'{ibs2}' if ibs2 is not None else '-', ibs_txt, ibs_c, ibs_c),
                        unsafe_allow_html=True)
        with ind4:
            kd_c = TRAFFIC_GREEN if k2 and d2 and k2 > d2 and k2 < 80 else (TRAFFIC_YELLOW if k2 and d2 and k2 > d2 else TRAFFIC_RED)
            kd_txt = '黃金交叉' if k2 and d2 and k2 > d2 else '死亡交叉'
            st.markdown(kpi('KD', f'K={k2}/D={d2}' if k2 else '-', kd_txt, kd_c, kd_c),
                        unsafe_allow_html=True)
        with ind5:
            if df2 is not None and 'MA20' in df2.columns and 'MA100' in df2.columns:
                p = price2
                m20 = float(df2['MA20'].iloc[-1])
                m100 = float(df2['MA100'].iloc[-1])
                if p > m20 > m100:
                    tr_txt = '多頭排列'
                    tr_c = TRAFFIC_GREEN
                elif p < m20 < m100:
                    tr_txt = '空頭排列'
                    tr_c = TRAFFIC_RED
                elif p > m100:
                    tr_txt = '多箱整理'
                    tr_c = TRAFFIC_YELLOW
                else:
                    tr_txt = '空箱整理'
                    tr_c = TRAFFIC_YELLOW
                st.markdown(kpi('趨勢', tr_txt, f'MA20={m20:.1f}', tr_c, tr_c),
                            unsafe_allow_html=True)
            else:
                st.markdown(kpi('趨勢', '-', '無MA數據', '#484f58'), unsafe_allow_html=True)
        with ind6:
            if bb2:
                bw_c = TRAFFIC_GREEN if bb2['bw'] < bb2['bw_mean'] * 0.7 else '#58a6ff'
                bw_txt = '帶寬極縮⚡' if bb2['bw'] < bb2['bw_mean'] * 0.7 else ('黏近上軌' if bb2['near_upper'] else f'均值{bb2["bw_mean"]:.1f}%')
                st.markdown(kpi('布林帶寬', f'{bb2["bw"]:.1f}%', bw_txt, bw_c, bw_c),
                            unsafe_allow_html=True)
            else:
                st.markdown(kpi('布林帶寬', '-', '數據不足', '#484f58'), unsafe_allow_html=True)

    # ── 動態大師建議(基於實際評分)──────────────────────
    _grade_label, _grade_color, _, _grade_emoji = health_grade(health2)
    _price_pos = ''
    if df2 is not None and 'MA20' in df2.columns and 'MA100' in df2.columns:
        _p2 = price2
        _m20 = float(df2['MA20'].iloc[-1])
        _m100 = float(df2['MA100'].iloc[-1])
        if _p2 > _m20 > _m100:
            _price_pos = '多頭排列，技術面強勢'
        elif _p2 < _m20 < _m100:
            _price_pos = '空頭排列，技術面偏弱'
        elif _p2 > _m100:
            _price_pos = '多箱整理，等待突破'
        else:
            _price_pos = '空箱整理，謹慎操作'
    _verdict_color = TRAFFIC_GREEN if health2 >= HEALTH_GRADE_A_MIN else (TRAFFIC_YELLOW if health2 >= HEALTH_GRADE_B_MIN else TRAFFIC_RED)
    _verdict = ('持股不動，佛系等待；所有指標均表現優異，繼續持有。' if health2 >= HEALTH_GRADE_A_MIN
                else ('等待突破訊號，不追高；多空交戰，方向未明，可分批布局。' if health2 >= HEALTH_GRADE_B_MIN
                      else '降低倉位或觀望；趨勢偏弱，以保本為優先。'))
    st.markdown(f"""<div style="background:#161b22;border:1px solid {_verdict_color};
border-left:4px solid {_verdict_color};border-radius:8px;padding:12px 14px;margin:8px 0;">
<span style="font-size:13px;font-weight:800;color:{_verdict_color};">{_grade_emoji} 大師綜合建議：{_verdict}</span>
<div style="font-size:11px;color:#8b949e;margin-top:4px;">技術位置：{_price_pos} | RSI={rsi2} | 量比={vr2} | KD=K{k2}/D{d2}</div>
</div>""", unsafe_allow_html=True)

    st.caption('📖 評分標準與指標說明 → 詳見「策略手冊」Tab')

    # ── v4.0 防守線 + 籌碼 + 套牢賣壓 ─────────────────────────────
    try:
        if df2 is not None and not df2.empty:
            # Build df for V4 engine (map column names)
            _v4_df = df2.copy()
            _col_map = {}
            for _c in _v4_df.columns:
                if _c in ('close', 'Close', 'adj close'):
                    _col_map[_c] = 'close'
                elif _c in ('open', 'Open'):
                    _col_map[_c] = 'open'
                elif _c in ('low', 'Low'):
                    _col_map[_c] = 'low'
                elif _c in ('volume', 'Volume', 'Trading_Volume'):
                    _col_map[_c] = 'volume'
            _v4_df = _v4_df.rename(columns=_col_map)

            # Try to get chip data from session state
            _inst2 = st.session_state.get('t2_inst', {})
            if '外資' in _inst2:
                _v4_df['foreign_net'] = _inst2.get('外資', 0)
                _v4_df['trust_net'] = _inst2.get('投信', 0)

            # Macro data from li_latest
            _li_for_v4 = st.session_state.get('li_latest')
            _v4_fut2 = 0.0
            _v4_pcr2 = 100.0
            if _li_for_v4 is not None and not _li_for_v4.empty:
                try:
                    _v4_fut2 = float(_li_for_v4.iloc[-1].get('外資大小', 0) or 0)
                except Exception:
                    pass
                try:
                    _v4_pcr2 = float(_li_for_v4.iloc[-1].get('選PCR', 100) or 100)
                except Exception:
                    pass

            _shares = st.session_state.get(f't2_shares_{sid2}', 1000000)
            _v4eng = V4StrategyEngine(_v4_df,
                                       {'vix': 15, 'foreign_futures': _v4_fut2, 'pcr': _v4_pcr2},
                                       max(int(_shares), 1))
            _v4rep = _v4eng.generate_report()

            st.markdown('---')
            _v4c1, _v4c2, _v4c3 = st.columns(3)

            # Task 4: Stop Loss
            with _v4c1:
                _sl = _v4rep['stop_loss']
                _sl_color = '#da3633' if _sl['stop_loss'] else '#484f58'
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid {_sl_color};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">🛡️ v4 防守價</div>'
                    f'<div style="font-size:20px;font-weight:900;color:{_sl_color};">'
                    f'{_sl["stop_loss"] or "N/A"} 元</div>'
                    f'<div style="font-size:11px;color:#8b949e;">MA20={_sl["ma20"]} | '
                    f'風險 {_sl["risk_pct"]}%</div>'
                    f'<div style="font-size:10px;color:#da3633;">跌破無條件停損</div>'
                    f'</div>', unsafe_allow_html=True)

            # Task 3: VPOC Resistance
            with _v4c2:
                _rs = _v4rep['resistance']
                _rs_color = '#da3633' if _rs['has_pressure'] else '#2ea043'
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid {_rs_color};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">📊 v4 上方賣壓</div>'
                    f'<div style="font-size:14px;font-weight:900;color:{_rs_color};">'
                    f'{"⚠️ 有解套賣壓" if _rs["has_pressure"] else "✅ 壓力有限"}</div>'
                    f'<div style="font-size:11px;color:#8b949e;">'
                    f'VPOC={_rs["vpoc_price"] or "N/A"} 元</div>'
                    f'</div>', unsafe_allow_html=True)

            # Task 1: Chip Ratio
            with _v4c3:
                _ch = _v4rep['chip_analysis']
                _ch_color = '#da3633' if '強勢' in _ch['signal'] else ('#2ea043' if '渙散' in _ch['signal'] else '#388bfd')
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid {_ch_color};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">💹 v4 相對籌碼</div>'
                    f'<div style="font-size:13px;font-weight:900;color:{_ch_color};">'
                    f'{_ch["signal"][:10]}</div>'
                    f'<div style="font-size:10px;color:#8b949e;">'
                    f'外本比 {_ch["foreign_ratio"] or "--"}%</div>'
                    f'</div>', unsafe_allow_html=True)
    except Exception as _v4_err:
        st.caption(f'v4.0 分析略過：{type(_v4_err).__name__}')

    # ── v5.0 RS強度 + 估值 + 布林偵測 ─────────────────────────────
    try:
        if df2 is not None and not df2.empty and len(df2) >= 20:
            _v5_r1, _v5_r2, _v5_r3 = st.columns(3)

            # Task 9: Bollinger Breakout
            with _v5_r1:
                _bb5 = detect_bollinger_breakout(df2)
                _bb5c = _bb5['color']
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid {_bb5c};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">📈 v5 布林偵測</div>'
                    f'<div style="font-size:13px;font-weight:900;color:{_bb5c};">'
                    f'{_bb5["signal"][:10]}</div>'
                    f'<div style="font-size:10px;color:#8b949e;">BW={_bb5["bw"]}%</div>'
                    f'</div>', unsafe_allow_html=True)

            # Task 10: 357 存股殖利率
            with _v5_r2:
                _dy5 = calc_dividend_yield_357(
                    price2 or 0,
                    pd.to_numeric(
                        (qtr2['EPS'] if qtr2 is not None and not qtr2.empty and 'EPS' in qtr2.columns
                         else pd.Series(dtype=float)).head(4),
                        errors='coerce').fillna(0).sum(),
                    avg_div2 / max(price2, 1) if avg_div2 and price2 else 0,
                    len([d for d in (st.session_state.get('t2_div_hist', []) or []) if d > 0])
                )
                _dy5c = _dy5['color']
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid {_dy5c};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">💰 v5 存股殖利率</div>'
                    f'<div style="font-size:14px;font-weight:900;color:{_dy5c};">'
                    f'{_dy5["est_yield"] or "N/A"}%</div>'
                    f'<div style="font-size:10px;color:#8b949e;">{_dy5["signal"][:8]}</div>'
                    f'</div>', unsafe_allow_html=True)

            # Task 5: 財報領先
            with _v5_r3:
                _fl5 = analyze_fundamental_leading(
                    cl2, None, None, None,
                    st.session_state.get(f't2_equity_{sid2}'))
                _fl5c = _fl5['color']
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid {_fl5c};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">🔬 v5 財報領先</div>'
                    f'<div style="font-size:13px;font-weight:900;color:{_fl5c};">'
                    f'{_fl5["signal"][:8]}</div>'
                    f'<div style="font-size:10px;color:#8b949e;">'
                    f'{"合約負債 ✅" if cl2 and cl2 > 0 else "無合約負債"}</div>'
                    f'</div>', unsafe_allow_html=True)
    except Exception as _v5e2:
        st.caption(f'v5.0 進階分析略過：{type(_v5e2).__name__}')
