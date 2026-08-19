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
    - macro_alert (2): check_macro_alerts / fetch_macro_snapshot（render_macro_alerts 已搬 L4 macro_ui_components）
    - market_strategy: get_market_assessment
    - leading_indicators: build_leading_fast / render_leading_table
    - ui_widgets: beginner_kpi / kpi / strategy_conclusion（v19.174 去識別化改名）
  * F2(2026-08)前為「app.py 內部 (4): _bps / _get_fm_token / _tw_now_str /
    gemini_call」(L5→L6 上行 import)。現已全部歸位:gemini_call → L3
    src.services.app_ai_service;_get_fm_token → L0 src.config.get_finmind_token;
    _tw_now_str → L0 shared.macro_compute;_bps 整個拿掉(session 由 L3 orchestrator 建)。
  * src/data/news (1): fetch_macro_news(P5-B3-β R8 抽出,原 app._fetch_macro_news)

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
        check_macro_alerts, fetch_macro_snapshot,
    )
    from src.ui.render.macro_ui_components import render_macro_alerts  # v19.159:render 歸位 L4
    from src.services import get_market_assessment
    from src.data.macro import render_leading_table
    # v19.174 去識別化：teacher_conclusion → strategy_conclusion
    from src.ui.render import beginner_kpi, cond_badge, kpi, strategy_conclusion
    # F2(2026-08):原本這裡是 `from app import _bps, _get_fm_token, _tw_now_str,
    # gemini_call`(L5→L6 上行 import,CLAUDE.md V-UP-APP-1)。四個名字各自歸位:
    #   gemini_call  → L3 src/services/app_ai_service.py
    #   _get_fm_token→ L0 src/config/config.py::get_finmind_token
    #   _tw_now_str  → L0 shared/macro_compute.py::tw_now_str
    #   _bps         → 本檔不再需要:唯一用途是餵 fetch_macro_bundle 的
    #                  bps_session,現由 L3 orchestrator 自行向 L1 取(見下方呼叫)
    from src.services.app_ai_service import gemini_call
    from src.config import get_finmind_token as _get_fm_token
    from shared.macro_compute import tw_now_str as _tw_now_str
    # v18.398 P5-B3-β R8:news fetcher 已抽至 src/data/news
    from src.data.news import fetch_macro_news as _fetch_macro_news

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
        # v19.176 P0-A(§1):舊文案在這裡宣稱 50 秒上界、同頁 spinner 宣稱 60 秒 ——
        # 同一顆按鈕兩個數字,且**兩個都被 code 自己的逾時上限否定**
        # (fetch_macro_bundle 100s + run_macro_trio_and_persist 200s = 300s)。
        # (舊字串本身不在此重述,否則會反過來讓 test_stale_lying_copy_removed 失效)
        # 使用者在第 61 秒會合理判定「當掉了」。三處文案統一改實測 + 真上限,
        # 並由 tests/test_p0a_key_alerts_and_spinner.py 機器化釘住。
        help='抓取總經 / 籌碼 / 先行指標（吃 30 分內暖快取，通常數秒；'
             '冷啟動實測 40~75 秒；逾時上限最長 300 秒 ≈ 5 分鐘）。'
             'v18.329：不再清掉個股 / ETF / 健診等其他頁快取。',
    )
    # v18.329：強制重抓另立按鈕（對齊 Fund「🆕 強制重抓最新（清快取）」）。
    # 正常更新走暖快取＝快；要零殘留才按這顆（會一併清掉其他頁快取，較慢）。
    do_force = st.button(
        '🆕 強制重抓最新（清快取）',
        key='cl_force_refresh',
        on_click=_on_force_clear_click,
        use_container_width=True,
        # v19.176 P0-A(§1):原文案只寫「較慢」沒給任何量級 —— 2026-08-05 實測
        # 冷載 72.4 秒。給實測值而非模糊形容,使用者才知道 70 秒還在跑是正常的。
        help='完全清除快取（pkl + st.cache_data + proxy）後重抓，確保零殘留；'
             '實測冷載約 75 秒（逾時上限同上，最長 300 秒 ≈ 5 分鐘），'
             '且會一併清掉個股 / ETF 等其他頁快取。',
    )
    do_refresh = bool(do_refresh or do_force)
    if do_refresh:
        st.session_state['chips_loaded'] = True
        st.session_state.pop('cl_data', None)

    # ── AI 總結卡（置頂，讀取 section_news_ai 生成結果）────────
    # session_state key 由 section_news_ai.py 寫入 '_macro_ai_report'
    _macro_ai_top = st.session_state.get('_macro_ai_report', '')
    with st.expander(
        '🤖 AI 總經戰情摘要' + (' ✅ 已生成，點此展開' if _macro_ai_top else ' — 載入資料後點底部「分析」按鈕，結果顯示此處'),
        expanded=bool(_macro_ai_top),
    ):
        if _macro_ai_top:
            st.markdown(_macro_ai_top)
        else:
            st.info('點擊上方「🚀 一鍵更新全部數據」載入資料，再點底部「⚡ 生成 AI 總結分析」，結果同步顯示此處。')

    if not _macro_loaded:
        st.markdown(
            '<div style="padding:12px 0 8px;">'
            '<span style="font-size:22px;font-weight:900;color:#e6edf3;">🌍 總經位階評估</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.info('👉 點擊上方按鈕載入總經資料')
        return

    # ── ⚡ 今日關鍵橫幅(v19.108 第九份 4-C 精簡版)──────────────
    # 門檻層吃 section_mid 載入時寫入的 session_state['macro_alerts']
    # (MACRO_ALERT_RULES SSOT 命中);急變層吃 macro_info 的 vix 序列/
    # fed_funds prev。零新 I/O(全讀 session)。
    #
    # 🔴 v19.176 P0-A(§1 Fail Loud, Never Fake)—— 修「首輪假綠燈」:
    # 【現象】2026-08-05 22:26 線上首輪載入,橫幅印「✅ 今日關鍵：門檻＋急變
    #   雙層掃描無異常」,但同一頁下方「🔍 總經警示詳情」同時列著 🟡×2
    #   (CPI YoY 2.81% / 美債 10Y 4.63%),下一輪 rerun 才變「⚡ 今日關鍵(2 項)」。
    # 【根因】兩件事疊加:
    #   (a) 時序 —— `macro_alerts` 是頁面**下方**的 section_mid.py:61-62 才寫入,
    #       同一輪 render 較晚執行;此處(頁首)先跑 → 永遠讀到「上一輪」的值。
    #   (b) 語意 —— 舊 code 把 `None`(還沒評估)直接餵進 banner,而 banner 把
    #       「items 為空」一律當「無異常」→ **未評估被冒充成綠色斷言**。原註解
    #       自稱「誠實顯示無異常」,但「無異常」是結論不是狀態,正是 §1 禁止的
    #       「讓流程看起來成功」。
    # 【修法】照 app.py:502 `_gl_slot` 的 v19.171 同款手法(placeholder 延後填充):
    #   1. 此處只 `st.empty()` 佔位 —— 版面位置完全不變(仍在【模組一】紅綠燈之前)。
    #   2. 真正內容延到 section_mid 那一段跑完、`macro_alerts` 是本輪最新值
    #      之後才填(見下方 _fill_key_alerts 的兩個呼叫點)。
    #      ⚠️ 本註解**刻意迴避**該 render 函式名後面直接接左括號的字面組合 ——
    #      tests/test_macro_section_render_wiring.py:54 與 test_render_smoke.py
    #      用 str.index 取「函式名+左括號」的**第一個**出現位置來驗證 long→mid
    #      呼叫順序;註解裡若出現同樣字面,會被當成呼叫點而假性紅燈(該字面在註解
    #      區的 offset 遠小於真正呼叫點)。真正的呼叫順序見本檔下方 render 區。
    #   3. `None` / `[]` / 非空 list 三態顯示三種不同結果,None 與 [] **絕不**
    #      走綠色分支(判定與文案見 `key_alerts_banner` docstring)。
    # 【v19.171 踩過的坑已確認不會重演】`_macro_session_reset()`
    #   (macro/handlers.py:21-24)pop 的 10 個 key **不含** 'macro_alerts' /
    #   'macro_info';且填充時機在同一輪 render 內、section_mid 之後,不經過
    #   任何 on_click callback → 不會被清掉。
    _key_alerts_slot = st.empty()

    def _fill_key_alerts() -> None:
        """把 ⚡ 今日關鍵橫幅填回頂部佔位(§1:未評估 ≠ 無異常)。

        `bool(_ma_raw)` 一次涵蓋兩種「沒有結論」的狀態:
          - `None` = section_mid 這輪還沒跑到(未評估)
          - `[]`   = 跑了但 check_macro_alerts 一個指標都沒取到(無資料可評)
        兩者都傳 `threshold_scanned=False` → L4 走中性灰「尚未完成」;
        只有「非空 list」(真的評估過)才允許出現 ✅ 綠色「無異常」。
        """
        from src.compute.macro.daily_key_alerts import collect_key_alerts as _cka
        from src.ui.render.macro_ui_components import key_alerts_banner as _kab
        _ma_raw = st.session_state.get('macro_alerts')
        _key_alerts_slot.markdown(
            _kab(_cka(_ma_raw, st.session_state.get('macro_info')),
                 threshold_scanned=bool(_ma_raw)),
            unsafe_allow_html=True,
        )

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
    # v19.173 誠實化：本名詞表原寫「綜合健康度 = 均線＋籌碼＋景氣」，但
    # `macro_helpers.compute_macro_health` 建構上只有 2 個輸入（jqavg 旌旗指數 ×
    # HEALTH_WEIGHT_JQ 0.6 + score/max_score×100 × HEALTH_WEIGHT_SCORE 0.4；
    # HEALTH_FNET_BONUS 已於 v19.102 校準後歸零）—— 籌碼／景氣**一項都沒進公式**。
    # 舊敘述等於用文件背書錯誤認知（讓人以為看這一個數字＝看完五桶），故改寫。
    # 同批把「評分 x/4」改為 x/N：分母吃 market_regime 的 max_score（基本 4，
    # ad_ratio / m1b_m2_gap 有傳才升 5-6，見 market_strategy.py:151-155），
    # 卡片實際渲染即為動態分母（handlers.py:102,123）。
    # v19.177 P1-B 反捏造（§1）：本表原寫「旌旗指數（站上 20MA 家數比）」——
    # 全站無任何一行在算「站上均線的家數比」，真值是**上漲佔比的 5 日均**
    # （src/services/jingqi_calc.py:43；名詞 SSOT: ui_widgets.BREADTH_JINGQI）。
    # 同批把「信心 %」那列補上「會列出缺哪幾份資料」—— 對應 handlers.py 的修正：
    # 原本缺 1/5 項時 conf=80%，既進不了 conf<70 的列缺項分支、也過不了 conf<80
    # 的警告條件 ⇒ 降級完全看不見。
    with st.expander('🔰 看不懂上面那張燈號卡片的數字？點我 30 秒讀懂'):
        st.markdown('''卡片上的每個數字，用一句話看懂：

| 卡片欄位 | 白話意思 |
|---|---|
| **綜合健康度 /100** | 只有兩個輸入：旌旗指數（＝上漲佔比的 5 日均，屬「廣度」）60% ＋ 大盤評分 40%；**不含籌碼、景氣**，那些請看下方五桶燈號 |
| **信心 %** | 系統對「資料夠不夠新、夠不夠齊」的把握度；**低於 70% 會直接擋住燈號**；只要少任何一項，卡片下方就會列出「缺了哪幾份資料」 |
| **評分 x/N** | 大盤多空打分，越高越偏多頭；分母 N 隨資料齊全度變動（基本 4；ADL／M1B-M2 有值才升 5-6） |
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
        # v19.170(P0-3 資安):原本渲染 token 前 12 碼到公開頁面 — 憑證材料不得
        # 入 UI/log(截圖、螢幕分享、瀏覽器快取都會外洩)。改為只顯示長度,
        # 對齊 data_loader.py:349-351 已修好的同類問題。
        st.success(f'✅ FinMind Token 已設定（len={len(_fm_tok_now)}）', icon='🔑')

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
        # v19.176 P0-A:本路徑不會跑到 render_section_mid → 門檻層這輪沒評估。
        # 佔位若就這樣留空白等於「靜默」,一樣不誠實(§1)→ 顯式填中性灰
        # 「尚未完成」。注意此時 session 內可能還殘留上一輪的 macro_alerts,
        # bool() 判定會讓它顯示上一輪掃描結果 —— 這是**真的掃過**的值,
        # 非腦補;新鮮度由頁面「上次更新」時間戳承載。
        _fill_key_alerts()
        return

    if do_refresh:
        _fetch_ph = st.empty()
        # v18.333：改用 st.spinner 動畫載入指示（對齊 Fund tab1 行為）。原本只有
        # 靜態 st.info 文字 + 按鈕殘留 → 阻塞抓取時畫面看似凍結、分不清是否載完。
        # spinner 在整個抓取期間動畫旋轉，結束自動消失，使用者一眼看出「進行中」。
        # v19.176 P0-A(§1 Fail Loud, Never Fake — 文案不得與 code 行為矛盾):
        # 舊文案宣稱的 60 秒是**假的上界** —— 這個 with 區塊裡序列跑
        #   fetch_macro_bundle       逾時上限 _AS_COMPLETED_TIMEOUT
        #                            = max(_job_timeouts)=80 + 20 = 100s
        #                            (macro_fetch_orchestrator.py:170-192)
        #   run_macro_trio_and_persist 逾時上限 global_timeout_s = 200s
        #                            (macro_trio_orchestrator.py:27)
        # → 100 + 200 = **300 秒**才是 code 允許的最長等待。宣告 60 秒等於
        # 叫使用者在第 61 秒誤判當機並中斷(實測冷載 72.4 秒,正好落在誤判區)。
        # 數字改動時 tests/test_p0a_key_alerts_and_spinner.py 會擋下不同步。
        # 「最長 300 秒」的字面格式被該守衛測試 regex 解析,改寫請一併改測試。
        # ⚠️ 下一行**必須維持單行**:tests/test_macro_loading_spinner.py 有兩條斷言,
        # 一條比對 spinner 開頭那段中文的連續字面,另一條的 regex 要求整個 with 陳述
        # 落在同一行([^\n]*)。拆成多行字串串接會讓兩條同時假性紅燈(v19.176 踩過)。
        # 本註解亦刻意不重述那兩段字面 —— 否則 test_p0a 的上界守衛會從註解取到
        # 「文案」,把說明文字誤當成 spinner 內容(v19.176 也踩過這個)。
        with st.spinner('🚀 並行抓取 總經 + 籌碼 + 先行指標中…（暖快取數秒；冷啟動實測 40~75 秒；逾時上限最長 300 秒 ≈ 5 分鐘，未到此時間都還在跑，請勿判定當機）'):
            # P3-D4 v18.389:7-job orchestrator 下沉 src/services/macro_fetch_orchestrator
            from src.services.macro_fetch_orchestrator import fetch_macro_bundle
            _bundle = fetch_macro_bundle(
                load_heavy=_load_heavy,
                prev_cl_data=st.session_state.get('cl_data') or {},
                fm_token=(_get_fm_token() or FINMIND_TOKEN
                          or os.environ.get('FINMIND_TOKEN', '')),
                li_token=(_get_fm_token() or FINMIND_TOKEN
                          or os.environ.get('FINMIND_TOKEN', '')),
                # F2:原 `bps_session=_bps()`(L5 自己造 requests.Session,且要靠
                # `from app import _bps` 上行取)。改為不傳 → L3 orchestrator 內部
                # 向 L1 proxy_helper 取 SSOT session,建立時點不變。
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
                # 本輪真的抓到新資料 → 清掉「沿用上輪」降級標記
                st.session_state.pop('li_retain_meta', None)
                print(f'[先行指標] ✅ {len(df_li_a)} 筆 (有效欄={df_li_a.notna().any().sum()})')
            else:
                if 'li_latest' not in st.session_state:
                    st.session_state.pop('li_latest', None)
                # ── B4-a D-1c(§2.4「過期 cache 回傳須帶 is_stale,禁止靜默」)──
                # 這條 else 原本是**完全靜默**的:build_leading_fast 回 None(含
                # stale pickle 超過 leading_indicators._STALE_MAX_AGE_MIN=3 日
                # 被擋掉的情形)時,畫面照舊渲染上一輪的 li_latest —— 而那份 df
                # 是走正常路徑存進來的,身上沒有任何 is_stale 旗標。於是
                # 「本輪其實什麼都沒抓到」在 UI 上與「本輪抓得好好的」長得一模一樣。
                # 這是「9 天凍結卻無警示」的第二條漏網路徑(第一條是值本身凍結,
                # 由 shared.data_freshness.detect_frozen_columns 在 🔎 資料診斷頁攔)。
                # 這裡把「沿用上輪」顯式記錄成 session meta:rounds 累計失敗輪數、
                # since 記第一次開始沿用的時刻,資料診斷頁據此把籌碼面降級 🟡 並明講。
                # 註:只在真的還有舊資料可沿用時才記;li_latest 不存在時是單純的
                # 「沒資料」,由覆蓋率欄顯示 ⬜,不需要這個標記。
                _li_prev_retain = st.session_state.get('li_retain_meta')
                if not isinstance(_li_prev_retain, dict):
                    _li_prev_retain = {}
                if st.session_state.get('li_latest') is not None:
                    st.session_state['li_retain_meta'] = {
                        'rounds': int(_li_prev_retain.get('rounds', 0) or 0) + 1,
                        'since': _li_prev_retain.get('since') or _tw_now_str(),
                        'last_try': _tw_now_str(),
                        'reason': ('empty_df' if df_li_a is not None else 'none'),
                    }
                print(f'[先行指標] ⚠️ 回傳{"空" if df_li_a is not None else "None"} — '
                      f'沿用舊快取(連續第 '
                      f'{(st.session_state.get("li_retain_meta") or {}).get("rounds", 0)} '
                      f'輪),已標記 li_retain_meta 供資料診斷頁降級')
            try:
                _fetch_ph.empty()
            except Exception:
                pass
            try:
                from shared.cache_layer import ADL_LOG_PATH as _adl_lp  # D14b v19.75:跨檔路徑 SSOT
                with open(_adl_lp,'r',encoding='utf-8') as _af:
                    print('[ADL詳細]\n' + _af.read())
                import os as _rmf
                _rmf.remove(_adl_lp)
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
            def _sec_tr(_k):
                # v19.81:無 secrets.toml 時 st.secrets.get 會 raise(CI/裸跑)→ env-only
                try:
                    return st.secrets.get(_k) if hasattr(st, 'secrets') else None
                except Exception:
                    return None
            _fred_key_tr = (os.environ.get('FRED_API_KEY') or _sec_tr('FRED_API_KEY') or '')
            _fm_tok_tr = (os.environ.get('FINMIND_TOKEN') or _sec_tr('FINMIND_TOKEN') or '')
            run_macro_trio_and_persist(
                tw_raw=tw_raw,
                fred_api_key=_fred_key_tr,
                fm_token=_fm_tok_tr,
            )

            # ── 計算市場狀態(用已載入資料,不另外發請求)──────
            # P3-D13 v18.392:抽至 src/services/market_assessment_apply。
            from src.services.market_assessment_apply import compute_and_apply_market_assessment
            compute_and_apply_market_assessment(inst=inst, tw_raw=tw_raw, margin=margin,
                                                df_adl=df_adl_raw)
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

    # ── 市場狀態卡：用已載入的真實資料渲染 ────────────────
    _mkt_info = st.session_state.get('mkt_info')
    if _mkt_info:
        _mkt_placeholder.empty()
        _mkt_placeholder.empty()  # 市場評分已整合至頂部紅綠燈看板，不重複顯示


    # F-7.1 B-S2:Section 2 拐點偵測 / 市場狀態抽至 src/ui/tabs/macro/section_state.py
    # v19.183 D2:顯式傳 `_show_market_data`(= 快取 ≤30 分且非刷新中)。
    # 沒傳之前,本 section 會在快取過期時**無條件**重算紅綠燈並蓋掉頁頂那句
    # 「⏳ 燈號等待中（已過期）」→ 30 分鐘新鮮度閘門形同不存在(§2.4)。
    # 與 render_traffic_light_top 回傳的旗標同源,兩邊不可能再各判各的。
    render_section_state(_mkt_info, _mkt_placeholder, _tl_placeholder, cd,
                         show_market_data=_show_market_data)
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
    # ── ⚡ 今日關鍵橫幅:延後填充點(v19.176 P0-A)────────────────
    # 這是 `st.session_state['macro_alerts']` 剛被 section_mid.py:62 寫成
    # **本輪最新值**的第一個時點 → 立刻填回頁首佔位,不再落後一個 rerun。
    # 刻意「越早越好」而非放在函式最末:即使下方任一 section 拋例外被
    # `_render_tab_isolated` 接住,頁首橫幅已經是正確內容(不會留白 / 不會假綠)。
    _fill_key_alerts()
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
               "→ 已移至「📖 系統說明書」Tab,含資料來源完整地圖 + 4 大策略主題。")

    # v19.168 IMPL-B:移除冗餘的「🧬 AI 總結本頁」lite 卡 —— 本頁已有 §十一「🤖 AI 總裁決」
    # 深報告(Gemini 生成完整戰情),泛用 lite 摘要重複。自由問答走獨立「🧬 AI 問答」tab。
