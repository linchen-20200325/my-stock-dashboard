# 重構狀態看板(深層拔毒 v18.369+)

## 進行中 batch
深層稽核 P0+P1+P2 全做(14 batch / ~10.5 hr / 7-8 commits)

## 已完成 commits(reverse chrono)

### P0-2 (v18.369) — portfolio_exposure SSOT 收攏
- **檔案**: `src/services/market_strategy.py`
- **拔毒**: 刪同名異實作 def(line 148-161),改 `from src.compute.risk.risk_control import portfolio_exposure`
- **SSOT**: L2 `risk_control.portfolio_exposure(regime)` 為唯一定義
- **驗證**: 全 pytest 2213/0 fail
- **commit**: 待 push

## 待動 batch
- P0-3 RSI 同檔重複抽 helper(scoring_engine.py:104 vs :239)
- P0-1 stock_names.py I/O 抽 L1 fetcher
- P0-4 dead fn 驗證 + 刪
- P1-1 ~ P1-5 結構性收乾
- P2-1 ~ P2-5 漸進命名 / SSOT 補
