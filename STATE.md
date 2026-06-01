# STATE.md — 台股 AI 戰情室 (Stock Dashboard)

> 極簡狀態檔。歷史 PR 紀錄見 git log；技術細節見 `ARCHITECTURE.md` / `DATASTATION.md` / `STRATEGY_MANUAL.md`。

## 專案定位
- **產品**：台股 / ETF 多 Tab 投資儀表板（市場 / 個股 / 組合 / 總經 / ETF）
- **技術棧**：Streamlit + pandas + Plotly + altair（<5）+ FinMind + yfinance + Gemini AI
- **基建**：NAS Squid Proxy + FastAPI 中繼站（個股新聞）
- **目前版本**：總經資料異常修復——PMI / 出口 YoY 新源（CIER 英文月度頁 + stat.gov.tw），全走 NAS 中繼站
  - **PMI**：新增 `_pmi_src_cier_en_monthly`（macro_core.py）為最高優先源，直接打 CIER 英文月度 slug `/en/eco/taiwan-manufacturing-pmi-{月}-{年}/`，每次嘗試 current/-1/-2 月共 3 個 slug；CIER 是官方發布單位、slug 結構自 2024 起穩定、HTML 乾淨命中率 >95%。9 源 → 10 源並行，全走 `fetch_url`（NAS Squid → 直連 → NAS 中繼站 fallback）
  - **出口 YoY**：在 `tab_macro.py:_fetch_export()` 最前面插方案 0 stat.gov.tw（DGBAS 出口年增率頁 `Point.aspx?sid=t.8&n=3587&sms=11480`），HTML 抓「YYYY年M月 出口年增率 XX.X%」格式；3 源 → 6 源備援，舊 FinMind/MOF/FRED/data.gov.tw/靜態 保留為 fallback
  - 根因：原方案在海外 IP（Streamlit Cloud）會被多數 TW 政府/CIER 站 403；雖已透過 `fetch_url` 三層 fallback 過 NAS，但**舊源 URL 結構失效**（CIER `/news/list?cid=21` 列表改、FRED 出口 series 2-3 月延遲、MOF 月度 CSV 路徑變動）→ 全鏈路滑落到靜態備援（出口 92 天前）或全失敗（PMI 未取得）
- **前一版**：ETF 經理人換手偵測持久化（GitHub Actions 爬蟲 → commit JSON → app 讀檔）｜代碼淨化與收尾完成 ✅
  - 新增 `update_etf_managers.py`（獨立爬蟲走 proxy_helper）+ workflow + watchlist/managers JSON；`track_etf_manager_change` 改以 repo 持久檔為主、`/tmp` 降次要，解決雲端重啟即清空→紅框不跳的問題
  - 沿革：#119 PMI/NAV/費用率改走 fetch_url → #122 主動式 ETF 中文名 + SITCA 'A' 剝除 + NAV 改 Basic0003 → #124 fetch_etf_meta_moneydj（Basic0004 一次取 zh_name + AUM + 費用率 + 追蹤指數）→ #126 經理人顯示 + 異動偵測 + `_html_kv_pairs`（MoneyDJ 儲存格配對） → #127 折溢價改 MoneyDJ Basic0001 直讀 + 內扣費用率改 KV 破「經理費(%)」陷阱 → #129 折溢價假日對齊最後交易日 → **#131** 經理人換手持久化（GitHub Actions 爬蟲 + repo JSON）→ **#132** ETF watchlist 擴充至 28 檔
  - ⚠️ **前提**：MoneyDJ 擋海外 IP，Streamlit App secrets 須設 `PROXY_URL`（家用 NAS 台灣 IP）這些 ETF 欄位才有值，否則 N/A（已設好；部署重建會自動清 `@st.cache_data` 快取）
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
