"""TAB 個股深度分析 + 健康度評分 — 從 app.py 抽出（PR P2-B Phase 5-C）

依賴策略
========
- Top-level: streamlit（最穩定）
- 函式內 late import 41 個依賴，避免循環 import：
  * stdlib: datetime, pandas, plotly
  * 設定: config.FINMIND_TOKEN
  * 外部模組: v4_strategy_engine / daily_checklist / v5_modules
    / financial_health_engine / tech_indicators / scoring_helpers / scoring_engine
    / ui_widgets / chart_plotter / data_loader
  * app.py 內部 (11): _fetch_stock_news / api_key / fetch_dividend_data
    / fetch_financials / fetch_price_data / fetch_quarterly / fetch_quarterly_extra
    / fetch_revenue / gemini_call / generate_ai_comment / render_health_score

呼叫端
======
- app.py: `with tab_stock: render_tab_stock()`
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.stock_buckets import (
    compute_stock_section_levels,
    get_pb_bands as _get_pb_bands_ssot,
    pb_bands_label as _pb_bands_label_ssot,
    render_stock_toc_html,
    section_header_html,
)
from shared.thresholds import YIELD_HIGH_DEC, YIELD_MID_DEC, YIELD_LOW_DEC
from shared.ttls import TTL_1DAY
# v18.325 PR-C: 健康度分級 + 龍頭資本支出門檻改用既有 SSOT（原 inline，§3.3 反捏造）
from shared.health_thresholds import HEALTH_GRADE_A_MIN, HEALTH_GRADE_B_MIN
from shared.signal_thresholds import (
    BB_DROP_OUT_RATIO,
    BB_NEAR_UPPER_RATIO,
    CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT,
    FGMS_LABEL_T2,
    FGMS_LABEL_T3,
    MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
    MARGIN_BALANCE_WARN_THRESHOLD_YI,
    SQ_GOOD_MIN,
    SQ_STABLE_MIN,
    STOCK_BIAS_DEEP_DEVIATION_PCT,
    STOCK_BIAS_MILD_DEVIATION_PCT,
    STOCK_BIAS_OVERHEAT_PCT,
    STOCK_RS_NEUTRAL_MIN,
    STOCK_RS_STRONG_MIN,
    STOP_LOSS_DEFAULT_PCT,
    STOP_PROFIT_T1_PCT,
    STOP_PROFIT_T2_PCT,
    VOLUME_RATIO_DRY,
    VOLUME_RATIO_MILD,
    VOLUME_RATIO_SURGE,
)
from src.ui.tabs.tab_helpers import (
    classify_bias_zone,            # v18.336 PR-H4:月線/年線乖離分層 SSOT
    classify_rs_zone,              # v18.337 PR-H5:RS 數值評級 SSOT
    classify_stock_status_lamp,    # v18.336 PR-H4:操作狀態燈 SSOT
    classify_trend_4tier,
    compute_stop_levels,           # v18.336 PR-H4:停利停損 SSOT
    format_condition_emoji, parse_cash_flow_ratio, safe_ma,
)
from src.ui.pages import kline_end_date
# v18.326 ── BPS / industry_category fetcher 已 SSOT 化(原私有 _fetch_*,組合 Tab 共用)──
from src.data.core import fetch_bps, fetch_industry_category
# R-FETCH-1 v18.412 ── 股本 fetcher 已搬至 L1(原私有 _fetch_share_capital 在 UI 層違憲)
from src.data.stock.share_capital_fetcher import fetch_share_capital


# v18.326 ── P/B 帶狀已下沉 shared/stock_buckets.py SSOT(組合 Tab 共用)
# v18.407 U4 Phase 3-B ── _fetch_pbratio_from_twse 已搬至 stock_sections.section_357_valuation


def _precompute_xsec(df2, sid2, rev2, qtr2, qtr_extra2) -> dict:
    """v18.309 Bug2 Stage 1：compute-once 跨段依賴 — AI 摘要與顯示段執行順序解耦。

    背景：個股面板有 4 組值「在顯示段算、3000 行後 AI 摘要跨段引用」
    (籌碼 _con20/_cty20/_sig20、相對強度 _rs_val、股本 _capital、先行指標
    _li_*)，導致物理重排會讓 AI 摘要落 fallback「未取得」(§1 靜默降級)。

    本函式於資料載入後**一次算完**這 4 組值 → AI 摘要改讀本 dict，與顯示段
    執行順序解耦，Stage 2 才能安全物理重排。顯示段仍各自重算自己 local(值相同)。

    各組獨立 try：某組失敗 → 該 key 缺席，AI 端既有 guard 落 fallback(行為等價)。
    純函式(除 fetch_share_capital 帶 @cache I/O,R-FETCH-1 v18.412 已搬至 L1),可單測 graceful degradation。

    Returns
    -------
    dict：可能含 con20/cty20/sig20 / rs_val / capital / li_results/li_green/
    li_yellow/li_red；任何輸入異常 → 缺對應 key(不 raise，不偽造)。
    """
    from src.services import analyze_20d_chips_from_df
    from src.compute.scoring import calc_rs_score, calc_leading_indicators_detail
    xsec: dict = {}
    # 1) 籌碼集中度(原 L1438 籌碼顯示段)— 只依賴 df2
    try:
        _c = analyze_20d_chips_from_df(df2)
        if isinstance(_c, dict) and not _c.get('error'):
            xsec['con20'] = _c['concentration']
            xsec['cty20'] = _c['continuity']
            xsec['sig20'] = _c['signal']
    except Exception:
        pass
    # 2) RS 相對強度(原 L902 進場顯示段)— 只依賴 df2
    try:
        xsec['rs_val'] = calc_rs_score(df2)
    except Exception:
        pass
    # 3) 股本(原 L1049 龍頭預警段)— 只依賴 sid2(帶 cache I/O)
    try:
        xsec['capital'] = fetch_share_capital(sid2)
    except Exception:
        pass
    # 4) 基本面 6 大先行指標(原 L2320 基本面段)— 依賴 rev2/qtr2/qtr_extra2
    try:
        _li = calc_leading_indicators_detail(rev_df=rev2, qtr_df=qtr2, bs_cf_df=qtr_extra2)
        xsec['li_results'] = _li
        xsec['li_green'] = sum(1 for _r in _li if _r['signal'] == '🟢')
        xsec['li_yellow'] = sum(1 for _r in _li if _r['signal'] == '🟡')
        xsec['li_red'] = sum(1 for _r in _li if _r['signal'] == '🔴')
    except Exception:
        pass
    return xsec


def render_tab_stock():
    # ─ Late imports（避免循環 import）─
    import datetime
    import pandas as pd
    import plotly.graph_objects as go
    from src.config import FINMIND_TOKEN
    # 外部模組
    from src.compute.strategy import V4StrategyEngine
    from src.services import analyze_20d_chips_from_df
    from src.compute.scoring import (
        compute_tech_bearish, judge_news_sentiment_cached, evaluate_exit_signals,
    )
    from src.compute.strategy import (
        analyze_fundamental_leading,
        calc_dividend_yield_357,
        detect_bollinger_breakout,
    )
    from src.services import analyze_financial_health, no_ai_overall_verdict
    from src.compute.strategy import (
        calc_rsi, calc_ibs, calc_volume_ratio,
        calc_kd, calc_bollinger, calc_vcp,
    )
    from src.compute.scoring.scoring_helpers import calc_fundamental_score, calc_health_score, health_grade  # v18.362 F-Q2:直打 submod,避撞 scoring_engine.calc_fundamental_score(同名不同 signature SSOT 違憲,留下個 PR 處理 rename)
    from src.compute.scoring import calc_rs_score, rs_slope
    # C1 v18.401:乖離率公式 SSOT(取代 4 處 inline (price-MA)/MA*100)
    from shared.calc_helpers import calc_bias_pct
    from src.ui.render import kpi, signal_box, teacher_conclusion
    from src.ui.render import plot_combined_chart, plot_quarterly_chart, plot_revenue_chart
    # U2 v18.401:統一容器框樣式 SSOT(取代 4 處 inline <div style="background..."> 重複)
    # U2-b v18.403:再補 border_left_banner 收 3 處 banner pattern
    from src.ui.render.tab_sections import border_left_banner, box_wrapper_close, box_wrapper_open
    from src.data.core import fetch_financial_statements
    # app.py 內部 helper
    from app import api_key, gemini_call
    # U5 B3-δ v18.405:6 fetcher 已抽至 L1 src/data/stock/app_stock_fetchers.py
    from src.data.stock.app_stock_fetchers import (
        fetch_dividend_data, fetch_financials, fetch_price_data,
        fetch_quarterly, fetch_quarterly_extra, fetch_revenue,
    )
    # U5 B3-γ v18.404:render_health_score 已抽至 L4
    from src.ui.render.app_render import render_health_score
    # v18.398 P5-B3-β R7:generate_ai_comment 已抽至 L3 service
    from src.services.app_ai_service import generate_ai_comment
    # v18.398 P5-B3-β R8:_fetch_stock_news 已抽至 L1 data
    from src.data.news import fetch_stock_news as _fetch_stock_news

    # v18.286 Empty state:解說卡 + 抓取項目 info 改成「資料載入後才出現」(對齊 fund 風格)。
    # 標題 / 操作列 / 載入按鈕永遠顯示;說明性區塊只在有 t2_data 時 render。
    _t2_loaded = bool(st.session_state.get('t2_data'))
    if _t2_loaded:
        st.markdown('''<div style="background:#0a1628;border:1px solid #1f6feb;border-radius:12px;padding:16px;margin-bottom:12px;">
<div style="font-size:18px;font-weight:900;color:#58a6ff;margin-bottom:8px;">🔬 個股深度分析 — 這支股票值得買嗎？</div>
<div style="font-size:13px;color:#c9d1d9;line-height:1.8;">
輸入你感興趣的股票代碼，系統會告訴你：<br>
• <b>現在貴不貴？</b>（357估值 + 河流圖）<br>
• <b>趨勢向上還是向下？</b>（健康度評分）<br>
• <b>大股東在買還是賣？</b>（法人籌碼）<br>
• <b>什麼時候該進場、出場？</b>（進出場訊號）<br>
💡 <b>建議：</b>先到「比較 × 排行」掃描找到候選股，再來這裡做最後確認。
</div></div>''', unsafe_allow_html=True)
    st.markdown("""<div style="padding:6px 0 4px;">
<span style="font-size:20px;font-weight:900;color:#e6edf3;">🔬 個股深度分析</span>
<span style="font-size:11px;color:#484f58;margin-left:10px;">健康評分 · 357評價 · 領先指標 · VCP · 布林 · K線 · AI五維</span>
</div>""", unsafe_allow_html=True)

    # ── 操作列 ──────────────────────────────────────────────
    t2_r1c1, t2_r1c2, t2_r1c3, t2_r1c4 = st.columns([2, 1, 1, 1])
    with t2_r1c1:
        t2_sid = st.text_input('個股代碼', value='2330', key='t2_sid', placeholder='如：2330')
    with t2_r1c2:
        t2_days = st.slider('天數', 60, 400, 250, 10, key='t2_days')
    with t2_r1c3:
        t2_use_normal = st.checkbox('一般K線', value=False, key='t2_use_normal')
        t2_adjusted   = not t2_use_normal
    with t2_r1c4:
        t2_run = st.button('🔍 載入完整分析', key='t2_run', type='primary', use_container_width=True)

    # ── 均線選擇（移入Tab2，無需展開）──────────────────────
    with st.container(border=True):
        st.markdown('<span style="font-size:11px;color:#8b949e;">📐 均線顯示設定</span>', unsafe_allow_html=True)
        ma_c1,ma_c2,ma_c3,ma_c4,ma_c5,ma_c6 = st.columns(6)
        with ma_c1:
            show_ma5   = st.checkbox('MA5',      value=False, key='t2_ma5')
        with ma_c2:
            show_ma20  = st.checkbox('MA20 月線', value=True,  key='t2_ma20')
        with ma_c3:
            show_ma60  = st.checkbox('MA60 季線', value=False, key='t2_ma60')
        with ma_c4:
            show_ma100 = st.checkbox('MA100',     value=True,  key='t2_ma100')
        with ma_c5:
            show_ma120 = st.checkbox('MA120',     value=False, key='t2_ma120')
        with ma_c6:
            show_ma240 = st.checkbox('MA240 年線',value=False, key='t2_ma240')
    show_ma_dict = {'MA5':show_ma5,'MA20':show_ma20,'MA60':show_ma60,
                    'MA100':show_ma100,'MA120':show_ma120,'MA240':show_ma240}

    # v18.286 Empty state:「自動從網路抓取」說明卡也只在資料載入後顯示
    if _t2_loaded:
        st.markdown("""<div style="background:#161b22;border:1px solid #21262d;border-left:4px solid #ffd700;
border-radius:8px;padding:10px 14px;font-size:12px;color:#8b949e;">
<b style="color:#ffd700;">自動從網路抓取：</b><br>
K線+均線(FinMind) · 三大法人籌碼 · 融資融券 · 357股利評價 · 月/季營收毛利率 · 合約負債/資本支出 · 健康評分(RSI+量比+IBS+KD+布林)
</div>""", unsafe_allow_html=True)

    if t2_run:
        sid2 = t2_sid or '2330'
        st.info(f'🌐 抓取 {sid2} 全方位數據...')
        # v18.196 並行化：7 個獨立 IO（含出場點 RSS 預抓）從序列改 ThreadPoolExecutor →
        # cold-start 省 30-50s + 預抓 RSS 標題避免下游出場點區塊阻塞 3-5s
        from concurrent.futures import ThreadPoolExecutor as _TPE_t2
        with _TPE_t2(max_workers=7) as _ex_t2:
            _fu_price = _ex_t2.submit(fetch_price_data, sid2, t2_days)
            _fu_div   = _ex_t2.submit(fetch_dividend_data, sid2)
            _fu_fin   = _ex_t2.submit(fetch_financials, sid2, '')
            _fu_rev   = _ex_t2.submit(fetch_revenue, sid2)
            _fu_qtr   = _ex_t2.submit(fetch_quarterly, sid2)
            _fu_qtr_extra = _ex_t2.submit(fetch_quarterly_extra, sid2)
            _fu_news  = _ex_t2.submit(_fetch_stock_news, sid2, sid2, 8, recency='3m')
            df2, name2, err2 = _fu_price.result()
            avg_div2, yearly2, div_src2 = _fu_div.result()
            cl2, cx2, _capex2, _cl_src2, _cx_src2, _, _fin_errs2 = _fu_fin.result()
            rev2, _ = _fu_rev.result()
            qtr2, _ = _fu_qtr.result()
            qtr_extra2, _ = _fu_qtr_extra.result()   # BS+CF時序（合約負債/存貨/資本支出）
            try:
                _raw_news_pre = _fu_news.result() or []
                st.session_state[f'_exit_news_titles_{sid2}'] = [
                    n.get('title', '') for n in _raw_news_pre if n.get('title')
                ]
            except Exception:
                pass
        rsi2     = calc_rsi(df2)
        ibs2     = calc_ibs(df2)
        vr2      = calc_volume_ratio(df2)
        k2, d2   = calc_kd(df2)
        bb2          = calc_bollinger(df2)
        bb_breakout2 = detect_bollinger_breakout(df2)  # B9: 預算一次，避免 section_health_score 重算
        vcp2     = calc_vcp(df2)
        health2, details2 = calc_health_score(df2, rsi2, ibs2, vr2, k2, d2, bb2)
        cur_price2 = float(df2['close'].iloc[-1]) if df2 is not None and not df2.empty else 0
        from src.config import get_stock_name as _gsn2
        _name2_resolved = (name2 if name2 and name2 != sid2 else None) or _gsn2(sid2) or sid2
        st.session_state['t2_data'] = {
            'sid':sid2,'name':_name2_resolved,'df':df2,'err':err2,
            'avg_div':avg_div2,'yearly':yearly2,'div_src':div_src2,
            'cl':cl2,'cx':cx2,'capex':_capex2,'rev':rev2,'qtr':qtr2,'qtr_extra':qtr_extra2,
            'cl_src': _cl_src2,'cx_src': _cx_src2,'fin_errs': _fin_errs2,
            'rsi':rsi2,'ibs':ibs2,'vr':vr2,'k':k2,'d':d2,'bb':bb2,'bb_breakout':bb_breakout2,'vcp':vcp2,
            'health':health2,'details':details2,'price':cur_price2,
            'fetched_at': pd.Timestamp.now(),
        }
        # 快取最後一次成功抓到的月營收/季財報，供下次失敗時 fallback
        if rev2 is not None and not rev2.empty:
            st.session_state[f'_last_rev_{sid2}'] = rev2
        if qtr2 is not None and not qtr2.empty:
            st.session_state[f'_last_qtr_{sid2}'] = qtr2

    t2d = st.session_state.get('t2_data')
    if not t2d:
        st.info('👆 輸入股票代碼後點擊「🔍 載入完整分析」')
    else:
        sid2   = t2d['sid']
        name2  = t2d['name']
        price2 = t2d['price']
        df2    = t2d['df']
        health2 = t2d['health']
        details2 = t2d['details']
        rsi2=t2d['rsi']
        ibs2=t2d['ibs']
        vr2=t2d['vr']
        k2=t2d['k']
        d2=t2d['d']
        bb2=t2d['bb']
        bb_breakout2=t2d.get('bb_breakout')
        vcp2=t2d['vcp']
        avg_div2=t2d['avg_div']
        yearly2=t2d['yearly']
        cl2=t2d['cl']
        cx2=t2d['cx']
        _capex2=t2d.get('capex')   # v18.457 Task#20: CF 資本支出(實際支出，區別 cx2 固定資產存量)
        _cl_src2=t2d.get('cl_src','')
        _cx_src2=t2d.get('cx_src','')
        _fin_errs2=t2d.get('fin_errs',[])
        rev2=t2d['rev']
        qtr2=t2d['qtr']
        qtr_extra2=t2d.get('qtr_extra')
        # Fallback 到快取（若本次抓取失敗）
        _rev2_cached = False
        _qtr2_cached = False
        if (rev2 is None or rev2.empty) and st.session_state.get(f'_last_rev_{sid2}') is not None:
            rev2 = st.session_state[f'_last_rev_{sid2}']
            _rev2_cached = True
        if (qtr2 is None or qtr2.empty) and st.session_state.get(f'_last_qtr_{sid2}') is not None:
            qtr2 = st.session_state[f'_last_qtr_{sid2}']
            _qtr2_cached = True

        # v18.309 Bug2 Stage 1：compute-once 跨段依賴(資料載入完成後一次算完)。
        # AI 摘要(L3200+)改讀 _xsec → 與顯示段執行順序解耦，Stage 2 物理重排才安全。
        _xsec = _precompute_xsec(df2, sid2, rev2, qtr2, qtr_extra2)

        # B5 v19.75(review 監控盲區):股本 meta 供 data_registry_scanner
        # (fetch_share_capital 失敗回 0.0 → scanner 登 missing 亮紅可見)
        try:
            st.session_state['t2_xsec_meta'] = {'sid': sid2, 'capital': _xsec.get('capital')}
        except Exception as _e_xm:
            print(f'[tab_stock] xsec meta 寫入失敗: {type(_e_xm).__name__}: {_e_xm}')

        # v19.83(第六份 review 3-7):V4 外本比分母 t2_shares_{sid} 原全 repo 無任何
        # 寫入 — section_health_score 永遠 fallback 預設 1,000,000 張,台積電(2,593 萬張)
        # 高估 26×、小型股低估數十倍,外本比門檻(0.5%/0.3%/0.1%)全失真。
        # 發行張數 = 股本(元) / 10(面額) / 1000(股/張);股本抓取失敗(0.0)不寫,
        # 維持既有 fallback(§1:不虛構)。
        try:
            _cap_v4 = float(_xsec.get('capital') or 0.0)
            if _cap_v4 > 0:
                st.session_state[f't2_shares_{sid2}'] = int(_cap_v4 / 10000)
        except Exception as _e_shv4:
            print(f'[tab_stock] t2_shares 寫入失敗: {type(_e_shv4).__name__}: {_e_shv4}')

        # v18.457 Task#18：寫入 t2_inst，供 section_kline_chart / section_health_score 讀取
        # df2 已含外資/投信欄（T86/TPEX merge，單位：張），取最後一日作為當前方向指標
        if df2 is not None and not df2.empty and '外資' in df2.columns and '投信' in df2.columns:
            try:
                st.session_state['t2_inst'] = {
                    '外資': float(df2['外資'].iloc[-1] or 0),
                    '投信': float(df2['投信'].iloc[-1] or 0),
                }
            except Exception:
                pass
        elif 't2_inst' not in st.session_state:
            st.session_state['t2_inst'] = {}

        # v18.337 user：每桶 Bar 上加「一句結論 + 燈號」。用上方 compute-once 的訊號
        # (health2 + _xsec rs_val/sig20/con20/li_*) 一次算出 6 桶結論，傳給各 section_header。
        # financials/ai 為 on-demand → 回 gray「展開後評定」(§1 不偽造)。
        _sec_lv = compute_stock_section_levels(
            health=health2,
            rs_val=_xsec.get('rs_val'),
            chips_sig=_xsec.get('sig20'),
            chips_con=_xsec.get('con20'),
            li_green=_xsec.get('li_green'),
            li_yellow=_xsec.get('li_yellow'),
            li_red=_xsec.get('li_red'),
        )

        # v18.197 ══ 📊 資料新鮮度條（截止日 + 抓取時間 + age + fallback 警示 + 強制重抓）══
        # v18.328 bugfix：K 線截止日改用 sidebar_health.kline_end_date() 共用 canonical。
        # 個股 price df 為 reset_index(drop=True)（RangeIndex，日期在 'date' 欄），
        # 原 pd.to_datetime(df2.index[-1]) 把整數 index 當 epoch 納秒 → 假 1970-01-01（§1）。
        _fetched_at = t2d.get('fetched_at')
        _fresh_cols = st.columns([5, 1])
        with _fresh_cols[0]:
            if _fetched_at is not None:
                _age_min = (pd.Timestamp.now() - _fetched_at).total_seconds() / 60
                _age_color = TRAFFIC_GREEN if _age_min < 60 else (TRAFFIC_YELLOW if _age_min < 240 else TRAFFIC_RED)
                _age_label = (f'{int(_age_min)} 分鐘前' if _age_min < 60
                              else f'{_age_min/60:.1f} 小時前')
                _end_str = kline_end_date(df2) or '—'
                _attrs = (df2.attrs or {}) if (df2 is not None and hasattr(df2, 'attrs')) else {}
                _ps = str(_attrs.get('price_src', 'unknown'))
                _is = str(_attrs.get('inst_src', 'unknown'))
                _ms = str(_attrs.get('margin_src', 'unknown'))
                _PRICE_LABEL = {
                    'yahoo_adj': '🟢 Yahoo還原', 'finmind_sdk': '🟠 FinMind原始(降級)',
                    'finmind_raw': '🟠 FinMind HTTP(降級)', 'yahoo_fallback': '🟠 Yahoo備援(降級)',
                    'unknown': '⬜ 未知',
                }
                _INST_LABEL = {
                    'finmind_sdk': '🟢 FinMind', 'finmind_raw': '🟠 FinMind HTTP(降級)',
                    'twse': '🟠 TWSE降級', 'tpex': '🟠 TPEX降級',
                    'missing': '🔴 缺失', 'unknown': '⬜ 未知',
                }
                _MARGIN_LABEL = {
                    'finmind_sdk': '🟢 FinMind', 'finmind_raw': '🟠 FinMind HTTP(降級)',
                    'missing': '🔴 缺失', 'unknown': '⬜ 未知',
                }
                # v18.201 D2：FinMind 後台 update + 抓取時間 hover tooltip
                def _fm_tooltip(_key: str, _label: str) -> str:
                    _lu = str(_attrs.get(f'{_key}_last_update', '') or '').strip()
                    _fa = str(_attrs.get(f'{_key}_fetched_at', '') or '').strip()
                    _parts = [_label.upper()]
                    if _lu:
                        _parts.append(f'後台 update {_lu}')
                    if _fa:
                        _parts.append(f'抓取於 {_fa}')
                    if len(_parts) == 1:
                        return ''
                    return ' ｜ '.join(_parts)
                _tip_p = _fm_tooltip('price', 'K 線')
                _tip_i = _fm_tooltip('inst', '籌碼')
                _tip_m = _fm_tooltip('margin', '融資')
                _ps_html = (f'<b style="color:#c9d1d9;" title="{_tip_p}">{_PRICE_LABEL.get(_ps, _ps)}</b>'
                            if _tip_p else f'<b style="color:#c9d1d9;">{_PRICE_LABEL.get(_ps, _ps)}</b>')
                _is_html = (f'<b style="color:#c9d1d9;" title="{_tip_i}">{_INST_LABEL.get(_is, _is)}</b>'
                            if _tip_i else f'<b style="color:#c9d1d9;">{_INST_LABEL.get(_is, _is)}</b>')
                _ms_html = (f'<b style="color:#c9d1d9;" title="{_tip_m}">{_MARGIN_LABEL.get(_ms, _ms)}</b>'
                            if _tip_m else f'<b style="color:#c9d1d9;">{_MARGIN_LABEL.get(_ms, _ms)}</b>')

                # v18.202 E2：財報三段資料源 chip（月營收 / 季財報 / 季財報-extra）
                # rev2 / qtr2 / qtr_extra2 的 .attrs 由 data_loader 寫入，過 @st.cache_data
                # pickle 保留（app.py wrapper 未轉換 df）。None/empty → missing。
                def _fin_attrs(_df, _key):
                    _a = (_df.attrs or {}) if (_df is not None and hasattr(_df, 'attrs')) else {}
                    _src = str(_a.get(f'{_key}_src', '') or '')
                    if (_df is None) or (hasattr(_df, 'empty') and _df.empty):
                        _src = 'missing'
                    elif not _src:
                        _src = 'unknown'
                    return _src, str(_a.get(f'{_key}_fetched_at', '') or '')
                _rev_src, _rev_fa = _fin_attrs(rev2, 'rev')
                _qtr_src, _qtr_fa = _fin_attrs(qtr2, 'qtr')
                _qe_src, _qe_fa = _fin_attrs(qtr_extra2, 'qtr_extra')
                _REVENUE_LABEL = {
                    'finmind': '🟢 FinMind', 'mops': '🟠 MOPS(備援)',
                    'missing': '🔴 缺失', 'unknown': '⬜ 未知',
                }
                _QTR_LABEL = {
                    'finmind_rest': '🟢 FinMind', 'finmind_sdk': '🟠 FinMind SDK(備援)',
                    'yfinance': '🟠 yfinance(備援)', 'missing': '🔴 缺失', 'unknown': '⬜ 未知',
                }
                _QTR_EXTRA_LABEL = {
                    'finmind': '🟢 FinMind', 'finmind_mops': '🟠 FinMind+MOPS補',
                    'missing': '🔴 缺失', 'unknown': '⬜ 未知',
                }
                def _fin_chip(_src, _fa, _label_map, _label):
                    _parts = [_label.upper()]
                    if _src and _src not in ('unknown', 'missing'):
                        _parts.append(f'源 {_src}')
                    if _fa:
                        _parts.append(f'抓取於 {_fa}')
                    _tip = ' ｜ '.join(_parts) if len(_parts) > 1 else ''
                    _txt = _label_map.get(_src, _src)
                    if _tip:
                        return f'<b style="color:#c9d1d9;" title="{_tip}">{_txt}</b>'
                    return f'<b style="color:#c9d1d9;">{_txt}</b>'
                _rev_html = _fin_chip(_rev_src, _rev_fa, _REVENUE_LABEL, '月營收')
                _qtr_html = _fin_chip(_qtr_src, _qtr_fa, _QTR_LABEL, '季財報')
                _qe_html = _fin_chip(_qe_src, _qe_fa, _QTR_EXTRA_LABEL, '季財報extra')
                st.markdown(
                    f'<div style="background:#0d1117;border-left:4px solid {_age_color};'
                    f'border-radius:4px;padding:6px 12px;margin-bottom:6px;font-size:11px;color:#8b949e;">'
                    f'📊 <b>資料新鮮度</b>　'
                    f'📅 K線截止：<b style="color:#c9d1d9;">{_end_str}</b>　'
                    f'🕐 抓取：<b style="color:#c9d1d9;">{_fetched_at.strftime("%H:%M:%S")}</b>　'
                    f'⏱️ <span style="color:{_age_color};font-weight:700;">{_age_label}</span>　'
                    f'📡 K線：{_ps_html}　'
                    f'🏦 籌碼：{_is_html}　'
                    f'💰 融資：{_ms_html}'
                    f'<br/>'
                    f'📈 月營收：{_rev_html}　'
                    f'📊 季財報：{_qtr_html}　'
                    f'📑 季財報extra：{_qe_html}'
                    f'</div>', unsafe_allow_html=True)
                _degraded = (
                    _ps in ('finmind_sdk', 'finmind_raw', 'yahoo_fallback')
                    or _is in ('finmind_raw', 'twse', 'tpex', 'missing')
                    or _ms in ('finmind_raw', 'missing')
                )
                # v18.202 E2：財報三段降級也納入警示
                _fin_degraded = (
                    _rev_src in ('mops', 'missing')
                    or _qtr_src in ('finmind_sdk', 'yfinance', 'missing')
                    or _qe_src in ('finmind_mops', 'missing')
                )
                if _degraded:
                    st.caption(
                        '🟠 主資料來源失敗已降級，技術指標 / 籌碼 / 融資數值可能與正常情況不同；'
                        '建議按右側 🔄 強制重抓 重試主源。'
                    )
                if _fin_degraded:
                    st.caption(
                        '🟠 財報資料（月營收 / 季財報）部分走備援源或缺失，EPS / 營收 / 合約負債 '
                        '數值可能與主源略有差異；hover chip 看資料源與抓取時間。'
                    )
        with _fresh_cols[1]:
            if st.button('🔄 強制重抓', key='t2_force_refresh',
                         help='清除所有 @st.cache_data 快取 + 清 session 殘留值，保證下次載入抓最新資料'):
                try:
                    st.cache_data.clear()
                except Exception:
                    pass
                for _k_pop in ('t2_data',
                               f'_exit_news_titles_{sid2}',
                               f'_last_rev_{sid2}',
                               f'_last_qtr_{sid2}'):
                    st.session_state.pop(_k_pop, None)
                st.rerun()
        if _rev2_cached or _qtr2_cached:
            _stale_parts = []
            if _rev2_cached:
                _stale_parts.append('月營收')
            if _qtr2_cached:
                _stale_parts.append('季財報')
            st.markdown(
                f'<div style="background:#3a2814;border-left:4px solid {TRAFFIC_YELLOW};'
                f'border-radius:4px;padding:8px 12px;margin-bottom:8px;font-size:12px;color:#ffd33d;">'
                f'⚠️ <b>{"／".join(_stale_parts)} 本次抓取失敗，目前顯示上次成功的舊值</b>'
                f'　— 按右上「🔄 強制重抓」可重試'
                f'</div>', unsafe_allow_html=True)

        # ── v18.204 I4：個股 ↔ 總經 regime 聯動（讀總經 Tab mkt_info，跨 Tab 訊號）──
        try:
            from src.ui.tabs import render_macro_stock_backdrop
            render_macro_stock_backdrop(st.session_state)
        except Exception as _e_msl:
            print(f'[macro_stock_link] {type(_e_msl).__name__}: {_e_msl}')

        # ── v18.207 I5：個股 ↔ ETF 投組 / 組合比較 跨 Tab 持倉聯動 banner ──
        try:
            from src.ui.tabs import render_stock_portfolio_membership
            render_stock_portfolio_membership(st.session_state, sid2, name2)
        except Exception as _e_pfl:
            print(f'[portfolio_linkage] {type(_e_pfl).__name__}: {_e_pfl}')

        # ══ 即時價格 + 趨勢儀表板 ════════════════════════════════
        if df2 is not None and not df2.empty and len(df2) >= 20:
            _p_now   = float(df2['close'].iloc[-1])
            _p_prev  = float(df2['close'].iloc[-2]) if len(df2) >= 2 else _p_now
            _p_chg   = round((_p_now - _p_prev) / _p_prev * 100, 2) if _p_prev else 0
            # R-CALC-2 v18.412:scalar MA inline → safe_ma SSOT(已 import 自 tab_helpers)
            _ma20_v  = safe_ma(df2, 20)
            _ma60_v  = safe_ma(df2, 60)  if len(df2) >= 60  else None
            _ma120_v = safe_ma(df2, 120) if len(df2) >= 120 else None
            # 趨勢燈號
            _above_ma20  = _p_now > _ma20_v
            _above_ma60  = (_p_now > _ma60_v) if _ma60_v else None
            _above_ma120 = (_p_now > _ma120_v) if _ma120_v else None
            _trend_score = sum([_above_ma20,
                                _above_ma60  if _above_ma60  is not None else False,
                                _above_ma120 if _above_ma120 is not None else False])
            _trend_label = {3: '🟢 強勢多頭', 2: '🟡 中性偏多', 1: '🟡 弱勢', 0: '🔴 空頭區間'}[_trend_score]
            _chg_color   = TRAFFIC_GREEN if _p_chg >= 0 else TRAFFIC_RED
            _chg_arrow   = '▲' if _p_chg >= 0 else '▼'
            st.markdown(f'''<div style="background:#0d1117;border:2px solid #21262d;border-radius:12px;
padding:14px 18px;margin-bottom:12px;">
<div style="font-size:22px;font-weight:900;color:#e6edf3;margin-bottom:8px;">
  📌 {name2}（{sid2}）
  <span style="font-size:14px;color:#8b949e;margin-left:8px;">即時趨勢總覽</span>
</div>
<div style="display:flex;gap:24px;flex-wrap:wrap;align-items:center;">
  <div><span style="font-size:28px;font-weight:900;color:#e6edf3;">{_p_now:.2f}</span>
       <span style="font-size:16px;color:{_chg_color};margin-left:6px;">{_chg_arrow} {abs(_p_chg):.2f}%</span></div>
  <div style="font-size:13px;color:#8b949e;line-height:2;">
    MA20：<b style="color:{TRAFFIC_GREEN if _above_ma20 else TRAFFIC_RED}">{_ma20_v:.2f}</b>
    {'✅' if _above_ma20 else '❌'}&nbsp;&nbsp;
    {'MA60：<b style="color:' + (TRAFFIC_GREEN if _above_ma60 else TRAFFIC_RED) + '">' + f'{_ma60_v:.2f}</b> ' + ("✅" if _above_ma60 else "❌") + "&nbsp;&nbsp;" if _ma60_v else ""}
    {'MA120：<b style="color:' + (TRAFFIC_GREEN if _above_ma120 else TRAFFIC_RED) + '">' + f'{_ma120_v:.2f}</b> ' + ("✅" if _above_ma120 else "❌") if _ma120_v else ""}
  </div>
  <div style="font-size:18px;font-weight:700;">{_trend_label}</div>
</div></div>''', unsafe_allow_html=True)

        # v18.307 Bug2 PR-C：頂部目錄（一眼看全貌 + 錨點跳轉）
        st.markdown(render_stock_toc_html(), unsafe_allow_html=True)
        # v18.307 Bug2 PR-C：section header 改走 shared/stock_buckets SSOT（DRY）
        st.markdown(section_header_html("entry", **_sec_lv["entry"]), unsafe_allow_html=True)
        # ══ 0. 停利停損 + 支撐壓力 ═══════════════════════════════
        st.markdown('---')
        st.markdown('#### 🎯 停利停損建議 + 近期支撐壓力')
        _sp_c1, _sp_c2, _sp_c3, _sp_c4 = st.columns(4)
        _cur_p  = float(df2['close'].iloc[-1]) if df2 is not None and not df2.empty else 0
        # S5 v19.78(第二份 review):門檻 len>=5 但標籤固定寫「近20日」— 5≤len<20 時
        # tail(20) 只涵蓋實際根數,壓力/支撐被高估卻標 20 日 → 標籤改動態視窗天數。
        _win20_n = min(len(df2), 20) if df2 is not None else 0
        _hi20_p = float(df2['high'].tail(20).max()) if df2 is not None and len(df2) >= 5 else 0
        _lo20_p = float(df2['low'].tail(20).min())  if df2 is not None and len(df2) >= 5 else 0
        # v18.336 PR-H4:停利停損改走 compute_stop_levels SSOT(tab_helpers)
        _stop = compute_stop_levels(_cur_p) or {
            'stop_profit_t1': 0.0, 'stop_profit_t2': 0.0, 'stop_loss_default': 0.0,
            't1_pct': STOP_PROFIT_T1_PCT, 't2_pct': STOP_PROFIT_T2_PCT,
            'loss_pct': STOP_LOSS_DEFAULT_PCT,
        }
        _tp1_p = round(_stop['stop_profit_t1'], 2)
        _tp2_p = round(_stop['stop_profit_t2'], 2)
        _sl_p  = round(_stop['stop_loss_default'], 2)
        _rr_p  = round((_tp1_p - _cur_p) / max(_cur_p - _sl_p, 0.01), 2) if _cur_p > 0 else 0
        with _sp_c1:
            st.markdown(kpi(f'停利目標1 (+{_stop["t1_pct"]:.0f}%)', f'{_tp1_p}', '短線先入袋', TRAFFIC_GREEN, '#0d2818'), unsafe_allow_html=True)
        with _sp_c2:
            st.markdown(kpi(f'停利目標2 (+{_stop["t2_pct"]:.0f}%)', f'{_tp2_p}', '波段目標', '#58a6ff', '#0d1f3c'), unsafe_allow_html=True)
        with _sp_c3:
            st.markdown(kpi(f'建議停損 (-{_stop["loss_pct"]:.0f}%)', f'{_sl_p}', '跌破認賠', TRAFFIC_RED, '#2a0d0d'), unsafe_allow_html=True)
        with _sp_c4:
            st.markdown(kpi('盈虧比', f'{_rr_p}x', '≥1.5 較理想', '#ffd700', '#1a1000'), unsafe_allow_html=True)

        # ── v18.336 PR-H4:📊 操作雷達(4 卡 — 對稱組合 Tab,個股 Tab P1 補齊)
        # 整合「狀態燈 + 月線乖離 + 年線乖離 + 量比」四個即時操作維度。
        st.markdown('#### 📊 操作雷達')
        _rd_c1, _rd_c2, _rd_c3, _rd_c4 = st.columns(4)
        # 變數準備(來自既有計算:health2 / df2)
        _ma20_now  = safe_ma(df2, 20)
        _ma240_now = safe_ma(df2, 240)
        _bias20_pct  = calc_bias_pct(_cur_p, _ma20_now)  if _cur_p > 0 else None
        _bias240_pct = calc_bias_pct(_cur_p, _ma240_now) if _cur_p > 0 else None
        _vol_now_r = (float(df2['volume'].iloc[-1]) / float(df2['volume'].tail(20).mean())
                       if (df2 is not None and 'volume' in df2.columns and len(df2) >= 20
                           and float(df2['volume'].tail(20).mean()) > 0)
                       else None)
        # MA100 (給 trend 4-tier 用,個股 K 線註解亦用)
        _ma100_now = safe_ma(df2, 100)
        _trend_lbl_radar, _tc_radar = classify_trend_4tier(
            _cur_p, _ma20_now, _ma100_now) if _cur_p > 0 else ('⚪無資料', TRAFFIC_YELLOW)
        # 估值結論(從既有 357 殖利率分級;若 avg_div2 / cur_yield 已算則可用,否則 '—')
        _valuation_simple = None
        try:
            _cur_yld = (avg_div2 / _cur_p * 100) if (avg_div2 and _cur_p > 0) else None
            if _cur_yld is not None:
                from shared.thresholds import classify_yield_zone
                _, _yld_code = classify_yield_zone(_cur_yld)
                if _yld_code == 'sell':
                    _valuation_simple = '昂貴'
                elif _yld_code == 'reduce':
                    _valuation_simple = '偏貴'
        except Exception as _e_yld:
            print(f'[tab_stock H4 valuation] {sid2} 殖利率分級失敗:{type(_e_yld).__name__}: {_e_yld}')
        # 卡 1:操作狀態燈(對稱組合 Tab)
        _status_lamp = classify_stock_status_lamp(
            health_score=health2, trend_label=_trend_lbl_radar,
            bias_pct=_bias20_pct, vol_ratio=_vol_now_r,
            valuation_label=_valuation_simple)
        with _rd_c1:
            st.markdown(kpi('狀態燈', _status_lamp, '健康+多頭+量縮+近20MA=🔵',
                            TRAFFIC_GREEN if '🔵' in _status_lamp else
                            (TRAFFIC_YELLOW if '🟡' in _status_lamp else
                             (TRAFFIC_RED if '🟠' in _status_lamp else '#666')),
                            '#0d1f0d'), unsafe_allow_html=True)
        # 卡 2:月線乖離分層
        _bias20_lbl, _bias20_color = classify_bias_zone(_bias20_pct)
        with _rd_c2:
            st.markdown(kpi('月線乖離(MA20)', _bias20_lbl, '±15% 中度 / ±20% 過熱',
                            _bias20_color, '#0d1818'), unsafe_allow_html=True)
        # 卡 3:年線乖離分層
        _bias240_lbl, _bias240_color = classify_bias_zone(_bias240_pct)
        with _rd_c3:
            st.markdown(kpi('年線乖離(MA240)', _bias240_lbl, '-20% 布局 / +20% 出場',
                            _bias240_color, '#0d1818'), unsafe_allow_html=True)
        # 卡 4:趨勢 4-tier
        with _rd_c4:
            st.markdown(kpi('K 線趨勢', _trend_lbl_radar,
                            '多頭/空頭/多箱/空箱', _tc_radar, '#1a1a0d'),
                        unsafe_allow_html=True)

        # ── v18.337 PR-H5:⚙️ 多因子評分(3 卡 — 對標個股組合 Tab P2 補齊)
        # SQ 獲利品質 / FGMS 前瞻動能 / RS 相對強度 — 三維 0-100 評分
        st.markdown('#### ⚙️ 多因子評分')
        _mf_c1, _mf_c2, _mf_c3 = st.columns(3)
        # 卡 1:SQ 獲利品質(對標個股組合 L431-439)
        _sq_label = '⚪ 無資料'
        _sq_color = '#666'
        try:
            from src.compute.scoring import calc_quality_score as _cqs2
            _sq_r2 = _cqs2(qtr2)
            if _sq_r2 and _sq_r2.get('sq') is not None:
                _sq_v2 = _sq_r2['sq']
                _sq_lbl2 = _sq_r2.get('sq_label', '')
                _sq_label = f"{_sq_v2:.0f}({_sq_lbl2})"
                # SQ_GOOD_MIN=75 / SQ_STABLE_MIN=55(shared.signal_thresholds)
                from shared.signal_thresholds import SQ_GOOD_MIN, SQ_STABLE_MIN
                _sq_color = (TRAFFIC_GREEN if _sq_v2 >= SQ_GOOD_MIN
                             else (TRAFFIC_YELLOW if _sq_v2 >= SQ_STABLE_MIN else TRAFFIC_RED))
        except Exception as _e_sq:
            print(f'[tab_stock H5 SQ] {sid2} {type(_e_sq).__name__}: {_e_sq}')
        with _mf_c1:
            st.markdown(kpi('SQ 獲利品質', _sq_label, '75 優 / 55 中 / <55 弱',
                            _sq_color, '#0d1f0d'), unsafe_allow_html=True)
        # 卡 2:FGMS 前瞻動能(對標個股組合 L440-454)
        _fgms_label = '⚪ 無資料'
        _fgms_color = '#666'
        try:
            from src.compute.scoring import calc_forward_momentum_score as _cfgms2
            _is_fin2 = bool(qtr2['是否金融股'].iloc[0]) if (qtr2 is not None and '是否金融股' in qtr2.columns) else False
            _fg_r2 = _cfgms2(qtr2, qtr_extra2, is_finance=_is_fin2)
            if _fg_r2 and _fg_r2.get('fgms') is not None:
                _fgms_v2 = _fg_r2['fgms']
                _fgms_lbl2 = _fg_r2.get('fgms_label', '')
                _fgms_label = f"{_fgms_v2:.0f}({_fgms_lbl2})"
                # FGMS_LABEL_T1=75 / T2=60 / T3=45(shared.signal_thresholds)
                from shared.signal_thresholds import (
                    FGMS_LABEL_T1, FGMS_LABEL_T2,
                )
                _fgms_color = (TRAFFIC_GREEN if _fgms_v2 >= FGMS_LABEL_T1
                               else (TRAFFIC_YELLOW if _fgms_v2 >= FGMS_LABEL_T2 else TRAFFIC_RED))
        except Exception as _e_fg:
            print(f'[tab_stock H5 FGMS] {sid2} {type(_e_fg).__name__}: {_e_fg}')
        with _mf_c2:
            st.markdown(kpi('FGMS 前瞻動能', _fgms_label, 'T1≥75 / T2≥60 / T3≥45',
                            _fgms_color, '#0d1818'), unsafe_allow_html=True)
        # 卡 3:RS 相對強度(classify_rs_zone SSOT)
        _rs_v_card = _xsec.get('rs_val') if isinstance(locals().get('_xsec'), dict) else None
        _rs_slope_card = None
        try:
            from src.compute.scoring import rs_slope as _rsslope_h5
            if _rs_v_card is None:
                from src.compute.scoring import calc_rs_score as _crs_h5
                _rs_v_card = _crs_h5(df2)
            _rs_slope_card = _rsslope_h5(df2)
        except Exception as _e_rs:
            print(f'[tab_stock H5 RS] {sid2} {type(_e_rs).__name__}: {_e_rs}')
        _rs_lbl_card, _rs_color_card = classify_rs_zone(_rs_v_card, _rs_slope_card)
        with _mf_c3:
            st.markdown(kpi('RS 相對強度', _rs_lbl_card, '≥75 強 / 50-75 中 / <50 弱',
                            _rs_color_card, '#1a1a0d'), unsafe_allow_html=True)

        _sp_c5, _sp_c6 = st.columns(2)
        _dist_hi = round((_hi20_p/_cur_p-1)*100, 1) if _cur_p > 0 else 0
        _dist_lo = round((1-_lo20_p/_cur_p)*100, 1) if _cur_p > 0 else 0
        # ── 大量紅K 進場價計算 ──────────────────────────────
        _entry_half = None
        _abs_sl     = None
        if df2 is not None and not df2.empty and len(df2) >= 5:
            # 找近20日最大量的紅K
            _red_k = df2[(df2['close'] > df2['open']) if 'open' in df2.columns
                         else df2['close'] > df2['close'].shift(1)].tail(20)
            if 'volume' in _red_k.columns and not _red_k.empty:
                # S4 v19.78:volume 全 NaN 時 — 舊版 pandas nlargest 剔 NaN 回空 df
                # → .iloc[0] IndexError;pandas 3.x 則回含 NaN 的任意列 → 靜默選錯
                # 紅K(進場價/停損算在錯的 bar 上)。先濾 NaN 再取,兩版行為統一:
                # 全 NaN → 空 → 維持 _entry_half=None 走「計算中」格,不造假。
                _top_red = _red_k[_red_k['volume'].notna()].nlargest(1, 'volume')
                if not _top_red.empty:
                    _big_red = _top_red.iloc[0]
                    _rk_high = float(_big_red.get('high', _big_red['close']))
                    _rk_low  = float(_big_red.get('low',  _big_red['close']) )
                    _entry_half = round((_rk_high + _rk_low) / 2, 2)  # 1/2 進場價
                    _abs_sl     = round(_rk_low * 0.995, 2)             # 紅K低點-0.5%

        _sp_c5b, _sp_c6b, _sp_c7b = st.columns(3)
        with _sp_c5b:
            if _entry_half:
                st.markdown(kpi('大量紅K 1/2 進場', f'{_entry_half:.2f}',
                                '朱家泓低風險買點', '#58a6ff', '#1a2744'), unsafe_allow_html=True)
            else:
                st.markdown(kpi('大量紅K 1/2', '計算中', '', '#484f58', '#0d1117'), unsafe_allow_html=True)
        with _sp_c6b:
            if _abs_sl:
                _bias_sl = round((_cur_p - _abs_sl) / _cur_p * 100, 1) if _cur_p else 0
                _sl_color = TRAFFIC_RED if _bias_sl < 5 else TRAFFIC_YELLOW
                st.markdown(kpi('絕對停損線', f'{_abs_sl:.2f}',
                                f'紅K低點（距{_bias_sl:.1f}%）', _sl_color, '#2a0d0d'), unsafe_allow_html=True)
            else:
                st.markdown(kpi('絕對停損線', _sl_p.__str__(), '跌破即出場', TRAFFIC_RED, '#2a0d0d'), unsafe_allow_html=True)
        with _sp_c7b:
            _rr2 = round((_tp1_p - _cur_p) / max(_cur_p - (_abs_sl or _sl_p), 0.01), 2) if _cur_p else 0
            _rr_color = TRAFFIC_GREEN if _rr2 >= 1.5 else (TRAFFIC_YELLOW if _rr2 >= 1 else TRAFFIC_RED)
            st.markdown(kpi('實際盈虧比', f'{_rr2}x', '≥1.5 可操作', _rr_color, '#0d1117'), unsafe_allow_html=True)

        with _sp_c5:
            st.markdown(kpi(f'近{_win20_n}日壓力', f'{_hi20_p:.2f}', f'距現價 +{_dist_hi}%', TRAFFIC_RED, '#2a0d0d'), unsafe_allow_html=True)
        with _sp_c6:
            st.markdown(kpi(f'近{_win20_n}日支撐', f'{_lo20_p:.2f}', f'距現價 -{_dist_lo}%', TRAFFIC_GREEN, '#0d2818'), unsafe_allow_html=True)

        # ══ 進出場訊號（多位老師方法整合）═══════════════════════
        st.markdown('---')

        # ══ 心理檢查 + 勝利方程式 + 禁止操作(U4 Phase 2-Psy v18.406:抽至 stock_sections.section_psy_checklist)══
        # v18.452:原 `_atr2_val if '_atr2_val' in dir() else None` 是抽出時的殘留防呆 —
        # `_atr2_val` 在本函式從未被賦值,`dir()` 恆為 False,等效恆為 None,改直寫消除
        # undefined-name 假訊號(見 tests/test_no_undefined_names.py)。render_psy_checklist_section
        # 對 None 已有文件化 fallback(用價格 × 7% 估算停損距離),行為不變。
        from src.ui.tabs.stock_sections import render_psy_checklist_section
        render_psy_checklist_section(
            sid2, df2, health2,
            _atr2_val=None,
        )

        # ══ 什麼時候買?什麼時候賣?(U4 Phase 3-WBS v18.410:抽至 stock_sections.section_when_buy_sell)══
        from src.ui.tabs.stock_sections import render_when_buy_sell_section
        render_when_buy_sell_section(
            sid2, name2, df2, bb2, k2, d2, rsi2, vcp2,
            _tp1_p, _tp2_p, _hi20_p, _lo20_p, _sl_p,
            gemini_call,
        )
        # ══ 龍頭預警區(U4 Phase 3-Dragon v18.411:抽至 stock_sections.section_dragon_alert)══
        from src.ui.tabs.stock_sections import render_dragon_alert_section
        render_dragon_alert_section(cl2, cx2, _xsec.get("capital", 0), capex=_capex2)  # v18.457 Task#20

        st.markdown(section_header_html("tech", **_sec_lv["tech"]), unsafe_allow_html=True)  # v18.307 Bug2 PR-C SSOT
        # ══ A. 健康度評分(U4 Phase 3-A v18.407:抽至 stock_sections.section_health_score)══
        from src.ui.tabs.stock_sections import render_health_score_section
        render_health_score_section(
            sid2, health2, details2, df2, price2, qtr2, yearly2, avg_div2,
            rsi2, vr2, ibs2, k2, d2, bb2, vcp2, cl2,
            bb_breakout2=bb_breakout2,
        )

        # ══ E. VCP+布林(U4 Phase 3-E v18.409:抽至 stock_sections.section_vcp_bollinger)══
        from src.ui.tabs.stock_sections import render_vcp_bollinger_section
        render_vcp_bollinger_section(sid2, vcp2, bb2)

        # ══ 籌碼定位 20 日(U4 Phase 3-Chips20D v18.411:抽至 stock_sections.section_chips_20d)══
        from src.ui.tabs.stock_sections import render_chips_20d_section
        render_chips_20d_section(df2, _sec_lv["chips"])

        # ══ F. K線技術圖(U4 Phase 3-F v18.409:抽至 stock_sections.section_kline_chart)══
        from src.ui.tabs.stock_sections import render_kline_chart_section
        render_kline_chart_section(
            sid2, name2, df2, price2, health2, rsi2,
            show_ma_dict, t2_adjusted, t2d,
        )

        # ══ G. AI 五維報告 ══════════════════════════════════════
        st.markdown('---')

        # ── 即時文字建議(U4 Phase 2-OpRec v18.406:抽至 stock_sections.section_op_recommendation)──
        from src.ui.tabs.stock_sections import render_op_recommendation_section
        render_op_recommendation_section(sid2, health2, vcp2, avg_div2, price2,
                                          rsi2, cl2, cx2)

        # v18.307 Bug2 PR-C SSOT（color_override 傳實際 TRAFFIC_GREEN 常數，防色票漂移）
        st.markdown(section_header_html("fundamental", color_override=TRAFFIC_GREEN, **_sec_lv["fundamental"]), unsafe_allow_html=True)
        # ══ B. 357 殖利率 + 3 河流圖(U4 Phase 3-B v18.407:抽至 stock_sections.section_357_valuation)══
        from src.ui.tabs.stock_sections import render_357_valuation_section
        render_357_valuation_section(sid2, name2, df2, price2,
                                      qtr2, yearly2, avg_div2, cl2, t2d)

        # ══ C. 領先指標 ════════════════════════════════════════
        # ══ C. 財報領先指標(U4 Phase 2-C v18.406:抽至 stock_sections.section_financial_leading)══
        from src.ui.tabs.stock_sections import render_financial_leading_section
        render_financial_leading_section(sid2, cl2, cx2,
                                          _cl_src2=_cl_src2, _cx_src2=_cx_src2,
                                          _fin_errs2=_fin_errs2,
                                          capex=_capex2)  # v18.458: CF 季資本支出(流量)

        # ══ D. 月營收 + 季毛利率(U4 Phase 2-D v18.406:抽至 stock_sections.section_revenue)══
        from src.ui.tabs.stock_sections import render_revenue_trend_section
        render_revenue_trend_section(sid2, name2, rev2, qtr2,
                                      _rev2_cached=_rev2_cached,
                                      _qtr2_cached=_qtr2_cached)
        # ══ 策略 1 結論 + MJ 趨勢分數(U4 Phase 3-S1 v18.408:抽至 stock_sections.section_strategy_conclusion)══
        from src.ui.tabs.stock_sections import render_strategy_conclusion_section
        render_strategy_conclusion_section(
            sid2, rev2, qtr2, qtr_extra2, FINMIND_TOKEN,
            fetch_financial_statements, analyze_financial_health,
        )
        # ══ D2. 基本面先行(U4 Phase 3-D2 v18.408:抽至 stock_sections.section_d2_leading)══
        from src.ui.tabs.stock_sections import render_d2_leading_section
        render_d2_leading_section(rev2, qtr2, qtr_extra2)

        # ── 資料彙整（供 AI 總結使用）──────────────────────────
        _regime2 = st.session_state.get('mkt_info', {}).get('regime', 'neutral')
        _rev_yoy_list = []
        if rev2 is not None and not rev2.empty and 'yoy' in rev2.columns:
            # P4b: vectorized — 對齊 date/index 後一次 apply
            _r3 = rev2.tail(3).copy()
            _r3['_lbl'] = _r3['date'].astype(str) if 'date' in _r3.columns else _r3.index.astype(str)
            _rev_yoy_list = [
                f'{lbl}: {yoy:+.1f}%'
                for lbl, yoy in zip(_r3['_lbl'], pd.to_numeric(_r3['yoy'], errors='coerce'))
                if not pd.isna(yoy)
            ]
        _vcp_ok2 = bool(vcp2 and isinstance(vcp2, dict) and vcp2.get('signal'))
        _ma_above2 = {}
        if df2 is not None and not df2.empty:
            for _mn, _mc in [('20MA', 'MA20'), ('60MA', 'MA60'), ('240MA', 'MA240')]:
                if _mc in df2.columns:
                    _ma_above2[_mn] = price2 > float(df2[_mc].iloc[-1])

        st.markdown(section_header_html("financials", **_sec_lv["financials"]), unsafe_allow_html=True)  # v18.307 Bug2 PR-C SSOT

        # ── 🔰 故事化白話：財報名詞快查（純疊加；放在體檢 expander 外，避免巢狀）──
        with st.expander('🔰 看懂下面這些財報名詞（新手必看，30 秒）'):
            st.markdown('''下面「AI 財報體檢」用的是 MJ（林明樟）財報分析框架，名詞白話對照：

| 名詞 | 白話意思 |
|---|---|
| **氣長不長**（現金 > 總資產 25%） | 公司手上現金夠不夠多；現金多＝氣長、撐得久、不怕周轉不靈 |
| **真假獲利 / OCF**（營業現金流為正） | 帳上賺錢有沒有真的收到現金；OCF 為正才是真賺，帳面賺卻沒收到現金＝**黑字破產**風險 |
| **那根棒子**（負債比 < 60%） | 公司欠錢的比例；越低越穩，>60% 代表槓桿偏高 |
| **周轉效率** | 賣貨、收帳的速度；越快＝資金越活、不卡庫存與呆帳 |
| **以長支長** | 用「長期的錢」（股本＋長期借款）買「長期資產」（廠房設備）；比率夠才不會短債養長投、周轉爆掉 |
| **MJ 300 / 150** | MJ 的嚴格標準：流動比率 >300%、速動比率 >150%＝短期還債餘裕大（收現行業或現金充足者會放寬門檻＝「保命符」） |
| **跨表勾稽 + 地雷** | 把損益表／資產負債表／現金流量表三張表交叉對驗，揪出兜不攏的造假或地雷訊號 |

> 💡 燈號：🟢 安全、🟡 注意、🔴 危險。任一生死指標亮紅燈，務必深究原因再決定要不要碰。''')

        with st.expander('🔬 AI 財報體檢（策略2）', expanded=True):
            _fh_key2 = f'_fh_{sid2}'
            if _fh_key2 not in st.session_state:
                with st.spinner('📊 正在從 FinMind 抓取財報數據…'):
                    try:
                        _fin_raw = fetch_financial_statements(sid2, FINMIND_TOKEN)
                        if _fin_raw.get('error'):
                            st.session_state[_fh_key2] = {'error': True, 'ai_insight': _fin_raw['error']}
                        else:
                            # B項：預填 5 年現金流量允當比率（精確版）
                            try:
                                from src.data.stock import fetch_5_years_cash_flow
                                _fin_raw['b_item_5y'] = fetch_5_years_cash_flow(sid2, FINMIND_TOKEN)
                            except Exception:
                                pass  # fallback 到 1Q 估算
                            # 近期新聞：供 MJ 體檢 AI insight 結合市場情緒
                            _mj_news = _fetch_stock_news(sid2, name2, 3)
                            _mj_news_str = '\n'.join(
                                f'- {_n["title"]}（{_n.get("source","RSS")} · {_n.get("published","")}）'
                                for _n in _mj_news
                            ) if _mj_news else '（暫無近期個股新聞）'
                            _fh_out = analyze_financial_health(api_key, sid2, _fin_raw,
                                                               news_context=_mj_news_str)
                            st.session_state[_fh_key2] = _fh_out
                            # 保存原始財報數據供診斷面板使用（ar_days/liab/b_item_5y 等）
                            st.session_state[f'_fin_raw_{sid2}'] = _fin_raw
                    except Exception as _fh_exc:
                        st.session_state[_fh_key2] = {'error': True, 'ai_insight': f'財報體檢發生例外：{_fh_exc}'}
            _fh = st.session_state.get(_fh_key2)
            if not _fh or _fh.get('error'):
                st.error(_fh.get('ai_insight', '財報體檢失敗，請確認 FINMIND_TOKEN 已設定。') if _fh else '載入中...')
            else:
                # ── 第一關：三大生死燈號 ────────────────────
                st.markdown('#### 🛡️ 第一關：生死與體質防禦')
                _fh_c1, _fh_c2, _fh_c3 = st.columns(3)
                with _fh_c1:
                    st.metric(
                        label='氣長不長（現金佔總資產 > 25%）',
                        value=f"{_fh.get('cash_ratio_status','?')} {_fh.get('cash_ratio_value','N/A')}",
                        delta='安全' if _fh.get('cash_ratio_status') == '🟢' else
                              '注意' if _fh.get('cash_ratio_status') == '🟡' else '危險',
                        delta_color='normal' if _fh.get('cash_ratio_status') == '🟢' else 'inverse',
                    )
                with _fh_c2:
                    st.metric(
                        label='真假獲利（OCF 必須為正）',
                        value=f"{_fh.get('ocf_status','?')} {_fh.get('ocf_value','N/A')}",
                        delta='穩定流入' if _fh.get('ocf_status') == '🟢' else '黑字破產警戒',
                        delta_color='normal' if _fh.get('ocf_status') == '🟢' else 'inverse',
                    )
                with _fh_c3:
                    st.metric(
                        label='那根棒子（負債比 < 60%）',
                        value=f"{_fh.get('debt_ratio_status','?')} {_fh.get('debt_ratio_value','N/A')}",
                        delta='穩健' if _fh.get('debt_ratio_status') == '🟢' else
                              '留意' if _fh.get('debt_ratio_status') == '🟡' else '危險',
                        delta_color='normal' if _fh.get('debt_ratio_status') == '🟢' else 'inverse',
                    )

                st.markdown('<hr style="border-color:#21262d;margin:10px 0;">', unsafe_allow_html=True)

                # ── 五力雷達圖 + 企業DNA / 護城河 ──────────
                _fh_left, _fh_right = st.columns([1, 1])

                with _fh_left:
                    st.markdown('#### 🎯 五力體質雷達圖')
                    _radar = _fh.get('radar_scores', {})
                    if _radar:
                        import plotly.graph_objects as _go_fh
                        _cats = list(_radar.keys()) + [list(_radar.keys())[0]]
                        _vals = [max(0, min(100, int(v))) for v in _radar.values()]
                        _vals += [_vals[0]]
                        _fig_fh = _go_fh.Figure(_go_fh.Scatterpolar(
                            r=_vals, theta=_cats, fill='toself',
                            line_color=TRAFFIC_GREEN, fillcolor='rgba(63,185,80,0.2)',
                        ))
                        _fig_fh.update_layout(
                            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            margin=dict(l=20, r=20, t=20, b=20),
                            showlegend=False,
                        )
                        st.plotly_chart(_fig_fh, width='stretch')
                    else:
                        st.warning('無法取得五力評分資料')

                with _fh_right:
                    st.markdown('#### 🧬 企業 DNA 與護城河')
                    _dna = _fh.get('business_model_dna', '無法判斷')
                    _dna_clr = (TRAFFIC_GREEN if 'A+' in _dna or _dna.startswith('A ')
                                else TRAFFIC_YELLOW if 'B' in _dna or 'C' in _dna
                                else TRAFFIC_RED)
                    st.markdown(
                        f'<div style="background:#161b22;border-left:4px solid {_dna_clr};'
                        f'border-radius:8px;padding:14px 16px;margin-bottom:10px;">'
                        f'<div style="font-size:11px;color:#484f58;margin-bottom:4px;">現金流矩陣判定</div>'
                        f'<div style="font-size:18px;font-weight:900;color:{_dna_clr};">{_dna}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown('**OPM 商業話語權檢驗**')
                    _opm = _fh.get('opm_data', {})
                    _p_days = _opm.get('payable_days', 0)
                    _r_days = _opm.get('receivable_days', 0)
                    _adv = _opm.get('advantage', False)
                    if _adv:
                        st.success(
                            f'👑 具備快收慢付優勢\n\n'
                            f'應付帳款 **{_p_days}天** > 應收帳款 **{_r_days}天**'
                        )
                    elif _r_days == 0:
                        st.info('DSO (應收帳款天數) 資料缺漏，無法判定 OPM 護城河')
                    else:
                        st.warning(
                            f'⚠️ 營運資金壓力較大\n\n'
                            f'應付帳款 **{_p_days}天** < 應收帳款 **{_r_days}天**'
                        )

                st.markdown('<hr style="border-color:#21262d;margin:10px 0;">', unsafe_allow_html=True)

                # ── 存活能力精細模組（Survival Module）──────────
                _surv2 = _fh.get('survival_module', {})
                if _surv2:
                    st.markdown('#### 🏥 存活能力精細診斷（MJ 3大生死指標）')
                    _sc_map = {'Pass': TRAFFIC_GREEN, 'Acceptable': TRAFFIC_YELLOW, 'Fail': TRAFFIC_RED}
                    _s2c = st.columns(3)
                    for _col2, (_key2, _lbl2) in zip(_s2c, [
                        ('Cash_Ratio', '💰 氣長不長'), ('DSO_Speed', '⚡ 收現速度')
                    ]):
                        _si2 = _surv2.get(_key2, {})
                        _sc2 = _sc_map.get(_si2.get('Status', 'Fail'), TRAFFIC_RED)
                        with _col2:
                            st.markdown(
                                f'<div style="background:{_sc2}18;border:1px solid {_sc2}55;'
                                f'border-radius:8px;padding:10px;text-align:center;">'
                                f'<div style="font-size:11px;color:#8b949e;">{_lbl2}</div>'
                                f'<div style="font-size:20px;font-weight:900;color:{_sc2};">{_si2.get("Value","N/A")}</div>'
                                f'<div style="font-size:11px;color:{_sc2};">{_si2.get("Status","?")}</div>'
                                f'<div style="font-size:10px;color:#8b949e;margin-top:4px;">{_si2.get("Insight","")}</div>'
                                f'</div>', unsafe_allow_html=True)
                    _r1102 = _surv2.get('Rule_100_100_10', {})
                    _r110c2 = _sc_map.get(_r1102.get('Status', 'Fail'), TRAFFIC_RED)
                    # 各分項勾叉（門檻：A>100% / B≥100% / C>10%，與 financial_health_engine:416/423/431 對齊）
                    _a_ok2 = parse_cash_flow_ratio(_r1102.get('Cash_Flow_Ratio',''), 100, strict=True)
                    _b_ok2 = parse_cash_flow_ratio(_r1102.get('Cash_Flow_Adequacy',''), 100, strict=False)
                    _c_ok2 = parse_cash_flow_ratio(_r1102.get('Cash_Reinvestment',''), 10, strict=True)
                    with _s2c[2]:
                        st.markdown(
                            f'<div style="background:{_r110c2}18;border:1px solid {_r110c2}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">🔄 100/100/10</div>'
                            f'<div style="font-size:11px;color:#c9d1d9;">'
                            f'A{format_condition_emoji(_a_ok2)}{_r1102.get("Cash_Flow_Ratio","N/A")} '
                            f'B{format_condition_emoji(_b_ok2)}{_r1102.get("Cash_Flow_Adequacy","N/A")} '
                            f'C{format_condition_emoji(_c_ok2)}{_r1102.get("Cash_Reinvestment","N/A")}</div>'
                            f'<div style="font-size:12px;font-weight:700;color:{_r110c2};">{_r1102.get("Status","?")}</div>'
                            f'<div style="font-size:10px;color:#8b949e;margin-top:4px;">{_r1102.get("Insight","")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    _v2 = _surv2.get('Final_Survival_Verdict', '')
                    if _v2:
                        st.caption(f'🎯 {_v2}')

                # ── 經營能力模組（Operating Module）──────────────
                _oper2 = _fh.get('operating_module', {})
                if _oper2:
                    st.markdown('#### ⚙️ 經營能力診斷（周轉效率 + 資金壓力）')
                    _oc1, _oc2, _oc3, _oc4 = st.columns(4)
                    _ccc_str = str(_oper2.get('Cash_Gap_Days', 'N/A'))
                    try:
                        _ccc_num = float(_ccc_str.split()[0].replace('天', '').strip())
                        _ccc_is_num = True
                    # S3 v19.78:空字串 ''.split() 回 [] → [0] 拋 IndexError,原 except 未涵蓋
                    except (ValueError, AttributeError, IndexError):
                        _ccc_num, _ccc_is_num = 0.0, False
                    # OPM 護城河：引擎判定 Yes 且 CCC 為實質負數，兩者同時成立才顯示
                    _opm_yes = (_oper2.get('OPM_Strategy', 'No') == 'Yes') and _ccc_is_num and (_ccc_num < 0)
                    _ccc_color = TRAFFIC_GREEN if _opm_yes else ('#8b949e' if not _ccc_is_num else TRAFFIC_YELLOW)
                    with _oc1:
                        st.metric('DSO 應收天數', _oper2.get('DSO', 'N/A'))
                    with _oc2:
                        st.metric('DIO 存貨天數', _oper2.get('DIO', 'N/A'))
                    with _oc3:
                        st.metric('DPO 應付天數', _oper2.get('DPO', 'N/A'))
                    with _oc4:
                        st.metric('總資產翻桌率', _oper2.get('Asset_Turnover', 'N/A'))
                    _oc5, _oc6 = st.columns(2)
                    with _oc5:
                        st.markdown(
                            f'<div style="background:#161b22;border-radius:8px;padding:10px;">'
                            f'<div style="font-size:11px;color:#8b949e;">做生意完整週期</div>'
                            f'<div style="font-size:18px;font-weight:900;color:#58a6ff;">{_oper2.get("Complete_Cycle","N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    with _oc6:
                        st.markdown(
                            f'<div style="background:#161b22;border-radius:8px;padding:10px;">'
                            f'<div style="font-size:11px;color:#8b949e;">缺錢天數 (CCC)</div>'
                            f'<div style="font-size:18px;font-weight:900;color:{_ccc_color};">{_oper2.get("Cash_Gap_Days","N/A")}</div>'
                            f'<div style="font-size:11px;color:{_ccc_color};">{"✅ OPM護城河：拿別人的錢做生意" if _opm_yes else ("⚪ CCC 資料不足" if not _ccc_is_num else "⚠️ 需自備營運資金")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _oper2.get('Verdict'):
                        st.caption(f'💡 {_oper2["Verdict"]}')

                # ── 獲利能力模組（Profitability Module）─────────
                _prof2 = _fh.get('profitability_module', {})
                if _prof2:
                    st.markdown('#### 💰 獲利能力診斷（MJ 5大指標）')
                    _p5c = st.columns(5)
                    # 1 毛利率
                    _gm2 = _prof2.get('Gross_Margin', {})
                    _gm2_ok = _gm2.get('Status', '') == 'Good'
                    with _p5c[0]:
                        st.markdown(
                            f'<div style="background:{TRAFFIC_GREEN if _gm2_ok else TRAFFIC_RED}18;'
                            f'border:1px solid {TRAFFIC_GREEN if _gm2_ok else TRAFFIC_RED}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">毛利率</div>'
                            f'<div style="font-size:17px;font-weight:900;color:{TRAFFIC_GREEN if _gm2_ok else TRAFFIC_RED};">{_gm2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{TRAFFIC_GREEN if _gm2_ok else TRAFFIC_RED};">{"好生意" if _gm2_ok else "辛苦生意"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 2 營業利益率
                    _om2 = _prof2.get('Operating_Margin', {})
                    _om2_ok = _om2.get('Core_Business_Profitable', 'No') == 'Yes'
                    with _p5c[1]:
                        st.markdown(
                            f'<div style="background:{TRAFFIC_GREEN if _om2_ok else TRAFFIC_RED}18;'
                            f'border:1px solid {TRAFFIC_GREEN if _om2_ok else TRAFFIC_RED}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">營業利益率</div>'
                            f'<div style="font-size:17px;font-weight:900;color:{TRAFFIC_GREEN if _om2_ok else TRAFFIC_RED};">{_om2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{TRAFFIC_GREEN if _om2_ok else TRAFFIC_RED};">{"本業獲利✅" if _om2_ok else "本業虧損❌"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 3 安全邊際
                    _mos2 = _prof2.get('Margin_Of_Safety', {})
                    _mos2_ok = _mos2.get('Status', '') == 'Strong'
                    with _p5c[2]:
                        st.markdown(
                            f'<div style="background:{TRAFFIC_GREEN if _mos2_ok else TRAFFIC_YELLOW}18;'
                            f'border:1px solid {TRAFFIC_GREEN if _mos2_ok else TRAFFIC_YELLOW}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">安全邊際</div>'
                            f'<div style="font-size:17px;font-weight:900;color:{TRAFFIC_GREEN if _mos2_ok else TRAFFIC_YELLOW};">{_mos2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{TRAFFIC_GREEN if _mos2_ok else TRAFFIC_YELLOW};">{"抗震極強✅" if _mos2_ok else "費用待改善"}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 4 稅後淨利率
                    _nm2 = _prof2.get('Net_Margin', {})
                    _nm2_s = _nm2.get('Status', '')
                    _nm2_c = TRAFFIC_GREEN if _nm2_s == 'Pass' else (TRAFFIC_YELLOW if _nm2_s == 'Thin Profit' else TRAFFIC_RED)
                    with _p5c[3]:
                        st.markdown(
                            f'<div style="background:{_nm2_c}18;border:1px solid {_nm2_c}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">稅後淨利率</div>'
                            f'<div style="font-size:17px;font-weight:900;color:{_nm2_c};">{_nm2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_nm2_c};">{_nm2_s}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 5 ROE
                    _roe2 = _prof2.get('ROE', {})
                    _roe2_warn = _roe2.get('Leverage_Warning', 'None') != 'None'
                    try:
                        _roe2_num = float(_roe2.get('Value', '0').replace('%', '').strip())
                    except (ValueError, AttributeError):
                        _roe2_num = None
                    _roe2_positive = _roe2_num is not None and _roe2_num > 0
                    _roe2_c = TRAFFIC_YELLOW if _roe2_warn else (TRAFFIC_GREEN if _roe2_positive else TRAFFIC_RED)
                    with _p5c[4]:
                        st.markdown(
                            f'<div style="background:{_roe2_c}18;border:1px solid {_roe2_c}55;'
                            f'border-radius:8px;padding:10px;text-align:center;">'
                            f'<div style="font-size:10px;color:#8b949e;">ROE</div>'
                            f'<div style="font-size:17px;font-weight:900;color:{_roe2_c};">{_roe2.get("Value","N/A")}</div>'
                            f'<div style="font-size:10px;color:{_roe2_c};">{"⚠️ 高槓桿驅動" if _roe2_warn else ("✅ 真實獲利" if _roe2_positive else "❌ 本業虧損")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    if _prof2.get('Final_Insight'):
                        st.caption(f'🎯 {_prof2["Final_Insight"]}')

                # ── 財務結構模組（Financial Structure Module）────
                _fstr2 = _fh.get('financial_structure_module', {})
                if _fstr2:
                    st.markdown('#### 🏗️ 財務結構診斷（那根棒子 + 以長支長）')
                    _fs2c = st.columns(2)
                    # 1 負債佔資產比率
                    _dr2 = _fstr2.get('Debt_Ratio', {})
                    _dr2_s = _dr2.get('Status', '')
                    _dr2_c = {'Pass': TRAFFIC_GREEN, 'Warning': TRAFFIC_YELLOW, 'Fail': TRAFFIC_RED, 'N/A': '#8b949e'}.get(_dr2_s, '#8b949e')
                    with _fs2c[0]:
                        st.markdown(
                            f'<div style="background:{_dr2_c}18;border:1px solid {_dr2_c}55;'
                            f'border-radius:10px;padding:14px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">負債佔資產比率</div>'
                            f'<div style="font-size:26px;font-weight:900;color:{_dr2_c};">{_dr2.get("Value","N/A")}</div>'
                            f'<div style="font-size:11px;color:{_dr2_c};">'
                            f'{"✅ 穩健（<60%）" if _dr2_s=="Pass" else ("⚠️ 偏高（60-70%）" if _dr2_s=="Warning" else ("🔴 高危（>70%）" if _dr2_s=="Fail" else ("🏦 特許行業" if "金融" in _dr2.get("Value","") else "⚪ 資料缺漏")))}'
                            f'</div></div>', unsafe_allow_html=True)
                    # 2 以長支長比率
                    _ltf2 = _fstr2.get('Long_Term_Funding_Ratio', {})
                    _ltf2_s = _ltf2.get('Status', '')
                    _ltf2_c = TRAFFIC_GREEN if _ltf2_s == 'Pass' else ('#8b949e' if _ltf2_s == 'N/A' else TRAFFIC_RED)
                    _ltf2_label = ('✅ 資金配置正確（>100%）' if _ltf2_s == 'Pass'
                                   else ('⚪ 資料不足，無法判斷' if _ltf2_s == 'N/A'
                                         else '🔴 短債長投！資金鏈危機'))
                    with _fs2c[1]:
                        st.markdown(
                            f'<div style="background:{_ltf2_c}18;border:1px solid {_ltf2_c}55;'
                            f'border-radius:10px;padding:14px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">以長支長比率</div>'
                            f'<div style="font-size:26px;font-weight:900;color:{_ltf2_c};">{_ltf2.get("Value","N/A")}</div>'
                            f'<div style="font-size:11px;color:{_ltf2_c};">{_ltf2_label}'
                            f'</div></div>', unsafe_allow_html=True)
                    if _fstr2.get('Final_Insight'):
                        st.caption(f'🏗️ {_fstr2["Final_Insight"]}')

                # ── 償債能力模組（Solvency Module）─────────────
                _solv2 = _fh.get('solvency_module', {})
                if _solv2:
                    st.markdown('#### 🛡️ 短期償債能力診斷（MJ 300/150 嚴格標準）')
                    # 最終裁決 banner
                    _sv2_v = _solv2.get('Final_Solvency_Verdict', '')
                    _sv2_pass = 'Pass' in _sv2_v
                    _sv2_exc  = 'Exception' in _sv2_v
                    _sv2_bc   = TRAFFIC_GREEN if _sv2_pass and not _sv2_exc else (TRAFFIC_YELLOW if _sv2_exc else TRAFFIC_RED)
                    _sv2_icon = '✅' if _sv2_pass and not _sv2_exc else ('⚡' if _sv2_exc else '🔴')
                    st.markdown(
                        f'<div style="background:{_sv2_bc}18;border:2px solid {_sv2_bc};'
                        f'border-radius:10px;padding:10px 16px;margin-bottom:10px;">'
                        f'<span style="font-size:14px;font-weight:900;color:{_sv2_bc};">'
                        f'{_sv2_icon} {_sv2_v}</span></div>', unsafe_allow_html=True)
                    # 保命符：依 Final_Solvency_Verdict 區分例外類型
                    _is_dso_exception  = "條件B：天天收現" in _sv2_v
                    _is_cash_exception = "條件A：現金充足" in _sv2_v
                    _is_any_exception  = _is_dso_exception or _is_cash_exception
                    # 流動比率門檻：條件B→150%；條件A→100%；無例外→300%
                    _cr_thresh = 150 if _is_dso_exception else (100 if _is_cash_exception else 300)
                    _cr_label  = (f'流動比率（保命符放寬 >{_cr_thresh}%）'
                                  if _is_any_exception else '流動比率（MJ嚴格 >300%）')
                    _sv2c = st.columns(2)
                    for _col, (_key, _label, _thresh) in zip(_sv2c, [
                        ('Current_Ratio', _cr_label, _cr_thresh),
                        ('Quick_Ratio', '速動比率（MJ嚴格 >150%）', 150),
                    ]):
                        _si = _solv2.get(_key, {})
                        _si_s = _si.get('Status', '')
                        # 保命符啟動時，重新以放寬閾值判定流動比率顏色與標籤
                        if _key == 'Current_Ratio' and _is_any_exception:
                            try:
                                _cr_num = float(_si.get('Value', '0').replace('%', '').strip())
                                if _cr_num > _thresh:
                                    _si_c, _si_s = TRAFFIC_GREEN, f'Pass（保命符 >{_thresh}%）'
                                else:
                                    _si_c = TRAFFIC_RED
                            except (ValueError, AttributeError):
                                _si_c = TRAFFIC_GREEN if 'Pass' in _si_s else TRAFFIC_RED
                        else:
                            _si_c = TRAFFIC_GREEN if 'Pass' in _si_s else TRAFFIC_RED
                        with _col:
                            st.markdown(
                                f'<div style="background:{_si_c}18;border:1px solid {_si_c}55;'
                                f'border-radius:10px;padding:12px;text-align:center;">'
                                f'<div style="font-size:11px;color:#8b949e;">{_label}</div>'
                                f'<div style="font-size:24px;font-weight:900;color:{_si_c};">{_si.get("Value","N/A")}</div>'
                                f'<div style="font-size:11px;color:{_si_c};">{_si_s}</div>'
                                f'</div>', unsafe_allow_html=True)
                    # Banner：依例外類型顯示不同提示
                    if _is_dso_exception:
                        st.info('🔍 已啟動收現行業交叉驗證保命符（DSO ≤ 15天，流動比率門檻放寬至 >150%）')
                    elif _is_cash_exception:
                        st.info('💰 已啟動現金充足交叉驗證保命符（現金佔總資產 >25%，流動比率門檻放寬至 >100%）')
                    if _solv2.get('Final_Insight'):
                        st.caption(f'🛡️ {_solv2["Final_Insight"]}')

                # ── 綜合診斷模組（Advanced Diagnostic Module）────
                _adv2 = _fh.get('advanced_diagnostic_module', {})
                if _adv2:
                    st.markdown('#### 🔬 綜合診斷與避雷（跨表勾稽 + 地雷偵測）')
                    # 第一列：盈餘品質 + 杜邦 + 雙高
                    _ad2r1 = st.columns(3)
                    # 盈餘品質
                    _eq2 = _adv2.get('Earnings_Quality', {})
                    _eq2_s = _eq2.get('Status', '')
                    _eq2_c = TRAFFIC_GREEN if _eq2_s == 'Pass' else (TRAFFIC_RED if _eq2_s == 'Fail' else '#8b949e')
                    with _ad2r1[0]:
                        st.markdown(
                            f'<div style="background:{_eq2_c}18;border:1px solid {_eq2_c}55;'
                            f'border-radius:10px;padding:12px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">盈餘含金量</div>'
                            f'<div style="font-size:22px;font-weight:900;color:{_eq2_c};">{_eq2.get("Value","N/A")}</div>'
                            f'<div style="font-size:11px;color:{_eq2_c};">{"✅ 真金白銀" if _eq2_s=="Pass" else ("🔴 紙上富貴" if _eq2_s=="Fail" else "N/A")}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 杜邦分析
                    _dp2 = _adv2.get('DuPont_Health', '')
                    _dp2_c = TRAFFIC_RED if '警報' in _dp2 else (TRAFFIC_GREEN if '健康' in _dp2 else TRAFFIC_YELLOW)
                    _dp2_icon = '🔴' if '警報' in _dp2 else ('✅' if '健康' in _dp2 else '⚠️')
                    with _ad2r1[1]:
                        st.markdown(
                            f'<div style="background:{_dp2_c}18;border:1px solid {_dp2_c}55;'
                            f'border-radius:10px;padding:12px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">杜邦分析</div>'
                            f'<div style="font-size:13px;font-weight:900;color:{_dp2_c};line-height:1.4;">{_dp2_icon} {_dp2}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 雙高危機
                    _dh2 = _adv2.get('Double_High_Warning', '')
                    _dh2_danger = 'Triggered' in _dh2
                    _dh2_c = TRAFFIC_RED if _dh2_danger else (TRAFFIC_GREEN if 'Clear' in _dh2 else '#8b949e')
                    with _ad2r1[2]:
                        st.markdown(
                            f'<div style="background:{_dh2_c}18;border:1px solid {_dh2_c}55;'
                            f'border-radius:10px;padding:12px;text-align:center;">'
                            f'<div style="font-size:11px;color:#8b949e;">雙高危機偵測</div>'
                            f'<div style="font-size:13px;font-weight:900;color:{_dh2_c};">{"🔴 觸發警報！" if _dh2_danger else ("✅ 安全" if "Clear" in _dh2 else "⬜ 資料不足")}</div>'
                            f'<div style="font-size:10px;color:{_dh2_c};">{_dh2}</div>'
                            f'</div>', unsafe_allow_html=True)
                    # 第二列：企業 DNA 全寬
                    _dna2 = _adv2.get('Business_DNA', '')
                    _dna2_c = TRAFFIC_GREEN if 'A+' in _dna2 else (TRAFFIC_YELLOW if '成長' in _dna2 or '新創' in _dna2 else (TRAFFIC_RED if '瀕死' in _dna2 else '#58a6ff'))
                    st.markdown(
                        f'<div style="background:{_dna2_c}18;border:1px solid {_dna2_c}55;'
                        f'border-radius:10px;padding:10px 16px;margin-top:8px;">'
                        f'<span style="font-size:11px;color:#8b949e;">企業 DNA（現金流矩陣）：</span>'
                        f'<span style="font-size:14px;font-weight:900;color:{_dna2_c};margin-left:8px;">{_dna2}</span>'
                        f'</div>', unsafe_allow_html=True)
                    if _adv2.get('Final_Verdict'):
                        st.caption(f'🔬 {_adv2["Final_Verdict"]}')

                # ── 老師動態總結論 ─────────────────────────────────
                _ov = no_ai_overall_verdict(
                    fin_data=st.session_state.get('t2_fin_data', {}),
                    fh_result=_fh,
                )
                _ovc = _ov.get("grade_color", "#58a6ff")
                st.markdown('<hr style="border-color:#30363d;margin:14px 0 10px;">', unsafe_allow_html=True)
                st.markdown(
                    f'<div style="background:{_ovc}12;border:2px solid {_ovc};border-radius:12px;padding:16px 20px;">'
                    f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:8px;">'
                    f'<span style="font-size:36px;font-weight:900;color:{_ovc};font-family:monospace;">'
                    f'{_ov.get("grade","?")}</span>'
                    f'<div>'
                    f'<div style="font-size:14px;font-weight:900;color:{_ovc};">{_ov.get("headline","")}</div>'
                    f'<div style="font-size:10px;color:#8b949e;margin-top:2px;">'
                    f'策略2 · 6大模組綜合評估 · '
                    f'✅ {_ov.get("pass_count",0)} 項達標　'
                    f'🔴 {_ov.get("fail_count",0)} 項警示　'
                    f'企業DNA：{_ov.get("dna","--")}'
                    f'</div></div></div>'
                    f'<div style="font-size:12px;color:#c9d1d9;line-height:1.7;">{_ov.get("comment","")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ══ 💠 集保籌碼大戶雷達（隨主代碼 sid2 自動查詢；置於 AI 總結上方供其引用）══
        st.markdown('---')
        from src.ui.tabs import render_chip_radar
        _chip_radar_summary = render_chip_radar(sid2)

        # ══ 🤖 AI 首席顧問總結 ═══════════════════════════════════
        st.markdown(section_header_html("ai", **_sec_lv["ai"]), unsafe_allow_html=True)  # v18.307 Bug2 PR-C SSOT

        _ai_sum_key = f'_ai_sum_{sid2}'
        _ai_sum_cached = st.session_state.get(_ai_sum_key, '')

        def _fmt_news_list(_news):
            if not _news:
                return '（暫無相關個股新聞）'
            _ls = []
            for _nn in _news:
                _t = _nn.get('title', '')
                _lk = _nn.get('link', '')
                _src = _nn.get('source', 'RSS')
                _pb = _nn.get('published', '') or '—'
                _head = f'[{_t}]({_lk})' if _lk else _t
                _ls.append(f'- `{_pb}` · {_head}　_{_src}_')
            return '\n'.join(_ls)

        def _show_news_expander(_news, _diag=None):
            _cnt = len(_news) if _news else 0
            with st.expander(f'📰 近期相關新聞（{_cnt} 則 · Google News RSS · 近期為主）', expanded=bool(_news)):
                st.caption('來源：Google News RSS（中英文）。依關聯度與時間排序、以近期報導為主；點標題開原文。')
                if _news:
                    st.markdown(_fmt_news_list(_news))
                else:
                    st.info('本次未取得個股新聞 — 可能 Google News RSS 暫時限流/封鎖（雲端海外 IP）或近期無相關報導；可稍後重試。')
                    if _diag:
                        st.caption('🔬 抓取診斷（proxy/直連 · HTTP · entries · 錯誤）：')
                        st.code('\n'.join(_diag), language='text')

        _ai_sum_c1, _ai_sum_c2 = st.columns([3, 1])
        with _ai_sum_c1:
            _do_ai_sum = st.button('🤖 生成 AI 首席顧問戰略評估報告', key='btn_ai_sum2', type='primary')
        with _ai_sum_c2:
            if st.button('🗑️ 清除報告', key='btn_ai_sum2_clr'):
                st.session_state.pop(_ai_sum_key, None)
                st.rerun()

        if _do_ai_sum:
            # ── 彙整技術面數據 ────────────────────────────────────
            _atr2 = float(df2['high'].sub(df2['low']).tail(14).mean()) if df2 is not None and len(df2) >= 14 else 0
            _ibs2 = round((float(df2['close'].iloc[-1]) - float(df2['low'].iloc[-1])) /
                          max(float(df2['high'].iloc[-1]) - float(df2['low'].iloc[-1]), 0.01), 2) if df2 is not None and not df2.empty else 'N/A'
            _vol_ratio2 = round(float(df2['volume'].iloc[-1]) / float(df2['volume'].tail(20).mean()), 2) if df2 is not None and len(df2) >= 20 else 'N/A'
            _bb_pos2 = 'N/A'
            if df2 is not None and 'BB_upper' in df2.columns and 'BB_lower' in df2.columns:
                _bb_u = float(df2['BB_upper'].iloc[-1])
                _bb_l = float(df2['BB_lower'].iloc[-1])
                _bb_pos2 = f'{round((price2 - _bb_l) / max(_bb_u - _bb_l, 0.01) * 100, 1)}%'
            _ma_str2 = ', '.join(f'{k}:{"上方✅" if v else "下方⚠️"}' for k,v in _ma_above2.items()) if _ma_above2 else 'N/A'
            _rsi_str2 = f'{rsi2:.1f}' if rsi2 else 'N/A'
            _k_str2   = f'{k2:.1f}' if k2 else 'N/A'
            _d_str2   = f'{d2:.1f}' if d2 else 'N/A'
            _tech_data2 = (
                f"現價={price2:.2f} | 健康度={health2:.0f}/100 | RSI={_rsi_str2} | "
                f"KD=K:{_k_str2}/D:{_d_str2} | "
                f"IBS={_ibs2} | 量比={_vol_ratio2} | ATR={_atr2:.2f} | 布林位階={_bb_pos2}\n"
                f"均線位階={_ma_str2}\n"
                f"VCP={'突破訊號✅' if _vcp_ok2 else ('整理收縮中' if vcp2 else '未形成')}"
            )
            # ── 彙整籌碼數據 ──────────────────────────────────────
            _chip_str2 = '無法取得三大法人明細'
            if df2 is not None and not df2.empty:
                _fb = next((df2[c].tail(10).sum() for c in df2.columns if '外資' in str(c) and '買' in str(c)), None)
                _tb = next((df2[c].tail(10).sum() for c in df2.columns if '投信' in str(c)), None)
                _db = next((df2[c].tail(10).sum() for c in df2.columns if '自營' in str(c)), None)
                _parts = []
                if _fb is not None:
                    _parts.append(f'外資10日:{_fb/1e8:+.1f}億')
                if _tb is not None:
                    _parts.append(f'投信10日:{_tb/1e8:+.1f}億')
                if _db is not None:
                    _parts.append(f'自營10日:{_db/1e8:+.1f}億')
                if _parts:
                    _chip_str2 = ' | '.join(_parts)
            # ── 彙整基本面數據 ────────────────────────────────────
            _fund_str2 = []
            if _rev_yoy_list:
                _fund_str2.append(f'月營收YoY近3月={", ".join(_rev_yoy_list)}')
            if qtr2 is not None and not qtr2.empty:
                _gm_col = next((c for c in qtr2.columns if '毛利' in str(c)), None)
                _eps_col = next((c for c in qtr2.columns if 'eps' in str(c).lower() or 'EPS' in str(c)), None)
                if _gm_col:
                    _gm_vals = pd.to_numeric(qtr2[_gm_col].tail(4), errors='coerce').dropna()
                    _fund_str2.append(f'近4季毛利率={[round(v,1) for v in _gm_vals.tolist()]}%')
                if _eps_col:
                    _eps_vals = pd.to_numeric(qtr2[_eps_col].tail(4), errors='coerce').dropna()
                    _fund_str2.append(f'近4季EPS={_eps_vals.tolist()}')
            if cl2 and cl2 > 0:
                _fund_str2.append(f'合約負債={cl2/1e8:.1f}億')
            if cx2 and cx2 > 0:
                _fund_str2.append(f'資本支出={cx2/1e8:.1f}億')
            if avg_div2 > 0 and price2 > 0:
                _cp2_ai = round(avg_div2/YIELD_HIGH_DEC, 1)
                _fp2_ai = round(avg_div2/YIELD_MID_DEC, 1)
                _dp2_ai = round(avg_div2/YIELD_LOW_DEC, 1)
                _zone2 = ('便宜' if price2 <= _cp2_ai else '合理' if price2 <= _fp2_ai
                          else '昂貴' if price2 <= _dp2_ai else '超過昂貴')
                _fund_str2.append(f'357估值={_zone2}（便宜:{_cp2_ai}/合理:{_fp2_ai}/昂貴:{_dp2_ai}）')
            # v18.327 PR-B:AI prompt 補 P/B 估值帶狀分級(PR-A 已 SSOT 化)
            try:
                from shared.stock_buckets import classify_pb_level, get_pb_bands
                _bps_ai = fetch_bps(sid2)
                if _bps_ai > 0 and price2 > 0:
                    _pb_raw_ai = price2 / _bps_ai
                    _ind_ai = fetch_industry_category(sid2)
                    _bands_ai = get_pb_bands(_ind_ai)
                    _pb_lvl_ai = classify_pb_level(_pb_raw_ai, _bands_ai)
                    _fund_str2.append(
                        f'P/B 帶狀估值=PB:{_pb_raw_ai:.2f} {_pb_lvl_ai} '
                        f'(產業帶 低:{_bands_ai[0]}/中:{_bands_ai[1]}/高:{_bands_ai[2]})'
                    )
            except Exception:
                pass
            # v18.327 PR-B:AI prompt 補 MJ 趨勢分數合議(月+季 65/35)
            try:
                from datetime import date as _date_ai
                from src.compute.health import (
                    current_finmind_yyyymm as _cfymm_ai,
                    list_snapshots as _ls_ai,
                    load_snapshot as _ld_ai,
                    save_snapshot as _sv_ai,
                )
                from src.compute.health import compute_one_stock_trend as _cost_ai
                _ymm_ai = _cfymm_ai(_date_ai.today())
                _mj_row_ai = _cost_ai(
                    sid=sid2, yyyymm_curr=_ymm_ai, token=FINMIND_TOKEN, w_monthly=0.65,
                    fetch_financial_statements=fetch_financial_statements,
                    analyze_financial_health=analyze_financial_health,
                    list_snapshots=_ls_ai, load_snapshot=_ld_ai, save_snapshot=_sv_ai,
                )
                _fund_str2.append(
                    f"MJ 趨勢分數(月+季 65/35)={_mj_row_ai.get('label', '—')} "
                    f"(合分 {_mj_row_ai.get('score', 0):+.2f},月分 {_mj_row_ai.get('mon_sub', 0):+.2f}/"
                    f"季分 {_mj_row_ai.get('mj_sub', 0):+.2f})"
                )
            except Exception:
                pass
            _fund_data2 = '\n'.join(_fund_str2) if _fund_str2 else '基本面資料不足'
            # ── 彙整財報體檢結果 ──────────────────────────────────
            _fh_res2 = st.session_state.get(f'_fh_{sid2}', {})
            _health_check_str2 = '尚未執行財報體檢'
            if _fh_res2 and not _fh_res2.get('error'):
                _opm2 = _fh_res2.get('opm_data', {})
                _opm_str2 = (f"應付帳款天數={_opm2.get('payable_days','N/A')}天 / "
                             f"應收帳款天數={_opm2.get('receivable_days','N/A')}天 → "
                             f"{'具備快收慢付優勢' if _opm2.get('advantage') else '付款週期不利'}"
                             if _opm2 else '無 OPM 資料')
                _red2 = _fh_res2.get('red_flags', '')
                _flags_str2 = (_red2 if _red2 and _red2.strip().lower() not in ('none', '無', '') else '無明顯地雷')
                _health_check_str2 = (
                    f"現金水位={_fh_res2.get('cash_ratio_status','')} {_fh_res2.get('cash_ratio_value','')} | "
                    f"OCF={_fh_res2.get('ocf_status','')} {_fh_res2.get('ocf_value','')} | "
                    f"負債比={_fh_res2.get('debt_ratio_status','')} {_fh_res2.get('debt_ratio_value','')}\n"
                    f"企業DNA={_fh_res2.get('business_model_dna','N/A')}\n"
                    f"OPM商業話語權={_opm_str2}\n"
                    f"五力雷達={_fh_res2.get('radar_scores',{})}\n"
                    f"AI財報洞察={_fh_res2.get('ai_insight','')}\n"
                    f"地雷警示={_flags_str2}"
                )
            # ── 彙整市場背景 ──────────────────────────────────────
            _mkt_info2 = st.session_state.get('mkt_info', {})
            _regime_txt2 = {'bull':'多頭市場（積極操作）','neutral':'震盪整理（謹慎觀望）','bear':'空頭市場（縮減部位）'}.get(_regime2, _regime2)
            # 宏觀指標彙整（VIX / 美核心CPI / 🇹🇼 台灣 PMI / 美10Y / 費半 SOX）— 供 AI 跨資產判讀
            _macro_info2 = st.session_state.get('macro_info', {}) or {}
            _ma_snap2    = st.session_state.get('ma_snap', {}) or {}
            _intl_snap2  = st.session_state.get('intl_snap', {}) or {}
            _macro_lines2 = []
            _vix_v2 = (_macro_info2.get('vix') or {}).get('current') or _ma_snap2.get('vix')
            if _vix_v2 is not None:
                try:
                    _macro_lines2.append(f"VIX 恐慌指數={float(_vix_v2):.2f}（>20 警戒、>30 恐慌）")
                except (TypeError, ValueError):
                    pass
            _cpi_v2 = (_macro_info2.get('us_core_cpi') or {}).get('yoy') or _ma_snap2.get('cpi')
            if _cpi_v2 is not None:
                try:
                    _macro_lines2.append(f"美核心 CPI YoY={float(_cpi_v2):+.2f}%（Fed 目標 2%；>3% 升息壓力）")
                except (TypeError, ValueError):
                    pass
            _pmi_v2 = (_macro_info2.get('ism_pmi') or {}).get('value')
            if _pmi_v2 is not None:
                try:
                    _macro_lines2.append(f"🇹🇼 台灣 PMI={float(_pmi_v2):.1f}（CIER；50=榮枯線；<45=製造業衰退強訊；台灣製造業景氣領先指標）")
                except (TypeError, ValueError):
                    pass
            _tnx_v2 = (_intl_snap2.get('tnx') or {}).get('last') or _ma_snap2.get('us10y')
            if _tnx_v2 is not None:
                try:
                    _macro_lines2.append(f"美 10Y 殖利率={float(_tnx_v2):.2f}%（>4% 估值壓抑、>5% 殺戮區）")
                except (TypeError, ValueError):
                    pass
            _sox_obj2 = _intl_snap2.get('sox') or {}
            _sox_pct2 = _sox_obj2.get('pct')
            _sox_last2 = _sox_obj2.get('last')
            if _sox_pct2 is not None:
                try:
                    _sl_str = f"｜當前 {float(_sox_last2):.0f}" if _sox_last2 is not None else ""
                    _macro_lines2.append(f"費半 SOX={float(_sox_pct2):+.2f}%{_sl_str}（領先台股科技股 2-4 週）")
                except (TypeError, ValueError):
                    pass
            _macro_extra2 = "\n  • " + "\n  • ".join(_macro_lines2) if _macro_lines2 else "（暫無，請先到「宏觀拼圖」分頁更新）"
            _mkt_ctx2 = (
                f"大盤格局={_regime_txt2} | 健康評分={_mkt_info2.get('market_score','N/A')} | "
                f"建議持股={_mkt_info2.get('exposure_limit_pct', st.session_state.get('macro_state',{}).get('exposure_limit_pct','N/A'))}%\n"
                f"宏觀跨資產背景：{_macro_extra2}"
            )
            # ── 抓取個股新聞（近期，RSS 偏近期）──────────────────
            _news_diag2 = []
            _stock_news2 = _fetch_stock_news(sid2, name2, 25, recency='6m', _diag=_news_diag2)
            st.session_state[_ai_sum_key + '_news'] = _stock_news2
            st.session_state[_ai_sum_key + '_newsdiag'] = _news_diag2
            _show_news_expander(_stock_news2, _news_diag2)
            _news_str2 = '\n'.join(
                f'- {_n["title"]}（{_n.get("source","RSS")} · {_n.get("published","")}）'
                for _n in _stock_news2
            ) if _stock_news2 else '（暫無相關個股新聞）'
            # ── 補餵上方已算章節（防呆：未算到顯示「未計算」不崩）──────
            try:
                _sr_parts2 = [
                    f'現價={_cur_p:.2f}',
                    f'近20日壓力={_hi20_p:.2f}(距現價+{_dist_hi}%)',
                    f'近20日支撐={_lo20_p:.2f}(距現價-{_dist_lo}%)',
                    f'停利目標1(+5%)={_tp1_p} / 目標2(+10%)={_tp2_p}',
                    f'建議停損(-8%)={_sl_p} | 盈虧比={_rr_p}x',
                ]
                if _entry_half:
                    _sr_parts2.append(f'朱家泓大量紅K 1/2 低風險買點={_entry_half}')
                if _abs_sl:
                    _sr_parts2.append(f'紅K低點絕對停損={_abs_sl}')
                _sr_str2 = ' | '.join(_sr_parts2)
            except Exception:
                _sr_str2 = '（支撐壓力/停利停損未計算）'
            # v18.309 Bug2 Stage 1：改讀 _xsec(compute-once,資料載入後算)→ 與顯示段
            # 執行順序解耦。key 缺席(該組計算失敗)→ except / get None 落 fallback(行為等價)。
            try:
                _conc_str2 = (f'集中度={_xsec["con20"]:+.1f}%（大戶外資+投信淨買佔成交量）| '
                              f'延續性={_xsec["cty20"]:.0f}%（買超日佔比）| 訊號={_xsec["sig20"]}')
            except Exception:
                _conc_str2 = '（近20日籌碼集中度未取得）'
            try:
                _li_str2 = (f'總覽 🟢×{_xsec["li_green"]} 🟡×{_xsec["li_yellow"]} 🔴×{_xsec["li_red"]}；'
                            + '；'.join(f'{_r["signal"]}{_r["name"]}={_r["value"]}'
                                       for _r in _xsec["li_results"][:8]))
            except Exception:
                _li_str2 = '（基本面先行指標未計算）'
            _rs_v = _xsec.get('rs_val')
            _rs_str2 = (f'{_rs_v:.0f} 分（≥75 強勢領漲、50-75 中性、<50 落後大盤；相對加權指數）'
                        if isinstance(_rs_v, (int, float)) else '（未計算）')
            try:
                _cap_v = _xsec.get('capital')
                if _cap_v and _cap_v > 0:
                    _cl_r = (locals().get('cl2') or 0) / _cap_v * 100
                    _cx_r = (locals().get('cx2') or 0) / _cap_v * 100
                    _is_lead = '✅ 符合龍頭高成長特徵' if (_cl_r >= 50 or _cx_r >= CAPEX_TO_EQUITY_RATIO_THRESHOLD_PCT) else '未達龍頭門檻'
                    _lead_str2 = (f'合約負債/股本={_cl_r:.0f}%、資本支出/股本={_cx_r:.0f}% → {_is_lead}'
                                  '（孫慶龍龍多：合約負債≥股本50%=客戶預付旺、資本支出≥股本80%=積極擴產）')
                else:
                    _lead_str2 = '（股本資料未取得，無法判定龍頭擴產特徵）'
            except Exception:
                _lead_str2 = '（龍頭預警未計算）'
            # ── 建構白話結構化 Prompt（共用元件 ai_structured_summary）──
            from src.services import build_structured_summary_prompt
            _sections_ai = [
                {'name': '這檔現在強不強、位置貴不貴（技術面）',
                 'data': f'{_tech_data2}\nRS 相對強度：{_rs_str2}'},
                {'name': '如果要買賣，附近的關鍵價位',
                 'data': _sr_str2},
                {'name': '大戶、法人在買還是在賣（籌碼）',
                 'data': (f'三大法人：{_chip_str2}\n'
                          f'{_chip_radar_summary or "集保大戶/散戶：無資料（未取得集保股權分散表）"}\n'
                          f'近20日籌碼集中度：{_conc_str2}')},
                {'name': '公司有沒有在賺錢、股價貴不貴（基本面與估值）',
                 'data': (f'{_fund_data2}\n'
                          f'基本面先行指標（🟢佳/🟡中性/🔴差）：{_li_str2}\n'
                          f'龍頭擴產檢測：{_lead_str2}')},
                {'name': '財報體質健不健康、有沒有地雷',
                 'data': _health_check_str2},
                {'name': '大環境順不順（大盤與國際）',
                 'data': _mkt_ctx2},
            ]
            _ai_sum_prompt = build_structured_summary_prompt(
                f'{sid2} {name2}', _sections_ai, news_text=_news_str2,
                overall_question=('這檔股票現在整體看起來如何、現在算相對好的'
                                  '時機還是要小心、最該注意什麼風險。'))

            # 串流輸出（打字機效果），L5：只讀 _ai_sum_prompt，不抓資料
            def _ai_stream_gen():
                _full = gemini_call(_ai_sum_prompt, max_tokens=1800)
                _chunk = 80
                import time as _t_ai
                for _i in range(0, len(_full), _chunk):
                    yield _full[_i:_i + _chunk]
                    _t_ai.sleep(0.015)
            _ai_sum_result = st.write_stream(_ai_stream_gen())
            st.session_state[_ai_sum_key] = _ai_sum_result

        if _ai_sum_cached and not _do_ai_sum:
            _cached_news = st.session_state.get(_ai_sum_key + '_news')
            if _cached_news is not None:
                _show_news_expander(_cached_news, st.session_state.get(_ai_sum_key + '_newsdiag'))
            st.markdown(_ai_sum_cached)
        elif not _do_ai_sum:
            st.caption('▲ 點擊上方按鈕，AI 將綜合技術面、基本面、財報體檢、近期新聞五大面向生成完整戰略評估報告。')

# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
# TAB 3: 綜合評分戰情室（汰弱留強 × 多因子評分 合併版）
# ══════════════════════════════════════════════════════════════

    st.markdown(f"""<div style="background:#2a0d0d;border:1px solid {TRAFFIC_RED};border-radius:8px;
padding:10px 14px;font-size:11px;color:{TRAFFIC_RED};margin-top:12px;">
⚠️ 本手冊整理自各大師公開課程內容，僅供學術研究與教育用途。
投資涉及風險，任何操作均應自行判斷，盈虧自負。本系統非投資顧問，不構成買賣建議。
</div>""", unsafe_allow_html=True)
