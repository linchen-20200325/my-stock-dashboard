"""TAB 比較 × 排行（多股比較 / 多因子排行 / 汰弱留強）— 從 app.py 抽出（PR P2-B Phase 5-B）

依賴策略
========
- Top-level: streamlit
- 函式內 late import: 27 個依賴（含 app.py 內部 helper 與外部模組函式），
  避免循環 import（tab_stock_grp.py ← app.py ← tab_stock_grp.py）。

呼叫端
======
- app.py: `with tab_stock_grp: render_stock_grp()`
"""
from __future__ import annotations

import streamlit as st

from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW


def render_stock_grp():
    # ─ Late imports(避免循環 import)─
    from src.config import FINMIND_TOKEN
    # 外部模組
    from src.services import build_structured_summary_prompt
    from src.services.stock_grp_service import get_news_for as _fetch_news_for  # R1 v18.405
    # app.py 內部 helper
    from app import gemini_call, parse_stocks

    st.markdown("""<div style="padding:6px 0 4px;">
<span style="font-size:20px;font-weight:900;color:#e6edf3;">📊 比較 × 排行</span>
<span style="font-size:11px;color:#484f58;margin-left:10px;">市場狀態 · 多股比較 · 多因子排行 · 汰弱留強 · 最終建議</span>
</div>""", unsafe_allow_html=True)

    # ══ ① 市場狀態快覽(Batch 7-1 v18.413:抽至 stock_grp_sections.section_market_status)══
    from src.ui.tabs.stock_grp_sections import render_market_status_section
    render_market_status_section()

    # ══ ② 輸入多檔代碼(v19.164 唯一來源:蔡森 / MJ / 三階段濾網全部吃這裡)═══
    # session_state-backed(供「帶入持股」回填;不用 value= 避免 widget 衝突警告)
    if 'multi_input' not in st.session_state:
        st.session_state['multi_input'] = '2330 2454 2317 2382 3017 2308 2303 2376 6669 3661'
    with st.container(border=True):
        t3c1, t3c2 = st.columns([4, 1])
        with t3c1:
            multi_input = st.text_area(
                '輸入多檔代碼（逗號/空格/換行，最多10檔）— 蔡森 / MJ 體質 / 三階段濾網全部吃這一組',
                height=68, key='multi_input',
                placeholder='例：2330 2454 2317 2382 3017')
        with t3c2:
            st.markdown('<br>', unsafe_allow_html=True)
            t3_run_btn = st.button('🚀 批次分析', type='primary',
                                   use_container_width=True, key='t3_run_btn')
        # v19.164:除貼清單外,一鍵帶入自己的 Google Sheet 持股(填入上方唯一輸入框)
        st.button('🔗 帶入我的持股（Google Sheet 組合）', key='_grp_load_holdings',
                  on_click=_grp_load_holdings_callback)
        _hmsg = st.session_state.pop('_grp_holdings_msg', None)
        if _hmsg:
            (st.success if _hmsg[0] == 'ok' else st.warning)(_hmsg[1])

    stock_list_t3 = parse_stocks(multi_input)[:10]
    if stock_list_t3:
        st.caption(f'待分析：{", ".join(stock_list_t3)}（共{len(stock_list_t3)}檔）'
                   '　·　按「🚀 批次分析」一鍵串跑：排行總表 + 蔡森目標價 + MJ 趨勢×轉機 + 三階段濾網')
    elif t3_run_btn:
        st.warning('⚠️ 請先在上方輸入至少一個有效股票代碼，再按「🚀 批次分析」')

    # ══ 批次分析邏輯(Batch 7-2 v18.414:抽至 stock_grp_sections.section_batch_fetcher)══
    if t3_run_btn and stock_list_t3:
        from src.ui.tabs.stock_grp_sections import run_batch_fetch
        run_batch_fetch(stock_list_t3)

    # ══ 顯示結果(Batch 7-3 v18.415:抽至 stock_grp_sections.section_portfolio_summary)══
    from src.ui.tabs.stock_grp_sections import render_portfolio_summary_section
    _t3_summary = render_portfolio_summary_section(gemini_call_fn=gemini_call)
    results_t3  = _t3_summary.get("results_t3", [])
    score_t3    = _t3_summary.get("score_t3", [])
    risk_alerts = _t3_summary.get("risk_alerts", [])
    _fund_map   = _t3_summary.get("fund_map", {})

    # ══ 批次財報體檢(Batch 7-4 v18.416:抽至 stock_grp_sections.section_financial_health)══
    from src.ui.tabs.stock_grp_sections import render_financial_health_section
    _fh_t3_cached = render_financial_health_section(
        stock_list=stock_list_t3,
        results_t3=results_t3,
        finmind_token=FINMIND_TOKEN,
    )
    # ══ 📊 MJ 趨勢分數（v18.189）+ 🎯 三階段濾網（v19.58）═══════════
    # v18.223 一鍵化：吃 batch 跑完時鎖定的 codes（t3_batch_codes），自動跑 MJ + picker + AI。
    # 不再依賴 stock_list_t3（避免 textarea 改動觸發重跑），改 textarea 後須按「批次分析」才更新。
    _batch_codes = st.session_state.get('t3_batch_codes')
    if _batch_codes:
        _bc_list = list(_batch_codes)
        _render_mj_trend_section(_bc_list, auto_run=True)
        # v18.453:轉傳批次財報體檢結果,讓 Stage 1 負債比檢查與其判定一致
        _render_stage_picker_section(_bc_list, auto_run=True, fh_map=_fh_t3_cached)
    elif stock_list_t3:
        st.info('💡 上方按「🚀 批次分析」會自動串跑 MJ 趨勢分數 + 三階段濾網 + AI 三型建議。')

    # ── 🤖 AI 投資組合綜合判讀(Batch 7-5 v18.417:抽至 stock_grp_sections.section_ai_portfolio)──
    from src.ui.tabs.stock_grp_sections import render_ai_portfolio_section
    render_ai_portfolio_section(
        results_t3=results_t3,
        score_t3=score_t3,
        risk_alerts=risk_alerts,
        fund_map=_fund_map,
        fh_cached=_fh_t3_cached,
        gemini_call_fn=gemini_call,
        fetch_news_fn=_fetch_news_for,
        build_prompt_fn=build_structured_summary_prompt,
    )

    # ── 🎚️ 風險貢獻分解（v19.138：輸入持股張數 → 市值權重 → Euler 分解，與 ETF 組合共用 L2/L4）──
    _render_risk_contribution_section(stock_list_t3)

    # ── 🧬 AI 總結本頁（v19.122 Phase 2，用批次已載資料組 bundle，不重抓；fail-soft）──
    try:
        from src.ui.tabs.tab_ai_chat import render_tab_summary
        render_tab_summary('個股組合', {
            '批次比較結果': st.session_state.get('t3_data'),
            '批次代碼': st.session_state.get('t3_batch_codes'),
            '財報體檢': st.session_state.get('_fh_t3_results'),
        }, context='general')
    except Exception as _ai_sum_e:
        st.caption(f'🧬 AI 總結暫不可用：{type(_ai_sum_e).__name__}')


def _grp_load_holdings_callback() -> None:
    """帶入 Google Sheet 持股組合代碼 → 填入上方唯一輸入框 multi_input(on_click callback)。

    v19.164 單一來源化:原「MJ 體檢轉機」獨立輸入框的帶入持股鈕搬來這裡,改填組合唯一輸入。
    §8.2.A EX-PASSTHRU-1:L5 lazy import L1 gsheet_portfolio(pass-through、無 L3 業務值)。
    graceful:未登入 Google / 未設組合 → 只回 warn,不炸。
    """
    try:
        from src.data.portfolio import gsheet_portfolio as _gsp  # EX-PASSTHRU-1
        names = _gsp.list_portfolios()
        if not names:
            st.session_state['_grp_holdings_msg'] = (
                'warn', '找不到雲端持股組合 — 請先到「🏦 ETF → 組合」設定 Google Sheet 持股。')
            return
        tickers: list[str] = []
        for _nm in names:
            for _r in (_gsp.load_portfolio(_nm) or []):
                _t = str(_r.get('ticker', '')).strip()
                if _t and _t not in tickers:
                    tickers.append(_t)
        if not tickers:
            st.session_state['_grp_holdings_msg'] = ('warn', '雲端持股組合是空的。')
            return
        capped = tickers[:10]  # 批次上限 10(parse_stocks 對齊)
        st.session_state['multi_input'] = ' '.join(capped)
        _tail = f'(共 {len(tickers)} 檔,取前 10)' if len(tickers) > 10 else f'(共 {len(tickers)} 檔)'
        st.session_state['_grp_holdings_msg'] = ('ok', f'已帶入持股 {_tail}:{" ".join(capped)}')
    except Exception as _e:  # noqa: BLE001 — 帶入失敗不炸 UI
        st.session_state['_grp_holdings_msg'] = (
            'warn', f'帶入持股失敗:{type(_e).__name__}(可能未登入 Google / 未設定組合)')


def _render_risk_contribution_section(stock_list: list[str]) -> None:
    """個股組合風險貢獻分解（v19.138）— 輸入各檔持有張數 → 市值權重 → Euler 分解。

    與 ETF 組合共用 L2 `compute_risk_contribution` + L4 `render_risk_contribution_panel`。
    button-gated：避免每次 rerun 都抓 N 檔 1 年價格（僅按「算風險貢獻」時才抓）。
    §1：抓不到價格的檔剔除並列出（不灌 0）；權重 scale-free（張數→市值→內部正規化）。
    §8.2 EX-PASSTHRU-1：L5 直呼 L1 `fetch_stock_history_1y`（pass-through、無 L3 業務值，
    L1 內已 @st.cache_data 集中緩存），沿用個股組合既有 lazy import 慣例。
    """
    import pandas as pd
    import streamlit as _st  # noqa: F811

    from src.compute.risk.risk_contribution import compute_risk_contribution
    from src.compute.risk.risk_control import check_portfolio_limits  # v19.151 投組上限接線
    from src.data.stock.picker_fetcher import fetch_stock_history_1y  # EX-PASSTHRU-1
    from src.ui.render.risk_contribution_render import render_risk_contribution_panel

    if not stock_list:
        return
    _st.markdown('---')
    with _st.expander('🎚️ 風險貢獻分解（輸入持股張數 → 看風險壓在哪幾檔）', expanded=False):
        _st.caption('輸入各檔「持有張數」，換算市值權重後做 Euler 風險分解 —— '
                    '揭露某檔「市值佔比 vs 風險佔比」的落差（風險是否壓在少數幾檔）。')
        _seed = pd.DataFrame({'代碼': list(stock_list), '持有張數': [0.0] * len(stock_list)})
        _edited = _st.data_editor(
            _seed, hide_index=True, use_container_width=True, key='rc_t3_editor',
            column_config={
                '代碼': _st.column_config.TextColumn(disabled=True),
                '持有張數': _st.column_config.NumberColumn(min_value=0.0, step=1.0, format='%.0f'),
            })
        if not _st.button('🎚️ 算風險貢獻', key='rc_t3_go'):
            return
        _lots: dict[str, float] = {}
        for _, _r in _edited.iterrows():
            try:
                _n = float(_r['持有張數'] or 0)
            except (TypeError, ValueError):
                _n = 0.0
            if _n > 0:
                _lots[str(_r['代碼']).strip()] = _n
        if not _lots:
            _st.info('請至少替一檔輸入持有張數（> 0）。')
            return
        _ret_dict: dict[str, "pd.Series"] = {}
        _weights: dict[str, float] = {}
        _price_miss: list[str] = []
        with _st.spinner(f'抓取 {len(_lots)} 檔近 1 年價格…'):
            for _code, _n in _lots.items():
                _df, _ = fetch_stock_history_1y(_code)
                if _df is not None and not _df.empty and 'Close' in _df.columns:
                    _close = _df['Close']
                    _ret_dict[_code] = _close.pct_change()
                    # 市值 = 張數 × 1000 股/張 × 現價（×1000 對所有檔一致，正規化後不影響佔比）
                    _weights[_code] = _n * 1000.0 * float(_close.iloc[-1])
                else:
                    _price_miss.append(_code)
        _returns = pd.DataFrame(_ret_dict).ffill() if _ret_dict else pd.DataFrame()
        _rc = compute_risk_contribution(_returns, _weights)
        render_risk_contribution_panel(_rc, show_header=False)

        # v19.151 投組層級風控接線:用同一份市值權重,把 RiskController 早定義卻空轉的
        # 「單股 ≤10% / 持股 ≤10 檔」上限真的顯示出來(§6.3 SSOT 門檻)。回撤暫停/現金
        # 下限需成本基礎與現金輸入 → 另案。抓不到價的檔不在 _weights,不計入集中度。
        _lim = check_portfolio_limits(_weights)
        _sm = _lim['single_max_pct'] * 100
        _rows = []
        if _lim['too_many_positions']:
            _rows.append(f'🔴 持股 <b>{_lim["n_positions"]}</b> 檔 — 超過建議上限 '
                         f'{_lim["max_positions"]} 檔(分散過度、難管理)')
        else:
            _rows.append(f'🟢 持股 {_lim["n_positions"]} 檔(上限 {_lim["max_positions"]})')
        if _lim['over_concentration']:
            _ov = '、'.join(f'{c} {p:.0f}%' for c, p in _lim['over_concentration'])
            _rows.append(f'🔴 單股超過 {_sm:.0f}%:<b>{_ov}</b> — 過度集中,考慮分散')
        elif _lim['max_weight_pct'] is not None:
            _rows.append(f'🟢 最大單股 {_lim["max_weight_pct"]:.0f}%(上限 {_sm:.0f}%),集中度 OK')
        _verdict = '🟢 集中度 OK' if _lim['ok'] else '🔴 集中度超標'
        _st.markdown(
            '<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;'
            'padding:10px 14px;margin-top:8px;">'
            f'<b>🛡️ 投組集中度守門</b>:<b>{_verdict}</b>'
            + ''.join(f'<div style="font-size:12px;color:#c9d1d9;margin-top:3px;">{_r}</div>'
                      for _r in _rows)
            + '</div>', unsafe_allow_html=True)
        _st.caption('單股 ≤10% / 持股 ≤10 檔為 SSOT 風控門檻;權重＝市值佔比。'
                    '回撤 15% 暫停 / 現金下限需成本基礎與現金輸入 → 另案。')

        if _price_miss:
            _st.caption(f'⚪ 這幾檔抓不到價格、已略過：{"、".join(_price_miss)}')


def _render_stage_picker_section(stock_list: list[str], *,
                                  auto_run: bool = False,
                                  fh_map: dict | None = None) -> None:
    """v19.58 個股組合內三階段濾網 — 直接拿 stock_list_t3 為 candidates，共用 picker 子函式。

    v18.223：auto_run=True 串接「批次分析」一鍵流程（picker 跳過按鈕直接跑、AI 也自動）。
    與 _render_mj_trend_section 互補：MJ 趨勢分數看「最近 3 月/3 季的進步退步」，
    三階段濾網看「當下是否進場（基本面 9 項 ＋ 籌碼技術 6 項 ＋ AI 三型建議）」。
    共用 data_loader.fetch_financial_statements + financial_health_engine（與 MJ 同源）。

    fh_map:v18.453 — 上方「批次財報體檢」已算好的 dict[代碼, analyze_financial_health()
    結果],轉傳給 render_tab_stock_picker 讓 Stage 1 負債比檢查直接沿用同一判定,
    修 user 回報「財報體檢顯示🟡、智慧選股卻顯示✅」的門檻不一致問題。
    """
    import pandas as pd
    import streamlit as _st  # noqa: F811

    from app import gemini_call  # late import 沿用 render_stock_grp 同模式避循環
    from src.ui.tabs.tab_stock_picker import render_tab_stock_picker

    _st.markdown('---')
    _st.markdown(
        '<div style="margin:16px 0 8px;padding:8px 16px;'
        'background:linear-gradient(90deg,#3b82f622,#0d1117);'
        'border-left:4px solid #3b82f6;border-radius:0 6px 6px 0;">'
        '<span style="font-size:15px;font-weight:900;color:#3b82f6;">'
        '🎯 三階段濾網（基本面 → 籌碼技術 → AI 建議）</span>'
        '<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
        f'直接用上方輸入的 {len(stock_list)} 檔當候選</span></div>',
        unsafe_allow_html=True,
    )

    # 把純代碼 list 轉成 picker 需要的最小 DataFrame
    _df = pd.DataFrame({'代碼': stock_list})
    render_tab_stock_picker(
        gemini_fn=gemini_call,
        candidates=_df,
        source_label='個股組合輸入',
        key_prefix='picker_t3',
        auto_run=auto_run,
        fh_map=fh_map,
    )


def _render_mj_trend_section(stock_list: list[str], *,
                              auto_run: bool = False) -> None:
    """v18.189 個股組合內「MJ 趨勢分數」區塊。

    v18.223：auto_run=True 串接「批次分析」一鍵流程（移除手動按鈕，自動跑全程 + cache）。
    對 stock_list 每檔合議「近 3 月月營收動能」+「近 3 季 MJ 體檢 status delta」
    產出 5 段判定（🚀 強進步 / 📈 進步 / ➖ 中性 / 📉 退步 / 🔻 強退步）。
    月權重 65%（先行）/ 季權重 35%（落後但見品質）。
    """
    import pandas as pd
    from datetime import date

    import streamlit as _st  # noqa: F811 — explicit local alias
    from src.config import FINMIND_TOKEN as _TOK
    from src.services.stock_grp_service import get_financial_statements as fetch_financial_statements  # R1 v18.405
    from src.services import analyze_financial_health
    from src.compute.health import diff_mj_health  # noqa: F401 — used transitively by score
    from src.compute.health import (
        current_finmind_yyyymm,
        list_snapshots,
        load_snapshot,
        save_snapshot,
    )
    from src.compute.health import compute_one_stock_trend, compute_trend_score  # noqa: F401

    _st.markdown('---')
    _st.markdown(
        '<div style="margin:16px 0 8px;padding:8px 16px;'
        'background:linear-gradient(90deg,#22c55e22,#0d1117);'
        'border-left:4px solid #22c55e;border-radius:0 6px 6px 0;">'
        '<span style="font-size:15px;font-weight:900;color:#22c55e;">'
        '📊 MJ 趨勢 × 轉機（找體質差→變好）</span>'
        '<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
        '月營收動能 × 季財報體檢 · 65/35 合議 · 併入本業虧轉盈 🌟 / 盈轉虧 ⚠️ 轉機偵測</span></div>',
        unsafe_allow_html=True,
    )
    _st.caption(
        '🔰 **判定規則**：≥+1.5 🚀 強進步 / +0.5~+1.5 📈 進步 / -0.5~+0.5 ➖ 中性 / '
        '-1.5~-0.5 📉 退步 / ≤-1.5 🔻 強退步。'
        '**月權重高**因月營收 10 日公布（先行指標），季財報 45 天遞延（落後但見獲利品質）。'
        '近 3 季 MJ 不足時自動補抓本季快照。'
        '**「轉機」欄** = 用同一份季財報快照判本業虧轉盈(🌟)/盈轉虧(⚠️),零額外抓取。'
    )

    # v18.223：auto_run 模式移除手動按鈕；slider 保留以利使用者觀察/調整權重
    _w_mon = _st.slider(
        '月營收權重',
        min_value=0.4, max_value=0.9, value=0.65, step=0.05,
        key='_mj_trend_w_mon',
        help='月營收動能占比，季財報自動 = 1 - 此值。改動後下次按「批次分析」生效。',
    )

    if not auto_run:
        _st.caption('💡 上方按「🚀 批次分析」自動跑 MJ 趨勢分數（首次 ~30-60s）')
        return

    if not _TOK:
        _st.error('🔴 未設定 `FINMIND_TOKEN` → 無法抓財報與月營收')
        return

    yyyymm_curr = current_finmind_yyyymm(date.today())
    # v18.223 cache 防 rerun 重跑（key 含 codes + 權重 + 當前季）
    _mj_cache_key = (
        f'_mj_trend_rows_{hash(tuple(stock_list))}_'
        f'{round(float(_w_mon) * 100)}_{yyyymm_curr}'
    )
    rows = _st.session_state.get(_mj_cache_key)
    if rows is None:
        rows = []
        prog = _st.progress(0.0, text=f'MJ 趨勢分數中 {len(stock_list)} 檔...')
        for i, sid in enumerate(stock_list, 1):
            prog.progress(i / len(stock_list),
                          text=f'[{i}/{len(stock_list)}] {sid} 趨勢計算中...')
            row = compute_one_stock_trend(
                sid, yyyymm_curr, _TOK, float(_w_mon),
                fetch_financial_statements=fetch_financial_statements,
                analyze_financial_health=analyze_financial_health,
                list_snapshots=list_snapshots,
                load_snapshot=load_snapshot,
                save_snapshot=save_snapshot,
            )
            rows.append(row)
        prog.empty()
        _st.session_state[_mj_cache_key] = rows

    _render_mj_trend_table(rows, pd, _st, yyyymm_curr)


_TREND_SORT_ORDER = {
    'strong_down': 0, 'down': 1, 'neutral': 2,
    'up': 3, 'strong_up': 4, 'error': 5,
}


def _fmt_quarter(yyyymm: str) -> str:
    """202503 → 2025Q1（季底月份對應季）；格式不符回原字串。"""
    s = str(yyyymm or '').strip()
    if len(s) != 6 or not s.isdigit():
        return s or '—'
    q = {'03': 'Q1', '06': 'Q2', '09': 'Q3', '12': 'Q4'}.get(s[4:6], s[4:6])
    return f'{s[:4]}{q}'


def _render_mj_trend_table(rows: list[dict], pd, st_mod, yyyymm_curr: str = '') -> None:
    """渲染結果表（退步在前）+ 統計 KPI。"""
    if not rows:
        return
    cnt = {k: 0 for k in _TREND_SORT_ORDER}
    for r in rows:
        cnt[r['label_code']] = cnt.get(r['label_code'], 0) + 1
    cols = st_mod.columns(5)
    cols[0].metric('🔻 強退步', cnt.get('strong_down', 0))
    cols[1].metric('📉 退步', cnt.get('down', 0))
    cols[2].metric('➖ 中性', cnt.get('neutral', 0))
    cols[3].metric('📈 進步', cnt.get('up', 0))
    cols[4].metric('🚀 強進步', cnt.get('strong_up', 0))

    # v18.199 ── 📊 快照新鮮度條（MJ 季財報分來自哪季 — 防補抓失敗靜默沿用舊季）──
    _fresh = sum(1 for r in rows if r.get('snap_stale') is False)
    _stale = sum(1 for r in rows if r.get('snap_stale') is True)
    _missing = sum(1 for r in rows if r.get('snap_stale') is None)
    if _stale == 0 and _missing == 0:
        _fc, _ft = TRAFFIC_GREEN, '🟢 全部最新'
    elif _fresh == 0:
        _fc, _ft = TRAFFIC_RED, '🔴 全部落後或缺'
    else:
        _fc, _ft = TRAFFIC_YELLOW, '🟡 部分落後'
    st_mod.markdown(
        f'<div style="margin:8px 0;padding:8px 14px;border-left:4px solid {_fc};'
        f'background:{_fc}14;border-radius:0 6px 6px 0;font-size:13px;">'
        f'<b style="color:{_fc};">📊 MJ 快照新鮮度</b>　'
        f'📅 應有最新季 <b>{_fmt_quarter(yyyymm_curr)}</b>　'
        f'<span style="color:{_fc};">{_ft}</span>　'
        f'<span style="color:#8b949e;">🟢 最新 {_fresh} ／ 🟡 落後 {_stale} ／ ⬜ 無快照 '
        f'{_missing}（共 {len(rows)} 檔）</span></div>',
        unsafe_allow_html=True,
    )

    def _quarter_cell(r: dict) -> str:
        _ym = r.get('snap_ym') or ''
        if not _ym:
            return '⬜ 無'
        _q = _fmt_quarter(_ym)
        return f'🟡 {_q}（舊）' if r.get('snap_stale') else f'🟢 {_q}'

    rows_sorted = sorted(rows, key=lambda r: _TREND_SORT_ORDER.get(r['label_code'], 99))

    # 🌟/⚠️ 轉機摘要(v19.164 合併「MJ 體檢轉機」)——user 要的「找體質差→變好」在這裡,
    # 判定由 compute_one_stock_trend 用同一份季快照附帶算出(turn_icon / diff_verdict),零額外抓取。
    _turn = [r['sid'] for r in rows_sorted if str(r.get('turn_icon', '')).startswith('🌟')]
    _break = [r['sid'] for r in rows_sorted if str(r.get('turn_icon', '')).startswith('⚠️')]
    if _turn:
        st_mod.success(f'🌟 **本業虧轉盈轉機股**：{", ".join(_turn)} —— 「體質差→變好」看這裡')
    if _break:
        st_mod.error(f'⚠️ **本業盈轉虧雷股**：{", ".join(_break)}')

    df = pd.DataFrame([{
        '代碼': r['sid'],
        '判定': r['label'],
        '轉機': r.get('turn_icon') or '—',
        '綜合分數': round(r['score'], 2),
        '月營收分': round(r['mon_sub'], 2),
        'MJ 季財報分': round(r['mj_sub'], 2),
        '季別': _quarter_cell(r),
        '備註': r['note'].strip().rstrip(';') if r['note'] else '',
    } for r in rows_sorted])
    st_mod.dataframe(df, use_container_width=True, hide_index=True)

    # 逐檔體質變化明細(🟢變好 / 🔴變差 逐項)——合併原「MJ 體檢轉機」下鑽,吃同一份 diff_verdict
    _diffable = [r for r in rows_sorted if r.get('diff_verdict') is not None]
    if _diffable:
        with st_mod.expander('🔍 逐檔體質變化明細（🟢變好 / 🔴變差 逐項；找體質差→變好）',
                             expanded=False):
            for r in _diffable:
                v = r['diff_verdict']
                _ic = f'　{r["turn_icon"]}' if r.get('turn_icon') else ''
                st_mod.markdown(
                    f"**{r['sid']}**：改善 {getattr(v, 'improve_count', 0)} / "
                    f"惡化 {getattr(v, 'deteriorate_count', 0)}{_ic}")
                for _title, _items in (('🟢 變好', getattr(v, 'improvements', None) or []),
                                       ('🔴 變差', getattr(v, 'deteriorations', None) or [])):
                    if _items:
                        st_mod.markdown(f'{_title}（{len(_items)} 項）')
                        st_mod.dataframe(pd.DataFrame([{
                            '模組': m.module.replace('_Module', ''), '指標': m.metric,
                            '上期': m.prev_status, '本期': m.curr_status,
                        } for m in _items]), use_container_width=True, hide_index=True)

    with st_mod.expander('🛠️ 逐檔細節（分子分數推導）', expanded=False):
        for r in rows_sorted:
            st_mod.markdown(f"**{r['sid']}**：{r['label']}（合分 {r['score']:.2f}）")
            st_mod.json({
                'monthly_detail': r.get('mon_detail', {}),
                'mj_detail': r.get('mj_detail', {}),
            })
