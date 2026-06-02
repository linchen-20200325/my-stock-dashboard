# STATE.md — 台股 AI 戰情室 (Stock Dashboard)

> 極簡狀態檔。歷史 PR 紀錄見 git log；技術細節見 `ARCHITECTURE.md` / `DATASTATION.md` / `STRATEGY_MANUAL.md`。

## 專案定位
- **產品**：台股 / ETF 多 Tab 投資儀表板（市場 / 個股 / 組合 / 總經 / ETF）
- **技術棧**：Streamlit + pandas + Plotly + altair（<5）+ FinMind + yfinance + Gemini AI
- **基建**：NAS Squid Proxy + FastAPI 中繼站（個股新聞）
- **目前版本**：紅綠燈門檻校準走 Walk-Forward + 季度排程（反過擬合）
  - **calc_traffic_light**：加 `health_defense_threshold` / `bull_min_score` optional kwargs（不影響 production，純供校準注入）
  - **macro_helpers.py**：module load 時優先讀 `macro_thresholds.json`，缺檔/越界 silently fall back module 常數；越界守門 H∈[20,60]、S∈[1,6]
  - **calibrate_macro_traffic.py**：新增 `walk_forward_validate(df, n_folds=4)`——滾動切折、每折 train 找最佳門檻 grid (H∈[25,45] step 2 × S∈[2,5])、test 報告 OOS、目標函數含「偏離現行常數」正則項；新增 `evaluate_thresholds` / `grid_search_thresholds` / `emit_thresholds_json` / `build_proposal_report`；CLI 加 `--optimize --emit-json --emit-proposal --n-folds`
  - **過擬合三重保護**：(a) walk-forward 永不在 train 評分 (b) 票選 + drift>30% 過半即回退預設 (c) 季度排程開 PR 給人類審閱、不自動 merge
  - **`.github/workflows/recalibrate_macro.yml`**：季度排程（1/4/7/10 月 1 號）+ workflow_dispatch（input range/n_folds），需 Secrets `PROXY_URL` + `FINMIND_TOKEN`，跑完開 PR with proposal as body
  - **calibration_ui.py**：UI 加 `_show_threshold_status()` 顯示現行門檻 + 最後校準時間戳 + 方法
  - **tests/test_calibrate_walkforward.py**：8 個 smoke（合成資料 walk-forward 不 raise、過擬合保護回退、threshold 覆寫單調性、JSON 讀寫一致、正則項懲罰偏離）全綠
- **前一版**：資料異常清單 2 筆續修——PMI / 出口 YoY 新源（CIER 英文月度頁 + stat.gov.tw），全走 NAS 中繼站
  - **PMI**：新增 `_pmi_src_cier_en_monthly`（macro_core.py）為最高優先源，直接打 CIER 英文月度 slug `/en/eco/taiwan-manufacturing-pmi-{月}-{年}/`，每次嘗試 current/-1/-2 月共 3 個 slug；CIER 是官方發布單位、slug 結構自 2024 起穩定、HTML 乾淨命中率 >95%。9 源 → 10 源並行，全走 `fetch_url`（NAS Squid → 直連 → NAS 中繼站 fallback）
  - **出口 YoY**：在 `tab_macro.py:_fetch_export()` 最前面插方案 0 stat.gov.tw（DGBAS 出口年增率頁 `Point.aspx?sid=t.8&n=3587&sms=11480`），HTML 抓「YYYY年M月 出口年增率 XX.X%」格式；與 #141 的 FRED series 校正 + data.gov.tw 6053 互補形成 6 源備援鏈
  - 根因：海外 IP 雖透過 `fetch_url` 三層 fallback 過 NAS，但**舊源 URL 結構失效**（CIER `/news/list?cid=21` 列表改、MOF 月度 CSV 路徑變動）→ 全鏈路滑落到靜態備援（出口 92 天前）或全失敗（PMI 未取得）
- **前一版**：v18.142 資料抓取器 series id / endpoint 校正（#141）
  - **美國核心 CPI**：誤用 `CPIAUCSL`（總體）→ 改 `CPILFESL`（核心）；新增方案 0 `fredgraph.csv` 無需 API key；BLS fallback 改 `CUSR0000SA0L1E`
  - **台灣出口 YoY**：FRED `VALEXPTWM052N`（IFS 延遲 13 月）→ 改 `XTEXVA01TWM664S`（OECD MEI 延遲 2-3 月）；新增 data.gov.tw dataset 6053 海關進出口貿易統計方案（走 NAS proxy）
  - tab_edu.py + data_registry.py 同步 identifier；新增 10 個 source-level regression tests；tests/ 850 passed
- **前二版**：紅綠燈校準誠實化 + 門檻收斂（#137-#140）
  - **#140**：校準報告加 TWII-only 警語 banner、建議讀現行常數（`HEALTH_DEFENSE_THRESHOLD=35` / `BULL_MIN_SCORE=4`）
  - **#139**：5Y TWII 校準顯示防禦 precision 14.8%、多頭 30.7% → `calc_traffic_light` 防禦 `_health < 40` 改 `<35`、bull 加 `_score >= 4` 條件
  - **#137-#138**：校準 Streamlit UI Tab + 比較×排行卡片載入修
- **前三版**：ETF 經理人換手偵測持久化（#131-#132）
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
