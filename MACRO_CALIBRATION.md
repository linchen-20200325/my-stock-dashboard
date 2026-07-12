# MACRO_CALIBRATION.md — 台股紅綠燈系統校準報告

> 自動產生：2026-07-12 01:19　|　模式：**Cache enriched (TWII + FinMind 籌碼/M1M2, 2y)**

- **回測期間**：2025-01-15 ~ 2026-06-10
- **有效樣本**：337 個交易日
- **燈號分佈**：🟡 142 日 · 🟢 129 日 · 🔴 66 日

---

## (a) 每個燈號的真實 vs 預測勝率

**真值定義**：
- 🔴 高風險命中 = 後 20 日 TWII 跌幅 > 8.0% 或 後 60 日跌幅 > 15.0%
- 🟢 多頭命中 = 後 20 日 TWII 漲幅 > 5.0%
- 🟡 中性 = 其他

**勝率指標**：

| 燈號 | 預測次數 | 真值次數 | Precision (對的%) | Recall (抓到%) | 備註 |
|------|----------|----------|-------------------|----------------|------|
| 🟢 多頭 | 129 | 163 | **56.6%** | 44.8% | 預測 🟢 後實際 20 日漲 >5% 比例 |
| 🔴 防禦 | 66 | 18 | **22.7%** | 83.3% | 預測 🔴 後實際發生 8% 跌幅比例 |

**Confusion Matrix**：

```
truth         green_hit  neutral  red_hit
pred                                     
green_pred           73       56        0
neutral_pred         61       78        3
red_pred             29       22       15
```

**按燈號分組的後續報酬**（mean / median / count）：

```
        ret_20d                    ret_60d                 
           mean    median count       mean     median count
color                                                      
🔴      1.005745  3.976648    66   9.562074  11.927411    66
🟡      4.421715  4.297036   142  16.521112  16.238344   128
🟢      6.019636  6.423890   129  16.846152  16.646958   103
```

## (b) 因子相關性矩陣

**`mkt_info.score` 與後 N 日報酬的相關係數**：

- score ↔ ret_20d：**0.376**
- score ↔ ret_60d：**0.322**

> 絕對值 > 0.2 視為弱相關，> 0.4 為中等，> 0.6 為強相關。
> 若 corr 接近 0：score 對未來報酬幾乎無預測力，需重新設計分數權重。

## (c) 門檻調整建議

> 現行門檻（讀自 `macro_helpers`）：🔴 防禦 `health < 35`、🟢 多頭 `regime=='bull' AND score >= 4`。

- 🔴 **防禦 precision 22.7% < 40%**：現行 `health < 35`，可考慮再收緊至 30，或追加「外資連續賣超 3 日」作為門檻共識條件。

---

## ⚠️ 樣本不足 / 限制聲明

- **TWII-only mode**：本次回測僅注入 ^TWII OHLCV 資料，外資買賣超、ADL、外資期貨、M1B-M2、jingqi 等指標均以「中性預設」（0 / 1.0 / None）代入。實務上完整版會多 2~3 分 score。
- **FinMind 歷史 quota 限制**：M1B-M2、ADL、外資期貨日 series 目前無歷史 fixture，校準完整版需先在 NAS 端 batch 抓 365 日歷史並 cache 至本機後重跑。
- **真值定義為單一閾值**：8% / 15% / 5% 為經驗值，未做 OOS 驗證；若改用 Sharpe / max drawdown 為真值，結論可能不同。

---
*產生工具：`calibrate_macro_traffic.py`　|　資料源：^TWII (Yahoo Chart via NAS proxy)　|　報告時間：2026-07-12 01:19*