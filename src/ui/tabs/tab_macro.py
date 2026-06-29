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
# P3-D7 v18.390:今日作戰室抽至 macro/section_warroom.py
from src.ui.tabs.macro.section_warroom import render_section_warroom  # noqa: F401
# P3-D9 v18.391:紅綠燈卡抽至 macro/section_traffic_light.py(認錯補做)
from src.ui.tabs.macro.section_traffic_light import render_traffic_light_top  # noqa: F401
# P3-D10 v18.392:長期 regime + 雷達 slow_verdict 準備抽至 macro/section_long_term.py
from src.ui.tabs.macro.section_long_term import prepare_long_term_radar  # noqa: F401



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
    # 【模組一】紅綠燈決策儀表板(P3-D9 v18.391:抽至 section_traffic_light)
    # 回傳 (placeholder, show_market_data, tl_eff_reg);warroom_summary 內部寫。
    # ════════════════════════════════════════════════════════
    _tl_placeholder, _show_market_data, _tl_eff_reg = render_traffic_light_top()

    # ── v18.171/172/173 長期 regime + 雷達 slow_verdict 準備 ─────
    # P3-D10 v18.392:抽至 macro/section_long_term.py(64 LOC,LOW)。
    _lt, _rr_fred_key, _slow_v = prepare_long_term_radar()

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
    # P3-D7 v18.390:154 LOC 抽至 macro/section_warroom.py(closure 3:
    # _tl_eff_reg + _show_market_data + do_refresh)。
    render_section_warroom(_tl_eff_reg, _show_market_data, do_refresh)

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

            # ── do_refresh 完成後自動估算旌旗指數(不等掃描)──────
            # P3-D11 v18.392:抽至 src/services/jingqi_calc.compute_and_store_jingqi。
            from src.services.jingqi_calc import compute_and_store_jingqi
            compute_and_store_jingqi(df_adl_raw)

            # ── M1B-M2 + 乖離率 + 6-source macro 並發 ─────────
            # P3-D12 v18.392:抽至 src/services/macro_trio_orchestrator。
            # truthy guard 在 service 內,partial 場景不蓋 stale(§1)。
            from src.services.macro_trio_orchestrator import run_macro_trio_and_persist
            _fred_key_tr = (os.environ.get('FRED_API_KEY') or
                            (st.secrets.get('FRED_API_KEY')
                             if hasattr(st, 'secrets') else None) or '')
            _fm_tok_tr = (os.environ.get('FINMIND_TOKEN') or
                          (st.secrets.get('FINMIND_TOKEN')
                           if hasattr(st, 'secrets') else None) or '')
            run_macro_trio_and_persist(
                tw_raw=tw_raw,
                fred_api_key=_fred_key_tr,
                fm_token=_fm_tok_tr,
            )

            # ── 計算市場狀態(用已載入資料,不另外發請求)──────
            # P3-D13 v18.392:抽至 src/services/market_assessment_apply。
            from src.services.market_assessment_apply import compute_and_apply_market_assessment
            compute_and_apply_market_assessment(inst=inst, tw_raw=tw_raw, margin=margin)
        # ── 全域資料登錄中心:掃描所有已載入 DF → 寫 data_registry ────
        # P1-X v18.393:275 LOC 抽至 src/services/data_registry_scanner.py(L3 service)。
        # caller 注入 INTL/TW/TECH MAP 對齊 macro_registry_patch / macro_fetch_orchestrator
        # DI 風格(雖然 3 MAP 同 L3 services 內,但 explicit DI 利測試)。
        from src.services.data_registry_scanner import scan_and_write_data_registry
        scan_and_write_data_registry(
            intl_map=INTL_MAP, tw_map=TW_MAP, tech_map=TECH_MAP,
        )

        st.rerun()  # 資料更新完成,重跑腳本讓頂部看板讀取最新 session_state

    cd     = st.session_state.get('cl_data', {})

    # ── Registry 常態 Patch:每次頁面渲染都更新個股/ETF 部分(不重發請求) ──
    # P3-D8 v18.390:161 LOC 抽至 src/services/macro_registry_patch.py。
    # INTL/TW/TECH MAP + rp_entry/scalar/ts 由 caller 注入,避 L3→L2 循環。
    from src.services.macro_registry_patch import patch_registry as _patch_reg
    _patch_reg(intl_map=INTL_MAP, tw_map=TW_MAP, tech_map=TECH_MAP,
               rp_entry=rp_entry, rp_scalar=rp_scalar, rp_ts=rp_ts)

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

    # §十 總經訊號歷史驗證 — v18.191 archived。
    # 5 個 expander 內容 + 復活步驟見 `ARCHIVED_FEATURES.md`(v18.395 P5-A4 搬出)。


    # F-7.1 B-3:§十一 News AI 總裁決抽至 src/ui/tabs/macro/section_news_ai.py
    # v18.393 P0-FIX:D-12 抽 trio (a13bb25) 後 _macro_info 變數從 render_tab_macro 作用域消失,
    # 但此處 call 仍 reference → 走入 §十一 render path 100% NameError。
    # 從 session_state 重讀(由 run_macro_trio_and_persist 在 do_refresh 期寫入)。
    _macro_info = st.session_state.get('macro_info') or {}
    render_section_news_ai(_macro_info, _tl_eff_reg)
    st.caption("📖 想看總經原理教室(景氣循環 / PMI / 殖利率倒掛 / 美林時鐘 等 10 章)?"
               "→ 已移至「📖 系統說明書」Tab,含資料來源完整地圖 + 4 大師策略。")
