# 重構狀態看板(深層拔毒 v18.369+)

## 進行中 batch
✅ D-9 紅綠燈卡(認錯補做)— PR #396 已 merge into main

## 🏁 PR #396 v18.391(merged 2026-06-28)
**tab_macro.py 1076 → 1012 LOC(−64)** — 認錯補做紅綠燈卡。
- D-9 `c1e8483`:紅綠燈卡 66 LOC → section_traffic_light(回傳 placeholder/show_market_data/tl_eff_reg 3-tuple)
- INDEX sync `d3f9a04`

**承認先前 verdict 錯誤**:之前以「placeholder 反模式」擋,但 B-S2 已跨 def 傳 placeholder,argument 自我矛盾。
累計 tab_macro 5387 → 1012 LOC(-81%)。

---


## 🏁 PR #395 v18.390(merged 2026-06-28)
**tab_macro.py 1445 → 1076 LOC(−369,−26%)** — 5 commit dashboard 三件套 + Registry patch。
- D-5 `ac06da7`:五桶 bar 43 LOC → section_summary_bar
- D-6 `89ab752`:戰情概覽 35 LOC → section_overview
- D-7 `98e8005`:今日作戰室 154 LOC → section_warroom
- D-8 `cfd521f`:Registry patch 161 LOC → services/macro_registry_patch
- INDEX sync `e9f2e23`

承認前次 deep-dive verdict 過嚴(誤標 5 段「不可抽」), 本 PR 確實抽 4 段。
全工作累計:tab_macro 5387 → 1076 LOC(−4311,−80%)。
殘餘 1076 LOC 真不可抽:紅綠燈 placeholder lifecycle(streamlit 反模式)。

---


## 🏁 PR #394 v18.389(merged into main 2026-06-28)
**tab_macro.py 5387 → 1445 LOC(−3942,−73%)** — 10 commit 累計成果。

### B-region(UI section 抽出)
- B-4 hotfix `38d7a10`:_m8_* NameError(production bug,section_mid 抽走後 §九 仍 ref)
- B-S8-A `b59b072`:§三 籌碼桶 558 LOC → `macro/section_chips.py`
- B-S8-B `bec36de`:§九 跨桶 AI 220 LOC → `macro/section_cross_ai.py`

### P1+P2(AI 導航優化)
- `6b4e443`:`macro/__init__.py` INDEX docstring(段落→子模組對照表)+
  section_ai_cross→section_cross_ai / section_ai→section_news_ai 並列命名

### P3 D-region(§8.2 分層治理)
- D-3 `28515db`:_job_bias 42 LOC → `macro_snapshot.compute_twii_bias`
- D-2 `221eb5f`:_job_m1b 89 LOC → `macro_snapshot.fetch_m1b_m2_block`(3-Tier)
- D-1 `9a32589`:_job_macro 604 LOC → 5 `fetch_*_block`(VIX/CPI/Fed/PMI/NDC/Export)
- D-4 `370a430`:7-job orchestrator 230 LOC → `services/macro_fetch_orchestrator.fetch_macro_bundle`

### 新增 / 強化模組
- `src/ui/tabs/macro/` 9 個 section_*.py
- `src/data/macro/macro_snapshot.py`:89 → 798 LOC(fetch 邏輯集中)
- `src/services/macro_fetch_orchestrator.py`:270 LOC(NEW)

### SSOT 檢查結論
0 新違憲。預先存在的 inline magic(100億 / -20000 期空 / 50/100 CLI/PMI 等)留待真實 bug 觸發再 SSOT 化(§-1)。

### 殘餘 tab_macro.py(1445 LOC)
- 紅綠燈卡(_tl_placeholder lifecycle,反模式不可抽)
- 戰情概覽 + 作戰室(過小 + closure 多)
- Registry patch(~165 LOC,可抽但 ROI 低)
- session_state writes 收尾(UI 邊界)

---


## ✅ 累計完成
- P0(4 batch / 4 commit):portfolio_exposure SSOT / RSI helper / stock_names L0→L1 / 4 dead fn
- P1(5 batch / 6 commit):3 處 UI yfinance→L1 / macro_snapshot L4→L1 / shared/macro_card 拔 streamlit / 6 dead fn / 6 dead fn cross 3 檔
- P2(2 batch / 2 commit):_prov_log SSOT / 2 inline magic 入 shared
- 跳過(honest stop,ROI 不對等):
  - P1-3 Gemini API 統一(4 caller payload/retry 分歧大)
  - P1-4b cache_layer PKL_DIR env(L0↔L0 hardcode 設計味道但 Python 不 crash)
  - P2-2 命名衝突分化(_safe_float/_num/_secret,改名影響 caller 多)
  - P2-4 pct_change YoY helper(各處 period 不一,強行 helper 破壞契約)
  - P2-5 to_json_rows generic(2 處不同 dataclass,Protocol 加抽 ROI 低)

## 已完成 commits(reverse chrono)

### E-2 (v18.387) — 20-period vol σ 抽 daily_return_rolling_std SSOT
- **檔案**: `shared/calc_helpers.py` + `src/compute/scoring/scoring_engine.py:122,240`
- **拔毒**: 2 處 `close.pct_change().rolling(20).std()` inline → `daily_return_rolling_std(close, window=20)`
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

**E-1 honest stop**: `rolling(N).mean()` 15+ 處散落,use case 多樣(close/volume/hi-lo/revenue),且本身就是 pandas 內建單行 SSOT,抽 wrap helper 純 cosmetic 無實際 SSOT 價值。

### A1 (v18.386) — Gemini API 5 caller 統一至 ai_fetcher.py
- **檔案**: `src/services/ai_fetcher.py`(NEW)+ ai_engine.py × 3 caller + financial_health_engine.py × 1 + macro_state_locker.py × 1
- **拔毒**: 5 處散落 Gemini call(retry/payload/timeout/model fallback)→ 統一 `post_gemini(api_key, prompt, *, models, persona, temperature, max_tokens, timeout, retries_per_model, retry_after_parse, inter_model_sleep, extra_generation_config, safety_settings, headers)`
- **新拓展**: `extra_generation_config`(topP/topK)+ `safety_settings`(BLOCK_NONE × 4)涵蓋 ai_engine call 1 的特殊 payload
- **回傳 tuple**: `(text, model_used_or_error)` — caller 自決失敗訊息 / emoji header
- **驗證**: 4 unit test(_build_payload + _extract_text)+ full pytest 2220/0 fail
- **commit**: 待 push

### B-S2 (v18.385) — Section 2 拐點偵測抽至 macro/section_state.py
- **檔案**: `src/ui/tabs/tab_macro.py` + `src/ui/tabs/macro/section_state.py`(NEW)
- **拔毒**: render_tab_macro line 2186-2565(380 LOC)§二 拐點偵測 + 市場狀態卡抽出。tab_macro 3402 → 3025 LOC(-11%)
- **closure 4 個 explicit pass**: `_mkt_info, _mkt_placeholder, _tl_placeholder, cd`(extremely manageable)
- **F-7.1 累計**: 5387 → 3025 LOC(**-43.8%**)
- **test fix**: 3 處 source-string assert 改合集(tab_macro + section_state)
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

### A4 (v18.384) — pct_change YoY helper 3 處統一
- **檔案**: `shared/calc_helpers.py`(NEW)+ macro_helpers.py:860 + scoring_engine.py:446 + msl_tw.py:191
- **拔毒**: 3 處 `series.pct_change(N) * 100.0` pattern → 抽 `pct_change_yoy(series, periods=12, multiplier=100.0)`
- **periods param**: 月頻 12(macro_helpers M2 / scoring revenue)+ 日頻 20(msl_tw TWII 20D 跌幅)
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

### A2 (v18.383) — cache_layer PKL_DIR env 注入(解 L0↔L0)
- **檔案**: `shared/cache_layer.py` + `src/config/data_config.py`
- **拔毒**: 原 `from src.config import PKL_DIR` 反向 import L0(L0↔L0 hardcode 設計味道)→ 改 `os.environ.get('STK_PKL_DIR', '/tmp/stock_cache')`,兩 file 同源 env
- **caller 介面**: 完全不變(`from shared.cache_layer import ...` / `from src.config import PKL_DIR`)
- **驗證**: smoke + full pytest 2220/0 fail
- **commit**: 待 push

### C-1+C-2+C-3 (v18.382) — 5 個 inline magic 補抽 SSOT
- **檔案**: shared/signal_thresholds.py + scoring_helpers.py:165 + etf_calc.py:901-907 + macro_helpers.py:948-949
- **拔毒**:
  - C-1:RSI 50/40 入 `RSI_STRONG_LOW/RSI_NEUTRAL_WEAK_LOW`(70/30 已在 config.py)
  - C-2:ETF 上下漲日數 60 入 `ETF_UP_DOWN_DAYS_THRESHOLD`
  - C-3:USDCNY 7.2/7.4 補抽 `CHINA_USDCNY_NEUTRAL/WEAK`(P2-3 已抽 7.0)
- **驗證**: full pytest 2220/0 fail
- **commit**: 待 push

### P2-3 (v18.381) — 2 inline magic 入 SSOT
- **檔案**: `shared/signal_thresholds.py` + `src/compute/macro/macro_helpers.py:947` + `src/compute/scoring/scoring_helpers.py:183`
- **拔毒**: 加 `CHINA_USDCNY_STRONG=7.0` + `VOLUME_RATIO_SURGE_HIGH=3.0`,2 處 caller 改 lazy import
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P2-1 (v18.380) — _prov_log 3 處統一至 provenance.py
- **檔案**: `src/data/core/provenance.py`(NEW)+ etf_fetch.py / daily_data_fetchers.py / nas_server.py 改 thin shim
- **拔毒**: 3 處同名異簽名 _prov_log → 統一 SSOT `prov_log(fn_name, source, result_summary, ticker='')`,3 caller 改 thin wrapper(backward compat)
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P1-5bcd (v18.379) — 6 個 0-caller dead fn 跨 3 檔刪
- **檔案**:
  - `src/data/macro/leading_indicators.py`:刪 build_dataset(line 762)+ render_table(line 809),共 117 LOC
  - `src/services/daily_checklist.py`:刪 get_export_yoy(line 250)+ get_business_indicator(line 255),含 @st.cache_data decorator
  - `src/data/core/data_registry.py`:刪 get_pingable_endpoints(line 573)+ get_summary_stats(line 602)
- **拔毒**: 全 grep 確認 0 caller(任何形式)
- **驗證**: 3 檔 ast.parse + full pytest 2213/0 fail
- **commit**: 待 push

### P1-5a (v18.378) — financial_health_engine.py 刪 6 個 dead analyze_*_module
- **檔案**: `src/services/financial_health_engine.py`
- **拔毒**: 6 個 0-caller def(analyze_survival/operating/profitability/financial_structure/solvency/advanced_diagnostic_module),全 grep 確認 0 caller(含動態 import / multiprocessing)
- **R2 教訓**: R1 awk 過範圍把 _FINANCIAL_STRUCTURE_PROMPT 等 module-level const 也刪了(test golden 引用),revert + R2 精準 disjoint 4 range 刪 def 留 consts
- **LOC**: 1115 → 962 (-13.7%,刪 ~153 LOC dead)
- **驗證**: ast.parse + full pytest 2213/0 fail
- **commit**: 待 push

### P1-4a (v18.377) — shared/macro_card.py streamlit 移除 + 刪 6 dead fn
- **檔案**: `shared/macro_card.py`
- **拔毒**: L0 含 `import streamlit as st` 違憲 + 6 個 0-caller dead fn(render_macro_card / render_macro_card_grid / build_cards_from_indicators / _esc / render_edu_markdown / _z_color)
- **保留**: calc_z_score / make_sparkline(tab_edu.py:158 唯一 caller 真用)
- **LOC**: ~290 → 81(-72%)
- **驗證**: smoke(z + sparkline OK + dir 確認 dead 全刪)+ full pytest 2213/0 fail
- **commit**: 待 push

### P1-1c (v18.376) — tab_macro yfinance ^TWII 2y 抽 L1
- **檔案**: `src/ui/tabs/tab_macro.py` + `src/data/macro/macro_snapshot.py`
- **拔毒**: tab_macro.py:973 line `import yfinance as _yf_bias; yf.download('^TWII', period='2y')` 違憲 → 抽 `fetch_twii_2y_for_ma240()` 至 L1 macro_snapshot.py(同檔有 vix block 模式),tab_macro 改 lazy import + thin call
- **驗證**: ast.parse + full pytest 2213/0 fail
- **commit**: 待 push

### P1-1b (v18.375) — yield_screener fetch_dividend_history 抽 L1
- **檔案**: `src/ui/tabs/yield_screener.py` + `src/data/stock/dividend_fetcher.py`(NEW)
- **拔毒**: line 70-125 fetch_dividend_history 整段含 yfinance + NAS proxy 注入 + 配息聚合 → 整檔搬至 L1。yield_screener 留 thin re-export(`from src.data.stock.dividend_fetcher import fetch_annual_dividends as fetch_dividend_history`)
- **EX-CACHE-1 例外**: L1 fetcher 用 @st.cache_data,允許(只 cache 不用 session_state/UI)
- **驗證**: full pytest 2213/0 fail(1 test source 對齊改合集)
- **commit**: 待 push

### P1-1a (v18.374) — tab_stock_picker yfinance 直呼抽 L1
- **檔案**: `src/ui/tabs/tab_stock_picker.py` + `src/data/stock/picker_fetcher.py`(NEW)
- **拔毒**: line 283 L5 UI 內 `yf.Ticker(...).history(...)` HTTP I/O 違憲 → 抽 `fetch_stock_history_1y(ticker)` 至 L1。_check_one_stock 內改 call helper(yf param 保留 backward compat,內部 dead 不再用)
- **__init__ 同步**: src/data/stock/__init__.py 加 picker_fetcher 入 _SUBMODULES
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P1-2 (v18.373) — macro_snapshot 整檔搬至 L1
- **檔案**: `src/ui/render/macro_snapshot.py` → `src/data/macro/macro_snapshot.py`
- **拔毒**: L4 render 含 yfinance.download HTTP I/O,檔頭自標 "L1 fetchers" 卻放 render/。git mv 整檔搬位 + 4 caller 改 import path
- **caller 改**: src/ui/tabs/tab_macro.py:1051 + tests/test_pr_q5c_singles.py:28,67 + tests/test_macro_snapshot.py:11,56
- **__init__ 同步**: src/ui/render/__init__.py 移除,src/data/macro/__init__.py 加入
- **驗證**: full pytest 2213/0 fail
- **commit**: 待 push

### P0-4 (v18.372) — app.py 4 個 dead fn 刪除
- **檔案**: `app.py`
- **拔毒**: 嚴格 grep 確認 0 caller(任何形式皆無)後刪 4 個 public/private fn:
  - `calc_jingqi` (line 1024, 51 LOC)
  - `render_market_overview` (line 1075, 32 LOC)
  - `render_top_rankings` (line 1107, 23 LOC)
  - `_run_llm_analysis` (line 1559, 78 LOC)
  - 共刪 184 LOC,app.py 1722→1538
- **驗證**: ast.parse OK + full pytest 2213/0 fail
- **commit**: 待 push

### P0-1 (v18.371) — stock_names.py I/O 抽 L1 fetcher
- **檔案**: `src/config/stock_names.py` + `src/data/core/stock_names_fetcher.py`(NEW)
- **拔毒**: L0 config 含 requests/yfinance HTTP I/O(嚴重違憲)→ I/O + cache 邏輯抽 L1 fetcher。stock_names.py 留 _STATIC_NAMES const + get_stock_name/refresh_name_cache thin shim(lazy import L1)
- **驗證**: smoke(static lookup 台積電 ✓ + unknown fallback ✓);full pytest 2213/0 fail
- **commit**: 待 push

### P0-3 (v18.370,commit a08786b) — RSI 計算抽 compute_rsi SSOT
- **檔案**: `src/compute/scoring/scoring_engine.py`
- **拔毒**: line 104-106 + 239-241 同檔重複 4 行 RSI 邏輯 → 抽 `compute_rsi(close, period=14)` 純函式,2 處 caller 改 1 行 call
- **驗證**: 全 pytest 2213/0 fail

### P0-2 (v18.369,commit 9b2f8f0) — portfolio_exposure SSOT 收攏
- **檔案**: `src/services/market_strategy.py`
- **拔毒**: 刪同名異實作 def(line 148-161),改 `from src.compute.risk.risk_control import portfolio_exposure`
- **SSOT**: L2 `risk_control.portfolio_exposure(regime)` 為唯一定義
- **驗證**: 全 pytest 2213/0 fail

## 待動 batch
- P0-1 stock_names.py I/O 抽 L1 fetcher
- P0-4 dead fn 驗證 + 刪(8 個候選)
- P1-1 ~ P1-5 結構性收乾
- P2-1 ~ P2-5 漸進命名 / SSOT 補
