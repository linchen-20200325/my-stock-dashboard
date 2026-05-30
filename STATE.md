# STATE.md — 台股 AI 戰情室 (Stock Dashboard)

> 極簡狀態檔。歷史 PR 紀錄見 git log；技術細節見 `ARCHITECTURE.md` / `DATASTATION.md` / `STRATEGY_MANUAL.md`。

## 專案定位
- **產品**：台股 / ETF 多 Tab 投資儀表板（市場 / 個股 / 組合 / 總經 / ETF）
- **技術棧**：Streamlit + pandas + Plotly + altair（<5）+ FinMind + yfinance + Gemini AI
- **基建**：NAS Squid Proxy + FastAPI 中繼站（個股新聞）
- **目前版本**：ETF 經理人換手偵測持久化（GitHub Actions 爬蟲 → commit JSON → app 讀檔）
  - 新增：`update_etf_managers.py`（獨立爬蟲,無 streamlit/pandas 相依,走 proxy_helper 讀 env PROXY_URL）+ `.github/workflows/update_etf_managers.yml`（週一排程 + 手動,需 repo Secrets 設 `PROXY_URL`）+ `etf_manager_watchlist.json`（追蹤清單）+ `etf_managers.json`（持久經理人/換手歷史,Actions 維護勿手改）。`track_etf_manager_change` 改以 repo 持久檔為換手基準/歷史主來源（近 180 天換手亮紅框,跨容器重啟存活）,`/tmp` 降次要。解決舊機制只存 `/tmp`、雲端重啟即清空→紅框幾乎不跳的問題
- **前一版**：ETF 折溢價假日/週末對齊最後交易日（#129）
  - 沿革：#119 PMI/NAV/費用率改走 fetch_url → #122 主動式 ETF 中文名 + SITCA 'A' 剝除 + NAV 改 Basic0003 → #124 fetch_etf_meta_moneydj（Basic0004 一次取 zh_name + AUM + 費用率 + 追蹤指數）→ #126 經理人顯示 + 異動偵測 + `_html_kv_pairs`（MoneyDJ 儲存格配對，新聞 etf_profile_fetcher 同法）→ #127 折溢價改 MoneyDJ Basic0001 直讀 + 內扣費用率改 KV 破「經理費(%)」陷阱（00982A→1.20%）+ 經理人不早退 + 未設 PROXY_URL 顯誠實橫幅 → **#129**：折溢價假日 bug——即時來源（goodinfo/TWSE/MoneyDJ/yfinance）原硬戳 `date.today()`，週末/假日與 yfinance 收盤日（上一交易日）同日 inner-join 落空→N/A。修：`fetch_etf_nav_history` 新增 `_last_business_day()`（淨值列改戳最近交易日）；`calc_premium_discount` 路徑B 同日 join 落空時假日兜底（最新淨值 vs 最新收盤，日期 ≤4 天才配，涵蓋連假）
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
