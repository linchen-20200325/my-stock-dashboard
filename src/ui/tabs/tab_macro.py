"""TAB 總經紅綠燈 + 多指標儀表板 — 從 app.py 抽出（PR P2-B Phase 5-D，最終巨型 TAB）

依賴策略
========
- Top-level: streamlit（最穩定）
- 函式內 late import 44 個依賴，避免循環 import：
  * stdlib: datetime, json, os, pandas, plotly, concurrent.futures
  * 設定: config.FINMIND_TOKEN
  * 外部模組:
    - macro_state_locker: MacroStateLocker / calculate_system_state / load_macro_state
    - v4_strategy_engine: V4StrategyEngine
    - daily_checklist (17): _fetch_otc_via_finmind / calc_stats
      / evaluate_market_status_v4_final / fetch_adl / fetch_institutional
      / fetch_margin_balance / fetch_single / multi_chart / section_header
      / sparkline / stat_card / COLORS_7 / INTL_MAP / INTL_UNIT
      / TECH_MAP / TW_MAP / TW_UNIT
    - macro_alert (3): check_macro_alerts / fetch_macro_snapshot / render_macro_alerts
    - market_strategy: get_market_assessment
    - leading_indicators: build_leading_fast / render_leading_table
    - ui_widgets: beginner_kpi / kpi / teacher_conclusion
  * app.py 內部 (5): _bps / _fetch_macro_news / _get_fm_token / _tw_now_str / gemini_call

呼叫端
======
- app.py: `with tab_macro: render_tab_macro()`
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW
# v18.325 PR-C: 融資餘額紅線改用既有 SSOT（原散落 inline 3400，§3.3 反捏造）
# v18.326 PR-D: 融資黃線 + 市場廣度門檻 SSOT
from shared.signal_thresholds import (
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
    BREADTH_BULL_PCT,
    BREADTH_NEUTRAL_PCT,
    BREADTH_BEAR_PCT,
)

from src.compute.macro import calc_traffic_light, rp_entry, rp_scalar, rp_ts
from src.ui.tabs.tab_helpers import safe_get



# F-7.1a v18.363:8 個頂部 helper 抽至 src/ui/tabs/macro/helpers.py(LOC 5387→4953)
from src.ui.tabs.macro.helpers import (  # noqa: F401
    _radar_threshold_lines,
    _make_radar_sparkline,
    _render_macro_indicator_card,
    _render_global_risk_bucket,
    _render_china_drag_panel,
    render_five_bucket_bar,
    render_macro_bucket_summary_bar,
    add_danger_hlines,
)
# F-7.1 B-1 v18.364:4 個 inner def 抽至 src/ui/tabs/macro/handlers.py
from src.ui.tabs.macro.handlers import (  # noqa: F401
    _macro_session_reset,
    _on_refresh_click,
    _on_force_clear_click,
    _render_traffic_light,
)
# F-7.1 B-2 v18.365:Section 6 短線急殺桶抽至 macro/section_short.py(LOC 4833→4521)
from src.ui.tabs.macro.section_short import render_section_short  # noqa: F401
# F-7.1 B-3 v18.366:§十一 News AI 總裁決抽至 macro/section_news_ai.py(P2 v18.389 rename)
from src.ui.tabs.macro.section_news_ai import render_section_news_ai  # noqa: F401
# F-7.1 B-4 v18.367:Section 4 (§八) 中期/總經拼圖抽至 macro/section_mid.py(LOC 4230→3797)
from src.ui.tabs.macro.section_mid import render_section_mid  # noqa: F401
# F-7.1 B-5 v18.368:Section 3 長期桶 LONG 抽至 macro/section_long.py(LOC 3797→3402)
from src.ui.tabs.macro.section_long import render_section_long  # noqa: F401
# F-7.1 B-S2 v18.385:Section 2 拐點偵測 / 市場狀態抽至 macro/section_state.py(LOC 3402→3025)
from src.ui.tabs.macro.section_state import render_section_state  # noqa: F401
# F-7.1 B-S8-A v18.388:Section 3 籌碼桶抽至 macro/section_chips.py(LOC 3034→~2475)
from src.ui.tabs.macro.section_chips import render_section_chips  # noqa: F401
# F-7.1 B-S8-B v18.388:§九 跨桶 AI 抽至 macro/section_cross_ai.py(P2 v18.389 rename)
from src.ui.tabs.macro.section_cross_ai import render_section_cross_ai  # noqa: F401
# P3-D5 v18.390:五桶 bar 抽至 macro/section_summary_bar.py
from src.ui.tabs.macro.section_summary_bar import render_five_bucket_summary  # noqa: F401
# P3-D6 v18.390:戰情概覽抽至 macro/section_overview.py
from src.ui.tabs.macro.section_overview import render_section_overview  # noqa: F401



def render_tab_macro():
    # ─ Late imports（避免循環 import）─
    import datetime
    import json
    import os
    import pandas as pd
    import plotly.graph_objects as go
    from concurrent.futures import ThreadPoolExecutor, as_completed
    # 外層 trio executor(_job_m1b/_job_bias/_job_macro 並發,L2176-2199)需要 as_completed
    # 別名與 concurrent.futures.TimeoutError;原本只在 _job_macro 內部定義,
    # 外層 200s timeout 觸發 except 時 → NameError 全頁炸。函式入口無條件定義。
    # v18.341 PR-L1 漏補修正(從 main 帶入)。
    from concurrent.futures import TimeoutError as _ConcFutTimeout
    _asc_mc = as_completed
    from src.config import FINMIND_TOKEN  # F-6.1 後正確 path
    # 外部模組
    from src.services import (
        MacroStateLocker, calculate_system_state, load_macro_state,
    )
    from src.compute.strategy import V4StrategyEngine
    from src.services import (
        _fetch_otc_via_finmind, calc_stats, evaluate_market_status_v4_final,
        fetch_adl, fetch_flow_snapshot, fetch_institutional, fetch_margin_balance,
        fetch_single, multi_chart, section_header, sparkline, stat_card,
        COLORS_7, INTL_MAP, INTL_UNIT, TECH_MAP, TW_MAP, TW_UNIT,
    )
    from src.data.macro import (
        check_macro_alerts, fetch_macro_snapshot, render_macro_alerts,
    )
    from src.services import get_market_assessment
    from src.data.macro import render_leading_table
    from src.ui.render import beginner_kpi, cond_badge, kpi, teacher_conclusion
    # app.py 內部 helper（v18.192：還原 section 十一 → 重新需要 _fetch_macro_news / gemini_call）
    from app import (
        _bps, _fetch_macro_news, _get_fm_token, _tw_now_str, gemini_call,
    )

    # F-7.1 B-1:_macro_session_reset / _on_refresh_click / _on_force_clear_click 抽至 src/ui/tabs/macro/handlers.py
    # ── Empty state gate(v18.286)──────────────────────────────
    # 對齊 Fund tab1 行為:未載入總經資料前只顯示標題+按鈕,避免說明卡擾人
    _macro_loaded = bool(
        st.session_state.get('cl_data')
        or st.session_state.get('mkt_info')
        or st.session_state.get('chips_loaded')
    )
    # v18.315：一鍵更新按鈕移到「最外層」(總是顯示在最上面)，取代原「空狀態 + 主流程
    # 埋在中間」兩顆同 key 按鈕(user 反饋:應在最外層就開始跑、內層按鈕取消)。
    # do_refresh 供下方主流程「點更新 → 清舊燈號 + 重抓」沿用。
    do_refresh = st.button(
        '🚀 一鍵更新全部數據（總經 + 籌碼 + 先行指標）',
        key='cl_refresh',
        on_click=_on_refresh_click,
        use_container_width=True,
        type='primary',
        help='抓取總經 / 籌碼 / 先行指標（吃 30 分內暖快取，通常數秒；冷啟動約 30~50 秒）。'
             'v18.329：不再清掉個股 / ETF / 健診等其他頁快取。',
    )
    # v18.329：強制重抓另立按鈕（對齊 Fund「🆕 強制重抓最新（清快取）」）。
    # 正常更新走暖快取＝快；要零殘留才按這顆（會一併清掉其他頁快取，較慢）。
    do_force = st.button(
        '🆕 強制重抓最新（清快取）',
        key='cl_force_refresh',
        on_click=_on_force_clear_click,
        use_container_width=True,
        help='完全清除快取（pkl + st.cache_data + proxy）後重抓，確保零殘留；'
             '較慢，且會一併清掉個股 / ETF 等其他頁快取。',
    )
    do_refresh = bool(do_refresh or do_force)
    if do_refresh:
        st.session_state['chips_loaded'] = True
        st.session_state.pop('cl_data', None)

    if not _macro_loaded:
        st.markdown(
            '<div style="padding:12px 0 8px;">'
            '<span style="font-size:22px;font-weight:900;color:#e6edf3;">🌍 總經位階評估</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.info('👉 點擊上方按鈕載入總經資料')
        return

    # ════════════════════════════════════════════════════════
    # 【模組一】紅綠燈決策儀表板（st.empty 佔位符修復版）
    # 修復：先挖洞（placeholder）→ 資料到位後回填，杜絕未審先判
    # ════════════════════════════════════════════════════════

    # 紅綠燈計算邏輯已抽至 macro_helpers.calc_traffic_light（Phase 7A-Ext）

    # F-7.1 B-1:_render_traffic_light 抽至 src/ui/tabs/macro/handlers.py
    # ── ① 最頂端先建立佔位符（關鍵：必須在任何計算前建立）───
    _tl_placeholder = st.empty()

    # ── ② 讀取快取（快取新鮮才顯示燈號，否則顯示等待，避免誤導）──
    # 設計原則：燈號必須反映「當前資料」而非「過期快取」
    # 30 分鐘內的快取視為有效；超過則要求重新更新
    import datetime as _dt_tl
    _cl_ts_str = st.session_state.get('cl_ts', '')
    _cache_fresh = False
    if _cl_ts_str:
        try:
            _cl_ts_dt = _dt_tl.datetime.strptime(_cl_ts_str[:16], '%Y-%m-%d %H:%M')
            _age_min  = (_dt_tl.datetime.now() - _cl_ts_dt).total_seconds() / 60
            _cache_fresh = _age_min < 30   # 30 分鐘內視為新鮮
        except Exception:
            _cache_fresh = False

    # 刷新進行中時隱藏舊資料（避免更新期間顯示過期結論）
    _is_refreshing = st.session_state.get('_is_refreshing', False)
    _show_market_data = _cache_fresh and not _is_refreshing

    if _cache_fresh and not _is_refreshing:
        # 快取新鮮 → 立即計算燈號（含資料新鮮度標記）
        # C1-D v18.290:走 section_inputs SSOT(對齊 5 桶 + 戰情概覽 + 今日作戰室)
        from src.services import load_section_inputs as _load_si_tl
        _tl_inp      = _load_si_tl(st.session_state)
        _tm_mkt_init = _tl_inp.mkt_info or {}
        _tm_jq_init  = _tl_inp.jingqi_info or {}
        _tm_cd_init  = _tl_inp.cl_data or {}
        _tm_li_init  = _tl_inp.li_latest
        _tl_init     = calc_traffic_light(_tm_mkt_init, _tm_jq_init, _tm_cd_init, _tm_li_init)
        _render_traffic_light(_tl_placeholder, _tl_init, _tm_mkt_init)
    else:
        # 無快取 or 快取過期 → 顯示等待狀態，不顯示誤導性燈號
        age_note = f'（上次更新 {_age_min:.0f} 分鐘前，已過期）' if _cl_ts_str and not _cache_fresh else '（尚無資料）'
        _tl_placeholder.warning(
            f'⏳ **燈號等待中 {age_note}**\n\n'
            '燈號將在「🚀 一鍵更新全部數據」完成後自動亮起。\n'
            '確保資料是今日最新，再做投資判斷。',
        )
        _tl_init = None

    # 統一有效市場 regime（確保交通燈與下方卡片結論一致）
    # 🔴 對應 bear，🟢 對應 bull，🟡 對應 neutral
    _tl_eff_reg = {'🔴': 'bear', '🟢': 'bull', '🟡': 'neutral'}.get(
        (_tl_init or {}).get('icon', ''), None
    )

    # ── 同步寫入 session_state（其他頁面需要的值）────────────
    if _tl_init:
        st.session_state['warroom_summary'] = {
            'traffic_light': _tl_init['label'],
            'health_score':  _tl_init['health'],
            'regime': _tm_mkt_init.get('regime', 'neutral'),
            'market_score':  _tl_init['score'],
            'jingqi_avg':    _tl_init['jqavg'],
            'leek_index':    _tl_init['leek'],
            'foreign_net_bn':_tl_init['fnet'],
            'futures_net':   _tl_init['fut_net'],
            'confidence_pct':_tl_init['conf'],
        }

    # ── v18.171 長期 vs 短期 雙視角總經面板（上移至紅綠燈卡正下方）─────
    # 長期 (12M)：景氣大循環位階；短期 (1Q)：對齊台股財報季偏向
    # 純函式集中於 macro_helpers.classify_long_term_regime / classify_short_term_regime
    # v18.173：_lt hoist 到 try 外，供下方雙速合議使用
    _lt = None
    try:
        from src.compute.macro import (
            classify_long_term_regime as _cls_lt,
            detect_mk_golden_inflection as _det_mk2,
        )
        # C1-E v18.291:雙視角 macro_info 走 section_inputs SSOT。
        # _fi_streak_cache 死碼移除(無 downstream consumer,grep 全檔僅此一處)。
        from src.services import load_section_inputs as _load_si_lt
        _lt_inp = _load_si_lt(st.session_state)
        _mi_d = _lt_inp.macro_info or {}
        _cpi_d  = _mi_d.get('us_core_cpi') or {}
        _fed_d  = _mi_d.get('fed_funds') or {}
        _ndc_d  = _mi_d.get('ndc_signal') or {}
        _pmi_d  = _mi_d.get('ism_pmi') or {}
        _vix_d  = _mi_d.get('vix') or {}
        _exp_d  = _mi_d.get('tw_export') or {}

        _mk_for_lt = _det_mk2(
            cpi_yoy=_cpi_d.get('yoy'),
            cpi_prev_yoy=_cpi_d.get('prev_yoy'),
            fed_rate=_fed_d.get('current'),
            fed_prev_rate=_fed_d.get('prev'),
        )
        _lt = _cls_lt(
            cpi_yoy=_cpi_d.get('yoy'),
            fed_rate=_fed_d.get('current'),
            fed_prev_rate=_fed_d.get('prev'),
            ndc_score=_ndc_d.get('score'),
            pmi=_pmi_d.get('value') or _pmi_d.get('current') or _pmi_d.get('pmi'),
            mk_signal=_mk_for_lt,
        )
        # v18.190: 雙視角 UI 區塊移除（與「拐點偵測 6 面向 + MK」功能重疊，
        # 雙視角為純加權打分、未經 backtest；保留 _lt 計算供下方雷達雙速合議使用）
    except Exception as _e_lts:
        print(f'[tab_macro/長短期雙視角] {type(_e_lts).__name__}: {_e_lts}')

    # ── v18.172/v18.173 全球風險雷達資料準備（render 已下移）──────────────
    # v18.317：10 燈雷達 render 從總覽頂部下移至「短線急殺」桶之後的 🌍 全球風險桶
    # （見下方 _render_global_risk_bucket 呼叫）。此處僅備妥 _rr_fred_key / _slow_v，
    # 並 pre-init 以保證下移後的呼叫點變數必定存在（即使本 try 中途 raise）。
    _rr_fred_key = ''
    _slow_v = None
    try:
        _rr_fred_key = (os.environ.get('FRED_API_KEY') or
                        (st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else None) or '')
        # v18.173：把 v18.171 dual-view 算出的長期 regime _lt 映射成 slow_verdict
        # 校準：_cls_lt score 範圍 ~[-2,+2]，乘 5 對齊 fund synth 期望的 ~[-10,+10]
        if _lt and isinstance(_lt, dict) and _lt.get('regime'):
            _reg = str(_lt['regime'])
            _icon = _reg.split()[0] if _reg.split() else '⚪'
            _slow_v = {
                'level':  _reg,
                'score':  float(_lt.get('score') or 0.0) * 5.0,
                'color':  _lt.get('color') or '#888',
                'icon':   _icon,
                'action': f"{_lt.get('detail','')}；建議持股 {_lt.get('suggest_pct','--')}",
            }
    except Exception as _e_rr:
        print(f'[tab_macro/risk_radar] {type(_e_rr).__name__}: {_e_rr}')

    # ══ v18.284 — 📊 總經五桶總結 bar（長期/中期/短線急殺/籌碼/新聞）══
    # 門檻讀 shared.macro_buckets SSOT;未載入時不顯示(對齊紅綠燈)。
    # P3-D5 v18.390:抽至 macro/section_summary_bar.py(43 LOC,internal try/except)。
    if _show_market_data:
        render_five_bucket_summary()

    # v18.311：移除冗餘「今日市場總覽 — 現在適合買股票嗎？」天氣解說 box(晴天/多雲/下雨)。
    # 頂部已有「📊 總經總結儀表板 + 五桶 bar」(L679),此天氣解說與其重複 → 刪除,讓總結 bar 當頂。
    # 多空白話解讀保留為「點開才看」expander(收合,不佔版面)。
    # ── 🔰 故事化白話解讀（純疊加；解碼上方燈號卡片的數字，不重複多空說明）──
    with st.expander('🔰 看不懂上面那張燈號卡片的數字？點我 30 秒讀懂'):
        st.markdown('''卡片上的每個數字，用一句話看懂：

| 卡片欄位 | 白話意思 |
|---|---|
| **綜合健康度 /100** | 把均線、籌碼、景氣等訊號綜合成一個「市場體檢分數」，越高越健康 |
| **信心 %** | 系統對「資料夠不夠新、夠不夠齊」的把握度；**低於 70% 會直接擋住燈號**，避免拿過期資料誤判 |
| **評分 x/4** | 大盤多空打分，分數越高越偏多頭 |
| **建議持股 %** | 對應目前環境，建議把多少比例的資金放在股票上（其餘留現金） |
| **灰色小標籤** | 當下觸發的關鍵訊號（如外資買超、融資增減、期貨淨部位等） |

> 💡 看燈前先按上方「🚀 一鍵更新全部數據」，燈號才會反映「今天」而不是過期資料。''')

    # v18.334：抓取進行中隱藏「今日市場總覽」標題（避免空標題在資料到位前先冒出，
    # 載入時只留下方 spinner）。非抓取（含抓完 rerun）照常顯示。
    if not do_refresh:
        st.divider()

        st.markdown("""<div style="padding:6px 0 4px;">
<span style="font-size:20px;font-weight:900;color:#e6edf3;">🌍 今日市場總覽</span>
<span style="font-size:11px;color:#484f58;margin-left:10px;">決定：現在能買嗎？大盤水位？</span>
</div>""", unsafe_allow_html=True)
    # 五步流程說明已整合至主導覽列，此處不重複顯示

    # ══ 戰情概覽（一眼看清今日市場）══════════════════════════
    # P3-D6 v18.390:抽至 macro/section_overview.py(2-col KPI:今日市場狀態 + 全市場健康度)。
    render_section_overview(_tl_eff_reg, _show_market_data)

    # ══ 今日作戰室（最重要：一眼看清今天該做什麼）══════════════
    # v18.334：抓取進行中隱藏標題（與下方空狀態一致，載入時只留 spinner）。
    if not do_refresh:
        st.markdown('''<div style="background:linear-gradient(135deg,#0a1628,#0d2040);
border:2px solid #1f6feb;border-radius:14px;padding:16px;margin-bottom:14px;">
<div style="font-size:18px;font-weight:900;color:#58a6ff;margin-bottom:4px;">
🎯 今日作戰室 — 現在該做什麼？</div>
<div style="font-size:11px;color:#484f58;">每次操作前先看這裡，5分鐘掌握今日全局</div>
</div>''', unsafe_allow_html=True)

    # C1-C v18.289:走 section_inputs.load_section_inputs SSOT(對齊 5 桶 + 戰情概覽)
    from src.services import load_section_inputs as _load_si_wr
    _wr_inp  = _load_si_wr(st.session_state)
    _wr_mkt  = _wr_inp.mkt_info or {}
    _wr_cd   = _wr_inp.cl_data or {}
    _wr_bias = _wr_inp.bias_info or {}
    _wr_m1b  = _wr_inp.m1b_m2_info or {}
    _wr_inst = _wr_cd.get('inst', {})
    _wr_fk   = next((k for k in _wr_inst if '外資' in k), None)
    if _wr_fk is None:
        _wr_fk = next((k for k in _wr_inst if '外資' in k), None)
    _wr_fnet = _wr_inst.get(_wr_fk,{}).get('net', None) if _wr_fk else None
    _wr_margin = _wr_cd.get('margin')
    _wr_adl  = _wr_cd.get('adl')
    _wr_ts   = _wr_inp.cl_ts
    # 以交通燈有效 regime 為主，確保與頂部卡片結論一致
    _wr_reg  = _tl_eff_reg or (_wr_mkt.get('regime','neutral') if _wr_mkt else 'neutral')
    # v4 引擎：解耦趨勢與位階，取得精準操作建議
    _wr_fut_net = _wr_inp.futures_net
    _v4 = evaluate_market_status_v4_final(
        _wr_bias.get('price', 0) or 0,
        _wr_bias.get('ma240', 0) or 0,
        _wr_fut_net,
    )
    # 持股建議統一用紅綠燈/market_regime 的 exposure_pct（與 ①②一致，不再用 v4 區間）
    _wr_exp = _wr_mkt.get('exposure_pct', '--') if _wr_mkt else '--'

    if _show_market_data and (_wr_mkt or _wr_cd):
        # ── 今日唯一結論（大字顯示）──────────────────────────
        _wr_action = '請先更新總經數據'
        _wr_action_color = '#484f58'
        _wr_warns = []

        # 主結論統一以頂部紅綠燈 regime 為準（與燈號/戰情概覽一致，杜絕打架）
        _wr_reg_map = {
            'bull':    ('🟢 趨勢偏多 — 可逢回布局核心部位',   TRAFFIC_GREEN),
            'neutral': ('🟡 方向震盪 — 區間操作、控制部位',   TRAFFIC_YELLOW),
            'bear':    ('🔴 趨勢偏空 — 優先保留現金、嚴設停損', TRAFFIC_RED),
        }
        _wr_base, _wr_action_color = _wr_reg_map.get(_wr_reg, ('請先更新總經數據', '#484f58'))
        _wr_action = (f'{_wr_base}（建議持股 {_wr_exp}）'
                      if _wr_exp not in ('--', None, '') else _wr_base)
        # v4 年線位階資訊 → 降為補充提示，不再覆蓋主結論
        _v4_bits = [f'年線乖離 {_v4["Bias_240"]:+.1f}%']
        if not _v4.get('Is_Bull'):
            _v4_bits.append('股價在年線下')
        if _v4.get('Is_Overheated'):
            _v4_bits.append('乖離過熱')
        if _v4.get('Is_Foreign_Hedging'):
            _v4_bits.append('外資期貨避險')
        _wr_v4_hint = '｜'.join(_v4_bits)

        # 風險警示收集（v5：純融資餘額判斷）
        if _wr_margin and _wr_margin > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:
            _wr_warns.append(('🔴', f'融資 {_wr_margin:.0f}億 極度危險，散戶過熱，不宜追高'))
        elif _wr_margin and _wr_margin > MARGIN_BALANCE_WARN_THRESHOLD_YI:
            _wr_warns.append(('🟡', f'融資 {_wr_margin:.0f}億 警戒，注意風險'))

        if _wr_bias:
            _b240 = _wr_bias.get('bias_240', 0)
            if _b240 > 20:
                _wr_warns.append(('🟡', f'年線乖離 {_b240:+.1f}%，大盤偏高，勿追買'))
            elif _b240 < -20:
                _wr_warns.append(('✅', f'年線負乖離 {_b240:+.1f}%，長期布局機會'))

        if _wr_fnet is not None and _wr_fnet < -20:
            _wr_warns.append(('🔴', f'外資賣超 {abs(_wr_fnet):.1f}億，主力離場，謹慎'))

        if _wr_adl is not None and not _wr_adl.empty and 'ad_ratio' in _wr_adl.columns:
            _adl_r = float(_wr_adl['ad_ratio'].iloc[-1])
            if _adl_r < 35:
                _wr_warns.append(('🔴', f'上漲股票僅 {_adl_r:.0f}%，市場廣度不足，觀望'))

        # 顯示今日結論
        st.markdown(
            f'<div style="background:#0a2818;border-left:5px solid {_wr_action_color};'
            f'border-radius:0 10px 10px 0;padding:14px 18px;margin:8px 0;">'
            f'<div style="font-size:11px;color:#484f58;margin-bottom:4px;">📌 今日唯一行動建議</div>'
            f'<div style="font-size:17px;font-weight:900;color:{_wr_action_color};">{_wr_action}</div>'
            + (f'<div style="font-size:11px;color:#8b949e;margin-top:4px;">📐 年線位階參考：{_wr_v4_hint}</div>' if _wr_v4_hint else '')
            + (f'<div style="font-size:11px;color:#484f58;margin-top:4px;">更新時間：{_wr_ts}</div>' if _wr_ts else '') +
            '</div>', unsafe_allow_html=True)

        # 今日5分鐘清單 — v18.318：5 列垂直清單 → 5 欄總結小卡（比照桶卡片視覺）
        st.markdown('##### ✅ 今日操作前 5 分鐘清單')
        _cl_items = [
            ('大盤燈號', '🟢 多頭' if _wr_reg=='bull' else ('🔴 空頭防禦' if _wr_reg=='bear' else '🟡 震盪'),
             _wr_reg=='bull', '多頭才積極操作'),
            ('外資方向', f'{"買超" if (_wr_fnet or 0)>0 else "賣超"} {abs(_wr_fnet or 0):.0f}億' if _wr_fnet is not None else '未知',
             (_wr_fnet or 0) > 0, '外資買超=跟著走'),
            ('融資餘額',
             f'{_wr_margin:.0f}億' if _wr_margin else '未取得 (N/A)',
             not _wr_margin or _wr_margin <= MARGIN_BALANCE_WARN_THRESHOLD_YI,
             '>2500億警戒，>3400億極危'),
            ('年線位置', f'乖離{_wr_bias.get("bias_240",0):+.1f}%' if _wr_bias else '未知',
             not _wr_bias or abs(_wr_bias.get("bias_240",0)) < 20, '超過±20%要警惕'),
            ('持股比例', f'建議{_wr_exp}', _wr_reg!='bear', '按建議比例，不要滿倉'),
        ]
        _cl_cols = st.columns(len(_cl_items))
        for _ccol, (_name, _val, _ok, _tip) in zip(_cl_cols, _cl_items):
            _ic = '✅' if _ok else '⚠️'
            _vc = TRAFFIC_GREEN if _ok else TRAFFIC_RED
            with _ccol:
                st.markdown(
                    f"<div style='background:#0d1117;border:1px solid #21262d;"
                    f"border-top:3px solid {_vc};border-radius:8px;padding:8px 10px;"
                    f"margin:2px 0;min-height:108px;display:flex;flex-direction:column;"
                    f"justify-content:space-between;'>"
                    f"<div>"
                    f"<div style='font-size:11px;color:#8b949e;'>{_ic} {_name}</div>"
                    f"<div style='font-size:15px;font-weight:800;color:{_vc};"
                    f"margin:5px 0;line-height:1.25;'>{_val}</div>"
                    f"</div>"
                    f"<div style='font-size:10px;color:#484f58;line-height:1.3;'>{_tip}</div>"
                    f"</div>", unsafe_allow_html=True)

        # 風險警示
        if _wr_warns:
            st.markdown('##### ⚠️ 今日風險警示')
            for _wic, _wtxt in _wr_warns:
                _wbg = '#2a0d0d' if '🔴' in _wic else ('#2a1f00' if '🟡' in _wic else '#0a2818')
                st.markdown(
                    f'<div style="background:{_wbg};border-radius:6px;padding:7px 12px;margin:3px 0;'
                    f'font-size:13px;color:#c9d1d9;">{_wic} {_wtxt}</div>',
                    unsafe_allow_html=True)

        # 月虧損強制停機警示
        _monthly_loss = st.session_state.get('monthly_loss_pct', 0)
        if _monthly_loss < -10:
            st.markdown(
                f'<div style="background:#3a0000;border:2px solid {TRAFFIC_RED};border-radius:10px;'
                f'padding:14px;margin:10px 0;text-align:center;">'
                f'<div style="font-size:16px;font-weight:900;color:{TRAFFIC_RED};">⛔ 月虧損警示</div>'
                f'<div style="font-size:13px;color:#c9d1d9;margin-top:6px;">'
                f'本月虧損已達 {abs(_monthly_loss):.1f}%，建議暫停操作 7 天<br>'
                f'冷靜後重新評估選股邏輯</div></div>',
                unsafe_allow_html=True)

        st.markdown('<hr style="border-color:#21262d;margin:12px 0;">', unsafe_allow_html=True)
    elif not do_refresh:
        # v18.334：抓取進行中不顯示「點擊載入」空狀態（與標題一致，載入時只留 spinner）
        st.info('📡 點擊「🚀 一鍵更新全部數據」載入今日作戰室')
        st.markdown('<hr style="border-color:#21262d;margin:12px 0;">', unsafe_allow_html=True)

    # ── FinMind Token 狀態提示（不發 API，只檢查 env 是否有值）───
    _fm_tok_now = _get_fm_token()
    if not _fm_tok_now:
        st.error(
            '🔑 **FINMIND_TOKEN 未設定** — 以下功能無法使用：月營收、合約負債/資本支出、'
            '先行指標（期貨/選擇權/法人留倉）\n\n'
            '**設定步驟（Streamlit Cloud）：**\n'
            '1. 前往 https://finmindtrade.com 免費註冊並取得 API Token\n'
            '2. Streamlit Cloud → 你的 App → **Settings → Secrets**\n'
            '3. 新增一行：`FINMIND_TOKEN = "your_token_here"`\n'
            '4. 按 Save → App 自動重啟後即生效'
        )
    else:
        st.success(f'✅ FinMind Token 已設定（{_fm_tok_now[:12]}...）', icon='🔑')

    # v18.315：原埋在中間的「一鍵更新」按鈕已移除 — 改由 render_tab_macro 最外層頂部
    # 的唯一按鈕觸發(解決 user 反饋「內層多一顆按鈕」+「應在最外層就開始跑」)。
    # do_refresh 沿用頂部按鈕的回傳值(同一函式作用域)，下方清舊燈號邏輯不變。

    # ── 時間戳列（按鈕移頂部後保留此資料新鮮度列） ──
    _now_ts = _tw_now_str()
    _last_ts = st.session_state.get('cl_ts', '尚未更新')
    _ts_color = TRAFFIC_GREEN if _last_ts != '尚未更新' else '#484f58'
    st.markdown(
        f'<div style="font-size:11px;padding:4px 0;">'
        f'<span style="color:#484f58;">現在：{_now_ts}</span>　'
        f'<span style="color:{_ts_color};">上次更新：{_last_ts}</span>'
        f'</div>', unsafe_allow_html=True)

    # ── 使用者點了更新 → 立即清空頂部燈號 placeholder ──
    # v18.334：抓取時不再於頂部顯示「正在重新載入」訊息。user 要求載入時只保留
    # 下方 spinner 一個下載指示，頂部與各區塊空狀態不重複冒出來。
    if do_refresh:
        _tl_placeholder.empty()

    # ── 市場狀態卡 placeholder（等資料載入後才更新）──────────────
    _mkt_placeholder = st.empty()

    # [v10.56.0] 進頁完全不自動抓資料：必須使用者點按鈕才觸發
    # 移除舊的冷啟動條件 `'cl_data' not in st.session_state`，避免新舊資料混雜誤導
    # 副作用：冷啟動時所有資料區塊顯示 placeholder，由 _show_market_data gate 控制
    _load_heavy = bool(do_refresh) or bool(st.session_state.get('chips_loaded', False))

    # 用戶要求：未按按鈕前完全空白，只剩按鈕（隱藏所有 section）
    if not _load_heavy:
        return

    if do_refresh:
        _fetch_ph = st.empty()
        # v18.333：改用 st.spinner 動畫載入指示（對齊 Fund tab1 行為）。原本只有
        # 靜態 st.info 文字 + 按鈕殘留 → 阻塞抓取時畫面看似凍結、分不清是否載完。
        # spinner 在整個抓取期間動畫旋轉，結束自動消失，使用者一眼看出「進行中」。
        with st.spinner('🚀 並行抓取 總經 + 籌碼 + 先行指標中…（約 30~60 秒，請稍候）'):
            # P3-D4 v18.389:7-job orchestrator 下沉 src/services/macro_fetch_orchestrator
            from src.services.macro_fetch_orchestrator import fetch_macro_bundle
            _bundle = fetch_macro_bundle(
                load_heavy=_load_heavy,
                prev_cl_data=st.session_state.get('cl_data') or {},
                fm_token=(_get_fm_token() or FINMIND_TOKEN
                          or os.environ.get('FINMIND_TOKEN', '')),
                li_token=(_get_fm_token() or FINMIND_TOKEN
                          or os.environ.get('FINMIND_TOKEN', '')),
                bps_session=_bps(),
                intl_map=INTL_MAP, tw_map=TW_MAP, tech_map=TECH_MAP,
                fetch_single=fetch_single,
                fetch_institutional=fetch_institutional,
                fetch_margin_balance=fetch_margin_balance,
                fetch_adl=fetch_adl,
            )
            intl_raw   = _bundle['intl_raw']
            tw_raw     = _bundle['tw_raw']
            tech_raw   = _bundle['tech_raw']
            inst       = _bundle['inst']
            inst_date  = _bundle['inst_date']
            margin     = _bundle['margin']
            df_adl_raw = _bundle['df_adl_raw']
            df_li_a    = _bundle['df_li_a']
            # 冷啟動時 df_li_a=None,沿用既有 session_state['li_latest'](保 cache)
            if not _load_heavy and df_li_a is None:
                df_li_a = st.session_state.get('li_latest')
            # ADL debug msg(失敗時設,成功時 pop)
            if _bundle.get('adl_debug_msg'):
                st.session_state['adl_debug_msg'] = _bundle['adl_debug_msg']
            else:
                st.session_state.pop('adl_debug_msg', None)

            # ── 儲存主要數據 ─────────────────────────────────────
            st.session_state['cl_data'] = dict(
                intl=intl_raw, tw=tw_raw, tech=tech_raw,
                inst=inst, inst_date=inst_date, margin=margin,
                adl=df_adl_raw)
            st.session_state['cl_ts'] = _tw_now_str()
            st.session_state['_is_refreshing'] = False  # 資料就位,解除刷新鎖
            # 快取最後一次有效的法人/融資資料,供 API 失敗時 fallback 使用
            if inst:
                st.session_state['_last_inst'] = inst
                st.session_state['_last_inst_date'] = inst_date
            if margin:
                st.session_state['_last_margin'] = margin

            # [BUG FIX] 寬鬆條件:有任何 DataFrame(即使全 '-')都存入 session_state
            if df_li_a is not None and not df_li_a.empty:
                st.session_state['li_latest'] = df_li_a
                print(f'[先行指標] ✅ {len(df_li_a)} 筆 (有效欄={df_li_a.notna().any().sum()})')
            else:
                if 'li_latest' not in st.session_state:
                    st.session_state.pop('li_latest', None)
                print(f'[先行指標] ⚠️ 回傳{"空" if df_li_a is not None else "None"} — 保留舊快取')
            try:
                _fetch_ph.empty()
            except Exception:
                pass
            try:
                with open('/tmp/_adl_log.txt','r',encoding='utf-8') as _af:
                    print('[ADL詳細]\n' + _af.read())
                import os as _rmf
                _rmf.remove('/tmp/_adl_log.txt')
            except Exception:
                pass

            # ── do_refresh 完成後自動估算旌旗指數（不等掃描）──────
            _jq_ratio_src = None
            if df_adl_raw is not None and not df_adl_raw.empty and 'ad_ratio' in df_adl_raw.columns:
                _jq_ratio_src = 'ADL'
                _jq_ratio = float(df_adl_raw['ad_ratio'].tail(5).mean())
            else:
                # 備援：用大盤漲跌估算（正日=60%上漲，負日=40%）
                _tw_d = st.session_state.get('cl_data',{}).get('tw',{})
                _twii_d = _tw_d.get('台股加權指數')
                if _twii_d is not None and not _twii_d.empty:
                    _cc_d = 'close' if 'close' in _twii_d.columns else 'Close'
                    if _cc_d in _twii_d.columns:
                        _ret5 = _twii_d[_cc_d].pct_change().tail(5)
                        _up_days = (_ret5 > 0).sum()
                        _jq_ratio = 40 + _up_days * 5  # 全漲=65%, 全跌=40%
                        _jq_ratio_src = '大盤估算'
                else:
                    _jq_ratio_src = None  # 無資料時不設定，不顯示錯誤數值
            if _jq_ratio_src and _jq_ratio_src != '預設值':
                _jq_ratio = float(_jq_ratio)
                _jq_pos  = '80~100%' if _jq_ratio>=BREADTH_BULL_PCT else ('50~70%' if _jq_ratio>=BREADTH_NEUTRAL_PCT else ('20~40%' if _jq_ratio>=BREADTH_BEAR_PCT else '0~20%'))
                _jq_reg  = 'bull' if _jq_ratio>=BREADTH_BULL_PCT else ('neutral' if _jq_ratio>=BREADTH_NEUTRAL_PCT else 'bear')
                _jq_col  = TRAFFIC_GREEN if _jq_ratio>=BREADTH_BULL_PCT else (TRAFFIC_YELLOW if _jq_ratio>=BREADTH_NEUTRAL_PCT else TRAFFIC_RED)
                _jq_lbl  = '🟢 多頭積極' if _jq_ratio>=BREADTH_BULL_PCT else ('🟡 中性均衡' if _jq_ratio>=BREADTH_NEUTRAL_PCT else '🔴 保守防禦')
                _jq_src_note = f'（來源：{_jq_ratio_src}）'
                st.session_state['jingqi_info'] = {
                    'avg':_jq_ratio,'pos':_jq_pos,'regime':_jq_reg,
                    'color':_jq_col,'label':_jq_lbl,'total':0,
                    'source':_jq_ratio_src,
                    'pct20':_jq_ratio,'pct60':_jq_ratio*0.9,
                    'pct120':_jq_ratio*0.8,'pct240':_jq_ratio*0.7
                }

            # ── M1B-M2 + 乖離率 並發計算 ──────────────────────
            def _job_m1b():
                # P3-D2 v18.389:3-Tier fallback 下沉 macro_snapshot.fetch_m1b_m2_block
                # FRED_API_KEY closure 由 caller 傳入,函式本身 pure-ish。
                _fred_key_m1 = (os.environ.get('FRED_API_KEY')
                                or (st.secrets.get('FRED_API_KEY')
                                    if hasattr(st, 'secrets') else None) or '')
                from src.data.macro.macro_snapshot import fetch_m1b_m2_block
                return fetch_m1b_m2_block(fred_api_key=_fred_key_m1)

            def _job_bias():
                # P3-D3 v18.389:純函式下沉 src/data/macro/macro_snapshot.compute_twii_bias
                # closure dep: tw_raw.get('台股加權指數')
                try:
                    from src.data.macro.macro_snapshot import compute_twii_bias
                    return compute_twii_bias(tw_raw.get('台股加權指數'))
                except Exception as _bias_e:
                    print(f'[Bias] compute_twii_bias 失敗: {_bias_e}')
                    return None

            def _job_macro():
                """總經拼圖 v5.3:VIX/CPI/PMI/NDC/Export/Fed 並行抓取(thin orchestrator)。

                P3-D1 v18.389:6 sub-fetcher(原 inline 共 604 LOC)全下沉至
                src/data/macro/macro_snapshot.py fetch_*_block。本 _job_macro 留
                並發 orchestration + provenance 注入。FRED key / FinMind token 由
                outer scope 讀(EX-L0-1 st.secrets bootstrap)後顯式傳入。
                """
                from src.data.macro.macro_snapshot import (
                    fetch_vix_block, fetch_cpi_block, fetch_fed_funds_block,
                    fetch_tw_pmi_block, fetch_ndc_block, fetch_export_block,
                )
                _fred_key = (os.environ.get('FRED_API_KEY') or
                             (st.secrets.get('FRED_API_KEY')
                              if hasattr(st, 'secrets') else None) or '')
                _fm_tok = (os.environ.get('FINMIND_TOKEN') or
                           (st.secrets.get('FINMIND_TOKEN')
                            if hasattr(st, 'secrets') else None) or '')

                # ── 並行 6 source(v10.61.0 手動 executor + shutdown(wait=False))──
                # 立即 cancel 未完成,避免 stuck thread 拖外層 80s timeout。
                _fetchers = {
                    'vix':       fetch_vix_block,
                    'cpi':       lambda: fetch_cpi_block(fred_api_key=_fred_key),
                    'pmi':       fetch_tw_pmi_block,
                    'ndc':       fetch_ndc_block,
                    'export':    lambda: fetch_export_block(
                                     fred_api_key=_fred_key, finmind_token=_fm_tok),
                    'fed_funds': lambda: fetch_fed_funds_block(fred_api_key=_fred_key),
                }
                _r = {}
                _pool_mc = ThreadPoolExecutor(max_workers=6)
                try:
                    _futs_mc = {_pool_mc.submit(fn): name
                                for name, fn in _fetchers.items()}
                    try:
                        for _fut_mc in as_completed(_futs_mc, timeout=70):
                            try:
                                _part = _fut_mc.result()
                                if _part:
                                    _r.update(_part)
                            except Exception as _e:
                                print(f'[Macro] ❌ {_futs_mc.get(_fut_mc, "?")}: {_e}')
                    except (TimeoutError, _ConcFutTimeout):
                        # 70s 到仍有 future 未完成:取消未完成者,保留已收到的 partial _r
                        _stuck = [_futs_mc[_f] for _f in _futs_mc if not _f.done()]
                        for _f_pending in _futs_mc:
                            if not _f_pending.done():
                                _f_pending.cancel()
                        print(f'[Macro] ⏰ as_completed 70s timeout,未完成={_stuck},保留 keys={list(_r.keys())}')
                finally:
                    _pool_mc.shutdown(wait=False)

                # Failsafe + provenance — 即使全失敗也回傳 partial 標記(不回 None),
                # 讓診斷頁能區分「沒抓」vs「抓過全失敗」;macro_info 至少有時間戳供 UX 判斷。
                _r.setdefault('_loaded_at',
                              datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                if not any(k for k in _r if not k.startswith('_')):
                    _r['_all_failed'] = True
                # v18.353 PR-Q3 S-PROV-1 phase 19:集中注入 fetched_at 到每個 sub-dict。
                # 6 fetchers (vix/cpi/pmi/ndc/export/fed_funds) 各自已有 'source' key
                # (FRED/BLS/MOF-CSV 等),集中 setdefault('fetched_at') 比改 14 處 return
                # point 乾淨,§2.2 provenance(source + fetched_at)完整化。schema-additive。
                try:
                    _now_macro_prov = datetime.datetime.utcnow().isoformat() + 'Z'
                    for _k_prov, _v_prov in _r.items():
                        if _k_prov.startswith('_'):
                            continue  # 跳過 meta key(_loaded_at / _all_failed)
                        if isinstance(_v_prov, dict):
                            _v_prov.setdefault('fetched_at', _now_macro_prov)
                except Exception as _e_prov:
                    print(f'[Macro/prov] inject fetched_at fail: {_e_prov}')
                print(f'[Macro] 完成 keys={[k for k in _r.keys() if not k.startswith("_")]}')
                return _r

            # v18.341 PR-L1: 對齊 _job_macro 內部好 pattern(L2105-2138)。
            # user 2026-06-28「總經抓資料會自動停止沒有抓完成,要直接抓好不可以突然停掉」。
            # 舊 v10.61.0 設計:per-job `result(timeout=30/30/80)` + `shutdown(wait=False)`
            # 故意 zombie kill — 任一慢源就被 cutoff,user 看到「中途停掉」。v18.331 把
            # build_leading_fast 併入 _job_macro 內部 6-job pool 後,_job_macro 偶爾超 80s
            # 導致 _macro_res = None,partial 結果全丟。
            # 修法:
            #   (a) timeout 拉大到 200s 全域(原 max=80),配合內部 _job_macro 已有 70s
            #       as_completed cancel + 60s 餘裕 + 外層 30s+30s 慢源餘裕
            #   (b) 改 as_completed loop + partial preserve(任一完成立刻入 dict,不等)
            #   (c) timeout 到 → 取消未完成 future,但**保留已收到的**(_res_map),
            #       下方 if _xxx_res 寫入 session_state 仍走原 truthy 守護(不蓋 stale)
            #   (d) shutdown(wait=False) 維持,因為 future 已 cancel
            _GLOBAL_TIMEOUT_S = 200   # 寬到讓全 3 job 多半能完成(M1B<30, bias<30, macro 80-180)
            _exc2 = ThreadPoolExecutor(max_workers=3)
            _res_map = {'m1b': None, 'bias': None, 'macro': None}
            try:
                _futs2 = {
                    _exc2.submit(_job_m1b):   'm1b',
                    _exc2.submit(_job_bias):  'bias',
                    _exc2.submit(_job_macro): 'macro',
                }
                try:
                    for _fut2 in _asc_mc(_futs2, timeout=_GLOBAL_TIMEOUT_S):
                        _name2 = _futs2.get(_fut2, '?')
                        try:
                            _res_map[_name2] = _fut2.result()
                        except Exception as _e2:
                            print(f'[並發] ❌ {_name2}: {type(_e2).__name__}: {_e2}')
                except (TimeoutError, _ConcFutTimeout):
                    _stuck2 = [_futs2[_f] for _f in _futs2 if not _f.done()]
                    for _f_pend in _futs2:
                        if not _f_pend.done():
                            _f_pend.cancel()
                    print(f'[並發] ⏰ outer trio {_GLOBAL_TIMEOUT_S}s timeout，未完成={_stuck2}，'
                          f'保留 partial={[k for k, v in _res_map.items() if v]}')
            finally:
                _exc2.shutdown(wait=False)
            _m1b_res, _bias_res, _macro_res = _res_map['m1b'], _res_map['bias'], _res_map['macro']
            # 寫入 session_state 保留原 truthy 守護:partial 場景(某 job timeout)→
            # 既有 stale 不被 None 蓋,user 看到「上次成功的值」而非「資料消失」(§1)
            if _m1b_res:
                st.session_state['m1b_m2_info'] = _m1b_res
            if _bias_res:
                st.session_state['bias_info']   = _bias_res
            if _macro_res:
                st.session_state['macro_info']  = _macro_res

            # ── 計算市場狀態（用已載入資料，不另外發請求）
            try:
                _foreign_net_loaded = 0  # 0 = 尚無資料（market_regime 會顯示「待更新」）
                for _k, _v in inst.items():
                    if '外資' in _k:
                        _net_v = _v.get('net')
                        if _net_v is not None:
                            _foreign_net_loaded = float(_net_v) * 1e8
                        break
                _twii_df_loaded = tw_raw.get('台股加權指數')
                print(f'[市場評估] 大盤DF shape={getattr(_twii_df_loaded,"shape",None)}, '
                      f'columns={list(getattr(_twii_df_loaded,"columns",[]))}, '
                      f'外資淨={_foreign_net_loaded/1e8:.1f}億')
                # 取得 M1B-M2 資金活水資料（宏爺評分維度）
                _m1b2  = st.session_state.get('m1b_m2_info') or {}
                _m1b2_gap  = (round(float(_m1b2['m1b_yoy']) - float(_m1b2['m2_yoy']), 2)
                               if _m1b2.get('m1b_yoy') is not None and _m1b2.get('m2_yoy') is not None
                               else None)
                _m1b2_prev = _m1b2.get('m1b_m2_gap_prev')  # 上月 gap（若有）
                _mkt_loaded = get_market_assessment(
                    df_index=_twii_df_loaded,
                    foreign_net=_foreign_net_loaded,
                    m1b_m2_gap=_m1b2_gap,
                    m1b_m2_prev=_m1b2_prev,
                )
                if _mkt_loaded:
                    if margin:
                        if margin > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:
                            _mkt_loaded['signals'].append('🔴 融資極度危險（>3400億）')
                        elif margin > MARGIN_BALANCE_WARN_THRESHOLD_YI:
                            _mkt_loaded['signals'].append('⚠️ 融資警戒（>2500億）')
                        else:
                            _mkt_loaded['signals'].append(f'✅ 融資安全（{margin:.0f}億）')
                    st.session_state['mkt_info'] = _mkt_loaded
                    print(f'[市場評估] 成功：{_mkt_loaded.get("label")} 評分{_mkt_loaded.get("score")}')
                else:
                    # 備援：直接用 yfinance 重抓
                    print('[市場評估] df_index 失敗，用 yfinance 備援')
                    _mkt_fb = get_market_assessment(df_index=None, foreign_net=_foreign_net_loaded)
                    if _mkt_fb:
                        if margin:
                            if margin > MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:
                                _mkt_fb['signals'].append('🔴 融資極度危險（>3400億）')
                            elif margin > MARGIN_BALANCE_WARN_THRESHOLD_YI:
                                _mkt_fb['signals'].append('⚠️ 融資警戒（>2500億）')
                            else:
                                _mkt_fb['signals'].append(f'✅ 融資安全（{margin:.0f}億）')
                        st.session_state['mkt_info'] = _mkt_fb
                        print(f'[市場評估] 備援成功：{_mkt_fb.get("label")}')
            except Exception as _me:
                print(f'[市場評估 ERROR] {_me}')
                import traceback
                traceback.print_exc()
        # ── 全域資料登錄中心：掃描所有已載入 DF，寫入 data_registry ────
        try:
            import pandas as _pd_reg
            _reg_new: dict = {}

            def _reg_add(_rname: str, _rdf, category: str = '大盤', frequency: str = 'daily'):
                """提取最新時間戳後寫入 registry（不儲存 df 本體，僅保留元資料）。"""
                if not isinstance(_rdf, _pd_reg.DataFrame) or _rdf.empty:
                    return
                _d = _rdf
                if isinstance(_d.index, _pd_reg.DatetimeIndex):
                    _latest = _d.index.max()
                else:
                    _dcol = None
                    _date_fmt = None
                    for _c in _d.columns:
                        _cl = str(_c).lower()
                        if _cl == '_date':
                            _dcol = _c
                            _date_fmt = '%Y%m%d'
                            break
                        if _cl in ('date', 'datetime', 'timestamp', '日期', 'quarter', 'period'):
                            _dcol = _c
                            break
                    if _dcol:
                        try:
                            _s = _d[_dcol]
                            if _date_fmt:
                                _s = _pd_reg.to_datetime(_s, format=_date_fmt, errors='coerce')
                            else:
                                _s = _pd_reg.to_datetime(_s, errors='coerce')
                            _latest = _s.max()
                        except Exception:
                            _latest = None
                    else:
                        _latest = None
                try:
                    _ls = (_pd_reg.Timestamp(_latest).strftime('%Y-%m-%d')
                           if _latest is not None and not _pd_reg.isna(_latest) else 'N/A')
                except Exception:
                    _ls = 'N/A'
                _reg_new[_rname] = {
                    'last_updated': _ls, 'rows': len(_d),
                    'category': category, 'frequency': frequency,
                }

            def _reg_missing(_rname: str, category: str = '大盤', frequency: str = 'daily'):
                _reg_new[_rname] = {
                    'last_updated': 'N/A', 'rows': 0,
                    'category': category, 'frequency': frequency, 'missing': True,
                }

            # ── 大盤/總經：國際、台股、科技指數（日更新，固定清單確保永遠顯示 20 筆）──
            # C1-F v18.292:整個 registry 區塊 10 處 session_state.get 收斂成 1 處 SectionInputs
            from src.services import load_section_inputs as _load_si_reg
            _reg_inp = _load_si_reg(st.session_state)
            _cl_reg = _reg_inp.cl_data or {}
            _intl_d = _cl_reg.get('intl') or {}
            for _rn in INTL_MAP:
                _rdf = _intl_d.get(_rn)
                if isinstance(_rdf, _pd_reg.DataFrame) and not _rdf.empty:
                    _reg_add(_rn, _rdf, category='大盤', frequency='daily')
                else:
                    _reg_missing(_rn, category='大盤', frequency='daily')
            _tw_d = _cl_reg.get('tw') or {}
            for _rn in TW_MAP:
                _rdf = _tw_d.get(_rn)
                if isinstance(_rdf, _pd_reg.DataFrame) and not _rdf.empty:
                    _reg_add(_rn, _rdf, category='大盤', frequency='daily')
                else:
                    _reg_missing(_rn, category='大盤', frequency='daily')
            _tech_d = _cl_reg.get('tech') or {}
            for _rn in TECH_MAP:
                _rdf = _tech_d.get(_rn)
                if isinstance(_rdf, _pd_reg.DataFrame) and not _rdf.empty:
                    _reg_add(_rn, _rdf, category='大盤', frequency='daily')
                else:
                    _reg_missing(_rn, category='大盤', frequency='daily')
            _adl_reg = _cl_reg.get('adl')
            if isinstance(_adl_reg, _pd_reg.DataFrame) and not _adl_reg.empty:
                _reg_add('ADL 市場廣度', _adl_reg, category='大盤', frequency='daily')
                # 拆分個別欄位：上漲家數 / 下跌家數 / AD累計值
                _adl_date_col = '_date' if '_date' in _adl_reg.columns else (
                    'date' if 'date' in _adl_reg.columns else None)
                for _acname, _acol in [('上漲股票家數', 'up'), ('下跌股票家數', 'down'),
                                        ('ADL 累計廣度值', 'adl')]:
                    if _acol in _adl_reg.columns:
                        _acsub = _adl_reg[[c for c in [_adl_date_col, _acol] if c]].copy()
                        _reg_add(_acname, _acsub, category='大盤', frequency='daily')
                    else:
                        _reg_missing(_acname, category='大盤', frequency='daily')
            else:
                _reg_missing('ADL 市場廣度', category='大盤', frequency='daily')
                for _acname0 in ('上漲股票家數', '下跌股票家數', 'ADL 累計廣度值'):
                    _reg_missing(_acname0, category='大盤', frequency='daily')

            # ── 三大法人 + 融資餘額（籌碼面，日更新）────────────────────
            _cl_inst_reg = _cl_reg.get('inst') or (_reg_inp.last_inst or {})
            _inst_date_reg = (_cl_reg.get('inst_date') or _reg_inp.last_inst_date)
            try:
                _inst_ds = str(_inst_date_reg)[:10] if _inst_date_reg else 'N/A'
            except Exception:
                _inst_ds = 'N/A'
            for _ik, _iname in [('外資及陸資', '三大法人 外資買賣超'),
                                 ('投信',       '三大法人 投信買賣超'),
                                 ('自營商',     '三大法人 自營商買賣超')]:
                if _cl_inst_reg.get(_ik) is not None:
                    _reg_new[_iname] = {'last_updated': _inst_ds, 'rows': 1, 'category': '大盤', 'frequency': 'daily'}
                else:
                    _reg_missing(_iname, category='大盤', frequency='daily')
            _margin_reg2 = _cl_reg.get('margin') or _reg_inp.last_margin
            if _margin_reg2:
                _reg_new['融資餘額（台股）'] = {'last_updated': _inst_ds, 'rows': 1, 'category': '大盤', 'frequency': 'daily'}
            else:
                _reg_missing('融資餘額（台股）', category='大盤', frequency='daily')

            # ── 旌旗指數 + 乖離率（日更新）──────────────────────────────
            # 用 cl_ts 作為代理日期（這些指標沒有獨立時間戳）
            _cl_ts_proxy = _reg_inp.cl_ts
            try:
                import re as _re_ts_reg
                _m_ts = _re_ts_reg.search(r'(\d{4}-\d{2}-\d{2})', _cl_ts_proxy)
                _proxy_date = _m_ts.group(1) if _m_ts else 'N/A'
            except Exception:
                _proxy_date = 'N/A'
            _jq_reg3 = _reg_inp.jingqi_info or {}
            if _jq_reg3.get('avg') is not None:
                _reg_new['旌旗指數（上漲佔比）'] = {'last_updated': _proxy_date, 'rows': 1, 'category': '大盤', 'frequency': 'daily'}
            else:
                _reg_missing('旌旗指數（上漲佔比）', category='大盤', frequency='daily')
            _bias_reg3 = _reg_inp.bias_info or {}
            for _bk, _bn in [('bias_240', 'TWII 年線乖離率'), ('bias_20', 'TWII 月線乖離率')]:
                if _bias_reg3.get(_bk) is not None:
                    _reg_new[_bn] = {'last_updated': _proxy_date, 'rows': 1, 'category': '大盤', 'frequency': 'daily'}
                else:
                    _reg_missing(_bn, category='大盤', frequency='daily')

            # ── M1B / M2 貨幣資金（月更新）──────────────────────────────
            _m1b_reg3 = _reg_inp.m1b_m2_info or {}
            for _mk, _mn in [('m1b_yoy', 'M1B 資金活水年增率'), ('m2_yoy', 'M2 廣義貨幣年增率')]:
                if _m1b_reg3.get(_mk) is not None:
                    _reg_new[_mn] = {'last_updated': _proxy_date, 'rows': 1, 'category': '大盤', 'frequency': 'monthly'}
                else:
                    _reg_missing(_mn, category='大盤', frequency='monthly')
            # M1B-M2 資金缺口（衍生指標）
            if _m1b_reg3.get('m1b_yoy') is not None and _m1b_reg3.get('m2_yoy') is not None:
                _reg_new['M1B-M2 資金缺口'] = {'last_updated': _proxy_date, 'rows': 1, 'category': '大盤', 'frequency': 'monthly'}
            else:
                _reg_missing('M1B-M2 資金缺口', category='大盤', frequency='monthly')

            # ── 宏觀指標（月/日更新）────────────────────────────────────
            _macro_reg3 = _reg_inp.macro_info or {}
            for _mkey, _mname, _mfreq in [
                ('vix',         'VIX 波動率指數',      'daily'),
                ('us_core_cpi', '美國核心CPI年增率',   'monthly'),
                ('fed_funds',   '美國 Fed Funds Rate', 'monthly'),  # v18.169
                ('ism_pmi',     '🇹🇼 台灣 PMI 製造業指數',  'monthly'),
                ('tw_export',   '台灣出口年增率',       'monthly'),
                ('ndc_signal',  '景氣先行指標（NDC）', 'monthly'),
            ]:
                _msub = _macro_reg3.get(_mkey)
                if _msub:
                    if isinstance(_msub, dict):
                        # vix 的日期在 'dates' list 最後一筆
                        _raw_d = (_msub.get('date') or _msub.get('period')
                                  or (_msub.get('dates') or [''])[-1] or _proxy_date)
                        _mdate = str(_raw_d)[:10]
                    else:
                        _mdate = _proxy_date
                    _reg_new[_mname] = {'last_updated': _mdate, 'rows': 1, 'category': '大盤', 'frequency': _mfreq}
                else:
                    _reg_missing(_mname, category='大盤', frequency=_mfreq)

            # ── 先行指標：按來源拆 5 細項（大盤，日更新）────────────────
            _li_reg = _reg_inp.li_latest
            _li_groups = {
                '[先行指標] 三大法人現貨':    ['外資', '投信', '自營'],
                '[先行指標] 外資期貨留倉':    ['外資大小'],
                '[先行指標] 選擇權PCR':       ['選PCR', '外(選)'],
                '[先行指標] 成交量（TWSE）':  ['成交量'],
                '[先行指標] 未平倉/韭菜指數': ['前五大留倉', '前十大留倉', '未平倉口數', '韭菜指數'],
            }
            if isinstance(_li_reg, _pd_reg.DataFrame) and not _li_reg.empty:
                _li_date_cols = [c for c in ['_date'] if c in _li_reg.columns]
                for _grp, _cols in _li_groups.items():
                    _vcols = [c for c in _cols if c in _li_reg.columns]
                    if not _vcols:
                        _reg_missing(_grp, category='大盤', frequency='daily')
                        continue
                    _sub = _li_reg[_li_date_cols + _vcols].copy()
                    _mask = _sub[_vcols].apply(
                        lambda s: s.notna() & (s.astype(str).str.strip() != '-')
                    ).any(axis=1)
                    _sub = _sub[_mask]
                    if not _sub.empty:
                        _reg_add(_grp, _sub, category='大盤', frequency='daily')
                    else:
                        _reg_missing(_grp, category='大盤', frequency='daily')
            else:
                for _grp in _li_groups:
                    _reg_missing(_grp, category='大盤', frequency='daily')

            # ── 個股細項（5項全部強制顯示，含缺失）──────────────────────
            _t2d_reg = st.session_state.get('t2_data')
            if _t2d_reg:
                _s2r = _t2d_reg.get('sid', '')
                _n2r = (_t2d_reg.get('name') or _s2r) or _s2r
                _pfx = f'[個股] {_s2r} {_n2r}'
                _lbl_freq = {
                    '價格走勢': 'daily', '月營收': 'monthly',
                    '季財報': 'quarterly', '現金流量': 'quarterly', '資產負債': 'quarterly'
                }
                for _lbl, _key in [('價格走勢','df'),('月營收','rev'),
                                    ('季財報','qtr'),('現金流量','cl'),('資產負債','cx')]:
                    _sub = _t2d_reg.get(_key)
                    _rname = f'{_pfx} | {_lbl}'
                    _f = _lbl_freq[_lbl]
                    if isinstance(_sub, _pd_reg.DataFrame) and not _sub.empty:
                        _reg_add(_rname, _sub, category='個股', frequency=_f)
                    else:
                        _reg_missing(_rname, category='個股', frequency=_f)
            else:
                _pfx0 = '[個股] — 尚未搜尋'
                for _lbl0, _f0 in [('價格走勢','daily'),('月營收','monthly'),
                                    ('季財報','quarterly'),('現金流量','quarterly'),('資產負債','quarterly')]:
                    _reg_missing(f'{_pfx0} | {_lbl0}', category='個股', frequency=_f0)

            # ── 比較排行（個股類別）──────────────────────────────────────
            _t3d_reg = st.session_state.get('t3_data')
            if _t3d_reg and _t3d_reg.get('results'):
                _reg_new['[比較] 多股比較排行'] = {
                    'last_updated': 'N/A', 'rows': len(_t3d_reg['results']),
                    'category': '個股', 'frequency': 'daily',
                }
            else:
                _reg_missing('[比較] 多股比較排行', category='個股', frequency='daily')

            # ── ETF 細項（全部強制顯示）─────────────────────────────────
            _etf1_reg = st.session_state.get('etf_single_data') or {}
            _etf_pdf  = _etf1_reg.get('price_df')
            _etf_tk   = _etf1_reg.get('ticker', '')
            _etf_nm   = _etf1_reg.get('name', '')
            _etf_pfx  = f'[ETF] {_etf_tk} {_etf_nm}'.strip() if _etf_tk else '[ETF] — 尚未搜尋'
            if isinstance(_etf_pdf, _pd_reg.DataFrame) and not _etf_pdf.empty:
                _reg_add(f'{_etf_pfx} | 價格走勢', _etf_pdf, category='ETF', frequency='daily')
            else:
                _reg_missing(f'{_etf_pfx} | 價格走勢', category='ETF', frequency='daily')
            if _etf1_reg.get('cur_yield') is not None:
                _reg_new[f'{_etf_pfx} | 殖利率與技術分析'] = {
                    'last_updated': 'N/A', 'rows': 1, 'category': 'ETF', 'frequency': 'daily',
                }
            else:
                _reg_missing(f'{_etf_pfx} | 殖利率與技術分析', category='ETF', frequency='daily')
            _etf2_reg = st.session_state.get('etf_portfolio_data') or {}
            if _etf2_reg.get('rows'):
                _etf2n = len(_etf2_reg['rows'])
                _reg_new[f'[ETF組合] 再平衡分析（{_etf2n}檔）'] = {
                    'last_updated': 'N/A', 'rows': _etf2n, 'category': 'ETF', 'frequency': 'daily',
                }
            else:
                _reg_missing('[ETF組合] 再平衡分析', category='ETF', frequency='daily')
            _etf3_reg = st.session_state.get('etf_backtest_data') or {}
            if _etf3_reg.get('cagr') is not None:
                _etf3n = len(_etf3_reg.get('weights', {}))
                _reg_new[f'[ETF回測] 回測績效（{_etf3n}檔）'] = {
                    'last_updated': 'N/A', 'rows': _etf3n, 'category': 'ETF', 'frequency': 'daily',
                }
            else:
                _reg_missing('[ETF回測] 回測績效', category='ETF', frequency='daily')


            st.session_state['data_registry'] = _reg_new
            print(f'[DataRegistry] 已登錄 {len(_reg_new)} 個資料源，類別標籤已寫入')
        except Exception as _re:
            print(f'[DataRegistry] 建立失敗: {_re}')

        st.rerun()  # 資料更新完成，重跑腳本讓頂部看板讀取最新 session_state

    cd     = st.session_state.get('cl_data', {})

    # ── Registry 常態 Patch：每次頁面渲染都更新個股/ETF 部分（不重發請求）──
    # 個股(t2_data)、ETF、比較排行 是用戶互動後才載入，需在每次 rerun 補入 registry
    # 注意：不限制 if _rp:，即使總經尚未更新也要讓 ETF/個股 資料進入診斷 Tab
    try:
        import pandas as _pd_rp
        _rp = dict(st.session_state.get('data_registry') or {})
        # proxy 日期：優先用總經更新時間；未更新過則用今天
        import datetime as _dt_prp
        _cl_ts_rp = st.session_state.get('cl_ts', '')
        try:
            import re as _re_rp
            _m_rp = _re_rp.search(r'(\d{4}-\d{2}-\d{2})', _cl_ts_rp)
            _proxy_rp = _m_rp.group(1) if _m_rp else _dt_prp.date.today().strftime('%Y-%m-%d')
        except Exception:
            _proxy_rp = _dt_prp.date.today().strftime('%Y-%m-%d')

        # 移除所有舊的個股 / ETF 單一 / ETF組合 / ETF回測 / 比較 key
        for _ok in list(_rp.keys()):
            if (_ok.startswith('[個股]') or _ok.startswith('[比較]')
                    or (_ok.startswith('[ETF]') and '|' in _ok)
                    or '[ETF組合]' in _ok or '[ETF回測]' in _ok):
                del _rp[_ok]

        # ── 個股 ──────────────────────────────────────────────────────
        _t2rp = st.session_state.get('t2_data')
        if _t2rp:
            _spfx = f'[個股] {_t2rp.get("sid","")} {(_t2rp.get("name") or _t2rp.get("sid",""))}'
            # DataFrame 型資料
            for _lbl, _key, _f in [('價格走勢','df','daily'),('月營收','rev','monthly'),
                                    ('季財報','qtr','quarterly')]:
                _rp[f'{_spfx} | {_lbl}'] = rp_entry(_t2rp.get(_key), '個股', _f)
            # cl/cx 為 fetch_financials 回傳的純量金額（非 DataFrame），須用 rp_scalar
            _rp[f'{_spfx} | 現金流量'] = rp_scalar(_t2rp.get('cl'), '個股', 'quarterly', _proxy_rp)
            _rp[f'{_spfx} | 資產負債'] = rp_scalar(_t2rp.get('cx'), '個股', 'quarterly', _proxy_rp)
            # 年度股利（list of dicts）
            import datetime as _dt_yr_rp
            _yr_rp = _t2rp.get('yearly') or []
            if _yr_rp:
                _yr_raw = str(_yr_rp[-1].get('year', ''))[:4]
                if _yr_raw.isdigit():
                    _yr_date = f'{_yr_raw}-12-31'
                    # 若為未來日期（如年度=當年但12月尚未到），截斷至今天
                    _today_cap = _dt_yr_rp.date.today().strftime('%Y-%m-%d')
                    _yr_date = min(_yr_date, _today_cap)
                else:
                    _yr_date = _proxy_rp
                _rp[f'{_spfx} | 年度股利'] = {'last_updated': _yr_date,
                                               'rows': len(_yr_rp), 'category': '個股', 'frequency': 'yearly'}
            else:
                _rp[f'{_spfx} | 年度股利'] = {'last_updated': 'N/A', 'rows': 0,
                                               'category': '個股', 'frequency': 'yearly', 'missing': True}
            # 健康度評分（純量）
            _rp[f'{_spfx} | 健康度評分'] = rp_scalar(_t2rp.get('health'), '個股', 'daily', _proxy_rp)
            # 技術指標：各自獨立
            _rp[f'{_spfx} | RSI'] = rp_scalar(_t2rp.get('rsi'), '個股', 'daily', _proxy_rp)
            _rp[f'{_spfx} | KD (K值)'] = rp_scalar(_t2rp.get('k'), '個股', 'daily', _proxy_rp)
            _rp[f'{_spfx} | IBS 內部強弱'] = rp_scalar(_t2rp.get('ibs'), '個股', 'daily', _proxy_rp)
            _rp[f'{_spfx} | 量比 VR'] = rp_scalar(_t2rp.get('vr'), '個股', 'daily', _proxy_rp)
            _rp[f'{_spfx} | 布林帶'] = rp_scalar(_t2rp.get('bb'), '個股', 'daily', _proxy_rp)
            _rp[f'{_spfx} | VCP 波幅收縮'] = rp_scalar(_t2rp.get('vcp'), '個股', 'daily', _proxy_rp)
            # 財報延伸（合約負債/存貨/資本支出時序）
            _rp[f'{_spfx} | 合約負債/資本支出'] = rp_entry(_t2rp.get('qtr_extra'), '個股', 'quarterly')
        else:
            _spfx0 = '[個股] — 尚未搜尋'
            for _lbl0, _f0 in [
                ('價格走勢','daily'),('月營收','monthly'),('季財報','quarterly'),
                ('現金流量','quarterly'),('資產負債','quarterly'),('年度股利','yearly'),
                ('健康度評分','daily'),('RSI','daily'),('KD (K值)','daily'),
                ('IBS 內部強弱','daily'),('量比 VR','daily'),('布林帶','daily'),
                ('VCP 波幅收縮','daily'),('合約負債/資本支出','quarterly'),
            ]:
                _rp[f'{_spfx0} | {_lbl0}'] = {'last_updated':'N/A','rows':0,'category':'個股','frequency':_f0,'missing':True}

        # ── 比較排行 ──────────────────────────────────────────────────
        _t3rp = st.session_state.get('t3_data')
        if _t3rp and _t3rp.get('results'):
            _rp['[比較] 多股比較排行'] = {'last_updated': _proxy_rp, 'rows': len(_t3rp['results']), 'category': '個股', 'frequency': 'daily'}
        else:
            _rp['[比較] 多股比較排行'] = {'last_updated': 'N/A', 'rows': 0, 'category': '個股', 'frequency': 'daily', 'missing': True}

        # ── ETF 單一 ──────────────────────────────────────────────────
        _e1rp = st.session_state.get('etf_single_data') or {}
        _etkrp = _e1rp.get('ticker', '')
        _epfxrp = f'[ETF] {_etkrp} {_e1rp.get("name","")}'.strip() if _etkrp else '[ETF] — 尚未搜尋'
        _rp[f'{_epfxrp} | 價格走勢'] = rp_entry(_e1rp.get('price_df'), 'ETF', 'daily')
        _rp[f'{_epfxrp} | 現金殖利率'] = rp_scalar(_e1rp.get('cur_yield'), 'ETF', 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 近5年平均殖利率'] = rp_scalar(_e1rp.get('avg_yield'), 'ETF', 'yearly', _proxy_rp)
        _rp[f'{_epfxrp} | 近1年含息總報酬'] = rp_scalar(_e1rp.get('total_ret'), 'ETF', 'daily', _proxy_rp)
        _e1_prem = (_e1rp.get('premium') or {})
        _rp[f'{_epfxrp} | 折溢價率'] = rp_scalar(_e1_prem.get('premium_pct'), 'ETF', 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 淨值 (NAV)'] = rp_scalar(_e1_prem.get('nav'), 'ETF', 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 追蹤誤差'] = rp_scalar(_e1rp.get('te'), 'ETF', 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | VCP 波幅收縮'] = rp_scalar(_e1rp.get('vcp'), 'ETF', 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 內控費用率'] = rp_scalar(_e1rp.get('expense'), 'ETF', 'yearly', _proxy_rp)
        _rp[f'{_epfxrp} | Beta'] = rp_scalar(_e1rp.get('beta'), 'ETF', 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | AuM 規模'] = rp_scalar(_e1rp.get('aum'), 'ETF', 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | KD 技術指標'] = rp_scalar(_e1rp.get('k_val'), 'ETF', 'daily', _proxy_rp)
        _rp[f'{_epfxrp} | 年線乖離率 BIAS240'] = rp_scalar(_e1rp.get('bias240'), 'ETF', 'daily', _proxy_rp)

        # ── ETF 組合 ──────────────────────────────────────────────────
        _e2rp = st.session_state.get('etf_portfolio_data') or {}
        if _e2rp.get('rows'):
            _e2n = len(_e2rp['rows'])
            _rp[f'[ETF組合] 再平衡分析（{_e2n}檔）'] = {'last_updated': _proxy_rp, 'rows': _e2n, 'category': 'ETF', 'frequency': 'daily'}
        else:
            _rp['[ETF組合] 再平衡分析'] = {'last_updated': 'N/A', 'rows': 0, 'category': 'ETF', 'frequency': 'daily', 'missing': True}

        # ── ETF 回測 ──────────────────────────────────────────────────
        _e3rp = st.session_state.get('etf_backtest_data') or {}
        if _e3rp.get('cagr') is not None:
            _e3n = len(_e3rp.get('weights', {}))
            _rp[f'[ETF回測] 回測績效（{_e3n}檔）'] = {'last_updated': _proxy_rp, 'rows': _e3n, 'category': 'ETF', 'frequency': 'daily'}
        else:
            _rp['[ETF回測] 回測績效'] = {'last_updated': 'N/A', 'rows': 0, 'category': 'ETF', 'frequency': 'daily', 'missing': True}

        # 若大盤項目完全缺失（DataRegistry 建立時拋出 exception），從 cl_data 補建
        if not any(v.get('category') == '大盤' for v in _rp.values()):
            _cd_rb = st.session_state.get('cl_data', {})
            if _cd_rb:
                def _rb_add(_n, _df, _cat='大盤', _freq='daily'):
                    if isinstance(_df, _pd_rp.DataFrame) and not _df.empty:
                        _rp[_n] = {'last_updated': rp_ts(_df), 'rows': len(_df), 'category': _cat, 'frequency': _freq}
                    else:
                        _rp[_n] = {'last_updated': 'N/A', 'rows': 0, 'category': _cat, 'frequency': _freq, 'missing': True}
                for _n in INTL_MAP:
                    _rb_add(_n, (_cd_rb.get('intl') or {}).get(_n))
                for _n in TW_MAP:
                    _rb_add(_n, (_cd_rb.get('tw') or {}).get(_n))
                for _n in TECH_MAP:
                    _rb_add(_n, (_cd_rb.get('tech') or {}).get(_n))
                _rb_add('ADL 市場廣度', _cd_rb.get('adl'))
                _inst_rb = _cd_rb.get('inst') or {}
                for _ik, _iname in [('外資及陸資','三大法人 外資買賣超'),
                                     ('投信','三大法人 投信買賣超'),
                                     ('自營商','三大法人 自營商買賣超')]:
                    _rp[_iname] = {'last_updated': 'N/A', 'rows': 1 if _inst_rb.get(_ik) else 0,
                                   'category': '大盤', 'frequency': 'daily',
                                   **({} if _inst_rb.get(_ik) else {'missing': True})}
                _rp['融資餘額（台股）'] = {'last_updated': 'N/A', 'rows': 1 if _cd_rb.get('margin') else 0,
                                          'category': '大盤', 'frequency': 'daily',
                                          **({} if _cd_rb.get('margin') else {'missing': True})}
                _macro_rb = st.session_state.get('macro_info') or {}
                for _mk, _mn, _mf in [('vix','VIX 波動率指數','daily'),
                                       ('us_core_cpi','美國核心CPI年增率','monthly'),
                                       ('fed_funds','美國 Fed Funds Rate','monthly'),  # v18.169
                                       ('ism_pmi','🇹🇼 台灣 PMI 製造業指數','monthly'),
                                       ('tw_export','台灣出口年增率','monthly'),
                                       ('ndc_signal','景氣先行指標（NDC）','monthly')]:
                    _msub_rb = _macro_rb.get(_mk)
                    if _msub_rb:
                        _raw_rb = ((_msub_rb.get('date') or _msub_rb.get('period')
                                    or (_msub_rb.get('dates') or [''])[-1])
                                   if isinstance(_msub_rb, dict) else None) or _proxy_rp
                        _rp[_mn] = {'last_updated': str(_raw_rb)[:10], 'rows': 1,
                                    'category': '大盤', 'frequency': _mf}
                    else:
                        _rp[_mn] = {'last_updated': 'N/A', 'rows': 0,
                                    'category': '大盤', 'frequency': _mf, 'missing': True}
                print('[RegistryPatch] 大盤項目補建完成')

        st.session_state['data_registry'] = _rp
    except Exception as _rpe:
        print(f'[RegistryPatch] {_rpe}')

    intl   = {n:s for n,s in cd.get('intl',{}).items() if s is not None and not s.empty}
    tw     = {n:s for n,s in cd.get('tw',{}).items()   if s is not None and not s.empty}
    tech   = {n:s for n,s in cd.get('tech',{}).items() if s is not None and not s.empty}
    inst   = cd.get('inst', {})
    margin = cd.get('margin')
    _inst_is_cached = False
    _margin_is_cached = False
    if not inst and st.session_state.get('_last_inst'):
        inst = st.session_state['_last_inst']
        _inst_is_cached = True
    if not margin and st.session_state.get('_last_margin'):
        margin = st.session_state['_last_margin']
        _margin_is_cached = True
    df_adl = cd.get('adl')  # 騰落指標 DataFrame

    # ── 市場狀態卡：用已載入的真實資料渲染 ────────────────
    _mkt_info = st.session_state.get('mkt_info')
    if _mkt_info:
        _mkt_placeholder.empty()
        _mkt_placeholder.empty()  # 市場評分已整合至頂部紅綠燈看板，不重複顯示


    # F-7.1 B-S2:Section 2 拐點偵測 / 市場狀態抽至 src/ui/tabs/macro/section_state.py
    render_section_state(_mkt_info, _mkt_placeholder, _tl_placeholder, cd)
    intl_s = {n:calc_stats(s) for n,s in intl.items()}
    tw_s   = {n:calc_stats(s) for n,s in tw.items()}
    tech_s = {n:calc_stats(s) for n,s in tech.items()}

    # 持久化跨 tab 共用的國際指標 snapshot（供 tab_stock AI Prompt 引用）
    st.session_state['intl_snap'] = {
        'sox': intl_s.get('費城半導體 SOX'),
        'dxy': intl_s.get('美元指數 DXY'),
        'tnx': intl_s.get('10Y公債殖利率'),
        'dji': intl_s.get('道瓊工業 DJI'),
    }

    # F-7.1 B-5:Section 3 長期桶 LONG 抽至 src/ui/tabs/macro/section_long.py
    render_section_long(_load_heavy, intl, intl_s, tech, tech_s, tw, tw_s)
    # F-7.1 B-4:Section 4 (§八) 中期/總經拼圖抽至 src/ui/tabs/macro/section_mid.py
    # (B-5 awk 誤刪此 call,R3 補回 — render_section_mid 應接續 render_section_long)
    render_section_mid(_load_heavy, intl_s, tech_s, tw_s)
    # ══════════════════════════════════════════════════════════════
    # v18.276 中國拖累唯讀面板 — Section 八 之後、Section 九 之前
    # 4 數字唯讀展示:不改變上方主分卡與今日市場總覽,僅示意 China 副盤折扣強度
    # ══════════════════════════════════════════════════════════════
    try:
        import os as _os_cd
        _fred_key_cd = (_os_cd.environ.get('FRED_API_KEY') or
                        (st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else None) or '')
        _main_health_cd = (st.session_state.get('warroom_summary') or {}).get('health_score')
        _render_china_drag_panel(_fred_key_cd, _main_health_cd)
    except Exception as _cd_e:  # noqa: BLE001
        print(f"[tab_macro/china_drag] {type(_cd_e).__name__}: {_cd_e}")

    # F-7.1 B-2:Section 6 短線急殺桶抽至 src/ui/tabs/macro/section_short.py
    render_section_short(_load_heavy, tw, tw_s)
    # ════════════════════════════════════════════════════════════════════
    # 🌍 全球風險桶（v18.317：10 燈短線雷達從總覽頂部下移至此，本土短線急殺 → 全球視角）
    #   資料源 risk_radar.detect_risk_radar；render gate 對齊其他桶（_show_market_data）。
    # ════════════════════════════════════════════════════════════════════
    if _show_market_data:
        _render_global_risk_bucket(_rr_fred_key, slow_verdict=_slow_v)

    # F-7.1 B-S8-A v18.388:Section 3 籌碼桶抽至 macro/section_chips.py(LOC 3034→~2475)。
    render_section_chips(inst, margin, cd)
    # F-7.1 B-S8-B v18.388:§九 跨桶 AI 抽至 macro/section_cross_ai.py(P2 v18.389 rename)。
    render_section_cross_ai(tech_s, tw_s)

    # ══════════════════════════════════════════════════════════════
    # SECTION 十: 📊 總經訊號歷史驗證 — v18.191 ARCHIVED
    # ══════════════════════════════════════════════════════════════
    # archived 原因：user 反饋總經面板過於複雜（v18.190 已砍雙視角+AI總裁決），
    # 進一步封存歷史驗證區（C 區）— 包含 5 個 expander：
    #   - 🎯 TWII Crisis 事件清單 + Phase 1 events
    #   - 🚦 Phase 3 訊號預測力驗證（命中率總覽 + 逐事件明細 + 📐 精確率分析）
    #   - 📡 跨資料源比對視角矩陣（Phase E）
    #   - 🎯 MT5-style 自動校準（walk-forward + 3 重 anti-overfit gate）
    #   - 🔬 多因子權重最佳化（高原區 + walk-forward OOS）
    # 模組保留磁碟：tab_macro_validation.py + 對應 service modules
    # （macro_validation_tw / macro_signal_lookback_tw / multi_factor_optimization 等全留）
    # 復活步驟：取消下方 5 行註解（1 分鐘工）即可恢復功能
    #
    # try:
    #     from tab_macro_validation import render_history_validation_section
    #     render_history_validation_section()
    # except Exception as _e_hv:
    #     st.caption(f"⚠️ 歷史驗證 section 載入失敗：{_e_hv}")


    # F-7.1 B-3:§十一 News AI 總裁決抽至 src/ui/tabs/macro/section_news_ai.py
    render_section_news_ai(_macro_info, _tl_eff_reg)
    st.caption("📖 想看總經原理教室(景氣循環 / PMI / 殖利率倒掛 / 美林時鐘 等 10 章)?"
               "→ 已移至「📖 系統說明書」Tab,含資料來源完整地圖 + 4 大師策略。")
