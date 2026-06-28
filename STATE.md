# 重構狀態看板(深層拔毒 v18.369+)

## 進行中 batch
深層稽核 P0+P1+P2 全做(14 batch / ~10.5 hr / 7-8 commits)

## 已完成 commits(reverse chrono)

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
