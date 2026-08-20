"""ETF 組合配置 TAB — 從 etf_dashboard.py 抽出（PR P2-B Phase 6-B）

依賴策略
========
- Top-level: streamlit
- 函式內 late import：
  * stdlib: numpy, pandas
  * etf_dashboard.py 內部 helper：
    _check_sector_exposure / _colored_box / _compute_etf_warroom_row
    / _plot_correlation / _plot_holdings_overlap / _render_weakness_table
    / _strategy_conclusion / build_holdings_overlap_matrix
    / compute_etf_weakness_row / fetch_etf_dividends / fetch_etf_holdings
    / fetch_etf_info / fetch_etf_price / macro_allocation_banner

去重歷史
========
- PR #6：刪 render_unified_decision 呼叫（與 etf_tab_ai.py「ETF AI 首席策略師」重疊）

呼叫端
======
- app.py 經 etf_dashboard re-export 取用
"""
from __future__ import annotations

import streamlit as st

from src.compute.etf import auto_role
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.signal_thresholds import (
    # F1 v19.184 §3.3：σ 位階說明文字（3σ / 2σ / 1σ / +2σ）原本是手抄，
    # 判定式在 `etf_helpers.classify_etf_quick_sigma` 讀這 5 個常數 →
    # 改了倍數只有燈會動、說明不會動。改由同一組常數插值。
    ETF_QUICK_SIGMA_CHEAP,
    ETF_QUICK_SIGMA_DISASTER,
    ETF_QUICK_SIGMA_OVERBOUGHT,
    ETF_QUICK_SIGMA_OVERSOLD,
    ETF_CORR_HIGH_THRESHOLD,
    # B5-a v19.180:持股 Overlap 的兩個門檻(`PORTFOLIO_OVERLAP_WEIGHT_THRESHOLD_PCT`
    # / `PORTFOLIO_OVERLAP_JACCARD_THRESHOLD_PCT`)改由 L2
    # `portfolio_gates.evaluate_overlap_gate` 依 method 自行取 SSOT —— 判定式與門檻
    # 住在同一處,UI 不再各拿一份自己比一次(比一次就多一個會漂移的地方)。
    # 本檔仍透過 `_ov_gate['threshold_pct']` 顯示實際採用的門檻。
    PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT,
    PORTFOLIO_STRESS_TEST_DROP_PCT,
    PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT,
    PORTFOLIO_VAR_95_PERCENTILE,
    PORTFOLIO_VAR_99_PERCENTILE,
    PORTFOLIO_VAR_MONTHLY_WARN_PCT,
    LAG_ALERT_STREAK_QUARTERS,   # 換股建議「連續輸盤季數」門檻 SSOT(與 asset_lag 燈號同源)
)
from shared.thresholds import YIELD_MID, YIELD_LOW

# B5-a v19.180:目標權重輸入欄名 SSOT(data_editor column_config / 解析 / 說明文案共用)。
TARGET_PCT_COL: str = '目標比例%'

# F1 v19.184 §3.3 — regime → 核/衛目標比例的**說明文字**
# ────────────────────────────────────────────────────────────────
# 原本這句話是手抄的字串常值:「多頭 60/40 / 中性 70/30 / 保守 80/20 / 空頭 85/15」。
# 真正的 SSOT 是 L2 `src/compute/strategy/portfolio_manager._CORE_RATIO`,
# 而那是**私有** dict(底線開頭)—— L5 直取私有符號是 §8.2.A.2 V-PICKER-PRIV-1 同款違憲。
# 解法:用該類別的 **public API**(`CoreSatelliteManager(...).core_ratio`)逐 regime 問一次。
# 零 L2 改動、零新常數,而且日後有人調 `_CORE_RATIO`,這句話會自己跟著改。
#
# regime 代碼 → 中文顯示名。⚠️ 中文名只是 UI label,**不是**判定依據;
# 代碼本身是 `market_regime` 的契約值(見 `shared/regime_arbiter.normalize_regime`)。
_REGIME_ZH_ORDER: tuple[tuple[str, str], ...] = (
    ('bull', '多頭'), ('neutral', '中性'), ('caution', '保守'), ('bear', '空頭'),
)


def _regime_core_sat_text() -> str:
    """「多頭 60/40 / 中性 70/30 / …」這句話，由 SSOT 現算。

    §1 Fail Loud：L2 取不到時**不回一個看起來合理的預設字串**（那等於把
    「60/40」這組數字重新捏造一次），而是明說讀不到、並在 log 留原因。
    """
    try:
        from src.compute.strategy import CoreSatelliteManager as _CSM_txt
    except Exception as _e_rt:   # noqa: BLE001
        print(f'[etf_tab_portfolio/regime_text] 讀不到 CoreSatelliteManager:'
              f'{type(_e_rt).__name__}: {_e_rt}')
        return '（讀不到 CoreSatelliteManager，目標比例暫無法顯示）'
    _parts = []
    for _rk, _zh in _REGIME_ZH_ORDER:
        # total_capital 只是為了合法建構（建構子要求 > 0），不影響 core_ratio。
        _m = _CSM_txt(1.0, regime=_rk)
        _parts.append(f'{_zh} {_m.core_ratio * 100:.0f}/{_m.satellite_ratio * 100:.0f}')
    return ' / '.join(_parts)


def _fetch_usdtwd_spot():
    """抓 USD/TWD 即期匯率 → `(rate, as_of, source)`;全失敗回 `(None, None, None)`。

    B1-a v19.179。**不新開抓取路徑**,只串既有的兩條 SSOT(§2.1):

    1. **主**:`src.data.macro.fetch_usdtwd_close`（`data_registry.py:389` 登錄的
       「USDTWD 匯率 / Yahoo / TWD=X」正式來源）—— 走 macro 的 NAS proxy 化
       Chart API,已含 §3.2 sanity [25,40] 過濾與 `source` / `fetched_at` provenance。
    2. **備**:`fetch_etf_price('TWD=X', period='5d')` —— 本檔 v19.64 原本就在用的
       yfinance 直抓路徑(保留為 fallback,不是新增)。

    §1:兩條都拿不到 → 回 None,由 caller 把美元持股排除並顯示 ⚠️,
    **絕不**回 1.0 或任何「估一個合理值」。

    §8.2:L5 直呼 L1 fetcher — 屬 §8.2.A `EX-PASSTHRU-1`(pass-through、L1 內
    已有 `@st.cache_data`)。**升級觸發條件**:若第二個 consumer 需要同一組匯率,
    本函式應上升為 L3 `src/services/fx_service.py`(現在只有投組頁用,先不做)。
    """
    import pandas as _pd_fx
    # ① macro SSOT(proxy + sanity + provenance)
    try:
        from src.data.macro import fetch_usdtwd_close
        _df = fetch_usdtwd_close(days_back=60)
        if _df is not None and not _df.empty:
            _last = _df.iloc[-1]
            _as_of = _pd_fx.to_datetime(_last['date']).strftime('%Y-%m-%d')
            return (float(_last['value']), _as_of,
                    str(_last.get('source') or 'Yahoo:TWD=X'))
    except Exception as _e_fx1:
        print(f'[etf_tab_portfolio/fx] macro fetch_usdtwd_close 失敗:'
              f'{type(_e_fx1).__name__}: {_e_fx1}')
    # ② 本檔既有 fallback(yfinance TWD=X)
    try:
        from src.data.etf.etf_fetch import fetch_etf_price as _fep
        _fx_df = _fep('TWD=X', period='5d')
        if _fx_df is not None and not _fx_df.empty and 'Close' in _fx_df.columns:
            _as_of = _pd_fx.to_datetime(_fx_df.index[-1]).strftime('%Y-%m-%d')
            return (float(_fx_df['Close'].iloc[-1]), _as_of, 'Yahoo:TWD=X:Close')
    except Exception as _e_fx2:
        print(f'[etf_tab_portfolio/fx] yfinance TWD=X fallback 失敗:'
              f'{type(_e_fx2).__name__}: {_e_fx2}')
    print('[etf_tab_portfolio/fx] ❌ USD/TWD 兩條來源皆失敗 → 美元持股將被排除(§1)')
    return (None, None, None)


def render_etf_portfolio(gemini_fn=None):
    # ─ Late imports（避免循環 import）─
    import numpy as np
    import pandas as pd
    # v18.438 hotfix:同 etf_tab_single 端 —— 原 `from etf_tab_single import (...)` 為錯誤/循環
    # 來源(這些 helper 實際在 etf_render(L4)/etf_calc(L2)/etf_fetch(L1),tab 從不 module-level
    # 提供)。改 import 真正 SSOT 來源(§8.2 downward;L1 fetcher 屬 EX-PASSTHRU-1)。
    from src.ui.render.etf_render import (   # 渲染類
        _check_sector_exposure, _colored_box, _plot_correlation,
        _plot_holdings_overlap, _render_weakness_table, render_etf_holdings,
        _strategy_conclusion, macro_allocation_banner,   # v19.174 去識別化改名
    )
    # v19.174 去識別化：策略代號常數（原本各 caller 傳人名字串）
    from src.ui.render.ui_widgets import (
        STRATEGY_TECHNICAL, STRATEGY_VALUATION,
    )
    from src.compute.etf.etf_calc import (   # 計算類
        _compute_etf_warroom_row, build_holdings_overlap_matrix,
        compute_etf_weakness_row,
    )
    from src.data.etf.etf_fetch import (     # 抓取類
        fetch_etf_dividends, fetch_etf_holdings, fetch_etf_info, fetch_etf_price,
    )
    # v18.335 PR-H3:壓力測試 + 年現金流彙整獨立函式 SSOT
    from src.compute.etf import calc_portfolio_stress_test
    from src.compute.etf import compute_etf_annual_cashflow

    # ── C1 v19.182:改吃 regime 唯一出口,移除捏造的 'neutral' 預設 ──────────────
    # （原本這裡先讀 `mkt_info` 只為了取 regime，取消後該變數在本函式已無其他
    #   讀取端，一併移除以免留下誤導性的「這頁有讀 mkt_info」痕跡。）
    # 原碼 `mkt_info.get('regime', 'neutral')` 有兩個問題:
    #   (a) `mkt_info['regime']` 是**趨勢面輸入**,不是總經結論 —— 總經紅綠燈判
    #       🔴 空頭防禦(健康分跌破門檻 / 外資期貨大額淨空)的那天,這裡照樣拿到
    #       'bull',於是下方「核心/衛星 vs regime 目標」用**多頭 60/40** 去比對,
    #       而同一頁最上方的配置橫幅卻已印「先控制股票曝險」;
    #   (b) 未載入時捏造 'neutral' → 整套核衛判定照跑,還會給出綠燈「符合建議」,
    #       而同頁橫幅寫「⬜ 總經未評估」(§1 Fail Loud:同頁自打臉)。
    # 現在未評估 → `regime=None` → 下方不建 CoreSatelliteManager → 目標比為 None
    # → `evaluate_core_satellite_gate` 走既有的 STATUS_UNKNOWN 分支誠實顯示
    #   「⚪ 無法判定：拿不到 regime 核心目標比」。
    from src.services.allocation_service import get_macro_regime as _get_macro_reg
    _macro_reg = _get_macro_reg()
    regime = _macro_reg['regime'] if _macro_reg['is_loaded'] else None
    macro_allocation_banner(regime)

    st.markdown('#### 📋 輸入持股組合')
    st.caption('💡 表格欄位：**股票代號 / 持有張數 / 平均買入價格 / 目標比例%（選填）**。'
               '系統自動：① 1 張 = 1000 股換算 ② 核心/衛星判讀 ③ 即時收盤價算現值、資本利得、已領配息。'
               '可用「+」新增列、勾選後 Del 刪除列。')
    with st.expander('💡 核心/衛星 · 再平衡 · 持股重疊（Overlap）是什麼？', expanded=False):
        st.markdown(
            '- **核心 / 衛星配置**：**核心**（追大盤市值型，佔多數、長期持有求穩）＋ **衛星**（高息/主題型，少量、求現金流或增強）。系統依代號自動判讀；**判不出來的代號會誠實標「未分類」並改判「無法判定」，不會硬塞進核心。**\n'
            '- **再平衡容忍偏離度**：當某檔實際權重偏離**你設定的目標比例**超過此 %，才建議調整 —— 避免頻繁交易產生成本。設 5% = 偏離超過 5 個百分點才動手。\n'
            '  - ⚠️ **沒填「目標比例%」就沒有偏離可算** —— 此時本檢查顯示「⚪ 無法判定」而非綠燈（拿現況當目標會讓偏離恆等於 0，那是「沒算」不是「已平衡」）。\n'
            '- **持股重疊（Overlap）**：兩檔 ETF 可能都重壓台積電 → 你以為分散、其實重複押注。Overlap 矩陣量化「成分股重疊度」，**>30% 代表分散效果打折**，宜換成低重疊的搭配。\n'
            '  - ⚠️ **台股 ETF 的成分股是中文股名、海外 ETF 是英文公司名**，兩者對不上 → 跨市場（如 0050 × VT）的重疊率**量不到**，會標「無法判定」而不是回報 0%。'
        )

    # ── 結構化表單輸入（取代 text_area）─────────────────────
    # P2 v19.202(user 指派「輸入持股組合分析移到戰情室」):輸入來源改**優先帶入
    # 📁 組合管理的真實持股**(戰情室 bridge 寫入 etf_portfolio_rows),解稽核發現的
    # 「手打範例列與持股脫節 → 工具鏈空轉」。未載入時才退回範例列供試玩。
    # ⚠️ Streamlit data_editor 帶 key 後,使用者一旦編輯即以 widget state 為準,此 seed
    # 僅影響「該持股組首次渲染」;要重帶最新持股用下方 🔄 以持股組簽章重置 editor key。
    _pf_seed = [r for r in (st.session_state.get('etf_portfolio_rows') or [])
                if isinstance(r, dict) and r.get('ticker')
                and r.get('lots') and r.get('avg_price')]
    if _pf_seed:
        _default_df = pd.DataFrame({
            '股票代號':     [r['ticker'] for r in _pf_seed],
            '持有張數':     [float(r['lots']) for r in _pf_seed],
            '平均買入價格': [float(r['avg_price']) for r in _pf_seed],
        })
        st.caption(f'✅ 已帶入 📁 組合管理的持股（{len(_pf_seed)} 檔;可微調,目標比例仍需自填）。')
    else:
        st.caption('（📁 組合管理未載入 → 表格開在範例列。先到 💼 我的持股戰情室 / 📁 組合管理 '
                   '載入持股,即可自動帶入真實部位。）')
        _default_df = pd.DataFrame({
            '股票代號':       ['0050.TW', '00713.TW', 'BND', '00878.TW'],
            '持有張數':       [1.0, 0.5, 0.2, 2.0],
            '平均買入價格':   [135.50, 82.30, 72.50, 20.10],
        })
    # B5-a v19.180:再平衡的「目標」必須由使用者給。原碼拿現況當目標 → 偏離恆 0 →
    # 永遠印「✅ 無需再平衡」(§1 假綠燈)。選填欄:留白 = 明說「沒設定」而非 0。
    # 表格只帶 3 欄(代號/張數/均價),故一律在此補齊目標比例欄,避免 KeyError。
    if TARGET_PCT_COL not in _default_df.columns:
        # NaN（非 0！）= 空白格。NumberColumn 對 float64 的 NaN 顯示空白,
        # 解析端把 NaN 判成「沒填」→ 不會被誤當「目標 0%」。
        _default_df[TARGET_PCT_COL] = pd.Series(
            [float('nan')] * len(_default_df), dtype='float64')
    # editor key 綁「持股組簽章」→ 從 📁 組合管理重新載入(持股變動)時 editor 以新持股重 seed;
    # 同一持股組內的手動微調照常保留(key 不變)。無 seed(範例列)→ 固定 'example'。
    import hashlib as _hl_pf
    _sig_raw = ('|'.join(f"{r['ticker']}:{float(r['lots']):g}:{float(r['avg_price']):g}"
                         for r in _pf_seed) if _pf_seed else 'example')
    _editor_sig = _hl_pf.md5(_sig_raw.encode()).hexdigest()[:10]
    edited_df = st.data_editor(
        _default_df, num_rows='dynamic', hide_index=True,
        use_container_width=True, key=f'etf_p_table_{_editor_sig}',
        column_config={
            '股票代號':     st.column_config.TextColumn(
                '股票代號', required=True, width='medium',
                help='台股加 .TW / .TWO 後綴；海外 ETF 直接代號（如 BND、VOO）'),
            '持有張數':     st.column_config.NumberColumn(
                '持有張數', required=True, min_value=0.0, format='%.2f', width='small',
                help='台股 1 張 = 1000 股；可填小數（如 0.2 張 = 200 股）'),
            '平均買入價格': st.column_config.NumberColumn(
                '平均買入價格', required=True, min_value=0.0, format='%.2f', width='small',
                help='你過去買入此檔的成本均價'),
            TARGET_PCT_COL: st.column_config.NumberColumn(
                TARGET_PCT_COL, required=False, min_value=0.0, max_value=100.0,
                format='%.1f', width='small',
                help='選填。你希望這一檔佔組合的比例（各檔加總 100%）。'
                     '「⚖️ 再平衡交易指令」只有在**全部填滿且總和 100%** 時才會下判斷；'
                     '留白 → 顯示「無法判定」（不會用現況假裝已平衡）。'
                     '⚠️ 此欄目前**不會**存進 Google Sheet 雲端組合。'),
        })


    tolerance = st.slider(
        '再平衡容忍偏離度（%）', 1, 15,
        int(PORTFOLIO_REBAL_TOLERANCE_DEFAULT_PCT), key='etf_p_tol')

    if st.button('📊 計算組合', key='etf_p_btn', use_container_width=True):
        st.session_state['etf_p_active'] = True

    if not st.session_state.get('etf_p_active'):
        st.info('💡 填好上方表格後點擊「計算組合」')
        return

    # ── 解析 data_editor 表格 → rows（1 張 = 1000 股換算）─────
    from src.compute.etf import normalize_etf_ticker
    rows = []
    for _, _row in edited_df.iterrows():
        _tk_raw = normalize_etf_ticker(_row.get('股票代號'))
        if not _tk_raw:
            continue
        try:
            _lots      = float(_row.get('持有張數') or 0)
            _avg_price = float(_row.get('平均買入價格') or 0)
        except (TypeError, ValueError):
            st.warning(f'⚠️ {_tk_raw} 張數/均價非數字，已略過')
            continue
        if _lots <= 0 or _avg_price <= 0:
            st.warning(f'⚠️ {_tk_raw} 張數或均價為 0，已略過')
            continue
        _shares = _lots * 1000  # 1 張 = 1000 股
        # B5-a:選填目標比例。留白 / 非數字 / NaN → None(= 明確「沒設定」),**不補 0**。
        _tgt_raw = _row.get(TARGET_PCT_COL)
        try:
            _tgt_user = None if _tgt_raw is None else float(_tgt_raw)
        except (TypeError, ValueError):
            _tgt_user = None
        if _tgt_user is not None and (_tgt_user != _tgt_user or _tgt_user < 0):
            _tgt_user = None                       # NaN / 負數 → 視為未填
        rows.append({
            'ticker':     _tk_raw,
            'lots':       _lots,
            'shares':     _shares,
            'avg_price':  _avg_price,
            'cost':       _shares * _avg_price,
            'target_pct_user': _tgt_user,   # None = 使用者沒填(§1:不拿現況冒充目標)
            'target_pct': None,             # 下方依 gate 結果決定要不要填
            'role':       auto_role(_tk_raw),
        })
    if not rows:
        st.error('❌ 請至少填入一筆有效持股（代號 + 張數 + 均價皆 > 0）')
        return

    # ── 批次抓現價 + 配息（每檔 yfinance 已有 @st.cache_data 護身）──
    # v18.206 H2：原序列 for-loop → ThreadPoolExecutor（鏡像 v18.195 tab_stock 6-IO 並行模式）。
    # N 檔 ETF 每檔 2 個 yfinance 呼叫（價 + 配息），N 檔 wallclock 由 Σ → max(每檔)。
    _cur_prices = {}
    _div_received = {}
    _pf_price_end = None  # v18.198 價格資料截止日（取各檔最大）
    with st.spinner('抓取現價與配息資料...'):
        import datetime as _dt_pf
        from concurrent.futures import ThreadPoolExecutor, as_completed
        _cutoff = pd.Timestamp(_dt_pf.date.today() - _dt_pf.timedelta(days=365))

        def _fetch_one(_tk: str, _shares: float):
            """單檔抓現價 + 配息（無 st.* 呼叫 → thread-safe）。回 (price, div_amt, price_end_ts)。"""
            _price = 0.0
            _div_amt = 0.0
            _p_end = None
            try:
                _df_p = fetch_etf_price(_tk, period='5d')
                if _df_p is not None and not _df_p.empty:
                    _price = float(_df_p['Close'].iloc[-1])
                    try:
                        _p_end = pd.to_datetime(_df_p.index[-1])
                    except Exception as _e_pend:
                        print(f'[etf_tab_portfolio] {_tk} 收盤日期解析失敗:{type(_e_pend).__name__}')
                        _p_end = None
            except Exception as _e_price:
                print(f'[etf_tab_portfolio] {_tk} 收盤價抓取失敗:{type(_e_price).__name__}: {_e_price}')
            try:
                _div_s = fetch_etf_dividends(_tk)
                if _div_s is not None and not _div_s.empty:
                    _div_s = _div_s.copy()
                    _div_s.index = pd.to_datetime(_div_s.index, errors='coerce')
                    try:
                        _div_s.index = _div_s.index.tz_localize(None)
                    except Exception as _e_tz:
                        print(f'[etf_tab_portfolio] {_tk} 配息 index tz strip 失敗:{type(_e_tz).__name__}')
                    _recent = _div_s[_div_s.index >= _cutoff]
                    _div_amt = float(_recent.sum()) * _shares
            except Exception as _e_div:
                print(f'[etf_tab_portfolio] {_tk} 配息抓取失敗:{type(_e_div).__name__}: {_e_div}')
            return (_price, _div_amt, _p_end)

        _workers = min(len(rows), 6)
        with ThreadPoolExecutor(max_workers=_workers) as _ex:
            _futs = {
                _ex.submit(_fetch_one, r['ticker'], r['shares']): r['ticker']
                for r in rows
            }
            for _fut in as_completed(_futs):
                _tk = _futs[_fut]
                try:
                    _p, _d, _pe = _fut.result()
                except Exception as _e_fut:
                    print(f'[etf_tab_portfolio] {_tk} fetch future 失敗:{type(_e_fut).__name__}: {_e_fut}')
                    _p, _d, _pe = 0.0, 0.0, None
                _cur_prices[_tk] = _p
                _div_received[_tk] = _d
                if _pe is not None and (_pf_price_end is None or _pe > _pf_price_end):
                    _pf_price_end = _pe
    _pf_fetched_at = pd.Timestamp.now()  # v18.198 抓取完成時戳

    # ── 算現值/資本利得/已領配息（此段全為「該檔原幣別」）──
    for r in rows:
        _cp = _cur_prices.get(r['ticker'], 0.0)
        r['current_price']   = _cp
        r['current_value']   = r['shares'] * _cp
        r['capital_gain']    = r['current_value'] - r['cost']
        r['capital_gain_pct']= (r['capital_gain'] / r['cost'] * 100) if r['cost'] > 0 else 0.0
        r['dividend_received'] = _div_received.get(r['ticker'], 0.0)
        # 總損益 = 資本利得 + 已領配息（粗略不含稅費）
        r['total_pnl']       = r['capital_gain'] + r['dividend_received']

    # ══════════════════════════════════════════════════════════════════
    # §4.1 **單一換匯點**（B1-a v19.179）
    # ------------------------------------------------------------------
    # 原碼把美元 ETF(BND/VOO…)的原幣金額直接加進 TWD 總額 = 預設 1 USD = 1 TWD,
    # 造成整頁每個數字都錯(總現值 / 權重 / 股債比 / 核衛 / 產業曝險 / 風險貢獻 /
    # VaR 元金額 / 壓測 / 效率前緣權重 / 組合殖利率)。
    # 這裡是**整頁唯一**的換匯處:換完之後,下游 9 個消費點一律吃同一套 TWD 欄位。
    # §1:匯率拿不到 → 該檔排除出總計並顯示 ⚠️,**不**預設 1.0。
    # ══════════════════════════════════════════════════════════════════
    from src.compute.etf.portfolio_fx import (
        CURRENCY_USD, convert_rows_to_twd, fx_disclosure_caption, holding_currency,
    )
    _fx_rate = _fx_asof = _fx_source = None
    if any(holding_currency(r['ticker']) == CURRENCY_USD for r in rows):
        with st.spinner('抓取 USD/TWD 匯率（組合含美元計價 ETF）...'):
            _fx_rate, _fx_asof, _fx_source = _fetch_usdtwd_spot()
    _fx = convert_rows_to_twd(rows, usdtwd_rate=_fx_rate)
    rows          = _fx['rows']        # ← 之後全頁只用這份（已統一 TWD）
    _fx_excluded  = _fx['excluded']
    _fx_rate_used = _fx['rate_used']

    if _fx_excluded:
        # §1 Fail Loud:講清楚哪幾檔、為什麼、影響是什麼 —— 不靜默 1:1 混算
        _ex_names = '、'.join(str(_e.get('ticker')) for _e in _fx_excluded)
        print(f'[etf_tab_portfolio/fx] ⚠️ USD/TWD 取不到 → 排除 {_ex_names} '
              f'(共 {len(_fx_excluded)} 檔) 不計入 TWD 總計')
        st.error(
            f'⚠️ **{_ex_names} 為美元計價,但 USD/TWD 匯率取不到 —— '
            f'未納入組合統計。**\n\n'
            '下方所有金額 / 權重 / 股債比 / 風險數字都**只涵蓋台幣計價持股**。'
            '（不會用 1 USD = 1 TWD 硬加 —— 那正是這個頁面過去算錯的原因。）'
            '請點下方「🔄 強制重抓」再試一次。')
    if not rows:
        st.error('❌ 所有持股皆為外幣計價且 USD/TWD 匯率取不到 —— '
                 '無法產生任何台幣口徑的組合統計（§1 寧可不給,也不給錯的數字）。')
        return

    total_value = sum(r['current_value'] for r in rows)
    total_cost  = sum(r['cost'] for r in rows)
    total_gain  = sum(r['capital_gain'] for r in rows)
    total_div   = sum(r['dividend_received'] for r in rows)

    # ══════════════════════════════════════════════════════════════════
    # §1 B5-a v19.180:**沒有目標就沒有偏離**
    # ------------------------------------------------------------------
    # 原碼:`target_pct = actual_pct` → `deviation` 恆 0 → 再平衡永遠印
    # 「✅ 所有標的偏離度均在 ±5% 內」。那個綠燈代表「沒算」不是「已平衡」。
    # 現改:目標一律由使用者的「目標比例%」欄提供,並交給 L2 gate 三態判定。
    # ══════════════════════════════════════════════════════════════════
    from src.compute.etf.portfolio_gates import (
        STATUS_PASS, STATUS_UNKNOWN,
        evaluate_core_satellite_gate, evaluate_overlap_gate, evaluate_rebalance_gate,
    )
    for r in rows:
        r['actual_pct'] = round(r['current_value'] / total_value * 100, 2) if total_value > 0 else 0
    _rebal_gate = evaluate_rebalance_gate(
        [{'ticker': r['ticker'], 'actual_pct': r['actual_pct'],
          'target_pct': r['target_pct_user']} for r in rows],
        tolerance_pp=tolerance)
    _target_is_user_set = _rebal_gate['status'] != STATUS_UNKNOWN
    for r in rows:
        r['target_source'] = 'user' if _target_is_user_set else 'unset'
        if _target_is_user_set:
            r['target_pct'] = float(r['target_pct_user'])
            r['deviation']  = round(r['actual_pct'] - r['target_pct'], 2)
        else:
            # 下游(etf_tab_ai prompt / portfolio_linkage)吃 float 契約 → 保持數值型別,
            # 但畫面上這兩欄一律顯示「—」,且 target_source='unset' 已標記其不可信。
            # ⚠️ 已知殘留:`src/ui/etf/etf_tab_ai.py:107-108` 仍會把這組值寫進 AI prompt
            #    成「希望比例 X% / 實際 X%（偏離 +0.0pp）」—— 該檔不在本次改動範圍。
            r['target_pct'] = r['actual_pct']
            r['deviation']  = 0.0

    # ── 共享給下游模組（葡萄串領息法 / AI 評斷）──
    st.session_state['etf_portfolio_rows'] = rows

    # ── 🧭 股債比 + 總經一致性(v19.63 #2/#3):真抗跌來自債券/現金,非挑不相關股票 ──
    try:
        from src.compute.etf.portfolio_coherence import (
            assess_stock_bond, coherence_note,
        )
        _sb = assess_stock_bond(
            [{'ticker': r['ticker'], 'value': r['current_value']} for r in rows])
        # v19.170 P0-1:姿態改讀建議持股 SSOT(get_allocation)。
        # 原本直呼 compute_position_throttle 繞過 SSOT —— 該路徑只算姿態帶、
        # 不含硬否決天花板,且讀的是可能過期的 session['macro_state'],
        # 會與 🎚️ 建議持股油門 給出不同姿態。
        # §1 Fail Loud:未評估時維持空字串(coherence_note 既有的未知分支)。
        from src.services.allocation_service import get_allocation
        _alloc_pf = get_allocation()
        _posture = _alloc_pf.posture if _alloc_pf.is_loaded else ''
        _segs = ''
        if _sb['stock_pct'] > 0:
            _segs += (f'<div style="width:{_sb["stock_pct"]}%;background:#3498db;'
                      f'text-align:center;">股 {_sb["stock_pct"]:.0f}%</div>')
        if _sb['bond_pct'] > 0:
            _segs += (f'<div style="width:{_sb["bond_pct"]}%;background:#16a085;'
                      f'text-align:center;">債 {_sb["bond_pct"]:.0f}%</div>')
        st.markdown(
            '**🧭 股債比**（真正的抗跌來自債券/現金,不是挑不相關的股票型 ETF）'
            f'<div style="display:flex;height:16px;border-radius:8px;overflow:hidden;'
            f'margin:6px 0;font-size:11px;color:#fff;">{_segs}</div>',
            unsafe_allow_html=True)
        _lvl, _cmsg = coherence_note(_posture, _sb['bond_pct'])
        {'warn': st.warning, 'info': st.info, 'ok': st.success}.get(_lvl, st.caption)(_cmsg)

        # ── 🧱 核心/衛星 拆解(v19.63 #4):核心=市值型定期定額不理循環,衛星才戰術 ──
        # §2.1 B5-a v19.180:改吃 `portfolio_gates.assess_role_split`。
        # 原本這條 bar 走 `portfolio_coherence.assess_core_satellite`(VT 因不在台股
        # 分類表 → 判「衛星」),而下方「🎯 核心/衛星 vs regime 目標」走 `auto_role`
        # (VT/00878 都判「核心」)—— **同一頁、同一個名詞、兩套數字**。
        # 現在兩處共用同一個分類 SSOT,並多一段「未分類」讓不確定性看得見。
        from src.compute.etf.portfolio_gates import assess_role_split
        _cs = assess_role_split(
            [{'ticker': r['ticker'], 'value': r['current_value']} for r in rows])
        _cs_total = _cs['total_value']

        def _bar_pct(_v):
            """bar 用「佔總市值」比例(含債券),與下方核衛閘門的「股票腿內」比例不同口徑。"""
            return round(_v / _cs_total * 100, 1) if _cs_total > 0 else 0.0

        _cs_segs = ''
        for _k, _pct, _col in (('核心', _bar_pct(_cs['core_value']), '#8957e5'),
                               ('衛星', _bar_pct(_cs['satellite_value']), '#e67e22'),
                               ('債券', _bar_pct(_cs['bond_value']), '#16a085'),
                               ('未分類', _bar_pct(_cs['unknown_value']), '#586069')):
            if _pct > 0:
                _cs_segs += (f'<div style="width:{_pct}%;background:{_col};'
                             f'text-align:center;">{_k} {_pct:.0f}%</div>')
        st.markdown(
            '**🧱 核心/衛星**（核心=市值型「定期定額、不理循環」；衛星=主題/高息「才做戰術調整」）'
            f'<div style="display:flex;height:16px;border-radius:8px;overflow:hidden;'
            f'margin:6px 0;font-size:11px;color:#fff;">{_cs_segs}</div>',
            unsafe_allow_html=True)
        st.caption('💡 建議把「相關係數/景氣調整」用在**衛星**那塊,**核心**維持被動不動,'
                   '避免用分散之名行追漲殺跌之實。'
                   '（本條 bar 是**佔總市值**；下方「🎯 vs regime 目標」是**股票部位內**'
                   '比例，債券已排除 —— 兩者口徑不同，數字不會相等。）')
    except Exception as _e_sb:
        print(f'[portfolio_coherence] {type(_e_sb).__name__}: {_e_sb}')

    # ── v18.208 I6：ETF 投組 ↔ 總經 regime 跨 Tab 聯動 banner ──
    # 鏡像 v18.204 I4 個股端設計：reuse render_macro_stock_backdrop helper
    # （純讀 mkt_info，不分個股/ETF），讓 user 看 ETF 投組時不忘大盤系統性風險背景
    try:
        from src.ui.tabs import render_macro_stock_backdrop
        render_macro_stock_backdrop(st.session_state)
    except Exception as _e_msl:
        print(f'[macro_stock_link/etf_pf] {type(_e_msl).__name__}: {_e_msl}')

    # ── 資產總覽卡（總成本 / 總現值 / 資本利得 / 已領配息 / 總損益；全 TWD）──
    _gain_color = TRAFFIC_GREEN if total_gain >= 0 else TRAFFIC_RED
    _gain_sign  = '+' if total_gain >= 0 else ''
    _total_pnl  = total_gain + total_div
    _pnl_color  = TRAFFIC_GREEN if _total_pnl >= 0 else TRAFFIC_RED
    _pnl_sign   = '+' if _total_pnl >= 0 else ''
    st.markdown(
        f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:10px;'
        f'padding:16px 20px;margin:8px 0 16px;display:flex;gap:24px;flex-wrap:wrap;">'
        f'<div><div style="font-size:11px;color:#8b949e;">總投入成本（TWD）</div>'
        f'<div style="font-size:18px;font-weight:700;color:#c9d1d9;">{total_cost:,.0f}</div></div>'
        f'<div><div style="font-size:11px;color:#8b949e;">總現值（TWD）</div>'
        f'<div style="font-size:18px;font-weight:700;color:#c9d1d9;">{total_value:,.0f}</div></div>'
        f'<div><div style="font-size:11px;color:#8b949e;">資本利得</div>'
        f'<div style="font-size:18px;font-weight:700;color:{_gain_color};">'
        f'{_gain_sign}{total_gain:,.0f} ({_gain_sign}{(total_gain/total_cost*100 if total_cost else 0):.2f}%)</div></div>'
        f'<div><div style="font-size:11px;color:#8b949e;">已領配息（近1年）</div>'
        f'<div style="font-size:18px;font-weight:700;color:{TRAFFIC_YELLOW};">+{total_div:,.0f}</div></div>'
        f'<div><div style="font-size:11px;color:#8b949e;">總損益（利得+配息）</div>'
        f'<div style="font-size:18px;font-weight:900;color:{_pnl_color};">'
        f'{_pnl_sign}{_total_pnl:,.0f} ({_pnl_sign}{(_total_pnl/total_cost*100 if total_cost else 0):.2f}%)</div></div>'
        f'</div>', unsafe_allow_html=True)

    # §2.2 provenance:換匯用了什麼匯率、哪一天、哪個來源 —— 全部講出來。
    if _fx_rate_used:
        st.caption(fx_disclosure_caption(_fx_rate_used, _fx_asof, _fx_source))
        st.caption('ℹ️ 成本與現值**用同一個今日即期匯率**換算,故「資本利得」是'
                   '**純價格報酬**、**不含匯兌損益** —— 你真實的匯兌損益取決於'
                   '當初買進時的換匯匯率,本頁沒有那筆資料,所以不估（§1 不捏造）。')

    # v18.198 ══ 📊 投組資料新鮮度條 ══（價格截止日 + 抓取時間 + age traffic-light + 強制重抓）
    _pf_age_min = (pd.Timestamp.now() - _pf_fetched_at).total_seconds() / 60
    _pf_color = TRAFFIC_GREEN if _pf_age_min < 60 else (TRAFFIC_YELLOW if _pf_age_min < 240 else TRAFFIC_RED)
    _pf_age_txt = (f'{_pf_age_min:.0f} 分鐘前' if _pf_age_min < 60
                   else (f'{_pf_age_min / 60:.1f} 小時前' if _pf_age_min < 1440 else f'{_pf_age_min / 1440:.1f} 天前'))
    _pf_end_txt = _pf_price_end.strftime('%Y-%m-%d') if _pf_price_end is not None else '—'
    _fcols = st.columns([5, 1])
    with _fcols[0]:
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #30363d;border-radius:8px;'
            f'padding:8px 14px;margin:0 0 12px;display:flex;gap:18px;flex-wrap:wrap;align-items:center;font-size:12px;">'
            f'<span style="color:#8b949e;">📅 價格截止 <b style="color:#c9d1d9;">{_pf_end_txt}</b></span>'
            f'<span style="color:#8b949e;">🕐 抓取 <b style="color:#c9d1d9;">{_pf_fetched_at.strftime("%m-%d %H:%M")}</b></span>'
            f'<span style="color:#8b949e;">⏱️ <b style="color:{_pf_color};">{_pf_age_txt}</b></span>'
            f'<span style="color:#8b949e;">📡 來源 <b style="color:#c9d1d9;">yfinance（現價快取 1h／成份股 1 天）</b></span>'
            f'</div>', unsafe_allow_html=True)
    with _fcols[1]:
        if st.button('🔄 強制重抓', key='etf_pf_force_refresh',
                     help='清快取後重新抓取最新現價與配息（不需重填表格）'):
            try:
                st.cache_data.clear()
            except Exception as _e_clr:
                print(f'[etf_tab_portfolio] cache_data.clear() 失敗:{type(_e_clr).__name__}')
            st.rerun()

    # ── 持股明細表 ──
    # 查詢 ETF 名稱（去掉 .TW/.TWO 後綴後查 stock_names）
    try:
        from src.config import get_stock_name as _gsn_etf
        from src.compute.etf import bare_etf_code as _bare
        def _etf_name(tk):
            code = _bare(tk)
            n = _gsn_etf(code)
            return n if n and n != code else (fetch_etf_info(tk).get('shortName') or fetch_etf_info(tk).get('longName') or tk)
    except Exception as _e_nm:
        print(f'[etf_tab_portfolio] _etf_name helper 初始化失敗:{type(_e_nm).__name__}')
        def _etf_name(tk): return tk
    # §4.1:單價欄一律顯示「原幣別」原值(美元 ETF 印台幣單價會誤導),
    # 金額欄一律 TWD(已換匯)。幣別欄讓兩者不會被混讀。
    overview_df = pd.DataFrame([{
        'ETF':       r['ticker'],
        '名稱':       _etf_name(r['ticker']),
        '類型':       r.get('role', '—'),
        '幣別':       r.get('currency', 'TWD'),
        '張數':       f'{r.get("lots", r["shares"]/1000):.2f}',
        '股數':       f'{int(r["shares"]):,}',
        '均價(原幣)': f'{r.get("avg_price_native", r["avg_price"]):.2f}',
        '現價(原幣)': (f'{r.get("current_price_native", r["current_price"]):.2f}'
                       if r.get('current_price_native', r['current_price']) > 0 else '-'),
        '成本(TWD)':  f'{r["cost"]:,.0f}',
        '現值(TWD)':  f'{r["current_value"]:,.0f}',
        '資本利得':   f'{"+" if r["capital_gain"]>=0 else ""}{r["capital_gain"]:,.0f}',
        '利得%':      f'{"+" if r["capital_gain_pct"]>=0 else ""}{r["capital_gain_pct"]:.2f}%',
        '已領配息':   f'+{r["dividend_received"]:,.0f}' if r['dividend_received'] > 0 else '-',
        # §1:沒設定目標 → 顯示「—」。原碼印目標=實際、偏離=+0.0,
        # 讀起來像「完美貼合目標」,實際上是把現況抄成目標的自我循環。
        '目標比例%':  (f'{r["target_pct"]:.1f}' if r.get('target_source') == 'user' else '—'),
        '實際比例%':  f'{r["actual_pct"]:.1f}',
        '偏離度%':    (f'{"+" if r["deviation"]>=0 else ""}{r["deviation"]:.1f}'
                       if r.get('target_source') == 'user' else '—'),
    } for r in rows])
    st.dataframe(overview_df, use_container_width=True, hide_index=True)
    if not _target_is_user_set:
        st.caption('ℹ️ 「目標比例% / 偏離度%」顯示「—」：你尚未在上方表格填「目標比例%」。'
                   '系統**不會**拿現況當目標（那樣偏離永遠是 0，等於沒檢查）。')
    if _fx_rate_used:
        st.caption(f'💱 「均價/現價」為**原幣別**單價；「成本/現值/資本利得/已領配息」'
                   f'已用 1 USD = {_fx_rate_used:.4f} TWD 換算為台幣。')

    # §1:換不了匯而被排除的持股 —— 仍然要讓使用者看見(只是不進總計)。
    if _fx_excluded:
        st.markdown('##### ⚠️ 未納入組合統計（匯率取不到，不做 1:1 硬加）')
        st.dataframe(pd.DataFrame([{
            'ETF':          _e['ticker'],
            '名稱':          _etf_name(_e['ticker']),
            '幣別':          _e.get('currency', 'USD'),
            '股數':          f'{int(_e["shares"]):,}',
            '均價(原幣)':    f'{_e.get("avg_price_native", _e["avg_price"]):.2f}',
            '現價(原幣)':    f'{_e.get("current_price_native", _e["current_price"]):.2f}',
            '現值(原幣)':    f'{_e.get("current_value_native", _e["current_value"]):,.2f}',
            '狀態':          '⚠️ USD/TWD 匯率取不到，未換匯、不計入總計',
        } for _e in _fx_excluded]), use_container_width=True, hide_index=True)

    # ── 🛰️ ETF 追蹤戰情室（核心/衛星分流燈號 + Sparkline）─────
    st.markdown('#### 🛰️ ETF 追蹤戰情室（核衛分流健檢）')
    st.caption('💡 **核心**看「總報酬 vs 殖利率 + MA60 趨勢」；**衛星**看「MA20 ± σ 五階分級買賣點」')
    _usd_in_rows = [r['ticker'] for r in rows if r.get('currency') == CURRENCY_USD]
    if _usd_in_rows:
        # §4.1 誠實:本表逐檔獨立(不加總),市價/報酬皆為**原幣別**,未換匯亦不需換匯。
        st.caption(f'💱 {"、".join(_usd_in_rows)} 為美元計價 —— 本表「市價」與'
                   '各項報酬率皆為**原幣別**（逐檔獨立比較，不涉及跨幣別相加）。')
    with st.spinner('批次計算 ETF 健檢指標...'):
        _war_rows = [_compute_etf_warroom_row(r['ticker'], _etf_name(r['ticker']),
                                              r.get('role', '—'))
                     for r in rows]

    # 核心戰情室 column_config
    _core_cols = {
        '代號':         st.column_config.TextColumn('代號', width='small'),
        '名稱':         st.column_config.TextColumn('名稱', width='medium'),
        '市價':         st.column_config.NumberColumn('市價', format='%.2f'),
        '折溢價%':      st.column_config.NumberColumn('折溢價%', format='%+.2f%%',
                          help='> +1% 追高；< 0% 折價撿便宜（存股框架條件 C）'),
        '年化配息率%':  st.column_config.NumberColumn('年化配息率%', format='%.2f%%'),
        '1年含息報酬%': st.column_config.NumberColumn('1年含息報酬%', format='%+.2f%%',
                          help='含息總報酬，與年化配息率比較'),
        '距季線%':      st.column_config.NumberColumn('距 MA60%', format='%+.2f%%',
                          help='負值=跌破季線 → 🟡 趨勢轉弱'),
        '走勢':         st.column_config.LineChartColumn('近30日走勢'),
        '健康燈號':     st.column_config.TextColumn('體質燈號', width='large',
                          help='🟢 體質健康 / 🔴 賺息賠本 / 🟡 趨勢轉弱'),
        '動作建議':     st.column_config.TextColumn('動作建議', width='medium'),
    }

    # 衛星戰情室 column_config：突顯 σ 位階 + 加碼比例
    _sat_cols = {
        '代號':         st.column_config.TextColumn('代號', width='small'),
        '名稱':         st.column_config.TextColumn('名稱', width='medium'),
        '市價':         st.column_config.NumberColumn('市價', format='%.2f'),
        '距月線%':      st.column_config.NumberColumn('距 MA20%', format='%+.2f%%',
                          help='相對月線乖離；σ 分級的基準'),
        'σ位階':        st.column_config.TextColumn('⚡短線 σ 位階', width='medium',
                          help=f'⚡短線(MA20基準):-{ETF_QUICK_SIGMA_DISASTER:g}σ 股災 / '
                               f'-{ETF_QUICK_SIGMA_OVERSOLD:g}σ 超跌 / '
                               f'-{ETF_QUICK_SIGMA_CHEAP:g}σ 便宜 / '
                               f'+{ETF_QUICK_SIGMA_OVERBOUGHT:g}σ 停利。'
                               '單檔 Tab「📅長線 σ」用 MA240 z-score,訊號差異屬不同時間尺度正常。'),
        '1年含息報酬%': st.column_config.NumberColumn('1年含息報酬%', format='%+.2f%%'),
        '走勢':         st.column_config.LineChartColumn('近30日走勢'),
        '健康燈號':     st.column_config.TextColumn('σ 燈號', width='medium',
                          help='🟢🟢🟢 大買 50% / 🟢🟢 買 30% / 🟢 小買 20% / 🔴 停利'),
        '動作建議':     st.column_config.TextColumn('動作建議', width='medium',
                          help='依 σ 位階自動推導加碼/停利比例'),
    }

    # 其他角色簡表
    _other_cols = {
        '代號':         st.column_config.TextColumn('代號', width='small'),
        '名稱':         st.column_config.TextColumn('名稱', width='medium'),
        '市價':         st.column_config.NumberColumn('市價', format='%.2f'),
        '年化配息率%':  st.column_config.NumberColumn('年化配息率%', format='%.2f%%'),
        '1年含息報酬%': st.column_config.NumberColumn('1年含息報酬%', format='%+.2f%%'),
        '走勢':         st.column_config.LineChartColumn('近30日走勢'),
        '健康燈號':     st.column_config.TextColumn('燈號', width='medium'),
    }

    # ── 核心資產戰情室（佔比 80%）────────────────────────────
    _core_rows = [w for w in _war_rows if w.get('類型') == '核心']
    _sat_rows  = [w for w in _war_rows if w.get('類型') == '衛星']
    _other_rows = [w for w in _war_rows if w.get('類型') not in ('核心', '衛星')]

    if _core_rows:
        st.markdown('##### 🏛️ 核心資產戰情室（目標 80%）— 穩領息')
        st.caption('🔴 賺息賠本（總報酬<殖利率）→ 換股 ｜ 🟡 跌破 MA60 → 趨勢轉弱 ｜ 🟢 體質健康（雙條件全綠）')
        _core_df = pd.DataFrame(_core_rows)[
            ['代號', '名稱', '市價', '折溢價%', '年化配息率%',
             '1年含息報酬%', '距季線%', '走勢', '健康燈號', '動作建議']
        ]
        st.dataframe(_core_df, column_config=_core_cols,
                     use_container_width=True, hide_index=True)
    if _sat_rows:
        st.markdown('##### 🚀 衛星資產戰情室（目標 20%）— 跌了就買 σ 分級')
        # F1 v19.184：σ 倍數插 SSOT（見 import 段註解）。
        # ⚠️ 加碼比例「50% / 30% / 20%」**刻意保留字面** —— 它們目前只以字串常值
        # 存在於 `src/compute/etf/etf_helpers.classify_etf_quick_sigma` 的回傳值裡
        # （`'大買 50%'`），全站沒有對應常數。在這裡新造一個 L0 常數而不改那邊，
        # 只會製造第二份真相（正是本批要消滅的東西）→ 列為 B 類待辦，
        # 需連同 `etf_helpers` 一起抽，不在本批範圍（該檔屬 L2，不在 F1 施工範圍）。
        st.caption(f'🟢🟢🟢 < MA20-{ETF_QUICK_SIGMA_DISASTER:g}σ 股災價(大買 50%) ｜ '
                   f'🟢🟢 < -{ETF_QUICK_SIGMA_OVERSOLD:g}σ 超跌(30%) ｜ '
                   f'🟢 < -{ETF_QUICK_SIGMA_CHEAP:g}σ 便宜(20%) ｜ '
                   f'🔴 ≥ +{ETF_QUICK_SIGMA_OVERBOUGHT:g}σ 停利')
        _sat_df = pd.DataFrame(_sat_rows)[
            ['代號', '名稱', '市價', '距月線%', 'σ位階',
             '1年含息報酬%', '走勢', '健康燈號', '動作建議']
        ]
        st.dataframe(_sat_df, column_config=_sat_cols,
                     use_container_width=True, hide_index=True)
    if _other_rows:
        st.markdown('##### 📦 其他持倉（未分類）')
        _oth_df = pd.DataFrame(_other_rows)[
            ['代號', '名稱', '市價', '年化配息率%', '1年含息報酬%', '走勢', '健康燈號']
        ]
        st.dataframe(_oth_df, column_config=_other_cols,
                     use_container_width=True, hide_index=True)

    # ── 存股框架 #9：核心 / 衛星比例 vs regime 目標 ────────────
    # ══════════════════════════════════════════════════════════════════
    # §1 B5-a v19.180:兩個假綠燈同時修
    # ------------------------------------------------------------------
    # (1) 判定式單邊 → `portfolio_manager.check_rebalance` 的
    #     `excess_ratio >= 0.10` 只抓「衛星**超標**」。衛星不足 30pp 落到 else
    #     分支印「✅ 核衛比例符合…（±10pp 容忍）」—— 畫面寫雙邊、判定是單邊。
    # (2) 分類把所有 ETF 歸核心 → `auto_role` 白名單同時收了高股息(00878)與
    #     債券(BND),一組 0050+00878+VT 會算出「核心 100% / 衛星 0%」。
    # 改走 L2 `portfolio_gates`:雙邊比對 + 分類走「債券 → 台股分類表 → 海外寬基
    # 白名單 → 未知」四段,查不到的代號誠實回「未知」並改判無法判定。
    # ══════════════════════════════════════════════════════════════════
    st.markdown('#### 🎯 核心 / 衛星 配置 vs regime 目標')
    _target_core_pct = None
    try:
        from src.compute.strategy import CoreSatelliteManager as _CSM
        # C1 v19.182:`regime is None`(總經未評估)時**不得**建 manager ——
        # `_CORE_RATIO.get(None, 0.70)` 會靜默給出 0.70,也就是把「中性 70/30」
        # 當成一個已知目標拿去判合格。§1 明文禁止「自行估一個合理值當常數」。
        # 目標為 None → 下方 gate 走既有 STATUS_UNKNOWN 分支誠實顯示無法判定。
        _mgr = _CSM(total_value, regime=regime) if (total_value > 0 and regime) else None
        _target_core_pct = _mgr.core_ratio * 100 if _mgr is not None else None
    except Exception as _csm_e:
        print(f'[etf_tab_portfolio/core_sat] CoreSatelliteManager 取目標失敗:'
              f'{type(_csm_e).__name__}: {_csm_e}')
    _cs_gate = evaluate_core_satellite_gate(
        [{'ticker': r['ticker'], 'value': r['current_value']} for r in rows],
        target_core_pct=_target_core_pct, regime=(regime or ''))
    _cs_split = _cs_gate['split']
    _cs_tol   = _cs_gate['tolerance_pp']
    _cs1, _cs2 = st.columns(2)
    _core_lbl = (f'核心比 (目標 {_target_core_pct:.0f}%)' if _target_core_pct is not None
                 else '核心比 (目標未知)')
    _sat_lbl  = (f'衛星比 (目標 {100 - _target_core_pct:.0f}%)'
                 if _target_core_pct is not None else '衛星比 (目標未知)')
    _core_dev = (_cs_split['core_pct'] - _target_core_pct
                 if _target_core_pct is not None else None)
    _sat_dev  = (_cs_split['satellite_pct'] - (100 - _target_core_pct)
                 if _target_core_pct is not None else None)
    _cs1.metric(_core_lbl, f'{_cs_split["core_pct"]:.1f}%',
                delta=(f'{_core_dev:+.1f}pp' if _core_dev is not None else None),
                delta_color=('normal' if _core_dev is not None and abs(_core_dev) <= _cs_tol
                             else 'inverse'))
    _cs2.metric(_sat_lbl, f'{_cs_split["satellite_pct"]:.1f}%',
                delta=(f'{_sat_dev:+.1f}pp' if _sat_dev is not None else None),
                delta_color=('normal' if _sat_dev is not None and abs(_sat_dev) <= _cs_tol
                             else 'inverse'))
    _cs_color = {STATUS_PASS: 'green', STATUS_UNKNOWN: 'yellow'}.get(
        _cs_gate['status'], 'red')
    _colored_box(f'<b>{_cs_gate["headline"]}</b><br>{_cs_gate["detail"]}', _cs_color)
    if _cs_gate['status'] == STATUS_PASS:
        _strategy_conclusion(
            STRATEGY_VALUATION,
            f'核 {_cs_split["core_pct"]:.0f}% / 衛 {_cs_split["satellite_pct"]:.0f}%',
            f'符合 regime={regime} 目標 {_target_core_pct:.0f}'
            f'/{100 - _target_core_pct:.0f}（±{_cs_tol:.0f}pp）',
            '維持當前配置')
    elif _cs_gate['status'] != STATUS_UNKNOWN:
        _strategy_conclusion(
            STRATEGY_VALUATION,
            f'核 {_cs_split["core_pct"]:.0f}% / 衛 {_cs_split["satellite_pct"]:.0f}%',
            f'偏離 regime={regime} 建議帶 '
            f'{_cs_gate["band_lo"]:.0f}~{_cs_gate["band_hi"]:.0f}%',
            '把超額的一側調回建議帶（核心=市值型被動；衛星才做戰術）')
    if _cs_split['unclassified']:
        st.caption(f'⚪ **未分類**（佔股票部位 {_cs_split["unknown_pct"]:.1f}%）：'
                   f'{"、".join(_cs_split["unclassified"])} —— 不在 ETF 分類表也不在'
                   '海外寬基白名單，**不硬歸核心也不硬歸衛星**；'
                   '要讓它可判定請補 `src/compute/etf/etf_categories.py`。')
    if _cs_split['bond_value'] > 0:
        st.caption(f'ℹ️ 債券部位（佔總市值 {_cs_split["bond_pct_of_total"]:.1f}%）'
                   '**不計入**核心/衛星分母 —— 核衛是「股票部位怎麼拆」，'
                   '債券請看上方「🧭 股債比」。')
    st.caption(f'💡 **regime 目標**：{_regime_core_sat_text()}'
               f'（核/衛），雙邊容忍 ±{_cs_tol:.0f}pp。'
               '分類規則：債券 → 台股 ETF 分類表（市值型=核心，其餘類別=衛星）→ '
               '海外寬基白名單（VT/VTI/VOO/SPY…）→ 未分類。')

    # ── 再平衡交易指令（含具體股數）────────────────────────────
    st.markdown('#### ⚖️ 再平衡交易指令')
    # §4.1 B1-a:金額(adj)是 TWD → 換算股數的「現價」也必須是 TWD 口徑。
    # 原碼用 `_cur_prices`(原幣別)當分母,美元 ETF 會算出約 32 倍的股數。
    # 改讀已換匯的 r['current_price'];原幣單價另存 r['current_price_native'] 供顯示。
    # B5-a:交易指令一律由 L2 gate 的 `breaches` 驅動（單一判定式，避免 UI 端
    # 再寫一次 `abs(dev) > tol` 而與燈號因四捨五入不同步）。
    _rows_by_tk = {r['ticker']: r for r in rows}
    rebal_actions = []
    for _b in _rebal_gate['breaches']:
        r = _rows_by_tk.get(_b['ticker'])
        if r is None:
            continue
        target_val = total_value * _b['target_pct'] / 100
        adj        = target_val - r['current_value']
        action     = _b['action']
        cur_price  = r.get('current_price', 0) or 0     # TWD 口徑
        shares     = int(abs(adj) / cur_price) if cur_price > 0 else 0
        rebal_actions.append({
            # ⚠️ key 名維持 '金額(元)' / '現價' 不變 —— `etf_tab_ai.py:127`
            # 直接讀這兩個 key 建 AI prompt(該檔不在本次改動範圍)。
            # 值的**口徑**已改為 TWD(原為原幣別),語意因此才正確。
            'ETF': r['ticker'], '動作': action,
            '金額(元)': abs(adj), '偏離度%': _b['deviation_pp'],
            '現價': cur_price, '建議股數': shares,
            '幣別': r.get('currency', 'TWD'),
            '現價(原幣)': r.get('current_price_native', cur_price),
        })

    if rebal_actions:
        _colored_box(f'<b>{_rebal_gate["headline"]}</b>', 'red')
        ra_df = pd.DataFrame([{
            'ETF':    a['ETF'],
            '動作':   a['動作'],
            '幣別':   a['幣別'],
            '現價(原幣)': f'{a["現價(原幣)"]:.2f}' if a['現價(原幣)'] > 0 else '-',
            '現價(TWD)':  f'{a["現價"]:.2f}' if a['現價'] > 0 else '-',
            '建議股數': f'{a["建議股數"]:,}' if a['建議股數'] > 0 else '-',
            '金額(TWD)': f'{a["金額(元)"]:,.0f}',
            '偏離度%': a['偏離度%'],
        } for a in rebal_actions])
        st.dataframe(ra_df, use_container_width=True, hide_index=True)
        for act in rebal_actions:
            color = 'green' if act['動作'] == '買進' else 'red'
            icon  = '📈' if act['動作'] == '買進' else '📉'
            _px_txt = (f'{act["現價(原幣)"]:.2f} {act["幣別"]}'
                       if act['幣別'] != 'TWD' else f'{act["現價"]:.2f} 元')
            _share_txt = (f'約 <b>{act["建議股數"]:,} 股</b>（現價 {_px_txt}）'
                          if act['建議股數'] > 0 else '（無法取得現價）')
            _colored_box(
                f'{icon} <b>{act["動作"]} {act["ETF"]}</b> {_share_txt}，'
                f'預估金額 <b>{act["金額(元)"]:,.0f} 元 TWD</b>'
                f'（偏離 {act["偏離度%"]:+.1f}%）',
                color)
    else:
        # §1 B5-a:三態 —— 只有「已比對過使用者設定的目標且全部在容忍帶內」才給綠燈。
        # 沒設定目標 / 只設定一部分 / 總和 ≠ 100% → ⚪ 無法判定 + 明說缺什麼。
        _rb_color = {STATUS_PASS: 'green', STATUS_UNKNOWN: 'yellow'}.get(
            _rebal_gate['status'], 'red')
        _colored_box(f'<b>{_rebal_gate["headline"]}</b><br>{_rebal_gate["detail"]}',
                     _rb_color)

    # ── 產業曝險上限檢查（單一類股 ≤ 30%）─────────────────────
    st.markdown('#### 🏗️ 產業曝險上限檢查（單一 GICS 類股 ≤ 30%）')
    _check_sector_exposure(rows, total_value)

    # ── 相關係數矩陣 ──────────────────────────────────────────
    st.markdown('#### 🔗 相關係數矩陣（近1年）')
    st.caption('💡 此矩陣用「日報酬率」算 Pearson 相關係數，'
               '反映**價格走勢同步度**（不看持股名單）。值越接近 1 表示分散效益越差。')
    tickers = [r['ticker'] for r in rows]
    ret_dict = {}
    with st.spinner('計算相關係數...'):
        for t in tickers:
            df_t = fetch_etf_price(t, period='1y')
            if not df_t.empty:
                ret_dict[t] = df_t['Close'].pct_change()
    if len(ret_dict) >= 2:
        # §1(v19.165):共同交易日交集,不 ffill(停牌/缺口日不捏造報酬,否則相關被拉假)
        ret_df = pd.DataFrame(ret_dict).dropna(how='any')
        corr   = ret_df.corr()
        _plot_correlation(corr)
        for i in range(len(corr)):
            for j in range(i + 1, len(corr)):
                val = corr.iloc[i, j]
                if val > ETF_CORR_HIGH_THRESHOLD:
                    _colored_box(
                        f'⚠️ <b>{corr.index[i]} × {corr.columns[j]}</b> '
                        f'相關係數 {val:.2f} > {ETF_CORR_HIGH_THRESHOLD:.2f}，資產同質性過高',
                        'red')
    else:
        st.warning('資料不足，無法計算相關係數')

    # ── 🎚️ 風險貢獻分解（市值% vs 風險%）── v19.137 Risk Contribution（PyPortfolioOpt 概念）
    # 與上方相關矩陣同源（ret_dict 日報酬）：相關看「同步度」，這裡看「風險壓在哪幾檔」。
    # v19.138：render 抽至 L4 risk_contribution_render，與個股組合共用（DRY）。
    from src.compute.risk.risk_contribution import compute_risk_contribution
    from src.ui.render.risk_contribution_render import render_risk_contribution_panel
    _rc_weights = {r['ticker']: r['current_value'] for r in rows if r['current_value'] > 0}
    # §1(v19.165):compute_risk_contribution 內部已 dropna(how='any');外層勿 ffill(捏造缺口值)
    _rc_returns = pd.DataFrame(ret_dict) if ret_dict else pd.DataFrame()
    _rc = compute_risk_contribution(_rc_returns, _rc_weights)
    render_risk_contribution_panel(_rc, warn_box=lambda _m: _colored_box(_m, 'red'))

    # ── 各檔 ETF 成分股明細（成分股顯示）──────────────────────
    st.markdown('#### 🧩 各檔 ETF 成分股明細')
    st.caption('💡 點開每檔 ETF 看它「真正持有哪些股票、各佔多少權重」。'
               '下方的持股 Overlap 矩陣，即是用這份成分股清單兩兩比對得出。')
    _h_dict = {}
    _h_miss = []
    with st.spinner('抓取各檔成份股清單（首次約 10-20 秒，之後 1 日快取）...'):
        for t in tickers:
            _h = fetch_etf_holdings(t)
            if _h:
                _h_dict[t] = _h
            else:
                _h_miss.append(t)
    for _i_t, t in enumerate(tickers):
        _hl_label = (f'📋 {t}　成分股 {len(_h_dict[t])} 檔'
                     if t in _h_dict else f'📋 {t}　⚪ 暫無成分股資料')
        with st.expander(_hl_label, expanded=False):
            render_etf_holdings(t, holdings=_h_dict.get(t), top_n=15,
                                key=f'port_{_i_t}_{t}')

    # ── 持股 Overlap 矩陣（PR — claude/etf-holdings-overlap）────
    st.markdown('#### 🧬 持股 Overlap 矩陣（成份股重疊度）')
    st.caption('💡 與上方「價格相關」對照看：價格相關高可能因市場連動（如全市場股災），'
               '但**持股 overlap 高**代表組合在「真正持有的股票」層面高度雷同 — '
               '即使換成不同名稱的 ETF，本質上也沒分散到。')
    _ov_method = st.radio(
        '演算法',
        ('權重 Overlap%（業界標準）', 'Jaccard 集合重疊（不看權重）'),
        horizontal=True, key='ov_method_radio',
        help='權重 Overlap%：兩 ETF 共同持股取較小權重加總；Jaccard：|A∩B|/|A∪B| 只看股票名單'
    )
    _method_key = 'jaccard' if 'Jaccard' in _ov_method else 'weight'
    if _h_miss:
        st.warning(f'⚪ 以下 ETF 拿不到成份股，對應行列顯示 N/A：{", ".join(_h_miss)}'
                   f'（MoneyDJ 暫無資料或為新 ETF）')
    _valid_count = len(_h_dict)
    # ══════════════════════════════════════════════════════════════════
    # §1 B5-a v19.180:重疊度三態判定（原碼只有「有警示 / 綠燈」兩態）
    # ------------------------------------------------------------------
    # 原綠燈「✅ 任兩檔重疊 < 30%」在以下三種「其實沒量到」的情況一律會亮:
    #   (a) 某檔抓不到成分股 → 該對是 NaN，迴圈 `pd.notna` 直接跳過 → 沒警示 = 綠燈
    #   (b) 跨市場（0050 中文股名 × VT 英文公司名）→ 交集恆為空 → 恆 0%
    #   (c) yfinance 只給前 10 大（VT 權重覆蓋率 ~15%）→ 重疊率**上限**就低於
    #       30% 門檻 → 這對不可能失敗，「沒超標」不代表分散
    # 現改由 L2 `evaluate_overlap_gate` 逐對標 ok / breach / no_data /
    # incomparable_namespace / inconclusive_ceiling，只有全部 ok 才給綠燈。
    # ══════════════════════════════════════════════════════════════════
    _ov_gate = evaluate_overlap_gate(
        {t: _h_dict.get(t) for t in tickers}, tickers, method=_method_key)
    _threshold = _ov_gate['threshold_pct']
    if _valid_count >= 2:
        _ov_mat = build_holdings_overlap_matrix(_h_dict, method=_method_key)
        # 補齊缺資料 ETF（讓矩陣 ticker 順序與上方價格矩陣一致）
        for _t_miss in _h_miss:
            if _t_miss not in _ov_mat.index:
                _ov_mat.loc[_t_miss] = np.nan
                _ov_mat[_t_miss]     = np.nan
        _ov_mat = _ov_mat.reindex(index=tickers, columns=tickers)
        # §1:量不到的那幾對從熱圖抹成 NaN(灰) —— 不讓一個「沒比到」的 0.0%
        # 在圖上長得跟「真的不重疊」一樣。
        for _p in _ov_gate['unmeasured']:
            if _p['a'] in _ov_mat.index and _p['b'] in _ov_mat.columns:
                _ov_mat.loc[_p['a'], _p['b']] = np.nan
                _ov_mat.loc[_p['b'], _p['a']] = np.nan
        _plot_holdings_overlap(
            _ov_mat,
            title=f'{"權重 Overlap%" if _method_key == "weight" else "Jaccard%"}'
                  f'（可比對 {_ov_gate["measured_pairs"]}/{_ov_gate["total_pairs"]} 對）'
        )
    _ov_color = {STATUS_PASS: 'green', STATUS_UNKNOWN: 'yellow'}.get(
        _ov_gate['status'], 'red')
    _colored_box(f'<b>{_ov_gate["headline"]}</b><br>{_ov_gate["detail"]}', _ov_color)
    # 逐對可稽核明細（重疊率 / 可測上限 / 各自權重覆蓋率 / 共同持股數）
    if _ov_gate['pairs']:
        _pair_df = pd.DataFrame([{
            'ETF A': _p['a'], 'ETF B': _p['b'],
            '重疊%': ('—' if _p['value_pct'] is None else f'{_p["value_pct"]:.1f}'),
            '可測上限%': ('—' if _p['ceiling_pct'] is None else f'{_p["ceiling_pct"]:.1f}'),
            'A 權重覆蓋%': f'{_p["coverage_a_pct"]:.0f}',
            'B 權重覆蓋%': f'{_p["coverage_b_pct"]:.0f}',
            '共同持股': _p['common_holdings'],
            '判定': {'ok': '✅ 已比對，未超標', 'breach': '🔴 超標',
                     'no_data': '⚪ 無成分股資料',
                     'incomparable_namespace': '⚪ 中/英文名對不上，沒比到',
                     'inconclusive_ceiling': '⚪ 上限低於門檻，不可能失敗'}[_p['status']],
            '說明': _p['reason'],
        } for _p in _ov_gate['pairs']])
        st.dataframe(_pair_df, use_container_width=True, hide_index=True)
        st.caption('💡 **可測上限%** = 在現有成分股資料下，這一對「最高可能」的重疊率。'
                   f'上限 ≤ 門檻 {_threshold:.0f}% 時，這對再怎麼雷同也不會觸發警示 → '
                   '判「無法判定」而非通過（§1：綠燈必須代表「算過且通過」）。')
    # §1:下游 AI prompt 讀這個字串 —— unknown 也要如實傳達「沒量到」。
    st.session_state['etf_overlap_summary'] = (
        f'{_ov_gate["headline"]}｜{_ov_gate["detail"]}')

    # ── 主動 ETF 弱勢度檢測（PR — claude/etf-weakness-manager）──
    # Gemini 邏輯：大跌時跌得比大盤深 + 反彈時漲得比大盤慢 + 連兩季輸盤 = 該換
    st.markdown('#### 🎯 主動 ETF 弱勢度檢測（vs 大盤被動式）')
    st.caption('💡 主動式 ETF 你付 1% 經理費，**就該打贏大盤**。如果近1年大跌時它跌更深、'
               '反彈時它漲更慢，連 2 季輸盤 → 該考慮換到被動式（如 0050）。'
               '⏳ 但若**剛換新經理人 <6 個月**，建議再給時間觀察。')
    _w_rows = []
    with st.spinner('檢測弱勢度（含經理人查詢，首次約 5-15 秒）...'):
        for _r in rows:
            _w_rows.append(compute_etf_weakness_row(_r['ticker'], _r.get('name', '')))
    if _w_rows:
        _render_weakness_table(_w_rows)
        # 換股建議匯總
        _switch_targets = [r for r in _w_rows
                           if r.get('主被動') == '主動式'
                           and (r.get('連敗季數') or 0) >= LAG_ALERT_STREAK_QUARTERS]
        if _switch_targets:
            _lines = []
            for _r in _switch_targets:
                _mgr_note = (f'（⏳ 新經理人 {_r["任期"]}，可再觀察）'
                             if isinstance(_r.get('任期'), str) and '個月' in _r['任期']
                             and any(ch.isdigit() for ch in _r['任期'])
                             and int(''.join(filter(str.isdigit, _r['任期'].split('個月')[0]))) < 6
                             else '')
                _lines.append(
                    f'🚨 <b>{_r["代號"]} {_r["名稱"]}</b> 已連續 {_r["連敗季數"]} 季輸 '
                    f'{_r.get("benchmark", "大盤")} — 經理人 {_r["經理人"]} '
                    f'(任期 {_r["任期"]}){_mgr_note}'
                )
            _colored_box('<br>'.join(_lines), 'red')
        st.session_state['etf_weakness_summary'] = ('；'.join(
            f'{_r["代號"]} 連{_r.get("連敗季數", 0)}季輸{_r.get("benchmark", "大盤")}(建議換被動式)'
            for _r in _switch_targets) if _switch_targets else '無主動式 ETF 連 2 季輸盤')

    # ── 壓力測試（v18.335 PR-H3:抽至 etf_calc.calc_portfolio_stress_test SSOT）─
    st.markdown(f'#### 🧨 壓力測試（模擬 S&P 500 下跌 {abs(PORTFOLIO_STRESS_TEST_DROP_PCT):.0f}%）')
    _stress = calc_portfolio_stress_test(rows, total_value)
    # 渲染表格(剔除內部 _loss 欄)
    stress_results = [{k: v for k, v in r.items() if not k.startswith('_')}
                      for r in _stress['per_etf']]
    total_stress = _stress['total_loss']
    st.dataframe(pd.DataFrame(stress_results), use_container_width=True, hide_index=True)
    # P3-A(§1/§3.1):beta 缺以 1.0 估算者須揭示,不靜默捏造
    if _stress.get('beta_imputed_count'):
        st.caption(f"⚠️ 其中 {_stress['beta_imputed_count']} 檔查無 Beta，以 1.0 估算納入壓測"
                   f"（{'、'.join(_stress['beta_imputed_tickers'])}）—— 該檔虧損為估計值、非真實 Beta。")
    loss_pct = _stress['loss_pct']
    _stress_warn = loss_pct > PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT
    color    = 'red' if _stress_warn else 'green'
    _colored_box(
        f'組合預估總虧損：<b>{total_stress:,.0f} 元</b>（{loss_pct:.1f}%）'
        + (f'&nbsp; ⚠️ 超過{PORTFOLIO_STRESS_TEST_LOSS_WARN_PCT:.0f}%，建議增加避險部位'
           if _stress_warn else '&nbsp; ✅ 風險可控'),
        color)
    if _stress_warn:
        _strategy_conclusion(STRATEGY_VALUATION,
                             f'S&P500↓20% 壓力測試損失 {loss_pct:.1f}%',
                             '尾部風險超標，組合過於進攻型',
                             '增加債券 ETF 或現金部位，降低整體 Beta')
    else:
        _strategy_conclusion(STRATEGY_VALUATION,
                             f'S&P500↓20% 壓力測試損失 {loss_pct:.1f}%',
                             '壓力測試風險可控，組合防禦性足夠',
                             '維持現有配置，定期再平衡')

    # ── VaR 風險值（歷史模擬法 + 參數法）────────────────────────
    st.markdown('#### 📉 VaR 風險值（Value at Risk）')
    st.caption('衡量正常市況下單日最大可能虧損：歷史模擬法取近1年最差分位數，參數法假設常態分布')
    _var_rets = {}
    with st.spinner('計算 VaR...'):
        for r in rows:
            _df_v = fetch_etf_price(r['ticker'], period='1y')
            if not _df_v.empty:
                _var_rets[r['ticker']] = _df_v['Close'].pct_change().dropna()
    if len(_var_rets) >= 1:
        # §1 誠實對齊(v19.165):只取「全員皆有交易」的共同日(dropna),不 ffill / 不 fillna(0)。
        # 舊寫法把新上市 ETF 上市前當成 0% 報酬 → 稀釋波動、低估尾部 VaR(風險看起來比實際小)。
        # 計算下沉 L2 etf_calc.align_portfolio_returns(可單元測試)。
        from src.compute.etf.etf_calc import align_portfolio_returns
        _va = align_portfolio_returns(_var_rets, {r['ticker']: r['actual_pct'] for r in rows})
        _port_ret = _va['port_ret']
        _n_common = _va['n_common']
        _limiter = _va['limiter']
        _limiter_start = _va['limiter_start']
        if _va['dropped'] > 0 and _limiter is not None and _limiter_start is not None:
            print(f"[etf_var] 共同交易日對齊:union {_va['n_union']}→交集 {_n_common}"
                  f"(剔 {_va['dropped']} 非共同日);視窗受最短檔 {_limiter}"
                  f"(起 {_limiter_start.date()})限制;未做任何填補(§1)")
        if len(_port_ret) >= 20:
            st.caption(f'📏 VaR 樣本＝{_n_common} 個「全員皆有交易」的共同日'
                       f'（{_port_ret.index.min():%Y-%m-%d} ~ {_port_ret.index.max():%Y-%m-%d}）;'
                       '缺失日一律剔除、未填 0 或 ffill（§1 誠實)。')
            if _limiter is not None and _limiter_start is not None \
                    and _limiter_start > _port_ret.index.min():
                st.warning(f'⚠️ VaR 視窗被最短一檔 **{_limiter}**'
                           f'（{_limiter_start:%Y-%m-%d} 才有資料）壓縮到 {_n_common} 日;'
                           '新上市 ETF 樣本短、尾部估計偏樂觀,請理解此限制。')
            # 歷史模擬法
            _h95 = float(_port_ret.quantile(PORTFOLIO_VAR_95_PERCENTILE)) * total_value
            _h99 = float(_port_ret.quantile(PORTFOLIO_VAR_99_PERCENTILE)) * total_value
            # 參數法
            _mu  = float(_port_ret.mean())
            _sig = float(_port_ret.std())
            _p95 = (_mu - 1.645 * _sig) * total_value
            _p99 = (_mu - 2.326 * _sig) * total_value
            # 月度 VaR（√21 近似）
            _m99 = _h99 * (21 ** 0.5)

            _vc1, _vc2 = st.columns(2)
            with _vc1:
                st.markdown('**📊 歷史模擬法**')
                st.metric('95% 日 VaR', f'{abs(_h95):,.0f} 元',
                          f'{abs(_h95)/total_value*100:.2f}% 組合市值')
                st.metric('99% 日 VaR', f'{abs(_h99):,.0f} 元',
                          f'{abs(_h99)/total_value*100:.2f}% 組合市值')
                st.caption('95% VaR：正常市況下100天中，95天的虧損不超過此值')
            with _vc2:
                st.markdown('**📐 參數法（常態分布）**')
                st.metric('95% 日 VaR', f'{abs(_p95):,.0f} 元',
                          f'{abs(_p95)/total_value*100:.2f}% 組合市值')
                st.metric('99% 日 VaR', f'{abs(_p99):,.0f} 元',
                          f'{abs(_p99)/total_value*100:.2f}% 組合市值')
                st.caption('金融市場有肥尾效應，歷史模擬法通常比參數法更保守')
            _var_warn = abs(_m99) / total_value * 100 > PORTFOLIO_VAR_MONTHLY_WARN_PCT
            _colored_box(
                f'📅 月度 99% VaR（√21 近似）：<b>{abs(_m99):,.0f} 元</b>'
                f'（{abs(_m99)/total_value*100:.2f}%）'
                + (f'&nbsp; ⚠️ 超過{PORTFOLIO_VAR_MONTHLY_WARN_PCT:.0f}%，'
                   '尾部風險偏高，建議增加防禦部位'
                   if _var_warn else '&nbsp; ✅ 月度尾部風險在可接受範圍內'),
                'red' if _var_warn else 'green')
            if _var_warn:
                _strategy_conclusion(STRATEGY_TECHNICAL,
                                     f'月度 99% VaR {abs(_m99)/total_value*100:.2f}%',
                                     f'月度尾部風險 > {PORTFOLIO_VAR_MONTHLY_WARN_PCT:.0f}%，組合波動過大',
                                     '增加低相關資產（如 BND/AGGG），降低整體波動')
            else:
                _strategy_conclusion(STRATEGY_TECHNICAL,
                                     f'月度 99% VaR {abs(_m99)/total_value*100:.2f}%',
                                     '月度尾部風險在可接受範圍，組合穩健',
                                     '維持現有風險配置，按計畫再平衡')
        else:
            st.warning(f'歷史共同交易日不足（{_n_common}<20'
                       + (f'，受最短檔 {_limiter} 限制' if _limiter else '')
                       + '），無法計算 VaR')
    else:
        st.warning('無法取得價格資料，跳過 VaR 計算')

    # ── 📈 與 0050 累積報酬比較（個別 + 組合）─────────────────────
    # §7 對齊:累積報酬 = (1+日報酬).cumprod()-1(小數,顯示 %,不年化)。三曲線(組合/個別/0050)
    # 一律在「共同交易日」上算(§1 dropna,不 ffill / 不 fillna(0));計算下沉 L2
    # etf_calc.compute_portfolio_vs_benchmark(可單元測試),繪圖走 L4 etf_render。
    # 重用 VaR 段已抓好的 _var_rets(每檔 1y 日報酬)+ 權重,只多抓一次 0050 基準。
    st.markdown('#### 📈 與 0050 累積報酬比較（個別 + 組合）')
    st.caption('把「組合(加權)」「每檔持股」與可直接買的 0050 疊在同一組共同交易日上比累積報酬%，'
               '看你的配置到底贏不贏得過大盤。')
    if _var_rets:
        from src.compute.etf.etf_calc import compute_portfolio_vs_benchmark
        from src.ui.render.etf_render import _plot_portfolio_vs_benchmark
        from shared.signal_thresholds import PORTFOLIO_BENCHMARK_TICKER
        _bench_ret = pd.Series(dtype='float64')
        with st.spinner(f'抓取 {PORTFOLIO_BENCHMARK_TICKER} 基準...'):
            try:
                _bdf = fetch_etf_price(PORTFOLIO_BENCHMARK_TICKER, period='1y')
                if _bdf is not None and not _bdf.empty and 'Close' in _bdf.columns:
                    _bench_ret = _bdf['Close'].pct_change().dropna()
            except Exception as _e_b:  # §1 fail loud:log + 下面走 warning,不吞成假曲線
                print(f'[etf_portfolio/bench] {type(_e_b).__name__}: {_e_b}')
        if _bench_ret.empty:
            st.warning(f'⚠️ 無法取得 {PORTFOLIO_BENCHMARK_TICKER} 基準價格，'
                       '略過累積報酬比較（不畫假曲線,§1）。')
        else:
            _cmp = compute_portfolio_vs_benchmark(
                _var_rets, {r['ticker']: r['actual_pct'] for r in rows}, _bench_ret)
            if _cmp['benchmark_ok'] and _cmp['n_common'] >= 2:
                _plot_portfolio_vs_benchmark(_cmp, benchmark_label=PORTFOLIO_BENCHMARK_TICKER)
                _p0, _p1 = _cmp['dates'].min(), _cmp['dates'].max()
                st.caption(
                    f'📏 共同交易日＝{_cmp["n_common"]} 日'
                    f'（{_p0:%Y-%m-%d} ~ {_p1:%Y-%m-%d}）;缺失日一律剔除、未填 0 或 ffill（§1 誠實)。'
                    + (f' 另因基準日與持股共同日不一致剔除 {_cmp["dropped_vs_benchmark"]} 日。'
                       if _cmp['dropped_vs_benchmark'] > 0 else ''))
                if _cmp['limiter'] is not None and _cmp['limiter_start'] is not None \
                        and _cmp['limiter_start'] > _p0:
                    st.caption(f'⚠️ 視窗受最短一檔 **{_cmp["limiter"]}**'
                               f'（{_cmp["limiter_start"]:%Y-%m-%d} 才有資料）壓縮,樣本偏短。')
                # §4.1 幣別誠實:美元計價持股(如 BND)為「原幣別」報酬,未含 USD/TWD 匯率
                _usd_used = [t for t in _cmp['tickers_used']
                             if holding_currency(t) == CURRENCY_USD]
                if _usd_used:
                    st.caption(f'💱 註:{"、".join(_usd_used)} 為美元計價,此處為「原幣別」累積報酬,'
                               '未計入 USD/TWD 匯率變動（**權重**已用今日即期匯率換算成 TWD 口徑,'
                               '但**報酬序列**仍是原幣別 —— 與 VaR 段同一誠實原則,不靜默混算)。')
                _fp, _fb = _cmp['final']['portfolio'], _cmp['final']['benchmark']
                if _fp is not None and _fb is not None:
                    _ex = (_fp - _fb) * 100
                    _colored_box(
                        f'期末累積報酬：組合 <b>{_fp*100:+.2f}%</b> vs '
                        f'{PORTFOLIO_BENCHMARK_TICKER} <b>{_fb*100:+.2f}%</b>'
                        f'&nbsp; 超額 <b>{_ex:+.2f}%</b>'
                        + ('&nbsp; ✅ 期間贏過大盤' if _ex >= 0 else '&nbsp; ⚠️ 期間落後大盤'),
                        'green' if _ex >= 0 else 'red')
            else:
                st.warning(f'共同交易日不足（{_cmp["n_common"]}<2），無法比較累積報酬。')
    else:
        st.info('無持股報酬資料，略過累積報酬比較。')

    # ── 📐 效率前緣（風險-報酬地圖）─────────────────────────────
    # ⚠️ **描述性視覺化,非規範性最佳化**:STATE.md:512 曾拒均值-變異數最佳化為「假精準」
    # (牴觸 §1)。這裡只把「你的組合」定位在歷史風險-報酬空間,疊隨機配置雲 + 前緣**參考**線,
    # **不**輸出「最適權重建議」。§7 對齊:年化 μ=mean(日報酬)×252、Σ=cov×252、
    # 組合 vol=sqrt(wᵀΣw)、Sharpe=ret/vol(rf=0)。計算下沉 L2 etf_calc.compute_efficient_frontier
    # (可單元測試、固定 seed 可重現),繪圖走 L4 etf_render。重用 VaR 段已抓好的 _var_rets + 權重。
    st.markdown('#### 📐 效率前緣（風險-報酬地圖）')
    st.caption('把「你的組合」畫在近1年歷史的「年化波動度 × 年化報酬」平面上,'
               '疊一片隨機配置的蒙地卡羅雲 + 前緣參考線,單純幫你**理解**組合在風險-報酬'
               '空間的相對位置(偏攻擊 / 偏防禦)。')
    if _var_rets:
        from src.compute.etf.etf_calc import compute_efficient_frontier
        from src.ui.render.etf_render import _plot_efficient_frontier
        from shared.signal_thresholds import (
            EFFICIENT_FRONTIER_N_SIM, EFFICIENT_FRONTIER_SEED,
        )
        with st.spinner('計算效率前緣（蒙地卡羅隨機配置）...'):
            _ef = compute_efficient_frontier(
                _var_rets, {r['ticker']: r['actual_pct'] for r in rows},
                n_sim=EFFICIENT_FRONTIER_N_SIM, seed=EFFICIENT_FRONTIER_SEED)
        if _ef['ok']:
            _plot_efficient_frontier(_ef)
            # §1 強制警語:描述性、對取樣窗極敏感、非投資建議
            st.caption('⚠️ 歷史估計,對取樣時間窗極度敏感;均值-變異數最適解實務上極不穩定,'
                       '僅供理解你的組合在風險-報酬空間的相對位置,非投資建議（§1）。'
                       '圖中「最小變異 / 最大夏普」為**歷史估計參考點,非建議**。')
            st.caption(f'📏 樣本＝{_ef["n_common"]} 個「全員皆有交易」的共同日;'
                       f'Sharpe 以無風險利率 **rf=0** 計算(僅供相對比較,非絕對夏普值)。'
                       '缺失日一律剔除、未填 0 或 ffill（§1 誠實）。')
            # §4.1 幣別誠實:美元計價持股(如 BND)為「原幣別」報酬,未含 USD/TWD 匯率
            _ef_usd = [t for t in _ef['tickers_used']
                       if holding_currency(t) == CURRENCY_USD]
            if _ef_usd:
                st.caption(f'💱 註:{"、".join(_ef_usd)} 為美元計價,此處報酬為「原幣別」,'
                           '未計入 USD/TWD 匯率變動（**權重**已換算為 TWD 口徑;'
                           '與 VaR / vs-0050 段同一誠實原則,不靜默混算）。')
        else:
            st.info(f'ℹ️ 無法繪製效率前緣：{_ef["note"]}。'
                    '（需 ≥2 檔有足夠共同歷史的持股,§1 不畫假圖。）')
    else:
        st.info('無持股報酬資料，略過效率前緣。')

    # ── 配息日曆 × 年度現金流預估 ──────────────────────────────
    st.markdown('#### 💰 配息日曆 × 年度現金流預估')
    st.caption('依過去12個月配息紀錄 × 持有股數推估未來現金流入。'
               '每股配息為**原幣別**；年收入與組合殖利率一律換算為 **TWD**，'
               '與上方「總現值」同幣別（§4.1 分子分母不得混幣）。')
    # v18.335 PR-H3:彙整邏輯抽至 etf_helpers.compute_etf_annual_cashflow SSOT
    # v19.64:同時收 per-ETF 月度明細 → etf_dividend_schedule 畫「ETF × 12 月」矩陣。
    from src.compute.etf.etf_dividend_schedule import (
        build_monthly_dividend_rows, pay_months_str,
    )
    _per_share_native = {}   # ticker → 近1年每股配息(原幣別;每股單價本就該用原幣)
    _sched_holdings = []     # per-ETF monthly_distribution(原幣別)供每月明細矩陣
    with st.spinner('抓取配息資料...'):
        for r in rows:
            _div_s  = fetch_etf_dividends(r['ticker'])
            # §4.1 B1-a:原碼 `int(current_value / _price)` 在單一換匯點之後會爆掉
            # (分子已換 TWD、分母仍是原幣 USD → 股數放大約 32 倍)。
            # 而 current_value / current_price 本來就恆等於 shares,直接用 shares 即可
            # (順帶修掉原本 int() 截斷可能把 200 股算成 199 的浮點誤差)。
            _shares = int(round(r['shares']))
            _cf = compute_etf_annual_cashflow(_div_s, _shares, lookback_days=365)
            if _cf is None:
                continue
            _per_share_native[r['ticker']] = _cf['annual_per_share']
            _sched_holdings.append({
                'ticker': r['ticker'],
                'name': _etf_name(r['ticker']),
                'monthly_distribution': _cf['monthly_distribution'],
                'n_payments': _cf['n_payments'],
                'shares': _shares,
            })

    # ── §4.1 幣別換算:美元計價 ETF(BND/AGG…)配息是 USD,不可直接加進 TWD。
    # B1-a v19.179:匯率**不再在這裡重抓** —— 直接用上方「單一換匯點」已取得的
    # `_fx_rate`(整頁同一個匯率、同一個 as-of)。原本這裡自己抓一次,會出現
    # 「配息用 A 匯率、現值用(沒有)匯率」的分子分母不同口徑,正是 12.20% 假殖利率的成因。
    # 另:換不了匯的美元持股已在單一換匯點被排除出 `rows`,故此處 any_needs_fx 恆為 False,
    # 保留該分支只作為第二道防線。
    _sched = build_monthly_dividend_rows(_sched_holdings, usdtwd_rate=_fx_rate_used)
    _monthly_twd = _sched['monthly_totals']

    # 「近1年配息預估」表改由 _sched['rows'] 建 —— 年收入一律取**已換匯 TWD**
    # (原碼 `_cf['estimated_income']` 是原幣別卻標「(元)」,BND 的 584 USD 被當 584 元)。
    _div_data = [{
        'ETF': _sr['ticker'],
        '幣別': _sr['currency'],
        '持有股數': int(_sr.get('shares') or 0),
        '近1年每股配息(原幣)': round(_per_share_native.get(_sr['ticker'], 0.0), 4),
        '預估年收入(TWD)': round(_sr['annual_twd']),
        '配息次數/年': _sr.get('n_payments', 0),
    } for _sr in _sched['rows']]

    if _div_data:
        _div_df = pd.DataFrame(_div_data)
        _div_df['預估年收入(TWD)'] = _div_df['預估年收入(TWD)'].apply(lambda x: f'{x:,}')
        st.dataframe(_div_df, use_container_width=True, hide_index=True)
        # §4.1 B1-a:分子(年現金流)與分母(總現值)**必須同幣別**。
        # 兩者現在都來自同一個換匯點的 TWD 口徑 —— 原碼分子已換匯、分母沒換,
        # 實機組合殖利率因此顯示 12.20%(真值約 3.9%),還被拿去下「殖利率優異」強結論。
        _total_annual_raw = _sched['annual_total_twd']
        _yoc = _total_annual_raw / total_value * 100 if total_value > 0 else 0
        _colored_box(
            f'💰 組合預估年度現金流入：<b>{_total_annual_raw:,.0f} 元 TWD</b>'
            f'（組合殖利率 {_yoc:.2f}% ＝ 年現金流 ÷ 總現值，同為 TWD 口徑）'
            + ('&nbsp; ✅ 每年現金流穩定，適合存股策略'
               if _yoc >= YIELD_LOW else '&nbsp; 🟡 殖利率偏低，可考慮增加高息ETF比例'),
            'green' if _yoc >= YIELD_LOW else 'yellow')
        if _yoc >= YIELD_MID:
            _strategy_conclusion(STRATEGY_VALUATION,
                                 f'組合殖利率 {_yoc:.2f}%，年現金流 {_total_annual_raw:,.0f} 元',
                                 '殖利率優異，現金流充沛，以息養股目標達成',
                                 '持續持有，配息再投入複利滾動')
        elif _yoc >= YIELD_LOW:
            _strategy_conclusion(STRATEGY_VALUATION,
                                 f'組合殖利率 {_yoc:.2f}%，年現金流 {_total_annual_raw:,.0f} 元',
                                 '殖利率合格，現金流穩定',
                                 '可維持，視需要提高高息 ETF 比例')
        else:
            _strategy_conclusion(STRATEGY_VALUATION,
                                 f'組合殖利率 {_yoc:.2f}%，年現金流 {_total_annual_raw:,.0f} 元',
                                 '殖利率偏低，現金流不足以息養股',
                                 '增加 00878/00713 等高息 ETF 比例')

        # §4.1:含美元 ETF 但抓不到匯率 → fail loud 提示,不靜默把 USD 當 TWD 加。
        # (第二道防線:換不了匯的檔已在單一換匯點被排除,正常不會進這個分支。)
        if _sched['any_needs_fx']:
            st.warning(
                '⚠️ 組合含**美元計價 ETF**,但 USD/TWD 匯率抓取失敗 —— '
                '這幾檔的配息**未換匯、不計入下方 TWD 總額**（避免把美元金額當台幣加）。'
                '點上方「🔄 強制重抓」可再試。')
        elif _sched.get('rate_used'):
            st.caption(fx_disclosure_caption(_sched['rate_used'], _fx_asof, _fx_source)
                       + '　—— 與上方總現值使用**同一個**匯率與同一個日期。')

        # 月度現金流長條圖(已換匯 TWD;全台股組合與原值相同)
        import plotly.graph_objects as _go_div
        _fig_div = _go_div.Figure(_go_div.Bar(
            x=[f'{m}月' for m in range(1, 13)],
            y=[_monthly_twd[m] for m in range(1, 13)],
            marker_color=TRAFFIC_GREEN,
            text=[f'{_monthly_twd[m]:,.0f}' if _monthly_twd[m] > 0 else ''
                  for m in range(1, 13)],
            textposition='auto',
        ))
        _fig_div.update_layout(
            title='未來12個月預估配息現金流（TWD，依歷史月份分配）',
            template='plotly_dark', height=260,
            paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
            margin=dict(l=0, r=0, t=32, b=0),
            yaxis_title='配息金額（TWD）',
        )
        st.plotly_chart(_fig_div, width='stretch')

        # ── 📅 每月配息明細（哪一檔・哪個月・配多少）── v19.64 每月月配息矩陣
        st.markdown('##### 📅 每月配息明細（哪一檔・哪個月・配多少 TWD）')
        st.caption('依過去 12 個月配息紀錄 × 你的持有股數推估。每格 = 該檔該月約可領（TWD）；'
                   '**頻率**看配息次數（月配/季配…），**年合計**是各檔一年總領。')
        _mx_rows = []
        for _sr in _sched['rows']:
            _row_d = {
                'ETF': _sr['ticker'],
                '名稱': _sr['name'],
                '頻率': _sr['freq'],
                '幣別': ('台幣' if _sr['currency'] == 'TWD'
                         else ('美元⚠️未換匯' if _sr['needs_fx'] else '美元→台幣')),
                '配息月份': pay_months_str(_sr['pay_months']),
            }
            for _m in range(1, 13):
                _v = _sr['monthly_twd'].get(_m, 0.0)
                _row_d[f'{_m}月'] = round(_v) if _v > 0 else 0
            _row_d['年合計'] = round(_sr['annual_twd'])
            _mx_rows.append(_row_d)
        # 依年合計高→低排序(領最多的排前面)
        _mx_rows.sort(key=lambda d: d.get('年合計', 0), reverse=True)
        # 加一列組合合計
        _tot_row = {'ETF': '　組合合計', '名稱': '', '頻率': '', '幣別': '',
                    '配息月份': ''}
        for _m in range(1, 13):
            _tot_row[f'{_m}月'] = round(_monthly_twd[_m])
        _tot_row['年合計'] = round(_sched['annual_total_twd'])
        _mx_rows.append(_tot_row)
        _mx_df = pd.DataFrame(_mx_rows)
        _month_num_cfg = {f'{_m}月': st.column_config.NumberColumn(
            f'{_m}月', format='%d') for _m in range(1, 13)}
        _month_num_cfg['年合計'] = st.column_config.NumberColumn('年合計', format='%d')
        st.dataframe(_mx_df, use_container_width=True, hide_index=True,
                     column_config=_month_num_cfg)
        st.caption('💡 想要「每月都有息」→ 挑不同**配息月份**的 ETF 湊成月月領；'
                   '同一個月一堆、其他月空白，代表現金流集中，可考慮錯開。'
                   '（此為**歷史推估**，實際配息與金額以各 ETF 公告為準）')
    else:
        st.info('⏳ 配息資料無法取得（可能為非配息型ETF或yfinance資料限制）')

    # ── 💰 配息稅後試算（二代健保 + 綜所稅二擇一）── L3 dividend_tax_service ──
    # §3.3:文案內的稅率/門檻一律由 L0 常數組出(不硬寫),兌現「改 L0 即全站同步」。
    from shared.dividend_tax_thresholds import (
        DIVIDEND_SEPARATE_TAX_RATE, MARGINAL_TAX_RATE_OPTIONS,
        NHI_SINGLE_PAYMENT_MIN_TWD, NHI_SUPPLEMENTARY_RATE,
    )
    from src.services.dividend_tax_service import get_dividend_tax_view
    _nhi_rate_txt = f'{NHI_SUPPLEMENTARY_RATE * 100:g}%'          # 2.11%
    _nhi_min_txt = f'{NHI_SINGLE_PAYMENT_MIN_TWD:,} 元'           # 20,000 元
    _sep_rate_txt = f'{DIVIDEND_SEPARATE_TAX_RATE * 100:g}%'      # 28%
    st.markdown('#### 💰 配息稅後試算（二代健保 ＋ 綜所稅）')
    st.caption(f'依近 1 年配息 × 持有股數，逐筆算二代健保補充保費（單筆 ≥ {_nhi_min_txt} 課 '
               f'{_nhi_rate_txt}、整元無條件捨去），綜所稅可選「合併 vs 分開」自動取較省。'
               '海外/美元 ETF 稅制不同，先排除標記。')
    _rate_labels = (['先不估（只算二代健保）']
                    + [f'{int(_r * 100)}%' for _r in MARGINAL_TAX_RATE_OPTIONS])
    _rate_pick = st.selectbox(
        '你的綜所稅邊際稅率', _rate_labels, index=0, key='_divtax_rate',
        help=f'選你落點的級距，系統自動比較「合併計稅 vs 分開計稅 {_sep_rate_txt}」取較省者')
    _marg = (None if _rate_pick.startswith('先不估')
             else MARGINAL_TAX_RATE_OPTIONS[_rate_labels.index(_rate_pick) - 1])
    _tax_view = get_dividend_tax_view(
        [{'ticker': r['ticker'], 'shares': r['shares']} for r in rows],
        marginal_rate=_marg)
    _ts = _tax_view['summary']
    if _ts['gross'] <= 0:
        st.info('目前組合近 1 年無台幣配息紀錄可試算（或持股皆為海外 ETF）。')
    else:
        _tc1, _tc2, _tc3, _tc4 = st.columns(4)
        _tc1.metric('稅前配息（近1年）', f"{_ts['gross']:,}")
        _tc2.metric('二代健保', f"−{_ts['nhi_premium']:,}")
        if _ts['income_tax'] is not None:
            _sgn = '−' if _ts['income_tax'] >= 0 else '+'   # 負=退稅 → 顯示 +
            _tc3.metric(f"綜所稅（{_ts['tax_method']}）",
                        f"{_sgn}{abs(_ts['income_tax']):,}")
        else:
            _tc3.metric('綜所稅', '未估')
        _tc4.metric('稅後淨額', f"{_ts['net_after_all']:,}")
        if _ts.get('tax_detail'):
            _td = _ts['tax_detail']
            _note = (f"合併計稅 {_td['combined']:,} ｜ 分開 {_sep_rate_txt} {_td['separate']:,} "
                     f"→ 系統採較省的「{_td['method']}」")
            if _td['best'] < 0:
                _note += "（負值＝股利可抵減 > 應納稅，實質退稅/節稅）"
            st.caption('🧮 ' + _note)
        if _tax_view['per_etf']:
            st.dataframe(pd.DataFrame(_tax_view['per_etf']),
                         use_container_width=True, hide_index=True)
        if _tax_view['overseas']:
            st.caption('🌏 海外/美元 ETF（稅制不同，未納入上表）：'
                       + '、'.join(_tax_view['overseas']))
        st.caption(f'※ 二代健保逐筆（月配每月各自比 {_nhi_min_txt}門檻）；綜所稅為年度合計估算，'
                   '實際以個人綜合所得與國稅局申報為準。')

    # 存入 session_state
    st.session_state['etf_portfolio_data'] = {
        'rows': rows, 'war_rows': _war_rows, 'rebal_actions': rebal_actions,
        # C1 v19.182:未評估存 'unknown' 而非捏造的 'neutral'(下游 AI prompt 讀它)
        'total_value': total_value, 'regime': (regime or 'unknown'),
        'loss_pct': loss_pct,
        # §2.2 provenance:下游(AI prompt / 診斷頁)要能知道這頁的 TWD 口徑
        # 是用哪個匯率、哪一天換的,以及有沒有持股被排除。
        'currency': 'TWD',
        'fx': {
            'usdtwd': _fx_rate_used,
            'as_of': _fx_asof,
            'source': _fx_source,
            'excluded_tickers': [str(_e.get('ticker')) for _e in _fx_excluded],
        },
    }
