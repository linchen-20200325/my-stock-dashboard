# New UI2 Reuse Matrix（KEEP AS-IS／WRAP／PORT／REIMPLEMENT／RETIRE LATER／DO NOT TOUCH）

- **狀態**：**隨 Architecture Gate 經客戶裁示 Q1～Q4 整體核准（2026-11-02；逐字見 DEC-123），待 #997 獨立稽核＋合併後凍結**；客戶未逐列裁示本矩陣（INFERENCE：隨整體核准）。（2026-11-02 客戶裁示 Q1～Q4 後更新；有意識的更新，不是漏刪；決策者 客戶（DEC-123 裁示）；原文刪除線保留）<br>原文：~~**Architecture Gate 草案，待客戶裁示**（隨 `docs/vnext/NEWUI2_ARCHITECTURE_GATE_2026-11-02.md` 一併送審；客戶 (5)-13「reuse matrix frozen」前 ⛔ 據以施工）。~~
- **日期**：2026-11-02　**基準**：工作樹＝PR #996 head `139e315b`（調查 invC 讀此 SHA；撰寫組 2026-11-02 `git fetch` 實查 `origin/main`＝`c1e10a62`，HEAD 比 main 多 1 個 docs commit）。以當下 `git fetch` 為準（DEC-118）。
- **決策來源**：客戶 2026-11-02 裁示 (5)-6「必須實查 repo 後分類：KEEP AS-IS／WRAP／PORT／REIMPLEMENT／RETIRE LATER／DO NOT TOUCH」（逐字見 `docs/DECISIONS.md` DEC-123）。
- **底稿**：調查 C（invC，2026-11-02，**單組唯讀**）：自寫 AST 掃描 433 個 .py（shared／src／scripts）抽 streamlit import、`session_state` 字面、`st.<UI>` 呼叫、I/O import、層間 import；對 `src/ui/views/*.py` 逐函式分「不直接引用 `st`／引用 `st`／引用 `st.session_state`」；計算每個 L1/L2/L3 模組的 importer 層；逐檔讀碼確認關鍵宣稱。
- **標記**：**FACT**＝invC 讀碼／grep／AST 實查；**INFERENCE**＝推論。
- ⚠️ **揭露（`CLAUDE.md` §-2 規則 6）**：**單組產出，未經第二組獨立驗證**。importer 集合以具名模組路徑比對；經套件 barrel／`__getattr__` 轉發的 import 歸到套件層 ⇒「只被 Old UI 用」「0 consumer」**非窮舉**。tests 分類為 regex 啟發式，數字是量級。全稱句一律附驗證方式或標「未窮舉」。
- ⚠️「pure（不直接引用 `st`）」≠「無 I/O」：views 的 `load_*` 函式不碰 `st` 但會呼叫 L3 取數。

---

## §0 分類定義

| 類 | 意義 | UI2 可否 import |
|---|---|---|
| **KEEP AS-IS** | 一字不改；UI2 直接 import（L0 常數／純 helper），或位於上游鏈（L1/L2/規則）UI2 不直接碰。**規則／公式類一律 change-frozen**〔客戶 (5)-1「禁止重寫既有 data／services／rules」〕 | L0：可；L1：⛔（經 L3）；L2／L3：經 feed |
| **WRAP** | 模組不改；UI2 只能經**新增的 feed／VM adapter**（additive，`src/services/ui2/*_feed.py`）間接使用 | 只經 feed |
| **PORT** | 邏輯須**搬家或解耦**才能給 UI2 用（UI 層 → L0／L3／presentation contract；session 隱性輸入 → 顯式參數）。原處保留至 RETIRE；**Old UI 原處一字不改**（新位置另建＋parity 測試）；**Legacy New UI 預設同法**（原處改 re-export 為備選，會動 production UI 檔、需客戶同意）。屬 migration 前置（Architecture Gate §5） | 搬到新位置後才可 |
| **REIMPLEMENT** | UI2 重寫（shell／nav／card／layout／chart container／狀態呈現），舊碼只當 reference | ⛔（只讀參考） |
| **RETIRE LATER** | 保留到 cutover＋Removal Gate 後才退場 | ⛔ 依賴 |
| **DO NOT TOUCH** | 凍結；UI2 ⛔ 修改、⛔ 消費（Old UI、LINE production、非 Digest AI 出口等） | ⛔ |

---

## §1 L0 — `shared/`（89 檔）、`src/config/`（5 檔）

| # | 模組／群組 | 類 | 理由 | 證據 | F/I |
|---|---|---|---|---|---|
| L0-1 | 規則／判定 SSOT：`allocation_decision`、`position_throttle`、`regime_arbiter`、`risk_cap_policy`、`risk_cap_history_policy`、`freshness_policy`、`input_provenance_policy`、`scoring_regime_gate`、`unified_verdict_thresholds`、`relative_thresholds`、`station_specs`、`macro_buckets`（16 燈 DangerSpec）、`dividend_station_thresholds`、`signal_thresholds`、`thresholds`、`health_thresholds`、`financial_health_thresholds`、其餘 `*_thresholds.py` | **KEEP AS-IS（change-frozen）** | 客戶 (5)-6 優先保留 deterministic rules／Risk Cap logic | AST：除 `fail_cooldown`／`cache_layer`／`app_cache` 外無 I/O import | FACT |
| L0-2 | 狀態／新鮮度／出處：`ui_state`（10 態 `UI_STATE_META`）、`staleness`、`data_freshness`、`trading_days`、`dated_value`、`price_asof_label`、`macro_provenance`、`holdings_data_short`、`vix_validity`、`asset_currency_gate`、`inst_net`、`na_drop_log` | **KEEP AS-IS**；UI2 經 VM 組 field-level freshness | Freeze §5.2 十態保留不改符號、四態是語意層；§9.5 freshness 只讀既有 SSOT | `holdings_data_short` 為 UI（`page_hold`）與 LINE（`holdings_digest_message`、`dividend_station_service`）共用「資料不足」判定（grep 4 檔） | FACT |
| L0-3 | Decision Digest 契約：`decision_digest`、`decision_digest_rules`（`RULE_ID_ALLOWLIST` 6 id）、`decision_digest_grounding`（G1～G6）、`decision_digest_terms`、`decision_digest_validator`、`strategy_class_schema` | **KEEP AS-IS**（Stage F 才擴 `SCHEMA_VERSION`） | rule id 只能用既有 6 個；candidates／industries 段缺＝Stage F 契約工作，不是 UI2 工作 | Freeze §12.1、§14.4 | FACT |
| L0-4 | 文案／顯示 SSOT：`compliance_copy`、`edu_tokens`、`etf_ui_labels`、`industry_codes`、`inst_labels`、`market_conclusion`、`colors`、`etf_codes`、`roc_calendar`、`sheet_id`、`secret_scrub`、`secret_md` | **KEEP AS-IS**（UI2 直接 import） | 純字串／純函式；`secret_scrub` 為 Freeze §12.2 強制前置 | 讀碼 | FACT（`colors` 由 UI2 token 層 WRAP＝INFERENCE） |
| L0-5 | `ia_nav4.py`（四頁 id／`PAGE4_LABELS`） | **KEEP AS-IS** | 四頁 IA SSOT（DEC-092／097；客戶 (5)-7） | ⚠️ `PAGE4_TO_VIEW` 指向 `ia_nav` legacy view id ⇒ UI2 路由需新映射（additive） | FACT |
| L0-6 | `ia_nav.py`（五頁／六向 `NAV_TREE`） | **RETIRE LATER** | 只服務 legacy D2 殼與五頁 view；`?legacy=1` rollback 仍依賴 | `app._nav4_resolve_legacy` 註解 | FACT |
| L0-7 | 計算 helper：`macro_compute`、`stats_helpers`、`calc_helpers`、`mk_test`、`macro_card`、`pcr_scale`、`margin_schema`、`tpex_schema`、`schemas`（pandera）、`parse_helpers`、`stock_buckets`、`sector_heatmap`、`global_lead_markets`、`lamp_direction_thresholds`、`macro_calibration`、`fred_series`、`etf_universe`、`finmind_subject_aliases`、`data_categories`、`http_diag`、`fetch_monitor`、`fail_cooldown`、`oauth_*_policy`、`dividend_frequency` | **KEEP AS-IS** | 上游 SSOT，UI2 不直接需要或只讀常數 | 讀碼 | FACT |
| L0-8 | `app_cache.py`、`cache_layer.py`（pickle 跨 session 快取） | **DO NOT TOUCH** | 為 `app.py`／舊流程服務的 L0 I/O helper；UI2 ⛔ 自建第二套快取（v3 §01「嚴禁 UI 層私自存放」） | 讀碼 | FACT（用途）／INFERENCE（UI2 不需） |
| L0-9 | `src/config/config.py`（EX-L0-1）、`data_config.py`、`stock_names.py`（V-L0-NAME-1） | **KEEP AS-IS** | EX-L0-1 合規；V-L0-NAME-1 屬既有待修、UI2 不觸發 | `CLAUDE.md` §8.2.A | FACT |
| L0-10 | `src/config/persona.py`（「股海老船長」AI 語氣） | **DO NOT TOUCH** | 只屬舊 AI 出口語氣；OneBrain（Stage G）另定 provider／vocab Gate | 讀碼 | FACT／INFERENCE |

## §2 L1 — `src/data/**`（59 檔）

> **UI2 硬規則（AI 總管暫定）**：UI2 程式碼 **0 個 `src.data.*` import**（不沿用 EX-PASSTHRU-1）。FACT：現有 `src/ui/views/**`、`src/ui_v2/**` 已是 0 個 `src.data` import（grep）。⇒ L1 對 UI2 一律 KEEP AS-IS（經 L3）或 WRAP（需新 L3 thin service）。

| # | 模組 | 類 | 理由 | 證據 | F/I |
|---|---|---|---|---|---|
| L1-1 | source adapters：`macro/macro_core`、`tw_macro`、`cbc_ef15m01`、`macro_snapshot`、`macro_cache_reader`、`stock/*_fetcher`（yield_pe／dividend／monthly_revenue／quarterly_financials／fundamentals_snapshot_loader／twse_holiday／market_close／mops_bulk／picker）、`core/data_loader`、`data_loader_inst_fetchers`、`financial_statements_fetcher`、`finmind_client`、`daily/daily_data_fetchers`、`etf/etf_fetch`、`sector_flow/reader`、`risk_cap/history`、`macro_fwd_test_store`、`portfolio/forward_test_store` | **KEEP AS-IS** | 客戶 (5)-6 優先保留 canonical data／source adapters | 已有 L3 consumer（importer 掃描） | FACT |
| L1-2 | `proxy/proxy_helper`、`yf_proxy`、`nas_server` | **KEEP AS-IS** | infra | `nas_server` 跑在 NAS（repo 內 0 importer） | FACT |
| L1-3 | `core/data_registry`、`core/provenance` | **KEEP AS-IS** | 來源註冊 SSOT（`CLAUDE.md` §2.1） | `provenance.prov_log` 被 Old UI 直呼 4 處 | FACT |
| L1-4 | `portfolio/gsheet_portfolio`、`oauth_state`、`oauth_nonce_store`（EX-OAUTH-1） | **WRAP**（只經 `holdings_service`／`me_account_service`／`portfolio_binding_service`） | 讀 `st.session_state` token；UI2 shell 需同等 OAuth bootstrap，但不改 OAuth | `app.py` 開機段直呼 `handle_oauth_callback`／`maybe_silent_reauth`／`sync_silent_marker`／`restore_sheet_binding_from_query` | FACT |
| L1-5 | `portfolio/gsheet_sa_reader`（Service Account，headless） | **KEEP AS-IS** | 未來 headless Digest 讀持股的唯一既有路徑 | 只被 `scripts/push_holdings_daily.py` 用 | FACT／INFERENCE |
| L1-6 | `portfolio/strategy_class_reader` | **KEEP AS-IS** | AB-4r 為 Digest 預備 | 0 consumer（非窮舉） | FACT |
| L1-7 | `notify/line_notify`、`telegram_notify`、`dispatch`、`chunk` | **DO NOT TOUCH** | LINE production 管道〔客戶 (5)-10「不要修改 LINE production」〕；純 I/O、無判斷 | `dispatch.send_notification` 24 行（讀碼） | FACT |
| L1-8 | **只有 Old UI 用、無 L3 的 L1**：`macro/foreign_flow_fetcher.fetch_foreign_flow_series`、`stock/share_capital_fetcher`、`stock/chip_concentration_fetcher`、`news/news_fetcher`（`fetch_stock_news`／`fetch_macro_news`）、`core` barrel 的 `fetch_bps`／`fetch_industry_category`／`fetch_financial_statements`、`etf` 的 `fetch_etf_holdings`／`fetch_etf_manager`／`fetch_etf_peer_history`／`fetch_etf_zh_name` | **WRAP**（若 Capability Map 保留該能力，需**新 thin L3**） | UI2 0-L1 規則下沒有 L3 就無法承接 | importer 只有 Old UI（＋scripts） | FACT（barrel 歸屬未窮舉） |
| L1-9 | **Old UI 直取的 private symbol**：`data_loader._fm_raw_headers`（V-PICKER-PRIV-1）、`yield_pe_fetcher._twse_official_pbratio`、`src.data.etf._fetch_news_for`／`_fetch_sector_returns`／`_fetch_holdings_yahoo_tw` | **PORT**（轉 public L3 介面）— migration 前置 M2 | v3 §01 排除③：private symbol 不是統一介面；T16（PB 河流）依賴 `_twse_official_pbratio` | `section_357_valuation._fetch_pbratio_from_twse` | FACT |
| L1-10 | `macro/leading_indicators.render_leading_table`（V-LEAD-RENDER-1） | **PORT**（render 移出 L1；資料留 L1） | L1 內定義 render fn | consumer＝Old UI `section_chips`、`tab_macro` | FACT |
| L1-11 | `macro/macro_alert.alert_summary`（L4 lazy fallback） | **KEEP AS-IS** | 只被 L4 `macro_ui_components` 用（EX-PASSTHRU-1）；UI2 不需 | importer 掃描 | FACT／INFERENCE |

## §3 L2 — `src/compute/**`（72 檔）

| # | 模組 | 類 | 理由 | 證據 | F/I |
|---|---|---|---|---|---|
| L2-1 | deterministic 動作／評估核心：`etf/dividend_station`（`action_branch` 七分支、`suggest_action`）、`scoring/*`（`scoring_engine`、`scoring_helpers`、`unified_verdict`、`exit_signals`）、`screener/*`、`macro/macro_helpers`（`compute_five_bucket_summary`）、`macro/dated_inputs`、`input_provenance`、`warroom_summary`、`daily_key_alerts`、`lamp_direction`、`macro_session_patch`、`health/*`、`risk/concentration`、`inst_sanity`、`reconcile`、`risk_contribution`、`risk_control`、`etf/*`（calc／helpers／scoring／recommendation／fx／asset_lag／dividend_tax）、`strategy/tech_indicators`、`v5_modules`、`sector_flow`、`trading_calendar` | **KEEP AS-IS（change-frozen）** | 客戶 (5)-6；Freeze §6.4 正式動作來源在 `dividend_station.action_branch`＋`StockAssessment.swap_level` | 讀碼 | FACT |
| L2-2 | `compute/notify/*`（`holdings_digest_message`、`market_alert_banner`、`signal_message`、`technical_snapshot`、`watchlist_message`、`watchlist_triggers`、`ai_judgment`、`weekly_review_prompt`） | **DO NOT TOUCH（LINE production）** | 只被 scripts／L3 週報用；⚠️ 含**第二套動作語意**（§8） | importer 掃描 | FACT |
| L2-3 | 只被 Old UI 用的 L2（無 L3）：`macro/flow_engine`、`etf/etf_smart_analysis`、`portfolio_gates`、`portfolio_coherence`、`etf_dividend_schedule`、`etf_categories`、`screener/scorability` | **WRAP**（保留則需新 thin L3） | UI2 只經 feed | importer 只有 Old UI（＋L2） | FACT（非窮舉：barrel） |
| L2-4 | 個股買賣語意：`strategy/entry_stop_levels`、`overextension`、`v4_strategy_engine`、`pattern_targets`、`portfolio_manager`、`scoring/exit_signals`（三維出場「建議減碼／強烈出場」） | **DO NOT TOUCH**（T21 critical；待 deterministic action contract 或退場 Gate） | HI-3 未核准、UI2 不承接；`exit_signals`「🟠 建議減碼」不在 `RULE_ID_ALLOWLIST` | Capability Map T21 | FACT |
| L2-5 | `etf/etf_quality.render_quality_badge` | **PORT**（render 移出 L2）；`compute_etf_quality` 本身 KEEP | L2 函式內 `st.caption`／`st.markdown`／`st.columns`；檔頭註解宣稱「無 st.markdown」**與碼不符** | AST；consumer＝Old UI `etf_tab_single` | FACT |
| L2-6 | `risk/risk_radar`（V-RADAR-1：L2 做 HTTP） | **DO NOT TOUCH** | 既有 known violation；UI2 不需 | Freeze §11：`valuation_level` 無人產生 | FACT |
| L2-7 | `macro/health_calibration`、`macro_forward_test` | **KEEP AS-IS** | cron／校準用 | 讀碼 | FACT |

## §4 L3 — `src/services/**`（58 檔）

欄「SS」＝檔內 `st.session_state`：**R**＝讀、**W**＝寫、**—**＝無（grep＋讀碼；註解內字樣已排除）。

| # | 服務 | SS | 類 | 理由＋證據 | F/I |
|---|---|---|---|---|---|
| S1 | `decision_digest_builder` | — | **KEEP AS-IS** | 純函式、只 import 標準庫＋L0；**0 production caller**；`MAX_ACTIONS=3` 截斷、無 candidates／industries（Freeze §14.4）。UI2 Digest Viewer／OneBrain 容器的未來來源 | FACT |
| S2 | `decision_digest_summary`（`build_rule_summary`） | — | **KEEP AS-IS** | 純函式；Freeze §15.4 grounding fallback；0 caller | FACT |
| S3 | `dividend_station_service` | — | **WRAP**（只取規則輸出：`get_station_rows`／`build_station_digest`／`build_switch_advice`／`get_station_macro`／`get_switch_in_candidates`） | headless 可跑（LINE cron 直接用）。⚠️ `build_ai_summary`／`build_summary_prompt`（Gemini）⛔ 給 UI2（Freeze §15.6） | FACT |
| S4 | `holdings_service.get_holdings` | — | **WRAP** | 唯讀、無 `st.*`；經 `gsheet_portfolio` 間接依賴 OAuth session | FACT |
| S5 | `valuation_service` | — | **WRAP** | `get_pe_name_maps`／`get_stock_dividends`；Freeze §10 Current 估值來源 | FACT |
| S6 | `market_twii_view_service` | — | **KEEP AS-IS** | 已是 view-shaped 薄讀取層（`TwiiTrendView`）；UI2 feed 的先例。📌 **2026-11-03 已由 `src/services/ui2/real_feed.py` 使用**（`get_twii_trend_view(1)`，NUI2-REAL-FEED A 批；service 本身未改） | FACT |
| S7 | `target_industry_service`、`trading_calendar_service`、`calibration_status_service` | — | **KEEP AS-IS** | 薄、唯讀、無 session | FACT |
| S8 | `stock_chips_service`、`portfolio_deep_service`、`sector_heatmap_service`、`stock_grp_service`、`health_history_service` | — | **WRAP** | 唯讀 L3；`portfolio_deep_service` 檔頭明文不寫 session | FACT |
| S9 | `sector_flow_service` | —（參數由 L5 從 session 取） | **WRAP** | etf tickers／sheet_id「由 L5 從 session_state 取」傳入 ⇒ feed 負責取值 | FACT |
| S10 | `fundamental_screener_service`（`get_ranked_picks`）、`rs_leader_service`、`shortage_screener_service` | — | **WRAP** | st 只為 cache；`get_ranked_picks`＝畫面與 cron 同源排名。⚠️ regime 濾網只在畫面路徑傳入（`app.py` 選股網註解：「凍結 cron／MCP／推播三處維持 None」）⇒ UI2 沿用同一 regime 解析規則（OLD-8） | FACT |
| S11 | `financial_health_engine.analyze_financial_health` | — | **WRAP（只允許 `api_key=""` 規則路徑）** | 新 UI `page_inspect` 以 `""` 呼叫；有 key 時走 `_gemini_call`＝非 Digest AI | FACT |
| S12 | `watchlist_service`（加入觀察）、`forward_test_service`、`risk_cap_history_reader_service`、`force_refresh_service` | — | **WRAP** | 目前只有 `app.py` consumer；UI2 加入觀察 CTA（Freeze §3.3，現 disabled）／Audit 頁需要 | FACT |
| S13 | `me_account_service`、`portfolio_binding_service` | R（經 gsheet／oauth） | **WRAP** | 👤 我的頁 L3；OAuth／Sheet 綁定一律走它，UI2 ⛔ 直碰 `oauth_state` | FACT |
| S14 | `macro_state_locker`（`get_macro_state`、`calculate_system_state`） | —（寫 `macro_state.json`） | **KEEP AS-IS（change-frozen）** | Risk Cap 規則引擎與 canonical 總經契約；`get_macro_state(require_valid_risk_cap=True)` 只認 `risk_cap_state.json` | FACT |
| S15 | `macro_engine_inputs`、`macro_fetch_orchestrator`（回 bundle，無副作用）、`market_strategy` | — | **KEEP AS-IS** | 規則輸入組裝；`load_engine_inputs_from_session(session, now)` 以參數收 session（唯讀） | FACT |
| S16 | `risk_cap_apply` | R（參數傳入，唯讀）；寫檔不寫 session | **KEEP AS-IS** | 檔頭：「不 import streamlit、**不寫 session**」；寫 `risk_cap_state.json`＋`macro_state.json`（原子） | FACT |
| S17 | `warroom_apply.compute_and_store_warroom_summary` | **R＋W**（寫／pop `warroom_summary`） | **WRAP**（只經 `refresh_macro_now` 觸發）；PORT 延到 Stage F | 讀 `load_section_inputs(st.session_state)`、寫 `st.session_state['warroom_summary']` | FACT |
| S18 | `market_assessment_apply.compute_and_apply_market_assessment` | **R＋W**（寫 `mkt_info`） | 同 S17 | 讀 `m1b_m2_info`、寫 `mkt_info` | FACT |
| S19 | `macro_session_apply.apply_macro_bundle` | **W**（`session_state.update(patch)`／pop） | 同 S17 | 檔頭：「import streamlit **只為 `st.session_state`**」 | FACT |
| S20 | `jingqi_calc`、`macro_trio_orchestrator`、`macro_registry_patch`、`data_registry_scanner` | **R＋W**（`jingqi_info`／`m1b_m2_info`／`bias_info`／`macro_info`／`data_registry`） | 同 S17（`macro_registry_patch` 只被 Old UI 用 → RETIRE LATER 候選） | grep 實查各自寫入 key | FACT |
| S21 | `macro_refresh_service.refresh_macro_now` | R＋W（整條鏈寫 session） | **WRAP（＝UI2 主 Update CTA 唯一入口）** | 已證可 headless：`risk_cap_history_service.run_headless_refresh`＋workflow `risk_cap_history_poc.yml` | FACT |
| S22 | `section_inputs.load_section_inputs(session)` | R（參數） | **KEEP AS-IS** | 收 dict 參數、不 import streamlit；現行「session → 結構化輸入」唯一 adapter | FACT |
| S23 | `allocation_service`（`get_allocation`、`get_macro_regime`、`register_cap`、`apply_vix_veto`、`apply_ring_gate`、`register_conflict`） | **R＋W**（讀 `warroom_summary`／`macro_info`／`li_latest`／`cl_ts`；寫 allocation cache、extra caps、conflicts） | **PORT**（Stage F 前置：session-free 簽名）；UI2 過渡期 **WRAP**。⚠️ **session-free 簽名會改既有 service，未經客戶 Gate 不得做** | Old UI `src/ui/tabs/macro/section_mid.py` 在 render 時呼叫 `apply_vix_veto`／`apply_ring_gate`／`register_conflict`（grep 唯一 caller）。**更正（2026-11-02 獨立稽核 F4，撰寫組讀碼複核）**：`get_allocation` 以 `_derive_intrinsic_caps()` **自行重算** VIX 否決權與三環第一環，並**先剔除同名登記**（`_INTRINSIC_CAP_NAMES`）⇒ render 期的 cap 登記**不影響建議持股數字**；**只有 `register_conflict` 的揭露文字**會隨舊頁有無 render 而不同（違 Freeze §14.2 的程度降為「揭露文字」）。📌 **2026-11-03 `get_macro_regime(strict=True, require_valid_risk_cap=True)` 已由 `src/services/ui2/real_feed.py` 使用**（只讀位階欄位；`get_allocation` 與寫入函式 ⛔ 使用，G2F 鎖定；service 本身未改、session-free 簽名仍待客戶 Gate） | FACT（讀碼：`get_allocation`、`register_cap` docstring v19.170） |
| S24 | `macro_v2_service`、`reconcile_service`、`data_registry_summary_service` | R（讀 session 指定 key） | **WRAP** | 唯讀；Audit 頁需要 | FACT |
| S25 | `risk_cap_history_service` | R（headless session） | **KEEP AS-IS** | VN1-STORE PoC | FACT |
| S26 | `ai_qa_service.run_agent`（Gemini 工具迴圈、讀 session warroom） | R | **DO NOT TOUCH**（UI2 ⛔ consume） | 新 UI `page_why` 仍在用；非 Digest 輸入＝違 Freeze §15.1；Stage G 取代 | FACT |
| S27 | `app_ai_service`（`gemini_call`、金鑰池、`build_llm_context`） | R | **RETIRE LATER**（Stage G 後） | `page_hold` ⑦ 直呼 `gemini_call`（`FUI-HOLD-GEMINI-DIRECT`）；`build_llm_context` 0 caller | FACT |
| S28 | `ai_fetcher.post_gemini` | — | **KEEP AS-IS** | LINE／週報／財報 AI 共用 HTTP wrapper；OneBrain provider adapter 屆時可 WRAP | FACT／INFERENCE |
| S29 | `ai_structured_summary` | — | **DO NOT TOUCH** | 舊 AI prompt 元件（L4／Old UI consumer） | FACT |
| S30 | `weekly_review_service` | — | **DO NOT TOUCH（LINE production）** | 自建「簡版 headless 大盤定調」（`_macro_lite_lines`）＋Gemini 逐檔建議 ⇒ **第二套市場判讀**（§8） | FACT |
| S31 | `daily_checklist` | — | **RETIRE LATER** | 純 re-export barrel，含 known violation（L3→L4 8 個 render fn，V-CHECKLIST-1） | FACT |
| S32 | `etf_scoring_service`、`etf_sector_service`、`etf_grp_compare_service`、`yield_screener_service`、`dividend_tax_service`、`portfolio_analysis_bridge`、`watchlist_health_service` | — | **WRAP**（若能力保留） | consumer 多為 Old UI／L3／scripts | FACT |
| S33 | `__init__` | — | **KEEP AS-IS** | — | FACT |

- **寫 session 的 `*_apply`**（FACT，grep `session_state[...] =`／`.update`／`.setdefault`／`.pop`）：`warroom_apply`、`market_assessment_apply`、`macro_session_apply`＝**寫**；`risk_cap_apply`＝**不寫 session**（只寫兩個 json 檔）。另 `jingqi_calc`／`macro_trio_orchestrator`／`macro_registry_patch`／`data_registry_scanner`／`allocation_service` 也寫 session。
- **services 內 `st.*` UI 呼叫**：0（grep 列舉 API 名；命中全在 docstring／註解；**非窮舉**其他 API 名）。

## §5 Legacy New UI — `src/ui/views/**`（15 檔，24,470 行）、`src/ui_v2/**`（13 檔）

- **FACT（routing）**：預設四頁只掛 `page_market`／`page_target`／`page_hold`／`page_me`；`page_today`／`page_find`／`page_inspect`／`page_why`／`shell_nav` 只在 `?legacy=1`。**但它們是四頁的依賴樞紐**：`page_market`／`_market_blocks` 用 `page_today` 約 30 個符號；`_target_blocks` 用 `page_find`＋`page_inspect` 約 40 個符號（grep 計數）。
- **FACT（跨代依賴）**：Legacy New UI 從 **Old UI** import：`src.ui.tabs.tab_today`（`Card`／`Note`／`MAX_COLS`／`scrub_state_glyphs`，6 檔用）、`src.ui.tabs.tab_macro_v2`、`src.ui.tabs.tab_stock_picker.summarize_factor_hits`、`src.ui.render.station_cards`、`src.ui.render.macro_v2_cards`、`sector_flow_render`、`sector_heatmap_render`。

| # | 模組 | 類 | 理由＋證據（fnscan：pure／st／ss 函式數） | F/I |
|---|---|---|---|---|
| V1 | `page_market.py`（786 行；18／6／3） | **REIMPLEMENT**（版面）＋**PORT**（`regime_source_text`／`status_line`／`danger_clause`／`regime_clause`／`card_badge_text`／`raw_rows`／`inst_rows` 等 pure 18） | 版面依 Q3=A Mobile-first 重做；pure 句型是已過客戶字樣審的資產 | FACT |
| V2 | `_market_blocks.py`（45／14／1） | **PORT**（`build_market_risks`、`hero_risk_*`、`risk_panel_rows`、`basis_*`、`twii_chart_frame/spec`、`chart_*_fold`、`chart_d_table_rows`…）＋**REIMPLEMENT**（`render_*` 14） | `build_market_risks` 已實作「冷啟動不出列、全灰＝insufficient ⛔ 硬選最差」等 Missing 語意；依賴 `page_today.MacroReadout` | FACT |
| V3 | `page_target.py`（52 行） | **REIMPLEMENT** | 純版面組裝 | FACT |
| V4 | `_target_blocks.py`（58／25／2） | **PORT**（`build_candidate_rows`、`build_industry_matrix`、`rank_industries`、`freshness_*`、`screen_summary`、`candidate_csv_bytes`…）＋**REIMPLEMENT**（render） | ⚠️ `kind_chip_text`／`count_chips`／`PE_BASIS_CHIP` 以 `guard_chip` 承載判型／計數／估值口徑＝**違反 Freeze §4.2**，⛔ 原樣 port，改 Neutral/Info；依賴 `tab_today.scrub_state_glyphs`（Old UI） | FACT |
| V5 | `page_hold.py`（5,759 行；100／8／2） | **PORT**（`build_action_card`／`build_todo_card`／`build_confidence_card`／`build_position_cap_card`／`build_switch_card`／`build_macro_stage_card`／`build_stress_card`／`build_var_card`…，與 `load_*`）＋**REIMPLEMENT**（render）；**⑦ `load_ai_summary`／`build_ai_summary_card`＝⛔ port** | builder 回傳 Old UI `tab_today.Card` ⇒ 無法直接 WRAP，須搬到中立 VM 型別；「訊號可信度」標籤待 `FUI-CONFIDENCE-LABEL-RENAME`；⚠️ `build_macro_stage_card` 的 ④ `posture_range`（`compute_position_throttle()`，**未套天花板**）⛔ 整包搬——見 Architecture Gate §5.4 警語與 §10.3 L7 | FACT |
| V6 | `page_me.py`（16／6／12） | **PORT**（`build_account_card`／`build_sheet_card`／`build_content_card`／`bind_result_message`）＋**REIMPLEMENT**；OAuth callback 類（`_on_*`）**WRAP** 經 `me_account_service` | ss 函式最多（12）＝session 互動密集 | FACT |
| V7 | `page_today.py`（4,121 行；pure 67） | **PORT**（`load_macro_readout`、`build_indicator_tiles`、`build_bucket_tiles`、`build_verdict_tiles`、`danger_completeness`、`coverage`、`_load_regime`／`_load_danger`／`_load_key_alerts`／`_load_lamp_directions`）→ 之後 **RETIRE LATER** | 不在預設導覽，但 `page_market` 依賴；內含 `_assert_*` 契約守衛 | FACT |
| V8 | `page_find.py`（pure 36）、`page_inspect.py`（pure 50）、`page_why.py`（pure 65） | **PORT**（`load_screen_result`／`build_screen_result_card`／`build_sector_flow_card`；`load_stock_readout`／`load_valuation`／`load_chips`／`load_etf_readout`／`build_*_card`／`classify_kind`；`load_sources`／`build_spec_flag_cards`／`build_lights_card`／`build_registry_card`／`build_calibration_card`／`build_reconcile_card`）→ **RETIRE LATER**；`page_why.load_qa`／`compose_qa_message`（AI QA）**⛔ port** | `_target_blocks` 依賴 F／I；`page_why` 是 👤 我的／Audit 能力主要現成實作 | FACT |
| V9 | `_ui_kit.py`（5／4／1） | **REIMPLEMENT**（grid／card／section_header／single_submit_form）＋**PORT**（`banned_signal_glyphs`／`assert_signal_text_clean`） | 依賴 Old UI `tab_today.Card` | FACT |
| V10 | `risk_cap_gate.py`（pure 6／零 st） | **PORT（→ L0，字串逐字不改）** — migration 前置 M1 | `has_system_risk_cap` 決定「建議持股：無法判定」＝風控閘門住在 L5；客戶逐字字串（PQ-C6-3）；Q1=A `⬜ 無法判定` 由此延伸；VM（L3）依 R5 ⛔ import L5 | FACT |
| V11 | `shell_nav4.py` | **REIMPLEMENT**（UI2 shell／nav） | 四頁 label 沿用 `ia_nav4`；UI2 頁狀態 key 用 `ui2_` 前綴（不沿用 `_nav4_page`，避免回滾互污） | FACT／INFERENCE |
| V12 | `shell_nav.py`（D2 殼） | **RETIRE LATER** | legacy 專用 | FACT |
| U1 | `src/ui_v2/compact.py`（純字串、無 st） | **PORT**（解耦後沿用 chip／`SafeHtml`／`META_KINDS`） | ⚠️ `compact → markup → blocks → page_find/hold/inspect/today/why`（五頁版面契約）傳遞依賴舊 IA；`unavailable` kind 須改名 `unwired`（Freeze §5.3）；新增 Danger／Positive／Neutral tone 只加不改（§4.3） | FACT |
| U2 | `src/ui_v2/markup.py`（純字串） | **PORT**（`card_html`／`fold_*_id`／`badge_html`／`page_css` 解耦 `page_today` 層表） | 模組層 `_TIERS_ON_PAGE`／`_BLOCK_COLS_USED` 由 `page_today` 推導 | FACT |
| U3 | `src/ui_v2/tokens.py`、`components.py` | **WRAP**（design token／元件規格；`MAX_COLS=3`、`BREAKPOINTS`、`resolve_cols`） | 純資料；`tokens.LIGHT` 有 `TBD`（`TokenNotSpecifiedError`） | FACT |
| U4 | `src/ui_v2/blocks.py`、`page_today.py`／`page_find.py`／`page_hold.py`／`page_inspect.py`／`page_why.py`（版面契約）、`render.py`、`app_today.py` | **RETIRE LATER** | 五頁 IA 版面契約，已被四頁 IA 取代；`app_today.py` 是獨立 `streamlit run` 入口（不在測試射程內） | FACT |

## §6 Old UI — `src/ui/tabs/**`（59）、`src/ui/etf/**`（8）、`src/ui/pages/**`（8）、`src/ui/render/**`（15）、`app.py` 內嵌區塊

**預設：全部 DO NOT TOUCH（只讀 reference）**〔客戶 (5)-4〕。下列為「業務邏輯混在 UI、UI2 需要卻無對應 service」＝**migration 前置（PORT 到 L0／L2／L3；Old UI 原處一字不改、另建＋parity 測試；舊處保留至 Removal Gate）**：

| # | 位置（檔＋符號） | 類 | 為何 UI2 需要 | PORT 去向（INFERENCE） | F/I |
|---|---|---|---|---|---|
| OLD-1 | `src/ui/tabs/tab_today.py`：`Card`／`Note`／`MAX_COLS`／`scrub_state_glyphs`／`classify_macro_contract`／`build_status_bar_card(s)`／`macro_attempt_*`／`upstream_error_why` | PORT | Legacy New UI 6 檔 import；卡片型別與 macro 契約分類是全部 builder 的回傳型別 | 中立 VM 型別＋L0 presentation 分類函式 | FACT |
| OLD-2 | `src/ui/tabs/tab_macro_v2.py`：`build_rows`／`bucket_summary`／`summary_coverage`／`overall_verdict`／`parallel_verdict` | PORT | 「指標危險度」worst-of rollup＋N/M 覆蓋句；`page_today._load_danger` 用（📊 市場 L1 依賴） | L2／L3（與 `P1R-FIVE-BUCKET-L3` 同方向） | FACT |
| OLD-3 | `src/ui/render/station_cards.py`：`judged_count`／`is_fully_judged`／`aggregate_judged`／`tally_states`／`cruise_or_gap`／`level_meaning` | PORT | 「沒事 vs 判不出」gate（Freeze §6.2、Q2-3／Q2-4）；docstring 明寫「gate 只做在畫面這一層、刻意不改 `suggest_action`（因同時餵 LINE）」 | L0／L3 System Action 呈現聚合（⛔ 改 `suggest_action`） | FACT |
| OLD-4 | `src/ui/render/macro_v2_cards.py`：`band_meta`／`threshold_text`／`BAND_META`／`fmt_value`／`ohlc_problems` | PORT | `page_today` lazy import | L0 presentation | FACT |
| OLD-5 | `src/ui/tabs/tab_stock_picker.py::summarize_factor_hits` | PORT | `page_find` 用（候選表因子命中片語，「掃失敗不假報 0」） | L3（screener service 旁） | FACT |
| OLD-6 | `src/ui/tabs/stock_sections/section_357_valuation.py`：`_render_dividend_river`（TTM 365D rolling 殖利率）、`_render_pe_river`（TTM EPS 4 季 rolling）、`_render_pb_river`、`_fetch_pbratio_from_twse` | PORT | Capability Map **T16 critical**（Freeze §10 Historical） | L2 純函式（只搬「歷史實際值」）；PB／357 倍數帶＝HI-3 ⛔ 搬情境線 | FACT |
| OLD-7 | `src/ui/tabs/macro/section_mid.py`：render 期間 `apply_vix_veto`／`apply_ring_gate`／`register_conflict` | PORT（Stage F 前置；低優先） | **只有 conflict 揭露文字**隨 render 改變；建議持股數字不受影響（`get_allocation` 重算＋剔除同名登記；S23 更正） | 移除 render 期 `register_conflict`——需客戶授權動 Old UI，或由 L3 吸收使該寫入成為 no-op。⚠️ **兩者都會改既有 Old UI／service，未經客戶 Gate 不得做** | FACT／INFERENCE |
| OLD-8 | `app.py` GROUP 2「🔭 選股網」內嵌區塊（V-APP-1）：regime 解析（`get_macro_regime()['regime']` 僅在已評估時傳）＋`get_ranked_picks`＋三個掃描 | PORT | UI2 🎯 標的頁需同一個 regime 濾網規則；目前只有畫面路徑傳 regime | L3：`fundamental_screener_service` 的 caller contract | FACT |
| OLD-9 | `src/ui/etf/etf_tab_smart.py` 5 個 `@st.cache_data`（V-SMART-CACHE-1） | PORT | ETF 智慧分析若保留 | cache 下沉 L1／L3 | FACT |
| OLD-10 | Old-UI-only L1/L2（§2 L1-8、L1-9；§3 L2-3） | （群組指標列；分類見 L1-8＝WRAP、L1-9＝PORT、L2-3＝WRAP） | 能力守恆（Capability Map 41 列舊獨有） | 新 thin L3 | FACT |
| OLD-11 | `app.py` 開機段：`set_page_config`、OAuth callback 三連呼、`_nav4_resolve_legacy`、`render_portfolio_status_bar`、`render_macro_compass`、置底常駐條 `_gl_slot` | **WRAP** | UI2 shell 需同等 bootstrap | UI2 shell 呼叫同一組 L1 OAuth API（經 L3）；不改 | FACT |

其餘 Old UI（`tab_macro`、`tab_stock*`、`stock_grp_sections`、`etf_tab_*`、`pages/health_inspector`、`data_coverage`、`calibration_ui`、`render/chart_plotter` 等）＝**DO NOT TOUCH**；`etf_tab_dividend_station` 已全經 `dividend_station_service`（讀碼 8 處 import），無額外 PORT 需求。

## §7 tests/（653 個 `test_*.py`；regex 啟發式分類，**非人工逐檔**）

| 群 | 量級 | 類 | 說明 |
|---|---|---|---|
| Domain（只 import shared／services／compute／data／config） | ≈298 | **KEEP AS-IS** | validated domain tests；UI2 的回歸底座。含 `test_decision_digest_*`、`test_batch_z65`（risk cap）、`test_macro_state_*` 等 |
| `test_c3_layering_guard.py` | 1 | **KEEP＋擴充** | ⚠️ UI2 新目錄**必須同 PR 登記** `_PATH_LAYERS`／`_MODULE_LAYERS`，否則 `_layer_of_file()` 回 None、五條規則對 UI2 靜默失效（`src/ui_v2` 前例）。現行規則只看 import：**不偵測** L2 `st.caption` 類 UI 呼叫、L3 `session_state` 使用、L5→L5 跨代 import ⇒ UI2 另立 G2／G4／G9（Architecture Gate §9） |
| Old-UI-bound（import `src.ui.tabs/etf/pages/render`，不含 views） | ≈148 | **DO NOT TOUCH**（隨 Old UI Removal Gate 處理） | — |
| New-UI-bound（import `src.ui.views`／`src.ui_v2`；含混用 48） | ≈130 | **RETIRE LATER，但先 PORT 斷言** | 例：`test_p04_hold_view`、`test_page_market`、`test_uim_market_page`、`test_uit_target_page*`、`test_p0x_view_mount_claims`、`ui_v2/test_*`（9）。⚠️ 大量是**語意 invariant**：`test_xv_h1ext_missing_not_hold`、`test_xv_h3_fx_not_summed`、`test_xv_asof`、`test_v2_silent_fail_b*`（13 檔）、`test_sec_*` scrub、`test_dec074_breadth_gate`、`test_nfa_nonfinite_gray` ⇒ cutover 前**先改寫成 UI2 presentation-contract 測試並轉綠**，否則退場即失守（`NUI2-NEWUI-SEMANTIC-TEST-PORT`）。`ui_v2/test_compact`／`test_markup`／`test_tokens` 隨 U1～U3 一起 PORT |
| 其他（無 src.ui import 但提到 app.py／AppTest，或無法歸類） | ≈77 | 未逐檔判定 | 分類器以字串比對 `app.py`／`AppTest`，誤判率未量測（INFERENCE：多數仍屬 domain） |

## §8 LINE／推播呼叫鏈與「第二套大腦」判定（FACT 為主；本批 ⛔ 改 LINE production）

- **現行排程**（FACT，`.github/workflows/*.yml`）：`push_holdings_daily.yml`（cron `30 22 * * 0-4`＝TW 週一～五 06:30）、`push_weekly_report.yml`（cron `0 21 * * 0`＝TW 週一 05:00）＝**自動**；`push_daily_signals.yml`、`push_watchlist_signals.yml`＝**排程已停用、只留 `workflow_dispatch`**。
- **鏈**：每日持股 `scripts/push_holdings_daily.py` → `gsheet_sa_reader` → `dividend_station_service`（**與 UI 同一引擎**）→ `market_alert_banner`（讀 `macro_cache_reader`）→ `holdings_digest_message.format_holdings_message` →（有 key）`post_gemini` 潤稿 → `dispatch.send_notification`；週報 `weekly_review_service`（自建定調＋Gemini 逐檔建議）；手動 `push_daily_signals`（`ai_judgment`）、`push_watchlist_signals`（三維出場「🟠 建議減碼／🔴 強烈出場」）。
- **判定**：(1) 持股個別動作＝同一大腦（低風險）；(2) 🔴 **第二套動作權威**（`market_alert_banner`「建議持股降至 10%／20%」＋「請以警語為準」）；(3) 🟠 第二套市場判讀（cron 無 `macro_state.json`；週報自建年線定調）；(4) 🟠 LINE 看不到 Risk Cap；(5) 🟠 LINE AI 非 Digest 輸入、無 grounding；(6) 與 System Action State／Decision Digest 目前**完全無關**。處置登記見 Architecture Gate §10.3。

## §9 UI2 需要、repo 目前沒有的 view-model 能力（摘要；完整允許／禁止判定見 Architecture Gate §4.3／§4.4）

| # | 能力 | 屬性 |
|---|---|---|
| N1 | 四態語意層＋十態→四態 map | ✅ presentation contract |
| N2 | Semantic chip tone＋`unavailable`→`unwired` | ✅（只加不改） |
| N3 | Field-level freshness 物件 | ✅；補 as_of 進 canonical 契約＝Stage F |
| N4 | 中立 VM 卡片型別 | ✅ |
| N5 | 「今日無需調整 vs 判不出」組合層 | ✅（PORT 既有規則進**System Action Aggregator（~~系統動作彙整層~~）**〔Architecture Gate ~~§4.5，G3′~~ §4.6，客戶 Q2；implementation Gate 後實作〕，⛔ 新門檻；VM ⛔ 自算） |
| N6 | 加／留／換／減呈現分組 | ✅ presentation-only；~~分組外觀屬線框待客戶核准~~ 分組與計入範圍客戶已核准（Q3 W-5=A），計數由 System Action Aggregator 產出 |
| N7 | System Action State 聚合層 | ✅ 允許作 **L3 deterministic 組裝**：~~最小彙整切片可依 **G3′=A′** 提前（Architecture Gate §4.5）~~ 最小彙整切片＝System Action Aggregator（客戶 Q2：新 runtime，契約凍結於 Architecture Gate §4.6，implementation Gate 後實作），完整版屬 Stage F；**不是** UI2 presentation 工作 |
| N8 | Risk Cap 閘門數值判定 | ❌ `FUI-RC-NUMERIC-GATE` |
| N9 | Rule Registry 讀取模型 | ✅ 讀既有 6 id；❌ 新造 rule id（`FUI-RULE-ID-SPEC`） |
| N10 | Decision Digest Viewer 模型 | ✅；真資料依賴 Stage F |
| N11 | Canonical Snapshot（session-free 狀態容器） | ✅ Stage F additive adapter；⚠️ 若需改既有 services 簽名＝觸碰「禁止重寫既有 services」→ 需客戶確認範圍 |
| N12 | Presentation Slice Independence 測試框架 | ✅ 測試基礎建設 |
| N13 | 市場頁第一屏 VM | ✅ 版面；「是否需要行動」只讀 N7，⛔ 由 regime 推導 |
| N14 | 單檔估值 VM | ✅ Current＋Historical（PORT）；❌ Forward／Scenario |
| N15 | LINE ← Digest consumer interface | ✅ 只定 interface／ownership；❌ 收編 10%／20% 警語 |
| N16 | OneBrain summary container | ✅ 容器；❌ 值域詞彙 |
| — | `recession_probability`、比例 Action、大盤 EPS×PE、個股買賣語意（T21） | ❌ 全部需 Decision Gate |

## §10 統計（矩陣列數；群組列 1 列計 1；混合列只計主類）

| 類 | 列數 | 列 ID |
|---|---|---|
| KEEP AS-IS | 26 | L0-1～5、L0-7、L0-9、L1-1～3、L1-5、L1-6、L1-11、L2-1、L2-7、S1、S2、S6、S7、S14、S15、S16、S22、S25、S28、S33 |
| WRAP | 21 | L1-4、L1-8、L2-3、S3、S4、S5、S8、S9、S10、S11、S12、S13、S17、S18、S19、S20、S21、S24、S32、U3、OLD-11 |
| PORT | 24 | L1-9、L1-10、L2-5、S23、V1、V2、V4、V5、V6、V7、V8、V9、V10、U1、U2、OLD-1～OLD-9（V1／V2／V4～V6／V9 另含 REIMPLEMENT 半；V7／V8 PORT 後 RETIRE） |
| REIMPLEMENT | 2 | V3、V11（＋UI2 全新 shell／nav／card／layout／chart container／狀態呈現，非既有列） |
| RETIRE LATER | 5 | L0-6、S27、S31、V12、U4 |
| DO NOT TOUCH | 10 | L0-8、L0-10、L1-7、L2-2、L2-4、L2-6、S26、S29、S30、Old UI 其餘（§6 末段） |
| **合計** | **88** | L0 10＋L1 11＋L2 7＋L3 33＋views 12＋ui_v2 4＋Old 11 |

- ⚠️ 列數是本矩陣粒度計數，**不是檔案數**。檔案級規模（FACT）：L3 58 檔中寫 session 者 9 檔；Legacy New UI views 15 檔逐函式（fnscan）：不直接引用 st 471、引用 st（非 session）82、引用 st.session_state 37。
- ⚠️ **計數口徑揭露**（撰寫組正式化時核對 invC §10）：分類小計 26＋21＋24＋2＋5＋10＝88；分區列數 10＋11＋7＋33＋12＋4＋11＝88。兩個 88 之間有一組**互相抵銷的口徑差**：(a) **OLD-10** 是指回 L1-8／L1-9／L2-3 的**群組指標列**，在分區列數中計 1、但**不入任何類小計**（其實際分類即 L1-8／L1-9／L2-3 各列）；(b) DO NOT TOUCH 的「**Old UI 其餘**」在類小計中計 1、但**不是**分區編號列。沿用 invC 原口徑，未改任何分類判定。

## §11 Top 10 風險（FACT＋INFERENCE）

1. **Legacy New UI 依賴 Old UI（跨代耦合）**：`tab_today.Card`／`tab_macro_v2.overall_verdict`／`station_cards.cruise_or_gap`／`tab_stock_picker.summarize_factor_hits`／`macro_v2_cards` 被 New UI import。Old UI「禁止修改」又要「之後退場」⇒ 必須先 PORT 成中立位置，否則 UI2 沿用 New UI builder 就把 Old UI 鎖死成永久依賴。layering guard **不擋 L5→L5**（→ G4）。
2. **session_state 是事實上的 canonical 狀態匯流排**：9 支 L3 寫 session；Digest market 段依賴 session warroom；無 Canonical Snapshot。UI2 若再加自己的 session key／快取＝第三套狀態。Headless Digest（Stage F）是「Decision Context 不因 UI 減少」的真正前提。
3. **conflict 揭露文字受 Old UI render 影響**（2026-11-02 稽核 F4 更正、降級）：`section_mid` render 時登記 caps／conflicts；但 `get_allocation` 以 `_derive_intrinsic_caps()` 重算並剔除同名登記 ⇒ **建議持股數字不受影響**，只有 `register_conflict` 的揭露文字會因「有沒有開過舊頁」而不同。輕度違 Freeze §14.2。
4. **LINE 第二套動作權威**：「建議持股降至 10%／20%」＋「請以警語為準」，不經 Risk Cap／System Action／Rule allowlist。收編或退場都需客戶 Gate。
5. **LINE 與 UI 市場狀態／Risk Cap 不一致**：cron 無 `macro_state.json`；週報自建定調；LINE 0 處讀 Risk Cap；選股 regime 濾網只在畫面路徑。
6. **風控／語意閘門住在顯示層**：`risk_cap_gate.has_system_risk_cap`（L5）、`cruise_or_gap`（L4）。UI2 重寫顯示層時最容易漏帶，造成「判不出被畫成今日無需調整」或缺上限仍給持股區間（Q1-4／Q2-4 直接違反）。
7. **Layering guard 盲點**：UI2 目錄未登記即五規則靜默失效；guard 只看 import，抓不到 L2 `st.caption`、L3 session 寫入、UI2→`src.ui.*` 的 L5→L5 依賴。
8. **Digest／System Action 不存在 → UI2 容器空轉誘發 UI 自造聚合**：UI2 在 Stage F 前若為了「有東西可顯示」在 VM 裡自己聚合動作，即違 invariant「System Action State 是唯一正式動作權威」。
9. **測試退場吞掉語意守衛**：≈130 支 New-UI-bound 測試含 silent-fail、missing≠hold、FX 不加總、as-of、secret scrub 等客戶裁示守衛；若隨版面一起退場而沒先改寫，cutover 後回歸無人看守。
10. **現成 New UI builder 夾帶已知違約／非 Digest AI**：`guard_chip` 誤用、`page_hold` ⑦ `gemini_call`、`page_why` `ai_qa_service.run_agent`、「訊號可信度」標籤；`compact` 傳遞依賴五頁版面契約。PORT 時「整包搬」會把違約帶進 UI2；必須逐函式挑選。

（附帶 INFERENCE：Old-UI-only 能力〔L1-8／L2-3／OLD-6 T16〕沒有 L3 ⇒ 能力守恆的實作成本集中在 PORT 前置，不在 UI2 版面本身。）

## §12 未驗與限制

- 全部為**單組**讀碼；未跑任何測試、未實機（`CLAUDE.md` §-2 規則 6：本檔全稱句皆為待驗；BACKLOG `NUI2-ARCH-SECOND-AUDIT`）。
- importer 集合經 barrel／`__getattr__` 轉發者歸到套件層 ⇒「只被 Old UI 用」「0 consumer」非窮舉。
- tests 分類為 regex 啟發式，數字是量級（±，未逐檔核對）。
- 「services 內 0 個 `st.*` UI 呼叫」只掃了列舉的 API 名。
- §8 第 3 點（cron 中 regime＝unknown）未實跑 cron 驗證。
- 本檔把 invC 正式化時**只改排版與欄位**（拆出「證據」欄、補 §0「UI2 可否 import」欄），未改任何分類判定；§10 計數口徑揭露見該節。
