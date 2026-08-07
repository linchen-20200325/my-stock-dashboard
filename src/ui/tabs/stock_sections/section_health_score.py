"""src/ui/tabs/stock_sections/section_health_score.py — A 健康度評分 + v4/v5 卡片(v18.407 U4 Phase 3-A).

從 tab_stock.py:1101-1368 抽出。含 A 健康度評分(SVG 量表 + 四維 + 6 技術指標
KPI + 綜合建議)、v4 防守線+VPOC+籌碼 3 卡、v5 布林+殖利率+財報領先 3 卡。

§8.2 layer:L5 UI Tab section helper(中風險:依賴 15+ locals / 8 helpers /
5 session_state keys,但無下游 state 寫回問題)。

對外 API:
- render_health_score_section(...) -> None
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
from shared.signal_thresholds import (
    BB_BW_SHRINK_WARN_RATIO,  # Phase 2 Batch 5b v18.429:布林帶寬收縮 warn SSOT
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
# v19.179 B1-b:配息年數改由實際 yearly 資料數出(原讀一個從沒被寫過的 session key)
from src.compute.strategy.v5_modules import count_dividend_paying_years
from src.ui.render import STRATEGY_TECHNICAL, kpi, strategy_conclusion  # v19.174 去識別化
from src.ui.render.app_render import render_health_score


def attach_chip_columns(df):
    """把 df2 的逐日「外資 / 投信」欄（張）對映成 V4 引擎要的
    `foreign_net` / `trust_net`（純函式，回**新的** DataFrame）。

    兩欄任一缺席 → **不建欄**（引擎會回「⚪ 無籌碼資料」）。§1：寧可讓下游
    誠實說「沒有籌碼資料」，也不要用單日值廣播成整欄假裝有 5 日累計。

    D1 v19.185 抽出的理由：舊碼在 render 裡寫
    `_v4_df['foreign_net'] = st.session_state['t2_inst'].get('外資', 0)` ——
    把**一天**的淨買量廣播到每一列，於是引擎的 `tail(5).sum()` 變成
    「最後一日 × 5」，`tail(3)` 的「連續3日流入」也只反映最新一天。
    抽成純函式後，「5 日加總必須等於 5 天的實際和」可以被測試直接驗。
    """
    _out = df.copy()
    if '外資' in _out.columns and '投信' in _out.columns:
        _out['foreign_net'] = pd.to_numeric(_out['外資'], errors='coerce').fillna(0)
        _out['trust_net'] = pd.to_numeric(_out['投信'], errors='coerce').fillna(0)
    return _out


def render_health_score_section(
    sid2: str, health2, details2,
    df2, price2, qtr2, yearly2, avg_div2,
    rsi2, vr2, ibs2, k2, d2, bb2, vcp2, cl2,
    bb_breakout2=None,  # B9: pre-computed detect_bollinger_breakout result
    capex2=None,        # D1 v19.185: CF 季資本支出(元) — v5 財報領先卡真正的輸入
    capital2=None,      # D1 v19.185: 股本(元,_precompute_xsec 已算) — 同上
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
    st.markdown(strategy_conclusion(STRATEGY_TECHNICAL, f'{sid2} 健康度 {health2:.0f}分', _ha, _hb),
                unsafe_allow_html=True)

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
            # S2 v19.78(第二份 review):歷史 <100 根時 rolling MA100 為 NaN,
            # `p > m20 > NaN` 靜默 False → 一路 fallthrough 誤標「空箱整理」。
            # NaN 顯式判別,與「真的空箱」區分(§4.6 新上市股票)。
            if (df2 is not None and 'MA20' in df2.columns and 'MA100' in df2.columns
                    and pd.notna(df2['MA20'].iloc[-1]) and pd.notna(df2['MA100'].iloc[-1])):
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
                st.markdown(kpi('趨勢', '-', '無MA數據(或均線未成形)', '#484f58'), unsafe_allow_html=True)
        with ind6:
            if bb2:
                bw_c = TRAFFIC_GREEN if bb2['bw'] < bb2['bw_mean'] * BB_BW_SHRINK_WARN_RATIO else '#58a6ff'
                bw_txt = '帶寬極縮⚡' if bb2['bw'] < bb2['bw_mean'] * BB_BW_SHRINK_WARN_RATIO else ('黏近上軌' if bb2['near_upper'] else f'均值{bb2["bw_mean"]:.1f}%')
                st.markdown(kpi('布林帶寬', f'{bb2["bw"]:.1f}%', bw_txt, bw_c, bw_c),
                            unsafe_allow_html=True)
            else:
                st.markdown(kpi('布林帶寬', '-', '數據不足', '#484f58'), unsafe_allow_html=True)

    # ── 動態綜合建議(基於實際評分)──────────────────────
    _grade_label, _grade_color, _, _grade_emoji = health_grade(health2)
    _price_pos = ''
    # S2 v19.78:同上 — MA 為 NaN 時不可判「空箱整理」,顯式標歷史不足
    if (df2 is not None and 'MA20' in df2.columns and 'MA100' in df2.columns
            and (pd.isna(df2['MA20'].iloc[-1]) or pd.isna(df2['MA100'].iloc[-1]))):
        _price_pos = '均線未成形（歷史不足），趨勢不判定'
    elif df2 is not None and 'MA20' in df2.columns and 'MA100' in df2.columns:
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
<span style="font-size:13px;font-weight:800;color:{_verdict_color};">{_grade_emoji} 綜合建議：{_verdict}</span>
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

            # ── D1 v19.185（§4.1 量綱 / §1 Fail Loud）：籌碼欄改吃 df2 的**逐日序列** ──
            # 舊碼 `_v4_df['foreign_net'] = _inst2.get('外資', 0)` 把 session 裡的
            # **單日**外資淨買量廣播成整欄。V4 `calc_relative_chips()` 做的是
            # `df.tail(5)['foreign_net'].sum()`，於是「近5日外資淨買」= 最後一日 × 5
            # （5 倍高估）；`tail(3)` 的連續判定也因為三根都同值而變成 0 或 3，
            # 「（連續3日流入✅）」只要**最新一天**達標就會掛上 —— 用 1 天的事實
            # 宣告 3 天的結論。
            # df2 本來就有逐日「外資」「投信」欄（單位：張，data_loader T86/TPEX merge），
            # 直接用即可；欄位不存在時**不建欄**，讓引擎回「⚪ 無籌碼資料」而不是
            # 用單日值偽造 5 日累計。（判定抽在 `attach_chip_columns`，可單測。）
            _v4_df = attach_chip_columns(_v4_df)

            # Macro data from li_latest
            # D1 v19.185（§3.3 反捏造）：原碼把 `'vix': 15` 直接寫死在 UI 層 ——
            # 那是 V4 引擎「抓不到 VIX 時的安全預設」，不該由畫面偽造成一個
            # 已知值。真值就在 session（`macro_info.vix.current`，與建議持股油門
            # 同源）；取不到就傳 None，讓引擎走它自己文件化的 fallback。
            _mi_v4 = st.session_state.get('macro_info') or {}
            _vix_obj_v4 = _mi_v4.get('vix') if isinstance(_mi_v4, dict) else None
            _v4_vix2 = None
            if isinstance(_vix_obj_v4, dict):
                try:
                    _vix_f = float(_vix_obj_v4.get('current'))
                    _v4_vix2 = _vix_f if _vix_f == _vix_f else None   # NaN guard
                except (TypeError, ValueError):
                    _v4_vix2 = None
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

            # ── D1 v19.185（§1 Fail Loud）：發行張數未知時**不得**用 1,000,000 張假裝 ──
            # 外本比 = 近5日外資淨買 ÷ 發行張數。台積電 2,593 萬張、小型股 2 萬張，
            # 用固定 1,000,000 張當分母算出來的百分比與門檻（0.5% / 0.3% / 0.1%）
            # 完全對不上，卻照樣印成一個具體數字。改為：股本抓到才算，抓不到就
            # 明講「股本未取得」（`t2_shares_{sid}` 由 tab_stock 於 capital>0 時寫入）。
            _shares_raw = st.session_state.get(f't2_shares_{sid2}')
            try:
                _shares = int(_shares_raw) if _shares_raw is not None else 0
            except (TypeError, ValueError):
                _shares = 0
            _shares_known = _shares > 0
            _v4eng = V4StrategyEngine(_v4_df,
                                       {'vix': _v4_vix2, 'foreign_futures': _v4_fut2,
                                        'pcr': _v4_pcr2},
                                       max(_shares, 1))
            _v4rep = _v4eng.generate_report()

            st.markdown('---')
            _v4c1, _v4c2, _v4c3 = st.columns(3)

            # Task 4: Stop Loss
            # v19.180 B2-a（§1 Fail Loud, Never Fake）：防守價可能**高於現價**
            # （MA20 與爆量紅K低點同時在現價之上）。原本無條件印
            # 「風險 {risk_pct}%」，跌破時就變成「風險 -1.1%」，使用者讀成
            # 「風險很小」，實際語意卻是「你已經該出場了」。改為讀 L2 引擎給的
            # `is_breached` 旗標分三態渲染，UI 不自己比大小（§2.1 SSOT）。
            with _v4c1:
                _sl = _v4rep['stop_loss']
                _sl_val = _sl.get('stop_loss')
                _sl_breach = _sl.get('is_breached')
                _sl_risk = _sl.get('risk_pct')
                if _sl_val is None or _sl_breach is None:
                    # 資料不足 / 現價無效 → 灰底 N/A，**不填 0 也不猜**（§1）
                    _sl_color, _sl_bg = TRAFFIC_NEUTRAL, '#0d1117'
                    _sl_main = 'N/A'
                    _sl_sub = _sl.get('msg', '無法計算防守線')
                    _sl_foot = ''
                elif _sl_breach:
                    _sl_color, _sl_bg = TRAFFIC_RED, '#2a0d0d'
                    _sl_main = f'🚨 已跌破 {_sl_val} 元'
                    _sl_sub = (f'MA20={_sl["ma20"]} | 現價低於防守價 '
                               f'{abs(_sl_risk):.1f}%' if _sl_risk is not None
                               else f'MA20={_sl["ma20"]}')
                    _sl_foot = '依規則無條件停損'
                else:
                    _sl_color, _sl_bg = '#da3633', '#0d1117'
                    _sl_main = f'{_sl_val} 元'
                    _sl_sub = (f'MA20={_sl["ma20"]} | 下檔緩衝 {_sl_risk:.1f}%'
                               if _sl_risk is not None else f'MA20={_sl["ma20"]}')
                    _sl_foot = '跌破無條件停損'
                _sl_foot_html = (f'<div style="font-size:10px;color:{_sl_color};">'
                                 f'{_sl_foot}</div>' if _sl_foot else '')
                st.markdown(
                    f'<div style="background:{_sl_bg};border:1px solid {_sl_color};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">🛡️ v4 防守價</div>'
                    f'<div style="font-size:20px;font-weight:900;color:{_sl_color};">'
                    f'{_sl_main}</div>'
                    f'<div style="font-size:11px;color:#8b949e;">{_sl_sub}</div>'
                    f'{_sl_foot_html}'
                    f'</div>', unsafe_allow_html=True)

            # Task 3: VPOC Resistance
            # ── D1 v19.185（§1 綠燈不代表算過）──────────────────────────────
            # 引擎在「資料 < 60 日」與「VPOC 計算失敗」兩種情況下都回
            # `vpoc_price=None, has_pressure=False`。舊碼只看 `has_pressure`，
            # 於是新股 / 壞資料一律顯示綠色的「✅ 壓力有限」，旁邊才小小地寫
            # 「VPOC=N/A 元」—— 使用者讀到的是「查過了，上方沒壓力」。
            # 三態：算得出才給紅/綠，算不出一律 ⚪ 未評估並附引擎給的原因。
            with _v4c2:
                _rs = _v4rep['resistance']
                _rs_known = _rs.get('vpoc_price') is not None
                if not _rs_known:
                    _rs_color = TRAFFIC_NEUTRAL
                    _rs_main = '⚪ 未評估'
                    _rs_sub = str(_rs.get('msg') or '無法計算 VPOC').lstrip('⚪ ')
                else:
                    _rs_color = '#da3633' if _rs['has_pressure'] else '#2ea043'
                    _rs_main = '⚠️ 有解套賣壓' if _rs['has_pressure'] else '✅ 壓力有限'
                    _rs_sub = f'VPOC={_rs["vpoc_price"]} 元'
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid {_rs_color};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">📊 v4 上方賣壓</div>'
                    f'<div style="font-size:14px;font-weight:900;color:{_rs_color};">'
                    f'{_rs_main}</div>'
                    f'<div style="font-size:11px;color:#8b949e;">{_rs_sub}</div>'
                    f'</div>', unsafe_allow_html=True)

            # Task 1: Chip Ratio
            with _v4c3:
                _ch = _v4rep['chip_analysis']
                if not _shares_known:
                    # §1：分母未知 → 外本比與其訊號都沒有意義，不印任何百分比。
                    st.markdown(
                        f'<div style="background:#0d1117;border:1px solid {TRAFFIC_NEUTRAL};'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:10px;color:#484f58;">💹 v4 相對籌碼</div>'
                        f'<div style="font-size:13px;font-weight:900;color:{TRAFFIC_NEUTRAL};">'
                        f'⚪ 未評估</div>'
                        f'<div style="font-size:10px;color:#8b949e;">'
                        f'股本(發行張數)未取得 → 外本比無分母</div>'
                        f'</div>', unsafe_allow_html=True)
                else:
                    _ch_color = '#da3633' if '強勢' in _ch['signal'] else ('#2ea043' if '渙散' in _ch['signal'] else '#388bfd')
                    st.markdown(
                        f'<div style="background:#0d1117;border:1px solid {_ch_color};'
                        f'border-radius:8px;padding:12px;text-align:center;">'
                        f'<div style="font-size:10px;color:#484f58;">💹 v4 相對籌碼</div>'
                        f'<div style="font-size:13px;font-weight:900;color:{_ch_color};">'
                        f'{_ch["signal"][:10]}</div>'
                        f'<div style="font-size:10px;color:#8b949e;">'
                        f'外本比 {_ch["foreign_ratio"] if _ch["foreign_ratio"] is not None else "--"}%</div>'
                        f'</div>', unsafe_allow_html=True)
    except Exception as _v4_err:
        st.caption(f'v4.0 分析略過：{type(_v4_err).__name__}')

    # ── v5.0 RS強度 + 估值 + 布林偵測 ─────────────────────────────
    try:
        if df2 is not None and not df2.empty and len(df2) >= 20:
            _v5_r1, _v5_r2, _v5_r3 = st.columns(3)

            # Task 9: Bollinger Breakout — B9: 使用從 tab_stock 預先計算的結果
            with _v5_r1:
                _bb5 = bb_breakout2 if bb_breakout2 is not None else detect_bollinger_breakout(df2)
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
            # v19.179 B1-b（CLAUDE.md §4.1 量綱 / §2.1 SSOT / §1 Fail Loud）:
            #   舊碼第 3 個位置參數傳 `avg_div2 / max(price2, 1)` —— 那是**殖利率**，
            #   但函式契約要的是**配發率**，函式內再 `eps × payout / price` ⇒ 除以
            #   股價兩次 ⇒ 2330 實機顯示 0.01%（真值 0.59%），並被判成「🔴 超貴」。
            #   舊碼第 4 個參數讀 `st.session_state['t2_div_hist']`，該 key 全站沒有
            #   任何寫入點 ⇒ 配息年數恆為 0（把「沒查」講成「查到 0 年」）。
            #   現在：直接餵已在手的 avg_div2（元）+ yearly2（近 5 年配息），
            #   分級與 B 區 357 共用 `classify_stock_357_price`，兩張卡不可能再打架。
            with _v5_r2:
                _dy5 = calc_dividend_yield_357(
                    price2 or 0,
                    avg_div_twd=avg_div2,
                    div_years=count_dividend_paying_years(yearly2),
                )
                _dy5c = _dy5['color']
                # §1：est_yield 為 None＝未評估，顯示「未評估」而不是 0%／N/A%
                _dy5_val = ('未評估' if _dy5['est_yield'] is None
                            else f'{_dy5["est_yield"]:.2f}%')
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid {_dy5c};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">💰 v5 存股殖利率</div>'
                    f'<div style="font-size:14px;font-weight:900;color:{_dy5c};">'
                    f'{_dy5_val}</div>'
                    f'<div style="font-size:10px;color:#8b949e;">{_dy5["signal"][:12]}</div>'
                    f'</div>', unsafe_allow_html=True)

            # Task 5: 財報領先
            # ── D1 v19.185（§1 Fail Loud）：本卡原本是**死區** ───────────────
            # 舊碼 `analyze_fundamental_leading(cl2, None, None, None,
            #        st.session_state.get(f't2_equity_{sid2}'))`：
            #   • 第 2 參數 cl_prev=None  → 引擎內 `cl_yoy` 恆 None → `cl_growth` 恆假
            #   • 第 3 參數 capex_now=None → `capex_ratio` 恆 None → `capex_ok` 恆假
            #   • 第 5 參數讀 `t2_equity_{sid}` —— **全站零寫入點**（幽靈 key）
            # 三個判定用的輸入全是 None ⇒ 引擎只可能回落到 else 分支
            # 「⚪ 一般水準 / 合約負債與資本支出未達龍多標準」。也就是說：
            # 這張卡對**任何**股票、任何財報都印同一句話，而那句話還宣稱
            # 「未達標準」= 把「沒算」講成「算過不達標」。
            # 現在餵入真的有的兩個輸入（CF 季資本支出 + 股本），「🟡 積極擴張」
            # 分支終於可能成立；cl_prev 仍缺（需去年同期合約負債）→ 在卡片上
            # **明說 YoY 未計**，不讓使用者把它讀成「已比較過 YoY」。
            with _v5_r3:
                _equity_v5 = capital2 if (capital2 and capital2 > 0) else None
                _capex_v5 = capex2 if (capex2 and capex2 > 0) else None
                _fl5 = analyze_fundamental_leading(cl2, None, _capex_v5, None, _equity_v5)
                _fl5c = _fl5['color']
                _fl5_notes = ['合約負債 ✅' if cl2 and cl2 > 0 else '無合約負債']
                if _capex_v5 is None or _equity_v5 is None:
                    _fl5_notes.append('資本支出/股本未評估')
                _fl5_notes.append('YoY 未計(缺去年同期)')
                st.markdown(
                    f'<div style="background:#0d1117;border:1px solid {_fl5c};'
                    f'border-radius:8px;padding:12px;text-align:center;">'
                    f'<div style="font-size:10px;color:#484f58;">🔬 v5 財報領先</div>'
                    f'<div style="font-size:13px;font-weight:900;color:{_fl5c};">'
                    f'{_fl5["signal"][:8]}</div>'
                    f'<div style="font-size:10px;color:#8b949e;">'
                    f'{" · ".join(_fl5_notes)}</div>'
                    f'</div>', unsafe_allow_html=True)
    except Exception as _v5e2:
        st.caption(f'v5.0 進階分析略過：{type(_v5e2).__name__}')
