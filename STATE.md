# STATE.md — 台股 AI 戰情室 (Stock Dashboard)

> 極簡狀態檔。歷史 PR 紀錄見 git log；技術細節見 `ARCHITECTURE.md` / `DATASTATION.md` / `STRATEGY_MANUAL.md`。

## 專案定位
- **產品**：台股 / ETF 多 Tab 投資儀表板（市場 / 個股 / 組合 / 總經 / ETF）
- **技術棧**：Streamlit + pandas + Plotly + altair（<5）+ FinMind + yfinance + Gemini AI
- **基建**：NAS Squid Proxy + FastAPI 中繼站（個股新聞）
- **目前版本**：v18.153_NdcOpenApiDiag（NDC URL 多 candidate 全 JSON 失敗 — 加強診斷 log 找根因）
  - **背景**：v18.152 bootstrap 10 個 NDC OpenAPI candidate URL 全回「JSON 解析失敗 line 1 column 1 (char 0)」— proxy 報「成功抓取」表示 HTTP 200 + body 有內容（非空），但首字元非 JSON。推測：NDC SPA 對所有 `/app/data/indicator/*` 路徑回 HTML 首頁（client-side routing fallback）
  - **update_macro_history.py**：`_fetch_ndc_indicator_full` JSON 解析失敗分支新增 `Content-Type` header 與 `body[:300]` dump（從原本只印 exception type → 補出 HTML/JSONP/空 body 的關鍵診斷）
  - **回歸**：tests/ 907 passed 零回歸（log 字串變動，不影響邏輯路徑測試）
  - **下一步**：merge 後 bootstrap 一次 → log 會印出 NDC 實際回什麼 → 我下一輪 PR 依結果選正確路徑（HTML 抓 → 改 data.gov.tw search；JSONP → 加 unwrap；空 → 改 query string 帶參數）
- **前一版**：v18.152_NdcOpenApiMigration（脫離 FinMind 付費牆 → 國發會 NDC OpenAPI 免費直連 + multi-URL probe）
  - **背景**：v18.151 把 dataset 改 `TaiwanBusinessIndicator` 後，bootstrap 撞 HTTP 400 `"Your level is register"` — FinMind 已把 NDC 信號/領先指標歸到 Sponsor 付費 tier（NT$500+/月）。Streamlit live tab `tw_macro.py` 用同 dataset 也壞掉（user 未察覺因為 tab 有 graceful 包覆）
  - **解法**：脫離 FinMind 改打**國發會 NDC OpenAPI**（`https://index.ndc.gov.tw/app/data/indicator/{slug}`）— PMI 已驗證有效（`macro_core._pmi_src_ndc`）+ proxy 白名單已涵蓋（`nas_server.py`），免 token、免錢
  - **update_macro_history.py**：
    - 移除 dead code `_finmind_macro_table` / `_pick_macro_column` / `_MACRO_FULL_TABLE_CACHE`（FinMind 路完全切斷，wide-format helper 不再需要）
    - 新增 `_NDC_SIGNAL_URL_CANDIDATES`（5 個 slug：monitoring / composite / signal / cyclical / SignalScore）+ `_NDC_LEADING_URL_CANDIDATES`（5 個：leading / Leading / lead / LeadingIndex / leadingComposite）+ `_NDC_VALUE_KEYS`（8 個 fallback）+ `_NDC_DATE_KEYS`（7 個）
    - 新增 `_fetch_ndc_indicator_full(candidates, label)` — 逐一 try URL via `proxy_helper.fetch_url`，多 JSON shape parser（list / {data:[]} / {items:[]} / {result.records:[]}）+ verbose log（HTTP code + body 前 200 char）供下一輪鎖死
    - `fetch_ndc_signal(start, end)` + `fetch_ndc_leading_index(start, end)` 取代舊 `fetch_finmind_*`（簽名拿掉 `token` 參數）
    - FETCHERS dict 把兩 dataset 的 `needs_token` 從 True 改 False（v18.152 起 NDC 表完全免 token）
    - Parquet 檔名保留 `finmind_ndc_signal.parquet` / `finmind_leading_index.parquet`（向後相容 macro_validation_tw.py + Section 十一 UI）
  - **tests/test_update_macro_history.py**：替換 11 個 FinMind 測試 → 11 個 NDC 測試（含 _FakeResp helper）：candidate URL constants 完整性 / 第一 URL 成功不打第二 / 第一 fail fallback 第二 / 全 URL fail 回空 / JSON shape={'data':[]} unwrap / yearMonth date key / round + Int64 cast / 範圍 filter / 全 fail graceful
  - **tw_macro.py 暫不動**：本 PR 純 bootstrap fetcher 修復；Streamlit live tab 同樣是 FinMind 來源，留下次 PR 一起遷移到 NDC OpenAPI（避免 hotfix scope 爆量）
  - **回歸**：tests/ **907 passed** 零回歸
  - **下一步**：merge 後請手動觸發 `update_macro_history.yml` workflow_dispatch + bootstrap=true / years=25 → bootstrap log 會印每個 candidate URL 的 HTTP 狀態 → 第一個 work 的 URL 自動寫進 Parquet；若全失敗，貼 log 給我 → 下一輪 PR 加新 candidate / 改用 data.gov.tw dataset ID fallback
- **前一版**：v18.151_FinMindBusinessIndicatorFix（FinMind v4 dataset 改名 hotfix — bootstrap 失敗復原）
  - **背景**：v18.149 用 dataset `TaiwanMacroEconomics` 抓 NDC + 領先指標，bootstrap 時 FinMind 回 HTTP 422 enum invalid（dataset 已被廢除/改名）→ NDC/領先 Parquet 0 rows → Section 十一驗證無資料可看
  - **根因**：FinMind v4 把 NDC monitoring + 領先 leading 合併打包成 wide-format dataset `TaiwanBusinessIndicator`（欄位：date / leading / leading_notrend / coincident / coincident_notrend / lagging / lagging_notrend / monitoring）
  - **update_macro_history.py**：dataset 改 `TaiwanBusinessIndicator`；移除 dead code `_filter_macro_indicator` + `NDC_SIGNAL_KEYS` + `LEADING_INDEX_KEYS`（wide-format 不需 long-format indicator filter）；新增 `_pick_macro_column(df, col)` wide-format 抽欄輔助；`fetch_finmind_ndc_signal` 改抓 `monitoring`、`fetch_finmind_leading_index` 改抓 `leading`；`_finmind_macro_table` cache 機制不變（NDC + leading 仍共用一次 API call）
  - **tests/test_update_macro_history.py**：移除 5 個 `_filter_macro_indicator` 測試 + 改寫 4 個 fetcher / cache 測試以 wide-format 為 fixture；新增 3 個 `_pick_macro_column` 測試（基本抽欄 + NaN drop / 缺欄 graceful / 空輸入）+ 1 個 dataset 名稱驗證測試（防 FinMind 再次改名時無感）
  - **回歸**：tests/ **907 passed**（v18.150 909 - 5 obsolete + 3 new = 907）零功能回歸
  - **下一步**：請手動觸發 `update_macro_history.yml` workflow_dispatch + bootstrap=true / years=25 → 應抓到 ~300 月 NDC + 領先資料（1984 起算）→ Section 十一可看 7 場 crisis 命中表 → 接 Phase E 跨來源比對
- **前二版**：v18.150_MacroBacktestUI（macro tab section 十一 — 歷史驗證 UI，鏡像 fund Phase 6a）
  - **User 需求**：「兩邊都可以做回測來驗證台股的總經 tab 與基金（全球的）總經 tab」。Sister repo my-Fund-dashboard 已於 v18.276 Phase B.2 把 Parquet 接到 Phase 6a 驗證 UI；本 PR 為台股對等版本，讀 PR #149 v18.149 鋪好的 NDC + 領先指標 Parquet + 既有 twii_ohlcv → 雙指標 × TWII crisis 命中表
  - **macro_validation_tw.py**（~270 行 pure data）：3 個 Parquet loader（NDC / 領先 / TWII close）+ `detect_twii_crisis_events`（high-water-mark walk-forward，與 fund crisis_backtest 同範式，預設 20% 回撤）+ `verify_ndc_signal_vs_crises`（峰前 N 月 → 峰時 NDC 下降 ≥ drop_pts 分；預設 4 分 ≈ 1 燈號跨度）+ `verify_leading_index_vs_crises`（peak 月 6M smoothed change < 0 即命中）+ `compute_smoothed_change_pct`（與 tw_macro.fetch_ndc_leading_index 一致 rolling 6 月 MA → pct_change × 100）+ `compute_hit_rate` 統計卡 helper
  - **tab_macro_validation.py**（~240 行 Streamlit UI）：`render_history_validation_section(cache_dir)` — Section 十一 渲染；缺檔友善 banner 引導 user 等 cron；3 sliders（TWII 回撤門檻 10-40% / lead_months 3-12 / NDC drop_pts 2-10）+ 跑按鈕 + 2 張命中率卡 + plotly 雙軸圖（TWII 主軸 + NDC 副軸 + crisis 紅區）+ NDC/領先指標雙命中表 + 2 個 CSV 下載按鈕（utf-8-sig BOM 解 Excel）
  - **tab_macro.py**：插 11 行（section 十之後，結尾 `<hr>` 之前）— `from tab_macro_validation import render_history_validation_section` + 呼叫，try/except 包覆避免 Parquet 缺檔影響整 tab 渲染
  - **tests/test_macro_validation_tw.py**（29 case 全綠）：Parquet 讀取（缺檔 / 正常解析 / 壞檔 graceful）/ detect_twii_crisis_events（v 型 / 門檻下無事件 / 空 / 過短 / open-ended 無 recovery / 多事件）/ verify_ndc（命中 exact 4 pts / 明確 8 pts / 無事件 / 空 series）/ compute_smoothed_change（常數 → 0% / 線性升全正 / 空 input）/ verify_li（peak 時 smooth<0 命中 / 單調升不命中 / 空 input）/ compute_hit_rate（mixed / empty / all None drop_pts）/ UI source-level（tab_macro.py import 與呼叫 + 模組 export render fn + section 順序在 10 之後）
  - **回歸**：tests/ **909 passed** 零回歸（880 + 29 新）
  - Roadmap：Phase D（PMI 補抓進 Parquet）→ Phase E（fund + stock 同框跨來源比對工具）
- **前三版**：v18.149_NdcLeadingHistoryFetchers（macro_history 擴 2 新表：景氣對策信號 + 領先指標）
  - **User 需求**：「兩邊都可以做回測來驗證台股的總經 tab 與基金（全球的）總經 tab」+ 「直接抓取資料放在資料庫，之後每周定期更新」→ 沿用 PR #144 已建的 Parquet 快取模式（非 SQLite），補上**驗證總經 Tab 的關鍵 2 指標**：NDC 景氣對策信號（拐點偵測 9-45 分）+ 領先指標綜合指數（6M smoothed change 領先期）
  - **update_macro_history.py**：新增 `fetch_finmind_ndc_signal` + `fetch_finmind_leading_index`（都打 FinMind TaiwanMacroEconomics dataset，模組級 `_MACRO_FULL_TABLE_CACHE` 字典快取讓兩 fetcher 共用一次 API call）；新增 `_finmind_macro_table()` 全表抓取（含 cache）+ `_filter_macro_indicator()` 指標篩選工具（支援 indicator/name/metric × value/data 欄位變體 + exact→contains 兩層 fallback）；DATASETS 從 4 表擴 6 表，FETCHERS dict 同步註冊（皆需 FINMIND_TOKEN）
  - **新增 Parquet**：`data_cache/finmind_ndc_signal.parquet`（columns: date, ndc_signal Int64）+ `data_cache/finmind_leading_index.parquet`（columns: date, leading_index float）；領先指標**只存原始值**，6M smoothed change 由分析端 on-the-fly 算（rolling 6 月需 lookback context，fetcher 增量時無法正確算）
  - **tests/test_update_macro_history.py**（+12 case = 19 全綠）：DATASETS 註冊驗證 / `_filter_macro_indicator` exact match / contains fallback / no match / empty input / missing columns / 替代欄位名（metric+data）/ macro_table_cache 同 key 不重打 / fetch_ndc_signal shape（含 Int64 + round）/ fetch_leading_index shape / fetch 找不到時回空 / NDC + LI 共用同一次 API call cache
  - **回歸**：tests/ **880 passed** 零回歸
  - Roadmap：Phase 2（macro tab 加歷史驗證 UI 子區塊 — 讀 Parquet 算月度 score、對齊 TWII crisis hit/miss）→ Phase 3（fund-dashboard FRED 9 指標 Parquet cache）
- **前三版**：v18.148 代碼淨化收尾（#148 — v5_modules / v4_strategy_engine / nas_server unused vars/imports 移除，0 邏輯改動）
- **前四版**：v18.147 macro-history 守護鏈強化（#144-#147）
  - **#144**：總經歷史資料快取層 + 每日增量 Actions（解 TWII-only 結構性偏弱）。data_cache/ Parquet 表 git 追蹤——twii_ohlcv / finmind_inst / finmind_margin / finmind_m1m2 + metadata.json。`update_macro_history.py` 無 streamlit 相依爬蟲，增量 append+dedupe；workflow 每日 UTC 09:00 + bootstrap mode；`calibrate_macro_traffic.py` 加 load_from_cache + _enrich_with_finmind 注入 FinMind 欄位
  - **#145-#147**：production hardening——FinMind 改直連印 HTTP status、三大法人英文 name 篩 'Foreign'、CBC M1B/M2 三 URL 備援 + SDMX EF15M01 fallback
- **前四版**：紅綠燈門檻校準走 Walk-Forward + 季度排程（反過擬合）
  - **calc_traffic_light**：加 `health_defense_threshold` / `bull_min_score` optional kwargs（不影響 production，純供校準注入）
  - **macro_helpers.py**：module load 時優先讀 `macro_thresholds.json`，缺檔/越界 silently fall back module 常數；越界守門 H∈[20,60]、S∈[1,6]
  - **calibrate_macro_traffic.py**：新增 `walk_forward_validate(df, n_folds=4)`——滾動切折、每折 train 找最佳門檻 grid (H∈[25,45] step 2 × S∈[2,5])、test 報告 OOS、目標函數含「偏離現行常數」正則項；新增 `evaluate_thresholds` / `grid_search_thresholds` / `emit_thresholds_json` / `build_proposal_report`；CLI 加 `--optimize --emit-json --emit-proposal --n-folds`
  - **過擬合三重保護**：(a) walk-forward 永不在 train 評分 (b) 票選 + drift>30% 過半即回退預設 (c) 季度排程開 PR 給人類審閱、不自動 merge
  - **`.github/workflows/recalibrate_macro.yml`**：季度排程（1/4/7/10 月 1 號）+ workflow_dispatch（input range/n_folds），需 Secrets `PROXY_URL` + `FINMIND_TOKEN`，跑完開 PR with proposal as body
  - **calibration_ui.py**：UI 加 `_show_threshold_status()` 顯示現行門檻 + 最後校準時間戳 + 方法
  - **tests/test_calibrate_walkforward.py**：8 個 smoke（合成資料 walk-forward 不 raise、過擬合保護回退、threshold 覆寫單調性、JSON 讀寫一致、正則項懲罰偏離）全綠
- **前五版**：資料異常清單 2 筆續修——PMI / 出口 YoY 新源（CIER 英文月度頁 + stat.gov.tw），全走 NAS 中繼站
  - **PMI**：新增 `_pmi_src_cier_en_monthly`（macro_core.py）為最高優先源，直接打 CIER 英文月度 slug `/en/eco/taiwan-manufacturing-pmi-{月}-{年}/`，每次嘗試 current/-1/-2 月共 3 個 slug；CIER 是官方發布單位、slug 結構自 2024 起穩定、HTML 乾淨命中率 >95%。9 源 → 10 源並行，全走 `fetch_url`（NAS Squid → 直連 → NAS 中繼站 fallback）
  - **出口 YoY**：在 `tab_macro.py:_fetch_export()` 最前面插方案 0 stat.gov.tw（DGBAS 出口年增率頁 `Point.aspx?sid=t.8&n=3587&sms=11480`），HTML 抓「YYYY年M月 出口年增率 XX.X%」格式；與 #141 的 FRED series 校正 + data.gov.tw 6053 互補形成 6 源備援鏈
  - 根因：海外 IP 雖透過 `fetch_url` 三層 fallback 過 NAS，但**舊源 URL 結構失效**（CIER `/news/list?cid=21` 列表改、MOF 月度 CSV 路徑變動）→ 全鏈路滑落到靜態備援（出口 92 天前）或全失敗（PMI 未取得）
- **前六版**：v18.142 資料抓取器 series id / endpoint 校正（#141）
  - **美國核心 CPI**：誤用 `CPIAUCSL`（總體）→ 改 `CPILFESL`（核心）；新增方案 0 `fredgraph.csv` 無需 API key；BLS fallback 改 `CUSR0000SA0L1E`
  - **台灣出口 YoY**：FRED `VALEXPTWM052N`（IFS 延遲 13 月）→ 改 `XTEXVA01TWM664S`（OECD MEI 延遲 2-3 月）；新增 data.gov.tw dataset 6053 海關進出口貿易統計方案（走 NAS proxy）
  - tab_edu.py + data_registry.py 同步 identifier；新增 10 個 source-level regression tests；tests/ 850 passed
- **前七版**：紅綠燈校準誠實化 + 門檻收斂（#137-#140）
  - **#140**：校準報告加 TWII-only 警語 banner、建議讀現行常數（`HEALTH_DEFENSE_THRESHOLD=35` / `BULL_MIN_SCORE=4`）
  - **#139**：5Y TWII 校準顯示防禦 precision 14.8%、多頭 30.7% → `calc_traffic_light` 防禦 `_health < 40` 改 `<35`、bull 加 `_score >= 4` 條件
  - **#137-#138**：校準 Streamlit UI Tab + 比較×排行卡片載入修
- **前八版**：ETF 經理人換手偵測持久化（#131-#132）
  - `update_etf_managers.py`（獨立爬蟲走 proxy_helper）+ workflow + watchlist/managers JSON；`track_etf_manager_change` 改以 repo 持久檔為主、`/tmp` 降次要，解決雲端重啟即清空→紅框不跳
  - 沿革：#119 PMI/NAV/費用率改走 fetch_url → #122 主動式 ETF 中文名 + NAV 改 Basic0003 → #124 fetch_etf_meta_moneydj（Basic0004 一次取齊）→ #126 經理人異動偵測 → #127 折溢價直讀 MoneyDJ Basic0001 + 費用率破「經理費(%)」陷阱 → #129 折溢價假日對齊最後交易日 → **#131** 經理人換手持久化 → **#132** ETF watchlist 擴充至 28 檔
  - ⚠️ **前提**：MoneyDJ 擋海外 IP，Streamlit App secrets 須設 `PROXY_URL`（家用 NAS 台灣 IP）這些 ETF 欄位才有值，否則 N/A
- **Secrets**：`FINMIND_TOKEN` · `GEMINI_API_KEY[_2..6]` · `PROXY_URL` · `FRED_API_KEY` ·（選配 `NAS_BASE_URL` / `NAS_API_KEY`）

## 模組分層（PR #58–#73 大重構後）
```
UI 層         app.py（1378 行入口） · tab_macro / tab_stock / tab_stock_grp / tab_edu
             etf_dashboard（49 行 shim）→ etf_tab_single / _portfolio / _backtest / _ai
             ui_widgets.py（9 個純 HTML 函式）
共用層        tab_helpers.py · macro_helpers.py · etf_helpers.py · tech_indicators.py
資料抓取      data_loader · macro_core · tw_macro · daily_checklist · tw_stock_data_fetcher
ETF 三層      etf_fetch（I/O） · etf_calc（計算） · etf_render（UI）
引擎          scoring_engine / financial_health_engine / market_strategy / risk_control
             backtest_engine / unified_decision / v4_strategy_engine / v5_modules
             yield_screener / flow_engine / exit_signals
AI / 警示     ai_engine · macro_alert · macro_state_locker · persona
雲端 / 基建   gsheet_portfolio · oauth_state · infra/oauth · proxy_helper · nas_server
熱錢監測      hot_money.py（三角交叉：外資 × 匯率 × 背離）
```

## 測試
- `pytest tests/` + `pytest test_*.py`
- 核心 smoke：`tests/test_hot_money.py`、`test_app_step4.py`、`test_market_strategy.py`

## 配置
- `requirements.txt` — runtime；`.streamlit/config.toml` — UI 設定
- 分支：開發於 `claude/etf-portfolio-download-CKR5h`，主幹 `main`
