# 階段1 交付物 #2 — 指標 SSOT 附錄

> **產出日**：2026-09-14 ｜ **性質**：唯讀盤點，未修改任何 repo 檔案
> **範圍**：台股/ETF 站（`/home/user/my-stock-dashboard`）＋ 基金站（`/home/user/linchen-20200325/my-fund-dashboard`，唯讀 clone）
> **紀律**：`§1 Fail Loud` — 查不到的算式一律寫「**查不到**」，不以常識補標準式；`§-2 規則 6` — 全稱句一律自標「單組結論」。

---

## 0. 閱讀前必看

### 0.1 兩種 repo 狀態（台股站）

> 🚨 **狀態在本次作業進行中改變了 —— PR #673 已於 2026-09-14 17:27 +0800 merge 進 `origin/main`。**
> **不是我做的**（我全程唯讀，未執行任何 git 寫入指令）。詳見 §7。
> 本節保留兩種狀態的區分，因為「**merge 前的 production 行為**」仍是理解問題的必要參照。

| 狀態代號 | 指涉 | git 座標 | 現況 |
|---|---|---|---|
| **[main-pre]** | PR #673 **merge 前**的 `origin/main` | `67c8306` | **已被取代**（2026-09-14 17:27 前的 production 行為） |
| **[673]** | PR #673 的修正內容 | 開工時：分支 `claude/stock-dashboard-handoff-g9dtm0`，工作樹 HEAD `ee6ffa5`，PR 狀態 `open / draft / merged:false` | **已 merge** → squash 成 `5808c03`，**現為 `origin/main`** |

**Merge 事實（實測）**
- Merge commit：`5808c03` 「fix(§1): 缺資料不得產出結論 —— 財報假結論四條路徑 ＋ 頁1 原地取數 ＋ 頁5 十六盞燈 **(#673)**」
- 作者：`linchen-20200325 <cheng10022@gmail.com>`，時間 `Mon Sep 14 17:27:31 2026 +0800`
- 規模：15 檔、`+5,749 / −197`
- `git branch -r --contains 5808c03` → `origin/main` ✅
- `git show origin/main:src/services/financial_health_engine.py | grep -c FIELD_ABSENT` → **22**（merge 前為 **0**）

⚠️ **對本附錄的影響**：下文凡標 **[673]** 者，**現在就是 production**；凡標 **[main]／[main-pre]** 者，描述的是 **2026-09-14 17:27 之前**的行為。
⚠️ **交辦當時的前提「該 PR 尚未 merge」在我開工時成立、在我收工時已不成立** —— 兩個時點的實測證據都附在上表，請以此為準。

### 0.2 缺值語彙

本附錄統一用三個詞，對應 [673] 在 `financial_health_engine.py` 建立的三態：

- **ABSENT**：key 不存在／值為 None／NaN／不可轉數字
- **ZERO**：欄位在，值**真的**是 0（＝一個觀測值）
- **VALUE**：欄位在且非 0

⚠️ 這三態在 [673] 自己的檔頭就標註了一件重要的事（逐字轉錄，屬該檔自陳）：
> 「**`FIELD_ABSENT` 在現行 fetcher 契約下對 production 資料永遠不會發生。**」
> 因為 `financial_statements_fetcher._v()` 查無時回 `0.0`、**永遠不回 None**，且 return dict 每個 key 必定存在。

⇒ **production 的缺漏偵測實際上靠的是領域規則**（`_stmt_gap` / `gp <= 0` / `assets <= 0` / 分母 `> 0`），不是 ABSENT 偵測。本附錄各節的「缺值時回什麼」一律記錄**領域規則**那一條，因為那才是會觸發的。

---

## 1. 母法四條釘死算式 — 逐條查證結果

> 客戶在母法釘死四條。本節逐條比對現行 code。**四條全部有落差**，其中兩條是根本性的。

### 1.1 Sharpe

**母法要求**
- 年化 252 日
- 台股無風險利率 → **台灣央行 1 年期定存利率**
- 海外標的 → **美國 3 個月國債殖利率（DTB3）**
- 台幣投海外資產 → 統一以 DTB3 為主、台幣定存為 fallback 並標註

**現行 code（三份實作，互不相同）**

| # | 位置 | 算式 | 週期 | 報酬定義 | rf 來源 |
|---|---|---|---|---|---|
| **S-1** | `src/compute/etf/etf_calc.py::calc_sharpe` | `(mean(r)·252·100 − rf_pct) / (std(r)·√252·100)` | 日 | **簡單報酬** `pct_change()` | 模組級 `_RF_PCT` |
| **S-2** | `src/compute/etf/dividend_station.py::sharpe_weekly` | `(mean(r_w) − rf_pct/100/52) / std(r_w, ddof=1) · √52` | **週** | 簡單報酬 | 由 caller 注入 |
| **S-3**（基金站） | `services/fund_service.py` | `(mean(r252) − rf_daily) / std(r252) · √252` | 日 | **對數報酬** `log_ret` | 模組級 `_RF_ANNUAL` |

**rf 實際來源（三份全部相同，且三份全部不是母法指定的）**

- 台股站：`ensure_etf_rf_injected()` → `src/data/macro/macro_snapshot.fetch_fed_funds_block` → **FRED `FEDFUNDS`（美國聯邦資金有效利率月均）**
- 台股站 fallback：`ETF_SHARPE_RF_FALLBACK_PCT = 5.33`（`shared/signal_thresholds.py:455`，自陳為 2024 年 FEDFUNDS 水準）
- 基金站：`_RF_ANNUAL = 0.04`（4%），載入總經資料後改為 **FEDFUNDS**；合法帶 `[0, 0.25]`
- 基金站效率前緣：`FRONTIER_RF_ANNUAL = 0.0`（**rf = 0**）

**落差（這是本附錄最重要的一條）**

1. ❌ **DTB3 完全未被使用。** 全 repo grep `DTB3` → **0 命中**（兩站皆然，單組結論）。
2. ❌ **台灣央行 1 年期定存利率完全未被使用。** grep `定存` 的全部命中都是 M1B/M2 的文案與教學字串，**沒有任何一處是利率取值**（單組結論）。
3. ❌ **無「台股 vs 海外」的 rf 分流。** 三份實作都用同一個全域 rf，不看標的國別。母法的「台幣投海外資產統一以 DTB3」這條在 code 裡**沒有對應的分支**。
4. ⚠️ **252 這一條台股站部分符合、部分不符**：S-1 符合（`TRADING_DAYS_PER_YEAR=252`）；**S-2 用的是 √52 週化**，不是 252 日化。S-2 是「存股月月配站」健檢 B 燈的唯一 Sharpe 來源。
5. ⚠️ **S-1 vs S-3 的報酬定義不同**（簡單 vs 對數）。兩者在小報酬下近似，但在波動大的標的上不等價，且**兩站同一檔標的會給出不同 Sharpe**。
6. ⚠️ `FRONTIER_RF_ANNUAL = 0.0` 的註解寫「與 performance_metrics 一致」——**效率前緣的 max-Sharpe 點是在 rf=0 下解出來的**，與同站 `fund_service` 的 rf=FEDFUNDS 不一致。

**N/A 觸發條件表 — Sharpe**

| 實作 | 條件 | 回傳 |
|---|---|---|
| S-1 | `len(ret) < 20` | `0.0` ⚠️ **不是 None** — 見下方警告 |
| S-1 | `ann_vol <= 0` | `0.0` ⚠️ 同上 |
| S-1 | 任何例外 | `0.0` + stderr log ⚠️ 同上 |
| S-2 | `weekly_close is None` 或 `len < min_weeks+1`（`MA_QUARTER_WEEKS`=13 → 需 ≥14 點） | `None` |
| S-2 | `len(rets) < min_weeks` | `None` |
| S-2 | `mu` / `sd` 非有限，或 `sd ≈ 0`（`FLOAT_ABS_TOL`） | `None` |
| S-3 | `n252 < MIN_OBS_SHARPE_SORTINO` | `None` + reason 字串 |
| S-3 | `std252 <= 1e-12`（常數 NAV／停售） | `None` + `"σ=0(常數 NAV / 停售,§4.6)→ Sharpe 未定義"` |

> 🚨 **S-1 的 `0.0` 是一個 §1 違憲點（本附錄新記錄，單組結論）。**
> `calc_sharpe` 在資料不足／波動為零／例外三種情況全部回 **`0.0` 而不是 `None`**。
> Sharpe = 0 是一個**有意義的觀測**（「報酬恰等於無風險利率」），不是缺值。
> 而消費端 `health_b` 的判燈是 `sharpe < SHARPE_NEG_THRESHOLD(=0)` → `0.0` 落在 🟢「Sharpe ≥ 0」。
> ⇒ **一檔資料不足的標的會拿到綠燈**。
> ⚠️ 但要分清楚：**`health_b` 實際吃的是 S-2（`sharpe_weekly`）不是 S-1**（見 `dividend_station_service` 的 `m["sharpe"] = ds.sharpe_weekly(...)`），S-2 正確回 `None` → ⚪。
> **S-1 的 `0.0` 流向何處（ETF 評分 `build_etf_score_row` / 多檔比較表）本次未追到底 —— 見 §6 未驗事項 U-3。**

---

### 1.2 基金淨值與同類中位數

**母法要求**
- 基金淨值採**還原權值（含息）**
- 同類中位數**錨定公會／晨星標準**並**標註更新週期**

**現行 code**

**(a) 還原權值（含息）— 部分符合，有明確的不含息 fallback**

`services/fund_total_return.py` 定義了 4 層 precedence（逐字轉錄其 docstring）：

```
1. perf["1Y"]      wb01 真 1Y / 本地還原淨值法注入
2. ret_1y_total    本地含息計算(可能短窗口年化)
3. ret_1y          純 NAV 變化率(不含息)          ← ⚠️ 不含息
4. NAV 序列年化    最後手段(跨度須 ≥ RET_1Y_EXTRAPOLATE_MIN_DAYS, scale cap 2x)  ← ⚠️ 不含息
```

對應的來源標籤常數（會**原樣印給使用者**）：
- `SRC_OFFICIAL = "MoneyDJ 官方"`
- `SRC_SELF_RESTORED = "自算（還原含息淨值）"`
- `SRC_SELF_TOTAL = "自算含息"`
- **`SRC_SELF_NAV_ONLY = "自算（僅淨值，不含配息）"`** ← 第 3 層
- **`SRC_SELF_ANNUALIZED = "自算（{days} 天資料外推年化）"`** ← 第 4 層
- `SRC_TOO_SHORT = "—（僅 {days} 天資料，不足以推算一年）"`

⇒ ✅ **有還原含息路徑**（第 1、2 層），且**來源標籤誠實標明**哪一層在講話。
⇒ ❌ **但不是「一律採還原權值」** —— 第 3、4 層是**純價格**，母法字面不允許。
⇒ ✅ 第 4 層已有防護：`is_extrapolated_1y_source()` 命中時吃本金判定端應**拒判**（⚪），檔內自陳這是修 ACTI71 假 🔴 的那條。

**(b) 另一處純價格：** `services/benchmark_compare.py` 檔頭逐字自陳：
> 「兩個產物,皆**純價格對純價格**(基金 NAV 不含息 vs 指數不含息…)」

⇒ 「與大盤比較」這個產物**整條是不含息的**，與母法直接衝突。（誠實標註，未掩蓋。）

**(c) 同類中位數 — ❌ 兩個要件都不符**

| 母法要件 | 現行 code |
|---|---|
| 同類**中位數** | 用的是 **MoneyDJ「同類型平均」**（`_extract_peer_1y` 找 key 含「平均」的那一列）。**平均 ≠ 中位數**，厚尾分布下兩者差距可觀。 |
| 錨定**公會／晨星** | 錨定 **MoneyDJ `risk_metrics.peer_compare`**。grep `晨星/Morningstar/SITCA/投信投顧公會` 在**計算路徑上 0 命中**（晨星只用於**補淨值**：`morningstar_secid` / `YF_MORNINGSTAR_CHART_URL`；SITCA 只出現在 `shared/schemas.py` 的 provenance 前綴白名單）。唯一一處提到公會的是 `ui/helpers/fund_grp_health/investment.py:163` 的一句**文案**：「或到晨星 / 投信投顧公會查同類清單」——那是叫使用者自己去查，不是系統錨定。 |
| 標註**更新週期** | **查不到**。本次未找到任何 `peer_compare` 的更新週期宣告或 TTL 標註（單組結論，見 §6 U-5）。 |

**(d) 另一條同類路徑（小 universe，不是母法講的那個）**

`services/peer_rank.py` 提供 `quartile_rank`，但它的母體是「**持倉 ∪ 選股池**」這種小 universe，不是公會同類母體。它的樣本量誠實度很高：
- 同類 < 2 檔 → 不給名次
- 2~3 檔 → 只給相對排名 X/n，**不分四分位**
- ≥ `PEER_QUARTILE_MIN_N`(=4) → 真四分位 + 揭露分母

**N/A 觸發條件表 — 同類比較**

| 條件 | 回傳 |
|---|---|
| `moneydj_raw.risk_metrics.peer_compare` 空 | `(None, "")` → `_grade` 回 `"⬜ 同類資料不足"` |
| peer_compare 有但找不到含「平均」的 key | `(None, "")` → 同上 |
| 找到 key 但整列無可轉數字的值 | `(None, best_key)` → 同上 |
| 自身 `ret_1y` 缺 | `"⬜ 報酬資料不足"` |
| `peer_rank`：同類 < 2 檔 | `"無同類可比(同類 < 2 檔)"`，rank/percentile/quartile 全 None |
| `peer_rank`：2~3 檔 | rank 有、**quartile = None**、`enough_sample=False` |

> 📌 `ui/helpers/fund/checkup.py:7` 自陳：「同類平均取自 MoneyDJ 績效評比頁 risk_metrics.peer_compare，**約 3 成基金抓不到** → 標 ⬜ 不評。」
> ⇒ 這條指標的實際覆蓋率約 **7 成**（該檔自陳值，本次未獨立量測）。

---

### 1.3 本益比（TTM）

**母法要求**
- 近四季 EPS 總和
- **EPS ≤ 0 統一標註 `N/A（虧損）`**

**現行 code — ❌ 根本性不符：本站不自己算 PE**

PE 的唯一 SSOT 是 `src/data/stock/yield_pe_fetcher.fetch_pe_name_maps()`，它**不計算 PE**，而是**直接取用交易所公告值**：

| 市場 | 端點 | 欄位 |
|---|---|---|
| 上市 | `https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_d` | `PEratio` |
| 上櫃 | `https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis` | `PriceEarningRatio` |

**合併規則**：上市先填 `setdefault`（§2.1 上層先填者贏，不平均）；任一源失敗 **fail-soft**，只少半邊涵蓋。

**落差**

1. ❌ **不是「近四季 EPS 總和」** —— 是 TWSE／TPEX 伺服器端算好的值。**TWSE 的 PEratio 口徑本站沒有宣告**，本附錄**不替它補一個**（§1）。
2. ❌ **沒有 `N/A（虧損）` 這個標籤。** 實作是「**PE ≤ 0 → 不放進 `pe_map`**」：
   ```python
   if _pe != _pe or _pe <= 0:      # NaN / ≤0 → 無本益比,不放 key
       continue
   ```
   ⇒ 結果是「這檔沒有本益比」，**不是**「這檔虧損」。畫面上它與「來源沒給」**長得一模一樣**。
3. ⚠️ **判定邊界是 PE ≤ 0，不是 EPS ≤ 0。** 兩者在數學上等價（price > 0 時），但 code 裡**沒有 EPS 這個輸入**，所以無法區分「虧損」與「來源空值」。該檔 docstring 自陳這個 `<= 0` 檢查只是「對來源改用 0 佔位的防呆」，因為 TWSE 給空字串、TPEX 給 `'-'`，實務上已是 NaN。
4. ✅ **有一個正確的防禦**：docstring 明寫 —— pe_low 因子是「值越小分越高」，若讓 0／負數進榜，**虧損股會被排成「全市場最便宜」**。這一條擋住了。

**另有一處「近四季 EPS 總和」，但它不是 PE**

`src/compute/scoring/scoring_helpers.py:59`：
```python
es = _pd_fs.to_numeric(qtr_df[eps_c].tail(4), errors='coerce').dropna()
sm = float(es.sum()) if len(es) >= 2 else 0
ok = sm >= 1
result['profit']['checks'].append(('近4季EPS>=1', f'{sm:.2f}', ok))
```
⚠️ **兩個問題（單組結論）**：
- 標籤寫「近4季EPS」，但門檻是 `len(es) >= 2` —— **只有 2 季也照樣加總並標成「近4季」**。
- `else 0` → 季數 < 2 時 sum 記為 `0`，然後 `ok = 0 >= 1 = False` 記為未達標。**缺資料被記成「不及格」**，而不是「未評估」。這是同一族的 §1 問題，**[673] 沒有動到這一處**。

**N/A 觸發條件表 — 本益比**

| 條件 | 現行行為 | 是否符合母法 |
|---|---|---|
| TWSE `PEratio` 為空字串 | `to_numeric(errors='coerce')` → NaN → 不入 `pe_map` | 部分（是 N/A，但無「虧損」標註） |
| TPEX `PriceEarningRatio` 為 `'-'` | 同上 | 同上 |
| PE ≤ 0 | `continue`，不入 `pe_map` | ❌ 無 `N/A（虧損）`標註 |
| PE 不可轉 float | `except (TypeError, ValueError): continue` | 部分 |
| 整個 TWSE 端點 200 以外／格式異常 | 回空 DataFrame + stderr log | fail-soft，上櫃仍可用 |
| 兩個端點都失敗 | `pe_map = {}`；UI 顯示「本輪拿到的本益比對照表是空的」 | ✅ 誠實 |
| 該檔不在 pe_map | 選股網「估值」因子不計分，並由 `SCREENER_MIN_FACTOR_COVERAGE_RATIO` 涵蓋門檻決定是否整檔擋出榜單 | ⚠️ 缺值會**影響入榜資格**，非只是少一分 |

---

### 1.4 殖利率

**母法要求**
- 近一年累計已除息總額 ÷ 最新收盤價
- **不配息標的顯示 `N/A`**

**現行 code — 三條路徑，只有一條符合**

| 路徑 | 位置 | 算式 | 符合母法？ |
|---|---|---|---|
| **Y-1 ETF／月月配站** | `dividend_station.annual_yield_pct` | `ttm_dividend / price × 100`，其中 `ttm = Σ div[index ≥ as_of − 365d]`、`price = _close.iloc[-1]` | ✅ **完全符合** |
| **Y-2 個股 357** | `v5_modules.calc_357_valuation` | `est_yield = avg_div_twd / price × 100` | ❌ **不符** — 分子是**近 5 年年度現金股利的平均**，不是近一年累計 |
| **Y-3 全市場掃描** | `yield_pe_fetcher` | TWSE `DividendYield` / TPEX `YieldRatio` 直接取用 | ⚠️ **口徑未宣告** |

**Y-2 的分子怎麼來的**（`src/data/stock/app_stock_fetchers.py:193-194`）：
```python
yr = ddf.groupby('year')['cash'].sum().reset_index().tail(5)
avg_div = float(yr['cash'].mean()) if len(yr) > 0 else 0
```
⇒ **近 5 個日曆年度、每年現金股利加總後取算術平均**。這是一個「平滑化的常態配息能力」，**不是**母法定義的「近一年累計已除息總額」。
⚠️ 另注意同段 `.fillna(0)` 在 cash 欄上 —— 缺值被當成 0 元配息計入平均，會**稀釋** `avg_div`（§1 記錄，[673] 未動）。

**「不配息 → N/A」符合度**

| 路徑 | 不配息時 | 是否 N/A |
|---|---|---|
| Y-1 | `fetch_etf_dividends` 回空 → `m["annual_yield_pct"]` **不設值** → `health_a` 回 `Flag("⚪", "A 資料不足（缺年化配息率 —— 配息沒抓到）", miss_reason=MISS_NO_INPUT)` | ✅ 是 ⚪，且帶原因 |
| Y-2 | `avg_div ≤ 0` → `classify_stock_357_price` 回 `'na'` → `{"est_yield": None, "signal": "⚪ 未評估", "msg": "無配息記錄，357 殖利率法則不適用（不以 0% 代替，避免誤判為超貴）"}` | ✅ 是 ⚪，且**明文拒絕用 0% 代替** |
| Y-3 | TWSE `DividendYield` 空字串 → NaN。**B6-b 修正後刻意不 dropna**，該檔保留 PE／名稱 | ✅ 缺值就是缺值，不連坐 |

⇒ ✅ **「不配息顯示 N/A」這半條，三條路徑都做到了，而且做得比母法要求更細**（帶缺值原因、明文拒絕 0% 代替）。
⇒ ❌ **「近一年累計 ÷ 最新收盤價」這半條，只有 Y-1 符合。**

---

### 1.5 補充：`YIELD_HIGH` 量綱雙胞胎（客戶點名項）

**現況**：`shared/thresholds.py` 同時宣告

```python
YIELD_HIGH: float = 7.0          YIELD_HIGH_DEC: float = YIELD_HIGH / 100   # 0.07
YIELD_MID:  float = 5.0          YIELD_MID_DEC:  float = YIELD_MID  / 100   # 0.05
YIELD_LOW:  float = 3.0          YIELD_LOW_DEC:  float = YIELD_LOW  / 100   # 0.03
```

**查證結果（單組結論）**：
- ✅ `_DEC` 版是 **由百分比版推導**（`YIELD_HIGH / 100`），不是第二份獨立寫死的數字 → **不會漂移**。這比 `CLAUDE.md §4.1` 條目寫的情況好：那條記的是「混用 = 100× 誤差」的**風險**，不是「現在有兩份不同步的值」。
- ✅ 用途明確分流：**百分比版用於比較**（`avg_div >= YIELD_HIGH`）、**`_DEC` 版只當分母反推目標價**（`avg_div / YIELD_HIGH_DEC`）。
- ✅ 本次抽查的 caller 全部用對邊：`scoring_helpers`（比較，用 `%`）、`tab_stock` / `section_batch_fetcher` / `section_357_valuation`（反推，用 `_DEC`）、`v5_modules`（顯示，用 `%`）。
- ⚠️ **殘留風險是命名，不是值**：兩個常數名只差 `_DEC` 四個字元，且**函式簽章不編碼單位**。§4.1 的命名規範（`rate_pct` / `rate_ratio`）**沒有套用在這裡**。
- ⚠️ 順帶記錄一個**文案 vs 燈色的不一致**（`classify_yield_zone` docstring）：`3% < cur ≤ 5%` → `🟡 適度減碼`，`5% < cur < 7%` → `⚪ 中性持有`。**殖利率較低的那一段拿到 🟡、較高的那一段拿到 ⚪**，燈色嚴重度順序與數值順序相反。未查證是否為刻意設計。

---

## 2. 台股／ETF 站 — 其餘指標

### 2.1 健康評分（總經）

| 項 | 內容 |
|---|---|
| **公式** | `health = Σ(vᵢ·wᵢ) / Σwᵢ + fnet_bonus`，其中 `i ∈ {有值的分項}`<br>分項：`jqavg`（旌旗指數＝上漲佔比的 5 日均＝**廣度**）權重 `HEALTH_WEIGHT_JQ = 0.6`；`score_pct` 權重 `HEALTH_WEIGHT_SCORE = 0.4`<br>`score_pct = min(score / max_score × 100, 100)`，`max_score = float(mkt_info.get('max_score') or 4.0)`<br>`fnet_bonus = HEALTH_FNET_BONUS if (fnet is not None and fnet > 0) else 0`（**v19.102 校準後 = 0，dead term**） |
| **資料來源** | `jqavg` ← `src/services/jingqi_calc.py`；`score`/`max_score` ← `market_strategy.market_regime()`；`fnet` ← 三大法人 |
| **計算頻率** | Streamlit rerun 內即算；headless cron `scripts/update_macro_forward_test.py` 每交易日一次 |
| **幣別** | N/A（無量綱分數 0-100） |
| **fallback** | 兩條腿**權重重新歸一化**（v19.177 P1-B），不用中性值頂替；缺項列進 `missing_sources`、回傳 `health_partial=True` |
| **虧損處理** | N/A（非損益指標） |
| **缺漏判定邊界** | `_w_sum <= 0`（兩條腿都缺）→ `health = None` → arbiter 回 `UNLOADED_VERDICT`（⬜ 總經未評估）。檔內明文：**不是 0 分**（0 會被判成最強利空），**也不是 🟡**（🟡 是一個市場判斷） |
| **對帳** | `health_reconcile.reconcile_health_score`（Method A ↔ Method B），**僅在輸入齊全時才跑**，走 stderr log，不改 UI |

**N/A 觸發條件表 — 總經健康評分**

| 條件 | 結果 |
|---|---|
| `jqavg is None` 且 `score_pct is None` | `health = None` → ⬜ 總經未評估 |
| 僅 `jqavg` 缺 | health 由 score_pct 單獨歸一化（除以 0.4）；`health_partial=True` |
| 僅 `score` 缺 | health 由 jqavg 單獨歸一化（除以 0.6）；`health_partial=True` |
| 三來源（mkt/jingqi/cl）全空 | `calc_traffic_light` 回 `None`；forward-test cron 印「不寫列(§1 不落空殼)」 |

> ⚠️ **名不副實已被揭露（`shared/macro_buckets.py` 自陳）**：「總經健康評分」建構上只有 **2 個輸入**，其中 `jqavg` 是**廣度**。五桶註冊表的 16 個 DangerSpec 中，真正餵進這條公式的**只有 jingqi 一項**；`ndc_signal / m1b_m2_gap / ism_pmi / us_core_cpi / tw_export / bias_240 / us10y / dxy / vix / adl / fut_net / margin / foreign_net / news_systemic` **全部不含**。
> ⇒ 「五桶多盞紅、但本分數仍不低」不是算錯，是評估範疇不同。

> ⚠️ **`shared/position_throttle.py` 自陳的更嚴重結構問題**：`jqavg`（σ=3.32）在數學上是個**準常數 ≈ +29.8**，對 health 變異只貢獻 2.8%，`corr(health, score_pct) = 0.987`。
> ⇒ **`health ≡ 29.8 + 0.4 × score_pct`，值域被壓成 [21.6, 78.1]。**
> ⇒ 名義上的「0.6 廣度 + 0.4 評分」在實務上**幾乎純粹是 score_pct 的仿射變換**。

---

### 2.2 🚨 `max_score` 恆為 None — **已實測證實，且已污染 production 資料**

> 客戶交辦的第 2 個地雷。**查證結果：屬實，而且比回報的更嚴重。**

**證據鏈（四段，全部實測）**

**① AST 掃描** `calc_traffic_light` 的 return dict：
```
line 522: 23 keys
['action','color','conf','conf_groups','defense','effective_regime','fk','fnet',
 'frozen_cols','fut_net','fut_net_frozen','health','health_partial','icon','jqavg',
 'label','leek','light','missing_sources','regime','regime_source','score','sub']
HAS max_score? False
```

**② `build_signal_row` 確實在讀它**（`src/compute/macro/macro_forward_test.py:113`）：
```python
'max_score': _opt_float(tl.get('max_score')),
```
用的是 `.get()` 不是 `[...]`，所以**不會 KeyError，只會靜默回 None**。

**③ 執行探針**（餵入 `mkt_info = {'score': 3, 'max_score': 6, ...}`）：
```
'max_score' in tl  -> False
tl.get('max_score') -> None
row['score']     -> 3.0
row['max_score'] -> None      ← 輸入明明給了 6
```
⇒ `max_score` 在 `calc_traffic_light` **內部被消費了**（`_max_score = float(_mkt.get('max_score') or 4.0)` 用來算 `score_pct`），但**沒有被再輸出**。

**④ production parquet 實測**（`data_cache/macro_forward_test/signals.parquet`）：
```
rows: 12
max_score notna count: 0 / 12
max_score unique: [None]
score sample: [4.0, 4.0, 3.0, 4.0, 5.0]
```

**為什麼這件事比「一個欄位是空的」嚴重**

- `shared/macro_forward_test_schema.py:53` 對這個欄位的註解逐字寫：
  `"max_score",  # float 當日實際分母(會隨選填腿在/不在浮動 —— 必存)`
  ⇒ **schema 自己宣告「必存」，實際 0/12 存到。**
- `max_score` **會浮動**（基本 4，`ad_ratio`/`m1b_m2` 腿有傳才升 5/6；`M1B_M2_LEG_ENABLED=False` 後 `_max` 從 6 降到 5）。
- 實測資料裡 **`score = 5.0`**（2026-09-07）。一個 `score=5` 配上未知分母，**可能是 5/5（滿分）也可能是 5/6**，兩者的 `score_pct` 是 100% vs 83.3%，**語意完全不同**。
- ⇒ **前進式驗證的 parquet 無法重建當日的 health**。這正是本專案唯一零 lookahead 的驗證資料集（`CLAUDE.md §2.3`），它的分母欄位是空的。
- `scripts/update_macro_forward_test.py:167` 還把它印進 log：`score={row['score']}/{row['max_score']}` → **每天的 cron log 都印 `score=4.0/None`**。

**修法（一行，但屬行為變更，須走 §8 流程）**：在 `calc_traffic_light` 的 return dict 補 `'max_score': _max_score`。
⚠️ **已寫入的 12 列無法回填**（那 12 天的 `mkt_info['max_score']` 沒有留存），屬**永久資料損失**。

---

### 2.3 財報體檢分數與等第

**[main-pre] 與 [673] 的差異是本節的重點。**
⚠️ **[673] 欄自 2026-09-14 17:27 起＝ production**（見 §0.1）；**[main-pre] 欄描述的是該時點之前**的行為。

| 項 | [main-pre]（已被取代） | [673]（**現為 production**） |
|---|---|---|
| **缺值讀取** | `fd.get(key, 0) or 0`（實測本檔 **6 處** `fin_data.get(..., 0) or 0` 命中該正規式；PR body 自陳全檔同型模式 **49 處**，改 20、不改 29） | `_read(fd, key) -> (值, 三態)`，三態常數 `FIELD_ABSENT` / `FIELD_ZERO` / `FIELD_VALUE` |
| **損益表整張缺** | 營收→0 → 三率→`0.0%` → `Core_Business_Profitable` 落 `else "Fail"` → **「本業虧損」** → `fail_items` ≥2 → **C 級**，畫面**無任何缺資料標示** | `_income_gap` 偵測 → 三率標 `NA_NO_INCOME_STATEMENT = "N/A (損益表缺漏)"` → **整體不評等** |
| **資產負債表整張缺** | `cl == 0` → `"Pass (無短期債務)"`、`ppe == 0` → `"Pass (輕資產)"` → **一張沒回來的表換到兩張及格證** → 推到 **A+「印鈔機」** | `_stmt_gaps` gate 涵蓋資產負債表 → **不評等** |
| **一項都算不出來** | 掉到最後 `else` → **「🔵 財務穩定，中規中矩」+ score_pct=50** | `if not valid:` → `grade="N/A"`、`headline="⬜ 財報資料不足，本輪不評等"`、`score_pct=None` |
| **`score_pct` 缺值預設** | `round(total_pts/max_pts*100) if max_pts > 0 else 50` ← **50 分憑空生成** | 同式仍在，但被上方兩道 gate 擋住（`not valid` 先回 N/A） |
| **未評估項揭露** | 無 | 任何等級都附「⚠️ 本輪有 N 項未評估（…）—— 缺資料不計分，等級只反映算得出來的那幾項」 |

**等第算式（兩版共用，[673] 未改）**

```
checks  = 11 項 (現金水位 / OCF / 本業獲利 / 100-100-10 / 負債比率 / 以長支長 /
                 流動比率 / 盈餘含金量 / 雙高危機 / …)
valid   = [(n,s) for n,s in checks if s != "N/A"]
_pts(s) = {Pass:2, Acceptable:1, Good:2, Strong:2, Exception_Pass:1,
           Warning:-1, Fail:-2, Fail_Initial:-1, "Thin Profit":-1}.get(s, 0)
total_pts = Σ _pts(s) for valid
max_pts   = len(valid) × 2
score_pct = round(total_pts / max_pts × 100)          if max_pts > 0 else 50
pass_items = [n for n,s in valid if _pts(s) >= 2]
fail_items = [n for n,s in valid if _pts(s) <  0]
```

等第決策樹（**順序即優先序**）：
```
is_dying or len(fail_items) >= 4   → F   🔴 高危企業
len(fail_items) >= 2               → C   🟡 有明顯改善空間
len(fail_items) == 1               → B+  🟡 大致穩健
is_cashcow ("A+" in Business_DNA)  → A+  🟢 印鈔機
score_pct >= 70                    → A   🟢 優質企業
else                               → B   🔵 財務穩定，中規中矩
```

> 🚨 **這棵樹的結構性弱點（[673] 已識別並就地註明，但**未改樹本身**）**：
> 「**少評幾項不會讓等級變差，只會讓它變好**」——因為分支條件全部掛在 `len(fail_items)`，而 N/A 不進 `fail_items`。
> ⇒ [673] 的解法是**在樹之前加 gate**（整張表缺 → 不評等），**不是**修樹。
> ⇒ **單格缺漏（不足以觸發整張表 gate）仍會讓等級偏好。** 這是 [673] **仍未解**的殘留風險（本附錄記錄，屬單組結論）。

**N/A 觸發條件表 — 財報體檢**

| 條件 | [main-pre]（已被取代） | [673]（**現為 production**） |
|---|---|---|
| 損益表整張缺 | **C 級「本業虧損」**（假結論） | `grade="N/A"`、`score_pct=None`、⬜「只拿到一半的財報，本輪不評等」 |
| 資產負債表整張缺 | **A+「印鈔機」**（假結論） | 同上 |
| 兩張都缺 | 依欄位落點，可能 C 也可能 A+ | 同上，`comment` 串接兩段原因 |
| 一項指標都算不出來 | **B「財務穩定」+ score_pct=50** | `grade="N/A"`、⬜「財報資料不足，本輪不評等」 |
| `fin_data` 含 `{"error": ...}` | `_FAIL_SAFE` 攔截（兩版同） | 同 |
| 單格缺漏（表還在） | 該項落 `_pts(...)=0`，不進 pass 也不進 fail | 同 + 「本輪有 N 項未評估」揭露 |
| 下游 `grade="N/A"` 的處理 | — | `compute/scoring/unified_verdict.fundamental_grade_to_state()` 落「未知 → None」，走 coverage 缺值路徑 |

> ⚠️ **[673] 自己登記但未修的同型 bug（逐字轉錄自 PR body）**：
> `src/ui/tabs/tab_stock.py`（🔬 個股分頁）有同型的布林渲染 bug：`== 'Yes'` / `== 'Good'`，缺值落 else → 紅底 +「本業虧損❌」。PR 讓它的 `Value` 變成 `N/A (損益表缺漏)`，**但標籤與紅底仍在說謊**。
> 另：頂層生死燈號（現金水位／OCF）缺資料仍畫 🔴；`radar_scores` 缺資料給 20/30 分。

---

### 2.4 五桶燈號

| 項 | 內容 |
|---|---|
| **公式** | `classify_danger(value, spec)`，三種方向：<br>`high_bad`: `v ≥ red → 紅`；`v ≥ yellow → 黃`；else 綠<br>`low_bad`: `v ≤ red → 紅`；`v ≤ yellow → 黃`；else 綠<br>`band`: `(red_lo≠None and v ≤ red_lo) or v ≥ red → 紅`；黃同理 |
| **桶** | long / mid / short / chips / news（5 桶，16 個 `DangerSpec`） |
| **門檻 SSOT** | `shared/macro_buckets.py`（L0）。**鏡像** `macro_core.MACRO_THRESHOLDS`（L1，L0 不可 import），由 `tests/test_macro_buckets.py::test_mirror_matches_macro_core` 斷言相等 |
| **門檻來源標註** | 每條 `DangerSpec.source` 標 `"SSOT:<位置>"` 或 `"DESIGN"`（後者為 UI 判讀門檻，無單一官方源，已具名 + 文件化） |
| **計算頻率** | 每次 rerun |
| **幣別** | 依 spec.unit：`""` / `"%"` / `"億"` / `"口"` / `"分"` / `"則"` |
| **fallback** | 無多源；值取不到即 gray |
| **缺漏判定邊界** | `value is None` 或 `float()` 失敗 → `"gray"`（⬜） |

**N/A 觸發條件表 — 五桶**

| 條件 | 結果 |
|---|---|
| `value is None` | `"gray"` ⬜ — 檔內明文「**不偽綠**」 |
| `float(value)` 拋 TypeError/ValueError | `"gray"` ⬜ |
| gray 參與 worst 計算？ | **否** — `LEVEL_RANK` 只有 green/yellow/red |

**鏡像的具體值（量測日 2026-08-27，`shared/macro_buckets.py`）**
`VIX` 22/30、`CPI` 3.5/4.0、`PMI` <50/<46、`US10Y` 4.5/5.0、`DXY` 105/110、`health` 35（紅）/50（黃）、融資 `2500億`（黃）/`3400億`（紅）、外資期貨 `-10000`/`-20000` 口、市場廣度中性 `50.0%`、系統性新聞 ≥1 則黃 / ≥2 則紅。

---

### 2.5 持股水位油門

| 項 | 內容 |
|---|---|
| **公式** | `compute_position_throttle(health, regime, ...)`：總經 health（0-100）→ 建議持股區間 %，並保留 **regime 否決**（空頭防禦強制壓低上界） |
| **健康分切點** | `THROTTLE_HEALTH_A = 70` / `THROTTLE_HEALTH_B = 50` / `THROTTLE_HEALTH_DEF = 35` |
| **持股 % 帶** | 80 / 50 / 20（對齊 `config.py` 的 `EXPOSURE_BULL/NEUTRAL/BEAR`） |
| **接線層** | `src/services/allocation_service.get_allocation()` — 全站**唯一**入口；UI **不得**再自行 `compute_position_throttle` / 讀 `mkt_info['exposure_pct']` / 硬編碼百分比 |
| **仲裁** | `姿態油門 × macro_state 曝險上限 × VIX／三環天花板` 三條輸入取嚴 |
| **快取** | 同一 rerun 內以 `(cl_ts, health, regime, exposure_limit_pct, vix, ring1)` 為 key |

> ⚠️ **量綱陷阱（檔內明文）**：`config.py` 存的是**比例** `0.80/0.50/0.20`，本模組用**百分比** `80/50/20`，**差 100×**。要引用請自行 ×100，**別直接 import 混用**。

> ⚠️ **三個切點只有一個是真對齊（檔內自陳）**：
> - ✅ `DEF = 35` 真對齊 `HEALTH_DEFENSE_THRESHOLD`（同尺度）
> - ⛔ `A = 70` **禁止**對齊 `HEALTH_GRADE_A_MIN(=80)` —— 後者是**個股六因子**尺度。照 80 切會讓「積極」帶在 2007-2026 的 4,769 個交易日裡**一次都不觸發**。現值 70 來自總經 health 自身分布的 **P90**（n=4,789，腿停用後 P90=70.5）
> - ⚠️ `B = 50` 與 `HEALTH_GRADE_B_MIN(=50)` 是**數值巧合，不是有效背書**；屬**未校準手訂值**

> 📌 該檔另誠實揭露：拿掉 `m1b_m2` 腿後 **防禦帶確實變寬**（12.45% → 13.61%，每年 31.4 → 34.3 天）；燈號佔比幾乎不動（🔴 27.04% → 27.04%）。刻意**不**同步調 DEF 抵銷，理由是該門檻的 walk-forward 校準跑出 4 折 4 種答案、第 3 折 OOS precision 0%、平均衰退 −111.5% ⇒ **無證據支持調整**。

**N/A 觸發條件表 — 油門**：health = None 時 arbiter 回 `UNLOADED_VERDICT`（⬜），`section_state.py:543` 明文「不渲染建議持股油門」。

---

### 2.6 最大回撤（MDD）

| 站 | 位置 | 公式 |
|---|---|---|
| 台股/ETF | `etf_calc.calc_mdd` | `min((close − cummax(close)) / cummax(close) × 100)` |
| 台股風控 | `risk_control.update_drawdown` | 對照 `MAX_PORTFOLIO_DRAWDOWN = 0.15`（**比例**，非 %） |
| 校準 | `health_calibration` | 未來 `horizon`(=20) 交易日最大回撤 ≥ θ_dd → 風險姿態真值 y=1；`mdd = dd[1:].max()`（**不含 t 自身 dd=0**，防 lookahead） |
| 基金 | `portfolio_performance` | `max_drawdown_pct = round(_dd × 100.0, 2)` |

| 項 | 內容 |
|---|---|
| **資料來源** | 日線 Close（ETF：yfinance／L1 fetcher；基金：NAV 序列） |
| **計算頻率** | 隨頁面／隨 metrics 計算 |
| **幣別** | N/A（%） |
| **fallback** | 無 |
| **虧損處理** | MDD 本身恆 ≤ 0，無「虧損 → N/A」語意 |

**N/A 觸發條件表 — MDD**

| 條件 | 結果 |
|---|---|
| `calc_mdd` 任何例外 | `return None` + stderr log ✅ |
| `df['Close']` 缺欄 | 落入 except → None |
| 基金 `max_drawdown` 樣本門檻 | ⚠️ `services/switch_strategy.py:76` 自陳「`calc_metrics` 把 max_drawdown 的樣本門檻…**完全無法區分**」——該處是說「缺」與「真的是 0」分不開。**細節本次未追**（見 §6 U-6） |

---

### 2.7 RSI

| 項 | 內容 |
|---|---|
| **公式（kernel SSOT）** | `scoring_engine.compute_rsi`：<br>`delta = close.diff()`<br>`gain = clip(delta, lower=0).ewm(alpha=1/period, adjust=False).mean()`<br>`loss = clip(−delta, upper=0 反向).ewm(alpha=1/period, adjust=False).mean()`<br>`RSI = 100 − 100 / (1 + gain / (loss + 1e-10))` |
| **平滑法** | **Wilder RMA**（α = 1/period），v19.89 自 SMA 改；理由：台股券商平台一律用 Wilder，改後 70/30 門檻才可與券商對照 |
| **period** | 預設 14 |
| **adapter** | `tech_indicators.calc_rsi` — 取 last + `round(1)` + guard |
| **門檻 SSOT** | `RSI_OVERBOUGHT=70` / `RSI_OVERSOLD=30`（`config.py:52-53`）；`RSI_STRONG_LOW` / `RSI_NEUTRAL_WEAK_LOW`（`signal_thresholds`） |
| **合理範圍** | [0, 100]（§3.2） |
| **幣別 / 虧損** | N/A |

**N/A 觸發條件表 — RSI**

| 條件 | 結果 |
|---|---|
| `df is None` 或 `len(df) < period + 1` | `None` ✅ |
| 最新值 `isna` | `None` ✅ |
| 任何例外 | `None` + stderr log ✅ |
| `loss` 恆為 0（全漲） | `+1e-10` epsilon → RSI ≈ 100（**不 raise**，刻意映射） |

---

### 2.8 ATR

| 項 | 內容 |
|---|---|
| **公式（kernel SSOT）** | `scoring_engine.compute_atr`：<br>`TR_t = max(High_t − Low_t, \|High_t − Close_{t−1}\|, \|Low_t − Close_{t−1}\|)`<br>`wilder=True`（預設）→ `tr.ewm(alpha=1/period, adjust=False).mean()`<br>`wilder=False` → `tr.rolling(period).mean()` |
| **首根處理** | `prev_close = NaN` → `max` skipna → `TR = High − Low` |
| **缺 high/low 欄** | **退回 close**（TR 退化為 `\|ΔClose\|`），**不炸** ⚠️ 靜默降級 |
| **period** | 預設 14 |
| **合理範圍** | `> 0`（§3.2） |
| **消費** | `calc_atr_stop`：`Stop = Entry − multiplier × ATR14`；`atr_stop_price`（risk_control） |

**N/A 觸發條件表 — ATR / ATR 停損**

| 條件 | 結果 |
|---|---|
| `df is None` 或 `len(df) < 14` | **刻意降級**：`{'stop_loss': entry×(1−ATR_STOP_FIXED_PCT/100), 'atr': None, 'method':'fixed_8pct', 'error': None}` — `error=None` 表**非異常路徑** |
| ATR 計算拋例外 | 同結構，但 `error = f"{type}: {msg}"` + stderr log（v18.241 D6 hotfix：原為 bare except + 靜默 8% fallback） |
| 缺 `high`/`low` 欄 | ⚠️ **不回 None**，TR 退化為 `\|ΔClose\|`，**呼叫端無從得知** |

> ⚠️ **記錄一個未修的降級破口（單組結論）**：缺 high/low 時 `compute_atr` 靜默退化，**回傳值型別與正常路徑相同**，沒有旗標。對照 `§1`「任何填補必須在輸出帶旗標」，這一處**不帶旗標**。

---

### 2.9 KD（隨機指標）

| 項 | 內容 |
|---|---|
| **公式** | `low_n = low.rolling(period).min()`；`high_n = high.rolling(period).max()`<br>`RSV = (close − low_n) / (high_n − low_n).replace(0, 1) × 100`<br>`K = RSV.ewm(com=2, adjust=False).mean()`（≡ α = 1/3）<br>`D = K.ewm(com=2, adjust=False).mean()` |
| **period** | 預設 9 |
| **合理範圍** | [0, 100] |
| **幣別 / 虧損** | N/A |

> ⚠️ **`.replace(0, 1)` 是一個未標旗標的填補（本附錄新記錄，單組結論）**：
> 當 `high_n == low_n`（period 內完全無波動，例如連續跌停鎖死）時，分母 0 被換成 **1**。
> ⇒ `RSV = (close − low_n) / 1 × 100`。因為此時 `close == low_n == high_n`，`RSV = 0` → K/D 向 0 收斂 → 被讀成「**極度超賣**」。
> ⇒ 實際情況是「**這段期間沒有價格資訊**」。對照 §1，這是「讓程式不報錯」而非「解決問題」。
> 對照組：同檔 `calc_bollinger` 對相同問題用的是 `ma.replace(0, float('nan'))` → 後續 `isna` → `return None`（正確做法），**兩個函式在同一個檔案裡用了兩種標準**。

**N/A 觸發條件表 — KD**

| 條件 | 結果 |
|---|---|
| `df is None` 或 `len(df) < period` | `(None, None)` ✅ |
| `k_val` 或 `d_val` 為 NaN | `(None, None)` ✅ |
| 任何例外 | `(None, None)` + stderr log ✅ |
| `high_n == low_n` | ⚠️ **不回 None** — 分母換 1，K/D → 0（假超賣） |

---

### 2.10 MA / 乖離

| 項 | 內容 |
|---|---|
| **公式（SSOT）** | `calc_bias_pct(price, ma) = (price − ma) / ma × 100`（R-CALC-3 v18.412 收斂） |
| **MA 定義** | `compute_twii_bias`：`_maN = float(_cs.tail(min(N, _n)).mean())`，N ∈ {20, 60, 120, 240} |
| **年線常數** | `ANNUAL_MA = 240`（交易日，`config.py:14`） |
| **資料來源** | `^TWII` 日線；資料不足 240 天時 fallback `fetch_twii_2y_for_ma240()` |

> 🚨 **兩個問題（第一個已被 repo 自己揭露，第二個是本附錄新記錄）**
>
> **(a) `bias_240` 在資料不足時其實不是年線乖離（repo 已揭露，I2 2026-08-10）**
> `_ma240 = mean(tail(min(240, n)))` —— 當 `n = 90` 時，`ma240` 實際是 **MA90**，`bias_240` 是「距 MA90 的乖離」。
> 回傳帶 `is_estimated = (n < 240)` 與 `data_days`，文案 SSOT 在 `macro_helpers` 的 I2 區塊。
> ⚠️ 但該檔明文：「I2 **只做揭露**：燈號／門檻／桶判定**仍直接套用這個估算值**，尚未針對估算另設規則」。
> ⚠️ 且 `macro_helpers.py:1464` 自陳：全 repo 讀 `bias_240` 的 **10 個消費點裡只有少數**帶揭露，其餘「拿到的都是裸數字 —— 一個『距 90 日均線的乖離』被當成年線乖離講給人與 LLM 聽」。
>
> **(b) `or 0` 把缺值壓成「價格恰在均線上」（本附錄新記錄）**
> 📌 **收工前補查後嚴重度已下修為「死碼」，不是活 bug —— 請直接看 §6 U-11 的修正結論，不要只讀下面這段。**
> ```python
> 'bias_20':  calc_bias_pct(_lp, _ma20,  decimals=1) or 0,
> 'bias_60':  calc_bias_pct(_lp, _ma60,  decimals=1) or 0,
> 'bias_240': calc_bias_pct(_lp, _ma240, decimals=1) or 0,
> ```
> `calc_bias_pct` 回 `None`（ma 無效）時 → `0`；而 **乖離 0.0% 是一個合法觀測**（價格恰在均線）。
> ⇒ 與 PR #673 修的 `fd.get(k,0) or 0` **是同一族的 §1 問題**，但在**不同的檔案**（`src/data/macro/macro_snapshot.py`，L1），**[673] 未涵蓋**。
> ⇒ `bias_240` 是五桶 `DangerSpec` 之一（`long` 桶），`0` 會被 `classify_danger` 判成**綠燈**，而非 gray。

**N/A 觸發條件表 — 乖離**

| 條件 | 結果 |
|---|---|
| `twii` 全空 / fetch 全敗 | `compute_twii_bias` 回 `None` ✅ |
| 找不到 Close 欄 | `None` + stderr log ✅ |
| `_cs` dropna 後長度 0 | `None` ✅ |
| `n < 240` | ⚠️ **不是 N/A** — 回估算值 + `is_estimated=True`；判燈**照用** |
| `calc_bias_pct` 回 None | ⚠️ 名義上 `or 0` → 0.0 → 判綠燈；**但實測推導此 caller 下 `ma > 0` 恆成立 ⇒ 此分支為死碼**（§6 U-11） |

---

### 2.11 法人集中度

> ⚠️ 客戶詞「法人集中度」在本 repo 對應到**兩個不同的東西**，本節兩個都記。

**(A) 投組產業集中度** — `src/compute/risk/concentration.py`

```
設已分類股票共 M 檔，分屬 K 個產業，產業 i 有 n_i 檔：
  w_i  = n_i / M              , Σ w_i = 1
  Top1 = max_i w_i
  Top3 = Σ_{i ∈ top-3} w_i
  HHI  = Σ w_i²               , 1/K ≤ HHI ≤ 1
  Neff = 1 / HHI              , 1 ≤ Neff ≤ K
```

| 項 | 內容 |
|---|---|
| **資料來源** | 產業別由 L3 `stock_grp_service.get_industry_category` 先查好傳入（L2 不自己抓） |
| **計算頻率** | 隨頁面 |
| **幣別** | N/A |
| **fallback** | 無 |
| **門檻／燈號** | ❌ **刻意不提供**（user 2026-08-14 裁示）。理由：DOJ 的 HHI 1500/2500 是衡量**產業市場結構**用的，套到投資組合沒有依據，憑空定一個就是新的 magic number（§3.3） |

> ⚠️ **兩個必須顯示給使用者的限制（檔內明文要求 UI 揭露）**：
> **限制 1 — 等權假設**：`stock_watchlist` schema 只有 `['name','ticker','updated_at']`，**系統不知道實際部位大小**，一律以 `w = 1/N` 計算。回傳帶 `basis='equal_weight'`，**UI 必須顯示這個假設**。
> **限制 2 — 未分類不納入分母**：查不到產業別的檔數不歸入任何桶。`coverage_pct` 一併回傳。檔內說明為何不併桶：併成一桶會**低估**集中度、併入最大桶是**直接捏造** ⇒ 選「排除 + 誠實揭露覆蓋率」。

**(B) 籌碼集中度（近 20 日主力買賣超）** — 消費端 `src/ui/views/page_inspect.py`

| 項 | 內容 |
|---|---|
| **輸入** | 「外資 ＋ 投信淨買賣超」與「成交量」兩組數字 |
| **缺值處理** | 檔內明文：「本站**不拿 0% 集中度頂替**（0% 是『買賣超剛好抵銷』這個結論，不是缺值）」✅ |
| **與異常值徽章的關係** | 檔內明文：「徽章與集中度**分別判、分別報**，不互相背書」——兩支吃的欄位不同，會出現「一支判得出、一支判不出」 |

**相關：三大法人單日買賣超 outlier 偵測**（`src/compute/risk/inst_sanity.py`）
`is_inst_net_outlier`：單日買賣超 > 該股 30D 均量 × `INST_NET_OUTLIER_VOLUME_RATIO(=5.0)` → 徽章。已 wire 進 `section_chips_20d`。

---

### 2.12 ETF 月月配健檢 A/B/C/D（附帶記錄 — 缺值原因分類做得最好的一組）

| 燈 | 判定 | 缺值處理 |
|---|---|---|
| **A 不吃本金** | `total_return_1y < annual_yield` → 🔴 | **兩個輸入的缺法分開標**：缺總報酬 → `MISS_NOT_ENOUGH`（日線歷史不足一年＝新上市，**重跑無用**）；缺配息率 → `MISS_NO_INPUT`（抓取失敗，**重跑有機會**）；兩者皆缺 → `most_fundamental_miss` 取較根本者 |
| **B 夏普** | `sharpe < SHARPE_NEG_THRESHOLD(=0)` → 🔴 | `sharpe is None` → ⚪ + `MISS_NOT_ENOUGH`。檔內明文更正：三條 None 路徑（週數不足／報酬筆數不足／波動≈0）**都是「有資料但算不出來」**，沒有一條是抓取失敗 |
| **C 趨勢防守** | 週收 < 13 週季線 **且** 季線下彎 → 🟡 | `ma13 is None or slope is None` → ⚪ + `MISS_NOT_ENOUGH`，訊息中的 13 走 SSOT `T.MA_QUARTER_WEEKS` |
| **D 折溢價** | `calc_premium_discount` SSOT（官方 iNAV 同日 inner-join + 3 守門員 G1/G2/G3 + sanity 上限） | `stale_nav` / `premium_pct=None` → **不填** `m["premium_pct"]` → 標「無折溢價資料」**不假判** |

> 📌 這組是本 repo 缺值語義化做得最完整的一處：`Flag` dataclass 帶 `miss_reason` 欄位，理由是「解析 msg 字串太脆弱 —— 改一個字就壞」。
> 📌 D 燈的歷史教訓值得記：末端 fallback 到 yfinance `navPrice` 會回「最後已公告淨值」被硬戳今日 → **假溢價觸發假 🟡**（v18.442 修的 0050 假 +5.07%）。

---

## 3. 基金站 — 指標

### 3.1 配息覆蓋率 / 吃本金

| 項 | 內容 |
|---|---|
| **公式（canonical SSOT）** | `services/health/dividend.py::classify_eating_principal`<br>`is_eating = total_return_pct < dividend_yield_pct`<br>`coverage_ratio = r / d`（僅 `d > 0`）<br>`gap_pct = d − r`（正數 = 吃本金深度）<br>`real_return_pct = r − d`（= −gap_pct） |
| **資料來源** | `total_return_pct` ← `compute_1y_total_return` 四層 chain（見 §1.2）；`dividend_yield_pct` ← MoneyDJ `wb05` 官方值優先，缺則退本地估算 |
| **計算頻率** | 隨頁面 |
| **幣別** | 兩個輸入皆為 %，無幣別 |
| **fallback** | 三個 wrapper 各自做分級（**核心判定不重複實作**）：<br>`portfolio_service.dividend_safety` → **5 級** + nav_warning<br>`fund_service.calc_health_from_manual` → **4 級**（用 `real_return_pct`）<br>`health.dividend_calc.div_health_light_for_pair` → **3 色燈**（用 `gap_pct` vs `warn_gap`） |
| **4D 評分用的分級** | `_score_coverage`：`cov ≥ 1.5 → 95` / `≥1.2 → 80` / `≥1.0 → 65` / `≥0.5 → 40` / `<0.5 → 15` |

**N/A 觸發條件表 — 配息覆蓋率**

| Case | 條件 | 回傳 |
|---|---|---|
| 1 | 任一 input 為 None / NaN / 非數值 | `is_data_missing=True`，其餘全 `None` / `False` ✅ |
| 2 | `dividend_yield_pct ≤ 0`（無配息基金） | `is_no_dividend=True`、`is_eating=False`、**`coverage_ratio=None`**（除以 0／負數無意義）、`gap_pct` 仍算 |
| 3 | 正常 | 全欄位算出 |
| 4D | `tr1y is None` 或 `adr is None` 或 `adr ≤ 0` | `_score_coverage` 回 `None` → **退出分母，不填 0** ✅ |
| — | `tr1y` 來源是 `SRC_SELF_ANNUALIZED`（短窗外推） | ⚠️ 判定端**應拒判**（⚪）—— `is_extrapolated_1y_source()` 提供偵測；**是否所有 caller 都照做，本次未窮舉**（見 §6 U-7） |

---

### 3.2 同類中位數比較

→ **見 §1.2(c)**。摘要：用的是 **MoneyDJ 同類型「平均」**，不是中位數；錨定 MoneyDJ，不是公會／晨星；更新週期**查不到**。約 3 成基金抓不到（該檔自陳）。

另有小 universe 四分位（`services/peer_rank.py`），母體是「持倉 ∪ 選股池」，與母法所指不同，但樣本量誠實度佳（< 2 檔不排名；2~3 檔不分四分位）。

---

### 3.3 報酬率

| 項 | 內容 |
|---|---|
| **公式（年化，peer_rank）** | `(NAV_末 / NAV_窗起)^(1/實際年) − 1`；實際年 = `(end_ts − s.index[li]).days / 365.25` |
| **PIT（§2.3）** | 窗起 = 序列**自身最後日期**回推，**不用系統今天** ✅ |
| **1Y 含息 chain** | 4 層 precedence（見 §1.2(a)） |
| **資料來源** | MoneyDJ wb01 績效表 → 本地含息計算 → 純 NAV → NAV 外推 |
| **幣別** | **依基金計價幣別**，未統一換算（見下方警告） |
| **合理性帶** | `is_implausible_1y()` — 走 `RET_1Y_PLAUSIBLE_MAX_PCT` / `MIN_PCT` SSOT。**不改值、不丟值**，只把 `SRC_IMPLAUSIBLE_SUFFIX = "　⚠️ 數值異常大，請先核對幣別與除息"` 黏在來源標籤上 ✅ |

> ⚠️ **稽核 E1 的歷史教訓（檔內明文）**：第 4 層原本 **30 天就敢 ×12 外推**，大表因此印出 **+201% 的台幣基金**。現在跨度不足半年直接回 `(None, SRC_TOO_SHORT)`。
> ⚠️ **ACTI71 案例**：短窗外推把「近一年淨值其實上漲」外推成 **−38.18%** → 假 🔴 嚴重吃本金。

**N/A 觸發條件表 — 報酬率**

| 條件 | 回傳 |
|---|---|
| 跨度 < `RET_1Y_EXTRAPOLATE_MIN_DAYS` | `(None, SRC_TOO_SHORT)` → 顯示「—（僅 N 天資料，不足以推算一年）」✅ |
| `peer_rank`：`len(s) < PEER_MIN_OBS(=50)` | `None` ✅ |
| `peer_rank`：實際年 < `window × PEER_MIN_SPAN_RATIO(=0.6)` | `None` ✅ |
| `start_p ≤ 0` 或 `end_p ≤ 0` 或 `years ≤ 0` | `None` ✅ |
| 某層來源給出不可轉數字的值 | 先 stderr log「該源給了垃圾」再 raise → 降級下一層 ✅（原為靜默降級） |
| 值落在合理帶外 | ⚠️ **不丟值** — 附警語後綴，讓它自己講話 |

---

### 3.4 波動度（σ）

| 項 | 內容 |
|---|---|
| **公式** | `services/fund_service.py:423`：`std_dict[lb] = round(base.std() × √TRADING_DAYS_PER_YEAR × 100, 2)` |
| **報酬定義** | 混用 —— `:423` 用 `base`（簡單報酬），`:453` 用 `log_ret`；⚠️ **同檔兩種口徑，本次未釐清各自的消費端**（見 §6 U-8） |
| **ddof** | pandas `.std()` 預設 **ddof=1** |
| **年化** | ×√252（交易日，非 365 日曆日） |
| **4D 評分** | `_score_volatility`：`σ < 10 → 90` / `< 15 → 75` / `< 20 → 55` / `< 30 → 35` / `≥ 30 → 15` |

> ✅ **v19.422 修的一個 §1 破口（值得記）**：`σ ≤ 0` 視為**無效／偽造**（真實年化 σ 恆 > 0）。稽核 Bug1 發現**無歷史基金 σ fallback = 0 → 被評「最低風險 90 分」**。現在回 `None` 不計分。

**N/A 觸發條件表 — σ**

| 條件 | 結果 |
|---|---|
| `sigma_pct is None` | `_score_volatility` 回 `None` → 退出分母 ✅ |
| `sigma_pct ≤ 0` | 回 `None`（v19.422）✅ |
| `len(log_ret) < 20` | `:453` 該支路回 `0` ⚠️ **不是 None** — 本次未追其消費端 |

---

### 3.5 基金評分體系（4D／實為 5D）

| 項 | 內容 |
|---|---|
| **函式** | `services/health/grade.py::compute_4d_health` |
| **維度數** | ⚠️ **函式名叫 4D，實際是 5 維**。檔內明文：「維度數以 `coverage.n_total` 為準，**不要從函式名推**」 |
| **5 維** | ① 💵 配息健康度（Coverage）② 📈 風險調整報酬（Sharpe）③ 📊 走勢健康（60d MA 方向 + ret_1y）④ 🛡️ 低波動性（σ）⑤ 💱 匯率風險（計價幣別對台幣的變異係數） |
| **Grade cutoffs** | `A ≥ 80 / B ≥ 65 / C ≥ 50 / D ≥ 35 / F < 35`，走 `shared.signal_thresholds.GRADE_CUTOFFS_4D` |
| **最低因子數** | `GRADE_4D_MIN_FACTORS` |
| **coverage 輸出** | 幾維有證據 / 幾維適用 / 缺哪幾維 —— 檔內明文：「**加維度必須同時揭露分母**，否則 2/5 的 A 與 5/5 的 A 在表上同形」✅ |

**各維評分表**

| 維 | 分級 |
|---|---|
| ① Coverage | `≥1.5→95` `≥1.2→80` `≥1.0→65` `≥0.5→40` `<0.5→15` |
| ② Sharpe | `≥1.5→95` `≥1.0→80` `≥0.5→60` `≥0→40` `<0→15` |
| ③ 走勢 | `up+正報酬→85` `up only→70` `down+負報酬→25` `down only→45` `無MA但ret>5%→70` `<−5%→25` 否則 `None` |
| ④ σ | `<10→90` `<15→75` `<20→55` `<30→35` `≥30→15` |
| ⑤ 匯率 | 三種 status 必須分得開（§1）：`"n/a"` 台幣計價 → **沒有匯率風險是事實，不是缺資料** |

> 📌 **為什麼是 5D 不是原訂 6D（檔內明文，實測後改案）**：
> - **費用率**：官方揭露率實測 **0** —— 有值的都是「拿經理費當費用率」，境外基金常差一倍以上 ⇒ 不進總分
> - **基金規模**：2 檔就撞出 2 種字串格式（「266.04 億(美元)」vs「58,185.32 百萬歐元」），單位差 100 倍 + 幣別差一層，解析錯**不會報錯只會安靜地錯約 90 倍**（§4.1）⇒ 不做

**其他評分體系（並存）**

| 體系 | 位置 | 公式 |
|---|---|---|
| **換標策略分** | `services/switch_strategy.switch_score` | `1Y含息 35 + Sharpe 30 + MaxDD 20 + vs大盤 15`（滿分 100）。§1：1Y 含息**或** Sharpe 缺 → `None`（核心維度不硬算）。`maxdd` 缺 → 分母 80；`vs_market` 缺 → 分母 85；兩者皆缺 → **分母 65** |
| **同類相對品質分** | `ui/helpers/fund_grp_health/quality.py` | 6 因子百分位（報酬／Sharpe／下檔σ／操盤／配息 coverage／成本），報酬用 MoneyDJ 大母體分位錨定，其餘用小 universe rank |
| **6F 進階指標** | `portfolio_service.calc_fund_factor_score` | **@deprecated for grading** — 保留為 dict 供詳表顯示 Sortino / Calmar / Alpha / 費用率 |

> ⚠️ **`switch_score` 自己記錄的一個假綠燈案例（逐字）**：「1Y含息 8% + Sharpe 1.0 + MaxDD/vs大盤**全缺** → 65/65 → **100 分 → 🟢**」。
> 處置是回 🟡 而非 ⬜，理由：核心兩維（1Y 含息 / Sharpe）**是有真實證據的**，丟成灰燈反而失真。

> ✅ **Sortino 的一個高品質修正值得記**（`fund_service.py:620` 區塊）：原式 `r252[r252 < 0].std()` **不是** downside deviation，CFA Institute (Kidd 2012) 逐字點名此為 "a fairly common mistake"。以 `{-1%,-2%,-3%,-5%}` 為例：正確 TDD = 3.12%、原式 = 1.71% ⇒ **TDD 低估 45%、Sortino 高估 82%**，且**方向恆為高估** ⇒ 下檔風險最大的基金被評得最好，**是排序反向不是精度問題**。現行式：
> `σ_D = sqrt( (1/N) · Σ [min(0, r_t − MAR)]² )`（**分母為全樣本 N**），`MAR = rf`（與 Sharpe 分子同基準）。

---

## 4. 母法修正提案候選

> 格式：變更條款／阻礙原因／替代方案／影響評估
> ⚠️ 依 `§-1.5.F 判定 8`：以下每一條**都附總管推薦方案**，不是丟選擇題。

### 提案 M-1｜Sharpe 的無風險利率（**最高優先**）

| 欄 | 內容 |
|---|---|
| **變更條款** | 「台股無風險利率採台灣央行 1 年期定存利率；海外標的採 DTB3；台幣投海外資產統一以 DTB3 為主、台幣定存為 fallback 並標註」 |
| **阻礙原因** | ① **兩個利率源目前都不在系統裡**：DTB3 全 repo 0 命中，台灣央行定存利率 0 命中（單組結論）。DTB3 可經既有 FRED 鏈取得（`shared/fred_series.py` 已有 FRED 基建），**成本低**；台灣央行 1 年期定存利率**沒有現成 fetcher**，CBC 現有接線只有 `ms1.json`（M1B/M2），須新建一條 T1 來源。<br>② **沒有「標的國別」這個欄位**：三份 Sharpe 實作都吃一個全域 rf，要分流必須在 fetcher/service 層先能回答「這檔是台股還是海外」——ETF 可由 `.TW`/`.TWO` 後綴推斷（`auto_detect_benchmark` 已有此邏輯），**個股與基金沒有對應欄位**。<br>③ **三份實作口徑不同**（日/週、簡單/對數），就算 rf 對了，**同一檔標的跨頁仍會拿到不同 Sharpe**。 |
| **替代方案（推薦）** | **分三階段，先做第 1 階段**：<br>**① 先統一口徑、保留現行 rf** —— 把 S-1／S-2／S-3 收斂成一個 kernel（建議以 S-3 的對數報酬 + √252 為準，因為它已有完整的樣本閘門與 σ=0 守衛），S-2 的週化改為 kernel 的 `periods_per_year=52` 參數。**這一步零新增資料源、可完全內部拍板**。<br>**② 接 DTB3** —— 走既有 FRED 鏈，新增 `DTB3` series；rf 分流先只做 ETF/個股的 `.TW` 後綴判定（已有現成邏輯）。<br>**③ 台灣央行定存利率** —— 須新建 T1 fetcher，且須與客戶確認「1 年期定期存款**牌告**利率」的具體口徑（五大行庫平均？央行公告？機動 vs 固定？）——**這一題只有客戶能用業務語言回答**（§-1.5.A-4）。 |
| **影響評估** | **HIGH。** rf 直接平移 Sharpe 分子，而 `health_b` 的門檻正是 `Sharpe < 0` ⇒ **會改變燈色**。現行 rf ≈ FEDFUNDS（近期約 4~5%）vs 台幣定存（約 1.5%）差約 3 個百分點 ⇒ **台股標的的 Sharpe 會系統性上移**，🔴 燈會變少。`shared/station_specs.py:209` 已自陳這是「**會改變燈色的錯**」。<br>⚠️ 第 ① 階段本身也是行為變更（簡單→對數報酬），須走 §8 流程 + 突變測試。 |

### 提案 M-2｜本益比（TTM）的「近四季 EPS 總和」

| 欄 | 內容 |
|---|---|
| **變更條款** | 「本益比（TTM）＝近四季 EPS 總和；EPS ≤ 0 統一標註 `N/A（虧損）`」 |
| **阻礙原因** | ① **本站不自己算 PE**，是取 TWSE `BWIBBU_d.PEratio` / TPEX `PriceEarningRatio` 的伺服器端權威值。<br>② 要改成自算，須對**全市場**取得近四季 EPS —— 現行只有**個股層級**的 `qtr_df`（FinMind 季報，`@st.cache_data`），**沒有全市場四季 EPS 的批次來源**。選股網每次掃描要打數百次 FinMind ⇒ **quota 直接爆掉**（`§4.6` 已列 FinMind quota 為必測邊界）。<br>③ **改自算會失去 T1 權威性**：TWSE 是 T1 官方，自算是 T2 衍生。與 `§2.1` 的 5-Tier 分級**方向相反**。 |
| **替代方案（推薦）** | **不改算式，改標註。推薦維持 TWSE/TPEX 官方 PE。**<br>理由：官方 PE 是 T1，自算是 T2，§2.1 上層贏；且全市場自算會踩 quota。<br>**要做的是補上母法真正在意的那件事 —— 缺值語義化**：把 `pe_map` 的「不放 key」改成**帶原因的三態**（比照 `dividend_station.Flag.miss_reason` 的既有範式）：<br>　`PE_MISS_LOSS`（來源給 ≤0 或明確標虧損）／`PE_MISS_NO_DATA`（來源空值）／`PE_MISS_SOURCE_DOWN`（端點掛了）。<br>並在**個股頁**（已有 `qtr_df`，quota 可負擔）補一個**自算四季 EPS 的對帳**（§4.3 雙演算法），差異過大時標旗標。 |
| **影響評估** | **LOW-MED。** 缺值語義化是 schema-additive，不改任何既有判定；個股頁對帳是新增觀測性。<br>⚠️ 但要同步修 `scoring_helpers.py:59` 的 `len(es) >= 2 else 0`（見 §2.3 上方）——那一處是真的把缺值記成不及格。 |

### 提案 M-3｜殖利率的「近一年累計已除息總額」

| 欄 | 內容 |
|---|---|
| **變更條款** | 「殖利率＝近一年累計已除息總額 ÷ 最新收盤價」 |
| **阻礙原因** | ① ETF 路徑（Y-1）**已完全符合**，無須改。<br>② **個股 357 路徑（Y-2）刻意用 5 年平均**，這不是 bug 而是「357 存股法則」的設計 —— 它要的是「常態配息能力」而非「去年配了多少」。**改成近一年會讓 357 三檔目標價（便宜/合理/昂貴）整組位移**，且**單一年度的特別股利會把目標價抬到不合理的高度**。<br>③ Y-3（全市場掃描）是 TWSE/TPEX 官方值，同 M-2 的理由不宜自算。 |
| **替代方案（推薦）** | **推薦：母法補一句「分**用途**分口徑」，而不是統一成一個。**<br>　· **估值／存股用途**（357）→ 維持**近 N 年平均**，但**明文寫進母法**並在畫面標「近 5 年平均配息推估」；<br>　· **現況揭露用途**（ETF 健檢 A 燈、殖利率卡）→ 維持**近一年累計**（已符合）。<br>兩者在畫面上**必須用不同欄名**，不得都叫「殖利率」。<br>⚠️ 順帶修 `app_stock_fetchers.py:193` 的 `.fillna(0)`（缺值年度被當 0 元計入平均，**稀釋** avg_div）。 |
| **影響評估** | **MED。** 若照母法字面統一成近一年，357 的三檔目標價全面位移，且對「去年剛好沒配」的標的會直接翻成超貴 🔴。<br>推薦方案（分口徑 + 改欄名）為**純文件 + UI 文案**變更，**零算式變更**，風險最低。<br>⚠️ 改欄名屬 UI 欄位異動 → 依 `§-1.5.D §03-2 ①` **須先出線框草稿送客戶拍板**。 |

### 提案 M-4｜同類中位數的錨定與口徑

| 欄 | 內容 |
|---|---|
| **變更條款** | 「同類中位數錨定公會／晨星標準並標註更新週期」 |
| **阻礙原因** | ① 現行錨定 **MoneyDJ `peer_compare`**，且取的是「**平均**」不是中位數。<br>② **MoneyDJ 只給彙總值，不給成分明細** ⇒ 系統**拿不到同類各檔的原始報酬**，因此**無法自己算中位數**。要算中位數必須自建同類母體。<br>③ **公會（SITCA）與晨星都沒有現成接線**：SITCA 只出現在 `shared/schemas.py` 的 provenance 前綴白名單（未使用）；晨星只用於**補淨值**（`morningstar_secid`），不是同類母體來源。<br>④ 覆蓋率問題：MoneyDJ peer 約 **3 成基金抓不到**（該檔自陳）。 |
| **替代方案（推薦）** | **推薦分兩段，先做第 1 段（低成本、立刻解決最大的誤導）**：<br>**① 先把「平均」正名為「平均」** —— 現行畫面／欄名若寫「同類中位數」是**與實作不符**（本次未逐一檢查 UI 字串，見 §6 U-9）。把欄名與文案統一改成「**MoneyDJ 同類型平均**」，並補上 `peer_compare` 的抓取時間戳（provenance 已有 `fetched_at` 範式可沿用）。**這一步零算式變更。**<br>**② 若客戶堅持要中位數** —— 唯一可行路徑是用 `services/peer_rank.py` 的**自建小 universe**（持倉 ∪ 選股池）算中位數，但必須**誠實標明母體不是公會同類**，且 `PEER_QUARTILE_MIN_N(=4)` 以下不給值。<br>**接公會／晨星同類母體屬新增 T1/T2 資料源，成本高且授權未知 —— 這一題須客戶裁示是否值得投入。** |
| **影響評估** | **① LOW**（文案 + provenance，schema-additive）。<br>**② MED-HIGH**（母體換掉 ⇒ 所有同類比較結論可能翻面，且小 universe 的統計意義遠弱於公會母體，有**用一個更差的數字取代一個標錯名字的數字**的風險）。<br>⇒ **總管推薦：先做 ①，② 等客戶明確表示需要再議。** |

### 提案 M-5｜`max_score` 欄位（**非母法條款，但影響母法可驗證性**）

| 欄 | 內容 |
|---|---|
| **變更條款** | 不是母法條款，但 `shared/macro_forward_test_schema.py` 宣告 `max_score` **必存** |
| **阻礙原因** | `calc_traffic_light` 的 return dict 沒有這個 key（實測 23 keys 無 `max_score`）。**已污染 12/12 列 production 資料，且無法回填**。 |
| **替代方案（推薦）** | **立即修**：`calc_traffic_light` return dict 補 `'max_score': _max_score`（該變數在函式內已存在）。<br>**同時**：在 `build_signal_row` 加一道 `§1` 守衛 —— schema 宣告「必存」的欄位若為 None，**應 raise 而非靜默寫入**（比照該函式既有的 `if not tl: raise ValueError`）。否則下一次同類漏接仍會靜默通過。<br>**歷史 12 列**：不回填、不刪除，建議在 parquet 或文件標明「schema v≤N 的列 max_score 不可用」。 |
| **影響評估** | **LOW（修法）／HIGH（不修的代價）**。修法是一行 + 一道守衛；不修的話前進式驗證資料集**永久無法重建 health**。<br>⚠️ 加 raise 守衛屬行為變更（cron 可能開始紅燈）→ 須走 §8 流程 + 突變測試（§-1.5.E A7）。 |

### 提案 M-6｜量綱命名規範未落實（`§4.1` 既有條款）

| 欄 | 內容 |
|---|---|
| **變更條款** | `CLAUDE.md §4.1`「新增變數**必須**編碼單位」 |
| **阻礙原因** | 現況大量違反但**尚未造成已知事故**：`YIELD_HIGH` vs `YIELD_HIGH_DEC`（差 100×）、`MAX_PORTFOLIO_DRAWDOWN=0.15`（比例）vs `position_throttle` 的 `80/50/20`（百分比，差 100×）、`EXPOSURE_BULL` 系列（比例）vs 油門（百分比）。 |
| **替代方案（推薦）** | **不做全域改名**（純 cosmetic、動到數十個 caller，正是 `§8.1 step 6` 反例 + 未過 `§8.4 step 4` scope gate）。<br>**推薦改為由測試守住**：新增一個 CI 守衛，斷言「**同一概念的 `%` 版與 `_DEC`／比例版必須由推導產生，不得各自寫死**」（`YIELD_*_DEC` 目前**已符合**此規則，可直接當基準案例）。<br>新增常數才適用命名規範。 |
| **影響評估** | **LOW。** 純新增測試，零行為變更。 |

---

## 5. 同一指標兩站算法不同的地方（影響能否統一）

| # | 指標 | 台股／ETF 站 | 基金站 | 可否統一 |
|---|---|---|---|---|
| **D-1** | **Sharpe 報酬定義** | **簡單報酬** `pct_change()`（S-1）／週簡單報酬（S-2） | **對數報酬** `log_ret`（S-3） | ⚠️ **可統一但屬行為變更**。推薦以對數為準（S-3 已有完整樣本閘門 + σ=0 守衛）。 |
| **D-2** | **Sharpe 週期** | S-1 日×252；**S-2 週×√52** | 日×252 | ⚠️ 可統一為 kernel + `periods_per_year` 參數。**S-2 的週化是判 B 燈的唯一來源，改動會改燈色。** |
| **D-3** | **Sharpe rf** | 模組級 `_RF_PCT`，fallback **5.33%** | 模組級 `_RF_ANNUAL`，預設 **4%**；效率前緣 **0%** | ⚠️ **三個不同的 fallback 值**。注入成功時都是 FEDFUNDS ⇒ **僅在注入失敗時分歧**，但那正是最需要一致的時候。推薦統一 fallback 到單一 L0 常數。 |
| **D-4** | **Sharpe 樣本門檻** | S-1 `len(ret) < 20` → **回 0.0**；S-2 `< 14 週` → `None` | `n252 < MIN_OBS_SHARPE_SORTINO` → `None` + reason | ❌ **S-1 的 `0.0` 必須先修成 `None` 才談得上統一**（見 §1.1 警告）。 |
| **D-5** | **σ ddof** | ETF `ret.std()`（ddof=1）；Bollinger 刻意 **ddof=0**（v19.105，母體 σ，原 ddof=1 帶寬虛胖 ~2.6%） | `.std()`（ddof=1） | ✅ 可統一（Bollinger 的 ddof=0 是刻意且有理由，應保留為例外並登記）。 |
| **D-6** | **年化天數** | 252（`TRADING_DAYS_PER_YEAR`）；CAGR 用 **365.25** 日曆日 | 252；年化報酬用 **365.25** | ✅ **兩站一致** —— 波動/Sharpe 用 252 交易日、報酬年期用 365.25 日曆日。 |
| **D-7** | **MDD** | `min((close − cummax)/cummax × 100)` | `round(_dd × 100, 2)` | ✅ 同式，可統一。 |
| **D-8** | **「含息」的落實** | ETF 走**還原價**（`total_return_pct` docstring 明寫「用還原價 → 已含息」）；個股 357 用**5 年平均配息** | 4 層 chain，**第 3/4 層不含息** | ⚠️ **不可直接統一** —— 兩站的資料可得性不同（ETF 有還原價、基金只有 NAV+配息記錄）。可統一的是**來源標籤制度**（基金站的 `SRC_*` 做得較好，建議台股站沿用）。 |
| **D-9** | **等第分界** | 個股健康 `A≥80 / B≥50`（`health_thresholds`）；財報體檢 `F/C/B+/A+/A/B` **由 fail_items 數決定，非分數帶** | 4D `A≥80 / B≥65 / C≥50 / D≥35 / F<35` | ❌ **不可統一** —— 台股財報體檢的等第**不是分數帶**，是 fail 計數決策樹。強行統一會改變全部等第。 |
| **D-10** | **缺值退出分母** | 總經健康 ✅ 權重重新歸一化；財報體檢 [673] ✅ gate；[main] ❌ | ✅ 4D `coverage` 揭露分母；`switch_score` ✅ 縮分母（80/85/65） | ✅ **方向一致**（缺值退出分母 + 揭露），基金站的 `coverage.n_total` 揭露範式**建議台股站沿用**。 |
| **D-11** | **同類比較** | 無此概念（個股比的是全市場百分位 `_percentile_scores`） | MoneyDJ 同類平均 + 小 universe 四分位 | — 不適用（兩站業務不同）。 |
| **D-12** | **Sortino** | ❌ **台股站無 Sortino** | ✅ 有，且用正確 TDD（分母全樣本 N，MAR=rf） | — 若日後台股站要加，**必須直接用基金站的正確式**，不可重蹈 `r[r<0].std()`。 |

---

## 6. 我沒能驗到的事（§-2 規則 6）

> 以下全部為**單組結論**或**根本未查**，**不得**作為後續動作的前提。

| # | 事項 | 狀態 |
|---|---|---|
| **U-1** | 「DTB3 / 台灣央行定存利率在兩站皆 0 命中」 | **單組 grep 結論**。只搜了 `DTB3` / `risk_free` / `riskfree` / `rf_rate` / `定存`。若以別的措辭存在（例如中文「一年期」、或 FRED series id 寫在某個 dict value 裡）本次掃不到。 |
| **U-2** | 「本附錄涵蓋了客戶指定的全部指標」 | **未窮舉**。客戶點名的指標我逐一查了，但**沒有反向確認 repo 裡還有哪些指標沒進這份附錄**。兩站合計數百個計算函式，本次是**由需求出發的定向查證**，不是全站盤點。 |
| **U-3** | `etf_calc.calc_sharpe`（S-1）的 `0.0` 回傳流向哪些消費端 | **未追到底**。已確認 `health_b` 吃的是 S-2 不是 S-1，但 S-1 被 `build_etf_score_row` / ETF 多檔比較表消費 —— **那些地方會不會把 0.0 當成有效 Sharpe 排序／評分，本次未驗**。這是判斷 S-1 嚴重度的關鍵，**優先請獨立一組驗**。 |
| **U-4** | `financial_health_engine` 的 `fd.get(k,0) or 0` 在 [main] 的**確切處數** | 我實測正規式 `\.get\([^)]*,\s*0\)\s*or\s*0` 在 [main] 命中 **6 處**；PR #673 body 自陳全檔同型模式 **49 處**（改 20、不改 29）。**兩個數字對不起來** —— 可能是 PR 用了更寬的模式定義（含 `fd.get(k) or 0`、`or 0.0` 等變形）。**我沒有重跑 PR 的盤點方法，無法裁定哪個數字對。** PR body 自己也把「49 處」與「不改的 29 處都安全」列為**未經第二組驗證的宣稱**。 |
| **U-5** | 基金站 `peer_compare` 的**更新週期** | **查不到**。搜了 TTL / 快取 / 更新週期相關字樣，未找到對 `peer_compare` 的週期宣告。**不排除存在於我沒搜到的地方**（例如 `repositories/fund/` 的抓取層）。母法要求「標註更新週期」，**現況是否真的沒標，需要第二組確認**。 |
| **U-6** | 基金站 `max_drawdown` 的樣本門檻與缺值語義 | **未追**。只看到 `switch_strategy.py:76` 自陳「`calc_metrics` 把 max_drawdown 的樣本門檻…完全無法區分」，**沒有讀 `calc_metrics` 的對應段落**。 |
| **U-7** | `is_extrapolated_1y_source()` 是否**所有**吃本金判定 caller 都照做 | **未窮舉**。只確認該函式存在且 docstring 要求 caller 拒判，**沒有逐一檢查 caller**。若有 caller 漏做，ACTI71 型的假 🔴 會復發。 |
| **U-8** | 基金站 σ 的兩種報酬口徑（`base` vs `log_ret`）各自餵給誰 | **未釐清**。`fund_service.py:423` 與 `:453` 用不同口徑，本次沒有追各自的消費端，**無法判斷是否為刻意分流或真的不一致**。 |
| **U-9** | 基金站 UI 是否真的把 MoneyDJ「平均」寫成「中位數」 | **未檢查 UI 字串**。我確認了**計算路徑**取的是平均，但**沒有逐一檢查畫面文案**。提案 M-4① 的前提（「畫面寫成中位數」）**尚未證實**。 |
| **U-10** | [673] 的「單格缺漏仍會讓等級偏好」 | **我的推論，非實測**。依據是等第決策樹全掛在 `len(fail_items)` 而 N/A 不進 fail_items。**沒有跑反例驗證**（例如只讓一格缺、其餘正常，看等級會不會比全齊時更好）。 |
| **U-11** | ~~`bias_240` 的 `or 0` 實際會不會觸發~~ | ✅ **已補查（收工前）**，結論**修正如下**，請以此為準：<br>`shared/calc_helpers.calc_bias_pct` 的 docstring 明寫「若 price/ma 為 None **或 `ma <= 0`** → 回 None」。而 caller `compute_twii_bias` 的 `_maN` 來自 `_cs = _twii[_cc_b].dropna()` 且 `_n > 0` 已先 guard ⇒ **台股指數收盤價恆 > 0，`ma > 0` 恆成立 ⇒ `calc_bias_pct` 在此 caller 永不回 None ⇒ `or 0` 是死碼**。<br>⇒ **§2.10(b) 的嚴重度應下修**：它**不是**正在製造假綠燈的活 bug，而是一個「看起來有守衛、實際不觸發」的 §1 表面違規。<br>⚠️ 但**仍建議修**（改成不帶 `or 0`），理由同 `CLAUDE.md §-2` 的 `db4c139` 前例：留著會讓下一個人以為「缺值已被處理」。<br>⚠️ 本結論為**單組推導**（推論鏈：`close > 0` → `mean > 0` → `ma > 0`），**未跑反例實測**。 |
| **U-15** | squash merge `5808c03` 的內容是否與我讀的分支 HEAD `ee6ffa5` 逐檔相同 | **未比對**。我對 [673] 的記錄全部讀自 merge 前的工作樹。**理論上 squash 內容相同，但沒驗。** |
| **U-16** | merge `5808c03` 另外帶進的 13 個檔案 | **完全沒查**。含 `macro_refresh_service.py`(+929)、`test_p01_macro_refresh.py`(+1748)、`page_today.py`(+550)、`macro_session_patch.py`(+176)、`macro_fetch_orchestrator.py`、`macro_session_apply.py`、`page_inspect.py`、`section_financial_health.py`、`station_specs.py` 等。**裡面有沒有新指標、或改到本附錄已記錄的指標，一律未知。** ⇒ **本附錄對現行 production 的涵蓋率低於它看起來的樣子，請據此打折。** |
| **U-12** | KD 的 `.replace(0, 1)` 實際觸發頻率 | **未實測**。連續 9 日 high==low 在台股（跌停鎖死）是可能的但罕見。**未量測**。 |
| **U-13** | 兩站是否還有第四、第五份 Sharpe 實作 | **單組 grep 結論**。台股站搜 `sharpe` 找到 S-1/S-2；基金站找到 S-3 + `portfolio_frontier._sharpe` + `portfolio_performance`。**後兩者我只看了 rf 參數，沒有比對算式**。 |
| **U-14** | 母法四條的「**現行畫面**」符合度 | **完全未驗**。本附錄查的是 **code 算式**。畫面上實際印出什麼數字、標什麼文案，**沒有跑起來看過**（沙箱無 Streamlit 實機）。 |

---

## 7. 唯讀紀律驗證（**含一件必須上報的意外**）

### 7.1 結果

| repo | 開工時 | 收工時 | 結論 |
|---|---|---|---|
| **台股站** `/home/user/my-stock-dashboard` | HEAD `ee6ffa5`<br>` M src/ui/views/page_why.py`<br>` M tests/test_p05_why_view.py` | HEAD **`5808c03`**<br>`git status --porcelain` **空** | ⚠️ **狀態變了，但不是我造成的** —— 見 7.2 |
| **基金站** `/home/user/linchen-20200325/my-fund-dashboard` | HEAD `9cbf037`，status 空 | HEAD `9cbf037`，status 空 | ✅ 完全未動 |

### 7.2 🚨 台股站在我作業期間被外部 merge（誠實上報，§1）

**發生什麼**：PR #673 於 `Mon Sep 14 17:27:31 2026 +0800` 被 **squash-merge 進 `origin/main`**，本地分支隨之前進。

| 項 | 值 |
|---|---|
| merge commit | `5808c03ce336be8ff48b9692bb16421c7c57e61d` |
| commit 作者 | `linchen-20200325 <cheng10022@gmail.com>` |
| commit 訊息 | `fix(§1): 缺資料不得產出結論 —— 財報假結論四條路徑 ＋ 頁1 原地取數 ＋ 頁5 十六盞燈 (#673)` |
| 規模 | 15 檔、`+5,749 / −197` |
| 我的 baseline `ee6ffa5` | 物件仍在（`git cat-file -t` → `commit`），未被 GC |

**不是我做的 —— 證據三條**：
1. 我全程只執行 `git status` / `git log` / `git show` / `git diff` / `git rev-parse` / `git branch` / `git cat-file` / `git fetch`（唯讀指令）。**沒有執行過 `commit` / `merge` / `push` / `add` / `checkout` / `reset` / `stash`**。
2. commit 的 author/committer 是 **user 本人的帳號**（`cheng10022@gmail.com`），不是本 session 的 attribution（本 session 的 commit 會帶 `Co-Authored-By: Claude Opus 5`，該 commit **沒有**）。
3. 該 merge 把 **15 個檔案** 一次帶進來，其中 13 個我從未讀寫過（`macro_refresh_service.py`、`test_p01_macro_refresh.py` 等）—— 我不可能產出這些內容。

**兩個原本 modified 的檔案去哪了**：被這次 squash merge 一併收進 commit，所以 working tree 轉為 clean。
**它們的內容在我作業期間一個 byte 都沒變**（md5 前後一致，見下表）—— 也就是說，**不是我改了它們之後被人 commit**：

| 檔案 | 開工 md5 | 收工 md5 | 一致 |
|---|---|---|---|
| `src/ui/views/page_why.py` | `580285be28cd5aa14eb866282f20a047` | `580285be28cd5aa14eb866282f20a047` | ✅ |
| `tests/test_p05_why_view.py` | `c94ba209446a0cabcad4385827168fb3` | `c94ba209446a0cabcad4385827168fb3` | ✅ |

**其他佐證**：兩站 `git stash list` 全程皆空；基金站 HEAD 與 status 完全未動。
**我唯一的寫入**：`scratchpad/probe_maxscore.py`（唯讀探針）＋ 本檔，**皆在 scratchpad，不在任何 repo 內**。

⇒ **我沒有修改、新增、刪除或提交兩個 repo 的任何檔案。**

### 7.3 對交辦條件的誠實對照

交辦要求「結束時兩個 repo 的 `git status --porcelain` 都必須為空」。

- **結果上：兩站都空了** ✅
- **但台股站之所以空，不是因為我沒動它（我本來就沒動），而是因為外部 merge 把原本既有的兩個 modified 檔案收掉了。** 我開工時它**就不是空的**，那兩個 modified 檔案**在我到場之前就存在**。
- ⇒ 「收工時為空」這個結果**不能**被當成「我全程唯讀」的證明。真正的證明是 7.2 的三條證據 + md5 比對，請以那個為準。

### 7.4 這件事對本交付物的影響

1. **§0.1 / §2.3 已就地更新**：[673] 現在就是 production，不再是「待 merge 的分支」。
2. ⚠️ **我對 [673] 的所有記錄，讀的是 merge 前的分支內容（HEAD `ee6ffa5`）**。squash merge 到 `5808c03` 的內容**理論上**相同，但**我沒有在 merge 後重新逐檔比對**（見 §6 U-15）。
3. ⚠️ **這次 merge 另外帶進 13 個我沒讀過的檔案**（含 `macro_refresh_service.py` +929 行、`macro_session_patch.py` +176 行、`page_today.py` +550 行）。**那些檔案裡有沒有新的指標、或改到本附錄已記錄的指標，我完全沒查**（見 §6 U-16）。**本附錄對 production 的涵蓋率因此低於它看起來的樣子。**

---

## 附錄 A — 本次使用的探針腳本

`/tmp/claude-0/-home-user-my-stock-dashboard/2192ed9a-9da4-598a-89d9-60cb1a4f22b2/scratchpad/probe_maxscore.py`
唯讀，import 兩個 L2 純函式並印出回傳 dict 的 key 集合。不寫檔、不打網路。
