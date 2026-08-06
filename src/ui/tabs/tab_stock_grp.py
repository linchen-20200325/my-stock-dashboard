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

    # ══ ② 輸入多檔代碼(v19.164 唯一來源:型態目標價 / 財報體質 / 三階段濾網全部吃這裡)═══
    # session_state-backed(供「帶入持股」回填;不用 value= 避免 widget 衝突警告)
    if 'multi_input' not in st.session_state:
        st.session_state['multi_input'] = '2330 2454 2317 2382 3017 2308 2303 2376 6669 3661'
    with st.container(border=True):
        t3c1, t3c2 = st.columns([4, 1])
        with t3c1:
            multi_input = st.text_area(
                '輸入多檔代碼（逗號/空格/換行，最多10檔）— 型態目標價 / 財報體質 / 三階段濾網全部吃這一組',
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
                   '　·　按「🚀 批次分析」一鍵串跑：排行總表 + 型態目標價 + 財報趨勢×轉機 + 三階段濾網')
    elif t3_run_btn:
        st.warning('⚠️ 請先在上方輸入至少一個有效股票代碼，再按「🚀 批次分析」')

    # ══ ②b 個股組合雲端儲存(Phase 1 個股/ETF 分家:專屬 stock_portfolio_sheet_id)══
    _render_stock_cloud_storage(stock_list_t3)

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
    # ══ 📊 財報趨勢分數（v18.189）+ 🎯 三階段濾網（v19.58）═══════════
    # v18.223 一鍵化：吃 batch 跑完時鎖定的 codes（t3_batch_codes），自動跑財報趨勢 + picker + AI。
    # 不再依賴 stock_list_t3（避免 textarea 改動觸發重跑），改 textarea 後須按「批次分析」才更新。
    _batch_codes = st.session_state.get('t3_batch_codes')
    if _batch_codes:
        _bc_list = list(_batch_codes)
        _render_fin_trend_section(_bc_list, auto_run=True)
        # v18.453:轉傳批次財報體檢結果,讓 Stage 1 負債比檢查與其判定一致
        _render_stage_picker_section(_bc_list, auto_run=True, fh_map=_fh_t3_cached)
    elif stock_list_t3:
        st.info('💡 上方按「🚀 批次分析」會自動串跑 財報趨勢分數 + 三階段濾網 + AI 三型建議。')

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

    # v19.168 IMPL-B:移除冗餘的「🧬 AI 總結本頁」lite 卡 —— 本頁已有 🤖 AI 投資組合綜合判讀
    # 深報告(經理人強弱排序),泛用 lite 摘要重複。自由問答走獨立「🧬 AI 問答」tab。


def _grp_load_holdings_callback() -> None:
    """帶入**個股專屬** Google Sheet 純代碼觀察清單 → 填入上方唯一輸入框 multi_input(on_click)。

    v19.164 單一來源化:原「財報體檢轉機」獨立輸入框的帶入持股鈕搬來這裡,改填組合唯一輸入。
    Option B:改讀個股專屬 sheet 的 `stock_watchlist` **純代碼清單**(name/ticker/updated_at,
    無張數/均價/哨兵),取代原本借 `portfolios` schema + 哨兵假價的路徑(§1 反捏造)。
    Phase 1 個股/ETF 分家:只讀個股專屬 sheet(`stock_portfolio_sheet_id`),不借 ETF 的
    `portfolio_sheet_id`(修 user 回報「帶入我的持股卻拉到 ETF 組合資料」)。
    §8.2.A EX-PASSTHRU-1:L5 lazy import L1 gsheet_portfolio(pass-through、無 L3 業務值)。
    §1 fail-loud:未設個股 sheet → 只回 warn 指引去下方面板設定,**不**靜默 fallback ETF sheet。
    graceful:未登入 Google / 讀取失敗 → 只回 warn,不炸。
    """
    try:
        from src.data.portfolio import gsheet_portfolio as _gsp  # EX-PASSTHRU-1
        stock_sid = _gsp._get_active_stock_sheet_id()
        if not stock_sid:  # §1:不靜默借用 ETF sheet
            st.session_state['_grp_holdings_msg'] = (
                'warn', '個股組合尚未設定雲端 Sheet — 請在下方「☁️ 個股組合雲端儲存」挑選或新建')
            return
        names = _gsp.list_stock_watchlists(sheet_id=stock_sid)
        if not names:
            st.session_state['_grp_holdings_msg'] = (
                'warn', '個股 Sheet 內還沒有代碼清單 — 請先到下方「☁️ 個股組合雲端儲存」存一組。')
            return
        tickers: list[str] = []
        for _nm in names:
            for _t in (_gsp.load_stock_watchlist(_nm, sheet_id=stock_sid) or []):
                _t = str(_t).strip()
                if _t and _t not in tickers:
                    tickers.append(_t)
        if not tickers:
            st.session_state['_grp_holdings_msg'] = ('warn', '個股清單是空的。')
            return
        capped = tickers[:10]  # 批次上限 10(parse_stocks 對齊)
        st.session_state['multi_input'] = ' '.join(capped)
        _tail = f'(共 {len(tickers)} 檔,取前 10)' if len(tickers) > 10 else f'(共 {len(tickers)} 檔)'
        st.session_state['_grp_holdings_msg'] = ('ok', f'已帶入持股 {_tail}:{" ".join(capped)}')
    except Exception as _e:  # noqa: BLE001 — 帶入失敗不炸 UI
        st.session_state['_grp_holdings_msg'] = (
            'warn', f'帶入持股失敗:{type(_e).__name__}(可能未登入 Google / 未設定組合)')


def _render_stock_cloud_storage(stock_list: list[str]) -> None:
    """☁️ 個股組合雲端儲存(獨立於 ETF 組合)— 存/讀**純代碼清單**到**專屬** Google Sheet。

    Option B(§1 反捏造):存的是 `stock_watchlist` 分頁的純代碼清單(name/ticker/updated_at),
    **不寫**任何張數/均價/哨兵假價;與 ETF 的 `portfolios`(5 欄含價格)物理隔離。
    Phase 1 個股/ETF 分家:本面板**只**操作 `stock_portfolio_sheet_id` session channel,
    絕不碰 ETF 的 `portfolio_sheet_id`,避免「帶入我的持股」誤拉 ETF 組合。

    §8.2.A EX-PASSTHRU-1:L5 lazy import L1 gsheet_portfolio + OAuth 原語(pass-through、
    無 L3 業務值;L1 內已 @st.cache/OAuth 集中緩存)。**不** reuse ETF 的 `_render_oauth_panel`
    ——那支寫死 `portfolio_sheet_id`,借用會污染 ETF sheet;改用同一批 OAuth 原語自建精簡版
    (§8.1 step 6:避免為重用而引入會破壞 ETF 的耦合)。
    §1:未設個股 sheet → 提示挑選/新建,不靜默借 ETF sheet。
    """
    import re

    from src.data.portfolio import gsheet_portfolio as _gsp  # EX-PASSTHRU-1

    with st.expander('☁️ 個股組合雲端儲存（獨立於 ETF 組合）', expanded=False):
        st.caption('把上方輸入的個股清單存成命名組合到**你自己的** Google Sheet;'
                   '之後按「🔗 帶入我的持股」即可一鍵回填。'
                   '此 Sheet **獨立於 ETF 組合**,兩邊互不污染。')

        # ── OAuth 登入狀態(reuse 原語,不重造 OAuth 邏輯)──────────────
        _logged_in = bool(st.session_state.get('gsheet_tokens'))
        _oauth_cfg = None
        _build_url = None
        _login_state = None
        try:
            from src.data.portfolio.oauth_state import get_login_state, get_oauth_cfg
            from infra.oauth import build_authorize_url
            _oauth_cfg = get_oauth_cfg()
            _build_url = build_authorize_url
            _login_state = get_login_state
        except Exception as _ie:  # noqa: BLE001 — OAuth 模組缺席仍可走 URL/ID 手貼
            st.caption(f'（OAuth 模組未就緒:{type(_ie).__name__} — 仍可手貼 Sheet URL/ID）')

        if _logged_in:
            _email = st.session_state.get('gsheet_email', '')
            st.success(f'🟢 已用 Google 登入{("：" + _email) if _email else ""}')
        elif _oauth_cfg and _build_url and _login_state:
            _url = _build_url(_oauth_cfg['client_id'], _oauth_cfg['redirect_uri'],
                              state=_login_state())
            st.info('ℹ️ 尚未登入 Google — 登入後可一鍵新建個股專屬 Sheet(或直接手貼下方 URL/ID)。')
            st.link_button('🔐 用 Google 登入', _url, use_container_width=True)
        # (SA 模式:無 OAuth cfg 也無登入 → 直接用下方 URL/ID 輸入即可)

        # ── 設定個股 sheet(URL/ID 手貼,OAuth+SA 皆可;regex 同 ETF sidebar)──
        _stock_sid = _gsp._get_active_stock_sheet_id()
        _raw = st.text_input(
            '個股 Google Sheet ID 或完整 URL(系統自動解析 ID)',
            value=_stock_sid, key='stock_grp_sheet_id_input',
            placeholder='貼上 https://docs.google.com/spreadsheets/d/...')
        _m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', _raw)
        _new_sid = _m.group(1) if _m else _raw.strip()
        # 只在「輸入框本次真的被改動」時才套用 → 避免下方 Drive 挑檔選定後,rerun 時
        # 殘留的舊輸入框值把剛選的 sheet 蓋回去(同面板兩處設 sheet 的競態,§1 不誤改)。
        if _raw != st.session_state.get('_stock_grp_prev_raw'):
            st.session_state['_stock_grp_prev_raw'] = _raw
            if _new_sid and _new_sid != _stock_sid:
                st.session_state[_gsp.STOCK_PORTFOLIO_SHEET_KEY] = _new_sid
                _stock_sid = _new_sid

        # ── 從 Drive 挑既有 Sheet(OAuth 限定;mirror ETF etf_tab_portfolio 挑選器)──
        # §8.2.A EX-PASSTHRU-1:L5 lazy 直呼 L1 list_user_folders/list_user_sheets
        # (pass-through、OAuth-gated、L1 內已集中緩存)。§1:列檔失敗 → 誠實報錯
        # (沿用 ETF 面板同款 403/中繼權限不足 引導文案),不捏造/回假 Sheet 清單。
        # 選定後寫入**個股** channel STOCK_PORTFOLIO_SHEET_KEY(絕不碰 ETF 的
        # portfolio_sheet_id)。widget key 一律 stock_grp_ 前綴、stash key 一律
        # _stock_grp_ 前綴,與 ETF 面板 etf_p_* keys 物理隔離,永不碰撞。
        if _logged_in:
            st.caption('📂 **或者** — 從你 Google Drive 既有的 Sheets 挑一個'
                       '（可選擇限定資料夾）:')

            # 資料夾下拉:先列出所有資料夾讓使用者挑(取代手貼 URL)
            _fbc1, _fbc2 = st.columns([2, 3])
            if _fbc1.button('🔄 載入資料夾清單',
                            key='stock_grp_load_folders',
                            use_container_width=True,
                            help='點一次抓 Drive 內所有資料夾;之後下方下拉就能選'):
                try:
                    _folders_ls = _gsp.list_user_folders()
                    st.session_state['_stock_grp_my_folders'] = _folders_ls
                    if not _folders_ls:
                        st.info('ℹ️ Drive 內沒有資料夾,或 token 缺 '
                                '`drive.metadata.readonly` 權限')
                except Exception as _fle:  # noqa: BLE001 — 列資料夾失敗顯示不炸
                    _err = str(_fle)
                    if 'insufficient' in _err.lower() or '403' in _err:
                        st.error('❌ 列資料夾失敗:OAuth token 缺中繼權限。'
                                 '左 sidebar「🚪 登出」→ 重新登入即可。')
                    else:
                        st.error(f'❌ 列資料夾失敗:{_fle}')

            _my_folders = st.session_state.get('_stock_grp_my_folders') or []
            _folder_options = [('', '🌐 整個帳號（不限資料夾）')] + [
                (f['id'], f"📁 {f['name']}  (`{f['id'][:10]}…`)") for f in _my_folders]
            _cur_folder_id = str(st.session_state.get('_stock_grp_drive_folder', '') or '')
            try:
                _cur_idx = next(i for i, (fid, _) in enumerate(_folder_options)
                                if fid == _cur_folder_id)
            except StopIteration:
                _cur_idx = 0
            _sel_folder_idx = st.selectbox(
                '📁 限定資料夾（可選）',
                range(len(_folder_options)),
                index=_cur_idx,
                format_func=lambda i: _folder_options[i][1],
                key='stock_grp_drive_folder_sel',
                help='留空 = 列整個帳號;或先點「🔄 載入資料夾清單」抓 Drive 資料夾後挑一個')
            _folder_id = _folder_options[_sel_folder_idx][0]
            st.session_state['_stock_grp_drive_folder'] = _folder_id

            if st.button('📂 從 Drive 列出 Sheets',
                         key='stock_grp_list_drive', use_container_width=True,
                         help='需要 OAuth `drive.metadata.readonly` 權限;若顯示權限不足請登出再登入'):
                try:
                    _files_ls = _gsp.list_user_sheets(folder_id=_folder_id)
                    st.session_state['_stock_grp_my_sheets'] = _files_ls
                    st.session_state['_stock_grp_list_tried'] = True
                    _scope_name = _folder_options[_sel_folder_idx][1].lstrip(
                        '📁🌐 ').split('  (')[0]
                    st.session_state['_stock_grp_list_scope'] = _scope_name
                except Exception as _lse:  # noqa: BLE001 — 列檔失敗顯示不炸
                    _err = str(_lse)
                    if 'insufficient' in _err.lower() or '403' in _err:
                        st.error('❌ 列檔失敗:OAuth token 缺少 `drive.metadata.readonly` 權限。\n\n'
                                 '**解法**:左 sidebar 先「🚪 登出」→ 重新「🔐 用 Google 登入」'
                                 '(這次同意畫面會多一條 Drive 中繼權限)→ 再回來點列檔。')
                    else:
                        st.error(f'❌ 列檔失敗:{_lse}')

            _my_sheets = st.session_state.get('_stock_grp_my_sheets') or []
            _list_scope = st.session_state.get('_stock_grp_list_scope', '')
            if _my_sheets:
                _opt_labels = [f"📄 {f['name']}  (`{f['id'][:14]}…`)" for f in _my_sheets]
                _scope_hint = f'（來源:{_list_scope}）' if _list_scope else ''
                _sel_idx = st.selectbox(
                    f'清單共 {len(_my_sheets)} 個 Sheets — 選一個 {_scope_hint}',
                    range(len(_opt_labels)),
                    format_func=lambda i: _opt_labels[i],
                    key='stock_grp_sel_my_sheets',
                )
                if st.button('✅ 使用此 Sheet 作為個股資料庫',
                             key='stock_grp_pick_my_sheet',
                             type='primary', use_container_width=True):
                    _picked = _my_sheets[_sel_idx]
                    st.session_state[_gsp.STOCK_PORTFOLIO_SHEET_KEY] = _picked['id']
                    st.success(f"✅ 已選用 `{_picked['name']}`")
                    st.rerun()
            elif st.session_state.get('_stock_grp_list_tried'):
                st.warning(
                    '⚠️ Drive 列檔回空 — 通常代表 OAuth token 是舊版發的'
                    '(只授了 `drive.file` scope,只能看本 app 建立的檔)。\n\n'
                    '**兩個解法擇一**:\n'
                    '1. 左 sidebar「🚪 登出」→ 重新「🔐 用 Google 登入」拿完整中繼權限\n'
                    '2. 直接用下方「🆕 建立個股專屬 Sheet」一鍵建一本'
                    '(用 `drive.file` 就可以,免重登)')

        # ── 一鍵新建個股專屬 Sheet(OAuth 限定;reuse L1 create_new_sheet)──
        if _logged_in:
            _nc1, _nc2 = st.columns([3, 2])
            _new_title = _nc1.text_input(
                '新 Sheet 名稱', value='台股 Dashboard - 個股組合',
                key='stock_grp_new_sheet_title', label_visibility='collapsed',
                placeholder='台股 Dashboard - 個股組合')
            if _nc2.button('🆕 建立個股專屬 Sheet', key='stock_grp_create_sheet',
                           use_container_width=True):
                try:
                    _nid, _nurl = _gsp.create_new_sheet(
                        _new_title, folder_name=_gsp._STOCK_DRIVE_FOLDER_NAME)
                except Exception as _ce:  # noqa: BLE001 — 建立失敗顯示不炸
                    st.error(f'❌ 建立失敗:{_ce}')
                else:
                    st.session_state[_gsp.STOCK_PORTFOLIO_SHEET_KEY] = _nid
                    st.success(f'✅ 已建立並選用「{_new_title}」（已放入專屬資料夾）'
                               f' — [打開 Sheet]({_nurl})')
                    st.rerun()

        if not _stock_sid:  # §1:未設定 → 不繼續(不借 ETF sheet)
            st.info('💡 尚未設定個股專屬 Sheet — 貼上 URL/ID,或(登入後)按「🆕 建立個股專屬 Sheet」。')
            return
        st.caption(f'✅ 個股 Sheet ID:`{_stock_sid}`')
        st.markdown('---')

        # ── 儲存目前個股清單(純代碼清單,§1 無張數/均價/哨兵)──────────────
        st.markdown('**💾 儲存上方個股清單為命名代碼組合**')
        st.caption('個股組合是純「**代碼清單**」—— 只存代碼,不存張數/均價/任何價格。'
                   '按「💾 儲存」把上方唯一輸入框目前的代碼存成命名組合;'
                   '之後「🔗 帶入我的持股」時原樣讀回這組代碼。')
        if stock_list:
            st.caption(f'待存代碼（{len(stock_list)} 檔）:{" ".join(stock_list)}')
        _sc1, _sc2 = st.columns([3, 1])
        _name = _sc1.text_input('組合名稱', value='',
                                placeholder='例如:主力觀察 / 高股息 / 波段',
                                key='stock_grp_save_name')
        if _sc2.button('💾 儲存', key='stock_grp_save_btn',
                       use_container_width=True,
                       disabled=(not _name.strip() or not stock_list)):
            try:
                _n = _gsp.save_stock_watchlist(_name, list(stock_list),
                                               sheet_id=_stock_sid)
            except Exception as _e:  # noqa: BLE001 — 儲存失敗顯示不炸
                st.error(f'❌ 儲存失敗:{_e}')
            else:
                st.success(f'✅ 已儲存「{_name}」共 {_n} 檔代碼到個股 Sheet')
        if not stock_list:
            st.caption('💡 上方唯一輸入框尚無有效代碼 —— 先輸入至少一檔再存。')

        st.markdown('---')

        # ── 載入/列出既有個股代碼清單(帶入上方唯一輸入框)──────────────
        st.markdown('**📂 載入既有個股代碼組合**（帶入上方唯一輸入框）')
        try:
            _names = _gsp.list_stock_watchlists(sheet_id=_stock_sid)
        except Exception as _e:  # noqa: BLE001 — 連線失敗顯示不炸
            st.error(f'❌ 無法連線個股 Sheet:{_e}')
            return
        if not _names:
            st.caption('💡 此個股 Sheet 尚無代碼組合 —— 先在上方存一組。')
            return
        _lc1, _lc2 = st.columns([3, 1])
        _sel = _lc1.selectbox('選擇組合', options=['—'] + _names,
                              key='stock_grp_load_sel')
        if _lc2.button('📂 載入', key='stock_grp_load_btn',
                       use_container_width=True, disabled=(_sel == '—')):
            try:
                _tks = _gsp.load_stock_watchlist(_sel, sheet_id=_stock_sid)
            except Exception as _e:  # noqa: BLE001 — 載入失敗顯示不炸
                st.error(f'❌ 載入失敗:{_e}')
            else:
                if not _tks:
                    st.warning(f'⚠️ 組合「{_sel}」是空的')
                else:
                    _capped = _tks[:10]
                    st.session_state['multi_input'] = ' '.join(_capped)
                    st.success(f'✅ 已載入「{_sel}」{len(_tks)} 檔,帶入上方輸入框:{" ".join(_capped)}')
                    st.rerun()


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
    與 _render_fin_trend_section 互補：財報趨勢分數看「最近 3 月/3 季的進步退步」，
    三階段濾網看「當下是否進場（基本面 9 項 ＋ 籌碼技術 6 項 ＋ AI 三型建議）」。
    共用 data_loader.fetch_financial_statements + financial_health_engine（與財報體檢同源）。

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


def _render_fin_trend_section(stock_list: list[str], *,
                              auto_run: bool = False) -> None:
    """v18.189 個股組合內「財報趨勢分數」區塊（v19.174 去識別化改名）。

    v18.223：auto_run=True 串接「批次分析」一鍵流程（移除手動按鈕，自動跑全程 + cache）。
    對 stock_list 每檔合議「近 3 月月營收動能」+「近 3 季財報體檢 status delta」
    產出 5 段判定（🚀 強進步 / 📈 進步 / ➖ 中性 / 📉 退步 / 🔻 強退步）。
    月權重 65%（先行）/ 季權重 35%（落後但見品質）。
    """
    import pandas as pd
    from datetime import date

    import streamlit as _st  # noqa: F811 — explicit local alias
    from src.config import FINMIND_TOKEN as _TOK
    from src.services.stock_grp_service import get_financial_statements as fetch_financial_statements  # R1 v18.405
    from src.services import analyze_financial_health
    from src.compute.health import diff_fin_health  # noqa: F401 — used transitively by score（v19.174 去識別化）
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
        '📊 財報趨勢 × 轉機（找體質差→變好）</span>'
        '<span style="font-size:11px;color:#8b949e;margin-left:8px;">'
        '月營收動能 × 季財報體檢 · 65/35 合議 · 併入本業虧轉盈 🌟 / 盈轉虧 ⚠️ 轉機偵測</span></div>',
        unsafe_allow_html=True,
    )
    _st.caption(
        '🔰 **判定規則**：≥+1.5 🚀 強進步 / +0.5~+1.5 📈 進步 / -0.5~+0.5 ➖ 中性 / '
        '-1.5~-0.5 📉 退步 / ≤-1.5 🔻 強退步。'
        '**月權重高**因月營收 10 日公布（先行指標），季財報 45 天遞延（落後但見獲利品質）。'
        '近 3 季財報快照不足時自動補抓本季快照。'
        '**「轉機」欄** = 用同一份季財報快照判本業虧轉盈(🌟)/盈轉虧(⚠️),零額外抓取。'
        '**月營收與季快照皆缺 → 標「⚪ 無法評分」**(分數 0.0 只是預設值,不是「持平」),'
        '不進 5 段計數也不參與排序(§1)。'
    )

    # v18.223：auto_run 模式移除手動按鈕；slider 保留以利使用者觀察/調整權重
    _w_mon = _st.slider(
        '月營收權重',
        min_value=0.4, max_value=0.9, value=0.65, step=0.05,
        key='_fin_trend_w_mon',
        help='月營收動能占比，季財報自動 = 1 - 此值。改動後下次按「批次分析」生效。',
    )

    if not auto_run:
        # v19.176 P0-A(§1 Fail Loud, Never Fake — 文案不得與 code 行為矛盾):
        # 舊文案給了一個憑空的固定秒數區間(上界 60 秒),但下方 L609-620 是**逐檔序列**
        # 迴圈(for sid in stock_list → compute_one_stock_trend,每檔都打 FinMind),
        # 耗時隨檔數線性成長且**無全域逾時上限** —— 30 檔的組合不可能 60 秒跑完。
        # 給結構性描述 + 指向真正的進度來源(進度條),比給一個必然說謊的數字誠實。
        _st.caption(
            '💡 上方按「🚀 批次分析」自動跑 財報趨勢分數。'
            '首次為**逐檔序列**抓 FinMind（無全域逾時上限），耗時隨檔數線性成長；'
            '開始後上方會出現「[N/總數] 趨勢計算中」進度條 —— 以進度條是否前進'
            '判斷是否仍在執行，不要用秒數猜。'
        )
        return

    if not _TOK:
        _st.error('🔴 未設定 `FINMIND_TOKEN` → 無法抓財報與月營收')
        return

    yyyymm_curr = current_finmind_yyyymm(date.today())
    # v18.223 cache 防 rerun 重跑（key 含 codes + 權重 + 當前季）
    _fin_cache_key = (
        f'_fin_trend_rows_{hash(tuple(stock_list))}_'
        f'{round(float(_w_mon) * 100)}_{yyyymm_curr}'
    )
    rows = _st.session_state.get(_fin_cache_key)
    if rows is None:
        rows = []
        prog = _st.progress(0.0, text=f'財報趨勢分數中 {len(stock_list)} 檔...')
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
        _st.session_state[_fin_cache_key] = rows

    _render_fin_trend_table(rows, pd, _st, yyyymm_curr)


_TREND_SORT_ORDER = {
    'strong_down': 0, 'down': 1, 'neutral': 2,
    'up': 3, 'strong_up': 4, 'error': 5,
}

# v19.164 稽核補回:「純季財報體質」verdict(與月+季混合的趨勢分數不同)。
# 一檔可能月營收強 → 混合趨勢分顯示「📈 進步」,但季財報 verdict 其實是「🔴 退步」——
# 兩者必須並列,否則「找體質差」的能力會被月營收動能蓋掉(對抗式稽核 90f5ca9 抓到的損失)。
_FIN_VERDICT_LABEL = {   # v19.174 去識別化：原 _MJ_VERDICT_LABEL
    'improving': '🟢 進步', 'deteriorating': '🔴 退步', 'mixed': '🟡 分歧',
    'stable': '⚪ 不變', 'first_snapshot': '⏳ 首季', 'fetch_failed': '❌ 失敗',
    # B5-b:0 季快照 ≠「首季」。首季 = 有 1 季但無法 diff;無快照 = 根本沒抓到。
    'no_snapshot': '⬜ 無季快照',
}

# 無法評分列在表格數值欄的顯示字元(§1:不用 0.00 冒充「持平」)
_UNSCORABLE_CELL = '—'


def _fin_verdict_code(r: dict) -> str:
    """取一列的『純季財報 verdict』代碼(非月+季混合趨勢分;來自 diff_fin_health)。"""
    v = r.get('diff_verdict')
    if v is not None:
        return getattr(v, 'verdict', 'first_snapshot') or 'first_snapshot'
    if r.get('label_code') == 'error':
        return 'fetch_failed'
    # 無 diff_verdict:有 ≥1 季快照 → 首季(還不能 diff);0 季 → 無快照(§1 兩者不同義)
    from src.compute.screener.scorability import trend_row_evidence
    return 'first_snapshot' if trend_row_evidence(r)[1] >= 1 else 'no_snapshot'


def _fmt_quarter(yyyymm: str) -> str:
    """202503 → 2025Q1（季底月份對應季）；格式不符回原字串。"""
    s = str(yyyymm or '').strip()
    if len(s) != 6 or not s.isdigit():
        return s or '—'
    q = {'03': 'Q1', '06': 'Q2', '09': 'Q3', '12': 'Q4'}.get(s[4:6], s[4:6])
    return f'{s[:4]}{q}'


def _render_fin_trend_table(rows: list[dict], pd, st_mod, yyyymm_curr: str = '') -> None:
    """渲染結果表（退步在前）+ 統計 KPI。

    B5-b(2026-08)§1:「月營收缺 + 季快照不足」時 `compute_trend_score` 回 score=0.0,
    而 0.0 正好落在「➖ 中性」帶(±0.5)正中央 —— 沒資料被講成「持平」,還進 KPI 計數
    與排序。改用 `scorability.split_trend_rows` 把這種列切出來標「⚪ 無法評分」,
    數值欄一律 `—`,不進 5 段判定計數、排在表尾。
    """
    if not rows:
        return
    from src.compute.screener.scorability import split_trend_rows
    _scorable, _unscorable = split_trend_rows(rows)

    cnt = {k: 0 for k in _TREND_SORT_ORDER}
    for r in _scorable:
        _lc = r.get('label_code')
        cnt[_lc] = cnt.get(_lc, 0) + 1
    cols = st_mod.columns(6)
    cols[0].metric('🔻 強退步', cnt.get('strong_down', 0))
    cols[1].metric('📉 退步', cnt.get('down', 0))
    cols[2].metric('➖ 中性', cnt.get('neutral', 0))
    cols[3].metric('📈 進步', cnt.get('up', 0))
    cols[4].metric('🚀 強進步', cnt.get('strong_up', 0))
    cols[5].metric('⚪ 無法評分', len(_unscorable),
                   help='月營收與季財報快照皆缺 → 分數 0.0 只是預設值,'
                        '不代表「持平」;已排除於左側 5 段計數與排序之外(§1)')
    st_mod.caption(f'↑ 上列＝月營收動能 × 季財報「**混合**」趨勢分(月 65% / 季 35%),'
                   f'分母為**可評分的 {len(_scorable)} 檔**(共 {len(rows)} 檔)。　'
                   '↓ 下列＝**純季財報體質** verdict(只看季度,不混月營收)——'
                   '兩者可能相反(月強但季退),分開看才不會漏掉「財報體質在惡化」。')
    if _unscorable:
        st_mod.warning(
            f'⚪ {len(_unscorable)} 檔無法評分(月營收與季快照皆缺,非「中性」):'
            + '、'.join(str(r.get('sid', '?')) for r in _unscorable))

    # v19.164 稽核補回:純季財報 verdict 計數(組合層「幾檔財報體質在惡化」一眼看)
    _finv = {k: 0 for k in _FIN_VERDICT_LABEL}
    for r in rows:
        _finv[_fin_verdict_code(r)] = _finv.get(_fin_verdict_code(r), 0) + 1
    mcols = st_mod.columns(7)
    mcols[0].metric('🔴 財報退步', _finv['deteriorating'])
    mcols[1].metric('🟡 分歧', _finv['mixed'])
    mcols[2].metric('🟢 財報進步', _finv['improving'])
    mcols[3].metric('⚪ 不變', _finv['stable'])
    mcols[4].metric('⏳ 首季', _finv['first_snapshot'])
    mcols[5].metric('⬜ 無季快照', _finv['no_snapshot'])
    mcols[6].metric('❌ 失敗', _finv['fetch_failed'])

    # v18.199 ── 📊 快照新鮮度條（季財報分來自哪季 — 防補抓失敗靜默沿用舊季）──
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
        f'<b style="color:{_fc};">📊 季財報快照新鮮度</b>　'
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

    # 排序:可評分列依 5 段(退步在前);無法評分列一律排到最後(§1 不與真分數混排)
    _unscorable_ids = {id(r) for r in _unscorable}
    rows_sorted = sorted(
        rows,
        key=lambda r: (1 if id(r) in _unscorable_ids else 0,
                       _TREND_SORT_ORDER.get(r.get('label_code'), 99)))

    # 🌟/⚠️ 轉機摘要(v19.164 合併「財報體檢轉機」)——user 要的「找體質差→變好」在這裡,
    # 判定由 compute_one_stock_trend 用同一份季快照附帶算出(turn_icon / diff_verdict),零額外抓取。
    _turn = [r['sid'] for r in rows_sorted if str(r.get('turn_icon', '')).startswith('🌟')]
    _break = [r['sid'] for r in rows_sorted if str(r.get('turn_icon', '')).startswith('⚠️')]
    if _turn:
        st_mod.success(f'🌟 **本業虧轉盈轉機股**：{", ".join(_turn)} —— 「體質差→變好」看這裡')
    if _break:
        st_mod.error(f'⚠️ **本業盈轉虧雷股**：{", ".join(_break)}')

    def _trend_row(r: dict) -> dict:
        """一列的表格 cell。§1:無法評分 → 判定/分數欄一律 `—`,不印 0.00。"""
        _bad = id(r) in _unscorable_ids
        return {
            '代碼': r['sid'],
            '判定(月+季)': '⚪ 無法評分' if _bad else r['label'],
            '季財報體質': _FIN_VERDICT_LABEL.get(_fin_verdict_code(r), '—'),  # 純季度 verdict(補回)
            '轉機': r.get('turn_icon') or '—',
            '綜合分數': _UNSCORABLE_CELL if _bad else f"{r['score']:.2f}",
            '月營收分': _UNSCORABLE_CELL if _bad else f"{r['mon_sub']:.2f}",
            '季財報分': _UNSCORABLE_CELL if _bad else f"{r['fin_sub']:.2f}",  # v19.174:改吃中性 key
            '季別': _quarter_cell(r),
            '備註': r['note'].strip().rstrip(';') if r['note'] else '',
        }

    df = pd.DataFrame([_trend_row(r) for r in rows_sorted])
    st_mod.dataframe(df, use_container_width=True, hide_index=True)

    # 逐檔體質變化明細(🟢變好 / 🔴變差 逐項)——合併原「財報體檢轉機」下鑽,吃同一份 diff_verdict
    _diffable = [r for r in rows_sorted if r.get('diff_verdict') is not None]
    if _diffable:
        with st_mod.expander('🔍 逐檔體質變化明細（🟢變好 / 🔴變差 逐項；找體質差→變好）',
                             expanded=False):
            for r in _diffable:
                v = r['diff_verdict']
                _ic = f'　{r["turn_icon"]}' if r.get('turn_icon') else ''
                _net = int(getattr(v, 'net_delta', 0) or 0)
                _vlabel = _FIN_VERDICT_LABEL.get(_fin_verdict_code(r), '')
                st_mod.markdown(
                    f"**{r['sid']}**　{_vlabel}　改善 {getattr(v, 'improve_count', 0)} / "
                    f"惡化 {getattr(v, 'deteriorate_count', 0)} / "
                    f"淨變化 {_net:+d}{_ic}")   # 淨變化(補回)
                for _title, _items in (('🟢 變好', getattr(v, 'improvements', None) or []),
                                       ('🔴 變差', getattr(v, 'deteriorations', None) or [])):
                    if _items:
                        st_mod.markdown(f'{_title}（{len(_items)} 項）')
                        st_mod.dataframe(pd.DataFrame([{
                            '模組': m.module.replace('_Module', ''), '指標': m.metric,
                            '上期': m.prev_status, '本期': m.curr_status,
                        } for m in _items]), use_container_width=True, hide_index=True)
                # ⚪ 不變逐項(補回;決策相關性低,收在巢狀展開)
                _unch = getattr(v, 'unchanged', None) or []
                if _unch:
                    with st_mod.expander(f'⚪ 不變（{len(_unch)} 項）', expanded=False):
                        st_mod.dataframe(pd.DataFrame([{
                            '模組': m.module.replace('_Module', ''), '指標': m.metric,
                            'Status': m.curr_status,
                        } for m in _unch]), use_container_width=True, hide_index=True)

    with st_mod.expander('🛠️ 逐檔細節（分子分數推導）', expanded=False):
        for r in rows_sorted:
            st_mod.markdown(f"**{r['sid']}**：{r['label']}（合分 {r['score']:.2f}）")
            st_mod.json({
                'monthly_detail': r.get('mon_detail', {}),
                'fin_detail': r.get('fin_detail', {}),   # v19.174:改吃中性 key
            })
