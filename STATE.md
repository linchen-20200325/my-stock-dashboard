# 重構狀態看板(深層拔毒 v18.369+)

## 進行中 batch
深層稽核 P0+P1+P2 全做(14 batch / ~10.5 hr / 7-8 commits)

## 已完成 commits(reverse chrono)

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
