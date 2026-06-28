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
# F-7.1 B-3 v18.366:Section 10/11 AI 總裁決抽至 macro/section_ai.py(LOC 4521→4230)
from src.ui.tabs.macro.section_ai import render_section_ai  # noqa: F401
# F-7.1 B-4 v18.367:Section 4 (§八) 中期/總經拼圖抽至 macro/section_mid.py(LOC 4230→3797)
from src.ui.tabs.macro.section_mid import render_section_mid  # noqa: F401
# F-7.1 B-5 v18.368:Section 3 長期桶 LONG 抽至 macro/section_long.py(LOC 3797→3402)
from src.ui.tabs.macro.section_long import render_section_long  # noqa: F401
# F-7.1 B-S2 v18.385:Section 2 拐點偵測 / 市場狀態抽至 macro/section_state.py(LOC 3402→3025)
from src.ui.tabs.macro.section_state import render_section_state  # noqa: F401
# F-7.1 B-S8-A v18.388:Section 3 籌碼桶抽至 macro/section_chips.py(LOC 3034→~2475)
from src.ui.tabs.macro.section_chips import render_section_chips  # noqa: F401



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
    # 頂部一眼判讀整版危險度；門檻讀 shared.macro_buckets SSOT。
    # v18.285：未載入資料時不顯示(對齊紅綠燈「尚無資料」+ 雷達 gate)，避免 pre-load 多餘面板。
    # 載入後(_show_market_data=True)五桶才以真實燈色出現,符合「summarize 已載入資料」語意。
    if _show_market_data:
        try:
            # C1-A v18.287:走 section_inputs.load_section_inputs SSOT,
            # 後續 C1-B+ 其他 section 也接同個 helper,降低物理重排耦合。
            from src.compute.macro import compute_five_bucket_summary
            from src.services import load_section_inputs
            _inp = load_section_inputs(st.session_state)
            _5b = compute_five_bucket_summary(
                macro_info=_inp.macro_info,
                mkt_info=_inp.mkt_info,
                warroom_summary=_inp.warroom_summary,
                m1b_m2_info=_inp.m1b_m2_info,
                bias_info=_inp.bias_info,
                cl_data=_inp.cl_data,
                li_latest=_inp.li_latest,
                jingqi_info=_inp.jingqi_info,
                news_items=_inp.news_items,
            )
            # v18.310：五桶 bar 升級為頂部「總結儀表板」(user 反饋「上方總結 bar 不夠顯眼」)
            st.markdown(
                '<div style="margin:6px 0 4px;padding:10px 16px;'
                'background:linear-gradient(90deg,#1f6feb22,#0d1117);'
                'border:1px solid #1f6feb55;border-radius:10px;">'
                '<span style="font-size:16px;font-weight:900;color:#58a6ff;">'
                '📊 總經總結儀表板</span>'
                '<span style="font-size:12px;color:#8b949e;margin-left:8px;">'
                '五時域一眼判讀：長期 ｜ 中期 ｜ 短線急殺 ｜ 籌碼 ｜ 新聞</span></div>',
                unsafe_allow_html=True)
            render_five_bucket_bar(_5b)
            # v18.310：下方各桶已加「桶群組 banner」分隔(取代純文字目錄)，此處保留簡短導航
            # v18.317：🌍 全球風險桶(雷達)；v18.321：🔮 拐點 + 💵 現金流向 加群組 banner
            st.caption(
                "📑 下方深度分析依桶順序排列，每桶有醒目分隔 banner："
                "🔮 拐點 → 💵 現金流向 → 🌳 長期 → 📈 中期 → ⚡ 短線急殺 → "
                "🌍 全球風險 → 🧩 籌碼 → 🧠 AI 綜合決策"
            )
            st.divider()
        except Exception as _e_5b:
            print(f'[tab_macro/五桶] {type(_e_5b).__name__}: {_e_5b}')

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
    # C1-B v18.288:走 section_inputs.load_section_inputs SSOT(對齊 5 桶 summary)
    from src.services import load_section_inputs as _load_si_ov
    _ov_inp  = _load_si_ov(st.session_state)
    _ov_mkt  = _ov_inp.mkt_info or {}
    _ov_jq   = _ov_inp.jingqi_info or {}
    _ov_cd   = _ov_inp.cl_data or {}
    # inst 優先從 cl_data，fallback 到獨立緩存的 _last_inst
    _ov_inst = _ov_cd.get('inst') or (_ov_inp.last_inst or {})

    # v18.316 去重(user 2026-06-27「按桶歸屬各留一處」+「5 分鐘清單為主」):
    # 外資 / 融資 / 年線乖離 / 持股 的「唯一家」= 下方「今日 5 分鐘清單」,
    # 今日市場總覽卡片不再重列這 4 個值(原 4 卡刪外資卡 + 年線卡 + regime 卡的持股副標),
    # 僅保留「大盤多空方向」+「全市場健康度(旌旗)」(後者清單未涵蓋)。
    # 風險警示仍只在觸發危險門檻時跳;§三 籌碼桶內部敘述不動。
    if _show_market_data and any([_ov_mkt, _ov_jq, _ov_cd]):
        _ov_cols = st.columns(2)
        # 大盤多空方向(持股比例見下方 5 分鐘清單,此處不重列)
        with _ov_cols[0]:
            # 以交通燈有效 regime 為主，確保與頂部卡片結論一致
            _ov_reg = _tl_eff_reg or (_ov_mkt.get('regime','neutral') if _ov_mkt else 'neutral')
            _ov_lbl = {'bull':'🟢 多頭','neutral':'🟡 震盪','bear':'🔴 空頭防禦'}.get(_ov_reg,'⚪')
            st.markdown(beginner_kpi('今日市場狀態', _ov_lbl, '大盤多空方向（持股比例見下方清單）',
                            TRAFFIC_GREEN if _ov_reg=='bull' else (TRAFFIC_RED if _ov_reg=='bear' else TRAFFIC_YELLOW),
                            '#0d1117'), unsafe_allow_html=True)
        # 旌旗/廣度(全市場健康度 — 5 分鐘清單未涵蓋,保留唯一)
        with _ov_cols[1]:
            _ov_jqp = _ov_jq.get('avg',None) if _ov_jq else None
            if _ov_jqp is not None:
                _ov_jc = TRAFFIC_GREEN if _ov_jqp>=BREADTH_BULL_PCT else (TRAFFIC_YELLOW if _ov_jqp>=BREADTH_NEUTRAL_PCT else TRAFFIC_RED)
                st.markdown(beginner_kpi('全市場健康度', f'{_ov_jqp:.0f}%', '有幾%的股票站在均線之上', _ov_jc, '>60%才適合積極買進'), unsafe_allow_html=True)
            else:
                st.markdown(kpi('旌旗指數', '--', '掃描後顯示', '#484f58', '#0d1117'), unsafe_allow_html=True)
        st.markdown('')

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
            import time as _t_spd
            _t_start = _t_spd.time()

            # ── 並發任務定義 ────────────────────────────────────
            # v18.193 perf: 3 個 job 內部從 ticker 序列改為內層 ThreadPoolExecutor 並行
            #             (原 N×fetch_single 序列 → max(t)；fetch_single /tmp pickle 30 分鐘
            #             cache 不變、DX-Y.NYB→DX=F→UUP 備援邏輯不變)
            def _parallel_fetch(_mp, **_kw):
                _max_w = max(1, len(_mp))
                with ThreadPoolExecutor(max_workers=_max_w) as _e_in:
                    _f_in = {_e_in.submit(fetch_single, _s, **_kw): _n for _n, _s in _mp.items()}
                    return {_f_in[_ft]: _ft.result() for _ft in _f_in}

            def _job_intl():
                return _parallel_fetch(INTL_MAP)

            def _job_tw():
                # 9mo ≈ 195 交易日，確保 ^TWII 有足夠 bars 計算 MA120（需120筆）
                return _parallel_fetch(TW_MAP, period='9mo')

            def _job_tech():
                return _parallel_fetch(TECH_MAP)

            def _job_inst():
                return fetch_institutional()

            def _job_margin():
                try:
                    return fetch_margin_balance()
                except Exception as _em:
                    print(f'[融資] ❌ {_em}')
                    return None

            def _job_adl():
                _tok_adl = os.environ.get('FINMIND_TOKEN','') or FINMIND_TOKEN
                return fetch_adl(days=60, token=_tok_adl)

            # v18.331 (2-C)：先行指標併入平行池。原 v8 因 Colab worker thread 中 requests
            # 受阻而移出池、改主流程序列呼叫（拖慢 ~15-55s）；現平台為 Streamlit Cloud，
            # 池內 inst/margin/adl 等 requests job 運作正常，該平台限制已不適用。
            # import + reload 留在主執行緒（importlib.reload 非 thread-safe），worker thread
            # 內只呼叫純抓取 build_leading_fast（不碰 UI）。失敗時下游既有 fallback（保留舊
            # li_latest）兜底，最壞只是先行指標顯示舊資料，不致崩潰。
            _li_tok = _get_fm_token() or FINMIND_TOKEN or os.environ.get('FINMIND_TOKEN', '')
            _li_build_fn = None
            try:
                import importlib as _il_li
                from src.data.macro import leading_indicators as _li_mod
                _il_li.reload(_li_mod)
                _li_build_fn = _li_mod.build_leading_fast
                print(f'[先行指標] v={getattr(_li_mod, "LI_VERSION", "?")} token={bool(_li_tok)}（併池）')
            except Exception as _e_li_imp:
                print(f'[先行指標] ❌ import 失敗 {type(_e_li_imp).__name__}: {_e_li_imp}')

            def _job_li():
                if _li_build_fn is None:
                    return None
                return _li_build_fn(days=14, token=_li_tok)

            # ── 並發執行（yfinance 最慢，先丟進去）─────────────
            # [Phase 2] 輕量任務（永遠跑，~30s 內完成）
            _jobs = {
                'intl':         _job_intl,
                'tw':           _job_tw,
                'tech':         _job_tech,
            }
            _job_timeouts = {
                'intl': 30, 'tw': 30, 'tech': 30,
            }
            # [Phase 2] 重量任務（按鈕觸發或手動 refresh 才跑）
            if _load_heavy:
                _jobs.update({
                    'inst':         _job_inst,
                    'margin':       _job_margin,
                    'adl':          _job_adl,
                    'li':           _job_li,   # v18.331 2-C：先行指標併池
                })
                _job_timeouts.update({
                    'inst': 25,
                    'margin': 25,
                    'adl': 55,
                    'li': 80,   # build_leading_fast 內部 thread join(timeout=80)
                })
            _results = {}
            # [BUG FIX] as_completed global timeout 從 50s 改為 110s
            # 原因：li job 內部 thread join(timeout=80)，50 < 80 導致 TimeoutError 崩潰
            # 並用 try/except TimeoutError 包住迴圈，確保其他6個 job 結果不因 li 超時而丟失
            # [BUG FIX] shutdown(wait=False) — 消除 `with TPE` 阻塞 7-20 分鐘的問題
            # 原理：手動管理 executor，超時後立即 cancel 未開始任務
            _AS_COMPLETED_TIMEOUT = max(_job_timeouts.values()) + 20
            _exc = ThreadPoolExecutor(max_workers=len(_jobs))
            _futs = {_exc.submit(fn): name for name, fn in _jobs.items()}
            try:
                try:
                    for _fut in as_completed(_futs, timeout=_AS_COMPLETED_TIMEOUT):
                        name = _futs[_fut]
                        _t_limit = _job_timeouts.get(name, 20)
                        try:
                            _results[name] = _fut.result(timeout=_t_limit)
                            print(f'[並發] ✅ {name} ({_t_spd.time()-_t_start:.1f}s)')
                        except Exception as _fe:
                            _results[name] = None
                            print(f'[並發] ❌ {name}: {type(_fe).__name__}: {_fe}')
                except TimeoutError:
                    print(f'[並發] ⚠️ as_completed {_AS_COMPLETED_TIMEOUT}s 超時，補救已完成結果')
                    for _fut, _name in _futs.items():
                        if _name not in _results:
                            if _fut.done():
                                try:
                                    _results[_name] = _fut.result(timeout=1)
                                    print(f'[並發] ✅ {_name} 補救成功')
                                except Exception as _fe2:
                                    _results[_name] = None
                            else:
                                _results[_name] = None
                                print(f'[並發] ⏰ {_name} 確認超時')
            finally:
                # [BUG FIX] 關鍵：立即取消未開始任務，不等待執行中的 thread
                try:
                    _exc.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    _exc.shutdown(wait=False)  # Python < 3.9
            # 補齊所有未收到結果的 job
            for _name in _jobs:
                if _name not in _results:
                    _results[_name] = None
                    print(f'[並發] ⏰ {_name} 超時')
            
            # ── 解包結果 ────────────────────────────────────────
            intl_raw  = _results.get('intl') or {}
            tw_raw    = _results.get('tw') or {}
            tech_raw  = _results.get('tech') or {}

            # [Phase 2] 重量區塊：cl_data 已存在則沿用舊值，否則 None
            _prev_cl  = st.session_state.get('cl_data') or {}
            if _load_heavy:
                inst_res  = _results.get('inst') or (None, None)
                inst, inst_date = inst_res if isinstance(inst_res, tuple) else (inst_res, None)
                # 如果 inst 是空的，用 FinMind TaiwanStockTotalInstitutionalInvestors 補救
                if not inst:
                    print('[並發] inst 為空，用 FinMind 補救...')
                    try:
                        _fm_t = _get_fm_token()
                        _start_i = (datetime.date.today()-datetime.timedelta(days=5)).strftime('%Y-%m-%d')
                        _ri = _bps().get('https://api.finmindtrade.com/api/v4/data',
                            params={'dataset':'TaiwanStockTotalInstitutionalInvestors',
                                    'start_date':_start_i,'token':_fm_t},
                            headers={'Authorization':f'Bearer {_fm_t}'}, timeout=15)
                        _ji = _ri.json()
                        print(f'[FinMind-Inst] status={_ji.get("status")} rows={len(_ji.get("data",[]))}')
                        if _ji.get('status')==200 and _ji.get('data'):
                            _df_i = pd.DataFrame(_ji['data'])
                            _ld_i = _df_i['date'].max()
                            _df_i = _df_i[_df_i['date']==_ld_i]
                            _df_i['buy']  = pd.to_numeric(_df_i.get('buy',  0), errors='coerce').fillna(0)
                            _df_i['sell'] = pd.to_numeric(_df_i.get('sell', 0), errors='coerce').fillna(0)
                            _df_i['_net'] = ((_df_i['buy'] - _df_i['sell']) / 1e8).round(2)
                            # FinMind name 欄為英文 key（Foreign_Investor / Investment_Trust / Dealer_*）
                            # 與 tw_macro.py:151 / hot_money.py:157 一致採英文匹配，中文為向下相容
                            inst = {}
                            for _nm, _net in zip(_df_i['name'].astype(str), _df_i['_net']):
                                _nl = _nm.lower()
                                if 'foreign' in _nl or '外資' in _nm:
                                    inst.setdefault('_f', 0)
                                    inst['_f'] = round(inst['_f'] + _net, 2)
                                elif 'investment_trust' in _nl or '投信' in _nm:
                                    inst['投信'] = {'net': _net}
                                elif 'dealer' in _nl or '自營' in _nm:
                                    inst.setdefault('_d', 0)
                                    inst['_d'] = round(inst['_d'] + _net, 2)
                            if '_f' in inst:
                                inst['外資及陸資'] = {'net': inst.pop('_f')}
                            if '_d' in inst:
                                inst['自營商'] = {'net': inst.pop('_d')}
                            inst_date = _ld_i
                            print(f'[FinMind-Inst] ✅ {inst}')
                    except Exception as _ei:
                        print(f'[FinMind-Inst] ❌ {_ei}')
                margin       = _results.get('margin')
                df_adl_raw   = _results.get('adl')
                if df_adl_raw is None:
                    st.session_state['adl_debug_msg'] = '來源均無回應（yfinance + TWSE MI_INDEX），詳見 Colab [ADL] 輸出'
                else:
                    st.session_state.pop('adl_debug_msg', None)
                # v18.331 (2-C)：先行指標已併入上方平行池（job 'li'），此處只讀結果，
                # 不再主流程序列呼叫。失敗時下游既有 fallback（下方）保留舊 li_latest。
                df_li_a = _results.get('li')
                if df_li_a is not None and not (hasattr(df_li_a, 'empty') and df_li_a.empty):
                    print(f'[先行指標] ✅ 併池成功 {len(df_li_a)} 筆')
                else:
                    print('[先行指標] ⚠️ 併池回空/None — 下游保留舊快取')
            else:
                # 冷啟動跳過重資料：沿用舊 cl_data 或 None
                inst       = _prev_cl.get('inst') or {}
                inst_date  = _prev_cl.get('inst_date')
                margin     = _prev_cl.get('margin')
                df_adl_raw = _prev_cl.get('adl')
                df_li_a    = st.session_state.get('li_latest')
                print('[Phase 2] 冷啟動跳過 inst/margin/adl/li（按鈕載入）')

            # ── 儲存主要數據 ─────────────────────────────────────
            st.session_state['cl_data'] = dict(
                intl=intl_raw, tw=tw_raw, tech=tech_raw,
                inst=inst, inst_date=inst_date, margin=margin,
                adl=df_adl_raw)
            st.session_state['cl_ts'] = _tw_now_str()
            st.session_state['_is_refreshing'] = False  # 資料就位，解除刷新鎖
            # 快取最後一次有效的法人/融資資料，供 API 失敗時 fallback 使用
            if inst:
                st.session_state['_last_inst'] = inst
                st.session_state['_last_inst_date'] = inst_date
            if margin:
                st.session_state['_last_margin'] = margin

            # [BUG FIX] 寬鬆條件：有任何 DataFrame（即使全 '-'）都存入 session_state
            # 原本 not df_li_a.empty 在 rows 有骨架但全 None 時仍為 True，但若某個版本回 None 或空 DF 則捨棄
            if df_li_a is not None and not df_li_a.empty:
                st.session_state['li_latest'] = df_li_a
                print(f'[先行指標] ✅ {len(df_li_a)} 筆 (有效欄={df_li_a.notna().any().sum()})')
            else:
                # 保留舊資料（若有），避免畫面空白
                if 'li_latest' not in st.session_state:
                    st.session_state.pop('li_latest', None)
                print(f'[先行指標] ⚠️ 回傳{"空" if df_li_a is not None else "None"} — 保留舊快取')

            print(f'[並發] 🎉 全部完成 共 {_t_spd.time()-_t_start:.1f}s')
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
                import pandas as _pd_m1
                _fm_tok_m1 = _get_fm_token()
                _start_m1 = (datetime.date.today()-datetime.timedelta(days=420)).strftime('%Y-%m-%d')

                # ── [Step 4] 路徑 0：tw_macro.fetch_cbc_m1b_m2 統一委派 ──
                # 內含 Tier 1 (CBC ms1.json) + Tier 2 (CPX EF15M01) + Tier 3 (^TWII proxy)
                # 全部走 NAS proxy,取代原本散落的 CPX EF01M01/EF17M01 + ms1.json 直連
                try:
                    from src.data.macro import fetch_cbc_m1b_m2 as _tw_cbc
                    _cbc_snap = _tw_cbc()
                    if _cbc_snap.get('m1b_yoy') is not None:
                        _src_label = ('TWII-proxy' if _cbc_snap.get('is_proxy_tier')
                                      else f'CBC-tier{_cbc_snap.get("tier_used")}')
                        print(f'[M1B/tw_macro] ✅ {_src_label} '
                              f'M1B={_cbc_snap["m1b_yoy"]:.2f}% M2={_cbc_snap["m2_yoy"]:.2f}%')
                        return {'m1b_yoy': _cbc_snap['m1b_yoy'],
                                'm2_yoy':  _cbc_snap['m2_yoy'],
                                'source':  _src_label}
                except Exception as _tw_e:
                    print(f'[M1B/tw_macro] ❌ {_tw_e}')

                # ── 路徑 2：FRED（台灣 M1B/M2，fetch_url + FRED_API_KEY）──
                try:
                    import os as _os_m1f
                    from src.data.proxy import fetch_url as _fu_m1
                    _fred_key_m1 = (_os_m1f.environ.get('FRED_API_KEY') or
                                    (st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else None) or '')
                    _fp_m1 = {'api_key': _fred_key_m1} if _fred_key_m1 else {}
                    _fred_base_p = {'file_type': 'json', 'sort_order': 'asc', 'limit': 36, **_fp_m1}
                    _fred_m1b_r = _fu_m1('https://api.stlouisfed.org/fred/series/observations',
                                         params={'series_id': 'MYAGM1TWA189S', **_fred_base_p}, timeout=12, attempts=1)
                    _fred_m2_r  = _fu_m1('https://api.stlouisfed.org/fred/series/observations',
                                         params={'series_id': 'MYAGM2TWA189S', **_fred_base_p}, timeout=12, attempts=1)
                    if _fred_m1b_r is None or _fred_m2_r is None:
                        raise ValueError('FRED fetch_url 回傳 None')
                    print('[M1B/FRED] M1 OK M2 OK')
                    if True:  # 保留縮排結構
                        _obs_m1 = [o for o in _fred_m1b_r.json().get('observations', [])
                                   if o.get('value', '.') != '.']
                        _obs_m2 = [o for o in _fred_m2_r.json().get('observations', [])
                                   if o.get('value', '.') != '.']
                        _df_fred_m1 = _pd_m1.DataFrame(_obs_m1)
                        _df_fred_m2 = _pd_m1.DataFrame(_obs_m2)
                        for _dfm in [_df_fred_m1, _df_fred_m2]:
                            _dfm['value'] = _pd_m1.to_numeric(_dfm['value'], errors='coerce')
                        _df_fred_m1 = _df_fred_m1.dropna(subset=['value'])
                        _df_fred_m2 = _df_fred_m2.dropna(subset=['value'])
                        print(f'[M1B/FRED] M1 rows={len(_df_fred_m1)} M2 rows={len(_df_fred_m2)} last={_df_fred_m1["date"].iloc[-1] if len(_df_fred_m1) else "?"}')
                        if len(_df_fred_m1) >= 13 and len(_df_fred_m2) >= 13:
                            _m1b_yoy_f = round((_df_fred_m1['value'].iloc[-1]/_df_fred_m1['value'].iloc[-13]-1)*100, 2)
                            _m2_yoy_f  = round((_df_fred_m2['value'].iloc[-1]/_df_fred_m2['value'].iloc[-13]-1)*100, 2)
                            print(f'[M1B/FRED] ✅ M1B={_m1b_yoy_f:.2f}% M2={_m2_yoy_f:.2f}%')
                            return {'m1b_yoy': _m1b_yoy_f, 'm2_yoy': _m2_yoy_f, 'source': 'FRED'}
                except Exception as _fred_e:
                    print(f'[M1B/FRED] ❌ {_fred_e}')

                # ── 路徑 2b：IMF DataMapper API（FRED 備援，全球可達）──
                try:
                    # MABMM301 = M2 年增率%, MANMM101 = M1 年增率% (IMF IFS)
                    from src.data.proxy import fetch_url as _fu_imf  # 強制走 NAS proxy（一致性；失敗自動降級直連）
                    _imf_m1_r = _fu_imf(
                        'https://www.imf.org/external/datamapper/api/v1/MANMM101/TW', timeout=15, attempts=1)
                    _imf_m2_r = _fu_imf(
                        'https://www.imf.org/external/datamapper/api/v1/MABMM301/TW', timeout=15, attempts=1)
                    print(f'[M1B/IMF] M1={getattr(_imf_m1_r, "status_code", None)} M2={getattr(_imf_m2_r, "status_code", None)}')
                    if (_imf_m1_r is not None and _imf_m2_r is not None
                            and _imf_m1_r.status_code == 200 and _imf_m2_r.status_code == 200):
                        _imf_m1_j = _imf_m1_r.json()
                        _imf_m2_j = _imf_m2_r.json()
                        _imf_m1_vals = _imf_m1_j.get('values', {}).get('MANMM101', {}).get('TW', {})
                        _imf_m2_vals = _imf_m2_j.get('values', {}).get('MABMM301', {}).get('TW', {})
                        print(f'[M1B/IMF] M1 years={len(_imf_m1_vals)} M2 years={len(_imf_m2_vals)}')
                        if _imf_m1_vals and _imf_m2_vals:
                            # IMF 返回的已是 YoY 年增率%，取最新一年
                            _imf_m1_sorted = sorted([(k, float(v)) for k, v in _imf_m1_vals.items() if v is not None], key=lambda x: x[0])
                            _imf_m2_sorted = sorted([(k, float(v)) for k, v in _imf_m2_vals.items() if v is not None], key=lambda x: x[0])
                            if _imf_m1_sorted and _imf_m2_sorted:
                                _m1b_yoy_imf = round(_imf_m1_sorted[-1][1], 2)
                                _m2_yoy_imf  = round(_imf_m2_sorted[-1][1], 2)
                                print(f'[M1B/IMF] ✅ year={_imf_m1_sorted[-1][0]} M1B={_m1b_yoy_imf:.2f}% M2={_m2_yoy_imf:.2f}%')
                                return {'m1b_yoy': _m1b_yoy_imf, 'm2_yoy': _m2_yoy_imf, 'source': f'IMF({_imf_m1_sorted[-1][0]})'}
                except Exception as _imf_e:
                    print(f'[M1B/IMF] ❌ {_imf_e}')

                # [Step 4] 舊路徑 3 (CBC ms1.json 直連) 已由 tw_macro Tier 1 取代

                # 若所有真實來源都失敗，回傳 None（顯示「待更新」比顯示錯誤數字好）
                print('[M1B] 所有路徑失敗，回傳 None')
                return None

            def _job_bias():
                try:
                    # tw_raw 只有 90 天，MA240 需要另外抓 2 年資料
                    _twii = tw_raw.get('台股加權指數')
                    _cc_b = 'Close' if (_twii is not None and 'Close' in getattr(_twii,'columns',[])) else 'close'
                    _n_existing = len(_twii) if _twii is not None and not _twii.empty else 0
                    if _n_existing < 240:
                        # P1-1c v18.376:抽至 L1 fetch_twii_2y_for_ma240
                        try:
                            from src.data.macro.macro_snapshot import fetch_twii_2y_for_ma240
                            _twii_2y = fetch_twii_2y_for_ma240()
                            if _twii_2y is not None and len(_twii_2y) >= 240:
                                _twii = _twii_2y
                                _cc_b = 'Close'
                            else:
                                print(f'[Bias] 2y 資料不足,使用現有 {_n_existing} 天')
                        except Exception as _yf_b_e:
                            print(f'[Bias] yfinance 2y 失敗: {_yf_b_e}')
                    if _twii is None or _twii.empty:
                        return None
                    # 寬鬆欄位查找：Close / close / Adj Close
                    if _cc_b not in _twii.columns:
                        _cc_b = next((c for c in _twii.columns if str(c).lower() in ('close','adj close','adjclose')), None)
                        if _cc_b is None:
                            print(f'[Bias] 找不到 Close 欄，現有欄位={list(_twii.columns)[:6]}')
                            return None
                    _cs = _twii[_cc_b].dropna()
                    _n  = len(_cs)
                    _lp = float(_cs.iloc[-1])
                    _ma20  = float(_cs.tail(min(20,_n)).mean())
                    _ma60  = float(_cs.tail(min(60,_n)).mean())
                    _ma120 = float(_cs.tail(min(120,_n)).mean())
                    _ma240 = float(_cs.tail(min(240,_n)).mean())
                    print(f'[Bias] price={_lp:.0f} MA240={_ma240:.0f} bias240={((_lp-_ma240)/_ma240*100):.1f}% (n={_n})')
                    return {
                        'bias_20':  round((_lp-_ma20) /_ma20 *100, 1) if _ma20  else 0,
                        'bias_60':  round((_lp-_ma60) /_ma60 *100, 1) if _ma60  else 0,
                        'bias_240': round((_lp-_ma240)/_ma240*100, 1) if _ma240 else 0,
                        'price':_lp,'ma20':_ma20,'ma60':_ma60,'ma120':_ma120,'ma240':_ma240,
                        'data_days':_n,'is_estimated':_n<240
                    }
                except Exception:
                    return None

            def _job_macro():
                """總經拼圖 v5.2：VIX/CPI/PMI/NDC/Export 並行抓取（NDC 改抓 StockFeel+MacroMicro 雙源）"""
                import requests as _rq_mc
                # L2: 使用頂層已匯入的 ThreadPoolExecutor / as_completed
                _TPE, _asc_mc = ThreadPoolExecutor, as_completed
                # 兼容 Python 3.8-3.10：concurrent.futures.TimeoutError 與 builtins.TimeoutError 不同類別
                from concurrent.futures import TimeoutError as _ConcFutTimeout

                def _mk_s():
                    """NAS proxy Session — 直接套用 proxy_helper.get_proxies()"""
                    from requests.adapters import HTTPAdapter as _HA
                    from urllib3.util.retry import Retry as _Rt
                    try:
                        from src.data.proxy import get_proxies as _gp
                        _px = _gp()
                    except Exception:
                        _px = None
                    _s2 = _rq_mc.Session()
                    _adp = _HA(max_retries=_Rt(total=2, backoff_factor=1.0,
                               status_forcelist=[429, 503, 504], raise_on_status=False))
                    _s2.mount('https://', _adp)
                    _s2.mount('http://', _adp)
                    if _px:
                        _s2.proxies.update(_px)
                    _s2.verify = False
                    return _s2

                def _mk_s_tw():
                    """台灣 IP proxy Session（同 _mk_s，保留名稱供既有呼叫相容）"""
                    return _mk_s()

                # ── 1. VIX ──────────────────────────────────────────────────────────
                # v18.332 Tier2 2-D slice 1：抽至 L1 macro_snapshot.fetch_vix_block（可單測）。
                from src.data.macro import fetch_vix_block as _fetch_vix  # P1-2 v18.373:macro_snapshot 搬到 L1

                # ── 2. CPI（美國核心 CPI YoY，series CPILFESL）─────────────────────
                #   v18.142 修：原本誤用 CPIAUCSL（總體 CPI All Items），與 UI 標籤
                #   「美國核心 CPI」不符；data_registry.py L46 標 CPILFESL 為準。
                #   新增方案 0：FRED 公開 fredgraph.csv（無需 API key，最穩）。
                def _fetch_cpi():
                    import datetime as _dt_cpi
                    import io as _io_cpi
                    import pandas as _pd_cpi
                    _s = _mk_s()
                    _cpi_errs = []
                    # ── 方案0: FRED 公開 fredgraph.csv（CPILFESL，無需 key）────────
                    try:
                        from src.data.proxy import fetch_url as _fu_cpi
                        _r0 = _fu_cpi('https://fred.stlouisfed.org/graph/fredgraph.csv',
                                      params={'id': 'CPILFESL'},
                                      timeout=10, attempts=1)
                        print(f'[Macro/CPI/fredgraph] response={"OK" if _r0 else "None"}')
                        if _r0 is not None and _r0.status_code == 200:
                            _df0 = _pd_cpi.read_csv(
                                _io_cpi.StringIO(_r0.content.decode('utf-8', errors='ignore')))
                            _df0 = _df0.dropna()
                            if len(_df0) >= 13:
                                _vals0 = _pd_cpi.to_numeric(_df0.iloc[:, 1],
                                                            errors='coerce').dropna()
                                if len(_vals0) >= 13:
                                    _yoy = round((_vals0.iloc[-1] / _vals0.iloc[-13] - 1) * 100, 2)
                                    # v18.169：補 prev_yoy 供 MK 黃金拐點偵測（CPI 月度變化）
                                    _prev_yoy = (round((_vals0.iloc[-2] / _vals0.iloc[-14] - 1) * 100, 2)
                                                 if len(_vals0) >= 14 else None)
                                    _date = str(_df0.iloc[-1, 0])[:10]
                                    print(f'[Macro/CPI/fredgraph] ✅ YoY={_yoy:.2f}% prev={_prev_yoy} date={_date}')
                                    return {'us_core_cpi': {'yoy': _yoy, 'prev_yoy': _prev_yoy,
                                                            'date': _date,
                                                            'source': 'FRED/fredgraph.csv',
                                                            'series_id': 'CPILFESL'}}
                            _cpi_errs.append(f'fredgraph:rows<13({len(_df0)})')
                        else:
                            _cpi_errs.append(f'fredgraph:HTTP{_r0.status_code if _r0 else "None"}')
                    except Exception as _e:
                        _cpi_errs.append(f'fredgraph:{type(_e).__name__}')
                        print(f'[Macro/CPI/fredgraph] ❌ {_e}')
                    # ── 方案1: FRED API（CPILFESL + API key 加速）────────────────
                    try:
                        import os as _os_cpi_f
                        from src.data.proxy import fetch_url as _fu_cpi
                        _fred_key_cpi = (_os_cpi_f.environ.get('FRED_API_KEY') or
                                         (st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else None) or '')
                        _cpi_start = (_dt_cpi.datetime.now() - _dt_cpi.timedelta(days=365*3)).strftime('%Y-%m-%d')
                        _cpi_end   = _dt_cpi.datetime.now().strftime('%Y-%m-%d')
                        _cpi_p = {'series_id': 'CPILFESL', 'file_type': 'json',
                                  'sort_order': 'asc', 'limit': 36,
                                  'observation_start': _cpi_start,
                                  'observation_end': _cpi_end}
                        if _fred_key_cpi:
                            _cpi_p['api_key'] = _fred_key_cpi
                        _rc1 = _fu_cpi('https://api.stlouisfed.org/fred/series/observations',
                                       params=_cpi_p, timeout=12, attempts=1)
                        print(f'[Macro/CPI/FRED-API] response={"OK" if _rc1 else "None"}')
                        if _rc1 is not None:
                            _obs_c = [o for o in _rc1.json().get('observations', [])
                                      if o.get('value', '.') != '.']
                            if len(_obs_c) >= 13:
                                _vals_c = [float(o['value']) for o in _obs_c]
                                _yoy = round((_vals_c[-1] / _vals_c[-13] - 1) * 100, 2)
                                # v18.169：補 prev_yoy 供 MK 黃金拐點偵測
                                _prev_yoy = (round((_vals_c[-2] / _vals_c[-14] - 1) * 100, 2)
                                             if len(_vals_c) >= 14 else None)
                                _date = _obs_c[-1]['date']
                                print(f'[Macro/CPI/FRED-API] ✅ YoY={_yoy:.2f}% prev={_prev_yoy} date={_date}')
                                return {'us_core_cpi': {'yoy': _yoy, 'prev_yoy': _prev_yoy,
                                                        'date': _date,
                                                        'source': 'FRED-API',
                                                        'series_id': 'CPILFESL'}}
                    except Exception as _e:
                        _cpi_errs.append(f'FRED-API:{type(_e).__name__}')
                        print(f'[Macro/CPI/FRED-API] ❌ {_e}')
                    # ── 方案2: BLS API（CUSR0000SA0L1E 核心 CPI SA）───────────────
                    try:
                        _rc = _s.post('https://api.bls.gov/publicAPI/v2/timeseries/data/',
                                      json={'seriesid': ['CUSR0000SA0L1E'],
                                            'startyear': str(_dt_cpi.date.today().year - 2),
                                            'endyear':   str(_dt_cpi.date.today().year)},
                                      headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'},
                                      timeout=15, verify=False)
                        print(f'[Macro/CPI/BLS] status={_rc.status_code}')
                        if _rc.status_code == 200:
                            _j = _rc.json()
                            _obs = (_j.get('Results') or {}).get('series', [{}])[0].get('data', [])
                            if len(_obs) >= 13:
                                _s2 = sorted([o for o in _obs if o.get('period', 'M13') != 'M13'],
                                             key=lambda x: (x['year'], x['period']))
                                _valid = []
                                for _o in _s2:
                                    try:
                                        _v = float(str(_o.get('value', '')).replace(',', ''))
                                        if _v > 0:
                                            _valid.append((_o, _v))
                                    except Exception:
                                        pass
                                if len(_valid) >= 13:
                                    _ents = [o for o, _ in _valid]
                                    _vals = [v for _, v in _valid]
                                    _yoy = round((_vals[-1] / _vals[-13] - 1) * 100, 2)
                                    # v18.169：補 prev_yoy 供 MK 黃金拐點偵測
                                    _prev_yoy = (round((_vals[-2] / _vals[-14] - 1) * 100, 2)
                                                 if len(_vals) >= 14 else None)
                                    _last = _ents[-1]
                                    _date = f"{_last['year']}-{int(_last['period'][1:]):02d}-01"
                                    print(f'[Macro/CPI/BLS] ✅ YoY={_yoy:.2f}% prev={_prev_yoy} date={_date}')
                                    return {'us_core_cpi': {'yoy': _yoy, 'prev_yoy': _prev_yoy,
                                                            'date': _date,
                                                            'source': 'BLS',
                                                            'series_id': 'CUSR0000SA0L1E'}}
                    except Exception as _e:
                        _cpi_errs.append(f'BLS:{type(_e).__name__}')
                        print(f'[Macro/CPI/BLS] ❌ {_e}')
                    return {'_err_cpi': ' | '.join(_cpi_errs) or 'all failed'}

                # ── 2b. Fed Funds Rate（FRED FEDFUNDS，月均有效利率）─────────────
                #   v18.169：MK 黃金拐點偵測需 CPI YoY × Fed Rate 同步月度比較。
                #   兩層備援：① fredgraph.csv 公開無 key ② FRED API 帶 key 加速。
                def _fetch_fed_funds():
                    import datetime as _dt_ff
                    import io as _io_ff
                    import pandas as _pd_ff
                    _ff_errs = []
                    # ── 方案0: FRED 公開 fredgraph.csv（無需 key）────────────────
                    try:
                        from src.data.proxy import fetch_url as _fu_ff
                        _r0 = _fu_ff('https://fred.stlouisfed.org/graph/fredgraph.csv',
                                     params={'id': 'FEDFUNDS'},
                                     timeout=10, attempts=1)
                        print(f'[Macro/FedFunds/fredgraph] response={"OK" if _r0 else "None"}')
                        if _r0 is not None and _r0.status_code == 200:
                            _df0 = _pd_ff.read_csv(
                                _io_ff.StringIO(_r0.content.decode('utf-8', errors='ignore')))
                            _df0 = _df0.dropna()
                            if len(_df0) >= 2:
                                _vals0 = _pd_ff.to_numeric(_df0.iloc[:, 1],
                                                           errors='coerce').dropna()
                                if len(_vals0) >= 2:
                                    _curr = round(float(_vals0.iloc[-1]), 2)
                                    _prev = round(float(_vals0.iloc[-2]), 2)
                                    _date = str(_df0.iloc[-1, 0])[:10]
                                    print(f'[Macro/FedFunds/fredgraph] ✅ {_prev:.2f}%→{_curr:.2f}% date={_date}')
                                    return {'fed_funds': {'current': _curr, 'prev': _prev,
                                                          'date': _date,
                                                          'source': 'FRED/fredgraph.csv',
                                                          'series_id': 'FEDFUNDS'}}
                            _ff_errs.append(f'fredgraph:rows<2({len(_df0)})')
                        else:
                            _ff_errs.append(f'fredgraph:HTTP{_r0.status_code if _r0 else "None"}')
                    except Exception as _e:
                        _ff_errs.append(f'fredgraph:{type(_e).__name__}')
                        print(f'[Macro/FedFunds/fredgraph] ❌ {_e}')
                    # ── 方案1: FRED API（FEDFUNDS + API key）────────────────────
                    try:
                        import os as _os_ff_f
                        from src.data.proxy import fetch_url as _fu_ff
                        _fred_key_ff = (_os_ff_f.environ.get('FRED_API_KEY') or
                                        (st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else None) or '')
                        _ff_start = (_dt_ff.datetime.now() - _dt_ff.timedelta(days=365*2)).strftime('%Y-%m-%d')
                        _ff_end = _dt_ff.datetime.now().strftime('%Y-%m-%d')
                        _ff_p = {'series_id': 'FEDFUNDS', 'file_type': 'json',
                                 'sort_order': 'asc', 'limit': 24,
                                 'observation_start': _ff_start,
                                 'observation_end': _ff_end}
                        if _fred_key_ff:
                            _ff_p['api_key'] = _fred_key_ff
                        _rc1 = _fu_ff('https://api.stlouisfed.org/fred/series/observations',
                                      params=_ff_p, timeout=12, attempts=1)
                        print(f'[Macro/FedFunds/FRED-API] response={"OK" if _rc1 else "None"}')
                        if _rc1 is not None:
                            _obs_f = [o for o in _rc1.json().get('observations', [])
                                      if o.get('value', '.') != '.']
                            if len(_obs_f) >= 2:
                                _vals_f = [float(o['value']) for o in _obs_f]
                                _curr = round(_vals_f[-1], 2)
                                _prev = round(_vals_f[-2], 2)
                                _date = _obs_f[-1]['date']
                                print(f'[Macro/FedFunds/FRED-API] ✅ {_prev:.2f}%→{_curr:.2f}% date={_date}')
                                return {'fed_funds': {'current': _curr, 'prev': _prev,
                                                      'date': _date,
                                                      'source': 'FRED-API',
                                                      'series_id': 'FEDFUNDS'}}
                    except Exception as _e:
                        _ff_errs.append(f'FRED-API:{type(_e).__name__}')
                        print(f'[Macro/FedFunds/FRED-API] ❌ {_e}')
                    return {'_err_fed_funds': ' | '.join(_ff_errs) or 'all failed'}

                # ── 3. 台灣 PMI（CIER 中華經濟研究院）────────────────────────────
                #   v3：Stock 端定位是台股視角，應抓「台灣製造業 PMI」（CIER 中華
                #   經濟研究院每月第一個工作日公布），而非美國 ISM PMI。
                #   舊版誤抓美國 ISM 導致與在地景氣脫節，且 ISM 自 2016-08 後 FRED
                #   斷供，三段爬蟲備援也常掛。改呼叫 macro_core.fetch_tw_pmi()
                #   共用函式（4 段備援：MacroMicro → CIER → StockFeel → 鉅亨）。
                #   注意：session_state key 仍為 'ism_pmi' 以維持向後相容（14 處讀取
                #   點不必動），但內容是台灣 PMI；UI 顯示為「🇹🇼 台灣製造業 PMI」。
                def _fetch_pmi():
                    """v3 薄殼：呼叫 macro_core.fetch_tw_pmi()，回傳台灣 CIER PMI。"""
                    from src.data.macro import fetch_tw_pmi as _ftp
                    _result = _ftp()
                    if _result.get('value') is not None:
                        return {'ism_pmi': _result}
                    # 失敗：只回傳 _err_pmi（不再帶 value:None junk 進 macro_info）
                    return {'_err_pmi': _result.get('_err_pmi', '4 段備援全失敗')}

                # ── 4. NDC 景氣對策信號 v2 — StockFeel + MacroMicro 雙源（v10.57.0 復活）
                #    舊源全廢（FinMind/NDC JSON/CKAN/行動版 HTML 都失效），改抓第三方。
                def _fetch_ndc():
                    import re as _re_ndc
                    from src.data.proxy import fetch_url as _fu_ndc
                    from bs4 import BeautifulSoup as _BS_ndc

                    # 方案 A: StockFeel 股感（每月更新文章，HTML 含「綜合分數 39」）
                    try:
                        _sf_url = ('https://www.stockfeel.com.tw/'
                                   '%E6%99%AF%E6%B0%A3%E5%B0%8D%E7%AD%96%E4%BF%A1%E8%99%9F-'
                                   '%E6%99%AF%E6%B0%A3%E6%8C%87%E6%A8%99-%E7%B7%A8%E5%88%B6-'
                                   '%E5%9C%8B%E7%99%BC%E6%9C%83/')
                        _sf_r = _fu_ndc(_sf_url, timeout=12, attempts=1)
                        if _sf_r is not None:
                            _sf_r.encoding = 'utf-8'
                            _txt_sf = _BS_ndc(_sf_r.text, 'html.parser').get_text(' ', strip=True)
                            # 找最近一筆「YYYY年M月.*?綜合(?:判斷)?分數.*?N分」
                            _m_sf = _re_ndc.search(
                                r'(20\d{2})\s*年\s*(\d{1,2})\s*月[^。]{0,80}?綜合(?:判斷)?分數[^\d]{0,15}(\d{1,2})\s*分',
                                _txt_sf)
                            if _m_sf:
                                _yr_sf, _mo_sf, _sc_sf = _m_sf.group(1), _m_sf.group(2), int(_m_sf.group(3))
                                if 9 <= _sc_sf <= 45:
                                    _date_sf = f'{_yr_sf}-{int(_mo_sf):02d}-01'
                                    print(f'[NDC/StockFeel] ✅ score={_sc_sf} date={_date_sf}')
                                    return {'ndc_signal': {'score': _sc_sf, 'signal': None,
                                                           'date': _date_sf, 'source': 'StockFeel'}}
                            print('[NDC/StockFeel] ⚠️ 未匹配「YYYY年M月...綜合分數N分」')
                    except Exception as _e_sf:
                        print(f'[NDC/StockFeel] ❌ {type(_e_sf).__name__}: {_e_sf}')

                    # 方案 B: MacroMicro 財經 M 平方（UGC Charts 公開頁面）
                    try:
                        _mm_url = 'https://www.macromicro.me/collections/10/tw-monitoring-indicators-relative'
                        _mm_r = _fu_ndc(_mm_url, timeout=12, attempts=1)
                        if _mm_r is not None:
                            _mm_r.encoding = 'utf-8'
                            _txt_mm = _BS_ndc(_mm_r.text, 'html.parser').get_text(' ', strip=True)
                            _m_mm = _re_ndc.search(
                                r'景氣對策信號[^。]{0,200}?(\d{1,2})\s*分',
                                _txt_mm)
                            if _m_mm:
                                _sc_mm = int(_m_mm.group(1))
                                if 9 <= _sc_mm <= 45:
                                    print(f'[NDC/MacroMicro] ✅ score={_sc_mm}')
                                    return {'ndc_signal': {'score': _sc_mm, 'signal': None,
                                                           'date': '', 'source': 'MacroMicro'}}
                            print('[NDC/MacroMicro] ⚠️ 未匹配「景氣對策信號...N分」')
                    except Exception as _e_mm:
                        print(f'[NDC/MacroMicro] ❌ {type(_e_mm).__name__}: {_e_mm}')

                    print('[NDC] ⚠️ 雙源皆失敗，回 _err_ndc 標記（v18.194 UI fail trace）')
                    return {'_err_ndc': 'StockFeel + MacroMicro 雙源皆失敗'}

                # ── 5. 台灣出口 YoY ─────────────────────────────────────────
                def _fetch_export():
                    import pandas as _pd7
                    import io as _io_ex
                    import os as _os_ex
                    import re as _re_ex
                    import datetime as _dt_ex
                    _s_ex = _mk_s()
                    _s_ex.verify = False
                    _s_ex.headers.update({'User-Agent': 'Mozilla/5.0',
                                          'Accept': 'application/json'})

                    # 方案 0 (2026-06 新增): 中華民國統計資訊網 stat.gov.tw 出口年增率
                    # 為什麼放首位？
                    #   stat.gov.tw 是 DGBAS 官方點資料頁，每月更新最新 YoY，HTML 含
                    #   「出口年增率 ... 12.3%」格式；走 fetch_url（NAS 中繼站）取台灣 IP。
                    try:
                        from src.data.proxy import fetch_url as _fu_stat
                        from bs4 import BeautifulSoup as _BS_stat
                        _stat_url = ('https://www.stat.gov.tw/Point.aspx?'
                                     'sid=t.8&n=3587&sms=11480')
                        _r_stat = _fu_stat(_stat_url, timeout=12, attempts=1)
                        if _r_stat is not None and _r_stat.status_code == 200:
                            _r_stat.encoding = 'utf-8'
                            _txt_stat = _BS_stat(_r_stat.text, 'html.parser').get_text(' ', strip=True)
                            # 模式：「2026年4月 出口年增率 18.9%」or「出口年增率 ... 18.9」
                            _m_stat = _re_ex.search(
                                r'(20\d{2})\s*年\s*(\d{1,2})\s*月[^。]{0,80}?'
                                r'出口[^。]{0,30}?年增率?[^\d\-]{0,15}(-?\d{1,3}\.\d)\s*%?',
                                _txt_stat)
                            if _m_stat:
                                _yr_s, _mo_s = int(_m_stat.group(1)), int(_m_stat.group(2))
                                _yoy_s = float(_m_stat.group(3))
                                if 1 <= _mo_s <= 12 and -80 <= _yoy_s <= 200:
                                    _date_s = f'{_yr_s}-{_mo_s:02d}'
                                    print(f'[Export/stat.gov.tw] ✅ YoY={_yoy_s:.2f}% date={_date_s}')
                                    return {'tw_export': {'yoy': _yoy_s, 'date': _date_s,
                                                          'source': 'stat.gov.tw'}}
                            print('[Export/stat.gov.tw] ❌ HTML 未含可解析 YoY')
                        else:
                            print(f'[Export/stat.gov.tw] ❌ HTTP {getattr(_r_stat, "status_code", "None")}')
                    except Exception as _e_stat:
                        print(f'[Export/stat.gov.tw] ❌ {type(_e_stat).__name__}: {_e_stat}')

                    # 方案FM: FinMind TaiwanEconomicIndicator 出口相關指標
                    try:
                        _fm_tok_ex = (_os_ex.environ.get('FINMIND_TOKEN') or
                                      (st.secrets.get('FINMIND_TOKEN') if hasattr(st, 'secrets') else None))
                        if _fm_tok_ex:
                            _ex_start_fm = (_dt_ex.date.today() - _dt_ex.timedelta(days=365*2)).strftime('%Y-%m-%d')
                            _fm_ex_r = _s_ex.get(
                                'https://api.finmindtrade.com/api/v4/data',
                                params={'dataset': 'TaiwanEconomicIndicator',
                                        'start_date': _ex_start_fm, 'token': _fm_tok_ex},
                                timeout=10)
                            if _fm_ex_r.status_code == 200:
                                _fm_ex_data = _fm_ex_r.json().get('data', [])
                                # 尋找出口相關指標（外銷訂單 or 出口）
                                for _kw_ex in ('出口', '外銷', 'export', 'Export'):
                                    _ex_rows = [r for r in _fm_ex_data
                                                if _kw_ex in str(r.get('indicator', ''))]
                                    if _ex_rows:
                                        _ex_rows.sort(key=lambda r: r.get('date', ''))
                                        # 找同類指標最新 13 筆算 YoY
                                        _ind_name = _ex_rows[-1].get('indicator')
                                        _same = [r for r in _ex_rows if r.get('indicator') == _ind_name]
                                        if len(_same) >= 13:
                                            _cur_ex = float(_same[-1].get('value', 0) or 0)
                                            _prev_ex = float(_same[-13].get('value', 1) or 1)
                                            if _prev_ex != 0:
                                                _yoy_ex = round((_cur_ex - _prev_ex) / abs(_prev_ex) * 100, 2)
                                                _date_ex = str(_same[-1].get('date', ''))[:7]
                                                print(f'[Export/FinMind] ✅ YoY={_yoy_ex:.2f}% date={_date_ex} ind={_ind_name}')
                                                return {'tw_export': {'yoy': _yoy_ex, 'date': _date_ex,
                                                                      'source': f'FinMind/{_ind_name}'}}
                                        break
                    except Exception as _e_fm_ex:
                        print(f'[Export/FinMind] ❌ {type(_e_fm_ex).__name__}: {_e_fm_ex}')

                    # 方案MOF: 財政部統計處 CSV — 透過 NAS proxy（台灣 IP 可直接存取）
                    try:
                        from src.data.proxy import fetch_url as _fu_ex
                        _now_ex = _dt_ex.date.today()
                        _mof_found = False
                        # v10.61.0: 月份迴圈從 4 砍到 2（當月+上月），避免最壞 8 URL × ~12s = 100s
                        # 拖爆 as_completed 70s timeout；MOF 通常上月就有，找不到再讓使用者手動重抓
                        for _m_off in range(0, 2):
                            if _mof_found:
                                break
                            _chk = (_now_ex.replace(day=1) - _dt_ex.timedelta(days=_m_off * 30))
                            for _mof_url in [
                                f'https://service.mof.gov.tw/public/Data/statistic/trade/excel/{_chk.year}{_chk.month:02d}.csv',
                                f'https://service.mof.gov.tw/public/Data/statistic/trade/html/{_chk.year}{_chk.month:02d}.csv',
                            ]:
                                try:
                                    _r_mof = _fu_ex(_mof_url, timeout=10, attempts=1)
                                    if _r_mof is not None and len(_r_mof.content) > 500:
                                        _df_mof = _pd7.read_csv(
                                            _io_ex.StringIO(_r_mof.content.decode('utf-8-sig', errors='ignore')),
                                            header=None)
                                        _vals_mof = _pd7.to_numeric(_df_mof.iloc[:, 1], errors='coerce').dropna()
                                        if len(_vals_mof) >= 13:
                                            _yoy_mof = round((_vals_mof.iloc[-1] - _vals_mof.iloc[-13]) /
                                                             abs(_vals_mof.iloc[-13]) * 100, 2)
                                            print(f'[Export/MOF] ✅ YoY={_yoy_mof:.2f}% url={_mof_url[-25:]}')
                                            _mof_found = True
                                            return {'tw_export': {'yoy': _yoy_mof,
                                                                  'date': f'{_chk.year}-{_chk.month:02d}',
                                                                  'source': 'MOF-proxy'}}
                                except Exception:
                                    continue
                    except Exception as _e_mof:
                        print(f'[Export/MOF] ❌ {type(_e_mof).__name__}: {_e_mof}')

                    # 方案DGTW: data.gov.tw dataset 6053「海關進出口貿易統計」CSV
                    #   v18.142：deep-research 確認 6053 月更（NDC 官方）；走 NAS proxy
                    try:
                        from src.data.proxy import fetch_url as _fu_ex
                        for _meta_url_ex in (
                            'https://data.gov.tw/api/v2/rest/dataset/6053',
                            'https://data.gov.tw/api/v1/rest/dataset/6053',
                        ):
                            try:
                                _rm_ex = _fu_ex(_meta_url_ex, timeout=10, attempts=1,
                                                headers={'Accept': 'application/json'})
                                if _rm_ex is None or _rm_ex.status_code != 200:
                                    continue
                                _jm_ex = _rm_ex.json()
                                _res_ex = (_jm_ex.get('result', {}).get('resources')
                                           or _jm_ex.get('resources')
                                           or _jm_ex.get('result', {}).get('distribution')
                                           or [])
                                _csv_url_ex = None
                                for _it in _res_ex:
                                    _fmt = str(_it.get('format', '')).upper()
                                    _u = (_it.get('url') or _it.get('resourceDownloadUrl')
                                          or _it.get('downloadUrl'))
                                    if _fmt in ('CSV', 'TEXT', 'XLS', 'XLSX') and _u:
                                        _csv_url_ex = _u
                                        break
                                if not _csv_url_ex:
                                    continue
                                _rc_ex = _fu_ex(_csv_url_ex, timeout=15, attempts=2)
                                if _rc_ex is None or _rc_ex.status_code != 200:
                                    continue
                                _df_dgtw = _pd7.read_csv(_io_ex.StringIO(
                                    _rc_ex.content.decode('utf-8-sig', errors='ignore')))
                                # 找出口值欄（含「出口」字、不含「增/率/比」字）
                                _val_k = next((c for c in _df_dgtw.columns
                                               if '出口' in str(c) and not any(
                                                   _x in str(c) for _x in ('增', '率', '比', '差'))), None)
                                _dt_k = next((c for c in _df_dgtw.columns
                                              if any(_x in str(c) for _x in ('年月', '月份', '日期', 'DATE', 'date'))), None)
                                if _val_k and _dt_k and len(_df_dgtw) >= 13:
                                    _df_dgtw = _df_dgtw.dropna(subset=[_val_k]).copy()
                                    _df_dgtw[_val_k] = _pd7.to_numeric(
                                        _df_dgtw[_val_k].astype(str).str.replace(',', ''),
                                        errors='coerce')
                                    _df_dgtw = _df_dgtw.dropna(subset=[_val_k])
                                    if len(_df_dgtw) >= 13:
                                        _cur_d = float(_df_dgtw[_val_k].iloc[-1])
                                        _prv_d = float(_df_dgtw[_val_k].iloc[-13])
                                        if _prv_d != 0:
                                            _yoy_d = round((_cur_d - _prv_d) / abs(_prv_d) * 100, 2)
                                            _date_d = str(_df_dgtw[_dt_k].iloc[-1])[:7]
                                            print(f'[Export/data.gov.tw-6053] ✅ YoY={_yoy_d:.2f}% date={_date_d}')
                                            return {'tw_export': {'yoy': _yoy_d, 'date': _date_d,
                                                                  'source': 'data.gov.tw/6053'}}
                            except Exception:
                                continue
                    except Exception as _e_dgtw:
                        print(f'[Export/data.gov.tw-6053] ❌ {type(_e_dgtw).__name__}: {_e_dgtw}')

                    # 方案FRED: FRED CSV（XTEXVA01TWM664S，OECD MEI，延遲 2-3 月）
                    #   v18.142 修：原本用 VALEXPTWM052N（IMF IFS，延遲 ~13 月）→ user
                    #   永遠看到「91 天前」。改 XTEXVA01TWM664S 立刻變新（deep-research 確認）。
                    try:
                        _ex_start = (_dt_ex.datetime.now() - _dt_ex.timedelta(days=365*5)).strftime('%Y-%m-%d')
                        _ex_end   = _dt_ex.datetime.now().strftime('%Y-%m-%d')
                        _fred_key_ex = (_os_ex.environ.get('FRED_API_KEY') or
                                        (st.secrets.get('FRED_API_KEY') if hasattr(st, 'secrets') else None) or '')
                        _fred_ex_p = {'id': 'XTEXVA01TWM664S', 'observation_start': _ex_start,
                                      'observation_end': _ex_end}
                        if _fred_key_ex:
                            _fred_ex_p['api_key'] = _fred_key_ex
                        _r_fred = _fu_ex('https://fred.stlouisfed.org/graph/fredgraph.csv',
                                         params=_fred_ex_p, timeout=8, attempts=1)
                        print(f'[Export/FRED-XTEXVA01TWM664S] response={"OK" if _r_fred else "None"}')
                        if _r_fred is not None and _r_fred.text.strip():
                            _df_fred = _pd7.read_csv(
                                _io_ex.StringIO(_r_fred.text),
                                names=['date', 'value'], skiprows=1)
                            _df_fred['value'] = _pd7.to_numeric(_df_fred['value'], errors='coerce')
                            _df_fred = _df_fred.dropna(subset=['value'])
                            if len(_df_fred) >= 13:
                                _cur_f = float(_df_fred['value'].iloc[-1])
                                _prev_f = float(_df_fred['value'].iloc[-13])
                                if _prev_f and _prev_f != 0:
                                    _yoy_f = round((_cur_f - _prev_f) / abs(_prev_f) * 100, 2)
                                    _date_f = str(_df_fred['date'].iloc[-1])[:7]
                                    print(f'[Export/FRED-XTEXVA01TWM664S] ✅ YoY={_yoy_f:.2f}% date={_date_f}')
                                    return {'tw_export': {'yoy': _yoy_f, 'date': _date_f,
                                                          'source': 'FRED/XTEXVA01TWM664S'}}
                    except Exception as _e_fred:
                        print(f'[Export/FRED-XTEXVA01TWM664S] ❌ {type(_e_fred).__name__}: {_e_fred}')

                    # 方案2: data.gov.tw CKAN — 財政部進出口統計（加 Accept header 防空 body）
                    try:
                        _pkg2 = _s_ex.get(
                            'https://data.gov.tw/api/3/action/package_search',
                            params={'q': '進出口貿易統計', 'fq': 'organization:mof', 'rows': 5},
                            headers={'Accept': 'application/json'},
                            timeout=5)
                        _pkg2_j = _pkg2.json()
                        _res_id2 = None
                        for _pk2 in ((_pkg2_j.get('result') or {}).get('results') or []):
                            for _rs2 in (_pk2.get('resources') or []):
                                if _rs2.get('format', '').upper() in ('CSV', 'TEXT'):
                                    _res_id2 = _rs2.get('url') or _rs2.get('download_url')
                                    break
                            if _res_id2:
                                break
                        if _res_id2:
                            _csv_ex = _s_ex.get(_res_id2, timeout=10)
                            _df_ex = _pd7.read_csv(
                                _io_ex.StringIO(_csv_ex.content.decode('utf-8-sig', errors='ignore')))
                            _val_k = next((c for c in _df_ex.columns
                                           if '出口' in c and '值' in c and '增' not in c), None)
                            _dt_k = next((c for c in _df_ex.columns
                                          if '年月' in c or '月份' in c or 'DATE' in c.upper()), None)
                            if _val_k and _dt_k and len(_df_ex) >= 13:
                                _df_ex = _df_ex.dropna(subset=[_val_k])
                                _cur = float(str(_df_ex[_val_k].iloc[-1]).replace(',', ''))
                                _prev = float(str(_df_ex[_val_k].iloc[-13]).replace(',', ''))
                                if _prev != 0:
                                    _yoy = round((_cur - _prev) / abs(_prev) * 100, 2)
                                    _dv = str(_df_ex[_dt_k].iloc[-1])[:7]
                                    print(f'[Export/gov-mof] ✅ YoY={_yoy:.2f}% date={_dv}')
                                    return {'tw_export': {'yoy': _yoy, 'date': _dv, 'source': 'MOF-CSV'}}
                        print(f'[Export/gov-mof] ❌ res_id={_res_id2}')
                    except Exception as _e_gov2:
                        print(f'[Export/gov-mof] ❌ {type(_e_gov2).__name__}: {_e_gov2}')

                    # v18.330 §1 Fail Loud：所有方案全失敗 → **不捏造**任何數值。
                    # 原本回傳一組寫死的歷史出口假值，會灌進總經儀表板、MK 拐點與 AI
                    # 摘要（違 §1 寧可炸不可造假）。改回空 dict（不貢獻 tw_export key）→
                    # 下游各 consumer 退為「待取得」placeholder（誠實顯示無資料）；失敗
                    # 事實由本 log 記錄供診斷（§2.4 可觀測性）。
                    print('[Export/fallback] ⚠️ 所有方案全失敗 → 回空（不捏造假值），UI 顯示「待取得」')
                    return {}

                # ── 並行執行（5 個獨立資料源同時跑，總時間 = max 而非 sum）──────
                # v10.61.0: 改手動 executor 管理，as_completed timeout 後 shutdown(wait=False)
                # 立刻逃離；避免 with-block 退出時 shutdown(wait=True) 卡在 stuck thread 上等
                # ~240s（fetch_url 三層重試 × 8 個 MOF URL）拖爆外層 _fut_macro.result(80s)。
                _r = {}
                _pool_mc = _TPE(max_workers=6)  # v18.169: 5→6 加 fed_funds
                try:
                    _futs_mc = {
                        _pool_mc.submit(_fetch_vix):        'vix',
                        _pool_mc.submit(_fetch_cpi):        'cpi',
                        _pool_mc.submit(_fetch_pmi):        'pmi',
                        _pool_mc.submit(_fetch_ndc):        'ndc',
                        _pool_mc.submit(_fetch_export):     'export',
                        _pool_mc.submit(_fetch_fed_funds):  'fed_funds',  # v18.169 MK 拐點
                    }
                    try:
                        for _fut_mc in _asc_mc(_futs_mc, timeout=70):
                            try:
                                _part = _fut_mc.result()
                                if _part:
                                    _r.update(_part)
                            except Exception as _e:
                                print(f'[Macro] ❌ {_futs_mc.get(_fut_mc, "?")}: {_e}')
                    except (TimeoutError, _ConcFutTimeout):
                        # 70s 到仍有 future 未完成：取消未完成者，保留已收到的 partial _r
                        _stuck = [_futs_mc[_f] for _f in _futs_mc if not _f.done()]
                        for _f_pending in _futs_mc:
                            if not _f_pending.done():
                                _f_pending.cancel()
                        print(f'[Macro] ⏰ as_completed 70s timeout，未完成={_stuck}，保留已收到 keys={list(_r.keys())}')
                finally:
                    # wait=False：不等 stuck thread 自然結束（thread 會 zombie 在背景跑完後自滅）
                    # 避免 with-block 預設 wait=True 把 _job_macro 卡到 240s
                    _pool_mc.shutdown(wait=False)

                # Failsafe：即使全失敗也回傳 partial 標記（不回 None），讓診斷頁能區分
                # 「沒抓」vs「抓過全失敗」；macro_info 至少有時間戳供 UX 判斷
                _r.setdefault('_loaded_at', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                if not any(k for k in _r if not k.startswith('_')):
                    _r['_all_failed'] = True
                # v18.353 PR-Q3 S-PROV-1 phase 19:集中注入 fetched_at 到每個 sub-dict。
                # 6 wrappers (_fetch_vix/cpi/pmi/ndc/export/fed_funds) 已有 'source' key
                # (各自 dict 內,如 'FRED/fredgraph.csv' / 'BLS' / 'MOF-CSV' 等),
                # 集中 setdefault('fetched_at') 比改 14 處 return point 乾淨。schema-additive,
                # caller 0 改;§2.2 provenance(source + fetched_at)完整化。
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
    # v18.310 桶群組 banner：AI 綜合(跨桶 AI §九 + 新聞 AI 裁決 §十一)
    from shared.macro_buckets import bucket_group_banner_html as _bgb
    st.markdown(_bgb('ai', 6), unsafe_allow_html=True)
    st.markdown(section_header('九', '🧠 跨桶｜總經 AI 投資決策分析', '🧠'), unsafe_allow_html=True)

    # ── 安全取數 ────────────────────────────────────────────────
    # v18.388:B-4 (1ee60c3) 把 _m8_* 隨 §八 section 抽至 section_mid local,§九 此處
    # 仍 reference → render 期 NameError。重抓 macro_info 以保持與 section_mid:58-64 同源。
    _macro_info_for_s9 = st.session_state.get('macro_info') or {}
    _m8_vix = _macro_info_for_s9.get('vix')
    _m8_pmi = _macro_info_for_s9.get('ism_pmi')
    _m8_exp = _macro_info_for_s9.get('tw_export')
    _m8_cpi = _macro_info_for_s9.get('us_core_cpi')
    _ai_vix  = float(_m8_vix.get('current', 0))  if _m8_vix else None
    _ai_vma  = float(_m8_vix.get('ma20', 0))     if _m8_vix else None
    _ai_is_cli = bool(_m8_pmi.get('is_oecd_cli', False)) if _m8_pmi else False
    _ai_cli  = float(_m8_pmi.get('value', 100))  if (_m8_pmi and _ai_is_cli) else None
    _ai_pmi  = float(_m8_pmi.get('value', 50))   if (_m8_pmi and not _ai_is_cli) else None
    _ai_exp  = float(_m8_exp.get('yoy', 0))      if _m8_exp else None
    _ai_cpi  = float(_m8_cpi.get('yoy', 0))      if _m8_cpi else None
    _ai_mi8  = st.session_state.get('m1b_m2_info') or {}
    _ai_m1b  = float(_ai_mi8['m1b_yoy']) if _ai_mi8.get('m1b_yoy') is not None else None
    _ai_m2   = float(_ai_mi8['m2_yoy'])  if _ai_mi8.get('m2_yoy') is not None else None
    _ai_gap  = round(_ai_m1b - _ai_m2, 2) if (_ai_m1b is not None and _ai_m2 is not None) else None
    _ai_bias = float(st.session_state.get('bias_info', {}).get('bias_240', 0))
    _ai_sox  = float((tech_s.get('費城半導體 SOX') or {}).get('pct') or 0)
    _ai_nvda = float((tech_s.get('輝達 NVDA') or {}).get('pct') or 0)
    _ai_twii_pct = float((tech_s.get('大盤 TWII') or tw_s.get('台股加權指數') or {}).get('pct') or 0)

    # ── ① 目前總經位階 ──────────────────────────────────────────
    _ai1_lbl, _ai1_clr, _ai1_desc, _ai1_cyc = '資料載入中', '#484f58', '請點擊更新總經拼圖', None
    _cycle_ref = _ai_cli if _ai_cli is not None else (_ai_pmi if _ai_pmi is not None else None)
    _cycle_exp = (_cycle_ref >= 100.0) if (_ai_cli is not None) else (_cycle_ref >= 50.0 if _cycle_ref is not None else None)
    if _ai_exp is not None:
        _exp_str = f'外銷訂單YoY={_ai_exp:+.1f}%'
        _cli_str = (f'OECD CLI={_ai_cli:.2f}' if _ai_cli is not None else
                    f'台灣 PMI={_ai_pmi:.1f}' if _ai_pmi is not None else '')
        if _cycle_exp and _ai_exp >= 10:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣擴張強勢期 📈', TRAFFIC_RED, 'bull'
            _ai1_desc = f'{_cli_str}（擴張）× {_exp_str}（強勁需求）— 主升段格局，基本面充分支撐'
        elif _cycle_exp and _ai_exp > 0:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣溫和擴張 🟢', TRAFFIC_GREEN, 'bull'
            _ai1_desc = f'{_cli_str}（擴張）× {_exp_str}— 穩步復甦，基本面有撐，持股安全'
        elif _cycle_exp and _ai_exp <= 0:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣高峰震盪 ⚡', TRAFFIC_YELLOW, 'peak'
            _ai1_desc = f'{_cli_str}（微擴張）× {_exp_str}— 高位整理，需求疲軟，留意反轉訊號'
        elif not _cycle_exp and _ai_exp >= 5:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣觸底回升 💎', '#58a6ff', 'recovery'
            _ai1_desc = f'{_cli_str}（收縮但出口反彈）× {_exp_str}— 左側佈局黃金窗口'
        elif not _cycle_exp and _ai_exp < 0:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣收縮期 📉', '#8b949e', 'bear'
            _ai1_desc = f'{_cli_str}（收縮）× {_exp_str}— 多看少做，等待出口數據翻正'
        else:
            _ai1_lbl, _ai1_clr, _ai1_cyc = '景氣整理期 🟡', TRAFFIC_YELLOW, 'neutral'
            _ai1_desc = f'{_cli_str} × {_exp_str}— 方向待確認，保守持股'
    elif _cycle_ref is not None:
        _cli_str = f'OECD CLI={_ai_cli:.2f}' if _ai_cli is not None else f'台灣 PMI={_ai_pmi:.1f}'
        _ai1_lbl = '景氣擴張（出口待確認）' if _cycle_exp else '景氣趨緩（出口待確認）'
        _ai1_clr = TRAFFIC_GREEN if _cycle_exp else TRAFFIC_YELLOW
        _ai1_cyc = 'bull' if _cycle_exp else 'neutral'
        _ai1_desc = f'{_cli_str} — 外銷訂單數據載入中'

    # ── ② 建議配置 ──────────────────────────────────────────────
    _ai2_lbl, _ai2_clr, _ai2_desc = '計算中', '#484f58', '等待 VIX 及資金數據'
    if _ai_vix is not None:
        _r1_ok  = _ai_vix < 20
        _r2_exp = _ai_exp is not None and _ai_exp >= 10
        _r2_gap = _ai_gap is not None and _ai_gap >= 1.0
        _r2_cnt = int(_r2_exp) + int(_r2_gap)
        _r3_sox = _ai_sox >= 1.5 or _ai_nvda >= 2.0
        _r3_tw  = _ai_twii_pct > 0
        _r3_cnt = int(_r3_sox) + int(_r3_tw)
        _fuel_str = ((' 出口+' if _r2_exp else '') + (' M1B-M2+' if _r2_gap else '')).strip(' +') or '—'
        if not _r1_ok:
            _ai2_lbl, _ai2_clr = '⛔ 防禦模式 持股0~20%', TRAFFIC_RED
            _ai2_desc = f'VIX={_ai_vix:.1f}≥20，大環境風險偏高，現金為王，等待 VIX<20 才考慮進場'
        elif _r2_cnt >= 2 and _r3_cnt >= 1:
            _ai2_lbl, _ai2_clr = '🚀 積極進攻 持股80~100%', '#f0e040'
            _ai2_desc = f'VIX={_ai_vix:.1f}安全 × 燃料充足（{_fuel_str}）× 點火訊號啟動 — 三環齊備，重壓主流'
        elif _r2_cnt >= 1 and _r3_cnt >= 1:
            _ai2_lbl, _ai2_clr = '🔥 標準多頭 持股60~80%', TRAFFIC_RED
            _ai2_desc = f'VIX={_ai_vix:.1f}安全，燃料（{_fuel_str}）有效，順勢佈局強勢個股，跌破10MA停損'
        elif _r3_cnt >= 1:
            _ai2_lbl, _ai2_clr = '🛡️ 試探建倉 持股30~50%', TRAFFIC_YELLOW
            _ai2_desc = '短線點火訊號存在但燃料不足，打帶跑策略，見好就收，嚴設停損'
        else:
            _ai2_lbl, _ai2_clr = '⏸️ 保守觀望 持股30%以下', '#8b949e'
            _ai2_desc = '三環條件均不足，保留現金等待更明確訊號，避免追高'

    # ── ③ 目前貨幣流向 ──────────────────────────────────────────
    _ai3_lbl, _ai3_clr, _ai3_desc = '待取得 M1B/M2', '#484f58', '央行貨幣數據載入中'
    if _ai_gap is not None:
        _gap_str = f'M1B={_ai_m1b:.1f}% M2={_ai_m2:.1f}% Gap={_ai_gap:+.2f}%'
        if _ai_gap >= 2.0:
            _ai3_lbl, _ai3_clr = '🔥 熱錢大量流入股市', TRAFFIC_RED
            _ai3_desc = f'{_gap_str} — 黃金交叉大幅擴散，投機資金湧入，活絡貨幣遠超廣義貨幣'
        elif _ai_gap >= 1.0:
            _ai3_lbl, _ai3_clr = '✅ 資金動能轉強', TRAFFIC_GREEN
            _ai3_desc = f'{_gap_str} — 活絡資金超越廣義貨幣，熱錢進場訊號確立，行情可期'
        elif _ai_gap >= 0:
            _ai3_lbl, _ai3_clr = '🟡 資金溫和偏多', TRAFFIC_YELLOW
            _ai3_desc = f'{_gap_str} — M1B微幅領先，資金偏多但動能尚未爆發，需等待 Gap≥1% 確認'
        elif _ai_gap > -1.0:
            _ai3_lbl, _ai3_clr = '⚠️ 資金略偏保守', TRAFFIC_YELLOW
            _ai3_desc = f'{_gap_str} — M2相對偏高，部分資金仍停留在定存，股市吸引力不足'
        else:
            _ai3_lbl, _ai3_clr = '📉 資金明顯外逃', '#8b949e'
            _ai3_desc = f'{_gap_str} — 死亡交叉，資金轉向固定收益，股市失血，謹慎操作'
    elif _ai_m1b is not None:
        _ai3_lbl, _ai3_clr = f'M1B={_ai_m1b:.1f}% M2待取得', '#484f58'
        _ai3_desc = 'M2 數據未就緒，暫無法判斷 Gap'

    # ── ④ 美股動態 ──────────────────────────────────────────────
    _ai4_lbl, _ai4_clr, _ai4_desc = '待取得', '#484f58', 'VIX / CPI 數據載入中'
    if _ai_vix is not None:
        _cpi_ok  = _ai_cpi is None or _ai_cpi < 3.0
        _cpi_wrm = _ai_cpi is not None and 3.0 <= _ai_cpi < 4.0
        _cpi_hot = _ai_cpi is not None and _ai_cpi >= 4.0
        _cpi_s   = f' CPI={_ai_cpi:.1f}%' if _ai_cpi is not None else ''
        _sox_s   = f' SOX={_ai_sox:+.1f}%' if _ai_sox else ''
        _vma_s   = f' MA20={_ai_vma:.1f}' if _ai_vma else ''
        if _ai_vix < 20 and _cpi_ok and (_ai_sox >= 1.5 or _ai_nvda >= 2.0):
            _ai4_lbl, _ai4_clr = '🚀 美股強勢，科技領漲', TRAFFIC_RED
            _ai4_desc = f'VIX={_ai_vix:.1f}（恐慌低）{_sox_s}（半導體點火）{_cpi_s} — 台股跟漲機率高，可積極佈局科技'
        elif _ai_vix < 20 and _cpi_ok:
            _ai4_lbl, _ai4_clr = '🟢 美股平穩，降息預期支撐', TRAFFIC_GREEN
            _ai4_desc = f'VIX={_ai_vix:.1f}{_vma_s}（安全）{_cpi_s} — 無系統性風險，有利個股選股表現'
        elif _ai_vix < 20 and _cpi_wrm:
            _ai4_lbl, _ai4_clr = '🟡 美股震盪，通膨黏性制約', TRAFFIC_YELLOW
            _ai4_desc = f'VIX={_ai_vix:.1f}尚可但{_cpi_s}偏高 — Fed降息預期受壓，資金轉向謹慎，避免過度加槓桿'
        elif _ai_vix < 20 and _cpi_hot:
            _ai4_lbl, _ai4_clr = '⚠️ 美股承壓，Fed鷹派升溫', TRAFFIC_YELLOW
            _ai4_desc = f'VIX={_ai_vix:.1f}{_cpi_s}超標 — 高利率環境延續，外資提款風險升高，注意匯率走勢'
        elif _ai_vix < 30:
            _ai4_lbl, _ai4_clr = '🟡 美股波動加劇，謹慎操作', TRAFFIC_YELLOW
            _ai4_desc = f'VIX={_ai_vix:.1f}（警戒區間 20~30）{_vma_s} — 市場情緒不確定，控制倉位，勿追高'
        else:
            _ai4_lbl, _ai4_clr = '🔴 美股恐慌模式，流動性危機', TRAFFIC_RED
            _ai4_desc = f'VIX={_ai_vix:.1f}≥30 — 全球流動性急凍，強制防禦，任何技術面買訊均視為誘多'

    # ── ⑤ 結論 ──────────────────────────────────────────────────
    _ai5_pts = []
    if _ai1_cyc == 'bull':
        _ai5_pts.append('景氣擴張有基本面支撐')
    elif _ai1_cyc == 'recovery':
        _ai5_pts.append('景氣觸底，左側佈局機會')
    elif _ai1_cyc == 'peak':
        _ai5_pts.append('高位整理，防範反轉')
    elif _ai1_cyc == 'bear':
        _ai5_pts.append('景氣收縮，防禦優先')
    if _ai_gap is not None:
        if _ai_gap >= 1.0:
            _ai5_pts.append(f'M1B-M2 Gap=+{_ai_gap:.1f}% 資金動能正向共振')
        elif _ai_gap < 0:
            _ai5_pts.append('M1B-M2死亡交叉，貨幣資金外逃')
    if _ai_vix is not None:
        if _ai_vix < 15:
            _ai5_pts.append(f'VIX={_ai_vix:.1f} 極度平靜')
        elif _ai_vix < 20:
            _ai5_pts.append(f'VIX={_ai_vix:.1f} 安全窗口')
        elif _ai_vix >= 30:
            _ai5_pts.append(f'VIX={_ai_vix:.1f} 觸發危機，暫停攻擊')
    if _ai_bias >= 15:
        _ai5_pts.append(f'年線乖離+{_ai_bias:.1f}% 高估值需嚴設停損')
    elif _ai_bias <= -5:
        _ai5_pts.append(f'年線乖離{_ai_bias:.1f}% 超跌逢低佈局')
    if _ai_exp is not None:
        if _ai_exp >= 10:
            _ai5_pts.append(f'外銷訂單YoY={_ai_exp:+.1f}% 出口強勁')
        elif _ai_exp < -5:
            _ai5_pts.append(f'外銷訂單YoY={_ai_exp:+.1f}% 出口衰退警訊')

    if _ai5_pts:
        _ai5_txt = '；'.join(_ai5_pts) + '。'
        _bull_score = (int(_ai1_cyc in ('bull', 'recovery')) +
                       int(_ai_gap is not None and _ai_gap >= 1.0) +
                       int(_ai_vix is not None and _ai_vix < 20) +
                       int(_ai_exp is not None and _ai_exp >= 0))
        _bear_score = (int(_ai1_cyc == 'bear') +
                       int(_ai_gap is not None and _ai_gap < 0) +
                       int(_ai_vix is not None and _ai_vix >= 30))
        if _bull_score >= 3 and _bear_score == 0:
            _ai5_clr, _ai5_icon = TRAFFIC_GREEN, '✅ 整體偏多，積極操作'
        elif _bear_score >= 2 or (_ai_vix is not None and _ai_vix >= 30):
            _ai5_clr, _ai5_icon = TRAFFIC_RED, '🚨 整體偏空，防禦為主'
        elif _bull_score >= 2:
            _ai5_clr, _ai5_icon = TRAFFIC_YELLOW, '🟡 溫和偏多，精選個股'
        else:
            _ai5_clr, _ai5_icon = '#8b949e', '⏸️ 中性觀望，等待訊號'
    else:
        _ai5_txt  = '請點擊「更新總經拼圖」載入資料後自動生成結論。'
        _ai5_clr, _ai5_icon = '#484f58', '⏳ 等待資料'

    # ── 渲染五維度卡片 ────────────────────────────────────────────
    _aic1, _aic2, _aic3 = st.columns(3)
    def _ai_card(title, label, desc, color):
        return (f'<div style="background:#0d1117;border:1px solid {color}44;border-radius:8px;'
                f'padding:12px;min-height:110px;">'
                f'<div style="font-size:10px;color:#484f58;margin-bottom:4px;">{title}</div>'
                f'<div style="font-size:13px;font-weight:700;color:{color};line-height:1.3;">{label}</div>'
                f'<div style="font-size:11px;color:#8b949e;margin-top:6px;line-height:1.5;">{desc}</div>'
                f'</div>')
    with _aic1:
        st.markdown(_ai_card('① 目前總經位階', _ai1_lbl, _ai1_desc, _ai1_clr), unsafe_allow_html=True)
    with _aic2:
        st.markdown(_ai_card('② 建議配置', _ai2_lbl, _ai2_desc, _ai2_clr), unsafe_allow_html=True)
    with _aic3:
        st.markdown(_ai_card('③ 目前貨幣流向', _ai3_lbl, _ai3_desc, _ai3_clr), unsafe_allow_html=True)

    _aic4, _aic5 = st.columns(2)
    with _aic4:
        st.markdown(_ai_card('④ 美股動態', _ai4_lbl, _ai4_desc, _ai4_clr), unsafe_allow_html=True)
    with _aic5:
        st.markdown(
            f'<div style="background:#0d1117;border:2px solid {_ai5_clr};border-radius:8px;'
            f'padding:12px;min-height:110px;">'
            f'<div style="font-size:10px;color:#484f58;margin-bottom:4px;">⑤ 結論</div>'
            f'<div style="font-size:14px;font-weight:900;color:{_ai5_clr};">{_ai5_icon}</div>'
            f'<div style="font-size:12px;color:#c9d1d9;margin-top:6px;line-height:1.6;">{_ai5_txt}</div>'
            f'</div>', unsafe_allow_html=True)

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


    # F-7.1 B-3:Section 10/11 AI 總裁決抽至 src/ui/tabs/macro/section_ai.py
    render_section_ai(_macro_info, _tl_eff_reg)
    st.caption("📖 想看總經原理教室(景氣循環 / PMI / 殖利率倒掛 / 美林時鐘 等 10 章)?"
               "→ 已移至「📖 系統說明書」Tab,含資料來源完整地圖 + 4 大師策略。")
