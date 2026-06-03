# STATE.md — 台股 AI 戰情室 (Stock Dashboard)

## 專案定位
- **產品**：台股 / ETF 多 Tab 投資儀表板（市場 / 個股 / 組合 / 總經 / ETF）
- **技術棧**：Streamlit + pandas + Plotly + FinMind + yfinance + Gemini AI
- **基建**：NAS Squid Proxy（解海外 IP 封鎖）+ FastAPI 中繼站（個股新聞）
- **部署**：GitHub + Streamlit Cloud

## 模組分層
```
UI 層         app.py · tab_macro / tab_stock / tab_stock_grp / tab_edu · ui_widgets
共用層        tab_helpers · macro_helpers · etf_helpers · tech_indicators
資料抓取      data_loader · macro_core · tw_macro · daily_checklist · update_macro_history
ETF 三層      etf_fetch（I/O）· etf_calc（計算）· etf_render（UI）+ etf_tab_*
引擎          scoring_engine · financial_health_engine · market_strategy · risk_control
              backtest_engine · unified_decision · v4_strategy_engine · v5_modules
              yield_screener · flow_engine · exit_signals
AI / 警示     ai_engine · macro_alert · macro_state_locker · persona
雲端 / 基建   gsheet_portfolio · oauth_state · infra/oauth · proxy_helper · nas_server
熱錢監測      hot_money.py（外資 × 匯率 × 背離 三角交叉）
校準系統      calibrate_macro_traffic + calibration_ui + macro_thresholds.json
```

## 資料快取
- `data_cache/`：Parquet 表 git 追蹤
  - `twii_ohlcv.parquet` · `finmind_inst.parquet` · `finmind_margin.parquet` · `finmind_m1m2.parquet`
  - `metadata.json`（last_updated / row_count / last_error per dataset）
- 每日 UTC 09:00 自動增量（Actions `update_macro_history.yml`）

## 自動化
- `.github/workflows/update_macro_history.yml` — 每日總經資料增量
- `.github/workflows/update_etf_managers.yml` — 每週 ETF 經理人爬蟲
- `.github/workflows/recalibrate_macro.yml` — 季度紅綠燈門檻 walk-forward 校準

## Secrets（GitHub Actions + Streamlit Cloud 各自設）
`FINMIND_TOKEN` · `GEMINI_API_KEY[_2..6]` · `PROXY_URL` · `FRED_API_KEY` ·（選配 `NAS_BASE_URL` / `NAS_API_KEY`）

## 測試
- `pytest tests/` + `pytest test_*.py`
- 核心 smoke：`tests/test_hot_money.py` · `test_app_step4.py` · `test_market_strategy.py`

## 配置
- `requirements.txt` — runtime；`.streamlit/config.toml` — UI 設定
- 主幹 `main`；開發走 `claude/<task>-<slug>` feature branch + PR
