"""src/ui/tabs/macro/section_overview.py — 戰情概覽(P3-D6 v18.390 抽出)。

原 tab_macro.py:335-368 inline。「一眼看清今日市場」2-column KPI 卡。

closure params:
- _tl_eff_reg: str | None   有效 traffic light regime(來自紅綠燈卡)
- _show_market_data: bool   資料載入 gate

session_state 只讀(load_section_inputs SSOT),無寫。
"""
from __future__ import annotations

import streamlit as st

from shared.colors import (
    TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW,
)
from shared.signal_thresholds import BREADTH_BULL_PCT, BREADTH_NEUTRAL_PCT


def render_section_overview(_tl_eff_reg, _show_market_data: bool) -> None:
    """渲染戰情概覽 2-col KPI(原 tab_macro line 335-368)。"""
    from src.services import load_section_inputs as _load_si_ov
    from src.ui.render import beginner_kpi, kpi
    # P0-C：廣度名詞定義 SSOT（正式名 / 白話 / 公式 / 單位皆取自此，不自寫文案）
    from src.ui.render.ui_widgets import BREADTH_JINGQI

    _ov_inp = _load_si_ov(st.session_state)
    _ov_mkt = _ov_inp.mkt_info or {}
    _ov_jq = _ov_inp.jingqi_info or {}
    _ov_cd = _ov_inp.cl_data or {}

    # v18.316 去重:外資 / 融資 / 年線乖離 / 持股 由下方「5 分鐘清單」唯一表達,
    # 此處只留「大盤多空方向」+「旌旗指數」(後者清單未涵蓋)。
    # (P0-C:原註解寫「全市場健康度(旌旗)」,該名已退役 —— 見下方 with 區塊說明)
    if _show_market_data and any([_ov_mkt, _ov_jq, _ov_cd]):
        _ov_cols = st.columns(2)
        with _ov_cols[0]:
            # ── C1 v19.182:唯一出口 + 移除捏造的 'neutral' 預設 ────────────
            # 原碼 `_tl_eff_reg or _ov_mkt.get('regime','neutral')`:
            #   (a) fallback 到 raw `mkt_info['regime']` = 第 2 個 producer ——
            #       紅綠燈判 🔴 而 mkt_info 是 bull 時,這張卡會印「🟢 多頭」;
            #   (b) 兩層 `'neutral'` 預設 = 拿不到資料時**捏造**「震盪」這個結論
            #       (§1:不知道 ≠ 判斷為震盪)。
            # 現在 `_tl_eff_reg` 已是 canonical 結論(見 section_traffic_light),
            # 拿不到就誠實印 ⬜ 未評估。
            _ov_reg = _tl_eff_reg or 'unknown'
            _ov_lbl = {'bull': '🟢 多頭', 'neutral': '🟡 震盪',
                       'bear': '🔴 空頭防禦'}.get(_ov_reg, '⬜ 未評估')
            _ov_clr = (TRAFFIC_GREEN if _ov_reg == 'bull' else
                       TRAFFIC_RED if _ov_reg == 'bear' else
                       TRAFFIC_YELLOW if _ov_reg == 'neutral' else TRAFFIC_NEUTRAL)
            _ov_note = ('大盤多空方向（持股比例見下方清單）' if _ov_reg != 'unknown'
                        else '總經尚未評估 — 請先按「🚀 一鍵更新全部數據」')
            # 順手修一個畫面上的垃圾字串（C1 附帶，非 regime 相關）：
            # `beginner_kpi(title, value, plain_meaning, color, tip)` 的第 5 個
            # 位置參數是 **tip**，舊碼卻傳了背景色字面值 `'#0d1117'`，於是卡片
            # 底下實際印出「💡 #0d1117」。這裡直接不傳 tip。
            st.markdown(beginner_kpi(
                '今日市場狀態', _ov_lbl, _ov_note, _ov_clr),
                unsafe_allow_html=True)
        # 旌旗指數(市場廣度家族 — 5 分鐘清單未涵蓋,保留唯一)
        # ── P0-C 定名（2026-08-05）────────────────────────────────
        # 原標題「全市場健康度」+ 說明「有幾%的股票站在均線之上」兩處都要改：
        #   1. 標題退役 —— 同一個標題在 section_short 貼的是「當日上漲佔比」、
        #      在紅綠燈卡貼的是「綜合健康度/100」(0.6×旌旗+0.4×大盤評分)，
        #      一名三義。清單見 ui_widgets.BREADTH_DEPRECATED_TITLES。
        #   2. 說明是**捏造**（§1 反捏造）—— 全站無任何一行在算「站上均線家數比」；
        #      jingqi_info['avg'] 實為「上漲佔比的 5 日均」(jingqi_calc.py:43)。
        # 名詞定義單一出處：ui_widgets.BREADTH_JINGQI（本檔不再自寫文案）。
        with _ov_cols[1]:
            _ov_jqp = _ov_jq.get('avg', None) if _ov_jq else None
            if _ov_jqp is not None:
                _ov_jc = (TRAFFIC_GREEN if _ov_jqp >= BREADTH_BULL_PCT
                          else (TRAFFIC_YELLOW if _ov_jqp >= BREADTH_NEUTRAL_PCT
                                else TRAFFIC_RED))
                # §1：代理值 / 備援源必須看得見，不可靜默當成主源呈現。
                # jingqi_calc 寫入的 source：'ADL'(yfinance ^TWII 估算,is_proxy)
                # / '大盤估算'(備援) ；section_short fallback 寫 'TWSE即時'。
                _ov_src = str(_ov_jq.get('source') or '')
                _ov_tip = f'{BREADTH_JINGQI.formula}；≥{BREADTH_BULL_PCT:.0f}% 才適合積極買進'
                if _ov_src and _ov_src != 'ADL':
                    _ov_tip = f'⚠️ 代理值（來源：{_ov_src}）　·　{_ov_tip}'
                st.markdown(beginner_kpi(
                    BREADTH_JINGQI.canonical, f'{_ov_jqp:.0f}{BREADTH_JINGQI.unit}',
                    BREADTH_JINGQI.plain, _ov_jc,
                    _ov_tip), unsafe_allow_html=True)
            else:
                st.markdown(kpi(BREADTH_JINGQI.canonical, '--', '掃描後顯示',
                                '#484f58', '#0d1117'),
                            unsafe_allow_html=True)
        st.markdown('')
