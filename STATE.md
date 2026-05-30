# STATE.md — 台股 AI 戰情室 (Stock Dashboard)

> 極簡狀態檔。歷史 PR 紀錄見 git log；技術細節見 `ARCHITECTURE.md` / `DATASTATION.md` / `STRATEGY_MANUAL.md`。

## 專案定位
- **產品**：台股 / ETF 多 Tab 投資儀表板（市場 / 個股 / 組合 / 總經 / ETF）
- **技術棧**：Streamlit + pandas + Plotly + altair（<5）+ FinMind + yfinance + Gemini AI
- **基建**：NAS Squid Proxy + FastAPI 中繼站（個股新聞）
- **目前版本**：PR #124（統一 ETF metadata 改走 MoneyDJ Basic0004 + NAS 中繼站）｜**代碼淨化與收尾完成** ✅
  - 沿革：#117 fetch_etf_underlying_index + liquidity_score → #119 PMI/NAV/費用率 6 處改走 fetch_url（NAS 中繼自動接管）→ #122 主動式 ETF 中文名 + SITCA 'A' 剝除 + MoneyDJ NAV 段改 Basic0003 → #124 新增 fetch_etf_meta_moneydj（Basic0004 一次取 zh_name + AUM + 經理費+保管費 + 追蹤指數），fetch_etf_info 在 yfinance.info 缺欄時自動 merge，get_etf_expense_ratio_safe 把 MoneyDJ 升為 primary — 繞 yfinance.info 海外 IP 封鎖 → 收尾淨化：data_loader.py / daily_checklist.py 移除 7 處 unused imports（ruff F401 全綠）
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
