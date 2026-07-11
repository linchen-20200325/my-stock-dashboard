# 紅綠燈健康評分權重重設計 — 方法論定案 (Proposal)

> 狀態：**Path 1 已核准實作**（user AskUserQuestion 定案）。本檔為 §8.1 架構設計 + §7 數學式的正式存檔，列入待核准/追蹤。
> 對應 code：`src/compute/macro/health_calibration.py`（L2 純函式，Phase 1）+ `scripts/`（Phase 2，cron 執行）。

---

## 0. 背景與觸發

- `MACRO_CALIBRATION.md`：`mkt_info.score` 對未來 60 日 TWII 報酬相關 = **−0.452**（20 日 −0.109）；🔴 precision **1.6%**、🔴 燈後平均 20 日報酬 **+1.38%**（反指標）。
- **關鍵限制**：該證據模式為 **「TWII-only · DEMO 合成資料 (sandbox)」**——外資流/ADL/外資期/M1B-M2/景氣全填中性預設。**不是真實市場資料**。
- 現行健康評分權重 `0.4 / 0.4 / +20` **從未用真實資料擬合過**。
- ∴ 任何「照 −0.452 反推/反轉權重」= 對合成雜訊過擬合（違 §1）。**第一步是取得真實資料，不是改權重。**

## 1. 現況（順帶校正文件漂移）

真實函式是 **`calc_traffic_light`**（`macro_helpers.py:35`），非文件說的 `compute_macro_health`。健康評分**只有 3 輸入**：

```
health = 0.4 · jqavg                      ← 大盤廣度（jingqi_info['avg']）
       + 0.4 · min(score/5 · 100, 100)    ← market_regime() 分數
       + (20 if 外資淨買 > 0 else 0)        ← 只看正負號，不看量級
```

紅綠燈是決策樹吃 `health` + `regime` + `防禦旗標`（macro_helpers.py:128-147）。

**三處文件 vs 實際不符（重設計須知）**：
| 項 | 文件 | 實際 |
|---|---|---|
| A | CLAUDE.md §3.2/§4.2「6-factor 權重和=1.0」+ `assert sum=1.0` | 健康評分是 **3 項、和 0.8 + 非正規化 +20**；「6 因子」在下一層 `market_regime` |
| B | — | health 把 score **除以 5**（`CONFIDENCE_SOURCE_COUNT`），但 `market_regime` 滿分是 **4 或 6** → 預設模式 score 到不了 100 天花板（準真 bug） |
| C | — | `MACRO_THRESHOLDS` 19 個指標（VIX/CPI/DXY…）**未進**健康評分，只驅動危險卡 |

**live `jqavg` 真相**（`jingqi_calc.py:43` + `fetch_adl` ①）：`jqavg = mean(ad_ratio_{t-4..t})`（5 日），而 `ad_ratio` 本身**重度是 ^TWII 估算**（`is_proxy=True`，公式「漲跌幅 ±1%≈±150 家、900 基準」，精確漲跌家數才覆蓋）。→ 重建 jqavg 歷史可**複用 `twii_ohlcv.parquet` + 鏡像同一 proxy**，成本低。

## 2. 定案決策（user AskUserQuestion）

| 決策 | 選擇 | 意義 |
|---|---|---|
| ① 目標函數 | **規避回撤・風險姿態** | 燈學「該防禦嗎」，非報酬預測器 |
| ② 時界 | **20 交易日** | 對齊部位調整頻率 |
| ③ 特徵集 | **先維持現 3 輸入** | jqavg/score/fnet + 修 /5 錯配；擴充指標標「先不做」 |
| ④ 資料 | **先建 jqavg 歷史重建管線** | 唯一不靠合成資料的路 |
| §7 數學式 | **接受照定義走** | 見 §3 |
| 存檔 | **本檔** | 追蹤用 |

## 3. §7 數學式（已 user 確認）

**① jqavg 重建（SSOT parity with `jingqi_calc` + `fetch_adl` ①）**
```
r_t = TWII 日漲跌幅（%）
up_t   = clip(900 + 150·r_t, ≥0)
down_t = clip(900 − 150·r_t, ≥0)
ad_ratio_t = up_t / (up_t + down_t) · 100        （total=0 → NaN，不偽造）
jqavg_t = mean(ad_ratio_{t-4 … t})               （5 日；前 ~5 日 NaN）
```
此為 live jqavg 的 **PROXY tier**；精確漲跌家數回填為**選配精度升級**（§6）。

**② 20 日「風險姿態」真值**
```
MDD_t = max_{t<k≤t+20} ( (max_{t≤j≤k} C_j − C_k) / max_{t≤j≤k} C_j )
y_t   = 1 (該防禦)  if MDD_t·100 ≥ θ_dd   else 0
```
θ_dd 預設 8%（對齊既有 `RED_20D_THR` 精神），**待 OOS 驗證，不寫死**。尾端不足 20 日 → NaN（訓練 drop）。

**③ 權重擬合（objective = 風險姿態分類）**
```
x_t = [ jqavg_t , score_norm_t , fnet_t ]      （score_norm 修除5錯配 → 除真實 max 4/6）
min_w  Σ_folds [ Σ_t logloss(y_t, σ(w·x_t)) + λ‖w‖² ]     （walk-forward, λ 由 inner-CV 選）
```
純 numpy L2-logistic（**不引 sklearn/scipy**，§8.1 step6 反過度依賴）。robustness voting（跨 fold 權重方差）+ overfit guard（drift>30% 或 fold 符號翻轉 → flag revert）。擬出 w 映回 raw 特徵空間供人審。

## 4. §8 架構

**單一職責**：離線校準管線，產出**提案權重**，**不直接改 SSOT**。

```
twii_ohlcv.parquet (+選配 TWSE 漲跌家數)
   │  scripts/update_breadth_history.py   (L1 cron，鏡像 fetch_adl proxy)
   ▼
data_cache/breadth_history.parquet  +  finmind_inst.parquet(fnet) + score 重建
   │  src/compute/macro/health_calibration.py  (L2 純函式，無 I/O)
   │     breadth_from_twii / risk_posture_label / fit_health_weights
   ▼
[X,y] → walk-forward fit → scripts/calibrate_health_weights.py 寫 MACRO_HEALTH_WEIGHT_PROPOSAL.md
   ▼
(人工審) → 一個小 commit 改 signal_thresholds 3 個權重常數
```
- **依賴方向**：L2 純函式無上行 import；scripts 讀 L1/L2；不碰 L3+。
- **失敗降級（§1）**：labeled 樣本不足 / fold 太少 → **raise**，不輸出擬合值、不用合成資料。
- **過度設計自評（§8.1 step6）**：最小版＝`twii_ohlcv` 重建 proxy breadth + 3 權重 logistic + walk-forward。**不**做精確漲跌家數回填、**不**加特徵、**不**加 sklearn → 全標「等最小版證明 ROI 再加」。

## 5. 落地階段

| Phase | 內容 | 執行地 | 狀態 |
|---|---|---|---|
| **1** | `health_calibration.py` L2 純函式 + 單測（機器） | in-session（可驗） | ← v19.92 |
| **2** | `scripts/update_breadth_history.py` + `scripts/calibrate_health_weights.py`（wiring） | 部署 cron | 待做 |
| **3** | 人審 proposal → 小 commit 改 `signal_thresholds` 3 權重 | 人工 | 待 Phase 2 產出 |

## 6. 已知近似與誠實限制

- **重建 jqavg = live 的 PROXY tier**（^TWII 推估），非精確漲跌家數。live 本身多數時候也吃這個 proxy，故偏差有限；精確回填為選配升級。
- **真實擬合在部署 cron**：沙箱無 `twii_ohlcv.parquet` + egress 被擋 → in-session 只交付「可單測的演算法」，**真實權重提案要 user 在部署環境跑**。
- **θ_dd（8%）待 OOS 驗證**；合成資料**不可**用於最終擬合（§1）。
- 「除 5 錯配」由 Phase 3 re-fit 一併解決（不另手改，避免 churn）。
