# 紅綠燈健康評分權重 — 校準提案（自動產生，待人審）

> 由 `scripts/calibrate_health_weights.py` 產出。方法論見 `MACRO_HEALTH_REWEIGHT_PROPOSAL.md`。
> **本檔僅為提案,未改任何 code / SSOT 常數**;Phase 3 人審後才手動改 `signal_thresholds`。

- 樣本區間: 2006-09-29 ~ 2026-08-31（labeled n=4750）
- 正例（該防禦）比例: 12.8%
- 選定 λ（L2）: 0.1
- 交叉驗證 val AUC: 0.714 / log-loss: 0.3333
- 穩健性 fold 權重相對方差: 0.561（sign_flip=True）
- ⚠️ overfit_flag: **True**（True = 跨 fold 不穩,**勿貿然採納**）

## 擬合權重（raw 特徵空間 → 對照現行 0.4 / 0.4 / +20）

| 特徵 | 擬合權重 | 現行 |
|---|---|---|
| jqavg | -0.0277 | 0.40 |
| score_norm | -0.0087 | 0.40 |
| fnet | -0.000520 | +20（sign-only）|
| intercept | -0.0863 | — |

## 人審檢查點（Phase 3 才動 code）
1. AUC 是否顯著 > 0.5？overfit_flag 是否 False？否則**不採納**。
2. 權重方向是否合理（低廣度→該防禦 = jqavg 負向）？
3. 若採納:改 `shared/signal_thresholds` 的 `HEALTH_WEIGHT_JQ` / `HEALTH_WEIGHT_SCORE` /
   `HEALTH_FNET_BONUS` + 修 `CONFIDENCE_SOURCE_COUNT` 除數錯配,附本提案為 PR 證據。
4. ⚠️ 資料為 ^TWII proxy 廣度 + 本地重建 score;若日後接精確漲跌家數需重跑。

## 輸入資料的 as-of（自動填,勿手改）

| 資料集 | 最新資料日 | 距產出日 | metadata.last_updated |
|---|---|---|---|
| twii_ohlcv | 2026-10-01 | 0 天 | 2026-10-01 |
| finmind_inst | 2026-10-01 | 0 天 | 2026-10-01 |
| finmind_m1m2 | 2026-08-01 | 61 天 | 2026-08-01 |
